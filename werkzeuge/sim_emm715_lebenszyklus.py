"""LEBENSZYKLUS-SZENARIEN zur Job-Erkennung nach emm715/emm717.

Nutzer 25.10.2026: "und wuerde ich neue Bauplaene erstellen und speichern
freezen reservieren? haben wir nichts kaputt gemacht in der job erkennung?
fahre ein paar simulationen und szenarien".

Gefahren werden die ECHTEN Funktionen (keine Nachbauten, Regel 9):
  * MainWindowHelpers._aktive_jobs_filtern  (wer zaehlt beim gefrorenen Plan)
  * mw_helpers.delivered_sicher             (gelieferte Runs, umstritten/belegt)
  * mw_helpers.fertig_menge                 (Erledigt-Budget-Formel)
Nur der Store wird gemockt (die Zuordnungs-Tabelle laege sonst in sqlite),
und die eine emm715-Bedingung aus dem Zeilenaufbau wird als Formel
mitgefuehrt (sie ist inline; ihr UI-Verhalten pinnt der Suite-Anker b216).

Szenarien A-H decken den Weg ab: frisch -> gespeichert -> gefroren, jeweils
mit eigenen, fremden, zugeordneten, unzugeordneten und alten Jobs.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eve_trader import store                                   # noqa: E402
from eve_trader.ui.mw_helpers import (MainWindowHelpers,       # noqa: E402
                                      delivered_sicher, fertig_menge)

FEHLER = []


def pruef(name, bedingung, detail=""):
    marke = "[OK]    " if bedingung else "[FEHLER]"
    print(f"{marke} {name}" + (f"   ({detail})" if detail else ""))
    if not bedingung:
        FEHLER.append(name)


class _Self:
    """Traeger fuer die echten Methoden: nur die Attribute, die
    `_aktive_jobs_filtern` wirklich liest."""
    def __init__(self, pid, alle, plaene):
        self._bd_open_plan_id = pid
        self._bd_active_jobs_alle = {t: list(js) for t, js in alle.items()}
        self._bd_active_jobs_map = {t: list(js) for t, js in alle.items()}
        self.settings = {"bau_saved_plans": plaene}


def filtern(pid, alle, plaene, zuordnung):
    """Echte `_aktive_jobs_filtern` mit gemocktem Store laufen lassen.
    zuordnung: {job_id: plan_id}."""
    _alt1, _alt2 = store.job_zuordnung_fuer_plan, store.job_zuordnung_alle
    try:
        store.job_zuordnung_fuer_plan = lambda p: {
            j: {"plan_id": pl} for j, pl in zuordnung.items()
            if str(pl) == str(p)}
        store.job_zuordnung_alle = lambda: dict(zuordnung)
        s = _Self(pid, alle, plaene)
        MainWindowHelpers._aktive_jobs_filtern(s)
        return s._bd_active_jobs_map, getattr(s, "_bd_active_unzugeordnet", {})
    finally:
        store.job_zuordnung_fuer_plan, store.job_zuordnung_alle = _alt1, _alt2


def karte_gefiltert(pid, frozen):
    """Die ECHTE `_jobs_karte_plan_gefiltert` (emm717) auf einem Dummy."""
    class _K:
        pass
    k = _K()
    k._bd_open_plan_id = pid
    k._bd_frozen = frozen
    return MainWindowHelpers._jobs_karte_plan_gefiltert(k)


def budget(plan_runs, geliefert, jobs_map, pid, frozen, umstritten):
    """Die emm715/emm717-Formel aus dem Zeilenaufbau (mw_bauplan_tabs
    ~9250): Erledigt-Budget je Item. Karten-Jobs zaehlen nur bei WIRKLICH
    plan-gefilterter Karte (gefroren mit Snapshot+ts, emm717), sonst gilt
    die Umstritten-Regel wie beim frischen Plan."""
    zaehlen = karte_gefiltert(pid, frozen)
    out = {}
    for t, pl in plan_runs.items():
        fertig = int(geliefert.get(t, 0) or 0)
        if zaehlen or t not in umstritten:
            fertig += sum(int(j.get("runs") or 0)
                          for j in (jobs_map.get(t) or []))
        out[t] = fertig_menge(pl, fertig, 0)
    return out


ITEM = 16670                      # das umkaempfte Zwischenprodukt
PLAN_RUNS = {ITEM: 100}
FREMD = [{"id": 555, "label": "Fremdplan",
          "frozen": {"plan_snapshot": {"build_runs": {ITEM: 999}},
                     "ts": 1000.0}}]
UMSTRITTEN = {ITEM}               # der Fremdplan baut das Item selbst

FROZEN_777 = {"plan_snapshot": {"build_runs": {ITEM: 100}}, "ts": 1000.0}

print("=" * 72)
print("A) FRISCH, eigene Jobs, KEIN Konkurrent -> Fortschritt sichtbar")
_map, _ = filtern(None, {ITEM: [{"job_id": 1, "runs": 100,
                                 "status": "active"}]}, [], {})
_b = budget(PLAN_RUNS, {}, _map, None, None, set())
pruef("A: 100/100 erledigt", _b[ITEM] == 100, f"budget={_b[ITEM]}")

print("\nB) FRISCH, fremde Jobs, Konkurrent baut dasselbe -> zaehlt NICHT")
_map, _ = filtern(None, {ITEM: [{"job_id": 2, "runs": 99999,
                                 "status": "active"}]}, FREMD, {})
_b = budget(PLAN_RUNS, {}, _map, None, None, UMSTRITTEN)
pruef("B: 0/100 erledigt (emm715)", _b[ITEM] == 0, f"budget={_b[ITEM]}")

print("\nC) GESPEICHERT, noch NICHT gefroren: die Karte ist ungefiltert")
print("   (`_aktive_jobs_filtern` laeuft nur im Einfrier-Zweig). Bis")
print("   emm717 reichte die Plan-Id, und fremde Jobs fuellten das Budget")
print("   (Loch, am 25.10.2026 als C1 ehrlich ausgewiesen). Seit emm717")
print("   verlangt `_jobs_karte_plan_gefiltert` Plan-Id UND Einfrier-Stand")
print("   - sonst Umstritten-Regel wie beim frischen Plan.")
_roh = {ITEM: [{"job_id": 2, "runs": 99999, "status": "active"}]}
_b = budget(PLAN_RUNS, {}, _roh, 777, None, UMSTRITTEN)  # Karte ungefiltert
pruef("C1: gespeichert+ungefroren, fremder Job umstritten -> 0/100 (emm717)",
      _b[ITEM] == 0, f"budget={_b[ITEM]}")
pruef("C1b: die echte Bedingung sagt 'nicht gefiltert' (Plan-Id allein)",
      not karte_gefiltert(777, None))
pruef("C1c: ... auch mit frozen OHNE Snapshot/ts",
      not karte_gefiltert(777, {}) and karte_gefiltert(777, FROZEN_777))
_map, _ = filtern(777, _roh, FREMD + [{"id": 777, "label": "Meiner"}], {})
_b = budget(PLAN_RUNS, {}, _map, 777, None, UMSTRITTEN)
pruef("C2: der Zuordnungs-Filter kaeme zum selben Schluss (0/100)",
      _b[ITEM] == 0, f"budget={_b[ITEM]}")

print("\nD) GEFROREN, Job per Klick DIESEM Plan zugeordnet -> zaehlt")
_map, _offen = filtern(777, {ITEM: [{"job_id": 3, "runs": 60,
                                     "status": "active",
                                     "start_date": "2026-10-25T12:00:00Z"}]},
                       FREMD + [{"id": 777, "frozen": {"ts": 1000.0}}],
                       {3: "777"})
_b = budget(PLAN_RUNS, {}, _map, 777, FROZEN_777, UMSTRITTEN)
pruef("D: 60/100 erledigt", _b[ITEM] == 60, f"budget={_b[ITEM]}")
pruef("D: nichts haengt als 'unzugeordnet'", not _offen)

print("\nE) GEFROREN, Job gehoert laut Zuordnung dem FREMDPLAN -> zaehlt nicht")
_map, _offen = filtern(777, {ITEM: [{"job_id": 4, "runs": 99999,
                                     "status": "active",
                                     "start_date": "2026-10-25T12:00:00Z"}]},
                       FREMD + [{"id": 777, "frozen": {"ts": 1000.0}}],
                       {4: "555"})
_b = budget(PLAN_RUNS, {}, _map, 777, FROZEN_777, UMSTRITTEN)
pruef("E: 0/100 erledigt", _b[ITEM] == 0, f"budget={_b[ITEM]}")
pruef("E: und auch nicht als 'unzugeordnet' angeboten", not _offen)

print("\nF) GEFROREN, Job NIEMANDEM zugeordnet, NACH dem Einfrieren gestartet")
_map, _offen = filtern(777, {ITEM: [{"job_id": 5, "runs": 70,
                                     "status": "active",
                                     "start_date": "2026-10-25T12:00:00Z"}]},
                       FREMD + [{"id": 777, "frozen": {"ts": 1000.0}}], {})
_b = budget(PLAN_RUNS, {}, _map, 777, FROZEN_777, UMSTRITTEN)
pruef("F: zaehlt NICHT als erledigt (Regel 3)", _b[ITEM] == 0,
      f"budget={_b[ITEM]}")
pruef("F: steht aber als OFFENE FRAGE bereit",
      sum(int(j.get("runs") or 0) for j in (_offen.get(ITEM) or [])) == 70)

print("\nG) GEFROREN, unzugeordneter Job aus der Zeit VOR dem Einfrieren")
_map, _offen = filtern(777, {ITEM: [{"job_id": 6, "runs": 80,
                                     "status": "active",
                                     "start_date": "1970-01-01T00:00:30Z"}]},
                       FREMD + [{"id": 777, "frozen": {"ts": 1000.0}}], {})
pruef("G: zaehlt nicht und wird nicht angeboten (alter Durchlauf)",
      not _map.get(ITEM) and not _offen.get(ITEM))

print("\nH) GELIEFERTE Runs: delivered_sicher (umstritten/belegt/Deckel)")
_s = delivered_sicher({ITEM: 100}, PLAN_RUNS, UMSTRITTEN, None)
pruef("H1: umstritten ohne Beleg -> 0", int(_s.get(ITEM, 0) or 0) == 0)
_s = delivered_sicher({ITEM: 100}, PLAN_RUNS, UMSTRITTEN, {ITEM: 40})
pruef("H2: per Klick belegte 40 zaehlen trotz Streit",
      int(_s.get(ITEM, 0) or 0) == 40)
_s = delivered_sicher({ITEM: 500}, PLAN_RUNS, set(), None)
pruef("H3: Deckel auf die Plan-Runs (500 geliefert -> 100)",
      int(_s.get(ITEM, 0) or 0) == 100)

print("\n" + "=" * 72)
print("ALLE SZENARIEN GRUEN" if not FEHLER
      else f"{len(FEHLER)} SZENARIO(S) ROT: {FEHLER}")
sys.exit(1 if FEHLER else 0)
