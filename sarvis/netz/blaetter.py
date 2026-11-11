"""Blaetter -- was Sarvis zeigt, statt es zu sagen.

Ein Blatt ist ein Stueck Inhalt, das zu gross fuer eine Kachel und zu
gestaltet fuer den Untertitel ist: ein Bericht, eine formatierte Notiz,
ein PDF zum Behalten. Drei Sorten, ein Begriff:

    markdown   Text mit Struktur. Geht komplett ueber den Draht, keine
               Datei, keine Adresse. Fuer die Antwort, die man liest
               statt hoert.
    html       Eine ganze Seite (werkzeuge/bericht.py baut sie). Liegt
               als Datei hier und wird ueber /blatt/<kennung> geholt.
    datei      PDF oder Word. Derselbe Weg, nur mit einem Knopf zum
               Herunterladen statt einem Rahmen zum Ansehen.

WARUM ES DIESE DATEI UEBERHAUPT GIBT

Auf dem Dev-PC schickte bericht.py ein file:///-Ziel an das eingebaute
Browserfenster, und das ging auf. Im Container geht das nicht: Die Datei
liegt auf dem Server, der Browser des Nutzers steht woanders, und die
Weboberfaeche verwirft alles, was nicht http ist -- STILL (sarvis.js,
seiteZeigen). Sarvis sagte also "der Bericht liegt vor dir", und es lag
nichts da. Kein Fehler im Protokoll, kein Eintrag im Log: eine Zusage,
die niemand einloest.

Ein Blatt schliesst diese Luecke an der einzigen Stelle, an der sie zu
schliessen ist -- bei der Auslieferung.

WARUM DIE KENNUNG DER GANZE SCHUTZ IST

    https://sarvis.tech-artist.de/blatt/<24 Bytes Zufall>

Diese Adresse traegt keinen Geraeteschluessel, und das ist keine
Nachlaessigkeit, sondern die einzige Bauart, die funktioniert: Ein
<iframe> schickt keine eigenen Kopfzeilen, ein Download-Knopf auch
nicht, und der Systemviewer, der das PDF spaeter oeffnet, erst recht
nicht. Wer hier eine Anmeldung verlangt, bekommt ein leeres Rechteck --
und zwar wieder eines ohne Fehlermeldung.

Was stattdessen schuetzt, ist dieselbe Ueberlegung wie bei den
Rueckadressen in netz/spotify.py, nur strenger:

  Die Kennung. secrets.token_urlsafe(24) sind 192 Bit aus dem
  Betriebssystem-Zufall. Erraten ist kein Angriffsweg, sondern eine
  Rechnung, die vor der Sonne fertig ist.

  Die Frist. Nach FRIST_TAGE ist das Blatt weg, auch wenn die Datei noch
  liegt. Ein Link, der einmal in einem Verlauf gelandet ist, gilt nicht
  ewig.

  Der Pfad wird nie aus der Adresse gebaut. Die Kennung ist ein
  Schluessel in ein Verzeichnis, kein Dateiname. "../../config.py" ist
  hier kein Pfad, sondern schlicht eine unbekannte Kennung.

  Kein Verzeichnis. Es gibt keine Liste aller Blaetter ueber HTTP. Wer
  eine Kennung nicht hat, kann sie auch nicht finden.

WARUM DAS VERZEICHNIS AUF DIE PLATTE GEHT

Ein Neustart des Dienstes ist im Betrieb nichts Besonderes -- ein neues
Image, ein Absturz, ein `compose up`. Laege das Verzeichnis nur im
Speicher, waere jeder offene Bericht danach tot, und zwar mit einem 404
in einem Rahmen, den der Nutzer gerade noch gelesen hat. Die Datei ist
klein und wird selten geschrieben.
"""
import json
import logging
import mimetypes
import secrets
import time
from pathlib import Path
from urllib.parse import quote

from aiohttp import web

from .. import config

log = logging.getLogger("sarvis.blaetter")

# Wo das Verzeichnis liegt. Unter DATEN, also im Volume -- es ueberlebt
# einen Neubau des Images, wie alles, was Sarvis gehoert.
VERZEICHNIS = config.DATEN / "blaetter.json"

# Wie lange ein Blatt abrufbar bleibt.
FRIST_TAGE = 7.0

# Wie viele Eintraege das Verzeichnis hoechstens fuehrt. Der Deckel ist
# gegen das unbegrenzte Wachsen einer Datei, die bei jedem Bericht
# einmal geschrieben wird -- nicht gegen einen Angriff.
EINTRAEGE_MAX = 400

# Was ueber diesen Weg ueberhaupt ausgeliefert wird. Eine Freiliste und
# keine Sperrliste: Was hier nicht steht, geht nicht hinaus, auch wenn
# ein Werkzeug es spaeter einmal hinlegt.
TYPEN = {
    "html": ("text/html; charset=utf-8", False),
    "pdf": ("application/pdf", True),
    "word": ("application/vnd.openxmlformats-officedocument"
             ".wordprocessingml.document", True),
    "excel": ("application/vnd.openxmlformats-officedocument"
              ".spreadsheetml.sheet", True),
    # charset im Typ, damit der Browser nicht raet -- und die Datei
    # traegt zusaetzlich eine BOM, weil Excel nur darauf hoert.
    "csv": ("text/csv; charset=utf-8", True),
    "text": ("text/plain; charset=utf-8", True),
    # Alles andere, was datei_schicken vom Server holt -- Fotos, ZIPs,
    # Plaene. Der Inhaltstyp wird beim Ausliefern aus dem Namen geraten;
    # geschickt wird IMMER als Anhang, nie zum Anzeigen im Browser: Eine
    # HTML- oder SVG-Datei vom Server wuerde sonst auf unserer Domain
    # ausgefuehrt.
    "beliebig": ("application/octet-stream", True),
}

# Was aus dem Server verschickt wurde, bleibt laenger abrufbar als ein
# Bericht: Man laedt es nicht immer sofort herunter, und die App fuehrt
# eine Liste aller empfangenen Dateien (siehe DRAHT.md, "Dateien").
FRIST_VERSAND_TAGE = 30.0

# Die Kopfzeilen, die JEDES Blatt bekommt.
#
# Die CSP hier ist die zweite von dreien, und sie ist die einzige, auf
# die sich verlassen laesst: Die erste steht im <head> des Dokuments
# (bericht.SICHERHEIT) und kaeme aus derselben Quelle wie der Inhalt --
# wer den Rumpf schreibt, koennte auch den Kopf schreiben. Die dritte
# ist das sandbox-Attribut am <iframe> in der Oberflaeche.
#
# "sandbox" ohne allow-same-origin steckt das Dokument in einen eigenen,
# leeren Ursprung: kein Zugriff auf localStorage, keine Cookies, kein
# Weg zu window.parent. Das ist der Riegel, um den es hier geht --
# ein Bericht wird aus Modellausgabe gebaut, und Modellausgabe hat auf
# Seiten gestanden, die Sarvis vorher gelesen hat.
KOEPFE = {
    "Content-Security-Policy": (
        "sandbox allow-popups allow-popups-to-escape-sandbox; "
        "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
        "font-src 'none'; connect-src 'none'; script-src 'none'; "
        "form-action 'none'; base-uri 'none'; frame-ancestors 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    # Nicht in fremden Zwischenspeichern und nicht im Verlauf der
    # Zwischenstationen: Es sind Kontostaende, Termine, Projektdaten.
    "Cache-Control": "private, no-store",
}


def _laden() -> dict:
    try:
        roh = json.loads(VERZEICHNIS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return roh if isinstance(roh, dict) else {}


def _schreiben(alle: dict) -> None:
    try:
        VERZEICHNIS.parent.mkdir(parents=True, exist_ok=True)
        # Erst daneben, dann umbenennen: Ein Absturz mitten im Schreiben
        # hinterlaesst sonst eine halbe JSON, und danach ist JEDES Blatt
        # weg statt nur das neue.
        neben = VERZEICHNIS.with_suffix(".json.neu")
        neben.write_text(json.dumps(alle, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        neben.replace(VERZEICHNIS)
    except OSError as e:
        log.warning("Blattverzeichnis nicht geschrieben: %s", e)


def _aufraeumen(alle: dict) -> dict:
    """Abgelaufene und ueberzaehlige Eintraege entfernen.

    Die Datei selbst bleibt liegen -- sie gehoert der Ablage, und
    bericht._aufraeumen fuehrt dort schon Buch. Hier faellt nur der
    Zugang weg.
    """
    jetzt = time.time()
    gueltig = {k: v for k, v in alle.items()
               if isinstance(v, dict) and float(v.get("bis") or 0) > jetzt}
    if len(gueltig) > EINTRAEGE_MAX:
        nach_alter = sorted(gueltig.items(),
                            key=lambda kv: float(kv[1].get("seit") or 0),
                            reverse=True)
        gueltig = dict(nach_alter[:EINTRAEGE_MAX])
    return gueltig


def hinlegen(pfad, typ: str = "html", titel: str = "",
             dateiname: str = "", tage: float = 0.0) -> str:
    """Eine Datei abrufbar machen. Gibt die Kennung zurueck.

    Die Datei wird nicht kopiert und nicht verschoben -- sie bleibt, wo
    sie liegt. Das Blatt ist nur der Zugang zu ihr.
    """
    datei = Path(pfad)
    if typ not in TYPEN:
        raise ValueError(f"Unbekannte Blattsorte: {typ!r}")
    kennung = secrets.token_urlsafe(24)
    alle = _aufraeumen(_laden())
    alle[kennung] = {
        "pfad": str(datei),
        "typ": typ,
        "titel": str(titel or datei.stem),
        # Was im Speichern-Dialog steht. Ohne eigenen Namen der der
        # Datei -- der traegt den Zeitstempel und ist brauchbar.
        "datei": str(dateiname or datei.name),
        "seit": time.time(),
        "bis": time.time() + (float(tage) or FRIST_TAGE) * 86400.0,
    }
    _schreiben(alle)
    return kennung


def erneuern(kennung: str, pfad, typ: str, titel: str = "",
             dateiname: str = "", tage: float = 0.0) -> float:
    """Eine abgelaufene Adresse aus der Ablage wieder aufmachen.

    Die Ablage (gespraeche.py) behaelt, was Sarvis erzeugt hat, laenger
    als die Frist einer Adresse. Wer es dort antippt, ist angemeldet --
    der Weg dorthin (POST /ablage/oeffnen) traegt den Geraeteschluessel.
    Dann bekommt DIESELBE Kennung eine neue Frist. Eine neue Kennung
    hiesse, dass die Karte im Verlauf auf eine tote Adresse zeigt.

    Gibt das neue "bis" zurueck, 0.0 wenn die Datei nicht mehr da ist.
    """
    datei = Path(pfad)
    if typ not in TYPEN or not datei.is_file():
        return 0.0
    alle = _aufraeumen(_laden())
    alt = alle.get(kennung) if isinstance(alle.get(kennung), dict) else {}
    bis = max(float(alt.get("bis") or 0),
              time.time() + (float(tage) or FRIST_TAGE) * 86400.0)
    alle[kennung] = {
        "pfad": str(datei), "typ": typ,
        "titel": str(titel or alt.get("titel") or datei.stem),
        "datei": str(dateiname or alt.get("datei") or datei.name),
        "seit": float(alt.get("seit") or time.time()), "bis": bis,
    }
    _schreiben(alle)
    return bis


def adresse(kennung: str) -> str:
    """Der Pfad, den die Oberflaeche anfaehrt.

    Absichtlich RELATIV. Der Endpunkt kennt seine oeffentliche Adresse
    nicht -- er hoert auf 127.0.0.1, davor steht Caddy. Eine hier
    gebaute absolute Adresse waere geraten, und beim Ausprobieren auf
    dem Rechner waere sie falsch. Die Oberflaeche weiss, woher sie
    geladen wurde; sie setzt das Fehlende davor.
    """
    return f"/blatt/{kennung}"


def nachsehen(kennung: str) -> dict | None:
    eintrag = _laden().get(str(kennung))
    if not isinstance(eintrag, dict):
        return None
    if float(eintrag.get("bis") or 0) <= time.time():
        return None
    return eintrag


async def _ausliefern(anfrage: web.Request) -> web.StreamResponse:
    kennung = anfrage.match_info.get("kennung", "")
    eintrag = nachsehen(kennung)
    if eintrag is None:
        # Dieselbe Antwort fuer "gibt es nicht" und "ist abgelaufen".
        # Der Unterschied waere eine Auskunft an jemanden, der raet.
        return web.Response(status=404, text="Dieses Blatt gibt es nicht "
                            "(mehr).", headers={"Cache-Control": "no-store"})

    datei = Path(eintrag.get("pfad") or "")
    if not datei.is_file():
        log.warning("Blatt %s zeigt auf %s -- weg.", kennung[:8], datei)
        return web.Response(status=410, text="Die Datei zu diesem Blatt "
                            "liegt nicht mehr da.")

    art, anhang = TYPEN.get(str(eintrag.get("typ")), TYPEN["html"])
    if eintrag.get("typ") == "beliebig":
        geraten, _ = mimetypes.guess_type(str(eintrag.get("datei") or datei.name))
        # Nie als HTML/SVG/JS ausliefern -- auch nicht als Anhang mit
        # passendem Typ. nosniff + octet-stream ist die sichere Seite.
        if geraten and not any(t in geraten for t in
                                ("html", "svg", "javascript", "xml")):
            art = geraten
    koepfe = dict(KOEPFE)
    if anhang:
        # Ein PDF im Rahmen anzuzeigen waere schoener, aber der Rahmen
        # ist ein sandbox-iframe ohne Skripte -- Chromes PDF-Betrachter
        # laeuft darin nicht. Also herunterladen und im Systemviewer
        # oeffnen: dort kann man drucken, suchen und behalten.
        name = str(eintrag.get("datei") or datei.name)
        # Nur ASCII in filename, der Rest in filename* -- ein Umlaut im
        # blossen filename bricht den Kopf bei aelteren Empfaengern.
        schlicht = (name.encode("ascii", "replace").decode("ascii")
                    .replace('"', "_"))
        koepfe["Content-Disposition"] = (
            f'attachment; filename="{schlicht}"; '
            f"filename*=UTF-8''{quote(name)}"
        )
    return web.FileResponse(datei, headers={**koepfe, "Content-Type": art})


def anmelden(app: web.Application) -> None:
    """Die Route eintragen. Ruft netz/server.py beim Aufbau."""
    app.router.add_get("/blatt/{kennung}", _ausliefern)


def dateien() -> list:
    """Alle noch abrufbaren DATEIEN (keine Berichte), neueste zuerst.

    Fuer GET /dateien: Die App fuehrt daraus ihre Liste "von Sarvis". Ohne
    sie waere ein Download, der kam, waehrend die App zu war, verloren --
    das Blatt geht nur an verbundene Oberflaechen.
    """
    liste = []
    for kennung, e in _aufraeumen(_laden()).items():
        if e.get("typ") == "html":
            continue
        datei = Path(e.get("pfad") or "")
        try:
            groesse = datei.stat().st_size
        except OSError:
            continue
        liste.append({"kennung": kennung, "titel": e.get("titel") or "",
                      "datei": e.get("datei") or datei.name,
                      "adresse": adresse(kennung), "bytes": groesse,
                      "seit": e.get("seit") or 0, "bis": e.get("bis") or 0})
    liste.sort(key=lambda x: x["seit"], reverse=True)
    return liste


def raten(dateiname: str) -> str:
    """Aus einem Dateinamen die Blattsorte -- oder "text" als Rueckfall."""
    art, _ = mimetypes.guess_type(str(dateiname))
    for sorte, (typ, _anhang) in TYPEN.items():
        if art and typ.startswith(art):
            return sorte
    return "text"
