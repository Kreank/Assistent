# 052 — leer wird zwischen clear() und put() gesetzt -- warten() kehrt zurueck, obwohl noch ein Satz aussteht

Status: gegenstandslos (audio.Lautsprecher läuft nur lokal, auf dem Server spricht der NetzLautsprecher; Fix b217416 steht im Code)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | race |
| **Bereich** | sprachweg |
| **Fundstelle** | `sarvis/audio.py:173` |
| **Status** | behoben |

## Was ist falsch

Richtig beschrieben: sagen() ruft leer.clear() (audio.py:173) und erst danach put() (Zeile 174); der Abspielfaden setzt leer im finally, sobald er die Schlange leer vorfindet (audio.py:165-169). Beide Zugriffe sind ungesichert, ein Threadwechsel genau zwischen clear() und put() laesst leer gesetzt stehen, obwohl gleich darauf ein Posten in der Schlange liegt. Das Fenster ist allerdings nur wenige Bytecodes breit UND der Abspielfaden muss zufaellig genau in diesem Augenblick seinen empty()-Test ausfuehren -- die beiden Ereignisse sind voellig unkorreliert (der eine Faden kommt aus mund.sprechen(), der andere aus sd.wait()). Die Einstufung 'niedrig' war schon im Fund richtig. Der angehaengte Satz, dadurch greife 'zusaetzlich der Echo-Fehler', ist Spekulation und gehoert nicht zum Beleg.

## Ablauf

main._antworten legt Satz fuer Satz nach (vorlesen -> lautsprecher.sagen, main.py:645-661) und wartet am Ende mit lautsprecher.warten() (main.py:676). Trifft der empty()-Test des Abspielfadens nach dem vorigen Satz genau in die Luecke zwischen clear() und put(), kehrt warten() zurueck, bevor der letzte Satz angefangen hat.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Der Ablauf laesst sich nicht widerlegen -- die beiden Operationen stehen ungeschuetzt nebeneinander und werden aus verschiedenen Faeden gerufen (sagen() aus dem to_thread-Worker bzw. dem Event-Loop, das finally aus dem Abspielfaden). Nur die praktische Trefferwahrscheinlichkeit ist sehr klein.

## Vorgeschlagene Behebung

Ein Lock um beide Seiten. In audio.py __init__ 'self._tor = threading.Lock()'. In sagen(): 'with self._tor: self.leer.clear(); self._schlange.put((proben, rate))'. Im finally von _schleife(): 'with self._tor:' um den Block 'if self._schlange.empty(): ... self.leer.set()'. Alternativ ein Zaehler self._offen, der unter dem Lock beim put() hochgeht und nach dem Abspielen herunter -- leer.set() nur bei 0.

## Behebung

Neues `self._tor = threading.Lock()` in `__init__`. `sagen()` haelt es ueber `_abbruch.clear()`, `leer.clear()` und `put()`, das `finally` in `_schleife()` ueber `empty()` und `leer.set()`, `abbrechen()` ueber das Leeren der Schlange und `leer.set()`. Unter dem Schloss wird nichts getan, was blockieren kann -- `sd.stop()` und `melden()` stehen bewusst ausserhalb, damit daraus keine Verklemmung wird. Belegt mit `scratchpad/pruef_audio.py`: ein Helferfaden fuehrt den `empty()`-Test erzwungen mitten in das Fenster zwischen `leer.clear()` und `put()`, und `leer` bleibt geloescht; die Gegenprobe mit dem alten Ablauf setzt es. Dazu 500 gekreuzte `sagen()`/`abbrechen()`-Durchgaenge, in denen `warten()` immer zurueckkehrte.
