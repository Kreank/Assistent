"""Google: Kalender, Mail, Aufgaben, Kontakte, Drive, Tabellen.

Eine Anmeldung, sechs Dienste. Bewusst ueber die klassischen APIs und
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
    """Einen API-Zugang bauen und merken, solange die Tokendatei dieselbe ist.

    Vorher wurde ein einmal gebauter Dienst fuer immer behalten. Nach den
    sieben Testing-Tagen half dann auch google_anmelden.bat nicht: Die
    schreibt eine neue Tokendatei, laeuft aber in einem eigenen Prozess --
    das laufende Sarvis hielt weiter den Dienst mit dem toten Zugang und
    scheiterte bis zum Neustart. Deshalb haengt der Merker jetzt am
    Aenderungsstempel der Tokendatei: neue Anmeldung, neuer Dienst.
    """
    from googleapiclient.discovery import build

    try:
        stempel = config.GOOGLE_TOKEN.stat().st_mtime
    except OSError:
        stempel = None
    gemerkt = _dienste.get(name)
    if gemerkt is not None and stempel is not None and gemerkt[0] == stempel:
        return gemerkt[1]
    zugang = _zugangsdaten()
    if zugang is None:
        _dienste.pop(name, None)
        return None
    # Erneut abfragen: _zugangsdaten() schreibt die Datei beim Auffrischen
    # neu -- mit dem alten Stempel wuerde der naechste Aufruf sinnlos noch
    # einmal bauen.
    try:
        stempel = config.GOOGLE_TOKEN.stat().st_mtime
    except OSError:
        stempel = None
    dienst = build(name, fassung, credentials=zugang, cache_discovery=False)
    _dienste[name] = (stempel, dienst)
    return dienst


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


def _faellig_deuten(roh):
    """Ein Faelligkeitsdatum als (Tag, Monat, Jahr) -- oder None.

    Claude liefert je nach Formulierung mal "03.10.2026", mal ISO. Vorher
    verstand aufgabe_anlegen nur das erste Format, verschluckte alles
    andere stillschweigend und meldete trotzdem "Aufgabe angelegt".
    """
    text = str(roh or "").strip()
    if not text:
        return None
    for muster in ("%d.%m.%Y", "%Y-%m-%d", "%d.%m.%y"):
        try:
            d = datetime.strptime(text, muster)
        except ValueError:
            continue
        return d.day, d.month, d.year
    return None


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


# --- Labels ---------------------------------------------------------------
# Gmail hat keine Ordner, sondern Labels -- und die eingebauten sind
# technisch dieselbe Sorte Ding wie die selbstgemachten. "TRASH" hier zu
# setzen waere ein zweiter, an mail_verschieben vorbeilaufender Weg in den
# Papierkorb. Die Liste greift aber ERST, wenn kein eigenes Label so
# heisst: Ein selbst angelegtes "Archiv" gibt es wirklich, und das muss
# erreichbar bleiben.
SYSTEM_LABELS = {
    "INBOX", "SPAM", "TRASH", "UNREAD", "READ", "STARRED", "IMPORTANT",
    "SENT", "DRAFT", "CHAT",
    "CATEGORY_PERSONAL", "CATEGORY_SOCIAL", "CATEGORY_PROMOTIONS",
    "CATEGORY_UPDATES", "CATEGORY_FORUMS",
    # Wer "Papierkorb" sagt, meint den Papierkorb -- nicht ein neues
    # Label, das nur so heisst.
    "POSTEINGANG", "PAPIERKORB", "ARCHIV", "SPAM_ORDNER", "GESENDET",
    "ENTWUERFE", "MARKIERT", "WICHTIG",
}


async def _labels_holen(dienst) -> list:
    """Alle Labels des Postfachs, roh wie Gmail sie liefert."""
    antwort = await asyncio.to_thread(
        lambda: dienst.users().labels().list(userId="me").execute())
    return antwort.get("labels", [])


def _eigene(labels: list) -> list:
    """Nur die selbst angelegten. Die eingebauten macht mail_verschieben."""
    return [eintrag for eintrag in labels
            if eintrag.get("type") != "system"
            and eintrag.get("id") not in SYSTEM_LABELS]


def _label_finden(labels: list, name: str):
    """Label nach Namen suchen, Gross- und Kleinschreibung egal.

    Gesucht wird zuerst der volle Name ("Arbeit/Rechnungen"), dann der
    letzte Abschnitt allein -- gesprochen sagt niemand den ganzen Pfad.
    Ist der letzte Abschnitt mehrdeutig, wird nichts geraten: Lieber
    einmal nachfragen als in den falschen Unterordner einsortieren.
    """
    gesucht = name.strip().strip("/").casefold()
    if not gesucht:
        return None
    for eintrag in labels:
        if eintrag.get("name", "").casefold() == gesucht:
            return eintrag
    kurz = [eintrag for eintrag in labels
            if eintrag.get("name", "").rsplit("/", 1)[-1].casefold() == gesucht]
    return kurz[0] if len(kurz) == 1 else None


# Wie viele Termine hoechstens geholt werden. Der Deckel bleibt -- mehr
# haelt beim Vorlesen niemand aus; nur muss die Antwort sagen, dass er griff.
TERMINE_GRENZE = 25


# --- Drive und Tabellen ---------------------------------------------------

TABELLE = "application/vnd.google-apps.spreadsheet"
DOKUMENT = "application/vnd.google-apps.document"

# Wieviel aus einer Datei bzw. Tabelle in den Kontext geht. Eine
# vorgelesene Antwort ist ohnehin kuerzer -- aber der ganze Text landet
# erst einmal bei Claude, und ein 200-Seiten-Dokument waere teuer.
LESE_GRENZE = 4000     # Zeichen
ZEILEN_GRENZE = 40     # Tabellenzeilen

ARTEN = {
    TABELLE: "Tabelle",
    DOKUMENT: "Dokument",
    "application/vnd.google-apps.presentation": "Präsentation",
    "application/vnd.google-apps.folder": "Ordner",
    "application/vnd.google-apps.form": "Formular",
    "application/pdf": "PDF",
}


def _art(mime: str) -> str:
    if mime in ARTEN:
        return ARTEN[mime]
    if mime.startswith("image/"):
        return "Bild"
    if mime.startswith("video/"):
        return "Video"
    if mime.startswith("audio/"):
        return "Audio"
    if mime.startswith("text/"):
        return "Textdatei"
    return "Datei"


def _fuer_abfrage(text: str) -> str:
    """Suchwort fuer Drives Abfragesprache entschaerfen.

    Ein Apostroph im Suchwort beendet dort sonst die Zeichenkette -- aus
    "Anna's Liste" wuerde eine kaputte Abfrage statt eines Treffers.
    """
    return str(text or "").replace("\\", "\\\\").replace("'", "\\'")


def _geaendert(roh: str) -> str:
    if not roh:
        return ""
    try:
        d = datetime.fromisoformat(roh.replace("Z", "+00:00")).astimezone()
        return f", zuletzt geändert {d:%d.%m.%Y}"
    except ValueError:
        return ""


async def _datei_finden(dienst, name: str):
    """Eine Datei anhand eines Namensteils suchen.

    Gibt (Datei, None) oder (None, Fehlerantwort) zurueck. Mehrdeutigkeit
    ist bewusst ein Fehler und keine Auswahl nach Gutduenken: Beim Lesen
    waere die falsche Datei nur laestig, beim Teilen nicht mehr.
    """
    frage = (f"name contains '{_fuer_abfrage(name)}' and trashed = false")
    antwort = await asyncio.to_thread(
        lambda: dienst.files().list(
            q=frage, pageSize=10, orderBy="modifiedTime desc",
            fields="files(id,name,mimeType,modifiedTime)").execute())
    treffer = antwort.get("files", [])
    if not treffer:
        return None, {"content": [{"type": "text", "text":
                      f"Keine Datei {name!r} in Drive gefunden."}],
                      "is_error": True}
    genau = [f for f in treffer if f["name"].lower() == str(name).lower()]
    if len(genau) == 1:
        return genau[0], None
    # Drive erlaubt zwei Dateien mit demselben Namen (zweimal hochgeladen,
    # Archivkopie). Vorher gewann bei genau gleichem Namen einfach die
    # zuletzt geaenderte -- beim Teilen konnte so still die falsche Datei
    # fuer jeden mit dem Link lesbar werden. Das Datum unterscheidet die
    # beiden, im Namen tut es nichts.
    if len(genau) > 1:
        namen = "; ".join(f["name"] + _geaendert(f.get("modifiedTime", ""))
                          for f in genau[:4])
        return None, {"content": [{"type": "text", "text":
                      "Mehrere Dateien heißen genau so: " + namen
                      + ". Frag nach, welche gemeint ist."}],
                      "is_error": True}
    if len(treffer) > 1:
        return None, {"content": [{"type": "text", "text":
                      "Mehrere passen: "
                      + "; ".join(f["name"] for f in treffer[:4])
                      + ". Frag nach, welche gemeint ist."}],
                      "is_error": True}
    return treffer[0], None


async def _tabelle_finden(name: str):
    """Tabelle suchen und den Namen ihres ersten Blattes mitliefern.

    Das Blatt braucht man fuer jeden Zugriff ohne ausdruecklichen Bereich:
    Ein Bereich "A1:C20" ohne Blattnamen trifft zwar das erste Blatt, aber
    values().append() haengt dann innerhalb dieses Bereichs an statt unten
    an der Tabelle.
    """
    drive = await _hole("drive", "v3")
    if drive is None:
        return None, _fehlt()
    frage = (f"name contains '{_fuer_abfrage(name)}' "
             f"and mimeType = '{TABELLE}' and trashed = false")
    antwort = await asyncio.to_thread(
        lambda: drive.files().list(
            q=frage, pageSize=10, orderBy="modifiedTime desc",
            fields="files(id,name,modifiedTime)").execute())
    treffer = antwort.get("files", [])
    if not treffer:
        return None, {"content": [{"type": "text", "text":
                      f"Keine Tabelle {name!r} gefunden."}],
                      "is_error": True}
    genau = [f for f in treffer if f["name"].lower() == str(name).lower()]
    # Wie in _datei_finden: Auch zwei gleichnamige Tabellen wurden vorher
    # stillschweigend nach dem juengsten Aenderungsdatum entschieden --
    # geschrieben haette Sarvis dann moeglicherweise in die falsche.
    if len(genau) > 1:
        namen = "; ".join(f["name"] + _geaendert(f.get("modifiedTime", ""))
                          for f in genau[:4])
        return None, {"content": [{"type": "text", "text":
                      "Mehrere Tabellen heißen genau so: " + namen
                      + ". Frag nach, welche gemeint ist."}],
                      "is_error": True}
    if not genau and len(treffer) > 1:
        return None, {"content": [{"type": "text", "text":
                      "Mehrere Tabellen passen: "
                      + "; ".join(f["name"] for f in treffer[:4])
                      + ". Frag nach, welche gemeint ist."}],
                      "is_error": True}
    datei = (genau or treffer)[0]

    blaetter = await _hole("sheets", "v4")
    if blaetter is None:
        return None, _fehlt()
    angaben = await asyncio.to_thread(
        lambda: blaetter.spreadsheets().get(
            spreadsheetId=datei["id"],
            fields="sheets.properties.title").execute())
    blatt = (angaben.get("sheets") or [{}])[0].get(
        "properties", {}).get("title", "Tabellenblatt1")
    return {"id": datei["id"], "name": datei["name"], "blatt": blatt}, None


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
            # Frueher wurde hier nur auf Punkte zerlegt; ein ISO-Datum lief
            # in den ValueError und der Zeitraum fiel stumm auf jetzt
            # zurueck. _faellig_deuten kennt beide Schreibweisen.
            datum = _faellig_deuten(args["ab"])
            if datum is not None:
                t, m, j = datum
                von = von.replace(year=j, month=m, day=t, hour=0, minute=0)
        bis = von + timedelta(days=tage)
        # Bleibt ein unverstandenes 'ab' doch einmal liegen, faellt das nur
        # auf, wenn die Antwort sagt, welchen Zeitraum sie meint.
        zeitraum = f"{von:%d.%m.} bis {bis:%d.%m.}"

        antwort = await asyncio.to_thread(
            lambda: dienst.events().list(
                calendarId="primary", timeMin=von.isoformat(),
                timeMax=bis.isoformat(), singleEvents=True,
                orderBy="startTime", maxResults=TERMINE_GRENZE,
            ).execute()
        )
        blinken("Kalender")
        eintraege = antwort.get("items", [])
        if not eintraege:
            return {"content": [{"type": "text", "text":
                    f"Vom {zeitraum} steht nichts an."}]}
        zeilen = [
            f"{_wann(e.get('start', {}))}: {e.get('summary', '(ohne Titel)')}"
            + (f" — {e['location']}" if e.get("location") else "")
            for e in eintraege
        ]
        # Dieselbe Markierung wie in tabelle_lesen: Google liefert hoechstens
        # TERMINE_GRENZE Eintraege, und bei vollem Kalender klang der letzte
        # genannte Termin wie der letzte des Zeitraums.
        if len(eintraege) >= TERMINE_GRENZE:
            zeilen.append(f"[… mehr als {TERMINE_GRENZE} Termine — weitere "
                          "nicht aufgezählt]")
        return {"content": [{"type": "text", "text":
                f"Termine {zeitraum}:\n" + "\n".join(zeilen)}]}

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
        # Vorher wurde hier hart auf 4000 Zeichen geschnitten, ohne ein
        # Zeichen davon zu setzen: Ein langer Verlauf kam mitten im Satz
        # abgeschnitten bei Claude an und wurde als vollstaendige Mail
        # vorgelesen. Dieselbe Markierung wie in drive_lesen.
        text = _text_aus(n.get("payload", {}))
        gekuerzt = ""
        if len(text) > LESE_GRENZE:
            text, gekuerzt = text[:LESE_GRENZE], "\n[… gekürzt]"
        return {"content": [{"type": "text", "text":
                f"Von {_kopf(n, 'From')}\nBetreff: {_kopf(n, 'Subject')}\n\n"
                + (text or "(kein lesbarer Text)") + gekuerzt}]}

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
        "Aus dem Papierkorb holt Gmail sie dreißig Tage lang zurück. "
        "Nur diese vier Wege. Zum Sortieren nach Thema gibt es "
        "Labels — dafür mail_einsortieren.",
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

    @tool(
        "labels_ansehen",
        "Zeigt die Labels des Postfachs — das sind Gmails Ordner. Vor dem "
        "Einsortieren nachsehen, sonst entsteht ein zweites Label mit fast "
        "gleichem Namen.",
        {"type": "object", "properties": {}},
    )
    async def labels_ansehen(args):
        dienst = await _hole("gmail", "v1")
        if dienst is None:
            return _fehlt()
        eigene = _eigene(await _labels_holen(dienst))
        blinken("E-Mail")
        if not eigene:
            return {"content": [{"type": "text", "text":
                    "Eigene Labels gibt es noch keine. Posteingang, Archiv "
                    "und Papierkorb gibt es immer."}]}
        namen = sorted(eintrag["name"] for eintrag in eigene)
        return {"content": [{"type": "text", "text":
                f"{len(namen)} Label(s): " + ", ".join(namen)}]}

    @tool(
        "mail_einsortieren",
        "Hängt ein Label an Mails oder nimmt es wieder ab — so sortiert "
        "Gmail. Für 'sortier die Werbung weg', 'pack das zu den "
        "Rechnungen'. Ein Label ändert nichts am Inhalt und ist jederzeit "
        "wieder abnehmbar.",
        {
            "type": "object",
            "properties": {
                "suche": {"type": "string",
                          "description": "Welche Mails, in Gmail-Schreibweise."},
                "label": {"type": "string",
                          "description": "Name des Labels. Unterlabel mit "
                                         "Schrägstrich: 'Arbeit/Rechnungen'."},
                "abnehmen": {"type": "boolean",
                             "description": "Label abnehmen statt anhängen. "
                                            "Vorgabe: anhängen."},
                "aus_posteingang": {
                    "type": "boolean",
                    "description": "Zusätzlich aus dem Posteingang nehmen. "
                                   "Das ist gemeint, wenn jemand "
                                   "'wegsortieren' sagt. Vorgabe: nein."},
                "anlegen": {"type": "boolean",
                            "description": "Ein Label, das es noch nicht "
                                           "gibt, neu anlegen. Vorgabe: nein."},
                "anzahl": {"type": "integer", "minimum": 1, "maximum": 25,
                           "description": "Höchstens so viele. Vorgabe 1."},
            },
            "required": ["suche", "label"],
        },
    )
    async def mail_einsortieren(args):
        dienst = await _hole("gmail", "v1")
        if dienst is None:
            return _fehlt()

        name = (args.get("label") or "").strip().strip("/")
        if not name:
            return {"content": [{"type": "text", "text":
                    "Ohne Labelnamen geht das nicht."}], "is_error": True}
        # Erst die Mails, dann das Label: Sonst entsteht bei einer Suche, die
        # nichts trifft, ein leeres Label -- und das steht dann fuer immer in
        # der Seitenleiste.
        anzahl = int(args.get("anzahl") or 1)
        liste = await asyncio.to_thread(
            lambda: dienst.users().messages().list(
                userId="me", q=args["suche"], maxResults=anzahl).execute()
        )
        kennungen = [m["id"] for m in liste.get("messages", [])]
        if not kennungen:
            return {"content": [{"type": "text", "text":
                    "Dazu finde ich nichts."}]}

        labels = await _labels_holen(dienst)
        # Gesucht wird nur unter den eigenen Labels -- und die Sperre der
        # eingebauten Namen greift erst danach. Andersherum waere ein selbst
        # angelegtes "Archiv" unerreichbar gewesen, bloss weil Gmail einen
        # Zustand gleichen Namens kennt.
        ziel = _label_finden(_eigene(labels), name)
        angelegt = False
        if ziel is None:
            if name.upper().replace(" ", "_") in SYSTEM_LABELS:
                return {"content": [{"type": "text", "text":
                        f"{name} ist ein Zustand, den Gmail selbst führt, "
                        "und kein eigenes Label. Posteingang, Archiv, "
                        "Papierkorb und gelesen/ungelesen macht "
                        "mail_verschieben."}], "is_error": True}
            if args.get("abnehmen"):
                return {"content": [{"type": "text", "text":
                        f"Ein Label {name!r} gibt es nicht — dann ist da "
                        "auch nichts abzunehmen."}], "is_error": True}
            if not args.get("anlegen"):
                # Kein stilles Anlegen: Ein verhoertes Wort waere sonst ein
                # neues Label, und niemand sieht, wo die Mail geblieben ist.
                vorhanden = sorted(e["name"] for e in _eigene(labels))
                return {"content": [{"type": "text", "text":
                        f"Ein Label {name!r} gibt es noch nicht. Vorhanden: "
                        + (", ".join(vorhanden) or "keins")
                        + ". Soll es wirklich neu angelegt werden, noch "
                          "einmal mit anlegen=true."}], "is_error": True}
            ziel = await asyncio.to_thread(
                lambda: dienst.users().labels().create(
                    userId="me",
                    body={"name": name,
                          "labelListVisibility": "labelShow",
                          "messageListVisibility": "show"}).execute()
            )
            angelegt = True

        abnehmen = bool(args.get("abnehmen"))
        raus = bool(args.get("aus_posteingang"))
        dazu = [] if abnehmen else [ziel["id"]]
        weg = ([ziel["id"]] if abnehmen else []) + (["INBOX"] if raus else [])

        # batchModify: ein Aufruf fuer alle Kennungen statt einer je Mail.
        await asyncio.to_thread(
            lambda: dienst.users().messages().batchModify(
                userId="me",
                body={"ids": kennungen,
                      "addLabelIds": dazu,
                      "removeLabelIds": weg}).execute()
        )
        blinken("E-Mail")
        vermerken(
            f"mail_einsortieren: Label {ziel['name']!r} "
            f"{'abgenommen von' if abnehmen else 'gesetzt an'} "
            f"{len(kennungen)} Mail(s)"
            + (", raus aus dem Posteingang" if raus else "")
            + ("; das Label war neu." if angelegt else ".")
        )
        satz = (f"{len(kennungen)} Mail(s) aus {ziel['name']} genommen."
                if abnehmen else
                f"{len(kennungen)} Mail(s) nach {ziel['name']} einsortiert.")
        if raus:
            satz += " Aus dem Posteingang sind sie raus."
        if angelegt:
            satz = f"Label {ziel['name']} neu angelegt. " + satz
        return {"content": [{"type": "text", "text": satz}]}

    # --- Aufgaben ---------------------------------------------------------

    async def _listen(dienst):
        """Alle Aufgabenlisten des Kontos.

        Frueher wurde nur die erste geholt (maxResults=1). Wer neben
        "Meine Aufgaben" eine zweite Liste fuehrt, bekam auf "was steht
        noch offen" ein "Keine offenen Aufgaben" -- eine Behauptung ueber
        alles, gepruefte war nur eine Liste.
        """
        listen = await asyncio.to_thread(
            lambda: dienst.tasklists().list().execute())
        return listen.get("items", [])

    async def _aufgaben_holen(dienst, kennung, **weitere):
        antwort = await asyncio.to_thread(
            lambda: dienst.tasks().list(tasklist=kennung, **weitere).execute())
        return antwort.get("items", [])

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
        listen = await _listen(dienst)
        if not listen:
            return {"content": [{"type": "text", "text":
                    "Es gibt keine Aufgabenliste."}]}
        auch = bool(args.get("auch_erledigte"))
        zeilen = []
        for eintrag in listen:
            offen = await _aufgaben_holen(
                dienst, eintrag["id"], showCompleted=auch,
                showHidden=auch, maxResults=50)
            if not offen:
                continue
            # Der Listenname nur, wenn es ueberhaupt mehrere gibt -- sonst
            # steht bei jedem "was steht an" ein "Meine Aufgaben:" davor.
            if len(listen) > 1:
                zeilen.append(f"{eintrag.get('title', '(ohne Namen)')}:")
            for a in offen:
                haken = "erledigt: " if a.get("status") == "completed" else ""
                faellig = ""
                if a.get("due"):
                    try:
                        d = datetime.fromisoformat(
                            a["due"].replace("Z", "+00:00"))
                        faellig = f" (bis {d:%d.%m.})"
                    except ValueError:
                        pass
                zeilen.append(
                    f"{haken}{a.get('title', '(ohne Titel)')}{faellig}")
        blinken("Aufgaben")
        if not zeilen:
            return {"content": [{"type": "text", "text":
                    "Keine offenen Aufgaben."}]}
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
        # Beim Anlegen bleibt die erste Liste die Vorgabe: Wohin eine neue
        # Aufgabe soll, sagt der Nutzer nicht -- geraten wird nichts.
        listen = await _listen(dienst)
        if not listen:
            return {"content": [{"type": "text", "text":
                    "Es gibt keine Aufgabenliste."}], "is_error": True}
        liste = listen[0]["id"]
        koerper = {"title": args["titel"]}
        if args.get("notiz"):
            koerper["notes"] = args["notiz"]
        # Ein unverstandenes Datum wurde hier frueher verschluckt (pass) und
        # die Aufgabe fristlos angelegt -- die Antwort sagte trotzdem nur
        # "Aufgabe angelegt". Jetzt bricht es ab wie termin_anlegen, und die
        # uebernommene Frist steht in der Antwort, damit ein Fehler auffaellt.
        frist = ""
        if args.get("faellig"):
            datum = _faellig_deuten(args["faellig"])
            if datum is None:
                return {"content": [{"type": "text", "text":
                        "Das Fälligkeitsdatum verstehe ich nicht. Format: "
                        "TT.MM.JJJJ. Nichts angelegt."}], "is_error": True}
            t, m, j = datum
            koerper["due"] = f"{j:04d}-{m:02d}-{t:02d}T00:00:00.000Z"
            frist = f", fällig {t:02d}.{m:02d}.{j}"
        await asyncio.to_thread(
            lambda: dienst.tasks().insert(tasklist=liste,
                                          body=koerper).execute())
        blinken("Aufgaben")
        vermerken(f"aufgabe_anlegen: Aufgabe {args['titel']!r} wurde "
                  f"angelegt{frist}.")
        return {"content": [{"type": "text", "text":
                f"Aufgabe angelegt: {args['titel']}{frist}."}]}

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
        listen = await _listen(dienst)
        if not listen:
            return {"content": [{"type": "text", "text":
                    "Es gibt keine Aufgabenliste."}], "is_error": True}
        suchwort = args["titel"].lower()
        # Gesucht wird in allen Listen -- sonst hiess es "keine offene
        # Aufgabe dazu", waehrend sie in der zweiten Liste stand.
        treffer = []
        for eintrag in listen:
            treffer += [(eintrag["id"], a) for a
                        in await _aufgaben_holen(dienst, eintrag["id"],
                                                 maxResults=100)
                        if suchwort in a.get("title", "").lower()
                        and a.get("status") != "completed"]
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Keine offene Aufgabe zu {args['titel']!r}."}]}
        if len(treffer) > 1:
            return {"content": [{"type": "text", "text":
                    "Mehrere passen: "
                    + "; ".join(a["title"] for _, a in treffer[:4])
                    + ". Frag nach, welche gemeint ist."}], "is_error": True}
        liste, ziel = treffer[0]
        ziel["status"] = "completed"
        await asyncio.to_thread(
            lambda: dienst.tasks().update(
                tasklist=liste, task=ziel["id"], body=ziel).execute())
        blinken("Aufgaben")
        vermerken(f"aufgabe_abhaken: {ziel['title']} wurde abgehakt.")
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

    # --- Drive ------------------------------------------------------------

    @tool(
        "drive_suchen",
        "Sucht Dateien in Google Drive — nach Namen UND nach Inhalt. Für "
        "'find mal die Rechnung von der Werkstatt' oder 'was habe ich zum "
        "Thema Umzug liegen'. Gibt Name, Art und Änderungsdatum zurück.",
        {
            "type": "object",
            "properties": {
                "suche": {"type": "string",
                          "description": "Suchwort. Kommt in Name oder "
                                         "Inhalt vor."},
                "nur_tabellen": {"type": "boolean",
                                 "description": "Nur Google-Tabellen. "
                                                "Vorgabe: nein."},
            },
            "required": ["suche"],
        },
    )
    async def drive_suchen(args):
        dienst = await _hole("drive", "v3")
        if dienst is None:
            return _fehlt()
        such = _fuer_abfrage(args["suche"])
        frage = f"(name contains '{such}' or fullText contains '{such}')"
        if args.get("nur_tabellen"):
            frage += f" and mimeType = '{TABELLE}'"
        frage += " and trashed = false"
        antwort = await asyncio.to_thread(
            lambda: dienst.files().list(
                q=frage, pageSize=10, orderBy="modifiedTime desc",
                fields="files(id,name,mimeType,modifiedTime)").execute())
        treffer = antwort.get("files", [])
        blinken("Drive")
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Nichts zu {args['suche']!r} in Drive gefunden."}]}
        zeilen = [f"{f['name']} — {_art(f.get('mimeType', ''))}"
                  f"{_geaendert(f.get('modifiedTime'))}" for f in treffer]
        return {"content": [{"type": "text", "text": "\n".join(zeilen)}]}

    @tool(
        "drive_lesen",
        "Liest den Inhalt einer Datei aus Google Drive vor. Funktioniert bei "
        "Google Docs und bei Textdateien. Vorher drive_suchen benutzen, wenn "
        "der genaue Name unklar ist.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Name der Datei oder ein Teil davon."},
            },
            "required": ["name"],
        },
    )
    async def drive_lesen(args):
        dienst = await _hole("drive", "v3")
        if dienst is None:
            return _fehlt()
        datei, fehler = await _datei_finden(dienst, args["name"])
        if fehler:
            return fehler
        art = datei.get("mimeType", "")
        blinken("Drive")

        if art == TABELLE:
            return {"content": [{"type": "text", "text":
                    f"{datei['name']} ist eine Tabelle — dafür ist "
                    "tabelle_lesen da."}], "is_error": True}
        try:
            if art == DOKUMENT:
                roh = await asyncio.to_thread(
                    lambda: dienst.files().export_media(
                        fileId=datei["id"], mimeType="text/plain").execute())
            elif art.startswith("text/") or art == "application/json":
                roh = await asyncio.to_thread(
                    lambda: dienst.files().get_media(
                        fileId=datei["id"]).execute())
            else:
                return {"content": [{"type": "text", "text":
                        f"{datei['name']} ist {_art(art)} — daraus kann ich "
                        "keinen Text holen."}], "is_error": True}
        except Exception as e:
            return {"content": [{"type": "text", "text":
                    f"Konnte {datei['name']} nicht lesen: {e}"}],
                    "is_error": True}

        text = (roh.decode("utf-8", "replace")
                if isinstance(roh, bytes) else str(roh)).strip()
        if not text:
            return {"content": [{"type": "text", "text":
                    f"{datei['name']} ist leer."}]}
        gekuerzt = ""
        if len(text) > LESE_GRENZE:
            text, gekuerzt = text[:LESE_GRENZE], "\n[… gekürzt]"
        return {"content": [{"type": "text", "text":
                f"{datei['name']}:\n{text}{gekuerzt}"}]}

    @tool(
        "drive_teilen",
        "Erzeugt einen Freigabelink für eine Datei in Drive. ACHTUNG: Danach "
        "kann JEDER mit dem Link die Datei ansehen. Nur auf ausdrücklichen "
        "Wunsch.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Name der Datei oder ein Teil davon."},
            },
            "required": ["name"],
        },
    )
    async def drive_teilen(args):
        dienst = await _hole("drive", "v3")
        if dienst is None:
            return _fehlt()
        datei, fehler = await _datei_finden(dienst, args["name"])
        if fehler:
            return fehler
        await asyncio.to_thread(
            lambda: dienst.permissions().create(
                fileId=datei["id"],
                body={"role": "reader", "type": "anyone"}).execute())
        angaben = await asyncio.to_thread(
            lambda: dienst.files().get(fileId=datei["id"],
                                       fields="webViewLink").execute())
        blinken("Drive")
        vermerken(f"drive_teilen: {datei['name']} ist jetzt per Link für "
                  "jeden lesbar.")
        return {"content": [{"type": "text", "text":
                f"{datei['name']} ist freigegeben: "
                f"{angaben.get('webViewLink', '(kein Link)')}"}]}

    # --- Tabellen ---------------------------------------------------------

    @tool(
        "tabelle_lesen",
        "Liest eine Google-Tabelle vor. Für 'was steht im Tankbuch' oder "
        "'lies mir die Einkaufsliste vor'.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Name der Tabelle oder Teil davon."},
                "bereich": {"type": "string",
                            "description": "Optional in A1-Schreibweise, z. B. "
                                           "'A1:C20'. Ohne Angabe das ganze "
                                           "erste Blatt."},
            },
            "required": ["name"],
        },
    )
    async def tabelle_lesen(args):
        blatt, fehler = await _tabelle_finden(args["name"])
        if fehler:
            return fehler
        dienst = await _hole("sheets", "v4")
        if dienst is None:
            return _fehlt()
        bereich = args.get("bereich") or blatt["blatt"]
        antwort = await asyncio.to_thread(
            lambda: dienst.spreadsheets().values().get(
                spreadsheetId=blatt["id"], range=bereich).execute())
        zeilen = antwort.get("values", [])
        blinken("Tabellen")
        if not zeilen:
            return {"content": [{"type": "text", "text":
                    f"{blatt['name']} ist leer."}]}
        gekuerzt = ""
        if len(zeilen) > ZEILEN_GRENZE:
            gekuerzt = f"\n[… {len(zeilen) - ZEILEN_GRENZE} weitere Zeilen]"
            zeilen = zeilen[:ZEILEN_GRENZE]
        text = "\n".join(" | ".join(str(z) for z in zeile) for zeile in zeilen)
        return {"content": [{"type": "text", "text":
                f"{blatt['name']}:\n{text}{gekuerzt}"}]}

    @tool(
        "tabelle_anhaengen",
        "Hängt eine Zeile unten an eine Google-Tabelle an. Für 'trag im "
        "Tankbuch 52 Liter für 89 Euro ein'. Überschreibt nie etwas.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Name der Tabelle oder Teil davon."},
                "werte": {"type": "array", "items": {"type": "string"},
                          "description": "Die Zellen der neuen Zeile, von "
                                         "links nach rechts."},
            },
            "required": ["name", "werte"],
        },
    )
    async def tabelle_anhaengen(args):
        blatt, fehler = await _tabelle_finden(args["name"])
        if fehler:
            return fehler
        dienst = await _hole("sheets", "v4")
        if dienst is None:
            return _fehlt()
        werte = [str(w) for w in (args.get("werte") or [])]
        if not werte:
            return {"content": [{"type": "text", "text":
                    "Ohne Werte kann ich nichts eintragen."}],
                    "is_error": True}
        await asyncio.to_thread(
            lambda: dienst.spreadsheets().values().append(
                spreadsheetId=blatt["id"], range=blatt["blatt"],
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": [werte]}).execute())
        blinken("Tabellen")
        vermerken(f"tabelle_anhaengen: In {blatt['name']} wurde eine Zeile "
                  f"angehängt ({', '.join(werte[:4])}).")
        return {"content": [{"type": "text", "text":
                f"Eingetragen in {blatt['name']}."}]}

    @tool(
        "tabelle_schreiben",
        "Schreibt Werte in einen bestimmten Bereich einer Google-Tabelle und "
        "ÜBERSCHREIBT, was dort steht. Zum Anfügen ist tabelle_anhaengen "
        "richtig, nicht dieses Werkzeug.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Name der Tabelle oder Teil davon."},
                "bereich": {"type": "string",
                            "description": "A1-Schreibweise, z. B. 'B4' oder "
                                           "'A1:C1' — genau eine Zeile. "
                                           "Mehrzeilige Bereiche kann dieses "
                                           "Werkzeug nicht füllen."},
                "werte": {"type": "array", "items": {"type": "string"},
                          "description": "Die Werte, von links nach rechts."},
            },
            "required": ["name", "bereich", "werte"],
        },
    )
    async def tabelle_schreiben(args):
        blatt, fehler = await _tabelle_finden(args["name"])
        if fehler:
            return fehler
        dienst = await _hole("sheets", "v4")
        if dienst is None:
            return _fehlt()
        werte = [str(w) for w in (args.get("werte") or [])]
        # Ohne diese Pruefung ging {"values": [[]]} hinaus und die Antwort
        # meldete trotzdem "ist gesetzt" -- wie in tabelle_anhaengen.
        if not werte:
            return {"content": [{"type": "text", "text":
                    "Ohne Werte kann ich nichts eintragen."}],
                    "is_error": True}
        await asyncio.to_thread(
            lambda: dienst.spreadsheets().values().update(
                spreadsheetId=blatt["id"], range=args["bereich"],
                valueInputOption="USER_ENTERED",
                body={"values": [werte]}).execute())
        blinken("Tabellen")
        vermerken(f"tabelle_schreiben: In {blatt['name']} wurde "
                  f"{args['bereich']} überschrieben.")
        return {"content": [{"type": "text", "text":
                f"{args['bereich']} in {blatt['name']} ist gesetzt."}]}

    @tool(
        "tabelle_anlegen",
        "Legt eine neue Google-Tabelle an, wahlweise mit Überschriftenzeile.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Name der Tabelle."},
                "spalten": {"type": "array", "items": {"type": "string"},
                            "description": "Optionale Überschriften."},
            },
            "required": ["name"],
        },
    )
    async def tabelle_anlegen(args):
        dienst = await _hole("sheets", "v4")
        if dienst is None:
            return _fehlt()
        neu = await asyncio.to_thread(
            lambda: dienst.spreadsheets().create(
                body={"properties": {"title": args["name"]}},
                fields="spreadsheetId,spreadsheetUrl").execute())
        spalten = [str(s) for s in (args.get("spalten") or [])]
        if spalten:
            await asyncio.to_thread(
                lambda: dienst.spreadsheets().values().update(
                    spreadsheetId=neu["spreadsheetId"], range="A1",
                    valueInputOption="USER_ENTERED",
                    body={"values": [spalten]}).execute())
        blinken("Tabellen")
        vermerken(f"tabelle_anlegen: Die Tabelle {args['name']} wurde "
                  "angelegt.")
        return {"content": [{"type": "text", "text":
                f"Tabelle {args['name']} ist angelegt."}]}

    return [termine_ansehen, termin_anlegen, termin_absagen,
            mails_ansehen, mail_lesen, mail_senden, mail_verschieben,
            labels_ansehen, mail_einsortieren,
            aufgaben_ansehen, aufgabe_anlegen, aufgabe_abhaken,
            kontakt_suchen, kontakt_anlegen,
            drive_suchen, drive_lesen, drive_teilen,
            tabelle_lesen, tabelle_anhaengen, tabelle_schreiben,
            tabelle_anlegen]
