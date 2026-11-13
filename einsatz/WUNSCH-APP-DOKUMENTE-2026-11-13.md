# Wunsch der Android-App: Dokumente schöner zeigen (13.11.2026)

Für den Agenten, der den Sarvis-Server baut. Von der Android-App
(`Kreank/Assistent_android`, Stand `8591ad6`). Sascha hat diesen Wunsch
freigegeben.

## Was die App jetzt kann

Die App hat einen eigenen Dokumentbetrachter wie die Apps von Claude und
ChatGPT. Im Chat steht eine Dokumentkarte, Antippen öffnet den Betrachter
mit Teilen, In Downloads speichern und Öffnen mit …:

- **Markdown und HTML-Berichte:** wie bisher. HTML-Berichte laufen seit
  heute **mit JavaScript** (Saschas Entscheidung). Der Rahmen bleibt
  eingesperrt: nur `/blatt/`-Adressen, keine Brücke zur App, kein Datei-
  und DOM-Speicher, jeder Link geht nach außen.
- **Dateien** (`blatt` der Sorte `datei`): Die App lädt sie in ihren Cache
  und zeigt sie selbst an.

| Art | Anzeige |
|---|---|
| PDF | Seiten untereinander, Zoom |
| Bilder | mit Zoom |
| Text und Code | mit Zeilennummern |
| JSON | eingerückt |
| CSV | als Tabelle |
| Audio und Video | eigener Player |

- **Office** (docx, xlsx, pptx, odt …): Android kann das ohne Bibliothek
  nicht darstellen. Die App zeigt nur eine Infokarte mit „Öffnen mit …“.

## Wunsch 1: Office auch als PDF

Bei jeder Office-Datei, die als `blatt` der Sorte `datei` rausgeht, legt
der Server **zusätzlich** eine PDF-Fassung ab (z. B. LibreOffice headless,
`soffice --headless --convert-to pdf`). Die PDF-Fassung bekommt eine eigene
`/blatt/`-Adresse, also gleiche Kennungsregeln und gleiche Frist.

Im Blatt, im Verlaufseintrag, in `GET /dateien` (`von_sarvis`) und in
`POST /ablage/oeffnen` kommt ein neues Feld dazu:

```json
{ "sorte": "datei", "datei": "Angebot.docx", "adresse": "/blatt/AAA…",
  "pdf": "/blatt/BBB…" }
```

- `pdf` fehlt, wenn die Umwandlung nicht ging oder die Datei schon ein PDF
  ist. Dann bleibt alles wie bisher.
- Die App zeigt `pdf` im Betrachter an. „Öffnen mit …“, „Teilen“ und
  „In Downloads speichern“ nehmen weiter das Original unter `adresse`.

## Wunsch 2: Vorschau, Typ und Seitenzahl mitschicken

Damit die Karte im Chat eine Miniatur und „12 Seiten“ zeigen kann, ohne
die ganze Datei zu laden. Dieselben Felder stehen im Blatt, im
Verlaufseintrag (`daten`), in `GET /dateien` (`von_sarvis`) und in der
Ablage (`eintraege`):

| Feld | Inhalt |
|---|---|
| `mime` | der echte Typ, z. B. `application/pdf` |
| `seiten` | Seitenzahl bei PDF (auch bei der Office-PDF-Fassung), sonst weglassen |
| `vorschau` | eine `/blatt/`-Adresse auf ein kleines Bild |

Zur `vorschau`:

- **Bild:** PNG oder WebP, höchstens 480 px breit.
- **Quelle je Art:**
  - PDF und Office: erste Seite
  - Bilder: verkleinert
  - Video: ein Standbild
  - **HTML-Berichte:** ein Bildschirmfoto der ersten Bildschirmhöhe.
    Sarvis hat dafür ja den eigenen Browser.
- **Fehlt das Feld**, zeigt die App nur das Typ-Symbol. Das ist kein
  Fehler.
- **Gleiche Regeln** wie für jede Blatt-Adresse: Kennung mit 192 Bit
  Zufall, gleiche Frist wie das Dokument.

## Wunsch 3: `bytes` immer mitliefern

In Verlaufseinträgen der Sorten `blatt`/`datei` fehlt `bytes` manchmal.
Die Karte zeigt dann „Datei“ statt „PDF · 1,2 MB“. Bitte immer setzen,
auch bei `html` (Größe des ausgelieferten Dokuments).

## Wunsch 4: HTML-Berichte fürs Handy bauen

Der Betrachter zeigt Berichte jetzt wie ein Browser: Zoom, seitliches
Scrollen, Skripte laufen. Damit sie gut aussehen:

- `<meta name="viewport" content="width=device-width, initial-scale=1">`
- Breite Tabellen und Diagramme in einen Kasten mit `overflow-x: auto`,
  nicht die ganze Seite breiter machen.
- Diagramme dürfen jetzt per Skript gezeichnet werden. Lieber eingebettet
  (inline) als von einem CDN, dann klappt es auch bei schlechtem Netz. SVG
  ohne Skript bleibt die robusteste Wahl.
- Dunkler Grund passt zur App (Hintergrund ca. `#111315`). Die
  Sicherheitslage vom 13.11. sah schon genau richtig aus.

## Frage zurück

Ist die `kennung` in einem Verlaufseintrag der Sorte `blatt`/`datei`
immer dasselbe wie das letzte Stück der `adresse` (`/blatt/<kennung>`)?
Die App sucht ihre Cache-Kopie unter der Kennung. Wenn das nicht dasselbe
ist, bitte in DRAHT.md vermerken, welches Feld gilt.

## Antwort bitte

Wie bisher als Abschnitt in `einsatz/DRAHT.md` und kurz hier darunter:
was gebaut ist, welche Felder es genau heißen.
