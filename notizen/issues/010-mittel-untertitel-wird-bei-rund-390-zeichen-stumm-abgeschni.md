# 010 — Untertitel wird bei rund 390 Zeichen stumm abgeschnitten -- und zwar hinten

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | stiller-abbruch |
| **Bereich** | anzeige |
| **Fundstelle** | `sarvis/hud.py:688` |
| **Status** | behoben |

## Was ist falsch

Der Untertitel wird in einen festen Kasten von 520x108 Malraster-Punkten gezeichnet. QPainter.drawText mit Rechteck clippt am Rechteck, solange Qt.TextDontClip nicht gesetzt ist -- und weil zusaetzlich Qt.AlignTop gilt, faellt nicht der Anfang, sondern das ENDE weg. Gerade der zuletzt gesprochene Satz bzw. das Ende eines Diktats verschwindet, ohne Auslassungszeichen, ohne Hinweis. Es gibt an keiner Stelle der Kette eine Laengenbegrenzung: anzeige.py:42 reicht den Text ungekuerzt durch, hud.py:268 legt ihn ungekuerzt ab.

## Ablauf

main.py:660 sammelt die ganze bereits gesprochene Antwort in EINEN Untertitel (' '.join(gesprochen)) und schickt ihn nach jedem Satz neu; main.py:760 schickt bei einem Diktat den kompletten Whisper-Text. Ein zwei Minuten langes Diktat ist ausdruecklich vorgesehen (weckwort.py:390-391). Der Nutzer sieht die ersten fuenf Zeilen und haelt den Rest fuer nicht verstanden -- gehoert wurde er trotzdem. Betrifft beide Richtungen, 'du' wie 'sarvis'.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Nachgemessen mit echten Windows-Schriftmassen (PySide6 6.11.2, nativer Plattform-Plugin, 96 dpi, Segoe UI 11 DemiBold): lineSpacing = 19.92, Kasten = QRectF(70, 432, 520, 108) (aus MITTE.y()=222 + KRANZ=176 + 34, hud.py:38-41,686), also 108/19.92 = 5.42 -> 5 Zeilen. QFontMetricsF.boundingRect fuer 888 Zeichen Flauftext meldet 519 px benoetigte Hoehe bei 108 px Kasten. Pixeltest: gezeichnet wurden 888 Zeichen, unterste bemalte Zeile 539, Kastenunterkante 540 -- alles darunter faellt weg. Maximal sichtbar: 388 Zeichen (der Reviewer nannte 356; Groessenordnung stimmt, exakter Wert korrigiert). Kein Aufrufer kuerzt: grep ueber alle untertitel()-Aufrufe (main.py:194,245,357,465,482,598,611,660,760,850) zeigt keine Begrenzung, anzeige.py:42 auch nicht. Widerlegen liess sich nichts.

## Vorgeschlagene Behebung

In hud.py an der Setzstelle (Zeile 266-268) den Text auf das begrenzen, was in den Kasten passt, und zwar vom ANFANG her kuerzen, damit das Neueste stehenbleibt. Konkret in _lesen(): self.untertitel = m.get('text', '') ersetzen durch eine Kuerzung wie self.untertitel = t if len(t) <= 380 else '… ' + t[-380:]. Sauberer, weil schriftabhaengig: in _text() vor dem Zeichnen mit QFontMetricsF(p.font()).boundingRect(kasten, flags, text) pruefen und solange Zeichen vom Anfang wegnehmen (mit vorangestelltem '…'), bis boundingRect().height() <= kasten.height(). Qt.TextDontClip ist hier ausdruecklich KEINE Loesung -- der Text liefe dann unten aus dem Fenster.

## Behebung

Der Untertitel wird vor dem Zeichnen auf die Kastenhoehe gekuerzt, und zwar VORN (`"... " + Rest`), damit das zuletzt Gesagte stehen bleibt. Neue Methode `_untertitel_passend()`, Ergebnis gemerkt statt bei jedem Bild neu gemessen (11 Messungen beim ersten Bild, 0 bei den folgenden 60). Die Schriftmessung wurde mit nachgebildeten Massen geprueft, nicht gegen das echte Qt -- kein Fenster geoeffnet.
