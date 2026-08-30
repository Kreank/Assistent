"""Der Browser ohne Kopf -- Nachfolger von browser.py auf dem Server.

Auf dem Dev-PC war der Browser ein Fenster: 1.321 Zeilen, davon rund die
Haelfte Qt (Rahmen, Kopfleiste, Groessengriff, Deckkraft) und die andere
Haelfte DOM. Auf dem Server gibt es kein Fenster und kein Qt. Die
Qt-Haelfte faellt damit weg; die DOM-Haelfte ist die Substanz und steht
hier fast unveraendert wieder.

WAS BLEIBT, UND WARUM

  _JS_HILFE ist woertlich uebernommen. Es bestimmt zu jedem Element
  "im_formular" und "absenden" -- beides aus dem DOM (el.form,
  el.closest('form'), el.type), nicht aus der Beschriftung, weil ein
  Knopf mit "Abbrechen" trotzdem der Absende-Knopf sein kann. Daran
  haengt die Rueckfragestufe in hirn._browserstufe.

  Die Lauf-Nummer und der Fingerabdruck (_kennung) bleiben. Beim Klicken
  wird gegen den Fingerabdruck AUS DEM LESEN verglichen. Ein Neulesen
  wuerde genau diese Wache abschalten -- das ist Sicherheit, kein
  Komfort.

  Beim Tippen wird der native Prototyp-Setter benutzt (Reacts
  value-Tracking merkt sonst nichts), input und change feuern mit
  bubbles, und Enter wird nicht gedrueckt.

WAS ANDERS IST

  KEIN QT-FADEN MEHR. browser.py musste jeden JS-Aufruf ueber
  _im_qt_faden/_js_daten in den Anzeigefaden schieben und mit einem
  threading.Event auf die Antwort warten. CDP ist von Haus aus
  asynchron: _senden() ist ein await, fertig. Rund 200 Zeilen
  Faden-Bruecke entfallen ersatzlos.

  EIGENE WELT STATT SEITEN-WELT. Qts runJavaScript lief in der Welt der
  Seite. Dort konnte die Seite unsere Hilfsfunktionen ueberschreiben --
  ein Skript, das Element.prototype.closest ersetzt, haette _absenden()
  belogen und damit die Rueckfrage ausgehebelt. Hier laeuft alles in
  einer eigenen, abgeschirmten Welt (Page.createIsolatedWorld). Dieselben
  DOM-Knoten, aber unsere Funktionen und unser window; die Seite kommt
  nicht daran. Der Fingerabdruck ist damit erst wirklich eine Wache.

  DOWNLOADS SAEUBERT CHROME. browser.py bekam von Qt den rohen
  Dateinamen aus dem Content-Disposition-Kopf und musste ihn selbst
  entschaerfen (_dateiname_saeubern, _freier_pfad -- zwei Riegel gegen
  "..\\..\\sarvis\\config.py"). Chrome nimmt den Namen gar nicht erst
  roh: Es saeubert selbst, haengt bei Namensgleichheit " (1)" an und
  schreibt ausschliesslich in den mit Browser.setDownloadBehavior
  gesetzten Ordner. Die beiden Riegel sind damit doppelt gemoppelt und
  fallen weg -- nicht aus Nachlaessigkeit, sondern weil der Angreifer
  jetzt eine Chrome-Luecke braeuchte und nicht mehr einen Fehler von uns.

WARUM CDP UND NICHT PLAYWRIGHT

  Gemessen an dem, was hier gebraucht wird: browser.py macht ALLES ueber
  ausgewertetes JavaScript. Es gibt keinen einzigen Selektor, kein
  auto-waiting, kein Locator-Gebastel -- also genau das, wofuer man
  Playwright nimmt, braucht dieser Browser nicht. Uebrig bleiben
  Runtime.evaluate, Page.navigate und Page.captureScreenshot, und die
  sind roh nicht schwerer als durch eine Bibliothek.

  Dagegen steht, was Playwright kostet: das Rad plus den Node-Treiber
  (rund 130 MB), und ohne executable_path noch ein eigenes Chromium
  (rund 300 MB) neben dem Chrome, das ohnehin ins Image muss. Das Image
  ist heute 6,18 GB; jede vermeidbare Schicht ist eine zu viel.

  Und ein dritter Punkt, der den Ausschlag gab: PIPE STATT PORT.
  Playwright kann es auch, aber roh ist es hier ohnehin geschenkt --
  Chrome bekommt --remote-debugging-pipe und redet ueber die
  Dateideskriptoren 3 und 4. KEIN Port. Das ist wichtig, weil der
  Container mit network_mode: host laeuft: ein
  --remote-debugging-port=9222 waere der Loopback des GANZEN Servers,
  und jeder Prozess darauf koennte diesen Browser fernsteuern -- einen
  Browser, der in Saschas Konten angemeldet ist. Die Pipe hat kein
  Publikum.

  Neue Abhaengigkeit: keine. Nur Standardbibliothek.

WANN ER LAEUFT

  ERST BEIM GEBRAUCH, DANN BIS ES RUHIG WIRD. Ein dauerhaft offener
  Chrome kostet 300 bis 500 MB. Der Server hat 30 GB und dreissig andere
  Container -- das ist kein Drama, aber es ist auch nichts, was man
  einfach so liegen laesst fuer ein Werkzeug, das ein paarmal am Tag
  gebraucht wird. Also: Der erste Aufruf startet ihn (rund eine Sekunde),
  und RUHE Sekunden nach dem letzten Aufruf hoert er wieder auf.

  Verloren geht dabei nichts, was zaehlt: Die Anmeldungen liegen als
  Cookies im Profil auf der Platte und ueberleben. Was nicht ueberlebt,
  ist "die offene Seite" -- nach zehn Minuten Pause ist nichts mehr
  offen, und web_lesen sagt das dann auch. Zehn Minuten sind laenger als
  jedes Gespraech, in dem noch von derselben Seite die Rede ist.

EIGENES PROFIL

  BROWSER_PROFIL, wie gehabt. Dies ist nicht Saschas Chrome und auch
  nicht der Chrome irgendeines anderen Dienstes auf dieser Maschine.
  Er laeuft dauerhaft und ist womoeglich angemeldet -- ein geteiltes
  Profil hiesse, dass zwei Programme sich gegenseitig die Sitzung
  umschreiben, und Chrome laesst ein Profil ohnehin nur einmal offen.
"""
import asyncio
import json
import os
import shutil
import socket
import threading
import time

from .. import config

# --- Grenzen fuers Lesen ---------------------------------------------------
# Unveraendert aus browser.py, samt Begruendung: Der ganze Text landet
# erst einmal bei Claude, und eine Nachrichtenseite hat leicht 60.000
# Zeichen. Gekuerzt wird MIT sichtbarer Markierung -- ein stummer Schnitt
# kommt als vollstaendige Seite an und wird als solche vorgelesen.
LESE_GRENZE = 4000

# Hoechstens so viele Elemente. Vierzig nummerierte Eintraege sind schon
# viel zum Vorlesen; hundert waeren eine Wand.
ELEMENT_GRENZE = 40
ELEMENT_TEXT_MAX = 80      # Beschriftung je Element

# Zeitlimit fuer ein Skript auf der Seite.
ZEITLIMIT = 5.0

# Wie lange nach einem Klick auf eine Navigation gewartet wird. Kurz: Wir
# wollen nur wissen, OB sich die Adresse aendert, nicht auf das fertige
# Laden warten.
KLICK_NACHLAUF = 0.8

# Wie lange auf eine frisch geladene Seite gewartet wird. Grosszuegiger
# als ZEITLIMIT -- hier haengt es am Netz und an der Gegenseite, nicht an
# uns. Laeuft es ab, wird trotzdem gelesen: Eine halb geladene Seite hat
# meistens schon den Text, auf den es ankommt.
LADE_ZEITLIMIT = 20.0

# Nach so vielen Sekunden ohne Auftrag hoert der Browser wieder auf.
# Siehe Modulkopf, "Wann er laeuft".
RUHE = 600.0

# Das Fenster, das es nicht gibt. Feste Masse, damit zweierlei
# reproduzierbar ist: was _sichtbar() ueber getBoundingClientRect zu
# sehen bekommt, und wie breit das Bild aus web_ansehen wird.
FENSTER_BREITE, FENSTER_HOEHE = 1280, 900

# Das Bild fuer web_ansehen. WebP statt PNG: Ein Vollbild-PNG dieser
# Groesse sind schnell 1 bis 2 MB, dasselbe als WebP bei Qualitaet 70
# liegt bei 60 bis 200 KB. Ueber Mobilfunk ist das der Unterschied
# zwischen "da" und "gleich".
BILD_GUETE = 70
BILD_GUETE_NOTFALL = 40    # zweiter Versuch, wenn das erste Bild zu gross war
# Der Draht deckelt bei 4 MB. Wir bleiben deutlich darunter, denn die
# base64-Fassung ist um ein Drittel groesser als das Bild selbst.
BILD_GRENZE = 2_500_000

# Wohin Downloads gehen. Ein eigener Ordner, damit an EINER Stelle
# nachzusehen (und aufzuraeumen) ist, was von fremden Seiten auf der
# Platte gelandet ist. Unter DATEN und nicht unter WURZEL: Der Quelltext
# ist im Container ein Bind-Mount vom Host, dort haben Downloads nichts
# verloren.
DOWNLOAD_ORDNER = config.DATEN / "browser-downloads"

# So viele abgeschlossene Downloads werden gemerkt. Die Liste ist eine
# Gedaechtnisstuetze fuer "wo liegt das jetzt", kein Archiv.
DOWNLOAD_GEDAECHTNIS = 50

# Wo Chrome steckt. Erst die Umgebung (damit ein anderes Image nichts
# umschreiben muss), dann die ueblichen Namen.
_KANDIDATEN = ("/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
               "/usr/bin/chromium", "/usr/bin/chromium-browser")


def chrome_finden() -> str:
    """Den Pfad zum Browser -- oder "" , wenn keiner da ist."""
    aus_umgebung = os.environ.get("SARVIS_CHROME", "").strip()
    if aus_umgebung and os.path.exists(aus_umgebung):
        return aus_umgebung
    for pfad in _KANDIDATEN:
        if os.path.exists(pfad):
            return pfad
    gefunden = shutil.which("google-chrome") or shutil.which("chromium")
    return gefunden or ""


# --- Was im Browser laeuft -------------------------------------------------
# WOERTLICH aus browser.py. Diese Hilfsfunktionen stehen VOR jedem Skript,
# statt einmal an window zu haengen: Ein window-Zustand ueberlebt keine
# Navigation, und ein Skript, dessen Haelfte auf der vorigen Seite lag,
# scheitert dann mit einem ReferenceError statt mit einer Meldung, die man
# vorlesen kann.
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


class _Draht:
    """CDP ueber die Pipe: JSON-Nachrichten, mit \\0 getrennt.

    Chrome bekommt --remote-debugging-pipe und liest dann von
    Dateideskriptor 3, schreibt auf 4. Die beiden dorthin zu bekommen
    geht ohne preexec_fn: Wir haengen die Pipes an stdin und stdout und
    lassen eine winzige sh die Umlegung machen. preexec_fn waere in
    einem Prozess mit Faeden ein Risiko -- zwischen fork und exec darf
    kein Python laufen, das eine Sperre braucht.
    """

    def __init__(self):
        self._prozess = None
        self._schreiben = None       # asyncio-Transport
        self._id = 0
        self._offen: dict[int, asyncio.Future] = {}
        self._horcher = []           # (praedikat, future) fuer Ereignisse
        self._laufend = []           # Handler(methode, params, sitzung)
        self._lesefaden = None

    # --- Starten und Beenden ---------------------------------------------

    async def starten(self, binaer: str, argumente: list[str]) -> None:
        r_zu_chrome, w_von_uns = os.pipe()
        r_zu_uns, w_von_chrome = os.pipe()

        # stdin -> fd 3, stdout -> fd 4, danach 0 und 1 ins Leere. Chrome
        # schreibt seine eigenen Meldungen sonst in unsere CDP-Leitung.
        huelle = ["/bin/sh", "-c",
                  'exec 3<&0 4>&1 0</dev/null 1>/dev/null; exec "$@"',
                  "sh", binaer] + argumente
        self._prozess = await asyncio.create_subprocess_exec(
            *huelle, stdin=r_zu_chrome, stdout=w_von_chrome,
            stderr=asyncio.subprocess.DEVNULL, start_new_session=True)
        os.close(r_zu_chrome)
        os.close(w_von_chrome)

        schleife = asyncio.get_running_loop()
        # GEMESSEN, und es kostete den ersten Testlauf: StreamReader hat
        # eine Vorgabegrenze von 64 KB, und readuntil() wirft darueber
        # LimitOverrunError. Eine CDP-Nachricht ist regelmaessig groesser
        # -- ein WebP-Bildschirmfoto als base64 sind schnell 200 KB, eine
        # Elementliste auch mal 80. Der Lesefaden waere dann still
        # gestorben und JEDE weitere Antwort ausgeblieben. Deshalb ein
        # grosser Puffer und unten das Trennen von Hand statt readuntil.
        leser = asyncio.StreamReader(limit=8 * 1024 * 1024)
        await schleife.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(leser),
            os.fdopen(r_zu_uns, "rb", 0))
        self._schreiben, _ = await schleife.connect_write_pipe(
            asyncio.Protocol, os.fdopen(w_von_uns, "wb", 0))
        self._lesefaden = asyncio.ensure_future(self._lesen(leser))

    def laeuft(self) -> bool:
        return (self._prozess is not None
                and self._prozess.returncode is None
                and self._schreiben is not None)

    async def beenden(self) -> None:
        if self._lesefaden is not None:
            self._lesefaden.cancel()
            self._lesefaden = None
        if self._schreiben is not None:
            try:
                self._schreiben.close()
            except Exception:
                pass
            self._schreiben = None
        p, self._prozess = self._prozess, None
        if p is not None and p.returncode is None:
            try:
                p.terminate()
                await asyncio.wait_for(p.wait(), 5.0)
            except (asyncio.TimeoutError, ProcessLookupError):
                try:
                    p.kill()
                except ProcessLookupError:
                    pass
        for zukunft in list(self._offen.values()):
            if not zukunft.done():
                zukunft.set_exception(ConnectionError("Browser ist weg."))
        self._offen.clear()

    # --- Lesen und Schreiben ---------------------------------------------

    async def _lesen(self, leser: asyncio.StreamReader) -> None:
        """Der Lesefaden: Stuecke holen, an \\0 trennen, verteilen.

        Von Hand statt readuntil, weil readuntil eine Groessengrenze hat
        und eine ueberschrittene Grenze eine Ausnahme ist -- also der
        eine Ort, an dem ein zu grosses Bild die ganze Leitung
        stillgelegt haette.
        """
        puffer = bytearray()
        try:
            while True:
                stueck = await leser.read(65536)
                if not stueck:
                    break                      # Chrome ist weg
                puffer += stueck
                while True:
                    schnitt = puffer.find(b"\0")
                    if schnitt < 0:
                        break
                    roh, puffer = bytes(puffer[:schnitt]), puffer[schnitt + 1:]
                    try:
                        nachricht = json.loads(roh.decode("utf-8"))
                    except (ValueError, UnicodeDecodeError):
                        continue
                    self._verteilen(nachricht)
        except (asyncio.CancelledError, ConnectionError):
            pass
        except Exception:
            pass

    def _verteilen(self, nachricht: dict) -> None:
        kennung = nachricht.get("id")
        if kennung is not None:
            zukunft = self._offen.pop(kennung, None)
            if zukunft is not None and not zukunft.done():
                zukunft.set_result(nachricht)
            return
        methode = str(nachricht.get("method") or "")
        params = nachricht.get("params") or {}
        sitzung = nachricht.get("sessionId") or ""
        for handler in list(self._laufend):
            try:
                handler(methode, params, sitzung)
            except Exception:
                pass
        for eintrag in list(self._horcher):
            praedikat, zukunft = eintrag
            if zukunft.done():
                self._horcher.remove(eintrag)
                continue
            try:
                if praedikat(methode, params, sitzung):
                    self._horcher.remove(eintrag)
                    zukunft.set_result((methode, params))
            except Exception:
                pass

    def bei_ereignis(self, handler) -> None:
        """Einen Dauerhorcher anmelden: handler(methode, params, sitzung)."""
        self._laufend.append(handler)

    def horchen(self, praedikat):
        """Auf EIN Ereignis lauschen -- SOFORT angemeldet.

        Gibt die Zukunft zurueck, statt schon zu warten. Der Unterschied
        ist nicht kosmetisch: Wer erst den Befehl schickt und dann
        anmeldet, verpasst ein Ereignis, das schneller war als er. Genau
        das passiert bei Page.navigate auf eine Seite aus dem Zwischen-
        speicher.
        """
        zukunft = asyncio.get_running_loop().create_future()
        self._horcher.append((praedikat, zukunft))
        return zukunft

    async def warten_auf(self, praedikat, sekunden: float):
        """Auf EIN Ereignis warten. Gibt None zurueck, wenn es ausbleibt."""
        zukunft = self.horchen(praedikat)
        try:
            return await asyncio.wait_for(zukunft, sekunden)
        except asyncio.TimeoutError:
            return None

    async def senden(self, methode: str, params: dict | None = None,
                     sitzung: str = "", sekunden: float = 20.0) -> dict:
        """Einen CDP-Befehl schicken und auf die Antwort warten.

        Wirft ConnectionError, wenn der Browser weg ist, und RuntimeError
        mit der Chrome-Meldung, wenn der Befehl abgelehnt wurde. Beides
        faengt der Aufrufer ab und macht einen deutschen Satz daraus.
        """
        if not self.laeuft():
            raise ConnectionError("Browser laeuft nicht.")
        self._id += 1
        kennung = self._id
        paket = {"id": kennung, "method": methode, "params": params or {}}
        if sitzung:
            paket["sessionId"] = sitzung
        zukunft = asyncio.get_running_loop().create_future()
        self._offen[kennung] = zukunft
        try:
            self._schreiben.write(
                json.dumps(paket).encode("utf-8") + b"\0")
        except Exception as e:
            self._offen.pop(kennung, None)
            raise ConnectionError(str(e)) from e
        try:
            antwort = await asyncio.wait_for(zukunft, sekunden)
        except asyncio.TimeoutError:
            self._offen.pop(kennung, None)
            raise TimeoutError(f"{methode} hat nicht geantwortet.")
        if "error" in antwort:
            fehler = antwort["error"] or {}
            raise RuntimeError(str(fehler.get("message") or fehler))
        return antwort.get("result") or {}


class Kopfbrowser:
    """Eine Seite, die Sarvis lesen und bedienen kann -- ohne Bildschirm."""

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

    def __init__(self):
        self._draht = _Draht()
        self._sitzung = ""        # CDP-Sitzung der einen offenen Seite
        self._ziel = ""           # deren targetId
        self._welt = None         # executionContextId unserer eigenen Welt
        self._lauf = 0            # Lauf-Nummer der Elementliste
        self._elemente: dict[int, str] = {}   # Nummer -> Fingerabdruck
        self._downloads: list[dict] = []
        self._download_namen: dict[str, str] = {}   # guid -> Dateiname
        self._neue_ziele: list[str] = []            # von uns geoeffnete Popups
        self._schloss = asyncio.Lock()
        self._zuletzt = 0.0
        self._waechter = None
        self._sandkasten = True   # beim ersten Fehlschlag auf False

    # --- Leben ------------------------------------------------------------

    @property
    def offen(self) -> bool:
        return bool(self._draht.laeuft() and self._sitzung)

    def _anfassen(self) -> None:
        self._zuletzt = time.monotonic()

    async def _sicherstellen(self) -> None:
        """Chrome starten, falls er nicht (mehr) laeuft."""
        self._anfassen()
        if self.offen:
            return
        binaer = chrome_finden()
        if not binaer:
            raise RuntimeError(
                "Auf diesem Rechner ist kein Chrome installiert — ohne den "
                "kann ich keine Seite lesen.")
        if self._draht.laeuft():
            await self._draht.beenden()
        try:
            await self._hochfahren(binaer)
        except Exception:
            # Genau EIN zweiter Versuch ohne Sandkasten. Chrome braucht
            # dafuer Benutzer-Namensraeume; ob der Container sie hergibt,
            # haengt an Seccomp und Kernel und laesst sich nicht raten.
            # Erst probieren, was sicherer ist -- und den Ausweg nehmen,
            # wenn es nicht geht, statt gar keinen Browser zu haben.
            if not self._sandkasten:
                raise
            self._sandkasten = False
            await self._draht.beenden()
            await self._hochfahren(binaer)

    async def _hochfahren(self, binaer: str) -> None:
        profil = config.BROWSER_PROFIL
        profil.mkdir(parents=True, exist_ok=True)
        DOWNLOAD_ORDNER.mkdir(parents=True, exist_ok=True)
        argumente = [
            "--headless=new",
            "--remote-debugging-pipe",
            f"--user-data-dir={profil}",
            f"--window-size={FENSTER_BREITE},{FENSTER_HOEHE}",
            "--no-first-run", "--no-default-browser-check",
            # Ohne GPU -- der Server hat eine, aber Ollama braucht sie,
            # und zum Lesen von Text hilft sie nicht.
            "--disable-gpu",
            # /dev/shm ist in Docker 64 MB gross. Chrome legt dort seine
            # Renderer-Puffer ab und stirbt sonst mitten auf grossen
            # Seiten, ohne dass es nach einem Speicherproblem aussieht.
            "--disable-dev-shm-usage",
            "--hide-scrollbars",
            "--lang=de-DE",
            # DAS WICHTIGSTE FLAG IN DIESER LISTE, und es sieht nicht so
            # aus. Ohne es sucht Chrome beim ersten Netzzugriff ueber
            # D-Bus einen Schluesselbund (gnome-keyring, KWallet) fuer
            # seinen Passwortspeicher. Auf einem Server gibt es keinen,
            # und Chrome merkt das nicht schnell, sondern nach einem
            # Zeitablauf. GEMESSEN, dreimal hintereinander: die erste
            # Navigation zu example.com brauchte 25,04 s, die zweite
            # 0,07 s -- mit --password-store=basic 0,05 s und 0,05 s.
            # Ein halbes Werkzeug, das in jeder zweiten Sitzung
            # "die Seite hat nicht geantwortet" meldet, waere daran
            # gescheitert, und niemand haette es bei Chrome gesucht.
            "--password-store=basic",
            "--disable-features=Translate,MediaRouter,OptimizationHints",
            "--disable-background-networking",
            "--mute-audio",
            "about:blank",
        ]
        if not self._sandkasten:
            argumente.insert(0, "--no-sandbox")
        await self._draht.starten(binaer, argumente)
        self._draht.bei_ereignis(self._ereignis)

        # Downloads: browserweit, mit Ereignissen. Der Ordner ist der
        # einzige, in den Chrome schreiben darf; den Dateinamen saeubert
        # Chrome selbst (siehe Modulkopf).
        await self._draht.senden("Browser.setDownloadBehavior", {
            "behavior": "allow", "downloadPath": str(DOWNLOAD_ORDNER),
            "eventsEnabled": True})
        await self._draht.senden("Target.setDiscoverTargets",
                                 {"discover": True})

        # Wir sind Chrome, und wir sagen es auch so. Das Wort "Headless"
        # in der Kennung beschreibt nur, dass kein Fenster aufgeht -- fuer
        # die Gegenseite ist es ein Grund, eine Sperrseite auszuliefern,
        # und die waere dann das, was Sarvis vorliest. Mehr wird an der
        # Kennung nicht gedreht: Wir geben uns nicht als Firefox aus.
        try:
            fassung = await self._draht.senden("Browser.getVersion", {})
            self._kennung = str(fassung.get("userAgent") or "").replace(
                "HeadlessChrome", "Chrome")
        except Exception:
            self._kennung = ""

        await self._seite_anlegen()

    async def _seite_anlegen(self, ziel: str = "") -> None:
        """Eine Seite zur GEZEIGTEN machen -- neu oder eine uebernommene."""
        if not ziel:
            antwort = await self._draht.senden(
                "Target.createTarget", {"url": "about:blank"})
            ziel = str(antwort.get("targetId") or "")
        antwort = await self._draht.senden(
            "Target.attachToTarget", {"targetId": ziel, "flatten": True})
        self._ziel = ziel
        self._sitzung = str(antwort.get("sessionId") or "")
        self._welt = None
        self._lauf += 1
        self._elemente = {}
        for befehl in ("Page.enable", "Runtime.enable", "DOM.enable"):
            await self._draht.senden(befehl, {}, self._sitzung)
        await self._draht.senden("Emulation.setDeviceMetricsOverride", {
            "width": FENSTER_BREITE, "height": FENSTER_HOEHE,
            "deviceScaleFactor": 1, "mobile": False}, self._sitzung)
        if getattr(self, "_kennung", ""):
            await self._draht.senden(
                "Emulation.setUserAgentOverride",
                {"userAgent": self._kennung, "acceptLanguage": "de-DE,de"},
                self._sitzung)

    def _ereignis(self, methode: str, params: dict, sitzung: str) -> None:
        """Was Chrome von sich aus meldet."""
        # Unsere eigene Welt ist weg -- bei jeder Navigation. Beim
        # naechsten Skript wird eine neue angelegt, und die gelesene
        # Elementliste ist damit von selbst ungueltig (window.__sarvis…
        # steckte in der alten Welt). Genau richtig.
        if methode in ("Runtime.executionContextsCleared",):
            self._welt = None
        elif methode == "Runtime.executionContextDestroyed":
            if params.get("executionContextId") == self._welt:
                self._welt = None
        elif methode == "Page.frameNavigated":
            rahmen = params.get("frame") or {}
            if not rahmen.get("parentId"):
                self._welt = None
                self._elemente = {}
        elif methode == "Target.targetCreated":
            info = params.get("targetInfo") or {}
            if (info.get("type") == "page"
                    and info.get("openerId") == self._ziel):
                self._neue_ziele.append(str(info.get("targetId")))
        elif methode == "Browser.downloadWillBegin":
            self._download_namen[str(params.get("guid"))] = str(
                params.get("suggestedFilename") or "")
        elif methode == "Browser.downloadProgress":
            zustand = str(params.get("state") or "")
            if zustand in ("completed", "canceled"):
                guid = str(params.get("guid"))
                name = self._download_namen.pop(guid, "")
                self._downloads.append({
                    "name": name,
                    "pfad": str(DOWNLOAD_ORDNER / name) if name else "",
                    "bytes": int(params.get("receivedBytes") or 0),
                    "zustand": ("fertig" if zustand == "completed"
                                else "abgebrochen"),
                    "zeit": time.time(),
                })
                del self._downloads[:-DOWNLOAD_GEDAECHTNIS]

    async def _waechter_lauf(self) -> None:
        """Aufhoeren, wenn eine Weile nichts mehr kam. Siehe Modulkopf."""
        try:
            while True:
                # Nicht haeufiger nachsehen als noetig -- und bei einer
                # kurz gestellten Ruhe (Test) nicht seltener als sie.
                await asyncio.sleep(max(1.0, min(30.0, RUHE / 4)))
                if not self._draht.laeuft():
                    return
                if time.monotonic() - self._zuletzt > RUHE:
                    async with self._schloss:
                        if time.monotonic() - self._zuletzt > RUHE:
                            await self._abbauen()
                    return
        except asyncio.CancelledError:
            pass

    def _waechter_wecken(self) -> None:
        if self._waechter is None or self._waechter.done():
            self._waechter = asyncio.ensure_future(self._waechter_lauf())

    async def _abbauen(self) -> None:
        await self._draht.beenden()
        self._sitzung = ""
        self._ziel = ""
        self._welt = None
        self._elemente = {}
        self._neue_ziele = []

    async def schliessen(self) -> None:
        """Seite zu -- und den Browser gleich mit.

        Auf dem Dev-PC hiess "zumachen": das Fenster verstecken, Chromium
        lief weiter. Hier sieht niemand ein Fenster, also gibt es keinen
        Grund, den Prozess weiterlaufen zu lassen; "zu" heisst zu, und
        die 300 bis 500 MB sind zurueck.
        """
        async with self._schloss:
            if self._waechter is not None:
                self._waechter.cancel()
                self._waechter = None
            await self._abbauen()

    # --- Skripte ----------------------------------------------------------

    async def _welt_holen(self) -> int:
        """Unsere eigene, von der Seite abgeschirmte Welt.

        Dieselben DOM-Knoten, aber ein eigenes window und eigene
        Prototypen. Die Seite kann darin nichts ueberschreiben -- und
        damit auch _absenden() und _kennung() nicht belaufen. In der Welt
        der Seite (so lief es unter Qt) waere der Fingerabdruck nur so
        vertrauenswuerdig wie die Seite selbst.
        """
        if self._welt is not None:
            return self._welt
        baum = await self._draht.senden("Page.getFrameTree", {}, self._sitzung)
        rahmen = ((baum.get("frameTree") or {}).get("frame") or {}).get("id")
        antwort = await self._draht.senden("Page.createIsolatedWorld", {
            "frameId": rahmen, "worldName": "sarvis",
            "grantUniveralAccess": False}, self._sitzung)
        self._welt = int(antwort.get("executionContextId"))
        return self._welt

    async def _js(self, ausdruck: str, zeitlimit: float = ZEITLIMIT,
                  geste: bool = False):
        """Ein Skript auswerten. Gibt (gelungen, Wert) zurueck."""
        try:
            welt = await self._welt_holen()
            antwort = await self._draht.senden("Runtime.evaluate", {
                "expression": ausdruck,
                "contextId": welt,
                "returnByValue": True,
                "userGesture": bool(geste),
            }, self._sitzung, zeitlimit)
        except Exception:
            return False, None
        if antwort.get("exceptionDetails"):
            return False, None
        ergebnis = antwort.get("result") or {}
        if "value" not in ergebnis:
            return False, None
        return True, ergebnis["value"]

    async def _js_daten(self, hilfe: str, ausdruck: str,
                        zeitlimit: float = ZEITLIMIT, geste: bool = False):
        return await self._js((hilfe + "\n" + ausdruck) if hilfe else ausdruck,
                              zeitlimit, geste)

    # --- Oeffnen ----------------------------------------------------------

    async def oeffnen(self, adresse: str,
                      zeitlimit: float = LADE_ZEITLIMIT) -> dict:
        """Eine Adresse in Sarvis' eigenem Browser laden.

        Gibt {ok, adresse, titel, grund}. Das Zeitlimit ist keine
        Bedingung, sondern ein Deckel: Laeuft es ab, wird trotzdem
        gelesen, was schon da ist. Eine Seite, deren letztes Zaehlpixel
        noch laedt, hat den Text laengst.
        """
        async with self._schloss:
            try:
                await self._sicherstellen()
            except Exception as e:
                # Kein Chrome, kein Start, kein Profil: alles drei ist ein
                # Satz, den man vorlesen kann, und keine Ausnahme, die
                # oben als Werkzeugabsturz ankommt.
                return {"ok": False, "grund": str(e)}
            self._waechter_wecken()
            if not self.offen:
                return {"ok": False, "grund": "Der Browser ist nicht da."}
            # Erst lauschen, dann losschicken -- siehe _Draht.horchen.
            geladen = self._draht.horchen(
                lambda m, p, s: (m == "Page.loadEventFired"
                                 and s == self._sitzung))
            try:
                antwort = await self._draht.senden(
                    "Page.navigate", {"url": adresse}, self._sitzung,
                    zeitlimit)
            except Exception as e:
                geladen.cancel()
                return {"ok": False,
                        "grund": f"Die Adresse ließ sich nicht öffnen: {e}"}
            if antwort.get("errorText"):
                geladen.cancel()
                return {"ok": False,
                        "grund": f"Die Seite kam nicht: "
                                 f"{antwort['errorText']}"}
            try:
                await asyncio.wait_for(geladen, zeitlimit)
            except asyncio.TimeoutError:
                # Kein Grund aufzugeben: Was schon da ist, wird gelesen.
                pass
            self._welt = None
            self._elemente = {}
            gelungen, wert = await self._js(
                "({titel: document.title || '', adresse: location.href})")
            if not gelungen or not isinstance(wert, dict):
                return {"ok": True, "adresse": adresse, "titel": "",
                        "grund": ""}
            return {"ok": True, "adresse": str(wert.get("adresse") or adresse),
                    "titel": str(wert.get("titel") or ""), "grund": ""}

    # --- Lesen ------------------------------------------------------------

    async def text_holen(self, zeitlimit: float = ZEITLIMIT) -> str:
        """Der sichtbare Text der Seite, mit Titel und Adresse davor.

        Wie in browser.py: innerText und nicht textContent -- textContent
        bringt auch <script> und <style> mit und ignoriert Umbrueche,
        innerText liefert das, was ein Mensch dort saehe.
        """
        if not self.offen:
            return ("Es ist gerade keine Seite offen. Sag mir die Adresse, "
                    "dann mache ich sie auf und lese sie.")
        self._anfassen()
        skript = """
        (function () {
          var t = document.body ? (document.body.innerText || '') : '';
          // Leerzeilenketten zusammenlegen: Eine gewoehnliche Seite
          // liefert sonst mehr Umbrueche als Text.
          t = t.replace(/[ \\t]+\\n/g, '\\n').replace(/\\n{3,}/g, '\\n\\n').trim();
          return {titel: document.title || '', adresse: location.href, text: t};
        })()
        """
        gelungen, wert = await self._js(skript, zeitlimit)
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

    async def elemente_holen(self, zeitlimit: float = ZEITLIMIT) -> list:
        """Die bedienbaren Elemente der Seite, nummeriert ab 1.

        Je Eintrag: nummer, art, text, im_formular, absenden, adresse,
        feldart, sichtbar, wert. im_formular und absenden kommen aus dem
        DOM, nicht aus der Beschriftung -- ein Knopf mit "Weiter" kann
        absenden, einer mit "Absenden" kann ein reines JavaScript sein.

        Die Fingerabdruecke bleiben hier und gehen NICHT mit hinaus: Sie
        sind Innenleben fuer klicken/tippen, nicht Information fuer den,
        der die Liste vorliest.
        """
        if not self.offen:
            return []
        self._anfassen()
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
          // passen, eine Referenz nie. Was hier an window haengt, haengt
          // an UNSEREM window (eigene Welt) -- die Seite kommt nicht
          // daran, und eine Navigation raeumt es von selbst weg.
          window.__sarvis_bedienung = {lauf: LAUF, knoten: knoten};
          return {liste: liste, gesamt: gesamt,
                  titel: document.title || '', adresse: location.href};
        })()
        """ % {"grenze": ELEMENT_GRENZE, "max": ELEMENT_TEXT_MAX,
               "lauf": self._lauf, "auswahl": json.dumps(_JS_AUSWAHL)}

        gelungen, wert = await self._js_daten(_JS_HILFE, ausdruck, zeitlimit)
        if not gelungen or not isinstance(wert, dict):
            self._elemente = {}
            return [{"nummer": 0, "art": "hinweis",
                     "text": ("Die Seite hat die Elemente nicht innerhalb "
                              f"von {zeitlimit:g} Sekunden geliefert."),
                     "im_formular": False, "absenden": False, "adresse": "",
                     "feldart": "", "sichtbar": False, "wert": ""}]

        liste = list(wert.get("liste") or [])
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
        weg (isConnected) oder er hat einen anderen Inhalt bekommen
        (Fingerabdruck). Beides meldet, statt zu klicken. Denn "die Seite
        hat sich geaendert, lies neu" ist eine Antwort, mit der man
        arbeiten kann; ein Klick auf den falschen Knopf ist keine.

        Ein Neulesen an dieser Stelle wuerde genau diese Wache
        abschalten. Es steht deshalb nicht zur Debatte.
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

    async def element_frisch(self, nummer: int,
                             zeitlimit: float = ZEITLIMIT) -> dict:
        """Das Element hinter einer Nummer -- FRISCH aus dem DOM.

        Das ist die Auskunft, auf der hirn._browserstufe seine
        Rueckfrage-Entscheidung baut. Sie darf nicht aus der Liste kommen,
        die das Modell gesehen hat: Das Modell hat sie von der SEITE, und
        eine Seite, die ihm einredet, ihr Bestell-Knopf sei ein harmloser
        Link, haette die Pruefung damit ausgehebelt.

        Der Fingerabdruck wird hier bewusst NICHT verglichen. Beurteilt
        werden soll, was jetzt wirklich dort steht -- und ob es noch
        dasselbe Element wie beim Lesen ist, entscheidet klicken() gleich
        danach und verweigert notfalls. Beide Wachen zusammen: Hier wird
        die Wahrheit geholt, dort wird die Veraenderung bemerkt.

        Leeres dict heisst "nicht feststellbar" -- und das faellt drueben
        auf "fragen". Nicht feststellbar heisst nicht harmlos.
        """
        if not self.offen:
            return {}
        self._anfassen()
        koerper = """
          return {ok: true, element: {
            art: _art(el),
            text: _beschriftung(el, 80),
            im_formular: !!_formular(el),
            absenden: _absenden(el),
            feldart: _feldart(el)
          }};
        """
        # Wie oben: nur ohne den Fingerabdruck-Vergleich.
        kopf = """
        (function () {
          var NR = %(nr)d, LAUF = %(lauf)d;
          var s = window.__sarvis_bedienung;
          if (!s || s.lauf !== LAUF) return {ok: false};
          var el = s.knoten[NR - 1];
          if (!el || !el.isConnected || !_sichtbar(el)) return {ok: false};
        """ % {"nr": int(nummer), "lauf": self._lauf}
        gelungen, wert = await self._js_daten(
            _JS_HILFE, kopf + koerper + "\n})()", zeitlimit)
        if not gelungen or not isinstance(wert, dict) or not wert.get("ok"):
            return {}
        return dict(wert.get("element") or {})

    async def klicken(self, nummer: int,
                      zeitlimit: float = ZEITLIMIT) -> dict:
        """Das Element mit dieser Nummer anklicken.

        Gibt geklickt, nummer, art, text, absenden, adresse_vorher,
        adresse, navigiert, neues_fenster, grund.

        Findet sich das Element nicht mehr, wird gemeldet und NICHTS
        geklickt. Nicht das naechstbeste, nicht das mit derselben
        Beschriftung -- lieber eine Fehlmeldung als eine Ueberweisung.

        NEUES_FENSTER HAT EINE ANDERE BEDEUTUNG BEKOMMEN.

        Unter Qt hiess es: "Der Link wollte ein neues Fenster, und
        QWebEnginePage macht keins auf -- es ist nichts passiert." Das
        war eine Entschuldigung fuer eine Einschraenkung.

        Chrome macht die Seite wirklich auf. Der Zweig verschwindet damit
        nicht, er meldet jetzt etwas anderes: dass die neue Seite die
        offene GEWORDEN ist. Das ist die richtige Entscheidung, und zwar
        aus drei Gruenden:

          Es ist, was der Nutzer meint. Wer sagt "klick auf das erste
          Ergebnis" und dabei auf einem target=_blank landet, will das
          Ergebnis sehen und nicht hoeren, dass die alte Seite noch da
          ist.

          Alles andere waere eine Sackgasse. Wuerden wir das Popup
          wegwerfen, waeren genau die Seiten unbedienbar, die
          Suchtreffer und Rechnungen in neuen Tabs oeffnen -- und das
          sind viele.

          Es bleibt EINE offene Seite. Die alte wird geschlossen, nicht
          gestapelt. Sonst muesste das Modell Tabs verwalten, und dafuer
          gibt es kein Werkzeug und keinen Grund.

        Uebernommen wird nur, was UNSERE Seite geoeffnet hat (openerId),
        und nur die zuletzt aufgemachte; alles weitere wird geschlossen.
        Eine Seite, die zehn Popups aufreisst, bekommt damit nicht zehn
        Sarvis-Browser, sondern einen.

        Nach der Uebernahme ist die Elementliste weg -- neue Seite, neue
        Nummern.
        """
        antwort = {"geklickt": False, "nummer": int(nummer), "art": "",
                   "text": "", "absenden": False, "adresse_vorher": "",
                   "adresse": "", "navigiert": False, "neues_fenster": False,
                   "grund": ""}
        if not self.offen:
            antwort["grund"] = "Es ist keine Seite offen."
            return antwort
        self._anfassen()
        self._neue_ziele = []
        koerper = """
          el.scrollIntoView({block: 'center', inline: 'center'});
          var vorher = location.href;
          var beschriftung = _beschriftung(el, 80);
          var art = _art(el), abs = _absenden(el);
          el.click();
          return {ok: true, vorher: vorher,
                  text: beschriftung, art: art, absenden: abs};
        """
        gelungen, wert = await self._js_daten(
            _JS_HILFE, self._element_skript(nummer, koerper), zeitlimit,
            geste=True)
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
        })

        # Kurz nachfassen, ob der Klick navigiert oder eine neue Seite
        # aufgemacht hat.
        await asyncio.sleep(min(KLICK_NACHLAUF, max(0.0, float(zeitlimit))))

        if self._neue_ziele:
            neu = self._neue_ziele[-1]
            alt = self._ziel
            for weiteres in self._neue_ziele[:-1]:
                try:
                    await self._draht.senden("Target.closeTarget",
                                             {"targetId": weiteres})
                except Exception:
                    pass
            self._neue_ziele = []
            try:
                await self._seite_anlegen(neu)
                if alt and alt != neu:
                    await self._draht.senden("Target.closeTarget",
                                             {"targetId": alt})
                antwort["neues_fenster"] = True
                antwort["navigiert"] = True
                gelungen2, wert2 = await self._js("location.href", zeitlimit)
                if gelungen2 and isinstance(wert2, str):
                    antwort["adresse"] = wert2
                return antwort
            except Exception:
                # Uebernahme misslungen -- dann lieber ehrlich bei der
                # alten Seite bleiben als bei einer halben.
                self._neue_ziele = []

        ok2, jetzt = await self._js("location.href", zeitlimit)
        if ok2 and isinstance(jetzt, str) and jetzt:
            antwort["adresse"] = jetzt
            antwort["navigiert"] = (jetzt != antwort["adresse_vorher"])
        if antwort["navigiert"]:
            # Nach einer Navigation ist die gelesene Liste Geschichte.
            self._elemente = {}
        return antwort

    async def tippen(self, nummer: int, text: str,
                     zeitlimit: float = ZEITLIMIT) -> dict:
        """Text in ein Eingabefeld schreiben.

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

        Passwoerter kommen nie zurueck: wert_danach zeigt dann nur Punkte.
        """
        antwort = {"getippt": False, "nummer": int(nummer), "feldart": "",
                   "text": "", "wert_danach": "", "grund": ""}
        if not self.offen:
            antwort["grund"] = "Es ist keine Seite offen."
            return antwort
        self._anfassen()
        # Sehr lange Texte abschneiden: Der String geht als Skript
        # hinueber, und ein Roman im Suchfeld ist kein Anwendungsfall.
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

        gelungen, wert = await self._js_daten(
            _JS_HILFE, self._element_skript(nummer, koerper), zeitlimit,
            geste=True)
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

    # --- Ansehen ----------------------------------------------------------

    async def bild(self, zeitlimit: float = 15.0) -> dict:
        """Ein Bild der Seite -- WebP, so gross wie das Fenster.

        NUR DER SICHTBARE AUSSCHNITT, kein captureBeyondViewport. Eine
        8.000 Pixel hohe Seite ist auf einem Handy ein Streifen und hilft
        niemandem; was oben steht, ist das, worum es geht.

        WebP bei Guete 70 statt PNG: gemessen ein Zehntel bis ein
        Zwanzigstel der Groesse, und zum Erkennen, was auf der Seite
        steht, reicht es mit Abstand. Wird es trotzdem zu gross, gibt es
        genau einen zweiten Versuch mit weniger Guete -- danach lieber
        eine Meldung als eine Nachricht, die der Draht abschneidet.
        """
        if not self.offen:
            return {"ok": False, "grund": "Es ist gerade keine Seite offen."}
        self._anfassen()
        for guete in (BILD_GUETE, BILD_GUETE_NOTFALL):
            try:
                antwort = await self._draht.senden("Page.captureScreenshot", {
                    "format": "webp", "quality": guete,
                    "captureBeyondViewport": False,
                    "optimizeForSpeed": True,
                }, self._sitzung, zeitlimit)
            except Exception as e:
                return {"ok": False,
                        "grund": f"Das Bild ließ sich nicht machen: {e}"}
            daten = str(antwort.get("data") or "")
            if not daten:
                return {"ok": False, "grund": "Chrome lieferte kein Bild."}
            if len(daten) <= BILD_GRENZE:
                break
        else:
            return {"ok": False,
                    "grund": "Das Bild wäre zu groß für die Leitung."}

        gelungen, wert = await self._js(
            "({titel: document.title || '', adresse: location.href})")
        kopf = wert if (gelungen and isinstance(wert, dict)) else {}
        return {"ok": True, "daten": daten,
                "bytes": (len(daten) * 3) // 4,
                "adresse": str(kopf.get("adresse") or ""),
                "titel": str(kopf.get("titel") or ""),
                "breite": FENSTER_BREITE, "hoehe": FENSTER_HOEHE}

    # --- Herunterladen ----------------------------------------------------

    def downloads(self) -> list:
        """Die zuletzt beendeten Downloads, aeltester zuerst.

        Je Eintrag: name, pfad, bytes, zustand ("fertig"/"abgebrochen"),
        zeit. Eine Kopie -- die Liste waechst aus dem Ereignisstrom.
        """
        return list(self._downloads)


# --- Der eine Browser ------------------------------------------------------
# Einer je Prozess. Zwei waeren nicht nur Verschwendung: Chrome laesst ein
# Profil nur einmal offen, der zweite wuerde sich beim ersten melden und
# sofort wieder beenden.

_browser: Kopfbrowser | None = None


def hol() -> Kopfbrowser:
    global _browser
    if _browser is None:
        _browser = Kopfbrowser()
    return _browser


# --- Der Rueckkanal fuer die Rueckfragestufe -------------------------------
#
# hirn._browserstufe holt sich das Element, ueber das gleich entschieden
# wird, ueber anzeige.fragen("web_element") -- ein Datagramm an
# 127.0.0.1:49731, das frueher die Qt-Anzeige beantwortete. Auf dem Server
# gibt es die nicht, also antwortet niemand, also faellt jeder Klick auf
# "fragen".
#
# Das ist sicher (nicht feststellbar heisst nicht harmlos), aber es ist
# nicht das, was gemeint war: Gefragt wuerde dann auch bei einem
# stinknormalen Link, und die Rueckfrage nennt nicht einmal, worauf.
#
# Deshalb antwortet hier jemand. Ein Faden, ein UDP-Socket, eine einzige
# Frageart -- und das Element kommt aus dem DOM, wie vorgesehen. hirn.py
# und anzeige.py bleiben unberuehrt; die Naht ist schon ein Protokoll,
# es fehlte nur die Gegenseite.
#
# Faellt das Binden fehl (weil doch eine echte Anzeige lauscht), bleibt
# alles beim Alten: keine Antwort, also "fragen". Fail-closed in beide
# Richtungen.

_ANZEIGE_ADRESSE = ("127.0.0.1", 49731)
_rueckkanal: threading.Thread | None = None


def rueckkanal_starten(schleife: asyncio.AbstractEventLoop) -> bool:
    """Den Beantworter fuer "web_element" anwerfen. True, wenn er lauscht."""
    global _rueckkanal
    if _rueckkanal is not None and _rueckkanal.is_alive():
        return True
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(_ANZEIGE_ADRESSE)
    except OSError:
        return False

    def lauf():
        while True:
            try:
                daten, absender = sock.recvfrom(65535)
                frage = json.loads(daten.decode("utf-8"))
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            if frage.get("art") != "web_element":
                continue          # alles andere geht uns nichts an
            port = frage.get("antwort_an")
            nummer = frage.get("nummer")
            if not port:
                continue
            element = {}
            try:
                zukunft = asyncio.run_coroutine_threadsafe(
                    hol().element_frisch(int(frage.get("nummer_element") or 0)),
                    schleife)
                element = zukunft.result(5.0) or {}
            except Exception:
                element = {}
            try:
                sock.sendto(json.dumps(
                    {"nummer": nummer, "ok": True, "element": element}
                ).encode("utf-8"), ("127.0.0.1", int(port)))
            except OSError:
                pass

    _rueckkanal = threading.Thread(target=lauf, daemon=True,
                                   name="sarvis-web-element")
    _rueckkanal.start()
    return True
