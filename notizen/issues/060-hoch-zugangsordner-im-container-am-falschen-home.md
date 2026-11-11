# 060 — Saschas Zugangsordner waren im Container „frei“: FRAGEN_TROTZ_FREI hing am falschen Home

Status: erledigt (Commit 55db580)

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | falsche-annahme (Windows/Einzelplatz) |
| **Bereich** | entscheidungen |
| **Fundstelle** | `sarvis/orte.py` (FRAGEN_TROTZ_FREI) |
| **Herkunft** | Prüflauf 11.11.2026, gegen den laufenden Container gemessen |

## Was war falsch

`FRAGEN_TROTZ_FREI` war aus `Path.home()` gebaut. Auf Windows war das
Saschas Ordner, im Container ist es `/srv/data/sarvis/home` — Sarvis'
eigenes Zuhause. Saschas `/home/server3070` steht aber als Ganzes in
`FREI_LESEN`. Damit galten seine `.ssh`, `.claude` und `.config` als
gewöhnlicher Teil der Freiliste.

## Gemessen (vorher → nachher, echte Funktionen im Container)

    auflisten_stufe('/home/server3070/.ssh')        frei   → fragen
    lesen_stufe('/home/server3070/.claude')         frei   → fragen
    befehl_stufe('tree /home/server3070/.config')   frei   → fragen
    befehl_stufe('ls ~/.ssh')                        frei   → fragen

Einzelne Dateien mit sprechendem Namen (`id_ed25519` unter `.ssh/`,
`.credentials.json`) fing schon `HEIKEL` ab; frei waren die Namenslisten
und alles ohne verräterischen Namen (Projekt-Gedächtnis unter
`.claude/projects`, Einstellungen unter `.config`).

## Behebung

Beide Benutzerordner — Saschas aus `PROJEKT_ORTE["privat"]` und der des
Prozesses — und dazu `.docker`, `.gnupg`, `.aws`, `.kube`, `.netrc`,
`.git-credentials`, `.bash_history`, `.claude.json`. Das ist „fragen“,
nicht „nie“: Sarvis darf dort weiter hin, nur nicht still.
