"""Erzeugt die zwei Logo-Bilder des Windows-Installers (emm943).

Nutzer 15.11.2026: "hier ist das Logo bitte bau es ein, es darf auch
kleiner sein". Inno Setup zeigt zwei Bilder: ein hohes auf der
Willkommens- und Abschluss-Seite (164 x 314) und ein kleines oben rechts
auf allen anderen Seiten (55 x 58). Beide entstehen hier aus DERSELBEN
Datei wie das Programm-Symbol (eve_trader/ui/assets/logo.png) - in
doppelter Groesse, damit sie auf 125/150/200 % nicht verwaschen; Inno
Setup skaliert sie selbst herunter.

Aufruf (nur noetig, wenn sich das Logo aendert):
    python werkzeuge/mache_installer_bilder.py
Schreibt installer_gross.bmp und installer_klein.bmp neben installer.iss.
BMP, weil das jede Inno-Setup-6-Fassung liest.
"""
import os
import sys

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOGO = os.path.join(WURZEL, "eve_trader", "ui", "assets", "logo.png")
# Der dunkle Ton aus dem Inneren des Logos - so geht das runde Logo ohne
# sichtbare Kante in die Flaeche ueber.
GRUND = "#07121f"
GROSS = (328, 628, 288)        # Breite, Hoehe, Logo-Kante
KLEIN = (110, 116, 104)


def bild(breite, hoehe, kante, oben=None):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    logo = QImage(LOGO)
    if logo.isNull():
        raise SystemExit("Logo nicht lesbar: " + LOGO)
    out = QImage(breite, hoehe, QImage.Format_RGB32)
    out.fill(QColor(GRUND))
    klein = logo.scaled(kante, kante, Qt.KeepAspectRatio,
                        Qt.SmoothTransformation)
    p = QPainter(out)
    y = (hoehe - klein.height()) // 2 if oben is None else oben
    p.drawImage((breite - klein.width()) // 2, y, klein)
    p.end()
    return out


def main():
    from PySide6.QtGui import QGuiApplication
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    app = QGuiApplication.instance() or QGuiApplication(sys.argv[:1])
    # Gross: das Logo im oberen Drittel, nicht mittig - dort schaut man hin.
    ziele = (("installer_gross.bmp", bild(*GROSS, oben=110)),
             ("installer_klein.bmp", bild(*KLEIN)))
    for name, img in ziele:
        pfad = os.path.join(WURZEL, name)
        if not img.save(pfad, "BMP"):
            raise SystemExit("Schreiben fehlgeschlagen: " + pfad)
        print(name, img.width(), "x", img.height(),
              os.path.getsize(pfad), "Bytes")
    del app


if __name__ == "__main__":
    main()
