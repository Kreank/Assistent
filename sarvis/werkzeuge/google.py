"""Google: Kalender, Mail, Aufgaben, Kontakte, Drive.

Eine Anmeldung, fuenf Dienste. Bewusst ueber die klassischen APIs und
nicht ueber Googles fertige MCP-Server: Deren Anmeldung laeuft ueber
claude.ai, und dass claude.ai-Connectors Sarvis' eigene Sitzung NICHT
erreichen, haben wir gemessen. Der Zugang liegt so als Datei hier, wie
bei Telegram auch.

Die Berechtigungen sind absichtlich breit -- eingeschraenkt wird nicht
beim Zugriff, sondern bei der Rueckfrage. Lesen laeuft still durch;
alles, was hinausgeht oder etwas veraendert, fragt vorher.
"""
import asyncio
import base64
import re
from datetime import datetime, timedelta
from email.message import EmailMessage

from claude_agent_sdk import tool

from .. import config

BEREICHE = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/tasks",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

_dienste: dict = {}
_schloss = asyncio.Lock()


# --- Anmeldung ------------------------------------------------------------

def _zugangsdaten(erneuern: bool = True):
    """Gespeicherten Zugang laden und bei Bedarf auffrischen."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not config.GOOGLE_TOKEN.exists():
        return None
    try:
        zugang = Credentials.from_authorized_user_file(
            str(config.GOOGLE_TOKEN), BEREICHE
        )
    except Exception:
        return None

    if zugang and zugang.expired and zugang.refresh_token and erneuern:
        try:
            zugang.refresh(Request())
            config.GOOGLE_TOKEN.write_text(zugang.to_json(), encoding="utf-8")
        except Exception:
            # Im Testing-Modus laeuft der Zugang nach sieben Tagen ab --
            # dann hilft kein Auffrischen, nur neu anmelden.
            return None
    return zugang if zugang and zugang.valid else None


def bereit() -> bool:
    return config.GOOGLE_TOKEN.exists() and config.GOOGLE_ZUGANG.exists()


def _dienst(name: str, fassung: str):
    """Einen API-Zugang bauen und merken."""
    from googleapiclient.discovery import build

    if name in _dienste:
        return _dienste[name]
    zugang = _zugangsdaten()
    if zugang is None:
        return None
    _dienste[name] = build(name, fassung, credentials=zugang,
                           cache_discovery=False)
    return _dienste[name]


async def _hole(name: str, fassung: str):
    async with _schloss:
        return await asyncio.to_thread(_dienst, name, fassung)


def anmelden_interaktiv():
    """Einmalige Anmeldung im Browser. Gibt eine kleine Probe zurueck."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    fluss = InstalledAppFlow.from_client_secrets_file(
        str(config.GOOGLE_ZUGANG), BEREICHE
    )
    zugang = fluss.run_local_server(port=0, prompt="consent")
    config.GOOGLE_TOKEN.write_text(zugang.to_json(), encoding="utf-8")
    _dienste.clear()

    from googleapiclient.discovery import build
    proben = []
    try:
        k = build("calendar", "v3", credentials=zugang, cache_discovery=False)
        anzahl = len(k.calendarList().list().execute().get("items", []))
        proben.append(("Kalender", f"{anzahl} Kalender"))
    except Exception as e:
        proben.append(("Kalender", f"Fehler: {e}"))
    try:
        m = build("gmail", "v1", credentials=zugang, cache_discovery=False)
        adresse = m.users().getProfile(userId="me").execute()
        proben.append(("Mail", adresse.get("emailAddress", "?")))
    except Exception as e:
        proben.append(("Mail", f"Fehler: {e}"))
    try:
        t = build("tasks", "v1", credentials=zugang, cache_discovery=False)
        anzahl = len(t.tasklists().list().execute().get("items", []))
        proben.append(("Aufgaben", f"{anzahl} Listen"))
    except Exception as e:
        proben.append(("Aufgaben", f"Fehler: {e}"))
    try:
        p = build("people", "v1", credentials=zugang, cache_discovery=False)
        anzahl = p.people().connections().list(
            resourceName="people/me", personFields="names", pageSize=1
        ).execute().get("totalPeople", 0)
        proben.append(("Kontakte", f"{anzahl} Kontakte"))
    except Exception as e:
        proben.append(("Kontakte", f"Fehler: {e}"))
    try:
        d = build("drive", "v3", credentials=zugang, cache_discovery=False)
        d.files().list(pageSize=1, fields="files(id)").execute()
        proben.append(("Drive", "erreichbar"))
    except Exception as e:
        proben.append(("Drive", f"Fehler: {e}"))
    return proben


# --- Hilfen ---------------------------------------------------------------

def _wann(zeit: dict) -> str:
    """Google-Zeitangabe in einen sprechbaren Text."""
    roh = zeit.get("dateTime") or zeit.get("date") or ""
    if not roh:
        return ""
    try:
        if "T" in roh:
            d = datetime.fromisoformat(roh.replace("Z", "+00:00")).astimezone()
            return f"{d:%d.%m. um %H:%M} Uhr"
        d = datetime.fromisoformat(roh)
        return f"{d:%d.%m.} ganztägig"
    except ValueError:
        return roh


def _kopf(nachricht: dict, feld: str) -> str:
    for k in nachricht.get("payload", {}).get("headers", []):
        if k.get("name", "").lower() == feld.lower():
            return k.get("value", "")
    return ""


def _text_aus(nutzlast: dict) -> str:
    """Den lesbaren Teil einer Mail herausholen."""
    if nutzlast.get("mimeType", "").startswith("text/plain"):
        daten = nutzlast.get("body", {}).get("data")
        if daten:
            return base64.urlsafe_b64decode(daten).decode("utf-8", "replace")
    for teil in nutzlast.get("parts", []) or []:
        gefunden = _text_aus(teil)
        if gefunden:
            return gefunden
    return ""


def _fehlt():
    """Was Sarvis sagt, wenn Google nicht erreichbar ist.

    Der haeufigste Fall ist nicht "nie angemeldet", sondern "Zugang
    abgelaufen": Im Testing-Modus verfallen Googles Zugaenge nach sieben
    Tagen. Deshalb wird unterschieden -- sonst sucht man den Fehler an
    der falschen Stelle.
    """
    if not config.GOOGLE_TOKEN.exists():
        return {"content": [{"type": "text", "text":
                "Google ist nicht angemeldet. Einmalig google_anmelden.bat "
                "ausführen."}], "is_error": True}
    return {"content": [{"type": "text", "text":
            "Der Google-Zugang ist abgelaufen — im Testing-Modus passiert "
            "das alle sieben Tage. Sag dem Nutzer, er soll "
            "google_anmelden.bat ausführen; das dauert zwanzig Sekunden."}],
            "is_error": True}


def zustand() -> str:
    """Kurzer Satz fuer die Konsole beim Start."""
    if not config.GOOGLE_ZUGANG.exists():
        return "keine Zugangsdaten"
    if not config.GOOGLE_TOKEN.exists():
        return "nicht angemeldet — google_anmelden.bat ausführen"
    if _zugangsdaten() is None:
        return "Zugang abgelaufen — google_anmelden.bat ausführen"
    return "angemeldet"


# --- Werkzeuge ------------------------------------------------------------

def werkzeuge(protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    def blinken(punkt: str):
        if leuchten:
            leuchten(punkt)

    # --- Kalender ---------------------------------------------------------

    @tool(
        "termine_ansehen",
        "Zeigt anstehende Termine. Für 'was steht heute an', 'was habe ich "
        "morgen vor', 'wann bin ich nächste Woche frei'.",
        {
            "type": "object",
            "properties": {
                "tage": {"type": "integer", "minimum": 1, "maximum": 60,
                         "description": "Zeitraum ab heute. Vorgabe 1."},
                "ab": {"type": "string",
                       "description": "Optional TT.MM.JJJJ, sonst ab jetzt."},
            },
        },
    )
    async def termine_ansehen(args):
        dienst = await _hole("calendar", "v3")
        if dienst is None:
            return _fehlt()
        tage = int(args.get("tage") or 1)
        von = datetime.now().astimezone()
        if args.get("ab"):
            try:
                t, m, j = (int(x) for x in str(args["ab"]).split("."))
                von = von.replace(year=j, month=m, day=t, hour=0, minute=0)
            except (ValueError, TypeError):
                pass
        bis = von + timedelta(days=tage)

        antwort = await asyncio.to_thread(
            lambda: dienst.events().list(
                calendarId="primary", timeMin=von.isoformat(),
                timeMax=bis.isoformat(), singleEvents=True,
                orderBy="startTime", maxResults=25,
            ).execute()
        )
        blinken("Kalender")
        eintraege = antwort.get("items", [])
        if not eintraege:
            return {"content": [{"type": "text", "text":
                    "In dem Zeitraum steht nichts an."}]}
        zeilen = [
            f"{_wann(e.get('start', {}))}: {e.get('summary', '(ohne Titel)')}"
            + (f" — {e['location']}" if e.get("location") else "")
            for e in eintraege
        ]
        return {"content": [{"type": "text", "text": "\n".join(zeilen)}]}

    @tool(
        "termin_anlegen",
        "Trägt einen Termin in den Kalender ein.",
        {
            "type": "object",
            "properties": {
                "titel": {"type": "string", "description": "Worum es geht."},
                "beginn": {"type": "string",
                           "description": "TT.MM.JJJJ HH:MM"},
                "dauer_minuten": {"type": "integer", "minimum": 5,
                                  "maximum": 1440,
                                  "description": "Vorgabe 60."},
                "ort": {"type": "string", "description": "Optional."},
                "notiz": {"type": "string", "description": "Optional."},
            },
            "required": ["titel", "beginn"],
        },
    )
    async def termin_anlegen(args):
        dienst = await _hole("calendar", "v3")
        if dienst is None:
            return _fehlt()
        try:
            beginn = datetime.strptime(str(args["beginn"]).strip(),
                                       "%d.%m.%Y %H:%M").astimezone()
        except (ValueError, KeyError):
            return {"content": [{"type": "text", "text":
                    "Den Zeitpunkt verstehe ich nicht. Format: "
                    "TT.MM.JJJJ HH:MM."}], "is_error": True}
        ende = beginn + timedelta(minutes=int(args.get("dauer_minuten") or 60))

        koerper = {
            "summary": args["titel"],
            "start": {"dateTime": beginn.isoformat()},
            "end": {"dateTime": ende.isoformat()},
        }
        if args.get("ort"):
            koerper["location"] = args["ort"]
        if args.get("notiz"):
            koerper["description"] = args["notiz"]

        await asyncio.to_thread(
            lambda: dienst.events().insert(calendarId="primary",
                                           body=koerper).execute()
        )
        blinken("Kalender")
        vermerken(f"termin_anlegen: {args['titel']} am "
                  f"{beginn:%d.%m.%Y %H:%M} ist eingetragen.")
        return {"content": [{"type": "text", "text":
                f"Eingetragen: {args['titel']} am {beginn:%d.%m.} um "
                f"{beginn:%H:%M} Uhr."}]}

    @tool(
        "termin_absagen",
        "Löscht einen Termin. Vorher mit termine_ansehen nachsehen, welcher "
        "gemeint ist.",
        {
            "type": "object",
            "properties": {
                "titel": {"type": "string",
                          "description": "Titel des Termins, wie er im "
                                         "Kalender steht."},
                "tage": {"type": "integer", "minimum": 1, "maximum": 60,
                         "description": "In welchem Zeitraum suchen. "
                                        "Vorgabe 14."},
            },
            "required": ["titel"],
        },
    )
    async def termin_absagen(args):
        dienst = await _hole("calendar", "v3")
        if dienst is None:
            return _fehlt()
        von = datetime.now().astimezone()
        bis = von + timedelta(days=int(args.get("tage") or 14))
        antwort = await asyncio.to_thread(
            lambda: dienst.events().list(
                calendarId="primary", timeMin=von.isoformat(),
                timeMax=bis.isoformat(), singleEvents=True,
                orderBy="startTime", maxResults=50, q=args["titel"],
            ).execute()
        )
        treffer = antwort.get("items", [])
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Keinen Termin {args['titel']!r} gefunden."}],
                    "is_error": True}
        if len(treffer) > 1:
            namen = "; ".join(
                f"{_wann(e.get('start', {}))} {e.get('summary', '')}"
                for e in treffer[:4]
            )
            return {"content": [{"type": "text", "text":
                    f"Mehrere passen: {namen}. Frag nach, welcher gemeint "
                    "ist."}], "is_error": True}
        ziel = treffer[0]
        await asyncio.to_thread(
            lambda: dienst.events().delete(calendarId="primary",
                                           eventId=ziel["id"]).execute()
        )
        blinken("Kalender")
        vermerken(f"termin_absagen: {ziel.get('summary')} wurde gelöscht.")
        return {"content": [{"type": "text", "text":
                f"{ziel.get('summary')} ist abgesagt."}]}

    # --- Mail -------------------------------------------------------------

    @tool(
        "mails_ansehen",
        "Zeigt die neuesten Mails mit Absender und Betreff. Für 'ist was "
        "gekommen', 'was liegt im Postfach'. Mit suche kann gezielt gesucht "
        "werden, in Gmail-Schreibweise: 'from:alex', 'is:unread', "
        "'newer_than:2d'.",
        {
            "type": "object",
            "properties": {
                "suche": {"type": "string",
                          "description": "Gmail-Suchausdruck. Leer = Posteingang."},
                "anzahl": {"type": "integer", "minimum": 1, "maximum": 20,
                           "description": "Vorgabe 8."},
            },
        },
    )
    async def mails_ansehen(args):
        dienst = await _hole("gmail", "v1")
        if dienst is None:
            return _fehlt()
        suche = (args.get("suche") or "in:inbox").strip()
        anzahl = int(args.get("anzahl") or 8)

        liste = await asyncio.to_thread(
            lambda: dienst.users().messages().list(
                userId="me", q=suche, maxResults=anzahl).execute()
        )
        kennungen = [m["id"] for m in liste.get("messages", [])]
        if not kennungen:
            return {"content": [{"type": "text", "text":
                    "Dazu liegt nichts im Postfach."}]}

        def hole(kennung):
            return dienst.users().messages().get(
                userId="me", id=kennung, format="metadata",
                metadataHeaders=["From", "Subject", "Date"]).execute()

        zeilen = []
        for kennung in kennungen:
            n = await asyncio.to_thread(hole, kennung)
            ungelesen = "UNREAD" in (n.get("labelIds") or [])
            absender = re.sub(r"\s*<[^>]+>", "", _kopf(n, "From")).strip('" ')
            zeilen.append(
                f"{'[neu] ' if ungelesen else ''}{absender}: "
                f"{_kopf(n, 'Subject') or '(kein Betreff)'}"
            )
        blinken("E-Mail")
        return {"content": [{"type": "text", "text": "\n".join(zeilen)}]}

    @tool(
        "mail_lesen",
        "Liest eine Mail im Volltext vor. Gesucht wird wie bei "
        "mails_ansehen; die neueste passende wird genommen.",
        {
            "type": "object",
            "properties": {
                "suche": {"type": "string",
                          "description": "z. B. 'from:alex' oder ein Betreff."},
            },
            "required": ["suche"],
        },
    )
    async def mail_lesen(args):
        dienst = await _hole("gmail", "v1")
        if dienst is None:
            return _fehlt()
        liste = await asyncio.to_thread(
            lambda: dienst.users().messages().list(
                userId="me", q=args["suche"], maxResults=1).execute()
        )
        treffer = liste.get("messages", [])
        if not treffer:
            return {"content": [{"type": "text", "text":
                    "Dazu finde ich keine Mail."}]}
        n = await asyncio.to_thread(
            lambda: dienst.users().messages().get(
                userId="me", id=treffer[0]["id"], format="full").execute()
        )
        blinken("E-Mail")
        text = _text_aus(n.get("payload", {}))[:4000]
        return {"content": [{"type": "text", "text":
                f"Von {_kopf(n, 'From')}\nBetreff: {_kopf(n, 'Subject')}\n\n"
                + (text or "(kein lesbarer Text)")}]}

    @tool(
        "mail_senden",
        "Verschickt eine Mail. Der Text muss fertig formuliert sein — er "
        "geht genau so hinaus.",
        {
            "type": "object",
            "properties": {
                "an": {"type": "string",
                       "description": "Empfängeradresse. Bei einem Namen "
                                      "vorher kontakt_suchen benutzen."},
                "betreff": {"type": "string"},
                "text": {"type": "string"},
            },
            "required": ["an", "betreff", "text"],
        },
    )
    async def mail_senden(args):
        dienst = await _hole("gmail", "v1")
        if dienst is None:
            return _fehlt()
        an = (args.get("an") or "").strip()
        if "@" not in an:
            return {"content": [{"type": "text", "text":
                    f"{an!r} ist keine Mailadresse. Erst kontakt_suchen."}],
                    "is_error": True}
        nachricht = EmailMessage()
        nachricht["To"] = an
        nachricht["Subject"] = args.get("betreff") or "(ohne Betreff)"
        nachricht.set_content(args.get("text") or "")
        roh = base64.urlsafe_b64encode(nachricht.as_bytes()).decode()

        await asyncio.to_thread(
            lambda: dienst.users().messages().send(
                userId="me", body={"raw": roh}).execute()
        )
        blinken("E-Mail")
        vermerken(f"mail_senden: Mail an {an} ist raus, Betreff "
                  f"{args.get('betreff')!r}.")
        return {"content": [{"type": "text", "text": f"Gesendet an {an}."}]}

    @tool(
        "mail_verschieben",
        "Verschiebt Mails in den Papierkorb, ins Archiv oder auf gelesen. "
        "Aus dem Papierkorb holt Gmail sie dreißig Tage lang zurück.",
        {
            "type": "object",
            "properties": {
                "suche": {"type": "string",
                          "description": "Welche Mails, in Gmail-Schreibweise."},
                "wohin": {
                    "type": "string",
                    "enum": ["papierkorb", "archiv", "gelesen", "ungelesen"],
                },
                "anzahl": {"type": "integer", "minimum": 1, "maximum": 25,
                           "description": "Höchstens so viele. Vorgabe 1."},
            },
            "required": ["suche", "wohin"],
        },
    )
    async def mail_verschieben(args):
        dienst = await _hole("gmail", "v1")
        if dienst is None:
            return _fehlt()
        anzahl = int(args.get("anzahl") or 1)
        liste = await asyncio.to_thread(
            lambda: dienst.users().messages().list(
                userId="me", q=args["suche"], maxResults=anzahl).execute()
        )
        kennungen = [m["id"] for m in liste.get("messages", [])]
        if not kennungen:
            return {"content": [{"type": "text", "text":
                    "Dazu finde ich nichts."}]}

        wohin = args["wohin"]
        for kennung in kennungen:
            if wohin == "papierkorb":
                await asyncio.to_thread(
                    lambda k=kennung: dienst.users().messages().trash(
                        userId="me", id=k).execute())
            else:
                aenderung = {
                    "archiv": {"removeLabelIds": ["INBOX"]},
                    "gelesen": {"removeLabelIds": ["UNREAD"]},
                    "ungelesen": {"addLabelIds": ["UNREAD"]},
                }[wohin]
                await asyncio.to_thread(
                    lambda k=kennung, a=aenderung:
                    dienst.users().messages().modify(
                        userId="me", id=k, body=a).execute())
        blinken("E-Mail")
        vermerken(f"mail_verschieben: {len(kennungen)} Mail(s) -> {wohin}")
        return {"content": [{"type": "text", "text":
                f"{len(kennungen)} Mail(s) nach {wohin}."}]}

    # --- Aufgaben ---------------------------------------------------------

    async def _erste_liste(dienst):
        listen = await asyncio.to_thread(
            lambda: dienst.tasklists().list(maxResults=1).execute())
        eintraege = listen.get("items", [])
        return eintraege[0]["id"] if eintraege else None

    @tool(
        "aufgaben_ansehen",
        "Zeigt die offenen Aufgaben aus Google Tasks.",
        {
            "type": "object",
            "properties": {
                "auch_erledigte": {"type": "boolean",
                                   "description": "Vorgabe: nein."},
            },
        },
    )
    async def aufgaben_ansehen(args):
        dienst = await _hole("tasks", "v1")
        if dienst is None:
            return _fehlt()
        liste = await _erste_liste(dienst)
        if liste is None:
            return {"content": [{"type": "text", "text":
                    "Es gibt keine Aufgabenliste."}]}
        auch = bool(args.get("auch_erledigte"))
        antwort = await asyncio.to_thread(
            lambda: dienst.tasks().list(
                tasklist=liste, showCompleted=auch,
                showHidden=auch, maxResults=50).execute())
        offen = antwort.get("items", [])
        blinken("Aufgaben")
        if not offen:
            return {"content": [{"type": "text", "text":
                    "Keine offenen Aufgaben."}]}
        zeilen = []
        for a in offen:
            haken = "erledigt: " if a.get("status") == "completed" else ""
            faellig = ""
            if a.get("due"):
                try:
                    d = datetime.fromisoformat(a["due"].replace("Z", "+00:00"))
                    faellig = f" (bis {d:%d.%m.})"
                except ValueError:
                    pass
            zeilen.append(f"{haken}{a.get('title', '(ohne Titel)')}{faellig}")
        return {"content": [{"type": "text", "text": "\n".join(zeilen)}]}

    @tool(
        "aufgabe_anlegen",
        "Legt eine Aufgabe in Google Tasks an.",
        {
            "type": "object",
            "properties": {
                "titel": {"type": "string"},
                "faellig": {"type": "string",
                            "description": "Optional TT.MM.JJJJ."},
                "notiz": {"type": "string", "description": "Optional."},
            },
            "required": ["titel"],
        },
    )
    async def aufgabe_anlegen(args):
        dienst = await _hole("tasks", "v1")
        if dienst is None:
            return _fehlt()
        liste = await _erste_liste(dienst)
        if liste is None:
            return {"content": [{"type": "text", "text":
                    "Es gibt keine Aufgabenliste."}], "is_error": True}
        koerper = {"title": args["titel"]}
        if args.get("notiz"):
            koerper["notes"] = args["notiz"]
        if args.get("faellig"):
            try:
                t, m, j = (int(x) for x in str(args["faellig"]).split("."))
                koerper["due"] = f"{j:04d}-{m:02d}-{t:02d}T00:00:00.000Z"
            except (ValueError, TypeError):
                pass
        await asyncio.to_thread(
            lambda: dienst.tasks().insert(tasklist=liste,
                                          body=koerper).execute())
        blinken("Aufgaben")
        return {"content": [{"type": "text", "text":
                f"Aufgabe angelegt: {args['titel']}."}]}

    @tool(
        "aufgabe_abhaken",
        "Hakt eine Aufgabe ab.",
        {
            "type": "object",
            "properties": {
                "titel": {"type": "string",
                          "description": "Teil des Aufgabentitels."},
            },
            "required": ["titel"],
        },
    )
    async def aufgabe_abhaken(args):
        dienst = await _hole("tasks", "v1")
        if dienst is None:
            return _fehlt()
        liste = await _erste_liste(dienst)
        if liste is None:
            return {"content": [{"type": "text", "text":
                    "Es gibt keine Aufgabenliste."}], "is_error": True}
        antwort = await asyncio.to_thread(
            lambda: dienst.tasks().list(tasklist=liste,
                                        maxResults=100).execute())
        suchwort = args["titel"].lower()
        treffer = [a for a in antwort.get("items", [])
                   if suchwort in a.get("title", "").lower()
                   and a.get("status") != "completed"]
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Keine offene Aufgabe zu {args['titel']!r}."}]}
        if len(treffer) > 1:
            return {"content": [{"type": "text", "text":
                    "Mehrere passen: "
                    + "; ".join(a["title"] for a in treffer[:4])
                    + ". Frag nach, welche gemeint ist."}], "is_error": True}
        ziel = treffer[0]
        ziel["status"] = "completed"
        await asyncio.to_thread(
            lambda: dienst.tasks().update(
                tasklist=liste, task=ziel["id"], body=ziel).execute())
        blinken("Aufgaben")
        return {"content": [{"type": "text", "text":
                f"{ziel['title']} ist abgehakt."}]}

    # --- Kontakte ---------------------------------------------------------

    @tool(
        "kontakt_suchen",
        "Sucht in den Google-Kontakten nach einem Namen und gibt Mailadresse "
        "und Telefonnummer zurück. IMMER benutzen, bevor eine Mail an einen "
        "Namen geht — gesprochene Adressen versteht keine Spracherkennung.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Name oder Teil davon."},
            },
            "required": ["name"],
        },
    )
    async def kontakt_suchen(args):
        dienst = await _hole("people", "v1")
        if dienst is None:
            return _fehlt()
        felder = "names,emailAddresses,phoneNumbers"

        # Die People-API will vor der ersten Suche aufgewaermt werden --
        # eine leere Anfrage fuellt ihren Zwischenspeicher. Ohne das kommt
        # beim ersten Mal gern nichts zurueck.
        try:
            await asyncio.to_thread(
                lambda: dienst.people().searchContacts(
                    query="", readMask=felder, pageSize=1).execute())
        except Exception:
            pass

        antwort = await asyncio.to_thread(
            lambda: dienst.people().searchContacts(
                query=args["name"], readMask=felder, pageSize=10).execute())
        treffer = antwort.get("results", [])
        if not treffer:
            # Zusaetzlich unter denen suchen, mit denen nur gemailt wurde.
            # Das braucht "contacts.other.readonly" -- die Berechtigung
            # haben wir NICHT, weil die breiten Varianten sie nicht
            # einschliessen. Fehlt sie, ist das kein Grund zu scheitern:
            # dann gibt es diese Quelle eben nicht. Vorher hat der 403
            # von hier die ganze Kontaktsuche als kaputt gemeldet.
            try:
                antwort = await asyncio.to_thread(
                    lambda: dienst.otherContacts().search(
                        query=args["name"], readMask="names,emailAddresses",
                        pageSize=10).execute())
                treffer = antwort.get("results", [])
            except Exception:
                treffer = []
        blinken("Kontakte")
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Keinen Kontakt {args['name']!r} gefunden."}]}
        zeilen = []
        for t in treffer[:6]:
            p = t.get("person", {})
            name = (p.get("names") or [{}])[0].get("displayName", "?")
            mails = ", ".join(m.get("value", "")
                              for m in (p.get("emailAddresses") or [])[:2])
            nummern = ", ".join(n.get("value", "")
                                for n in (p.get("phoneNumbers") or [])[:2])
            zeilen.append(f"{name}" + (f" — {mails}" if mails else "")
                          + (f" — {nummern}" if nummern else ""))
        return {"content": [{"type": "text", "text": "\n".join(zeilen)}]}

    @tool(
        "kontakt_anlegen",
        "Legt einen neuen Kontakt in Google Kontakte an.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "mail": {"type": "string", "description": "Optional."},
                "telefon": {"type": "string", "description": "Optional."},
            },
            "required": ["name"],
        },
    )
    async def kontakt_anlegen(args):
        dienst = await _hole("people", "v1")
        if dienst is None:
            return _fehlt()
        teile = args["name"].split()
        koerper = {"names": [{"givenName": teile[0],
                              "familyName": " ".join(teile[1:])}]}
        if args.get("mail"):
            koerper["emailAddresses"] = [{"value": args["mail"]}]
        if args.get("telefon"):
            koerper["phoneNumbers"] = [{"value": args["telefon"]}]
        await asyncio.to_thread(
            lambda: dienst.people().createContact(body=koerper).execute())
        blinken("Kontakte")
        vermerken(f"kontakt_anlegen: {args['name']} wurde angelegt.")
        return {"content": [{"type": "text", "text":
                f"{args['name']} ist als Kontakt angelegt."}]}

    return [termine_ansehen, termin_anlegen, termin_absagen,
            mails_ansehen, mail_lesen, mail_senden, mail_verschieben,
            aufgaben_ansehen, aufgabe_anlegen, aufgabe_abhaken,
            kontakt_suchen, kontakt_anlegen]
