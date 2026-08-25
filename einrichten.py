# -*- coding: utf-8 -*-
"""Einmalige Einrichtung: Symbol erzeugen und Sarvis bei Windows anmelden.

Windows zeigt Benachrichtigungen nur dann unter einem eigenen Namen an,
wenn eine Anwendungskennung (AppUserModelID) registriert ist. Registriert
wird sie über eine Verknüpfung im Startmenü, in der diese Kennung als
Eigenschaft steckt. Ohne das erscheint jede Meldung als „Python".

Aufruf:  .venv\\Scripts\\python.exe einrichten.py
"""
import math
import sys

from sarvis import config
from sarvis.hinweis import KENNUNG


def symbol_erzeugen() -> bool:
    """Malt das Ringmotiv der Anzeige als .ico.

    Dasselbe Bild wie im Overlay, damit die Benachrichtigung erkennbar
    zu Sarvis gehört und nicht nach Standardsymbol aussieht.
    """
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QColor, QImage, QPainter, QPen, QRadialGradient
    from PySide6.QtCore import QPointF, Qt

    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    kante = 256
    bild = QImage(kante, kante, QImage.Format_ARGB32)
    bild.fill(Qt.transparent)
    p = QPainter(bild)
    p.setRenderHint(QPainter.Antialiasing)
    mitte = QPointF(kante / 2, kante / 2)
    farbe = QColor(0, 229, 255)

    dunkel = QRadialGradient(mitte, kante / 2)
    dunkel.setColorAt(0.0, QColor(14, 22, 38, 255))
    dunkel.setColorAt(1.0, QColor(8, 12, 22, 235))
    p.setPen(Qt.NoPen)
    p.setBrush(dunkel)
    p.drawEllipse(mitte, kante / 2 - 2, kante / 2 - 2)

    # Strahlenkranz wie im Overlay
    innen, balken = 62, 56
    for i in range(balken):
        winkel = -math.pi / 2 + 2 * math.pi * i / balken
        laenge = 16 + 14 * abs(math.sin(i * 0.9))
        ci, si = math.cos(winkel), math.sin(winkel)
        f = QColor(farbe)
        f.setAlphaF(0.45 + 0.45 * abs(math.sin(i * 0.9)))
        p.setPen(QPen(f, 4.0, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(
            QPointF(mitte.x() + ci * (innen + 8), mitte.y() + si * (innen + 8)),
            QPointF(mitte.x() + ci * (innen + 8 + laenge),
                    mitte.y() + si * (innen + 8 + laenge)),
        )

    p.setBrush(Qt.NoBrush)
    ring = QColor(farbe)
    ring.setAlphaF(0.9)
    p.setPen(QPen(ring, 5.0))
    p.drawEllipse(mitte, innen, innen)

    kern = QRadialGradient(mitte, 34)
    hell = QColor(farbe)
    hell.setAlphaF(0.95)
    aus = QColor(farbe)
    aus.setAlpha(0)
    kern.setColorAt(0.0, hell)
    kern.setColorAt(1.0, aus)
    p.setPen(Qt.NoPen)
    p.setBrush(kern)
    p.drawEllipse(mitte, 34, 34)
    p.setBrush(QColor(238, 248, 255, 240))
    p.drawEllipse(mitte, 11, 11)
    p.end()

    config.SYMBOL.parent.mkdir(parents=True, exist_ok=True)
    if not bild.save(str(config.SYMBOL)):
        print(f"  Symbol liess sich nicht schreiben: {config.SYMBOL}")
        return False
    print(f"  Symbol angelegt : {config.SYMBOL}")
    return True


def verknuepfung_anlegen() -> bool:
    """Startmenü-Verknüpfung mit der Anwendungskennung.

    Der eigentliche Zweck ist nicht die Verknüpfung, sondern die
    Eigenschaft System.AppUserModel.ID darin — daran erkennt Windows
    die Meldungen als von Sarvis.
    """
    try:
        import pythoncom
        from win32com.propsys import propsys, pscon
        from win32com.shell import shell
    except ImportError:
        print("  pywin32 fehlt:  pip install pywin32")
        return False

    ziel = config.WURZEL / "starten.bat"
    verkn = config.VERKNUEPFUNG
    verkn.parent.mkdir(parents=True, exist_ok=True)

    link = pythoncom.CoCreateInstance(
        shell.CLSID_ShellLink, None,
        pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink,
    )
    link.SetPath(str(ziel))
    link.SetWorkingDirectory(str(config.WURZEL))
    link.SetDescription("Sarvis — persönlicher Sprachassistent")
    if config.SYMBOL.exists():
        link.SetIconLocation(str(config.SYMBOL), 0)

    laden = link.QueryInterface(pythoncom.IID_IPersistFile)
    speicher = link.QueryInterface(propsys.IID_IPropertyStore)
    speicher.SetValue(
        pscon.PKEY_AppUserModel_ID,
        propsys.PROPVARIANTType(KENNUNG, pythoncom.VT_LPWSTR),
    )
    speicher.Commit()
    laden.Save(str(verkn), 0)

    print(f"  Verknüpfung     : {verkn}")
    print(f"  Kennung         : {KENNUNG}")
    return True


def main() -> int:
    if sys.platform != "win32":
        print("Nur unter Windows nötig.")
        return 0
    print("\n  Sarvis einrichten\n" + "  " + "-" * 40)
    symbol_erzeugen()
    if not verknuepfung_anlegen():
        return 1

    print("\n  Probe wird gesendet ...")
    from win11toast import notify
    notify(
        title="Sarvis ist eingerichtet",
        body="Ab jetzt melden sich Timer und Erinnerungen hier — "
             "und bleiben im Info-Center stehen.",
        app_id=KENNUNG,
        icon={"src": str(config.SYMBOL), "placement": "appLogoOverride",
              "hint-crop": "circle"} if config.SYMBOL.exists() else None,
    )
    print("  Erschienen? Dann steht sie jetzt auch im Info-Center.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
