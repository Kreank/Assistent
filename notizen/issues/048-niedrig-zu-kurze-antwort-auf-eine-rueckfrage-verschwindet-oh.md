# 048 — Zu kurze Antwort auf eine Rueckfrage verschwindet ohne Konsolenzeile

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | stiller-abbruch |
| **Bereich** | hauptschleife |
| **Fundstelle** | `sarvis/main.py:459` |
| **Status** | behoben |

## Was ist falsch

_antwort_hoeren (main.py:455-461) verwirft eine Aufnahme unter MIN_AUFNAHME_SEK (config.py:198, 0,4 s) mit einem nackten return -- ohne Konsolenzeile. Der gleichwertige Pfad _durchgang gibt in derselben Lage "(nur 0.12s -- verworfen)" aus (main.py:745-748). Die Meldung des urspruenglichen Fundes war ueberzeichnet: es fehlt die Konsolenzeile, nicht "jede Meldung".

## Ablauf

Sarvis fragt, der Nutzer tippt die Taste nur an. Die Aufnahme liegt unter 0,4 s und wird verworfen, die Future bleibt offen. In der Konsole steht dazu nichts. Die Anzeige geht auf FRAGT zurueck, signalisiert also weiterhin korrekt "wartet auf dich", und nach Ablauf von RUECKFRAGE_SEKUNDEN (config.py:638, 25 s) sagt Sarvis hoerbar rueckfrage.ABGELAUFEN ("Ich habe keine Antwort bekommen und lasse es lieber.", main.py:361-364) und lehnt ab. Der Nutzer bleibt also nicht dauerhaft im Unklaren -- aber wer die Konsole beobachtet, sieht 25 Sekunden lang keinen Hinweis darauf, warum seine Antwort nicht ankam, und kann in dieser Zeit nicht mit einem laufenden Fenster gegensteuern.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Nachgesehen und bestaetigt: In main.py:455-461 steht zwischen dem Schwellenvergleich und dem return keine Ausgabe, waehrend main.py:745-748 im Parallelfall druckt. Ein Auffangen an anderer Stelle gibt es nicht -- self.antwort bleibt unberuehrt, der Timeout in main.py:359 laeuft weiter. Herabgestuft bzw. praezisiert bleibt es trotzdem bei niedrig: der Zustand ist sicher (im Zweifel "nein", main.py:363-364), die Anzeige bleibt korrekt auf FRAGT, es gibt eine gesprochene Schlussmeldung, und die Aufnahme muss unter 0,4 s liegen -- wer die Taste haelt und "ja" sagt, kommt darueber. Es fehlt nur die Diagnosezeile.

## Vorgeschlagene Behebung

In main.py zwischen Zeile 458 und 459 die Zeile aus dem Parallelpfad ergaenzen: vor 'self.anzeige.zustand(FRAGT)' ein 'print(f"  (Antwort nur {dauer:.2f}s -- verworfen, ich warte weiter)")' einfuegen. Bewusst nichts weiter: die Future darf NICHT aufgeloest werden, das Weiterwarten ist hier richtig.

## Behebung

In `_antwort_hoeren` (main.py) steht vor `self.anzeige.zustand(FRAGT)` jetzt `print(f"  (Antwort nur {dauer:.2f}s -- verworfen, ich warte weiter)")`, wie im Parallelpfad `_durchgang`. Die Future bleibt unangetastet — das Weiterwarten ist hier richtig, geändert wurde ausschließlich die Diagnosezeile. Belegt durch Lesen des Kontrollflusses und `py_compile`; ausgeführt wurde diese Stelle nicht, da sie an Mikrofon und Aufnehmer hängt.
