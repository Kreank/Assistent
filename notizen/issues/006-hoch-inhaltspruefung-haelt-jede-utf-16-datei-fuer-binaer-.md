# 006 — Inhaltsprüfung hält jede UTF-16-Datei für binär und liest sie still

Status: erledigt (Commit b217416)

| | |
|---|---|
| **Schwere** | hoch |
| **Klasse** | stiller-abbruch |
| **Bereich** | entscheidungen |
| **Fundstelle** | `sarvis/schutz.py:414` |
| **Status** | behoben |

## Was ist falsch

inhalt_heikel() bricht ab, sobald in den ersten 4 KB ein Nullbyte steht, mit der Begründung "binaer, kein Textgeheimnis". UTF-16-kodierter Text — unter Windows PowerShell 5.1 der Normalfall für alles, was über Out-File oder ">" entsteht — besteht zur Hälfte aus Nullbytes. Damit fällt genau die Prüfung aus, die laut Modulkommentar (schutz.py:284-295) seit "D: als Ganzes frei" die alleinige Absicherung gegen unbekannt benannte Dateien ist.

## Ablauf

Zwei Dateien mit identischem Inhalt ("Kunde Meier / api_key = sk-liveAbCdEf1234567890xyz / Ende") unter D:\Privat abgelegt, einmal UTF-8, einmal UTF-16. Nachgemessen: lesen_stufe(utf-8) -> "fragen" (inhalt_heikel True), lesen_stufe(utf-16) -> "frei" (inhalt_heikel False). Auch durchsuchen_stufe(utf-16-Datei) -> "frei", weil es für Einzeldateien auf lesen_stufe durchreicht (schutz.py:172-174). Die UTF-16-Variante wird ohne Rückfrage geöffnet und der Schlüssel geht ans Modell. Der Nutzer bekommt nichts zu hören — es sieht aus, als sei die Datei einfach unverdächtig gewesen.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Widerlegungsversuche: (a) Namensliste HEIKEL (Zeile 28-39) — greift nur bei sprechenden Namen; "notizen16.txt" trifft keines der Muster (gemessen). (b) DOKUMENT_UNPRUEFBAR (Zeile 303-304) — .txt steht nicht darin. (c) FRAGEN_TROTZ_FREI — betrifft nur D:/Strato Server. (d) Der wohlwollende Grundsatz im Docstring ("Im Zweifel False") rechtfertigt das Auslassen von Binärdateien, nicht von Text: UTF-16 ist Text, und die Prüfung hätte den Schlüssel gefunden, wenn sie ihn hätte lesen können. Kein Aufrufer fängt es ab. Bestätigt.

## Vorgeschlagene Behebung

schutz.py:414-416 ersetzen: vor dem Binär-Abbruch auf UTF-16 prüfen und dann entsprechend dekodieren. Etwa: if roh[:2] in (b"\\xff\\xfe", b"\\xfe\\xff"): text = roh.decode("utf-16", errors="replace") — sonst, ohne BOM, den Nullbyte-Anteil messen (roh[:4096].count(0) > len(roh[:4096]) * 0.3 und jedes zweite Byte 0) und je nach Versatz utf-16-le bzw. utf-16-be dekodieren; erst wenn beides nicht zutrifft, bei b"\\x00" in roh[:4096] wie bisher False zurückgeben. Die Musterprüfung darunter (Zeile 418-425) bleibt unverändert.

## Behebung

Der Nullbyte-Abbruch ist in `_als_text()` gewandert (schutz.py:488-514): Mit BOM wird als UTF-16 dekodiert, ohne BOM entscheidet die Verteilung der Nullbytes (jedes zweite Byte auf Null, immer an derselben Stelle) zwischen `utf-16-le` und `utf-16-be`; erst wenn keins davon zutrifft, gilt die Datei wie bisher als binär und `inhalt_heikel()` gibt `False` zurück. Die Musterprüfung darunter blieb unverändert. Belegt mit vier Dateien gleichen Inhalts (`api_key = sk-live…`): UTF-8, UTF-16 LE mit BOM, UTF-16 BE mit BOM und UTF-16 LE ohne BOM ergeben jetzt alle `True` (vorher nur UTF-8), eine echte Binärdatei und ein harmloser Text weiter `False`. Gegenprobe über 430 echte Dateien im Projekt: kein einziges Ergebnis hat sich gegenüber vorher verändert, also kein neuer Fehlalarm.
