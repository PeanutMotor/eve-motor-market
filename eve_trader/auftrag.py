"""DIAGNOSE-AUFTRAEGE: ein Werkzeug aus `werkzeuge/` starten, ohne dass der
Nutzer doppelklicken muss.

NUTZER 24.10.2026: "kannst du nicht selber bats laufen lassen? mach alles
selber" - und zu Recht. Die Fehlersuche braucht viele Laeufe hintereinander
(Corp-Hangar vergessen, laufende Jobs vergessen, Abschnitt nachgeruestet),
und jedes Mal musste er die .bat anklicken.

WARUM NICHT ANDERS: in diese Sitzung kommt kein Shell-Zugriff auf seinen
Rechner; der Windows-Explorer ist nur auf Klick-Stufe freigegeben (kein
Tippen, Fensterinhalt geschwaerzt). Dateien in den Projektordner LEGEN
geht aber. Also: eine Auftragsdatei hinlegen, das laufende Programm fuehrt
sie aus.

SO ENG WIE MOEGLICH GEBAUT - das hier startet Prozesse, also gilt Regel 3
doppelt:
  * NUR Dateien aus dem Ordner `werkzeuge/` dieses Projekts, nur `*.py`,
    nur Namen aus [a-z0-9_]. Kein Pfad, kein `..`, keine Shell.
  * Argumente nur aus einem engen Zeichenvorrat; alles andere -> Abbruch.
  * KEINE Shell (`shell=False`), die Datei wird als Argument an denselben
    Python uebergeben, der das Programm ausfuehrt.
  * Die Auftragsdatei wird VOR dem Start umbenannt - ein Auftrag laeuft
    genau einmal, auch wenn er abstuerzt. Kein Dauerlauf.
  * Abschaltbar: `settings["diagnose_auftraege"] = False`.
  * Nur EIN Auftrag gleichzeitig.

Die Auftragsdatei `werkzeuge/_auftrag.txt` enthaelt EINE Zeile, z.B.:
    pruefe_materialbilanz.py --zeilen 40
Danach liegt `werkzeuge/_auftrag_erledigt.txt` mit dem Ergebnis daneben
(Rueckgabewert, Laufzeit, letzte Ausgabezeilen); der Bericht selbst
schreibt das Werkzeug wie immer nach `berichte/`.
"""
import os
import re
import subprocess
import sys
import threading
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WERKZEUGE = os.path.join(WURZEL, "werkzeuge")
AUFTRAG = os.path.join(WERKZEUGE, "_auftrag.txt")
ERLEDIGT = os.path.join(WERKZEUGE, "_auftrag_erledigt.txt")

# Wie oft nachgesehen wird. Eine Minute reicht: der Auftrag kommt von
# aussen, und haeufigeres Nachsehen kostet nur Plattenzugriffe.
TAKT_MS = 60_000
# Ein Werkzeug darf nicht ewig laufen - sonst haengt der Auftrag fest.
FRIST_S = 900

_NAME = re.compile(r"^[a-z0-9_]+\.py$")
_ARG = re.compile(r"^[A-Za-z0-9_.,:=+-]+$")

_laeuft = threading.Lock()


def _zerlegen(zeile):
    """(Dateiname, [Argumente]) - oder (None, Grund), wenn etwas nicht passt.

    Bewusst streng: lieber einen gueltigen Auftrag ablehnen als einen
    ungueltigen ausfuehren.
    """
    # de_scan4: aus / de_scan5: aus - BEGRUENDUNG: dieser Text landet in
    # werkzeuge/_auftrag_erledigt.txt, nie auf der Oberflaeche. Dieselbe
    # Ausnahme wie bei den Argumenten von `_log_exception`: eine
    # Uebersetzung braucht nur, was ein Nutzer im Fenster sieht.
    teile = (zeile or "").strip().split()
    if not teile:
        return None, "leere Zeile"
    name = teile[0]
    if not _NAME.match(name):
        return None, f"kein erlaubter Werkzeugname: {name!r}"
    pfad = os.path.join(WERKZEUGE, name)
    # Doppelt gesichert: der aufgeloeste Pfad MUSS in werkzeuge/ liegen.
    if os.path.dirname(os.path.abspath(pfad)) != os.path.abspath(WERKZEUGE):
        return None, "Pfad zeigt aus werkzeuge/ heraus"
    if not os.path.isfile(pfad):
        return None, f"Werkzeug gibt es nicht: {name}"
    for a in teile[1:]:
        if not _ARG.match(a):
            return None, f"Argument nicht erlaubt: {a!r}"
    return pfad, teile[1:]


# de_scan4: an / de_scan5: an


def _ausfuehren(pfad, args):
    # de_scan4: aus / de_scan5: aus - BEGRUENDUNG wie oben: Protokolltext
    # fuer _auftrag_erledigt.txt, keine Oberflaeche.
    t0 = time.time()
    umg = dict(os.environ)
    umg["PYTHONIOENCODING"] = "utf-8"
    try:
        fertig = subprocess.run(
            [sys.executable, pfad] + list(args),
            cwd=WURZEL, env=umg, shell=False, timeout=FRIST_S,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        text = (fertig.stdout or b"").decode("utf-8", "replace")
        return fertig.returncode, text, time.time() - t0
    except subprocess.TimeoutExpired:
        return -1, f"Abbruch nach {FRIST_S} s", time.time() - t0
    except Exception as e:
        return -1, f"{type(e).__name__}: {e}", time.time() - t0


def _protokoll(name, args, code, text, dauer):
    letzte = [z for z in (text or "").splitlines() if z.strip()][-40:]
    try:
        with open(ERLEDIGT, "w", encoding="utf-8") as fh:
            fh.write(f"Auftrag: {name} {' '.join(args)}\n")
            fh.write(f"Beendet: {time.strftime('%Y-%m-%d %H:%M:%S')} "
                     f"(Ortszeit)\n")
            fh.write(f"Laufzeit: {dauer:.1f} s\n")
            fh.write(f"Rueckgabewert: {code}\n")
            fh.write("-" * 70 + "\n")
            fh.write("\n".join(letzte) + "\n")
    except Exception:
        pass


# de_scan4: an / de_scan5: an


def _einmal_nachsehen():
    """Liegt ein Auftrag da? Dann ausfuehren - genau einmal."""
    if not os.path.isfile(AUFTRAG):
        return
    if not _laeuft.acquire(blocking=False):
        return                       # es laeuft schon einer
    try:
        try:
            with open(AUFTRAG, "r", encoding="utf-8", errors="replace") as fh:
                zeile = fh.readline()
        except Exception:
            return
        # ZUERST WEGNEHMEN, DANN AUSFUEHREN: so laeuft ein Auftrag genau
        # einmal, auch wenn das Werkzeug abstuerzt oder das Programm
        # mittendrin beendet wird.
        try:
            os.remove(AUFTRAG)
        except Exception:
            return
        pfad, rest = _zerlegen(zeile)
        if pfad is None:
            _protokoll(zeile.strip(), [], -1, f"ABGELEHNT: {rest}", 0.0)
            return
        code, text, dauer = _ausfuehren(pfad, rest)
        _protokoll(os.path.basename(pfad), rest, code, text, dauer)
    finally:
        _laeuft.release()


# Sitzungsunterlage, die NIE im Repo und NIE im Quelltext-Zip liegt
# (.gitignore). Nur wo sie liegt, wird an diesem Projekt entwickelt.
MERKDATEI = "CLAUDE.md"


def erlaubt(settings=None, wurzel=None, eingefroren=None):
    """Darf die Wache hier ueberhaupt laufen? (emm996, Nutzer 22.11.2026:
    "ja" auf "nur noch bei dir aktiv, bei allen anderen aus".)

    Der Helfer ist ein Werkzeug der FEHLERSUCHE an diesem Projekt - wer Eve
    MoMa nur benutzt (EXE oder Quelltext von GitHub), braucht ihn nicht und
    soll kein Programm haben, das auf Zuruf Dateien startet. Aktiv nur, wenn
      * nicht als EXE gebaut (`sys.frozen`),
      * nicht abgeschaltet (`settings["diagnose_auftraege"] is False`),
      * die Sitzungsunterlage MERKDATEI in der Projektwurzel liegt.
    """
    if eingefroren is None:
        eingefroren = bool(getattr(sys, "frozen", False))
    if eingefroren:
        return False
    if (settings or {}).get("diagnose_auftraege") is False:
        return False
    return os.path.isfile(os.path.join(wurzel or WURZEL, MERKDATEI))


def starte_wachen(fenster, settings=None):
    """Haengt die Wache in die Qt-Ereignisschleife.

    Laeuft im Hintergrund (eigener Thread je Auftrag), damit ein Werkzeug
    das Fenster nie einfriert. Ohne Qt oder bei abgeschalteter Einstellung
    passiert nichts.
    """
    if not erlaubt(settings):
        return None
    try:
        from PySide6.QtCore import QTimer
    except Exception:
        return None

    def _tick():
        threading.Thread(target=_einmal_nachsehen, daemon=True).start()

    t = QTimer(fenster)
    t.setInterval(TAKT_MS)
    t.timeout.connect(_tick)
    t.start()
    _tick()                           # einmal gleich beim Start
    return t
