# 013 — Zwei gleichnamige Dateien: Drive waehlt still die zuletzt geaenderte -- auch beim Teilen

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | falsche-annahme |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/google.py:242` |
| **Status** | behoben |

## Was ist falsch

Sobald mindestens ein Treffer den Namen exakt traegt, wird genau[0] genommen, ohne zu pruefen, ob genau mehrere Eintraege hat. Drive erlaubt gleichnamige Dateien. Dieselbe Luecke in _tabelle_finden (Zeile 276-283). Zu praezisieren ist der Vorwurf: Dass ein exakter Treffer gegenueber unscharfen gewinnt, ist richtig und gewollt -- die Luecke ist ausschliesslich der Fall MEHRERER exakt gleichnamiger Dateien.

## Ablauf

In Drive liegen zwei Dateien namens 'Steuer 2025' (etwa eine im Archiv, eine aktuell -- entsteht z. B. durch zweimaliges Hochladen derselben Datei). Nutzer: "Gib Steuer 2025 frei." genau enthaelt beide, es wird ohne Nachfrage die zuletzt geaenderte genommen (orderBy='modifiedTime desc', Zeile 235). Die Rueckfrage in rueckfrage.py:334-336 nennt nur den gesuchten Namen, nicht die aufgeloeste Datei -- der Nutzer kann den Unterschied nicht hoeren. Danach ist moeglicherweise die falsche Datei fuer jeden mit dem Link lesbar.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Zeile 242-243: 'genau = [...]' / 'if genau: return genau[0], None' -- keine Laengenpruefung; die Mehrdeutigkeitspruefung in Zeile 244 ('if len(treffer) > 1') wird bei einem exakten Treffer nie erreicht. Zeile 276-283 gleiches Muster ('if not genau and len(treffer) > 1'). drive_teilen ruft _datei_finden in Zeile 1019 auf, greift also wirklich. Ein Auffangnetz existiert nicht: config.py:611 setzt drive_teilen auf 'fragen', aber die Frage wird aus dem Rohargument gebaut. Herabgestuft auf mittel, weil zwei buchstabengleiche Namen in Drive vorkommen, aber nicht der Normalfall sind.

## Vorgeschlagene Behebung

google.py:243 zu 'if len(genau) == 1: return genau[0], None' und bei 'len(genau) > 1' denselben Mehrdeutigkeitsfehler zurueckgeben wie Zeile 244-249, ergaenzt um das Aenderungsdatum aus _geaendert(), damit die beiden Gleichnamigen unterscheidbar sind (dazu 'modifiedTime' ins fields-Feld in Zeile 236 aufnehmen). In _tabelle_finden Zeile 278 analog: 'if len(genau) > 1 or (not genau and len(treffer) > 1)'.

## Behebung

Bei mehreren exakt gleichnamigen Treffern wird nicht mehr still die zuletzt geaenderte genommen, sondern der Mehrdeutigkeitsfehler zurueckgegeben, ergaenzt um das Aenderungsdatum. Geprueft mit einer Drive-Attrappe ohne Netzzugriff.

Nebenwirkung: Auch harmlose Lesevorgaenge (`drive_lesen`, `tabelle_lesen`) fragen jetzt nach. Eine Aufspaltung nach Gefaehrlichkeit wurde bewusst nicht gebaut.
