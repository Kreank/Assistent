# 053 — Whisper laeuft im Mikrofon-Lesefaden; die Ueberlauf-Meldung von read() wird weggeworfen

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | stiller-abbruch |
| **Bereich** | sprachweg |
| **Fundstelle** | `sarvis/weckwort.py:287` |
| **Status** | behoben |

## Was ist falsch

Sachlich richtig: _schleife() (weckwort.py:281-292) liest blockierend und ruft in derselben Schleife _block() -> _pruefen() -> _deuten() -> ohren.hoeren(). Waehrend Whisper rechnet, wird strom.read() nicht aufgerufen, und das zweite Rueckgabefeld (die Ueberlauf-Flagge) wird in Zeile 287 mit '_' verworfen -- es gibt keinerlei Hinweis in der Konsole, waehrend audio.py:65-66 den Mikro-Status sehr wohl meldet. KORREKTUR der Wirkung und damit der Schwere: Der vom Reviewer gezeichnete Fall 'Loch mitten im Diktat' entsteht nicht. _pruefen() feuert ueber den Stille-Weg erst, wenn der Nutzer bereits 0,55 bis 3 s geschwiegen hat; und wenn der Durchgang weckt, setzt _deuten() in Zeile 475 ohnehin pausiert=True, danach wird verworfen. Auch der Notbremsen-Fall endet mit einer Weckung oder einem Verwerfen. Es bleibt genau eine Luecke: bei einem NICHT weckenden Lauf (Fenster zu, Halluzination, Echo) fehlen dem Mikrofon die Transkriptionssekunden -- bei kurzen Zurufen auf der 3080 Bruchteile einer Sekunde, spuerbar nur, wenn der Nutzer nach kurzer Pause sofort weiterredet. Das ist ein Randfall, kein Betriebsfehler.

## Ablauf

Ein Abschnitt endet, ohne zu wecken (kein Weckwort und Fenster zu, Halluzination, oder Echo). _pruefen() haelt den Lesefaden fuer die Dauer der Transkription an; der Geraetepuffer laeuft ueber, read() meldet das per Flagge, die verworfen wird. Der Anfang eines unmittelbar folgenden Satzes kann dadurch fehlen -- ohne eine Zeile in der Konsole.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Die Blockierung ist im Code eindeutig (weckwort.py:286-290 ruft _block() im selben Faden wie read(); _block->_pruefen->_deuten->self.ohren.hoeren in Zeile 411-418). Widerlegen liess sich nur der Schadensfall: nach jedem weckenden Durchgang ist der Horcher per pausiert=True (Zeile 475) und _verwerfen() (Zeile 386) ohnehin stumm geschaltet, die verlorenen Sekunden waeren also gar nicht verwendet worden. Deshalb niedrig statt mittel.

## Vorgeschlagene Behebung

Zwei kleine Schritte, beide in weckwort.py:281-292. Erstens die Flagge auswerten statt verwerfen: 'block, ueberlauf = strom.read(BLOCK)' und bei ueberlauf einmalig (mit Merker, damit es nicht spammt) print('  (Mikro: Puffer uebergelaufen -- Sekunden verloren)'). Zweitens, wenn die Luecke stoeren sollte: _pruefen() nicht im Lesefaden ausfuehren, sondern den fertigen Puffer in eine queue.Queue legen, die ein zweiter Daemon-Faden abarbeitet -- der Lesefaden ruft dann nur noch put() und bleibt am Mikrofon.

## Behebung

Nur der erste der beiden Vorschlaege umgesetzt: `strom.read(BLOCK)` liefert die Flagge jetzt nach `ueberlauf` statt nach `_`, und ein Ueberlauf wird ueber das neue `_meckern()` gemeldet (gedrosselt auf hoechstens eine Zeile je `MECKER_PAUSE` = 30 s, weil der Faden 33-mal je Sekunde laeuft). Den zweiten Vorschlag -- `_pruefen()` in einen eigenen Faden auszulagern -- habe ich NICHT umgesetzt: das ist ein Umbau des ganzen Ablaufs samt neuer Nebenlaeufigkeit zwischen Puffer, `pausiert` und `_verwerfen()`, und der Schaden ist laut Fund ein Randfall. Belegt mit `scratchpad/pruef_weckwort.py`: eine Attrappe fuer `sd.InputStream` meldet bei jedem `read()` Ueberlauf; nach rund einer Million Lesungen steht genau eine Zeile in der Konsole.
