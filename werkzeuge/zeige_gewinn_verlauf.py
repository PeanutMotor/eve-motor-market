# -*- coding: utf-8 -*-
"""Diagnose fuer den Gewinne-Tab (emm407, Nutzer 04.10.2026: "die
Zeitperiode vom Profit tracken funktioniert nicht, es geht nur bis 90
Tage" / "ich verliere immer wieder mal ein bisschen Profit").

NUR LESEND. Schreibt berichte/gewinn_verlauf_bericht.txt:
  1) je Charakter: aelteste/neueste Transaktion, Anzahl Kaeufe/Verkaeufe
  2) je Monat: Transaktionen, Verkaufsumsatz gesamt, davon im Gewinne-Tab
     ERFASST (realized_trades) und NICHT ERFASST (Verkaeufe ohne Kauf-Lot
     in der Datenbank - genau die "verschwinden" aus der Anzeige)
  3) dieselbe Rechnung wie der Tab (Steuer/Broker/Handels-Paar aus den
     Einstellungen), Summen fuer 90/180/365/Alle Tage

Hintergrund: ESI behaelt Wallet-Transaktionen nur ~30 Tage; Eve MoMa
sammelt sie dauerhaft in der eigenen Datenbank und loescht nie von selbst.
"Alles" kann also nur zeigen, was je gesammelt wurde.
"""
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_WURZEL)
sys.path.insert(0, _WURZEL)

from eve_trader import config, market, store  # noqa: E402

FASSUNG = 1


def _monat(datum):
    return str(datum)[:7]


def main():
    s = config.load_settings()
    tax = float(s.get("sales_tax_pct") or 0) / 100.0
    broker = float(s.get("broker_fee_pct") or 0) / 100.0
    paar = set()
    for x in (s.get("handels_charaktere") or []):
        try:
            paar.add(int(x))
        except (TypeError, ValueError):
            pass

    txs = store.get_transactions(None)
    z = [f"Gewinn-Verlauf-Diagnose - Fassung {FASSUNG} - "
         f"{datetime.now():%d.%m.%Y %H:%M}",
         f"Steuer {tax * 100:.3f} % / Broker {broker * 100:.3f} % / "
         f"Handels-Paar: {sorted(paar) if paar else 'keines (alle einzeln)'}",
         f"Transaktionen in der Datenbank: {len(txs)}", ""]

    # 1) je Charakter
    z.append("== 1) Je Charakter =========================================")
    je_char = defaultdict(list)
    for t in txs:
        je_char[t.get("character_id")].append(t)
    namen = {}
    try:
        namen = {int(c["character_id"]): c.get("character_name") or ""
                 for c in store.list_characters()}
    except Exception:
        pass
    for cid, liste in sorted(je_char.items(), key=lambda kv: str(kv[0])):
        daten = sorted(t["date"] for t in liste)
        k = sum(1 for t in liste if t["is_buy"])
        v = len(liste) - k
        z.append(f"  {namen.get(int(cid)) if cid is not None else '?'} "
                 f"(#{cid}): {len(liste)} Transaktionen "
                 f"({k} Kaeufe / {v} Verkaeufe), "
                 f"aelteste {daten[0][:10]}, neueste {daten[-1][:10]}")
    z.append("")

    # 2) je Monat: Umsatz gesamt vs. im Gewinne-Tab erfasst
    events = market.realized_trades(txs, tax, broker, paar=paar or None)
    umsatz_monat = defaultdict(float)
    verkauf_monat = defaultdict(int)
    for t in txs:
        if not t["is_buy"]:
            umsatz_monat[_monat(t["date"])] += (
                float(t["unit_price"]) * int(t["quantity"]))
            verkauf_monat[_monat(t["date"])] += 1
    erfasst_monat = defaultdict(float)
    netto_monat = defaultdict(float)
    for e in events:
        erfasst_monat[_monat(e["date"])] += float(e["revenue"])
        netto_monat[_monat(e["date"])] += float(e["net"])
    z.append("== 2) Je Monat: Verkaufsumsatz gesamt / im Gewinne-Tab ====")
    z.append("   Monat    Verkaeufe  Umsatz gesamt      erfasst            "
             "NICHT erfasst      Netto-Gewinn")
    for m in sorted(set(umsatz_monat) | set(erfasst_monat)):
        ges = umsatz_monat.get(m, 0.0)
        erf = erfasst_monat.get(m, 0.0)
        z.append(f"   {m}   {verkauf_monat.get(m, 0):8d}  "
                 f"{ges:16,.0f}  {erf:16,.0f}  {ges - erf:16,.0f}  "
                 f"{netto_monat.get(m, 0.0):16,.0f}".replace(",", "'"))
    z.append("")
    z.append("   'NICHT erfasst' = Verkaeufe, deren Kauf nicht (mehr) in der")
    z.append("   Datenbank steht - sie fallen aus dem Gewinne-Tab heraus,")
    z.append("   egal welche Periode gewaehlt ist.")
    z.append("")

    # 3) Summen wie der Tab
    z.append("== 3) Summen wie der Gewinne-Tab ===========================")
    jetzt = datetime.now(timezone.utc)
    for tage, name in ((90, "90 Tage"), (180, "180 Tage"),
                       (365, "1 Jahr"), (0, "Alles")):
        if tage:
            grenze = (jetzt - timedelta(days=tage)).strftime("%Y-%m-%d")
            ev = [e for e in events if e["date"] >= grenze]
        else:
            ev = events
        z.append(f"   {name:>8}: {len(ev):6d} Ereignisse, Netto "
                 f"{sum(e['net'] for e in ev):16,.0f} ISK".replace(",", "'"))

    os.makedirs("berichte", exist_ok=True)
    pfad = os.path.join("berichte", "gewinn_verlauf_bericht.txt")
    with open(pfad, "w", encoding="utf-8") as f:
        f.write("\n".join(z) + "\n")
    print("\n".join(z))
    print(f"\nBericht: {pfad}")


if __name__ == "__main__":
    main()
