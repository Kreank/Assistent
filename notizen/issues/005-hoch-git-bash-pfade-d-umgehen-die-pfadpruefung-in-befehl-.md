# 005 — Git-Bash-Pfade (/d/...) umgehen die Pfadprüfung in befehl_stufe

Status: gegenstandslos (Git-Bash-Schreibweise /d/... gibt es auf dem Server nicht, die Umdeutung läuft nur noch unter Windows; die Linux-Entsprechung — ~, $HOME, Symlinks — ist mit 55db580 geschlossen)

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | falsche-annahme |
| **Bereich** | entscheidungen |
| **Fundstelle** | `sarvis/schutz.py:274` |
| **Status** | behoben |

## Was ist falsch

befehl_stufe sucht Pfade nur in Laufwerksbuchstaben-Schreibweise (re.findall(r"[a-zA-Z]:[\\/]...")). Die Git-Bash-Form "/d/Strato Server" trifft weder diesen Regex noch _heikler_ort_erwaehnt (schutz.py:236-239 vergleicht als Teilstring gegen "d:/strato server"). Der Schleifenrumpf läuft dann nie, und die Funktion fällt auf "frei" durch. freigabe._pfad_im_befehl (freigabe.py:54-56) behandelt genau diese Schreibweise ausdrücklich — mit demselben Schadensbild im Docstring; in schutz.py fehlt die Entsprechung.

## Ablauf

Sarvis ruft das Bash-Werkzeug (unter Windows Git Bash) auf. Nachgemessen mit dem echten Modul: befehl_stufe('ls /d/Strato Server') -> "frei", ebenso 'ls "/d/Strato Server"', 'ls /d/Strato\\ Server' und 'tree /d/Strato Server'. hirn.darf_ich (hirn.py:191-192) macht daraus PermissionResultAllow — der Passwortordner wird ohne Rückfrage aufgelistet, obwohl auflisten_stufe ihn wegen FRAGEN_TROTZ_FREI korrekt auf "fragen" setzt ("welche Zugaenge es ueberhaupt gibt, ist selbst eine Auskunft", schutz.py:145-148). Auch Inhalte sind erreichbar: befehl_stufe('echo $(cat "/d/Strato Server/pw.txt")') -> "frei", weil echo in NUR_SCHAUEN steht und der Pfad nicht gefunden wird; dieselbe Zeile mit "D:/Strato Server" -> "fragen". Zur Korrektur am Ursprungsfund: die dort genannten Beispiele 'grep -r ... /d/Strato Server' und 'cat /d/Strato Server/pw.txt' ergeben gemessen "fragen" (grep und cat stehen nicht in NUR_SCHAUEN); 'Select-String -Path /d/Strato Server/*' ergibt zwar "frei", würde aber in PowerShell den Pfad gar nicht auf D:\Strato Server auflösen. Der Schutz hängt trotzdem allein an der Schreibweise.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Ich habe nach einem Auffangnetz gesucht: (a) _heikler_ort_erwaehnt — vergleicht nur die Windows-Form, greift bei /d/ nicht (gemessen); (b) NUR_SCHAUEN als Begrenzung — bremst zwar cat und grep aus, lässt aber ls, dir, tree, git und echo durch, und echo mit Kommandosubstitution liest Inhalte; (c) die Freigabenprüfung in hirn.darf_ich wird gar nicht erreicht, weil bereits "frei" zurückkommt (hirn.py:191). Kein Aufrufer fängt den Fall ab. Bestätigt; nur der behauptete Ablauf war teils falsch und ist oben korrigiert.

## Vorgeschlagene Behebung

In schutz.py eine gemeinsame Pfadsammlung einführen und an beiden Stellen benutzen: def _pfade_im_befehl(b): treffer = re.findall(r"[a-zA-Z]:[\\/][^\s\"']*", b); treffer += [f"{lw.upper()}:/{rest}" for lw, rest in re.findall(r"(?<![\w/])/([a-zA-Z])/([^\s\"']*)", b)]; return treffer. Diese Funktion in Zeile 274 statt des re.findall verwenden. Zusätzlich _heikler_ort_erwaehnt (Zeile 236-239) um die Git-Bash-Form erweitern: neben "d:/strato server" auch "/d/strato server" bilden (wurzel.drive.rstrip(':').lower() -> f"/{lw}/{rest}") und beide Formen gegen t prüfen. Damit fällt sowohl ls als auch echo $(cat ...) wieder auf "fragen".

## Behebung

`schutz.pfade_im_befehl()` (schutz.py:227-246) sammelt beide Schreibweisen und ersetzt das `re.findall` in `befehl_stufe` (schutz.py:372). `_heikler_ort_erwaehnt` vergleicht jetzt zusätzlich die Git-Bash-Form (`d:/strato server` UND `/d/strato server`) und macht vorher den Bash-Schutzstrich vor dem Leerzeichen rückgängig, sonst wäre aus `Strato\ Server` ein `Strato/ Server` geworden (schutz.py:248-273). Gemessen: `ls /d/Strato Server`, `ls "/d/Strato Server"`, `ls /d/Strato\ Server`, `tree /d/Strato Server` und `echo $(cat "/d/Strato Server/pw.txt")` lieferten vorher alle `frei`, jetzt alle `fragen`; `Get-ChildItem D:/Privat` bleibt `frei`.
