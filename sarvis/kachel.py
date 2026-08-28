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
Bildschirmpixeln gerechnete Kachel eine Briefmarke.
"""
import math

from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer
from PySide6.QtGui import (QColor, QFont, QFontMetrics, QGuiApplication,
                           QPainter, QPen)
from PySide6.QtWidgets import QWidget

from . import config

# Das Malraster einer Kachel. Dieselbe Logik wie BREITE/HOEHE in hud.py:
# Hier drin wird gerechnet, erst der Maler wird gestreckt.
BREITE = 250
RAND = 14              # Innenabstand
ZEILE = 15             # Hoehe einer Datenzeile
SKALA = max(0.6, min(3.0, config.ANZEIGE_SKALA))

# Abstand zwischen der sichtbaren Engine und der Kachel, im Malraster.
ABSTAND = 18

# Farben. Eine Antwort gehoert zu dem, was er GERADE sagt -- sie traegt
# deshalb die Sprechfarbe aus hud.py. Ein Zustand gehoert zu etwas, das
# laeuft, und traegt dieselbe eigene Farbe wie die Hintergrund-Ecke:
# Das ist bewusst keiner der Gespraechszustaende.
FARBE_ANTWORT = QColor(255, 179, 71)
FARBE_ZUSTAND = QColor(126, 224, 168)

# Wie lange eine Antwort-Kachel steht, wenn nichts anderes gesagt wird.
# Lang genug, um sie nach dem gesprochenen Satz noch in Ruhe anzusehen;
# kurz genug, dass sie nicht zum Moebel wird.
ANTWORT_SEKUNDEN = 45.0

AUF = 0.22             # Sekunden zum Aufblenden
ZU = 0.55              # Sekunden zum Ausblenden


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
        self.punkte: list = []
        self.stand = ""          # "Stand 10:42" -- wann die Daten geholt wurden
        self.hervor = -1         # welcher Punkt gerade leuchtet (-1 = keiner)
        self._hoehe = 0          # wird in _masse_setzen aus dem Inhalt gerechnet

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
        """
        if isinstance(roh, dict):
            zahl = roh.get("zahl")
            return {"text": str(roh.get("text", "")),
                    "wert": str(roh.get("wert", "")),
                    "zahl": float(zahl) if isinstance(zahl, (int, float))
                    else None}
        if isinstance(roh, (tuple, list)):
            text = str(roh[0]) if roh else ""
            wert = str(roh[1]) if len(roh) > 1 else ""
            return {"text": text, "wert": wert, "zahl": None}
        return {"text": str(roh), "wert": "", "zahl": None}

    def anzeigen(self, kopf: str, punkte: list, gross: str = "",
                 stand: str = "", sekunden: float = 0.0) -> None:
        """Inhalt setzen und aufklappen.

        sekunden=0 heisst: bleibt stehen, bis jemand sie wegnimmt. Das ist
        die Vorgabe fuer Zustands-Kacheln -- ein laufender Auftrag hoert
        ja nicht nach 45 Sekunden auf zu laufen.
        """
        self.kopf = str(kopf or "")
        self.punkte = [self._punkt(x) for x in (punkte or [])]
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
        """Eine Zeile hervorheben -- spaeter das, was er gerade sagt."""
        self.hervor = int(zeile)
        self.update()

    # --- Groesse und Ort --------------------------------------------------

    def _masse_setzen(self) -> None:
        """Hoehe aus dem Inhalt, Breite fest.

        setFixedSize und nicht resize, aus demselben Grund wie in hud.py:
        Beim Ueberqueren einer DPI-Grenze rechnet Qt die Fenstergroesse
        sonst jedes Mal neu um, und das schaukelt sich auf.
        """
        hoehe = RAND + 16                      # Kopfzeile
        if self.gross:
            hoehe += 30
        hoehe += len(self.punkte) * ZEILE
        if self.stand:
            hoehe += 16
        hoehe += RAND
        self._hoehe = hoehe
        self.setFixedSize(round(BREITE * SKALA), round(hoehe * SKALA))

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
        kasten = QRectF(0.5, 0.5, BREITE - 1, self._hoehe - 1)
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
        p.drawLine(QPointF(0, 1), QPointF(BREITE, 1))

    def _kopfzeile(self, p, farbe, y: float) -> float:
        f = QFont("Segoe UI", 7)
        f.setLetterSpacing(QFont.PercentageSpacing, 160)
        f.setCapitalization(QFont.AllUppercase)
        p.setFont(f)
        c = QColor(farbe)
        c.setAlphaF(0.95)
        self._beschriften(p, QRectF(RAND, y, BREITE - 2 * RAND, 15),
                          Qt.AlignLeft, self.kopf, c)

        if self.sorte == "zustand":
            # Ein wandernder Punkt, wie in der Hintergrund-Ecke: Eine
            # stehende Zeile sieht aus wie eine haengengebliebene.
            schritt = 0.5 + 0.5 * math.sin(self._tick * 2.2)
            punkt = QColor(farbe)
            punkt.setAlphaF(0.25 + 0.70 * schritt)
            p.setPen(Qt.NoPen)
            p.setBrush(punkt)
            p.drawEllipse(QPointF(BREITE - RAND - 3, y + 7), 2.6, 2.6)
        return y + 18

    def _grosse_zahl(self, p, farbe, y: float) -> float:
        f = QFont("Segoe UI", 17)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        c = QColor(farbe)
        c.setAlphaF(0.98)
        self._beschriften(p, QRectF(RAND, y, BREITE - 2 * RAND, 30),
                          Qt.AlignLeft | Qt.AlignVCenter, self.gross, c)
        return y + 30

    def _datenzeilen(self, p, farbe, y: float) -> float:
        p.setFont(QFont("Segoe UI", 7))
        mass = QFontMetrics(p.font())
        wertbreite = 78
        platz = BREITE - 2 * RAND - wertbreite - 6

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
            voll = QRectF(RAND - 4, y - 1, BREITE - 2 * RAND + 8, ZEILE - 1)

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
                    p, QRectF(BREITE - RAND - wertbreite, y, wertbreite,
                              ZEILE - 1),
                    Qt.AlignRight, punkt["wert"], c)
            y += ZEILE
        return y

    def _fusszeile(self, p, farbe, y: float) -> None:
        f = QFont("Segoe UI", 6)
        f.setLetterSpacing(QFont.PercentageSpacing, 130)
        p.setFont(f)
        # Blasser als alles andere, aber da. Der Zeitstempel ist die
        # Antwort auf "steht da noch der Wert von vorgestern?" -- ohne ihn
        # veraltet eine Kachel stillschweigend.
        c = QColor(farbe)
        c.setAlphaF(0.45)
        self._beschriften(p, QRectF(RAND, y + 2, BREITE - 2 * RAND, 14),
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
