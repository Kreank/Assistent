# 008 — Vollstaendige URL wird auf die Startseite verkuerzt -- der Link geht verloren

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | reihenfolge |
| **Bereich** | werkzeuge |
| **Fundstelle** | `sarvis/werkzeuge/programme.py:124` |
| **Status** | behoben |

## Was ist falsch

_adresse() schneidet aus dem Ziel zuerst alles bis zum ersten Punkt heraus und schlaegt DIESEN Rest in SEITEN nach -- noch bevor geprueft wird, ob das Ziel ueberhaupt eine fertige Adresse ist. Aus einer vollstaendigen URL zu einer der 14 bekannten Seiten wird damit die blosse Startseite; Pfad und Parameter werden stumm verworfen. Der Zweig _SIEHT_AUS_WIE_ADRESSE ab Zeile 132 wird bei diesen Seiten nie erreicht.

## Ablauf

Nutzer: 'mach mir den GitHub-Link zu anthropics/claude-code auf'. web_oeffnen bekommt ziel='https://github.com/anthropics/claude-code', _adresse() liefert ('https://github.com', 'Github'). Es oeffnet die Startseite, Sarvis sagt 'Github ist offen.' -- kein Fehler, kein Hinweis. Dasselbe bei jedem YouTube-Video und jedem Amazon-Artikel. Nicht betroffen sind Adressen ausserhalb von SEITEN.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Widerlegungsversuch gescheitert. Nachgemessen mit den Zeilen 122-124: 'https://github.com/anthropics/claude-code' -> 'github', 'https://www.youtube.com/watch?v=abc' -> 'youtube', 'amazon.de/dp/B08XYZ' -> 'amazon'. Alle drei Schluessel stehen in SEITEN (Zeile 85-110), also greift Zeile 126 und Zeile 132 ist tot. Kein Aufrufer faengt das ab: web_oeffnen (Zeile 302-309) reicht 'ziel' unveraendert durch, steht auf 'still' (config.py:588) und wird im Systemprompt nirgends eingeschraenkt (grep nach 'web_oeffnen' in sarvis/: nur config.py:588). Die Werkzeugbeschreibung laedt sogar ausdruecklich zu vollstaendigen Adressen ein (programme.py:290-291). Einzige Entlastung: 'https://heise.de/news/x' -> 'heise' steht nicht in SEITEN und laeuft korrekt ueber Zeile 132 -- der Schaden bleibt auf die 14 bekannten Domains beschraenkt, und genau die sind die haeufigsten.

## Vorgeschlagene Behebung

Reihenfolge in _adresse() umdrehen: vor der SEITEN-Aufloesung pruefen, ob das Ziel wie eine Adresse aussieht UND einen Pfad, Query oder Fragment hat. Konkret vor Zeile 126 einfuegen: rest = re.sub(r'^(https?://)?(www\.)?', '', ziel.strip()); if _SIEHT_AUS_WIE_ADRESSE.match(ziel) and re.search(r'[/?#]', rest.rstrip('/')): dann sofort die Adresse zurueckgeben (mit https:// davor, falls es fehlt). Die SEITEN-Suche in Zeile 126-130 bleibt danach fuer blosse Namen ('youtube') und nackte Domains ohne Pfad ('youtube.com') zustaendig.

## Behebung

`_adresse()` prueft jetzt VOR der SEITEN-Aufloesung, ob das Ziel wie eine Adresse aussieht und Pfad, Query oder Fragment traegt -- dann wird es unveraendert durchgereicht. Gemessen: `https://github.com/anthropics/claude-code` blieb vorher als `https://github.com` uebrig, jetzt bleibt die volle Adresse. 11 Faelle geprueft, `youtube`, `youtube.com` und die Suchform laufen unveraendert.

Nachtrag (nicht vom Subagenten): Der neue Zweig verwarf einen mitgegebenen Suchbegriff stumm, waehrend die Antwort weiterhin "Suche nach ..." sagte -- dieselbe Fehlerklasse. `_adresse()` gibt jetzt als drittes Stueck zurueck, ob die Suche verwendet wurde, und der Aufrufer sagt es, wenn nicht.
