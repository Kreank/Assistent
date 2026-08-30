# Eine native Sarvis-App bauen

**Auftrag für eine KI, die auf dem Windows-Rechner arbeitet.** Dieses
Dokument ist selbsttragend — es beschreibt alles, was gebraucht wird.
Der Server ist fertig und wartet; gebaut werden muss nur die Bedienung.

---

## Was Sarvis ist und was fehlt

Sarvis ist ein persönlicher Sprachassistent. Er lief bisher als Programm
auf diesem Windows-Rechner und ist auf einen Server umgezogen. Dort
laufen jetzt: Spracherkennung (Whisper), Sprachausgabe (Piper), sein
Kopf (Claude), 77 Werkzeuge (Kalender, Mail, Telegram, Dateien,
Projekte, Finanzen).

Erreichbar ist er über:

    wss://sarvis.tech-artist.de/draht

Es gibt bereits eine Weboberfläche, die funktioniert. Was ihr fehlt und
was **nur eine native App kann**, sind zwei Dinge:

**1. Der systemweite Tastaturhaken.** Sarvis' beste Bedienung war die
rechte Strg-Taste: halten, reden, loslassen — ohne das Fenster zu
wechseln, mitten aus der Arbeit heraus. Ein Browser bekommt Tastendrücke
nur, wenn er den Fokus hat. Das ist der eigentliche Grund für diese App.

Die rechte Strg-Taste ist bewusst gewählt: Sie tut allein gar nichts.
F10 aktiviert in vielen Programmen die Menüleiste, Alt erst recht — und
wer Alt hält, während er redet, macht aus jedem Streifen von Tab oder F4
eine Tastenkombination. Der Haken darf die Taste **nicht abfangen**; das
Vordergrundprogramm soll sie trotzdem bekommen.

**2. Ein Overlay über allen Fenstern.** Klickdurchlässig, damit man
hindurcharbeiten kann. Das ist, wie Sarvis vorher aussah.

Alles andere — Mikrofon, Ton, Anzeige — kann die Weboberfläche auch.
Wenn eines dieser beiden Dinge nicht gebraucht wird, lohnt die App nicht.

---

## Der Draht

JSON über WebSocket. Nichts Browser-Eigenes, kein REST, kein gRPC.
Mehrere Oberflächen dürfen gleichzeitig verbunden sein und sehen
dasselbe — die App verdrängt die Weboberfläche nicht.

### Anmelden

Die **erste Nachricht** auf der offenen Verbindung ist der Schlüssel.
Nicht als Query-Parameter in der Adresse: Der stünde im Zugriffslog des
Reverse Proxy, im Verlauf und in jedem Weiterleitungs-Header.

```json
{ "schluessel": "…", "kann_browser": true }
```

`kann_browser: true` heißt „dieses Gerät hat einen großen Bildschirm und
kann Web-Werkzeuge bedienen". Für den Dev-PC ja, fürs Handy nein.

Antwort:

```json
{ "art": "willkommen", "geraet": "Dev-PC", "seit": 1788082503.1 }
```

Ungültiger Schlüssel → Verbindung wird mit Code **4401** geschlossen,
ohne Angabe, was falsch war. Keine Anmeldung binnen 10 Sekunden →
dasselbe. Der Schlüssel kommt von Sascha; er wird auf dem Server je
Gerät erzeugt und ist einzeln widerrufbar.

**Speichern:** Windows Credential Manager oder DPAPI, nicht im Klartext
in einer Datei neben der Exe.

### Wiederverbinden

Die Verbindung bricht ab — WLAN wechselt, Rechner schläft, Server startet
neu. Die App muss von selbst wiederkommen, mit **wachsendem Abstand**
(1 s, dann 1,6× bis maximal 20 s). Nicht im Sekundentakt hämmern.

Bei Code 4401 **nicht** wiederverbinden: Der Schlüssel gilt nicht, und
weitere Versuche ändern daran nichts.

---

## Was hereinkommt (Server → App)

Jede Nachricht trägt `art`. **Unbekannte Arten und unbekannte Felder
ignorieren, nicht als Fehler behandeln.** So lässt sich das Protokoll
erweitern, ohne alle Oberflächen gleichzeitig anzufassen.

| art | Felder | Bedeutung |
|---|---|---|
| `zustand` | `zustand`, `strom` | `ruhig` · `hoert` · `denkt` · `spricht` · `fragt` |
| `pegel` | `pegel` 0–1 | Ausschlag für den Ring, höchstens 50/s |
| `untertitel` | `wer` (`du`/`sarvis`), `text`, `strom` | was gerade gesagt wird |
| `nachhoeren` | `sekunden` | so lange ist kein Weckwort nötig |
| `hintergrund` | `zeilen` (max 3), `gesamt`, `seit`, `fertig` | was nebenher arbeitet |
| `werkzeug` | `name`, `aktiv`, `strom` | ein Werkzeug leuchtet auf |
| `freigabe` | `text`, `sekunden` | was gerade ohne Rückfrage durchgeht |
| `kachel` | `name`, `sorte`, `kopf`, `gross`, `stand`, `punkte`, `form`, `weggelassen`, `sekunden` | eine Datenkachel |
| `kachel_weg` | `name` | Kachel ausblenden |
| `ton` | `daten` (base64), `rate`, `runde` | gesprochenes Audio |
| `ton_stopp` | `runde` | sofort still sein |

`browser`, `browser_zu` und `verschieben` sind Reste aus dem
Desktop-Betrieb und können ignoriert werden.

### Das Feld `strom`

Leer heißt: **das Gespräch**. Davon gibt es genau eines — das ist der
Ring in der Mitte. Ein benannter Strom gehört zu einem Vorgang, der
nebenher läuft (Sarvis kann Aufträge im Hintergrund bearbeiten und dabei
weiterreden). Eine Oberfläche ohne Platz dafür überspringt benannte
Ströme einfach; die Weboberfläche tut genau das.

### Kacheln

`name` ist die **Identität**, nicht die Überschrift: Zweimal `finanzen`
heißt dieselbe Kachel mit neuem Inhalt, nicht zwei übereinander.

`sorte` bestimmt Farbe und Lebensdauer:
- `antwort` — gehört zu einem Satz, verschwindet nach `sekunden`
  (Vorgabe 45), Farbe `rgb(255,179,71)`
- `zustand` — gehört zu etwas, das läuft, bleibt bis `kachel_weg`,
  Farbe `rgb(126,224,168)`

`punkte` sind Datenpunkte, keine fertigen Zeilen:
`{"text": "Wohnen", "wert": "1.098,00", "zahl": 1098.0}`. Aus `zahl`
wird die Länge eines Balkens hinter der Schrift. `weggelassen` sagt, wie
viele Punkte der Server abgeschnitten hat — das gehört angezeigt („und
3 weitere"), sonst ist die Kürzung stumm und die Kachel behauptet
Vollständigkeit.

**Kacheln dürfen nicht anklickbar sein.** Das ist keine Stilfrage: Im
ursprünglichen Sarvis steht dafür ein eigenes Fensterflag, mit der
Begründung „kein Klick, der an der Rückfrage vorbeiläuft". Gehandelt
wird über Sarvis, nicht am Bild vorbei.

---

## Was hinausgeht (App → Server)

| art | Felder |
|---|---|
| `zuruf` | `text` — eine getippte Zeile |
| `sprache` | `daten` (base64), `rate` — eine fertige Aufnahme |
| `antwort` | `nummer`, `inhalt` — Antwort auf eine Frage des Servers |

### Das Audioformat ist nicht verhandelbar

**16 000 Hz · mono · int16 · little-endian · base64.**

Genau das erwartet Whisper. Alles andere müsste serverseitig umgetastet
werden, und lineare Interpolation ohne Tiefpass macht dabei hörbaren
Schaden. Also gleich in dieser Rate aufnehmen (WASAPI kann das).

Aufnahmen unter **0,4 Sekunden** verwirft der Server als Versehen.
Nachrichten über **4 MB** weist er ab — 30 Sekunden bei 16 kHz sind als
base64 rund 1,3 MB.

### Push-to-talk ist hier umgedreht

Der Server sagt **nicht** „jetzt aufnehmen". Die App entscheidet das
selbst und schickt eine fertige Aufnahme. Das ist Absicht: Eine
Rundreise vor dem ersten Wort würde genau die Zeit kosten, in der schon
geredet wird — der Anfang ginge verloren.

Besser noch: **schon vor dem Tastendruck in einen Ringpuffer aufnehmen**
und beim Loslassen die letzten ~300 ms davor mitschicken. Menschen
drücken die Taste oft eine Silbe zu spät.

### Mikrofon-Einstellungen, die zählen

- **Echo-Unterdrückung an.** Sarvis' eigener Echo-Filter vergleicht
  *Text*, keine Wellenformen — er merkt erst nach Whisper, dass er sich
  selbst gehört hat. Ohne akustische Unterdrückung klingelt es bei
  Lautsprecherbetrieb bei jedem Durchlauf erneut.
- **Verstärkungsautomatik AUS.** Die Weckwort-Schwelle ist ein absoluter
  Pegel und wird von einer Automatik wertlos.

### Ton abspielen — und die Runde beachten

`ton` kommt **satzweise**, nicht als fertige Antwort. Das ist der
Unterschied zwischen „fühlt sich an wie reden" und „fühlt sich an wie
ein Formular": Während Satz eins klingt, baut der Server schon Satz
zwei. Die App muss die Blöcke **nahtlos aneinanderhängen**, nicht jeden
einzeln abspielen und dazwischen eine Lücke lassen.

**Die `runde` ist die Wahrheit.** Reinreden ist erlaubt — wer Sarvis
unterbricht, soll ihn sofort zum Schweigen bringen. Über Netz kann ein
Satz aber schon unterwegs sein, wenn der Abbruch erfolgt. Deshalb:

- `ton_stopp` → alle eingeplanten Blöcke abbrechen **und** die eigene
  Runde auf die gemeldete setzen
- ein `ton` mit `runde` **kleiner** als die eigene → verwerfen
- wer selbst zu reden anfängt → Ton **sofort** stoppen, ohne auf den
  Server zu warten; bis dessen `ton_stopp` ankommt, hätte man sich sonst
  selbst zugehört

Ohne das spielt ein alter Satz nach dem „Gestoppt." — genau der Fehler,
gegen den der Rundenzähler ursprünglich gebaut wurde, nur um eine
Netzlaufzeit versetzt.

---

## Wie es aussehen soll

Der Look existiert und soll **übernommen, nicht neu erfunden** werden.
Die Zahlen stammen aus dem ursprünglichen Overlay; die Weboberfläche
unter `web/sarvis.js` im Repo `Kreank/Assistent` (Branch `server`) ist
eine vollständige Übersetzung davon und taugt als Vorlage.

```
Zeichenraster    660 × 548, Mitte bei (330, 222)
Ring             Radius 58
Werkzeugkranz    Radius 176, 17 Werkzeuge, oben beginnend im Uhrzeigersinn
Striche          72 Stück, an der Senkrechten gespiegelt, Länge 5 + Pegel·46
Takt             60 Bilder je Sekunde
```

| Zustand | Farbe | Beschriftung |
|---|---|---|
| ruhig | `126,158,200` | bereit |
| hoert | `0,229,255` | hört zu |
| denkt | `180,124,255` | denkt nach |
| spricht | `255,179,71` | spricht |
| fragt | `255,120,140` | wartet auf dich |

```
atem     = 0.5 + 0.5·sin(t·1.6)
stärke   = geglätteter Pegel            bei hoert/spricht
         = max(atem·0.25, Pegel)        sonst
Glättung = +45 % steigend, +12 % fallend  (sofort ausschlagen, nicht flackern)
```

Bei `denkt` und `fragt` **ersetzen drei kreisende Bögen die Striche** —
Radien 74/86/98, Tempi +1,0 / −0,7 / +0,45, Spannen 110°/70°/40°, Alpha
0,55/0,42/0,29.

Werkzeuge glimmen beim Aufleuchten und klingen mit Faktor 0,975 je Bild
ab (halbe Helligkeit nach 0,44 s, aus nach 2,5 s).

Jede Schrift bekommt einen **Saum**: fünfmal in `rgba(4,8,16,.55)` an
den Versätzen (−1,0) (1,0) (0,−1) (0,1) (1,1), dann einmal in Farbe.
Ohne ihn ist helle Schrift über einem hellen Fenster unlesbar.

Die 17 Werkzeuge in dieser Reihenfolge: Timer, Gedächtnis, Telegram,
Websuche, Programme, Musik, Dateien, Projekte, Aufträge, Kalender,
E-Mail, Aufgaben, Kontakte, Drive, Tabellen, Entwicklung, Finanzen.

---

## Technikvorschläge für Windows

Frei wählbar, das sind nur Hinweise:

- **C# / WPF** oder **Rust / egui** — beide können randlose
  Klickdurchlässigkeit (`WS_EX_TRANSPARENT | WS_EX_LAYERED`) und globale
  Tastaturhaken (`SetWindowsHookEx` mit `WH_KEYBOARD_LL`).
- Der Haken darf die Taste **nicht** abfangen: `CallNextHookEx`
  weiterrufen.
- **Bekannte Grenze:** Hat ein Programm mit Administratorrechten den
  Fokus, blockiert Windows den Haken. Das war beim alten Sarvis auch so;
  es ist keine Fehlfunktion, sollte aber nicht als eine gemeldet werden.
- Audio: **WASAPI** in 16 kHz aufnehmen, Wiedergabe in der Rate, die der
  Server meldet (`rate` im `ton`, üblich 22 050).
- Autostart über den Startordner oder einen Registry-Run-Eintrag.

## Für Android gilt dasselbe

Derselbe Draht, dasselbe Audioformat. Der Gewinn gegenüber der
Weboberfläche ist dort ein anderer: Ein **Foreground Service** darf das
Mikrofon offenhalten, wenn der Bildschirm gesperrt ist — damit ginge
„Hey Sarvis" auch in der Tasche. Ein Browser darf das nicht.

Das Repo `Kreank/NotizVoiceApp` (Kotlin/Compose) taugt als Vorlage für
Aufbau und Berechtigungen.

---

## Testen, ohne den Server zu belasten

Ein Wegwerf-Server, der den Draht spricht, ist in rund 60 Zeilen Python
gebaut (`aiohttp`). Er sollte:

1. eine Anmeldung entgegennehmen und `willkommen` antworten
2. auf `zuruf` mit `zustand`/`untertitel` reagieren
3. auf `sprache` die Länge der Aufnahme zurückmelden — so sieht man
   sofort, ob das Format stimmt
4. eine Testkachel schicken
5. eine Tondatei satzweise schicken und dabei die `runde` mitzählen

Im Repo liegt unter `einsatz/vorschau.py` genau so etwas, allerdings
serverseitig. Es lässt sich als Vorlage lesen.

**Die Reihenfolge, in der es sich lohnt zu bauen:**

1. Verbinden, anmelden, wiederverbinden — ohne das ist alles andere
   nicht prüfbar
2. Der Ring mit `zustand` und `pegel`. Man sieht sofort, ob der Draht
   trägt.
3. Tastaturhaken und Aufnahme. Das ist der Grund für die App.
4. Ton mit Runden-Logik. Der fehleranfälligste Teil.
5. Werkzeugkranz, Untertitel, Kacheln.
6. Overlay-Fenster, klickdurchlässig, immer obenauf.

---

## Was der Server garantiert und was nicht

**Garantiert:** Meldungen kommen in der Reihenfolge an, in der sie
gesendet wurden. Fast alle sind Zustände, keine Änderungen — eine
verlorene kostet ein Bild, die nächste heilt es.

**Nicht garantiert:** dass jede ankommt. Bei schlechter Verbindung staut
der Server und dampft dann ein: Was verloren bleiben würde (`werkzeug`,
`kachel_weg`), überlebt vollständig, vom Rest bleibt je Art der neueste
Stand. Die App darf also **nicht** darauf bauen, jeden Zwischenwert zu
sehen — wohl aber darauf, dass der letzte Stand stimmt.

**Ebenfalls nicht garantiert:** dass der Server überhaupt antwortet. Er
kann neu starten, während die App verbunden ist. Ein Zustand, der ewig
„denkt nach" behauptet, ist schlimmer als einer, der sagt, dass die
Verbindung weg ist.
