# 059 — Der Not-Aus lässt den Satz durch, der gerade synthetisiert wird

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | race |
| **Bereich** | hauptschleife |
| **Fundstelle** | `sarvis/main.py` (`vorlesen` in `_antworten`) |
| **Status** | behoben |
| **Herkunft** | Nebenbefund beim Beheben von 047, im Kontrollfluss nachgelesen |

## Was ist falsch

`vorlesen()` läuft in einem `asyncio.to_thread` und lässt sich nicht abbrechen.
Der Faden prüft `self.abgebrochen` zweimal: einmal vor der Synthese und einmal
danach, bevor er den Satz an den Lautsprecher gibt. Genau zwischen diesen
beiden Blicken setzt `_alles_stoppen()` die Flagge wieder auf `False`
(main.py:582), und die Hauptschleife tut dasselbe an zwei weiteren Stellen
(main.py:892 und 925).

Kehrt der Faden aus `mund.sprechen()` zurück, nachdem die Flagge zurückgesetzt
wurde, ist die zweite Prüfung wirkungslos.

## Ablauf

Der Nutzer drückt die Not-Aus-Taste, während Sarvis spricht:

1. `_stopp_taste()` bricht den Ton ab und legt "stopp" in die Schlange.
2. Die Schleife ruft `_unterbrechen()` — `abgebrochen = True`, die Aufgabe
   wird gecancelt. Der Vorlesefaden läuft trotzdem weiter, er hängt noch in
   der Synthese.
3. `_alles_stoppen()` setzt `abgebrochen = False` (main.py:582) und sagt
   "Gestoppt."
4. Der Vorlesefaden kommt aus der Synthese zurück, prüft `not self.abgebrochen`
   → `True`, und schiebt seinen Satz **nach** dem "Gestoppt." hinterher.

Der Not-Aus ist die einzige Möglichkeit, Sarvis mitten im Satz zu stoppen.
Dass danach noch ein Satz kommt, ist genau das, was er verhindern soll.

## Warum das bestätigt wurde

Im Kontrollfluss nachgelesen, nicht ausgeführt: `self.abgebrochen = True` steht
in `_unterbrechen` (main.py:508), die drei Rücksetzungen in `_alles_stoppen`
(582) und in der Hauptschleife (892, 925). Die beiden Prüfungen im
Vorlesefaden greifen auf dieselbe Flagge zu. Der Kommentar, den ein Fix-Agent
beim Beheben von 047 hinterlassen hat, beschreibt denselben Sachverhalt aus
eigener Messung: "Dieser Faden laeuft nach dem Abbruch weiter, und die Schleife
setzt die Flagge inzwischen schon wieder auf False."

## Behebung

Zusätzlich zur Flagge gibt es jetzt einen Zähler `self.durchgang`, den
`_unterbrechen()` bei jedem Abbruch erhöht. `_antworten` merkt sich zu Beginn
seine `marke`, und `vorlesen()` prüft an beiden Stellen zusätzlich
`self.durchgang == marke`. Eine hochzählende Zahl kann nicht zurückfallen wie
eine Flagge, die jemand anders wieder löscht.

Die Flagge bleibt daneben bestehen — sie deckt das Reinreden ab, wo kein
vollständiger Abbruch stattfindet.
