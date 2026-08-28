"""Hirn: Claude, ueber eine dauerhaft offene Sitzung.

Der Punkt ist die Dauerhaftigkeit. Ein Prozess pro Zuruf kostet rund fuenf
Sekunden Startzeit -- gemessen. Eine offene Sitzung kostet die einmal beim
Hochfahren, danach nur noch die eigentliche Antwort.
"""
import asyncio
import random
from datetime import datetime
from typing import AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    StreamEvent,
    TextBlock,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)

from . import config, schutz
from .gedaechtnis import systemprompt
from .werkzeuge import SERVER, kurzer_name, voller_name

WOCHENTAGE = ("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag",
              "Samstag", "Sonntag")
MONATE = ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli",
          "August", "September", "Oktober", "November", "Dezember")


def jetzt_zeile() -> str:
    """Datum und Uhrzeit als Vorspann fuer jeden Zuruf.

    Die Sitzung kennt beim Verbinden ein Datum, aber keine laufende Uhr --
    auf "wie spaet ist es" konnte Sarvis deshalb nur das Datum nennen. Der
    Vorspann geht mit jeder Frage neu mit und stimmt dadurch immer.

    Die Sekunden gehoeren dazu: Ohne sie rechnete Sarvis "Timer auf 8:29:30"
    aus einer Uhrzeit ohne Sekunden aus und lag bis zu eine Minute daneben.
    """
    n = datetime.now()
    return (f"[Jetzt: {WOCHENTAGE[n.weekday()]}, {n.day}. {MONATE[n.month - 1]} "
            f"{n.year}, {n.hour}:{n.minute:02d}:{n.second:02d} Uhr]")


class Hirn:
    # Welches Werkzeug welchen Punkt im Anzeigenkranz aufleuchten laesst.
    KRANZ = {"WebSearch": "Websuche", "WebFetch": "Websuche",
             "Read": "Dateien", "Glob": "Dateien",
             "Grep": "Dateien", "Write": "Dateien",
             "Edit": "Dateien", "PowerShell": "Dateien",
             "Bash": "Dateien"}

    def __init__(self, werkzeuge=None, namen=None, leuchten=None,
                 nachfragen=None, protokoll=None, zustand_zeile=None,
                 freigaben=None):
        self.klient: ClaudeSDKClient | None = None
        self.letzte_kosten: float | None = None
        self.hinweise: list[str] = []
        self.werkzeuge = werkzeuge   # In-Process-Werkzeugserver oder None
        self.namen = namen or []
        self.leuchten = leuchten
        # nachfragen(kurzname, eingabe) -> (entscheidung, wortlaut);
        # von Sarvis gestellt. entscheidung ist "ja", "nein" oder "anders".
        self.nachfragen = nachfragen
        # Laufende Freigaben auf Zeit ("frag die naechste halbe Stunde
        # nicht mehr"). Siehe freigabe.py.
        self.freigaben = freigaben
        self._offen = False  # laeuft gerade eine Antwortrunde?
        # Ein Abbruch, dessen Leerlesen nicht durchkam: In der Leitung
        # koennen Reste der alten Runde liegen. Der naechste Zuruf raeumt
        # sie kurz nach, statt die alte Antwort auf die neue Frage zu sagen.
        self._leitung_unsauber = False
        self.protokoll = protokoll   # was in diesem Zug schon wirkte
        self._nachtrag = ""          # Hinweis fuer den naechsten Zuruf
        # Liefert eine Zeile mit dem, was gerade laeuft (Arbeitsgedaechtnis)
        self.zustand_zeile = zustand_zeile
        # Laufende Unter-Arbeiter: Werkzeugkennung -> kurze Beschreibung.
        # Sie sind der Grund, warum Sarvis still wirken kann, waehrend
        # etwas gebaut wird -- also gehoeren sie in die Anzeige.
        self.subagenten: dict = {}
        # Arbeiter, die mittendrin verloren gingen -- (Was, Wann).
        self.abgebrochene: list = []

    async def start(self) -> None:
        # Der Kern des Gedaechtnisses gehoert in den Systemprompt, nicht an
        # die Frage: dort wird er zwischengespeichert und kostet ab dem
        # zweiten Zuruf praktisch nichts.
        prompt, self.hinweise = systemprompt()
        self.klient = ClaudeSDKClient(
            options=ClaudeAgentOptions(
                model=config.MODELL,
                system_prompt=prompt,
                # Nur was ausdruecklich erlaubt ist. Alles Uebrige faellt
                # auf "dontAsk" und wird damit abgelehnt -- eine Erlaubnis-
                # liste, keine Sperrliste.
                # Nur die stillen Werkzeuge stehen hier. Das ist keine
                # Feinheit: Was in allowed_tools steht, wird vorab genehmigt
                # und erreicht den Rueckruf NIE. Die "fragen"-Werkzeuge
                # fehlen deshalb absichtlich -- sie fallen auf den Modus
                # "default" durch und landen dadurch bei can_use_tool.
                allowed_tools=self._stille_werkzeuge(),
                disallowed_tools=["NotebookEdit"],
                permission_mode="default",
                can_use_tool=self.darf_ich,
                # Nichts aus dem Projekt laden. Der Werkzeugserver laeuft
                # in-process und kostet keine Startzeit -- die 2,4 Sekunden
                # von vorhin waren externe MCP-Server.
                setting_sources=[],
                mcp_servers=({SERVER: self.werkzeuge} if self.werkzeuge else {}),
                strict_mcp_config=True,
                # Kurze Zurufe brauchen keine Grundsatzueberlegung.
                effort="low",
                # Wortweise Ausgabe, damit der Mund frueh anfangen kann.
                include_partial_messages=True,
            )
        )
        await self.klient.connect()

    # --- Erlaubnis --------------------------------------------------------

    def _stille_werkzeuge(self) -> list[str]:
        """Werkzeuge, die ohne Nachfrage durchlaufen duerfen."""
        still = [
            voller_name(kurz)
            for kurz, stufe in config.WERKZEUG_STUFEN.items()
            if stufe == "still"
        ]
        return [n for n in still if n in self.namen] + list(
            config.EINGEBAUTE_WERKZEUGE
        )

    @staticmethod
    def _pfadstufe(werkzeug: str, eingabe: dict):
        """Stufe eines eingebauten Werkzeugs anhand von Pfad bzw. Befehl.

        Gibt zusaetzlich einen sprechenden Namen zurueck, damit die
        Rueckfrage sagen kann, worum es geht -- "in config.php schreiben"
        statt "Edit ausfuehren".
        """
        e = eingabe or {}
        if werkzeug in ("Bash", "PowerShell"):
            befehl = str(e.get("command") or "")
            return (schutz.befehl_stufe(befehl), "befehl_ausfuehren",
                    {"befehl": befehl})

        pfad = str(e.get("file_path") or e.get("path") or "")
        if werkzeug in ("Write", "Edit"):
            return (schutz.schreiben_stufe(pfad), "datei_schreiben",
                    {"pfad": pfad})

        # Glob liefert nur Namen, keine Inhalte -- das ist eine mildere
        # Stufe. Sonst muesste Sarvis fuer jeden Blick um Erlaubnis
        # fragen und behauptet stattdessen ins Blaue, etwas gebe es nicht.
        # Geprueft wurde nur "path" -- Glob traegt sein Ziel aber im
        # Pflichtfeld "pattern", "path" ist optional. Gemessen: mit
        # {"pattern": "D:/Strato Server/**/*"} war der Pfad leer,
        # auflisten_stufe("") heisst "frei", und die Dateinamen des
        # Passwortordners gingen ohne eine Rueckfrage ans Modell.
        if werkzeug == "Glob":
            muster = str(e.get("pattern") or "")
            ziel = pfad or muster
            stufe = schutz.auflisten_stufe(ziel)
            if stufe == "frei" and schutz.heikler_ort_beruehrt(pfad, muster):
                stufe = "fragen"
            return stufe, "ordner_ansehen", {"pfad": ziel}

        # Grep durchsucht einen ganzen Baum. Das ist etwas anderes als
        # eine Datei zu lesen: Beim Lesen sieht die Pruefung vorher in
        # die Datei hinein, beim Baum kann sie das nicht.
        if werkzeug == "Grep":
            if not pfad:
                return "still", werkzeug, e   # ohne Pfad = Arbeitsverzeichnis
            return (schutz.durchsuchen_stufe(pfad), "ordner_durchsuchen",
                    {"pfad": pfad, "muster": e.get("pattern") or ""})

        # Read liest Inhalte -- streng, aber mit Blick in die Datei.
        return (schutz.lesen_stufe(pfad), "datei_lesen", {"pfad": pfad})

    async def darf_ich(self, name: str, eingabe: dict, zusammenhang):
        """Wird gerufen, wenn ein Werkzeug nicht vorab genehmigt ist.

        Drei Ausgaenge, und der dritte ist der wichtigste: Was in
        WERKZEUG_STUFEN nicht steht, wird abgelehnt. Eine Erlaubnisliste
        kann nichts uebersehen -- eine Sperrliste schon.
        """
        kurz = kurzer_name(name)
        stufe = config.WERKZEUG_STUFEN.get(kurz)

        def erlauben():
            """Ja sagen -- und einen Ordnerwechsel darin nachvollziehen.

            Der Arbeitsordner wird ausschliesslich hier fortgeschrieben,
            also erst NACH der Entscheidung. Andersherum stellte ein
            Befehl sich seinen eigenen Freifahrtschein aus: 'cd
            D:/Mitra/MCN; <irgendwas>' haette den Ort gesetzt, an dem
            derselbe Befehl gemessen wird.
            """
            if kurz in ("Bash", "PowerShell", "befehl_ausfuehren"):
                schutz.arbeitsordner_merken(
                    str((eingabe or {}).get("command")
                        or (eingabe or {}).get("befehl") or "")
                )
            return PermissionResultAllow()

        # Bei den eingebauten Werkzeugen haengt die Stufe nicht am Werkzeug,
        # sondern daran, WAS angefasst wird. Lesen im Projektordner ist
        # etwas anderes als Schreiben in D:\Mitra.
        if stufe == "pfad":
            stufe, kurz, eingabe = self._pfadstufe(kurz, eingabe)

        # "still" kommt aus WERKZEUG_STUFEN, "frei" aus schutz.py --
        # dasselbe Ergebnis, zwei Herkuenfte. Beide muessen hier stehen,
        # sonst faellt alles Freigegebene ans Ende durch und wird abgelehnt.
        if stufe in ("still", "frei"):
            return erlauben()

        if stufe == "nie":
            return PermissionResultDeny(
                message="Das ist gesperrt — es ließe sich nicht "
                        "zurücknehmen. Sag dem Nutzer, was du vorhattest "
                        "und warum es nicht ging."
            )

        if stufe == "fragen":
            # Eine laufende Freigabe ersetzt die Rueckfrage -- aber nur
            # fuer dasselbe Werkzeug am selben Ort, und nur solange sie
            # laeuft. Das ist die einzige Stelle, an der etwas ohne
            # Nachfrage durchgeht, das sonst fragen wuerde.
            if self.freigaben is not None and self.freigaben.erlaubt(kurz, eingabe):
                print(f"  ~ {kurz}: läuft unter einer Freigabe durch")
                return erlauben()

            if self.nachfragen is None:
                return PermissionResultDeny(
                    message="Rückfragen sind gerade nicht möglich."
                )

            entscheidung, wortlaut = await self.nachfragen(kurz, eingabe)
            if entscheidung == "ja":
                return erlauben()

            # Der Wortlaut geht mit. Ohne ihn erfaehrt das Modell nur
            # "abgelehnt" und nie, WAS gesagt wurde -- eine Einschraenkung
            # wie "ja, aber nur die erste" war damit verloren, bevor sie
            # irgendwo ankommen konnte.
            gesagt = f' Er sagte: "{wortlaut}".' if wortlaut else ""
            if entscheidung == "anders":
                return PermissionResultDeny(
                    message="Der Nutzer hat nicht abgelehnt, sondern es "
                            f"anders gewollt.{gesagt} Setz dieselbe Sache "
                            "geändert noch einmal an. Frag nicht, ob du "
                            "darfst — tu es einfach richtig."
                )
            return PermissionResultDeny(
                message=f"Der Nutzer hat abgelehnt.{gesagt} Tu es nicht und "
                        "frag nicht nochmal nach."
            )

        return PermissionResultDeny(
            message=f"Das Werkzeug {kurz} ist für Sarvis nicht freigegeben."
        )

    def _subagenten_verfolgen(self, nachricht) -> None:
        """Mitschreiben, welche Unter-Arbeiter gerade laufen.

        Start ist ein Werkzeugaufruf aus config.UNTERARBEITER in SEINER
        Nachricht (nicht in der eines Arbeiters), Ende der zugehoerige
        Rueckgabeblock. Ohne das Ende bliebe die Anzeige stehen und
        behauptete Arbeit, die laengst fertig ist.

        Der Name ist gemessen: In dieser Fassung heisst das Werkzeug
        "Agent". Hier stand "Task" -- also sprang die Anzeige nie an.
        """
        if isinstance(nachricht, AssistantMessage):
            for block in nachricht.content:
                if (isinstance(block, ToolUseBlock)
                        and block.name in config.UNTERARBEITER):
                    e = block.input or {}
                    was = (e.get("description") or e.get("subagent_type")
                           or "Arbeiter")
                    self.subagenten[block.id] = str(was)[:40]
        elif isinstance(nachricht, UserMessage):
            inhalt = nachricht.content
            if isinstance(inhalt, list):
                for block in inhalt:
                    if isinstance(block, ToolResultBlock):
                        self.subagenten.pop(block.tool_use_id, None)

    def _arbeiter_verloren(self) -> None:
        """Uebriggebliebene Unter-Arbeiter als abgebrochen vermerken.

        Wer normal fertig wird, ist beim Rueckgabeblock schon aus der
        Liste geflogen. Was hier noch steht, ist mit dem Zug gestorben.
        """
        for was in self.subagenten.values():
            self.abgebrochene.append((was, datetime.now()))
        del self.abgebrochene[:-3]
        self.subagenten.clear()

    def abgebrochene_zeile(self) -> str:
        """Was unfertig liegengeblieben ist -- fuer den Vorspann.

        Ein Unter-Arbeiter stirbt mit dem Zug, in dem er laeuft. Ohne
        diese Zeile weiss Sarvis im naechsten Zug nichts mehr davon und
        fragt "was soll denn als Naechstes rein?", waehrend halbfertige
        Arbeit herumliegt. Genau so passiert -- der Nutzer musste ihm
        seine eigene abgebrochene Arbeit erklaeren.

        Zwei Stunden lang, dann ist es keine Nachricht mehr.
        """
        jetzt = datetime.now()
        self.abgebrochene = [(w, t) for w, t in self.abgebrochene
                             if (jetzt - t).total_seconds() < 7200]
        if not self.abgebrochene:
            return ""
        teile = [f'"{w}" um {t:%H:%M}' for w, t in self.abgebrochene]
        return ("[Mittendrin abgebrochen und NICHT zu Ende gebracht: "
                + "; ".join(teile)
                + ". Frag nicht, was gemacht werden soll -- sieh nach, wie "
                  "weit es ist, und knüpfe dort an.]")

    def subagenten_kurz(self) -> list:
        """Was die Unter-Arbeiter gerade tun -- fuer die Anzeige."""
        return [f"Arbeiter: {w}" for w in self.subagenten.values()]

    async def unterbrechen(self) -> None:
        """Claude mitten im Satz stoppen -- und den Puffer leerraeumen.

        Das Stoppen allein reicht nicht: Die schon erzeugten Nachrichten
        liegen weiter in der Leitung, und die naechste Frage liest sie als
        Erstes. Im Test kam auf "wie viel ist drei plus vier" die Aufzaehlung
        der Bundeslaender von davor -- die Antworten waren um eine Runde
        verschoben. Deshalb hier bis zum Abschluss der abgebrochenen Runde
        leerlesen, bevor wieder etwas gefragt wird.
        """
        if self.klient is None:
            return
        try:
            await self.klient.interrupt()
        except Exception:
            pass  # nicht mehr unterbrechbar heisst: war schon fertig

        # Der Abbruch stoppt nur das Reden. Werkzeuge, die vorher liefen,
        # wirken weiter -- Sarvis muss davon im naechsten Zug wissen, sonst
        # legt er auf "doch auf 10:14" einen zweiten Wecker an, statt den
        # ersten zu aendern. Genau so passiert.
        # Wer beim Abbruch noch lief, ist mit abgebrochen worden.
        self._arbeiter_verloren()

        try:
            if self._offen:
                try:
                    async with asyncio.timeout(10):
                        async for nachricht in self.klient.receive_response():
                            if isinstance(nachricht, ResultMessage):
                                break
                except (TimeoutError, asyncio.TimeoutError):
                    # Stumm geschluckt sah das hinterher aus wie sauber
                    # leergeraeumt. Wenn die Runde nicht leer wird, liegen
                    # ihre Nachrichten noch in der Leitung -- das gehoert
                    # gesagt, und die naechste Runde raeumt kurz nach.
                    self._leitung_unsauber = True
                    print("  (Abbruch: Runde nicht in 10 s leergelesen -- die "
                          "nächste Antwort kann Reste enthalten)")
                except Exception as fehler:
                    self._leitung_unsauber = True
                    print(f"  (Abbruch: Leerlesen fehlgeschlagen -- {fehler})")
                finally:
                    self._offen = False
        finally:
            # ERST jetzt der Schnappschuss: Ein Werkzeug mit Netzverkehr --
            # finanzen_buchen, telegram_senden, mail_senden -- kann waehrend
            # des Leerlesens noch fertig werden und vermerkt danach. Vor dem
            # Leerlesen gezogen, fehlte genau dieser Eintrag im Nachtrag und
            # wurde beim naechsten Zuruf von leeren() weggeraeumt: Sarvis
            # wusste nichts von der Buchung und legte eine zweite an.
            if self.protokoll is not None:
                self._nachtrag = self.protokoll.nachtrag()

    async def stopp(self) -> None:
        # Beenden darf nie das Beenden verhindern: doppelte Aufrufe und ein
        # halb abgebauter Unterprozess sind kein Grund fuer einen Traceback.
        klient, self.klient = self.klient, None
        if klient is None:
            return
        try:
            await klient.disconnect()
        except Exception:
            pass

    # --- Kontext ----------------------------------------------------------

    async def kontext_anteil(self) -> float | None:
        """Wie voll der Kontext ist, 0.0 bis 1.0 -- oder None.

        Kostet nichts: Die Zahl rechnet der CLI-Prozess selbst aus und
        liefert sie ueber den Steuerkanal; es geht keine Anfrage ans
        Modell. Gemessen -- zwischen zwei Abrufen wuchs der Kontext um
        keinen einzigen Token.

        Faellt sie aus, kommt None zurueck und nicht etwa eine Null: Eine
        Wache, die bei einem Fehler "alles frei" meldet, ist schlimmer
        als keine.
        """
        if self.klient is None:
            return None
        try:
            stand = await self.klient.get_context_usage()
            return float(stand.get("percentage") or 0.0) / 100.0
        except Exception as e:
            print(f"  Kontextstand nicht lesbar: {type(e).__name__}: {e}")
            return None

    async def verdichten(self, anweisung: str = "") -> bool:
        """Das Gespraech zusammenfassen -- "/compact" mit eigener Anweisung.

        Ohne Anweisung fasst der Befehl fuer einen Programmierer zusammen
        ("welche Dateien wurden geaendert"). Was ein Sprachassistent
        behalten muss, ist etwas anderes; das steht in
        config.KONTEXT_VERDICHTEN_ANWEISUNG.

        Der Verlauf geht dabei NICHT verloren. Das SDK schreibt ihn
        weiter vollstaendig in die Sitzungsdatei -- geprueft: Nach einem
        "/compact" standen die drei Zurufe von davor unveraendert darin.
        Verdichtet wird nur, was bei jedem Zuruf mitgeschickt wird;
        nachgeschlagen wird mit verlauf_nachschlagen.
        """
        if self.klient is None or self._offen:
            return False
        befehl = f"/compact {anweisung}".strip() if anweisung else "/compact"
        try:
            await self.klient.query(befehl)
            async for nachricht in self.klient.receive_response():
                if isinstance(nachricht, ResultMessage):
                    break
            return True
        except Exception as e:
            print(f"  Verdichten ging nicht: {type(e).__name__}: {e}")
            # Wie beim Abbruch: In der Leitung koennen Reste liegen.
            self._leitung_unsauber = True
            return False

    async def fragen(self, text: str) -> AsyncIterator[str]:
        """Schickt den Zuruf hin und liefert die Antwort in Schnipseln."""
        assert self.klient is not None, "Hirn nicht gestartet"
        self.letzte_kosten = None
        gestroemt = False

        # Wurde in diesem Zug schon ein Wartesatz vorgeschoben?
        gewartet = False
        # Hat der Notnagel schon geredet? TextBlock und ToolUseBlock
        # koennen in DERSELBEN Nachricht stehen -- ohne diese Marke kaeme
        # der Wartesatz hinter einem gerade gesprochenen Satz hinterher.
        gesagt_ohne_strom = False

        vorspann = jetzt_zeile()
        # Was gerade laeuft, geht bei JEDEM Zuruf mit. Das ist Arbeits-
        # gedaechtnis: Sarvis muss sich nicht erinnern, dass ein Wecker
        # existiert -- er sieht es. Erinnerung kann truegen, besonders nach
        # einem Abbruch; eine Zustandszeile kann es nicht.
        if self.zustand_zeile is not None:
            laufendes = self.zustand_zeile()
            if laufendes:
                vorspann += "\n" + laufendes
        verloren = self.abgebrochene_zeile()
        if verloren:
            vorspann += "\n" + verloren
        # Was gerade ohne Rueckfrage durchgeht, gehoert genauso ins
        # Arbeitsgedaechtnis wie ein laufender Timer -- sonst kann
        # Sarvis auf "was darfst du gerade" nur raten.
        if self.freigaben is not None:
            frei = self.freigaben.zeile()
            if frei:
                vorspann += "\n" + frei
        if self._nachtrag:
            vorspann += "\n" + self._nachtrag
            self._nachtrag = ""
        if self.protokoll is not None:
            self.protokoll.leeren()

        # Zweiter Anlauf fuer eine Leitung, die beim letzten Abbruch nicht
        # leer wurde. Kostet im Normalfall nichts -- die Flagge steht nur
        # nach einem gerissenen Leerlesen. Meist ist die alte Runde
        # inzwischen laengst fertig und die Reste liegen sofort bereit.
        if self._leitung_unsauber:
            self._leitung_unsauber = False
            try:
                async with asyncio.timeout(2):
                    async for nachricht in self.klient.receive_response():
                        if isinstance(nachricht, ResultMessage):
                            break
            except Exception:
                pass

        self._offen = True
        await self.klient.query(vorspann + "\n" + text)
        async for nachricht in self.klient.receive_response():
            # Text eines Unter-Arbeiters geht NICHT an den Mund. Die SDK
            # markiert ihn mit parent_tool_use_id. Ohne diese Zeile sprach
            # Sarvis mitten in seiner Antwort englische Saetze mit, die
            # gar nicht seine waren -- "I will start by exploring the
            # backend API", woertlich so passiert. Der Arbeiter meldet an
            # den Orchestrator, nicht an den Nutzer.
            if getattr(nachricht, "parent_tool_use_id", None) is not None:
                continue

            self._subagenten_verfolgen(nachricht)

            if isinstance(nachricht, StreamEvent):
                e = nachricht.event or {}
                if e.get("type") == "content_block_delta":
                    delta = e.get("delta") or {}
                    if delta.get("type") == "text_delta" and delta.get("text"):
                        gestroemt = True
                        yield delta["text"]
            elif isinstance(nachricht, AssistantMessage):
                # Ein einziger Zweig, und zwar mit Absicht: Vorher stand
                # hier "elif ... and not gestroemt" und darunter ein
                # zweites elif fuer den Kranz. Der Fall, fuer den der
                # zweite gebaut war -- Werkzeug laeuft, gesagt wurde noch
                # nichts --, wurde damit vom ersten verschluckt. Der
                # Wartesatz konnte nie fallen und der Kranzpunkt blieb
                # genau dann dunkel, wenn er das Einzige gewesen waere,
                # was ueberhaupt etwas zeigt.
                # Eingebaute Werkzeuge melden sich nicht selbst im Kranz --
                # die eigenen tun das in ihrem Code, hier fehlen nur die.
                for block in nachricht.content:
                    # Notnagel, falls die Teilnachrichten ausbleiben.
                    if isinstance(block, TextBlock) and block.text:
                        if not gestroemt:
                            gesagt_ohne_strom = True
                            yield block.text
                        continue
                    name = getattr(block, "name", "")
                    punkt = self.KRANZ.get(name)
                    if punkt and self.leuchten:
                        self.leuchten(punkt)

                    # Ein langsames Werkzeug faengt an, und gesagt wurde
                    # noch nichts: Dann schiebt der Code den Wartesatz
                    # vor. Er geht denselben Weg wie jeder andere Satz --
                    # durch den Satzsammler in den Mund -- und ist damit
                    # gesprochen, BEVOR das Werkzeug antwortet. Genau das
                    # war der Punkt.
                    if (not gestroemt and not gesagt_ohne_strom
                            and not gewartet
                            and name in config.LANGSAME_WERKZEUGE):
                        gewartet = True
                        yield random.choice(config.WARTESAETZE) + " "
            elif isinstance(nachricht, ResultMessage):
                self.letzte_kosten = nachricht.total_cost_usd
                self._offen = False
                # Ist die Runde vorbei, laeuft auch kein Arbeiter mehr --
                # ein Rest hier waere eine Anzeige, die nie verschwindet.
                # Und er waere mittendrin gestorben, also gehoert er ins
                # Arbeitsgedaechtnis.
                self._arbeiter_verloren()
