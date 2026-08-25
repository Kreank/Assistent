"""Wie Sarvis eine Rückfrage formuliert und wie er die Antwort versteht.

Getrennt von der Mechanik, weil hier die Sprache steckt: Eine Rückfrage
muss man beantworten können, ohne hinzusehen, also muss sie den Inhalt
enthalten -- "Soll ich Anna schreiben, dass du später kommst?" und nicht
"Werkzeug telegram_senden ausführen?".
"""
import re

from . import schutz

# Was als Ja oder Nein zaehlt. Whisper liefert ganze Saetze, deshalb wird
# nicht auf Gleichheit geprueft, sondern auf ein Vorkommen am Anfang.
JA = (
    "ja", "jap", "jo", "joa", "jawohl", "klar", "okay", "ok", "in ordnung",
    "mach das", "mach", "machs", "mach es", "gerne", "bitte", "genau",
    "richtig", "stimmt", "passt", "einverstanden", "los", "leg los",
    "schick", "schick es", "abschicken", "senden", "ja bitte", "ja gerne",
)
NEIN = (
    "nein", "ne", "nee", "nö", "noe", "nicht", "lass", "lass es",
    "lieber nicht", "abbrechen", "stopp", "stop", "halt", "warte",
    "nein danke", "auf keinen fall", "vergiss es", "doch nicht",
)


def deuten(text: str) -> bool | None:
    """Ja, Nein oder unklar. Unklar ist ein eigenes Ergebnis, kein Nein --
    darauf wird nachgefragt statt geraten."""
    t = re.sub(r"[^\wäöüß ]+", " ", (text or "").lower()).strip()
    if not t:
        return None
    woerter = t.split()

    # Verneinung zuerst: "ja, aber nicht jetzt" ist kein Ja.
    for muster in sorted(NEIN, key=len, reverse=True):
        if t.startswith(muster) or f" {muster} " in f" {t} ":
            return False
    for muster in sorted(JA, key=len, reverse=True):
        if t.startswith(muster) or f" {muster} " in f" {t} ":
            return True
    if len(woerter) == 1 and woerter[0] in ("hm", "hmm", "äh", "ähm"):
        return None
    return None


def _kuerzen(text: str, laenge: int = 90) -> str:
    # Satzzeichen am Ende weg: der eingesetzte Text steht mitten in einer
    # Frage, sonst wird daraus "...später.?"
    text = " ".join(str(text or "").split()).rstrip(".!?;:, ")
    return text if len(text) <= laenge else text[: laenge - 1] + "…"


def formulieren(werkzeug: str, eingabe: dict) -> str:
    """Aus Werkzeug und Eingabe eine Frage machen, die man hören kann."""
    e = eingabe or {}

    if werkzeug == "datei_lesen":
        pfad = e.get("pfad") or ""
        if schutz.heikel(pfad):
            return (f"Achtung: {schutz.sprechbar(pfad)} enthält vermutlich "
                    "Zugangsdaten. Soll ich sie trotzdem öffnen?")
        return f"Soll ich {schutz.sprechbar(pfad)} lesen?"

    if werkzeug == "ordner_ansehen":
        return f"Soll ich nachsehen, was in {schutz.sprechbar(e.get('pfad'))} liegt?"

    if werkzeug == "datei_schreiben":
        pfad = e.get("pfad") or ""
        vorhanden = ""
        try:
            from pathlib import Path as _P
            if _P(pfad).exists():
                vorhanden = "überschreiben"
        except (OSError, ValueError):
            pass
        return (f"Soll ich {schutz.sprechbar(pfad)} "
                f"{vorhanden or 'anlegen'}?")

    if werkzeug == "programm_beenden":
        return f"Soll ich {_kuerzen(e.get('name'), 40)} wirklich beenden?"

    if werkzeug == "befehl_ausfuehren":
        # Absicht statt Kommandozeile. Den vollen Befehl vorzulesen war
        # nicht zu beantworten, nur zu ertragen.
        return f"Soll ich {schutz.absicht(e.get('befehl'))}?"

    if werkzeug == "merken":
        return f"Soll ich mir merken: {_kuerzen(e.get('inhalt'))}?"

    if werkzeug == "vergessen":
        return (f"Soll ich alles zu {_kuerzen(e.get('stichwort'), 50)} aus "
                "dem Gedächtnis löschen?")

    if werkzeug == "telegram_senden":
        an = e.get("an") or "den Kontakt"
        return f"Soll ich {an} schreiben: {_kuerzen(e.get('text'))}?"

    if werkzeug == "mail_senden":
        an = e.get("an") or "den Empfänger"
        # Bei einer Mail zaehlt der Inhalt, nicht nur der Empfaenger --
        # anders als beim Termin kann man sie nicht zurueckholen. Deshalb
        # kommt der Anfang des Textes mit in die Frage.
        return (f"Soll ich eine Mail an {an} senden, Betreff "
                f"{_kuerzen(e.get('betreff'), 50)}? "
                f"Der Text lautet: {_kuerzen(e.get('text'), 160)}")

    if werkzeug == "projekt_anlegen":
        return (f"Soll ich ein Projekt {_kuerzen(e.get('name'), 50)} anlegen?")

    if werkzeug == "projekt_oeffnen":
        return f"Soll ich {_kuerzen(e.get('name'), 50)} im Terminal öffnen?"

    if werkzeug == "auftrag_geben":
        return (f"Soll ich im Projekt {_kuerzen(e.get('projekt'), 40)} "
                f"daran arbeiten: {_kuerzen(e.get('was'), 80)}?")

    if werkzeug == "termin_anlegen":
        # Die Feldnamen muessen zu denen im Werkzeug passen -- vorher stand
        # hier "wann", das Werkzeug heisst es aber "beginn". Ergebnis war
        # "am angegebenen Zeitpunkt", also genau die Angabe, wegen der man
        # ueberhaupt fragt.
        return (f"Soll ich {_kuerzen(e.get('titel'), 50)} "
                f"am {e.get('beginn', 'genannten Zeitpunkt')} eintragen?")

    if werkzeug == "termin_absagen":
        return f"Soll ich den Termin {_kuerzen(e.get('titel'), 50)} absagen?"

    if werkzeug == "mail_verschieben":
        wohin = {"papierkorb": "in den Papierkorb verschieben",
                 "archiv": "archivieren",
                 "gelesen": "auf gelesen setzen",
                 "ungelesen": "auf ungelesen setzen"}.get(
                     e.get("wohin"), "verschieben")
        anzahl = e.get("anzahl") or 1
        was = "eine Mail" if int(anzahl) == 1 else f"{anzahl} Mails"
        return f"Soll ich {was} zu {_kuerzen(e.get('suche'), 40)} {wohin}?"

    if werkzeug == "drive_teilen":
        # Der Satz muss die Tragweite tragen, nicht den Werkzeugnamen:
        # "freigeben" klingt harmlos, "jeder mit dem Link" nicht.
        return (f"Soll ich {_kuerzen(e.get('name'), 50)} freigeben? "
                "Danach kann jeder mit dem Link mitlesen.")

    if werkzeug == "tabelle_schreiben":
        return (f"Soll ich in {_kuerzen(e.get('name'), 40)} den Bereich "
                f"{e.get('bereich', 'den angegebenen')} überschreiben mit "
                f"{_kuerzen(', '.join(str(w) for w in (e.get('werte') or [])), 80)}?")

    if werkzeug == "tabelle_anlegen":
        return f"Soll ich eine Tabelle {_kuerzen(e.get('name'), 50)} anlegen?"

    if werkzeug == "kontakt_anlegen":
        return f"Soll ich {_kuerzen(e.get('name'), 40)} als Kontakt anlegen?"

    # Auffangfall: lieber umstaendlich als stumm.
    teile = ", ".join(f"{k} {_kuerzen(v, 40)}" for k, v in list(e.items())[:3])
    return f"Soll ich {werkzeug} ausführen{', mit ' + teile if teile else ''}?"


NACHHAKEN = "Ich habe das nicht verstanden. Ja oder nein?"
ABGELEHNT = "Gut, ich lasse es."
ABGELAUFEN = "Ich habe keine Antwort bekommen und lasse es lieber."
