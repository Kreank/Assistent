"""Weckwort: dauerhaft mithören, bei "Hey Sarvis" aufwachen.

Warum nicht openWakeWord: Dessen Fertigmodelle sind auf englische
Aussprache trainiert. Gemessen: "Hey Sarvis" von unserer deutschen Stimme
erreichte 0,09 bis 0,13 -- selbst "Hey Jarvis" nur 0,45. Unbrauchbar.

Stattdessen die Kette, die ohnehin läuft:

  Silero-VAD (CPU, billig)  entscheidet, ob überhaupt jemand redet
        ↓ nur dann
  Whisper (3080er GPU)      versteht, WAS gesagt wurde
        ↓
  Anfang = Weckwort?        dann ist der Rest schon der Zuruf

Der letzte Punkt ist der eigentliche Gewinn: "Hey Sarvis, wie spät ist
es?" ist EIN Satz. Kein Aufwachen, Piepen, nochmal sprechen -- man redet
einfach.

Solange niemand spricht, rechnet nur der VAD. Whisper rührt sich nicht.
"""
import re
import threading
import time
from difflib import SequenceMatcher

import numpy as np
import sounddevice as sd

from . import config, rueckfrage

# Silero rechnet in Rahmen von 480 Abtastwerten (30 ms bei 16 kHz).
# Eine andere Blockgroesse laesst einen Rest uebrig, der die Vorhersage
# verfaelscht.
BLOCK = 480
RATE = 16000


def _sauber(text: str) -> str:
    return re.sub(r"[^\wäöüß ]+", " ", (text or "").lower()).strip()


def _worte(text: str) -> set:
    """Die Woerter eines Satzes, kleingeschrieben und ohne Satzzeichen.

    Fuer den Vergleich "sagt er das gerade selbst?" -- siehe _eigen_echo.
    """
    roh = (text or "").lower().split()
    return {w.strip(".,!?;:-–„“»«'\"") for w in roh} - {""}


# Was Whisper aus Stille und Rauschen macht. Keine Vermutung: Diese
# Saetze stehen in den Trainingsdaten als Video-Abspann und kommen bei
# leisem Nichts zuverlaessig zurueck. Im Betrieb gehoert: "We'll see you
# next time. Bye-bye. Bye-bye." -- und das ging als Zuruf weiter.
#
# Bewusst nur Unverwechselbares. "Vielen Dank" steht NICHT hier: Das
# sagt man wirklich, und ein verschlucktes Danke ist schlimmer als eine
# gelegentliche Halluzination.
_HALLUZINATIONEN = (
    "bye-bye", "bye bye", "thank you for watching", "thanks for watching",
    "see you next time", "untertitel", "untertitelung", "amara.org",
    "subtitles by", "subs by", "ondertiteling", "good night", "goodbye",
    "good bye",
)

# Woerter, die man WIRKLICH mehrfach hintereinander sagt. Ohne diese
# Ausnahme wuerde ein nachdruecklich gemeintes "ja, ja, ja" als
# Halluzination verworfen -- und ausgerechnet die Bestaetigung, die man
# zweimal geben musste, verschwaende.
_ECHTE_WIEDERHOLUNG = {
    "ja", "nein", "ok", "okay", "stopp", "stop", "halt", "warte",
    "genau", "danke", "hallo", "sarvis", "nee", "doch",
}


def _dreht_sich_im_kreis(text: str) -> bool:
    """Dasselbe Wort dreimal hintereinander -- Whisper haengt fest.

    Beobachtet: "Heissler, Heissler, Heissler" und "Baitchen, Baitchen
    Baitchen", beide aus Stille. Das ist kein Verhoeren, sondern ein
    bekanntes Verhalten des Modells: Es faengt an zu wiederholen und
    kommt nicht mehr heraus. Eine Liste einzelner Saetze kann das nicht
    abfangen -- das Muster schon.
    """
    worte = [w for w in re.split(r"[\s,.!?;:-]+", (text or "").lower()) if w]
    if len(worte) < 3:
        return False
    for i in range(len(worte) - 2):
        if worte[i] == worte[i + 1] == worte[i + 2]:
            return worte[i] not in _ECHTE_WIEDERHOLUNG
    return False


def _halluziniert(text: str) -> bool:
    t = " ".join((text or "").lower().split())
    return any(m in t for m in _HALLUZINATIONEN)


def _klingt_wie_name(wort: str) -> bool:
    """Ist dieses eine Wort der Name? Whisper verhoert ihn gern."""
    return SequenceMatcher(None, wort, config.NAME).ratio() \
        >= config.WECKWORT_AEHNLICHKEIT


def erkennen(text: str) -> str | None:
    """Faengt der Satz mit dem Weckwort an? Dann kommt der Rest zurueck.

    Entscheidend ist die POSITION, nicht die Aehnlichkeit ganzer Wort-
    folgen. Ein unscharfer Vergleich ueber mehrere Woerter weckte sonst
    bei "Der Sarvis laeuft ganz gut" -- und verschluckte umgekehrt bei
    "Hey Sarvis, wie spaet ist es" das "wie", weil auch drei Woerter noch
    aehnlich genug aussahen. Beides gemessen, beides behoben.

    Erlaubt ist deshalb genau zweierlei:
        <Name> ...                z. B. "Sarvis, Licht aus"
        <Anrede> <Name> ...       z. B. "Hey Sarvis, wie spaet ist es"
    """
    worte = _sauber(text).split()
    if not worte:
        return None

    if _klingt_wie_name(worte[0]):
        return " ".join(worte[1:]).strip()

    # Anrede und Name kleben oft zusammen: Whisper macht aus "Hey Sarvis"
    # gern "HiService" oder "HeySarvis". Gemessen, kein Einzelfall.
    # Deshalb die Anrede abschneiden und den Rest pruefen.
    for anrede in config.ANREDEN:
        if worte[0].startswith(anrede) and len(worte[0]) > len(anrede) + 2:
            if _klingt_wie_name(worte[0][len(anrede):]):
                return " ".join(worte[1:]).strip()

    if len(worte) >= 2 and worte[0] in config.ANREDEN \
            and _klingt_wie_name(worte[1]):
        return " ".join(worte[2:]).strip()

    return None


class Horcher:
    """Hoert im Hintergrund mit und meldet, wenn das Weckwort faellt."""

    def __init__(self, ohren, wecken, anzeige=None):
        """wecken(zuruf: str) -- wird gerufen, wenn das Weckwort fiel."""
        self.ohren = ohren
        self.wecken = wecken
        self.anzeige = anzeige
        self.vad = None
        self._strom = None
        self._faden = None
        self._laeuft = False
        self.pausiert = False     # waehrend Sarvis redet oder arbeitet
        # Was er gerade sagt -- die letzten Saetze, nicht nur der neueste:
        # Die Synthese laeuft dem Ton voraus, waehrend Satz 1 noch klingt,
        # ist Satz 3 schon gebaut. Ein Filter, der nur den neuesten kennt,
        # vergliche gegen etwas, das noch gar nicht zu hoeren war.
        self._eigene_saetze: list = []
        self._puffer: list[np.ndarray] = []
        self._redet = False
        self._stille = 0.0
        self._begonnen = 0.0
        self._nachhoeren_bis = 0.0   # bis wann ohne Weckwort

    # --- Steuerung ---------------------------------------------------------

    def start(self) -> bool:
        if not config.WECKWORT_AN:
            return False
        try:
            from openwakeword.vad import VAD
            self.vad = VAD()
        except Exception as e:
            print(f"  (Weckwort aus: VAD ließ sich nicht laden — {e})")
            return False

        self._laeuft = True
        self._faden = threading.Thread(target=self._schleife, daemon=True)
        self._faden.start()
        return True

    def stopp(self) -> None:
        self._laeuft = False

    def spricht(self, text: str | None) -> None:
        """Sarvis redet gerade diesen Satz -- oder ist fertig (None).

        Ohne REINREDEN ist das schlicht pause(): Ohr zu, solange er redet.
        Mit REINREDEN bleibt es offen, damit man ihn unterbrechen kann.
        """
        if not config.REINREDEN:
            self.pause(text is not None)
            return
        if text is None:
            self._eigene_saetze = []
            self.pause(False)
            return
        self._eigene_saetze.append(_worte(text))
        del self._eigene_saetze[:-3]
        # Waehrend er redet, zaehlt jeder Satz als Antwort. Mitten in
        # seinen Satz hinein "Hey Sarvis" zu rufen waere albern -- man
        # faellt jemandem ins Wort, man meldet sich nicht an.
        self._nachhoeren_bis = max(
            self._nachhoeren_bis,
            time.perf_counter() + config.NACHHOEREN_SEK,
        )
        if self.pausiert:
            self.pausiert = False
            self._verwerfen()

    def _eigen_echo(self, text: str) -> bool:
        """Kommt da seine eigene Stimme durchs Mikrofon zurueck?

        Mit Kopfhoerern ist das wenig, aber nicht nichts. Was zurueck-
        kommt, sind seine eigenen Worte -- und die kennen wir genau: es
        ist der Satz, den er in diesem Moment sagt.

        Kurzes bleibt ungeprueft. Sonst verschluckt der Filter ein "nein",
        das zufaellig auch in seinem Satz vorkommt -- und ausgerechnet das
        kurze Dazwischenrufen ist der Fall, um den es hier geht.
        """
        if not self._eigene_saetze:
            return False
        w = _worte(text)
        if len(w) < 3:
            return False
        eigen = set().union(*self._eigene_saetze)
        if len(w & eigen) / len(w) >= 0.7:
            print(f"  (eigene Stimme verworfen: {text!r})")
            return True
        return False

    def pause(self, an: bool) -> None:
        """Waehrend Sarvis spricht, hoert er nicht auf sich selbst.

        Ohne das weckt ihn seine eigene Stimme aus dem Lautsprecher --
        bei Kopfhoerern egal, bei Boxen eine Endlosschleife.
        """
        self.pausiert = an
        if an:
            self._verwerfen()

    # --- Ablauf -------------------------------------------------------------

    def _verwerfen(self):
        self._puffer = []
        self._redet = False
        self._stille = 0.0
        # Silero ist ein Netz mit Gedaechtnis. Ohne Ruecksetzen bleibt es
        # nach einem laengeren Abschnitt auf "Sprache" haengen und meldet
        # 0.91, obwohl der Pegel bei null liegt -- gemessen. Der Abschnitt
        # endet dann nie, und Whisper laeuft erst nach der Notbremse.
        if self.vad is not None:
            try:
                self.vad.reset_states()
            except Exception:
                pass

    def _schleife(self):
        try:
            with sd.InputStream(samplerate=RATE, channels=1, dtype="float32",
                                blocksize=BLOCK) as strom:
                self._strom = strom
                while self._laeuft:
                    block, _ = strom.read(BLOCK)
                    if self.pausiert:
                        continue
                    self._block(block[:, 0].copy())
        except Exception as e:
            print(f"  (Weckwort-Horcher beendet: {e})")

    def _block(self, block: np.ndarray) -> None:
        jetzt = time.perf_counter()
        try:
            # Silero will 16-Bit-PCM: predict() teilt intern durch 32767.
            # Mit Fliesskomma-Werten aus sounddevice kommt dabei praktisch
            # null heraus -- der VAD haette nie Sprache gesehen. Genau
            # dieser Fehler liess den Horcher stumm bleiben.
            pcm = (np.clip(block, -1.0, 1.0) * 32767).astype(np.int16)
            wahrscheinlich = float(self.vad.predict(pcm, frame_size=BLOCK))
        except Exception:
            return

        # Zweite Meinung: der Pegel. Der VAD allein meldete 0.91 bei
        # leerem Pegelbalken -- wer nichts hoert, redet auch nicht.
        pegel = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
        spricht = (wahrscheinlich >= config.VAD_SCHWELLE
                   and pegel >= config.WECKWORT_MIN_PEGEL)

        if spricht:
            if not self._redet:
                self._redet = True
                self._begonnen = jetzt
            self._stille = 0.0
            self._puffer.append(block)
            # Notbremse: wer minutenlang redet, meint nicht uns.
            if jetzt - self._begonnen > config.WECKWORT_MAX_SEK:
                self._pruefen()
            return

        if not self._redet:
            return

        # Nachlauf: kurze Pausen im Satz sind keine Satzenden.
        self._puffer.append(block)
        self._stille += BLOCK / RATE
        if self._stille >= self._stille_grenze():
            self._pruefen()

    def _stille_grenze(self) -> float:
        """Wie lange Stille diesen Satz beendet -- je nachdem, wie lange
        schon gesprochen wird.

        "Wie spaet ist es" ist nach einer halben Sekunde Stille fertig.
        Wer seit fuenf Sekunden einen Gedanken ausformuliert, macht
        dazwischen Pausen -- und wurde bisher jedes Mal unterbrochen.
        """
        gesprochen = sum(len(b) for b in self._puffer) / RATE
        if gesprochen >= config.WECKWORT_LANG_AB_SEK:
            return config.WECKWORT_STILLE_LANG_SEK
        return config.WECKWORT_STILLE_SEK

    def _pruefen(self) -> None:
        stueck = self._puffer
        dauer = sum(len(b) for b in stueck) / RATE
        self._verwerfen()
        if dauer < config.WECKWORT_MIN_SEK:
            return

        audio = np.concatenate(stueck)
        try:
            # Der Name als Hinweis -- hier zaehlt er am meisten.
            text = self.ohren.hoeren(
                audio, hinweise=f"Hey {config.NAME.capitalize()}"
            )
        except Exception as e:
            print(f"  (Weckwort: Whisper stolperte — {e})")
            return
        if not text:
            return
        if _halluziniert(text) or _dreht_sich_im_kreis(text):
            print(f"  (Whisper-Halluzination verworfen: {text!r})")
            return
        if self._eigen_echo(text):
            return

        zuruf = erkennen(text)
        wie = "Weckwort"

        if zuruf is None:
            # Hat Sarvis gerade geantwortet, ist der naechste Satz die
            # Fortsetzung -- dann waere ein erneutes "Hey Sarvis" albern.
            # Er fragt ja selbst, wie er dienen kann; die Antwort darauf
            # zu verwerfen war der Fehler.
            if not self.hoert_nach():
                return
            # Im Nachhoerfenster genuegt jeder Satz -- deshalb hier eine
            # Mindestlaenge. Ein einzelnes "Ähm" oder ein Rascheln soll
            # keinen Auftrag ausloesen, wenn kein Weckwort davorsteht.
            # ACHTUNG: Diese Pruefung gehoert NUR hierhin. Stand sie weiter
            # unten fuer beide Faelle, verschluckte sie das blosse
            # "Hey Sarvis" -- denn dessen Rest ist leer, und leer ist
            # nicht dasselbe wie nichts.
            # Ein einzelnes Wort waere sonst zu wenig -- ausser es ist
            # genau die Antwort auf eine Rueckfrage. "Ja." hat ein Wort,
            # und mehr sagt man da auch nicht.
            if (len(text.split()) < 2
                    and rueckfrage.deuten(text) == rueckfrage.UNKLAR):
                return
            zuruf = text.strip()
            wie = "Nachhören"

        self._nachhoeren_bis = 0.0
        print(f"\n  * {wie}: {text!r}")
        self.pausiert = True     # bis der Durchgang durch ist
        self.wecken(zuruf)

    # --- Nachhoeren ---------------------------------------------------------

    def nachhoeren(self, sekunden: float | None = None) -> None:
        """Kurzes Fenster, in dem kein Weckwort noetig ist."""
        if not self._laeuft:
            return
        self._nachhoeren_bis = time.perf_counter() + (
            config.NACHHOEREN_SEK if sekunden is None else sekunden
        )

    def hoert_nach(self) -> bool:
        return time.perf_counter() < self._nachhoeren_bis
