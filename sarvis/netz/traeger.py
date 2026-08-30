"""Die Anzeige-Naht ueber Netz -- an alle Oberflaechen zugleich.

Ersetzt UdpTraeger aus anzeige.py. Derselbe Vertrag, andere Leitung:

  senden()  geht an JEDE verbundene Oberflaeche, nicht an ein Fenster
  fragen()  geht an genau eine -- die, die einen Browser hat

Der zweite Punkt ist der Unterschied, den man leicht uebersieht. Ein
Zustand gehoert allen: Wenn Sarvis nachdenkt, sollen Handy und Dev-PC
das zeigen. Eine Frage wie "was steht auf der Seite" hat dagegen genau
einen sinnvollen Empfaenger, und es waere falsch, die erste Antwort
gewinnen zu lassen.

WARUM NIE BLOCKIERT WIRD

Die Anzeige-Methoden werden aus der Ereignisschleife und aus
Audio-Rueckrufen gerufen -- ohne await, ohne Faden. Genau deshalb steht
zwischen hier und dem Netz eine Warteschlange je Oberflaeche, und der
Sender legt nur hinein.

Ist eine Oberflaeche langsam, laeuft ihre Schlange voll. Dann werden
ihre AELTESTEN Meldungen weggeworfen, nicht die neuen -- fast alles hier
sind Zustaende, und der jeweils neueste ist der richtige. Ein Pegel von
vor zwei Sekunden ist wertlos; ein Zustand von vor zwei Sekunden ist
falsch.

Ausgenommen sind die drei Arten, bei denen Verlust bleibt: werkzeug
(ein Ereignis, kein Zustand), kachel_weg (sonst steht eine Kachel fuer
immer) und verschieben. Die duerfen nicht der Schlange zum Opfer fallen,
also stehen sie in WICHTIG und werden beim Aufraeumen uebersprungen.
"""
import asyncio
import json
from uuid import uuid4

# Wie viele Meldungen je Oberflaeche warten duerfen, bevor aufgeraeumt
# wird. Bei 50 Pegeln je Sekunde sind 200 rund vier Sekunden Rueckstand
# -- wer dann noch nicht gesendet hat, ist nicht langsam, sondern weg.
SCHLANGE_MAX = 200

# Arten, die beim Aufraeumen NICHT weggeworfen werden. Siehe Modulkopf.
WICHTIG = frozenset({"werkzeug", "kachel_weg", "verschieben"})


class Oberflaeche:
    """Eine verbundene Bedienoberflaeche -- ein Handy, ein Dev-PC."""

    def __init__(self, name: str, kann_browser: bool = False,
                 faehigkeiten: set[str] | None = None):
        self.name = name
        self.kann_browser = kann_browser
        # Was diese Oberflaeche ausserdem kann. Ein Browser meldet
        # nichts; eine native App sagt bei der Anmeldung, dass sie
        # Programme starten und Medientasten druecken kann.
        self.faehigkeiten = set(faehigkeiten or ())
        self.schlange: asyncio.Queue = asyncio.Queue()
        # Offene Fragen dieser Oberflaeche: nummer -> Future
        self.offen: dict[str, asyncio.Future] = {}

    def einlegen(self, felder: dict) -> None:
        """Nicht blockierend. Bei Rueckstand fliegt Altes heraus."""
        if self.schlange.qsize() >= SCHLANGE_MAX:
            self._aufraeumen()
        try:
            self.schlange.put_nowait(felder)
        except asyncio.QueueFull:
            pass

    def _aufraeumen(self) -> None:
        """Rueckstand eindampfen, ohne die Anzeige zu verfaelschen.

        Behalten wird zweierlei, und beides aus einem Grund:

          - alles aus WICHTIG, weil dort Verlust bleibt (ein Werkzeug,
            das nie aufleuchtet; eine Kachel, die nie verschwindet)
          - je uebriger Art der NEUESTE Stand

        Der zweite Punkt ist der eigentliche: Wuerde man einfach alles
        wegwerfen, zeigte die Oberflaeche nach dem Stau den Zustand von
        VOR dem Stau und wartete auf den naechsten Wechsel -- der
        vielleicht nie kommt, weil Sarvis inzwischen still dasteht. Ein
        Ring, der ewig "denkt nach" behauptet, ist schlimmer als einer,
        der ein paar Bilder uebersprungen hat.

        Die Reihenfolge bleibt dabei erhalten: erst die wichtigen
        Ereignisse in ihrer urspruenglichen Folge, dann die
        zusammengefassten Zustaende.
        """
        wichtig: list[dict] = []
        neueste: dict[str, dict] = {}
        while True:
            try:
                m = self.schlange.get_nowait()
            except asyncio.QueueEmpty:
                break
            if m.get("art") in WICHTIG:
                wichtig.append(m)
            else:
                # Je Art EIN Eintrag -- und bei Kacheln je NAME einer,
                # sonst ueberschreibt die Finanzkachel die Terminkachel.
                schluessel = str(m.get("art", ""))
                if m.get("name"):
                    schluessel += ":" + str(m["name"])
                if m.get("strom"):
                    schluessel += "@" + str(m["strom"])
                neueste[schluessel] = m
        for m in wichtig + list(neueste.values()):
            try:
                self.schlange.put_nowait(m)
            except asyncio.QueueFull:
                break

    def antwort(self, nummer: str, inhalt: dict) -> None:
        """Eine Antwort auf eine gestellte Frage zuordnen."""
        fut = self.offen.pop(nummer, None)
        if fut is not None and not fut.done():
            fut.set_result(inhalt)


class NetzTraeger:
    """Erfuellt denselben Vertrag wie anzeige.UdpTraeger."""

    def __init__(self, schleife: asyncio.AbstractEventLoop):
        self.schleife = schleife
        self.oberflaechen: list[Oberflaeche] = []

    # --- Vertrag ---------------------------------------------------------

    def senden(self, felder: dict) -> None:
        """An alle. Blockiert nie, auch nicht aus einem fremden Faden.

        call_soon_threadsafe, weil das hier aus dem Audio-Rueckruf und
        aus dem Tastaturfaden kommen kann -- eine Warteschlange von
        asyncio ist nicht fadensicher.
        """
        try:
            self.schleife.call_soon_threadsafe(self._verteilen, felder)
        except RuntimeError:
            pass  # Schleife laeuft nicht mehr -- wie ein verlorenes Datagramm

    def _verteilen(self, felder: dict) -> None:
        for o in list(self.oberflaechen):
            o.einlegen(felder)

    def fragen(self, felder: dict, sekunden: float) -> dict | None:
        """Eine Frage an die Oberflaeche, die einen Browser hat.

        Blockiert bis zum Zeitlimit -- wird deshalb nur aus einem Faden
        gerufen (asyncio.to_thread), genau wie beim UDP-Traeger.

        None heisst hier dreierlei, und der Aufrufer darf keines davon
        als leeres Ergebnis ausgeben: niemand verbunden, niemand mit
        Browser, oder keine Antwort in der Zeit.
        """
        ziel = next((o for o in self.oberflaechen if o.kann_browser), None)
        if ziel is None:
            return None
        nummer = uuid4().hex[:12]
        fut = self.schleife.create_future()
        ziel.offen[nummer] = fut

        def stellen():
            ziel.einlegen({**felder, "nummer": nummer})

        try:
            self.schleife.call_soon_threadsafe(stellen)
            # Aus einem fremden Faden auf ein Future der Schleife warten.
            return asyncio.run_coroutine_threadsafe(
                asyncio.wait_for(asyncio.shield(fut), sekunden), self.schleife
            ).result(sekunden + 1.0)
        except Exception:
            return None
        finally:
            ziel.offen.pop(nummer, None)

    # --- Verwaltung ------------------------------------------------------

    def dazu(self, o: Oberflaeche) -> None:
        self.oberflaechen.append(o)

    def weg(self, o: Oberflaeche) -> None:
        if o in self.oberflaechen:
            self.oberflaechen.remove(o)
        for fut in o.offen.values():
            if not fut.done():
                fut.cancel()
        o.offen.clear()

    def wie_viele(self) -> int:
        return len(self.oberflaechen)

    def kann(self, faehigkeit: str) -> bool:
        """Kann irgendeine verbundene Oberflaeche das?"""
        return any(faehigkeit in o.faehigkeiten for o in self.oberflaechen)


def als_text(felder: dict) -> str:
    """Eine Meldung als Zeile fuer den Draht.

    ensure_ascii=False: Umlaute gehen als Umlaute. Der UDP-Traeger
    schickte sie als \\uXXXX, was doppelt so viele Bytes sind und auf
    dem Weg zum Handy nichts bringt.
    """
    return json.dumps(felder, ensure_ascii=False, separators=(",", ":"))
