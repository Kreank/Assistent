"""Wie riskant ist ein Zugriff -- und wie sagt man das in einem Satz?

Der Grundsatz: nicht aussperren, sondern nachfragen. Ein Assistent, der
nichts anfassen darf, nuetzt nichts. Aber die Rueckfrage muss tragen, was
sie beim Tippen nicht muss -- naemlich alles, was du zum Entscheiden
brauchst, in einem hoerbaren Satz.

Drei Stufen:

  frei     Lesen dort, wo ohnehin gearbeitet wird -- laeuft durch.
  fragen   Alles Schreibende, alles Ausserhalb, alles Heikle.
  nie      Eine sehr kurze Liste. Begruendung unten.
"""
import re
from pathlib import Path

from . import config

# Dateien, deren Inhalt Zugaenge oeffnet. Loesen eine deutlichere
# Rueckfrage aus -- "das ist eine Datei mit Zugangsdaten".
HEIKEL = (
    r"\.env$", r"\.pem$", r"\.key$", r"\.pfx$", r"\.p12$", r"\.ppk$",
    r"\.session$", r"id_rsa", r"\.kdbx$", r"\.ovpn$",
    r"passw", r"kennwor", r"secret", r"credential", r"token",
    r"\.aws[/\\]", r"\.ssh[/\\]", r"\.gnupg[/\\]",
)

# Die einzige harte Sperre. Nicht weil Sarvis dort nichts zu suchen
# haette, sondern weil es EINWEGTUEREN sind:
#   - Wer WERKZEUG_STUFEN aendert, schaltet alle kuenftigen Rueckfragen
#     ab. Eine einzige Zustimmung wuerde jede weitere ersetzen.
#   - Wer die Sitzungsdatei liest, hat das Telegram-Konto.
#   - Windows-Systemordner repariert kein "war doch nicht so gemeint".
NIE_SCHREIBEN = (
    r"^[A-Z]:[/\\]Windows[/\\]",
    r"^[A-Z]:[/\\]Program Files",
    r"[/\\]sarvis[/\\]config\.py$",
    r"[/\\]sarvis[/\\]schutz\.py$",
)
NIE_LESEN = (
    r"[/\\]sarvis\.session$",
    r"[/\\]Sarvis[/\\]\.env$",
)

# Shell-Befehle, die nicht mit einem gesprochenen "ja" beantwortbar sind.
NIE_BEFEHL = (
    r"\bformat\s+[a-z]:", r"\bshutdown\b", r"\bdiskpart\b",
    # PowerShell-Entsprechungen. Unter Windows heisst Claude Codes
    # Shell-Werkzeug "PowerShell", nicht "Bash" -- eine Sperrliste, die
    # nur cmd-Befehle kennt, sperrt hier gar nichts.
    r"\bFormat-Volume\b", r"\bStop-Computer\b", r"\bRestart-Computer\b",
    r"\bClear-Disk\b", r"\bInitialize-Disk\b", r"\bSet-ExecutionPolicy\b",
    r"\bRemove-Item\b[^|]*\bHK(LM|CU):",
    r"\bbcdedit\b", r"\bvssadmin\b.*\bdelete\b",
    r"\bcipher\s+/w", r"\breg\s+delete\s+HK(LM|EY_LOCAL)",
    r"curl[^|]*\|\s*(ba)?sh", r"iwr[^|]*\|\s*iex",
    r"rm\s+-rf\s+[/~]\s*$", r"\bdel\s+/[fs].*[a-z]:\\\s*$",
)


def _passt(pfad: str, muster) -> bool:
    p = str(pfad).replace("\\", "/")
    return any(re.search(m, p, re.IGNORECASE) for m in muster)


def heikel(pfad: str) -> bool:
    """Enthaelt die Datei vermutlich Zugangsdaten?"""
    return _passt(pfad, HEIKEL)


def _unter(pfad: str, wurzeln) -> bool:
    try:
        p = Path(pfad).resolve()
    except (OSError, ValueError):
        return False
    for w in wurzeln:
        try:
            w = Path(w).resolve()
        except (OSError, ValueError):
            continue
        if p == w or w in p.parents:
            return True
    return False


def lesen_stufe(pfad: str) -> str:
    if not pfad:
        return "frei"                      # kein Pfad = Arbeitsverzeichnis
    if _passt(pfad, NIE_LESEN):
        return "nie"
    if heikel(pfad):
        return "fragen"
    if _unter(pfad, config.FREI_LESEN):
        return "frei"
    return "fragen"


def auflisten_stufe(pfad: str) -> str:
    """Nur Namen sehen, keine Inhalte -- eine eigene, mildere Stufe.

    Zu wissen, DASS es "D:\\Privat" gibt, ist etwas anderes als zu lesen,
    was darin steht. Ohne diese Trennung muss Sarvis fuer jeden Blick um
    Erlaubnis fragen und behauptet lieber ins Blaue, ein Ordner existiere
    nicht -- genau das ist passiert. Wer nicht nachsehen darf, raet.
    """
    if not pfad:
        return "frei"
    if _passt(pfad, NIE_SCHREIBEN) or _passt(pfad, NIE_LESEN):
        return "nie"
    return "frei"


def schreiben_stufe(pfad: str) -> str:
    if _passt(pfad, NIE_SCHREIBEN):
        return "nie"
    if _unter(pfad, config.FREI_SCHREIBEN):
        return "frei"
    return "fragen"


# Befehle, die nur hinsehen. Ohne diese Liste fragt Sarvis vor jedem
# "git status" nach, und dann schaltet man ihn nach zehn Minuten ab.
NUR_SCHAUEN = (
    r"^git\s+(status|log|diff|branch|show|remote\s+-v)\b",
    r"^(ls|dir|pwd|tree)\b",
    # PowerShell schaut mit anderen Worten hin. Ohne diese Zeilen fragt
    # Sarvis vor jedem Blick nach -- und behauptet lieber ins Blaue,
    # ein Ordner existiere nicht.
    r"^(Get-ChildItem|gci|Get-Location|Test-Path|Resolve-Path|Split-Path)\b",
    r"^Get-(Command|Date|Host|Process|Volume|PSDrive)\b",
    # Anzeigeverben aus der Pipe. "Get-ChildItem D:\ | Select-Object Name"
    # wird in zwei Teile zerlegt, und beide muessen harmlos sein.
    # Where-Object und ForEach-Object fehlen absichtlich: die nehmen
    # Skriptbloecke entgegen, in denen alles Moegliche stehen kann.
    r"^(Select-Object|Sort-Object|Format-(Table|List|Wide)"
    r"|Measure-Object|Out-String|Select-String)\b",
    r"^(python|py|node|npm|pip|git)\s+(--version|-V|version)\b",
    r"^(python|py)\s+-m\s+(pytest|unittest)\b",
    r"^(pytest|npm\s+test|npm\s+run\s+test)\b",
    # "where" braucht ein Leerzeichen dahinter. Sonst trifft das Muster
    # auch "Where-Object" -- der Bindestrich ist eine Wortgrenze, \b
    # allein reicht hier nicht. Und in einem Where-Object-Skriptblock
    # kann alles Moegliche stehen.
    r"^where\s", r"^which\s", r"^echo\b",
)


def befehl_stufe(befehl: str) -> str:
    befehl = (befehl or "").strip()
    if any(re.search(m, befehl, re.IGNORECASE) for m in NIE_BEFEHL):
        return "nie"

    # Verkettungen aufteilen: "git status && rm -rf x" ist nicht harmlos,
    # nur weil es harmlos anfaengt.
    teile = [t.strip() for t in re.split(r"&&|\|\||;|\|", befehl) if t.strip()]
    if teile and all(
        any(re.search(m, t, re.IGNORECASE) for m in NUR_SCHAUEN) for t in teile
    ):
        # Auflisten darf ueberall hinsehen, Inhalte lesen nicht. "dir D:\\"
        # zeigt nur Namen -- dafuer jedes Mal zu fragen, war der Grund,
        # warum Sarvis lieber ins Blaue behauptete, ein Ordner existiere
        # nicht, statt nachzusehen.
        nur_namen = all(
            re.match(r"^(ls|dir|tree|pwd|Get-ChildItem|gci"
                     r"|Get-Location|Test-Path|Resolve-Path|Split-Path"
                     r"|Get-PSDrive|Get-Volume|Select-Object|Sort-Object"
                     r"|Format-Table|Measure-Object)\b", t, re.IGNORECASE)
            for t in teile
        )
        pruefer = auflisten_stufe if nur_namen else lesen_stufe
        for pfad in re.findall(r"[a-zA-Z]:[\\/][^\s\"']*", befehl):
            if pruefer(pfad) != "frei":
                return "fragen"
        return "frei"

    return "fragen"


# --- Wie man einen Pfad ausspricht ---------------------------------------

def sprechbar(pfad: str, fall: str = "akkusativ") -> str:
    """D:/Mitra/MCN/config.php -> 'config.php im Ordner MCN'.

    Ein voller Pfad vorgelesen ist unzumutbar ("D Doppelpunkt Backslash
    Mitra Backslash..."). Datei und umgebender Ordner reichen zum
    Wiedererkennen; steht die Datei woanders als erwartet, faellt genau
    das auf.
    """
    try:
        p = Path(str(pfad))
    except (OSError, ValueError):
        return str(pfad)
    if p.name and p.parent.name:
        return f"{p.name} im Ordner {p.parent.name}"
    if p.name and p.drive:
        # Direkt auf dem Laufwerk: "Privat" allein sagt zu wenig, es
        # klaenge nach einem beliebigen Ordner irgendwo. Vierter Fall,
        # damit die Rueckfrage grammatisch aufgeht: eingesetzt wird der
        # Text in "Soll ich ... lesen?", also Akkusativ.
        artikel = "dem" if fall == "dativ" else "den"
        return f"{artikel} Ordner {p.name} auf Laufwerk {p.drive.rstrip(':')}"
    return p.name or str(pfad)


# Aus einem Befehl wird eine Absicht. Vorgelesen will niemand
# "Get-PSDrive -Name D | Select-Object Name,Used,Free,Root" hoeren --
# das beantwortet man nicht, das erduldet man.
_ABSICHTEN = (
    (r"^(Get-ChildItem|gci|dir|ls|tree)\b", "nachsehen, was in {} liegt",
     "nachsehen, was dort liegt"),
    (r"^(Get-Content|type|cat)\b", "{} lesen", "eine Datei lesen"),
    (r"^(Remove-Item|del|rm|rmdir)\b", "{} löschen", "etwas löschen"),
    (r"^(New-Item|mkdir|md)\b", "{} anlegen", "etwas anlegen"),
    (r"^(Copy-Item|copy|cp)\b", "{} kopieren", "etwas kopieren"),
    (r"^(Move-Item|move|mv|ren|Rename-Item)\b", "{} verschieben",
     "etwas verschieben"),
    (r"^(Set-Content|Out-File|Add-Content)\b", "in {} schreiben",
     "in eine Datei schreiben"),
    (r"^Get-(PSDrive|Volume|Disk)\b", "", "die Laufwerke abfragen"),
    (r"^Get-CimInstance\b", "", "Systeminformationen abfragen"),
    (r"^Get-Process\b", "", "die laufenden Programme abfragen"),
    (r"^(Start-Process|start)\b", "", "ein Programm starten"),
    (r"^Stop-Process\b", "", "ein Programm beenden"),
    (r"^git\b", "", "einen Git-Befehl ausführen"),
    (r"^(npm|pnpm|yarn)\s+(install|i|add)\b", "", "Pakete installieren"),
    (r"^pip\s+install\b", "", "Pakete installieren"),
    (r"^(npm|pnpm|yarn)\b", "", "einen npm-Befehl ausführen"),
    (r"^(python|py)\b", "", "ein Python-Skript ausführen"),
)


def absicht(befehl: str) -> str:
    """Was der Befehl vorhat, in wenigen Worten -- zum Vorlesen."""
    b = " ".join(str(befehl or "").split())
    erster = b.split("|")[0].strip()
    pfade = re.findall(r"[a-zA-Z]:[\\/][^\s\"';|]*", b)
    # "was in X liegt" verlangt Dativ, "X lesen" Akkusativ.
    ziel_dativ = sprechbar(pfade[0], "dativ") if pfade else ""
    ziel = sprechbar(pfade[0]) if pfade else ""

    for muster, mit_ziel, ohne_ziel in _ABSICHTEN:
        if re.match(muster, erster, re.IGNORECASE):
            if ziel and mit_ziel:
                dativ = " in {}" in mit_ziel or mit_ziel.startswith("in {}")
                return mit_ziel.format(ziel_dativ if dativ else ziel)
            return ohne_ziel
    if ziel:
        return f"einen Befehl auf {ziel} ausführen"
    return "einen Befehl auf deinem Rechner ausführen"


def kurz_befehl(befehl: str, laenge: int = 90) -> str:
    b = " ".join(str(befehl or "").split())
    return b if len(b) <= laenge else b[: laenge - 1] + "…"
