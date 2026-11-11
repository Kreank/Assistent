# 047 — Nach einem Abbruch bleibt der Horcher im Zustand "Sarvis spricht" haengen

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | zustand-ueberschrieben |
| **Bereich** | hauptschleife |
| **Fundstelle** | `sarvis/main.py:678` |
| **Status** | behoben |

## Was ist falsch

vorlesen() meldet jeden Satz mit self.horcher.spricht(satz) an (main.py:650); zurueckgesetzt wird nur auf dem Normalweg in main.py:678. Wird die Aufgabe unterbrochen, ruft weder _unterbrechen() (486-505) noch eines der finally-Bloecke (704-705, 718-719, 735-736) jemals spricht(None) -- dort steht nur pause(False). Im Horcher bleibt _spricht_gerade = True und _eigene_saetze gefuellt. Die Folge ist aber -- entgegen der Meldung -- ausschliesslich eine Anzeige-Folge, kein Hoerverlust: _spricht_gerade wird in weckwort.py nur an zwei Stellen gelesen (Zeile 313 fuer die Pegelmeldung und Zeile 397 fuer die DENKT-Anzeige langer Aufnahmen). VAD, Puffer, _pruefen, _deuten und das Wecken laufen unveraendert weiter.

## Ablauf

Der Nutzer faellt Sarvis mitten in der Antwort ins Wort. Der wirklich dauerhafte Fall ist die Tastenunterbrechung, auf die kein gesprochener Satz folgt: nach _unterbrechen() nimmt _durchgang() auf, verwirft aber (zu kurz, main.py:745-748, oder "nichts verstanden", 753-756) und sagt nichts. _spricht_gerade bleibt True, weckwort._block meldet den Mikrofonpegel nicht mehr (weckwort.py:313), der Ring der Anzeige steht still -- bis Sarvis das naechste Mal einen Satz regulaer spricht und spricht(text) den Ring wieder uebernimmt. Zusaetzlich bleiben bis zu drei alte Saetze in _eigene_saetze; _eigen_echo verwirft die naechste Aeusserung aber nur, wenn sie mindestens drei Woerter hat UND 70 % Wortueberschneidung mit einem dieser alten Saetze zeigt (weckwort.py:220-241) -- praktisch nur, wenn der Nutzer Sarvis woertlich zitiert.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Bestaetigt, aber deutlich harmloser als gemeldet, deshalb von mittel auf niedrig. Nachgesehen: Alle drei Aufraeumbloecke (main.py:704-705, 718-719, 735-736) setzen nur arbeitet/aufgabe/pause -- spricht(None) fehlt in allen dreien, _unterbrechen (486-505) ebenfalls. Ein Selbstheilen gibt es auf den meisten Wegen: die "stopp"-Verzweigung endet in _alles_stoppen() -> _sagen("Gestoppt.") -> _sagen_und_warten mit finally spricht(None) (main.py:470-477); der Weckwort-Abbruch startet sofort _weckwort_durchgang, dessen erstes vorlesen() spricht(satz) neu setzt; die Tastenaufnahme selbst speist den Ring ueber Aufnehmer(melden=self.anzeige.pegel) (main.py:85). Haengen bleibt es nur in der oben beschriebenen Luecke -- und dann rein optisch. Die im Fund behauptete Folge "totes Mikrofon" stimmt fuer die Anzeige, nicht fuer das Hoeren.

## Vorgeschlagene Behebung

Zwei kleine Ergaenzungen, weil der Faden von vorlesen() beim Abbruch weiterlaeuft und ein spaetes spricht(satz) sonst ein frueheres spricht(None) wieder ueberschreibt: (a) in vorlesen() (main.py:644-658) den Rumpf ab Zeile 650 in try/finally fassen und im finally 'if self.abgebrochen: self.horcher.spricht(None)' setzen; (b) in _unterbrechen() nach 'self.aufgabe = None' (main.py:502) zusaetzlich 'self.horcher.spricht(None)' aufrufen. spricht(None) ist idempotent (weckwort.py:197-205: setzt _spricht_gerade=False, leert _eigene_saetze, ruft pause(False)) und kollidiert nicht mit dem direkt danach folgenden pause(False) der finally-Bloecke.

## Behebung

`vorlesen()` in main.py fasst den Rumpf ab `spricht(satz)` in try/finally und meldet den Satz im finally wieder ab, wenn er nicht tatsächlich beim Lautsprecher gelandet ist; zusätzlich ruft `_unterbrechen()` nach `self.aufgabe = None` ein `self.horcher.spricht(None)`. Bewusst am tatsächlich Gesprochenen festgemacht statt an `self.abgebrochen`: Der Vorlese-Faden läuft nach dem Abbruch weiter, und die Schleife setzt die Flagge in main.py:863/896 bereits wieder auf False — eine späte Prüfung auf die Flagge hätte den Abbruch verpasst. Belegt mit einem Skript, das den Quelltext von `vorlesen` unverändert aus main.py schneidet und mit Attrappen ausführt: Abbruch während der Synthese, Abbruch mit zwischenzeitlich zurückgesetzter Flagge, leere Synthese und ein Fehler in der Synthese enden alle mit `_spricht_gerade = False`, der Normalfall behält die Anmeldung für den Echo-Filter.
