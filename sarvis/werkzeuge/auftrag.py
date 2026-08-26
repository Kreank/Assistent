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
import subprocess
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
    tool,
)

from .. import config
from .projekte import _pfad

# Werkzeuge, die der Arbeiter benutzen darf. Alles Uebrige wird abgelehnt.
ARBEITER_WERKZEUGE = [
    "Read", "Write", "Edit", "Glob", "Grep", "Bash",
    "WebSearch", "WebFetch", "TodoWrite", "Task", "NotebookEdit",
]

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
main, nichts außerhalb des Ordners."""


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

    def dauer(self) -> int:
        ende = self.beendet or datetime.now()
        return int((ende - self.begonnen).total_seconds())


class Werkstatt:
    """Haelt die laufenden Auftraege und startet die Arbeiter."""

    def __init__(self, sagen=None, melden=None, leuchten=None):
        self.sagen = sagen        # Sarvis meldet sich von selbst
        self.melden = melden      # Windows-Benachrichtigung
        self.leuchten = leuchten
        self.auftraege: dict[int, Auftrag] = {}
        self._naechste = 1

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

        auftrag = Auftrag(nummer=nummer, projekt=ordner.name, was=was,
                          zweig=zweig, ordner=ordner)
        self.auftraege[nummer] = auftrag
        auftrag.aufgabe = asyncio.get_running_loop().create_task(
            self._arbeiten(auftrag)
        )
        self._sichern()
        return auftrag, ""

    async def _arbeiten(self, auftrag: Auftrag) -> None:
        klient = None
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
            ))
            await klient.connect()
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
                    f"ist fertig, nach {minuten} Minuten. {kurz}")
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
            config.AUFTRAG_DATEI.write_text(json.dumps([
                {"nummer": a.nummer, "projekt": a.projekt, "was": a.was,
                 "zweig": a.zweig, "status": a.status,
                 "begonnen": a.begonnen.isoformat(),
                 "beendet": a.beendet.isoformat() if a.beendet else None}
                for a in self.auftraege.values()
            ], ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError:
            pass

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

    return [auftrag_geben, auftrag_status, auftrag_abbrechen]
