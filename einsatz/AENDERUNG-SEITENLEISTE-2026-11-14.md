# Vertrag: Seitenleiste — Kalender, Ordner, Gespräche löschen (14.11.2026)

**Für den Agenten, der die Sarvis-Android-App baut** (Package `de.techartist.sarvis`).

Saschas Wunsch an die App (14.11.2026, wörtlich gekürzt):

> In der Leiste, die erscheint, wenn ich nach rechts wische (Ablage, Gedächtnis …), hätte ich gerne
> noch den **Google-Kalender** mit drin, dass ich nicht immer in meine Kalender-App wechseln muss.
> Dann hätte ich gerne die **Ordner strukturiert aufgelistet, zu denen Sarvis Zugang hat** (ich bin
> ein Mensch und sehe gerne visuell). Ich brauche noch die Möglichkeit, **Gespräche löschen** zu können.

Seine Entscheidungen dazu: **Kalender ansehen UND bearbeiten** (anlegen, ändern, löschen).
**Gespräche löschen = Papierkorb, 30 Tage zurückholbar**, danach endgültig.

Der Server ist fertig und läuft. Maßgeblich für jedes Feld ist `einsatz/DRAHT.md`, Abschnitte
**„Kalender“**, **„Ordner“** und **„Hinaus: die Fadenbefehle“** (Papierkorb).
`python einsatz/draht_pruefen.py` ist grün.

> **Nichts Bestehendes wurde geändert oder entfernt.** `faeden` hat nur ein neues Feld `papierkorb`.
> Gelöschte Gespräche stehen nicht mehr in `liste`.

## Übersicht

| # | Was | Server | App |
|---|---|---|---|
| 1 | Gespräche löschen + Papierkorb | ✅ | ⬜ |
| 2 | Kalender (Liste/Woche, Termin anlegen/ändern/löschen) | ✅ | ⬜ |
| 3 | Ordner als Baum zum Durchklicken | ✅ | ⬜ |

## 1. Gespräche löschen

- In der Gesprächsliste: Löschen (Wischgeste oder Menü) schickt
  `{ "art": "faden_loeschen", "faden": "f-…" }`. **Keine Sicherheitsabfrage nötig** — es ist ja
  zurückholbar. Besser: kurzer Hinweis „In den Papierkorb gelegt · Rückgängig“ (Rückgängig =
  `faden_wiederherstellen`).
- Danach kommt `faeden` mit neuer `liste` und `papierkorb`. Wurde das aktive gelöscht, ist schon ein
  neues, leeres aktiv.
- **Papierkorb** als eigener Punkt (z. B. unten in der Gesprächsliste, mit Anzahl). Je Eintrag:
  Titel, „gelöscht am …“, „wird am … endgültig gelöscht“ (`endgueltig`), Knöpfe
  **Wiederherstellen** und **Endgültig löschen** (`papierkorb_leeren` mit `faden`).
  Oben **„Papierkorb leeren“** (`papierkorb_leeren` ohne `faden`).
- **Endgültig** braucht eine Sicherheitsabfrage — das ist nicht umkehrbar.
- Ein Gespräch im Papierkorb antippen = Verlauf ansehen über `GET /verlauf?faden=…` (geht weiter),
  ohne zu wechseln. Wechseln würde es wiederherstellen.

## 2. Kalender

- Eintrag „Kalender“ in der Seitenleiste. Ansicht: **Agenda** (Tage untereinander, Termine darunter)
  reicht; heute oben. `GET /termine?tage=14`, beim Herunterscrollen weiter mit `von=`.
- Farbe je Termin = `farbe` des Kalenders. Ganztägige oben am Tag. Ort/Notiz in der Detailansicht.
- **Neuer Termin:** Knopf „+“ → Titel, Datum, Uhrzeit von/bis oder „ganztägig“, Ort, Notiz,
  Kalender (nur die mit `schreiben: true`, Vorgabe `haupt`). `POST /termin/anlegen`.
- **Termin antippen:** Details; bei `schreiben: true` Bearbeiten (`/termin/aendern`, nur geänderte
  Felder schicken) und Löschen (`/termin/loeschen`, mit Sicherheitsabfrage).
  Bei `serie: true` dazuschreiben „betrifft nur diesen Termin“.
- Feiertage-Kalender u. ä. (`schreiben: false`) nur anzeigen, keine Bearbeiten-Knöpfe.
- Fehler 503 = „Google ist auf dem Server nicht angemeldet“ als ruhiger Hinweis, nicht als Absturz.
- Nach jeder Änderung und beim Öffnen der Leiste neu holen (Sarvis kann per Sprache auch Termine
  anlegen; dafür gibt es keine Meldung am Draht).

## 3. Ordner

- Eintrag „Ordner“ in der Seitenleiste. Start: `GET /ordner` → die Wurzeln als **Kacheln** mit Name,
  Beschreibung und drei kleinen Zeichen für `darf` (lesen/schreiben/durchsuchen; `frei` = grün,
  `fragen` = gelb mit Hinweis „fragt vorher“). Die Liste nicht in der App festschreiben.
- Antippen → `GET /ordner?pfad=…` → Liste: Ordner-/Dateisymbol (nach Endung), Name, Größe, Datum.
  Zurück über `oben` (oder Brotkrumen aus `pfad`). Versteckte Einträge standardmäßig einklappen
  („12 versteckte zeigen“).
- `geschuetzt: true` → Schloss-Symbol, nicht antippbar.
- Keine Dateiinhalte, kein Download hier. (Wer eine Datei will, sagt es Sarvis.)

## Abnahme

1. Gespräch löschen → verschwindet aus der Liste, steht im Papierkorb; Wiederherstellen bringt es
   mit vollem Verlauf zurück; „Endgültig“ fragt nach und entfernt es.
2. Kalender zeigt dieselben Termine wie Google Kalender auf dem Handy; ein in der App angelegter
   Termin erscheint in der Google-Kalender-App und umgekehrt; Verschieben behält die Dauer.
3. Ordner: Projekte → `sarvis` → `einsatz` lässt sich durchklicken; `.ssh` im Benutzerordner hat ein
   Schloss und öffnet nicht.
