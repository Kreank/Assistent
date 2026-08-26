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
import sys
from datetime import datetime

from claude_agent_sdk import tool

from .. import config

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

    return [projekt_anlegen, projekt_liste, projekt_oeffnen]
