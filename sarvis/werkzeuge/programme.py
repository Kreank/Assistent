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
        "web_zeigen",
        "Zeigt eine Internetseite. Für 'geh auf YouTube', 'mach mal Amazon "
        "auf', 'zeig mir meinen Kalender als Monatsansicht', 'zeig mir die "
        "Seite'. Bekannte Seiten kennt es beim Namen, sonst nimmt es die "
        "Adresse. Die Seite erscheint in Sarvis' eigenem Fenster; es lässt "
        "sich größer ziehen und schließt mit Escape. "
        "extern=true NUR, wenn der Nutzer einen Browser als SEINEN "
        "bezeichnet: 'in meinem Browser', 'in meinem Chrome', 'im "
        "richtigen Browser', 'im normalen Browser'. Das bloße Wort "
        "'Browser' reicht NICHT — 'öffne im Browser' und 'mach den "
        "Browser auf' meinen Sarvis' Fenster, denn das IST der Browser. "
        "Im Zweifel ohne extern: Dort kann Sarvis die Seite hinterher "
        "lesen und bedienen, im fremden Browser nicht.",
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
                "extern": {
                    "type": "boolean",
                    "description": "Im Standardbrowser des Nutzers öffnen "
                                   "statt in Sarvis' Fenster. Nur wenn er "
                                   "das ausdrücklich sagt.",
                },
            },
            "required": ["ziel"],
        },
    )
    async def web_zeigen(args):
        """Eine Seite zeigen -- hier, oder auf Wunsch im eigenen Browser.

        Frueher waren das ZWEI Werkzeuge, web_oeffnen und web_zeigen, und
        das Modell musste sich zwischen zwei fast gleichen Beschreibungen
        entscheiden. Gemessen an acht Zurufen: Es nahm fuenfmal von fuenf
        das falsche -- auch bei "zeig mir meinen Kalender als
        Monatsansicht", wo es die richtige Monatsadresse baute und sie
        dann im Standardbrowser oeffnete.

        Jetzt gibt es nichts zu entscheiden: einen Weg, und die Ausnahme
        kommt vom Nutzer. Das ist auch der Grund, warum der Engine-Browser
        der Normalfall ist und nicht umgekehrt -- Lesen, Klicken und
        Herunterladen gehen nur dort. In einem Chrome-Fenster daneben
        waere "und jetzt klick auf das erste Video" nicht mehr moeglich.
        """
        ziel = (args.get("ziel") or "").strip()
        suche = (args.get("suche") or "").strip()
        extern = bool(args.get("extern"))
        if not ziel:
            return {"content": [{"type": "text", "text":
                    "Welche Seite denn?"}], "is_error": True}

        adresse, name, gesucht = _adresse(ziel, suche)

        if extern:
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
        else:
            sicht.browser(adresse)

        if leuchten:
            leuchten("Websuche")
        vermerken(f"web_zeigen{' (extern)' if extern else ''}: {adresse}")

        wo = "ist offen" if extern else "steht in der Anzeige"
        # Eine Suche, die nicht lief, wird nicht behauptet.
        if suche and not gesucht:
            schluss = (f" {wo}. Nach {suche} habe ich nicht gesucht -- in "
                       "eine fertige Adresse passt kein Suchbegriff.")
        elif gesucht and suche:
            schluss = f" {wo}, Suche nach {suche}."
        else:
            schluss = f" {wo}."

        # Der Hinweis auf die eigene Anmeldung faellt genau einmal: beim
        # ersten Mal, wenn es das Profil noch nicht gibt. Danach waere er
        # Geschwaetz -- und beim ersten Mal ist er der Unterschied
        # zwischen "kaputt" und "einmal anmelden".
        if not extern and not config.BROWSER_PROFIL.exists():
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

    # --- Die Seite lesen und bedienen -------------------------------------
    #
    # Alle sechs sprechen mit dem Anzeigeprozess, in dem der Browser lebt.
    # sicht.fragen() blockiert bis zum Zeitlimit, deshalb geht es durch
    # einen Faden -- die Schleife darf nie auf die Optik warten muessen.

    async def _browser_fragen(art: str, sekunden: float = 12.0, **felder):
        antwort = await asyncio.to_thread(sicht.fragen, art, sekunden,
                                          **felder)
        if antwort is None:
            return None, ("Die Anzeige antwortet nicht. Läuft sie noch?")
        if not antwort.get("ok"):
            return None, str(antwort.get("grund") or "Das ging nicht.")
        return antwort, ""

    @tool(
        "web_lesen",
        "Liest vor, was auf der gezeigten Seite steht. Für 'was steht da', "
        "'lies mir das vor', 'fass die Seite zusammen'. Nur die Seite im "
        "eigenen Fenster — in einem fremden Browser sieht Sarvis nichts.",
        {"type": "object", "properties": {}},
    )
    async def web_lesen(args):
        antwort, fehler = await _browser_fragen("web_lesen")
        if fehler:
            return {"content": [{"type": "text", "text": fehler}],
                    "is_error": True}
        if leuchten:
            leuchten("Websuche")
        return {"content": [{"type": "text",
                             "text": antwort.get("text") or "(nichts lesbar)"}]}

    @tool(
        "web_elemente",
        "Zählt auf, was auf der Seite anklickbar oder beschreibbar ist — "
        "nummeriert. Diese Nummern brauchen web_klicken und web_tippen. "
        "Vor jedem Klick einmal aufrufen: Nummern von vorhin können auf "
        "eine andere Seite zeigen.",
        {"type": "object", "properties": {}},
    )
    async def web_elemente(args):
        antwort, fehler = await _browser_fragen("web_elemente")
        if fehler:
            return {"content": [{"type": "text", "text": fehler}],
                    "is_error": True}
        elemente = antwort.get("elemente") or []
        if not elemente:
            return {"content": [{"type": "text", "text":
                    "Auf der Seite ist nichts zu bedienen."}]}
        zeilen = []
        for e in elemente:
            teile = [f"{e.get('nummer')}. {e.get('art')}: "
                     f"{e.get('text') or '(ohne Beschriftung)'}"]
            # Was die Rueckfrage spaeter auffangen wird, steht hier schon
            # dabei -- dann weiss das Modell vorher, dass es nicht der
            # harmlose Weg ist, und muss nicht raten.
            if e.get("absenden"):
                teile.append("(schickt das Formular ab)")
            elif e.get("im_formular"):
                teile.append("(im Formular)")
            zeilen.append(" ".join(teile))
        if leuchten:
            leuchten("Websuche")
        return {"content": [{"type": "text", "text": "\n".join(zeilen)}]}

    @tool(
        "web_klicken",
        "Klickt ein Element auf der gezeigten Seite an — die Nummer kommt "
        "aus web_elemente. Vorher web_elemente aufrufen, sonst stimmt die "
        "Nummer womöglich nicht mehr.",
        {
            "type": "object",
            "properties": {
                "nummer": {"type": "integer",
                           "description": "Nummer aus web_elemente."},
            },
            "required": ["nummer"],
        },
    )
    async def web_klicken(args):
        antwort, fehler = await _browser_fragen(
            "web_klicken", nummer_element=args.get("nummer"))
        if fehler:
            return {"content": [{"type": "text", "text": fehler}],
                    "is_error": True}
        e = antwort.get("ergebnis") or {}
        if not e.get("geklickt"):
            return {"content": [{"type": "text", "text":
                    e.get("grund") or "Das ging nicht."}], "is_error": True}
        if leuchten:
            leuchten("Websuche")
        vermerken(f"web_klicken: {e.get('text')!r}")
        satz = f"Geklickt: {e.get('text') or 'das Element'}."
        if e.get("navigiert"):
            satz += " Die Seite hat gewechselt."
        if e.get("neues_fenster"):
            # Ehrlich gesagt statt verschwiegen: Der Link wollte ein neues
            # Fenster, und das gibt es hier nicht. Sonst stuende Sarvis da
            # und behauptete, er habe geklickt, waehrend nichts passiert.
            satz += (" Der Link wollte ein neues Fenster aufmachen — das "
                     "kann ich hier nicht, es ist nichts passiert.")
        return {"content": [{"type": "text", "text": satz}]}

    @tool(
        "web_tippen",
        "Schreibt Text in ein Eingabefeld der gezeigten Seite. Die Nummer "
        "kommt aus web_elemente. Abgeschickt wird dabei NICHT — dafür "
        "danach den Absende-Knopf mit web_klicken.",
        {
            "type": "object",
            "properties": {
                "nummer": {"type": "integer",
                           "description": "Nummer aus web_elemente."},
                "text": {"type": "string",
                         "description": "Was hineingeschrieben werden soll."},
            },
            "required": ["nummer", "text"],
        },
    )
    async def web_tippen(args):
        antwort, fehler = await _browser_fragen(
            "web_tippen", nummer_element=args.get("nummer"),
            text=str(args.get("text") or ""))
        if fehler:
            return {"content": [{"type": "text", "text": fehler}],
                    "is_error": True}
        e = antwort.get("ergebnis") or {}
        if not e.get("getippt"):
            return {"content": [{"type": "text", "text":
                    e.get("grund") or "Das ging nicht."}], "is_error": True}
        if leuchten:
            leuchten("Websuche")
        return {"content": [{"type": "text", "text":
                f"Eingetragen: {e.get('wert_danach') or e.get('text')}."}]}

    @tool(
        "web_zoom",
        "Macht die gezeigte Seite größer oder kleiner. Für 'mach das "
        "größer', 'zoom mal rein'. 1 ist die Normalgröße.",
        {
            "type": "object",
            "properties": {
                "faktor": {"type": "number",
                           "description": "0,5 bis 3. 1 ist normal."},
            },
            "required": ["faktor"],
        },
    )
    async def web_zoom(args):
        antwort, fehler = await _browser_fragen(
            "web_zoom", 6.0, faktor=args.get("faktor"))
        if fehler:
            return {"content": [{"type": "text", "text": fehler}],
                    "is_error": True}
        return {"content": [{"type": "text", "text":
                f"Auf {antwort.get('faktor')} gestellt."}]}

    @tool(
        "web_downloads",
        "Sagt, was von den gezeigten Seiten heruntergeladen wurde und wo "
        "es liegt. Für 'wo ist die Datei hin', 'hast du das runtergeladen'.",
        {"type": "object", "properties": {}},
    )
    async def web_downloads(args):
        antwort, fehler = await _browser_fragen("web_downloads", 6.0)
        if fehler:
            return {"content": [{"type": "text", "text": fehler}],
                    "is_error": True}
        dateien = antwort.get("dateien") or []
        if not dateien:
            return {"content": [{"type": "text", "text":
                    "Von der Seite wurde nichts heruntergeladen."}]}
        zeilen = [f"{d.get('name')} ({d.get('zustand')}) — {d.get('pfad')}"
                  for d in dateien[-6:]]
        return {"content": [{"type": "text", "text":
                f"{len(dateien)} Datei(en):\n" + "\n".join(zeilen)}]}

    return [programm_starten, programm_suchen, programm_beenden,
            web_zeigen, route_zeigen,
            web_lesen, web_elemente, web_klicken, web_tippen,
            web_zoom, web_downloads]
