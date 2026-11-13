"""Begleiter eines Blatts -- Typ, Seiten, Vorschaubild, PDF-Fassung.

Wunsch der Android-App vom 13.11.2026 (einsatz/WUNSCH-APP-DOKUMENTE-
2026-11-13.md): Die Dokumentkarte im Chat soll eine Miniatur und
"PDF · 12 Seiten · 1,2 MB" zeigen, OHNE vorher die ganze Datei zu laden,
und Office-Dateien soll man im Betrachter lesen koennen, obwohl Android
docx/xlsx ohne Bibliothek nicht darstellt.

Dafuer bekommt jedes Blatt (html/datei) beim Hinlegen bis zu fuenf Felder:

    mime      der echte Typ, z. B. application/pdf
    bytes     Groesse der ausgelieferten Datei
    seiten    Seitenzahl bei PDF und bei der PDF-Fassung einer Office-Datei
    pdf       /blatt/-Adresse der PDF-Fassung (nur Office)
    vorschau  /blatt/-Adresse eines PNG, hoechstens 480 px breit

WARUM PDF UND VORSCHAU EIGENE BLAETTER SIND

Gleiche Kennungsregel (192 Bit Zufall), gleiche Frist, gleiche Kopfzeilen
-- also derselbe Weg, kein zweiter. Ein Unterblatt traegt "eltern" mit der
Kennung des Dokuments; damit taucht es weder in GET /dateien noch in der
Ablage als eigenes Stueck auf, und blaetter.erneuern() verlaengert es
zusammen mit dem Dokument.

WARUM ALLES OPTIONAL IST

Jedes Feld, das nicht ging, fehlt einfach. Die App zeigt dann das
Typ-Symbol -- das ist ausdruecklich kein Fehler. Ein haengendes
LibreOffice darf deshalb nie ein Blatt aufhalten: Jeder Aufruf hat eine
Zeitgrenze, jeder Fehler endet in einem fehlenden Feld.

Gemessen 13.11.2026 im Container: Bildschirmfoto eines Berichts 0,3 s.
"""
import logging
import mimetypes
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from .. import config
from . import blaetter

log = logging.getLogger("sarvis.begleiter")

ORDNER = config.DATEN / "begleit"
BREITE = 480

OFFICE = {".docx", ".doc", ".odt", ".rtf", ".xlsx", ".xls", ".ods",
          ".pptx", ".ppt", ".odp"}

# Was mimetypes im schlanken Image nicht immer kennt.
_MIME_NACH = {
    ".md": "text/markdown", ".json": "application/json",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
    ".odp": "application/vnd.oasis.opendocument.presentation",
    ".webp": "image/webp", ".heic": "image/heic", ".opus": "audio/ogg",
    ".oga": "audio/ogg", ".m4a": "audio/mp4",
    ".docx": "application/vnd.openxmlformats-officedocument"
             ".wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument"
             ".spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument"
             ".presentationml.presentation",
    ".doc": "application/msword", ".xls": "application/vnd.ms-excel",
    ".ppt": "application/vnd.ms-powerpoint", ".rtf": "application/rtf",
    ".csv": "text/csv", ".zip": "application/zip", ".pdf": "application/pdf",
}


def mime_von(name: str, typ: str = "") -> str:
    if typ == "html":
        return "text/html"
    endung = Path(name).suffix.lower()
    if endung in _MIME_NACH:
        return _MIME_NACH[endung]
    geraten, _ = mimetypes.guess_type(name)
    return geraten or "application/octet-stream"


def _lauf(befehl: list, sekunden: float) -> bool:
    try:
        r = subprocess.run(befehl, stdout=subprocess.DEVNULL,
                           stderr=subprocess.PIPE, timeout=sekunden)
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("%s: %s", befehl[0], e)
        return False
    if r.returncode != 0:
        log.warning("%s endete mit %s: %s", befehl[0], r.returncode,
                    r.stderr.decode("utf-8", "replace")[-300:])
        return False
    return True


def seiten_zaehlen(pdf: Path) -> int | None:
    try:
        from pypdf import PdfReader
        n = len(PdfReader(str(pdf), strict=False).pages)
        return n or None
    except Exception as e:
        log.info("Seiten von %s nicht lesbar: %s", pdf.name, e)
        return None


def office_als_pdf(quelle: Path, ziel: Path) -> bool:
    """LibreOffice headless. Eigenes Profil je Aufruf -- zwei gleichzeitige
    soffice auf demselben Profil blockieren sich gegenseitig still."""
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return False
    with tempfile.TemporaryDirectory(prefix="sarvis-lo-") as tmp:
        ok = _lauf([soffice, f"-env:UserInstallation=file://{tmp}/profil",
                    "--headless", "--norestore", "--convert-to", "pdf",
                    "--outdir", tmp, str(quelle)], 90)
        fertig = Path(tmp) / (quelle.stem + ".pdf")
        if not ok or not fertig.is_file():
            return False
        shutil.move(str(fertig), ziel)
    return True


def _pdf_vorschau(pdf: Path, ziel: Path) -> bool:
    if not shutil.which("pdftoppm"):
        return False
    stamm = ziel.with_suffix("")
    ok = _lauf(["pdftoppm", "-png", "-f", "1", "-l", "1", "-singlefile",
                "-scale-to-x", str(BREITE), "-scale-to-y", "-1",
                str(pdf), str(stamm)], 30)
    return ok and ziel.is_file()


def _ffmpeg_vorschau(quelle: Path, ziel: Path, video: bool) -> bool:
    if not shutil.which("ffmpeg"):
        return False
    vorne = ["ffmpeg", "-v", "error", "-y"]
    skal = ["-vf", f"scale='min({BREITE},iw)':-2", "-frames:v", "1", str(ziel)]
    if video:
        # Erst eine Sekunde hinein (das erste Bild ist oft schwarz), bei
        # ganz kurzen Clips dann doch das erste.
        if _lauf(vorne + ["-ss", "1", "-i", str(quelle)] + skal, 30) \
                and ziel.is_file():
            return True
    return _lauf(vorne + ["-i", str(quelle)] + skal, 30) and ziel.is_file()


def _html_vorschau(quelle: Path, ziel: Path) -> bool:
    """Bildschirmfoto der ersten Bildschirmhoehe, 480 px breit.

    Ein eigener, kurzlebiger Chrome und nicht der Browser, mit dem Sarvis
    surft: Der hat Anmeldungen und offene Seiten, und ein Bericht ist
    Modellausgabe. Netz ist dicht (Proxy ins Leere) -- ein Bericht laedt
    ohnehin nichts nach, und so bleibt es auch, falls doch.
    """
    from .browser_kopf import chrome_finden
    try:
        chrome = chrome_finden()
    except Exception:
        return False
    if not chrome:
        return False
    with tempfile.TemporaryDirectory(prefix="sarvis-foto-") as tmp:
        ok = _lauf([chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
                    "--disable-dev-shm-usage", "--hide-scrollbars",
                    "--password-store=basic", "--disable-background-networking",
                    "--mute-audio", "--no-first-run",
                    f"--user-data-dir={tmp}/profil",
                    "--proxy-server=127.0.0.1:9",
                    f"--window-size={BREITE},{BREITE * 3 // 2}",
                    f"--screenshot={ziel}", quelle.as_uri()], 30)
    return ok and ziel.is_file()


def _unterblatt(eltern: str, pfad: Path, typ: str, titel: str,
                dateiname: str, bis: float) -> str:
    tage = max((bis - time.time()) / 86400.0, 0.01)
    k = blaetter.hinlegen(pfad, typ, titel, dateiname, tage)
    blaetter.markieren(k, {"eltern": eltern})
    return k


def anreichern(kennung: str) -> dict:
    """Begleitfelder fuer ein frisch hingelegtes Blatt bauen und merken.

    Gibt die Felder zurueck, wie sie in Blatt, Verlauf, /dateien und
    Ablage stehen. Laeuft im Thread (to_thread) -- es ruft Prozesse auf.
    """
    eintrag = blaetter.nachsehen(kennung)
    if not eintrag:
        return {}
    pfad = Path(eintrag.get("pfad") or "")
    typ = str(eintrag.get("typ") or "")
    name = str(eintrag.get("datei") or pfad.name)
    try:
        groesse = pfad.stat().st_size
    except OSError:
        return {}
    felder: dict = {"mime": mime_von(name, typ), "bytes": groesse}
    bis = float(eintrag.get("bis") or 0)
    ORDNER.mkdir(parents=True, exist_ok=True)
    titel = str(eintrag.get("titel") or pfad.stem)
    mime = felder["mime"]
    endung = Path(name).suffix.lower()

    t = time.perf_counter()
    try:
        pdf_quelle = None
        if mime == "application/pdf":
            pdf_quelle = pfad
        elif endung in OFFICE:
            ziel = ORDNER / f"{kennung}.pdf"
            if office_als_pdf(pfad, ziel):
                pdf_quelle = ziel
                felder["pdf"] = blaetter.adresse(_unterblatt(
                    kennung, ziel, "pdf", titel,
                    Path(name).stem + ".pdf", bis))
        if pdf_quelle is not None:
            n = seiten_zaehlen(pdf_quelle)
            if n:
                felder["seiten"] = n

        bild = ORDNER / f"{kennung}.png"
        gebaut = False
        if typ == "html":
            gebaut = _html_vorschau(pfad, bild)
        elif pdf_quelle is not None:
            gebaut = _pdf_vorschau(pdf_quelle, bild)
        elif mime.startswith("image/") and "svg" not in mime:
            gebaut = _ffmpeg_vorschau(pfad, bild, video=False)
        elif mime.startswith("video/"):
            gebaut = _ffmpeg_vorschau(pfad, bild, video=True)
        if gebaut:
            felder["vorschau"] = blaetter.adresse(_unterblatt(
                kennung, bild, "vorschau", f"Vorschau {titel}",
                f"{Path(name).stem}-vorschau.png", bis))
    except Exception as e:
        # Begleitfelder sind Zugabe. Was bis hier ging, bleibt.
        log.warning("Begleiter fuer %s unvollstaendig: %s", kennung[:8], e)

    blaetter.markieren(kennung, {"extra": felder})
    log.info("Begleiter %s: %s in %.1f s", kennung[:8],
             ",".join(sorted(felder)), time.perf_counter() - t)
    _aufraeumen()
    return felder


def felder(kennung: str) -> dict:
    """Die gemerkten Begleitfelder eines Blatts -- {} wenn keine."""
    e = blaetter._laden().get(str(kennung))
    extra = e.get("extra") if isinstance(e, dict) else None
    return dict(extra) if isinstance(extra, dict) else {}


def _aufraeumen() -> None:
    """Begleitdateien, auf die kein Blatt mehr zeigt, wegraeumen."""
    try:
        lebend = {str(e.get("pfad")) for e in blaetter._laden().values()
                  if isinstance(e, dict)}
        for d in ORDNER.iterdir():
            if str(d) not in lebend and time.time() - d.stat().st_mtime > 3600:
                d.unlink(missing_ok=True)
    except OSError:
        pass


def auffrischen(kennung: str) -> dict:
    """Fuer POST /ablage/oeffnen: Begleitfelder eines wieder geoeffneten
    Dokuments mitverlaengern -- oder neu bauen, wenn ein Unterblatt
    inzwischen abgelaufen und weggeraeumt ist."""
    f = felder(kennung)
    eltern = blaetter.nachsehen(kennung)
    if not eltern:
        return {}
    if not f:
        return anreichern(kennung)
    for feld in ("pdf", "vorschau"):
        if feld not in f:
            continue
        k = str(f[feld]).rsplit("/", 1)[-1]
        e = blaetter._laden().get(k)
        if not isinstance(e, dict) or not blaetter.erneuern(
                k, e.get("pfad"), e.get("typ"), e.get("titel", ""),
                e.get("datei", ""),
                max((float(eltern.get("bis") or 0) - time.time()) / 86400.0,
                    0.01)):
            return anreichern(kennung)
    return f
