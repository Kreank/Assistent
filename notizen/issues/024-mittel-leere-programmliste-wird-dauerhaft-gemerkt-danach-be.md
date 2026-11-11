# 024 — Leere Programmliste wird dauerhaft gemerkt -- danach behauptet Sarvis fuer immer, es gebe das Programm nicht

Status: gegenstandslos (Get-StartApps/PowerShell gibt es auf dem Server nicht; Fix b217416 steht im Code)

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | zustand-ueberschrieben |
| **Bereich** | werkzeuge |
| **Fundstelle** | `sarvis/werkzeuge/programme.py:55` |
| **Status** | behoben |

## Was ist falsch

Scheitert der Abruf der Startmenue-Liste, wird die leere Liste in dieselbe Variable geschrieben, die als Zwischenspeicher dient. Da der Zwischenspeicher nur auf 'is not None' prueft (Zeile 29), gilt die leere Liste ab da als gueltiges Ergebnis. Ein zweiter Versuch findet nie statt: _holen(neu=True) wird im Modul nirgends aufgerufen.

## Ablauf

Scheitert der erste PowerShell-Aufruf (Timeout nach 30 s, Virenscanner, Anmeldung noch nicht fertig), wird einmal '(Programmliste liess sich nicht laden: ...)' auf die Konsole geschrieben -- die der Nutzer beim Sprechen nicht sieht -- und _liste = [] gesetzt. Jeder weitere Zuruf im selben Sarvis-Lauf bekommt die leere Liste und antwortet: "Ein Programm namens 'Spotify' finde ich nicht im Startmenue" -- eine Behauptung ueber eine Liste, die nie gelesen wurde. programm_suchen ohne Suchwort sagt '0 Programme insgesamt, darunter:'. Erst ein Neustart heilt das.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Widerlegungsversuch gescheitert, aber Einstufung korrigiert. Bestaetigt: Zeile 29 prueft '_liste is not None', Zeile 55 setzt _liste = [] im except-Zweig; grep nach '_holen(' in der Datei findet genau drei Stellen -- die Definition (25), Zeile 76 und Zeile 220, beide ohne Argument. Der Parameter neu=True ist toter Code, kein Aufrufer heilt den Zustand. Herabgestuft von 'hoch' auf 'mittel': Der Pfad setzt voraus, dass der allererste PowerShell-Aufruf scheitert, und Get-StartApps ist auf einem laufenden Windows ein Standardaufruf mit 30 s Zeitfenster (Zeile 42). Das trifft den Nutzer nicht im Normalbetrieb -- wenn es aber trifft, dann fuer den ganzen Lauf und mit einer falschen Aussage.

## Vorgeschlagene Behebung

Im except-Zweig (Zeile 51-55) nicht in den Zwischenspeicher schreiben: _liste auf None lassen und stattdessen eine lokale leere Liste zurueckgeben (return [] direkt aus dem except heraus, statt ueber Zeile 56). Dann versucht es der naechste Aufruf erneut. Zusaetzlich in programm_starten (Zeile 173-176) und programm_suchen (Zeile 220-224) den Fall 'Liste leer' vom Fall 'nichts gefunden' trennen, damit Sarvis sagt 'Ich komme gerade nicht an die Programmliste' statt zu behaupten, es gebe das Programm nicht.

## Behebung

Der except-Zweig in `_holen()` schreibt nicht mehr `_liste = []`, sondern gibt eine lokale leere Liste zurueck; ausserdem trennen `programm_starten` und `programm_suchen` jetzt "Liste nicht erreichbar" von "nichts gefunden". Ein Fehlschlag wird damit nicht mehr dauerhaft gemerkt.
