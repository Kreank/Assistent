# Fehlerberichte — Stand 11.11.2026

Alle Berichte in diesem Ordner gegen den Code geprüft, der seit dem
30.08.2026 als Container `sarvis` auf dem Server läuft (Branch `server`).
Geprüft wurde am Code und, wo es um die Bremse geht, an den echten
Funktionen im laufenden Container — nicht an den Berichten.

Im Ordner liegen 61 Dateien: 59 nummerierte Berichte, der Einzelbericht
`auftrag-abbrechen-greift-nicht.md` und die alte `UEBERSICHT.md` vom
Review. Bewertet sind also **60 Berichte**.

| Einordnung | Anzahl | Nummern |
|---|---|---|
| erledigt | 48 | 001, 002, 003, 004, 006, 007, 008, 009, 011, 012, 013, 014, 015, 016, 017, 018, 019, 020, 021, 022, 023, 027, 031, 032, 033, 034, 035, 036, 037, 038, 039, 040, 041, 042, 043, 044, 045, 046, 047, 048, 049, 050, 053, 054, 056, 058, 059, auftrag-abbrechen |
| gegenstandslos | 12 | 005, 010, 024, 025, 026, 028, 029, 030, 051, 052, 055, 057 |
| offen | 0 | — |

**Erledigt** heißt: Die Behebung aus dem Bericht steht im heutigen Code
(fast alle aus Commit b217416 vom 28.08.2026). **Gegenstandslos** heißt:
Der betroffene Weg läuft auf dem Server nicht (Qt-HUD, lokaler
Lautsprecher, PowerShell, Git-Bash) — die Behebung steht trotzdem im
Code — oder es wurde bewusst so entschieden (055).

Wichtig dabei: Mehrere Sicherheitsfixes von damals (003, 004, 020, 022,
027) standen zwar im Code, griffen auf Linux aber nur halb, weil die
Ortslisten im Container auf das falsche Home zeigten oder Linux-
Schreibweisen nicht erkannt wurden. Das ist heute nachgezogen —
siehe die neuen Funde unten.

## Die 60 Berichte

| Nr | Schwere | Titel | Status |
|---|---|---|---|
| 001 | hoch | [Leseschranke des Arbeiters greift nur bei absoluten Pfaden](001-hoch-leseschranke-des-arbeiters-greift-nur-bei-absoluten-.md) | erledigt (Commit b217416; Bash-Zweig auf Linux seit d3ac2b2, ~/$HOME/cd/.. seit 55db580) |
| 002 | hoch | [auftrag_fortsetzen ruft ein blinken(), das es in dieser Datei nicht gibt](002-hoch-auftrag-fortsetzen-ruft-ein-blinken-das-es-in-dieser.md) | erledigt (Commit b217416) |
| 003 | hoch | [Freigabe für "Ordner durchsuchen" ist ortlos — und ortlos heißt überall](003-hoch-freigabe-fuer-ordner-durchsuchen-ist-ortlos-und-ortl.md) | erledigt (Commit b217416) |
| 004 | hoch | [Befehls-Freigabe prüft nur den ERSTEN Pfad einer Kette](004-hoch-befehls-freigabe-prueft-nur-den-ersten-pfad-einer-ke.md) | erledigt (Commit b217416; POSIX-Pfade seit d3ac2b2, ~/$HOME seit 55db580) |
| 005 | hoch | [Git-Bash-Pfade (/d/...) umgehen die Pfadprüfung in befehl_stufe](005-hoch-git-bash-pfade-d-umgehen-die-pfadpruefung-in-befehl-.md) | gegenstandslos (Git-Bash-Schreibweise /d/... gibt es auf dem Server nicht, die Umdeutung läuft nur noch unter Windows; die Linux-Entsprechung — ~, $HOME, Symlinks — ist mit 55db580 geschlossen) |
| 006 | hoch | [Inhaltsprüfung hält jede UTF-16-Datei für binär und liest sie still](006-hoch-inhaltspruefung-haelt-jede-utf-16-datei-fuer-binaer-.md) | erledigt (Commit b217416) |
| 007 | hoch | [Wartesatz und Werkzeug-Leuchten sind unerreichbar -- der erste elif frisst genau den Fall, fuer den der zweite gebaut wurde](007-hoch-wartesatz-und-werkzeug-leuchten-sind-unerreichbar-de.md) | erledigt (Commit b217416) |
| 008 | hoch | [Vollstaendige URL wird auf die Startseite verkuerzt -- der Link geht verloren](008-hoch-vollstaendige-url-wird-auf-die-startseite-verkuerzt-.md) | erledigt (Commit b217416) |
| 009 | hoch | [projekt_anlegen mit art='web' bricht mitten im Anlegen ab und laesst eine halbe Projektruine zurueck](009-hoch-projekt-anlegen-mit-art-web-bricht-mitten-im-anlegen.md) | erledigt (Commit b217416) |
| 010 | mittel | [Untertitel wird bei rund 390 Zeichen stumm abgeschnitten -- und zwar hinten](010-mittel-untertitel-wird-bei-rund-390-zeichen-stumm-abgeschni.md) | gegenstandslos (Qt-HUD wird auf dem Server nicht gestartet; Fix b217416 steht im Code) |
| 011 | mittel | [stand() vergleicht gegen ein fest verdrahtetes main](011-mittel-stand-vergleicht-gegen-ein-fest-verdrahtetes-main.md) | erledigt (Commit b217416) |
| 012 | mittel | [Personensuche findet die Akte, liefert aber keine Inhalte](012-mittel-personensuche-findet-die-akte-liefert-aber-keine-inh.md) | erledigt (Commit b217416) |
| 013 | mittel | [Zwei gleichnamige Dateien: Drive waehlt still die zuletzt geaenderte -- auch beim Teilen](013-mittel-zwei-gleichnamige-dateien-drive-waehlt-still-die-zul.md) | erledigt (Commit b217416) |
| 014 | mittel | [Gemerkte Google-Dienste werden nie verworfen -- Neuanmeldung wirkt erst nach Neustart](014-mittel-gemerkte-google-dienste-werden-nie-verworfen-neuanme.md) | erledigt (Commit b217416; Rest RefreshError: das SDK meldet Ausnahmen eines Werkzeugs als Fehlerergebnis ans Modell, kein Absturz) |
| 015 | mittel | [aufgabe_anlegen verschluckt ein unverstandenes Faelligkeitsdatum und meldet Erfolg](015-mittel-aufgabe-anlegen-verschluckt-ein-unverstandenes-faell.md) | erledigt (Commit b217416) |
| 016 | mittel | [mail_lesen schneidet bei 4000 Zeichen ab, ohne es zu kennzeichnen](016-mittel-mail-lesen-schneidet-bei-4000-zeichen-ab-ohne-es-zu-.md) | erledigt (Commit b217416) |
| 017 | mittel | [aufgabe_anlegen und aufgabe_abhaken landen nicht im Protokoll](017-mittel-aufgabe-anlegen-und-aufgabe-abhaken-landen-nicht-im-.md) | erledigt (Commit b217416) |
| 018 | mittel | [telegram_senden verschickt bei EINEM schwachen Zufallstreffer ohne Rueckfrage](018-mittel-telegram-senden-verschickt-bei-einem-schwachen-zufal.md) | erledigt (Commit b217416) |
| 019 | mittel | [Fehlende Wortgrenze: das Wort "Termin" erzeugt eine Freigabe](019-mittel-fehlende-wortgrenze-das-wort-termin-erzeugt-eine-fre.md) | erledigt (Commit b217416) |
| 020 | mittel | [Die einzige harte Sperre gilt nicht für die Shell](020-mittel-die-einzige-harte-sperre-gilt-nicht-fuer-die-shell.md) | erledigt (Commit b217416; Umwege über Symlink/./ seit 55db580, rekursives rm auf Wurzelorte seit 44e5fc2) |
| 021 | mittel | [Gesprochenes "hoer auf" waehrend einer offenen Rueckfrage stoppt nichts](021-mittel-gesprochenes-hoer-auf-waehrend-einer-offenen-rueckfr.md) | erledigt (Commit b217416) |
| 022 | mittel | [Glob umgeht die Rueckfrage fuer D:\Strato Server -- der Pfad steht in `pattern`, geprueft wird nur `path`](022-mittel-glob-umgeht-die-rueckfrage-fuer-d-strato-server-der-.md) | erledigt (Commit b217416; auf Linux erst wirksam seit 55db580 — FRAGEN_TROTZ_FREI zeigte im Container auf das falsche Home) |
| 023 | mittel | [spricht(None) loescht den Echo-Filter, bevor das eigene Echo ueberhaupt geprueft wurde](023-mittel-spricht-none-loescht-den-echo-filter-bevor-das-eigen.md) | erledigt (Commit b217416) |
| 024 | mittel | [Leere Programmliste wird dauerhaft gemerkt -- danach behauptet Sarvis fuer immer, es gebe das Programm nicht](024-mittel-leere-programmliste-wird-dauerhaft-gemerkt-danach-be.md) | gegenstandslos (Get-StartApps/PowerShell gibt es auf dem Server nicht; Fix b217416 steht im Code) |
| 025 | mittel | [Der Kommentar verspricht 'nicht stillschweigend leer' -- genau das passiert bei jedem PowerShell-Fehler ohne Ausnahme](025-mittel-der-kommentar-verspricht-nicht-stillschweigend-leer-.md) | gegenstandslos (PowerShell gibt es auf dem Server nicht; Fix b217416 steht im Code) |
| 026 | mittel | [programm_beenden kann bei einem Namen ohne Wortzeichen ALLE Prozesse abschiessen](026-mittel-programm-beenden-kann-bei-einem-namen-ohne-wortzeich.md) | gegenstandslos (powershell.exe/Stop-Process gibt es auf dem Server nicht; Fix b217416 steht im Code) |
| 027 | mittel | [ort_ansehen laeuft still, prueft nur die Namens-Stufe -- liest aber Dateiinhalt vor](027-mittel-ort-ansehen-laeuft-still-prueft-nur-die-namens-stufe.md) | erledigt (Commit b217416; auf Linux erst wirksam seit 55db580) |
| 028 | niedrig | [Die Hintergrund-Ecke ist nicht frei: 'Finanzen' aus dem Kranz liegt darueber](028-niedrig-die-hintergrund-ecke-ist-nicht-frei-finanzen-aus-dem.md) | gegenstandslos (Qt-HUD wird auf dem Server nicht gestartet; Fix b217416 steht im Code) |
| 029 | niedrig | [Das Aufblenden ('hervor') hat mit der ausgelieferten Konfiguration keinerlei Wirkung](029-niedrig-das-aufblenden-hervor-hat-mit-der-ausgelieferten-kon.md) | gegenstandslos (Qt-HUD wird auf dem Server nicht gestartet; Fix b217416 steht im Code) |
| 030 | niedrig | [Der Mausgriff wird beim Loslassen nicht zurueckgesetzt](030-niedrig-der-mausgriff-wird-beim-loslassen-nicht-zurueckgeset.md) | gegenstandslos (Qt-HUD wird auf dem Server nicht gestartet; Fix b217416 steht im Code) |
| 031 | niedrig | [Der Phaser wandert nicht: der LFO wird auf einen einzigen Mittelwert eingedampft](031-niedrig-der-phaser-wandert-nicht-der-lfo-wird-auf-einen-einz.md) | erledigt (Commit b217416) |
| 032 | niedrig | [Unbekannter Farbname: die ganze Effektkette faellt still weg](032-niedrig-unbekannter-farbname-die-ganze-effektkette-faellt-st.md) | erledigt (Commit b217416; Rest — Startzeile in mund.py — mit 44e5fc2) |
| 033 | niedrig | [Die Abbruchmeldung eines Auftrags wird nie erreicht](033-niedrig-die-abbruchmeldung-eines-auftrags-wird-nie-erreicht.md) | erledigt (Commit b217416) |
| 034 | niedrig | [merken loescht bei kurzen Inhalten stumm fremde Eintraege](034-niedrig-merken-loescht-bei-kurzen-inhalten-stumm-fremde-eint.md) | erledigt (Commit b217416) |
| 035 | niedrig | [Freitextzeilen ohne fuehrenden Strich gehen beim naechsten Schreiben verloren](035-niedrig-freitextzeilen-ohne-fuehrenden-strich-gehen-beim-nae.md) | erledigt (Commit b217416) |
| 036 | niedrig | [Zerrissene timer.json loescht alle Timer ohne ein Wort](036-niedrig-zerrissene-timer-json-loescht-alle-timer-ohne-ein-wo.md) | erledigt (Commit b217416) |
| 037 | niedrig | [Timer-Dauern werden in Wanduhrzeit umgerechnet und ueberleben die Zeitumstellung nicht](037-niedrig-timer-dauern-werden-in-wanduhrzeit-umgerechnet-und-u.md) | erledigt (Commit b217416) |
| 038 | niedrig | [Beim Wiederherstellen genau der ungenaue Umweg, den stellen_bis verwirft](038-niedrig-beim-wiederherstellen-genau-der-ungenaue-umweg-den-s.md) | erledigt (Commit b217416) |
| 039 | niedrig | [termine_ansehen faellt bei unverstandenem Startdatum still auf heute zurueck](039-niedrig-termine-ansehen-faellt-bei-unverstandenem-startdatum.md) | erledigt (Commit b217416) |
| 040 | niedrig | [Aufgaben-Werkzeuge sehen nur die erste Aufgabenliste](040-niedrig-aufgaben-werkzeuge-sehen-nur-die-erste-aufgabenliste.md) | erledigt (Commit b217416) |
| 041 | niedrig | [tabelle_schreiben schreibt immer nur eine Zeile, meldet aber den ganzen Bereich als gesetzt](041-niedrig-tabelle-schreiben-schreibt-immer-nur-eine-zeile-meld.md) | erledigt (Commit b217416) |
| 042 | niedrig | [termine_ansehen deckelt bei 25 Terminen ohne Hinweis](042-niedrig-termine-ansehen-deckelt-bei-25-terminen-ohne-hinweis.md) | erledigt (Commit b217416) |
| 043 | niedrig | [telegram_lesen sagt "neueste zuerst" und liefert aelteste zuerst](043-niedrig-telegram-lesen-sagt-neueste-zuerst-und-liefert-aelte.md) | erledigt (Commit b217416) |
| 044 | niedrig | [Telegram-Verbindungen werden bei jedem Neuaufbau liegengelassen](044-niedrig-telegram-verbindungen-werden-bei-jedem-neuaufbau-lie.md) | erledigt (Commit b217416; schliessen() wird inzwischen beim Beenden in main.py gerufen) |
| 045 | niedrig | [telegram_lesen wirft Bild- und Sprachnachrichten still aus der Zaehlung](045-niedrig-telegram-lesen-wirft-bild-und-sprachnachrichten-stil.md) | erledigt (Commit b217416) |
| 046 | niedrig | [Anzeige zeigt die kürzeste Freigabe, zählt aber die längste herunter](046-niedrig-anzeige-zeigt-die-kuerzeste-freigabe-zaehlt-aber-die.md) | erledigt (Commit b217416) |
| 047 | niedrig | [Nach einem Abbruch bleibt der Horcher im Zustand "Sarvis spricht" haengen](047-niedrig-nach-einem-abbruch-bleibt-der-horcher-im-zustand-sar.md) | erledigt (Commit b217416) |
| 048 | niedrig | [Zu kurze Antwort auf eine Rueckfrage verschwindet ohne Konsolenzeile](048-niedrig-zu-kurze-antwort-auf-eine-rueckfrage-verschwindet-oh.md) | erledigt (Commit b217416) |
| 049 | niedrig | [Der Protokoll-Nachtrag wird VOR dem Leerlesen aufgenommen -- was waehrend des Abbruchs noch fertig wird, faellt still weg](049-niedrig-der-protokoll-nachtrag-wird-vor-dem-leerlesen-aufgen.md) | erledigt (Commit b217416) |
| 050 | niedrig | [Das Leerlesen nach dem Abbruch schluckt jeden Fehler und jeden Zeitablauf -- danach ist die naechste Antwort um eine Runde verschoben](050-niedrig-das-leerlesen-nach-dem-abbruch-schluckt-jeden-fehler.md) | erledigt (Commit b217416) |
| 051 | niedrig | [abbrechen() erwischt den Satz nicht, den der Abspielfaden schon aus der Schlange gezogen hat](051-niedrig-abbrechen-erwischt-den-satz-nicht-den-der-abspielfad.md) | gegenstandslos (audio.Lautsprecher läuft nur lokal, auf dem Server spricht der NetzLautsprecher; Fix b217416 steht im Code) |
| 052 | niedrig | [leer wird zwischen clear() und put() gesetzt -- warten() kehrt zurueck, obwohl noch ein Satz aussteht](052-niedrig-leer-wird-zwischen-clear-und-put-gesetzt-warten-kehr.md) | gegenstandslos (audio.Lautsprecher läuft nur lokal, auf dem Server spricht der NetzLautsprecher; Fix b217416 steht im Code) |
| 053 | niedrig | [Whisper laeuft im Mikrofon-Lesefaden; die Ueberlauf-Meldung von read() wird weggeworfen](053-niedrig-whisper-laeuft-im-mikrofon-lesefaden-die-ueberlauf-m.md) | erledigt (Commit b217416; Lesen und Verstehen laufen in getrennten Fäden) |
| 054 | niedrig | [Ein VAD-Fehler verschluckt den Block und kann den Horcher dauerhaft taub machen](054-niedrig-ein-vad-fehler-verschluckt-den-block-und-kann-den-ho.md) | erledigt (Commit b217416) |
| 055 | niedrig | [Die Mindestlaenge WECKWORT_MIN_SEK kann nie greifen -- der Nachlauf ist laenger als die Schwelle](055-niedrig-die-mindestlaenge-weckwort-min-sek-kann-nie-greifen-.md) | gegenstandslos (bewusst nicht geändert: ein verschlucktes „Ja“ wiegt schwerer als ein durchgelassenes Husten; Begründung steht bei WECKWORT_MIN_SEK in config.py) |
| 056 | niedrig | [Buchungen und Empfaenger werden hart auf sechs gekappt -- ohne jeden Hinweis, dass da mehr war](056-niedrig-buchungen-und-empfaenger-werden-hart-auf-sechs-gekap.md) | erledigt (Commit b217416) |
| 057 | niedrig | ["X ist gestartet" wird gesagt und ins Gedaechtnis geschrieben, ohne dass irgendetwas geprueft wurde](057-niedrig-x-ist-gestartet-wird-gesagt-und-ins-gedaechtnis-gesc.md) | gegenstandslos (programm_starten braucht PowerShell, die es auf dem Server nicht gibt; Fix b217416 steht im Code) |
| 058 | hoch | ["Ja, frag nicht mehr nach" galt als Einwand statt als Zustimmung](058-hoch-zustimmung-mit-freigabe-galt-als-einwand.md) | erledigt (Commit b217416) |
| 059 | mittel | [Der Not-Aus lässt den Satz durch, der gerade synthetisiert wird](059-mittel-not-aus-laesst-den-satz-in-arbeit-durch.md) | erledigt (Commit b217416) |
| — | hoch | [Auftrag abbrechen greift nicht — BEHOBEN 2. September 2026](auftrag-abbrechen-greift-nicht.md) | erledigt (Commit 5754c30) |

## Neu am 11.11.2026

Beim Prüfen gefunden, gegen den laufenden Container gemessen (vorher
und nachher) und behoben. Alle aus derselben Fehlerklasse: Annahmen aus
der Windows-Zeit, die auf Linux still ins Leere laufen.

| Nr | Schwere | Titel | Status |
|---|---|---|---|
| 060 | hoch | [Saschas Zugangsordner waren im Container „frei“: FRAGEN_TROTZ_FREI hing am falschen Home](060-hoch-zugangsordner-im-container-am-falschen-home.md) | erledigt (Commit 55db580) |
| 061 | hoch | [Die harte Sperre („nie“) war per Symlink, „/./“ oder „//“ zu umgehen](061-hoch-harte-sperre-per-symlink-umgehbar.md) | erledigt (Commit 55db580) |
| 062 | hoch | [~, $HOME, das nackte „cd“ und „..“ galten nicht als Pfad](062-hoch-tilde-home-und-cd-sind-keine-pfade.md) | erledigt (Commit 55db580) |
| 063 | mittel | [Eine Freigabe für einen Ordner deckte still die Zugangsorte darin](063-mittel-freigabe-fuer-ordner-deckte-zugangsorte.md) | erledigt (Commit 55db580) |
| 064 | hoch | [Rekursives Löschen der Wurzelorte war nur „fragen“](064-hoch-rekursives-loeschen-der-wurzelorte-nur-fragen.md) | erledigt (Commit 44e5fc2) |
| 065 | niedrig | [Der Horcher hielt die Anzeige vom Start fest](065-niedrig-horcher-haelt-die-startanzeige-fest.md) | erledigt (Commit 0fbb0fd) |

## Geprüft und gelaufen

- `python einsatz/draht_pruefen.py` — grün (23 Arten hinein, 10 hinaus)
- `pruefung_gedaechtnis.py` im Container — 23/23
- `wache_test.py` im Container — 6/6
- Gegenprobe der Bremse gegen die echten Funktionen im Container,
  vorher und nachher (Befunde in 060–065)
- Vergleich alt/neu: 54 Alltagsbefehle für `befehl_stufe` — keine
  Stufe verändert; 18 Befehle für den Arbeiter — nur `ls ~` und
  `echo ~` jetzt abgelehnt

Nicht geprüft: die Oberflächen selbst (App, Weboberfläche) nach dem
Horcher-Fix 065; Ende-zu-Ende-Gespräche mit echten Rückfragen.
