# 022 — Glob umgeht die Rueckfrage fuer D:\Strato Server -- der Pfad steht in `pattern`, geprueft wird nur `path`

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | falsche-annahme |
| **Bereich** | hirn |
| **Fundstelle** | `sarvis/hirn.py:156` |
| **Status** | behoben |

## Was ist falsch

_pfadstufe holt den Pfad in hirn.py:148 ausschliesslich aus `file_path` bzw. `path`. Glob traegt sein Ziel aber im Pflichtfeld `pattern`; `path` ist optional. Wird nur ein absolutes Muster uebergeben, ist `pfad` leer, schutz.auflisten_stufe("") liefert "frei" (schutz.py:139-140), und darf_ich() genehmigt in Zeile 191-192 still. Derselbe Weg steht offen, wenn `path` gesetzt, aber weit ist: auflisten_stufe prueft nur die Wurzel, waehrend das Muster darunter rekursiv laeuft. (Die Zeilennummern der Meldung waren um zwei verschoben -- die pfad-Zeile ist 148, der Glob-Zweig 156-158.)

## Ablauf

Sarvis ruft Glob mit {"pattern": "D:/Strato Server/**/*"} auf, ohne `path` zu setzen. Zeile 148 liefert pfad = "", Zeile 157 ruft schutz.auflisten_stufe("") -- dort steht `if not pfad: return "frei"`. darf_ich() trifft Zeile 191 und gibt PermissionResultAllow() zurueck. Die Dateinamen des Passwortordners gehen ans Modell, ohne dass eine Rueckfrage gestellt oder etwas ausgegeben wird. Zweiter Weg, unabhaengig davon, ob die SDK absolute Muster ohne `path` annimmt: Glob(path="D:/", pattern="**/*") -- auflisten_stufe("D:/") ist weder NIE noch _unter(FRAGEN_TROTZ_FREI), gibt also "frei", und das Muster laeuft trotzdem durch D:/Strato Server.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Widerlegungsversuche, die alle nicht tragen: (1) 'Glob ist gar nicht erreichbar' -- doch: config.WERKZEUG_STUFEN fuehrt "Glob": "pfad" (config.py:625), es steht NICHT in disallowed_tools (nur NotebookEdit, hirn.py:104) und faellt bei permission_mode="default" in can_use_tool. (2) 'Es ist vorab genehmigt, also egal' -- nein, EINGEBAUTE_WERKZEUGE enthaelt nur ["WebSearch"] (config.py:642-644), Glob laeuft also wirklich durch darf_ich. (3) 'Das Muster wird woanders geprueft' -- `pattern` wird in _pfadstufe nur beim Grep-Zweig und dort nur als Anzeigetext "muster" durchgereicht (hirn.py:166-167); schutz.py kennt fuer Pfade keinen Musterpfad. Die Absicherung, die es fuer Befehle gibt (_heikler_ort_erwaehnt, schutz.py:228-243, ausdruecklich gegen genau diese Luecke bei 'dir D:\Strato Server' gebaut), wird von befehl_stufe gerufen, nicht von auflisten_stufe. (4) Der Kommentar in auflisten_stufe (schutz.py:143-146: 'Auch blosse Dateinamen verraten dort schon zu viel') belegt, dass die Rueckfrage hier gewollt ist -- es ist also kein Missverstaendnis des Reviewers, sondern eine Pruefung, die nicht ausloest. Schwere bleibt mittel und nicht hoch: Es lecken nur Dateinamen, der Inhalt faellt weiter auf lesen_stufe -> heikel()/FRAGEN_TROTZ_FREI -> "fragen", und das Modell muss den Ordner von sich aus ansteuern.

## Vorgeschlagene Behebung

Zwei Aenderungen. (a) In schutz.py eine oeffentliche Hilfe neben _heikler_ort_erwaehnt anlegen:

def heikler_ort_beruehrt(pfad: str, muster: str = "") -> bool:
    """Beruehrt ein Auflisten/Durchsuchen einen Ort aus FRAGEN_TROTZ_FREI?

    Zwei Wege dorthin: Der Ort steht im Muster selbst, oder das Muster
    laeuft rekursiv unter einer Wurzel, die ihn enthaelt.
    """
    if _heikler_ort_erwaehnt(f"{pfad} {muster}"):
        return True
    if "**" not in str(muster or "") or not pfad:
        return False
    try:
        p = Path(pfad).resolve()
    except (OSError, ValueError):
        return False
    for w in config.FRAGEN_TROTZ_FREI:
        try:
            w = Path(w).resolve()
        except (OSError, ValueError):
            continue
        if p == w or p in w.parents:
            return True
    return False

(b) hirn.py:156-158 ersetzen durch:

        if werkzeug == "Glob":
            muster = str(e.get("pattern") or "")
            ziel = pfad or muster
            stufe = schutz.auflisten_stufe(ziel)
            if stufe == "frei" and schutz.heikler_ort_beruehrt(pfad, muster):
                stufe = "fragen"
            return stufe, "ordner_ansehen", {"pfad": ziel}

Damit trifft der erste Weg ueber auflisten_stufe(muster) direkt und der zweite ueber die neue Pruefung. Achtung beim Umsetzen: schutz.py steht in NIE_SCHREIBEN (schutz.py:63-66) -- Sarvis selbst darf die Datei nicht aendern, ein Mensch schon.

## Behebung

`schutz.heikler_ort_beruehrt(pfad, muster)` (schutz.py:275-300) prüft beide Wege — Ort im Muster, oder rekursives Muster unter einer Wurzel, die den Ort enthält — und der Glob-Zweig in `hirn._pfadstufe` nimmt jetzt `pattern` als Ziel, wenn `path` fehlt, und stuft ein sonst freies Ergebnis darüber hoch (hirn.py:156-168). Belegt am echten Modul: `_pfadstufe('Glob', {'pattern': 'D:/Strato Server/**/*'})` und `{'path':'D:/','pattern':'**/*'}` lieferten vorher `frei`, jetzt `fragen`; `{'path':'D:/Privat/Sarvis','pattern':'**/*.py'}` und `{'pattern':'*.py'}` bleiben `frei`. Als Beifang trifft es über die erweiterte Ortsprüfung auch die Git-Bash-Form `/d/Strato Server/**/*`.
