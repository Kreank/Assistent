"""Microsoft: Outlook-Mail, Outlook-Kalender und OneDrive (seit 19.11.2026).

WARUM NICHT DER CONNECTOR AUS DER CLAUDE-APP

Sascha hat sein Microsoft-Konto in der Claude-App verbunden. Sarvis laeuft
aber mit strict_mcp_config und ohne externe MCP-Server -- die kosteten je
Zuruf rund 2,4 Sekunden. Also wie bei Google: eigene Werkzeuge im
Prozess, die Microsoft Graph direkt ansprechen.

ANMELDUNG

Privates Konto (hotmail) -> Endpunkt "consumers". Oeffentlicher Client
ohne Geheimnis, Geraetecode-Fluss: einsatz/microsoft_anmelden.py zeigt
einen Code, Sascha bestaetigt ihn auf www.microsoft.com/link (privates Konto), danach
liegt hier ein Auffrischungs-Token in /srv/data/sarvis/microsoft_token.json
(chmod 600). Die App-Kennung (Client-ID) steht als MICROSOFT_CLIENT_ID in
/srv/data/sarvis/.env. Bewusst kein msal: Das waere ein Neubau des Images
fuer zwei HTTP-Aufrufe.

TEAMS

Gibt es hier nicht. Microsoft bietet die Teams-Schnittstellen nur fuer
Firmen- und Schulkonten an, nicht fuer private.

STUFEN (config.WERKZEUG_STUFEN)

Ansehen still; Senden, Verschieben, Termine anlegen/loeschen, Hochladen
und Anhaenge aus fremder Hand fragen nach -- wie bei Google. Senden und
Loeschen stehen zusaetzlich in FREIGABE_NIE.
"""
import asyncio
import json
import os
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

import httpx
from claude_agent_sdk import tool

from .. import config

TOKEN_DATEI = config.DATEN / "microsoft_token.json"
BEHOERDE = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
GRAPH = "https://graph.microsoft.com/v1.0"
BEREICHE = ("offline_access User.Read Mail.ReadWrite Mail.Send "
            "Calendars.ReadWrite Files.ReadWrite")
ZEITZONE = "Europe/Berlin"
ZEITGRENZE = 30.0
LESE_GRENZE = 6000
EINFACH_HOCHLADEN = 4 * 1024 * 1024     # darueber: Upload-Sitzung
STUECK = 5 * 320 * 1024                 # Vielfaches von 320 KiB (Graph)

_schloss = asyncio.Lock()
# Die zuletzt gezeigten Listen. Graph-IDs sind 150 Zeichen lang -- die
# sagt niemand. Sarvis spricht von "Mail 2" und "Termin 3".
_mails: list[dict] = []
_termine: list[dict] = []
_dateien: list[dict] = []


# --- Anmeldung ------------------------------------------------------------

def client_id() -> str | None:
    return config._env_werte().get("MICROSOFT_CLIENT_ID")


def bereit() -> bool:
    return bool(client_id()) and TOKEN_DATEI.exists()


def token_speichern(daten: dict) -> None:
    gespeichert = {
        "access_token": daten["access_token"],
        "refresh_token": daten.get("refresh_token"),
        "laeuft_ab": time.time() + int(daten.get("expires_in", 3600)) - 120,
    }
    tmp = TOKEN_DATEI.with_suffix(".tmp")
    tmp.write_text(json.dumps(gespeichert), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(TOKEN_DATEI)


async def _token() -> str | None:
    async with _schloss:
        try:
            t = json.loads(TOKEN_DATEI.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if t.get("laeuft_ab", 0) > time.time():
            return t["access_token"]
        if not t.get("refresh_token"):
            return None
        async with httpx.AsyncClient(timeout=ZEITGRENZE) as c:
            r = await c.post(f"{BEHOERDE}/token", data={
                "client_id": client_id(), "grant_type": "refresh_token",
                "refresh_token": t["refresh_token"], "scope": BEREICHE})
        if r.status_code != 200:
            print(f"  ! Microsoft-Token nicht erneuert: {r.text[:200]}")
            return None
        daten = r.json()
        # Microsoft dreht das Auffrischungs-Token bei jedem Auffrischen.
        # Kommt keins mit, gilt das alte weiter.
        daten.setdefault("refresh_token", t["refresh_token"])
        token_speichern(daten)
        return daten["access_token"]


class KeinZugang(Exception):
    pass


async def _graph(methode: str, pfad: str, *, json_daten=None, params=None,
                 kopf=None, inhalt=None, roh=False):
    token = await _token()
    if not token:
        raise KeinZugang()
    kopfzeilen = {"Authorization": f"Bearer {token}",
                  "Prefer": f'outlook.timezone="{ZEITZONE}", '
                            'outlook.body-content-type="text"'}
    kopfzeilen.update(kopf or {})
    url = pfad if pfad.startswith("http") else GRAPH + pfad
    async with httpx.AsyncClient(timeout=ZEITGRENZE, follow_redirects=True) as c:
        r = await c.request(methode, url, json=json_daten, params=params,
                            headers=kopfzeilen, content=inhalt)
    if r.status_code >= 400:
        try:
            meldung = r.json().get("error", {}).get("message", "")
        except ValueError:
            meldung = r.text[:200]
        raise RuntimeError(f"Microsoft sagt {r.status_code}: {meldung[:200]}")
    if roh:
        return r
    if r.status_code == 204 or not r.content:
        return {}
    return r.json()


def _antwort(text: str, fehler: bool = False) -> dict:
    a = {"content": [{"type": "text", "text": text}]}
    if fehler:
        a["is_error"] = True
    return a


KEIN_ZUGANG = ("Der Microsoft-Zugang ist abgelaufen oder fehlt. Sascha muss "
               "sich neu anmelden (einsatz/microsoft_anmelden.py).")


def _sicher(f):
    """Fehler als Satz statt als Absturz des Zugs."""
    async def huelle(args):
        try:
            return await f(args)
        except KeinZugang:
            return _antwort(KEIN_ZUGANG, True)
        except (RuntimeError, httpx.HTTPError) as e:
            return _antwort(f"Microsoft: {e}", True)
    huelle.__name__ = f.__name__
    return huelle


# --- Zeiten ---------------------------------------------------------------

def zeit_deuten(roh: str) -> datetime | None:
    """'20.11.2026 15:30', '20.11. 15:30', '2026-11-20T15:30' -> datetime."""
    s = " ".join(str(roh or "").replace(" um ", " ").split())
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        pass
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{2,4})?\s*(\d{1,2})?(?::(\d{2}))?", s)
    if not m:
        return None
    tag, monat = int(m.group(1)), int(m.group(2))
    jahr = int(m.group(3)) if m.group(3) else date.today().year
    if jahr < 100:
        jahr += 2000
    stunde = int(m.group(4)) if m.group(4) else 9
    minute = int(m.group(5)) if m.group(5) else 0
    try:
        return datetime(jahr, monat, tag, stunde, minute)
    except ValueError:
        return None


def _zeit_lesbar(graphzeit: dict, ganztag: bool = False) -> str:
    try:
        d = datetime.fromisoformat(graphzeit["dateTime"][:19])
    except (KeyError, ValueError, TypeError):
        return "?"
    wochentag = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"][d.weekday()]
    return f"{wochentag} {d:%d.%m.}" + ("" if ganztag else f" {d:%H:%M}")


def _absender(m: dict) -> str:
    a = (m.get("from") or {}).get("emailAddress") or {}
    return a.get("name") or a.get("address") or "?"


def _nummer(liste: list, roh, art: str):
    try:
        n = int(roh)
    except (TypeError, ValueError):
        return None, f"Welche {art}? Gib die Nummer aus der letzten Liste."
    if not 1 <= n <= len(liste):
        return None, (f"{art} {n} kenne ich nicht — erst die Liste neu "
                      "holen.")
    return liste[n - 1], None


# --- Fuer die Rueckfrage ----------------------------------------------------
#
# Die Werkzeuge arbeiten mit Listennummern, Sascha sieht die Liste aber nie:
# "Soll ich die Outlook-Mail 6 nach papierkorb verschieben?" war nicht zu
# beantworten (Sascha, 19.11.: "Woher soll ich wissen, was Mail 6 ist?").
# Diese Helfer loesen die Nummer in das auf, was man wiedererkennt.

def mail_benennen(nummer) -> str | None:
    """'die Mail von X vom TT.MM., Betreff „Y“' -- oder None, wenn unbekannt."""
    m, fehler = _nummer(_mails, nummer, "Mail")
    if fehler:
        return None
    betreff = " ".join(str(m.get("subject") or "").split()) or "ohne Betreff"
    if len(betreff) > 70:
        betreff = betreff[:69].rsplit(" ", 1)[0] + "…"
    wann = (m.get("receivedDateTime") or "")[:10]
    datum = f" vom {wann[8:10]}.{wann[5:7]}." if len(wann) == 10 else ""
    return f"die Mail von {_absender(m)}{datum}, Betreff „{betreff}“"


def anhang_benennen(nummer, anhang) -> str | None:
    m, fehler = _nummer(_mails, nummer, "Mail")
    if fehler or not m.get("_anhaenge"):
        return None
    a, fehler = _nummer(m["_anhaenge"], anhang, "Anhang")
    return None if fehler else (str(a.get("name") or "") or None)


def termin_benennen(nummer) -> str | None:
    t, fehler = _nummer(_termine, nummer, "Termin")
    if fehler:
        return None
    titel = t.get("subject") or "ohne Titel"
    return (f"den Termin „{titel}“ am "
            f"{_zeit_lesbar(t.get('start'), bool(t.get('isAllDay')))}")


# --- Werkzeuge ------------------------------------------------------------

def werkzeuge(protokoll=None, leuchten=None) -> list:

    def blinken():
        if leuchten:
            leuchten("Microsoft")

    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    # ----- Mail -----

    @tool(
        "outlook_mails_ansehen",
        "Zeigt Mails aus Saschas OUTLOOK-/Hotmail-Postfach (nicht Gmail). "
        "Ohne Suche die neuesten im Posteingang. Ergebnis ist eine "
        "nummerierte Liste — mit der Nummer weiterlesen, antworten, "
        "verschieben.",
        {"type": "object", "properties": {
            "suche": {"type": "string",
                      "description": "Optional Suchbegriff (Absender, Betreff, Text)."},
            "nur_ungelesen": {"type": "boolean"},
            "anzahl": {"type": "integer", "minimum": 1, "maximum": 30,
                       "description": "Vorgabe 10."},
        }},
    )
    @_sicher
    async def outlook_mails_ansehen(args):
        blinken()
        anzahl = int(args.get("anzahl") or 10)
        felder = "id,subject,from,receivedDateTime,isRead,bodyPreview,hasAttachments"
        suche = (args.get("suche") or "").strip().replace('"', "")
        if suche:
            daten = await _graph("GET", "/me/messages", params={
                "$search": f'"{suche}"', "$top": anzahl, "$select": felder})
        else:
            params = {"$top": anzahl, "$select": felder,
                      "$orderby": "receivedDateTime desc"}
            if args.get("nur_ungelesen"):
                params["$filter"] = "isRead eq false"
            daten = await _graph("GET", "/me/mailFolders/inbox/messages",
                                 params=params)
        mails = daten.get("value") or []
        _mails[:] = mails
        if not mails:
            return _antwort("Keine passenden Mails im Outlook-Postfach.")
        zeilen = []
        for i, m in enumerate(mails, 1):
            wann = (m.get("receivedDateTime") or "")[:16].replace("T", " ")
            zeilen.append(
                f"{i}. {'' if m.get('isRead') else '[neu] '}{_absender(m)} — "
                f"{m.get('subject') or '(ohne Betreff)'} ({wann} UTC"
                f"{', Anhang' if m.get('hasAttachments') else ''}): "
                f"{(m.get('bodyPreview') or '')[:120]}")
        return _antwort("\n".join(zeilen))

    @tool(
        "outlook_mail_lesen",
        "Liest eine Outlook-Mail ganz, Nummer aus outlook_mails_ansehen. "
        "Nennt auch die Anhänge.",
        {"type": "object", "properties": {"nummer": {"type": "integer"}},
         "required": ["nummer"]},
    )
    @_sicher
    async def outlook_mail_lesen(args):
        blinken()
        m, fehler = _nummer(_mails, args.get("nummer"), "Mail")
        if fehler:
            return _antwort(fehler, True)
        voll = await _graph("GET", f"/me/messages/{m['id']}", params={
            "$select": "subject,from,toRecipients,ccRecipients,"
                       "receivedDateTime,body,hasAttachments"})
        text = ((voll.get("body") or {}).get("content") or "").strip()
        gekuerzt = ""
        if len(text) > LESE_GRENZE:
            text, gekuerzt = text[:LESE_GRENZE], "\n[… gekürzt]"
        an = ", ".join((r.get("emailAddress") or {}).get("address", "")
                       for r in voll.get("toRecipients") or [])
        anhaenge = ""
        if voll.get("hasAttachments"):
            liste = await _graph("GET", f"/me/messages/{m['id']}/attachments",
                                 params={"$select": "id,name,size"})
            m["_anhaenge"] = liste.get("value") or []
            anhaenge = "\nAnhänge: " + "; ".join(
                f"{i}. {a.get('name')} ({int(a.get('size', 0)) // 1024} KB)"
                for i, a in enumerate(m["_anhaenge"], 1))
        return _antwort(
            f"Von: {_absender(voll)}\nAn: {an}\nBetreff: {voll.get('subject')}\n"
            f"Empfangen: {(voll.get('receivedDateTime') or '')[:16]} UTC"
            f"{anhaenge}\n\n{text or '(kein Text)'}{gekuerzt}")

    @tool(
        "outlook_mail_senden",
        "Schickt eine Mail aus Saschas OUTLOOK-/Hotmail-Konto. Mit "
        "'antwort_auf' (Nummer aus der Liste) als Antwort auf diese Mail. "
        "Nur wenn er ausdrücklich Outlook/Hotmail will — sonst mail_senden "
        "(Gmail).",
        {"type": "object", "properties": {
            "an": {"type": "string", "description": "Adresse(n), mit Komma getrennt. "
                                                    "Bei Antwort leer lassen."},
            "betreff": {"type": "string"},
            "text": {"type": "string"},
            "cc": {"type": "string"},
            "antwort_auf": {"type": "integer"},
        }, "required": ["text"]},
    )
    @_sicher
    async def outlook_mail_senden(args):
        blinken()
        text = str(args.get("text") or "")

        def empfaenger(roh):
            return [{"emailAddress": {"address": a.strip()}}
                    for a in str(roh or "").split(",") if "@" in a]

        if args.get("antwort_auf"):
            m, fehler = _nummer(_mails, args.get("antwort_auf"), "Mail")
            if fehler:
                return _antwort(fehler, True)
            await _graph("POST", f"/me/messages/{m['id']}/reply",
                         json_daten={"comment": text})
            vermerken(f"outlook_mail_senden: Antwort auf „{m.get('subject')}“ verschickt")
            return _antwort(f"Antwort an {_absender(m)} ist raus.")
        an = empfaenger(args.get("an"))
        if not an:
            return _antwort("An wen? Es fehlt eine gültige Adresse.", True)
        nachricht = {"subject": args.get("betreff") or "",
                     "body": {"contentType": "Text", "content": text},
                     "toRecipients": an}
        if args.get("cc"):
            nachricht["ccRecipients"] = empfaenger(args.get("cc"))
        await _graph("POST", "/me/sendMail",
                     json_daten={"message": nachricht, "saveToSentItems": True})
        vermerken(f"outlook_mail_senden: an {args.get('an')} — {args.get('betreff')}")
        return _antwort(f"Mail an {args.get('an')} ist raus.")

    @tool(
        "outlook_mail_verschieben",
        "Verschiebt eine Outlook-Mail (Nummer aus der Liste): ins Archiv, "
        "in den Papierkorb, in den Spam oder in einen Ordner mit Namen.",
        {"type": "object", "properties": {
            "nummer": {"type": "integer"},
            "wohin": {"type": "string",
                      "description": "'archiv', 'papierkorb', 'spam', 'posteingang' "
                                     "oder ein Ordnername."},
        }, "required": ["nummer", "wohin"]},
    )
    @_sicher
    async def outlook_mail_verschieben(args):
        blinken()
        m, fehler = _nummer(_mails, args.get("nummer"), "Mail")
        if fehler:
            return _antwort(fehler, True)
        wohin = str(args.get("wohin") or "").strip()
        ziel = {"archiv": "archive", "papierkorb": "deleteditems",
                "spam": "junkemail", "posteingang": "inbox"}.get(wohin.lower())
        if not ziel:
            ordner = await _graph("GET", "/me/mailFolders",
                                  params={"$top": 100, "$select": "id,displayName"})
            treffer = [o for o in ordner.get("value") or []
                       if o.get("displayName", "").lower() == wohin.lower()]
            if not treffer:
                namen = ", ".join(o.get("displayName", "") for o in ordner.get("value") or [])
                return _antwort(f"Einen Ordner „{wohin}“ gibt es nicht. Da sind: {namen}", True)
            ziel = treffer[0]["id"]
        await _graph("POST", f"/me/messages/{m['id']}/move",
                     json_daten={"destinationId": ziel})
        vermerken(f"outlook_mail_verschieben: „{m.get('subject')}“ → {wohin}")
        return _antwort(f"Verschoben nach {wohin}.")

    @tool(
        "outlook_anhang_holen",
        "Legt einen Anhang einer Outlook-Mail auf dem Server ab (Mail-Nummer "
        "und Anhang-Nummer aus outlook_mail_lesen). Danach mit datei_lesen "
        "ansehen oder datei_schicken weitergeben.",
        {"type": "object", "properties": {
            "nummer": {"type": "integer"}, "anhang": {"type": "integer"}},
         "required": ["nummer", "anhang"]},
    )
    @_sicher
    async def outlook_anhang_holen(args):
        from .google import _anhang_ziel, _dateiname_saeubern
        blinken()
        m, fehler = _nummer(_mails, args.get("nummer"), "Mail")
        if fehler:
            return _antwort(fehler, True)
        if not m.get("_anhaenge"):
            return _antwort("Erst die Mail mit outlook_mail_lesen öffnen.", True)
        a, fehler = _nummer(m["_anhaenge"], args.get("anhang"), "Anhang")
        if fehler:
            return _antwort(fehler, True)
        r = await _graph("GET", f"/me/messages/{m['id']}/attachments/{a['id']}/$value",
                         roh=True)
        ziel = _anhang_ziel(_dateiname_saeubern(a.get("name")))
        if ziel is None:
            return _antwort("Der Dateiname taugt nicht als Ablageort.", True)
        ziel.write_bytes(r.content)
        vermerken(f"outlook_anhang_holen: {ziel}")
        return _antwort(f"Liegt unter {ziel}.")

    # ----- Kalender -----

    @tool(
        "outlook_termine_ansehen",
        "Zeigt Termine aus Saschas OUTLOOK-Kalender (nicht Google). "
        "Nummerierte Liste — mit der Nummer löschen.",
        {"type": "object", "properties": {
            "tage": {"type": "integer", "minimum": 1, "maximum": 60,
                     "description": "Zeitraum, Vorgabe 7."},
            "ab": {"type": "string", "description": "Optional TT.MM.JJJJ, sonst ab heute."},
        }},
    )
    @_sicher
    async def outlook_termine_ansehen(args):
        blinken()
        beginn = zeit_deuten(args.get("ab")) if args.get("ab") else None
        beginn = (beginn or datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
        ende = beginn + timedelta(days=int(args.get("tage") or 7))
        daten = await _graph("GET", "/me/calendarView", params={
            "startDateTime": beginn.isoformat(), "endDateTime": ende.isoformat(),
            "$orderby": "start/dateTime", "$top": 50,
            "$select": "id,subject,start,end,location,isAllDay"},
            kopf={"Prefer": f'outlook.timezone="{ZEITZONE}"'})
        termine = daten.get("value") or []
        _termine[:] = termine
        if not termine:
            return _antwort("Im Outlook-Kalender steht in dem Zeitraum nichts.")
        zeilen = []
        for i, t in enumerate(termine, 1):
            ganz = bool(t.get("isAllDay"))
            ort = (t.get("location") or {}).get("displayName")
            zeilen.append(f"{i}. {_zeit_lesbar(t.get('start'), ganz)}"
                          + (" ganztägig" if ganz else
                             f"–{_zeit_lesbar(t.get('end'))[-5:]}")
                          + f": {t.get('subject') or '(ohne Titel)'}"
                          + (f" — {ort}" if ort else ""))
        return _antwort("\n".join(zeilen))

    @tool(
        "outlook_termin_anlegen",
        "Trägt einen Termin in Saschas OUTLOOK-Kalender ein. Nur wenn er "
        "ausdrücklich Outlook will — sonst termin_anlegen (Google).",
        {"type": "object", "properties": {
            "titel": {"type": "string"},
            "beginn": {"type": "string", "description": "TT.MM.JJJJ HH:MM"},
            "dauer_minuten": {"type": "integer", "description": "Vorgabe 60."},
            "ort": {"type": "string"},
            "notiz": {"type": "string"},
            "erinnern_minuten": {"type": "integer",
                                 "description": "Erinnerung vorher, Vorgabe 15."},
        }, "required": ["titel", "beginn"]},
    )
    @_sicher
    async def outlook_termin_anlegen(args):
        blinken()
        beginn = zeit_deuten(args.get("beginn"))
        if beginn is None:
            return _antwort(f"Mit dem Zeitpunkt {args.get('beginn')!r} kann ich "
                            "nichts anfangen (TT.MM.JJJJ HH:MM).", True)
        ende = beginn + timedelta(minutes=int(args.get("dauer_minuten") or 60))
        termin = {
            "subject": args.get("titel"),
            "start": {"dateTime": beginn.isoformat(), "timeZone": ZEITZONE},
            "end": {"dateTime": ende.isoformat(), "timeZone": ZEITZONE},
            "isReminderOn": True,
            "reminderMinutesBeforeStart": int(args.get("erinnern_minuten") or 15),
        }
        if args.get("ort"):
            termin["location"] = {"displayName": args["ort"]}
        if args.get("notiz"):
            termin["body"] = {"contentType": "Text", "content": args["notiz"]}
        await _graph("POST", "/me/events", json_daten=termin)
        vermerken(f"outlook_termin_anlegen: {args.get('titel')} am {beginn:%d.%m.%Y %H:%M}")
        return _antwort(f"Im Outlook-Kalender eingetragen: {args.get('titel')} "
                        f"am {beginn:%d.%m.} um {beginn:%H:%M} Uhr.")

    @tool(
        "outlook_termin_loeschen",
        "Löscht einen Termin aus dem Outlook-Kalender, Nummer aus "
        "outlook_termine_ansehen.",
        {"type": "object", "properties": {"nummer": {"type": "integer"}},
         "required": ["nummer"]},
    )
    @_sicher
    async def outlook_termin_loeschen(args):
        blinken()
        t, fehler = _nummer(_termine, args.get("nummer"), "Termin")
        if fehler:
            return _antwort(fehler, True)
        await _graph("DELETE", f"/me/events/{t['id']}")
        _termine.remove(t)
        vermerken(f"outlook_termin_loeschen: {t.get('subject')}")
        return _antwort(f"Gelöscht: {t.get('subject')}.")

    # ----- OneDrive -----

    @tool(
        "onedrive_suchen",
        "Sucht Dateien und Ordner in Saschas OneDrive (nicht Google Drive). "
        "Nummerierte Liste — mit der Nummer holen.",
        {"type": "object", "properties": {
            "suche": {"type": "string", "description": "Name oder Inhalt."}},
         "required": ["suche"]},
    )
    @_sicher
    async def onedrive_suchen(args):
        blinken()
        suche = str(args.get("suche") or "").replace("'", "''")
        daten = await _graph("GET", f"/me/drive/root/search(q='{suche}')", params={
            "$top": 20,
            "$select": "id,name,size,lastModifiedDateTime,file,folder,parentReference"})
        dateien = daten.get("value") or []
        _dateien[:] = dateien
        if not dateien:
            return _antwort("Nichts gefunden im OneDrive.")
        zeilen = []
        for i, d in enumerate(dateien, 1):
            art = "Ordner" if d.get("folder") else f"{int(d.get('size', 0)) // 1024} KB"
            wo = ((d.get("parentReference") or {}).get("path") or "").split("root:")[-1]
            zeilen.append(f"{i}. {d.get('name')} ({art}, geändert "
                          f"{(d.get('lastModifiedDateTime') or '')[:10]})"
                          + (f" in {wo}" if wo else ""))
        return _antwort("\n".join(zeilen))

    @tool(
        "onedrive_holen",
        "Lädt eine OneDrive-Datei (Nummer aus onedrive_suchen) auf den "
        "Server. Danach mit datei_lesen ansehen oder datei_schicken "
        "weitergeben. 'als_pdf' wandelt Word/Excel/PowerPoint vorher um.",
        {"type": "object", "properties": {
            "nummer": {"type": "integer"}, "als_pdf": {"type": "boolean"}},
         "required": ["nummer"]},
    )
    @_sicher
    async def onedrive_holen(args):
        from .google import _anhang_ziel, _dateiname_saeubern
        blinken()
        d, fehler = _nummer(_dateien, args.get("nummer"), "Datei")
        if fehler:
            return _antwort(fehler, True)
        if d.get("folder"):
            return _antwort("Das ist ein Ordner, keine Datei.", True)
        name = d.get("name") or "datei"
        params = None
        if args.get("als_pdf"):
            params = {"format": "pdf"}
            name = name.rsplit(".", 1)[0] + ".pdf"
        r = await _graph("GET", f"/me/drive/items/{d['id']}/content",
                         params=params, roh=True)
        ziel = _anhang_ziel(_dateiname_saeubern(name))
        if ziel is None:
            return _antwort("Der Dateiname taugt nicht als Ablageort.", True)
        ziel.write_bytes(r.content)
        return _antwort(f"Liegt unter {ziel} ({len(r.content) // 1024} KB).")

    @tool(
        "onedrive_hochladen",
        "Lädt eine Datei vom Server in Saschas OneDrive. Ohne Ordner landet "
        "sie in 'Sarvis'. Eine gleichnamige Datei wird nicht überschrieben.",
        {"type": "object", "properties": {
            "pfad": {"type": "string", "description": "Datei auf dem Server."},
            "ordner": {"type": "string",
                       "description": "Zielordner im OneDrive, z. B. 'Dokumente/Rechnungen'."},
        }, "required": ["pfad"]},
    )
    @_sicher
    async def onedrive_hochladen(args):
        from .. import schutz
        blinken()
        quelle = Path(schutz.pfad_aufloesen(str(args.get("pfad") or "")))
        if not quelle.is_file():
            return _antwort(f"Die Datei {quelle} gibt es nicht.", True)
        # Dieselbe Sperre wie datei_schicken: Zugangsdaten gehen nicht raus.
        if schutz.heikel(str(quelle)) or schutz.versenden_stufe(str(quelle)) == "nie":
            return _antwort("Diese Datei lade ich nicht hoch — sie kann "
                            "Zugangsdaten enthalten.", True)
        ordner = str(args.get("ordner") or "Sarvis").strip("/ ")
        ziel = "/".join(p for p in (ordner, quelle.name) if p)
        ziel_url = "/me/drive/root:/" + quote(ziel)
        groesse = quelle.stat().st_size
        konflikt = {"@microsoft.graph.conflictBehavior": "rename"}
        if groesse <= EINFACH_HOCHLADEN:
            erg = await _graph("PUT", f"{ziel_url}:/content",
                               params={"@microsoft.graph.conflictBehavior": "rename"},
                               inhalt=quelle.read_bytes(),
                               kopf={"Content-Type": "application/octet-stream"})
        else:
            sitzung = await _graph("POST", f"{ziel_url}:/createUploadSession",
                                   json_daten={"item": konflikt})
            adresse = sitzung["uploadUrl"]
            erg = {}
            with quelle.open("rb") as f, httpx.Client(timeout=120) as c:
                pos = 0
                while pos < groesse:
                    stueck = f.read(STUECK)
                    r = await asyncio.to_thread(
                        c.put, adresse, content=stueck, headers={
                            "Content-Range": f"bytes {pos}-{pos + len(stueck) - 1}/{groesse}"})
                    if r.status_code >= 400:
                        raise RuntimeError(f"Hochladen abgebrochen ({r.status_code})")
                    pos += len(stueck)
                    if r.status_code in (200, 201):
                        erg = r.json()
        vermerken(f"onedrive_hochladen: {quelle} → {ordner}/{erg.get('name', quelle.name)}")
        return _antwort(f"Liegt im OneDrive unter {ordner}/{erg.get('name', quelle.name)}.")

    return [outlook_mails_ansehen, outlook_mail_lesen, outlook_mail_senden,
            outlook_mail_verschieben, outlook_anhang_holen,
            outlook_termine_ansehen, outlook_termin_anlegen,
            outlook_termin_loeschen, onedrive_suchen, onedrive_holen,
            onedrive_hochladen]
