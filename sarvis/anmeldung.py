"""Ist Sarvis' Kopf angemeldet? -- und was zu tun ist, wenn nicht.

WARUM ES DAS GIBT

Am 30.08.2026 lief Sarvis vier Stunden lang und antwortete auf jeden
Zuruf mit "Failed to authenticate: OAuth session expired and could not
be refreshed". Auf Englisch, mitten in einem deutschen Gespraech, ohne
einen Hinweis, was zu tun ist. Gemerkt hat es Sascha beim Ausprobieren.

Der Fehler dahinter war meiner: Ich hatte die Anmeldung von Saschas
Claude-Code-Sitzung KOPIERT, statt Sarvis eine eigene zu geben. Das
haelt nicht, und zwar aus einem Grund, der sich nicht wegkonfigurieren
laesst: **Ein Refresh-Token gilt fuer genau eine Einloesung.** Wer
zuerst erneuert, macht die Kopie des anderen ungueltig. Zwei Prozesse
auf einer Anmeldung sind also nicht "riskant", sondern eine Zeitbombe
mit bekannter Zuendzeit.

DER RICHTIGE WEG ist ein eigenes, langlebiges Token:

    docker compose exec sarvis claude setup-token

Das fragt einmal nach einer Anmeldung im Browser und haelt danach.

WAS DIESE DATEI TUT

Sie verhindert den Ausfall nicht -- ein Token kann zurueckgezogen
werden, ein Abo auslaufen, ein Dienst stillstehen. Sie sorgt dafuer,
dass man es SOFORT sieht statt beim naechsten Ausprobieren:

  beim Start        eine deutliche Zeile mit dem Befehl zum Beheben
  im Betrieb        eine deutsche Meldung statt einer englischen
                    Ausnahme -- und in der Anzeige, nicht nur im Log

Das ist der eigentliche Unterschied im Produktivbetrieb. Nicht dass
nichts kaputtgeht, sondern dass Kaputtes sich meldet.
"""
import asyncio
import json
import subprocess

# Wie lange auf die Auskunft gewartet wird. Sie kostet normalerweise
# Millisekunden; laenger als das heisst, dass etwas anderes klemmt, und
# dann soll der Start nicht daran haengen.
FRIST = 15.0

# Woran ein Anmeldefehler zu erkennen ist. Absichtlich mehrere Muster:
# Die Meldung kommt aus der CLI und kann sich mit ihr aendern, und ein
# Anmeldefehler, den wir nicht erkennen, faellt zurueck in genau das
# Verhalten, gegen das diese Datei gebaut ist.
MUSTER = (
    "failed to authenticate",
    "oauth",
    "session expired",
    "not logged in",
    "unauthorized",
    "401",
    "invalid api key",
    "authentication_error",
)

RAT = (
    "Sarvis' Zugang zu Claude gilt nicht mehr. Ein Token holen:\n"
    "      docker compose exec sarvis claude setup-token\n"
    "    danach: docker compose restart"
)


def _status_lesen() -> dict:
    """`claude auth status` als Verzeichnis, oder leer."""
    try:
        fertig = subprocess.run(["claude", "auth", "status"],
                                capture_output=True, text=True, timeout=FRIST)
        return json.loads(fertig.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


async def pruefen() -> tuple[bool, str]:
    """(angemeldet, was man dazu sagen kann).

    Laeuft in einem Faden: Es ist ein Unterprozess, und der gehoert
    nicht in die Ereignisschleife, die gleichzeitig ein Gespraech
    traegt.

    Bei Zweifel WAHR: Wer nicht sicher weiss, dass die Anmeldung fehlt,
    soll den Start nicht mit einer Warnung verstellen, die vielleicht
    falsch ist. Der echte Fehler faellt beim ersten Zuruf ohnehin auf --
    dann aber mit verstaendlichem Text (siehe klingt_nach_anmeldung).
    """
    d = await asyncio.to_thread(_status_lesen)
    if not d:
        return True, "Anmeldung nicht pruefbar (claude auth status)"
    if d.get("loggedIn"):
        art = d.get("authMethod") or "?"
        return True, f"angemeldet ({art})"
    return False, "NICHT ANGEMELDET"


def klingt_nach_anmeldung(fehler) -> bool:
    """Ist dieser Fehler ein Anmeldeproblem?"""
    text = f"{type(fehler).__name__}: {fehler}".lower()
    return any(m in text for m in MUSTER)


def satz() -> str:
    """Was Sarvis dazu SAGT -- gesprochen, nicht als Fehlermeldung.

    Auf Deutsch und ohne Fachwort: Wer gerade mit ihm redet, will
    wissen, was los ist, nicht welche Ausnahme geflogen ist. Der Befehl
    steht im Log, nicht im gesprochenen Satz -- niemand tippt etwas ab,
    das er gehoert hat.
    """
    return ("Mein Zugang zu Claude gilt nicht mehr. Ich kann gerade nicht "
            "denken. Im Protokoll steht, wie du mich wieder anmeldest.")
