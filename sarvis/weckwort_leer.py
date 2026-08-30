"""Ein Horcher, der nicht horcht -- fuer den Betrieb ohne Mikrofon.

Auf dem Server gibt es keinen Mikrofonstrom. Der echte Horcher in
weckwort.py oeffnet einen sounddevice-Strom, laesst Silero darauf laufen
und weckt bei "Hey Sarvis" -- alles drei setzt ein Geraet voraus, und
schon der IMPORT von weckwort.py scheitert ohne PortAudio.

Diese Fassung hat dieselben sechs Methoden und tut nichts. Sie ist
bewusst kein Platzhalter mit NotImplementedError: Die Schleife in
main.py ruft pause(), spricht() und nachhoeren() an rund zwanzig
Stellen, und jede davon mit einer Ausnahme zu quittieren hiesse, die
Schleife fuer den Netzbetrieb umzuschreiben. Sie soll aber gleich
bleiben -- ein zweiter Ablauf waere eine zweite Stelle, an der man
kuenftig jeden Fehler zweimal sucht.

WAS DAMIT WEGFAELLT UND WAS NICHT

Weg ist nur das ZUHOEREN auf diesem Rechner. Das Weckwort selbst bleibt
moeglich: Die Oberflaeche auf dem Dev-PC kann ihren Mikrofonstrom
schicken, und dann laeuft dieselbe Erkennung wie bisher -- nur eben
gefuettert vom Netz statt von PortAudio. Das ist die Dauerhorch-
Schnittstelle in klang.py; sie ist beschrieben, aber noch nicht gebaut.

Bis dahin gilt: Der Ausloeser liegt auf dem Geraet, an dem jemand sitzt.
Eine gehaltene Taste, eine Sprachnachricht, eine getippte Zeile.

`nachhoeren` und `spricht` fuehren trotzdem Buch. Nicht aus
Ordnungsliebe: main.py liest `frage_offen`, und der Echo-Gedanke
dahinter ("was ich gerade selbst gesagt habe, ist kein Zuruf") gilt
weiter, sobald ein Client seinen Strom schickt.
"""
import time


class Horcher:
    """Dieselbe Schnittstelle wie weckwort.Horcher, ohne Mikrofon."""

    def __init__(self, ohren=None, geweckt=None, anzeige=None):
        self.ohren = ohren
        self._geweckt = geweckt
        self.anzeige = anzeige
        self.pausiert = False
        self.frage_offen = False
        self._spricht_gerade = None
        self._nachhoeren_bis = 0.0

    def start(self) -> bool:
        """Nichts zu starten. False heisst "kein Weckwort" -- main.py
        wertet das aus und sagt es beim Hochfahren."""
        return False

    def stopp(self) -> None:
        pass

    def pause(self, an: bool = True) -> None:
        self.pausiert = bool(an)

    def spricht(self, text: str | None = None) -> None:
        """Was Sarvis gerade selbst sagt.

        Wird mitgefuehrt, damit der Echo-Gedanke traegt, sobald ein
        Client seinen Mikrofonstrom schickt: Was er von sich selbst
        hoert, ist kein Zuruf.
        """
        self._spricht_gerade = text

    def nachhoeren(self, sekunden: float = 0.0) -> None:
        """Das Fenster, in dem kein Weckwort noetig waere."""
        if sekunden > 0:
            self._nachhoeren_bis = time.monotonic() + sekunden

    def hoert_nach(self, seit: float = 0.0) -> bool:
        return time.monotonic() < self._nachhoeren_bis
