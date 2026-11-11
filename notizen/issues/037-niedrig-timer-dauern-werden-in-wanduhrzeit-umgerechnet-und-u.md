# 037 — Timer-Dauern werden in Wanduhrzeit umgerechnet und ueberleben die Zeitumstellung nicht

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | zeitfenster |
| **Bereich** | auftraege |
| **Fundstelle** | `sarvis/werkzeuge/zeit.py:55` |
| **Status** | behoben |

## Was ist falsch

stellen() (Zeile 54-55) rechnet eine Dauer sofort in einen naiven lokalen Zeitpunkt um, und _warten() (Zeile 78-86) vergleicht diesen Zeitpunkt sekundenweise gegen datetime.now(). Solange die Wanduhr gleichmaessig laeuft, stimmt das. An den beiden Umstellungsnaechten springt sie, und aus 'in einer Stunde' wird eine halbe oder eine doppelte. Fuer die Uhrzeit-Variante (stellen_bis ueber timer_stellen, Zeile 251-269) ist der Wanduhr-Vergleich richtig, fuer Dauern ist er es nicht.

## Ablauf

Nacht auf den letzten Sonntag im Maerz, 01:30 Uhr: 'stell einen Timer auf eine Stunde'. faellig = 02:30 naiv. Um 02:00 springt die Uhr auf 03:00. Der naechste Schleifendurchlauf sieht now=03:00 > 02:30 und meldet 'Dein Timer ist abgelaufen' -- nach 30 echten Minuten. Im Oktober umgekehrt. Der Nutzer bekommt keinen Hinweis darauf, dass das Fenster verschoben wurde. Reichweite: 'sekunden' ist im Schema auf hoechstens 86400 begrenzt (Zeile 226-232), betroffen ist also nur ein Timer, der in einer der beiden Umstellungsnaechte ueber den Sprung hinweg laeuft.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Sachlich richtig -- naive lokale Zeitpunkte plus Vergleich gegen datetime.now() verhalten sich an Umstellungen genau so. Die Einstufung 'mittel' ist aber zu hoch: Der Fall tritt zweimal im Jahr auf, nur zwischen 02:00 und 03:00 nachts, und nur fuer Dauer-Timer, die genau diesen Sprung ueberspannen -- also hoechstens 24 Stunden im Jahr Ausloesefenster fuer ein Werkzeug, das ueberwiegend fuer Nudeln und Wecker benutzt wird. Deshalb Herabstufung auf 'niedrig'.

## Vorgeschlagene Behebung

Dauer-Timer an einen absoluten Zeitpunkt haengen statt an die Wanduhr: in stellen() (Zeile 54-55) 'datetime.now().astimezone() + timedelta(...)' verwenden und in _warten() (Zeile 82) gegen 'datetime.now().astimezone()' vergleichen. Das behaelt das Verhalten bei schlafendem PC (Vergleich gegen echte Zeit, nicht gegen Prozesslaufzeit) und macht den Sprung wirkungslos. Wichtig: isoformat schreibt dann einen Offset mit, und wiederherstellen() (Zeile 168-172) muss vor dem Vergleich mit 'jetzt' beide Seiten gleich behandeln -- sonst wirft der Vergleich naiv gegen aware einen TypeError.

## Behebung

`stellen()` haengt eine Dauer jetzt an einen absoluten Zeitpunkt
(`datetime.now().astimezone() + timedelta(...)`), der Zeitversatz wird also
festgehalten und der Sprung wirkungslos. Bewusst KEINE monotone Uhr: die
ueberlebt den Neustart nicht, den ein persistierter Timer ueberleben soll.
Uhrzeit-Timer bleiben ohne Zeitversatz, weil "um sechs" die Wanduhr meint.
Weil damit beide Sorten in timer.json stehen koennen, waehlt die neue
Hilfsfunktion `_jetzt_wie()` die passende Vergleichszeit (`_warten`, `alle`,
`wiederherstellen`); die genannte Uhrzeit wird ueber `faellig.astimezone()`
angezeigt. Belegt mit `scratchpad/pruef_zeit.py`, das zeit.py eine
gefaelschte Uhr und eine Europe/Berlin-Regel unterschiebt: Am 29.03. und am
25.10.2026 laeuft ein Ein-Stunden-Timer echte 60 Minuten (alte Rechnung: 30
bzw. 120), ein Wecker auf 06:00 klingelt weiterhin um 06:00 Wanduhrzeit, und
naiv und mit Zeitversatz gespeicherte Timer stehen ohne TypeError nebeneinander.
