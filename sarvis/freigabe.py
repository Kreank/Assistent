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
import time
from pathlib import Path

from . import config

# Woraus sich der Ort einer Anfrage ergibt. Werkzeuge, die hier nicht
# stehen, haben keinen Ort -- ihre Freigabe gilt fuer das Werkzeug als
# solches.
# ordner_durchsuchen gehoert dazu, seit gemessen wurde, was sein Fehlen
# anrichtet: ort() lieferte "", die Freigabe wurde ortlos eingetragen --
# und ortlos heisst laut _unter() UEBERALL. Ein "ja, such hier eine
# halbe Stunde lang" gab damit auch D:\Strato Server frei.
_PFAD_WERKZEUGE = ("datei_lesen", "datei_schreiben", "ordner_ansehen",
                   "ordner_durchsuchen")

# Werkzeuge, die statt eines Pfades ein PROJEKT nennen. Ihr Ort ist der
# Projektordner -- wer einen Auftrag im Projekt X freigibt, meint das
# Projekt, nicht diesen einen Auftragstext.
_PROJEKT_WERKZEUGE = ("auftrag_geben", "projekt_oeffnen")


def _pfade_im_befehl(befehl: str) -> list[str]:
    """Alle Pfade eines Befehls -- dieselbe Sammlung wie in schutz.py.

    Es gab zwei Fassungen davon, und sie waren sich nicht einig: Hier
    wurde die Git-Bash-Form "/d/..." erkannt, in schutz.befehl_stufe
    nicht. Wo zwei Stellen dieselbe Frage verschieden beantworten, faellt
    frueher oder spaeter etwas zwischen sie -- gemessen ist es das
    schon, in beide Richtungen.
    """
    from . import schutz
    return schutz.pfade_im_befehl(befehl)


def _pfad_im_befehl(befehl: str) -> str:
    """Der erste Pfad in einem Befehl -- auch in Git-Bash-Schreibweise."""
    pfade = _pfade_im_befehl(befehl)
    return pfade[0] if pfade else ""


def _ordner(pfad: str) -> str:
    """Der Ordner zu einem Pfad -- bei einer Datei der darueber."""
    if not pfad:
        return ""
    try:
        p = Path(pfad)
        # Ein vorhandener Ordner ist selbst der Ort. Sonst waere der Ort
        # von "D:\Mitra" das Laufwerk D -- viel zu weit.
        return str((p if p.is_dir() else p.parent).resolve())
    except (OSError, ValueError):
        return ""


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
    elif werkzeug in _PROJEKT_WERKZEUGE:
        # Diese Werkzeuge nennen kein Pfad-, sondern ein Projektfeld.
        # Ohne diese Zeile war ihr Ort leer -- und ortlos heisst: keine
        # Freigabe moeglich, also bei jedem Versuch neu fragen. Genau das
        # ist am 2. September passiert, als ein Auftrag sieben Mal
        # scheiterte und sieben Mal einzeln bestaetigt werden musste.
        from .werkzeuge.projekte import _finden
        ordner, _ = _finden(str(e.get("projekt") or ""))
        pfad = str(ordner) if ordner else ""
    elif werkzeug == "befehl_ausfuehren":
        befehl = str(e.get("befehl") or "")
        pfad = _pfad_im_befehl(befehl)
        if not pfad:
            # "docker compose up" nennt keinen Pfad -- ortlos ist er
            # deshalb aber nicht: Er laeuft im Arbeitsordner der Shell.
            # Ohne diese Zeile war eine Freigabe fuer ein Projekt eine
            # leere Zusage. Gemessen an einem Docker-Projekt: erteilt,
            # angesagt, und trotzdem bei jedem der vier folgenden
            # Befehle wieder gefragt.
            from . import schutz
            return schutz.arbeitsordner()
    return _ordner(pfad)


def _befehl_ganz_unter(befehl: str, freigegeben: str) -> bool:
    """Liegt JEDER Pfad des Befehls unter dem freigegebenen Ort?

    ort() nimmt den ersten Pfad -- fuer das Eintragen reicht das, fuer
    das Pruefen nicht: 'Get-Content D:\\Privat\\Sarvis\\notiz.txt;
    Get-Content "D:\\Strato Server\\pw.txt"' bekam den Ort des ersten
    zugewiesen und lief unter einer Freigabe fuer den Projektordner ohne
    eine einzige Rueckfrage durch -- gemessen, samt Passwortdatei.
    Ein Befehl ganz ohne Pfad wird am Arbeitsordner der Shell gemessen
    -- dort landet er ja. Frueher fiel er hier durch, mit der
    Begruendung, ein Ort muesse erkennbar sein. Erkennbar ist er, nur
    steht er nicht im Befehl: Gemessen liefen genau die Startbefehle
    ("docker compose up", "npm run start", "ng serve") in diese Luecke
    und fragten trotz laufender Freigabe jedes Mal erneut.
    """
    pfade = _pfade_im_befehl(befehl)
    if not pfade:
        from . import schutz
        return _unter(schutz.arbeitsordner(), freigegeben)
    return all(_unter(_ordner(p), freigegeben) for p in pfade)


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
        # Ein Werkzeug, das einen Pfad oder Befehl mitbringt, dessen Ort
        # sich aber nicht bestimmen laesst, bekommt gar keine Freigabe.
        # Sonst entstuende genau das, was hier nie entstehen soll: ein
        # ortloser Eintrag, der ueberall gilt -- so geschehen, weil ein
        # Werkzeug in _PFAD_WERKZEUGE fehlte. Lieber einmal zu oft
        # gefragt als eine halbe Stunde lang die ganze Platte frei.
        e = eingabe or {}
        if not wo and (e.get("pfad") or e.get("befehl")):
            return ""
        self._offen[(werkzeug, wo)] = time.monotonic() + minuten * 60
        return f"{self._benennen(werkzeug, wo)} für {self._dauer(minuten)}"

    # --- pruefen ----------------------------------------------------------

    def erlaubt(self, werkzeug: str, eingabe: dict) -> bool:
        self._aufraeumen()
        wo = ort(werkzeug, eingabe)
        for (w, freigegeben), _ in self._offen.items():
            if w != werkzeug:
                continue
            # Ein Befehl hat nicht EINEN Ort, sondern so viele, wie er
            # Pfade nennt -- und eine Freigabe deckt ihn nur, wenn sie
            # alle deckt.
            if werkzeug == "befehl_ausfuehren" and freigegeben:
                if _befehl_ganz_unter(str((eingabe or {}).get("befehl") or ""),
                                      freigegeben):
                    return True
                continue
            if _unter(wo, freigegeben):
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

    def anzeige_stand(self) -> tuple[str, float]:
        """Text und Restsekunden fuer die Anzeige -- aus DERSELBEN Freigabe.

        Vorher waren das zwei Aufrufe, und sie meinten zwei verschiedene
        Freigaben: der Text die zuerst ablaufende, der Zaehler den Rest
        der laengsten. Bei "Dateien lesen 5 Minuten" neben "Befehle
        ausfuehren 60 Minuten" stand "frei: Dateien lesen in X · 5 min",
        nachdem genau die schon abgelaufen war -- die Anzeige blendete
        erst mit der langen aus. Ein Zaehler, der etwas anderes meint als
        die Zeile darueber, ist schlimmer als keiner.
        """
        self._aufraeumen()
        if not self._offen:
            return "", 0.0
        (w, o), bis = min(self._offen.items(), key=lambda x: x[1])
        rest = max(0.0, bis - time.monotonic())
        mehr = f" +{len(self._offen) - 1}" if len(self._offen) > 1 else ""
        return f"frei: {self._benennen(w, o)} · {rest / 60:.0f} min{mehr}", rest

    # --- Sprache ----------------------------------------------------------

    @staticmethod
    def _benennen(werkzeug: str, wo: str) -> str:
        from . import schutz
        name = config.FREIGABE_NAMEN.get(werkzeug, werkzeug.replace("_", " "))
        if not wo:
            return name
        return f"{name} in {schutz.sprechbar(wo, 'dativ')}"

    # Dieselben Wortformen braucht auch die Rueckfrage, wenn sie die
    # Freigabe anbietet -- sonst kuendigt sie etwas anderes an, als
    # hinterher gilt.
    @staticmethod
    def wo_lang(wo: str) -> str:
        from . import schutz
        return schutz.sprechbar(wo, "dativ") if wo else "das"

    @staticmethod
    def dauer_lang(minuten: float) -> str:
        return Freigaben._dauer(minuten)

    @staticmethod
    def _dauer(minuten: float) -> str:
        if minuten >= 120:
            return f"{minuten / 60:.0f} Stunden"
        if minuten >= 60:
            return "eine Stunde" if minuten < 90 else "anderthalb Stunden"
        return f"{minuten:.0f} Minuten"
