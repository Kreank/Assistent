"""Die Anzeige. Eigener Prozess, hoert auf UDP, malt den Zustand.

Rahmenlos, durchsichtig, immer oben und klick-durchlaessig -- das Fenster
liegt ueber allem, faengt aber keine Maus ab. Wenn es abstuerzt, laeuft
Sarvis unbeirrt weiter; die Optik ist bewusst nichts, worauf die Schleife
warten muss.

Aufbau: in der Mitte ein Ring, der ausschlaegt -- beim Zuhoeren mit deiner
Stimme, beim Sprechen mit seiner. Aussen herum der Werkzeugkranz.
"""
import json
import math
import sys
from collections import deque

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QPainter,
    QPen,
    QRadialGradient,
)
from PySide6.QtNetwork import QHostAddress, QUdpSocket
from PySide6.QtWidgets import QApplication, QWidget

from . import config
from .anzeige import ADRESSE, DENKT, FRAGT, HOERT, RUHIG, SPRICHT

BREITE, HOEHE = 660, 548
MITTE = QPointF(BREITE / 2, 222)
RADIUS = 58
KRANZ = 176              # Abstand der Werkzeuge von der Mitte
BALKEN = 72              # Striche rund um den Ring
VERLAUF_LAENGE = BALKEN // 2

FARBEN = {
    RUHIG: QColor(126, 158, 200),
    HOERT: QColor(0, 229, 255),
    DENKT: QColor(180, 124, 255),
    SPRICHT: QColor(255, 179, 71),
    FRAGT: QColor(255, 120, 140),   # anders als alles andere:
                                    # hier wartet er auf DICH
}
BESCHRIFTUNG = {
    RUHIG: "bereit",
    HOERT: "hört zu",
    DENKT: "denkt nach",
    SPRICHT: "spricht",
    FRAGT: "wartet auf dich",
}
# Wie sichtbar das Ganze im jeweiligen Zustand ist -- einstellbar in config.py.
# Im Ruhezustand zurueckgenommen, aber klar da: sonst haelt man es fuer
# abgestuerzt, und genau das ist schon passiert.
DECKKRAFT = {
    RUHIG: config.DECKKRAFT_RUHIG,
    HOERT: config.DECKKRAFT_AKTIV,
    DENKT: config.DECKKRAFT_AKTIV,
    SPRICHT: config.DECKKRAFT_AKTIV,
    FRAGT: config.DECKKRAFT_AKTIV,
}


class Hud(QWidget):
    def __init__(self, lauschen: bool = True):
        """lauschen=False: nur malen, keinen Port belegen (fuers Rendern)."""
        super().__init__()
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.resize(BREITE, HOEHE)
        self._platzieren()

        self.zustand = RUHIG
        self.verlauf = deque([0.0] * VERLAUF_LAENGE, maxlen=VERLAUF_LAENGE)
        self.pegel = 0.0
        self.geglaettet = 0.0
        self.deckkraft = DECKKRAFT[RUHIG]
        self.tick = 0.0
        self.wer = ""
        self.untertitel = ""
        self.hervor = 0.0        # Sekunden, die wir voll sichtbar bleiben
        self.nachhoeren = 0.0    # Sekunden, in denen kein Weckwort noetig ist
        self.nachhoeren_ganz = 1.0
        self.verschiebbar = False  # Verschiebemodus?
        self._griff = None         # Mausversatz beim Ziehen
        # Name -> (Zustand, Aufleuchten 0..1)
        self.werkzeuge = {n: [z, 0.0] for n, z in config.WERKZEUGE}
        self.reihenfolge = [n for n, _ in config.WERKZEUGE]

        self.sock = QUdpSocket(self) if lauschen else None
        if lauschen and not self.sock.bind(QHostAddress("127.0.0.1"), ADRESSE[1]):
            # Laeuft schon eine Anzeige, wuerde diese hier stumm danebenstehen
            # und die alte weitermalen. Lieber laut abbrechen als still falsch.
            raise SystemExit(
                f"Port {ADRESSE[1]} ist belegt -- es laeuft bereits eine Anzeige."
            )
        if lauschen:
            self.sock.readyRead.connect(self._lesen)

        self.uhr = QTimer(self)
        self.uhr.timeout.connect(self._schlag)
        self.uhr.start(16)  # ~60 Bilder je Sekunde

    def _platzieren(self):
        """Gemerkte Position, sonst unten mittig."""
        try:
            gemerkt = json.loads(config.ANZEIGE_DATEI.read_text(encoding="utf-8"))
            x, y = int(gemerkt["x"]), int(gemerkt["y"])
            # Nicht ausserhalb aller Bildschirme landen -- sonst ist die
            # Anzeige unsichtbar und man haelt sie fuer kaputt.
            for schirm in QGuiApplication.screens():
                g = schirm.availableGeometry()
                if g.contains(x + BREITE // 2, y + 60):
                    self.move(x, y)
                    return
        except (OSError, ValueError, KeyError, TypeError):
            pass
        flaeche = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            flaeche.center().x() - BREITE // 2,
            flaeche.bottom() - HOEHE + 12,
        )

    def _position_merken(self):
        try:
            config.ANZEIGE_DATEI.write_text(
                json.dumps({"x": self.x(), "y": self.y()}), encoding="utf-8"
            )
        except OSError:
            pass

    # --- Verschiebemodus ---------------------------------------------------

    def _verschiebemodus(self, an: bool):
        """Klickdurchlaessigkeit voruebergehend abschalten.

        Normalerweise faengt die Anzeige keine Maus ab -- man arbeitet durch
        sie hindurch. Zum Verschieben muss sie das kurz koennen, sonst gibt
        es nichts zum Anfassen.
        """
        if an == self.verschiebbar:
            return
        self.verschiebbar = an
        self.setWindowFlag(Qt.WindowTransparentForInput, not an)
        self.show()   # Windows uebernimmt geaenderte Flags erst beim Zeigen
        if not an:
            self._position_merken()
            self._griff = None
        self.hervor = 3.0
        self.update()

    def mousePressEvent(self, e):
        if self.verschiebbar and e.button() == Qt.LeftButton:
            self._griff = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self.verschiebbar and self._griff is not None:
            self.move(e.globalPosition().toPoint() - self._griff)
            e.accept()

    def mouseReleaseEvent(self, e):
        if self.verschiebbar:
            self._position_merken()
            e.accept()

    # --- Eingang -----------------------------------------------------------

    def _lesen(self):
        while self.sock.hasPendingDatagrams():
            d = self.sock.receiveDatagram()
            try:
                m = json.loads(bytes(d.data()).decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                continue
            art = m.get("art")
            if art == "zustand":
                neu = m.get("zustand", RUHIG)
                if neu != self.zustand:
                    self.zustand = neu
                    if neu == HOERT:
                        self.verlauf.extend([0.0] * VERLAUF_LAENGE)
                        self.untertitel = ""
            elif art == "pegel":
                self.pegel = max(0.0, min(1.0, m.get("pegel", 0.0)))
            elif art == "untertitel":
                self.wer = m.get("wer", "")
                self.untertitel = m.get("text", "")
                # Auch im Ruhezustand kurz aufblenden -- sonst steht die
                # Begruessung beim Start in einem Fenster, das man nicht sieht.
                self.hervor = 4.0
            elif art == "verschieben":
                self._verschiebemodus(bool(m.get("an")))
            elif art == "nachhoeren":
                self.nachhoeren = float(m.get("sekunden") or 0.0)
                self.nachhoeren_ganz = max(0.1, self.nachhoeren)
            elif art == "werkzeug":
                eintrag = self.werkzeuge.get(m.get("name", ""))
                if eintrag and m.get("aktiv"):
                    eintrag[1] = 1.0

    def _schlag(self):
        self.tick += 0.016
        # Traeges Nachziehen: schnell hoch, langsam runter -- sonst zappelt es.
        ziel = self.pegel
        k = 0.45 if ziel > self.geglaettet else 0.12
        self.geglaettet += (ziel - self.geglaettet) * k
        if self.zustand in (HOERT, SPRICHT):
            self.verlauf.append(self.geglaettet)
        else:
            self.verlauf.append(self.verlauf[-1] * 0.85)

        self.hervor = max(0.0, self.hervor - 0.016)
        self.nachhoeren = max(0.0, self.nachhoeren - 0.016)
        ziel_deck = DECKKRAFT[self.zustand]
        if self.hervor > 0.0:
            ziel_deck = max(ziel_deck, 0.97)
        self.deckkraft += (ziel_deck - self.deckkraft) * 0.10
        for eintrag in self.werkzeuge.values():
            eintrag[1] *= 0.975  # Aufleuchten klingt langsam ab
        self.update()

    # --- Malen -------------------------------------------------------------

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setOpacity(self.deckkraft)
        farbe = FARBEN[self.zustand]

        # Solange das Nachhoerfenster laeuft, faerbt sich der ruhige Ring
        # schwach in die Zuhoer-Farbe -- man sieht aus dem Augenwinkel, ob
        # ein "Hey Sarvis" noetig ist oder nicht.
        if self.zustand == RUHIG and self.nachhoeren > 0.0:
            anteil = 0.30 + 0.35 * (self.nachhoeren / self.nachhoeren_ganz)
            farbe = self._mischen(FARBEN[RUHIG], FARBEN[HOERT], anteil)

        atem = 0.5 + 0.5 * math.sin(self.tick * 1.6)
        staerke = (
            self.geglaettet if self.zustand in (HOERT, SPRICHT) else atem * 0.25
        )

        self._untergrund(p, staerke)
        self._kranz(p, farbe)
        self._schein(p, farbe, staerke)
        if self.zustand in (DENKT, FRAGT):
            self._boegen(p, farbe)
        else:
            self._balken(p, farbe)
        self._ring(p, farbe, staerke)
        self._kern(p, farbe, staerke)
        self._text(p, farbe)
        if self.verschiebbar:
            self._verschiebe_hinweis(p)

    def _verschiebe_hinweis(self, p):
        p.setOpacity(1.0)
        rahmen = QColor(120, 210, 255, 190)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(rahmen, 2, Qt.DashLine))
        p.drawRoundedRect(QRectF(6, 6, BREITE - 12, HOEHE - 12), 14, 14)
        f = QFont("Segoe UI", 10, QFont.DemiBold)
        p.setFont(f)
        self._beschriften(
            p, QRectF(0, 14, BREITE, 22), Qt.AlignHCenter,
            "Ziehen zum Verschieben — Tastenkombination erneut = festmachen",
            QColor(190, 232, 255, 235),
        )

    @staticmethod
    def _beschriften(p, kasten, ausrichtung, text, farbe):
        """Schrift mit dunklem Saum.

        Ein Overlay liegt mal auf schwarzem Editor, mal auf weissem
        Explorer. Helle Schrift allein ist im zweiten Fall unlesbar --
        egal wie hoch die Deckkraft steht. Der Saum loest das dort, wo das
        Problem sitzt, statt alles heller zu drehen.
        """
        saum = QColor(4, 8, 16)
        saum.setAlphaF(0.55 * farbe.alphaF())
        p.setPen(saum)
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (1, 1)):
            p.drawText(kasten.translated(dx, dy), ausrichtung, text)
        p.setPen(farbe)
        p.drawText(kasten, ausrichtung, text)

    @staticmethod
    def _mischen(a: QColor, b: QColor, anteil: float) -> QColor:
        anteil = max(0.0, min(1.0, anteil))
        return QColor(
            int(a.red() + (b.red() - a.red()) * anteil),
            int(a.green() + (b.green() - a.green()) * anteil),
            int(a.blue() + (b.blue() - a.blue()) * anteil),
        )

    def _untergrund(self, p, staerke):
        """Weicher dunkler Grund. Ohne den verschwindet die Schrift auf
        hellem Untergrund -- ein Overlay muss auf jedem Fenster lesbar sein."""
        r = KRANZ * 1.85
        g = QRadialGradient(MITTE, r)
        for stelle, alpha in ((0.0, 178), (0.45, 146), (0.72, 74), (1.0, 0)):
            g.setColorAt(stelle, QColor(6, 10, 20, int(alpha * (0.8 + 0.2 * staerke))))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(MITTE, r, r * 0.92)

    def _kranz(self, p, farbe):
        """Die Werkzeuge rundherum, oben beginnend im Uhrzeigersinn."""
        anzahl = len(self.reihenfolge)
        if not anzahl:
            return
        schrift = QFont("Segoe UI", 8)
        schrift.setLetterSpacing(QFont.PercentageSpacing, 130)
        schrift.setCapitalization(QFont.AllUppercase)
        p.setFont(schrift)
        mass = QFontMetrics(schrift)

        for i, name in enumerate(self.reihenfolge):
            lage, glut = self.werkzeuge[name]
            winkel = -math.pi / 2 + 2 * math.pi * i / anzahl
            ci, si = math.cos(winkel), math.sin(winkel)
            punkt = QPointF(MITTE.x() + ci * KRANZ, MITTE.y() + si * KRANZ)

            grund = (config.WERKZEUG_BEREIT if lage == "bereit"
                     else config.WERKZEUG_GEPLANT)
            kraft = min(1.0, grund + glut * 0.9)

            f = QColor(farbe if (lage == "bereit" or glut > 0.02)
                       else QColor(150, 168, 196))
            f.setAlphaF(kraft)

            # Speiche nach innen
            s = QColor(f)
            s.setAlphaF(kraft * 0.35)
            p.setPen(QPen(s, 1.0))
            p.drawLine(
                QPointF(MITTE.x() + ci * (KRANZ - 26), MITTE.y() + si * (KRANZ - 26)),
                QPointF(MITTE.x() + ci * (KRANZ - 12), MITTE.y() + si * (KRANZ - 12)),
            )

            # Punkt
            r = 2.6 + glut * 3.0
            p.setPen(Qt.NoPen)
            p.setBrush(f)
            p.drawEllipse(punkt, r, r)

            # Beschriftung, nach aussen versetzt
            breite = mass.horizontalAdvance(name) + 16
            kasten = QRectF(
                punkt.x() + ci * (breite / 2 + 9) - breite / 2,
                punkt.y() + si * 15 - 8,
                breite,
                16,
            )
            self._beschriften(p, kasten, Qt.AlignCenter, name, f)

    def _schein(self, p, farbe, staerke):
        r = RADIUS * (2.6 + staerke * 0.8)
        g = QRadialGradient(MITTE, r)
        innen = QColor(farbe)
        innen.setAlphaF(0.20 + 0.28 * staerke)
        mitte = QColor(farbe)
        mitte.setAlpha(int(40 * (0.4 + staerke)))
        aussen = QColor(farbe)
        aussen.setAlpha(0)
        g.setColorAt(0.0, innen)
        g.setColorAt(0.45, mitte)
        g.setColorAt(1.0, aussen)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(MITTE, r, r)

    def _balken(self, p, farbe):
        """Striche rund um den Ring, gespiegelt -- wie eine Welle im Kreis."""
        werte = list(self.verlauf)
        for i in range(BALKEN):
            # Spiegelung an der Senkrechten: links und rechts gleich
            idx = i if i < VERLAUF_LAENGE else BALKEN - 1 - i
            wert = werte[max(0, min(len(werte) - 1, idx))]
            winkel = -math.pi / 2 + (2 * math.pi * i / BALKEN)
            laenge = 5 + wert * 46
            ci, si = math.cos(winkel), math.sin(winkel)
            a1 = QPointF(
                MITTE.x() + ci * (RADIUS + 7), MITTE.y() + si * (RADIUS + 7)
            )
            a2 = QPointF(
                MITTE.x() + ci * (RADIUS + 7 + laenge),
                MITTE.y() + si * (RADIUS + 7 + laenge),
            )
            f = QColor(farbe)
            f.setAlphaF(0.30 + 0.55 * min(1.0, wert * 1.6))
            p.setPen(QPen(f, 2.2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(a1, a2)

    def _boegen(self, p, farbe):
        """Denkzustand: drei Boegen mit verschiedenen Geschwindigkeiten."""
        ringe = (
            (RADIUS + 16, 1.0, 110),
            (RADIUS + 28, -0.7, 70),
            (RADIUS + 40, 0.45, 40),
        )
        for i, (r, tempo, spanne) in enumerate(ringe):
            f = QColor(farbe)
            f.setAlphaF(0.55 - i * 0.13)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(f, 2.4, Qt.SolidLine, Qt.RoundCap))
            kasten = QRectF(MITTE.x() - r, MITTE.y() - r, r * 2, r * 2)
            start = int((self.tick * tempo * 200) % 360)
            p.drawArc(kasten, start * 16, spanne * 16)

    def _ring(self, p, farbe, staerke):
        r = RADIUS + staerke * 5
        f = QColor(farbe)
        f.setAlphaF(0.85)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(f, 2.0))
        p.drawEllipse(MITTE, r, r)

    def _kern(self, p, farbe, staerke):
        r = 6 + staerke * 9
        g = QRadialGradient(MITTE, r * 2.2)
        innen = QColor(farbe)
        innen.setAlphaF(0.9)
        aussen = QColor(farbe)
        aussen.setAlpha(0)
        g.setColorAt(0.0, innen)
        g.setColorAt(1.0, aussen)
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(MITTE, r * 2.2, r * 2.2)
        p.setBrush(QColor(235, 245, 255, 230))
        p.drawEllipse(MITTE, r * 0.45, r * 0.45)

    def _text(self, p, farbe):
        wort = BESCHRIFTUNG.get(self.zustand, "")
        if self.zustand == RUHIG and self.nachhoeren > 0.0:
            wort = "hört noch zu"
        if wort:
            f = QFont("Segoe UI", 8)
            f.setLetterSpacing(QFont.PercentageSpacing, 200)
            f.setCapitalization(QFont.AllUppercase)
            p.setFont(f)
            c = QColor(farbe)
            c.setAlphaF(0.92)
            self._beschriften(
                p, QRectF(0, MITTE.y() + RADIUS + 74, BREITE, 18),
                Qt.AlignHCenter, wort, c,
            )

        if self.untertitel:
            p.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
            if self.wer == "du":
                c = QColor(232, 241, 253, 240)
            else:
                c = QColor(farbe)
                c.setAlphaF(0.92)
            y = MITTE.y() + KRANZ + 34
            self._beschriften(
                p, QRectF(70, y, BREITE - 140, HOEHE - y - 8),
                Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap,
                self.untertitel, c,
            )


def _eltern_wache(app, pid: int):
    """Beendet die Anzeige, sobald Sarvis weg ist.

    Ohne das bleibt bei einem zugeklappten Konsolenfenster eine verwaiste
    Anzeige zurueck und blockiert mit ihrem Port den naechsten Start.

    Bewusst ueber OpenProcess/WaitForSingleObject und nicht ueber os.kill:
    os.kill wuerde auf Windows TerminateProcess aufrufen und den Eltern-
    prozess tatsaechlich abschiessen, statt nur nachzusehen.
    """
    if sys.platform != "win32" or not pid:
        return None
    import ctypes

    SYNCHRONIZE = 0x00100000
    WAIT_OBJECT_0 = 0x0
    kernel = ctypes.windll.kernel32
    griff = kernel.OpenProcess(SYNCHRONIZE, False, pid)
    if not griff:
        app.quit()
        return None

    def nachsehen():
        if kernel.WaitForSingleObject(griff, 0) == WAIT_OBJECT_0:
            app.quit()

    wache = QTimer(app)
    wache.timeout.connect(nachsehen)
    wache.start(1500)
    return wache


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    eltern = 0
    if "--eltern" in sys.argv:
        try:
            eltern = int(sys.argv[sys.argv.index("--eltern") + 1])
        except (IndexError, ValueError):
            eltern = 0
    hud = Hud()
    hud.show()
    _wache = _eltern_wache(app, eltern)  # noqa: F841 -- am Leben halten
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
