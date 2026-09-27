"""Zeigt, WIE der Gewinn auf jeder Karte in "Meine Bauplaene" entsteht
(Fassung 1, 26.09.2026).

WOZU: Nutzer-Frage 26.09.2026 - "wie kommt hier Multibuild auf 1,14 Mrd
Profit? ... am Ende soll das Buendel insgesamt so viel Profit zeigen wie
jeder Einzelplan zusammengerechnet". Die Karte zeigt nur die eine Zahl;
hier stehen ihre Bestandteile daneben, mit DERSELBEN Rechnung wie die Karte
(`_bau_saved_plan_quick_estimate`), nicht mit einer zweiten.

Je Karte: Verkauf (Summe Enden x Menge zum letzten Markt-Scan), Gebuehren
(Satz und Quelle), Baukosten (eingefroren = aus dem Einkaufs-Schnappschuss,
sonst live), Zusatzkosten, Gewinn. Beim Buendel dazu je Endprodukt der
Anteil (buendel_kosten_je_ende) und - zum Vergleich - was jede Quelle ALLEIN
gerechnet ergaebe, damit man sieht, warum die Summen nicht gleich sein
muessen.

GERATEN WIRD HIER NICHTS. Das Hauptfenster wird unsichtbar (offscreen)
aufgebaut, damit exakt der Code der Karten laeuft.

AUFRUF: werkzeuge\\zeige_karten.bat doppelklicken.
Danach liegt `berichte\\karten_bericht.txt` da - die hochladen.
Es wird NUR GELESEN: weder Datenbank noch Einstellungen werden veraendert
(das Fenster wird nicht geschlossen, sondern der Prozess beendet - sonst
schriebe closeEvent den Filterstand zurueck).
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

FASSUNG = 1
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERICHT = os.path.join(WURZEL, "berichte", "karten_bericht.txt")


def _isk(v):
    try:
        return f"{float(v):,.0f}".replace(",", "'")
    except (TypeError, ValueError):
        return "?"


def _zeit(ts):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError, OSError):
        return "?"


def main():
    zeilen = [f"karten_bericht  Fassung {FASSUNG}  "
              f"{time.strftime('%Y-%m-%d %H:%M')}", ""]
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from eve_trader.ui.main_window import MainWindow
    import eve_trader.ui.erst_einrichtung as _ee
    from eve_trader import industry, store, esi

    def _still(self, *_a, **_k):
        return None
    for _n in ("_erste_einrichtung_pruefen", "_erststart_rezepte_anbieten",
               "_erststart_ohne_charakter", "_tutorial_erstfrage",
               "_frage_verlauf_laden"):
        setattr(MainWindow, _n, _still)

    class _Ohne(_ee.ErstEinrichtung):
        def __init__(self, fenster, auto=True):
            super().__init__(fenster, auto=False)

        def exec(self):
            return 0
    _ee.ErstEinrichtung = _Ohne

    win = MainWindow()
    app.processEvents()
    plans = list(win.settings.get("bau_saved_plans") or [])
    zeilen.append(f"Gespeicherte Plaene: {len(plans)}")
    if not industry.sde_ready():
        zeilen.append("SDE nicht geladen - keine Rechnung moeglich.")
    snapshot = store.get_snapshot() or []
    pm = {s["type_id"]: s["sell_min"] for s in snapshot if s["sell_min"] > 0}
    try:
        adj = esi.adjusted_prices() or {}
    except Exception as e:
        zeilen.append(f"adjusted_prices nicht abrufbar: {type(e).__name__}: {e}")
        adj = {}
    if not adj:
        adj = dict(pm)
    zeilen.append(f"Markt-Scan: {len(pm)} Preise; Ziel-Marge "
                  f"{win.settings.get('target_margin')} %; Zusatzkosten "
                  f"{_isk(win.settings.get('bau_extra_cost', 0))} ISK")
    zeilen.append("")
    recipes = industry.recipes_cached() if industry.sde_ready() else None
    namen = store.cached_names(
        [int(t) for p in plans for t, _q in (p.get("enden") or [])]
        + [int(p.get("type_id") or 0) for p in plans if int(p.get("type_id") or 0) > 0])
    est_all = {}
    for p in plans:
        est = None
        if recipes is not None:
            try:
                est = win._bau_saved_plan_quick_estimate(p, recipes, pm, adj)
            except Exception as e:
                zeilen.append(f"!! {p.get('label')}: {type(e).__name__}: {e}")
        est_all[p.get("id")] = est
    by_id = {p.get("id"): p for p in plans}
    for p in plans:
        pid = p.get("id")
        est = est_all.get(pid)
        ist_multi = win._multi_ist_plan(p)
        frz = p.get("frozen") or {}
        zeilen.append("=" * 78)
        zeilen.append(f"{'BUENDEL' if ist_multi else 'PLAN'}  {p.get('label')}"
                      f"  (id {pid}, Menge {p.get('qty')})")
        zeilen.append(f"  eingefroren: {'ja, ' + _zeit(frz.get('ts')) if frz else 'nein'}"
                      f"   Schnappschuss: {'ja' if frz.get('plan_snapshot') else 'nein'}"
                      f"   Reservierung: {'an' if p.get('reserve') else 'aus'}"
                      f"   abgeschlossen: {'ja' if p.get('done_manual') else 'nein'}")
        if est is None:
            zeilen.append("  keine Schaetzung (kein Preis fuer ein Ende oder Fehler)")
            zeilen.append("")
            continue
        gross = float(est["sell"]) / max(1e-9, 1 - float(est["fee_pct"]) / 100.0)
        zeilen.append(f"  Verkauf brutto     {_isk(gross):>18}  (Summe Enden x Menge, letzter Scan)")
        zeilen.append(f"  - Gebuehren        {_isk(gross - float(est['sell'])):>18}"
                      f"  ({est['fee_pct']:.3f} %, Quelle: {est.get('fee_quelle')})")
        zeilen.append(f"  - Baukosten        {_isk(est['cost']):>18}"
                      f"  ({'Einkaufs-Schnappschuss' if frz.get('plan_snapshot') else 'live gerechnet'})")
        zeilen.append(f"  - Zusatzkosten     {_isk(est['extra']):>18}")
        zeilen.append(f"  = Gewinn           {_isk(est['profit']):>18}   <- steht auf der Karte")
        if ist_multi and est.get("plan"):
            try:
                je = industry.buendel_kosten_je_ende(est["plan"])
            except Exception as e:
                je = {}
                zeilen.append(f"  buendel_kosten_je_ende: {type(e).__name__}: {e}")
            zeilen.append("  je Endprodukt (Anteil am Buendel):")
            zeilen.append(f"    {'Endprodukt':34} {'Menge':>7} {'Kosten/Stk':>14} "
                          f"{'Verkauf/Stk':>14} {'Sell-Vorschlag':>15}")
            for tid, q in (p.get("enden") or []):
                k = je.get(int(tid)) or {}
                cost = k.get("je_stueck")
                vs = win._plan_sell_vorschlag(cost, p.get("sell_hub")) if cost is not None else None
                zeilen.append(f"    {str(namen.get(int(tid), tid))[:34]:34} {int(q):>7} "
                              f"{_isk(cost):>14} {_isk(pm.get(int(tid))):>14} {_isk(vs):>15}")
            summe = sum(float((je.get(int(t)) or {}).get("gesamt", 0) or 0)
                        for t, _q in (p.get("enden") or []))
            zeilen.append(f"    Summe der Anteile {_isk(summe)} gegen Baukosten {_isk(est['cost'])}")
            zeilen.append("  Quellen ALLEIN gerechnet (heutige Preise, nicht eingefroren) - nur zum Vergleich:")
            s_all = 0.0
            for qid in (p.get("quellen") or []):
                src = by_id.get(qid)
                e2 = est_all.get(qid)
                if src is None:
                    zeilen.append(f"    Quelle {qid}: nicht mehr vorhanden")
                    continue
                if e2 is None:
                    zeilen.append(f"    {src.get('label')}: keine Schaetzung")
                    continue
                s_all += float(e2["profit"])
                zeilen.append(f"    {str(src.get('label'))[:40]:40} Gewinn allein {_isk(e2['profit']):>16}"
                              f"  (Kosten {_isk(e2['cost'])}, Zusatz {_isk(e2['extra'])})")
            zeilen.append(f"    Summe allein {_isk(s_all)}  vs Buendel {_isk(est['profit'])}"
                          f"  Differenz {_isk(float(est['profit']) - s_all)}")
        zeilen.append("")
    os.makedirs(os.path.dirname(BERICHT), exist_ok=True)
    with open(BERICHT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(zeilen) + "\n")
    print("\n".join(zeilen))
    print(f"\nBericht: {BERICHT}")
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
