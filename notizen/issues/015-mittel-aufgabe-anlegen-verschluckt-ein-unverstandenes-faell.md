# 015 — aufgabe_anlegen verschluckt ein unverstandenes Faelligkeitsdatum und meldet Erfolg

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | stiller-abbruch |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/google.py:751` |
| **Status** | behoben |

## Was ist falsch

Laesst sich das Datum nicht in TT.MM.JJJJ zerlegen, wird der Fehler geschluckt und 'due' nicht gesetzt. Die Rueckmeldung lautet unveraendert "Aufgabe angelegt", ohne ein Wort zur fehlenden Frist. Im selben Modul macht es termin_anlegen richtig und antwortet bei unverstandenem Zeitpunkt mit einem Fehler.

## Ablauf

Nutzer: "Trag mir als Aufgabe ein: Reifen wechseln, bis 3. Oktober." Claude uebergibt faellig="2026-10-03" -> str.split(".") ergibt eine einelementige Liste -> ValueError beim Entpacken -> pass. Die Aufgabe entsteht ohne Datum, Sarvis antwortet "Aufgabe angelegt: Reifen wechseln." Nichts im Rueckgabetext nennt die Frist, der Nutzer hat keine Chance, das Fehlen zu bemerken.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Zeile 747-752 exakt wie gemeldet; Zeile 756-758 gibt unveraendert 'Aufgabe angelegt: ...' zurueck, ohne koerper.get('due') zu erwaehnen. Ich habe nach einem Auffangnetz gesucht und keins gefunden: aufgabe_anlegen steht in config.py:601 auf 'still', es gibt also nicht einmal eine Rueckfrage, in der ein Datum vorgelesen wuerde. Anders als bei termine_ansehen taucht das Datum auch in der Antwort nirgends auf -- hier fehlt jedes Signal, deshalb bleibt es bei mittel.

## Vorgeschlagene Behebung

Den except-Zweig in Zeile 751-752 nicht schweigen lassen. Entweder wie termin_anlegen (Zeile 421-425) mit einer Fehlerantwort abbrechen, oder das Format grosszuegiger lesen (ISO zusaetzlich zulassen) und im Erfolgsfall die uebernommene Frist mitsagen: 'f"Aufgabe angelegt: {args[titel]}" + (f", faellig {t:02d}.{m:02d}.{j}." if koerper.get("due") else ".")'. Dann faellt ein verschlucktes Datum sofort auf.

## Behebung

Neuer Helfer `_faellig_deuten()` versteht TT.MM.JJJJ und ISO; `aufgabe_anlegen` bricht bei unverstandenem Datum mit Fehler ab, statt es zu verschlucken, und nennt die uebernommene Frist in der Antwort.

Verhaltensaenderung: Ein Aufruf, der vorher "Erfolg" meldete und die Frist stillschweigend wegliess, meldet jetzt einen Fehler.
