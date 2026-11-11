# 057 — "X ist gestartet" wird gesagt und ins Gedaechtnis geschrieben, ohne dass irgendetwas geprueft wurde

Status: gegenstandslos (programm_starten braucht PowerShell, die es auf dem Server nicht gibt; Fix b217416 steht im Code)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | falsche-annahme |
| **Bereich** | werkzeuge |
| **Fundstelle** | `sarvis/werkzeuge/programme.py:187` |
| **Status** | behoben |

## Was ist falsch

Popen startet nur die Huelle (powershell.exe bzw. explorer.exe) und kehrt sofort zurueck. Ob Start-Process das Programm wirklich gestartet hat oder ob die AppUserModelID noch existiert, wird nie ermittelt. Der except-Zweig in Zeile 191 greift nur, wenn schon powershell.exe/explorer.exe selbst nicht startbar ist; seine Meldung 'liess sich nicht starten' suggeriert aber, dass Startfehler erkannt wuerden.

## Ablauf

Verschwindet ein Programm zwischen dem einmaligen Listenabruf und dem Start (Deinstallation im laufenden Sarvis-Betrieb, geaenderte AppUserModelID nach einem Store-Update), kehrt explorer.exe shell:AppsFolder\<alte-ID> trotzdem mit Erfolg zurueck. Sarvis sagt 'Spotify ist gestartet.' und schreibt 'programm_starten: Spotify wurde gestartet.' ins Protokoll -- eine Tatsachenbehauptung ohne Grundlage, die spaeter als Gedaechtnis wieder auftaucht.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Technisch richtig beschrieben, aber deutlich harmloser als gemeldet -- herabgestuft von 'mittel' auf 'niedrig'. Bestaetigt: Zeile 187-190 verwendet Popen ohne wait/returncode, und in der ganzen Datei gibt es danach keine Pruefung mehr; Zeile 197 und 202 behaupten den Erfolg. Entlastend: 'ziel' stammt aus Get-StartApps, das im selben Lauf live von Windows geholt wurde (Zeile 32-50) -- der beschriebene Fall verlangt, dass die App zwischen Listenabruf und Start verschwindet, was innerhalb eines Sarvis-Laufs selten ist. Fuer den AppsFolder-Zweig (Zeile 185-186) ist eine Erfolgspruefung ausserdem gar nicht moeglich: explorer.exe meldet dort grundsaetzlich Erfolg, unabhaengig davon, ob die ID noch gilt. Ein vollstaendiger Fix existiert also nicht, nur eine Teilverbesserung.

## Vorgeschlagene Behebung

Im _IST_PFAD-Zweig (Zeile 180-182) subprocess.run statt Popen verwenden (mit capture_output=True, timeout=15) und bei returncode != 0 den stderr-Text als Fehler zurueckgeben -- dort ist der Startfehler tatsaechlich sichtbar. Fuer den AppsFolder-Zweig, wo das nicht geht, die Aussage ehrlich halten: Zeile 202 'Ich habe {name} angestossen.' statt '{name} ist gestartet.' und Zeile 197 entsprechend 'programm_starten: {name} wurde angestossen.', damit im Protokoll keine ungepruefte Tatsache landet.

## Behebung

Im `_IST_PFAD`-Zweig läuft der Start jetzt über `subprocess.run(..., capture_output=True, timeout=15)`; bei `returncode != 0` kommt die erste stderr-Zeile als Fehler zurück, und ins Protokoll wird nichts geschrieben. Für den AppsFolder-Zweig, wo explorer.exe grundsätzlich Erfolg meldet, bleibt es bei Popen, aber ohne Erfolgsbehauptung: gesagt wird "Ich habe {name} angestoßen.", vermerkt "{name} wurde angestoßen (ob es hochkommt, ist nicht geprüft)." Ein Zeitablauf des Startbefehls meldet ausdrücklich, dass der Ausgang unbekannt ist. Belegt mit einem Skript, das den echten Werkzeug-Handler mit ausgetauschtem `subprocess` und einer Attrappen-Programmliste ausführt — es wurde dabei kein Prozess gestartet.
