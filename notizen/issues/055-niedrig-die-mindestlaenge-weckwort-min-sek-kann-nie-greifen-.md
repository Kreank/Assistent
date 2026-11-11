# 055 — Die Mindestlaenge WECKWORT_MIN_SEK kann nie greifen -- der Nachlauf ist laenger als die Schwelle

Status: gegenstandslos (bewusst nicht geändert: ein verschlucktes „Ja“ wiegt schwerer als ein durchgelassenes Husten; Begründung steht bei WECKWORT_MIN_SEK in config.py)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | falsche-annahme |
| **Bereich** | sprachweg |
| **Fundstelle** | `sarvis/weckwort.py:387` |
| **Status** | verworfen |

## Was ist falsch

Nachgerechnet und richtig: dauer summiert den GESAMTEN Puffer (weckwort.py:381-382), und in den Puffer wandern in Zeile 331 auch alle Stilleblöcke des Nachlaufs, bevor _stille hochgezaehlt wird (Zeile 332). Ueber den Stille-Weg wird _pruefen() erst erreicht, wenn _stille die Grenze erreicht -- mindestens WECKWORT_STILLE_SEK = 0,55 s, also 19 Bloecke a 30 ms = 0,57 s, plus mindestens ein Sprachblock. dauer ist damit immer >= 0,60 s, WECKWORT_MIN_SEK = 0,5 wird nie unterschritten. Der zweite Weg (Notbremse, Zeile 323-324) liefert 90 bzw. 180 s. Es gibt keinen dritten Aufruf von _pruefen(). Der Kommentar in config.py:88 ('kuerzer ist ein Huesteln') beschreibt einen Filter, den es tatsaechlich nicht gibt. Die Folge bleibt gering: das Geraeusch geht durch Whisper, das Ergebnis faellt danach fast immer durch _halluziniert/_dreht_sich_im_kreis (Zeile 424) oder die Zwei-Wort-Mindestlaenge (Zeile 465). Es kostet GPU-Zeit, nicht Funktion.

## Ablauf

Ein kurzes Huesteln ueberschreitet VAD- und Pegelschwelle fuer einen Block. Der Nachlauf haengt 0,57 s Stille an, die Grenze faellt, _pruefen() rechnet dauer ~0,60 s, die Pruefung in Zeile 387 laesst es durch, und Whisper laeuft ueber ein reines Geraeusch.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Rechnerisch zwingend: BLOCK/RATE = 0,03 s, die Stille-Grenze ist minimal 0,55 s, und jeder Stilleblock landet vor dem Hochzaehlen im Puffer (Zeile 331-333). _stille wird bei jedem Sprachblock auf 0 zurueckgesetzt (Zeile 320), die frueheren Stilleblöcke bleiben aber im Puffer -- dauer waechst also nur. Ein Pfad mit kleinerem Puffer existiert nicht.

## Vorgeschlagene Behebung

Die Nachlauf-Stille aus der Rechnung nehmen. In weckwort.py:380-388 vor dem _verwerfen() den Stillestand sichern und abziehen: 'stille = self._stille' direkt nach 'stueck = self._puffer', dann 'dauer = sum(len(b) for b in stueck) / RATE - stille'. (self._verwerfen() in Zeile 386 setzt _stille auf 0, deshalb muss der Wert vorher gesichert werden.) Danach misst WECKWORT_MIN_SEK das, was der Kommentar in config.py:88 verspricht: die tatsaechlich gesprochene Zeit.

## Behebung

Nachgerechnet und bestaetigt, aber bewusst NICHT geaendert. Gemessen mit `scratchpad/pruef_weckwort.py`: ein einzelner Sprachblock plus Nachlauf ergibt 20 Bloecke = 0,600 s Puffer bei 0,570 s Stille -- die Schwelle von 0,5 s wird also tatsaechlich nie unterschritten. Der vorgeschlagene Abzug der Nachlauf-Stille wuerde die Konstante zwar scharf stellen, aber bei 0,5 s auch jede Ein-Wort-Antwort verschlucken: "Ja." misst rund 0,36 s, "YouTube" rund 0,45 s -- genau die Faelle, fuer die `_deuten()` (Kommentar bei der Zwei-Wort-Pruefung) ausdruecklich gebaut wurde. Scharf stellen laesst sich das nur zusammen mit einem kleineren `WECKWORT_MIN_SEK` (~0,25) in `config.py`, und die Datei gehoert nicht zu diesem Auftrag. Der Schaden ist ohnehin nur GPU-Zeit fuer ein Huesteln, das die nachgelagerten Filter verwerfen -- deshalb Meldung statt Codeaenderung.
