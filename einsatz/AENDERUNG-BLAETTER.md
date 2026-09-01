# Änderungsblatt: Blätter — 01.09.2026

*(Fassung 2, nachmittags: Excel, CSV und Text sind dazugekommen. Am Protokoll ändert das nichts — nur die Liste der MIME-Typen unter Punkt 2 ist länger.)*

**Für den Agenten, der die Windows- und die Android-App gebaut hat.**

Kurz vorweg, damit die wichtigste Frage sofort beantwortet ist:

> **Es muss nichts angepasst werden, damit die Apps weiterlaufen.**
> Keine bestehende Nachrichtenart wurde geändert, kein Feld entfernt,
> kein Feld umbenannt, keine Bedeutung verschoben. Es sind zwei Arten
> **dazugekommen** und ein HTTP-Weg. Eine App, die unbekannte Arten
> still überspringt — so wie `DRAHT.md` es seit jeher verlangt —,
> merkt von dieser Änderung genau nichts.

Anpassen lohnt sich nur, wenn die App das Neue **zeigen** soll. Tut sie
es nicht, sagt Sarvis dem Nutzer „das liegt jetzt vor dir", und vor ihm
liegt nichts. Genau dieser Fehler war der Anlass für den ganzen Umbau
(siehe unten, „Warum es das gibt").

Maßgeblich ist `einsatz/DRAHT.md`, nicht dieses Blatt. Dort steht das
vollständige Protokoll, und es lässt sich gegen den Code prüfen
(`python einsatz/draht_pruefen.py`). Dieses Blatt ist nur die
Differenz.

---

## 1. Was dazugekommen ist

### Zwei Arten, Server → Oberfläche

| `art` | Felder |
|---|---|
| `blatt` | `kennung`, `sorte`, `titel`, `adresse`, `inhalt`, `datei`, `bytes`, `sekunden` |
| `blatt_weg` | `kennung` |

Ein **Blatt** ist, was gelesen statt gehört wird — größer als eine
Kachel, kleiner als ein eigener Bildschirm. `kennung` ist die
Identität wie `name` bei der Kachel: Zweimal dieselbe heißt dasselbe
Blatt mit neuem Inhalt, nicht zwei übereinander. `sekunden` ist die
Lebensdauer; `0` heißt „bis `blatt_weg`".

Drei Sorten in einem Kasten:

| `sorte` | wo der Inhalt steckt | wie er gezeigt wird |
|---|---|---|
| `markdown` | `inhalt`, mit der Nachricht | die App setzt ihn selbst |
| `html` | `adresse` → `/blatt/<kennung>` | in einem gekapselten Rahmen |
| `datei` | dito, plus `datei` und `bytes` | Knopf zum Herunterladen |

### Ein HTTP-Weg

```
GET  /blatt/<kennung>
```

Liefert den Bericht (`text/html`), das PDF oder die Word-Datei.
Antworten: `200` · `404` (unbekannt **oder** abgelaufen — bewusst
nicht unterscheidbar) · `410` (Eintrag gilt, Datei ist weg).

Gesetzte Kopfzeilen: `Content-Security-Policy` (mit `sandbox`),
`X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`,
`Cache-Control: private, no-store`, bei Dateien zusätzlich
`Content-Disposition: attachment` mit `filename` **und** `filename*`.

**`adresse` ist immer ein relativer Pfad**, beginnend mit `/blatt/`.
Nie absolut — der Endpunkt hört auf `127.0.0.1`, davor steht Caddy, er
kennt seine öffentliche Adresse nicht. Die App setzt ihre eigene Basis
davor (dieselbe, unter der sie den Draht öffnet).

**Prüft das.** Eine App, die eine `adresse` verwendet, ohne auf
`/blatt/` zu prüfen, lädt eine fremde Seite in ihren eigenen Rahmen,
sobald einmal etwas anderes über den Draht käme. Der Draht ist
authentifiziert — was über ihn kommt, ist trotzdem aus Modellausgabe
gebaut.

### Kein Geräteschlüssel auf diesem Weg

Das ist Absicht und keine Lücke. Ein `<iframe>` schickt keine eigenen
Kopfzeilen, ein Download-Knopf auch nicht, und der Systemviewer, der
das PDF danach öffnet, erst recht nicht. Wer hier eine Anmeldung
verlangt, bekommt ein leeres Rechteck — wieder eines ohne
Fehlermeldung.

Was stattdessen schützt: 192 Bit Zufall in der Kennung
(`secrets.token_urlsafe(24)`), sieben Tage Frist, kein Verzeichnis
über HTTP, und der Dateipfad wird **nie** aus der Adresse gebaut — die
Kennung ist ein Schlüssel in eine Tabelle, kein Dateiname.
`../../etc/passwd` ist dort keine Pfadangabe, sondern eine unbekannte
Kennung (gemessen: `404`).

---

## 2. Was zu tun ist, wenn Blätter gezeigt werden sollen

### `sorte: "markdown"` — selbst setzen

Der Text kommt **mit** der Nachricht. Die zu unterstützende Teilmenge,
identisch in `sarvis/werkzeuge/markdown_lesen.py` (Python) und
`web/sarvis.js` (JS) — nehmt eine davon als Vorlage:

```
# bis ###        Überschriften (tiefer wird auf 3 begrenzt)
**fett**  *kursiv*  `code`
- Punkt      und      1. Nummer
> Zitat
```Codeblock```
| Tabelle | mit | Kopfzeile |
---              Trennlinie
[Text](https://ziel)
```

**HTML im Markdown wird nicht ausgeführt, sondern angezeigt.** Escaped
jeden Text, erzeugt jedes Tag selbst. Ein Linkziel, das nicht mit
`http://`, `https://`, `mailto:` oder `tel:` beginnt, wird zu blossem
Text — sichtbar, aber nicht anklickbar. Auf Android heißt das:
**keine** `WebView` mit `loadData()` für Markdown, sondern echte
Textelemente oder eine `WebView` mit denselben Regeln wie unten.

Verschachtelte Listen, Bilder und Fußnoten gibt es nicht. Was nicht
erkannt wird, überlebt als schlichter Text — nichts geht verloren, es
sieht nur nicht aus wie gemeint.

### `sorte: "html"` — rahmen, nicht einbetten

Android `WebView`, Windows `WebView2`. **Die Einstellungen sind nicht
optional:**

- **JavaScript AUS** (`settings.javaScriptEnabled = false`;
  WebView2: `IsScriptEnabled = false`)
- **Keine Brücke zum nativen Teil** — kein `addJavascriptInterface`,
  kein `AddHostObjectToScript`, kein `WebMessageReceived`-Handler, der
  irgendetwas auslöst
- **Kein Dateisystemzugriff** (`allowFileAccess`,
  `allowFileAccessFromFileURLs`, `allowUniversalAccessFromFileURLs`
  alle `false`)
- **Kein `localStorage`/DOM-Speicher** — dort liegt in der App der
  Geräteschlüssel
- **Navigation abfangen:** Ein Klick auf einen Link im Bericht gehört
  in den Systembrowser (`Intent.ACTION_VIEW` /
  `Process.Start`), nicht in denselben Rahmen.

Der Grund steht in `DRAHT.md` ausführlich und in einem Satz hier:
Sarvis kann den Rechner bedienen. Was er anzeigt, hat er womöglich
gerade von einer fremden Seite gelesen. Ein Rahmen, aus dem heraus
etwas zurück in die Auftragsschleife reden kann, ist ein
Prompt-Injection-Weg mit Systemzugriff dahinter.

Die Weboberfläche macht es mit
`sandbox="allow-popups allow-popups-to-escape-sandbox"` — also **ohne**
`allow-scripts` und **ohne** `allow-same-origin`.

### `sorte: "datei"` — herunterladen und dem System übergeben

`datei` ist der vorgeschlagene Dateiname, `bytes` die Größe (zum
Anzeigen, nicht zum Prüfen).

- **Android:** herunterladen (der `Content-Disposition`-Kopf liefert
  den Namen), in den App-eigenen Bereich legen, dann über einen
  `FileProvider` per `Intent.ACTION_VIEW` mit
  `FLAG_GRANT_READ_URI_PERMISSION` öffnen. `DownloadManager` geht
  auch, kann aber die Basis-Adresse und ein eventuelles
  Zertifikats-Pinning nicht mitbenutzen.
- **Windows:** in `%TEMP%` oder den Download-Ordner schreiben, dann
  `ShellExecute` / `Process.Start(… UseShellExecute = true)`.
- **Nicht im eigenen Rahmen anzeigen.** Ein PDF in einer `WebView`
  ohne Skripte geht nicht — Chromes PDF-Betrachter ist selbst eine
  Anwendung. Ein Knopf und ein Satz sind die ehrliche Lösung.

MIME-Typen, die kommen können:

| Typ | woher |
|---|---|
| `application/pdf` | PDF |
| `…wordprocessingml.document` | Word (.docx) |
| `…spreadsheetml.sheet` | Excel (.xlsx) |
| `text/csv; charset=utf-8` | CSV |
| `text/plain; charset=utf-8` | Text/Markdown (.md) |
| `text/html` | Bericht — der einzige, der **nicht** als Anhang kommt |

Die Liste ist eine **Freiliste** im Server (`blaetter.TYPEN`): Was dort
nicht steht, wird gar nicht erst ausgeliefert. Sie kann wachsen; die
App muss sie nicht kennen, sondern nur dem `Content-Type` folgen und
im Zweifel dem System überlassen, was es damit anfängt.

Nur `text/html` wird gerahmt. Alles andere trägt
`Content-Disposition: attachment` und gehört heruntergeladen.

---

## 3. Was sich ausdrücklich NICHT geändert hat

- Die Anmeldung am Draht (`schluessel`, `kann_browser`, `kann`)
- Das Audioformat (16 000 Hz · mono · int16 · little-endian · base64)
- `ton` / `ton_stopp` und die Rundenlogik
- `radio` / `radio_aus`, `kann_radio`
- Kacheln, Untertitel, Zustand, Pegel, Hintergrund, Werkzeug, Freigabe
- Die Fernsicht (`schirm_an`, `klick`, `taste`, `rollen`)
- `befehl` und `kann_rechner`
- Sämtliche Arten Oberfläche → Server

Es gibt in dieser Änderung **keine** neue Fähigkeit, die eine App beim
Anmelden melden müsste. Blätter gehen an alle verbundenen Oberflächen,
wie Kacheln auch.

---

## 4. Warum es das gibt

Auf dem Dev-PC schickte Sarvis für einen Bericht eine
`file:///`-Adresse an sein eingebautes Browserfenster, und das ging
auf — Datei und Fenster lagen auf demselben Rechner.

Im Container ist genau das der Fehler: Die Datei liegt auf dem Server,
der Browser des Nutzers steht woanders. Die Weboberfläche verwarf jede
Adresse, die nicht mit `http` beginnt — **still**, ohne Log, ohne
Meldung. Sarvis sagte „die Seite steht vor dir", und es stand nichts.

Das Blatt schließt diese Lücke an der einzigen Stelle, an der sie zu
schließen ist: bei der Auslieferung.

Dazu kamen zwei Werkzeuge, die es vorher nicht gab: `blatt_zeigen`
(eine formatierte Antwort im Gespräch) und `dokument_erstellen` (PDF
oder Word zum Behalten und Weitergeben). Beides erzeugt Blätter — für
die App ist es derselbe Fall.

---

## 5. Zum Ausprobieren, ohne die App anzufassen

Die Weboberfläche (`web/` im Repo) kann alles davon und ist die
lebende Vorlage. Interessant sind dort drei Stellen:

- `markdown()` in `web/sarvis.js` — der Wandler, geprüft gegen 13
  Angriffsproben (Skript im Text, `javascript:`-Ziel, Anführungszeichen
  im Link, `onerror`-Attribut …); keine ist durchgekommen
- `blattZeigen()` daneben — die Fallunterscheidung der drei Sorten
- `#blatt .rahmen` in `web/index.html` — die Sandbox-Attribute mit
  ihrer Begründung
