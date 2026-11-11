# 051 — abbrechen() erwischt den Satz nicht, den der Abspielfaden schon aus der Schlange gezogen hat

Status: gegenstandslos (audio.Lautsprecher läuft nur lokal, auf dem Server spricht der NetzLautsprecher; Fix b217416 steht im Code)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | race |
| **Bereich** | sprachweg |
| **Fundstelle** | `sarvis/audio.py:138` |
| **Status** | behoben |

## Was ist falsch

Das Fenster existiert: _schleife() nimmt den Posten mit get() (audio.py:157) und _abspielen() prueft _abbruch erst in der Pegelschleife (audio.py:148), also nach sd.play() (Zeile 138). Faellt abbrechen() (Zeile 176-192) genau dazwischen, laeuft sd.stop() ins Leere, der Satz wird danach vollstaendig gespielt, die Pegelschleife bricht sofort ab und leer ist gesetzt -- warten() meldet 'fertig', waehrend Sarvis noch redet. KORREKTUR der Schwere: Das Fenster reicht von get() bis zum Anlaufen des Ausgabestroms, also wenige Millisekunden pro Satz, und es steht nur direkt an einer Satzgrenze offen -- waehrend ein Satz laeuft, haengt der Faden in der Pegelschleife bzw. sd.wait() und hat den naechsten Posten noch gar nicht geholt. Zudem faengt main das Nachschieben neuer Saetze bereits ab: vorlesen() prueft self.abgebrochen vor und nach der Synthese (main.py:645-661). Es bleibt ein schmales Rennen, kein Verhalten des Normalbetriebs.

## Ablauf

Der Nutzer drueckt den Not-Aus (main._stopp_taste:572-583) oder redet rein (main._unterbrechen:486-495) in genau dem Moment, in dem der Abspielfaden den naechsten Satz gerade entnommen hat und sd.play() noch nicht angelaufen ist. Der Satz wird zu Ende gespielt, der Ring steht dabei auf null, und warten() ist bereits zurueckgekehrt.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Es gibt keine Absicherung vor sd.play(): _abspielen() beginnt mit concatenate/_huellkurve und ruft direkt play(); die erste _abbruch-Abfrage steht in Zeile 148. Auch der frueh gesetzte Merker main.abgebrochen hilft hier nicht, weil der Posten bereits in der Schlange lag. Der Fund selbst liess sich nicht widerlegen, nur seine Haeufigkeit.

## Vorgeschlagene Behebung

In audio.py am Anfang von _abspielen() (vor Zeile 134) 'if self._abbruch.is_set(): return' einfuegen und direkt nach sd.play(proben, rate) (Zeile 138) noch einmal 'if self._abbruch.is_set(): sd.stop(); return'. Damit schrumpft das Fenster auf wenige Bytecodes. Sauber schliessen laesst es sich mit einer Generationsnummer: self._runde in __init__, abbrechen() erhoeht sie, sagen() legt (proben, rate, self._runde) in die Schlange, und _schleife() ueberspringt jeden Posten, dessen Runde aelter ist als die aktuelle -- das faengt auch den Fall ab, dass ein neues sagen() das _abbruch-Event bereits wieder gecleart hat (audio.py:172).

## Behebung

`_schleife()` prueft jetzt vor dem Abspielen `runde != self._runde or self._abbruch.is_set()` und ueberspringt den Posten; `sagen()` legt dafuer `(proben, rate, self._runde)` ein, `abbrechen()` zaehlt `_runde` hoch. Zusaetzlich fragt `_abspielen()` direkt hinter `sd.play()` noch einmal den Merker ab und stoppt dort. Die Generationsnummer war noetig, weil ein `sagen()` unmittelbar nach dem Abbruch den Merker wieder loescht -- genau der Fall aus `_alles_stoppen()`. Belegt mit `scratchpad/pruef_audio.py`: der Abspielfaden wird per gepatchtem `get()` genau in das Fenster zwischen Entnahme und Pruefung gestellt; danach spielt er den abgebrochenen Satz nicht mehr an, wohl aber den nachgeschobenen neuen. Die Gegenprobe `scratchpad/gegenprobe_051.py` laeuft gegen `git show HEAD:sarvis/audio.py` und spielt den Satz dort weiterhin.
