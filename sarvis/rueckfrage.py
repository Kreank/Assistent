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


def _ohne_freigabe(text: str) -> str:
    """Die Freigabewendung herausschneiden, was uebrig bleibt zaehlt.

    "frag nicht mehr nach" traegt ein "nicht", das nichts ablehnt -- es
    gehoert zur Freigabe. Wer den ganzen Satz gegen die Nein-Liste
    haelt, liest ausgerechnet in der gebraeuchlichsten Zustimmung einen
    Einwand.
    """
    for m in _FREIGABE:
        text = re.sub(m, " ", text)
    return " ".join(text.split())


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
        #
        # Die Freigabewendung wird vorher herausgeschnitten. Sonst las
        # das "nicht" aus "ja, frag nicht mehr nach" als Einwand: Der
        # Satz fiel in den Anders-Zweig, die Handlung lief NICHT, die
        # Freigabe entstand NICHT, und gefragt wurde weiter. Gemessen:
        # deuten("ja, frag nicht mehr nach") -> "anders", waehrend
        # freigabe_erkennen() denselben Satz mit 30 Minuten erkennt --
        # zwei Funktionen derselben Datei, die sich widersprachen.
        rest = _ohne_freigabe(rest)
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
    # Dieselbe fehlende Wortgrenze wie bei "termin"/"min": ohne \b machte
    # "mach das immer freitags" eine Dauerfreigabe auf.
    r"nicht\s+jedes\s+mal", r"immer\s+(erlaubt|frei)\b",
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

    # Eine Zeitangabe allein reicht NICHT mehr. Vorher tat sie es, und
    # damit wurde aus "ja, ich habe in einer stunde einen termin" eine
    # Stunde Blankoerlaubnis fuer das Werkzeug -- gemessen 60.0. Die
    # Wendung muss ausgesprochen sein; die Dauer verfeinert sie nur.
    if not any(re.search(m, t) for m in _FREIGABE):
        return None
    dauer = _dauer_lesen(t)
    return dauer if dauer is not None else config.FREIGABE_MINUTEN


def _dauer_lesen(t: str) -> float | None:
    # Die Wortgrenze steht vorn als Rueckblick und nicht als \b: "termin"
    # endet auf "min" und ergab damit eine Freigabe von einer Minute, auf
    # ein blosses "ja" hin. Mit \b davor fiele dafuer "30min" heraus --
    # das schreibt Whisper so, und gemeint ist es auch so.
    treffer = re.search(
        r"(\d+|" + "|".join(_ZAHLWORT) + r")?\s*"
        r"(?<![A-Za-zÄÖÜäöüß])(minuten|minute|min|stunden|stunde|std)\b", t)
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


# Die eingebauten Werkzeuge des SDK heissen englisch und tragen englische
# Feldnamen. Vorgelesen wurde daraus "Soll ich Read ausfuehren, mit file
# path Schraegstrich srv Schraegstrich data ..." -- ein Werkzeugname, den
# niemand kennt, und ein Pfad Zeichen fuer Zeichen. Genau die Frage, die
# man nicht beantwortet, sondern ertraegt.
#
# Statt dafuer eigene Saetze zu schreiben, werden sie auf die deutschen
# Werkzeuge abgebildet, deren Formulierungen daruntersehen schon stimmen.
# Das bringt zwei Dinge geschenkt, die eine zweite Fassung nur wieder
# verlieren wuerde: die Warnung vor Zugangsdaten beim Lesen, und die
# Unterscheidung zwischen Anlegen und Ueberschreiben beim Schreiben.
_EINGEBAUT = {
    "Read":       ("datei_lesen",         {"pfad": "file_path"}),
    "Write":      ("datei_schreiben",     {"pfad": "file_path"}),
    "Glob":       ("ordner_durchsuchen",  {"pfad": "path",
                                           "muster": "pattern"}),
    "Grep":       ("ordner_durchsuchen",  {"pfad": "path",
                                           "muster": "pattern"}),
    "Bash":       ("befehl_ausfuehren",   {"befehl": "command"}),
    "PowerShell": ("befehl_ausfuehren",   {"befehl": "command"}),
}


def _uebersetzen(werkzeug: str, eingabe: dict):
    """Englisches Werkzeug -> deutsches Werkzeug samt umbenannter Felder.

    Gibt (None, eingabe) zurueck, wenn es keine Entsprechung gibt -- dann
    bleibt alles wie vorher.
    """
    treffer = _EINGEBAUT.get(werkzeug)
    if treffer is None:
        return None, eingabe
    deutsch, felder = treffer
    e = eingabe or {}
    return deutsch, {ziel: e.get(quelle) for ziel, quelle in felder.items()
                     if e.get(quelle) is not None}


def formulieren(werkzeug: str, eingabe: dict) -> str:
    """Aus Werkzeug und Eingabe eine Frage machen, die man hören kann."""
    e = eingabe or {}

    # Edit hat keine deutsche Entsprechung: datei_schreiben unterscheidet
    # zwischen Anlegen und Ueberschreiben, Edit tut weder das eine noch
    # das andere -- es aendert eine Stelle in einer bestehenden Datei.
    if werkzeug == "Edit":
        return f"Soll ich etwas in {schutz.sprechbar(e.get('file_path'))} ändern?"

    deutsch, umbenannt = _uebersetzen(werkzeug, e)
    if deutsch is not None:
        return formulieren(deutsch, umbenannt)

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

    if werkzeug == "datei_schicken":
        pfad = e.get("pfad") or ""
        if schutz.heikel(pfad):
            return (f"Achtung: {schutz.sprechbar(pfad)} enthält vermutlich "
                    "Zugangsdaten. Soll ich sie dir trotzdem schicken?")
        return f"Soll ich dir {schutz.sprechbar(pfad)} schicken?"

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
        bezug = (" als Antwort auf eine frühere Nachricht"
                 if e.get("antwort_auf") else "")
        return (f"Soll ich {an}{bezug} schreiben: "
                f"{_kuerzen(e.get('text'))}?")

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

    if werkzeug == "auftrag_fortsetzen":
        return (f"Soll ich Auftrag {e.get('nummer')} dort fortsetzen, "
                "wo er aufgehört hat?")

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

    if werkzeug == "mail_einsortieren":
        anzahl = e.get("anzahl") or 1
        was = "eine Mail" if int(anzahl) == 1 else f"{anzahl} Mails"
        label = _kuerzen(e.get("label"), 40)
        suche = _kuerzen(e.get("suche"), 40)
        if e.get("abnehmen"):
            # "bei eine Mail" -- der Dativ braucht eine eigene Form.
            bei = "einer Mail" if int(anzahl) == 1 else f"{anzahl} Mails"
            return f"Soll ich bei {bei} zu {suche} das Label {label} abnehmen?"
        # Beides muss in die Frage, weil man beides der Mail hinterher nicht
        # mehr ansieht: dass sie aus dem Posteingang verschwindet, und dass
        # dabei ein Label entsteht, das es vorher nicht gab.
        raus = " und aus dem Posteingang nehmen" if e.get("aus_posteingang") else ""
        frage = f"Soll ich {was} zu {suche} nach {label} einsortieren{raus}?"
        if e.get("anlegen"):
            frage += " Das Label lege ich dabei neu an."
        return frage

    if werkzeug == "dauerauftrag_anlegen":
        # Zwei Kleinigkeiten, die nur beim VORLESEN auffallen: Ein Minus
        # vor dem Betrag spricht Piper nicht, es verschwindet einfach --
        # aus "-312,00" wuerde eine Einnahme. Und der Rhythmus steht in
        # der Schnittstelle ohne Umlaut ("jaehrlich"). Beides kommt hier
        # aus finanzen.py, damit es nur eine Fassung davon gibt.
        from .werkzeuge.finanzen import _rhythmus
        roh = str(e.get("betrag") or "").strip()
        richtung = "raus" if roh.startswith("-") else "rein"
        betrag = roh.lstrip("-") or "dem genannten Betrag"
        return (f"Soll ich einen Dauerauftrag {_kuerzen(e.get('name'), 40)} "
                f"über {betrag} Euro {richtung} anlegen, "
                f"{_rhythmus(e.get('rhythmus') or 'monatlich')} ab "
                f"{e.get('start') or 'dem genannten Datum'}?")

    if werkzeug == "dauerauftrag_buchen":
        # Das "bis" MUSS in die Frage. Es ist der einzige Unterschied
        # zwischen "bucht den faelligen Monat" und "legt drei Jahre
        # Buchungen an" -- und zurueckholen laesst sich das nicht.
        bis = e.get("bis")
        return ("Soll ich die fälligen Daueraufträge buchen"
                + (f", alles bis {bis}?" if bis else " bis heute?"))

    if werkzeug == "telegram_medium_holen":
        return (f"Soll ich das Medium aus Nachricht "
                f"{e.get('nachricht_id')} im Chat mit "
                f"{_kuerzen(e.get('chat'), 30)} herunterladen?")

    if werkzeug == "mail_anhang_holen":
        # Der Dateiname gehoert in die Frage, nicht der Suchausdruck: Was
        # auf der Platte landet, ist die Datei -- und ihr Name ist das
        # Einzige daran, was der Nutzer vorher beurteilen kann.
        datei = _kuerzen(e.get("datei") or "", 45)
        was = f"den Anhang {datei}" if datei else "den Anhang"
        if e.get("nummer"):
            was = f"Anhang Nummer {e.get('nummer')}"
        return (f"Soll ich {was} aus der Mail zu "
                f"{_kuerzen(e.get('suche'), 40)} herunterladen?")

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


# --- Zwei weitere Zurufe, die nicht ans Hirn gehoeren ---------------------
#
# Beide aus demselben Grund wie ist_stopp: Wer "nochmal" sagt, will die
# letzte Antwort hoeren und keine Antwort AUF das Wort "nochmal". Und wer
# "sei zehn Minuten still" sagt, will Ruhe -- nicht die gesprochene
# Zusage, ab jetzt still zu sein.

_NOCHMAL = {"nochmal", "nochmals", "wiederhol", "wiederhole", "wiederholen",
            "wiederholung"}
_NOCHMAL_PAARE = (("sag", "nochmal"), ("noch", "mal"), ("was", "sagtest"),
                  ("nicht", "verstanden"), ("was", "war"))


def ist_nochmal(text: str) -> bool:
    """Heisst das: sag deine letzte Antwort noch einmal?

    Eng gehalten. "Nochmal" kommt auch mitten in einem Auftrag vor
    ("schick das nochmal an Julian"), und dort waere eine Wiederholung
    falsch. Deshalb nur bei kurzen Zurufen und nur, wenn sonst nichts
    Inhaltliches danebensteht.
    """
    worte = [w.strip('.,!?;:-–"\'„“»«') for w in (text or "").lower().split()]
    menge = {w for w in worte if w}
    if not menge or len(worte) > 4:
        return False
    if menge & _ANDERES:
        return False
    if menge & _NOCHMAL:
        return True
    return any(a in menge and b in menge for a, b in _NOCHMAL_PAARE)


_RUHE_WORTE = {"ruhe", "still", "leise", "pause", "psst", "sch"}
_RUHE_PAARE = (("sei", "still"), ("sei", "leise"), ("nicht", "reden"),
               ("halt", "kurz"), ("mund", "halten"))
_WIEDER_WORTE = {"weiter", "weitermachen", "weiterreden", "wieder"}

# Woerter, an denen eine Frage erkennbar ist. Sie schliessen die
# Ruhe-Bitte aus -- nicht das Wiederholen, denn "was war das" IST eine
# Frage und genau der Fall, um den es dort geht.
_FRAGEWOERTER = {"wie", "warum", "wieso", "weshalb", "wann", "wo", "wer",
                 "welche", "welcher", "welches", "wieviel", "ob"}

# Zahlwoerter, die gesprochen ankommen. Eine Ziffer schreibt Whisper
# selten -- "zehn Minuten" ist der Normalfall, "10 Minuten" die Ausnahme.
_ZAHLEN = {
    "eine": 1, "einer": 1, "zwei": 2, "drei": 3, "vier": 4, "fünf": 5,
    "fuenf": 5, "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
    "elf": 11, "zwölf": 12, "zwoelf": 12, "fünfzehn": 15, "fuenfzehn": 15,
    "zwanzig": 20, "dreißig": 30, "dreissig": 30, "vierzig": 40,
    "fünfundvierzig": 45, "fuenfundvierzig": 45, "sechzig": 60,
    "halbe": 30,
}


def ist_ruhe(text: str) -> float | None:
    """Heisst das: sei eine Weile still? Rueckgabe: Minuten, sonst None.

    Ohne genannte Dauer eine Viertelstunde -- lang genug fuer ein
    Telefonat oder einen Kunden im Raum, kurz genug, dass ein
    vergessenes "wieder da" nicht den halben Tag kostet.
    """
    roh = (text or "").lower()
    worte = [w.strip('.,!?;:-–"\'„“»«') for w in roh.split()]
    menge = {w for w in worte if w}
    if not menge or len(worte) > 6:
        return None
    if menge & _ANDERES or menge & _WIEDER_WORTE:
        return None
    # Eine FRAGE ist keine Bitte. "Wie leise ist das?" enthaelt "leise"
    # und meint das Gegenteil von Ruhe -- gemessen, das war ein echter
    # Fehlalarm. Wer still haben will, fragt nicht danach.
    if menge & _FRAGEWOERTER:
        return None
    treffer = bool(menge & _RUHE_WORTE) or any(
        a in menge and b in menge for a, b in _RUHE_PAARE)
    if not treffer:
        return None
    # "Stunde" vor "Minute" pruefen -- sonst wird aus einer Stunde eine
    # Minute, weil beide Woerter im selben Satz stehen koennen.
    einheit = 60.0 if ("stunde" in roh or "stunden" in roh) else 1.0
    for w in worte:
        if w.isdigit():
            return min(int(w) * einheit, 480.0)
        if w in _ZAHLEN:
            return min(_ZAHLEN[w] * einheit, 480.0)
    if einheit == 60.0:
        return 60.0
    return 15.0


def ist_wieder_da(text: str) -> bool:
    """Hebt die Ruhe auf: "wieder da", "du kannst wieder reden"."""
    worte = [w.strip('.,!?;:-–"\'„“»«') for w in (text or "").lower().split()]
    menge = {w for w in worte if w}
    if not menge or len(worte) > 5:
        return False
    return bool(menge & _WIEDER_WORTE)


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
    if werkzeug == "Edit":
        return (f"Es geht um {schutz.sprechbar(e.get('file_path'))}. "
                "Soll ich das machen?")
    deutsch, umbenannt = _uebersetzen(werkzeug, e)
    if deutsch is not None:
        return genauer(deutsch, umbenannt)
    if werkzeug == "befehl_ausfuehren":
        return (f"Er würde {schutz.absicht_lang(e.get('befehl'))}. "
                "Soll ich?")
    if werkzeug in ("datei_lesen", "datei_schreiben", "ordner_ansehen",
                    "ordner_durchsuchen", "datei_schicken"):
        return (f"Es geht um {schutz.sprechbar(e.get('pfad'))}. "
                "Soll ich das machen?")
    return None


NACHHAKEN = "Ich habe das nicht verstanden. Ja oder nein?"
ABGELEHNT = "Gut, ich lasse es."
ABGELAUFEN = "Ich habe keine Antwort bekommen und lasse es lieber."
