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

## Antwort vom Server (13.11.2026, abends)

Gebaut und live. Genaues in `einsatz/DRAHT.md`, Abschnitt „Begleitfelder
an `html`/`datei`".

1. **Office als PDF:** ja. Feld `pdf` (`/blatt/…`, Anhang,
   `application/pdf`) bei docx/doc/odt/rtf/xlsx/xls/ods/pptx/ppt/odp.
   LibreOffice headless im Image, gemessen ~1 s je Datei. Fehlt bei PDF
   selbst und wenn die Umwandlung scheitert.
2. **Vorschau, Typ, Seiten:** `mime` (immer), `seiten` (PDF und
   Office-PDF-Fassung), `vorschau` (`/blatt/…`, **PNG**, inline
   `image/png`, höchstens 480 px breit). Quellen: PDF/Office erste Seite
   (pdftoppm), Bilder verkleinert, Video Standbild bei 1 s, HTML
   Bildschirmfoto 480 × 720 aus einem eigenen, netzlosen Chrome. Steht in
   `blatt`, Verlaufseintrag (`daten`), `GET /dateien`, `GET /ablage`,
   `POST /ablage/oeffnen`. Gleiche Kennungsregel, gleiche Frist wie das
   Dokument; die Ablage verlängert beides mit.
3. **`bytes`:** jetzt immer, auch bei `html`.
4. **HTML fürs Handy:** war schon so — `viewport`, Tabellen im
   Scrollkasten (`.tabelle`, `overflow-x:auto`), Diagramme als SVG mit
   `width:100%`, dunkler Grund `#070B11`. **Skripte bleiben in Berichten
   aus** (CSP `script-src 'none'` im Kopf und als HTTP-Kopf): Berichte
   sind Modellausgabe, oft aus gelesenen Webseiten; die Diagramme rechnet
   Python als SVG, dafür braucht es kein JavaScript. Die App darf Skripte
   erlauben, es kommen nur keine.

**Frage:** Ja. Bei `html`/`datei` gilt immer `adresse == "/blatt/" +
kennung`; in der Ablage ist `schluessel` dieselbe Kennung. Für den Cache
die `kennung` nehmen. Steht so in DRAHT.md.
