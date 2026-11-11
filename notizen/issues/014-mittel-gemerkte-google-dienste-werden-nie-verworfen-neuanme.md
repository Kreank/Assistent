# 014 — Gemerkte Google-Dienste werden nie verworfen -- Neuanmeldung wirkt erst nach Neustart

Status: erledigt (Commit b217416; Rest RefreshError: das SDK meldet Ausnahmen eines Werkzeugs als Fehlerergebnis ans Modell, kein Absturz)

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | zustand-ueberschrieben |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/google.py:71` |
| **Status** | behoben |

## Was ist falsch

_dienst gibt einen einmal gebauten Dienst fuer immer zurueck; _dienste.clear() steht nur in anmelden_interaktiv (Zeile 95), und das laeuft laut google_anmelden.bat in einem eigenen Prozess. Ein Teil der Begruendung des Reviewers ist falsch: Der gemerkte Dienst haelt KEINE toten Zugangsdaten, solange das Refresh-Token lebt -- googleapiclient baut den Dienst mit AuthorizedHttp, das frischt das Zugriffstoken bei jedem Aufruf selbst auf. Bestaetigt bleibt der eigentliche Punkt: Ist das Refresh-Token nach sieben Tagen verfallen, hilft die Neuanmeldung im laufenden Prozess nicht, weil der Cache nie verworfen wird.

## Ablauf

Sarvis laeuft dauerhaft. Nach sieben Tagen verfaellt der Testing-Zugang (Kommentar in _zugangsdaten, Zeile 55-56). Der naechste Kalenderaufruf scheitert beim Auffrischen mit einem RefreshError statt mit der freundlichen Meldung von _fehlt() -- termine_ansehen hat kein try/except um den API-Aufruf. Der Nutzer fuehrt google_anmelden.bat aus; die schreibt eine neue Tokendatei und leert _dienste im EIGENEN Prozess. Im laufenden Sarvis haelt _dienste weiter den Dienst mit dem verfallenen Credentials-Objekt, jeder weitere Aufruf scheitert bis zum Neustart, und nichts sagt, dass ein Neustart noetig ist.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Zeile 70-72: 'if name in _dienste: return _dienste[name]' -- der Zugang wird danach nie wieder geprueft. Zeile 95 ist die einzige Stelle mit _dienste.clear(), sie steht in anmelden_interaktiv; google_anmelden.bat startet dafuer '.venv\Scripts\python.exe google_anmelden.py', also einen getrennten Prozess. Ich habe im gesamten Projekt keinen weiteren Aufrufer von _dienste.clear() oder einen Wiederaufbau der Werkzeuge zur Laufzeit gefunden (bauen() in werkzeuge/__init__.py:60 laeuft einmal beim Start). Damit stimmt der Fund, wenn auch aus einem etwas anderen Grund als beschrieben.

## Vorgeschlagene Behebung

In _dienst den Cache an die Tokendatei binden: neben dem Dienst die mtime von config.GOOGLE_TOKEN merken ('_dienste[name] = (stempel, dienst)') und bei geaenderter mtime neu bauen -- dann wirkt eine Neuanmeldung sofort. Zusaetzlich in _dienst 'zugang = _zugangsdaten()' auch im Cache-Treffer-Fall pruefen oder, einfacher, den Aufruf in _hole mit try/except google.auth.exceptions.RefreshError umgeben, dort _dienste.pop(name, None) machen und None zurueckgeben, damit die Werkzeuge wieder auf die Meldung von _fehlt() laufen.

## Behebung

`_dienst()` haengt den gemerkten Dienst an den mtime der Tokendatei und verwirft ihn bei Aenderung. Nach einer Neuanmeldung wirkt der Zugang jetzt sofort statt erst nach einem Neustart.

Unvollstaendig: Ein RefreshError, der erst beim eigentlichen API-Aufruf fliegt, wird weiterhin nirgends abgefangen -- der Nutzer sieht dann eine nackte Ausnahme statt der freundlichen Meldung. Ein Auffangring muesste in jedem Werkzeug oder einer gemeinsamen Huelle sitzen; das waere ein Umbau, kein Fix.
