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
import queue
import re
import threading
import time
from difflib import SequenceMatcher

import numpy as np

from . import audio, config, rueckfrage
from .anzeige import DENKT, FRAGT, RUHIG

# Silero rechnet in Rahmen von 480 Abtastwerten (30 ms bei 16 kHz).
# Eine andere Blockgroesse laesst einen Rest uebrig, der die Vorhersage
# verfaelscht.
BLOCK = 480
RATE = 16000
# Wie viele ungelesene Bloecke sich hoechstens stauen duerfen, bevor
# Aeltestes wegfaellt: 200 * 30 ms = 6 Sekunden. Der Rueckstand entsteht
# durch Whisper und ist gemessen rund 0,13 s -- der Deckel ist reine
# Vorsorge gegen einen Faden, der wirklich haengt. Ohne ihn waechst die
# Schlange still weiter, und der Horcher hoert immer weiter in der
# Vergangenheit zu, ohne dass jemand es merkt.
MAX_RUECKSTAND = 200

# Wie oft eine Stoermeldung hoechstens wiederholt wird. Einmalig waere zu
# wenig: Faellt der VAD dauerhaft aus, hoert der Horcher auf zu reagieren,
# ohne abzustuerzen -- und eine einzelne Zeile von vor einer Stunde findet
# niemand mehr. Jeden Block zu melden waere 33-mal je Sekunde.
MECKER_PAUSE = 30.0


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


# Woerter, mit denen ein deutscher Satz praktisch nie ENDET. Bewusst
# ohne die abtrennbaren Vorsilben (an, auf, aus, mit, zu, ab ...) --
# "Mach das Licht an" und "Hoer auf" sind fertig. Ebenso ohne das/die/der
# ("Was ist das") und ohne Pronomen ("Was ist mit ihm").
_HAENGT_NOCH = {
    "und", "oder", "aber", "also", "sondern", "denn", "dass", "weil",
    "wenn", "ob", "falls", "damit", "obwohl", "bevor", "nachdem", "sowie",
    "der", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer", "eines",
    "ne", "nen", "mein", "meine", "meinen", "meinem", "meiner",
    "dein", "deine", "deinen", "deinem", "deiner", "unser", "unsere",
    "von", "vom", "zum", "zur", "im", "beim", "für", "über", "unter",
    "zwischen", "gegen", "ohne", "wegen", "seit", "bis", "als", "wie",
    "möchte", "möchten", "will", "würde", "würdest", "soll", "sollst",
    "muss", "müsste", "kann", "könnte", "könntest", "wollte",
    "äh", "ähm", "öhm", "hm", "zwar", "sozusagen", "quasi",
}


def _klingt_unfertig(text: str) -> bool:
    """Hoert sich das an wie ein Satz, der noch weitergeht?

    Nur am Ende ablesbar, und nur in die sichere Richtung: Lieber einmal
    einen fertigen Satz drei Sekunden halten als einen halben losschicken.
    Ein Satzzeichen am Ende (. ? !) gilt als fertig -- Whisper setzt es
    bei abgebrochener Rede meist nicht.
    """
    t = (text or "").strip()
    if not t:
        return False
    if t.endswith(("...", "…", ":", ",", " -", "–")):
        return True
    if t[-1] in ".?!":
        return False
    letztes = t.split()[-1].strip("\"'„“»«").lower()
    return letztes in _HAENGT_NOCH


def _klingt_wie_name(wort: str, schwelle: float | None = None) -> bool:
    """Ist dieses eine Wort der Name? Whisper verhoert ihn gern.

    schwelle nur fuer den Klebefall unten -- siehe config.
    """
    if schwelle is None:
        schwelle = config.WECKWORT_AEHNLICHKEIT
    return SequenceMatcher(None, wort, config.NAME).ratio() >= schwelle


def _mitten_drin(worte: list) -> str | None:
    """Anrede und Name IRGENDWO im Text -- nur fuer gekappte Laermstuecke.

    Normalerweise gilt: Das Weckwort steht am Anfang, sonst gar nicht.
    Diese Regel ist teuer gelernt und bleibt der Normalfall -- "der
    Sarvis laeuft ganz gut" soll ihn nicht wecken.

    Im Dauerlaerm geht sie aber nicht auf. Dort schneidet der Horcher
    blind alle paar Sekunden ein Stueck heraus, weil das Radio keine
    Pause macht. Wo dein Satz in diesem Stueck liegt, ist Zufall: Vor
    dir lief eine Werbung, hinter dir laufen die Nachrichten weiter. Auf
    den Anfang zu bestehen hiesse, dich im Auto grundsaetzlich zu
    ueberhoeren.

    Zwei Sicherungen halten das eng:

    Erstens ist NUR "<Anrede> <Name>" erlaubt, nie der Name allein. Ein
    Radiobeitrag ueber einen Butler namens Jarvis weckt ihn also nicht;
    es muesste jemand im Radio woertlich "hey jarvis" sagen.

    Zweitens gilt hier die STRENGE Aehnlichkeit. Der lockere Klebefall
    (siehe erkennen) bleibt dem Satzanfang vorbehalten -- mitten im
    Fremdtext ist jede Lockerung ein Risiko ohne Gegenwert.

    Was danach kommt, ist der Zuruf. Dass daran hinten noch ein Stueck
    Radio klebt, laesst sich nicht vermeiden -- ein verunreinigter Zuruf
    ist immer noch besser als gar keiner.
    """
    for i in range(1, len(worte) - 1):
        if worte[i] in config.ANREDEN and _klingt_wie_name(worte[i + 1]):
            return " ".join(worte[i + 2:]).strip()
    return None


def erkennen(text: str, mitten: bool = False) -> str | None:
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
            if _klingt_wie_name(worte[0][len(anrede):],
                                config.WECKWORT_AEHNLICHKEIT_KLEBT):
                return " ".join(worte[1:]).strip()

    if len(worte) >= 2 and worte[0] in config.ANREDEN \
            and _klingt_wie_name(worte[1]):
        return " ".join(worte[2:]).strip()

    # Nur bei einem Stueck, das der Dauerlaerm erzwungen hat.
    if mitten:
        return _mitten_drin(worte)

    return None


class Horcher:
    """Hoert im Hintergrund mit und meldet, wenn das Weckwort faellt."""

    def __init__(self, ohren, wecken, anzeige=None, horch=None):
        """wecken(zuruf: str) -- wird gerufen, wenn das Weckwort fiel.

        horch liefert die Bloecke. Ohne Angabe das Mikrofon dieses
        Rechners; im Netzbetrieb schickt eine Oberflaeche ihren Strom.
        """
        self.ohren = ohren
        self.wecken = wecken
        self.anzeige = anzeige
        if horch is None:
            from . import klang
            horch = klang.dauerhorch()
        self.horch = horch
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
        # Bis wann die noch zum Vergleich taugen, nachdem er fertig ist.
        self._eigen_bis = 0.0
        self._puffer: list[np.ndarray] = []
        self._redet = False
        self._stille = 0.0
        self._begonnen = 0.0
        self._nachhoeren_bis = 0.0   # bis wann ohne Weckwort
        # Sagt er gerade selbst etwas? Dann speist der Lautsprecher den
        # Ring, und der Horcher haelt sich still -- sonst kaempfen zwei
        # Quellen um denselben Ausschlag.
        self._spricht_gerade = False
        self._diktat = False      # dieser Abschnitt laeuft als Diktat
        self._frage_offen = False  # er hat gefragt und wartet auf Antwort
        self._gemeckert: dict[str, float] = {}   # wann welche Stoerung zuletzt
        # Weckwort gefallen, aber der Satz war zu Ende des Stuecks noch
        # nicht fertig -- dann wird EINMAL weitergesammelt statt geweckt.
        self._zuruf_unfertig = False
        # Ein angefangener Satz, auf dessen Rest gewartet wird -- und bis
        # wann. Siehe config.UNFERTIG_WARTEN_SEK.
        self._gehalten = ""
        self._gehalten_bis = 0.0
        # Sitzt die sendende Oberflaeche im Auto? Die App sagt es uns
        # ueber den Draht ({"art": "auto", "an": true}) -- bei jedem
        # Wechsel und einmal direkt nach dem Willkommen.
        self._auto = False
        # Bis wann noch "es ist laut hier" gilt -- siehe config.
        self._laerm_bis = 0.0

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
        self._spricht_gerade = text is not None
        if self._spricht_gerade:
            self._melden(0.0)   # ab hier gehoert der Ring seiner Stimme
        if not config.REINREDEN:
            self.pause(text is not None)
            return
        if text is None:
            # Nicht loeschen, nur ablaufen lassen. Sein Echo steckt beim
            # letzten Satz noch im Puffer und wird erst 0,55 bis 1,4 s
            # spaeter ausgewertet -- wer hier sofort leert, hat beim
            # Vergleich nichts mehr in der Hand, und die eigene Stimme
            # lief als Zuruf durch. pause(False) raeumt den Puffer nicht ab.
            self._eigen_bis = time.perf_counter() + config.DIKTAT_STILLE_SEK
            self.pause(False)
            return
        self._eigen_bis = 0.0
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

    def _eigen_echo(self, text: str, begonnen: float = 0.0) -> bool:
        """Kommt da seine eigene Stimme durchs Mikrofon zurueck?

        Mit Kopfhoerern ist das wenig, aber nicht nichts. Was zurueck-
        kommt, sind seine eigenen Worte -- und die kennen wir genau: es
        ist der Satz, den er in diesem Moment sagt.

        Kurzes bleibt ungeprueft. Sonst verschluckt der Filter ein "nein",
        das zufaellig auch in seinem Satz vorkommt -- und ausgerechnet das
        kurze Dazwischenrufen ist der Fall, um den es hier geht.

        Gezaehlt wird gegen den ANFANG der Aufnahme, nicht gegen jetzt:
        Zwischen dem letzten Ton und dieser Frage liegt noch Whisper, und
        wie lange der rechnet, haengt an der Laenge des Stuecks.
        """
        if self._eigen_bis and begonnen > self._eigen_bis:
            self._eigene_saetze = []
            self._eigen_bis = 0.0
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
            self._melden(0.0)
            self._verwerfen()
        # Der Quelle Bescheid sagen. Lokal folgenlos -- man ueberspringt
        # einfach die Verarbeitung. Ueber Netz ist es der Unterschied
        # zwischen "haelt still" und "sendet weiter, bis der Rueckstand
        # ueberlaeuft": Wer weitersendet, waehrend Sarvis redet, laesst
        # ihn sich selbst zuhoeren, und der Deckel wirft am Ende
        # ausgerechnet das weg, was danach gesagt wird.
        try:
            self.horch.senden_pausieren(bool(an))
        except Exception:
            pass

    # --- Ablauf -------------------------------------------------------------

    def _melden(self, wert: float) -> None:
        """Ausschlag an die Anzeige -- damit man SIEHT, dass er zuhoert.

        Bisher meldete nur die Tastenaufnahme ihren Pegel. Beim Weckwort
        und im Nachhoerfenster stand der Ring still, egal wie laut man
        redete. Das sieht aus wie ein totes Mikrofon, und genau so wurde
        es gelesen: Man redet, nichts passiert, man faengt von vorn an.
        """
        if self.anzeige is not None:
            self.anzeige.pegel(wert)

    def _meckern(self, was: str, text: str) -> None:
        """Eine Stoerung melden, ohne die Konsole zuzuschuetten.

        Der Horcher laeuft 33-mal je Sekunde. Was hier schiefgeht, geht
        deshalb entweder einmal schief oder tausendmal -- gedrosselt
        gemeldet sieht man beides.
        """
        jetzt = time.perf_counter()
        if jetzt - self._gemeckert.get(was, -MECKER_PAUSE * 2) < MECKER_PAUSE:
            return
        self._gemeckert[was] = jetzt
        print(text)

    def _schonen(self, an: bool) -> None:
        """Der Quelle sagen, ob sie bei Rueckstand wegwerfen darf.

        Sie wirft sonst die AELTESTEN Bloecke weg -- und die aeltesten
        sind, waehrend jemand spricht, der Anfang seines Satzes. Genau
        dort steht das Weckwort. Solange geredet wird, soll sie deshalb
        lieber warten; ihre harte Grenze greift trotzdem, falls wirklich
        ein Faden haengt.
        """
        if an == getattr(self, "_schont", False):
            return
        self._schont = an
        try:
            self.horch.schonen(an)
        except Exception:
            pass          # eine Quelle, die das nicht kennt, darf das

    def _weiterhoeren(self) -> None:
        """Wie _verwerfen -- aber der Abschnitt laeuft weiter.

        Beim Kappen im Dauerlaerm hoert der Sprecher nicht auf. Ein Rest
        bleibt als Ueberlappung stehen, damit ein Weckwort auf der
        Schnittkante im naechsten Stueck vollstaendig vorkommt.

        Und der VAD wird hier ausdruecklich NICHT zurueckgesetzt. Sein
        Gedaechtnis stimmt ja gerade: Es wird tatsaechlich weiter
        geredet. Ruecksetzen wuerde die Vorhersage genau dann verwerfen,
        wenn sie richtig ist.
        """
        rest = int(config.LAERM_UEBERLAPPUNG_SEK * RATE / BLOCK)
        self._puffer = self._puffer[-rest:] if rest else []
        self._laerm_bis = (time.perf_counter()
                           + config.LAERM_GEDAECHTNIS_SEK)
        self._stille = 0.0
        self._begonnen = time.perf_counter() - config.LAERM_UEBERLAPPUNG_SEK

    def _verwerfen(self):
        self._puffer = []
        self._redet = False
        self._stille = 0.0
        self._diktat = False
        self._schonen(False)
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
        """Mikrofon lesen und verstehen -- getrennt, in zwei Faeden.

        Vorher lag beides in dieser Schleife: strom.read() holte einen
        Block, und derselbe Faden lief weiter bis in Whisper hinein.
        Solange das rechnete, rief niemand read(), der Geraetepuffer lief
        ueber, und das Gehoerte fehlte danach einfach. Gemessen auf der
        3080 mit echter Sprache: 0,114 s bei einem kurzen Zuruf bis
        0,150 s bei einem langen Satz -- knapp fuenf Bloecke, also rund
        eine Silbe. Genug, um einem "Hey Sarvis" den Anfang zu nehmen,
        wenn kurz davor ein Rascheln geprueft wurde.
        (Die frueher hier stehende Meldung sprach von "Sekunden verloren"
        -- das war um eine Groessenordnung zu hoch gegriffen.)

        Jetzt fuellt der Audio-Faden von PortAudio nur noch eine
        Warteschlange. Whisper darf blockieren, so lange es will: Die
        Bloecke stauen sich und werden danach nachgeholt, statt zu
        verschwinden. Am Zustand des Horchers aendert das nichts -- der
        wird weiterhin ausschliesslich hier angefasst.
        """
        # Die Bloecke kommen aus der Quelle, nicht mehr direkt vom
        # Geraet. Lokal ist das klang.LokalHorch mit demselben Code wie
        # vorher; auf dem Server schickt eine Oberflaeche ihren
        # Mikrofonstrom ueber den Draht.
        #
        # Was hier NICHT steht, ist der Grund fuer den Umbau: kein
        # sounddevice mehr. Dieses Modul liess sich sonst auf einem
        # Rechner ohne Audiogeraet nicht einmal importieren -- und
        # damit war das Weckwort auf dem Server nicht "aus", sondern
        # unerreichbar.
        try:
            self.horch.oeffnen()
            while self._laeuft:
                for block, stromzeit in self.horch.bloecke():
                    if not self._laeuft:
                        break
                    meldung = self.horch.aussetzer()
                    if meldung:
                        self._meckern("strom", f"  ({meldung})")
                    if self.pausiert:
                        continue
                    self._block(block)
        except Exception as e:
            print(f"  (Weckwort-Horcher beendet: {e})")
        finally:
            try:
                self.horch.schliessen()
            except Exception:
                pass

    def _gehaltenes_losschicken(self) -> None:
        """Der Rest kam nicht -- dann geht der Anfang so los, wie er ist."""
        zuruf, self._gehalten = self._gehalten, ""
        self._nachhoeren_bis = 0.0
        print(f"\n  * Kein Rest gekommen, geht so los: {zuruf!r}")
        self.pausiert = True
        self._verwerfen()
        self.wecken(zuruf)

    def _block(self, block: np.ndarray) -> None:
        jetzt = time.perf_counter()
        # Wartet ein angefangener Satz, und es kam nichts mehr nach?
        # Solange gerade geredet wird, nicht -- das ist ja der Rest.
        if (self._gehalten and not self._redet
                and jetzt >= self._gehalten_bis):
            self._gehaltenes_losschicken()
            return
        try:
            # Silero will 16-Bit-PCM: predict() teilt intern durch 32767.
            # Mit Fliesskomma-Werten aus sounddevice kommt dabei praktisch
            # null heraus -- der VAD haette nie Sprache gesehen. Genau
            # dieser Fehler liess den Horcher stumm bleiben.
            pcm = (np.clip(block, -1.0, 1.0) * 32767).astype(np.int16)
            wahrscheinlich = float(self.vad.predict(pcm, frame_size=BLOCK))
        except Exception as e:
            # Frueher stand hier 'return'. Damit blieb bei einem Dauer-
            # fehler _redet auf True stehen, _pruefen() wurde nie wieder
            # erreicht, und der Horcher war dauerhaft taub -- ohne
            # Absturz und ohne eine einzige Zeile. Als "keine Sprache"
            # gewertet laeuft ein angefangener Abschnitt normal aus.
            wahrscheinlich = 0.0
            self._meckern("vad", f"  (VAD stolperte — {e})")

        # Zweite Meinung: der Pegel. Der VAD allein meldete 0.91 bei
        # leerem Pegelbalken -- wer nichts hoert, redet auch nicht.
        pegel = float(np.sqrt(np.mean(np.square(block, dtype=np.float64))))
        spricht = (wahrscheinlich >= config.VAD_SCHWELLE
                   and pegel >= config.WECKWORT_MIN_PEGEL)

        # Solange er nicht selbst redet, gehoert der Ring dem Mikrofon.
        if not self._spricht_gerade:
            self._melden(audio.pegel(block))

        if spricht:
            if not self._redet:
                self._redet = True
                self._begonnen = jetzt
            self._stille = 0.0
            self._puffer.append(block)
            # Es redet jemand -- ab hier nichts mehr wegwerfen.
            self._schonen(True)
            if jetzt - self._begonnen > self._deckel():
                # Beim Laerm-Deckel wird nur ein Stueck herausgeschnitten
                # und es geht weiter -- der Sprecher hoert ja nicht auf.
                # Bei der Notbremse ist der Abschnitt wirklich zu Ende.
                self._pruefen(gekappt=self._laerm_deckel())
            return

        if not self._redet:
            return

        # Nachlauf: kurze Pausen im Satz sind keine Satzenden.
        self._puffer.append(block)
        self._stille += BLOCK / RATE
        if self._stille >= self._stille_grenze():
            self._pruefen()

    def _deckel(self) -> float:
        """Wie lange ein Abschnitt hoechstens dauern darf.

        Zwei Werte, weil es zwei Faelle sind. Ein laufender Fernseher soll
        den Puffer nicht endlos fuellen -- der wird nach WECKWORT_MAX_SEK
        abgeraeumt. Wer dagegen im offenen Fenster angefangen hat, redet
        mit ihm und darf dabei ausholen.

        Vorher galt ein Deckel fuer beide. Nach dreissig Sekunden wurde
        geprueft, das Nachhoerfenster war da laengst zu, und die ganze
        Rede verschwand ohne ein Wort Antwort.
        """
        # Frueher stand hier WECKWORT_MAX_SEK (90 s). Das war zu lang:
        # Bei Dauerlaerm wuchs der Abschnitt so weit, dass ein Weckwort
        # darin nur noch in der Mitte vorkam -- und dort wurde nie
        # gesucht. Jetzt wird alle paar Sekunden hineingehoert.
        return (config.LAERM_STUECK_SEK if self._laerm_deckel()
                else config.WECKWORT_MAX_ANGESPROCHEN_SEK)

    def _laerm_deckel(self) -> bool:
        """Gilt der kurze Laerm-Deckel -- oder die lange Notbremse?

        Eine Wahrheit fuer zwei Fragen: wann abgeschnitten wird, UND ob
        das Abgeschnittene ein Laermstueck ist. Die beiden aus getrennten
        Bedingungen abzuleiten ging schief -- im Auto galt der kurze
        Deckel, das Stueck wurde aber nicht als Laerm behandelt, und das
        Radio ging als Antwort im Nachhoerfenster durch. Gemessen.
        """
        return self.im_laerm() or not self.hoert_nach(self._begonnen)

    def im_laerm(self) -> bool:
        """Ist es hier gerade dauerhaft laut? Gemessen, nicht vermutet.

        Ausschliesslich die Messung: Zuletzt musste ein Abschnitt
        abgeschnitten werden, weil keine Pause kam.

        Das Auto-Signal der App zaehlt hier bewusst NICHT mit. Es sagt,
        wo das Handy steckt, nicht wie laut es dort ist -- und im Auto
        mit ausgeschaltetem Radio ist es still. Wer das Signal hier
        mitzaehlen liesse, zerhackte genau dort jedes Diktat, wo es am
        ehesten gebraucht wird: unterwegs, mit freien Haenden.

        Im Auto greift die Messung ohnehin von selbst. Bevor Sascha ihn
        anspricht, ist das Nachhoerfenster zu; dort wird schon nach ein
        paar Sekunden Dauerlaerm geschnitten, und ab dann gilt der
        Merker auch im offenen Fenster.

        Wofuer das Signal dient, steht in im_auto(): Es lockert die
        SUCHE nach dem Weckwort, nicht den Schnitt.
        """
        return time.perf_counter() < self._laerm_bis

    def _stille_grenze(self) -> float:
        """Wie lange Stille diesen Satz beendet -- je nachdem, wie lange
        schon gesprochen wird.

        "Wie spaet ist es" ist nach einer halben Sekunde Stille fertig.
        Wer seit fuenf Sekunden einen Gedanken ausformuliert, macht
        dazwischen Pausen -- und wurde bisher jedes Mal unterbrochen.
        """
        gesprochen = sum(len(b) for b in self._puffer) / RATE
        # Dritte Stufe: Wer eine halbe Minute am Stueck spricht, ruft
        # nichts mehr zu -- der diktiert. Und wer diktiert, denkt
        # zwischendurch nach. Zwei Sekunden Schweigen sind da kein
        # Satzende, sondern eine Formulierung, die noch nicht steht.
        #
        # Bewusst ohne Kommandowort. "Sarvis, ich diktiere dir jetzt
        # etwas" sagt kein Mensch; man faengt einfach an zu reden. Die
        # Laenge der Rede ist das Signal, nicht eine Ansage darueber.
        if gesprochen >= config.DIKTAT_AB_SEK:
            if not self._diktat:
                self._diktat = True
                print(f"  (Diktat: seit {gesprochen:.0f}s am Stueck -- "
                      f"er wartet jetzt {config.DIKTAT_STILLE_SEK:.0f}s "
                      f"Stille ab, statt dir ins Wort zu fallen)")
            return config.DIKTAT_STILLE_SEK
        if gesprochen >= config.WECKWORT_LANG_AB_SEK:
            return config.WECKWORT_STILLE_LANG_SEK
        return config.WECKWORT_STILLE_SEK

    def _pruefen(self, gekappt: bool = False) -> None:
        stueck = self._puffer
        dauer = sum(len(b) for b in stueck) / RATE
        # Wann dieser Abschnitt BEGANN -- nicht, wann er endet. Daran
        # haengt unten, ob das Nachhoerfenster offen war.
        begonnen = self._begonnen
        if not gekappt:
            self._verwerfen()
        if dauer < config.WECKWORT_MIN_SEK:
            if gekappt:
                self._weiterhoeren()
            return

        # Ueber ein langes Stueck rechnet Whisper spuerbar -- zwei Minuten
        # Diktat sind auch auf der Karte keine Millisekunden. Ohne Anzeige
        # steht der Ring in dieser Zeit still, und das sieht genau aus wie
        # ein Mikrofon, das gar nichts gehoert hat. Genau der Eindruck,
        # der einen dazu bringt, noch mal von vorn anzufangen.
        zeigt = (dauer >= config.WECKWORT_LANG_AB_SEK
                 and self.anzeige is not None
                 and not self._spricht_gerade
                 and not gekappt)     # im Laerm liefe die Anzeige dauernd
        if zeigt:
            self.anzeige.zustand(DENKT)
        geweckt = False
        try:
            geweckt = self._deuten(stueck, begonnen, gekappt)
        finally:
            # Wurde geweckt, fuehrt die Schleife die Anzeige weiter. Sonst
            # zurueck -- aber wohin? Steht eine Rueckfrage offen, gehoert
            # der Ring ihr: Einfach auf RUHIG zu setzen loeschte das
            # "wartet auf dich", waehrend er tatsaechlich weiter wartete.
            if zeigt and not geweckt:
                self.anzeige.zustand(FRAGT if self._frage_offen else RUHIG)
            # Erst jetzt entscheidet sich, wie viel vom Stueck stehen
            # bleibt. Beim Wecken hat _deuten schon abgeraeumt; steht ein
            # angefangener Zuruf offen, bleibt ALLES stehen und waechst
            # beim naechsten Mal weiter -- sonst nur die Ueberlappung.
            if gekappt and not geweckt:
                if self._zuruf_unfertig:
                    # Der Puffer bleibt und waechst -- aber die Uhr fuer
                    # den naechsten Schnitt laeuft neu an. Ohne das waere
                    # sie sofort wieder abgelaufen und dasselbe Stueck
                    # ginge im Kreis durch Whisper.
                    self._begonnen = time.perf_counter()
                else:
                    self._weiterhoeren()

    def _deuten(self, stueck: list, begonnen: float,
                gekappt: bool = False) -> bool:
        """Was war das? True, wenn daraus ein Zuruf wurde.

        gekappt heisst: Dieses Stueck endete nicht durch Stille, sondern
        wurde aus einem Dauerlaerm herausgeschnitten. Dann steht darin
        fast sicher Fremdtext, und es gelten zwei andere Regeln -- siehe
        unten.
        """
        aufnahme = np.concatenate(stueck)
        try:
            # Der Name als Hinweis -- hier zaehlt er am meisten.
            text = self.ohren.hoeren(
                aufnahme, hinweise=f"Hey {config.NAME.capitalize()}"
            )
        except Exception as e:
            print(f"  (Weckwort: Whisper stolperte — {e})")
            return False
        if not text:
            return False
        if _halluziniert(text) or _dreht_sich_im_kreis(text):
            print(f"  (Whisper-Halluzination verworfen: {text!r})")
            return False
        if self._eigen_echo(text, begonnen):
            return False

        # Mitten im Satz suchen darf er in zwei Faellen: wenn das Stueck
        # aus Dauerlaerm herausgeschnitten wurde (gemessen), oder wenn
        # die App sagt, dass gefahren wird (gewusst). Sonst nie.
        mitten = gekappt or self._auto
        zuruf = erkennen(text, mitten=mitten)
        wie = "Weckwort"
        if zuruf is not None and mitten and not erkennen(text):
            wie = "Weckwort im Lärm" if gekappt else "Weckwort im Auto"

        # Der Schnitt faellt blind -- er kann mitten zwischen "Hey
        # Sarvis" und die Frage fallen. Dann steht das Weckwort da, aber
        # der Zuruf ist leer, und Sarvis wachte auf, um nichts zu hoeren.
        # Gemessen: Schnitt bei 19,6 s, Zuruf ab 19,7 s -- er sagte "Ja?"
        # und die Frage war weg.
        #
        # Deshalb einmal weitersammeln statt wecken: Beim naechsten
        # Durchgang ist das Stueck laenger und enthaelt beides. Nur
        # EINMAL, sonst wuechse der Puffer bei jedem halben Weckwort
        # immer weiter.
        vorher_unfertig = self._zuruf_unfertig
        self._zuruf_unfertig = False
        if (mitten and zuruf is not None and not vorher_unfertig
                and len(zuruf.split()) < 2):
            self._zuruf_unfertig = True
            print(f"  * Weckwort am Stückrand: {text[-40:]!r} "
                  f"— warte auf den Rest")
            return False

        # NACKTES WECKWORT IM LAERM ODER AUTO -- der haeufigste Fehlstart.
        #
        # Whisper bekommt "Hey Sarvis" als Hotword mit (siehe oben, die
        # hoeren()-Zeile). Bei Rauschen und Fremdgeplapper gibt es genau
        # diesen Hinweis als Text zurueck -- der Prompt kommt heraus, wo
        # nichts hineinging. Das ist kein Verhoeren, sondern ein bekanntes
        # Verhalten des Modells, dieselbe Familie wie die Abspann-Saetze
        # in _HALLUZINATIONEN.
        #
        # GEMESSEN am Morgen des 03.09. im Auto: zwoelf Fehlstarts in
        # zwanzig Minuten, und ALLE ZWOELF lauteten wortgleich "Hey
        # Sarvis" und sonst nichts. Kein einziger trug einen Zuruf. Er
        # antwortete zwoelfmal "Zu Diensten", "Schieß los", "Sag an" --
        # in ein Auto, in dem niemand ihn gerufen hatte.
        #
        # Warum es hier nicht reicht, den Text zu verwerfen: Manchmal ist
        # der Ruf echt. Man sagt "Hey Sarvis", holt Luft und fragt dann.
        # Deshalb wird nicht verworfen, sondern STILL zugehoert -- ein
        # kurzes Fenster, in dem der naechste Satz ohne Weckwort gilt.
        # Kommt er, wird er bearbeitet; kommt nichts, hat es niemand
        # gemerkt. Der Fehlstart kostet dann Rechenzeit statt Aufmerksam-
        # keit, und das ist der billigere Fehler.
        #
        # Nur im Laerm und im Auto. Am Schreibtisch, wo ein Stueck durch
        # Stille begrenzt ist, ist ein nacktes "Hey Sarvis" fast immer
        # echt -- dort bleibt es beim gesprochenen "Ja?".
        if mitten and zuruf is not None and not zuruf.strip():
            self.nachhoeren(config.WECKWORT_NACKT_SEK)
            print(f"  (nur das Weckwort, kein Zuruf: {text!r} "
                  f"— {config.WECKWORT_NACKT_SEK:.0f}s still zugehört)")
            return False

        if zuruf is None:
            if gekappt:
                # Kein Weckwort in einem Laermstueck heisst: Das war
                # nicht fuer uns. Der Nachhoer-Zweig darunter darf hier
                # NICHT greifen -- er nimmt jeden Satz als Zuruf, und in
                # einem Laermstueck ist jeder Satz das Radio. Sonst
                # unterhielte sich Sarvis mit den Nachrichten.
                self._meckern("laerm", f"  (Dauerlärm, kein Weckwort: "
                                       f"{text[:60]!r})")
                return False
            # Hat Sarvis gerade geantwortet, ist der naechste Satz die
            # Fortsetzung -- dann waere ein erneutes "Hey Sarvis" albern.
            # Er fragt ja selbst, wie er dienen kann; die Antwort darauf
            # zu verwerfen war der Fehler.
            # Entscheidend ist der ANFANG des Satzes, nicht sein Ende.
            # Hier stand die aktuelle Uhrzeit: Wer im offenen Fenster
            # loslegte und laenger sprach, als das Fenster dauert, fiel
            # genau in dem Moment heraus, in dem er fertig war. Gemessen
            # an einer Rede von 35 Sekunden bei 18 Sekunden Fenster --
            # verworfen, stumm, ohne eine Zeile in der Konsole.
            if not self.hoert_nach(begonnen):
                if len(text.split()) >= 2:
                    print(f"  (kein Weckwort, Fenster war zu: {text!r})")
                return False
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
            #
            # Und nicht nur "ja": Steht eine Frage offen, ist JEDES
            # einzelne Wort eine moegliche Antwort. Auf "Was soll ich
            # öffnen?" sagt man "YouTube" -- ein Wort, das rueckfrage.
            # deuten() nicht kennt und das deshalb hier stumm verschwand.
            # Woertlich passiert: dreimal "YouTube" gesagt, dreimal
            # verworfen, ohne eine Zeile in der Konsole.
            # Haengt ein angefangener Satz in der Luft, ist auch ein
            # einzelnes Wort sein Rest ("... erinnern an" -- "Morgen.").
            if (len(text.split()) < 2
                    and not self._frage_offen
                    and not self._gehalten
                    and rueckfrage.deuten(text) == rueckfrage.UNKLAR):
                print(f"  (zu kurz fuer einen Zuruf, verworfen: {text!r})")
                return False
            zuruf = text.strip()
            wie = "Nachhören"

        # Der Rest eines angefangenen Satzes: vorne anhaengen. Kam statt
        # dessen ein neues "Hey Sarvis", hat er von vorn angefangen --
        # dann gilt der neue Anlauf, der alte Anfang ist verbraucht.
        if self._gehalten:
            if wie == "Nachhören":
                zuruf = f"{self._gehalten} {zuruf}"
            self._gehalten = ""

        # Klingt das nach mehr? Dann noch nicht wecken, sondern warten.
        # Nicht bei einer offenen Rueckfrage (dort ist "Ja" fertig) und
        # nicht im Laermstueck (dort entscheidet der Schnitt, nicht er).
        if (not gekappt and not self._frage_offen
                and _klingt_unfertig(zuruf)):
            self._gehalten = zuruf
            self._gehalten_bis = (time.perf_counter()
                                  + config.UNFERTIG_WARTEN_SEK)
            self._nachhoeren_bis = max(self._nachhoeren_bis,
                                       self._gehalten_bis)
            print(f"  … klingt unfertig, warte auf den Rest: "
                  f"{zuruf[-50:]!r}")
            self._verwerfen()
            return False

        self._nachhoeren_bis = 0.0
        print(f"\n  * {wie}: {text!r}")
        self.pausiert = True     # bis der Durchgang durch ist
        # Die Laerm-Ueberlappung enthaelt das Weckwort noch einmal --
        # sonst wird derselbe Zuruf im naechsten Stueck ein zweites Mal
        # erkannt und Sarvis antwortet doppelt. Gemessen im Trockenlauf.
        # Dass die Pause das nebenbei auch abfangen wuerde, reicht nicht:
        # Darauf soll sich das hier nicht verlassen muessen.
        self._verwerfen()
        self.wecken(zuruf)
        return True

    # --- Nachhoeren ---------------------------------------------------------

    def im_auto(self, an: bool, geraet: str = "") -> None:
        """Die Oberflaeche meldet, dass sie im Auto steckt.

        Dauerlaerm erkennt der Horcher ohnehin selbst -- daran, dass ein
        Abschnitt nie durch Stille endet. Dafuer braucht er dieses Wort
        nicht.

        Wofuer er es braucht: Auch eine ruhige Fahrt ist laut genug, dass
        ein Zuruf zwischen Motor und Fahrbahn liegt, ohne dass der
        Abschnitt je gekappt wuerde. Dann darf er das Weckwort auch
        mitten im Satz suchen statt nur am Anfang -- dieselbe Lockerung
        wie im gemessenen Laerm, nur ausgeloest durch Wissen statt durch
        Messung.

        Am Schreibtisch bleibt es bei der strengen Regel.
        """
        an = bool(an)
        if an != self._auto:
            wo = f" ({geraet})" if geraet else ""
            print(f"  (Auto: {'ein' if an else 'aus'}{wo})")
        self._auto = an

    def frage_offen(self, an: bool) -> None:
        """Steht gerade eine Rueckfrage offen?

        Der Horcher muss das wissen, weil eine Antwort auf eine Frage
        anderen Regeln gehorcht als ein Zuruf aus dem Nichts: Sie darf
        aus einem einzigen Wort bestehen. Auf "Was soll ich öffnen?"
        sagt man "YouTube" und sonst nichts.
        """
        self._frage_offen = bool(an)

    def nachhoeren(self, sekunden: float | None = None) -> None:
        """Kurzes Fenster, in dem kein Weckwort noetig ist."""
        if not self._laeuft:
            return
        # Im Auto ist das Standardfenster kuerzer. Achtzehn Sekunden
        # ohne Weckwort sind am Schreibtisch richtig; im Auto redet in
        # dieser Zeit das Radio weiter, und jeder Satz im offenen
        # Fenster gilt als Zuruf. Eine ausdrueckliche Angabe (etwa nach
        # einer Rueckfrage) sticht das -- dort ist DEINE Antwort gemeint
        # und soll nicht an der Fahrt scheitern.
        vorgabe = (config.NACHHOEREN_AUTO_SEK if self._auto
                   else config.NACHHOEREN_SEK)
        self._nachhoeren_bis = time.perf_counter() + (
            vorgabe if sekunden is None else sekunden
        )

    def hoert_nach(self, zeitpunkt: float | None = None) -> bool:
        """War das Fenster zu diesem Zeitpunkt offen? Ohne Angabe: jetzt."""
        wann = time.perf_counter() if zeitpunkt is None else zeitpunkt
        return wann < self._nachhoeren_bis
