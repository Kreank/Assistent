# 043 — telegram_lesen sagt "neueste zuerst" und liefert aelteste zuerst

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | reihenfolge |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/telegram.py:226` |
| **Status** | behoben |

## Was ist falsch

iter_messages liefert neueste zuerst (Telethon-Vorgabe, reverse=False), genau so werden die Zeilen angehaengt und beim Ausgeben mit reversed() umgedreht. Die Ausgabe ist aelteste zuerst, der Kopftext behauptet 'neueste zuerst'. Es ist eine falsche Beschriftung, nicht eine falsche Reihenfolge -- die Reihenfolge selbst (Chatverlauf von oben nach unten) ist die richtige.

## Ablauf

Nutzer: "Was hat Anna geschrieben?" -> telegram_lesen gibt den Verlauf aelteste-zuerst aus, der Kopf sagt 'neueste zuerst'. Anders als gemeldet fuehrt das kaum zur falschen Antwort: Jede Zeile beginnt mit '[26.08. 14:33]', das Modell entnimmt die Reihenfolge den Zeitstempeln und nicht der Ueberschrift. Schaden entsteht nur, wenn das Modell die Zeitstempel ignoriert und der Beschriftung mehr glaubt als dem Inhalt.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Zeile 215 'async for n in k.iter_messages(...)' -> neueste zuerst; Zeile 219 haengt in dieser Reihenfolge an; Zeile 226 '\n".join(reversed(zeilen))' dreht um; Zeile 225 sagt 'neueste zuerst'. Der Widerspruch ist real. Entkraeftet ist nur die Schwere: Zeile 219 setzt vor jede Nachricht '[{n.date.astimezone():%d.%m. %H:%M}]', die Ordnung ist also aus dem Text selbst ablesbar. Das Gegenargument des Reviewers (telegram_suchen widerspreche sich mit telegram_lesen) traegt nicht: telegram_suchen macht in Zeile 278 gar keine Aussage ueber die Reihenfolge ('N Fundstellen zu ...').

## Vorgeschlagene Behebung

Eine Zeile: In Zeile 225 'neueste zuerst' durch 'aelteste zuerst' ersetzen. Nicht reversed() entfernen -- die aufsteigende Ordnung ist die, in der man einen Chat liest, und telegram_suchen bleibt davon unberuehrt.

## Behebung

In der Kopfzeile von telegram_lesen steht statt "neueste zuerst" jetzt
"aelteste zuerst"; reversed() bleibt, weil die aufsteigende Ordnung die
ist, in der man einen Chat liest. Belegt mit Attrappe: vier Nachrichten
in Telethon-Reihenfolge (neueste zuerst) ergeben eine Ausgabe mit
aufsteigenden Zeitstempeln 23.08. bis 26.08. und passendem Kopf.
