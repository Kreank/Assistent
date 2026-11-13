"""Timer und Wecker.

Das erste Werkzeug -- und ausgerechnet das erzwingt die interessanteste
Faehigkeit: Ein Timer, der ablaeuft, muss sich von selbst melden. Bis hier
konnte Sarvis nur reden, wenn er gefragt wurde. Der Weg dafuer entsteht
hier und traegt spaeter auch laengere Auftraege ("...und such mir
waehrenddessen die Nachrichten raus").
"""
import asyncio
import calendar
import re
import json
import time
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from claude_agent_sdk import tool

from .. import config
# Mitbenutzt statt nachgebaut: Zwei Fassungen desselben Kniffs driften
# auseinander, und beim Wecker faellt das erst auf, wenn er nicht klingelt.
# Der saubere Platz waere ein eigenes kleines Dateimodul.
from .auftrag import _atomar_schreiben


def _jetzt_wie(faellig: datetime) -> datetime:
    """Die Vergleichszeit so beschaffen wie der gespeicherte Zeitpunkt.

    Dauer-Timer haengen an einem absoluten Zeitpunkt (mit Zeitversatz),
    Uhrzeit-Timer an der Wanduhr (ohne). Beides gegeneinander zu
    vergleichen wirft TypeError -- und in timer.json koennen nach einem
    Update beide Sorten nebeneinander stehen.
    """
    if faellig.tzinfo is not None:
        return datetime.now(faellig.tzinfo)
    return datetime.now()


def _dauer_sagen(sekunden: int) -> str:
    """600 -> 'zehn Minuten'. Wird vorgelesen, also ausgeschrieben."""
    zahlen = {
        1: "eine", 2: "zwei", 3: "drei", 4: "vier", 5: "fünf", 6: "sechs",
        7: "sieben", 8: "acht", 9: "neun", 10: "zehn", 11: "elf", 12: "zwölf",
        15: "fünfzehn", 20: "zwanzig", 30: "dreißig", 45: "fünfundvierzig",
    }
    if sekunden < 60:
        n = zahlen.get(sekunden, str(sekunden))
        return f"{n} Sekunde" + ("" if sekunden == 1 else "n")
    minuten, rest = divmod(sekunden, 60)
    if minuten < 60:
        n = zahlen.get(minuten, str(minuten))
        text = f"{n} Minute" + ("" if minuten == 1 else "n")
        if rest:
            text += f" und {_dauer_sagen(rest)}"
        return text
    stunden, minuten = divmod(minuten, 60)
    # Ab zwei Tagen in TAGEN reden. "Noch 107 Stunden und 18 Minuten"
    # ist woertlich richtig und trotzdem unbrauchbar -- niemand rechnet
    # das im Kopf in "übernächsten Montag" um, und vorgelesen ist es
    # eine Zumutung. Erst seit Erinnerungen ueber 24 Stunden hinaus
    # moeglich sind, kommen solche Zahlen ueberhaupt vor.
    if stunden >= 48:
        tage, reststunden = divmod(stunden, 24)
        n = zahlen.get(tage, str(tage))
        text = f"{n} Tage"
        # Die Stunden nur, wenn sie ins Gewicht fallen. "Sieben Tage und
        # eine Stunde" hilft niemandem.
        if reststunden >= 2:
            text += f" und {_dauer_sagen(reststunden * 3600)}"
        return text
    n = zahlen.get(stunden, str(stunden))
    text = f"{n} Stunde" + ("" if stunden == 1 else "n")
    if minuten:
        text += f" und {_dauer_sagen(minuten * 60)}"
    return text


@dataclass
class Wecker:
    """Haelt die laufenden Timer und meldet sich, wenn einer faellig ist."""

    sagen: callable            # wird gerufen, wenn ein Timer ablaeuft
    leuchten: callable = None  # Werkzeug im Kranz aufleuchten lassen
    melden: callable = None    # Windows-Benachrichtigung (titel, text)
    # Seit 13.11.2026: Eintraege der Sorte "aufgabe" sprechen beim
    # Faelligwerden keinen festen Satz, sondern fuehren einen Auftrag aus
    # (ausfuehren(was, nummer) -- main.py reiht ihn als Zug des Hirns ein).
    # Vorher legte Sarvis Daueraufgaben mit dem eingebauten CronCreate von
    # Claude Code an, und die laufen nach sieben Tagen aus.
    ausfuehren: callable = None
    # Wird nach jeder Aenderung der Liste gerufen (Draht-Art "geplant").
    geaendert: callable = None
    laufende: dict = field(default_factory=dict)
    _naechste_nummer: int = 1

    def stellen(self, sekunden: int, was: str,
                wiederholt: str | None = None,
                sorte: str = "timer") -> tuple[int, datetime]:
        # Eine Dauer meint echte Zeit, keine Wanduhrzeit: astimezone()
        # haelt den Zeitversatz von jetzt fest, dann bleibt "in einer
        # Stunde" auch in der Umstellungsnacht eine Stunde. Bewusst keine
        # monotone Uhr -- die faengt bei jedem Neustart bei null an, und
        # der Timer soll den Neustart ueberleben.
        return self.stellen_bis(
            datetime.now().astimezone() + timedelta(seconds=sekunden), was,
            wiederholt=wiederholt, sorte=sorte)

    def stellen_bis(self, faellig: datetime, was: str,
                    wiederholt: str | None = None, sorte: str = "timer",
                    pausiert: bool = False, zuletzt: float | None = None,
                    nummer: int | None = None) -> tuple[int, datetime]:
        """Auf einen festen Zeitpunkt stellen.

        Fuer genannte Uhrzeiten der genauere Weg: Der Umweg ueber eine
        Dauer schneidet zweimal Nachkommastellen ab und landet dadurch
        rund eine Sekunde zu frueh.

        nummer: nur beim Neustellen eines wiederkehrenden Eintrags und
        beim Wiederherstellen. Die Nummer bleibt dann dieselbe -- die App
        loescht und pausiert ueber sie, und eine Nummer, die nach jedem
        Klingeln wechselt, ist als Griff nichts wert.
        """
        if nummer is None:
            nummer = self._naechste_nummer
        self._naechste_nummer = max(self._naechste_nummer, nummer + 1)

        aufgabe = asyncio.get_running_loop().create_task(self._warten(nummer))
        self.laufende[nummer] = {"was": was, "faellig": faellig,
                                 "aufgabe": aufgabe, "wiederholt": wiederholt,
                                 "sorte": sorte if sorte == "aufgabe" else "timer",
                                 "pausiert": bool(pausiert),
                                 "zuletzt": zuletzt}
        self._sichern()
        return nummer, faellig

    @staticmethod
    def _naechster_termin(faellig: datetime, wiederholt: str) -> datetime:
        """Wann klingelt ein wiederkehrender Timer das naechste Mal?

        Gerechnet wird auf der WANDUHR, nicht in Sekunden: "jeden Morgen
        um sieben" bleibt sieben Uhr, auch in der Nacht der Zeitumstellung.
        86400 Sekunden dazuzuzaehlen ergaebe dort sechs oder acht.

        Monatlich am 31. gibt es nicht in jedem Monat. Statt den Termin
        auf den 1. des uebernaechsten rutschen zu lassen -- was ihn
        stillschweigend verschoebe -- wird auf den letzten Tag des
        Zielmonats gelegt. Wer "jeden Monat zum Abschluss" sagt, meint
        das Monatsende, nicht den Ersten.
        """
        if wiederholt == "taeglich":
            return faellig + timedelta(days=1)
        if wiederholt == "woechentlich":
            return faellig + timedelta(days=7)
        if wiederholt == "monatlich":
            jahr, monat = faellig.year, faellig.month + 1
            if monat > 12:
                jahr, monat = jahr + 1, 1
            letzter = calendar.monthrange(jahr, monat)[1]
            return faellig.replace(year=jahr, month=monat,
                                   day=min(faellig.day, letzter))
        return faellig + timedelta(days=1)

    async def _warten(self, nummer: int) -> None:
        """Wartet gegen die Wanduhr, nicht gegen eine Dauer.

        asyncio.sleep(600) waere zehn Minuten Prozesslaufzeit. Geht der PC
        dazwischen schlafen, tickt diese Uhr nicht weiter und der Timer
        klingelt um die Schlafdauer zu spaet. Deshalb sekundenweise gegen
        die echte Uhrzeit pruefen.
        """
        try:
            while True:
                eintrag = self.laufende.get(nummer)
                if eintrag is None:
                    return
                faellig = eintrag["faellig"]
                rest = (faellig - _jetzt_wie(faellig)).total_seconds()
                if rest <= 0:
                    # Ein pausierter EINMALIGER Eintrag wartet, bis er
                    # wieder an ist -- dann kommt er sofort. Ein
                    # wiederkehrender ueberspringt nur diesen Termin.
                    if eintrag.get("pausiert") and not eintrag.get("wiederholt"):
                        await asyncio.sleep(1.0)
                        continue
                    break
                await asyncio.sleep(min(1.0, rest))
        except asyncio.CancelledError:
            return

        eintrag = self.laufende.pop(nummer, None)
        if eintrag is None:
            self._sichern()
            return
        was = eintrag["was"]
        sorte = eintrag.get("sorte") or "timer"
        pausiert = bool(eintrag.get("pausiert"))
        zuletzt = eintrag.get("zuletzt") if pausiert else time.time()

        # Wiederkehrend? Dann sofort den naechsten stellen, noch bevor
        # gesprochen wird. Erst zu reden und dann neu zu stellen hiesse:
        # Wer den Prozess in diesen Sekunden neu startet, hat den
        # wiederkehrenden Timer verloren -- und merkt es erst, wenn er
        # das naechste Mal nicht klingelt.
        wiederholt = eintrag.get("wiederholt")
        if wiederholt:
            self.stellen_bis(
                self._naechster_termin(eintrag["faellig"], wiederholt),
                was, wiederholt=wiederholt, sorte=sorte, pausiert=pausiert,
                zuletzt=zuletzt, nummer=nummer)
        else:
            self._sichern()
        if pausiert:
            print(f"  (Geplant {nummer} pausiert -- Termin übersprungen)")
            return
        if sorte == "aufgabe" and self.ausfuehren is not None:
            # Kein Satz, sondern ein Zug: Das Hirn bekommt den Auftrag,
            # als haette Sascha ihn gerade gesagt. Gesprochen und gezeigt
            # wird, was dabei herauskommt.
            try:
                await self.ausfuehren(was, nummer)
            except Exception as e:
                print(f"  ! Geplante Aufgabe {nummer} nicht ausgeführt: {e}")
            return
        # Erst die Benachrichtigung, dann die Stimme: Die Benachrichtigung
        # bleibt stehen, falls gerade niemand am Rechner sitzt.
        if self.melden is not None:
            # Titel fett, Text darunter -- so ist die Meldung auf einen
            # Blick lesbar, ohne dass sich beides wiederholt.
            # Kein capitalize(): das macht aus "den Müll" ein "den müll".
            self.melden(
                "Timer abgelaufen",
                (was[0].upper() + was[1:]) if was else "Die Zeit ist um.",
            )
        await self.sagen(
            f"Dein Timer ist abgelaufen: {was}." if was
            else "Dein Timer ist abgelaufen."
        )

    def abbrechen(self, nummer: int) -> bool:
        eintrag = self.laufende.pop(nummer, None)
        if eintrag is None:
            return False
        eintrag["aufgabe"].cancel()
        self._sichern()
        return True

    def pausieren(self, nummer: int, an: bool) -> bool:
        """Pausieren heisst: Der Eintrag bleibt, tut aber nichts."""
        eintrag = self.laufende.get(nummer)
        if eintrag is None:
            return False
        eintrag["pausiert"] = bool(an)
        self._sichern()
        return True

    def liste(self) -> list[dict]:
        """Fuer GET /geplant und die Draht-Art "geplant" (DRAHT.md)."""
        aus = []
        for n, e in sorted(self.laufende.items()):
            try:
                faellig = e["faellig"].timestamp()
            except (OSError, ValueError, OverflowError):
                faellig = 0.0
            aus.append({"nummer": n, "sorte": e.get("sorte") or "timer",
                        "was": e["was"], "faellig": faellig,
                        "wiederholt": e.get("wiederholt"),
                        "pausiert": bool(e.get("pausiert")),
                        "zuletzt": e.get("zuletzt")})
        return aus

    # --- ueber einen Neustart retten ---------------------------------------

    def _sichern(self) -> None:
        """Timer auf Platte schreiben.

        Ohne das verschwindet ein Timer stillschweigend, sobald Sarvis
        neu startet -- und bei einem Wecker ist genau das der Fehler, den
        man erst merkt, wenn es zu spaet ist.
        """
        try:
            # Ueber eine Nebendatei, nicht in die echte hinein: Wer den
            # Prozess zwischen dem Kuerzen auf null Bytes und dem
            # Schreiben abschiesst, hinterliess sonst eine halbe Datei --
            # und die kostet beim naechsten Start alle Timer auf einmal.
            _atomar_schreiben(
                config.TIMER_DATEI,
                json.dumps(
                    [{"nummer": n, "was": e["was"],
                      "faellig": e["faellig"].isoformat(),
                      # Ohne dieses Feld ueberlebt ein wiederkehrender
                      # Timer den ersten Neustart als EINMALIGER -- er
                      # klingelt noch einmal und ist dann still. Das
                      # faellt erst in der Woche darauf auf.
                      "wiederholt": e.get("wiederholt"),
                      "sorte": e.get("sorte") or "timer",
                      "pausiert": bool(e.get("pausiert")),
                      "zuletzt": e.get("zuletzt")}
                     for n, e in self.laufende.items()],
                    ensure_ascii=False, indent=1,
                ),
            )
        except OSError as e:
            # Frueher stand hier ein stilles pass. Das ist genau der
            # Fehler, den man nie findet: Schlaegt das Schreiben fehl --
            # gesperrte Datei, Virenscanner, zweite Instanz --, bleibt ein
            # abgelaufener Timer in der Datei stehen und wird bei JEDEM
            # Start neu angesagt. Aufhalten soll es Sarvis weiter nicht,
            # aber sichtbar muss es sein.
            print(f"  ! timer.json ließ sich nicht schreiben: {e}")
        if self.geaendert is not None:
            try:
                self.geaendert()
            except Exception as e:
                print(f"  (Geplant-Liste nicht gemeldet -- {e})")

    async def wiederherstellen(self) -> list[str]:
        """Beim Start: was noch laeuft, wieder scharf machen.

        Gibt die Meldungen zurueck, die Sarvis sagen sollte -- fuer Timer,
        die abgelaufen sind, waehrend er aus war.
        """
        if not config.TIMER_DATEI.exists():
            return []
        try:
            gespeichert = json.loads(config.TIMER_DATEI.read_text(encoding="utf-8"))
            if not isinstance(gespeichert, list):
                raise ValueError("kein JSON-Array")
        except (OSError, ValueError) as e:
            # Frueher stand hier ein stilles []. Das ist derselbe Fehler
            # wie ein stilles pass beim Schreiben, nur teurer: Sarvis
            # haelt danach fest, dass kein Timer laeuft, und der Wecker
            # klingelt nie. Die kaputte Datei wird beiseitegelegt, sonst
            # ueberschreibt sie das naechste Sichern.
            print(f"  ! timer.json unlesbar -- keine Timer wiederhergestellt: {e}")
            try:
                config.TIMER_DATEI.replace(
                    config.TIMER_DATEI.with_name(config.TIMER_DATEI.name + ".kaputt"))
            except OSError:
                pass
            return ["Meine Timerliste war beim Start unlesbar. Falls du einen "
                    "Wecker gestellt hattest, ist er weg."]

        verpasst: list[str] = []
        verworfen = 0
        for e in gespeichert:
            try:
                faellig = datetime.fromisoformat(e["faellig"])
            except (KeyError, TypeError, ValueError):
                continue
            was = e.get("was", "")
            sorte = e.get("sorte") or "timer"
            mehr = {"sorte": sorte, "pausiert": bool(e.get("pausiert")),
                    "zuletzt": e.get("zuletzt")}
            try:
                mehr["nummer"] = int(e["nummer"])
            except (KeyError, TypeError, ValueError):
                pass
            if mehr.get("nummer") in self.laufende:
                mehr.pop("nummer")
            jetzt = _jetzt_wie(faellig)
            if faellig <= jetzt:
                stunden = (jetzt - faellig).total_seconds() / 3600
                if mehr["pausiert"]:
                    pass
                elif stunden <= config.TIMER_NACHMELDEN_STUNDEN:
                    verpasst.append(
                        (f"Die geplante Aufgabe „{was[:80]}“ ist ausgefallen, "
                         "während ich aus war." if sorte == "aufgabe" else
                         f"Dein Timer{' für ' + was if was else ''} ist "
                         "abgelaufen, während ich aus war.")
                    )
                else:
                    # Zu alt, um noch eine Nachricht zu sein. Nicht
                    # ansagen, aber auch nicht liegen lassen -- sonst
                    # steht er beim naechsten Start wieder da.
                    verworfen += 1
                    print(f"  (Timer{' für ' + was if was else ''} war vor "
                          f"{stunden:.0f} Stunden fällig -- nicht mehr angesagt)")
                # Ein WIEDERKEHRENDER Timer darf nicht mit seinem
                # verpassten Termin sterben. "Jeden Montag" heisst jeden
                # Montag, auch wenn Sarvis an einem davon aus war --
                # sonst raeumt ein Wochenende ohne Server die Erinnerung
                # stillschweigend ab.
                wdh = e.get("wiederholt")
                if wdh:
                    naechster = faellig
                    while naechster <= jetzt:
                        naechster = self._naechster_termin(naechster, wdh)
                    self.stellen_bis(naechster, was, wiederholt=wdh, **mehr)
                elif mehr["pausiert"]:
                    # Pausiert und einmalig: bleibt liegen, bis er wieder
                    # an ist (siehe _warten).
                    self.stellen_bis(faellig, was, **mehr)
                continue
            # Direkt auf den gespeicherten Zeitpunkt, nicht ueber eine
            # Dauer: Der Umweg schneidet Nachkommastellen ab und legt
            # einen Wecker auf 06:00:00 bis zu eine Sekunde daneben --
            # genau deshalb gibt es stellen_bis.
            self.stellen_bis(faellig, was, wiederholt=e.get("wiederholt"),
                             **mehr)

        # Auch das stille Wegraeumen muss auf die Platte: Ohne das taucht
        # ein zu alter Timer bei jedem Start erneut auf und wird jedes Mal
        # aufs Neue verworfen.
        if verpasst or verworfen:
            self._sichern()
        return verpasst

    def alle(self) -> list[dict]:
        return [
            {"nummer": n, "was": e["was"],
             "sorte": e.get("sorte") or "timer",
             "pausiert": bool(e.get("pausiert")),
             "wiederholt": e.get("wiederholt"),
             "rest": max(0, int((e["faellig"]
                                 - _jetzt_wie(e["faellig"])).total_seconds()))}
            for n, e in sorted(self.laufende.items())
        ]


def werkzeuge(wecker: Wecker, protokoll=None) -> list:
    """Die Werkzeuge, die Claude sieht. Beschreibungen sind die halbe Miete:
    daran entscheidet das Modell, ob es sie ueberhaupt greift."""

    def leuchten():
        if wecker.leuchten:
            wecker.leuchten("Timer")

    def vermerken(text: str):
        # Nur bleibende Wirkung -- ein Blick in die Liste aendert nichts.
        if protokoll is not None:
            protokoll.merken(text)

    _WOCHENTAGE = {
        "montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3,
        "freitag": 4, "samstag": 5, "sonnabend": 5, "sonntag": 6,
    }

    def _datum_deuten(roh: str, jetzt: datetime):
        """Aus 'Donnerstag' oder '14.03.' einen Tag machen.

        Die Rechnung gehoert hierher und nicht ins Modell -- aus demselben
        Grund, aus dem die Uhrzeit hier umgerechnet wird: Sarvis hat sich
        beim Selbstrechnen schon einmal um eine Minute vertan, und bei
        einem Datum waere es ein ganzer Tag. Ein Wecker, der einen Tag
        daneben liegt, ist schlimmer als keiner.

        Rueckgabe: (date, Fehlertext).
        """
        roh = " ".join(str(roh or "").split()).lower().strip().rstrip(",")
        if not roh:
            return None, ""

        # "morgen", "uebermorgen" -- kommen gesprochen oft statt eines Datums
        if roh in ("heute",):
            return jetzt.date(), ""
        if roh in ("morgen",):
            return (jetzt + timedelta(days=1)).date(), ""
        if roh in ("uebermorgen", "übermorgen"):
            return (jetzt + timedelta(days=2)).date(), ""

        # Wochentag: immer der NAECHSTE. "Donnerstag" an einem Donnerstag
        # meint den kommenden, nicht heute -- wer heute meint, sagt eine
        # Uhrzeit.
        wort = roh.replace("nächsten", "").replace("naechsten", "").strip()
        if wort in _WOCHENTAGE:
            heute = jetzt.weekday()
            ziel = _WOCHENTAGE[wort]
            vor = (ziel - heute) % 7
            return (jetzt + timedelta(days=vor or 7)).date(), ""

        # TT.MM. oder TT.MM.JJJJ
        t = re.match(r"^(\d{1,2})\.\s*(\d{1,2})\.\s*(\d{2,4})?$", roh)
        if t:
            tag, monat = int(t.group(1)), int(t.group(2))
            jahr = t.group(3)
            if jahr:
                jahr = int(jahr)
                if jahr < 100:
                    jahr += 2000
            else:
                jahr = jetzt.year
            try:
                d = date(jahr, monat, tag)
            except ValueError:
                return None, f"Den {roh} gibt es nicht."
            # Ohne Jahresangabe und schon vorbei: naechstes Jahr gemeint.
            if not t.group(3) and d < jetzt.date():
                try:
                    d = date(jahr + 1, monat, tag)
                except ValueError:
                    return None, f"Den {roh} gibt es nicht."
            return d, ""

        return None, (f"Mit dem Datum {roh!r} kann ich nichts anfangen. "
                      "Sag mir einen Wochentag oder ein Datum wie 14.03.")

    @tool(
        "timer_stellen",
        "Stellt einen Timer oder eine Erinnerung, die von selbst Bescheid "
        "sagt — von 'in zehn Minuten' bis 'Donnerstag früh'. Entweder eine "
        "Dauer ab jetzt (sekunden) ODER eine Uhrzeit angeben, nicht beides. "
        "Bei einer genannten Uhrzeit immer 'uhrzeit' benutzen und die Dauer "
        "NICHT selbst ausrechnen. Für einen anderen Tag zusätzlich 'datum'. "
        "Für 'jeden Montag' oder 'jeden Morgen' zusätzlich 'wiederholt'. "
        "Soll zu der Zeit etwas GETAN werden (Briefing, Nachrichten "
        "zusammenfassen, Wetter nachsehen), den Auftrag in 'auftrag' "
        "schreiben: Dann führst du ihn zu der Zeit selbst aus. Das ist der "
        "einzige Weg für geplante und wiederkehrende Aufgaben; er läuft "
        "nie ab und übersteht Neustarts. Sascha sieht und verwaltet diese "
        "Einträge in der App unter 'Geplant'.",
        {
            "type": "object",
            "properties": {
                "sekunden": {
                    "type": "integer",
                    "description": "Dauer in Sekunden ab jetzt, für 'in zehn "
                                   "Minuten'. Genau die genannte Zeit "
                                   "übernehmen, nicht in eine plausiblere "
                                   "Einheit umrechnen.",
                    "minimum": 5,
                    # Hier stand 86400 -- ein Tag. Damit war "erinnere mich
                    # Donnerstag an den Kessel" schlicht unmoeglich, und
                    # das ist die haeufigste Bitte an einen Assistenten
                    # ueberhaupt. Der Wecker selbst konnte es immer: Er
                    # rechnet mit festen Zeitpunkten, sichert auf Platte
                    # und stellt sich nach einem Neustart wieder scharf.
                    # Nur der Weg dorthin war zugemauert. Ein Jahr ist
                    # jetzt die Grenze, und die ist nur noch da, damit ein
                    # verhoertes "in dreissig" nicht dreissig Jahre wird.
                    "maximum": 31_536_000,
                },
                "uhrzeit": {
                    "type": "string",
                    "description": "Feste Uhrzeit als HH:MM oder HH:MM:SS, für "
                                   "'um halb neun'. Ohne datum gilt: heute, "
                                   "und wenn heute schon vorbei, morgen.",
                    "pattern": r"^\d{1,2}:\d{2}(:\d{2})?$",
                },
                "datum": {
                    "type": "string",
                    "description": "Für einen anderen Tag: 'TT.MM.' oder "
                                   "'TT.MM.JJJJ', oder ein Wochentag "
                                   "('Donnerstag' meint den nächsten). Nur "
                                   "zusammen mit uhrzeit. Ohne genannte "
                                   "Uhrzeit wird es 9 Uhr früh.",
                },
                "wiederholt": {
                    "type": "string",
                    "enum": ["taeglich", "woechentlich", "monatlich"],
                    "description": "Für 'jeden Morgen', 'jeden Montag', "
                                   "'jeden Ersten'. Nach dem Klingeln stellt "
                                   "sich der Timer von selbst neu.",
                },
                "wofuer": {
                    "type": "string",
                    "description": "Wofür der Timer ist, kurz. Wird beim "
                                   "Ablaufen vorgelesen, z. B. 'die Nudeln'.",
                },
                "auftrag": {
                    "type": "string",
                    "description": "Statt einer Erinnerung: was du zu der "
                                   "Zeit tun sollst, als vollständiger, "
                                   "für sich verständlicher Auftrag an dich "
                                   "selbst (Quellen, Form des Ergebnisses). "
                                   "Dann entfällt 'wofuer'.",
                },
            },
        },
    )
    async def timer_stellen(args):
        wofuer = (args.get("wofuer") or "").strip()
        roh = (args.get("uhrzeit") or "").strip()
        rohdatum = (args.get("datum") or "").strip()
        wiederholt = (args.get("wiederholt") or "").strip() or None
        auftrag = (args.get("auftrag") or "").strip()
        sorte = "aufgabe" if auftrag else "timer"
        if auftrag:
            wofuer = auftrag

        tag = None
        if rohdatum:
            tag, fehler = _datum_deuten(rohdatum, datetime.now())
            if tag is None:
                return {"content": [{"type": "text", "text": fehler}],
                        "is_error": True}
            # Ein Datum ohne Uhrzeit meint den Morgen. "Erinnere mich
            # Donnerstag an den Kessel" um Mitternacht zu melden waere
            # zwar woertlich richtig und trotzdem falsch.
            if not roh:
                roh = "09:00"

        if roh:
            # Die Umrechnung gehoert hierher, nicht ins Modell. Sarvis hat
            # "Timer auf 8:29:30" aus einer Uhrzeit ohne Sekunden selbst
            # ausgerechnet und lag eine Minute daneben. Code rechnet genau.
            teile = roh.split(":")
            try:
                stunde, minute = int(teile[0]), int(teile[1])
                sekunde = int(teile[2]) if len(teile) > 2 else 0
                # Bleibt bewusst ohne Zeitversatz: "um sechs" meint die
                # Wanduhr, auch wenn die Nacht dazwischen 23 oder 25
                # Stunden hat. Nur Dauern haengen an der echten Zeit.
                jetzt = datetime.now()
                ziel = jetzt.replace(hour=stunde, minute=minute,
                                     second=sekunde, microsecond=0)
                if tag is not None:
                    ziel = ziel.replace(year=tag.year, month=tag.month,
                                        day=tag.day)
            except (ValueError, IndexError):
                return {"content": [{"type": "text", "text":
                        f"Mit der Uhrzeit {roh!r} kann ich nichts anfangen."}],
                        "is_error": True}
            if ziel <= jetzt:
                if tag is not None:
                    # Ein genanntes Datum wird NICHT stillschweigend
                    # verschoben. Wer "am 14." sagt und den 14. meint,
                    # soll erfahren, dass der vorbei ist -- nicht einen
                    # Wecker fuer morgen bekommen.
                    return {"content": [{"type": "text", "text":
                            f"Der {ziel:%d.%m.%Y um %H:%M} ist vorbei. "
                            "Meinst du nächstes Jahr?"}], "is_error": True}
                ziel += timedelta(days=1)   # heute vorbei -> morgen
            sekunden = int(round((ziel - jetzt).total_seconds()))
            nummer, faellig = wecker.stellen_bis(ziel, wofuer,
                                                 wiederholt=wiederholt,
                                                 sorte=sorte)
        elif args.get("sekunden") is not None:
            sekunden = int(args["sekunden"])
            nummer, faellig = wecker.stellen(sekunden, wofuer,
                                             wiederholt=wiederholt,
                                             sorte=sorte)
        else:
            return {"content": [{"type": "text", "text":
                    "Ich brauche entweder eine Dauer oder eine Uhrzeit."}],
                    "is_error": True}

        # astimezone() rechnet den Zeitpunkt in die dann gueltige Ortszeit
        # um -- sonst nennt ein Dauer-Timer ueber die Umstellung hinweg
        # eine Uhrzeit, die auf keiner Uhr im Haus steht.
        oertlich = faellig.astimezone()
        uhrzeit = oertlich.strftime('%H:%M:%S')
        # Bei allem, was nicht heute ist, gehoert der Tag dazu -- sonst
        # klingt "faellig um 9 Uhr" nach morgen frueh, obwohl Donnerstag
        # gemeint ist.
        wann = (f"am {oertlich:%d.%m.} um {oertlich:%H:%M} Uhr"
                if oertlich.date() != datetime.now().date()
                else f"um {uhrzeit} Uhr")
        wieder = {"taeglich": ", danach täglich",
                  "woechentlich": ", danach wöchentlich",
                  "monatlich": ", danach monatlich"}.get(wiederholt, "")
        leuchten()
        if auftrag:
            vermerken(f"timer_stellen: geplante Aufgabe {nummer}, fällig "
                      f"{wann}{wieder}: {auftrag[:120]}")
            return {"content": [{"type": "text", "text":
                    f"Geplante Aufgabe {nummer} steht: fällig {wann}{wieder}. "
                    "Sie läuft nicht ab."}]}
        vermerken(f"timer_stellen: Timer {nummer}"
                  + (f" für {wofuer}" if wofuer else "")
                  + f", fällig {wann}{wieder} — läuft.")
        return {"content": [{"type": "text", "text":
                f"Timer {nummer} läuft: {_dauer_sagen(sekunden)}"
                + (f" für {wofuer}" if wofuer else "")
                + f", fällig {wann}{wieder}."}]}

    @tool(
        "timer_liste",
        "Zeigt alle laufenden Timer und geplanten Aufgaben mit Restzeit. "
        "Benutze das, wenn gefragt wird, wie lange noch, oder was gerade "
        "läuft oder geplant ist.",
        {"type": "object", "properties": {}},
    )
    async def timer_liste(args):
        offen = wecker.alle()
        leuchten()
        if not offen:
            return {"content": [{"type": "text", "text": "Es läuft kein Timer."}]}
        zeilen = [
            ("Geplante Aufgabe" if t["sorte"] == "aufgabe" else "Timer")
            + f" {t['nummer']}"
            + (f" ({t['was'][:100]})" if t["was"] else "")
            + f": noch {_dauer_sagen(t['rest'])}"
            + ({"taeglich": ", täglich", "woechentlich": ", wöchentlich",
                "monatlich": ", monatlich"}.get(t["wiederholt"] or "", ""))
            + (" — pausiert" if t["pausiert"] else "")
            for t in offen
        ]
        return {"content": [{"type": "text", "text": "\n".join(zeilen)}]}

    @tool(
        "timer_abbrechen",
        "Bricht einen laufenden Timer oder eine geplante Aufgabe ab. Die "
        "Nummer steht in timer_liste.",
        {
            "type": "object",
            "properties": {
                "nummer": {"type": "integer", "description": "Nummer des Timers."}
            },
            "required": ["nummer"],
        },
    )
    async def timer_abbrechen(args):
        leuchten()
        if wecker.abbrechen(int(args["nummer"])):
            vermerken(f"timer_abbrechen: Timer {args['nummer']} wurde gelöscht.")
            return {"content": [{"type": "text", "text": "Timer abgebrochen."}]}
        return {"content": [{"type": "text", "text":
                "Diesen Timer gibt es nicht."}], "is_error": True}

    return [timer_stellen, timer_liste, timer_abbrechen]
