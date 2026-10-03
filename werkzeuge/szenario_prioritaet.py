"""SZENARIO: Plaene umsortieren mitten im Bauen - was passiert mit
Runplaner-Runs und reservierten Materialien? (Nutzer 28.09.2026: "koennen wir
das testen ... wenn ich den Plan wieder zurueckschiebe, sind die Runs noch am
selben Arbeitsprozess wie vorher?").

Spielt einen Ablauf mit drei eingefrorenen Plaenen durch, die dasselbe
Zwischenprodukt X und denselben Rohstoff M brauchen - mit den ECHTEN
Funktionen des Programms (Reservierung, Rangfolge, Job-Zuordnung, sichere
Liefer-Karte). Nur die Fensterteile sind nachgestellt, und zwar mit genau den
Zeilen, die das Fenster auch rechnet (Kommentar an jeder Stelle).

Aufruf:  python werkzeuge/szenario_prioritaet.py
Ergebnis: Bericht auf dem Schirm; `szenario()` liefert die Zustaende fuer die
Pruefung aa437. Die echte Datenbank wird NICHT angefasst (eigene Temp-Datei).
"""
import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from eve_trader import config, store                       # noqa: E402
from eve_trader.ui.mw_helpers import (MainWindowHelpers as H,  # noqa: E402
                                      delivered_sicher)

X, K, M = 9001, 9002, 34          # Zwischenprodukt (Reaktion), Komponente, Rohstoff
NAMEN = {X: "X (Reaktion)", K: "K (Komponente)", M: "M (Rohstoff)"}


def _iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


class _Fenster(H):
    """Das, was ein offenes Bauplan-Fenster fuer die Zuordnung braucht."""

    def __init__(self, welt, pid):
        self.settings = welt["settings"]
        self._bd_open_plan_id = pid
        self._bd_delivered_jobs = [j for j in welt["jobs"] if j["status"] == "delivered"]
        self._bd_active_jobs_alle = {}
        for j in welt["jobs"]:
            if j["status"] == "active":
                self._bd_active_jobs_alle.setdefault(j["product_type_id"], []).append(j)
        self._bd_active_jobs_map = dict(self._bd_active_jobs_alle)

        class _R:
            reaction_products = {X}
        self._bd_recipes = _R()

    def _log_exception(self, wo, text):
        print(f"   !! Fehler in {wo}: {text}")


def _plan(pid, name, t0):
    snap = {"build_runs": {X: 10, K: 10},
            "build_mats": {K: [[X, 100]], X: [[M, 500]]}}
    return {"id": pid, "label": name, "reserve": True,
            # wie im echten Plan: der Verbrauch steht drin, auch der des
            # Zwischenprodukts X (K frisst 100) - daran erkennt das Programm,
            # dass X "strittig" ist, sobald zwei Plaene es brauchen
            "reserve_map": {str(M): 500, str(X): 100},
            "assignments": [
                {"tid": X, "runs": 10, "stage": "reaction_2", "char_id": 7},
                {"tid": K, "runs": 10, "stage": "component", "char_id": 7}],
            "frozen": {"ts": t0, "plan_snapshot": H._plan_snapshot_pack(snap),
                       "stock_seen_ts": t0}}


def _fenster_oeffnen(welt, pid):
    """Wie `_fill_bauplan_schedule`: Jobs zuordnen (Klick, eindeutig,
    Prioritaet) - das passiert bei jedem Oeffnen des Plans."""
    p = next(p for p in welt["settings"]["bau_saved_plans"] if p["id"] == pid)
    _Fenster(welt, pid)._job_zuordnung_nachfuehren(p["assignments"], p["frozen"]["ts"])


def _bestandsabruf(welt):
    """ESI-Bestand neu: jeder Plan merkt sich die Bestandszeit (wie
    `stock_seen_ts` im Fenster) - erst danach geben Belege frei."""
    jetzt = time.time() + 1
    for p in welt["settings"]["bau_saved_plans"]:
        p["frozen"]["stock_seen_ts"] = jetzt


def _zustand(welt):
    s = welt["settings"]
    rang = H.plan_rang(s)
    aus = {}
    for p in s["bau_saved_plans"]:
        pid = p["id"]
        # --- MATERIAL: `_reservierungen_anwenden` -------------------------
        lager = dict(welt["hangar"])
        fremd, _ = H._reserved_by_other_plans(s, pid)
        eigen = H._reserved_by_this_plan(s, pid)
        if str(pid) in rang:
            eigen = {}
        H.bestand_nach_reservierungen(lager, fremd, eigen)
        eigene_res = H._reserved_by_this_plan(s, pid).get(M, 0)
        # --- RUNPLANER-REST: wie `_fill_bauplan_schedule` -----------------
        seit = p["frozen"]["ts"]
        geliefert_alle = [j for j in welt["jobs"] if j["status"] == "delivered"]
        _, geliefert = H._frozen_auto_checked(geliefert_alle, p["assignments"], seit)
        zu = store.job_zuordnung_fuer_plan(pid)
        belegt = {}
        for j in geliefert_alle:
            if int(j["job_id"]) in zu:
                belegt[j["product_type_id"]] = belegt.get(j["product_type_id"], 0) + j["runs"]
        plan_runs = {X: 10, K: 10}
        sicher = delivered_sicher(geliefert, plan_runs, H._umstrittene_items(s, pid), belegt)
        # laufende Jobs: wie das Fenster seit emm268 NUR die dieses Plans
        # (`_aktive_jobs_filtern`), die unzugeordneten extra
        fen = _Fenster(welt, pid)
        fen._aktive_jobs_filtern()
        rest = {}
        for t, pr in plan_runs.items():
            lauf = sum(j["runs"] for j in (fen._bd_active_jobs_map.get(t) or []))
            rest[t] = pr - min(pr, int(sicher.get(t, 0)) + lauf)
        offen_lauf = sorted(j["job_id"] for js in fen._bd_active_unzugeordnet.values()
                            for j in js)
        aus[p["label"]] = {"rang": rang.get(str(pid)), "M_frei": lager.get(M, 0),
                           "M_reserviert": eigene_res, "rest_X": rest[X],
                           "rest_K": rest[K],
                           "jobs": sorted(zu), "laeuft_offen": offen_lauf}
    return aus


def _zeigen(titel, z):
    print(f"\n== {titel}")
    print(f"   {'Plan':<8}{'Rang':>5}{'M frei':>8}{'M res.':>8}"
          f"{'Rest X':>8}{'Rest K':>8}   Jobs   (laeuft, niemandem zugeordnet)")
    for name, d in z.items():
        print(f"   {name:<8}{str(d['rang'] or '-'):>5}{d['M_frei']:>8}"
              f"{d['M_reserviert']:>8}{d['rest_X']:>8}{d['rest_K']:>8}   {d['jobs']}"
              f"   {d['laeuft_offen'] or ''}")


def szenario(zeigen=True):
    tmp = tempfile.mkdtemp(prefix="szenario_prio_")
    _alt_db = config.db_path
    config.db_path = lambda: os.path.join(tmp, "szenario.db")
    try:
        t0 = time.time() - 2 * 86400
        welt = {"settings": {"bau_saved_plans": [_plan(1, "A", t0), _plan(2, "B", t0),
                                                 _plan(3, "C", t0)],
                             "bau_plan_reihenfolge": ["1", "2", "3"]},
                "hangar": {M: 1000}, "jobs": []}
        z = {}
        z["1"] = _zustand(welt)
        # 2. A baut: Klick auf die X-Zeile, Job startet, ESI sieht ihn laufen.
        store.run_klick_merken(1, X, 10, True, ts=t0 + 100)
        welt["jobs"].append({"job_id": 501, "product_type_id": X, "runs": 10,
                             "activity_id": 11, "status": "active",
                             "start_date": _iso(t0 + 200), "completed_date": None})
        welt["hangar"][M] = 500                 # der Reaktor hat M gefressen
        _fenster_oeffnen(welt, 1)
        _bestandsabruf(welt)
        z["2"] = _zustand(welt)
        # 2b. Ein zweiter X-Job laeuft OHNE Klick (X brauchen alle drei):
        # die Prioritaet gibt ihn beim Oeffnen gleich #1 mit Platz (B).
        welt["jobs"].append({"job_id": 503, "product_type_id": X, "runs": 10,
                             "activity_id": 11, "status": "active",
                             "start_date": _iso(t0 + 300), "completed_date": None})
        z["2b_vor"] = _zustand(welt)
        _fenster_oeffnen(welt, 3)
        _bestandsabruf(welt)
        z["2b"] = _zustand(welt)
        # 3. C nach oben geschoben; danach liefert ein X-Job OHNE Klick ab.
        welt["settings"]["bau_plan_reihenfolge"] = ["3", "1", "2"]
        z["3a"] = _zustand(welt)
        for j in welt["jobs"]:
            if j["job_id"] == 501:
                j.update(status="delivered", completed_date=_iso(t0 + 900))
        welt["jobs"].append({"job_id": 502, "product_type_id": X, "runs": 10,
                             "activity_id": 11, "status": "delivered",
                             "start_date": _iso(t0 + 1000),
                             "completed_date": _iso(t0 + 2000)})
        welt["hangar"][X] = 10
        _fenster_oeffnen(welt, 2)
        _bestandsabruf(welt)
        z["3b"] = _zustand(welt)
        # 4. C wieder zurueck nach unten.
        welt["settings"]["bau_plan_reihenfolge"] = ["1", "2", "3"]
        z["4"] = _zustand(welt)
        if zeigen:
            print("SZENARIO: drei eingefrorene Plaene A, B, C - je 10 Runs X "
                  "(braucht 500 M) und 10 Runs K. Hangar: 1'000 M.")
            _zeigen("1. Start, Reihenfolge A, B, C", z["1"])
            _zeigen("2. A klickt X, startet den Job (laeuft), naechster Bestandsabruf",
                    z["2"])
            _zeigen("2b. zweiter X-Job laeuft OHNE Klick - noch kein Plan geoeffnet",
                    z["2b_vor"])
            _zeigen("2b. ... Plan geoeffnet: Prioritaet ordnet ihn zu", z["2b"])
            _zeigen("3a. C nach ganz oben geschoben (C, A, B)", z["3a"])
            _zeigen("3b. As Job abgeliefert; ein zweiter X-Job OHNE Klick "
                    "abgeliefert, B geoeffnet", z["3b"])
            _zeigen("4. C wieder nach unten (A, B, C)", z["4"])
        return z
    finally:
        config.db_path = _alt_db


if __name__ == "__main__":
    szenario()
