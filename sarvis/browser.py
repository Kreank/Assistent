"""Ein Browser in der Engine -- statt eines Fensters daneben.

Warum ueberhaupt: Es gibt Dinge, die eine handgemalte Kachel nie so gut
zeigen wird wie das echte Programm. Eine Kalender-Monatsansicht in 250
Rasterpunkte zu malen waere schlechter als Google Kalender selbst. Ein
PDF, ein Drive-Dokument, ein Rechercheergebnis -- alles das kann eine
Seite besser.

Damit ergibt sich die Trennlinie, die es vorher nicht gab:

    Die Kachel ist fuer den Blick nebenbei.
    Der Browser ist fuers Hinsetzen.

Und ein zweiter Grundsatz bleibt gueltig: Sarvis bringt die Seite, DU
bedienst sie. Er kann hierher navigieren -- klicken, tippen und
abschicken tust du. Damit laeuft nichts an der Rueckfrage vorbei, denn
eine Seite anzuzeigen ist keine Handlung an der Aussenwelt.

DREI UNTERSCHIEDE ZU DEN KACHELN, alle drei mit Absicht:

  Er nimmt Eingaben an. Kacheln sind klickdurchlaessig
  (WindowTransparentForInput), damit man durch sie hindurcharbeitet. Ein
  Browser, den man bedienen soll, kann das nicht sein.

  Er ist undurchsichtig. Text auf einer fremden Seite ueber einem
  durchscheinenden Grund ist unlesbar, und anders als bei einer Kachel
  koennen wir den Kontrast nicht selbst bestimmen.

  Er ist groesser zu ziehen. Feste Groessen sind fuer Anzeigen richtig,
  fuer Inhalte nicht.

EIGENES PROFIL, EIGENE ANMELDUNG: Dies ist nicht dein Chrome. Der
Cookie-Speicher liegt getrennt unter BROWSER_PROFIL, also musst du dich
beim ersten Mal hier anmelden, auch wenn du nebenan laengst angemeldet
bist. Danach bleibt es -- geprueft, das Profil steht auf
AllowPersistentCookies. Der Ordner gehoert NICHT ins Repository.
"""
from PySide6.QtCore import QPoint, QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWebEngineCore import QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QSizeGrip, QVBoxLayout, QWidget

from . import config

# Kopfleiste: hier steht der Seitentitel, und hier fasst man zum
# Verschieben an. Hoehe in Bildschirmpunkten, nicht im Kachelraster --
# der Browser rechnet nicht in dem gemalten Raster, weil sein Inhalt
# nicht von uns gemalt wird.
KOPF = 30
RAHMEN = QColor(0, 229, 255)      # dieselbe Farbe wie "hoert" in hud.py
GRUND = QColor(8, 13, 20)


class Browser(QWidget):
    """Eine Seite, die Sarvis bringt und du bedienst."""

    _profil = None   # EIN Profil fuer alle Fenster -- siehe _profil_holen

    def __init__(self):
        super().__init__()
        # Kein WindowTransparentForInput und kein WA_TranslucentBackground:
        # beides waere hier falsch, siehe Modulkopf.
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("Sarvis")
        self.setMinimumSize(420, 320)
        self.resize(config.BROWSER_BREITE, config.BROWSER_HOEHE)

        self._titel = ""
        self._griff = None      # Mausversatz beim Verschieben

        self.ansicht = QWebEngineView(self)
        self.ansicht.page().setBackgroundColor(QColor(255, 255, 255))
        self.ansicht.titleChanged.connect(self._titel_setzen)

        lage = QVBoxLayout(self)
        lage.setContentsMargins(1, KOPF, 1, 1)
        lage.setSpacing(0)
        lage.addWidget(self.ansicht)

        # Anfasser unten rechts. Ein rahmenloses Fenster hat sonst keine
        # Kante, an der Windows die Groesse aendern liesse -- und
        # groesser ziehen zu koennen war der ganze Punkt.
        self._anfasser = QSizeGrip(self)
        self._anfasser.setFixedSize(16, 16)

    # --- Profil -----------------------------------------------------------

    @classmethod
    def _profil_holen(cls) -> QWebEngineProfile:
        """Das gemeinsame, dauerhafte Profil.

        Als Klassenattribut und nicht je Fenster, aus zwei Gruenden:
        Anmeldungen sollen ueber Fenster hinweg gelten, und ein Profil,
        das eingesammelt wird, waehrend eine Seite es noch benutzt,
        nimmt die Seite mit -- das ist der klassische Absturz in
        PySide6. Eine Kennung an der Klasse haelt es am Leben.
        """
        if cls._profil is None:
            config.BROWSER_PROFIL.mkdir(parents=True, exist_ok=True)
            profil = QWebEngineProfile("sarvis")
            profil.setPersistentStoragePath(str(config.BROWSER_PROFIL))
            profil.setCachePath(str(config.BROWSER_PROFIL / "cache"))
            profil.setPersistentCookiesPolicy(
                QWebEngineProfile.AllowPersistentCookies)
            cls._profil = profil
        return cls._profil

    # --- zeigen -----------------------------------------------------------

    def zeigen(self, adresse: str, anker=None) -> None:
        """Eine Seite laden und das Fenster hervorholen."""
        if anker is not None and not self.isVisible():
            self._neben(anker)
        self.ansicht.setUrl(QUrl(adresse))
        self.show()
        self.raise_()

    def _neben(self, anker) -> None:
        """Beim ERSTEN Zeigen mittig ueber der Engine aufstellen.

        Nur beim ersten Mal: Wer das Fenster einmal geschoben oder
        groesser gezogen hat, will es beim naechsten Zuruf dort wieder
        finden -- eine Anzeige, die selbsttaetig zurueckspringt, ist
        aergerlicher als eine, die falsch steht.
        """
        from PySide6.QtGui import QGuiApplication
        mitte = anker.center()
        schirm = None
        for s in QGuiApplication.screens():
            if s.geometry().contains(mitte):
                schirm = s
                break
        frei = (schirm or QGuiApplication.primaryScreen()).availableGeometry()
        x = mitte.x() - self.width() // 2
        y = mitte.y() - self.height() // 2
        x = max(frei.left(), min(x, frei.right() - self.width()))
        y = max(frei.top(), min(y, frei.bottom() - self.height()))
        self.move(x, y)

    def _titel_setzen(self, titel: str) -> None:
        self._titel = str(titel or "")
        self.update()

    # --- Bedienen ---------------------------------------------------------

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._anfasser.move(self.width() - 17, self.height() - 17)

    def mousePressEvent(self, e):
        # Nur die Kopfleiste ist zum Anfassen da. Weiter unten liegt die
        # Seite, und dort gehoert der Klick der Seite.
        if e.position().y() <= KOPF:
            self._griff = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e):
        if self._griff is not None:
            self.move(e.globalPosition().toPoint() - self._griff)

    def mouseReleaseEvent(self, _e):
        self._griff = None

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self.hide()

    # --- Malen ------------------------------------------------------------

    def paintEvent(self, _):
        """Nur Rahmen und Kopfleiste -- den Rest malt Chromium."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        p.setPen(Qt.NoPen)
        p.setBrush(GRUND)
        p.drawRect(0, 0, self.width(), KOPF)

        rahmen = QColor(RAHMEN)
        rahmen.setAlphaF(0.55)
        p.setPen(QPen(rahmen, 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1))

        f = QFont("Segoe UI", 8)
        f.setLetterSpacing(QFont.PercentageSpacing, 120)
        p.setFont(f)
        c = QColor(RAHMEN)
        c.setAlphaF(0.92)
        p.setPen(c)
        p.drawText(QRectF(12, 0, self.width() - 150, KOPF),
                   Qt.AlignLeft | Qt.AlignVCenter, self._titel or "lädt …")

        hinweis = QColor(RAHMEN)
        hinweis.setAlphaF(0.42)
        p.setPen(hinweis)
        p.setFont(QFont("Segoe UI", 7))
        p.drawText(QRectF(self.width() - 140, 0, 128, KOPF),
                   Qt.AlignRight | Qt.AlignVCenter, "Esc schließt")


def bauen() -> Browser:
    """Ein Fenster mit dem gemeinsamen Profil.

    Das Profil muss VOR der Seite stehen: Eine QWebEnginePage bekommt ihr
    Profil bei der Erzeugung und laesst es sich nachtraeglich nicht mehr
    austauschen.
    """
    from PySide6.QtWebEngineCore import QWebEnginePage

    fenster = Browser()
    seite = QWebEnginePage(Browser._profil_holen(), fenster)
    seite.setBackgroundColor(QColor(255, 255, 255))
    fenster.ansicht.setPage(seite)
    seite.titleChanged.connect(fenster._titel_setzen)
    return fenster
