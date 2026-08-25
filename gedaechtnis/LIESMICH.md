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

## Aufbau

```
gedaechtnis/
  kern.md              immer geladen — kurz halten
  personen/<name>.md   eine Datei je Mensch
  notizen/JJJJ-MM-TT-*.md   Episodisches, datiert
```
