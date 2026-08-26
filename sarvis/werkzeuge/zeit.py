"""Timer und Wecker.

Das erste Werkzeug -- und ausgerechnet das erzwingt die interessanteste
Faehigkeit: Ein Timer, der ablaeuft, muss sich von selbst melden. Bis hier
konnte Sarvis nur reden, wenn er gefragt wurde. Der Weg dafuer entsteht
hier und traegt spaeter auch laengere Auftraege ("...und such mir
waehrenddessen die Nachrichten raus").
"""
import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from claude_agent_sdk import tool

from .. import config


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
    laufende: dict = field(default_factory=dict)
    _naechste_nummer: int = 1

    def stellen(self, sekunden: int, was: str) -> tuple[int, datetime]:
        return self.stellen_bis(datetime.now() + timedelta(seconds=sekunden), was)

    def stellen_bis(self, faellig: datetime, was: str) -> tuple[int, datetime]:
        """Auf einen festen Zeitpunkt stellen.

        Fuer genannte Uhrzeiten der genauere Weg: Der Umweg ueber eine
        Dauer schneidet zweimal Nachkommastellen ab und landet dadurch
        rund eine Sekunde zu frueh.
        """
        nummer = self._naechste_nummer
        self._naechste_nummer += 1

        aufgabe = asyncio.get_running_loop().create_task(self._warten(nummer))
        self.laufende[nummer] = {"was": was, "faellig": faellig, "aufgabe": aufgabe}
        self._sichern()
        return nummer, faellig

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
                rest = (eintrag["faellig"] - datetime.now()).total_seconds()
                if rest <= 0:
                    break
                await asyncio.sleep(min(1.0, rest))
        except asyncio.CancelledError:
            return

        eintrag = self.laufende.pop(nummer, None)
        self._sichern()
        if eintrag is None:
            return
        was = eintrag["was"]
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

    # --- ueber einen Neustart retten ---------------------------------------

    def _sichern(self) -> None:
        """Timer auf Platte schreiben.

        Ohne das verschwindet ein Timer stillschweigend, sobald Sarvis
        neu startet -- und bei einem Wecker ist genau das der Fehler, den
        man erst merkt, wenn es zu spaet ist.
        """
        try:
            config.TIMER_DATEI.write_text(
                json.dumps(
                    [{"nummer": n, "was": e["was"],
                      "faellig": e["faellig"].isoformat()}
                     for n, e in self.laufende.items()],
                    ensure_ascii=False, indent=1,
                ),
                encoding="utf-8",
            )
        except OSError as e:
            # Frueher stand hier ein stilles pass. Das ist genau der
            # Fehler, den man nie findet: Schlaegt das Schreiben fehl --
            # gesperrte Datei, Virenscanner, zweite Instanz --, bleibt ein
            # abgelaufener Timer in der Datei stehen und wird bei JEDEM
            # Start neu angesagt. Aufhalten soll es Sarvis weiter nicht,
            # aber sichtbar muss es sein.
            print(f"  ! timer.json ließ sich nicht schreiben: {e}")

    async def wiederherstellen(self) -> list[str]:
        """Beim Start: was noch laeuft, wieder scharf machen.

        Gibt die Meldungen zurueck, die Sarvis sagen sollte -- fuer Timer,
        die abgelaufen sind, waehrend er aus war.
        """
        if not config.TIMER_DATEI.exists():
            return []
        try:
            gespeichert = json.loads(config.TIMER_DATEI.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []

        verpasst: list[str] = []
        verworfen = 0
        jetzt = datetime.now()
        for e in gespeichert:
            try:
                faellig = datetime.fromisoformat(e["faellig"])
            except (KeyError, ValueError):
                continue
            was = e.get("was", "")
            if faellig <= jetzt:
                stunden = (jetzt - faellig).total_seconds() / 3600
                if stunden <= config.TIMER_NACHMELDEN_STUNDEN:
                    verpasst.append(
                        f"Dein Timer{' für ' + was if was else ''} ist "
                        "abgelaufen, während ich aus war."
                    )
                else:
                    # Zu alt, um noch eine Nachricht zu sein. Nicht
                    # ansagen, aber auch nicht liegen lassen -- sonst
                    # steht er beim naechsten Start wieder da.
                    verworfen += 1
                    print(f"  (Timer{' für ' + was if was else ''} war vor "
                          f"{stunden:.0f} Stunden fällig -- nicht mehr angesagt)")
                continue
            self.stellen(int((faellig - jetzt).total_seconds()), was)

        # Auch das stille Wegraeumen muss auf die Platte: Ohne das taucht
        # ein zu alter Timer bei jedem Start erneut auf und wird jedes Mal
        # aufs Neue verworfen.
        if verpasst or verworfen:
            self._sichern()
        return verpasst

    def alle(self) -> list[dict]:
        jetzt = datetime.now()
        return [
            {"nummer": n, "was": e["was"],
             "rest": max(0, int((e["faellig"] - jetzt).total_seconds()))}
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

    @tool(
        "timer_stellen",
        "Stellt einen Timer, der von selbst Bescheid sagt. Entweder eine "
        "Dauer ab jetzt (sekunden) ODER eine feste Uhrzeit (uhrzeit) angeben, "
        "nicht beides. Bei einer genannten Uhrzeit immer 'uhrzeit' benutzen "
        "und die Dauer NICHT selbst ausrechnen.",
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
                    "maximum": 86400,
                },
                "uhrzeit": {
                    "type": "string",
                    "description": "Feste Uhrzeit als HH:MM oder HH:MM:SS, für "
                                   "'um halb neun'. Liegt sie heute schon in "
                                   "der Vergangenheit, gilt morgen.",
                    "pattern": r"^\d{1,2}:\d{2}(:\d{2})?$",
                },
                "wofuer": {
                    "type": "string",
                    "description": "Wofür der Timer ist, kurz. Wird beim "
                                   "Ablaufen vorgelesen, z. B. 'die Nudeln'.",
                },
            },
        },
    )
    async def timer_stellen(args):
        wofuer = (args.get("wofuer") or "").strip()
        roh = (args.get("uhrzeit") or "").strip()

        if roh:
            # Die Umrechnung gehoert hierher, nicht ins Modell. Sarvis hat
            # "Timer auf 8:29:30" aus einer Uhrzeit ohne Sekunden selbst
            # ausgerechnet und lag eine Minute daneben. Code rechnet genau.
            teile = roh.split(":")
            try:
                stunde, minute = int(teile[0]), int(teile[1])
                sekunde = int(teile[2]) if len(teile) > 2 else 0
                jetzt = datetime.now()
                ziel = jetzt.replace(hour=stunde, minute=minute,
                                     second=sekunde, microsecond=0)
            except (ValueError, IndexError):
                return {"content": [{"type": "text", "text":
                        f"Mit der Uhrzeit {roh!r} kann ich nichts anfangen."}],
                        "is_error": True}
            if ziel <= jetzt:
                ziel += timedelta(days=1)   # heute vorbei -> morgen
            sekunden = int(round((ziel - jetzt).total_seconds()))
            nummer, faellig = wecker.stellen_bis(ziel, wofuer)
        elif args.get("sekunden") is not None:
            sekunden = int(args["sekunden"])
            nummer, faellig = wecker.stellen(sekunden, wofuer)
        else:
            return {"content": [{"type": "text", "text":
                    "Ich brauche entweder eine Dauer oder eine Uhrzeit."}],
                    "is_error": True}

        leuchten()
        vermerken(f"timer_stellen: Timer {nummer}"
                  + (f" für {wofuer}" if wofuer else "")
                  + f", fällig um {faellig.strftime('%H:%M:%S')} Uhr — läuft.")
        return {"content": [{"type": "text", "text":
                f"Timer {nummer} läuft: {_dauer_sagen(sekunden)}"
                + (f" für {wofuer}" if wofuer else "")
                + f", fällig um {faellig.strftime('%H:%M:%S')} Uhr."}]}

    @tool(
        "timer_liste",
        "Zeigt alle laufenden Timer mit Restzeit. Benutze das, wenn gefragt "
        "wird, wie lange noch, oder was gerade läuft.",
        {"type": "object", "properties": {}},
    )
    async def timer_liste(args):
        offen = wecker.alle()
        leuchten()
        if not offen:
            return {"content": [{"type": "text", "text": "Es läuft kein Timer."}]}
        zeilen = [
            f"Timer {t['nummer']}"
            + (f" ({t['was']})" if t["was"] else "")
            + f": noch {_dauer_sagen(t['rest'])}"
            for t in offen
        ]
        return {"content": [{"type": "text", "text": "\n".join(zeilen)}]}

    @tool(
        "timer_abbrechen",
        "Bricht einen laufenden Timer ab. Die Nummer steht in timer_liste.",
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
