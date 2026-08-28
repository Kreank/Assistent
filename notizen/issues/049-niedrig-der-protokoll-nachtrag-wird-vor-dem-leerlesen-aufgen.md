# 049 — Der Protokoll-Nachtrag wird VOR dem Leerlesen aufgenommen -- was waehrend des Abbruchs noch fertig wird, faellt still weg

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | reihenfolge |
| **Bereich** | hirn |
| **Fundstelle** | `sarvis/hirn.py:327` |
| **Status** | behoben |

## Was ist falsch

unterbrechen() nimmt den Schnappschuss des Protokolls in Zeile 327-328, liest danach bis zu zehn Sekunden lang leer (Zeile 332-337) und setzt _offen zurueck. Ein Werkzeug, das beim Schnappschuss noch lief und erst waehrend des Leerlesens fertig wird, ruft protokoll.merken() nach dem Schnappschuss -- der Eintrag steht dann im Protokoll, aber nicht im Nachtrag, und wird beim naechsten Zuruf in Zeile 384-385 durch leeren() geloescht. Zu korrigieren am gemeldeten Ablauf: timer_stellen ist ein rein lokaler Aufruf im Millisekundenbereich und praktisch nie das betroffene Werkzeug. Realistisch sind nur die Werkzeuge mit Netzverkehr -- finanzen_buchen, telegram_senden, mail_senden, termin_anlegen -- also genau die, die aussen wirken.

## Ablauf

Sarvis bucht auf Zuruf eine Ausgabe im Finanzdashboard und faengt an zu antworten. Der Nutzer faellt ihm ins Wort, main._unterbrechen() (main.py:486-505) bricht die Aufgabe ab und ruft hirn.unterbrechen(). await klient.interrupt() ist ein Aufhaengepunkt -- der Werkzeug-Handler laeuft im selben Ereignisring weiter, haengt aber noch an der HTTP-Antwort. Der Schnappschuss in Zeile 328 wird ohne ihn gezogen. Waehrend der Schleife ab Zeile 334 kommt die Antwort, der Handler ruft vermerken('finanzen_buchen: ...'). Beim naechsten Zuruf enthaelt _nachtrag den Eintrag nicht, Zeile 384-385 leert das Protokoll -- Sarvis weiss nichts von der Buchung und legt auf 'nimm doch lieber 40 Euro' eine zweite an.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Ich habe nach einem Aufraeumer gesucht, der das auffaengt, und keinen gefunden. Protokoll (werkzeuge/__init__.py:22-56) hat genau drei Methoden -- merken, leeren, nachtrag -- und keinen Zeitstempel und keine Trennung zwischen 'schon nachgetragen' und 'neu'. Die Werkzeuge rufen vermerken() nach getaner Arbeit, nicht davor (Beispiel erinnern.py:282-284: erst _schreiben/umschichten, dann vermerken). Der Handler haengt nicht an der Aufgabe, die main._unterbrechen() in Zeile 497 abbricht: Das ist der Verbraucher von receive_response, waehrend die MCP-Werkzeugaufrufe im internen Leseweg der SDK bedient werden -- deshalb laufen sie weiter, und genau darauf beruht ja der ganze Zweck der Klasse. Der Fund stimmt also. Die Schwere setze ich von mittel auf niedrig herunter: Das Zeitfenster ist die Restlaufzeit eines Werkzeugs ab dem Moment, in dem interrupt() zurueckkommt. Bei allen lokalen Werkzeugen (Timer, Gedaechtnis, Programme, Medien) ist es faktisch null, und der Fall, den der Docstring beschreibt -- Werkzeug VOR dem Abbruch fertig --, funktioniert einwandfrei. Es bleibt ein Rennen mit schmalem Fenster, kein Normalfall.

## Vorgeschlagene Behebung

Den Schnappschuss hinter das Leerlesen ziehen, ohne den frueh-Ausstieg zu verlieren. hirn.py:327-340 ersetzen durch:

        if self._offen:
            try:
                async with asyncio.timeout(10):
                    async for nachricht in self.klient.receive_response():
                        if isinstance(nachricht, ResultMessage):
                            break
            except (TimeoutError, asyncio.TimeoutError):
                ...  # siehe Fund 4
            finally:
                self._offen = False

        # ERST jetzt: Werkzeuge, die waehrend des Leerlesens noch fertig
        # geworden sind, gehoeren in den Nachtrag.
        if self.protokoll is not None:
            self._nachtrag = self.protokoll.nachtrag()

Damit faellt auch das `if not self._offen: return` weg -- der Schnappschuss muss auf beiden Wegen gezogen werden, und _arbeiter_verloren() in Zeile 325 steht ohnehin schon davor.

## Behebung

In `hirn.unterbrechen()` wird der Protokoll-Schnappschuss jetzt NACH dem Leerlesen gezogen, und zwar in einem umschließenden `finally` — dadurch entfällt der frühe `return`, und der Nachtrag entsteht auf jedem Weg, auch wenn das Leerlesen von außen abgebrochen wird. Belegt mit einem Skript, das die echte Methode mit einer Klienten-Attrappe ausführt: Ein Werkzeug, das erst während des Leerlesens `merken()` ruft, steht anschließend im Nachtrag; ohne offene Runde wird der Schnappschuss weiterhin gezogen.
