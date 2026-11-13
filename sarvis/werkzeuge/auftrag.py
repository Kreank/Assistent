"""Aufträge: Arbeiter im Hintergrund, die tatsächlich entwickeln.

Der Aufbau, auf den es ankommt -- zwei getrennte Sitzungen:

  Sarvis    schnell, redet mit dir, hat KEINE Schreibrechte.
  Arbeiter  eigene Sitzung, effort high, Schreibrechte NUR im Projekt.

Die Trennung ist nicht Kosmetik. Im SDK erben Unteragenten den
Erlaubnismodus ihres Elternteils und koennen ihn nicht ueberschreiben --
haette Sarvis' Sitzung Schreibrechte, haetten sie alle, ueberall.

Geprüft wird nicht vorher, sondern nachher: Jeder Auftrag arbeitet auf
einem eigenen Git-Zweig und schreibt einen Bericht. Gefaellt das Ergebnis
nicht, ist es ein `git checkout master` -- und weg.
"""
import asyncio
import json
import re
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    tool,
)

from .. import config, schutz
from .projekte import _finden, _pfad

# Werkzeuge, die der Arbeiter benutzen darf. Alles Uebrige wird abgelehnt.
ARBEITER_WERKZEUGE = [
    "Read", "Write", "Edit", "Glob", "Grep", "Bash",
    "WebSearch", "WebFetch", "TodoWrite", "NotebookEdit",
    # Unter-Arbeiter: Damit teilt ein Arbeiter grosse Aufgaben auf --
    # "drei bauen, zwei pruefen". Beide Namen, siehe config.UNTERARBEITER.
    *config.UNTERARBEITER,
]

# Gemessen am 26.08.2026: Die Werkzeugaufrufe eines UNTER-Arbeiters
# laufen durch dieselbe Rechtepruefung wie die des Arbeiters. Ein
# Unter-Arbeiter, der ausserhalb des Projektordners lesen wollte, wurde
# abgelehnt -- und die Ablehnung kam beim Arbeiter an, nicht still
# verschluckt. Die Grenze "nichts ausserhalb des Ordners" traegt also
# auch eine Ebene tiefer.

# Shell-Befehle, die auch im eigenen Ordner nichts zu suchen haben.
VERBOTEN = (
    r"\bgit\s+push\b",
    r"\bgit\s+remote\b",
    r"\bshutdown\b", r"\bformat\b", r"\breg\s+(add|delete)\b",
    r"\bnet\s+user\b", r"\brunas\b", r"\bsc\s+(create|delete)\b",
    r"curl[^|]*\|\s*(ba)?sh",       # curl ... | sh
    r"iwr[^|]*\|\s*iex",            # PowerShell-Aequivalent
    r"\brmdir\s+/s\s+[a-z]:\\",
    r"\bdel\s+/[fs]",

    # --- Linux ------------------------------------------------------
    # Der Arbeiter hat Bash. Seine einzige Schranke ist der Projektordner,
    # und die traegt nur, wo ein Pfad im Befehl steht. Diese Muster
    # greifen unabhaengig davon -- sie sperren die Befehle, die auch im
    # eigenen Ordner nichts zu suchen haben.
    r"\bsudo\b",                              # gar nicht erst anfangen
    r"\bsystemctl\b", r"\bservice\s+\w+\s+(stop|restart)\b",
    r"\bdocker\b[^|]*\s-v\s+/[^:\s]*:",      # Host-Ordner hereinmounten
    r"\bdocker\b[^|]*--privileged",
    r"\bdocker\s+system\s+prune\b",
    r"\b(mkfs|wipefs|shred)\b", r"\bdd\b[^|]*\bof=/dev/",
    r"\b(chmod|chown)\b[^|]*\s-R\b[^|]*\s/\s*$",
    r"\b(userdel|usermod|passwd)\b",
    r"\bln\b(?![^|]*\s-s)",                   # HARTE Links, siehe unten
    r"\bcrontab\b",
)

# Warum ln ohne -s gesperrt ist:
#
# Ein harter Link hat kein Ziel, das sich aufloesen liesse -- er IST die
# Datei. Ein harter Link im Projektordner auf eine Datei ausserhalb macht
# diese Datei damit im Projektordner beschreibbar, und keine Ortspruefung
# kann das sehen: gemessen lieferte schreiben_stufe() fuer so einen Link
# "frei". Symbolische Links (ln -s) sind harmlos, weil resolve() ihnen
# folgt und am ZIEL misst -- die bleiben erlaubt.

ARBEITER_PROMPT = """Du arbeitest an einem Projekt für Sascha.

Ablauf:
1. Verschaff dir erst einen Überblick über das Projekt.
2. Setz den Auftrag um. Kleine, nachvollziehbare Schritte.
3. Prüfe deine Arbeit, so weit es geht: Starte was startbar ist, lass
   Tests laufen, wenn es welche gibt. Ungeprüfter Code ist halbe Arbeit.
4. Committe auf dem aktuellen Zweig. Sinnvolle Commit-Nachrichten.
5. Schreib zum Schluss `bericht.md` im Projektordner.

Der Bericht ist das Wichtigste, denn Sascha war nicht dabei. Er enthält:
- Was du gemacht hast, in ganzen Sätzen.
- Was du geprüft hast und was dabei herauskam. Mit Zahlen, wenn es
  welche gibt.
- Woran du unsicher warst, und was du deshalb NICHT gemacht hast.
- Was als Nächstes anstünde.

Schreib den Bericht ehrlich. Wenn etwas nicht funktioniert hat, gehört
das hinein — ein Bericht, der Erfolg meldet, wo keiner war, ist schlimmer
als gar keiner.

Die allerletzte Zeile deiner Antwort beginnt mit `GESPROCHEN:` und
enthält zwei bis drei Sätze, die jemandem vorgelesen werden. Reiner
Fließtext: keine Aufzählung, keine Sternchen, keine Backticks, keine
Dateinamen mit Endung. Sag, was jetzt anders ist und ob es geprüft ist.

Beispiel:
GESPROCHEN: Die Kilometergeld-Berechnung steht, mit dreißig Cent je
Kilometer und kaufmännischer Rundung. Zehn Tests laufen durch. Offen ist
noch, wie mehrere Fahrten zusammengerechnet werden sollen.

Grenzen: Du bleibst im Projektordner. Kein `git push`, kein Merge nach
main, nichts außerhalb des Ordners.

Führe Buch, und zwar WÄHREND der Arbeit, nicht am Ende:

* Lege gleich zu Beginn `fortschritt.md` im Projektordner an und schreibe
  nach jedem abgeschlossenen Teilschritt eine Zeile hinein: was du getan
  hast, was du geprüft hast, was als Nächstes drankommt. Diese Datei ist
  für den Fall, dass du mitten in der Arbeit abgeschnitten wirst — dann
  ist sie das Einzige, woran jemand anknüpfen kann. Ein Bericht, den es
  erst am Ende gibt, gibt es genau dann nicht, wenn er gebraucht wird.
* Committe nach jedem abgeschlossenen Teilschritt, mit einer Nachricht,
  die sagt WAS fertig ist. Der Zweig wird ohnehin nie nach main
  gemergt — häufige Commits kosten dich nichts und sind der einzige
  verlässliche Zwischenstand.
* Wirst du fortgesetzt, lies zuerst `git log`, `git status` und
  `fortschritt.md`. Fang nicht von vorn an.

Fehlende Angaben: Fehlt dir etwas, das nur Sascha wissen kann (Anschrift,
E-Mail, Telefon, Impressumsangaben, persönliche Texte), dann erfinde es
nicht — aber bau auch keine großen sichtbaren TODO-Kästen in das
Ergebnis. Lass den Teil schlicht und unauffällig weg oder nimm einen
dezenten Platzhalter, und schreib im Bericht unter der Überschrift
"## Offene Fragen an Sascha" jede fehlende Angabe als konkrete Frage auf.
Sarvis legt sie ihm als Formular hin. Genau dieses Format, eine Frage je
Nummer, damit es sich lesen lässt:
    1. **Kurzer Titel:** Die Frage in einem Satz. (Vorschlag, falls du einen hast)
Nur fragen, was Sascha wirklich entscheiden muss — höchstens zehn Fragen.

Werkstatt und Handbuch (nur lesen) unter /opt/handbuch — zuerst
/opt/handbuch/README.md lesen, wenn eins davon passt:
* Webseiten, die beeindrucken sollen (Portfolio, Firmenseite,
  Landingpage): Saschas Hausstil in
  /opt/handbuch/webseiten-design/SKILL.md. Das ist VERBINDLICH, nicht
  Inspiration. Ein generischer Standard-Look (Karten-Raster, Pillen,
  Orange auf Dunkelgrau) ist genau das, was Sascha nicht will.
* 3D (Leitmotiv, Hero-Bild, glTF für three.js): `blender`, Anleitung in
  /opt/handbuch/blender/ANLEITUNG.md. Nur auf der CPU rendern.
* Videos aus HTML (Projekt-Clips, animierte Vorschauen): `hyperframes`,
  Anleitung in /opt/handbuch/hyperframes/hyperframes/SKILL.md.
* Bilder von echten, laufenden Seiten (z. B. für Projektkarten) holst du
  dir mit Chrome im Hintergrund:
  `google-chrome --headless=new --no-sandbox --hide-scrollbars
  --window-size=1440,900 --screenshot=bild.png <adresse>`

Bei allem Sichtbaren (Webseite, Bild, Video): Sieh dir das Ergebnis
selbst an, bevor du fertig meldest — Screenshot machen, mit Read
öffnen, kritisch prüfen wie ein Gestalter, nachbessern. Mindestens zwei
Runden. Bilder vorher klein halten (Breite höchstens 1600 Pixel), sonst
wird die Nachricht zu groß."""


def _stand_lesen(ordner: Path) -> tuple[str, str]:
    """(zuletzt erledigt, als Naechstes) aus fortschritt.md.

    Der Arbeiter fuehrt die Datei waehrend der Arbeit (ARBEITER_PROMPT):
    "- [x] Was fertig ist ... Nächstes: Was kommt." Gelesen wird der
    letzte abgehakte Punkt.
    """
    try:
        text = (ordner / "fortschritt.md").read_text(encoding="utf-8")
    except OSError:
        return "", ""
    punkte = re.findall(r"^\s*-\s*\[x\]\s*(.+?)(?=^\s*-\s*\[|^#|^>|\Z)",
                        text, re.M | re.S | re.I)
    if not punkte:
        return "", ""
    letzter = " ".join(punkte[-1].split())
    naechstes = ""
    m = re.search(r"N(?:ä|ae)chste[sr]?:\s*(.+)$", letzter)
    if m:
        naechstes = m.group(1).strip()
        letzter = letzter[:m.start()].strip()
    letzter = re.sub(r"[`*]", "", letzter)
    naechstes = re.sub(r"[`*]", "", naechstes)
    return _satzweise(letzter, 260), _satzweise(naechstes, 160)


def _satzweise(text: str, grenze: int) -> str:
    """Auf hoechstens grenze Zeichen kuerzen -- am Satzende, nicht mitten
    im Wort. ("Offen ist, ob noch eine Datenschutze Er hat 4 Fragen" war
    der Anlass, 13.11.2026.)"""
    text = " ".join((text or "").split())
    if len(text) <= grenze:
        return text
    stueck = text[:grenze]
    ende = max(stueck.rfind(". "), stueck.rfind("! "), stueck.rfind("? "))
    if ende >= grenze // 3:
        return stueck[:ende + 1]
    return stueck.rsplit(" ", 1)[0] + " …"


def offene_fragen(ordner: Path) -> list[dict]:
    """Die Fragen aus "## Offene Fragen an Sascha" in bericht.md.

    Format, wie der Arbeiter es schreibt (ARBEITER_PROMPT):
        1. **Kontakt-E-Mail:** Welche Adresse soll ...
           (Vorschlag: ...)
    -> [{"nr": 1, "titel": "Kontakt-E-Mail", "frage": "Welche Adresse ..."}]
    Folgezeilen gehoeren zur Frage davor. Hoechstens 20 Fragen.
    """
    try:
        text = (ordner / "bericht.md").read_text(encoding="utf-8")
    except OSError:
        return []
    m = re.search(r"^##+\s*Offene Fragen[^\n]*\n(.*?)(?=^##?\s|^---\s*$|\Z)",
                  text, re.M | re.S)
    if not m:
        return []
    fragen, aktuell = [], None
    for zeile in m.group(1).splitlines():
        neu = re.match(r"^\s*(\d+)[.)]\s+(.*)$", zeile)
        if neu:
            aktuell = {"nr": int(neu.group(1)), "roh": neu.group(2).strip()}
            fragen.append(aktuell)
        elif aktuell is not None and zeile.strip():
            aktuell["roh"] += " " + zeile.strip()
    aus = []
    for f in fragen[:20]:
        roh = f["roh"]
        t = re.match(r"^\*\*(.+?)\*\*:?\s*(.*)$", roh)
        titel, frage = (t.group(1).rstrip(":").strip(), t.group(2).strip()) if t \
            else ("", roh)
        frage = re.sub(r"[*`]", "", frage).strip()
        aus.append({"nr": f["nr"], "titel": titel[:80], "frage": frage[:400]})
    return aus


def _eingang_kopieren(ordner: Path, namen: list) -> tuple[int, list]:
    """Dateien aus dem Sarvis-Eingang nach <projekt>/eingang/ kopieren.

    Nur reine Dateinamen (kein Pfad), nur was wirklich im Eingang liegt.
    eingang/ kommt in die .gitignore: Was Sascha schickt, kann Privates
    enthalten (gemessen: Screenshots mit Kundendaten) und gehoert nicht
    in die Projektgeschichte.
    """
    if not namen:
        return 0, []
    import shutil
    from ..orte import EINGANG
    ziel = ordner / "eingang"
    ziel.mkdir(exist_ok=True)
    kopiert, fehlt = 0, []
    for name in namen:
        name = Path(str(name)).name
        quelle = EINGANG / name
        if name and quelle.is_file():
            shutil.copy2(quelle, ziel / name)
            kopiert += 1
        else:
            fehlt.append(name)
    ignore = ordner / ".gitignore"
    try:
        zeilen = ignore.read_text(encoding="utf-8").splitlines() if ignore.exists() else []
        if "eingang/" not in zeilen:
            with ignore.open("a", encoding="utf-8") as f:
                f.write(("\n" if zeilen and zeilen[-1] else "") + "eingang/\n")
    except OSError:
        pass
    return kopiert, fehlt


def _glatt(text: str, grenze: int = 600) -> str:
    """Formatierung wegnehmen, bis nur noch sprechbarer Fliesstext bleibt.

    Stand frueher fest in vorlesbar(). Jetzt steht es hier, weil
    bericht_kurz() dieselbe Behandlung braucht: Ein Bericht wird mit
    genau denselben Sternchen und Backticks geschrieben wie die
    Schlussnachricht, und Piper spricht beides gleich falsch aus.
    """
    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[`*_#>]+", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)   # Links
    text = re.sub(r"\b([\w-]+)\.(py|md|txt|json|js|ts|html|css)\b",
                  r"\1", text)                              # Dateiendungen
    return " ".join(text.split())[:grenze]


def vorlesbar(text: str) -> str:
    """Aus der Schlussnachricht des Arbeiters einen sprechbaren Satz machen.

    Der Arbeiter schreibt fuer Menschen, die lesen -- mit Sternchen,
    Backticks und Aufzaehlungen. Piper spricht das als "Sternchen
    Sternchen kilometergeld punkt py". Deshalb erst die markierte Zeile
    suchen, und was uebrig bleibt, von Formatierung befreien.
    """
    text = (text or "").strip()
    if not text:
        return "Fertig, aber ohne Zusammenfassung."

    for zeile in reversed(text.splitlines()):
        if zeile.strip().upper().startswith("GESPROCHEN:"):
            text = zeile.split(":", 1)[1]
            break
    else:
        # Kein Marker: der letzte zusammenhaengende Absatz ist die beste
        # Naeherung -- Aufzaehlungen davor faellt so von selbst weg.
        absaetze = [a.strip() for a in text.split("\n\n") if a.strip()]
        text = absaetze[-1] if absaetze else text

    return _glatt(text) or "Fertig, aber ohne Zusammenfassung."


def bericht_kurz(text: str) -> str:
    """Aus einem bericht.md ein paar vorlesbare Saetze machen.

    Der Bericht ist zum Lesen geschrieben, nicht zum Hoeren:
    Ueberschriften, Trennlinien, Codebloecke. Vorgelesen taugt davon nur
    der Fliesstext -- eine Ueberschrift klingt gesprochen wie ein
    abgerissener Halbsatz mitten im Vortrag. Deshalb fliegen
    Ueberschriften und Trennlinien vorher raus; Aufzaehlungspunkte
    bleiben, denn sie sind meist ganze Saetze.

    Gekuerzt wird hart bei 500 Zeichen. Das ist kein Bericht mehr,
    sondern ein Anfang -- und genau als solcher wird er auch angesagt.
    """
    behalten = []
    im_block = False
    for zeile in (text or "").splitlines():
        blank = zeile.strip()
        if blank.startswith("```"):
            im_block = not im_block
            continue
        if im_block or blank.startswith("#"):
            continue
        if blank and set(blank) <= set("-=_| "):   # Trenn- und Tabellenlinien
            continue
        behalten.append(zeile)
    return _glatt("\n".join(behalten), 500)


@dataclass
class Auftrag:
    nummer: int
    projekt: str
    was: str
    zweig: str
    ordner: Path
    status: str = "läuft"          # läuft | fertig | fehler | abgebrochen
    begonnen: datetime = field(default_factory=datetime.now)
    beendet: datetime | None = None
    ergebnis: str = ""
    aufgabe: object = None
    stand_text: str = ""           # wie weit er kam, aus Git gelesen
    # Die Kennung der Claude-Sitzung. Wird VOR dem Start vergeben und
    # gesichert -- sonst waere ein Absturz nach zwei Sekunden nicht
    # fortsetzbar, weil die Kennung erst am Ende zurueckkaeme.
    sitzung: str = ""
    zuletzt_gesehen: str = ""      # ISO-Zeit des letzten Lebenszeichens
    # Soll beim Losschicken an die alte Sitzung angeknuepft werden?
    fortsetzen: bool = False
    # Der Zweig, von dem abgespalten wurde. Gemessen: Beide Projekte
    # unter D:/Projekte heissen ihren Basiszweig "master", stand() hat
    # aber gegen "main" verglichen -- git brach mit "ambiguous argument"
    # ab und jeder unterbrochene Auftrag meldete "noch kein Commit".
    basis: str = ""
    # Modellzuege in diesem Lauf (fuer den Fortschrittsbalken der App).
    # Zaehlt ab dem letzten Start/Fortsetzen -- das Pensum auch.
    schritte: int = 0

    def dauer(self) -> int:
        ende = self.beendet or datetime.now()
        return int((ende - self.begonnen).total_seconds())


def journal(nummer: int, ereignis: str, **felder) -> None:
    """Eine Zeile ans Fortschritts-Journal anhaengen.

    Anhaengen statt Ueberschreiben ist der ganze Trick: Stirbt der
    Prozess mitten im Schreiben, ist hoechstens die letzte Zeile
    zerrissen -- alles davor bleibt gueltig und lesbar. Beim
    Ueberschreiben einer JSON-Datei ist dagegen im schlimmsten Fall
    ALLES weg, weil das Schreiben mit einem Kuerzen auf null Bytes
    beginnt.
    """
    zeile = {"zeit": datetime.now().isoformat(timespec="seconds"),
             "nummer": nummer, "ereignis": ereignis, **felder}
    try:
        with open(config.AUFTRAG_JOURNAL, "a", encoding="utf-8") as f:
            f.write(json.dumps(zeile, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        pass          # ein fehlendes Journal darf keinen Auftrag aufhalten


def journal_lesen() -> list:
    """Alle lesbaren Zeilen. Kaputte werden uebersprungen, nicht beklagt."""
    zeilen = []
    try:
        roh = config.AUFTRAG_JOURNAL.read_text(encoding="utf-8").splitlines()
    except OSError:
        return zeilen
    for z in roh:
        z = z.strip()
        if not z:
            continue
        try:
            zeilen.append(json.loads(z))
        except ValueError:
            continue   # abgerissene letzte Zeile eines Absturzes
    return zeilen


def _atomar_schreiben(pfad, text: str) -> None:
    """Datei ersetzen, ohne sie je halb dastehen zu lassen.

    Erst in eine Nebendatei IM SELBEN ORDNER schreiben (sonst waere das
    Ersetzen ein Kopiervorgang ueber Laufwerksgrenzen), auf die Platte
    zwingen, dann tauschen.

    Die Wiederholungsschleife ist keine Ziererei: Unter Windows wirft das
    Ersetzen PermissionError, wenn irgendwer die Zieldatei gerade offen
    hat -- ein Virenscanner, der die frisch geschriebene Datei prueft,
    genuegt. Unter Linux liefe derselbe Aufruf klaglos durch.
    """
    pfad = Path(pfad)
    fd, tmp = tempfile.mkstemp(dir=str(pfad.parent), prefix=pfad.name + ".",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        for versuch in range(5):
            try:
                os.replace(tmp, pfad)
                return
            except PermissionError:
                if versuch == 4:
                    raise
                time.sleep(0.02 * (versuch + 1))
    finally:
        try:
            Path(tmp).unlink()
        except OSError:
            pass


class Werkstatt:
    """Haelt die laufenden Auftraege und startet die Arbeiter."""

    def __init__(self, sagen=None, melden=None, leuchten=None):
        self.sagen = sagen        # Sarvis meldet sich von selbst
        self.melden = melden      # Windows-Benachrichtigung
        self.leuchten = leuchten
        self.auftraege: dict[int, Auftrag] = {}
        self._naechste = 1
        self._laden()

    def _laden(self) -> None:
        """Was frueher lief, aus der Datei holen.

        auftraege.json wurde bisher nur geschrieben und nie gelesen. Zwei
        Folgen, beide unangenehm: Die Nummerierung fing nach jedem Start
        wieder bei 1 an und ueberschrieb beim naechsten Sichern die alten
        Eintraege -- und ein Auftrag, der beim Beenden noch lief, war
        spurlos weg.

        Er laeuft NICHT weiter: Der Arbeiter lebt im Prozess von Sarvis,
        und der ist beendet worden. Genau das muss man aber erfahren
        koennen, statt es aus einem Git-Zweig zu erraten. Deshalb wird
        "laeuft" beim Laden zu "unterbrochen".
        """
        try:
            roh = json.loads(config.AUFTRAG_DATEI.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            # Zerrissene oder leere Datei. Frueher hiess das: alle
            # Auftraege stillschweigend vergessen, samt Nummerierung.
            # Das Journal weiss es noch.
            print("  (auftraege.json unlesbar -- rekonstruiere aus dem Journal)")
            roh = self._aus_journal()
        if not isinstance(roh, list):
            return
        for e in roh:
            try:
                nummer = int(e["nummer"])
                a = Auftrag(
                    nummer=nummer,
                    projekt=str(e.get("projekt") or ""),
                    was=str(e.get("was") or ""),
                    zweig=str(e.get("zweig") or ""),
                    ordner=Path(str(e.get("ordner") or ".")),
                    status=str(e.get("status") or "fertig"),
                    begonnen=datetime.fromisoformat(e["begonnen"]),
                    beendet=(datetime.fromisoformat(e["beendet"])
                             if e.get("beendet") else None),
                )
            except (KeyError, TypeError, ValueError):
                continue
            a.sitzung = str(e.get("sitzung") or "")
            a.zuletzt_gesehen = str(e.get("zuletzt_gesehen") or "")
            a.basis = str(e.get("basis") or "")
            # Das Ergebnis lebte bisher nur im Arbeitsspeicher: Wer die
            # gesprochene Ansage verpasst hat, bekam sie nie wieder. Es
            # wird hier wie alle Zusatzfelder mit .get() geholt -- eine
            # auftraege.json von vor dieser Aenderung kennt das Feld nicht
            # und laedt trotzdem, sie hat dann eben ein leeres Ergebnis.
            a.ergebnis = str(e.get("ergebnis") or "")
            if a.status == "läuft":
                a.status = "unterbrochen"
                a.beendet = a.beendet or datetime.now()
                journal(nummer, "unterbrochen",
                        grund="Sarvis wurde neu gestartet")
            self.auftraege[nummer] = a
            self._naechste = max(self._naechste, nummer + 1)
        # Fuer die Unterbrochenen einmal nachsehen, wie weit sie kamen.
        # Nur fuer die -- Git zu befragen kostet Zeit, und bei fertigen
        # Auftraegen ist die Antwort ohne Wert.
        for a in self.auftraege.values():
            if a.status == "unterbrochen":
                try:
                    a.stand_text = self.stand(a)
                except Exception:
                    a.stand_text = ""

    @staticmethod
    def _aus_journal() -> list:
        """Aus dem Journal wieder eine Auftragsliste falten.

        Das Journal ist die Wahrheit ueber den Verlauf; auftraege.json
        ist nur die bequeme Zusammenfassung. Geht die kaputt, laesst sie
        sich hieraus neu bauen.
        """
        stand = {}
        for z in journal_lesen():
            nummer = z.get("nummer")
            if not isinstance(nummer, int):
                continue
            e = stand.setdefault(nummer, {"nummer": nummer, "status": "läuft"})
            for feld in ("projekt", "was", "zweig", "ordner", "sitzung",
                         "begonnen", "beendet", "status", "zuletzt_gesehen",
                         "basis", "ergebnis"):
                if z.get(feld):
                    e[feld] = z[feld]
            if z.get("ereignis") == "beendet":
                e["status"] = z.get("status", "fertig")
            elif z.get("ereignis") == "lebt":
                e["zuletzt_gesehen"] = z.get("zeit", "")
        return list(stand.values())

    def unterbrochene(self) -> list:
        """Auftraege, die ein Neustart mittendrin erwischt hat."""
        return [a for a in self.auftraege.values() if a.status == "unterbrochen"]

    # --- Erlaubnis des Arbeiters ------------------------------------------

    def _wachhund(self, ordner: Path):
        """Erlaubnispruefer fuer genau diesen Arbeiter.

        Bewusst selbst geschrieben statt ueber Musterregeln: Ich will
        genau wissen, was durchkommt. Der Ordner ist die Grenze.
        """
        wurzel = ordner.resolve()
        # Nur lesen: das Handbuch und die Werkstatt. Beide sind im
        # Container read-only eingehaengt -- auch ein Bash-Befehl, der dort
        # schreiben will, scheitert also am Dateisystem, nicht erst hier.
        lesewurzeln = [Path("/opt/handbuch"), Path("/opt/blender")]

        def lesbar(pfad: str) -> bool:
            if innerhalb(pfad):
                return True
            # Nur absolute Pfade: Relatives meint den Projektordner und
            # ist oben schon entschieden.
            try:
                p = Path(pfad)
                if not p.is_absolute():
                    return False
                p = p.resolve()
            except (OSError, ValueError):
                return False
            return any(p == w or w in p.parents for w in lesewurzeln)

        def innerhalb(pfad: str) -> bool:
            try:
                p = Path(pfad)
                p = p if p.is_absolute() else (wurzel / p)
                p = p.resolve()
            except (OSError, ValueError):
                return False
            return p == wurzel or wurzel in p.parents

        async def darf(name: str, eingabe: dict, zusammenhang):
            if name not in ARBEITER_WERKZEUGE:
                return PermissionResultDeny(
                    message=f"{name} ist für diesen Auftrag nicht freigegeben."
                )

            if name in ("Write", "Edit", "NotebookEdit"):
                ziel = eingabe.get("file_path") or eingabe.get("path") or ""
                if not innerhalb(str(ziel)):
                    return PermissionResultDeny(
                        message="Außerhalb des Projektordners wird nicht "
                                "geschrieben."
                    )
                return PermissionResultAllow()

            if name in ("Read", "Glob", "Grep"):
                # Lesen ist keine Handlung, aber ein Abfluss: Was der
                # Arbeiter liest, landet in seinem Kontext und geht damit
                # nach draussen. Ohne diese Sperre koennte er die .env mit
                # den Telegram-Zugangsdaten oeffnen. Fehlt der Pfad, meint
                # das Werkzeug ohnehin den Projektordner.
                #
                # Geprueft wurde hier frueher nur, wenn der Pfad absolut
                # war. Der Arbeiter laeuft aber mit cwd = Projektordner:
                # Grep(path="../..") oder Glob(pattern="../../**/.env")
                # sind relativ, die Bedingung fiel komplett aus, und die
                # .env stand im Kontext. innerhalb() loest Relatives seit
                # jeher gegen die Wurzel auf -- der Schreibzweig darueber
                # benutzt genau das. Und geprueft wird jedes Ortsfeld
                # einzeln: in der alten or-Kette gewann immer das erste
                # gesetzte, ein harmloses path="." deckte also ein
                # glob="../../**" zu.
                if name == "Grep":
                    felder = ("path", "glob")      # pattern ist ein Regex
                elif name == "Glob":
                    felder = ("path", "pattern")
                else:
                    felder = ("file_path", "path")
                for feld in felder:
                    ziel = str(eingabe.get(feld) or "")
                    if ziel and not lesbar(ziel):
                        return PermissionResultDeny(
                            message="Außerhalb des Projektordners wird nichts "
                                    "gelesen."
                        )
                return PermissionResultAllow()

            if name == "Bash":
                befehl = str(eingabe.get("command") or "")
                for muster in VERBOTEN:
                    if re.search(muster, befehl, re.IGNORECASE):
                        return PermissionResultDeny(
                            message="Dieser Befehl ist gesperrt."
                        )
                # Pfade, die aus dem Projekt herausfuehren: nein.
                #
                # Die Erkennung kommt bewusst aus schutz.pfade_im_befehl
                # statt aus einem zweiten Regex hier. Der zweite war naemlich
                # stehengeblieben, als der erste um POSIX erweitert wurde --
                # er suchte weiter nur nach Laufwerksbuchstaben und fand auf
                # Linux gar nichts. Gemessen liefen dadurch alle diese
                # Befehle des Arbeiters ungeprueft durch:
                #     cat /etc/shadow
                #     cp /home/server3070/.ssh/id_ed25519 .
                #     docker run -v /:/host alpine cat /host/etc/shadow
                # Read/Write/Grep/Glob waren die ganze Zeit sauber begrenzt --
                # nur Bash, das Werkzeug mit der groessten Reichweite, nicht.
                # Eine Ortspruefung, zwei Regexe: einer davon veraltet still.
                for gefunden in schutz.pfade_im_befehl(befehl, str(wurzel)):
                    if not lesbar(gefunden):
                        return PermissionResultDeny(
                            message=f"{gefunden} liegt außerhalb des Projekts."
                        )
                return PermissionResultAllow()

            return PermissionResultAllow()

        return darf

    # --- Auftrag starten ---------------------------------------------------

    def starten(self, projekt: str, was: str) -> tuple[Auftrag | None, str]:
        # _finden statt _pfad: _pfad sieht nur im Sandkasten nach, es gibt
        # aber drei Orte (privat, arbeit, sandkasten). Ein Projekt, das
        # projekt_anlegen unter "arbeit" angelegt hat, war fuer
        # auftrag_geben damit unsichtbar.
        #
        # Gemessen am 2. September: Sascha bat darum, Herstellerdokumente
        # zu suchen und abzulegen. Sarvis legte das Projekt unter
        # "arbeit" an, versuchte dann sieben Mal einen Auftrag und bekam
        # sieben Mal "Dieses Projekt finde ich nicht" -- bei jedem
        # Versuch mit einer neuen Rueckfrage an Sascha.
        ordner, _ort = _finden(projekt)
        if ordner is None:
            return None, ("Dieses Projekt finde ich nicht — weder privat "
                          "noch unter Arbeit noch im Sandkasten.")

        laeuft = [a for a in self.auftraege.values()
                  if a.status == "läuft" and a.ordner == ordner]
        if laeuft:
            return None, (f"Im Projekt {ordner.name} läuft schon Auftrag "
                          f"{laeuft[0].nummer}. Erst den abwarten.")

        nummer = self._naechste
        self._naechste += 1
        zweig = f"sarvis/{nummer}-{re.sub(r'[^a-z0-9]+', '-', was.lower())[:28].strip('-')}"

        # Woher abgespalten wird, weiss nur dieser Moment: Nach dem
        # checkout -b ist HEAD der neue Zweig. Ohne diese Zeile musste
        # stand() den Basiszweig spaeter raten -- und riet "main", waehrend
        # die echten Projekte "master" heissen.
        basis = ""
        try:
            fertig = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                    cwd=ordner, capture_output=True, text=True,
                                    timeout=10)
            if fertig.returncode == 0 and fertig.stdout.strip() != "HEAD":
                basis = fertig.stdout.strip()   # "HEAD": abgeloester Kopf
        except (OSError, subprocess.SubprocessError):
            pass

        try:
            subprocess.run(["git", "checkout", "-q", "-b", zweig], cwd=ordner,
                           check=True, capture_output=True, timeout=30)
        except (subprocess.SubprocessError, OSError) as e:
            return None, f"Der Git-Zweig ließ sich nicht anlegen: {e}"

        # Die Sitzungskennung wird HIER vergeben, nicht vom SDK, und
        # steht damit in der Datei, bevor die erste Zeile Arbeit
        # existiert. Kaeme sie erst mit der Schlussmeldung zurueck, waere
        # ausgerechnet der abgebrochene Auftrag der einzige ohne Kennung
        # -- also der einzige, den man nicht fortsetzen kann.
        auftrag = Auftrag(nummer=nummer, projekt=ordner.name, was=was,
                          zweig=zweig, ordner=ordner, basis=basis,
                          sitzung=str(uuid.uuid4()))
        self.auftraege[nummer] = auftrag
        journal(nummer, "gestartet", projekt=ordner.name, was=was,
                zweig=zweig, ordner=str(ordner), sitzung=auftrag.sitzung,
                basis=basis,
                begonnen=auftrag.begonnen.isoformat(timespec="seconds"))
        self._sichern()          # erst festhalten, dann loslaufen
        # Hier stand create_task -- und diese Methode laeuft in einem
        # Worker-Thread (auftrag_geben ruft sie ueber to_thread auf,
        # damit das Gespraech waehrend der git-Aufrufe nicht steht). In
        # einem Thread gibt es keinen laufenden Event-Loop:
        # get_running_loop() warf "no running event loop", die Arbeit
        # wurde nie angeworfen -- aber der Auftrag stand zwei Zeilen
        # weiter oben schon als "läuft" in der Datei.
        #
        # Genau das war am 1. September zu sehen: Sarvis meldete einen
        # Fehler, auftrag_status meldete "läuft seit 6 Minuten", und
        # zuletzt_gesehen blieb leer -- weil nie jemand arbeitete.
        # auftrag_abbrechen fand dann kein aufgabe-Objekt, uebersprang
        # das Abbrechen und meldete trotzdem Erfolg.
        #
        # Das Anwerfen gehoert deshalb in den Event-Loop: losschicken().
        return auftrag, ""

    def losschicken(self, auftrag) -> str:
        """Die Arbeit wirklich anwerfen. MUSS im Event-Loop laufen.

        Getrennt von starten(), weil das im Worker-Thread laeuft und dort
        keine Aufgabe erzeugt werden kann. Rueckgabe: leer, wenn es
        klappte, sonst der Fehler -- und dann steht der Auftrag auch
        nicht faelschlich als laufend in der Datei.
        """
        try:
            auftrag.aufgabe = asyncio.get_running_loop().create_task(
                self._arbeiten(auftrag, fortsetzen=auftrag.fortsetzen)
            )
            return ""
        except RuntimeError as e:
            auftrag.status = "fehler"
            auftrag.ergebnis = f"Ließ sich nicht starten: {e}"
            auftrag.beendet = datetime.now()
            journal(auftrag.nummer, "beendet", status="fehler",
                    ergebnis=auftrag.ergebnis)
            self._sichern()
            return auftrag.ergebnis

    def stand(self, auftrag) -> str:
        """Wie weit ist der Auftrag wirklich gekommen? Aus Git, nicht aus Absicht.

        Nach einem Abbruch ist das Protokoll eine Behauptung, der Zweig
        eine Tatsache. Deshalb wird hier nachgesehen und nicht geraten.
        """
        def git(*args):
            """None heisst "git hat nicht geantwortet", "" heisst "nichts".

            Frueher war beides "" -- ein Fehlschlag sah aus wie ein leeres
            Ergebnis, und genau das kam hier vor.
            """
            try:
                e = subprocess.run(["git", *args], cwd=auftrag.ordner,
                                   capture_output=True, text=True, timeout=10)
                return e.stdout.strip() if e.returncode == 0 else None
            except (OSError, subprocess.SubprocessError):
                return None

        basis = auftrag.basis
        if not basis:
            # Auftraege von vor dem basis-Feld: nachsehen statt raten.
            for kandidat in ("master", "main"):
                if git("rev-parse", "--verify", "-q", kandidat) is not None:
                    basis = kandidat
                    break
        protokoll = git("log", auftrag.zweig, "--not", basis or "HEAD",
                        "--oneline")
        commits = [z for z in (protokoll or "").splitlines() if z.strip()]
        offen = [z for z in (git("status", "--porcelain") or "").splitlines()
                 if z.strip()]
        teile = []
        if protokoll is None:
            teile.append("wie weit er kam, konnte ich nicht ermitteln")
        elif commits:
            # Einzahl mitfuehren: "1 Commits" faellt beim Lesen nicht
            # auf, beim VORLESEN sofort.
            wort = "Commit" if len(commits) == 1 else "Commits"
            teile.append(
                f"{len(commits)} {wort}, zuletzt: {commits[0][:60]}")
        else:
            teile.append("noch kein Commit")
        if offen:
            teile.append(f"{len(offen)} Dateien ungespeichert geändert")
        fortschritt = auftrag.ordner / "fortschritt.md"
        if fortschritt.exists():
            try:
                letzte = [z for z in fortschritt.read_text(
                    encoding="utf-8", errors="replace").splitlines() if z.strip()]
                if letzte:
                    teile.append("zuletzt notiert: " + letzte[-1][:80])
            except OSError:
                pass
        return "; ".join(teile)

    def einzelstand(self, nummer) -> tuple[str, bool]:
        """Ein Auftrag, mit dem inhaltlichen Stand aus dem Projekt.

        Warum der teure Teil NUR hier laeuft und nicht in uebersicht():
        stand() startet bis zu vier Git-Prozesse mit je zehn Sekunden
        Zeitlimit und liest fortschritt.md dazu. Die Uebersicht
        beantwortet "was laeuft gerade?" -- eine Frage, die oft kommt und
        sofort beantwortet sein will; bei zehn Auftraegen waeren das
        vierzig Git-Aufrufe fuer eine Antwort, die in der Liste ohnehin
        schon steht. "Wie weit ist Auftrag drei?" ist die andere Frage:
        Sie nennt eine Nummer, sie meint den Inhalt, und fuer die eine
        Antwort ist ein Git-Aufruf sein Geld wert.

        Nachgesehen wird nur bei laufenden und unterbrochenen Auftraegen.
        Bei einem fertigen ist der Zweig endgueltig, aber uninteressant --
        da zaehlt das Ergebnis, und das holt auftrag_ergebnis.
        """
        try:
            a = self.auftraege.get(int(nummer or 0))
        except (TypeError, ValueError):
            a = None
        if a is None:
            return "Diesen Auftrag kenne ich nicht.", True

        minuten = max(1, a.dauer() // 60)
        if a.status == "läuft":
            satz = (f"Auftrag {a.nummer} im Projekt {a.projekt} läuft seit "
                    f"{minuten} Minuten, auf dem Zweig {a.zweig}.")
        else:
            satz = (f"Auftrag {a.nummer} im Projekt {a.projekt} ist "
                    f"{a.status}, nach {minuten} Minuten, auf dem Zweig "
                    f"{a.zweig}.")

        if a.status in ("läuft", "unterbrochen"):
            try:
                a.stand_text = self.stand(a)
            except Exception:
                a.stand_text = ""
            # rstrip: Die letzte Notiz aus fortschritt.md bringt ihren
            # eigenen Punkt mit -- ohne das endet der Satz auf "..".
            satz += (f" Stand im Projekt: {a.stand_text.rstrip('. ')}."
                     if a.stand_text
                     else " Wie weit er inhaltlich ist, konnte ich nicht "
                          "ermitteln.")
        elif a.ergebnis:
            satz += " Das Ergebnis kann ich noch einmal vorlesen."
        return satz, False

    def bericht(self, auftrag) -> str:
        """Den bericht.md dieses Auftrags holen. Leerer String, wenn keiner da ist.

        Zwei Wege, und die Reihenfolge hat einen Grund. Zuerst `git show
        zweig:bericht.md`: Das liest aus dem Zweig und funktioniert auch
        dann noch, wenn im Ordner laengst wieder master ausgecheckt ist.

        Dann erst die Platte -- denn der Arbeiter schreibt den Bericht als
        LETZTES, oft ohne ihn noch zu committen; dann kennt der Zweig ihn
        gar nicht. Gelesen wird von der Platte aber nur, wenn dort auch
        wirklich dieser Zweig steht. Sonst laese man den Bericht eines
        fremden Standes vor und gaebe ihn als den eigenen aus.
        """
        ordner = Path(auftrag.ordner)
        if not auftrag.zweig or not ordner.exists():
            return ""

        def git(*args):
            try:
                e = subprocess.run(["git", *args], cwd=ordner,
                                   capture_output=True, text=True, timeout=10,
                                   encoding="utf-8", errors="replace")
                return e.stdout if e.returncode == 0 else None
            except (OSError, subprocess.SubprocessError):
                return None

        aus_zweig = git("show", f"{auftrag.zweig}:bericht.md")
        if aus_zweig and aus_zweig.strip():
            return aus_zweig

        kopf = git("rev-parse", "--abbrev-ref", "HEAD")
        if kopf is None or kopf.strip() != auftrag.zweig:
            return ""
        try:
            return (ordner / "bericht.md").read_text(encoding="utf-8",
                                                     errors="replace")
        except OSError:
            return ""

    def ergebnis_von(self, nummer) -> tuple[str, bool]:
        """Die Schlussansage eines abgeschlossenen Auftrags -- noch einmal."""
        try:
            a = self.auftraege.get(int(nummer or 0))
        except (TypeError, ValueError):
            a = None
        if a is None:
            return "Diesen Auftrag kenne ich nicht.", True
        if a.status == "läuft":
            return (f"Auftrag {a.nummer} läuft noch. Ein Ergebnis gibt es "
                    "erst, wenn er fertig ist -- wie weit er ist, kann ich "
                    "dir aber sagen."), False

        minuten = max(1, a.dauer() // 60)
        if a.ergebnis:
            return (f"Auftrag {a.nummer} im Projekt {a.projekt}, {a.status} "
                    f"nach {minuten} Minuten. {a.ergebnis}"), False

        # Kein gespeichertes Ergebnis. Zwei Faelle: ein Auftrag von vor
        # dieser Aenderung, oder einer, der abgebrochen wurde, bevor er
        # etwas sagen konnte. In beiden Faellen ist der bericht.md auf dem
        # Zweig das Einzige, was von der Arbeit uebrig ist -- ihn nicht zu
        # lesen und stattdessen "weiss ich nicht mehr" zu antworten waere
        # bequem und falsch. Vorgelesen wird er als das, was er ist: ein
        # Anfang, kein Ergebnis.
        kurz = bericht_kurz(self.bericht(a))
        if kurz:
            return (f"Von Auftrag {a.nummer} habe ich keine gesprochene "
                    f"Zusammenfassung mehr, aber den Bericht auf dem Zweig "
                    f"{a.zweig}. Er beginnt so: {kurz}"), False
        return (f"Von Auftrag {a.nummer} habe ich weder eine Zusammenfassung "
                f"noch einen Bericht. Nachsehen kannst du auf dem Zweig "
                f"{a.zweig}."), False

    def _stand_zeigen(self, auftrag: Auftrag, zustand: str = "läuft",
                      schluss: str = "") -> None:
        """Die Statuskarte des Auftrags im Verlauf -- neu oder aktualisiert.

        Seit 13.11.2026. Vorher sah man nach einer Stunde Abwesenheit
        einen einzigen Satz und wusste nicht, was gerade passiert.
        """
        try:
            from .. import anzeige as anzeige_modul
            erledigt, naechstes = _stand_lesen(auftrag.ordner)
            minuten = max(1, auftrag.dauer() // 60)
            kopf = (f"Auftrag {auftrag.nummer} · {auftrag.projekt} · "
                    + (f"läuft seit {minuten} Min." if zustand == "läuft"
                       else f"{zustand} nach {minuten} Min."))
            zeilen = [kopf, "Aufgabe: " + _satzweise(auftrag.was, 160)]
            if erledigt:
                zeilen.append("Zuletzt erledigt: " + erledigt)
            if naechstes and zustand == "läuft":
                zeilen.append("Als Nächstes: " + naechstes)
            if schluss:
                zeilen.append(schluss)
            anzeige_modul.aktuelle().auftrag_stand(
                auftrag.nummer, "\n".join(zeilen), zustand, auftrag.projekt,
                seit=auftrag.begonnen.timestamp(),
                schritte=auftrag.schritte, pensum=config.AUFTRAG_ZUEGE)
        except Exception as e:
            print(f"  (Auftragsstand nicht gezeigt: {e})")

    async def _arbeiten(self, auftrag: Auftrag, fortsetzen: bool = False) -> None:
        klient = None
        letztes_werkzeug = ""
        letztes_zeichen = time.monotonic()
        self._stand_zeigen(auftrag)
        try:
            klient = ClaudeSDKClient(options=ClaudeAgentOptions(
                model=config.MODELL,
                system_prompt=ARBEITER_PROMPT,
                cwd=str(auftrag.ordner),
                # Kein Arbeiter plant Dinge fuer spaeter -- siehe hirn.py.
                disallowed_tools=list(config.PLANUNG_GESPERRT),
                allowed_tools=[],                 # nichts vorab genehmigen --
                can_use_tool=self._wachhund(auftrag.ordner),   # alles prüfen
                permission_mode="default",
                setting_sources=[],
                mcp_servers={},
                strict_mcp_config=True,
                effort="high",       # anders als Sarvis: hier zählt Gründlichkeit
                max_turns=config.AUFTRAG_ZUEGE,
                # Standard ist 1 MB je Nachricht. Liest der Arbeiter einen
                # Screenshot (base64), reisst das sofort -- so ist Auftrag 4
                # (Portfolio, 12.11.2026) gescheitert.
                max_buffer_size=32 * 1024 * 1024,
                # Beim ersten Lauf die Kennung VORGEBEN, beim Fortsetzen
                # dieselbe wieder aufnehmen. Gemessen: Der Arbeiter hat
                # danach seinen eigenen Verlauf zurueck.
                **({"resume": auftrag.sitzung} if fortsetzen
                   else {"session_id": auftrag.sitzung}),
            ))
            await klient.connect()
            if fortsetzen:
                await klient.query(
                    "Du wurdest mitten in der Arbeit unterbrochen. Sieh zuerst "
                    "nach, wie weit du gekommen bist (git log, git status, "
                    "fortschritt.md), und mach dann weiter. Fang NICHT von "
                    "vorn an.\n\n"
                    f"Ursprünglicher Auftrag: {auftrag.was}"
                )
            else:
                await klient.query(
                    f"Projekt: {auftrag.ordner}\nZweig: {auftrag.zweig}\n\n"
                    f"Auftrag: {auftrag.was}"
                )
            letzter = ""
            schluss = None
            auftrag.schritte = 0
            # Nach message_id zaehlen: Eine Modellantwort mit Text und
            # Werkzeugaufruf kommt als mehrere AssistantMessage an.
            gezaehlt: set = set()
            async for nachricht in klient.receive_response():
                if isinstance(nachricht, AssistantMessage):
                    mid = getattr(nachricht, "message_id", None) or id(nachricht)
                    if mid not in gezaehlt:
                        gezaehlt.add(mid)
                        auftrag.schritte += 1
                if hasattr(nachricht, "content"):
                    for block in getattr(nachricht, "content", []) or []:
                        if isinstance(block, TextBlock) and block.text.strip():
                            letzter = block.text.strip()
                        elif isinstance(block, ToolUseBlock):
                            letztes_werkzeug = block.name

                # Lebenszeichen ins Journal. Nicht als Stoppuhr, sondern
                # damit sich hinterher sagen laesst, wann er zuletzt
                # gesehen wurde -- und woran er da war.
                if (time.monotonic() - letztes_zeichen
                        >= config.AUFTRAG_LEBENSZEICHEN_SEK):
                    letztes_zeichen = time.monotonic()
                    auftrag.zuletzt_gesehen = datetime.now().isoformat(
                        timespec="seconds")
                    journal(auftrag.nummer, "lebt", werkzeug=letztes_werkzeug)
                    self._stand_zeigen(auftrag)
                if isinstance(nachricht, ResultMessage):
                    schluss = nachricht
                    break
            # Ein API-Fehler (Anmeldung, 403, Ueberlast) kommt NICHT als
            # Ausnahme, sondern als normale Schlussnachricht mit is_error.
            # Bis 13.11.2026 hiess das "fertig": Auftrag 5 meldete nach
            # einer Minute "ist fertig ... Failed to authenticate. API
            # Error: 403 ... Soll ich es dir zeigen?" -- und Sascha
            # wusste nicht, was er gefragt wird.
            fehlgeschlagen = bool(getattr(schluss, "is_error", False)) or (
                re.match(r"(Failed to authenticate|API Error)", letzter or "")
                is not None)
            if getattr(schluss, "subtype", "") == "error_max_turns":
                # Kein Fehler im eigentlichen Sinn: Das Arbeitspensum ist
                # aufgebraucht, der Stand liegt committet im Zweig.
                # Gemessen 13.11.: Auftrag 6 meldete stattdessen seinen
                # letzten Halbsatz ("Jetzt die Stationsanzeige und die
                # App:") als Fehlergrund.
                auftrag.status = "fehler"
                auftrag.ergebnis = (
                    f"Er hat sein Arbeitspensum von {config.AUFTRAG_ZUEGE} "
                    "Schritten aufgebraucht und ist mittendrin stehen "
                    "geblieben. Der Zwischenstand ist gespeichert, er kann "
                    "an derselben Stelle weitermachen. Soll ich ihn "
                    "fortsetzen?")
            elif fehlgeschlagen:
                auftrag.status = "fehler"
                auftrag.ergebnis = (letzter or str(
                    getattr(schluss, "result", "") or "unbekannter Fehler"))[:300]
            else:
                auftrag.ergebnis = vorlesbar(letzter)
                auftrag.status = "fertig"
        except asyncio.CancelledError:
            auftrag.status = "abgebrochen"
            # Hier und nicht ueber _melden: Das 'raise' beendet die
            # Aufgabe, die Zeile hinter dem finally wird nie erreicht --
            # und ein 'await' in einer gecancelten Aufgabe bricht sofort
            # wieder ab. Nur die Benachrichtigung, keine Ansage: Nach
            # einem "Stopp" will niemand noch etwas hoeren, aber der
            # Zweigname soll nachlesbar stehenbleiben.
            if self.melden is not None:
                self.melden("Auftrag abgebrochen",
                            f"Zweig {auftrag.zweig} · Stand in bericht.md")
            raise
        except Exception as e:
            auftrag.status = "fehler"
            auftrag.ergebnis = f"{type(e).__name__}: {e}"
        finally:
            auftrag.beendet = datetime.now()
            # Das Ergebnis kommt mit ins Journal, nicht nur in die
            # auftraege.json: Geht die kaputt, baut _aus_journal() den
            # Stand daraus neu -- und ohne diese Zeile waere dabei
            # ausgerechnet das verloren, was der Mensch hoeren will.
            journal(auftrag.nummer, "beendet", status=auftrag.status,
                    ergebnis=auftrag.ergebnis[:600],
                    beendet=auftrag.beendet.isoformat(timespec="seconds"))
            if klient is not None:
                try:
                    await klient.disconnect()
                except Exception:
                    pass
            self._sichern()

        await self._melden(auftrag)

    async def _melden(self, auftrag: Auftrag) -> None:
        minuten = max(1, auftrag.dauer() // 60)
        self._stand_zeigen(
            auftrag,
            {"fertig": "fertig", "abgebrochen": "abgebrochen"}.get(
                auftrag.status, "gestoppt"),
            "" if auftrag.status == "fertig"
            else _satzweise(auftrag.ergebnis, 300))
        if auftrag.status == "fertig":
            kurz = _satzweise(auftrag.ergebnis, 400)
            fragen = offene_fragen(auftrag.ordner)
            if fragen:
                # Seit 13.11.2026: Die Fragen des Arbeiters standen nur im
                # Bericht, und niemand stellte sie. Jetzt liegen sie als
                # Formular im Verlauf.
                from .. import anzeige as anzeige_modul
                anzeige_modul.aktuelle().formular(
                    f"auftrag-{auftrag.nummer}-fragen",
                    f"Fragen zu Auftrag {auftrag.nummer} ({auftrag.projekt})",
                    fragen, auftrag.nummer, auftrag.projekt)
                frage_satz = (f" Er hat {len(fragen)} "
                              f"{'Frage' if len(fragen) == 1 else 'Fragen'} "
                              "an dich. Ich habe sie dir als Formular "
                              "hingelegt, füll es aus, dann geht es weiter.")
            else:
                frage_satz = " Soll ich es dir zeigen?"
            text = (f"Auftrag {auftrag.nummer} im Projekt {auftrag.projekt} "
                    f"ist fertig, nach {minuten} Minuten. {kurz}"
                    + frage_satz)
            titel = f"Auftrag fertig: {auftrag.projekt}"
        elif auftrag.status == "abgebrochen":
            text = f"Auftrag {auftrag.nummer} wurde abgebrochen."
            titel = "Auftrag abgebrochen"
        else:
            text = (f"Auftrag {auftrag.nummer} im Projekt {auftrag.projekt} "
                    f"ist gescheitert. {auftrag.ergebnis[:200]}")
            titel = f"Auftrag gescheitert: {auftrag.projekt}"

        if self.melden is not None:
            # Seit 11.11.2026 geht das auch als Web Push aufs Handy
            # (main._benachrichtigen). Auf einem Sperrbildschirm sagt
            # "Zweig x · Bericht in bericht.md" nichts -- der erste Satz
            # des Ergebnisses sagt, was los ist. Der Zweig bleibt dahinter.
            erster = " ".join((auftrag.ergebnis or "").split())[:160]
            self.melden(titel, (f"{erster} · " if erster else "")
                        + f"Zweig {auftrag.zweig}")
        if self.sagen is not None:
            await self.sagen(text)

    # --- Zustand ------------------------------------------------------------

    def fortsetzen(self, nummer: int) -> tuple:
        """Einen unterbrochenen Auftrag da weitermachen lassen, wo er war.

        Bewusst NUR auf Ansage. Kein System, das ich gefunden habe, nimmt
        so etwas von allein wieder auf -- und das aus gutem Grund: Der
        Arbeiter wuerde auf seinem eigenen halbfertigen Stand
        weiterbauen, ohne dass jemand ihn gesehen hat.
        """
        a = self.auftraege.get(int(nummer or 0))
        if a is None:
            return None, "Diesen Auftrag kenne ich nicht."
        if a.status not in ("unterbrochen", "fehler", "abgebrochen"):
            return None, f"Auftrag {a.nummer} ist {a.status} -- da gibt es nichts fortzusetzen."
        if not a.sitzung:
            return None, ("Von diesem Auftrag habe ich keine Sitzungskennung. "
                          "Er stammt noch aus der Zeit davor -- ich kann nur "
                          "einen neuen anlegen.")
        if not a.ordner.exists():
            return None, f"Den Projektordner {a.ordner} gibt es nicht mehr."

        a.status = "läuft"
        a.beendet = None
        journal(a.nummer, "fortgesetzt", sitzung=a.sitzung)
        self._sichern()
        # Auch hier NICHT create_task: fortsetzen() wird ebenfalls ueber
        # to_thread gerufen. Siehe die lange Begruendung in starten().
        a.fortsetzen = True
        return a, ""

    async def abbrechen(self, a) -> tuple[bool, str]:
        """Anhalten, warten, NACHSEHEN. Rueckgabe: (wirklich weg?, Text).

        Die drei Schritte sind der ganze Punkt. Vorher wurde nur der
        erste getan und der dritte behauptet.

        Fall eins: Es lief nie etwas. Genau das war am 1. September der
        Zustand -- die Aufgabe wurde wegen "no running event loop" nie
        erzeugt, der Auftrag stand aber als "läuft" in der Datei. Dann
        gibt es nichts abzubrechen, wohl aber einen Eintrag geradezu-
        ruecken. Und das gehoert gesagt, nicht verschwiegen: Wer denkt,
        er habe etwas gestoppt, sieht nicht nach.

        Fall zwei: Es laeuft wirklich. cancel() wirkt erst, wenn die
        Aufgabe das naechste Mal wartet. Deshalb eine kurze Frist -- und
        wenn sie verstreicht, wird das gemeldet, statt Erfolg zu
        behaupten.
        """
        if a.status == "unterbrochen":
            # Ein Neustart hat ihn erwischt; es laeuft nichts, was man
            # anhalten koennte. Zu tun ist nur das, was bisher fehlte:
            # den Zustand raeumen, damit die Vorspannzeile verschwindet
            # und nicht weiter jeden Zuruf mit derselben Frage belegt.
            a.status = "abgebrochen"
            a.beendet = datetime.now()
            journal(a.nummer, "beendet", status="abgebrochen",
                    ergebnis="Vom Nutzer verworfen.")
            self._sichern()
            return True, (f"Auftrag {a.nummer} ist verworfen, ich frage "
                          f"nicht mehr danach. Der Zweig {a.zweig} bleibt "
                          "stehen — sag Bescheid, wenn er auch weg soll.")

        if a.aufgabe is None or a.aufgabe.done():
            a.status = "abgebrochen"
            a.beendet = datetime.now()
            journal(a.nummer, "beendet", status="abgebrochen",
                    ergebnis="Es lief nichts -- Eintrag berichtigt.")
            self._sichern()
            return True, (f"Auftrag {a.nummer} steht jetzt auf abgebrochen. "
                          "Gearbeitet hat daran allerdings nie jemand — der "
                          "Eintrag stand nur so in der Liste. Der Zweig "
                          f"{a.zweig} bleibt.")

        a.aufgabe.cancel()
        await asyncio.wait([a.aufgabe],
                           timeout=config.AUFTRAG_ABBRUCH_FRIST_SEK)
        if not a.aufgabe.done():
            return False, (f"Auftrag {a.nummer} reagiert nicht auf den "
                           f"Abbruch. Er läuft noch. Ich fasse nach.")
        if a.status == "läuft":          # sollte _arbeiten gesetzt haben
            a.status = "abgebrochen"
            a.beendet = datetime.now()
            self._sichern()
        return True, (f"Auftrag {a.nummer} ist gestoppt, nachgesehen. "
                      f"Der Zweig {a.zweig} bleibt.")

    def alles_abbrechen(self) -> int:
        """Jeden laufenden Auftrag anhalten. Rueckgabe: wie viele es waren.

        Fuer das gesprochene "Stopp". Ueber auftrag_abbrechen muesste
        Sarvis erst die Nummer nennen -- und dazu das Hirn fragen, das
        genau in diesem Moment nicht mehr gefragt werden soll.
        """
        n = 0
        for a in self.auftraege.values():
            if a.status == "läuft" and a.aufgabe is not None and not a.aufgabe.done():
                a.aufgabe.cancel()
                n += 1
        return n

    def _sichern(self) -> None:
        try:
            _atomar_schreiben(config.AUFTRAG_DATEI, json.dumps([
                {"nummer": a.nummer, "projekt": a.projekt, "was": a.was,
                 "zweig": a.zweig, "status": a.status,
                 "ordner": str(a.ordner),
                 "basis": a.basis,
                 "sitzung": a.sitzung,
                 "zuletzt_gesehen": a.zuletzt_gesehen,
                 # Ohne dieses Feld ueberlebte die Ansage keinen Neustart.
                 # Es ist bereits durch vorlesbar() gegangen und damit
                 # kurz -- nur der Fehlerfall schreibt hier eine rohe
                 # Ausnahme hinein, deshalb die Grenze.
                 "ergebnis": a.ergebnis[:600],
                 "begonnen": a.begonnen.isoformat(),
                 "beendet": a.beendet.isoformat() if a.beendet else None}
                for a in self.auftraege.values()
            ], ensure_ascii=False, indent=1))
        except OSError:
            pass

    def laufende_kurz(self) -> list:
        """Was gerade arbeitet -- kurz genug fuer die Anzeige."""
        return [f"Auftrag {a.nummer}: {a.projekt}"
                for a in sorted(self.auftraege.values(), key=lambda x: x.nummer)
                if a.status == "läuft"]

    def uebersicht(self) -> list[str]:
        if not self.auftraege:
            return []
        zeilen = []
        for a in sorted(self.auftraege.values(), key=lambda x: -x.nummer)[:10]:
            dauer = f"{max(1, a.dauer() // 60)} min"
            zeilen.append(
                f"Auftrag {a.nummer} · {a.projekt} · {a.status} · {dauer}"
                f" · Zweig {a.zweig} · {a.was[:60]}"
            )
        return zeilen


def werkzeuge(werkstatt: Werkstatt, protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    @tool(
        "auftrag_geben",
        "Lässt im Hintergrund an einem Projekt arbeiten und meldet sich von "
        "selbst, wenn es fertig ist. Für alles, was länger dauert als eine "
        "Antwort: Funktion einbauen, Fehler suchen, umbauen. Der Auftrag "
        "sollte so ausformuliert sein, dass jemand ohne Vorwissen ihn "
        "versteht — der Arbeiter kennt euer Gespräch nicht. "
        "VORHER ERFRAGEN: Der Arbeiter kann niemanden fragen. Braucht die "
        "Arbeit Angaben, die nur der Nutzer kennt — Name, Anschrift, "
        "E-Mail, Telefon, Impressum, Zugangsdaten-Orte, Wunschtexte, "
        "Farben, Vorbilder —, dann frag sie im Gespräch ab, BEVOR du den "
        "Auftrag gibst, und schreib sie in den Auftrag. Kurz und gebündelt "
        "in einer Frage. Bei Webseiten zusätzlich fragen, ob es ein "
        "Vorbild oder eine Stimmung gibt. Sagt der Nutzer 'weiß ich noch "
        "nicht', dann bleibt es offen — aber gefragt wird. "
        "Dieses Werkzeug fragt NICHT mehr nach — benutze es nur, wenn der "
        "Nutzer die Arbeit ausdrücklich will ('mach', 'bau', 'starte', "
        "'kannst du … erstellen'). Ist unklar, ob er nur laut denkt, frag "
        "im Gespräch. "
        "LÄUFT SCHON EIN AUFTRAG im selben Projekt, wird dieser NICHT "
        "angenommen. Versprich dann nie, ihn 'danach anzuhängen' — das "
        "kannst du nicht. Sag ehrlich, dass er erst nach dem laufenden "
        "gestartet werden kann, und starte ihn, sobald die Fertigmeldung "
        "kommt und Sascha zustimmt. "
        "KEINE ANTWORT auf deine Rückfrage heißt NICHT 'abgelehnt': Sag "
        "später 'du hattest nicht bestätigt', nicht 'du hast abgelehnt'. "
        "DESIGN: Sagt Sascha 'meine Designvorgaben', 'mein Stil' oder "
        "'mein Design', meint er seinen Hausstil für Schaufenster-Seiten "
        "(dunkel, filmisch, ein Leitmotiv, eine Signalfarbe). Der liegt "
        "für den Arbeiter in /opt/handbuch/webseiten-design/SKILL.md — "
        "schreib in den Auftrag, dass er sich daran hält. Erfinde keinen "
        "eigenen Look und leite ihn nicht aus Screenshots ab. "
        "BILDER: Schickt Sascha Bilder für eine öffentliche Seite, frag "
        "nach, was sie zeigen, falls es nicht eindeutig ist — und weise "
        "ihn darauf hin, wenn Namen, Adressen oder Kundendaten darauf "
        "zu sehen sind.",
        {
            "type": "object",
            "properties": {
                "projekt": {"type": "string",
                            "description": "Projektname aus projekt_liste."},
                "was": {"type": "string",
                        "description": "Der Auftrag, ausformuliert und "
                                       "vollständig. Ruhig mehrere Sätze."},
                "dateien": {
                    "type": "array", "items": {"type": "string"},
                    "description": "Dateinamen aus dem Eingang (was der "
                                   "Nutzer geschickt hat, siehe "
                                   "eingang_zeigen), die der Arbeiter "
                                   "braucht. Der Arbeiter kommt an den "
                                   "Eingang NICHT heran — nur so bekommt "
                                   "er sie. Sie liegen dann im Projekt "
                                   "unter eingang/ (nicht in Git). Im "
                                   "Auftragstext auf eingang/ verweisen."},
            },
            "required": ["projekt", "was"],
        },
    )
    async def auftrag_geben(args):
        # to_thread, weil starten() zweimal git aufruft -- rev-parse mit
        # 10 s, checkout -b mit 30 s Zeitgrenze -- und dabei die
        # Auftragsdatei schreibt. Es laeuft INNERHALB von hirn.fragen(),
        # also auf demselben Event-Loop wie das Gespraech: Solange es
        # blockierte, stand alles. Keine Satzsynthese wurde angestossen,
        # der Not-Aus aus dem Tastaturfaden wurde nicht abgeholt, die
        # Hintergrundanzeige tickte nicht. Bei einem grossen Repository
        # mit vielen Arbeitskopie-Aenderungen ist das hoerbar.
        #
        # Genau das ist der Punkt von Weg A: Ein Auftrag soll das
        # Gespraech NICHT anhalten -- auch nicht fuer die Sekunden, die
        # sein Losschicken kostet.
        auftrag, fehler = await asyncio.to_thread(
            werkstatt.starten,
            (args.get("projekt") or "").strip(),
            (args.get("was") or "").strip(),
        )
        if auftrag is None:
            return {"content": [{"type": "text", "text": fehler}],
                    "is_error": True}
        # Mitgeschickte Dateien ins Projekt legen (13.11.2026): Auftrag 6
        # sollte Bilder aus dem Eingang einbauen und konnte sie nicht
        # einmal sehen -- der Eingang liegt ausserhalb seines Ordners.
        kopiert, fehlt = await asyncio.to_thread(
            _eingang_kopieren, auftrag.ordner, args.get("dateien") or [])
        # Erst HIER, im Event-Loop, faengt die Arbeit wirklich an.
        fehler = werkstatt.losschicken(auftrag)
        if fehler:
            return {"content": [{"type": "text", "text":
                    f"Auftrag {auftrag.nummer} ließ sich nicht starten: "
                    f"{fehler}"}], "is_error": True}
        if leuchten:
            leuchten("Aufträge")
        vermerken(f"auftrag_geben: Auftrag {auftrag.nummer} läuft im Projekt "
                  f"{auftrag.projekt} auf Zweig {auftrag.zweig}.")
        return {"content": [{"type": "text", "text":
                f"Auftrag {auftrag.nummer} läuft im Projekt "
                f"{auftrag.projekt}, auf dem Zweig {auftrag.zweig}. "
                + (f"{kopiert} Datei(en) liegen für ihn unter eingang/. "
                   if kopiert else "")
                + (f"Nicht gefunden im Eingang: {', '.join(fehlt)}. "
                   if fehlt else "")
                + "Ich melde mich, wenn er fertig ist."}]}

    @tool(
        "auftrag_status",
        "Sagt, welche Aufträge laufen oder gelaufen sind — mit Zweig und "
        "Dauer. Mit einer Nummer sieht Sarvis zusätzlich im Projekt nach, wie "
        "weit dieser eine Auftrag INHALTLICH ist: Commits, geänderte Dateien, "
        "letzte eigene Notiz. Für 'wie weit ist Auftrag drei?' also immer mit "
        "Nummer fragen.",
        {
            "type": "object",
            "properties": {
                "nummer": {"type": "integer",
                           "description": "Auftragsnummer. Weglassen für die "
                                          "Übersicht über alle."}
            },
        },
    )
    async def auftrag_status(args):
        nummer = args.get("nummer")
        if nummer not in (None, ""):
            # einzelstand() ruft stand(), und das sind bis zu vier
            # git-Aufrufe mit je 10 s Zeitgrenze.
            text, fehler = await asyncio.to_thread(
                werkstatt.einzelstand, nummer)
            antwort = {"content": [{"type": "text", "text": text}]}
            if fehler:
                antwort["is_error"] = True
            return antwort
        zeilen = await asyncio.to_thread(werkstatt.uebersicht)
        if not zeilen:
            return {"content": [{"type": "text", "text":
                    "Es läuft kein Auftrag und es lief auch keiner."}]}
        return {"content": [{"type": "text", "text": "\n".join(zeilen)}]}

    @tool(
        "auftrag_ergebnis",
        "Liest das Ergebnis eines abgeschlossenen Auftrags noch einmal vor — "
        "die Zusammenfassung, die der Arbeiter am Ende gemeldet hat. Für 'was "
        "kam bei Auftrag zwei heraus?' oder wenn die Ansage verpasst wurde. "
        "Fehlt die gespeicherte Zusammenfassung, wird der Bericht vom Zweig "
        "gelesen.",
        {
            "type": "object",
            "properties": {
                "nummer": {"type": "integer", "description": "Auftragsnummer."}
            },
            "required": ["nummer"],
        },
    )
    async def auftrag_ergebnis(args):
        # ergebnis_von() liest notfalls bericht.md vom Zweig -- git show.
        text, fehler = await asyncio.to_thread(
            werkstatt.ergebnis_von, args.get("nummer"))
        if fehler:
            return {"content": [{"type": "text", "text": text}],
                    "is_error": True}
        vermerken(f"auftrag_ergebnis: {text[:200]}")
        return {"content": [{"type": "text", "text": text}]}

    @tool(
        "auftrag_abbrechen",
        "Bricht einen laufenden Auftrag ab ODER verwirft einen, den ein "
        "Neustart unterbrochen hat. Für 'verwirf das', 'lass es', 'brauch "
        "ich nicht mehr' — auch wenn gerade niemand daran arbeitet. Was "
        "committet wurde, bleibt auf dem Zweig stehen; gelöscht wird nichts.",
        {
            "type": "object",
            "properties": {
                "nummer": {"type": "integer", "description": "Auftragsnummer."}
            },
            "required": ["nummer"],
        },
    )
    async def auftrag_abbrechen(args):
        a = werkstatt.auftraege.get(int(args.get("nummer") or 0))
        # "unterbrochen" gehoert ausdruecklich dazu. Vorher stand hier nur
        # "läuft" -- und damit gab es fuer einen unterbrochenen Auftrag
        # ueberhaupt keinen Weg, ihn loszuwerden:
        #
        # Die Vorspannzeile (werkzeuge/__init__.py) weist Sarvis bei JEDEM
        # Zuruf an, das Fortsetzen oder Verwerfen anzubieten, solange ein
        # Auftrag auf "unterbrochen" steht. Sagte der Nutzer "verwirf das",
        # antwortete dieses Werkzeug "Dieser Auftrag läuft nicht", der
        # Status blieb, und beim naechsten Zuruf fragte Sarvis erneut.
        # Gemessen: ueber vierzig Mal an einem Vormittag. Von aussen sah
        # das aus, als habe er die Antwort vergessen -- er konnte ihr nur
        # nicht folgen.
        if a is None or a.status not in ("läuft", "unterbrochen"):
            return {"content": [{"type": "text", "text":
                    "Diesen Auftrag gibt es nicht oder er ist längst "
                    "beendet."}], "is_error": True}
        # Hier stand: cancel() schicken und sofort "abgebrochen" melden.
        # Das war eine Behauptung, keine Auskunft. cancel() wirkt erst,
        # wenn die Aufgabe das naechste Mal wartet -- und wenn gar keine
        # Aufgabe existierte, passierte ueberhaupt nichts. Beides sah von
        # aussen gleich aus: Erfolgsmeldung, und auftrag_status sagte
        # danach weiter "läuft". Der Nutzer hat es gemerkt, nicht Sarvis.
        weg, text = await werkstatt.abbrechen(a)
        vermerken(f"auftrag_abbrechen: {text}")
        antwort = {"content": [{"type": "text", "text": text}]}
        if not weg:
            antwort["is_error"] = True
        return antwort

    @tool(
        "auftrag_fortsetzen",
        "Setzt einen unterbrochenen Auftrag dort fort, wo er aufgehört hat — "
        "mit dem Gedächtnis des ursprünglichen Arbeiters. Für 'mach da weiter' "
        "nach einem Neustart. Fängt NICHT von vorn an.",
        {
            "type": "object",
            "properties": {
                "nummer": {"type": "integer", "description": "Auftragsnummer."}
            },
            "required": ["nummer"],
        },
    )
    async def auftrag_fortsetzen(args):
        a, fehler = await asyncio.to_thread(
            werkstatt.fortsetzen, args.get("nummer"))
        if a is None:
            return {"content": [{"type": "text", "text": fehler}],
                    "is_error": True}
        fehler = werkstatt.losschicken(a)
        if fehler:
            return {"content": [{"type": "text", "text":
                    f"Auftrag {a.nummer} ließ sich nicht fortsetzen: "
                    f"{fehler}"}], "is_error": True}
        # Hier stand blinken() -- eine Funktion, die es in diesem Modul
        # nie gab. Der NameError traf JEDEN Aufruf, und zwar NACH dem
        # Neustart des Arbeiters: Sarvis meldete "hat nicht geklappt",
        # waehrend der Arbeiter im Hintergrund schon weiterschrieb.
        if leuchten:
            leuchten("Aufträge")
        vermerken(f"auftrag_fortsetzen: Auftrag {a.nummer} läuft weiter.")
        return {"content": [{"type": "text", "text":
                f"Auftrag {a.nummer} läuft weiter, auf Zweig {a.zweig}. "
                "Er sieht sich erst an, wie weit er war."}]}

    return [auftrag_geben, auftrag_status, auftrag_ergebnis,
            auftrag_abbrechen, auftrag_fortsetzen]
