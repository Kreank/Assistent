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
        if self._stille >= config.WECKWORT_STILLE_SEK:
            self._pruefen()

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
