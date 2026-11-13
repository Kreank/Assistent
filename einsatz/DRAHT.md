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
| `blatt` | `kennung`, `sorte`, `titel`, `adresse`, `inhalt`, `datei`, `bytes`, `sekunden`; optional `mime`, `seiten`, `pdf`, `vorschau` | etwas zum Lesen |
| `blatt_weg` | `kennung` | Blatt zuklappen |
| `geplant` | `eintraege` | Timer und geplante Aufgaben — immer die ganze Liste, Form wie `GET /geplant` |
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
| `eintrag` | `faden`, `id`, `zeit`, `wer`, `sorte`, `text`, `daten`, `geraet` | ein Eintrag im Gesprächsverlauf, neu oder geändert (seit 11.11.2026) |
| `faeden` | `aktiv`, `liste`, `wechselt` | welche Gesprächsfäden es gibt und welcher gilt (seit 11.11.2026) |

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
eine Zeile. Vier Sorten, ein Kasten:

| `sorte` | wo der Inhalt steckt | wie er gezeigt wird |
|---|---|---|
| `markdown` | `inhalt`, mit der Nachricht | die Oberfläche setzt ihn |
| `html` | `adresse` → `/blatt/<kennung>` | in einem Rahmen |
| `datei` | dito, plus `datei` und `bytes` | ein Knopf zum Herunterladen |
| `seite` | `adresse` → eine **Webseiten-Vorschau** (seit 13.11.2026) | eingebettet **mit** JavaScript, dazu „Im Browser öffnen“ |

**`seite` ist die einzige Ausnahme von den Regeln unten** und genau
begrenzt: `adresse` muss auf
`^https://test\.tech-artist\.de/(vorschau|offen)/[a-z0-9-]+/$` passen,
sonst wird nichts angezeigt. Dort liegen nur Seiten, die Sarvis aus
Saschas Projekten gebaut hat (`werkzeug vorschau_zeigen`). Weil eine
React-Seite ohne Skripte weiß bleibt, darf **dieser** Rahmen Skripte
ausführen — er gehört einer anderen Herkunft (test.tech-artist.de) und
kommt deshalb nicht an den Geräteschlüssel dieser Oberfläche. Unter
`/vorschau/` fragt der Server nach Benutzer und Passwort (Basic Auth);
bietet der eingebettete Rahmen das nicht an, bleibt „Im Browser
öffnen“. `/offen/` braucht nichts.

`kennung` ist die **Identität**, wie `name` bei der Kachel: Zweimal
dieselbe heißt dasselbe Blatt mit neuem Inhalt, nicht zwei
übereinander. `sekunden` ist die Lebensdauer, 0 heißt „bis
`blatt_weg`".

**`adresse` ist immer ein Pfad auf diesen Server**, beginnend mit
`/blatt/` (Ausnahme nur `seite`, siehe oben). Nie eine fremde Adresse — und eine Oberfläche, die etwas
anderes bekommt, zeigt es nicht an. Der Draht ist authentifiziert, was
über ihn kommt, ist trotzdem aus Modellausgabe gebaut.

### Begleitfelder an `html`/`datei` (seit 13.11.2026)

Auf Wunsch der Android-App (`WUNSCH-APP-DOKUMENTE-2026-11-13.md`). Sie
stehen **gleich benannt** im `blatt`, in seinem Verlaufseintrag
(`daten`), in `GET /dateien` (`von_sarvis`), in `GET /ablage`
(`eintraege`) und in `POST /ablage/oeffnen`:

| Feld | Inhalt | wann |
|---|---|---|
| `bytes` | Größe der ausgelieferten Datei | **immer**, auch bei `html` |
| `mime` | echter Typ, z. B. `application/pdf`, `text/html`, `image/jpeg` | immer |
| `seiten` | Seitenzahl (Zahl) | PDF und Office mit PDF-Fassung |
| `pdf` | `/blatt/<k>` der PDF-Fassung | nur Office (`docx`, `doc`, `odt`, `rtf`, `xlsx`, `xls`, `ods`, `pptx`, `ppt`, `odp`) |
| `vorschau` | `/blatt/<k>` eines **PNG**, höchstens 480 px breit | PDF/Office: erste Seite · Bild: verkleinert · Video: Standbild bei 1 s · `html`: Bildschirmfoto 480 × 720 aus einem eigenen, netzlosen Chrome |

- **Jedes Feld außer `bytes`/`mime` kann fehlen** (Umwandlung ging nicht,
  Art ohne Vorschau, z. B. ZIP, CSV, Text). Dann Typ-Symbol, kein Fehler.
  Ist die Datei selbst ein PDF, gibt es kein `pdf`.
- `pdf` und `vorschau` sind eigene Blätter: 192 Bit Zufall, **dieselbe
  Frist wie das Dokument**, `POST /ablage/oeffnen` verlängert sie mit
  (oder baut sie neu, wenn sie schon weggeräumt waren). Sie tauchen nie
  als eigener Eintrag in `/dateien` oder in der Ablage auf.
- `pdf` kommt als Anhang (`Content-Disposition: attachment`, Typ
  `application/pdf`), `vorschau` inline als `image/png` — taugt also auch
  für ein `<img>`.
- „Öffnen mit …", „Teilen", „In Downloads speichern" nehmen weiter
  `adresse` (das Original).
- **Kennung = letztes Stück der Adresse.** Bei `blatt`-Einträgen der
  Sorte `html`/`datei` gilt immer `adresse == "/blatt/" + kennung`, und in
  der Ablage ist `schluessel` dieselbe Kennung. Für den Cache der App
  also die `kennung` nehmen.

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
| `faden_neu` | `titel` | ein neues Gespräch anfangen, es wird aktiv |
| `faden_wechseln` | `faden` | in ein anderes Gespräch wechseln |
| `faden_umbenennen` | `faden`, `titel` | einem Gespräch einen Namen geben |
| `faden_archivieren` | `faden`, `an` | ins Archiv legen (`an: false` holt zurück) |
| `formular_antwort` | `eintrag`, `antworten` | ein ausgefülltes Formular abschicken (seit 13.11.2026) |

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
     "bis": 1796942000.1, "mime": "application/pdf", "seiten": 3,
     "vorschau": "/blatt/…"}
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

---

## Gesprächsverlauf und Fäden (seit 11.11.2026)

Bis hierhin zeigte eine Oberfläche genau **eine** Untertitelzeile; was
vorher gesagt wurde, war weg. Jetzt führt der Server den Verlauf selbst
(SQLite, `/srv/data/sarvis/gespraeche.db`, `sarvis/gespraeche.py`), in
**Fäden**: getrennten Gesprächen wie in einem Messenger.

### Das Modell

- Ein **Faden** ist ein Gespräch mit eigenem Kontext. Technisch ist er
  eine SDK-Sitzung des Hirns; beim Wechsel wird sie mit `resume` wieder
  aufgenommen (gemessen: unter 1 s). Das **Gedächtnis** (gemerkt,
  entschieden, Personen) gilt über alle Fäden hinweg.
- Es gibt **genau einen aktiven Faden für alle Oberflächen**. Es gibt nur
  ein Hirn: Was per Weckwort, Taste oder Zuruf kommt, landet im aktiven
  Faden, egal von welchem Gerät. Wer wechselt, wechselt überall.
- Ein Neustart des Dienstes nimmt den zuletzt aktiven Faden wieder auf.
  Er ist also kein neues Gespräch mehr.

### `faeden` — die Liste

```json
{ "art": "faeden", "aktiv": "f-4aa4788c777c", "wechselt": false,
  "liste": [ { "id": "f-4aa4788c777c", "titel": "Urlaub planen",
               "angelegt": 1794392519.6, "zuletzt": 1794392990.1,
               "archiviert": false, "eintraege": 14 } ] }
```

Kommt **gleich nach dem `willkommen`**, nach jedem Wechsel, Umbenennen,
Archivieren und nach jedem Zuruf (der Titel kann sich ändern, die
Reihenfolge auch). Immer die ganze Liste, zuletzt benutzte zuerst — ein
Zustand, keine Änderung.

- `titel` leer heißt: noch unbenannt. Anzeigen als „Neues Gespräch“. Der
  erste Zuruf gibt ihm sofort einen vorläufigen Titel (seine ersten
  Wörter); wenige Sekunden später benennt Sarvis das Gespräch selbst und
  schickt eine neue `faeden`-Liste. Beides nur, solange es niemand von Hand
  benannt hat — ein Mensch gewinnt immer.
- `wechselt: true` steht zwischen „Befehl angenommen“ und „Hirn ist im
  neuen Faden“. Danach kommt dieselbe Liste mit `false`. Zeigen, nicht
  blockieren: Ein Zuruf in dieser Zeit wartet auf dem Server.
- Ein leerer Faden (kein Eintrag) verschwindet, sobald man ihn verlässt.

### `eintrag` — was im Faden geschieht

```json
{ "art": "eintrag", "faden": "f-…", "id": 812, "zeit": 1794392990.1,
  "wer": "sarvis", "sorte": "text", "text": "Morgen wird es sonnig.",
  "daten": {}, "geraet": "" }
```

**`id` ist die Identität.** Kommt dieselbe `id` noch einmal, ist es
derselbe Eintrag mit neuem Stand — ersetzen, nicht anhängen. Die `id`
steigt über alle Fäden hinweg; innerhalb eines Fadens ist sie die
Reihenfolge.

Einträge eines **anderen** als des aktiven Fadens: ignorieren (sie kommen
nur in der Wechselsekunde vor).

| `wer` | `sorte` | `text` | `daten` |
|---|---|---|---|
| `du` | `text` | was gesagt oder getippt wurde (Whisper-Ergebnis) | `{}` |
| `du` | `datei` | Dateiname im Eingang | `datei`, `bytes` |
| `sarvis` | `text` | die ganze Antwort, wie gesprochen | `{}`, oder `unterbrochen: true`, wenn reingeredet wurde (dann nur der Teil bis dahin) |
| `sarvis` | `meldung` | von selbst gesagt: Timer, fertiger Auftrag | `{}` |
| `sarvis` | `frage` | die Rückfrage vor einer Handlung | `offen`, `werkzeug`; geschlossen zusätzlich `entscheidung` (`ja`·`nein`·`anders`·`abgebrochen`) und `antwort` (Wortlaut) |
| `sarvis` | `blatt` | Titel | alle Felder des `blatt` (`kennung`, `sorte`, `titel`, `adresse`, `inhalt`, `datei`, `bytes`, dazu die Begleitfelder `mime`, `seiten`, `pdf`, `vorschau`, soweit vorhanden) |
| `sarvis` | `auftrag` | Statuskarte eines Hintergrundauftrags, mehrzeilig (Laufzeit, Aufgabe, zuletzt erledigt, als Nächstes) — **dieselbe `id` wird laufend ersetzt** | `nummer`, `zustand` (`läuft`, `fertig`, `gestoppt`, `abgebrochen`), `projekt`; seit 13.11.2026 zusätzlich `seit` (Start, Unix-Sekunden), `schritte` (Modellzüge bisher), `pensum` (Höchstzahl, derzeit 250) — **können fehlen**, dann unbestimmter Balken |
| `sarvis` | `formular` | Titel | `kennung`, `fragen` (Liste aus `nr`, `titel`, `frage`), `auftrag`, `projekt`, `offen`, nach dem Abschicken `antworten` (`{"<nr>": "Text"}`) |
| `sarvis` | `kachel` | Kopfzeile | alle Felder der `kachel` außer `sekunden` |
| `system` | `text` | Hinweis des Systems („keine Antwort — …“) | `{}` |
| `system` | `text` | „Geplante Aufgabe 7: …“ — eine geplante Aufgabe ist fällig und läuft; die Antwort folgt als `sarvis`/`text` (seit 13.11.2026) | `{}` |

`geraet` ist bei `du` das Gerät, von dem es kam; sonst leer.

**Wann kommt was.** Der Zuruf kommt, sobald er verstanden ist; die
Antwort kommt **als Ganzes**, wenn sie fertig formuliert ist — während
gesprochen wird, gibt es weiter `untertitel`. Eine Oberfläche, die beides
hat, zeigt den Untertitel als vorläufige Blase und ersetzt sie durch den
`eintrag`. (Die Web-App: `#live`, gelöscht bei `eintrag` von `sarvis` oder
`zustand: ruhig`.)

**Karten.** Blatt und Kachel kommen weiterhin als `blatt`/`kachel` für die
Bühne — und zusätzlich als `eintrag`, damit sie im Verlauf stehen bleiben.
Dieselbe Kachel (`name`) oder dasselbe Blatt (`kennung`) mehrmals im selben
Zug ist **ein** Eintrag mit neuem Stand. Zustandskacheln (`sorte: zustand`)
kommen nicht in den Verlauf. Die Regeln der Bühne gelten auch in der
Karte: **Kacheln nicht anklickbar**, `adresse` nur `/blatt/…`, Markdown
nur über den eigenen Wandler, nie als HTML.

Ein Blatt der Sorte `html`/`datei` im Verlauf öffnet man über
`POST /ablage/oeffnen` mit `schluessel` = `daten.kennung` (siehe
„Ablage“) — die Adresse kann abgelaufen sein. Markdown steht vollständig
in `daten.inhalt`.

**Rückfragen mit Knopf.** Solange `daten.offen` wahr ist, darf die
Oberfläche **Ja** und **Nein** anbieten. Ein Knopf schickt einen
**gewöhnlichen Zuruf** `{ "art": "zuruf", "text": "Ja" }` bzw. `"Nein"` —
dieselbe Antwort, als wäre sie gesagt worden; der Server deutet sie wie
gesprochen. Es gibt dafür keine eigene Art und keine Abkürzung an den
Stufen vorbei. Danach kommt derselbe Eintrag mit `offen: false`.

### Hinaus: die Fadenbefehle

```json
{ "art": "faden_neu" }                       // optional "titel"
{ "art": "faden_wechseln", "faden": "f-…" }
{ "art": "faden_umbenennen", "faden": "f-…", "titel": "Urlaub" }
{ "art": "faden_archivieren", "faden": "f-…", "an": true }
```

- `faden_neu` ohne `titel`, während der aktive Faden noch leer ist:
  passiert nichts (ein zweiter leerer daneben wäre Müll). Sonst entsteht
  ein neuer und wird aktiv.
- `faden_wechseln` und `faden_neu` **unterbrechen** eine laufende Antwort
  und eine offene Rückfrage — sie gehören zum alten Faden.
- `faden_archivieren` mit dem aktiven Faden: Er geht ins Archiv, und ein
  neuer, leerer wird aktiv. Ein archivierter Faden, in den man wechselt,
  kommt von selbst aus dem Archiv.
- `faden_umbenennen` mit leerem `titel` gibt den Namen an die Automatik
  zurück. Höchstens 80 Zeichen.
- Antwort ist immer ein `faeden` an alle. Unbekannte Fäden: still nichts.

### Formulare (seit 13.11.2026)

Hat ein Auftrag offene Fragen an Sascha (Abschnitt „Offene Fragen an
Sascha“ in seinem Bericht), legt Sarvis sie als **`eintrag` mit `sorte:
formular`** in den Verlauf. Eine eigene Draht-Art gibt es dafür nicht.

Solange `daten.offen` wahr ist: je Frage ein Eingabefeld (Beschriftung
`titel`, darunter klein `frage`), dazu „Absenden“. Abschicken:

```json
{ "art": "formular_antwort", "eintrag": 812,
  "antworten": { "1": "kontakt@…", "2": "", "3": "Sascha …" } }
```

Leere Antwort heißt „weiß ich noch nicht“. Der Server setzt `offen` auf
`false`, legt `antworten` dazu (der Eintrag kommt als `eintrag` mit
derselben `id` neu) und gibt die Antworten als Folgeauftrag weiter.
Ein zweites Abschicken desselben Formulars wird still übergangen.
Wie `zuruf` gehört `formular_antwort` in die Warteschlange, solange die
Leitung nicht steht.

**Seit 13.11.2026 (abends): Antwortarten, Rückfragen, später beantworten.**

Jede Frage in `daten.fragen` kann zusätzlich tragen (fehlt es: wie oben,
Freitext):

| Feld | Werte | Bedeutung |
|---|---|---|
| `typ` | `text` (Vorgabe) · `einfach` · `mehrfach` · `janein` · `zahl` · `datum` | wie man antwortet |
| `optionen` | Liste, höchstens 8, je ≤ 60 Zeichen | bei `einfach`/`mehrfach` |
| `frei` | bool | zusätzlich „Anders: …“ mit Textfeld |
| `vorschlag` | String, bei `mehrfach` Liste | vorbelegt |
| `pflicht` | bool | ohne Antwort kein Abschicken |

Antworten: `text`/`einfach`/`zahl`/`datum` (ISO `2026-11-20`)/`janein`
(`"ja"`/`"nein"`) als **String**, `mehrfach` als **Liste** (höchstens 20,
je ≤ 200 Zeichen). „Anders“ steht als Wert bzw. als weiteres
Listenelement. Leer heißt „weiß ich noch nicht“.

- `daten.zweck`: `"rueckfrage"` (Sarvis fragt im Gespräch, Werkzeug
  `fragen_stellen`) oder `"auftrag"` (offene Fragen eines Arbeiters;
  fehlt das Feld: `"auftrag"`). Rückfragen gehen als gewöhnlicher Zuruf
  („Meine Antworten auf „…“: 1. Farben: Blau, Grün …“) an das Gespräch,
  **nicht** als Folgeauftrag.
- `daten.erledigt`, sobald `offen` falsch ist: `"beantwortet"` oder
  `"anders"`. **`anders`** heißt: Sascha hat gesprochen oder frei getippt,
  während ein Rückfrage-Formular offen war; dann schließt der Server alle
  offenen **Rückfrage**-Formulare des aktiven Fadens. Grau zeigen, nicht
  mehr ausfüllbar. Auftrags-Formulare bleiben offen.
- **`formular_antwort` findet das Formular über `eintrag` in jedem
  Faden**, auch Tage später. Steht es in einem anderen als dem aktiven
  Faden, wechselt der Server zuerst dorthin (es kommt `faeden` mit
  `wechselt`), dann folgt der Zuruf.
- Im Auto (`auto` an) und ohne verbundenen Bildschirm legt Sarvis keine
  Rückfrage-Formulare hin, sondern fragt mündlich.

### HTTP: Verlauf nachladen und durchsuchen

Alles mit `X-Sarvis-Schluessel` im Kopf, ohne: **401** `{"fehler": "kein Zugang"}`.

```
GET /faeden                     → { "aktiv": "f-…", "liste": [ … wie oben … ] }
GET /verlauf?faden=f-…&anzahl=60&vor=812
    → { "faden": { id, titel, angelegt, zuletzt, archiviert, eintraege },
        "eintraege": [ … wie der Draht, ohne "art", ALT → NEU … ],
        "mehr": true }
GET /suche?q=urlaub             → { "treffer": [ { …eintrag…, "faden_titel": "…" } ] }
```

- `faden` weggelassen = der aktive. Unbekannt: **404**.
- `anzahl` 1–200 (Vorgabe 60). `vor` = eine `id`: nur ältere. Mit `mehr`
  weiß man, ob es noch ältere gibt — „Ältere laden“ nimmt die kleinste
  `id`, die man hat.
- **Wann holen:** nach jedem `willkommen` (was kam, während die Leitung weg
  war, steht nur dort) und wenn `faeden.aktiv` sich ändert. Was während
  des Holens schon per Draht kam, nicht wegwerfen: Einträge mit höherer
  `id` als der letzte geholte behalten.
- `/suche` sucht ab zwei Zeichen in Zurufen, Antworten, Meldungen und
  Rückfragen aller Fäden, neueste zuerst, höchstens 40.

## Ablage (seit 11.11.2026)

Alles, was Sarvis erzeugt hat — Blätter (Markdown), Berichte (HTML),
Dateien —, mit dem Faden, in dem es entstand. Was schon vor dem
11.11.2026 in `blaetter.json` stand, ist übernommen. `GET /dateien` bleibt
unverändert für Apps, die es schon nutzen.

```
GET /ablage                 (optional ?sorte=markdown|html|datei)
→ { "eintraege": [ { "schluessel": "…", "sorte": "markdown|html|datei",
                     "titel": "…", "datei": "…", "bytes": 48211,
                     "faden": "f-…", "faden_titel": "…", "eintrag": 812,
                     "seit": 1794350000.1, "geaendert": …,
                     "vorhanden": true } ],
    "von_dir": [ { "datei": "…", "bytes": …, "seit": … } ] }

POST /ablage/oeffnen        { "schluessel": "…" }
→ markdown: { "sorte": "markdown", "titel": "…", "inhalt": "…" }
→ sonst:    { "sorte": "html|datei", "titel", "datei", "bytes",
              "adresse": "/blatt/…", "bis": 1796984619.1,
              "mime", "seiten"?, "pdf"?, "vorschau"? }
→ 404 unbekannt · 410 {"fehler": "liegt nicht mehr da"}
```

- **Die Adresse unter `/blatt/` läuft ab** (Berichte 7, Dateien 30 Tage).
  Die Ablage nicht. `POST /ablage/oeffnen` gibt **dieselbe** Kennung mit
  neuer Frist zurück, solange die Datei noch auf der Platte liegt —
  deshalb mit Schlüssel. Danach wie ein Blatt: `html` im Rahmen ohne
  `allow-scripts`, `datei` als Download.
- `vorhanden: false` heißt: Die Datei ist weg (alte Berichte räumt
  `bericht._aufraeumen` nach einer Weile ab). Zeigen, aber nicht
  antippbar machen.
- `schluessel` ist bei `html`/`datei` die geheime Blatt-Kennung, bei
  Markdown `md-<eintrag>`. Die Liste ist also vertraulich wie `/dateien`.

### Formulare in der Ablage (seit 13.11.2026)

`GET /ablage` (auch `?sorte=formular`) führt jedes Formular mit
`sorte: "formular"`, `schluessel: "fm-<eintrag>"`, `titel`, `seit`,
`faden`, `eintrag`, dazu **`offen`** (bool) und **`fragen`** (Anzahl).
**Offene stehen vorn**, danach wie gehabt neueste zuerst.

```
POST /ablage/oeffnen  { "schluessel": "fm-812" }
→ { "sorte": "formular", "titel": "…", "eintrag": { …der ganze Verlaufseintrag… } }
```

Beantwortet wird wie im Chat mit `formular_antwort` und der
`eintrag`-Nummer.

### Abhaken in Markdown-Blättern (seit 13.11.2026)

Aufgabenzeilen (`- [ ] …`, `- [x] …`, auch `* `, `+ `, `1. `) zeigt die App
als Kästchen. Antippen:

```
POST /blatt/haken   { "schluessel": "md-<eintrag>", "zeile": 7, "an": true }
→ 200 { "gut": true, "inhalt": "<das ganze neue Markdown>" }
→ 404 unbekannt · 409 { "fehler": "…", "inhalt": "<aktueller Inhalt>" }
```

- `zeile` zählt ab 0 im `inhalt`, wie die App ihn bekommen hat. Steht
  dort keine Aufgabenzeile mehr: **409**, den mitgeschickten `inhalt`
  zeigen.
- Der Server ändert nur `[ ]`↔`[x]` in dieser Zeile, speichert in der
  Ablage und schickt den Blatt-`eintrag` mit derselben `id` an alle
  Geräte. Sarvis liest den Stand mit `blatt_lesen`.
- Mit `X-Sarvis-Schluessel`.

## Geplant — Timer und geplante Aufgaben (seit 13.11.2026)

Zwei Sorten Eintrag in einer Liste: `timer` sagt beim Fälligwerden einen
Satz („Dein Timer ist abgelaufen: die Nudeln“), `aufgabe` führt einen
Auftrag aus — Sarvis macht dann einen ganzen Zug, als hätte Sascha ihn
gerade gesagt (im Verlauf als `system`-Zeile „Geplante Aufgabe …“, danach
die Antwort an **alle** Geräte plus Push „Geplant“). Läuft gerade ein
Gespräch, wartet die Aufgabe, bis es ruhig ist; sie unterbricht nie.

**Kein Ablaufdatum.** Wiederkehrende Einträge stellen sich nach jedem
Termin neu und überstehen Neustarts (`timer.json`). Angelegt wird **nur
beim Sprechen** („jeden Morgen um sieben ein Briefing“) — die App braucht
keinen eigenen Weg zum Anlegen.

```
GET  /geplant                         (X-Sarvis-Schluessel)
→ { "eintraege": [ { "nummer": 7, "sorte": "timer" | "aufgabe",
                     "was": "Morgenbriefing: …",
                     "faellig": 1794466800.0, "wiederholt": "taeglich"
                       | "woechentlich" | "monatlich" | null,
                     "pausiert": false, "zuletzt": 1794380400.0 | null } ] }

POST /geplant/loeschen   { "nummer": 7 }             → { "gut": true } · 404
POST /geplant/pausieren  { "nummer": 7, "an": true } → { "gut": true } · 404
```

- **`nummer` bleibt** über Wiederholungen und Neustarts dieselbe.
- `faellig` ist der nächste Termin; `zuletzt` der letzte tatsächlich
  ausgeführte (bei Timern und bei nie ausgeführten Aufgaben `null`).
- Pausiert: Ein wiederkehrender Eintrag überspringt seine Termine, ein
  einmaliger wartet und kommt sofort, wenn er wieder an ist.
- Löschen und Pausieren sind Handlungen des Menschen in seiner eigenen
  App — **ohne Rückfrage**, sofort.

Nach **jeder** Änderung (anlegen, löschen, pausieren, Termin vorbei) kommt
auf dem Draht die ganze Liste, ein Zustand wie `faeden`:

```json
{ "art": "geplant", "eintraege": [ … wie oben … ] }
```

## Gedächtnis ansehen und löschen (seit 13.11.2026)

Dieselben Daten, die Sarvis mit `gedaechtnis_zeigen`/`vergessen` benutzt.
Vertraulich wie `/dateien`, also mit Schlüssel.

```
GET  /gedaechtnis
→ { "gemerkt":     [ { "id": "g-…", "text": "…", "seit": 1794… } ],
    "beobachtet":  [ { "id": "b-…", … } ],
    "entschieden": [ { "id": "e-…", … } ],
    "personen":    [ { "id": "p-mueller", "name": "…", "text": "…",
                       "seit": … } ] }

POST /gedaechtnis/vergessen  { "id": "…" }  → { "gut": true } · 404
```

- **`gemerkt`** hat Sascha ausdrücklich gesagt (gilt als Tatsache),
  **`beobachtet`** hat Sarvis geschlossen (Vermutung — so anzeigen),
  **`entschieden`** sind Entscheidungen mit `[thema: …]` am Ende.
- `id` ist ein Hash der Zeile, keine laufende Nummer: Wird die Zeile
  geändert, ist es eine neue `id`. Nach dem Löschen die Liste neu holen.
- `seit` ist das Datum am Anfang des Eintrags (0, wenn keins dasteht).
- Eine **Person** zu löschen löscht ihre ganze Akte (`text` ist die Akte,
  höchstens 4000 Zeichen).
- Sarvis erfährt es beim nächsten Zug („gilt nicht mehr“) — auch wenn der
  Eintrag noch in seiner laufenden Sitzung steckt.

## Benachrichtigungen bei geschlossener App (Web Push, seit 11.11.2026)

Ein Timer, eine Erinnerung oder ein fertiger Hintergrundauftrag erreicht
jetzt auch ein Gerät, auf dem Sarvis gerade nicht offen ist. Verfahren:
Standard-Web-Push (RFC 8030/8291/8292) mit VAPID. Der private Schlüssel
liegt in `/srv/data/sarvis/vapid_privat.pem` (0600).

```
GET  /push/schluessel   → { "schluessel": "<VAPID-Public-Key, base64url>",
                            "abos": 1 }              // Abos DIESES Geräts
POST /push/abo          Body: PushSubscription.toJSON()
                        { "endpoint": "https://fcm.googleapis.com/…",
                          "keys": { "p256dh": "…", "auth": "…" } }
                        → { "gut": true } · 400 { "fehler": "…" }
POST /push/abmelden     { "endpoint": "…" } → { "gut": true, "entfernt": 1 }
POST /push/probe        → { "gesendet": 1, "fehler": 0, "entfernt": 0 }
```

Alle vier mit `X-Sarvis-Schluessel`. Ein Abo gehört zu dem Gerät, dessen
Schlüssel es angemeldet hat; wird das Gerät widerrufen, bekommt es nichts
mehr (das Abo verschwindet beim nächsten Versand). Meldet der Push-Dienst
404/410, ist das Abo erloschen und wird gelöscht — die App meldet es beim
nächsten Start einfach neu an (die Web-App tut das bei jedem `willkommen`).

**Erlaubte Push-Dienste** (`config.PUSH_DIENSTE`): `fcm.googleapis.com`,
`updates.push.services.mozilla.com`, `push.apple.com`,
`notify.windows.com` und deren Unterdomänen, nur https auf 443. Sonst
**400** `{"fehler": "dieser Push-Dienst ist nicht erlaubt"}`. Grund: Der
Server POSTet von sich aus an diese Adresse; ohne Liste ließe er sich an
beliebige Ziele schicken.

**Was ankommt** (nach dem Entschlüsseln, UTF-8-JSON):

```json
{ "titel": "Timer abgelaufen", "text": "Wäsche aufhängen",
  "art": "wecker", "zeit": 1794392990.1 }
```

`art`: `wecker` (Timer, Erinnerung), `auftrag` (Hintergrundauftrag fertig,
abgebrochen, gescheitert), `probe`, `meldung` (sonstiges). Nur was auf
einen Sperrbildschirm gehört — keine Kontostände, keine Mailtexte.

**Der Service Worker** (`/waechter.js`) zeigt die Meldung — außer ein
Sarvis-Fenster ist sichtbar **und** im Vordergrund (dann hat man es
gehört und sieht es im Verlauf). Die Probe zeigt immer. Antippen öffnet
bzw. holt die App nach vorn. `wecker` bleibt stehen, bis man ihn
wegwischt.

Gesendet wird immer an alle Abos, auch wenn gerade eine Oberfläche
verbunden ist: „Verbunden“ heißt bei einem Handy in der Tasche nicht,
dass jemand hinsieht. Ob gezeigt wird, entscheidet das Gerät.

**iPhone:** Web Push geht nur, wenn Sarvis als Web-App auf dem
Home-Bildschirm liegt (iOS 16.4+). **Native Apps** nutzen dieselben
Wege, wenn sie einen Web-Push-fähigen Dienst haben (z. B. UnifiedPush);
dessen Host gehört dann in `config.PUSH_DIENSTE`.

Prüfen ohne Browser: `einsatz/push_pruefen.py` (verschlüsselt, schickt
an einen Empfänger auf 127.0.0.1, entschlüsselt unabhängig mit `http_ece`
und prüft die VAPID-Signatur).
