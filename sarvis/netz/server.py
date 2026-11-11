"""Der Endpunkt: eine Adresse, beliebig viele Oberflaechen.

    sarvis.tech-artist.de  ->  Caddy  ->  127.0.0.1:8900

Zwei Wege fuehren hier hinein:

    GET  /            die Oberflaeche selbst (HTML, JS, das Symbol)
    GET  /blatt/<k>   ein Bericht, ein PDF, eine Word-Datei
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

from .. import config, gespraeche
from ..werkzeuge import eingang
from . import blaetter, geraete
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


# Wie oft hoechstens ueber DIESELBE unbekannte Art gemeckert wird.
UNBEKANNT_PAUSE = 60.0


class Endpunkt:
    """Haelt die Verbindungen und reicht zwischen Netz und Sarvis durch.

    Kennt Sarvis selbst NICHT. Was ein Zuruf bedeutet, entscheidet die
    Schleife; hier wird er nur entgegengenommen und weitergegeben. Das
    ist Absicht: Ein Endpunkt, der Gespraechslogik enthaelt, ist die
    zweite Stelle, an der man sie spaeter aendern muss.
    """

    def __init__(self, zuruf_an=None, sprache_an=None, strom_an=None,
                 auto_an=None, datei_an=None, weg_an=None,
                 faden_an=None, da_an=None):
        """zuruf_an(text, geraet)        -- eine getippte Zeile kam an
        sprache_an(proben, geraet)    -- eine fertige Aufnahme kam an
        strom_an(daten, rate, geraet) -- ein Stueck Dauerstrom kam an
        auto_an(an, geraet)             -- die Oberflaeche sitzt im Auto
        datei_an(pfad, geraet)          -- eine Datei kam herein
        weg_an(geraet)                -- eine Oberflaeche ist gegangen
        faden_an(art, m, geraet)      -- ein Fadenbefehl (faden_neu, ...)
        da_an(geraet)                 -- eine Oberflaeche ist angemeldet
        Alle werden in der Ereignisschleife von Sarvis gerufen.
        """
        self.faden_an = faden_an
        self.da_an = da_an
        self.zuruf_an = zuruf_an
        self.sprache_an = sprache_an
        self.strom_an = strom_an
        self.auto_an = auto_an
        self.datei_an = datei_an
        # Wann zuletzt ueber welche unbekannte Art gemeckert wurde.
        self._gemeckert: dict[str, float] = {}
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

    async def _datei(self, anfrage: web.Request) -> web.Response:
        """Eine Datei, die jemand aus der App herueberschickt.

        WARUM HTTP UND NICHT DER DRAHT: Der traegt 4 MB je Nachricht, und
        base64 blaeht um ein Drittel auf -- eine 5-MB-Datei passt nicht
        mehr. In Stuecke zerlegen hiesse, im Protokoll eine
        Zusammensetz-Logik zu fuehren samt der Frage, was bei einem
        abgebrochenen Stueck geschieht. Das kann HTTP schon.

        ANMELDUNG: Derselbe Geraeteschluessel wie am Draht, hier im
        Kopf "X-Sarvis-Schluessel". Nicht als Abfrage in der Adresse:
        Adressen landen in Protokollen und im Verlauf des Browsers,
        Koepfe nicht.

        Bewusst KEINE Ausnahme fuer "ist ja nur eine Datei": Wer
        hochladen darf, fuellt Sarvis' Eingang und damit seinen Kontext.
        """
        schluessel = anfrage.headers.get("X-Sarvis-Schluessel", "")
        name = await asyncio.to_thread(geraete.pruefen, schluessel)
        if name is None:
            # Dieselbe Antwort wie am Draht und ebenso ohne Hinweis,
            # WAS falsch war.
            return web.json_response({"fehler": "kein Zugang"}, status=401)

        if anfrage.content_length and \
                anfrage.content_length > config.DATEI_MAX:
            return web.json_response(
                {"fehler": "zu gross",
                 "hoechstens": config.DATEI_MAX}, status=413)

        try:
            teile = await anfrage.multipart()
            feld = await teile.next()
        except Exception:
            feld = None
        if feld is None or feld.name != "datei":
            return web.json_response(
                {"fehler": "kein Feld 'datei'"}, status=400)

        dateiname = feld.filename or "datei"
        if not eingang.endung_erlaubt(dateiname):
            # Die Endungsliste ist eine Positivliste. Was hier auflaeuft,
            # ist entweder wirklich unerwuenscht oder eine Endung, an die
            # niemand gedacht hat -- deshalb wird sie mitgeteilt, statt
            # nur "nein" zu sagen.
            return web.json_response(
                {"fehler": "diese Art Datei nehme ich nicht",
                 "endung": Path(dateiname.lower()).suffix},
                status=415)

        # Stueckweise lesen und dabei mitzaehlen: Ohne das koennte ein
        # Client ohne content_length beliebig viel schicken.
        roh = bytearray()
        while True:
            brocken = await feld.read_chunk(64 * 1024)
            if not brocken:
                break
            roh += brocken
            if len(roh) > config.DATEI_MAX:
                return web.json_response({"fehler": "zu gross"}, status=413)
        if not roh:
            return web.json_response({"fehler": "leer"}, status=400)

        pfad = await asyncio.to_thread(
            eingang.ablegen, dateiname, bytes(roh), name)
        if self.datei_an is not None:
            await self.datei_an(pfad, name)
        return web.json_response({"gut": True, "name": pfad.name,
                                  "bytes": len(roh)})

    async def _dateien(self, anfrage: web.Request) -> web.Response:
        """Was es fuer die App zum Herunterladen gibt -- und was sie schickte.

        Ein Blatt geht nur an Oberflaechen, die gerade verbunden sind. Was
        Sarvis verschickt, waehrend die App zu ist, waere sonst nur noch in
        seinem Satz "liegt bereit" vorhanden. Diese Liste holt die App beim
        Verbinden und nach jedem Datei-Blatt.

        Mit Geraeteschluessel im Kopf wie /datei: Die Liste selbst ist die
        Sammlung der geheimen Adressen.
        """
        schluessel = anfrage.headers.get("X-Sarvis-Schluessel", "")
        if await asyncio.to_thread(geraete.pruefen, schluessel) is None:
            return web.json_response({"fehler": "kein Zugang"}, status=401)
        from . import blaetter

        def von_dir():
            try:
                alle = sorted((d for d in config.EINGANG.glob("*")
                               if d.is_file()),
                              key=lambda d: d.stat().st_mtime, reverse=True)
            except OSError:
                return []
            return [{"datei": d.name, "bytes": d.stat().st_size,
                     "seit": d.stat().st_mtime} for d in alle[:60]]

        von_sarvis = await asyncio.to_thread(blaetter.dateien)
        geschickt = await asyncio.to_thread(von_dir)
        return web.json_response({"von_sarvis": von_sarvis,
                                  "von_dir": geschickt},
                                 headers={"Cache-Control": "no-store"})

    async def _waechter(self, anfrage: web.Request) -> web.StreamResponse:
        """Der Service Worker an der WURZEL -- sonst reicht er nur bis /dabei/.

        Unter /dabei/waechter.js registriert, galt er nur fuer /dabei/ und
        sah weder die Seite noch das Teilen (POST /teilen). Fuers Teilen
        aus dem Android-Menue muss er genau diesen Aufruf abfangen.
        """
        return web.FileResponse(WEB / "waechter.js", headers={
            "Content-Type": "text/javascript; charset=utf-8",
            "Cache-Control": "no-cache"})

    async def _teilen(self, anfrage: web.Request) -> web.Response:
        """Rueckfall, wenn das Teilen am Service Worker vorbeiging.

        Normal faengt waechter.js diesen POST ab und reicht die Datei an
        die Seite, die sie MIT Schluessel hochlaedt. Kommt er hier an,
        war der Worker noch nicht aktiv -- dann nichts annehmen (es fehlt
        der Schluessel) und zur Seite zurueck.
        """
        raise web.HTTPSeeOther("/?geteilt=verpasst")

    # --- Verlauf, Faeden, Ablage, Push (seit 11.11.2026) -----------------
    #
    # Alles hier traegt den Geraeteschluessel im Kopf, wie /datei und
    # /dateien. Es sind Gespraechsinhalte und die Liste der geheimen
    # Blatt-Adressen. Vertrag: einsatz/DRAHT.md, "Gespraechsverlauf und
    # Faeden", "Ablage", "Benachrichtigungen".

    async def _wer(self, anfrage: web.Request) -> str | None:
        schluessel = anfrage.headers.get("X-Sarvis-Schluessel", "")
        return await asyncio.to_thread(geraete.pruefen, schluessel)

    @staticmethod
    def _kein_zugang() -> web.Response:
        return web.json_response({"fehler": "kein Zugang"}, status=401)

    @staticmethod
    def _json(daten, status: int = 200) -> web.Response:
        return web.json_response(daten, status=status,
                                 headers={"Cache-Control": "no-store"})

    async def _faeden(self, anfrage: web.Request) -> web.Response:
        if await self._wer(anfrage) is None:
            return self._kein_zugang()
        aktiv = await asyncio.to_thread(gespraeche.aktiv)
        liste = await asyncio.to_thread(gespraeche.faeden)
        return self._json({"aktiv": aktiv, "liste": liste})

    async def _verlauf(self, anfrage: web.Request) -> web.Response:
        """Die Eintraege eines Fadens, juengste zuletzt, aeltere seitenweise."""
        if await self._wer(anfrage) is None:
            return self._kein_zugang()
        q = anfrage.query
        kennung = q.get("faden") or await asyncio.to_thread(gespraeche.aktiv)
        try:
            vor = int(q.get("vor") or 0)
            anzahl = int(q.get("anzahl") or 60)
        except ValueError:
            return self._json({"fehler": "vor/anzahl muessen Zahlen sein"}, 400)
        faden = await asyncio.to_thread(gespraeche.faden, kennung)
        if faden is None:
            return self._json({"fehler": "diesen Faden gibt es nicht"}, 404)
        faden.pop("sitzung", None)
        seite = await asyncio.to_thread(gespraeche.verlauf, kennung, vor, anzahl)
        return self._json({"faden": faden, **seite})

    async def _suche(self, anfrage: web.Request) -> web.Response:
        if await self._wer(anfrage) is None:
            return self._kein_zugang()
        wort = anfrage.query.get("q", "")
        return self._json({"treffer": await asyncio.to_thread(
            gespraeche.suchen, wort)})

    async def _ablage(self, anfrage: web.Request) -> web.Response:
        """Was Sarvis erzeugt hat -- und was du ihm geschickt hast."""
        if await self._wer(anfrage) is None:
            return self._kein_zugang()
        sorte = anfrage.query.get("sorte", "")
        if sorte and sorte not in ("markdown", "html", "datei"):
            return self._json({"fehler": "sorte: markdown, html oder datei"}, 400)
        liste = await asyncio.to_thread(gespraeche.ablage, sorte)

        def von_dir():
            try:
                alle = sorted((d for d in config.EINGANG.glob("*")
                               if d.is_file()),
                              key=lambda d: d.stat().st_mtime, reverse=True)
            except OSError:
                return []
            return [{"datei": d.name, "bytes": d.stat().st_size,
                     "seit": d.stat().st_mtime} for d in alle[:60]]

        return self._json({"eintraege": liste,
                           "von_dir": await asyncio.to_thread(von_dir)})

    async def _ablage_oeffnen(self, anfrage: web.Request) -> web.Response:
        """Ein Stueck aus der Ablage holen -- und seine Adresse erneuern.

        Eine Blatt-Adresse gilt 7 bzw. 30 Tage (blaetter.py). Die Ablage
        haelt laenger. Wer hier mit Schluessel fragt, bekommt dieselbe
        Adresse mit neuer Frist, solange die Datei noch da ist.
        """
        if await self._wer(anfrage) is None:
            return self._kein_zugang()
        try:
            m = await anfrage.json()
        except Exception:
            return self._json({"fehler": "JSON erwartet"}, 400)
        schl = str((m or {}).get("schluessel") or "")
        zeile = await asyncio.to_thread(gespraeche.abgelegt, schl)
        if not zeile:
            return self._json({"fehler": "gibt es nicht"}, 404)
        if zeile["sorte"] == "markdown":
            return self._json({"sorte": "markdown", "titel": zeile["titel"],
                               "inhalt": zeile["inhalt"]})
        typ = zeile["typ"] or ("html" if zeile["sorte"] == "html" else "beliebig")
        bis = await asyncio.to_thread(
            blaetter.erneuern, schl, zeile["pfad"], typ, zeile["titel"],
            zeile["datei"],
            blaetter.FRIST_VERSAND_TAGE if zeile["sorte"] == "datei" else 0.0)
        if not bis:
            return self._json({"fehler": "liegt nicht mehr da"}, 410)
        return self._json({"sorte": zeile["sorte"], "titel": zeile["titel"],
                           "datei": zeile["datei"], "bytes": zeile["bytes"],
                           "adresse": blaetter.adresse(schl), "bis": bis})

    async def _push_schluessel(self, anfrage: web.Request) -> web.Response:
        name = await self._wer(anfrage)
        if name is None:
            return self._kein_zugang()
        from . import push
        oeffentlich = await asyncio.to_thread(push.oeffentlich)
        abos = await asyncio.to_thread(push.abos, name)
        return self._json({"schluessel": oeffentlich, "abos": len(abos)})

    async def _push_abo(self, anfrage: web.Request) -> web.Response:
        name = await self._wer(anfrage)
        if name is None:
            return self._kein_zugang()
        from . import push
        try:
            abo = await anfrage.json()
        except Exception:
            return self._json({"fehler": "JSON erwartet"}, 400)
        grund = await asyncio.to_thread(push.abo_speichern, abo, name)
        if grund:
            return self._json({"fehler": grund}, 400)
        return self._json({"gut": True})

    async def _push_abmelden(self, anfrage: web.Request) -> web.Response:
        name = await self._wer(anfrage)
        if name is None:
            return self._kein_zugang()
        from . import push
        try:
            m = await anfrage.json()
        except Exception:
            return self._json({"fehler": "JSON erwartet"}, 400)
        weg = await asyncio.to_thread(push.abo_loeschen,
                                      str((m or {}).get("endpoint") or ""), name)
        return self._json({"gut": True, "entfernt": weg})

    async def _push_probe(self, anfrage: web.Request) -> web.Response:
        """Eine Probe an die Abos DIESES Geraets -- zum Ausprobieren."""
        name = await self._wer(anfrage)
        if name is None:
            return self._kein_zugang()
        from . import push
        ergebnis = await asyncio.to_thread(push.alle_senden, {
            "titel": "Sarvis", "text": "Benachrichtigungen kommen an.",
            "art": "probe", "zeit": time.time()}, name)
        return self._json(ergebnis)

    # --- WebSocket -------------------------------------------------------

    async def _draht(self, anfrage: web.Request) -> web.WebSocketResponse:
        ws = web.WebSocketResponse(heartbeat=30.0, max_msg_size=NACHRICHT_MAX)
        await ws.prepare(anfrage)

        oberflaeche = await self._anmelden(ws)
        if oberflaeche is None:
            return ws

        log.info("Oberfläche verbunden: %s", oberflaeche.name)
        self.traeger.dazu(oberflaeche)
        if self.da_an is not None:
            # Gleich nach dem willkommen: welche Faeden es gibt und welcher
            # gilt. Geht an alle -- ein Zustand, den die anderen schon
            # kennen, schadet ihnen nicht.
            try:
                await self.da_an(oberflaeche.name)
            except Exception as e:
                log.warning("Begruessung an %s: %s", oberflaeche.name, e)
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

        # --- Gespraechsfaeden (seit 11.11.2026) ---------------------------
        # Es gibt EIN Hirn und damit einen aktiven Faden fuer alle. Wer
        # wechselt, wechselt fuer jede Oberflaeche; alle bekommen danach
        # "faeden" mit dem neuen Stand. Was die Befehle tun, entscheidet
        # main.py -- hier wird nur weitergereicht.
        elif art == "faden_neu":
            if self.faden_an is not None:
                await self.faden_an(art, m, o.name)

        elif art == "faden_wechseln":
            if self.faden_an is not None:
                await self.faden_an(art, m, o.name)

        elif art == "faden_umbenennen":
            if self.faden_an is not None:
                await self.faden_an(art, m, o.name)

        elif art == "faden_archivieren":
            if self.faden_an is not None:
                await self.faden_an(art, m, o.name)

        elif art == "auto":
            # Die Oberflaeche sagt, ob sie gerade im Auto steckt.
            #
            # Warum das nicht bei der Anmeldung steht: Die laeuft einmal
            # beim Verbinden. Ein- und ausgestiegen wird mitten in einer
            # Verbindung, oft Stunden spaeter.
            #
            # Was der Server damit macht, steht im Horcher. Kurz: Er
            # erkennt Dauerlaerm ohnehin selbst an seinem Ton -- dieses
            # Wort macht ihn nur sicherer, weil es Auto von "lautes
            # Zimmer" unterscheidet.
            #
            # Auf das Feld wird ausdruecklich geprueft statt m.get("an")
            # zu nehmen. Ein fehlendes Feld ergaebe sonst stillschweigend
            # False -- also "nicht im Auto", und zwar genau dann, wenn
            # jemand es "im_auto" oder "modus" genannt hat. Die Funktion
            # bliebe aus, im Protokoll stuende nichts, und gefunden waere
            # es erst nach der dritten erfolglosen Fahrt.
            if "an" not in m:
                log.warning('auto von %s ohne Feld "an" (bekam: %s) -- '
                            "ignoriert. Tippfehler im Feldnamen?",
                            o.name, sorted(k for k in m if k != "art"))
            elif self.auto_an is not None:
                await self.auto_an(bool(m["an"]), o.name)

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

        else:
            # Unbekannte Arten werden ignoriert -- das steht so im
            # Protokoll und ist richtig: Eine neuere App darf einem
            # aelteren Server etwas schicken, das er noch nicht kennt,
            # ohne dass die Verbindung bricht.
            #
            # Ignorieren heisst aber nicht verschweigen. Wer sich beim
            # Namen vertippt -- "auto_modus" statt "auto", "im_auto"
            # statt "an" --, bekommt sonst NICHTS zu sehen: Die Funktion
            # bleibt einfach aus, alles wirkt normal, und gefunden wird
            # es erst nach der dritten erfolglosen Fahrt.
            #
            # Gedrosselt, weil ein Client, der eine unbekannte Art in
            # Schleife schickt, sonst das Protokoll flutet.
            jetzt = time.monotonic()
            if jetzt - self._gemeckert.get(art, -UNBEKANNT_PAUSE * 2) \
                    >= UNBEKANNT_PAUSE:
                self._gemeckert[art] = jetzt
                log.warning("Unbekannte Art %r von %s -- ignoriert. "
                            "Tippfehler im Namen?", art, o.name)

    # --- Aufbau ----------------------------------------------------------

    def anwendung(self, traeger: NetzTraeger) -> web.Application:
        self.traeger = traeger
        app = web.Application(client_max_size=NACHRICHT_MAX)
        app.router.add_get("/", self._seite)
        app.router.add_get("/leben", self._leben)
        app.router.add_post("/datei", self._datei)
        app.router.add_get("/dateien", self._dateien)
        app.router.add_get("/faeden", self._faeden)
        app.router.add_get("/verlauf", self._verlauf)
        app.router.add_get("/suche", self._suche)
        app.router.add_get("/ablage", self._ablage)
        app.router.add_post("/ablage/oeffnen", self._ablage_oeffnen)
        app.router.add_get("/push/schluessel", self._push_schluessel)
        app.router.add_post("/push/abo", self._push_abo)
        app.router.add_post("/push/abmelden", self._push_abmelden)
        app.router.add_post("/push/probe", self._push_probe)
        app.router.add_get("/waechter.js", self._waechter)
        app.router.add_post("/teilen", self._teilen)
        app.router.add_get("/draht", self._draht)
        if WEB.is_dir():
            app.router.add_static("/dabei/", WEB, name="dabei")
        # Die Spotify-Anmeldung. Zwei Wege ohne Geraeteschluessel --
        # Spotify hat keinen; was stattdessen schuetzt, steht in
        # netz/spotify.py.
        from . import spotify
        spotify.anmelden(app)
        # Die Blaetter -- Berichte, PDFs, Word-Dateien. Ebenfalls ohne
        # Geraeteschluessel, und ebenfalls mit Begruendung: Ein <iframe>
        # und ein Download-Knopf schicken keine eigenen Kopfzeilen.
        # Was stattdessen schuetzt, steht in netz/blaetter.py.
        blaetter.anmelden(app)
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
