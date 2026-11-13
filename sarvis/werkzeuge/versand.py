"""Dateien aufs Handy schicken -- was er gebaut hat UND was auf dem Server liegt.

Bis zum 10.11.2026 konnte Sarvis nur herausgeben, was er selbst erzeugt
hatte (dokument_erstellen). "Schick mir mal die Rechnung aus dem
Projektordner" oder "gib mir das Foto von gestern" ging nicht: Die Datei
lag ein Stockwerk tiefer auf derselben Platte, und es gab keinen Weg zu
Sascha. Sascha am 10.11.: "Wichtig ist mir der Dateiversand."

DER WEG

Derselbe wie bei den Dokumenten: blaetter.hinlegen() macht die Datei
unter /blatt/<192 Bit Zufall> abrufbar, und ein Blatt der Sorte "datei"
legt der Oberflaeche einen Knopf zum Herunterladen hin. Nichts wird
kopiert -- ausser bei Ordnern, die als ZIP in die Ablage gepackt werden.

WAS GESCHUETZT IST

Ein Pfad auf den Server wird in hirn._pfadstufe ueber
schutz.versenden_stufe gemessen: Was Zugangsdaten enthalten koennte,
geht nur nach Rueckfrage raus, was in NIE_LESEN steht, gar nicht. Ein
blosser Name sucht nur in Eingang und Ablage -- dort liegt nur, was
Sascha geschickt oder Sarvis gebaut hat.

Beim Packen eines Ordners wird jede einzelne Datei noch einmal gegen
dieselbe Stufe gehalten. Ein Ordner mit einer .env darin waere sonst
der Umweg, auf dem genau die mitkommt.
"""
import asyncio
import time
import zipfile
from pathlib import Path

from claude_agent_sdk import tool

from .. import anzeige as anzeige_modul
from .. import config, schutz
from . import eingang

# Was beim Packen eines Ordners nie mitkommt: Ballast, den man neu
# erzeugen kann, und der gross ist.
_AUSLASSEN = {".git", "node_modules", "__pycache__", ".venv", "venv",
              ".mypy_cache", ".pytest_cache", ".next", "dist", "build",
              ".gradle", ".idea"}

# Ab hier wird nicht gepackt, sondern ehrlich abgesagt. Ein ZIP von
# mehreren Gigabyte ueber eine Mobilverbindung ist kein Versand, sondern
# ein haengender Download.
ORDNER_MAX = 500 * 1024 * 1024
ORDNER_DATEIEN_MAX = 5000


def _packen(ordner: Path) -> tuple:
    """Ordner -> ZIP in der Ablage. Rueckgabe (zip, ausgelassen) oder Fehler."""
    dateien, groesse, ausgelassen = [], 0, 0
    for d in sorted(ordner.rglob("*")):
        if any(teil in _AUSLASSEN for teil in d.relative_to(ordner).parts):
            continue
        if not d.is_file() or d.is_symlink():
            continue
        if (schutz.heikel(str(d))
                or schutz.versenden_stufe(str(d)) == "nie"):
            ausgelassen += 1
            continue
        dateien.append(d)
        groesse += d.stat().st_size
        if groesse > ORDNER_MAX or len(dateien) > ORDNER_DATEIEN_MAX:
            raise ValueError(
                f"Der Ordner ist zu groß zum Verschicken (über "
                f"{ORDNER_MAX // 1024 // 1024} MB oder "
                f"{ORDNER_DATEIEN_MAX} Dateien). Nenn mir einen Unterordner "
                "oder einzelne Dateien.")
    if not dateien:
        raise ValueError("In dem Ordner liegt nichts, was ich schicken kann.")
    config.ABLAGE.mkdir(parents=True, exist_ok=True)
    ziel = config.ABLAGE / f"{ordner.name or 'ordner'}-{time.strftime('%Y%m%d-%H%M')}.zip"
    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for d in dateien:
            z.write(d, d.relative_to(ordner.parent))
    return ziel, ausgelassen


def werkzeuge(protokoll=None, leuchten=None) -> list:
    sicht = anzeige_modul.aktuelle()

    def antwort(text: str, fehler: bool = False) -> dict:
        r = {"content": [{"type": "text", "text": text}]}
        if fehler:
            r["is_error"] = True
        return r

    @tool(
        "datei_schicken",
        "Schickt Sascha eine Datei aufs Gerät, als Knopf zum Herunterladen. "
        "Für 'schick mir …', 'gib mir mal die Datei …', 'kann ich das "
        "haben'. Geht mit (1) einem Pfad auf dem Server — jede Datei unter "
        "/home/server3070, /srv/storage/projects oder /srv/data/sarvis; "
        "ein ORDNER wird als ZIP gepackt — oder (2) einem Namen oder "
        "Namensteil, dann wird in dem gesucht, was er dir geschickt hat und "
        "was du selbst erzeugt hast ('das Angebot', 'die Preisliste'). "
        "Mehrere Dateien: einmal je Datei aufrufen.",
        {
            "type": "object",
            "properties": {
                "pfad": {"type": "string",
                         "description": "Absoluter Pfad auf dem Server, "
                                        "oder Name/Namensteil."},
                "titel": {"type": "string",
                          "description": "Kurze Überschrift für den "
                                         "Download, optional."},
            },
            "required": ["pfad"],
        },
    )
    async def datei_schicken(args):
        was = str(args.get("pfad") or "").strip()
        if not was:
            return antwort("Welche Datei? Ich brauche einen Pfad oder Namen.",
                           True)

        if "/" in was or was.startswith("~"):
            try:
                pfad = schutz.pfad_aufloesen(was)
            except (OSError, RuntimeError):
                return antwort(f"Den Pfad {was} verstehe ich nicht.", True)
            if not pfad.exists():
                return antwort(f"{was} gibt es nicht.", True)
            # Die Stufe hat hirn.darf_ich schon gemessen -- "nie" kommt
            # hier gar nicht an. Doppelt haelt besser, es ist eine Zeile.
            if schutz.versenden_stufe(str(pfad)) == "nie":
                return antwort("Diese Datei verschicke ich nicht.", True)
        else:
            gefunden, fehler = eingang.datei_finden(was)
            if gefunden is None:
                return antwort(fehler, True)
            pfad = gefunden

        hinweis = ""
        if pfad.is_dir():
            try:
                pfad, ausgelassen = await asyncio.to_thread(_packen, pfad)
            except (OSError, ValueError) as e:
                return antwort(str(e), True)
            if ausgelassen:
                hinweis = (f" {ausgelassen} Datei(en) mit möglichen "
                           "Zugangsdaten habe ich weggelassen.")

        from ..netz import blaetter
        name = pfad.name
        titel = str(args.get("titel") or "").strip() or name
        try:
            kennung = await asyncio.to_thread(
                blaetter.hinlegen, pfad, "beliebig", titel, name,
                blaetter.FRIST_VERSAND_TAGE)
        except (OSError, ValueError) as e:
            return antwort(f"Bereitstellen ging nicht: {e}", True)

        groesse = pfad.stat().st_size
        from ..netz import begleiter
        extra = await asyncio.to_thread(begleiter.anreichern, kennung)
        sicht.blatt(kennung, sorte="datei", titel=titel,
                    adresse=blaetter.adresse(kennung), datei=name,
                    bytes_=groesse, extra=extra)
        if leuchten:
            leuchten("Dateien")
        if protokoll is not None:
            protokoll.merken(f"datei_schicken: {pfad}")

        draht = sicht.draht()
        if sicht.ueber_netz() and draht and not draht.wie_viele():
            return antwort(f"{name} liegt bereit, aber gerade ist keine "
                           "Oberfläche verbunden — sie steht in seiner "
                           "Dateiliste der App, sobald er sie öffnet."
                           + hinweis)
        mb = groesse / 1024 / 1024
        menge = f"{mb:.1f} MB" if mb >= 1 else f"{groesse // 1024 or 1} KB"
        return antwort(f"{name} ({menge}) liegt jetzt als Download bei ihm "
                       "und bleibt 30 Tage abrufbar." + hinweis)

    return [datei_schicken]
