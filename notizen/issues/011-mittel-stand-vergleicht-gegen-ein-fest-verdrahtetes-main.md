# 011 — stand() vergleicht gegen ein fest verdrahtetes main

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | falsche-annahme |
| **Bereich** | auftraege |
| **Fundstelle** | `sarvis/werkzeuge/auftrag.py:473` |
| **Status** | behoben |

## Was ist falsch

Der Basiszweig ist in Zeile 473 fest als 'main' eingetragen, obwohl starten() den Zweig mit 'git checkout -b' (Zeile 435-436) von dem Zweig abspaltet, der gerade ausgecheckt ist. Der Modul-Docstring nennt in Zeile 14 selbst 'git checkout master'. Schlaegt der git-Aufruf fehl, liefert die Hilfsfunktion git() (Zeile 465-471) einen leeren String zurueck, ohne dass der Fehler irgendwo auftaucht -- 'Fehler' und 'keine Commits' sind nicht unterscheidbar.

## Ablauf

Empirisch nachgestellt: In D:/Projekte/finanzdashboard existiert nur der Basiszweig 'master' plus 'sarvis/1-am-projekt-finanzdashboard-w'. 'git log sarvis/1-... --not main --oneline' bricht mit "fatal: ambiguous argument 'main'" ab, git() gibt '' zurueck, commits ist leer -- waehrend 'git log ... --not master' vier Commits auflistet. _laden() (Zeile 314-320) ruft stand() fuer jeden unterbrochenen Auftrag, unterbrochen_zeile() (werkzeuge/__init__.py:89-109) traegt das Ergebnis ins Arbeitsgedaechtnis und sagt dem Nutzer 'Auftrag 1 (finanzdashboard) -- noch kein Commit; N Dateien ungespeichert geändert' und bietet an, den Zweig zu verwerfen. Auf dieser Falschauskunft entscheidet der Nutzer. Umgekehrt zaehlt der Aufruf in einem main-Repo, wenn der Auftrag von einem Feature-Zweig aus gestartet wurde, dessen fremde Commits mit.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Nicht nur bestaetigt, sondern reproduziert: Beide vorhandenen Projekte unter D:/Projekte (finanzdashboard, kilometergeld) haben master als Basiszweig, keines hat main. Der Fund trifft also nicht einen theoretischen Randfall, sondern jeden unterbrochenen Auftrag in den real existierenden Projekten. Schwere bleibt 'mittel' und nicht 'hoch': Die Folge ist eine falsche Statuszeile, kein Datenverlust -- der Zweig wird nicht automatisch verworfen, das entscheidet laut unterbrochen_zeile ausdruecklich der Nutzer.

## Vorgeschlagene Behebung

Den Basiszweig beim Start festhalten statt zu raten: in starten() vor dem 'checkout -b' (vor Zeile 435) 'git rev-parse --abbrev-ref HEAD' auslesen, als Feld 'basis' im Auftrag-Dataclass (Zeile 152-176) fuehren, in _sichern()/journal mitschreiben und in _laden() zurueckholen. Zeile 473 dann 'git("log", auftrag.zweig, "--not", auftrag.basis or "HEAD", "--oneline")'. Als Rueckfall fuer Altauftraege ohne Feld: der erste Zweig, den 'git rev-parse --verify -q master' bzw. 'main' bestaetigt. Zusaetzlich sollte git() (Zeile 465-471) einen Fehlschlag unterscheidbar machen (z. B. None statt ''), damit stand() 'konnte ich nicht ermitteln' sagen kann statt 'noch kein Commit'.

## Behebung

`Auftrag` bekommt ein Feld `basis`; `starten()` liest den Zweig vor dem `checkout -b` mit `git rev-parse --abbrev-ref HEAD` aus (ein abgelöster Kopf, also die Antwort "HEAD", gilt als unbekannt), und das Feld wird in Journal, `_sichern()`, `_laden()` und `_aus_journal()` mitgeführt. `stand()` vergleicht gegen `auftrag.basis` und fällt für Altaufträge ohne Feld auf den ersten Zweig zurück, den `git rev-parse --verify -q` bestätigt (erst `master`, dann `main`); `git()` liefert bei einem Fehlschlag jetzt `None` statt `""`, sodass "wie weit er kam, konnte ich nicht ermitteln" von "noch kein Commit" unterscheidbar ist. Belegt an einem Wegwerf-Repo im Scratchpad mit Basiszweig `master` und zwei Commits auf `sarvis/1-test`: die alte Fassung meldet "noch kein Commit", die neue "2 Commits, zuletzt: ... arbeit zwei" — mit und ohne gemerkte Basis; in einem Ordner ohne Repo sagt die alte Fassung "noch kein Commit", die neue "konnte ich nicht ermitteln". `pruef_011b.py` zeigt zusätzlich, dass `basis` das Sichern, Laden und die Rekonstruktion aus dem Journal übersteht.
