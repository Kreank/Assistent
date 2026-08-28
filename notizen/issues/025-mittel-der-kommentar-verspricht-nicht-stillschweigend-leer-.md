# 025 — Der Kommentar verspricht 'nicht stillschweigend leer' -- genau das passiert bei jedem PowerShell-Fehler ohne Ausnahme

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | falsche-annahme |
| **Bereich** | werkzeuge |
| **Fundstelle** | `sarvis/werkzeuge/programme.py:45` |
| **Status** | behoben |

## Was ist falsch

Der except-Zweig faengt nur Python-Ausnahmen ab. ergebnis.returncode wird nie geprueft, ergebnis.stderr nie angesehen, und leerer stdout wird durch 'text or "[]"' in eine gueltige leere Liste umgedeutet. Der Fall, den der Kommentar in Zeile 52-53 als behoben beschreibt, laeuft weiterhin voellig stumm durch -- ohne Ausnahme gibt es auch keine print-Meldung.

## Ablauf

PowerShell startet, scheitert aber am Befehl selbst (Ausfuehrungsrichtlinie, Get-StartApps nicht verfuegbar, Fehler nach stderr). returncode ist ungleich 0 oder stdout leer. json.loads("" or "[]") liefert [], keine Ausnahme, kein print. _liste wird auf [] gesetzt und nach Fund 2 dauerhaft behalten. Der Nutzer hoert nur 'finde ich nicht im Startmenue'.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Widerlegungsversuch gescheitert. subprocess.run in Zeile 32-43 laeuft mit capture_output=True, aber ergebnis.returncode und ergebnis.stderr kommen in der ganzen Datei nirgends vor (grep). Zeile 44 dekodiert nur stdout, Zeile 45 macht aus leerem Text mit 'text or "[]"' eine gueltige leere Liste -- json.loads('[]') wirft nichts. Damit ist der except-Zweig samt print unerreichbar, obwohl der Kommentar in Zeile 52-53 genau diesen Fall als abgedeckt beschreibt. Wurzel derselbe Defekt wie Fund 2, aber eine eigene Luecke: Fund 2 betrifft das Merken, dieser hier das Erkennen. Gleiche Einstufung wie Fund 2 -- setzt einen kaputten PowerShell-Aufruf voraus.

## Vorgeschlagene Behebung

Nach Zeile 43 pruefen und einen Fehler ausloesen, damit der bestehende Zweig greift: if ergebnis.returncode != 0 or not (ergebnis.stdout or b'').strip(): raise RuntimeError((ergebnis.stderr or b'').decode('utf-8', errors='replace')[:200] or f'Rueckgabewert {ergebnis.returncode}, keine Ausgabe'). Danach 'text or "[]"' in Zeile 45 durch schlichtes json.loads(text) ersetzen, damit leerer Text nicht mehr zu einer gueltigen Liste umgedeutet wird. Zusammen mit dem Fix aus Fund 2 wird der Fehlschlag dann auch nicht mehr gecacht.

## Behebung

Nach dem PowerShell-Aufruf werden `returncode` und leerer `stdout` geprueft und loesen einen Fehler mit dem stderr-Anfang aus. Der print-Zweig, den der Kommentar versprach, war vorher unerreichbar.

Nebenwirkung: Ein Rechner, auf dem `Get-StartApps` wirklich nichts liefert, fragt bei jedem Zuruf erneut PowerShell (rund 0,8 s), statt einmal eine leere Liste zu merken. Die Alternative waere die falsche Behauptung aus Fund 024.
