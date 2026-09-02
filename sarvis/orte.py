"""Wo was liegt -- und wo Sarvis ohne Rueckfrage hinlangen darf.

Diese Datei ist aus config.py herausgeloest worden, weil die Pfade das
Einzige waren, was sich beim Umzug von Windows auf den Server wirklich
aendert. Sie standen ueber 1271 Zeilen verteilt; hier stehen sie
beieinander, und wer wissen will, wie weit Sarvis reicht, liest EINE
Datei statt einer ganzen.

config.py importiert alles hier Definierte zurueck. Jeder Aufrufer, der
bisher config.FREI_LESEN oder config.PROJEKT_ORTE geschrieben hat, tut
das weiter -- die Trennung ist eine Verschiebung, kein Umbau.

ZWEI DINGE, DIE HIER LEICHT UEBERSEHEN WERDEN:

Erstens steht diese Datei in schutz.NIE_SCHREIBEN, zusammen mit den fuenf
anderen Regeldateien. Sie MUSS dort stehen: Waeren die Freilisten hier
und die Sperre nicht, reichte ein gesprochenes "ja", um FREI_LESEN zu
erweitern -- also genau die Vollmacht, die sich selbst aendern darf und
deshalb keine ist. Wer diese Datei umbenennt, muss das Muster dort
mitziehen.

Zweitens ist "/" nirgends eine Freiliste, und das ist kein Versehen.
Auf Windows war D: ganz frei zu lesen, weil dort ohnehin nur Eigenes
lag und C: die natuerliche Grenze war. Auf Linux gibt es diese Grenze
nicht -- alles haengt an einem Baum. Der Reflex "D: war frei, also
nehmen wir /" waere der schwerste denkbare Fehler: Er zoege /proc mit
herein, und dort steht in jedem environ die Umgebung eines fremden
Prozesses. Gemessen faellt die durch die Inhaltspruefung, weil sie
NUL-getrennt ist und deshalb als binaer gilt.
"""
import os
from pathlib import Path


def _aus_umgebung(name: str, vorgabe: Path) -> Path:
    """Ein Ort, den die Umgebung uebersteuern darf.

    Damit gilt dieselbe Datei im Container, auf dem blanken Server und
    zum Ausprobieren -- ohne Zweig auf sys.platform und ohne zweite
    Fassung, die auseinanderlaeuft.
    """
    wert = os.environ.get(name, "").strip()
    return Path(wert) if wert else vorgabe


# --- Die beiden Wurzeln ---------------------------------------------------
# Sie sind bewusst getrennt und liegen sogar auf verschiedenen Platten.
#
#   WURZEL  der Quelltext. Liegt im Git, wird deployt, aendert sich durch
#           Commits.
#   DATEN   was Sarvis mitbringt und erzeugt: Gedaechtnis, Timer,
#           Auftragsjournal, Zugaenge, abgelegte Berichte.
#
# Beides in einen Topf zu werfen war auf einem Einzelplatz-PC bequem und
# ist auf einem Server falsch: Erzeugtes waechst, gehoert nicht ins
# Repository, und es muss einen "git checkout" ueberleben.
WURZEL = Path(__file__).resolve().parent.parent
DATEN = _aus_umgebung("SARVIS_DATEN", Path("/srv/data/sarvis"))

# --- Was Sarvis erzeugt ---------------------------------------------------
# Sein Werktisch: Berichte als Seite, Auswertungen, Zwischenstaende.
ABLAGE = DATEN / "erzeugt"

# Was von aussen HEREINKOMMT -- Dateien, die jemand aus der App
# herueberschickt. Getrennt von ABLAGE, weil die Herkunft der
# Unterschied ist: In ABLAGE liegt, was Sarvis selbst gebaut hat, hier
# liegt, was ihm gegeben wurde. Beim Aufraeumen ist das der Unterschied
# zwischen "kann er neu erzeugen" und "ist weg".
EINGANG = DATEN / "eingang"

# Das Gedaechtnis -- Markdown, von Hand lesbar. Der einzige hier
# genannte Ort, dessen Verlust unersetzlich ist: Der Rest erzeugt sich
# neu, das hier ist alles, was Sarvis ueber Sascha weiss.
GEDAECHTNIS = DATEN / "gedaechtnis"

# --- Projekte -------------------------------------------------------------
# Der Sandkasten. Bewusst NEBEN den echten Projekten, nicht darin: Der
# Ordner ist die Grenze, nicht die Vernunft des Modells.
PROJEKTE = DATEN / "sandkasten"

# Wohin ein neues Projekt darf. Der Schluessel ist das Wort, das Sarvis
# versteht; der Wert der Ordner.
#
# Angelegt wird nie ungefragt: projekt_anlegen steht auf "fragen", und
# die Rueckfrage nennt den Ort. Wer "privat" hoert, wo er "Arbeit"
# gemeint hat, sagt nein.
PROJEKT_ORTE = {
    "privat":     _aus_umgebung("SARVIS_PRIVAT", Path("/home/server3070")),
    "arbeit":     _aus_umgebung("SARVIS_ARBEIT", Path("/srv/storage/projects")),
    "sandkasten": PROJEKTE,
}

# Wie die Orte vorgelesen werden -- ein Pfad sagt beim Zuhoeren zu wenig.
PROJEKT_ORT_NAMEN = {
    "privat":     "deinem Benutzerordner",
    "arbeit":     "den Projekten unter s r v Storage",
    "sandkasten": "dem Sandkasten",
}

# --- Wo Sarvis ohne Rueckfrage arbeiten darf ------------------------------
# Der Grundsatz ist nicht Aussperren, sondern Nachfragen. Diese Listen
# sagen nur, wo er NICHT jedes Mal fragen muss. Ueberall sonst darf er
# auch -- er fragt eben vorher.
#
# Lesen ist harmloser als Schreiben, deshalb ist die Leseliste laenger.
# Was hier NICHT steht und auch nicht hineingehoert: /, /etc, /proc,
# /var, /root und die Docker-Volumes unter /srv/data.
FREI_LESEN = [
    PROJEKT_ORTE["arbeit"],
    PROJEKT_ORTE["privat"],
    DATEN,
]

# Schreiben bleibt eng. Das ist keine Inkonsequenz, sondern der
# Unterschied, um den es geht: Ein Blick ist zurueckzunehmen, indem man
# ihn vergisst. Eine geaenderte Datei nicht.
#
# Und es gibt einen zweiten, koerperlichen Grund fuer genau diesen Ort:
# /srv/data ist eine EIGENE PLATTE (sdc1). Ein harter Link kann keine
# Dateisystemgrenze ueberschreiten -- von hier aus laesst sich also gar
# kein Link auf etwas unter /srv/storage oder / legen. Das schliesst die
# Hardlink-Luecke physisch, zusaetzlich zum ln-Verbot in auftrag.py.
# (Gemessen: schreiben_stufe() lieferte fuer einen harten Link auf eine
# Datei ausserhalb "frei" -- ein harter Link hat kein Ziel, dem resolve()
# folgen koennte, er IST die Datei.)
#
# Wer diese Liste erweitert, prueft vorher mit "df", ob der neue Ort auf
# derselben Platte liegt wie etwas Schuetzenswertes.
FREI_SCHREIBEN = [
    PROJEKTE,
    ABLAGE,
]

# Wo ganze Ordner still DURCHSUCHT werden duerfen.
#
# Viel enger als FREI_LESEN, und das ist kein Widerspruch: Eine einzelne
# Datei zu lesen ist ein gezielter Griff -- man weiss vorher, was man
# holt, und die Inhaltspruefung sieht vorher hinein. Ein Grep ueber einen
# Baum ist ein Netz: Man weiss nicht, was haengen bleibt, und pruefen
# liesse es sich nur, indem vorher jede Datei geoeffnet wird.
FREI_DURCHSUCHEN = [
    PROJEKTE,
    ABLAGE,
]

# Orte, an denen trotz Freiliste gefragt wird.
#
# Nicht gesperrt -- gefragt. Sarvis DARF dort hinsehen, wenn er es sagen
# soll. Er tut es nur nicht still nebenbei, weil hier Zugangsdaten
# liegen und ein Passwort, das einmal durch ein Sprachmodell gelaufen
# ist, nicht wieder unbekannt wird.
#
# Die verstreuten .env-Dateien in den Projekten brauchen hier keinen
# Eintrag: schutz.HEIKEL faengt sie schon am Namen ab, dazu .ssh/,
# id_rsa, token, secret, passw und ein Dutzend mehr.
#
# ACHTUNG bei Erweiterungen: Diese Pruefung ist auf Linux buchstaben-
# genau (PosixPath vergleicht anders als WindowsPath). Kein Ort aus
# dieser Liste darf auf einem case-insensitiven Dateisystem liegen --
# eingehaengtes NTFS, exFAT, ZFS mit casesensitivity=insensitive.
FRAGEN_TROTZ_FREI = [
    Path.home() / ".ssh",
    Path.home() / ".claude",
    Path.home() / ".config",
    DATEN / "browser-profil",
]

# --- Arbeit am eigenen Projekt --------------------------------------------
# Ein Assistent, der beim Starten des eigenen Projekts siebenmal fragt,
# wird beim achten Mal nicht mehr gefragt -- dann tippt man selbst.
#
# Frei laeuft nur, was ALLE drei Bedingungen erfuellt: Der Arbeitsordner
# liegt unter einem ENTWICKLUNG_ORT, jeder Schritt der Kette steht in
# ENTWICKLUNG_BEFEHLE, kein Schritt in ENTWICKLUNG_FRAGT_TROTZDEM. Dazu
# kommt die vierte Bedingung in schutz.entwicklung_frei: Jeder im Befehl
# genannte Pfad liegt ebenfalls im Entwicklungsbereich.
#
# Diese vierte Bedingung war auf Linux ohne Wirkung, solange
# pfade_im_befehl() nur nach Laufwerksbuchstaben suchte -- gemessen war
# "cd /etc" damit frei. Sie traegt erst wieder, seit die Funktion auch
# POSIX-Pfade findet.
ENTWICKLUNG_ORTE = [
    PROJEKT_ORTE["arbeit"],
    PROJEKT_ORTE["privat"],
    PROJEKTE,
]

# --- Der Verlauf ----------------------------------------------------------
# Wo die Sitzungsdateien liegen, in denen verlauf_nachschlagen sucht.
# Sie schreibt das SDK, nicht Sarvis -- eine Zeile je Nachricht, und zwar
# vollstaendig: Auch was verdichtet wurde, steht dort weiter.
#
# Der Ordnername ist ein Slug aus dem Arbeitsverzeichnis. Auf Windows
# stand hier fest "D--Privat-Sarvis"; im Container heisst er anders, und
# der Fehlschlag waere STUMM -- verlauf_nachschlagen antwortet dann nur
# "Ich finde keinen gespeicherten Verlauf." Deshalb wird er aus WURZEL
# gerechnet statt geraten.
def _verlauf_slug(pfad: Path) -> str:
    """Wie Claude Code einen Pfad zu einem Ordnernamen macht."""
    return str(pfad).replace("/", "-").replace("\\", "-").replace(":", "-")


VERLAUF_ORDNER = _aus_umgebung(
    "SARVIS_VERLAUF",
    Path.home() / ".claude" / "projects" / _verlauf_slug(WURZEL),
)

# --- Windows-Reste --------------------------------------------------------
# Bleibt stehen, damit hinweis.py und einrichten.py importierbar bleiben.
# Auf Linux zeigt es ins Leere, und das ist folgenlos: hinweis.py prueft
# vorher sys.platform, einrichten.py wird auf dem Server nicht gerufen.
VERKNUEPFUNG = (Path.home() / "AppData/Roaming/Microsoft/Windows"
                / "Start Menu/Programs/Sarvis.lnk")
