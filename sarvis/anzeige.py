"""Zustandsmeldungen an die Anzeige.

Zwoelf Ereignisarten und eine Frage mit Antwort -- mehr ist die Naht
zwischen Sarvis und dem, was man von ihm sieht, nicht. Genau deshalb
laesst sie sich ins Netz verlegen: Sie ist schon ein Protokoll, es
stand nur bisher auf einem UDP-Socket zu localhost.

    zustand    pegel       untertitel   verschieben
    nachhoeren hintergrund browser      browser_zu
    kachel     kachel_weg  werkzeug     freigabe

DER TRAEGER IST AUSTAUSCHBAR

Anzeige spricht nicht mehr selbst mit einem Socket, sondern mit einem
Traeger. Heute ist das UdpTraeger und alles bleibt, wie es war; spaeter
tritt eine Netzfassung daneben, die dasselbe an alle verbundenen
Oberflaechen schickt -- Handy und Dev-PC gleichzeitig.

Was der Traeger dabei nachbauen MUSS, weil der ganze Rest darauf beruht:

  Er blockiert nie. Diese Methoden werden aus der Ereignisschleife und
  aus Audio-Rueckrufen gerufen, ohne await, ohne Faden. Ein Netz-Send,
  der im Aufnahme-Rueckruf wartet, verzerrt den Ton.

  Er darf verlieren. "Laeuft keine Anzeige, verschwindet es im Nichts"
  ist keine Nachlaessigkeit, sondern eine Zusage: bericht.py schickt
  eine Seite und FRAGT hinterher nach, ob sie wirklich zu sehen ist,
  statt es zu behaupten. Ueber Netz kommt ein dritter Fall dazu, den es
  bisher nicht gab -- Anzeige da, aber langsam. Dagegen hilft nur ein
  Puffer mit Deckel und einer Wegwerfregel.

FAST ALLES SIND ZUSTAENDE, KEINE AENDERUNGEN

zustand, pegel, untertitel, nachhoeren, freigabe, hintergrund und selbst
kachel (immer der ganze Inhalt) heilen sich beim naechsten Senden von
selbst. Ein verlorenes Datagramm kostet ein Bild, mehr nicht.

Drei Ausnahmen, bei denen Verlust bleibt -- heute unauffaellig, weil
Loopback-UDP praktisch nichts verliert, ueber Netz aber nicht mehr:

    werkzeug      ein Ereignis, kein Zustand: verloren = nie gezeigt
    kachel_weg    verloren -> eine Zustandskachel steht fuer immer
    verschieben   ein Umschaltbefehl: verloren -> beide Seiten uneins

DAS STROM-FELD

Sarvis soll ansprechbar bleiben, waehrend er arbeitet. Damit gibt es
kuenftig mehr als einen Vorgang gleichzeitig: das Gespraech und n
Auftraege. Von den zwoelf Arten trug bisher nur die Kachel eine
Identitaet ("zweimal 'finanzen' heisst dieselbe Kachel mit neuem
Inhalt"), und genau das ist das Muster, dem die anderen folgen muessen.

Deshalb tragen zustand, untertitel, hintergrund und werkzeug jetzt ein
optionales strom -- leer heisst "das Gespraech". Die heutige Anzeige
ignoriert unbekannte Felder einfach; es kostet also nichts und muss
spaeter nicht nachgeruestet werden. Und Nachruesten waere teuer: zustand
ist kein Datenfeld, sondern der Verteiler des ganzen Bildes (Farbe,
Deckkraft, Beschriftung, Boegen oder Balken). Ein strom-Feld dort spaeter
einzufuehren hiesse, paintEvent und die Farbtabellen gleichzeitig
anzufassen -- also genau die Stelle, an der der Sarvis-Look sitzt.

Die Grenze verlaeuft dort, wo hud.py sie schon gezogen hat: "Der Ring in
der Mitte gehoert IHM, diese Ecke der Arbeit im Hintergrund." Der Ring
bleibt das Gespraech. Was arbeitet, bekommt einen Namen.
"""
import json
import socket
import time
from uuid import uuid4

ADRESSE = ("127.0.0.1", 49731)

# Wie oft der Pegel hoechstens weitergereicht wird.
#
# Er hat drei Erzeuger, alle ungedrosselt: der Weckwort-Horcher rund um
# die Uhr mit 33/s, der Aufnehmer waehrend der Aufnahme mit 40/s, der
# Lautsprecher waehrend des Sprechens mit 80/s. Fuer ein Datagramm auf
# localhost war das gleichgueltig. Ueber Netz sind 80 Nachrichten je
# Sekunde je verbundenem Geraet Dauerlast -- und jede Verzoegerung staut
# sich in einer Sendewarteschlange, die es heute gar nicht gibt.
#
# Die Anzeige braucht sie auch nicht: Sie malt 60 Bilder je Sekunde und
# zieht den Wert dabei selbst traege nach. Sie braucht nur den jeweils
# neuesten. 50/s liegt unter der Bildrate und ueber dem, was das Auge
# an einem Ausschlag unterscheidet.
PEGEL_JE_SEKUNDE = 50

# Wie viele Datenpunkte je Form hoechstens mitgehen. Siehe kachel(),
# warum das nicht eine Zahl fuer alle ist.
PUNKTE_DECKEL = {
    "liste": 12, "blasen": 12, "vergleich": 12, "text": 12,
    "balken": 24,       # zwei Jahre Monatswerte
    "torte": 8,         # mehr Tortenstuecke unterscheidet niemand
    "kategorien": 30,   # gruppiert, also lesbar auch bei vielen
    # Die beiden Graphen haengen nicht an der Lesbarkeit, sondern an der
    # Hoehe: Gemessen faechert ein Knoten auf 24 Ziele auf und die
    # Kachel wird 498 Raster hoch -- bei 30 waeren es 582 und damit
    # hoeher als die Engine mit 548. Beim Ablauf sind 10 einzeilige
    # Kaesten 518 Raster.
    "fluss": 24,
    "ablauf": 10,
}

# Zustaende
RUHIG = "ruhig"
HOERT = "hoert"
DENKT = "denkt"
SPRICHT = "spricht"
FRAGT = "fragt"


# Die Anzeige, die gerade gilt.
#
# Drei Werkzeugmodule bauten sich bisher jeweils ihre EIGENE
# Anzeige(config.ANZEIGE) -- kacheln.py, bericht.py, programme.py. Auf
# einem Rechner war das gleichgueltig: Jede oeffnete einen UDP-Socket
# zum selben Fenster, und Sockets sind billig.
#
# Im Netzbetrieb ist es ein Fehler, und zwar ein stiller: Diese drei
# schickten weiter Datagramme an 127.0.0.1:49731, wo niemand mehr
# zuhoert. Kacheln, Berichte und geoeffnete Seiten kamen also nirgends
# an -- ohne Fehlermeldung, denn "verschwindet im Nichts" ist genau die
# Zusage des Traegers.
#
# Deshalb eine Stelle statt drei. main.py setzt sie, sobald feststeht,
# worueber gesendet wird; wer vorher fragt, bekommt eine UDP-Anzeige wie
# frueher.
_aktuelle: "Anzeige | None" = None


def setzen(anzeige: "Anzeige") -> None:
    """Die Anzeige hinterlegen, die alle benutzen sollen."""
    global _aktuelle
    _aktuelle = anzeige


def _echte() -> "Anzeige":
    """Die geltende Anzeige -- notfalls eine neue ueber UDP."""
    global _aktuelle
    if _aktuelle is None:
        from . import config
        _aktuelle = Anzeige(config.ANZEIGE)
    return _aktuelle


class _Weiterreicher:
    """Schlaegt die geltende Anzeige bei JEDEM Aufruf neu nach.

    Der Umweg ist noetig, weil die Werkzeuge einmal gebaut werden --
    beim Hochfahren, im Konstruktor -- und dann jahrelang dieselben
    Objekte behalten. Wer sich dabei die Anzeige merkt, merkt sich die,
    die GERADE galt.

    Genau das ist passiert: Die Werkzeuge entstehen vor dem Endpunkt,
    hielten also die UDP-Anzeige fest und schickten weiter an ein
    Fenster, das es nicht gibt. Sarvis sagte "die Route liegt auf deinem
    Bildschirm", und auf dem Bildschirm lag nichts.

    Ein Attributzugriff mehr je Aufruf. Das ist billiger als die Regel,
    dass man Werkzeuge in einer bestimmten Reihenfolge bauen muss --
    solche Regeln haelt man ein, bis man sie vergisst.
    """

    def __getattr__(self, name):
        return getattr(_echte(), name)


def aktuelle() -> "Anzeige":
    """Ein Griff auf die jeweils geltende Anzeige."""
    return _Weiterreicher()


# Wem die Antwort gerade gilt -- ein Geraetename, oder None fuer "an
# alle". main._antwort_an setzt das vor jedem Durchgang, gleichzeitig mit
# dem Ziel des Lautsprechers.
#
# WARUM DAS HIER STEHT UND NICHT NUR AM LAUTSPRECHER
#
# Der Lautsprecher kennt es laengst -- er schickt den Ton gezielt an das
# Geraet, das gefragt hat. Nur kommen Werkzeuge an ihn nicht heran: Sie
# werden beim Hochfahren gebaut und bekommen die Anzeige, sonst nichts.
#
# Ton ist aber nicht mehr das Einzige, was auf EIN Geraet gehoert. Das
# Radio gehoert dorthin, wo gefragt wurde, aus demselben koerperlichen
# Grund: Wer am Rechner "mach Radio an" sagt, will es nicht aus dem Handy
# in der Jackentasche im Flur hoeren.
#
# Also eine Stelle statt zweier Wege dorthin -- dieselbe Entscheidung wie
# bei _aktuelle weiter oben.
_ziel: str | None = None


def zielen(geraet: str | None) -> None:
    """Festlegen, wem das Naechste gilt. None heisst: an alle."""
    global _ziel
    _ziel = geraet or None


def ziel() -> str | None:
    """Wem gerade geantwortet wird -- None, wenn niemandem bestimmten."""
    return _ziel


class UdpTraeger:
    """Der Weg zur Anzeige auf demselben Rechner.

    Ein Datagramm je Meldung, nicht blockierend, und was nicht ankommt,
    ist weg. Genau diese drei Eigenschaften muss jeder andere Traeger
    nachbauen -- siehe Modulkopf.
    """

    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)

    def senden(self, felder: dict) -> None:
        try:
            self._sock.sendto(json.dumps(felder).encode("utf-8"), ADRESSE)
        except OSError:
            pass  # Anzeige laeuft nicht -- egal

    def fragen(self, felder: dict, sekunden: float) -> dict | None:
        """Eine Frage, die auf Antwort wartet.

        Ein zweiter Socket, der nur fuer diese eine Frage lebt:
        aufmachen, den eigenen Port in der Frage nennen, warten,
        zumachen. Kein fester zweiter Port, den irgendwer belegt haben
        koennte, und nichts, was ueber die Frage hinaus offen bleibt.
        """
        rueck = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            rueck.bind(("127.0.0.1", 0))
            nummer = uuid4().hex[:12]
            self.senden({**felder, "antwort_an": rueck.getsockname()[1],
                         "nummer": nummer})
            ende = time.monotonic() + sekunden
            while True:
                rest = ende - time.monotonic()
                if rest <= 0:
                    return None
                rueck.settimeout(rest)
                try:
                    daten, _ = rueck.recvfrom(65535)
                except OSError:
                    return None
                try:
                    antwort = json.loads(daten.decode("utf-8"))
                except (ValueError, UnicodeDecodeError):
                    continue
                # Nur die Antwort auf GENAU diese Frage. Eine verspaetete
                # von vorhin wuerde sonst die von jetzt beantworten -- und
                # zwar mit dem Inhalt der falschen Seite.
                if antwort.get("nummer") == nummer:
                    return antwort
        finally:
            rueck.close()


class Anzeige:
    def __init__(self, an: bool = True, traeger=None):
        self.an = an
        self._traeger = traeger or (UdpTraeger() if an else None)
        # Wann zuletzt ein Pegel durchgelassen wurde (time.monotonic).
        self._pegel_zuletzt = 0.0

    def _senden(self, **felder) -> None:
        if self._traeger is None:
            return
        self._traeger.senden(felder)

    def fragen(self, art: str, sekunden: float = 8.0, **felder):
        """Eine Frage an die Anzeige -- und diesmal MIT Antwort.

        Der uebrige Draht ist mit Absicht einseitig: Der Sender blockiert
        nie, und laeuft die Anzeige nicht, verschwinden die Meldungen im
        Nichts. Fuer "was steht auf der Seite" reicht das nicht -- eine
        Frage ohne Antwort ist keine.

        Blockiert bis zum Zeitlimit -- also NUR aus einem Faden aufrufen
        (asyncio.to_thread), nie aus der Schleife heraus.

        Gibt None zurueck, wenn niemand antwortet. Das ist der Normalfall,
        wenn die Anzeige gar nicht laeuft, und muss vom Aufrufer als
        "geht gerade nicht" gesagt werden -- nicht als leeres Ergebnis.

        Ueber Netz kommt ein Unterschied dazu, den es hier nicht gibt:
        "niemand hat geantwortet" und "die Verbindung ist weg" sind
        beides None. Fuer den Nutzer ist das derselbe Satz, fuers
        Wiederverbinden nicht.
        """
        if self._traeger is None:
            return None
        return self._traeger.fragen({"art": art, **felder}, sekunden)

    def zustand(self, was: str, text: str = "", strom: str = "") -> None:
        """Der Gemuetszustand: ruhig, hoert, denkt, spricht, fragt.

        strom leer = das Gespraech, also der Ring in der Mitte. Ein
        benannter Strom gehoert zu einem Vorgang, der nebenher laeuft --
        die heutige Anzeige ignoriert ihn, eine Oberflaeche mit Platz
        kann ihn getrennt zeigen. Siehe Modulkopf.
        """
        self._senden(art="zustand", zustand=was, text=text, strom=strom)

    def pegel(self, wert: float) -> None:
        """Der Ausschlag fuer den Ring -- gedrosselt, siehe PEGEL_JE_SEKUNDE.

        Bewusst hier und nicht bei den drei Erzeugern: Sie rufen aus
        Audio-Rueckrufen und wissen nichts voneinander. Der Deckel gehoert
        an die Naht, wo alle drei zusammenlaufen.
        """
        wert = round(float(wert), 4)
        jetzt = time.monotonic()
        # Die Null geht IMMER durch. Sie ist kein Messwert, sondern ein
        # Schlusspunkt: Aufnehmer und Lautsprecher melden sie genau
        # einmal, wenn sie fertig sind. Faellt sie der Drossel zum Opfer,
        # bleibt der Ring auf dem letzten Ausschlag stehen und behauptet
        # eine Stimme, die schweigt -- und die naechste Meldung kommt
        # erst beim naechsten Zuruf.
        if wert > 0.0 and jetzt - self._pegel_zuletzt < 1.0 / PEGEL_JE_SEKUNDE:
            return
        self._pegel_zuletzt = jetzt
        self._senden(art="pegel", pegel=wert)

    def untertitel(self, wer: str, text: str, strom: str = "") -> None:
        self._senden(art="untertitel", wer=wer, text=text, strom=strom)

    def verschieben(self, an: bool) -> None:
        """Verschiebemodus ein- oder ausschalten."""
        self._senden(art="verschieben", an=bool(an))

    def nachhoeren(self, sekunden: float) -> None:
        """Fenster offen: so lange ist kein Weckwort noetig."""
        self._senden(art="nachhoeren", sekunden=round(float(sekunden), 2))

    def hintergrund(self, zeilen, seit: float = 0.0,
                    fertig: bool = False) -> None:
        """Was gerade im Hintergrund arbeitet -- leere Liste: nichts.

        Sarvis kann still dastehen und trotzdem beschaeftigt sein: Ein
        Auftrag laeuft weiter, ein Subagent baut ein Frontend, waehrend
        das Gespraech schon woanders ist. Ohne Anzeige ist das von
        Nichtstun nicht zu unterscheiden -- und man fragt nach, ob
        ueberhaupt etwas passiert.
        """
        alle = [str(z) for z in (zeilen or [])]
        self._senden(art="hintergrund",
                     zeilen=alle[:3],
                     # Wie viele es WIRKLICH sind. Die Anzeige schrieb
                     # bisher "im Hintergrund · n" aus der bereits
                     # gekappten Liste -- die Zahl konnte also nie ueber
                     # drei gehen, egal wie viel lief. Bei der Kachel
                     # macht der Code das schon richtig ("weggelassen",
                     # damit die Kuerzung nicht STUMM ist); hier fehlte
                     # das Gegenstueck.
                     gesamt=len(alle),
                     seit=round(float(seit), 1), fertig=bool(fertig))

    def browser(self, adresse: str) -> None:
        """Eine Seite im eingebauten Browser zeigen."""
        self._senden(art="browser", adresse=str(adresse or ""))

    def browser_zu(self) -> None:
        self._senden(art="browser_zu")

    def kachel(self, name: str, kopf: str, punkte, sorte: str = "antwort",
               gross: str = "", stand: str = "", sekunden: float = 0.0,
               form: str = "liste", spalten=()) -> None:
        """Eine Kachel neben der Engine zeigen -- oder ihren Inhalt ersetzen.

        name ist die Identitaet, nicht die Ueberschrift: Zweimal "finanzen"
        heisst dieselbe Kachel mit neuem Inhalt, nicht zwei uebereinander.

        sorte trennt die beiden Lebensdauern. Eine "antwort" gehoert zu
        einem Satz und geht nach einer Weile von selbst; ein "zustand"
        gehoert zu etwas, das laeuft, und bleibt stehen, bis er endet.

        punkte sind DATENPUNKTE, keine fertigen Zeilen:
        {"text": "Wohnen", "wert": "1.098,00", "zahl": 1098.0}. Aus "zahl"
        wird die Laenge des Balkens, und daran erkennt die Kachel spaeter,
        welchen Posten Sarvis gerade nennt. Wer hier Text schickt, kann
        weder zeichnen noch hervorheben.
        """
        # Erst kappen, dann senden -- und die Zahl der Weggelassenen
        # mitschicken. Ohne sie waere die Kuerzung STUMM: Die Kachel
        # rechnet Knoten- und Gruppensummen aus dem, was ankommt, und
        # zeigt sie, als waeren es alle. Bei einer Liste fehlen dann nur
        # Zeilen; bei einem Fluss steht eine falsche Zahl da.
        alle = list(punkte or [])
        deckel = PUNKTE_DECKEL.get(str(form or "liste"), 12)
        behalten = alle[:deckel]
        self._senden(art="kachel", name=str(name), sorte=str(sorte),
                     kopf=str(kopf), gross=str(gross), stand=str(stand),
                     weggelassen=len(alle) - len(behalten),
                     # Der Deckel haengt an der Form. Zwoelf reichen zum
                     # Vorbeigehen -- aber ein Balkendiagramm ueber zwoelf
                     # Monate braucht genau zwoelf, und eine Kategorien-
                     # liste vertraegt mehr, weil sie gruppiert ist.
                     #
                     # Am Datagramm liegt es nicht: Gemessen sind 150
                     # Buchungen 24.570 Bytes gegen einen harten Deckel
                     # von 65.507. Es liegt an der Lesbarkeit, und die
                     # ist je Form verschieden.
                     punkte=behalten,
                     # Die Form entscheidet, WIE gemalt wird -- Liste,
                     # Gespraechsblasen, zwei Spalten mit Differenz oder
                     # Fliesstext. Die Spaltennamen sind Inhalt, keine
                     # Gestaltung: Welcher Monat rechts steht, weiss nur
                     # der Aufrufer.
                     form=str(form or "liste"),
                     spalten=[str(x) for x in (spalten or [])][:2],
                     sekunden=round(float(sekunden), 1))

    def befehl(self, art: str, **felder) -> None:
        """Einen Befehl an die Oberflaechen schicken, die ihn ausfuehren.

        Die Umkehrung des ueblichen Wegs: Sonst schickt Sarvis, was man
        SEHEN soll. Hier schickt er, was jemand TUN soll -- ein Programm
        starten, die Musik anhalten. Auf dem Server geht beides nicht
        selbst, vor dem richtigen Rechner sitzt jemand anderes.

        Eine Oberflaeche, die das nicht kann, ignoriert es einfach --
        unbekannte Arten zu ueberspringen ist ohnehin die Regel. Deshalb
        vorher kann() fragen, sonst sagt Sarvis "erledigt" ins Leere.
        """
        self._senden(art="befehl", befehl=str(art), **felder)

    def kann(self, faehigkeit: str) -> bool:
        """Kann eine verbundene Oberflaeche das?

        Ueber UDP immer False: Dort haengt ein Anzeigefenster, kein
        Rechner, der Befehle ausfuehrt. Auf Windows brauchte Sarvis das
        auch nie -- er lief ja selbst auf dem Rechner.
        """
        traeger = self._traeger
        pruefen = getattr(traeger, "kann", None)
        return bool(pruefen(faehigkeit)) if pruefen else False

    def kann_hier(self, faehigkeit: str) -> bool:
        """Kann das Geraet, dem gerade geantwortet wird, das?

        Der Unterschied zu kann() zaehlt ueberall dort, wo etwas auf EINEM
        Geraet passieren soll statt auf allen -- beim Radio etwa. "Kann es
        irgendwer" hiesse dort: Sarvis sagt am Rechner "laeuft", und der
        Ton ginge im Browser auf dem Handy an. Oder nirgends.
        """
        traeger = self._traeger
        pruefen = getattr(traeger, "kann_geraet", None)
        return bool(pruefen(ziel(), faehigkeit)) if pruefen else False

    def draht(self):
        """Der Traeger, ueber den gesendet wird -- oder None.

        Fuer die wenigen Faelle, die eine EIGENE Nachrichtenart gezielt
        an ein Geraet schicken (netz/klang_netz.py fuer den Ton,
        werkzeuge/lesen.py fuers Radio). Alles, was an alle geht, nimmt
        die Methoden hier drueber und nicht diesen Griff.
        """
        return self._traeger

    def kachel_weg(self, name: str) -> None:
        """Eine Kachel ausblenden lassen -- der Auftrag ist fertig."""
        self._senden(art="kachel_weg", name=str(name))

    def werkzeug(self, name: str, aktiv: bool = True,
                 strom: str = "") -> None:
        """Ein Werkzeug im Kranz aufleuchten lassen.

        Mehrere gleichzeitig sind schon heute moeglich -- jede Glut
        klingt fuer sich ab. Was fehlt, ist die Herkunft: Zwei Vorgaenge,
        die zugleich Dateien anfassen, sind eine einzige Glut. Dafuer
        das strom-Feld.
        """
        self._senden(art="werkzeug", name=name, aktiv=bool(aktiv),
                     strom=strom)

    def freigabe(self, text: str, sekunden: float = 0.0) -> None:
        """Was gerade ohne Rueckfrage durchgeht -- leerer Text: nichts.

        Sichtbarkeit ist bei einer Freigabe kein Beiwerk. Was still gilt,
        gilt irgendwann laenger, als man im Kopf hat. Die Restzeit geht
        mit, damit die Anzeige von selbst wieder verschwindet, statt eine
        laengst abgelaufene Freigabe weiter zu behaupten.
        """
        self._senden(art="freigabe", text=str(text or ""),
                     sekunden=round(float(sekunden), 1))
