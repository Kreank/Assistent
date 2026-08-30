"""Der Weckwort-Dauerstrom, wenn das Mikrofon woanders steht.

Damit funktioniert "Hey Sarvis" ohne Tastendruck auch, wenn Sarvis auf
einem Server ohne Mikrofon laeuft: Eine Oberflaeche haelt ihres offen
und schickt blockweise, was sie hoert.

WER SENDET UND WER NICHT

Das entscheidet die Oberflaeche, nicht der Server -- und das ist keine
Bequemlichkeit, sondern der Unterschied zwischen brauchbar und nicht:

    Am Rechner    einfach durchsenden. 16 kHz int16 sind 256 kbit/s,
                  im heimischen Netz ein halbes Promille einer
                  Gigabit-Leitung, und es faellt kein Volumen an.
    Am Handy      besser gar nicht. Rund 260 MB am Tag, auch wenn
                  niemand redet, und das Mikrofon dauerhaft offen.
                  Dort bleibt es bei Push-to-talk.

Meldet niemand einen Strom, liefert dieser Horch schlicht nichts. Der
Weckwort-Faden dreht dann Leerlauf, und Sarvis hoert nur auf das, was
ihm geschickt wird. Das ist der Normalfall und kein Fehler.

DIE ERKENNUNG BLEIBT HIER

Der Client liefert nur Rohton. Ob jemand "Hey Sarvis" gesagt hat,
entscheidet weiterhin der Server -- Silero-VAD, dann Whisper, dann der
Aehnlichkeitsvergleich mit seinen gemessenen Schwellen (sarvis 1,00,
jarvis 0,83, service 0,62, serviert 0,57, Grenze 0,60). Das ist die
Stelle, an der die Arbeit steckt, und sie soll nicht in drei
Oberflaechen dreimal existieren und dreimal auseinanderlaufen.

DIE BLOCKGROESSE IST EINE BEDINGUNG, KEINE EMPFEHLUNG

Silero rechnet in Rahmen von 480 Werten bei 16 kHz. Kommt etwas anderes
an, wird hier neu geblockt -- und zwar hier und nicht beim Client, weil
sonst jede Oberflaeche dieselbe Zeile richtig hinbekommen muesste.

Der Fehler faellt naemlich nicht auf: Der VAD sagt bei falscher Blockung
nicht "Fehler", er sagt nur oefter das Falsche.
"""
import base64
import queue
import threading

import numpy as np

BLOCK = 480
RATE = 16000

# Wie viele Bloecke warten duerfen, bevor Aelteres wegfliegt.
# 200 Bloecke sind 6,0 Sekunden -- so lange darf der Server hinterher
# sein, bevor das Zuhoeren zum Vorlesen von Vergangenheit wird.
MAX_RUECKSTAND = 200


class NetzHorch:
    """klang.Dauerhorch, gefuettert von einer Oberflaeche."""

    rate = RATE
    block = BLOCK

    def __init__(self, traeger=None):
        self.traeger = traeger
        self._eingang: queue.Queue = queue.Queue()
        self._rest = np.zeros(0, dtype="float32")
        self._samples = 0
        self._meldung: str | None = None
        self._schloss = threading.Lock()
        self._pausiert = False
        # Wer gerade sendet. Nur EINE Oberflaeche zur Zeit -- zwei
        # Mikrofone in einen Strom zu mischen ergaebe Kauderwelsch, und
        # der VAD saehe dauernd Sprache.
        self.quelle: str | None = None

    # --- Vom Endpunkt gefuettert ------------------------------------------

    def hinein(self, daten: str, rate: int, geraet: str) -> None:
        """Ein Stueck Dauerstrom von einer Oberflaeche.

        Wird aus der Ereignisschleife gerufen und darf nichts Langsames
        tun -- das Umblocken passiert erst beim Abholen, im
        Weckwort-Faden.
        """
        if self._pausiert:
            return
        if self.quelle is None:
            self.quelle = geraet
            print(f"  (Weckwort: {geraet} sendet jetzt mit)")
        elif self.quelle != geraet:
            return          # eine zur Zeit, siehe oben
        if rate != RATE:
            # Nicht selbst umtasten: Ohne Tiefpass gaebe das Aliasing,
            # und mit waere es Arbeit im falschen Faden. Die Oberflaeche
            # kann ihren AudioContext gleich richtig anfordern.
            self._meldung = (f"{geraet} schickt {rate} Hz statt {RATE} -- "
                             "verworfen")
            return
        try:
            roh = base64.b64decode(daten, validate=True)
        except Exception:
            return
        if not roh or len(roh) % 2:
            return
        werte = np.frombuffer(roh, dtype="<i2").astype("float32") / 32768.0
        if self._eingang.qsize() > MAX_RUECKSTAND:
            weg = 0
            while self._eingang.qsize() > MAX_RUECKSTAND // 2:
                try:
                    self._eingang.get_nowait()
                    weg += 1
                except queue.Empty:
                    break
            self._meldung = (f"Horcher kommt nicht nach: {weg} Bloecke "
                             "verworfen, Aelteres zuerst")
        self._eingang.put(werte)

    def geht(self, geraet: str) -> None:
        """Die sendende Oberflaeche ist weg."""
        if self.quelle == geraet:
            self.quelle = None
            self._meldung = f"{geraet} sendet nicht mehr mit"
            with self._schloss:
                self._rest = np.zeros(0, dtype="float32")

    # --- Vertrag ---------------------------------------------------------

    def oeffnen(self) -> None:
        pass          # es gibt nichts zu oeffnen; jemand sendet oder nicht

    def bloecke(self):
        """Genau BLOCK Werte je Stueck -- was nicht aufgeht, bleibt liegen.

        Der Rest zwischen zwei Sendungen wird MITGENOMMEN, nicht
        weggeworfen. Sonst faellt an jeder Sendungsgrenze ein Stueck
        Ton unter den Tisch, und bei 300-Millisekunden-Buendeln waere
        das dreimal in der Sekunde ein Loch -- hoerbar wuerde es nicht,
        aber der VAD saehe Sprache abreissen, wo keine abreisst.
        """
        while True:
            try:
                stueck = self._eingang.get(timeout=0.5)
            except queue.Empty:
                return          # der Aufrufer sieht nach, ob er noch laeuft
            with self._schloss:
                self._rest = (np.concatenate([self._rest, stueck])
                              if len(self._rest) else stueck)
                while len(self._rest) >= BLOCK:
                    block, self._rest = self._rest[:BLOCK], self._rest[BLOCK:]
                    self._samples += BLOCK
                    # Stromzeit aus Samples, nicht aus der Wanduhr: Der
                    # Horcher vergleicht sie mit dem Nachhoerfenster und
                    # dem Echo-Filter, und ueber Netz liegen zwischen
                    # beiden zwei Laufzeiten in verschiedene Richtungen.
                    yield block, self._samples / RATE

    def aussetzer(self) -> str | None:
        m, self._meldung = self._meldung, None
        return m

    def senden_pausieren(self, an: bool) -> None:
        """Der Oberflaeche sagen, dass sie aufhoeren soll.

        Waehrend Sarvis selbst spricht oder eine Rueckfrage laeuft,
        braucht niemand den Strom. Lokal war das ein No-op -- man
        ueberspringt einfach die Verarbeitung. Ueber Netz ist es wichtig:
        Der Client sendet sonst weiter, der Rueckstand laeuft auf, und
        der Deckel wirft am Ende echte Sprache weg.
        """
        self._pausiert = bool(an)
        if an:
            while not self._eingang.empty():
                try:
                    self._eingang.get_nowait()
                except queue.Empty:
                    break
            with self._schloss:
                self._rest = np.zeros(0, dtype="float32")
        if self.traeger is not None:
            self.traeger.senden({"art": "horchen", "an": not an})

    def schliessen(self) -> None:
        self.quelle = None
