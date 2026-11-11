# 027 — ort_ansehen laeuft still, prueft nur die Namens-Stufe -- liest aber Dateiinhalt vor

Status: erledigt (Commit b217416; auf Linux erst wirksam seit 55db580)

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | falsche-annahme |
| **Bereich** | werkzeuge |
| **Fundstelle** | `sarvis/werkzeuge/projekte.py:442` |
| **Status** | behoben |

## Was ist falsch

Der Kommentar direkt darueber begruendet die Pruefung damit, dass hier 'dieselbe Grenze wie beim stillen Auflisten' gelte. auflisten_stufe ist in schutz.py:134 ausdruecklich als 'Nur Namen sehen, keine Inhalte' dokumentiert und prueft entsprechend weder heikel() noch inhalt_heikel(). lage() bleibt aber nicht bei Namen: es liest README.md und gibt 300 Zeichen Inhalt zurueck. Fuer diesen Griff waere lesen_stufe zustaendig, die vorher in die Datei hineinsieht.

## Ablauf

ort_ansehen steht in config.py:562 auf 'still', laeuft also ohne Rueckfrage. Der Nutzer sagt 'was liegt eigentlich in D:\Privat\altprojekt'. Liegt dort eine README.md, in der zu Beginn ein API-Schluessel notiert ist, wird sie gelesen und ihr Anfang an das Sprachmodell weitergereicht -- ohne Rueckfrage. Ueber datei_lesen bzw. lesen_stufe waere derselbe Zugriff auf 'fragen' gefallen, weil inhalt_heikel() vorher hineinsieht.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Widerlegungsversuch gescheitert. Gepruefte Kette: config.py:562 setzt ort_ansehen auf 'still', hirn.py:189-191 laesst 'still' ohne Rueckfrage durch. projekte.py:442 prueft nur auflisten_stufe; die Funktion (schutz.py:132-148) prueft NIE_SCHREIBEN/NIE_LESEN und FRAGEN_TROTZ_FREI, ruft aber weder heikel() noch inhalt_heikel() -- im Gegensatz zu lesen_stufe (schutz.py:113-129), die genau bei FREI_LESEN-Pfaden zusaetzlich inhalt_heikel() befragt. FREI_LESEN enthaelt D:/ ganz (config.py:470-474), der Unterschied zwischen beiden Stufen ist an dieser Stelle also exakt die Inhaltspruefung. lage() liest in projekte.py:224-230 README.md und haengt 300 Zeichen an. Ich habe geprueft, ob sonst noch Inhalt fliesst: _durchgehen (120-141) sammelt nur Namen/Endungen/mtime, _git_stand liest nur Git-Metadaten -- der README-Griff ist die einzige Stelle. Entlastend und deshalb nicht 'hoch': D:\Strato Server bleibt geschuetzt, weil FRAGEN_TROTZ_FREI (config.py:507-509) auch in auflisten_stufe geprueft wird; es fliessen hoechstens 300 Zeichen aus einer Datei, die der Nutzer selbst adressiert hat.

## Vorgeschlagene Behebung

In lage() vor dem Lesen die richtige Stufe verlangen: in Zeile 224-225 aus 'if liesmich.exists():' ein 'if liesmich.exists() and schutz.lesen_stufe(str(liesmich)) == "frei":' machen (schutz ist in der Datei bereits importiert, siehe Zeile 442) und im Else-Fall stattdessen 'README: vorhanden, nicht gelesen' anhaengen. Damit bleibt ort_ansehen still und schnell, und die Inhaltsgrenze gilt trotzdem an der einzigen Stelle, an der Inhalt gelesen wird. Den Kommentar in Zeile 438-441 entsprechend richtigstellen.

## Behebung

In `lage()` wird die README nur noch gelesen, wenn `schutz.lesen_stufe()` fuer genau diese Datei "frei" liefert; sonst steht dort "README: vorhanden, nicht gelesen". Der irrefuehrende Kommentar in `ort_ansehen` wurde richtiggestellt. Dass `lesen_stufe` anders entscheidet als `auflisten_stufe`, wurde an erfundenen Pfad-Zeichenketten belegt -- `D:\Strato Server` wurde dabei nicht angefasst.
