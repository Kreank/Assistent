"""Kacheln, die neben der Engine aufklappen und wieder gehen.

Eine Kachel ist ein eigenes Fenster, kein Teil der Engine. Das ist die
Entscheidung, an der der ganze Entwurf haengt: Waeren es Bereiche
INNERHALB des Overlays, muesste der Ring aus seinem paintEvent in ein
Layout umgebaut werden -- ein Tag Arbeit, nach dem alles genauso
aussieht wie vorher. Eigene Fenster brauchen kein gemeinsames Layout.
Der Ring wird nicht angefasst.

Die sechs Fensterflaggen sind aus hud.py uebernommen, und zwar
absichtlich woertlich. Sie loesen die drei Aergernisse, die aufploppende
Fenster sonst haben:

    Qt.Tool                        kein Eintrag in der Taskleiste
    Qt.WindowTransparentForInput   Klicks gehen hindurch
    WA_ShowWithoutActivating       klaut keinen Tastaturfokus

Die dritte ist die wichtigste. Ein Fenster, das beim Aufklappen den
Fokus nimmt, verschluckt den Buchstaben, den man gerade tippt -- und
zwar in irgendeiner fremden Anwendung. Das waere kein Schoenheitsfehler,
sondern ein Grund, die Anzeige abzuschalten.

Die zweite bringt etwas mit, das wie eine Einschraenkung aussieht und in
Wahrheit die richtige Entscheidung erzwingt: Eine Kachel laesst sich
nicht anklicken. Damit bleibt es dabei, dass hier angezeigt und ueber
Sarvis gehandelt wird -- kein Klick, der an der Rueckfrage vorbeilaeuft.

Gemalt wird wie ueberall sonst in einem festen Raster, gestreckt wird
nur der Maler (SKALA). Auf einem 5120er Bildschirm waere eine in
Bildschirmpunkten gerechnete Kachel eine Briefmarke.

NEUN FORMEN, EIN AUSSEHEN
=========================

Der Aufrufer waehlt die FORM, nicht das Aussehen. Farben, Schriften und
Abstaende stehen hier im Modul und kommen nirgends von aussen herein:
Eine Kachel gehoert optisch zum Ring, und ein Aufrufer, der gestalten
darf, zerlegt genau das. Was er waehlt, ist die Bauart des Inhalts:

    "liste"       Zeilen mit Wert rechts und Balken hinter der Schrift.
                  Die Vorgabe -- und die Form, mit der alles anfing.
    "blasen"      Gespraechsblasen fuer Telegram- und Mailverlaeufe.
                  Wer geschrieben hat, sagt die Seite; die Zeit steht
                  klein unter der Blase.
    "vergleich"   Zwei Wertspalten und eine Differenz. Die Differenz
                  rechnet die Kachel SELBST aus den Zahlen aus.
    "text"        Fliesstext fuer eine Zusammenfassung oder einen Auszug.
    "balken"      Senkrechtes Balkendiagramm mit Grundlinie. Zwoelf
                  Monate nebeneinander, Ausgaben nach unten.
    "torte"       Kreisdiagramm mit Legende. Die Prozente rechnet die
                  Kachel SELBST.
    "kategorien"  Liste mit Zwischenueberschriften und Gruppensummen.
                  Die Summen rechnet die Kachel SELBST.
    "fluss"       Sankey: Mengen, die sich verzweigen. Die DICKE eines
                  Bandes ist der Betrag. Knoten, Spalten, Summen und
                  Stapelreihenfolge rechnet die Kachel SELBST.
    "ablauf"      Kaesten und Pfeile: ein Weg durch Schritte und
                  Verzweigungen, kein Mengenfluss.

Warum Differenz, Prozente und Gruppensummen nicht uebernommen werden,
sondern hier entstehen: Eine gerechnete Zahl kann nicht halluziniert
sein, eine uebergebene schon. Der Weg von der Datenquelle bis hierher
fuehrt durch ein Sprachmodell, und ein Modell, das "minus 42 Euro"
schreiben DARF, schreibt es irgendwann auch dann, wenn es 24 waren.

Dieselbe Ueberlegung ist der Grund, warum ein zu kleines Tortenstueck
NICHT auf eine Mindestgroesse aufgeblasen wird: Ein Bild, das 0,5 Prozent
wie 5 Prozent aussehen laesst, behauptet etwas Falsches -- und zwar
lautlos.

ZWEI GRAPHEN IN EINER FLACHEN LISTE
===================================

"fluss" und "ablauf" sind Graphen, aber der Draht von aussen kennt nur
eine flache Liste von Punkten. Ein Graph muss sich also als Punktliste
ausdruecken lassen, und dafuer gibt es genau zwei Moeglichkeiten: Ein
Punkt ist eine KANTE, oder ein Punkt ist ein KNOTEN. Beide Formen
waehlen verschieden, und zwar aus demselben Grund -- was der Nutzer
ansieht und was leuchten soll:

    fluss    Punkt = Kante ({"von": ..., "nach": ..., "zahl": ...}).
             Ein Sankey IST eine Menge von Baendern; die Knoten sind
             das, was uebrig bleibt, wenn man die Baender zaehlt. Und
             leuchten soll das Band, also muss das Band der Punkt sein.
             Zwei Namen mit gleichem Rang brauchen zwei Feldnamen: "von"
             und "nach" statt "text" und "gruppe". Eine Richtung, die in
             einer Namenskonvention steckt, wird irgendwann vertauscht,
             und ein vertauschter Sankey sieht richtig aus.

    ablauf   Punkt = Knoten ({"text": ..., "von": ..., "wert": ...}).
             Ein Ablauf ist eine Kette von Kaesten; leuchten soll der
             Kasten. Und die KETTE ist der Regelfall: Steht "von" nicht
             da, ist der vorige Punkt gemeint -- eine gerade Kette
             braucht dann nichts als ihre Texte. Verzweigungen entstehen
             dadurch, dass zwei Punkte dasselbe "von" tragen.

Beide teilen sich _raenge(): die Einteilung in Spalten (fluss) bzw.
Zeilen (ablauf) ueber den laengsten Weg von vorn. Dort sitzt auch der
Kreisschutz -- ein Modell kann "A -> B -> A" schicken, und eine
Rangrechnung, die das nicht erwartet, laeuft endlos.

DER UMBRUCH WIRD EINMAL GERECHNET
=================================

Bei Blasen und Fliesstext haengt die Fensterhoehe am Umbruch: Wie hoch
die Kachel sein muss, weiss man erst, wenn man weiss, wie viele Zeilen
der Text ergibt. _masse_setzen() rechnet ihn deshalb dort aus, wo auch
die Hoehe entsteht, und legt das Ergebnis in self._plan ab. paintEvent
liest nur noch. Zwei Gruende, beide gemessen:

  Ein Umbruch im paintEvent liefe 30 mal je Sekunde fuer einen Text,
  der sich nie aendert.

  Und faende er dort mit anderen Massen statt, waere das Fenster zum
  Inhalt schief -- abgeschnittener Text unten oder ein leerer Rand.
  Genau deshalb setzen Messung und Malen dieselbe Schrift ueber
  _schrift_klein(), statt sie an zwei Stellen hinzuschreiben.
"""
import math

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QGuiApplication,
                           QPainter, QPainterPath, QPen, QPolygonF)
from PySide6.QtWidgets import QWidget

from . import config

# Das Malraster einer Kachel. Dieselbe Logik wie BREITE/HOEHE in hud.py:
# Hier drin wird gerechnet, erst der Maler wird gestreckt.
BREITE = 250
RAND = 14              # Innenabstand
ZEILE = 15             # Hoehe einer Datenzeile
SKALA = max(0.6, min(3.0, config.ANZEIGE_SKALA))

# Wie breit eine Kachel je Form ist. Nicht eine Breite fuer alles: Eine
# Gespraechsblase in 250 Rasterpunkten waere ein Treppengedicht, und vier
# Spalten passen dort gar nicht hinein. Die Zahlen sind an der Schrift
# gemessen (Segoe UI 7, das ist die Schrift aller Datenzeilen):
#
#   liste      250 -- unveraendert. Bezeichnung plus ein Betrag rechts,
#              mehr steht nie drin.
#   blasen     320 -- eine Blase darf 78 % davon nehmen, innen bleiben
#              rund 236 Punkte. Das sind ~45 Zeichen je Zeile. Unter 40
#              bricht jeder zweite Satz mitten im Nebensatz um.
#   vergleich  360 -- drei Zahlenspalten ("1.098,00" misst rund 46) plus
#              die Differenz, die Vorzeichen UND Dreieck traegt. Danach
#              bleiben noch ~107 Punkte fuer die Bezeichnung; darunter
#              waere von "Lebensmittel" nur "Lebens…" zu sehen.
#   text       300 -- rund 55 Zeichen je Zeile. Das ist die Spanne, in
#              der man Fliesstext noch fluessig liest; breiter wird das
#              Zeilenspringen muehsam, schmaler das Umbrechen.
#   balken     320 -- innen 292. Der Deckel steht bei 24 Balken (zwei
#              Jahre Monatswerte), zwoelf sind der Regelfall. 292/12 =
#              24,3 Punkte je Fach: Darunter passt "Jan" (gemessen 15 in
#              der Fussschrift), "Januar" (30) passt bei KEINER
#              vernuenftigen Breite -- bei 24 Balken sind es 12,2, und
#              dann traegt nur noch jeder zweite Balken seine Marke.
#              Schmaler als 300 verlieren auch die zwoelf ihre
#              Beschriftung, und ein Diagramm ohne Achsenbeschriftung
#              ist ein Muster.
#   torte      320 -- Ring 104 plus 14 Luft plus 174 Legende. Die Legende
#              traegt vier Dinge nebeneinander: Farbtupfer (7), Name (80
#              -- "Lebensmittel" misst 51, "Versicherung" 51), Betrag (42
#              -- "1.098,00" misst 33) und Prozent (32 -- "<0,1 %" misst
#              28). Ohne den Betrag waere die Kachel 42 schmaler, aber
#              dann stuende die Zahl, die der Aufrufer mitgeschickt hat,
#              nirgends.
#   kategorien 270 -- die 250 der Liste plus 11 fuer den Einzug der
#              Eintraege (sonst schrumpft die Bezeichnung von 138 auf
#              127) plus 9, damit die Zwischenueberschrift und ihre Summe
#              sich nicht beruehren: "VERSICHERUNGEN" misst gesperrt und
#              in Grossbuchstaben 86, die Summenspalte nimmt 78 -- das
#              sind 164 von 242 Punkten Innenbreite.
#
# Fuer "fluss" und "ablauf" steht hier die OBERGRENZE, nicht die Breite.
# Das ist der eine Unterschied zu den sieben oberen Formen, und er hat
# einen Grund: Deren Breite haengt an der Schrift und steht damit fest.
# Bei einem Graphen haengt sie an der Zahl der SPALTEN -- und die steht
# erst fest, wenn die Daten da sind. Eine Kachel mit drei Knoten in 739
# Punkten waere ein Bild mit zwei Handbreit Nichts darin. _fluss_rechnen
# und _ablauf_rechnen setzen self.breite deshalb selbst; sie kommen dabei
# nie ueber den Wert hier.
#
#   fluss      800 -- die Freigabe des Nutzers, und zwar ganz. Eine Spalte
#              besteht aus 9 Knotenbalken + 111 Namensspur + 72 Schwung,
#              zusammen 192; die letzte Spalte braucht keinen Schwung
#              mehr. Damit ist 14 + n * 120 + (n-1) * 72 + 14 die Breite:
#
#                  zwei Spalten   340        vier Spalten   724
#                  drei Spalten   532        fuenf Spalten  800
#
#              Bei fuenf Spalten reichen die 800 nicht mehr fuer 72
#              Schwung; er faellt dann auf sein Mindestmass 44, und die
#              Namensspur bekommt, was uebrig bleibt (110 statt 111 --
#              der Name verliert einen Punkt, nicht seinen Sinn). GENAU
#              DA IST DIE GRENZE: Fuenf Spalten sind die letzten, die
#              eine eigene Namensspur UND einen Bogen unterbringen.
#              Deshalb steht F_SPALTEN auf 5 und nicht mehr auf 6.
#
#              Der Finanzfall der Aufgabe (Einnahmen -> Bereich -> Posten)
#              hat drei Spalten und ist 532 breit. Das sind 150 mehr als
#              die erste Fassung brauchte -- und genau diese 150 sind der
#              Unterschied zwischen einer Schrift, die auf den Baendern
#              klebt, und einer, die daneben steht.
#   ablauf     708 -- vier Kaesten nebeneinander: 14 + 4 * 150 + 3 * 22
#              + 14 = 694, plus 14 fuer die Gasse am rechten Rand, durch
#              die ein Pfeil laeuft, der eine Zeile ueberspringt. 150 ist
#              die Kastenbreite, in der "Ergebnis geprueft" (misst 78)
#              und "Auftrag angelegt" (75) einzeilig stehen. Mehr als vier
#              Kaesten in einer Zeile werden nicht weggelassen, sondern
#              schmaler -- 708 ist auch dann die Grenze. Untergrenze ist
#              BREITE: Eine gerade Kette waere sonst 178 breit, und
#              schmaler als die schmalste vorhandene Form soll keine
#              Kachel sein.
FORM_BREITE = {"liste": BREITE, "blasen": 320, "vergleich": 360, "text": 300,
               "balken": 320, "torte": 320, "kategorien": 270,
               "fluss": 800, "ablauf": 708}
FORMEN = tuple(FORM_BREITE)

# Abstand zwischen der sichtbaren Engine und der Kachel, im Malraster.
ABSTAND = 18

# Farben. Eine Antwort gehoert zu dem, was er GERADE sagt -- sie traegt
# deshalb die Sprechfarbe aus hud.py. Ein Zustand gehoert zu etwas, das
# laeuft, und traegt dieselbe eigene Farbe wie die Hintergrund-Ecke:
# Das ist bewusst keiner der Gespraechszustaende.
FARBE_ANTWORT = QColor(255, 179, 71)
FARBE_ZUSTAND = QColor(126, 224, 168)

# Die beiden Richtungen der Differenz. Sie sind NICHT "gut" und
# "schlecht": Weniger ausgegeben ist gut, weniger eingenommen nicht --
# die Kachel weiss nicht, welcher Fall vorliegt, und behauptet es
# deshalb auch nicht. Gruen heisst hier mehr, Rot heisst weniger.
#
# Die Farbe ist ausserdem nie das einzige Zeichen: Vor jeder Differenz
# steht ihr Vorzeichen und ein Dreieck, das in die Richtung zeigt. Wer
# Rot und Gruen schlecht trennt -- rund jeder zwoelfte Mann --, liest
# das Vorzeichen und sieht das Dreieck.
FARBE_MEHR = QColor(126, 224, 168)
FARBE_WENIGER = QColor(255, 138, 128)

# Wie lange eine Antwort-Kachel steht, wenn nichts anderes gesagt wird.
# Lang genug, um sie nach dem gesprochenen Satz noch in Ruhe anzusehen;
# kurz genug, dass sie nicht zum Moebel wird.
ANTWORT_SEKUNDEN = 45.0

AUF = 0.22             # Sekunden zum Aufblenden
ZU = 0.55              # Sekunden zum Ausblenden

# --- Masse der neuen Formen -------------------------------------------

ZEILE_FLIESS = 14      # Untergrenze fuer eine umgebrochene Zeile
BLASE_ANTEIL = 0.78    # wie viel der Innenbreite eine Blase hoechstens nimmt
BLASE_RAND = 7         # Innenabstand in der Blase
BLASE_LUFT = 7         # Abstand zwischen zwei Blasen
BLASE_ZEILEN = 7       # mehr Zeilen bekommt keine einzelne Blase
BLASE_ECKE = 6         # Rundung der Blasenecken

# Wie hoch der Blasenstapel hoechstens wird. Die Engine ist 548
# Rasterpunkte hoch; mit Kopf, Fusszeile und Rand bleibt die Kachel
# damit unter ihr. Eine Kachel, die ueber den Bildschirm hinauswaechst,
# waere schlimmer als ein Verlauf, dem oben etwas fehlt -- und was oben
# fehlt, ist das Aelteste.
BLASEN_HOEHE = 340

# Dasselbe fuer Fliesstext, nur in Zeilen gerechnet: 18 * 14 = 252
# Rasterpunkte.
TEXT_ZEILEN = 18

# Spaltenbreiten im Vergleich -- siehe FORM_BREITE fuer die Herleitung.
V_WERT = 68            # je Wertspalte
V_DIFF = 74            # Differenz (Vorzeichen und Dreieck brauchen Platz)
V_LUFT = 5             # zwischen den Spalten
V_ZEILE = 16           # etwas hoeher als ZEILE: hier stehen vier Angaben

# --- Balken ------------------------------------------------------------

B_HOCH = 96            # Hoehe der Zeichenflaeche im Malraster
B_LUFT = 5             # Abstand zwischen zwei Balken, hoechstens
B_LUFT_MIN = 2         # ... und mindestens: ohne Fuge wird es eine Flaeche
B_SCHMAL = 3           # duennster Balken, der noch als Balken gilt
B_FUSS = 3             # Abstand von der Zeichenflaeche zur Beschriftung
B_KUERZEL = 3          # auf so viele Zeichen wird eine Marke gekuerzt
# In diesen Schritten wird ausgeduennt, wenn selbst das Kuerzel nicht
# mehr unter einen Balken passt. Keine krummen Zahlen: Bei zwoelf
# Monatswerten trifft 2 die geraden, 3 das Quartal, 6 das Halbjahr --
# jeder dieser Schritte ergibt eine Reihe, die man noch zuordnen kann.
B_SCHRITTE = (1, 2, 3, 4, 6)

# --- Torte -------------------------------------------------------------

T_RING = 104           # Durchmesser des Kreises
T_ZEILE = 14           # Hoehe einer Legendenzeile
T_LUFT = 14            # zwischen Kreis und Legende
T_TUPF = 7             # Kantenlaenge des Farbtupfers
T_NAME = 80            # Namensspalte der Legende
T_WERT = 42            # Betragsspalte
T_PROZ = 32            # Prozentspalte
T_AUS = 4              # so weit steht das hervorgehobene Stueck heraus
# Der gemalte Kreis ist um genau diesen Weg kleiner als sein Feld: So
# bleibt das herausgezogene Stueck innerhalb von T_RING, und die Legende
# rutscht nicht, sobald irgendwo etwas leuchtet.
T_RADIUS = (T_RING - 2 * T_AUS) / 2.0
T_BESCHRIFTET = 0.62   # auf diesem Anteil des Radius steht die Prozentzahl
# Kleiner als das bekommt ein Stueck seine Zahl nicht mehr hinein. 30
# Grad sind 8,3 Prozent -- darunter wird die Sehne so kurz, dass die
# Zahl ueber die Kante haengt.
T_MINDEST_GRAD = 30.0

# --- Kategorien --------------------------------------------------------

K_KOPF = 15            # Hoehe einer Zwischenueberschrift
K_LUFT = 6             # Abstand VOR einer neuen Gruppe (nicht vor der ersten)
K_EINZUG = 11          # so weit stehen die Eintraege unter der Ueberschrift ein
K_WERT = 78            # Wertspalte, wie in der Liste
# Wie hoch die Gruppenliste hoechstens wird -- dieselbe Ueberlegung wie
# BLASEN_HOEHE: Der Deckel steht bei 30 Punkten, und 30 Punkte in sechs
# Gruppen waeren 576 Rasterpunkte. Die Engine ist 548 hoch.
K_HOEHE = 360

# --- Fluss (Sankey) -----------------------------------------------------

F_KNOTEN = 9           # Breite eines Knotenbalkens
# Die Namensspur: der Streifen RECHTS neben jedem Knotenbalken, in dem
# seine Beschriftung steht. Sie ist der Kern dieser Form, und die erste
# Fassung hatte sie nicht -- dort stand die Schrift mitten in den
# Baendern. Warum das nicht zu retten war und warum eine eigene Spur
# ueberhaupt moeglich ist, steht bei _fluss_rechnen unter GERADE STRECKE.
#
#   111 = 5 Innenabstand + 56 Name + 4 Luft + 42 Betrag + 4 Innenabstand.
#   56 fuer den Namen, weil "Lebensmittel" 51 misst und "Versicherung"
#   ebenfalls 51; 42 fuer den Betrag, weil "1.098,00" 33 misst.
F_NAME = 111
F_WERT = 42            # davon die Betragsspalte
F_NAME_RAND = 5        # Innenabstand der Spur, links am Balken
# Wie weit ein Band schwingen darf -- der Teil zwischen zwei Spuren, in
# dem es seine Hoehe wechselt. Hoechstens 72: mehr macht das Bild breiter,
# ohne dass die Kurve besser wird. Mindestens 44: darunter ist der
# Schwung kein Bogen mehr, sondern ein Knick.
F_KURVE = 72
F_KURVE_MIN = 44
# Tiefer wird nicht aufgefaechert. Fuenf und nicht sechs, seit die
# Beschriftung ihre eigene Spur hat: Bei sechs Spalten bliebe fuer den
# Namen eine Spur von 83 Punkten und damit 28 fuer den Namen selbst --
# aus "Lebensmittel" wuerde "Leb…". Die Wahl steht zwischen einer sechsten
# Stufe ohne lesbare Namen und fuenf Stufen mit; ein Geldfluss hat
# Einnahmen, Bereich, Posten, Detail -- das sind vier. Was tiefer liegt,
# faellt weg und wird vermerkt.
F_SPALTEN = 5
F_HOCH = 200           # Grundhoehe der Zeichenflaeche
# So viel der Zeichenflaeche bleibt mindestens fuer die Balken selbst.
# Der senkrechte Abstand zweier Knoten ist eine ganze Textzeile hoch --
# das ist es, was die Beschriftung duenner Baender rettet: Zwei Knoten
# liegen dann immer so weit auseinander, dass ihre Namen sich nicht
# ueberlappen koennen, egal wie duenn sie sind. Bei vielen Knoten in
# einer Spalte fressen diese Abstaende die Flaeche auf, deshalb waechst
# sie mit -- unter F_BALKEN_MIN sinkt der Platz fuer die Balken nie.
F_BALKEN_MIN = 84
# Duenner als das wird ein Knotenbalken nicht gemalt. Das ist KEIN
# Aufblasen im Sinne der Torte: Aufgeblasen wird nichts, was verglichen
# wird -- verglichen werden die Baender, und die bleiben genau so duenn,
# wie sie sind. Der Balken ist die Marke, an der die Baender haengen,
# und eine Marke von null Punkten ist neben ihrer Beschriftung ein
# Fehler und keine Auskunft.
F_STRICH = 0.8

# --- Ablauf --------------------------------------------------------------

A_KASTEN = 150         # Breite eines Kastens, wenn Platz dafuer ist
A_LUFT = 22            # zwischen zwei Kaesten derselben Zeile, hoechstens
A_PFEIL = 24           # senkrechter Abstand zweier Zeilen: der Pfeil und
                       # seine Beschriftung ("ja"/"nein") wohnen darin
A_RAND = 5             # Innenabstand im Kasten
A_ZEILEN = 2           # mehr Textzeilen bekommt kein Kasten
A_ECKE = 5             # Rundung der Kastenecken
A_GASSE = 14           # Spur am rechten Rand fuer Pfeile ueber eine Zeile
A_KOPF = 3.2           # halbe Breite der Pfeilspitze
# Wie hoch der Ablauf hoechstens wird -- dieselbe Ueberlegung wie
# BLASEN_HOEHE, nur andersherum gerechnet: Der Deckel steht bei zehn
# Schritten, und zehn einzeilige Kaesten sind 10 * 25 + 9 * 24 = 466.
# Mit Kopf, Fusszeile und Rand bleibt die Kachel damit unter der 548
# Punkte hohen Engine. Erst zweizeilige Kaesten sprengen das, und dann
# wird UNTEN gekappt -- beim Ablauf ist das der schlechtere Schnitt (das
# Ende ist das Ziel), aber der einzige, der nicht luegt: Oben zu kappen
# hiesse, einen Weg ohne Anfang zu zeigen.
A_HOEHE = 470
# Die aeusserste Breite. Sie steht hier und nicht nur in FORM_BREITE,
# weil die Kastenbreite daraus gerechnet wird.
A_MAX = 708

# Die Marke, mit der ueberall im Projekt gekuerzt wird. Ein stummer
# Schnitt sieht aus wie ein vollstaendiger Text.
MARKE = "[… gekürzt]"
MARKE_ALT = "[… ältere ausgeblendet]"
MARKE_OHNE = "[… ohne negative Werte]"
MARKE_KANTEN = "[… unvollständige Bänder weggelassen]"
MARKE_KREIS = "[… Kreis aufgetrennt]"
MARKE_TIEF = "[… tiefere Stufen weggelassen]"
# Nicht die Kachel hat gekuerzt, sondern der Draht: anzeige.PUNKTE_DECKEL
# schneidet ab, bevor die Kachel etwas sieht. Sie kann also nicht sagen,
# WAS fehlt -- nur, DASS etwas fehlt. Das ist immer noch besser als eine
# Knotensumme, die wie das Ganze aussieht und es nicht ist.
MARKE_DECKEL = "[… zu viele Punkte, gekürzt]"


class Kachel(QWidget):
    """Ein Kaertchen neben der Engine. Lebt, solange es etwas zu zeigen gibt."""

    def __init__(self, sorte: str = "antwort"):
        super().__init__()
        # Woertlich dieselben Flaggen wie die Engine -- siehe Modulkopf.
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        self.sorte = sorte
        self.form = "liste"
        self.kopf = ""
        self.gross = ""          # die eine grosse Zahl, wenn es eine gibt
        # Datenpunkte, NICHT fertige Textzeilen. Jeder Punkt ist
        # {"text": ..., "wert": ..., "zahl": ...} -- "wert" ist die
        # vorgelesene Schreibweise, "zahl" der rohe Wert.
        #
        # Der Unterschied ist keine Formsache: Aus "zahl" wird die Laenge
        # des Balkens, und spaeter erkennt die Kachel daran, welchen Punkt
        # Sarvis gerade nennt. Wer hier fertige Strings schickt, kann
        # weder zeichnen noch hervorheben.
        #
        # Sechs Felder kommen fuer die anderen Formen dazu und stoeren die
        # alten nicht, weil sie leer bleiben duerfen: "von_mir" (Blasen),
        # "wert2" und "zahl2" (Vergleich), "gruppe" (Kategorien), "von"
        # und "nach" (Fluss und Ablauf).
        self.punkte: list = []
        self.spalten: tuple = ()  # Ueberschriften der beiden Wertspalten
        self.stand = ""          # "Stand 10:42" -- wann die Daten geholt wurden
        self.hervor = -1         # welcher Punkt gerade leuchtet (-1 = keiner)
        self.breite = BREITE     # haengt an der Form, siehe FORM_BREITE
        self._hoehe = 0          # wird in _masse_setzen aus dem Inhalt gerechnet
        # Der einmal gerechnete Umbruch. Was drinsteht, haengt an der
        # Form; wer ihn liest, muss ihn nicht neu ermitteln. Siehe
        # Modulkopf.
        self._plan: list = []
        # Dasselbe fuer Masse, die nicht je Zeile gelten, sondern fuer die
        # ganze Form: die Lage der Grundlinie, die Fachbreite, die Summe
        # einer Torte. Sie gehoeren nicht in _plan, weil dort gezaehlt und
        # durchgelaufen wird -- ein Eintrag, der keine Zeile ist, waere in
        # jeder dieser Schleifen ein Sonderfall.
        self._bau: dict = {}
        self._gekappt = False    # wurde oben etwas weggelassen?
        self._weggelassen = 0    # ... und wie viele schon am Draht?
        self._zh = ZEILE_FLIESS  # gemessene Zeilenhoehe der Fliessschrift
        self._zf = 12            # gemessene Hoehe der kleinen Fusszeile

        self._rest = 0.0         # Sekunden, die sie noch stehen bleibt
        self._alter = 0.0        # Sekunden seit dem Aufklappen
        self._tick = 0.0
        self._anker = None       # zuletzt bekannte Lage der Engine
        self._seite = "links" if sorte == "zustand" else "rechts"
        self._versatz = 0        # Stapelabstand, wenn mehrere je Seite

        self._uhr = QTimer(self)
        self._uhr.timeout.connect(self._schlag)

    # --- zeigen und verschwinden -----------------------------------------

    @staticmethod
    def _punkt(roh) -> dict:
        """Einen Eintrag auf die gemeinsame Form bringen.

        Erlaubt sind ein fertiges dict, ein Paar (Text, Wert) oder blosser
        Text. Das erspart jedem Aufrufer die Huelle, ohne dass die
        Zeichenlogik drei Faelle kennen muss.

        Es gibt EINE Punktform fuer alle neun Kachelformen, nicht neun.
        Sonst muesste jede Stelle, die einen Punkt anfasst, vorher nach
        der Form fragen -- und ein Punkt aus der falschen Form waere ein
        Absturz statt eines leeren Feldes.
        """
        def zahl_von(wert):
            # bool ist in Python ein int. Ein True als Balkenlaenge waere
            # eine 1.0, und niemand haette es je bemerkt.
            if isinstance(wert, bool) or not isinstance(wert, (int, float)):
                return None
            return float(wert)

        if isinstance(roh, dict):
            return {"text": str(roh.get("text", "")),
                    "wert": str(roh.get("wert", "")),
                    "wert2": str(roh.get("wert2", "")),
                    "zahl": zahl_von(roh.get("zahl")),
                    "zahl2": zahl_von(roh.get("zahl2")),
                    "von_mir": bool(roh.get("von_mir")),
                    "gruppe": str(roh.get("gruppe", "")),
                    "von": str(roh.get("von", "")),
                    "nach": str(roh.get("nach", ""))}
        if isinstance(roh, (tuple, list)):
            text = str(roh[0]) if roh else ""
            wert = str(roh[1]) if len(roh) > 1 else ""
            return {"text": text, "wert": wert, "wert2": "",
                    "zahl": None, "zahl2": None, "von_mir": False,
                    "gruppe": "", "von": "", "nach": ""}
        return {"text": str(roh), "wert": "", "wert2": "",
                "zahl": None, "zahl2": None, "von_mir": False, "gruppe": "",
                "von": "", "nach": ""}

    def anzeigen(self, kopf: str, punkte: list, gross: str = "",
                 stand: str = "", sekunden: float = 0.0,
                 form: str = "liste", spalten=(),
                 weggelassen: int = 0) -> None:
        """Inhalt setzen und aufklappen.

        sekunden=0 heisst: bleibt stehen, bis jemand sie wegnimmt. Das ist
        die Vorgabe fuer Zustands-Kacheln -- ein laufender Auftrag hoert
        ja nicht nach 45 Sekunden auf zu laufen.

        form ist die Bauart des Inhalts, nicht sein Aussehen -- siehe
        Modulkopf. Etwas Unbekanntes faellt auf "liste" zurueck: Eine
        Kachel, die wegen eines Tippfehlers gar nicht aufgeht, ist
        schlechter als eine, die schlicht aussieht.

        spalten benennt im Vergleich die beiden Wertspalten
        ("August", "Juli"). Ohne Angabe entfaellt die Kopfzeile der
        Spalten; die Differenz steht trotzdem da. Das ist Inhalt, keine
        Gestaltung -- welcher Monat rechts steht, weiss nur der Aufrufer.

        Welche Felder eines Punktes eine Form liest:

            liste       text, wert, zahl
            blasen      text, wert (Zeit), von_mir
            vergleich   text, wert, wert2, zahl, zahl2
            text        text
            balken      text (kurz halten!), wert, zahl -- zahl darf
                        negativ sein
            torte       text, wert, zahl -- nur zahl > 0 bekommt ein
                        Stueck
            kategorien  text, wert, zahl, gruppe
            fluss       von, nach, zahl -- ein Punkt ist eine KANTE.
                        "zahl" muss groesser als null sein, sonst gibt
                        es kein Band. "text" und "wert" liest der Fluss
                        nicht: Die Knotennamen stehen in von/nach, und
                        die Betraege an den Knoten sind SUMMEN, die die
                        Kachel selbst bildet.
            ablauf      text, von, wert, nach -- ein Punkt ist ein KASTEN.
                        "von" nennt den Kasten davor; fehlt es, ist der
                        vorige Punkt gemeint (das ist die Kette). "wert"
                        beschriftet den Pfeil, der in diesen Kasten
                        fuehrt ("ja"/"nein"). "nach" nennt einen
                        ZUSAETZLICHEN Kasten, in den dieser Schritt
                        ausserdem muendet -- damit laufen Zweige wieder
                        zusammen.

        Was eine Form nicht liest, darf fehlen. Ein Punkt ohne "zahl"
        bekommt keinen Balken, kein Tortenstueck und geht in keine
        Gruppensumme ein -- er verschwindet aber nicht, sondern steht
        ohne diese Angaben da.
        """
        self.form = form if form in FORMEN else "liste"
        self.kopf = str(kopf or "")
        # VOR _masse_setzen: Die Fahne entscheidet dort, ob die Marke
        # gesetzt wird, und wird danach nicht mehr angefasst.
        try:
            self._weggelassen = max(0, int(weggelassen or 0))
        except (TypeError, ValueError):
            self._weggelassen = 0
        self.punkte = [self._punkt(x) for x in (punkte or [])]
        self.spalten = tuple(str(s) for s in (spalten or ()))[:2]
        self.gross = str(gross or "")
        self.stand = str(stand or "")
        self.hervor = -1
        if sekunden <= 0 and self.sorte == "antwort":
            sekunden = ANTWORT_SEKUNDEN
        self._rest = float(sekunden)
        self._alter = 0.0
        self._masse_setzen()
        if self._anker is not None:
            self._platzieren(self._anker)
        self.show()
        if not self._uhr.isActive():
            self._uhr.start(33)
        self.update()

    def wegnehmen(self) -> None:
        """Ausblenden lassen. Nicht sofort verstecken -- das ruckt.

        Der Fall, an dem die erste Fassung scheiterte: Eine Zustands-Kachel
        hat _rest == 0, was "bleibt stehen" heisst. Die Bedingung lautete
        `_rest > ZU`, und die ist bei 0 falsch -- ausgerechnet die Kachel,
        die nur ueber diesen Weg verschwinden KANN, blieb damit fuer immer
        stehen. Gemessen: nach fuenf Minuten und einem wegnehmen() stand
        sie unveraendert da.

        Ein bereits kuerzerer Rest wird nicht verlaengert.
        """
        if not self.isVisible():
            self._uhr.stop()
            return
        if self._rest <= 0 or self._rest > ZU:
            self._rest = ZU

    def leuchten(self, zeile: int) -> None:
        """Eine Zeile hervorheben -- spaeter das, was er gerade sagt.

        Gezaehlt wird ueber die PUNKTE, nicht ueber das, was zu sehen ist.
        Bei Blasen kann oben etwas weggelassen worden sein; wuerde hier
        das Sichtbare gezaehlt, leuchtete die falsche Nachricht.
        """
        self.hervor = int(zeile)
        self.update()

    # --- Schriften --------------------------------------------------------
    #
    # Messung und Malen holen sich ihre Schrift HIER, nicht jeder fuer
    # sich. Stuenden die zwei Zeilen an zwei Stellen, waere der Tag
    # absehbar, an dem eine davon auf 8 Punkt geht und das Fenster nicht
    # mehr zum Inhalt passt.

    @staticmethod
    def _schrift_klein() -> QFont:
        """Die Schrift aller Datenzeilen, Blasen und Fliesstexte."""
        return QFont("Segoe UI", 7)

    @staticmethod
    def _schrift_fuss() -> QFont:
        """Kleiner: Zeitstempel unter einer Blase, Stand, Spaltenkoepfe."""
        f = QFont("Segoe UI", 6)
        f.setLetterSpacing(QFont.PercentageSpacing, 130)
        return f

    # --- Umbruch ----------------------------------------------------------

    @staticmethod
    def _umbrechen(mass: QFontMetrics, text: str, breite: float) -> list:
        """Wortweiser Umbruch auf eine feste Breite.

        Qt kann das mit Qt.TextWordWrap selbst -- aber erst beim Malen,
        und dort ist es zu spaet: Die Fensterhoehe muss vorher feststehen.
        Deshalb hier, mit derselben Schriftmessung, die auch malt.

        Ein Wort, das allein nicht in eine Zeile passt, wird hart
        getrennt. Das ist haesslich und trotzdem richtig: Eine URL oder
        ein Dateipfad ohne Leerzeichen liefe sonst aus der Blase heraus
        und waere zur Haelfte weg. Lieber umgebrochen als abgeschnitten.
        """
        zeilen = []
        for absatz in str(text).split("\n"):
            worte = absatz.split()
            if not worte:
                zeilen.append("")
                continue
            zeile = ""
            for wort in worte:
                probe = wort if not zeile else zeile + " " + wort
                if mass.horizontalAdvance(probe) <= breite:
                    zeile = probe
                    continue
                if zeile:
                    zeilen.append(zeile)
                    zeile = ""
                while mass.horizontalAdvance(wort) > breite:
                    # Das laengste Stueck suchen, das noch passt. Mindestens
                    # ein Zeichen wird immer genommen -- sonst laeuft die
                    # Schleife ewig, wenn schon ein Buchstabe zu breit ist.
                    n = 1
                    while (n < len(wort)
                           and mass.horizontalAdvance(wort[:n + 1]) <= breite):
                        n += 1
                    zeilen.append(wort[:n])
                    wort = wort[n:]
                zeile = wort
            if zeile:
                zeilen.append(zeile)
        return zeilen

    # --- Groesse und Ort --------------------------------------------------

    def _masse_setzen(self) -> None:
        """Hoehe aus dem Inhalt, Breite aus der Form.

        setFixedSize und nicht resize, aus demselben Grund wie in hud.py:
        Beim Ueberqueren einer DPI-Grenze rechnet Qt die Fenstergroesse
        sonst jedes Mal neu um, und das schaukelt sich auf.

        Hier entsteht auch der Umbruch. Er MUSS hier entstehen: Bei
        Blasen und Fliesstext ist die Zeilenzahl die Hoehe.
        """
        self.breite = FORM_BREITE.get(self.form, BREITE)
        self._plan = []
        self._bau = {}
        # Nicht False, sondern: Hat der Draht schon gekuerzt? Dann ist
        # oben etwas weggelassen worden, bevor diese Kachel den ersten
        # Punkt gesehen hat -- und die Formen, die selbst kappen,
        # setzen ihre Marke ohnehin ueber dieselbe Fahne.
        self._gekappt = self._weggelassen > 0
        # Einmal messen, beide Werte merken -- die Zeilenhoehen der
        # gerechneten Formen haengen an der wirklichen Schrift, nicht an
        # einer geratenen Zahl.
        self._zh = max(ZEILE_FLIESS, QFontMetrics(self._schrift_klein()).height())
        self._zf = QFontMetrics(self._schrift_fuss()).height()

        # Kopfzeile. 18, nicht 16: So viel ruecken _kopfzeile und alles
        # darunter wirklich vor. Hier standen 16, und damit war jede
        # Kachel zwei Rasterpunkte zu niedrig -- unten blieb ein Rand von
        # 12 statt 14 uebrig, waehrend oben 14 standen. Bei Fliesstext
        # faellt so etwas auf, bei fuenf Listenzeilen nicht.
        hoehe = RAND + 18
        if self.gross:
            hoehe += 30
        if self.form == "blasen":
            hoehe += self._blasen_rechnen()
        elif self.form == "vergleich":
            hoehe += self._vergleich_rechnen()
        elif self.form == "text":
            hoehe += self._text_rechnen()
        elif self.form == "balken":
            hoehe += self._balken_rechnen()
        elif self.form == "torte":
            hoehe += self._torte_rechnen()
        elif self.form == "kategorien":
            hoehe += self._kategorien_rechnen()
        elif self.form == "fluss":
            hoehe += self._fluss_rechnen()
        elif self.form == "ablauf":
            hoehe += self._ablauf_rechnen()
        else:
            hoehe += len(self.punkte) * ZEILE
        if self.stand:
            hoehe += 16
        hoehe += RAND
        self._hoehe = hoehe
        self.setFixedSize(round(self.breite * SKALA), round(hoehe * SKALA))

    def _blasen_rechnen(self) -> float:
        """Jede Blase umbrechen, vermessen und den Stapel deckeln.

        Gekappt wird von OBEN, also am Aelteren: Ein Verlauf wird von
        unten gelesen, die letzte Nachricht ist die, um die es geht.
        Dass etwas fehlt, sagt eine Marke -- stillschweigend
        wegzulassen waere dasselbe wie zu behaupten, mehr sei nicht da.
        """
        mass = QFontMetrics(self._schrift_klein())
        innen = round((self.breite - 2 * RAND) * BLASE_ANTEIL) - 2 * BLASE_RAND
        blasen = []
        for i, punkt in enumerate(self.punkte):
            zeilen = self._umbrechen(mass, punkt["text"], innen) or [""]
            if len(zeilen) > BLASE_ZEILEN:
                zeilen = zeilen[:BLASE_ZEILEN - 1] + [MARKE]
            # Die Blase ist so breit wie ihr laengste Zeile, nicht so
            # breit wie erlaubt: Ein "ja" in einem 250 Punkte breiten
            # Kasten sieht aus wie ein Fehler.
            breit = min(innen, max(mass.horizontalAdvance(z) for z in zeilen))
            hoch = len(zeilen) * self._zh + 2 * BLASE_RAND
            blasen.append({
                "punkt": i,
                "zeilen": zeilen,
                "wert": punkt["wert"],
                "von_mir": punkt["von_mir"],
                "breite": breit + 2 * BLASE_RAND,
                "hoehe": hoch,
                # Die Zeit steht UNTER der Blase, nicht darin: In der
                # Blase konkurriert sie mit dem Text um die Breite, und
                # bei kurzen Nachrichten gewinnt sie.
                "fuss": self._zf if punkt["wert"] else 0,
            })

        # Von hinten auffuellen, bis der Deckel erreicht ist.
        platz = BLASEN_HOEHE
        behalten = []
        for blase in reversed(blasen):
            braucht = blase["hoehe"] + blase["fuss"]
            if behalten:
                braucht += BLASE_LUFT
            if braucht > platz and behalten:
                self._gekappt = True
                break
            platz -= braucht
            behalten.append(blase)
        behalten.reverse()

        self._plan = behalten
        hoehe = sum(b["hoehe"] + b["fuss"] for b in behalten)
        hoehe += BLASE_LUFT * max(0, len(behalten) - 1)
        if self._gekappt:
            hoehe += self._zh
        return hoehe

    def _text_rechnen(self) -> float:
        """Fliesstext umbrechen. Jeder Punkt ist ein Absatz."""
        mass = QFontMetrics(self._schrift_klein())
        innen = self.breite - 2 * RAND
        zeilen = []
        for punkt in self.punkte:
            if zeilen:
                zeilen.append("")            # Absatzabstand
            zeilen.extend(self._umbrechen(mass, punkt["text"], innen))
        if len(zeilen) > TEXT_ZEILEN:
            # Die Marke ersetzt die letzte Zeile, sie kommt nicht dazu:
            # sonst waere die gekuerzte Fassung hoeher als der Deckel.
            zeilen = zeilen[:TEXT_ZEILEN - 1] + [MARKE]
            self._gekappt = True
        self._plan = zeilen
        return len(zeilen) * self._zh

    def _vergleich_rechnen(self) -> float:
        """Die Differenzen ausrechnen. Eine Zeile bleibt eine Zeile.

        Gerechnet wird HIER und nicht beim Malen -- nicht wegen der
        Hoehe, die steht ohnehin fest, sondern weil eine Subtraktion
        nicht dreissigmal je Sekunde stattfinden muss. Die Textbreite
        kommt gleich mit: Das Dreieck steht links neben der Zahl, und
        wo das ist, haengt an ihrer Breite.
        """
        mass = QFontMetrics(self._schrift_klein())
        self._plan = []
        for punkt in self.punkte:
            diff = self._differenz(punkt["zahl"], punkt["zahl2"])
            diff["breite"] = mass.horizontalAdvance(diff["text"])
            self._plan.append(diff)
        return (self._zf + 3 if self.spalten else 0) + len(self.punkte) * V_ZEILE

    def _balken_rechnen(self) -> float:
        """Fachbreite, Grundlinie und Beschriftung -- einmal, nicht 30/s.

        Alles hier haengt an der Zahl der Balken, und die aendert sich
        nur, wenn neuer Inhalt kommt. Im paintEvent stuende dieselbe
        Rechnerei dreissig Mal je Sekunde -- inklusive der Suche nach
        der Beschriftung, die jedes Wort einzeln vermisst.

        DIE GRUNDLINIE LIEGT NICHT AM BODEN. Sie liegt dort, wo die Null
        liegt: Sind Ausgaben und Einnahmen in einem Bild, geht ein Teil
        der Balken nach unten. Die Skala umfasst deshalb hoechsten und
        tiefsten Wert, und beide Richtungen teilen sich B_HOCH im
        Verhaeltnis ihrer Betraege. Zwei getrennte Massstaebe waeren
        bequemer zu rechnen und eine Luege: Dann waere ein Minus von 20
        so lang wie ein Plus von 2.000.

        DIE BESCHRIFTUNG in drei Stufen, weil eine Stufe nicht reicht:
        Erst ungekuerzt; passt das nicht, auf drei Zeichen; passt DAS
        nicht, nur noch jeder n-te Balken. Drei Zeichen sind keine
        beliebige Zahl -- die deutschen Monatskuerzel sind genau die
        ersten drei Buchstaben, alle zwoelf. Und drei Zeichen ohne
        Auslassungspunkte, nicht mit: Bei dieser Groesse frisst das "…"
        ein Drittel des Platzes, und "Ja…" sagt weniger als "Jan".
        """
        if not self.punkte:
            # Kein Balken, keine Achse. Ein leeres Achsenkreuz waere eine
            # Behauptung ueber eine Skala, die es nicht gibt.
            return 0.0

        mass = QFontMetrics(self._schrift_fuss())
        innen = self.breite - 2 * RAND
        anzahl = len(self.punkte)
        fach = innen / anzahl
        luft = max(B_LUFT_MIN, min(B_LUFT, fach * 0.22))
        breit = max(B_SCHMAL, fach - luft)

        zahlen = [pt["zahl"] if isinstance(pt["zahl"], float) else None
                  for pt in self.punkte]
        # Ein Punkt ohne Zahl bekommt keinen Balken -- und keine Null.
        # Eine gemalte Null saehe aus wie ein gemessener Nullwert.
        hoch = max([z for z in zahlen if z is not None and z > 0], default=0.0)
        tief = min([z for z in zahlen if z is not None and z < 0], default=0.0)
        spanne = hoch - tief

        voll = [pt["text"] for pt in self.punkte]
        kurz = [t[:B_KUERZEL] for t in voll]

        def passt(texte, schritt: int) -> bool:
            platz = fach * schritt - 2
            return all(mass.horizontalAdvance(texte[i]) <= platz
                       for i in range(0, anzahl, schritt))

        if passt(voll, 1):
            texte, schritt = voll, 1
        elif passt(kurz, 1):
            texte, schritt = kurz, 1
        else:
            texte = kurz
            schritt = next((s for s in B_SCHRITTE[1:] if passt(kurz, s)),
                           B_SCHRITTE[-1])

        def geschrieben(i: int) -> str:
            """Was ueber einem Balken steht -- lieber der Text des
            Aufrufers, denn nur der kennt die Einheit."""
            if self.punkte[i]["wert"]:
                return self.punkte[i]["wert"]
            z = zahlen[i]
            if z is None:
                return ""
            return ("−" if z < 0 else "") + self._zahl_deutsch(z)

        self._plan = []
        for i, z in enumerate(zahlen):
            marke = texte[i] if i % schritt == 0 else ""
            self._plan.append({
                "punkt": i,
                "zahl": z,
                "x": RAND + i * fach + (fach - breit) / 2,
                "mitte": RAND + (i + 0.5) * fach,
                # Der Rest ist der Notnagel fuer den Fall, dass selbst
                # der weiteste Schritt nicht reicht. Dann lieber ein
                # sichtbar gekuerztes Wort als eines, das in den Nachbarn
                # laeuft.
                "marke": mass.elidedText(marke, Qt.ElideRight,
                                         fach * schritt - 2) if marke else "",
            })

        # Der hoechste und der tiefste Balken werden angeschrieben. Ohne
        # das waere die Kachel ein Muster: Man saehe, dass Juli groesser
        # ist als Juni, aber nicht, ob es um 30 oder um 3.000 Euro geht.
        oben_i = max((i for i, z in enumerate(zahlen)
                      if z is not None and z > 0), key=lambda i: zahlen[i],
                     default=-1)
        unten_i = min((i for i, z in enumerate(zahlen)
                       if z is not None and z < 0), key=lambda i: zahlen[i],
                      default=-1)
        self._bau = {
            "fach": fach, "breit": breit, "schritt": schritt,
            "spanne": spanne, "hoch": hoch, "tief": tief,
            # Wo die Null innerhalb der Zeichenflaeche liegt. Ohne
            # negative Werte ist das der Boden.
            "null": B_HOCH * (hoch / spanne) if spanne > 0 else B_HOCH,
            "oben_i": oben_i, "unten_i": unten_i,
            "oben_text": geschrieben(oben_i) if oben_i >= 0 else "",
            "unten_text": geschrieben(unten_i) if unten_i >= 0 else "",
        }
        return (self._zf + 2 + B_HOCH + B_FUSS + self._zf
                + (self._zf if unten_i >= 0 else 0))

    def _torte_rechnen(self) -> float:
        """Winkel und Prozente ausrechnen und die Legende deckeln.

        Die Winkel entstehen HIER als Fliesskommagrad und werden
        aufsummiert weitergereicht, nicht je Stueck neu aus dem Anteil
        gerechnet. Das ist kein Geiz: Rundet man acht Stuecke einzeln,
        fehlen am Ende ein paar Zehntelgrad, und der Kreis hat einen
        feinen Spalt bei zwoelf Uhr.

        NEGATIVE UND FEHLENDE WERTE bekommen kein Stueck. Eine Torte
        zeigt Anteile an einem Ganzen, und ein negativer Anteil ist
        keiner -- man kann ihn weder als Flaeche malen noch dazuzaehlen,
        ohne dass die Summe der uebrigen Stuecke falsch wird. Sie
        verschwinden aber nicht: Sie stehen mit ihrem Betrag in der
        Legende, nur ohne Prozentzahl und ohne Farbtupfer, und eine
        Marke unter der Legende sagt, dass die 100 Prozent sie nicht
        enthalten. Stillschweigend weglassen waere dasselbe wie zu
        behaupten, es gaebe sie nicht.
        """
        if not self.punkte:
            return 0.0

        mass = QFontMetrics(self._schrift_klein())
        werte = [pt["zahl"] if (isinstance(pt["zahl"], float)
                                and pt["zahl"] > 0) else None
                 for pt in self.punkte]
        summe = sum(w for w in werte if w is not None)
        fehlt = any(w is None for w in werte)

        halb = T_RADIUS * T_BESCHRIFTET
        winkel = 90.0                 # zwoelf Uhr, dann im Uhrzeigersinn
        self._plan = []
        for i, w in enumerate(werte):
            anteil = (w / summe) if (w is not None and summe > 0) else 0.0
            spanne = -360.0 * anteil
            prozent = self._prozent(anteil) if w is not None else ""
            # Passt die Prozentzahl ins Stueck? Gemessen wird die Sehne
            # auf dem Radius, auf dem sie stehen soll -- nicht der Winkel:
            # Ein schmales Stueck ist weiter aussen breit genug, aber
            # dort steht die Zahl nicht.
            sehne = 2 * halb * math.sin(math.radians(abs(spanne)) / 2)
            innen = prozent if (w is not None
                                and abs(spanne) >= T_MINDEST_GRAD
                                and sehne >= mass.horizontalAdvance(prozent) + 4
                                ) else ""
            self._plan.append({"punkt": i, "start": winkel, "spanne": spanne,
                               "anteil": anteil, "prozent": prozent,
                               "innen": innen, "stueck": w is not None})
            winkel += spanne

        # Bleibt kein einziges Stueck uebrig, wird auch kein Platz fuer
        # den Kreis freigehalten: Ein leeres rundes Loch neben der
        # Legende sieht aus wie ein Fehler beim Malen. Die Legende
        # ruecht dann nach links und bekommt die frei gewordene Breite
        # fuer die Namen -- was uebrig bleibt, IST eine Liste.
        ring = summe > 0
        self._gekappt = fehlt
        self._bau = {
            "summe": summe, "ohne": fehlt, "ende": winkel, "ring": ring,
            "block": max(T_RING if ring else 0, len(self.punkte) * T_ZEILE),
            "x_leg": RAND + (T_RING + T_LUFT if ring else 0),
            "name": T_NAME + (0 if ring else T_RING + T_LUFT),
        }
        return self._bau["block"] + (self._zh if fehlt else 0)

    def _kategorien_rechnen(self) -> float:
        """Gruppieren, Summen bilden, den Stapel deckeln.

        Gruppiert wird in der Reihenfolge des ERSTEN Auftretens, nicht
        alphabetisch: Der Aufrufer hat eine Reihenfolge im Kopf, wenn er
        "Wohnen" vor "Freizeit" schickt, und die ist meist die, in der
        Sarvis sie auch vorliest.

        Die Gruppensumme rechnet die Kachel -- aber nur, wenn JEDER
        Eintrag der Gruppe eine Zahl hat. Fehlt eine, bleibt das
        Summenfeld leer. Eine Summe ueber unvollstaendige Posten sieht
        aus wie ein Ergebnis und ist keines; dieselbe Ueberlegung wie bei
        der Differenz im Vergleich.

        Gekappt wird UNTEN, anders als bei den Blasen. Ein Verlauf wird
        von unten gelesen, eine aufgeschluesselte Ausgabenliste von oben:
        Was der Aufrufer zuerst schickt, ist der groesste Posten.
        """
        if not self.punkte:
            return 0.0

        ordnung, mitglieder = [], {}
        for i, pt in enumerate(self.punkte):
            g = pt["gruppe"]
            if g not in mitglieder:
                mitglieder[g] = []
                ordnung.append(g)
            mitglieder[g].append(i)

        zahlen = [pt["zahl"] if isinstance(pt["zahl"], float) else None
                  for pt in self.punkte]

        reihen = []
        for nr, gruppe in enumerate(ordnung):
            leute = mitglieder[gruppe]
            # Punkte ohne Gruppe stehen ohne Ueberschrift da. Eine
            # erfundene Ueberschrift ("Sonstiges") waere eine Auskunft,
            # die niemand gegeben hat.
            if gruppe:
                teile = [zahlen[i] for i in leute]
                summe = (sum(teile) if all(t is not None for t in teile)
                         else None)
                reihen.append({
                    "art": "kopf", "text": gruppe,
                    "summe": "" if summe is None else (
                        ("−" if summe < -0.005 else "")
                        + self._zahl_deutsch(summe)),
                    "hoehe": K_KOPF + (K_LUFT if nr else 0),
                })
            for i in leute:
                reihen.append({"art": "zeile", "punkt": i, "hoehe": ZEILE})

        hoehe = 0.0
        behalten = []
        for reihe in reihen:
            if hoehe + reihe["hoehe"] > K_HOEHE:
                self._gekappt = True
                break
            hoehe += reihe["hoehe"]
            behalten.append(reihe)
        if self._gekappt:
            # Platz fuer die Marke freiraeumen, statt sie anzuhaengen:
            # sonst waere die gekuerzte Liste hoeher als der Deckel. Und
            # keine Ueberschrift ohne Zeilen stehen lassen -- die sagt
            # nur, dass etwas fehlt, ohne zu zeigen, was.
            while behalten and (hoehe + self._zh > K_HOEHE
                                or behalten[-1]["art"] == "kopf"):
                hoehe -= behalten[-1]["hoehe"]
                behalten.pop()
            behalten.append({"art": "marke", "hoehe": self._zh})
            hoehe += self._zh

        # Der Balken hinter der Schrift misst sich am groessten Posten
        # ueberhaupt, nicht am groessten der eigenen Gruppe. Je Gruppe
        # waere jede Gruppe fuer sich gut lesbar -- und der Vergleich
        # zwischen den Gruppen, wegen dem man sie nebeneinander stellt,
        # waere falsch: Die 40 Euro Freizeit saehen aus wie die 1.098
        # Euro Wohnen.
        self._plan = behalten
        self._bau = {"groesste": max([z for z in zahlen
                                      if z is not None and z > 0], default=0.0)}
        return hoehe

    # --- Graphen: Raenge, Fluss, Ablauf -----------------------------------

    @staticmethod
    def _raenge(knoten: list, kanten: list) -> tuple:
        """Spalte (Fluss) bzw. Zeile (Ablauf) je Knoten -- laengster Weg.

        knoten ist eine Liste beliebiger Namen, kanten eine Liste von
        Paaren (von, nach) daraus. Zurueck kommen die Raenge und die
        Nummern der Kanten, die AUFGETRENNT werden mussten.

        Gerechnet wird der laengste Weg von vorn, nicht der kuerzeste:
        Nur so zeigt JEDE Kante nach rechts bzw. nach unten. Beim
        kuerzesten Weg landet ein Knoten neben seinem eigenen Vorgaenger,
        und ein Band muesste rueckwaerts laufen.

        DER KREIS IST DER PUNKT DIESER FUNKTION. Ein Modell kann
        "A -> B -> A" schicken -- kein boeser Wille, sondern zwei
        Buchungen, die es beide gesehen hat. Eine Rangrechnung, die
        einfach so lange entspannt, bis sich nichts mehr aendert, laeuft
        dann bis zum Abwuergen der Anzeige. Gezaehlt werden deshalb die
        offenen Eingaenge: Solange einer auf null faellt, geht es normal
        weiter. Bleiben nur noch Knoten im Kreis uebrig, wird der mit den
        wenigsten offenen Eingaengen aufgemacht und seine restlichen
        Eingaenge werden AUFGETRENNT -- also weggelassen und vermerkt.

        Warum weggelassen und nicht rueckwaerts gemalt: Ein Sankey wird
        von links nach rechts gelesen, ein Ablauf von oben nach unten.
        Ein Band, das gegen diese Richtung laeuft, quert im Zweifel das
        ganze Bild und behauptet dabei eine Reihenfolge, die es nicht
        gibt. Ein Vermerk unter dem Bild sagt stattdessen, dass hier
        etwas nicht gezeigt werden konnte -- und dass die Rechnung
        darueber gestolpert ist, sieht man dem Bild sonst nirgends an.

        In jedem Durchgang kommt mindestens ein Knoten dazu, also endet
        die Schleife spaetestens nach len(knoten) Durchgaengen.
        """
        aus = {k: [] for k in knoten}
        ein = {k: 0 for k in knoten}
        for nr, (a, b) in enumerate(kanten):
            aus[a].append(nr)
            ein[b] += 1

        rang = {k: 0 for k in knoten}
        fertig, getrennt = set(), set()
        schlange = [k for k in knoten if ein[k] == 0]
        while len(fertig) < len(knoten):
            if not schlange:
                offen = [k for k in knoten if k not in fertig]
                naechster = min(offen, key=lambda k: (ein[k], knoten.index(k)))
                for nr, (a, b) in enumerate(kanten):
                    if (b == naechster and nr not in getrennt
                            and a not in fertig):
                        getrennt.add(nr)
                        ein[naechster] -= 1
                schlange.append(naechster)
            k = schlange.pop(0)
            if k in fertig:
                continue
            fertig.add(k)
            for nr in aus[k]:
                if nr in getrennt:
                    continue
                b = kanten[nr][1]
                rang[b] = max(rang[b], rang[k] + 1)
                ein[b] -= 1
                if ein[b] <= 0 and b not in fertig:
                    schlange.append(b)
        return rang, getrennt

    def _fluss_rechnen(self) -> float:
        """Aus Kanten Knoten, aus Wegen Spalten, aus Betraegen Baender.

        Alles hier haengt nur an den Daten und wird deshalb einmal
        gerechnet, samt der fertigen QPainterPath je Band: Ein Sankey
        aus zwanzig Baendern hat vierzig Bezierkurven, und die
        dreissigmal je Sekunde neu aufzubauen waere die teuerste Zeile
        des ganzen Moduls.

        DAS SCHWIERIGE IST DIE STAPELREIHENFOLGE, nicht die Spalte. Die
        Baender an einem Knoten muessen in derselben Ordnung liegen wie
        die Knoten, an denen ihr anderes Ende haengt -- sonst kreuzen
        sie sich INNERHALB des Knotens, und das ist der Fehler, den man
        nicht ausrechnen, sondern nur ansehen kann: Die Betraege stimmen
        weiterhin. Deshalb zwei getrennte Schritte:

          Erst die Reihenfolge der KNOTEN je Spalte, ueber den
          Schwerpunkt ihrer Nachbarn und vier Durchgaenge hin und
          zurueck. Das ist die uebliche Heuristik und reicht: Sie
          minimiert Kreuzungen ZWISCHEN den Spalten, und mehr als eine
          Heuristik ist hier nicht zu holen (das Problem ist NP-schwer).

          Dann, wenn die Knoten liegen, die Reihenfolge der BAENDER an
          jedem Knoten: ausgehende nach der Hoehe ihres Ziels, eingehende
          nach der Hoehe ihrer Quelle. Das ist keine Heuristik, sondern
          eine Sortierung -- und sie schliesst Kreuzungen im Knoten aus.

        UNGLEICHE SUMMEN sind der Normalfall, nicht der Fehler: Von 3.400
        Euro Einnahmen gehen 1.098 nach Wohnen, der Rest ist einfach
        nicht aufgeschluesselt. Der Knoten ist deshalb so hoch wie das
        GROESSERE von Ein- und Ausgang, und die Baender stapeln sich auf
        beiden Seiten von oben. Was nicht weitergereicht wird, bleibt als
        unbebaenderter Balkenrest unten stehen -- sichtbar, ohne dass
        jemand es behaupten muesste. Die Zahl neben dem Knoten ist dieses
        Groessere, also die Summe, die durch ihn hindurchgeht.

        NEGATIVE UND FEHLENDE BETRAEGE bekommen kein Band, dieselbe
        Ueberlegung wie bei der Torte: Die Dicke ist der Betrag, und ein
        negativer Betrag hat keine Dicke. Ihn als Betrag zu malen hiesse,
        einen Fluss zu zeigen, den es nicht gibt.

        GERADE STRECKE: WARUM DIE BESCHRIFTUNG EINE EIGENE SPUR HAT
        -----------------------------------------------------------
        Die erste Fassung schrieb die Knotennamen in den Zwischenraum
        zwischen zwei Spalten, also mitten in die Baender, und verliess
        sich auf den dunklen Saum aus _beschriften. Angesehen war das
        unbrauchbar: Ueber einem dicken, hellen Band steht helle Schrift
        auf hellem Grund, und der Saum ist ein Saum, keine Platte.
        "Wohnen 1.098" war auf seinem eigenen hervorgehobenen Band
        praktisch nicht zu lesen.

        Eine eigene Spur schien zuerst unmoeglich, und zwar aus einem
        Grund, der stimmt: Ein Band haengt an zwei Balken, also gehoert
        ALLES zwischen ihnen dem Band. Ein reservierter Streifen dazwischen
        wuerde das Band zerschneiden.

        Der Ausweg ist nicht, den Streifen freizuhalten, sondern die
        Baender darin GERADE laufen zu lassen. Auf einer waagerechten
        Strecke liegt jedes Band genau auf der Hoehe seines Quellknotens
        -- es hat seine Hoehe noch nicht gewechselt. Damit gilt in der
        Spur hinter einem Balken:

            Es liegen dort NUR die abgehenden Baender dieses einen
            Knotens, gestapelt auf genau seiner Hoehe. Fremde Baender
            koennen nicht hinein, denn die liegen auf der Hoehe IHRES
            Knotens, und die Knoten einer Spalte ueberlappen sich nicht.

        Erst hinter der Spur beginnt der Bogen, und erst dort mischen
        sich die Baender. Der Nutzen ist nicht bloss optisch: Unter einer
        Beschriftung liegt jetzt eine BEKANNTE Farbe -- entweder der
        eigene Ton des Knotens oder der Kachelgrund. Damit laesst sich
        die Schriftfarbe ausrechnen statt raten, und genau das tut
        _fluss_malen ueber _schrift_auf().

        Bezahlt wird das mit Breite: 111 Punkte je Spalte, die vorher
        die Baender hatten. Bei drei Spalten sind das 532 statt 382 --
        gut ein Drittel mehr und immer noch weit unter den 800, die zur
        Verfuegung stehen. Bei sechs Spalten ginge es nicht mehr auf,
        deshalb steht der Deckel jetzt bei fuenf.
        """
        # Ohne Bild keine Breite: Die Obergrenze aus FORM_BREITE gilt fuer
        # sechs Spalten, und 739 Rasterpunkte, in denen nichts steht als
        # eine Kopfzeile, sehen nicht nach "keine Daten" aus, sondern nach
        # einem Fenster, das nicht fertig geworden ist.
        self.breite = BREITE
        if not self.punkte:
            return 0.0

        mass = QFontMetrics(self._schrift_klein())
        marken = [MARKE_DECKEL] if self._weggelassen else []

        # --- 1. Was ist ueberhaupt eine Kante?
        kanten, unklar = [], False
        for i, punkt in enumerate(self.punkte):
            von, nach = punkt["von"].strip(), punkt["nach"].strip()
            zahl = punkt["zahl"]
            if (not von or not nach or von == nach
                    or not isinstance(zahl, float) or zahl <= 0):
                unklar = True
                continue
            kanten.append({"punkt": i, "von": von, "nach": nach, "wert": zahl})

        def aufgeben() -> float:
            """Nichts zu malen -- aber sagen, dass etwas da war."""
            self._plan = []
            self._bau = {"marken": marken, "knoten": [], "flaeche": 0.0}
            return len(marken) * self._zh

        if unklar:
            marken.append(MARKE_KANTEN)
        if not kanten:
            return aufgeben()

        # --- 2. Knoten in der Reihenfolge des ersten Auftretens
        namen = []
        for kante in kanten:
            for name in (kante["von"], kante["nach"]):
                if name not in namen:
                    namen.append(name)

        # --- 3. Spalten, Kreise auftrennen
        rang, getrennt = self._raenge(
            namen, [(k["von"], k["nach"]) for k in kanten])
        if getrennt:
            marken.append(MARKE_KREIS)
            kanten = [k for nr, k in enumerate(kanten) if nr not in getrennt]

        # --- 4. Zu tief? Dann faellt der Rest weg, aber nicht stumm.
        if any(rang[n] >= F_SPALTEN for n in namen):
            marken.append(MARKE_TIEF)
            namen = [n for n in namen if rang[n] < F_SPALTEN]
            bleibt = set(namen)
            kanten = [k for k in kanten
                      if k["von"] in bleibt and k["nach"] in bleibt]
        if not kanten or not namen:
            return aufgeben()

        spalten = [[] for _ in range(max(rang[n] for n in namen) + 1)]
        for name in namen:
            spalten[rang[name]].append(name)

        # --- 5. Reihenfolge der Knoten je Spalte (Schwerpunkt)
        vorher = {n: [] for n in namen}
        nachher = {n: [] for n in namen}
        for kante in kanten:
            vorher[kante["nach"]].append(kante["von"])
            nachher[kante["von"]].append(kante["nach"])

        ort = {}

        def orte_merken():
            for spalte in spalten:
                for platz, name in enumerate(spalte):
                    ort[name] = platz

        def schwerpunkt(spalte, nachbarn):
            def mitte(name):
                weit = [ort[m] for m in nachbarn[name] if m in ort]
                return sum(weit) / len(weit) if weit else ort[name]
            # sorted ist stabil: Knoten ohne Nachbarn behalten ihren Platz.
            return sorted(spalte, key=mitte)

        orte_merken()
        for _ in range(4):
            for c in range(1, len(spalten)):
                spalten[c] = schwerpunkt(spalten[c], vorher)
                orte_merken()
            for c in range(len(spalten) - 2, -1, -1):
                spalten[c] = schwerpunkt(spalten[c], nachher)
                orte_merken()

        # --- 6. Wie hoch ist ein Knoten?
        ein = {n: 0.0 for n in namen}
        aus = {n: 0.0 for n in namen}
        for kante in kanten:
            aus[kante["von"]] += kante["wert"]
            ein[kante["nach"]] += kante["wert"]
        durch = {n: max(ein[n], aus[n]) for n in namen}

        luft = self._zh
        breiteste = max(len(s) for s in spalten)
        flaeche = float(max(F_HOCH, (breiteste - 1) * luft + F_BALKEN_MIN))
        # Der Massstab ist der KLEINSTE, den irgendeine Spalte vertraegt:
        # Ein Massstab je Spalte waere bequemer und eine Luege -- dann
        # waere ein Band rechts dicker als sein eigener Zufluss links.
        moeglich = [(flaeche - (len(s) - 1) * luft) / sum(durch[n] for n in s)
                    for s in spalten if s and sum(durch[n] for n in s) > 0]
        massstab = min(moeglich) if moeglich else 0.0

        # --- 7a. Wie breit sind Namensspur und Schwung?
        #
        # Die Spur bekommt, was sie braucht (F_NAME), der Schwung den
        # Rest -- gedeckelt bei F_KURVE, damit ein Zweispalter nicht
        # halb aus Bogen besteht. Reicht es fuer beides nicht, gibt der
        # Schwung bis F_KURVE_MIN nach und erst dann die Spur: Ein
        # flacherer Bogen ist immer noch ein Bogen, ein abgeschnittener
        # Name ist keine Auskunft mehr.
        wieviel = len(spalten)
        rest = FORM_BREITE["fluss"] - 2 * RAND - wieviel * F_KNOTEN
        spur = float(F_NAME)
        schwung = 0.0
        if wieviel > 1:
            schwung = min(float(F_KURVE),
                          (rest - wieviel * spur) / (wieviel - 1))
            if schwung < F_KURVE_MIN:
                schwung = float(F_KURVE_MIN)
                spur = (rest - (wieviel - 1) * schwung) / wieviel
        namensbreite = spur - F_NAME_RAND - F_WERT - 8

        # --- 7b. Wo liegt ein Knoten?
        knoten, nummer = [], {}
        for c, spalte in enumerate(spalten):
            stapel = (sum(durch[n] for n in spalte) * massstab
                      + luft * max(0, len(spalte) - 1))
            y = (flaeche - stapel) / 2.0
            for platz, name in enumerate(spalte):
                hoch = durch[name] * massstab
                nummer[name] = len(knoten)
                knoten.append({
                    "name": name, "spalte": c, "platz": platz,
                    "anzahl": max(2, len(spalte)),
                    "x": float(RAND + c * (F_KNOTEN + spur + schwung)),
                    "y": y, "hoehe": hoch,
                    "kurz": mass.elidedText(name, Qt.ElideRight,
                                            namensbreite),
                    "betrag": self._zahl_deutsch(durch[name]),
                    # Wie weit die eigenen Baender den Knoten von oben
                    # her belegen. Das Malen braucht es, um zu wissen,
                    # was unter der Beschriftung liegt -- siehe dort.
                    "aus": aus[name] * massstab,
                })
                y += hoch + luft

        # --- 8. Stapelreihenfolge an jedem Knoten
        for name in namen:
            k = knoten[nummer[name]]
            hinaus = sorted([e for e in kanten if e["von"] == name],
                            key=lambda e: knoten[nummer[e["nach"]]]["y"]
                            + knoten[nummer[e["nach"]]]["hoehe"] / 2.0)
            y = k["y"]
            for kante in hinaus:
                kante["y0"] = y
                y += kante["wert"] * massstab
            herein = sorted([e for e in kanten if e["nach"] == name],
                            key=lambda e: knoten[nummer[e["von"]]]["y"]
                            + knoten[nummer[e["von"]]]["hoehe"] / 2.0)
            y = k["y"]
            for kante in herein:
                kante["y1"] = y
                y += kante["wert"] * massstab

        # --- 9. Die Baender
        self._plan = []
        for kante in kanten:
            a = knoten[nummer[kante["von"]]]
            b = knoten[nummer[kante["nach"]]]
            x0 = a["x"] + F_KNOTEN
            xg = x0 + spur              # hier hoert die Spur auf
            x1 = b["x"]
            xm = (xg + x1) / 2.0
            dick = kante["wert"] * massstab
            y0, y1 = kante["y0"], kante["y1"]
            # Erst gerade durch die Namensspur, dann der Bogen. Die
            # gerade Strecke ist nicht Zierde, sie ist der Grund, warum
            # die Spur ueberhaupt eine Spur ist -- siehe Docstring.
            pfad = QPainterPath(QPointF(x0, y0))
            pfad.lineTo(xg, y0)
            pfad.cubicTo(xm, y0, xm, y1, x1, y1)
            pfad.lineTo(x1, y1 + dick)
            pfad.cubicTo(xm, y1 + dick, xm, y0 + dick, xg, y0 + dick)
            pfad.lineTo(x0, y0 + dick)
            pfad.closeSubpath()
            self._plan.append({
                "punkt": kante["punkt"], "pfad": pfad,
                # Ein Band traegt die Farbe seiner QUELLE. Damit hat
                # alles, was aus einem Knoten kommt, einen Ton -- und
                # was in ihn hineinlaeuft, mehrere. So folgt das Auge
                # dem Weg und nicht der Spalte.
                "stufe": (a["platz"], a["anzahl"]),
                "von": nummer[kante["von"]], "nach": nummer[kante["nach"]],
            })

        self._gekappt = bool(marken)
        self._bau = {"knoten": knoten, "flaeche": flaeche, "marken": marken,
                     "massstab": massstab, "spur": spur, "schwung": schwung,
                     "name": namensbreite}
        # Die Breite haengt an der Zahl der Spalten -- siehe FORM_BREITE.
        # Sie wird nicht gedeckelt, sondern IST der Deckel, sobald spur
        # und schwung ihn ausreizen; die Rechnung oben kann ihn nicht
        # ueberschreiten.
        self.breite = round(2 * RAND + wieviel * F_KNOTEN + wieviel * spur
                            + (wieviel - 1) * schwung)
        return flaeche + len(marken) * self._zh

    def _ablauf_rechnen(self) -> float:
        """Kaesten in Zeilen, Pfeile dazwischen -- einmal ausgerechnet.

        Ein Punkt ist hier ein KASTEN, kein Pfeil. Der Grund steht im
        Modulkopf: Leuchten soll der Kasten, und die gerade Kette ist der
        Regelfall. "von" darf deshalb fehlen und meint dann den vorigen
        Punkt -- eine Kette aus fuenf Schritten ist fuenf Texte, sonst
        nichts.

        Nennt "von" einen Namen, den es nicht gibt, gilt ebenfalls der
        vorige Punkt. Das ist eine Entscheidung gegen die Alternative,
        nicht fuer die Bequemlichkeit: Ein Kasten ohne Vorgaenger stuende
        als zweiter Anfang neben dem Ablauf, und ein Ablauf mit zwei
        Anfaengen sieht kaputt aus, obwohl nur ein Name falsch
        geschrieben war. Die Reihenfolge der Liste ist ohnehin eine
        Angabe des Aufrufers, keine Erfindung der Kachel.

        ZUSAMMENLAUFENDE ZWEIGE gehen ueber "nach", und nur darueber: Der
        Baum aus "von" ist das Geruest, an dem die Zeilen haengen; jedes
        "nach" ist eine ZUSAETZLICHE Kante daran. Beide zusammen gehen
        durch _raenge, und deshalb rutscht ein Kasten, in den zwei Zweige
        muenden, von selbst unter den tieferen der beiden -- sonst
        zeigte einer der beiden Pfeile zur Seite statt nach unten.

        Was dabei ENTSTEHT und beachtet werden muss: Ein Pfeil kann jetzt
        eine Zeile ueberspringen. Der laeuft nicht quer durch die
        Kaesten dazwischen, sondern durch eine Gasse am rechten Rand.
        Ohne die waere genau das der Fehler, den man bei jedem vierten
        Graphen sieht -- ein Pfeil, der durch einen Kasten geht.
        """
        # Siehe _fluss_rechnen: ohne Kaesten keine Breite.
        self.breite = BREITE
        if not self.punkte:
            return 0.0

        anzahl = len(self.punkte)
        marken = [MARKE_DECKEL] if self._weggelassen else []

        # Namen -> erster Punkt mit diesem Namen. Der erste, nicht der
        # letzte: Wer zweimal "fertig" schickt, meint beim Verweisen das
        # erste -- alles andere waere geraten.
        wo = {}
        for i, punkt in enumerate(self.punkte):
            text = punkt["text"].strip()
            if text and text not in wo:
                wo[text] = i

        kanten, aufschrift = [], {}
        for i, punkt in enumerate(self.punkte):
            eltern = wo.get(punkt["von"].strip(), i - 1 if i else None)
            if eltern is not None and eltern != i:
                kanten.append((eltern, i))
                if punkt["wert"]:
                    aufschrift[(eltern, i)] = punkt["wert"]
        for i, punkt in enumerate(self.punkte):
            ziel = wo.get(punkt["nach"].strip())
            if (ziel is not None and ziel != i and (i, ziel) not in kanten):
                kanten.append((i, ziel))

        rang, getrennt = self._raenge(list(range(anzahl)), kanten)
        if getrennt:
            marken.append(MARKE_KREIS)
            kanten = [k for nr, k in enumerate(kanten) if nr not in getrennt]

        zeilen = [[] for _ in range(max(rang.values()) + 1)]
        for i in range(anzahl):
            zeilen[rang[i]].append(i)
        breiteste = max(len(z) for z in zeilen)

        # Braucht ueberhaupt ein Pfeil die Gasse? Nur dann kostet sie
        # Breite -- eine leere Spur am Rand waere ein schiefes Bild.
        gasse = any(rang[b] - rang[a] > 1 for a, b in kanten)
        rand_gasse = A_GASSE if gasse else 0

        # Kaesten werden SCHMALER, nicht weggelassen: Ein Ablauf, dem der
        # vierte Zweig fehlt, ist ein anderer Ablauf. Ein schmaler Kasten
        # mit gekuerztem Text ist immer noch derselbe.
        #
        # Die Fuge schrumpft mit, und zwar nie ueber die Haelfte des
        # Platzes hinaus. Ohne diese Schranke faende sich eine Zahl von
        # Zweigen, bei der die Fugen allein schon breiter waeren als die
        # Kachel -- und dann stuenden die Kaesten ausserhalb. Mit ihr
        # bleibt fuer sie immer mindestens die halbe Innenbreite uebrig,
        # und die Summe unten kann A_MAX gar nicht ueberschreiten.
        platz = A_MAX - 2 * RAND - rand_gasse
        luft = min(A_LUFT, platz / (2.0 * breiteste))
        kasten_breit = min(A_KASTEN,
                           (platz - (breiteste - 1) * luft) / breiteste)
        self.breite = round(max(
            BREITE, 2 * RAND + rand_gasse + breiteste * kasten_breit
            + (breiteste - 1) * luft))

        mass = QFontMetrics(self._schrift_klein())
        innen = max(1.0, kasten_breit - 2 * A_RAND)
        texte = []
        for punkt in self.punkte:
            umbruch = self._umbrechen(mass, punkt["text"], innen) or [""]
            if len(umbruch) > A_ZEILEN:
                rest = " ".join(umbruch[A_ZEILEN - 1:])
                umbruch = umbruch[:A_ZEILEN - 1] + [
                    mass.elidedText(rest, Qt.ElideRight, innen)]
            texte.append(umbruch)

        # --- Lage der Kaesten, von oben nach unten
        lage, y, gekappt = {}, 0.0, False
        zone = self.breite - 2 * RAND - rand_gasse
        for r, reihe in enumerate(zeilen):
            hoch = max(len(texte[i]) for i in reihe) * self._zh + 2 * A_RAND
            if r and y + A_PFEIL + hoch > A_HOEHE:
                gekappt = True
                break
            if r:
                y += A_PFEIL
            gesamt = len(reihe) * kasten_breit + (len(reihe) - 1) * luft
            x = RAND + (zone - gesamt) / 2.0
            for i in reihe:
                lage[i] = QRectF(x, y, kasten_breit, hoch)
                x += kasten_breit + luft
            y += hoch
        if gekappt:
            marken.append(MARKE)

        # --- Pfeile
        self._plan = []
        spur = 0
        for a, b in kanten:
            if a not in lage or b not in lage:
                continue
            oben, unten = lage[a], lage[b]
            sx, sy = oben.center().x(), oben.bottom()
            tx, ty = unten.center().x(), unten.top()

            def neben(hoehe: float) -> QRectF:
                """Beschriftung rechts neben dem senkrechten Stueck.

                Sie sitzt auf derselben Hoehe wie die Beschriftung der
                geknickten Geschwister, naemlich unter dem Querstrich --
                und das ist der Grund, warum sie ueberhaupt dorthin muss:
                Ein Kasten mit drei Ausgaengen hat einen geraden Pfeil
                in der Mitte und zwei geknickte daneben. Stuende sein
                Wort weiter oben, laege es genau auf dem Querstrich der
                beiden anderen. Gemessen: "unklar" lag quer ueber der
                Klammer von "ok" und "nein".
                """
                return QRectF(sx + 4, hoehe,
                              min(kasten_breit / 2.0,
                                  self.breite - RAND - sx - 4), self._zf)

            if rang[b] - rang[a] > 1:
                # Ueber die Gasse aussen herum. Zwei Spuren nebeneinander
                # reichen: Bei zehn Schritten gibt es nicht mehr
                # ueberspringende Pfeile, die gleichzeitig auf derselben
                # Hoehe laufen.
                gx = self.breite - RAND - 5 - (spur % 2) * 6
                spur += 1
                ecken = [(sx, sy), (sx, sy + 8), (gx, sy + 8),
                         (gx, ty - 8), (tx, ty - 8), (tx, ty)]
                schrift = neben(sy + 9)
                lage_aus = Qt.AlignLeft
            elif abs(sx - tx) < 0.6:
                ecken = [(sx, sy), (tx, ty)]
                schrift = neben(sy + A_PFEIL / 2.0 + 1)
                lage_aus = Qt.AlignLeft
            else:
                quer = sy + A_PFEIL / 2.0
                ecken = [(sx, sy), (sx, quer), (tx, quer), (tx, ty)]
                # Die Beschriftung sitzt UNTER dem Querstueck, nicht
                # darueber: Darueber stiesse sie bei A_PFEIL = 24 an die
                # Unterkante des Kastens, aus dem der Pfeil kommt.
                schrift = QRectF(min(sx, tx), quer + 1, abs(tx - sx), self._zf)
                lage_aus = Qt.AlignHCenter
            self._plan.append({
                "art": "pfeil",
                "linie": QPolygonF([QPointF(*e) for e in ecken]),
                "spitze": QPolygonF([QPointF(tx - A_KOPF, ty - 5.0),
                                     QPointF(tx + A_KOPF, ty - 5.0),
                                     QPointF(tx, ty)]),
                "text": aufschrift.get((a, b), ""),
                "schrift": schrift, "aus": lage_aus,
            })
        for i in sorted(lage):
            self._plan.append({"art": "kasten", "punkt": i,
                               "kasten": lage[i], "zeilen": texte[i]})
        for text in marken:
            self._plan.append({"art": "marke", "text": text})

        self._gekappt = bool(marken)
        self._bau = {"hoehe": y, "marken": marken}
        return y + len(marken) * self._zh

    @staticmethod
    def _prozent(anteil: float) -> str:
        """0.1412 -> "14 %". Genauer nur da, wo es noetig ist.

        Unter zehn Prozent eine Nachkommastelle, darueber keine: "76,4 %"
        liest sich langsamer als "76 %" und sagt in einer Kachel nichts
        dazu -- bei "0,5 %" ist die Stelle dagegen die ganze Auskunft.
        Was auf null runden wuerde, wird als "<0,1 %" geschrieben: Eine
        gemalte Null neben einem sichtbaren Stueck waere ein Widerspruch.
        """
        p = anteil * 100.0
        if p <= 0:
            return "0 %"
        if p < 0.1:
            return "<0,1 %"
        if p < 10:
            return f"{p:.1f}".replace(".", ",") + " %"
        return f"{p:.0f} %"

    @staticmethod
    def _leuchtdichte(c: QColor) -> float:
        """Relative Helligkeit nach WCAG -- fuer Kontrastrechnungen.

        Nicht (r+g+b)/3: Gruen traegt zur empfundenen Helligkeit gut
        siebenmal so viel bei wie Blau. Ein Mittelwert wuerde ausgerechnet
        die beiden Kachelfarben falsch einschaetzen, weil die eine
        orange und die andere gruen ist.
        """
        def kanal(v: float) -> float:
            v = v / 255.0
            return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
        return (0.2126 * kanal(c.red()) + 0.7152 * kanal(c.green())
                + 0.0722 * kanal(c.blue()))

    @staticmethod
    def _ueber_grund(ton: QColor, deckung: float) -> QColor:
        """Was man wirklich sieht, wenn ton mit dieser Deckung liegt.

        Ein Band ist halbdurchsichtig; seine Farbe allein sagt nichts
        darueber, wie hell die Stelle am Ende ist. Gerechnet wird gegen
        den Kachelgrund, nicht gegen den Schreibtisch dahinter: Der
        Grund deckt zu rund neunzig Prozent, der Rest faellt gegenueber
        dem Unterschied zwischen heller und dunkler Schrift nicht ins
        Gewicht.
        """
        g = QColor(8, 13, 20)
        rest = 1.0 - deckung
        return QColor(round(ton.red() * deckung + g.red() * rest),
                      round(ton.green() * deckung + g.green() * rest),
                      round(ton.blue() * deckung + g.blue() * rest))

    @classmethod
    def _schrift_auf(cls, grund: QColor, kerze: QColor) -> QColor:
        """Welche Schrift auf DIESEM Grund noch zu lesen ist.

        Die Kachelfarbe bleibt, solange sie traegt -- eine Kachel, in der
        die Beschriftung mal orange und mal weiss ist, sieht aus wie zwei
        Kacheln. Erst wenn sie MESSBAR nicht mehr traegt, wird gewechselt,
        und dann auf das, was auf diesem Grund am besten steht: dunkle
        Tinte auf hellem Band, fast weiss auf mittlerem.

        Die Schwelle ist die 4,5:1 aus WCAG fuer normalen Fliesstext,
        nicht die 3,0:1 fuer grosse Schrift: Hier steht Segoe UI 7, und
        das ist das Gegenteil von grosser Schrift.

        Warum ueberhaupt gerechnet und nicht wie im Tortenstueck an einer
        Helligkeitsschwelle festgemacht: Dort liegt die Zahl auf einer
        fast deckenden Flaeche, hier auf einem Band mit 0,38 oder 0,80
        Deckung ueber dem Kachelgrund. Dieselbe Bandfarbe ergibt je nach
        Deckung einen ganz anderen Untergrund -- und genau daran ist die
        erste Fassung gescheitert.
        """
        hell = cls._leuchtdichte(grund)

        def kontrast(c: QColor) -> float:
            dort = cls._leuchtdichte(c)
            return (max(hell, dort) + 0.05) / (min(hell, dort) + 0.05)

        if kontrast(kerze) >= 4.5:
            return QColor(kerze)
        dunkel = QColor(8, 13, 20)
        weiss = QColor(245, 248, 252)
        return dunkel if kontrast(dunkel) >= kontrast(weiss) else weiss

    @staticmethod
    def _stufe(farbe: QColor, i: int, anzahl: int) -> QColor:
        """Die i-te Abstufung der Kachelfarbe.

        Kein Regenbogen: Eine Kachel gehoert optisch zum Ring, und acht
        frei gewaehlte Bunttoene daneben sehen aus wie ein fremdes
        Fenster. Abgestuft wird die EINE Farbe, die die Kachel ohnehin
        traegt.

        Drei Groessen wandern gleichzeitig -- Helligkeit, Saettigung und
        ein kleiner Ton-Versatz -- statt nur der Helligkeit. Wandert nur
        eine, faellt die ganze Unterscheidung aus, sobald sie fuer einen
        Betrachter ausfaellt.

        DIE REIHENFOLGE IST NICHT DIE DER LEGENDE. Die erste Fassung
        lief die Abstufung der Reihe nach durch -- das las sich schoen
        und war gemessen unbrauchbar: Bei acht Stuecken lagen zwei
        benachbarte Toene 1,08:1 auseinander, und die Kante zwischen
        ihnen war keine. Vergeben wird deshalb ueber Kreuz (0, 4, 1, 5,
        …), sodass zwei im KREIS benachbarte Stuecke moeglichst weit
        auseinander liegen -- gemessen wird der schwaechste Nachbarschritt,
        nicht der Durchschnitt. Wer ein Stueck in der Legende sucht,
        vergleicht ohnehin den Farbtupfer und zaehlt nicht ab.
        """
        h, s, v, _ = farbe.getHsvF()
        if anzahl <= 1:
            return QColor(farbe)
        # ueber Kreuz: erst jede zweite Stufe, dann die dazwischen
        platz = (i % 2) * ((anzahl + 1) // 2) + i // 2
        anteil = platz / (anzahl - 1)
        if h < 0:                      # unbunt -- dann nur die Helligkeit
            return QColor.fromHsvF(0.0, 0.0,
                                   max(0.0, v * (1.0 - 0.62 * anteil)))
        return QColor.fromHsvF(
            (h + 0.055 * anteil) % 1.0,
            max(0.0, min(1.0, s * (1.0 - 0.38 * anteil))),
            max(0.0, min(1.0, v * (1.0 - 0.58 * anteil))))

    @staticmethod
    def _zahl_deutsch(wert: float) -> str:
        """1234.5 -> "1.234,50". Ohne Vorzeichen, das setzt der Aufrufer.

        Zwei Nachkommastellen nur, wenn es welche gibt: "13" liest sich
        schneller als "13,00", und in einer Kachel zaehlt genau das.
        """
        stellen = 0 if abs(wert - round(wert)) < 0.005 else 2
        roh = f"{abs(wert):,.{stellen}f}"
        # Erst tauschen, dann ersetzen -- sonst werden aus den Punkten,
        # die gerade Kommas geworden sind, wieder Punkte.
        return roh.replace(",", "\x00").replace(".", ",").replace("\x00", ".")

    @classmethod
    def _differenz(cls, zahl, zahl2) -> dict:
        """Was zwischen den beiden Zahlen liegt -- selbst gerechnet.

        Fehlt eine der beiden, wird nichts behauptet: leeres Feld statt
        einer Null, die wie ein Ergebnis aussieht.
        """
        if not isinstance(zahl, float) or not isinstance(zahl2, float):
            return {"text": "", "richtung": 0}
        d = zahl - zahl2
        if abs(d) < 0.005:
            return {"text": "±0", "richtung": 0}
        # Echtes Minuszeichen, kein Bindestrich: In Segoe UI ist der
        # Bindestrich so kurz, dass man ihn neben einer Ziffer uebersieht.
        zeichen = "+" if d > 0 else "−"
        return {"text": zeichen + cls._zahl_deutsch(d),
                "richtung": 1 if d > 0 else -1}

    def platzieren_an(self, anker: QRect, seite: str = "",
                      versatz: int = 0) -> None:
        """Die Lage der Engine merken und sich danach ausrichten.

        Uebergeben wird ausdruecklich der SICHTBARE Bereich der Engine,
        nicht ihr Fenster: Das Overlay hat ringsum durchsichtigen Rand.
        Wer sich an der Fensterkante ausrichtet, setzt die Kachel
        scheinbar grundlos weit weg.

        seite ist "rechts" oder "links". Ohne Angabe entscheidet die
        Sorte: Antworten rechts, Zustaende links. Das ist keine
        Geschmacksfrage -- ohne getrennte Seiten liegen die beiden
        uebereinander, und gemessen taten sie das auch: Beide landeten
        auf denselben Bildschirmpunkten.

        versatz stapelt mehrere Kacheln derselben Seite untereinander.
        """
        self._anker = QRect(anker)
        self._seite = seite or ("links" if self.sorte == "zustand"
                                else "rechts")
        self._versatz = int(versatz)
        if self.isVisible():
            self._platzieren(self._anker)

    def _platzieren(self, anker: QRect) -> None:
        abstand = round(ABSTAND * SKALA)
        schirm = self._schirm_von(anker)
        frei = schirm.availableGeometry() if schirm else None

        rechts = anker.right() + abstand
        links = anker.left() - abstand - self.width()
        x = rechts if self._seite == "rechts" else links
        y = anker.top() + self._versatz

        if frei is not None:
            # Passt die gewuenschte Seite nicht mehr, wird die andere
            # genommen. Halb ueber den Bildschirmrand hinaus waere
            # schlimmer als die falsche Seite.
            if x + self.width() > frei.right():
                x = links if links >= frei.left() else x
            elif x < frei.left():
                x = rechts if rechts + self.width() <= frei.right() else x
            # Immer noch daneben: dann lieber am Rand kleben als draussen.
            x = max(frei.left(), min(x, frei.right() - self.width()))
            y = max(frei.top(), min(y, frei.bottom() - self.height()))

        self.move(x, y)

    @staticmethod
    def _schirm_von(anker: QRect):
        """Der Bildschirm, auf dem die Engine steht."""
        mitte = anker.center()
        for schirm in QGuiApplication.screens():
            if schirm.geometry().contains(mitte):
                return schirm
        return QGuiApplication.primaryScreen()

    # --- Takt -------------------------------------------------------------

    def _schlag(self) -> None:
        self._tick += 0.033
        self._alter += 0.033
        if self._rest > 0:
            self._rest -= 0.033
            if self._rest <= 0:
                self._rest = 0.0
                self.hide()
                self._uhr.stop()
                return
        self.update()

    def _deckkraft(self) -> float:
        """Auf- und Ausblenden. Ein hartes Erscheinen wirkt wie ein Fehler."""
        auf = min(1.0, self._alter / AUF) if AUF > 0 else 1.0
        zu = 1.0
        # _rest == 0 heisst "bleibt stehen" -- dann wird nie ausgeblendet.
        if 0 < self._rest < ZU:
            zu = self._rest / ZU
        return max(0.0, min(1.0, auf * zu)) * config.DECKKRAFT_AKTIV

    # --- Malen ------------------------------------------------------------

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Ab hier wird im Raster gemalt, nicht in Bildschirmpixeln.
        p.scale(SKALA, SKALA)
        p.setOpacity(self._deckkraft())

        farbe = FARBE_ANTWORT if self.sorte == "antwort" else FARBE_ZUSTAND
        self._grund(p, farbe)

        y = float(RAND)
        y = self._kopfzeile(p, farbe, y)
        if self.gross:
            y = self._grosse_zahl(p, farbe, y)
        # Der Rumpf ist das Einzige, was sich je Form unterscheidet. Kopf,
        # grosse Zahl, Grund und Fusszeile sind ueberall dieselben -- eine
        # Kachel soll als Kachel erkennbar bleiben, egal was drinsteht.
        if self.form == "blasen":
            y = self._blasen_malen(p, farbe, y)
        elif self.form == "vergleich":
            y = self._vergleich_malen(p, farbe, y)
        elif self.form == "text":
            y = self._text_malen(p, farbe, y)
        elif self.form == "balken":
            y = self._balken_malen(p, farbe, y)
        elif self.form == "torte":
            y = self._torte_malen(p, farbe, y)
        elif self.form == "kategorien":
            y = self._kategorien_malen(p, farbe, y)
        elif self.form == "fluss":
            y = self._fluss_malen(p, farbe, y)
        elif self.form == "ablauf":
            y = self._ablauf_malen(p, farbe, y)
        else:
            y = self._datenzeilen(p, farbe, y)
        if self.stand:
            self._fusszeile(p, farbe, y)

    def _grund(self, p, farbe) -> None:
        """Dunkler Grund mit feinem Rahmen.

        Der Grund ist nicht Zierde: Eine Kachel liegt mal auf schwarzem
        Editor, mal auf weissem Explorer. Ohne ihn waere sie im zweiten
        Fall unlesbar, egal wie hoch die Deckkraft steht -- dasselbe
        Problem, das _beschriften in hud.py mit dem Saum loest.
        """
        kasten = QRectF(0.5, 0.5, self.breite - 1, self._hoehe - 1)
        grund = QColor(8, 13, 20)
        grund.setAlphaF(0.90 * config.ANZEIGE_GRUND / 1.30)
        p.setPen(Qt.NoPen)
        p.setBrush(grund)
        p.drawRect(kasten)

        rahmen = QColor(farbe)
        rahmen.setAlphaF(0.30)
        p.setPen(QPen(rahmen, 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawRect(kasten)

        # Ein kraeftiger Strich oben: Er sagt auf einen Blick, welche Sorte
        # Kachel das ist -- Antwort oder laufender Zustand.
        strich = QColor(farbe)
        strich.setAlphaF(0.85)
        p.setPen(QPen(strich, 2.0))
        p.drawLine(QPointF(0, 1), QPointF(self.breite, 1))

    def _kopfzeile(self, p, farbe, y: float) -> float:
        f = QFont("Segoe UI", 7)
        f.setLetterSpacing(QFont.PercentageSpacing, 160)
        f.setCapitalization(QFont.AllUppercase)
        p.setFont(f)
        c = QColor(farbe)
        c.setAlphaF(0.95)
        self._beschriften(p, QRectF(RAND, y, self.breite - 2 * RAND, 15),
                          Qt.AlignLeft, self.kopf, c)

        if self.sorte == "zustand":
            # Ein wandernder Punkt, wie in der Hintergrund-Ecke: Eine
            # stehende Zeile sieht aus wie eine haengengebliebene.
            schritt = 0.5 + 0.5 * math.sin(self._tick * 2.2)
            punkt = QColor(farbe)
            punkt.setAlphaF(0.25 + 0.70 * schritt)
            p.setPen(Qt.NoPen)
            p.setBrush(punkt)
            p.drawEllipse(QPointF(self.breite - RAND - 3, y + 7), 2.6, 2.6)
        return y + 18

    def _grosse_zahl(self, p, farbe, y: float) -> float:
        f = QFont("Segoe UI", 17)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        c = QColor(farbe)
        c.setAlphaF(0.98)
        self._beschriften(p, QRectF(RAND, y, self.breite - 2 * RAND, 30),
                          Qt.AlignLeft | Qt.AlignVCenter, self.gross, c)
        return y + 30

    def _datenzeilen(self, p, farbe, y: float) -> float:
        p.setFont(self._schrift_klein())
        mass = QFontMetrics(p.font())
        wertbreite = 78
        platz = self.breite - 2 * RAND - wertbreite - 6

        # Der groesste Wert bestimmt die Balkenlaenge. Nur positive Zahlen:
        # Ein Balken fuer minus achtzig Euro muesste in die andere Richtung
        # zeigen, und das ist eine eigene Ueberlegung wert -- solange sie
        # nicht angestellt ist, wird lieber kein Balken gemalt als ein
        # falscher.
        zahlen = [pt["zahl"] for pt in self.punkte
                  if isinstance(pt["zahl"], float) and pt["zahl"] > 0]
        groesste = max(zahlen) if zahlen else 0.0

        for i, punkt in enumerate(self.punkte):
            leuchtet = (i == self.hervor)
            voll = QRectF(RAND - 4, y - 1, self.breite - 2 * RAND + 8, ZEILE - 1)

            # Der Balken liegt HINTER der Schrift, nicht daneben: Neben
            # ihr bliebe fuer Bezeichnung und Betrag zu wenig Platz, und
            # ein Diagramm, dessen Beschriftung abgeschnitten ist, sagt
            # weniger als eine blosse Liste.
            zahl = punkt["zahl"]
            if groesste > 0 and isinstance(zahl, float) and zahl > 0:
                anteil = max(0.0, min(1.0, zahl / groesste))
                balken = QColor(farbe)
                balken.setAlphaF(0.24 if leuchtet else 0.13)
                p.setPen(Qt.NoPen)
                p.setBrush(balken)
                p.drawRect(QRectF(voll.left(), voll.top(),
                                  voll.width() * anteil, voll.height()))

            if leuchtet:
                # Der hervorgehobene Eintrag bekommt einen Rahmen, nicht nur
                # eine andere Farbe: Eine Nuance heller erkennt niemand aus
                # zwei Metern Entfernung -- und ein Grund allein waere vom
                # Balken darunter nicht zu unterscheiden.
                rand = QColor(farbe)
                rand.setAlphaF(0.75)
                p.setPen(QPen(rand, 1.0))
                p.setBrush(Qt.NoBrush)
                p.drawRect(voll)

            c = QColor(farbe)
            c.setAlphaF(1.0 if leuchtet else 0.78)
            self._beschriften(
                p, QRectF(RAND, y, platz, ZEILE - 1), Qt.AlignLeft,
                mass.elidedText(punkt["text"], Qt.ElideRight, platz), c)
            if punkt["wert"]:
                self._beschriften(
                    p, QRectF(self.breite - RAND - wertbreite, y, wertbreite,
                              ZEILE - 1),
                    Qt.AlignRight, punkt["wert"], c)
            y += ZEILE
        return y

    # --- Blasen -----------------------------------------------------------

    def _blasen_malen(self, p, farbe, y: float) -> float:
        """Gespraechsblasen. Links der andere, rechts ich.

        Die Seite ist die Auskunft darueber, wer geschrieben hat -- das
        ist die Sehgewohnheit aus jedem Messenger, und sie kostet keine
        Zeile Text. Damit sie auch dann traegt, wenn beide Blasen
        zufaellig gleich breit sind, unterscheiden sie sich zusaetzlich:
        meine ist gefuellt, seine traegt einen Balken an der Kante.
        """
        if self._gekappt:
            p.setFont(self._schrift_klein())
            c = QColor(farbe)
            c.setAlphaF(0.40)
            self._beschriften(p, QRectF(RAND, y, self.breite - 2 * RAND,
                                        self._zh),
                              Qt.AlignHCenter, MARKE_ALT, c)
            y += self._zh

        for blase in self._plan:
            leuchtet = (blase["punkt"] == self.hervor)
            breit = blase["breite"]
            x = (self.breite - RAND - breit) if blase["von_mir"] else RAND
            kasten = QRectF(x, y, breit, blase["hoehe"])

            # Die fremde Blase ist blasser als die eigene, aber nicht
            # unsichtbar: Bei 0.08 war sie auf hellem Untergrund vom
            # Kachelgrund nicht mehr zu unterscheiden -- dann steht dort
            # kein Verlauf, sondern eine Liste mit Einzug.
            grund = QColor(farbe)
            grund.setAlphaF((0.32 if leuchtet else 0.22) if blase["von_mir"]
                            else (0.20 if leuchtet else 0.12))
            p.setPen(Qt.NoPen)
            p.setBrush(grund)
            p.drawRoundedRect(kasten, BLASE_ECKE, BLASE_ECKE)

            if not blase["von_mir"]:
                # Der Balken an der Aussenkante: Er trennt die fremde
                # Blase von der eigenen auch dann, wenn beide gleich
                # weit vom Rand entfernt stehen.
                kante = QColor(farbe)
                kante.setAlphaF(0.70)
                p.setPen(Qt.NoPen)
                p.setBrush(kante)
                p.drawRect(QRectF(x, y + 2, 2.5, blase["hoehe"] - 4))

            if leuchtet:
                # Dieselbe Geste wie in der Liste: ein Rahmen, keine
                # Nuance. Eine hellere Fuellung waere aus zwei Metern
                # nicht von der Nachbarblase zu unterscheiden.
                rand = QColor(farbe)
                rand.setAlphaF(0.80)
                p.setPen(QPen(rand, 1.0))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(kasten, BLASE_ECKE, BLASE_ECKE)

            p.setFont(self._schrift_klein())
            c = QColor(farbe)
            c.setAlphaF(1.0 if leuchtet else 0.86)
            zy = y + BLASE_RAND
            for zeile in blase["zeilen"]:
                self._beschriften(
                    p, QRectF(x + BLASE_RAND, zy,
                              breit - 2 * BLASE_RAND, self._zh),
                    Qt.AlignLeft | Qt.AlignVCenter, zeile, c)
                zy += self._zh
            y += blase["hoehe"]

            if blase["fuss"]:
                p.setFont(self._schrift_fuss())
                cf = QColor(farbe)
                cf.setAlphaF(0.45)
                self._beschriften(
                    p, QRectF(RAND, y, self.breite - 2 * RAND, blase["fuss"]),
                    Qt.AlignRight if blase["von_mir"] else Qt.AlignLeft,
                    blase["wert"], cf)
                y += blase["fuss"]
            y += BLASE_LUFT
        return y - BLASE_LUFT if self._plan else y

    # --- Vergleich ---------------------------------------------------------

    def _vergleich_malen(self, p, farbe, y: float) -> float:
        """Zwei Wertspalten und die selbst gerechnete Differenz."""
        x_diff = self.breite - RAND - V_DIFF
        x_zwei = x_diff - V_LUFT - V_WERT
        x_eins = x_zwei - V_LUFT - V_WERT
        platz = x_eins - V_LUFT - RAND

        if self.spalten:
            p.setFont(self._schrift_fuss())
            f = QFont(p.font())
            f.setCapitalization(QFont.AllUppercase)
            p.setFont(f)
            c = QColor(farbe)
            c.setAlphaF(0.50)
            koepfe = list(self.spalten) + [""] * (2 - len(self.spalten))
            for x, wort in ((x_eins, koepfe[0]), (x_zwei, koepfe[1])):
                self._beschriften(p, QRectF(x, y, V_WERT, self._zf),
                                  Qt.AlignRight, wort, c)
            self._beschriften(p, QRectF(x_diff, y, V_DIFF, self._zf),
                              Qt.AlignRight, "Differenz", c)
            y += self._zf + 3

        p.setFont(self._schrift_klein())
        mass = QFontMetrics(p.font())
        for i, punkt in enumerate(self.punkte):
            leuchtet = (i == self.hervor)
            voll = QRectF(RAND - 4, y - 1, self.breite - 2 * RAND + 8,
                          V_ZEILE - 1)
            if leuchtet:
                rand = QColor(farbe)
                rand.setAlphaF(0.75)
                p.setPen(QPen(rand, 1.0))
                p.setBrush(Qt.NoBrush)
                p.drawRect(voll)

            c = QColor(farbe)
            c.setAlphaF(1.0 if leuchtet else 0.78)
            self._beschriften(
                p, QRectF(RAND, y, platz, V_ZEILE - 1), Qt.AlignLeft,
                mass.elidedText(punkt["text"], Qt.ElideRight, platz), c)
            for x, wert in ((x_eins, punkt["wert"]), (x_zwei, punkt["wert2"])):
                self._beschriften(p, QRectF(x, y, V_WERT, V_ZEILE - 1),
                                  Qt.AlignRight, wert, c)

            diff = (self._plan[i] if i < len(self._plan)
                    else {"text": "", "richtung": 0, "breite": 0})
            if diff["text"]:
                self._differenz_malen(p, farbe, diff,
                                      QRectF(x_diff, y, V_DIFF, V_ZEILE - 1))
            y += V_ZEILE
        return y

    def _differenz_malen(self, p, farbe, diff: dict, kasten: QRectF) -> None:
        """Vorzeichen, Farbe UND Dreieck -- drei Zeichen fuer eine Aussage.

        Die Farbe allein reicht nicht: Rot und Gruen sind fuer rund jeden
        zwoelften Mann dieselbe Farbe. Das Vorzeichen steht direkt vor der
        Zahl, das Dreieck davor zeigt in dieselbe Richtung -- wer keines
        von beiden sieht, liest immer noch die Zahl.
        """
        richtung = diff["richtung"]
        if richtung == 0:
            c = QColor(farbe)
            c.setAlphaF(0.55)
        else:
            c = QColor(FARBE_MEHR if richtung > 0 else FARBE_WENIGER)
            c.setAlphaF(0.95)

        self._beschriften(p, kasten, Qt.AlignRight | Qt.AlignVCenter,
                          diff["text"], c)

        if richtung == 0:
            return
        # Selbst gemalt statt als Zeichen aus einer Schrift: Die
        # Icon-Schrift kann fehlen (siehe hud._icon_schrift), und ein
        # leerer Kasten waere hier keine Auskunft, sondern eine falsche.
        rechts = kasten.right() - diff.get("breite", 0) - 4
        mitte = kasten.center().y()
        spitze = 3.0
        if richtung > 0:
            ecken = [QPointF(rechts - 5, mitte + 2.4),
                     QPointF(rechts, mitte + 2.4),
                     QPointF(rechts - 2.5, mitte + 2.4 - spitze * 1.6)]
        else:
            ecken = [QPointF(rechts - 5, mitte - 2.4),
                     QPointF(rechts, mitte - 2.4),
                     QPointF(rechts - 2.5, mitte - 2.4 + spitze * 1.6)]
        p.setPen(Qt.NoPen)
        p.setBrush(c)
        p.drawPolygon(QPolygonF(ecken))

    # --- Fliesstext --------------------------------------------------------

    def _text_malen(self, p, farbe, y: float) -> float:
        """Der fertig umgebrochene Text. Zeile fuer Zeile, kein Umbruch mehr.

        Ohne Hervorhebung: In einem Fliesstext gibt es keine Zeile, die
        Sarvis gerade nennt -- er nennt hoechstens einen Satz, und der
        steht nicht sauber in einer Zeile.
        """
        p.setFont(self._schrift_klein())
        c = QColor(farbe)
        c.setAlphaF(0.84)
        blass = QColor(farbe)
        blass.setAlphaF(0.45)
        for zeile in self._plan:
            if zeile:
                self._beschriften(
                    p, QRectF(RAND, y, self.breite - 2 * RAND, self._zh),
                    Qt.AlignLeft | Qt.AlignVCenter, zeile,
                    blass if zeile == MARKE else c)
            y += self._zh
        return y

    # --- Balken ------------------------------------------------------------

    def _balken_malen(self, p, farbe, y: float) -> float:
        """Balken nebeneinander, Grundlinie quer, Marken darunter.

        Warum die Balken nach unten NICHT rot werden, obwohl das die
        Gewohnheit waere: Die Richtung sagt es schon, und zwar
        unmissverstaendlich -- ueber der Linie oder darunter, das
        verwechselt niemand. Eine zweite Farbe daneben waere auf einer
        Zustandskachel ausgerechnet das Paar Gruen/Rot, das rund jeder
        zwoelfte Mann nicht trennt. Unterschieden wird deshalb ueber die
        FORM: nach oben gefuellt, nach unten umrissen. Das bleibt auch
        in Graustufen stehen.
        """
        if not self._plan:
            return y
        bau = self._bau
        y_flaeche = y + self._zf + 2
        y_null = y_flaeche + bau["null"]
        spanne = bau["spanne"]

        for eintrag in self._plan:
            zahl = eintrag["zahl"]
            if zahl is None or spanne <= 0 or abs(zahl) < 1e-9:
                continue
            leuchtet = (eintrag["punkt"] == self.hervor)
            laenge = B_HOCH * (abs(zahl) / spanne)
            kasten = QRectF(eintrag["x"],
                            y_null - laenge if zahl > 0 else y_null,
                            bau["breit"], laenge)
            fuellung = QColor(farbe)
            if zahl > 0:
                fuellung.setAlphaF(0.92 if leuchtet else 0.58)
                p.setPen(Qt.NoPen)
                p.setBrush(fuellung)
                p.drawRect(kasten)
            else:
                fuellung.setAlphaF(0.30 if leuchtet else 0.16)
                strich = QColor(farbe)
                strich.setAlphaF(0.95 if leuchtet else 0.62)
                p.setPen(QPen(strich, 1.0))
                p.setBrush(fuellung)
                # Um einen halben Punkt eingerueckt, sonst liegt der
                # Strich halb ausserhalb des Faches und der Balken sieht
                # breiter aus als sein Nachbar.
                p.drawRect(kasten.adjusted(0.5, 0.5, -0.5, -0.5))

        # Die Grundlinie zuletzt und ueber den Balken: Sie ist die
        # Achse, an der abgelesen wird, und darf von keinem Balken
        # ueberdeckt werden.
        linie = QColor(farbe)
        linie.setAlphaF(0.55)
        p.setPen(QPen(linie, 1.0))
        p.drawLine(QPointF(RAND, y_null), QPointF(self.breite - RAND, y_null))

        if 0 <= self.hervor < len(self._plan):
            # Wie ueberall in dieser Kachel: ein Rahmen, keine Nuance.
            # Er umschliesst das ganze Fach, nicht nur den Balken --
            # sonst waere ein Monat mit sehr kleinem Wert kaum markiert.
            eintrag = self._plan[self.hervor]
            rand = QColor(farbe)
            rand.setAlphaF(0.75)
            p.setPen(QPen(rand, 1.0))
            p.setBrush(Qt.NoBrush)
            p.drawRect(QRectF(eintrag["mitte"] - bau["fach"] / 2 + 0.5,
                              y_flaeche, bau["fach"] - 1, B_HOCH))

        p.setFont(self._schrift_fuss())
        mass = QFontMetrics(p.font())
        hell = QColor(farbe)
        hell.setAlphaF(0.80)

        def anschreiben(text: str, mitte: float, oben: float) -> None:
            """Mittig ueber den Balken, aber nie ueber den Rand hinaus."""
            breit = mass.horizontalAdvance(text) + 2
            x = min(max(mitte - breit / 2, RAND),
                    self.breite - RAND - breit)
            self._beschriften(p, QRectF(x, oben, breit, self._zf),
                              Qt.AlignHCenter, text, hell)

        if bau["oben_text"]:
            anschreiben(bau["oben_text"], self._plan[bau["oben_i"]]["mitte"], y)
        y_marken = y_flaeche + B_HOCH + B_FUSS
        if bau["unten_text"]:
            anschreiben(bau["unten_text"],
                        self._plan[bau["unten_i"]]["mitte"], y_marken)
            y_marken += self._zf

        for eintrag in self._plan:
            if not eintrag["marke"]:
                continue
            leuchtet = (eintrag["punkt"] == self.hervor)
            c = QColor(farbe)
            c.setAlphaF(1.0 if leuchtet else 0.62)
            self._beschriften(
                p, QRectF(eintrag["mitte"] - bau["fach"] * bau["schritt"] / 2,
                          y_marken, bau["fach"] * bau["schritt"], self._zf),
                Qt.AlignHCenter, eintrag["marke"], c)
        return y_marken + self._zf

    # --- Torte -------------------------------------------------------------

    def _torte_malen(self, p, farbe, y: float) -> float:
        """Kreis links, Legende rechts.

        Gemalt wird mit QPainterPath und nicht mit drawPie, weil drawPie
        seine Winkel in Sechzehntelgrad als ganze Zahl nimmt. Acht
        gerundete Stuecke ergeben zusammen nicht mehr 360 Grad, und der
        Fehler steht sichtbar bei zwoelf Uhr.

        DIE BESCHRIFTUNG TRAEGT DIE AUSSAGE, die Farbe hilft nur. Jedes
        Stueck steht mit Namen, Betrag und Prozentzahl in der Legende --
        wer die Abstufungen nicht auseinanderhalten kann, liest die
        Kachel trotzdem vollstaendig. Die Zahl IM Stueck ist die Zugabe
        fuer die grossen; ein Stueck von einem halben Prozent bekommt
        keine, weil sie nicht hineinpasst, und wird deshalb nicht groesser
        gemalt, als es ist.
        """
        if not self._plan:
            return y
        anzahl = len(self._plan)
        block = self._bau["block"]
        kreis = QRectF(RAND + T_AUS, y + (block - T_RING) / 2 + T_AUS,
                       2 * T_RADIUS, 2 * T_RADIUS)
        mitte = kreis.center()

        # Die Fuge zwischen zwei Stuecken hat die Farbe des Grundes. Sie
        # ist der eigentliche Grund, warum benachbarte Abstufungen
        # auseinanderzuhalten sind: Selbst wenn zwei Toene fuer jemanden
        # gleich aussehen, bleibt die Kante sichtbar.
        fuge = QColor(8, 13, 20)
        fuge.setAlphaF(0.85)

        for i, stueck in enumerate(self._plan):
            if not stueck["stueck"] or abs(stueck["spanne"]) < 1e-9:
                continue
            leuchtet = (stueck["punkt"] == self.hervor)
            versatz = QPointF(0, 0)
            if leuchtet:
                mittelwinkel = math.radians(stueck["start"]
                                            + stueck["spanne"] / 2)
                versatz = QPointF(math.cos(mittelwinkel) * T_AUS,
                                  -math.sin(mittelwinkel) * T_AUS)
            pfad = QPainterPath(mitte + versatz)
            pfad.arcTo(kreis.translated(versatz), stueck["start"],
                       stueck["spanne"])
            pfad.closeSubpath()

            fuellung = self._stufe(farbe, i, anzahl)
            fuellung.setAlphaF(0.98 if leuchtet else 0.86)
            p.setPen(QPen(fuge, 1.0))
            p.setBrush(fuellung)
            p.drawPath(pfad)

            if leuchtet:
                rand = QColor(farbe)
                rand.setAlphaF(0.90)
                p.setPen(QPen(rand, 1.2))
                p.setBrush(Qt.NoBrush)
                p.drawPath(pfad)

        # Die Prozentzahlen zuletzt, damit keine Fuge darueber laeuft.
        p.setFont(self._schrift_klein())
        for i, stueck in enumerate(self._plan):
            if not stueck["innen"]:
                continue
            winkel = math.radians(stueck["start"] + stueck["spanne"] / 2)
            weit = T_RADIUS * T_BESCHRIFTET
            ort = QPointF(mitte.x() + math.cos(winkel) * weit,
                          mitte.y() - math.sin(winkel) * weit)
            # Auf dunklen Stuecken hell schreiben, auf hellen dunkel --
            # sonst verschwindet die Zahl in der eigenen Abstufung.
            grund = self._stufe(farbe, i, anzahl)
            c = (QColor(8, 13, 20) if grund.valueF() > 0.62
                 else QColor(245, 248, 252))
            c.setAlphaF(0.95)
            p.setPen(c)
            p.drawText(QRectF(ort.x() - 26, ort.y() - self._zh / 2,
                              52, self._zh),
                       Qt.AlignCenter, stueck["innen"])

        # --- Legende
        x_leg = self._bau["x_leg"]
        namensbreite = self._bau["name"]
        x_name = x_leg + T_TUPF + 5
        x_wert = x_name + namensbreite + 4
        x_proz = x_wert + T_WERT + 4
        y_leg = y + (block - anzahl * T_ZEILE) / 2
        p.setFont(self._schrift_klein())
        mass = QFontMetrics(p.font())
        for i, stueck in enumerate(self._plan):
            punkt = self.punkte[stueck["punkt"]]
            leuchtet = (stueck["punkt"] == self.hervor)
            if leuchtet:
                rand = QColor(farbe)
                rand.setAlphaF(0.75)
                p.setPen(QPen(rand, 1.0))
                p.setBrush(Qt.NoBrush)
                # Vier Punkte ueber den Satzspiegel hinaus, wie in der
                # Liste: Ein Rahmen, der die Prozentzahl beruehrt, sieht
                # aus wie ein abgeschnittenes Feld.
                p.drawRect(QRectF(x_leg - 4, y_leg + 0.5,
                                  self.breite - RAND - x_leg + 8,
                                  T_ZEILE - 1))

            tupf = QRectF(x_leg, y_leg + (T_ZEILE - T_TUPF) / 2,
                          T_TUPF, T_TUPF)
            if stueck["stueck"]:
                p.setPen(Qt.NoPen)
                p.setBrush(self._stufe(farbe, i, anzahl))
                p.drawRoundedRect(tupf, 1.5, 1.5)
            else:
                # Kein Stueck, kein Tupfer -- ein leeres Kaestchen sagt,
                # dass dieser Posten im Kreis nicht vorkommt.
                leer = QColor(farbe)
                leer.setAlphaF(0.35)
                p.setPen(QPen(leer, 1.0))
                p.setBrush(Qt.NoBrush)
                p.drawRect(tupf.adjusted(0.5, 0.5, -0.5, -0.5))

            c = QColor(farbe)
            c.setAlphaF(1.0 if leuchtet else 0.82)
            self._beschriften(
                p, QRectF(x_name, y_leg, namensbreite, T_ZEILE),
                Qt.AlignLeft | Qt.AlignVCenter,
                mass.elidedText(punkt["text"], Qt.ElideRight, namensbreite), c)
            self._beschriften(p, QRectF(x_wert, y_leg, T_WERT, T_ZEILE),
                              Qt.AlignRight | Qt.AlignVCenter,
                              punkt["wert"], c)
            self._beschriften(p, QRectF(x_proz, y_leg, T_PROZ, T_ZEILE),
                              Qt.AlignRight | Qt.AlignVCenter,
                              stueck["prozent"], c)
            y_leg += T_ZEILE

        y += block
        if self._bau.get("ohne"):
            p.setFont(self._schrift_klein())
            c = QColor(farbe)
            c.setAlphaF(0.45)
            self._beschriften(p, QRectF(RAND, y, self.breite - 2 * RAND,
                                        self._zh),
                              Qt.AlignHCenter, MARKE_OHNE, c)
            y += self._zh
        return y

    # --- Kategorien ---------------------------------------------------------

    def _kategorien_malen(self, p, farbe, y: float) -> float:
        """Zwischenueberschrift mit Summe, darunter die eingerueckten Posten."""
        groesste = self._bau.get("groesste", 0.0)
        platz = self.breite - 2 * RAND - K_EINZUG - 6 - K_WERT
        for reihe in self._plan:
            if reihe["art"] == "kopf":
                y += reihe["hoehe"] - K_KOPF        # die Luft davor
                f = self._schrift_fuss()
                f.setCapitalization(QFont.AllUppercase)
                p.setFont(f)
                mass = QFontMetrics(f)
                c = QColor(farbe)
                c.setAlphaF(0.62)
                frei = self.breite - 2 * RAND - K_WERT - 6
                self._beschriften(
                    p, QRectF(RAND, y, frei, self._zf), Qt.AlignLeft,
                    mass.elidedText(reihe["text"], Qt.ElideRight, frei), c)
                if reihe["summe"]:
                    self._beschriften(
                        p, QRectF(self.breite - RAND - K_WERT, y, K_WERT,
                                  self._zf),
                        Qt.AlignRight, reihe["summe"], c)
                # Ein Haarstrich unter der Ueberschrift. Er ist das, was
                # aus einer eingerueckten Liste eine gruppierte macht:
                # Ohne ihn liest man die Ueberschrift als ersten Posten.
                strich = QColor(farbe)
                strich.setAlphaF(0.22)
                p.setPen(QPen(strich, 1.0))
                p.drawLine(QPointF(RAND, y + self._zf + 1.5),
                           QPointF(self.breite - RAND, y + self._zf + 1.5))
                y += K_KOPF
                continue

            if reihe["art"] == "marke":
                p.setFont(self._schrift_klein())
                c = QColor(farbe)
                c.setAlphaF(0.45)
                self._beschriften(p, QRectF(RAND, y, self.breite - 2 * RAND,
                                            reihe["hoehe"]),
                                  Qt.AlignHCenter, MARKE, c)
                y += reihe["hoehe"]
                continue

            punkt = self.punkte[reihe["punkt"]]
            leuchtet = (reihe["punkt"] == self.hervor)
            p.setFont(self._schrift_klein())
            mass = QFontMetrics(p.font())
            voll = QRectF(RAND + K_EINZUG - 4, y - 1,
                          self.breite - RAND - (RAND + K_EINZUG) + 8, ZEILE - 1)

            zahl = punkt["zahl"]
            if groesste > 0 and isinstance(zahl, float) and zahl > 0:
                balken = QColor(farbe)
                balken.setAlphaF(0.24 if leuchtet else 0.13)
                p.setPen(Qt.NoPen)
                p.setBrush(balken)
                p.drawRect(QRectF(voll.left(), voll.top(),
                                  voll.width() * min(1.0, zahl / groesste),
                                  voll.height()))
            if leuchtet:
                rand = QColor(farbe)
                rand.setAlphaF(0.75)
                p.setPen(QPen(rand, 1.0))
                p.setBrush(Qt.NoBrush)
                p.drawRect(voll)

            c = QColor(farbe)
            c.setAlphaF(1.0 if leuchtet else 0.78)
            self._beschriften(
                p, QRectF(RAND + K_EINZUG, y, platz, ZEILE - 1), Qt.AlignLeft,
                mass.elidedText(punkt["text"], Qt.ElideRight, platz), c)
            if punkt["wert"]:
                self._beschriften(
                    p, QRectF(self.breite - RAND - K_WERT, y, K_WERT,
                              ZEILE - 1),
                    Qt.AlignRight, punkt["wert"], c)
            y += ZEILE
        return y

    # --- Fluss ---------------------------------------------------------------

    def _fluss_malen(self, p, farbe, y: float) -> float:
        """Baender hinten, Balken darauf, Beschriftung zuletzt.

        Die Reihenfolge ist die ganze Lesbarkeit: Ein Band, das ueber
        seinen eigenen Knotenbalken laeuft, verschluckt dessen Kante, und
        eine Beschriftung unter einem Band ist keine.

        Ein Band ist halbdurchsichtig, ein Balken nicht. Das ist kein
        Geschmack: Zwei Baender, die sich kreuzen, muessen als zwei
        Baender lesbar bleiben -- deckend waere das obere einfach vorn
        und das untere weg. Der Balken dagegen ist die Marke, an der
        abgelesen wird, und die darf nicht durchscheinen.

        DIE BESCHRIFTUNG STEHT IN IHRER EIGENEN SPUR rechts neben dem
        Balken -- warum das geht, steht bei _fluss_rechnen unter GERADE
        STRECKE. Hier zaehlt die Folge daraus: Unter einer Beschriftung
        liegt genau eine von zwei bekannten Farben, naemlich der eigene
        Ton des Knotens (wenn seine abgehenden Baender die Zeile
        ausfuellen) oder der Kachelgrund (wenn nicht -- letzte Spalte,
        oder ein Knoten, der mehr aufnimmt als er weitergibt).

        Beide sind ausrechenbar, und deshalb wird die Schriftfarbe hier
        ausgerechnet und nicht gesetzt: _ueber_grund mischt die wirkliche
        Farbe unter der Zeile, _schrift_auf waehlt zwischen der
        Kachelfarbe und der dunklen Tinte, was darauf besser steht. Das
        ist der Fall, der die erste Fassung erledigt hat: Ein
        hervorgehobenes Band steht auf 0,80 Deckung, und darauf ist die
        helle Kachelfarbe nicht mehr zu lesen -- dort schreibt die
        Kachel jetzt dunkel.
        """
        knoten = self._bau.get("knoten") or []
        marken = self._bau.get("marken") or []
        flaeche = self._bau.get("flaeche", 0.0)
        if not knoten and not marken:
            return y

        p.save()
        p.translate(0.0, y)

        leuchtend = None
        for band in self._plan:
            leuchtet = (band["punkt"] == self.hervor)
            if leuchtet:
                leuchtend = band
            c = self._stufe(farbe, band["stufe"][0], band["stufe"][1])
            c.setAlphaF(0.80 if leuchtet else 0.38)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawPath(band["pfad"])
        if leuchtend is not None:
            # Wie ueberall in dieser Kachel: ein Rahmen, keine Nuance.
            # Ein Band, das nur heller ist, verschwindet zwischen seinen
            # Nachbarn, sobald es duenn ist -- und duenn ist es meistens.
            rand = QColor(farbe)
            rand.setAlphaF(0.85)
            p.setPen(QPen(rand, 1.0))
            p.setBrush(Qt.NoBrush)
            p.drawPath(leuchtend["pfad"])

        p.setFont(self._schrift_klein())
        for nr, k in enumerate(knoten):
            c = self._stufe(farbe, k["platz"], k["anzahl"])
            c.setAlphaF(0.95)
            p.setPen(Qt.NoPen)
            p.setBrush(c)
            p.drawRect(QRectF(k["x"], k["y"], F_KNOTEN,
                              max(k["hoehe"], F_STRICH)))

            x_text = k["x"] + F_KNOTEN + F_NAME_RAND
            # Bei sehr duennen Knoten haengt die mittig gesetzte
            # Beschriftung sonst oben oder unten aus der Flaeche heraus.
            y_text = max(0.0, min(flaeche - self._zh,
                                  k["y"] + k["hoehe"] / 2.0 - self._zh / 2.0))

            # Was liegt unter dieser Zeile? Die abgehenden Baender des
            # Knotens fuellen ihn von oben her auf k["aus"] Punkte auf --
            # deckt das mehr als die halbe Zeile, ist der Bandton der
            # Grund, sonst der Kachelgrund. Gemessen wird die wirkliche
            # Ueberlappung und nicht "hat der Knoten Ausgaenge": Ein
            # Knoten, der 1.098 aufnimmt und 820 weitergibt, hat unter
            # seiner Zeile noch Band, unter seinem Fuss aber nicht mehr.
            ueber = max(0.0, (min(y_text + self._zh, k["y"] + k["aus"])
                              - max(y_text, k["y"])))
            leuchtet = (leuchtend is not None
                        and nr in (leuchtend["von"], leuchtend["nach"]))
            if ueber >= self._zh / 2.0:
                deckung = 0.80 if (leuchtend is not None
                                   and leuchtend["von"] == nr) else 0.38
                grund = self._ueber_grund(
                    self._stufe(farbe, k["platz"], k["anzahl"]), deckung)
            else:
                grund = QColor(8, 13, 20)
            # Deckend, anders als in den Listenformen: Dort ist die
            # Deckkraft eine Abstufung zwischen wichtig und weniger
            # wichtig, hier waere sie ein Abzug von genau dem Kontrast,
            # der eben ausgerechnet wurde.
            tinte = self._schrift_auf(grund, farbe)
            self._beschriften(
                p, QRectF(x_text, y_text, self._bau["name"], self._zh),
                Qt.AlignLeft | Qt.AlignVCenter, k["kurz"], tinte)
            self._beschriften(
                p, QRectF(x_text + self._bau["name"] + 4, y_text, F_WERT,
                          self._zh),
                Qt.AlignRight | Qt.AlignVCenter, k["betrag"], tinte)

            if leuchtet:
                rand = QColor(farbe)
                rand.setAlphaF(0.70)
                p.setPen(QPen(rand, 1.0))
                p.setBrush(Qt.NoBrush)
                p.drawRect(QRectF(k["x"] - 1.5, k["y"] - 1.5, F_KNOTEN + 3,
                                  max(k["hoehe"], F_STRICH) + 3))
        p.restore()

        y += flaeche
        blass = QColor(farbe)
        blass.setAlphaF(0.45)
        p.setFont(self._schrift_klein())
        for text in marken:
            self._beschriften(p, QRectF(RAND, y, self.breite - 2 * RAND,
                                        self._zh),
                              Qt.AlignHCenter, text, blass)
            y += self._zh
        return y

    # --- Ablauf --------------------------------------------------------------

    def _ablauf_malen(self, p, farbe, y: float) -> float:
        """Pfeile zuerst, Kaesten darueber.

        Die Pfeilspitze endet genau auf der Oberkante ihres Kastens; der
        Kasten wird danach gemalt und deckt sie deshalb nicht zu, sondern
        schliesst an sie an. Andersherum saehe jeder Pfeil aus, als
        stiesse er einen Punkt zu weit.
        """
        p.save()
        p.translate(0.0, y)
        for stueck in self._plan:
            if stueck["art"] == "pfeil":
                strich = QColor(farbe)
                strich.setAlphaF(0.55)
                p.setPen(QPen(strich, 1.0))
                p.setBrush(Qt.NoBrush)
                p.drawPolyline(stueck["linie"])
                p.setPen(Qt.NoPen)
                p.setBrush(strich)
                p.drawPolygon(stueck["spitze"])
                if stueck["text"]:
                    p.setFont(self._schrift_fuss())
                    c = QColor(farbe)
                    c.setAlphaF(0.72)
                    self._beschriften(p, stueck["schrift"], stueck["aus"],
                                      stueck["text"], c)
                continue
            if stueck["art"] != "kasten":
                continue

            leuchtet = (stueck["punkt"] == self.hervor)
            kasten = stueck["kasten"]
            grund = QColor(farbe)
            grund.setAlphaF(0.30 if leuchtet else 0.12)
            kante = QColor(farbe)
            kante.setAlphaF(0.95 if leuchtet else 0.50)
            p.setPen(QPen(kante, 1.6 if leuchtet else 1.0))
            p.setBrush(grund)
            p.drawRoundedRect(kasten.adjusted(0.5, 0.5, -0.5, -0.5),
                              A_ECKE, A_ECKE)

            p.setFont(self._schrift_klein())
            c = QColor(farbe)
            c.setAlphaF(1.0 if leuchtet else 0.86)
            zy = kasten.top() + A_RAND
            for zeile in stueck["zeilen"]:
                self._beschriften(
                    p, QRectF(kasten.left() + A_RAND, zy,
                              kasten.width() - 2 * A_RAND, self._zh),
                    Qt.AlignHCenter | Qt.AlignVCenter, zeile, c)
                zy += self._zh
        p.restore()

        y += self._bau.get("hoehe", 0.0)
        blass = QColor(farbe)
        blass.setAlphaF(0.45)
        p.setFont(self._schrift_klein())
        for stueck in self._plan:
            if stueck["art"] != "marke":
                continue
            self._beschriften(p, QRectF(RAND, y, self.breite - 2 * RAND,
                                        self._zh),
                              Qt.AlignHCenter, stueck["text"], blass)
            y += self._zh
        return y

    def _fusszeile(self, p, farbe, y: float) -> None:
        p.setFont(self._schrift_fuss())
        # Blasser als alles andere, aber da. Der Zeitstempel ist die
        # Antwort auf "steht da noch der Wert von vorgestern?" -- ohne ihn
        # veraltet eine Kachel stillschweigend.
        c = QColor(farbe)
        c.setAlphaF(0.45)
        self._beschriften(p, QRectF(RAND, y + 2, self.breite - 2 * RAND, 14),
                          Qt.AlignLeft, self.stand, c)

    @staticmethod
    def _beschriften(p, kasten, ausrichtung, text, farbe):
        """Schrift mit dunklem Saum -- dieselbe Loesung wie in hud.py.

        Auch mit eigenem Grund noch noetig: Der Grund ist halbdurchsichtig,
        damit die Kachel nicht wie ein aufgeklebter Zettel wirkt. Damit
        schlaegt heller Untergrund weiter durch.
        """
        saum = QColor(4, 8, 16)
        saum.setAlphaF(0.55 * farbe.alphaF())
        p.setPen(saum)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):
            p.drawText(kasten.translated(dx, dy), ausrichtung, text)
        p.setPen(farbe)
        p.drawText(kasten, ausrichtung, text)
