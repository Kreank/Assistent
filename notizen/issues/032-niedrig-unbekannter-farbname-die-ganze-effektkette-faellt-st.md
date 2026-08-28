# 032 — Unbekannter Farbname: die ganze Effektkette faellt still weg

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | stiller-abbruch |
| **Bereich** | anzeige |
| **Fundstelle** | `sarvis/stimmfarbe.py:418` |
| **Status** | behoben |

## Was ist falsch

faerben() schlaegt den Namen mit FARBEN.get(farbe) nach und gibt bei einem Fehlschlag das Audio unveraendert zurueck -- kein Fehler, keine Meldung, kein Logeintrag. tonhoehe_faktor() (stimmfarbe.py:409-411) faellt genauso still auf FARBEN['aus'] zurueck. Ein Tippfehler in config.STIMMFARBE fuehrt damit dazu, dass die Stimme unbearbeitet bleibt, waehrend der Start ausdruecklich das Gegenteil meldet.

## Ablauf

config.STIMMFARBE (config.py:243) auf einen Namen setzen, den es in FARBEN nicht gibt (etwa 'sarvis_kuhl' statt 'sarvis_kuehl'). Mund.__init__ (mund.py:41-42) ruft tonhoehe_faktor() -> stiller Rueckfall auf 0 Halbtoene, also keine Vorkompensation des Sprechtempos. Die Startzeile mund.py:51-53 baut den Zusatz aber allein aus 'aus' ja/nein: farbe = '' if self.farbe == 'aus' else f', Farbe {self.farbe}' -- also druckt sie 'Piper bereit ... , Farbe sarvis_kuhl'. Danach gibt faerben() jeden Satz unbearbeitet zurueck. Der Nutzer bekommt die Bestaetigung, dass seine Farbe aktiv ist, hoert aber die rohe Sprecherstimme.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Beide Rueckfaelle im Code bestaetigt (stimmfarbe.py:409-411 und 417-419), und ich habe gezielt nach einer Pruefung an anderer Stelle gesucht: grep ueber das ganze Projekt nach STIMMFARBE / stimmfarbe. / FARBEN findet ausser config.py:243 nur mund.py:41, 42 und 64 -- es gibt nirgends eine Validierung, weder in einrichten.py noch beim Start. Die vom Reviewer zitierte Startmeldung habe ich in mund.py:51-53 nachgelesen, sie stimmt woertlich. Die Einstufung 'niedrig' ist richtig: der Auslieferungswert ist 'aus' (config.py:243), es braucht also einen Nutzer, der die Datei selbst bearbeitet und sich dabei vertippt -- und der Schaden ist die unbearbeitete Stimme, sonst nichts.

## Vorgeschlagene Behebung

Den Tippfehler dort melden, wo er entsteht -- beim Start, nicht bei jedem Satz. In mund.py nach Zeile 41 einfuegen: 'if self.farbe not in stimmfarbe.FARBEN: print(f"  ! Stimmfarbe {self.farbe!r} gibt es nicht -- moeglich: {', '.join(sorted(stimmfarbe.FARBEN))}"); self.farbe = "aus"'. Dann stimmt auch die Startzeile wieder, weil self.farbe danach tatsaechlich 'aus' ist. Passend dazu den Kommentar bei config.py:242 vervollstaendigen: er nennt sechs Farben, FARBEN kennt siebzehn.

## Behebung

Die vorgeschlagene Stelle liegt in mund.py, die fuer diesen Durchgang gesperrt war -- gemeldet wird deshalb in stimmfarbe.py, an genau den beiden Stellen, an denen der stille Rueckfall passierte. Neu ist `_bekannt(farbe)`: unbekannte Namen werden einmal je Name auf der Konsole gemeldet ("  ! Stimmfarbe 'sarvis_kuhl' gibt es nicht -- möglich: ..." mit allen siebzehn Namen), danach bleibt es beim bisherigen Verhalten. `tonhoehe_faktor()` ruft das auf und faellt danach ausdruecklich auf "aus" zurueck, `faerben()` ebenso. Da mund.py `tonhoehe_faktor()` beim Start aufruft (mund.py:42), erscheint die Meldung direkt vor der Zeile "Piper bereit" -- also einmal beim Start, nicht bei jedem Satz.

Belegt mit einem Pruefskript: `tonhoehe_faktor('sarvis_kuhl')` gibt die Meldung aus und liefert 1.0; die folgenden `faerben()`-Aufrufe mit demselben falschen Namen melden nichts mehr; bekannte Namen ('aus', 'sarvis_kuehl') melden gar nichts.

Zwei Punkte bleiben offen, weil sie ausserhalb der freigegebenen Dateien liegen: die Startzeile in mund.py:51-53 druckt weiterhin ", Farbe sarvis_kuhl", weil `self.farbe` dort unveraendert bleibt -- die Meldung steht jetzt aber unmittelbar darueber. Und der Kommentar bei config.py:242 nennt weiterhin nur sechs der siebzehn Farben.
