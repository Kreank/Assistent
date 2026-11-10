# Sarvis: Recherche und Zielbild (10.11.2026)

Recherche-Bericht: Was ein guter persönlicher KI-Assistent heute können
muss, wie die großen Anbieter das lösen, wo Sarvis steht und wie die App
künftig aussehen sollte. Für den Code wurde nur gelesen, nichts geändert.

**Zur Quellenlage, ehrlich gesagt:** Die Webrecherche lief am 10.11.2026.
Die Aussagen zu Funktionen der Anbieter stützen sich, wo möglich, auf deren
Hilfeseiten (OpenAI Help Center, Claude Support). Vieles stammt aber aus
Fachpresse und Blogs. Zahlen aus Herstellerblogs (Latenzbudgets,
Genauigkeitswerte) sind als Richtwerte zu lesen, nicht als Messung.
Die Quellen stehen am Ende.

---

## 0. Die Kurzantwort auf Saschas Frage

> „Sarvis arbeitet ja mit Claude in einem eigenen Container, und Claude kann
> eigentlich schon alles. Müsste ich ihm nicht nur eine Stimme geben?“

**Zur Hälfte richtig, und die Stimme hat er längst.**

Richtig ist: Das *Denken* ist dasselbe. Sarvis' Hirn ist ein dauerhaft
offener Claude-Agent über das Agent SDK (`sarvis/hirn.py`, Modell
`claude-opus-5`, `config.MODELL`). Damit ist das Modell, das in claude.ai
antwortet, auch in Sarvis. Verstehen, Schreiben, Rechnen, Code und
Werkzeuge bedienen kann er genauso gut.

Nicht richtig ist: „Claude kann alles“ meint meistens **claude.ai**, und
claude.ai ist Modell **plus** sehr viel Drumherum, das Anthropic als
Produkt gebaut hat. Das Drumherum kommt nicht mit, wenn man nur das Modell
anspricht:

| Was man in claude.ai sieht | Ist das Modell? | In Sarvis? |
|---|---|---|
| Verstehen, antworten, Werkzeuge wählen | **ja** | da (dasselbe Modell) |
| Chatverlauf, mehrere Gespräche, Seitenleiste | nein, Oberfläche | fehlt |
| Projekte mit Dateien und eigenen Anweisungen | nein, Oberfläche + Speicher | nur teilweise (Gedächtnis) |
| Artifacts (interaktive Seiten in eigener Sandbox-Domain) | nein, Infrastruktur | bewusst nicht (Blätter ohne Skripte) |
| Datei-Erstellung (Word/Excel/PowerPoint/PDF) | nein: Modell schreibt Code, eine **Sandbox-VM** führt ihn aus | eigene Bauer für PDF/Word/Excel/CSV/MD |
| Research (lange Recherche mit Quellen) | nein, Ablaufsteuerung über viele Modellaufrufe | teilweise (Hintergrundaufträge) |
| Connectors (Gmail, Kalender, Drive) | nein, MCP-Server + Anmeldung | **da**, sogar mehr (Telegram, Finanzen, Spotify …) |
| Sprachmodus (Hören, Sprechen, Unterbrechen) | nein, Audio-Kette | **da** (Whisper, Piper/ElevenLabs, Weckwort) |
| Benachrichtigungen aufs Handy, geplante Aufgaben | nein, Server + Push-Dienst | teilweise (Wecker ja, Push nein) |

Die Stimme war also nie das Fehlende. Sarvis hat Ohren und Mund seit
August. **Was ihm im Vergleich zu claude.ai fehlt, ist vor allem
Oberfläche:** ein sichtbarer Gesprächsverlauf, mehrere Gesprächsfäden, eine
Ablage für das, was er erzeugt hat, Benachrichtigungen bei geschlossener
App. Dazu kommen ein paar Ausgabeformate. Am Denken fehlt nichts.

Es gibt sogar Dinge, die Sarvis **voraus hat**: Weckwort ohne Tastendruck,
Telegram, Finanzen, Radio und Musik, Auto-Modus, Hintergrundaufträge mit
eigener Stimme, abgestufte Rückfragen vor jeder Handlung nach außen.
Weder claude.ai noch ChatGPT haben eine echte Weckwort-Bedienung.

---

## 1. Was ein guter persönlicher Assistent 2026 können muss

Maßstab: ChatGPT (Advanced Voice, Canvas, Scheduled Tasks), Claude.ai
(Artifacts, Projekte, Dateien, Research), Gemini/Gemini Live, Alexa+,
Siri/Apple Intelligence, Home Assistant Assist, Open WebUI, LibreChat.

Was die Großen gerade tun, in einem Satz je Anbieter:

- **ChatGPT:** Canvas als Bearbeitungsfläche neben dem Chat (HTML/React
  wird in einer Sandbox gerendert, Export als PDF/DOCX/MD). Seit Juni 2026
  „Scheduled Tasks“ mit eigener Übersichtsseite und Handy-Benachrichtigung,
  Pulse wurde darin aufgelöst.
- **Claude.ai:** Artifacts in eigener Sandbox-Domain, seit Oktober 2025
  mit Speicher und MCP-Zugriff. Datei-Erstellung (xlsx, pptx, docx, pdf) in
  einer Sandbox-VM. Projekte, Research.
- **Gemini Live:** Kamera und Bildschirm teilen im Live-Gespräch, seit
  Mai 2025 für alle auf Android und iOS. Man kann jederzeit unterbrechen.
- **Alexa+:** seit Februar 2026 in den USA allgemein verfügbar. Sie führt
  Gespräche ohne ständiges „Alexa“, nimmt Dokumente per Mail entgegen und
  merkt sie sich, erledigt Aufgaben auf Webseiten. Die Berichte über die
  Zuverlässigkeit sind gemischt.
- **Siri:** Die persönliche Kontextsuche (Mails, Nachrichten, Fotos) und
  das Handeln über Apps hinweg wurden mehrfach verschoben. Laut letzter
  Meldung kommen sie mit iOS 27. Beim Stand ist Apple Schlusslicht.
- **Home Assistant Assist:** gestreamte Sprachausgabe, während das LLM noch
  schreibt. „Weiterreden ohne Weckwort“ nur, wenn das Modell eine Rückfrage
  stellt.
- **Open WebUI / LibreChat:** selbst gehostete Chat-Oberflächen mit
  Verlauf, Projekten/Wissensbasen, RAG, MCP und Agenten. Gute Vorlage für
  die Bildschirmaufteilung, nicht für Sprache.

### Fähigkeitsliste mit Einstufung und Abgleich

Legende: **P** = Pflicht · **S** = sinnvoll · **K** = Kür.
Sarvis: ✅ vorhanden · 🟡 teilweise · ❌ fehlt.

#### A. Gespräch und Sprache

| Fähigkeit | Stufe | Sarvis | Fundstelle / Begründung |
|---|---|---|---|
| Sprechen und hören, Antwort satzweise gesprochen | P | ✅ | README „Zwei Entscheidungen“, `sarvis/mund.py`, `sarvis/ohren.py` |
| Erster Ton unter ~1,5 s | P | ✅ | README „Gemessen“: 1,07–2,02 s bis zum ersten Ton |
| Tippen statt sprechen | P | ✅ | `web/index.html` Feld `#zeile`, Draht `zuruf` |
| Weckwort / freihändig | S | ✅ | `sarvis/weckwort.py`, Draht „Dauerstrom“ |
| Unterbrechen (Barge-in) | P | 🟡 | per Taste, Weckwort oder Stoppwort (`main.py` `_unterbrechen` ~Z. 720, `rueckfrage._STOPP_WORTE`). Einfach losreden ohne Namen unterbricht nicht |
| Gutes Satzende-Erkennen (Endpointing) | P | 🟡 | feste Stillezeiten 0,55 s / 1,4 s (README „Menschen machen Pausen“). Kein semantisches Erkennen, ob der Satz inhaltlich fertig ist |
| Weiterhören nach der Antwort | S | ✅ | `NACHHOEREN_SEK` = 18 s |
| **Sichtbarer Gesprächsverlauf (Chat)** | **P** | ❌ | Die PWA zeigt genau **eine** Untertitelzeile (`web/sarvis.js` `case 'untertitel'`, ~Z. 2033). Der Verlauf liegt nur auf dem Server (`werkzeuge/verlauf.py`) |
| **Mehrere Gespräche / neues Gespräch / Themenfäden** | **P** | ❌ | Ein einziger dauerhafter `ClaudeSDKClient` (`hirn.py` `start()`), Platz wird per `/compact` geschaffen (`hirn.py` `verdichten`) |
| Gespräch durchsuchen | S | 🟡 | nur Sarvis selbst über `verlauf_nachschlagen`, nicht der Mensch in der App |

#### B. Wissen und Recherche

| Fähigkeit | Stufe | Sarvis | Fundstelle / Begründung |
|---|---|---|---|
| Websuche, Seite lesen | P | ✅ | `WebSearch`/`WebFetch` in `config.WERKZEUG_STUFEN` |
| Lange Recherche mit Quellenbericht („Research“) | S | 🟡 | Hintergrundaufträge (`werkzeuge/auftrag.py`) + `seite_zeigen` sind die Bausteine. Einen festen Ablauf „recherchieren → Quellen prüfen → Bericht mit Fußnoten“ gibt es nicht |
| Dateien verstehen (PDF, Word, Excel, Bilder) | P | 🟡 | Server: `POST /datei` + `werkzeuge/eingang.py`, `lesen.py`. **Die PWA hat keinen Datei-Knopf** (in `web/` kein `type="file"`). Hochladen geht nur aus einer nativen App |
| Foto aufnehmen und fragen („was ist das?“) | S | 🟡 | als Upload möglich, kein Kamera-Knopf in der PWA |
| Live-Kamera / Bildschirm teilen | K | ❌ | Gemini-Live-Klasse, braucht ein Echtzeit-Videomodell |
| Projekte / Wissenssammlungen mit eigenen Anweisungen | S | 🟡 | Gedächtnis mit Personen und Notizen (`gedaechtnis.py`, `werkzeuge/erinnern.py`), aber kein „Projekt“, das Dateien, Anweisungen und Gespräche bündelt |

#### C. Gedächtnis und Personalisierung

| Fähigkeit | Stufe | Sarvis | Fundstelle / Begründung |
|---|---|---|---|
| Langzeitgedächtnis, Fakten vs. Vermutungen | P | ✅ | `werkzeuge/erinnern.py`: gemerkt / beobachtet / entschieden, Personen, Notizen |
| Gedächtnis einsehen und löschen | P | 🟡 | per Sprache (`gedaechtnis_zeigen`, `vergessen`). Keine Ansicht in der App, in der man blättert und löscht |
| Einstellungen (Stimme, Weckwort, Ruhezeiten) in der App | S | ❌ | nur in `sarvis/config.py` |

#### D. Handeln

| Fähigkeit | Stufe | Sarvis | Fundstelle / Begründung |
|---|---|---|---|
| Kalender, Mail, Aufgaben, Kontakte, Drive, Tabellen | P | ✅ | `werkzeuge/google.py` |
| Messenger | S | ✅ | `werkzeuge/telegram.py` |
| Wecker, Timer, Erinnerungen, auch wiederkehrend | P | ✅ | `werkzeuge/zeit.py` (`wiederholt`: täglich/wöchentlich) |
| **Geplante KI-Aufgaben** („jeden Morgen um 7 ein Briefing“, „sag Bescheid, wenn …“) | S | 🟡 | Wecker sprechen festen Text. Einen wiederkehrenden Lauf, in dem Sarvis selbst nachsieht und zusammenfasst, habe ich im Code nicht gefunden. Das ist die ChatGPT-„Scheduled Tasks“-Klasse |
| **Benachrichtigung bei geschlossener App (Push)** | **P** | ❌ | Meldungen gehen nur an verbundene Oberflächen (`main.py` `_melden_sprechen`). Der Service Worker hat kein Push (`web/waechter.js`). Ein Timer bei geschlossener App klingelt ins Leere |
| Hintergrundaufträge, während man weiterredet | S | ✅ | `werkzeuge/auftrag.py`, Draht `hintergrund`, `strom` |
| Webseiten bedienen (Agent im Browser) | K | ✅ | `sarvis/browser.py`, `web_klicken`/`web_tippen`, Fernsicht |
| Rückfrage vor Handlungen nach außen | P | ✅ | Stufen still/fragen/pfad/browser in `config.WERKZEUG_STUFEN`, `FREIGABE_NIE`, `sarvis/freigabe.py`, `rueckfrage.py` |
| Musik, Radio, Medien | S | ✅ | `musik.py`, `medien.py`, Draht `radio`/`befehl` |
| Wetter, Verkehr, Tanken, Nachrichten | S | ✅ | `wetter.py`, `unterwegs.py` |
| Finanzen | K | ✅ | `finanzen.py` |
| Rechnen ohne Raten | P | ✅ | `rechnen.py`, `rechner.py` |

#### E. Ausgabe

| Fähigkeit | Stufe | Sarvis | Fundstelle / Begründung |
|---|---|---|---|
| Formatierte Antwort (Überschriften, Listen, Tabellen) | P | ✅ | `blatt_zeigen`, Markdown-Teilmenge (DRAHT.md „Blätter“) |
| Bericht mit Diagrammen | S | ✅ | `seite_zeigen`, `werkzeuge/bericht.py` (SVG, serverseitig gerechnet) |
| Kleine Datenkarten im Vorbeigehen | S | ✅ | Kacheln, 9 Formen (`werkzeuge/kacheln.py`) |
| Downloads PDF / DOCX / XLSX / CSV / MD | P | ✅ | `werkzeuge/dokument.py` `SORTEN` |
| Kalendereintrag (.ics), Kontakt (.vcf) | S | ❌ | fehlt (Termine gehen nur direkt in Google) |
| Präsentation (.pptx) | S | ❌ | fehlt |
| Bild/Diagramm als PNG/SVG zum Speichern | S | ❌ | Diagramme gibt es nur eingebettet in der Seite |
| ZIP (mehrere Dateien), HTML-Datei | K | ❌ | fehlt |
| **Ablage: „Was hast du mir erstellt?“** | **P** | ❌ | Blätter laufen nach 7 Tagen ab (`netz/blaetter.py`). In der App gibt es keine Liste der eigenen Dateien |
| Gemeinsam an einem Dokument arbeiten, Versionen | S | ❌ | Ein Blatt mit gleicher `kennung` wird überschrieben, frühere Fassungen sind weg |
| Interaktive Seiten (Rechner, Checkliste, Mini-App) | K | ❌ | bewusst gesperrt (iframe ohne `allow-scripts`). Siehe Abschnitt 4 |

#### F. Plattform

| Fähigkeit | Stufe | Sarvis | Fundstelle / Begründung |
|---|---|---|---|
| Handy + PC, mehrere Geräte gleichzeitig | P | ✅ | Draht: mehrere Oberflächen gleichzeitig, Geräteschlüssel |
| App auf dem Startbildschirm, Offline-Hülle | S | ✅ | `web/manifest.json`, `web/waechter.js` |
| Weckwort bei gesperrtem Handy | K | 🟡 | nur mit nativer Android-App (einsatz/APP-BAUEN.md) |
| Auto-Modus | K | ✅ | Draht `auto`, README „Wenn nie eine Pause kommt“ |

**Bilanz:** Bei Handeln, Gedächtnis und Sprache ist Sarvis vorn. Die
roten Pflichtpunkte liegen fast alle in **Oberfläche und Ablage**:
Chatverlauf, Gesprächsfäden, Push, Dateiablage. Die übrigen Lücken sind
Datei-Upload in der PWA und Unterbrechen ohne Namen.

---

## 2. Datei-Ausgabe: welche Formate

### Was die Großen tatsächlich liefern

- **Claude.ai:** erzeugt und bearbeitet `.xlsx`, `.pptx`, `.docx` und
  `.pdf` in einer Sandbox-VM. Die Dateien lassen sich herunterladen oder in
  Google Drive ablegen. Vorschau seit September 2025, für alle
  Bezahltarife seit 21.10.2025. Weil dort beliebiger Python-Code läuft,
  geht praktisch auch CSV, PNG-Diagramme, ZIP, MD, HTML.
- **ChatGPT:** Canvas exportiert Dokumente als PDF, DOCX und MD, Code als
  passende Datei (.py, .js …). Über die Code-Ausführung (früher „Code
  Interpreter“) entstehen CSV, XLSX, DOCX, PDF, PPTX, PNG und ZIP. Das ist
  in der Fachpresse gut belegt, offizielle Formatlisten gibt es nur für den
  Upload.
- **Gemini:** exportiert nach Google Docs und Sheets (nicht vertieft
  recherchiert).
- **Alexa+/Siri:** liefern keine Dateien. Sie handeln direkt (Termin,
  Erinnerung).

### Empfehlung für Sarvis

| Format | Wofür | Stand | Priorität |
|---|---|---|---|
| PDF | fertig, zum Weitergeben/Drucken | ✅ | – |
| DOCX | zum Weiterschreiben | ✅ | – |
| XLSX | Zahlen zum Weiterrechnen | ✅ | – |
| CSV | Import in andere Programme | ✅ | – |
| MD / TXT | Notizen, Rohtext | ✅ (`text` → `.md`) | – |
| **ICS** | „schick mir das als Termin“: ein Tipp, und er liegt im Handy-Kalender. Auch für Termine, die nicht in Google sollen | ❌ | **hoch**. Klein (reiner Text nach RFC 5545), großer Nutzen am Handy |
| **VCF** | Kontakt weitergeben oder ins Handy übernehmen | ❌ | **hoch**. Klein, reiner Text |
| **PNG** (Diagramm/Bild) | Diagramm in WhatsApp/Telegram teilen | ❌ | mittel. Das SVG gibt es schon (`bericht.py`), Umwandeln geht mit dem vorhandenen Chrome (`dokument._chrome`) |
| SVG | Diagramm verlustfrei | ❌ | niedrig. Fällt fast umsonst mit ab, **aber** SVG kann Skripte enthalten und muss deshalb als Download (`Content-Disposition: attachment`) raus, nie inline |
| PPTX | Präsentation | ❌ | niedrig für Privatgebrauch. Wenn, dann wie `docx_bauen.py` aus der Standardbibliothek |
| ZIP | mehrere Dateien auf einmal | ❌ | niedrig. `zipfile` ist vorhanden |
| HTML-Datei | Seite offline behalten | ❌ | niedrig. Der Bericht existiert schon als HTML |

**Mindestumfang:** PDF, DOCX, XLSX, CSV, MD (alles da) **plus ICS und
VCF**. Danach PNG. Der Rest ist Kür.

---

## 3. Oberfläche: Chat, Kategorien oder Kacheln?

### Was Forschung und Praxis sagen

1. **Ein leeres Eingabefeld zeigt nicht, was das System kann.** Das ist
   die bekannteste Kritik an reinen Chat-Oberflächen (Jakob Nielsen,
   Nielsen Norman Group, und viele Folgeartikel): Schreiben fällt den
   meisten schwerer als Lesen, und ein Prompt-Feld bietet unendlich viele
   Möglichkeiten, aber kaum Hinweise. Nielsens Prognose: Gute
   KI-Oberflächen werden **hybrid**, also Absicht in Worten plus
   klassische Bedienelemente.
2. **„Prompt-Controls“ helfen.** Das sind Knöpfe und Vorschläge rund um
   das Eingabefeld. Eine Studie zu Chatbots (USA/China) fand sie nützlich,
   aber auch: Schlecht beschriftete oder ungeordnete Knöpfe erhöhen den
   Lernaufwand. **Wenige, klar benannte Einstiege schlagen viele.**
3. **Bei 100+ Werkzeugen wählt das Modell selbst, nicht der Mensch.**
   Keiner der Großen zeigt seine Werkzeuge als Menü. ChatGPT, Claude und
   Gemini haben einen Chat, eine Seitenleiste mit **Gesprächen und
   Projekten** und höchstens ein „+“-Menü für Dateien und Modi. Der Mensch
   sagt, was er will. Der Assistent sucht das Werkzeug.
4. **Zu viele Werkzeuge verschlechtern auch das Modell.** Anthropic und
   andere berichten, dass die Trefferquote bei der Werkzeugwahl ab etwa
   30–50 gleichzeitig sichtbaren Werkzeugen spürbar sinkt. Die Antwort
   darauf ist „Tool Search“: Werkzeuge werden erst bei Bedarf geladen.
   Laut Berichten über Anthropic-interne Tests stieg die Trefferquote
   damit deutlich (Opus 4: 49 % → 74 %). Die Zahlen sind aus zweiter
   Hand. **Für Sarvis (107 Werkzeuge) ist das ein Prüfpunkt:** Ob das
   Agent SDK die Werkzeuge bei ihm aufschiebt, habe ich nicht gemessen.
   Fehlgriffe bei der Werkzeugwahl wären das Anzeichen.
5. **Dashboards/Kacheln** taugen für den Blick nebenbei (Wetter, nächster
   Termin, Kontostand), aber nicht als Hauptbedienung. Sarvis' Kacheln
   sind genau richtig eingeordnet: Sie zeigen, sie bedienen nicht
   (DRAHT.md: „Kacheln dürfen nicht anklickbar sein“).

### Empfehlung

**Chat in der Mitte, keine Werkzeug-Kategorien als Navigation.** Mit 107
Werkzeugen wäre jede Kategorienleiste entweder zu grob, um zu helfen, oder
zu fein, um sie zu überblicken. Und sie würde suggerieren, dass man erst
einen Bereich wählen muss. Das muss man bei Sarvis nicht.

Kategorien **ja**, aber an zwei Stellen, wo sie wirklich helfen:

1. **Als Startvorschläge** auf dem leeren Bildschirm. Sechs Knöpfe, die
   einen Satz einsetzen, keine Menüs.
2. **Als Filter in der Ablage** (Dateien, Blätter, Erinnerungen).

Vorschlag für die sechs Bereiche, passend zu Sarvis' Werkzeugumfang:

| Bereich | umfasst (Werkzeuge) | Beispiel-Vorschlag |
|---|---|---|
| **Mein Tag** | Kalender, Aufgaben, Timer/Wecker, Wetter, Merkzettel | „Was steht heute an?“ |
| **Nachrichten** | Mail, Telegram, Kontakte | „Hab ich was Wichtiges bekommen?“ |
| **Geld** | Finanzen, Daueraufträge | „Wie stehe ich diesen Monat?“ |
| **Unterwegs** | Verkehr, Tanken, Route, Wetterwarnungen | „Wie komme ich am besten nach …?“ |
| **Wissen & Dateien** | Websuche, Recherche-Aufträge, Drive, Eingang, Dokumente, Gedächtnis | „Fass mir die Datei zusammen“ |
| **Unterhaltung** | Musik, Radio, Nachrichten | „Spiel was Ruhiges“ |

Projekte/Programme/Entwicklung bewusst **nicht** als Bereich: Das sind
Saschas Bastelwerkzeuge, keine Alltagseinstiege. Sie bleiben über Sprache
erreichbar.

---

## 4. Artifacts und Canvas, und wie Sarvis das sicher könnte

### Was das ist

- **Claude Artifacts:** Inhalte, die neben dem Chat in einem eigenen Fenster
  stehen: Dokumente, Code, Diagramme, **interaktive HTML/React-Seiten**.
  Seit Juni 2025 können sie selbst Claude aufrufen („KI-gestützte
  Artifacts“). Seit Oktober 2025 haben sie dauerhaften Speicher (20 MB je
  Artifact, nur veröffentlichte) und Zugriff auf MCP-Connectors. Sie haben
  Versionen, lassen sich teilen und als Mini-App weitergeben.
- **ChatGPT Canvas:** eine Bearbeitungsfläche neben dem Chat für Text und
  Code. Man markiert Stellen und lässt sie umschreiben, hat
  Kurzbefehle (kürzer, Lesestufe, Emojis, Code prüfen) und eine
  Versionsgeschichte. HTML/React wird in einer Sandbox gerendert. Export
  als PDF, DOCX, MD.

Kern beider Ideen: **Etwas Bleibendes, an dem man gemeinsam weiterarbeitet**,
statt einer Antwort, die im Verlauf nach oben rutscht.

### Wie die Großen das absichern

Ein Sicherheitsbericht (Pluto Security, 2026) hat Claude Artifacts
vermessen:

- **Jedes Artifact bekommt eine eigene Herkunft**:
  `<uuid>.frame.claudeusercontent.com`, also eine *andere Domain* als
  claude.ai. Zwei Artifacts sehen sich nicht. Die Sitzung des Nutzers auf
  claude.ai ist damit außer Reichweite.
- **Skripte sind erlaubt, das Netz ist zu:**
  `script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:`, aber
  `connect-src 'self'; form-action 'self'; webrtc 'block'`. Kamera,
  Mikrofon und Standort sind gesperrt. Im Test kam über fetch, XHR,
  WebSocket, Bild-Beacon und sendBeacon nichts nach draußen.
- **Zugriffe auf Konten laufen nur über die Elternseite**, per
  `postMessage`-Brücke ohne Token, mit den Rechten des Betrachters.
- Anthropic selbst (2024): iframe-Sandbox, Prozess-Isolation, strenge CSP.
- **MCP Apps** (Standard seit 26.01.2026, SEP-1865) gehen genauso vor:
  `ui://`-Ressource, Sandbox-iframe, nur `postMessage`, kein Zugriff auf
  DOM, Cookies oder Speicher der Gastgeberseite. CSP standardmäßig
  „nichts erlaubt“. Werkzeuge ruft die Seite **nicht selbst** auf, der
  Host vermittelt.
- ChatGPT Canvas rendert ebenfalls in einer Sandbox. Laut OpenAI kann das
  Rendern allerdings externe Netzanfragen auslösen, die Sandbox ist dort
  also offener.

**Die Lehre:** Die Großen verbieten Skripte nicht. Sie verbieten, dass
Skripte **etwas erreichen**: keine fremde Herkunft, kein Netz, keine
Schlüssel, Handlungen nur über die Elternseite.

### Lohnt sich das für Sarvis?

**Interaktive Artefakte: ja, aber als zweite Stufe und eng begrenzt.**
Für einen Sprachassistenten am Handy ist das meiste, was man „sehen“ will,
mit Blatt, Seite und Kachel schon gedeckt. Interaktiv lohnt sich bei:

- Checklisten zum Abhaken (Einkauf, Packliste)
- kleinen Rechnern („was kostet die Finanzierung bei x %“, mit Schieberegler)
- sortier- und filterbaren Tabellen (Buchungen, Vergleiche)
- Diagrammen zum Antippen (Werte bei Berührung)

**Canvas-artiges Weiterbearbeiten: ja, und das ist wichtiger.** „Mach den
zweiten Absatz kürzer“, „füg noch die Kosten hinzu“: Das geht schon heute
per Sprache, wenn ein Blatt **eine Versionsgeschichte** bekommt und
dauerhaft in der Ablage bleibt. Dafür braucht es keine Skripte.

### Wie Sarvis interaktive Artefakte sicher anbieten könnte

Die heutige Regel (kein `allow-scripts`) bleibt für **alle Blätter aus
Modellausgabe** bestehen. Interaktive Artefakte werden eine **eigene,
vierte Sorte** mit eigenem Zaun:

1. **Eigene Herkunft.** Ausliefern von einer eigenen Domain, im Idealfall
   einer *anderen registrierbaren Domain* (nicht nur einer Subdomain von
   tech-artist.de), damit Browser sie als fremde Website behandeln. Das ist
   das Muster `claudeusercontent.com`. Mindestens aber eine eigene
   Subdomain ohne Cookies.
2. **iframe mit `sandbox="allow-scripts"`, niemals zusätzlich
   `allow-same-origin`.** Die Kombination aus beidem hebt die Sandbox auf.
3. **CSP ohne Netz:** `default-src 'none'; script-src 'unsafe-inline';
   style-src 'unsafe-inline'; img-src data:; connect-src 'none';
   form-action 'none'; frame-ancestors https://sarvis.tech-artist.de`.
   Alle Daten stecken beim Erzeugen schon in der Seite, nachladen kann sie
   nichts. Keine fremden Bibliotheken vom CDN. Wenn Diagramm- oder
   React-Code nötig ist, liefert Sarvis eine feste, geprüfte Kopie von
   derselben Artefakt-Domain.
4. **Keine Handlungen aus dem Artefakt.** Die Seite darf per `postMessage`
   höchstens einen **Vorschlag** schicken („Eintrag 3 abgehakt“, „Termin
   für Freitag vorschlagen“). Die App gibt ihn als normalen Zuruf an
   Sarvis weiter. Dort greifen die üblichen Stufen und Rückfragen. Die
   App prüft `event.origin` und nimmt nur eine feste Liste an
   Nachrichtenarten an.
5. **Kein Geräteschlüssel in Reichweite.** Durch die fremde Herkunft
   kommt die Seite nicht an `localStorage` der App. Das ist der Grund für
   Punkt 1.
6. **Herkunft der Inhalte beachten.** Hat Sarvis in derselben Runde fremde
   Webseiten oder Mails gelesen, entsteht nur die Variante ohne Skripte.
   Das ist dieselbe Logik wie heute bei der Browser-Stufe.
7. **Ein Schalter je Blatt:** „interaktiv“ ist eine Entscheidung des
   Werkzeugs (`artefakt_zeigen`), keine Lockerung von `blatt_zeigen`.

So bleibt der Satz aus DRAHT.md wahr: Was aus Modellausgabe gebaut wird,
kann sich ansehen lassen, aber nichts tun.

---

## 5. Sprachinteraktion: was sie „rund“ macht

| Thema | Richtwert / Praxis | Sarvis heute |
|---|---|---|
| **Pause zwischen Sprechern** | Menschen wechseln nach ~200–300 ms (Gesprächsforschung, z. B. Stivers u. a. 2009). GPT-4o antwortete laut OpenAI im Mittel nach 320 ms, ein reines Sprachmodell ohne Werkzeuge | – |
| **Ende-zu-Ende-Ziel** | **~800 ms** vom Satzende bis zum ersten hörbaren Ton gilt in der Branche als Faustregel. Unter ~1,5 s fühlt es sich noch nach Gespräch an | 1,07–2,02 s gemessen, **plus** 0,55–1,4 s Stille-Warten. Gefühlt also 1,6–3,4 s |
| **Satzende erkennen** | Feste Stille-Zeitgrenzen kosten jede Runde ihre volle Länge („700 ms Timeout = 700 ms mehr pro Runde“). Stand der Technik: ein **Modell**, das an Klang und Wortlaut erkennt, ob der Satz fertig ist (OpenAI `semantic_vad` mit „eagerness“, LiveKit Turn Detector, Pipecat Smart Turn). Laut Herstellern spart das 300–500 ms je Runde bei weniger Unterbrechungen | feste 0,55 s / 1,4 s, gut durchdacht, aber starr |
| **Unterbrechen (Barge-in)** | Ton sofort stoppen, auch bereits gepufferten. Innerhalb von ~100 ms unterscheiden, ob jemand wirklich unterbricht oder nur „mhm“ sagt. Echo-Unterdrückung, damit der Assistent sich nicht selbst hört. Messgröße: erste Silbe bis Stille | über Taste, Weckwort und Stoppwort sauber gelöst (`_unterbrechen` stoppt Ton, Auftrag und Claude). Bloßes Dazwischenreden geht nicht |
| **Satzweise sprechen** | Pflicht. Der erste Satz geht in die Sprachausgabe, sobald er fertig ist | ✅ |
| **Füllsätze** | Nur wenn wirklich gewartet wird (Werkzeug > ~1–2 s), kurz und abwechselnd („Moment, ich schau nach“). Nie vor schnellen Antworten | vorhanden (Wartesatz). Issue 007 meldet, dass er nicht immer erreichbar ist |
| **Rückfragen-Disziplin** | Nur fragen, wenn die Antwort etwas ändert oder eine Handlung nach außen geht. Höchstens eine Frage auf einmal, mit Vorschlag („Freitag um 10, passt das?“) | stark: Stufen, Freigabe-Fenster, „eine Zustimmung je Auftrag“ (Commit 597fa76) |
| **Weiterreden ohne Namen** | Nach einer Antwort kurz offen bleiben. Home Assistant tut das nur, wenn das Modell eine Frage stellt, Nutzer wünschen sich mehr | 18 s Nachhören, besser als HA |
| **Sprechen und Lesen trennen** | Kurz sprechen, Details zeigen | ✅ Kacheln/Blätter, Systemprompt regelt das |

**Fazit Sprache:** Sarvis ist hier schon gut und durchdacht. Die zwei
spürbaren Hebel sind **ein Satzende-Modell statt fester Stille** (spart
wahrscheinlich 0,3–0,8 s je Runde) und **Unterbrechen durch einfaches
Losreden**. Beides gehört nach der Oberfläche in die Reihe, nicht davor.

---

## 6. Zielbild: wie die App aussehen sollte

### Grundsatz

**Sprache zuerst, aber alles bleibt lesbar.** Der heutige Ring mit
Kacheln ist schön und bleibt. Er wird aber vom Hauptbildschirm zur
**Sprechansicht**. Hauptbildschirm wird ein Gesprächsverlauf, wie ihn jeder
von Messengern kennt.

### Bildschirme

**1. Gespräch (Hauptbildschirm)**
- Oben: Name des aktuellen Fadens, Knopf „Neu“, Verbindungsanzeige.
- Mitte: Verlauf als Blasen. Gesprochenes erscheint als Text,
  Sarvis' Antworten ebenso. Blätter, Berichte, Dateien und Kacheln
  erscheinen **als Karten im Verlauf** und öffnen sich beim Antippen groß.
  Sie verschwinden also nicht mehr nach 45 Sekunden.
- Rückfragen erscheinen als Karte mit **Ja / Nein**. Gesprochen
  antworten geht weiterhin.
- Unten: großer Mikrofonknopf (halten oder antippen), Textfeld,
  „+“ für Datei/Foto/Kamera.
- Leerer Faden: die sechs Startvorschläge aus Abschnitt 3.
- Laufende Hintergrundaufträge als schmale Leiste über dem Eingabefeld
  (heute `hintergrund`).

**2. Sprechansicht (Vollbild)**
- Der bekannte Ring mit Kacheln, für freihändig, Auto, Küche.
- Wechselt automatisch, wenn per Weckwort gesprochen wird oder der
  Auto-Modus an ist. Wischen nach unten führt zurück zum Verlauf.

**3. Fäden (Seitenleiste / Liste)**
- Gespräche nach Datum, umbenennbar, durchsuchbar.
- Optional „angeheftete“ Fäden je Thema (Urlaub, Auto, Finanzen) als
  einfache Form von Projekten: Ein Faden mit eigenen Notizen und Dateien.

**4. Ablage**
- Alles, was Sarvis erzeugt oder bekommen hat: Blätter, Berichte, Dateien,
  Uploads. Filter nach den sechs Bereichen und nach Art.
- Jedes Blatt mit Versionen („vorherige Fassung“).
- Teilen über das Teilen-Menü des Handys.

**5. Geplant**
- Wecker, Erinnerungen, wiederkehrende Aufgaben, laufende Aufträge.
  Pausieren, löschen, ändern, wie ChatGPTs Seite „Scheduled“.

**6. Gedächtnis & Einstellungen**
- Was Sarvis über Sascha weiß (gemerkt / beobachtet / entschieden,
  Personen), mit Löschen.
- Stimme, Weckwort an/aus, Ruhezeiten, Geräte, Benachrichtigungen.

### Was auf dem Server passieren muss

Reihenfolge nach Wirkung pro Aufwand. Die Aufwände sind grobe Schätzungen
für einen Agenten, der den Code kennt.

| # | Baustein | Was genau | Aufwand |
|---|---|---|---|
| **1** | **Gesprächsverlauf am Draht** | Neue Arten, z. B. `verlauf` (letzte N Einträge beim Verbinden) und `eintrag` (je Zuruf/Antwort/Karte mit fester ID). Der Server speichert Einträge selbst (SQLite in `/srv/data/sarvis`), statt sie aus der SDK-Sitzungsdatei zu kratzen. Blätter und Kacheln bekommen einen Verweis im Eintrag. Alte Oberflächen ignorieren die neuen Arten, das erlaubt DRAHT.md ausdrücklich | 2–3 Tage |
| **2** | **Chat-Oberfläche in der PWA** | Bildschirm „Gespräch“ mit Karten, Ja/Nein-Karten für Rückfragen, Ring als Sprechansicht. Datei-/Foto-Knopf an `POST /datei` anschließen (der Endpunkt existiert) | 3–5 Tage |
| **3** | **Push-Benachrichtigungen** | Web Push (VAPID) im Service Worker. Der Melder (`main.py` `_melden_sprechen`) schickt Push, wenn keine Oberfläche verbunden ist. Android-PWA kann das, iOS nur als installierte Web-App | 1–2 Tage |
| **4** | **Ablage + Versionen** | Blätter nicht nach 7 Tagen löschen, sondern in die Ablage übernehmen (Kennung bleibt geheim, Frist nur für die *Adresse* ohne Anmeldung). Neue Fassung einer `kennung` legt Version an statt zu überschreiben. Werkzeug `ablage_suchen` | 2 Tage |
| **5** | **ICS + VCF (+ PNG)** | zwei neue Sorten in `dokument.py` (reiner Text), PNG über den vorhandenen Chrome | 0,5–1 Tag |
| **6** | **Gesprächsfäden** | Mehrere SDK-Sitzungen bzw. Sitzungswechsel (`resume`) je Faden. Das Gedächtnis bleibt fadenübergreifend. Achtung: Die Startzeit von 5 s je neuer Sitzung (README) muss man durch einen vorgewärmten Ersatz-Client verstecken | 3–4 Tage |
| **7** | **Geplante KI-Aufgaben** | Wecker um einen „Auftrag“ erweitern. Zur Zeit X läuft ein Hintergrundauftrag (`auftrag.py` existiert) und meldet per Push/Stimme das Ergebnis. Beispiel: Morgenbriefing | 1–2 Tage |
| **8** | **Satzende-Modell + Losreden** | Ein Turn-Detection-Modell (z. B. Pipecat Smart Turn, läuft auf CPU) vor die festen Stillezeiten setzen. Unterbrechen bei eigener Stimme ohne Namen, wenn Kopfhörer erkannt sind (`config.REINREDEN` deutet das schon an) | 2–4 Tage, mit Messung |
| **9** | **Interaktive Artefakte** | Eigene Domain, Sorte `artefakt`, CSP und `postMessage`-Vorschläge wie in Abschnitt 4. Erst nach 1–4, weil sie den Verlauf und die Ablage brauchen | 3–4 Tage |
| **10** | **Werkzeugwahl prüfen** | Messen, ob 107 Werkzeuge die Wahl verschlechtern. Falls ja: Werkzeugsuche/Aufschieben einschalten oder Werkzeuge nach Bereich bündeln | 1 Tag Messung |

Auf Live-Kamera und Bildschirmteilen würde ich vorerst verzichten. Das
braucht ein Echtzeit-Videomodell, und Claude über das Agent SDK ist dafür
nicht gebaut. Fotos per Upload decken 90 % der Fälle.

---

## Quellen

Anbieter, offizielle Seiten:
- Claude: Datei-Erstellung, Hilfeseite – https://support.claude.com/en/articles/12111783-create-and-edit-files-with-claude
- Claude: Ankündigung „Claude can now create and edit files“ – https://claude.com/blog/create-files
- Claude: Was sind Artifacts – https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them
- OpenAI: Canvas, Hilfeseite – https://help.openai.com/en/articles/9930697-what-is-the-canvas-feature-in-chatgpt-and-how-do-i-use-it
- OpenAI: Scheduled Tasks, Hilfeseite – https://help.openai.com/en/articles/10291617-tasks-in-chatgpt
- OpenAI: Realtime VAD / semantic_vad – https://developers.openai.com/de-DE/api/docs/guides/realtime-vad
- OpenAI: GPT-4o Ankündigung (232/320 ms) – https://openai.com/index/hello-gpt-4o/
- Google: Gemini Live mit Kamera/Bildschirm – https://blog.google/products-and-platforms/products/gemini/gemini-live-android-tips/

Sicherheit / Artifacts / MCP Apps:
- Pluto Security: Inside Claude Artifacts – https://pluto.security/blog/inside-claude-artifacts-how-your-agent-publishes-to-the-web/
- Simon Willison: How Anthropic built Artifacts (2024) – https://simonwillison.net/2024/Aug/28/how-anthropic-built-artifacts
- MCP Apps, Sandbox/Origins/CSP – https://sunpeak.ai/blogs/mcp-app-iframe-sandbox-origins-cors
- MCP Apps, Überblick – https://www.morphllm.com/mcp-apps
- KI-gestützte Artifacts (Juni 2025) – https://ppc.land/claude-artifacts-expand-to-enable-ai-powered-app-creation/

Fachpresse:
- Canvas mit HTML/React-Rendering – https://the-decoder.com/openais-chatgpt-gets-a-major-canvas-upgrade-with-html-and-react-code-rendering/
- Claude Datei-Erstellung (Engadget) – https://www.engadget.com/ai/claude-can-now-edit-and-create-files-including-excel-spreadsheets-143043937.html
- ChatGPT Scheduled Tasks ersetzt Pulse – https://www.digit.in/news/general/openai-is-retiring-chatgpt-pulse-and-replacing-it-with-scheduled-tasks-here-is-why.html/amp/
- Gemini Live für alle (9to5Google) – https://9to5google.com/2025/05/23/gemini-live-free-camera-screen-sharing/
- Gemini Live, heise – https://heise.de/-10424328
- Alexa+ Überblick (gemischte Quellenlage) – https://aisotools.com/blog/alexa-plus-review-2026 · https://www.outlookbusiness.com/technology/amazons-alexa-rolled-out-to-100000-users-ceo-andy-jassy-reveals
- Siri-Verschiebung – https://www.igeeksblog.com/apple-delays-gemini-powered-siri-features-ios-26-4-ios-27/
- Home Assistant: Streaming-TTS – https://community.home-assistant.io/t/streaming-tts-for-kokoro-kokoro-wyoming-assist-speaks-before-the-llm-finishes/1024691
- Home Assistant: Weiterreden – https://community.home-assistant.io/t/what-is-continued-conversation-for-voice-assistant-pe/864058
- Open WebUI vs. LibreChat – https://docs.openwebui.com/alternatives/librechat

UX und Werkzeugwahl:
- Nielsen zu hybriden KI-Oberflächen (Sekundärquelle) – https://martincheng.substack.com/p/beyond-chat-why-user-experience-design
- Prompt-Box-Paradox – https://thirteen23.substack.com/p/the-prompt-box-paradox
- Prompt-Controls in Chatbots – https://myhub.ai/items/prompt-controls-in-genai-chatbots-4-main-uses-and-best-practices
- Zu viele Werkzeuge / Tool Search – https://dev.to/tridaai/too-many-tools-hurt-agents-5bii · https://unified.to/blog/scaling_mcp_tools_with_anthropic_defer_loading

Sprache, Latenz:
- Picovoice: Latency, Turn-Taking, Barge-in – https://picovoice.ai/guide/voice-agents/voice-ux-latency-turn-taking/
- 800-ms-Regel – https://www.twig.so/blog/voice-ai-agents-latency-budget-800ms · https://builder.aws.com/content/3JDFAfXBiuwPP5MPzgf4RUWSAIp/the-800ms-rule-budgeting-latency-for-a-real-time-voice-agent-on-aws
- Turn-Taking 250 ms – https://tianpan.co/blog/2026-05-10-voice-agent-turn-taking-250ms-threshold-reshapes-architecture
- Wo Sprachagenten scheitern – https://aaif.io/blog/where-voice-agents-fail-in-production-part-1-latency-turns-and-interruptions
- Gesprächsforschung (Stivers u. a., PNAS 2009, Sprecherwechsel ~200 ms) – https://www.pnas.org/doi/10.1073/pnas.0903616106
