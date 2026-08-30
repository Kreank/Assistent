"""Zusehen und eingreifen -- Sarvis' Browser auf dem Bildschirm des Nutzers.

Auf dem Dev-PC gab es EINEN Browser. Sarvis machte ihn auf, Sascha sah
hinein und klickte selbst weiter, wenn Sarvis nicht weiterkam. Auf dem
Server sind es zwei geworden: einer hier, ohne Bildschirm, und einer
dort, ohne Zugriff. Das hier naeht sie wieder zusammen.

    Bilder hinaus   Page.startScreencast -> "schirm"
    Klicks herein   "klick"/"taste"/"rollen" -> Input.dispatch*

WAS DIESES MODUL IST UND WAS NICHT

Es ist die BUCHHALTUNG, nicht die Technik. Wer gerade zusieht, wer
aufhoert, wann der Strom anfaengt und wann er von selbst aufhoert --
das steht hier. Was ein Klick in CDP heisst, steht in browser_kopf.py.

Die Trennung hat einen Grund: browser_kopf kennt keine Oberflaechen und
soll auch keine kennen (er wird von den Werkzeugen benutzt, die nichts
vom Draht wissen), und der Endpunkt kennt kein CDP.

DREI GRUENDE, WARUM DER STROM AUFHOERT

  1. Der Zuschauer sagt es ("schirm_an": false).
  2. Der Zuschauer geht (Verbindung weg -- weg()).
  3. Der Browser geht (Ruhe-Waechter nach zehn Minuten, Absturz,
     web_schliessen). Dann kommt der Rueckruf aus browser_kopf, und
     jeder Zuschauer bekommt "schirm_aus".

Der dritte ist der, den man vergisst. Ohne ihn bliebe das letzte Bild
stehen und behauptete eine Seite, die es nicht mehr gibt -- und der
Nutzer klickte darauf, ins Leere.

NUR AN DIE, DIE ZUSEHEN WOLLEN

traeger.senden() geht an ALLE Oberflaechen. Fuer einen Zustand ist das
richtig; fuer einen Bildstrom waere es Verschwendung: acht Bilder je
Sekunde an ein Handy, das sie nicht angefordert hat und auf dem ein
1280er Fenster ohnehin Lupenarbeit waere.

Also wird eingelegt statt gesendet -- genau wie traeger.fragen() eine
EINZELNE Oberflaeche adressiert. Der Rueckstandsdeckel gilt trotzdem:
Bleibt ein Zuschauer haengen, wirft Oberflaeche._aufraeumen() seine
alten Bilder weg und behaelt das neueste. Genau richtig, denn ein Bild
von vor zwei Sekunden ist wertlos. Dafuer darf "schirm" nicht in
traeger.WICHTIG stehen -- steht es auch nicht, mit Vermerk dort.
"""
import asyncio
import logging

from . import browser_kopf

log = logging.getLogger("sarvis.netz")

# Wie oft der Browser waehrend des Zusehens angefasst wird, damit sein
# Ruhe-Waechter ihn nicht unter dem Zuschauer wegraeumt. Eine stehende
# Seite erzeugt keine Bilder (Chrome schickt nur bei Veraenderung), und
# ohne diesen Puls waere sie nach zehn Minuten Betrachtung weg.
PULS = 60.0

# Ab wie vielen wartenden Meldungen fuer eine Oberflaeche ihr KEIN Bild
# mehr eingelegt wird.
#
# Der Rueckstandsdeckel des Traegers steht bei 200 Meldungen und wirft
# dann Altes weg. Fuer Pegel und Zustaende ist das richtig; fuer einen
# Bildstrom kaeme er viel zu spaet: 200 Meldungen sind bei acht Bildern
# je Sekunde 25 Sekunden Rueckstand, und 25 Sekunden lang saehe der
# Nutzer eine Seite, die es laengst nicht mehr gibt -- und klickte
# hinein. Ein Klick auf ein 25 Sekunden altes Bild ist schlimmer als
# gar kein Bild.
#
# Sechs wartende Meldungen sind knapp eine Sekunde. Wer mehr im
# Rueckstand hat, bekommt einfach das naechste Bild nicht, und der
# Strom passt sich damit von selbst an die Leitung an. Das ist genau
# der richtige Regler: Es sinkt die Bildrate, nicht die Schaerfe.
STAU = 6


class Fernsicht:
    """Wer sieht gerade zu -- und was darf er."""

    def __init__(self, browser_holen=None):
        # Einspritzbar, damit ein Test einen eigenen Browser unterschieben
        # kann, ohne den Prozess-weiten anzufassen.
        self._holen = browser_holen or browser_kopf.hol
        self._zusehende: set = set()
        self._puls = None

    def sieht_zu(self, o) -> bool:
        return o in self._zusehende

    # --- An und aus -------------------------------------------------------

    async def schalten(self, o, an: bool) -> None:
        """"schirm_an" von einer Oberflaeche."""
        if an:
            await self._dazu(o)
        else:
            await self._weniger(o, sagen=True)

    async def _dazu(self, o) -> None:
        if o in self._zusehende:
            return
        browser = self._holen()
        neu = not self._zusehende
        self._zusehende.add(o)
        if not neu:
            return          # Der Strom laeuft schon, er bekommt ihn mit.
        antwort = await browser.schirm_starten(self._bild, self._browser_zu)
        if not antwort.get("ok"):
            self._zusehende.discard(o)
            log.info("Fernsicht ging nicht an: %s", antwort.get("grund"))
            # Ehrlich sein statt schweigen: Die Oberflaeche hat einen
            # Schalter umgelegt und muss ihn zuruecklegen koennen.
            o.einlegen({"art": "schirm_aus"})
            return
        log.info("Fernsicht an für %s", getattr(o, "name", "?"))
        if self._puls is None or self._puls.done():
            self._puls = asyncio.ensure_future(self._puls_lauf())

    async def _weniger(self, o, sagen: bool = False) -> None:
        if o not in self._zusehende:
            return
        self._zusehende.discard(o)
        if sagen:
            o.einlegen({"art": "schirm_aus"})
        if self._zusehende:
            return
        # Der letzte ist gegangen. Weiterzusenden hiesse, Bilder fuer
        # niemanden zu kodieren.
        try:
            bilanz = await self._holen().schirm_stoppen()
        except Exception:
            bilanz = {}
        if self._puls is not None:
            self._puls.cancel()
            self._puls = None
        log.info("Fernsicht aus: %s Bilder, %s B/s",
                 bilanz.get("bilder"), bilanz.get("bytes_je_sekunde"))

    async def weg(self, o) -> None:
        """Eine Oberflaeche hat die Verbindung verloren."""
        await self._weniger(o, sagen=False)

    def _browser_zu(self) -> None:
        """Der Browser ist von sich aus gegangen. Aus browser_kopf."""
        for o in list(self._zusehende):
            o.einlegen({"art": "schirm_aus"})
        self._zusehende.clear()
        if self._puls is not None:
            self._puls.cancel()
            self._puls = None

    def _bild(self, daten: str, breite: int, hoehe: int) -> None:
        """Ein Bild an jeden, der zusieht. Aus dem Ereignisstrom von CDP."""
        for o in list(self._zusehende):
            if o.schlange.qsize() > STAU:
                continue        # Diese Leitung kommt nicht nach. Siehe STAU.
            o.einlegen({"art": "schirm", "daten": daten,
                        "breite": breite, "hoehe": hoehe})

    async def _puls_lauf(self) -> None:
        try:
            while self._zusehende:
                await asyncio.sleep(PULS)
                if self._zusehende:
                    self._holen().wach_halten()
        except asyncio.CancelledError:
            pass

    # --- Was der MENSCH tut ----------------------------------------------
    #
    # ===================================================================
    # HIER KOMMEN DIE KLICKS HEREIN, UND HIER WIRD NICHT NACHGEFRAGT.
    #
    # Vor jedem Klick, den SARVIS macht, holt hirn._browserstufe das
    # Element frisch aus dem DOM und loest eine gesprochene Rueckfrage
    # aus, wenn es ein Formular abschickt -- auch wenn "Abbrechen"
    # darauf steht, denn das entscheidet el.form und nicht die
    # Beschriftung.
    #
    # FUER DIE DREI METHODEN HIER GILT DAS NICHT, UND DAS IST RICHTIG SO.
    #
    # Die Rueckfrage schuetzt davor, dass SARVIS unbeabsichtigt etwas
    # ausloest: Das Modell hat die Elementliste von einer fremden Seite,
    # und eine Seite, die ihm einredet, ihr Bestell-Knopf sei ein
    # harmloser Link, haette die Pruefung damit ausgehebelt. Hier klickt
    # kein Modell, sondern ein Mensch auf einen Punkt in einem Bild, das
    # er ansieht. Es gibt nichts zu schuetzen. Eine Rueckfrage hiesse
    # "willst du wirklich klicken, worauf du gerade geklickt hast" -- sie
    # waere nicht vorsichtig, sondern laecherlich, und nach dem dritten
    # Mal legt niemand mehr die Hand auf die Maus.
    #
    # WER DAS SPAETER "ZUR SICHERHEIT" NACHRUESTET, macht die
    # Fernsteuerung unbenutzbar und gewinnt nichts. Das FEHLEN der
    # Pruefung ist die Funktion, nicht eine vergessene Zeile.
    #
    # Was sehr wohl gilt und was diese Freiheit traegt:
    #
    #   ANGEMELDET. netz/server.py nimmt gar nichts entgegen, bevor die
    #   erste Nachricht ein gueltiger Geraeteschluessel war (_anmelden
    #   laeuft VOR _empfangen, und bei Fehlschlag wird geschlossen).
    #   Eine nicht angemeldete Verbindung kann diese Methoden nicht
    #   erreichen -- nicht "sollte nicht", sondern kann nicht.
    #
    #   SEHEND. Wer nicht in _zusehende steht, klickt nicht. Blind auf
    #   eine Seite zu klicken, die man nicht sieht, ist genau der
    #   Unfall, gegen den die Rueckfrage bei Sarvis gebaut ist -- und
    #   der einzige Fall, in dem ein Menschenklick ihm gleicht.
    # ===================================================================

    async def klick(self, o, m: dict) -> None:
        if o not in self._zusehende:
            return
        await self._holen().zeiger_klick(
            m.get("x"), m.get("y"), str(m.get("knopf") or "links"))

    async def taste(self, o, m: dict) -> None:
        if o not in self._zusehende:
            return
        await self._holen().taste(text=str(m.get("text") or ""),
                                  sonder=str(m.get("sonder") or ""))

    async def rollen(self, o, m: dict) -> None:
        if o not in self._zusehende:
            return
        await self._holen().zeiger_rollen(
            m.get("x"), m.get("y"), m.get("hoch"))
