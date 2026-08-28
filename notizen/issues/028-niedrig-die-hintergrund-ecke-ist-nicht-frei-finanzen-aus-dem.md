# 028 — Die Hintergrund-Ecke ist nicht frei: 'Finanzen' aus dem Kranz liegt darueber

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | falsche-annahme |
| **Bereich** | anzeige |
| **Fundstelle** | `sarvis/hud.py:619` |
| **Status** | behoben |

## Was ist falsch

Der Docstring von _hintergrund_malen begruendet die Ecke oben links ausdruecklich damit, dass sie 'bei jedem Zustand frei bleibt' -- genau, um das frueher beobachtete Uebereinanderliegen dreier Texte zu vermeiden. Mit der aktuellen config.WERKZEUGE-Liste (17 Eintraege, config.py:789-807) landet die Beschriftung des letzten Werkzeugs 'Finanzen' aber genau in diesem Bereich. Die Annahme im Docstring stimmt also nicht mehr. Praktisch schlagen die Texte aber erst bei einer ungewoehnlich langen Hintergrundzeile aufeinander -- deshalb Schwere von mittel auf niedrig korrigiert. Nebenbefund derselben Stelle bestaetigt: der 260 px breite Kasten ohne TextWordWrap schneidet jede Zeile ab rund 44 Zeichen stumm ab.

## Ablauf

paintEvent (hud.py:344,352) malt in jedem Bild erst _kranz, dann ueber _text den Hintergrundkasten -- beide immer, es gibt keinen Zustand, in dem nur eines davon gezeichnet wird. Sobald _hintergrund_melden (main.py:507) eine Zeile mit rund 46 Zeichen oder mehr schickt, kreuzen sich die Glyphen am linken Rand von 'FINANZEN'. Die realistische Quelle dafuer ist hirn.subagenten_kurz(): 'Arbeiter: ' plus eine auf 40 Zeichen gekappte Beschreibung, also bis zu 50 Zeichen.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Geometrie nachgerechnet und mit echten Schriftmassen nachgemessen: 'Finanzen' ist Index 16 von 17, Winkel 4.3416 rad, Punkt (266.2, 58.0), Beschriftungskasten x 204.3..287.6 / y 32.2..48.2 (hud.py:518-526). Hintergrundzeile 0 = QRectF(20, 27, 260, 14), Zeile 1 = QRectF(20, 40, 260, 14) (hud.py:641-645). QRectF.intersects meldet fuer beide Ueberlappung -- das allein sagt aber nichts, weil die Zeilen linksbuendig sind und nur so weit reichen wie ihr Text. Deshalb Pixeltest mit beiden Ebenen getrennt gerendert und ueberlagert: 38 Zeichen ('Arbeiter: Fehler in der Anzeige suchen', endet bei x 170) -> 0 ueberlappende Pixel. 50 Zeichen ('Arbeiter: Frontend fuer das Dashboard bauen und pr', endet bei x 228) -> 35 ueberlappende Pixel im Bereich x 211..226, y 36..39. 'Arbeiter: MMMM…' (50 Zeichen) -> 102 Pixel. Der Fund ist also echt, aber bedingt. Zwei Angaben des Reviewers waren sachlich falsch und sind korrigiert: (a) subagenten_kurz() ist SEHR WOHL begrenzt -- hirn.py:258 kappt die Beschreibung mit str(was)[:40]; (b) auftrag.laufende_kurz() (auftrag.py:655) liefert 'Auftrag {nummer}: {projekt}', wobei projekt ein blosser Ordnername ist (auftrag.py:447, ordner.name) -- gemessen 64 px Breite, endet bei x 84, kann die Beschriftung also nie erreichen. Der 260-px-Abschnitt stimmt: 'Arbeiter: ' + 40 Zeichen ist 359 px breit, in 260 px passen rund 44 Zeichen.

## Vorgeschlagene Behebung

Zwei kleine Aenderungen an derselben Stelle. Erstens die Zeilen so kuerzen, dass sie den Kranz nicht erreichen: in hud.py:643-646 vor dem Zeichnen QFontMetricsF(p.font()).elidedText(zeile, Qt.ElideRight, 180) verwenden und den Kasten von 260 auf 180 verschmaelern -- dann endet der Text spaetestens bei x 200, also links von der Beschriftung ab x 204, und ein zu langer Text bekommt sichtbar '…' statt eines stummen Schnitts. Zweitens den Docstring ab Zeile 611 richtigstellen: die Ecke ist frei bis x 200, nicht unbegrenzt. Alternativ den Kasten um 20 px nach unten schieben (x, y = 16.0, 32.0), dann liegt Zeile 0 unterhalb von y 48.2.

## Behebung

In `_hintergrund_malen` (hud.py) sind die drei Zeilenkaesten von 260 auf 180 px verschmaelert worden, und der Text laeuft jetzt durch `QFontMetrics(p.font()).elidedText(zeile, Qt.ElideRight, 180)` -- damit endet er spaetestens bei x 200, links von der Beschriftung ab x 204.3, und ein zu langer Text bekommt sichtbar '…' statt eines stummen Schnitts. Der Docstring behauptet nicht mehr, die Ecke sei unbegrenzt frei, sondern nennt die Grenze x 200 und ihren Grund.

Belegt mit einem Rechenskript, das die Kranz-Geometrie ohne Qt nachbaut (Winkel 4.3416 rad, Punkt 266.4/57.9, Beschriftungskasten x 204.3..287.6 / y 32.2..48.2 -- deckungsgleich mit den Messwerten im Bericht): mit 260 px ueberschneiden sich Zeile 0 und Zeile 1 mit der Beschriftung, mit 180 px keine der drei Zeilen. `py_compile` laeuft durch; das Modul wurde bewusst nicht geladen und kein Fenster geoeffnet.
