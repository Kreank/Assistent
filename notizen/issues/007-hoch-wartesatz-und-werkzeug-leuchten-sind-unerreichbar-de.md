# 007 — Wartesatz und Werkzeug-Leuchten sind unerreichbar -- der erste elif frisst genau den Fall, fuer den der zweite gebaut wurde

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | reihenfolge |
| **Bereich** | hirn |
| **Fundstelle** | `sarvis/hirn.py:408` |
| **Status** | behoben |

## Was ist falsch

Die beiden AssistantMessage-Zweige stehen in der falschen Reihenfolge. Zeile 408 greift bei `not gestroemt`, Zeile 413 ist damit nur noch erreichbar, wenn `gestroemt` bereits True ist. Die Bedingung in Zeile 428 (`not gestroemt and not gewartet`) kann deshalb nie wahr werden: Der Wartesatz aus config.WARTESAETZE wird nie gesprochen. Zu praezisieren gegenueber der Meldung: Der KRANZ-Punkt leuchtet NICHT 'nie', sondern nur dann nicht, wenn Sarvis in diesem Zug noch kein Wort gesagt hat -- also genau in dem Fall, in dem die Anzeige das Einzige waere, was ueberhaupt etwas zeigt. Hat er vorher geredet, ist gestroemt True, Zweig 413 greift und der Kranz leuchtet.

## Ablauf

Nutzer: 'Hey Sarvis, was kostet gerade eine Waermepumpe?' Das Modell ruft WebSearch sofort auf, ohne vorher etwas zu sagen. Es kam kein text_delta, also ist gestroemt False. Die AssistantMessage mit dem ToolUseBlock trifft Zeile 408, laeuft ueber die Bloecke, findet keinen TextBlock und liefert nichts. Zeile 413 wird nicht mehr betreten, weil elif. Der Nutzer hoert vom Zuruf bis zum Suchergebnis nichts, und der Kranzpunkt 'Websuche' bleibt dunkel. Kein Fehler, keine Meldung.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Ich habe versucht, das zu widerlegen, und es geht nicht. Zeile 408 lautet woertlich `elif isinstance(nachricht, AssistantMessage) and not gestroemt:`, Zeile 413 `elif isinstance(nachricht, AssistantMessage):`. Zweiter Zweig also nur bei gestroemt == True erreichbar -- damit ist `not gestroemt` in Zeile 428 konstant False. `gestroemt` wird ausschliesslich in Zeile 406 gesetzt (text_delta) und in fragen() nie zurueckgesetzt. Kein anderer Aufrufer schiebt den Wartesatz ein: `grep -rn WARTESAETZE sarvis/` findet nur config.py:165 (Definition) und hirn.py:431. Auch die Ersatzhypothese 'WebSearch faellt in die Rueckfrage und da hoert man ja etwas' traegt nicht -- WebSearch steht in config.EINGEBAUTE_WERKZEUGE (config.py:642-644) und wird ueber _stille_werkzeuge() (hirn.py:130-132) vorab genehmigt, erreicht darf_ich() also nie. Bei WebSearch/Agent bleibt es genau so still, wie config.py:140-148 es ausdruecklich verhindern will. Schwere bleibt hoch nach der genannten Regel (trifft den Nutzer im normalen Betrieb), auch wenn nichts kaputtgeht -- es ist ausschliesslich UX.

## Vorgeschlagene Behebung

Die beiden Zweige zu einem zusammenlegen und den Notnagel innerhalb der Blockschleife behandeln. hirn.py:408-420 ersetzen durch:

            elif isinstance(nachricht, AssistantMessage):
                for block in nachricht.content:
                    # Notnagel, falls die Teilnachrichten ausbleiben.
                    if isinstance(block, TextBlock) and block.text:
                        if not gestroemt and not gesagt_ohne_strom:
                            gesagt_ohne_strom = True
                            yield block.text
                        continue
                    name = getattr(block, "name", "")
                    punkt = self.KRANZ.get(name)
                    if punkt and self.leuchten:
                        self.leuchten(punkt)
                    if (not gestroemt and not gesagt_ohne_strom
                            and not gewartet
                            and name in config.LANGSAME_WERKZEUGE):
                        gewartet = True
                        yield random.choice(config.WARTESAETZE) + " "

Dazu neben `gewartet = False` (Zeile 360) ein `gesagt_ohne_strom = False` einfuehren. Das Flag ist noetig, weil TextBlock und ToolUseBlock in DERSELBEN AssistantMessage stehen koennen -- sonst kaeme der Wartesatz hinter einem gerade erst per Notnagel ausgegebenen Satz noch einmal hinterher. Wichtig: `continue` nach dem TextBlock, damit ein Textblock nicht in die Werkzeugpruefung faellt.

## Behebung

Die beiden AssistantMessage-Zweige sind zu einem zusammengelegt, der Notnagel für Textblöcke sitzt jetzt in der Blockschleife mit `continue`, und `gesagt_ohne_strom` (hirn.py:370-373) verhindert, dass der Wartesatz hinter einem gerade per Notnagel gesprochenen Satz noch hinterherkommt (hirn.py:421-455). Abweichend vom Vorschlag hängt nur der Wartesatz an dem Flag, nicht der Notnagel selbst — sonst hätte er bei ausbleibenden Teilnachrichten ab der zweiten Nachricht geschwiegen. Belegt mit einem Skript, das den Klienten durch eine Attrappe ersetzt (kein Netz, kein Fenster) und die Nachrichtenfolge aus dem Ablauf einspielt: Die Fassung aus HEAD sagt bei einem sofortigen WebSearch nichts und lässt den Kranz dunkel, die neue sagt einen Wartesatz und leuchtet "Websuche"; Text und Werkzeug in derselben Nachricht ergeben genau einen Satz, zwei getrennte Textnachrichten weiter beide.
