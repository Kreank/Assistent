# 026 — programm_beenden kann bei einem Namen ohne Wortzeichen ALLE Prozesse abschiessen

Status: gegenstandslos (powershell.exe/Stop-Process gibt es auf dem Server nicht; Fix b217416 steht im Code)

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | filter-zu-streng |
| **Bereich** | werkzeuge |
| **Fundstelle** | `sarvis/werkzeuge/programme.py:252` |
| **Status** | behoben |

## Was ist falsch

Der Name wird bereinigt, indem alles ausser Wortzeichen, Punkt, Leerzeichen und Bindestrich entfernt wird. Dass dabei nichts uebrig bleiben kann, wird nirgends geprueft -- die einzige Leerpruefung steht in Zeile 246, also VOR der Bereinigung. Aus einem leeren Rest wird das PowerShell-Muster "**", und das trifft jeden laufenden Prozess. Ausserdem beendet das Muster auch im Normalfall alle Treffer, die Antwort nennt aber nur den ersten Prozessnamen.

## Ablauf

Das Modell setzt einen Namen, der nur aus Satzzeichen oder einem Emoji besteht (z.B. name='!!!'). Zeile 246 laesst das durch, re.sub in Zeile 252 macht daraus "". Der Befehl lautet dann Get-Process -Name "**" | Stop-Process -Force und beendet saemtliche Prozesse des Nutzers, Sarvis eingeschlossen. KORREKTUR am urspruenglichen Ablauf: Die Rueckfrage nennt sehr wohl den Rohnamen -- rueckfrage.py:253-254 formuliert 'Soll ich !!! wirklich beenden?'. Der Nutzer hoerte also etwas Sinnloses und wuerde vermutlich ablehnen; die Absicherung haengt damit allein an seiner Aufmerksamkeit.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Der Defekt ist echt, die Einstufung war zu hoch. Bestaetigt: Zeile 246 prueft den Rohnamen, Zeile 252 bereinigt danach ohne erneute Pruefung, Zeile 257 baut daraus -Name "*{sicher}*", bei leerem sicher also "**" -- PowerShell-Wildcard, trifft alles -- und Zeile 258 beendet mit '$p | Stop-Process -Force' ausdruecklich ALLE Treffer, waehrend Zeile 259 nur den ersten Namen zurueckmeldet. Keine Absicherung dahinter. Herabgestuft auf 'mittel', weil zwei Dinge zusammenkommen muessen, die den Fall zum Randfall machen: (a) das Modell muesste einen Namen setzen, der nach Entfernen aller Nicht-Wortzeichen leer ist -- \w umfasst in Python auch Umlaute und CJK, es bleiben praktisch nur reine Satzzeichen oder Emoji; (b) programm_beenden steht auf 'fragen' (config.py:580), und die Rueckfrage spricht den Rohnamen aus (rueckfrage.py:253). Die Folge waere allerdings total (auch Sarvis selbst), und die Absicherung kostet eine Zeile -- deshalb nicht 'niedrig'.

## Vorgeschlagene Behebung

Direkt nach Zeile 252 einfuegen: if not sicher.strip(' .-'): return {'content': [{'type': 'text', 'text': f'Mit dem Namen {gesucht!r} kann ich nichts anfangen.'}], 'is_error': True}. Zweitens die Antwort ehrlich machen: in Zeile 259 'Select-Object -ExpandProperty ProcessName -Unique' statt '-First 1' verwenden, in Zeile 263-264 alle Zeilen der Ausgabe einsammeln und in Zeile 274 alle beendeten Namen nennen ('Chrome, Chromedriver sind beendet.').

## Behebung

Nach der Bereinigung wird geprueft, ob ueberhaupt etwas uebrig bleibt -- sonst Abbruch, bevor das Muster gebaut wird. Namen wie `!!!`, `...`, ein Emoji oder Leerzeichen werden abgelehnt; `chrome`, `blender`, `notepad++` nicht. Ausserdem sammelt der Befehl die Namen vor dem Beenden ein, sodass die Antwort alle nennt. Geprueft ohne einen einzigen echten `Get-Process`- oder `Stop-Process`-Aufruf.
