# 062 — ~, $HOME, das nackte „cd“ und „..“ galten nicht als Pfad

Status: erledigt (Commit 55db580)

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | falsche-annahme (Windows-Regex) |
| **Bereich** | entscheidungen / auftraege |
| **Fundstelle** | `sarvis/schutz.py` (`pfade_im_befehl`, `_laufwerksform`, `arbeitsordner_merken`) |
| **Herkunft** | Prüflauf 11.11.2026 |

## Was war falsch

`pfade_im_befehl` trägt vier Sicherungen (harte Sperre über Befehle,
`entwicklung_frei`, Befehlsfreigabe, Wachhund des Arbeiters). Was sie
nicht findet, gilt an allen vier Stellen als unbedenklich. Sie kannte
weder `~` noch `$HOME`/`${HOME}`, `$PWD`, das nackte `cd` oder `..`
ohne Schrägstrich dahinter. Dazu machte `_laufwerksform` auch auf Linux
aus `/a/x` ein `A:/x` — für PosixPath ein relativer Pfad im Projekt.

## Gemessen (vorher → nachher, im Container)

    Arbeiter: 'cat $HOME/.claude/.credentials.json'               Allow → Deny
    Arbeiter: 'cd && cat .claude.json'                             Allow → Deny
    Arbeiter: 'cd .. && cd .. && cd .. && cat srv/data/sarvis/google_token.json'
                                                                   Allow → Deny
    Freigabe „Befehle in mcn“ deckte 'cat $HOME/.claude/.credentials.json'
                                                                   True  → False
    entwicklung_frei('cd ~ && pytest')                             True  → False
    _im_entwicklungsbereich('/a/../../etc')                        True  → False

## Behebung

Die Muster `_HEIM_PFAD`, `_PWD_PFAD`, `_CD_NACKT` und `_HOCH`; innerhalb
eines Befehls werden `cd`-Schritte mitgegangen (`_nach_cd`), damit
`cd web && npm run build && cd ..` im Arbeiter erlaubt bleibt.
`_laufwerksform` wirkt nur noch unter Windows, `arbeitsordner_merken`
deutet `~` und das nackte `cd` wie die Shell.

Gegenprobe: 54 Alltagsbefehle für `befehl_stufe` unverändert; im
Arbeiter von 18 nur `ls ~` und `echo ~` jetzt abgelehnt (der
Benutzerordner liegt außerhalb seines Projekts).

## Grenze

Was sich erst zur Laufzeit ergibt — `$(printf …)`, eine im selben Befehl
gesetzte Variable — sieht kein Regex. Dafür bleiben Sperrlisten und
Rückfrage.
