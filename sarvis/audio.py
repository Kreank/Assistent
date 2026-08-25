"""Aufnahme und Wiedergabe. Duenne Schicht ueber sounddevice.

Beide Seiten melden ihren Pegel an die Anzeige weiter -- beim Zuhoeren deine
Stimme, beim Sprechen seine. Der Ring schlaegt dadurch mit dem echten Signal
aus und nicht mit einer Animation, die so tut als ob.
"""
import queue
import threading
import time
from typing import Callable

import numpy as np
import sounddevice as sd

from . import config

HOP = 0.025       # Sekunden je Pegelwert
AUSKLANG = 0.30   # Sekunden Stille hinter jeder Aeusserung


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


def _pegel(block: np.ndarray) -> float:
    """Lautstaerke eines Blocks auf 0..1, mit Kurve fuers Auge."""
    if not len(block):
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
    return float(min(1.0, (rms / 0.14) ** 0.6)) if rms > 1e-6 else 0.0


class Aufnehmer:
    """Push-to-talk-Aufnahme. start() sammelt, stop() liefert das Ergebnis."""

    def __init__(
        self,
        rate: int = config.ABTASTRATE,
        melden: Callable[[float], None] | None = None,
    ):
        self.rate = rate
        self.melden = melden
        self._brocken: list[np.ndarray] = []
        self._strom: sd.InputStream | None = None
        self._schloss = threading.Lock()

    def _rein(self, daten, rahmen, zeit, status):
        if status:
            print(f"  (Mikro meldet: {status})")
        with self._schloss:
            self._brocken.append(daten.copy())
        if self.melden is not None:
            self.melden(_pegel(daten))

    def start(self) -> None:
        if self._strom is not None:
            return
        with self._schloss:
            self._brocken = []
        self._strom = sd.InputStream(
            samplerate=self.rate,
            channels=1,
            dtype="float32",
            blocksize=int(self.rate * HOP),
            callback=self._rein,
        )
        self._strom.start()

    def stop(self) -> np.ndarray:
        if self._strom is None:
            return np.zeros(0, dtype="float32")
        self._strom.stop()
        self._strom.close()
        self._strom = None
        if self.melden is not None:
            self.melden(0.0)
        with self._schloss:
            brocken = self._brocken
            self._brocken = []
        if not brocken:
            return np.zeros(0, dtype="float32")
        return np.concatenate(brocken, axis=0).flatten()


class Lautsprecher:
    """Spielt Bloecke der Reihe nach ab. Ein Faden, eine Warteschlange."""

    def __init__(self, melden: Callable[[float], None] | None = None):
        self.melden = melden
        self._schlange: queue.Queue = queue.Queue()
        self.leer = threading.Event()
        self.leer.set()
        self._faden = threading.Thread(target=self._schleife, daemon=True)
        self._faden.start()

    @staticmethod
    def _huellkurve(proben: np.ndarray, rate: int) -> np.ndarray:
        """Pegel je HOP-Fenster -- daraus speist sich der Ausschlag."""
        schritt = max(1, int(rate * HOP))
        n = len(proben) // schritt
        if n <= 0:
            return np.zeros(0, dtype="float32")
        teile = proben[: n * schritt].reshape(n, schritt)
        rms = np.sqrt(np.mean(np.square(teile, dtype=np.float64), axis=1))
        return np.clip((rms / 0.14) ** 0.6, 0.0, 1.0).astype("float32")

    def _abspielen(self, proben: np.ndarray, rate: int) -> None:
        # Stille anhaengen, sonst frisst die Ausgabe die letzte Silbe.
        # sd.wait() kehrt zurueck, sobald der Geraetepuffer gefuellt ist --
        # nicht, wenn er ausgespielt ist. Der naechste sd.play() bricht den
        # Rest dann ab ("...2026" wurde zu "...202"). Piper liefert nur rund
        # 100 ms Auslauf, das reicht dafuer nicht.
        proben = np.concatenate(
            [proben, np.zeros(int(rate * AUSKLANG), dtype=proben.dtype)]
        )
        huelle = self._huellkurve(proben, rate)
        sd.play(proben, rate)
        if self.melden is None or not len(huelle):
            sd.wait()
            return
        # Mitlaufen statt blockieren: der Pegel folgt der Abspielposition.
        beginn = time.perf_counter()
        dauer = len(proben) / rate
        i = 0
        while True:
            vergangen = time.perf_counter() - beginn
            if vergangen >= dauer:
                break
            i = min(len(huelle) - 1, int(vergangen / HOP))
            self.melden(float(huelle[i]))
            time.sleep(HOP / 2)
        sd.wait()

    def _schleife(self):
        while True:
            posten = self._schlange.get()
            if posten is None:
                continue
            proben, rate = posten
            try:
                self._abspielen(proben, rate)
            except Exception as e:  # ein kaputter Block darf nicht alles killen
                print(f"  (Wiedergabe fehlgeschlagen: {e})")
            finally:
                if self._schlange.empty():
                    if self.melden is not None:
                        self.melden(0.0)
                    self.leer.set()

    def sagen(self, proben: np.ndarray, rate: int) -> None:
        self.leer.clear()
        self._schlange.put((proben, rate))

    def abbrechen(self) -> None:
        """Sofort still sein -- mitten im Wort, wenn es sein muss.

        Reihenfolge zaehlt: erst die Warteschlange leeren, dann den Ton
        stoppen. Andersherum zieht der Abspielfaden den naechsten Satz
        heraus und redet weiter.
        """
        while True:
            try:
                self._schlange.get_nowait()
            except queue.Empty:
                break
        sd.stop()
        if self.melden is not None:
            self.melden(0.0)
        self.leer.set()

    def warten(self) -> None:
        self.leer.wait()
