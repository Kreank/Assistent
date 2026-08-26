"""Zustandsmeldungen an die Anzeige.

Bewusst ueber einen UDP-Socket auf localhost: der Sender blockiert nie, und
wenn die Anzeige gar nicht laeuft, verschwinden die Meldungen einfach im
Nichts. Die Schleife darf nie auf die Optik warten muessen.
"""
import json
import socket

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
