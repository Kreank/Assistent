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

from .. import config
from ..anzeige import Anzeige

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
            # PowerShell kann starten und trotzdem am Befehl scheitern
            # (Ausfuehrungsrichtlinie, Get-StartApps nicht da). Dann kam
            # kein Fehler, sondern leerer stdout -- und 'text or "[]"'
            # machte daraus eine gueltige leere Liste. Der except-Zweig
            # unten war damit unerreichbar, obwohl sein Kommentar genau
            # diesen Fall als abgedeckt beschrieb.
            if ergebnis.returncode != 0 or not (ergebnis.stdout or b"").strip():
                raise RuntimeError(
                    (ergebnis.stderr or b"").decode(
                        "utf-8", errors="replace").strip()[:200]
                    or f"Rueckgabewert {ergebnis.returncode}, keine Ausgabe")
            text = (ergebnis.stdout or b"").decode("utf-8", errors="replace")
            roh = json.loads(text)
            _liste = [
                {"name": str(e.get("Name", "")), "id": str(e.get("AppID", ""))}
                for e in (roh if isinstance(roh, list) else [roh])
                if e.get("Name")
            ]
        except Exception as e:
            # Nicht stillschweigend leer lassen -- genau das hat den
            # Kodierungsfehler oben so lange verdeckt.
            print(f"  (Programmliste ließ sich nicht laden: {e})")
            # Und den Fehlschlag NICHT merken. Frueher stand hier
            # _liste = []; weil der Zwischenspeicher oben nur auf
            # 'is not None' prueft, galt die leere Liste danach als
            # gueltiges Ergebnis -- fuer den ganzen Lauf, und ein
            # zweiter Versuch fand nie statt. Sarvis behauptete dann zu
            # jedem Programm, es gebe es nicht im Startmenue.
            return []
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


def _adresse(ziel: str, suche: str = "") -> tuple[str, str, bool]:
    """Aus 'youtube' + 'Katzen' wird eine fertige Adresse.

    Drittes Rueckgabestueck: ob der Suchbegriff wirklich verwendet wurde.
    Nicht jeder Weg hierdurch kann ihn unterbringen -- und wer ihn
    fallenlaesst, darf hinterher nicht behaupten, er haette gesucht.
    """
    from urllib.parse import quote_plus

    ziel = ziel.strip()
    ohne_vorspann = re.sub(r"^(https?://)?(www\.)?", "", ziel.lower())

    # Eine Adresse MIT Pfad, Query oder Fragment wird gar nicht erst in
    # SEITEN nachgeschlagen. Vorher lief die Namensaufloesung zuerst:
    # aus 'https://github.com/anthropics/claude-code' wurde der
    # Schluessel 'github', geoeffnet hat sich die blosse Startseite --
    # Pfad und Parameter still verworfen, ohne Fehler und ohne Hinweis.
    if (re.search(r"[/?#]", ohne_vorspann.rstrip("/"))
            and _SIEHT_AUS_WIE_ADRESSE.match(ziel)):
        adresse = ziel if ziel.lower().startswith("http") else f"https://{ziel}"
        # Ein Suchbegriff geht hier verloren: In eine fertige Adresse mit
        # eigenem Pfad laesst er sich nicht hineinschreiben. Das meldet
        # der Aufrufer -- lautlos schlucken waere genau der Fehler, der
        # oben gerade behoben wurde.
        return adresse, ziel, False

    schluessel = ohne_vorspann.rstrip("/")
    schluessel = schluessel.split(".")[0] if "." in schluessel else schluessel

    if schluessel in SEITEN:
        start, suchform = SEITEN[schluessel]
        if suche and suchform:
            return (suchform.format(quote_plus(suche)),
                    schluessel.capitalize(), True)
        return start, schluessel.capitalize(), False

    if _SIEHT_AUS_WIE_ADRESSE.match(ziel):
        adresse = ziel if ziel.lower().startswith("http") else f"https://{ziel}"
        return adresse, ziel, False

    # Weder bekannt noch eine Adresse -- dann als Suche behandeln.
    from urllib.parse import quote_plus as q
    begriff = f"{ziel} {suche}".strip()
    return f"https://www.google.de/search?q={q(begriff)}", "Die Suche", True


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    def blinken():
        if leuchten:
            leuchten("Programme")

    # Ein eigener Draht zur Anzeige. Die Werkzeuge bekommen von aussen nur
    # leuchten() gereicht, und dafuer eine zweite Leitung durch drei
    # Ebenen zu faedeln waere mehr Umbau als Nutzen: Anzeige ist ein
    # zustandsloser UDP-Sender, der nie blockiert und ins Nichts sendet,
    # wenn die Anzeige gar nicht laeuft.
    sicht = Anzeige(config.ANZEIGE)

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

        # Erst fragen, OB es eine Liste gibt. Ohne diese Trennung klang
        # ein misslungener PowerShell-Aufruf wie eine Auskunft ueber das
        # Startmenue -- "gibt es nicht", obwohl nie darin gesucht wurde.
        if not await _holen():
            return {"content": [{"type": "text", "text":
                    "Ich komme gerade nicht an die Programmliste."}],
                    "is_error": True}

        treffer = await _finden(gesucht)
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Ein Programm namens {gesucht!r} finde ich nicht im "
                    "Startmenü."}], "is_error": True}

        ziel = treffer[0]
        ist_pfad = bool(_IST_PFAD.search(ziel["id"]))
        try:
            if ist_pfad:
                # Hier laesst sich der Start tatsaechlich pruefen:
                # Start-Process meldet einen Fehler, wenn die Datei weg
                # ist. Also abwarten und den Rueckgabewert ansehen, statt
                # Popen sofort als Erfolg zu deuten.
                fertig = await asyncio.to_thread(
                    subprocess.run,
                    ["powershell.exe", "-NoProfile", "-Command",
                     f'Start-Process "{ziel["id"]}"'],
                    capture_output=True, text=True, timeout=15,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if fertig.returncode != 0:
                    grund = (fertig.stderr or "").strip().splitlines()
                    return {"content": [{"type": "text", "text":
                            f"{ziel['name']} ließ sich nicht starten: "
                            + (grund[0] if grund else
                               f"Fehlercode {fertig.returncode}")}],
                            "is_error": True}
            else:
                # Store-Apps und alles mit AppUserModelID gehen nur so --
                # und explorer.exe meldet dort IMMER Erfolg, auch bei einer
                # AppUserModelID, die es nicht mehr gibt. Eine Erfolgs-
                # pruefung ist hier nicht moeglich, also wird auch keine
                # behauptet: unten heisst es "angestossen", nicht
                # "gestartet".
                await asyncio.to_thread(
                    subprocess.Popen,
                    ["explorer.exe", f'shell:AppsFolder\\{ziel["id"]}'],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
        except subprocess.TimeoutExpired:
            return {"content": [{"type": "text", "text":
                    f"Der Startbefehl für {ziel['name']} hängt — ob das "
                    "Programm hochkommt, weiß ich nicht."}],
                    "is_error": True}
        except Exception as e:
            return {"content": [{"type": "text", "text":
                    f"{ziel['name']} ließ sich nicht starten: {e}"}],
                    "is_error": True}

        blinken()
        weitere = ""
        if len(treffer) > 1 and _guete(treffer[1]["name"], gesucht) >= 60:
            weitere = f" (es gäbe auch {treffer[1]['name']})"
        if ist_pfad:
            vermerken(f"programm_starten: {ziel['name']} wurde gestartet.")
            return {"content": [{"type": "text", "text":
                    f"{ziel['name']} ist gestartet.{weitere}"}]}
        vermerken(f"programm_starten: {ziel['name']} wurde angestoßen "
                  "(ob es hochkommt, ist nicht geprüft).")
        return {"content": [{"type": "text", "text":
                f"Ich habe {ziel['name']} angestoßen.{weitere}"}]}

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
        alle = await _holen()
        if not alle:
            # Nicht "0 Programme insgesamt" melden -- das waere eine
            # Aussage ueber eine Liste, die nie gelesen wurde.
            return {"content": [{"type": "text", "text":
                    "Ich komme gerade nicht an die Programmliste."}],
                    "is_error": True}
        if not gesucht:
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
        # Die Leerpruefung oben sieht nur den Rohnamen. Besteht der aus
        # lauter Satzzeichen oder einem Emoji, bleibt hier nichts uebrig
        # -- und aus dem Muster wurde "**", das in PowerShell JEDEN
        # laufenden Prozess trifft, Sarvis eingeschlossen.
        if not sicher.strip(" .-"):
            return {"content": [{"type": "text", "text":
                    f"Mit dem Namen {gesucht!r} kann ich nichts anfangen."}],
                    "is_error": True}
        try:
            ergebnis = await asyncio.to_thread(
                subprocess.run,
                ["powershell.exe", "-NoProfile", "-Command",
                 # Die Namen VOR dem Beenden einsammeln und ALLE melden:
                 # Stop-Process traf schon immer jeden Treffer, die
                 # Antwort nannte aber nur den ersten. Wer "beende Chrome"
                 # sagte, erfuhr nicht, dass auch Chromedriver weg ist.
                 f'$p = Get-Process -Name "*{sicher}*" -ErrorAction '
                 'SilentlyContinue; if ($p) { $n = $p | Select-Object '
                 '-ExpandProperty ProcessName -Unique; '
                 '$p | Stop-Process -Force; $n } else { "" }'],
                capture_output=True, text=True, timeout=30,
            )
            namen = [z.strip() for z in (ergebnis.stdout or "").splitlines()
                     if z.strip()]
        except Exception as e:
            return {"content": [{"type": "text", "text":
                    f"Ging nicht: {e}"}], "is_error": True}

        blinken()
        if not namen:
            return {"content": [{"type": "text", "text":
                    f"{gesucht} läuft gerade nicht."}]}
        alle = ", ".join(namen)
        einzeln = len(namen) == 1
        vermerken(f"programm_beenden: {alle} "
                  f"{'wurde' if einzeln else 'wurden'} beendet.")
        return {"content": [{"type": "text", "text":
                f"{alle} {'ist' if einzeln else 'sind'} beendet."}]}

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

        adresse, name, gesucht = _adresse(ziel, suche)
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
        if suche and not gesucht:
            # Er hat die Adresse geoeffnet, aber nicht gesucht. Das zu
            # verschweigen hiesse, eine Suche zu behaupten, die nie lief.
            schluss = (f" ist offen. Nach {suche} habe ich nicht gesucht -- "
                       "in eine fertige Adresse passt kein Suchbegriff.")
        elif gesucht and suche:
            schluss = f" ist offen, Suche nach {suche}."
        else:
            schluss = " ist offen."
        return {"content": [{"type": "text", "text": name + schluss}]}

    @tool(
        "web_zeigen",
        "Zeigt eine Seite IN der Anzeige, statt den Browser daneben "
        "aufzumachen. Für 'zeig mir meinen Kalender als Monatsansicht', "
        "'zeig mir die Seite', 'mach das hier auf'. Nimm dieses Werkzeug, "
        "wenn der Nutzer etwas SEHEN will; web_oeffnen, wenn er in seinem "
        "gewohnten Browser weiterarbeiten will. Das Fenster lässt sich "
        "größer ziehen und schließt mit Escape.",
        {
            "type": "object",
            "properties": {
                "ziel": {
                    "type": "string",
                    "description": "Name einer bekannten Seite oder eine "
                                   "vollständige Adresse.",
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
    async def web_zeigen(args):
        ziel = (args.get("ziel") or "").strip()
        suche = (args.get("suche") or "").strip()
        if not ziel:
            return {"content": [{"type": "text", "text":
                    "Welche Seite denn?"}], "is_error": True}

        adresse, name, gesucht = _adresse(ziel, suche)
        sicht.browser(adresse)
        if leuchten:
            leuchten("Websuche")
        vermerken(f"web_zeigen: {adresse}")

        # Dieselbe Ehrlichkeit wie bei web_oeffnen: Eine Suche, die nicht
        # lief, wird nicht behauptet.
        if suche and not gesucht:
            schluss = (f" steht in der Anzeige. Nach {suche} habe ich nicht "
                       "gesucht -- in eine fertige Adresse passt kein "
                       "Suchbegriff.")
        elif gesucht and suche:
            schluss = f" steht in der Anzeige, Suche nach {suche}."
        else:
            schluss = " steht in der Anzeige."

        # Der Hinweis auf die eigene Anmeldung faellt genau einmal: beim
        # ersten Mal, wenn es das Profil noch nicht gibt. Danach waere er
        # Geschwaetz -- und beim ersten Mal ist er der Unterschied
        # zwischen "kaputt" und "einmal anmelden".
        if not config.BROWSER_PROFIL.exists():
            schluss += (" Das ist ein eigener Browser, nicht dein Chrome -- "
                        "bei angemeldeten Seiten musst du dich dort einmal "
                        "anmelden.")
        return {"content": [{"type": "text", "text": name + schluss}]}

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
            web_oeffnen, web_zeigen, route_zeigen]
