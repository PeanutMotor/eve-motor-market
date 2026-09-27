"""Ladezeit-Messung (Nutzer 27.09.2026: "das Oeffnen eines Bauplans dauert
sehr lange, Multi-Bauplaene mehrere Minuten - da muessten wir mal messen,
was so viel Zeit kostet").

NUR AUF WUNSCH: aktiv ausschliesslich mit der Umgebungsvariable
EMM_LADEZEIT=1 (gesetzt von `werkzeuge\\messe_ladezeit.bat`). Ohne sie tut
dieses Modul NICHTS - kein Profiler, keine Datei, kein Overhead im Alltag.

Was gemessen wird:
* jeder Hintergrund-Job (`workers.Worker.run`) - Wandzeit + die teuersten
  Funktionen (cProfile, je Thread);
* das Oeffnen eines Bauplans im OBERFLAECHEN-Thread vom Klick bis alles
  ruhig ist (`ui_start` ... `ui_stop`), inklusive aller Rueckrufe dazwischen.

Ergebnis: `berichte/ladezeiten.txt` im Projektordner (wird angehaengt).
"""
import cProfile
import io
import os
import pstats
import threading
import time
from contextlib import contextmanager

AN = os.environ.get("EMM_LADEZEIT") == "1"

_ORDNER = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "berichte")
DATEI = os.path.join(_ORDNER, "ladezeiten.txt")

_lock = threading.Lock()
# EIN PROFILER FUER DEN GANZEN PROZESS (gemessen in der Rotprobe
# 27.09.2026): ab Python 3.12 haengt cProfile an sys.monitoring, und das
# gibt es nur EINMAL je Interpreter - ein zweites enable(), auch aus einem
# anderen Thread, wirft "Another profiling tool is already active". Das
# haette waehrend einer Messung jeden Hintergrund-Job abstuerzen lassen.
# Deshalb: laeuft schon einer, misst der naechste Block nur die Zeit. Der
# laufende Profiler sieht unter 3.12 ohnehin alle Threads.
_aktiv = [False]
_ui = {}                         # die laufende Oberflaechen-Messung
# DIE OBERFLAECHE HAT VORRANG (zweiter Nutzer-Bericht 27.09.2026: "open
# build plan 12.49 s (time only - another profile was running)" - genau die
# wichtigste Messung kam ohne Profil, weil gerade die Plan-Karten rechneten).
# Beginnt eine Oberflaechen-Messung, uebernimmt sie den laufenden Profiler
# eines Hintergrund-Jobs; der Job-Bericht zeigt dann nur den Teil davor.
_laufend = {"prof": None}
_uebergeben = set()              # id() der Job-Profile, die abgeben mussten


def _profil_starten(vorrang=False):
    """Profiler starten, wenn noch keiner laeuft - sonst None. Wirft nie.
    vorrang=True (Oberflaeche): ein laufendes Job-Profil wird beendet und
    der Profiler uebernommen."""
    with _lock:
        if _aktiv[0]:
            alt = _laufend["prof"]
            if not vorrang or alt is None:
                return None
            try:
                alt.disable()
            except Exception:
                pass
            _uebergeben.add(id(alt))
            _aktiv[0] = False
            _laufend["prof"] = None
        prof = cProfile.Profile()
        try:
            prof.enable()
        except (ValueError, RuntimeError):
            return None
        _aktiv[0] = True
        _laufend["prof"] = prof
        return prof


def _profil_stoppen(prof):
    if prof is None:
        return
    try:
        prof.disable()
    except Exception:
        pass
    with _lock:
        # Nur freigeben, wenn DIESES Profil noch der laufende ist - hat die
        # Oberflaeche es uebernommen, gehoert der Profiler jetzt ihr.
        if _laufend["prof"] is prof:
            _aktiv[0] = False
            _laufend["prof"] = None


def _schreiben(text):
    try:
        os.makedirs(_ORDNER, exist_ok=True)
        with _lock, open(DATEI, "a", encoding="utf-8") as f:
            f.write(text)
    except OSError:
        pass                     # Messung darf das Programm nie stoeren


def _bericht(name, sekunden, prof, top=30, ui=False, marken=None):
    kopf = (f"\n== {time.strftime('%Y-%m-%d %H:%M:%S')}  {name}  "
            f"{sekunden:.2f} s  (Thread {threading.current_thread().name})\n")
    for _m in (marken or []):
        _text, _sek = _m[0], _m[1]
        _zeile = f"   {_sek:7.2f} s  {_text}"
        if len(_m) > 2:
            _zeile += f"  (UI thread busy {_m[2]:.2f} s)"
        kopf += _zeile + "\n"
    if marken and any(len(_m) > 2 for _m in marken):
        kopf += ("   (\"busy\" = computing time of the UI thread itself; the rest "
                 "of the wall time it waited, e.g. for background jobs)\n")
    if prof is None:
        return kopf + "   (time only - another profile was running)\n"
    if id(prof) in _uebergeben:
        _uebergeben.discard(id(prof))
        kopf += ("   (profile only until a build plan was opened - "
                 "the build plan measurement took it over)\n")
    elif ui:
        kopf += ("   (includes background jobs running at the same time)\n")
    puffer = io.StringIO()
    st = pstats.Stats(prof, stream=puffer)
    st.strip_dirs().sort_stats("cumulative").print_stats(top)
    puffer.write("\n-- by own time (tottime):\n")
    st.sort_stats("tottime").print_stats(15)
    return kopf + puffer.getvalue()


@contextmanager
def messen(name):
    """Block messen (Wandzeit + cProfile). Ohne EMM_LADEZEIT: nichts.
    Laeuft schon ein Profiler (irgendwo im Prozess), nur die Zeit."""
    if not AN:
        yield
        return
    t0 = time.perf_counter()
    prof = _profil_starten()
    try:
        yield
    finally:
        _profil_stoppen(prof)
        _schreiben(_bericht(name, time.perf_counter() - t0, prof))


def ui_start(name):
    """Messung im Oberflaechen-Thread beginnen (z. B. Klick auf einen
    Bauplan). Eine schon laufende wird zuerst abgeschlossen."""
    if not AN:
        return
    if _ui:
        ui_stop()
    # Laeuft gerade ein Job-Profil, uebernimmt die Oberflaeche den Profiler.
    _ui.update({"name": name, "t0": time.perf_counter(),
                "cpu0": (time.thread_time() if threading.current_thread()
                         is threading.main_thread() else None),
                "prof": _profil_starten(vorrang=True)})


def ui_zwischenzeit(text):
    """Zwischenzeit in der laufenden Oberflaechen-Messung festhalten (z. B.
    "main window built") - steht spaeter im Kopf des Berichts."""
    if not AN or not _ui:
        return
    _eintrag = (text, time.perf_counter() - _ui["t0"])
    if _ui.get("cpu0") is not None and threading.current_thread() is threading.main_thread():
        _eintrag += (time.thread_time() - _ui["cpu0"],)
    _ui.setdefault("marken", []).append(_eintrag)


def _beim_beenden():
    """Wird Eve MoMa geschlossen, bevor die Oberflaeche ruhig war, steht die
    angefangene Messung trotzdem im Bericht (erster Nutzer-Lauf 27.09.2026:
    der Bauplan-Teil fehlte ganz)."""
    if _ui:
        _ui["name"] = str(_ui.get("name")) + " (closed before idle)"
        ui_stop()


if AN:
    import atexit
    atexit.register(_beim_beenden)


def ui_laeuft():
    return bool(_ui)


def ui_stop():
    """Oberflaechen-Messung beenden und schreiben."""
    if not AN or not _ui:
        return
    prof = _ui.get("prof")
    _profil_stoppen(prof)
    name, t0, marken = _ui.get("name"), _ui.get("t0"), _ui.get("marken")
    _ui.clear()
    _schreiben(_bericht("UI thread: " + str(name), time.perf_counter() - t0, prof,
                        ui=True, marken=marken))
