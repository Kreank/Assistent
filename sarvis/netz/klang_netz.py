"""Sarvis' Stimme ueber Netz -- er spricht, wo jemand zuhoert.

Erfuellt klang.Lautsprecher, schickt aber keine Samples an ein Geraet,
sondern eine Meldung an jede verbundene Oberflaeche. Der Browser haengt
sie an seine Wiedergabe an.

EINEN AUFNEHMER GIBT ES HIER NICHT, UND DAS IST ABSICHT

Push-to-talk ist ueber Netz umgedreht. Lokal sagt die Schleife "jetzt
aufnehmen" und holt sich hinterher das Ergebnis; ueber Netz entscheidet
das GERAET, wann es aufnimmt -- der Daumen liegt dort, nicht hier. Der
Server bekommt eine fertige Aufnahme geschickt und verarbeitet sie.

Das ist kein Verlust, sondern der bessere Schnitt: Es spart die
Rundreise vor dem ersten Wort. Wuerde die Schleife "start" rufen und auf
Antwort warten, ginge genau die Zeit verloren, in der schon geredet wird
-- der Anfang des ersten Wortes.

Die Aufnahme kommt deshalb ueber server.Endpunkt.sprache_an herein und
nicht ueber einen Aufnehmer. Aufnehmer bleibt trotzdem im Vertrag: Die
Schleife braucht ihn fuer den lokalen Fall, und ein Vertrag, der je nach
Betriebsart anders aussieht, ist keiner.

WAS ALS TON HINAUSGEHT

    {art: "ton", daten: base64-int16, rate: 22050, runde: n}

int16 statt float32, weil es halb so gross ist und fuer Sprache
verlustfrei genug. Die RUNDE geht mit, und der Client verwirft, was
aelter ist als seine aktuelle -- ohne das kommt der Fehler zurueck,
gegen den der Rundenzaehler gebaut wurde, nur um eine Netzlaufzeit
versetzt: Ein Satz, der beim Abbruch schon unterwegs war, spielt nach
dem "Gestoppt.".
"""
import base64
import threading
import time

import numpy as np

from ..klang import AUSKLANG


class NetzLautsprecher:
    """klang.Lautsprecher, aber die Ohren sind woanders."""

    def __init__(self, traeger, melden=None):
        self.traeger = traeger
        self.melden = melden
        # Wem die Antwort gilt. Wird vor jedem Durchgang gesetzt; None
        # heisst "an alle" -- etwa bei einem Timer, der sich von selbst
        # meldet und niemanden bestimmtes meint.
        self.ziel: str | None = None
        self._runde = 0
        self._schloss = threading.Lock()
        # Wie viele Sekunden Ton unterwegs bzw. eingeplant sind. Daran
        # haengt warten(): Der Server weiss nicht, wann der Client fertig
        # gespielt hat, aber er weiss, wie lang das Gesagte war.
        self._bis = 0.0
        # Wann der zuletzt eingereihte Ton beim Client verklungen sein
        # muesste (monotone Uhr). Der Client haengt nahtlos an -- ein Block
        # beginnt also erst, wenn der vorige zu Ende ist.
        self._ende = 0.0
        self._leer = threading.Event()
        self._leer.set()

    # --- Vertrag ---------------------------------------------------------

    def sagen(self, proben: np.ndarray, rate: int,
              ausklang: bool = True) -> None:
        if proben is None or not len(proben):
            return
        # AUSKLANG anhaengen -- Sache der Umsetzung, nicht des Aufrufers.
        # Lokal umging er ein PortAudio-Verhalten; im Browser ist er der
        # Puffer zwischen zwei angehaengten Bloecken, damit die letzte
        # Silbe nicht am naechsten Satz haengenbleibt.
        stille = np.zeros(int(rate * AUSKLANG) if ausklang else 0,
                          dtype="float32")
        ganz = np.concatenate([np.asarray(proben, dtype="float32"), stille])
        klein = np.clip(ganz * 32768.0, -32768, 32767).astype("<i2")

        with self._schloss:
            runde = self._runde
            self._bis += len(ganz) / rate
            jetzt = time.monotonic()
            self._ende = max(self._ende, jetzt) + len(ganz) / rate
            restzeit = self._ende - jetzt
            mein_ende = self._ende
            self._leer.clear()
        self.traeger.senden_gezielt(self.ziel, {
            "art": "ton",
            "daten": base64.b64encode(klein.tobytes()).decode("ascii"),
            "rate": int(rate),
            "runde": runde,
        })
        # Der Pegel fuer den Ring wird hier NICHT gemeldet. Der Client
        # kennt die Huellkurve seines eigenen Tons genauer als wir --
        # und er weiss vor allem, wann er wirklich spielt.
        # Der Wecker zielt auf das Ende ALLES Eingereihten, nicht nur
        # dieses Blocks: Seit Pocket TTS kommt ein Satz in mehreren
        # Stuecken, und der Wecker des ersten durfte nicht "fertig"
        # melden, waehrend die naechsten noch spielen. Nur der Wecker,
        # dessen Ziel noch das aktuelle Ende ist, meldet leer.
        threading.Timer(restzeit, self._vielleicht_leer,
                        args=(runde, mein_ende)).start()

    def _vielleicht_leer(self, runde: int, ende: float | None = None) -> None:
        with self._schloss:
            if runde != self._runde:
                return          # abgebrochen, jemand anders raeumt auf
            if ende is not None and ende != self._ende:
                return          # danach kam noch Ton -- dessen Wecker meldet
            self._bis = max(0.0, self._bis - 0.0)
            self._leer.set()

    def abbrechen(self) -> int:
        """Blockiert nie -- wird aus drei Faeden gerufen."""
        with self._schloss:
            self._runde += 1
            self._bis = 0.0
            self._ende = 0.0
            self._leer.set()
            runde = self._runde
        # Das Stoppen geht an ALLE. Wenn ein anderes Geraet noch einen
        # alten Satz spielt, soll auch das aufhoeren -- sonst redet
        # Sarvis an zwei Stellen weiter, obwohl er unterbrochen wurde.
        self.traeger.senden({"art": "ton_stopp", "runde": runde})
        if self.melden is not None:
            self.melden(0.0)
        return runde

    def warten(self, frist: float | None = None) -> bool:
        """Wartet, bis das Gesagte verklungen sein MUESSTE.

        "Muesste", nicht "ist": Eine echte Rueckmeldung des Clients waere
        genauer, aber sie kann ausbleiben -- Verbindung weg, Seite
        geschlossen, Handy in der Tasche. Dann haenge die Schleife fuer
        immer, und Sarvis naehme keinen Zuruf mehr an.

        Also die Laenge des Gesagten plus eine Zugabe fuer den Weg. Zu
        frueh zurueckzukehren kostet einen falschen Anzeigezustand; zu
        spaet kostet das ganze Gespraech.
        """
        return self._leer.wait(timeout=frist)

    @property
    def runde(self) -> int:
        return self._runde

    def pegel_an(self, melden) -> None:
        self.melden = melden
