# 045 — telegram_lesen wirft Bild- und Sprachnachrichten still aus der Zaehlung

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | filter-zu-streng |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/telegram.py:216` |
| **Status** | behoben |

## Was ist falsch

Die Anzahlgrenze wirkt beim Holen, der Textfilter erst danach. Nachrichten ohne Text (Foto ohne Bildunterschrift, Sprachnachricht, Sticker, Standort) werden ueber continue verworfen, ohne dass in der Ausgabe eine Luecke sichtbar waere.

## Ablauf

Nutzer: "Lies mir die letzten acht Nachrichten von Anna vor." Fuenf davon sind Fotos, eine ist eine Sprachnachricht. Sarvis liest drei Zeilen vor, ohne zu erwaehnen, dass sechs Nachrichten dazwischenlagen. Die Zeitstempel der verbleibenden Zeilen zeigen zwar eine zeitliche Luecke, sagen aber nicht, was dort stand -- und die Sprachnachricht, auf die es womoeglich ankam, existiert fuer den Nutzer nicht.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Zeile 215-219 wie gemeldet: limit=anzahl gilt fuer iter_messages, 'if not n.text: continue' filtert danach. Ein Auffangnetz gibt es nicht -- Zeile 221-223 meldet nur den Sonderfall, dass gar nichts uebrig blieb ('In X steht nichts Lesbares'). Es bleibt bei niedrig: Sarvis kann Bilder und Sprachnachrichten ohnehin nicht vorlesen, der Verlust ist also begrenzt auf das Wissen, DASS etwas da war.

## Vorgeschlagene Behebung

Statt 'continue' in Zeile 216-217 einen Platzhalter setzen: aus n eine kurze Marke ableiten ('[Foto]', '[Sprachnachricht]', '[Sticker]', sonst '[Anhang]' -- ueber n.photo / n.voice / n.sticker / n.media) und die Zeile mit dieser Marke statt n.text anhaengen. Dann bleibt die Zaehlung stimmig und das Modell kann sagen, dass eine Sprachnachricht dabei war.

## Behebung

Statt 'continue' setzt telegram_lesen jetzt eine Marke: `_marke(n)`
leitet aus der Nachricht [Sticker], [Foto], [Sprachnachricht], [Video],
[Audio], [Standort], [Kontakt], [Umfrage], [Datei], sonst [Anhang] bzw.
[Systemnachricht] ab. Die Reihenfolge der Pruefungen ist bewusst
(Sticker vor Video, Sprachnachricht vor Datei), weil Telethon mehrere
Merkmale gleichzeitig setzt. Damit stimmt die Zaehlung wieder. Belegt
mit Attrappe: vier angeforderte Nachrichten, davon ein Foto und eine
Sprachnachricht, ergeben vier Zeilen mit benannten Platzhaltern.
