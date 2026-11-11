# 031 — Der Phaser wandert nicht: der LFO wird auf einen einzigen Mittelwert eingedampft

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | falsche-annahme |
| **Bereich** | anzeige |
| **Fundstelle** | `sarvis/stimmfarbe.py:154` |
| **Status** | behoben |

## Was ist falsch

Der Docstring verspricht 'langsam wandernde Ausloeschungen'. Der LFO wird als vollstaendiges Array berechnet, dann aber nur ueber lfo.mean() als Skalar benutzt. Damit stehen die vier Kerbfrequenzen fuer den gesamten Satz fest -- es wandert nichts, es ist ein statisches Kerbfilter. Der Parameter 'geschwindigkeit' hat praktisch keine Wirkung mehr; stattdessen haengt der Klang von der LAENGE des Satzes ab, weil der Mittelwert eines Sinus ueber ein endliches Fenster laengenabhaengig ist. Schwere von mittel auf niedrig korrigiert: die Stelle ist in der ausgelieferten Konfiguration ueberhaupt nicht erreichbar (siehe Begruendung).

## Ablauf

mund.py:64 ruft stimmfarbe.faerben() mit config.STIMMFARBE. Nur wenn dort eine der vier Farben 'entrueckt', 'maschine', 'sirene' oder 'sarvis_kuehl' steht, laeuft _phaser ueberhaupt. Dann kippt die Klangfarbe von Satz zu Satz mit der Satzlaenge, statt innerhalb eines Satzes zu schimmern.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Die Codestelle ist genau so, wie gemeldet (stimmfarbe.py:152-156): lfo wird ueber die volle Laenge gebaut, in der Schleife steht dann 0.6 + 0.8 * lfo.mean(). Die Zahlen des Reviewers sind exakt reproduziert (numpy, 22050 Hz): geschwindigkeit 0.18 / 2.0 s -> mean 0.862 -> unterste Kerbe 386.9 Hz; 0.35 / 2.0 s -> 0.649 -> 335.7 Hz. Bei fester geschwindigkeit 0.2 wandert die oberste Kerbe allein mit der Satzlaenge: 2843 Hz (0.8 s), 3091 Hz (2.0 s), 2400 Hz (5.0 s). Widerlegen liess sich der Mechanismus nicht -- wohl aber die Tragweite: config.py:243 liefert STIMMFARBE = 'aus' aus, und FARBEN['aus'] hat eine leere Schrittliste (stimmfarbe.py:168), es laeuft also im Auslieferungszustand gar keine Effektkette. Zusaetzlich nennt der Kommentar bei config.py:242 als moegliche Werte nur 'aus', 'hologramm', 'bordcomputer', 'halle', 'kuenstlich', 'nah' -- und KEINE dieser sechs Farben benutzt den Phaser. Die vier betroffenen Farben (stimmfarbe.py:237, 251, 291, 351) sind in der Konfiguration nirgends dokumentiert. Damit ist das ein Randfall: niedrig.

## Vorgeschlagene Behebung

Den LFO blockweise auswerten statt ihn zu mitteln. In stimmfarbe.py:150-157 die Schleife umbauen: das Signal in Bloecke von etwa 512 Proben zerlegen, je Block den LFO-Wert an der Blockmitte nehmen (lfo[i * block + block // 2]) und die Kerbfilter mit diesem Wert auf den Block anwenden, dabei den Filterzustand mit signal.lfilter(..., zi=...) ueber die Blockgrenzen mitfuehren, damit es nicht knackt. Wer den Aufwand scheut: wenigstens den Docstring bei Zeile 148 richtigstellen ('feste Ausloeschungen') und den nutzlosen Parameter 'geschwindigkeit' entfernen, damit die Signatur nicht laenger etwas verspricht, was die Funktion nicht tut.

## Behebung

`_phaser` (stimmfarbe.py) filtert jetzt blockweise: 512 Proben je Block, der LFO-Wert wird an der Blockmitte abgegriffen, und der Filterzustand jeder der vier Stufen laeuft ueber die Blockgrenzen mit (`signal.lfilter(..., zi=...)`), damit es an den Uebergaengen nicht knackt. Der Docstring nennt die Beobachtung, die dahintersteht; die Signatur bleibt unveraendert, `geschwindigkeit` wirkt wieder.

Belegt mit einem Pruefskript auf erzeugten Audiodaten (numpy/scipy, 22050 Hz, kein Ton abgespielt): die unterste Kerbe liegt in der ersten Satzhaelfte bei 344.5 Hz und in der zweiten bei 366.1 Hz -- sie wandert also innerhalb des Satzes. Die Laengenabhaengigkeit ist weg: derselbe Signalanfang ergibt bei 0.8 s, 2.0 s und 5.0 s Satzlaenge in den ersten 17408 Proben bitgleiche Ausgaben (max. Abweichung 0.0). Der groesste Sprung AN einer Blockgrenze ist mit mitgefuehrtem Zustand 0.170 gegenueber 0.261 ohne und liegt unter dem groessten Sprung im Signal selbst (0.346) -- es knackt also nicht. Die vier betroffenen Farben (entrueckt, maschine, sirene, sarvis_kuehl) laufen vollstaendig durch, ohne NaN und mit erhaltener Spitze.
