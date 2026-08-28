# 056 — Buchungen und Empfaenger werden hart auf sechs gekappt -- ohne jeden Hinweis, dass da mehr war

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | filter-zu-streng |
| **Bereich** | werkzeuge |
| **Fundstelle** | `sarvis/werkzeuge/finanzen.py:265` |
| **Status** | behoben |

## Was ist falsch

Der angeforderte Umfang wird auf FINANZ_HOECHSTENS (6, config.py:364) begrenzt und so an den Server geschickt. Da der Server dann nur sechs Datensaetze liefert, kann der Rest anschliessend nicht mehr benannt werden. Der Deckel selbst ist Absicht und richtig; was fehlt, ist allein der Hinweis darauf -- weder die Werkzeugbeschreibung ('Wie viele. Vorgabe 5.') noch die Antwort erwaehnen ihn. finanzen_ausgaben macht es in Zeile 194-198 anders und sagt ', dazu N kleinere Kategorien'.

## Ablauf

Nutzer: 'lies mir die letzten fuenfzehn Buchungen vor'. Das Modell setzt limit=15, min(15, 6) macht daraus 6, der Server liefert sechs Buchungen. Sarvis liest sechs vor und hoert auf -- fuer den Nutzer klingt das, als seien es alle. Eine erneute Nachfrage mit hoeherem limit liefert wieder sechs. Dasselbe in finanzen_empfaenger, Zeile 233.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Der Sachverhalt stimmt, die Einstufung als 'mittel' nicht -- herabgestuft auf 'niedrig'. Bestaetigt: finanzen.py:265 und :233 kappen mit min(...), FINANZ_HOECHSTENS = 6 (config.py:364), und weil der Deckel in die Server-Anfrage einfliesst, kommt der Rest gar nicht erst an. ABER: Der Deckel ist keine Panne, sondern eine ausdrueckliche Entwurfsentscheidung, im Code begruendet -- config.py:362-363: 'Wie viele Posten hoechstens vorgelesen werden. Zwanzig Kategorien am Stueck haelt niemand aus -- wer mehr will, fragt nach.' Bei einem Sprachassistenten ist das richtig. Es gehen keine Daten verloren, es wird nichts Falsches gesagt, und ein gezieltes Nachfragen ('was war bei REWE') liefert die gesuchte Buchung ueber den Parameter 'suche'. Uebrig bleibt eine fehlende Hoeflichkeitsformel. Ein Subagent sollte hier auf keinen Fall den Deckel entfernen.

## Vorgeschlagene Behebung

Nur den Hinweis nachruesten, den Deckel unangetastet lassen. In beiden Werkzeugbeschreibungen die limit-Beschreibung von 'Wie viele. Vorgabe 5.' auf 'Wie viele. Vorgabe 5, hoechstens 6 -- mehr wird nicht am Stueck vorgelesen.' aendern (finanzen.py um Zeile 229 und um Zeile 259). Zusaetzlich in beiden Funktionen merken, ob gekappt wurde -- gekappt = int(args.get('limit') or 5) > config.FINANZ_HOECHSTENS -- und in dem Fall an den Antwortsatz ' Mehr lese ich nicht am Stueck vor.' anhaengen.

## Behebung

Der Deckel ist unangetastet geblieben, nur der Hinweis kam dazu: Die
limit-Beschreibung beider Werkzeuge lautet jetzt "Wie viele. Vorgabe 5,
hoechstens 6 — mehr wird nicht am Stueck vorgelesen." (aus
config.FINANZ_HOECHSTENS zusammengesetzt), und `_deckelhinweis()` haengt
" Mehr lese ich nicht am Stueck vor." an die Antwort, wenn mehr verlangt
war als vorgelesen wird. Belegt mit Attrappe statt echtem Dashboard:
limit=15 schickt weiterhin limit=6 an den Server und ergaenzt den
Nachsatz, limit=3 und die Vorgabe 5 nicht.
