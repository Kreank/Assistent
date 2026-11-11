# 018 — telegram_senden verschickt bei EINEM schwachen Zufallstreffer ohne Rueckfrage

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | falsche-annahme |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/telegram.py:174` |
| **Status** | behoben |

## Was ist falsch

Geprueft wird nur, ob mehrere Chats dieselbe Guete haben (Zeile 175-180). Ein einzelner unscharfer Treffer wird ohne Mindestguete gesendet. Der Beleg des Reviewers ist dabei sachlich falsch: Sein eigenes Beispiel 'Ben' -> 'Kollegen Benedikt' ergibt nicht 30 ueber 'g in n' (Zeile 69), sondern 50 ueber 'any(teil.startswith(g))' (Zeile 67). Ein blosser Mittendrin-Teilstring (30) ist ein zusaetzlicher, seltenerer Fall. Der bestaetigte Kern: unterhalb von Guete 70 wird geraten, und die Rueckfrage kann das nicht auffangen.

## Ablauf

Nutzer: "Schreib Ben, ich komme spaeter." Es gibt keinen Chat 'Ben', aber die Gruppe 'Kollegen Benedikt' -> Guete 50, treffer hat einen Eintrag, gleichauf Laenge 1 -> gesendet. Die Rueckfrage (Stufe 'fragen' laut config.py:540) hilft nicht: rueckfrage.py:267-269 formuliert 'Soll ich Ben schreiben: ...?' aus dem Argument, nicht aus dem aufgeloesten Ziel -- die Aufloesung passiert erst im Werkzeug, danach. Der Nutzer hoert den Fehler erst in der Bestaetigung 'Gesendet an Kollegen Benedikt' (Zeile 188), also zu spaet. Voraussetzung ist allerdings, dass kein Chat besser passt: Gibt es 'Ben' wirklich, gewinnt er mit 100 und die Aufloesung ist korrekt.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Zeile 174-183: 'beste = treffer[0][0]' wird nirgends mit einem Mindestwert verglichen, 'gleichauf' prueft nur Gleichstand. Ein Sicherungsnetz an anderer Stelle gibt es nicht: config.py:540 setzt telegram_senden auf 'fragen', aber main.py:316 ruft rueckfrage.formulieren(werkzeug, eingabe) VOR dem Werkzeugaufruf mit den Rohargumenten -- der aufgeloeste Chatname existiert zu dem Zeitpunkt noch nicht. Die Werkzeugbeschreibung (Zeile 141-143) verlangt den exakten Namen, erzwingt ihn aber nicht. Herabgestuft auf mittel, weil der Fall voraussetzt, dass gar kein besser passender Chat existiert und das Modell entgegen der Beschreibung telegram_kontakte uebersprungen hat.

## Vorgeschlagene Behebung

In telegram_senden nach Zeile 174 eine Mindestguete verlangen: 'if beste < 70: return {... f"Der beste Treffer zu {an!r} ist {treffer[0][1].name} -- das ist geraten. Frag nach, wer gemeint ist. Nichts gesendet.", "is_error": True}'. 70 ist die Schwelle, ab der ein ganzes Wort des Chatnamens getroffen ist (Zeile 65) oder der Name mit dem Gesuchten beginnt (Zeile 62); 'Anna' -> 'Anna Mueller' (70) und 'Alex' -> 'Alex Frank' (80) laufen weiter durch, 'Ben' -> 'Kollegen Benedikt' (50) fragt nach.

## Behebung

In `telegram_senden` wird vor dem Gleichstands-Test eine Mindestguete von 70 verlangt; darunter geht nichts raus, sondern eine Fehlerantwort, die den geratenen Namen nennt. Geprueft wurde nur `_passt` -- keine Verbindung, kein Versand.

Verhaltensaenderung: "Schreib Ben" trifft die Gruppe "Kollegen Benedikt" (Guete 50) nicht mehr automatisch. `telegram_lesen` und `telegram_suchen` nehmen weiterhin ungeprueft den ersten Treffer -- reines Lesen, war nicht Gegenstand des Fundes.
