"""Sarvis' Gedaechtnis -- die immer geladene Schicht.

Zwei Schichten, weil sie unterschiedlich teuer sind:

  kern.md      geht bei JEDEM Zuruf mit. Teuer, also kurz.
  personen/    wird nur nachgeschlagen, wenn es gebraucht wird (Stufe 2).
  notizen/

Der Kern gehoert in den Systemprompt und nicht in die Frage: Dort wird er
zwischengespeichert und kostet dadurch bei jedem weiteren Zuruf fast nichts.
Wuerde er an die Frage gehaengt, waere er jedes Mal neu zu lesen.
"""
import re
from pathlib import Path

from . import config

# Ab hier wird der Kern nicht mehr besser, sondern nur noch unschaerfer.
# Kein hartes Limit -- Sarvis soll nicht schweigen, weil eine Datei zu
# lang ist -- aber eine sichtbare Warnung beim Start.
KERN_WARNGRENZE = 4000  # Zeichen, grob 60-70 Zeilen


def _ohne_geruest(text: str) -> str:
    """HTML-Kommentare und leere Abschnitte raus.

    Die Vorlage besteht groesstenteils aus Ausfuellhinweisen. Die wuerden
    sonst als vermeintliche Fakten mitgehen -- und Sarvis wuerde
    frueher oder spaeter ueber "(Name)" reden.
    """
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = re.sub(r"^\(.*\)$", "", text, flags=re.MULTILINE)

    zeilen = [z.rstrip() for z in text.splitlines()]
    behalten: list[str] = []
    for zeile in zeilen:
        # Platzhalter in Klammern und leere Listenpunkte fliegen raus
        if re.fullmatch(r"\s*-\s*\(.*\)\s*", zeile) or re.fullmatch(r"\s*-\s*", zeile):
            continue
        behalten.append(zeile)

    # Ueberschriften ohne Inhalt entfernen
    ergebnis: list[str] = []
    for i, zeile in enumerate(behalten):
        if zeile.startswith("#"):
            rest = behalten[i + 1:]
            naechste = next(
                (r for r in rest if r.strip() and not r.startswith("---")), ""
            )
            if not naechste or naechste.startswith("#"):
                continue
        ergebnis.append(zeile)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(ergebnis)).strip()


def kern_lesen() -> tuple[str, list[str]]:
    """Gibt (Text fuer den Systemprompt, Hinweise fuer die Konsole) zurueck."""
    hinweise: list[str] = []
    datei: Path = config.GEDAECHTNIS / "kern.md"
    if not datei.exists():
        # kern.md ist ausgefuellt persoenlich und steht deshalb NICHT im
        # Repository -- nur die leere Struktur als kern.VORLAGE.md. Beim
        # ersten Start (oder nach einem frischen Klon) wird daraus eine
        # eigene Datei gemacht, sonst stuende hier nur eine Warnung und
        # niemand wuesste, was zu tun ist.
        vorlage = config.GEDAECHTNIS / "kern.VORLAGE.md"
        if vorlage.exists():
            datei.write_text(vorlage.read_text(encoding="utf-8"),
                             encoding="utf-8")
            return "", [f"kern.md aus der Vorlage angelegt -- bitte ausfuellen ({datei})"]
        return "", [f"kein Gedaechtnis gefunden ({datei})"]

    roh = datei.read_text(encoding="utf-8")
    inhalt = _ohne_geruest(roh)

    # Die Anleitung am Kopf der Datei ist fuer dich, nicht fuer Sarvis.
    if "---" in inhalt:
        inhalt = inhalt.split("---", 1)[1].strip()

    if not inhalt:
        return "", ["Gedaechtnis ist noch leer (gedaechtnis/kern.md ausfuellen)"]

    if len(inhalt) > KERN_WARNGRENZE:
        hinweise.append(
            f"kern.md ist {len(inhalt)} Zeichen lang -- ueber {KERN_WARNGRENZE} "
            "wird Sarvis eher unschaerfer als kluger. Details nach personen/."
        )

    tiefe = _tiefe_zaehlen()
    return inhalt, hinweise + ([tiefe] if tiefe else [])


def _tiefe_zaehlen() -> str:
    personen = list((config.GEDAECHTNIS / "personen").glob("*.md"))
    personen = [p for p in personen if p.stem != "BEISPIEL"]
    notizen = list((config.GEDAECHTNIS / "notizen").glob("*.md"))
    if not personen and not notizen:
        return ""
    return f"{len(personen)} Person(en), {len(notizen)} Notiz(en) im Hintergrund"


def systemprompt() -> tuple[str, list[str]]:
    """Der vollstaendige Systemprompt inklusive Gedaechtnis.

    Drei Quellen, und sie werden bewusst getrennt uebergeben. Wuerde man
    Beobachtungen unter dieselbe Ueberschrift schreiben wie Gesagtes,
    verloere Sarvis genau die Information, auf die es ankommt: wie sicher
    er sich sein darf.
    """
    from .werkzeuge.erinnern import lesen

    kern, hinweise = kern_lesen()
    gesagt = lesen("gesagt")
    bemerkt = lesen("bemerkt")

    if not (kern or gesagt or bemerkt):
        return config.SYSTEMPROMPT, hinweise

    teile = [config.SYSTEMPROMPT, "\n\n--- Was du über den Nutzer weißt ---\n"]

    if kern:
        teile.append("\nGrundlegendes:\n" + kern)
    if gesagt:
        teile.append("\nVon ihm ausdrücklich gesagt (gilt als Tatsache):\n"
                     + "\n".join(gesagt))
    if bemerkt:
        teile.append(
            "\nDir selbst aufgefallen — VERMUTUNGEN, keine Tatsachen:\n"
            + "\n".join(bemerkt)
        )

    teile.append(
        "\n\nWie du damit umgehst:\n"
        "- Nutze das Wissen beiläufig, wenn es zur Sache gehört. Zähl es nie "
        "auf und weise nicht darauf hin, dass du es hast.\n"
        "- Steht etwas nicht darin, weißt du es schlicht nicht — rate nicht.\n"
        "- Vermutungen behandelst du als Vermutung. Sag \"du hattest mal "
        "erwähnt\", nicht \"du machst das immer so\". Widerspricht der Nutzer, "
        "gilt sofort seine Version, und du löschst die Vermutung.\n"
        "- Eine Vermutung ist NIE Grundlage für eine Handlung nach außen. "
        "Mails, Nachrichten und Termine entstehen ausschließlich auf "
        "ausdrücklichen Zuruf — nie, weil du aus dem Zusammenhang schließt, "
        "dass es gerade passen würde.\n"
        "- Was du dir merkst, merkst du sparsam: nur was über den Tag hinaus "
        "zählt. Laufendes wie Timer gehört nicht ins Gedächtnis, das siehst "
        "du ohnehin im Vorspann."
    )
    if bemerkt:
        hinweise.append(f"{len(bemerkt)} eigene Beobachtung(en) geladen")
    if gesagt:
        hinweise.append(f"{len(gesagt)} gemerkte Angabe(n) geladen")
    return "".join(teile), hinweise
