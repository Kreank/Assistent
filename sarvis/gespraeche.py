"""Gesprächsfäden, ihr Verlauf und die Ablage -- auf der Platte.

Bis 11.11.2026 gab es genau ein Gespräch, und sichtbar war davon eine
Untertitelzeile. Was gesagt wurde, stand nur in der Sitzungsdatei des
SDK (werkzeuge/verlauf.py kratzt es dort heraus, für Sarvis selbst).
Für den Menschen gab es keinen Verlauf, nach dem Neuladen war alles
weg, und ein zweites Gespräch gab es nicht.

Hier liegt jetzt, was die Oberflächen zeigen:

    faeden     ein Gespräch: Titel, wann zuletzt, archiviert, und die
               SDK-Sitzung, die dazu gehört (hirn.py nimmt sie mit
               resume wieder auf)
    eintraege  was in einem Faden passiert ist: Zuruf, Antwort,
               Meldung, Rückfrage, Blatt, Kachel, Datei
    ablage     alles, was Sarvis erzeugt hat -- Blätter, Berichte,
               Dateien --, mit dem Weg zur Datei, auch wenn die Adresse
               unter /blatt/ längst abgelaufen ist
    stand      ein paar Schlüssel-Wert-Paare (welcher Faden aktiv ist)

WARUM SQLITE UND NICHT DIE SDK-SITZUNG

Die Sitzungsdatei gehört dem SDK. Ihr Format ist nicht unseres, sie wird
verdichtet ("/compact"), und Blätter oder Kacheln stehen darin nur als
Werkzeugaufruf. Ein Verlauf für Menschen ist etwas anderes als der
Kontext eines Modells -- also ein eigener Speicher, den wir selbst
schreiben. Eine Datei, keine zweite Datenbank im Netz.

WAS ES NICHT IST

Kein Gedächtnis. Das bleibt fadenübergreifend in gedaechtnis.py; ein
neuer Faden ist ein frischer Kontext, kein frischer Sarvis.
"""
import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from . import config

DATEI = config.DATEN / "gespraeche.db"

# Wie viele Einträge eine Seite des Verlaufs höchstens hat.
SEITE_MAX = 200

# Wie lang ein automatischer Titel höchstens wird.
TITEL_LAENGE = 48

_sperre = threading.RLock()
_bereit = False


def _verbindung() -> sqlite3.Connection:
    """Eine kurze Verbindung je Aufruf.

    Die Aufrufer leben in der Ereignisschleife UND in Fäden (Werkzeuge,
    Push-Versand). Eine geteilte Verbindung über Fäden hinweg ist bei
    sqlite3 eine Fehlerquelle; eine Datei zu öffnen kostet dagegen nichts
    Messbares.
    """
    DATEI.parent.mkdir(parents=True, exist_ok=True)
    v = sqlite3.connect(str(DATEI), timeout=10)
    v.row_factory = sqlite3.Row
    return v


_SCHEMA = """
CREATE TABLE IF NOT EXISTS faeden (
    id          TEXT PRIMARY KEY,
    titel       TEXT NOT NULL DEFAULT '',
    titel_von   TEXT NOT NULL DEFAULT 'auto',
    angelegt    REAL NOT NULL,
    zuletzt     REAL NOT NULL,
    archiviert  INTEGER NOT NULL DEFAULT 0,
    sitzung     TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS eintraege (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    faden   TEXT NOT NULL,
    zeit    REAL NOT NULL,
    wer     TEXT NOT NULL,
    sorte   TEXT NOT NULL,
    text    TEXT NOT NULL DEFAULT '',
    daten   TEXT NOT NULL DEFAULT '{}',
    geraet  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS eintraege_faden ON eintraege (faden, id);
CREATE TABLE IF NOT EXISTS ablage (
    schluessel  TEXT PRIMARY KEY,
    sorte       TEXT NOT NULL,
    typ         TEXT NOT NULL DEFAULT '',
    titel       TEXT NOT NULL DEFAULT '',
    datei       TEXT NOT NULL DEFAULT '',
    bytes       INTEGER NOT NULL DEFAULT 0,
    pfad        TEXT NOT NULL DEFAULT '',
    inhalt      TEXT NOT NULL DEFAULT '',
    faden       TEXT NOT NULL DEFAULT '',
    eintrag     INTEGER NOT NULL DEFAULT 0,
    seit        REAL NOT NULL,
    geaendert   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ablage_seit ON ablage (seit);
CREATE TABLE IF NOT EXISTS stand (
    schluessel  TEXT PRIMARY KEY,
    wert        TEXT NOT NULL
);
"""


def oeffnen() -> None:
    """Schema anlegen (nur dazu, nie weg) und die Blätter übernehmen.

    Additiv: Jede Tabelle mit IF NOT EXISTS. Wer hier später eine Spalte
    braucht, hängt sie mit ALTER TABLE ... ADD COLUMN an -- gelöscht
    wird nichts.
    """
    global _bereit
    with _sperre:
        with _verbindung() as v:
            v.execute("PRAGMA journal_mode=WAL")
            v.executescript(_SCHEMA)
        try:
            DATEI.chmod(0o600)
        except OSError:
            pass
        _bereit = True
        _blaetter_uebernehmen()
        _formulare_nachtragen()
        if not aktiv():
            neu = faden_anlegen()
            aktiv_setzen(neu["id"])


def _sicher_offen() -> None:
    if not _bereit:
        oeffnen()


# --- Stand ----------------------------------------------------------------

def _stand(schluessel: str, wert: str | None = None) -> str:
    with _sperre, _verbindung() as v:
        if wert is not None:
            v.execute("INSERT INTO stand VALUES (?, ?) ON CONFLICT(schluessel)"
                      " DO UPDATE SET wert = excluded.wert", (schluessel, wert))
            return wert
        z = v.execute("SELECT wert FROM stand WHERE schluessel = ?",
                      (schluessel,)).fetchone()
        return z["wert"] if z else ""


# --- Fäden ----------------------------------------------------------------

def _faden_aus(z: sqlite3.Row, anzahl: int | None = None) -> dict:
    d = {"id": z["id"], "titel": z["titel"], "angelegt": z["angelegt"],
         "zuletzt": z["zuletzt"], "archiviert": bool(z["archiviert"])}
    if anzahl is not None:
        d["eintraege"] = anzahl
    return d


def faden_anlegen(titel: str = "") -> dict:
    """Einen neuen, leeren Faden. Wird erst durch aktiv_setzen der aktive."""
    jetzt = time.time()
    kennung = "f-" + secrets.token_hex(6)
    titel = " ".join(str(titel or "").split())[:80]
    with _sperre, _verbindung() as v:
        v.execute("INSERT INTO faeden (id, titel, titel_von, angelegt, zuletzt)"
                  " VALUES (?, ?, ?, ?, ?)",
                  (kennung, titel, "mensch" if titel else "auto", jetzt, jetzt))
    return {"id": kennung, "titel": titel, "angelegt": jetzt,
            "zuletzt": jetzt, "archiviert": False, "eintraege": 0}


def faden(kennung: str) -> dict | None:
    _sicher_offen()
    with _sperre, _verbindung() as v:
        z = v.execute("SELECT * FROM faeden WHERE id = ?", (kennung,)).fetchone()
        if not z:
            return None
        n = v.execute("SELECT COUNT(*) FROM eintraege WHERE faden = ?",
                      (kennung,)).fetchone()[0]
        d = _faden_aus(z, n)
        d["sitzung"] = z["sitzung"]
        return d


def faeden() -> list[dict]:
    """Alle Fäden, zuletzt benutzte zuerst."""
    _sicher_offen()
    with _sperre, _verbindung() as v:
        zeilen = v.execute(
            "SELECT f.*, (SELECT COUNT(*) FROM eintraege e WHERE e.faden = f.id)"
            " AS n FROM faeden f ORDER BY f.zuletzt DESC").fetchall()
    return [_faden_aus(z, z["n"]) for z in zeilen]


def aktiv() -> str:
    """Die Kennung des aktiven Fadens -- leer, wenn es keinen gibt."""
    kennung = _stand("aktiv")
    if kennung:
        with _sperre, _verbindung() as v:
            if v.execute("SELECT 1 FROM faeden WHERE id = ?",
                         (kennung,)).fetchone():
                return kennung
    return ""


def aktiv_setzen(kennung: str) -> None:
    _stand("aktiv", kennung)
    with _sperre, _verbindung() as v:
        # Wer einen archivierten Faden wieder aufmacht, holt ihn zurück.
        v.execute("UPDATE faeden SET archiviert = 0, zuletzt = ? WHERE id = ?",
                  (time.time(), kennung))


def umbenennen(kennung: str, titel: str) -> bool:
    titel = " ".join(str(titel or "").split())[:80]
    with _sperre, _verbindung() as v:
        n = v.execute("UPDATE faeden SET titel = ?, titel_von = ? WHERE id = ?",
                      (titel, "mensch" if titel else "auto", kennung)).rowcount
    return bool(n)


def archivieren(kennung: str, an: bool = True) -> bool:
    with _sperre, _verbindung() as v:
        n = v.execute("UPDATE faeden SET archiviert = ? WHERE id = ?",
                      (1 if an else 0, kennung)).rowcount
    return bool(n)


def leer_entfernen(kennung: str) -> bool:
    """Einen Faden ohne einen einzigen Eintrag wieder wegnehmen.

    "Neu" antippen und dann doch in ein altes Gespräch wechseln hinterließe
    sonst eine Reihe leerer "Neues Gespräch" in der Liste. Nur was nie
    benutzt wurde -- kein Eintrag, keine Sitzung --, verschwindet.
    """
    with _sperre, _verbindung() as v:
        n = v.execute("DELETE FROM faeden WHERE id = ? AND sitzung = '' AND"
                      " NOT EXISTS (SELECT 1 FROM eintraege WHERE faden = ?)",
                      (kennung, kennung)).rowcount
    return bool(n)


def sitzung_setzen(kennung: str, sitzung: str) -> None:
    """Die SDK-Sitzung zu einem Faden festhalten -- für resume."""
    if not kennung or not sitzung:
        return
    with _sperre, _verbindung() as v:
        v.execute("UPDATE faeden SET sitzung = ? WHERE id = ? AND sitzung != ?",
                  (sitzung, kennung, sitzung))


def modelltitel_setzen(kennung: str, titel: str) -> bool:
    """Den Titel, den Sarvis selbst vergeben hat, eintragen.

    Nur solange niemand von Hand umbenannt hat (titel_von = 'auto') --
    ein Mensch gewinnt immer, auch wenn das Modell später antwortet.
    """
    titel = " ".join(str(titel or "").split()).strip(" \"'„“.:")[:80]
    if not titel:
        return False
    with _sperre, _verbindung() as v:
        n = v.execute("UPDATE faeden SET titel = ?, titel_von = 'sarvis'"
                      " WHERE id = ? AND titel_von = 'auto'",
                      (titel, kennung)).rowcount
    return n > 0


def _kurztitel(text: str) -> str:
    """Ein Titel aus dem ersten Zuruf -- die ersten Wörter, nicht geraten.

    Das ist der Platzhalter, bis Sarvis selbst benannt hat
    (main.Assistent._selbst_benennen, config.TITEL_MODELL).
    """
    t = " ".join(str(text or "").split()).strip(" ,.;:!?-")
    if len(t) <= TITEL_LAENGE:
        return t[:1].upper() + t[1:]
    schnitt = t[:TITEL_LAENGE].rsplit(" ", 1)[0] or t[:TITEL_LAENGE]
    return schnitt[:1].upper() + schnitt[1:] + " …"


# --- Einträge -------------------------------------------------------------

def _eintrag_aus(z: sqlite3.Row) -> dict:
    try:
        daten = json.loads(z["daten"] or "{}")
    except ValueError:
        daten = {}
    return {"id": z["id"], "faden": z["faden"], "zeit": z["zeit"],
            "wer": z["wer"], "sorte": z["sorte"], "text": z["text"],
            "daten": daten, "geraet": z["geraet"]}


def eintragen(faden_id: str, wer: str, sorte: str, text: str = "",
              daten: dict | None = None, geraet: str = "") -> dict:
    """Einen Eintrag anhängen. Gibt ihn zurück, wie er am Draht geht.

    Nebenbei: Der erste Zuruf in einem Faden ohne Titel gibt ihm einen.
    """
    _sicher_offen()
    jetzt = time.time()
    roh = json.dumps(daten or {}, ensure_ascii=False)
    with _sperre, _verbindung() as v:
        c = v.execute("INSERT INTO eintraege (faden, zeit, wer, sorte, text,"
                      " daten, geraet) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      (faden_id, jetzt, wer, sorte, str(text or ""), roh,
                       str(geraet or "")))
        nummer = c.lastrowid
        v.execute("UPDATE faeden SET zuletzt = ? WHERE id = ?", (jetzt, faden_id))
        if wer == "du" and sorte == "text" and text:
            erster = v.execute("SELECT titel FROM faeden WHERE id = ? AND"
                               " titel_von = 'auto' AND titel = ''",
                               (faden_id,)).fetchone() is not None
            v.execute("UPDATE faeden SET titel = ? WHERE id = ? AND"
                      " titel_von = 'auto' AND titel = ''",
                      (_kurztitel(text), faden_id))
        z = v.execute("SELECT * FROM eintraege WHERE id = ?", (nummer,)).fetchone()
    e = _eintrag_aus(z)
    if wer == "du" and sorte == "text" and text and erster:
        e["erster_zuruf"] = True      # nur intern, siehe main._eintragen
    return e


def aendern(nummer: int, text: str | None = None,
            daten: dict | None = None) -> dict | None:
    """Einen Eintrag ersetzen (dieselbe Kachel neu, die Rückfrage entschieden)."""
    with _sperre, _verbindung() as v:
        if text is not None:
            v.execute("UPDATE eintraege SET text = ? WHERE id = ?",
                      (str(text), nummer))
        if daten is not None:
            v.execute("UPDATE eintraege SET daten = ? WHERE id = ?",
                      (json.dumps(daten, ensure_ascii=False), nummer))
        z = v.execute("SELECT * FROM eintraege WHERE id = ?", (nummer,)).fetchone()
    return _eintrag_aus(z) if z else None


def eintrag(nummer: int) -> dict | None:
    """Einen Eintrag ueber seine id -- egal in welchem Faden (13.11.2026).

    Ein Formular in der Ablage soll sich auch Tage spaeter und aus einem
    anderen Faden heraus beantworten lassen.
    """
    _sicher_offen()
    with _sperre, _verbindung() as v:
        z = v.execute("SELECT * FROM eintraege WHERE id = ?",
                      (int(nummer),)).fetchone()
    return _eintrag_aus(z) if z else None


def offene_formulare(faden_id: str, anzahl: int = 200) -> list[dict]:
    """Offene Formulare unter den juengsten Eintraegen eines Fadens."""
    return [e for e in verlauf(faden_id, 0, anzahl)["eintraege"]
            if e["sorte"] == "formular" and (e["daten"] or {}).get("offen")]


def verlauf(faden_id: str, vor: int = 0, anzahl: int = 60) -> dict:
    """Die jüngsten Einträge eines Fadens, ältere seitenweise.

    vor = eine Eintragsnummer: nur was davor liegt. Zurück kommt die
    Liste ALT -> NEU, dazu ob es noch ältere gibt.
    """
    _sicher_offen()
    anzahl = max(1, min(int(anzahl or 60), SEITE_MAX))
    with _sperre, _verbindung() as v:
        if vor:
            zeilen = v.execute(
                "SELECT * FROM eintraege WHERE faden = ? AND id < ?"
                " ORDER BY id DESC LIMIT ?", (faden_id, int(vor), anzahl + 1)
            ).fetchall()
        else:
            zeilen = v.execute(
                "SELECT * FROM eintraege WHERE faden = ? ORDER BY id DESC"
                " LIMIT ?", (faden_id, anzahl + 1)).fetchall()
    mehr = len(zeilen) > anzahl
    liste = [_eintrag_aus(z) for z in zeilen[:anzahl]]
    liste.reverse()
    return {"eintraege": liste, "mehr": mehr}


def suchen(wort: str, anzahl: int = 40) -> list[dict]:
    """Einträge, in deren Text das Wort vorkommt -- über alle Fäden."""
    wort = str(wort or "").strip()
    if len(wort) < 2:
        return []
    muster = "%" + wort.replace("\\", "\\\\").replace("%", "\\%") \
        .replace("_", "\\_") + "%"
    with _sperre, _verbindung() as v:
        zeilen = v.execute(
            "SELECT e.*, f.titel AS faden_titel FROM eintraege e"
            " JOIN faeden f ON f.id = e.faden"
            " WHERE e.text LIKE ? ESCAPE '\\' AND e.sorte IN"
            " ('text', 'meldung', 'frage') ORDER BY e.id DESC LIMIT ?",
            (muster, int(anzahl))).fetchall()
    raus = []
    for z in zeilen:
        e = _eintrag_aus(z)
        e["faden_titel"] = z["faden_titel"]
        raus.append(e)
    return raus


# --- Ablage ---------------------------------------------------------------

def ablegen(schluessel: str, sorte: str, titel: str = "", datei: str = "",
            bytes_: int = 0, pfad: str = "", typ: str = "", inhalt: str = "",
            faden_id: str = "", eintrag: int = 0) -> None:
    """Ein Erzeugnis in die Ablage -- oder seinen Stand erneuern."""
    jetzt = time.time()
    with _sperre, _verbindung() as v:
        v.execute(
            "INSERT INTO ablage (schluessel, sorte, typ, titel, datei, bytes,"
            " pfad, inhalt, faden, eintrag, seit, geaendert)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(schluessel) DO UPDATE SET titel = excluded.titel,"
            " datei = excluded.datei, bytes = excluded.bytes,"
            " inhalt = excluded.inhalt, geaendert = excluded.geaendert,"
            " pfad = CASE WHEN excluded.pfad != '' THEN excluded.pfad ELSE pfad END,"
            " typ = CASE WHEN excluded.typ != '' THEN excluded.typ ELSE typ END,"
            " faden = CASE WHEN faden = '' THEN excluded.faden ELSE faden END,"
            " eintrag = CASE WHEN eintrag = 0 THEN excluded.eintrag ELSE eintrag END",
            (schluessel, sorte, typ, str(titel or ""), str(datei or ""),
             int(bytes_ or 0), str(pfad or ""), str(inhalt or ""),
             faden_id or "", int(eintrag or 0), jetzt, jetzt))


def abgelegt(schluessel: str) -> dict | None:
    with _sperre, _verbindung() as v:
        z = v.execute("SELECT * FROM ablage WHERE schluessel = ?",
                      (schluessel,)).fetchone()
    return dict(z) if z else None


def ablage(sorte: str = "", anzahl: int = 300) -> list[dict]:
    """Was Sarvis erzeugt hat, neueste zuerst -- ohne den Markdown-Text.

    Der Text eines Blattes kann 40.000 Zeichen haben. Für eine Liste
    reicht der Titel; geholt wird der Text beim Öffnen.
    """
    _sicher_offen()
    bedingung, werte = "", []
    if sorte:
        bedingung, werte = "WHERE a.sorte = ?", [sorte]
    with _sperre, _verbindung() as v:
        zeilen = v.execute(
            "SELECT a.schluessel, a.sorte, a.titel, a.datei, a.bytes, a.pfad,"
            " a.faden, a.eintrag, a.seit, a.geaendert, f.titel AS faden_titel"
            " FROM ablage a LEFT JOIN faeden f ON f.id = a.faden "
            + bedingung + " ORDER BY a.seit DESC LIMIT ?",
            (*werte, int(anzahl))).fetchall()
    raus = []
    for z in zeilen:
        d = dict(z)
        pfad = d.pop("pfad") or ""
        # Ob die Datei noch da ist, gehört in die Liste: Berichte räumt
        # bericht._aufraeumen nach einer Weile weg. Ein Eintrag, der
        # beim Antippen "gibt es nicht mehr" sagt, ist ehrlicher als einer,
        # der fehlt -- aber er soll es vorher schon zeigen.
        d["vorhanden"] = True if d["sorte"] in ("markdown", "formular") else (
            bool(pfad) and Path(pfad).is_file())
        d["faden_titel"] = d.get("faden_titel") or ""
        raus.append(d)
    return raus


def _formulare_nachtragen() -> None:
    """Formulare aus der Zeit vor dem 13.11.2026 (abends) in die Ablage.

    Seitdem legt main._mitschrift jedes neue selbst ab; das hier holt die
    aelteren nach und tut danach nichts mehr (INSERT OR IGNORE).
    """
    with _sperre, _verbindung() as v:
        v.execute(
            "INSERT OR IGNORE INTO ablage (schluessel, sorte, titel, faden,"
            " eintrag, seit, geaendert)"
            " SELECT 'fm-' || id, 'formular', text, faden, id, zeit, zeit"
            " FROM eintraege WHERE sorte = 'formular'")


def blatt_finden(stichwort: str = "") -> dict | None:
    """Das juengste Markdown-Blatt, dessen Titel das Stichwort enthaelt.

    Fuer blatt_lesen: Sarvis soll ein Blatt so sehen, wie es JETZT ist --
    mit den Haken, die Sascha inzwischen gesetzt hat.
    """
    _sicher_offen()
    wort = str(stichwort or "").strip()
    muster = "%" + wort.replace("\\", "\\\\").replace("%", "\\%") \
        .replace("_", "\\_") + "%"
    with _sperre, _verbindung() as v:
        z = v.execute(
            "SELECT schluessel, titel, inhalt, eintrag, seit, geaendert"
            " FROM ablage WHERE sorte = 'markdown' AND titel LIKE ?"
            " ESCAPE '\\' ORDER BY seit DESC LIMIT 1", (muster,)).fetchone()
    return dict(z) if z else None


def _blaetter_uebernehmen() -> None:
    """Was schon in blaetter.json steht, einmal in die Ablage.

    Zusammenführen statt doppeln: Die Dateiliste der App (GET /dateien)
    liest weiter blaetter.json; die Ablage kennt alles, auch das, was vor
    ihr entstand.
    """
    try:
        from .netz import blaetter
        alle = blaetter._laden()
    except Exception:
        return
    for kennung, e in alle.items():
        if not isinstance(e, dict) or abgelegt(kennung):
            continue
        typ = str(e.get("typ") or "")
        pfad = str(e.get("pfad") or "")
        try:
            groesse = Path(pfad).stat().st_size
        except OSError:
            groesse = 0
        with _sperre, _verbindung() as v:
            v.execute(
                "INSERT OR IGNORE INTO ablage (schluessel, sorte, typ, titel,"
                " datei, bytes, pfad, seit, geaendert)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (kennung, "html" if typ == "html" else "datei", typ,
                 str(e.get("titel") or ""), str(e.get("datei") or ""),
                 groesse, pfad, float(e.get("seit") or time.time()),
                 float(e.get("seit") or time.time())))
