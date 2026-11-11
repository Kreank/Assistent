# 064 — Rekursives Löschen der Wurzelorte war nur „fragen“

Status: erledigt (Commit 44e5fc2)

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | falsche-annahme (Sperrliste) |
| **Bereich** | entscheidungen |
| **Fundstelle** | `sarvis/schutz.py` (NIE_BEFEHL, `befehl_stufe`) |
| **Herkunft** | Prüflauf 11.11.2026 |

## Was war falsch

`NIE_BEFEHL` kannte nur `rm -rf /` und `rm -rf ~` als ganze Zeile. Der
Container hat genau drei beschreibbare Mounts — Saschas Benutzerordner,
alle Projekte, Sarvis' Daten samt Gedächtnis —, und deren vollständige
Löschung lag ein gesprochenes „ja“ entfernt:

    rm -rf /*   rm -rf ~/*   rm -rf $HOME   rm -r -f /home/server3070
    rm -fr /srv/data/sarvis   rm -rf /srv/storage/projects/*
    cd .. && rm -rf *        (aus einem Projekt heraus)

Alle gemessen „fragen“, jetzt „nie“.

## Behebung

`_loescht_wurzel()`: rekursives `rm` auf einen Wurzelort (privat,
arbeit, Daten, Sarvis' eigener Ordner, HOME), dessen Inhalt als Ganzes
oder alles darüber ist „nie“, auch nach einem `cd` in derselben Kette.
Ein einzelnes Projekt, `rm -rf build` oder eine einzelne Datei bleiben
„fragen“.
