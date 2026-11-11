# Änderungsblatt: Verlauf, Gesprächsfäden, Ablage, Benachrichtigungen — 11.11.2026

**Für den Agenten, der die Android- (und Windows-)App baut.**

> **Es muss nichts angepasst werden, damit die Apps weiterlaufen.**
> Keine bestehende Nachrichtenart wurde geändert, kein Feld entfernt oder
> umbenannt. Dazugekommen sind zwei Arten herein (`eintrag`, `faeden`),
> vier hinaus (`faden_*`) und neue HTTP-Wege. Eine App, die unbekannte
> Arten still überspringt, läuft unverändert.

Maßgeblich ist `einsatz/DRAHT.md`, Abschnitte **„Gesprächsverlauf und
Fäden“**, **„Ablage“** und **„Benachrichtigungen bei geschlossener App“**.
Dieses Blatt ist nur die Differenz und die Bauanleitung. Prüfen:
`python einsatz/draht_pruefen.py`. Vorlage zum Abschauen: `web/sarvis.js`
(Abschnitte „Gesprächsfäden und Verlauf“, „Die Ablage“, „Web Push“) und
`web/waechter.js`.

Warum: Am Denken fehlte Sarvis nichts, es fehlte Oberfläche
(`notizen/2026-11-10-recherche-zielbild.md`). Bisher zeigte eine App genau
eine Untertitelzeile, und nach dem Neustart war alles weg.

---

## 1. Was der Nutzer jetzt erwartet (so sieht es die Web-App)

1. **Hauptbildschirm = Verlauf** wie in einem Messenger: Zurufe rechts,
   Antworten links, dazu Karten für Blätter, Berichte, Dateien, Kacheln
   und Rückfragen. Der Ring wird zur **Sprechansicht** (umschaltbar; beim
   freihändigen Mithören automatisch).
2. **Gespräche** (Fäden): Liste mit Titel und Zeit, „Neues Gespräch“,
   antippen = wechseln, umbenennen, archivieren, Suche.
3. **Ablage**: alles Erzeugte mit Filter (Blätter · Berichte · Dateien ·
   von dir), antippen = öffnen/herunterladen, auch nach Wochen.
4. **Benachrichtigungen**: Timer, Erinnerungen und fertige Aufträge
   kommen aufs Gerät, auch wenn die App zu ist.

## 2. Verlauf (Draht + HTTP)

**Beim `willkommen`** kommt sofort ein `faeden`. Dann:

```
GET /verlauf?faden=<faeden.aktiv>&anzahl=60      (X-Sarvis-Schluessel)
→ { "faden": {…}, "eintraege": [ … ALT → NEU … ], "mehr": true }
```

Danach kommt jeder neue oder geänderte Eintrag als Draht-Nachricht:

```json
{ "art": "eintrag", "faden": "f-…", "id": 812, "zeit": 1794392990.1,
  "wer": "du|sarvis|system", "sorte": "text|datei|meldung|frage|blatt|kachel",
  "text": "…", "daten": { … }, "geraet": "…" }
```

Regeln, an denen eine App sonst vorbeibaut:

- **`id` ist die Identität.** Gleiche `id` → Eintrag ersetzen (eine
  Rückfrage wird entschieden, eine Kachel ändert sich im selben Zug).
- **Nach jedem `willkommen` neu holen** — auch beim Wiederverbinden. Was
  während der Lücke geschah, kommt nicht per Draht nach. Einträge, die
  beim Holen schon per Draht da waren und eine höhere `id` haben, behalten.
- `eintrag` mit `faden` ≠ aktiv: überspringen.
- **Die Antwort kommt als Ganzes**, nachdem sie formuliert ist. Für das
  „läuft gerade“-Gefühl weiter `untertitel` (wer = sarvis) als vorläufige
  Blase zeigen und beim `eintrag` von `sarvis` bzw. `zustand: ruhig`
  entfernen. Bei `zustand: denkt` drei Punkte.
- „Ältere laden“: `GET /verlauf?faden=…&vor=<kleinste id>&anzahl=60`,
  solange `mehr` wahr ist.
- `sorte: text` mit `daten.unterbrochen: true` → als unterbrochen
  kennzeichnen (Teilantwort).

**Karten** — dieselben Sicherheitsregeln wie auf der Bühne:

| `sorte` | zeigen | antippen |
|---|---|---|
| `blatt`, `daten.sorte = markdown` | Titel + erste Zeilen von `daten.inhalt` | Markdown-Blatt groß öffnen (eigener Wandler, nie als HTML) |
| `blatt`, `daten.sorte = html` | „Bericht“ + Titel | `POST /ablage/oeffnen {"schluessel": daten.kennung}` → `adresse` im WebView **ohne JavaScript** |
| `blatt`, `daten.sorte = datei` | Dateiname + Größe | dito → `adresse` herunterladen (DownloadManager) |
| `kachel` | wie auf der Bühne gemalt | **nichts** — Kacheln sind nicht anklickbar |
| `frage` | Text; solange `daten.offen`: **Ja** / **Nein** | Knopf schickt `{"art":"zuruf","text":"Ja"}` bzw. `"Nein"` |
| `datei` (wer = du) | 📎 Name + Größe | — |
| `meldung` | wie Antwort, mit Glocke | — |

Die Rückfrage-Knöpfe sind **kein** neuer Weg an den Stufen vorbei: Der
Server bekommt denselben Zuruf, als wäre „Ja“ gesagt worden. Nach dem
Antippen beide Knöpfe sperren; der geschlossene Eintrag kommt gleich
danach (`offen: false`, `entscheidung`).

## 3. Gesprächsfäden

```json
{ "art": "faden_neu" }
{ "art": "faden_wechseln", "faden": "f-…" }
{ "art": "faden_umbenennen", "faden": "f-…", "titel": "Urlaub" }
{ "art": "faden_archivieren", "faden": "f-…", "an": true }
```

- **Ein aktiver Faden für alle Geräte.** Nach jedem Befehl kommt `faeden`
  an alle; die App wechselt ihre Ansicht danach, nicht vorher. Ändert sich
  `aktiv`, Verlauf neu holen.
- `wechselt: true` → im Titel „wechselt …“ zeigen. Dauer gemessen unter
  1 Sekunde.
- Titel leer → „Neues Gespräch“. Archiv als eigener, eingeklappter
  Abschnitt; Wechseln in einen archivierten Faden holt ihn zurück.
- Suche: Titel lokal filtern, ab zwei Zeichen zusätzlich
  `GET /suche?q=…` (Treffer tragen `faden` und `faden_titel`; antippen =
  wechseln).
- Sprache, Weckwort und Hochladen landen immer im **aktiven** Faden.

## 4. Ablage

```
GET  /ablage                       → { eintraege: [...], von_dir: [...] }
POST /ablage/oeffnen {schluessel}  → markdown: {inhalt} | sonst: {adresse, bis}
                                     404 unbekannt · 410 liegt nicht mehr da
```

Filter über `sorte` (`markdown` = Blätter, `html` = Berichte, `datei`).
`vorhanden: false` grau und nicht antippbar. „Neu“-Markierung macht die
App selbst (höchstes gesehenes `seit` merken; die Web-App zählt nur
Dateien und Berichte). `GET /dateien` gibt es unverändert weiter.

## 5. Benachrichtigungen (Web Push)

Für die **Web-App** fertig. Eine **native App** hat zwei Wege:

- **Android mit UnifiedPush** (ntfy o. ä.): Der Distributor liefert eine
  Web-Push-Adresse samt `p256dh`/`auth`. Diese per `POST /push/abo` wie
  eine `PushSubscription` anmelden, den Host des Dienstes in
  `config.PUSH_DIENSTE` eintragen lassen (Server-Seite, eine Zeile).
  Entschlüsseln nach RFC 8291 (aes128gcm) — die UnifiedPush-Bibliotheken
  können das.
- **Ohne Push-Dienst:** Die App bekommt Meldungen nur, solange der Draht
  offen ist (`eintrag` mit `sorte: meldung`). Das ist der bisherige Stand.

```
GET  /push/schluessel  → { schluessel, abos }      (VAPID-Public-Key)
POST /push/abo         { endpoint, keys: { p256dh, auth } }
POST /push/abmelden    { endpoint }
POST /push/probe       → { gesendet, fehler, entfernt }
```

Inhalt nach dem Entschlüsseln: `{ "titel", "text", "art": "wecker|auftrag|probe|meldung", "zeit" }`.
Zeigen, außer die App ist gerade im Vordergrund (dann hat man es gehört).
`wecker` sollte stehen bleiben, bis man ihn wegwischt. Antippen öffnet
die App.

**Abo bei jedem Start erneut melden** (`POST /push/abo` ist idempotent):
Der Server löscht Abos, die der Dienst als erloschen meldet (404/410),
und Abos widerrufener Geräte.

## 6. Was sich im Verhalten von Sarvis ändert (zur Einordnung)

- Ein Neustart des Dienstes ist kein neues Gespräch mehr: Der zuletzt
  aktive Faden wird mit seinem Kontext wieder aufgenommen.
- Ein neuer Faden ist ein frischer Kontext; das Gedächtnis (gemerkt,
  entschieden, Personen) gilt überall.
- Push geht an alle angemeldeten Geräte, auch wenn eins verbunden ist —
  ob gezeigt wird, entscheidet das Gerät (siehe DRAHT.md).
