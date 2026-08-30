"""Wer darf mit Sarvis reden -- ein Schluessel je Geraet.

WARUM NICHT EIN PASSWORT

Sarvis auf dem Dev-PC war ein Programm hinter der Haustuer. Wer davor
sass, war Sascha; das war keine Annahme, sondern die Lage. Auf
sarvis.tech-artist.de ist er ein Endpunkt im Internet, der Mails
verschicken, Geld buchen und an den Projekten arbeiten kann.

Ein Passwort waere dafuer das falsche Werkzeug, aus einem einzigen
Grund: Es ist ueberall dasselbe. Geht ein Handy verloren, muss man es
aendern -- und damit alle anderen Geraete gleich mit aussperren, in
genau dem Moment, in dem man am wenigsten Lust darauf hat. Ein Schluessel
je Geraet laesst sich einzeln zuruecknehmen, und der Rest merkt nichts.

WAS HIER GESPEICHERT WIRD

Nicht der Schluessel. Nur sein SHA-256-Abdruck, wie bei einem Passwort.
Wer diese Datei liest, kann sich damit nicht anmelden -- er sieht nur,
dass es ein Geraet gibt.

Der Schluessel selbst wird genau einmal gezeigt, beim Anlegen. Danach
ist er weg. Das ist unbequem und Absicht: Ein Schluessel, den man
jederzeit nachschlagen kann, liegt irgendwann in einer Notiz-App.

STIMME IST KEIN AUSWEIS

Das gehoert hierher, weil es sonst niemand aufschreibt: Sarvis erkennt
nicht, WER spricht. Er erkennt, was gesagt wurde. Der Schluessel ist der
einzige Ausweis -- wer ihn hat, ist Sascha, auch wenn er ganz anders
klingt. Eine Stimmerkennung waere ein zweites Schloss an derselben Tuer
und keine Antwort darauf.
"""
import hashlib
import json
import os
import secrets
import time
from pathlib import Path

from .. import config

# Wie lang ein Schluessel ist. 32 Byte aus secrets sind 256 Bit
# Zufall; als URL-sichere Zeichen sind das 43 Stellen. Zum Abtippen zu
# lang, aber niemand tippt ihn ab -- er steht in einem Link.
LAENGE = 32

# Wo die Abdruecke liegen. Unter DATEN, weil es Zustand ist und kein
# Quelltext, und weil DATEN auf einer eigenen Platte liegt.
DATEI = config.DATEN / "geraete.json"


def _abdruck(schluessel: str) -> str:
    return hashlib.sha256(schluessel.encode("utf-8")).hexdigest()


def _laden() -> list[dict]:
    try:
        with DATEI.open(encoding="utf-8") as f:
            daten = json.load(f)
        return daten if isinstance(daten, list) else []
    except (OSError, ValueError):
        return []


def _sichern(geraete: list[dict]) -> None:
    """Ueber eine Nebendatei, damit ein Absturz nichts zerreisst.

    Und mit Rechten 0600: Es sind zwar nur Abdruecke, aber die Liste
    verraet, wie viele Geraete es gibt und wann sie zuletzt da waren.
    """
    DATEI.parent.mkdir(parents=True, exist_ok=True)
    neben = DATEI.with_suffix(".json.neu")
    with neben.open("w", encoding="utf-8") as f:
        json.dump(geraete, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.chmod(neben, 0o600)
    neben.replace(DATEI)


def anlegen(name: str) -> str:
    """Ein neues Geraet eintragen und seinen Schluessel liefern.

    Der Rueckgabewert ist das einzige Mal, dass der Schluessel im Klartext
    existiert. Wer ihn nicht notiert, legt ein neues Geraet an.
    """
    name = (str(name or "").strip() or "namenlos")[:40]
    schluessel = secrets.token_urlsafe(LAENGE)
    geraete = _laden()
    geraete.append({
        "name": name,
        "abdruck": _abdruck(schluessel),
        "angelegt": time.time(),
        "zuletzt": 0.0,
    })
    _sichern(geraete)
    return schluessel


def pruefen(schluessel: str) -> str | None:
    """Der Geraetename, wenn der Schluessel gilt -- sonst None.

    Der Vergleich laeuft ueber compare_digest und ueber ALLE Eintraege,
    auch wenn der erste schon passt. Beides gegen Zeitmessung: Wer
    tausende Schluessel durchprobiert, soll aus der Antwortdauer nicht
    ablesen koennen, wie weit er gekommen ist.
    """
    if not schluessel:
        return None
    gesucht = _abdruck(str(schluessel))
    geraete = _laden()
    treffer = None
    for i, g in enumerate(geraete):
        if secrets.compare_digest(str(g.get("abdruck", "")), gesucht):
            treffer = i
    if treffer is None:
        return None
    geraete[treffer]["zuletzt"] = time.time()
    try:
        _sichern(geraete)
    except OSError:
        pass  # Der Zeitstempel ist Komfort, keine Bedingung
    return str(geraete[treffer].get("name") or "namenlos")


def liste() -> list[dict]:
    """Alle Geraete -- Name, wann angelegt, wann zuletzt gesehen."""
    return [{"name": g.get("name"), "angelegt": g.get("angelegt"),
             "zuletzt": g.get("zuletzt")} for g in _laden()]


def widerrufen(name: str) -> int:
    """Alle Geraete dieses Namens hinauswerfen. Gibt die Zahl zurueck.

    Nach Namen und nicht nach Schluessel, weil man den Schluessel des
    verlorenen Handys ja gerade nicht mehr hat -- und weil "welches
    Handy" eine Frage ist, die man beantworten kann, "welcher Abdruck"
    nicht.
    """
    geraete = _laden()
    bleiben = [g for g in geraete if g.get("name") != name]
    weg = len(geraete) - len(bleiben)
    if weg:
        _sichern(bleiben)
    return weg
