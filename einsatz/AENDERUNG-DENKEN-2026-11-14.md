# Vertrag: Sarvis' Denken sichtbar + Stimme in Stücken (14.11.2026)

**Für den Agenten, der die Sarvis-Android-App baut** (Package `de.techartist.sarvis`).

Saschas Wunsch (14.11.2026): „Es wäre cool, wenn ich sein Denken sehen könnte … wie im Web das
Denken aufklappen und sehen, was gerade gemacht wird. Natürlich sauber ausgegeben.“

Der Server ist fertig und läuft, die Web-Oberfläche zeigt es schon. Maßgeblich: `einsatz/DRAHT.md`,
Tabelle der Verlaufseinträge, Zeile **`sarvis` / `denken`**, und Abschnitt „Ton abspielen“.

## 1. Gedanken-Karte (`eintrag` mit `sorte: "denken"`)

- Kommt als gewöhnlicher `eintrag` und steht im Verlauf zwischen Zuruf und Antwort, auch nach
  `GET /verlauf`.
- **Zugeklappt**: eine leise Zeile mit `text` („Denkt nach …“ / „Gedanken · 3 Schritte · 4 s“),
  Pfeil zum Aufklappen. Solange `daten.fertig == false`: pulsierender Punkt.
  `daten.abgebrochen == true`: „· abgebrochen“ anhängen.
- **Aufgeklappt**: Zeitleiste aus `daten.schritte`:
  - `gedanke`: „Überlegt“ + `text` (kursiv, mehrzeilig).
  - `werkzeug`: `titel` fett, darunter `text`; Zeichen je `stand`: läuft ⏳ · fertig ✓ · fehler ✗;
    `ergebnis` klein und blass darunter.
- Dieselbe `id` kommt mehrfach (live). **Ersetzen, nicht anhängen, und den Auf-/Zu-Zustand behalten.**
- Bis das umgesetzt ist, zeigt die App die Karte als normale Sarvis-Blase mit `text` — unschön, bricht
  aber nichts.

## 2. Stimme in Stücken (`ton`)

Seit heute spricht Sarvis mit Pocket TTS und schickt einen Satz in **mehreren `ton`-Blöcken**
(erster ~0,48 s, dann je ~0,24 s, `rate` 24000). Die Blöcke **nahtlos aneinanderhängen**, nicht je
Block eine neue Wiedergabe mit Pause. Gemessen ist jeder Block ~0,3 s vor seinem Einsatz da.
Hört Sascha in der App Pausen mitten im Satz, liegt es hier.

## Abnahme

1. Frage, bei der Sarvis ein Werkzeug braucht („Was steht morgen im Kalender?“) → über der Antwort
   die Zeile „Gedanken · 1 Schritt · …“, aufgeklappt „Termine ansehen“ mit ✓ und Auszug.
2. Während er arbeitet: „Denkt nach …“ mit Puls, Schritte erscheinen nacheinander.
3. Ein langer Satz klingt in der App ohne Stocker.
