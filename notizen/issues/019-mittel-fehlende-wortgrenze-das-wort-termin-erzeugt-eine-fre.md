# 019 — Fehlende Wortgrenze: das Wort "Termin" erzeugt eine Freigabe

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | falsche-annahme |
| **Bereich** | entscheidungen |
| **Fundstelle** | `sarvis/rueckfrage.py:164` |
| **Status** | behoben |

## Was ist falsch

Im Dauer-Regex steht die Wortgrenze \b nur HINTER der Einheit, nicht davor. "min" trifft deshalb mitten im Wort — "termin" endet auf "min". Da die Mengenangabe optional ist und \s* auch leer passt, liefert _dauer_lesen() dann 1 Minute, und freigabe_erkennen() (Zeile 155-158) macht daraus eine echte Freigabe, obwohl der Nutzer nur "ja" gesagt hat. Der Docstring behauptet das Gegenteil: "eine Freigabe muss man aussprechen, sie entsteht nicht aus Bequemlichkeit".

## Ablauf

Sarvis fragt "Soll ich Zahnarzt am Dienstag eintragen?". Der Nutzer antwortet "ja, trag den Termin ein". Nachgemessen: deuten -> 'ja', freigabe_erkennen -> 1.0. main.py:378-380 ruft _freigabe_erteilen mit minuten=None, dort greift freigabe_erkennen (main.py:433-434), und Sarvis sagt "Gut. Termine eintragen für 1 Minuten frage ich nicht mehr nach." — eine Erlaubnis, die niemand verlangt hat, dazu mit falscher Grammatik. Der zweite, schwerere Fall ist unabhängig von der Wortgrenze: "ja, ich habe in einer stunde einen termin" -> gemessen 60.0, also eine Stunde Blankoerlaubnis für dieses Werkzeug, weil irgendwo im Satz eine Zeitangabe stand. Da termin_anlegen nicht in _PFAD_WERKZEUGE steht, ist diese Freigabe zudem ortlos und gilt überall.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Widerlegungsversuche: (a) Vielleicht greift der Merker in main.py — nein, _abgelehnt (main.py:293) betrifft nur Nein/Anders. (b) Vielleicht verhindert erteilbar() es — termin_anlegen steht nicht in FREIGABE_NIE (config.py:666-669). (c) Vielleicht wird der Treffer durch group(1) verhindert — nein, group(1) ist optional und bleibt None, menge wird 1.0 (rueckfrage.py:171-172). Beide Sätze mit dem echten Modul gemessen: 1.0 bzw. 60.0. Bestätigt. Schwere mittel statt hoch: Der Wortgrenzenfall erzeugt nur eine Minute; der ernstere Teil (jede Zeitangabe im Satz erzeugt eine Freigabe) ist eine bewusste Entwurfsentscheidung in Zeile 153-158, die hier fehlgeht.

## Vorgeschlagene Behebung

Zwei Änderungen. Erstens rueckfrage.py:162-164: vor die Einheit einen negativen Rückblick setzen, kein \b (sonst bricht "30min"): r"(\\d+|" + "|".join(_ZAHLWORT) + r")?\\s*(?<![A-Za-zÄÖÜäöüß])(minuten|minute|min|stunden|stunde|std)\\b". Damit fällt "termin" heraus, "30 min" und "30min" bleiben. Zweitens Zeile 155-158: eine Zeitangabe allein nicht mehr als Freigabewunsch werten — if not any(re.search(m, t) for m in _FREIGABE): return None, und die erkannte Dauer danach nur noch zur Verfeinerung benutzen. _FREIGABE enthält mit r"für die nächste(n)" und r"die nächsten? \\S+ (minuten|stunde)" bereits die Wendungen, mit denen man eine Dauer wirklich ausspricht.

## Behebung

Drei Stellen: negativer Rueckblick vor der Einheit im Dauer-Regex, Freigabe nur noch bei ausgesprochener Wendung, und `immer\s+(erlaubt|frei)` -- dieselbe fehlende Wortgrenze machte "mach das immer freitags" zur Dauerfreigabe. Gemessen: "ja, trag den Termin ein" ergab vorher 1.0 Minuten Freigabe, jetzt None; "ja, ich habe in einer stunde einen termin" vorher 60.0, jetzt None.

Verhaltensaenderung: Eine reine Zeitangabe erzeugt keine Dauerfreigabe mehr. Es braucht eine ausgesprochene Wendung. Siehe auch [058], das denselben Bereich betrifft.
