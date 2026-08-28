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
import socket
import sys
import threading
from collections import deque

from PySide6.QtCore import QPointF, QRect, QRectF, QSize, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
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
from .kachel import Kachel

# Das Raster, in dem gemalt wird. Alles darunter rechnet in diesen
# Zahlen -- sie sind KEINE Bildschirmpixel mehr, seit es SKALA gibt.
BREITE, HOEHE = 660, 548
# Wie gross das Fenster daraus wird. Der Maler wird gestreckt, nicht die
# Konstanten: sonst muesste man zwei Dutzend Abstaende einzeln nachziehen.
SKALA = max(0.6, min(3.0, config.ANZEIGE_SKALA))
FENSTER_BREITE = round(BREITE * SKALA)
FENSTER_HOEHE = round(HOEHE * SKALA)
MITTE = QPointF(BREITE / 2, 222)
RADIUS = 58
KRANZ = 176              # Abstand der Werkzeuge von der Mitte
BALKEN = 72              # Striche rund um den Ring
ICON_PIXEL = 17          # Kantenlaenge der Werkzeug-Zeichen im Malraster
# In dieser Reihenfolge gesucht: Windows 11 bringt die erste mit, Windows
# 10 die zweite -- die Zeichencodes sind dieselben.
ICON_SCHRIFTEN = ("Segoe Fluent Icons", "Segoe MDL2 Assets")
VERLAUF_LAENGE = BALKEN // 2

# Wie viel vom Fenster ringsum durchsichtiger Rand ist. Das Fenster ist
# 660x548 Rasterpunkte gross, der Kranz samt Beschriftung nutzt davon nur
# die Mitte. Wer eine Kachel an der FENSTERkante ausrichtet, setzt sie
# scheinbar grundlos weit weg -- abgemessen am gerenderten Bild.
# Browser-Fragen, die ueber JavaScript laufen und deshalb einen eigenen
# Faden brauchen -- so steht es im Vertrag von browser.py.
_WEB_MIT_JS = ("web_lesen", "web_elemente", "web_element",
               "web_klicken", "web_tippen")

# Eine Antwort und kein leeres Ergebnis: "kein Fenster offen" ist etwas
# anderes als "die Seite ist leer", und nur eine der beiden Auskuenfte
# hilft weiter.
_KEIN_BROWSER = {"ok": False, "grund": "Es ist gerade keine Seite offen."}

SICHTBAR_EINZUG_X = 70
SICHTBAR_EINZUG_Y = 14


def _icon_schrift():
    """Die vorhandene Icon-Schrift -- oder None.

    Erst zur Laufzeit zu beantworten: QFontDatabase braucht eine laufende
    QApplication, beim Import gibt es die noch nicht. Fehlt beides, malt
    der Kranz wieder Punkte statt Zeichen -- lieber schlichter als leer.
    """
    vorhanden = set(QFontDatabase.families())
    for name in ICON_SCHRIFTEN:
        if name in vorhanden:
            return name
    return None

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
        # Feste Groesse, nicht resize(): Beim Ueberqueren einer
        # Skalierungsgrenze rechnet Qt die Fenstergroesse sonst mit dem
        # DPI-Verhaeltnis um -- und zwar jedes Mal neu. Siehe
        # _schirm_gewechselt.
        self.setFixedSize(FENSTER_BREITE, FENSTER_HOEHE)
        self._platzieren()
        # winId() erzwingt das Fenster, sonst gibt es noch kein
        # windowHandle, an dem der Bildschirmwechsel haengen koennte.
        self.winId()
        if self.windowHandle() is not None:
            self.windowHandle().screenChanged.connect(self._schirm_gewechselt)

        self.zustand = RUHIG
        self.verlauf = deque([0.0] * VERLAUF_LAENGE, maxlen=VERLAUF_LAENGE)
        self.pegel = 0.0
        self.geglaettet = 0.0
        self.deckkraft = DECKKRAFT[RUHIG]
        self.tick = 0.0
        self.wer = ""
        self.untertitel = ""
        # Was davon in den Kasten passt, und wozu es gerechnet wurde --
        # siehe _untertitel_passend().
        self._untertitel_quelle = ""
        self._untertitel_passt = ""
        self.hervor = 0.0        # Sekunden, die wir voll sichtbar bleiben
        self.nachhoeren = 0.0    # Sekunden, in denen kein Weckwort noetig ist
        self.nachhoeren_ganz = 1.0
        # Was gerade ohne Rueckfrage durchgeht. Steht dauerhaft da,
        # solange es gilt -- eine Freigabe, die man nicht sieht, ist
        # keine Zusage mehr, sondern eine Gewohnheit.
        self.freigabe = ""
        self.freigabe_rest = 0.0
        # Was im Hintergrund arbeitet, waehrend er still dasteht.
        self.hintergrund: list = []
        self.hg_seit = 0.0        # wie lange laeuft es schon (Sekunden)
        self.hg_fertig = False    # gerade fertig geworden?
        self.verschiebbar = False  # Verschiebemodus?
        # Kacheln, die gerade neben der Engine stehen: name -> Kachel.
        # Der Name ist die Identitaet -- zweimal "finanzen" ist dieselbe
        # Kachel mit neuem Inhalt, nicht zwei uebereinander.
        self.kacheln: dict = {}
        self._letzter_anker = None
        # Der eingebettete Browser. Erst beim ersten Zuruf gebaut: Ein
        # Chromium im Voraus zu starten kostet Hunderte Megabyte fuer
        # etwas, das an vielen Tagen niemand braucht.
        self._browser = None
        # Der zuletzt gelesene Elementstand. Siehe _web_bedienen, warum er
        # nicht bei jeder Frage neu geholt wird.
        self._elemente: list = []
        self._griff = None         # Mausversatz beim Ziehen
        # Name -> (Zustand, Aufleuchten 0..1)
        self.werkzeuge = {n: [z, 0.0] for n, z in config.WERKZEUGE}
        self.reihenfolge = [n for n, _ in config.WERKZEUGE]
        self.icon_schrift = _icon_schrift()
        # Code -> Zeichen, einmal statt sechzigmal je Sekunde.
        self.icons = {}
        for name, code in config.WERKZEUG_ICONS.items():
            try:
                self.icons[name] = chr(int(code, 16))
            except (TypeError, ValueError):
                pass

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
                if g.contains(x + FENSTER_BREITE // 2, y + round(60 * SKALA)):
                    self.move(x, y)
                    return
        except (OSError, ValueError, KeyError, TypeError):
            pass
        flaeche = QGuiApplication.primaryScreen().availableGeometry()
        self.move(
            flaeche.center().x() - FENSTER_BREITE // 2,
            flaeche.bottom() - FENSTER_HOEHE + 12,
        )

    def _schirm_gewechselt(self, _schirm=None):
        """Nach einem Bildschirmwechsel die Groesse wieder festnageln.

        Wer zwei Bildschirme mit verschiedener Skalierung hat, schiebt die
        Anzeige ueber eine DPI-Grenze. Windows meldet WM_DPICHANGED, und
        Qt rechnet die Fenstergroesse mit dem Verhaeltnis um -- aber vom
        bereits umgerechneten Wert aus. Das schaukelt sich auf. Gemessen
        auf 100 % -> 125 % und zurueck:

            660x548 -> 1031x856 -> 1289x1070 -> 2518x2091

        In der anderen Richtung geht es mit 0,8 je Uebergang nach unten,
        bis die Anzeige ganz verschwunden ist. Genau so ist es passiert.
        Die feste Groesse allein reicht nicht: Qt setzt die Schranken beim
        Umrechnen mit um. Also hier neu setzen, nach jedem Wechsel.
        """
        soll = QSize(FENSTER_BREITE, FENSTER_HOEHE)
        if self.size() != soll:
            self.setFixedSize(soll)

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
        # Auf die gehaltene Taste pruefen, nicht nur auf den Griff: sonst
        # zieht auch ein Zug mit der rechten Maustaste am Fenster.
        if (self.verschiebbar and self._griff is not None
                and (e.buttons() & Qt.LeftButton)):
            self.move(e.globalPosition().toPoint() - self._griff)
            e.accept()

    def mouseReleaseEvent(self, e):
        # Der Griff wurde beim Loslassen nicht geloescht. Nach einem
        # beendeten Zug stand der alte Versatz weiter da, und die naechste
        # Mausbewegung im Verschiebemodus sprang das Fenster damit an eine
        # falsche Stelle -- die dann auch noch gemerkt wurde.
        if self.verschiebbar and self._griff is not None:
            self._griff = None
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
            elif art == "hintergrund":
                self.hintergrund = [str(z) for z in (m.get("zeilen") or [])]
                self.hg_seit = float(m.get("seit") or 0.0)
                self.hg_fertig = bool(m.get("fertig"))
            elif art == "freigabe":
                self.freigabe = str(m.get("text") or "")
                self.freigabe_rest = float(m.get("sekunden") or 0.0)
            elif art == "werkzeug":
                eintrag = self.werkzeuge.get(m.get("name", ""))
                if eintrag and m.get("aktiv"):
                    eintrag[1] = 1.0
            elif art == "browser":
                self._browser_zeigen(str(m.get("adresse") or ""))
            elif art in _WEB_MIT_JS:
                # Diese vier gehen ueber runJavaScript und MUESSEN laut
                # browser.py aus einem Arbeitsfaden kommen -- hier laeuft
                # der Qt-Faden. Also weiterreichen. Der Browser wird noch
                # hier geholt, solange wir im richtigen Faden sind.
                threading.Thread(target=self._web_bedienen,
                                 args=(art, m, self._browser_holen()),
                                 daemon=True).start()
            elif art == "web_zoom":
                b = self._browser_holen()
                if b is None:
                    self._antworten(m, _KEIN_BROWSER)
                else:
                    self._antworten(m, {"ok": True,
                                        "faktor": b.zoom(m.get("faktor"))})
            elif art == "web_suchen":
                b = self._browser_holen()
                if b is not None:
                    b.suchen(str(m.get("text") or ""))
                self._antworten(m, {"ok": b is not None}
                                if b else _KEIN_BROWSER)
            elif art == "web_downloads":
                b = self._browser_holen()
                self._antworten(m, {"ok": True, "dateien": b.downloads()}
                                if b else _KEIN_BROWSER)
            elif art == "web_stand":
                # Was gerade offen ist. Die erste Frage ueber den
                # Rueckkanal -- und die einzige, die auch dann eine
                # sinnvolle Antwort hat, wenn gar kein Browser laeuft.
                b = self._browser_holen()
                self._antworten(m, {
                    "offen": b is not None,
                    "adresse": b.ansicht.url().toString() if b else "",
                    "titel": (b._titel if b else ""),
                })
            elif art == "browser_zu":
                if self._browser is not None:
                    self._browser.hide()
            elif art == "kachel":
                self._kachel_zeigen(m)
            elif art == "kachel_weg":
                vorhanden = self.kacheln.get(str(m.get("name", "")))
                if vorhanden is not None:
                    vorhanden.wegnehmen()

    # --- Kacheln -----------------------------------------------------------

    def _sichtbar(self) -> QRect:
        """Der sichtbare Teil der Engine, nicht ihr Fenster.

        Daran richtet sich eine Kachel aus. Der Unterschied betraegt bei
        Skala 1,3 rund neunzig Bildschirmpunkte je Seite -- genug, dass es
        aussaehe, als haette jemand die Kachel danebengelegt.
        """
        ex = round(SICHTBAR_EINZUG_X * SKALA)
        ey = round(SICHTBAR_EINZUG_Y * SKALA)
        return QRect(self.x() + ex, self.y() + ey,
                     self.width() - 2 * ex, self.height() - 2 * ey)

    def _antworten(self, m: dict, inhalt: dict) -> None:
        """Die Antwort dorthin zurueckschicken, wo die Frage herkam.

        Der Port steht in der Frage, nicht in einer Einstellung: Wer
        fragt, macht sich seinen Socket selbst auf und schliesst ihn
        wieder. Damit gibt es keinen zweiten festen Port, der belegt sein
        koennte, und keine Verbindung, die laenger lebt als die Frage.
        """
        port = m.get("antwort_an")
        if not port:
            return
        # Ein GEWOEHNLICHER Socket, nicht der QUdpSocket der Anzeige.
        # Grund: Die Browser-Antworten entstehen in einem Arbeitsfaden
        # (siehe _web_bedienen), und ein Qt-Objekt aus einem fremden Faden
        # zu benutzen ist ein Fehler, den man erst Wochen spaeter als
        # sporadischen Absturz wiedersieht. Ein Datagramm an localhost
        # braucht Qt ohnehin nicht.
        try:
            daten = json.dumps({"nummer": m.get("nummer"), **inhalt},
                               ensure_ascii=False).encode("utf-8")
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.sendto(daten, ("127.0.0.1", int(port)))
        except (OSError, ValueError, TypeError) as e:
            print(f"Antwort ging nicht raus: {type(e).__name__}: {e}")

    def _web_bedienen(self, art: str, m: dict, browser) -> None:
        """Die Browser-Fragen, die JavaScript brauchen. Im Arbeitsfaden.

        Was hier passiert, darf dauern -- eine Seite, die nicht antwortet,
        laesst das Zeitlimit von browser.py verstreichen. Genau deshalb
        laeuft es nicht im Qt-Faden: Sonst stuende waehrenddessen die
        ganze Anzeige, Ring und Kacheln eingeschlossen.
        """
        if browser is None:
            self._antworten(m, _KEIN_BROWSER)
            return
        try:
            if art == "web_lesen":
                inhalt = {"ok": True, "text": browser.text_holen()}
            elif art == "web_elemente":
                liste = browser.elemente_holen()
                # Gemerkt, damit web_element daraus antworten kann, ohne
                # die Seite neu zu lesen. Der Unterschied ist nicht
                # Bequemlichkeit: browser.klicken() vergleicht beim Klick
                # gegen den Fingerabdruck AUS DIESEM Lesen und merkt
                # dadurch, wenn sich die Seite zwischendurch geaendert
                # hat. Ein Neulesen wuerde genau diese Wache abschalten.
                self._elemente = liste
                inhalt = {"ok": True, "elemente": liste}
            elif art == "web_element":
                # Die Frage, mit der hirn.darf_ich entscheidet. Sie kommt
                # aus dem gemerkten Stand; gibt es keinen, wird einmal
                # gelesen -- lieber frisch als gar nicht.
                if not self._elemente:
                    self._elemente = browser.elemente_holen()
                nummer = m.get("nummer_element")
                treffer = next((e for e in self._elemente
                                if e.get("nummer") == nummer), {})
                inhalt = {"ok": True, "element": treffer}
            elif art == "web_klicken":
                inhalt = {"ok": True,
                          "ergebnis": browser.klicken(m.get("nummer_element"))}
            else:   # web_tippen
                inhalt = {"ok": True,
                          "ergebnis": browser.tippen(m.get("nummer_element"),
                                                     str(m.get("text") or ""))}
        except Exception as e:
            inhalt = {"ok": False,
                      "grund": f"{type(e).__name__}: {e}"}
        self._antworten(m, inhalt)

    def _browser_holen(self):
        """Den Browser liefern -- oder None, wenn keiner offen ist.

        Anders als beim Zeigen wird hier NICHT gebaut: Wer fragt, was auf
        der Seite steht, meint eine Seite, die es gibt. Ein frisch
        gestartetes, leeres Chromium waere keine Antwort.
        """
        if self._browser is None or not self._browser.isVisible():
            return None
        return self._browser

    def _browser_zeigen(self, adresse: str) -> None:
        """Seite im eingebauten Browser zeigen, ihn notfalls erst bauen.

        Scheitert das Bauen -- etwa weil PySide6-Addons fehlt --, wird das
        gemeldet und nicht verschwiegen: Ein Browser, der stumm nicht
        aufgeht, sieht aus wie ein Assistent, der die Bitte ueberhoert hat.
        """
        if not adresse:
            return
        if self._browser is None:
            try:
                from .browser import bauen
                self._browser = bauen()
            except Exception as e:
                print(f"Browser nicht verfuegbar: {type(e).__name__}: {e}")
                return
        self._browser.zeigen(adresse, self._sichtbar())

    def _kachel_zeigen(self, m: dict) -> None:
        name = str(m.get("name") or "")
        if not name:
            return
        sorte = "zustand" if m.get("sorte") == "zustand" else "antwort"
        kachel = self.kacheln.get(name)
        # Wechselt eine Kachel die Sorte, wird sie neu gebaut: Sorte
        # bestimmt Farbe und Lebensdauer, und beides nachtraeglich
        # umzustellen waere mehr Sonderfall als Nutzen.
        if kachel is not None and kachel.sorte != sorte:
            kachel.hide()
            kachel = None
        if kachel is None:
            kachel = Kachel(sorte)
            self.kacheln[name] = kachel
        kachel.platzieren_an(self._sichtbar())
        kachel.anzeigen(
            m.get("kopf") or "",
            m.get("punkte") or [],
            gross=m.get("gross") or "",
            stand=m.get("stand") or "",
            sekunden=float(m.get("sekunden") or 0.0),
            form=m.get("form") or "liste",
            spalten=tuple(m.get("spalten") or ()),
            # Wie viele Punkte der Draht abgeschnitten hat, bevor die
            # Kachel sie sah. Nur sie kann es vermerken.
            weggelassen=int(m.get("weggelassen") or 0),
        )
        # Erst jetzt anordnen: Die Hoehe steht erst fest, wenn der Inhalt
        # drin ist, und danach richtet sich der Stapel darunter.
        self._anordnen()

    def _anordnen(self) -> None:
        """Alle Kacheln neu verteilen: Antworten rechts, Zustaende links.

        Das Anordnen gehoert hierher und nicht in die einzelne Kachel:
        Nur die Engine weiss, wie viele es gerade gibt. Eine Kachel, die
        sich selbst platziert, kennt die anderen nicht -- gemessen landeten
        Antwort und Zustand auf demselben Punkt.

        Mehrere je Seite werden untereinander gestapelt. Der Regelfall
        bleibt eine je Seite; der Stapel ist dafuer da, dass ein dritter
        Kasten nicht unsichtbar unter dem zweiten verschwindet.

        ZWEI DURCHGAENGE, und das ist der Punkt: Die Sorte sagt nur, wo
        eine Kachel hin SOLL. Wo sie landet, entscheidet
        Kachel._platzieren -- passt die gewuenschte Seite nicht mehr auf
        den Schirm, klappt es auf die andere um. Wer danach nach der
        gewuenschten Seite stapelt, stapelt am falschen Ort.

        Gemessen bei der Engine auf x=3801 des Ultrawide: Bis 360
        Rasterpunkte Breite passt eine Antwort rechts (529 Pixel frei).
        Ab 500 klappt sie nach links, wo 3869 frei sind -- und lag dort
        zu 100 Prozent auf der Zustands-Kachel, weil beide den Versatz
        null ihrer je eigenen Seite trugen. Heute faellt das nicht auf:
        Die breiteste Form ist 360. Eine breite Form wie ein Fluss
        loest es sofort aus.

        Deshalb wird erst hingestellt und NACHGESEHEN, wo die Kachel
        wirklich steht, und erst im zweiten Durchgang gestapelt. Die
        Alternative waere, die Passt-das-noch-Rechnung hier zu
        wiederholen -- zwei Stellen, die dasselbe rechnen und
        auseinanderlaufen, sobald eine sich aendert.
        """
        anker = self._sichtbar()
        luft = round(10 * SKALA)
        sichtbare = [k for k in self.kacheln.values() if k.isVisible()]

        # Erster Durchgang: hinstellen und fragen, wo sie gelandet ist.
        # Links vom Anker heisst links, alles andere rechts.
        seiten = []
        for kachel in sichtbare:
            wunsch = "links" if kachel.sorte == "zustand" else "rechts"
            kachel.platzieren_an(anker, wunsch, 0)
            seiten.append("links" if kachel.x() < anker.left() else "rechts")

        # Zweiter Durchgang: nach der TATSAECHLICHEN Seite stapeln. Die
        # Seite wird jetzt ausdruecklich verlangt -- dort hat sie eben
        # gepasst, also bleibt sie auch diesmal dort.
        versatz = {"rechts": 0, "links": 0}
        for kachel, seite in zip(sichtbare, seiten):
            kachel.platzieren_an(anker, seite, versatz[seite])
            versatz[seite] += kachel.height() + luft

    def _kacheln_nachfuehren(self) -> None:
        """Die Kacheln der Engine hinterherziehen.

        Sie haengt nicht fest: Der Verschiebemodus zieht sie mit der Maus,
        und ein Bildschirmwechsel setzt sie neu. Eine Kachel, die stehen
        bleibt, wo die Engine vorhin war, sieht aus wie vergessen.

        Neu verteilt wird auch, wenn sich die ZAHL der sichtbaren Kacheln
        aendert -- sonst bleibt nach dem Ausblenden der ersten eine Luecke
        stehen, in die niemand nachrueckt.
        """
        anker = self._sichtbar()
        sichtbare = sum(1 for k in self.kacheln.values() if k.isVisible())
        stand = (anker, sichtbare)
        if stand == self._letzter_anker:
            return
        self._letzter_anker = stand
        self._anordnen()

    def _schlag(self):
        self.tick += 0.016
        self._kacheln_nachfuehren()
        # Traeges Nachziehen: schnell hoch, langsam runter -- sonst zappelt es.
        ziel = self.pegel
        k = 0.45 if ziel > self.geglaettet else 0.12
        self.geglaettet += (ziel - self.geglaettet) * k
        if self.zustand in (HOERT, SPRICHT):
            self.verlauf.append(self.geglaettet)
        else:
            # Der Weckwort-Horcher meldet seinen Pegel auch im Ruhezustand.
            # Vorher klang der Verlauf hier nur ab, egal wie laut jemand
            # redete -- man sah dem Ring nie an, ob er einen hoert.
            self.verlauf.append(max(self.geglaettet, self.verlauf[-1] * 0.85))

        self.hervor = max(0.0, self.hervor - 0.016)
        self.nachhoeren = max(0.0, self.nachhoeren - 0.016)
        if self.freigabe:
            self.freigabe_rest -= 0.016
            if self.freigabe_rest <= 0.0:
                self.freigabe = ""
        ziel_deck = DECKKRAFT[self.zustand]
        if self.hervor > 0.0:
            # Hier stand die 0.97 ein zweites Mal hart im Code -- zufaellig
            # derselbe Wert wie DECKKRAFT_RUHIG, weshalb das Aufblenden gar
            # nichts tat. Wer DECKKRAFT_RUHIG in config.py absenkt, haette
            # ausserdem still die Kopplung verloren: gemeint war immer
            # "kurz voll sichtbar", also der Aktiv-Wert.
            ziel_deck = max(ziel_deck, config.DECKKRAFT_AKTIV)
        self.deckkraft += (ziel_deck - self.deckkraft) * 0.10
        for eintrag in self.werkzeuge.values():
            eintrag[1] *= 0.975  # Aufleuchten klingt langsam ab
        self.update()

    # --- Malen -------------------------------------------------------------

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        # Ab hier wird im gebauten Raster gemalt, nicht in Bildschirm-
        # pixeln. Deshalb bleiben alle Konstanten unten unveraendert.
        p.scale(SKALA, SKALA)
        p.setOpacity(self.deckkraft)
        farbe = FARBEN[self.zustand]

        # Solange das Nachhoerfenster laeuft, faerbt sich der ruhige Ring
        # schwach in die Zuhoer-Farbe -- man sieht aus dem Augenwinkel, ob
        # ein "Hey Sarvis" noetig ist oder nicht.
        if self.zustand == RUHIG and self.nachhoeren > 0.0:
            anteil = 0.30 + 0.35 * (self.nachhoeren / self.nachhoeren_ganz)
            farbe = self._mischen(FARBEN[RUHIG], FARBEN[HOERT], anteil)

        atem = 0.5 + 0.5 * math.sin(self.tick * 1.6)
        # Im Ruhezustand atmet der Ring -- es sei denn, das Mikrofon hoert
        # gerade wirklich etwas. Dann schlaegt er aus, auch ohne gefallenes
        # Weckwort. Das ist der ganze Unterschied zwischen "er ueberlegt
        # noch" und "das Ding ist tot".
        staerke = (
            self.geglaettet if self.zustand in (HOERT, SPRICHT)
            else max(atem * 0.25, self.geglaettet)
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
            # ANZEIGE_GRUND deckt den Untergrund staerker ab; 255 ist die
            # Grenze, sonst faerbt der Verlauf nach aussen falsch.
            deckung = alpha * config.ANZEIGE_GRUND * (0.8 + 0.2 * staerke)
            g.setColorAt(stelle, QColor(6, 10, 20, min(255, int(deckung))))
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(MITTE, r, r * 0.92)

    def _entwicklungsfarbe(self):
        """Welche Farbe das Entwicklungs-Icon gerade hat -- oder None.

        Es gibt keinen echten Fortschritt zu messen; was ein Arbeiter
        gerade tut, weiss nur er. Was man ehrlich sagen kann, ist WIE
        LANGE er schon dabei ist -- und ob er fertig ist. Genau das
        zeigen die drei Farben, nichts anderes wird behauptet.
        """
        if self.hg_fertig:
            return QColor(120, 226, 140)          # fertig
        if not self.hintergrund:
            return None                            # laeuft nichts
        if self.hg_seit < config.ENTWICKLUNG_ROT_SEK:
            return QColor(255, 104, 104)          # gerade begonnen
        return QColor(255, 176, 72)               # laeuft

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

            # Die Entwicklung leuchtet in EIGENER Farbe weiter, solange
            # gebaut wird -- unabhaengig davon, was Sarvis gerade macht.
            # Sie atmet dabei, damit sie sich von einem Werkzeug
            # unterscheidet, das nur eben kurz aufgeleuchtet ist.
            if name == "Entwicklung":
                eigen = self._entwicklungsfarbe()
                if eigen is not None:
                    puls = 0.5 + 0.5 * math.sin(self.tick * 2.4)
                    f = QColor(eigen)
                    f.setAlphaF(0.72 + 0.28 * puls)
                    glut = max(glut, 0.30 + 0.40 * puls)

            # Speiche nach innen
            s = QColor(f)
            s.setAlphaF(kraft * 0.35)
            p.setPen(QPen(s, 1.0))
            p.drawLine(
                # Endet weiter innen als frueher: ein Zeichen ist hoeher
                # als ein Punkt, sonst stoesst die Speiche daran an.
                QPointF(MITTE.x() + ci * (KRANZ - 30), MITTE.y() + si * (KRANZ - 30)),
                QPointF(MITTE.x() + ci * (KRANZ - 17), MITTE.y() + si * (KRANZ - 17)),
            )

            zeichen = self.icons.get(name) if self.icon_schrift else None

            if zeichen is None:
                # Punkt -- der Rueckfall, wenn die Icon-Schrift fehlt.
                r = 2.6 + glut * 3.0
                p.setPen(Qt.NoPen)
                p.setBrush(f)
                p.drawEllipse(punkt, r, r)
            else:
                # Aufleuchten: ein weicher Schein HINTER dem Zeichen. Das
                # Zeichen selbst nur heller zu faerben reicht nicht -- eine
                # duenne Linie hat zu wenig Flaeche, um aus dem Augenwinkel
                # aufzufallen. Genau darum geht es hier aber.
                if glut > 0.02:
                    weite = ICON_PIXEL * 1.6
                    sch = QRadialGradient(punkt, weite)
                    innen = QColor(f)
                    innen.setAlphaF(min(1.0, 0.50 * glut))
                    aussen = QColor(f)
                    aussen.setAlpha(0)
                    sch.setColorAt(0.0, innen)
                    sch.setColorAt(1.0, aussen)
                    p.setPen(Qt.NoPen)
                    p.setBrush(sch)
                    p.drawEllipse(punkt, weite, weite)

                zf = QFont(self.icon_schrift)
                # Waechst beim Aufleuchten leicht mit -- dieselbe Geste wie
                # beim Punkt vorher, nur sichtbarer.
                zf.setPixelSize(round(ICON_PIXEL + glut * 3))
                p.setFont(zf)
                p.setPen(f)
                p.setBrush(Qt.NoBrush)
                kante = ICON_PIXEL * 2
                p.drawText(
                    QRectF(punkt.x() - kante / 2, punkt.y() - kante / 2,
                           kante, kante),
                    Qt.AlignCenter, zeichen,
                )
                p.setFont(schrift)   # zurueck auf die Beschriftung

            # Beschriftung, nach aussen versetzt. Weiter weg als beim
            # Punkt: ein Zeichen ist gut dreimal so breit.
            breite = mass.horizontalAdvance(name) + 16
            kasten = QRectF(
                punkt.x() + ci * (breite / 2 + 15) - breite / 2,
                punkt.y() + si * 19 - 8,
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

    def _hintergrund_malen(self, p) -> None:
        """Laufende Arbeit, die nicht im Gespraech steht -- oben links.

        Die Ecke ist keine Geschmacksfrage. Mittig unter dem Ring lag die
        Zeile ueber den Beschriftungen des Kranzes UND ueber der
        Freigabe: drei Texte uebereinander, keiner davon lesbar. Oben
        links ist der einzige Platz, der bei jedem Zustand frei bleibt --
        aber nur bis x 200: seit der Kranz siebzehn Werkzeuge hat, liegt
        die Beschriftung des letzten ('Finanzen') ab x 204 auf derselben
        Hoehe wie die erste Zeile. Deshalb werden die Zeilen bei 180
        gekuerzt, mit sichtbarem '…' statt eines stummen Schnitts.

        Eigene Farbe, ebenfalls absichtlich: Das gehoert zu keinem der
        Zustaende -- es laeuft weiter, egal ob er zuhoert, denkt oder
        schweigt. Der Ring in der Mitte gehoert IHM, diese Ecke der
        Arbeit im Hintergrund.
        """
        farbe = self._entwicklungsfarbe() or QColor(126, 224, 168)
        x, y = 16.0, 12.0

        # Drei wandernde Punkte: Eine stehende Zeile sieht aus wie eine,
        # die haengengeblieben ist.
        schritt = int(self.tick * 3.0) % 3
        p.setPen(Qt.NoPen)
        for i in range(3):
            c = QColor(farbe)
            c.setAlphaF(0.95 if i == schritt else 0.25)
            p.setBrush(c)
            p.drawEllipse(QPointF(x + 3 + i * 7.0, y + 8.0), 2.4, 2.4)

        kopf = (f"im Hintergrund · {len(self.hintergrund)}"
                if len(self.hintergrund) > 1 else "im Hintergrund")
        f = QFont("Segoe UI", 7)
        f.setLetterSpacing(QFont.PercentageSpacing, 160)
        f.setCapitalization(QFont.AllUppercase)
        p.setFont(f)
        kopffarbe = QColor(farbe)
        kopffarbe.setAlphaF(0.95)
        self._beschriften(p, QRectF(x + 26, y, 240, 15), Qt.AlignLeft,
                          kopf, kopffarbe)
        y += 15

        p.setFont(QFont("Segoe UI", 7))
        mass = QFontMetrics(p.font())
        for zeile in self.hintergrund[:3]:
            c = QColor(farbe)
            c.setAlphaF(0.78)
            self._beschriften(p, QRectF(x + 4, y, 180, 14), Qt.AlignLeft,
                              mass.elidedText(zeile, Qt.ElideRight, 180), c)
            y += 13

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

        if self.hintergrund or self.hg_fertig:
            self._hintergrund_malen(p)

        if self.freigabe:
            f = QFont("Segoe UI", 7)
            f.setLetterSpacing(QFont.PercentageSpacing, 160)
            f.setCapitalization(QFont.AllUppercase)
            p.setFont(f)
            self._beschriften(
                p, QRectF(0, MITTE.y() + RADIUS + 92, BREITE, 16),
                Qt.AlignHCenter, self.freigabe, QColor(255, 186, 92, 225),
            )

        if self.untertitel:
            p.setFont(QFont("Segoe UI", 11, QFont.DemiBold))
            if self.wer == "du":
                c = QColor(232, 241, 253, 240)
            else:
                c = QColor(farbe)
                c.setAlphaF(0.92)
            y = MITTE.y() + KRANZ + 34
            kasten = QRectF(70, y, BREITE - 140, HOEHE - y - 8)
            richtung = Qt.AlignHCenter | Qt.AlignTop | Qt.TextWordWrap
            self._beschriften(
                p, kasten, richtung,
                self._untertitel_passend(p, kasten, richtung), c,
            )

    def _untertitel_passend(self, p, kasten, richtung) -> str:
        """So viel Untertitel, wie in den Kasten passt -- vorn gekuerzt.

        drawText schneidet am Rechteck ab, und mit AlignTop faellt das
        ENDE weg: Ab rund 390 Zeichen verschwand ausgerechnet der zuletzt
        gesprochene Teil eines Diktats, ohne ein Zeichen dafuer. Gekuerzt
        wird deshalb vorn, das Neueste bleibt stehen. Qt.TextDontClip
        waere keine Loesung -- dann liefe der Text unten aus dem Fenster.

        Das Ergebnis wird gemerkt: Sonst wuerde die Schrift sechzigmal in
        der Sekunde neu vermessen, obwohl der Satz derselbe bleibt.
        """
        if self.untertitel == self._untertitel_quelle:
            return self._untertitel_passt
        self._untertitel_quelle = self.untertitel
        text = self.untertitel
        if p.boundingRect(kasten, richtung, text).height() > kasten.height():
            # Kleinster Schnitt, der noch passt -- halbierend gesucht,
            # weil jeder Versuch den ganzen Text neu umbricht.
            frueh, spaet = 0, len(text)
            while frueh < spaet:
                mitte = (frueh + spaet) // 2
                probe = "… " + text[mitte:]
                if p.boundingRect(kasten, richtung,
                                  probe).height() <= kasten.height():
                    spaet = mitte
                else:
                    frueh = mitte + 1
            text = "… " + text[frueh:]
        self._untertitel_passt = text
        return text


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
