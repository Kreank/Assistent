# 038 — Beim Wiederherstellen genau der ungenaue Umweg, den stellen_bis verwirft

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | reihenfolge |
| **Bereich** | auftraege |
| **Fundstelle** | `sarvis/werkzeuge/zeit.py:185` |
| **Status** | behoben |

## Was ist falsch

stellen_bis() existiert laut seinem Docstring (Zeile 57-62) gerade deshalb, weil der Umweg ueber eine Dauer Nachkommastellen abschneidet und den Timer rund eine Sekunde daneben legt. wiederherstellen() hat den exakten Zeitpunkt in 'faellig' bereits als datetime vorliegen (Zeile 169), wirft ihn aber weg und geht ueber int(...total_seconds()) -- also genau den beschriebenen Umweg.

## Ablauf

Korrigiert: Ein Wecker auf 06:00:00 ueberlebt einen Neustart. faellig wird gegen 'jetzt' (Zeile 163) in eine auf ganze Sekunden abgeschnittene Dauer verwandelt, aus der stellen() mit einem neuen datetime.now() wieder einen Zeitpunkt baut. Die Abschneidung zieht bis zu einer Sekunde nach vorn, die zwischen Zeile 163 und Zeile 185 verstrichene Zeit schiebt um denselben Betrag nach hinten -- der neue Zeitpunkt liegt also um bis zu eine Sekunde neben 06:00:00, in welche Richtung, ist nicht vorhersagbar. Die Behauptung, der Wecker rutsche mit jedem Neustart weiter nach vorn, stimmt so nicht: Es addiert sich nichts auf, jeder Neustart setzt neu gegen den gespeicherten Zeitpunkt an. Richtig waere trotzdem self.stellen_bis(faellig, was).

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Der Code sagt es eindeutig (Zeile 185), und stellen_bis(faellig, was) ist an dieser Stelle ohne jede Nebenwirkung einsetzbar, weil stellen() ohnehin nur an stellen_bis delegiert (Zeile 54-55). Der Fund selbst ist damit richtig, seine Wirkungsbeschreibung war zu dramatisch -- die Abweichung ist unter einer Sekunde und kumuliert nicht. 'niedrig' bleibt.

## Vorgeschlagene Behebung

Zeile 185 ersetzen durch 'self.stellen_bis(faellig, was)'. Die lokale Variable 'jetzt' wird an dieser Stelle dann nicht mehr gebraucht (sie bleibt fuer den Vergleich in Zeile 170 noetig).

## Behebung

Zeile ersetzt durch `self.stellen_bis(faellig, was)`; `jetzt` wird jetzt je
Eintrag ueber `_jetzt_wie(faellig)` bestimmt und weiter fuer den Vergleich
gebraucht. Belegt mit `scratchpad/pruef_zeit.py`: Ein Wecker auf 06:00:00 kommt
nach Sichern und Wiederherstellen (mit 30,5 Sekunden Abstand) auf die
Mikrosekunde genau wieder auf 06:00:00 heraus, ein Dauer-Timer behaelt seinen
Zeitversatz.
