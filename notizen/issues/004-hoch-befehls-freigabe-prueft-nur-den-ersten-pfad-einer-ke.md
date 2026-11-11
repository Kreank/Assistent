# 004 — Befehls-Freigabe prüft nur den ERSTEN Pfad einer Kette

Status: erledigt (Commit b217416; POSIX-Pfade seit d3ac2b2, ~/$HOME seit 55db580)

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | falsche-annahme |
| **Bereich** | entscheidungen |
| **Fundstelle** | `sarvis/freigabe.py:72` |
| **Status** | behoben |

## Was ist falsch

ort() bestimmt den Ort eines Befehls über _pfad_im_befehl(), und das ist laut eigenem Docstring "der erste Pfad in einem Befehl" (freigabe.py:42-57, re.search statt re.findall). Ein Befehl mit mehreren Pfaden bekommt damit den Ort des ersten zugewiesen. Da hirn.darf_ich die laufende Freigabe VOR der Rückfrage prüft (hirn.py:206-208) und sie ein "fragen" bedingungslos überstimmt, deckt eine harmlos erteilte Freigabe auch Ziele ab, die nie freigegeben wurden.

## Ablauf

Der Nutzer gibt "Befehle ausführen in Sarvis im Ordner Privat" für 30 Minuten frei. Danach läuft 'Get-Content D:/Privat/Sarvis/notiz.txt; Get-Content "D:/Strato Server/pw.txt"' auf. Nachgemessen: befehl_stufe(...) -> "fragen" (der heikle Ort wird von _heikler_ort_erwaehnt korrekt erkannt), aber ort('befehl_ausfuehren', ...) -> 'D:\\Privat\\Sarvis' und erlaubt(...) -> True. hirn.py:206-208 lässt den Befehl daraufhin ohne eine einzige Rückfrage durch und druckt nur "~ befehl_ausfuehren: läuft unter einer Freigabe durch". Der Passwortordner wird gelesen, obwohl die Stufenprüfung ihn richtig markiert hatte.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Widerlegungsversuche: (a) Der Trenner ";" steht in der Zeichenklasse von _pfad_im_befehl (Zeile 51: [^\s\"';|]*), der erste Pfad bricht also sauber ab und der zweite wird nie betrachtet — die Annahme des Reviewers stimmt genau. (b) erlaubt() (Zeile 123-129) prüft _unter(wo, freigegeben) mit dem einen wo aus ort(); es gibt keine zweite Schleife über weitere Pfade. (c) hirn.darf_ich prüft die Freigabe vor der Rückfrage, ein "fragen" wird also nicht mehr erreicht. Kein Aufrufer fängt es ab, mit dem echten Modul gemessen. Bestätigt.

## Vorgeschlagene Behebung

Zwei Stellen. Erstens in freigabe.py eine Listenfassung ergänzen: def _pfade_im_befehl(befehl) -> list[str] (re.findall statt re.search, plus die Git-Bash-Form wie in Zeile 54-56). Zweitens erlaubt() (Zeile 123-129) für befehl_ausfuehren gesondert behandeln: alle Pfade des Befehls einsammeln, jeden über dieselbe Ordner-Logik wie ort() auf seinen Ordner abbilden, und nur dann True zurückgeben, wenn ALLE unter dem freigegebenen Ort liegen (all(_unter(o, freigegeben) for o in orte)) — und False, wenn der Befehl gar keinen Pfad enthält, obwohl die Freigabe einen Ort hat. erteilen() darf weiter den ersten Pfad als Ort nehmen; entscheidend ist die Prüfseite.

## Behebung

Die Pfadsammlung liegt jetzt einmal in `schutz.pfade_im_befehl()` (schutz.py:227-246, `re.findall` plus Git-Bash-Form) und wird von `freigabe._pfade_im_befehl()` mitbenutzt (freigabe.py:46-58). `erlaubt()` behandelt `befehl_ausfuehren` gesondert: Eine verortete Freigabe trägt nur noch, wenn JEDER Pfad des Befehls unter dem freigegebenen Ort liegt, und ein Befehl ganz ohne Pfad trägt sie nie (freigabe.py:94-108 und 159-176). `erteilen()` nimmt weiter den ersten Pfad als Ort. Belegt am echten Modul: bei laufender Freigabe für `D:\Privat\Sarvis` liefert `erlaubt(befehl_ausfuehren, 'Get-Content D:/Privat/Sarvis/notiz.txt; Get-Content "D:/Strato Server/pw.txt"')` vorher `True`, nachher `False` — der Befehl im Projektordner allein bleibt `True`.
