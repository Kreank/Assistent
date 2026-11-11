# 061 — Die harte Sperre („nie“) war per Symlink, „/./“ oder „//“ zu umgehen

Status: erledigt (Commit 55db580)

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | falsche-annahme (Schreibweise statt Ort) |
| **Bereich** | entscheidungen |
| **Fundstelle** | `sarvis/schutz.py` (`_passt`) |
| **Herkunft** | Prüflauf 11.11.2026 |

## Was war falsch

`NIE_LESEN` und `NIE_SCHREIBEN` verglichen nur die Schreibweise, und die
Muster für die wirklichen Orte sind mit `$` verankert. Ein Punkt, ein
doppelter Schrägstrich oder ein Link reichten, um aus „nie“ ein
„fragen“ zu machen — und ein Link mit harmlosem Namen an einem Ort der
Freiliste machte den Google-Token sogar still lesbar.

## Gemessen (vorher → nachher, im Container)

    lesen_stufe('/srv/data/sarvis/./google_token.json')    fragen → nie
    lesen_stufe('/srv/data//sarvis/google_token.json')     fragen → nie
    lesen_stufe('<sandkasten>/harmlos.txt' -> Token)      FREI   → nie
    befehl_stufe('ln -s ../../google_token.json x')        fragen → nie
    befehl_stufe('cd /srv/data/sarvis && cat ./google_token.json')
                                                           fragen → nie

## Behebung

`_passt` prüft zusätzlich das aufgelöste Ziel (`os.path.realpath`,
Relatives am Arbeitsordner der Shell). `befehl_stufe` prüft `NIE_LESEN`
außerdem über den ganzen Befehl, damit ein `cd` davor mitzählt.
