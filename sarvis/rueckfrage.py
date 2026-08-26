"""Wie Sarvis eine Rückfrage formuliert und wie er die Antwort versteht.

Getrennt von der Mechanik, weil hier die Sprache steckt: Eine Rückfrage
muss man beantworten können, ohne hinzusehen, also muss sie den Inhalt
enthalten -- "Soll ich Anna schreiben, dass du später kommst?" und nicht
"Werkzeug telegram_senden ausführen?".
"""
import re

from . import config, schutz

# --- Ja, Nein, oder etwas Drittes ----------------------------------------
#
# Frueher gab es nur ja / nein / unklar, und "unklar" fuehrte zum
# Nachhaken. Das war zu grob: Auf "ja, aber nur die erste" gab es ein
# glattes Ja -- und das Werkzeug lief mit den urspruenglichen Angaben,
# als waere die Einschraenkung nie gesagt worden.
#
# Deshalb vier Ausgaenge:
#
#   "ja"      ausfuehren
#   "nein"    nicht ausfuehren
#   "anders"  nicht ausfuehren, aber es war keine Absage -- der Satz geht
#             an Sarvis zurueck, damit er es richtig noch einmal ansetzt
#   "unklar"  nichts verstanden, einmal nachhaken
#
# Geprueft wird wortweise. Vorher stand hier startswith(): damit begann
# "machen wir das nicht" mit dem Ja-Wort "mach".

JA = (
    "ja", "jo", "joa", "jap", "jup", "jupp", "yep", "jawohl", "jaja",
    "klar", "na klar", "klar doch", "logo", "okay", "ok", "oki",
    "in ordnung", "alles klar", "passt", "passt so", "perfekt", "super",
    "gut", "sehr gut", "gerne", "bitte", "genau", "richtig", "stimmt",
    "korrekt", "einverstanden", "sicher", "sicherlich", "unbedingt",
    "auf jeden fall", "auf jeden", "mach", "mach das", "machs", "mach es",
    "mach mal", "mach ruhig", "tu das", "tu es", "los", "leg los",
    "schick", "schick es", "schick ab", "abschicken", "senden",
    "bestätige", "bestätigt", "ja bitte", "ja gerne", "weiter",
    "fahr fort", "genehmigt", "freigegeben",
)

# "lass" steht hier bewusst NICHT mehr allein: "ja, lass uns das machen"
# wurde dadurch als Nein verstanden -- gemessen, nicht vermutet. Nur die
# Wendungen, die wirklich abwinken.
NEIN = (
    "nein", "ne", "nee", "nö", "noe", "nicht", "nicht machen",
    "bitte nicht", "lieber nicht", "besser nicht", "bloß nicht",
    "bloss nicht", "auf keinen fall", "keinesfalls", "lass es",
    "lass mal", "lass das", "lass gut sein", "lass stecken",
    "abbrechen", "abbruch", "stopp", "stop", "halt", "vergiss es",
    "vergiss das", "doch nicht", "nein danke", "quatsch", "falsch",
    "niemals", "negativ",
)

# Signale dafuer, dass es weder ein glattes Ja noch eine Absage ist,
# sondern eine Korrektur. Bewusst enge Wendungen: ein blosses "nur"
# haette "ja, nur zu" zerlegt.
ANDERS = (
    "aber", "außer", "ausser", "statt", "stattdessen", "jedoch",
    "allerdings", "lieber", "warte", "moment", "erst mal", "erstmal",
    "erst noch", "vorher", "zuerst", "ändere", "ändern", "anders",
    "nur die", "nur das", "nur den", "nur dem", "nur bei", "nur für",
    "nur wenn", "nicht die", "nicht das", "nicht den",
)

JA_SICHER, NEIN_SICHER, ANDERS_, UNKLAR = "ja", "nein", "anders", "unklar"


def _wortweise(muster: str) -> str:
    return r"\b" + r"\s+".join(re.escape(w) for w in muster.split()) + r"\b"


def _am_anfang(text: str, muster) -> str | None:
    """Das laengste Muster, mit dem der Satz beginnt."""
    for m in sorted(muster, key=len, reverse=True):
        if re.match(_wortweise(m), text):
            return m
    return None


def _kommt_vor(text: str, muster) -> bool:
    return any(re.search(_wortweise(m), text) for m in muster)


def deuten(text: str) -> str:
    """"ja", "nein", "anders" oder "unklar" -- siehe oben."""
    t = re.sub(r"[^\wäöüß ]+", " ", (text or "").lower())
    t = " ".join(t.split())
    if not t:
        return UNKLAR

    # Absagen zuerst, und zwar nur am Satzanfang. Frueher wurde im ganzen
    # Satz gesucht -- daran ist "ja, lass uns das machen" gestorben.
    if _am_anfang(t, NEIN):
        return NEIN_SICHER

    zusage = _am_anfang(t, JA)
    if zusage:
        rest = t[len(zusage):].strip()
        # "ja, aber nur die erste" und "mach das, aber nicht löschen":
        # zugestimmt, doch nicht zu dem, was gefragt wurde.
        if _kommt_vor(rest, ANDERS) or _kommt_vor(rest, NEIN):
            return ANDERS_
        return JA_SICHER

    # Kein klares Wort am Anfang. Eine Absage irgendwo im Satz zaehlt
    # trotzdem -- eine Zusage irgendwo im Satz bewusst nicht: "das haette
    # ich gerne anders" ist kein Startschuss.
    if _kommt_vor(t, NEIN):
        return NEIN_SICHER
    if _kommt_vor(t, JA) or _kommt_vor(t, ANDERS):
        return ANDERS_
    return UNKLAR


# --- Freigabe auf Zeit ----------------------------------------------------

_ZAHLWORT = {
    "eine": 1, "einer": 1, "ein": 1, "zwei": 2, "drei": 3, "vier": 4,
    "fünf": 5, "fuenf": 5, "sechs": 6, "zehn": 10, "zwölf": 12,
    "zwoelf": 12, "fünfzehn": 15, "fuenfzehn": 15, "zwanzig": 20,
    "dreißig": 30, "dreissig": 30, "vierzig": 40, "sechzig": 60,
    "halbe": 0.5, "halben": 0.5,
}

# "und jetzt hör auf zu fragen" -- in allen Varianten, die man wirklich
# sagt. Ohne eines dieser Signale gilt ein Ja nur fuer diesen einen Fall.
_FREIGABE = (
    r"frag(e|st)?\s+(mich\s+)?nicht\s+(mehr|nochmal|noch\s+mal|wieder|jedes)",
    r"nicht\s+(mehr|nochmal|noch\s+mal|jedes\s+mal)\s+frag",
    r"ohne\s+(nach)?zufragen", r"ohne\s+(nach)?frage",
    r"hör\s+auf\s+zu\s+fragen", r"hoer\s+auf\s+zu\s+fragen",
    r"(musst|brauchst)\s+(du\s+)?nicht\s+(mehr\s+)?(zu\s+)?frag",
    r"nicht\s+jedes\s+mal", r"immer\s+(erlaubt|frei)",
    r"ab\s+jetzt", r"von\s+jetzt\s+an", r"für\s+die\s+nächste",
    r"fuer\s+die\s+naechste", r"für\s+die\s+nächsten",
    r"die\s+nächsten?\s+\S+\s+(minuten|stunde)",
)


def freigabe_erkennen(text: str) -> float | None:
    """Wie lange soll nicht mehr gefragt werden? Minuten, oder None.

    None heisst: ganz normales Ja, gilt nur fuer diesen einen Aufruf. Das
    ist der Regelfall und bleibt es auch -- eine Freigabe muss man
    aussprechen, sie entsteht nicht aus Bequemlichkeit.
    """
    t = " ".join(re.sub(r"[^\wäöüß ]+", " ", (text or "").lower()).split())
    if not t:
        return None

    # Eine ausdrueckliche Zeitangabe reicht als Wunsch fuer sich: "ja, für
    # die nächste halbe Stunde" sagt niemand, der nur einmal ja meint.
    dauer = _dauer_lesen(t)
    if dauer is None and not any(re.search(m, t) for m in _FREIGABE):
        return None
    return dauer if dauer is not None else config.FREIGABE_MINUTEN


def _dauer_lesen(t: str) -> float | None:
    treffer = re.search(
        r"(\d+|" + "|".join(_ZAHLWORT) + r")?\s*"
        r"(minuten|minute|min|stunden|stunde|std)\b", t)
    if not treffer:
        # "für heute" ist eine Ansage, aber keine Zahl.
        if re.search(r"\b(für|fuer)\s+heute\b", t):
            return config.FREIGABE_MAX_MINUTEN
        return None
    roh, einheit = treffer.group(1), treffer.group(2)
    if roh is None:
        # "eine Stunde" ohne Zahl davor, oder schlicht "für die Stunde"
        menge = 1.0
    elif roh.isdigit():
        menge = float(roh)
    else:
        menge = float(_ZAHLWORT.get(roh, 1))
    return menge * (60 if einheit.startswith("std") or einheit.startswith("stund")
                    else 1)


def _kuerzen(text: str, laenge: int = 90) -> str:
    # Satzzeichen am Ende weg: der eingesetzte Text steht mitten in einer
    # Frage, sonst wird daraus "...später.?"
    text = " ".join(str(text or "").split()).rstrip(".!?;:, ")
    if len(text) <= laenge:
        return text
    # An der Wortgrenze schneiden. Vorher endete die Frage mitten im Wort
    # ("...wurde aber mitt…?") -- gesprochen klingt das wie ein Fehler
    # und nicht wie eine Frage.
    schnitt = text[: laenge - 1]
    luecke = schnitt.rfind(" ")
    if luecke > laenge * 0.55:
        schnitt = schnitt[:luecke]
    return schnitt.rstrip(" ,;:.") + "…"


def _erster_satz(text: str, laenge: int = 70) -> str:
    """Der erste Satz -- fuer Texte, die als Prompt geschrieben wurden."""
    roh = " ".join(str(text or "").split())
    ende = re.search(r"[.!?](\s|$)", roh)
    if ende:
        roh = roh[: ende.start()]
    return _kuerzen(roh, laenge)


def formulieren(werkzeug: str, eingabe: dict) -> str:
    """Aus Werkzeug und Eingabe eine Frage machen, die man hören kann."""
    e = eingabe or {}

    if werkzeug == "datei_lesen":
        pfad = e.get("pfad") or ""
        if schutz.heikel(pfad):
            return (f"Achtung: {schutz.sprechbar(pfad)} enthält vermutlich "
                    "Zugangsdaten. Soll ich sie trotzdem öffnen?")
        return f"Soll ich {schutz.sprechbar(pfad)} lesen?"

    if werkzeug == "ordner_durchsuchen":
        muster = _kuerzen(e.get("muster"), 40)
        wo = schutz.sprechbar(e.get("pfad"), "dativ")
        return (f"Soll ich in {wo} nach {muster} suchen?" if muster
                else f"Soll ich {wo} durchsuchen?")

    if werkzeug == "ordner_ansehen":
        return f"Soll ich nachsehen, was in {schutz.sprechbar(e.get('pfad'))} liegt?"

    if werkzeug == "datei_schreiben":
        pfad = e.get("pfad") or ""
        vorhanden = ""
        neuer_ordner = None
        try:
            from pathlib import Path as _P
            p = _P(pfad)
            if p.exists():
                vorhanden = "überschreiben"
            # Entsteht der Ordner gerade erst mit? Dann reicht sein Name
            # nicht. "index.html im Ordner Finanzdashboard" klingt, als
            # gäbe es den Ordner schon -- und WO er liegt, erfährt man
            # nie. Genau so landete ein Dashboard unbemerkt in D:/Privat.
            elif p.parent and not p.parent.exists():
                neuer_ordner = p.parent
        except (OSError, ValueError):
            pass

        if neuer_ordner is not None:
            wo = schutz.sprechbar(neuer_ordner.parent, "dativ")
            return (f"Soll ich {p.name} anlegen? Der Ordner "
                    f"{neuer_ordner.name} entsteht dabei in {wo}.")

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
        # Der Ort MUSS in der Frage stehen. Er ist der eigentliche Grund,
        # warum hier ueberhaupt gefragt wird -- ein Projekt am falschen
        # Ort merkt man erst Wochen spaeter.
        ort = config.PROJEKT_ORT_NAMEN.get((e.get("ort") or "").lower(), "")
        wohin = f" in {ort}" if ort else ""
        return (f"Soll ich ein Projekt {_kuerzen(e.get('name'), 50)}"
                f"{wohin} anlegen?")

    if werkzeug == "projekt_oeffnen":
        return f"Soll ich {_kuerzen(e.get('name'), 50)} im Terminal öffnen?"

    if werkzeug == "auftrag_geben":
        # Der Auftragstext ist ein Arbeitsauftrag fuer den Arbeiter, kein
        # Satz zum Vorlesen: lang, mit Vorgeschichte, oft mehrere Absaetze.
        # Vorgelesen wurde er bis "...wurde aber mitt…?" -- das beantwortet
        # niemand. Der erste Satz sagt, worum es geht; alles Weitere
        # steht im Auftrag, nicht in der Frage.
        worum = _erster_satz(e.get("was"), 70)
        # Endet es schon mit Auslassungspunkten, waere ein Punkt dahinter
        # ein "….." -- vorgelesen ein Stolpern.
        schluss = "" if worum.endswith("…") else "."
        return (f"Soll ich einen Auftrag im Projekt "
                f"{_kuerzen(e.get('projekt'), 40)} starten? "
                f"Es geht um: {worum}{schluss}")

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


# Woerter, die einen laufenden Vorgang beenden. Bewusst getrennt von den
# NEIN-Woertern: Ein "nein" beantwortet eine Frage, ein "stopp" bricht ab,
# ohne dass eine Frage offen steht.
_STOPP_WORTE = {"stopp", "stop", "stoppen", "stoppe", "aufhören", "aufhoeren",
                "abbrechen", "abbruch", "beenden", "beende"}
# Dieselbe Absicht in zwei Woertern.
_STOPP_PAARE = (("hör", "auf"), ("hoer", "auf"), ("hört", "auf"),
                ("brich", "ab"), ("sei", "still"), ("lass", "das"))
# Diese zaehlen nur in einem KURZEN Zuruf. "halt" ist im Deutschen ein
# Fuellwort ("das ist halt so") -- als Abbruchbefehl gilt es nur, wenn
# nicht viel anderes daneben steht.
_STOPP_KURZ = {"halt", "still", "schluss", "ruhe"}
# Wird eines davon genannt, ist ein bestimmtes Ding gemeint und nicht
# alles. "Timer beenden" oder "stopp die Musik" haben ihr eigenes
# Werkzeug -- ein Not-Aus daraus zu machen waere schlimmer als die
# Rueckfrage, die es ersetzt.
_ANDERES = {"timer", "wecker", "uhr", "musik", "lied", "song", "titel",
            "wiedergabe", "programm", "programme", "fenster", "app"}


def ist_stopp(text: str) -> bool:
    """Heisst dieser Zuruf: sofort aufhoeren?

    Wird VOR dem Hirn gefragt. Sonst antwortet Claude auf "hör auf" mit
    einem Lagebericht statt aufzuhoeren -- genau das ist passiert.
    """
    worte = [w.strip(".,!?;:-–\"'„“»«") for w in (text or "").lower().split()]
    menge = {w for w in worte if w}
    if not menge:
        return False
    if menge & _ANDERES:
        return False
    if menge & _STOPP_WORTE:
        return True
    for a, b in _STOPP_PAARE:
        if a in menge and b in menge:
            return True
    if menge & _STOPP_KURZ and (len(worte) <= 3 or worte[0] in _STOPP_KURZ):
        return True
    return False


def genauer(werkzeug: str, eingabe: dict) -> str | None:
    """Dieselbe Frage noch einmal -- mit dem, was beim ersten Mal fehlte.

    Beim ersten Fragen ist Kuerze richtig. Wer aber zurueckfragt ("und
    welcher Befehl?"), bekommt mit "Ich habe das nicht verstanden" genau
    die Auskunft nicht, die er verlangt hat -- und sagt beim zweiten Mal
    wieder nicht ja. Im Betrieb mehrfach so passiert.

    Gibt None zurueck, wenn es nichts Genaueres zu sagen gibt; dann
    bleibt es beim NACHHAKEN.
    """
    e = eingabe or {}
    if werkzeug == "befehl_ausfuehren":
        return (f"Er würde {schutz.absicht_lang(e.get('befehl'))}. "
                "Soll ich?")
    if werkzeug in ("datei_lesen", "datei_schreiben", "ordner_ansehen",
                    "ordner_durchsuchen"):
        return (f"Es geht um {schutz.sprechbar(e.get('pfad'))}. "
                "Soll ich das machen?")
    return None


NACHHAKEN = "Ich habe das nicht verstanden. Ja oder nein?"
ABGELEHNT = "Gut, ich lasse es."
ABGELAUFEN = "Ich habe keine Antwort bekommen und lasse es lieber."
