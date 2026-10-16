"""Windows-Zeilenenden (CRLF) fuer alle .bat-Dateien des Projekts.

WARUM ES DAS GIBT (emm564, Nutzer 16.10.2026: "kannst du da nicht etwas
besseres bauen? ich finde das eh nie" - gemeint war fix_crlf.py, das
ausserhalb des Projektordners lag und nach jeder neuen .bat von Hand
gestartet werden musste). Dateien, die aus der Sitzung auf die Platte
kommen, koennen mit LF statt CRLF ankommen; `cmd` ueberspringt dann nach
`call`/`goto` stumm Zeilen (Befund 18.09.2026), und aa530 wird rot.

Jetzt repariert `pruefe.py` das SELBST, bevor es prueft - als Schritt 0,
mit Namen jeder reparierten Datei im Bericht. Kein eigener Handgriff mehr.

Gefasst wird NUR, was eindeutig ist: eine Datei, die LF ohne CR enthaelt,
wird auf CRLF gebracht; schon vorhandene CRLF bleiben, wie sie sind (kein
CRCRLF). Inhalt und Kodierung bleiben unangetastet - es werden nur Bytes
der Zeilenenden ersetzt.
"""
import os

# DIESELBEN DREI ORDNER WIE aa530. NICHT: .venv (fremde Dateien), _archiv
# (Geschichte, wird nie gestartet), build/dist (erzeugt) - und NICHT die
# Wurzel: build.bat/run.bat liegen dort seit jeher mit LF, gehoeren zum
# Repo und zum Quelltext-Zip und laufen beim Nutzer so (gemessen
# 16.10.2026, erster Probelauf haette beide still umgeschrieben).
ORDNER = ("werkzeuge", "release", "tests")


def crlf(daten: bytes) -> bytes:
    """LF -> CRLF, ohne vorhandene CRLF zu verdoppeln."""
    return daten.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")


def reparieren(wurzel="."):
    """Alle .bat in ORDNER pruefen; reparierte Dateien als Liste
    relativer Pfade zurueckgeben (leer = alles war schon richtig)."""
    repariert = []
    for ordner in ORDNER:
        pfad = os.path.join(wurzel, ordner) if ordner else wurzel
        if not os.path.isdir(pfad):
            continue
        for name in sorted(os.listdir(pfad)):
            if not name.lower().endswith(".bat"):
                continue
            datei = os.path.join(pfad, name)
            if not os.path.isfile(datei):
                continue
            with open(datei, "rb") as f:
                alt = f.read()
            neu = crlf(alt)
            if neu != alt:
                with open(datei, "wb") as f:
                    f.write(neu)
                repariert.append(os.path.join(ordner, name) if ordner else name)
    return repariert


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    _r = reparieren(".")
    print("\n".join(_r) if _r else "alle .bat haben schon CRLF")
