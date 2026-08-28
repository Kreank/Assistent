# 029 — Das Aufblenden ('hervor') hat mit der ausgelieferten Konfiguration keinerlei Wirkung

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | falsche-annahme |
| **Bereich** | anzeige |
| **Fundstelle** | `sarvis/hud.py:311` |
| **Status** | behoben |

## Was ist falsch

self.hervor wird an zwei Stellen mit ausdruecklicher Begruendung gesetzt (hud.py:271 Untertitel: 4.0 Sekunden, hud.py:229 Verschiebemodus: 3.0 Sekunden) und wirkt ausschliesslich ueber diese eine Zeile. Der Boden ist hart auf 0.97 verdrahtet -- und config.DECKKRAFT_RUHIG ist ebenfalls exakt 0.97, DECKKRAFT_AKTIV ist 1.00. max(0.97, 0.97) und max(1.00, 0.97) aendern nichts. Der Mechanismus ist heute wirkungslos. Es ist damit kein Fehlverhalten, das der Nutzer sieht, sondern eine doppelt gefuehrte Konstante, die eine Schutzfunktion still verlieren laesst, sobald jemand an config.py dreht.

## Ablauf

In allen fuenf Zustaenden ist ziel_deck >= 0.97 (DECKKRAFT-Tabelle hud.py:80-86), das max() greift nie. Wer DECKKRAFT_RUHIG spaeter absenkt -- der Wert ist bei config.py:715 und im Kommentar bei hud.py:78 ausdruecklich als frei drehbar ausgewiesen --, bekommt die Schutzfunktion zurueck; wer ihn anhebt oder verstellt, verliert die Kopplung still, weil die 0.97 hier ein zweites, unabhaengiges Mal steht.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Beide Werte nachgelesen: config.py:716 DECKKRAFT_RUHIG = 0.97, config.py:717 DECKKRAFT_AKTIV = 1.00. hud.py:80-86 baut die Tabelle genau daraus. hud.py:309-311 setzt ziel_deck = DECKKRAFT[self.zustand] und danach max(ziel_deck, 0.97). Fuer 0.97 und 1.00 ist das die Identitaet. grep nach 'hervor' zeigt genau fuenf Fundstellen (124, 229, 271, 303, 310) -- ausser dieser einen Zeile wird der Wert nirgends gelesen, es gibt also keine zweite Wirkung, mit der sich der Fund entkraeften liesse. Die Einstufung 'niedrig' des Reviewers ist richtig: heute passiert nichts Falsches, es ist eine latente Wartungsfalle, kein Nutzerproblem.

## Vorgeschlagene Behebung

In hud.py:311 die hart eingetragene Zahl durch den Konfigurationswert ersetzen, den sie meint: ziel_deck = max(ziel_deck, config.DECKKRAFT_AKTIV). Dann blendet ein Untertitel bzw. der Verschiebemodus tatsaechlich auf volle Sichtbarkeit auf, unabhaengig davon, wie tief DECKKRAFT_RUHIG spaeter gestellt wird, und es gibt nur noch eine Quelle fuer den Wert. Der Kommentar bei hud.py:269-270 stimmt dann auch wieder.

## Behebung

In `_schlag` (hud.py) ist die hart eingetragene 0.97 durch `config.DECKKRAFT_AKTIV` ersetzt, mit einem Kommentar, der die doppelt gefuehrte Konstante erklaert. Die Werte in config.py sind vorher selbst nachgelesen worden: DECKKRAFT_RUHIG = 0.97 (config.py:716), DECKKRAFT_AKTIV = 1.00 (config.py:717) -- der Fund stimmt also, config.py selbst wurde nicht angefasst.

Belegt mit einem Rechenskript: bei ausgeliefertem DECKKRAFT_RUHIG = 0.97 liefert `max(0.97, 0.97)` unveraendert 0.97 (das Aufblenden tat nichts), `max(0.97, 1.00)` liefert jetzt 1.00. Auch bei einem abgesenkten DECKKRAFT_RUHIG = 0.55 blendet es jetzt auf 1.00 statt auf 0.97 auf.
