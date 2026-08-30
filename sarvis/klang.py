"""Die Naht zwischen Sarvis und seinem Gehoer, seiner Stimme.

Bis hierher war beides dasselbe wie der Rechner, auf dem er lief:
sounddevice griff auf das Mikrofon zu, das eine Handbreit entfernt lag,
und spielte in Lautsprecher, die im selben Zimmer standen. Auf einem
Server gibt es beides nicht. Sarvis bekommt Sprache von aussen
geschickt und schickt seine Antwort zurueck.

Diese Datei ist der Schnitt dafuer -- und zwar VOR dem Umzug. Sie
aendert heute nichts: aufnehmer() und lautsprecher() liefern dieselben
Klassen aus audio.py wie bisher. Was sie schafft, ist die Stelle, an der
spaeter eine zweite Fassung danebentritt, ohne dass die Gespraechs-
schleife noch einmal angefasst werden muss.

Das ist Absicht. Die Schleife in main.py ist der empfindlichste Teil des
Programms -- Abbruch, Reinreden, Durchgangszaehler, Echo-Filter haengen
darin ineinander. Sie zweimal umzubauen (einmal fuer die Schnittstelle,
einmal fuers Netz) waere zweimal dasselbe Risiko.

DREI ZUSAGEN, DIE JEDE FASSUNG HALTEN MUSS

Sie stehen hier und nicht in audio.py, weil sie nicht die Umsetzung
beschreiben, sondern den Vertrag. Wer die Netzfassung baut, liest sie.

  1. abbrechen() blockiert NIE und darf aus jedem Faden gerufen werden.
     Heute geschieht das aus dreien: aus der Ereignisschleife
     (main.py:174, 522, 587) und aus dem Tastaturfaden von pynput
     (main.py:613). Ein Netz-Aufruf, der dort wartet, friert den Not-Aus
     ein -- also die eine Taste, die immer gehen muss.

  2. sagen() reiht nur ein und spielt nicht selbst ab. Darauf beruht das
     satzweise Vorlesen: Waehrend Satz eins klingt, baut Piper schon
     Satz zwei. Blockierte sagen(), waere aus dem Nebeneinander ein
     Nacheinander -- und das ist laut README der Unterschied zwischen
     "fuehlt sich an wie reden" und "fuehlt sich an wie ein Formular".

  3. Die RUNDE ist die Wahrheit, nicht die Abbruch-Flagge. Jeder
     eingereihte Posten traegt die Runde seines Einlegens; abbrechen()
     zaehlt hoch, und alles Aeltere gilt ab da als ungueltig -- auch
     das, was der Abspielfaden schon herausgezogen hatte.

     Ueber Netz muss die Runde MITGEHEN und der Client selbst verwerfen,
     was aelter ist als seine aktuelle. Sonst kommt genau der Fehler
     zurueck, gegen den der Zaehler gebaut wurde, nur um eine
     Netzlaufzeit versetzt: ein Satz, der schon unterwegs war, spielt
     nach dem "Gestoppt.".

WAS DIE NETZFASSUNG ZUSAETZLICH BEDENKEN MUSS

  - start() kehrt heute zurueck, wenn wirklich aufgenommen wird. Ueber
    Netz liegt dazwischen eine Anfrage und eine Antwort, und der Anfang
    des ersten Wortes geht verloren, wenn der Client nicht schon vorher
    in einen Ringpuffer aufnimmt.

  - stop() liefert heute alles, was da ist. Ueber Netz sind die letzten
    Rahmen noch unterwegs -- daher die Frist und ein Marker fuer den
    letzten Rahmen, sonst fehlt das Satzende.

  - warten() heisst "verklungen", nicht "abgeschickt". Ohne Rueckmeldung
    vom Client waere es eine Luege: main.py setzt danach die Anzeige auf
    RUHIG und meldet den Sprecher ab, waehrend noch Ton kommt. Deshalb
    hat warten() eine Frist und einen Wahrheitswert -- ohne die haengt
    Sarvis bei einem Verbindungsabbruch fuer immer.

  - Der AUSKLANG von 300 ms bleibt Sache der Umsetzung, nicht des
    Aufrufers. Er umgeht heute ein Puffer-Verhalten von PortAudio
    (sd.wait() kehrt zurueck, wenn der Geraetepuffer voll ist, nicht
    wenn er ausgespielt ist -- "zweitausendsechsundzwanzig" wurde zu
    "zweitausendsechsundzwanzi"). Im Browser stellt sich dasselbe
    Problem in anderer Form, und die Loesung gehoert dorthin, wo das
    Geraet ist.

DAS WECKWORT BLEIBT -- ES WECHSELT NUR DIE QUELLE

Ein erster Entwurf hatte es gestrichen, mit dem Argument, dauerhaftes
Mithoeren ueber Netz sei zu teuer. Das stimmt nur fuer einen der beiden
Faelle, und es waere der falsche Verzicht gewesen: "Hey Sarvis" waehrend
der Arbeit zu rufen, ohne eine Taste zu suchen, ist der Unterschied
zwischen einem Assistenten und einem Programm.

Gerechnet, roh und mit Kompression:

    16 kHz, int16      32.000 B/s  =  256 kbit/s  =  2,76 GB am Tag
    Opus 24 kbit/s      3.000 B/s  =   24 kbit/s  =   259 MB am Tag

Am Dev-PC im heimischen Netz ist das gleichgueltig -- 256 kbit/s auf
einer Gigabit-Leitung sind ein halbes Promille, und es faellt kein
Volumen an. Am Handy im Mobilnetz sind 259 MB am Tag zwar machbar, aber
nichts, was man dauerhaft laufen laesst, ohne es zu merken.

Also entscheidet der CLIENT, wann er sendet, nicht der Server:

  Dev-PC    sendet dauerhaft. Der Silero-VAD und die Weckworterkennung
            laufen wie bisher auf dem Server. Nichts geht verloren.
  Handy     laesst den VAD im Browser laufen und sendet nur, wenn
            wirklich jemand redet. Dann kostet der Leerlauf nichts, und
            das Weckwort geht trotzdem.
  Notfall   Push-to-talk. Immer verfuegbar, braucht keinen VAD.

Der wertvolle Teil bleibt dabei serverseitig, und das ist Absicht: Die
Erkennung selbst (Whisper hoert den ganzen Satz, dann wird der Anfang
mit "sarvis" verglichen) ist gemessen und feinjustiert -- sarvis 1,00,
jarvis 0,83, service 0,62, serviert 0,57, Schwelle 0,60. Und sie loest
das, woran openWakeWord scheiterte: Dessen Fertigmodelle sind auf
englische Aussprache trainiert und erreichten fuer "Hey Sarvis" von
einer deutschen Stimme nur 0,09 bis 0,13.

Was der Client liefert, ist deshalb nur der Strom -- nicht die
Entscheidung, ob jemand Sarvis gemeint hat.
"""
from typing import Callable, Protocol, runtime_checkable

import numpy as np

from . import config

# Wie lange Stille an jede Aeusserung angehaengt wird. Zieht hierher um,
# weil es zum Vertrag gehoert und nicht zur Umsetzung -- siehe oben.
AUSKLANG = 0.30


def gong(rate: int = 22050) -> tuple[np.ndarray, int]:
    """Kurzer Zweiklang vor einer Meldung.

    Selbst erzeugt statt als Datei mitgeliefert -- eine Sinuswelle mit
    Huellkurve ist weniger Code als das Einlesen einer WAV. Zweck: Ein
    Timer, den man nur hoert, wenn man ohnehin zuhoert, ist kein Timer.
    """
    stuecke = []
    for hoehe, dauer in ((880.0, 0.13), (1174.7, 0.34)):   # a'' und d'''
        n = int(rate * dauer)
        t = np.arange(n, dtype="float32") / rate
        welle = np.sin(2 * np.pi * hoehe * t, dtype="float32")
        welle += 0.3 * np.sin(2 * np.pi * hoehe * 2 * t, dtype="float32")
        # Weicher Einsatz und Ausklang, sonst knackt es an den Raendern
        anstieg = np.minimum(1.0, np.arange(n) / (rate * 0.012))
        abfall = np.exp(-3.2 * t / dauer)
        stuecke.append((welle * anstieg * abfall * 0.32).astype("float32"))
    pause = np.zeros(int(rate * 0.045), dtype="float32")
    return np.concatenate([stuecke[0], pause, stuecke[1]]), rate


@runtime_checkable
class Aufnehmer(Protocol):
    """Push-to-talk: start() sammelt, stop() liefert."""

    rate: int

    def start(self) -> None:
        """Aufnahme beginnen. Kehrt zurueck, wenn wirklich aufgenommen wird.

        Darf blockieren -- lokal, um den Strom zu oeffnen; ueber Netz, um
        auf die Bestaetigung zu warten. Wird deshalb aus einem Faden
        gerufen, nicht aus der Ereignisschleife.
        """

    def stop(self, frist: float = 2.0) -> np.ndarray:
        """Aufnahme beenden und das Aufgenommene liefern.

        float32, mono, self.rate, eindimensional. Ein leeres Array, wenn
        nichts kam -- NIE None: main.py rechnet unmittelbar mit len().

        frist: wie lange auf nachlaufende Rahmen gewartet wird. Die
        lokale Fassung ignoriert sie, weil es dort keine gibt.
        """

    def pegel_an(self, melden: Callable[[float], None] | None) -> None:
        """Wohin der Ausschlag fuer den Ring gemeldet wird."""


@runtime_checkable
class Lautsprecher(Protocol):
    """Spielt Bloecke der Reihe nach ab."""

    def sagen(self, proben: np.ndarray, rate: int) -> None:
        """Einreihen. Kehrt SOFORT zurueck (Zusage 2)."""

    def abbrechen(self) -> int:
        """Sofort still. Gibt die neue Runde zurueck (Zusagen 1 und 3)."""

    def warten(self, frist: float | None = None) -> bool:
        """Blockiert, bis alles Eingereihte verklungen ist.

        True  = fertig gespielt oder sauber abgebrochen
        False = Frist abgelaufen (nur ueber Netz; lokal nie)
        """

    @property
    def runde(self) -> int:
        """Welche Wiedergaberunde gerade gilt."""

    def pegel_an(self, melden: Callable[[float], None] | None) -> None:
        ...


@runtime_checkable
class Dauerhorch(Protocol):
    """Der Strom fuers Weckwort -- blockweise, ohne Anfang und ohne Ende."""

    rate: int      # 16000
    block: int     # 480

    def oeffnen(self) -> None:
        ...

    def bloecke(self):
        """Liefert (block, stromzeit_sek). block hat GENAU self.block Werte.

        Die 480 sind keine runde Zahl, sondern eine Bedingung: Silero
        rechnet in Rahmen dieser Groesse, und eine andere Blockung
        verfaelscht seine Vorhersage. Opus kennt kein 30-ms-Frame
        (2,5/5/10/20/40/60 ms) -- wer ueber Opus schickt, muss
        serverseitig neu auf 480 blocken. Das ist eine Zeile, die man
        vergisst, und sie faellt nicht auf: Der VAD sagt dann nicht
        "Fehler", er sagt nur oefter das Falsche.

        stromzeit_sek: monoton, ab Streambeginn, aus der Zahl der Samples
        gerechnet -- NICHT aus perf_counter(). Der Horcher fuehrt heute
        drei Zeiten in Wanduhr (_begonnen, _nachhoeren_bis, _eigen_bis)
        und vergleicht sie miteinander; ueber Netz liegen dazwischen zwei
        Laufzeiten in verschiedene Richtungen, und das Nachhoerfenster
        wird mal zu kurz, mal zu lang. Stumm, ohne Fehlermeldung.
        Rechnet alles in Stromzeit, verschwindet das Problem.

        Blockiert hoechstens eine halbe Sekunde und liefert dann nichts,
        damit der Horcher nachsehen kann, ob er noch laufen soll.
        """

    def aussetzer(self) -> str | None:
        """Eine Meldung ueber eine Luecke im Strom, oder None.

        Lokal ist das der PortAudio-Status, ueber Netz ein Abriss der
        Verbindung. Beides ist dasselbe fuer den Horcher: Ein Stueck
        Sprache fehlt, und er soll es sagen duerfen, statt es zu raten.
        """

    def senden_pausieren(self, an: bool) -> None:
        """Lokal folgenlos. Ueber Netz weist es den Client an, waehrend
        einer Pause nichts zu schicken -- sonst laeuft der Rueckstand auf
        und der Deckel wirft echte Sprache weg."""

    def schliessen(self) -> None:
        ...


class LokalHorch:
    """Der Dauerstrom vom Mikrofon dieses Rechners.

    Genau das, was frueher fest in weckwort._schleife stand -- nur
    herausgeloest, damit eine Netzfassung danebentreten kann. Das
    Verhalten ist unveraendert, einschliesslich der beiden Eigenheiten,
    die dort teuer gelernt wurden:

    Im Audio-Rueckruf wird NICHTS gerechnet. Was dort aufhaelt, reisst
    genau das Loch, das die Warteschlange gerade beseitigt.

    Und der Rueckstandsdeckel wirft ALTES weg, nicht neues. Ein Horcher,
    der sechs Sekunden hinterherhinkt, hoert nicht mehr zu, er liest
    Vergangenheit vor.
    """

    rate = 16000
    block = 480          # Silero rechnet in Rahmen dieser Groesse

    MAX_RUECKSTAND = 200   # = 6,0 Sekunden

    def __init__(self):
        import queue as _q
        import threading as _t
        self._eingang = _q.Queue()
        self._uebergelaufen = _t.Event()
        self._strom = None
        self._samples = 0
        self._meldung = None

    def oeffnen(self) -> None:
        import sounddevice as sd

        def herein(daten, rahmen, zeit, status):
            if status:
                self._uebergelaufen.set()
            self._eingang.put(daten[:, 0].copy())

        self._strom = sd.InputStream(samplerate=self.rate, channels=1,
                                     dtype="float32", blocksize=self.block,
                                     callback=herein)
        self._strom.start()

    def bloecke(self):
        import queue as _q
        while True:
            try:
                block = self._eingang.get(timeout=0.5)
            except _q.Empty:
                return          # der Aufrufer sieht nach, ob er noch laeuft
            if self._uebergelaufen.is_set():
                self._uebergelaufen.clear()
                self._meldung = ("Mikro meldet einen Aussetzer -- ein "
                                 "Stueck Aufnahme fehlt")
            rueckstand = self._eingang.qsize()
            if rueckstand > self.MAX_RUECKSTAND:
                while self._eingang.qsize() > self.MAX_RUECKSTAND // 2:
                    try:
                        self._eingang.get_nowait()
                    except _q.Empty:
                        break
                self._meldung = (f"Horcher kommt nicht nach: {rueckstand} "
                                 "Bloecke im Rueckstand, Aelteres verworfen")
            self._samples += len(block)
            # Stromzeit aus SAMPLES, nicht aus der Wanduhr -- siehe die
            # Begruendung im Dauerhorch-Protokoll.
            yield block, self._samples / self.rate

    def aussetzer(self) -> str | None:
        m, self._meldung = self._meldung, None
        return m

    def senden_pausieren(self, an: bool) -> None:
        pass          # lokal gibt es niemanden, dem man das sagen muesste

    def schliessen(self) -> None:
        if self._strom is not None:
            try:
                self._strom.stop()
                self._strom.close()
            except Exception:
                pass
            self._strom = None


def aufnehmer(melden: Callable[[float], None] | None = None) -> Aufnehmer:
    """Der Aufnehmer, den diese Fassung benutzt."""
    if config.KLANG_QUELLE == "netz":
        raise NotImplementedError(
            "Die Netzfassung des Aufnehmers steht noch nicht. "
            "config.KLANG_QUELLE zurueck auf 'lokal' setzen."
        )
    from .audio import Aufnehmer as Lokal
    return Lokal(melden=melden)


def lautsprecher(melden: Callable[[float], None] | None = None) -> Lautsprecher:
    """Der Lautsprecher, den diese Fassung benutzt."""
    if config.KLANG_QUELLE == "netz":
        raise NotImplementedError(
            "Die Netzfassung des Lautsprechers steht noch nicht. "
            "config.KLANG_QUELLE zurueck auf 'lokal' setzen."
        )
    from .audio import Lautsprecher as Lokal
    return Lokal(melden=melden)


def dauerhorch(traeger=None) -> Dauerhorch:
    """Die Quelle fuer den Weckwort-Strom.

    Im Netzbetrieb kommen die Bloecke von einer Oberflaeche, die ihr
    Mikrofon offenhaelt -- der Dev-PC etwa. Meldet keine, liefert der
    Horch schlicht nichts, und der Weckwort-Faden dreht Leerlauf. Das
    ist der Normalfall und kein Fehler: Am Handy will man das Mikrofon
    nicht dauernd offen haben, und dann bleibt es bei Push-to-talk.
    """
    if config.KLANG_QUELLE == "netz":
        from .netz.horch_netz import NetzHorch
        return NetzHorch(traeger)
    return LokalHorch()
