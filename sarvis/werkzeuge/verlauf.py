"""Im eigenen Gespraechsverlauf nachschlagen.

Der Gegenpol zur Verdichtung. Wenn Sarvis sein Gespraech zusammenfasst,
um Platz zu schaffen, verliert er die Einzelheiten -- aber nur im Kopf.
Auf der Platte stehen sie weiter: Das SDK schreibt jede Nachricht in
eine Sitzungsdatei, und das gilt auch fuer alles, was verdichtet wurde.
Geprueft an einer Sitzung nach "/compact": Die Zurufe von vor der
Verdichtung standen unveraendert in der Datei.

Das ist kein Gedaechtnis. Der Unterschied ist wichtig genug fuer einen
eigenen Absatz:

    gedaechtnis/    was Sarvis ueber dich WEISS. Ueberlebt Neustarts,
                    wird bewusst hineingeschrieben, ist zum Lesen
                    gedacht.
    Verlauf         was gesagt WURDE. Faellt an, ist niemandes
                    Entscheidung, und wird nur nachgeschlagen.

Deshalb landet hier auch nichts. Das Werkzeug liest, es schreibt nie.

Fremde Sitzungen bleiben aussen vor: Im selben Ordner liegen die
Sitzungen von Claude Code am Projekt Sarvis. Die tragen die Marke "cli",
Sarvis' eigene "sdk-py" -- geprueft an acht Dateien.
"""
import json
import time
import re
from datetime import datetime

from claude_agent_sdk import tool

from .. import config

# Wie viele Treffer hoechstens zurueckkommen. Der Deckel ist kein
# Schoenheitsfehler, sondern der Zweck: Das Ergebnis geht in denselben
# Kontext zurueck, den das Nachschlagen entlasten soll. Wer dreissig
# Treffer holt, hat die Verdichtung umsonst gemacht.
TREFFER = 6

# Wie lang ein einzelner Treffer sein darf.
LAENGE = 220

# Wie weit zurueck gesucht wird -- in TAGEN, nicht in Dateien.
#
# Hier stand eine Dateizahl (12), und das war der falsche Massstab: Wie
# viele Dateien ein Zeitraum ergibt, haengt nicht am Zeitraum, sondern
# daran, wie oft Sarvis neu gestartet wurde. Gemessen am 2. September:
# 50 Sitzungsdateien aus vier Tagen, allein 30 davon vom 30. August. Mit
# einem Deckel von 12 endete sein Rueckblick nach knapp zwei Tagen --
# und zwar unsichtbar, ohne dass irgendwo "aelter finde ich nichts"
# gestanden haette. Wer neu startet, verkuerzt sein eigenes Gedaechtnis.
#
# Nach Tagen zu rechnen ist das, was ein Mensch meint, wenn er "letzte
# Woche" sagt.
SITZUNGEN_TAGE = 45

# Trotzdem eine Obergrenze, aber eine grosszuegige: Sie soll nur
# verhindern, dass die Suche bei jahrelangem Betrieb minutenlang laeuft.
# 6,9 MB aus vier Tagen sind in Bruchteilen einer Sekunde durchsucht.
SITZUNGEN_HOECHSTENS = 400


def _ist_titelsitzung(datei) -> bool:
    """Die Sitzung, in der Sarvis nur einen Gespraechstitel vergeben hat."""
    try:
        with datei.open(encoding="utf-8") as f:
            for zeile in f:
                if '"type":"user"' not in zeile.replace(" ", ""):
                    continue
                inhalt = (json.loads(zeile).get("message") or {}).get("content")
                if isinstance(inhalt, list):
                    inhalt = " ".join(b.get("text", "") for b in inhalt
                                      if isinstance(b, dict))
                # Auch die Uebersetzungen der sichtbaren Gedanken
                # (denken.py, seit 14.11.2026) sind keine Gespraeche.
                return str(inhalt or "").startswith(
                    ("Erster Zuruf: ", "Gedanke übersetzen: "))
    except (OSError, ValueError):
        pass
    return False


def _sitzungen() -> list:
    """Sarvis' eigene Sitzungsdateien, neueste zuerst.

    Erkannt an "sdk-py" in der ersten Zeile, die einen Einstiegspunkt
    nennt. Ohne diesen Filter laege der ganze Entwicklungsverlauf von
    Claude Code mit im Zugriff -- Dateien mit sieben Megabyte, in denen
    Sarvis nichts zu suchen hat.
    """
    ordner = config.VERLAUF_ORDNER
    if not ordner.is_dir():
        return []
    dateien = sorted(ordner.glob("*.jsonl"),
                     key=lambda d: d.stat().st_mtime, reverse=True)
    grenze = time.time() - SITZUNGEN_TAGE * 86400
    try:
        from .. import gespraeche
        geloescht = gespraeche.geloeschte_sitzungen()
    except Exception:
        geloescht = set()
    eigene = []
    for datei in dateien:
        try:
            if datei.stat().st_mtime < grenze:
                break          # ab hier ist alles aelter, sortiert
        except OSError:
            continue
        try:
            with datei.open(encoding="utf-8") as f:
                for zeile in f:
                    if '"entrypoint"' not in zeile:
                        continue
                    try:
                        marke = json.loads(zeile).get("entrypoint")
                    except json.JSONDecodeError:
                        break
                    if marke == config.VERLAUF_MARKE:
                        eigene.append(datei)
                    break
            # Zwei Sorten Sitzungen, die kein Gespraech sind (14.11.2026):
            # Die Titelvergabe (main._selbst_benennen) laeuft als eigene
            # Sitzung und sah nur die ersten 600 Zeichen -- von dort kam
            # die falsche Auskunft, Saschas Nachricht sei "abgeschnitten".
            # Und Gespraeche im Papierkorb soll er nicht hervorholen.
            if eigene and eigene[-1] is datei and (
                    datei.stem in geloescht or _ist_titelsitzung(datei)):
                eigene.pop()
        except OSError:
            continue
        if len(eigene) >= SITZUNGEN_HOECHSTENS:
            break
    return eigene


def _wann(roh: str) -> str:
    """Der Zeitstempel einer Zeile, kurz und deutsch."""
    try:
        # Die Stempel stehen in UTC mit "Z" -- ohne Umrechnung waere die
        # Antwort zwei Stunden daneben und klaenge wie ein anderer Tag.
        z = datetime.fromisoformat(str(roh).replace("Z", "+00:00"))
        return z.astimezone().strftime("%d.%m. %H:%M")
    except (TypeError, ValueError):
        return "?"


def _text(nachricht) -> str:
    """Den gesprochenen Text einer Zeile -- ohne Werkzeugkram."""
    inhalt = (nachricht or {}).get("content")
    if isinstance(inhalt, str):
        return inhalt
    teile = []
    for block in inhalt or []:
        if isinstance(block, dict) and block.get("type") == "text":
            teile.append(block.get("text") or "")
    return " ".join(teile)


# Zwei Sorten Rauschen, und sie brauchen zwei Behandlungen.
#
# Der VORSPANN haengt vor einem echten Zuruf, in derselben Nachricht --
# Uhrzeit, laufende Timer, Freigaben, Shell-Ordner. Hier duerfen nur die
# betroffenen ZEILEN weg; die Aeusserung darunter ist echt.
_VORSPANN = re.compile(
    r"^\[Jetzt:|^\[Läuft gerade:|^\[Ohne Rückfrage|^\[Shell-Ordner:"
    r"|^\[Abgebrochen",
)

# FREMDES traegt zwar die Rolle "user", stammt aber nicht vom Nutzer:
# eingespielte Skill-Anleitungen, Kommandoprotokolle, die Zusammen-
# fassung nach einer Verdichtung. Hier muss die GANZE Nachricht weg.
#
# Zeilenweise reichte nicht, gemessen: Eine Suche nach "Drive" lieferte
# als Treffer ein "Du: **Running means launching the actual app** ..." --
# die zweite Zeile einer Skill-Anleitung, deren erste gefiltert worden
# war. Der Nutzer hat den Satz nie gesagt.
_FREMD = re.compile(
    # Alles, was mit einer Marke anfaengt, ist Maschinerie: <command-name>,
    # <system-reminder>, <task-notification>, <channel>. Gesprochen faengt
    # nie jemand mit einer spitzen Klammer an -- eine einzelne Regel statt
    # einer Liste, die man ergaenzen muss, sobald eine Marke dazukommt.
    r"^<"
    r"|^This session is being continued|^Diese Sitzung wird fortgesetzt"
    r"|^Base directory for this skill:|^Summary:|^Caveat:",
    re.IGNORECASE,
)


def _zeilen(datei):
    """Die sprechenden Zeilen einer Sitzung: (stempel, wann, wer, was).

    Der rohe Stempel geht mit, weil ueber mehrere Sitzungsdateien hinweg
    sortiert werden muss. Die vorgelesene Form ("28.08. 10:33") traegt
    kein Jahr und waere als Sortierschluessel falsch.
    """
    try:
        roh = datei.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for zeile in roh:
        try:
            d = json.loads(zeile)
        except json.JSONDecodeError:
            continue
        art = d.get("type")
        if art not in ("user", "assistant"):
            continue
        text = _text(d.get("message")).strip()
        if not text:
            continue
        # Erst die ganze Nachricht pruefen -- an ihrer ersten Zeile.
        # Dann erst zeilenweise den Vorspann abziehen.
        erste = next((z.strip() for z in text.splitlines() if z.strip()), "")
        if _FREMD.match(erste):
            continue
        text = "\n".join(z for z in text.splitlines()
                         if z.strip() and not _VORSPANN.match(z.strip()))
        if not text.strip():
            continue
        yield (str(d.get("timestamp") or ""),
               _wann(d.get("timestamp")),
               "Du" if art == "user" else "Ich",
               " ".join(text.split()))


def werkzeuge(protokoll=None, leuchten=None) -> list:
    def blinken(punkt: str = "Gedächtnis"):
        if leuchten:
            leuchten(punkt)

    @tool(
        "verlauf_nachschlagen",
        "Schlägt im bisherigen Gesprächsverlauf nach — auch in dem, was "
        "zusammengefasst wurde, und in früheren Sitzungen. Für 'was hatte "
        "ich vorhin gesagt', 'wie hieß die Datei nochmal', 'worüber haben "
        "wir gestern geredet'. Nicht für Wissen über den Nutzer — das "
        "steht im Gedächtnis und wird mit gedaechtnis_nachschlagen geholt.",
        {
            "type": "object",
            "properties": {
                "suche": {"type": "string",
                          "description": "Ein Wort oder eine Wendung, die "
                                         "gefallen sein muss."},
                "nur_diese_sitzung": {
                    "type": "boolean",
                    "description": "Nur der laufende Verlauf statt aller "
                                   "Sitzungen. Vorgabe: alle."},
            },
            "required": ["suche"],
        },
    )
    async def verlauf_nachschlagen(args):
        suche = str(args.get("suche") or "").strip()
        if len(suche) < 3:
            return {"content": [{"type": "text", "text":
                    "Das Suchwort ist zu kurz — damit fände ich alles."}],
                    "is_error": True}

        dateien = _sitzungen()
        if args.get("nur_diese_sitzung"):
            dateien = dateien[:1]
        if not dateien:
            return {"content": [{"type": "text", "text":
                    "Ich finde keinen gespeicherten Verlauf."}]}

        gesucht = suche.casefold()
        treffer = []
        for datei in dateien:
            for stempel, wann, wer, text in _zeilen(datei):
                if gesucht in text.casefold():
                    kurz = text if len(text) <= LAENGE else text[:LAENGE] + " …"
                    treffer.append((stempel, f"{wann} {wer}: {kurz}"))
        if not treffer:
            return {"content": [{"type": "text", "text":
                    f"Zu {suche!r} finde ich im Verlauf nichts."}]}

        # Ueber alle Sitzungen hinweg nach Zeit ordnen. Vorher kam die
        # Reihenfolge aus der Dateiliste, und die Treffer sprangen
        # zwischen den Tagen hin und her.
        treffer.sort(key=lambda t: t[0])
        mehr = len(treffer) - TREFFER
        # Die juengsten behalten, aber von frueher nach spaeter vorlesen
        # -- so, wie es passiert ist.
        gezeigt = [t[1] for t in treffer[-TREFFER:]]
        blinken()
        kopf = (f"{len(treffer)} Stellen zu {suche!r}"
                + (f", die {TREFFER} jüngsten:" if mehr > 0 else ":"))
        return {"content": [{"type": "text", "text":
                kopf + "\n" + "\n".join(gezeigt)}]}

    return [verlauf_nachschlagen]
