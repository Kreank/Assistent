"""Ein Browser in der Engine -- statt eines Fensters daneben.

Warum ueberhaupt: Es gibt Dinge, die eine handgemalte Kachel nie so gut
zeigen wird wie das echte Programm. Eine Kalender-Monatsansicht in 250
Rasterpunkte zu malen waere schlechter als Google Kalender selbst. Ein
PDF, ein Drive-Dokument, ein Rechercheergebnis -- alles das kann eine
Seite besser.

Damit ergibt sich die Trennlinie, die es vorher nicht gab:

    Die Kachel ist fuer den Blick nebenbei.
    Der Browser ist fuers Hinsetzen.

Der zweite Grundsatz war lange: Sarvis bringt die Seite, DU bedienst
sie. Der erste Teil bleibt -- eine Seite anzuzeigen ist keine Handlung
an der Aussenwelt und braucht keine Rueckfrage. Der zweite Teil hat
jetzt einen Unterbau bekommen: Weiter unten stehen Methoden, mit denen
sich eine Seite LESEN und BEDIENEN laesst.

Diese Methoden entscheiden NICHTS. Sie duerfen alles und fragen nie --
genau deshalb liefern sie mit jedem Element die zwei Angaben, an denen
oben entschieden wird: "im_formular" und "absenden". Beide kommen aus
dem DOM und nicht aus der Beschriftung, weil ein Knopf, auf dem
"Abbrechen" steht, trotzdem ein Absenden-Knopf sein kann. Wer diese
Methoden verdrahtet, baut die Rueckfrage darauf; hier unten gibt es
keine.

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
import json
import re
import threading
import time
from pathlib import Path

from PySide6.QtCore import (QPoint, QRectF, QThread, QTimer, Qt, QUrl,
                            Signal)
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPen
from PySide6.QtWebEngineCore import (QWebEngineDownloadRequest,
                                     QWebEngineProfile)
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

# --- Deckkraft -------------------------------------------------------------
# Der Einwand im Modulkopf gegen Durchscheinen bleibt richtig -- aber nur
# fuer den Moment, in dem jemand wirklich liest. Steht das Fenster bloss
# da, ist Durchscheinen der gewollte Effekt: Man sieht, was dahinter
# liegt, und das Fenster gehoert sichtbar zur Engine statt daneben.
# Deshalb adaptiv, nach demselben Muster wie DECKKRAFT_RUHIG/AKTIV in
# hud.py: zurueckgenommen, solange niemand dran ist, voll deckend, sobald
# die Maus drueber steht oder das Fenster den Fokus hat.
#
# GEMESSEN: setWindowOpacity wirkt auch auf den von Chromium gemalten
# Inhalt -- eine weisse Seite ueber rotem Grund kam bei 0,5 als
# rgb(255,128,128) vom Bildschirm zurueck, also genau die Mischung. Das
# war nicht selbstverstaendlich, denn WA_TranslucentBackground wirkt nur
# auf das, was WIR malen.
#
# Diese beiden Werte gehoeren spaeter nach config.py, neben
# DECKKRAFT_RUHIG und DECKKRAFT_AKTIV der Engine.
DECKKRAFT_RUHIG = 0.88
DECKKRAFT_AKTIV = 1.00

# Wie schnell zwischen beiden umgeblendet wird: Anteil des Rests je Bild.
# Ein harter Wechsel sieht aus wie ein Flackern, dasselbe Nachziehen wie
# in hud.py bei _schlag.
DECKKRAFT_ZUG = 0.18

# --- Grenzen fuers Lesen ---------------------------------------------------
# Dieselbe Zahl und dieselbe Begruendung wie LESE_GRENZE in
# werkzeuge/google.py: Der ganze Text landet erst einmal bei Claude, und
# eine Nachrichtenseite hat leicht 60.000 Zeichen. Gekuerzt wird MIT
# sichtbarer Markierung -- ein stummer Schnitt kommt als vollstaendige
# Seite an und wird als solche vorgelesen.
LESE_GRENZE = 4000

# Hoechstens so viele Elemente. Vierzig nummerierte Eintraege sind schon
# viel zum Vorlesen; hundert waeren eine Wand, in der niemand mehr
# findet, was er sucht. Wird gekappt, steht es in der Liste -- siehe
# elemente_holen.
ELEMENT_GRENZE = 40
ELEMENT_TEXT_MAX = 80      # Beschriftung je Element

# Zeitlimit, wenn keines mitkommt. Eine Seite, die nach fuenf Sekunden
# kein innerText herausrueckt, haengt -- dann ist eine Meldung besser als
# ein Warten, das der Sprecher nicht erklaeren kann.
ZEITLIMIT = 5.0

# Wie lange nach einem Klick auf eine Navigation gewartet wird. Kurz:
# Wir wollen nur wissen, OB sich die Adresse aendert, nicht auf das
# fertige Laden warten.
KLICK_NACHLAUF = 0.8

# Zoomgrenzen. Qt liesse 0,25 bis 5,0 zu -- beides ist unbrauchbar:
# Bei 0,25 liest niemand mehr etwas, bei 5,0 passen zwei Woerter ins
# Fenster und man sucht sich den Rest zusammen.
ZOOM_MIN, ZOOM_MAX = 0.5, 3.0

# Wohin Downloads gehen. Ein eigener Ordner, damit an einer Stelle
# nachzusehen (und aufzuraeumen) ist, was von fremden Seiten auf der
# Platte gelandet ist -- dieselbe Ueberlegung wie ANHANG_ORDNER in
# werkzeuge/google.py.
DOWNLOAD_ORDNER = config.WURZEL / "downloads"

# So viele abgeschlossene Downloads werden gemerkt. Die Liste ist eine
# Gedaechtnisstuetze fuer "wo liegt das jetzt", kein Archiv.
DOWNLOAD_GEDAECHTNIS = 50

# Windows haelt diese Namen fuer Geraete und nicht fuer Dateien -- eine
# Datei "CON.txt" laesst sich nicht anlegen. Gleiche Liste wie in
# werkzeuge/google.py; bewusst kopiert und nicht importiert, denn dieses
# Modul laeuft im Anzeigeprozess und soll die Werkzeuge samt ihrer
# Abhaengigkeiten nicht mitziehen.
GERAETENAMEN = ({"CON", "PRN", "AUX", "NUL"}
                | {f"COM{i}" for i in range(1, 10)}
                | {f"LPT{i}" for i in range(1, 10)})

NAME_MAX = 80      # Laenge des Namensstamms; Windows deckelt den Pfad bei 260


# --- Dateinamen aus fremder Hand ------------------------------------------
# Gleiches Muster wie _dateiname_saeubern/_anhang_ziel in
# werkzeuge/google.py, und aus demselben Grund: Der Name kommt von der
# Seite. Er ist Text, keine Zusage.

def _dateiname_saeubern(roh: str) -> str:
    """Einen Dateinamen von der Seite in einen harmlosen verwandeln.

    Content-Disposition schlaegt einen Namen vor, und den sucht sich der
    Server aus. "..\\..\\sarvis\\config.py" wuerde beim Zusammensetzen aus
    dem Downloadordner herausfuehren, "C:datei" zeigt unter Windows auf
    das Arbeitsverzeichnis von Laufwerk C. Deshalb wird der Name nicht
    repariert, sondern auf das reduziert, was ein Dateiname sein darf:
    letzter Abschnitt, harmlose Zeichen, begrenzte Laenge.
    """
    name = str(roh or "").strip()
    # Beide Trennerarten: Ein Linux-Server schickt "/", ein Windows-Server
    # "\" -- und Python nimmt unter Windows beides als Trenner.
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r'[<>:"|?*]', "_", name)
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)
    # Punkte und Leerzeichen am Ende schluckt Windows beim Anlegen still.
    # Geprueft haetten wir dann einen anderen Namen als den geschriebenen.
    name = name.strip(" .")
    if not name:
        return "download"
    stamm, punkt, endung = name.rpartition(".")
    if not punkt:
        stamm, endung = name, ""
    if stamm.upper() in GERAETENAMEN:
        stamm = "_" + stamm
    stamm = stamm[:NAME_MAX] or "download"
    endung = endung[:16]
    return stamm + ("." + endung if endung else "")


def _freier_pfad(ordner: Path, name: str):
    """Freien Pfad im Zielordner suchen; legt den Ordner an, wenn er fehlt.

    Gibt None zurueck, wenn der Pfad wider Erwarten aus dem Ordner
    herausfuehrt. Das ist der zweite Riegel hinter _dateiname_saeubern --
    zwei Riegel, weil ein Fehler hier eine fremde Datei an einen Ort
    schreibt, den sich die Seite ausgesucht hat.
    """
    ordner.mkdir(parents=True, exist_ok=True)
    stamm, punkt, endung = name.rpartition(".")
    if not punkt:
        stamm, endung = name, ""
    ziel = ordner / name
    zaehler = 2
    # Zwei Downloads gleichen Namens ueberschreiben einander nicht -- sonst
    # waere die Rechnung von gestern nach dem naechsten Klick weg.
    while ziel.exists():
        ziel = ordner / (f"{stamm}-{zaehler}"
                         + ("." + endung if endung else ""))
        zaehler += 1
    if ordner.resolve() != ziel.resolve().parent:
        return None
    return ziel


# --- Was im Browser laeuft -------------------------------------------------
# Diese Hilfsfunktionen stehen VOR jedem Skript, statt einmal an window zu
# haengen: Ein window-Zustand ueberlebt keine Navigation, und ein Skript,
# dessen Haelfte auf der vorigen Seite lag, scheitert dann mit einem
# ReferenceError statt mit einer Meldung, die man vorlesen kann.
_JS_HILFE = """
function _kurz(s, max) {
  s = String(s == null ? '' : s).replace(/\\s+/g, ' ').trim();
  return s.length > max ? s.slice(0, max) + '\\u2026' : s;
}
function _sichtbar(el) {
  if (!el || !el.isConnected) return false;
  try { if (el.matches(':disabled')) return false; } catch (e) {}
  if (el.getAttribute && el.getAttribute('aria-disabled') === 'true') return false;
  if (el.closest && el.closest('[inert]')) return false;
  if (el.getAttribute && el.getAttribute('aria-hidden') === 'true') return false;
  // Nullgroesse faengt gleich mehreres ab: display:none beim Element
  // selbst, display:none bei einem Vorfahren, hidden, und die
  // Zaehlpixel, die nur 1x1 gross sind.
  var r = el.getBoundingClientRect();
  if (r.width < 2 || r.height < 2) return false;
  var s = window.getComputedStyle(el);
  if (!s) return false;
  if (s.display === 'none') return false;
  if (s.visibility === 'hidden' || s.visibility === 'collapse') return false;
  if (parseFloat(s.opacity || '1') < 0.05) return false;
  return true;
}
function _formular(el) {
  return el.form || (el.closest ? el.closest('form') : null) || null;
}
function _absenden(el) {
  // Aus dem DOM, nicht aus der Beschriftung. el.type liefert bei
  // <button> von sich aus 'submit', wenn kein type dasteht -- genau die
  // Regel der Spezifikation. Ohne Formular kann nichts abgesendet
  // werden, auch ein <button type=submit> nicht.
  if (!_formular(el)) return false;
  var t = el.tagName.toLowerCase();
  var typ = String(el.type || '').toLowerCase();
  if (t === 'input') return typ === 'submit' || typ === 'image';
  if (t === 'button') return typ === 'submit';
  return false;
}
function _art(el) {
  var t = el.tagName.toLowerCase();
  var typ = String(el.type || '').toLowerCase();
  if (t === 'select') return 'auswahl';
  if (t === 'textarea') return 'feld';
  if (t === 'img') return 'bild';
  if (t === 'input') {
    if (typ === 'button' || typ === 'submit' || typ === 'reset'
        || typ === 'image' || typ === 'checkbox' || typ === 'radio')
      return 'knopf';
    return 'feld';
  }
  if (t === 'button') return 'knopf';
  var rolle = String((el.getAttribute && el.getAttribute('role')) || '')
              .toLowerCase();
  if (t === 'a' && el.hasAttribute('href')) return 'link';
  if (rolle === 'link') return 'link';
  if (el.isContentEditable) return 'feld';
  return 'knopf';
}
function _feldart(el) {
  var t = el.tagName.toLowerCase();
  if (t === 'input') return String(el.type || 'text').toLowerCase();
  if (t === 'textarea') return 'mehrzeilig';
  if (t === 'select') return el.multiple ? 'mehrfachauswahl' : 'auswahl';
  if (el.isContentEditable) return 'text';
  return '';
}
function _beschriftung(el, max) {
  var t = el.tagName.toLowerCase();
  var s = '';
  if (t === 'img') {
    s = el.alt || el.title || '';
  } else if (t === 'input' || t === 'textarea' || t === 'select') {
    var typ = String(el.type || '').toLowerCase();
    if (typ === 'button' || typ === 'submit' || typ === 'reset') s = el.value || '';
    var etikett = '';
    try {
      if (el.labels && el.labels.length) etikett = el.labels[0].innerText;
    } catch (e) {}
    // Der WERT eines Feldes ist hier bewusst nicht die Beschriftung: Bei
    // einem Passwortfeld waere er das Passwort, und die Beschriftung geht
    // an Claude.
    s = s || el.getAttribute('aria-label') || etikett || el.placeholder
          || el.title || el.name || '';
  } else {
    s = el.innerText || '';
    if (!s.trim()) {
      var bild = el.querySelector ? el.querySelector('img[alt]') : null;
      s = el.getAttribute('aria-label') || el.title
            || (bild ? bild.alt : '') || '';
    }
  }
  return _kurz(s, max);
}
function _kennung(el) {
  // Der Fingerabdruck eines Elements. Er wird beim Lesen gemerkt und beim
  // Klicken erneut gebildet: Baut eine Seite ihren Inhalt neu auf und
  // sitzt an derselben Stelle ein anderer Knopf, stimmt er nicht mehr
  // ueberein -- und dann wird nicht geklickt, sondern gemeldet.
  var t = el.tagName.toLowerCase();
  return [t, String(el.type || ''), el.id || '', el.name || '',
          (t === 'a' ? (el.getAttribute('href') || '') : ''),
          _absenden(el) ? 'A' : '-',
          _beschriftung(el, 80)].join('|');
}
"""

# Auswahl der Kandidaten. Bewusst breit -- was davon wirklich bedienbar
# ist, entscheidet _sichtbar, nicht die Auswahl.
_JS_AUSWAHL = ("a[href], button, input, select, textarea, img, "
               "[role=button], [role=link], [onclick], "
               "[contenteditable=''], [contenteditable=true]")


class Browser(QWidget):
    """Eine Seite, die Sarvis bringt -- und lesen und bedienen kann."""

    _profil = None   # EIN Profil fuer alle Fenster -- siehe _profil_holen

    # Downloads haengen am PROFIL, und das Profil ist gemeinsam. Also
    # gehoeren auch der Zielordner und die Merkliste an die Klasse: Zwei
    # Fenster, die sich ein Profil teilen, teilen sich zwangslaeufig auch
    # das downloadRequested-Signal.
    _download_ordner = None
    _download_profil = None      # an welchem Profil schon verbunden wurde
    _downloads: list = []

    # Auftraege in den Qt-Faden. Ein Signal und keine direkte Methode:
    # Ein Signal darf aus jedem Faden ausgeloest werden, und mit
    # QueuedConnection laeuft der Empfaenger im Faden des Empfaengers.
    # Siehe _im_qt_faden.
    _auftrag = Signal(object)

    def __init__(self):
        super().__init__()
        # Kein WindowTransparentForInput: Ein Browser, den man bedienen
        # soll, darf Klicks nicht durchlassen.
        #
        # Und KEIN WindowStaysOnTopHint. Das stand hier, aus hud.py
        # uebernommen -- dort ist es richtig: Eine Statusanzeige soll man
        # immer sehen, sonst haelt man sie fuer abgestuerzt. Ein Fenster,
        # in dem man liest und arbeitet, ist etwas anderes. Obenauf
        # bedeutete: Man bekommt seinen Editor nicht mehr davor, und ein
        # Fenster, das man nicht wegschieben kann, ist kein Fenster
        # mehr, sondern ein Aufkleber. Dass es beim Zuruf trotzdem
        # sichtbar wird, macht zeigen() mit raise_().
        #
        # Die Kacheln bleiben obenauf -- sie sind Anzeigen und keine
        # Fenster zum Arbeiten, und man arbeitet durch sie hindurch.
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.Tool
        )
        # Bleibt: nach vorne holen ja, den Tastaturfokus stehlen nein.
        # Wer gerade tippt, tippt weiter -- geprueft, raise_() aendert
        # daran nichts (siehe zeigen()).
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("Sarvis")
        self.setMinimumSize(420, 320)
        self.resize(config.BROWSER_BREITE, config.BROWSER_HOEHE)

        self._titel = ""
        self._griff = None      # Mausversatz beim Verschieben

        # Deckkraft: gestartet wird zurueckgenommen, weil beim ersten
        # Zeigen noch niemand dranstand.
        self._deckkraft = DECKKRAFT_RUHIG
        self.setWindowOpacity(DECKKRAFT_RUHIG)
        self.uhr = QTimer(self)
        self.uhr.setInterval(33)          # rund 30 Bilder je Sekunde
        self.uhr.timeout.connect(self._deckkraft_nachziehen)

        # Was zuletzt gelesen wurde: {nummer: fingerabdruck}. Daran
        # erkennt ein Klick, ob er noch dasselbe Element meint.
        self._elemente: dict = {}
        self._lauf = 0          # Zaehler je Leseblick, siehe elemente_holen
        self._auftrag.connect(self._auftrag_ausfuehren, Qt.QueuedConnection)

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

        # Der Verschiebe-Zeiger liegt auf dem FENSTER, nicht auf der
        # Seite: Die QWebEngineView ist ein Kindwidget und setzt ihren
        # eigenen Zeiger (Textmarke, Hand ueber Links) -- der Zeiger des
        # Elternfensters erscheint darum nur dort, wo wir selbst malen,
        # also auf der Kopfleiste und dem Rahmen. Genau die Flaeche, an
        # der man ziehen kann. Kein Sonderfall noetig.
        self.setCursor(Qt.SizeAllCursor)

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
        """Eine Seite laden und das Fenster hervorholen.

        show() bringt es auf den Schirm, raise_() nach vorne. Kein
        activateWindow(): Das Fenster soll SICHTBAR werden, nicht den
        Tastaturfokus an sich reissen -- wer gerade in seinem Editor
        tippt, tippt danach weiter.

        GEMESSEN unter Windows 11 mit einem Qt.Tool-Fenster ohne
        WindowStaysOnTopHint und mit WA_ShowWithoutActivating: raise_()
        setzt das Fenster in der Z-Reihenfolge vor ein zuvor
        hervorgeholtes Fremdfenster, und isActiveWindow() bleibt dabei
        False. Beides zusammen ist genau das Gewollte.
        """
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

    # --- Deckkraft --------------------------------------------------------

    def _jemand_dran(self) -> bool:
        """Ob gerade jemand an diesem Fenster ist.

        Zwei Anzeichen, und beide bewusst so gewaehlt:

        Die Maus steht darueber. NICHT ueber enterEvent/leaveEvent
        abgefragt: Die QWebEngineView ist ein Kindwidget und nimmt die
        Maus an sich, sobald der Zeiger die Seite erreicht -- das
        Elternfenster bekaeme dabei ein leaveEvent und blendete
        ausgerechnet dann ab, wenn jemand liest. Ein Vergleich der
        Fenstergeometrie mit der Zeigerposition kennt diesen Unterschied
        nicht und stimmt immer.

        Oder das Fenster ist aktiv. isActiveWindow() haelt bei Qt.Tool
        stand -- WA_ShowWithoutActivating verhindert nur, dass das
        Fenster sich den Fokus beim Zeigen NIMMT; klickt man hinein,
        wird es trotzdem aktiv.
        """
        if self.isActiveWindow():
            return True
        return self.frameGeometry().contains(QCursor.pos())

    def _deckkraft_nachziehen(self) -> None:
        ziel = DECKKRAFT_AKTIV if self._jemand_dran() else DECKKRAFT_RUHIG
        self._deckkraft += (ziel - self._deckkraft) * DECKKRAFT_ZUG
        # Am Ende aufsetzen: Ein exponentielles Nachziehen kommt nie ganz
        # an, und ein Fenster, das bei 0,997 stehen bleibt, ist nicht
        # "voll deckend".
        if abs(ziel - self._deckkraft) < 0.004:
            self._deckkraft = ziel
        self.setWindowOpacity(self._deckkraft)

    def showEvent(self, e):
        # Die Uhr laeuft nur, solange das Fenster zu sehen ist. Ein Takt
        # fuer ein verstecktes Fenster waere Arbeit fuer nichts -- und
        # der Prozess hier malt nebenbei den Ring.
        super().showEvent(e)
        self.uhr.start()

    def hideEvent(self, e):
        super().hideEvent(e)
        self.uhr.stop()

    # --- Der Weg zum JavaScript -------------------------------------------
    #
    # runJavaScript() ist asynchron: Es gibt nichts zurueck, sondern ruft
    # spaeter einen Rueckruf -- und "spaeter" heisst: wenn die Qt-Schleife
    # wieder drankommt. Wer ein Ergebnis will, braucht also einen Weg vom
    # Rueckruf zurueck zum Aufrufer. Drei kamen in Frage:
    #
    #   Eine zweite QEventLoop starten und darin warten. Der uebliche
    #   Trick -- und der schlechteste. Waehrend die verschachtelte
    #   Schleife laeuft, kommen ALLE anderen Ereignisse weiter durch:
    #   Der naechste UDP-Befehl wird mitten in unserem Warten bearbeitet,
    #   ein Timer malt neu, ein zweiter Leseblick beginnt, waehrend der
    #   erste noch haengt. Solche Fehler sind spaeter nicht mehr zu
    #   finden, weil sie von der Reihenfolge fremder Ereignisse abhaengen.
    #
    #   processEvents() in einer Warteschleife. Dasselbe, nur ohne Namen.
    #
    #   Der Rueckruf legt sein Ergebnis in einen Kasten und setzt ein
    #   threading.Event; der AUFRUFER wartet darauf -- aber in einem
    #   anderen Faden. Die Qt-Schleife laeuft dabei ungestoert weiter und
    #   ruft irgendwann den Rueckruf; das Zeitlimit ist einfach das
    #   Zeitlimit von Event.wait(). Nichts wird verschachtelt, nichts
    #   blockiert.
    #
    # Der dritte Weg ist es geworden. Der Preis steht in _qt_faden_pruefen:
    # Diese Methoden muessen aus einem ARBEITSFADEN gerufen werden, nicht
    # aus dem Qt-Faden selbst. Wer sie aus einem Signal-Handler ruft,
    # bekommt eine klare Fehlermeldung statt eines Aufhaengers.

    def _im_qt_faden(self, arbeit) -> None:
        """arbeit() im Qt-Faden ausfuehren lassen -- aus jedem Faden erlaubt."""
        self._auftrag.emit(arbeit)

    def _auftrag_ausfuehren(self, arbeit) -> None:
        try:
            arbeit()
        except Exception as e:      # noqa: BLE001 -- ein Fehler hier darf
            # die Anzeige nicht mitnehmen; sie ist der Prozess, in dem der
            # Ring laeuft.
            print(f"Browser-Auftrag fehlgeschlagen: {type(e).__name__}: {e}")

    def _qt_faden_pruefen(self) -> None:
        """Sicherstellen, dass wir NICHT im Qt-Faden sind.

        Im Qt-Faden zu warten hiesse: Wir halten genau die Schleife an,
        die den Rueckruf bringen soll -- ein Aufhaenger bis zum
        Zeitlimit, jedes Mal. Lieber ein lautes Nein.
        """
        if QThread.currentThread() == self.thread():
            raise RuntimeError(
                "Die Lese- und Bedienmethoden des Browsers muessen aus "
                "einem Arbeitsfaden gerufen werden, nicht aus dem "
                "Qt-Faden -- sonst wartet die Schleife auf sich selbst.")

    def _js(self, skript: str, zeitlimit: float):
        """Ein Skript ausfuehren und auf sein Ergebnis warten.

        Gibt (gelungen, wert) zurueck. gelungen=False heisst: Zeitlimit
        abgelaufen oder es gab keine Seite -- NICHT, dass das Ergebnis
        None war. Beides auseinanderzuhalten ist noetig, weil ein Skript
        durchaus null liefern darf.
        """
        self._qt_faden_pruefen()
        fertig = threading.Event()
        kasten = [None]

        def ablegen(wert):
            kasten[0] = wert
            fertig.set()

        def starten():
            seite = self.ansicht.page()
            if seite is None:
                fertig.set()
                return
            # Ein Rueckruf, der nie kommt (Seite navigiert waehrenddessen
            # weg), ist kein Problem: Dann laeuft schlicht das Zeitlimit ab.
            seite.runJavaScript(skript, ablegen)

        self._im_qt_faden(starten)
        if not fertig.wait(max(0.1, float(zeitlimit))):
            return False, None
        return True, kasten[0]

    def _js_daten(self, vorspann: str, ausdruck: str, zeitlimit: float):
        """Wie _js, aber fuer Objekte und Listen -- ueber JSON.

        GEMESSEN mit PySide6 6.11.2: runJavaScript liefert Zahlen und
        Strings sauber, aber JEDES Objekt und JEDE Liste kommen als
        leerer String an. "1+1" gibt 2.0, "({a:1})" gibt "". Die
        Umwandlung von JS-Objekten nach QVariant greift hier also nicht,
        und ein Ergebnis waere still leer statt fehlerhaft -- das ist die
        unangenehmste Sorte Fehler.

        Deshalb geht alles Strukturierte als JSON-String durch die
        Bruecke und wird hier geparst. Das kostet nichts und ist
        ausserdem eindeutig: Was ankommt, ist genau das, was drueben
        stand.
        """
        gelungen, roh = self._js(
            f"{vorspann}\nJSON.stringify({ausdruck})", zeitlimit)
        if not gelungen or not isinstance(roh, str) or not roh:
            return False, None
        try:
            return True, json.loads(roh)
        except ValueError:
            return False, None

    def _wert_holen(self, arbeit, zeitlimit: float = 2.0):
        """Etwas im Qt-Faden ausrechnen lassen und den Wert abholen.

        Fuer alles, was KEIN JavaScript ist -- Zoom setzen, Signale
        verbinden. Anders als _js darf das auch im Qt-Faden selbst laufen:
        Dort ist es einfach ein direkter Aufruf, kein Warten.
        """
        if QThread.currentThread() == self.thread():
            return True, arbeit()
        fertig = threading.Event()
        kasten = [None]

        def lauf():
            try:
                kasten[0] = arbeit()
            finally:
                fertig.set()

        self._im_qt_faden(lauf)
        if not fertig.wait(max(0.1, float(zeitlimit))):
            return False, None
        return True, kasten[0]

    # --- Lesen ------------------------------------------------------------

    def text_holen(self, zeitlimit: float = ZEITLIMIT) -> str:
        """Der sichtbare Text der Seite, mit Titel und Adresse davor.

        Gibt EINEN String zurueck, fertig zum Weiterreichen:

            Titel: Beispielseite
            Adresse: https://example.com/

            Hier steht der Text …
            [… gekürzt]

        Bewusst innerText und nicht textContent: textContent bringt auch
        den Inhalt von <script> und <style> mit und ignoriert Umbrueche,
        innerText liefert das, was ein Mensch dort saehe.

        Scheitert es, ist der String ein deutscher Satz, der sagt warum --
        ein leerer String hiesse "die Seite ist leer", und das waere eine
        andere Aussage.
        """
        skript = """
        (function () {
          var t = document.body ? (document.body.innerText || '') : '';
          // Leerzeilenketten zusammenlegen: Eine gewoehnliche Seite
          // liefert sonst mehr Umbrueche als Text.
          t = t.replace(/[ \\t]+\\n/g, '\\n').replace(/\\n{3,}/g, '\\n\\n').trim();
          return {titel: document.title || '', adresse: location.href, text: t};
        })()
        """
        gelungen, wert = self._js_daten("", skript, zeitlimit)
        if not gelungen:
            return ("Die Seite hat innerhalb von "
                    f"{zeitlimit:g} Sekunden nicht geantwortet.")
        if not isinstance(wert, dict):
            return "Die Seite hat keinen lesbaren Text zurückgegeben."
        text = str(wert.get("text") or "")
        gekuerzt = ""
        if len(text) > LESE_GRENZE:
            text, gekuerzt = text[:LESE_GRENZE], "\n[… gekürzt]"
        kopf = (f"Titel: {wert.get('titel') or '(ohne Titel)'}\n"
                f"Adresse: {wert.get('adresse') or '(unbekannt)'}")
        if not text:
            return kopf + "\n\n(Die Seite zeigt keinen Text.)"
        return f"{kopf}\n\n{text}{gekuerzt}"

    def elemente_holen(self, zeitlimit: float = ZEITLIMIT) -> list:
        """Die bedienbaren Elemente der Seite, nummeriert ab 1.

        Je Eintrag ein dict:

            nummer      int   1, 2, 3 … -- damit ruft man klicken/tippen
            art         str   "knopf" | "link" | "feld" | "auswahl" | "bild"
            text        str   sichtbare Beschriftung, auf 80 Zeichen gekappt
            im_formular bool  steckt in einem <form>
            absenden    bool  ist der Absende-Knopf dieses Formulars
            adresse     str   bei Links das Ziel, bei Bildern die Quelle
            feldart     str   bei Feldern text/password/email/…, sonst ""
            sichtbar    bool  immer True -- Unsichtbares steht gar nicht drin
            wert        str   was im Feld steht (bei Passwortfeldern nie)

        "sichtbar" ist immer True und trotzdem da: Der Aufrufer soll das
        Feld lesen duerfen, ohne zu wissen, dass die Auswahl schon
        vorher passiert ist. Ausgesiebt wird alles mit display:none,
        visibility:hidden, Nullgroesse, [hidden], aria-hidden, [inert],
        opacity nahe null und alles, was :disabled trifft -- ein
        disabled-Knopf ist zu sehen, aber nicht zu bedienen, und in eine
        Liste zum Anklicken gehoert er darum nicht.

        im_formular und absenden kommen aus dem DOM (el.form bzw.
        el.closest('form'), und el.type, das bei <button> von sich aus
        'submit' meldet, wenn kein type dasteht). NICHT aus der
        Beschriftung: Ein Knopf mit "Weiter" kann absenden, einer mit
        "Absenden" kann ein reines JavaScript sein.

        Wird gekappt, steht als LETZTER Eintrag ein Hinweis mit
        nummer 0 und art "hinweis" -- 0 ist keine gueltige Nummer, ein
        Klick darauf schlaegt sauber fehl. So bleibt die Rueckgabe eine
        einzige Liste, und die Kappung geht trotzdem nicht verloren.

        Bilder kommen nur mit, wenn sie nicht schon in einem Link oder
        Knopf stecken -- sonst stuenden Bild und Link zweimal da und man
        klickt zweimal dasselbe.
        """
        self._lauf += 1
        ausdruck = """
        (function () {
          var GRENZE = %(grenze)d, MAX = %(max)d, LAUF = %(lauf)d;
          var kandidaten = document.querySelectorAll(%(auswahl)s);
          var knoten = [], liste = [], gesamt = 0;
          for (var i = 0; i < kandidaten.length; i++) {
            var el = kandidaten[i];
            if (!_sichtbar(el)) continue;
            var t = el.tagName.toLowerCase();
            if (t === 'input' && String(el.type).toLowerCase() === 'hidden') continue;
            // Ein Bild in einem Link ist der Link. Zweimal auffuehren
            // hiesse: zwei Nummern, ein Ziel.
            if (t === 'img' && el.closest('a[href], button')) continue;
            gesamt++;
            if (liste.length >= GRENZE) continue;
            var art = _art(el);
            var adresse = '';
            if (art === 'link' && el.href) adresse = String(el.href);
            else if (t === 'img') {
              var q = String(el.currentSrc || el.src || '');
              // Eine data:-URI ist hier nutzlos und kann ein halbes
              // Megabyte gross sein -- die geht nicht mit.
              adresse = q.indexOf('data:') === 0 ? '' : q.slice(0, 300);
            }
            var wert = '';
            var fa = _feldart(el);
            // Der Inhalt eines Passwortfeldes geht nirgendwohin. Er wuerde
            // sonst im Kontext von Claude stehen und im Verlauf landen.
            if (art === 'feld' && fa !== 'password') wert = _kurz(el.value, MAX);
            if (el.isContentEditable) wert = _kurz(el.innerText, MAX);
            knoten.push(el);
            liste.push({
              nummer: liste.length + 1,
              art: art,
              text: _beschriftung(el, MAX),
              im_formular: !!_formular(el),
              absenden: _absenden(el),
              adresse: adresse,
              feldart: fa,
              sichtbar: true,
              wert: wert,
              kennung: _kennung(el)
            });
          }
          // Die Knoten selbst merken, nicht bloss einen Selektor: Ein
          // Selektor kann nach einem Neuaufbau auf ein ANDERES Element
          // passen, eine Referenz nie. Was an window haengt, ist nach
          // einer Navigation von selbst weg -- genau richtig, denn dann
          // ist die Liste ohnehin ungueltig.
          window.__sarvis_bedienung = {lauf: LAUF, knoten: knoten};
          return {liste: liste, gesamt: gesamt,
                  titel: document.title || '', adresse: location.href};
        })()
        """ % {"grenze": ELEMENT_GRENZE, "max": ELEMENT_TEXT_MAX,
               "lauf": self._lauf, "auswahl": json.dumps(_JS_AUSWAHL)}

        gelungen, wert = self._js_daten(_JS_HILFE, ausdruck, zeitlimit)
        if not gelungen or not isinstance(wert, dict):
            self._elemente = {}
            return [{"nummer": 0, "art": "hinweis",
                     "text": ("Die Seite hat die Elemente nicht innerhalb "
                              f"von {zeitlimit:g} Sekunden geliefert."),
                     "im_formular": False, "absenden": False, "adresse": "",
                     "feldart": "", "sichtbar": False, "wert": ""}]

        liste = list(wert.get("liste") or [])
        # Die Fingerabdruecke bleiben HIER und gehen nicht mit hinaus: Sie
        # sind Innenleben fuer klicken/tippen, nicht Information fuer den,
        # der die Liste vorliest.
        self._elemente = {}
        for eintrag in liste:
            nr = int(eintrag["nummer"])
            self._elemente[nr] = str(eintrag.pop("kennung", ""))

        gesamt = int(wert.get("gesamt") or len(liste))
        if gesamt > len(liste):
            liste.append({
                "nummer": 0, "art": "hinweis",
                "text": f"[… {gesamt - len(liste)} weitere Elemente gekürzt]",
                "im_formular": False, "absenden": False, "adresse": "",
                "feldart": "", "sichtbar": False, "wert": ""})
        return liste

    # --- Bedienen ---------------------------------------------------------

    def _element_skript(self, nummer: int, koerper: str) -> str:
        """Ein Skript, das erst das Element wiederfindet und dann koerper tut.

        Der gemeinsame Kopf von klicken und tippen. Er prueft in dieser
        Reihenfolge und bricht beim ersten Nein ab -- lieber gar nichts
        tun als etwas anderes:

          Ist die Liste noch die, die gelesen wurde? (Lauf-Nummer)
          Gibt es die Nummer?
          Haengt der Knoten noch im Dokument? (isConnected)
          Ist er noch sichtbar und bedienbar?
          Ist es noch DASSELBE Element? (Fingerabdruck)

        Der letzte Punkt ist der wichtige. Eine Seite kann sich zwischen
        Lesen und Klicken aendern -- eine Liste laedt nach, ein Banner
        geht auf, React baut den Baum neu. Dann ist entweder der Knoten
        weg (faellt bei isConnected durch) oder er steht noch, hat aber
        einen anderen Inhalt bekommen (faellt beim Fingerabdruck durch).
        Beides meldet, statt zu klicken. Denn "die Seite hat sich
        geaendert, lies neu" ist eine Antwort, mit der man arbeiten kann;
        ein Klick auf den falschen Knopf ist keine.
        """
        kennung = self._elemente.get(int(nummer), None)
        # koerper wird ANGEHAENGT und nicht eingesetzt: Er enthaelt bei
        # tippen() den Text des Benutzers, und ein Prozentzeichen darin
        # wuerde die Formatierung hier zerreissen.
        kopf = """
        (function () {
          var NR = %(nr)d, LAUF = %(lauf)d, SOLL = %(kennung)s;
          var s = window.__sarvis_bedienung;
          if (!s || s.lauf !== LAUF)
            return {ok: false, grund: 'liste_veraltet'};
          var el = s.knoten[NR - 1];
          if (!el) return {ok: false, grund: 'unbekannte_nummer'};
          if (!el.isConnected) return {ok: false, grund: 'element_weg'};
          if (!_sichtbar(el)) return {ok: false, grund: 'nicht_bedienbar'};
          var ist = _kennung(el);
          if (SOLL !== null && ist !== SOLL)
            return {ok: false, grund: 'element_veraendert', jetzt: ist};
        """ % {"nr": int(nummer), "lauf": self._lauf,
               "kennung": json.dumps(kennung)}
        return kopf + koerper + "\n})()"

    _GRUENDE = {
        "liste_veraltet": ("Die Elementliste ist nicht mehr gültig — die "
                           "Seite muss neu gelesen werden."),
        "unbekannte_nummer": "Diese Nummer gibt es auf der Seite nicht.",
        "element_weg": "Das Element ist nicht mehr auf der Seite.",
        "nicht_bedienbar": ("Das Element ist inzwischen unsichtbar oder "
                            "gesperrt."),
        "element_veraendert": ("An dieser Nummer steht jetzt ein anderes "
                              "Element — die Seite hat sich geändert."),
        "kein_feld": "Das ist kein Eingabefeld.",
    }

    def klicken(self, nummer: int, zeitlimit: float = ZEITLIMIT) -> dict:
        """Das Element mit dieser Nummer anklicken.

        Gibt zurueck:

            geklickt       bool  ob wirklich geklickt wurde
            nummer         int   die angefragte Nummer
            art            str   was es war ("knopf"/"link"/…), sonst ""
            text           str   seine Beschriftung, sonst ""
            absenden       bool  war es ein Absende-Knopf
            adresse_vorher str   Adresse vor dem Klick
            adresse        str   Adresse danach (kann dieselbe sein)
            navigiert      bool  adresse != adresse_vorher
            neues_fenster  bool  Link mit target=_blank -- siehe unten
            grund          str   bei geklickt=False: warum nicht, deutsch

        Findet sich das Element nicht mehr, wird gemeldet und NICHTS
        geklickt. Nicht das naechstbeste, nicht das mit derselben
        Beschriftung -- lieber eine Fehlmeldung als eine Ueberweisung.

        neues_fenster: Ein Link mit target=_blank verlangt vom Browser ein
        zweites Fenster. Diese QWebEnginePage macht keins auf, also
        passiert dann sichtbar nichts. Das steht im Ergebnis, damit es
        gesagt werden kann statt still zu scheitern.
        """
        koerper = """
          el.scrollIntoView({block: 'center', inline: 'center'});
          var vorher = location.href;
          var neu = (el.tagName.toLowerCase() === 'a'
                     && String(el.target || '') === '_blank');
          var beschriftung = _beschriftung(el, 80);
          var art = _art(el), abs = _absenden(el);
          el.click();
          return {ok: true, vorher: vorher, neues_fenster: neu,
                  text: beschriftung, art: art, absenden: abs};
        """
        gelungen, wert = self._js_daten(
            _JS_HILFE, self._element_skript(nummer, koerper), zeitlimit)
        antwort = {"geklickt": False, "nummer": int(nummer), "art": "",
                   "text": "", "absenden": False, "adresse_vorher": "",
                   "adresse": "", "navigiert": False, "neues_fenster": False,
                   "grund": ""}
        if not gelungen or not isinstance(wert, dict):
            antwort["grund"] = ("Die Seite hat auf den Klick nicht innerhalb "
                                f"von {zeitlimit:g} Sekunden geantwortet.")
            return antwort
        if not wert.get("ok"):
            schluessel = str(wert.get("grund") or "")
            antwort["grund"] = self._GRUENDE.get(
                schluessel, f"Der Klick ist nicht möglich ({schluessel}).")
            return antwort

        antwort.update({
            "geklickt": True,
            "art": str(wert.get("art") or ""),
            "text": str(wert.get("text") or ""),
            "absenden": bool(wert.get("absenden")),
            "adresse_vorher": str(wert.get("vorher") or ""),
            "adresse": str(wert.get("vorher") or ""),
            "neues_fenster": bool(wert.get("neues_fenster")),
        })
        # Kurz nachfassen, ob der Klick navigiert hat. Ein Schlaf ist hier
        # erlaubt und harmlos: Wir sind im Arbeitsfaden, die Qt-Schleife
        # laeuft weiter und laedt waehrenddessen.
        time.sleep(min(KLICK_NACHLAUF, max(0.0, float(zeitlimit))))
        ok2, jetzt = self._js("location.href", zeitlimit)
        if ok2 and isinstance(jetzt, str) and jetzt:
            antwort["adresse"] = jetzt
            antwort["navigiert"] = (jetzt != antwort["adresse_vorher"])
        if antwort["navigiert"]:
            # Nach einer Navigation ist die gelesene Liste Geschichte.
            # Sie hier zu verwerfen erspart einen Klick, der erst drueben
            # am Lauf-Vergleich scheitert.
            self._elemente = {}
        return antwort

    def tippen(self, nummer: int, text: str,
               zeitlimit: float = ZEITLIMIT) -> dict:
        """Text in ein Eingabefeld schreiben.

        Gibt zurueck:

            getippt      bool  ob geschrieben wurde
            nummer       int   die angefragte Nummer
            feldart      str   text/password/email/… bzw. "mehrzeilig"
            text         str   Beschriftung des Feldes
            wert_danach  str   was jetzt drinsteht; bei Passwortfeldern
                               nur Punkte, nie der Inhalt
            grund        str   bei getippt=False: warum nicht, deutsch

        Zwei Dinge passieren hier, die ein schlichtes el.value = "…"
        nicht tut:

        Der Wert wird ueber den NATIVEN Setter des Prototyps gesetzt.
        React haengt sich an die value-Eigenschaft des Elements und merkt
        sich den letzten Wert, den es selbst geschrieben hat. Setzt man
        value direkt, sieht React seinen alten Wert, haelt das Ereignis
        fuer eine Wiederholung und verwirft es -- das Feld sieht gefuellt
        aus und das Formular ist leer.

        Danach werden input und change ausgeloest, beide mit bubbles.
        Ohne sie laeuft keine Validierung, keine Suchvorschlagsliste,
        kein v-model.

        Enter wird NICHT gedrueckt. Ein Formular mit einem einzigen
        Textfeld wuerde damit abgesendet -- und Absenden ist eine
        Handlung, die ueber klicken() und damit ueber die Rueckfrage
        laufen soll, nicht als Nebenwirkung des Tippens.
        """
        # Sehr lange Texte abschneiden: Der String geht als Skript durch
        # die Bruecke, und ein Roman im Suchfeld ist kein Anwendungsfall.
        text = str(text or "")[:5000]
        koerper = """
          var TEXT = %(text)s;
          var art = _art(el);
          if (art !== 'feld' && art !== 'auswahl')
            return {ok: false, grund: 'kein_feld'};
          el.focus();
          if (el.isContentEditable) {
            el.textContent = TEXT;
          } else {
            var proto = Object.getPrototypeOf(el);
            var b = Object.getOwnPropertyDescriptor(proto, 'value');
            if (b && b.set) b.set.call(el, TEXT); else el.value = TEXT;
          }
          el.dispatchEvent(new Event('input', {bubbles: true}));
          el.dispatchEvent(new Event('change', {bubbles: true}));
          var fa = _feldart(el);
          var jetzt = el.isContentEditable ? (el.innerText || '')
                                           : String(el.value == null ? '' : el.value);
          return {ok: true, feldart: fa, text: _beschriftung(el, 80),
                  wert: fa === 'password' ? '' : jetzt,
                  laenge: jetzt.length};
        """ % {"text": json.dumps(text)}

        gelungen, wert = self._js_daten(
            _JS_HILFE, self._element_skript(nummer, koerper), zeitlimit)
        antwort = {"getippt": False, "nummer": int(nummer), "feldart": "",
                   "text": "", "wert_danach": "", "grund": ""}
        if not gelungen or not isinstance(wert, dict):
            antwort["grund"] = ("Die Seite hat auf die Eingabe nicht "
                                f"innerhalb von {zeitlimit:g} Sekunden "
                                "geantwortet.")
            return antwort
        if not wert.get("ok"):
            schluessel = str(wert.get("grund") or "")
            antwort["grund"] = self._GRUENDE.get(
                schluessel, f"Die Eingabe ist nicht möglich ({schluessel}).")
            return antwort

        feldart = str(wert.get("feldart") or "")
        laenge = int(wert.get("laenge") or 0)
        antwort.update({
            "getippt": True,
            "feldart": feldart,
            "text": str(wert.get("text") or ""),
            # Bei einem Passwortfeld nur die Laenge zeigen. Der Wert
            # ginge sonst zurueck in den Kontext und in den Verlauf.
            "wert_danach": ("•" * laenge if feldart == "password"
                            else str(wert.get("wert") or "")),
        })
        return antwort

    # --- Ansicht ----------------------------------------------------------

    def zoom(self, faktor: float) -> float:
        """Die Seite groesser oder kleiner stellen; gibt den neuen Wert.

        Begrenzt auf ZOOM_MIN..ZOOM_MAX. Qt liesse mehr zu, aber ein
        Zoom, den man mit blossem Auge nicht mehr lesen kann, ist keine
        Einstellung, sondern ein Unfall -- und zurueckstellen kann ihn
        nur, wer noch etwas erkennt.
        """
        try:
            wunsch = float(faktor)
        except (TypeError, ValueError):
            wunsch = 1.0
        wunsch = max(ZOOM_MIN, min(ZOOM_MAX, wunsch))

        def setzen():
            self.ansicht.setZoomFactor(wunsch)
            return float(self.ansicht.zoomFactor())

        gelungen, wert = self._wert_holen(setzen)
        return float(wert) if gelungen and wert is not None else wunsch

    def suchen(self, text: str) -> None:
        """Auf der Seite suchen und die Treffer hervorheben.

        findText ist von sich aus asynchron und liefert seinen Befund an
        einen Rueckruf -- den brauchen wir hier nicht: Was gefunden
        wurde, sieht man auf der Seite. Ein leerer Text loescht die
        Hervorhebung, das ist Qt-Verhalten und hier erwuenscht.
        """
        text = str(text or "")

        def suche():
            seite = self.ansicht.page()
            if seite is not None:
                seite.findText(text)

        self._im_qt_faden(suche)

    # --- Herunterladen ----------------------------------------------------

    def herunterladen_annehmen(self, ordner=None) -> str:
        """Downloads ohne Dialog in einen festen Ordner annehmen.

        Ohne das hier passiert bei einem Download gar nichts: Qt fragt
        ueber downloadRequested, und wer nicht antwortet, dessen Download
        gilt als abgelehnt. Ein Fenster mit "Speichern unter" gibt es in
        dieser Engine nicht.

        Der vorgeschlagene Dateiname kommt aus dem Content-Disposition-Kopf
        der Seite und ist damit FREMDE EINGABE. Er wird gesaeubert
        (_dateiname_saeubern) und der zusammengesetzte Pfad danach noch
        einmal geprueft (_freier_pfad, plus ein Vergleich gegen das, was
        Qt daraus tatsaechlich macht). Passt etwas nicht, wird der
        Download abgebrochen statt geschrieben.

        Gibt den Ordner als String zurueck. Kann mehrfach gerufen werden;
        das Signal wird nur einmal je Profil verbunden.
        """
        ziel = Path(ordner) if ordner else DOWNLOAD_ORDNER
        ziel = ziel.resolve()

        def einhaengen():
            profil = Browser._profil_holen()
            Browser._download_ordner = ziel
            ziel.mkdir(parents=True, exist_ok=True)
            # Nur einmal je Profil verbinden -- sonst laeuft ein Download
            # nach dem zweiten Aufruf zweimal durch die Annahme, und der
            # zweite Durchgang trifft eine Anfrage, die schon angenommen
            # ist.
            if Browser._download_profil is not profil:
                profil.downloadRequested.connect(Browser._download_angefragt)
                Browser._download_profil = profil
            return str(ziel)

        gelungen, wert = self._wert_holen(einhaengen)
        return str(wert) if gelungen and wert else str(ziel)

    @classmethod
    def _download_angefragt(cls, anfrage) -> None:
        """Ein Download klopft an: Namen saeubern, Ziel pruefen, annehmen."""
        ordner = cls._download_ordner or DOWNLOAD_ORDNER
        roh = anfrage.suggestedFileName() or anfrage.downloadFileName() or ""
        name = _dateiname_saeubern(roh)
        pfad = _freier_pfad(Path(ordner), name)
        if pfad is None:
            anfrage.cancel()
            return

        anfrage.setDownloadDirectory(str(ordner))
        anfrage.setDownloadFileName(pfad.name)

        # Zweiter Riegel, und zwar auf dem, was QT zusammengesetzt hat --
        # nicht auf dem, was wir hineingegeben haben. Zwischen beidem
        # koennte Qt noch etwas tun, und geprueft gehoert der Pfad, der
        # geschrieben wird.
        gesetzt = (Path(anfrage.downloadDirectory())
                   / anfrage.downloadFileName())
        try:
            gesetzt.resolve().relative_to(Path(ordner).resolve())
        except (ValueError, OSError):
            anfrage.cancel()
            return

        anfrage.accept()
        # Erst beim Ende merken, nicht beim Start: Ein abgebrochener
        # Download stuende sonst mit einem Pfad in der Liste, unter dem
        # nichts liegt.
        anfrage.isFinishedChanged.connect(
            lambda a=anfrage: cls._download_beendet(a))

    @classmethod
    def _download_beendet(cls, anfrage) -> None:
        if not anfrage.isFinished():
            return
        zustand = anfrage.state()
        wie = {
            QWebEngineDownloadRequest.DownloadCompleted: "fertig",
            QWebEngineDownloadRequest.DownloadCancelled: "abgebrochen",
            QWebEngineDownloadRequest.DownloadInterrupted: "abgerissen",
        }.get(zustand, "unklar")
        cls._downloads.append({
            "name": str(anfrage.downloadFileName()),
            "pfad": str(Path(anfrage.downloadDirectory())
                        / anfrage.downloadFileName()),
            "adresse": str(anfrage.url().toString()),
            "bytes": int(anfrage.receivedBytes() or 0),
            "zustand": wie,
            "zeit": time.time(),
        })
        del cls._downloads[:-DOWNLOAD_GEDAECHTNIS]

    def downloads(self) -> list:
        """Die zuletzt beendeten Downloads, aeltester zuerst.

        Je Eintrag: name, pfad, adresse, bytes, zustand ("fertig",
        "abgebrochen", "abgerissen"), zeit (Unix-Zeit). Eine Kopie --
        die Liste wird aus dem Qt-Faden gefuellt, und wer darueber
        laeuft, waehrend etwas ankommt, bekaeme sonst eine Ueberraschung.
        """
        return list(Browser._downloads)

    # --- Fenster bedienen -------------------------------------------------

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

        # Griffpunkte links vor dem Titel. Die Kopfleiste war schon immer
        # die Anfassleiste -- man sah es ihr nur nicht an, und der Nutzer
        # hat es nicht gefunden. Von den moeglichen Hinweisen ist das der
        # leiseste: Ein Wort wie "ziehen" waere Text, den man beim
        # zweiten Mal nur noch wegliest, ein durchgehender Streifen
        # nimmt dem Titel den Platz. Sechs Punkte sind das Zeichen, das
        # aus jeder Werkzeugleiste bekannt ist, und sie stehen genau
        # dort, wo man hinfasst.
        griff = QColor(RAHMEN)
        griff.setAlphaF(0.38)
        p.setPen(Qt.NoPen)
        p.setBrush(griff)
        for sx in (0, 5):
            for sy in (0, 5, 10):
                p.drawEllipse(QRectF(11 + sx, KOPF / 2 - 7 + sy, 2.2, 2.2))
        p.setBrush(Qt.NoBrush)

        f = QFont("Segoe UI", 8)
        f.setLetterSpacing(QFont.PercentageSpacing, 120)
        p.setFont(f)
        c = QColor(RAHMEN)
        c.setAlphaF(0.92)
        p.setPen(c)
        p.drawText(QRectF(28, 0, self.width() - 166, KOPF),
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
