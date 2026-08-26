"""Die Schleife: Taste halten, reden, loslassen, hoeren.

Stufe eins. Noch ohne Werkzeuge -- es geht erst einmal nur darum, ob sich
das Ganze wie ein Gespraech anfuehlt oder wie ein Formular.
"""
import asyncio
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime

# Windows-Konsole auf UTF-8, sonst zerfallen Umlaute in Claudes Antworten.
for strom in (sys.stdout, sys.stderr):
    try:
        strom.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

from pynput import keyboard  # noqa: E402

from . import config, rueckfrage  # noqa: E402
from .anzeige import DENKT, FRAGT, HOERT, RUHIG, SPRICHT, Anzeige  # noqa: E402
from .audio import Aufnehmer, Lautsprecher, gong  # noqa: E402
from .freigabe import Freigaben  # noqa: E402
from .hinweis import zeigen  # noqa: E402
from .hirn import Hirn  # noqa: E402
from .mund import Mund, Satzsammler, taste_aussprechen, tageszeit  # noqa: E402
from .ohren import Ohren  # noqa: E402
from .weckwort import Horcher  # noqa: E402
from .werkzeuge import google  # noqa: E402
from .werkzeuge import bauen, kurzer_name, zustand_zeile  # noqa: E402


def _taste_aufloesen(name: str):
    name = name.strip().lower()
    if hasattr(keyboard.Key, name):
        return getattr(keyboard.Key, name)
    if len(name) == 1:
        return keyboard.KeyCode.from_char(name)
    raise ValueError(f"Unbekannte Taste in config.TASTE: {name!r}")


def _anzeige_starten() -> subprocess.Popen | None:
    """Overlay als eigenen Prozess starten -- stirbt es, laeuft Sarvis weiter."""
    if not config.ANZEIGE:
        return None
    protokoll = config.WURZEL / "anzeige.log"
    try:
        vorgang = subprocess.Popen(
            [sys.executable, "-m", "sarvis.hud", "--eltern", str(os.getpid())],
            cwd=str(config.WURZEL),
            # Unsere Prozesskennung geht mit: die Anzeige beendet sich selbst,
            # sobald wir weg sind -- auch bei zugeklapptem Konsolenfenster.
            stdin=subprocess.DEVNULL,
            stdout=protokoll.open("w", encoding="utf-8"),
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as e:
        print(f"  (Anzeige liess sich nicht starten: {e})")
        return None

    # Kurz nachsehen, ob sie ueberhaupt stehen bleibt -- ein stiller Fehlstart
    # ist schlimmer als gar keine Anzeige, weil man ewig woanders sucht.
    time.sleep(1.2)
    if vorgang.poll() is not None:
        grund = ""
        try:
            grund = protokoll.read_text(encoding="utf-8").strip().splitlines()[-1]
        except (OSError, IndexError):
            pass
        print(f"  (Anzeige abgebrochen: {grund or 'siehe anzeige.log'})")
        return None
    return vorgang


class Sarvis:
    def __init__(self):
        self.taste = _taste_aufloesen(config.TASTE)
        self.anzeige = Anzeige(config.ANZEIGE)
        self.aufnehmer = Aufnehmer(melden=self.anzeige.pegel)
        self.lautsprecher = Lautsprecher(melden=self.anzeige.pegel)
        self.ohren = Ohren()
        self.mund = Mund()
        (self.werkzeugserver, self.werkzeugnamen, self.wecker,
         self.protokoll, self.werkstatt) = bauen(
            sagen=self.von_selbst_sagen,
            leuchten=self.anzeige.werkzeug,
            melden=zeigen,
        )
        # Freigaben auf Zeit. Bewusst hier und nicht im Hirn: Sie
        # gehoeren zum Gespraech, nicht zum Modell -- ein Neustart hebt
        # jede auf.
        self.freigaben = Freigaben()
        self.hirn = Hirn(self.werkzeugserver, self.werkzeugnamen,
                         leuchten=self.anzeige.werkzeug,
                         nachfragen=self.nachfragen,
                         protokoll=self.protokoll,
                         zustand_zeile=lambda: zustand_zeile(self.wecker),
                         freigaben=self.freigaben)
        self.schlange: asyncio.Queue[str] = asyncio.Queue()
        self.schleife: asyncio.AbstractEventLoop | None = None
        self.haelt = False           # Taste gerade gedrueckt?
        self.arbeitet = False        # Antwort laeuft gerade?
        self.aufgabe = None          # der laufende Durchgang, abbrechbar
        self.abgebrochen = False     # wurde reingeredet?
        self.verschiebt = False      # Anzeige gerade im Verschiebemodus?
        self.antwort = None          # offene Rueckfrage (Future)
        self.horcher = Horcher(self.ohren, self._geweckt,
                               anzeige=self.anzeige)
        # Was in DIESEM Zug schon abgelehnt wurde. Siehe nachfragen().
        self._abgelehnt: dict = {}
        self.gruesse = []            # vorbereitete Weckantworten
        self.gruss_laeuft = False

    # --- Tastatur (fremder Faden) -----------------------------------------

    def _runter(self, taste):
        # Offene Rueckfrage: Enter heisst ja, Escape heisst nein.
        if self.antwort is not None and not self.antwort.done():
            if taste == keyboard.Key.enter:
                self.schleife.call_soon_threadsafe(self._antwort_geben, "ja")
                return
            if taste == keyboard.Key.esc:
                self.schleife.call_soon_threadsafe(self._antwort_geben, "nein")
                return

        if taste != self.taste or self.haelt:
            return  # Tastenwiederholung ignorieren
        # Bewusst NICHT auf self.arbeitet pruefen: Reinreden muss erlaubt
        # sein. Wer einen Assistenten nicht unterbrechen kann, wartet
        # jedes Mal eine falsche Antwort zu Ende ab.
        self.haelt = True
        self.schleife.call_soon_threadsafe(self.schlange.put_nowait, "start")

    def _hoch(self, taste):
        if taste != self.taste or not self.haelt:
            return
        self.haelt = False
        self.schleife.call_soon_threadsafe(self.schlange.put_nowait, "stop")

    def _geweckt(self, zuruf: str) -> None:
        """Das Weckwort ist gefallen -- aus fremdem Faden gemeldet."""
        self.schleife.call_soon_threadsafe(
            self.schlange.put_nowait, ("weckwort", zuruf)
        )

    def _antwort_geben(self, text: str) -> None:
        if self.antwort is not None and not self.antwort.done():
            # Wer waehrend der Frage antwortet, will den Rest nicht mehr
            # hoeren. Ohne das redet Sarvis die Frage zu Ende, obwohl sie
            # laengst beantwortet ist -- und man sitzt daneben und wartet.
            self.lautsprecher.abbrechen()
            self.antwort.set_result(text)

    def _verschieben_umschalten(self):
        """Anzeige zum Verschieben freigeben und wieder festmachen."""
        self.verschiebt = not self.verschiebt
        self.anzeige.verschieben(self.verschiebt)
        print("  Anzeige: " + ("verschiebbar -- ziehen, dann Tastenkombination "
                               "erneut" if self.verschiebt else "festgemacht"))

    # --- Ablauf ------------------------------------------------------------

    async def von_selbst_sagen(self, text: str, mit_gong: bool = True) -> None:
        """Reden, ohne gefragt worden zu sein.

        Bis Stufe 1 konnte Sarvis nur antworten. Ein Timer, der ablaeuft,
        muss sich aber selbst melden -- und derselbe Weg traegt spaeter
        laengere Auftraege ("...und such mir waehrenddessen die Nachrichten").

        Wartet ab, wenn gerade gesprochen oder zugehoert wird: dazwischen-
        zureden ist schlimmer als ein paar Sekunden spaeter dran zu sein.
        """
        for _ in range(120):  # hoechstens zwei Minuten hoeflich warten
            if not self.arbeitet and not self.haelt:
                break
            await asyncio.sleep(1.0)

        print(f"\n  Sarvis : {text}   (von selbst)")
        # Mit Kopfhoerern bleibt das Ohr offen (config.REINREDEN), damit
        # man ihm ins Wort fallen kann; mit Boxen schaltet spricht() ab.
        self.horcher.spricht(text)
        self.anzeige.zustand(SPRICHT)
        self.anzeige.untertitel("sarvis", text)
        if mit_gong and config.GONG:
            # Erst der Ton, dann die Worte: Wer nicht direkt am Rechner
            # sitzt, verpasst sonst den Anfang des Satzes.
            self.lautsprecher.sagen(*gong())
        proben, rate = await asyncio.to_thread(self.mund.sprechen, text)
        if len(proben):
            self.lautsprecher.sagen(proben, rate)
            await asyncio.to_thread(self.lautsprecher.warten)
        self.anzeige.zustand(RUHIG)
        self.horcher.spricht(None)

    # --- Begruessung auf Vorrat --------------------------------------------

    async def _gruss_vorbereiten(self) -> None:
        """Alle Weckantworten einmal aussprechen und bereitlegen.

        Frueher wurde die Begruessung bei jedem Ruf von Claude erfunden --
        gemessen zwei bis drei Sekunden, bevor ueberhaupt ein Ton kam. Ein
        Assistent, der beim Wecken erst nachdenkt, wirkt traege. Jetzt
        stehen ein paar kurze Saetze fest und liegen fertig gesprochen da.
        """
        if self.gruesse or self.gruss_laeuft:
            return
        self.gruss_laeuft = True
        try:
            fertig = []
            for text in config.WECKANTWORTEN:
                proben, rate = await asyncio.to_thread(self.mund.sprechen, text)
                if len(proben):
                    fertig.append((text, proben, rate))
            self.gruesse = fertig
        except Exception as e:
            print(f"  (Weckantworten ließen sich nicht vorbereiten: {e})")
        finally:
            self.gruss_laeuft = False

    async def _gruessen(self) -> bool:
        """Weckantwort sofort sprechen. False = noch nichts vorbereitet."""
        if not self.gruesse:
            return False
        text, proben, rate = random.choice(self.gruesse)
        _reinreden = text          # gleich an spricht() weitergereicht
        print(f"\n  Sarvis : {text}")
        self.horcher.spricht(_reinreden)
        self.anzeige.zustand(SPRICHT)
        self.anzeige.untertitel("sarvis", text)
        self.lautsprecher.sagen(proben, rate)
        await asyncio.to_thread(self.lautsprecher.warten)
        self.anzeige.zustand(RUHIG)
        self.horcher.spricht(None)
        self.horcher.nachhoeren()
        self.anzeige.nachhoeren(config.NACHHOEREN_SEK)
        return True

    # --- Rueckfrage --------------------------------------------------------

    async def nachfragen(self, werkzeug: str, eingabe: dict):
        """Laut nachfragen. Gibt (Entscheidung, Wortlaut) zurueck.

        Entscheidung ist "ja", "nein" oder "anders" -- und der Wortlaut
        geht mit, weil er sonst verloren geht. Frueher kam hier nur ein
        bool heraus: Auf "ja, aber nur die erste" lief das Werkzeug mit
        den urspruenglichen Angaben los, und Sarvis erfuhr nie, dass
        ueberhaupt etwas eingeschraenkt worden war.

        Antwort per Stimme (Taste halten und "ja" sagen) oder per Taste
        (Enter = ja, Escape = nein). Beides, weil beides seine Situation
        hat: Wer die Haende frei hat, redet; wer im Buero sitzt, drueckt.

        Bei Zeitablauf wird abgelehnt. Ein Assistent, der im Zweifel
        handelt, ist schlimmer als einer, der im Zweifel fragt. Wurde
        dagegen etwas Ganzes gesagt, das nur keine Antwort auf die Frage
        war, geht es als Zuruf weiter statt verloren.
        """
        # Schon gefragt und schon beantwortet? Dann nicht noch einmal.
        #
        # Beobachtet: Auf "Soll ich finanzdashboard im Terminal oeffnen?"
        # kam "wir wollen daran weiterarbeiten" -- also etwas anderes.
        # Danach stand woertlich dieselbe Frage wieder da, und man musste
        # ein zweites Mal nein sagen. Im Systemprompt steht zwar, dass er
        # es nicht unveraendert wiederholen soll; darauf zu bauen reicht
        # offensichtlich nicht.
        #
        # Der Schluessel ist Werkzeug samt Eingabe: Eine wirklich andere
        # Anfrage fragt weiterhin. Und der Merker gilt nur fuer diesen
        # einen Zug -- ein spaeteres "mach das doch" darf nicht an einer
        # alten Ablehnung haengen bleiben.
        schluessel = None
        try:
            schluessel = (werkzeug,
                          json.dumps(eingabe or {}, sort_keys=True, default=str))
        except (TypeError, ValueError):
            pass
        if schluessel is not None and schluessel in self._abgelehnt:
            frueher, wortlaut = self._abgelehnt[schluessel]
            print(f"  ? schon beantwortet ({frueher}) -- nicht nochmal gefragt")
            return frueher, wortlaut

        frage = rueckfrage.formulieren(werkzeug, eingabe)
        print(f"\n  ? Sarvis fragt: {frage}")

        letztes = ""
        # Das Antwortfenster steht, BEVOR die Frage gesprochen wird.
        #
        # Vorher wurde es erst danach angelegt. Wer schnell antwortet --
        # und auf "soll ich das ausführen?" antwortet man schnell --,
        # traf in die Luecke dazwischen: Das "ja" gehoerte dann zu keiner
        # Frage, wurde als neuer Zuruf behandelt, und die Frage lief in
        # den Zeitablauf. Im Protokoll sah das so aus:
        #
        #   * Nachhoeren: 'Ja'
        #   Du     : Ja   (per Weckwort)
        #   ? keine Antwort -- abgelehnt
        #
        # Man musste also zweimal antworten. Seit man ihm ins Wort fallen
        # darf, ist die Luecke ausserdem so breit wie die Frage selbst.
        self.antwort = self.schleife.create_future()
        # Waehrend die Frage offen steht, braucht das "ja" kein Weckwort.
        # Ohne das muesste man "Hey Sarvis, ja" sagen -- auf eine Frage,
        # die er gerade selbst gestellt hat.
        self.horcher.nachhoeren(config.RUECKFRAGE_SEKUNDEN + 12)
        try:
            for versuch in range(2):
                # Der zweite Versuch wiederholt nicht, er erklaert: Wer
                # zurueckfragt, hat die Frage gehoert und WILL mehr wissen.
                text = frage if versuch == 0 else (
                    rueckfrage.genauer(werkzeug, eingabe)
                    or rueckfrage.NACHHAKEN
                )
                self.anzeige.zustand(FRAGT)
                self.anzeige.untertitel("sarvis", text)
                await asyncio.to_thread(self._sagen_und_warten, text)

                self.anzeige.zustand(FRAGT)
                self.horcher.nachhoeren(config.RUECKFRAGE_SEKUNDEN + 2)
                try:
                    async with asyncio.timeout(config.RUECKFRAGE_SEKUNDEN):
                        gehoert = await self.antwort
                except (TimeoutError, asyncio.TimeoutError):
                    print("  ? keine Antwort -- abgelehnt")
                    await self._sagen(rueckfrage.ABGELAUFEN)
                    return "nein", ""

                entschieden = rueckfrage.deuten(gehoert)
                letztes = (gehoert or "").strip()
                print(f"  ? Antwort: {gehoert!r} -> {entschieden}")

                if entschieden == "ja":
                    await self._freigabe_erteilen(werkzeug, eingabe, gehoert)
                    self.anzeige.zustand(RUHIG)
                    return "ja", gehoert

                if entschieden == "nein":
                    if schluessel is not None:
                        self._abgelehnt[schluessel] = ("nein", gehoert)
                    await self._sagen(rueckfrage.ABGELEHNT)
                    return "nein", gehoert

                if entschieden == "anders":
                    # Hier wird bewusst NICHT nachgehakt und nichts gesagt:
                    # Der Nutzer hat klar geredet, nur eben etwas anderes als
                    # gefragt. Sein Satz geht ans Hirn zurueck, und Sarvis
                    # antwortet gleich selbst darauf -- ein "Ich lasse es"
                    # dazwischen waere schlicht falsch.
                    if schluessel is not None:
                        self._abgelehnt[schluessel] = ("anders", gehoert)
                    self.anzeige.zustand(DENKT)
                    return "anders", gehoert

                # Vor dem Nachhaken ein frisches Fenster: Im alten liegt
                # die eben gehoerte Antwort schon drin, der zweite Versuch
                # waere sonst sofort mit demselben Satz zu Ende.
                self.antwort = self.schleife.create_future()
        finally:
            self.antwort = None

        # Zweimal kein Ja und kein Nein -- aber es wurde etwas gesagt.
        # Dann ist es eher ein neuer Auftrag als ein Missverstaendnis:
        # "ach, mach lieber erst die Mail von gestern auf". Frueher fiel
        # so ein Satz ersatzlos weg, und Sarvis wirkte, als hoerte er
        # nicht zu. Kurze Laute bleiben ein Missverstaendnis.
        if len(letztes.split()) >= 3:
            print("  ? nicht als Antwort verstanden -- geht als Zuruf weiter")
            self.anzeige.zustand(DENKT)
            return "anders", letztes

        await self._sagen(rueckfrage.ABGELAUFEN)
        return "nein", ""

    async def _freigabe_erteilen(self, werkzeug: str, eingabe: dict,
                                 gehoert: str) -> None:
        """Aus "ja, und frag nicht nochmal" eine Freigabe auf Zeit machen.

        Nur auf ausdruecklichen Wunsch. Ein blosses "ja" gilt weiter fuer
        genau diesen einen Aufruf -- Bequemlichkeit allein darf keine
        Dauererlaubnis erzeugen.
        """
        minuten = rueckfrage.freigabe_erkennen(gehoert)
        if minuten is None:
            return

        if not self.freigaben.erteilbar(werkzeug):
            # Was hinausgeht, wird jedes Mal gefragt. Das ist keine
            # Einstellung, die man vergessen hat -- das ist der Zweck.
            await self._sagen(
                "Das mache ich diesmal. Aber bei so etwas frage ich jedes "
                "Mal neu, das lässt sich nicht abstellen."
            )
            return

        was = self.freigaben.erteilen(werkzeug, eingabe, minuten)
        if not was:
            return
        print(f"  ~ Freigabe erteilt: {was}")
        self.anzeige.freigabe(self.freigaben.kurz(),
                              self.freigaben.rest_sekunden())
        await self._sagen(f"Gut. {was} frage ich nicht mehr nach.")

    async def _antwort_hoeren(self) -> None:
        """Aufnahme als Antwort auf eine offene Rueckfrage auswerten."""
        proben = self.aufnehmer.stop()
        dauer = len(proben) / config.ABTASTRATE
        if dauer < config.MIN_AUFNAHME_SEK:
            self.anzeige.zustand(FRAGT)
            return
        self.anzeige.zustand(DENKT)
        gehoert = await asyncio.to_thread(self.ohren.hoeren, proben)
        print(f"  Du     : {gehoert}   (Antwort auf die Rückfrage)")
        self.anzeige.untertitel("du", gehoert)
        self._antwort_geben(gehoert)

    def _sagen_und_warten(self, text: str) -> None:
        """Einen Satz sprechen und abwarten, bis er zu Ende ist."""
        self.horcher.spricht(text)
        try:
            proben, rate = self.mund.sprechen(text)
            if len(proben):
                self.lautsprecher.sagen(proben, rate)
                self.lautsprecher.warten()
        finally:
            self.horcher.spricht(None)

    async def _sagen(self, text: str) -> None:
        print(f"  Sarvis : {text}")
        self.anzeige.zustand(SPRICHT)
        self.anzeige.untertitel("sarvis", text)
        await asyncio.to_thread(self._sagen_und_warten, text)
        self.anzeige.zustand(RUHIG)

    async def _unterbrechen(self) -> None:
        """Reinreden: sofort still sein und alles Laufende fallen lassen.

        Die Reihenfolge ist wichtig. Erst die Flagge setzen, damit kein
        Faden mehr etwas nachschiebt; dann der Ton, weil der als Einziges
        hoerbar ist; dann Claude, damit die naechste Frage nicht die halbe
        alte Antwort hinterhergeschoben bekommt.
        """
        self.abgebrochen = True
        self.lautsprecher.abbrechen()
        if self.aufgabe is not None and not self.aufgabe.done():
            self.aufgabe.cancel()
            try:
                await self.aufgabe
            except (asyncio.CancelledError, Exception):
                pass
        self.aufgabe = None
        await self.hirn.unterbrechen()
        self.arbeitet = False
        print("  (unterbrochen)")

    async def _hintergrund_melden(self) -> None:
        """Laufende Arbeit an die Anzeige melden, einmal je Sekunde.

        Bewusst gepollt und nicht bei jeder Aenderung gemeldet: Die
        Quellen liegen in zwei verschiedenen Welten (Werkstatt und Hirn),
        und eine Anzeige, die einmal eine Meldung verpasst, behauptete
        sonst dauerhaft das Falsche. Einmal je Sekunde neu zu sagen, was
        Sache ist, kann nicht auseinanderlaufen.
        """
        letzte = None
        letzter_stand = None
        beginn = 0.0        # seit wann laeuft ueberhaupt etwas
        fertig_um = 0.0     # wann wurde das Letzte fertig
        while True:
            zeilen = []
            try:
                if self.werkstatt is not None:
                    zeilen += self.werkstatt.laufende_kurz()
                zeilen += self.hirn.subagenten_kurz()
            except Exception:
                zeilen = []

            jetzt = time.perf_counter()
            if zeilen and not letzte:
                beginn = jetzt          # aus dem Nichts wurde Arbeit
                fertig_um = 0.0
            elif not zeilen and letzte:
                fertig_um = jetzt       # das Letzte ist durch

            # "Fertig" bleibt kurz stehen: Verschwaende die Anzeige sofort,
            # verpasste man genau den Moment, auf den man gewartet hat.
            fertig = bool(fertig_um and
                          jetzt - fertig_um < config.ENTWICKLUNG_GRUEN_SEK)
            seit = (jetzt - beginn) if zeilen and beginn else 0.0
            stand = (zeilen, fertig, int(seit) // 10)
            if stand != letzter_stand:
                self.anzeige.hintergrund(zeilen, seit=seit, fertig=fertig)
                letzter_stand = stand
            letzte = zeilen
            await asyncio.sleep(1.0)

    async def _alles_stoppen(self) -> None:
        """Sofort still und alles Laufende anhalten.

        Bewusst NICHT _unterbrechen(): Das killt self.aufgabe -- und diese
        Methode laeuft selbst darin. Sie wuerde sich also selbst abraeumen,
        bevor sie die Auftraege erreicht.
        """
        self.lautsprecher.abbrechen()
        try:
            await self.hirn.unterbrechen()
        except Exception:
            pass
        wieviele = 0
        if self.werkstatt is not None:
            wieviele = self.werkstatt.alles_abbrechen()
        self.abgebrochen = False
        print(f"  (gestoppt -- {wieviele} laufende Auftraege abgebrochen)")
        # Ein Wort. Wer "hör auf" sagt, will keinen Bericht darueber, was
        # aufgehoert hat.
        await self._sagen("Gestoppt." if not wieviele else
                          f"Gestoppt, {wieviele} Auftrag abgebrochen."
                          if wieviele == 1 else
                          f"Gestoppt, {wieviele} Aufträge abgebrochen.")

    def _stopp_taste(self) -> None:
        """Die Stopp-Tastenkombination -- aus fremdem Faden gemeldet.

        Der Ton wird HIER abgebrochen, nicht erst in der Schleife. Ist die
        gerade beschaeftigt, laege die Meldung sonst in der Warteschlange,
        waehrend Sarvis weiterredet -- und genau in dem Moment drueckt man
        die Taste. Der Lautsprecher ist dafuer gebaut: eigener Faden,
        eigene Warteschlange, von aussen ansprechbar.
        """
        self.lautsprecher.abbrechen()
        print("\n  (Not-Aus gedrueckt)")
        if self.schleife is not None:
            self.schleife.call_soon_threadsafe(self.schlange.put_nowait, "stopp")

    def _begruessen(self) -> None:
        """Beim Start laut melden.

        Zwei Zwecke: man hoert sofort, ob Headset oder Boxen ueberhaupt an
        sind -- und der Weg Text -> Piper -> Lautsprecher ist damit einmal
        durchlaufen, bevor es ernst wird.
        """
        text = random.choice(config.BEGRUESSUNGEN).format(
            tageszeit=tageszeit(datetime.now().hour),
            taste=taste_aussprechen(config.TASTE),
        )
        self.anzeige.zustand(SPRICHT)
        self.anzeige.untertitel("sarvis", text)
        try:
            proben, rate = self.mund.sprechen(text)
            if len(proben):
                self.lautsprecher.sagen(proben, rate)
                self.lautsprecher.warten()
        except Exception as e:
            print(f"  (Begruessung fehlgeschlagen: {e})")
        self.anzeige.zustand(RUHIG)
        self.anzeige.untertitel("sarvis", text)

    async def _antworten(self, gesagt: str, t_los: float) -> None:
        # Die Freigabe-Anzeige bei jedem Zuruf nachziehen: Sie zaehlt
        # zwar von selbst herunter, aber die Minutenangabe stammt vom
        # Zeitpunkt der Erteilung und waere sonst bald falsch.
        self.anzeige.freigabe(self.freigaben.kurz(),
                              self.freigaben.rest_sekunden())
        # "Hör auf" ist ein Befehl, keine Gespraechseroeffnung. Ginge er
        # ans Hirn, kaeme ein Lagebericht zurueck statt eines Abbruchs --
        # woertlich passiert: "Das Angular-Frontend wird gerade gebaut,
        # der Auftrag laeuft noch."
        # Neuer Zuruf, neue Lage: Was vorhin abgelehnt wurde, darf jetzt
        # wieder gefragt werden.
        self._abgelehnt = {}

        if rueckfrage.ist_stopp(gesagt):
            await self._alles_stoppen()
            return

        sammler = Satzsammler()
        erster_ton: float | None = None
        erstes_wort: float | None = None
        ganze_antwort: list[str] = []
        gesprochen: list[str] = []

        def vorlesen(satz: str) -> None:
            nonlocal erster_ton
            if self.abgebrochen:
                return
            # Beim Reinreden bleibt das Ohr offen -- der Satz geht mit,
            # damit _eigen_echo seine eigene Stimme aussortieren kann.
            self.horcher.spricht(satz)
            proben, rate = self.mund.sprechen(satz)
            # Die Synthese laeuft in einem Faden und laesst sich nicht
            # abbrechen -- also danach nochmal nachsehen, sonst rutscht der
            # gerade fertige Satz nach dem Abbruch doch noch heraus.
            if len(proben) and not self.abgebrochen:
                if erster_ton is None:
                    erster_ton = time.perf_counter()
                    self.anzeige.zustand(SPRICHT)
                gesprochen.append(satz)
                self.anzeige.untertitel("sarvis", " ".join(gesprochen))
                self.lautsprecher.sagen(proben, rate)

        async for schnipsel in self.hirn.fragen(gesagt):
            if erstes_wort is None:
                erstes_wort = time.perf_counter()
            ganze_antwort.append(schnipsel)
            for satz in sammler.dazu(schnipsel):
                await asyncio.to_thread(vorlesen, satz)

        rest = sammler.rest()
        if rest:
            await asyncio.to_thread(vorlesen, rest)

        text = "".join(ganze_antwort).strip()
        print(f"  Sarvis : {text}")
        await asyncio.to_thread(self.lautsprecher.warten)
        self.anzeige.zustand(RUHIG)
        self.horcher.spricht(None)

        jetzt = time.perf_counter()
        print(
            "  ---- "
            f"erstes Wort {(erstes_wort or jetzt) - t_los:.2f}s | "
            f"erster Ton {(erster_ton or jetzt) - t_los:.2f}s | "
            f"fertig {jetzt - t_los:.2f}s"
        )

    async def _gruss_oder_neu(self) -> None:
        """Vorbereitete Begruessung, sonst eben doch frisch erfinden."""
        try:
            if not await self._gruessen():
                # Vorrat noch nicht fertig -- dann eben schlicht.
                await self._sagen(config.WECKANTWORTEN[0])
                self.horcher.nachhoeren()
                self.anzeige.nachhoeren(config.NACHHOEREN_SEK)
                asyncio.create_task(self._gruss_vorbereiten())
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"  Fehler: {type(e).__name__}: {e}")
            self.anzeige.zustand(RUHIG)
        finally:
            self.arbeitet = False
            self.aufgabe = None
            self.horcher.pause(False)

    async def _weckwort_durchgang(self, zuruf: str) -> None:
        """Wie _durchgang, aber der Text steht schon fest."""
        try:
            await self._antworten(zuruf, time.perf_counter())
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"  Fehler: {type(e).__name__}: {e}")
            self.anzeige.zustand(RUHIG)
        finally:
            self.arbeitet = False
            self.aufgabe = None
            self.horcher.pause(False)
            # Er hat gerade geredet -- der naechste Satz ist vermutlich
            # die Antwort darauf und braucht kein Weckwort.
            self.horcher.nachhoeren()
            self.anzeige.nachhoeren(config.NACHHOEREN_SEK)

    async def _durchgang_sicher(self) -> None:
        try:
            await self._durchgang()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"  Fehler: {type(e).__name__}: {e}")
            self.anzeige.zustand(RUHIG)
        finally:
            self.arbeitet = False
            self.aufgabe = None
            self.horcher.pause(False)
            self.horcher.nachhoeren()
            self.anzeige.nachhoeren(config.NACHHOEREN_SEK)

    async def _durchgang(self) -> None:
        proben = self.aufnehmer.stop()
        t_los = time.perf_counter()
        dauer = len(proben) / config.ABTASTRATE

        if dauer < config.MIN_AUFNAHME_SEK:
            print(f"  (nur {dauer:.2f}s -- verworfen)")
            self.anzeige.zustand(RUHIG)
            return

        self.anzeige.zustand(DENKT)
        gesagt = await asyncio.to_thread(self.ohren.hoeren, proben)
        t_stt = time.perf_counter()
        if not gesagt:
            print(f"  (nichts verstanden, {dauer:.1f}s Audio)")
            self.anzeige.zustand(RUHIG)
            return

        print(f"\n  Du     : {gesagt}")
        print(f"  ---- Aufnahme {dauer:.1f}s | Whisper {t_stt - t_los:.2f}s")
        self.anzeige.untertitel("du", gesagt)
        await self._antworten(gesagt, t_los)

    async def laufen(self) -> None:
        self.schleife = asyncio.get_running_loop()
        print("  Claude verbindet ...")
        t = time.perf_counter()
        await self.hirn.start()
        print(f"  Claude bereit nach {time.perf_counter() - t:.1f}s")
        for hinweis in self.hirn.hinweise:
            print(f"  Gedaechtnis: {hinweis}")
        # Abgelaufener Google-Zugang faellt sonst erst auf, wenn man ihn
        # braucht -- und dann steht man mitten im Satz.
        print(f"  Google     : {google.zustand()}")

        print("  Warmlaufen ...")
        await asyncio.to_thread(self.ohren.aufwaermen)
        await asyncio.to_thread(self.mund.aufwaermen)
        await asyncio.to_thread(self._begruessen)

        # Timer, die den letzten Lauf ueberlebt haben, wieder scharf machen.
        for meldung in await self.wecker.wiederherstellen():
            await self.von_selbst_sagen(meldung)

        lauscher = keyboard.Listener(on_press=self._runter, on_release=self._hoch)
        lauscher.start()

        # Erste Begruessung im Voraus erzeugen, solange noch nichts los ist.
        asyncio.create_task(self._gruss_vorbereiten())

        if self.horcher.start():
            print(f"  Weckwort aktiv: \"Hey {config.NAME.capitalize()}\"")

        # Eigener Lauscher fuer die Tastenkombination -- der Push-to-talk-
        # Lauscher sieht nur einzelne Tasten, keine Kombinationen.
        # Der Not-Aus haengt ausdruecklich NICHT an config.ANZEIGE. Wer die
        # Anzeige abschaltet, verliert sonst die einzige Moeglichkeit, Sarvis
        # mitten im Satz zu stoppen -- und merkt es erst, wenn er sie braucht.
        schalter = None
        tasten = {config.TASTE_STOPP: self._stopp_taste}
        if config.ANZEIGE:
            tasten[config.TASTE_VERSCHIEBEN] = self._verschieben_umschalten
        try:
            schalter = keyboard.GlobalHotKeys(tasten)
            schalter.start()
        except Exception as e:
            print(f"  (Tastenkombinationen gingen nicht: {e})")

        print("\n" + "=" * 62)
        print(f"  Sarvis laeuft.  [{config.TASTE.upper()}] halten, reden, loslassen.")
        if config.ANZEIGE:
            print(f"  Anzeige verschieben: {config.TASTE_VERSCHIEBEN}")
        print(f"  Sofort still: {config.TASTE_STOPP}")
        print("  Strg+C zum Beenden.")
        print("=" * 62)

        melder = asyncio.create_task(self._hintergrund_melden())
        try:
            while True:
                befehl = await self.schlange.get()
                antwortet = self.antwort is not None and not self.antwort.done()

                # Weckwort: der Zuruf steckt schon im selben Satz, es muss
                # also nichts mehr aufgenommen werden.
                if isinstance(befehl, tuple) and befehl[0] == "weckwort":
                    zuruf = befehl[1]
                    if antwortet:
                        self._antwort_geben(zuruf)
                        continue
                    if self.arbeitet or self.aufgabe is not None:
                        await self._unterbrechen()
                    self.abgebrochen = False
                    if not zuruf:
                        # Nur der Name gerufen: erst den Vorrat probieren,
                        # das spart die Runde zu Claude und die Synthese.
                        self.arbeitet = True
                        self.aufgabe = asyncio.create_task(
                            self._gruss_oder_neu()
                        )
                        continue
                    print(f"\n  Du     : {zuruf}   (per Weckwort)")
                    self.anzeige.untertitel("du", zuruf)
                    self.arbeitet = True
                    self.aufgabe = asyncio.create_task(
                        self._weckwort_durchgang(zuruf)
                    )
                    continue

                if befehl == "stopp":
                    # Geht vor allem anderen, auch vor einer offenen
                    # Rueckfrage: Stopp heisst Stopp.
                    if self.arbeitet or self.aufgabe is not None:
                        await self._unterbrechen()
                    await self._alles_stoppen()
                    continue

                if befehl == "start":
                    # Steht eine Rueckfrage offen, ist die Taste die Antwort
                    # darauf -- nicht der Beginn eines neuen Zurufs. Wuerde
                    # hier unterbrochen, killte die Taste genau die Frage,
                    # die sie beantworten soll.
                    if not antwortet:
                        if self.arbeitet or self.aufgabe is not None:
                            await self._unterbrechen()
                        self.abgebrochen = False
                    # Waehrend der Tastenaufnahme muss der Horcher nicht
                    # mitrechnen -- und soll nicht zweimal dasselbe hoeren.
                    self.horcher.pause(True)
                    self.aufnehmer.start()
                    self.anzeige.zustand(HOERT)
                    print("\n  * hoert zu ...")

                elif befehl == "stop":
                    if antwortet:
                        await self._antwort_hoeren()
                        self.horcher.pause(False)
                    else:
                        # Als Aufgabe, damit sie abbrechbar bleibt -- ohne
                        # das laesst sich nicht reinreden.
                        self.arbeitet = True
                        self.aufgabe = asyncio.create_task(
                            self._durchgang_sicher()
                        )
        finally:
            melder.cancel()
            lauscher.stop()
            self.horcher.stopp()
            if schalter is not None:
                schalter.stop()
            await self.hirn.stopp()


def main() -> int:
    hud = _anzeige_starten()
    sarvis = Sarvis()
    try:
        asyncio.run(sarvis.laufen())
    except KeyboardInterrupt:
        print("\n  Tschuess.")
    finally:
        if hud is not None:
            hud.terminate()
    return 0


if __name__ == "__main__":
    sys.exit(main())
