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


# Welche Entscheidungen beim Start im Systemprompt standen.
#
# Der Systemprompt wird EINMAL beim Start gebaut und danach nie wieder
# (hirn.py). Alles, was Sarvis sich waehrend des Betriebs merkt, steht
# also erst nach einem Neustart in seinem Kontext.
#
# Bei einer Eigenschaft des Nutzers ist das zu verschmerzen -- innerhalb
# der Sitzung weiss er es ohnehin aus dem Gespraech. Bei einer
# ENTSCHEIDUNG ist es genau der kritische Fall: "Verwirf das" faellt
# mitten im Betrieb, und wenn eine Vorspannzeile im naechsten Zug erneut
# auffordert, dieselbe Sache anzubieten, dann muss die Entscheidung JETZT
# dagegenstehen und nicht nach dem naechsten Neustart.
#
# Deshalb wird hier festgehalten, was beim Start dabei war -- und was
# seither dazukam, haengt der Vorspann bei jedem Zuruf frisch an.
_BEIM_START: set = set()

# Wie viele Entscheidungen hoechstens in den Vorspann wandern. Der
# Vorspann wird nicht zwischengespeichert, jede Zeile kostet also bei
# jedem Zuruf erneut. Zwoelf ist grosszuegig fuer einen Menschen und
# klein genug, dass es nicht auffaellt: rund 500 Zeichen.
ENTSCHEIDUNGEN_IM_VORSPANN = 12


def entscheidungen_nachtrag() -> str:
    """ALLE geltenden Entscheidungen -- bei jedem Zuruf neu, im Vorspann.

    Warum nicht nur die neuen, und warum ueberhaupt doppelt zum
    Systemprompt: Etwas steht im Kontext und wird trotzdem nicht befolgt.
    Gemessen ist, dass die Treue zu einer geaeusserten Vorgabe nach rund
    zehn Zuegen unter zehn Prozent faellt, obwohl der Satz die ganze Zeit
    dasteht. Weit oben im Prompt heisst nicht praesent.

    Der Vorspann ist die einzige Schicht, die bei JEDEM Zuruf frisch
    gebaut wird -- und er steht direkt neben den Zeilen, die eine
    Entscheidung ueberfahren wuerden ("biete an, den Zweig zu
    verwerfen"). Genau dort gehoert der Widerspruch hin, nicht
    zehntausend Zeichen weiter oben.

    Das kostet Kontext, weil der Vorspann nicht zwischengespeichert wird.
    Bei einer Handvoll Entscheidungen sind das ein paar Dutzend Token je
    Zuruf. Deshalb der Deckel unten: Die juengsten zaehlen, und dass
    gekuerzt wurde, wird gesagt statt verschwiegen.
    """
    from .werkzeuge.erinnern import lesen
    try:
        alle = lesen("entschieden")
    except Exception:
        return ""
    if not alle:
        return ""
    # Juengste zuerst -- die Datei ist chronologisch, das Neueste unten.
    gilt = list(reversed(alle))[:ENTSCHEIDUNGEN_IM_VORSPANN]
    mehr = len(alle) - len(gilt)
    text = " · ".join(z.lstrip("- ") for z in gilt)
    if mehr > 0:
        text += (f" · (und {mehr} ältere — mit gedaechtnis_zeigen "
                 "nachzulesen)")
    return ("[Das hat er entschieden. Daran hältst du dich, ohne erneut "
            "zu fragen — auch wenn eine Zeile hier daneben dieselbe Sache "
            "noch einmal anbietet: " + text + "]")


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
    entschieden = lesen("entschieden")

    if not (kern or gesagt or bemerkt or entschieden):
        return config.SYSTEMPROMPT, hinweise

    teile = [config.SYSTEMPROMPT, "\n\n--- Was du über den Nutzer weißt ---\n"]

    if kern:
        teile.append("\nGrundlegendes:\n" + kern)
    # Entscheidungen stehen NICHT hier, obwohl sie hierher zu passen
    # scheinen. Sie gehen ueber den Vorspann (entscheidungen_nachtrag),
    # und zwar bei jedem Zuruf neu -- die Begruendung steht dort.
    #
    # Hier waeren sie zwar billiger, weil der Systemprompt
    # zwischengespeichert wird. Aber er wird auch nur EINMAL beim Start
    # gebaut: Was Sascha mitten im Betrieb entscheidet, stuende erst nach
    # dem naechsten Neustart drin. Genau dann, wenn es darauf ankommt,
    # waere es nicht da.
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
        "du ohnehin im Vorspann.\n"
        "- Eine ENTSCHEIDUNG ist davon ausgenommen: die hältst du immer "
        "fest, sofort, ohne zu fragen. \"Verwirf das\", \"das machen wir "
        "nicht mehr\", \"ab jetzt immer so\" — merken mit art "
        "'entschieden' und einem thema. Das ist keine Vermutung über ihn, "
        "sondern seine eigene Ansage, und sie kostet ihn Zeit, wenn du sie "
        "verlierst: Er hat sie dann schon einmal gesagt.\n"
        "- Widerspricht eine neue Entscheidung einer alten, merkst du die "
        "neue mit DEMSELBEN thema. Die alte wird dadurch abgelöst — darum "
        "musst du dich nicht weiter kümmern.\n"
        "- Steht eine Entscheidung oben und ein Vorspann oder ein Werkzeug "
        "fordert dich auf, dieselbe Sache erneut anzubieten, dann tu es "
        "nicht. Sag stattdessen, was entschieden wurde, oder führe es aus. "
        "Zweimal dasselbe gefragt zu werden ist das, was am meisten nervt."
    )
    if bemerkt:
        hinweise.append(f"{len(bemerkt)} eigene Beobachtung(en) geladen")
    if gesagt:
        hinweise.append(f"{len(gesagt)} gemerkte Angabe(n) geladen")
    if entschieden:
        hinweise.append(f"{len(entschieden)} Entscheidung(en) geladen")
    _BEIM_START.clear()
    _BEIM_START.update(entschieden)
    return "".join(teile), hinweise
