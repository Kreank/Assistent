"""Markdown lesen -- einmal, fuer drei Ausgaenge.

Sarvis schreibt Markdown. Daraus wird ein Blatt im Browser, ein PDF zum
Behalten und eine Word-Datei zum Weiterschreiben. Waeren das drei
Wandler, wuerde eine Tabelle in zweien richtig und im dritten falsch
aussehen -- und niemand faende heraus, in welchem, weil man selten alle
drei nebeneinander haelt.

Also einmal lesen, in eine Liste von Bloecken:

    {"art": "ueberschrift", "stufe": 2, "teile": [...]}
    {"art": "absatz",       "teile": [...]}
    {"art": "liste",        "geordnet": False, "punkte": [punkt, ...]}

Ein "punkt" ist {"teile": [...], "stufe": 0, "haken": None}. stufe ist
die Verschachtelungstiefe (0 bis 2), haken ist True/False bei einer
Aufgabenliste ("- [x] erledigt") und sonst None.
    {"art": "zitat",        "teile": [...]}
    {"art": "code",         "text": "...", "sprache": "python"}
    {"art": "tabelle",      "kopf": [[teile], ...], "zeilen": [[[teile]]]}
    {"art": "linie"}

Ein "teil" ist ein Stueck Fliesstext mit Auszeichnung:

    {"text": "...", "fett": bool, "kursiv": bool, "code": bool,
     "ziel": "https://..."}

WAS ABSICHTLICH FEHLT

Fussnoten und HTML im Markdown. Das zweite ist gefaehrlich -- ein
<script> im Markdown waere genau der Weg, gegen den die ganze
Absicherung gebaut ist; das erste ist in einer gesprochenen Antwort
noch nie vorgekommen. Was hier nicht gelesen wird, ueberlebt als
schlichter Text -- nichts geht verloren, es sieht nur nicht aus wie
gemeint.

Ebenfalls nicht gelesen: der eingerueckte Codeblock (vier Leerzeichen
statt Ruecktikken). Er liesse sich nicht sicher von der Fortsetzung
eines Listenpunkts unterscheiden, und eine Aufzaehlung, die zur Haelfte
als Quelltext erscheint, ist schlimmer als ein Codeblock, der wie ein
Absatz aussieht.

VERSCHACHTELTE LISTEN GAB ES ANFANGS NICHT, und das war ein Fehler,
kein Verzicht: Unterpunkte landeten auf derselben Ebene wie die
Hauptpunkte. Nicht bloss haesslich -- aus "zwei Posten, davon einer mit
drei Unterpunkten" wurden fuenf gleichrangige Posten, und die Aussage
war eine andere. Jetzt traegt jeder Punkt seine Stufe.

ROH-HTML WIRD NIE DURCHGEREICHT. Es gibt in dieser Datei keinen Pfad,
auf dem ein Zeichen aus der Eingabe unveraendert in einer Ausgabe
landet: Der HTML-Ausgang escaped jeden Text, der docx-Ausgang steckt
ihn in ein XML-Element. Das ist keine Vorsicht, sondern die Bedingung
dafuer, dass ein Blatt aus Modellausgabe gebaut werden darf.
"""
import re
from html import escape

# Wie tief eine Ueberschrift gehen darf. Mehr als drei Stufen hat in
# einem Bericht noch nie geholfen, und h4 ist im Rahmen von bericht.py
# ohnehin nicht gestaltet.
STUFEN_MAX = 3

_UEBERSCHRIFT = re.compile(r"^(#{1,6})\s+(.*)$")
# Die Einrueckung wird MITGELESEN (Gruppe 1), daraus wird die Stufe.
_PUNKT = re.compile(r"^([ \t]*)[-*+]\s+(.*)$")
_ZAHL = re.compile(r"^([ \t]*)(\d{1,3})[.)]\s+(.*)$")
# Mehrfache > gelten als ein Zitat -- ">> so" ist ein verschachteltes
# Zitat, und ein sichtbar stehengebliebenes ">" ist schlechter als eine
# nicht dargestellte Verschachtelung.
_ZITAT = re.compile(r"^\s*>+\s?(.*)$")
# Aufgabenliste: "- [ ] offen" und "- [x] erledigt".
_HAKEN = re.compile(r"^\[([ xX])\]\s+(.*)$")
# Wie viele Leerzeichen eine Stufe sind. Zwei ist die uebliche
# Schreibweise, vier kommt genauso vor -- deshalb wird durch zwei
# geteilt und gedeckelt, statt auf eine Zahl zu bestehen.
_STUFE_BREITE = 2
STUFEN_TIEF = 2
_LINIE = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_ZAUN = re.compile(r"^\s*```+\s*(\w*)\s*$")
_TRENNZEILE = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")

# Inline, in dieser Reihenfolge geprueft. Code zuerst: Was in
# Ruecktikken steht, ist woertlich und darf nicht noch einmal nach
# Sternchen abgesucht werden -- sonst wird aus `a*b*c` ein Kursivsatz
# mitten im Code.
_INLINE = re.compile(
    r"(?P<code>`[^`\n]+`)"
    # Das Bild VOR dem Link, sonst frisst der Link die Klammern und
    # das Ausrufezeichen bleibt einzeln stehen ("!Bild").
    r"|(?P<bild>!\[[^\]\n]*\]\([^)\s]+\))"
    r"|(?P<link>\[[^\]\n]+\]\([^)\s]+\))"
    r"|(?P<fett>\*\*[^*\n]+\*\*|__[^_\n]+__)"
    r"|(?P<durch>~~[^~\n]+~~)"
    r"|(?P<kursiv>\*[^*\n]+\*|_[^_\n]+_)"
)

# Was als Linkziel durchgeht. Alles andere wird zu blossem Text.
#
# Der Grund steht in sarvis.js an derselben Stelle: Ein javascript:-Ziel
# in einem href ist ein fremder Befehl an einem Knopf, den der Nutzer
# fuer harmlos haelt. mailto und tel sind erlaubt, weil sie nichts
# ausfuehren, sondern ein Programm oeffnen, das fragt.
_ZIEL_OK = re.compile(r"^(https?://|mailto:|tel:)", re.IGNORECASE)


def _teile(zeile: str) -> list:
    """Eine Zeile Fliesstext in ausgezeichnete Stuecke zerlegen."""
    teile, zuletzt = [], 0
    for treffer in _INLINE.finditer(zeile):
        if treffer.start() > zuletzt:
            teile.append({"text": zeile[zuletzt:treffer.start()]})
        roh = treffer.group(0)
        if treffer.group("code"):
            teile.append({"text": roh[1:-1], "code": True})
        elif treffer.group("bild"):
            # BILDER WERDEN NICHT GELADEN, sondern benannt. Die
            # Content-Security-Policy laesst ohnehin nur data:-Quellen
            # durch (bericht.SICHERHEIT) -- ein <img> auf eine fremde
            # Adresse waere ein leerer Rahmen UND ein Abruf, der
            # verraet, wann das Blatt geoeffnet wurde. Statt dessen der
            # Beschriftungstext, und wenn es keinen gibt, das Wort.
            schnitt = roh.index("](")
            beschriftung = roh[2:schnitt].strip()
            teile.append({"text": f"[{beschriftung or 'Bild'}]",
                          "kursiv": True})
        elif treffer.group("durch"):
            teile.append({"text": roh[2:-2], "durch": True})
        elif treffer.group("link"):
            schnitt = roh.index("](")
            text = roh[1:schnitt]
            ziel = roh[schnitt + 2:-1]
            if _ZIEL_OK.match(ziel):
                teile.append({"text": text, "ziel": ziel})
            else:
                # Nicht wegwerfen -- der Nutzer soll sehen, was dastand,
                # nur eben nicht darauf klicken koennen.
                teile.append({"text": f"{text} ({ziel})"})
        elif treffer.group("fett"):
            teile.append({"text": roh[2:-2], "fett": True})
        else:
            teile.append({"text": roh[1:-1], "kursiv": True})
        zuletzt = treffer.end()
    if zuletzt < len(zeile):
        teile.append({"text": zeile[zuletzt:]})
    return teile or [{"text": ""}]


def _einzug(zeile: str) -> int:
    """Wie weit eine Zeile eingerueckt ist, in Leerzeichen.

    Ein Tabulator zaehlt als vier. Nicht als acht: Markdown-Schreiber
    mischen Tabulator und zwei Leerzeichen, und bei acht waere eine
    Tabulator-Ebene doppelt so tief wie die daneben.
    """
    roh = zeile[:len(zeile) - len(zeile.lstrip(" \t"))]
    return roh.count(" ") + roh.count("\t") * 4


def _spalten(zeile: str) -> list:
    """Eine Tabellenzeile in ihre Zellen zerlegen."""
    roh = zeile.strip()
    if roh.startswith("|"):
        roh = roh[1:]
    if roh.endswith("|"):
        roh = roh[:-1]
    return [_teile(z.strip()) for z in roh.split("|")]


def lesen(text: str) -> list:
    """Markdown in Bloecke zerlegen. Der einzige Einstieg hier."""
    zeilen = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    bloecke, absatz = [], []

    def absatz_schliessen():
        if absatz:
            bloecke.append({"art": "absatz", "teile": _teile(" ".join(absatz))})
            absatz.clear()

    i = 0
    while i < len(zeilen):
        zeile = zeilen[i]

        zaun = _ZAUN.match(zeile)
        if zaun:
            absatz_schliessen()
            sprache, inhalt = zaun.group(1) or "", []
            i += 1
            while i < len(zeilen) and not _ZAUN.match(zeilen[i]):
                inhalt.append(zeilen[i])
                i += 1
            # Ein Codeblock ohne schliessenden Zaun ist kein Fehler,
            # sondern ein Modell, dem die Zeichen ausgegangen sind. Was
            # da ist, wird gezeigt.
            bloecke.append({"art": "code", "sprache": sprache,
                            "text": "\n".join(inhalt)})
            i += 1
            continue

        if not zeile.strip():
            absatz_schliessen()
            i += 1
            continue

        if _LINIE.match(zeile):
            absatz_schliessen()
            bloecke.append({"art": "linie"})
            i += 1
            continue

        ueber = _UEBERSCHRIFT.match(zeile)
        if ueber:
            absatz_schliessen()
            bloecke.append({"art": "ueberschrift",
                            "stufe": min(len(ueber.group(1)), STUFEN_MAX),
                            "teile": _teile(ueber.group(2).strip())})
            i += 1
            continue

        # Eine Tabelle erkennt man erst an der ZWEITEN Zeile: Die erste
        # sieht aus wie jede andere mit Strichen darin.
        if ("|" in zeile and i + 1 < len(zeilen)
                and _TRENNZEILE.match(zeilen[i + 1])):
            absatz_schliessen()
            kopf = _spalten(zeile)
            i += 2
            reihen = []
            while i < len(zeilen) and "|" in zeilen[i] and zeilen[i].strip():
                reihen.append(_spalten(zeilen[i]))
                i += 1
            bloecke.append({"art": "tabelle", "kopf": kopf, "zeilen": reihen})
            continue

        zitat = _ZITAT.match(zeile)
        if zitat:
            absatz_schliessen()
            gesammelt = [zitat.group(1)]
            i += 1
            while i < len(zeilen) and _ZITAT.match(zeilen[i]):
                gesammelt.append(_ZITAT.match(zeilen[i]).group(1))
                i += 1
            bloecke.append({"art": "zitat",
                            "teile": _teile(" ".join(gesammelt).strip())})
            continue

        punkt = _PUNKT.match(zeile)
        zahl = _ZAHL.match(zeile)
        if punkt or zahl:
            absatz_schliessen()
            # Die Sorte der ERSTEN Zeile bestimmt die Liste. Ein
            # nummerierter Unterpunkt unter einer Aufzaehlung ist
            # trotzdem derselbe Block -- sonst zerfaellt eine Liste in
            # drei, sobald jemand die Ebenen mischt.
            geordnet = bool(zahl)
            grund = _einzug(zeile)
            punkte = []
            while i < len(zeilen):
                p = _PUNKT.match(zeilen[i]) or _ZAHL.match(zeilen[i])
                if not p:
                    break
                roh = p.group(len(p.groups()))       # der Text danach
                stufe = min((_einzug(zeilen[i]) - grund) // _STUFE_BREITE,
                            STUFEN_TIEF)
                haken = None
                kasten = _HAKEN.match(roh.strip())
                if kasten:
                    haken = kasten.group(1).lower() == "x"
                    roh = kasten.group(2)
                punkte.append({"teile": _teile(roh.strip()),
                               "stufe": max(stufe, 0), "haken": haken})
                i += 1
            bloecke.append({"art": "liste", "geordnet": geordnet,
                            "punkte": punkte})
            continue

        absatz.append(zeile.strip())
        i += 1

    absatz_schliessen()
    return bloecke


# Wie ein Haken dargestellt wird. Zeichen und keine Kontrollkaestchen:
# Ein <input type="checkbox"> waere im Blatt anklickbar und wuerde
# nichts bewirken -- ein Schalter, der nichts schaltet, ist schlechter
# als ein Zeichen. Und in Word und Excel gibt es ihn ohnehin nicht.
HAKEN_AN, HAKEN_AUS = "\u2611", "\u2610"      # gehakt, leer


def punkt_text(punkt) -> str:
    """Der Text eines Listenpunkts, mit Haken davor, ohne Auszeichnung."""
    text = "".join(str(t.get("text") or "") for t in punkt.get("teile") or [])
    haken = punkt.get("haken")
    if haken is None:
        return text
    return f"{HAKEN_AN if haken else HAKEN_AUS} {text}"


# --- Ausgang eins: HTML ---------------------------------------------------

def _teile_html(teile) -> str:
    aus = []
    for t in teile or []:
        text = escape(str(t.get("text") or ""))
        if t.get("code"):
            text = f"<code>{text}</code>"
        if t.get("fett"):
            text = f"<strong>{text}</strong>"
        if t.get("kursiv"):
            text = f"<em>{text}</em>"
        if t.get("durch"):
            text = f"<s>{text}</s>"
        ziel = str(t.get("ziel") or "")
        if ziel and _ZIEL_OK.match(ziel):
            # rel: Ein Bericht wird aus Modellausgabe gebaut, und die
            # Ziele darin stammen aus Seiten, die Sarvis gelesen hat.
            # noopener trennt das Fenster, noreferrer verraet nicht, von
            # wo aus geklickt wurde.
            text = (f'<a href="{escape(ziel, quote=True)}" target="_blank" '
                    f'rel="noopener noreferrer">{text}</a>')
        aus.append(text)
    return "".join(aus)


def _gleicher_titel(bloecke, titel: str) -> bool:
    """Faengt der Text mit genau der Ueberschrift an, die schon oben steht?

    Kommt staendig vor und sieht immer falsch aus: seite_bauen setzt den
    Titel in den Kopf, und ein Modell, das um "Markdown mit Titel"
    gebeten wird, schreibt ihn als erstes noch einmal als "# ...".
    Gemessen an einem Muster-Angebot: "Angebot Heizungserneuerung" stand
    zweimal untereinander, einmal gross im Kopf und einmal als
    Ueberschrift darunter.

    Verglichen wird nachsichtig -- ohne Gross- und Kleinschreibung, ohne
    Satzzeichen am Ende, ohne doppelte Leerzeichen. Wer den Titel
    absichtlich wiederholt, schreibt ihn nicht Zeichen fuer Zeichen
    gleich.
    """
    if not bloecke or not titel:
        return False
    erst = bloecke[0]
    if erst.get("art") != "ueberschrift":
        return False
    def schlicht(s):
        return " ".join(str(s or "").split()).strip(" .:!?—-").casefold()
    text = "".join(str(x.get("text") or "") for x in erst.get("teile") or [])
    return schlicht(text) == schlicht(titel)


def _liste_html(block) -> str:
    """Eine Liste samt ihrer Unterebenen.

    Verschachtelt wird richtig, also INNERHALB des vorigen <li> -- ein
    <ul> als Geschwister des <li> waere zwar auch eingerueckt, aber
    Vorleseprogramme lesen es dann als eigene Liste vor, und die
    Zugehoerigkeit ist weg.
    """
    tag = "ol" if block.get("geordnet") else "ul"
    aus = [f"<{tag}>"]
    stufe = 0
    offen = False        # steht gerade ein <li> offen, in das etwas hinein darf
    for punkt in block.get("punkte") or []:
        ziel = int(punkt.get("stufe") or 0)
        while ziel > stufe:
            # Ohne offenes <li> zuerst eines aufmachen: Eine Liste, die
            # mit einem Unterpunkt beginnt, ist ungueltiges HTML.
            if not offen:
                aus.append("<li>")
                offen = True
            aus.append(f"<{tag}>")
            stufe += 1
            offen = False
        while ziel < stufe:
            if offen:
                aus.append("</li>")
                offen = False
            aus.append(f"</{tag}></li>")
            stufe -= 1
        if offen:
            aus.append("</li>")
        haken = punkt.get("haken")
        marke = ""
        if haken is not None:
            marke = (f'<span class="haken">'
                     f'{HAKEN_AN if haken else HAKEN_AUS}</span> ')
        aus.append(f"<li>{marke}{_teile_html(punkt.get('teile'))}")
        offen = True
    if offen:
        aus.append("</li>")
    while stufe > 0:
        aus.append(f"</{tag}></li>")
        stufe -= 1
    aus.append(f"</{tag}>")
    return "".join(aus)


def als_html(bloecke, titel: str = "") -> str:
    """Bloecke in den Rumpf einer Seite -- passend zu bericht.seite_bauen.

    Nur Tags, die der Rahmen dort auch gestaltet. Das Ergebnis geht
    durch _rumpf_richten und bekommt damit denselben Tabellenkasten wie
    ein handgeschriebener Rumpf.

    titel ist optional und dient nur einem Zweck: die erste Ueberschrift
    wegzulassen, wenn sie den Titel bloss wiederholt.
    """
    bloecke = list(bloecke or [])
    if titel and _gleicher_titel(bloecke, titel):
        bloecke = bloecke[1:]
    aus = []
    for b in bloecke or []:
        art = b.get("art")
        if art == "ueberschrift":
            stufe = int(b.get("stufe") or 2) + 1     # h1 gehoert dem Titel
            aus.append(f"<h{stufe}>{_teile_html(b.get('teile'))}</h{stufe}>")
        elif art == "absatz":
            aus.append(f"<p>{_teile_html(b.get('teile'))}</p>")
        elif art == "zitat":
            aus.append(f"<blockquote>{_teile_html(b.get('teile'))}</blockquote>")
        elif art == "code":
            aus.append("<pre><code>"
                       + escape(str(b.get("text") or ""))
                       + "</code></pre>")
        elif art == "linie":
            aus.append("<hr>")
        elif art == "liste":
            aus.append(_liste_html(b))
        elif art == "tabelle":
            kopf = "".join(f"<th>{_teile_html(z)}</th>"
                           for z in b.get("kopf") or [])
            zeilen = "".join(
                "<tr>" + "".join(f"<td>{_teile_html(z)}</td>" for z in reihe)
                + "</tr>" for reihe in b.get("zeilen") or [])
            aus.append(f"<table><thead><tr>{kopf}</tr></thead>"
                       f"<tbody>{zeilen}</tbody></table>")
    return "\n".join(aus)


def als_csv(bloecke) -> str:
    """Alle Tabellen als CSV -- fuer den Import anderswo.

    ZWEI ENTSCHEIDUNGEN, DIE BEIDE DEUTSCH SIND:

    Semikolon statt Komma. Das deutsche Excel erwartet als Trennzeichen
    das, was in den Windows-Regionseinstellungen als Listentrenner
    steht, und das ist hier das Semikolon. Eine Komma-CSV landet beim
    Doppelklick vollstaendig in Spalte A -- die Datei ist nicht kaputt,
    sie sieht nur so aus, und niemand sucht den Fehler beim Trenner.

    Und eine BOM voran. Ohne sie liest Excel die Datei als Windows-1252,
    und aus "Wärmepumpe" wird "WÃ¤rmepumpe". Andere Programme stoert
    das Zeichen nicht; Excel ohne es schon.

    Steht KEINE Tabelle im Inhalt, kommt der Text zeilenweise -- eine
    leere Datei waere die schlechtere Antwort.
    """
    zeilen = []
    tabellen = [b for b in bloecke or [] if b.get("art") == "tabelle"]
    if tabellen:
        for nr, b in enumerate(tabellen):
            if nr:
                zeilen.append("")       # Leerzeile zwischen zwei Tabellen
            for reihe in [b.get("kopf") or []] + list(b.get("zeilen") or []):
                zeilen.append(";".join(_csv_feld("".join(
                    str(t.get("text") or "") for t in zelle))
                    for zelle in reihe))
    else:
        for zeile in nur_text(bloecke).split("\n"):
            zeilen.append(_csv_feld(zeile))
    return "\ufeff" + "\r\n".join(zeilen) + "\r\n"


def _csv_feld(text: str) -> str:
    """Ein Feld nach RFC 4180 -- nur einpacken, wenn es noetig ist."""
    roh = str(text or "")
    if any(c in roh for c in ';"\r\n'):
        return '"' + roh.replace('"', '""') + '"'
    return roh


def nur_text(bloecke) -> str:
    """Alles ohne Auszeichnung -- fuer Vorschauen und fuers Protokoll."""
    aus = []
    for b in bloecke or []:
        if b.get("art") == "code":
            aus.append(str(b.get("text") or ""))
        elif b.get("art") == "liste":
            for p in b.get("punkte") or []:
                einzug = "  " * int(p.get("stufe") or 0)
                aus.append(f"{einzug}- {punkt_text(p)}")
        elif b.get("art") == "tabelle":
            for reihe in [b.get("kopf") or []] + list(b.get("zeilen") or []):
                aus.append(" | ".join(
                    "".join(str(t.get("text") or "") for t in z) for z in reihe))
        elif b.get("teile"):
            aus.append("".join(str(t.get("text") or "")
                               for t in b.get("teile")))
    return "\n".join(aus)
