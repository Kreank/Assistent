"""Projekte anlegen und öffnen -- Sarvis als Pförtner.

Der lästige Teil am Anfang eines Projekts ist Ordner anlegen, README
schreiben, git init. Genau das lässt sich gut zurufen. Entwickelt wird
danach dort, wo man sieht was passiert.

Alles spielt sich unter config.PROJEKTE ab und nirgends sonst. Der Ordner
ist die Grenze -- nicht die Vernunft des Modells.
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


def _pfad(name: str):
    """Zielordner -- und die Zusicherung, dass er unter PROJEKTE liegt.

    Ohne diese Pruefung koennte ein Name wie '../../Privat' aus dem
    Sandkasten herausfuehren. Das ist keine Theorie, sondern der
    naheliegendste Weg, wie so etwas schiefgeht.
    """
    ziel = (config.PROJEKTE / kurzname(name)).resolve()
    wurzel = config.PROJEKTE.resolve()
    if wurzel not in ziel.parents:
        return None
    return ziel


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    def blinken():
        if leuchten:
            leuchten("Projekte")

    @tool(
        "projekt_anlegen",
        "Legt ein neues Projekt unter D:\\Projekte an: Ordner, README mit "
        "der Beschreibung, Git-Repository und je nach Art ein Grundgerüst. "
        "Für 'mach mir ein neues Projekt für X'.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Kurzer Projektname, wie gesagt."},
                "beschreibung": {
                    "type": "string",
                    "description": "Worum es geht, in eigenen Worten "
                                   "ausformuliert — landet im README und ist "
                                   "später der Auftrag. Ruhig zwei, drei Sätze.",
                },
                "art": {"type": "string", "enum": ["leer", "python", "web"],
                        "description": "Grundgerüst. Vorgabe: leer."},
            },
            "required": ["name", "beschreibung"],
        },
    )
    async def projekt_anlegen(args):
        name = (args.get("name") or "").strip()
        ziel = _pfad(name)
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
        "Zählt auf, welche Projekte unter D:\\Projekte liegen, mit dem "
        "Datum der letzten Änderung.",
        {"type": "object", "properties": {}},
    )
    async def projekt_liste(args):
        blinken()
        if not config.PROJEKTE.exists():
            return {"content": [{"type": "text", "text":
                    "Es gibt noch keine Projekte."}]}
        ordner = [p for p in config.PROJEKTE.iterdir() if p.is_dir()]
        if not ordner:
            return {"content": [{"type": "text", "text":
                    "Es gibt noch keine Projekte."}]}
        ordner.sort(key=lambda p: -p.stat().st_mtime)
        zeilen = [f"{p.name} — zuletzt "
                  f"{datetime.fromtimestamp(p.stat().st_mtime):%d.%m.%Y}"
                  for p in ordner[:15]]
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
        ziel = _pfad(args.get("name") or "")
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
