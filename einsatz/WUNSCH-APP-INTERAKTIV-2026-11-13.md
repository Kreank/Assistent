# Wunsch der Android-App: Antworten anhaken statt nur lesen (13.11.2026, abends)

Von: dem Agenten, der die Sarvis-Android-App baut. Auf Wunsch von Sascha:

> „Momentan ist alles auf Zeigen ausgelegt." Wenn Sarvis eine Liste macht,
> auf die Sascha antworten soll, soll sie **ausfüllbar** sein; Sarvis liest
> die Antworten und arbeitet sie ein. Hat Sarvis im Chat eine Nachfrage,
> stellt er **kontextbezogene Fragen mit Antworten zum Anhaken**
> (Einfach- und Mehrfachauswahl).

Heute gibt es zwei Bausteine: die **Rückfrage** (Ja/Nein vor einer
Handlung) und das **Formular** (nur Freitext, nur aus offenen Fragen eines
Auftrags, `main.py:389`, `main.py:528`). Dieser Wunsch baut das Formular
aus, statt etwas Neues danebenzustellen. Alles bleibt rückwärtsverträglich:
Fehlt ein neues Feld, verhält sich alles wie heute.

Was die App baut, steht am Ende. Sie kann die neuen Felder schon zeigen,
bevor der Server sie schickt — es kommt dann eben nur Freitext.

---

## 1. Fragen mit Antwortarten (Formular, erweitert)

Jede Frage in `daten.fragen` bekommt optional:

| Feld | Werte | Bedeutung |
|---|---|---|
| `typ` | `text` (Vorgabe) · `einfach` · `mehrfach` · `janein` · `zahl` · `datum` | wie man antwortet |
| `optionen` | Liste von Strings, höchstens 8, je ≤ 60 Zeichen | bei `einfach`/`mehrfach` |
| `frei` | bool | zusätzlich „Anders: …" mit Textfeld |
| `vorschlag` | String oder Liste | vorbelegt (Sarvis' Vermutung) |
| `pflicht` | bool | ohne Antwort kein Abschicken |

Antworten in `formular_antwort` (Draht) und in `daten.antworten`:

- `text`, `einfach`, `zahl`, `datum` (ISO `2026-11-20`), `janein` (`"ja"`/`"nein"`) → **String**
- `mehrfach` → **Liste von Strings**
- „Anders" → der eingetippte Text steht als Wert (bei `mehrfach` als weiteres Listenelement)
- leer / leere Liste → „weiß ich noch nicht"

**Server-Änderung:** `main.py:555` macht heute `str(v)` aus jedem Wert —
Listen bitte als Liste behalten (je Element ≤ 200 Zeichen, höchstens 20)
und für den Text ans Hirn mit „, " verbinden.

## 2. Rückfrage mit Auswahl im Chat (neues Werkzeug fürs Hirn)

Ein Werkzeug, z. B. `fragen_stellen(titel, fragen)`, mit dem Sarvis im
**laufenden Gespräch** ein Formular hinlegt — nicht nur am Ende eines
Auftrags. Es wird ein `eintrag` mit `sorte: formular` wie heute, dazu:

- `daten.zweck`: `"rueckfrage"` (aus dem Gespräch) oder `"auftrag"` (wie heute; fehlt es → `"auftrag"`).
- Gesprochen sagt Sarvis nur einen Satz („Ich hab dir drei Fragen hingelegt.").
  Im Auto (`kann_anzeigen` falsch o. ä.) lieber gar kein Formular, sondern
  wie bisher fragen.
- **Antworten:** bei `zweck: rueckfrage` als gewöhnlicher Zuruf in **denselben
  Faden** („Meine Antworten auf „…": 1. Farbe: Blau, Grün · 2. Termin:
  2026-11-20"), **nicht** als Folgeauftrag.
- **Beantwortet Sascha stattdessen mit der Stimme oder tippt frei**, solange
  ein Rückfrage-Formular offen ist: Formular schließen mit
  `daten.offen = false`, `daten.erledigt = "anders"`. Dann zeigt die App
  es grau und nicht mehr ausfüllbar.

Regel fürs Hirn (Vorschlag für den Systemtext):

- Ja/Nein **vor einer Handlung** → wie heute die Rückfrage (`frage`).
- Eine oder mehrere **Entscheidungen mit klaren Möglichkeiten** →
  `fragen_stellen` mit `einfach`/`mehrfach`, Optionen kurz, die
  wahrscheinlichste als `vorschlag`, `frei: true`, wenn die Liste nicht
  vollständig sein kann.
- **Viele offene Angaben** (Portfolio: Kontakt, Texte, Bilder …) → ein
  Formular mit `text`-Feldern statt einer Markdown-Liste „offene Punkte".
- Reine Information → Blatt wie heute.

## 3. Formulare in der Ablage und später beantworten

Heute sucht `_formular_antwort` das Formular nur in den letzten 200
Einträgen des **aktiven** Fadens (`main.py:544`). Ein Formular, das in der
Ablage liegt, muss sich aber auch Tage später und aus einem anderen Faden
heraus beantworten lassen.

- `formular_antwort` findet den Eintrag über seine `id` **in jedem Faden**
  und schickt die Antworten in den Faden, in dem das Formular steht.
- `GET /ablage` führt Formulare mit `sorte: "formular"`, `schluessel:
  "fm-<eintrag>"`, `titel`, `seit`, `faden`, dazu **`offen`** (bool) und
  **`fragen`** (Anzahl). Offene zuerst.
- `POST /ablage/oeffnen { "schluessel": "fm-<eintrag>" }` → `{ "eintrag":
  { … der ganze Verlaufseintrag … } }`. Die App zeigt das Formular dann
  bildschirmfüllend.

## 4. Abhaken in Markdown-Blättern

Für Listen, die nur abgehakt werden („Portfolio – offene Punkte", Einkauf,
Packliste): Sarvis schreibt sie als Aufgabenliste `- [ ] …` / `- [x] …`.
Die App zeigt dort echte Kästchen.

```
POST /blatt/haken   { "schluessel": "md-<eintrag>", "zeile": 7, "an": true }
→ { "gut": true, "inhalt": "<das ganze neue Markdown>" }   · 404 · 409
```

- `zeile` zählt ab 0 im `inhalt`, wie die App ihn bekommen hat. Steht dort
  keine Aufgabenzeile mehr (Blatt inzwischen geändert): **409** mit dem
  aktuellen `inhalt`, die App zeigt dann den.
- Der Server ersetzt nur `[ ]`↔`[x]` in genau dieser Zeile und legt den
  Eintrag mit derselben `id` neu (`eintrag` an alle), damit auch andere
  Geräte den Haken sehen.
- Liest Sarvis das Blatt später, sieht er die Haken — kein eigener Zuruf.
- Vertraulich wie `/ablage`, also mit `X-Sarvis-Schluessel`.

---

## Was die App baut (zur Abstimmung, kein Auftrag an den Server)

- Formularfelder je `typ`: Auswahlchips (einfach/mehrfach), Ja/Nein-Knöpfe,
  Zahl, Datumswähler, Freitext, „Anders: …"; Pflichtfelder; Entwurf bleibt
  auf dem Gerät, bis abgeschickt.
- Rückfrage-Formulare direkt im Chat; große Formulare öffnen sich
  bildschirmfüllend.
- Ablage: Filter „Zum Ausfüllen" mit Zähler, offene Formulare oben.
- Kästchen in Markdown-Blättern (Antippen → `/blatt/haken`).
- Daneben, weil der Server es schon kann: Ansichten „Geplant" und
  „Gedächtnis", Fortschrittsbalken für Aufträge.
- Neues Erscheinungsbild nach Material 3 (2025/26): Chat im Mittelpunkt,
  Gesprächsliste als Seitenleiste, große Eingabeleiste; die Kugel wird
  zur Nebensache.

## Abnahme

1. Sarvis fragt im Gespräch „Welche Farben fürs Portfolio?" als
   `mehrfach`-Formular; Sascha hakt zwei an und tippt eine dritte bei
   „Anders" → Sarvis antwortet im selben Faden mit allen drei.
2. Ein Formular von gestern aus der Ablage beantworten, während ein
   anderer Faden aktiv ist → kommt an, Formular ist danach zu.
3. Ein Kästchen in „Portfolio – offene Punkte" abhaken → auf dem zweiten
   Gerät ist es auch abgehakt; Sarvis sieht es, wenn er das Blatt liest.
4. Altes Formular (ohne `typ`) → unverändert Freitext.
