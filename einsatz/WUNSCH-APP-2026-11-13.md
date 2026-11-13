# Wünsche der Android-App an den Server — 13.11.2026

**Für den Agenten, der den Sarvis-Server baut.** Gegenstück zu
`AENDERUNG-2026-11-13.md`: Dort stand, was die App nachziehen muss. Hier
steht, was der App fehlt und nur der Server liefern kann. Reihenfolge =
Nummer = Nutzen für Sascha.

> **Nichts davon ist eilig für den Betrieb.** Die App läuft mit dem heutigen
> Server vollständig. Alles hier sind Ergänzungen; bestehende Arten und
> Felder bleiben, wie sie sind.

## Was die App seit heute kann (Stand Commit `4cfe6aa`, Repo `Assistent_android`)

Punkte 1–6 aus `AENDERUNG-2026-11-13.md` sind gebaut: Verlauf mit `GET
/verlauf` nach jedem `willkommen`, Fäden (neu/wechseln/umbenennen/archivieren),
Suche über `GET /suche`, Statuskarten, Ja/Nein-Knöpfe, Formulare,
Warteschlange (90 s), Webseiten-Vorschau `seite`, Links.

Dazu **ohne Server-Änderung**:
- Benachrichtigungen, solange der Draht offen ist (der Vordergrunddienst hält
  ihn auch in der Tasche): `meldung` → Benachrichtigung mit „Antworten“,
  offene `frage` → Benachrichtigung mit **Ja/Nein** (schickt normalen
  `zuruf`), laufende `auftrag`-Karte → stille, laufende Benachrichtigung.
- Schnelleinstellungs-Kachel und App-Kürzel „Zuhören“ / „Neues Gespräch“.

`kann_radio` meldet die App weiterhin **nicht** (kein eigenes Abspielwerk).
Punkt 7 (Ablage-Bildschirm, Push) ist auf App-Seite noch offen.

---

## 1. Geplante KI-Aufgaben — dauerhaft und verwaltbar (wichtigster Punkt)

**Warum.** Am 13.11. um 16:07 sagte Sarvis im Verlauf: „Solche
Daueraufträge laufen nach sieben Tagen aus, dann muss ich sie neu stellen.“
Ein Morgenbriefing, das nach einer Woche still aufhört, ist keins. Genau
das ist inzwischen Standard bei den Großen: ChatGPT „Tasks“ und Gemini
„Scheduled Actions“ führen einen Auftrag zu einer festen Zeit wiederkehrend
aus, mit einer **Übersicht zum Pausieren und Löschen**; Gemini hat dazu ein
„Daily Brief“. Beide begrenzen auf rund zehn aktive Aufgaben. Das Zielbild
(`notizen/2026-11-10-recherche-zielbild.md`, Baustein 7, Bildschirm 5
„Geplant“) sieht dasselbe vor.

**Vorschlag.** Der `Wecker` (`werkzeuge/zeit.py`) kann schon alles
Schwierige: fester Zeitpunkt, Wanduhr, `wiederholt`
(täglich/wöchentlich/monatlich), übersteht Neustarts über `timer.json`.
Was fehlt, ist eine zweite Sorte Eintrag, die beim Fälligwerden nicht einen
festen Satz spricht, sondern einen **Auftrag** ausführt (Hintergrundauftrag
wie `werkzeuge/auftrag.py` oder ein Zug des Hirns), und deren Ergebnis als
`meldung`/Blatt in den Verlauf und per Push kommt. Ohne Ablaufdatum.

**Schnittstelle** (Vorschlag, gern anders, Hauptsache in DRAHT.md):

```
GET  /geplant                    (X-Sarvis-Schluessel)
→ { "eintraege": [ { "nummer": 7, "sorte": "timer" | "aufgabe",
                     "was": "Morgenbriefing: Kalender, Wetter, Security-News",
                     "faellig": 1794466800.0, "wiederholt": "taeglich" | null,
                     "pausiert": false, "zuletzt": 1794380400.0 | null } ] }
POST /geplant/loeschen   { "nummer": 7 }          → { "gut": true }
POST /geplant/pausieren  { "nummer": 7, "an": true } → { "gut": true }
```

Plus Draht-Art `geplant` (ganze Liste, ein Zustand, wie `faeden`) nach jeder
Änderung. Anlegen bleibt **beim Sprechen** („jeden Morgen um sieben ein
Briefing“); die App braucht zum Anlegen keinen eigenen Weg.

Löschen und Pausieren über HTTP sind Handlungen des Menschen in seiner
eigenen App, also **ohne Rückfrage**. Anlegen einer Aufgabe, die nach außen
handelt (Mail, Telegram), unterliegt weiter den Stufen.

**Abnahme.** „Jeden Morgen um 7 ein Briefing“ sagen → `GET /geplant` zeigt
es → Server neu starten → am nächsten Morgen kommt das Briefing, und auch
noch am achten Tag.

## 2. Gedächtnis einsehen und löschen

**Warum.** Zielbild Abschnitt C: „Gedächtnis einsehen und löschen — per
Sprache ja, keine Ansicht in der App.“ ChatGPT und Claude zeigen das
Gedächtnis als Liste mit Löschen; Vertrauen in einen Assistenten, der sich
Dinge merkt, hängt daran, dass man nachsehen kann.

**Schnittstelle.**

```
GET  /gedaechtnis
→ { "gemerkt": [ { "id": "…", "text": "…", "seit": 1794… } ],
    "beobachtet": [ … ], "entschieden": [ … ],
    "personen": [ { "id": "…", "name": "…", "text": "…" } ] }
POST /gedaechtnis/vergessen  { "id": "…" }  → { "gut": true } · 404
```

Dieselben Daten, die `gedaechtnis_zeigen` und `vergessen`
(`werkzeuge/erinnern.py`) schon benutzen. Vertraulich wie `/dateien`, also
mit Schlüssel.

**Abnahme.** In der App einen Eintrag löschen → „Was weißt du über …?“ →
Sarvis kennt ihn nicht mehr.

## 3. Fortschritt in der Statuskarte (klein)

**Warum.** Die App zeigt laufende Aufträge jetzt als laufende
Benachrichtigung. Android 16 (QPR1) kann daraus eine „Live Update“-Anzeige
mit Fortschrittsbalken in der Statusleiste machen. Dafür fehlt nur eine
Zahl: Wie weit ist der Auftrag?

**Wunsch.** In `daten` der `sorte: auftrag` zusätzlich `seit` (Startzeit,
Unix-Sekunden), `schritte` (bisher) und `pensum` (Höchstzahl, heute 250).
Rein additiv; die App rechnet daraus den Balken und zeigt ohne die Felder
weiter den unbestimmten Balken.

## 4. Satzende-Erkennung statt fester Stillezeiten (Recherche, groß)

**Warum.** Das ist der größte spürbare Zeitgewinn im Gespräch. Laut README
wartet der Server 0,55–1,4 s Stille, bevor er einen Satz für beendet hält,
und zwar in **jeder** Runde. Branchenrichtwert sind ~800 ms vom Satzende
bis zum ersten Ton. Stand der Technik ist ein kleines Modell, das an Klang
und Wortlaut erkennt, ob der Satz fertig ist:

- **Pipecat Smart Turn v3**: Whisper-Tiny-Encoder plus Linearschicht,
  BSD-2-Lizenz, läuft auf CPU, 23 Sprachen (laut forasoft/Medium). Ein
  Hersteller-Benchmark nennt 94 % richtige Satzenden bei 1 % zu frühem
  Abschneiden (englisch, 200 Clips, also nur ein Anhaltspunkt).
- LiveKit Turn Detector: Lizenz „LiveKit Model License“, Angaben zur
  Architektur widersprüchlich. Eher nicht.

**Vorschlag.** Erst messen (Zeit zwischen Satzende und Ton, getrennt nach
Stille-Wartezeit), dann Smart Turn vor die festen Zeiten setzen: bei hoher
Sicherheit früher abschneiden, sonst wie bisher.

## 5. Push bei beendeter App (nur nach Saschas Entscheidung)

Die App bekommt Meldungen, solange ihr Dienst läuft. Wird er beendet, kommt
nichts. Der Weg dafür wäre UnifiedPush mit einem Verteiler (z. B. ntfy, auch
selbst gehostet). Er braucht auf dem Handy eine Verteiler-App und in der App
eine neue Bibliothek, und beides muss Sascha erst freigeben. Auf dem Server
wäre es dann nur der Host des Verteilers in `config.PUSH_DIENSTE`. **Bis
dahin nichts tun.**

---

### Quellen der Recherche (13.11.2026, Fachpresse, Richtwerte)

- Gemini Scheduled Actions / ChatGPT Tasks: techradar.com („Gemini's new
  Scheduled Actions …“), tech.yahoo.com („Google Gemini's scheduled actions
  finally …“), techcrunch.com (2026-05-19, Gemini Daily Brief, I/O 2026)
- Smart Turn / Turn Detection: forasoft.com („Pipecat vs LiveKit Agents
  2026“), benchmarks.speko.ai („Turn-Taking for Voice Agents 2026“),
  micdrop.dev („Smart Turn and End of Turn Detection“)
- Live Updates: androidauthority.com („Android 16 QPR1 adds full support for
  Live Updates“), androidpolice.com (Anforderungen)
- UnifiedPush: unifiedpush.org (FAQ, Distributors, Developers/Intro)
