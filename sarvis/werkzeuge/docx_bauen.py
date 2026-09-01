"""Eine Word-Datei schreiben -- ohne Bibliothek.

WARUM KEIN python-docx

Es waere eine Zeile in requirements.txt und danach ein Neubau des
Images: Die pip-Schicht haengt an requirements.txt, und wer sie
anfasst, zieht die 1,5 GB CUDA-Raeder noch einmal. Fuer ein Format,
von dem hier sechs Elemente gebraucht werden -- Ueberschrift, Absatz,
Liste, Tabelle, Code, Link --, ist das der falsche Preis. Dieselbe
Rechnung wie beim Browser (kein Playwright) und beim Ton (kein ffmpeg),
und sie steht aus demselben Grund hier im Kopf: damit der Naechste
nicht denkt, es sei aus Unkenntnis unterblieben.

WAS EIN .DOCX WIRKLICH IST

Ein ZIP mit XML darin. Fuenf Dateien reichen fuer ein Dokument, das
Word, LibreOffice und Google Docs oeffnen:

    [Content_Types].xml     welcher Teil welchen Typ hat
    _rels/.rels             wo das Hauptdokument liegt
    word/document.xml       der Inhalt
    word/styles.xml         Ueberschrift 1-3, Zitat, Code
    word/numbering.xml      Aufzaehlung und Nummerierung
    word/_rels/document.xml.rels    die Ziele der Links

ECHTE LISTEN UND KEINE PUNKTE ALS TEXT. Ein "• " am Zeilenanfang sieht
im ersten Moment gleich aus und ist beim ersten Bearbeiten falsch: Wer
in Word einen Punkt einfuegt, bekommt keinen zweiten dazu, und beim
Umbrechen haengt die zweite Zeile unter dem Punkt statt neben ihm. Der
Sinn einer Word-Datei ist, dass man darin weiterschreibt.

XML-SICHERHEIT: Jeder Text geht durch _x(). Es gibt keinen Pfad, auf
dem ein Zeichen aus der Eingabe unveraendert in die Datei kommt -- eine
Ueberschrift, die "</w:t>" enthaelt, waere sonst kein Angriff, aber ein
kaputtes Dokument, und zwar eines, das Word wortlos verweigert.
"""
import zipfile
from datetime import datetime

# Namensraeume. Nur die drei, die gebraucht werden -- Word ergaenzt den
# Rest beim ersten Speichern selbst.
_NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
       'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')

# Steuerzeichen, die in XML 1.0 ueberhaupt nicht vorkommen duerfen --
# auch nicht als Entitaet. Ein einziges davon macht die Datei
# unlesbar, und Word sagt dann nur "Der Inhalt weist Probleme auf".
_VERBOTEN = {c: None for c in range(0x20) if c not in (0x09, 0x0A, 0x0D)}


def _x(text) -> str:
    """Text in XML-Text. Der einzige Weg, auf dem Eingabe hineinkommt."""
    return (str(text or "")
            .translate(_VERBOTEN)
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def _lauf(teil: dict, links: dict) -> str:
    """Ein Stueck Text mit seiner Auszeichnung."""
    eigenschaften = []
    if teil.get("fett"):
        eigenschaften.append("<w:b/>")
    if teil.get("kursiv"):
        eigenschaften.append("<w:i/>")
    if teil.get("durch"):
        eigenschaften.append("<w:strike/>")
    if teil.get("code"):
        eigenschaften.append('<w:rFonts w:ascii="Consolas" '
                             'w:hAnsi="Consolas"/>')
    ziel = str(teil.get("ziel") or "")
    if ziel:
        # Blau und unterstrichen: Word malt einen Hyperlink nicht von
        # selbst, es folgt dem Zeichenformat. Ohne das sieht der Link
        # aus wie Fliesstext und niemand klickt.
        eigenschaften.append('<w:color w:val="2C7BE5"/><w:u w:val="single"/>')
    rpr = f"<w:rPr>{''.join(eigenschaften)}</w:rPr>" if eigenschaften else ""
    # xml:space="preserve" -- ohne das frisst Word die Leerzeichen
    # zwischen zwei Laeufen, und aus "ein **fetter** Satz" wird
    # "einfetterSatz".
    lauf = (f"<w:r>{rpr}"
            f'<w:t xml:space="preserve">{_x(teil.get("text"))}</w:t></w:r>')
    if ziel:
        kennung = links.setdefault(ziel, f"rId{100 + len(links)}")
        return f'<w:hyperlink r:id="{kennung}">{lauf}</w:hyperlink>'
    return lauf


def _absatz(teile, links: dict, stil: str = "", liste: int = 0,
            stufe: int = 0) -> str:
    eigenschaften = []
    if stil:
        eigenschaften.append(f'<w:pStyle w:val="{stil}"/>')
    if liste:
        eigenschaften.append(f'<w:numPr><w:ilvl w:val="{stufe}"/>'
                             f'<w:numId w:val="{liste}"/></w:numPr>')
    ppr = f"<w:pPr>{''.join(eigenschaften)}</w:pPr>" if eigenschaften else ""
    laeufe = "".join(_lauf(t, links) for t in (teile or [{"text": ""}]))
    return f"<w:p>{ppr}{laeufe}</w:p>"


def _tabelle(block: dict, links: dict) -> str:
    def zelle(teile, kopf=False):
        schatten = ('<w:shd w:val="clear" w:color="auto" w:fill="EFEFEF"/>'
                    if kopf else "")
        inhalt = [dict(t, fett=True) for t in teile] if kopf else teile
        return (f"<w:tc><w:tcPr>{schatten}</w:tcPr>"
                f"{_absatz(inhalt, links)}</w:tc>")

    spalten = max([len(block.get("kopf") or [])]
                  + [len(z) for z in block.get("zeilen") or []] + [1])
    # Rahmen einzeln: Ein Tabellenstil waere kuerzer, aber "TableGrid"
    # muss dann in styles.xml stehen und heisst in aelteren Fassungen
    # anders. Sechs Zeilen hier gelten ueberall.
    kanten = "".join(
        f'<w:{k} w:val="single" w:sz="4" w:space="0" w:color="D0D0D0"/>'
        for k in ("top", "left", "bottom", "right", "insideH", "insideV"))
    reihen = []
    if block.get("kopf"):
        reihen.append("<w:tr>" + "".join(zelle(z, True)
                                         for z in block["kopf"]) + "</w:tr>")
    for zeile in block.get("zeilen") or []:
        # Fehlende Zellen auffuellen: Ein Modell laesst in der letzten
        # Spalte gern eine leer, und Word zeigt eine unvollstaendige
        # Reihe als zerrissene Tabelle.
        gefuellt = list(zeile) + [[{"text": ""}]] * (spalten - len(zeile))
        reihen.append("<w:tr>" + "".join(zelle(z)
                                         for z in gefuellt[:spalten]) + "</w:tr>")
    return ("<w:tbl><w:tblPr>"
            '<w:tblW w:w="5000" w:type="pct"/>'
            f"<w:tblBorders>{kanten}</w:tblBorders>"
            "</w:tblPr>" + "".join(reihen) + "</w:tbl>")


def _koerper(bloecke, links: dict) -> str:
    aus = []
    for b in bloecke or []:
        art = b.get("art")
        if art == "ueberschrift":
            aus.append(_absatz(b.get("teile"), links,
                               stil=f"Ueberschrift{min(int(b.get('stufe') or 1), 3)}"))
        elif art == "absatz":
            aus.append(_absatz(b.get("teile"), links))
        elif art == "zitat":
            aus.append(_absatz(b.get("teile"), links, stil="Zitat"))
        elif art == "code":
            # Zeilenweise, weil ein <w:br/> in Word zwar umbricht, aber
            # der graue Kasten dann eine einzige hohe Flaeche ist und
            # beim Bearbeiten zusammenklappt.
            for zeile in str(b.get("text") or "").split("\n"):
                aus.append(_absatz([{"text": zeile, "code": True}], links,
                                   stil="Quelltext"))
        elif art == "liste":
            nummer = 2 if b.get("geordnet") else 1
            for punkt in b.get("punkte") or []:
                teile = list(punkt.get("teile") or [])
                haken = punkt.get("haken")
                if haken is not None:
                    # Das Zeichen als eigener Lauf davor -- in Word gibt
                    # es kein Kontrollkaestchen in einer Aufzaehlung,
                    # und ein echtes Formularfeld waere hier ein
                    # Fremdkoerper, den man beim Bearbeiten nicht los
                    # wird.
                    from . import markdown_lesen
                    zeichen = (markdown_lesen.HAKEN_AN if haken
                               else markdown_lesen.HAKEN_AUS)
                    teile = [{"text": zeichen + " "}] + teile
                aus.append(_absatz(teile, links, liste=nummer,
                                   stufe=int(punkt.get("stufe") or 0)))
        elif art == "tabelle":
            aus.append(_tabelle(b, links))
            # Word klebt zwei Tabellen ohne Absatz dazwischen zu einer
            # zusammen. Der leere Absatz ist keine Zierde.
            aus.append("<w:p/>")
        elif art == "linie":
            aus.append('<w:p><w:pPr><w:pBdr><w:bottom w:val="single" '
                       'w:sz="6" w:space="1" w:color="C8C8C8"/></w:pBdr>'
                       "</w:pPr></w:p>")
    return "".join(aus)


_TYPEN = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
</Types>"""

_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""


def _stil(kennung, name, groesse, farbe="1A1A1A", fett=False, kursiv=False,
          abstand=240, schrift="") -> str:
    r = []
    if schrift:
        r.append(f'<w:rFonts w:ascii="{schrift}" w:hAnsi="{schrift}"/>')
    if fett:
        r.append("<w:b/>")
    if kursiv:
        r.append("<w:i/>")
    r.append(f'<w:color w:val="{farbe}"/><w:sz w:val="{groesse}"/>')
    return (f'<w:style w:type="paragraph" w:styleId="{kennung}">'
            f'<w:name w:val="{name}"/><w:qFormat/>'
            f'<w:pPr><w:spacing w:before="{abstand}" w:after="120"/></w:pPr>'
            f"<w:rPr>{''.join(r)}</w:rPr></w:style>")


# Halbe Punkte: w:sz zaehlt in Halbpunkten, 22 sind also 11 pt.
_STILE = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
          f"<w:styles {_NS}>"
          '<w:docDefaults><w:rPrDefault><w:rPr>'
          '<w:rFonts w:ascii="Calibri" w:hAnsi="Calibri"/>'
          '<w:sz w:val="22"/></w:rPr></w:rPrDefault></w:docDefaults>'
          # Der Standardabsatz. Er sieht nach nichts aus und fehlt
          # trotzdem schmerzhaft: Ein Absatz ohne pStyle verweist auf
          # den Vorgabestil, und wenn es den nicht gibt, hat er GAR
          # keinen. Gemessen mit python-docx an der ersten Fassung:
          # paragraph.style war None. Word repariert das still, andere
          # Leser nicht.
          '<w:style w:type="paragraph" w:default="1" w:styleId="Standard">'
          '<w:name w:val="Normal"/><w:qFormat/>'
          '<w:pPr><w:spacing w:after="140" w:line="276" '
          'w:lineRule="auto"/></w:pPr></w:style>'
          + _stil("Ueberschrift1", "heading 1", 36, "1A1A1A", fett=True,
                  abstand=360)
          + _stil("Ueberschrift2", "heading 2", 28, "1A1A1A", fett=True)
          + _stil("Ueberschrift3", "heading 3", 24, "444444", fett=True)
          + _stil("Zitat", "Quote", 22, "555555", kursiv=True)
          + _stil("Quelltext", "HTML Code", 20, "222222", abstand=0,
                  schrift="Consolas")
          + "</w:styles>")

# Zwei Nummerierungen: 1 = Punkte, 2 = Zahlen. Beide mit Einzug, sonst
# klebt der Text am Rand.
def _ebenen_punkte() -> str:
    """Drei Ebenen Aufzaehlung -- Punkt, Strich, Kreis.

    Die Zeichen wechseln je Ebene, wie in Word ueblich. Ohne das saehen
    Unterpunkte genauso aus wie Hauptpunkte und die Verschachtelung
    waere nur noch am Einzug zu erkennen -- und der geht beim ersten
    Umformatieren verloren.
    """
    zeichen = ("\u2022", "\u2013", "\u25e6")
    return "".join(
        f'<w:lvl w:ilvl="{i}"><w:numFmt w:val="bullet"/>'
        f'<w:lvlText w:val="{z}"/>'
        f'<w:pPr><w:ind w:left="{720 + i * 360}" w:hanging="360"/></w:pPr>'
        '<w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial"/></w:rPr></w:lvl>'
        for i, z in enumerate(zeichen))


def _ebenen_zahlen() -> str:
    """Drei Ebenen Nummerierung -- 1. / a) / i.

    Jede Ebene zaehlt fuer sich; start bei 1. %2 und %3 beziehen sich
    auf die eigene Ebene, nicht auf die daruberliegende -- "2.a)" waere
    Word-Standard, ist aber in einer Aufstellung schwerer zu lesen als
    ein schlichtes a).
    """
    formate = (("decimal", "%1."), ("lowerLetter", "%2)"),
               ("lowerRoman", "%3."))
    return "".join(
        f'<w:lvl w:ilvl="{i}"><w:start w:val="1"/>'
        f'<w:numFmt w:val="{art}"/><w:lvlText w:val="{text}"/>'
        f'<w:pPr><w:ind w:left="{720 + i * 360}" w:hanging="360"/></w:pPr>'
        "</w:lvl>"
        for i, (art, text) in enumerate(formate))


_NUMMERN = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            f"<w:numbering {_NS}>"
            '<w:abstractNum w:abstractNumId="1">'
            + _ebenen_punkte() + "</w:abstractNum>"
            '<w:abstractNum w:abstractNumId="2">'
            + _ebenen_zahlen() + "</w:abstractNum>"
            '<w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num>'
            '<w:num w:numId="2"><w:abstractNumId w:val="2"/></w:num>'
            "</w:numbering>")


def schreiben(ziel, titel: str, bloecke, untertitel: str = "",
              stand: str = "") -> None:
    """Die Datei schreiben. bloecke kommen aus markdown_lesen.lesen()."""
    from .. import config

    links: dict = {}
    jetzt = datetime.now()

    # Derselbe Kopf wie auf der Seite, und dieselbe Regel dahinter:
    # config.DOKUMENT_ABSENDER entscheidet, wer oben steht. Ohne
    # Eintrag ist es Sarvis; mit Eintrag der Absender, denn ein
    # Dokument, das weitergegeben wird, kommt nicht vom Assistenten.
    absender = str(getattr(config, "DOKUMENT_ABSENDER", "") or "").strip()
    kopf = []
    if absender:
        kopf.append(_absatz([{"text": absender, "fett": True}], links))
        for zeile in getattr(config, "DOKUMENT_ZEILEN", []) or []:
            if str(zeile).strip():
                kopf.append(_absatz([{"text": str(zeile).strip()}], links,
                                    stil="Zitat"))
    kopf.append(_absatz([{"text": titel}], links, stil="Ueberschrift1"))
    if untertitel:
        kopf.append(_absatz([{"text": untertitel, "kursiv": True}], links))
    kopf.append(_absatz(
        [{"text": str(stand or f"Stand {jetzt:%d.%m.%Y, %H:%M} Uhr")}],
        links, stil="Zitat"))

    # Der Koerper ZUERST bauen: Er fuellt links, und die Beziehungsdatei
    # muss danach geschrieben werden. Andersherum waere jeder Link im
    # Dokument eine Kennung ohne Ziel -- Word meldet das als Fehler in
    # der Datei, nicht als fehlenden Link.
    # Dieselbe Doppelung wie auf der Seite -- und hier faellt sie noch
    # mehr auf, weil Word beide als "Ueberschrift 1" ins
    # Inhaltsverzeichnis nimmt.
    from . import markdown_lesen
    if markdown_lesen._gleicher_titel(bloecke, titel):
        bloecke = list(bloecke)[1:]
    koerper = _koerper(bloecke, links)
    eigener = str(getattr(config, "DOKUMENT_FUSS", "") or "").strip()
    if eigener:
        fuss_text = eigener
    elif absender:
        fuss_text = f"{jetzt:%d.%m.%Y}"
    else:
        fuss_text = f"Erzeugt von Sarvis am {jetzt:%d.%m.%Y um %H:%M} Uhr"
    fuss = _absatz([{"text": fuss_text, "kursiv": True}], links, stil="Zitat")

    dokument = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f"<w:document {_NS}><w:body>"
                + "".join(kopf) + koerper + fuss
                # Der Abschnittsteil gehoert ans Ende des Koerpers: A4
                # hoch, 2 cm Rand (1134 Twips = 2 cm).
                + '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                  '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" '
                  'w:left="1134"/></w:sectPr>'
                "</w:body></w:document>")

    ziele = "".join(
        f'<Relationship Id="{kennung}" Type="http://schemas.openxmlformats'
        f'.org/officeDocument/2006/relationships/hyperlink" '
        f'Target="{_x(ziel_url)}" TargetMode="External"/>'
        for ziel_url, kennung in links.items())
    dok_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/'
                'package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats'
                '.org/officeDocument/2006/relationships/styles" '
                'Target="styles.xml"/>'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats'
                '.org/officeDocument/2006/relationships/numbering" '
                'Target="numbering.xml"/>'
                + ziele + "</Relationships>")

    with zipfile.ZipFile(ziel, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _TYPEN)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", dokument)
        z.writestr("word/styles.xml", _STILE)
        z.writestr("word/numbering.xml", _NUMMERN)
        z.writestr("word/_rels/document.xml.rels", dok_rels)
