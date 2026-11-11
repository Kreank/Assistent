# 033 — Die Abbruchmeldung eines Auftrags wird nie erreicht

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | reihenfolge |
| **Bereich** | auftraege |
| **Fundstelle** | `sarvis/werkzeuge/auftrag.py:570` |
| **Status** | behoben |

## Was ist falsch

'await self._melden(auftrag)' steht in Zeile 570 ausserhalb des try/finally. Im Abbruchfall wird die CancelledError in Zeile 553-555 nach dem finally-Block weitergereicht, die Zeile darunter also uebersprungen. Der 'abgebrochen'-Zweig in _melden (Zeile 580-582) samt Windows-Benachrichtigung ist damit toter Code -- er kann nur erreicht werden, wenn der Status auf anderem Weg 'abgebrochen' wuerde, was nirgends geschieht: _laden() macht aus 'läuft' ein 'unterbrochen' (Zeile 306), nicht 'abgebrochen'.

## Ablauf

Nutzer sagt 'Stopp'. alles_abbrechen() (Zeile 624-637) cancelt die Aufgabe, _arbeiten faengt die CancelledError, setzt Status 'abgebrochen' und reicht sie weiter. Das finally schreibt Journal und Datei, danach endet die Aufgabe -- ohne _melden. Es erscheint keine Windows-Benachrichtigung mit dem Zweignamen und dem Hinweis auf bericht.md, anders als bei 'fertig' und 'fehler'. Dasselbe gilt fuer das Werkzeug auftrag_abbrechen (Zeile 741-744), das ebenfalls nur cancel() aufruft.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Bestaetigt: _melden wird im ganzen Modul nur an Zeile 570 aufgerufen, und die einzige Stelle, die 'abgebrochen' setzt, ist der CancelledError-Zweig, der unmittelbar danach 'raise' ausfuehrt. Die Schwere 'niedrig' ist richtig und ich wuerde sie nicht anheben: Der Nutzer hat den Abbruch selbst ausgeloest und bekommt aus auftrag_abbrechen bzw. main.py eine Rueckmeldung samt Zweignamen. Fehlt nur die Windows-Benachrichtigung.

## Vorgeschlagene Behebung

Wenn die Meldung erwuenscht ist, im except-Zweig (Zeile 553-555) vor dem 'raise' die synchrone Benachrichtigung direkt absetzen: 'if self.melden is not None: self.melden("Auftrag abgebrochen", f"Zweig {auftrag.zweig} · Stand in bericht.md")'. Ein 'await self._melden(...)' im finally waere der falsche Weg -- in einer gerade gecancelten Aufgabe wird das naechste await sofort wieder abgebrochen, und die gesprochene Ansage will man nach einem 'Stopp' ohnehin nicht.

## Behebung

Die Benachrichtigung sitzt jetzt im `except asyncio.CancelledError`-Zweig von
`_arbeiten` (auftrag.py:608-619), unmittelbar vor dem `raise` und bewusst
synchron: In einer gerade gecancelten Aufgabe wuerde jedes `await` sofort
wieder abbrechen. Gesprochen wird nichts -- nach einem "Stopp" will niemand
noch eine Ansage. Belegt mit `scratchpad/pruef_033.py`: Der SDK-Klient ist
durch einen haengenden Ersatz getauscht, `alles_abbrechen()` stoppt den
Auftrag, und die Pruefung sieht genau eine Benachrichtigung "Auftrag
abgebrochen" samt Zweigname, keine Ansage, und Journal wie auftraege.json
weiterhin geschrieben. Der (weiterhin unerreichbare) 'abgebrochen'-Zweig in
`_melden` wurde nicht angefasst.
