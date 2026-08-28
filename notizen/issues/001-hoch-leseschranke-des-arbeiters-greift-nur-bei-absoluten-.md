# 001 — Leseschranke des Arbeiters greift nur bei absoluten Pfaden

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | filter-zu-streng |
| **Bereich** | auftraege |
| **Fundstelle** | `sarvis/werkzeuge/auftrag.py:392` |
| **Status** | behoben |

## Was ist falsch

Im Lese-Zweig des Wachhunds (Read/Glob/Grep) wird die Ordnergrenze nur geprueft, wenn der Pfad absolut ist. Jeder relative Pfad kommt ungeprueft durch, obwohl innerhalb() relative Pfade korrekt gegen die Wurzel aufloesen wuerde (Zeile 363: 'p = p if p.is_absolute() else (wurzel / p)'). Im Write/Edit-Zweig (Zeile 386-389) wird genau diese Aufloesung benutzt, im Lese-Zweig nicht. Der Kommentar darueber (Zeile 383-387) begruendet die Sperre ausdruecklich damit, dass der Arbeiter sonst die .env mit den Telegram-Zugangsdaten oeffnen koennte.

## Ablauf

Der Arbeiter laeuft mit cwd = Projektordner (Zeile 495: cwd=str(auftrag.ordner)). Ruft er Grep mit path='../..' oder Glob mit pattern='../../**/.env' auf, ist is_absolute() False, die Bedingung faellt komplett aus und es wird PermissionResultAllow() zurueckgegeben. Der Inhalt landet im Kontext des Arbeiters und geht damit nach draussen. Fuer Read verlangt das Werkzeug selbst einen absoluten Pfad, die Luecke traegt also vor allem ueber Grep(path=...) und Glob(pattern=/path=...) -- und ueber Unter-Arbeiter, die laut Kommentar Zeile 51-56 durch dieselbe Pruefung laufen. Eine Erlaubnis erzeugt keine Meldung, Nutzer und Sarvis sehen davon nichts.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Bestaetigt, kein Gegenbeweis gefunden. Die einzige Schranke ist can_use_tool: Zeile 496-500 setzt allowed_tools=[], permission_mode='default', setting_sources=[], mcp_servers={} -- es gibt keine zweite Ebene, die den Pfad noch einmal prueft. Zeile 392-393 lautet woertlich 'if ziel and Path(str(ziel)).is_absolute() and not innerhalb(str(ziel))'. Der Write-Zweig daneben (Zeile 387) kommt ohne is_absolute() aus und beweist damit, dass die Aufloesung ueber innerhalb() gewollt und funktionsfaehig ist. Das SDK selbst konnte ich nicht einsehen (claude_agent_sdk ist in dieser Umgebung nicht installiert), an der Auswertung der Bedingung aendert das aber nichts. Einstufung 'hoch' bleibt: Es geht um die Freigabegrenze eines fremdgesteuerten Agenten.

## Vorgeschlagene Behebung

Zeile 392-393 auf denselben Weg bringen wie den Write-Zweig: 'if ziel and not innerhalb(str(ziel)):'. Relative Muster wie '**/*.py' loesen dann zu wurzel/'**/*.py' auf und bleiben erlaubt, '../..' wird abgelehnt. Zusaetzlich sollten die uebrigen Pfadfelder mitgeprueft werden, die diese Werkzeuge kennen (Grep: 'path' UND 'glob'; Glob: 'path' UND 'pattern') -- derzeit gewinnt in der or-Kette immer das erste gesetzte Feld.

## Behebung

Der Lese-Zweig in `_wachhund` prüft nicht mehr auf `is_absolute()`, sondern übergibt jedes Ortsfeld direkt an `innerhalb()` — das löst relative Pfade seit jeher gegen die Projektwurzel auf, genau wie der Schreib-Zweig daneben. Statt der `or`-Kette wird jetzt pro Werkzeug jedes Ortsfeld einzeln geprüft (Read: `file_path`, `path`; Glob: `path`, `pattern`; Grep: `path`, `glob` — `pattern` ist bei Grep ein Regex und kein Ort), damit ein harmloses `path="."` kein `glob="../../**"` mehr zudeckt. Belegt mit `pruef_001.py` im Scratchpad: `Grep(path="../..")`, `Glob(pattern="../../**/.env")` und `Grep(path=".", glob="../../**/*.env")` liefern vorher alle `Allow`, nachher alle `Deny`, während `Glob(pattern="**/*.py")`, `Grep(path="sarvis")`, `Grep(glob="*.{py,md}")`, ein absoluter Pfad im Projekt und Grep ganz ohne Ortsangabe weiterhin `Allow` bekommen.
