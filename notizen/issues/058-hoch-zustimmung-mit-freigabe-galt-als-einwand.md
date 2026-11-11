# 058 — "Ja, frag nicht mehr nach" galt als Einwand statt als Zustimmung

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | filter-zu-streng |
| **Bereich** | entscheidungen |
| **Fundstelle** | `sarvis/rueckfrage.py:99` (deuten) |
| **Status** | behoben |
| **Herkunft** | Nebenbefund beim Beheben von Issue 019, eigenständig nachgemessen |

## Was ist falsch

`deuten()` prüft den Rest hinter einem "ja" gegen die NEIN-Liste. Das Wort
"nicht" steht dort — und es steht auch in der gebräuchlichsten Freigabewendung
überhaupt: "frag nicht mehr nach". Damit landete ausgerechnet die häufigste
Zustimmung im Anders-Zweig.

Zwei Funktionen derselben Datei widersprachen sich: `_FREIGABE` (Zeile 155 ff.)
listet `frag(e|st)?\s+(mich\s+)?nicht\s+(mehr|nochmal|...)` ausdrücklich als
Freigabewendung, und `freigabe_erkennen()` liefert für denselben Satz korrekt
30 Minuten — nur wird die Funktion nie erreicht, weil `deuten()` vorher
abbiegt.

## Ablauf

Sarvis fragt "Soll ich das ausführen?". Der Nutzer sagt "ja, frag nicht mehr
nach". Gemessen vor der Behebung:

    deuten("ja, frag nicht mehr nach")            -> "anders"   (erwartet: "ja")
    deuten("ja, frag mich nicht nochmal")         -> "anders"   (erwartet: "ja")
    freigabe_erkennen("ja, frag nicht mehr nach") -> 30.0       (wird nie erreicht)

Folge in `main.nachfragen` (main.py:392-400): Der Anders-Zweig merkt den
Vorgang als abgelehnt (`self._abgelehnt[schluessel] = ("anders", gehoert)`) und
gibt den Satz ans Hirn zurück. Der Nutzer bekommt damit **weder die Handlung
noch die Freigabe** — und wird beim nächsten Mal erneut gefragt, obwohl er
genau das abbestellt hat.

"ja, hör auf zu fragen" funktionierte, weil dort kein NEIN-Wort vorkommt. Die
Sache fiel deshalb nie zuverlässig auf.

## Warum das bestätigt wurde

Selbst nachgemessen mit dem echten Modul, nicht aus einem Agentenbericht
übernommen. Der Widerspruch ist innerhalb einer Datei belegbar: dieselbe
Wendung ist einmal als Freigabe registriert und einmal als Einwand gewertet.

## Behebung

Neue Hilfsfunktion `_ohne_freigabe()` schneidet die Freigabewendungen aus dem
Rest heraus, bevor gegen ANDERS und NEIN geprüft wird. Damit zählt nur noch,
was neben der Freigabe steht.

Nachgemessen: "ja, frag nicht mehr nach", "ja, frag mich nicht nochmal",
"ja, und frag nicht jedes mal", "mach das, frag nicht mehr" ergeben jetzt alle
`ja` mit 30 Minuten. Echte Einwände bleiben unverändert `anders`
("ja, aber nur die erste", "ja, aber lösch nichts", "ja, aber nicht löschen",
"ja, aber frag weiter nach"), Absagen bleiben `nein`, und ein schlichtes "ja"
erzeugt weiterhin keine Freigabe.
