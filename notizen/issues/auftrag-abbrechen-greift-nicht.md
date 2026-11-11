# Auftrag abbrechen greift nicht — BEHOBEN 2. September 2026

Status: erledigt (Commit 5754c30)

**Gefunden:** 1. September 2026, abends
**Schwere:** hoch — ein Auftrag, den der Nutzer abbricht, läuft weiter

## Beobachtung

Auftrag 1 im Projekt `lokale-llms-recherche` wurde zweimal über
`auftrag_abbrechen` gestoppt. Beide Male kam die Rückmeldung:

> Auftrag 1 abgebrochen. Der Zweig sarvis/1-recherchiere-im-web-die-aktu bleibt.

Ein anschließendes `auftrag_status` zeigte den Auftrag jedoch weiterhin als
**laufend**:

> Auftrag 1 im Projekt lokale-llms-recherche läuft seit 6 Minuten, auf dem
> Zweig sarvis/1-recherchiere-im-web-die-aktu. Stand im Projekt: noch kein
> Commit; 1 Dateien ungespeichert geändert.

Auch die Anzeige beim Nutzer zeigte den Auftrag weiter als aktiv. Der
Nutzer hat es bemerkt, nicht Sarvis.

## Das Problem in einem Satz

`auftrag_abbrechen` meldet Erfolg, ohne ihn geprüft zu haben.

## Zwei Fehler, die zu trennen sind

1. **Der Abbruch selbst wirkt nicht.** Der Prozess läuft weiter. Zu klären:
   Wird überhaupt ein Signal geschickt, kommt es an, und fängt der Arbeiter
   es ab, ohne sich zu beenden?
2. **Die Rückmeldung lügt.** Selbst wenn der Abbruch dauert, darf das
   Werkzeug nicht „abgebrochen" melden, ohne nachzusehen. Es muss nach dem
   Signal kurz warten und den Status wirklich nachlesen. Steht der Auftrag
   dann noch, gehört das gesagt — mit dem Hinweis, dass härter nachgefasst
   wird.

## Nebenbefund: der Start meldete falsch

Derselbe Auftrag hatte beim Anlegen zunächst `no running event loop`
zurückgegeben und danach zweimal eine Ablehnungsmeldung — **gestartet ist
er trotzdem**. Sarvis ging deshalb davon aus, dass kein Auftrag läuft, und
hat die Recherche selbst erledigt. Ergebnis: doppelte Arbeit und ein
unbemerkter Hintergrundprozess.

Start und Abbruch haben also denselben Grundfehler: Die Rückmeldung
beschreibt nicht, was tatsächlich geschehen ist.

## Vorschlag

- `auftrag_geben`: Nach dem Start den Status nachlesen und die tatsächlich
  vergebene Auftragsnummer zurückgeben. Bei einer Fehlermeldung prüfen, ob
  trotzdem etwas läuft, bevor „nicht gestartet" gemeldet wird.
- `auftrag_abbrechen`: Signal schicken, kurz warten, Status nachlesen.
  Erst dann melden. Läuft der Auftrag weiter, härter nachfassen und das
  Ergebnis ehrlich zurückgeben.
- Beide Werkzeuge sollen nie einen Zustand behaupten, den sie nicht
  gelesen haben.

## Noch offen

Auftrag 1 lief zum Zeitpunkt dieser Notiz weiter. Der Zweig
`sarvis/1-recherchiere-im-web-die-aktu` im Projekt
`lokale-llms-recherche` steht, mit einer ungespeicherten Änderung und
ohne Commit. Vor dem Aufräumen nachsehen, ob der Prozess noch lebt.


---

## Befund: eine Ursache für alle drei Beobachtungen

`Werkstatt.starten()` endete mit

```python
auftrag.aufgabe = asyncio.get_running_loop().create_task(self._arbeiten(auftrag))
```

und wurde von `auftrag_geben` über `asyncio.to_thread` gerufen — also in
einem Worker-Thread. Dort gibt es keinen laufenden Event-Loop:
`get_running_loop()` warf **`no running event loop`**. Genau die
Meldung, die beim Start kam.

Der Auftrag war zu diesem Zeitpunkt aber schon eingetragen, ins Journal
geschrieben und mit Status `läuft` gesichert. Daraus folgte alles Übrige:

- `auftrag_status` meldete „läuft seit 6 Minuten" — es lief nichts.
- `auftrag_abbrechen` fand `aufgabe = None`, übersprang das Abbrechen
  und meldete trotzdem Erfolg.
- Der Status blieb `läuft`, also sah der nächste Blick wieder „läuft".

**Bestätigt in den Daten:** In `auftraege.json` steht bei Auftrag 1
`"status": "läuft"` bei `"zuletzt_gesehen": ""` — er hat nie ein
einziges Lebenszeichen gegeben.

Die Vermutung „der Prozess läuft weiter" war also falsch. Es lief nie
einer. Was im Projektordner liegt (`recherche/`), stammt von Sarvis
selbst, der die Recherche daraufhin von Hand erledigt hat.

## Was geändert wurde

1. **Die Ursache.** `starten()` legt den Auftrag nur noch an;
   angeworfen wird er von `losschicken()`, das im Event-Loop läuft.
   `fortsetzen()` hatte denselben Fehler und geht denselben Weg.
   Schlägt das Anwerfen fehl, steht der Auftrag auf `fehler` statt
   fälschlich auf `läuft`.
2. **Der Abbruch sieht nach.** Neu `Werkstatt.abbrechen()`: Signal
   schicken, bis zu `AUFTRAG_ABBRUCH_FRIST_SEK` warten, Zustand lesen,
   dann erst melden. Reagiert der Auftrag nicht, wird das als Fehler
   zurückgegeben — nicht als Erfolg.
3. **Der Sonderfall wird benannt.** War nie ein Arbeiter da, sagt er
   das ausdrücklich, statt einen Abbruch zu behaupten, den es nicht gab.

## Geprüft

Gegen die echte `Werkstatt` mit einem echten Git-Projekt, `starten()`
wie im Betrieb über `to_thread`:

| Fall | Ergebnis |
|---|---|
| Start im Worker-Thread | kein Fehler mehr, Arbeiter läuft wirklich an |
| Abbruch eines laufenden Auftrags | gestoppt, Status `abgebrochen`, nicht mehr als laufend gelistet |
| Eintrag ohne Arbeiter (der Fall vom 1. 9.) | wird berichtigt und ausdrücklich benannt |
| Arbeiter ignoriert den Abbruch | wird als Fehler gemeldet, Status bleibt ehrlich `läuft` |

## Altbestand

Auftrag 1 steht beim nächsten Start automatisch auf `unterbrochen`
(`_aus_journal` setzt hängengebliebene `läuft`-Einträge um). Der Zweig
`sarvis/1-recherchiere-im-web-die-aktu` bleibt mit dem ungespeicherten
Ordner `recherche/` stehen — der kann weg, sobald Sascha ihn nicht mehr
braucht.
