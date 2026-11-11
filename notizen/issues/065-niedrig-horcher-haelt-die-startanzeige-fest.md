# 065 — Der Horcher hielt die Anzeige vom Start fest

Status: erledigt (Commit 0fbb0fd)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | gemerkte Anzeige statt `anzeige.aktuelle()` |
| **Bereich** | sprachweg |
| **Fundstelle** | `sarvis/main.py` (Konstruktor, `Horcher(...)`) |
| **Herkunft** | Prüflauf 11.11.2026 |

## Was war falsch

Der Horcher wird im Konstruktor mit `anzeige=self.anzeige` gebaut, die
Netz-Anzeige entsteht erst in `_netz_aufbauen`. Im Netzbetrieb ist die
Startanzeige abgeschaltet — Pegel und „denkt“ bei langem Diktat
(`weckwort._pruefen`) gingen ins Leere; die App sah einen stillen Ring,
also genau das, was diese Meldungen verhindern sollen.

## Behebung

`anzeige=anzeige_modul.aktuelle()`, wie bei den Werkzeugen.

Spürbare Folge: Im Dauerhorchen schickt der Server jetzt seinen Pegel
(rund 33 Meldungen je Sekunde, wenige Byte) an die Oberflächen; die
Weboberfläche zeigt ihn, solange sie nicht selbst aufnimmt. Nicht in der
echten App angesehen.

`Hirn.anzeige` ist bewusst eine eigene UDP-Anzeige — nur für die Frage
„web_element“, beantwortet von `browser_kopf.rueckkanal_starten`, und
fällt ohne Antwort auf „fragen“. Kein Fund.
