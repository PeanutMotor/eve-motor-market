"""Beide GUI-Suiten (aa+b) PARALLEL statt nacheinander - Nutzer 25.10.2026:
"das hat ewig gedauert wie koennen wir das schneller machen".

GEMESSEN (25.10.2026, dieser Rechner): aa alleine 46 s, b alleine 38 s,
nacheinander also 84 s. Beide Suiten sind voneinander unabhaengig (eigene
Prozesse, eigenes Qt, kein gemeinsamer Zustand) - parallel beansprucht das
nur die Wand-Uhr-Zeit des LANGSAMEREN Laufs (~46 s statt 84 s), nicht die
Rechenzeit insgesamt (die Maschine hat mehrere Kerne, s. de_scan4/5 laufen
nebenbei ohnehin in Sekunden).

Aufruf: python3 werkzeuge/suiten_parallel.py
Exit-Code 0 nur, wenn ALLE vier Teile gruen sind (aa, b, de_scan4, de_scan5).
"""
import os
import subprocess
import sys
import time
from pathlib import Path

os.chdir(Path(__file__).resolve().parent.parent)
_env = dict(os.environ)
_env["QT_QPA_PLATFORM"] = "offscreen"

_laeufe = [
    ("aa (Bestand-Herkunft)", ["python3", "tests/test_bestand_herkunft.py"], _env),
    ("b (Bauplan-Aufbau)", ["python3", "tests/test_bauplan_aufbau.py"], _env),
    ("de_scan4", ["python3", "tests/de_scan4.py"], dict(os.environ)),
    ("de_scan5", ["python3", "tests/de_scan5.py"], dict(os.environ)),
]

_t0 = time.time()
_prozesse = [(name, subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT, text=True))
             for name, cmd, env in _laeufe]

_rot = []
for name, p in _prozesse:
    _out = p.communicate()[0]
    _letzte = [l for l in _out.splitlines() if l.strip()][-6:]
    print(f"--- {name} ---")
    print("\n".join(_letzte))
    if p.returncode != 0:
        _rot.append(name)

print(f"\nGesamtdauer (parallel): {time.time() - _t0:.1f} s")
if _rot:
    print(f"ROT: {_rot}")
else:
    print("ALLE VIER SUITEN GRUEN")
sys.exit(1 if _rot else 0)
