"""Aussprache: Text so umschreiben, dass Piper ihn richtig vorliest.

Warum es diese Datei ueberhaupt gibt: Piper phonemisiert ueber espeak-ng,
und espeak liest Zahlen zwar, aber nach eigenen Regeln. Gemessen wurde,
was espeak wirklich erzeugt (piper.phonemize_espeak.EspeakPhonemizer),
nicht geraten:

    "bis 31.12.2029"   -> "einunddreissig PUNKT zwoelf PUNKT zweitausend..."
    "20000,66 Euro"    -> "zwanzigtausend KOMMA sechs sechs Euro"
    "um 15:30 Uhr"     -> "um fuenfzehn UHR dreissig UHR"
    "am 22. Maerz"     -> "am zweiundzwanzig.Maerz"

Vier Sorten Fehler: Satzzeichen werden woertlich gesprochen ("Punkt",
"Komma"), Cent werden ziffernweise gelesen, bei Uhrzeiten kommt ein
zweites "Uhr", und Ordinalzahlen bleiben Grundzahlen.

Was NICHT das Problem ist: der Tausenderpunkt. "1.098,00" liest espeak
korrekt als "eintausendachtundneunzig". Ein Kommentar in
werkzeuge/finanzen.py behauptet das Gegenteil -- der stammt aus einer
aelteren Messung und stimmt nicht mehr.

Die Regeln greifen NUR dort, wo espeak nachweislich falsch liegt.
Alles andere bleibt unangetastet -- besonders die gewoehnliche
Dezimalzahl ("3,5") und Prozentangaben ("31,55 Prozent"): da ist "Komma"
die richtige Ansage, das ist kein Geld. Text ohne Ziffern verlaesst die
Funktion unveraendert und ohne einen einzigen Regex-Durchlauf.

Keine neue Abhaengigkeit: die deutschen Zahlwoerter stehen hier.
"""
import re

# Umlaute stehen bewusst in den Zeichenketten (nicht in den Kommentaren):
# espeak spricht "fünf" und "fuenf" beides richtig, aber "dreissig" wird
# zu "drei-ssig" nur, wenn man Glueck hat -- "dreißig" ist eindeutig.
_EINER = [
    "null", "eins", "zwei", "drei", "vier", "fünf", "sechs", "sieben",
    "acht", "neun", "zehn", "elf", "zwölf", "dreizehn", "vierzehn",
    "fünfzehn", "sechzehn", "siebzehn", "achtzehn", "neunzehn",
]
_ZEHNER = {
    2: "zwanzig", 3: "dreißig", 4: "vierzig", 5: "fünfzig",
    6: "sechzig", 7: "siebzig", 8: "achtzig", 9: "neunzig",
}

MONATE = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober",
    11: "November", 12: "Dezember",
}


def _bis_hundert(n: int) -> str:
    if n < 20:
        return _EINER[n]
    einer, zehner = n % 10, _ZEHNER[n // 10]
    if not einer:
        return zehner
    # "einundzwanzig", nicht "einsundzwanzig" -- die 1 verliert im
    # Verbund ihr s.
    return ("ein" if einer == 1 else _EINER[einer]) + "und" + zehner


def _bis_tausend(n: int) -> str:
    hundert, rest = n // 100, n % 100
    if not hundert:
        return _bis_hundert(n)
    wort = ("ein" if hundert == 1 else _EINER[hundert]) + "hundert"
    return wort + (_bis_hundert(rest) if rest else "")


def zahlwort(n: int) -> str:
    """Ganze Zahl als deutsches Zahlwort.

    Ab einer Million wird getrennt geschrieben, weil "Million" ein
    Substantiv ist und espeak sonst ein Wortungetuem phonemisiert.
    """
    if n < 0:
        return "minus " + zahlwort(-n)
    if n < 1000:
        return _bis_tausend(n)
    if n < 10 ** 6:
        tausend, rest = n // 1000, n % 1000
        wort = ("ein" if tausend == 1 else _bis_tausend(tausend)) + "tausend"
        return wort + (_bis_tausend(rest) if rest else "")
    for grenze, eins, viele in (
        (10 ** 9, "eine Million", "Millionen"),
        (10 ** 12, "eine Milliarde", "Milliarden"),
        (10 ** 15, "eine Billion", "Billionen"),
    ):
        if n < grenze:
            teiler = grenze // 1000
            kopf, rest = n // teiler, n % teiler
            wort = eins if kopf == 1 else zahlwort(kopf) + " " + viele
            return wort + (" " + zahlwort(rest) if rest else "")
    # Jenseits von Billionen wird niemand mehr zuhoeren; ziffernweise
    # ist dann ehrlicher als ein falsch zusammengesetztes Wort.
    return " ".join(_EINER[int(z)] for z in str(n))


# Unregelmaessige Ordinalzahlen. Der Rest ist Grundzahl + "te" (unter 20)
# bzw. + "ste" (ab 20).
_ORDINAL_SONDER = {1: "erste", 3: "dritte", 7: "siebte", 8: "achte"}

# Nach diesen Woertern steht die Ordinalzahl im Nominativ/Akkusativ
# Neutrum und bleibt endungslos: "der 3." -> "der dritte".
_NOMINATIV = {
    "der", "die", "das", "ein", "eine", "dieser", "diese", "dieses",
    "jeder", "jede", "jedes", "welcher", "welche", "welches",
}


def ordnungszahl(n: int, endung: str = "n") -> str:
    """'22' -> 'zweiundzwanzigste' bzw. mit endung='n' 'zweiundzwanzigsten'.

    BEWUSST NICHT GELOEST: die volle Kasus-Beugung. Richtig waere sie nur
    mit Satzanalyse -- "am 22. März" braucht "zweiundzwanzigsten", "der
    22. März" braucht "zweiundzwanzigste". Geloest ist nur der Blick auf
    das unmittelbar vorangehende Wort (siehe _endung); alles andere
    bekommt "-sten", weil Datumsangaben in Sarvis' Antworten fast immer
    nach "am", "vom", "seit", "bis" oder "zum" stehen. Eine falsche
    Endung ist hoerbar, aber verstaendlich -- eine ausgelassene Zahl
    nicht.
    """
    if n < 20:
        stamm = _ORDINAL_SONDER.get(n) or (_EINER[n] + "te")
    else:
        stamm = zahlwort(n) + "ste"
    return stamm + endung


def _endung(text: str, stelle: int) -> str:
    """Endung der Ordinalzahl aus dem Wort davor. Standard: '-n'."""
    davor = text[:stelle].rstrip()
    wort = re.split(r"[^\wÄÖÜäöüß]+", davor)[-1].lower() if davor else ""
    return "" if wort in _NOMINATIV else "n"


def jahreszahl(j: int) -> str:
    """Jahre von 1100 bis 1999 spricht man in Hundertern.

    "1998" ist "neunzehnhundertachtundneunzig", nicht "eintausend...".
    Ab 2000 gilt wieder die Grundzahl -- so sagt man es, und so macht es
    espeak von selbst.
    """
    if 1100 <= j <= 1999:
        rest = j % 100
        return _EINER[j // 100] + "hundert" + (_bis_hundert(rest) if rest else "")
    return zahlwort(j)


def _datumswort(text: str, stelle: int, tag: int, monat: int, jahr=None) -> str:
    teile = [ordnungszahl(tag, _endung(text, stelle)), MONATE[monat]]
    if jahr is not None:
        teile.append(jahreszahl(jahr))
    return " ".join(teile)


def _uhrzeitwort(stunde: int, minute: int, sekunde=None) -> str:
    # "ein Uhr", nicht "eins Uhr" -- vor dem Substantiv faellt das s weg.
    wort = ("ein" if stunde == 1 else zahlwort(stunde)) + " Uhr"
    if minute:
        wort += " " + zahlwort(minute)
    if sekunde:
        wort += " und " + zahlwort(sekunde) + " Sekunden"
    return wort


def _betragswort(vorzeichen: str, ganz: int, cent: int) -> str:
    """Geldbetrag als Satz.

    Drei Entscheidungen, die man hoert:
    - Glatte Betraege OHNE "null null": "1.098,00 Euro" ist
      "eintausendachtundneunzig Euro". Niemand sagt die Nullen mit.
    - Die Cent werden als EINE Zahl gesprochen und hinter die Waehrung
      gestellt: "vierzehn Euro neunundachtzig". Genau das ist die Form,
      die man am Tresen hoert -- espeak liest stattdessen "acht neun".
    - Das Minus wird ausgesprochen. espeak verschluckt das Zeichen
      lautlos, und ein verschlucktes Minus dreht die Aussage um.
    """
    teile = []
    if vorzeichen:
        teile.append("minus")
    if ganz == 0 and cent:
        # "0,99 Euro" ist "neunundneunzig Cent", nicht "null Euro ...".
        teile.append("ein Cent" if cent == 1 else zahlwort(cent) + " Cent")
        return " ".join(teile)
    teile.append("ein Euro" if ganz == 1 else zahlwort(ganz) + " Euro")
    if cent:
        # Unter zehn Cent kommt "Cent" dazu. Ohne das waere "7,05 Euro"
        # als "sieben Euro fünf" nicht von "7,50 Euro" ("sieben Euro
        # fünfzig") zu unterscheiden -- beim Zuhoeren zaehlt niemand
        # Stellen mit.
        if cent < 10:
            teile.append(("ein" if cent == 1 else zahlwort(cent)) + " Cent")
        else:
            teile.append(zahlwort(cent))
    return " ".join(teile)


def _cent(gruppe) -> int:
    """',5' sind fuenfzig Cent, nicht fuenf -- rechts auffuellen."""
    if not gruppe:
        return 0
    return int(gruppe.ljust(2, "0"))


def _ganz(gruppe: str) -> int:
    return int(gruppe.replace(".", ""))


# --- Muster -------------------------------------------------------------
#
# Die Reihenfolge ist Teil der Logik: ISO-Datum vor der Uhrzeit (sonst
# reisst die Uhrzeit den Zeitstempel auseinander), volles Datum vor dem
# kurzen, und Geld vor der allgemeinen Minus-Regel.
#
# Alle Muster sind gegen Ziffern links und rechts abgeriegelt, damit
# nichts mitten aus einer laengeren Zahl herausgeschnitten wird --
# "1.098.000" darf nicht als Datum durchgehen.

_ISO = re.compile(
    r"(?<![\d-])(\d{4})-(\d{2})-(\d{2})"
    r"(?:[T ](\d{2}):(\d{2})(?::(\d{2}))?)?(?!\d)")

_UHRZEIT_PUNKT = re.compile(
    r"(?<![\d.,:])([01]?\d|2[0-3])\.([0-5]\d)\s*Uhr\b")

_DATUM = re.compile(r"(?<![\d.,])(\d{1,2})\.(\d{1,2})\.(\d{4})(?!\d)")

_DATUM_KURZ = re.compile(r"(?<![\d.,])(\d{1,2})\.(\d{1,2})\.(?!\d)")

_MONATSNAMEN = ("Januar|Februar|März|Maerz|April|Mai|Juni|Juli|August|"
                "September|Oktober|November|Dezember")
_TAG_MONAT = re.compile(r"(?<![\d.,])(\d{1,2})\.\s*(" + _MONATSNAMEN + r")\b")

_UHRZEIT = re.compile(
    r"(?<![\d.,:])([01]?\d|2[0-3]):([0-5]\d)(?::([0-5]\d))?(?!\d)"
    r"(?:\s*Uhr\b)?")

_ZAHLKOPF = r"(\d{1,3}(?:\.\d{3})+|\d+)"
_GELD_NACH = re.compile(
    r"(?<![\w.,\-−])([-−])?" + _ZAHLKOPF + r"(?:,(\d{1,2}))?"
    r"\s*(?:€|Euro\b|EUR\b)", re.IGNORECASE)
_GELD_VOR = re.compile(
    r"(?:€|EUR\b)\s*([-−])?" + _ZAHLKOPF + r"(?:,(\d{1,2}))?(?![\d,])",
    re.IGNORECASE)

_ORDINAL = re.compile(
    r"\b(am|vom|zum|beim|im|seit|ab|der|die|das|dem|den|des)"
    r"\s+(\d{1,3})\.(?!\d)")

# Ein Minus vor einer Zahl spricht espeak gar nicht. Nur am Wortanfang,
# damit Bereiche ("10-15") und Bindestriche in Woertern nichts abbekommen.
_MINUS = re.compile(r"(?<![\w.,\-−])[-−](?=\d)")

_ZIFFER = re.compile(r"\d")


def _ersetze_iso(m: re.Match) -> str:
    jahr, monat, tag = int(m[1]), int(m[2]), int(m[3])
    if not (1 <= monat <= 12 and 1 <= tag <= 31):
        return m[0]
    wort = _datumswort(m.string, m.start(), tag, monat, jahr)
    if m[4] is not None:
        sek = int(m[6]) if m[6] else None
        wort += " um " + _uhrzeitwort(int(m[4]), int(m[5]), sek)
    return wort


def _ersetze_datum(m: re.Match) -> str:
    tag, monat = int(m[1]), int(m[2])
    if not (1 <= monat <= 12 and 1 <= tag <= 31):
        # Kein gueltiges Datum -- unveraendert lassen. Was hier steht,
        # ist entweder eine Versionsnummer oder ein Tippfehler; beides
        # zu einem Datum zu verbiegen waere schlimmer als der "Punkt".
        return m[0]
    # Dieselbe Funktion bedient beide Muster: das kurze Datum ("22.03.")
    # hat schlicht keine dritte Gruppe.
    jahr = int(m[3]) if m.re.groups >= 3 else None
    return _datumswort(m.string, m.start(), tag, monat, jahr)


def _ersetze_tag_monat(m: re.Match) -> str:
    tag = int(m[1])
    if not 1 <= tag <= 31:
        return m[0]
    # Der Monatsname bleibt so stehen, wie er dasteht: espeak spricht
    # "Maerz" und "März" gleich aus.
    return ordnungszahl(tag, _endung(m.string, m.start())) + " " + m[2]


def _ersetze_uhrzeit(m: re.Match) -> str:
    sek = int(m[3]) if m[3] else None
    return _uhrzeitwort(int(m[1]), int(m[2]), sek)


def _ersetze_uhrzeit_punkt(m: re.Match) -> str:
    return _uhrzeitwort(int(m[1]), int(m[2]))


def _ersetze_geld(m: re.Match) -> str:
    return _betragswort(m[1] or "", _ganz(m[2]), _cent(m[3]))


def _ersetze_ordinal(m: re.Match) -> str:
    zahl = int(m[2])
    if zahl == 0:
        return m[0]
    endung = "" if m[1].lower() in _NOMINATIV else "n"
    return m[1] + " " + ordnungszahl(zahl, endung)


_REGELN = (
    (_ISO, _ersetze_iso),
    (_UHRZEIT_PUNKT, _ersetze_uhrzeit_punkt),
    (_DATUM, _ersetze_datum),
    (_DATUM_KURZ, _ersetze_datum),
    (_TAG_MONAT, _ersetze_tag_monat),
    (_UHRZEIT, _ersetze_uhrzeit),
    (_GELD_VOR, _ersetze_geld),
    (_GELD_NACH, _ersetze_geld),
    (_ORDINAL, _ersetze_ordinal),
    (_MINUS, "minus "),
)


def vorlesbar(text: str) -> str:
    """Schreibt Zahlen, Geld, Datum und Uhrzeit so um, wie man sie sagt.

    Laeuft vor JEDEM gesprochenen Satz, deshalb der Schnellausstieg: ohne
    Ziffer im Text kann keine Regel greifen, und das ist der haeufigste
    Fall.

    Faellt hier etwas um, wird der Originaltext gesprochen. Ein
    unschoener Satz ist besser als ein stummer Assistent -- diese
    Funktion sitzt zwischen Antwort und Stimme, sie darf nie der Grund
    sein, dass gar nichts kommt.
    """
    if not text or not _ZIFFER.search(text):
        return text
    original = text
    try:
        for muster, ersatz in _REGELN:
            text = muster.sub(ersatz, text)
        return text
    except Exception:
        return original
