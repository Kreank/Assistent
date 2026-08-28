# 030 — Der Mausgriff wird beim Loslassen nicht zurueckgesetzt

| | |
|---|---|
| **Schwere** | niedrig |
| **Klasse** | zustand-haengt |
| **Bereich** | anzeige |
| **Fundstelle** | `sarvis/hud.py:242` |
| **Status** | behoben |

## Was ist falsch

mousePressEvent (hud.py:231) setzt self._griff nur bei der linken Maustaste, mouseReleaseEvent (hud.py:241) loescht ihn nicht wieder. Nach einem abgeschlossenen Zug bleibt der alte Versatz stehen. Jede folgende Mausbewegung mit einer ANDEREN gedrueckten Taste erfuellt die Bedingung in mouseMoveEvent und schiebt das Fenster mit dem veralteten Versatz -- es springt. Der Fehler ist auf den Verschiebemodus begrenzt, weil er ausserhalb davon gar keine Mausereignisse gibt.

## Ablauf

Verschiebemodus einschalten (die Anzeige nimmt dann Qt.WindowTransparentForInput weg, hud.py:224, und faengt ueber ihre volle Flaeche von 858x712 Bildschirmpunkten die Maus ab -- 660x548 mal ANZEIGE_SKALA 1.30, config.py:712). Ring mit links an die gewuenschte Stelle ziehen, loslassen -- _griff behaelt den Versatz dieses Zuges. Jetzt mit der rechten oder mittleren Taste in dieser Flaeche ziehen: mousePressEvent ignoriert die Taste, aber mouseMoveEvent sieht 'self._griff is not None' und setzt das Fenster auf Cursorposition minus altem Versatz. mouseReleaseEvent schreibt die verrutschte Position dann auch noch nach anzeige.json (_position_merken, hud.py:204).

## Warum das bestätigt wurde

Ein zweiter Reviewer hat versucht, diesen Fund zu widerlegen, und ist gescheitert:

Der Code ist genau so. Ich habe gezielt nach einer Absicherung gesucht und nur eine gefunden, die den Fall NICHT abfaengt: _verschiebemodus(False) setzt self._griff = None (hud.py:228) -- das raeumt erst beim VERLASSEN des Modus auf, nicht zwischen zwei Zuegen innerhalb desselben Modus. Auch die Initialisierung (hud.py:137, self._griff = None) hilft nur beim ersten Mal. Qt liefert mouseMoveEvent ohne setMouseTracking(True) nur bei gedrueckter Taste -- setMouseTracking wird nirgends im Modul aufgerufen, also ist die vom Reviewer beschriebene Bedingung (irgendeine Taste gedrueckt) genau richtig getroffen. Die Einstufung 'niedrig' bleibt: es braucht einen Rechts- oder Mittelklick-ZUG innerhalb des ohnehin selten aktiven Verschiebemodus.

## Vorgeschlagene Behebung

Zwei Zeilen. In hud.py:241-244 den Griff beim Loslassen aufraeumen und nur dann speichern, wenn wirklich gezogen wurde: 'def mouseReleaseEvent(self, e): if self.verschiebbar and self._griff is not None: self._griff = None; self._position_merken(); e.accept()'. Zusaetzlich in mouseMoveEvent (hud.py:236) auf die tatsaechlich gehaltene Taste pruefen: 'if self.verschiebbar and self._griff is not None and (e.buttons() & Qt.LeftButton):'. Das eine schliesst die Luecke, das andere macht sie unerreichbar, auch wenn spaeter jemand setMouseTracking einschaltet.

## Behebung

`mouseReleaseEvent` (hud.py) setzt `self._griff = None` und merkt die Position nur noch, wenn wirklich gezogen wurde; `mouseMoveEvent` prueft zusaetzlich `e.buttons() & Qt.LeftButton`, damit ein Zug mit einer anderen Taste den Pfad gar nicht erst erreicht. Beide Stellen haben einen Kommentar, der das beobachtete Springen benennt.

Belegt mit einem Rechenskript, das die drei Ereignisbehandler ohne Qt nachbaut und beide Staende gegeneinander laufen laesst: linker Zug, loslassen, danach ein Zug mit der rechten Taste. Vorher sprang das Fenster von (300,200) auf (420,320) und schrieb diese Position auch noch weg; jetzt bleibt es auf (300,200), und es wird nur eine Position gemerkt.
