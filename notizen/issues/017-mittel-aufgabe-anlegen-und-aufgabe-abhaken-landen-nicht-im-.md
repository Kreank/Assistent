# 017 — aufgabe_anlegen und aufgabe_abhaken landen nicht im Protokoll

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | zustand-ueberschrieben |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/google.py:757` |
| **Status** | behoben |

## Was ist falsch

Beide Werkzeuge veraendern dauerhaft Google Tasks, rufen aber als einzige veraendernde Google-Werkzeuge kein vermerken() auf. Der Protokoll-Docstring in werkzeuge/__init__.py sagt: 'Nur Werkzeuge mit bleibender Wirkung landen hier' -- eine angelegte Aufgabe hat bleibende Wirkung.

## Ablauf

Nutzer: "Leg mir eine Aufgabe an: Reifen wechseln." Die Aufgabe entsteht (aufgabe_anlegen laeuft laut config.py:601 still durch, also ohne Rueckfrage). Der Nutzer unterbricht und sagt "nein, Oelwechsel". Weil nichts vermerkt wurde, enthaelt der Nachtrag den ersten Vorgang nicht -- Sarvis legt eine zweite Aufgabe an, statt die erste zu aendern. Das ist genau der Fehler, den der Protokoll-Docstring am doppelt gestellten Wecker beschreibt.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Nachgezaehlt: vermerken() steht in google.py in den Zeilen 433, 488, 614, 668, 898, 1030, 1114, 1152, 1186 -- also bei termin_anlegen, termin_absagen, mail_senden, mail_verschieben, kontakt_anlegen, drive_teilen, tabelle_anhaengen, tabelle_schreiben, tabelle_anlegen. In aufgabe_anlegen (endet Zeile 758) und aufgabe_abhaken fehlt es. Dass es an der Erlaubnisstufe laege, ist widerlegt: tabelle_anhaengen ist laut config.py:619 ebenfalls 'still' und vermerkt trotzdem, erinnern.merken (config.py:524, 'still') in erinnern.py:285 ebenso. Die Auslassung ist also nicht Absicht, sondern Luecke.

## Vorgeschlagene Behebung

In aufgabe_anlegen vor Zeile 757 'vermerken(f"aufgabe_anlegen: Aufgabe {args[titel]!r} wurde angelegt.")' einfuegen, in aufgabe_abhaken analog 'vermerken(f"aufgabe_abhaken: {titel} wurde abgehakt.")' vor der Erfolgsantwort -- gleiche Form wie die anderen neun Stellen.

## Behebung

`aufgabe_anlegen` und `aufgabe_abhaken` rufen jetzt `vermerken(...)` wie die neun anderen veraendernden Google-Werkzeuge, jeweils nach dem erfolgreichen API-Aufruf.
