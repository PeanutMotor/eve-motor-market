#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MESSUNG emm721 (Pruefpunkt aus OFFENE_PUNKTE.md, 25.10.2026): zaehlt die
Fehlbedarfs-Pruefung (`_fehlbedarf_jetzt`) fremde laufende Jobs als Deckung?

Die Stelle (main_window, `_im_bestand`-Schleife) liest `_bd_active_jobs_map`
OHNE Bedingung - und beim frischen/gespeichert-ungefrorenen Plan traegt die
Karte ALLE Jobs ALLER Plaene (die Plan-Filterung laeuft nur im
Einfrier-Zweig, s. emm717). Dazu steckt die PIPELINE aller Jobs (auch
fremder) im Live-Bestand (`_virtual_stock` zaehlt jobs_by_char ungefiltert).

GERECHNET WIRD MIT DEN ECHTEN FUNKTIONEN (MW._fehlbedarf_jetzt,
MW._rest_geliefert_jetzt, fehlbedarf_vorschau, _umstrittene_items) auf einem
nackten Objekt - keine Nachbildung (Regel 9/5).

SZENARIO A - das Loch: frischer Plan baut E (1 Run, braucht 10 X), X wird
GEKAUFT (steht nicht in build_runs). Ein ANDERER gespeicherter Plan baut X
(Schnappschuss build_runs {X: 25}) und hat einen LAUFENDEN Job X mit 25
Runs. Der Live-Bestand traegt deshalb X: 25 - das ist NUR die Pipeline des
fremden Jobs, im Hangar liegt nichts.
  WAHRHEIT: die 25 X gehoeren dem anderen Plan. DIESER Plan muss 10 X
  kaufen. Meldet die Pruefung "nichts fehlt", kauft der Nutzer zu wenig
  (Regel 3, gefaehrliche Richtung).

SZENARIO B - Gegenprobe (muss unveraendert bleiben): dasselbe, aber KEIN
anderer Plan baut X (Item unumstritten; der Job ist z.B. ein Handbau).
Dann zaehlt die Pipeline wie bisher als kommender Bestand - gewollt.

SZENARIO C - Gegenprobe eigener Plan: gespeichert+gefroren, die Karte ist
plan-gefiltert und traegt NUR den eigenen X-Job - der zaehlt natuerlich.

Aufruf: python3 werkzeuge/sim_emm721.py   (Exit 0 = alle Erwartungen gruen)
"""
import os
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from eve_trader.ui.main_window import MainWindow as MW  # noqa: E402

E, X, M = 100, 200, 300


class _Dummy:
    """Nacktes Objekt mit den ECHTEN Methoden - nur Zustand wird gestellt."""
    _fehlbedarf_jetzt = MW._fehlbedarf_jetzt
    _rest_geliefert_jetzt = MW._rest_geliefert_jetzt
    _bd_echter_bestand = MW._bd_echter_bestand
    _jobs_karte_plan_gefiltert = MW._jobs_karte_plan_gefiltert
    _umstrittene_items = staticmethod(MW._umstrittene_items)
    # emm799: _fehlbedarf_jetzt liest die EINE Stelle fuer die fremde
    # Pipeline - die ECHTE Methode, keine Nachbildung (Regel 9). Ihre
    # Zutaten (settings, _bd_open_plan_id, Jobs-Karten, _bd_recipes)
    # stellt __init__ ohnehin.
    _fremde_pipeline_umstritten = MW._fremde_pipeline_umstritten
    _erz_durch_bestand = MW._erz_durch_bestand
    # emm738+: _erz_durch_bestand liest _erz_bestand_lage - auch hier die
    # ECHTE Methode; ohne reprocess-Schritte im Plan liefert sie {}.
    _erz_bestand_lage = MW._erz_bestand_lage
    # fuer den Einfrier-Zweig von _bd_echter_bestand (Szenario C):
    _resolve_stock_sources = MW._resolve_stock_sources     # classmethod
    _reservierungen_anwenden = MW._reservierungen_anwenden
    _reserved_by_other_plans = staticmethod(MW._reserved_by_other_plans)
    _reserved_by_this_plan = staticmethod(MW._reserved_by_this_plan)
    plan_rang = staticmethod(MW.plan_rang)
    bestand_nach_reservierungen = staticmethod(MW.bestand_nach_reservierungen)
    _bestand_fuer_deckung = MW._bestand_fuer_deckung

    def __init__(self, build_runs, build_mats, live, jobs_map,
                 saved_plans=(), open_plan_id=None, frozen=None,
                 jobs_alle=None, pipeline=None):
        self.settings = {"bau_saved_plans": list(saved_plans)}
        self._bd_plan_ref = {"plan": {"build_runs": dict(build_runs),
                                      "build_mats": dict(build_mats),
                                      "build_made": {}}}
        self._bd_recipes = types.SimpleNamespace(
            product_to_bp={E: (900, 1, 1), X: (901, 1, 1)},
            bp_materials={(900, 1): list(build_mats.get(E) or []),
                          (901, 1): list(build_mats.get(X) or [])})
        self._bd_opts = {"stock": dict(live)}
        self._bd_live_stock = dict(live)
        self._bd_frozen = frozen
        self._bd_open_plan_id = open_plan_id
        self._bd_active_jobs_map = {k: list(v) for k, v in jobs_map.items()}
        self._bd_active_jobs_alle = ({k: list(v) for k, v in jobs_alle.items()}
                                     if jobs_alle is not None
                                     else {k: list(v)
                                           for k, v in jobs_map.items()})
        self._bd_runplan_delivered_sicher = {}
        self._bd_runplan_checked = set()
        self._bd_runplan_runs_by_key = {}
        self._bd_manual_stock = {}
        self._bd_manual_ts = None
        self._bd_esi_stock_ts = None
        self._bd_manual_perm = False
        self._bd_manual_only = False
        self._bd_pipeline_live = dict(pipeline or {})
        self._bd_buendel_enden = None

    def _log_exception(self, *a):
        raise AssertionError(f"_log_exception gerufen: {a}")


FREMD_PLAN = {"id": 777, "label": "Fremdplan", "frozen": {
    "plan_snapshot": {"build_runs": {X: 25}}, "ts": 1.0}}
JOB_X_25 = {X: [{"runs": 25, "job_id": 42, "start_date": None}]}


def fehlt_map(d):
    return {t: f for t, f, _b, _da, _p in d._fehlbedarf_jetzt()}


def main():
    ok = True

    def pruefe(name, ist, soll):
        nonlocal ok
        gut = (ist == soll)
        ok = ok and gut
        print(("  OK   " if gut else "  LOCH ") + name
              + f"  ist={ist} soll={soll}")

    print("SZENARIO A: fremder Plan baut X, sein Job (25 Runs) steht als"
          " Pipeline im Bestand; DIESER Plan kauft X (braucht 10).")
    a = _Dummy(build_runs={E: 1}, build_mats={E: [(X, 10)]},
               live={X: 25}, jobs_map=JOB_X_25, saved_plans=[FREMD_PLAN])
    pruefe("A: X fehlt 10 (fremde Pipeline zaehlt NICHT)",
           fehlt_map(a), {X: 10})

    print("SZENARIO B: niemand sonst baut X (unumstritten) - die Pipeline"
          " zaehlt wie bisher als kommender Bestand.")
    b = _Dummy(build_runs={E: 1}, build_mats={E: [(X, 10)]},
               live={X: 25}, jobs_map=JOB_X_25, saved_plans=[])
    pruefe("B: nichts fehlt (unveraendertes Verhalten)", fehlt_map(b), {})

    print("SZENARIO C: eigener Plan, gefroren, Karte plan-gefiltert -"
          " der EIGENE Job zaehlt.")
    c = _Dummy(build_runs={E: 1, X: 10}, build_mats={E: [(X, 10)],
                                                     X: [(M, 10)]},
               live={X: 10, M: 0}, jobs_map={X: [{"runs": 10, "job_id": 7,
                                                  "start_date": None}]},
               saved_plans=[FREMD_PLAN], open_plan_id=555,
               frozen={"plan_snapshot": {"build_runs": {E: 1, X: 10}},
                       "ts": 2.0},
               pipeline={X: 10})
    # Eigener X-Job laeuft (10 Runs): sein Output steckt in live (X: 10),
    # seine Zutaten sind verbraucht -> weder X noch M duerfen fehlen.
    pruefe("C: nichts fehlt (eigener Job deckt, wie bisher)",
           fehlt_map(c), {})

    print("SZENARIO D: eigener Plan GEFROREN (Karte gefiltert, leer), der"
          " fremde X-Job steht nur in der Rohliste + Pipeline.")
    d = _Dummy(build_runs={E: 1}, build_mats={E: [(X, 10)]},
               live={X: 25}, jobs_map={},
               jobs_alle=JOB_X_25,
               saved_plans=[FREMD_PLAN], open_plan_id=555,
               frozen={"plan_snapshot": {"build_runs": {E: 1}}, "ts": 2.0})
    pruefe("D: X fehlt 10 (fremde Pipeline zaehlt auch beim gefrorenen"
           " Plan nicht)", fehlt_map(d), {X: 10})
    print()
    print("ALLE ERWARTUNGEN GRUEN" if ok else "MINDESTENS EIN LOCH / BRUCH")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
