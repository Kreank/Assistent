# 009 — projekt_anlegen mit art='web' bricht mitten im Anlegen ab und laesst eine halbe Projektruine zurueck

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | falsche-annahme |
| **Bereich** | werkzeuge |
| **Fundstelle** | `sarvis/werkzeuge/projekte.py:305` |
| **Status** | behoben |

## Was ist falsch

Auf jede Geruestdatei wird .format(titel=titel) angewendet, auch auf solche ohne Platzhalter. Der Inhalt von stil.css enthaelt geschweifte Klammern aus CSS, die str.format als Ersetzungsfeld liest. Der Fehler trifft ausschliesslich die Art 'web'; 'python' und 'leer' laufen durch.

## Ablauf

Nutzer: 'mach mir ein neues Web-Projekt fuer meine Fotoseite, privat'. Der Ordner wird angelegt (Zeile 297), README.md geschrieben (Zeile 299-303), index.html geschrieben -- dann bricht stil.css mit KeyError ab. git init, git add und git commit in Zeile 310-316 laufen nie. Der Nutzer bekommt keine Bestaetigung, sondern einen Werkzeugfehler. Versucht er es noch einmal mit demselben Namen, antwortet Sarvis 'fotoseite gibt es schon' (Zeile 291-293) -- der Ordner ist da, halbfertig und ohne Git.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Widerlegungsversuch gescheitert, sogar nachgemessen: ':root { color-scheme: light dark; }\n'.format(titel='X') wirft KeyError: ' color-scheme'. Genau dieser String steht in GERUEST['web']['stil.css'] (projekte.py:46), und Zeile 304-306 ruft .format(titel=titel) ueber alle Geruestdateien. Die Dict-Reihenfolge ist Einfuegereihenfolge: index.html (Zeile 39-45, enthaelt nur {titel} und formatiert sauber) wird geschrieben, dann kracht stil.css. Es gibt kein try/except um die Schleife -- der naechste except-Block sitzt erst in Zeile 317 und faengt nur SubprocessError/OSError um die Git-Aufrufe. Die Aufraeumfrage habe ich geprueft: nirgends wird der Ordner bei einem Fehler wieder entfernt. Die anderen Arten sind sauber ('python' hat nur {titel} in hauptprogramm.py, die .gitignore-Dateien enthalten keine Klammern).

## Vorgeschlagene Behebung

Zeile 305 von inhalt.format(titel=titel) auf inhalt.replace('{titel}', titel) umstellen -- gleiches Ergebnis fuer die vorhandenen Platzhalter, aber unempfindlich gegen Klammern in CSS, JS oder JSON, die kuenftig dazukommen. (Die Alternative, in stil.css doppelte Klammern zu schreiben, behebt nur diesen einen Fall und faellt beim naechsten Geruest wieder um.) Zusaetzlich die Schleife 304-306 in try/except OSError legen und im Fehlerfall den angelegten Pfad in der Meldung nennen, damit der Nutzer die halbe Ruine findet.

## Behebung

`inhalt.format(titel=titel)` durch `inhalt.replace("{titel}", titel)` ersetzt und die Schleife in try/except OSError gelegt, das den halbfertigen Pfad nennt. Vorher warf das CSS-Geruest reproduzierbar `KeyError: ' color-scheme'` und liess eine halbe Projektruine zurueck.
