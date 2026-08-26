"""Projekte anlegen und öffnen -- Sarvis als Pförtner.

Der lästige Teil am Anfang eines Projekts ist Ordner anlegen, README
schreiben, git init. Genau das lässt sich gut zurufen. Entwickelt wird
danach dort, wo man sieht was passiert.

Wohin, entscheidet der Nutzer -- nicht das Modell. Frueher gab es nur
config.PROJEKTE, und damit konnte die Frage "entwickeln wir fuer privat
oder fuer die Arbeit?" gar nicht erst gestellt werden. Es landete immer
im selben Ordner, und man erfuhr es erst, wenn man nachfragte.

Jetzt gibt es drei Orte (config.PROJEKT_ORTE), und der Ort ist ein
Pflichtfeld. Die Grenze bleibt derselbe Gedanke wie vorher: Ein Projekt
kann nur INNERHALB eines dieser Ordner entstehen, geprueft wird das am
aufgeloesten Pfad -- nicht an der Vernunft des Modells.
"""
import re
import subprocess
from pathlib import Path
import sys
from datetime import datetime

from claude_agent_sdk import tool

from .. import config, schutz

UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
                         "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"})

GERUEST = {
    "leer": {},
    "python": {
        "hauptprogramm.py": '"""{titel}"""\n\n\ndef main():\n    pass\n\n\n'
                            'if __name__ == "__main__":\n    main()\n',
        "requirements.txt": "",
        ".gitignore": ".venv/\n__pycache__/\n*.pyc\n.env\n",
    },
    "web": {
        "index.html": "<!doctype html>\n<html lang=\"de\">\n<head>\n"
                      "  <meta charset=\"utf-8\">\n"
                      "  <meta name=\"viewport\" content=\"width=device-width,"
                      " initial-scale=1\">\n  <title>{titel}</title>\n"
                      "  <link rel=\"stylesheet\" href=\"stil.css\">\n"
                      "</head>\n<body>\n  <h1>{titel}</h1>\n"
                      "  <script src=\"seite.js\"></script>\n</body>\n</html>\n",
        "stil.css": ":root { color-scheme: light dark; }\n",
        "seite.js": "",
        ".gitignore": "node_modules/\ndist/\n.env\n",
    },
}


def kurzname(name: str) -> str:
    """'Angebotsrechner für Dächer' -> 'angebotsrechner-fuer-daecher'."""
    s = (name or "").translate(UMLAUTE).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:60] or "projekt"


def _wurzel(ort: str):
    """Der Ordner zu einem Ortsnamen, oder None."""
    return config.PROJEKT_ORTE.get((ort or "").strip().lower())


def _pfad(name: str, ort: str = "sandkasten"):
    """Zielordner -- und die Zusicherung, dass er im gewaehlten Ort liegt.

    Ohne diese Pruefung koennte ein Name wie '../../Privat' aus dem
    Ordner herausfuehren. Das ist keine Theorie, sondern der
    naheliegendste Weg, wie so etwas schiefgeht.
    """
    wurzel = _wurzel(ort)
    if wurzel is None:
        return None
    ziel = (wurzel / kurzname(name)).resolve()
    if wurzel.resolve() not in ziel.parents:
        return None
    return ziel


def _finden(name: str):
    """Ein bestehendes Projekt in allen Orten suchen."""
    for ort in config.PROJEKT_ORTE:
        ziel = _pfad(name, ort)
        if ziel is not None and ziel.exists():
            return ziel, ort
    return None, None



# Woran man erkennt, was an einem Ort gemacht wird. Reihenfolge zaehlt:
# Das Spezifischere zuerst, sonst ist jedes Angular-Projekt nur ein
# "Node-Projekt".
_MARKER = (
    ("angular.json", "Angular-Frontend"),
    ("next.config.js", "Next.js-Frontend"),
    ("vite.config.ts", "Vite-Frontend"),
    ("package.json", "Node-Projekt"),
    ("pyproject.toml", "Python-Projekt"),
    ("requirements.txt", "Python-Projekt"),
    ("docker-compose.yml", "Docker-Aufbau"),
    ("Dockerfile", "Docker-Aufbau"),
    ("Cargo.toml", "Rust-Projekt"),
    ("go.mod", "Go-Projekt"),
    ("index.html", "Webseite"),
)

# Ordner, die nichts ueber den Ort aussagen, aber alles ueberwiegen
# wuerden: In node_modules liegen mehr Dateien als im ganzen Projekt.
_UEBERGEHEN = {".git", "node_modules", ".venv", "venv", "__pycache__",
               "dist", "build", ".next", ".angular", ".idea", ".vscode"}

_TEXTARTEN = {".md", ".txt", ".pdf", ".docx", ".doc", ".rtf", ".odt"}
_BILDARTEN = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".mp4",
              ".mov", ".psd", ".ai", ".blend"}
_CODEARTEN = {".py", ".ts", ".js", ".tsx", ".jsx", ".html", ".css", ".scss",
              ".java", ".cs", ".go", ".rs", ".php", ".sql", ".sh", ".ps1"}


def _durchgehen(wurzel, tiefe=3):
    """Dateien sammeln, ohne sich in node_modules zu verlieren."""
    dateien = []
    def rein(ordner, stufe):
        if stufe > tiefe:
            return
        try:
            eintraege = list(ordner.iterdir())
        except OSError:
            return
        for e in eintraege:
            if e.name in _UEBERGEHEN or e.name.startswith("."):
                if e.name not in (".gitignore", ".env.example"):
                    continue
            if e.is_dir():
                rein(e, stufe + 1)
            elif e.is_file():
                dateien.append(e)
            if len(dateien) > 4000:      # Notbremse, nicht Genauigkeit
                return
    rein(wurzel, 1)
    return dateien


def _git_stand(ordner):
    """Zweig, letzter Commit und ob etwas offen ist -- oder ''."""
    if not (ordner / ".git").exists():
        return ""
    def git(*args):
        try:
            e = subprocess.run(["git", *args], cwd=ordner, capture_output=True,
                               text=True, timeout=6)
            return e.stdout.strip() if e.returncode == 0 else ""
        except (OSError, subprocess.SubprocessError):
            return ""
    zweig = git("rev-parse", "--abbrev-ref", "HEAD")
    letzter = git("log", "-1", "--format=%s (%cr)")
    offen = [z for z in git("status", "--porcelain").splitlines() if z.strip()]
    teile = []
    if zweig:
        teile.append(f"Zweig {zweig}")
    if letzter:
        teile.append(f"zuletzt: {letzter}")
    teile.append(f"{len(offen)} offene Änderungen" if offen
                 else "nichts Offenes")
    return "; ".join(teile)


def lage(ordner) -> str:
    """Was fuer ein Ort ist das? Ein kurzer Bericht fuer das Modell.

    Der Zweck ist nicht Vollstaendigkeit, sondern eine gute naechste
    Frage. Wer sieht, dass dort ein halbfertiges Angular-Frontend liegt,
    fragt "weiterbauen?" -- und nicht "was soll rein?".
    """
    dateien = _durchgehen(ordner)
    if not dateien:
        return f"{ordner.name}: leer oder nicht lesbar."

    namen = {d.name for d in dateien}
    arten = {}
    for d in dateien:
        arten[d.suffix.lower()] = arten.get(d.suffix.lower(), 0) + 1

    zeilen = [f"Ort: {ordner}", f"{len(dateien)} Dateien"]

    gefunden = []
    for marker, was in _MARKER:
        if marker in namen and was not in gefunden:
            gefunden.append(was)
    if gefunden:
        zeilen.append("Erkannt: " + ", ".join(gefunden[:3]))

    text = sum(n for a, n in arten.items() if a in _TEXTARTEN)
    bild = sum(n for a, n in arten.items() if a in _BILDARTEN)
    code = sum(n for a, n in arten.items() if a in _CODEARTEN)
    if not gefunden:
        if text > len(dateien) * 0.5:
            zeilen.append("Ueberwiegend Texte -- Anleitungen, Notizen, "
                          "Dokumente.")
        elif bild > len(dateien) * 0.5:
            zeilen.append("Ueberwiegend Bilder oder Videos.")
        elif code > len(dateien) * 0.3:
            zeilen.append("Ueberwiegend Quelltext, aber keine bekannte "
                          "Projektdatei.")
    zeilen.append("Dateiarten: " + ", ".join(
        f"{a or 'ohne'} {n}" for a, n in
        sorted(arten.items(), key=lambda x: -x[1])[:6]))

    if text and (text > code or not gefunden):
        titel = [d.stem for d in dateien
                 if d.suffix.lower() in _TEXTARTEN][:8]
        if titel:
            zeilen.append("Dokumente u.a.: " + ", ".join(titel))

    git = _git_stand(ordner)
    if git:
        zeilen.append("Git: " + git)

    neu = sorted(dateien, key=lambda d: -d.stat().st_mtime)[:5]
    zeilen.append("Zuletzt geändert: " + "; ".join(
        f"{d.relative_to(ordner)} ({datetime.fromtimestamp(d.stat().st_mtime):%d.%m. %H:%M})"
        for d in neu))

    liesmich = ordner / "README.md"
    if liesmich.exists():
        try:
            anfang = " ".join(liesmich.read_text(
                encoding="utf-8", errors="replace").split())[:300]
            zeilen.append("README: " + anfang)
        except OSError:
            pass
    return "\n".join(zeilen)


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    def blinken():
        if leuchten:
            leuchten("Projekte")

    @tool(
        "projekt_anlegen",
        "Legt ein neues Projekt an: Ordner, README mit der Beschreibung, "
        "Git-Repository und je nach Art ein Grundgerüst. Für 'mach mir ein "
        "neues Projekt für X'. "
        "WICHTIG: 'ort' ist Pflicht und darf NICHT geraten werden. Hat der "
        "Nutzer nicht gesagt, wohin das Projekt soll, dann frag ihn zuerst "
        "— privat, für die Arbeit, oder erstmal in den Sandkasten — und "
        "warte seine Antwort ab, bevor du dieses Werkzeug benutzt.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Kurzer Projektname, wie gesagt."},
                "ort": {
                    "type": "string",
                    "enum": ["privat", "arbeit", "sandkasten"],
                    "description": "Wohin das Projekt gehört. privat = "
                                   "D:\\Privat, arbeit = D:\\Mitra, "
                                   "sandkasten = D:\\Projekte. Nur setzen, "
                                   "wenn der Nutzer es gesagt hat.",
                },
                "beschreibung": {
                    "type": "string",
                    "description": "Worum es geht, in eigenen Worten "
                                   "ausformuliert — landet im README und ist "
                                   "später der Auftrag. Ruhig zwei, drei Sätze.",
                },
                "art": {"type": "string", "enum": ["leer", "python", "web"],
                        "description": "Grundgerüst. Vorgabe: leer."},
            },
            "required": ["name", "beschreibung", "ort"],
        },
    )
    async def projekt_anlegen(args):
        name = (args.get("name") or "").strip()
        ort = (args.get("ort") or "").strip().lower()
        if _wurzel(ort) is None:
            return {"content": [{"type": "text", "text":
                    "Ich weiß nicht, wohin. Frag den Nutzer, ob das Projekt "
                    "privat, für die Arbeit oder in den Sandkasten soll."}],
                    "is_error": True}
        ziel = _pfad(name, ort)
        if ziel is None:
            return {"content": [{"type": "text", "text":
                    "Dieser Name führt aus dem Projektordner heraus. "
                    "Nicht angelegt."}], "is_error": True}
        if ziel.exists():
            return {"content": [{"type": "text", "text":
                    f"{ziel.name} gibt es schon."}], "is_error": True}

        titel = name or ziel.name
        beschreibung = (args.get("beschreibung") or "").strip()
        ziel.mkdir(parents=True)

        (ziel / "README.md").write_text(
            f"# {titel}\n\n{beschreibung}\n\n---\n\n"
            f"Angelegt am {datetime.now():%d.%m.%Y} auf Zuruf über Sarvis.\n",
            encoding="utf-8",
        )
        for datei, inhalt in GERUEST.get(args.get("art") or "leer", {}).items():
            (ziel / datei).write_text(inhalt.format(titel=titel),
                                      encoding="utf-8")

        meldung = ""
        try:
            subprocess.run(["git", "init", "-q"], cwd=ziel, check=True,
                           capture_output=True, timeout=30)
            subprocess.run(["git", "add", "-A"], cwd=ziel, check=True,
                           capture_output=True, timeout=30)
            subprocess.run(["git", "commit", "-q", "-m", "Erster Stand"],
                           cwd=ziel, check=True, capture_output=True,
                           timeout=30)
        except (subprocess.SubprocessError, OSError) as e:
            meldung = f" (Git ging nicht: {e})"

        blinken()
        vermerken(f"projekt_anlegen: {ziel} wurde angelegt.")
        return {"content": [{"type": "text", "text":
                f"Angelegt: {ziel}{meldung}"}]}

    @tool(
        "projekt_liste",
        "Zählt auf, welche Projekte es gibt — privat, für die Arbeit und im "
        "Sandkasten —, mit Ort und Datum der letzten Änderung.",
        {
            "type": "object",
            "properties": {
                "ort": {"type": "string",
                        "enum": ["privat", "arbeit", "sandkasten"],
                        "description": "Nur diesen Ort auflisten. Weglassen "
                                       "zeigt alle."},
            },
        },
    )
    async def projekt_liste(args):
        blinken()
        nur = (args.get("ort") or "").strip().lower()
        orte = ({nur: config.PROJEKT_ORTE[nur]} if nur in config.PROJEKT_ORTE
                else config.PROJEKT_ORTE)

        gefunden = []
        for ort, wurzel in orte.items():
            if not wurzel.exists():
                continue
            for p in wurzel.iterdir():
                # Nur was wie ein Projekt aussieht -- D:\\Privat enthaelt
                # auch anderes. Ein Git-Repo oder ein README genuegt.
                if not p.is_dir():
                    continue
                if not ((p / ".git").exists() or (p / "README.md").exists()):
                    continue
                gefunden.append((p, ort))

        if not gefunden:
            return {"content": [{"type": "text", "text":
                    "Es gibt noch keine Projekte."}]}
        gefunden.sort(key=lambda x: -x[0].stat().st_mtime)
        zeilen = [f"{p.name} ({ort}) — zuletzt "
                  f"{datetime.fromtimestamp(p.stat().st_mtime):%d.%m.%Y}"
                  for p, ort in gefunden[:15]]
        return {"content": [{"type": "text", "text": "\n".join(zeilen)}]}

    @tool(
        "projekt_oeffnen",
        "Öffnet ein Terminal mit Claude Code im Projektordner, damit dort "
        "weitergearbeitet werden kann. Optional mit einem ersten Auftrag.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Projektname."},
                "auftrag": {"type": "string",
                            "description": "Optional: womit Claude Code "
                                           "gleich anfangen soll."},
            },
            "required": ["name"],
        },
    )
    async def projekt_oeffnen(args):
        ziel, _ort = _finden(args.get("name") or "")
        if ziel is None or not ziel.exists():
            return {"content": [{"type": "text", "text":
                    "Dieses Projekt finde ich nicht."}], "is_error": True}
        auftrag = (args.get("auftrag") or "").strip()
        befehl = "claude" + (f' "{auftrag}"' if auftrag else "")
        try:
            subprocess.Popen(
                ["cmd", "/c", "start", f"Sarvis - {ziel.name}",
                 "cmd", "/k", f'cd /d "{ziel}" && {befehl}'],
                shell=False,
            )
        except OSError as e:
            return {"content": [{"type": "text", "text":
                    f"Terminal ging nicht auf: {e}"}], "is_error": True}
        blinken()
        vermerken(f"projekt_oeffnen: Terminal für {ziel.name} geöffnet.")
        return {"content": [{"type": "text", "text":
                f"Terminal für {ziel.name} ist offen."}]}

    @tool(
        "ort_ansehen",
        "Sieht sich einen Ordner oder ein Projekt an und sagt, WAS für ein "
        "Ort das ist: Wird dort entwickelt und womit, wie weit ist es, "
        "liegen dort Anleitungen, Bilder oder Notizen? Mit Git-Stand und "
        "den zuletzt geänderten Dateien. "
        "BENUTZE DAS, wenn der Nutzer den Ort wechselt ('gehen wir mal ins "
        "Projekt X', 'was liegt in Y'). Öffne dafür KEIN Terminal. Und frag "
        "danach etwas, das zu dem passt, was du siehst — bei angefangener "
        "Arbeit, ob weitergebaut werden soll; bei einer Sammlung von "
        "Anleitungen, ob du zusammenfassen oder etwas Bestimmtes suchen "
        "sollst.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Projektname oder ganzer Pfad."},
            },
            "required": ["name"],
        },
    )
    async def ort_ansehen(args):
        roh = (args.get("name") or "").strip()
        ziel, _ort = _finden(roh)
        if ziel is None:
            try:
                versuch = Path(roh).expanduser()
                if versuch.is_dir():
                    ziel = versuch.resolve()
            except (OSError, ValueError):
                ziel = None
        if ziel is None or not ziel.is_dir():
            return {"content": [{"type": "text", "text":
                    f"Den Ort {roh} finde ich nicht."}], "is_error": True}

        # Dieses Werkzeug laeuft ohne Rueckfrage. Damit das vertretbar
        # bleibt, gilt hier dieselbe Grenze wie beim stillen Auflisten --
        # sonst waere es ein Weg, an der Pruefung vorbei in fremde Ordner
        # zu sehen.
        if schutz.auflisten_stufe(str(ziel)) != "frei":
            return {"content": [{"type": "text", "text":
                    "Dort sehe ich nicht ungefragt nach. Nimm ordner_ansehen "
                    "— das fragt den Nutzer."}], "is_error": True}

        blinken()
        return {"content": [{"type": "text", "text": lage(ziel)}]}

    return [projekt_anlegen, projekt_liste, projekt_oeffnen, ort_ansehen]
