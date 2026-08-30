"""Fachklassen -- vom zugerufenen Wortlaut zur sauberen Position.

WARUM DIE LUECKE UEBERHAUPT DA IST

Sascha diktiert "Kugelhahn 4-Wege 1 Zoll". Der Artikelstamm hat zwei
Millionen Positionen. Zwischen beidem liegt kein Suchproblem, sondern
ein Sprachproblem: Was gesprochen wird, ist eine Kurzform; was im
Stamm steht, ist ein Langtext mit Herstellerhandschrift. Wer den
Wortlaut ungefiltert in die Artikelsuche kippt, bekommt entweder
nichts oder alles.

Das buildingSMART Data Dictionary schliesst genau diese Luecke. Es
kennt die Branchenklassifikation, und zwar auf Deutsch: "Kugelhahn"
ist dort eine Klasse mit einem Code, einem Elternknoten und
achtundfuenfzig benannten Merkmalen. Damit laesst sich der Zuruf auf
etwas Eindeutiges normalisieren, BEVOR die Artikelsuche losgeht.

DER EIGENTLICHE GEWINN SIND DIE RUECKFRAGEN

Eine Klasse zu treffen ist die halbe Sache. Die andere Haelfte ist zu
wissen, was am Zuruf noch fehlt. Die Merkmalsliste der Klasse ist
genau diese Checkliste -- und weil sie aus der Branchennorm kommt und
nicht aus dem Modell, fragt Sarvis nach der Nennweite und der
Anschlussart statt nach irgendetwas, das plausibel klingt.

WARUM ETIM UND NICHT IRGENDEIN VERZEICHNIS

Das bSDD haelt vierhundert Verzeichnisse, davon einundvierzig mit
deutschen Bezeichnungen. Fuer SHK zaehlt nur eines: ETIM. Es ist die
Klassifikation, nach der der Grosshandel seine Artikeldaten ausliefert
-- dieselbe Welt, aus der auch der Artikelstamm stammt. Die anderen
deutschen Verzeichnisse beschreiben Bauwerke, keine Bauteile.

Festgenagelt ist ETIM 10.0 und nicht die neuere 10.1: die 10.1 gibt es
bisher nur auf Englisch. Ein deutsches Merkmal aus einer aelteren
Fassung ist mehr wert als ein englisches aus der neuen.

WAS DIE SCHNITTSTELLE NICHT KANN -- GEMESSEN, NICHT VERMUTET

  Mehrwortsuche gibt es nicht. "Kugelhahn 1 Zoll" liefert null
  Treffer, "Kugelhahn" acht. Die Suche vergleicht die ganze Zeichen-
  kette, sie zerlegt sie nicht. Deshalb sucht _suchen() in Stufen und
  faellt auf einzelne Woerter zurueck.

  Umlaute sind Pflicht. "Heizkoerper" findet nichts, "Heizkörper"
  fuenfundvierzig. Ein Diktat liefert richtige Umlaute, ein tippendes
  Modell nicht immer -- darum die Rueckuebersetzung in _umlaute().

  Die deutsche Trefferliste kommt nach Code sortiert. Beim Wort
  "Heizkörper" steht "Pinsel" vor "Heizkörperventil". Die Reihenfolge
  muss hier entstehen, sonst ist die Antwort unbrauchbar -- und weil
  der Name allein nicht reicht (ETIM nennt den Waschtisch
  "Waschbecken"), kommt die Naehe aus einem zweiten Endpunkt dazu.

  Eine Klasse samt Merkmalen zu holen dauert drei bis neunzehn
  Sekunden -- hundert Kilobyte, gemessen. Deshalb der
  Zwischenspeicher, deshalb liefert fachklasse_suchen nur Namen und
  Codes, und deshalb laedt ein Hintergrundfaden die haeufigen Klassen
  schon beim Start (_VORRAT). Im Auto ist das der Unterschied zwischen
  einer Antwort und einem abgerissenen Gespraech.

  Welches Merkmal wichtig ist, sagt ETIM NICHT. Es gibt kein
  Pflichtkennzeichen. Was hier vorne steht, ist eine Setzung dieses
  Moduls (_GRUPPEN) -- Anschluss und Werkstoff vor Pruefsiegeln.

WER BEI KNAPPER LEITUNG GEWINNT

Immer der, der gefragt hat. Der Vorlader haelt still, solange ein
Zuruf laeuft, und es geht nur eine Abfrage zur Zeit hinaus. Beides
steht in _holen, und beides steht dort, weil das Gegenteil gemessen
wurde: Ohne die Regeln verbrauchte der Vorlader die Abfragen und der
Zuruf bekam nach acht Sekunden "das Verzeichnis bremst mich aus" --
schlechter als ganz ohne Vorladen.

Quelle: buildingSMART Data Dictionary (api.bsdd.buildingsmart.org),
Verzeichnis ETIM 10.0, Lizenz ODC-By 1.0. Lesende Abfragen brauchen
keine Anmeldung.
"""
import re
import threading
import time

import httpx
from claude_agent_sdk import tool

API = "https://api.bsdd.buildingsmart.org"

# ETIM 10.0 -- die neueste Fassung MIT deutschen Bezeichnungen. Die 10.1
# ist neuer, aber englisch, und damit fuer den Zweck hier wertlos.
ETIM = "https://identifier.buildingsmart.org/uri/etim/etim/10.0"
SPRACHE = "de-DE"

ZEITGRENZE = 25.0

# Wie die Merkmalsgruppen von ETIM heissen (englisch, auch in der
# deutschen Fassung) und wie sie hier heissen sollen. Die Zahl ist der
# Rang: kleiner heisst weiter vorn. Das ist die Handwerkersicht --
# womit wird es angeschlossen, woraus ist es, wie ist es gebaut. Was
# ein Pruefsiegel hat, entscheidet keine Bestellung.
_GRUPPEN = {
    "Connection":               (0, "Anschluss"),
    "Material":                 (1, "Werkstoff"),
    "Model , type":             (2, "Bauart"),
    "Setting , control":        (3, "Bedienung und Regelung"),
    "Electrical":               (3, "Elektrisch"),
    "Other":                    (4, "Sonstiges"),
    "Operating conditions":     (5, "Betriebsbedingungen"),
    "Measurements":             (6, "Maße"),
    "Options":                  (7, "Ausstattung"),
    "Approval , certification": (9, "Zulassungen"),
}
_GRUPPE_UNBEKANNT = (5, "Sonstiges")

# Merkmalsnamen, die ein Handwerker zuerst braucht, um eine Position
# eindeutig zu machen. Geprueft wird auf den Wortanfang -- "Anschluss 1"
# soll gewinnen, "Mit Kupplungsanschluss 1" nicht.
_VORNE = ("nenndurchmesser", "anschluss", "werkstoff", "material",
          "ausführung", "bauart", "bedienung", "druckstufe", "typ",
          "nennweite", "nennleistung", "leistung", "größe", "farbe",
          "inhalt", "volumen", "baulänge", "breite", "höhe", "länge")

# Was am Ende der Liste gehoert. Pruefsiegel und Konturcodes stehen in
# keinem Angebot und beantworten keine Rueckfrage.
_HINTEN = ("prüfung", "siegel", "zulassung", "kennzeichen", "zertifi",
           "geprüft", "konturcode", "arbeitslänge", "schlüsselweite",
           "wandstärke")

# Wie viele Merkmale einer Gruppe in die Kurzantwort duerfen. Ohne
# diese Grenze gewinnt "Werkstoff" mit neun Materialangaben die halbe
# Antwort, und die Anschlussart taucht gar nicht auf.
_JE_GRUPPE = 2

_UMLAUTE = (("ae", "ä"), ("oe", "ö"), ("ue", "ü"), ("Ae", "Ä"),
            ("Oe", "Ö"), ("Ue", "Ü"), ("ss", "ß"))

_CODE = re.compile(r"^E[CG]\d{6}$", re.IGNORECASE)

# Woerter, die im Diktat stehen, aber nichts klassifizieren. Neben den
# Fuellwoertern stehen hier die leeren Kopfnomen: "Element" allein
# liefert hundert Treffer vom Einschlaganker bis zum Taster, "WC-Element
# mit Betätigungsplatte" wird darueber nie richtig. Wer sie ueberspringt,
# landet beim naechsten Wort -- und das traegt Bedeutung.
_FUELLWORTE = {"mit", "ohne", "und", "oder", "der", "die", "das", "ein",
               "eine", "einen", "für", "fuer", "von", "zum", "zur", "im",
               "am", "auf", "neu", "stück", "stk", "set", "satz",
               "element", "teil", "teile", "gerät", "geraet", "system",
               "einheit", "zubehör", "zubehoer", "material", "artikel",
               "stueck", "komplett", "passend", "sonstiges"}

# --- Zwischenspeicher ---------------------------------------------------
# Eine Klasse mit allen Merkmalen sind rund hundert Kilobyte. Sarvis
# fragt typischerweise erst nach der Klasse, dann nach den Merkmalen,
# dann nach den offenen Punkten -- dreimal dasselbe Dokument. Der
# Speicher lebt so lange wie der Prozess; ETIM 10.0 aendert sich nicht
# mehr, eine Verfallszeit waere Theater.
#
# Kein Schloss. Geschrieben wird ein fertiges Dokument unter einen
# Schluessel, und das ist unter der GIL unteilbar -- ein halb
# eingetragener Eintrag kann nicht entstehen. Das Schlimmste, was der
# Vorlader und ein Zuruf gleichzeitig anrichten koennen, ist, dieselbe
# Klasse zweimal zu holen. Das kostet eine Abfrage und sonst nichts.
_KLASSEN: dict[str, dict] = {}

# --- Vorladen -----------------------------------------------------------
# Was Sascha wirklich diktiert -- und zwar nur das, was beim Messen
# GETROFFEN hat. Jede dieser Klassen wurde ueber einen zugerufenen
# Begriff gefunden und stand dabei an erster Stelle; die schoenen Faelle
# ohne Treffer (Gastherme, Brennwertkessel, Rohrisolierung hat ETIM
# nicht) stehen bewusst nicht hier. Vorgeladen wird, was sich vorladen
# LOHNT, nicht was vollstaendig aussieht.
#
# Der Grund fuer die Liste ueberhaupt: Eine kalte Klasse zu holen dauert
# drei bis neunzehn Sekunden -- hundert Kilobyte ueber eine Leitung, auf
# die wir keinen Einfluss haben. Das ist im Auto der Unterschied
# zwischen einer Antwort und einem abgerissenen Gespraech. Warm kostet
# dieselbe Frage null.
_VORRAT = (
    ("EC011343", "Kugelhahn"),
    ("EC011344", "Eckventil"),
    ("EC010136", "Heizkörperventil"),
    ("EC010064", "Thermostatkopf für Ventil"),
    ("EC011311", "Überlaufventil (das Sicherheitsventil)"),
    ("EC003261", "Absperrschieber"),
    ("EC010071", "Füll- und Entleerungshahn"),
    ("EC010980", "Umwälzpumpe"),
    ("EC010958", "Membrandruckausdehnungsgefäß"),
    ("EC011550", "Waschbecken"),
    ("EC011720", "Duschrinne"),
    ("EC010235", "Urinal"),
    ("EC011336", "Vorwandelement Wand-WC mit Druckspüler"),
    ("EC010145", "Vorwandelement Wand-WC mit Spülkasten"),
    ("EC011022", "Flachheizkörper"),
    ("EC011023", "Röhrenheizkörper"),
    ("EC004512", "Hausanschlussfilter"),
)

# Abstand zwischen zwei Klassen. Gemessen, nicht geschaetzt: Bei zwei
# und bei vier Sekunden bremst der Dienst -- und zwar den Vorlader UND
# den Zuruf, der zufaellig danebenlag. Bei zehn Sekunden laeuft eine
# Reihe von Klassen sauber durch.
#
# Der Dienst ist kostenlos und verlangt keine Anmeldung. Wer ihn im
# Schwung leerraeumt, sorgt dafuer, dass er das eines Tages nicht mehr
# ist. Und es hat niemand Eile: Der Faden laeuft im Hintergrund, und
# ob er nach vier oder nach acht Minuten fertig ist, merkt kein
# Mensch -- gebraucht wird der Vorrat erst, wenn Sascha im Auto sitzt.
_VORRAT_ABSTAND = 10.0

# Was nach einer Bremse gewartet wird, zusaetzlich zum Ruecklauf in
# _holen -- und was daraus wird, wenn es wieder passiert.
#
# Die Bremse zaehlt Abfragen ueber die Zeit, nicht gleichzeitige:
# gemessen, als der Vorlader bei vier Sekunden Abstand ausgebremst
# wurde UND der Zuruf gleich mit. Wie eng die Grenze genau ist, steht
# nirgends und kann sich aendern -- also wird sie nicht geraten,
# sondern ertastet: Bei jeder Bremse verdoppelt sich die Pause, bei
# jedem Erfolg faellt sie zurueck. So findet der Faden von selbst das
# Tempo, das der Dienst gerade zulaesst, und niemand muss eine Zahl
# pflegen, die nur zufaellig einmal gestimmt hat.
_VORRAT_BREMSPAUSE = 30.0
_VORRAT_BREMSPAUSE_MAX = 240.0

_vorlader: threading.Thread | None = None

# --- Vortritt -----------------------------------------------------------
# Beim Messen ist genau das eingetreten, wovor die Bremse warnt: Der
# Vorlader hat die Abfragen aufgebraucht, und der Zuruf, auf den es
# ankam, bekam "das Verzeichnis bremst mich gerade aus" -- nach acht
# Sekunden Warten. Das ist SCHLECHTER als gar kein Vorladen: Vorher
# wartete Sascha einmal lange und bekam seine Antwort, jetzt wartete er
# lange und bekam eine Absage.
#
# Also hat der Zuruf Vortritt. Der Vorlader haelt still, solange
# jemand fragt, und danach noch ein paar Sekunden -- ein Werkzeug macht
# zwei bis drei Abfragen hintereinander, und zwischen die gehoert
# niemand.
_ZURUF_ZULETZT = 0.0
_VORRANG_RUHE = 8.0

# Eine Abfrage zur Zeit, prozessweit.
#
# Der Vortritt allein reichte nicht: Er haelt den Vorlader an, BEVOR er
# losfaehrt -- steckt er aber schon in einer Abfrage, wenn der Zuruf
# kommt, laufen doch zwei nebeneinander, und die Bremse trifft genau
# den falschen. Gemessen: Absage nach acht Sekunden, waehrend der
# Vorlader in Ruhe fertig las.
#
# Mit dem Tor wartet der Zuruf im schlimmsten Fall EINE Abfrage lang
# (drei bis fuenf Sekunden) und bekommt dann seine Antwort, statt nach
# acht Sekunden abgewiesen zu werden. Gehalten wird es nur um den
# Netzzugriff selbst, nicht um die Ruecklaufpausen -- sonst blockierte
# ein ausgebremster Vorlader den Zuruf sieben Sekunden lang fuer
# nichts.
_LEITUNG = threading.Lock()


def _zuruecktreten() -> None:
    """Warten, bis der letzte Zuruf lange genug her ist.

    Laeuft ausschliesslich im Vorlader-Faden. Dass er dadurch laenger
    braucht, ist der Zweck und nicht der Preis: Seine Arbeit hat keinen
    Termin, die des Zurufs schon.
    """
    while True:
        ruhe = time.monotonic() - _ZURUF_ZULETZT
        if ruhe >= _VORRANG_RUHE:
            return
        time.sleep(min(1.0, _VORRANG_RUHE - ruhe))


def _holen(weg: str, **werte) -> tuple[int, dict]:
    """Ein Aufruf gegen das bSDD. (status, inhalt).

    Die Schnittstelle bremst bei schneller Folge mit 429 -- gemessen
    beim Durchprobieren mehrerer Begriffe hintereinander. Zweimal
    warten und noch einmal fragen holt das zuverlaessig auf. Laenger
    zu warten hiesse, dass Sarvis mitten im Satz stehenbleibt, und ein
    Wartender hoert lieber, dass es gerade nicht geht.

    Hier faellt auch die Entscheidung, wer bei knapper Leitung gewinnt:
    Ein Aufruf aus dem Vorlader tritt zurueck, einer aus einem Werkzeug
    nie. Das steht bewusst an dieser einen Stelle -- jeder Weg nach
    draussen laeuft durch sie, und eine zweite Stelle waere eine, die
    man beim naechsten Werkzeug vergisst.
    """
    global _ZURUF_ZULETZT
    vorlader = threading.current_thread() is _vorlader
    if vorlader:
        _zuruecktreten()
    else:
        # Vor UND nach dem Aufruf stempeln. Nur hinterher genuegte
        # nicht: Waehrend eines langen Zurufs sieht der Vorlader sonst
        # den Stempel des vorigen, haelt die Luft fuer rein und faehrt
        # mitten hinein.
        _ZURUF_ZULETZT = time.monotonic()
    try:
        for pause in (2, 5, 0):
            try:
                with _LEITUNG:
                    with httpx.Client(timeout=ZEITGRENZE) as c:
                        a = c.get(f"{API}{weg}", params=werte)
                if a.status_code == 429 and pause:
                    # Ausserhalb des Tors schlafen: Wer wartet, soll
                    # niemanden mitwarten lassen.
                    time.sleep(pause)
                    continue
                if a.status_code != 200:
                    return a.status_code, {}
                return 200, a.json()
            except (httpx.HTTPError, ValueError):
                return 0, {}
        return 429, {}
    finally:
        if not vorlader:
            _ZURUF_ZULETZT = time.monotonic()


def _umlaute(text: str) -> str:
    """'Heizkoerper' -> 'Heizkörper'.

    Nur als zweiter Versuch gedacht: 'Zuerst' wuerde sonst zu 'Züerst'.
    Wenn die erste Suche etwas findet, kommt das hier nie zum Einsatz.
    """
    for flach, echt in _UMLAUTE:
        text = text.replace(flach, echt)
    return text


def _flach(text: str) -> str:
    """Kleingeschrieben, ohne Umlaute, ohne Satzzeichen -- zum Vergleichen."""
    text = (text or "").lower()
    for flach, echt in _UMLAUTE:
        text = text.replace(echt, flach)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _begriffe(text: str) -> list[str]:
    """Aus einem Zuruf die Woerter, unter denen sich suchen laesst.

    In der Reihenfolge, in der sie gesprochen wurden. Das ist keine
    Bequemlichkeit, sondern gemessen: "Kugelhahn 1 Zoll Innengewinde
    Messing" landete beim laengsten Wort auf dem Innengewindebohrer.
    Wer eine Position diktiert, sagt zuerst, WAS es ist, und danach,
    wie es beschaffen ist.

    Zahlen und Masse fliegen raus -- unter "1" findet niemand einen
    Kugelhahn -- und die leeren Kopfnomen aus _FUELLWORTE auch.
    """
    roh = re.split(r"[^0-9A-Za-zÄÖÜäöüß/-]+", text or "")
    worte = [w.strip("-/") for w in roh if len(w.strip("-/")) >= 4]
    worte = [w for w in worte
             if w.lower() not in _FUELLWORTE and not w[0].isdigit()]
    return list(dict.fromkeys(worte))


def _rohsuche(begriff: str) -> tuple[list[dict], int]:
    stand, d = _holen("/api/Dictionary/v1/Classes", Uri=ETIM,
                      SearchText=begriff, languageCode=SPRACHE, Limit=100)
    if stand != 200:
        return [], stand
    return ([c for c in (d.get("classes") or [])
             if c.get("classType") == "Class"], 200)


def _relevanz(begriff: str) -> dict[str, int]:
    """Die Reihenfolge, in der das bSDD selbst die Treffer sieht.

    Zwei Endpunkte, zwei Haelften einer Antwort: /Dictionary/Classes
    liefert die deutschen Namen, aber nach Code sortiert.
    /TextSearch/v2 sortiert nach Naehe -- und zwar unter Einbezug der
    Synonyme, die im deutschen Namen gar nicht vorkommen -- gibt die
    Namen aber nur englisch zurueck. Also beides holen und ueber den
    Code zusammenlegen.

    Warum das noetig ist, zeigt genau ein Fall: ETIM nennt den
    Waschtisch auf Deutsch "Waschbecken". Wer nur Namen vergleicht,
    findet unter "Waschtisch" den Waschtischschluessel und nie das
    Becken. Die Synonymliste haengt an der Klasse selbst -- sie fuer
    jeden Kandidaten zu holen waere ein Dutzend Abfragen; dieser eine
    Aufruf leistet dasselbe.

    Faellt der Aufruf aus, ist das kein Fehler: dann bleibt die
    Sortierung nach Namen, die in den meisten Faellen dasselbe sagt.
    """
    stand, d = _holen("/api/TextSearch/v2", SearchText=begriff,
                      DictionaryUris=ETIM, Limit=20)
    if stand != 200:
        return {}
    # Nur die Reihenfolge wird gebraucht. Namen liefert dieser Endpunkt
    # ausschliesslich englisch -- auch den der Obergruppe, der hier
    # verlockend danebensteht. Die deutsche Obergruppe haengt an der
    # Klasse selbst und wird dort geholt, wo sie ohnehin geladen ist.
    return {c.get("code", ""): i
            for i, c in enumerate(d.get("classes") or [])}


def _punkte(name: str, begriff: str, platz: int | None = None) -> int:
    """Wie gut passt eine Klasse zum gesuchten Begriff.

    Noetig, weil das bSDD nach Code sortiert zurueckgibt und nicht nach
    Naehe. Beim Wort "Heizkörper" steht sonst "Pinsel" oben, weil sein
    Code kleiner ist.

    Gewichtet wird in dieser Reihenfolge: Ein Name, der dem Zuruf
    woertlich entspricht, gewinnt immer -- "Kugelhahn" ist der
    Kugelhahn und nicht das Zubehoer dafuer. Sonst entscheidet die
    Naehe, die das bSDD selbst sieht (platz), weil die die Synonyme
    kennt. Der Namensvergleich bleibt darunter als Rueckfall fuer
    alles, was in der Relevanzliste gar nicht auftaucht.
    """
    n, b = _flach(name), _flach(begriff)
    if not n or not b:
        return 0
    p = 0
    if n == b:
        # Absoluter Vorrang. Ein Gleichstand mit irgendetwas anderem
        # waere hier immer die falsche Antwort.
        p += 1000
    if platz is not None:
        p += 100 - 4 * platz
    elif n.startswith(b):
        p += 60
    elif re.search(rf"\b{re.escape(b)}\b", n):
        p += 40
    elif b in n:
        p += 25
    # Ein Ersatzteil ist fast nie gemeint, wenn nach dem Ding gefragt
    # wird. Es taucht aber bei jeder zweiten Suche in der Liste auf.
    # Geprueft wird gegen die flache Schreibweise -- "Zubehör" heisst
    # dort "zubehoer", und genau daran ging die Pruefung zuerst vorbei.
    if n.startswith("zubehoer") or n.startswith("ersatzteil"):
        p -= 60
    # Kurze Namen sind die Grundklassen, lange die Sonderfaelle.
    p -= len(n) // 12
    return p


def _suchen(text: str) -> tuple[list[dict], str, int]:
    """Klassen zu einem Zuruf finden. (treffer, tatsaechlich gesucht, status)

    In Stufen, weil die Schnittstelle keine Mehrwortsuche kann: erst der
    ganze Wortlaut, dann die Umlautfassung, dann Wort fuer Wort in der
    Reihenfolge, in der sie gesprochen wurden. Die zweite Rueckgabe
    sagt, worunter es am Ende getroffen hat -- Sarvis soll das sagen
    koennen, sonst klingt ein Treffer auf ein Nebenwort wie ein Treffer
    auf den Zuruf.

    Bricht ab, sobald die Schnittstelle stoert: Weiterprobieren wuerde
    die Bremse nur fester ziehen, und aus einer Stoerung wuerde ein
    "nichts gefunden" -- die eine Auskunft, die hier falsch waere.
    """
    text = (text or "").strip()
    if not text:
        return [], "", 200

    versuche = [text]
    if _umlaute(text) != text:
        versuche.append(_umlaute(text))
    for w in _begriffe(text):
        if w not in versuche:
            versuche.append(w)
        if _umlaute(w) != w:
            versuche.append(_umlaute(w))

    for begriff in versuche[:6]:
        treffer, stand = _rohsuche(begriff)
        if stand != 200:
            return [], begriff, stand
        if treffer:
            naehe = _relevanz(begriff)
            for c in treffer:
                c["_platz"] = naehe.get(c.get("code", ""))
            treffer.sort(key=lambda c: -_punkte(c.get("name", ""), begriff,
                                                c.get("_platz")))
            return treffer, begriff, 200
    return [], text, 200


def _klasse(kennung: str) -> tuple[dict, int]:
    """Eine Klasse samt Merkmalen, auf Deutsch. (klasse, status)"""
    kennung = (kennung or "").strip()
    if not kennung:
        return {}, 200
    uri = (kennung if kennung.startswith("http")
           else f"{ETIM}/class/{kennung.upper()}")
    if uri in _KLASSEN:
        return _KLASSEN[uri], 200
    stand, d = _holen("/api/Class/v1", Uri=uri, IncludeClassProperties="true",
                      languageCode=SPRACHE)
    if stand != 200:
        return {}, stand
    if not d.get("name"):
        return {}, 200
    _KLASSEN[uri] = d
    return d, 200


def _aufloesen(kennung: str) -> tuple[dict, str, int]:
    """Code oder gesprochener Name -> Klasse. (klasse, worunter, status)"""
    kennung = (kennung or "").strip()
    if _CODE.match(kennung) or kennung.startswith("http"):
        klasse, stand = _klasse(kennung)
        return klasse, kennung, stand
    treffer, begriff, stand = _suchen(kennung)
    if stand != 200 or not treffer:
        return {}, begriff, stand
    klasse, stand = _klasse(treffer[0].get("code", ""))
    return klasse, begriff, stand


def _gewicht(p: dict, stelle: int) -> int:
    """Wie weit vorn ein Merkmal steht. Klein heisst wichtig.

    ETIM liefert keine Angabe darueber, welches Merkmal Pflicht ist --
    es gibt schlicht kein solches Feld. Die Reihenfolge hier ist
    deshalb gesetzt und nicht abgeleitet: Womit wird es angeschlossen,
    woraus ist es, wie ist es gebaut. Innerhalb einer Gruppe bleibt die
    Reihenfolge von ETIM erhalten, die ist fachlich sortiert.
    """
    rang = _GRUPPEN.get(p.get("propertySet"), _GRUPPE_UNBEKANNT)[0]
    g = rang * 10
    name = _flach(p.get("name", ""))
    if any(name.startswith(w) for w in (_flach(v) for v in _VORNE)):
        g -= 6
    if p.get("allowedValues"):
        # Eine Auswahlliste ist eine Frage, die sich beantworten laesst.
        # Ein freies Zahlenfeld ist eine, die man nachmessen muesste.
        g -= 4
    if p.get("dataType") == "Boolean":
        g += 6
    if any(w in name for w in (_flach(v) for v in _HINTEN)):
        g += 25
    # Zweiter Anschluss: fast immer wie der erste, und wenn nicht, sagt
    # der Handwerker es von selbst.
    if re.search(r"\b2\b", name):
        g += 12
    return g * 1000 + stelle


def _sortiert(klasse: dict) -> list[dict]:
    cp = klasse.get("classProperties") or []
    return [p for _, p in sorted(((_gewicht(p, i), p)
                                  for i, p in enumerate(cp)),
                                 key=lambda paar: paar[0])]


def _kurzliste(klasse: dict, anzahl: int) -> list[dict]:
    """Die wichtigsten Merkmale, aber aus verschiedenen Gruppen.

    Ohne die Grenze je Gruppe besteht die Antwort zu einem Kugelhahn aus
    sechs Werkstoffangaben und die Anschlussart fehlt. Breite schlaegt
    hier Tiefe -- das Tiefe kommt auf Nachfrage.
    """
    gezaehlt: dict[str, int] = {}
    heraus = []
    for p in _sortiert(klasse):
        g = p.get("propertySet") or ""
        if gezaehlt.get(g, 0) >= _JE_GRUPPE:
            continue
        gezaehlt[g] = gezaehlt.get(g, 0) + 1
        heraus.append(p)
        if len(heraus) >= anzahl:
            break
    return heraus


def _werte(p: dict, hoechstens: int = 6) -> list[str]:
    alle = [v.get("value", "") for v in (p.get("allowedValues") or [])]
    alle = [v for v in alle if v and v.lower() != "sonstige"]
    return alle[:hoechstens]


def _einheit(p: dict) -> str:
    e = p.get("units") or []
    return e[0] if e else ""


def _merkmal_zeile(p: dict) -> str:
    """Ein Merkmal als ein Satzteil -- Name, Einheit, ein paar Werte."""
    zeile = p.get("name", "?")
    einheit = _einheit(p)
    if einheit:
        zeile += f" (in {einheit})"
    werte = _werte(p)
    if werte:
        rest = len(p.get("allowedValues") or []) - len(werte)
        zeile += ": " + ", ".join(werte)
        if rest > 0:
            zeile += f" und {rest} weitere"
    elif p.get("dataType") == "Boolean":
        zeile += ": ja oder nein"
    return zeile


def _beantwortet(p: dict, wortlaut: str) -> str:
    """Steht die Antwort auf dieses Merkmal schon im Zuruf? ('' = nein)

    Zwei Wege: Entweder faellt einer der erlaubten Werte woertlich im
    Wortlaut ("1 Zoll" in "Kugelhahn 4-Wege 1 Zoll"), oder der
    Merkmalsname selbst wird genannt. Ein Wert wie "1 Zoll (25)" wird
    dafuer auf den Teil vor der Klammer gekuerzt -- so spricht niemand.
    """
    flach = " " + _flach(wortlaut) + " "
    alle = [v.get("value", "") for v in (p.get("allowedValues") or [])]
    for wert in alle:
        kurz = wert.split(" (")[0]
        f = _flach(kurz)
        if len(f) < 3 or f in ("ohne", "sonstige", "andere"):
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(f)}(?![a-z0-9])", flach):
            # Fangen mehrere Werte mit diesem Wort an, hat der Wortlaut
            # nur die Gattung genannt. Dann die Gattung zurueckgeben und
            # nicht den ersten Vertreter: ETIM kennt fuenf Innengewinde,
            # und aus dem gesagten "Innengewinde" wuerde sonst ein
            # behauptetes "Innengewinde (metrisch)".
            gleich = [w for w in alle
                      if _flach(w.split(" (")[0]).startswith(f)]
            return kurz if len(gleich) > 1 else wert
    kopf = _flach(p.get("name", "")).split(" ")[0]
    if len(kopf) >= 6 and re.search(rf"\b{re.escape(kopf)}", flach):
        return "im Wortlaut genannt"
    return ""


def _vorladen() -> None:
    """Die haeufigen Klassen holen, waehrend niemand fragt.

    Laeuft in einem eigenen Faden, weil der Start von Sarvis sich um
    keine Sekunde verzoegern darf -- er ist heute nach gut einer halben
    Sekunde bereit, und daran aendert dieses Modul nichts. Wer frueher
    fragt als der Faden liefert, wartet genau einmal so lange wie
    vorher; schlechter wird es nie.

    Einzeln und mit Abstand. Der Dienst kostet nichts und will keine
    Anmeldung, und er bremst bei schneller Folge -- beides Gruende,
    ihn nicht in einem Schwung leerzuraeumen. Eine Bremse ist hier kein
    Fehler, sondern eine Bitte: warten und weitermachen.

    Faellt alles aus -- kein Netz, Dienst weg, Zeitueberschreitung --,
    passiert nichts weiter. Dann ist der Speicher leer, und die
    Werkzeuge holen sich ihre Klasse beim ersten Zugriff selbst, genau
    wie ohne diesen Faden. Deshalb faengt die Schleife auch alles ab:
    Ein Vorlader, der den Prozess mit einem Traceback beschmutzt, waere
    schaedlicher als gar keiner.
    """
    t0 = time.perf_counter()
    geladen = 0
    strafe = 0.0
    for code, _ in _VORRAT:
        try:
            klasse, stand = _klasse(code)
            if klasse:
                geladen += 1
                # Es geht wieder: Tempo langsam zurueckholen, aber nicht
                # in einem Satz -- sonst rennt der Faden nach jedem
                # geglueckten Abruf erneut in dieselbe Bremse.
                strafe = strafe / 2 if strafe > _VORRAT_ABSTAND else 0.0
            elif stand == 429:
                # Ausgebremst. Deutlich mehr Luft lassen, dieselbe
                # Klasse einmal wiederholen, dann weiterziehen -- eine
                # stoerrische Klasse soll den Vorrat nicht aufhalten.
                strafe = min(max(strafe * 2, _VORRAT_BREMSPAUSE),
                             _VORRAT_BREMSPAUSE_MAX)
                time.sleep(strafe)
                klasse, _ = _klasse(code)
                if klasse:
                    geladen += 1
        except Exception:
            # Absichtlich alles: Dieser Faden hat keinen Empfaenger,
            # der einen Fehler sinnvoll behandeln koennte, und sein
            # Ausfall ist folgenlos.
            pass
        time.sleep(_VORRAT_ABSTAND + strafe)

    dauer = time.perf_counter() - t0
    # Eine Zeile, im Ton der uebrigen Startmeldungen. Sie kommt spaeter
    # als der Rest -- das ist der Punkt der Sache.
    if geladen == len(_VORRAT):
        print(f"  Fachdaten  : {geladen} Klassen vorgeladen "
              f"({dauer:.0f}s)", flush=True)
    elif geladen:
        print(f"  Fachdaten  : {geladen} von {len(_VORRAT)} Klassen "
              f"vorgeladen ({dauer:.0f}s), der Rest kommt beim "
              f"Nachschlagen", flush=True)
    else:
        # KEIN Fehler. Ohne Netz beim Start ist das der normale Lauf
        # der Dinge, und die Werkzeuge funktionieren unveraendert --
        # nur eben mit der Wartezeit beim ersten Mal.
        print("  Fachdaten  : nicht vorgeladen, wird beim ersten "
              "Nachschlagen geholt", flush=True)


def _vorlader_starten() -> None:
    """Den Faden genau einmal anwerfen.

    werkzeuge() kann mehrfach aufgerufen werden -- beim Messen, beim
    Neuaufbau des Werkzeugservers. Siebzehn Klassen ein zweites Mal zu
    holen brachte niemandem etwas und dem Dienst eine Bremse ein.
    """
    global _vorlader
    if _vorlader is not None:
        return
    # daemon: Der Faden haelt beim Beenden nichts auf. Sarvis
    # zuzumachen soll nicht davon abhaengen, dass ein Waschbecken
    # fertig geladen ist.
    _vorlader = threading.Thread(target=_vorladen, name="fachdaten-vorrat",
                                 daemon=True)
    _vorlader.start()


def _stoerung(stand: int) -> dict:
    """Die Schnittstelle antwortet nicht -- und das ist NICHT dasselbe wie
    "gibt es nicht".

    Genau diese Verwechslung ist beim Messen passiert: Nach einer
    Handvoll Abfragen kam 429, und Sarvis haette gesagt, es gebe keinen
    Kugelhahn. Ein Assistent, der eine Stoerung als Auskunft ausgibt,
    ist schlimmer als einer, der schweigt.
    """
    was = ("Das Fachverzeichnis bremst mich gerade aus"
           if stand == 429 else "Das Fachverzeichnis antwortet nicht")
    return {"content": [{"type": "text", "text":
            was + ". Frag in einem Moment nochmal — was ich sage, wäre "
            "sonst geraten."}], "is_error": True}


def _nichts_gefunden(begriff: str) -> dict:
    """Der haeufigste Fehlschlag -- und was er tatsaechlich bedeutet.

    Die deutsche Abdeckung von ETIM ist gut, aber nicht vollstaendig,
    und sie folgt der Normsprache und nicht der Baustellensprache
    ("Flachheizkörper", nicht "Plattenheizkörper"). Ein Nulltreffer ist
    deshalb meistens ein Wortproblem und kein Datenproblem -- das soll
    der Satz sagen, damit Sascha das andere Wort probiert.
    """
    return {"content": [{"type": "text", "text":
            f"Zu {begriff} finde ich in der Klassifikation nichts. Das "
            "heißt meist, dass die Norm ein anderes Wort benutzt — "
            "versuch es mit dem Oberbegriff oder einem zweiten "
            "Ausdruck dafür."}]}


def werkzeuge(protokoll, leuchten=None):

    # Ab hier laeuft im Hintergrund der Vorrat ein. Der Aufruf kehrt
    # sofort zurueck -- er startet einen Faden und wartet auf nichts.
    _vorlader_starten()

    def leuchte() -> None:
        if leuchten:
            leuchten("Fachdaten")

    # --- Klasse finden --------------------------------------------------

    @tool(
        "fachklasse_suchen",
        "Einen umgangssprachlichen Bauteilnamen auf die deutsche "
        "Fachklassifikation abbilden — Klassenname und Code, der beste "
        "Treffer zuerst. Damit wird aus 'Kugelhahn' eine saubere Klasse, "
        "bevor im Artikelstamm gesucht wird. Quelle: buildingSMART Data "
        "Dictionary, Verzeichnis ETIM 10.0 (Lizenz ODC-By) — dieselbe "
        "Klassifikation, nach der der Großhandel seine Artikeldaten "
        "ausliefert.",
        {
            "type": "object",
            "properties": {
                "begriff": {"type": "string",
                            "description": "z.B. 'Kugelhahn', 'Duschrinne', "
                                           "'Membranausdehnungsgefäß'"},
                "anzahl": {"type": "integer",
                           "description": "Höchstens 10, Vorgabe 5"},
            },
            "required": ["begriff"],
        },
    )
    async def fachklasse_suchen(args):
        begriff = (args.get("begriff") or "").strip()
        wie_viele = max(1, min(10, int(args.get("anzahl") or 5)))
        leuchte()
        treffer, gesucht, stand = _suchen(begriff)
        if stand != 200:
            return _stoerung(stand)
        if not treffer:
            return _nichts_gefunden(begriff)

        zeilen = []
        for c in treffer[:wie_viele]:
            zeilen.append(f"{c.get('name', '?')} ({c.get('code', '?')})")
        vorspann = ""
        if _flach(gesucht) != _flach(begriff):
            # Getroffen hat ein Nebenwort des Zurufs. Das zu verschweigen
            # waere die schlimmere Variante: Sarvis klaenge sicher, waere
            # es aber nicht.
            vorspann = f"Gesucht habe ich unter {gesucht}. "
        rest = len(treffer) - wie_viele
        text = (vorspann + "Passende Klassen: " + "; ".join(zeilen)
                + (f" und {rest} weitere" if rest > 0 else "") + ".")
        return {"content": [{"type": "text", "text": text}]}

    # --- Merkmale einer Klasse ------------------------------------------

    @tool(
        "fachklasse_merkmale",
        "Die Merkmale einer Fachklasse auf Deutsch — mit Einheit und, wo "
        "die Norm sie vorgibt, den erlaubten Werten. Ohne weitere Angabe "
        "kommen nur die Merkmale, die eine Position eindeutig machen "
        "(Nennweite, Anschluss, Werkstoff, Bauart); 'alle' oder ein "
        "einzelner Merkmalsname liefern den Rest. Quelle: buildingSMART "
        "Data Dictionary, ETIM 10.0 (ODC-By).",
        {
            "type": "object",
            "properties": {
                "klasse": {"type": "string",
                           "description": "Klassenname oder Code, z.B. "
                                          "'Kugelhahn' oder 'EC011343'"},
                "alle": {"type": "boolean",
                         "description": "Alle Merkmale nach Gruppen statt "
                                        "nur der wichtigsten"},
                "merkmal": {"type": "string",
                            "description": "Nur dieses eine Merkmal, dafür "
                                           "mit allen erlaubten Werten, "
                                           "z.B. 'Anschluss 1'"},
                "anzahl": {"type": "integer",
                           "description": "Wie viele wichtige Merkmale, "
                                          "Vorgabe 6"},
            },
            "required": ["klasse"],
        },
    )
    async def fachklasse_merkmale(args):
        leuchte()
        klasse, _, stand = _aufloesen(args.get("klasse") or "")
        if stand != 200:
            return _stoerung(stand)
        if not klasse:
            return _nichts_gefunden(args.get("klasse") or "")
        name = klasse.get("name", "?")
        code = klasse.get("code", "?")
        alle_m = klasse.get("classProperties") or []
        if not alle_m:
            return {"content": [{"type": "text", "text":
                    f"Zu {name} ({code}) sind keine Merkmale hinterlegt."}]}

        # Ein einzelnes Merkmal, dafuer vollstaendig.
        wunsch = (args.get("merkmal") or "").strip()
        if wunsch:
            f = _flach(wunsch)
            passend = [p for p in alle_m if f in _flach(p.get("name", ""))]
            if not passend:
                return {"content": [{"type": "text", "text":
                        f"Ein Merkmal {wunsch} hat {name} nicht."}]}
            p = passend[0]
            werte = [v.get("value", "") for v in (p.get("allowedValues") or [])]
            text = f"{name}, {p.get('name')}"
            einheit = _einheit(p)
            if einheit:
                text += f" (in {einheit})"
            if werte:
                text += ": " + ", ".join(werte) + "."
            elif p.get("dataType") == "Boolean":
                text += ": ja oder nein."
            else:
                text += ": freier Wert, keine Auswahlliste."
            return {"content": [{"type": "text", "text": text}]}

        # Alles, nach Gruppen sortiert -- fuer den Bildschirm, nicht fuers
        # Vorlesen. Deshalb kommt es nur auf ausdrueckliche Nachfrage.
        if args.get("alle"):
            nach_gruppe: dict[str, list[str]] = {}
            raenge: dict[str, int] = {}
            for p in _sortiert(klasse):
                rang, titel = _GRUPPEN.get(p.get("propertySet"),
                                           _GRUPPE_UNBEKANNT)
                raenge[titel] = rang
                nach_gruppe.setdefault(titel, []).append(_merkmal_zeile(p))
            teile = [f"{name} ({code}) hat {len(alle_m)} Merkmale."]
            for titel in sorted(nach_gruppe, key=lambda t: raenge[t]):
                teile.append(f"{titel}: " + "; ".join(nach_gruppe[titel]) + ".")
            return {"content": [{"type": "text", "text": "\n".join(teile)}]}

        wie_viele = max(1, min(15, int(args.get("anzahl") or 6)))
        kurz = _kurzliste(klasse, wie_viele)
        rest = len(alle_m) - len(kurz)
        eltern = (klasse.get("parentClassReference") or {}).get("name", "")
        text = (f"{name} ({code})"
                + (f", Obergruppe {eltern}" if eltern else "")
                + ", die wichtigsten Merkmale: "
                + "; ".join(_merkmal_zeile(p) for p in kurz) + ".")
        if rest > 0:
            text += (f" Dazu {rest} weitere — sag Bescheid, wenn du sie "
                     "brauchst.")
        return {"content": [{"type": "text", "text": text}]}

    # --- Was am Zuruf noch fehlt ----------------------------------------

    @tool(
        "fachklasse_rueckfragen",
        "Aus einem diktierten Schnipsel ableiten, was für eine eindeutige "
        "Angebotsposition noch fehlt: Der Wortlaut wird auf eine "
        "Fachklasse abgebildet, und deren Merkmale werden gegen den "
        "Wortlaut gehalten. Zurück kommt, was schon feststeht und welche "
        "Punkte offen sind — mit den Werten, die die Norm dafür zulässt. "
        "Für Rückfragen, die fachlich stimmen, statt geraten sind. "
        "Quelle: buildingSMART Data Dictionary, ETIM 10.0 (ODC-By).",
        {
            "type": "object",
            "properties": {
                "wortlaut": {"type": "string",
                             "description": "Der Schnipsel wie diktiert, "
                                            "z.B. 'Kugelhahn 4-Wege 1 Zoll'"},
                "klasse": {"type": "string",
                           "description": "Optional: Klasse oder Code "
                                          "vorgeben, wenn die Zuordnung "
                                          "schon feststeht"},
                "anzahl": {"type": "integer",
                           "description": "Wie viele Punkte höchstens, "
                                          "Vorgabe 4"},
            },
            "required": ["wortlaut"],
        },
    )
    async def fachklasse_rueckfragen(args):
        leuchte()
        wortlaut = (args.get("wortlaut") or "").strip()
        klasse, gesucht, stand = _aufloesen(args.get("klasse") or wortlaut)
        if stand != 200:
            return _stoerung(stand)
        if not klasse:
            return _nichts_gefunden(wortlaut)
        name = klasse.get("name", "?")
        code = klasse.get("code", "?")

        # Erst die breite Auswahl, dann filtern -- sonst faellt ein
        # beantworteter Punkt aus der Liste und es kommt nichts nach.
        kandidaten = _kurzliste(klasse, 12)
        wie_viele = max(1, min(8, int(args.get("anzahl") or 4)))

        klar, offen = [], []
        for p in kandidaten:
            antwort = _beantwortet(p, wortlaut)
            if antwort:
                klar.append(f"{p.get('name')}: {antwort}")
            elif len(offen) < wie_viele:
                offen.append(p)

        teile = [f"Das ist ein {name} ({code})."]
        if not args.get("klasse") and _flach(gesucht) != _flach(wortlaut):
            # Getroffen hat ein einzelnes Wort des Zurufs, nicht der Zuruf.
            # Bei "WC-Element mit Betätigungsplatte" entscheidet das ueber
            # richtig und falsch -- und Sascha kann es nur korrigieren,
            # wenn er es hoert.
            teile.append(f"(Zugeordnet über das Wort {gesucht}.)")
        if klar:
            teile.append("Schon klar — " + "; ".join(klar) + ".")
        if offen:
            fragen = []
            for p in offen:
                werte = _werte(p, 4)
                frage = p.get("name", "?")
                einheit = _einheit(p)
                if werte:
                    frage += " (" + ", ".join(werte) + "?)"
                elif einheit:
                    frage += f" (in {einheit})"
                elif p.get("dataType") == "Boolean":
                    frage += " (ja oder nein)"
                fragen.append(frage)
            teile.append("Offen ist noch: " + "; ".join(fragen) + ".")
        else:
            teile.append("Damit ist die Position eindeutig genug.")
        return {"content": [{"type": "text", "text": " ".join(teile)}]}

    return [fachklasse_suchen, fachklasse_merkmale, fachklasse_rueckfragen]
