# Vertrag: Android-App ↔ Sarvis-Server — Stand 13.11.2026

**Für den Agenten, der die Sarvis-Android-App baut** (Package `de.techartist.sarvis`).

Der Server ist fertig und läuft. Alles, was hier steht, ist **in der Weboberfläche schon umgesetzt**
(`web/sarvis.js`) und fehlt nur noch in der App. Maßgeblich für jedes Feld ist `einsatz/DRAHT.md`
(`python einsatz/draht_pruefen.py` prüft es gegen den Servercode).

> **Keine bestehende Nachrichtenart wurde geändert oder entfernt.** Die App läuft weiter wie bisher.
> Alles hier sind Ergänzungen. Unbekannte Arten und Sorten weiter still überspringen.

## Woher die Unterlagen kommen

Repo `github.com/Kreank/Assistent`, **Zweig `server`** (nicht `main`):

| Datei | Wofür |
|---|---|
| `einsatz/AENDERUNG-2026-11-13.md` | dieser Vertrag |
| `einsatz/DRAHT.md` | das Protokoll, Feld für Feld |
| `einsatz/AENDERUNG-OBERFLAECHE.md` | Verlauf/Fäden/Ablage/Push ausführlich (11.11.) |
| `web/sarvis.js`, `web/index.html` | Vorlage: so macht es die Weboberfläche |

## Übersicht

| # | Was | Server | App |
|---|---|---|---|
| 1 | Verlauf und Gesprächsfäden | ✅ seit 11.11. | ⬜ |
| 2 | Statuskarte laufender Aufträge | ✅ | ⬜ |
| 3 | Nichts Getipptes verlieren (Warteschlange, Neuverbinden) | ✅ | ⬜ |
| 4 | Formulare (offene Fragen ausfüllen) | ✅ | ⬜ |
| 5 | Webseiten-Vorschau (Kartenart `seite`) | ✅ | ⬜ |
| 6 | Links in Antworten anklickbar | ✅ | ⬜ |
| 7 | Ablage und Benachrichtigungen (Push) | ✅ seit 11.11. | ⬜ (nach 1–6) |

**Reihenfolge = Nummer.** Jede Aufgabe ist einzeln testbar; nach jeder bauen und prüfen.

## Warum (was Sascha erlebt)

- Er schickt einen Auftrag ab, ist eine Stunde weg und sieht danach **einen einzigen Satz** — kein
  Verlauf, kein Stand, keine Ahnung, ob etwas läuft. Nach jedem Neustart von Sarvis ist der
  Bildschirm leer. Der Server hat alles gespeichert, die App fragt es nur nie ab (gemessen: die App
  ruft `/draht` und `/dateien`, nie `/verlauf`).
- Ein getipptes „ja“ ging verloren: Handy kam aus dem Standby, Leitung noch zu, die App zeigte es
  trotzdem als gesendet.
- Fragen des Arbeiters kamen als Text, den man nicht ausfüllen kann.
- Eine Vorschau-Karte war leer, Links waren nicht anklickbar.

---

## 1. Verlauf und Gesprächsfäden (zuerst, wichtigste)

Ausführlich: `AENDERUNG-OBERFLAECHE.md` Abschnitte 1–3 und `DRAHT.md` „Gesprächsverlauf und Fäden“.

- Hauptbildschirm = **Verlauf wie in einem Messenger** (Zurufe rechts, Antworten links, Karten für
  Blätter, Berichte, Dateien, Kacheln, Rückfragen, Formulare, Auftragsstand). Der Ring wird zur
  umschaltbaren Sprechansicht.
- **Nach JEDEM `willkommen`** (auch nach Wiederverbinden):
  `GET /verlauf?faden=<faeden.aktiv>&anzahl=60`, Kopfzeile `X-Sarvis-Schluessel` → `eintraege`
  ALT → NEU. Danach kommen neue/geänderte Einträge als Draht-Nachricht `eintrag`.
  **Gleiche `id` = Eintrag ersetzen**, nicht anhängen.
- „Ältere laden“: `&vor=<kleinste id>`, solange `mehr` wahr ist.
- `eintrag` mit `faden` ≠ aktiver Faden: überspringen.
- Rückfrage (`sorte: frage`, `daten.offen: true`): Text + **Ja/Nein-Knöpfe**, die
  `{"art":"zuruf","text":"Ja"}` bzw. `"Nein"` schicken. Sarvis wartet 75 Sekunden.
- Gesprächsliste (Fäden): wechseln, neu, umbenennen, archivieren (`faden_*`, siehe DRAHT.md).
- Lokal zwischenspeichern (Room) ist erlaubt; **Quelle der Wahrheit ist der Server** — nach jedem
  Verbinden neu holen.
- Mehrzeiliger `text` (Zeilenumbrüche) muss als mehrzeilig angezeigt werden.

**Abnahme:** `docker restart sarvis` auf dem Server → die App verbindet neu und zeigt **denselben
Verlauf** wie vorher.

## 2. Statuskarte laufender Aufträge

- `eintrag` mit `sorte: auftrag`, `daten`: `nummer`, `zustand` (`läuft` | `fertig` | `gestoppt` |
  `abgebrochen`), `projekt`. `text` ist mehrzeilig, z. B.:
  ```
  Auftrag 8 · portfolio · läuft seit 12 Min.
  Aufgabe: 3D-Objekte und Bewegung …
  Zuletzt erledigt: Punktkugel in Blender gebaut …
  Als Nächstes: Scroll-Animationen der Karten
  ```
- Kommt etwa **jede Minute neu mit derselben `id`** → an Ort und Stelle ersetzen.
- Symbol nach `zustand`: ⏳ läuft · ✅ fertig · ⚠️ gestoppt/abgebrochen.
- Schön, nicht Pflicht: laufende Aufträge oben im Verlauf anheften.

**Abnahme:** Auftrag starten, App schließen, nach ein paar Minuten öffnen → Karte zeigt Laufzeit
und zuletzt Erledigtes; am Ende ✅.

## 3. Nichts Getipptes verlieren

Vorlage `web/sarvis.js`: `senden`, `warteschlangeLeeren`, `frischVerbinden`, `visibilitychange`.

- Die Leitung gilt **erst nach `willkommen`** als bereit. Vorher und wenn sie zu ist: `zuruf` und
  `formular_antwort` in eine **Warteschlange**, nach dem nächsten `willkommen` in Reihenfolge
  senden. Älter als **90 Sekunden** → verwerfen.
- Ist die Leitung beim Senden zu: **sofort neu verbinden**, nicht auf das Backoff warten.
- App kommt nach **mehr als 20 Sekunden** aus dem Hintergrund (`ON_START`/`onResume`): alte
  WebSocket-Verbindung verwerfen, frisch verbinden (eine Leitung, die das schlafende Handy für offen
  hält, ist oft tot).
- Nicht verbunden: sichtbar „verbindet …“, Eingabe aber **nicht** sperren.
- `strom`/`sprache` (Audio) **nicht** puffern.

**Abnahme:** Flugmodus an, „Ja“ tippen, Flugmodus aus → im Serverprotokoll (`docker logs sarvis`)
steht `Du (<Gerät>): Ja`.

## 4. Formulare (offene Fragen ausfüllen)

`DRAHT.md` → „Formulare“. Vorlage `web/sarvis.js`: `formularKarte`, Klick auf `data-formular`.

- `eintrag` mit `sorte: formular`; `daten.fragen` = Liste aus `nr`, `titel`, `frage`.
- Solange `daten.offen`: je Frage Überschrift `titel`, darunter klein `frage`, darunter ein
  mehrzeiliges Eingabefeld. Unten **Absenden**.
- Absenden: `{"art":"formular_antwort","eintrag":<id>,"antworten":{"<nr>":"…"}}`, leere Felder
  als `""`. Danach Felder sperren.
- Der Server schickt denselben Eintrag neu (`offen: false`, `antworten`) → nur noch anzeigen.

**Abnahme:** Formular ausfüllen und abschicken → Sarvis startet einen Folgeauftrag (eine neue
Statuskarte ⏳ erscheint).

## 5. Webseiten-Vorschau (Kartenart `seite`)

`DRAHT.md` → „Blätter“, Zeile `seite`. Kommt als Draht-Nachricht `blatt` (`sorte: seite`) und im
Verlauf als `eintrag` `sorte: blatt` mit `daten.sorte: seite`, `daten.adresse`, `daten.titel`.

- **Adresse prüfen**, sonst nichts anzeigen:
  `^https://test\.tech-artist\.de/(vorschau|offen)/[a-z0-9-]+/$`
- Großflächig in einer **WebView mit JavaScript** (React-Seiten sind sonst weiß), mit Titel,
  „Schließen“ und **„Im Browser öffnen“** (`ACTION_VIEW`). JavaScript **nur** für diese
  geprüften Adressen — Blätter der Sorte `html` bleiben ohne.
- Keine `addJavascriptInterface`-Brücke, kein Zugriff auf App-Daten. Navigation auf eine andere
  Domain → externer Browser.
- `/vorschau/…` ist mit Benutzer/Passwort geschützt (HTTP Basic Auth): Anmeldedialog über
  `onReceivedHttpAuthRequest` anbieten, sonst bleibt „Im Browser öffnen“. `/offen/…` ist frei.
- Verlaufskarte: „Webseite“, Titel, Adresse; antippen = dieselbe Ansicht.

**Abnahme:** Sarvis „zeig mir die Portfolio-Seite, offen für alle“ → Seite erscheint bedienbar in
der App.

## 6. Links anklickbar

- In `sorte: text` und `meldung` jede `https://…`-Adresse als Link (z. B. `AnnotatedString` mit
  `LinkAnnotation.Url`), Satzzeichen am Ende nicht mit in den Link. Antippen → externer Browser.
- Nur `https://`.

## 7. Danach: Ablage und Benachrichtigungen

Steht in `AENDERUNG-OBERFLAECHE.md` (Ablage `GET /ablage`, `POST /ablage/oeffnen`; Push über
`/push/*`). Nicht dringend — erst, wenn 1–6 laufen.

---

## Serverseitig erledigt — in der App nichts zu tun

- Sarvis liest URLs und Dateipfade nicht vor.
- Aufträge starten ohne zweite Rückfrage; Rückfragen warten 75 s; Zeitablauf gilt nicht als Nein.
- Auftragsmeldungen sind am Satzende gekürzt und sagen ehrlich „fertig“ / „gestoppt“ /
  „Pensum aufgebraucht, soll ich fortsetzen?“.

## Bei Unklarheiten

Nicht raten: `DRAHT.md` lesen, dann in `web/sarvis.js` nachsehen, wie es dort gelöst ist. Weicht
die App bewusst ab, das im Commit begründen.
