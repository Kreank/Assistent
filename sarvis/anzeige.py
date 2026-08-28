"""Zustandsmeldungen an die Anzeige.

Bewusst ueber einen UDP-Socket auf localhost: der Sender blockiert nie, und
wenn die Anzeige gar nicht laeuft, verschwinden die Meldungen einfach im
Nichts. Die Schleife darf nie auf die Optik warten muessen.
"""
import json
import socket
import time
from uuid import uuid4

ADRESSE = ("127.0.0.1", 49731)

# Zustaende
RUHIG = "ruhig"
HOERT = "hoert"
DENKT = "denkt"
SPRICHT = "spricht"
FRAGT = "fragt"


class Anzeige:
    def __init__(self, an: bool = True):
        self.an = an
        self._sock: socket.socket | None = None
        if an:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setblocking(False)

    def _senden(self, **felder) -> None:
        if not self._sock:
            return
        try:
            self._sock.sendto(json.dumps(felder).encode("utf-8"), ADRESSE)
        except OSError:
            pass  # Anzeige laeuft nicht -- egal

    def fragen(self, art: str, sekunden: float = 8.0, **felder):
        """Eine Frage an die Anzeige -- und diesmal MIT Antwort.

        Der uebrige Draht ist mit Absicht einseitig: Der Sender blockiert
        nie, und laeuft die Anzeige nicht, verschwinden die Meldungen im
        Nichts. Fuer "was steht auf der Seite" reicht das nicht -- eine
        Frage ohne Antwort ist keine.

        Also ein zweiter Socket, der nur fuer diese eine Frage lebt:
        aufmachen, den eigenen Port in der Frage nennen, warten,
        zumachen. Kein fester zweiter Port, den irgendwer belegt haben
        koennte, und nichts, was ueber die Frage hinaus offen bleibt.

        Blockiert bis zum Zeitlimit -- also NUR aus einem Faden aufrufen
        (asyncio.to_thread), nie aus der Schleife heraus.

        Gibt None zurueck, wenn niemand antwortet. Das ist der Normalfall,
        wenn die Anzeige gar nicht laeuft, und muss vom Aufrufer als
        "geht gerade nicht" gesagt werden -- nicht als leeres Ergebnis.
        """
        if not self._sock:
            return None
        rueck = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            rueck.bind(("127.0.0.1", 0))
            nummer = uuid4().hex[:12]
            self._senden(art=art, antwort_an=rueck.getsockname()[1],
                         nummer=nummer, **felder)
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

    def zustand(self, was: str, text: str = "") -> None:
        self._senden(art="zustand", zustand=was, text=text)

    def pegel(self, wert: float) -> None:
        self._senden(art="pegel", pegel=round(float(wert), 4))

    def untertitel(self, wer: str, text: str) -> None:
        self._senden(art="untertitel", wer=wer, text=text)

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
        self._senden(art="hintergrund",
                     zeilen=[str(z) for z in (zeilen or [])][:3],
                     seit=round(float(seit), 1), fertig=bool(fertig))

    def browser(self, adresse: str) -> None:
        """Eine Seite im eingebauten Browser zeigen."""
        self._senden(art="browser", adresse=str(adresse or ""))

    def browser_zu(self) -> None:
        self._senden(art="browser_zu")

    def kachel(self, name: str, kopf: str, punkte, sorte: str = "antwort",
               gross: str = "", stand: str = "", sekunden: float = 0.0) -> None:
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
        self._senden(art="kachel", name=str(name), sorte=str(sorte),
                     kopf=str(kopf), gross=str(gross), stand=str(stand),
                     # Zwoelf reichen. Eine Kachel wird im Vorbeigehen
                     # gelesen, nicht studiert -- und der Deckel haelt
                     # nebenbei das Datagramm klein.
                     punkte=list(punkte or [])[:12],
                     sekunden=round(float(sekunden), 1))

    def kachel_weg(self, name: str) -> None:
        """Eine Kachel ausblenden lassen -- der Auftrag ist fertig."""
        self._senden(art="kachel_weg", name=str(name))

    def werkzeug(self, name: str, aktiv: bool = True) -> None:
        """Ein Werkzeug im Kranz aufleuchten lassen (Stufe 2)."""
        self._senden(art="werkzeug", name=name, aktiv=bool(aktiv))

    def freigabe(self, text: str, sekunden: float = 0.0) -> None:
        """Was gerade ohne Rueckfrage durchgeht -- leerer Text: nichts.

        Sichtbarkeit ist bei einer Freigabe kein Beiwerk. Was still gilt,
        gilt irgendwann laenger, als man im Kopf hat. Die Restzeit geht
        mit, damit die Anzeige von selbst wieder verschwindet, statt eine
        laengst abgelaufene Freigabe weiter zu behaupten.
        """
        self._senden(art="freigabe", text=str(text or ""),
                     sekunden=round(float(sekunden), 1))
