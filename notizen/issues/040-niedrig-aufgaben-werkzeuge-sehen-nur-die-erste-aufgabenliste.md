# 040 — Aufgaben-Werkzeuge sehen nur die erste Aufgabenliste

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | filter-zu-streng |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/google.py:676` |
| **Status** | behoben |

## Was ist falsch

_erste_liste holt mit maxResults=1 nur eine Aufgabenliste; alle drei Aufgaben-Werkzeuge arbeiten ausschliesslich darin. Der Zusatz des Reviewers, mehrere Listen seien 'in Google Tasks der Normalfall', trifft nicht zu: Google legt genau eine Liste ('Meine Aufgaben') an, weitere entstehen nur, wenn der Nutzer sie selbst anlegt. Der Name _erste_liste zeigt, dass die Beschraenkung bewusst gewaehlt ist; falsch ist nur, dass sie sich in der Antwort als Tatsachenbehauptung tarnt.

## Ablauf

Der Nutzer fuehrt neben 'Meine Aufgaben' eine zweite Liste ('Einkauf'). Er fragt "Was steht noch offen?" -> aufgaben_ansehen sieht nur die erste Liste und antwortet "Keine offenen Aufgaben.", obwohl welche existieren. Ebenso meldet aufgabe_abhaken "Keine offene Aufgabe zu 'Milch'". Wer nur die Vorgabeliste fuehrt -- der Regelfall -- merkt davon nie etwas.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Zeile 674-678 wie gemeldet; die Aufrufer in Zeile 693, 741 und 771 arbeiten alle nur mit dieser einen Liste. Es gibt keine Stelle, die weitere Listen nachlaedt. Herabgestuft auf niedrig, weil die Voraussetzung -- mehr als eine selbst angelegte Liste -- eine bewusste Handlung des Nutzers ist und die drei Werkzeuge in der Vorgabelage vollstaendig korrekt arbeiten.

## Vorgeschlagene Behebung

_erste_liste durch _listen(dienst) ersetzen (maxResults weglassen, items zurueckgeben) und in aufgaben_ansehen ueber alle Listen iterieren, den Listennamen bei mehr als einer Liste vor die Zeilen setzen. In aufgabe_abhaken denselben Weg gehen und die Aufgabe in der Liste abhaken, in der sie gefunden wurde. Bei aufgabe_anlegen darf die erste Liste die Vorgabe bleiben -- dort ist die Wahl eindeutig und harmlos.

## Behebung

`_erste_liste` ist durch `_listen` ersetzt (alle Aufgabenlisten statt
maxResults=1). aufgaben_ansehen geht ueber alle Listen und stellt den
Listennamen nur voran, wenn es mehr als eine gibt; aufgabe_abhaken sucht
in allen Listen und hakt in der Liste ab, in der die Aufgabe gefunden
wurde; aufgabe_anlegen behaelt bewusst die erste Liste. Belegt mit
Attrappe: zwei Listen mit der offenen Aufgabe in der zweiten — sie wird
gefunden und in L2 aktualisiert; bei genau einer Liste ist die Ausgabe
unveraendert ohne Vorspann.
