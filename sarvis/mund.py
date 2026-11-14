"""Mund: Text zu Sprache, lokal auf der CPU."""
import logging
import re
import time

import numpy as np
from piper import PiperVoice, SynthesisConfig

from . import aussprache
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
        # Eine unbekannte Farbe wirkt als "aus" -- dann darf die Startzeile
        # sie nicht bestaetigen (Fund 032, zweite Haelfte).
        if self.farbe == "aus":
            farbe = ""
        elif self.farbe in stimmfarbe.FARBEN:
            farbe = f", Farbe {self.farbe}"
        else:
            farbe = f", Farbe {self.farbe} unbekannt -- wirkt als 'aus'"
        print(f"  Piper bereit nach {time.perf_counter() - t:.1f}s "
              f"(Tempo {config.TEMPO}{sprecher}{farbe})")

        # Die schoenere Stimme, wenn sie eingeschaltet ist. Piper wird
        # TROTZDEM geladen und bleibt geladen: Er ist der Rueckfall, und
        # ein Rueckfall, den man erst holen muesste, wenn er gebraucht
        # wird, ist keiner -- dann steht die Antwort still, waehrend ein
        # Modell von der Platte kommt.
        self.eleven = None
        if getattr(config, "STIMME_DIENST", "piper") == "elevenlabs":
            from .eleven import Eleven
            self.eleven = Eleven()
            print(f"  {self.eleven.stand_satz()}")

        # Pocket TTS (seit 14.11.2026, siehe pocket.py). Laedt es nicht --
        # Paket fehlt, Modell nicht holbar --, spricht Sarvis mit Piper
        # weiter, statt gar nicht zu starten.
        self.pocket = None
        if getattr(config, "STIMME_DIENST", "piper") == "pocket":
            try:
                from .pocket import Pocket
                self.pocket = Pocket()
            except Exception as e:
                print(f"  Pocket TTS nicht verfuegbar ({e!r}) -- Piper spricht")

    def sprechen(self, text: str) -> tuple[np.ndarray, int]:
        """Ein Stueck Text zu Audio. Gibt (Proben, Abtastrate) zurueck.

        Der Rueckfall ist hier eine einzige Zeile, und das ist Absicht:
        eleven.sprechen() gibt None fuer JEDEN Grund -- kein Netz, leeres
        Kontingent, Schluessel ohne Berechtigung, Ton nicht lesbar. Der
        Aufrufer muss keinen Fall unterscheiden, und es gibt keinen Pfad,
        auf dem am Ende gar nichts gesprochen wird.
        """
        # Links und Pfade nie vorlesen (Sascha, 13.11.2026) -- gilt fuer
        # beide Stimmen, der Bildschirmtext bleibt unberuehrt.
        text = aussprache.ohne_links(text)
        if not text:
            return np.zeros(0, dtype="float32"), config.ABTASTRATE
        if self.pocket is not None:
            teile, rate = [], config.ABTASTRATE
            for proben, rate, _ in self.sprechen_strom(text):
                teile.append(proben)
            if teile:
                return np.concatenate(teile), rate
            return np.zeros(0, dtype="float32"), rate
        if self.eleven is not None:
            fertig = self.eleven.sprechen(text)
            if fertig is not None:
                # Keine Stimmfarbe drueber. Der ganze Zweck dieser Stimme
                # ist, wie sie ist; ein Filter darauf waere, als male man
                # ueber ein Foto.
                return fertig

        # Erst hier, nicht vor ElevenLabs: Piper phonemisiert ueber
        # espeak-ng und liest Zahlen, Geld, Datum und Uhrzeit falsch
        # vor -- siehe aussprache.py. ElevenLabs kann das selbst.
        text = aussprache.vorlesbar(text)

        teile, rate = [], config.ABTASTRATE
        for brocken in self.stimme.synthesize(text, syn_config=self.einstellung):
            teile.append(brocken.audio_float_array)
            rate = brocken.sample_rate
        if not teile:
            return np.zeros(0, dtype="float32"), rate
        return stimmfarbe.faerben(np.concatenate(teile), rate, self.farbe)

    def sprechen_strom(self, text: str):
        """Wie sprechen(), aber in Stuecken: (proben, rate, letztes).

        Nur Pocket liefert wirklich mehrere Stuecke -- es rechnet knapp
        schneller als Echtzeit, und einen ganzen Satz abzuwarten hiesse
        sekundenlange Stille vor dem ersten Ton. Piper und ElevenLabs
        geben EIN Stueck. Bricht Pocket vor dem ersten Stueck ab, spricht
        Piper den Satz; bricht es mittendrin ab, endet der Satz dort --
        ihn doppelt zu hoeren waere schlimmer.

        Bei Pocket ist das letzte Stueck LEER (letztes=True, 0 Proben):
        Jedes Stueck geht sofort hinaus, ohne auf das naechste zu warten
        -- ob es das letzte war, weiss man erst hinterher. Der Aufrufer
        haengt dann nur noch den Ausklang an.
        """
        if self.pocket is None:
            proben, rate = self.sprechen(text)
            yield proben, rate, True
            return
        text = aussprache.ohne_links(text)
        if not text:
            return
        text = aussprache.alles_ausschreiben(text)
        rate = self.pocket.rate
        schon = False
        try:
            for stueck in self.pocket.strom(text):
                schon = True
                yield stueck, rate, False
        except Exception as e:
            print(f"  (Pocket TTS fehlgeschlagen: {e!r})")
            if not schon:
                # Ohne Pocket: der alte Weg ueber Piper.
                pocket, self.pocket = self.pocket, None
                try:
                    proben, rate = self.sprechen(text)
                finally:
                    self.pocket = pocket
                yield proben, rate, True
                return
        yield np.zeros(0, dtype="float32"), rate, True

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
