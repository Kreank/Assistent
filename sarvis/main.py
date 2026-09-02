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

from . import anmeldung, config, klang, rueckfrage, schutz  # noqa: E402
from . import anzeige as anzeige_modul  # noqa: E402
from .anzeige import DENKT, FRAGT, HOERT, RUHIG, SPRICHT, Anzeige  # noqa: E402
from .klang import gong  # noqa: E402

# pynput haengt einen systemweiten Tastaturhaken ein und braucht dafuer
# X11 oder uinput. Auf einem Server ohne Bildschirm gibt es beides
# nicht, und der IMPORT allein scheitert schon -- Sarvis kaeme dort gar
# nicht bis zur ersten Zeile.
#
# Im Netzbetrieb wird die Taste auch nicht gebraucht: Der Ausloeser
# liegt auf dem Geraet, an dem jemand sitzt, nicht auf dem Server.
# Dasselbe gilt fuer den Weckwort-Horcher, der an einem Mikrofon haengt.
keyboard = None
if config.KLANG_QUELLE == "lokal":
    from pynput import keyboard  # noqa: E402,F811
from .freigabe import Freigaben, ort as freigabe_ort  # noqa: E402
from .hinweis import zeigen  # noqa: E402
from .hirn import Hirn  # noqa: E402
from .mund import Mund, Satzsammler, taste_aussprechen, tageszeit  # noqa: E402
from .ohren import Ohren  # noqa: E402
# Seit die Horch-Schleife ihre Bloecke aus einer Quelle bezieht statt
# direkt von PortAudio, braucht dieses Modul kein Audiogeraet mehr --
# es laesst sich auch headless importieren. weckwort_leer.py ist damit
# ueberfluessig geworden; im Netzbetrieb liefert klang.dauerhorch()
# einen Horch, der auf den Strom einer Oberflaeche wartet.
from .weckwort import Horcher  # noqa: E402
from .werkzeuge import google  # noqa: E402
from .werkzeuge import erinnern  # noqa: E402
from .gedaechtnis import (entscheidung_verpasst,  # noqa: E402
                          entscheidungen_nachtrag,
                          klingt_nach_entscheidung)
from .werkzeuge import (bauen, kurzer_name, unterbrochen_zeile,  # noqa: E402
                        zustand_zeile)


# Wie lange eine Meldung auf Ruhe wartet, bevor sie trotzdem gesagt
# wird. Vorher standen hier 120 Durchlaeufe zu einer Sekunde, mitten im
# Code. Ein Timer, der nie klingelt, weil das Gespraech nicht aufhoert,
# waere schlimmer als einer, der dazwischenredet.
MELDUNG_GEDULD_SEK = 120.0


class _Nichts:
    """Steht da, wo im Netzbetrieb ein Tastenlauscher stuende.

    Billiger als ein "if" an jeder der vier Stellen, an denen die
    Schleife ihn startet und stoppt -- und vor allem sieht die Schleife
    dann in beiden Betriebsarten gleich aus.
    """

    def start(self): pass
    def stop(self): pass


def _fehlt(pfad, rat: str) -> str:
    """Warum eine Werkzeuggruppe nicht gebaut wurde, in einem Satz."""
    return f"nicht angemeldet ({pfad.name} fehlt) -- {rat}"


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
    if config.KLANG_QUELLE == "netz":
        # Das Overlay ist ein Qt-Fenster. Auf einem Server gibt es keinen
        # Bildschirm, auf den es gehoerte, und PySide6 ist dort gar nicht
        # installiert -- der Unterprozess wuerde beim Import sterben und
        # eine Fehlerzeile hinterlassen, die nichts bedeutet.
        # Die Anzeige laeuft im Netzbetrieb im Browser.
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
        # Ohne Tastaturhaken gibt es auch keine Taste aufzuloesen.
        self.taste = (_taste_aufloesen(config.TASTE)
                      if config.KLANG_QUELLE == "lokal" else None)
        self.im_netz = config.KLANG_QUELLE == "netz"

        # Im Netzbetrieb wird der Anzeige-Traeger erst in laufen()
        # gesetzt: Er braucht die Ereignisschleife, und die laeuft hier
        # noch nicht.
        self.anzeige = Anzeige(config.ANZEIGE and not self.im_netz)
        # Hinterlegen, damit die Werkzeuge dieselbe benutzen statt sich
        # je eine eigene zu bauen -- siehe anzeige.aktuelle().
        anzeige_modul.setzen(self.anzeige)
        self.endpunkt = None
        self.traeger = None

        # Ueber klang.py statt direkt aus audio.py: Dort steht der
        # Vertrag, und dort tritt die Netzfassung daneben, ohne dass
        # diese Schleife noch einmal angefasst werden muss.
        #
        # Aufnehmer gibt es im Netzbetrieb keinen -- Push-to-talk ist
        # dort umgedreht: Das GERAET entscheidet, wann es aufnimmt, und
        # schickt eine fertige Aufnahme. Das spart die Rundreise vor dem
        # ersten Wort, in der sonst der Anfang verlorenginge.
        self.aufnehmer = (None if self.im_netz
                          else klang.aufnehmer(melden=self._pegel))
        self.lautsprecher = (None if self.im_netz
                             else klang.lautsprecher(melden=self._pegel))
        self.ohren = Ohren()
        self.mund = Mund()
        (self.werkzeugserver, self.werkzeugnamen, self.wecker,
         self.protokoll, self.werkstatt) = bauen(
            sagen=self.von_selbst_sagen,
            # Ueber self, nicht self.anzeige.werkzeug: Die Werkzeuge
            # werden EINMAL gebaut, hier im Konstruktor. Eine gebundene
            # Methode haelt die Anzeige fest, die gerade gilt -- und im
            # Netzbetrieb wird sie danach ausgetauscht. Genau deshalb
            # leuchtete auf dem Server kein einziges Werkzeug: Die
            # Meldungen gingen weiter per UDP an ein Fenster, das es
            # nicht gibt, und niemand merkte es.
            leuchten=self._leuchten,
            melden=zeigen,
        )
        # Freigaben auf Zeit. Bewusst hier und nicht im Hirn: Sie
        # gehoeren zum Gespraech, nicht zum Modell -- ein Neustart hebt
        # jede auf.
        self.freigaben = Freigaben()
        self.hirn = Hirn(self.werkzeugserver, self.werkzeugnamen,
                         leuchten=self._leuchten,
                         nachfragen=self.nachfragen,
                         protokoll=self.protokoll,
                         zustand_zeile=lambda: " ".join(
                             z for z in (zustand_zeile(self.wecker),
                                         unterbrochen_zeile(self.werkstatt),
                                         # NACH der Auftragszeile, nicht
                                         # davor: Was Sascha entschieden
                                         # hat, soll das letzte Wort haben
                                         # gegenüber einer Zeile, die
                                         # dieselbe Sache erneut anbietet.
                                         entscheidungen_nachtrag(),
                                         self._anstupser,
                                         schutz.arbeitsordner_zeile())
                             if z),
                         freigaben=self.freigaben)
        # Ein Hinweis fuer GENAU den naechsten Zuruf: Da fiel eine
        # Entscheidung und nichts wurde festgehalten. Siehe
        # gedaechtnis.entscheidung_verpasst.
        self._anstupser = ""
        self.schlange: asyncio.Queue[str] = asyncio.Queue()
        # Was Sarvis von sich aus sagen will: Timer, fertige Auftraege.
        # Eine Schlange und EIN Sprecher -- siehe von_selbst_sagen().
        self.meldungen: asyncio.Queue[tuple[str, bool]] = asyncio.Queue()
        self.schleife: asyncio.AbstractEventLoop | None = None
        # Bis wann die Kontextwache stillhaelt (time.monotonic).
        self._verdichtet_bis = 0.0
        self.haelt = False           # Taste gerade gedrueckt?
        self.arbeitet = False        # Antwort laeuft gerade?
        self.aufgabe = None          # der laufende Durchgang, abbrechbar
        self.abgebrochen = False     # wurde reingeredet?
        # Zaehler statt Flagge: Welcher Durchgang laeuft gerade?
        #
        # self.abgebrochen allein reicht nicht. Der Vorlesefaden laeuft in
        # einem to_thread und laesst sich nicht abbrechen -- er kehrt aus
        # der Synthese zurueck, wenn _alles_stoppen die Flagge schon
        # wieder auf False gesetzt hat, und schiebt seinen Satz dann NACH
        # dem "Gestoppt." heraus. Eine Zahl, die bei jedem Abbruch
        # hochzaehlt, kann nicht so zurueckfallen.
        self.durchgang = 0
        self.verschiebt = False      # Anzeige gerade im Verschiebemodus?
        self.antwort = None          # offene Rueckfrage (Future)
        # Woher die Weckwort-Bloecke kommen. Lokal das Mikrofon, im
        # Netzbetrieb eine Oberflaeche, die ihres offenhaelt -- meldet
        # sich keine, wartet er still. Der Traeger wird nachgereicht,
        # sobald die Ereignisschleife laeuft (siehe _netz_aufbauen).
        self.horch = klang.dauerhorch()
        self.horcher = Horcher(self.ohren, self._geweckt,
                               anzeige=self.anzeige, horch=self.horch)
        # Was in DIESEM Zug schon abgelehnt wurde. Siehe nachfragen().
        self._abgelehnt: dict = {}
        # Wie oft am selben Ort hintereinander ja gesagt wurde.
        self._ja_folge: dict = {}
        self.gruesse = []            # vorbereitete Weckantworten
        self.gruss_laeuft = False

    # --- Tastatur (fremder Faden) -----------------------------------------

    def _leuchten(self, name: str, aktiv: bool = True, strom: str = "") -> None:
        """Ein Werkzeug aufleuchten lassen -- ueber die JEWEILS geltende
        Anzeige.

        Nicht self.anzeige.werkzeug direkt weitergeben: Das bindet die
        Anzeige von jetzt an ein Objekt, das den ganzen Lauf ueberdauert.
        """
        self.anzeige.werkzeug(name, aktiv, strom)

    def _pegel(self, wert: float) -> None:
        """Dasselbe fuer den Ausschlag."""
        self.anzeige.pegel(wert)

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
        """Reden, ohne gefragt worden zu sein -- EINREIHEN, nicht sprechen.

        Bis Stufe 1 konnte Sarvis nur antworten. Ein Timer, der ablaeuft,
        muss sich aber selbst melden -- und derselbe Weg traegt laengere
        Auftraege ("...und such mir waehrenddessen die Nachrichten").

        Frueher stand hier die Hoeflichkeitsschleife selbst: bis zu 120
        Sekunden warten, ob gerade geredet wird. Das hatte zwei Fehler,
        und beide fallen im Serverbetrieb staerker ins Gewicht.

        ERSTENS blockierte es den Aufrufer. auftrag._melden() steht in
        genau diesem await, waehrend sein Auftragsfaden nicht aufraeumt.
        Ein Auftrag, der fertig wird, waehrend Sarvis eine lange Runde
        faehrt, haengt bis zu zwei Minuten -- und genau das soll Weg A
        abstellen: Arbeit soll das Gespraech nicht anhalten und das
        Gespraech nicht die Arbeit.

        ZWEITENS gab es keine Reihenfolge. Zwei Timer, die zusammen
        ablaufen, warteten unabhaengig voneinander dieselben Sekunden ab
        und redeten dann gleichzeitig los -- in einen Lautsprecher.

        Jetzt reiht das hier nur ein und kehrt sofort zurueck. Gesprochen
        wird in _melder(), einem einzigen Faden, der wartet, bis wirklich
        Ruhe ist, und die Meldungen der Reihe nach abarbeitet.
        """
        await self.meldungen.put((text, mit_gong))

    async def _melder(self) -> None:
        """Der eine Faden, der von sich aus spricht.

        Wartet auf Ruhe, aber nicht ewig: Ein Timer, der nie klingelt,
        weil das Gespraech nicht aufhoert, waere schlimmer als einer, der
        dazwischenredet. Nach MELDUNG_GEDULD_SEK wird gesprochen -- so
        stand es auch vorher schon, nur eben pro Meldung statt einmal
        fuer alle.
        """
        while True:
            text, mit_gong = await self.meldungen.get()
            wartet = 0.0
            while (self.arbeitet or self.haelt) and wartet < MELDUNG_GEDULD_SEK:
                await asyncio.sleep(0.2)
                wartet += 0.2
            try:
                await self._melden_sprechen(text, mit_gong)
            except Exception as e:
                # Eine misslungene Meldung darf den Melder nicht beenden,
                # sonst schweigt Sarvis ab da fuer alle weiteren.
                print(f"  (Meldung ging nicht raus: {e})")
            finally:
                self.meldungen.task_done()

    async def _melden_sprechen(self, text: str, mit_gong: bool = True) -> None:
        """Eine eingereihte Meldung wirklich sagen.

        An ALLE: Ein Timer, der ablaeuft, meint niemanden bestimmten. Wer
        ihn gestellt hat, sitzt vielleicht laengst woanders -- und eine
        Erinnerung, die im Kopfhoerer am leeren Schreibtisch klingelt,
        waere genau die falsche.
        """
        if hasattr(self.lautsprecher, "ziel"):
            self.lautsprecher.ziel = None
        anzeige_modul.zielen(None)
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
        # Wer von sich aus etwas meldet, stellt oft eine Frage dazu ("ist
        # fertig -- soll ich es dir zeigen?"). Ohne offenes Fenster muesste
        # man darauf mit "Hey Sarvis, ja" antworten, und das sagt niemand.
        self.horcher.nachhoeren()
        self.anzeige.nachhoeren(config.NACHHOEREN_SEK)

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

        # Zehnmal dasselbe fragen ist keine Sorgfalt mehr, sondern
        # Zermuerbung -- wer zum zehnten Mal ja sagt, hoert nicht mehr hin,
        # was er da bestaetigt. Nach dem dritten Ja am selben Ort bietet
        # die Frage deshalb die Freigabe auf Zeit gleich mit an. Ein Ja
        # gilt dann fuer beides, und der Nutzer hoert genau, wofuer.
        #
        # Nur MIT Ort: Ohne Ort waere die Freigabe ortlos, und ortlos
        # heisst ueberall (freigabe._unter). Das waere das Gegenteil von
        # dem, was hier gemeint ist.
        wo = freigabe_ort(werkzeug, eingabe)
        folge = f"{werkzeug}|{wo}"
        anbieten = bool(
            wo
            and self._ja_folge.get(folge, 0) >= 2
            and self.freigaben.erteilbar(werkzeug)
            and not self.freigaben.erlaubt(werkzeug, eingabe)
        )

        frage = rueckfrage.formulieren(werkzeug, eingabe)
        if anbieten:
            frage += (" Sag ja, dann frage ich dafür "
                      f"{Freigaben.wo_lang(wo)} die nächsten "
                      f"{Freigaben.dauer_lang(config.FREIGABE_MINUTEN)} "
                      "nicht mehr.")
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
        # Solange die Frage offen steht, genuegt ein einzelnes Wort als
        # Antwort -- der Horcher wirft sonst alles weg, was kuerzer als
        # zwei Woerter ist und nicht "ja" oder "nein" heisst.
        self.horcher.frage_offen(True)
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
                    self._ja_folge[folge] = self._ja_folge.get(folge, 0) + 1
                    if anbieten:
                        self._ja_folge[folge] = 0
                    await self._freigabe_erteilen(
                        werkzeug, eingabe, gehoert,
                        minuten=config.FREIGABE_MINUTEN if anbieten else None)
                    self.anzeige.zustand(RUHIG)
                    return "ja", gehoert

                if entschieden == "nein":
                    # Ein Nein setzt die Kette zurueck: Was gerade abgelehnt
                    # wurde, ist kein Fall fuer eine Pauschalfreigabe.
                    self._ja_folge[folge] = 0
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
            self.horcher.frage_offen(False)

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
                                 gehoert: str, minuten: float = None) -> None:
        """Aus "ja, und frag nicht nochmal" eine Freigabe auf Zeit machen.

        Auf ausdruecklichen Wunsch -- oder wenn die Frage die Freigabe
        selbst angeboten hat (minuten gesetzt). Ein blosses "ja" auf eine
        gewoehnliche Frage erzeugt weiterhin keine Dauererlaubnis.
        """
        if minuten is None:
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
            # Kein Ort erkennbar, also keine Freigabe. Das muss gesagt
            # werden: Wer "und frag nicht mehr nach" sagt, geht sonst
            # davon aus, dass es gilt, und wundert sich beim naechsten
            # Mal ueber dieselbe Frage. Hier stand ein nacktes return.
            print(f"  ~ keine Freigabe erteilt ({werkzeug}: kein Ort erkennbar)")
            await self._sagen(
                "Diesmal mache ich es. Eine Dauerfreigabe lege ich dafür "
                "nicht an — ich konnte nicht erkennen, worauf sie sich "
                "beziehen soll."
            )
            return
        print(f"  ~ Freigabe erteilt: {was}")
        self.anzeige.freigabe(*self.freigaben.anzeige_stand())
        await self._sagen(f"Gut. {was} frage ich nicht mehr nach.")

    async def _antwort_hoeren(self) -> None:
        """Aufnahme als Antwort auf eine offene Rueckfrage auswerten."""
        proben = await asyncio.to_thread(self.aufnehmer.stop)
        dauer = len(proben) / config.ABTASTRATE
        if dauer < config.MIN_AUFNAHME_SEK:
            # Der Parallelfall in _durchgang druckt hier, dieser nicht --
            # wer die Taste nur antippt, sah 25 Sekunden lang gar nichts
            # und suchte den Fehler beim Mikrofon. Die Future bleibt
            # bewusst offen: Weiterwarten ist hier richtig.
            print(f"  (Antwort nur {dauer:.2f}s -- verworfen, ich warte weiter)")
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
        self.durchgang += 1          # alles Aeltere ist ab jetzt ungueltig
        self.lautsprecher.abbrechen()
        if self.aufgabe is not None and not self.aufgabe.done():
            self.aufgabe.cancel()
            try:
                await self.aufgabe
            except (asyncio.CancelledError, Exception):
                pass
        self.aufgabe = None
        # Der letzte Satz war angemeldet, gesagt wird er nicht mehr -- also
        # abmelden. Wurde das vergessen, blieb der Horcher auf "spricht"
        # stehen und meldete keinen Pegel mehr an den Ring; die Anzeige
        # zeigte danach nicht mehr, dass das Mikrofon gehoert wird.
        self.horcher.spricht(None)
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
            # Gezaehlt, nicht geschaetzt: Was hier steht, ist die Laenge
            # der Liste, die gerade gebaut wurde. Faellt ein Dienst aus
            # (kein Google-Zugang, kein Finanzschluessel), sagt er
            # entsprechend weniger -- und das ist richtig so.
            werkzeuge=len(self.werkzeugnamen),
        )
        self.anzeige.zustand(SPRICHT)
        self.anzeige.untertitel("sarvis", text)
        # Der Horcher laeuft jetzt schon -- also den Satz anmelden, damit
        # der Echo-Filter seine eigenen Worte kennt und er sich nicht
        # selbst weckt.
        self.horcher.spricht(text)
        try:
            proben, rate = self.mund.sprechen(text)
            if len(proben):
                self.lautsprecher.sagen(proben, rate)
                self.lautsprecher.warten()
        except Exception as e:
            print(f"  (Begruessung fehlgeschlagen: {e})")
        self.anzeige.zustand(RUHIG)
        self.anzeige.untertitel("sarvis", text)
        self.horcher.spricht(None)
        # Wer direkt nach dem Startsatz loslegt, meint ihn -- genauso wie
        # nach jeder anderen Antwort. Ohne dieses Fenster muesste man dem
        # Geraet, das sich gerade vorgestellt hat, mit "Hey Sarvis"
        # antworten, und genau das hat bisher jeden Anlauf gekostet.
        self.horcher.nachhoeren()
        self.anzeige.nachhoeren(config.NACHHOEREN_SEK)

    async def _antworten(self, gesagt: str, t_los: float) -> None:
        # Die Freigabe-Anzeige bei jedem Zuruf nachziehen: Sie zaehlt
        # zwar von selbst herunter, aber die Minutenangabe stammt vom
        # Zeitpunkt der Erteilung und waere sonst bald falsch.
        self.anzeige.freigabe(*self.freigaben.anzeige_stand())
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

        # Der Anstupser gilt fuer genau diesen einen Zuruf. Ob Sarvis
        # ihn befolgt hat, entscheidet sich unten; stehenbleiben darf er
        # nicht, sonst mahnt er dieselbe Sache in jedem weiteren Zug an.
        self._anstupser = ""
        # Merkposten fuer nachher: Fiel hier ein Entscheidungswort, und
        # wie oft war bis jetzt etwas gemerkt worden?
        klang_entschieden = klingt_nach_entscheidung(gesagt)
        stand_vorher = erinnern.schreibstand()

        sammler = Satzsammler()
        erster_ton: float | None = None
        erstes_wort: float | None = None
        ganze_antwort: list[str] = []
        gesprochen: list[str] = []
        marke = self.durchgang       # woran dieser Durchgang haengt

        def vorlesen(satz: str) -> None:
            nonlocal erster_ton
            if self.abgebrochen or self.durchgang != marke:
                return
            # Beim Reinreden bleibt das Ohr offen -- der Satz geht mit,
            # damit _eigen_echo seine eigene Stimme aussortieren kann.
            self.horcher.spricht(satz)
            heraus = False
            try:
                proben, rate = self.mund.sprechen(satz)
                # Die Synthese laeuft in einem Faden und laesst sich nicht
                # abbrechen -- also danach nochmal nachsehen, sonst rutscht
                # der gerade fertige Satz nach dem Abbruch doch noch heraus.
                if (len(proben) and not self.abgebrochen
                        and self.durchgang == marke):
                    if erster_ton is None:
                        erster_ton = time.perf_counter()
                        self.anzeige.zustand(SPRICHT)
                    gesprochen.append(satz)
                    self.anzeige.untertitel("sarvis", " ".join(gesprochen))
                    self.lautsprecher.sagen(proben, rate)
                    heraus = True
            finally:
                # Wurde der Satz nicht gesagt, wird seine Anmeldung wieder
                # zurueckgenommen. Sonst blieb der Horcher nach einem
                # Abbruch auf "spricht" stehen -- das spricht(None) unten
                # wird dann nie erreicht, und keiner der drei finally-
                # Bloecke holt es nach. Der Horcher meldet in diesem
                # Zustand keinen Mikrofonpegel mehr (weckwort._block), der
                # Ring der Anzeige steht still, und nach jedem Not-Aus
                # sieht es aus, als sei das Mikrofon tot. Gemessen: genau
                # dieses Bild hat mehrfach Zeit gekostet.
                #
                # Bewusst am tatsaechlich Gesagten festgemacht und nicht an
                # self.abgebrochen: Dieser Faden laeuft nach dem Abbruch
                # weiter, und die Schleife setzt die Flagge inzwischen
                # schon wieder auf False -- ein spaeter Blick darauf
                # verpasste den Abbruch.
                if not heraus:
                    self.horcher.spricht(None)

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
        # Fiel ein Entscheidungswort und wurde trotzdem nichts
        # festgehalten? Dann steht beim naechsten Zuruf ein Hinweis im
        # Vorspann. Kein Modellaufruf, keine Wartezeit -- nur eine Zeile,
        # die beim naechsten Mal garantiert ankommt.
        if klang_entschieden and erinnern.schreibstand() == stand_vorher:
            self._anstupser = entscheidung_verpasst(gesagt)
            print("  (Entscheidungswort gefallen, nichts gemerkt — "
                  "ich hake beim nächsten Zuruf nach)")

        await self._kontext_wache()

    async def _kontext_wache(self) -> None:
        """Nach der Antwort nachsehen, ob der Kopf zu voll wird.

        Hier und nicht vor dem naechsten Zuruf: Verdichten kostet einen
        Modellaufruf und ein paar Sekunden. Davor waere das eine Pause
        mitten im Gespraech -- danach merkt es niemand.

        Das SDK verdichtet zwar von selbst, aber erst bei 96,7 % des
        Fensters. Das ist aus zwei Gruenden zu spaet: Es passiert dann
        mitten in einer Antwort, und WAS zusammengefasst wird, entscheidet
        niemand.
        """
        if not config.KONTEXT_WACHE:
            return
        # Nach einer Verdichtung eine Weile Ruhe. Ohne diese Sperre
        # versuchte die Wache es nach jedem Zuruf erneut -- und wenn die
        # Zusammenfassung nichts mehr wegnimmt, waere das eine Schleife,
        # die bei jedem Wort Geld kostet.
        if time.monotonic() < self._verdichtet_bis:
            return
        anteil = await self.hirn.kontext_anteil()
        if anteil is None:
            return
        print(f"  ---- Kontext {anteil * 100:.0f} %")
        if anteil < config.KONTEXT_VERDICHTEN_AB:
            return

        print("  ---- verdichte den Verlauf")
        self.anzeige.zustand(DENKT)
        geschafft = await self.hirn.verdichten(
            config.KONTEXT_VERDICHTEN_ANWEISUNG)
        self.anzeige.zustand(RUHIG)
        # Die Sperre gilt auch, wenn es NICHT geklappt hat: Ein Fehler,
        # der sich nach jedem Zuruf wiederholt, ist keine Wache mehr.
        self._verdichtet_bis = (time.monotonic()
                                + config.KONTEXT_VERDICHTEN_PAUSE_SEK)
        if not geschafft:
            return
        nachher = await self.hirn.kontext_anteil()
        if nachher is not None:
            print(f"  ---- Kontext jetzt {nachher * 100:.0f} %")
        # Gesagt wird es, weil Sarvis hinterher Feinheiten von vorhin
        # nicht mehr weiss. Stumm verdichten hiesse: Er wird ploetzlich
        # vergesslich, und niemand erfaehrt warum.
        await self._sagen(config.KONTEXT_VERDICHTET_SATZ)

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
            if anmeldung.klingt_nach_anmeldung(e):
                # Nicht die englische Ausnahme vorlesen lassen. Wer
                # gerade redet, will wissen was los ist, nicht welche
                # Ausnahme geflogen ist.
                print(f"    -> {anmeldung.RAT}")
                # Die Wache aus dem Warten holen: Wer gerade nicht
                # zuhoert, soll es trotzdem erfahren, und zwar jetzt
                # und nicht in einer halben Stunde.
                anmeldung.jetzt_nachsehen()
                await self.von_selbst_sagen(anmeldung.satz(), mit_gong=False)
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
            if anmeldung.klingt_nach_anmeldung(e):
                # Nicht die englische Ausnahme vorlesen lassen. Wer
                # gerade redet, will wissen was los ist, nicht welche
                # Ausnahme geflogen ist.
                print(f"    -> {anmeldung.RAT}")
                # Die Wache aus dem Warten holen: Wer gerade nicht
                # zuhoert, soll es trotzdem erfahren, und zwar jetzt
                # und nicht in einer halben Stunde.
                anmeldung.jetzt_nachsehen()
                await self.von_selbst_sagen(anmeldung.satz(), mit_gong=False)
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
            if anmeldung.klingt_nach_anmeldung(e):
                # Nicht die englische Ausnahme vorlesen lassen. Wer
                # gerade redet, will wissen was los ist, nicht welche
                # Ausnahme geflogen ist.
                print(f"    -> {anmeldung.RAT}")
                # Die Wache aus dem Warten holen: Wer gerade nicht
                # zuhoert, soll es trotzdem erfahren, und zwar jetzt
                # und nicht in einer halben Stunde.
                anmeldung.jetzt_nachsehen()
                await self.von_selbst_sagen(anmeldung.satz(), mit_gong=False)
            self.anzeige.zustand(RUHIG)
        finally:
            self.arbeitet = False
            self.aufgabe = None
            self.horcher.pause(False)
            self.horcher.nachhoeren()
            self.anzeige.nachhoeren(config.NACHHOEREN_SEK)

    async def _durchgang(self) -> None:
        proben = await asyncio.to_thread(self.aufnehmer.stop)
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

    async def _netz_aufbauen(self) -> None:
        """Anzeige und Stimme ans Netz haengen, Endpunkt hochfahren.

        Erst hier und nicht im Konstruktor: Der Traeger braucht die
        laufende Ereignisschleife, um aus fremden Faeden einlegen zu
        koennen (call_soon_threadsafe).
        """
        from .netz import server
        from .netz.klang_netz import NetzLautsprecher
        from .netz.traeger import NetzTraeger

        self.traeger = NetzTraeger(self.schleife)
        self.anzeige = Anzeige(True, traeger=self.traeger)
        # Jetzt gilt der Netz-Traeger. Ohne diese Zeile schickten
        # kacheln.py, bericht.py und programme.py weiter per UDP an ein
        # Fenster, das es auf dem Server nicht gibt -- und zwar still.
        anzeige_modul.setzen(self.anzeige)
        self.lautsprecher = NetzLautsprecher(self.traeger,
                                             melden=self._pegel)
        # Der Horch braucht den Traeger, um dem Client zu sagen, wann er
        # aufhoeren soll -- waehrend Sarvis redet, will niemand den
        # Strom, und ohne dieses Wort laeuft der Rueckstand auf.
        self.horch.traeger = self.traeger
        self.endpunkt = server.Endpunkt(zuruf_an=self._zuruf_vom_netz,
                                        sprache_an=self._sprache_vom_netz,
                                        strom_an=self._strom_vom_netz,
                                        auto_an=self._auto_vom_netz,
                                        weg_an=self._oberflaeche_weg)
        await server.starten(self.endpunkt, self.traeger, config.NETZ_HAFEN)
        print(f"  Endpunkt  : 127.0.0.1:{config.NETZ_HAFEN}")

    async def _zuruf_vom_netz(self, text: str, geraet: str) -> None:
        """Eine getippte Zeile von einer Oberflaeche.

        Geht denselben Weg wie ein Weckwort-Zuruf: Der Text steht schon
        fest, es ist nichts aufzunehmen. Damit gilt auch dieselbe Regel
        fuers Reinreden -- wer tippt, waehrend Sarvis redet, unterbricht
        ihn, so wie wenn er dazwischenspraeche.
        """
        print(f"\n  Du ({geraet}): {text}")
        self._antwort_an(geraet)
        self.anzeige.untertitel("du", text)
        self.schlange.put_nowait(("weckwort", text))

    async def _auto_vom_netz(self, an: bool, geraet: str) -> None:
        """Die Oberflaeche steckt jetzt im Auto -- oder eben nicht mehr."""
        self.horcher.im_auto(an, geraet)

    async def _strom_vom_netz(self, daten: str, rate: int, geraet: str) -> None:
        """Ein Stueck Dauerstrom fuers Weckwort.

        Geht direkt an den Horch und nicht durch die Schleife: Es kommen
        mehrere Buendel je Sekunde, und jedes davon durch die
        Gespraechslogik zu schleusen waere Arbeit fuer nichts. Was
        daraus wird, entscheidet der Weckwort-Faden -- in aller Regel
        naemlich: nichts.
        """
        self.horch.hinein(daten, rate, geraet)

    def _antwort_an(self, geraet: str) -> None:
        """Wem die naechste gesprochene Antwort gilt.

        Sehen sollen alle dasselbe -- Zustand, Kacheln, Untertitel gehen
        auf jeden Bildschirm, der zusieht. HOEREN nicht: Wer am Rechner
        fragt, will die Antwort im Kopfhoerer und nicht aus dem Handy in
        der Jacke im Flur.

        Gemessen genau so passiert, und es ist mehr als unbequem: Ein
        Assistent, der woanders antwortet als man ihn gefragt hat, ist
        im Zweifel gar nicht zu hoeren.
        """
        # Der lokale Lautsprecher kennt kein Ziel -- er IST das Geraet.
        # Nur der ueber Netz muss wissen, wohin.
        if hasattr(self.lautsprecher, "ziel"):
            self.lautsprecher.ziel = geraet
        # Und dieselbe Auskunft fuer die Werkzeuge: Das Radio gehoert auf
        # dasselbe Geraet wie die Stimme, kommt aber nicht am
        # Lautsprecher vorbei an diese Information.
        anzeige_modul.zielen(geraet)

    async def _oberflaeche_weg(self, geraet: str) -> None:
        """Eine Oberflaeche hat sich verabschiedet."""
        self.horch.geht(geraet)

    async def _sprache_vom_netz(self, proben, geraet: str) -> None:
        """Eine fertige Aufnahme von einer Oberflaeche.

        Whisper laeuft hier und nicht in der Schleife: Er braucht auf der
        Karte rund 0,2 Sekunden, und die gehoeren in einen Faden. Was
        dabei herauskommt, geht denselben Weg wie ein Weckwort.
        """
        if proben is None or not len(proben):
            return
        sek = len(proben) / config.ABTASTRATE
        if sek < config.MIN_AUFNAHME_SEK:
            return          # versehentlich getippt

        # Wie laut war das ueberhaupt? Ohne diese Zeile sieht man bei
        # einer stummen Aufnahme nur "Whisper 0.10s" und ein leeres
        # Ergebnis -- und sucht den Fehler bei Whisper, obwohl er beim
        # Mikrofon liegt. Der Spitzenwert trennt die drei Faelle
        # zuverlaessig: 0.000 = gar kein Signal, unter 0.01 = viel zu
        # leise (Verstaerkung, falsches Geraet), darueber = Whisper
        # hatte wirklich nichts zu verstehen.
        import numpy as _np
        spitze = float(_np.max(_np.abs(proben))) if len(proben) else 0.0
        rms = float(_np.sqrt(_np.mean(_np.square(proben)))) if len(proben) else 0.0
        if spitze < 0.01:
            print(f"  ({geraet}: {sek:.1f}s angekommen, aber praktisch "
                  f"still -- Spitze {spitze:.4f}, RMS {rms:.4f}. "
                  f"Mikrofon, Verstaerkung oder falsches Geraet?)")
        self.anzeige.zustand(DENKT)
        t = time.perf_counter()
        try:
            gesagt = await asyncio.to_thread(self.ohren.hoeren, proben)
        except Exception as e:
            print(f"  (Whisper: {type(e).__name__}: {e})")
            self.anzeige.zustand(RUHIG)
            return
        print(f"\n  Du ({geraet}): {gesagt}")
        print(f"  ---- Aufnahme {sek:.1f}s | Whisper "
              f"{time.perf_counter() - t:.2f}s | Spitze {spitze:.3f}")
        if not gesagt.strip():
            self.anzeige.zustand(RUHIG)
            return
        self._antwort_an(geraet)
        self.anzeige.untertitel("du", gesagt)
        self.schlange.put_nowait(("weckwort", gesagt))

    async def laufen(self) -> None:
        self.schleife = asyncio.get_running_loop()
        if self.im_netz:
            await self._netz_aufbauen()
        print("  Claude verbindet ...")
        t = time.perf_counter()
        await self.hirn.start()
        print(f"  Claude bereit nach {time.perf_counter() - t:.1f}s")
        for hinweis in self.hirn.hinweise:
            print(f"  Gedaechtnis: {hinweis}")
        # Was von den 77 Werkzeugen wirklich gebaut wurde -- und warum
        # nicht.
        #
        # Drei Gruppen werden nur zugeschaltet, wenn ihre Zugaenge da
        # sind: Finanzen (14), Google (23), Telegram (5). Fehlt eine
        # Datei, fehlen die Werkzeuge, und zwar STILL: Sarvis sieht sie
        # dann einfach nicht und antwortet "das kann ich nicht" statt
        # "mein Zugang fehlt". Im schlimmsten Fall sind es 35 statt 77,
        # und zwei der drei Ausfaelle standen nirgends.
        #
        # Beim ersten Start im Container debuggt man das sonst im
        # Blindflug. Deshalb eine Zeile je Gruppe.
        # Ob sein Kopf ueberhaupt erreichbar ist. Ohne diese Zeile lief
        # Sarvis am 30.08. vier Stunden lang und antwortete auf jeden
        # Zuruf mit "Failed to authenticate" -- auf Englisch, mitten im
        # deutschen Gespraech, und gemerkt hat es niemand bis zum
        # Ausprobieren.
        angemeldet, wie = await anmeldung.pruefen()
        print(f"  Anmeldung  : {wie}")
        if not angemeldet:
            print(f"    -> {anmeldung.RAT}")
        print(f"  Werkzeuge  : {len(self.werkzeugnamen)} gebaut")
        print(f"  Google     : {google.zustand()}")
        print(f"  Telegram   : {'angemeldet' if config.telegram_bereit() else _fehlt(config.TELEGRAM_SITZUNG, 'telegram_anmelden.py ausfuehren')}")
        print(f"  Finanzen   : {'Schlüssel da' if config.finanz_schluessel() else 'kein FD_API_SCHLUESSEL in der .env -- 14 Werkzeuge fehlen'}")
        print(f"  Daten      : {config.DATEN}{'' if config.DATEN.is_dir() else '   FEHLT -- Gedaechtnis, Timer und Zugaenge liegen dort'}")

        print("  Warmlaufen ...")
        await asyncio.to_thread(self.ohren.aufwaermen)
        await asyncio.to_thread(self.mund.aufwaermen)

        # Das Ohr geht VOR der Begruessung auf.
        #
        # Vorher stand horcher.start() ein Stueck weiter unten: Waehrend
        # er sich vorstellte -- und in den Sekunden danach, in denen das
        # VAD-Modell erst noch laedt -- lief kein einziger Mikrofonstrom.
        # Wer direkt nach dem Startsatz losredete, wurde nicht ueberhoert,
        # er wurde nie gehoert. Ein Zuruf aus dieser Zeit landet jetzt in
        # der Schlange und wird abgeholt, sobald die Schleife unten steht.
        if self.horcher.start():
            print(f"  Weckwort aktiv: \"Hey {config.NAME.capitalize()}\"")

        await asyncio.to_thread(self._begruessen)

        # Timer, die den letzten Lauf ueberlebt haben, wieder scharf machen.
        for meldung in await self.wecker.wiederherstellen():
            await self.von_selbst_sagen(meldung)

        lauscher = _Nichts() if self.im_netz else keyboard.Listener(
            on_press=self._runter, on_release=self._hoch)
        lauscher.start()

        # Erste Begruessung im Voraus erzeugen, solange noch nichts los ist.
        asyncio.create_task(self._gruss_vorbereiten())

        # Eigener Lauscher fuer die Tastenkombination -- der Push-to-talk-
        # Lauscher sieht nur einzelne Tasten, keine Kombinationen.
        # Der Not-Aus haengt ausdruecklich NICHT an config.ANZEIGE. Wer die
        # Anzeige abschaltet, verliert sonst die einzige Moeglichkeit, Sarvis
        # mitten im Satz zu stoppen -- und merkt es erst, wenn er sie braucht.
        schalter = None
        tasten = {} if self.im_netz else {config.TASTE_STOPP: self._stopp_taste}
        if config.ANZEIGE and not self.im_netz:
            tasten[config.TASTE_VERSCHIEBEN] = self._verschieben_umschalten
        # Im Netzbetrieb gibt es keine Tastatur, an die sich ein Haken
        # haengen liesse -- pynput ist gar nicht erst geladen. Ohne diese
        # Bedingung meldete der Start "'NoneType' object has no attribute
        # 'GlobalHotKeys'". Kein Schaden, aber eine Fehlermeldung, die
        # nichts bedeutet, kostet beim naechsten echten Fehler
        # Aufmerksamkeit -- man liest sie irgendwann nicht mehr.
        if tasten:
            try:
                schalter = keyboard.GlobalHotKeys(tasten)
                schalter.start()
            except Exception as e:
                print(f"  (Tastenkombinationen gingen nicht: {e})")

        print("\n" + "=" * 62)
        if self.im_netz:
            # Was hier steht, muss stimmen. Eine Startzeile, die zum
            # Tastendruck auffordert, wo es keine Tastatur gibt, ist der
            # Anfang davon, dass niemand mehr hinsieht.
            print(f"  Sarvis laeuft.  Erreichbar ueber den Draht auf "
                  f"127.0.0.1:{config.NETZ_HAFEN}.")
            print("  Bedient wird er von aussen -- Weboberflaeche, App, "
                  "Telegram.")
        else:
            print(f"  Sarvis laeuft.  [{config.TASTE.upper()}] halten, "
                  f"reden, loslassen.")
            if config.ANZEIGE:
                print(f"  Anzeige verschieben: {config.TASTE_VERSCHIEBEN}")
            print(f"  Sofort still: {config.TASTE_STOPP}")
        print("  Strg+C zum Beenden.")
        print("=" * 62)

        melder = asyncio.create_task(self._hintergrund_melden())
        stimme = asyncio.create_task(self._melder())
        # Sieht von selbst nach, ob der Zugang zu Claude noch gilt, und
        # schreibt Sascha an, wenn nicht. Alles andere hier meldet erst,
        # wenn jemand zuhoert -- das ist genau der Fall, der am
        # 31.08.2026 vier Stunden lang nicht eintrat.
        zugangswache = asyncio.create_task(
            anmeldung.wache(sagen=lambda s: self.von_selbst_sagen(
                s, mit_gong=False)))
        try:
            while True:
                befehl = await self.schlange.get()
                antwortet = self.antwort is not None and not self.antwort.done()

                # Weckwort: der Zuruf steckt schon im selben Satz, es muss
                # also nichts mehr aufgenommen werden.
                if isinstance(befehl, tuple) and befehl[0] == "weckwort":
                    zuruf = befehl[1]
                    if antwortet:
                        # "Hör auf" waehrend einer offenen Frage stoppte
                        # bisher nichts: Der Satz ging als Antwort in die
                        # Future, und ist_stopp wird nur in _antworten
                        # gefragt -- laufende Hintergrundauftraege liefen
                        # weiter. Ein klares Ja bleibt aber ein Ja:
                        # "ja, hör auf zu fragen" ist eine Freigabe und
                        # kein Not-Aus.
                        if (rueckfrage.ist_stopp(zuruf)
                                and rueckfrage.deuten(zuruf) != "ja"):
                            if self.arbeitet or self.aufgabe is not None:
                                await self._unterbrechen()
                            await self._alles_stoppen()
                            continue
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
                    await asyncio.to_thread(self.aufnehmer.start)
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
            stimme.cancel()
            zugangswache.cancel()
            lauscher.stop()
            self.horcher.stopp()
            # schliessen() gab es, aufgerufen hat es nie jemand -- die
            # Telegram-Verbindung blieb beim Beenden offen stehen.
            try:
                from .werkzeuge import telegram
                await asyncio.to_thread(telegram.schliessen)
            except Exception as e:
                print(f"  (Telegram-Verbindung nicht sauber getrennt: {e})")
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
