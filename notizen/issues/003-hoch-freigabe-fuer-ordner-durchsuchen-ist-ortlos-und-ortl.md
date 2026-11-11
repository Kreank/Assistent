# 003 — Freigabe für "Ordner durchsuchen" ist ortlos — und ortlos heißt überall

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | falsche-annahme |
| **Bereich** | entscheidungen |
| **Fundstelle** | `sarvis/freigabe.py:39` |
| **Status** | behoben |

## Was ist falsch

_PFAD_WERKZEUGE listet nur datei_lesen, datei_schreiben und ordner_ansehen. Das Werkzeug ordner_durchsuchen hat aber ebenfalls ein Feld "pfad" (hirn.py:166-167 bildet Grep darauf ab) und steht in config.FREIGABE_NAMEN (config.py:677) als freigebbar. Weil es in _PFAD_WERKZEUGE fehlt, liefert ort() für jede Suchfreigabe "", und eine ortlose Freigabe gilt laut _unter() (freigabe.py:84-86) überall — genau der Fall, vor dem der Modulkopf warnt.

## Ablauf

Sarvis fragt "Soll ich in Projekt X nach ... suchen?". Der Nutzer sagt "ja, und frag die nächste halbe Stunde nicht mehr" — main.py:378 ruft _freigabe_erteilen, rueckfrage.freigabe_erkennen liefert 30, freigaben.erteilen trägt den Schlüssel ("ordner_durchsuchen", "") ein. Ab jetzt läuft JEDES Grep 30 Minuten lang still durch — auch über D:\Strato Server, das durchsuchen_stufe() korrekt auf "fragen" setzt. Nachgemessen: ort('ordner_durchsuchen', {'pfad':'D:/Privat/Sarvis'}) -> '' ; erlaubt(pfad='D:/Strato Server') -> True ; durchsuchen_stufe('D:/Strato Server') -> 'fragen'. Gesagt und angezeigt wird nur "Ordner durchsuchen für 30 Minuten" (kurz() -> 'frei: Ordner durchsuchen · 30 min') — ohne Ort, also merkt der Nutzer die Ausweitung nicht.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Ich habe versucht, den Fund zu widerlegen, und zwei Absicherungen gefunden, die aber beide nicht greifen. Erstens: main.py:307-314 bietet die Freigabe nur bei `wo` truthy von selbst an ("Nur MIT Ort") — das schützt aber nur den automatischen Vorschlag; der ausdrückliche Weg über rueckfrage.freigabe_erkennen (main.py:433-436) hat diese Bedingung nicht. Zweitens: FREIGABE_NIE (config.py:666-669) enthält ordner_durchsuchen nicht, erteilbar() gibt also True zurück. Gemessen mit dem echten Modul: der Schlüssel wird ortlos eingetragen und deckt D:/Strato Server ab. Der Fund stimmt.

## Vorgeschlagene Behebung

freigabe.py:39 um das Werkzeug ergänzen: _PFAD_WERKZEUGE = ("datei_lesen", "datei_schreiben", "ordner_ansehen", "ordner_durchsuchen"). Damit liefert ort() (Zeile 69-70) den Suchpfad, die Freigabe hängt am Ordner, und _unter() sperrt D:/Strato Server wieder aus. Zusätzlich abzusichern wäre erteilen() (Zeile 112-119): Wenn ein Werkzeug ein Feld "pfad" oder "befehl" in der Eingabe hat, der ermittelte Ort aber leer ist, gar keine Freigabe erteilen (return "") — dann kann derselbe Fehler bei einem neuen Werkzeug nicht wieder still passieren.

## Behebung

`ordner_durchsuchen` steht jetzt in `_PFAD_WERKZEUGE` (freigabe.py:42-45), damit `ort()` den Suchpfad liefert und die Freigabe wieder am Ordner hängt statt ortlos zu gelten. Zusätzlich erteilt `erteilen()` gar keine Freigabe mehr, wenn die Eingabe ein Feld `pfad` oder `befehl` mitbringt, sich daraus aber kein Ort bestimmen lässt (freigabe.py:145-153) — derselbe Fehler kann bei einem neuen Werkzeug nicht wieder still passieren. Belegt mit einem Skript gegen die echten Module: vorher `ort('ordner_durchsuchen', {'pfad':'D:/Privat/Sarvis'})` -> `''` und `erlaubt(..., 'D:/Strato Server')` -> `True`, nachher `'D:\Privat\Sarvis'` bzw. `False`; eine Freigabe für `git status` (kein Pfad im Befehl) wird jetzt nicht mehr eingetragen.
