# Änderungsblatt für die Android-App — 13.11.2026

**Für den Agenten, der die Sarvis-Android-App baut** (Package `de.techartist.sarvis`).

Maßgeblich für jedes Feld ist `einsatz/DRAHT.md`. Dieses Blatt sagt, **was in der App fehlt**, in
welcher Reihenfolge es gebaut werden soll und woran man merkt, dass es fertig ist. Vorlage zum
Abschauen ist die Weboberfläche `web/sarvis.js` — dort ist alles schon umgesetzt.

> **Keine bestehende Nachrichtenart wurde geändert.** Die App läuft weiter wie bisher. Alles hier
> sind Ergänzungen.

---

## Warum (was Sascha erlebt)

1. **Nach jedem Neustart von Sarvis ist der Bildschirm leer.** Kein Verlauf, kein Hinweis, ob ein
   Auftrag noch läuft. Der Server hat aber alles gespeichert — die App fragt es nur nie ab.
   (Gemessen: Die App ruft `/draht` und `/dateien`, aber nie `/verlauf`.)
2. **Ein getipptes „ja“ auf eine Rückfrage ging verloren.** Das Handy kam gerade aus dem Standby,
   die Leitung war noch nicht wieder offen, die App zeigte das „ja“ trotzdem als gesendet. Sarvis
   wartete 35 Sekunden und brach mit „Ich habe keine Antwort bekommen“ ab.
3. **Eine Vorschau-Karte war leer.** Sarvis kann jetzt Webseiten aus Projekten bauen und zeigen
   (Kartenart `seite`), die App kennt sie nicht.
4. **Links in Antworten sind nicht anklickbar.**

---

## Aufgabe 1 (zuerst, wichtigste): Verlauf und Gesprächsfäden

Steht vollständig in **`einsatz/AENDERUNG-OBERFLAECHE.md`** (Abschnitte 1–3) und in `DRAHT.md`
„Gesprächsverlauf und Fäden“. Wurde bisher nicht umgesetzt. Kurzfassung:

- Hauptbildschirm = **Verlauf wie in einem Messenger** (Zurufe rechts, Antworten links, Karten für
  Blätter, Berichte, Dateien, Kacheln, Rückfragen). Der Ring wird zur umschaltbaren Sprechansicht.
- **Nach JEDEM `willkommen`** (auch nach Wiederverbinden):
  `GET /verlauf?faden=<faeden.aktiv>&anzahl=60` mit Kopfzeile `X-Sarvis-Schluessel` → Liste
  ALT → NEU. Danach neue/geänderte Einträge per Draht-Nachricht `eintrag` (gleiche `id` = ersetzen).
- „Ältere laden“ mit `&vor=<kleinste id>`, solange `mehr` wahr ist.
- Rückfrage-Karte (`sorte: frage`, `daten.offen: true`) mit **Ja/Nein-Knöpfen**, die
  `{"art":"zuruf","text":"Ja"}` bzw. `"Nein"` schicken.
- Gesprächsliste (Fäden): wechseln, neu, umbenennen, archivieren.
- Einträge lokal (Room o. ä.) zwischenspeichern ist erlaubt, **Quelle der Wahrheit bleibt der
  Server** — nach dem Wiederverbinden immer neu holen.

**Fertig, wenn:** Sarvis wird neu gestartet (`docker restart sarvis` auf dem Server), die App
verbindet sich neu und zeigt danach **denselben Verlauf** wie vorher, inklusive der letzten
Meldungen zu Aufträgen.

---

## Aufgabe 2: Nichts Getipptes verlieren

Vorlage: `web/sarvis.js`, Funktionen `senden`, `warteschlangeLeeren`, `frischVerbinden` und der
`visibilitychange`-Block.

- **Erst nach `willkommen` gilt die Leitung als bereit.** Vorher (und wenn sie zu ist) kommen
  `zuruf`-Nachrichten — auch die Ja/Nein-Knöpfe — in eine **Warteschlange** und werden direkt nach
  dem nächsten `willkommen` in Reihenfolge gesendet. Älter als **90 Sekunden** → verwerfen
  (sonst platzt ein altes „ja“ in eine neue Frage).
- Ist die Leitung beim Tippen zu, **sofort neu verbinden**, nicht auf das Backoff warten.
- **App kommt nach mehr als 20 Sekunden aus dem Hintergrund** (`onResume`/`ON_START`): alte
  WebSocket-Verbindung verwerfen und frisch verbinden. Eine Leitung, die ein schlafendes Handy für
  offen hält, ist oft tot — was man darauf sendet, verschwindet ohne Fehler.
- Solange nicht verbunden: sichtbar anzeigen („verbindet …“), Eingabe aber **nicht** sperren.
- `strom`-/Audio-Nachrichten **nicht** puffern (veraltet, sinnlos), nur `zuruf`.

**Fertig, wenn:** Flugmodus an, „Ja“ tippen, Flugmodus aus → das „Ja“ kommt beim Server an
(im Serverprotokoll `docker logs sarvis` steht `Du (<Gerät>): Ja`).

---

## Aufgabe 3: Kartenart `seite` (Webseiten-Vorschau)

Siehe `DRAHT.md` → „Blätter“, Zeile `seite`. Kommt als Draht-Nachricht `blatt` und im Verlauf als
`eintrag` mit `sorte: blatt`, `daten.sorte: seite`, `daten.adresse`, `daten.titel`.

- **Adresse prüfen**, sonst nichts anzeigen:
  `^https://test\.tech-artist\.de/(vorschau|offen)/[a-z0-9-]+/$`
- Anzeigen in einer **WebView mit JavaScript an** (React-Seiten sind sonst weiß), großflächig wie
  ein Blatt, mit Titel, „Schließen“ und **„Im Browser öffnen“** (Intent `ACTION_VIEW`).
  Nur für diese geprüften Adressen JavaScript erlauben — alle anderen Blätter (`html`) bleiben
  **ohne** JavaScript, wie bisher.
- In der WebView keine `addJavascriptInterface`-Brücke, kein Zugriff auf App-Daten, Navigation aus
  der Vorschau heraus (andere Domain) → im externen Browser öffnen statt in der WebView.
- `/vorschau/…` ist mit Benutzer/Passwort geschützt (HTTP Basic Auth). Die WebView soll den
  Anmeldedialog anbieten (`onReceivedHttpAuthRequest` → Dialog) — oder es bleibt beim Knopf
  „Im Browser öffnen“. `/offen/…` braucht nichts.
- Verlaufskarte: Art „Webseite“, Titel, darunter die Adresse; antippen = dieselbe Ansicht öffnen.

**Fertig, wenn:** Sascha sagt Sarvis „zeig mir die Portfolio-Seite, offen für alle“, und die Seite
erscheint in der App bedienbar (scrollen, Hell/Dunkel umschalten).

---

## Aufgabe 4: Links in Textblasen anklickbar

- In `sorte: text` und `meldung` jede `https://…`-Adresse als Link darstellen
  (z. B. `LinkifyText`/`AnnotatedString` mit `UrlAnnotation`), Satzzeichen am Ende nicht mit in den
  Link nehmen. Antippen → externer Browser.
- Nur `https://`, keine anderen Schemata.

---

## Aufgabe 5: Formulare (offene Fragen ausfüllen)

Siehe `DRAHT.md` → „Formulare“. Hat ein Auftrag offene Fragen, kommt ein `eintrag` mit
`sorte: formular`. Vorlage: `web/sarvis.js`, Funktion `formularKarte` und der Klick auf
`data-formular`.

- Solange `daten.offen`: je Frage Überschrift (`titel`), darunter klein `frage`, darunter ein
  mehrzeiliges Eingabefeld. Unten „Absenden“.
- Absenden schickt `{"art":"formular_antwort","eintrag":<id>,"antworten":{"<nr>":"…"}}` — leere
  Felder als leeren Text. Wie `zuruf` in die Warteschlange, wenn die Leitung nicht steht.
- Danach kommt derselbe Eintrag neu (`offen: false`, `antworten`) → Antworten nur noch anzeigen.

**Fertig, wenn:** Ein Formular in der App ausgefüllt und abgeschickt wird und Sarvis daraufhin einen
Folgeauftrag startet (Rückfrage „Soll ich einen Auftrag … starten?“ erscheint).

## Aufgabe 6: Statuskarte laufender Aufträge

Solange ein Hintergrundauftrag läuft, liegt im Verlauf ein `eintrag` mit `sorte: auftrag`.
Er wird **laufend mit derselben `id` ersetzt** (etwa jede Minute): Laufzeit, Aufgabe, zuletzt
erledigt, als Nächstes — am Ende „fertig“ oder „gestoppt“ mit Grund. `text` ist mehrzeilig
(Zeilenumbrüche anzeigen), `daten.zustand` ist `läuft` | `fertig` | `gestoppt` | `abgebrochen`
(z. B. Symbol ⏳ / ✅ / ⚠️). Ohne Aufgabe 1 (Verlauf + `eintrag` per Draht) sieht man sie nicht —
das ist der Grund, warum Sascha nach einer Stunde Abwesenheit nicht wusste, was los ist.

## Nicht nötig (serverseitig schon erledigt)

- Sarvis liest URLs und Dateipfade nicht mehr vor — das macht der Server vor der Sprachausgabe.
- Auftragsmeldungen sind klarer formuliert („Pensum aufgebraucht, soll ich fortsetzen?“) — kommen als
  normale `meldung`, keine App-Änderung.

## Prüfen

- `python einsatz/draht_pruefen.py` auf dem Server: DRAHT.md stimmt mit dem Code überein.
- Reihenfolge: Aufgabe 1 → 6 → 2 → 3 → 4 → 5. Nach jeder Aufgabe einzeln testbar.
