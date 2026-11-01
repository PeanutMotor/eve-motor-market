"""Stellt den Fall nach, der emm636 ausgeloest hat - OHNE darauf zu warten.

NUTZER 23.10.2026: "kannst du das bitte simulieren und nachstellen so eine
situation? damit ich nicht warten muss dass so ein Fall vorkommt?"

WAS HIER PASSIERT: der Bericht nimmt DEINE echten eingefrorenen Plaene
(Rezeptbaum, Mengen, Einfrier-Bestand aus settings.json) und laesst dann
kuenstlich Material verschwinden - genau das, was im Spiel passiert, wenn
ein anderer Plan zugreift, etwas verkauft oder ein Job falsch geklickt
wird. Danach rechnet er DIESELBE Funktion zweimal:

  ALT  `fehlbedarf_vorschau(..., live = max(Einfrier-Bestand, live))`
       So lief es bis emm636: der Melder bekam den gemergten Stand - also
       genau die Zahl, die ein verschwundenes Material versteckt.

  NEU  `fehlbedarf_vorschau(..., live = echter Stand)`
       So laeuft es seit emm636 (`_bd_echter_bestand`).

Beide Male dieselbe Funktion, dieselben Plandaten - nur der Bestand, den
der Melder sieht, ist ein anderer. Die Differenz ist die Menge, die der
alte Weg verschwiegen haette und die im Spiel gefehlt haette.

RECHNET MIT DEN FUNKTIONEN DES WERKZEUGS SELBST (`fehlbedarf_vorschau`,
`restbedarf_map`) - keine nachgebaute Zweitrechnung. Liest nur, aendert
nichts, braucht KEIN ESI (der Einfrier-Bestand steht in settings.json).

AUFRUF (ohne Angaben: 30 % Verlust auf allen Materialien):
    python werkzeuge\\simuliere_bestandsverlust.py
    python werkzeuge\\simuliere_bestandsverlust.py --verlust 50
    python werkzeuge\\simuliere_bestandsverlust.py --item Ceramic --weg 4494
"""
import argparse
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import config, store   # noqa: E402
from eve_trader.ui.mw_helpers import (fehlbedarf_vorschau,   # noqa: E402
                                      restbedarf_map)

FASSUNG = 1
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERICHT = os.path.join(WURZEL, "berichte", "verlust_simulation_bericht.txt")


def _z(n):
    try:
        return f"{int(n):,}".replace(",", "'")
    except (TypeError, ValueError):
        return "?"


def _unpack(v):
    def _key(k):
        if isinstance(k, str):
            _k = k[1:] if k.startswith("-") else k
            if _k.isdigit():
                return int(k)
        return k
    if isinstance(v, dict):
        return {_key(k): _unpack(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_unpack(x) for x in v]
    return v


def _settings_rohe():
    import json
    try:
        with open(config.settings_path(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return config.load_settings()


def _out_qty_map(tids):
    """{type_id: Stueck je Run} aus der SDE - fuer die Gutschrift der
    eigenen, noch offenen Produktion. Ohne sie zaehlte ein Plan, der sein
    Material selbst herstellt, es faelschlich als fehlend."""
    out = {}
    for pfad in (os.path.join(WURZEL, "sde_kompakt.db"),
                 os.path.join(config.app_data_dir(), "industry.db")):
        if not os.path.exists(pfad):
            continue
        try:
            con = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
            for t in tids:
                if t in out:
                    continue
                r = con.execute(
                    "SELECT quantity FROM products WHERE product_id=? "
                    "LIMIT 1", (int(t),)).fetchone()
                if r and int(r[0] or 0) > 0:
                    out[int(t)] = int(r[0])
            con.close()
        except Exception:
            continue
    return out


def _namen(tids):
    out = {}
    try:
        out.update(store.cached_names(sorted(tids)) or {})
    except Exception:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verlust", type=float, default=30.0,
                    help="Prozent des Bestands, der verschwindet (Vorgabe 30)")
    ap.add_argument("--item", default=None,
                    help="nur dieses Material (Namensteil)")
    ap.add_argument("--weg", type=int, default=None,
                    help="feste Stueckzahl statt Prozent")
    args = ap.parse_args()

    aus = []
    p = aus.append
    p("=" * 78)
    p(f"VERLUST-SIMULATION - was der Melder vorher verschwiegen haette "
      f"(Fassung {FASSUNG})")
    p(f"Erstellt: {time.strftime('%Y-%m-%d %H:%M:%S')} (Ortszeit)")
    p("=" * 78)
    p("")
    p("  Echte Plaene, echte Mengen, echter Einfrier-Bestand aus deiner")
    p("  settings.json. KUENSTLICH ist nur der Verlust - damit du den Fall")
    p("  nicht abwarten musst.")
    if args.weg is not None:
        p(f"  Angenommener Verlust: {_z(args.weg)} Stueck je betroffenem Material")
    else:
        p(f"  Angenommener Verlust: {args.verlust:g} % des Bestands")
    if args.item:
        p(f"  Nur Materialien mit „{args.item}“ im Namen")
    p("")

    settings = _settings_rohe()
    plaene = [pl for pl in (settings.get("bau_saved_plans") or [])
              if isinstance(pl, dict) and not pl.get("done_manual")
              and ((pl.get("frozen") or {}).get("plan_snapshot"))]
    if not plaene:
        p("  Keine aktiven, eingefrorenen Plaene gefunden - nichts zu zeigen.")
        _schreiben(aus)
        return

    gesamt_alt = gesamt_neu = 0
    gesamt_posten = 0
    for pl in plaene:
        lab = str(pl.get("label") or pl.get("item_name") or "?")
        snap = _unpack((pl.get("frozen") or {}).get("plan_snapshot") or {})
        frozen = {int(k): int(v or 0)
                  for k, v in (_unpack((pl.get("frozen") or {}).get("stock")
                                       or {})).items()}
        runs = {int(k): int(v or 0)
                for k, v in (snap.get("build_runs") or {}).items()}
        mats = snap.get("build_mats") or {}
        if not runs or not mats:
            continue
        # NOCH OFFENER BEDARF - dieselbe Funktion wie das Werkzeug.
        # `delivered` bewusst leer: die Simulation fragt "was braucht
        # dieser Plan noch, wenn ich jetzt alle offenen Runs starte".
        _rem, need = restbedarf_map(runs, mats, {})
        oq = _out_qty_map(set(need) | set(runs))
        namen = _namen(set(need))

        # DER VERLUST: aus dem Einfrier-Bestand verschwindet etwas.
        live = dict(frozen)
        betroffen = []
        for t in sorted(need, key=lambda x: -need[x]):
            nm = str(namen.get(t) or t)
            # Name ODER type_id - der Namens-Cache kennt nicht jedes Item,
            # und mit der Nummer trifft man auch dann genau eines.
            if args.item and args.item.lower() not in nm.lower() \
                    and str(args.item).strip() != str(t):
                continue
            da = int(frozen.get(t, 0) or 0)
            if da <= 0:
                continue
            weg = (min(da, int(args.weg)) if args.weg is not None
                   else int(da * args.verlust / 100.0))
            if weg <= 0:
                continue
            live[t] = da - weg
            betroffen.append((t, da, weg))
        if not betroffen:
            continue

        # ZWEIMAL DIESELBE FUNKTION - nur der Bestand ist ein anderer.
        _alt_stock = {t: max(int(frozen.get(t, 0) or 0), int(live.get(t, 0) or 0))
                      for t in set(frozen) | set(live)}
        alt = {t: f for t, f, *_r in
               fehlbedarf_vorschau(runs, mats, oq, {}, _alt_stock)}
        neu = {t: f for t, f, *_r in
               fehlbedarf_vorschau(runs, mats, oq, {}, live)}

        zeilen = []
        for t, da, weg in betroffen:
            _a, _n = int(alt.get(t, 0)), int(neu.get(t, 0))
            if _n == _a:
                continue
            zeilen.append((_n - _a, t, need.get(t, 0), da, weg, _a, _n))
        if not zeilen:
            continue
        zeilen.sort(reverse=True)
        p("-" * 78)
        p(f"PLAN  {lab}")
        p("-" * 78)
        p(f"  {'MATERIAL':28} {'BEDARF':>11} {'VORHER':>10} {'WEG':>10} "
          f"{'ALT SAGT':>11} {'NEU SAGT':>11} {'VERSCHWIEGEN':>13}")
        for d, t, bed, da, weg, _a, _n in zeilen[:25]:
            p(f"  {str(namen.get(t) or t)[:28]:28} {_z(bed):>11} {_z(da):>10} "
              f"{_z(weg):>10} {_z(_a):>11} {_z(_n):>11} {_z(d):>13}")
        if len(zeilen) > 25:
            p(f"  ... und {len(zeilen) - 25} weitere Posten")
        _sa = sum(x[5] for x in zeilen)
        _sn = sum(x[6] for x in zeilen)
        p("")
        p(f"  SUMME dieses Plans: ALT haette {_z(_sa)} Stueck verlangt, "
          f"NEU verlangt {_z(_sn)}.")
        p(f"  -> {_z(_sn - _sa)} Stueck haette der alte Weg VERSCHWIEGEN - "
          f"genau das, was")
        p(f"     dir danach im Spiel gefehlt haette.")
        p("")
        gesamt_alt += _sa
        gesamt_neu += _sn
        gesamt_posten += len(zeilen)

    p("=" * 78)
    p("ERGEBNIS")
    p("=" * 78)
    if not gesamt_posten:
        p("  Kein Posten reagiert auf diesen Verlust - probiere einen")
        p("  groesseren Wert, z.B. --verlust 60.")
    else:
        p(f"  {gesamt_posten} Posten ueber alle Plaene.")
        p(f"  ALT haette zusammen {_z(gesamt_alt)} Stueck zum Kauf verlangt.")
        p(f"  NEU verlangt {_z(gesamt_neu)} Stueck.")
        p(f"  VERSCHWIEGEN: {_z(gesamt_neu - gesamt_alt)} Stueck.")
        p("")
        p("  Genau diese Menge haettest du NICHT gekauft - und sie haette")
        p("  dir beim Starten der offenen Runs gefehlt.")
    _schreiben(aus)


def _schreiben(aus):
    os.makedirs(os.path.dirname(BERICHT), exist_ok=True)
    with open(BERICHT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(aus) + "\n")
    print("\n".join(aus))
    print("")
    print(f"Geschrieben: {BERICHT}")


if __name__ == "__main__":
    main()
