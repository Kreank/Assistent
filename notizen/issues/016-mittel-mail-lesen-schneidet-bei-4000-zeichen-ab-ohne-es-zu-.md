# 016 — mail_lesen schneidet bei 4000 Zeichen ab, ohne es zu kennzeichnen

| | |
|---|---|
| **Schwere** | mittel |
| **Klasse** | stiller-abbruch |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/google.py:573` |
| **Status** | behoben |

## Was ist falsch

Der Mailtext wird hart auf 4000 Zeichen gekuerzt, ohne Markierung und ohne die dafuer vorhandene Konstante LESE_GRENZE (Zeile 179). drive_lesen macht es an derselben Grenze richtig und haengt '[… gekuerzt]' an.

## Ablauf

Nutzer: "Lies mir die Mail von der Werkstatt vor." Die Mail ist laenger als 4000 Zeichen (Angebot, langer Verlauf, Newsletter). Claude bekommt einen mitten im Satz abgeschnittenen Text ohne Hinweis und liest ihn als vollstaendige Mail vor oder fasst sie zusammen und laesst den entscheidenden Schluss weg. Weder Modell noch Nutzer koennen merken, dass etwas fehlt.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Zeile 573 'text = _text_aus(n.get("payload", {}))[:4000]' -- die Zahl steht doppelt im Modul, obwohl LESE_GRENZE in Zeile 179 genau dafuer definiert ist; danach wird der Text in Zeile 574-576 ungekennzeichnet ausgegeben. Der Gegenbeleg des Reviewers stimmt: Zeile 995-999 in drive_lesen setzt '[… gekuerzt]', Zeile 1071-1073 in tabelle_lesen macht es mit '[… N weitere Zeilen]' ebenso. mail_lesen ist die einzige Ausnahme, ein Auffangnetz gibt es nirgends. Mails ueber 4000 Zeichen sind haeufig genug, um mittel zu rechtfertigen.

## Vorgeschlagene Behebung

Zeile 573 durch dasselbe Muster wie drive_lesen ersetzen: 'text = _text_aus(n.get("payload", {}))' / 'gekuerzt = ""' / 'if len(text) > LESE_GRENZE: text, gekuerzt = text[:LESE_GRENZE], "\n[… gekuerzt]"' und in Zeile 576 '+ (text or "(kein lesbarer Text)") + gekuerzt'.

## Behebung

`mail_lesen` nutzt die Konstante `LESE_GRENZE` statt der doppelt verdrahteten 4000 und haengt bei Ueberlaenge "[... gekuerzt]" an -- dasselbe Muster wie `drive_lesen`.
