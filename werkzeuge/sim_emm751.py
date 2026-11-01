#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIMULATION: DER HAKEN-LOESER FRISST BESTAETIGTE HAKEN (emm751).

SEIN BEFUND, woertlich (29.10.2026, 16:06, mit Screenshot "Minmatar 1"):
  "mir fällt auf: Probe und Breacher habe ich schon mehrmals angehackt
   und sie lösen sich immer wieder von selbst. ich weiss nicht warum,
   ausserdem hat ESI schon lange gegengechecket und bestätigt dass sie
   da sind und/oder gebaut wurden"

GEMESSEN an seiner settings.json (Plan "Minmatar 1", id 1791918437302)
und dem Diagnose-Export vom 28.10.:
  * Probe (586):    50 Runs geplant, 50 in der ESI-Job-Zuordnung,
                    Haken-Zeitstempel 18.10. 16:44 UND 28.10. 18:37
                    (nach einer Umverteilung neu gehakt).
  * Breacher (598): dasselbe Bild.
  * Im Screenshot von heute (29.10. 16:04): beide Zeilen OHNE Haken,
    beide mit gruenem Punkt (ESI bestaetigt) - Dromi I daneben, gleich
    gebaut, hat seinen Haken noch (sein Zeitstempel ist vom 18.10.,
    einen Tag NACH den Jobs - innerhalb des Fensters).

DIE URSACHE: `haken_ohne_job` (emm350) haelt einen Haken fuer einen
Fehlklick, wenn kein gelieferter Job hoechstens `rueck` (3 Tage) VOR dem
Haken endete. Die Probe-/Breacher-Jobs liefen um den 18.10.; neu gehakt
am 28.10. sind sie 10 Tage alt - aus dem Fenster gefallen, Haken weg.
Beim naechsten Haken dasselbe: "sie lösen sich immer wieder von selbst".
DERSELBE SYSTEMATISCHE FEHLER WIE emm526 (Science), nur bei Bau-Zeilen.

DER FIX: decken die GELIEFERTEN Runs eines Items seine GEPLANTEN Runs
vollstaendig, ist das Item nachweislich fertig gebaut - sein Haken ist
kein Fehlklick und bleibt, egal wie alt die Jobs sind. Das Fenster
selbst bleibt fuer alles andere bestehen (ein Uralt-Job eines FRUEHEREN
Plans darf einen frischen Fehlklick weiterhin nicht decken).

Aufruf: QT_QPA_PLATFORM=offscreen python3 werkzeuge/sim_emm751.py
(Exit 0 = alles gruen). Reine Rechnung, kein Fenster, kein Netz.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = tempfile.mkdtemp(prefix="sim751_")
for _k in ("HOME", "APPDATA", "USERPROFILE"):
    os.environ[_k] = HOME
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.chdir(ROOT)
sys.path.insert(0, ROOT)

OK = True


def pruefe(name, ist, soll):
    global OK
    gut = (ist == soll)
    OK = OK and gut
    print(("  OK   " if gut else "  ROT  ") + name
          + ("" if gut else f"\n           ist={ist!r}\n           soll={soll!r}"))


def ja(name, b):
    pruefe(name, bool(b), True)


from eve_trader.ui.mw_helpers import (haken_ohne_job,        # noqa: E402
                                      HAKEN_FRIST, HAKEN_RUECK)

TAG = 86400.0
PROBE, BREACHER, DROMI1 = 586, 598, 40347
GEBAUT_18_10 = 1_000_000.0                  # die Jobs endeten hier
HAKEN_28_10 = GEBAUT_18_10 + 10 * TAG       # 10 Tage spaeter neu gehakt
ABRUF = HAKEN_28_10 + HAKEN_FRIST + 60      # Job-Abruf nach der Frist

ja("Vorbedingung: 10 Tage liegen weit ausserhalb des Rueckblick-Fensters",
   10 * TAG > HAKEN_RUECK)

JOBS = [{"product_type_id": PROBE, "runs": 50,
         "completed_date": None, "end_date": None, "start_date": None},
        {"product_type_id": BREACHER, "runs": 25,
         "completed_date": None, "end_date": None, "start_date": None},
        {"product_type_id": BREACHER, "runs": 25,
         "completed_date": None, "end_date": None, "start_date": None}]
# Zeiten als Unix-Sekunden direkt ueber _iso_ts nicht moeglich - die
# Funktion liest ISO-Strings. Also echte ISO-Zeiten bauen:
import datetime as _dt                                      # noqa: E402


def _iso(ts):
    return _dt.datetime.fromtimestamp(ts, _dt.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


for _j in JOBS:
    _j["completed_date"] = _iso(GEBAUT_18_10)

HAKEN = {f"component|2115318203|{PROBE}": HAKEN_28_10,
         f"component|2115318203|{BREACHER}": HAKEN_28_10}
PLAN_RUNS = {PROBE: 50, BREACHER: 50, DROMI1: 50}


def loeser(haken=HAKEN, jobs=JOBS, plan_runs=PLAN_RUNS, abruf=ABRUF,
           aktiv=()):
    return haken_ohne_job(haken, aktiv, jobs, abruf, plan_runs=plan_runs)


# =====================================================================
print("TEIL A - sein Fall: fertig gebaut, alt gehakt")

pruefe("A1 Probe und Breacher: beide Haken BLEIBEN (vorher flogen beide)",
       loeser(), [])
pruefe("A2 ... auch ueber mehrere Jobs summiert (Breacher: 25 + 25 = 50)",
       loeser(haken={f"component|x|{BREACHER}": HAKEN_28_10}), [])
# Der alte Weg, zum Vergleich: ohne plan_runs griff nur das Fenster.
pruefe("A3 OHNE die Deckungs-Pruefung flogen genau diese zwei Haken "
       "(der alte Fehler)",
       haken_ohne_job(HAKEN, (), JOBS, ABRUF),
       sorted(HAKEN, key=str))

# =====================================================================
print("")
print("TEIL B - der Fehlklick-Schutz bleibt scharf")

pruefe("B1 nur 30 von 50 Runs geliefert, Jobs alt: der Haken fliegt "
       "weiterhin (Teildeckung ist keine Deckung)",
       loeser(jobs=[{"product_type_id": PROBE, "runs": 30,
                     "completed_date": _iso(GEBAUT_18_10)}],
              haken={f"component|x|{PROBE}": HAKEN_28_10}),
       [f"component|x|{PROBE}"])
pruefe("B2 gar kein Job: der Haken fliegt (emm350, sein eigener Wunsch)",
       loeser(jobs=[], haken={f"component|x|{PROBE}": HAKEN_28_10}),
       [f"component|x|{PROBE}"])
pruefe("B3 Item ohne plan_runs-Eintrag: wie bisher nur das Fenster",
       loeser(haken={f"component|x|{9999}": HAKEN_28_10}),
       [f"component|x|{9999}"])
pruefe("B4 ein LAUFENDER Job schuetzt weiterhin",
       loeser(jobs=[], haken={f"component|x|{PROBE}": HAKEN_28_10},
              aktiv=(PROBE,)), [])
pruefe("B5 ein frischer Job im Fenster schuetzt weiterhin (alter Weg)",
       loeser(jobs=[{"product_type_id": PROBE, "runs": 1,
                     "completed_date": _iso(HAKEN_28_10 - TAG)}],
              haken={f"component|x|{PROBE}": HAKEN_28_10}), [])
pruefe("B6 vor Ablauf der Pruef-Frist wird gar nichts entfernt",
       loeser(jobs=[], abruf=HAKEN_28_10 + 60,
              haken={f"component|x|{PROBE}": HAKEN_28_10}), [])

# =====================================================================
print("")
print("TEIL C - nichts geht an Mist-Eingaben kaputt")

pruefe("C1 plan_runs=None: exakt das alte Verhalten",
       haken_ohne_job(HAKEN, (), JOBS, ABRUF, plan_runs=None),
       sorted(HAKEN, key=str))
for _mist in ({PROBE: "x"}, {"y": 50}, {PROBE: None}):
    loeser(plan_runs=_mist)
ja("C2 unbrauchbare plan_runs werfen nicht", True)
pruefe("C3 Science-Zeilen bleiben ausgenommen (emm526)",
       loeser(haken={"inv|x|586": HAKEN_28_10}, jobs=[]), [])

print("")
print("ALLES GRUEN" if OK else "ES GIBT ROTE PUNKTE")
sys.exit(0 if OK else 1)
