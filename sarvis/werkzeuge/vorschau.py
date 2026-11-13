"""Webseiten aus Projekten zum Anschauen bereitstellen.

Sascha (13.11.2026): Ein Arbeiter baut eine Webseite -- und dann? Sie lag
im Sandkasten, und ansehen konnte er sie nur, wenn jemand sie per Hand
irgendwo hinstellte. Jetzt baut Sarvis sie und legt sie unter
test.tech-artist.de ab:

    /vorschau/<projekt>/   mit Passwort (Caddy basic_auth)
    /offen/<projekt>/      fuer jeden mit dem Link

Welche der beiden, entscheidet Sascha jedes Mal -- das Modell fragt, wenn
er es nicht gesagt hat. Caddy zeigt nur auf die beiden festen Ordner;
Sarvis legt Dateien hinein und fasst die Caddyfile nie an.

Gebaut wird mit --base auf den Unterpfad. Ohne das laedt ein Vite-Build
seine Skripte von /assets/... und zeigt unter /vorschau/x/ eine weisse
Seite.
"""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from claude_agent_sdk import tool

from .. import anzeige as anzeige_modul
from .projekte import _finden, kurzname

WURZEL = Path("/srv/data/sarvis/vorschau")
ADRESSE = "https://test.tech-artist.de"
ZUGAENGE = {"login": "vorschau", "offen": "offen"}   # zugang -> Unterordner

# Was beim reinen Kopieren (Seite ohne Build) nicht mit darf.
_NICHT_KOPIEREN = shutil.ignore_patterns(
    ".git", "node_modules", ".env", ".env.*", "*.pem", "*.key", ".laufzeit",
    "__pycache__", ".venv", "venv", "fortschritt.md", "bericht.md")


def _text(t: str, fehler: bool = False) -> dict:
    a = {"content": [{"type": "text", "text": t}]}
    if fehler:
        a["is_error"] = True
    return a


def _laufen(befehl: list[str], ordner: Path, sekunden: int) -> tuple[bool, str]:
    try:
        r = subprocess.run(befehl, cwd=ordner, capture_output=True, text=True,
                           timeout=sekunden)
    except (subprocess.SubprocessError, OSError) as e:
        return False, str(e)
    aus = (r.stdout + "\n" + r.stderr).strip()
    return r.returncode == 0, aus[-1500:]


def _bauen(ordner: Path, ziel: Path, basis: str) -> str | None:
    """Baut ordner nach ziel. Gibt eine Fehlermeldung zurueck oder None."""
    paket = ordner / "package.json"
    if paket.exists():
        try:
            skripte = json.loads(paket.read_text(encoding="utf-8")).get(
                "scripts", {})
        except (OSError, ValueError):
            skripte = {}
        vite = any((ordner / f"vite.config.{e}").exists()
                   for e in ("ts", "js", "mjs", "mts"))
        if not vite and "build" not in skripte:
            return "Das Projekt hat kein Build-Skript."
        if not (ordner / "node_modules").exists():
            ok, aus = _laufen(["npm", "install", "--no-audit", "--no-fund"],
                              ordner, 600)
            if not ok:
                return f"npm install ging nicht:\n{aus}"
        if vite:
            # Direkt in den Zielordner, mit dem Unterpfad als Basis.
            ok, aus = _laufen(["npx", "vite", "build", "--base", basis,
                               "--outDir", str(ziel), "--emptyOutDir"],
                              ordner, 600)
            return None if ok else f"Der Build ging nicht:\n{aus}"
        ok, aus = _laufen(["npm", "run", "build"], ordner, 600)
        if not ok:
            return f"Der Build ging nicht:\n{aus}"
        for name in ("dist", "build", "out"):
            if (ordner / name / "index.html").exists():
                shutil.copytree(ordner / name, ziel)
                return None
        return "Der Build lief, aber ich finde keinen Ausgabeordner mit index.html."
    if (ordner / "index.html").exists():
        shutil.copytree(ordner, ziel, ignore=_NICHT_KOPIEREN)
        return None
    return "Das ist keine Webseite: weder package.json noch index.html."


def _ordner(name: str) -> Path | None:
    ziel, _ort = _finden(name)
    return ziel if ziel is not None and ziel.is_dir() else None


def werkzeuge(protokoll=None, leuchten=None) -> list:
    sicht = anzeige_modul.aktuelle()

    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    @tool(
        "vorschau_zeigen",
        "Baut die Webseite eines Projekts (Vite/React, npm-Build oder "
        "einfache index.html) und stellt sie unter test.tech-artist.de "
        "bereit, damit der Nutzer sie im Browser ansehen kann — als Karte "
        "mit Öffnen-Knopf in der App. Für 'zeig mir die Seite', 'stell das "
        "online', 'ich will das sehen'. Nochmal aufrufen = neuer Stand an "
        "derselben Adresse. "
        "WICHTIG: 'zugang' ist Pflicht und darf NICHT geraten werden. Hat "
        "der Nutzer nicht gesagt, ob mit Login oder offen für jeden, frag "
        "ihn zuerst und warte die Antwort ab. login = nur mit Passwort, "
        "offen = jeder mit dem Link kann es sehen.",
        {
            "type": "object",
            "properties": {
                "projekt": {"type": "string",
                            "description": "Projektname, wie bei "
                                           "projekt_liste."},
                "zugang": {"type": "string", "enum": ["login", "offen"],
                           "description": "login = mit Passwort, offen = "
                                          "für jeden. Nur setzen, wenn der "
                                          "Nutzer es gesagt hat."},
            },
            "required": ["projekt", "zugang"],
        },
    )
    async def vorschau_zeigen(args):
        zugang = (args.get("zugang") or "").strip().lower()
        if zugang not in ZUGAENGE:
            return _text("Frag den Nutzer zuerst, ob die Vorschau mit Login "
                         "oder offen für jeden sein soll.", True)
        ordner = _ordner(args.get("projekt") or "")
        if ordner is None:
            return _text("Dieses Projekt finde ich nicht.", True)
        name = kurzname(ordner.name)
        unter = ZUGAENGE[zugang]
        basis = f"/{unter}/{name}/"

        if leuchten:
            leuchten("Projekte")
        (WURZEL / unter).mkdir(parents=True, exist_ok=True)
        # Erst in einen Nebenordner bauen, dann tauschen: Ein Build, der
        # mittendrin scheitert, laesst die alte Vorschau stehen.
        neu = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=WURZEL / unter))
        neu.rmdir()            # copytree/vite wollen ihn selbst anlegen
        fehler = _bauen(ordner, neu, basis)
        if fehler:
            shutil.rmtree(neu, ignore_errors=True)
            return _text(fehler, True)
        alt = WURZEL / unter / name
        if alt.exists():
            shutil.rmtree(alt)
        neu.rename(alt)
        # Lesbar fuer Caddy (anderer Benutzer auf dem Host).
        for p in [alt, *alt.rglob("*")]:
            p.chmod(0o755 if p.is_dir() else 0o644)
        # Wer von offen auf login wechselt (oder umgekehrt), will die alte
        # Fassung unter der anderen Adresse nicht mehr haben.
        for anderer in ZUGAENGE.values():
            if anderer != unter and (WURZEL / anderer / name).exists():
                shutil.rmtree(WURZEL / anderer / name)

        url = f"{ADRESSE}{basis}"
        titel = f"Vorschau: {ordner.name}"
        sicht.blatt(f"vorschau-{name}", sorte="seite", titel=titel,
                    adresse=url)
        vermerken(f"vorschau_zeigen: {ordner} -> {url} ({zugang})")
        wie = ("mit Passwort" if zugang == "login"
               else "offen für jeden mit dem Link")
        return _text(f"Bereit unter {url} ({wie}). Die Seite ist in der App "
                     "aufgeklappt, im Verlauf steht eine Karte dazu. Schreib "
                     f"die Adresse {url} in deine Antwort, damit Sascha sie "
                     "anklicken und weitergeben kann. Vorgelesen wird sie "
                     "nicht, das filtert die Sprachausgabe heraus.")

    @tool(
        "vorschau_entfernen",
        "Nimmt die Vorschau eines Projekts von test.tech-artist.de wieder "
        "herunter (beide Varianten, mit Login und offen).",
        {
            "type": "object",
            "properties": {"projekt": {"type": "string"}},
            "required": ["projekt"],
        },
    )
    async def vorschau_entfernen(args):
        name = kurzname(args.get("projekt") or "")
        weg = [u for u in ZUGAENGE.values() if (WURZEL / u / name).exists()]
        for u in weg:
            shutil.rmtree(WURZEL / u / name)
        sicht.blatt_weg(f"vorschau-{name}")
        if not weg:
            return _text("Dazu gibt es keine Vorschau.")
        vermerken(f"vorschau_entfernen: {name}")
        return _text("Vorschau entfernt.")

    return [vorschau_zeigen, vorschau_entfernen]
