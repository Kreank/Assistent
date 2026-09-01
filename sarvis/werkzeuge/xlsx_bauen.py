"""Eine Excel-Datei schreiben -- ohne Bibliothek.

Gleiche Bauart und gleiche Begruendung wie docx_bauen.py: ein ZIP mit
XML darin, geschrieben mit zipfile aus der Standardbibliothek. openpyxl
waere eine Zeile in requirements.txt und danach ein Neubau des Images
samt der 1,5 GB CUDA-Raeder, die an derselben pip-Schicht haengen.

WORAUF ES BEI EXCEL ANKOMMT: ZAHLEN MUESSEN ZAHLEN SEIN

Eine Tabelle als Text zu exportieren ist keine Excel-Datei, sondern ein
Bild einer Tabelle in einer Excel-Datei. Man kann nicht summieren, nicht
sortieren, nicht filtern -- und genau dafuer nimmt man Excel. Der ganze
Aufwand in _wert() dient diesem einen Punkt.

Und deutsche Zahlen sind der Grund, warum das nicht trivial ist:
"12.400,00" ist zwoelftausendvierhundert, nicht zwoelf Komma vier.
Wer hier float() aufruft, bekommt entweder einen Fehler oder --
schlimmer -- eine Zahl, die um den Faktor tausend danebenliegt und wie
eine richtige aussieht.

WAS AUS EINEM MARKDOWN-BLOCK WIRD

    tabelle       ein echter Zellbereich mit Kopfzeile
    ueberschrift  eine fette Zeile darueber
    absatz/zitat  eine Textzeile
    liste         je Punkt eine Zeile mit vorangestelltem Zeichen
    code          je Zeile eine Zelle in fester Schrift
    linie         eine leere Zeile

Nichts geht verloren. Eine Excel-Datei, die nur die Tabellen enthaelt
und den Text davor wegwirft, verliert den Zusammenhang -- und der stand
oft genau in dem Satz, der erklaert, was die Spalte bedeutet.
"""
import re
import zipfile
from datetime import datetime

_NS = ('xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/'
       'relationships"')

_VERBOTEN = {c: None for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)}

# Wie breit eine Spalte hoechstens wird. Ohne Deckel macht ein langer
# Satz in einer Zelle die Spalte 200 Zeichen breit, und die Tabelle
# passt auf keinen Bildschirm mehr.
BREITE_MAX = 62
BREITE_MIN = 9

# Ab wie vielen Datenzeilen die Kopfzeile eingefroren wird. Darunter
# sieht man sie ohnehin, und ein eingefrorener Bereich in einer
# Vier-Zeilen-Tabelle ist nur im Weg.
EINFRIEREN_AB = 12

# Was als Zahl durchgeht: nur, wenn die GANZE Zelle eine ist.
# "24 h" bleibt Text -- eine Zahl mit Einheit ist keine Zahl, und wer
# sie zu einer macht, verliert die Einheit stillschweigend.
_ZAHL = re.compile(r"^-?\d{1,3}(\.\d{3})*(,\d+)?$|^-?\d+(,\d+)?$"
                   r"|^-?\d+(\.\d+)?$")


def _x(text) -> str:
    return (str(text or "")
            .translate(_VERBOTEN)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _wert(text: str):
    """Zahl oder None. Deutsches und englisches Format, streng geprueft."""
    roh = str(text or "").strip()
    if not roh or not _ZAHL.match(roh):
        return None
    if "," in roh:
        # Komma da -> deutsches Format: Punkte sind Tausendertrenner.
        roh = roh.replace(".", "").replace(",", ".")
    elif roh.count(".") >= 1:
        teile = roh.lstrip("-").split(".")
        # "1.234" ist zweideutig. Sieht es nach Tausendergruppen aus
        # (jede Gruppe nach der ersten genau drei Ziffern), gilt das --
        # das ist in deutschen Texten der haeufigere Fall und der, bei
        # dem ein Irrtum um Faktor tausend danebenliegt.
        if len(teile) > 1 and all(len(g) == 3 for g in teile[1:]):
            roh = roh.replace(".", "")
    try:
        return float(roh)
    except ValueError:
        return None


def _zelle(spalte: int, zeile: int, text: str, stil: int = 0) -> str:
    ort = f"{_spaltenname(spalte)}{zeile}"
    zahl = _wert(text)
    if zahl is not None:
        # Zahlen bekommen den Zahlenstil, wenn sie nicht schon einen
        # eigenen haben (Kopfzeile bleibt Kopfzeile).
        s = stil if stil else 3
        return f'<c r="{ort}" s="{s}"><v>{zahl!r}</v></c>'
    if not str(text or "").strip():
        return f'<c r="{ort}" s="{stil}"/>'
    # inlineStr statt sharedStrings: eine Datei weniger, ein Index
    # weniger, und bei Berichtsgroessen kostet es nichts.
    return (f'<c r="{ort}" s="{stil}" t="inlineStr"><is>'
            f'<t xml:space="preserve">{_x(text)}</t></is></c>')


def _spaltenname(n: int) -> str:
    """1 -> A, 27 -> AA."""
    name = ""
    while n > 0:
        n, rest = divmod(n - 1, 26)
        name = chr(65 + rest) + name
    return name


def _text_von(teile) -> str:
    return "".join(str(t.get("text") or "") for t in teile or [])


# Stilnummern, wie sie unten in _STILE angelegt sind.
NORMAL, KOPFZEILE, TITEL, ZAHL, LEISE, FEST = 0, 1, 2, 3, 4, 5

_STILE = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          f'<styleSheet {_NS}>'
          # 164 ist die erste freie Nummer -- 0 bis 163 sind von Excel
          # vergeben und duerfen nicht neu belegt werden.
          '<numFmts count="1">'
          '<numFmt numFmtId="164" formatCode="#,##0.00"/></numFmts>'
          '<fonts count="5">'
          '<font><sz val="11"/><name val="Calibri"/></font>'
          '<font><b/><sz val="11"/><name val="Calibri"/></font>'
          '<font><b/><sz val="15"/><name val="Calibri"/></font>'
          '<font><sz val="9"/><color rgb="FF6B7580"/><name val="Calibri"/></font>'
          '<font><sz val="10"/><name val="Consolas"/></font>'
          '</fonts>'
          '<fills count="3">'
          # Die ersten beiden sind Pflicht und muessen genau so
          # aussehen: Excel verlangt none und gray125 an Position 0
          # und 1 und zeigt die Datei sonst als beschaedigt an.
          '<fill><patternFill patternType="none"/></fill>'
          '<fill><patternFill patternType="gray125"/></fill>'
          '<fill><patternFill patternType="solid">'
          '<fgColor rgb="FFEFF1F3"/><bgColor indexed="64"/></patternFill>'
          '</fill></fills>'
          '<borders count="2">'
          '<border><left/><right/><top/><bottom/><diagonal/></border>'
          '<border><left/><right/><top/>'
          '<bottom style="thin"><color rgb="FFC8CDD3"/></bottom>'
          '<diagonal/></border></borders>'
          '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" '
          'borderId="0"/></cellStyleXfs>'
          '<cellXfs count="6">'
          '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
          '<xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" '
          'applyFont="1" applyFill="1" applyBorder="1"/>'
          '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" xfId="0" '
          'applyFont="1"/>'
          '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" '
          'applyNumberFormat="1"/>'
          '<xf numFmtId="0" fontId="3" fillId="0" borderId="0" xfId="0" '
          'applyFont="1"/>'
          '<xf numFmtId="0" fontId="4" fillId="0" borderId="0" xfId="0" '
          'applyFont="1"/>'
          '</cellXfs>'
          '<cellStyles count="1"><cellStyle name="Normal" xfId="0" '
          'builtinId="0"/></cellStyles></styleSheet>')

_TYPEN = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""

_MAPPE_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""


def _blattname(titel: str) -> str:
    """Was Excel als Registername akzeptiert.

    Verboten sind : \\ / ? * [ ], hoechstens 31 Zeichen, nicht leer.
    Ein Name mit einem dieser Zeichen laesst die Datei gar nicht erst
    aufgehen -- und Titel kommen vom Modell.
    """
    name = re.sub(r"[:\\/?*\[\]]", " ", str(titel or "")).strip()
    name = " ".join(name.split())[:31]
    return name or "Tabelle"


def schreiben(ziel, titel: str, bloecke, untertitel: str = "",
              stand: str = "") -> None:
    """Die Datei schreiben. bloecke kommen aus markdown_lesen.lesen()."""
    from .. import config
    from . import markdown_lesen

    if markdown_lesen._gleicher_titel(bloecke, titel):
        bloecke = list(bloecke)[1:]

    jetzt = datetime.now()
    zeilen = []          # je Eintrag: (liste von (text, stil))
    breiten = {}

    def merken(spalte, text):
        laenge = len(str(text or ""))
        if laenge:
            breiten[spalte] = min(BREITE_MAX,
                                  max(breiten.get(spalte, BREITE_MIN),
                                      laenge + 2))

    def reihe(zellen):
        for i, (text, _stil) in enumerate(zellen, start=1):
            merken(i, text)
        zeilen.append(zellen)

    absender = str(getattr(config, "DOKUMENT_ABSENDER", "") or "").strip()
    if absender:
        reihe([(absender, KOPFZEILE)])
        for z in getattr(config, "DOKUMENT_ZEILEN", []) or []:
            if str(z).strip():
                reihe([(str(z).strip(), LEISE)])
        reihe([("", NORMAL)])

    reihe([(titel, TITEL)])
    if untertitel:
        reihe([(untertitel, LEISE)])
    reihe([(str(stand or f"Stand {jetzt:%d.%m.%Y, %H:%M} Uhr"), LEISE)])
    reihe([("", NORMAL)])

    einfrieren = 0
    for b in bloecke or []:
        art = b.get("art")
        if art == "tabelle":
            kopf = [(_text_von(z), KOPFZEILE) for z in b.get("kopf") or []]
            if kopf:
                reihe(kopf)
                if (not einfrieren
                        and len(b.get("zeilen") or []) >= EINFRIEREN_AB):
                    einfrieren = len(zeilen)
            for r in b.get("zeilen") or []:
                reihe([(_text_von(z), NORMAL) for z in r])
            reihe([("", NORMAL)])
        elif art == "ueberschrift":
            reihe([(_text_von(b.get("teile")), KOPFZEILE)])
        elif art in ("absatz", "zitat"):
            reihe([(_text_von(b.get("teile")), NORMAL)])
        elif art == "liste":
            geordnet = b.get("geordnet")
            # Je Stufe eine eigene Zaehlung: Sonst laufen Haupt- und
            # Unterpunkte durch dieselbe Nummer und aus 1/2/3 wird
            # 1/2/3/4/5 quer ueber die Ebenen.
            zaehler = {}
            for punkt in b.get("punkte") or []:
                stufe = int(punkt.get("stufe") or 0)
                for tiefer in [s for s in zaehler if s > stufe]:
                    zaehler[tiefer] = 0
                zaehler[stufe] = zaehler.get(stufe, 0) + 1
                marke = f"{zaehler[stufe]}." if geordnet else "•"
                if punkt.get("haken") is not None:
                    marke = ""      # das Hakenzeichen ist schon Marke genug
                text = markdown_lesen.punkt_text(punkt)
                einzug = "    " * stufe
                reihe([(f"{einzug}{marke} {text}".rstrip()
                        if marke else f"{einzug}{text}", NORMAL)])
        elif art == "code":
            for z in str(b.get("text") or "").split("\n"):
                reihe([(z, FEST)])
        elif art == "linie":
            reihe([("", NORMAL)])

    fuss = str(getattr(config, "DOKUMENT_FUSS", "") or "").strip()
    if not fuss and not absender:
        fuss = f"Erzeugt von Sarvis am {jetzt:%d.%m.%Y um %H:%M} Uhr"
    if fuss:
        reihe([("", NORMAL)])
        reihe([(fuss, LEISE)])

    xml_zeilen = []
    for nr, zellen in enumerate(zeilen, start=1):
        inhalt = "".join(_zelle(i, nr, text, stil)
                         for i, (text, stil) in enumerate(zellen, start=1))
        xml_zeilen.append(f'<row r="{nr}">{inhalt}</row>')

    spalten = "".join(
        f'<col min="{i}" max="{i}" width="{b}" customWidth="1"/>'
        for i, b in sorted(breiten.items())) or '<col min="1" max="1" width="40"/>'

    if einfrieren:
        sicht = ('<sheetView tabSelected="1" workbookViewId="0">'
                 f'<pane ySplit="{einfrieren}" topLeftCell="A{einfrieren + 1}" '
                 'activePane="bottomLeft" state="frozen"/></sheetView>')
    else:
        sicht = '<sheetView tabSelected="1" workbookViewId="0"/>'

    letzte = max(len(z) for z in zeilen) if zeilen else 1
    blatt = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             f'<worksheet {_NS}>'
             f'<dimension ref="A1:{_spaltenname(letzte)}{max(len(zeilen), 1)}"/>'
             f'<sheetViews>{sicht}</sheetViews>'
             '<sheetFormatPr defaultRowHeight="15"/>'
             f'<cols>{spalten}</cols>'
             f'<sheetData>{"".join(xml_zeilen)}</sheetData>'
             '</worksheet>')

    mappe = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             f'<workbook {_NS}><sheets>'
             f'<sheet name="{_x(_blattname(titel))}" sheetId="1" '
             'r:id="rId1"/></sheets></workbook>')

    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _TYPEN)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("xl/workbook.xml", mappe)
        z.writestr("xl/_rels/workbook.xml.rels", _MAPPE_RELS)
        z.writestr("xl/worksheets/sheet1.xml", blatt)
        z.writestr("xl/styles.xml", _STILE)
