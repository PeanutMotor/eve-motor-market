"""EIN Befehl vor jeder Veroeffentlichung:  python pruefe.py

Laeuft die vier Pruefungen, die zusammen den Stand absichern, und sagt am
Ende in einer Zeile, ob veroeffentlicht werden darf.

WARUM ZUSAMMEN: jede findet etwas, das die anderen NICHT finden.
  * aa/b-Suiten  - die Zusagen des Werkzeugs (rechnet es richtig?)
  * lint_order   - Reihenfolge/Struktur im Quelltext
  * pyflakes     - undefinierte Namen. Sitzung 16: 38 Stueck, alle erst
                   beim AUSFUEHREN sichtbar. Kompilieren zeigt sie nicht,
                   und beide Suiten waren dabei gruen.

Die Rotprobe laeuft hier NICHT mit (--check dauert 2 Min, der volle Lauf
Stunden). Sie ist eine eigene Runde: `python tests\\rotprobe.py --check`.
"""
import os
import subprocess
import sys

os.chdir(os.path.dirname(os.path.abspath(__file__)) or ".")
PY = sys.executable


class _Doppelt:
    """Alles, was auf dem Bildschirm steht, auch in berichte\\pruefe_bericht.txt.

    18.09.2026: das Fenster schloss sich beim Nutzer sofort nach dem
    Lauf, er konnte NICHTS lesen. Der Nutzer hat keine Shell - eine
    Textdatei neben dem Skript ist der einzige Weg, der immer geht.
    Faellt das Skript selbst mit einer Ausnahme, steht auch die drin
    (siehe sys.excepthook unten)."""

    def __init__(self, konsole, datei):
        self._k = konsole
        self._f = datei

    def write(self, s):
        try:
            self._k.write(s)
        except Exception:
            pass
        try:
            self._f.write(s)
            self._f.flush()
        except Exception:
            pass

    def flush(self):
        for o in (self._k, self._f):
            try:
                o.flush()
            except Exception:
                pass


os.makedirs("berichte", exist_ok=True)
_BERICHT = open(os.path.join("berichte", "pruefe_bericht.txt"), "w",
                encoding="utf-8", errors="replace")
sys.stdout = _Doppelt(sys.stdout, _BERICHT)
sys.stderr = _Doppelt(sys.stderr, _BERICHT)
import datetime as _dt
print(f"pruefe.py Fassung 7 - {_dt.datetime.now():%Y-%m-%d %H:%M:%S} - "
      f"Python {sys.version.split()[0]}")


def _haken(typ, wert, tb):
    import traceback
    print("\nABBRUCH von pruefe.py selbst:")
    print("".join(traceback.format_exception(typ, wert, tb)))
    _w = globals().get("_warte")
    if _w is not None:
        _w()


sys.excepthook = _haken


def lauf(titel, befehl, umgebung=None, muster_ok=None):
    u = dict(os.environ)
    u.update(umgebung or {})
    # FASSUNG 5 (01.10.2026): stuerzt Python selbst ab, schreibt der
    # faulthandler wenigstens noch, WO (Zugriffsverletzung u. a.).
    u.setdefault("PYTHONFAULTHANDLER", "1")
    # FASSUNG 7 (02.10.2026): das Kind schreibt UTF-8 - gelesen wird ohnehin
    # UTF-8 (unten). Vorher schrieb es auf Windows cp1252 und starb an "\u25b8".
    u["PYTHONIOENCODING"] = "utf-8"
    print(f"\n=== {titel} " + "=" * max(0, 56 - len(titel)))
    # ZEICHENTABELLE FESTNAGELN: Windows liest sonst mit cp1252, und ein
    # Umlaut in der Ausgabe kann den ganzen Text verschlucken (Sitzung 16:
    # beim Nutzer stand unter zwei Ueberschriften GAR NICHTS, bei mir die
    # Gruen-Zeile). `errors="replace"` heisst: lieber ein Fragezeichen im
    # Text als eine leere Ausgabe.
    p = subprocess.run(befehl, capture_output=True, text=True, env=u,
                       encoding="utf-8", errors="replace")
    aus = (p.stdout or "") + (p.stderr or "")
    _zeilen = [z for z in aus.splitlines() if z.strip()]
    for z in _zeilen:
        if "FEHLER" in z or "Befund" in z or "gruen" in z or "undefined" in z:
            # FASSUNG 4 (23.09.2026): FEHLER-Zeilen nicht mehr bei 110
            # Zeichen abschneiden. Eine Pruefung, die ihre Messwerte ins
            # Label schreibt (b85: die Spaltenbreiten), war damit aus der
            # Ferne wertlos - genau dann, wenn man sie braucht.
            print("  " + (z.strip() if "FEHLER" in z else z.strip()[:110]))
    if not _zeilen:
        print("  (keine Ausgabe - lief die Pruefung ueberhaupt?)")
    # RUECKGABEWERT AUCH BEI GRUEN ZEIGEN (Fassung 5, 01.10.2026). Beim
    # Nutzer endete die b-Suite einmal mit 3221226505 (0xC0000409) NACH der
    # Ergebniszeile - gesehen nur, weil sie rot war. Ob das auch bei gruenem
    # Lauf passiert und was Qt/Python davor auf stderr schreibt, war nicht
    # zu erkennen. Am Urteil aendert das nichts (es zaehlt die Ergebniszeile).
    if p.returncode != 0:
        print(f"  WARNUNG Rueckgabewert {p.returncode} "
              f"(0x{p.returncode & 0xFFFFFFFF:08X})")
        _err = [z for z in (p.stderr or "").splitlines() if z.strip()
                and "DeprecationWarning" not in z
                and "does not support raise" not in z]
        for z in _err[-10:]:
            print("  ! " + z.rstrip()[:160])
    _ok = muster_ok(aus) if muster_ok is not None else (p.returncode == 0)
    if not _ok:
        # BEI ROT DEN ECHTEN TEXT ZEIGEN (Sitzung 16): sonst steht da nur
        # "ROT" und niemand weiss, woran es liegt. Der Nutzer sah genau
        # das - zwei rote Zeilen ohne einen einzigen Hinweis darauf, was
        # schiefging.
        print(f"  -- Rueckgabewert {p.returncode}, letzte Zeilen: --")
        for z in (_zeilen[-12:] or ["(gar nichts)"]):
            print("  | " + z.rstrip()[:110])
    return _ok


def _warte():
    """Beim DOPPELKLICK offen bleiben.

    Windows schliesst das Fenster sonst sofort, und der Nutzer sieht nichts
    (Sitzung 16: "dann geht das cmd fuer 1 Sekunde auf und schliesst sich
    direkt"). Laeuft es aus einer schon offenen Kommandozeile, ist die
    Pause ueberfluessig - dann steht der Text ohnehin da; wer Enter
    drueckt, verliert nichts.
    """
    try:
        input("\nEnter zum Schliessen ...")
    except (EOFError, KeyboardInterrupt):
        pass


ergebnis = {}
def _suite_ok(aus):
    """Gruen ist NUR, was auch wirklich gelaufen ist.

    Erste Fassung fragte bloss "steht FEHLER drin?" - bei LEERER Ausgabe
    war das falsch und meldete OK, obwohl gar nichts lief. Der Nutzer sah
    genau das (Sitzung 16): vier Haken, aber unter zwei Ueberschriften
    stand nichts. Jetzt muss die Abschlusszeile "N/N gruen" da sein.
    """
    import re
    m = re.search(r"(\d+)/(\d+) gruen", aus)
    return bool(m) and m.group(1) == m.group(2) and "FEHLER" not in aus


ergebnis["Bestand-Herkunft (aa)"] = lauf(
    "Bestand-Herkunft", [PY, os.path.join("tests", "test_bestand_herkunft.py")],
    muster_ok=_suite_ok)
ergebnis["Bauplan-Aufbau (b)"] = lauf(
    "Bauplan-Aufbau", [PY, os.path.join("tests", "test_bauplan_aufbau.py")],
    umgebung={"QT_QPA_PLATFORM": "offscreen", "PYTHONPATH": os.getcwd()},
    muster_ok=_suite_ok)

_dateien = []
for wurzel, _d, _f in os.walk("eve_trader"):
    _dateien += [os.path.join(wurzel, n) for n in _f if n.endswith(".py")]
ergebnis["Lint (Reihenfolge)"] = lauf(
    "Lint", [PY, os.path.join("tests", "lint_order.py")] + _dateien + ["main.py"],
    muster_ok=lambda a: "0 Befund" in a)

# PYFLAKES MUSS WIRKLICH LAUFEN (Fassung 6, 01.10.2026): in der .venv des
# Nutzers fehlte es - "No module named pyflakes" enthaelt kein "undefined
# name", und die Zeile stand auf OK, obwohl gar nichts geprueft wurde.
_pf_da = subprocess.run([PY, "-c", "import pyflakes"],
                        capture_output=True).returncode == 0
if _pf_da:
    ergebnis["pyflakes (undefinierte Namen)"] = lauf(
        "pyflakes", [PY, "-m", "pyflakes", "eve_trader/"],
        muster_ok=lambda a: "undefined name" not in a
        and "No module named" not in a)
else:
    print("\n=== pyflakes " + "=" * 48)
    print("  pyflakes fehlt - einmal nachruesten:  "
          ".venv\\Scripts\\python -m pip install pyflakes")
    ergebnis["pyflakes (undefinierte Namen)"] = None

print("\n" + "=" * 62)
# Eine Pruefung, die NICHT lief (None), sagt nichts - sie darf die
# Freigabe nicht durchwinken (Fassung 6).
schlecht = [k for k, v in ergebnis.items() if v is not True]
for k, v in ergebnis.items():
    print(f"  {'OK  ' if v else 'FEHLT' if v is None else 'ROT '}  {k}")
if schlecht:
    print("\nNICHT VEROEFFENTLICHEN - erst reparieren: " + ", ".join(schlecht))
    _warte()
    sys.exit(1)
print("\nAlles gruen. Veroeffentlichen ist in Ordnung.")
# DIE VERSIONSNUMMER ZEIGEN (Sitzung 17). Das Programm meldete sich als
# 0.1.0, waehrend auf Github 0.1.2 stand - die Update-Pruefung meldete
# damit jedem die eigene Fassung als "neu". Keine Pruefung kann die
# Github-Marke kennen; also steht die Zahl hier, wo vor dem Hochladen
# ohnehin jemand hinsieht. Gelesen wie in build.bat - dieselbe Quelle.
_ver = subprocess.run([PY, "-c", "import eve_trader;print(eve_trader.__version__)"],
                      capture_output=True, text=True, encoding="utf-8",
                      errors="replace").stdout.strip() or "?"
print(f"Programmversion: {_ver}  -  die Release-Marke auf Github muss "
      f"genau so heissen (neue Fassung = hoehere Zahl).")
_warte()
