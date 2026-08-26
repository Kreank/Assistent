# Sarvis' Gedächtnis

Zwei Schichten, weil sie unterschiedlich teuer sind.

| | `kern.md` | `personen/`, `notizen/` |
|---|---|---|
| geladen | **immer**, bei jedem Zuruf | nur wenn Sarvis nachschlägt |
| kostet | Kontext bei *jeder* Frage | einen Werkzeugaufruf, wenn gebraucht |
| Inhalt | wenige, dauerhafte Fakten | alles Übrige |
| Größe | unter 60 Zeilen | beliebig |

Alles ist Markdown und von Hand lesbar. Das ist Absicht: Bei einem
Assistenten, der Mails verschickt, musst du nachlesen können, was er
über dich zu wissen glaubt — und es korrigieren, ohne zu fragen.

## Regeln, die das Ding gesund halten

**Datiert schreiben.** Jeder Eintrag bekommt das Datum, an dem er
gelernt wurde. Ohne Datum weiß später niemand, ob eine Information von
gestern oder von vorletztem Jahr ist.

**Vergängliches mit Ablauf.** „Ich bin nächste Woche in Hamburg" ist in
drei Wochen falsch. Solche Einträge tragen `(gilt bis TT.MM.JJJJ)` und
verschwinden danach. Hieran sterben die meisten Gedächtnisse: Sie
sammeln, aber sie vergessen nie.

**Ändern statt anhängen.** Widerspricht etwas Neues dem Alten, wird das
Alte ersetzt. Zwei widersprüchliche Einträge sind schlimmer als keiner.

**Nur was gesagt wurde.** Sarvis schreibt sich nur Dinge auf, um die du
ihn ausdrücklich bittest — nicht, was er aus dem Gespräch schließt.
Erschlossene Fakten sind der schnellste Weg zu einem Assistenten, der
selbstsicher Falsches über dich glaubt.

## Womit Sarvis das bedient

| Werkzeug | schreibt wohin | Schicht |
|---|---|---|
| `merken` | `gemerkt.md` / `beobachtet.md` | **1** — immer geladen |
| `person_merken` | `personen/<name>.md` | 2 — nur auf Nachfrage |
| `notiz_schreiben` | `notizen/JJJJ-MM-TT-*.md` | 2 |
| `gedaechtnis_zeigen` | liest Schicht 1 vor | |
| `gedaechtnis_nachschlagen` | durchsucht Schicht 2 | |

Die Zuordnung trifft Sarvis beim Merken selbst, angeleitet durch die
Werkzeugbeschreibungen: Dauerhaftes über *dich* nach Schicht 1, alles
über *andere Menschen* in deren Akte, *Ereignisse und Zwischenstände*
in eine datierte Notiz. Er kann dabei danebengreifen — deshalb ist
alles lesbarer Text, den du selbst verschieben kannst.

## Die Grenze

Schicht 1 trägt höchstens `GEDAECHTNIS_MAX_EINTRAEGE` Einträge je Datei
(Vorgabe 60, in `config.py`). Was darüber hinausgeht, wandert **nicht in
den Müll**, sondern als ältester Eintrag zuerst in eine monatliche
Sammeldatei unter `notizen/` — auffindbar über
`gedaechtnis_nachschlagen`, aber nicht mehr an jedem Zuruf hängend.

Der Grund ist nicht der Preis: Der Systemprompt wird zwischengespeichert
und kostet ab dem zweiten Zuruf fast nichts. Der Grund ist, dass in
einem Gedächtnis, in dem alles gleich laut ist, nichts mehr gefunden
wird.

## Aufbau

```
gedaechtnis/
  kern.md              immer geladen — kurz halten
  personen/<name>.md   eine Datei je Mensch
  notizen/JJJJ-MM-TT-*.md   Episodisches, datiert
```
