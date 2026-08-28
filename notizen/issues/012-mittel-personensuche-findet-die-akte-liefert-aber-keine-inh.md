# 012 — Personensuche findet die Akte, liefert aber keine Inhalte

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | falsche-annahme |
| **Bereich** | auftraege |
| **Fundstelle** | `sarvis/werkzeuge/erinnern.py:161` |
| **Status** | behoben |

## Was ist falsch

Beim Anlegen wird der Name normalisiert (_sauberer_name, Zeile 58-70: Kleinschreibung, Umlaute zu ae/oe/ue, alles Nicht-Alphanumerische zu Bindestrich), beim Suchen nicht (Zeile 148: nur lower() und Leerzeichen normalisieren). Der Vergleich 'suche in datei.stem.lower()' (Zeile 161) trifft deshalb nicht mehr, sobald der gesuchte Name ein Leerzeichen oder einen Umlaut enthaelt. Der Treffer entsteht dann nur noch ueber die Ueberschriftzeile im Dateiinhalt -- und geliefert werden ausschliesslich die Zeilen, die den Suchtext woertlich enthalten (Zeile 162-163), also genau diese eine Ueberschrift.

## Ablauf

person_merken('Thomas Müller', ...) legt personen/thomas-mueller.md an mit '# Thomas Müller' (Zeile 314-318) und darunter '- 2026-08-27 — Trinkt Kaffee schwarz'. Nutzer fragt: 'Was weisst du ueber Thomas Müller?' -> suche='thomas müller', stem='thomas-mueller' -> passt=False. Die Faktenzeilen enthalten 'thomas müller' nicht, nur die Ueberschrift tut es. Zurueck kommt 'thomas-mueller.md:\n  # Thomas Müller' -- Sarvis sieht eine leere Akte und sagt laut Werkzeugbeschreibung ('Findest du hier nichts, sag das -- rate nicht'), er wisse nichts, obwohl alles dasteht. Dasselbe bei jedem Umlautnamen ('Müller' vs. stem 'mueller'). Nur einwortige Namen ohne Umlaut ('Thomas') funktionieren.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Bestaetigt, kein Auffangnetz gefunden: gedaechtnis_nachschlagen (Zeile 369-381) reicht das Stichwort unveraendert an nachschlagen() weiter, und nachschlagen() ist der einzige Lesepfad in Schicht 2 -- es gibt keine Stelle, die die Akte als Ganzes vorlegt. _sauberer_name wird ausschliesslich beim Schreiben benutzt (Zeile 87, 313), nie beim Suchen. Schwere bleibt 'mittel': Der Fall trifft nur zusammengesetzte Namen und Umlaute, und der Nutzer bekommt eine falsche Auskunft, aber nichts geht kaputt.

## Vorgeschlagene Behebung

In nachschlagen() (nach Zeile 148) zusaetzlich einen normalisierten Schluessel bilden und beim Dateinamen beides pruefen: 'schluessel = _sauberer_name(stichwort, 80)' und Zeile 161 zu 'stem = datei.stem.lower(); passt = suche in stem or (schluessel and schluessel in stem)'. Damit trifft 'Thomas Müller' -> 'thomas-mueller' und es werden wie beabsichtigt alle Zeilen der Akte geliefert. Fuer die Zeilensuche innerhalb einer Datei zusaetzlich Umlaute auf beiden Seiten falten, sonst findet 'mueller' die Zeile 'Müller' weiterhin nicht.

## Behebung

`nachschlagen()` bildet aus dem Stichwort zusätzlich einen Dateinamen-Schlüssel über `_sauberer_name()` und faltet Umlaute über die neue Hilfsfunktion `_falten()` — beim Dateinamen wie bei der Zeilensuche, auf beiden Seiten des Vergleichs. Der Rückfallwert "ohne-namen" von `_sauberer_name()` gilt ausdrücklich nicht als Treffer. Belegt mit `pruef_012.py` im Scratchpad an einer Akte `thomas-mueller.md`: Die alte Fassung liefert für "Thomas Müller" und für "Müller" nur die Überschriftzeile, die neue alle drei Zeilen; die Fälle "mueller", "thomas-mueller", "Thomas", "Kaffee" und "Bahn" verhalten sich vorher wie nachher gleich.
