"""PRÜFT DIE RIG-WIRKUNG GEGEN DIE ECHTE SDE - OHNE ITEM-NAMEN (emm719,
25.10.2026, Nutzer "punkt 1 finde wege es selber zu loesen").

VORGESCHICHTE: dieses Skript versuchte urspruenglich, Item-Namen aus der
lokalen SDE zu lesen (`item_cat.name` / `item_cat.type_name`). Beide Spalten
gibt es dort NICHT - PRAGMA table_info(item_cat) zeigt nur type_id, group_id,
category_id, meta_group_id, meta_level, volume, packaged_volume, race_id.
Item-Namen kommen im Tool ausschliesslich live von ESI (esi.resolve_names),
nicht aus der lokalen DB - der alte, namensbasierte Ansatz war offline also
grundsaetzlich nicht pruefbar und lieferte nur "NICHT IN DER SDE-TABELLE".

NEUER ANSATZ: die Tabelle `rigs` fuehrt pro Rig die rohen SDE-Effekt-Strings
(Spalte `effects`, z.B. "rigAdvLarShipManufactureMaterialBonus,
rigAdvLarShipManufactureTimeBonus"). Diese laufen DIREKT durch die echte
`industry.rig_domains()` - ganz ohne Item-Namen. Damit wurde am 25.10.2026
GEMESSEN (nicht geraten), dass `_RIG_EFFECT_DOMAINS` die 12 Schiffsgroessen-
Fertigungs-Rigs (Basic/Advanced x Small/Medium/Large, I/II, in L- UND
M-Set) sowie das XL-Set-"AllShip"-Rig NICHT traf - sie wirkten im Tool mit
0 % Bonus trotz Einbau. Behoben in emm719 (siehe MEMORY.md).

Aufruf:  python3 werkzeuge/pruefe_rig_wirkung.py
Gibt 0 zurueck, wenn ausser den (anderer Mechanismus, bewusst leer) Moon-
Drilling-Rigs kein Fertigungs-/Efficiency-Rig mehr ohne Domaene bleibt.
"""
import sqlite3
import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL))

from eve_trader import industry  # noqa: E402

# Ein paar konkrete Item/Rig-Paare zur Veranschaulichung (Schnittmenge
# Rig-Domaenen x Item-Domaenen, OHNE Item-Namen - category_id/group_name/
# meta_group_id sind handfeste SDE-Felder, keine Vermutung):
PROBEN_ITEMS = [
    # (Anzeige-Label, category_id, group_name, meta_group_id)
    ("Frigate (Basic Small Ship)", 6, "Frigate", None),
    ("Assault Frigate (T2, Advanced Small Ship)", 6, "Assault Frigate", 2),
    ("Cruiser (Basic Medium Ship)", 6, "Cruiser", None),
    ("Dreadnought (Capital Ship)", 6, "Dreadnought", None),
]


def main():
    db = industry._db_path()
    if not Path(db).exists():
        print(f"sde_kompakt.db nicht gefunden: {db}")
        return 1
    con = sqlite3.connect(db)
    rows = con.execute(
        "SELECT name, effects FROM rigs WHERE name LIKE 'Standup%'"
    ).fetchall()
    con.close()
    print(f"{len(rows)} Standup-Rigs in der SDE gefunden.\n")

    leer, belegt = [], []
    for name, effects in rows:
        effs = [e.strip() for e in (effects or "").split(",") if e.strip()]
        doms = industry.rig_domains(effs)
        relevant = ("manufactur" in name.lower()
                    or "efficiency" in name.lower())
        if doms:
            belegt.append((name, effects, doms))
        elif relevant:
            leer.append((name, effects))

    bekannt_anders = [n for n, _ in leer if "moon drilling" in n.lower()]
    echte_luecken = [(n, e) for n, e in leer
                      if "moon drilling" not in n.lower()]

    print("=" * 78)
    print("BEISPIEL: TRIFFT DAS 'AllShip'-RIG (Standup XL-Set) DIE RICHTIGEN "
          "ITEMS?")
    print("=" * 78)
    allship = industry.rig_domains(["rigAllShipManufactureMaterialBonus"])
    print(f"  Rig-Domaenen: {sorted(allship)}")
    for label, cat, grp, meta in PROBEN_ITEMS:
        dom = industry.item_domains(cat, grp, meta)
        greift = bool(dom & allship)
        dom_txt = ", ".join(sorted(dom))
        print(f"    {label:46s} Item-Domaenen {dom_txt:35s} "
              f"{'WIRKT' if greift else 'wirkt nicht'}")

    print()
    print("=" * 78)
    print("VOLLER SWEEP GEGEN ALLE ECHTEN STANDUP-RIGS")
    print("=" * 78)
    print(f"Domaene gefunden:            {len(belegt)}")
    print(f"Leer, aber bekannt anderer Mechanismus (Moon Drilling): "
          f"{len(bekannt_anders)}")
    print(f"ECHTE LUECKEN (Fertigungs-/Efficiency-Rig ohne Domaene): "
          f"{len(echte_luecken)}")
    for n, e in echte_luecken:
        print(f"  FEHLT: {n} -> {e}")

    if echte_luecken:
        print("\nFEHLGESCHLAGEN - siehe Liste oben.")
        return 1
    print("\nOK - alle Fertigungs-/Efficiency-Rigs matchen eine Domaene.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
