"""Einstellungen. Alles, was man drehen will, steht hier.

Die PFADE stehen nicht hier, sondern in orte.py -- sie waren das
Einzige, was sich beim Umzug von Windows auf den Server wirklich
aendert, und sie lagen ueber diese ganze Datei verteilt. Von dort
werden sie zurueckgeholt, damit jeder Aufrufer weiter config.FREI_LESEN
oder config.PROJEKT_ORTE schreiben kann.

Was hier bleibt, ist Politik statt Topologie: Schwellwerte,
Werkzeugstufen, Befehlsmuster, der Systemprompt.
"""
import os
from pathlib import Path  # noqa: F401  -- von unten noch gebraucht

from .orte import (ABLAGE, DATEN, ENTWICKLUNG_ORTE, FRAGEN_TROTZ_FREI,
                   FREI_DURCHSUCHEN, FREI_LESEN, FREI_SCHREIBEN, GEDAECHTNIS,
                   PROJEKTE, PROJEKT_ORTE, PROJEKT_ORT_NAMEN, VERKNUEPFUNG,
                   VERLAUF_ORDNER, WURZEL)  # noqa: F401  -- Re-Export

# Wie viele Eintraege die IMMER geladene Schicht hoechstens traegt.
#
# Der Grund steht in gedaechtnis/LIESMICH.md: kern.md soll unter 60
# Zeilen bleiben. Fuer gemerkt.md und beobachtet.md galt das bisher
# nicht -- sie wuchsen ohne Bremse, und alles davon haengt an JEDEM
# Zuruf mit dran. Nicht wegen der Kosten (der Systemprompt wird
# zwischengespeichert), sondern weil Wichtiges zwischen Belanglosem
# untergeht, sobald es ein paar hundert Zeilen sind.
#
# Was darueber hinausgeht, wird NICHT geloescht, sondern als datierte
# Notiz eine Schicht tiefer gelegt und bleibt ueber
# gedaechtnis_nachschlagen auffindbar.
GEDAECHTNIS_MAX_EINTRAEGE = 60
# Laufende Timer, damit sie einen Neustart ueberleben.
TIMER_DATEI = DATEN / "timer.json"

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
GOOGLE_ZUGANG = DATEN / "google_zugang.json"
GOOGLE_TOKEN = DATEN / "google_token.json"

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
# Kuerzere Abschnitte gelten als Huesteln und werden verworfen.
#
# ACHTUNG, diese Schwelle greift derzeit NIE, und das ist Absicht: Die
# geprüfte Dauer umfasst den gesamten Puffer einschliesslich der
# Nachlauf-Stille (WECKWORT_STILLE_SEK, 0,55 s). Ein einzelner
# Sprachblock plus Nachlauf ergibt gemessen 0,600 s -- die 0,5 werden
# nie unterschritten.
#
# Scharf gestellt wurde sie bewusst nicht. Dazu muesste die Stille
# abgezogen und der Wert auf etwa 0,25 gesenkt werden, und dann traefe
# die Schwelle genau die Faelle, fuer die der Nachhoer-Zweig gebaut ist:
# "Ja." liegt bei rund 0,36 s, "YouTube" bei 0,45 s. Ein verschlucktes
# "Ja" kostet mehr als ein durchgelassenes Huesteln -- letzteres faengt
# Whisper ohnehin ab, indem es leeren Text liefert.
WECKWORT_MIN_SEK = 0.5

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
#
# Dann stand er auf 30 -- und damit exakt auf dem Punkt, an dem ein
# Diktat gerade erst anfaengt (DIKTAT_AB_SEK). Wer "Hey Sarvis, schreib
# mir einen Bericht ueber ..." sagte und dann ausholte, wurde nach einer
# halben Minute abgeschnitten. Ein Fernseher macht ohnehin alle paar
# Sekunden eine Pause und laeuft nie in diesen Deckel; getroffen hat er
# nur den, der wirklich etwas zu sagen hatte.
WECKWORT_MAX_SEK = 90.0

# Derselbe Deckel, wenn er dich gerade angesprochen hat -- also wenn du
# im offenen Nachhoerfenster zu reden anfaengst. Dann bist DU gemeint,
# und wer einen Gedanken zu Ende bringt, braucht mehr als eine halbe
# Minute. Der Wert ist trotzdem endlich: Der Puffer liegt im RAM, und
# drei Minuten bei 16 kHz sind rund elf Megabyte.
WECKWORT_MAX_ANGESPROCHEN_SEK = 180.0

# Ab wann er annimmt, dass du nicht zurufst, sondern diktierst.
#
# Kein Kommandowort und kein Knopf: Man sagt nicht "Sarvis, ich diktiere
# jetzt" -- man faengt an zu reden. Die Laenge der Rede ist das Signal.
# Es ist dieselbe Staffelung wie bei WECKWORT_STILLE_LANG_SEK, nur eine
# Stufe weiter: je laenger jemand spricht, desto geduldiger wird er.
#
# Der Preis steht offen da: Nach dem letzten Wort vergehen erst diese
# Sekunden, bevor Whisper ueberhaupt anfaengt. Beim Diktat ist das
# richtig -- unterbrochen zu werden kostet mehr als drei Sekunden.
DIKTAT_AB_SEK = 30.0
DIKTAT_STILLE_SEK = 3.0

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
# Werkzeuge, bei denen KEIN Wartesatz faellt. Die Liste ist bewusst
# andersherum gebaut als frueher, und dafuer gibt es zwei Gruende.
#
# ERSTENS war die alte Liste nutzlos. Sie zaehlte sechs Werkzeuge auf --
# WebSearch, WebFetch, Task, Agent, Bash, PowerShell --, also nur
# eingebaute. Keins von Sarvis' eigenen stand darin, und selbst ein
# Eintrag haette nichts genuetzt: Verglichen wurde der ROHE Name, und der
# lautet bei den eigenen "mcp__sarvis__mails_ansehen". Die Pruefung
# konnte nie zutreffen.
#
# ZWEITENS ist der Schaden ungleich verteilt. Vergisst man ein langsames
# Werkzeug, stehen fuenf bis sieben Sekunden Stille im Raum. Vergisst man
# ein schnelles, faellt ein "Moment" zu viel. Das eine merkt man sofort,
# das andere kaum -- also ist "langsam" die richtige Vorgabe, und ein
# neues Werkzeug schweigt nicht mehr aus Versehen.
#
# GEMESSEN an 301 echten Aufrufen aus den Sitzungsprotokollen (Mitte):
#
#   mails_ansehen      1,47s      termine_ansehen     0,52s
#   programm_starten   0,87s      kontakt_suchen      0,37s
#   aufgaben_ansehen   0,66s      finanzen_kontostand 0,18s
#   telegram_kontakte  0,63s      timer_stellen       0,01s
#
# Die einzelnen Werkzeuge sind also gar nicht das Problem -- die Stille
# entsteht durch die KETTE: ToolSearch, dann das Werkzeug, dann der
# Antworttext, jeweils eine Runde zum Modell. Deshalb faellt der
# Wartesatz beim ToolSearch, dem fruehesten Zeitpunkt, an dem ueberhaupt
# etwas bekannt ist -- siehe hirn.py.
SCHNELLE_WERKZEUGE = {
    # Rein im Arbeitsspeicher oder eine kleine Datei.
    "timer_stellen", "timer_liste", "timer_abbrechen",
    "merken", "person_merken", "notiz_schreiben", "vergessen",
    "gedaechtnis_zeigen", "gedaechtnis_nachschlagen",
    # Ein Tastendruck bzw. ein Datagramm, das niemand beantwortet.
    "medien_steuern", "kachel_zeigen", "kachel_weg",
    "web_zeigen", "web_schliessen", "route_zeigen",
    # Liest nur die eigene Sicherung.
    "auftrag_status", "projekt_liste",
}

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
# Sie muessen KURZ bleiben, und das ist keine Geschmacksfrage: Sie sind
# die Antwort auf das Weckwort, und ihr ganzer Zweck ist, sofort da zu
# sein. Ein epischer Dreizeiler waere hier genau das Gegenteil von dem,
# was er sein soll -- man wartet dann eben auf die Ansage statt auf die
# Antwort.
#
# Vierzehn statt vier, weil vier bei taeglicher Benutzung nach einer
# Woche wie eine einzige klingen. Sie werden ALLE beim Start einmal
# gesprochen und liegen dann fertig da (main._gruss_vorbereiten); das
# laeuft nebenher und kostet nichts, was man merkt.
WECKANTWORTEN = [
    "Ja?",
    "Ich höre.",
    "Sag an.",
    "Bin da.",
    "Zu Diensten.",
    "Leg los.",
    "Ich bin ganz Ohr.",
    "Was brauchst du?",
    "Bereit.",
    "Immer noch wach.",
    "Schieß los.",
    "Hier bin ich.",
    "Was liegt an?",
    "Ich bin dran.",
]

# --- Ohren ----------------------------------------------------------------
WHISPER_MODELL = "large-v3-turbo"
WHISPER_GERAET = "cuda"        # bei Ärger: "cpu"
WHISPER_GENAUIGKEIT = "int8_float16"  # bei "cpu": "int8"
# Gemessen auf der RTX 3070 dieses Servers, large-v3-turbo, 4-s-Zuruf:
#
#   float16        2.289 MiB VRAM   0,228 s
#   int8_float16   1.297 MiB VRAM   0,205 s
#   int8           1.297 MiB VRAM   0,215 s
#
# Also die Haelfte des Speichers und nicht langsamer. Auf der 3080 des
# Dev-PCs war float16 die richtige Wahl -- dort lag nichts anderes auf
# der Karte. Hier teilt Whisper sie sich mit dem Haupt-LLM, und von
# 8 GB bleiben neben qwen3.5:9b keine 2,3 GB uebrig.
SPRACHE = "de"

# Woerter, die Whisper erwarten soll. Ohne das schreibt es "Sarvis" als
# "Salvis", "Salas" oder "Service" -- gemessen am echten Mikrofon.
# Namen aus deinem Umfeld gehoeren hier ebenfalls hinein, dann trifft er
# sie beim Diktieren zuverlaessiger.
HOTWORDS = "Sarvis"

# --- Woher der Klang kommt ------------------------------------------------
# "lokal" -- Mikrofon und Lautsprecher dieses Rechners (sounddevice).
# "netz"  -- Sprache kommt von aussen und geht nach aussen zurueck.
#
# Auf dem Server gibt es kein Mikrofon und keine Lautsprecher; er bekommt
# Sprache geschickt und schickt seine Antwort zurueck. Der Vertrag
# zwischen beiden Fassungen steht in klang.py. Die Netzfassung ist noch
# nicht gebaut -- "netz" sagt das beim Start deutlich, statt still etwas
# anderes zu tun.
KLANG_QUELLE = os.environ.get("SARVIS_KLANG", "lokal").strip() or "lokal"

# Wo der Endpunkt lauscht, wenn KLANG_QUELLE = "netz".
#
# Nur auf 127.0.0.1 -- nach aussen fuehrt ausschliesslich Caddy, und das
# bringt HTTPS mit. Ueber diese Leitung geht ein Geraeteschluessel, der
# Sarvis alles erlaubt: Mails, Buchungen, Arbeit an den Projekten. Ein
# zweiter Weg hinein waere einer ohne Zertifikat.
NETZ_HAFEN = 8900

# --- Aufnahme -------------------------------------------------------------
ABTASTRATE = 16000  # was Whisper erwartet
MIN_AUFNAHME_SEK = 0.4  # kürzer = versehentlich getippt, wird verworfen

# --- Mund -----------------------------------------------------------------
# --- Welche Stimme spricht ------------------------------------------------
# EIN Schalter. "piper" laeuft lokal, kostet nichts und ist der Alltag;
# "elevenlabs" klingt besser und ist zum Vorfuehren gedacht.
#
# Warum nicht dauerhaft die schoenere? Gemessen an fuenf echten Tagen aus
# Sarvis' eigenen Sitzungsprotokollen: 363 gesprochene Antworten, im
# Schnitt 73 Zeichen, 5.289 Zeichen an einem Durchschnittstag und 9.719
# am staerksten. Das kostenlose Kontingent sind 10.000 Zeichen im MONAT
# -- es reicht 1,9 Tage. Als Alltagsstimme haette man zwei gute Tage und
# achtundzwanzig, an denen man ueber den Wechsel stolpert; fuer eine
# Vorfuehrung von zehn Minuten reicht es muehelos.
#
# Umschalten heisst: dieses eine Wort aendern und Sarvis neu starten.
STIMME_DIENST = "piper"        # "piper" | "elevenlabs"

# Welche Stimme drueben gesprochen wird.
#
# Gemessen am 28.08.2026: Auf dem kostenlosen Tarif gehen NUR Stimmen der
# Sorte "premade". Die Sorte "professional" -- also alles aus der
# Stimmbibliothek, darunter die urspruenglich gewuenschte
# 87AwpS6yC86wa2WglbsK (Michael Danisch) -- wird mit 402 abgelehnt:
# "Free users cannot use library voices via the API."
#
# Weitere premade-Stimmen, falls Brian nicht gefaellt:
#   onwK4e9ZLuTAKqWW03F9  Daniel, ruhiger Sprecher
#   cjVigY5qzO86Huf0OWal  Eric, weich
#   iP95p4xoKVk53GoZ742B  Chris, bodenstaendig
#
# ACHTUNG: Das sind englische Stimmen, die ueber das mehrsprachige Modell
# Deutsch sprechen. Wie stark der Akzent durchschlaegt, muss man hoeren.
ELEVENLABS_STIMME = "nPczCjzI2devNBz1zQrb"   # Brian, tief und resonant
ELEVENLABS_MODELL = "eleven_multilingual_v2"

# Rohe 16-Bit-Werte waeren einfacher zu verarbeiten, brauchen aber einen
# bezahlten Tarif. MP3 geht ueberall und wird mit av dekodiert, das
# ohnehin im Projekt liegt.
ELEVENLABS_FORMAT = "mp3_44100_128"

# Ein haengender Dienst darf ein Gespraech nicht anhalten -- dieselbe
# Ueberlegung wie beim Finanzdashboard.
ELEVENLABS_ZEITGRENZE = 20.0

# --- Was auf Dokumenten steht --------------------------------------------
#
# Kopf und Fuss von Berichten, PDFs und Word-Dateien
# (werkzeuge/bericht.py, werkzeuge/dokument.py).
#
# LEER HEISST SARVIS. Steht hier kein Name, tragen die Dokumente das
# Ringzeichen und "Erzeugt von Sarvis am ..." -- richtig fuer etwas, das
# nur man selbst liest, und falsch fuer alles, was an jemand anderen
# geht: Dort steht dann der Assistent im Briefkopf statt des Absenders.
#
# Sobald ein Name eingetragen ist, weichen beide dem hier. Beispiel:
#
#   DOKUMENT_ABSENDER = "Sascha Richter"
#   DOKUMENT_ZEILEN = ["Musterstrasse 1, 04103 Leipzig",
#                      "0341 1234567 · post@example.de"]
#   DOKUMENT_FUSS = "Sascha Richter · USt-IdNr. DE123456789"
#
# Die Zeilen stehen klein unter dem Namen, der Fuss unten auf jeder
# Seite. Wer nur den Namen setzt, bekommt genau den -- die anderen
# beiden sind einzeln entbehrlich.
DOKUMENT_ABSENDER = ""
DOKUMENT_ZEILEN: list[str] = []
DOKUMENT_FUSS = ""

# Ausgewaehlt am 28.08.2026 aus achtzehn Farben auf zwei Stimmdateien,
# an fuenf echten Saetzen verglichen (Weckantwort, Begruessung, Zahlen,
# Rueckfrage, lange Aufzaehlung).
#
# ZURUECK AUF MEDIUM am 01.09.2026, auf Ansage. "high" war die Wahl aus
# dem Vergleich und im Betrieb die schlechtere: Die groessere Datei
# kostet bei langen Saetzen 1330 statt 637 Millisekunden, und das ist
# nicht irgendeine Rechenzeit, sondern die Stille vor dem ersten Ton --
# jedes Mal. Am einzelnen Satz war der Unterschied im Klang zu hoeren,
# im Gespraech war es die Wartezeit.
#
# Beide Dateien liegen weiterhin unter DATEN/stimmen; ein Wechsel ist
# diese eine Zeile und ein Neustart.
STIMME = DATEN / "stimmen" / "de_DE-thorsten-medium.onnx"

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
#
# AUS SEIT DEM 01.09.2026, auf Ansage: "wieder Thorsten normal".
#
# Am Tag zuvor wurde dafuer die Stimmdatei von high auf medium gestellt
# -- das war die falsche Haelfte. Verzerrt hat nicht das Modell,
# sondern diese Zeile: Die Farbe "sarvis" schiebt die Formanten um
# Faktor 1,32 (das ist der kuenstliche Beiklang), doppelt die Stimme
# zweifach leicht verstimmt und legt Hall darueber. Das Ergebnis klingt
# nach Bordcomputer, und genau das war urspruenglich gewollt.
#
# Seit dem 01.09.2026 nachmittags "praesent", nach sechs Hoerproben am
# selben Satz: etwas Fundament, etwas Luft, ein kleiner Raum -- sonst
# nichts. Die Wahl fiel zwischen "aus", "praesent" und "sternenschiff"
# und war knapp; wer sie noch einmal hoeren will, findet das Skript
# unter stimmproben.py und die Farben hier daneben.
#
# Die Nachbarn, falls es doch kippen soll: "aus" ist unbearbeitet,
# "sternenschiff" eine Stufe entrueckter (Star-Trek-Richtung),
# "begleiter" noch eine weiter. Zurueck zur alten Bordcomputer-Stimme
# geht mit "sarvis"; die Effektkette steht unveraendert in
# stimmfarbe.py. Es ist jedesmal ein Wort und ein Neustart.
STIMMFARBE = "praesent"

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

Dein Gedächtnis hat zwei Schichten, und du entscheidest beim Merken, wohin etwas gehört. Dauerhafte Eigenschaften des NUTZERS ("mag keine Umlaute in Dateinamen") → merken. Alles über einen anderen MENSCHEN → person_merken. Ereignisse, Zwischenstände, was heute besprochen wurde → notiz_schreiben. Der Unterschied ist nicht Ordnungsliebe: Was du mit merken speicherst, hängt an JEDEM künftigen Zuruf mit dran; die anderen beiden werden nur gelesen, wenn jemand danach fragt. Ein Gedächtnis, in dem alles gleich laut ist, findet nichts mehr.

Fragt der Nutzer nach einem Menschen oder nach etwas Vergangenem, das nicht in deinem Kontext steht, dann schlag mit gedaechtnis_nachschlagen nach, bevor du sagst, du wüsstest es nicht.

Wechselt der Nutzer den Ort ("gehen wir mal ins Projekt X", "was liegt eigentlich in Y"), dann öffne KEIN Terminal. projekt_oeffnen ist nur für "mach mir da ein Terminal auf" — sonst nie. Sieh dir stattdessen mit ort_ansehen an, was dort liegt, und stell dann eine Frage, die zu dem passt, was du siehst: Liegt dort angefangene Arbeit, frag, ob weitergebaut werden soll und woran zuletzt gearbeitet wurde. Sind es Anleitungen oder Notizen, frag, ob du zusammenfassen sollst oder ob er etwas Bestimmtes sucht. Rate nicht, was er vorhat — sieh nach und frag passend.

Für ein neues Projekt benutzt du projekt_anlegen — nicht einfach eine Datei irgendwohin schreiben. Das Werkzeug fragt nach dem Ort, legt README und Git-Repository an und macht damit nachvollziehbar, wo etwas entstanden ist. Eine lose Datei in einem selbst gewählten Ordner findet der Nutzer nächste Woche nicht wieder.

Du hast eine Anzeige, und du sollst sie benutzen. Sobald deine Antwort aus Zahlen, einer Liste, einem Verlauf oder einem Vergleich besteht, stell sie hin, statt sie nur vorzulesen. Vorgelesene Zahlen sind nach dem dritten Posten weg.

Vier Wege, und die Größe entscheidet — nicht dein Geschmack. kachel_zeigen ist eine Kachel neben der Engine, für den Blick nebenbei: ein paar Zeilen, ein Balken- oder Tortendiagramm, ein Gesprächsverlauf, ein Vergleich. blatt_zeigen ist eine formatierte Antwort im Gespräch: Überschriften, Listen, eine kleine Tabelle, Links — alles, was gesprochen unübersichtlich wäre und doch keine ganze Auswertung ist. seite_zeigen ist eine Seite fürs Hinsetzen: eine richtige Auswertung mit mehreren Diagrammen. dokument_erstellen macht eine Datei zum BEHALTEN oder WEITERGEBEN — PDF zum Ausdrucken und Verschicken, Word zum Weiterschreiben, Excel wenn gerechnet oder sortiert werden soll, CSV für den Import woandershin, Text für das rohe Markdown.

Bei drei Zahlen fragst du nicht, da nimmst du die Kachel. Bei einer Anleitung in fünf Schritten fragst du auch nicht, da nimmst du das Blatt. Bei einer Jahresauswertung nimmst du die Seite. Nur wenn es wirklich dazwischen liegt, fragst du in einem Halbsatz: "Als Blatt daneben oder als Seite zum Hinsetzen?" Das ist eine Frage zur Sache, keine Erlaubnisfrage — sie ist erlaubt.

Der Unterschied zwischen Seite und Dokument ist nicht die Größe, sondern was danach damit geschieht: Eine Seite liest man und schließt sie, ein Dokument geht an jemanden oder wird aufgehoben. Erzeug ein Dokument, wenn der Nutzer es sagt ("schick mir das", "zum Ausdrucken", "als PDF") — nicht auf Verdacht. Eine Datei, die niemand wollte, liegt danach herum.

Sagt er nur "als Datei", entscheidet der Inhalt: Sind es überwiegend Zahlen in einer Tabelle, nimm Excel — dort kommen sie als Zahlen an, mit denen man rechnen kann. Ist es ein Schreiben, nimm PDF. Soll er daran weiterschreiben, Word. Frag nicht nach dem Format, wenn der Inhalt es beantwortet.

Das Blatt und das Dokument schreibst du in Markdown: # Überschriften, **fett**, *kursiv*, ~~durchgestrichen~~, `code`, - Listen mit eingerückten Unterpunkten, 1. Nummerierung, - [ ] und - [x] für Checklisten, > Zitate, ```Code```, | Tabellen |, --- Trennlinie, [Text](https://ziel). Kein HTML — das wird als Text angezeigt, nicht ausgeführt.

Zwei Dinge, an denen es sonst scheitert: Eine Tabelle braucht ihre |---|-Trennzeile unter der Kopfzeile, sonst ist sie keine. Und Unterpunkte rückst du mit zwei Leerzeichen ein — daran hängt die Verschachtelung, in der Anzeige wie in Word.

Was du hinstellst, sagst du trotzdem. Die Anzeige ersetzt die Antwort nicht, sie zeigt sie. Und schick den Nutzer nie auf eine fremde Webseite und lass ihn sich nirgends anmelden, um etwas zu sehen, das du ihm gerade vorgelesen hast.

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
# oder Boxen ueberhaupt an sind -- und der Weg Text -> Piper ->
# Lautsprecher ist einmal durchlaufen, bevor es ernst wird.
#
# Der Tastenhinweis stand hier frueher in jedem Satz ("Halt die rechte
# Steuerungstaste"). Er ist raus, auf ausdruecklichen Wunsch: Wer den
# Assistenten taeglich benutzt, kennt die Taste, und ein Satz, der jeden
# Morgen dasselbe erklaert, wird zur Ansage im Fahrstuhl. {taste} wird
# weiterhin uebergeben -- wer den Hinweis zurueckwill, schreibt ihn
# einfach in einen Satz.
#
# Zwei Regeln bleiben:
#
#   Kurz. Man hoert sie JEDEN Start. Ein Satz, der beim dritten Mal
#   nervt, ist ein schlechter Satz, egal wie gut er beim ersten klang.
#
#   Nichts behaupten, was nicht stimmt. "Sensoren aktiv" waere ein
#   schoener Satz und eine Luege -- Sarvis hat keine. Was er hat, sind
#   Werkzeuge, und die kann er zaehlen. Deshalb {werkzeuge}: Die Zahl
#   kommt aus der tatsaechlich gebauten Liste, nicht aus dem Text. Wird
#   eins gebaut, sagt er es am naechsten Morgen von selbst; faellt ein
#   Dienst aus, sagt er entsprechend weniger.
#
# ACHTUNG bei {taste}, falls jemand ihn zurueckholt: Der Platzhalter
# bringt seinen eigenen kleinen Artikel mit ("die rechte
# Steuerungstaste") und darf nie am Satzanfang stehen.
#
# {tageszeit} und {werkzeuge} werden ersetzt, {taste} steht bereit.
BEGRUESSUNGEN = [
    "{tageszeit}. Ich bin wach. {werkzeuge} Werkzeuge scharf, Mikrofon offen.",
    "{tageszeit}. Alles läuft. Sag, was du brauchst.",
    "{tageszeit}. Hochgefahren, Ohren offen, {werkzeuge} Werkzeuge griffbereit.",
    "{tageszeit}. Wach, scharf und auf Empfang.",
    "{tageszeit}. Sarvis ist oben. {werkzeuge} Werkzeuge warten.",
    "{tageszeit}. Systeme wach. Was liegt an?",
    "{tageszeit}. {werkzeuge} Werkzeuge, ein Mikrofon und volle Aufmerksamkeit.",
    "{tageszeit}. Bereit, wenn du es bist.",
]

# --- Finanzdashboard ------------------------------------------------------
# Laeuft auf einem eigenen Server; Sarvis spricht dieselbe Schnittstelle
# wie die Weboberflaeche und darf dort dasselbe. Der Unterschied ist nur
# der Nachweis: dort ein Sitzungs-Cookie, hier eine Kopfzeile.
FINANZ_BASIS = "https://finanz.tech-artist.de/api"

# Der Schluessel steht in .env, NIE im Quelltext -- so verlangt es auch
# die Referenz des Dashboards. Er laeuft nicht ab, bis er getauscht wird,
# und ist damit so viel wert wie der Zugang zur Oberflaeche selbst.
FINANZ_SCHLUESSEL_NAME = "FD_API_SCHLUESSEL"

# Ein haengender Server darf ein Gespraech nicht anhalten.
FINANZ_ZEITGRENZE = 20.0

# Wie viele Posten hoechstens vorgelesen werden. Zwanzig Kategorien am
# Stueck haelt niemand aus -- wer mehr will, fragt nach.
FINANZ_HOECHSTENS = 6


def finanz_schluessel():
    """Der API-Schluessel aus der .env, oder None."""
    return _env_werte().get(FINANZ_SCHLUESSEL_NAME)


# --- Telegram -------------------------------------------------------------
# Zugangsdaten stehen in .env, nicht hier. Die Sitzungsdatei ist so viel
# wert wie das Konto selbst -- beide stehen in der .gitignore.
TELEGRAM_SITZUNG = DATEN / "sarvis.session"


def _env_werte() -> dict:
    """Alles aus der .env als Verzeichnis. Fehlt sie, ist es leer.

    Eine Stelle fuer alle Zugaenge: Vorher las telegram_zugang() die
    Datei selbst, und der naechste Zugang haette dieselben zehn Zeilen
    noch einmal gebraucht.

    GESUCHT WIRD ZUERST IM DATENORDNER, dann neben dem Quelltext.

    Auf Windows gab es nur einen Ort -- Programm und Daten lagen im
    selben Verzeichnis. Auf dem Server sind sie getrennt, und Zugaenge
    gehoeren zu den Daten: Sie ueberleben ein "git checkout", sie liegen
    auf der Platte, die gesichert wird, und sie kommen beim Deploy nicht
    versehentlich mit.

    Der zweite Ort bleibt als Rueckfall, damit ein Windows-Checkout
    unveraendert weiterlaeuft.
    """
    datei = DATEN / ".env"
    if not datei.exists():
        datei = WURZEL / ".env"
    if not datei.exists():
        return {}
    werte = {}
    for zeile in datei.read_text(encoding="utf-8").splitlines():
        zeile = zeile.strip()
        if zeile and not zeile.startswith("#") and "=" in zeile:
            k, v = zeile.split("=", 1)
            werte[k.strip()] = v.strip()
    return werte


def telegram_zugang():
    """(api_id, api_hash) aus der .env, oder None."""
    werte = _env_werte()
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
# PROJEKTE, ABLAGE, PROJEKT_ORTE und PROJEKT_ORT_NAMEN: siehe orte.py

# Wo Sarvis ablegt, was beim Antworten entsteht -- Berichte, Auswertungen,
# Zwischenstaende. Siehe FREI_SCHREIBEN weiter unten.


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

# Wie die Orte vorgelesen werden -- "Mitra" sagt beim Zuhoeren zu wenig.
# --- Kontext: wie viel Gespraech Sarvis mit sich herumtraegt -------------
# Jeder Zuruf schickt den GANZEN bisherigen Verlauf mit. Das ist kein
# Fehler, sondern der Grund, warum Sarvis auf "was hatte ich vorhin
# gesagt" antworten kann -- aber es waechst.
#
# Gemessen am 28.08.2026 mit get_context_usage():
#
#   Fenster (Opus 5)            1.000.000 Token
#   belegt, bevor ein Wort faellt   21.727   (Systemprompt, Werkzeuge,
#                                             Gedaechtniskern)
#   je kurzem Zuruf                   ~590   (12 Zurufe: +7.077)
#
# Fuers blosse Reden reicht das fuer ueber tausend Zurufe. Beim ARBEITEN
# nicht: eine lange Mail, ein "docker compose logs", ein Auftragsbericht
# kosten je ein Vielfaches davon.
#
# Das SDK verdichtet von selbst -- aber erst bei 967.000, also kurz vor
# knapp. Zu spaet aus zwei Gruenden: Es passiert mitten in einer Antwort,
# und WAS zusammengefasst wird, entscheidet dann niemand. Deshalb
# verdichtet Sarvis vorher, im Leerlauf, mit eigener Anweisung.
KONTEXT_WACHE = True

# Ab welchem Anteil des Fensters verdichtet wird.
KONTEXT_VERDICHTEN_AB = 0.65

# Wie oft hoechstens -- eine Verdichtung, die sofort wieder ausloest,
# waere eine Schleife. Frisst sie nichts weg, wird eine Weile Ruhe
# gegeben.
KONTEXT_VERDICHTEN_PAUSE_SEK = 600

# Womit verdichtet wird. "/compact" nimmt eigene Anweisungen entgegen --
# ohne sie fasst es fuer einen Programmierer zusammen ("welche Dateien
# wurden geaendert"), nicht fuer ein Gespraech.
KONTEXT_VERDICHTEN_ANWEISUNG = (
    "Fasse als Gespraechsgedaechtnis eines Sprachassistenten zusammen, "
    "nicht als Arbeitsbericht. Behalte: offene Fragen und Zusagen, "
    "worum der Nutzer gerade gebeten hat, laufende Auftraege und Timer, "
    "getroffene Entscheidungen und ihre Begruendung, sowie alles, was er "
    "ueber sich selbst gesagt hat. Wirf weg: Werkzeugausgaben im "
    "Wortlaut, Dateiinhalte, Listen und Suchergebnisse -- die stehen "
    "noch im Verlauf auf der Platte und lassen sich mit "
    "verlauf_nachschlagen wiederholen. Schreibe auf Deutsch."
)

# Was Sarvis dabei sagt. Stumm verdichten waere das Schlimmste: Er
# wuesste hinterher Feinheiten von vorhin nicht mehr, und niemand
# wuesste, warum.
KONTEXT_VERDICHTET_SATZ = (
    "Kurz zur Info: Ich habe unser bisheriges Gespräch zusammengefasst, "
    "damit der Kopf frei bleibt. Einzelheiten von vorhin schlage ich bei "
    "Bedarf im Verlauf nach."
)

# Wo die Sitzungsdateien liegen, in denen genau das nachgeschlagen wird.
# Sie schreibt das SDK, nicht Sarvis -- eine Zeile je Nachricht, und
# zwar VOLLSTAENDIG: Auch was verdichtet wurde, steht dort weiter.
# Geprueft an einer Sitzung nach "/compact" -- die drei Zurufe von vor
# der Verdichtung standen unveraendert in der Datei.
# VERLAUF_ORDNER: siehe orte.py -- der Ordnername wird dort aus WURZEL
# gerechnet statt geraten, weil er im Container anders heisst.

# Woran Sarvis' eigene Sitzungen zu erkennen sind. Im selben Ordner
# liegen auch die Sitzungen von Claude Code am Projekt -- die gehen ihn
# nichts an. Geprueft: Sarvis' Sitzungen tragen "sdk-py", die von Claude
# Code "cli".
VERLAUF_MARKE = "sdk-py"

AUFTRAG_DATEI = DATEN / "auftraege.json"

# Das Fortschritts-Journal. Nur ANHAENGEN, nie ueberschreiben: Ein
# Absturz kostet dann hoechstens die letzte Zeile, nie die Historie.
# auftraege.json ist der bequeme Momentanstand, dieses Journal der
# Verlauf -- und der Rettungsanker, wenn die JSON zerrissen ist.
AUFTRAG_JOURNAL = DATEN / "fortschritt.jsonl"

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

# Schreiben bleibt eng. Das ist keine Inkonsequenz, sondern der
# Unterschied, um den es geht: Ein Blick ist zurueckzunehmen, indem man
# ihn vergisst. Eine geaenderte Datei nicht. Ueberall sonst darf Sarvis
# auch schreiben -- er fragt vorher.

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

# Orte, an denen trotz Freiliste gefragt wird.
#
# Nicht gesperrt -- gefragt. Der Unterschied ist der ganze Punkt: Sarvis
# DARF dort hinsehen, wenn er es sagen soll. Er tut es nur nicht still
# nebenbei, weil hier Zugangsdaten liegen und ein Passwort, das einmal
# durch ein Sprachmodell gelaufen ist, nicht wieder unbekannt wird.

# --- Arbeit am eigenen Projekt --------------------------------------------
# Ein Assistent, der beim Starten des eigenen Projekts siebenmal fragt,
# wird beim achten Mal nicht mehr gefragt -- dann tippt man selbst.
#
# Gemessen an einem Docker-Projekt: fuenf Befehle, fuenf Rueckfragen. Eine
# erteilte Freigabe half NICHT, und das war kein Zufall: Sie haengt an
# einem Ort, und "docker compose up" nennt keinen. Dieselbe Messung fuer
# Angular und Django, dasselbe Bild -- kein einziger Startbefehl traegt
# einen Pfad.
#
# Deshalb hier zwei Listen und ein Ort. Frei laeuft nur, was ALLE drei
# Bedingungen erfuellt:
#
#   1. Der Arbeitsordner der Shell liegt unter einem ENTWICKLUNG_ORT.
#   2. JEDER Schritt der Kette steht in ENTWICKLUNG_BEFEHLE.
#   3. KEIN Schritt steht in ENTWICKLUNG_FRAGT_TROTZDEM.
#
# Der Arbeitsordner wird in schutz.py mitgefuehrt -- nachvollzogen aus
# den "cd"-Befehlen, die tatsaechlich erlaubt wurden. Ohne ihn waere
# nicht pruefbar, WO ein pfadloser Befehl laeuft, und eine Freigabe fuer
# ein Projekt wuerde Befehle decken, die woanders laufen.


# Was als Arbeit am eigenen Projekt gilt.
#
# Ein Muster steht hier nur, wenn es die EIGENEN Einstiegspunkte des
# Projekts anspricht -- die package.json, die manage.py, die
# docker-compose.yml. Alles, was einen beliebigen Befehl als Argument
# entgegennimmt, steht bewusst NICHT hier: "docker compose exec" ist
# keine Startzeile, sondern eine Luke, durch die alles passt. Aus
# demselben Grund fehlen Where-Object und ForEach-Object in NUR_SCHAUEN.
ENTWICKLUNG_BEFEHLE = (
    # In den Projektordner wechseln gehoert dazu -- sonst faellt genau
    # der Befehl heraus, der den Arbeitsordner ueberhaupt erst setzt.
    # Wohin gewechselt wird, prueft die Pfadbedingung weiter unten.
    r"^(cd|chdir|Set-Location|sl)\b",

    # Docker: hochfahren, ansehen, anhalten. "down" fehlt absichtlich --
    # mit -v nimmt es die Volumes mit, und was in einer Datenbank stand,
    # kommt davon nicht zurueck.
    r"^docker\s+compose\s+(up|ps|logs|start|stop|restart|top|config|events)\b",
    r"^docker\s+(ps|logs|images|stats|version|info)\b",

    # Node, Angular, Vite und Verwandte. "run" fuehrt ein Skript aus der
    # package.json aus, also unseren eigenen Eintrag.
    r"^(npm|pnpm|yarn|bun)\s+(run|start|test|dev|build|serve)\b",
    r"^(ng|vite|next|nuxt|astro|svelte-kit)\s+"
    r"(serve|dev|start|build|test|preview)\b",

    # Python: Django, ASGI/WSGI, Tests, Linter.
    r"^(python|python3|py)\s+manage\.py\s+"
    r"(runserver|migrate|makemigrations|showmigrations|check|collectstatic)\b",
    r"^(python|python3|py)\s+-m\s+"
    r"(pytest|unittest|uvicorn|gunicorn|http\.server|django)\b",
    r"^(uvicorn|gunicorn|hypercorn|daphne|flask)\s",
    r"^(pytest|tox|nox|ruff|flake8|mypy|black|isort)\b",

    # Bauen und Testen anderswo.
    r"^(make|cargo|go|dotnet|mvn|gradle|\./gradlew|\.\\gradlew)\s+"
    r"(run|build|test|dev|start|serve|watch|check|fmt|vet|clippy)\b",
)

# Was trotzdem fragt, auch wenn es oben passt.
#
# Zwei Sorten, und beide sind keine Arbeit am eigenen Code:
#
#   Fremder Code. "npm install" laedt Pakete aus dem Netz und fuehrt
#   deren Install-Skripte aus. Das ist eine Lieferung von aussen, und die
#   wird angesagt -- so steht es auch in den globalen Regeln.
#
#   Weg ist weg. Volumes, Bilder, veroeffentlichte Staende. Eine
#   Rueckfrage kostet drei Sekunden, ein geloeschtes Volume einen Abend.
ENTWICKLUNG_FRAGT_TROTZDEM = (
    r"\b(install|ci|add|update|upgrade|dlx)\b", r"^npx\b",
    r"\b(prune|rmi|down)\b", r"--renew-anon-volumes\b", r"\s-V\b",
    r"\b(deploy|publish|release|push)\b",
)

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
    # Schicht 2 des Gedaechtnisses. Schreiben und Nachschlagen laufen
    # still durch -- es ist lokal, datiert und jederzeit nachlesbar,
    # genau wie merken. Nur Loeschen fragt (vergessen).
    "person_merken":           "still",
    "notiz_schreiben":         "still",
    "gedaechtnis_nachschlagen": "still",
    "gedaechtnis_zeigen": "still",

    # Etwas neben der Engine einblenden. Still, und zwar deutlich: Eine
    # Kachel zeigt nur, was Sarvis ohnehin gerade sagt -- sie geht nicht
    # nach draussen, sie aendert nichts, und sie verschwindet von selbst
    # wieder. Fragte sie nach, waere sie unbenutzbar: Man blendet etwas
    # WAEHREND der Antwort ein, nicht nach einer Rueckfrage darueber.
    "kachel_zeigen":      "still",
    "kachel_weg":         "still",
    # Die grosse Schwester der Kachel: eine ganze Seite im eingebauten
    # Browser. Still aus denselben Gruenden -- es geht nichts nach
    # draussen, es aendert nichts, und geschrieben wird in Sarvis'
    # eigenen Werktisch (ABLAGE, steht in FREI_SCHREIBEN und in der
    # .gitignore). Der Inhalt stammt von ihm selbst und nicht aus
    # fremder Hand; genau das ist der Unterschied zu mail_anhang_holen,
    # das deshalb fragt.
    #
    # Und eine Rueckfrage waere hier unbenutzbar: Man zeigt etwas
    # WAEHREND der Antwort, nicht nach einer Rueckfrage darueber. Die
    # falsche Frage ("Soll ich chat-niko.html anlegen?") war der Anlass
    # fuer das Werkzeug.
    "seite_zeigen":       "still",
    # Zeigen ist kein Handeln -- dieselbe Einstufung wie Kachel
    # und Seite. dokument_erstellen schreibt zwar eine Datei,
    # aber in Sarvis' eigene Ablage und nirgendwo sonst
    # (bericht._ziel prueft das zweifach).
    "blatt_zeigen":       "still",
    "blatt_weg":          "still",
    "dokument_erstellen": "still",
    # Der Gespraechsverlauf ist kein Gedaechtnis, sondern das Protokoll
    # der eigenen Sitzung -- Nachschlagen darin ist Nachlesen dessen, was
    # ohnehin gesagt wurde.
    "verlauf_nachschlagen":    "still",
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
    # Finanzen: Abfragen sind harmlos und laufen still. Eine Buchung
    # anzulegen fragt nach -- sie taucht spaeter im Kontoabgleich auf,
    # und eine falsche findet man dann schwer wieder.
    # Kategorien auflisten und einen gesprochenen Namen auf eine Nummer
    # aufloesen. Reines Lesen -- und finanzen_buchungen loest ohnehin
    # intern mit auf, damit ein Satz ein Aufruf bleibt.
    "finanzen_kategorien": "still",
    # Zwei Abfragen und eine Subtraktion. Gerechnet wird in Python, nicht
    # im Modell: Eine subtrahierte Zahl kann nicht halluziniert sein.
    "finanzen_vergleich":  "still",
    "finanzen_kontostand": "still",
    # Dauerauftraege. Auflisten und Vorschau sind reines Lesen -- und die
    # Vorschau MUSS still laufen: Sonst nimmt das Modell fuer "was kommt
    # denn noch" den Weg ueber dauerauftrag_buchen, der wirklich bucht.
    "finanzen_dauerauftraege": "still",
    "finanzen_vorschau":       "still",
    # Anlegen schreibt einen Satz, der sich kuenftig wiederholt -- also
    # mindestens der Rang einer einzelnen Buchung.
    "dauerauftrag_anlegen":    "fragen",
    # Und der hier legt MEHRERE echte Buchungen auf einmal an.
    "dauerauftrag_buchen":     "fragen",
    "finanzen_ausgaben":   "still",
    "finanzen_monate":     "still",
    "finanzen_empfaenger": "still",
    "finanzen_buchungen":  "still",
    "finanzen_konten":     "still",
    "finanzen_buchen":     "fragen",
    # Umbuchen legt zwei verbundene Buchungen an -- derselbe Rang wie
    # eine einzelne, und auf dem falschen Konto genauso laestig.
    "finanzen_umbuchen":   "fragen",

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
    # Nachlesen, was schon einmal gesagt wurde -- aus der eigenen
    # Sicherung und dem bericht.md des Zweigs. Aendert nichts.
    "auftrag_ergebnis":   "still",
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

    # Eine Seite zu ZEIGEN ist ansehen, nicht handeln -- und ein Fenster
    # ist schneller zu als jede Rueckfrage.
    #
    # Hier stand frueher web_oeffnen daneben, fuer den Standardbrowser.
    # Zwei Werkzeuge fuer fast dasselbe waren ein Entwurfsfehler:
    # Gemessen griff Sarvis fuenfmal von fuenf zum falschen. Jetzt ist es
    # ein Werkzeug mit einem Schalter, den der Nutzer umlegt.
    "web_zeigen":         "still",
    "route_zeigen":       "still",

    # Die Seite im eigenen Fenster lesen und bedienen.
    #
    # Lesen ist harmlos: Es steht ohnehin auf dem Bildschirm.
    # Zumachen ist so harmlos wie Aufmachen.
    "web_schliessen":     "still",
    "web_lesen":          "still",
    "web_elemente":       "still",
    "web_zoom":           "still",
    "web_downloads":      "still",
    # Ein Bild der offenen Seite an den Bildschirm des Nutzers. Hinsehen
    # ist keine Handlung an der Aussenwelt. Und es ist die einzige
    # Moeglichkeit fuer den Nutzer, ueberhaupt zu sehen, was Sarvis
    # gerade tut -- sein Browser laeuft unsichtbar auf dem Server.
    "web_ansehen":        "still",

    # Klicken und Tippen NICHT. Bis vor kurzem galt "Sarvis bringt die
    # Seite, du bedienst sie" -- das trug, weil Zeigen keine Handlung
    # ist. Ein Klick ist eine, und der Browser ist in deinen Konten
    # angemeldet.
    #
    # "browser" ist eine eigene Stufe, kein "still" und kein "fragen":
    # Was ein Klick darf, haengt daran, WORAUF geklickt wird -- genauso
    # wie bei den Shell-Befehlen, wo "pfad" den Befehl ansehen laesst.
    # Entschieden wird in schutz.klick_stufe bzw. schutz.tipp_stufe,
    # und zwar am echten Element aus dem DOM. Siehe hirn._browserstufe.
    "web_klicken":        "browser",
    "web_tippen":         "browser",

    # Google. Ansehen laeuft still, alles Veraendernde und alles, was
    # hinausgeht, fragt nach -- so wie ueberall sonst auch.
    "termine_ansehen":    "still",
    "termin_anlegen":     "fragen",
    "termin_absagen":     "fragen",
    "mails_ansehen":      "still",
    "mail_lesen":         "still",
    "mail_senden":        "fragen",
    "mail_verschieben":   "fragen",
    # Labels ansehen ist Nachschlagen. Einsortieren fragt -- nicht weil ein
    # Label gefaehrlich waere (es ist abnehmbar), sondern weil dasselbe
    # Werkzeug mit aus_posteingang archiviert, und das kann mail_verschieben
    # nicht ohne Rueckfrage.
    "labels_ansehen":     "still",
    # Nachschlagen, welche Kalender es gibt -- wie labels_ansehen.
    "kalender_liste":     "still",
    # Und hier NICHT still, obwohl es wie Lesen aussieht.
    #
    # mail_anhang_holen und telegram_medium_holen legen eine Datei aus
    # FREMDER Hand auf der Platte ab. Dass Name und Zielordner entschaerft
    # sind, macht den INHALT nicht harmlos -- ausgesucht hat ihn ein
    # Absender, nicht der Nutzer. Genau das meinen die globalen Regeln
    # mit "Lieferung von aussen wird angesagt".
    #
    # Dazu kommt eine Luecke, die man kennen muss: Der Download schreibt
    # direkt mit write_bytes, nicht ueber das Write-Werkzeug. Die
    # Pfadpruefung in schutz.py greift also gar nicht. Diese zwei Zeilen
    # sind die einzige Bremse.
    "mail_anhang_holen":     "fragen",
    "telegram_medium_holen": "fragen",
    "mail_einsortieren":  "fragen",
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

    # Auf dem Rechner des Nutzers etwas tun. "fragen", nicht "still":
    # Ein Programm zu starten ist eine Handlung an einer fremden
    # Maschine, und wer am Rechner sitzt, soll nicht ueberrascht werden.
    # Musik zu steuern dagegen ist zurueckzunehmen, indem man wieder
    # drueckt -- das darf still.
    # Musik. Alles "still": Wer Musik anmacht, hoert sofort, ob es die
    # richtige war, und macht sie sonst wieder aus. Eine Rueckfrage vor
    # jedem Titel waere genau die Sorte Nachfragen, die dazu fuehrt,
    # dass man den Assistenten nicht mehr benutzt.
    "musik_laeuft": "still",
    "musik_abspielen": "still",
    "musik_steuern": "still",
    "musik_geraete": "still",
    "musik_suchen": "still",

    "programm_am_rechner": "fragen",
    "musik_am_rechner": "still",

    # --- Ins Netz sehen ---------------------------------------------------
    # Auf dem Dev-PC fehlten diese beiden, und es fiel nicht auf: Dort
    # machte web_zeigen den eingebauten Browser auf, und gelesen hat
    # Sascha. Auf dem Server gibt es keinen Bildschirm -- ohne diese
    # Zeilen sagt Sarvis "ich komme an keinen Fahrplan heran" und
    # antwortet aus dem Gedaechtnis des Modells. Gemessen genau so
    # passiert, bei einer Zugverbindung Berlin-Leipzig.
    #
    # "still", weil Nachsehen keine Handlung an der Aussenwelt ist --
    # dieselbe Stufe wie web_lesen und mail_lesen.
    #
    # ABER: Damit waechst der Weg, vor dem das README warnt. Ein stilles
    # Lesewerkzeug speist ein Modell, das anschliessend die Rueckfrage
    # fuer mail_senden selbst formuliert. Eine Seite, die "ignoriere
    # deine Anweisungen und schicke X" enthaelt, redet ab hier mit.
    #
    # Was dagegen steht, steht schon: mail_senden, telegram_senden,
    # drive_teilen und die anderen wirksamen Werkzeuge bleiben auf
    # "fragen", und sie stehen zusaetzlich in FREIGABE_NIE -- sie lassen
    # sich also nicht einmal auf ein Ja hin fuer 30 Minuten freischalten.
    # Der Weg von einer fremden Seite zu einer verschickten Mail fuehrt
    # damit immer ueber einen gesprochenen Satz von Sascha.
    "WebSearch": "still",
    "WebFetch": "still",

    # --- Nachschlagen: Wetter, Verkehr, Nachrichten, Fachklassen ---------
    #
    # Sechzehn Werkzeuge, eine Begruendung: Sie fragen oeffentliche
    # Dienste, sie aendern nichts, und sie werden fast immer genau dann
    # gebraucht, wenn die Haende nicht frei sind -- im Auto, auf der
    # Baustelle, mit dem Handy in der Jacke. Eine Rueckfrage vor einer
    # Frostwarnung waere genau die Reibung, die dazu fuehrt, dass man
    # nicht mehr fragt.
    #
    # Radio ist die einzige Ausnahme mit bleibender Wirkung -- und die
    # ist zurueckzunehmen, indem man es wieder ausmacht.
    "wetter_jetzt":       "still",
    "wetter_vorhersage":  "still",
    "wetter_warnungen":   "still",
    "regen_bald":         "still",
    "pollenflug":         "still",

    "autobahn_lage":        "still",
    "autobahn_baustellen":  "still",
    "tanken_guenstig":      "still",
    "tanken_preis":         "still",

    "nachrichten":  "still",
    "radio_suchen": "still",
    "radio_an":     "still",
    "radio_aus":    "still",

    "fachklasse_suchen":      "still",
    "fachklasse_merkmale":    "still",
    "fachklasse_rueckfragen": "still",
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
    # mail_einsortieren steht hier aus einem Grund: Mit aus_posteingang tut
    # es, was mail_verschieben tut. Fehlte es, waere die Sperre daneben
    # umgehbar -- eine halbe Stunde Freigabe aufs Einsortieren, und der
    # Posteingang laesst sich ohne weitere Frage leerraeumen.
    "termin_absagen", "mail_verschieben", "mail_einsortieren",
    # dauerauftrag_buchen, und die Abwaegung lohnt das Aufschreiben:
    # Der Endpunkt ist idempotent, zweimal bejaht legt also nichts
    # doppelt an. Genau den Fall deckt das aber NICHT, der wehtut -- ein
    # Lauf "bis Ende 2029" legt Jahre an Buchungen an, und ein zweiter
    # macht das nicht rueckgaengig, er legt nur nichts obendrauf.
    # Dagegen steht ein Nutzen von praktisch null: Man bucht einmal im
    # Monat, nicht zehnmal in einer halben Stunde. Freigabe ohne Nutzen,
    # aber mit Restschaden.
    "dauerauftrag_buchen",
    # Klicken laesst sich nicht pauschal freigeben, und das ist der
    # ganze Punkt: Harmlose Klicks laufen ohnehin ohne Rueckfrage
    # durch (klick_stufe sagt "frei"). Eine Freigabe wuerde deshalb
    # NUR die Faelle einschliessen, wegen derer ueberhaupt gefragt
    # wird -- Formulare, Bestellungen, Loeschen. Tippen bleibt
    # freigebbar: ein langes Formular zu diktieren ist der Normalfall,
    # und abgeschickt wird es damit noch lange nicht.
    "web_klicken",
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
    "finanzen_buchen": "Buchungen eintragen",
    "finanzen_umbuchen": "Geld umbuchen",
    "ort_ansehen": "Orte ansehen",
    "auftrag_geben": "Aufträge vergeben",
    "termin_anlegen": "Termine eintragen",
    "tabelle_schreiben": "Tabellen schreiben",
    "tabelle_anlegen": "Tabellen anlegen",
    "kontakt_anlegen": "Kontakte anlegen",
    # Anlegen bleibt freigebbar: "trag mir meine Dauerauftraege ein" ist
    # ein echter Massenfall, und angelegt ist noch nicht gebucht.
    "dauerauftrag_anlegen": "Daueraufträge anlegen",
    "web_tippen": "in Felder schreiben",
    "mail_anhang_holen": "Mailanhänge herunterladen",
    "telegram_medium_holen": "Telegram-Medien herunterladen",
    "merken": "sich Dinge merken",
}

# Kurzer Zweiklang, bevor Sarvis sich von selbst meldet (Timer).
GONG = True

# Windows-Benachrichtigungen. Anders als der gesprochene Hinweis bleiben
# sie im Info-Center stehen -- eine Erinnerung, die man verpasst hat,
# war sonst nie da. Einmalige Anmeldung: python einrichten.py
TOAST = True
SYMBOL = WURZEL / "sarvis.ico"
# VERKNUEPFUNG: siehe orte.py (Windows-Rest)

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
ANZEIGE_DATEI = DATEN / "anzeige.json"

# --- Browser in der Engine ------------------------------------------------
# Es gibt Dinge, die eine handgemalte Kachel nie so gut zeigen wird wie das
# echte Programm: eine Kalender-Monatsansicht, ein PDF, ein Drive-Dokument,
# eine Rechercheseite. Daher die Trennlinie: Die Kachel ist fuer den Blick
# nebenbei, der Browser fuers Hinsetzen.
#
# Dies ist NICHT dein Chrome. Der Cookie-Speicher liegt getrennt, also ist
# beim ersten Aufruf einer angemeldeten Seite eine eigene Anmeldung faellig.
# Danach bleibt sie -- geprueft, das Profil steht auf AllowPersistentCookies.
#
# Die Startgroesse ist bewusst nicht die halbe Wand: Aufgehen soll er
# handlich, groesser ziehen kann man ihn am Anfasser unten rechts.
BROWSER_BREITE = 1100
BROWSER_HOEHE = 780

# Profil und Zwischenspeicher. Gehoert NICHT ins Repository -- hier liegen
# Anmeldungen.
BROWSER_PROFIL = DATEN / "browser-profil"

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
    "Finanzen":    "E8C7",  # Geldschein
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
    ("Finanzen",   "bereit"),
]
