# 044 — Telegram-Verbindungen werden bei jedem Neuaufbau liegengelassen

Status: erledigt (Commit b217416; schliessen() wird inzwischen beim Beenden in main.py gerufen)

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | ressource-leck |
| **Bereich** | aussenwelt |
| **Fundstelle** | `sarvis/werkzeuge/telegram.py:40` |
| **Status** | behoben |

## Was ist falsch

Ist der Klient nicht mehr verbunden, wird ein neuer TelegramClient gebaut, ohne den alten zu trennen; im Zweig 'nicht autorisiert' wird _klient auf None gesetzt, die offene Verbindung bleibt bestehen. schliessen() existiert (Zeile 45-52), wird aber im ganzen Projekt nirgends aufgerufen -- das habe ich mit einer Suche ueber alle .py-Dateien bestaetigt, es findet sich nur die Definition.

## Ablauf

Der Zweig 'nicht verbunden' wird selten erreicht, weil Telethon mit auto_reconnect selbst wieder aufbaut und is_connected() dann wieder True liefert; dort leckt hoechstens gelegentlich ein Klient samt seinen Netzwerk-Tasks. Sicher trifft es den Zweig 'nicht autorisiert': Ist die Sitzung am Telefon widerrufen worden, verbindet JEDER Telegram-Aufruf neu, stellt fest, dass er nicht autorisiert ist, setzt _klient = None und laesst die Verbindung offen. Der Nutzer bekommt dabei aber bei jedem Aufruf die Meldung 'Telegram ist nicht angemeldet' -- er merkt den Zustand sofort und wird ihn nicht hundertfach wiederholen.

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Zeile 29-42: kein disconnect() vor dem Neuaufbau in Zeile 38 und keins in Zeile 41. Ein Auffangnetz habe ich gesucht und nicht gefunden -- kein Aufrufer von telegram.schliessen(), auch nicht beim Herunterfahren in main.py. Herabgestuft auf niedrig: Der haeufig unterstellte Pfad (Verbindungsabbruch) wird durch Telethons eigenes Wiederverbinden meist gar nicht erreicht, und der sichere Pfad (nicht autorisiert) ist ein Dauerfehlerzustand, der dem Nutzer bei jedem Aufruf laut gemeldet wird und deshalb nicht lange besteht.

## Vorgeschlagene Behebung

In klient() vor dem Neuaufbau aufraeumen: In Zeile 30 den Fall 'alter Klient existiert, ist aber nicht verbunden' abfangen und dort 'try: await _klient.disconnect() except Exception: pass' ausfuehren, bevor Zeile 38 einen neuen baut. In Zeile 40-41 vor '_klient = None' ebenfalls 'await _klient.disconnect()' setzen. Zusaetzlich schliessen() beim Herunterfahren von Sarvis aufrufen, sonst bleibt die Funktion toter Code.

## Behebung

In klient() wird vor dem Neuaufbau aufgeraeumt: Ist der alte Klient
vorhanden, aber nicht verbunden, wird er getrennt und verworfen; im
Zweig 'nicht autorisiert' wird ebenfalls getrennt, bevor _klient auf
None geht. Belegt mit Attrappen (falsches telethon-Modul, kein
Netzzugriff): beide Zweige rufen disconnect() genau einmal und
hinterlassen _klient = None. NICHT erledigt ist der dritte Teil des
Vorschlags — schliessen() beim Herunterfahren aufzurufen, denn das
stuende in main.py, die nicht zu den freigegebenen Dateien gehoerte.
schliessen() bleibt damit vorerst ohne Aufrufer.
