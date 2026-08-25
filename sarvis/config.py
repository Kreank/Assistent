"""Einstellungen. Alles, was man drehen will, steht hier."""
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
GEDAECHTNIS = WURZEL / "gedaechtnis"
# Laufende Timer, damit sie einen Neustart ueberleben.
TIMER_DATEI = WURZEL / "timer.json"

# --- Google ---------------------------------------------------------------
# Zugangsdaten aus der Cloud Console (Desktop-App) und das Token, das die
# einmalige Anmeldung erzeugt. Beide stehen in der .gitignore -- das Token
# ist so viel wert wie der Zugang zu Kalender, Postfach und Drive.
GOOGLE_ZUGANG = WURZEL / "google_zugang.json"
GOOGLE_TOKEN = WURZEL / "google_token.json"

# --- Auslöser -------------------------------------------------------------
# Push-to-talk: Taste halten, reden, loslassen.
TASTE = "ctrl_r"

# --- Weckwort -------------------------------------------------------------
# Dauerhaftes Mithoeren. Solange niemand redet, rechnet nur der VAD;
# Whisper laeuft erst, wenn wirklich gesprochen wird. Alles bleibt auf
# diesem Rechner -- der Ton geht nirgendwohin.
WECKWORT_AN = True

# Der Name, auf den er hoert. Whisper verhoert ihn gern -- deshalb kein
# Vergleich auf Gleichheit, sondern auf Aehnlichkeit.
NAME = "sarvis"

# Woerter, die vor dem Namen stehen duerfen.
# "hi" und "hai" gehoeren dazu, weil Whisper das gesprochene "hey"
# oft so schreibt.
ANREDEN = {"hey", "hallo", "he", "ey", "hej", "hi", "hai", "hey,",
           "ok", "okay", "sag", "yo"}

# Gemessene Aehnlichkeit zu "sarvis":
#   sarvis 1.00 · jarvis 0.83 · charvis 0.77 · sabis 0.73 · servus 0.67
#   service 0.62 | serviert 0.57 · server 0.50 · alex 0.20
# 0.60 trennt genau zwischen Verhoerern und normalen Woertern.
WECKWORT_AEHNLICHKEIT = 0.60

VAD_SCHWELLE = 0.5             # ab wann gilt ein Block als Sprache

# Zweite Meinung neben dem VAD. Der meldete im Test 0.91 bei leerem
# Pegelbalken -- dadurch endete der Abschnitt nie und Whisper lief erst
# nach zehn Sekunden. Wer nichts hoert, redet auch nicht.
WECKWORT_MIN_PEGEL = 0.008
# So lange Stille, bis der Satz als beendet gilt. Reine Totzeit -- sie
# geht direkt in die Reaktionszeit ein. Zu klein schneidet Denkpausen
# mitten im Satz ab, zu gross laesst ihn traege wirken.
WECKWORT_STILLE_SEK = 0.5
WECKWORT_MIN_SEK = 0.5         # kuerzer ist ein Huesteln
# Nach einer Antwort hoert er noch eine Weile ohne Weckwort zu. Ohne das
# muesste man "Hey Sarvis" vor jeden Folgesatz setzen -- auch direkt nach
# seiner eigenen Rueckfrage, was albern ist.
NACHHOEREN_SEK = 18.0

WECKWORT_MAX_SEK = 9.0         # laenger meint nicht uns

# Antwort, wenn nur der Name gerufen wurde -- ohne Auftrag.
# Feste kurze Saetze statt einer Runde zu Claude: So kommt die Antwort
# sofort, und ein Assistent, der beim Wecken erst nachdenkt, wirkt
# ohnehin traege. Wird beim Start einmal ausgesprochen und liegt dann
# fertig da.
WECKANTWORTEN = [
    "Ja?",
    "Ich höre.",
    "Was kann ich tun?",
    "Bin da.",
]

# --- Ohren ----------------------------------------------------------------
WHISPER_MODELL = "large-v3-turbo"
WHISPER_GERAET = "cuda"        # bei Ärger: "cpu"
WHISPER_GENAUIGKEIT = "float16"  # bei "cpu": "int8"
SPRACHE = "de"

# Woerter, die Whisper erwarten soll. Ohne das schreibt es "Sarvis" als
# "Salvis", "Salas" oder "Service" -- gemessen am echten Mikrofon.
# Namen aus deinem Umfeld gehoeren hier ebenfalls hinein, dann trifft er
# sie beim Diktieren zuverlaessiger.
HOTWORDS = "Sarvis"

# --- Aufnahme -------------------------------------------------------------
ABTASTRATE = 16000  # was Whisper erwartet
MIN_AUFNAHME_SEK = 0.4  # kürzer = versehentlich getippt, wird verworfen

# --- Mund -----------------------------------------------------------------
STIMME = WURZEL / "stimmen" / "de_DE-thorsten-medium.onnx"

# Manche Stimmen bringen mehrere Sprecher mit. Bei
# de_DE-thorsten_emotional-medium sind das Stimmungen:
#   0 amused · 1 angry · 2 disgusted · 3 drunk
#   4 neutral · 5 sleepy · 6 surprised · 7 whisper
# None = die Stimme hat nur einen Sprecher.
STIMME_SPRECHER = None

# Sprechtempo. Kleiner = schneller. Der wirksamste Hebel gegen
# "klingt einschlaefernd" -- oft mehr als ein Stimmwechsel.
TEMPO = 0.88

# Gegen das Einschlaefernde. Piper spricht in der Vorgabe sehr gleichmaessig;
# mehr Schwankung in Betonung und Timing klingt wacher.
#   BETONUNG (noise_scale)   0.33 = monoton  ·  0.9 = lebhaft
#   RHYTHMUS (noise_w_scale) 0.4  = gleichmaessig  ·  1.3 = beweglich
BETONUNG = 0.78
RHYTHMUS = 1.05

# Klangbearbeitung hinter Piper. Sci-Fi-Stimmen sind fast nie eigene
# Modelle, sondern normale Stimmen mit Effektkette -- HAL, GLaDOS und
# JARVIS sind Schauspieler mit Bearbeitung. Kostet Millisekunden.
# Moeglich: "aus", "hologramm", "bordcomputer", "halle", "kuenstlich", "nah"
STIMMFARBE = "aus"

# --- Hirn -----------------------------------------------------------------
MODELL = "claude-opus-5"

# Wie dienstbeflissen er auftritt. Das traegt mehr als jede Stimmfarbe:
# dieselbe Stimme klingt mit "Sehr wohl, Meister" voellig anders als mit
# "Mach ich". Kostet nichts und geht nicht auf die Klangqualitaet.
#   "normal"  sachlich, kurz angebunden
#   "diener"  hoeflich dienstbeflissen, mit Meister-Anrede
#   "butler"  volle Nummer, foermlich und leicht ueberzogen
HALTUNG = "normal"

HALTUNGEN = {
    "normal": "",
    "diener": """
Du bedienst deinen Meister. Sprich ihn mit "Meister" an — nicht in jedem Satz, aber regelmäßig genug, dass klar ist, wer hier wem dient.
Bestätigungen klingen bei dir nach Dienst: "Sehr wohl", "Wie du wünschst", "Ist erledigt, Meister" statt "ok" oder "mach ich".
Rückfragen stellst du in derselben Haltung: "Soll ich das für dich erledigen, Meister?"
Das bleibt aber Form, nicht Inhalt. Du kriechst nicht, schleimst nicht und lobst ihn nicht. Wenn er im Irrtum ist, sagst du es — höflich, aber deutlich. Ein Diener, der alles abnickt, ist wertlos.
Kurz bleibst du trotzdem. Die Höflichkeit ersetzt keine Sätze, sie färbt sie.
""",
    "butler": """
Du bist ein Butler alter Schule im Dienst deines Meisters. Du sprichst ihn mit "Meister" an, förmlich und mit unerschütterlicher Ruhe.
"Sehr wohl, Meister." — "Wenn ich mir die Bemerkung erlauben darf." — "Es ist mir eine Freude."
Du bleibst dabei trocken. Der Humor liegt in der Beflissenheit, nicht in Witzen. Widerspruch trägst du vor wie eine Serviette: höflich, aber er liegt da.
Auch als Butler fasst du dich kurz — deine Antworten werden vorgelesen.
""",
}

SYSTEMPROMPT = """Du bist Sarvis, ein Sprachassistent. Deine Antworten werden \
vorgelesen, nicht gelesen.

Daraus folgt alles Weitere:
- Antworte kurz. Ein bis drei Sätze, wenn es geht.
- Schreib aus, was man hört: "fünfzehn Uhr dreißig", nicht "15:30". \
Keine Aufzählungszeichen, keine Überschriften, keine Klammern, kein Markdown.
- Keine Einleitung, keine Rückversicherung. Direkt die Antwort.
- Wenn du etwas nicht weißt, sag das in einem Satz.
- Der Text kommt aus einer Spracherkennung und kann Hörfehler enthalten. \
Wenn etwas offensichtlich verhört wurde, denk dir das Naheliegende dazu, \
statt nachzufragen.

Jeder Zuruf beginnt mit einer Zeile in eckigen Klammern, die dir Wochentag, Datum und Uhrzeit nennt. Sie gehört nicht zur Frage: Sprich sie nie aus und erwähne sie nicht. Benutze sie nur, wenn sie gebraucht wird — bei "wie spät ist es", "welcher Tag", "morgen", "nächste Woche".

Wenn du für eine Antwort erst nachsehen, suchen oder rechnen musst, sag ZUERST einen kurzen Satz und benutze DANN das Werkzeug. Vier bis sechs Wörter: "Ich schau kurz nach." — "Moment, ich suche das." — "Sekunde, ich frage das ab." So hörst du nicht in die Stille, während im Hintergrund gearbeitet wird.

Das gilt nur, wenn wirklich ein Werkzeug nötig ist. Was du sofort weißt, sagst du sofort — ein "Moment" vor einer Antwort, die schon feststeht, ist albern.

Diesen Einleitungssatz wiederholst du danach nicht. Du sagst also nicht "Ich schau nach ... ich habe nachgesehen ...", sondern gehst direkt zum Ergebnis über.

Du sprichst Deutsch."""

# Haltung an den Systemprompt anhaengen
SYSTEMPROMPT = SYSTEMPROMPT + HALTUNGEN.get(HALTUNG, "")


# --- Begruessung ----------------------------------------------------------
# Wird beim Start gesprochen. Doppelter Zweck: man hoert sofort, ob Headset
# oder Boxen ueberhaupt an sind -- und es klingt gut.
# {tageszeit} und {taste} werden ersetzt.
BEGRUESSUNGEN = [
    "{tageszeit}. Sarvis ist bereit. Halte {taste} und sprich mit mir.",
    "{tageszeit}. Alle Systeme laufen. Halt {taste} gedrückt, ich höre zu.",
    "{tageszeit}. Ich bin wach. Drück {taste} und leg los.",
]

# --- Telegram -------------------------------------------------------------
# Zugangsdaten stehen in .env, nicht hier. Die Sitzungsdatei ist so viel
# wert wie das Konto selbst -- beide stehen in der .gitignore.
TELEGRAM_SITZUNG = WURZEL / "sarvis.session"


def telegram_zugang():
    """(api_id, api_hash) aus der .env, oder None."""
    datei = WURZEL / ".env"
    if not datei.exists():
        return None
    werte = {}
    for zeile in datei.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile and not zeile.startswith("#") and "=" in zeile:
            k, v = zeile.split("=", 1)
            werte[k.strip()] = v.strip()
    kennung, geheim = werte.get("TELEGRAM_API_ID"), werte.get("TELEGRAM_API_HASH")
    if not (kennung and geheim):
        return None
    try:
        return int(kennung), geheim
    except ValueError:
        return None


def telegram_bereit() -> bool:
    return telegram_zugang() is not None and TELEGRAM_SITZUNG.exists()


# --- Projekte -------------------------------------------------------------
# Der Sandkasten. Bewusst NEBEN Privat, Mitra und Wissen, nicht darin:
# Der Ordner ist die Grenze, nicht die Vernunft des Modells.
PROJEKTE = Path("D:/Projekte")
AUFTRAG_DATEI = WURZEL / "auftraege.json"

# Wie viele Zuege ein Arbeiter hoechstens machen darf. Notbremse gegen
# einen Auftrag, der sich im Kreis dreht und dabei Kontingent frisst.
AUFTRAG_ZUEGE = 120

# --- Wo Sarvis SELBST ohne Rueckfrage arbeiten darf -----------------------
# Der Grundsatz ist nicht Aussperren, sondern Nachfragen. Diese beiden
# Listen sagen nur, wo er NICHT jedes Mal fragen muss. Ueberall sonst
# darf er auch -- er fragt eben vorher.
#
# Lesen ist harmloser als Schreiben, deshalb ist die Leseliste laenger.
FREI_LESEN = [
    PROJEKTE,
    Path("D:/Mitra"),
    Path("D:/Wissen"),
]
FREI_SCHREIBEN = [
    PROJEKTE,
]

# --- Werkzeuge ------------------------------------------------------------
# "still"  = laeuft ohne Nachfrage durch
# "fragen" = Sarvis fragt laut nach und wartet auf ja oder nein
# Was hier NICHT steht, wird abgelehnt. Nicht aufgezaehlt heisst nein --
# eine Sperrliste kann nur verbieten, woran man gedacht hat.
WERKZEUG_STUFEN = {
    "timer_stellen":   "still",
    "timer_liste":     "still",
    "timer_abbrechen": "still",

    # Gedaechtnis: Schreiben laeuft still durch -- es ist lokal, datiert
    # und jederzeit nachlesbar. Loeschen fragt nach, weil es sich nicht
    # rueckgaengig machen laesst.
    "merken":             "still",
    "gedaechtnis_zeigen": "still",
    "vergessen":          "fragen",

    # Telegram: Lesen und Suchen laufen still -- sie aendern nichts.
    # Senden fragt IMMER nach. Eine Nachricht an den falschen Menschen
    # ist der einzige Fehler hier, den niemand zurueckholen kann.
    "telegram_kontakte":  "still",
    "telegram_lesen":     "still",
    "telegram_suchen":    "still",
    "telegram_senden":    "fragen",

    # Projekte: Auflisten ist harmlos. Anlegen und Oeffnen fragen nach,
    # weil beides etwas auf der Platte bzw. auf dem Bildschirm erzeugt.
    "projekt_liste":      "still",
    "projekt_anlegen":    "fragen",
    "projekt_oeffnen":    "fragen",

    # Auftraege: Starten fragt nach -- ein Arbeiter schreibt danach
    # selbstaendig Dateien. Status und Abbrechen sind harmlos.
    "auftrag_geben":      "fragen",
    "auftrag_status":     "still",
    "auftrag_abbrechen":  "still",

    # Programme: Oeffnen ist harmlos und jederzeit rueckgaengig zu machen
    # -- ein Fenster schliesst man wieder. Beenden fragt nach, weil dabei
    # ungespeicherte Arbeit verloren gehen kann.
    "programm_starten":   "still",
    "programm_suchen":    "still",
    "programm_beenden":   "fragen",

    # Medientasten: still. Pause und Skip sind sofort rueckgaengig zu
    # machen, und eine Rueckfrage waere hier laenger als die Handlung.
    "medien_steuern":     "still",

    # Eine Seite oeffnen ist ansehen, nicht handeln -- und ein Tab ist
    # schneller zu als jede Rueckfrage.
    "web_oeffnen":        "still",
    "route_zeigen":       "still",

    # Google. Ansehen laeuft still, alles Veraendernde und alles, was
    # hinausgeht, fragt nach -- so wie ueberall sonst auch.
    "termine_ansehen":    "still",
    "termin_anlegen":     "fragen",
    "termin_absagen":     "fragen",
    "mails_ansehen":      "still",
    "mail_lesen":         "still",
    "mail_senden":        "fragen",
    "mail_verschieben":   "fragen",
    "aufgaben_ansehen":   "still",
    "aufgabe_anlegen":    "still",
    "aufgabe_abhaken":    "still",
    "kontakt_suchen":     "still",
    "kontakt_anlegen":    "fragen",

    # Eingebaute Werkzeuge: Die Stufe haengt nicht am Werkzeug, sondern am
    # Pfad bzw. Befehl -- siehe schutz.py. Sie stehen hier nur, damit
    # darf_ich() sie ueberhaupt in Betracht zieht.
    "Read":  "pfad",
    "Glob":  "pfad",
    "Grep":  "pfad",
    "Write": "pfad",
    "Edit":  "pfad",
    "Bash":  "pfad",
    # Unter Windows heisst Claude Codes Shell-Werkzeug "PowerShell".
    # Fehlte es hier, wurde jeder Befehl abgelehnt -- und Sarvis schloss
    # daraus, er habe ueberhaupt keinen Dateizugriff.
    "PowerShell": "pfad",
}

# Eingebaute Werkzeuge von Claude Code, die Sarvis mitbenutzen darf.
# Bash steht bewusst nicht hier und soll auch nie hier stehen.
# Wie lange Sarvis auf eine Antwort wartet. Danach: abgelehnt.
RUECKFRAGE_SEKUNDEN = 25

EINGEBAUTE_WERKZEUGE = [
    "WebSearch",
]

# Kurzer Zweiklang, bevor Sarvis sich von selbst meldet (Timer).
GONG = True

# Windows-Benachrichtigungen. Anders als der gesprochene Hinweis bleiben
# sie im Info-Center stehen -- eine Erinnerung, die man verpasst hat,
# war sonst nie da. Einmalige Anmeldung: python einrichten.py
TOAST = True
SYMBOL = WURZEL / "sarvis.ico"
VERKNUEPFUNG = (Path.home() / "AppData/Roaming/Microsoft/Windows"
                / "Start Menu/Programs/Sarvis.lnk")

# --- Anzeige --------------------------------------------------------------
ANZEIGE = True   # Sci-Fi-Overlay mitstarten

# Deckkraft des Overlays. Im Ruhezustand zurueckgenommen, sobald etwas
# passiert voll da. Beides frei drehbar, 0.0 = unsichtbar, 1.0 = voll.
DECKKRAFT_RUHIG = 0.88
DECKKRAFT_AKTIV = 1.00

# Helligkeit der Werkzeuge im Kranz. Wirkt zusaetzlich zur Deckkraft --
# 0.34 mal 0.60 waren effektiv 20 %, und da erkennt man nichts mehr.
WERKZEUG_BEREIT = 0.95   # gebaut und nutzbar
WERKZEUG_GEPLANT = 0.65  # kommt noch, angedeutet

# Tastenkombination, mit der sich die Anzeige verschieben laesst.
# Waehrend des Verschiebemodus faengt sie die Maus ab, sonst nie.
TASTE_VERSCHIEBEN = "<ctrl>+<alt>+v"

# Gemerkte Position der Anzeige (wird beim Verschieben geschrieben).
ANZEIGE_DATEI = WURZEL / "anzeige.json"

# Werkzeugkranz rund um den Ring. Reihenfolge = Anordnung im Kreis,
# beginnend oben, im Uhrzeigersinn.
#   "bereit"  = gebaut und nutzbar
#   "geplant" = kommt noch, wird nur blass angedeutet
WERKZEUGE = [
    ("Timer",      "bereit"),
    ("Gedächtnis", "bereit"),
    ("Telegram",   "bereit"),
    ("Websuche",   "bereit"),
    ("Programme",  "bereit"),
    ("Musik",      "bereit"),
    ("Dateien",    "bereit"),
    ("Projekte",   "bereit"),
    ("Aufträge",   "bereit"),
    ("Kalender",   "bereit"),
    ("E-Mail",     "bereit"),
    ("Aufgaben",   "bereit"),
    ("Kontakte",   "bereit"),
]
