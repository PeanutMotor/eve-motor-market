"""Vergleicht die GECACHTE Preis-Historie (das, was der Scanner gerade
analysiert) mit einer FRISCH von ESI geholten Historie - fuer die Items,
deren Tradability-Punkte-Anzeige dem Nutzer widerspruechlich vorkam
(Fassung 1, 17.10.2026).

WOZU: Nutzer-Screenshot (Daytrade, Preset "Hidden gems - higher margin")
zeigte z. B. "Remote Sensing" mit Marge 260 % und Tradability nur 1 Punkt
(trade_score 31) - obwohl das Item laut Nutzer-Einschaetzung eigentlich gut
handelbar sein sollte. KEINE URSACHE BENANNT, bevor hier gemessen wurde
(Regel 5): entweder der trade_score ist bei diesem Item tatsaechlich
niedrig (dann ist die Anzeige korrekt und die Frage betrifft die
Preset-Schwelle), oder der Scanner hat mit einer VERALTETEN gecachten
Historie gerechnet (scanner._CACHE_ANALYZE_MAX_AGE_H = 168 h = 7 Tage gilt
als "frisch genug" fuer den Gratis-Topf - bei pausiertem Abruf
(max_cached_items ueberschritten) kann die Historie trotzdem bis zu 7 Tage
alt sein, bevor sie ueberhaupt als "nicht mehr frisch" aussortiert wird).

Was dieser Bericht macht, je Item:
  1. GECACHT: liest `history` + `history_meta` direkt aus ledger.db (nur
     lesend, keine neue Verbindung ueber store, um sicher nichts zu
     schreiben) und rechnet denselben trade_score wie der Scanner
     (scanner.window_stats) auf dieser gecachten Historie.
  2. LIVE: holt per ESI (OEFFENTLICH, kein Login/Token noetig) die aktuelle
     Historie und rechnet denselben trade_score darauf.
  3. Zeigt beides nebeneinander, dazu das Alter des Caches.

Grosse Abweichung GECACHT vs. LIVE = Cache-Alter ist die Ursache. Beide
etwa gleich (und beide niedrig) = die Anzeige stimmt, die Frage betrifft
dann die Preset-Schwellen, nicht den Scanner.

AUFRUF: werkzeuge\\zeige_tradability.bat doppelklicken, oder
  TS_SUCHE="Item A,Item B" python werkzeuge\\zeige_tradability.py
Danach liegt `berichte\\tradability_bericht.txt` da.
Es wird NUR GELESEN (ledger.db nur per SELECT) und per ESI nur per GET/POST
auf den oeffentlichen /universe/ids/- und /markets/.../history/-Endpunkt -
keine Datenbank-Schreibung, kein Login.
"""
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import config, esi, scanner, store   # noqa: E402

FASSUNG = 1
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERICHT = os.path.join(WURZEL, "berichte", "tradability_bericht.txt")

# Vorgabe: genau die vier Items aus dem Nutzer-Screenshot (Daytrade,
# "Hidden gems - higher margin"). TS_SUCHE ueberschreibt das.
_VORGABE = ("Remote Sensing,Heavy Energy Nosferatu I,"
            "Caldari Battleship,Interplanetary Consolidation")


def _resolve_type_id(name: str):
    """Name -> type_id. Erst der lokale Namens-Cache (meist schon da, weil
    das Item in einem Scan auftauchte), sonst live ueber /universe/ids/
    (oeffentlich, kein Login - derselbe Weg wie esi.resolve_corp_id)."""
    try:
        treffer = store.name_to_type_id().get(name.strip().lower())
        if treffer:
            return int(treffer)
    except Exception:
        pass
    try:
        r = esi._session.post(f"{config.ESI_BASE}/universe/ids/",
                              params={"datasource": "tranquility"},
                              json=[name], timeout=20)
        if r.status_code == 200:
            for eintrag in (r.json() or {}).get("inventory_types") or []:
                if (eintrag.get("name") or "").strip().lower() == name.strip().lower():
                    return int(eintrag["id"])
    except Exception:
        pass
    return None


def _gecachte_historie_roh(type_id: int, region: int):
    """Direkt aus ledger.db lesen (SELECT only) - bewusst NICHT ueber
    store._conn(), damit dieses Werkzeug garantiert keine Verbindung offen
    haelt, die das laufende Programm stoeren koennte."""
    pfad = config.db_path()
    if not os.path.exists(pfad):
        return [], None
    con = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True, timeout=5)
    try:
        con.row_factory = sqlite3.Row
        zeilen = [dict(r) for r in con.execute(
            "SELECT date,average,highest,lowest,volume,order_count "
            "FROM history WHERE type_id=? AND region=? ORDER BY date",
            (type_id, region))]
        meta = con.execute(
            "SELECT updated_at FROM history_meta WHERE type_id=? AND region=?",
            (type_id, region)).fetchone()
        alter_s = None
        if meta and meta["updated_at"]:
            import time
            alter_s = time.time() - meta["updated_at"]
        return zeilen, alter_s
    finally:
        con.close()


def _fmt_stunden(sek):
    if sek is None:
        return "nie gecacht"
    h = sek / 3600.0
    if h < 48:
        return f"{h:.1f} h"
    return f"{h / 24.0:.1f} Tage"


def main():
    names = [n.strip() for n in
             (os.environ.get("TS_SUCHE") or _VORGABE).split(",") if n.strip()]
    try:
        region = store.get_scan_region()
    except Exception:
        region = 10000002   # The Forge - Vorgabe, falls die DB noch leer ist
    zeilen_aus = []
    zeilen_aus.append(f"zeige_tradability Fassung {FASSUNG} - Region {region}")
    zeilen_aus.append(f"_CACHE_ANALYZE_MAX_AGE_H = {scanner._CACHE_ANALYZE_MAX_AGE_H} h "
                      f"(so alt darf der Cache sein und trotzdem als 'frisch genug' "
                      f"fuer den Gratis-Topf gelten)")
    zeilen_aus.append("")

    for name in names:
        tid = _resolve_type_id(name)
        zeilen_aus.append(f"=== {name} ===")
        if not tid:
            zeilen_aus.append("  type_id nicht gefunden (Name falsch geschrieben?)")
            zeilen_aus.append("")
            continue
        zeilen_aus.append(f"  type_id: {tid}")

        cache_rows, alter_s = _gecachte_historie_roh(tid, region)
        cache_ws = scanner.window_stats(cache_rows, 28) if cache_rows else None
        zeilen_aus.append(f"  GECACHT: Alter {_fmt_stunden(alter_s)}, "
                          f"{len(cache_rows)} Tage Historie in der DB")
        if cache_ws:
            zeilen_aus.append(
                f"    trade_score={cache_ws['trade_score']:.1f}  "
                f"active_ratio={cache_ws['active_ratio']:.2f}  "
                f"txn_day={cache_ws['txn_day']}  "
                f"day_range_pct={cache_ws['day_range_pct']:.2f}  "
                f"daily_vol={cache_ws['daily_vol']:.1f}")
        else:
            zeilen_aus.append("    keine gecachte Historie vorhanden")

        try:
            live_rows = esi.fetch_market_history(tid, region)
        except Exception as e:
            live_rows = None
            zeilen_aus.append(f"  LIVE: ESI-Abruf fehlgeschlagen ({type(e).__name__}: {e})")
        if live_rows is not None:
            live_ws = scanner.window_stats(live_rows, 28) if live_rows else None
            zeilen_aus.append(f"  LIVE (gerade eben von ESI): {len(live_rows)} Tage Historie")
            if live_ws:
                zeilen_aus.append(
                    f"    trade_score={live_ws['trade_score']:.1f}  "
                    f"active_ratio={live_ws['active_ratio']:.2f}  "
                    f"txn_day={live_ws['txn_day']}  "
                    f"day_range_pct={live_ws['day_range_pct']:.2f}  "
                    f"daily_vol={live_ws['daily_vol']:.1f}")
                if cache_ws:
                    diff = live_ws["trade_score"] - cache_ws["trade_score"]
                    zeilen_aus.append(f"    DIFFERENZ zu gecacht: {diff:+.1f} Punkte")
            else:
                zeilen_aus.append("    keine Historie von ESI zurueckbekommen")
        zeilen_aus.append("")

    os.makedirs(os.path.join(WURZEL, "berichte"), exist_ok=True)
    with open(BERICHT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(zeilen_aus))
    print("\n".join(zeilen_aus))
    print(f"\nBericht geschrieben: {BERICHT}")


if __name__ == "__main__":
    main()
