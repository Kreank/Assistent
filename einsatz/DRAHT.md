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
`sarvis/netz/server.py`, `sarvis/netz/klang_netz.py` und
`sarvis/netz/fernsicht.py` wirklich senden und entgegennehmen, und
meldet jede Abweichung. Es gab kurzzeitig zwei
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
| `kann_radio` | „Ich kann eine Stream-Adresse selbst abspielen" (siehe `radio`) |

`kann_rechner` meldet **eine Weboberfläche nicht** — ein Browser darf
keine Programme starten, und das soll so bleiben. Eine native App meldet
es.

`kann_radio` ist andersherum: Die Weboberfläche meldet es (ein
`<audio>`-Element hat jeder Browser), eine native App erst, wenn sie ein
eigenes Abspielwerk gebaut hat. **Melde es nicht auf Vorrat.** Sarvis
fragt vor jedem Sender, ob das Gerät, das gerade spricht, es kann, und
sagt sonst „Auf diesem Gerät kann ich kein Radio abspielen". Das ist die
ehrliche Antwort; eine App, die die Fähigkeit meldet und die Nachricht
dann verschluckt, macht daraus ein „läuft", nach dem nichts klingt.

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

Das heißt wörtlich: **still überspringen.** Nicht loggen und abbrechen,
nicht die Verbindung schließen, nicht mit einer Ausnahme abstürzen. Ein
`switch` ohne `default` tut das von selbst; ein `else: throw` ist der
Fehler. Der Server ist immer der neuere von beiden — er bekommt eine
Art dazu, lange bevor alle drei Oberflächen sie kennen. `radio` und
`radio_aus` sind genau so entstanden.

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
| `blatt` | `kennung`, `sorte`, `titel`, `adresse`, `inhalt`, `datei`, `bytes`, `sekunden` | etwas zum Lesen |
| `blatt_weg` | `kennung` | Blatt zuklappen |
| `ton` | `daten`, `rate`, `runde` | gesprochenes Audio, satzweise |
| `ton_stopp` | `runde` | sofort still sein |
| `radio` | `url`, `name` | diesen Sender abspielen — Adresse, kein Ton |
| `radio_aus` | — | Radio beenden |
| `browser` | `adresse` | Rest aus dem Desktop-Betrieb |
| `browser_zu` | — | dito |
| `horchen` | `an` | Dauerstrom jetzt schicken oder nicht |
| `befehl` | `befehl`, plus Felder je nach Art | etwas auf dem Gerät TUN |
| `web_bild` | `daten`, `adresse`, `titel`, `breite`, `hoehe` | ein Blick auf Sarvis' eigenen Browser |
| `schirm` | `daten`, `breite`, `hoehe` | ein Bild aus dem Live-Strom |
| `schirm_aus` | — | der Live-Strom ist zu Ende |
| `verschieben` | `an` | dito |

<!-- /draht:herein -->

`zustand` trägt zusätzlich ein `text`, das schon die Desktop-Anzeige nie
gelesen hat — ein totes Feld am Draht. Ignorieren.

`browser`, `browser_zu` und `verschieben` steuerten ein Fenster auf
Saschas Rechner. Für eine Netz-Oberfläche haben sie keine Bedeutung; sie
stehen hier, damit niemand sie für neu hält, wenn sie auftauchen.

**`schirm` und `schirm_aus` gehen NICHT an alle.** Sie sind die einzigen
Arten, die eine einzelne Oberfläche adressieren — die, die den Strom
angefordert hat. Siehe unten, „Die Fernsicht".

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

### Blätter

Ein Blatt ist, was gelesen statt gehört wird. Die Kachel ist zu klein
dafür (rund 290 Punkte breit, zwölf Datenpunkte), der Untertitel ist
eine Zeile. Drei Sorten, ein Kasten:

| `sorte` | wo der Inhalt steckt | wie er gezeigt wird |
|---|---|---|
| `markdown` | `inhalt`, mit der Nachricht | die Oberfläche setzt ihn |
| `html` | `adresse` → `/blatt/<kennung>` | in einem Rahmen |
| `datei` | dito, plus `datei` und `bytes` | ein Knopf zum Herunterladen |

`kennung` ist die **Identität**, wie `name` bei der Kachel: Zweimal
dieselbe heißt dasselbe Blatt mit neuem Inhalt, nicht zwei
übereinander. `sekunden` ist die Lebensdauer, 0 heißt „bis
`blatt_weg`".

**`adresse` ist immer ein Pfad auf diesen Server**, beginnend mit
`/blatt/`. Nie eine fremde Adresse — und eine Oberfläche, die etwas
anderes bekommt, zeigt es nicht an. Der Draht ist authentifiziert, was
über ihn kommt, ist trotzdem aus Modellausgabe gebaut.

Die Adresse trägt keinen Geräteschlüssel, weil sie keinen tragen kann:
Ein `<iframe>` schickt keine eigenen Kopfzeilen, ein Download-Knopf
auch nicht, und der Systemviewer, der das PDF danach öffnet, erst
recht nicht. Was stattdessen schützt, steht in
`sarvis/netz/blaetter.py`: 192 Bit Zufall in der Kennung, sieben Tage
Frist, kein Verzeichnis, und der Pfad wird nie aus der Adresse gebaut.

**Markdown ist die einzige Auszeichnung, und HTML ist keine.** Die
Teilmenge: `#` bis `###`, `**fett**`, `*kursiv*`, `~~durchgestrichen~~`,
`` `code` ``, `-` und `1.` Listen mit bis zu drei Ebenen (zwei
Leerzeichen je Ebene), `- [ ]` und `- [x]` für Haken, `>` Zitat,
```` ``` ```` Codeblock, `|` Tabellen (die `|---|`-Zeile ist Pflicht),
`---` Trennlinie, `[Text](https://ziel)`. Alles andere überlebt als
Text.

Ein Linkziel, das nicht mit `http://`, `https://`, `mailto:` oder
`tel:` beginnt, wird zu blossem Text — sichtbar, aber nicht anklickbar.
**Bilder werden benannt, nicht geladen:** `![Foto](…)` wird zu
`[Foto]`. Ein `<img>` auf eine fremde Adresse wäre in einem Blatt
zweierlei — ein leerer Rahmen, weil die CSP nur `data:` durchlässt,
und ein Abruf, der verrät, wann das Blatt geöffnet wurde.

Nicht gelesen werden Fußnoten und der eingerückte Codeblock (vier
Leerzeichen statt Rücktikken). Der zweite ließe sich nicht sicher von
der Fortsetzung eines Listenpunkts unterscheiden, und eine Aufzählung,
die zur Hälfte als Quelltext erscheint, ist schlimmer als ein
Codeblock, der wie ein Absatz aussieht.

**Der Rahmen bekommt kein `allow-scripts`.** Das ist die Bedingung
dafür, dass ein Blatt aus Modellausgabe gebaut werden darf: Sarvis
kann den Rechner bedienen, und was er anzeigt, hat er womöglich von
einer fremden Seite gelesen. Ohne Skripte, ohne `allow-same-origin`
und ohne Zugriff auf `localStorage` (dort liegt der Geräteschlüssel)
ist der Inhalt etwas zum Ansehen und sonst nichts. Wer das später „zur
Bequemlichkeit" lockert, hebt die einzige Absicherung auf, die es hier
gibt.

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

### `web_bild` — zusehen, was Sarvis im Browser tut

Sarvis hat einen eigenen Browser auf dem Server. Damit liest er Seiten,
füllt Formulare aus und klickt — unsichtbar. `web_bild` ist der Blick
darauf:

```json
{ "art": "web_bild", "daten": "<base64-WebP>", "adresse": "https://…",
  "titel": "…", "breite": 1280, "hoehe": 900 }
```

`daten` ist **ohne** `data:`-Präfix; wer es anzeigen will, setzt
`data:image/webp;base64,` davor.

Es kommt **nicht automatisch** nach jedem Klick — das wäre ein Screencast
durch die Hintertür und würde bei jeder Aktion Bandbreite kosten. Es ist
ein Werkzeug, das Sarvis benutzt, wenn es etwas zu sehen gibt, oder auf
Zuruf („zeig mal, was du da machst").

Gemessen: eine schlichte Seite 12 KB, ein Wikipedia-Artikel 107 KB. Weit
unter den 4 MB des Drahts.

Nicht zu verwechseln mit `browser`: Das schickt eine **Adresse**, damit
der Nutzer die Seite in SEINEM Browser öffnet. `web_bild` zeigt, was in
Sarvis' eigenem steht.

### Die Fernsicht — zusehen **und** eingreifen

`web_bild` ist ein Foto. Die Fernsicht ist das Fenster: ein Bildstrom
heraus, Klicks und Tasten hinein. Damit ist Sarvis' Browser wieder das,
was er auf dem Dev-PC war — einer, in den beide hineingreifen können.

    Oberfläche → { "art": "schirm_an", "an": true }
    Server     → { "art": "schirm", "daten": "<base64-jpeg>",
                   "breite": 1280, "hoehe": 900 }        … achtmal je Sekunde
    Oberfläche → { "art": "klick", "x": 0.42, "y": 0.31, "knopf": "links" }
                 { "art": "taste", "text": "Wärmepumpe" }
                 { "art": "taste", "sonder": "Enter" }
                 { "art": "rollen", "x": 0.5, "y": 0.5, "hoch": -320 }
    Oberfläche → { "art": "schirm_an", "an": false }
    Server     → { "art": "schirm_aus" }

`daten` ist **JPEG**, ohne `data:`-Präfix (`web_bild` ist WebP — beim
Bewegtbild zählt die Zeit zum Kodieren, nicht die letzten zehn Prozent
Größe). Davor gehört `data:image/jpeg;base64,`.

**Koordinaten sind Anteile zwischen 0 und 1, keine Pixel.** Die
Oberfläche skaliert das Bild und kennt ihre Skalierung besser als der
Server; der rechnet mit seiner Fenstergröße (1280 × 900) in Pixel um.
Wer mit `object-fit: contain` anzeigt, muss die schwarzen Ränder
herausrechnen — sonst trifft jeder Klick gleichmäßig daneben.

`hoch` beim Rollen zählt **nach oben**; negativ heißt nach unten. Das
ist das umgekehrte Vorzeichen von `deltaY` im Browser.

`sonder` kennt: `Enter` · `Backspace` · `Tab` · `Escape` · `Delete` ·
`ArrowLeft/Up/Right/Down` · `Home` · `End` · `PageUp` · `PageDown`.
Entweder `text` **oder** `sonder`, nicht beides.

**Nur an die, die zusehen.** Alle anderen Arten gehen an jede verbundene
Oberfläche. Dieser Strom nicht: Er geht ausschließlich an die, die
`schirm_an` geschickt hat. Acht Bilder je Sekunde an ein Handy, das
nicht hinsieht, wären reine Verschwendung. Wer nicht zusieht, kann auch
nicht klicken — ein `klick` ohne laufenden Strom wird verworfen.

**Der Strom hört von selbst auf**: wenn der letzte Zuschauer abschaltet
oder die Verbindung verliert, und wenn Sarvis' Browser zumacht
(Ruhezeit, Absturz, `web_schliessen`). Im letzten Fall kommt
`schirm_aus`. Darauf zu hören ist keine Höflichkeit: Sonst steht ein
Standbild da, das aussieht wie live, und der nächste Klick geht ins
Leere.

**Gemessen** (im Container, je zehn Sekunden, 1280 × 900, Güte 60):

| Lage | Bilder/s | Datenrate |
|---|---|---|
| Seite steht still | 0 | 0 |
| schlichte Seite, gescrollt | 0,9 | 9 KB/s |
| Wikipedia-Artikel, ununterbrochen gescrollt | 8,0 | 1.178 KB/s (9,6 Mbit/s) |

Chrome schickt nur bei Veränderung — Zusehen ohne Bewegung kostet
nichts. Der letzte Wert ist der schlimmste Fall und nicht die Benutzung.

Wird es zu viel, sinkt die **Rate** und nicht die Güte: Von JPEG 60 auf
30 spart am selben Bild nur 130 → 90 KB und macht die Schrift unlesbar.
Und die Rate sinkt von selbst: Wer mehr als sechs Meldungen im Rückstand
hat, bekommt das nächste Bild nicht.

### Die Rückfrage gilt hier **nicht** — mit Absicht

Vor jedem Klick, den **Sarvis** macht, holt `hirn._browserstufe` das
Element frisch aus dem DOM und fragt gesprochen nach, wenn es ein
Formular abschickt — auch wenn „Abbrechen" darauf steht, denn das
entscheidet `el.form`, nicht die Beschriftung.

Für `klick`, `taste` und `rollen` gilt das nicht. Die Prüfung schützt
davor, dass **Sarvis** unbeabsichtigt etwas auslöst — vor einem Modell,
das seine Elementliste von einer fremden Seite hat. Klickt der Mensch
selbst auf einen Punkt in einem Bild, das er ansieht, gibt es nichts zu
schützen; eine Rückfrage hieße „willst du wirklich klicken, worauf du
gerade geklickt hast".

**Wer das später „zur Sicherheit" nachrüstet, macht die Fernsteuerung
unbenutzbar und gewinnt nichts.** Das Fehlen der Prüfung ist die
Funktion.

Was diese Freiheit trägt: Der Draht ist **authentifiziert**. `_anmelden`
läuft in `netz/server.py` vor `_empfangen`; wer keinen gültigen
Geräteschlüssel schickt, bekommt die Verbindung mit 4401 geschlossen und
erreicht die Verarbeitung nie. Ein `klick` von einer nicht angemeldeten
Verbindung ist nicht unwahrscheinlich, sondern unmöglich.

**Nicht fürs Handy.** Ein 1280 Punkte breites Fenster auf einem Telefon
ist Lupenarbeit, und Zielen mit dem Finger trifft nicht den Knopf, den
man meint. Die Weboberfläche blendet den Schalter unter 700 Punkten
Breite ganz aus. Der bessere Weg dorthin gibt es schon: die Art
`browser` schickt die **Adresse**, und die Seite geht im eigenen Browser
auf.

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
| `schirm_an` | `an` | Bildstrom von Sarvis' Browser an/aus |
| `klick` | `x`, `y`, `knopf` | dort hineinklicken |
| `taste` | `text`, `sonder` | dort tippen |
| `rollen` | `x`, `y`, `hoch` | dort scrollen |
| `auto` | `an` | die Oberfläche sitzt im Fahrzeug (siehe unten) |

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

### `radio` — Ton, den nicht Sarvis macht

```json
{ "art": "radio", "url": "https://…/stream.mp3", "name": "Deutschlandfunk" }
{ "art": "radio_aus" }
```

**Hier kommt kein Audio über den Draht, nur eine Adresse.** Einen
Radiostream durchzureichen hieße, dass der Server stundenlang Musik
herunterlädt, um sie unverändert weiterzugeben — Arbeit, Bandbreite und
Verzögerung für nichts. Der Client kann den Sender direkt anwählen.

Fünf Punkte, an denen eine App sonst am Protokoll vorbeibaut:

1. **Ein eigenes Abspielwerk, getrennt von der Sprachwiedergabe.** Nicht
   in denselben Mixer, nicht in dieselbe Warteschlange wie `ton`. Sonst
   löscht der nächste `ton_stopp` auch das Radio.
2. **Sarvis redet über das Radio, statt es abzuwürgen.** Kommt ein `ton`,
   Radio auf etwa **15 %** herunterblenden; ist der Ton verklungen,
   wieder auf. Wann das ist, weiß nur der Client: Der Server meldet nicht,
   wann sein Satz zu Ende gespielt ist — er schickt Ton, und dessen Länge
   kennt, wer ihn eingeplant hat. In der Weboberfläche steht deshalb ein
   Timer über die Dauer des eingeplanten Puffers plus 0,35 s Zugabe; ein
   `ton_stopp` dreht sofort wieder auf. **Nicht pausieren** — wer nach der
   Uhrzeit fragt, will nicht, dass die Musik aus ist.
3. **`radio` kommt nur bei `kann_radio`** (siehe „Anmelden"). Wer es nicht
   meldet, bekommt die Art nie zu sehen.
4. **`radio` geht gezielt an EIN Gerät** — das, von dem gerade gesprochen
   wird. Wie der Ton und aus demselben Grund. **`radio_aus` geht an
   alle**, wie `ton_stopp`: Läuft irgendwo noch ein Sender, soll auch der
   aufhören, auch wenn man inzwischen woanders sitzt.
5. **Beim Beenden die Quelle wirklich lösen**, nicht nur pausieren. Ein
   pausierter Stream lädt im Hintergrund weiter — unhörbar, Tag und Nacht.
   Im Browser: `src` entfernen und `load()`.

`url` ist immer **https** und nie HLS (`.m3u8`) — dafür sorgt der Server.
Beides ist eine Browser-Rücksicht: Auf einer https-Seite verweigert der
Browser http-Ton lautlos, und `.m3u8` spielt ein schlichtes
Audio-Element nur in Safari. Eine native App darf beides trotzdem
abspielen können; sie bekommt es nur nicht angeboten.

`name` ist zum Anzeigen und sonst nichts — keine Identität, kein
Schlüssel. Zweimal `radio` heißt schlicht: jetzt dieser Sender. Der
Server kürzt ihn schon (im Verzeichnis heißt ein Sender auch mal
„0R - COFFEE LOUNGE || Background Music, Jazz, Lounge, …"), er kann
aber trotzdem lang sein oder fehlen.

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
jarvis 0,83 · charvis 0,77 · sabis 0,73 · servus 0,67 · service 0,62 ·
serviert 0,57, **Grenze 0,70**). Die Grenze lag bis 09/2026 auf 0,60 und
damit unter „service" — im Auto weckte ihn die Radiowerbung. 0,70 trennt
sauber: Ein verhörter Buchstabe im Namen ergibt 0,83, zwei ergeben 0,73
bis 0,77; darunter liegt nur noch Fremdwortschatz. Sie lösen das,
woran openWakeWord scheiterte: Dessen Fertigmodelle sind auf englische
Aussprache trainiert und erreichten für „Hey Sarvis" von einer deutschen
Stimme nur 0,09 bis 0,13.

### Wenn nie eine Pause kommt: Dauerlärm

Ein Abschnitt endet normalerweise durch Stille. Im Auto kommt die nie —
das Radio redet durch. Der Abschnitt wuchs deshalb bis zur Notbremse nach
90 Sekunden, und ein „Hey Sarvis" stand dann irgendwo **mitten** in
diesem Klumpen. Geprüft wurde aber nur der Anfang. Ergebnis: Im Auto
wurde er nicht spät geweckt, sondern gar nicht.

Drei Dinge greifen jetzt ineinander:

1. **Gekappt statt gewachsen.** Kommt keine Pause, wird alle sechs
   Sekunden (`LAERM_STUECK_SEK`) trotzdem hineingehört — mit
   anderthalb Sekunden Überlappung, damit ein Weckwort nicht an der
   Schnittkante zerbricht.
2. **In einem gekappten Stück wird auch mitten im Satz gesucht** — dort
   aber ausschließlich nach *Anrede plus Name* („hey sarvis"), nie nach
   dem Namen allein, und mit der strengen Ähnlichkeit. Findet er das
   Weckwort ganz am Stückrand, wartet er einmal auf das nächste Stück,
   statt mit leerem Zuruf aufzuwachen.
3. **Der Rückstands-Deckel schont laufende Sprache.** Er warf die
   ältesten Blöcke weg — mitten im Satz also dessen Anfang, wo das
   Weckwort steht. Solange geredet wird, darf jetzt mehr auflaufen
   (`MAX_RUECKSTAND_HART`).

Im offenen Nachhörfenster wird **nicht** gekappt: Wer angesprochen wurde
und diktiert, macht Denkpausen und darf ausholen.

## Dateien hochladen

Sascha schickt aus der App etwas herüber — einen Plan als PDF, ein
Angebot als Word, eine Preisliste als Excel, eine Datei aus einem
Projekt. Sarvis liest sie und sagt, was drinsteht.

### 1. Adresse und Methode

```
POST /datei
Content-Type: multipart/form-data
```

**Multipart, nicht roher Body.** Ein Feld, und es heißt `datei`:

```
--grenze
Content-Disposition: form-data; name="datei"; filename="Angebot.pdf"
Content-Type: application/pdf

<Bytes>
--grenze--
```

Der Dateiname aus `filename` wird übernommen, gesäubert und mit einem
Zeitstempel versehen. Ein anderer Feldname als `datei` ergibt **400**.

Warum nicht über den Draht: Der trägt 4 MB je Nachricht, und base64
bläht um ein Drittel auf — eine 5-MB-Datei passt nicht mehr. In Stücke
zerlegen hieße, im Protokoll eine Zusammensetz-Logik zu führen samt der
Frage, was bei einem abgebrochenen Stück geschieht. Das kann HTTP schon.

### 2. Anmeldung

**Derselbe Geräteschlüssel wie am Draht, im Kopf:**

```
X-Sarvis-Schluessel: <derselbe Schlüssel wie bei der Draht-Anmeldung>
```

Nicht als Abfrage in der Adresse — Adressen landen in Protokollen und
im Browserverlauf, Kopfzeilen nicht.

Das ist bewusst das Gegenteil der Blätter. Die tragen keinen Schlüssel,
weil ein Download-Knopf und ein System-PDF-Viewer keine eigenen
Kopfzeilen schicken können. Beim Hochladen baut die App die Anfrage
selbst, kann also einen Kopf setzen — und muss es: Wer hochladen darf,
füllt Sarvis' Eingang und damit seinen Kontext.

Ohne oder mit falschem Schlüssel: **401**, in beiden Fällen dieselbe
Antwort und ohne Hinweis, was falsch war.

### 3. Grenzen

| | |
|---|---|
| Höchstens je Datei | **100 MB** (`config.DATEI_MAX`, seit 10.11.2026; vorher 25 MB) |
| Zu groß | **413** `{"fehler": "zu gross", "hoechstens": 26214400}` |
| Leere Datei | **400** `{"fehler": "leer"}` |
| Falsches Feld | **400** `{"fehler": "kein Feld 'datei'"}` |

Geprüft wird zweimal: erst `Content-Length`, dann beim stückweisen
Lesen mitgezählt. Ein Client ohne `Content-Length` kommt also nicht
durch die Hintertür.

**Erlaubte Endungen** — eine Positivliste (`config.DATEI_ENDUNGEN`):

- Text: `.txt .md .markdown .rst .log .csv .tsv .json .yaml .yml .toml .ini .cfg .conf .env .xml .html .htm .svg`
- Code: `.py .js .ts .tsx .jsx .css .scss .sass .less .java .kt .kts .c .h .cpp .hpp .cs .go .rs .rb .php .swift .sql .gradle .dockerfile .diff .patch`
- Dokumente: `.pdf .docx .doc .xlsx .xls .pptx .odt .ods .rtf .epub`
- Bilder: `.png .jpg .jpeg .gif .webp .bmp .heic .heif` — Sarvis **sieht** sie (`datei_lesen` liefert ein Bild, kein Text)
- Seit 10.11.2026 außerdem: `.zip .ics .vcf .gpx .kml .kmz .ppt .odp`, Audio `.mp3 .m4a .ogg .opus .wav .aac .flac`, Video `.mp4 .mov .webm .3gp .mkv` — angenommen und weiterschickbar, aber nicht hineingelesen

Alles andere: **415** `{"fehler": "diese Art Datei nehme ich nicht", "endung": ".sh"}`

Ausführbares steht bewusst nicht drin — `.exe`, `.sh`, `.bat`, `.ps1`.
Sarvis kann Programme starten; eine Datei von außen, die ausgeführt
werden könnte, ist ein Weg zu weit. Die Antwort nennt die abgelehnte
Endung, damit unterscheidbar bleibt, ob etwas wirklich unerwünscht ist
oder ob nur niemand daran gedacht hat.

### 4. Was zurückkommt

```json
{ "gut": true, "name": "2026-09-02-1933-Angebot.pdf", "bytes": 128442 }
```

**`name` ist die Kennung.** Unter diesem Namen liegt die Datei im
Eingang, und darauf zeigt Sarvis im Gespräch. Der Zeitstempel steht
vorn, damit der Ordner sich chronologisch sortiert und zwei Dateien
namens „Angebot.pdf" von verschiedenen Tagen einander nicht
überschreiben — was der Normalfall ist, nicht die Ausnahme.

Die App kann den Namen anzeigen („liegt bei Sarvis als …") oder ihn
schlicht verwerfen; nötig ist er nicht.

### Was danach passiert

Sarvis **liest die Datei nicht von selbst vor.** Wer eine Datei
schickt, tut das meistens mitten in einem Satz und will danach etwas
Bestimmtes wissen. Ein Assistent, der ungefragt eine Preisliste
vorträgt, ist eine Zumutung.

Er erfährt nur, dass sie da ist: Beim nächsten Zuruf steht eine Zeile
in seinem Vorspann (`[Gerade angekommen: … ]`). Fragt Sascha dann
etwas, liest Sarvis mit `datei_lesen` hinein. Der Name muss dabei nicht
stimmen — „schau mal ins Angebot von Müller" findet `Angebot.docx`,
„lies mir den Wartungsbericht vor" findet `bericht.pdf`.

Der Eingang hält die **60 jüngsten** Dateien; darüber fällt die älteste
weg. Die App muss also nichts aufräumen.

## Dateien abholen (seit 10.11.2026)

Sarvis schickt Dateien mit dem Werkzeug `datei_schicken` — selbst
Erzeugtes **und** jede Datei vom Server (Benutzerordner, Projekte,
Sarvis' Daten; ein Ordner kommt als ZIP). Am Draht ist das nichts Neues:
ein `blatt` der Sorte `datei`, wie bei `dokument_erstellen`. Neu sind
zwei Dinge.

### 1. Jede Dateiart, nicht nur PDF/Word/Excel

`datei` kann jetzt **jeder** Dateiname sein (`foto.jpg`, `Plan.zip`,
`README.md`). Die Oberfläche bietet ihn zum Herunterladen an wie bisher.
Endet `datei` auf `.jpg .jpeg .png .gif .webp .bmp`, **darf** sie das
Bild zusätzlich als Vorschau zeigen — dieselbe `adresse` als Bildquelle.
Ausgeliefert wird immer als Anhang (`Content-Disposition: attachment`),
HTML/SVG/JS nie mit ihrem echten Typ.

Frist: Verschicktes bleibt **30 Tage** abrufbar (Berichte weiter 7).

### 2. Die Dateiliste: `GET /dateien`

Ein Blatt geht nur an Oberflächen, die **gerade verbunden** sind. Was
kam, während die App zu war, holt sie hier ab — beim `willkommen` und
nach jedem Datei-Blatt.

```
GET /dateien
X-Sarvis-Schluessel: <Geräteschlüssel>
```

```json
{
  "von_sarvis": [
    {"kennung": "…", "titel": "Angebot Müller", "datei": "Angebot.pdf",
     "adresse": "/blatt/…", "bytes": 48211, "seit": 1794350000.1,
     "bis": 1796942000.1}
  ],
  "von_dir": [
    {"datei": "2026-11-10-2205-Plan.pdf", "bytes": 226503,
     "seit": 1794350000.0}
  ]
}
```

- `von_sarvis`: neueste zuerst, nur noch gültige, ohne Berichte (`html`).
  `adresse` wie beim Blatt — ohne Schlüssel abrufbar, Schutz ist die Kennung.
- `von_dir`: was in Sarvis' Eingang liegt (höchstens 60), **ohne**
  Download-Adresse — nur zur Anzeige.
- `seit`/`bis` sind Unix-Sekunden. Was „neu“ ist, merkt sich die
  Oberfläche selbst (die Web-App: `localStorage` `sarvis-dateien-gesehen`).
- Ohne/falscher Schlüssel: **401** `{"fehler": "kein Zugang"}`.

## Teilen aus dem Handy-Menü (Web-App)

Die PWA trägt im Manifest ein `share_target` (`POST /teilen`,
multipart, Dateifeld `dateien`, dazu `title`/`text`/`url`). Der Service
Worker — seit 10.11.2026 an der **Wurzel** (`/waechter.js`, Scope `/`) —
fängt den POST ab, legt die Dateien in den Cache `sarvis-teilen` und
leitet auf `/?geteilt=1`; die Seite lädt sie mit Schlüssel über
`POST /datei` hoch. Geteilter Text landet im Eingabefeld, nicht als
Zuruf. Kommt der POST doch beim Server an (Worker noch nicht aktiv),
antwortet er **303** nach `/?geteilt=verpasst` und nimmt nichts an —
dort fehlt der Schlüssel.

Eine native App braucht das nicht: Sie meldet sich selbst als
Teilen-Ziel an (Android `ACTION_SEND`/`ACTION_SEND_MULTIPLE`) und lädt
direkt über `POST /datei`.

### `auto` — die Oberfläche sitzt im Fahrzeug

```json
{ "art": "auto", "an": true }
```

Wird bei jedem Wechsel geschickt und einmal direkt nach dem `willkommen`
(bei der Anmeldung allein reicht es nicht — ein- und ausgestiegen wird
mitten in einer Verbindung, oft Stunden später).

Die Nachricht lockert genau eine Sache: die **Suche** nach dem Weckwort.
Im Auto darf es auch mitten im Satz stehen, nicht nur am Anfang — auch
wenn der Lärm gerade nicht laut genug für einen Schnitt war. Am
Schreibtisch bleibt es bei der strengen Regel.

Was sie ausdrücklich **nicht** tut: den Schnitt erzwingen. Wo geschnitten
wird, entscheidet allein die Messung (kommt eine Pause oder nicht). Das
Signal sagt, wo das Handy steckt, nicht wie laut es dort ist — und im
Auto mit ausgeschaltetem Radio ist es still. Würde es den Schnitt
steuern, wäre ausgerechnet unterwegs kein Diktat mehr möglich.

Die Nachricht ist rückwärtskompatibel: Ein Server, der sie nicht kennt,
ignoriert sie (siehe „Rahmen").

**Damit hat eine Android-App wieder einen Grund**: Ein Foreground Service
darf das Mikrofon offenhalten, wenn der Bildschirm gesperrt ist — ein
Browser im Hintergrund nicht.

Blockgröße für den VAD: **genau 480 Werte** bei 16 kHz. Silero rechnet in
Rahmen dieser Größe; eine andere Blockung verfälscht seine Vorhersage.
Opus kennt kein 30-ms-Frame (2,5/5/10/20/40/60 ms) — wer über Opus
schickt, muss serverseitig neu blocken. Das ist eine Zeile, die man
vergisst, und sie fällt nicht auf: Der VAD sagt dann nicht „Fehler", er
sagt nur öfter das Falsche.
