# 020 — Die einzige harte Sperre gilt nicht für die Shell

Status: erledigt (Commit b217416; Umwege über Symlink/./ seit 55db580, rekursives rm auf Wurzelorte seit 44e5fc2)

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | falsche-annahme |
| **Bereich** | entscheidungen |
| **Fundstelle** | `sarvis/schutz.py:243` |
| **Status** | behoben |

## Was ist falsch

befehl_stufe() zieht NIE_SCHREIBEN und NIE_LESEN nirgends heran — geprüft werden nur NIE_BEFEHL (Zeile 245), der heikle Ort (Zeile 247) und die Schau-Listen. Alles Übrige endet bei "fragen" (Zeile 279). Damit lässt sich die Sperre, die laut Kommentar (Zeile 41-62) gerade NICHT durch ein gesprochenes Ja aufhebbar sein soll, mit genau einem gesprochenen Ja aufheben.

## Ablauf

Nachgemessen: schreiben_stufe('D:/Privat/Sarvis/sarvis/schutz.py') -> "nie", aber befehl_stufe('Set-Content D:/Privat/Sarvis/sarvis/schutz.py -Value x') -> "fragen". Dasselbe beim Lesen: lesen_stufe('D:/Privat/Sarvis/.env') -> "nie", befehl_stufe('Get-Content D:/Privat/Sarvis/.env') -> "fragen". Sarvis fragt dann — gemessen über schutz.absicht() — "in schutz.py im Ordner sarvis schreiben" bzw. ".env im Ordner Sarvis lesen"; ein Ja darauf ändert die Regeldatei, die das Fragen überhaupt vorschreibt. Verschärfend: läuft parallel eine Freigabe für befehl_ausfuehren in D:\Privat\Sarvis, entfällt sogar die Rückfrage (hirn.py:206-208).

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Widerlegungsversuche: (a) Vielleicht fängt NIE_BEFEHL das ab — nein, dort stehen nur format/shutdown/diskpart-artige Befehle, kein Set-Content (Zeile 73-85, gemessen). (b) Vielleicht landet der Befehl gar nicht bei befehl_stufe — doch: hirn._pfadstufe (hirn.py:143-146) leitet Bash und PowerShell dorthin. (c) Vielleicht ist "fragen" hier bewusst gewählt, weil die Rückfrage den Namen nennt — sie tut es (absicht() nennt schutz.py bzw. .env), aber der Modulkommentar sagt ausdrücklich, ein Ja auf diese Frage "waere keine Erlaubnis fuer eine Handlung, sondern die Abschaffung des Fragens". Der Fund stimmt. Schwere bleibt mittel: Es braucht eine ausdrückliche Zustimmung auf eine Frage, die das Ziel korrekt benennt — kein stiller Durchlauf, außer in Verbindung mit einer laufenden Befehlsfreigabe.

## Vorgeschlagene Behebung

In befehl_stufe direkt nach dem NIE_BEFEHL-Block (schutz.py:245-246) eine Pfadprüfung einziehen, mit derselben Pfadsammlung wie in Fund 2: for pfad in _pfade_im_befehl(befehl): if _passt(pfad, NIE_LESEN): return "nie" — NIE_LESEN sperrt Lesen wie Schreiben. Für NIE_SCHREIBEN nur bei verändernden Befehlen sperren, sonst wäre das bloße Lesen von config.py plötzlich "nie": if _passt(pfad, NIE_SCHREIBEN) and re.match(r"^(Set-Content|Add-Content|Out-File|Remove-Item|Move-Item|Rename-Item|Copy-Item|del|rm|mv|cp|ren|sed\\s+-i|tee)\\b", teil, re.IGNORECASE) für einen der Schritte aus _schritte(befehl): return "nie". Zusätzlich abdecken: Umleitungen ("> datei", ">> datei") gelten ebenfalls als verändernd.

## Behebung

`befehl_stufe` prüft jetzt vor allem Weiteren die Pfade jedes Kettengliedes gegen die harten Sperren (schutz.py:331-347): `NIE_LESEN` sperrt jeden Zugriff, `NIE_SCHREIBEN` nur im verändernden Schritt (`_VERAENDERND`, schutz.py:302-310), damit das blosse Anzeigen von config.py nicht plötzlich "nie" wird. Umleitungen zählen als Schreiben und werden über ihr Ziel geprüft (`_umleitungsziele`, schutz.py:312-321) — `echo x > …\sarvis\hirn.py` lief vorher sogar auf "frei" durch, weil `echo` in NUR_SCHAUEN steht. Gemessen: `Set-Content …/sarvis/schutz.py -Value x` und `Get-Content …/Sarvis/.env` (auch als `cat /d/Privat/Sarvis/.env`) waren "fragen" bzw. "frei" und sind jetzt "nie"; ein Abgleich über 37 Alltagsbefehle gegen die Fassung aus HEAD zeigt ausser den beabsichtigten keine einzige geänderte Stufe.
