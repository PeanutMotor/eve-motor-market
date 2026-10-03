"""Buy/hold/margin- und FIFO-Berechnungen des Portfolios.

Preise kommen AUSSCHLIESSLICH aus dem ESI-Markt-Snapshot (store.get_snapshot)
- die frühere Fuzzwork-Aggregator-Abfrage (Drittanbieter, verstieß gegen die
Grundregel "nur ESI/SDE" und war die einzige zweite Preisquelle im Tool) wurde
entfernt."""
from dataclasses import dataclass


@dataclass
class Holding:
    type_id: int
    name: str
    quantity: int
    avg_buy: float
    oldest_date: str = ""
    jita_sell_min: float = 0.0
    jita_buy_max: float = 0.0
    net_unit: float = 0.0
    margin_pct: float = 0.0
    profit_total: float = 0.0
    flag: bool = False


def aggregate_holdings(transactions) -> dict:
    """FIFO lot tracking PER CHARACTER (each character's sells consume only that
    character's own buy lots), then merged per type_id. So combining several
    characters can't mismatch one character's sells against another's buys – the
    combined view is exactly the sum of the individual characters.
    Returns {type_id: {"quantity", "avg_buy", "oldest"}} for qty > 0."""
    from collections import defaultdict, deque
    lots = defaultdict(deque)  # (character_id, type_id) -> deque[[qty, price, date]]
    # buys before sells on the same day so FIFO consumes correctly
    ordered = sorted(transactions, key=lambda x: (x["date"], 0 if x["is_buy"] else 1))
    for t in ordered:
        key = (t.get("character_id"), t["type_id"])
        if t["is_buy"]:
            lots[key].append([t["quantity"], t["unit_price"], t["date"]])
        else:
            qty = t["quantity"]
            dq = lots[key]
            while qty > 0 and dq:
                lot = dq[0]
                take = min(qty, lot[0])
                lot[0] -= take
                qty -= take
                if lot[0] == 0:
                    dq.popleft()
            # leftover sells (items owned before tracking began) are ignored
    holdings = {}
    for (_char, tid), dq in lots.items():
        remaining = [l for l in dq if l[0] > 0]
        if not remaining:
            continue
        qty = sum(l[0] for l in remaining)
        val = sum(l[0] * l[1] for l in remaining)
        oldest = min(l[2] for l in remaining)[:10]
        if tid in holdings:                     # anderen Charakter mit gleichem Item mergen
            h = holdings[tid]
            newq = h["quantity"] + qty
            h["avg_buy"] = (h["avg_buy"] * h["quantity"] + val) / newq
            h["quantity"] = newq
            h["oldest"] = min(h["oldest"], oldest)
        else:
            holdings[tid] = {"quantity": qty, "avg_buy": val / qty, "oldest": oldest}
    return holdings


def ist_container(gruppenname) -> bool:
    """CONTAINER BEKOMMEN NIE FRACHT (Nutzer 29.09.2026: "das sind Container,
    die ausgepackt sind und etwas drin ist ... koennen immer weg aus der
    Rechnung"). Die SDE kennt fuer sie nur das Volumen AUSGEPACKT
    (Giant Freight Container 120'000 m3) - daraus wurden +16'699 % Fracht.
    Erkannt am Gruppennamen ("Cargo Container", "Secure Cargo Container",
    "Audit Log Secure Container", "Freight Container"), nicht an Type-IDs;
    "Container Blueprints" endet nicht auf "Container" und bleibt."""
    # de_scan4: aus - SDE-Gruppenname (interner Schluessel), keine Anzeige
    return str(gruppenname or "").strip().endswith("Container")
    # de_scan4: an


def fracht_je_item(transactions, hub_orte, satz, volumen, ohne=()) -> dict:
    """FRACHT JE ITEM aus den echten Kaeufen (Nutzer 29.09.2026: "ich muss
    die Frachtkosten VOR dem Verkauf auf die Marge obendrauf schlagen
    koennen" - und die Menge darf NICHT aus dem Warenkorb kommen, "oft fuegt
    man die Anzahl erst mit Suggested quantity hinzu oder findet eine freie
    Anzahl direkt ingame").

    Dieselbe FIFO-Rechnung wie `aggregate_holdings` (je Charakter, Kaeufe
    vor Verkaeufen am selben Tag), nur tragen die Lots ihren KAUFORT mit.
    Fracht bekommen genau die noch liegenden Stueck, die NICHT an einem Ort
    aus `hub_orte` gekauft wurden: Stueck x m3 x ISK/m3. Unbekannter Ort
    (alte Daten, 0/None) -> keine Fracht; unbekanntes Volumen -> keine.

    Rueckgabe {type_id: {"menge", "menge_fracht", "fracht", "je_stueck",
    "m3"}} nur fuer Items mit Fracht > 0. `je_stueck` ist ueber ALLE noch
    liegenden Stueck gemittelt - genau wie `avg_buy` - damit beide Zahlen
    zusammen die Kostenbasis desselben Stapels sind.
    """
    from collections import defaultdict, deque
    try:
        satz = float(satz or 0)
    except (TypeError, ValueError):
        satz = 0.0
    if satz <= 0:
        return {}
    hub = {int(o) for o in (hub_orte or ()) if o}
    ohne = {int(x) for x in (ohne or ())}
    lots = defaultdict(deque)       # (char, tid) -> [[menge, ort], ...]
    ordered = sorted(transactions, key=lambda x: (x["date"], 0 if x["is_buy"] else 1))
    for t in ordered:
        key = (t.get("character_id"), t["type_id"])
        if t["is_buy"]:
            lots[key].append([t["quantity"], t.get("location_id") or 0])
        else:
            qty = t["quantity"]
            dq = lots[key]
            while qty > 0 and dq:
                lot = dq[0]
                take = min(qty, lot[0])
                lot[0] -= take
                qty -= take
                if lot[0] == 0:
                    dq.popleft()
    aus = {}
    for (_char, tid), dq in lots.items():
        for menge, ort in dq:
            if menge <= 0:
                continue
            e = aus.setdefault(tid, {"menge": 0, "menge_fracht": 0})
            e["menge"] += menge
            if ort and int(ort) not in hub:
                e["menge_fracht"] += menge
    ergebnis = {}
    for tid, e in aus.items():
        m3 = float((volumen or {}).get(tid) or 0)
        if tid in ohne or m3 <= 0 or e["menge_fracht"] <= 0 or e["menge"] <= 0:
            continue
        fracht = e["menge_fracht"] * m3 * satz
        ergebnis[tid] = {"menge": e["menge"], "menge_fracht": e["menge_fracht"],
                         "fracht": fracht, "je_stueck": fracht / e["menge"],
                         "m3": m3}
    return ergebnis


def realized_trades(transactions, tax: float = 0.0, broker: float = 0.0,
                    paar=None, fracht_satz=0.0, volumen=None, ohne=()) -> list:
    """Match each sell against FIFO buy lots to get realised profit per sale.
    tax/broker are fractions (e.g. 0.045). Returns events sorted by date.
    Sells whose buy lot isn't in the data are matched only for the known part.

    `paar` = Menge von character_ids, die als EIN Haendler gelten.

    WARUM ES DAS GIBT (Sitzung 16). Der Nutzer kauft mit einem Charakter in
    Jita und verkauft mit einem anderen in 4-HWWF. FIFO je Charakter findet
    fuer diesen Verkauf KEIN Kauf-Lot - der Handel verschwindet spurlos aus
    dem Profits-Tab. In seinen echten Daten gemessen: 26,4 Mrd ISK Umsatz,
    der genau so wegfiel.

    DIE TRENNUNG JE CHARAKTER BLEIBT DIE VORGABE und ist richtig: ohne sie
    matchen Verkaeufe von Char A gegen Kaeufe von Char B, und bei "Alle
    Charaktere" blaeht sich der Umsatz auf (Entscheidung aus Sitzung 9).
    Nur wer ein Handels-PAAR ausdruecklich eingetragen hat, sagt damit: diese
    beiden sind ein Betrieb. Dann - und nur dann - teilen sie sich die Lots.

    FRACHT (Nutzer 30.09.2026: "Profits-Tab muss Fracht mitrechnen und mit
    einem Symbol anzeigen"): mit `fracht_satz` > 0 traegt jedes Lot seinen
    Kaufort; ein verkauftes Stueck, das an einem ANDEREN Ort gekauft wurde
    als dort, wo es verkauft wurde, kostet m3 x Satz. Unbekannter Ort (0),
    unbekanntes Volumen oder Rechtsklick "keine Fracht" -> keine. Das
    Ereignis traegt "fracht", `net` ist um sie gemindert. Der Satz ist der
    HEUTIGE (welcher damals galt, weiss niemand).
    """
    try:
        fracht_satz = max(0.0, float(fracht_satz or 0))
    except (TypeError, ValueError):
        fracht_satz = 0.0
    ohne = set(int(x) for x in (ohne or ()))
    from collections import defaultdict, deque
    paar = {int(c) for c in (paar or []) if str(c).lstrip("-").isdigit()}
    lots = defaultdict(deque)
    events = []
    ordered = sorted(transactions, key=lambda x: (x["date"], 0 if x["is_buy"] else 1))
    for t in ordered:
        tid = t["type_id"]
        _cid = t.get("character_id")
        # Alle Charaktere des Paares teilen sich EINEN Schluessel.
        key = (("paar" if (_cid is not None and int(_cid) in paar) else _cid),
               tid)                            # FIFO je Charakter getrennt halten,
        if t["is_buy"]:                         # sonst matchen Verkäufe von Char A gegen
            lots[key].append([t["quantity"], t["unit_price"],    # Käufe von Char B →
                              int(t.get("location_id") or 0)])
        else:                                   # falscher, aufgeblähter Umsatz bei „Alle“.
            qty = t["quantity"]
            sell = t["unit_price"]
            dq = lots[key]
            matched_qty = 0
            matched_cost = 0.0
            fracht = 0.0
            _vort = int(t.get("location_id") or 0)
            _m3 = (float((volumen or {}).get(tid) or 0)
                   if (fracht_satz > 0 and tid not in ohne) else 0.0)
            while qty > 0 and dq:
                lot = dq[0]
                take = min(qty, lot[0])
                matched_qty += take
                matched_cost += take * lot[1]
                if _m3 > 0 and _vort and lot[2] and lot[2] != _vort:
                    fracht += take * _m3 * fracht_satz
                lot[0] -= take
                qty -= take
                if lot[0] == 0:
                    dq.popleft()
            if matched_qty <= 0:
                continue
            buy_avg = matched_cost / matched_qty
            gross = (sell - buy_avg) * matched_qty
            net = (sell * (1 - tax - broker) - buy_avg) * matched_qty - fracht
            events.append({
                "date": t["date"][:10],
                "type_id": tid,
                "qty": matched_qty,
                "sell": sell,
                "buy": buy_avg,
                "gross": gross,
                "net": net,
                "revenue": sell * matched_qty,
                "fracht": fracht,
            })
    return events


def realized_summary(events, days: int = 0):
    """Aggregate realised events over the last `days` (0 = all). Returns
    (totals dict, per_type list sorted by net profit)."""
    import datetime as _dt
    if days:
        cutoff = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
        events = [e for e in events if e["date"] >= cutoff]
    by_type = {}
    tot_net = tot_gross = tot_rev = tot_fr = 0.0
    tot_qty = 0
    for e in events:
        tot_net += e["net"]
        tot_gross += e["gross"]
        tot_rev += e["revenue"]
        tot_fr += float(e.get("fracht") or 0.0)
        tot_qty += e["qty"]
        a = by_type.setdefault(e["type_id"], {"type_id": e["type_id"], "qty": 0,
                                              "net": 0.0, "revenue": 0.0, "cost": 0.0,
                                              "fracht": 0.0})
        a["fracht"] += float(e.get("fracht") or 0.0)
        a["qty"] += e["qty"]
        a["net"] += e["net"]
        a["revenue"] += e["revenue"]
        a["cost"] += e["buy"] * e["qty"]
    rows = sorted(by_type.values(), key=lambda x: x["net"], reverse=True)
    for r in rows:
        # Marge auf Einkauf + Fracht (dieselbe Basis wie in der Verkaufsliste)
        _b = r["cost"] + r["fracht"]
        r["margin"] = (r["net"] / _b * 100) if _b else 0.0
    totals = {"net": tot_net, "gross": tot_gross, "revenue": tot_rev,
              "qty": tot_qty, "trades": len(events), "fracht": tot_fr}
    return totals, rows


def _fill(ladder, qty, buy=True):
    """Walk an order ladder to fill `qty`. ladder is [(price, volume), ...]
    ascending for buying, descending for selling."""
    remaining = qty
    total = 0.0
    marginal = 0.0
    for price, vol in ladder:
        if remaining <= 0:
            break
        take = min(remaining, vol)
        total += take * price
        marginal = price
        remaining -= take
    filled = qty - remaining
    key = "cost" if buy else "revenue"
    return {key: total, "avg": (total / filled if filled else 0.0),
            "marginal": marginal, "filled": filled, "short": max(0, remaining)}


def worthwhile_fill(sell_ladder, cutoff):
    """Walk ascending sell orders and take every order whose price is still at
    or below `cutoff` (the point where the trade stops being worth it).
    Returns the cumulative worthwhile quantity, its average price and the last
    (highest still-worthwhile) price."""
    qty = 0
    cost = 0.0
    last = 0.0
    if not cutoff or cutoff <= 0:
        # Ohne gültigen Break-even-Preis wäre JEDE Order "lohnend" und die
        # ganze Leiter würde empfohlen - dann lieber ehrlich: nichts.
        return {"qty": 0, "avg": 0.0, "last": 0.0, "cost": 0.0}
    for price, vol in sell_ladder:
        if cutoff and price > cutoff:
            break
        qty += vol
        cost += price * vol
        last = price
    return {"qty": qty, "avg": (cost / qty if qty else 0.0),
            "last": last, "cost": cost}


def fill_buy(sell_ladder, qty):
    """Realistic cost to buy qty by walking ascending sell orders."""
    return _fill(sell_ladder, qty, buy=True)


def holdings_from_assets(assets: dict, transactions) -> dict:
    """Real inventory (from the assets endpoint) priced with the FIFO cost basis
    derived from transactions. assets = {type_id: quantity}.
    Items you hold but never bought on the market show avg_buy = 0 (unknown)."""
    lots = aggregate_holdings(transactions)
    holdings = {}
    for tid, qty in assets.items():
        if qty <= 0:
            continue
        lot = lots.get(tid)
        holdings[tid] = {
            "quantity": qty,
            "avg_buy": lot["avg_buy"] if lot else 0.0,
            "oldest": lot["oldest"] if lot else "",
        }
    return holdings


def evaluate(holdings: dict, names: dict, prices: dict, settings: dict) -> list:
    tax = settings["sales_tax_pct"] / 100.0
    broker = settings["broker_fee_pct"] / 100.0
    target = settings["target_margin"]
    mode = settings["sell_mode"]
    rows = []
    for tid, h in holdings.items():
        p = prices.get(tid, {})
        sell_min = p.get("sell_min", 0.0)
        buy_max = p.get("buy_max", 0.0)
        if mode == "instant":
            market = buy_max
            net = market * (1 - tax)
        else:
            market = sell_min
            net = market * (1 - tax - broker)
        avg_buy = h["avg_buy"]
        if avg_buy and avg_buy > 0:
            margin = (net - avg_buy) / avg_buy * 100.0
            profit_total = (net - avg_buy) * h["quantity"]
            flag = margin >= target
        else:
            margin = 0.0
            profit_total = 0.0
            flag = False
        rows.append(Holding(
            type_id=tid,
            name=names.get(tid, f"#{tid}"),
            quantity=h["quantity"],
            avg_buy=avg_buy,
            oldest_date=h.get("oldest", ""),
            jita_sell_min=sell_min,
            jita_buy_max=buy_max,
            net_unit=net,
            margin_pct=margin,
            profit_total=profit_total,
            flag=flag,
        ))
    rows.sort(key=lambda r: r.margin_pct, reverse=True)
    return rows
