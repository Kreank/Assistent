"""Der Endpunkt: eine Adresse, beliebig viele Oberflaechen.

    sarvis.tech-artist.de  ->  Caddy  ->  127.0.0.1:8900

Zwei Wege fuehren hier hinein:

    GET  /            die Oberflaeche selbst (HTML, JS, das Symbol)
    WS   /draht       der Ereignisstrom in beide Richtungen

WAS UEBER DEN DRAHT GEHT

    Server -> Oberflaeche   die zwoelf Anzeige-Arten aus anzeige.py,
                            dazu "ton" mit gesprochenem Audio und
                            "schirm" mit dem Bildstrom des Browsers
    Oberflaeche -> Server   "zuruf" (getippter Text), "sprache"
                            (aufgenommenes Audio), "antwort" (auf eine
                            gestellte Frage), "hier" (Lebenszeichen)
                            sowie "schirm_an", "klick", "taste",
                            "rollen" -- die Fernsteuerung des Browsers

DIE REIHENFOLGE BEIM ANMELDEN IST NICHT BELIEBIG

Der Schluessel geht als erste Nachricht ueber die schon offene
Verbindung, nicht als Query-Parameter in der Adresse. Der Unterschied
ist nicht kosmetisch: Eine URL steht im Zugriffslog von Caddy, im
Verlauf des Browsers und in jedem Weiterleitungs-Header. Ein
Schluessel, der dort steht, ist kein Geheimnis mehr.

Bis die Anmeldung durch ist, wird nichts gesendet und nichts
entgegengenommen ausser genau dieser einen Nachricht. Wer nach
ANMELDE_FRIST nicht angemeldet ist, fliegt.

WARUM KEIN "WER ZUERST KOMMT"

Mehrere Oberflaechen duerfen gleichzeitig verbunden sein -- das ist der
Sinn der Sache: Handy und Dev-PC zeigen dasselbe. Sprechen darf
trotzdem nur eine zur Zeit, denn es gibt nur ein Gespraech und einen
Gespraechsfaden. Ein Zuruf vom Handy, waehrend der Dev-PC gerade
aufnimmt, ist deshalb kein Fehler, sondern dasselbe wie Reinreden: Er
unterbricht. Das entscheidet aber die Schleife in main.py, nicht dieser
Server -- er reicht nur weiter.
"""
import asyncio
import base64
import json
import logging
import time
from pathlib import Path

from aiohttp import WSMsgType, web

from .. import config
from . import geraete
from .fernsicht import Fernsicht
from .traeger import NetzTraeger, Oberflaeche, als_text

log = logging.getLogger("sarvis.netz")

# Wo die Oberflaeche liegt. Neben dem Quelltext, nicht unter DATEN:
# Sie ist Programm und gehoert ins Git.
WEB = config.WURZEL / "web"

# Wie lange eine Verbindung Zeit hat, sich anzumelden.
ANMELDE_FRIST = 10.0

# Groesste Nachricht, die eine Oberflaeche schicken darf. Sprache ist
# das Groesste, was vorkommt: 30 Sekunden bei 16 kHz als int16 sind
# 960 KB, als base64 rund 1,3 MB. Vier Megabyte lassen Luft und
# verhindern trotzdem, dass jemand den Speicher vollaeuft.
NACHRICHT_MAX = 4 * 1024 * 1024


class Endpunkt:
    """Haelt die Verbindungen und reicht zwischen Netz und Sarvis durch.

    Kennt Sarvis selbst NICHT. Was ein Zuruf bedeutet, entscheidet die
    Schleife; hier wird er nur entgegengenommen und weitergegeben. Das
    ist Absicht: Ein Endpunkt, der Gespraechslogik enthaelt, ist die
    zweite Stelle, an der man sie spaeter aendern muss.
    """

    def __init__(self, zuruf_an=None, sprache_an=None, strom_an=None,
                 weg_an=None):
        """zuruf_an(text, geraet)        -- eine getippte Zeile kam an
        sprache_an(proben, geraet)    -- eine fertige Aufnahme kam an
        strom_an(daten, rate, geraet) -- ein Stueck Dauerstrom kam an
        weg_an(geraet)                -- eine Oberflaeche ist gegangen
        Alle vier werden in der Ereignisschleife von Sarvis gerufen.
        """
        self.zuruf_an = zuruf_an
        self.sprache_an = sprache_an
        self.strom_an = strom_an
        self.weg_an = weg_an
        self.traeger: NetzTraeger | None = None
        # Wer Sarvis' Browser gerade zusieht und darin klickt. Der
        # Endpunkt haelt das Buch nicht selbst -- siehe fernsicht.py.
        self.fernsicht = Fernsicht()

    # --- HTTP ------------------------------------------------------------

    async def _seite(self, anfrage: web.Request) -> web.StreamResponse:
        datei = WEB / "index.html"
        if not datei.is_file():
            return web.Response(
                status=503,
                text="Die Oberfläche ist noch nicht gebaut.",
            )
        return web.FileResponse(datei)

    async def _leben(self, anfrage: web.Request) -> web.Response:
        """Fuer Caddy und fuers Nachsehen -- verraet nichts Vertrauliches."""
        return web.json_response({
            "wach": True,
            "oberflaechen": self.traeger.wie_viele() if self.traeger else 0,
        })

    # --- WebSocket -------------------------------------------------------

    async def _draht(self, anfrage: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30.0, max_msg_size=NACHRICHT_MAX)
        await ws.prepare(anfrage)

        oberflaeche = await self._anmelden(ws)
        if oberflaeche is None:
            return ws

        log.info("Oberfläche verbunden: %s", oberflaeche.name)
        self.traeger.dazu(oberflaeche)
        sender = asyncio.create_task(self._senden(ws, oberflaeche))
        try:
            await self._empfangen(ws, oberflaeche)
        finally:
            sender.cancel()
            self.traeger.weg(oberflaeche)
            # Vor allem anderen: Sieht niemand mehr zu, hoert der
            # Bildstrom auf. Eine geschlossene Verbindung ist der
            # haeufigste Weg, wie ein Zuschauer verschwindet -- haeufiger
            # als das Umlegen des Schalters.
            try:
                await self.fernsicht.weg(oberflaeche)
            except Exception:
                pass
            if self.weg_an is not None:
                # Damit der Weckwort-Strom nicht auf eine Quelle wartet,
                # die es nicht mehr gibt.
                try:
                    await self.weg_an(oberflaeche.name)
                except Exception:
                    pass
            log.info("Oberfläche weg: %s", oberflaeche.name)
        return ws

    async def _anmelden(self, ws) -> Oberflaeche | None:
        """Die erste Nachricht muss der Schluessel sein.

        Der Vergleich laeuft in einem Faden: Er liest eine Datei und
        rechnet einen Hash, und beides gehoert nicht in die
        Ereignisschleife, die gleichzeitig ein Gespraech traegt.
        """
        try:
            erste = await asyncio.wait_for(ws.receive(), ANMELDE_FRIST)
        except asyncio.TimeoutError:
            await ws.close(code=4401, message=b"keine Anmeldung")
            return None
        if erste.type is not WSMsgType.TEXT:
            await ws.close(code=4401, message=b"keine Anmeldung")
            return None
        try:
            m = json.loads(erste.data)
        except ValueError:
            await ws.close(code=4400, message=b"unlesbar")
            return None

        name = await asyncio.to_thread(geraete.pruefen, m.get("schluessel", ""))
        if name is None:
            # Bewusst dieselbe Antwort wie bei fehlender Anmeldung und
            # bewusst ohne Hinweis, WAS falsch war.
            await ws.close(code=4401, message=b"kein Zugang")
            return None

        # Was diese Oberflaeche kann, sagt sie selbst. Ein Browser
        # meldet nichts -- er DARF keine Programme starten, und das ist
        # richtig so. Eine native App meldet "kann_rechner".
        koennen = {str(f) for f in (m.get("kann") or []) if str(f)}
        o = Oberflaeche(name, kann_browser=bool(m.get("kann_browser")),
                        faehigkeiten=koennen)
        await ws.send_str(als_text({
            "art": "willkommen",
            "geraet": name,
            "seit": time.time(),
        }))
        return o

    async def _senden(self, ws, o: Oberflaeche) -> None:
        """Was in der Schlange liegt, hinausschicken."""
        try:
            while True:
                felder = await o.schlange.get()
                await ws.send_str(als_text(felder))
        except (asyncio.CancelledError, ConnectionResetError):
            raise
        except Exception as e:
            log.warning("Senden an %s ging nicht: %s", o.name, e)

    async def _empfangen(self, ws, o: Oberflaeche) -> None:
        async for nachricht in ws:
            if nachricht.type is not WSMsgType.TEXT:
                continue
            try:
                m = json.loads(nachricht.data)
            except ValueError:
                continue
            await self._verarbeiten(m, o)

    async def _verarbeiten(self, m: dict, o: Oberflaeche) -> None:
        art = str(m.get("art") or "")

        if art == "zuruf":
            text = str(m.get("text") or "").strip()
            if text and self.zuruf_an is not None:
                await self.zuruf_an(text, o.name)

        elif art == "sprache":
            proben = _proben_aus(m.get("daten"), int(m.get("rate") or 0))
            if proben is not None and self.sprache_an is not None:
                await self.sprache_an(proben, o.name)

        elif art == "strom":
            # Der Dauerstrom fuers Weckwort. Bewusst NICHT dekodiert und
            # nicht geprueft: Es kommen mehrere Buendel je Sekunde, und
            # was davon Sprache ist, entscheidet der VAD im
            # Weckwort-Faden. Hier waere jede Rechnung Arbeit in der
            # Ereignisschleife, die gleichzeitig ein Gespraech traegt.
            if self.strom_an is not None:
                await self.strom_an(m.get("daten"),
                                    int(m.get("rate") or 0), o.name)

        elif art == "antwort":
            # Die Antwort auf eine Frage, die WIR gestellt haben.
            o.antwort(str(m.get("nummer") or ""), m.get("inhalt") or {})

        elif art == "hier":
            pass  # Lebenszeichen, aiohttp haelt die Verbindung selbst wach

        # --- Die Fernsicht ------------------------------------------------
        # Alles ab hier erreicht nur, wer angemeldet ist: _anmelden()
        # laeuft VOR _empfangen(), und wer dort durchfaellt, bekommt die
        # Verbindung geschlossen und kommt nie in diese Methode. Ein
        # "klick" von einer unangemeldeten Verbindung ist damit nicht
        # unwahrscheinlich, sondern unmoeglich.
        #
        # Warum hier trotzdem NICHT nachgefragt wird, obwohl Sarvis' eigene
        # Klicks eine Rueckfrage ausloesen: siehe fernsicht.py, der lange
        # Block ueber klick(). Kurz -- die Rueckfrage schuetzt vor Sarvis,
        # nicht vor dem Menschen.

        elif art == "schirm_an":
            await self.fernsicht.schalten(o, bool(m.get("an")))

        elif art == "klick":
            await self.fernsicht.klick(o, m)

        elif art == "taste":
            await self.fernsicht.taste(o, m)

        elif art == "rollen":
            await self.fernsicht.rollen(o, m)

    # --- Aufbau ----------------------------------------------------------

    def anwendung(self, traeger: NetzTraeger) -> web.Application:
        self.traeger = traeger
        app = web.Application(client_max_size=NACHRICHT_MAX)
        app.router.add_get("/", self._seite)
        app.router.add_get("/leben", self._leben)
        app.router.add_get("/draht", self._draht)
        if WEB.is_dir():
            app.router.add_static("/dabei/", WEB, name="dabei")
        # Die Spotify-Anmeldung. Zwei Wege ohne Geraeteschluessel --
        # Spotify hat keinen; was stattdessen schuetzt, steht in
        # netz/spotify.py.
        from . import spotify
        spotify.anmelden(app)
        return app


def _proben_aus(daten, rate: int):
    """base64-PCM in ein float32-Array -- oder None, wenn es nicht passt.

    Der Client schickt int16, weil das die Haelfte von float32 ist und
    fuer Sprache verlustfrei genug. Whisper will float32 zwischen -1
    und 1, also wird hier geteilt und nicht gerundet.
    """
    if not daten or rate <= 0:
        return None
    try:
        import numpy as np
        roh = base64.b64decode(daten, validate=True)
        if not roh or len(roh) % 2:
            return None
        return (np.frombuffer(roh, dtype="<i2").astype("float32") / 32768.0)
    except Exception:
        return None


async def starten(endpunkt: Endpunkt, traeger: NetzTraeger,
                  hafen: int = 8900) -> web.AppRunner:
    """Den Endpunkt hochfahren. Gibt den Runner zum spaeteren Beenden.

    Nur auf 127.0.0.1: Nach aussen fuehrt ausschliesslich Caddy, und das
    bringt HTTPS mit. Ein Endpunkt, der selbst am offenen Netz haengt,
    haette einen zweiten Weg hinein -- einen ohne Zertifikat.
    """
    app = endpunkt.anwendung(traeger)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    seite = web.TCPSite(runner, "127.0.0.1", hafen)
    await seite.start()
    log.info("Endpunkt hört auf 127.0.0.1:%d", hafen)
    return runner
