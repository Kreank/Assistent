# 041 — tabelle_schreiben schreibt immer nur eine Zeile, meldet aber den ganzen Bereich als gesetzt

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | falsche-annahme |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/google.py:1150` |
| **Status** | behoben |

## Was ist falsch

Der Rumpf ist auf eine Zeile verdrahtet ([werte]), waehrend die Werkzeugbeschreibung 'A1:C3' als Beispielbereich anbietet; ausserdem fehlt die Leerpruefung, die tabelle_anhaengen an derselben Stelle hat. Die Darstellung als stiller Datenverlust ist jedoch zu scharf: Mehrzeilige Werte lassen sich ueber das Schema gar nicht uebergeben, und ein Missverhaeltnis zwischen Wertezahl und Bereich lehnt die Sheets-API mit einem Fehler ab, statt still zu kuerzen.

## Ablauf

Der wirklich stille Fall ist eng: Der Nutzer sagt "Setz A1 bis C3 auf diese Werte" und das Modell uebergibt genau drei Werte. Dann wird Zeile 1 geschrieben, die Zeilen 2 und 3 bleiben stehen, und die Antwort lautet 'A1:C3 in Tankbuch ist gesetzt'. Uebergibt das Modell dagegen neun Werte, passt die Zeile nicht in den Bereich und die Sheets-API antwortet mit einem 400er -- es scheitert also laut. Bei leerem werte-Feld geht {"values": [[]]} hinaus und die Antwort meldet trotzdem Erfolg.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Zeile 1144-1155 wie zitiert; die fehlende Leerpruefung ist echt, tabelle_anhaengen hat sie in Zeile 1102-1106. Entkraeftet ist die Schwere: Das Eingabeschema in Zeile 1132-1133 definiert werte als '{"type": "array", "items": {"type": "string"}}', also flach -- eine mehrzeilige Absicht kann das Modell gar nicht ausdruecken, der Code verwirft nichts. Zusaetzlich steht tabelle_schreiben laut config.py:620 auf 'fragen', und rueckfrage.py:337-340 liest Bereich UND Werte vor ('den Bereich A1:C3 ueberschreiben mit a, b, c?') -- der Nutzer hoert die Zahl der Werte vor der Ausfuehrung. Bleibt ein Beschreibungs- und ein Robustheitsmangel, kein Datenverlust im Normalbetrieb.

## Vorgeschlagene Behebung

Zwei kleine Aenderungen: (1) In Zeile 1130-1131 das Beispiel 'A1:C3' aus der Bereichsbeschreibung streichen und durch einen einzeiligen Bereich ersetzen ('z. B. B4 oder A1:C1 -- genau eine Zeile'). (2) Vor Zeile 1145 dieselbe Leerpruefung wie in tabelle_anhaengen einsetzen: 'if not werte: return {... "Ohne Werte kann ich nichts eintragen.", "is_error": True}'.

## Behebung

Beide vorgeschlagenen Punkte umgesetzt: Die Bereichsbeschreibung nennt
kein 'A1:C3' mehr, sondern "'B4' oder 'A1:C1' — genau eine Zeile", und
vor dem Schreiben steht dieselbe Leerpruefung wie in tabelle_anhaengen.
Der einzeilige Rumpf bleibt, weil das Eingabeschema mehrzeilige Werte
gar nicht ausdruecken kann. Belegt mit Attrappe: leeres werte-Feld
liefert is_error und es geht kein update hinaus; der Normalfall schreibt
unveraendert `{"values": [["a","b","c"]]}`.
