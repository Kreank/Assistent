"""Aufträge: Arbeiter im Hintergrund, die tatsächlich entwickeln.

Der Aufbau, auf den es ankommt -- zwei getrennte Sitzungen:

  Sarvis    schnell, redet mit dir, hat KEINE Schreibrechte.
  Arbeiter  eigene Sitzung, effort high, Schreibrechte NUR im Projekt.

Die Trennung ist nicht Kosmetik. Im SDK erben Unteragenten den
Erlaubnismodus ihres Elternteils und koennen ihn nicht ueberschreiben --
haette Sarvis' Sitzung Schreibrechte, haetten sie alle, ueberall.

Geprüft wird nicht vorher, sondern nachher: Jeder Auftrag arbeitet auf
einem eigenen Git-Zweig und schreibt einen Bericht. Gefaellt das Ergebnis
nicht, ist es ein `git checkout master` -- und weg.
"""
import asyncio
import json
import re
import os
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from claude_agent_sdk import (
    ClaudeAgentOptions,
    ClaudeSDKClient,
    PermissionResultAllow,
    PermissionResultDeny,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    tool,
)

from .. import config
from .projekte import _pfad

# Werkzeuge, die der Arbeiter benutzen darf. Alles Uebrige wird abgelehnt.
ARBEITER_WERKZEUGE = [
    "Read", "Write", "Edit", "Glob", "Grep", "Bash",
    "WebSearch", "WebFetch", "TodoWrite", "NotebookEdit",
    # Unter-Arbeiter: Damit teilt ein Arbeiter grosse Aufgaben auf --
    # "drei bauen, zwei pruefen". Beide Namen, siehe config.UNTERARBEITER.
    *config.UNTERARBEITER,
]

# Gemessen am 26.08.2026: Die Werkzeugaufrufe eines UNTER-Arbeiters
# laufen durch dieselbe Rechtepruefung wie die des Arbeiters. Ein
# Unter-Arbeiter, der ausserhalb des Projektordners lesen wollte, wurde
# abgelehnt -- und die Ablehnung kam beim Arbeiter an, nicht still
# verschluckt. Die Grenze "nichts ausserhalb des Ordners" traegt also
# auch eine Ebene tiefer.

# Shell-Befehle, die auch im eigenen Ordner nichts zu suchen haben.
VERBOTEN = (
    r"\bgit\s+push\b",
    r"\bgit\s+remote\b",
    r"\bshutdown\b", r"\bformat\b", r"\breg\s+(add|delete)\b",
    r"\bnet\s+user\b", r"\brunas\b", r"\bsc\s+(create|delete)\b",
    r"curl[^|]*\|\s*(ba)?sh",       # curl ... | sh
    r"iwr[^|]*\|\s*iex",            # PowerShell-Aequivalent
    r"\brmdir\s+/s\s+[a-z]:\\",
    r"\bdel\s+/[fs]",
)

ARBEITER_PROMPT = """Du arbeitest an einem Projekt für Sascha.

Ablauf:
1. Verschaff dir erst einen Überblick über das Projekt.
2. Setz den Auftrag um. Kleine, nachvollziehbare Schritte.
3. Prüfe deine Arbeit, so weit es geht: Starte was startbar ist, lass
   Tests laufen, wenn es welche gibt. Ungeprüfter Code ist halbe Arbeit.
4. Committe auf dem aktuellen Zweig. Sinnvolle Commit-Nachrichten.
5. Schreib zum Schluss `bericht.md` im Projektordner.

Der Bericht ist das Wichtigste, denn Sascha war nicht dabei. Er enthält:
- Was du gemacht hast, in ganzen Sätzen.
- Was du geprüft hast und was dabei herauskam. Mit Zahlen, wenn es
  welche gibt.
- Woran du unsicher warst, und was du deshalb NICHT gemacht hast.
- Was als Nächstes anstünde.

Schreib den Bericht ehrlich. Wenn etwas nicht funktioniert hat, gehört
das hinein — ein Bericht, der Erfolg meldet, wo keiner war, ist schlimmer
als gar keiner.

Die allerletzte Zeile deiner Antwort beginnt mit `GESPROCHEN:` und
enthält zwei bis drei Sätze, die jemandem vorgelesen werden. Reiner
Fließtext: keine Aufzählung, keine Sternchen, keine Backticks, keine
Dateinamen mit Endung. Sag, was jetzt anders ist und ob es geprüft ist.

Beispiel:
GESPROCHEN: Die Kilometergeld-Berechnung steht, mit dreißig Cent je
Kilometer und kaufmännischer Rundung. Zehn Tests laufen durch. Offen ist
noch, wie mehrere Fahrten zusammengerechnet werden sollen.

Grenzen: Du bleibst im Projektordner. Kein `git push`, kein Merge nach
main, nichts außerhalb des Ordners.

Führe Buch, und zwar WÄHREND der Arbeit, nicht am Ende:

* Lege gleich zu Beginn `fortschritt.md` im Projektordner an und schreibe
  nach jedem abgeschlossenen Teilschritt eine Zeile hinein: was du getan
  hast, was du geprüft hast, was als Nächstes drankommt. Diese Datei ist
  für den Fall, dass du mitten in der Arbeit abgeschnitten wirst — dann
  ist sie das Einzige, woran jemand anknüpfen kann. Ein Bericht, den es
  erst am Ende gibt, gibt es genau dann nicht, wenn er gebraucht wird.
* Committe nach jedem abgeschlossenen Teilschritt, mit einer Nachricht,
  die sagt WAS fertig ist. Der Zweig wird ohnehin nie nach main
  gemergt — häufige Commits kosten dich nichts und sind der einzige
  verlässliche Zwischenstand.
* Wirst du fortgesetzt, lies zuerst `git log`, `git status` und
  `fortschritt.md`. Fang nicht von vorn an."""


def vorlesbar(text: str) -> str:
    """Aus der Schlussnachricht des Arbeiters einen sprechbaren Satz machen.

    Der Arbeiter schreibt fuer Menschen, die lesen -- mit Sternchen,
    Backticks und Aufzaehlungen. Piper spricht das als "Sternchen
    Sternchen kilometergeld punkt py". Deshalb erst die markierte Zeile
    suchen, und was uebrig bleibt, von Formatierung befreien.
    """
    text = (text or "").strip()
    if not text:
        return "Fertig, aber ohne Zusammenfassung."

    for zeile in reversed(text.splitlines()):
        if zeile.strip().upper().startswith("GESPROCHEN:"):
            text = zeile.split(":", 1)[1]
            break
    else:
        # Kein Marker: der letzte zusammenhaengende Absatz ist die beste
        # Naeherung -- Aufzaehlungen davor faellt so von selbst weg.
        absaetze = [a.strip() for a in text.split("\n\n") if a.strip()]
        text = absaetze[-1] if absaetze else text

    text = re.sub(r"```.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"[`*_#>]+", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)   # Links
    text = re.sub(r"\b([\w-]+)\.(py|md|txt|json|js|ts|html|css)\b",
                  r"\1", text)                              # Dateiendungen
    text = " ".join(text.split())
    return text[:600] or "Fertig, aber ohne Zusammenfassung."


@dataclass
class Auftrag:
    nummer: int
    projekt: str
    was: str
    zweig: str
    ordner: Path
    status: str = "läuft"          # läuft | fertig | fehler | abgebrochen
    begonnen: datetime = field(default_factory=datetime.now)
    beendet: datetime | None = None
    ergebnis: str = ""
    aufgabe: object = None
    stand_text: str = ""           # wie weit er kam, aus Git gelesen
    # Die Kennung der Claude-Sitzung. Wird VOR dem Start vergeben und
    # gesichert -- sonst waere ein Absturz nach zwei Sekunden nicht
    # fortsetzbar, weil die Kennung erst am Ende zurueckkaeme.
    sitzung: str = ""
    zuletzt_gesehen: str = ""      # ISO-Zeit des letzten Lebenszeichens

    def dauer(self) -> int:
        ende = self.beendet or datetime.now()
        return int((ende - self.begonnen).total_seconds())


def journal(nummer: int, ereignis: str, **felder) -> None:
    """Eine Zeile ans Fortschritts-Journal anhaengen.

    Anhaengen statt Ueberschreiben ist der ganze Trick: Stirbt der
    Prozess mitten im Schreiben, ist hoechstens die letzte Zeile
    zerrissen -- alles davor bleibt gueltig und lesbar. Beim
    Ueberschreiben einer JSON-Datei ist dagegen im schlimmsten Fall
    ALLES weg, weil das Schreiben mit einem Kuerzen auf null Bytes
    beginnt.
    """
    zeile = {"zeit": datetime.now().isoformat(timespec="seconds"),
             "nummer": nummer, "ereignis": ereignis, **felder}
    try:
        with open(config.AUFTRAG_JOURNAL, "a", encoding="utf-8") as f:
            f.write(json.dumps(zeile, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        pass          # ein fehlendes Journal darf keinen Auftrag aufhalten


def journal_lesen() -> list:
    """Alle lesbaren Zeilen. Kaputte werden uebersprungen, nicht beklagt."""
    zeilen = []
    try:
        roh = config.AUFTRAG_JOURNAL.read_text(encoding="utf-8").splitlines()
    except OSError:
        return zeilen
    for z in roh:
        z = z.strip()
        if not z:
            continue
        try:
            zeilen.append(json.loads(z))
        except ValueError:
            continue   # abgerissene letzte Zeile eines Absturzes
    return zeilen


def _atomar_schreiben(pfad, text: str) -> None:
    """Datei ersetzen, ohne sie je halb dastehen zu lassen.

    Erst in eine Nebendatei IM SELBEN ORDNER schreiben (sonst waere das
    Ersetzen ein Kopiervorgang ueber Laufwerksgrenzen), auf die Platte
    zwingen, dann tauschen.

    Die Wiederholungsschleife ist keine Ziererei: Unter Windows wirft das
    Ersetzen PermissionError, wenn irgendwer die Zieldatei gerade offen
    hat -- ein Virenscanner, der die frisch geschriebene Datei prueft,
    genuegt. Unter Linux liefe derselbe Aufruf klaglos durch.
    """
    pfad = Path(pfad)
    fd, tmp = tempfile.mkstemp(dir=str(pfad.parent), prefix=pfad.name + ".",
                               suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        for versuch in range(5):
            try:
                os.replace(tmp, pfad)
                return
            except PermissionError:
                if versuch == 4:
                    raise
                time.sleep(0.02 * (versuch + 1))
    finally:
        try:
            Path(tmp).unlink()
        except OSError:
            pass


class Werkstatt:
    """Haelt die laufenden Auftraege und startet die Arbeiter."""

    def __init__(self, sagen=None, melden=None, leuchten=None):
        self.sagen = sagen        # Sarvis meldet sich von selbst
        self.melden = melden      # Windows-Benachrichtigung
        self.leuchten = leuchten
        self.auftraege: dict[int, Auftrag] = {}
        self._naechste = 1
        self._laden()

    def _laden(self) -> None:
        """Was frueher lief, aus der Datei holen.

        auftraege.json wurde bisher nur geschrieben und nie gelesen. Zwei
        Folgen, beide unangenehm: Die Nummerierung fing nach jedem Start
        wieder bei 1 an und ueberschrieb beim naechsten Sichern die alten
        Eintraege -- und ein Auftrag, der beim Beenden noch lief, war
        spurlos weg.

        Er laeuft NICHT weiter: Der Arbeiter lebt im Prozess von Sarvis,
        und der ist beendet worden. Genau das muss man aber erfahren
        koennen, statt es aus einem Git-Zweig zu erraten. Deshalb wird
        "laeuft" beim Laden zu "unterbrochen".
        """
        try:
            roh = json.loads(config.AUFTRAG_DATEI.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError):
            # Zerrissene oder leere Datei. Frueher hiess das: alle
            # Auftraege stillschweigend vergessen, samt Nummerierung.
            # Das Journal weiss es noch.
            print("  (auftraege.json unlesbar -- rekonstruiere aus dem Journal)")
            roh = self._aus_journal()
        if not isinstance(roh, list):
            return
        for e in roh:
            try:
                nummer = int(e["nummer"])
                a = Auftrag(
                    nummer=nummer,
                    projekt=str(e.get("projekt") or ""),
                    was=str(e.get("was") or ""),
                    zweig=str(e.get("zweig") or ""),
                    ordner=Path(str(e.get("ordner") or ".")),
                    status=str(e.get("status") or "fertig"),
                    begonnen=datetime.fromisoformat(e["begonnen"]),
                    beendet=(datetime.fromisoformat(e["beendet"])
                             if e.get("beendet") else None),
                )
            except (KeyError, TypeError, ValueError):
                continue
            a.sitzung = str(e.get("sitzung") or "")
            a.zuletzt_gesehen = str(e.get("zuletzt_gesehen") or "")
            if a.status == "läuft":
                a.status = "unterbrochen"
                a.beendet = a.beendet or datetime.now()
                journal(nummer, "unterbrochen",
                        grund="Sarvis wurde neu gestartet")
            self.auftraege[nummer] = a
            self._naechste = max(self._naechste, nummer + 1)
        # Fuer die Unterbrochenen einmal nachsehen, wie weit sie kamen.
        # Nur fuer die -- Git zu befragen kostet Zeit, und bei fertigen
        # Auftraegen ist die Antwort ohne Wert.
        for a in self.auftraege.values():
            if a.status == "unterbrochen":
                try:
                    a.stand_text = self.stand(a)
                except Exception:
                    a.stand_text = ""

    @staticmethod
    def _aus_journal() -> list:
        """Aus dem Journal wieder eine Auftragsliste falten.

        Das Journal ist die Wahrheit ueber den Verlauf; auftraege.json
        ist nur die bequeme Zusammenfassung. Geht die kaputt, laesst sie
        sich hieraus neu bauen.
        """
        stand = {}
        for z in journal_lesen():
            nummer = z.get("nummer")
            if not isinstance(nummer, int):
                continue
            e = stand.setdefault(nummer, {"nummer": nummer, "status": "läuft"})
            for feld in ("projekt", "was", "zweig", "ordner", "sitzung",
                         "begonnen", "beendet", "status", "zuletzt_gesehen"):
                if z.get(feld):
                    e[feld] = z[feld]
            if z.get("ereignis") == "beendet":
                e["status"] = z.get("status", "fertig")
            elif z.get("ereignis") == "lebt":
                e["zuletzt_gesehen"] = z.get("zeit", "")
        return list(stand.values())

    def unterbrochene(self) -> list:
        """Auftraege, die ein Neustart mittendrin erwischt hat."""
        return [a for a in self.auftraege.values() if a.status == "unterbrochen"]

    # --- Erlaubnis des Arbeiters ------------------------------------------

    def _wachhund(self, ordner: Path):
        """Erlaubnispruefer fuer genau diesen Arbeiter.

        Bewusst selbst geschrieben statt ueber Musterregeln: Ich will
        genau wissen, was durchkommt. Der Ordner ist die Grenze.
        """
        wurzel = ordner.resolve()

        def innerhalb(pfad: str) -> bool:
            try:
                p = Path(pfad)
                p = p if p.is_absolute() else (wurzel / p)
                p = p.resolve()
            except (OSError, ValueError):
                return False
            return p == wurzel or wurzel in p.parents

        async def darf(name: str, eingabe: dict, zusammenhang):
            if name not in ARBEITER_WERKZEUGE:
                return PermissionResultDeny(
                    message=f"{name} ist für diesen Auftrag nicht freigegeben."
                )

            if name in ("Write", "Edit", "NotebookEdit"):
                ziel = eingabe.get("file_path") or eingabe.get("path") or ""
                if not innerhalb(str(ziel)):
                    return PermissionResultDeny(
                        message="Außerhalb des Projektordners wird nicht "
                                "geschrieben."
                    )
                return PermissionResultAllow()

            if name in ("Read", "Glob", "Grep"):
                # Lesen ist keine Handlung, aber ein Abfluss: Was der
                # Arbeiter liest, landet in seinem Kontext und geht damit
                # nach draussen. Ohne diese Sperre koennte er die .env mit
                # den Telegram-Zugangsdaten oeffnen. Fehlt der Pfad, meint
                # das Werkzeug ohnehin den Projektordner.
                ziel = (eingabe.get("file_path") or eingabe.get("path")
                        or eingabe.get("pattern") or "")
                if ziel and Path(str(ziel)).is_absolute() \
                        and not innerhalb(str(ziel)):
                    return PermissionResultDeny(
                        message="Außerhalb des Projektordners wird nichts "
                                "gelesen."
                    )
                return PermissionResultAllow()

            if name == "Bash":
                befehl = str(eingabe.get("command") or "")
                for muster in VERBOTEN:
                    if re.search(muster, befehl, re.IGNORECASE):
                        return PermissionResultDeny(
                            message="Dieser Befehl ist gesperrt."
                        )
                # Absolute Pfade auf andere Laufwerke oder Ordner: nein.
                for gefunden in re.findall(r"[a-zA-Z]:[\\/][^\s\"']*", befehl):
                    if not innerhalb(gefunden):
                        return PermissionResultDeny(
                            message=f"{gefunden} liegt außerhalb des Projekts."
                        )
                return PermissionResultAllow()

            return PermissionResultAllow()

        return darf

    # --- Auftrag starten ---------------------------------------------------

    def starten(self, projekt: str, was: str) -> tuple[Auftrag | None, str]:
        ordner = _pfad(projekt)
        if ordner is None or not ordner.exists():
            return None, "Dieses Projekt finde ich nicht."

        laeuft = [a for a in self.auftraege.values()
                  if a.status == "läuft" and a.ordner == ordner]
        if laeuft:
            return None, (f"Im Projekt {ordner.name} läuft schon Auftrag "
                          f"{laeuft[0].nummer}. Erst den abwarten.")

        nummer = self._naechste
        self._naechste += 1
        zweig = f"sarvis/{nummer}-{re.sub(r'[^a-z0-9]+', '-', was.lower())[:28].strip('-')}"

        try:
            subprocess.run(["git", "checkout", "-q", "-b", zweig], cwd=ordner,
                           check=True, capture_output=True, timeout=30)
        except (subprocess.SubprocessError, OSError) as e:
            return None, f"Der Git-Zweig ließ sich nicht anlegen: {e}"

        # Die Sitzungskennung wird HIER vergeben, nicht vom SDK, und
        # steht damit in der Datei, bevor die erste Zeile Arbeit
        # existiert. Kaeme sie erst mit der Schlussmeldung zurueck, waere
        # ausgerechnet der abgebrochene Auftrag der einzige ohne Kennung
        # -- also der einzige, den man nicht fortsetzen kann.
        auftrag = Auftrag(nummer=nummer, projekt=ordner.name, was=was,
                          zweig=zweig, ordner=ordner,
                          sitzung=str(uuid.uuid4()))
        self.auftraege[nummer] = auftrag
        journal(nummer, "gestartet", projekt=ordner.name, was=was,
                zweig=zweig, ordner=str(ordner), sitzung=auftrag.sitzung,
                begonnen=auftrag.begonnen.isoformat(timespec="seconds"))
        self._sichern()          # erst festhalten, dann loslaufen
        auftrag.aufgabe = asyncio.get_running_loop().create_task(
            self._arbeiten(auftrag)
        )
        return auftrag, ""

    def stand(self, auftrag) -> str:
        """Wie weit ist der Auftrag wirklich gekommen? Aus Git, nicht aus Absicht.

        Nach einem Abbruch ist das Protokoll eine Behauptung, der Zweig
        eine Tatsache. Deshalb wird hier nachgesehen und nicht geraten.
        """
        def git(*args):
            try:
                e = subprocess.run(["git", *args], cwd=auftrag.ordner,
                                   capture_output=True, text=True, timeout=10)
                return e.stdout.strip() if e.returncode == 0 else ""
            except (OSError, subprocess.SubprocessError):
                return ""
        commits = [z for z in git("log", auftrag.zweig, "--not", "main",
                                  "--oneline").splitlines() if z.strip()]
        offen = [z for z in git("status", "--porcelain").splitlines() if z.strip()]
        teile = []
        if commits:
            teile.append(f"{len(commits)} Commits, zuletzt: {commits[0][:60]}")
        else:
            teile.append("noch kein Commit")
        if offen:
            teile.append(f"{len(offen)} Dateien ungespeichert geändert")
        fortschritt = auftrag.ordner / "fortschritt.md"
        if fortschritt.exists():
            try:
                letzte = [z for z in fortschritt.read_text(
                    encoding="utf-8", errors="replace").splitlines() if z.strip()]
                if letzte:
                    teile.append("zuletzt notiert: " + letzte[-1][:80])
            except OSError:
                pass
        return "; ".join(teile)

    async def _arbeiten(self, auftrag: Auftrag, fortsetzen: bool = False) -> None:
        klient = None
        letztes_werkzeug = ""
        letztes_zeichen = time.monotonic()
        try:
            klient = ClaudeSDKClient(options=ClaudeAgentOptions(
                model=config.MODELL,
                system_prompt=ARBEITER_PROMPT,
                cwd=str(auftrag.ordner),
                allowed_tools=[],                 # nichts vorab genehmigen --
                can_use_tool=self._wachhund(auftrag.ordner),   # alles prüfen
                permission_mode="default",
                setting_sources=[],
                mcp_servers={},
                strict_mcp_config=True,
                effort="high",       # anders als Sarvis: hier zählt Gründlichkeit
                max_turns=config.AUFTRAG_ZUEGE,
                # Beim ersten Lauf die Kennung VORGEBEN, beim Fortsetzen
                # dieselbe wieder aufnehmen. Gemessen: Der Arbeiter hat
                # danach seinen eigenen Verlauf zurueck.
                **({"resume": auftrag.sitzung} if fortsetzen
                   else {"session_id": auftrag.sitzung}),
            ))
            await klient.connect()
            if fortsetzen:
                await klient.query(
                    "Du wurdest mitten in der Arbeit unterbrochen. Sieh zuerst "
                    "nach, wie weit du gekommen bist (git log, git status, "
                    "fortschritt.md), und mach dann weiter. Fang NICHT von "
                    "vorn an.\n\n"
                    f"Ursprünglicher Auftrag: {auftrag.was}"
                )
            else:
                await klient.query(
                    f"Projekt: {auftrag.ordner}\nZweig: {auftrag.zweig}\n\n"
                    f"Auftrag: {auftrag.was}"
                )
            letzter = ""
            async for nachricht in klient.receive_response():
                if hasattr(nachricht, "content"):
                    for block in getattr(nachricht, "content", []) or []:
                        if isinstance(block, TextBlock) and block.text.strip():
                            letzter = block.text.strip()
                        elif isinstance(block, ToolUseBlock):
                            letztes_werkzeug = block.name

                # Lebenszeichen ins Journal. Nicht als Stoppuhr, sondern
                # damit sich hinterher sagen laesst, wann er zuletzt
                # gesehen wurde -- und woran er da war.
                if (time.monotonic() - letztes_zeichen
                        >= config.AUFTRAG_LEBENSZEICHEN_SEK):
                    letztes_zeichen = time.monotonic()
                    auftrag.zuletzt_gesehen = datetime.now().isoformat(
                        timespec="seconds")
                    journal(auftrag.nummer, "lebt", werkzeug=letztes_werkzeug)
                if isinstance(nachricht, ResultMessage):
                    break
            auftrag.ergebnis = vorlesbar(letzter)
            auftrag.status = "fertig"
        except asyncio.CancelledError:
            auftrag.status = "abgebrochen"
            raise
        except Exception as e:
            auftrag.status = "fehler"
            auftrag.ergebnis = f"{type(e).__name__}: {e}"
        finally:
            auftrag.beendet = datetime.now()
            journal(auftrag.nummer, "beendet", status=auftrag.status,
                    beendet=auftrag.beendet.isoformat(timespec="seconds"))
            if klient is not None:
                try:
                    await klient.disconnect()
                except Exception:
                    pass
            self._sichern()

        await self._melden(auftrag)

    async def _melden(self, auftrag: Auftrag) -> None:
        minuten = max(1, auftrag.dauer() // 60)
        if auftrag.status == "fertig":
            kurz = " ".join(auftrag.ergebnis.split())[:400]
            text = (f"Auftrag {auftrag.nummer} im Projekt {auftrag.projekt} "
                    f"ist fertig, nach {minuten} Minuten. {kurz} "
                    "Soll ich es dir zeigen?")
            titel = f"Auftrag fertig: {auftrag.projekt}"
        elif auftrag.status == "abgebrochen":
            text = f"Auftrag {auftrag.nummer} wurde abgebrochen."
            titel = "Auftrag abgebrochen"
        else:
            text = (f"Auftrag {auftrag.nummer} im Projekt {auftrag.projekt} "
                    f"ist gescheitert. {auftrag.ergebnis[:200]}")
            titel = f"Auftrag gescheitert: {auftrag.projekt}"

        if self.melden is not None:
            self.melden(titel, f"Zweig {auftrag.zweig} · Bericht in bericht.md")
        if self.sagen is not None:
            await self.sagen(text)

    # --- Zustand ------------------------------------------------------------

    def fortsetzen(self, nummer: int) -> tuple:
        """Einen unterbrochenen Auftrag da weitermachen lassen, wo er war.

        Bewusst NUR auf Ansage. Kein System, das ich gefunden habe, nimmt
        so etwas von allein wieder auf -- und das aus gutem Grund: Der
        Arbeiter wuerde auf seinem eigenen halbfertigen Stand
        weiterbauen, ohne dass jemand ihn gesehen hat.
        """
        a = self.auftraege.get(int(nummer or 0))
        if a is None:
            return None, "Diesen Auftrag kenne ich nicht."
        if a.status not in ("unterbrochen", "fehler", "abgebrochen"):
            return None, f"Auftrag {a.nummer} ist {a.status} -- da gibt es nichts fortzusetzen."
        if not a.sitzung:
            return None, ("Von diesem Auftrag habe ich keine Sitzungskennung. "
                          "Er stammt noch aus der Zeit davor -- ich kann nur "
                          "einen neuen anlegen.")
        if not a.ordner.exists():
            return None, f"Den Projektordner {a.ordner} gibt es nicht mehr."

        a.status = "läuft"
        a.beendet = None
        journal(a.nummer, "fortgesetzt", sitzung=a.sitzung)
        self._sichern()
        a.aufgabe = asyncio.get_running_loop().create_task(
            self._arbeiten(a, fortsetzen=True)
        )
        return a, ""

    def alles_abbrechen(self) -> int:
        """Jeden laufenden Auftrag anhalten. Rueckgabe: wie viele es waren.

        Fuer das gesprochene "Stopp". Ueber auftrag_abbrechen muesste
        Sarvis erst die Nummer nennen -- und dazu das Hirn fragen, das
        genau in diesem Moment nicht mehr gefragt werden soll.
        """
        n = 0
        for a in self.auftraege.values():
            if a.status == "läuft" and a.aufgabe is not None and not a.aufgabe.done():
                a.aufgabe.cancel()
                n += 1
        return n

    def _sichern(self) -> None:
        try:
            _atomar_schreiben(config.AUFTRAG_DATEI, json.dumps([
                {"nummer": a.nummer, "projekt": a.projekt, "was": a.was,
                 "zweig": a.zweig, "status": a.status,
                 "ordner": str(a.ordner),
                 "sitzung": a.sitzung,
                 "zuletzt_gesehen": a.zuletzt_gesehen,
                 "begonnen": a.begonnen.isoformat(),
                 "beendet": a.beendet.isoformat() if a.beendet else None}
                for a in self.auftraege.values()
            ], ensure_ascii=False, indent=1))
        except OSError:
            pass

    def laufende_kurz(self) -> list:
        """Was gerade arbeitet -- kurz genug fuer die Anzeige."""
        return [f"Auftrag {a.nummer}: {a.projekt}"
                for a in sorted(self.auftraege.values(), key=lambda x: x.nummer)
                if a.status == "läuft"]

    def uebersicht(self) -> list[str]:
        if not self.auftraege:
            return []
        zeilen = []
        for a in sorted(self.auftraege.values(), key=lambda x: -x.nummer)[:10]:
            dauer = f"{max(1, a.dauer() // 60)} min"
            zeilen.append(
                f"Auftrag {a.nummer} · {a.projekt} · {a.status} · {dauer}"
                f" · Zweig {a.zweig} · {a.was[:60]}"
            )
        return zeilen


def werkzeuge(werkstatt: Werkstatt, protokoll=None, leuchten=None) -> list:
    def vermerken(text: str):
        if protokoll is not None:
            protokoll.merken(text)

    @tool(
        "auftrag_geben",
        "Lässt im Hintergrund an einem Projekt arbeiten und meldet sich von "
        "selbst, wenn es fertig ist. Für alles, was länger dauert als eine "
        "Antwort: Funktion einbauen, Fehler suchen, umbauen. Der Auftrag "
        "sollte so ausformuliert sein, dass jemand ohne Vorwissen ihn "
        "versteht — der Arbeiter kennt euer Gespräch nicht.",
        {
            "type": "object",
            "properties": {
                "projekt": {"type": "string",
                            "description": "Projektname aus projekt_liste."},
                "was": {"type": "string",
                        "description": "Der Auftrag, ausformuliert und "
                                       "vollständig. Ruhig mehrere Sätze."},
            },
            "required": ["projekt", "was"],
        },
    )
    async def auftrag_geben(args):
        auftrag, fehler = werkstatt.starten(
            (args.get("projekt") or "").strip(),
            (args.get("was") or "").strip(),
        )
        if auftrag is None:
            return {"content": [{"type": "text", "text": fehler}],
                    "is_error": True}
        if leuchten:
            leuchten("Aufträge")
        vermerken(f"auftrag_geben: Auftrag {auftrag.nummer} läuft im Projekt "
                  f"{auftrag.projekt} auf Zweig {auftrag.zweig}.")
        return {"content": [{"type": "text", "text":
                f"Auftrag {auftrag.nummer} läuft im Projekt "
                f"{auftrag.projekt}, auf dem Zweig {auftrag.zweig}. "
                "Ich melde mich, wenn er fertig ist."}]}

    @tool(
        "auftrag_status",
        "Sagt, welche Aufträge laufen oder gelaufen sind — mit Zweig, Dauer "
        "und Stand.",
        {"type": "object", "properties": {}},
    )
    async def auftrag_status(args):
        zeilen = werkstatt.uebersicht()
        if not zeilen:
            return {"content": [{"type": "text", "text":
                    "Es läuft kein Auftrag und es lief auch keiner."}]}
        return {"content": [{"type": "text", "text": "\n".join(zeilen)}]}

    @tool(
        "auftrag_abbrechen",
        "Bricht einen laufenden Auftrag ab. Was bis dahin committet wurde, "
        "bleibt auf dem Zweig stehen.",
        {
            "type": "object",
            "properties": {
                "nummer": {"type": "integer", "description": "Auftragsnummer."}
            },
            "required": ["nummer"],
        },
    )
    async def auftrag_abbrechen(args):
        a = werkstatt.auftraege.get(int(args.get("nummer") or 0))
        if a is None or a.status != "läuft":
            return {"content": [{"type": "text", "text":
                    "Dieser Auftrag läuft nicht."}], "is_error": True}
        if a.aufgabe is not None:
            a.aufgabe.cancel()
        vermerken(f"auftrag_abbrechen: Auftrag {a.nummer} abgebrochen.")
        return {"content": [{"type": "text", "text":
                f"Auftrag {a.nummer} abgebrochen. Der Zweig {a.zweig} bleibt."}]}

    @tool(
        "auftrag_fortsetzen",
        "Setzt einen unterbrochenen Auftrag dort fort, wo er aufgehört hat — "
        "mit dem Gedächtnis des ursprünglichen Arbeiters. Für 'mach da weiter' "
        "nach einem Neustart. Fängt NICHT von vorn an.",
        {
            "type": "object",
            "properties": {
                "nummer": {"type": "integer", "description": "Auftragsnummer."}
            },
            "required": ["nummer"],
        },
    )
    async def auftrag_fortsetzen(args):
        a, fehler = werkstatt.fortsetzen(args.get("nummer"))
        if a is None:
            return {"content": [{"type": "text", "text": fehler}],
                    "is_error": True}
        blinken()
        vermerken(f"auftrag_fortsetzen: Auftrag {a.nummer} läuft weiter.")
        return {"content": [{"type": "text", "text":
                f"Auftrag {a.nummer} läuft weiter, auf Zweig {a.zweig}. "
                "Er sieht sich erst an, wie weit er war."}]}

    return [auftrag_geben, auftrag_status, auftrag_abbrechen,
            auftrag_fortsetzen]
