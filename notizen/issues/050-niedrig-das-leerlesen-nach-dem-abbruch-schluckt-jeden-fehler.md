# 050 — Das Leerlesen nach dem Abbruch schluckt jeden Fehler und jeden Zeitablauf -- danach ist die naechste Antwort um eine Runde verschoben

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | stiller-abbruch |
| **Bereich** | hirn |
| **Fundstelle** | `sarvis/hirn.py:337` |
| **Status** | behoben |

## Was ist falsch

Der except-Ausdruck enthaelt neben TimeoutError auch Exception, faengt also alles ab und tut nichts damit -- die ersten beiden Eintraege sind ausserdem redundant, weil asyncio.TimeoutError seit 3.11 ein Alias von TimeoutError ist. Im finally wird _offen trotzdem auf False gesetzt. Laeuft die Zehn-Sekunden-Grenze ab, bleiben die Nachrichten der abgebrochenen Runde in der Leitung liegen, und der Code verhaelt sich anschliessend so, als waere sauber leergeraeumt worden. Es gibt weder eine Konsolenzeile noch einen Vermerk, der die naechste Runde davon wissen liesse.

## Ablauf

Sarvis laeuft in einem laengeren Zug; der Nutzer unterbricht. klient.interrupt() stoppt das Reden, aber die ResultMessage kommt nicht innerhalb von zehn Sekunden. asyncio.timeout schlaegt zu, Zeile 337 schluckt es kommentarlos, Zeile 340 setzt _offen = False. Beim naechsten Zuruf liest fragen() ab Zeile 389 aus derselben Leitung und bekommt zuerst die Reste der alten Runde -- inklusive deren ResultMessage, die receive_response() sofort beendet. Der Satzsammler spricht die alte Antwort auf die neue Frage. Genau das Symptom, das der Docstring dieser Methode als geloest beschreibt.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Ein echter Widerlegungspunkt: `except (..., Exception)` faengt asyncio.CancelledError NICHT -- die haengt seit 3.8 unter BaseException. Ein Abbruch von aussen faellt also korrekt durch, das Netz ist nicht so grob wie es aussieht. Die Zehn-Sekunden-Grenze selbst ist ebenfalls kein Fehler, sondern die bewusste Alternative zum Haengenbleiben. Was bleibt und was ich nicht wegbekomme: Es gibt keinen zweiten Anlauf und keine Meldung. In fragen() steht vor `await self.klient.query(...)` (Zeile 388) nichts, was eine unsaubere Leitung erkennen oder nachraeumen wuerde -- ich habe die Zeilen 353-389 vollstaendig gelesen, es gibt kein solches Flag im ganzen Hirn. Die Folge, die der Fund beschreibt, tritt also wirklich ein, wenn die Grenze reisst. Schwere von mittel auf niedrig: Der Pfad wird nur erreicht, wenn das Leerlesen nach einem bereits bestaetigten interrupt() laenger als zehn Sekunden braucht -- ein Randfall, und der Normalfall des Abbruchs ist abgedeckt. Der Kern des Funds ist die fehlende Meldung, nicht ein gebrochener Ablauf.

## Vorgeschlagene Behebung

Die Faelle trennen, sagen was war, und die naechste Runde vorwarnen. hirn.py:337-340:

        except (TimeoutError, asyncio.TimeoutError):
            self._leitung_unsauber = True
            print("  (Abbruch: Runde nicht in 10 s leergelesen -- die "
                  "naechste Antwort kann Reste enthalten)")
        except Exception as fehler:
            self._leitung_unsauber = True
            print(f"  (Abbruch: Leerlesen fehlgeschlagen -- {fehler})")
        finally:
            self._offen = False

Dazu in __init__ `self._leitung_unsauber = False` und in fragen() direkt vor Zeile 387 (`self._offen = True`) ein kurzer zweiter Anlauf:

        if self._leitung_unsauber:
            self._leitung_unsauber = False
            try:
                async with asyncio.timeout(2):
                    async for nachricht in self.klient.receive_response():
                        if isinstance(nachricht, ResultMessage):
                            break
            except (TimeoutError, asyncio.TimeoutError):
                pass

Das kostet im Normalfall nichts, weil das Flag nur nach einem gerissenen Leerlesen gesetzt ist.

## Behebung

Der Sammel-`except` ist in zwei Zweige getrennt (Zeitablauf und sonstiger Fehler), beide melden es in der Konsole und setzen `self._leitung_unsauber`; `fragen()` räumt bei gesetzter Flagge vor dem nächsten `query()` mit einer Zwei-Sekunden-Grenze nach und löscht sie. Im Normalfall kostet das nichts, weil die Flagge nur nach einem gerissenen Leerlesen steht. Belegt mit einem Skript, das die echten Methoden mit einer Klienten-Attrappe ausführt: Ein hängender Leerlesevorgang setzt die Flagge und druckt die Meldung, der nächste Zuruf liest die Reste weg und fragt danach genau einmal, und ohne Flagge findet kein zweiter Lesevorgang statt.
