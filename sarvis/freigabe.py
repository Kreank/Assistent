r"""Freigaben auf Zeit -- "ja, und frag die naechste halbe Stunde nicht mehr".

Der Grund ist derselbe wie bei allem anderen hier: Ein Assistent, der
alle zehn Sekunden dieselbe Erlaubnis einholt, wird abgeschaltet. Ein
Chef sagt einmal ja und danach eine Weile nichts mehr.

Eine Freigabe haengt an ZWEI Dingen, nicht an einem:

    (was)  das Werkzeug   -- "Dateien lesen"
    (wo)   der Ort        -- "unter D:\Mitra\MCN"

Nur am Werkzeug waere zu breit: Wer einmal Lesen im Projektordner
freigibt, haette danach auch Lesen in D:\Strato Server frei. Nur am Ort
waere ebenso falsch -- lesen duerfen heisst nicht schreiben duerfen.

Drei Dinge sind bewusst so gebaut:

  Zeitlich begrenzt. Es gibt kein "fuer immer". Eine Freigabe, an die
  man sich nicht mehr erinnert, ist keine Freigabe mehr, sondern eine
  Einstellung -- und die gehoert in config.py, wo man sie sieht.

  Sichtbar. Solange eine laeuft, steht sie in der Anzeige und in der
  Zustandszeile, die bei jedem Zuruf mitgeht. Was still gilt, gilt
  irgendwann laenger, als man denkt.

  Nicht fuer alles. Was hinausgeht und sich nicht zurueckholen laesst --
  Mail, Telegram, Freigabe von Dateien -- bleibt aussen vor. Dort ist die
  Rueckfrage nicht laestig, sondern der eigentliche Zweck.
"""
import re
import time
from pathlib import Path

from . import config

# Woraus sich der Ort einer Anfrage ergibt. Werkzeuge, die hier nicht
# stehen, haben keinen Ort -- ihre Freigabe gilt fuer das Werkzeug als
# solches.
_PFAD_WERKZEUGE = ("datei_lesen", "datei_schreiben", "ordner_ansehen")


def ort(werkzeug: str, eingabe: dict) -> str:
    """Der Ordner, um den es geht -- oder "" fuer ortlose Werkzeuge.

    Bei einer Datei ist es der Ordner darueber: Wer "config.php im Ordner
    MCN" freigibt, meint den Ordner, nicht genau diese eine Datei -- sonst
    fragt Sarvis bei der naechsten Datei daneben wieder.
    """
    e = eingabe or {}
    pfad = ""
    if werkzeug in _PFAD_WERKZEUGE:
        pfad = str(e.get("pfad") or "")
    elif werkzeug == "befehl_ausfuehren":
        treffer = re.findall(r"[a-zA-Z]:[\\/][^\s\"';|]*", str(e.get("befehl") or ""))
        pfad = treffer[0] if treffer else ""
    if not pfad:
        return ""
    try:
        p = Path(pfad)
        # Ein vorhandener Ordner ist selbst der Ort. Sonst waere der Ort
        # von "D:\Mitra" das Laufwerk D -- viel zu weit.
        return str((p if p.is_dir() else p.parent).resolve())
    except (OSError, ValueError):
        return ""


def _unter(kind: str, eltern: str) -> bool:
    if not eltern:
        return True          # ortlose Freigabe gilt ueberall
    if not kind:
        return False
    try:
        k, e = Path(kind).resolve(), Path(eltern).resolve()
    except (OSError, ValueError):
        return False
    return k == e or e in k.parents


class Freigaben:
    """Die laufenden Freigaben. Lebt nur im Arbeitsspeicher.

    Absicht: Ein Neustart hebt jede Freigabe auf. Etwas, das einen
    Neustart ueberlebt, ist eine Einstellung und keine Zusage im Gespraech.
    """

    def __init__(self):
        # (werkzeug, ort) -> Ablaufzeitpunkt
        self._offen: dict[tuple[str, str], float] = {}

    # --- erteilen ---------------------------------------------------------

    def erteilbar(self, werkzeug: str) -> bool:
        return werkzeug not in config.FREIGABE_NIE

    def erteilen(self, werkzeug: str, eingabe: dict, minuten: float) -> str:
        """Freigabe eintragen. Gibt den Satz zurueck, der gesagt wird."""
        if not self.erteilbar(werkzeug):
            return ""
        minuten = max(1.0, min(float(minuten), config.FREIGABE_MAX_MINUTEN))
        wo = ort(werkzeug, eingabe)
        self._offen[(werkzeug, wo)] = time.monotonic() + minuten * 60
        return f"{self._benennen(werkzeug, wo)} für {self._dauer(minuten)}"

    # --- pruefen ----------------------------------------------------------

    def erlaubt(self, werkzeug: str, eingabe: dict) -> bool:
        self._aufraeumen()
        wo = ort(werkzeug, eingabe)
        for (w, freigegeben), _ in self._offen.items():
            if w == werkzeug and _unter(wo, freigegeben):
                return True
        return False

    def _aufraeumen(self) -> None:
        jetzt = time.monotonic()
        for schluessel, bis in list(self._offen.items()):
            if bis <= jetzt:
                del self._offen[schluessel]

    def zuruecknehmen(self) -> int:
        """Alles zurueck auf Anfang. Gibt zurueck, wie viele es waren."""
        anzahl = len(self._offen)
        self._offen.clear()
        return anzahl

    # --- zeigen -----------------------------------------------------------

    def offene(self) -> list[tuple[str, float]]:
        """[(Beschreibung, Restminuten)] -- fuer Anzeige und Zustandszeile."""
        self._aufraeumen()
        jetzt = time.monotonic()
        return [
            (self._benennen(w, o), max(0.0, (bis - jetzt) / 60))
            for (w, o), bis in sorted(self._offen.items(), key=lambda x: x[1])
        ]

    def zeile(self) -> str:
        """Die Zeile fuer den Vorspann -- damit auch Sarvis selbst es weiss.

        Ohne sie kann er auf "was darfst du gerade" nur raten, und genau
        das soll er ja nirgends.
        """
        offen = self.offene()
        if not offen:
            return ""
        teile = [f"{was} (noch {rest:.0f} Min.)" for was, rest in offen]
        return ("[Ohne Rückfrage freigegeben: " + "; ".join(teile)
                + ". Läuft von selbst ab; du kannst es nicht verlängern.]")

    def rest_sekunden(self) -> float:
        """Wie lange die laengste laufende Freigabe noch gilt.

        Die Anzeige braucht das, um sich selbst wieder auszublenden. Ohne
        sie stuende dort noch "frei" , wenn laengst wieder gefragt wird --
        und das waere schlimmer als gar keine Anzeige.
        """
        self._aufraeumen()
        if not self._offen:
            return 0.0
        return max(0.0, max(self._offen.values()) - time.monotonic())

    def kurz(self) -> str:
        """Ganz knapp fuer die Anzeige -- dort ist kein Platz fuer Saetze."""
        offen = self.offene()
        if not offen:
            return ""
        was, rest = offen[0]
        mehr = f" +{len(offen) - 1}" if len(offen) > 1 else ""
        return f"frei: {was} · {rest:.0f} min{mehr}"

    # --- Sprache ----------------------------------------------------------

    @staticmethod
    def _benennen(werkzeug: str, wo: str) -> str:
        from . import schutz
        name = config.FREIGABE_NAMEN.get(werkzeug, werkzeug.replace("_", " "))
        if not wo:
            return name
        return f"{name} in {schutz.sprechbar(wo, 'dativ')}"

    @staticmethod
    def _dauer(minuten: float) -> str:
        if minuten >= 120:
            return f"{minuten / 60:.0f} Stunden"
        if minuten >= 60:
            return "eine Stunde" if minuten < 90 else "anderthalb Stunden"
        return f"{minuten:.0f} Minuten"
