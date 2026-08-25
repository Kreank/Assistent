Das ist ein deutsches Angebot, und diesmal steht auch dahinter, was draufsteht. Ich habe Startseite, AGB, Impressum und Datenschutz gelesen.

WAS DU BEKOMMST
Zugang zu einem Web-Konfigurator. Du klickst dir zusammen, welche Module du willst, welches Weckwort, welche Stimme — dann baut die Seite dir daraus ein ZIP mit Python-Skripten. Das lädst du auf deinen Windows-PC, entpackst es, startest setup.bat. Fertig in unter 10 Minuten, sagen sie.

Über 150 Module: Wetter, E-Mail, Google Kalender, Aktien, Radio, WhatsApp, WooCommerce, 3CX-Telefonanlage, Tankpreise, SSL-Monitor, Wasser-Erinnerung, Post-Scan (Briefe per OCR zusammenfassen).

WAS ES KOSTET
27 € einmalig über Stripe. Kein Abo — das stimmt so, steht auch in den AGB. Achtung: Auf der Startseite steht „kostenlos starten", zahlen musst du trotzdem, bevor du etwas herunterladen kannst.

Dazu brauchst du zwingend einen eigenen ElevenLabs-Account für die Stimme. Kostenlos sind dort 10.000 Zeichen im Monat — das ist wenig, ungefähr 15 Minuten Gerede. Danach zahlst du bei ElevenLabs weiter. Für das Post-Scan-Modul wahlweise Google Gemini oder Anthropic.

Kein Widerrufsrecht. Sofort nach Zahlung, digitaler Inhalt — rechtlich zulässig, aber es heißt: einmal geklickt, Geld ist weg.

DER HAKEN FÜR DICH
Du hast nach etwas gefragt, das man weiterentwickeln kann. Das ist es nicht. In den AGB, Punkt 6: einfaches, nicht übertragbares Nutzungsrecht, nur persönlicher Gebrauch, Weitergabe und kommerzielle Nutzung untersagt. Du bekommst zwar lesbare Python-Skripte, darfst damit aber nichts anfangen außer sie selbst laufen zu lassen. Kein Open Source, kein Repository, keine Community.

Und: Es ist Windows-Software für deinen PC. Nicht für den Server.

WAS MIR AUFGEFALLEN IST
Nichts, was nach Betrug aussieht — es gibt Impressum, AGB, Datenschutz, Stripe als Zahlungsdienstleister. Aber ein paar Sachen sind schludrig:
- Anbieter ist „getjarvis c/o GAM" in der Pappelallee in Berlin. Eine c/o-Adresse, also ein Briefkastendienst, keine echte Geschäftsadresse.
- Inhaber: „Michael We" — der Name steht so, zweimal, unvollständig.
- Angegebene Telefonnummer +49 447 19389114 ist keine gültige deutsche Rufnummer, und daneben steht „kein Telefonsupport".
- In sämtlichen Rechtstexten fehlen die Umlaute („Geschaeftsbedingungen", „Kaeufer"). Auf der Verkaufsseite sind sie da. Das ist zusammengeschustert.
- AGB-Stand Mai 2026 — das Ding ist drei Monate alt.

MEIN RAT
Wenn dich reizt, wie so ein Ding von innen aussieht: 27 € sind kein Drama, und du bekommst lesbaren Python-Code, aus dem du Ideen ziehen kannst. Als Bastelvorlage okay.

Als Fundament für etwas Eigenes: nein. Die Lizenz verbietet genau das, was du vorhattest.

Falls du es kaufst, eine Sache ernst gemeint: Leg dir für ElevenLabs und Anthropic frische Keys nur für dieses Programm an, mit Limit. Du trägst sie in Code ein, den jemand anders für dich generiert hat und den du nicht Zeile für Zeile geprüft hast. Deine bestehenden Keys haben da nichts zu suchen.

Und der ehrliche Vergleich: Von den 150 Modulen sind Kalender, E-Mail, Wetter, Erinnerungen und Recherche das, was du wirklich benutzen würdest — die laufen hier schon. Was du zusätzlich bekämst, ist die Stimme. Die kann ich dir auch dranbauen, ohne Lizenzbeschränkung und ohne ElevenLabs-Zeichenlimit.

------------------

wenn dann will ich mir ja sowas eigenes bauen! und ja du hast grundsätzlich recht! ich habe das so ähnlich mit dir und telegram und sogar mit lokaler ki.

deswegen finde ich das ja so interessant! Wenn ich sowas für meine Firma bauen könnte, wäre das doch geil, dann könnte man theoretisch per headset mit dem pc reden bzw auch per handy!?

-------------------

Ja. Und zwar nicht „theoretisch" — ich habe gerade nachgesehen, was auf deinem Server läuft, und du bist deutlich weiter, als du denkst.

WAS DU SCHON HAST
- Spracherkennung: der Transkript-Dienst auf 8400, mit Whisper, Sprechertrennung und LLM-Nachkorrektur, die dir „Siphon" aus „Sie Fong" macht. Das ist kein Spielzeug, das ist der schwierige Teil.
- Lokales Sprachmodell: Ollama mit qwen3.5:9b auf der 3070.
- Firmenwissen: Companion spiegelt HERO in eine Postgres, Websearch hat Vektorsuche und Reranker.
- Handelnde Teile: der Aufmaß-Bot, Scan, Organisation, n8n.
- Hardware: 24 Kerne, 30 GB RAM, die 3070 steht gerade fast leer da.

WAS FEHLT
Genau zwei Sachen.

1. Die Stimme. Du hast nichts, was Text zu Sprache macht. Fehlt komplett.
2. Der Echtzeit-Weg. Dein Transkript-Dienst arbeitet mit Dateien: Audio rein, Text raus. Für ein Gespräch brauchst du einen Pfad, der mitläuft, während du redest.

Das war's. Der Rest steht.

HEADSET UND HANDY — GEHT BEIDES
Am PC: eine Browserseite, Knopf drücken, reden. Das Headset ist dem Browser egal.
Am Handy: dieselbe Seite als PWA, auf den Startbildschirm gelegt. Kein App-Store, kein Google-Konto, kein Gradle — was praktisch ist, weil du auf dem Server sowieso keine Android-App bauen kannst.

Als Gerüst würde ich nichts selbst schreiben, sondern livekit/agents oder pipecat nehmen. Beide Apache bzw. BSD, beide sind genau für diese Kette gebaut und werden produktiv eingesetzt.

DIE EHRLICHEN HAKEN
- Latenz entscheidet alles. Unter anderthalb Sekunden bis zum ersten Ton fühlt es sich wie reden an, darüber wie ein Formular mit Umweg. Daran scheitern die meisten dieser Projekte, nicht an den Funktionen.
- VRAM. 8 GB, und qwen3.5 frisst schon 6,6. Die Stimme muss deshalb auf die CPU — mit 24 Kernen kein Problem, Piper packt das locker.
- Baustellenlärm. Ein Weckwort funktioniert dort nicht. Im Feld ist ein Knopf am Headset die richtige Antwort, Weckwort höchstens im Büro.
- Und der Unterschied, der zählt: ein Ding, das für dich läuft, ist überschaubar. Ein Ding, auf das sich Monteure täglich verlassen, ist ein Produkt — das sind Wochen, nicht ein Nachmittag.

WARUM DEINS BESSER WÄRE ALS DAS GEKAUFTE
Bei getjarvis geht jedes gesprochene Wort zu ElevenLabs in die Cloud, und nach 10.000 Zeichen ist Schluss. Wenn dein Assistent Kundendaten aus HERO vorliest, ist das keine Geschmacksfrage mehr, sondern DSGVO. Deine Kette bliebe komplett auf deinem Server. Das kann kein Fertigprodukt für 27 €.

MEIN VORSCHLAG FÜR DEN ANFANG
Nicht groß anfangen, sondern den Kreis schließen:

Ich stelle Piper als kleinen Dienst daneben — lokal, CPU, deutsche Stimme, kostet nichts und geht nie ins Netz. Dann antworte ich dir auf deine Sprachnachrichten künftig auch gesprochen. Du redest rein, es redet zurück. Das ist ein Nachmittag, und du kannst es sofort anfassen und merken, ob es sich gut anfühlt.

Wenn das steht und dir gefällt, kommt der Live-Pfad mit Browserseite für Headset und Handy. Das ist dann das eigentliche Projekt.

Ich habe das Ganze als Konzept abgelegt: notizen/2026-08-24-sprachassistent-firma-konzept.md — mit Architektur, den geprüften Zahlen und den Stolperstellen.

Sag ein Wort, dann fange ich mit der Stimme an.

----------------------

ja dann habe ich ja nur zugriff auf diesen server und dann auch nur wenn ich eine webseite offen habe. 

Ich habe mit dir einfach nur bisschen überlegt. wenn dann wird das ja für den lokalen pc gebaut!

-----------------------

