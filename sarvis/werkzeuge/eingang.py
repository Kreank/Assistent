"""Dateien, die von aussen hereinkommen -- ablegen und lesbar machen.

Sascha schickt aus der App etwas herueber: einen Plan als PDF, ein
Angebot als Word, eine Preisliste als Excel, eine Datei aus einem
Projekt. Sarvis soll sagen koennen, was drinsteht.

WARUM UEBER HTTP UND NICHT UEBER DEN DRAHT

Der Draht traegt 4 MB je Nachricht (NACHRICHT_MAX), und base64 blaeht um
ein Drittel auf -- eine 3-MB-Datei passt also gerade so, eine 5-MB-Datei
nicht mehr. Sie in Stuecke zu zerlegen hiesse, im Protokoll eine
Zusammensetz-Logik zu fuehren, mitsamt der Frage, was bei einem
abgebrochenen Stueck geschieht. Ein HTTP-POST kann das alles schon.

WAS HIER NICHT PASSIERT

Ausgefuehrt wird nichts. Die Endungsliste (config.DATEI_ENDUNGEN) ist
eine Positivliste ohne .exe, .sh, .bat, .ps1: Was nicht daraufsteht,
kommt nicht herein. Eine Sperrliste waere die falsche Richtung -- man
muesste an jede neue gefaehrliche Endung denken, und das geht einmal
gut.

Der Dateiname wird auf seinen letzten Teil eingekuerzt und gefiltert.
"../../etc/passwd" wird zu "passwd", nicht zu einem Ausbruch.
"""
import re
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import tool

from .. import config

# Wie viel Text hoechstens zurueckkommt, wenn Sarvis eine Datei liest.
# Das Ergebnis geht in seinen Kontext und wird ihm vorgelesen -- eine
# vollstaendige Preisliste mit 8000 Zeilen hilft niemandem. Wer mehr
# will, fragt gezielt nach oder laesst Sarvis die Datei mit seinen
# Dateiwerkzeugen durchsuchen; sie liegt ja auf der Platte.
TEXT_MAX = 20_000

# Wie viele Zeilen einer Tabelle. Dasselbe in Gruen.
ZEILEN_MAX = 300


def _sauberer_dateiname(roh: str) -> str:
    """Aus einem beliebigen Namen einen, den man gefahrlos anlegen kann.

    Drei Dinge auf einmal: kein Pfad (nur der letzte Teil), keine
    Sonderzeichen, nicht leer. Der letzte Punkt bleibt stehen -- an der
    Endung haengt, ob die Datei ueberhaupt herein darf und wie sie
    spaeter gelesen wird.
    """
    name = str(roh or "").replace("\\", "/").split("/")[-1].strip()
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))
    for alt, neu in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        name = name.replace(alt, neu).replace(alt.upper(), neu.upper())
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-.")
    if not name:
        name = "datei"
    stamm, punkt, endung = name.rpartition(".")
    if punkt:
        name = f"{stamm[:60]}.{endung[:12]}"
    return name[:80]


def endung_erlaubt(name: str) -> bool:
    return Path(name.lower()).suffix in config.DATEI_ENDUNGEN


def _ordner() -> Path:
    config.EINGANG.mkdir(parents=True, exist_ok=True)
    return config.EINGANG


def aufraeumen() -> int:
    """Alte Dateien wegnehmen, damit der Eingang nicht still zuwaechst."""
    dateien = sorted(_ordner().glob("*"), key=lambda d: d.stat().st_mtime)
    weg = dateien[:-config.EINGANG_HOECHSTENS] if (
        len(dateien) > config.EINGANG_HOECHSTENS) else []
    for d in weg:
        try:
            d.unlink()
        except OSError:
            pass
    return len(weg)


def ablegen(name: str, daten: bytes, von: str = "") -> Path:
    """Eine hereingekommene Datei sichern. Gibt den Pfad zurueck.

    Der Zeitstempel steht VORN im Namen. Damit sortiert der Ordner sich
    von selbst chronologisch, und zwei gleichnamige Dateien von
    verschiedenen Tagen ueberschreiben einander nicht -- was bei
    "Angebot.pdf" der Normalfall ist, nicht die Ausnahme.
    """
    sauber = _sauberer_dateiname(name)
    ziel = _ordner() / f"{datetime.now():%Y-%m-%d-%H%M}-{sauber}"
    zaehler = 2
    while ziel.exists():
        ziel = _ordner() / (f"{datetime.now():%Y-%m-%d-%H%M}-{zaehler}-"
                            f"{sauber}")
        zaehler += 1
    ziel.write_bytes(daten)
    aufraeumen()
    print(f"  (Datei angekommen: {ziel.name}, {len(daten)/1024:.0f} kB"
          + (f", von {von}" if von else "") + ")")
    return ziel


# --- Aus einer Datei Text machen -----------------------------------------

def _aus_docx(pfad: Path) -> str:
    from docx import Document
    d = Document(str(pfad))
    stuecke = [a.text for a in d.paragraphs if a.text.strip()]
    for t in d.tables:
        for zeile in t.rows:
            felder = [z.text.strip() for z in zeile.cells]
            if any(felder):
                stuecke.append(" | ".join(felder))
    return "\n".join(stuecke)


def _aus_xlsx(pfad: Path) -> str:
    import openpyxl
    # data_only: Was in der Zelle STEHT, nicht die Formel. Wer nach dem
    # Gesamtpreis fragt, will 1.240,50 hoeren und nicht "=SUMME(D2:D18)".
    mappe = openpyxl.load_workbook(str(pfad), data_only=True, read_only=True)
    stuecke = []
    for blatt in mappe.worksheets:
        stuecke.append(f"--- Blatt: {blatt.title} ---")
        for i, zeile in enumerate(blatt.iter_rows(values_only=True)):
            if i >= ZEILEN_MAX:
                stuecke.append(f"... (weitere Zeilen in {blatt.title})")
                break
            felder = ["" if z is None else str(z) for z in zeile]
            if any(f.strip() for f in felder):
                stuecke.append(" | ".join(felder))
    mappe.close()
    return "\n".join(stuecke)


def _aus_pdf(pfad: Path) -> str:
    from pypdf import PdfReader
    leser = PdfReader(str(pfad))
    stuecke = []
    for i, seite in enumerate(leser.pages, 1):
        text = (seite.extract_text() or "").strip()
        if text:
            stuecke.append(f"--- Seite {i} ---\n{text}")
        if sum(len(s) for s in stuecke) > TEXT_MAX:
            stuecke.append(f"... (Rest von {len(leser.pages)} Seiten)")
            break
    if not stuecke:
        # Ein gescanntes Blatt hat keinen Textlayer. Das ist keine
        # Panne, sondern ein Bild -- und das gehoert gesagt, sonst
        # meldet Sarvis "die Datei ist leer" und niemand versteht warum.
        return ("(kein Text in dieser PDF — vermutlich ein Scan oder "
                "eine Bilddatei. Sarvis kann sie mit seinem Lesewerkzeug "
                "ansehen, statt sie auszulesen.)")
    return "\n\n".join(stuecke)


def _aus_text(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8", errors="replace")


_LESER = {
    ".docx": _aus_docx,
    ".xlsx": _aus_xlsx, ".xlsm": _aus_xlsx,
    ".pdf": _aus_pdf,
}

# Formate, die es noch gibt und die keine der drei Bibliotheken oeffnet:
# das alte Word und Excel von vor 2007. Sie umzuwandeln braucht
# LibreOffice im Bild -- rund 400 MB fuer einen Fall, der bei Sascha
# praktisch nicht vorkommt. Statt daran zu scheitern, wird gesagt, was
# zu tun ist.
_ZU_ALT = {
    ".doc": "Word vor 2007", ".xls": "Excel vor 2007",
    ".ppt": "PowerPoint vor 2007",
}


def text_von(pfad: Path) -> str:
    """Der lesbare Inhalt einer Datei -- oder eine ehrliche Auskunft."""
    endung = pfad.suffix.lower()
    if endung in _ZU_ALT:
        return (f"({_ZU_ALT[endung]}-Format, das kann ich nicht öffnen. "
                "Wenn du es einmal als aktuelles Format speicherst "
                f"({'docx' if endung == '.doc' else 'xlsx'}), lese ich es.)")
    leser = _LESER.get(endung, _aus_text)
    try:
        text = leser(pfad)
    except Exception as e:
        return f"(Die Datei ließ sich nicht lesen — {type(e).__name__}: {e})"
    text = text.strip()
    if not text:
        return "(Die Datei enthält keinen lesbaren Text.)"
    if len(text) > TEXT_MAX:
        text = text[:TEXT_MAX] + "\n\n... (gekürzt — die ganze Datei liegt "
        text += f"unter {pfad})"
    return text


# Woerter, die in einem gesprochenen Satz stehen und nichts ueber die
# gesuchte Datei aussagen.
_FUELLWOERTER = {
    "das", "die", "der", "den", "dem", "des", "ein", "eine", "einen",
    "mal", "bitte", "mir", "mir's", "doch", "noch", "von", "vom", "aus",
    "in", "im", "auf", "zu", "zum", "zur", "und", "oder", "was", "wie",
    "steht", "drin", "schau", "lies", "guck", "sieh", "nach", "datei",
    "dokument", "anhang", "letzte", "letzten", "neue", "neueste",
}


def _knapp(text: str) -> str:
    """Nur Buchstaben und Ziffern -- fuer den Vergleich mit Dateinamen.

    "Mueller" im Satz gegen "Angebot-Mueller.docx" im Namen: Der
    Bindestrich darf nicht stoeren.
    """
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def _suchen(gesucht: str, dateien: list) -> list:
    """Welche Dateien passen zu dem, was gesagt wurde?

    Gesprochen kommt nie ein Dateiname an. Es kommt "schau mal ins
    Angebot von Mueller" -- und danach den ganzen Satz im Dateinamen zu
    suchen, findet nie etwas. Gemessen: "angebot" fand die Datei,
    "das Angebot Mueller" fand nichts, obwohl es dieselbe ist.

    Deshalb in drei Stufen, von genau nach grosszuegig:

      1. Der ganze Ausdruck steckt im Namen  -- "angebot" trifft sicher.
      2. Der Ausdruck ohne Trennzeichen      -- "angebot mueller" gegen
                                                "angebot-mueller".
      3. Wortweise, bestes Ergebnis gewinnt  -- Fuellwoerter raus, dann
                                                zaehlen, wie viele der
                                                uebrigen Woerter im
                                                Namen vorkommen.

    Nur wenn Stufe 3 wirklich etwas trifft, kommt etwas zurueck. Ein
    Zufallstreffer ueber ein einzelnes gemeinsames Zeichen waere
    schlimmer als ein ehrliches "finde ich nicht".
    """
    treffer = [d for d in dateien if gesucht in d.name.lower()]
    if treffer:
        return treffer

    knapp = _knapp(gesucht)
    treffer = [d for d in dateien if knapp and knapp in _knapp(d.name)]
    if treffer:
        return treffer

    woerter = [w for w in (_knapp(w) for w in gesucht.split())
               if len(w) >= 3 and w not in _FUELLWOERTER]
    if not woerter:
        return []
    # Beidseitig vergleichen. Der Dateiname ist kurz ("bericht.pdf"),
    # das gesprochene Wort oft laenger und genauer ("Wartungsbericht").
    # Nur in eine Richtung zu suchen findet das nicht -- gemessen: "lies
    # mir den Wartungsbericht vor" fand die bericht.pdf nicht, obwohl
    # jeder Mensch sie gemeint haette.
    bewertet = []
    for d in dateien:
        name = _knapp(d.stem)
        # Der Zeitstempel vorn gehoert nicht zum Namen und wuerde bei
        # einer Suche nach einer Zahl mitzaehlen.
        name = re.sub(r"^\d{8}\d*", "", name)
        teile = [t for t in re.split(r"[^a-z0-9]+", d.stem.lower())
                 if len(t) >= 4 and not t.isdigit()]
        punkte = 0
        for w in woerter:
            if w in name:
                punkte += 2          # das Wort steckt im Dateinamen
            elif any(t in w for t in teile):
                punkte += 1          # der Dateiname steckt im Wort
        if punkte:
            bewertet.append((punkte, d))
    if not bewertet:
        return []
    beste = max(p for p, _ in bewertet)
    return [d for p, d in bewertet if p == beste]


def _beschreiben(pfad: Path) -> str:
    groesse = pfad.stat().st_size
    wann = datetime.fromtimestamp(pfad.stat().st_mtime)
    einheit = (f"{groesse/1024/1024:.1f} MB" if groesse > 1024 * 1024
               else f"{groesse/1024:.0f} kB")
    return f"{pfad.name}  ({einheit}, {wann:%d.%m. %H:%M})"


def neueste(seit: float = 0.0) -> list:
    """Was seit einem Zeitpunkt hereinkam -- fuer die Vorspannzeile."""
    try:
        return sorted((d for d in _ordner().glob("*")
                       if d.stat().st_mtime > seit),
                      key=lambda d: d.stat().st_mtime)
    except OSError:
        return []


def eingang_zeile(seit: float) -> str:
    """Liegt etwas Neues im Eingang? Dann gehoert das in den Vorspann.

    Ohne diese Zeile muesste Sascha jedes Mal ansagen, dass er etwas
    geschickt hat -- und genau das soll er nicht muessen. Er schickt die
    Datei und redet weiter.
    """
    neu = neueste(seit)
    if not neu:
        return ""
    namen = ", ".join(d.name for d in neu[-3:])
    mehr = f" (und {len(neu)-3} weitere)" if len(neu) > 3 else ""
    return (f"[Gerade angekommen: {namen}{mehr}. Liegt im Eingang. Sieh "
            "mit datei_lesen hinein, wenn er danach fragt oder wenn es "
            "zum Gespräch gehört — ungefragt vorlesen sollst du sie "
            "nicht.]")


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def blinken():
        if leuchten:
            leuchten("Dateien")

    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    @tool(
        "eingang_zeigen",
        "Listet die Dateien auf, die Sascha herübergeschickt hat — "
        "neueste zuletzt. Für 'was hab ich dir geschickt', 'welche "
        "Dateien liegen da'.",
        {"type": "object", "properties": {}},
    )
    async def eingang_zeigen(args):
        dateien = sorted(_ordner().glob("*"), key=lambda d: d.stat().st_mtime)
        blinken()
        if not dateien:
            return {"content": [{"type": "text", "text":
                    "Im Eingang liegt nichts."}]}
        zeilen = [_beschreiben(d) for d in dateien[-20:]]
        return {"content": [{"type": "text", "text":
                f"{len(dateien)} Datei(en) im Eingang:\n"
                + "\n".join(zeilen)}]}

    @tool(
        "datei_lesen",
        "Liest eine hereingeschickte Datei und gibt ihren Inhalt zurück — "
        "Text, Code, PDF, Word, Excel. Ohne Namen die zuletzt "
        "angekommene. Der Name muss nicht genau stimmen, ein Stück davon "
        "reicht ('das Angebot', 'die Preisliste').",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Teil des Dateinamens. Weglassen "
                                        "für die zuletzt angekommene."},
            },
        },
    )
    async def datei_lesen(args):
        dateien = sorted(_ordner().glob("*"), key=lambda d: d.stat().st_mtime)
        if not dateien:
            return {"content": [{"type": "text", "text":
                    "Im Eingang liegt nichts."}], "is_error": True}
        gesucht = " ".join(str(args.get("name") or "").lower().split())
        if gesucht:
            passend = _suchen(gesucht, dateien)
            if not passend:
                return {"content": [{"type": "text", "text":
                        f"Zu '{gesucht}' finde ich nichts im Eingang. Da "
                        "liegt: " + ", ".join(d.name for d in dateien[-8:])}],
                        "is_error": True}
            pfad = passend[-1]
        else:
            pfad = dateien[-1]

        blinken()
        text = await __import__("asyncio").to_thread(text_von, pfad)
        vermerken(f"datei_lesen: {pfad.name} ({len(text)} Zeichen)")
        return {"content": [{"type": "text", "text":
                f"--- {pfad.name} ---\n{text}"}]}

    return [eingang_zeigen, datei_lesen]
