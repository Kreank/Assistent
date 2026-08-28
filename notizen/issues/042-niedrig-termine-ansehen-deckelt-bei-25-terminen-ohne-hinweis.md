# 042 — termine_ansehen deckelt bei 25 Terminen ohne Hinweis

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | stiller-abbruch |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/google.py:372` |
| **Status** | behoben |

## Was ist falsch

maxResults ist fest auf 25 gesetzt, waehrend der Zeitraum bis zu 60 Tage betragen darf. Es gibt weder eine Folgeseite noch einen Hinweis auf abgeschnittene Eintraege -- anders als bei tabelle_lesen, das die Kuerzung mit '[… N weitere Zeilen]' ausweist.

## Ablauf

Nutzer: "Was steht die naechsten vier Wochen an?" Bei gut gefuelltem Kalender liefert Google die ersten 25 Termine, alles danach fehlt. Sarvis liest die Liste vor, als waere sie vollstaendig. Die Zeitstempel zeigen immerhin, bis wann die Auskunft reicht -- der Nutzer haelt den letzten genannten Termin aber fuer den letzten des Zeitraums.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Zeile 367-373 wie zitiert, kein pageToken und kein Hinweis; Zeile 381-385 gibt die Zeilen unveraendert aus. Der Gegenbeleg stimmt: tabelle_lesen weist die Kuerzung in Zeile 1071-1073 aus, drive_lesen in Zeile 995-997. Niedrig bleibt richtig: 25 Termine reichen fuer die Vorgabe (tage=1) und fuer eine normale Woche muehelos; nur der ausdrueckliche Mehrwochen-Blick bei vollem Kalender laeuft an die Grenze, und die Antwort bleibt dabei inhaltlich korrekt, nur unvollstaendig.

## Vorgeschlagene Behebung

Nach dem Aufbau von 'zeilen' pruefen, ob genau maxResults Eintraege kamen, und dann eine Schlusszeile anhaengen: 'if len(eintraege) >= 25: zeilen.append(f"[… mehr als 25 Termine bis {bis:%d.%m.} -- weitere nicht aufgezaehlt]")'. Das ist dasselbe Muster wie in tabelle_lesen und kostet keinen zusaetzlichen API-Aufruf.

## Behebung

maxResults steht jetzt als `TERMINE_GRENZE` (25) im Modul, und wenn
Google genau so viele Eintraege liefert, haengt die Antwort die Zeile
"[… mehr als 25 Termine — weitere nicht aufgezaehlt]" an — dasselbe
Muster wie "[… N weitere Zeilen]" in tabelle_lesen, ohne zusaetzlichen
API-Aufruf. Der Deckel selbst bleibt. Belegt mit Attrappe: 25 Termine
erzeugen die Schlusszeile, 24 nicht.
