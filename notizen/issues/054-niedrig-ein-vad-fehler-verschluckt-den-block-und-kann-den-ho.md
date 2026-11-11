# 054 — Ein VAD-Fehler verschluckt den Block und kann den Horcher dauerhaft taub machen

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | stiller-abbruch |
| **Bereich** | sprachweg |
| **Fundstelle** | `sarvis/weckwort.py:303` |
| **Status** | behoben |

## Was ist falsch

Der Struktur nach richtig: 'except Exception: return' (weckwort.py:303-304) kehrt zurueck, bevor der Block gepuffert, _stille hochgezaehlt und _melden() gerufen wird. Bei einem Dauerfehler bliebe _redet auf True und _pruefen() wuerde nie wieder erreicht, weil beide Aufrufstellen (Zeile 324 und 334) in _block() unterhalb des try stehen. Es gibt auch keine Meldung -- start() (Zeile 179-181) faengt nur das LADEN ab. KORREKTUR: Der vom Reviewer genannte Ausloeser existiert nicht. Die Blockgroesse ist konstant: sd.InputStream wird mit blocksize=BLOCK geoeffnet und strom.read(BLOCK) liefert stets 480 Abtastwerte (weckwort.py:283-287), pcm hat damit immer die erwartete Form. Silero laeuft als ONNX-Netz mit fester Eingabeform -- was beim ersten Block funktioniert, funktioniert auch beim tausendsten. Es bleibt ein rein theoretischer Pfad (Speichernot, Treiberabsturz), und selbst dann ist die Folge sichtbar, weil der Pegelring stehen bleibt (Zeile 313-314 wird ja gerade nicht mehr erreicht). Randfall -> niedrig.

## Ablauf

vad.predict() wirft dauerhaft (praktisch nur bei Speichernot oder einem kaputten Modellzustand). _block() kehrt jedes Mal sofort zurueck, _redet bleibt True, der Puffer haelt einen halben Satz, es faellt keine Konsolenzeile. Der Horcher reagiert nicht mehr auf das Weckwort; sichtbar wird es nur daran, dass der Pegelring nicht mehr ausschlaegt.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Der Code bestaetigt die Struktur, aber nicht die Wahrscheinlichkeit: die Blockgroesse ist ueber blocksize=BLOCK und read(BLOCK) fest verdrahtet, der im Fund genannte 'Block mit falscher Laenge' kann gar nicht auftreten. Damit ist es kein Fehler, den der Nutzer im Betrieb trifft, sondern eine Haertungsluecke.

## Vorgeschlagene Behebung

weckwort.py:303-304 nicht mit 'return' quittieren, sondern den Block als 'keine Sprache' behandeln, damit ein laufender Abschnitt normal ausläuft und geprueft wird: 'except Exception as e: wahrscheinlich = 0.0' und davor/darin einmalig melden, z. B. ueber einen Merker self._vad_gemeckert in __init__: 'if not self._vad_gemeckert: self._vad_gemeckert = True; print(f"  (VAD stolperte — {e})")'. Der Pegel und der Nachlauf laufen dann weiter, und ein Dauerfehler steht in der Konsole.

## Behebung

`except Exception: return` in `_block()` ersetzt durch `except Exception as e: wahrscheinlich = 0.0` plus eine gedrosselte Meldung ueber das neue `_meckern()`. Der Block wird damit als "keine Sprache" gewertet: Pegelring, Nachlauf und `_pruefen()` laufen normal weiter, ein angefangener Abschnitt kommt zum Abschluss, `_redet` faellt zurueck auf False, und ein Dauerfehler steht in der Konsole statt in der Stille. Belegt mit `scratchpad/pruef_weckwort.py`: ein Attrappen-VAD, dessen `predict()` immer wirft, wird mitten in einen laufenden Abschnitt eingesetzt -- der Abschnitt wird trotzdem einmal geprueft, der Puffer geraeumt, der Ring weiter gefuettert, genau eine Zeile gemeldet, und nach dem Zuruecksetzen des VAD weckt der Horcher wieder.
