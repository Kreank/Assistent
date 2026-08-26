"""Mund: Text zu Sprache, lokal auf der CPU."""
import logging
import re
import time

import numpy as np
from piper import PiperVoice, SynthesisConfig

from . import config
from . import stimmfarbe

# Satzende: Punkt/Frage/Ruf/Doppelpunkt, gefolgt von Leerzeichen oder Ende.
#
# Der zweite Fall ist wichtiger, als er aussieht: Wenn Sarvis erst
# "Moment, ich schau nach." sagt und dann das Ergebnis anhaengt, kommt aus
# dem Strom "nach.Auf D liegen..." -- ohne Leerzeichen. Ohne diese Regel
# waere beides EIN Satz, wuerde zusammen gesprochen, und der ganze Sinn
# des Einleitungssatzes waere dahin.
_SATZENDE = re.compile(r"(?<=[.!?:;])\s+|(?<=[.!?])(?=[A-ZÄÖÜ])|\n+")


class Mund:
    def __init__(self):
        if not config.STIMME.exists():
            raise FileNotFoundError(
                f"Stimme fehlt: {config.STIMME}\n"
                "Nachladen mit: python -m sarvis.hole_stimme"
            )
        print(f"  Piper laedt ({config.STIMME.name}) ...")
        # Piper meldet beim Laden fehlende Randzeichen im Phonem-Verzeichnis
        # ("Missing phoneme from id map: ̧"). Das ist folgenlos, sieht
        # in der Konsole aber wie ein Fehler aus.
        logging.getLogger("piper").setLevel(logging.ERROR)
        t = time.perf_counter()
        self.stimme = PiperVoice.load(config.STIMME)
        # Tonhoehe wird nicht im Nachhinein verschoben, sondern hier
        # vorkompensiert: Piper spricht entsprechend schneller, das
        # Neuabtasten danach zieht es wieder gerade. Ein Phasenvocoder
        # wuerde die Zischlaute verwaschen, und genau die traegt eine
        # Assistentenstimme.
        self.farbe = getattr(config, "STIMMFARBE", "aus")
        tempo = config.TEMPO * stimmfarbe.tonhoehe_faktor(self.farbe)
        self.einstellung = SynthesisConfig(
            length_scale=tempo,
            noise_scale=getattr(config, "BETONUNG", None),
            noise_w_scale=getattr(config, "RHYTHMUS", None),
        )
        if getattr(config, "STIMME_SPRECHER", None) is not None:
            self.einstellung.speaker_id = config.STIMME_SPRECHER
        sprecher = ("" if config.STIMME_SPRECHER is None
                    else f", Sprecher {config.STIMME_SPRECHER}")
        farbe = "" if self.farbe == "aus" else f", Farbe {self.farbe}"
        print(f"  Piper bereit nach {time.perf_counter() - t:.1f}s "
              f"(Tempo {config.TEMPO}{sprecher}{farbe})")

    def sprechen(self, text: str) -> tuple[np.ndarray, int]:
        """Ein Stueck Text zu Audio. Gibt (Proben, Abtastrate) zurueck."""
        teile, rate = [], config.ABTASTRATE
        for brocken in self.stimme.synthesize(text, syn_config=self.einstellung):
            teile.append(brocken.audio_float_array)
            rate = brocken.sample_rate
        if not teile:
            return np.zeros(0, dtype="float32"), rate
        return stimmfarbe.faerben(np.concatenate(teile), rate, self.farbe)

    def aufwaermen(self) -> None:
        self.sprechen("Bereit.")


class Satzsammler:
    """Sammelt Text-Schnipsel und gibt sie satzweise heraus.

    Ohne das wartet man auf die ganze Antwort, bevor der erste Ton kommt --
    und genau daran fuehlt sich so ein Assistent langsam an.
    """

    def __init__(self, mindestlaenge: int = 25):
        self.puffer = ""
        self.mindestlaenge = mindestlaenge
        # Der ERSTE Satz einer Antwort geht ohne Mindestlaenge heraus.
        #
        # Er ist der einzige, bei dem es auf jede Zehntelsekunde ankommt,
        # und er ist typischerweise genau der kurze Einleitungssatz, der
        # die Wartezeit ueberbruecken soll. "Moment, ich schaue nach."
        # hat 24 Zeichen -- eines zu wenig -- und waere zusammen mit dem
        # Ergebnis gesprochen worden. Damit haette der Wartesatz eine
        # Pause behauptet, die schon vorbei ist.
        #
        # Fuer alles Weitere bleibt die Mindestlaenge: Mitten in einer
        # Antwort zerhackt jedes "Ja." als eigener Atemzug die Stimme.
        self._erster = True

    def dazu(self, schnipsel: str) -> list[str]:
        self.puffer += schnipsel
        fertig = []
        while True:
            # Erste Satzgrenze, die weit genug hinten liegt. Zu kurze
            # Bruchstuecke ("Ja.") einzeln vorzulesen zerhackt die Stimme,
            # also warten wir, bis genug Text fuer einen Atemzug da ist.
            # Eine Grenze ohne Leerzeichen ("nach.Auf") entsteht nur, wenn
            # zwei fertige Saetze aneinanderstossen -- typisch fuer den
            # Einleitungssatz vor einem Werkzeugaufruf. Der ist kurz, und
            # genau deshalb darf die Mindestlaenge hier nicht greifen:
            # sonst wird er mit dem Ergebnis zusammen gesprochen und die
            # ganze Ueberbrueckung ist dahin.
            schwelle = 0 if self._erster else self.mindestlaenge
            grenze = next(
                (t for t in _SATZENDE.finditer(self.puffer)
                 if t.start() >= schwelle or t.start() == t.end()),
                None,
            )
            if grenze is None:
                break
            satz = self.puffer[: grenze.start()].strip()
            self.puffer = self.puffer[grenze.end():]
            if satz:
                fertig.append(satz)
                self._erster = False
        return fertig

    def rest(self) -> str:
        uebrig = self.puffer.strip()
        self.puffer = ""
        return uebrig


def tageszeit(stunde: int) -> str:
    if 5 <= stunde < 11:
        return "Guten Morgen"
    if 11 <= stunde < 18:
        return "Guten Tag"
    if 18 <= stunde < 23:
        return "Guten Abend"
    return "Gute Nacht"


def taste_aussprechen(name: str) -> str:
    """'f10' spricht Piper als 'eff zehn' -- so wird ein Wort daraus."""
    besonders = {
        "alt_l": "die linke Alt-Taste", "alt_r": "die rechte Alt-Taste",
        "ctrl_l": "die linke Steuerungstaste", "ctrl_r": "die rechte Steuerungstaste",
        "shift_l": "die linke Umschalttaste", "shift_r": "die rechte Umschalttaste",
        "space": "die Leertaste", "pause": "die Pause-Taste",
        "scroll_lock": "die Rollen-Taste",
    }
    name = name.strip().lower()
    if name in besonders:
        return besonders[name]
    if name.startswith("f") and name[1:].isdigit():
        return f"F {name[1:]}"
    return f"die Taste {name.upper()}"
