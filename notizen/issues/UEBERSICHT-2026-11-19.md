# Review vom 19.11.2026 — Änderungen seit 0fbb0fd (22 Commits, ~10.000 Zeilen)

Drei Prüfer parallel (Bremse/Außenwirkung, Netz-Endpunkte, Hauptschleife/Sprache),
schwere Funde danach selbst nachgeprüft. Behoben im selben Zug, getestet im Container
(rueckfragen_pruefen, draht_pruefen, pruefung_gedaechtnis 23/23, wache_test 6/6 und
gezielte Proben je Fund).

| Schwere | Fund | Status |
|---|---|---|
| hoch | Arbeiter (seit 13.11. ohne Rückfrage) konnten im Sarvis-Repo selbst schutz.py/config.py umschreiben | behoben: `projekte.eigenes_repo()` sperrt Sarvis als Ziel für Aufträge und Vorschau. Ohne-Rückfrage-Start bleibt (Saschas Entscheidung) |
| hoch | Outlook: Frage nannte `an`, Werkzeug antwortete an den Absender von `antwort_auf` | behoben: beides zugleich wird abgelehnt, Frage folgt der Werkzeug-Reihenfolge |
| hoch | Vorschau „offen“ kopierte das ganze Projekt (eingang/, zugang.env, DBs, Symlink-Ziele) | behoben: Erlaubnisliste Webdateien, keine Symlinks, `schutz.heikel` je Datei |
| hoch | Push nach geplanter Aufgabe meldete Zufallssätze statt des Ergebnisses | behoben: `_letzte_antwort` |
| mittel | Outlook-CC fehlte in der Rückfrage | behoben |
| mittel | Termin-Nummern verrutschten nach dem Löschen | behoben: Lücke (None) statt remove |
| mittel | Vorschau-Build blockierte die Ereignisschleife bis 20 min; npm-Skripte mit vollen Rechten/Umgebung | behoben: `to_thread`, `--ignore-scripts`, Umgebung ohne Schlüssel. Rest: `npm run build` führt weiter Projektcode aus |
| mittel | Geplante Aufgabe mit Rückfrage: nachts laut an alle Geräte, verschluckte echten Zuruf | behoben: `hirn.unbeaufsichtigt` → keine Rückfrage, Ablehnung mit Hinweis; Ruhe gilt auch dort |
| mittel | Formularantwort beantwortete eine offene Ja/Nein-Rückfrage als „nein“ | behoben: Formular wartet, bis die Rückfrage entschieden ist |
| mittel | Teilen-Ziel: fremde Seite konnte Dateien in den Eingang schieben (CSRF über Service Worker) | behoben: Upload nur nach Bestätigung |
| mittel | Aussprache: „0711-123456“ → „… bis …“, „2026-0042“ als Bereich | behoben: Telefonregel, Bereich nur wenn rechts > links ohne führende Null |
| niedrig-mittel | Harte Löschsperre per sudo/env/command/xargs/`/bin/rm`/`find -delete` umgehbar | behoben, gemessen |
| niedrig | `nur_ungelesen` (Graph InefficientFilter), Kalenderfenster in UTC, OneDrive-Suche unkodiert | behoben (Graph nicht live geprüft — Microsoft-Token war abgelaufen) |
| niedrig | Gmail-Vorschau ohne Liste → stilles Neusuchen | behoben: Hinweis auf der Karte, Zeitgrenze 20 s |
| niedrig | `-€5` ohne Minus | behoben |
| niedrig | Pocket „may skip words“ bei langen Sätzen ohne Komma | behoben: Teilen ab 22 Wörtern |
| niedrig | Gedächtnis: Löschen aus der App gegen gleichzeitiges Merken, nicht-atomares Schreiben | behoben: RLock + Nebendatei/replace |
| niedrig | Löschhinweis aus der App ging bei laufendem Zug verloren | behoben: nur der tatsächlich gesendete Anstupser wird entfernt |
| niedrig | Denkkarte konnte auf „Denkt nach …“ zurückfallen | behoben: ganzer Rumpf unter dem Schloss |
| niedrig | Unterbrochene geplante Aufgabe verschwand still | behoben: Meldung im Verlauf |
| niedrig | soffice-Zeitablauf ließ soffice.bin als Waise | behoben: Prozessgruppe + killpg |
| niedrig | Titel/Übersetzung mit `max_turns=1` ohne Werkzeugsperre | behoben: `tools=[]` |
| niedrig | Caddy-Zugriffslog für alle lesbar (enthält geheime /blatt/-Adressen) | behoben 19.11. per `/srv/storage/scripts/caddy-log-schuetzen.sh` (Sascha, sudo): `mode 0640` im Caddyfile, Ordner 0750, ACL nur für server3070 (Wächter-Sammler); CrowdSec läuft als root |
| niedrig | Fehlversuche am Schlüssel nicht geloggt (Hausstandard) | behoben: gedrosselt mit IP |

## Offen

- Office→PDF hält das Blatt bis zu 2 min auf (Begleitfelder sollten nachgereicht werden).
- Arbeiter-Bash: die Pfadprüfung ist eine Heuristik (z. B. base64-kodierte Pfade);
  echte Abhilfe wäre ein eigener Container ohne Daten-Mounts.
- Dev-PC-Tastaturweg (zwei Hirnzüge gleichzeitig) — läuft auf dem Server nicht.
