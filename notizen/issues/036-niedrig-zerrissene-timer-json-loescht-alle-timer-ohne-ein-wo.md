# 036 — Zerrissene timer.json loescht alle Timer ohne ein Wort

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | stiller-abbruch |
| **Bereich** | auftraege |
| **Fundstelle** | `sarvis/werkzeuge/zeit.py:158` |
| **Status** | behoben |

## Was ist falsch

_sichern() schreibt mit write_text (Zeile 131-138), also nicht atomar -- anders als auftrag._atomar_schreiben (auftrag.py:214-247, mit Nebendatei, fsync und os.replace). Ein Abbruch zwischen dem Kuerzen auf null Bytes und dem Schreiben hinterlaesst eine leere oder halbe Datei. Beim naechsten Start faengt wiederherstellen() den ValueError ab und gibt eine leere Liste zurueck (Zeile 156-159). Ausgerechnet der Kommentar in _sichern (Zeile 139-146) begruendet ausfuehrlich, warum ein stilles pass beim Timer der Fehler ist, den man nie findet -- 20 Zeilen tiefer steht genau dieses stille Aufgeben, und zwar auch fuer OSError (gesperrte Datei, Virenscanner).

## Ablauf

Korrigiert: Der Zweig 'zweite Instanz schreibt gleichzeitig' fuehrt unter Windows zum PermissionError im Schreiben und damit zur sichtbaren Meldung aus Zeile 147, nicht zur Korruption. Bleiben: Stromausfall oder Abschuss des Prozesses in dem Sekundenbruchteil zwischen open('w') und close -- oder eine beim Lesen gesperrte Datei (OSError). Beim Start liest wiederherstellen(), json.loads scheitert, es kommt [] zurueck. Kein print, keine Ansage, kein Eintrag im Arbeitsgedaechtnis; zustand_zeile() (werkzeuge/__init__.py:112-132) ist ebenfalls leer, Sarvis haelt also fest, dass kein Timer laeuft. Der Wecker klingelt nie.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Code trifft zu: Zeile 156-159 gibt bei OSError und ValueError still [] zurueck, waehrend die Schwesterstelle im selben Modul (Zeile 147) und der Auftragslader in auftrag.py:280 ('(auftraege.json unlesbar -- rekonstruiere aus dem Journal)') genau solche Faelle melden. Ein Einzelinstanz-Schloss, das die Konkurrenz ausschliessen wuerde, habe ich nicht gefunden. Die Herabstufung auf 'niedrig' ist begruendet: Das Zeitfenster fuer eine zerrissene Datei ist Bruchteile einer Sekunde je Schreibvorgang, und die Datei ist wenige hundert Byte gross.

## Vorgeschlagene Behebung

Zwei kleine Aenderungen: (1) In _sichern (Zeile 131-138) ueber eine Nebendatei schreiben und mit os.replace tauschen -- auftrag._atomar_schreiben laesst sich dafuer in ein gemeinsames Modul heben statt zu duplizieren. (2) In wiederherstellen (Zeile 156-159) den stillen Ausstieg ersetzen: die Ausnahme melden ('  ! timer.json unlesbar -- keine Timer wiederhergestellt: {e}') und die kaputte Datei nach timer.json.kaputt umbenennen, damit sie nicht beim naechsten Sichern ueberschrieben wird.

## Behebung

(1) `_sichern()` schreibt ueber `auftrag._atomar_schreiben` -- mitbenutzt statt
nachgebaut, da ein gemeinsames Dateimodul eine Datei ausserhalb dieses
Auftrags gewesen waere (siehe Bericht). (2) `wiederherstellen()` gibt bei
OSError, kaputtem JSON oder einem JSON, das kein Array ist, nicht mehr still
`[]` zurueck: Es druckt die Ausnahme, benennt die Datei nach
`timer.json.kaputt` um, damit das naechste Sichern sie nicht ueberschreibt,
und gibt eine gesprochene Meldung zurueck ("Meine Timerliste war beim Start
unlesbar..."). Belegt mit `scratchpad/pruef_zeit.py`: halbe und leere
timer.json werden gemeldet und gerettet, nach dem Sichern bleibt keine
Nebendatei liegen.
