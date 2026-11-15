"""Einen Bauplan mit den ECHTEN Daten des Nutzers nachrechnen - ohne Qt,
ohne Screenshot.

GEGENSTUECK zu `werkzeuge/export_sim_daten.py` (emm832). Das holt Preise,
Skills und Strukturen in eine Datei; dieses hier rechnet damit und gibt
genau die Zahlen aus, die sonst im Bauplan-Fenster stehen: Baukosten je
Stueck, Gewinn, Marge, die Invention-Aufschluesselung und die
Einkaufsliste.

WOZU: Bis emm831 kamen Zahlen-Befunde aus Screenshots. Drei Fehler in
Folge (Relic-Preis fehlte in der Karte, Skillbonus fehlte im Plan,
T3-Kopieranleitung) haetten sich hiermit ohne eine einzige Rueckfrage
nachstellen lassen.

WAS ES NICHT KANN: die OBERFLAECHE. Layout, Schriftbreiten, ob ein Knopf
sichtbar ist - dafuer bleibt der Screenshot das Mittel der Wahl (die
Breiten-Falle aus emm822 war genau so ein Fall: Windows misst breiter als
der Container).

AUFRUF:
    python werkzeuge\\sim_plan.py --item 34317 --menge 1
    python werkzeuge\\sim_plan.py --item Confessor --menge 10 --relic 34416
    python werkzeuge\\sim_plan.py --plan "Confessor"
    python werkzeuge\\sim_plan.py --item 34317 --kurve 1,2,4,8,12
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import industry                                 # noqa: E402


def _isk(v):
    return f"{v:,.0f}".replace(",", "'")


def _laden(pfad):
    with open(pfad, "r", encoding="utf-8") as f:
        return json.load(f)


def _preistabelle(daten, quelle=None):
    """{type_id: sell_min} aus dem Export. Ohne Angabe die Quelle mit den
    meisten Eintraegen - das ist in aller Regel der Haupt-Handelsplatz."""
    alle = daten.get("preise") or {}
    if not alle:
        return {}, ""
    if quelle is None:
        quelle = max(alle, key=lambda k: len(alle[k]))
    pm = {}
    for t, v in (alle.get(quelle) or {}).items():
        s = v.get("sell")
        if s and s > 0:
            pm[int(t)] = float(s)
    return pm, quelle


def _opts(daten, recipes, relic=None, decryptor_map=None):
    """Die opts einer Bauplan-Rechnung aus den exportierten Einstellungen.

    BEWUSST SCHLANK: hier wird nicht das ganze Fenster nachgebaut, sondern
    das, was die Kosten bestimmt. Was fehlt, faellt auf die Vorgaben von
    `industry` zurueck - und steht unten in der Ausgabe, damit niemand eine
    Zahl fuer vollstaendiger haelt, als sie ist.
    """
    s = daten.get("settings") or {}
    adj = {int(k): v for k, v in (daten.get("adjusted") or {}).items()}
    o = {
        "me": float(s.get("bau_me", 0) or 0),
        "te": float(s.get("bau_te", 0) or 0),
        "job_pct": s.get("bau_job_pct", 3),
        "build_reactions": True,
        "invention": True,
        "tree_depth": 6,
        "adjusted_prices": adj,
        "inv_confidence": float(s.get("bau_inv_confidence",
                                      industry.DEFAULT_INVENTION_CONFIDENCE)),
    }
    if relic:
        o["inv_relic_map"] = dict(relic)
    if decryptor_map:
        o["inv_decryptor_map"] = dict(decryptor_map)
    # Invention-Skillbonus wie im Fenster: bester Charakter unter denen, die
    # als "Fuer Invention" markiert sind (dieselbe Formel, industry.
    # invention_skill_modifier) - genau der Posten, der in emm828 im Plan
    # fehlte, waehrend die Karte ihn hatte.
    skills = s.get("bau_char_skills") or {}
    inv_chars = [str(c) for c in (s.get("bau_invention_chars") or [])]
    if skills and inv_chars:
        karte = industry.bp_invention_skills_map()
        mods = {}
        for bp_id, eintrag in (recipes.invention_for_bpc or {}).items():
            quelle = industry.invention_quelle_fuer_bp(bp_id, recipes, o)
            t1 = (quelle or eintrag)[0]
            best = 1.0
            for cid in inv_chars:
                sk = skills.get(cid) or {}
                sk_int = {}
                for k, v in sk.items():
                    try:
                        sk_int[int(k)] = int(v)
                    except (TypeError, ValueError):
                        continue
                try:
                    m = industry.invention_skill_modifier(t1, sk_int, karte)
                except Exception:
                    m = 1.0
                best = max(best, m)
            if best != 1.0:
                mods[bp_id] = best
        if mods:
            o["inv_skill_modifier"] = mods
    return o


def _item_id(wert, recipes):
    """Zahl oder Name -> type_id. Der Name geht ueber dieselbe Stelle wie im
    Programm (`industry.type_id_for_name`), damit hier nichts anderes
    gefunden wird als dort."""
    try:
        return int(wert)
    except (TypeError, ValueError):
        pass
    tid = industry.type_id_for_name(str(wert))
    if tid:
        return int(tid)
    raise SystemExit(f"Item {wert!r} nicht gefunden - bitte die type_id angeben.")


def _zeige(tid, menge, pm, recipes, o, verkauf=None, vorwahl=True):
    plan = industry.production_plan(tid, menge, pm.get, recipes, o)
    if not plan:
        print("  kein Plan (nicht baubar?)")
        return None
    # DIESELBE RELIC-VORWAHL WIE DAS FENSTER (emm830, main_window.job()):
    # ohne sie rechnete dieses Werkzeug mit der ERGIEBIGSTEN Quelle,
    # waehrend das Programm die BILLIGSTE nimmt - also genau die zweite
    # Wahrheit, die wir hier eigentlich aufdecken wollen (Arbeitsregel 9).
    if vorwahl and not o.get("inv_relic_map"):
        runs = {}
        for _t, _r in (plan.get("build_runs") or {}).items():
            _bp = (recipes.product_to_bp or {}).get(int(_t))
            if _bp and _bp[1] == industry.MANUFACTURING:
                runs[_bp[0]] = int(_r or 0)
        wahl = industry.beste_relic_quellen(recipes, runs, pm.get, o)
        if wahl:
            o["inv_relic_map"] = wahl
            plan = industry.production_plan(tid, menge, pm.get, recipes, o)
    # EHRLICH BLEIBEN: Material ohne Preis zaehlt mit 0 und macht den Plan
    # zu billig. Das MUSS dastehen, sonst liest sich eine Luecke wie ein
    # Ergebnis (Arbeitsregel 1).
    _ohne = [t for t in (plan.get("buy") or {}) if not pm.get(int(t))]
    if _ohne:
        print(f"  WARNUNG: {len(_ohne)} Einkaufsposten ohne Preis "
              f"(z.B. {_ohne[:4]}) - die Kosten sind zu NIEDRIG.")
    kosten = float(plan["total_cost"])
    je = kosten / max(1, menge)
    zeile = f"  Menge {menge:>4}  Baukosten/Stueck {_isk(je):>16}"
    if verkauf:
        gewinn = verkauf * menge - kosten
        zeile += (f"  Gewinn {_isk(gewinn):>16}"
                  f"  Marge {gewinn / (verkauf * menge) * 100:>6.1f}%")
    inv = float(plan.get("inv_cost", 0) or 0)
    if inv:
        zeile += f"  (Invention {_isk(inv / max(1, menge))}/Stueck)"
    print(zeile)
    return plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--daten", default=os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "berichte", "sim_daten.json"))
    p.add_argument("--item", default=None, help="type_id oder Name")
    p.add_argument("--menge", type=int, default=1)
    p.add_argument("--plan", default=None,
                   help="Name eines exportierten Plans statt --item/--menge")
    p.add_argument("--relic", default=None,
                   help="bp_id:type_id - Relic-Wahl erzwingen")
    p.add_argument("--quelle", default=None, help="Preis-Quelle (Handelsplatz)")
    p.add_argument("--kurve", default=None,
                   help="Mengen mit Komma, z.B. 1,2,4,8,12 - zeigt, ab wann "
                        "sich die Invention rechnet")
    p.add_argument("--material", action="store_true",
                   help="die Einkaufsliste mit ausgeben")
    a = p.parse_args()

    if not os.path.exists(a.daten):
        raise SystemExit(f"{a.daten} fehlt - erst werkzeuge\\export_sim_daten.py "
                         f"auf dem Rechner mit der Installation laufen lassen.")
    daten = _laden(a.daten)
    pm, quelle = _preistabelle(daten, a.quelle)
    recipes = industry.recipes_cached()
    print(f"Daten vom {daten.get('erstellt')} - Preisquelle {quelle!r} "
          f"({len(pm)} Preise)")
    if not daten.get("adjusted"):
        print("HINWEIS: keine Adjusted Prices im Export (--esi beim Export) - "
              "Jobgebuehren und EIV fehlen, die Kosten sind damit zu NIEDRIG.")

    relic = None
    if a.relic:
        bp, tid = a.relic.split(":")
        relic = {int(bp): int(tid)}

    if a.plan:
        plaene = [x for x in (daten.get("plaene") or [])
                  if a.plan.lower() in str(x.get("label") or "").lower()
                  or a.plan.lower() in str(x.get("item_name") or "").lower()]
        if not plaene:
            raise SystemExit(f"Kein exportierter Plan passt zu {a.plan!r}. "
                             f"Vorhanden: {daten.get('plan_namen')}")
        for pl in plaene:
            tid = int(pl["type_id"])
            menge = int(pl.get("qty", 1) or 1)
            o = _opts(daten, recipes,
                      relic=relic or {int(k): int(v) for k, v in
                                      (pl.get("relic_map") or {}).items()})
            o["me"] = float(pl.get("me", o["me"]) or 0)
            print(f"\nPlan {pl.get('label') or pl.get('item_name')}:")
            _zeige(tid, menge, pm, recipes, o, verkauf=pm.get(tid))
        return 0

    if not a.item:
        raise SystemExit("--item oder --plan angeben.")
    tid = _item_id(a.item, recipes)
    o = _opts(daten, recipes, relic=relic)
    verkauf = pm.get(tid)
    print(f"\nItem {tid}  Verkauf (sell) {_isk(verkauf) if verkauf else '-'}")
    mengen = ([int(x) for x in a.kurve.split(",")] if a.kurve
              else [a.menge])
    letzter = None
    for m in mengen:
        letzter = _zeige(tid, m, pm, recipes, o, verkauf=verkauf) or letzter
    if a.material and letzter:
        print("\nEinkaufsliste (buy):")
        for t, q in sorted((letzter.get("buy") or {}).items(),
                           key=lambda kv: -kv[1]):
            print(f"  {t:>8}  {q:>8}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
