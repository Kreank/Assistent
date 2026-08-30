"""Nachrichten und Radio -- zwei offene Dienste, kein Konto, kein Schluessel.

WARUM BEIDES IN EINER DATEI STEHT

Es beantwortet dieselbe Frage: was gerade in der Welt laeuft. Und beides
gibt es ohne Anmeldung -- die Tagesschau, weil sie oeffentlich-rechtlich
ist; das Radioverzeichnis, weil Freiwillige es pflegen. Dafuer gelten
Hausregeln. Die stehen hier nicht als Bitte im Kommentar, sondern als
Code: _Sperre haelt die 60 Abrufe je Stunde wirklich ein, und
_klick_melden meldet zurueck, was benutzt wurde.

Ein Kommentar "bitte nicht oefter als 60-mal" haelt niemand ein. Ein
Modell, das in einer Schleife nachfragt, kommt in einer Minute auf mehr,
und gesperrt wird dann nicht das Modell, sondern der Server.

WARUM DER RADIOTON NICHT UEBER DEN DRAHT GEHT

Sarvis' Stimme geht als rohes PCM zum Client (art "ton"). Fuer einen
Radiostream waere das der falsche Weg: Der Server lieferte stundenlang
Audio aus, das er selbst erst herunterlaedt und unveraendert
weiterreicht -- Arbeit, Bandbreite und Verzoegerung fuer nichts. Der
Client kann den Sender direkt anwaehlen, der Server steht nur im Weg.

Also geht nur die ADRESSE hinueber (art "radio"), und der Client haengt
sein eigenes Abspielwerk daran. Getrennt von der Sprachwiedergabe, damit
Sarvis ueber das laufende Radio reden kann, ohne es abzuwuergen: Der
Client dreht leiser, solange Ton ankommt, und wieder auf, wenn der Satz
verklungen ist. Beschrieben in einsatz/DRAHT.md, umgesetzt in
web/sarvis.js.

WOHIN DAS RADIO GEHT

An das Geraet, das gerade redet -- nicht an alle. Wer am Rechner "mach
Radio an" sagt, will es nicht aus dem Handy in der Jackentasche hoeren;
derselbe Grund, aus dem auch die gesprochene Antwort gezielt geht.

Das AUSschalten geht dagegen an alle, genau wie ton_stopp: Laeuft
irgendwo noch ein Sender, soll auch der aufhoeren. Ein Radio, das man
nicht mehr los wird, weil man inzwischen an einem anderen Geraet sitzt,
waere der schlechtere Fehler.

UND NUR AN GERAETE, DIE ES KOENNEN

Der Draht handelt Faehigkeiten schon aus: Jede Oberflaeche sagt bei der
Anmeldung, was sie kann. "kann_radio" kommt dazu -- die Weboberflaeche
meldet es, eine native App erst, wenn sie es umgesetzt hat.

Gefragt wird nach dem GERAET, das gerade redet, nicht nach irgendeinem.
Sonst sagt Sarvis am Rechner "laeuft", und der Ton ginge im Browser auf
dem Handy an -- oder nirgends. Ein Werkzeug, das erfolgreich aussieht
und nichts bewirkt, ist der schlimmere Fehler: Wer das dreimal erlebt,
fragt nicht mehr.
"""
import asyncio
import random
import re
import socket
import threading
import time
from collections import deque

import httpx
from claude_agent_sdk import tool

from .. import anzeige as anzeige_modul

ZEITGRENZE = 15.0

# Was eine Oberflaeche koennen muss, damit dort Radio spielt: ein
# eigenes Abspielwerk fuer eine Stream-Adresse, getrennt von der
# Sprachwiedergabe. Gemeldet wird das bei der Anmeldung in "kann",
# genau wie kann_rechner -- siehe einsatz/DRAHT.md.
FAEHIGKEIT = "kann_radio"

# Eine aussagekraeftige Kennung ist bei beiden Diensten Hausregel und
# beim Radioverzeichnis ausdrueckliche Bedingung: Wer sich nicht zu
# erkennen gibt, wird als Bot behandelt und irgendwann ausgesperrt.
KENNUNG = "Sarvis/1.0 (Sprachassistent; +https://sarvis.tech-artist.de)"


# ======================================================================
# Die Grenze, die wirklich gilt
# ======================================================================

class _Sperre:
    """Ein Zaehlwerk, das eine fremde Grenze einhaelt statt sie zu nennen.

    Die Tagesschau erlaubt fuer private Nutzung 60 Abrufe je Stunde.
    Das ist kein Vorschlag: Wer darueber liegt, wird abgewiesen, und
    zwar nicht nur mit dem einen Aufruf, der zu viel war.

    Deshalb ein gleitendes Fenster ueber die Zeitpunkte der letzten
    Abrufe -- nicht ein Zaehler, der zur vollen Stunde zurueckspringt.
    Bei so einem Zaehler laegen 59 Abrufe um 10:59 und 59 um 11:01
    beide "im Rahmen", waeren fuer den Dienst aber 118 in zwei Minuten.

    Mit Schloss, weil Sarvis Auftraege nebenlaeufig bearbeitet und zwei
    davon gleichzeitig fragen koennen.
    """

    def __init__(self, wie_viele: int, je_sekunden: float):
        self.wie_viele = wie_viele
        self.fenster = je_sekunden
        self._zeiten: deque[float] = deque()
        self._schloss = threading.Lock()

    def nehmen(self) -> bool:
        """Einen Platz belegen. False heisst: jetzt nicht."""
        with self._schloss:
            self._aufraeumen()
            if len(self._zeiten) >= self.wie_viele:
                return False
            self._zeiten.append(time.monotonic())
            return True

    def wieder_in(self) -> int:
        """Sekunden, bis wieder ein Platz frei wird."""
        with self._schloss:
            self._aufraeumen()
            if len(self._zeiten) < self.wie_viele or not self._zeiten:
                return 0
            return max(1, int(self._zeiten[0] + self.fenster
                              - time.monotonic()) + 1)

    def _aufraeumen(self) -> None:
        grenze = time.monotonic() - self.fenster
        while self._zeiten and self._zeiten[0] < grenze:
            self._zeiten.popleft()


# ======================================================================
# Tagesschau
# ======================================================================

# Ohne Schraegstrich am Ende: Mit ihm und ohne Parameter antwortet der
# Dienst mit 308 auf die Fassung ohne, und httpx folgt Umleitungen von
# sich aus nicht -- man bekaeme eine leere Antwort und suchte den Fehler
# im eigenen Code. Gemessen genau so.
TAGESSCHAU = "https://www.tagesschau.de/api2u/news"

TAGESSCHAU_SPERRE = _Sperre(60, 3600.0)

RESSORTS = ("inland", "ausland", "wirtschaft", "sport", "investigativ",
            "wissen")

# Die Nummern sind die des Dienstes, nicht unsere Erfindung. Sie
# stehen hier ausgeschrieben, weil ein Mensch "Sachsen" sagt und nicht
# "regions=13".
REGIONEN = {
    "baden-württemberg": 1, "bayern": 2, "berlin": 3, "brandenburg": 4,
    "bremen": 5, "hamburg": 6, "hessen": 7,
    "mecklenburg-vorpommern": 8, "niedersachsen": 9,
    "nordrhein-westfalen": 10, "rheinland-pfalz": 11, "saarland": 12,
    "sachsen": 13, "sachsen-anhalt": 14, "schleswig-holstein": 15,
    "thüringen": 16,
}

_MARKUP = re.compile(r"<[^>]+>")


def _region_nummer(text: str) -> int | None:
    """Aus 'Sachsen' oder 'sachsen anhalt' die Nummer des Dienstes."""
    schluessel = (text or "").strip().lower().replace(" ", "-")
    if not schluessel:
        return None
    if schluessel.isdigit():
        nummer = int(schluessel)
        return nummer if 1 <= nummer <= 16 else None
    if schluessel in REGIONEN:
        return REGIONEN[schluessel]
    # "nrw", "sachsen anhalt" und aehnliche Kurzformen trifft niemand
    # exakt -- deshalb ein Teiltreffer, bevor gar nichts gefunden wird.
    for name, nummer in REGIONEN.items():
        if schluessel in name or name.startswith(schluessel):
            return nummer
    return None


def _satz(meldung: dict) -> str:
    """Eine Meldung als EIN gesprochener Satz.

    Nicht der volle Artikel: Der laeuft ueber tausend Zeichen, und
    vorgelesen sind das Minuten fuer eine Meldung. Der Anreisser der
    Tagesschau ist bereits genau das, was ein Mensch beim Ueberfliegen
    liest -- Titel plus erster Satz.

    Kein Aufzaehlungszeichen davor. Was gesprochen wird, hat keine
    Spiegelstriche; ein Modell, das eine Liste mit '-' bekommt, liest
    sie vor.
    """
    titel = _MARKUP.sub("", meldung.get("title") or "").strip()
    titel = titel.rstrip(" .;:")
    erster = _MARKUP.sub("", meldung.get("firstSentence") or "").strip()
    if not titel:
        return ""
    if not erster:
        return titel + "."
    if erster[-1] not in ".!?":
        erster += "."
    return f"{titel}: {erster}"


# ======================================================================
# Radio Browser
# ======================================================================

# Der Dienst hat keinen festen Server, sondern einen Verbund. Der Name
# loest per DNS auf mehrere Spiegel auf; wer immer denselben nimmt,
# belastet einen und laesst die anderen leer stehen.
RADIO_POOL = "all.api.radio-browser.info"
SPIEGEL_FRIST = 3600.0

_spiegel_name = ""
_spiegel_zeit = 0.0

# Was gerade laeuft -- damit radio_aus sagen kann, was es ausmacht, und
# radio_an nicht zweimal denselben Sender anwirft.
_laeuft: dict = {}

# Die letzte Suche. radio_an greift darauf zurueck, statt neu zu suchen:
# Eine zweite Suche kann bei einem anderen Spiegel landen und eine
# andere Reihenfolge liefern -- dann spielt etwas anderes als das, was
# Sarvis gerade aufgezaehlt hat.
_gefunden: list[dict] = []


def _spiegel_suchen() -> str:
    """Einen der Spiegel des Verbunds -- ueber DNS, wie vorgesehen.

    Die IPs hinter dem Sammelnamen ruecklaeufig aufzuloesen ist der vom
    Dienst empfohlene Weg: Man bekommt die echten Namen (de1, de2, ...)
    und waehlt einen aus. Der Sammelname selbst taete es auch, aber dann
    entscheidet der DNS-Zwischenspeicher, und der bleibt eine Stunde
    lang beim selben Spiegel.

    Blockierend (getaddrinfo, gethostbyaddr) -- deshalb rufen die
    Werkzeuge das ueber asyncio.to_thread.
    """
    global _spiegel_name, _spiegel_zeit
    if _spiegel_name and time.time() - _spiegel_zeit < SPIEGEL_FRIST:
        return _spiegel_name
    namen: set[str] = set()
    try:
        for eintrag in socket.getaddrinfo(RADIO_POOL, 443,
                                          type=socket.SOCK_STREAM):
            adresse = eintrag[4][0]
            try:
                namen.add(socket.gethostbyaddr(adresse)[0])
            except OSError:
                continue
    except OSError:
        pass
    # Faellt die Aufloesung aus, tut es der Sammelname selbst. Lieber
    # ein Spiegel, den der DNS aussucht, als gar keine Nachrichten.
    _spiegel_name = "https://" + (random.choice(sorted(namen)) if namen
                                  else RADIO_POOL)
    _spiegel_zeit = time.time()
    return _spiegel_name


def _adresse(sender: dict) -> str:
    """url_resolved, weil url noch eine Umleitung sein kann."""
    return (sender.get("url_resolved") or sender.get("url") or "").strip()


def _taugt(sender: dict) -> bool:
    """Faellt beim Verzeichnis selbst gerade durch die Pruefung?

    lastcheckok ist das Ergebnis des letzten automatischen Abspielens
    durch den Dienst. Wer das ignoriert, bietet Sender an, die seit
    Monaten tot sind -- und Sarvis sagt "laeuft", waehrend nichts kommt.
    """
    return bool(_adresse(sender)) and sender.get("lastcheckok") == 1


def _rang(sender: dict) -> tuple:
    """Reihenfolge nach Abspielbarkeit, dann nach Beliebtheit.

    https zuerst: Die Weboberflaeche laeuft ueber https, und ein Browser
    verweigert dort jeden Ton von http -- ohne Fehlermeldung, die der
    Nutzer sehen wuerde. Ein http-Sender ist im Browser kein schlechter
    Sender, sondern gar keiner.

    Dann kein HLS: .m3u8 spielt ein schlichtes Audio-Element nur in
    Safari ab. Chrome und Firefox brauchen dafuer eine Bibliothek, und
    eine neue Abhaengigkeit ist es nicht wert.
    """
    adr = _adresse(sender)
    return (0 if adr.lower().startswith("https://") else 1,
            1 if sender.get("hls") else 0,
            -int(sender.get("clickcount") or 0),
            -int(sender.get("votes") or 0))


def _kurz(name: str) -> str:
    """Der Name, so weit er sich vorlesen laesst.

    Im Verzeichnis traegt jeder Sender selbst ein, wie er heisst, und
    viele schreiben dort ihre halbe Suchmaschinenoptimierung hinein.
    Gemessen, echter Eintrag: "0R - COFFEE LOUNGE || Background Music,
    Jazz, Lounge, Chill, Smooth, Acoustic, ..." -- 250 Zeichen fuer
    einen Sender. Fuenf davon aufgezaehlt sind eine Minute Vorlesen.

    Alles ab dem ersten senkrechten Strich oder Komma ist bei diesen
    Eintraegen Beiwerk; davor steht der Name. Was dann noch zu lang ist,
    war nie ein Name.
    """
    kurz = re.split(r"[|,]", name or "", maxsplit=1)[0]
    kurz = " ".join(kurz.split()).strip(" -–—")
    if not kurz:
        kurz = " ".join((name or "").split())[:60]
    return kurz[:60].strip() or "?"


def _beschreibung(sender: dict) -> str:
    """Ein Sender in einem gesprochenen Halbsatz."""
    teile = []
    land = (sender.get("country") or "").strip()
    if land:
        teile.append(land)
    rate = sender.get("bitrate") or 0
    codec = (sender.get("codec") or "").strip()
    if rate:
        teile.append(f"{rate} kBit" + (f" {codec}" if codec else ""))
    name = _kurz(sender.get("name") or "?")
    return name + (f" ({', '.join(teile)})" if teile else "")


async def _radio_rufen(weg: str, params: dict | None = None):
    """Ein Aufruf beim Verzeichnis. None heisst: ging nicht.

    Mit einem zweiten Versuch, und der ist hier keine Vorsicht, sondern
    gemessen: Von zwoelf frisch aufgebauten Verbindungen zum Spiegel
    scheitern regelmaessig ein bis drei -- vom Server aus wie vom Host,
    mit httpx wie mit curl. Das ist die Natur eines Verbunds, den
    Freiwillige betreiben, und kein Grund, dem Nutzer "antwortet nicht"
    zu sagen, wenn der zweite Versuch in 400 Millisekunden klappt.

    Beim zweiten Fehlschlag wird der gemerkte Spiegel verworfen. Beim
    naechsten Mal wird neu ausgesucht -- ist ein Spiegel wirklich weg,
    haengt Sarvis sonst eine Stunde lang an ihm fest.
    """
    global _spiegel_zeit
    grund = await asyncio.to_thread(_spiegel_suchen)
    for versuch in (1, 2):
        try:
            async with httpx.AsyncClient(
                    timeout=ZEITGRENZE,
                    headers={"User-Agent": KENNUNG,
                             "Accept": "application/json"}) as c:
                a = await c.get(grund + weg, params=params)
            if a.status_code != 200:
                return None
            return a.json()
        except ValueError:
            return None
        except httpx.HTTPError:
            if versuch == 1:
                await asyncio.sleep(0.4)
                continue
            _spiegel_zeit = 0.0
    return None


async def _klick_melden(kennung: str) -> str:
    """Den Klick anmelden -- und dabei die Adresse holen.

    /json/url/<uuid> tut beides in einem Aufruf: Es zaehlt den Sender
    als angehoert und antwortet mit seiner Stream-Adresse.

    Das Zaehlen ist die Gegenleistung fuer einen Dienst, der nichts
    kostet und niemanden registriert. Aus diesen Klicks entsteht genau
    die Beliebtheitsreihenfolge, nach der hier sortiert wird -- wer nur
    liest und nie meldet, lebt von der Arbeit der anderen und macht die
    Sortierung mit der Zeit schlechter.
    """
    d = await _radio_rufen(f"/json/url/{kennung}")
    if isinstance(d, dict) and d.get("ok"):
        return (d.get("url") or "").strip()
    return ""


# ======================================================================
# Der Draht
# ======================================================================

def _draht():
    """Der Traeger der geltenden Anzeige -- oder None.

    Ueber anzeige.aktuelle() und nicht ueber eine gemerkte Anzeige: Die
    Werkzeuge entstehen beim Hochfahren, der Netz-Traeger erst danach.
    Wer sich hier etwas merkt, merkt sich den falschen.
    """
    return anzeige_modul.aktuelle().draht()


def _kann_radio() -> bool:
    """Kann das Geraet, dem gerade geantwortet wird, Radio abspielen?

    Nicht "kann es irgendwer": Der Ton geht gezielt dorthin, wo gefragt
    wurde. Die UDP-Anzeige des Desktop-Betriebs meldet ohnehin nie eine
    Faehigkeit -- sie ist ein Fenster, kein Abspielwerk.
    """
    return bool(anzeige_modul.aktuelle().kann_hier(FAEHIGKEIT))


def _radio_senden(url: str, name: str) -> bool:
    """Die Stream-Adresse an das Geraet, das gerade redet."""
    traeger = _draht()
    if traeger is None or not hasattr(traeger, "senden_gezielt"):
        return False
    traeger.senden_gezielt(anzeige_modul.ziel(),
                           {"art": "radio", "url": url, "name": name})
    return True


def _radio_aus_senden() -> bool:
    """Das Aufhoeren an ALLE -- wie ton_stopp, und aus demselben Grund."""
    traeger = _draht()
    if traeger is None:
        return False
    traeger.senden({"art": "radio_aus"})
    return True


# ======================================================================
# Die Werkzeuge
# ======================================================================

def werkzeuge(protokoll, leuchten=None):

    def vermerken(was: str) -> None:
        if protokoll is not None:
            protokoll.merken(was)

    def leuchte(name: str) -> None:
        # "Websuche" und "Musik" statt eigener Kranzplaetze: Die Liste
        # der Werkzeuge im Anzeigenkranz steht in config.WERKZEUGE und
        # wird von mehreren Stellen zugleich gepflegt. Ein Name, den es
        # dort nicht gibt, leuchtet nirgends.
        if leuchten:
            leuchten(name)

    # --- Nachrichten ----------------------------------------------------

    @tool(
        "nachrichten",
        "Die aktuellen Nachrichten der Tagesschau — wahlweise nach "
        "Ressort (Inland, Ausland, Wirtschaft, Sport, Investigativ, "
        "Wissen) oder nach Bundesland. Liefert drei bis fünf Meldungen "
        "als kurze Sätze zum Vorlesen, nicht ganze Artikel.",
        {
            "type": "object",
            "properties": {
                "ressort": {"type": "string",
                            "enum": list(RESSORTS),
                            "description": "Ohne Angabe: alle Ressorts."},
                "region": {"type": "string",
                           "description": "Ein Bundesland, z.B. 'Sachsen' "
                                          "oder 'Nordrhein-Westfalen'. "
                                          "Dann kommen regionale Meldungen."},
                "anzahl": {"type": "integer",
                           "description": "Drei bis fünf, Vorgabe vier."},
            },
        },
    )
    async def nachrichten(args):
        leuchte("Websuche")
        wie_viele = max(1, min(5, int(args.get("anzahl") or 4)))
        params: dict = {}
        wovon = "Die Nachrichten"

        ressort = (args.get("ressort") or "").strip().lower()
        if ressort:
            if ressort not in RESSORTS:
                return {"content": [{"type": "text", "text":
                        f"Ein Ressort {ressort} gibt es nicht. Es gibt: "
                        + ", ".join(RESSORTS) + "."}], "is_error": True}
            params["ressort"] = ressort
            wovon = f"Die Nachrichten aus dem Ressort {ressort.capitalize()}"

        if args.get("region"):
            nummer = _region_nummer(args["region"])
            if nummer is None:
                return {"content": [{"type": "text", "text":
                        f"Ein Bundesland {args['region']} kenne ich nicht."}],
                        "is_error": True}
            params["regions"] = nummer
            wovon = f"Die Nachrichten aus {args['region'].strip()}"

        if not TAGESSCHAU_SPERRE.nehmen():
            minuten = max(1, TAGESSCHAU_SPERRE.wieder_in() // 60)
            return {"content": [{"type": "text", "text":
                    f"Ich habe die Tagesschau in dieser Stunde schon "
                    f"{TAGESSCHAU_SPERRE.wie_viele}-mal gefragt — mehr "
                    f"erlaubt sie für private Nutzung nicht. In etwa "
                    f"{minuten} Minuten geht es wieder."}], "is_error": True}

        # Kein zweiter Versuch wie beim Radioverzeichnis: Dort zaehlt
        # niemand mit, hier schon. Ein stiller Wiederholungsversuch waere
        # ein Abruf, den die Sperre nicht sieht -- und dann haelt sie die
        # Grenze nur noch ungefaehr ein. Ungefaehr ist bei einer fremden
        # Grenze dasselbe wie gar nicht.
        try:
            async with httpx.AsyncClient(
                    timeout=ZEITGRENZE,
                    headers={"User-Agent": KENNUNG}) as c:
                a = await c.get(TAGESSCHAU, params=params)
            if a.status_code != 200:
                raise httpx.HTTPError(str(a.status_code))
            d = a.json()
        except (httpx.HTTPError, ValueError):
            return {"content": [{"type": "text", "text":
                    "Die Tagesschau antwortet gerade nicht."}],
                    "is_error": True}

        saetze = []
        for m in (d.get("news") or []):
            # Videobeitraege und Webansichten haben oft keinen Anreisser
            # und nichts, was sich vorlesen liesse.
            if m.get("type") not in (None, "story"):
                continue
            satz = _satz(m)
            if satz:
                saetze.append(satz)
            if len(saetze) >= wie_viele:
                break

        if not saetze:
            return {"content": [{"type": "text", "text":
                    "Dazu gibt es gerade keine Meldungen."}]}
        return {"content": [{"type": "text", "text":
                f"{wovon}:\n" + "\n".join(saetze)}]}

    # --- Radio suchen ---------------------------------------------------

    @tool(
        "radio_suchen",
        "Radiosender im offenen Senderverzeichnis suchen — nach Name, "
        "Land, Sprache oder Genre. Spielt noch nichts ab; dafür ist "
        "radio_an da. Nützlich, wenn mehrere Sender zur Auswahl stehen "
        "sollen.",
        {
            "type": "object",
            "properties": {
                "name": {"type": "string",
                         "description": "z.B. 'Deutschlandfunk', 'MDR'"},
                "land": {"type": "string",
                         "description": "Ausgeschrieben und englisch, wie "
                                        "im Verzeichnis: 'Germany'"},
                "sprache": {"type": "string",
                            "description": "englisch: 'german', 'english'"},
                "genre": {"type": "string",
                          "description": "z.B. 'jazz', 'news', 'classical'"},
                "anzahl": {"type": "integer",
                           "description": "Höchstens 8, Vorgabe 5"},
            },
        },
    )
    async def radio_suchen(args):
        global _gefunden
        leuchte("Musik")
        wie_viele = max(1, min(8, int(args.get("anzahl") or 5)))
        params = {"hidebroken": "true", "order": "clickcount",
                  "reverse": "true", "limit": wie_viele * 6}
        for feld, wohin in (("name", "name"), ("land", "country"),
                            ("sprache", "language"), ("genre", "tag")):
            wert = (args.get(feld) or "").strip()
            if wert:
                params[wohin] = wert
        if len(params) == 4:
            return {"content": [{"type": "text", "text":
                    "Wonach soll ich suchen — ein Name, ein Land, eine "
                    "Sprache oder ein Genre?"}], "is_error": True}

        d = await _radio_rufen("/json/stations/search", params)
        if d is None:
            return {"content": [{"type": "text", "text":
                    "Das Senderverzeichnis antwortet gerade nicht."}],
                    "is_error": True}

        treffer = sorted((s for s in d if _taugt(s)), key=_rang)[:wie_viele]
        if not treffer:
            return {"content": [{"type": "text", "text":
                    "Dazu finde ich keinen Sender, der gerade läuft."}]}
        _gefunden = treffer
        return {"content": [{"type": "text", "text":
                "; ".join(_beschreibung(s) for s in treffer) + "."}]}

    # --- Radio an -------------------------------------------------------

    @tool(
        "radio_an",
        "Einen Radiosender abspielen — auf dem Gerät, von dem der Nutzer "
        "gerade spricht. Sag den Sendernamen so, wie ein Mensch ihn "
        "nennt. Der Ton läuft im Browser oder in der App, nicht über "
        "Sarvis' Stimme; Sarvis kann darüber weiterreden.",
        {
            "type": "object",
            "properties": {
                "sender": {"type": "string",
                           "description": "z.B. 'Deutschlandfunk', "
                                          "'MDR Jump', 'BBC World Service'"},
            },
            "required": ["sender"],
        },
    )
    async def radio_an(args):
        global _laeuft
        leuchte("Musik")
        gesucht = (args.get("sender") or "").strip()
        if not gesucht:
            return {"content": [{"type": "text", "text":
                    "Welchen Sender denn?"}], "is_error": True}

        # Vor der Suche fragen, nicht danach: Wenn hier ohnehin kein Ton
        # herauskommen kann, ist jeder Aufruf beim Verzeichnis vergeudet
        # -- und ein gemeldeter Klick fuer einen Sender, der nie lief,
        # verfaelscht dort die Beliebtheitsreihenfolge.
        if not _kann_radio():
            return {"content": [{"type": "text", "text":
                    "Auf diesem Gerät kann ich kein Radio abspielen — es "
                    "meldet kein eigenes Abspielwerk. Im Browser geht es; "
                    "in der App erst, wenn sie es kann."}], "is_error": True}

        # Erst in der letzten Suche nachsehen: Wenn Sarvis eben drei
        # Sender aufgezaehlt hat und der Nutzer einen davon nennt, soll
        # genau der laufen -- und nicht der, den eine zweite Suche bei
        # einem anderen Spiegel zufaellig nach oben sortiert.
        klein = gesucht.lower()
        sender = next((s for s in _gefunden
                       if klein in (s.get("name") or "").lower()), None)
        if sender is None:
            d = await _radio_rufen("/json/stations/search",
                                   {"name": gesucht, "hidebroken": "true",
                                    "order": "clickcount", "reverse": "true",
                                    "limit": 30})
            if d is None:
                return {"content": [{"type": "text", "text":
                        "Das Senderverzeichnis antwortet gerade nicht."}],
                        "is_error": True}
            tauglich = sorted((s for s in d if _taugt(s)), key=_rang)
            sender = tauglich[0] if tauglich else None
        if sender is None:
            return {"content": [{"type": "text", "text":
                    f"Einen Sender namens {gesucht} finde ich nicht."}],
                    "is_error": True}

        name = _kurz(sender.get("name") or gesucht)
        adresse = await _klick_melden(sender.get("stationuuid") or "")
        # Faellt die Klickmeldung aus, ist das kein Grund, nichts
        # abzuspielen -- die Adresse steht auch im Suchergebnis.
        adresse = adresse or _adresse(sender)
        if not adresse:
            return {"content": [{"type": "text", "text":
                    f"{name} hat gerade keine gültige Adresse."}],
                    "is_error": True}

        if not adresse.lower().startswith("https://"):
            # Ein Browser auf einer https-Seite laesst http-Ton nicht zu,
            # und zwar still. Lieber vorher sagen, warum nichts kommt.
            return {"content": [{"type": "text", "text":
                    f"{name} sendet unverschlüsselt über http — das "
                    f"blockiert der Browser. Such lieber einen anderen "
                    f"Sender oder eine andere Fassung davon."}],
                    "is_error": True}

        if not _radio_senden(adresse, name):
            return {"content": [{"type": "text", "text":
                    "Die Verbindung zu deinem Gerät ist gerade weg."}],
                    "is_error": True}

        _laeuft = {"name": name, "url": adresse}
        vermerken(f"radio_an: {name} läuft jetzt.")
        return {"content": [{"type": "text", "text":
                f"{name} läuft."}]}

    # --- Radio aus ------------------------------------------------------

    @tool(
        "radio_aus",
        "Das laufende Radio beenden. Betrifft nur das Radio, nicht "
        "Sarvis' Stimme.",
        {"type": "object", "properties": {}},
    )
    async def radio_aus(args):
        global _laeuft
        leuchte("Musik")
        lief = _laeuft.get("name") or ""
        _laeuft = {}
        # Hier wird NICHT nach kann_radio gefragt: Aufhoeren geht an
        # alle, und wer es nicht kennt, ueberspringt es ohnehin. Ein
        # "das kann dieses Geraet nicht", waehrend woanders noch Musik
        # laeuft, waere die falsche Antwort.
        if not _radio_aus_senden():
            return {"content": [{"type": "text", "text":
                    "Gerade ist keine Oberfläche verbunden."}],
                    "is_error": True}
        return {"content": [{"type": "text", "text":
                (f"{lief} ist aus." if lief else "Radio aus.")}]}

    return [nachrichten, radio_suchen, radio_an, radio_aus]
