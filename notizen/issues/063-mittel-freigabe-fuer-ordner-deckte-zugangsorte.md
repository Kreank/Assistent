# 063 — Eine Freigabe für einen Ordner deckte still die Zugangsorte darin

Status: erledigt (Commit 55db580)

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | filter-zu-weit |
| **Bereich** | entscheidungen |
| **Fundstelle** | `sarvis/freigabe.py` (`erlaubt`) |
| **Herkunft** | Prüflauf 11.11.2026 |

## Was war falsch

`hirn.darf_ich` prüft die laufende Freigabe, sobald die Stufe „fragen“
ist — auch dann, wenn „fragen“ gerade WEGEN eines Ortes aus
`FRAGEN_TROTZ_FREI` kam. Eine Freigabe für „Lesen in deinem
Benutzerordner“ deckte damit `.ssh/config` mit ab. Dieselbe Klasse wie
003/004: eine harmlos erteilte Freigabe, die weiter reicht als gesagt.

## Gemessen

    Freigabe datei_lesen für /home/server3070, danach
    erlaubt(datei_lesen, /home/server3070/.ssh/config)   True → False
    erlaubt(datei_lesen, /home/server3070/notiz2.txt)    True → True

## Behebung

`erlaubt()` überspringt eine Freigabe, wenn die Anfrage einen Ort aus
`FRAGEN_TROTZ_FREI` berührt und die Freigabe nicht selbst in genau
diesem Ort liegt. Wer `.ssh` ausdrücklich freigibt, meint es — dann gilt
sie.
