# Code-Review vom 27.08.2026 — Übersicht

Vollständiger Review des Sarvis-Codes (10.419 Zeilen, 26 Dateien) durch acht
Reviewer, jeder Fund anschließend von einem Gegenspieler geprüft, dessen
Auftrag es war, ihn zu widerlegen.

| | Anzahl |
|---|---|
| gemeldet | 63 |
| **bestätigt** | **57** (+1 Nachtrag) |
| widerlegt | 6 |
| davon hoch | 9 |
| davon mittel | 18 |
| davon niedrig | 30 |

## Bestätigte Funde

| Nr | Schwere | Bereich | Fundstelle | Titel |
|---|---|---|---|---|
| 001 | hoch | auftraege | `sarvis/werkzeuge/auftrag.py:392` | [Leseschranke des Arbeiters greift nur bei absoluten Pfaden](001-hoch-leseschranke-des-arbeiters-greift-nur-bei-absoluten-.md) |
| 002 | hoch | auftraege | `sarvis/werkzeuge/auftrag.py:767` | [auftrag_fortsetzen ruft ein blinken(), das es in dieser Datei nicht gibt](002-hoch-auftrag-fortsetzen-ruft-ein-blinken-das-es-in-dieser.md) |
| 003 | hoch | entscheidungen | `sarvis/freigabe.py:39` | [Freigabe für "Ordner durchsuchen" ist ortlos — und ortlos heißt überall](003-hoch-freigabe-fuer-ordner-durchsuchen-ist-ortlos-und-ortl.md) |
| 004 | hoch | entscheidungen | `sarvis/freigabe.py:72` | [Befehls-Freigabe prüft nur den ERSTEN Pfad einer Kette](004-hoch-befehls-freigabe-prueft-nur-den-ersten-pfad-einer-ke.md) |
| 005 | hoch | entscheidungen | `sarvis/schutz.py:274` | [Git-Bash-Pfade (/d/...) umgehen die Pfadprüfung in befehl_stufe](005-hoch-git-bash-pfade-d-umgehen-die-pfadpruefung-in-befehl-.md) |
| 006 | hoch | entscheidungen | `sarvis/schutz.py:414` | [Inhaltsprüfung hält jede UTF-16-Datei für binär und liest sie still](006-hoch-inhaltspruefung-haelt-jede-utf-16-datei-fuer-binaer-.md) |
| 007 | hoch | hirn | `sarvis/hirn.py:408` | [Wartesatz und Werkzeug-Leuchten sind unerreichbar -- der erste elif frisst genau den Fall, fuer den der zweite gebaut wurde](007-hoch-wartesatz-und-werkzeug-leuchten-sind-unerreichbar-de.md) |
| 008 | hoch | werkzeuge | `sarvis/werkzeuge/programme.py:124` | [Vollstaendige URL wird auf die Startseite verkuerzt -- der Link geht verloren](008-hoch-vollstaendige-url-wird-auf-die-startseite-verkuerzt-.md) |
| 009 | hoch | werkzeuge | `sarvis/werkzeuge/projekte.py:305` | [projekt_anlegen mit art='web' bricht mitten im Anlegen ab und laesst eine halbe Projektruine zurueck](009-hoch-projekt-anlegen-mit-art-web-bricht-mitten-im-anlegen.md) |
| 010 | mittel | anzeige | `sarvis/hud.py:688` | [Untertitel wird bei rund 390 Zeichen stumm abgeschnitten -- und zwar hinten](010-mittel-untertitel-wird-bei-rund-390-zeichen-stumm-abgeschni.md) |
| 011 | mittel | auftraege | `sarvis/werkzeuge/auftrag.py:473` | [stand() vergleicht gegen ein fest verdrahtetes main](011-mittel-stand-vergleicht-gegen-ein-fest-verdrahtetes-main.md) |
| 012 | mittel | auftraege | `sarvis/werkzeuge/erinnern.py:161` | [Personensuche findet die Akte, liefert aber keine Inhalte](012-mittel-personensuche-findet-die-akte-liefert-aber-keine-inh.md) |
| 013 | mittel | aussenwelt | `sarvis/werkzeuge/google.py:242` | [Zwei gleichnamige Dateien: Drive waehlt still die zuletzt geaenderte -- auch beim Teilen](013-mittel-zwei-gleichnamige-dateien-drive-waehlt-still-die-zul.md) |
| 014 | mittel | aussenwelt | `sarvis/werkzeuge/google.py:71` | [Gemerkte Google-Dienste werden nie verworfen -- Neuanmeldung wirkt erst nach Neustart](014-mittel-gemerkte-google-dienste-werden-nie-verworfen-neuanme.md) |
| 015 | mittel | aussenwelt | `sarvis/werkzeuge/google.py:751` | [aufgabe_anlegen verschluckt ein unverstandenes Faelligkeitsdatum und meldet Erfolg](015-mittel-aufgabe-anlegen-verschluckt-ein-unverstandenes-faell.md) |
| 016 | mittel | aussenwelt | `sarvis/werkzeuge/google.py:573` | [mail_lesen schneidet bei 4000 Zeichen ab, ohne es zu kennzeichnen](016-mittel-mail-lesen-schneidet-bei-4000-zeichen-ab-ohne-es-zu-.md) |
| 017 | mittel | aussenwelt | `sarvis/werkzeuge/google.py:757` | [aufgabe_anlegen und aufgabe_abhaken landen nicht im Protokoll](017-mittel-aufgabe-anlegen-und-aufgabe-abhaken-landen-nicht-im-.md) |
| 018 | mittel | aussenwelt | `sarvis/werkzeuge/telegram.py:174` | [telegram_senden verschickt bei EINEM schwachen Zufallstreffer ohne Rueckfrage](018-mittel-telegram-senden-verschickt-bei-einem-schwachen-zufal.md) |
| 019 | mittel | entscheidungen | `sarvis/rueckfrage.py:164` | [Fehlende Wortgrenze: das Wort "Termin" erzeugt eine Freigabe](019-mittel-fehlende-wortgrenze-das-wort-termin-erzeugt-eine-fre.md) |
| 020 | mittel | entscheidungen | `sarvis/schutz.py:243` | [Die einzige harte Sperre gilt nicht für die Shell](020-mittel-die-einzige-harte-sperre-gilt-nicht-fuer-die-shell.md) |
| 021 | mittel | hauptschleife | `sarvis/main.py:835` | [Gesprochenes "hoer auf" waehrend einer offenen Rueckfrage stoppt nichts](021-mittel-gesprochenes-hoer-auf-waehrend-einer-offenen-rueckfr.md) |
| 022 | mittel | hirn | `sarvis/hirn.py:156` | [Glob umgeht die Rueckfrage fuer D:\Strato Server -- der Pfad steht in `pattern`, geprueft wird nur `path`](022-mittel-glob-umgeht-die-rueckfrage-fuer-d-strato-server-der-.md) |
| 023 | mittel | sprachweg | `sarvis/weckwort.py:203` | [spricht(None) loescht den Echo-Filter, bevor das eigene Echo ueberhaupt geprueft wurde](023-mittel-spricht-none-loescht-den-echo-filter-bevor-das-eigen.md) |
| 024 | mittel | werkzeuge | `sarvis/werkzeuge/programme.py:55` | [Leere Programmliste wird dauerhaft gemerkt -- danach behauptet Sarvis fuer immer, es gebe das Programm nicht](024-mittel-leere-programmliste-wird-dauerhaft-gemerkt-danach-be.md) |
| 025 | mittel | werkzeuge | `sarvis/werkzeuge/programme.py:45` | [Der Kommentar verspricht 'nicht stillschweigend leer' -- genau das passiert bei jedem PowerShell-Fehler ohne Ausnahme](025-mittel-der-kommentar-verspricht-nicht-stillschweigend-leer-.md) |
| 026 | mittel | werkzeuge | `sarvis/werkzeuge/programme.py:252` | [programm_beenden kann bei einem Namen ohne Wortzeichen ALLE Prozesse abschiessen](026-mittel-programm-beenden-kann-bei-einem-namen-ohne-wortzeich.md) |
| 027 | mittel | werkzeuge | `sarvis/werkzeuge/projekte.py:442` | [ort_ansehen laeuft still, prueft nur die Namens-Stufe -- liest aber Dateiinhalt vor](027-mittel-ort-ansehen-laeuft-still-prueft-nur-die-namens-stufe.md) |
| 028 | niedrig | anzeige | `sarvis/hud.py:619` | [Die Hintergrund-Ecke ist nicht frei: 'Finanzen' aus dem Kranz liegt darueber](028-niedrig-die-hintergrund-ecke-ist-nicht-frei-finanzen-aus-dem.md) |
| 029 | niedrig | anzeige | `sarvis/hud.py:311` | [Das Aufblenden ('hervor') hat mit der ausgelieferten Konfiguration keinerlei Wirkung](029-niedrig-das-aufblenden-hervor-hat-mit-der-ausgelieferten-kon.md) |
| 030 | niedrig | anzeige | `sarvis/hud.py:242` | [Der Mausgriff wird beim Loslassen nicht zurueckgesetzt](030-niedrig-der-mausgriff-wird-beim-loslassen-nicht-zurueckgeset.md) |
| 031 | niedrig | anzeige | `sarvis/stimmfarbe.py:154` | [Der Phaser wandert nicht: der LFO wird auf einen einzigen Mittelwert eingedampft](031-niedrig-der-phaser-wandert-nicht-der-lfo-wird-auf-einen-einz.md) |
| 032 | niedrig | anzeige | `sarvis/stimmfarbe.py:418` | [Unbekannter Farbname: die ganze Effektkette faellt still weg](032-niedrig-unbekannter-farbname-die-ganze-effektkette-faellt-st.md) |
| 033 | niedrig | auftraege | `sarvis/werkzeuge/auftrag.py:570` | [Die Abbruchmeldung eines Auftrags wird nie erreicht](033-niedrig-die-abbruchmeldung-eines-auftrags-wird-nie-erreicht.md) |
| 034 | niedrig | auftraege | `sarvis/werkzeuge/erinnern.py:278` | [merken loescht bei kurzen Inhalten stumm fremde Eintraege](034-niedrig-merken-loescht-bei-kurzen-inhalten-stumm-fremde-eint.md) |
| 035 | niedrig | auftraege | `sarvis/werkzeuge/erinnern.py:210` | [Freitextzeilen ohne fuehrenden Strich gehen beim naechsten Schreiben verloren](035-niedrig-freitextzeilen-ohne-fuehrenden-strich-gehen-beim-nae.md) |
| 036 | niedrig | auftraege | `sarvis/werkzeuge/zeit.py:158` | [Zerrissene timer.json loescht alle Timer ohne ein Wort](036-niedrig-zerrissene-timer-json-loescht-alle-timer-ohne-ein-wo.md) |
| 037 | niedrig | auftraege | `sarvis/werkzeuge/zeit.py:55` | [Timer-Dauern werden in Wanduhrzeit umgerechnet und ueberleben die Zeitumstellung nicht](037-niedrig-timer-dauern-werden-in-wanduhrzeit-umgerechnet-und-u.md) |
| 038 | niedrig | auftraege | `sarvis/werkzeuge/zeit.py:185` | [Beim Wiederherstellen genau der ungenaue Umweg, den stellen_bis verwirft](038-niedrig-beim-wiederherstellen-genau-der-ungenaue-umweg-den-s.md) |
| 039 | niedrig | aussenwelt | `sarvis/werkzeuge/google.py:364` | [termine_ansehen faellt bei unverstandenem Startdatum still auf heute zurueck](039-niedrig-termine-ansehen-faellt-bei-unverstandenem-startdatum.md) |
| 040 | niedrig | aussenwelt | `sarvis/werkzeuge/google.py:676` | [Aufgaben-Werkzeuge sehen nur die erste Aufgabenliste](040-niedrig-aufgaben-werkzeuge-sehen-nur-die-erste-aufgabenliste.md) |
| 041 | niedrig | aussenwelt | `sarvis/werkzeuge/google.py:1150` | [tabelle_schreiben schreibt immer nur eine Zeile, meldet aber den ganzen Bereich als gesetzt](041-niedrig-tabelle-schreiben-schreibt-immer-nur-eine-zeile-meld.md) |
| 042 | niedrig | aussenwelt | `sarvis/werkzeuge/google.py:372` | [termine_ansehen deckelt bei 25 Terminen ohne Hinweis](042-niedrig-termine-ansehen-deckelt-bei-25-terminen-ohne-hinweis.md) |
| 043 | niedrig | aussenwelt | `sarvis/werkzeuge/telegram.py:226` | [telegram_lesen sagt "neueste zuerst" und liefert aelteste zuerst](043-niedrig-telegram-lesen-sagt-neueste-zuerst-und-liefert-aelte.md) |
| 044 | niedrig | aussenwelt | `sarvis/werkzeuge/telegram.py:40` | [Telegram-Verbindungen werden bei jedem Neuaufbau liegengelassen](044-niedrig-telegram-verbindungen-werden-bei-jedem-neuaufbau-lie.md) |
| 045 | niedrig | aussenwelt | `sarvis/werkzeuge/telegram.py:216` | [telegram_lesen wirft Bild- und Sprachnachrichten still aus der Zaehlung](045-niedrig-telegram-lesen-wirft-bild-und-sprachnachrichten-stil.md) |
| 046 | niedrig | entscheidungen | `sarvis/freigabe.py:184` | [Anzeige zeigt die kürzeste Freigabe, zählt aber die längste herunter](046-niedrig-anzeige-zeigt-die-kuerzeste-freigabe-zaehlt-aber-die.md) |
| 047 | niedrig | hauptschleife | `sarvis/main.py:678` | [Nach einem Abbruch bleibt der Horcher im Zustand "Sarvis spricht" haengen](047-niedrig-nach-einem-abbruch-bleibt-der-horcher-im-zustand-sar.md) |
| 048 | niedrig | hauptschleife | `sarvis/main.py:459` | [Zu kurze Antwort auf eine Rueckfrage verschwindet ohne Konsolenzeile](048-niedrig-zu-kurze-antwort-auf-eine-rueckfrage-verschwindet-oh.md) |
| 049 | niedrig | hirn | `sarvis/hirn.py:327` | [Der Protokoll-Nachtrag wird VOR dem Leerlesen aufgenommen -- was waehrend des Abbruchs noch fertig wird, faellt still weg](049-niedrig-der-protokoll-nachtrag-wird-vor-dem-leerlesen-aufgen.md) |
| 050 | niedrig | hirn | `sarvis/hirn.py:337` | [Das Leerlesen nach dem Abbruch schluckt jeden Fehler und jeden Zeitablauf -- danach ist die naechste Antwort um eine Runde verschoben](050-niedrig-das-leerlesen-nach-dem-abbruch-schluckt-jeden-fehler.md) |
| 051 | niedrig | sprachweg | `sarvis/audio.py:138` | [abbrechen() erwischt den Satz nicht, den der Abspielfaden schon aus der Schlange gezogen hat](051-niedrig-abbrechen-erwischt-den-satz-nicht-den-der-abspielfad.md) |
| 052 | niedrig | sprachweg | `sarvis/audio.py:173` | [leer wird zwischen clear() und put() gesetzt -- warten() kehrt zurueck, obwohl noch ein Satz aussteht](052-niedrig-leer-wird-zwischen-clear-und-put-gesetzt-warten-kehr.md) |
| 053 | niedrig | sprachweg | `sarvis/weckwort.py:287` | [Whisper laeuft im Mikrofon-Lesefaden; die Ueberlauf-Meldung von read() wird weggeworfen](053-niedrig-whisper-laeuft-im-mikrofon-lesefaden-die-ueberlauf-m.md) |
| 054 | niedrig | sprachweg | `sarvis/weckwort.py:303` | [Ein VAD-Fehler verschluckt den Block und kann den Horcher dauerhaft taub machen](054-niedrig-ein-vad-fehler-verschluckt-den-block-und-kann-den-ho.md) |
| 055 | niedrig | sprachweg | `sarvis/weckwort.py:387` | [Die Mindestlaenge WECKWORT_MIN_SEK kann nie greifen -- der Nachlauf ist laenger als die Schwelle](055-niedrig-die-mindestlaenge-weckwort-min-sek-kann-nie-greifen-.md) |
| 056 | niedrig | werkzeuge | `sarvis/werkzeuge/finanzen.py:265` | [Buchungen und Empfaenger werden hart auf sechs gekappt -- ohne jeden Hinweis, dass da mehr war](056-niedrig-buchungen-und-empfaenger-werden-hart-auf-sechs-gekap.md) |
| 057 | niedrig | werkzeuge | `sarvis/werkzeuge/programme.py:187` | ["X ist gestartet" wird gesagt und ins Gedaechtnis geschrieben, ohne dass irgendetwas geprueft wurde](057-niedrig-x-ist-gestartet-wird-gesagt-und-ins-gedaechtnis-gesc.md) |

## Nachtrag

Beim Beheben aufgefallen und eigenständig nachgemessen — nicht Teil des
ursprünglichen Reviews:

| Nr | Schwere | Bereich | Fundstelle | Titel |
|---|---|---|---|---|
| 058 | hoch | entscheidungen | `sarvis/rueckfrage.py:99` | ["Ja, frag nicht mehr nach" galt als Einwand](058-hoch-zustimmung-mit-freigabe-galt-als-einwand.md) |
| 059 | mittel | hauptschleife | `sarvis/main.py` | [Der Not-Aus lässt den Satz in Arbeit durch](059-mittel-not-aus-laesst-den-satz-in-arbeit-durch.md) |

## Widerlegte Meldungen

Diese wurden gemeldet, hielten der Gegenprüfung aber nicht stand — hier
festgehalten, damit sie nicht ein zweites Mal gemeldet werden.

- **Die Push-to-talk-Taste wird erst nach Begruessung und Timer-Ansagen scharf gemacht** (`sarvis/main.py`)
  Drei Belege sprechen dagegen. (1) Die Aeusserung geht NICHT verloren: Der Horcher laeuft seit Zeile 787 (self.horcher.start()), _begruessen() meldet seinen Satz sogar ausdruecklich am Echo-Filter an (main.py:602) und oeffnet danach das Nachhoerfenster (main.py:614-615, NACHHOEREN_SEK=18). Ein Zuruf aus dieser Zeit laeuft ueber weckwort.py:_pruefen/_deuten in den eigenen Faden des Horchers und land
- **Beim Nachhaken wird die Dauerfreigabe erteilt, ohne sie noch einmal anzukuendigen** (`sarvis/main.py`)
  Zwei Gruende. (1) Die Ankuendigung ist gefallen -- es ist dieselbe Frage. main.py:352-355 waehlt beim zweiten Versuch bewusst rueckfrage.genauer(...) oder NACHHAKEN ("Ich habe das nicht verstanden. Ja oder nein?"). Das ist keine neue Frage, sondern eine Ruecknachfrage zur unveraendert offenen ersten, deren Wortlaut den Zusatz "Sag ja, dann frage ich dafuer ... die naechsten 30 Minuten nicht mehr" 
- **Ein Fehler beim Abfragen der Hintergrundarbeit wird als "fertig" angezeigt** (`sarvis/main.py`)
  Beide Quellen koennen praktisch nicht werfen, und der einzige denkbare Grund (nebenlaeufige Mutation) ist ausgeschlossen. laufende_kurz (werkzeuge/auftrag.py:653-657) ist eine reine Listenkomprehension ueber sorted(self.auftraege.values(), key=lambda x: x.nummer) mit f-Strings ueber a.nummer/a.projekt und einem Vergleich a.status == "laeuft" -- alles Felder des Auftrag-Datensatzes, keine Ein-/Ausg
- **GEDAECHTNIS_MAX_EINTRAEGE begrenzt nicht die Schicht, sondern jede Datei einzeln -- die immer geladene Schicht wird doppelt so gross wie angesagt** (`sarvis/config.py`)
  Der Reviewer liest nur die Ueberschriftszeile 7 und ignoriert die Begruendung darunter. config.py:8-11 sagt woertlich: 'Der Grund steht in gedaechtnis/LIESMICH.md: kern.md soll unter 60 Zeilen bleiben. Fuer gemerkt.md und beobachtet.md galt das bisher nicht -- sie wuchsen ohne Bremse.' Das ist genau die Ansage, dieselbe Grenze wie bei kern.md nun AUCH je Datei zu ziehen -- nicht, ein gemeinsames B
- **Die Begruendung fuer TASTE_STOPP widerspricht REINREDEN in derselben Datei** (`sarvis/config.py`)
  Der Fund raeumt schon in der eigenen Beschreibung ein, dass die Taste funktioniert -- es geht ausschliesslich um Kommentartext, also um nichts, was der Nutzer je merkt. Und der Widerspruch ist keiner: config.py:97-99 schreibt 'ACHTUNG: Auf Lautsprechern ausschalten' -- REINREDEN ist eine Einstellung mit zwei gueltigen Stellungen, und in der Stellung False ist der TASTE_STOPP-Kommentar woertlich ri
- **_finden durchsucht nur 200 Chats, verspricht im Docstring aber alle** (`sarvis/werkzeuge/telegram.py`)
  Zeile 75-79 im Wortlaut: '"""Alle Chats, die passen -- absteigend nach Guete. / Gibt bewusst eine Liste zurueck und nicht den besten Treffer: Ueber Mehrdeutigkeit entscheidet nicht dieses Modul, sondern der Nutzer."""' -- die zweite Haelfte des Docstrings erklaert die erste und macht klar, worauf sich 'alle' bezieht. Die Signatur in Zeile 74 nennt 'grenze: int = 200' offen als Parameter, das Verha