# 021 — Gesprochenes "hoer auf" waehrend einer offenen Rueckfrage stoppt nichts

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | filter-zu-streng |
| **Bereich** | hauptschleife |
| **Fundstelle** | `sarvis/main.py:835` |
| **Status** | behoben |

## Was ist falsch

Jeder normale Zuruf laeuft zuerst durch rueckfrage.ist_stopp() (main.py:634 -- die einzige Aufrufstelle im ganzen Projekt, nachgeprueft per Suche). Steht dagegen eine Rueckfrage offen, wird der Zuruf in der Weckwort-Verzweigung direkt als Antwort in die Future geschoben (main.py:833-838) und ist_stopp nie gefragt. Betroffen sind genau die Stopp-Wendungen, die rueckfrage.deuten() nicht kennt: "hoer auf", "aufhoeren", "stoppen"/"stoppe" (NEIN enthaelt nur "stopp"/"stop", und _wortweise setzt \\b, greift also nicht bei "stoppen"), "beenden", "brich ab", "sei still", "schluss", "ruhe". "stopp", "stop", "halt", "abbrechen", "abbruch", "lass das" stehen dagegen in NEIN und lehnen wenigstens die Frage ab -- laufende Auftraege beenden auch sie nicht.

## Ablauf

Ein Auftrag laeuft im Hintergrund, Sarvis fragt "Soll ich das ausfuehren?". Der Nutzer sagt "hoer auf". Der Satz geht an _antwort_geben (main.py:157-163), rueckfrage.deuten("hoer auf") liefert UNKLAR (weder in NEIN noch in JA noch in ANDERS -- nur in _STOPP_PAARE, rueckfrage.py:370). Sarvis hakt mit rueckfrage.genauer(...) oder NACHHAKEN nach (main.py:352-355). Sagt der Nutzer erneut "hoer auf", endet die Schleife nach zwei Versuchen; "hoer auf" hat nur zwei Woerter, faellt also nicht in den >=3-Woerter-Zweig (main.py:415) und wird ueber ABGELAUFEN als "nein" gewertet. Das angefragte Werkzeug laeuft damit zwar nicht -- aber _alles_stoppen() wird nie erreicht, laufende Hintergrundauftraege laufen weiter, und der Nutzer musste zweimal reden.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Kein Aufrufer faengt den Fall ab. Suche ueber sarvis/: ist_stopp wird ausschliesslich in main.py:634 gerufen, also erst in _antworten -- und dorthin kommt der Satz bei offener Rueckfrage gar nicht, weil main.py:835-838 mit 'continue' abbiegt. Der Horcher leitet den Satz auch nicht anders weiter: weckwort.py:466 laesst bei _frage_offen sogar Einzelwoerter durch, prueft aber nirgends auf Stopp. Der Kommentar an der "stopp"-Verzweigung (main.py:858-859: "Geht vor allem anderen, auch vor einer offenen Rueckfrage: Stopp heisst Stopp") belegt, dass Vorrang die Absicht ist -- er gilt aber nur fuer die Tastenkombination. Immerhin nicht ganz wirkungslos: _antwort_geben ruft lautsprecher.abbrechen() (main.py:161), die laufende Frage verstummt also sofort. Deshalb mittel und nicht hoch: kein Werkzeug wird faelschlich ausgefuehrt, es bleibt bei weiterlaufenden Hintergrundauftraegen und einer zweiten noetigen Aeusserung.

## Vorgeschlagene Behebung

In main.py:835-838 vor der Weitergabe an die Future pruefen: 'if antwortet: if rueckfrage.ist_stopp(zuruf): self._antwort_geben("nein"); await self._alles_stoppen(); continue' -- dann schliesst die offene Frage sauber als Ablehnung (deuten("nein") -> NEIN_SICHER, nachfragen kehrt mit "nein" zurueck) und der Not-Aus laeuft trotzdem. Damit nicht zwei Saetze hintereinander kommen (ABGELEHNT aus main.py:388 und "Gestoppt." aus main.py:566-570), entweder in nachfragen einen Merker abfragen oder die Future mit einem eigenen Sentinel aufloesen, auf den nachfragen ohne ABGELEHNT zurueckkehrt. Unabhaengig davon lohnt es, "aufhoeren", "stoppen", "stoppe", "beenden" in rueckfrage.NEIN aufzunehmen, damit auch ohne Not-Aus wenigstens die Frage klar abgelehnt statt nachgehakt wird.

## Behebung

Die Weckwort-Verzweigung prueft bei offener Rueckfrage jetzt zuerst `rueckfrage.ist_stopp()` und laeuft dann denselben Not-Aus wie die Tastenkombination; ein klares Ja ist ausgenommen. Alle 16 Stopp-Wendungen aus dem Fund loesen den Abbruch aus, waehrend "ja", "YouTube", "timer beenden" und "ja, hoer auf zu fragen" Antwort auf die Frage bleiben.

Verhaltensaenderung: Die offene Frage wird dabei still verworfen, gesagt wird nur "Gestoppt."
