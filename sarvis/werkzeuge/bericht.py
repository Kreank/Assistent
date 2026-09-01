"""Eine ganze Seite zeigen -- fuer das, was in keine Kachel passt.

Die Kacheln koennen viel, aber sie koennen es klein: ein paar Zeilen
neben der Engine, im Vorbeigehen lesbar, hoechstens zwoelf Datenpunkte.
"Analysiere mir zwoelf Monate Finanzen, schluessle sie nach Kategorien
auf und zeig die Unterschiede" sind sechzig Werte, drei Diagramme und
eine Tabelle. Das gehoert nicht neben die Engine, das gehoert auf eine
Seite.

DIE ABGRENZUNG, dieselbe Linie wie in kacheln.py und browser.py, nur um
einen Fall erweitert:

    kachel_zeigen   Du HAST die Daten und sie passen in ein paar Zeilen.
                    Sie gehoeren neben die Engine, fuer den Blick nebenbei.
    seite_zeigen    Du HAST die Daten, aber es sind zu viele. Eine
                    Auswertung, ein Vergleich, ein Bericht -- etwas, wofuer
                    man sich hinsetzt. Du baust die Seite selbst.
    web_zeigen      Der Nutzer will eine FREMDE Seite. Nicht fuer Daten,
                    die du schon hast.

VORGESCHICHTE, die diese Datei erklaert: Sarvis hat genau das schon
einmal von sich aus versucht --

    Nutzer: "kannst du mir das nicht visuell zeigen?"
    Sarvis: "Soll ich chat-niko.html anlegen? Der Ordner tmp entsteht
             dabei in Sarvis im Ordner Privat."

Die Absicht war richtig, der Ort war falsch (mitten im Quelltext), und
die Rueckfrage stellte die falsche Frage: Sie fragte nach einem ORDNER,
waehrend es um die Darstellung ging. Beides faellt hier weg. Der Ort
steht fest (config.ABLAGE, in FREI_SCHREIBEN und in der .gitignore), und
gefragt wird nicht -- eine Seite hinzustellen ist Zeigen, kein Handeln.

NICHTS WIRD NACHGELADEN. Keine CDN, keine Schrift aus dem Netz, keine
Diagrammbibliothek. Drei Gruende, in dieser Reihenfolge:

  Ein Bericht muss auch dann vollstaendig sein, wenn das WLAN weg ist --
  sonst steht der Nutzer vor einer Seite mit unbeschrifteten Kaesten und
  haelt Sarvis fuer kaputt.
  Eine Seite, die etwas nachlaedt, verraet dabei, wann sie geoeffnet
  wurde und was darauf steht. Die Daten hier sind Kontostaende.
  Der eingebaute Browser laedt aus einem eigenen Profil; jeder Abruf
  nach draussen waere ein Zeitfenster, in dem die Seite haengt.

Durchgesetzt wird das nicht durch Vorsatz, sondern durch eine
Content-Security-Policy im Kopf der Seite (siehe SICHERHEIT): Chromium
laedt dann gar nichts Externes mehr, auch wenn das Modell doch einmal
ein <img src="https://..."> in den Rumpf schreibt.

DIAGRAMME BAUT PYTHON, NICHT DAS MODELL. Sarvis liefert Zahlen, dieses
Modul rechnet daraus SVG. Die Alternative -- CSS-Klassen fuer Balken --
haette bedeutet, dass das Modell die Prozentwerte selbst ausrechnet, und
eine falsch skalierte Achse sieht man einem Bild nicht an. Gerechnet
wird hier, aus demselben Grund, aus dem finanzen_vergleich in Python
subtrahiert: Eine gerechnete Zahl kann nicht halluziniert sein.
"""
import asyncio
import re
from datetime import datetime
from html import escape

from claude_agent_sdk import tool

from .. import config
from .. import anzeige as anzeige_modul

# --- Farben ---------------------------------------------------------------
# Die Zustandsfarben der Engine aus hud.py (FARBEN). Bewusst KOPIERT und
# nicht importiert -- dasselbe Vorgehen wie bei GERAETENAMEN in
# browser.py: hud.py zieht PySide6 mit, und die Werkzeuge laufen im
# Sprachprozess, der keine Qt-Anwendung ist. Ein Import kostete hier
# Sekunden fuer fuenf Zahlen.
RUHIG = "#7E9EC8"
HOERT = "#00E5FF"
DENKT = "#B47CFF"
SPRICHT = "#FFB347"
FRAGT = "#FF788C"

# --- Dateinamen -----------------------------------------------------------
# Windows haelt diese Namen fuer Geraete und nicht fuer Dateien. Gleiche
# Liste wie in werkzeuge/google.py und browser.py.
GERAETENAMEN = ({"CON", "PRN", "AUX", "NUL"}
                | {f"COM{i}" for i in range(1, 10)}
                | {f"LPT{i}" for i in range(1, 10)})

# Laenge des Namensstamms. Windows deckelt den ganzen Pfad bei 260
# Zeichen, und ein Titel vom Modell kann ein ganzer Satz sein.
NAME_MAX = 60

# So viele Berichte bleiben liegen. Der Ordner ist ein Werktisch, kein
# Archiv: Was aelter ist als die letzten dreissig, hat niemand mehr
# aufgemacht -- und die Datei selbst ist in einer Sekunde neu gebaut,
# solange die Daten noch da sind. Aufgeraeumt wird ausschliesslich, was
# dieses Modul selbst angelegt hat (siehe _NAMENSMUSTER).
BERICHTE_BEHALTEN = 30

# Nur Dateien, deren Name auf unseren Zeitstempel endet -- "-20260828-1433"
# oder "-20260828-1433-2". Wer sonst noch etwas in die Ablage legt (ein
# Auftrag, der Nutzer selbst), soll es dort wiederfinden.
# Woran dieses Modul seine eigenen Erzeugnisse wiedererkennt. Die drei
# Endungen, weil _aufraeumen sonst PDFs und Word-Dateien liegen liesse
# und der Ordner nur noch waechst (werkzeuge/dokument.py legt sie hier
# ab, nach demselben Muster und mit Absicht).
_NAMENSMUSTER = re.compile(r"-\d{8}-\d{4}(-\d+)?\.(html|pdf|docx)$")

# Hoechstens so viele Datenpunkte je Diagramm. Vierzig Saeulen auf 900
# Punkten Breite sind rund zwanzig Punkte je Saeule -- darunter wird aus
# dem Diagramm ein Kamm.
DIAGRAMM_MAX = 40

# Wie viele Diagramme eine Seite traegt. Mehr liest niemand am Stueck,
# und jedes einzelne kostet ein paar Kilobyte im Dokument.
DIAGRAMME_MAX = 12

# Der Rumpf kommt vom Modell und geht ungeprueft in die Datei -- das ist
# der Sinn der Sache. Eine Obergrenze steht trotzdem davor: Ein Bericht
# von zwei Megabyte ist kein Bericht, sondern ein Unfall in einer
# Schleife.
INHALT_MAX = 400_000

# Wie lange auf die Antwort der Anzeige gewartet wird, wenn wir wissen
# wollen, ob das Fenster wirklich aufgegangen ist. Kurz: Die Frage
# beantwortet der Anzeigeprozess ohne Netz und ohne Platte.
STAND_ZEITLIMIT = 3.0

# --- Sicherheit -----------------------------------------------------------
# Die harte Regel als Regel des Browsers, nicht als Vorsatz des Autors.
#
#   default-src 'none'     nichts wird geladen: kein Skript, kein
#                          Stylesheet, kein Bild, kein iframe, kein fetch
#   style-src 'unsafe-inline'   der eigene <style>-Block und
#                          style="..."-Attribute im Rumpf
#   img-src data:          eingebettete Bilder bleiben moeglich, aber nur
#                          als Daten IM Dokument
#
# Ein <a href="https://..."> bleibt erlaubt und ist auch richtig so: Ein
# Link ist kein Ladevorgang. Er tut erst etwas, wenn der Nutzer klickt --
# und dann ist es seine Entscheidung.
SICHERHEIT = ("default-src 'none'; style-src 'unsafe-inline'; "
              "img-src data:; font-src 'none'; connect-src 'none'; "
              "form-action 'none'; base-uri 'none'")

# --- Der Rahmen -----------------------------------------------------------
# Sarvis soll nicht bei jedem Bericht CSS erfinden. Er liefert den Rumpf,
# der Rahmen kommt von hier -- dunkler Grund, die Farben der Engine,
# ruhige Typografie. Damit sieht ein Bericht aus wie Sarvis und nicht wie
# eine fremde Webseite.
#
# Die Schrift ist eine Systemschrift-Kette. Segoe UI ist auf jedem
# Windows da; die uebrigen Eintraege stehen fuer den Fall, dass das
# jemand woanders aufmacht.
#
# Breite: Das Fenster ist 1100 Punkte breit (config.BROWSER_BREITE) und
# laesst sich groesser ziehen. Deshalb eine Spalte mit max-width und
# margin:auto -- bei 1100 fuellt sie das Fenster fast ganz, bei 2000
# steht sie mittig statt in ellenlangen Zeilen auseinandergezogen.
# Kennzahlen und Tabellen bekommen dazu ihre eigene Regel, damit weder
# das eine umbricht noch das andere den Seitenrand sprengt.
_WURZEL_CSS = (
    ":root{"
    "--grund:#070B11;--flaeche:#0D141E;--kante:#1B2836;"
    "--text:#E6EEF7;--leise:#94A9C0;--gitter:#18242F;"
    "--ruhig:" + RUHIG + ";--hoert:" + HOERT + ";--denkt:" + DENKT + ";"
    "--spricht:" + SPRICHT + ";--fragt:" + FRAGT + "}"
)

_STIL = _WURZEL_CSS + """
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--grund);color:var(--text);
 font-family:"Segoe UI",system-ui,-apple-system,Roboto,"Helvetica Neue",
 Arial,sans-serif;font-size:15px;line-height:1.6;
 -webkit-font-smoothing:antialiased}
.spalte{max-width:1040px;margin:0 auto;padding:0 28px}
.kopf{border-bottom:1px solid var(--kante);
 background:linear-gradient(180deg,#0C141F 0%,var(--grund) 100%);
 padding:26px 0 22px;margin-bottom:34px}
.marke{display:flex;align-items:center;gap:9px;color:var(--ruhig);
 font-size:12px;letter-spacing:.22em;text-transform:uppercase}
.marke svg{width:20px;height:20px;flex:0 0 auto}
h1{margin:14px 0 0;font-size:30px;line-height:1.2;font-weight:600;
 letter-spacing:-.01em}
.unter{margin:8px 0 0;color:var(--leise);font-size:16px;max-width:70ch}
.absender{margin:4px 0 0;color:var(--leise);font-size:12.5px;
 line-height:1.55}
.stand{margin:12px 0 0;color:var(--ruhig);font-size:12.5px;
 letter-spacing:.08em;text-transform:uppercase}
h2{margin:38px 0 14px;font-size:19px;font-weight:600;letter-spacing:-.005em;
 padding-bottom:8px;border-bottom:1px solid var(--kante)}
h3{margin:26px 0 8px;font-size:15px;font-weight:600;color:var(--ruhig)}
/* h4 GIBT ES SEIT MARKDOWN, und vorher gab es sie nicht.
   markdown_lesen.als_html schiebt jede Ueberschrift eine Ebene tiefer,
   weil h1 dem Titel im Kopf gehoert -- aus "###" wird also h4. Ohne
   diese Zeile stand die dritte Gliederungsebene im Browserstandard
   mitten in einer durchgestalteten Seite; gemessen an einem Muster mit
   drei Ebenen fiel genau sie heraus. */
h4{margin:22px 0 7px;font-size:13.5px;font-weight:600;
 letter-spacing:.03em;color:var(--leise)}
p{margin:0 0 12px}

/* WAS MARKDOWN ERZEUGT.

   Bis hierher schrieb das Modell den Rumpf als HTML und benutzte dabei
   die Klassen weiter unten (.kennzahl, .tabelle, .hinweis). Seit
   werkzeuge/dokument.py kommt der Rumpf auch aus Markdown, und das
   erzeugt schlichte Tags: ul, ol, blockquote, pre, code, hr. Die waren
   hier nie gestaltet -- eine Aufzaehlung stand dann im Browserstandard
   mitten in einer sonst durchgestalteten Seite, und im PDF genauso.
   Gemessen an einem Muster-Angebot: das Zitat war ein eingerueckter
   Absatz ohne jedes Kennzeichen.

   Bewusst zurueckhaltend: Diese Tags sollen aussehen wie der Rest,
   nicht auffallen. */
ul,ol{margin:0 0 14px;padding-left:24px}
li{margin:0 0 6px}
li::marker{color:var(--ruhig)}
/* Eine Unterliste steht IM li ihres Punktes. Ohne diese Zeile setzt
   der Browser den Aussenabstand des Blocks noch einmal darunter, und
   zwischen Unterpunkt und naechstem Hauptpunkt klafft eine Luecke, die
   aussieht wie ein Absatzende. */
li > ul,li > ol{margin:5px 0 0}
s{color:var(--leise)}
/* Das Hakenzeichen traegt die Aussage, nicht der Aufzaehlungspunkt --
   deshalb bekommt es die Farbe und der Punkt daneben verschwindet. */
.haken{color:var(--ruhig);margin-right:2px}
blockquote{margin:0 0 14px;padding:2px 0 2px 15px;
 border-left:2px solid var(--kante);color:var(--leise)}
hr{border:0;border-top:1px solid var(--kante);margin:26px 0}
code{font-family:Consolas,ui-monospace,"SF Mono",monospace;font-size:.88em;
 padding:1px 6px;border-radius:5px;background:var(--flaeche);
 border:1px solid var(--kante)}
pre{margin:0 0 16px;padding:13px 15px;border-radius:9px;
 background:var(--flaeche);border:1px solid var(--kante);overflow-x:auto}
pre code{padding:0;border:0;background:none;font-size:12.5px;line-height:1.55}
a{color:var(--hoert)}
strong{color:#fff;font-weight:600}
.block{margin:0 0 34px}
.hinweis{color:var(--leise);font-size:13.5px}
.gut{color:var(--hoert)}
.schlecht{color:var(--fragt)}
.punkte{margin:0 0 12px;padding-left:20px}
.punkte li{margin:0 0 5px}
.kennzahlen{display:grid;gap:14px;margin:0 0 26px;
 grid-template-columns:repeat(auto-fit,minmax(190px,1fr))}
.kennzahl{background:var(--flaeche);border:1px solid var(--kante);
 border-left:2px solid var(--hoert);border-radius:9px;padding:14px 16px}
.kennzahl .wert{display:block;font-size:25px;font-weight:600;
 line-height:1.15;font-variant-numeric:tabular-nums}
.kennzahl .etikett{display:block;margin-top:5px;color:var(--leise);
 font-size:12.5px;letter-spacing:.05em;text-transform:uppercase}
.kennzahl .dazu{display:block;margin-top:6px;font-size:13px;
 color:var(--leise)}
.tabelle{overflow-x:auto;margin:0 0 22px;border:1px solid var(--kante);
 border-radius:9px;background:var(--flaeche)}
table{border-collapse:collapse;width:100%;min-width:460px;font-size:14px}
th,td{padding:9px 14px;text-align:left;
 border-bottom:1px solid var(--kante);white-space:nowrap}
th{color:var(--ruhig);font-weight:600;font-size:12px;letter-spacing:.07em;
 text-transform:uppercase;background:#101A26}
tbody tr:last-child td{border-bottom:none}
tbody tr:hover td{background:#101A26}
td.zahl,th.zahl{text-align:right;font-variant-numeric:tabular-nums}
tfoot td{font-weight:600;background:#101A26;border-top:1px solid var(--kante)}
.diagramm{margin:0 0 26px;padding:16px 18px 12px;background:var(--flaeche);
 border:1px solid var(--kante);border-radius:9px}
.diagramm figcaption{margin:0 0 10px;color:var(--ruhig);font-size:12.5px;
 letter-spacing:.07em;text-transform:uppercase}
.diagramm svg{display:block;width:100%;height:auto}
.legende{display:flex;flex-wrap:wrap;gap:16px;margin-top:8px;
 color:var(--leise);font-size:12.5px}
.legende span{display:flex;align-items:center;gap:6px}
.legende i{width:11px;height:11px;border-radius:3px;display:inline-block}
.ax{fill:var(--leise);font-size:12px}
.bn{fill:var(--text);font-size:13px}
.wl{fill:var(--leise);font-size:11.5px}
/* Nur oben und unten, und zwar bei BEIDEM: .fuss traegt auch .spalte,
   und ein Kurzbefehl fuer margin oder padding wuerde deren seitlichen
   Einzug und das margin:auto ueberschreiben. Der Fusstext klebte dann
   im breitgezogenen Fenster links, waehrend der Rest mittig steht. */
.fuss{margin-top:44px;padding-top:18px;padding-bottom:40px;
 border-top:1px solid var(--kante);color:var(--leise);font-size:12px;
 word-break:break-all}
@media (max-width:640px){
 .spalte{padding:0 16px}
 h1{font-size:24px}
}

/* AUF PAPIER IST ALLES ANDERSHERUM.

   Der dunkle Grund ist am Bildschirm richtig und auf Papier ein Fehler
   -- eine A4-Seite Anthrazit kostet eine halbe Patrone und macht die
   Schrift schlechter lesbar, nicht besser. Chrome zieht diesen Block
   auch beim Erzeugen eines PDF heran (Page.printToPDF wertet
   @media print aus), er ist also nicht nur fuer den seltenen Fall
   gedacht, dass jemand wirklich druckt: Er IST der Stil des PDF.

   Deshalb werden hier die Variablen umgesetzt statt einzelne Regeln
   nachgezogen -- alles, was von ihnen abhaengt, kommt dann von selbst
   mit. Was das nicht erreicht, sind die drei Stellen mit fest
   eingetragener Farbe; sie stehen darunter.

   Flaechen bekommen einen Rahmen statt einer Fuellung: Ein grauer
   Kasten im Druck ist ein grauer Kasten, ein Rahmen ist eine Kontur.

   Und: keine Seitenumbrueche mitten in einer Ueberschrift oder einem
   Diagramm. Ein Balkendiagramm, das ueber zwei Seiten faellt, ist
   zweimal die Haelfte. */
@media print{
 :root{--grund:#fff;--text:#16202B;--leise:#5A6672;--ruhig:#7A5A2A;
  --flaeche:#fff;--kante:#C8CDD3}
 body{background:#fff;color:#16202B}
 .kopf{background:#fff;border-bottom:1px solid #C8CDD3}
 strong{color:#000}
 th{background:#F0F2F4;color:#3C4854}
 tfoot td,tbody tr:hover td{background:#F0F2F4}
 .spalte{max-width:none;padding:0}
 code,pre{background:#F6F7F8;border-color:#D6DAE0}
 blockquote{border-left-color:#B8BEC6}
 .fuss{padding-bottom:0}
 a{color:#16202B}
 h1,h2,h3,h4{break-after:avoid;page-break-after:avoid}
 .diagramm,.kennzahl,table,blockquote,pre{break-inside:avoid;
  page-break-inside:avoid}
 @page{margin:18mm 16mm}
}
"""

# Das Ringzeichen im Kopf. Zwei Kreise, dieselben zwei Farben wie die
# Engine im Ruhezustand -- gerade genug, dass die Seite ohne Beschriftung
# als Sarvis' Seite erkennbar ist. Inline, also ohne jeden Abruf.
_RING = ('<svg viewBox="0 0 24 24" aria-hidden="true">'
         f'<circle cx="12" cy="12" r="9" fill="none" stroke="{HOERT}" '
         'stroke-width="1.6" opacity=".85"/>'
         f'<circle cx="12" cy="12" r="3.2" fill="{RUHIG}"/></svg>')


# --- Zahlen ---------------------------------------------------------------

def _zahl(wert: float, stellen=None) -> str:
    """Eine Zahl deutsch: Punkt als Tausender, Komma als Dezimaltrenner.

    Ohne Angabe entscheidet der Betrag: Ab hundert sind Nachkommastellen
    an einer Achse nur Rauschen, darunter koennen sie der Unterschied
    sein, um den es geht.
    """
    try:
        wert = float(wert)
    except (TypeError, ValueError):
        return "?"
    if stellen is None:
        stellen = 0 if (abs(wert) >= 100
                        or abs(wert - round(wert)) < 0.005) else 2
    text = f"{wert:,.{stellen}f}"
    # Ueber ein Zeichen, das in Zahlen nicht vorkommt, tauschen -- sonst
    # macht der zweite replace die Arbeit des ersten wieder kaputt.
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def _kurz(text: str, max_zeichen: int) -> str:
    text = " ".join(str(text or "").split())
    if len(text) <= max_zeichen:
        return text
    return text[:max_zeichen - 1].rstrip() + "…"


# --- Diagramme ------------------------------------------------------------
#
# Reines SVG, von Python gerechnet. Kein Skript auf der Seite, keine
# Bibliothek, kein Nachladen -- und mit viewBox statt fester Groesse
# skaliert dasselbe Bild im 1100er Fenster und im breitgezogenen.
#
# Drei Formen, weil drei Fragen dahinterstehen:
#
#   saeulen  Wie hat sich das ueber die ZEIT entwickelt? Zwoelf Monate
#            nebeneinander, senkrecht, in der Reihenfolge der Zeit.
#   balken   Wer ist der GROESSTE? Kategorien mit Namen, waagerecht --
#            weil "Versicherungen und Beitraege" senkrecht unter einer
#            Saeule nicht lesbar ist.
#   linie    Wie ist der VERLAUF? Dasselbe wie saeulen, aber wenn es auf
#            die Richtung ankommt und nicht auf den einzelnen Wert.
#
# Zeichenflaeche fuer saeulen und linie. Links bleibt Platz fuer die
# Achsenbeschriftung, unten fuer die Namen.
_LX, _RX, _OY, _UY = 76.0, 884.0, 24.0, 268.0
_SVG_HOEHE = 300


def _punkte_lesen(roh) -> list:
    """Die Datenpunkte eines Diagramms als [(name, wert, wert2|None)].

    Was keine Zahl ist, faellt raus statt zu einer Null zu werden: Eine
    erfundene Null steht im Bild wie ein gemessener Wert da.
    """
    raus = []
    for p in list(roh or [])[:DIAGRAMM_MAX]:
        if not isinstance(p, dict):
            continue
        try:
            wert = float(p.get("wert"))
        except (TypeError, ValueError):
            continue
        zwei = p.get("wert2")
        try:
            zwei = None if zwei is None else float(zwei)
        except (TypeError, ValueError):
            zwei = None
        raus.append((str(p.get("name") or ""), wert, zwei))
    return raus


def _grenzen(punkte):
    """Untere Kante, obere Kante, Schrittweite -- alle drei rund.

    Zwei Entscheidungen stecken darin:

    DIE NULL IST IMMER DABEI. Eine Achse, die bei 2.800 anfaengt, macht
    aus drei Prozent Unterschied einen Berg. Das ist der aelteste Trick
    in der Statistik und in einem Bericht ueber das eigene Geld genau der
    falsche.

    RUNDE SCHRITTE. Die Kanten einfach auf den kleinsten und groessten
    Wert zu legen, ist eine Zeile weniger -- und beschriftet die Achse
    dann mit 1.101, 2.201, 3.302. Solche Zahlen liest niemand, sie sehen
    aus wie Messwerte und sind doch nur Fuenftel einer krummen Spanne.
    Also die naechstgroessere runde Schrittweite aus 1, 2, 2,5 oder 5 mal
    einer Zehnerpotenz -- und weil beide Kanten Vielfache davon sind,
    liegt die Null zwangslaeufig auf einer Linie.

    Fuenf Abschnitte als Ziel, nicht vier: Die Schrittweite wird immer
    aufgerundet, und aus vier Abschnitten werden dabei schnell drei.
    Gemessen an den Monatsausgaben unten -- mit vier reichte die Achse
    bis 6.000, obwohl der hoechste Wert 4.402 ist; mit fuenf bis 5.000.
    """
    from math import ceil, floor, log10
    werte = [w for _, w, _ in punkte]
    werte += [z for _, _, z in punkte if z is not None]
    hoch = max(werte + [0.0])
    tief = min(werte + [0.0])
    if hoch - tief < 1e-9:
        hoch = tief + 1.0
    roh = (hoch - tief) / 5.0
    grad = 10.0 ** floor(log10(roh))
    for faktor in (1.0, 2.0, 2.5, 5.0, 10.0):
        schritt = faktor * grad
        if roh <= schritt:
            break
    return floor(tief / schritt) * schritt, ceil(hoch / schritt) * schritt, \
        schritt


def _achsen(tief: float, hoch: float, schritt: float) -> str:
    """Die waagerechten Linien mit Beschriftung, die Nulllinie kraeftiger."""
    teile = []
    wert = tief
    # Ueber die Anzahl laufen und nicht addieren: Wiederholtes Addieren
    # von 2,5 traefe die Null um ein Millionstel daneben, und dann faende
    # der Vergleich unten die Nulllinie nicht.
    anzahl = int(round((hoch - tief) / schritt))
    for i in range(anzahl + 1):
        wert = tief + i * schritt
        y = _UY - (wert - tief) / (hoch - tief) * (_UY - _OY)
        null = abs(wert) < schritt * 1e-6 and tief < -1e-9
        farbe = "#33495E" if null else "var(--gitter)"
        teile.append(f'<line x1="{_LX}" y1="{y:.1f}" x2="{_RX}" y2="{y:.1f}" '
                     f'stroke="{farbe}" stroke-width="1"/>')
        teile.append(f'<text x="{_LX - 10:.1f}" y="{y + 4:.1f}" '
                     f'text-anchor="end" class="ax">{escape(_zahl(wert))}'
                     '</text>')
    return "".join(teile)


def _namen_unten(punkte) -> str:
    """Die Namen unter der Achse -- bei vielen Punkten nur jeder n-te.

    Zwoelf Monatsnamen passen nebeneinander, vierzig Kalenderwochen nicht.
    Statt sie zu drehen (schraege Schrift liest sich schlecht) faellt
    jeder zweite oder dritte weg: Die Achse bleibt lesbar, und welcher
    Balken gemeint ist, sagt die Reihenfolge.
    """
    n = len(punkte)
    schritt = 1 if n <= 16 else (n + 11) // 12
    band = (_RX - _LX) / n
    teile = []
    for i, (name, _, _) in enumerate(punkte):
        if i % schritt or not name:
            continue
        mitte = _LX + band * (i + 0.5)
        teile.append(f'<text x="{mitte:.1f}" y="{_UY + 19:.1f}" '
                     'text-anchor="middle" class="ax">'
                     f'{escape(_kurz(name, 12))}</text>')
    return "".join(teile)


def _saeulen_svg(punkte) -> str:
    n = len(punkte)
    tief, hoch, schritt = _grenzen(punkte)

    def y(wert):
        return _UY - (wert - tief) / (hoch - tief) * (_UY - _OY)

    zwei = any(z is not None for _, _, z in punkte)
    band = (_RX - _LX) / n
    breite = band * (0.34 if zwei else 0.58)
    teile = [_achsen(tief, hoch, schritt)]
    nulllinie = y(0.0)
    for i, (_, wert, wert2) in enumerate(punkte):
        mitte = _LX + band * (i + 0.5)
        reihe = [(wert, HOERT)] + ([(wert2, SPRICHT)] if zwei else [])
        gesamt = breite * len(reihe)
        for k, (v, farbe) in enumerate(reihe):
            if v is None:
                continue
            x = mitte - gesamt / 2 + k * breite
            oben = min(y(v), nulllinie)
            # Mindesthoehe: Ein Wert von null waere sonst unsichtbar, und
            # "kein Balken" liest sich als "keine Daten".
            hoehe = max(1.6, abs(y(v) - nulllinie))
            teile.append(f'<rect x="{x:.1f}" y="{oben:.1f}" '
                         f'width="{breite * 0.88:.1f}" height="{hoehe:.1f}" '
                         f'rx="2" fill="{farbe}" opacity=".9"/>')
        # Der Wert ueber der Saeule -- nur, wenn Platz dafuer ist.
        if not zwei and n <= 12:
            teile.append(f'<text x="{mitte:.1f}" '
                         f'y="{min(y(wert), nulllinie) - 7:.1f}" '
                         'text-anchor="middle" class="wl">'
                         f'{escape(_zahl(wert))}</text>')
    teile.append(_namen_unten(punkte))
    return _huelle("".join(teile), _SVG_HOEHE)


def _linie_svg(punkte) -> str:
    n = len(punkte)
    tief, hoch, schritt = _grenzen(punkte)

    def y(wert):
        return _UY - (wert - tief) / (hoch - tief) * (_UY - _OY)

    # Bei einem einzigen Punkt gaebe es keine Strecke -- dann steht er in
    # der Mitte statt am linken Rand.
    def x(i):
        return _LX if n == 1 else _LX + (_RX - _LX) * i / (n - 1)

    teile = [_achsen(tief, hoch, schritt)]
    for spalte, farbe in ((1, HOERT), (2, SPRICHT)):
        stuecke = [(i, (w if spalte == 1 else z))
                   for i, (_, w, z) in enumerate(punkte)]
        stuecke = [(i, v) for i, v in stuecke if v is not None]
        if len(stuecke) < 2:
            continue
        weg = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in stuecke)
        # Die Flaeche darunter, sehr blass: Sie zeigt die Richtung auch
        # dann, wenn die Linie flach laeuft.
        teile.append(f'<polygon points="{x(stuecke[0][0]):.1f},'
                     f'{y(0.0):.1f} {weg} {x(stuecke[-1][0]):.1f},'
                     f'{y(0.0):.1f}" fill="{farbe}" opacity=".10"/>')
        teile.append(f'<polyline points="{weg}" fill="none" stroke="{farbe}" '
                     'stroke-width="2.2" stroke-linejoin="round" '
                     'stroke-linecap="round"/>')
        if n <= 24:
            for i, v in stuecke:
                teile.append(f'<circle cx="{x(i):.1f}" cy="{y(v):.1f}" '
                             f'r="3.2" fill="{farbe}"/>')
    teile.append(_namen_unten(punkte))
    return _huelle("".join(teile), _SVG_HOEHE)


def _balken_svg(punkte) -> str:
    """Waagerechte Balken -- fuer Kategorien mit richtigen Namen.

    Negative Werte bekommen die Warnfarbe statt einer Achse in der Mitte:
    Mit Namen links und einer Nullachse irgendwo dazwischen wird das
    Bild unlesbar, und in einer Ausgabenliste ist das Vorzeichen ohnehin
    eine Eigenschaft des Postens, keine Richtung.
    """
    zeile = 30.0
    hoehe = int(len(punkte) * zeile + 14)
    sx, ex = 214.0, 884.0        # Anfang und Ende der Balkenspur
    ende = ex - 104.0            # rechts bleibt Platz fuer den Wert
    gross = max([abs(w) for _, w, _ in punkte] + [1e-9])
    teile = []
    for i, (name, wert, _) in enumerate(punkte):
        y = 8.0 + i * zeile
        breite = max(2.0, abs(wert) / gross * (ende - sx))
        farbe = FRAGT if wert < 0 else HOERT
        teile.append(f'<rect x="{sx}" y="{y + 5:.1f}" width="{breite:.1f}" '
                     f'height="{zeile - 14:.1f}" rx="3" fill="{farbe}" '
                     'opacity=".85"/>')
        teile.append(f'<text x="0" y="{y + zeile / 2 + 1:.1f}" class="bn">'
                     f'{escape(_kurz(name, 26))}</text>')
        teile.append(f'<text x="{ex}" y="{y + zeile / 2 + 1:.1f}" '
                     f'text-anchor="end" class="ax">{escape(_zahl(wert))}'
                     '</text>')
    return _huelle("".join(teile), hoehe)


def _huelle(inneres: str, hoehe: int) -> str:
    # dominant-baseline waere kuerzer als das Nachrechnen der Grundlinie,
    # wird aber von aelteren Renderern verschieden ausgelegt. Also feste
    # Zahlen -- das Bild soll ueberall gleich aussehen.
    #
    # Ohne xmlns: Ein <svg> IM HTML landet beim Parser von selbst im
    # SVG-Namensraum, das Attribut waere ueberfluessig. Und es waere die
    # einzige Zeichenfolge "http://" im ganzen Dokument -- die Pruefung
    # "steht hier irgendwo eine externe Adresse?" haette dann jedes Mal
    # einen Treffer, den man wegerklaeren muss. Eine Pruefung, die man
    # wegerklaert, prueft bald nichts mehr.
    return (f'<svg viewBox="0 0 900 {hoehe}" role="img">'
            + inneres + '</svg>')


def _diagramm(d: dict) -> str:
    """Ein Diagramm als fertiger <figure>-Block.

    Faellt hier etwas aus, kommt ein lesbarer Satz auf die Seite und kein
    leerer Kasten: Ein Bericht mit einer Luecke, die sich erklaert, ist
    brauchbar; einer mit einem stummen Loch nicht.
    """
    if not isinstance(d, dict):
        return '<p class="hinweis">Ein Diagramm war unbrauchbar.</p>'
    titel = str(d.get("titel") or "").strip()
    einheit = str(d.get("einheit") or "").strip()
    form = str(d.get("form") or "saeulen").strip().lower()
    punkte = _punkte_lesen(d.get("punkte"))
    if not punkte:
        return ('<p class="hinweis">Diagramm '
                f'{escape(titel) or "ohne Titel"}: keine verwertbaren '
                'Zahlen.</p>')
    try:
        if form == "balken":
            svg = _balken_svg(punkte)
        elif form == "linie":
            svg = _linie_svg(punkte)
        else:
            svg = _saeulen_svg(punkte)
    except (ValueError, TypeError, ZeroDivisionError) as e:
        return ('<p class="hinweis">Diagramm '
                f'{escape(titel) or "ohne Titel"} liess sich nicht '
                f'zeichnen ({escape(type(e).__name__)}).</p>')

    kopf = ""
    if titel or einheit:
        kopf = ("<figcaption>"
                + escape(titel)
                + (f" · in {escape(einheit)}" if einheit else "")
                + "</figcaption>")
    legende = ""
    reihen = [str(r) for r in (d.get("reihen") or [])][:2]
    zwei = any(z is not None for _, _, z in punkte)
    if reihen and form in ("saeulen", "linie"):
        namen = list(reihen) if zwei else reihen[:1]
        legende = ('<div class="legende">' + "".join(
            f'<span><i style="background:{f}"></i>{escape(nm)}</span>'
            for nm, f in zip(namen, (HOERT, SPRICHT))) + "</div>")
    beschreibung = escape(_kurz(titel or "Diagramm", 60)
                          + f", {len(punkte)} Werte")
    svg = svg.replace('role="img"', f'role="img" aria-label="{beschreibung}"')
    return f'<figure class="diagramm">{kopf}{svg}{legende}</figure>'


_PLATZ = re.compile(r"\[\[\s*diagramm\s*:\s*(\d+)\s*\]\]", re.IGNORECASE)


def _diagramme_einsetzen(inhalt: str, diagramme: list) -> str:
    """Die Platzhalter im Rumpf durch die gezeichneten Diagramme ersetzen.

    Der Rumpf enthaelt [[diagramm:1]] an der Stelle, an der das erste
    Diagramm stehen soll. Warum ein Platzhalter und nicht einfach alle
    Diagramme oben: Ein Diagramm gehoert neben den Absatz, der es
    erklaert -- und die Reihenfolge kennt nur der, der den Text schreibt.
    Wo der Platzhalter fehlt oder eine Nummer nicht vergeben ist, wird
    trotzdem nichts stillschweigend verschluckt: Uebrige Diagramme kommen
    hinten dran, Platzhalter ohne Diagramm werden zu einem sichtbaren
    Satz.
    """
    fertig = {}
    for i, d in enumerate(list(diagramme or [])[:DIAGRAMME_MAX], start=1):
        fertig[i] = _diagramm(d)
    benutzt = set()

    def ersetzen(treffer):
        nummer = int(treffer.group(1))
        if nummer in fertig:
            benutzt.add(nummer)
            return fertig[nummer]
        return ('<p class="hinweis">Hier war Diagramm '
                f'{nummer} vorgesehen, es kam aber keins mit.</p>')

    rumpf = _PLATZ.sub(ersetzen, inhalt)
    rest = [fertig[i] for i in sorted(fertig) if i not in benutzt]
    if rest:
        rumpf += "\n" + "\n".join(rest)
    return rumpf


# --- Der Rumpf vom Modell -------------------------------------------------

_KOERPER = re.compile(r"<body[^>]*>(.*)</body>", re.IGNORECASE | re.DOTALL)
_TABELLE_AUF = re.compile(r"<table\b", re.IGNORECASE)


def _rumpf_richten(inhalt: str) -> str:
    """Was das Modell geschickt hat, in einen brauchbaren Rumpf verwandeln.

    Zwei Handgriffe, beide gemessen an dem, was Sprachmodelle bei "gib
    mir HTML" tatsaechlich tun:

    Manchmal kommt ein GANZES Dokument, mit <!DOCTYPE>, eigenem <head>
    und eigenem <style>. Eingesetzt ergaebe das ein Dokument im Dokument
    -- Chromium repariert das still, aber der fremde Stil ueberschreibt
    dabei den Rahmen. Also wird der Koerper herausgeschnitten.

    Und Tabellen werden in ihren Scrollkasten gewickelt, falls das nicht
    schon geschehen ist. Eine breite Tabelle ohne ihn schiebt die ganze
    Seite waagerecht, und dann scrollt der Nutzer den Text statt der
    Zahlen.
    """
    text = str(inhalt or "").strip()
    treffer = _KOERPER.search(text)
    if treffer:
        text = treffer.group(1).strip()
    elif text.lower().startswith("<!doctype"):
        # Ein Dokument ohne <body>-Tag: alles vor dem ersten sichtbaren
        # Element ist Vorspann, den wir nicht brauchen.
        text = re.sub(r"^<!doctype[^>]*>", "", text,
                      flags=re.IGNORECASE).strip()
    if 'class="tabelle"' not in text:
        text = _TABELLE_AUF.sub('<div class="tabelle"><table', text)
        text = re.sub(r"</table>", "</table></div>", text,
                      flags=re.IGNORECASE)
    return text


# --- Wohin die Datei kommt ------------------------------------------------
#
# Gleiches Muster wie _dateiname_saeubern/_anhang_ziel in
# werkzeuge/google.py, und aus demselben Grund -- nur ist die fremde Hand
# hier eine andere: Der Titel kommt vom MODELL. Er ist Text, keine
# Zusage, und er wird mit einem Ordnerpfad zusammengesetzt.

_UMLAUTE = {"ä": "ae", "ö": "oe", "ü": "ue",
            "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
            "ß": "ss"}


def _stamm_saeubern(titel: str) -> str:
    """Aus dem Titel einen harmlosen Namensstamm machen.

    "..\\..\\sarvis\\config.py" wuerde beim Zusammensetzen aus der Ablage
    herausfuehren, "C:datei" zeigt unter Windows auf das
    Arbeitsverzeichnis von Laufwerk C. Deshalb wird der Titel nicht
    repariert, sondern auf das reduziert, was ein Dateiname sein darf:
    letzter Abschnitt, harmlose Zeichen, begrenzte Laenge.

    Zwei Unterschiede zu google.py, beide bewusst:

    Eine WEISSE Liste statt einer schwarzen. Dort muss der Name des
    Absenders erhalten bleiben, damit der Nutzer seinen Anhang
    wiedererkennt; hier ist der Name reine Ablage, und was nicht
    ausdruecklich erlaubt ist, wird zum Bindestrich.

    Die ENDUNG kommt nicht aus dem Titel. Sie ist immer ".html", von uns
    angehaengt. Damit ist die ganze Frage nach gefaehrlichen Endungen
    (.py, .bat, .lnk) gar nicht erst zu stellen.
    """
    name = str(titel or "").strip()
    for zeichen, ersatz in _UMLAUTE.items():
        name = name.replace(zeichen, ersatz)
    # Beide Trennerarten -- Python nimmt unter Windows beides als Trenner.
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-")
    # Punkte und Leerzeichen am Ende schluckt Windows beim Anlegen still.
    # Geprueft haetten wir dann einen anderen Namen als den geschriebenen.
    name = name.strip(" .")
    if not name:
        return "bericht"
    if name.split(".")[0].upper() in GERAETENAMEN:
        name = "_" + name
    return name[:NAME_MAX].strip(" .-") or "bericht"


def _ziel(stamm: str, endung: str = ".html"):
    """Freien Pfad in der Ablage suchen; legt den Ordner an, wenn er fehlt.

    Gibt None zurueck, wenn der Pfad wider Erwarten aus dem Ordner
    herausfuehrt. Das ist der zweite Riegel hinter _stamm_saeubern --
    zwei Riegel, weil ein Fehler hier eine Datei an einen Ort schreibt,
    den sich das Modell ausgesucht hat.

    Der Zeitstempel im Namen ist die Antwort auf "aeltere Berichte sollen
    sich nicht ueberschreiben": Zwei Auswertungen desselben Titels von
    heute und von gestern stehen nebeneinander, und wer "den von
    gestern" sucht, sieht ihn am Namen. Dass der Ordner damit nicht
    zuwaechst, besorgt _aufraeumen.
    """
    config.ABLAGE.mkdir(parents=True, exist_ok=True)
    stempel = datetime.now().strftime("%Y%m%d-%H%M")
    ziel = config.ABLAGE / f"{stamm}-{stempel}{endung}"
    zaehler = 2
    # Zweimal derselbe Titel in derselben Minute ueberschreibt nicht --
    # es koennen zwei verschiedene Auswertungen sein.
    while ziel.exists():
        ziel = config.ABLAGE / f"{stamm}-{stempel}-{zaehler}{endung}"
        zaehler += 1
    if config.ABLAGE.resolve() != ziel.resolve().parent:
        return None
    return ziel


def _aufraeumen() -> int:
    """Alte Berichte wegraeumen; gibt zurueck, wie viele gingen.

    Nur Dateien, die dieses Modul selbst angelegt hat -- erkennbar am
    Zeitstempel im Namen. Ein Auftrag, der etwas anderes in die Ablage
    legt, findet es dort wieder.
    """
    try:
        dateien = [p for p in config.ABLAGE.iterdir()
                   if p.is_file() and _NAMENSMUSTER.search(p.name)]
    except OSError:
        return 0
    if len(dateien) <= BERICHTE_BEHALTEN:
        return 0
    try:
        dateien.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    except OSError:
        return 0
    weg = 0
    for alt in dateien[BERICHTE_BEHALTEN:]:
        try:
            alt.unlink()
            weg += 1
        except OSError:
            pass        # Datei offen oder schon weg -- kein Grund zu klagen
    return weg


# --- Die Seite ------------------------------------------------------------

def seite_bauen(titel: str, inhalt: str, untertitel: str = "",
                stand: str = "", diagramme=None, pfad: str = "") -> str:
    """Der fertige HTML-Text -- Rahmen von hier, Rumpf vom Aufrufer.

    Oeffentlich (ohne Unterstrich), damit sich eine Seite auch ohne
    laufende Anzeige bauen und pruefen laesst.
    """
    rumpf = _diagramme_einsetzen(_rumpf_richten(inhalt), diagramme or [])
    jetzt = datetime.now()
    stand = str(stand or "").strip() or f"Stand {jetzt:%d.%m.%Y, %H:%M} Uhr"

    # WER OBEN STEHT, entscheidet config.DOKUMENT_ABSENDER. Ohne Eintrag
    # bleibt es beim Ringzeichen -- so, wie es seit jeher war und wie es
    # fuer eine Auswertung richtig ist, die nur Sascha liest. Mit
    # Eintrag steht dort der Absender: Ein Angebot, das der Assistent
    # unterschreibt, ist kein Angebot.
    absender = str(getattr(config, "DOKUMENT_ABSENDER", "") or "").strip()
    if absender:
        marke = [f'<div class="marke"><span>{escape(absender)}</span></div>']
        zeilen = [str(z).strip()
                  for z in getattr(config, "DOKUMENT_ZEILEN", []) or []
                  if str(z).strip()]
        if zeilen:
            marke.append('<p class="absender">'
                         + "<br>".join(escape(z) for z in zeilen) + "</p>")
    else:
        marke = [f'<div class="marke">{_RING}<span>Sarvis</span></div>']

    kopf = marke + [f"<h1>{escape(str(titel))}</h1>"]
    if untertitel:
        kopf.append(f'<p class="unter">{escape(str(untertitel))}</p>')
    kopf.append(f'<p class="stand">{escape(stand)}</p>')

    eigener_fuss = str(getattr(config, "DOKUMENT_FUSS", "") or "").strip()
    if eigener_fuss:
        fuss = escape(eigener_fuss)
    elif absender:
        # Name gesetzt, aber keine Fusszeile: Dann lieber nur das Datum
        # als eine Herkunftsangabe, die dem Kopf widerspricht.
        fuss = f"{jetzt:%d.%m.%Y}"
    else:
        fuss = f"Erzeugt von Sarvis am {jetzt:%d.%m.%Y um %H:%M} Uhr"
    if pfad and not absender:
        # Der Dateipfad ist eine Notiz an den Betreiber und gehoert
        # nicht auf etwas, das nach draussen geht.
        fuss += f" · {escape(pfad)}"
    return (
        "<!DOCTYPE html>\n"
        '<html lang="de">\n<head>\n'
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, '
        'initial-scale=1">\n'
        '<meta http-equiv="Content-Security-Policy" content="'
        + SICHERHEIT + '">\n'
        f"<title>{escape(str(titel))}</title>\n"
        "<style>\n" + _STIL + "</style>\n"
        "</head>\n<body>\n"
        '<header class="kopf"><div class="spalte">'
        + "".join(kopf)
        + "</div></header>\n"
        '<main class="spalte">\n' + rumpf + "\n</main>\n"
        f'<footer class="spalte fuss">{fuss}</footer>\n'
        "</body>\n</html>\n"
    )


# --- Das Werkzeug ---------------------------------------------------------

def werkzeuge(protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    # Eigener Draht zur Anzeige, wie in programme.py und kacheln.py.
    # Die gemeinsame Anzeige, nicht eine eigene -- sonst sendet dieses
    # Modul im Netzbetrieb weiter per UDP an ein Fenster, das es
    # nicht gibt. Siehe anzeige.aktuelle().
    sicht = anzeige_modul.aktuelle()

    @tool(
        "seite_zeigen",
        "Baut eine ganze Seite und zeigt sie im eingebauten Browser — für "
        "AUSWERTUNGEN, die zu groß für eine Kachel sind: zwölf Monate "
        "Finanzen mit Kategorien, ein Vergleich über mehrere Zeiträume, "
        "eine Recherche mit Tabelle, ein Bericht zum Hinsetzen. "
        "Faustregel: bis zu einer Handvoll Zahlen kachel_zeigen, ab "
        "'schlüssle das auf' oder 'analysier mir das' diese Seite. "
        "Du schreibst den Inhalt selbst als HTML; Rahmen, Farben, "
        "Schrift und Diagramme kommen von Sarvis. Sag den Kern trotzdem "
        "laut — die Seite ersetzt deine Antwort nicht.\n"
        "AUFBAU: Nur der KÖRPER, kein <html> und kein <style>. Es gibt "
        "fertige Klassen, benutze sie statt eigener Formatierung:\n"
        "<section class=\"block\"><h2>Überschrift</h2>…</section>\n"
        "<div class=\"kennzahlen\"><div class=\"kennzahl\">"
        "<span class=\"wert\">20.480,66 €</span>"
        "<span class=\"etikett\">Kontostand</span>"
        "<span class=\"dazu\">+3,2 % zum Vormonat</span></div>…</div>\n"
        "<table> mit <th class=\"zahl\"> und <td class=\"zahl\"> für "
        "Zahlenspalten (rechtsbündig); <tfoot> für die Summenzeile. Um "
        "den Scrollkasten kümmert sich Sarvis.\n"
        "<p class=\"hinweis\">…</p> für Nebenbemerkungen, "
        "<span class=\"gut\">/<span class=\"schlecht\"> für Plus und "
        "Minus, <ul class=\"punkte\"> für Aufzählungen.\n"
        "DIAGRAMME nicht selbst zeichnen: Schick die Zahlen in "
        "'diagramme' und setze [[diagramm:1]], [[diagramm:2]] … an die "
        "Stelle im Text, wo sie stehen sollen. Sarvis rechnet Achsen und "
        "SVG.\n"
        "NICHTS AUS DEM NETZ: keine Bilder per URL, keine Schriften, "
        "keine Skripte, keine Bibliotheken — das wird geblockt und bleibt "
        "leer. Alles muss im HTML selbst stehen.",
        {
            "type": "object",
            "properties": {
                "titel": {
                    "type": "string",
                    "description": "Überschrift der Seite, drei bis sechs "
                                   "Wörter: 'Finanzen 2026 im Überblick'. "
                                   "Daraus wird auch der Dateiname.",
                },
                "inhalt": {
                    "type": "string",
                    "description": "Der Körper der Seite als HTML — "
                                   "Abschnitte, Kennzahlen, Tabellen, "
                                   "Text, Diagramm-Platzhalter. Ohne "
                                   "<html>, <head> und <style>.",
                },
                "untertitel": {
                    "type": "string",
                    "description": "Ein Satz unter der Überschrift: worum "
                                   "es geht und über welchen Zeitraum.",
                },
                "stand": {
                    "type": "string",
                    "description": "Woher die Daten sind: 'Stand 28.08.2026, "
                                   "Konto Girokonto'. Ohne Angabe steht "
                                   "Datum und Uhrzeit da.",
                },
                "diagramme": {
                    "type": "array",
                    "description": "Die Diagramme in der Reihenfolge ihrer "
                                   "Platzhalter. Höchstens zwölf.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "form": {
                                "type": "string",
                                "enum": ["saeulen", "balken", "linie"],
                                "description": "saeulen: senkrecht, für "
                                               "Zeitreihen wie zwölf Monate "
                                               "(Vorgabe). balken: "
                                               "waagerecht, für Kategorien "
                                               "mit langen Namen. linie: "
                                               "für den Verlauf.",
                            },
                            "titel": {"type": "string",
                                      "description": "Überschrift des "
                                                     "Diagramms."},
                            "einheit": {"type": "string",
                                        "description": "'€', 'Stunden', "
                                                       "'Stück'. Steht in "
                                                       "der Überschrift."},
                            "reihen": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Namen der ein oder zwei "
                                               "Reihen für die Legende, "
                                               "z. B. ['2026', '2025'].",
                            },
                            "punkte": {
                                "type": "array",
                                "description": "Die Werte, höchstens "
                                               "vierzig, in der richtigen "
                                               "Reihenfolge.",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {
                                            "type": "string",
                                            "description": "Beschriftung: "
                                                           "'Jan', "
                                                           "'Wohnen'."},
                                        "wert": {"type": "number",
                                                 "description": "Die rohe "
                                                                "Zahl, ohne "
                                                                "Einheit."},
                                        "wert2": {"type": "number",
                                                  "description": "Zweite "
                                                                 "Reihe zum "
                                                                 "Vergleich, "
                                                                 "z. B. das "
                                                                 "Vorjahr."},
                                    },
                                    "required": ["wert"],
                                },
                            },
                        },
                        "required": ["punkte"],
                    },
                },
            },
            "required": ["titel", "inhalt"],
        },
    )
    async def seite_zeigen(args):
        titel = str(args.get("titel") or "").strip()
        inhalt = str(args.get("inhalt") or "").strip()
        if not titel or not inhalt:
            return {"content": [{"type": "text", "text":
                    "Ohne Titel und Inhalt kann ich keine Seite bauen."}],
                    "is_error": True}
        if len(inhalt) > INHALT_MAX:
            return {"content": [{"type": "text", "text":
                    f"Der Inhalt ist {len(inhalt)} Zeichen lang und damit "
                    "zu groß für eine Seite. Kürze ihn oder teile auf."}],
                    "is_error": True}

        ziel = _ziel(_stamm_saeubern(titel))
        if ziel is None:
            return {"content": [{"type": "text", "text":
                    f"Der Titel {titel!r} führt aus der Ablage heraus. "
                    "Nichts geschrieben."}], "is_error": True}

        seite = seite_bauen(titel, inhalt,
                            untertitel=str(args.get("untertitel") or ""),
                            stand=str(args.get("stand") or ""),
                            diagramme=args.get("diagramme"),
                            pfad=str(ziel))
        try:
            # Die Platte durch einen Faden, wie ueberall sonst auch: Die
            # Schleife darf nie auf ein Dateisystem warten muessen.
            await asyncio.to_thread(ziel.write_text, seite, encoding="utf-8")
        except OSError as e:
            return {"content": [{"type": "text", "text":
                    f"Konnte die Seite nicht schreiben: {e}"}],
                    "is_error": True}
        await asyncio.to_thread(_aufraeumen)

        # ZWEI WEGE, UND DER TRAEGER ENTSCHEIDET.
        #
        # Am Dev-PC oeffnet das eingebaute Fenster eine file:///-Adresse
        # -- Datei und Fenster liegen auf demselben Rechner. Ueber Netz
        # ist genau das der Fehler, den es hier zu beheben gab: Die
        # Datei liegt im Container, der Browser des Nutzers steht
        # woanders, und die Weboberflaeche verwirft alles, was nicht
        # http ist, STILL (sarvis.js, seiteZeigen). Sarvis sagte "die
        # Seite steht im Fenster", und es stand nichts.
        #
        # Also wird die Seite ueber Netz nicht verschickt, sondern
        # ABRUFBAR gemacht: netz/blaetter.py legt sie unter eine
        # unerratbare Adresse, die Oberflaeche rahmt sie ein.
        offen = False
        if sicht.ueber_netz():
            from ..netz import blaetter
            try:
                kennung = await asyncio.to_thread(
                    blaetter.hinlegen, ziel, "html", titel)
            except (OSError, ValueError) as e:
                return {"content": [{"type": "text", "text":
                        f"Die Seite ist geschrieben, aber ich konnte sie "
                        f"nicht bereitstellen: {e}"}], "is_error": True}
            sicht.blatt(kennung, sorte="html", titel=titel,
                        adresse=blaetter.adresse(kennung))
            # Ueber Netz gibt es keine Rueckfrage ans Fenster, aber
            # etwas Besseres: Der Traeger weiss, wie viele Oberflaechen
            # verbunden sind. Null heisst, es sieht gerade niemand hin
            # -- und das gehoert gesagt statt behauptet.
            draht = sicht.draht()
            offen = bool(draht and draht.wie_viele())
        else:
            # as_uri() und nicht "file:///" + Pfad: Umlaute, Leerzeichen
            # und Backslashes werden dabei richtig kodiert. Ein
            # handgebautes file://-Ziel scheitert genau dann, wenn der
            # Titel deutsch ist.
            sicht.browser(ziel.as_uri())
            # Und jetzt nachsehen, ob wirklich etwas aufgegangen ist.
            # Der Draht zur Anzeige ist mit Absicht einseitig -- laeuft
            # sie nicht, verschwindet die Meldung im Nichts, und ohne
            # diese Frage behauptete Sarvis eine Seite, die niemand
            # sieht. web_stand ist die einzige Frage, die auch ohne
            # Browser eine sinnvolle Antwort hat (siehe hud.py).
            if sicht.an:
                antwort = await asyncio.to_thread(
                    sicht.fragen, "web_stand", STAND_ZEITLIMIT)
                offen = bool(antwort and antwort.get("offen"))

        if leuchten:
            # Derselbe Globus wie bei web_zeigen: Es ist dasselbe Fenster.
            leuchten("Websuche")
        vermerken(f"seite_zeigen: {titel} -> {ziel.name}")

        anzahl = len(list(args.get("diagramme") or []))
        womit = f" mit {anzahl} Diagramm{'en' if anzahl != 1 else ''}" \
            if anzahl else ""
        if offen and sicht.ueber_netz():
            satz = (f"»{titel}«{womit} liegt jetzt als Blatt vor dem "
                    "Nutzer. Sag den Kern trotzdem — die Seite ersetzt "
                    "deine Antwort nicht.")
        elif offen:
            satz = (f"»{titel}«{womit} steht jetzt im Browserfenster. Sag "
                    "den Kern trotzdem — die Seite ersetzt deine Antwort "
                    "nicht.")
        elif sicht.ueber_netz():
            # Ehrlich statt schoen, zweiter Fall: Die Seite ist da und
            # abrufbar, es ist nur niemand verbunden, der sie sehen
            # koennte.
            satz = (f"»{titel}«{womit} ist fertig, aber gerade ist keine "
                    "Oberfläche verbunden — sie wird da sein, sobald "
                    "wieder eine offen ist.")
        else:
            # Ehrlich statt schoen: Die Datei ist da, das Fenster nicht.
            # Der Pfad steht in der Antwort, damit Sarvis ihn nennen
            # kann, wenn der Nutzer nichts sieht.
            satz = (f"»{titel}«{womit} ist geschrieben, aber die Anzeige "
                    "antwortet nicht — es kann sein, dass kein Fenster "
                    f"aufgegangen ist. Die Seite liegt unter {ziel}.")
        return {"content": [{"type": "text", "text": satz}]}

    return [seite_zeigen]
