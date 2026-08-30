# Der Draht — das Protokoll zwischen Sarvis und seinen Oberflächen

**Dies ist die einzige Beschreibung des Protokolls.** Wer eine Oberfläche
baut — Web, Windows, Android —, baut gegen diese Datei. Wenn sie einer
anderen Beschreibung widerspricht, gilt sie; wenn sie dem Code
widerspricht, gilt der Code.

Damit das keine Behauptung bleibt:

```bash
python einsatz/draht_pruefen.py
```

Das vergleicht die Tabellen unten mit dem, was `sarvis/anzeige.py`,
`sarvis/netz/server.py` und `sarvis/netz/klang_netz.py` wirklich senden
und entgegennehmen, und meldet jede Abweichung. Es gab kurzzeitig zwei
Papiere über dieses Protokoll; nach fünf Minuten fehlten im zweiten
bereits drei Felder. Dagegen hilft keine Sorgfalt, sondern eine Prüfung.

Der **Look** steht nicht hier, sondern in `sarvis/hud.py` (1094 Zeilen)
und `sarvis/kachel.py` (2766). `web/sarvis.js` ist eine vollständige
Übersetzung davon und die praktischere Vorlage.

---

## Die Leitung

    wss://sarvis.tech-artist.de/draht

JSON über WebSocket, eine Nachricht je Rahmen. Nichts Browser-Eigenes —
eine native App spricht denselben Draht und ist gleichberechtigt.
Mehrere Oberflächen dürfen gleichzeitig verbunden sein und sehen
dasselbe; keine verdrängt eine andere.

### Anmelden

Die **erste Nachricht** auf der offenen Verbindung ist der Schlüssel.
Nicht als Query-Parameter in der Adresse: Der stünde im Zugriffslog des
Reverse Proxy, im Browserverlauf und in jedem Weiterleitungs-Header.

```json
{ "schluessel": "…", "kann_browser": true, "kann": ["kann_rechner"] }
```

`kann_browser` sagt, ob dieses Gerät die eingebauten Web-Werkzeuge
bedienen kann (eine Seite lesen, ein Formular ausfüllen). Sarvis richtet
solche Fragen an genau **ein** Gerät, und zwar das erste verbundene mit
`true`. Für einen Rechner sinnvoll, fürs Handy nicht.

`kann` ist eine Liste von Fähigkeiten, die über das Anzeigen hinausgehen.
Bisher gibt es eine:

| Fähigkeit | bedeutet |
|---|---|
| `kann_rechner` | „Ich kann Programme starten und Medientasten drücken" |

**Eine Weboberfläche meldet sie nicht** — ein Browser darf keine
Programme starten, und das soll so bleiben. Eine native App meldet sie.

Was hier fehlt, fehlt mit Folgen: Sarvis fragt vor jedem solchen Befehl
nach, ob überhaupt jemand ihn ausführen könnte, und sagt sonst ehrlich,
dass er es von hier nicht kann. Eine App, die `kann_rechner` meldet und
die Befehle dann ignoriert, ist schlimmer als eine, die es nicht meldet:
Sarvis sagt dann „erledigt", und nichts ist passiert.

Antwort bei Erfolg:

```json
{ "art": "willkommen", "geraet": "Dev-PC", "seit": 1788082503.1 }
```

Ungültiger Schlüssel oder keine Anmeldung binnen **10 Sekunden** →
Verbindung wird mit Code **4401** geschlossen, ohne Angabe, was falsch
war. Bei 4401 **nicht** wiederverbinden — der Schlüssel gilt nicht, und
Wiederholen ändert daran nichts.

Sonst: wiederverbinden mit **wachsendem Abstand** (1 s, dann 1,6× bis
höchstens 20 s). Nicht im Sekundentakt hämmern.

### Schlüssel anlegen und zurücknehmen

Auf dem Server, je Gerät einer:

```bash
python -c "import sys; sys.path.insert(0,'/srv/storage/projects/sarvis'); \
from sarvis.netz import geraete; print(geraete.anlegen('Dev-PC'))"
```

Er wird **genau einmal** gezeigt; gespeichert wird nur sein SHA-256-Abdruck.
Zurücknehmen mit `geraete.widerrufen("Dev-PC")` — das trifft nur dieses
Gerät, alle anderen laufen weiter. `geraete.liste()` zeigt, welche es
gibt und wann sie zuletzt da waren.

**Speichern in der App:** Windows Credential Manager, Android Keystore —
nicht im Klartext neben der ausführbaren Datei.

---

## Hinein: Server → Oberfläche

Jede Nachricht trägt `art`. **Unbekannte Arten und unbekannte Felder
ignorieren, nicht als Fehler behandeln.** So lässt sich das Protokoll
erweitern, ohne alle Oberflächen gleichzeitig anzufassen.

<!-- draht:herein — zwischen diesen Marken liest einsatz/draht_pruefen.py -->

| `art` | Felder | Bedeutung |
|---|---|---|
| `zustand` | `zustand`, `strom` | ruhig · hoert · denkt · spricht · fragt |
| `pegel` | `pegel` | Ausschlag 0–1 für den Ring, höchstens 50/s |
| `untertitel` | `wer`, `text`, `strom` | `wer` ist "du" oder "sarvis" |
| `nachhoeren` | `sekunden` | so lange ist kein Weckwort nötig |
| `hintergrund` | `zeilen`, `gesamt`, `seit`, `fertig` | was nebenher arbeitet |
| `werkzeug` | `name`, `aktiv`, `strom` | ein Werkzeug leuchtet auf |
| `freigabe` | `text`, `sekunden` | was gerade ohne Rückfrage durchgeht |
| `kachel` | `name`, `sorte`, `kopf`, `gross`, `stand`, `punkte`, `form`, `spalten`, `weggelassen`, `sekunden` | eine Datenkachel |
| `kachel_weg` | `name` | Kachel ausblenden |
| `ton` | `daten`, `rate`, `runde` | gesprochenes Audio, satzweise |
| `ton_stopp` | `runde` | sofort still sein |
| `browser` | `adresse` | Rest aus dem Desktop-Betrieb |
| `browser_zu` | — | dito |
| `horchen` | `an` | Dauerstrom jetzt schicken oder nicht |
| `befehl` | `befehl`, plus Felder je nach Art | etwas auf dem Gerät TUN |
| `verschieben` | `an` | dito |

<!-- /draht:herein -->

`zustand` trägt zusätzlich ein `text`, das schon die Desktop-Anzeige nie
gelesen hat — ein totes Feld am Draht. Ignorieren.

Die letzten drei Arten steuerten ein Fenster auf Saschas Rechner. Für
eine Netz-Oberfläche haben sie keine Bedeutung; sie stehen hier, damit
niemand sie für neu hält, wenn sie auftauchen.

### `strom` — wenn mehreres gleichzeitig läuft

Leer heißt: **das Gespräch**. Davon gibt es genau eines, und es ist der
Ring in der Mitte. Ein benannter Strom gehört zu einem Vorgang, der
nebenher läuft — Sarvis kann Aufträge im Hintergrund bearbeiten und
dabei weiterreden.

Eine Oberfläche ohne Platz dafür überspringt benannte Ströme einfach.
Die Weboberfläche tut genau das: `if (m.strom) break;`

### Kacheln

`name` ist die **Identität**, nicht die Überschrift: Zweimal `finanzen`
heißt dieselbe Kachel mit neuem Inhalt, nicht zwei übereinander.

`sorte` bestimmt Farbe und Lebensdauer:

| `sorte` | Farbe | Lebensdauer |
|---|---|---|
| `antwort` | rgb(255,179,71) | `sekunden`, Vorgabe 45 |
| `zustand` | rgb(126,224,168) | bleibt bis `kachel_weg` |

`punkte` sind Datenpunkte, keine fertigen Zeilen:

```json
{ "text": "Wohnen", "wert": "1.098,00", "zahl": 1098.0 }
```

Aus `zahl` wird die Länge eines Balkens **hinter** der Schrift, nicht
daneben. Weitere Felder je nach `form`: `wert2` und `zahl2` (Vergleich),
`gruppe` (Kategorien), `von`/`nach` (Fluss, Ablauf), `von_mir` (Blasen).

`form` ist eine von neun: liste · blasen · vergleich · text · balken ·
torte · kategorien · fluss · ablauf. Unbekanntes fällt auf `liste`
zurück. `spalten` (höchstens zwei) beschriftet die Spalten bei `vergleich`.

`weggelassen` sagt, wie viele Punkte der Server abgeschnitten hat.
**Das gehört angezeigt** („und 3 weitere"): Sonst ist die Kürzung stumm,
und die Kachel behauptet Vollständigkeit. Die Deckel je Form stehen in
`sarvis/anzeige.py` (`PUNKTE_DECKEL`) und hängen an der Lesbarkeit, nicht
an der Übertragung.

**Kacheln dürfen nicht anklickbar sein.** Keine Stilfrage: Im
ursprünglichen Sarvis steht dafür ein eigenes Fensterflag mit der
Begründung „kein Klick, der an der Rückfrage vorbeiläuft". Gehandelt
wird über Sarvis, nicht am Bild vorbei. Auf einem Touchscreen ist ab Werk
alles anklickbar — die Sicherung muss also **aktiv** wiederhergestellt
werden, sonst verschwindet sie lautlos.

### `befehl` — die Umkehrung

Alle anderen Arten schicken, was man **sehen** soll. Diese schickt, was
jemand **tun** soll:

```json
{ "art": "befehl", "befehl": "programm", "name": "Spotify", "was": "" }
{ "art": "befehl", "befehl": "medien", "was": "pause" }
```

`medien` kennt: `pause` · `weiter` · `zurueck` · `stop` · `lauter` ·
`leiser` · `stumm`. Unter Windows sind das die virtuellen Medientasten
(`VK_MEDIA_PLAY_PAUSE` und Geschwister) — sie wirken auf das, was gerade
Ton macht, ohne dass man wissen muss, welches Programm das ist.

**Warum es das gibt:** Auf dem Dev-PC konnte Sarvis Programme starten und
Musik steuern — er lief ja auf demselben Rechner. Auf dem Server ist
kein Spotify installiert, kein Bildschirm angeschlossen und niemand, der
etwas hören würde. Zwölf Werkzeuge konnten nur noch scheitern.

Also die Umkehrung: Nicht Sarvis führt den Befehl aus, sondern das
Gerät, vor dem jemand sitzt. Damit wird aus dem Verlust ein Gewinn —
vorher ging es nur auf dem einen Rechner, jetzt auf jedem, an dem eine
App läuft. Vom Handy aus „mach Musik an" zu sagen, ging vorher gar nicht.

Wer `kann_rechner` nicht meldet, bekommt diese Art nie zu sehen.

### `hintergrund`

`zeilen` sind höchstens drei, `gesamt` ist die **wirkliche** Anzahl. Der
Unterschied zählt: Bei sieben laufenden Aufträgen kommen drei Zeilen und
`gesamt: 7`. Wer die Zahl aus der Länge der Liste nimmt, zeigt „· 3" und
lügt.

`seit` sind Sekunden, seit überhaupt etwas läuft. `fertig` heißt, dass
gerade **alles** fertig geworden ist.

---

## Hinaus: Oberfläche → Server

<!-- draht:hinaus -->

| `art` | Felder | |
|---|---|---|
| `zuruf` | `text` | eine getippte Zeile |
| `sprache` | `daten`, `rate` | eine fertige Aufnahme |
| `antwort` | `nummer`, `inhalt` | Antwort auf eine Frage des Servers |
| `strom` | `daten`, `rate` | ein Stück Dauerstrom fürs Weckwort |
| `hier` | — | Lebenszeichen, optional |

<!-- /draht:hinaus -->

`hier` ist wirklich optional: Der Server hält die Verbindung selbst mit
WebSocket-Pings wach (alle 30 s). Es schadet nicht, es zu schicken, aber
es ersetzt nichts.

### Das Audioformat ist nicht verhandelbar

**16 000 Hz · mono · int16 · little-endian · base64.**

Genau das erwartet Whisper. Alles andere müsste serverseitig umgetastet
werden, und lineare Interpolation ohne Tiefpass macht dabei hörbaren
Schaden. Im Browser bekommt man es, indem man den `AudioContext` direkt
mit `{sampleRate: 16000}` anfordert; nativ nimmt man gleich so auf
(WASAPI und AudioRecord können das).

Aufnahmen unter **0,4 Sekunden** verwirft der Server als Versehen.
Nachrichten über **4 MB** weist er ab — 30 Sekunden bei 16 kHz sind als
base64 rund 1,3 MB.

### Push-to-talk ist hier umgedreht

Der Server sagt **nicht** „jetzt aufnehmen". Die Oberfläche entscheidet
das selbst und schickt eine fertige Aufnahme. Das ist Absicht: Eine
Rundreise vor dem ersten Wort würde genau die Zeit kosten, in der schon
geredet wird.

Besser noch: **schon vor dem Tastendruck in einen Ringpuffer aufnehmen**
und beim Loslassen die letzten ~300 ms davor mitschicken. Menschen
drücken die Taste oft eine Silbe zu spät.

### Mikrofon-Einstellungen, die zählen

- **Echo-Unterdrückung an.** Sarvis' eigener Echo-Filter vergleicht
  *Text*, keine Wellenformen — er merkt erst nach Whisper, dass er sich
  selbst gehört hat. Ohne akustische Unterdrückung klingelt es bei
  Lautsprecherbetrieb bei jedem Durchlauf erneut.
- **Verstärkungsautomatik AUS.** Die Weckwort-Schwelle ist ein absoluter
  Pegel (`WECKWORT_MIN_PEGEL = 0.008`) und wird von einer Automatik
  wertlos.

### Ton abspielen — und die Runde beachten

`ton` kommt **satzweise**, nicht als fertige Antwort. Das ist der
Unterschied zwischen „fühlt sich an wie reden" und „fühlt sich an wie ein
Formular": Während Satz eins klingt, baut der Server schon Satz zwei. Die
Blöcke gehören **nahtlos aneinandergehängt**, nicht einzeln abgespielt
mit Lücken dazwischen.

**Die `runde` ist die Wahrheit.** Reinreden ist ausdrücklich erlaubt —
wer Sarvis unterbricht, soll ihn sofort zum Schweigen bringen. Über Netz
kann ein Satz aber schon unterwegs sein, wenn der Abbruch erfolgt:

1. `ton_stopp` → alle eingeplanten Blöcke abbrechen **und** die eigene
   Runde auf die gemeldete setzen
2. ein `ton` mit `runde` **kleiner** als die eigene → verwerfen
3. wer selbst zu reden anfängt → Ton **sofort** stoppen, ohne auf den
   Server zu warten; bis dessen `ton_stopp` ankommt, hätte man sich
   sonst selbst zugehört

Ohne das spielt ein alter Satz nach dem „Gestoppt." — genau der Fehler,
gegen den der Rundenzähler ursprünglich gebaut wurde, nur um eine
Netzlaufzeit versetzt.

`rate` beim Ton ist die Rate der **Piper-Stimme**, üblich 22 050 — nicht
zu verwechseln mit den 16 000 der Aufnahme.

---

## Was der Server zusagt und was nicht

**Zugesagt:** Nachrichten kommen in der Reihenfolge an, in der sie
gesendet wurden. Fast alle sind Zustände, keine Änderungen — eine
verlorene kostet ein Bild, die nächste heilt es.

**Nicht zugesagt: dass jede ankommt.** Bei schlechter Verbindung staut
der Server und dampft dann ein. Was verloren bleiben würde (`werkzeug`,
`kachel_weg`, `verschieben`), überlebt vollständig; vom Rest bleibt je
Art, Name und Strom der **neueste** Stand. Eine Oberfläche darf also
nicht darauf bauen, jeden Zwischenwert zu sehen — wohl aber darauf, dass
der letzte Stand stimmt.

**Ebenfalls nicht zugesagt: dass er überhaupt antwortet.** Er kann neu
starten, während die Oberfläche verbunden ist. Ein Ring, der ewig „denkt
nach" behauptet, ist schlimmer als einer, der sagt, dass die Verbindung
weg ist.

---

## Der Dauerstrom: „Hey Sarvis" ohne Tastendruck

Eine Oberfläche kann ihr Mikrofon offenhalten und blockweise schicken,
was es hört. Dann läuft auf dem Server dieselbe Erkennung wie früher
lokal: erst der Sprach-Erkenner (billig, CPU), und nur wenn wirklich
jemand redet, Whisper.

```json
{ "art": "strom", "rate": 16000, "daten": "base64-int16" }
```

Dasselbe Format wie `sprache`. Gebündelt wird auf etwa eine
Viertelsekunde (4096 Werte): Einzeln zu senden wären acht Nachrichten je
Sekunde nur für Rahmen-Overhead, länger zu sammeln machte das Weckwort
träge.

Der Server antwortet mit `horchen`, wenn er den Strom gerade **nicht**
will — während er selbst redet oder eine Rückfrage läuft. Darauf zu
hören ist keine Höflichkeit: Wer weitersendet, während Sarvis spricht,
lässt ihn sich selbst zuhören, und der Rückstandsdeckel wirft am Ende
ausgerechnet das weg, was danach gesagt wird.

**Nur eine Oberfläche zur Zeit** darf senden. Zwei Mikrofone in einen
Strom zu mischen ergäbe Kauderwelsch, und der Sprach-Erkenner sähe
dauernd Sprache. Wer zuerst sendet, hat ihn; meldet er sich ab, ist er
wieder frei.

**Die Erkennung bleibt beim Server.** Der Client liefert nur Rohton. Ob
jemand „Hey Sarvis" gesagt hat, entscheiden Silero-VAD, Whisper und der
Ähnlichkeitsvergleich mit seinen gemessenen Schwellen — das ist die
Stelle, an der die Arbeit steckt, und sie soll nicht in drei Oberflächen
dreimal existieren und dreimal auseinanderlaufen.

Ob es sich lohnt, hängt vom Gerät ab:

- **Am Rechner** einfach durchsenden. 16 kHz int16 sind 256 kbit/s — im
  heimischen Netz ein halbes Promille einer Gigabit-Leitung, und es
  fällt kein Volumen an. Die Weboberfläche hat dafür einen Schalter.
- **Am Handy** besser gar nicht: rund 260 MB am Tag, auch wenn niemand
  redet, und das Mikrofon dauerhaft offen. Dort bleibt es bei
  Push-to-talk. Wer es trotzdem will, lässt den Sprach-Erkenner lokal
  laufen und sendet nur, wenn wirklich jemand spricht.

Die Schwellen der Erkennung sind gemessen und feinjustiert (sarvis 1,00 ·
jarvis 0,83 · service 0,62 · serviert 0,57, Grenze 0,60). Sie lösen das,
woran openWakeWord scheiterte: Dessen Fertigmodelle sind auf englische
Aussprache trainiert und erreichten für „Hey Sarvis" von einer deutschen
Stimme nur 0,09 bis 0,13.

**Damit hat eine Android-App wieder einen Grund**: Ein Foreground Service
darf das Mikrofon offenhalten, wenn der Bildschirm gesperrt ist — ein
Browser im Hintergrund nicht.

Blockgröße für den VAD: **genau 480 Werte** bei 16 kHz. Silero rechnet in
Rahmen dieser Größe; eine andere Blockung verfälscht seine Vorhersage.
Opus kennt kein 30-ms-Frame (2,5/5/10/20/40/60 ms) — wer über Opus
schickt, muss serverseitig neu blocken. Das ist eine Zeile, die man
vergisst, und sie fällt nicht auf: Der VAD sagt dann nicht „Fehler", er
sagt nur öfter das Falsche.
