# 039 — termine_ansehen faellt bei unverstandenem Startdatum still auf heute zurueck

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | stiller-abbruch |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/google.py:364` |
| **Status** | behoben |

## Was ist falsch

Scheitert das Zerlegen von 'ab', wird der Fehler geschluckt und der Zeitraum beginnt bei jetzt, ohne Hinweis auf den verworfenen Wunsch. Der gemeldete Schaden tritt aber nur in einem Teilfall wirklich ein, siehe Begruendung -- deshalb herabgestuft.

## Ablauf

Nutzer: "Was steht am 3. Oktober an?" Claude uebergibt ab in einem anderen Format als TT.MM.JJJJ (z. B. ISO) -> ValueError -> pass -> von bleibt jetzt, bis = heute + 1 Tag. Stehen fuer heute Termine an, enthaelt die Antwort deren Datum ueber _wann() -- Modell und Nutzer hoeren dann '27.08., 14:00: Zahnarzt' auf eine Frage nach dem 3. Oktober und koennen es bemerken. Wirklich stumm falsch ist nur der leere Fall: 'In dem Zeitraum steht nichts an.' klingt wie eine Auskunft ueber den 3. Oktober und ist eine ueber heute.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Zeile 360-365 exakt wie gemeldet, das Schlucken ist real. Entkraeftet ist die Schwere: Die Antwort besteht in Zeile 381-385 aus '_wann(e.get("start"))'-Zeilen, traegt also im Regelfall das tatsaechliche Datum sichtbar mit. Zusaetzlich ist das Format in der Parameterbeschreibung (Zeile 349) ausdruecklich als 'TT.MM.JJJJ' benannt, und termine_ansehen ist lesend -- es entsteht kein bleibender Schaden, nur eine mit falschem Bezug vorgelesene Auskunft im leeren Fall.

## Vorgeschlagene Behebung

Zeile 364-365: statt 'pass' den Zeitraum melden, den Sarvis tatsaechlich abgefragt hat. Am billigsten ist es, den abgefragten Zeitraum in beide Antworten aufzunehmen: f"Vom {von:%d.%m.} bis {bis:%d.%m.} steht nichts an." bzw. als Kopfzeile ueber den Terminzeilen. Damit ist der stille Rueckfall in jedem Fall hoerbar, ohne einen zusaetzlichen Fehlerpfad zu bauen.

## Behebung

Das Startdatum wird jetzt mit `_faellig_deuten` gedeutet, das neben
TT.MM.JJJJ auch ISO versteht — damit faellt der haeufigste Ausloeser des
stillen Rueckfalls weg. Zusaetzlich nennt jede Antwort den Zeitraum, der
tatsaechlich abgefragt wurde ("Termine 27.08. bis 26.09.:" bzw. "Vom
03.10. bis 04.10. steht nichts an."), sodass ein doch einmal verworfenes
'ab' hoerbar ist; ein zusaetzlicher Fehlerpfad ist nicht entstanden.
Belegt mit einem Attrappen-Skript ohne Netzzugriff, das termine_ansehen
gegen einen falschen Kalenderdienst mit ISO-Datum, TT.MM.JJJJ und
unverstaendlichem 'ab' aufruft und timeMin sowie Antworttext prueft.
