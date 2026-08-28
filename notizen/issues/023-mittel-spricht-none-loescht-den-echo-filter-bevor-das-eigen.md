# 023 — spricht(None) loescht den Echo-Filter, bevor das eigene Echo ueberhaupt geprueft wurde

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | reihenfolge |
| **Bereich** | sprachweg |
| **Fundstelle** | `sarvis/weckwort.py:203` |
| **Status** | behoben |

## Was ist falsch

Der zeitliche Ablauf stimmt: Mit REINREDEN=True bleibt der Horcher waehrend der Rede offen (weckwort.py:200-218 setzt pausiert=False und verwirft), Sarvis' Stimme landet ueber _block() im Puffer, und ausgewertet wird dieser Puffer erst, wenn _stille die Grenze erreicht -- 0,55 s (kurz) bzw. 1,4 s (ab 2 s Puffer, weckwort.py:352-378) nach dem letzten Ton. spricht(None) laeuft aber schon direkt nach lautsprecher.warten() und leert _eigene_saetze (weckwort.py:203-206); pause(False) raeumt den Puffer NICHT ab, weil _verwerfen() nur im Zweig 'if an' steht (weckwort.py:248-251). _eigen_echo() steigt danach in Zeile 231-232 mit 'return False' aus. Der Echo-Filter ist damit am ENDE jeder Rede wirkungslos -- er greift nur noch, wenn mitten in der Rede eine Stille-Grenze faellt (z. B. wenn die Synthese des naechsten Satzes laenger dauert als der laufende). KORREKTUR der Einstufung: Die Wirkung setzt voraus, dass das Mikrofon Sarvis' Stimme mit RMS >= WECKWORT_MIN_PEGEL (0.008) UND VAD >= 0.5 aufnimmt. config.py:91-100 legt REINREDEN=True ausdruecklich als Kopfhoerer-Betrieb fest ('Mit Kopfhoerern kommt fast nichts zurueck') und schreibt fuer Boxen 'Auf Lautsprechern ausschalten' vor -- und mit REINREDEN=False geht spricht() ueber pause(True/False), wo pause(True) den Puffer leert und _schleife() waehrend der Rede gar nichts erst puffert (weckwort.py:288-289). Der Fehler trifft also nur die Konstellation 'REINREDEN an und trotzdem hoerbares Echo', nicht den vorgesehenen Normalbetrieb. Deshalb mittel statt hoch.

## Ablauf

Sarvis spricht (main._sagen_und_warten:547-558, main._antworten:645-678, main._begruessen:592-617). Nach lautsprecher.warten() ruft main horcher.spricht(None) -> _eigene_saetze = [], pause(False) ohne _verwerfen(). 0,25 bis 1,1 s spaeter faellt die Stille-Grenze, _pruefen() gibt das mitgeschnittene Echo an Whisper, _eigen_echo() hat nichts zum Vergleichen, das Nachhoerfenster ist offen (spricht() hat es in Zeile 212-215 selbst verlaengert), also greift auch die Fenster-Pruefung in Zeile 444 nicht. Bei offener Rueckfrage wird der Satz in main.py:834-837 direkt per _antwort_geben() als Antwort auf die eigene Frage eingesetzt, sonst startet er einen neuen Durchgang.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Kein Aufrufer raeumt den Puffer nach der Rede ab: die einzigen _verwerfen()-Aufrufe stehen in pause(an=True), in spricht() beim Aufwachen aus der Pause und in _pruefen() selbst. main ruft nach der Antwort nur horcher.pause(False) (main.py:705/719/736) -- ebenfalls ohne Verwerfen. Auch der AUSKLANG von 0,30 s (audio.py:18/134-136) deckt die Luecke nicht: er verbraucht nur einen Teil der 0,55 s, und bei laengeren Reden gilt ohnehin die 1,4-s-Grenze. Widerlegen liess sich der Ablauf nicht -- nur die Schwere.

## Vorgeschlagene Behebung

Den Filter nachwirken lassen, statt ihn hart zu leeren. In weckwort.py:203-206: '_eigene_saetze' nicht loeschen, sondern eine Nachwirkzeit setzen, z. B. self._eigen_bis = time.perf_counter() + config.DIKTAT_STILLE_SEK (deckt auch die 1,4-s-Grenze und den Diktat-Fall ab). In _eigen_echo() (weckwort.py:231) davor: 'if self._eigen_bis and time.perf_counter() > self._eigen_bis: self._eigene_saetze = []'. In __init__ self._eigen_bis = 0.0 anlegen, und in spricht(text) beim naechsten Satz self._eigen_bis = 0.0 zuruecksetzen. Damit bleibt der zuletzt gesprochene Satz genau so lange vergleichbar, wie sein Echo noch im Nachlauf haengen kann.

## Behebung

`spricht(None)` loescht die eigenen Saetze nicht mehr sofort, sondern setzt eine Nachwirkzeit; `_eigen_echo()` raeumt sie erst ab, wenn die Aufnahme nach deren Ablauf begann. Vorher war der Echo-Filter genau in dem Moment leer, in dem das eigene Echo aus dem Lautsprecher noch unterwegs war.

Verhaltensaenderung: Wer innerhalb von rund 3 Sekunden fast woertlich wiederholt, was Sarvis gerade gesagt hat, wird verworfen -- in der Konsole steht dann "(eigene Stimme verworfen: ...)".
