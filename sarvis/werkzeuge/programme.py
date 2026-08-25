"""Programme starten und beenden.

Windows fuehrt selbst eine Liste von allem Startbaren -- Get-StartApps,
173 Eintraege auf diesem Rechner. Damit muss Sarvis weder Pfade raten
noch wissen, dass Spotify aus dem Store kommt und anders gestartet wird
als Blender.

Die Liste kostet 0,84 s. Deshalb wird sie einmal geholt und gemerkt.
"""
import asyncio
import json
import re
import subprocess
from difflib import SequenceMatcher

from claude_agent_sdk import tool

_liste: list[dict] | None = None
_schloss = asyncio.Lock()

# Windows braucht fuer zwei Arten von Programmen zwei Wege.
_IST_PFAD = re.compile(r"\.exe$|^[a-zA-Z]:[\\/]", re.IGNORECASE)


async def _holen(neu: bool = False) -> list[dict]:
    """Alle startbaren Programme, wie Windows sie kennt."""
    global _liste
    async with _schloss:
        if _liste is not None and not neu:
            return _liste
        try:
            ergebnis = await asyncio.to_thread(
                subprocess.run,
                ["powershell.exe", "-NoProfile", "-Command",
                 # UTF-8 erzwingen. Ohne das kommt der Text in der
                 # Windows-Standardkodierung, und ein einziger Programm-
                 # name mit Sonderzeichen laesst das Einlesen platzen --
                 # die Liste war dann leer, ohne dass es auffiel.
                 "[Console]::OutputEncoding = "
                 "[Text.Encoding]::UTF8; "
                 "Get-StartApps | ConvertTo-Json -Compress"],
                capture_output=True, timeout=30,
            )
            text = (ergebnis.stdout or b"").decode("utf-8", errors="replace")
            roh = json.loads(text or "[]")
            _liste = [
                {"name": str(e.get("Name", "")), "id": str(e.get("AppID", ""))}
                for e in (roh if isinstance(roh, list) else [roh])
                if e.get("Name")
            ]
        except Exception as e:
            # Nicht stillschweigend leer lassen -- genau das hat den
            # Kodierungsfehler oben so lange verdeckt.
            print(f"  (Programmliste ließ sich nicht laden: {e})")
            _liste = []
        return _liste


def _guete(name: str, gesucht: str) -> int:
    n, g = name.lower().strip(), gesucht.lower().strip()
    if not n or not g:
        return 0
    if n == g:
        return 100
    if n.startswith(g):
        return 85
    if any(w == g for w in n.split()):
        return 75
    if g in n:
        return 60
    aehnlich = SequenceMatcher(None, n, g).ratio()
    return int(aehnlich * 50) if aehnlich >= 0.7 else 0


async def _finden(gesucht: str) -> list[dict]:
    treffer = [(p, _guete(p["name"], gesucht)) for p in await _holen()]
    treffer = [(p, g) for p, g in treffer if g]
    treffer.sort(key=lambda x: -x[1])
    return [p for p, _ in treffer]


# Seiten, die man beim Namen nennt. Der zweite Eintrag ist die Suchform --
# "such auf YouTube nach X" soll direkt bei den Ergebnissen landen und
# nicht auf der Startseite.
SEITEN = {
    "youtube":       ("https://www.youtube.com",
                      "https://www.youtube.com/results?search_query={}"),
    "google":        ("https://www.google.de",
                      "https://www.google.de/search?q={}"),
    "wikipedia":     ("https://de.wikipedia.org",
                      "https://de.wikipedia.org/w/index.php?search={}"),
    "github":        ("https://github.com",
                      "https://github.com/search?q={}"),
    "amazon":        ("https://www.amazon.de",
                      "https://www.amazon.de/s?k={}"),
    "ebay":          ("https://www.ebay.de",
                      "https://www.ebay.de/sch/i.html?_nkw={}"),
    "kleinanzeigen": ("https://www.kleinanzeigen.de",
                      "https://www.kleinanzeigen.de/s-{}/k0"),
    "maps":          ("https://www.google.de/maps",
                      "https://www.google.de/maps/search/{}"),
    "chatgpt":       ("https://chatgpt.com", None),
    "claude":        ("https://claude.ai", None),
    "gmail":         ("https://mail.google.com", None),
    "spotify":       ("https://open.spotify.com",
                      "https://open.spotify.com/search/{}"),
    "netflix":       ("https://www.netflix.com", None),
    "wetter":        ("https://www.wetter.com",
                      "https://www.wetter.com/suche/?q={}"),
}

_SIEHT_AUS_WIE_ADRESSE = re.compile(
    r"^(https?://|www\.)|^[\w-]+\.(de|com|org|net|io|dev|eu|at|ch)(/|$)",
    re.IGNORECASE,
)


def _adresse(ziel: str, suche: str = "") -> tuple[str, str]:
    """Aus 'youtube' + 'Katzen' wird eine fertige Adresse."""
    from urllib.parse import quote_plus

    schluessel = ziel.lower().strip().rstrip("/")
    schluessel = re.sub(r"^(https?://)?(www\.)?", "", schluessel)
    schluessel = schluessel.split(".")[0] if "." in schluessel else schluessel

    if schluessel in SEITEN:
        start, suchform = SEITEN[schluessel]
        if suche and suchform:
            return suchform.format(quote_plus(suche)), schluessel.capitalize()
        return start, schluessel.capitalize()

    if _SIEHT_AUS_WIE_ADRESSE.match(ziel):
        adresse = ziel if ziel.lower().startswith("http") else f"https://{ziel}"
        return adresse, ziel

    # Weder bekannt noch eine Adresse -- dann als Suche behandeln.
    from urllib.parse import quote_plus as q
    begriff = f"{ziel} {suche}".strip()
    return f"https://www.google.de/search?q={q(begriff)}", "Die Suche"


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    def blinken():
        if leuchten:
            leuchten("Programme")

    @tool(
        "programm_starten",
        "Startet ein Programm auf dem Rechner — Spotify, Blender, Chrome, "
        "was auch immer im Startmenü steht. Für 'mach mal Spotify auf' oder "
        "'öffne Blender'.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Name des Programms, wie man ihn "
                                        "sagen würde."},
            },
            "required": ["name"],
        },
    )
    async def programm_starten(args):
        gesucht = (args.get("name") or "").strip()
        if not gesucht:
            return {"content": [{"type": "text", "text":
                    "Welches Programm denn?"}], "is_error": True}

        treffer = await _finden(gesucht)
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Ein Programm namens {gesucht!r} finde ich nicht im "
                    "Startmenü."}], "is_error": True}

        ziel = treffer[0]
        try:
            if _IST_PFAD.search(ziel["id"]):
                befehl = ["powershell.exe", "-NoProfile", "-Command",
                          f'Start-Process "{ziel["id"]}"']
            else:
                # Store-Apps und alles mit AppUserModelID gehen nur so.
                befehl = ["explorer.exe",
                          f'shell:AppsFolder\\{ziel["id"]}']
            await asyncio.to_thread(
                subprocess.Popen, befehl,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as e:
            return {"content": [{"type": "text", "text":
                    f"{ziel['name']} ließ sich nicht starten: {e}"}],
                    "is_error": True}

        blinken()
        vermerken(f"programm_starten: {ziel['name']} wurde gestartet.")
        weitere = ""
        if len(treffer) > 1 and _guete(treffer[1]["name"], gesucht) >= 60:
            weitere = f" (es gäbe auch {treffer[1]['name']})"
        return {"content": [{"type": "text", "text":
                f"{ziel['name']} ist gestartet.{weitere}"}]}

    @tool(
        "programm_suchen",
        "Sucht, welche Programme es auf dem Rechner gibt. Ohne Suchwort "
        "kommen ein paar bekannte.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Teil des Namens."},
            },
        },
    )
    async def programm_suchen(args):
        gesucht = (args.get("name") or "").strip()
        blinken()
        if not gesucht:
            alle = await _holen()
            namen = [p["name"] for p in alle[:20]]
            return {"content": [{"type": "text", "text":
                    f"{len(alle)} Programme insgesamt, darunter:\n"
                    + "\n".join(namen)}]}
        treffer = await _finden(gesucht)
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Nichts gefunden zu {gesucht!r}."}]}
        return {"content": [{"type": "text", "text":
                "\n".join(p["name"] for p in treffer[:10])}]}

    @tool(
        "programm_beenden",
        "Beendet ein laufendes Programm. Ungespeicherte Arbeit geht dabei "
        "verloren — deshalb nur auf ausdrücklichen Wunsch.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "Name des Programms oder Prozesses."},
            },
            "required": ["name"],
        },
    )
    async def programm_beenden(args):
        gesucht = (args.get("name") or "").strip()
        if not gesucht:
            return {"content": [{"type": "text", "text":
                    "Welches Programm denn?"}], "is_error": True}
        # Ueber den Prozessnamen, nicht ueber das Startmenue: beenden laesst
        # sich nur, was auch laeuft.
        sicher = re.sub(r"[^\w .-]", "", gesucht)[:60]
        try:
            ergebnis = await asyncio.to_thread(
                subprocess.run,
                ["powershell.exe", "-NoProfile", "-Command",
                 f'$p = Get-Process -Name "*{sicher}*" -ErrorAction '
                 'SilentlyContinue; if ($p) { $p | Stop-Process -Force; '
                 '$p | Select-Object -First 1 -ExpandProperty ProcessName } '
                 'else { "" }'],
                capture_output=True, text=True, timeout=30,
            )
            name = (ergebnis.stdout or "").strip().splitlines()
            name = name[-1] if name else ""
        except Exception as e:
            return {"content": [{"type": "text", "text":
                    f"Ging nicht: {e}"}], "is_error": True}

        blinken()
        if not name:
            return {"content": [{"type": "text", "text":
                    f"{gesucht} läuft gerade nicht."}]}
        vermerken(f"programm_beenden: {name} wurde beendet.")
        return {"content": [{"type": "text", "text": f"{name} ist beendet."}]}

    @tool(
        "web_oeffnen",
        "Öffnet eine Internetseite im Standardbrowser. Für 'geh auf "
        "YouTube', 'mach mal Amazon auf' oder 'such auf YouTube nach "
        "Katzenvideos'. Bekannte Seiten kennt es beim Namen, sonst nimmt "
        "es die Adresse.",
        {
            "type": "object",
            "properties": {
                "ziel": {
                    "type": "string",
                    "description": "Name einer bekannten Seite (youtube, "
                                   "google, github, amazon, ebay, wikipedia, "
                                   "chatgpt, spotify, maps, gmail, "
                                   "kleinanzeigen) oder eine vollständige "
                                   "Adresse.",
                },
                "suche": {
                    "type": "string",
                    "description": "Optional: wonach dort gesucht werden "
                                   "soll. Nur bei den bekannten Seiten.",
                },
            },
            "required": ["ziel"],
        },
    )
    async def web_oeffnen(args):
        ziel = (args.get("ziel") or "").strip()
        suche = (args.get("suche") or "").strip()
        if not ziel:
            return {"content": [{"type": "text", "text":
                    "Welche Seite denn?"}], "is_error": True}

        adresse, name = _adresse(ziel, suche)
        try:
            await asyncio.to_thread(
                subprocess.Popen,
                ["powershell.exe", "-NoProfile", "-Command",
                 f'Start-Process "{adresse}"'],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as e:
            return {"content": [{"type": "text", "text":
                    f"Ging nicht: {e}"}], "is_error": True}

        if leuchten:
            leuchten("Websuche")
        vermerken(f"web_oeffnen: {adresse}")
        return {"content": [{"type": "text", "text":
                (f"{name} ist offen" + (f", Suche nach {suche}." if suche
                                        else ".")) }]}

    @tool(
        "route_zeigen",
        "Öffnet eine Route in Google Maps — von wo nach wo, mit Verkehrs"
        "mittel. Für 'wie komme ich von Hamburg nach Berlin' oder 'zeig mir "
        "den Weg zum Bahnhof'.",
        {
            "type": "object",
            "properties": {
                "von": {"type": "string",
                        "description": "Startpunkt. Leer lassen für den "
                                       "aktuellen Standort."},
                "nach": {"type": "string", "description": "Ziel."},
                "mittel": {
                    "type": "string",
                    "enum": ["auto", "oepnv", "fuss", "rad"],
                    "description": "Verkehrsmittel. Vorgabe: auto.",
                },
            },
            "required": ["nach"],
        },
    )
    async def route_zeigen(args):
        from urllib.parse import quote_plus

        nach = (args.get("nach") or "").strip()
        if not nach:
            return {"content": [{"type": "text", "text":
                    "Wohin denn?"}], "is_error": True}
        von = (args.get("von") or "").strip()
        mittel = {"auto": "driving", "oepnv": "transit",
                  "fuss": "walking", "rad": "bicycling"}.get(
                      args.get("mittel") or "auto", "driving")

        adresse = ("https://www.google.com/maps/dir/?api=1"
                   f"&destination={quote_plus(nach)}"
                   f"&travelmode={mittel}")
        if von:
            adresse += f"&origin={quote_plus(von)}"

        try:
            await asyncio.to_thread(
                subprocess.Popen,
                ["powershell.exe", "-NoProfile", "-Command",
                 f'Start-Process "{adresse}"'],
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except Exception as e:
            return {"content": [{"type": "text", "text":
                    f"Ging nicht: {e}"}], "is_error": True}

        if leuchten:
            leuchten("Websuche")
        wie = {"driving": "mit dem Auto", "transit": "mit Bus und Bahn",
               "walking": "zu Fuß", "bicycling": "mit dem Rad"}[mittel]
        return {"content": [{"type": "text", "text":
                f"Route {wie} " + (f"von {von} " if von else "")
                + f"nach {nach} ist offen."}]}

    return [programm_starten, programm_suchen, programm_beenden,
            web_oeffnen, route_zeigen]
