# -*- coding: utf-8 -*-
"""Rendert die Anzeige in eine PNG -- alle vier Zustaende, ueber einem
Verlauf von hell nach dunkel. Damit sieht man die Lesbarkeit, ohne die
Anzeige laufen lassen und den Bildschirm abfotografieren zu muessen."""
import math, sys
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QColor, QLinearGradient, QBrush
from PySide6.QtCore import Qt, QRectF
app = QApplication(sys.argv)
from sarvis.hud import Hud, BREITE, HOEHE, DECKKRAFT
from sarvis.anzeige import RUHIG, HOERT, DENKT, SPRICHT

zustaende = [
    (RUHIG,   0.0,  "", ""),
    (HOERT,   0.62, "du", "Wie wird das Wetter morgen in Hamburg?"),
    (DENKT,   0.0,  "du", "Wie wird das Wetter morgen in Hamburg?"),
    (SPRICHT, 0.55, "sarvis", "Morgen wird es wechselhaft, um die achtzehn Grad."),
]
gesamt = QImage(BREITE*2, HOEHE*2, QImage.Format_ARGB32_Premultiplied)
mal = QPainter(gesamt)
g = QLinearGradient(0, 0, BREITE*2, HOEHE*2)
g.setColorAt(0.0, QColor(238, 240, 243)); g.setColorAt(0.5, QColor(118, 122, 130))
g.setColorAt(1.0, QColor(20, 22, 28))
mal.fillRect(gesamt.rect(), QBrush(g))
for i, (z, pegel, wer, text) in enumerate(zustaende):
    h = Hud(lauschen=False)
    h.zustand = z; h.deckkraft = DECKKRAFT[z]
    h.pegel = pegel; h.geglaettet = pegel; h.tick = 1.7
    h.wer = wer; h.untertitel = text
    if z in (HOERT, SPRICHT):
        for k in range(len(h.verlauf)):
            h.verlauf[k] = max(0.05, pegel*(0.45+0.55*abs(math.sin(k*0.7))))
    if z == SPRICHT: h.werkzeuge["Websuche"][1] = 1.0
    bild = QImage(BREITE, HOEHE, QImage.Format_ARGB32_Premultiplied)
    bild.fill(Qt.transparent); h.render(bild)
    mal.drawImage((i % 2)*BREITE, (i//2)*HOEHE, bild)
    mal.setPen(QColor(255, 80, 80))
    mal.drawText(QRectF((i%2)*BREITE+12, (i//2)*HOEHE+8, 200, 20), Qt.AlignLeft, z)
mal.end()
ziel = sys.argv[1] if len(sys.argv) > 1 else "anzeige_vorschau.png"
gesamt.save(ziel); print("gespeichert:", ziel)
