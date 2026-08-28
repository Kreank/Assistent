# 034 — merken loescht bei kurzen Inhalten stumm fremde Eintraege

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | filter-zu-streng |
| **Bereich** | auftraege |
| **Fundstelle** | `sarvis/werkzeuge/erinnern.py:278` |
| **Status** | behoben |

## Was ist falsch

Als 'Widerspruchserkennung' dient die Teilzeichenkette aus den ersten 40 Zeichen des neuen Inhalts (Zeile 278-279). Der Filter wirkt nur in eine Richtung: Er trifft alte Eintraege, die den neuen Text enthalten -- nicht solche, die ihm widersprechen. Geloescht wird ohne Zaehlung und ohne Hinweis; die Antwort lautet nur 'Gemerkt (gesagt).' (Zeile 285-286). Das Gegenstueck vergessen() (Zeile 441-447) meldet dagegen genau, wie viele Eintraege es getroffen hat, und umschichten() (Zeile 105-113) betont ausdruecklich, dass nichts geloescht wird -- hier wird es geloescht.

## Ablauf

Korrigiert gegenueber der Meldung: Der Ablauf 'merk dir Anna' ist unrealistisch, weil das Schema fuer 'inhalt' einen vollstaendigen Satz verlangt (Zeile 240-245) -- bei einem Satz von 40 Zeichen muesste ein alter Eintrag diesen Satz woertlich enthalten, das ist dann tatsaechlich ein Duplikat. Real bleiben zwei Faelle: (a) Ein kurzer Inhalt, der Praefix eines aelteren, spezifischeren ist -- neu 'Ich mag Kaffee', alt '- 2026-05-02 — Ich mag Kaffee schwarz': der spezifischere Eintrag verschwindet ersatzlos und ungezaehlt. (b) Der eigentlich gemeinte Fall greift gar nicht: 'Ich mag Kaffee' und spaeter 'Ich mag Kaffee nicht' -- kern ist jetzt laenger als der alte Eintrag, der alte bleibt stehen, beide Widersprueche stehen nebeneinander.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Der Mechanismus ist genau so im Code (Zeile 278-280) und es gibt keine Zaehlung, keine Sicherung und keine Ablage in Schicht 2 fuer die verworfenen Zeilen. Der gemeldete Ausloeser stimmt aber nicht: Das Werkzeugschema verlangt einen ganzen Satz, und ein einzelnes Wort als 'inhalt' waere ein Fehlgebrauch des Modells, kein normaler Betrieb. Uebrig bleibt eine Heuristik, die in seltenen Konstellationen einen spezifischeren Eintrag frisst und im Zielfall nicht anschlaegt -- deshalb Herabstufung von 'mittel' auf 'niedrig'.

## Vorgeschlagene Behebung

Zeile 278-280: Mindestlaenge und Rueckmeldung ergaenzen, z. B. 'kern = inhalt.lower()[:40]' / 'ersetzt = [z for z in zeilen if len(kern) >= 20 and kern in z.lower()]' / 'zeilen = [z for z in zeilen if z not in ersetzt]' und in der Antwort (Zeile 285-286) anhaengen: '... ersetzt N frühere Einträge.' Wer es sauber will, haengt die ersetzten Zeilen zusaetzlich an die Monatsablage aus umschichten() an, statt sie zu verwerfen.

## Behebung

Der Kern greift erst ab 20 Zeichen, damit ein kurzer Praefix nicht den
genaueren Eintrag frisst, und was er trifft, wird nicht mehr weggeworfen:
Die ersetzten Zeilen wandern ueber die neue Hilfsfunktion `_ablegen()` in
dieselbe Monatsablage in Schicht 2, die auch `umschichten()` benutzt (das
jetzt ebenfalls `_ablegen()` ruft). Die Antwort beziffert die Ersetzung
("1 früherer Eintrag ersetzt — nachzulesen in den Notizen."). Belegt mit
`scratchpad/pruef_erinnern.py`: "Ich mag Kaffee" laesst "Ich mag Kaffee
schwarz" stehen, ein wirklich gleichlautender laengerer Eintrag wird ersetzt,
gezaehlt, liegt danach in der Ablage und ist ueber `nachschlagen()` wieder
auffindbar.
