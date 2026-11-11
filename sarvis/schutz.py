"""Wie riskant ist ein Zugriff -- und wie sagt man das in einem Satz?

Der Grundsatz: nicht aussperren, sondern nachfragen. Ein Assistent, der
nichts anfassen darf, nuetzt nichts. Aber die Rueckfrage muss tragen, was
sie beim Tippen nicht muss -- naemlich alles, was du zum Entscheiden
brauchst, in einem hoerbaren Satz.

Drei Stufen:

  frei     Lesen auf D: -- der Platte, auf der ohnehin nur Eigenes liegt.
  fragen   Alles Schreibende, alles auf C:, alles Heikle. Der Regelfall.
  nie      Nur noch Sarvis' eigene Regeldateien. Begruendung unten.

"Nie" ist bewusst fast leer. Ein Assistent, der etwas grundsaetzlich
nicht darf, ist an der Stelle kein Assistent mehr -- er soll fragen
duerfen. Was uebrig bleibt, sind zwei Sorten Ausnahme: Regeln, die sich
nicht selbst aendern duerfen, und Befehle, die ein verhoertes "ja" nicht
tragen wuerde.
"""
import os
import re
import sys
import shlex
from pathlib import Path

from . import config

# Dateien, deren Inhalt Zugaenge oeffnet. Loesen eine deutlichere
# Rueckfrage aus -- "das ist eine Datei mit Zugangsdaten".
HEIKEL = (
    r"\.env$", r"\.pem$", r"\.key$", r"\.pfx$", r"\.p12$", r"\.ppk$",
    r"\.session$", r"id_rsa", r"\.kdbx$", r"\.ovpn$",
    r"passw", r"kennwor", r"secret", r"credential", r"token",
    # Erst noetig, seit D: als Ganzes frei zu lesen ist: Vorher fiel
    # "D:\\Privat\\API-Key's.md" schon deshalb auf "fragen", weil
    # D:\\Privat nicht in der Freiliste stand. Jetzt haengt es an dieser
    # Zeile -- gemessen, die Datei ging vorher still durch.
    r"api.{0,2}key", r"zugang", r"zugaeng", r"zugäng", r"login",
    r"geheim", r"\.pw$", r"\.kdb$",
    r"\.aws[/\\]", r"\.ssh[/\\]", r"\.gnupg[/\\]",
)

# Die einzige harte Sperre -- und sie betrifft nur noch Sarvis' eigene
# Regeln. Alles andere darf er, er fragt eben vorher. Windows und
# Program Files standen hier frueher auch; die sind jetzt "fragen".
#
# Warum ausgerechnet diese Dateien nicht:
#
# Ein Assistent fragt seinen Chef, wenn er unsicher ist. Aber er fragt
# ihn nicht "darf ich die Regel aendern, dass ich dich fragen muss?" --
# ein Ja darauf waere keine Erlaubnis fuer eine Handlung, sondern die
# Abschaffung des Fragens. Eine Vollmacht, die sich selbst aendern darf,
# ist keine.
#
# Es sind alle sieben, nicht nur die naheliegenden zwei:
#   config.py     die Werkzeugstufen und die Befehlsmuster
#   orte.py       die Freilisten -- WO er ohne Rueckfrage hinlangen darf
#   schutz.py     diese Datei
#   hirn.py       darf_ich() -- die Pruefung selbst
#   rueckfrage.py deuten() -- wer das aendert, macht aus jedem Nein ein Ja
#   freigabe.py   erlaubt() -- was ohne Rueckfrage durchlaeuft
#   main.py       nachfragen() -- die Frage, die ueberhaupt gestellt wird
#
# Sarvis' uebriger Code faellt ohnehin auf "fragen": D:\Privat steht
# nicht in FREI_SCHREIBEN.
NIE_SCHREIBEN = (
    r"[/\\]sarvis[/\\]"
    r"(config|orte|schutz|hirn|rueckfrage|freigabe|main)\.py$",
)

# Das Muster haengt am ORDNERNAMEN "sarvis", nicht am wirklichen Ort.
# Auf Windows war das gleichgueltig -- das Paket lag immer in
# D:\Privat\Sarvis\sarvis. Auf dem Server ist es eine Bedingung an das
# Bereitstellungsverzeichnis: Gemessen faellt
# /opt/sarvis-assistent/.env auf "fragen" zurueck statt auf "nie", weil
# der Ordner anders heisst.
#
# Deshalb kommen zu den Namensmustern die WIRKLICHEN Orte dazu. Beides,
# nicht nur das eine: Die Namensmuster fangen auch eine Kopie an einem
# fremden Ort ab, die Ortspruefung auch einen umbenannten Ordner.
NIE_LESEN = (
    r"[/\\]sarvis\.session$",
    r"[/\\][Ss]arvis[/\\]\.env$",
)

# Dazu die WIRKLICHEN Orte, als Muster gebaut statt getippt. Sie gehen
# in dieselbe Liste, damit alle sechs Pruefstellen sie mitnehmen -- eine
# zweite Liste haette an jeder davon einzeln angebunden werden muessen,
# und eine davon haette man vergessen.
#
# sarvis.session ist Telegram, google_token.json der Google-Zugang:
# Zugaenge zu Konten, nicht bloss Einstellungen. Wer sie lesen kann,
# kann in Saschas Namen schreiben.
NIE_LESEN += tuple(
    re.escape(str(pfad).replace("\\", "/")) + r"$"
    for pfad in (
        config.DATEN / "sarvis.session",
        config.DATEN / "google_token.json",
        config.DATEN / "google_zugang.json",
        config.WURZEL / ".env",
        config.DATEN / ".env",
    )
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

    # --- Linux ------------------------------------------------------
    # Die Liste darueber ist vollstaendig Windows. Auf dem Server sperrte
    # sie damit nichts: gemessen war 'systemctl stop caddy' nur "fragen",
    # also mit einem gesprochenen "ja" erreichbar -- und ein "ja" faellt
    # im Gespraech leicht.
    #
    # Aufgenommen wird nur, was sich nicht zurueckholen laesst oder den
    # Server als Ganzes trifft. Alles Uebrige bleibt bei "fragen": der
    # Grundsatz ist nicht aussperren, sondern nachfragen.
    r"\bmkfs(\.\w+)?\b",                    # Dateisystem neu anlegen
    r"\bdd\b[^|]*\bof=/dev/",                # roh auf ein Geraet schreiben
    r">\s*/dev/(sd|nvme|vd|hd)",              # dasselbe per Umleitung
    r"\b(chmod|chown)\b[^|]*\s-R\b[^|]*\s/\s*$",   # Rechte ab Wurzel
    r"\bsystemctl\b[^|]*\b(stop|disable|mask)\b",   # Dienste abschalten
    # Kein Schraegstrich und kein Wortzeichen davor: "passwd" ist ein
    # Befehl, "/etc/passwd" ist eine Datei. Gemessen fiel
    # 'cat /etc/passwd' sonst auf "nie" -- und "nie" ist die Stufe, die
    # sich nicht mit einem Ja aufheben laesst. Eine Sperre, die das
    # Falsche trifft, verliert genau dort ihre Glaubwuerdigkeit.
    r"(?<![/\w.])(userdel|usermod|passwd)\b",
    r"\biptables\b[^|]*\s-F\b", r"\bufw\s+disable\b",   # Firewall
    r"\bdocker\s+system\s+prune\b",         # raeumt fremde Container weg
    r"\bgit\s+push\b[^|]*--force",           # fremde Historie ueberschreiben
    r":\(\)\s*\{.*\|.*&.*\}\s*;?\s*:",       # Fork-Bombe
    r"\bshred\b", r"\bwipefs\b",
)


def _passt(pfad: str, muster) -> bool:
    """Trifft ein Muster den Pfad -- wie er dasteht ODER wohin er fuehrt?

    Nur die Schreibweise zu pruefen reichte auf Windows. Auf Linux ist
    ein Symlink eine Zeile, und die Sperrmuster fuer die wirklichen Orte
    sind mit "$" verankert. Gemessen am 11.11.2026 im Container:
        lesen_stufe('/srv/data/sarvis/./google_token.json')   -> fragen
        lesen_stufe('/srv/data//sarvis/google_token.json')    -> fragen
        lesen_stufe('<sandkasten>/harmlos.txt' -> Token)     -> FREI
    Die harte Sperre ("nie") war also mit einem Punkt, einem doppelten
    Schraegstrich oder einem Link auf "fragen" oder gar "frei"
    herunterzuhandeln. Deshalb zusaetzlich das aufgeloeste Ziel.
    """
    roh = str(pfad or "")
    p = roh.replace("\\", "/")
    if any(re.search(m, p, re.IGNORECASE) for m in muster):
        return True
    if not roh:
        return False
    try:
        # Relatives gegen den Ordner, in dem die Shell steht -- nicht
        # gegen den des Prozesses. Fuer absolute Pfade gleichgueltig.
        echt = os.path.realpath(os.path.join(_arbeitsordner, roh))
    except (OSError, ValueError):
        return False
    if echt == p:
        return False
    return any(re.search(m, echt, re.IGNORECASE) for m in muster)


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
    # Vor der Freiliste, sonst zieht D: als Ganzes den Passwortordner mit.
    if _unter(pfad, config.FRAGEN_TROTZ_FREI):
        return "fragen"
    if _unter(pfad, config.FREI_LESEN):
        # Der letzte Halt vor dem stillen Lesen. Nur hier, nicht bei
        # "fragen" -- dort wird ohnehin gefragt, und die Datei zweimal
        # zu oeffnen bringt nichts.
        if unpruefbares_dokument(pfad) or inhalt_heikel(pfad):
            return "fragen"
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
    # Auch blosse Dateinamen verraten dort schon zu viel -- welche
    # Zugaenge es ueberhaupt gibt, ist selbst eine Auskunft.
    if _unter(pfad, config.FRAGEN_TROTZ_FREI):
        return "fragen"
    return "frei"


def durchsuchen_stufe(pfad: str) -> str:
    """Einen ganzen Ordnerbaum nach Inhalten absuchen.

    Strenger als lesen_stufe, und zwar aus einem sachlichen Grund: Beim
    Lesen einer einzelnen Datei kann inhalt_heikel() vorher hineinsehen.
    Bei einem Baum mit zehntausenden Dateien kann es das nicht -- die
    Pruefung wuerde laenger dauern als die Suche. Ein Grep ueber
    D:\\Privat brachte frueher Zeilen aus jeder Datei zurueck, die
    zufaellig passten, Zugangsdaten eingeschlossen.

    Deshalb hier keine Inhaltspruefung, sondern eine engere Freiliste.
    """
    if not pfad:
        return "frei"                      # Arbeitsverzeichnis
    if _passt(pfad, NIE_LESEN):
        return "nie"
    if _unter(pfad, config.FRAGEN_TROTZ_FREI):
        return "fragen"
    # Eine einzelne Datei ist auch beim Suchen ein gezielter Griff --
    # dort gelten dieselben Regeln wie beim Lesen, samt Blick hinein.
    try:
        if Path(pfad).is_file():
            return lesen_stufe(pfad)
    except (OSError, ValueError):
        pass
    if _unter(pfad, config.FREI_DURCHSUCHEN):
        return "frei"
    return "fragen"


def schreiben_stufe(pfad: str) -> str:
    if _passt(pfad, NIE_SCHREIBEN):
        return "nie"
    if _unter(pfad, config.FREI_SCHREIBEN):
        return "frei"
    return "fragen"


def pfad_aufloesen(was: str) -> Path:
    """"~/x" heisst SASCHAS Benutzerordner, nicht den des Containers.

    Im Container ist HOME /srv/data/sarvis/home -- expanduser() fuehrte
    "~/Screenshot.png" also in Sarvis' eigenes Zuhause, wo es die Datei
    nicht gibt (gemessen 10.11.2026).
    """
    was = str(was or "").strip()
    if was == "~" or was.startswith("~/"):
        was = str(config.PROJEKT_ORTE["privat"]) + was[1:]
    return Path(was).expanduser().resolve()


def versenden_stufe(pfad: str) -> str:
    """Eine Datei (oder einen Ordner als ZIP) aufs Handy schicken.

    Milder als lesen_stufe, und zwar aus der Sache: Beim Versenden sieht
    das MODELL den Inhalt gar nicht -- die Bytes gehen am Gespraech
    vorbei direkt an Saschas Geraet. Ein PDF muss deshalb nicht erst
    "pruefbar" sein, bevor es still raus darf.

    Streng bleibt, was Zugangsdaten enthaelt: Die gehen ueber eine
    Adresse ohne Anmeldung (nur 192 Bit Zufall, siehe netz/blaetter.py),
    und ein Passwort soll nicht nebenbei in einem Download-Ordner landen.
    """
    if not pfad:
        return "fragen"
    if _passt(pfad, NIE_LESEN):
        return "nie"
    if heikel(pfad) or _unter(pfad, config.FRAGEN_TROTZ_FREI):
        return "fragen"
    if _unter(pfad, list(config.FREI_LESEN) + list(config.FREI_DURCHSUCHEN)):
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
    # Tests standen frueher hier, mit der Begruendung "schauen tun sie ja
    # auch". Tun sie nicht: pytest sammelt Testdateien ein und FUEHRT sie
    # aus, in dem Ordner, in dem es gerade steht. Gemessen: mit dem
    # Arbeitsordner C:\Users\sasch lief "pytest" ohne eine Rueckfrage
    # durch. Sie sind nicht verloren, sondern umgezogen -- in den eigenen
    # Projektordnern deckt ENTWICKLUNG_BEFEHLE sie ab, ueberall sonst
    # wird gefragt. Innerhalb der Projekte kostet das keine einzige
    # Rueckfrage mehr als vorher.
    # "where" braucht ein Leerzeichen dahinter. Sonst trifft das Muster
    # auch "Where-Object" -- der Bindestrich ist eine Wortgrenze, \b
    # allein reicht hier nicht. Und in einem Where-Object-Skriptblock
    # kann alles Moegliche stehen.
    r"^where\s", r"^which\s", r"^echo\b",
)

# Befehle, die INHALTE ueber einen Baum hinweg zusammensuchen. Sie
# stehen teils in NUR_SCHAUEN -- schauen tun sie ja auch --, aber fuer
# sie gilt durchsuchen_stufe statt lesen_stufe. Ohne diese Zeile lief
# "Get-ChildItem D:\\Privat -Recurse | Select-String passwort" still
# durch: Der geprüfte Pfad ist ein Ordner, und ein Ordner hat keinen
# Inhalt, in den man hineinsehen koennte.
SUCHBEFEHLE = (
    r"^(Select-String|sls|findstr|grep|rg|ack|ag)\b",
)


# Ein Schema-Praefix wie "http://" oder "file://". Wird vor der
# Pfadsuche ausgeschnitten: Sonst liest der POSIX-Zweig aus
# "curl http://x.example/y" den Pfad "//x.example/y", und der
# Laufwerks-Zweig machte daraus gemessen "p://x.example/y" -- beides
# keine Pfade, aber beide loesen Rueckfragen aus, die niemand versteht.
_SCHEMA = re.compile(r"\b[a-zA-Z][a-zA-Z0-9+.\-]*://\S*")

# Ein absoluter POSIX-Pfad. Das (?<![\w:/.]) haelt vier Faelle heraus:
# Wortzeichen davor (Division "a/b", Optionen "-n/x"), einen
# Doppelpunkt (Laufwerksform, die der Zweig darueber schon hat), einen
# zweiten Schraegstrich -- und einen Punkt, damit aus "../../.env" nicht
# der Pfad "/../.env" wird. Der faellt zwar streng aus (er loest sich zu
# /.env auf und liegt nirgends), aber zufaellig streng ist nicht streng.
#
# Die Tilde steht seit dem 11.11.2026 mit in der Klammer: "~/.ssh" wurde
# sonst als "/.ssh" gelesen -- ein Ort, den es nicht gibt. Die Tilde
# deutet jetzt _HEIM_PFAD unten, und zwar so, wie die Shell es tut.
_POSIX_PFAD = re.compile(r"(?<![\w:/.~])(/[^\s\"';|]*)")

# Der Benutzerordner in seinen drei Schreibweisen: ~, $HOME, ${HOME} --
# und ~name fuer den eines anderen. Vorher fand pfade_im_befehl darin
# nichts, und "nichts gefunden" heisst an allen vier Pruefstellen
# "nichts zu beanstanden". Gemessen am 11.11.2026 im Container:
#     Arbeiter: 'cat $HOME/.claude/.credentials.json'      -> erlaubt
#     Freigabe "Befehle in mcn" deckte denselben Befehl     -> still
#     entwicklung_frei('cd ~ && pytest')                    -> True
_HEIM_PFAD = re.compile(
    r"(?<![\w:/.~$])(~[A-Za-z_][\w.-]*|~|\$HOME\b|\$\{HOME\})"
    r"(/[^\s\"';|]*)?(?=$|[\s\"';|&)<>])")

# Das Arbeitsverzeichnis als Variable -- dasselbe wie ".".
_PWD_PFAD = re.compile(
    r"(?<![\w:/.$])(\$PWD\b|\$\{PWD\}|\$\(pwd\)|`pwd`)(/[^\s\"';|]*)?")

# Ein nacktes "cd" (oder "cd ~") wechselt in den Benutzerordner. Ohne
# Argument steht darin kein Pfad, also fand die Pruefung nichts -- der
# Arbeiter kam mit 'cd && cat .claude.json' aus seinem Projekt heraus.
_CD_NACKT = re.compile(r"(?:^|[;&|(]\s*)cd\s*(?=$|[;&|)])")

# ".." als ganzes Wort. Der relative Zweig unten verlangt einen
# Schraegstrich dahinter -- 'cd .. && cd .. && cat srv/data/...' ging
# damit am Wachhund des Arbeiters vorbei, Schritt fuer Schritt nach oben.
_HOCH = re.compile(r"(?<![\w:/.])\.\.(?=$|[\s;|&)\"'])")

# Ein RELATIVER Pfad, aber nur mit "./" oder "../" davor.
#
# Ohne diesen Zweig blieb der Ausbruch nach oben offen: Steht in einem
# Befehl gar kein absoluter Pfad, faellt freigabe._befehl_ganz_unter auf
# den Arbeitsordner zurueck und haelt ihn fuer erlaubt. Damit deckte eine
# Freigabe fuer "Befehle in mcn" auch
#   cd /srv/storage/projects/mcn && cat ../../../home/server3070/.ssh/id_ed25519
#
# Bewusst NUR mit Punkt-Praefix. Ein blosses "src/app.py" mitzunehmen
# hiesse, jedes Unterkommando nach Pfaden abzusuchen, und liefe bei
# "npm run a/b" oder "git log --format=x/y" ins Leere -- False Positives
# an einer Stelle, an der jeder davon eine gesprochene Rueckfrage ist.
# "./" und "../" dagegen sind eindeutig, und genau sie tragen den
# Ausbruch.
_REL_PFAD = re.compile(r"(?<![\w:/.])(\.\.?/[^\s\"';|]*)")


def pfade_im_befehl(befehl: str, bezug: str | None = None) -> list[str]:
    """ALLE Pfade eines Befehls -- POSIX wie Windows.

    Diese eine Funktion traegt vier Sicherungen: die NIE_LESEN/
    NIE_SCHREIBEN-Pruefung ueber Befehle (befehl_stufe), die vierte
    Bedingung von entwicklung_frei ("jeder genannte Pfad liegt auch im
    Entwicklungsbereich"), _befehl_ganz_unter in freigabe.py und den
    Bash-Zweig des Arbeiter-Wachhunds. Findet sie nichts, greift keine
    davon -- und zwar still.

    Genau das war auf Linux der Fall. Gemessen vor diesem Umbau, mit
    den heutigen Listen und Arbeitsordner /srv/storage/projects/mcn:

        pfade_im_befehl('cat /etc/shadow')  -> []
        befehl_stufe('ls /')                -> 'frei'
        entwicklung_frei('cd /etc')         -> True
        freigabe fuer "Befehle in mcn" deckte 'cat /etc/shadow'

    Der Regex suchte ausschliesslich nach Laufwerksbuchstaben. Auf
    Windows war das vollstaendig, auf Linux traf es nichts.

    Die Git-Bash-Umdeutung ("/d/x" ist Laufwerk D) laeuft nur noch auf
    Windows. Auf Linux ist /d/x ein gewoehnlicher Ordner, und sie haette
    aus ihm faelschlich "D:/x" gemacht -- einen Pfad, der hier nirgends
    liegt und deshalb jede Ortspruefung bestanden haette.

    Rueckgabe in der Form, die auf dieser Plattform gilt: absolute
    POSIX-Pfade so, wie sie dastehen; Windows-Pfade in Laufwerksform.

    Relative Pfade zaehlen nur mit "./" oder "../" davor (und ".." als
    ganzes Wort); ein blosses "src/app.py" bleibt bewusst aussen vor.
    Dazu kommen ~, $HOME, $PWD und das nackte "cd" -- siehe die Muster
    darueber. Was sich dagegen erst zur Laufzeit ergibt ($(printf ...),
    eine selbst gesetzte Variable), sieht kein Regex; dafuer gibt es
    die Sperrlisten und die Rueckfrage.
    """
    b = _SCHEMA.sub(" ", str(befehl or ""))
    treffer = re.findall(r"[a-zA-Z]:[\\/][^\s\"';|]*", b)
    if sys.platform == "win32":
        treffer += [
            f"{lw.upper()}:/{rest}"
            for lw, rest in re.findall(r"(?<![\w/])/([a-zA-Z])/([^\s\"';|]*)", b)
        ]
    else:
        treffer += _POSIX_PFAD.findall(b)
    # Relative Pfade gegen den Ordner aufloesen, in dem der Befehl
    # wirklich landet. Nicht resolve() -- das macht _unter() selbst, und
    # es soll hier keine Datei angefasst werden, nur gerechnet.
    #
    # bezug ist ausdruecklich ein Parameter und nicht immer der
    # Arbeitsordner: Der Arbeiter in auftrag.py laeuft in SEINEM
    # Projektordner, nicht in Sarvis'. Beide denselben Bezug nehmen zu
    # lassen ginge meistens gut und einmal falsch aus -- naemlich dann,
    # wenn Sarvis' Ordner zufaellig im Projekt liegt.
    #
    # Innerhalb EINES Befehls wird jedes "cd" mitgegangen: In
    # 'cd web && npm run build && cd ..' meint das ".." den Projektordner
    # und nicht dessen Elternordner. Ohne das Mitgehen lehnte der
    # Arbeiter genau diesen Alltagsbefehl ab, sobald ".." ueberhaupt
    # als Pfad zaehlte -- und umgekehrt lief 'cd .. && cd .. && cat x'
    # nach oben hinaus, solange es nicht zaehlte.
    ort = str(bezug or _arbeitsordner)
    # Benutzerordner und Arbeitsverzeichnis als Schreibweise. Gerechnet
    # wird mit dem HOME dieses Prozesses: Die Shell, die den Befehl
    # ausfuehrt, erbt es -- im Container ist das /srv/data/sarvis/home,
    # nicht Saschas Ordner, und genau dorthin fuehrt "~" dann auch.
    for wort, rest in _HEIM_PFAD.findall(b):
        treffer.append(_heim(wort) + rest)
    if _CD_NACKT.search(b):
        treffer.append(_heim("~"))
    for teil in _zerlegen(b):
        treffer += [os.path.join(ort, r) for r in _REL_PFAD.findall(teil)]
        treffer += [os.path.join(ort, "..") for _ in _HOCH.findall(teil)]
        treffer += [ort + rest for _, rest in _PWD_PFAD.findall(teil)]
        ort = _nach_cd(teil, ort)
    return treffer


def _nach_cd(teil: str, ort: str) -> str:
    """Wo die Shell nach diesem Schritt steht -- logisch, wie "cd" rechnet.

    Ohne Dateizugriff: Hier wird nur mitgezaehlt, geprueft wird spaeter
    an jedem einzelnen Pfad. "cd -" kennt nur die Shell; dann gilt "/",
    also ausserhalb jeder Freiliste.
    """
    if re.match(r"^(cd|chdir)$", teil, re.IGNORECASE):
        return _heim("~")
    treffer = _CD.match(teil)
    if not treffer:
        return ort
    ziel = treffer.group(1).strip().strip('"\'')
    if ziel == "-":
        return "/"
    heim = _HEIM_PFAD.match(ziel)
    if heim:
        ziel = _heim(heim.group(1)) + (heim.group(2) or "")
    return os.path.normpath(os.path.join(ort, _laufwerksform(ziel)))


def _heim(wort: str) -> str:
    """'~', '$HOME', '${HOME}' oder '~name' -- als Ordner.

    Ein ~name, den es nicht gibt, laesst die Shell stehen, wie er ist;
    hier wird daraus "/" -- ausserhalb jeder Freiliste. Lieber eine
    Rueckfrage zu viel als ein Ort, den niemand pruefen kann.
    """
    if wort in ("~", "$HOME", "${HOME}"):
        return str(Path.home())
    voll = os.path.expanduser(wort)
    return voll if voll != wort else "/"


def _heikler_ort_erwaehnt(text: str) -> bool:
    """Kommt ein Ordner aus FRAGEN_TROTZ_FREI im Befehlstext vor?

    Noetig, weil der Pfad-Regex weiter unten am Leerzeichen abbricht:
    "dir D:\\Strato Server" lieferte nur "D:\\Strato", und das liegt
    nicht im geschuetzten Ordner -- der Befehl waere frei durchgelaufen.
    Ein Teilstringvergleich kennt das Problem nicht und trifft auch
    "dir \"D:\\Strato Server\"".

    Beide Schreibweisen, seit gemessen wurde, dass 'ls /d/Strato Server'
    hier vorbeilief: Verglichen wurde nur "d:/strato server".
    """
    # Der geschuetzte Ordner hat ein Leerzeichen im Namen, und in der
    # Bash wird das als "\\ " geschrieben. Erst den Schutzstrich weg,
    # dann die Trenner angleichen -- sonst wird aus "Strato\\ Server"
    # ein "Strato/ Server" und der Vergleich geht daran vorbei.
    t = str(text or "").replace(chr(92) + " ", " ").replace(chr(92), "/").lower()
    for wurzel in config.FRAGEN_TROTZ_FREI:
        w = str(wurzel).replace(chr(92), "/").lower()
        if w in t:
            return True
        laufwerk, trenner, rest = w.partition(":/")
        if trenner and f"/{laufwerk}/{rest}" in t:
            return True
    return False


def heikler_ort_beruehrt(pfad: str, muster: str = "") -> bool:
    """Beruehrt ein Auflisten/Durchsuchen einen Ort aus FRAGEN_TROTZ_FREI?

    Zwei Wege dorthin, und beide gingen an auflisten_stufe vorbei, weil
    die nur den Pfad ansieht: Der Ort steht im MUSTER selbst (Glob traegt
    sein Ziel in "pattern", "path" ist optional -- gemessen: ohne "path"
    war der Pfad leer und damit "frei"), oder das Muster laeuft rekursiv
    unter einer Wurzel, die ihn enthaelt ("D:/" mit "**/*").
    """
    if _heikler_ort_erwaehnt(f"{pfad} {muster}"):
        return True
    if "**" not in str(muster or "") or not pfad:
        return False
    try:
        p = Path(pfad).resolve()
    except (OSError, ValueError):
        return False
    for wurzel in config.FRAGEN_TROTZ_FREI:
        try:
            w = Path(wurzel).resolve()
        except (OSError, ValueError):
            continue
        if p == w or p in w.parents:
            return True
    return False


# Befehle, die etwas veraendern. Nur bei ihnen sperrt NIE_SCHREIBEN --
# sonst waere schon das blosse Anzeigen von config.py "nie".
_VERAENDERND = re.compile(
    r"^(Set-Content|Add-Content|Out-File|Clear-Content|Remove-Item"
    r"|Move-Item|Rename-Item|Copy-Item|New-Item|del|rm|mv|cp|ren"
    r"|sed\s+-i|tee)\b",
    re.IGNORECASE,
)


def _umleitungsziele(befehl: str) -> list[str]:
    """Wohin ein Befehl seine Ausgabe umleitet.

    "echo x > datei" nennt kein veraenderndes Programm und lief deshalb
    an der Pruefung vorbei -- gemessen fiel 'echo x > ...\\sarvis\\hirn.py'
    sogar auf "frei", weil echo in NUR_SCHAUEN steht.
    """
    roh = re.findall(r">>?\s*(\"[^\"]+\"|'[^']+'|[^\s\"'|;&]+)", str(befehl or ""))
    return [z.strip("\"'") for z in roh]


def _zerlegen(befehl: str) -> list[str]:
    """Eine Kette in ihre Schritte -- an &&, ||, ; und der Pipe.

    Dieselbe Zerlegung wie bisher in befehl_stufe, nur an einer Stelle:
    "git status && rm -rf x" ist nicht harmlos, nur weil es harmlos
    anfaengt, und jede Pruefung muss dieselben Schritte sehen.
    """
    return [t.strip() for t in re.split(r"&&|\|\||;|\|", str(befehl or ""))
            if t.strip()]


# --- Wo Sarvis gerade arbeitet -------------------------------------------
# Ein pfadloser Befehl -- "docker compose up" -- laeuft irgendwo, und ohne
# dieses Irgendwo ist nicht pruefbar, ob er laufen darf. Die Shell behaelt
# ihren Ordner zwischen den Aufrufen; hier wird derselbe Stand mitgefuehrt.
#
# Startwert ist Sarvis' eigener Ordner: Von dort wird er gestartet
# (starten.bat), und genau dort landet ein Befehl, vor dem kein "cd"
# stand. Das ist keine Annahme, sondern der Ort, an dem der Prozess laeuft.
_arbeitsordner = str(config.WURZEL)

_CD = re.compile(r"^(?:cd|chdir|Set-Location|sl)\s+(?:-Path\s+)?(.+)$",
                 re.IGNORECASE)


def _laufwerksform(pfad: str) -> str:
    """Git-Bash-Schreibweise in Laufwerksform -- "/d/x" wird "D:/x".

    Nur auf Windows. Auf Linux ist "/a/x" ein gewoehnlicher Pfad, und
    die Umdeutung machte daraus "A:/x" -- fuer PosixPath ein RELATIVER
    Pfad, der am Arbeitsordner angehaengt wurde. Gemessen am 11.11.2026:
    _im_entwicklungsbereich('/a/../../etc') -> True, weil daraus
    '<projekt>/A:/../../etc' wurde, also ein Ort im Projektbaum.
    Dieselbe Weiche wie in pfade_im_befehl.
    """
    if sys.platform != "win32":
        return pfad
    treffer = re.match(r"^/([a-zA-Z])/(.*)$", str(pfad or ""))
    return f"{treffer.group(1).upper()}:/{treffer.group(2)}" if treffer else pfad


def arbeitsordner() -> str:
    """Der Ordner, in dem ein pfadloser Befehl landet."""
    return _arbeitsordner


def arbeitsordner_merken(befehl: str) -> str:
    """Den Ordnerwechsel eines Befehls nachvollziehen.

    Wird erst gerufen, wenn der Befehl erlaubt WURDE -- nie vorher. Sonst
    koennte ein Befehl den Ort setzen, an dem er selbst geprueft wird:
    'cd D:/Mitra/MCN; <irgendwas>' waere dann ein Freifahrtschein, den
    der Befehl sich selbst ausstellt.

    Relative Ziele ("cd frontend", "cd ..") werden am bisherigen Stand
    aufgeloest, genau wie die Shell es tut.
    """
    global _arbeitsordner
    for teil in _zerlegen(befehl):
        treffer = _CD.match(teil)
        if treffer:
            ziel = _laufwerksform(treffer.group(1).strip().strip('"\''))
        elif re.match(r"^(cd|chdir)$", teil, re.IGNORECASE):
            ziel = "~"            # nacktes cd: wie die Shell, nach Hause
        else:
            continue
        # "~" und "$HOME" meinen den Benutzerordner der SHELL. Vorher
        # wurde "~" als Ordnername im Projekt gesucht, nicht gefunden und
        # der Wechsel ignoriert -- die Shell stand danach woanders, als
        # hier mitgeschrieben war.
        heim = _HEIM_PFAD.match(ziel)
        if heim:
            ziel = _heim(heim.group(1)) + (heim.group(2) or "")
        if not ziel:
            continue
        try:
            neu = Path(_arbeitsordner, ziel).resolve()
        except (OSError, ValueError):
            continue
        # Nur was es wirklich gibt. Ein "cd" ins Leere aendert auch in
        # der Shell nichts -- und ein erfundener Ordner darf hier keinen
        # Ort setzen, an dem spaeter gemessen wird.
        if neu.is_dir():
            _arbeitsordner = str(neu)
    return _arbeitsordner


def arbeitsordner_zeile() -> str:
    """Wo ein Befehl ohne "cd" landet -- damit Sarvis es nicht raten muss.

    Die Shell behaelt ihren Ordner zwischen den Aufrufen, das Modell
    nicht. Ohne diese Zeile bleiben Sarvis zwei schlechte Wege: jedes Mal
    vorsichtshalber ein "cd" davorschreiben, oder im falschen Projekt
    starten. Arbeitsgedaechtnis statt Erinnerung, wie bei den Timern.
    """
    ordner = arbeitsordner()
    if _im_entwicklungsbereich(ordner):
        return (f"[Shell-Ordner: {ordner} — eigenes Projekt, Starten und "
                "Testen laufen dort ohne Rückfrage]")
    return f"[Shell-Ordner: {ordner}]"


def _im_entwicklungsbereich(pfad: str) -> bool:
    """Liegt ein Pfad unter einem Entwicklungsort -- und nicht im Heiklen?

    Relative Angaben werden am Arbeitsordner aufgeloest, nicht am Ordner
    des Prozesses. Der Unterschied faellt bei Umleitungen an: "npm run
    start > out.txt" schreibt dorthin, wo die SHELL steht, und genau dort
    muss die Pruefung hinsehen.
    """
    if not pfad:
        return False
    try:
        p = str(Path(_arbeitsordner, _laufwerksform(pfad)))
    except (OSError, ValueError):
        return False
    if _unter(p, config.FRAGEN_TROTZ_FREI):
        return False
    return _unter(p, config.ENTWICKLUNG_ORTE)


def entwicklung_frei(befehl: str) -> bool:
    """Ist das Arbeit am eigenen Projekt -- und darf deshalb durchlaufen?

    Vier Bedingungen, und alle vier muessen halten. Die Begruendung
    steht bei den Listen in config.py; hier nur, was geprueft wird:

      1. Der Arbeitsordner liegt unter einem ENTWICKLUNG_ORT.
      2. Jeder Schritt der Kette steht in ENTWICKLUNG_BEFEHLE.
      3. Kein Schritt steht in ENTWICKLUNG_FRAGT_TROTZDEM.
      4. Jeder Pfad, den der Befehl NENNT, liegt ebenfalls dort --
         sonst waere 'docker compose -f C:/fremd/x.yml up' frei, bloss
         weil der Arbeitsordner stimmt.
    """
    teile = _zerlegen(befehl)
    if not teile or not _im_entwicklungsbereich(_arbeitsordner):
        return False
    for teil in teile:
        if any(re.search(m, teil, re.IGNORECASE)
               for m in config.ENTWICKLUNG_FRAGT_TROTZDEM):
            return False
        if not any(re.match(m, teil, re.IGNORECASE)
                   for m in config.ENTWICKLUNG_BEFEHLE):
            return False
    for pfad in pfade_im_befehl(befehl) + _umleitungsziele(befehl):
        if not _im_entwicklungsbereich(pfad):
            return False
    return True


def _loescht_wurzel(teil: str, ort: str) -> bool:
    """Loescht dieser Schritt rekursiv einen Wurzelort -- oder etwas darueber?

    NIE_BEFEHL kannte dafuer nur 'rm -rf /' und 'rm -rf ~' als ganze
    Zeile. Gemessen am 11.11.2026 im Container lagen damit nur ein
    gesprochenes "ja" entfernt:
        rm -rf /*              rm -rf ~/*            rm -rf $HOME
        rm -r -f /home/server3070      rm -fr /srv/data/sarvis
        rm -rf /srv/storage/projects/*
    Beschreibbar gemountet sind genau Saschas Benutzerordner, alle
    Projekte und Sarvis' Daten samt Gedaechtnis -- also alles, was zaehlt.
    Ein einzelnes Projekt zu loeschen bleibt "fragen"; gesperrt ist nur
    der Wurzelort selbst, sein Inhalt als Ganzes ("/*") und alles
    darueber.
    """
    if not re.match(r"^rm\b", teil):
        return False
    try:
        woerter = shlex.split(teil)
    except ValueError:
        woerter = teil.split()
    flaggen = [w for w in woerter[1:] if w.startswith("-")]
    if not any(w == "--recursive" or (not w.startswith("--") and "r" in w.lower())
               for w in flaggen):
        return False
    geschuetzt = {os.path.realpath(str(p)) for p in (
        config.PROJEKT_ORTE["privat"], config.PROJEKT_ORTE["arbeit"],
        config.DATEN, config.WURZEL, Path.home())}
    for w in woerter[1:]:
        if w.startswith("-") or not w:
            continue
        heim = _HEIM_PFAD.match(w)
        if heim:
            w = _heim(heim.group(1)) + (heim.group(2) or "")
        # "/x/*" und "/x/" meinen beim Loeschen dasselbe wie "/x".
        w = re.sub(r"(/\.?\*|/)+$", "", w) if w not in ("/", "/*") else "/"
        if w in ("*", ".*", ""):
            w = "."
        ziel = os.path.realpath(os.path.join(ort, w))
        for g in geschuetzt:
            if g == ziel or g.startswith(ziel.rstrip("/") + "/"):
                return True
    return False


def befehl_stufe(befehl: str) -> str:
    befehl = (befehl or "").strip()
    if any(re.search(m, befehl, re.IGNORECASE) for m in NIE_BEFEHL):
        return "nie"

    # Verkettungen aufteilen: "git status && rm -rf x" ist nicht harmlos,
    # nur weil es harmlos anfaengt.
    teile = _zerlegen(befehl)

    ort = _arbeitsordner
    for teil in teile:
        if _loescht_wurzel(teil, ort):
            return "nie"
        ort = _nach_cd(teil, ort)

    # Die harte Sperre galt bisher nur fuer die Datei-Werkzeuge, nicht
    # fuer die Shell: schreiben_stufe("...sarvis/schutz.py") war "nie",
    # 'Set-Content ...sarvis/schutz.py' aber nur "fragen" -- ein einziges
    # gesprochenes Ja haette die Regeldatei geaendert, die das Fragen
    # ueberhaupt vorschreibt. Gelesen wird gar nicht (NIE_LESEN),
    # geschrieben nur im veraendernden Schritt.
    for teil in teile:
        veraendernd = bool(_VERAENDERND.match(teil))
        for pfad in pfade_im_befehl(teil):
            if _passt(pfad, NIE_LESEN):
                return "nie"
            if veraendernd and _passt(pfad, NIE_SCHREIBEN):
                return "nie"
    for ziel in _umleitungsziele(befehl):
        if _passt(ziel, NIE_SCHREIBEN) or _passt(ziel, NIE_LESEN):
            return "nie"
    # Noch einmal ueber den GANZEN Befehl: Nur so geht ein "cd" davor in
    # die Rechnung ein -- 'cd /srv/data/sarvis && cat ./google_token.json'
    # nennt den Ort in einem Schritt und die Datei im naechsten.
    for pfad in pfade_im_befehl(befehl):
        if _passt(pfad, NIE_LESEN):
            return "nie"

    if _heikler_ort_erwaehnt(befehl):
        return "fragen"

    # Arbeit am eigenen Projekt laeuft durch. Steht bewusst NACH den
    # harten Sperren und nach dem heiklen Ort: Was nie darf, darf auch
    # im eigenen Projektordner nicht.
    if entwicklung_frei(befehl):
        return "frei"

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
        sucht = any(
            re.match(m, t, re.IGNORECASE) for t in teile for m in SUCHBEFEHLE
        )
        if sucht:
            pruefer = durchsuchen_stufe
        else:
            pruefer = auflisten_stufe if nur_namen else lesen_stufe
        for pfad in pfade_im_befehl(befehl):
            if pruefer(pfad) != "frei":
                return "fragen"
        return "frei"

    return "fragen"


# --- Klicken und Tippen im eingebauten Browser ---------------------------
# Bis heute galt: "Sarvis bringt die Seite, du bedienst sie." Das trug,
# weil Zeigen keine Handlung ist. Ein Klick ist eine -- und der Browser
# ist in den Konten des Nutzers angemeldet.
#
# Freigegeben wurde das ausdruecklich, mit einer Bedingung: Formulare und
# alles Bedenkliche oder Unumkehrbare holen sich eine Bestaetigung. Diese
# Bedingung steht hier in Python und nicht im Systemprompt, aus demselben
# Grund wie bei den Shell-Befehlen: Ein Modell laesst sich umstimmen --
# und zwar ausgerechnet von der Seite, die es gerade liest. Eine Funktion
# nicht.
#
# Drei Pruefungen, und die ersten beiden sind die verlaesslichen:
#
#   1. Ist es ein Absenden?        aus dem DOM (type=submit)
#   2. Steht es in einem Formular? aus dem DOM (closest("form"))
#   3. Sagt die Beschriftung etwas? aus der SEITE -- also das schwaechste
#      Glied, denn wer die Seite schreibt, schreibt auch die Beschriftung
#
# Deshalb nennt die Rueckfrage nicht nur, was draufsteht, sondern was
# erkannt wurde. Ein Loeschen-Knopf, der "Cookies akzeptieren" heisst,
# bleibt ein Formular-Absenden, und genau das wird vorgelesen.

# Woerter in der Beschriftung, bei denen immer gefragt wird. Bewusst als
# Wortanfaenge: "loesch" trifft loeschen, Loeschung, geloescht.
KLICK_HEIKEL = (
    r"kauf", r"bestell", r"bezahl", r"zahlungspflicht", r"ueberweis",
    r"überweis", r"abschick", r"absend", r"senden", r"abschließ",
    r"abschliess", r"loesch", r"lösch", r"entfern", r"verwerf",
    r"kuendig", r"kündig", r"abbestell", r"abmeld", r"ausloggen",
    r"bestaetig", r"bestätig", r"endgueltig", r"endgültig",
    r"unwiderruf", r"zustimm", r"akzeptier", r"einwillig", r"freigeb",
    r"veroeffentlich", r"veröffentlich", r"teilen", r"posten",
    r"abonnier", r"reservier", r"beauftrag", r"registrier",
    r"anmelden", r"speichern", r"uebernehmen", r"übernehmen",
)

# Feldarten, in die Sarvis NIE schreibt. Ein Passwort kennt er nicht, und
# ein Werkzeug, das in ein Passwortfeld schreiben darf, ist ein Werkzeug,
# das man dazu bringen kann, etwas Falsches hineinzuschreiben.
FELD_NIE = ("password", "hidden")


def _beschriftung_heikel(text: str) -> bool:
    t = str(text or "").casefold()
    return any(re.search(m, t, re.IGNORECASE) for m in KLICK_HEIKEL)


def klick_stufe(element: dict) -> str:
    """Darf dieser Klick ohne Rueckfrage laufen?

    Ohne Element -- also wenn gar nicht feststellbar ist, worauf geklickt
    wird -- wird gefragt. Nicht aufgezaehlt heisst auch hier nein.
    """
    if not isinstance(element, dict) or not element:
        return "fragen"
    if element.get("absenden"):
        return "fragen"
    if element.get("im_formular"):
        return "fragen"
    if _beschriftung_heikel(element.get("text")):
        return "fragen"
    return "frei"


def tipp_stufe(element: dict) -> str:
    """Darf hier hineingeschrieben werden?

    Ein Formular auszufuellen ist noch keine Handlung nach draussen -- das
    wird es erst beim Absenden, und das fragt ohnehin. Trotzdem steht hier
    "fragen": So war es ausgemacht, und wer ein langes Formular diktiert,
    sagt einmal "ja, frag die naechste Minute nicht mehr". Genau dafuer
    gibt es die Freigaben auf Zeit.
    """
    if not isinstance(element, dict) or not element:
        return "fragen"
    if str(element.get("feldart") or "").lower() in FELD_NIE:
        return "nie"
    return "fragen"


def klick_grund(element: dict) -> str:
    """Was der Code erkannt hat -- fuer die Rueckfrage.

    Der wichtigste Halbsatz der ganzen Browsersteuerung. Die Beschriftung
    stammt von der Seite und kann luegen; das hier stammt aus dem HTML.
    """
    if not isinstance(element, dict) or not element:
        return "unklar, worauf"
    if element.get("absenden"):
        return "ein Formular wird damit abgeschickt"
    if element.get("im_formular"):
        return "das steht in einem Formular"
    if _beschriftung_heikel(element.get("text")):
        return "die Beschriftung klingt nach etwas Endgültigem"
    return ""


# --- Zugangsdaten am Inhalt erkennen -------------------------------------
#
# Die Namensliste oben ist eine SPERRLISTE, und die kann nur verbieten,
# woran jemand gedacht hat. Solange nur einzelne Ordner frei zu lesen
# waren, trug das nicht viel: Alles Unbekannte fiel ohnehin auf "fragen".
# Seit D: als Ganzes frei ist, haengt der Schutz allein an ihr -- und
# damit an der Frage, ob ein Ordner zufaellig "Passwoerter" heisst und
# nicht "Tresor", "Zugaenge alt" oder "Kram".
#
# Deshalb zusaetzlich der Blick hinein. Er ist billig (die ersten 64 KB),
# er greift nur dort, wo sonst STILL gelesen wuerde, und er sieht nur
# innerhalb dieses Programms nach -- der Inhalt geht nicht ans Modell.
# Genau das ist der Punkt: Die Pruefung liest, damit Sarvis es nicht
# ungefragt tut.

# Dokumente, die Text tragen, sich aber nicht als Text lesen lassen.
# Sie werden NICHT still gelesen -- nicht weil sie verdaechtig waeren,
# sondern weil die Pruefung hier blind ist. Claude Codes Read-Werkzeug
# kann PDFs, die Musterpruefung kann es nicht: Der Text steht dort
# komprimiert im Binaerstrom. Auf E: liegen 11 PDFs und laut Ansage
# "auch gerne mal Passwoerter" -- geraten wird da nicht.
DOKUMENT_UNPRUEFBAR = (".pdf", ".doc", ".xls", ".ppt", ".rtf", ".msg",
                       ".one", ".kdb", ".pages", ".numbers")

# Diese dagegen sind ZIP-Archive mit XML darin -- da kommt man mit
# Bordmitteln hinein, also wird hineingesehen statt gefragt.
DOKUMENT_ZIP = (".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp")

PRUEF_BYTES = 64 * 1024
PRUEF_GROESSE_MAX = 8 * 1024 * 1024   # groessere Dateien sind keine Zugangsdaten

# Eindeutig, ohne dass der Wert danach noch geprueft werden muesste.
INHALT_EINDEUTIG = (
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"-----BEGIN OPENSSH PRIVATE KEY-----",
    r"\bAKIA[0-9A-Z]{16}\b",              # AWS
    r"\bsk-[A-Za-z0-9_-]{20,}",              # OpenAI/Anthropic-Stil
    r"\bgh[pousr]_[A-Za-z0-9]{20,}",         # GitHub
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}",       # Slack
    r"\bAIza[0-9A-Za-z_-]{30,}",             # Google
    r"\bey[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",   # JWT
    r"Authorization\s*:\s*(Bearer|Basic)\s+\S{10,}",
    r"://[^/\s:@]+:[^/\s@]{6,}@",         # user:pass@host
)

# "irgendwas = wert" -- hier muss der Wert noch geprueft werden, sonst
# schlaegt jede Zeile Quelltext an, die das Wort "token" enthaelt.
# Die Wortgrenze davor darf kein \b sein: In "DB_PASSWORD" steht ein
# Unterstrich vor dem Wort, und der ist selbst ein Wortzeichen -- \b
# findet dort keine Grenze und das Muster ging daran vorbei. Gemessen.
INHALT_ZUWEISUNG = re.compile(
    r"(?<![A-Za-z])(api[_-]?key|apikey|client[_-]?secret|secret|token|"
    r"passwor[dt]|kennwort|passphrase|pwd|auth[_-]?token)(?![A-Za-z])"
    r"""\s*[:=]\s*["']?([^\s"',;]{8,})""",
    re.IGNORECASE,
)

# Was wie ein Zugang aussieht, aber keiner ist. Ohne diese Liste fragt
# Sarvis vor jeder README nach, in der "API_KEY=dein_schluessel_hier"
# als Beispiel steht -- und vor halbem Quelltext.
PLATZHALTER = re.compile(
    r"^(your|dein|deine|my|xxx|\.\.\.|<|\\{|\$|%|null|none|true|false|"
    r"changeme|change_me|example|beispiel|todo|test|dummy|placeholder|"
    r"secret|token|password|passwort|os\.|process\.|getenv|env\.|"
    r"config\.|self\.|this\.|req\.|resp)",
    re.IGNORECASE,
)


def unpruefbares_dokument(pfad: str) -> bool:
    """Ein Dokument, in das die Pruefung nicht hineinsehen kann?"""
    try:
        p = Path(pfad)
        return p.suffix.lower() in DOKUMENT_UNPRUEFBAR and p.is_file()
    except (OSError, ValueError):
        return False


def _zip_text(pfad: Path) -> str:
    """Den Text aus einem Office- oder OpenDocument-Container holen.

    Nur die XML-Teile, nur die ersten paar hundert Kilobyte. Bilder und
    Einbettungen interessieren nicht -- gesucht wird Geschriebenes.
    """
    import zipfile
    stuecke: list[str] = []
    gesamt = 0
    try:
        with zipfile.ZipFile(pfad) as archiv:
            for eintrag in archiv.namelist():
                if not eintrag.lower().endswith((".xml", ".txt", ".rels")):
                    continue
                try:
                    roh = archiv.read(eintrag)[:PRUEF_BYTES]
                except (KeyError, OSError, RuntimeError, zipfile.BadZipFile):
                    continue
                stuecke.append(roh.decode("utf-8", errors="replace"))
                gesamt += len(roh)
                if gesamt > 4 * PRUEF_BYTES:
                    break
    except (OSError, ValueError, zipfile.BadZipFile):
        return ""
    # Die XML-Marken raus, sonst steht zwischen jedem Wort ein Tag und
    # "Passwort: geheim" ist nie ein zusammenhaengender Text.
    text = " ".join(stuecke)
    return re.sub(r"<[^>]{0,200}>", " ", text)


def _als_text(roh: bytes):
    """Die Rohbytes als Text -- oder None, wenn es wirklich binaer ist.

    Der Nullbyte-Abbruch allein war zu grob: UTF-16 besteht zur Haelfte
    aus Nullbytes, und unter Windows entsteht so ziemlich alles, was
    PowerShell 5.1 mit ">" oder Out-File schreibt, in UTF-16. Gemessen:
    dieselbe Datei mit demselben Schluessel fiel als UTF-8 auf "fragen"
    und als UTF-16 auf "frei" -- die Inhaltspruefung sah nur Nullen und
    hielt Text fuer ein Bild.
    """
    if roh[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return roh.decode("utf-16", errors="replace")
    kopf = roh[:4096]
    if b"\x00" not in kopf:
        return roh.decode("utf-8", errors="replace")
    # Ohne Vorzeichen hilft nur die Verteilung: Bei UTF-16 steht in
    # lateinischem Text jedes zweite Byte auf Null, immer an derselben
    # Stelle. Ein Bild oder eine EXE hat die Nullen verstreut.
    gerade = kopf[0::2].count(0)
    ungerade = kopf[1::2].count(0)
    haelfte = max(1, len(kopf) // 2)
    if ungerade > haelfte * 0.8 and gerade < haelfte * 0.2:
        return roh.decode("utf-16-le", errors="replace")
    if gerade > haelfte * 0.8 and ungerade < haelfte * 0.2:
        return roh.decode("utf-16-be", errors="replace")
    return None


def inhalt_heikel(pfad: str) -> bool:
    """Stehen in der Datei mutmasslich Zugangsdaten?

    Bewusst wohlwollend: Im Zweifel False. Ein Fehlalarm bei jeder
    zweiten Datei waere schlimmer als keine Pruefung -- dann klickt man
    die Rueckfrage weg, ohne hinzuhoeren, und der Schutz ist weg.
    """
    try:
        p = Path(pfad)
        if not p.is_file() or p.stat().st_size > PRUEF_GROESSE_MAX:
            return False
    except (OSError, ValueError):
        return False

    if p.suffix.lower() in DOKUMENT_ZIP:
        text = _zip_text(p)
        if not text:
            return False
    else:
        try:
            with p.open("rb") as datei:
                roh = datei.read(PRUEF_BYTES)
        except (OSError, ValueError):
            return False
        text = _als_text(roh)
        if text is None:
            return False                   # binaer, kein Textgeheimnis

    if any(re.search(m, text, re.IGNORECASE) for m in INHALT_EINDEUTIG):
        return True

    for treffer in INHALT_ZUWEISUNG.finditer(text):
        wert = treffer.group(2)
        if not PLATZHALTER.match(wert):
            return True
    return False


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
        laufwerk = p.drive.rstrip(":")
        # Eine Endung heisst Datei. Ohne diese Unterscheidung fragte
        # Sarvis "Soll ich den Ordner alt.zip verschieben?" -- und wer
        # das hoert, sagt nein, weil er denkt, es sei das Falsche gemeint.
        if p.suffix:
            artikel = "der" if fall == "dativ" else "die"
            return f"{artikel} Datei {p.name} auf Laufwerk {laufwerk}"
        artikel = "dem" if fall == "dativ" else "den"
        return f"{artikel} Ordner {p.name} auf Laufwerk {laufwerk}"
    return p.name or str(pfad)


# Aus einem Befehl wird eine Absicht. Vorgelesen will niemand
# "Get-PSDrive -Name D | Select-Object Name,Used,Free,Root" hoeren --
# das beantwortet man nicht, das erduldet man.
_ABSICHTEN = (
    (r"^(Get-ChildItem|gci|dir|ls|tree)\b", "nachsehen, was in {} liegt",
     # Kein "dort": Ohne Argument MEINT der Befehl den Arbeitsordner --
     # das ist eine Auskunft, "dort" ist keine.
     "nachsehen, was im aktuellen Ordner liegt"),
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
    # Alles Weitere kam beim Bauen des Finanzdashboards vor -- und wurde
    # mangels Muster als nackte Kommandozeile vorgelesen.
    (r"^(for|while|foreach|ForEach-Object)\b", "",
     "mehrere Dateien der Reihe nach durchgehen"),
    (r"^if\b", "", "eine Bedingung prüfen"),
    (r"^(cat|head|tail|more)\b", "{} lesen", "eine Datei lesen"),
    (r"^echo\b", "", "etwas ausgeben"),
    (r"^(pytest|py\.test)\b", "", "die Tests laufen lassen"),
    (r"^(node|npx)\b", "", "ein Node-Programm ausführen"),
    (r"^ng\b", "", "das Angular-Werkzeug aufrufen"),
    (r"^docker(\s+compose)?\b", "", "einen Docker-Befehl ausführen"),
    (r"^(uvicorn|gunicorn|flask)\b", "", "den Webserver starten"),
    (r"^(pip|uv)\b", "", "Pakete verwalten"),
    (r"^(where|which|Get-Command)\b", "", "nachsehen, wo ein Programm liegt"),
    (r"^(findstr|Select-String|grep|rg)\b", "in {} suchen", "etwas suchen"),
    (r"^(Test-Path|test)\b", "nachsehen, ob es {} gibt",
     "nachsehen, ob etwas da ist"),
)


def _erstes_ziel(rest: str) -> str:
    """Das erste Argument, das ein Ziel sein koennte -- ohne Schalter.

    Frueher galt nur ein voller Pfad mit Laufwerksbuchstaben als Ziel.
    Ein relativer wie "app/routers" oder schlicht "tests" wurde
    uebersehen, und uebrig blieb die Frage "Soll ich nachsehen, was DORT
    liegt?" -- die kann niemand beantworten, der nur zuhoert. Genau
    daran ist es im Betrieb gescheitert.

    shlex statt eigener Zerlegung, damit ein Pfad mit Leerzeichen in
    Anfuehrungszeichen ein Argument bleibt. posix=False, weil der
    Backslash hier Pfadtrenner ist und kein Fluchtzeichen.
    """
    try:
        stuecke = shlex.split(rest, posix=False)
    except ValueError:          # unpaarige Anfuehrungszeichen
        stuecke = rest.split()
    for wort in stuecke:
        wort = wort.strip("\"").strip("'")
        # Schalter (-Recurse, --long), Variablen und Verkettungen sind
        # kein Ziel.
        if not wort or wort[0] in "-$" or wort in ("|", "&", "&&", ";"):
            continue
        # "/s" ist ein Schalter, "/d/Projekte/Finanzdashboard" ein Pfad --
        # so schreibt die Git-Bash Laufwerke. Ohne diese Unterscheidung
        # fiel der Pfad durch, und die Rueckfrage las die ganze
        # Kommandozeile vor statt zu sagen, worum es geht.
        if wort.startswith("/") and "/" not in wort[1:]:
            continue
        return wort
    return ""


def _wie_pfad(wort: str) -> bool:
    """Sieht das Argument ueberhaupt nach einem Ort aus?

    Ohne diese Frage wurde aus "docker compose up" ein "Soll ich einen
    Befehl auf compose ausfuehren?" -- ein Unterbefehl als Ort verkauft.
    Dann lieber den Befehl selbst nennen.
    """
    try:
        p = Path(wort)
    except (OSError, ValueError):
        return False
    return len(p.parts) > 1 or bool(p.suffix) or wort in (".", "..")


_ZAHLWORTE = {2: "zwei", 3: "drei", 4: "vier", 5: "fünf", 6: "sechs",
              7: "sieben", 8: "acht", 9: "neun"}


def _schritte(befehl: str) -> list:
    """Eine Befehlskette in ihre Schritte zerlegen.

    Zwei Dinge passieren hier. Erstens wird an && und ; getrennt: Eine
    Kette ist kein Befehl, sondern mehrere, und wer fragt "was machst du
    da?" meint alle. Zweitens fliegt ein fuehrendes "cd" raus -- in
    welchen Ordner er vorher wechselt, ist nicht die Handlung, nach der
    gefragt wird. Genau daran scheiterte die Beschreibung von
    "cd /d/Projekte/Finanzdashboard && cat README.md".
    """
    # NICHT am Semikolon trennen: In "for f in *.py; do echo $f; done"
    # steht es mitten in EINEM Befehl, und das Zerlegen machte daraus
    # drei sinnlose Schritte ("einen Befehl mit do ausfuehren").
    roh = re.split(r"&&|\|\|", str(befehl or ""))
    schritte = [t.strip() for t in roh if t.strip()]
    ohne_cd = [t for t in schritte if not re.match(r"^cd\b", t, re.IGNORECASE)]
    return ohne_cd or schritte or [""]


def absicht(befehl: str) -> str:
    """Was der Befehl vorhat, in wenigen Worten -- zum Vorlesen.

    Bewusst NIE die Kommandozeile selbst: Vorgelesen kann damit niemand
    etwas anfangen, und eine Frage, die man nicht versteht, beantwortet
    man nicht -- man erduldet sie.
    """
    schritte = _schritte(befehl)
    erste = _eine_absicht(schritte[0])
    if len(schritte) == 1:
        return erste
    if len(schritte) == 2:
        return f"{erste} und danach noch etwas machen"
    # Ziffern werden vorgelesen wie Ziffern; Woerter klingen wie Sprache.
    zahl = _ZAHLWORTE.get(len(schritte) - 1, str(len(schritte) - 1))
    return f"{erste} und danach noch {zahl} weitere Schritte machen"


def absicht_lang(befehl: str) -> str:
    """Alle Schritte in Worten -- fuer "und welcher Befehl genau?".

    Dieselbe Sprache wie absicht(), nur vollstaendig. Auch hier keine
    Kommandozeile: Wer nachfragt, will es GENAUER wissen, nicht
    technischer.
    """
    teile = [_eine_absicht(t) for t in _schritte(befehl)]
    if len(teile) == 1:
        return teile[0]
    return ", dann ".join(teile[:-1]) + f", und zum Schluss {teile[-1]}"


def _eine_absicht(befehl: str) -> str:
    """Ein einzelner Schritt in Worten."""
    b = " ".join(str(befehl or "").split())
    erster = b.split("|")[0].strip()
    pfade = re.findall(r"[a-zA-Z]:[\\/][^\s\"';|]*", b)
    # "was in X liegt" verlangt Dativ, "X lesen" Akkusativ.
    # Kein voller Pfad? Dann taugt das erste Argument als Ziel.
    teile = erster.split(None, 1)
    roh = pfade[0] if pfade else _erstes_ziel(teile[1] if len(teile) > 1 else "")
    ziel_dativ = sprechbar(roh, "dativ") if roh else ""
    ziel = sprechbar(roh) if roh else ""

    for muster, mit_ziel, ohne_ziel in _ABSICHTEN:
        if re.match(muster, erster, re.IGNORECASE):
            if ziel and mit_ziel:
                dativ = " in {}" in mit_ziel or mit_ziel.startswith("in {}")
                return mit_ziel.format(ziel_dativ if dativ else ziel)
            return ohne_ziel
    if ziel and _wie_pfad(roh):
        return f"einen Befehl auf {ziel} ausführen"
    # Letzter Ausweg: wenigstens das Programm nennen, das gerufen wird.
    # Die Kommandozeile vorzulesen war der Versuch davor und ist an der
    # Wirklichkeit gescheitert -- "cd Schraegstrich d Schraegstrich
    # Projekte und und cat README punkt md" beantwortet niemand.
    programm = teile[0] if teile else ""
    if programm and programm.isascii() and len(programm) <= 20:
        return f"einen Befehl mit {programm} ausführen"
    return "einen Befehl auf deinem Rechner ausführen"


def kurz_befehl(befehl: str, laenge: int = 90) -> str:
    b = " ".join(str(befehl or "").split())
    return b if len(b) <= laenge else b[: laenge - 1] + "…"
