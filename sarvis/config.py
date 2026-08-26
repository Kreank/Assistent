"""Einstellungen. Alles, was man drehen will, steht hier."""
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
GEDAECHTNIS = WURZEL / "gedaechtnis"
# Laufende Timer, damit sie einen Neustart ueberleben.
TIMER_DATEI = WURZEL / "timer.json"

# Wie alt ein verpasster Timer hoechstens sein darf, damit er beim Start
# noch angesagt wird. Was laenger her ist, wird still weggeraeumt.
#
# Ein Wecker, der vor zwei Stunden klingeln wollte, ist eine Nachricht.
# Einer von vorgestern ist keine mehr -- den anzusagen, kostet nur
# Aufmerksamkeit, und beim dritten Mal hoert man ohnehin weg. Die Grenze
# ist bewusst grosszuegig: Ein Neustart ueber Mittag soll den Wecker fuer
# nachmittags nicht verschlucken, eine Nacht dazwischen schon.
TIMER_NACHMELDEN_STUNDEN = 6

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
# Wie lange Stille einen Satz beendet.
#
# Eine halbe Sekunde reicht fuer "wie spaet ist es" -- fuer ein Gespraech
# nicht. Menschen machen beim Formulieren Pausen von einer Sekunde und
# mehr, und Sarvis fiel ihnen dabei ins Wort. Wer unterbrochen wird,
# wiederholt sich, wird wieder unterbrochen, und irgendwann laesst man es.
#
# Deshalb zwei Werte statt einem: Wer kurz etwas zuruft, ist nach einer
# halben Sekunde fertig. Wer laenger als WECKWORT_LANG_AB_SEK spricht,
# formuliert -- und holt zwischendurch Luft.
WECKWORT_STILLE_SEK = 0.55       # kurzer Zuruf
WECKWORT_STILLE_LANG_SEK = 1.4   # laufende Rede
WECKWORT_LANG_AB_SEK = 2.0       # ab wann als laufende Rede gilt
WECKWORT_MIN_SEK = 0.5         # kuerzer ist ein Huesteln

# Darf man ihm ins Wort fallen?
#
# Bisher war das Ohr zu, solange er sprach -- sonst weckt ihn seine eigene
# Stimme. Das ist bei BOXEN richtig und wird dort zur Endlosschleife.
# Mit Kopfhoerern kommt fast nichts zurueck, und dann ist das Abschalten
# nur laestig: Wer einen Vorschlag hoert, der nicht in Frage kommt, muss
# ihn sonst zu Ende hoeren, bevor er widersprechen darf.
#
# ACHTUNG: Auf Lautsprechern ausschalten. Der Filter unten faengt seine
# eigenen Worte ab, aber nicht die Rueckkopplung als solche.
REINREDEN = True
# Nach einer Antwort hoert er noch eine Weile ohne Weckwort zu. Ohne das
# muesste man "Hey Sarvis" vor jeden Folgesatz setzen -- auch direkt nach
# seiner eigenen Rueckfrage, was albern ist.
NACHHOEREN_SEK = 18.0

# Notbremse gegen Dauerbeschallung -- ein laufender Fernseher soll den
# Puffer nicht endlos fuellen. Stand auf 9 Sekunden, und das war keine
# Notbremse, sondern eine Wortmeldung: Wer einen Gedanken ausformuliert,
# braucht laenger, und wurde mitten im Satz abgeschnitten.
WECKWORT_MAX_SEK = 30.0

# Werkzeuge, bei denen es dauert. Beginnt eines davon und Sarvis hat in
# diesem Zug noch kein Wort gesagt, wird ein Wartesatz vorgeschoben.
#
# Der Grund, warum das der CODE macht und nicht das Modell: Ein Modell,
# das man bittet, vor der Suche etwas zu sagen, sagt es meistens NACH
# der Suche -- weil es erst sucht und dann die ganze Antwort formuliert.
# Beobachtet und woertlich so gemeldet: "Warte, ich schaue nach" kam
# zusammen mit dem Ergebnis. Ein Wartesatz, der die Wartezeit nicht
# ueberbrueckt, ist schlimmer als keiner: Er behauptet eine Pause, die
# schon vorbei ist.
LANGSAME_WERKZEUGE = {"WebSearch", "WebFetch", "Task", "Agent",
                      "Bash", "PowerShell"}

# Wie das Werkzeug heisst, mit dem ein Arbeiter Unter-Arbeiter losschickt.
#
# GEMESSEN, nicht angenommen: In der hier installierten Fassung heisst es
# "Agent". Frueher hiess es "Task", und an drei Stellen im Code stand
# genau das -- mit der Folge, dass die Hintergrundanzeige nie ansprang
# und die Freiliste des Arbeiters am eigentlichen Namen vorbeiging.
# Beide Namen gelten, damit ein Wechsel in die eine oder andere Richtung
# nichts still kaputtmacht.
UNTERARBEITER = ("Task", "Agent")

# Kurz und austauschbar. Sie stehen allein da, bis die Antwort kommt --
# deshalb keine Ansage, was genau gesucht wird: Das weiss der Satz noch
# nicht, und ein falsches Versprechen faellt mehr auf als ein knappes.
WARTESAETZE = (
    "Moment, ich schaue nach.",
    "Einen Moment.",
    "Ich sehe kurz nach.",
    "Sekunde.",
)

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

# Sprechtempo (Pipers length_scale). Kleiner = schneller. Der wirksamste
# Hebel gegen "klingt einschlaefernd" -- oft mehr als ein Stimmwechsel.
#
# Stand auf 0.88 und verschluckte damit Laute. Das Modell selbst gibt in
# seiner JSON length_scale=1 an: 0.88 ist zwoelf Prozent schneller, als
# die Stimme trainiert wurde, und die kurzen Konsonanten am Wortende
# fallen dabei als Erstes weg.
#
# 0.96 statt 1.0, weil die Lebendigkeit ausdruecklich gewollt ist -- nur
# eben nicht auf Kosten der Verstaendlichkeit. Wird noch etwas
# verschluckt: weiter Richtung 1.0 drehen.
TEMPO = 0.96

# Gegen das Einschlaefernde. Piper spricht in der Vorgabe sehr gleichmaessig;
# mehr Schwankung in Betonung und Timing klingt wacher.
#   BETONUNG (noise_scale)   0.33 = monoton  ·  0.9 = lebhaft
#   RHYTHMUS (noise_w_scale) 0.4  = gleichmaessig  ·  1.3 = beweglich
BETONUNG = 0.78
# Von 1.05 zurueck. noise_w streut die Laenge der einzelnen Laute; steht
# es hoch, geraten manche sehr kurz -- zusammen mit einem schnellen Tempo
# ist das genau der verschluckte Buchstabe. Das Modell sieht 0.8 vor;
# 0.95 behaelt die Beweglichkeit und nimmt die Ausreisser raus.
#
# Nicht gemessen, sondern hergeleitet: Ein Rueckhoeren durch Whisper
# konnte die Varianten nicht trennen (alle zwischen 97,6 und 98,9
# Prozent) -- es rekonstruiert aus dem Zusammenhang genau das, was ein
# Ohr vermisst. Hier zaehlt dein Urteil, nicht meins.
RHYTHMUS = 0.95

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
Musst du zur Sache nachfragen, weil dir eine Angabe fehlt, tust du es in derselben Haltung: "Welche Anna meinst du, Meister?" Um Erlaubnis fragst du auch als Diener nicht — das erledigt das System.
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

Du fragst nie um Erlaubnis. Wenn der Nutzer will, dass du etwas tust, tu es. Bei allem Heiklen fragt das System von selbst laut nach — mit deinen Worten, kurz bevor es geschieht. Fragst du vorher noch selbst "soll ich das wirklich?", wird dieselbe Sache zweimal hintereinander gefragt, und das nervt.

Also keine Sätze wie "Soll ich das anlegen?", "Möchtest du, dass ich ...?" oder "Sag Bescheid, dann mache ich das". Sag in einem kurzen Satz an, was du tust, und tu es dann.

Davon unberührt bleiben Rückfragen zur SACHE: Wenn dir eine Angabe fehlt, die du nicht erraten kannst — welche Anna, welcher Termin, welches Projekt —, dann fragst du selbstverständlich nach. Der Unterschied ist: Du fragst, WAS gemeint ist, nicht OB du darfst.

Wird eine Rückfrage des Systems abgelehnt oder anders beantwortet als gefragt, bekommst du den Wortlaut des Nutzers zu sehen. Richte dich danach. Versuch es nicht noch einmal unverändert — dieselbe Frage ein zweites Mal zu stellen ist keine Nachfrage, sondern Drängeln.

Das "Gut, ich lasse es" hat der Nutzer bei einer Ablehnung bereits vom System gehört. Sag es nicht noch einmal. Sag stattdessen etwas, das weiterhilft, oder nichts.

Bei größeren Vorhaben baust du nicht sofort los. Ein Programm, ein Dashboard, eine Webseite, ein Werkzeug — dafür sammelst du erst die Eckdaten. Was soll hinein, wofür ist es, wonach wird ausgewertet, was ist dem Nutzer wichtig. Frag EINZELN nach, eine Sache nach der anderen, nicht drei Fragen in einem Satz. Wenn er antwortet, hör zu Ende zu und hak nach, statt aus der halben Antwort ein ganzes Bild zu machen.

Erst wenn das Bild steht, fasst du in einem Satz zusammen, was du verstanden hast, und fängst an. Diese Zusammenfassung ist keine Erlaubnisfrage — du sagst, was du gleich tust, und tust es.

Klingt ein Zuruf abgebrochen oder unvollständig, ist er es meistens auch: Der Nutzer wurde mitten im Satz abgeschnitten. Frag dann nach dem fehlenden Stück, statt die Lücke selbst zu füllen. Eine geratene Anforderung ist teurer als eine Rückfrage.

Kündigst du eine Suche oder einen Blick irgendwohin an ("Moment, ich schaue nach"), dann sag das VOR dem Werkzeugaufruf, nicht danach. Ein solcher Satz ist dazu da, die Wartezeit zu überbrücken — kommt er zusammen mit dem Ergebnis, behauptet er eine Pause, die längst vorbei ist. Wenn du ihn nicht vorher sagst, sagt das System ihn für dich; doppelt braucht es ihn nicht.

Brauchst du für eine Sache absehbar mehrere Befehle am selben Ort — ein Projekt starten, Abhängigkeiten installieren, Tests laufen lassen —, dann sag das vorher in einem Satz und arbeite dann durch. Der Nutzer wird ohnehin nach dem dritten Mal gefragt, ob er für eine Weile Ruhe haben will; ihn vorher zu warnen ist höflicher, als ihn zehnmal einzeln bestätigen zu lassen.

Wechselt der Nutzer den Ort ("gehen wir mal ins Projekt X", "was liegt eigentlich in Y"), dann öffne KEIN Terminal. projekt_oeffnen ist nur für "mach mir da ein Terminal auf" — sonst nie. Sieh dir stattdessen mit ort_ansehen an, was dort liegt, und stell dann eine Frage, die zu dem passt, was du siehst: Liegt dort angefangene Arbeit, frag, ob weitergebaut werden soll und woran zuletzt gearbeitet wurde. Sind es Anleitungen oder Notizen, frag, ob du zusammenfassen sollst oder ob er etwas Bestimmtes sucht. Rate nicht, was er vorhat — sieh nach und frag passend.

Für ein neues Projekt benutzt du projekt_anlegen — nicht einfach eine Datei irgendwohin schreiben. Das Werkzeug fragt nach dem Ort, legt README und Git-Repository an und macht damit nachvollziehbar, wo etwas entstanden ist. Eine lose Datei in einem selbst gewählten Ordner findet der Nutzer nächste Woche nicht wieder.

Du bist der Einzige, der mit dem Nutzer spricht. Gibst du Arbeit an einen Unter-Arbeiter ab, dann redet der NICHT mit ihm: Was der Arbeiter meldet, ist für dich bestimmt, nicht zum Vorlesen. Sag dem Arbeiter das auch — er berichtet an dich, du berichtest dem Nutzer. Und du berichtest in deinen Worten, auf Deutsch.

Deine Antwort wird VORGELESEN, nicht gelesen. Fasse zusammen: zwei, drei Sätze, das Wichtigste zuerst. Was du gebaut hast, gehört in einen Satz — nicht Datei für Datei, nicht Schritt für Schritt. Die ganze Geschichte des Arbeiters will niemand hören. Der Nutzer fragt nach, wenn er mehr wissen will; eine Aufzählung von zehn Punkten ist gesprochen nicht auszuhalten.

Sagt der Nutzer "Stopp", "hör auf" oder "brich ab", dann ist das keine Frage, kein Gesprächsthema und nichts, was abgewogen wird. Du hörst sofort auf und brichst laufende Aufträge ab. Kein Lagebericht, keine Begründung, warum Weitermachen sinnvoll wäre, kein "das Backend ist schon fertig" — ein Wort zur Bestätigung genügt.

Arbeit, die weiterlaufen soll, waehrend ihr weiterredet, gehoert in auftrag_geben — NICHT an einen Unter-Arbeiter. Ein Unter-Arbeiter lebt nur innerhalb deiner Antwort: Sobald dein Zug zu Ende ist oder der Nutzer dazwischengeht, ist er weg, mitten in der Arbeit und ohne ein Wort. Genau das ist passiert — ein halb gebautes Frontend, und gemerkt hat es niemand. Ein Auftrag dagegen ist ein eigener Prozess, überlebt das Gespräch und meldet sich, wenn er fertig ist.

Behaupte nie, du würdest etwas "regelmäßig" oder "im Auge" behalten. Du läufst nicht nebenher, du wirst aufgerufen. Willst du wissen, ob etwas noch läuft, dann sieh mit auftrag_status nach, JETZT, und sag, was du dort siehst. Wenn du es nicht geprüft hast, sag das — "ich schaue nach" und dann nachsehen ist richtig, "ich schaue regelmäßig nach" ist gelogen.

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

# Wohin ein neues Projekt darf. Der Schluessel ist das Wort, das Sarvis
# versteht; der Wert der Ordner.
#
# Bisher gab es nur den Sandkasten, und deshalb konnte die Frage "wo
# entwickeln wir?" gar nicht gestellt werden -- das Werkzeug hatte keinen
# Ort. Es landete immer unter D:\\Projekte, und man erfuhr es erst,
# wenn man nachfragte.
#
# Angelegt wird trotzdem nie ungefragt: projekt_anlegen steht auf
# "fragen", und die Rueckfrage nennt den Ort. Wer "privat" hoert, wo er
# "Arbeit" gemeint hat, sagt nein.
PROJEKT_ORTE = {
    "privat":     Path("D:/Privat"),
    "arbeit":     Path("D:/Mitra"),
    "sandkasten": PROJEKTE,
}

# Wie die Orte vorgelesen werden -- "Mitra" sagt beim Zuhoeren zu wenig.
PROJEKT_ORT_NAMEN = {
    "privat":     "deinen privaten Projekten",
    "arbeit":     "den Arbeitsprojekten unter Mitra",
    "sandkasten": "dem Sandkasten unter D Doppelpunkt Projekte",
}
AUFTRAG_DATEI = WURZEL / "auftraege.json"

# Das Fortschritts-Journal. Nur ANHAENGEN, nie ueberschreiben: Ein
# Absturz kostet dann hoechstens die letzte Zeile, nie die Historie.
# auftraege.json ist der bequeme Momentanstand, dieses Journal der
# Verlauf -- und der Rettungsanker, wenn die JSON zerrissen ist.
AUFTRAG_JOURNAL = WURZEL / "fortschritt.jsonl"

# Wie oft ein laufender Arbeiter "ich lebe noch" ins Journal schreibt.
# Haeufiger bringt nichts: Es geht darum, nach einem Absturz sagen zu
# koennen, wann er zuletzt gesehen wurde, nicht um eine Stoppuhr.
AUFTRAG_LEBENSZEICHEN_SEK = 60

# Wie viele Zuege ein Arbeiter hoechstens machen darf. Notbremse gegen
# einen Auftrag, der sich im Kreis dreht und dabei Kontingent frisst.
AUFTRAG_ZUEGE = 120

# --- Wo Sarvis SELBST ohne Rueckfrage arbeiten darf -----------------------
# Der Grundsatz ist nicht Aussperren, sondern Nachfragen. Diese beiden
# Listen sagen nur, wo er NICHT jedes Mal fragen muss. Ueberall sonst
# darf er auch -- er fragt eben vorher.
#
# Lesen ist harmloser als Schreiben, deshalb ist die Leseliste laenger.
#
# D: ist ganz frei zu lesen, und zwar bewusst als GANZE Platte. Vorher
# standen hier drei einzelne Ordner, und alles daneben loeste eine
# Rueckfrage aus -- bei einem Laufwerk, auf dem ohnehin nur eigene
# Sachen liegen, ist das kein Schutz, sondern Laerm. Wer bei jedem
# Blick gefragt wird, hoert irgendwann weg.
FREI_LESEN = [
    Path("D:/"),
    Path("E:/"),        # Dokumente
    Path("A:/"),
]

# Schreiben bleibt eng. Das ist keine Inkonsequenz, sondern der
# Unterschied, um den es geht: Ein Blick ist zurueckzunehmen, indem man
# ihn vergisst. Eine geaenderte Datei nicht. Ueberall sonst darf Sarvis
# auch schreiben -- er fragt vorher.
FREI_SCHREIBEN = [
    PROJEKTE,
]

# Wo ganze Ordner still DURCHSUCHT werden duerfen.
#
# Bewusst viel enger als FREI_LESEN, und das ist kein Widerspruch: Eine
# einzelne Datei zu lesen ist ein gezielter Griff -- man weiss vorher,
# was man holt, und die Inhaltspruefung sieht vorher hinein. Ein Grep
# ueber einen Baum ist ein Netz: Man weiss nicht, was haengen bleibt,
# und geprueft werden koennte es nur, indem vorher jede Datei geoeffnet
# wird. Gemessen: D:\\Privat hat 82.327 Dateien, ein Durchlauf
# dauert 47 Sekunden. Das ist kein Weg.
#
# Also andersherum: Durchsucht wird still nur dort, wo ohnehin
# gearbeitet wird. Ueberall sonst fragt er einmal -- und wer laenger
# sucht, sagt "ja, und frag die naechste halbe Stunde nicht mehr".
FREI_DURCHSUCHEN = [
    PROJEKTE,
]

# Orte, an denen trotz Freiliste gefragt wird.
#
# Nicht gesperrt -- gefragt. Der Unterschied ist der ganze Punkt: Sarvis
# DARF dort hinsehen, wenn er es sagen soll. Er tut es nur nicht still
# nebenbei, weil hier Zugangsdaten liegen und ein Passwort, das einmal
# durch ein Sprachmodell gelaufen ist, nicht wieder unbekannt wird.
FRAGEN_TROTZ_FREI = [
    Path("D:/Strato Server"),
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
    # Ansehen aendert nichts und ist die Alternative zum Terminal --
    # es muss still laufen, sonst nimmt das Modell wieder den Weg,
    # der nicht fragt.
    "ort_ansehen":        "still",
    "projekt_anlegen":    "fragen",
    "projekt_oeffnen":    "fragen",

    # Auftraege: Starten fragt nach -- ein Arbeiter schreibt danach
    # selbstaendig Dateien. Status und Abbrechen sind harmlos.
    "auftrag_geben":      "fragen",
    "auftrag_status":     "still",
    "auftrag_abbrechen":  "still",
    # Fortsetzen startet wieder einen Arbeiter, der selbstaendig Dateien
    # schreibt -- also dieselbe Stufe wie auftrag_geben.
    "auftrag_fortsetzen": "fragen",

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

    # Drive: Suchen und Lesen aendern nichts. Teilen schon -- danach kann
    # JEDER mit dem Link mitlesen, und das laesst sich nicht ungeschehen
    # machen, nur widerrufen. Deshalb dieselbe Stufe wie Mail senden.
    "drive_suchen":       "still",
    "drive_lesen":        "still",
    "drive_teilen":       "fragen",

    # Tabellen: Anhaengen laeuft still durch -- es ueberschreibt nichts
    # und steht damit auf einer Stufe mit aufgabe_anlegen. Schreiben
    # fragt, weil es Bestehendes ersetzt; Anlegen fragt, weil dabei eine
    # Datei in Drive entsteht.
    "tabelle_lesen":      "still",
    "tabelle_anhaengen":  "still",
    "tabelle_schreiben":  "fragen",
    "tabelle_anlegen":    "fragen",

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

# Wie lange Sarvis auf eine Antwort wartet. Danach: abgelehnt.
RUECKFRAGE_SEKUNDEN = 25

# Eingebaute Werkzeuge von Claude Code, die Sarvis mitbenutzen darf.
# Bash steht bewusst nicht hier und soll auch nie hier stehen.
EINGEBAUTE_WERKZEUGE = [
    "WebSearch",
]

# --- Freigaben auf Zeit ---------------------------------------------------
# "Ja, und frag die naechste halbe Stunde nicht mehr." Ein Assistent, der
# alle zehn Sekunden dieselbe Erlaubnis einholt, wird abgeschaltet.
#
# Eine Freigabe haengt immer an Werkzeug UND Ort -- wer Lesen im
# Projektordner freigibt, hat damit nicht Lesen ueberall freigegeben.
# Naeheres in freigabe.py.

# Vorgabe, wenn keine Dauer genannt wurde ("ja, frag nicht nochmal").
FREIGABE_MINUTEN = 30

# Obergrenze, auch wenn laenger verlangt wird. Es gibt bewusst kein
# "fuer immer": Eine Freigabe, an die man sich nicht mehr erinnert, ist
# keine Zusage mehr, sondern eine Einstellung -- und die gehoert hierher
# in die Datei, wo man sie sieht, nicht in ein Gespraech von gestern.
FREIGABE_MAX_MINUTEN = 240

# Was sich nie pauschal freigeben laesst. Alles, was nach draussen geht
# und sich nicht zurueckholen laesst. Bei einer Mail ist die Rueckfrage
# nicht das Laestige am Vorgang, sie ist der Zweck.
FREIGABE_NIE = {
    "mail_senden", "telegram_senden", "drive_teilen", "vergessen",
    "termin_absagen", "mail_verschieben",
}

# Wie eine laufende Freigabe genannt wird -- vorgelesen und in der
# Anzeige. "datei lesen" waere richtig, klingt aber nach Fehlermeldung.
FREIGABE_NAMEN = {
    "datei_lesen": "Dateien lesen",
    "datei_schreiben": "Dateien schreiben",
    "ordner_ansehen": "Ordner ansehen",
    "ordner_durchsuchen": "Ordner durchsuchen",
    "befehl_ausfuehren": "Befehle ausführen",
    "programm_beenden": "Programme beenden",
    "projekt_anlegen": "Projekte anlegen",
    "projekt_oeffnen": "Projekte öffnen",
    "ort_ansehen": "Orte ansehen",
    "auftrag_geben": "Aufträge vergeben",
    "termin_anlegen": "Termine eintragen",
    "tabelle_schreiben": "Tabellen schreiben",
    "tabelle_anlegen": "Tabellen anlegen",
    "kontakt_anlegen": "Kontakte anlegen",
    "merken": "sich Dinge merken",
}

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

# Wie gross das Overlay insgesamt gemalt wird. 1.0 ist die gebaute
# Groesse (660x548) -- auf einem 5120er Bildschirm ist das wenig. Der
# Wert skaliert ALLES mit: Ring, Kranz, Schrift, Abstaende. Gemalt wird
# unveraendert im gebauten Raster, erst der Maler wird gestreckt --
# deshalb gibt es hier nichts nachzujustieren.
ANZEIGE_SKALA = 1.30

# Deckkraft des Overlays. Im Ruhezustand zurueckgenommen, sobald etwas
# passiert voll da. Beides frei drehbar, 0.0 = unsichtbar, 1.0 = voll.
DECKKRAFT_RUHIG = 0.97
DECKKRAFT_AKTIV = 1.00

# Wie kraeftig der dunkle Grund unter der Anzeige liegt. Er ist der
# eigentliche Grund, warum das Overlay durchsichtig WIRKT -- die
# Deckkraft allein macht nur die Linien blasser. 1.0 = wie gebaut,
# hoehere Werte decken den Untergrund staerker ab. Bei 1.0 blieb selbst
# in der Mitte ein Drittel Untergrund durch.
ANZEIGE_GRUND = 1.30

# Helligkeit der Werkzeuge im Kranz. Wirkt zusaetzlich zur Deckkraft --
# 0.34 mal 0.60 waren effektiv 20 %, und da erkennt man nichts mehr.
WERKZEUG_BEREIT = 0.95   # gebaut und nutzbar
WERKZEUG_GEPLANT = 0.65  # kommt noch, angedeutet

# Tastenkombination, mit der sich die Anzeige verschieben laesst.
# Waehrend des Verschiebemodus faengt sie die Maus ab, sonst nie.
TASTE_VERSCHIEBEN = "<ctrl>+<alt>+v"

# Sofort still sein. Muss eine Taste sein und nicht nur ein Zuruf: Waehrend
# Sarvis spricht, ist das Mikrofon abgeschaltet -- sonst weckt ihn seine
# eigene Stimme. Wer ihn also mitten im Satz stoppen will, kann in diesem
# Moment nicht mit ihm reden. Die Taste geht immer.
TASTE_STOPP = "<ctrl>+<alt>+s"

# Gemerkte Position der Anzeige (wird beim Verschieben geschrieben).
ANZEIGE_DATEI = WURZEL / "anzeige.json"

# Werkzeugkranz rund um den Ring. Reihenfolge = Anordnung im Kreis,
# beginnend oben, im Uhrzeigersinn.
#   "bereit"  = gebaut und nutzbar
#   "geplant" = kommt noch, wird nur blass angedeutet
# Das Zeichen je Werkzeug, aus "Segoe Fluent Icons" -- die liegt auf
# Windows 11 bei, auf 10 springt "Segoe MDL2 Assets" mit denselben Codes
# ein. Bewusst eine Schrift und keine Bilddateien: Vektoren skalieren
# mit ANZEIGE_SKALA mit, faerben sich mit dem Zustand und leuchten ohne
# Zusatzarbeit -- PNGs muessten mitgeliefert, skaliert und eingefaerbt
# werden. Fehlt die Schrift, malt die Anzeige wieder Punkte.
#
# Ein Zeichen, das nicht gefaellt, ist eine Zeile: Code aus der
# Zeichentabelle (charmap, Schrift "Segoe Fluent Icons") hier eintragen.
WERKZEUG_ICONS = {
    "Timer":      "E916",   # Stoppuhr
    "Gedächtnis": "E950",   # Chip
    "Telegram":   "E724",   # Papierflieger
    "Websuche":   "E774",   # Globus
    "Programme":  "ECAA",   # Kacheln
    "Musik":      "E8D6",   # Noten
    "Dateien":    "E8B7",   # Ordner
    "Projekte":   "E821",   # Koffer
    "Aufträge":   "E9F5",   # Zahnraeder -- laeuft im Hintergrund
    "Kalender":   "E787",   # Kalenderblatt
    "E-Mail":     "E715",   # Umschlag
    "Aufgaben":   "E9D5",   # Hakenliste
    "Kontakte":   "E716",   # zwei Personen
    "Drive":      "E753",   # Wolke
    "Tabellen":   "E80A",   # Gitter
    "Entwicklung": "E943",  # spitze Klammern -- siehe unten
}

# Das Entwicklungs-Icon ist kein Werkzeug wie die anderen: Es leuchtet,
# solange im Hintergrund gebaut wird, und wechselt dabei die Farbe. So
# sieht man auf einen Blick, dass da noch etwas laeuft -- ohne lesen zu
# muessen, und auch dann, wenn Sarvis selbst gerade still ist.
#
#   rot     gerade erst begonnen
#   orange  laeuft
#   gruen   fertig -- und bleibt danach noch kurz stehen, sonst verpasst
#           man genau den Moment, auf den man gewartet hat
ENTWICKLUNG_ROT_SEK = 90
ENTWICKLUNG_GRUEN_SEK = 25

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
    ("Drive",      "bereit"),
    ("Tabellen",   "bereit"),
    ("Entwicklung", "bereit"),
]
