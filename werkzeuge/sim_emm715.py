"""SIMULATION emm715 - frischer Plan erbt Fortschritt fremder Plaene.

Nutzer 25.10.2026, Vagabond NEU erstellt: "im runplaner wird schon angezeigt
ich haette Fuel Reactions fertig gemacht, und components auch schon, dabei
sind all diese Sachen in anderen Bauplaenen reserviert".

Stellt die Kette mit den ECHTEN reinen Helfern nach (fertig_menge,
vorstufen_erledigt aus mw_helpers) - nur das Erledigt-Budget selbst wird
in beiden Fassungen nachgebildet, weil es inline im Zeilenaufbau steht:

  ALT (mw_bauplan_tabs.py ~9216): laufende Jobs zaehlen IMMER ins Budget,
      auch beim ungespeicherten Plan, wo `_bd_active_jobs_map` ALLE Jobs
      aller Plaene traegt.
  NEU (ausgeliefert): beim ungespeicherten Plan zaehlen laufende Jobs nur
      fuer Items, die KEIN anderer offener Plan baut (`_umstrittene_items`,
      dieselbe Regel wie `delivered_sicher`). Beim gespeicherten Plan ist
      die Karte plan-gefiltert (emm268/emm422) und zaehlt wie bisher.
      Damit bleibt der b41-Fall intakt: eigene Jobs an einem Plan ohne
      Konkurrenten tragen weiter Lauf-Punkt und fertige Stufe.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from eve_trader.ui.mw_helpers import fertig_menge, vorstufen_erledigt  # noqa: E402

# --- Szenario: frischer Vagabond-Plan, nichts davon je gestartet -----------
# Vereinfachte Kette: Fuel -> Reaktion -> Komponente. IDs frei gewaehlt.
FUEL, REAKT, KOMP = 4051, 16670, 11530
build_runs = {FUEL: 10, REAKT: 100, KOMP: 446}
build_mats = {                      # Verbraucher je Vorstufe
    REAKT: [(FUEL, 1)],             # die Reaktion frisst Fuel
    KOMP: [(REAKT, 1)],             # die Komponente frisst die Reaktion
}
# ESI: fuer ANDERE Plaene laufen riesige Jobs derselben Items.
fremde_jobs = {REAKT: 2000, KOMP: 2255}
geliefert = {}                       # dieser Plan hat nie etwas geliefert
open_plan_id = None                  # UNGESPEICHERT
# Die anderen Plaene BAUEN genau diese Items selbst -> umstritten
# (`_umstrittene_items` via plan_baut_items).
umstritten = {FUEL, REAKT, KOMP}


def erledigt_budget(variante):
    """Nachbildung von mw_bauplan_tabs ~9214: `_rest_budget` traegt die
    ERLEDIGTE Menge je Item (fertig_menge = geliefert+laufend, gedeckelt
    auf die Plan-Runs) - weiter unten dient sie als Erledigt-Karte.
    variante: "alt" = laufende Jobs zaehlen immer;
              "neu" = ausgelieferte Regel (gespeichert ODER unumstritten)."""
    gespeichert = bool(open_plan_id)
    out = {}
    for t, pl in build_runs.items():
        fertig = int(geliefert.get(t, 0) or 0)
        if variante == "alt" or gespeichert or t not in umstritten:
            fertig += int(fremde_jobs.get(t, 0) or 0)
        out[t] = fertig_menge(pl, fertig, 0)
    return out


def stufen_offen(erl):
    """Offene Runs je Item, nachdem die Vorstufen-Regel (echte Funktion)
    das Erledigt-Budget angehoben hat - wie im Runplaner-Aufbau."""
    vs = vorstufen_erledigt(build_runs, build_mats, erl)
    offen = {t: build_runs[t] - int(erl.get(t, 0) or 0)
             for t in build_runs}
    for t in vs:
        offen[t] = 0
    return offen


print("Frischer, UNGESPEICHERTER Plan - fremde Jobs laufen fuer andere Plaene")
print(f"  Plan-Runs: Fuel {build_runs[FUEL]}, Reaktion {build_runs[REAKT]}, "
      f"Komponente {build_runs[KOMP]}")
print(f"  Fremde laufende Jobs: Reaktion {fremde_jobs[REAKT]}, "
      f"Komponente {fremde_jobs[KOMP]}\n")

fehler = 0
for name, zaehlen in (("ALT (laufende Jobs zaehlen immer)", "alt"),
                      ("NEU (umstrittene Items zaehlen nicht)", "neu")):
    rest = erledigt_budget(zaehlen)
    offen = stufen_offen(rest)
    fuel_falsch = offen[FUEL] == 0
    print(f"{name}")
    for t, lbl in ((FUEL, "Fuel"), (REAKT, "Reaktion"), (KOMP, "Komponente")):
        marke = ""
        if offen[t] == 0:
            marke = "  -> Stufe erscheint ERLEDIGT/Completed"
        print(f"   {lbl:11s} offen: {offen[t]:>4}{marke}")
    if fuel_falsch and offen[REAKT] == 0:
        print("   !! GENAU der Nutzer-Befund: Fuel + Reaktion 'Completed',")
        print("      obwohl dieser Plan nie einen Job gestartet hat")
        if name.startswith("NEU"):
            fehler += 1
    print()

print("NEU-Fassung korrekt" if fehler == 0 else "NEU-Fassung FALSCH")
