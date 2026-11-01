#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIMULATION: STOCK LOCATIONS GLAUBT EINEM ACHT TAGE ALTEN HAKEN (emm749).

SEIN BEFUND, woertlich (28.10.2026):
  "nur dafür habe ich tatsächlich zu wenig Material um es nachzubauen,
   aber Stock Location sieht es nicht und der Bauplan auch nicht"
und einen Tag vorher, zum selben Mechanismus:
  "warum hat mir stok locations gestern zu wenig material zu kaufen
   angegeben?"

DAS DRITTE VORKOMMEN DERSELBEN URSACHE. emm747 hat die Regel "der Haken
gilt nur, bis ESI widerspricht" fuer `_rest_geliefert_jetzt` gebaut,
emm748 fuer den Nachlauf-Ofen - und `lagerorte.gebaute_runs`, die
Stock Locations speist, blieb liegen. Sie stand sogar woertlich in der
emm747-Doku ("`gebaute_runs` zaehlt einen Haken als GEBAUT
(`max(aus_jobs, aus_haken)`)") und wurde trotzdem nicht angefasst.

GEMESSEN an seiner settings.json (gelesen 28.10.2026 19:00), Plan
"Minmatar 1" (id 1791918437302):
  checked_runplan_runs["reaction_2|16673"] = 319 Runs Fernite Carbide
  juengster Zeitstempel dazu: 192,2 STUNDEN alt - acht Tage.
  checked_runplan_runs["reaction_2|17317"] = Fermionic Condensates,
  Zeitstempel 192,1 Stunden alt.
Die Haken-Frist (`HAKEN_FRIST_S`) betraegt 65 Minuten.

Aufruf: QT_QPA_PLATFORM=offscreen python3 werkzeuge/sim_emm749.py
(Exit 0 = alles gruen). Reine Rechnung, kein Fenster, kein Netz.
"""
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = tempfile.mkdtemp(prefix="sim749_")
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


from eve_trader.lagerorte import gebaute_runs                # noqa: E402
from eve_trader.ui.mw_helpers import (HAKEN_FRIST_S,         # noqa: E402
                                      restbedarf_map)

FC, ECU, ROH = 16673, 11557, 16656
PID = 1791918437302
JETZT = time.time()
ACHT_TAGE = JETZT - 192.2 * 3600          # sein gemessenes Haken-Alter
FRISCH = JETZT - 60

ja("Vorbedingung: die Frist ist viel kuerzer als sein Haken-Alter",
   HAKEN_FRIST_S < 192.2 * 3600)


def plan(ts, haken=319):
    return {"id": PID,
            "checked_runplan_runs": {f"reaction_2|{FC}": haken},
            "checked_runplan_ts": {f"reaction_2|2113366524|{FC}": ts,
                                   # Diese Bauart gibt es auch - hinten
                                   # steht eine Charakter-Id, keine
                                   # type_id. Sie darf nichts kaputt
                                   # machen.
                                   "char|reaction_2|2113366524": ts}}


def jobs(runs):
    """`job_zuordnung_details`-Karte: {job_id: {plan_id, type_id, runs}}."""
    if not runs:
        return {}
    return {"777": {"plan_id": PID, "type_id": FC, "runs": runs}}


# =====================================================================
print("TEIL A - sein Fall: 319 Runs abgehakt vor acht Tagen, ESI sieht nichts")

_alt = gebaute_runs(plan(ACHT_TAGE), jobs(0))
pruefe("A1 der alte Haken zaehlt NICHT mehr als gebaut", _alt.get(FC, 0), 0)
_neu = gebaute_runs(plan(FRISCH), jobs(0))
pruefe("A2 derselbe Haken, eben gesetzt: zaehlt voll (sein Ablauf bleibt)",
       _neu.get(FC, 0), 319)

# =====================================================================
print("")
print("TEIL B - was das fuer die Einkaufsliste heisst")

# Fernite Carbide: 319 Runs zu 10'000 Stueck; eine Zutat (Fernite Alloy)
# zu 31'262 Stueck fuer alle 319 Runs.
BR = {FC: 319}
BM = {FC: [(ROH, 31262)]}
_, _brauch_alt = restbedarf_map(BR, BM, gebaute_runs(plan(ACHT_TAGE),
                                                     jobs(0)))
_, _brauch_neu = restbedarf_map(BR, BM, gebaute_runs(plan(FRISCH),
                                                     jobs(0)))
pruefe("B1 mit dem alten Haken stand die Zutat auf 0 - das Material "
       "fiel aus der Liste", _brauch_neu.get(ROH, 0), 0)
pruefe("B2 jetzt steht sie wieder drin, in voller Hoehe",
       _brauch_alt.get(ROH, 0), 31262)

# =====================================================================
print("")
print("TEIL C - ESI behaelt immer das letzte Wort")

_belegt = gebaute_runs(plan(ACHT_TAGE), jobs(319))
pruefe("C1 ESI belegt alle 319 Runs: sie zaehlen als gebaut",
       _belegt.get(FC, 0), 319)
_teil = gebaute_runs(plan(ACHT_TAGE), jobs(200))
pruefe("C2 ESI belegt nur 200: genau 200 zaehlen, nicht 319",
       _teil.get(FC, 0), 200)
# Die Rueckrichtung: hier wird NICHTS gespeichert, der Stand entsteht
# bei jedem Aufruf neu. Kommt der Beleg spaeter, zaehlt der Haken wieder.
pruefe("C3 Rueckrichtung: spaeter Beleg stellt den Haken von selbst "
       "wieder her", gebaute_runs(plan(ACHT_TAGE), jobs(319)).get(FC, 0),
       319)
# Mehr abgehakt als geplant bleibt gedeckelt (emm670).
_deckel = gebaute_runs(plan(ACHT_TAGE, haken=500), jobs(319),
                       plan_runs={FC: 319})
pruefe("C4 500 abgehakt, 319 geplant, 319 belegt: Deckel haelt",
       _deckel.get(FC, 0), 319)

# =====================================================================
print("")
print("TEIL D - nichts geht kaputt, wo es keine Zeitstempel gibt")

_ohne_ts = gebaute_runs({"id": PID,
                         "checked_runplan_runs": {f"reaction_2|{FC}": 319}},
                        jobs(0))
pruefe("D1 alter Plan ohne `checked_runplan_ts`: Verhalten wie vor "
       "emm749", _ohne_ts.get(FC, 0), 319)
pruefe("D2 gar keine Haken: unveraendert",
       gebaute_runs({"id": PID}, jobs(50)).get(FC, 0), 50)
pruefe("D3 leerer Plan wirft nicht", gebaute_runs({}, {}), {})
for _mist in (None, {"id": PID, "checked_runplan_runs": {"x": "y"},
                     "checked_runplan_ts": {"x": "y"}},
              {"id": PID, "checked_runplan_runs": {f"a|{FC}": 5},
               "checked_runplan_ts": None}):
    gebaute_runs(_mist, None)
ja("D4 unbrauchbare Eingaben werfen nicht", True)

# `extra` (emm475) wird weiterhin ADDIERT, nicht gekappt - das sind
# andere, eindeutig zuteilbare Jobs, nicht dieselben Runs.
_extra = gebaute_runs(plan(ACHT_TAGE), jobs(0), {FC: 40})
pruefe("D5 eindeutige, noch nicht zugeordnete Jobs zaehlen weiter "
       "(emm475)", _extra.get(FC, 0), 40)

print("")
print("ALLES GRUEN" if OK else "ES GIBT ROTE PUNKTE")
sys.exit(0 if OK else 1)
