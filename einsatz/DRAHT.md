# Der Draht — wie eine Oberfläche mit Sarvis spricht

Die Weboberfläche ist **eine** Bedienung, nicht die einzige. Was sie
benutzt, ist ein offenes Protokoll: JSON über WebSocket, nichts
Browser-Eigenes. Eine native App unter Windows oder Android spricht
denselben Draht und ist gleichberechtigt — mehrere Oberflächen dürfen
gleichzeitig verbunden sein und sehen dasselbe.

    wss://sarvis.tech-artist.de/draht

## Warum eine native App sich lohnen kann

Nicht wegen der Optik. Wegen zweier Dinge, die ein Browser nicht darf:

**Windows: der Tastaturhaken.** Sarvis' beste Bedienung ist die rechte
Strg-Taste — halten, reden, loslassen, ohne das Fenster zu wechseln. Ein
Browser bekommt Tastendrücke nur, wenn er den Fokus hat. Eine native App
hängt einen systemweiten Haken ein und hört auch bei minimiertem Fenster
mit. Dazu käme das randlose Overlay über allen Fenstern, wie es das
heutige Qt-HUD ist.

**Android: das Weckwort bei gesperrtem Bildschirm.** Ein Browser darf das
Mikrofon nicht offenhalten, wenn er im Hintergrund liegt. Ein Foreground
Service darf es. Das ist der einzige echte Verlust der PWA gegenüber
einer App — alles andere (Mikrofon, Ton, Push, Vollbild, Startbildschirm)
kann sie auch.

Umgekehrt gilt: Solange man das nicht braucht, ist die PWA weniger
Arbeit — eine Codebasis, kein Store, keine Signatur, kein Update-Zyklus.

## Anmelden

Erste Nachricht auf der offenen Verbindung. **Nicht** als Query-Parameter
in der Adresse: Die stünde im Zugriffslog, im Verlauf und in jedem
Weiterleitungs-Header.

```json
{ "schluessel": "GoTOWW…", "kann_browser": false }
```

`kann_browser` sagt, ob dieses Gerät die eingebauten Web-Werkzeuge
bedienen kann (eine Seite lesen, ein Formular ausfüllen). Nur ein Gerät
mit großem Bildschirm sollte das mit `true` beantworten; Sarvis richtet
seine Fragen dann dorthin.

Antwort bei Erfolg:

```json
{ "art": "willkommen", "geraet": "Handy Sascha", "seit": 1788082503.1 }
```

Bei einem ungültigen Schlüssel wird die Verbindung mit Code **4401**
geschlossen — ohne Hinweis, was falsch war. Nach zehn Sekunden ohne
Anmeldung ebenfalls.

Schlüssel legt man auf dem Server an:

```bash
python -c "import sys; sys.path.insert(0,'/srv/storage/projects/sarvis');
from sarvis.netz import geraete; print(geraete.anlegen('Dev-PC'))"
```

Er wird genau einmal gezeigt; gespeichert wird nur sein Abdruck.
Zurücknehmen: `geraete.widerrufen("Dev-PC")` — trifft nur dieses Gerät.

## Was hereinkommt (Server → Oberfläche)

Zwölf Anzeigearten, dazu Ton. Jede trägt `art`. **Unbekannte Arten und
unbekannte Felder ignorieren, nicht als Fehler behandeln** — so lässt
sich das Protokoll erweitern, ohne alle Oberflächen gleichzeitig
anzufassen.

| art | Felder | Bedeutung |
|---|---|---|
| `zustand` | `zustand`, `strom` | `ruhig` `hoert` `denkt` `spricht` `fragt` |
| `pegel` | `pegel` (0–1) | Ausschlag für den Ring, höchstens 50/s |
| `untertitel` | `wer` (`du`/`sarvis`), `text`, `strom` | was gerade gesagt wird |
| `nachhoeren` | `sekunden` | so lange ist kein Weckwort nötig |
| `hintergrund` | `zeilen` (max 3), `gesamt`, `seit`, `fertig` | was nebenher arbeitet |
| `werkzeug` | `name`, `aktiv`, `strom` | ein Werkzeug leuchtet auf |
| `freigabe` | `text`, `sekunden` | was gerade ohne Rückfrage durchgeht |
| `kachel` | `name`, `sorte`, `kopf`, `gross`, `stand`, `punkte`, `form`, `spalten`, `weggelassen`, `sekunden` | eine Datenkachel |
| `kachel_weg` | `name` | Kachel ausblenden |
| `browser`, `browser_zu`, `verschieben` | | Reste aus dem Desktop-Betrieb, für Netz-Oberflächen ohne Bedeutung |
| `ton` | `daten` (base64), `rate`, `runde` | gesprochenes Audio, int16 mono |
| `ton_stopp` | `runde` | sofort still sein |

### `strom` — wenn mehrere Dinge gleichzeitig laufen

Leer heißt: **das Gespräch**. Das ist der Ring in der Mitte, und davon
gibt es genau einen. Ein benannter Strom gehört zu einem Vorgang, der
nebenher läuft. Eine Oberfläche, die dafür keinen Platz hat, darf
benannte Ströme schlicht überspringen — die Weboberfläche tut das.

### `runde` — warum sie bei jedem Ton mitgeht

Reinreden ist erlaubt: Wer Sarvis unterbricht, soll ihn sofort zum
Schweigen bringen. Lokal genügte dafür ein Stopp-Befehl an die Soundkarte
— kehrt er zurück, ist es still. Über Netz gibt es diese Garantie nicht:
Ein Satz kann schon unterwegs sein, wenn der Abbruch erfolgt.

Deshalb trägt jeder Ton die Runde seines Absendens, und `ton_stopp` zählt
sie hoch. **Die Oberfläche muss selbst verwerfen, was älter ist als ihre
aktuelle Runde.** Ohne das spielt ein alter Satz nach dem „Gestoppt." —
genau der Fehler, gegen den der Zähler ursprünglich gebaut wurde, nur um
eine Netzlaufzeit versetzt.

Wer selbst aufnimmt, sollte den Ton **sofort** stoppen, ohne auf den
Server zu warten — bis dessen `ton_stopp` ankommt, hätte man sich sonst
selbst zugehört.

## Was hinausgeht (Oberfläche → Server)

| art | Felder | |
|---|---|---|
| `zuruf` | `text` | eine getippte Zeile |
| `sprache` | `daten` (base64), `rate` | eine fertige Aufnahme |
| `antwort` | `nummer`, `inhalt` | Antwort auf eine Frage des Servers |
| `hier` | | Lebenszeichen (optional) |

### Sprache: das Format ist nicht verhandelbar

**16 000 Hz, mono, int16, little-endian, base64.** Genau das erwartet
Whisper; alles andere müsste serverseitig umgetastet werden, und lineare
Interpolation ohne Tiefpass macht dabei hörbaren Schaden.

Im Browser bekommt man das, indem man den `AudioContext` direkt mit
`{sampleRate: 16000}` anfordert. Nativ nimmt man gleich in dieser Rate
auf.

Push-to-talk ist hier **umgedreht** gegenüber dem Desktop-Sarvis: Das
Gerät entscheidet, wann es aufnimmt, und schickt eine fertige Aufnahme.
Der Server sagt nicht „jetzt aufnehmen". Das spart die Rundreise vor dem
ersten Wort — sonst ginge genau die Zeit verloren, in der schon geredet
wird.

Aufnahmen unter 0,4 Sekunden verwirft der Server als Versehen.
Nachrichten über 4 MB weist er ab; 30 Sekunden bei 16 kHz sind als
base64 rund 1,3 MB.

### Mikrofon-Einstellungen, die zählen

- **Echo-Unterdrückung an.** Sarvis' eigener Echo-Filter vergleicht
  *Text*, keine Wellenformen — er merkt erst nach Whisper, dass er sich
  selbst gehört hat. Ohne akustische Unterdrückung klingelt es bei
  Freisprechbetrieb bei jedem Durchlauf erneut.
- **Verstärkungsautomatik aus.** Die Weckwort-Schwelle ist ein absoluter
  Pegel (`WECKWORT_MIN_PEGEL = 0.008`) und wird von einer Automatik
  wertlos.

## Was noch fehlt

Der **Dauerstrom** fürs Weckwort. Bisher schickt eine Oberfläche fertige
Aufnahmen. Für „Hey Sarvis" ohne Tastendruck muss sie blockweise senden;
die Schnittstelle dafür (`Dauerhorch` in `sarvis/klang.py`) ist
beschrieben, aber nicht gebaut. Zwei Wege stehen dort offen:

- **Am Rechner** einfach durchsenden. 16 kHz int16 sind 256 kbit/s — im
  heimischen Netz ein halbes Promille einer Gigabit-Leitung.
- **Am Handy** den Sprach-Erkenner (VAD) lokal laufen lassen und nur
  senden, wenn wirklich jemand redet. Sonst wären es rund 260 MB am Tag,
  auch wenn niemand spricht.

In beiden Fällen bleibt die **Erkennung** von „Hey Sarvis" auf dem
Server. Sie ist gemessen und feinjustiert (sarvis 1,00 · jarvis 0,83 ·
service 0,62 · serviert 0,57, Schwelle 0,60) und löst das, woran
openWakeWord scheiterte: Dessen Fertigmodelle sind auf englische
Aussprache trainiert und erreichten für „Hey Sarvis" von einer deutschen
Stimme nur 0,09 bis 0,13.

Blockgröße für den VAD: **genau 480 Werte** bei 16 kHz. Silero rechnet in
Rahmen dieser Größe, eine andere Blockung verfälscht seine Vorhersage.
Opus kennt kein 30-ms-Frame — wer über Opus schickt, muss serverseitig
neu blocken.
