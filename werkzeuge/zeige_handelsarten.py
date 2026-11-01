# -*- coding: utf-8 -*-
"""Wie viele Daytrades und wie viele Swingtrades? (emm568, Nutzer
16.10.2026: "kann man herausfinden wieviel Daytrades und wieviel
Swingtrades ich gemacht habe in Jita mit Lezaar als Charakter?")

NUR LESEND. Schreibt berichte/handelsarten_bericht.txt.

EHRLICH VORAB: MoMa speichert NICHT, aus welchem Reiter ein Handel kam -
in der Datenbank stehen nur Kaeufe und Verkaeufe. Die Art wird deshalb aus
der HALTEDAUER abgeleitet: Kauf und Verkauf werden wie im Gewinne-Tab nach
FIFO zusammengefuehrt (je Charakter, je Item), und fuer jeden Verkauf zaehlt
die mengengewichtete Zeit seit dem Kauf seiner Lots.
  Daytrade  = gehalten unter 24 Stunden
  Swingtrade = gehalten 24 Stunden oder laenger
Dazu eine feinere Verteilung, damit man die Grenze selbst beurteilen kann.

Gezaehlt wird EIN VERKAUF (eine Wallet-Transaktion) als ein Handel. Nur
Jita 4-4 (Station 60003760), Kauf UND Verkauf dort. Verkaeufe, deren Kauf
nicht in der Datenbank steht (aelter als die Sammlung, anderer Charakter,
anderer Ort), stehen getrennt da - sie lassen sich nicht einordnen.
"""
import os
import sys
from collections import defaultdict, deque
from datetime import datetime

_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_WURZEL)
sys.path.insert(0, _WURZEL)

from eve_trader import config, store  # noqa: E402

FASSUNG = 1
CHAR_NAME = "Lezaar"
JITA_44 = 60003760
GRENZEN = ((1, "unter 1 h"), (6, "1 - 6 h"), (24, "6 - 24 h"),
           (72, "1 - 3 Tage"), (168, "3 - 7 Tage"), (None, "ueber 7 Tage"))


def _zeit(s):
    s = str(s).replace("Z", "")
    for f in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], f)
        except ValueError:
            continue
    return None


def _isk(v):
    return f"{v:,.0f}".replace(",", "'")


def auswerten(txs, tax=0.0, broker=0.0):
    """FIFO mit Kaufzeit je Lot. Rueckgabe: (handel, ohne_kauf) -
    handel = [{stunden, menge, umsatz, roh, netto}], ohne_kauf = Anzahl
    Verkaeufe ohne passenden Kauf."""
    lots = defaultdict(deque)
    handel, ohne = [], 0
    for t in sorted(txs, key=lambda x: (x["date"], 0 if x["is_buy"] else 1)):
        z = _zeit(t["date"])
        if z is None:
            continue
        if t["is_buy"]:
            lots[t["type_id"]].append([int(t["quantity"]), float(t["unit_price"]), z])
            continue
        rest = int(t["quantity"])
        menge = kosten = sek = 0.0
        dq = lots[t["type_id"]]
        while rest > 0 and dq:
            lot = dq[0]
            n = min(rest, lot[0])
            menge += n
            kosten += n * lot[1]
            sek += n * (z - lot[2]).total_seconds()
            lot[0] -= n
            rest -= n
            if lot[0] == 0:
                dq.popleft()
        if menge <= 0:
            ohne += 1
            continue
        vk = float(t["unit_price"])
        handel.append({"stunden": sek / menge / 3600.0, "menge": menge,
                       "umsatz": vk * menge, "roh": vk * menge - kosten,
                       "netto": vk * menge * (1 - tax - broker) - kosten})
    return handel, ohne


def main():
    s = config.load_settings()
    cid = None
    for c in store.list_characters():
        if (c.get("character_name") or "").strip().lower() == CHAR_NAME.lower():
            cid = int(c["character_id"])
    z = [f"Handelsarten - Fassung {FASSUNG} - {datetime.now():%d.%m.%Y %H:%M}",
         f"Charakter: {CHAR_NAME} (#{cid})   Ort: Jita 4-4 (#{JITA_44})", ""]
    if cid is None:
        z.append(f"Charakter '{CHAR_NAME}' ist in MoMa nicht verlinkt.")
    else:
        # Gebuehren: die des Charakters, sonst die globalen (wie der Bauplan).
        _cf = (s.get("char_fees") or {}).get(str(cid)) or {}
        try:
            tax = float(_cf.get("tax", s.get("sales_tax_pct", 0))) / 100.0
            broker = float(_cf.get("broker", s.get("broker_fee_pct", 0))) / 100.0
        except (TypeError, ValueError):
            tax = broker = 0.0
        txs = [t for t in store.get_transactions(cid)
               if int(t.get("location_id") or 0) == JITA_44]
        daten = sorted(t["date"] for t in txs)
        handel, ohne = auswerten(txs, tax, broker)
        z.append(f"Transaktionen in Jita: {len(txs)} "
                 f"({sum(1 for t in txs if t['is_buy'])} Kaeufe / "
                 f"{sum(1 for t in txs if not t['is_buy'])} Verkaeufe)")
        if daten:
            z.append(f"Zeitraum der gesammelten Daten: {daten[0][:10]} bis "
                     f"{daten[-1][:10]}")
        z.append(f"Gebuehren fuer 'Netto': Sales Tax {tax * 100:.2f} % + "
                 f"Broker {broker * 100:.2f} % (nur auf den Verkauf; die "
                 f"Broker Fee der KAUF-Order ist nicht abgezogen)")
        z.append("")
        for titel, auswahl in (
                ("DAYTRADES (unter 24 h gehalten)",
                 [h for h in handel if h["stunden"] < 24]),
                ("SWINGTRADES (24 h oder laenger)",
                 [h for h in handel if h["stunden"] >= 24])):
            z.append(f"== {titel}")
            z.append(f"   Anzahl Verkaeufe: {len(auswahl)}")
            z.append(f"   Stueck:           {_isk(sum(h['menge'] for h in auswahl))}")
            z.append(f"   Umsatz:           {_isk(sum(h['umsatz'] for h in auswahl))} ISK")
            z.append(f"   Gewinn vor Geb.:  {_isk(sum(h['roh'] for h in auswahl))} ISK")
            z.append(f"   Gewinn netto:     {_isk(sum(h['netto'] for h in auswahl))} ISK")
            z.append("")
        z.append("== VERTEILUNG NACH HALTEDAUER")
        unten = 0.0
        for oben, name in GRENZEN:
            n = [h for h in handel if h["stunden"] >= unten
                 and (oben is None or h["stunden"] < oben)]
            z.append(f"   {name:>14}: {len(n):6d} Verkaeufe, netto "
                     f"{_isk(sum(h['netto'] for h in n)):>16} ISK")
            unten = oben or 0.0
        z.append("")
        z.append(f"Verkaeufe OHNE passenden Kauf in Jita (nicht einzuordnen): {ohne}")
    os.makedirs("berichte", exist_ok=True)
    pfad = os.path.join("berichte", "handelsarten_bericht.txt")
    with open(pfad, "w", encoding="utf-8") as f:
        f.write("\n".join(z) + "\n")
    print("\n".join(z))
    print(f"\nBericht: {pfad}")


if __name__ == "__main__":
    main()
