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
import mimetypes
import re
from datetime import date, datetime, time as dtime, timedelta
from email.message import EmailMessage

from claude_agent_sdk import tool

from .. import config
from . import eingang

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
    sieben Testing-Tagen half dann auch eine neue Anmeldung nicht: Die
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


async def eigene_adresse() -> str | None:
    """Die Mailadresse des angemeldeten Kontos, oder nichts.

    Damit niemand eine Adresse ins Programm schreiben muss: Wer
    angemeldet ist, ist auch der, den eine Warnung angeht.
    """
    dienst = await _hole("gmail", "v1")
    if dienst is None:
        return None
    try:
        gefragt = await asyncio.to_thread(
            lambda: dienst.users().getProfile(userId="me").execute())
    except Exception:
        return None
    return (gefragt or {}).get("emailAddress")


async def mail_hinaus(an: str, betreff: str, text: str) -> bool:
    """Eine Mail verschicken, ohne den Umweg ueber das Werkzeug.

    WOFUER

    mail_senden() ist ein Werkzeug: Es haengt an den Closures
    `vermerken` und `blinken` aus werkzeuge() und ist damit nur aus
    einem Gespraech heraus aufrufbar. Die Anmeldewache laeuft aber
    NEBEN dem Gespraech und muss gerade dann noch melden koennen, wenn
    der Kopf nicht mehr denkt -- das ist ja der ganze Anlass.

    Gibt zurueck, ob es geklappt hat, und wirft nichts: Eine Wache, die
    am Melden scheitert und dabei ihre eigene Schleife abraeumt, waere
    schlimmer als keine.
    """
    dienst = await _hole("gmail", "v1")
    if dienst is None or "@" not in (an or ""):
        return False
    nachricht = EmailMessage()
    nachricht["To"] = an
    nachricht["Subject"] = betreff
    nachricht.set_content(text)
    roh = base64.urlsafe_b64encode(nachricht.as_bytes()).decode()
    try:
        await asyncio.to_thread(
            lambda: dienst.users().messages().send(
                userId="me", body={"raw": roh}).execute())
    except Exception:
        return False
    return True


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


# --- Anhaenge -------------------------------------------------------------
# Bis hierher kannte die Datei nur den Fliesstext einer Mail. Wer eine
# Rechnung als PDF bekam, erfuhr davon gar nichts -- mail_lesen las den
# Begleitsatz vor und schwieg ueber den Anhang.

# Wie viele Anhaenge hoechstens aufgezaehlt werden. Mehr haelt beim
# Vorlesen niemand aus; dass der Rest existiert, sagt die Antwort trotzdem.
ANHAENGE_GRENZE = 10

# Wie gross ein Anhang hoechstens sein darf, den wir herunterladen. Der
# Inhalt geht als base64 durch den Arbeitsspeicher -- ein Video mit 300 MB
# waere ein stiller Speicherberg fuer eine Datei, die niemand vorlesen kann.
ANHANG_MAX_BYTES = 25 * 1024 * 1024

# Wohin heruntergeladene Anhaenge kommen. Ein eigener Ordner, damit man
# an einer Stelle nachsehen (und aufraeumen) kann, was aus fremden Mails
# auf der Platte gelandet ist.
ANHANG_ORDNER = config.WURZEL / "anhaenge"

# Windows haelt diese Namen fuer Geraete und nicht fuer Dateien -- eine
# Datei "CON.txt" laesst sich nicht anlegen, das Schreiben schlaegt mit
# einer nichtssagenden Meldung fehl.
GERAETENAMEN = ({"CON", "PRN", "AUX", "NUL"}
                | {f"COM{i}" for i in range(1, 10)}
                | {f"LPT{i}" for i in range(1, 10)})

# Wie lang der Namensstamm hoechstens werden darf. Windows deckelt den
# ganzen Pfad bei 260 Zeichen, und ein Absender kann den Namen beliebig
# lang machen.
NAME_MAX = 80

# Endungen, die wir auch dann als Text behandeln, wenn der Absender einen
# unbrauchbaren Typ mitgeschickt hat -- "application/octet-stream" steht
# bei Mailprogrammen erschreckend oft an einer schlichten .csv.
TEXT_ENDUNGEN = (".txt", ".md", ".csv", ".json", ".log",
                 ".yaml", ".yml", ".ini", ".xml")


def _dateiname_saeubern(roh: str) -> str:
    """Einen Dateinamen aus fremder Hand in einen harmlosen verwandeln.

    Der Name eines Anhangs stammt von dem, der die Mail geschickt hat. Er
    ist Text, keine Zusage -- und er wird hier mit einem Ordnerpfad
    zusammengesetzt. "..\\..\\Autostart\\start.bat" wuerde dabei aus dem
    Anhangordner herausfuehren, "C:datei" zeigt unter Windows auf das
    Arbeitsverzeichnis von Laufwerk C. Deshalb wird der Name nicht
    repariert, sondern auf das reduziert, was ein Dateiname sein darf:
    letzter Abschnitt, harmlose Zeichen, begrenzte Laenge.
    """
    name = str(roh or "").strip()
    # Beide Trennerarten: Eine Mail von einem Linux-Absender bringt "/",
    # eine von Windows "\" -- und Python nimmt unter Windows beides.
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r'[<>:"|?*]', "_", name)
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    # Punkte und Leerzeichen am Ende schluckt Windows beim Anlegen still.
    # Geprueft haetten wir dann einen anderen Namen als den geschriebenen.
    name = name.strip(" .")
    if not name:
        return "anhang"
    stamm, punkt, endung = name.rpartition(".")
    if not punkt:
        stamm, endung = name, ""
    if stamm.upper() in GERAETENAMEN:
        stamm = "_" + stamm
    stamm = stamm[:NAME_MAX] or "anhang"
    endung = endung[:16]
    return stamm + ("." + endung if endung else "")


def _anhang_ziel(name: str):
    """Freien Pfad im Anhangordner suchen; legt den Ordner an, wenn er fehlt.

    Gibt None zurueck, wenn der Pfad wider Erwarten aus dem Ordner
    herausfuehrt. Das ist der zweite Riegel hinter _dateiname_saeubern --
    zwei Riegel, weil ein Fehler hier eine fremde Datei an einen Ort
    schreibt, den sich der Absender ausgesucht hat.
    """
    ANHANG_ORDNER.mkdir(parents=True, exist_ok=True)
    stamm, punkt, endung = name.rpartition(".")
    if not punkt:
        stamm, endung = name, ""
    ziel = ANHANG_ORDNER / name
    zaehler = 2
    # Zwei Anhaenge gleichen Namens ueberschreiben einander nicht -- sonst
    # waere die Rechnung von gestern nach dem naechsten Abruf weg.
    while ziel.exists():
        ziel = ANHANG_ORDNER / (
            f"{stamm}-{zaehler}" + ("." + endung if endung else ""))
        zaehler += 1
    ordner = ANHANG_ORDNER.resolve()
    if ordner != ziel.resolve().parent:
        return None
    return ziel


def _ist_textdatei(mime: str, name: str) -> bool:
    """Ob sich der Anhang vorlesen laesst."""
    mime = (mime or "").lower()
    if mime.startswith("text/"):
        return True
    if mime in ("application/json", "application/xml", "application/csv"):
        return True
    return name.lower().endswith(TEXT_ENDUNGEN)


def _groesse(zahl) -> str:
    """Bytezahl als sprechbare Groesse."""
    try:
        n = int(zahl or 0)
    except (TypeError, ValueError):
        return "unbekannte Größe"
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.1f}".replace(".", ",") + " MB"
    if n >= 1024:
        return f"{round(n / 1024)} kB"
    return f"{n} Byte"


def _anhaenge_aus(nutzlast: dict) -> list:
    """Alle Anhaenge einer Mail einsammeln.

    Gmail legt Anhaenge irgendwo in den Teilebaum: Bei einer Mail mit Text,
    HTML-Fassung und zwei Dateien liegen sie eine Ebene tiefer als der
    Text. Deshalb wird der ganze Baum durchlaufen, nicht nur die erste
    Ebene -- wie in _text_aus auch.
    """
    gefunden = []

    def gehen(teil: dict):
        name = (teil.get("filename") or "").strip()
        koerper = teil.get("body") or {}
        # Ohne attachmentId gibt es nichts nachzuladen. Eingebettete
        # Bilder, die ihre Daten direkt im Teil tragen, sind Zierrat der
        # HTML-Fassung und kein Anhang, den jemand meint.
        if name and koerper.get("attachmentId"):
            gefunden.append({
                "nummer": len(gefunden) + 1,
                "name": name,
                "mime": teil.get("mimeType") or "",
                "groesse": koerper.get("size", 0),
                "kennung": koerper["attachmentId"],
            })
        for unter in teil.get("parts") or []:
            gehen(unter)

    gehen(nutzlast or {})
    return gefunden


def _anhang_zeile(anhang: dict) -> str:
    """Ein Anhang zum Vorlesen -- mit Nummer, Art und Groesse.

    Die Nummer steht dabei, weil zwei Anhaenge derselben Mail denselben
    Namen tragen duerfen (Google Play verschickt seine Nutzungsbedingungen
    zweimal). Ohne Nummer waere keiner von beiden erreichbar, denn nach
    dem Namen sind sie nicht zu unterscheiden.
    """
    return (f"{anhang['nummer']}. {anhang['name']} — {_art(anhang['mime'])}, "
            f"{_groesse(anhang['groesse'])}")


def _anhaenge_satz(anhaenge: list) -> str:
    """Die Anhangzeile unter einer vorgelesenen Mail."""
    if not anhaenge:
        return ""
    teile = [_anhang_zeile(a) for a in anhaenge[:ANHAENGE_GRENZE]]
    rest = len(anhaenge) - len(teile)
    satz = f"\n\nAnhänge ({len(anhaenge)}): " + "; ".join(teile)
    if rest > 0:
        satz += f"; [… {rest} weitere nicht aufgezählt]"
    return satz + ". Herunterladen mit mail_anhang_holen."


def _anhang_waehlen(anhaenge: list, name, nummer=None):
    """Aus mehreren Anhaengen den gemeinten aussuchen.

    Gibt (Anhang, None) oder (None, Fehlerantwort). Bei mehreren und ohne
    Angabe wird nicht der erste genommen: Welche der drei Dateien gemeint
    ist, weiss nur der Nutzer.
    """
    def unklar(text: str, auswahl: list):
        return None, {"content": [{"type": "text", "text":
                      text + " " + "; ".join(_anhang_zeile(a)
                                             for a in auswahl[:ANHAENGE_GRENZE])
                      + ". Frag nach, welcher gemeint ist — die Nummer "
                        "genügt."}], "is_error": True}

    if nummer is not None:
        try:
            gewaehlt = int(nummer)
        except (TypeError, ValueError):
            gewaehlt = 0
        for a in anhaenge:
            if a["nummer"] == gewaehlt:
                return a, None
        return None, {"content": [{"type": "text", "text":
                      f"Einen Anhang Nummer {nummer} hat die Mail nicht — "
                      f"es sind {len(anhaenge)}."}], "is_error": True}

    gesucht = str(name or "").strip().casefold()
    if not gesucht:
        if len(anhaenge) == 1:
            return anhaenge[0], None
        return unklar("Die Mail hat mehrere Anhänge:", anhaenge)
    for passt in (lambda n: n == gesucht, lambda n: gesucht in n):
        treffer = [a for a in anhaenge if passt(a["name"].casefold())]
        if len(treffer) == 1:
            return treffer[0], None
        if len(treffer) > 1:
            return unklar("Mehrere Anhänge passen:", treffer)
    return None, {"content": [{"type": "text", "text":
                  f"Einen Anhang {name!r} hat die Mail nicht. Vorhanden: "
                  + "; ".join(_anhang_zeile(a)
                              for a in anhaenge[:ANHAENGE_GRENZE]) + "."}],
                  "is_error": True}


# --- Kalender aussuchen ---------------------------------------------------
# calendarId="primary" stand frueher an vier Stellen fest im Code. Wer
# neben dem Hauptkalender einen zweiten fuehrt, kam nicht heran -- und
# bekam keinen Hinweis darauf, sondern eine Antwort ueber den falschen
# Kalender, die wie eine Antwort ueber alle klang.

async def _kalender_holen(dienst) -> list:
    antwort = await asyncio.to_thread(
        lambda: dienst.calendarList().list(maxResults=100).execute())
    return antwort.get("items", [])


async def _kalender_id(dienst, name):
    """Gesprochenen Kalendernamen auf eine ID aufloesen.

    Gibt (ID, Anzeigename, None) oder (None, "", Fehlerantwort). Ohne
    Angabe bleibt es beim Hauptkalender. Ist der Name mehrdeutig, wird
    nichts geraten -- ein Termin im falschen Kalender ist genauso weg wie
    eine Mail an den falschen Menschen.
    """
    gesucht = str(name or "").strip().casefold()
    if not gesucht:
        return "primary", "", None
    eintraege = await _kalender_holen(dienst)
    for passt in (lambda s: s == gesucht, lambda s: gesucht in s):
        treffer = [e for e in eintraege
                   if passt((e.get("summary") or "").casefold())]
        if len(treffer) == 1:
            return treffer[0]["id"], treffer[0].get("summary", ""), None
        if len(treffer) > 1:
            return None, "", {"content": [{"type": "text", "text":
                              "Mehrere Kalender passen: "
                              + "; ".join(e.get("summary", "?")
                                          for e in treffer[:4])
                              + ". Frag nach, welcher gemeint ist."}],
                              "is_error": True}
    vorhanden = ", ".join(e.get("summary", "?") for e in eintraege[:10])
    return None, "", {"content": [{"type": "text", "text":
                      f"Einen Kalender {name!r} gibt es nicht. Vorhanden: "
                      + (vorhanden or "keiner") + "."}], "is_error": True}


def _im_kalender(anzeige: str) -> str:
    """Zusatz fuer die Antwort, damit klar ist, welcher Kalender gemeint war.

    Beim Hauptkalender bleibt er leer -- sonst stuende bei jedem "was steht
    heute an" ein "im Kalender ..." davor, das niemand hoeren will.
    """
    return f" im Kalender {anzeige}" if anzeige else ""


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
                "Google ist nicht angemeldet. Das wird auf dem Server "
                "nachgeholt — der Weg steht in einsatz/LIESMICH.md."}],
                "is_error": True}
    return {"content": [{"type": "text", "text":
            "Der Google-Zugang ist abgelaufen — im Testing-Modus passiert "
            "das alle sieben Tage. Sag dem Nutzer, dass die Neuanmeldung "
            "auf dem Server nachgeholt werden muss; die Windows-Datei "
            "google_anmelden.bat hilft dabei nicht."}],
            "is_error": True}


def zustand() -> str:
    """Kurzer Satz fuer die Konsole beim Start."""
    if not config.GOOGLE_ZUGANG.exists():
        return "keine Zugangsdaten"
    if not config.GOOGLE_TOKEN.exists():
        return "nicht angemeldet — einsatz/google_anmelden_server.py link"
    if _zugangsdaten() is None:
        return "Zugang abgelaufen — einsatz/google_anmelden_server.py link"
    return "angemeldet"


# --- Werkzeuge ------------------------------------------------------------

# Wie die Liste heisst, auf die ein Merkzettel ohne Angabe geht.
# Bewusst nicht "Einkaufsliste": Auf den Zettel kommt auch, was
# mitzunehmen ist oder wen man anrufen muss -- nicht nur
# Gekauftes.
MERKZETTEL = "Merkzettel"

# Was beim Sprechen dazwischenrutscht und nicht auf den Zettel gehoert.
# Gemessen: "Dichtungen, ähm, Dichtungen und Teflonband" ergab drei
# Eintraege, einer davon "ähm". Nur ALLEINSTEHEND gefiltert -- "also
# Winkel" bleibt, weil da ein Ding dransteht.
_FUELLLAUTE = {"ähm", "ähh", "äh", "ehm", "hm", "hmm", "also", "und",
               "dann", "noch", "ja", "genau", "warte", "moment"}


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
                "kalender": {"type": "string",
                             "description": "Optional der Name eines anderen "
                                            "Kalenders. Ohne Angabe der "
                                            "Hauptkalender. Welche es gibt, "
                                            "sagt kalender_liste."},
            },
        },
    )
    async def termine_ansehen(args):
        dienst = await _hole("calendar", "v3")
        if dienst is None:
            return _fehlt()
        kennung, welcher, fehler = await _kalender_id(dienst,
                                                      args.get("kalender"))
        if fehler:
            return fehler
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
                calendarId=kennung, timeMin=von.isoformat(),
                timeMax=bis.isoformat(), singleEvents=True,
                orderBy="startTime", maxResults=TERMINE_GRENZE,
            ).execute()
        )
        blinken("Kalender")
        eintraege = antwort.get("items", [])
        if not eintraege:
            return {"content": [{"type": "text", "text":
                    f"Vom {zeitraum} steht{_im_kalender(welcher)} nichts "
                    "an."}]}
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
                f"Termine {zeitraum}{_im_kalender(welcher)}:\n"
                + "\n".join(zeilen)}]}

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
                "kalender": {"type": "string",
                             "description": "Optional der Name eines anderen "
                                            "Kalenders. Ohne Angabe der "
                                            "Hauptkalender."},
            },
            "required": ["titel", "beginn"],
        },
    )
    async def termin_anlegen(args):
        dienst = await _hole("calendar", "v3")
        if dienst is None:
            return _fehlt()
        kennung, welcher, fehler = await _kalender_id(dienst,
                                                      args.get("kalender"))
        if fehler:
            return fehler
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
            lambda: dienst.events().insert(calendarId=kennung,
                                           body=koerper).execute()
        )
        blinken("Kalender")
        vermerken(f"termin_anlegen: {args['titel']} am "
                  f"{beginn:%d.%m.%Y %H:%M} ist eingetragen"
                  f"{_im_kalender(welcher)}.")
        return {"content": [{"type": "text", "text":
                f"Eingetragen{_im_kalender(welcher)}: {args['titel']} am "
                f"{beginn:%d.%m.} um {beginn:%H:%M} Uhr."}]}

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
                "kalender": {"type": "string",
                             "description": "Optional der Name eines anderen "
                                            "Kalenders. Ohne Angabe der "
                                            "Hauptkalender."},
            },
            "required": ["titel"],
        },
    )
    async def termin_absagen(args):
        dienst = await _hole("calendar", "v3")
        if dienst is None:
            return _fehlt()
        kennung, welcher, fehler = await _kalender_id(dienst,
                                                      args.get("kalender"))
        if fehler:
            return fehler
        von = datetime.now().astimezone()
        bis = von + timedelta(days=int(args.get("tage") or 14))
        antwort = await asyncio.to_thread(
            lambda: dienst.events().list(
                calendarId=kennung, timeMin=von.isoformat(),
                timeMax=bis.isoformat(), singleEvents=True,
                orderBy="startTime", maxResults=50, q=args["titel"],
            ).execute()
        )
        treffer = antwort.get("items", [])
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Keinen Termin {args['titel']!r}"
                    f"{_im_kalender(welcher)} gefunden."}],
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
            lambda: dienst.events().delete(calendarId=kennung,
                                           eventId=ziel["id"]).execute()
        )
        blinken("Kalender")
        vermerken(f"termin_absagen: {ziel.get('summary')} wurde"
                  f"{_im_kalender(welcher)} gelöscht.")
        return {"content": [{"type": "text", "text":
                f"{ziel.get('summary')} ist abgesagt."}]}

    @tool(
        "termin_verschieben",
        "Verschiebt einen Termin auf eine andere Zeit — und behält dabei "
        "Titel, Ort, Notiz und Eingeladene. Für 'schieb den Müller auf "
        "Donnerstag' oder 'eine Stunde später'. Nicht absagen und neu "
        "anlegen: Das verliert die Einladung und den Verlauf.",
        {
            "type": "object",
            "properties": {
                "titel": {"type": "string",
                          "description": "Titel des Termins, wie er im "
                                         "Kalender steht."},
                "neuer_beginn": {
                    "type": "string",
                    "description": "Neuer Beginn als JJJJ-MM-TT HH:MM. Die "
                                   "Dauer bleibt, wenn nichts anderes "
                                   "gesagt wird.",
                },
                "dauer_minuten": {
                    "type": "integer", "minimum": 5, "maximum": 1440,
                    "description": "Optional: neue Dauer. Ohne Angabe bleibt "
                                   "die bisherige.",
                },
                "tage": {"type": "integer", "minimum": 1, "maximum": 60,
                         "description": "In welchem Zeitraum gesucht wird. "
                                        "Vorgabe 14."},
                "kalender": {"type": "string",
                             "description": "Optional ein anderer Kalender."},
            },
            "required": ["titel", "neuer_beginn"],
        },
    )
    async def termin_verschieben(args):
        dienst = await _hole("calendar", "v3")
        if dienst is None:
            return _fehlt()
        kennung, welcher, fehler = await _kalender_id(dienst,
                                                      args.get("kalender"))
        if fehler:
            return fehler

        neu_roh = " ".join(str(args.get("neuer_beginn") or "").split())
        try:
            neu_beginn = datetime.fromisoformat(neu_roh).astimezone()
        except ValueError:
            return {"content": [{"type": "text", "text":
                    f"Mit {neu_roh!r} kann ich nichts anfangen. Ich brauche "
                    "JJJJ-MM-TT HH:MM."}], "is_error": True}

        von = datetime.now().astimezone()
        bis = von + timedelta(days=int(args.get("tage") or 14))
        antwort = await asyncio.to_thread(
            lambda: dienst.events().list(
                calendarId=kennung, timeMin=von.isoformat(),
                timeMax=bis.isoformat(), singleEvents=True,
                orderBy="startTime", maxResults=50, q=args["titel"],
            ).execute()
        )
        treffer = antwort.get("items", [])
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Keinen Termin {args['titel']!r}"
                    f"{_im_kalender(welcher)} gefunden."}],
                    "is_error": True}
        if len(treffer) > 1:
            namen = "; ".join(
                f"{_wann(e.get('start', {}))} {e.get('summary', '')}"
                for e in treffer[:4])
            return {"content": [{"type": "text", "text":
                    f"Mehrere passen: {namen}. Frag nach, welcher gemeint "
                    "ist."}], "is_error": True}

        ziel = treffer[0]
        # Die bisherige Dauer uebernehmen, wenn keine neue genannt ist.
        # Wer "schieb das auf drei" sagt, meint denselben Termin zu einer
        # anderen Zeit -- nicht einen neuen von unbestimmter Laenge.
        dauer = args.get("dauer_minuten")
        if not dauer:
            try:
                a = datetime.fromisoformat(
                    ziel["start"]["dateTime"].replace("Z", "+00:00"))
                b = datetime.fromisoformat(
                    ziel["end"]["dateTime"].replace("Z", "+00:00"))
                dauer = max(5, int((b - a).total_seconds() // 60))
            except (KeyError, TypeError, ValueError):
                # Ganztaegige Termine haben kein dateTime.
                dauer = 60
        neu_ende = neu_beginn + timedelta(minutes=int(dauer))

        # patch statt update: Es werden NUR Anfang und Ende geaendert.
        # Ein update mit selbstgebautem Koerper wuerde alles ueberschreiben,
        # was nicht mitgeschickt wird -- Eingeladene, Ort, Beschreibung,
        # Erinnerungen. Genau das ist der Grund, warum Absagen und neu
        # Anlegen kein Ersatz ist.
        await asyncio.to_thread(
            lambda: dienst.events().patch(
                calendarId=kennung, eventId=ziel["id"],
                body={"start": {"dateTime": neu_beginn.isoformat()},
                      "end": {"dateTime": neu_ende.isoformat()}},
            ).execute()
        )
        blinken("Kalender")
        wann = neu_beginn.strftime("%d.%m. um %H:%M")
        vermerken(f"termin_verschieben: {ziel.get('summary')} liegt jetzt "
                  f"am {wann}{_im_kalender(welcher)}.")
        return {"content": [{"type": "text", "text":
                f"{ziel.get('summary')} liegt jetzt am {wann} Uhr."}]}

    @tool(
        "freie_zeit",
        "Sagt, wann im Kalender noch Platz ist. Für 'wann hab ich Donnerstag "
        "Luft', 'wo kriege ich zwei Stunden unter', 'wann kann ich den "
        "Kunden einschieben'.",
        {
            "type": "object",
            "properties": {
                "tage": {"type": "integer", "minimum": 1, "maximum": 21,
                         "description": "Wie viele Tage ab heute angesehen "
                                        "werden. Vorgabe 7."},
                "ab_tag": {"type": "string",
                           "description": "Optional JJJJ-MM-TT: erst ab "
                                          "diesem Tag suchen."},
                "dauer_minuten": {
                    "type": "integer", "minimum": 15, "maximum": 600,
                    "description": "Wie lang die Lücke mindestens sein muss. "
                                   "Vorgabe 60.",
                },
                "von_uhr": {"type": "integer", "minimum": 0, "maximum": 23,
                            "description": "Frühester Beginn. Vorgabe 7."},
                "bis_uhr": {"type": "integer", "minimum": 1, "maximum": 24,
                            "description": "Spätestes Ende. Vorgabe 18."},
                "kalender": {"type": "string",
                             "description": "Optional ein anderer Kalender."},
            },
        },
    )
    async def freie_zeit(args):
        dienst = await _hole("calendar", "v3")
        if dienst is None:
            return _fehlt()
        kennung, welcher, fehler = await _kalender_id(dienst,
                                                      args.get("kalender"))
        if fehler:
            return fehler

        mindestens = int(args.get("dauer_minuten") or 60)
        von_uhr = int(args.get("von_uhr") if args.get("von_uhr") is not None
                      else 7)
        bis_uhr = int(args.get("bis_uhr") or 18)
        if bis_uhr <= von_uhr:
            return {"content": [{"type": "text", "text":
                    "Das Zeitfenster ergibt keinen Sinn — das Ende liegt vor "
                    "dem Anfang."}], "is_error": True}

        jetzt = datetime.now().astimezone()
        if args.get("ab_tag"):
            try:
                start_tag = datetime.fromisoformat(
                    str(args["ab_tag"])).astimezone().date()
            except ValueError:
                return {"content": [{"type": "text", "text":
                        "Mit dem Tag kann ich nichts anfangen. JJJJ-MM-TT."}],
                        "is_error": True}
        else:
            start_tag = jetzt.date()
        tage = int(args.get("tage") or 7)

        von = datetime.combine(start_tag, dtime(0, 0)).astimezone()
        bis = von + timedelta(days=tage)
        antwort = await asyncio.to_thread(
            lambda: dienst.events().list(
                calendarId=kennung, timeMin=von.isoformat(),
                timeMax=bis.isoformat(), singleEvents=True,
                orderBy="startTime", maxResults=250,
            ).execute()
        )

        belegt = []
        for e in antwort.get("items", []):
            # Abgesagte zaehlen nicht als belegt -- sonst gilt eine Zeit
            # als voll, die tatsaechlich frei ist.
            if e.get("status") == "cancelled":
                continue
            if e.get("transparency") == "transparent":
                continue          # "frei" markiert, blockiert nicht
            a, b = e.get("start", {}), e.get("end", {})
            if "date" in a:
                # Ganztaegig: blockiert den ganzen Tag.
                try:
                    tag = date.fromisoformat(a["date"])
                    belegt.append((
                        datetime.combine(tag, dtime(0, 0)).astimezone(),
                        datetime.combine(tag, dtime(23, 59)).astimezone()))
                except ValueError:
                    pass
                continue
            try:
                belegt.append((
                    datetime.fromisoformat(a["dateTime"]).astimezone(),
                    datetime.fromisoformat(b["dateTime"]).astimezone()))
            except (KeyError, TypeError, ValueError):
                continue
        belegt.sort()

        luecken = []
        for n in range(tage):
            tag = start_tag + timedelta(days=n)
            beginn = datetime.combine(tag, dtime(von_uhr, 0)).astimezone()
            ende = datetime.combine(tag, dtime(0, 0)).astimezone() \
                + timedelta(hours=bis_uhr)
            # Heute zaehlt erst ab jetzt -- eine Luecke von acht Uhr
            # anzubieten, wenn es zehn ist, waere Unsinn.
            beginn = max(beginn, jetzt)
            zeiger = beginn
            for a, b in belegt:
                if b <= zeiger or a >= ende:
                    continue
                if a > zeiger and (a - zeiger).total_seconds() / 60 >= mindestens:
                    luecken.append((zeiger, min(a, ende)))
                zeiger = max(zeiger, b)
            if zeiger < ende and (ende - zeiger).total_seconds() / 60 >= mindestens:
                luecken.append((zeiger, ende))

        blinken("Kalender")
        if not luecken:
            return {"content": [{"type": "text", "text":
                    f"In den nächsten {tage} Tagen finde ich zwischen "
                    f"{von_uhr} und {bis_uhr} Uhr keine Lücke von "
                    f"{mindestens} Minuten{_im_kalender(welcher)}."}]}
        _TAGE = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
                 "Samstag", "Sonntag")
        zeilen = []
        for a, b in luecken[:12]:
            minuten = int((b - a).total_seconds() // 60)
            lang = (f"{minuten // 60} Std." if minuten >= 120
                    else f"{minuten} Min.")
            zeilen.append(f"{_TAGE[a.weekday()]} {a:%d.%m.}: "
                          f"{a:%H:%M} bis {b:%H:%M} ({lang})")
        mehr = (f"\n… und {len(luecken) - 12} weitere"
                if len(luecken) > 12 else "")
        return {"content": [{"type": "text", "text":
                "\n".join(zeilen) + mehr}]}

    @tool(
        "kalender_liste",
        "Nennt die Kalender des Kontos. Vorher benutzen, wenn ein anderer "
        "als der Hauptkalender gemeint sein könnte — die anderen Werkzeuge "
        "brauchen den Namen so, wie er hier steht.",
        {"type": "object", "properties": {}},
    )
    async def kalender_liste(args):
        dienst = await _hole("calendar", "v3")
        if dienst is None:
            return _fehlt()
        eintraege = await _kalender_holen(dienst)
        blinken("Kalender")
        if not eintraege:
            return {"content": [{"type": "text", "text":
                    "Es gibt keinen Kalender."}]}
        zeilen = []
        for e in eintraege:
            name = e.get("summary", "(ohne Namen)")
            merkmale = []
            if e.get("primary"):
                merkmale.append("Hauptkalender")
            # Fremde Kalender kann man abonniert haben, ohne hineinschreiben
            # zu duerfen. Steht das nicht dabei, sieht es nach einem Fehler
            # von Sarvis aus, wenn termin_anlegen dort scheitert.
            if e.get("accessRole") in ("reader", "freeBusyReader"):
                merkmale.append("nur lesbar")
            zeilen.append(name + (f" ({', '.join(merkmale)})"
                                  if merkmale else ""))
        return {"content": [{"type": "text", "text":
                f"{len(zeilen)} Kalender: " + "; ".join(zeilen)}]}

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
        # Anhaenge kamen vorher gar nicht vor: Eine Mail mit "Rechnung im
        # Anhang" wurde vollstaendig vorgelesen, und dass die Rechnung
        # daran haengt, erfuhr niemand. Genannt wird sie auch dann, wenn
        # wir sie nicht oeffnen koennen -- wissen soll er es trotzdem.
        return {"content": [{"type": "text", "text":
                f"Von {_kopf(n, 'From')}\nBetreff: {_kopf(n, 'Subject')}\n\n"
                + (text or "(kein lesbarer Text)") + gekuerzt
                + _anhaenge_satz(_anhaenge_aus(n.get("payload", {})))}]}

    @tool(
        "mail_anhang_holen",
        "Lädt einen Anhang aus einer Mail herunter und legt ihn im Ordner "
        "'anhaenge' ab; der Antwortsatz nennt den Pfad. Gesucht wird die "
        "Mail wie bei mails_ansehen, die neueste passende wird genommen. "
        "Textdateien (txt, md, csv, json) kann das Werkzeug auf Wunsch "
        "gleich vorlesen.",
        {
            "type": "object",
            "properties": {
                "suche": {"type": "string",
                          "description": "Welche Mail, in Gmail-Schreibweise. "
                                         "'has:attachment' findet nur solche "
                                         "mit Anhang."},
                "datei": {"type": "string",
                          "description": "Name des Anhangs oder ein Teil "
                                         "davon. Nötig, wenn die Mail "
                                         "mehrere hat."},
                "nummer": {"type": "integer", "minimum": 1,
                           "description": "Der wievielte Anhang, gezählt wie "
                                          "in der Anhangzeile von mail_lesen. "
                                          "Sticht den Namen — nötig, wenn "
                                          "zwei Anhänge gleich heißen."},
                "vorlesen": {"type": "boolean",
                             "description": "Inhalt zusätzlich ausgeben. "
                                            "Geht nur bei Textdateien. "
                                            "Vorgabe: nein."},
            },
            "required": ["suche"],
        },
    )
    async def mail_anhang_holen(args):
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
        kennung = treffer[0]["id"]
        n = await asyncio.to_thread(
            lambda: dienst.users().messages().get(
                userId="me", id=kennung, format="full").execute()
        )
        anhaenge = _anhaenge_aus(n.get("payload", {}))
        if not anhaenge:
            return {"content": [{"type": "text", "text":
                    f"Die Mail {_kopf(n, 'Subject') or '(kein Betreff)'!r} "
                    "hat keinen Anhang."}]}
        anhang, fehler = _anhang_waehlen(anhaenge, args.get("datei"),
                                         args.get("nummer"))
        if fehler:
            return fehler

        # Vor dem Laden pruefen, nicht danach: Die Groesse steht schon in
        # der Nachricht, und ein 300-MB-Video will man nicht erst durch den
        # Speicher schieben, um es dann abzulehnen.
        try:
            gemeldet = int(anhang.get("groesse") or 0)
        except (TypeError, ValueError):
            gemeldet = 0
        if gemeldet > ANHANG_MAX_BYTES:
            return {"content": [{"type": "text", "text":
                    f"{anhang['name']} ist {_groesse(gemeldet)} groß — mehr "
                    f"als die Grenze von {_groesse(ANHANG_MAX_BYTES)}. Nicht "
                    "heruntergeladen."}], "is_error": True}

        try:
            roh = await asyncio.to_thread(
                lambda: dienst.users().messages().attachments().get(
                    userId="me", messageId=kennung,
                    id=anhang["kennung"]).execute())
            inhalt = base64.urlsafe_b64decode(roh.get("data") or "")
        except Exception as e:
            return {"content": [{"type": "text", "text":
                    f"Konnte {anhang['name']} nicht laden: {e}"}],
                    "is_error": True}
        if len(inhalt) > ANHANG_MAX_BYTES:
            # Die gemeldete Groesse ist eine Angabe des Absenders wie der
            # Dateiname auch -- also wird sie nach dem Laden nachgeprueft.
            return {"content": [{"type": "text", "text":
                    f"{anhang['name']} ist tatsächlich "
                    f"{_groesse(len(inhalt))} groß und damit zu groß. Nicht "
                    "gespeichert."}], "is_error": True}

        sauber = _dateiname_saeubern(anhang["name"])
        ziel = _anhang_ziel(sauber)
        if ziel is None:
            return {"content": [{"type": "text", "text":
                    f"Der Dateiname {anhang['name']!r} führt aus dem "
                    "Anhangordner heraus. Nicht gespeichert."}],
                    "is_error": True}
        try:
            await asyncio.to_thread(ziel.write_bytes, inhalt)
        except OSError as e:
            return {"content": [{"type": "text", "text":
                    f"Konnte {sauber} nicht speichern: {e}"}],
                    "is_error": True}
        blinken("E-Mail")

        satz = (f"{anhang['name']} ({_groesse(len(inhalt))}) liegt jetzt "
                f"unter {ziel}.")
        # Der Name kann unterwegs ein anderer geworden sein -- entweder weil
        # er entschaerft wurde oder weil schon eine Datei so hiess. Das
        # gehoert in die Antwort, sonst sucht der Nutzer den alten Namen.
        if ziel.name != anhang["name"]:
            satz += f" Gespeichert als {ziel.name}."

        if args.get("vorlesen"):
            if not _ist_textdatei(anhang["mime"], sauber):
                satz += (f" Vorlesen geht nicht: Das ist "
                         f"{_art(anhang['mime'])}, kein Text.")
            else:
                text = inhalt.decode("utf-8", "replace").strip()
                if not text:
                    satz += " Die Datei ist leer."
                else:
                    gekuerzt = ""
                    if len(text) > LESE_GRENZE:
                        text = text[:LESE_GRENZE]
                        gekuerzt = "\n[… gekürzt]"
                    satz += f"\n\n{text}{gekuerzt}"

        vermerken(f"mail_anhang_holen: {ziel.name} aus einer Mail von "
                  f"{_kopf(n, 'From') or '?'} liegt jetzt in {ANHANG_ORDNER}.")
        return {"content": [{"type": "text", "text": satz}]}

    @tool(
        "mail_senden",
        "Verschickt eine Mail, auf Wunsch mit Anhang. Der Text muss fertig "
        "formuliert sein — er geht genau so hinaus. Für 'schick das "
        "Angebot an Julian': erst dokument_erstellen, dann den Dateinamen "
        "als anhang mitgeben.",
        {
            "type": "object",
            "properties": {
                "an": {"type": "string",
                       "description": "Empfängeradresse. Bei einem Namen "
                                      "vorher kontakt_suchen benutzen."},
                "betreff": {"type": "string"},
                "text": {"type": "string"},
                "anhang": {
                    "type": "string",
                    "description": "Eine Datei, die mitgeschickt wird. Der "
                                   "Name reicht und muss nicht genau "
                                   "stimmen — gesucht wird in dem, was du "
                                   "erzeugt hast, und in dem, was Sascha "
                                   "dir geschickt hat.",
                },
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

        anhang = (args.get("anhang") or "").strip()
        pfad = None
        if anhang:
            pfad, fehler = eingang.datei_finden(anhang)
            if pfad is None:
                # Abbrechen statt ohne Anhang senden. Eine Mail, die
                # "im Anhang finden Sie" sagt und nichts anhaengt, ist
                # schlimmer als gar keine -- und niemand merkt es, weil
                # das Senden ja "geklappt" hat.
                return {"content": [{"type": "text", "text":
                        f"{fehler} Ich habe NICHTS gesendet."}],
                        "is_error": True}
            art, _ = mimetypes.guess_type(pfad.name)
            haupt, _, unter = (art or "application/octet-stream").partition("/")
            nachricht.add_attachment(
                await asyncio.to_thread(pfad.read_bytes),
                maintype=haupt, subtype=unter or "octet-stream",
                filename=pfad.name)

        roh = base64.urlsafe_b64encode(nachricht.as_bytes()).decode()

        await asyncio.to_thread(
            lambda: dienst.users().messages().send(
                userId="me", body={"raw": roh}).execute()
        )
        blinken("E-Mail")
        dazu = f" mit {pfad.name}" if pfad else ""
        vermerken(f"mail_senden: Mail an {an} ist raus, Betreff "
                  f"{args.get('betreff')!r}{dazu}.")
        return {"content": [{"type": "text", "text":
                f"Gesendet an {an}{dazu}."}]}

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

    def _liste_waehlen(listen: list, name):
        """Aus den Aufgabenlisten die gemeinte aussuchen.

        Gibt (Liste, None) oder (None, Fehlerantwort). Ohne Angabe bleibt
        es bei der ersten -- das ist "Meine Aufgaben" und war schon immer
        die Vorgabe. Mit Angabe wird nicht geraten: Eine Aufgabe in der
        falschen Liste findet niemand wieder, weil er sie in der richtigen
        sucht.
        """
        gesucht = str(name or "").strip().casefold()
        if not gesucht:
            return listen[0], None
        for passt in (lambda t: t == gesucht, lambda t: gesucht in t):
            treffer = [e for e in listen
                       if passt((e.get("title") or "").casefold())]
            if len(treffer) == 1:
                return treffer[0], None
            if len(treffer) > 1:
                return None, {"content": [{"type": "text", "text":
                              "Mehrere Listen passen: "
                              + "; ".join(e.get("title", "?")
                                          for e in treffer[:4])
                              + ". Frag nach, welche gemeint ist."}],
                              "is_error": True}
        vorhanden = ", ".join(e.get("title", "?") for e in listen[:10])
        return None, {"content": [{"type": "text", "text":
                      f"Eine Aufgabenliste {name!r} gibt es nicht. "
                      f"Vorhanden: {vorhanden}. Nichts angelegt."}],
                      "is_error": True}

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
                "liste": {"type": "string",
                          "description": "Optional der Name einer anderen "
                                         "Aufgabenliste. Ohne Angabe die "
                                         "erste. Welche es gibt, zeigt "
                                         "aufgaben_ansehen."},
            },
            "required": ["titel"],
        },
    )
    async def aufgabe_anlegen(args):
        dienst = await _hole("tasks", "v1")
        if dienst is None:
            return _fehlt()
        # Ohne Angabe bleibt die erste Liste die Vorgabe -- wer nichts sagt,
        # meint "Meine Aufgaben". Wer eine zweite Liste fuehrt, kann sie
        # jetzt aber nennen; vorher landete alles in der ersten, ohne dass
        # die Antwort das verriet.
        listen = await _listen(dienst)
        if not listen:
            return {"content": [{"type": "text", "text":
                    "Es gibt keine Aufgabenliste."}], "is_error": True}
        ziel, fehler = _liste_waehlen(listen, args.get("liste"))
        if fehler:
            return fehler
        liste = ziel["id"]
        # Der Listenname nur, wenn es ueberhaupt mehrere gibt -- sonst
        # steht bei jeder Aufgabe ein "in Meine Aufgaben" dahinter.
        wohin = (f" in {ziel.get('title', '')}" if len(listen) > 1 else "")
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
        vermerken(f"aufgabe_anlegen: Aufgabe {args['titel']!r} wurde"
                  f"{wohin} angelegt{frist}.")
        return {"content": [{"type": "text", "text":
                f"Aufgabe angelegt{wohin}: {args['titel']}{frist}."}]}

    @tool(
        "merkzettel",
        "Setzt mehrere Sachen auf einmal auf eine Liste — den Merkzettel "
        "für den Großhandel, den Einkauf, was mitzunehmen ist. Für "
        "'schreib Dichtungen, Teflonband und zwei Eckventile auf die "
        "Liste'. Ohne Angabe landet alles auf 'Merkzettel'; eine andere "
        "Liste kann genannt werden.",
        {
            "type": "object",
            "properties": {
                "sachen": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1, "maxItems": 30,
                    "description": "Die einzelnen Dinge, jedes für sich. "
                                   "Aus 'Dichtungen, Teflonband und zwei "
                                   "Eckventile' werden drei Einträge.",
                },
                "liste": {"type": "string",
                          "description": "Optional ein anderer Listenname."},
            },
            "required": ["sachen"],
        },
    )
    async def merkzettel(args):
        dienst = await _hole("tasks", "v1")
        if dienst is None:
            return _fehlt()
        roh = args.get("sachen") or []
        sachen = []
        for e in roh:
            e = " ".join(str(e or "").split())
            # Doppeltes weglassen: Gesprochen kommt "Dichtungen, ähm,
            # Dichtungen und Teflonband" durchaus vor, und zwei gleiche
            # Zeilen auf einem Zettel helfen niemandem.
            if not e or e.casefold() in _FUELLLAUTE:
                continue
            if e.casefold() not in {x.casefold() for x in sachen}:
                sachen.append(e)
        if not sachen:
            return {"content": [{"type": "text", "text":
                    "Da war nichts, was ich aufschreiben könnte."}],
                    "is_error": True}

        listen = await _listen(dienst)
        if not listen:
            return {"content": [{"type": "text", "text":
                    "Es gibt keine Aufgabenliste."}], "is_error": True}
        gewuenscht = str(args.get("liste") or "").strip() or MERKZETTEL
        ziel, _fehler = _liste_waehlen(listen, gewuenscht)
        if ziel is None:
            # Die Liste gibt es noch nicht -- dann wird sie angelegt,
            # statt auf "Meine Aufgaben" auszuweichen. Ein Merkzettel,
            # der sich unter die Aufgaben mischt, ist keiner mehr: Im
            # Baumarkt will man eine Liste durchgehen, nicht zwischen
            # Terminen suchen.
            try:
                ziel = await asyncio.to_thread(
                    lambda: dienst.tasklists().insert(
                        body={"title": gewuenscht}).execute())
                print(f"  (Aufgabenliste {gewuenscht!r} angelegt)")
            except Exception as e:
                return {"content": [{"type": "text", "text":
                        f"Die Liste {gewuenscht!r} gibt es nicht und ich "
                        f"konnte sie nicht anlegen: {e}"}], "is_error": True}

        # Rueckwaerts einfuegen: Google Tasks stellt jeden neuen Eintrag
        # nach oben. Ohne das steht die Liste hinterher verkehrt herum,
        # und wer sie vorliest, faengt beim letzten Wort an.
        angelegt = []
        for e in reversed(sachen):
            try:
                await asyncio.to_thread(
                    lambda t=e: dienst.tasks().insert(
                        tasklist=ziel["id"], body={"title": t}).execute())
                angelegt.append(e)
            except Exception as ex:
                return {"content": [{"type": "text", "text":
                        f"{len(angelegt)} von {len(sachen)} sind drauf, "
                        f"dann ging es nicht weiter: {ex}"}],
                        "is_error": True}

        blinken("Aufgaben")
        vermerken(f"merkzettel: {len(angelegt)} Sachen auf "
                  f"{ziel.get('title')}: {', '.join(sachen)}")
        wohin = ziel.get("title", gewuenscht)
        if len(sachen) == 1:
            return {"content": [{"type": "text", "text":
                    f"{sachen[0]} steht auf dem {wohin}."}]}
        return {"content": [{"type": "text", "text":
                f"{len(sachen)} Sachen stehen auf dem {wohin}: "
                + ", ".join(sachen) + "."}]}

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

    return [termine_ansehen, termin_anlegen, termin_absagen, termin_verschieben, freie_zeit, kalender_liste,
            mails_ansehen, mail_lesen, mail_anhang_holen, mail_senden,
            mail_verschieben, labels_ansehen, mail_einsortieren,
            aufgaben_ansehen, aufgabe_anlegen, aufgabe_abhaken, merkzettel,
            kontakt_suchen, kontakt_anlegen,
            drive_suchen, drive_lesen, drive_teilen,
            tabelle_lesen, tabelle_anhaengen, tabelle_schreiben,
            tabelle_anlegen]
