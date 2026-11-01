"""MESSUNG zu emm718: eine GEKAUFTE Vorstufe (nie in build_runs, weil ihre
Blaupausen-Kategorie nicht als besessen markiert ist - `never_build_hit`)
wird vom Rest-Bedarf trotzdem korrekt ausgeschlossen, sobald ihr einziger
Verbraucher voll geliefert ist.

Nutzer 25.10.2026, Gallente-1-Buendel: "Materials Tab zeigt wieder ich
haette intermediate reactions nicht, ja logisch habe ich nicht mehr es ist
alles verbaut bereits zu composite Reactions". Die ECHTE Rechnung
(`fehlbedarf_vorschau`, pur) hatte das laengst richtig erkannt - der Fehler
lag allein in der ANZEIGE (`_fill_material_tab`, mw_bauplan_tabs.py): der
"Blueprint not marked as owned"-Hinweis ueberschrieb die korrekt berechnete
Zeile UNBEDINGT, ganz gleich ob gerade etwas fehlte oder nicht.

Aufruf: python3 werkzeuge/sim_emm718.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from eve_trader.ui.mw_helpers import fehlbedarf_vorschau   # noqa: E402

FEHLER = []


def pruef(name, bedingung, detail=""):
    marke = "[OK]    " if bedingung else "[FEHLER]"
    print(f"{marke} {name}" + (f"   ({detail})" if detail else ""))
    if not bedingung:
        FEHLER.append(name)


COMPOSITE = 302
INTERMEDIATE = 300   # NIE in build_runs (never_build_hit -> gekauft)

build_runs = {COMPOSITE: 10}
build_mats = {COMPOSITE: [(INTERMEDIATE, 1000)]}
out_qty = {COMPOSITE: 1}

print("A) Composite 4/10 geliefert -> Intermediate wird noch gebraucht")
_a = fehlbedarf_vorschau(build_runs, build_mats, out_qty, {COMPOSITE: 4}, {})
pruef("A: Intermediate steht im Rest-Bedarf (600 fehlen)",
      any(m == INTERMEDIATE and f == 600 for m, f, *_ in _a), f"{_a}")

print("\nB) Composite 10/10 (VOLL) geliefert -> Intermediate NICHT mehr")
_b = fehlbedarf_vorschau(build_runs, build_mats, out_qty, {COMPOSITE: 10}, {})
pruef("B: Intermediate steht NICHT mehr im Rest-Bedarf (emm718 bestaetigt)",
      not any(m == INTERMEDIATE for m, *_ in _b), f"{_b}")

print("\n" + "=" * 72)
print("ALLE SZENARIEN GRUEN" if not FEHLER
      else f"{len(FEHLER)} SZENARIO(S) ROT: {FEHLER}")
sys.exit(1 if FEHLER else 0)
