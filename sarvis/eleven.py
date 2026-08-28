"""ElevenLabs: die gute Stimme, wenn sie gebraucht wird.

Gedacht zum VORFUEHREN, nicht fuer den Alltag -- und das ist keine
Bescheidenheit, sondern Arithmetik. Gemessen an fuenf echten Tagen aus
Sarvis' Sitzungsprotokollen:

    363 gesprochene Antworten, im Schnitt 73 Zeichen
    Schnitt je Tag   5.289 Zeichen
    staerkster Tag   9.719 Zeichen

Das kostenlose Kontingent sind 10.000 Zeichen im MONAT. Es reicht damit
1,9 Tage, an einem Tag wie dem staerksten genau einen. Wer das als
Alltagsstimme einschaltet, hat zwei gute Tage und danach acht-
undzwanzig, an denen er ueber den Wechsel stolpert. Fuer eine
Vorfuehrung von zehn Minuten reicht es dagegen muehelos.

Deshalb der Schalter in config.STIMME_DIENST, und deshalb ist "piper"
die Vorgabe.

DER RUECKFALL IST DER EIGENTLICHE ENTWURF. Was hier schiefgehen kann,
geht irgendwann schief, und zwar mitten im Satz vor Publikum: kein Netz,
Kontingent leer, Schluessel ohne Berechtigung, Dienst langsam. In JEDEM
dieser Faelle spricht Piper weiter, und Sarvis sagt kein Wort darueber
-- eine Stimme, die sich fuer sich selbst entschuldigt, ist schlimmer
als eine, die einfach anders klingt. Gemeldet wird auf der Konsole,
einmal, mit Grund.

WELCHE STIMMEN GEHEN: Gemessen am 28.08.2026 laesst der kostenlose Tarif
nur die Sorte "premade" durch. Alles aus der Stimmbibliothek -- Sorte
"professional" -- wird mit 402 abgelehnt ("Free users cannot use library
voices via the API"), auch die anfangs gewuenschte 87Aw... Das Konto
sieht 21 premade- und 5 professional-Stimmen; geprueft wurden beide
Sorten, das Ergebnis ist eindeutig.

WAS ES KOSTET: Der Kopf "character-cost" der Antwort nennt genau die
Textlaenge (78 Zeichen -> 78). Danach wird gezaehlt. Die Abfrage des
Kontostands hinkt dagegen hinterher -- 115 vor vier Anfragen ueber je 78
Zeichen, 115 danach. Deshalb korrigiert sie den eigenen Stand nur nach
oben, nie nach unten.

WAS ES AN ZEIT KOSTET: 1,30 bis 1,54 Sekunden bis zum ersten Ton, gegen
0,12 bei Piper. Fuer eine Vorfuehrung ist das zu verschmerzen, fuer den
Alltag waere es der zweite Grund gegen diesen Dienst -- nach dem
Kontingent.
"""
import io
import time

import numpy as np

from . import config

_BASIS = "https://api.elevenlabs.io/v1"

# Wie viel vom Kontingent verbraucht sein darf, bevor zurueckgefallen
# wird. Nicht bei hundert Prozent: Die letzte Anfrage wuerde sonst
# mitten im Satz abgelehnt, und der Rest der Vorfuehrung fiele auf die
# Nase. Ein Zehntel Rueckhalt reicht fuer jede einzelne Antwort.
GRENZE = 0.90

# Nach so vielen Saetzen wird der Stand neu erfragt. Dazwischen wird
# mitgezaehlt -- das ist genau genug und spart eine Abfrage je Satz.
NACHZAEHLEN_NACH = 15


class Eleven:
    """Spricht ueber ElevenLabs. Gibt None zurueck, wenn es nicht geht.

    None heisst immer dasselbe: Nimm Piper. Der Aufrufer muss keinen
    einzigen Fehlerfall unterscheiden -- das ist der Sinn.
    """

    def __init__(self):
        self.bereit = False
        self.grund = ""
        self._verbraucht = 0
        self._grenze = 0
        self._seit_abfrage = 0
        self._gemeldet = set()

        schluessel = config._env_werte().get("ELEVENLABS_SCHLUESSEL")
        if not schluessel:
            self.grund = "kein Schluessel in der .env"
            return
        self._kopf = {"xi-api-key": schluessel}
        if self._stand_holen():
            self.bereit = True

    # --- Kontingent -------------------------------------------------------

    def _stand_holen(self) -> bool:
        import httpx

        try:
            a = httpx.get(f"{_BASIS}/user/subscription", headers=self._kopf,
                          timeout=config.ELEVENLABS_ZEITGRENZE)
        except Exception as e:
            self.grund = f"nicht erreichbar ({type(e).__name__})"
            return False
        if a.status_code != 200:
            self.grund = f"Zugang abgelehnt ({a.status_code})"
            return False
        d = a.json()
        gemeldet = int(d.get("character_count") or 0)
        self._grenze = int(d.get("character_limit") or 0)
        self._seit_abfrage = 0
        # Der Zaehler geht NIE zurueck.
        #
        # Gemessen: 115 vor vier Anfragen ueber je 78 Zeichen, 115 danach.
        # Die Abfrage hinkt hinterher -- vermutlich zwischengespeichert.
        # Wuerde man sie ungeprueft uebernehmen, setzte jede
        # Nachsynchronisierung den Stand zurueck, und die Bremse bei
        # neunzig Prozent griffe nie. Der eigene Stand ist im Zweifel der
        # aktuellere; die Abfrage darf ihn nur nach OBEN korrigieren
        # (etwa wenn nebenher noch woanders gesprochen wurde).
        self._verbraucht = max(self._verbraucht, gemeldet)
        return True

    def anteil(self) -> float:
        """Wie viel vom Kontingent weg ist, 0.0 bis 1.0."""
        if not self._grenze:
            return 0.0
        return self._verbraucht / self._grenze

    def reicht_noch(self, zeichen: int) -> bool:
        """Passt dieser Satz noch unter die Grenze?

        Gerechnet wird MIT dem Satz, nicht vor ihm: Sonst rutscht man
        genau an der Schwelle noch hinein und faellt beim naechsten Wort
        heraus -- mitten in derselben Antwort.
        """
        if not self._grenze:
            return True
        return (self._verbraucht + zeichen) / self._grenze < GRENZE

    def stand_satz(self) -> str:
        """Eine Zeile fuer die Konsole beim Start."""
        if not self.bereit:
            return f"ElevenLabs aus ({self.grund})"
        return (f"ElevenLabs bereit -- {self._verbraucht} von "
                f"{self._grenze} Zeichen verbraucht "
                f"({self.anteil() * 100:.0f} %)")

    # --- Sprechen ---------------------------------------------------------

    def sprechen(self, text: str):
        """(Proben, Rate) -- oder None, wenn Piper uebernehmen soll."""
        import httpx

        if not self.bereit or not text.strip():
            return None
        if not self.reicht_noch(len(text)):
            self._melden("kontingent",
                         f"Kontingent zu {self.anteil() * 100:.0f} % "
                         "verbraucht -- ab jetzt Piper")
            return None

        try:
            a = httpx.post(
                f"{_BASIS}/text-to-speech/{config.ELEVENLABS_STIMME}",
                headers={**self._kopf, "content-type": "application/json"},
                params={"output_format": config.ELEVENLABS_FORMAT},
                json={"text": text, "model_id": config.ELEVENLABS_MODELL},
                timeout=config.ELEVENLABS_ZEITGRENZE,
            )
        except Exception as e:
            self._melden("netz", f"nicht erreichbar ({type(e).__name__})")
            return None

        if a.status_code != 200:
            grund = f"Fehler {a.status_code}"
            try:
                grund += ": " + str(a.json().get("detail", {}).get("message"))
            except Exception:
                pass
            self._melden(f"http{a.status_code}", grund)
            return None

        # Erst zaehlen, dann dekodieren: Verbraucht ist es beim Dienst
        # auch dann, wenn das Umwandeln hier scheitert.
        #
        # Gezaehlt wird aus dem Kopf der Antwort, nicht aus der Textlaenge.
        # Gemessen stimmen beide ueberein (78 Zeichen, "character-cost: 78"),
        # aber der Dienst rechnet ab, nicht wir -- und wenn er das eines
        # Tages anders tut, soll die Bremse mitwandern.
        try:
            kosten = int(a.headers.get("character-cost", len(text)))
        except (TypeError, ValueError):
            kosten = len(text)
        self._verbraucht += kosten
        self._seit_abfrage += 1
        if self._seit_abfrage >= NACHZAEHLEN_NACH:
            self._stand_holen()

        try:
            return _zu_proben(a.content, config.ELEVENLABS_FORMAT)
        except Exception as e:
            self._melden("dekodieren", f"Ton nicht lesbar ({type(e).__name__})")
            return None

    def _melden(self, schluessel: str, text: str) -> None:
        """Jeden Grund genau EINMAL auf die Konsole.

        Sonst steht bei fehlendem Netz je Satz eine Zeile da, und die
        eine Zeile, auf die es ankommt, geht darin unter.
        """
        if schluessel in self._gemeldet:
            return
        self._gemeldet.add(schluessel)
        print(f"  (ElevenLabs: {text} -- Piper uebernimmt)")


# --- Ton umwandeln --------------------------------------------------------

def _zu_proben(daten: bytes, form: str) -> tuple[np.ndarray, int]:
    """Antwort des Dienstes zu (float32-Proben, Rate).

    Zwei Wege, und der erste ist der bessere: Bei "pcm_..." kommen rohe
    16-Bit-Werte, die nur geteilt werden muessen. Der kostet allerdings
    einen bezahlten Tarif -- deshalb kann es auch MP3 sein, und das geht
    durch av (schon im Projekt, wegen nichts anderem waere es der Muehe
    wert).
    """
    if form.startswith("pcm_"):
        rate = int(form.split("_")[1])
        roh = np.frombuffer(daten, dtype="<i2").astype("float32")
        return roh / 32768.0, rate

    import av

    behaelter = av.open(io.BytesIO(daten))
    strom = behaelter.streams.audio[0]
    # Auf ein Kanal und float32 bringen -- alles Weitere im Projekt
    # rechnet damit. Die Rate laesst der Umwandler, wie sie ist; der
    # Lautsprecher bekommt sie mitgeteilt.
    umwandler = av.AudioResampler(format="flt", layout="mono")
    stuecke = []
    for bild in behaelter.decode(strom):
        for teil in umwandler.resample(bild):
            stuecke.append(teil.to_ndarray().reshape(-1))
    # Der Umwandler haelt beim letzten Bild noch etwas zurueck.
    for teil in umwandler.resample(None):
        stuecke.append(teil.to_ndarray().reshape(-1))
    rate = strom.rate
    behaelter.close()
    if not stuecke:
        return np.zeros(0, dtype="float32"), rate
    return np.concatenate(stuecke).astype("float32"), rate
