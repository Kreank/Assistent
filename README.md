# Sarvis

Ein privater Sprachassistent für den eigenen PC. „Hey Sarvis" rufen oder
eine Taste halten, reden, Antwort hören.

**Was steht:** die geschlossene Schleife — Ohren, Hirn, Mund — dazu die
Anzeige, das Weckwort, das Gedächtnis, die gesprochenen Rückfragen und
**41 eigene Werkzeuge**: Timer, Telegram, Google (Kalender, Mail,
Aufgaben, Kontakte, Drive, Tabellen), Programme und Medien, Dateien,
Projekte und Hintergrundaufträge.

## Starten

Doppelklick auf `starten.bat` — oder:

```
.venv\Scripts\python.exe -m sarvis.main
```

Dann **rechte Strg-Taste gedrückt halten**, reden, loslassen. Strg+C beendet.

Beim Start meldet sich Sarvis gesprochen — daran hörst du sofort, ob
Headset oder Boxen überhaupt an sind, und der ganze Weg Text → Piper →
Lautsprecher ist einmal durchlaufen, bevor es ernst wird.

Die Anzeige startet automatisch mit. Sie ist klick-durchlässig — du kannst
durch sie hindurch arbeiten — und ist im Ruhezustand auf 80 % zurückgenommen.
Abschalten über `ANZEIGE = False` in `sarvis/config.py`.

### Warum die rechte Strg-Taste

Sie tut allein **gar nichts**. F10 aktiviert in vielen Programmen die
Menüleiste, Alt erst recht — und wer Alt hält, während er redet, macht aus
jedem Streifen von Tab oder F4 eine Tastenkombination. Deshalb ist Strg
auch in Discord und TeamSpeak der übliche Push-to-talk-Knopf.

Andere Taste? Eine Zeile in `sarvis/config.py`. Die Begrüßung sagt sie
danach automatisch richtig an — „die rechte Steuerungstaste", nicht
„ctrl underscore r".

**Die Taste wird nicht abgefangen.** Sarvis hängt einen systemweiten
Tastaturhaken ein, hört also auch bei minimierter Konsole mit; das
Vordergrundprogramm bekommt den Tastendruck aber trotzdem. Bei der rechten
Strg-Taste ist das folgenlos, bei F10 oder Alt wäre es das nicht.
Ausnahme: Hat ein Programm mit Administratorrechten den Fokus, blockiert
Windows den Haken.

## Weckwort

Neben der Taste hört Sarvis dauerhaft mit. **„Hey Sarvis, wie spät ist
es?" ist *ein* Satz** — kein Aufwachen, kein Piepen, kein zweites Mal
sprechen. Was hinter dem Namen steht, ist schon der Auftrag.

Abschalten über `WECKWORT_AN = False` in `sarvis/config.py`.

### Warum nicht openWakeWord

Dessen Fertigmodelle sind auf englische Aussprache trainiert. Gemessen
mit unserer deutschen Stimme: „Hey Sarvis" erreichte **0,09 bis 0,13**,
selbst „Hey Jarvis" nur 0,45. Unbrauchbar.

Stattdessen die Kette, die ohnehin schon läuft:

```
Silero-VAD (CPU, billig)    redet überhaupt jemand?
      ↓ nur dann
Whisper (GPU)               was wurde gesagt?
      ↓
Fängt es mit dem Namen an?  dann ist der Rest der Auftrag
```

Solange niemand spricht, rechnet **nur der VAD**. Whisper rührt sich
nicht, und der Ton verlässt den Rechner nie.

### Verglichen wird Ähnlichkeit, nicht Gleichheit

Whisper verhört den Namen zuverlässig. Gemessene Ähnlichkeit zu
„sarvis":

| erkannt | | | |
|---|---|---|---|
| sarvis 1,00 | jarvis 0,83 | charvis 0,77 | sabis 0,73 |
| servus 0,67 | service 0,62 | serviert 0,57 | server 0,50 |

Die Schwelle steht auf **0,60** (`WECKWORT_AEHNLICHKEIT`) und trennt
damit genau zwischen Verhörern und normalen Wörtern — „alex" liegt bei
0,20.

Davor darf eine Anrede stehen: hey, hallo, he, ey, ok, sag, yo und
einige mehr. „hi" und „hai" stehen mit in der Liste, weil Whisper
gesprochenes „hey" oft so schreibt.

### Nachhören

Nach einer Antwort hört Sarvis **18 Sekunden** weiter zu, ohne dass man
den Namen wiederholt (`NACHHOEREN_SEK`). Ohne das müsste man „Hey
Sarvis" auch vor die Antwort auf seine eigene Rückfrage setzen.

Wird nur der Name gerufen, ohne Auftrag, kommt eine feste kurze Antwort
— „Ja?", „Ich höre." Die wird beim Start **einmal vorproduziert** und
liegt dann fertig da: Ein Assistent, der beim Wecken erst nachdenkt,
wirkt träge, und für zwei Wörter lohnt keine Runde zu Claude.

### Eine Falle, die zehn Sekunden kostete

Der VAD meldete im Test **0,91 bei leerem Pegelbalken**. Dadurch endete
der Sprachabschnitt nie und Whisper lief erst nach zehn Sekunden.
Deshalb steht neben dem VAD eine zweite Meinung — `WECKWORT_MIN_PEGEL`.
Wer nichts hört, redet auch nicht.

## Wie es läuft

| Teil | Was | Wo |
|---|---|---|
| Ohren | faster-whisper `large-v3-turbo` | lokal, RTX 3080 |
| Hirn | Claude Opus 5 über das Agent SDK | Claude-Code-Anmeldung |
| Mund | Piper, Stimme `de_DE-thorsten-high` | lokal, CPU |

Kein ElevenLabs, kein API-Key, keine Cloud für Sprache — nur der Text der
Frage und der Antwort verlässt den Rechner.

### Zwei Entscheidungen, die das Tempo machen

**Eine dauerhaft offene Claude-Sitzung.** Ein Prozess pro Zuruf kostet
gemessen 5,0 s Startzeit (2,6 s ohne MCP-Server). Die Sitzung zahlt das
einmal beim Hochfahren, danach nur noch die Antwort.

**Satzweises Vorlesen.** Piper bekommt den ersten Satz, sobald er fertig
ist, statt auf die ganze Antwort zu warten. Das ist der Unterschied
zwischen „fühlt sich an wie reden" und „fühlt sich an wie ein Formular".

## Gemessen

Ganze Kette, ohne Mikrofon: Piper spricht einen Satz, Whisper hört ihn,
Claude antwortet (`messen.bat`).

| Zuruf | Audio | Whisper | 1. Wort | **1. Ton** |
|---|---|---|---|---|
| Zahnarzttermin eintragen | 4,1 s | 0,32 s | 1,93 s | **2,02 s** |
| Wetter morgen in Hamburg | 2,3 s | 0,15 s | 1,16 s | **1,22 s** |
| Nachricht an Anna | 3,5 s | 0,24 s | 0,96 s | **1,07 s** |

Der erste Durchlauf ist immer der langsamste. Hochfahren: rund 5 s.

## Zwei Dinge, die nicht offensichtlich sind

**Der Uhrzeit-Vorspann.** Die Sitzung kennt beim Verbinden ein Datum, aber
keine laufende Uhr — auf „wie spät ist es" kam deshalb nur das Datum.
Jeder Zuruf bekommt jetzt eine Zeile vorangestellt:

    [Jetzt: Dienstag, 25. August 2026, 7:35 Uhr]

Der Systemprompt sagt Claude, dass diese Zeile nicht zur Frage gehört und
nie vorgelesen wird. Sie geht mit jeder Frage neu mit und stimmt dadurch
immer — auch nach acht Stunden Laufzeit.

**Der Ausklang.** Hinter jede Äußerung kommen 300 ms Stille
(`AUSKLANG` in `sarvis/audio.py`). Grund: `sd.wait()` kehrt zurück, sobald
der Gerätepuffer gefüllt ist, nicht wenn er ausgespielt ist — die letzte
Silbe ging verloren („zweitausendsechsundzwanzig" wurde zu
„zweitausendsechsundzwanzi"). Nachgemessen: Piper liefert selbst nur rund
100 ms Auslauf, das reicht dafür nicht.

## Stimme wechseln

Drei Zeilen in `sarvis/config.py`: `STIMME`, `STIMME_SPRECHER`, `TEMPO`.

`python stimmproben.py` erzeugt aus allen vorhandenen Stimmen dieselbe
Hörprobe nach `stimmen/proben/` — anhören, entscheiden, eintragen.

**`TEMPO` ist der wirksamste Hebel**, oft mehr als ein Stimmwechsel.
Kleiner = schneller. Thorsten klingt bei `1.0` getragen bis einschläfernd;
bei `0.9` ist es dieselbe Stimme und ein anderer Eindruck.

Verfügbare deutsche Stimmen bei
`huggingface.co/rhasspy/piper-voices` unter `de/de_DE`:
thorsten (low/medium/**high**), thorsten_emotional (medium, acht
Stimmungen als Sprecher-IDs), kerstin, ramona, eva_k, karlsson, pavoque.

Achtung auf die Qualitätsstufe: `low` und `x_low` sind mit weniger
Material trainiert und klingen blechern. `de_DE-kerstin-low` läuft mit
16 kHz, Thorsten mit 22 kHz — hörbar.

### Haltung — der billigste Hebel von allen

`HALTUNG` in `config.py` ändert nicht den Klang, sondern den Ton:
`"normal"` ist sachlich und kurz angebunden, `"diener"` höflich
dienstbeflissen mit Meister-Anrede, `"butler"` die volle Nummer.

Das trägt weiter als jeder Stimmwechsel — dieselbe Stimme klingt mit
„Sehr wohl, Meister" völlig anders als mit „Mach ich". Es kostet nichts
und geht nicht auf die Klangqualität.

### Stimmfarbe

`STIMMFARBE` legt eine Effektkette hinter Piper: `"aus"`, `"hologramm"`,
`"bordcomputer"`, `"halle"`, `"kuenstlich"`, `"nah"`. Steht ab Werk auf
`"aus"`.

Der Umweg, den man sich damit spart: Sci-Fi-Stimmen sind fast nie eigene
Modelle. HAL 9000, GLaDOS, JARVIS — alles Schauspieler mit einer
Effektkette dahinter. Der Vorteil gegenüber einem geklonten Modell ist
nicht Klangtreue, sondern **Tempo**: Die Kette kostet Millisekunden und
läuft auf der CPU. Ein Klon-Modell bräuchte die GPU, und die hat Whisper.

Die Tonhöhe wird dabei bewusst **nicht** nachträglich verschoben, sondern
über Pipers Sprechtempo vorkompensiert. Ein Phasenvocoder verwäscht
Zischlaute — und genau die trägt eine Assistentenstimme.

## Einstellen

Alles Drehbare steht in `sarvis/config.py`: Taste und Weckwort,
Whisper-Modell, Stimme, Sprechtempo, Stimmfarbe, Haltung, Modell,
Systemprompt, Erlaubnisstufen und die freigegebenen Pfade.

Läuft Whisper nicht auf der Karte, `WHISPER_GERAET = "cpu"` und
`WHISPER_GENAUIGKEIT = "int8"` setzen — langsamer, aber es läuft.

## Die Anzeige

Ein rahmenloses Overlay unten am Bildschirm, immer im Vordergrund.

| Zustand | Farbe | was der Ring macht |
|---|---|---|
| bereit | blaugrau, fast weg | atmet langsam |
| hört zu | cyan | schlägt mit **deiner** Stimme aus |
| denkt nach | violett | drei kreisende Bögen |
| spricht | bernstein | schlägt mit **seiner** Stimme aus |

Der Ausschlag kommt aus dem echten Signal — beim Zuhören aus dem
Mikrofonpegel, beim Sprechen aus der Hüllkurve dessen, was gerade
abgespielt wird. Nichts davon ist eine Animation, die nur so tut.

Außen herum der Werkzeugkranz aus `config.WERKZEUGE`. Was gebaut ist,
steht auf `"bereit"` und leuchtet auf, sobald es benutzt wird; alles
andere ist blass angedeutet.

### Verschieben

**Strg+Alt+V** gibt die Anzeige frei: gestrichelter Rahmen, mit der Maus
ziehen, dieselbe Kombination macht sie wieder fest. Die Position wird in
`anzeige.json` gemerkt.

Nur in diesem Modus fängt die Anzeige überhaupt die Maus ab — sonst
arbeitest du durch sie hindurch. Landet sie durch einen abgesteckten
Monitor außerhalb aller Bildschirme, fällt sie beim nächsten Start auf
unten-mittig zurück, statt unsichtbar zu bleiben.

Kombination ändern: `TASTE_VERSCHIEBEN` in `config.py`.

### Sichtbarkeit einstellen

Drei Werte in `sarvis/config.py`, und sie wirken **multiplikativ** — das
ist der Haken, über den ich selbst gestolpert bin:

| Wert | Standard | wirkt auf |
|---|---|---|
| `DECKKRAFT_RUHIG` | `0.88` | alles, solange nichts passiert |
| `DECKKRAFT_AKTIV` | `1.00` | alles, während gehört/gedacht/gesprochen wird |
| `WERKZEUG_BEREIT` | `0.95` | gebaute Werkzeuge im Kranz |
| `WERKZEUG_GEPLANT` | `0.65` | noch nicht gebaute Werkzeuge |

Ein geplantes Werkzeug im Ruhezustand steht also bei `0.65 × 0.88`, also
effektiv 57 %. Mit den alten Werten (`0.34 × 0.60`) waren es 20 % — da
erkennt man nichts mehr, auch wenn die Deckkraft allein plausibel klingt.

Zurzeit steht **kein** Werkzeug auf „geplant": Alle 15 Punkte im Kranz
sind gebaut. Der Wert wirkt erst wieder, wenn einer dazukommt.

Zusätzlich hat jede Schrift einen dunklen Saum. Ein Overlay liegt mal auf
schwarzem Editor, mal auf weißem Explorer; helle Schrift allein ist im
zweiten Fall unlesbar, egal wie hoch die Deckkraft steht.

**Vorschau ohne Neustart:** `python anzeige_vorschau.py bild.png` rendert
alle vier Zustände über einen Verlauf von hell nach dunkel. Schneller als
starten und den Bildschirm abfotografieren — und ehrlicher, weil man beide
Extreme gleichzeitig sieht.

Die Anzeige läuft als **eigener Prozess** und bekommt ihre Zustände über
einen UDP-Socket auf `127.0.0.1:49731`. Das ist Absicht: die Schleife
wartet nie auf die Optik, und wenn die Anzeige abstürzt, redet Sarvis
unbeirrt weiter.

## Windows-Benachrichtigungen

Läuft ein Timer ab, meldet sich Sarvis dreifach: **Gong**, **gesprochen**
und als **Windows-Benachrichtigung**. Die Benachrichtigung ist die einzige
davon, die den Moment überlebt — sie bleibt im Info-Center stehen, auch
wenn gerade niemand am Rechner sitzt.

Einmalig einrichten:

```
.venv\Scripts\python.exe einrichten.py
```

Das legt `sarvis.ico` an (dasselbe Ringmotiv wie das Overlay) und eine
Verknüpfung im Startmenü. Der Zweck ist nicht die Verknüpfung, sondern die
Eigenschaft `System.AppUserModel.ID` darin: **Nur damit erscheinen die
Meldungen als „Sarvis" statt als „Python"** und landen zuverlässig im
Info-Center. Nachprüfen: `Get-StartApps | ? Name -like '*Sarvis*'`.

Abschalten über `TOAST = False`, den Gong über `GONG = False`.

### Eine Falle, die Sarvis stumm machen würde

**`win11toast` muss nach `onnxruntime` geladen werden.** Andersherum
stirbt dessen Initialisierung mit `DLL load failed ...
onnxruntime_pybind11_state` — und damit Piper, also Sarvis' Stimme.
Nachgestellt und bestätigt.

Deshalb importiert `sarvis/hinweis.py` `win11toast` **erst im Arbeitsfaden**
und sichert davor `onnxruntime` ab. Diese beiden Zeilen sind kein Stil,
sondern der Grund, warum die Stimme funktioniert — bitte nicht „aufräumen".

## Reinreden

Halt einfach die Taste, während Sarvis redet. Er ist sofort still, wirft
die laufende Antwort weg und hört zu.

Das Stoppen allein reichte nicht: Die schon erzeugten Nachrichten liegen
weiter in der Leitung, und die nächste Frage liest sie als Erstes. Im Test
kam auf „wie viel ist drei plus vier" die Aufzählung der Bundesländer von
davor — alle Antworten um eine Runde verschoben. Deshalb wird nach dem
Abbruch bis zum Ende der abgebrochenen Runde leergelesen, bevor wieder
etwas gefragt wird.

## Werkzeuge

**41 eigene Werkzeuge**, dazu `WebSearch` von Claude Code. Alle laufen
**im selben Prozess** — kein Unterprozess, keine Startzeit. Die 2,4
Sekunden, die externe MCP-Server gekostet haben, entstehen hier nicht.

Jedes hat eine Erlaubnisstufe in `config.WERKZEUG_STUFEN`:

| Stufe | |
|---|---|
| **still** | läuft ohne Nachfrage durch |
| **fragen** | Sarvis fragt laut nach und wartet auf ja oder nein |
| *nicht aufgezählt* | wird abgelehnt |

Die letzte Zeile ist wichtiger, als sie aussieht: **Nicht aufgezählt
heißt nein.** Eine Sperrliste kann nur verbieten, woran man gedacht hat.

| Bereich | still | fragt nach |
|---|---|---|
| Zeit | `timer_stellen`, `timer_liste`, `timer_abbrechen` | — |
| Gedächtnis | `merken`, `gedaechtnis_zeigen` | `vergessen` |
| Telegram | `telegram_kontakte`, `telegram_lesen`, `telegram_suchen` | `telegram_senden` |
| Kalender | `termine_ansehen` | `termin_anlegen`, `termin_absagen` |
| Mail | `mails_ansehen`, `mail_lesen` | `mail_senden`, `mail_verschieben` |
| Aufgaben | `aufgaben_ansehen`, `aufgabe_anlegen`, `aufgabe_abhaken` | — |
| Kontakte | `kontakt_suchen` | `kontakt_anlegen` |
| Drive | `drive_suchen`, `drive_lesen` | `drive_teilen` |
| Tabellen | `tabelle_lesen`, `tabelle_anhaengen` | `tabelle_schreiben`, `tabelle_anlegen` |
| Programme | `programm_starten`, `programm_suchen`, `web_oeffnen`, `route_zeigen` | `programm_beenden` |
| Medien | `medien_steuern` | — |
| Projekte | `projekt_liste` | `projekt_anlegen`, `projekt_oeffnen` |
| Aufträge | `auftrag_status`, `auftrag_abbrechen` | `auftrag_geben` |
| Dateien | Lesen, wo ohnehin gearbeitet wird | alles Übrige — siehe unten |

### Wie eine Rückfrage abläuft

Eine Rückfrage muss man beantworten können, **ohne hinzusehen**. Also
enthält sie den Inhalt, nicht den Werkzeugnamen:

> „Soll ich Anna schreiben, dass du später kommst?"

und nicht „Werkzeug `telegram_senden` ausführen?".

Antworten geht **per Stimme oder per Taste** — Enter ist ja, Escape ist
nein. Beides, weil beides seine Situation hat: Wer die Hände frei hat,
redet; wer im Büro sitzt, drückt. Solange die Frage offen steht, braucht
das „ja" **kein Weckwort** — auf eine Frage, die er gerade selbst
gestellt hat, wäre das albern.

Drei Dinge, die dabei nicht offensichtlich sind:

**Verneinung wird zuerst geprüft.** „Ja, aber nicht jetzt" ist kein Ja.

**Unklar ist kein Nein.** Wer etwas antwortet, das weder ja noch nein
ist, wird einmal nachgefragt, statt dass geraten wird.

**Im Zweifel wird abgelehnt.** Nach 25 Sekunden ohne Antwort
(`RUECKFRAGE_SEKUNDEN`) gilt die Handlung als abgelehnt. Ein Assistent,
der im Zweifel handelt, ist schlimmer als einer, der im Zweifel fragt.

### Timer und Wecker

Löschen und Ändern braucht kein eigenes Werkzeug: „Verlänger den
Wäsche-Timer um fünf Minuten" setzt Sarvis aus Liste, Abbrechen und Neu
zusammen. Getestet.

**Timer überleben einen Neustart** (`timer.json`). Was ablief, während
Sarvis aus war, meldet er beim nächsten Start nach.

Der Wecker läuft **komplett in Sarvis** — keine Windows-Weckfunktion.
Ist Sarvis zu, klingelt nichts. Gewartet wird gegen die Wanduhr, nicht
gegen eine Dauer: sonst ginge ein Timer um die Schlafdauer des PCs falsch.

### Programme, Medien und Web

„Mach mal Spotify auf", „geh auf YouTube", „nächster Titel", „wie komme
ich von Hamburg nach Berlin". Programme werden im Startmenü gesucht,
Medientasten wirken auf alles, was gerade Ton macht — Spotify, YouTube,
VLC.

Öffnen läuft still durch, **Beenden fragt nach**: Ein Fenster schließt
man wieder, ungespeicherte Arbeit nicht. Und eine Rückfrage vor „Pause"
wäre länger als die Handlung selbst.

### Dateien

Der Grundsatz ist **nicht aussperren, sondern nachfragen**. Ein
Assistent, der nichts anfassen darf, nützt nichts.

| | |
|---|---|
| frei lesen | `D:\Projekte`, `D:\Mitra`, `D:\Wissen` |
| frei schreiben | `D:\Projekte` |
| überall sonst | er darf, er fragt eben vorher |

Dateien, deren Inhalt Zugänge öffnet — `.env`, `.pem`, `.key`, `id_rsa`,
`.kdbx`, alles mit „passw", „secret" oder „token" im Namen — lösen eine
**deutlichere Rückfrage** aus: „das ist eine Datei mit Zugangsdaten".

Dazu eine sehr kurze harte Sperre. Nicht, weil Sarvis dort nichts zu
suchen hätte, sondern weil es **Einwegtüren** sind:

| gesperrt | warum |
|---|---|
| `sarvis/config.py`, `sarvis/schutz.py` | Wer die Erlaubnisstufen ändert, schaltet alle künftigen Rückfragen ab. Eine einzige Zustimmung würde jede weitere ersetzen. |
| `sarvis.session`, `.env` | Wer die Sitzungsdatei liest, hat das Telegram-Konto. |
| `C:\Windows`, `C:\Program Files` | Repariert kein „war doch nicht so gemeint". |
| `format`, `shutdown`, `diskpart`, `Clear-Disk`, `curl \| sh` … | Befehle, die sich mit einem gesprochenen „ja" nicht verantworten lassen. |

Der Prüfer ist bewusst **handgeschrieben statt mustergesteuert**, damit
nachvollziehbar bleibt, was durchkommt. Er kennt auch `PowerShell`, nicht
nur `Bash` — unter Windows heißt Claude Codes Shell-Werkzeug so, und eine
Sperrliste, die nur cmd-Befehle kennt, sperrt hier gar nichts.

## Gedächtnis

Sarvis merkt sich Dinge über dich — in **Markdown, von Hand lesbar**.
Das ist Absicht: Bei einem Assistenten, der Mails verschickt, musst du
nachlesen können, was er über dich zu wissen glaubt, und es korrigieren,
ohne ihn zu fragen.

Zwei Schichten, weil sie unterschiedlich teuer sind:

| | `kern.md` | `personen/`, `notizen/` |
|---|---|---|
| geladen | **immer**, bei jedem Zuruf | nur wenn er nachschlägt |
| kostet | Kontext bei *jeder* Frage | einen Werkzeugaufruf |
| Größe | unter 60 Zeilen | beliebig |

Der Kern steht im **Systemprompt**, nicht in der Frage. Dort wird er
zwischengespeichert und kostet ab dem zweiten Zuruf fast nichts; an die
Frage gehängt wäre er jedes Mal neu zu lesen. Wird er zu lang, warnt
Sarvis beim Start — ab etwa 4000 Zeichen wird er nicht klüger, sondern
unschärfer.

**Gesagt und bemerkt werden getrennt.** Was du ihm ausdrücklich aufträgst,
landet in `gemerkt.md`; was ihm von selbst auffällt, in `beobachtet.md` —
ausdrücklich als Vermutung, zum Durchsehen und Korrigieren. Gelöscht wird
nur auf Rückfrage.

Die Vorlage besteht größtenteils aus Ausfüllhinweisen. Die werden vor dem
Laden herausgefiltert, sonst würde Sarvis früher oder später über
„(Name)" reden.

**Der Inhalt ist aus dem Repository ausgeschlossen** — der Aufbau ist
drin, was er über dich weiß, nicht.

## Projekte und Aufträge

Sarvis kann Projekte anlegen und im Hintergrund daran arbeiten lassen.

| Werkzeug | Stufe | |
|---|---|---|
| `projekt_liste` | still | was liegt unter `D:\Projekte` |
| `projekt_anlegen` | fragt | Ordner, README, Git, Grundgerüst |
| `projekt_oeffnen` | fragt | Terminal mit Claude Code darin |
| `auftrag_geben` | **fragt** | Arbeiter im Hintergrund |
| `auftrag_status` | still | was läuft, wie lange schon |
| `auftrag_abbrechen` | still | |

### Zwei getrennte Sitzungen

```
Sarvis    schnell (effort low), redet mit dir, KEINE Schreibrechte
Arbeiter  eigene Sitzung (effort high), schreibt NUR im Projektordner
```

Das ist kein Ordnungsprinzip, sondern nötig: Im SDK **erben Unteragenten
den Erlaubnismodus ihres Elternteils** und können ihn nicht überschreiben.
Hätte Sarvis' Sitzung Schreibrechte, hätten sie alle — überall.

### Geprüft wird nachher, nicht vorher

Jeder Auftrag läuft auf einem eigenen Git-Zweig (`sarvis/<n>-<was>`),
committet dort und **merged nie nach main**. Gefällt das Ergebnis nicht,
ist es ein `git checkout master`. Deshalb genügt die Rückfrage als
Startfreigabe — man muss nicht jede Änderung einzeln hören.

Zum Schluss schreibt der Arbeiter `bericht.md`: was er tat, was er prüfte
und **woran er unsicher war**. Sarvis liest davon zwei, drei Sätze vor.

### Der Zaun

Der Arbeiter hat einen eigenen Erlaubnisprüfer — bewusst handgeschrieben
statt über Musterregeln, damit nachvollziehbar ist, was durchkommt:

| | |
|---|---|
| Schreiben | nur innerhalb des Projektordners |
| **Lesen** | ebenfalls nur dort — sonst könnte er die `.env` öffnen, und was er liest, geht in seinen Kontext |
| Bash | erlaubt (sonst kann er seine Arbeit nicht prüfen), aber ohne `git push`, `git remote`, `curl \| sh`, Systembefehle und Pfade außerhalb |
| Rest | abgelehnt |

30 Prüffälle laufen dagegen, darunter `../../Privat`, `C:/Windows/...`
und `type D:\Privat\Sarvis\.env`.

## Google

Kalender, Mail, Aufgaben, Kontakte, Drive und Tabellen hängen an
**einer** Anmeldung. Einrichten: `google_anmelden.bat`.

| still | fragt nach |
|---|---|
| Termine ansehen | Termin anlegen, absagen |
| Mails ansehen und lesen | **Mail senden** |
| Aufgaben ansehen, anlegen, abhaken | Mail verschieben oder löschen |
| Kontakt suchen | Kontakt anlegen |
| Drive durchsuchen und lesen | **Datei freigeben** |
| Tabelle lesen, Zeile anhängen | Tabelle überschreiben, Tabelle anlegen |

Löschen geht in den Papierkorb — dreißig Tage rückholbar, wie beim Klick
in Gmail. Deshalb reicht `gmail.modify`; den Vollzugriff mit endgültigem
Löschen haben wir bewusst nicht genommen: Das ist die einzige Handlung,
bei der ein missverstandenes „ja" nicht mehr zu reparieren wäre.

### Drive und Tabellen

Drive sucht **nach Namen und nach Inhalt** — „find mal die Rechnung von
der Werkstatt" findet also auch, was nur im Text steht. Vorgelesen wird
aus Google Docs und Textdateien; aus PDF, Bild oder Ordner kommt eine
ehrliche Absage statt Kauderwelsch.

Bei den Tabellen sind **Anhängen und Überschreiben getrennte Werkzeuge**,
und das ist kein Formalismus: „Trag im Tankbuch 52 Liter für 89 Euro ein"
darf nie in einer Zelle landen, die schon etwas enthält. Anhängen läuft
deshalb still durch, Überschreiben fragt.

Zwei Dinge, über die man sonst stolpert:

**Der Blattname muss mit.** Ein Bereich `A1:C20` ohne Blattnamen trifft
zwar das erste Blatt, aber `append` hängt dann *innerhalb* dieses
Bereichs an statt unten an der Tabelle. Deshalb wird zu jeder Tabelle
der Name ihres ersten Blattes mitgeholt.

**Werte werden interpretiert**, wie beim Tippen in der Tabelle: Aus
„89,10" wird die Zahl 89,1, nicht der Text „89,10". Das ist gewollt —
sonst könnte man mit den Zellen später nicht rechnen.

**Mehrdeutigkeit ist ein Fehler, keine Auswahl.** Passen mehrere Dateien
auf den gesagten Namen, zählt Sarvis sie auf und fragt nach, statt die
zuletzt geänderte zu nehmen. Beim Lesen wäre die falsche Datei lästig,
beim Freigeben nicht mehr.

**Der Kontaktzugriff löst das Namensproblem.** Gesprochene Mailadressen
versteht keine Spracherkennung. Bei „schreib Alex eine Mail" schlägt
Sarvis die Adresse selbst nach — das steht ausdrücklich in der
Werkzeugbeschreibung, damit er gar nicht erst rät.

### Warum nicht Googles fertige MCP-Server

Es gibt `Calendar MCP API` und `Workspace MCP API` in der Cloud Console.
Die brauchen einen OAuth-Client vom Typ *Webanwendung* mit Rückleitung
auf `https://claude.ai/api/mcp/auth_callback` — **die Anmeldung liefe
also über claude.ai.** Und dass claude.ai-Connectors Sarvis' eigene
Sitzung nicht erreichen, ist gemessen (`get_mcp_status()` zeigt nur die
lokalen Plugins). Das wäre dieselbe Sackgasse zweimal.

Deshalb die klassischen APIs mit einem **Desktop-Client**: Der Zugang
liegt als Datei hier, wie bei Telegram auch.

### Der Zugang läuft alle 7 Tage ab

Im Testing-Modus verfallen Googles Zugänge nach sieben Tagen. Beim Start
steht deshalb eine Zeile in der Konsole:

```
Google     : angemeldet
Google     : Zugang abgelaufen — google_anmelden.bat ausführen
```

Abstellen ließe sich das nur durch Veröffentlichen der App. Das scheitert
aber nicht an Gmail, sondern an zwei Pflichtangaben: **URL der Startseite
und der Datenschutzerklärung.** Für eine reine Desktop-Anwendung gibt es
beides nicht — man müsste zwei Seiten irgendwo hinstellen.

## Was noch nicht drin ist

- **Einstellungsoberfläche.** Alles Drehbare steht bis dahin in
  `sarvis/config.py`.
- **Spotify gezielt steuern.** Sarvis startet die App und bedient die
  Medientasten; einen bestimmten Titel auswählen kann er nicht. Dafür
  bräuchte es die Spotify-API mit eigener Anmeldung — bewusst
  zurückgestellt, weil Starten und Pausieren den Alltag abdecken.
- **Kalender-Erinnerungen von sich aus.** Er sieht Termine an, wenn man
  fragt, meldet sich aber nicht ungefragt. Nur Timer tun das — sie sind
  das einzige, was im Hintergrund gegen die Uhr wartet.

### Geprüft, damit es niemand nochmal glauben muss

Die Gmail- und Kalender-Connectors aus einer Claude-Code-Sitzung sind in
Sarvis' eigener Sitzung **nicht** verfügbar — abgefragt über
`get_mcp_status()`. Mail und Kalender brauchen also einen eigenen Weg
(Google-OAuth oder ein eigener MCP-Server). Das Telegram-Plugin dagegen
ist da und nutzbar.

## Neu aufsetzen

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Die Stimme (63 MB) landet in `stimmen/` und kommt von
`huggingface.co/rhasspy/piper-voices` (`de/de_DE/thorsten/medium`).
Das Whisper-Modell lädt sich beim ersten Start selbst (einmalig ~2 min).
