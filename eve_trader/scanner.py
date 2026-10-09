"""Market-wide scanner for all Jita items.

Two data passes:
  1. Universe + current prices: page the public Jita order book once
     (cached). Gives best buy/sell and on-book liquidity for every item.
  2. History (per item, cached): daily average + volume, used for the
     undervalued signal and the real volume filter.
"""
import concurrent.futures as cf
import time

import requests

from . import config, esi, store

_UA = {"User-Agent": "MotorMarket/0.1"}
_ORDERS = f"{config.ESI_BASE}/markets/{config.FORGE_REGION}/orders/"

# Zweistufige Bau-Gewinn-Schätzung ("build"-Modus): die schnelle Pro-Stück-
# Formel (build_cost) kennt keine Losgröße/Reaktions-Überschuss und kann
# Grenzfälle zu pessimistisch einschätzen. Items innerhalb dieses Fensters um
# die Marge-Schwelle werden NACH der schnellen Vorfilterung nochmal genau
# (mit einer realistischen Losgröße über production_plan) nachgerechnet -
# der große Rest bleibt bei der schnellen Schätzung (Performance).
_BORDERLINE_MARGIN_WINDOW = 15.0

# Wie alt darf eine gecachte Historie sein, um noch GRATIS mitanalysiert zu
# werden (Analyse-Deckel, s. find_deals)? Bewusst deutlich mehr als die 24 h,
# nach denen history_cached einen Neuabruf ansetzt:
#   • Mit 24 h wären am Tag nach einem Scan ALLE gecachten Historien
#     gleichzeitig "veraltet" - die analysierte Grundgesamtheit fiele täglich
#     auf das Abruf-Budget zurück, statt zu wachsen. Genau das soll die
#     Änderung ja verhindern.
#   • Fachlich unkritisch: der aktuelle PREIS kommt immer frisch aus dem
#     Markt-Snapshot. Die Historie liefert nur Normalpreis/Volumen/Trend über
#     ein 30-180-Tage-Fenster - ein paar fehlende Tage am Ende verschieben
#     einen 90-Tage-Median praktisch nicht (und Swing hält ohnehin Wochen).
# Items, die älter als das hier sind, fallen ins Abruf-Budget zurück und
# werden dort turnusmäßig aufgefrischt.
_CACHE_ANALYZE_MAX_AGE_H = 168.0     # 7 Tage


def _realistic_build_qty(sell_price):
    """Grobe, preis-gestaffelte Schätzung, wie viel man von einem Item
    realistischerweise auf einmal baut - billige Munition/Ammo in
    Tausenderpacks, Fregatten in Dutzenden, teure Schiffe nur einzeln. Nur für
    die genaue Losgrößen-Nachrechnung von Grenzfällen gedacht, keine feste
    Empfehlung."""
    p = sell_price or 0
    if p < 10_000:
        return 5000
    if p < 100_000:
        return 500
    if p < 1_000_000:
        return 50
    if p < 10_000_000:
        return 10
    if p < 100_000_000:
        return 3
    return 1


# ---- universe / current prices ---------------------------------------------
def build_snapshot(progress=None, region: int = config.FORGE_REGION,
                   should_cancel=None, station: int = None,
                   hub_label: str = None) -> list:
    """Page through every sell+buy order in a region, aggregate per type_id.
    If 'station' is given, only orders AT that station are counted, so the scan
    reflects the actual trade hub (Jita 4-4, Amarr EFA, …) instead of the whole
    region – keeps the deals consistent with the station-specific price/order
    lookups elsewhere."""
    orders_url = f"{config.ESI_BASE}/markets/{region}/orders/"

    def get_page(p, want_pages=False):
        """Fetch one order page. Short timeout + rate-limit (420/429) backoff so a
        throttled ESI — e.g. after several quick re-scans — doesn't stall for 40 s
        per page. Returns rows (or (rows, pages) if want_pages).
        rows is None wenn die Seite nach allen Versuchen NICHT ladbar war -
        bewusst unterscheidbar von einer leeren Seite, damit der Aufrufer
        fehlende Seiten erkennt statt still einen unvollständigen (= falsche
        Preise enthaltenden) Snapshot zu speichern."""
        rows, pages = None, 1
        for attempt in range(4):
            if should_cancel and should_cancel():
                break
            try:
                r = esi._session.get(orders_url,
                                     params={"order_type": "all", "page": p},
                                     headers=_UA, timeout=15)
            except Exception:
                if attempt == 3:
                    break
                time.sleep(1.0)
                continue
            if r.status_code in (420, 429):
                wait = 2.0
                ra = r.headers.get("Retry-After")
                if ra:
                    try:
                        wait = min(10.0, float(ra))
                    except ValueError:
                        pass
                time.sleep(wait)
                continue
            if r.status_code >= 500:
                # 5xx = transient (CCP-Gateway-Schluckauf) -> wie Netzfehler
                # behandeln und erneut versuchen, statt die Seite sofort
                # aufzugeben (vorher: 1 Versuch, Seite weg).
                if attempt == 3:
                    break
                time.sleep(1.0)
                continue
            try:
                r.raise_for_status()
                rows = r.json()
                pages = int(r.headers.get("X-Pages", "1"))
            except Exception:
                rows = None
            break
        return (rows, pages) if want_pages else rows

    first_page, pages = get_page(1, want_pages=True)
    if first_page is None:
        if should_cancel and should_cancel():
            return []
        from .sprache import t as _txt
        raise RuntimeError(_txt("Market scan: page 1 of the order book could not be "
                                "loaded (ESI unreachable?) \u2013 the old snapshot "
                                "stays active."))
    agg = {}

    def fold(orders):
        for o in orders:
            if station and o.get("location_id") != station:
                continue        # nur Orders an der Hub-Station zählen
            tid = o["type_id"]
            a = agg.setdefault(tid, {"type_id": tid, "sell_min": 0.0, "buy_max": 0.0,
                                     "sell_qty": 0, "buy_qty": 0,
                                     "sell_orders": 0, "buy_orders": 0,
                                     "sell_best_qty": 0, "buy_best_qty": 0})
            if o["is_buy_order"]:
                a["buy_orders"] += 1
                a["buy_qty"] += o["volume_remain"]
                # Menge AM besten Preis: ein Spread, der nur hinter 1 Stück
                # existiert, ist keiner (Wegwerf-Order-Falle).
                if o["price"] > a["buy_max"]:
                    a["buy_max"] = o["price"]
                    a["buy_best_qty"] = o["volume_remain"]
                elif o["price"] == a["buy_max"]:
                    a["buy_best_qty"] += o["volume_remain"]
            else:
                a["sell_orders"] += 1
                a["sell_qty"] += o["volume_remain"]
                if a["sell_min"] == 0 or o["price"] < a["sell_min"]:
                    a["sell_min"] = o["price"]
                    a["sell_best_qty"] = o["volume_remain"]
                elif o["price"] == a["sell_min"]:
                    a["sell_best_qty"] += o["volume_remain"]

    fold(first_page)
    if progress:
        progress(1, pages)

    ex = cf.ThreadPoolExecutor(max_workers=8)
    failed_pages = []
    try:
        futures = {ex.submit(get_page, p): p for p in range(2, pages + 1)}
        done = 1
        for fut in cf.as_completed(futures):
            if should_cancel and should_cancel():
                try:
                    ex.shutdown(wait=False, cancel_futures=True)
                except TypeError:
                    ex.shutdown(wait=False)
                return []          # cancelled → don't save a partial snapshot
            try:
                res = fut.result()
            except Exception:
                res = None
            if res is None:
                failed_pages.append(futures[fut])
            else:
                fold(res)
            done += 1
            if progress:
                progress(done, pages)
    finally:
        ex.shutdown(wait=False)

    # Fehlgeschlagene Seiten NICHT still weglassen (fehlt die Seite mit der
    # günstigsten Sell-Order eines Items, steht dessen sell_min falsch im
    # Snapshot - und der gilt dann für ALLE Berechnungen bis zum nächsten
    # Scan). Erst seriell nachladen; klappt es immer noch nicht: Abbruch OHNE
    # zu speichern - der alte (vollständige) Snapshot bleibt aktiv.
    still_failed = []
    for p in sorted(failed_pages):
        if should_cancel and should_cancel():
            return []
        res = get_page(p)
        if res is None:
            still_failed.append(p)
        else:
            fold(res)
    if still_failed:
        from .sprache import t as _txt
        raise RuntimeError(_txt(
            "Market scan incomplete: {n} of {pages} order book pages could not be "
            "loaded (e.g. page {p}). The snapshot is NOT saved \u2013 the old one "
            "stays active. Please scan again.").format(
                n=len(still_failed), pages=pages, p=still_failed[0]))

    if should_cancel and should_cancel():
        return []
    rows = list(agg.values())
    store.save_snapshot(rows, region)
    if hub_label:
        store.set_scan_label(hub_label)
    return rows


# ---- history ---------------------------------------------------------------
def history_cached(type_id: int, region: int = config.FORGE_REGION,
                   max_age_h: float = 24, allow_fetch=True) -> list:
    # ESI market history updates once a day, so a 24h cache avoids needless
    # refetches while staying current.
    age = store.history_age_seconds(type_id, region)
    have = store.get_history(type_id, region)
    stale = age is None or age > max_age_h * 3600
    # If we have a timestamp but NO rows, that's either a genuinely untraded item
    # or (more often) a fetch that failed/was rate-limited. Retry those after just
    # 1h instead of 24h, so a bad run doesn't hide items for a whole day. Items
    # WITH real history still stay cached the full 24h (fast).
    if not stale and not have and age is not None and age > 3600:
        stale = True
    # allow_fetch=False → the run has hit ESI's rate limit; stop fetching new
    # history and just use whatever is cached, so the scan finishes fast instead
    # of crawling through hundreds of timing-out requests.
    if not (stale and allow_fetch):
        return have                       # cache hit → single DB read, no fetch
    data = None
    try:
        data = esi.fetch_market_history(type_id, region)
    except esi.RateLimited:
        raise                             # let find_deals back off globally
    except Exception:
        data = None
    if data is not None:
        store.save_history(type_id, data, region)
        return store.get_history(type_id, region)   # re-read the freshly saved rows
    # negative cache: don't hammer every run, but the 1h empty-retry above
    # means it heals quickly once ESI cooperates.
    try:
        store.touch_history(type_id, region)
    except Exception:
        pass
    return have                           # nothing new; return what we already had


def trend_stats(history: list, days: int) -> dict:
    """Normal price level (robust median) + trend direction over the window.
    Used for the buy-low/hold/sell-high (mean-reversion) strategy."""
    rows = history[-days:] if days else history
    avgs = [r["average"] for r in rows if r["average"]]
    n = len(avgs)
    if n < 4:
        return {"normal": 0.0, "trend_pct": 0.0, "trend": "unklar"}
    s = sorted(avgs)
    mid = n // 2
    median = s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2
    mean = sum(avgs) / n
    # linear regression slope over the window
    xs = list(range(n))
    mx = sum(xs) / n
    num = sum((xs[i] - mx) * (avgs[i] - mean) for i in range(n))
    den = sum((xs[i] - mx) ** 2 for i in range(n)) or 1.0
    slope = num / den
    trend_pct = (slope * (n - 1) / mean * 100) if mean else 0.0  # total % change over window
    if trend_pct < -8:
        trend = "falling"
    elif trend_pct > 8:
        trend = "rising"
    else:
        trend = "sideways"
    return {"normal": median, "trend_pct": trend_pct, "trend": trend}


def long_baseline(history: list) -> float:
    """Ausreißer-fester Langzeit-Normalpreis: Median der Tagesdurchschnitte
    über die GESAMTE verfügbare Historie (ESI liefert ~13 Monate). Ein 2-3-
    Wochen-Spike ist darin nur ein kleiner Bruchteil der Tage und verschiebt
    den Median praktisch nicht - anders als den Fenster-Normalwert, wenn das
    Fenster gerade die Abkling-Phase des Spikes enthält (Nutzer-Fall:
    "vor 3-4 Monaten Spike, 3 Wochen Fall zurück aufs Jahresniveau - Tool
    hielt das Jahresniveau für ein Schnäppchen"). Ab 120 Datentagen belastbar,
    sonst 0 (= nicht verfügbar)."""
    # NUR die letzten 180 Tage: ein 2-3-Wochen-Spike ist darin ~11 % der
    # Tage (Median unbeeindruckt), aber legitim GEWACHSENE Preise werden
    # nicht mehr an ihrem Vorjahres-Niveau gemessen - die 13-Monats-Version
    # kappte jeden Aufwärtstrend weg und leerte den Swing-Scan (Regression,
    # vom Nutzer gemeldet).
    avgs = [r["average"] for r in history[-180:] if r.get("average")]
    if len(avgs) < 90:
        return 0.0
    avgs = sorted(avgs)
    return avgs[len(avgs) // 2]


def recovery_days_estimate(history: list, normal: float, current: float) -> float:
    """Wie viele Tage brauchte das Item nach VERGLEICHBAREN Dips historisch
    zurück zum Normalpreis? Episoden: Tagesdurchschnitt fällt mindestens 60 %
    so tief unter Normal wie jetzt; Dauer bis zur ersten Rückkehr auf >=
    Normal. Nur ABGESCHLOSSENE Episoden zählen (die laufende am Ende nicht).
    0 = keine vergleichbare Episode gefunden."""
    if not normal or normal <= 0 or current <= 0 or current >= normal:
        return 0.0
    depth_now = (normal - current) / normal
    thresh = normal * (1.0 - 0.6 * depth_now)
    durations, start = [], None
    for i, r in enumerate(history):
        a = r.get("average") or 0.0
        if not a:
            continue
        if start is None:
            if a <= thresh:
                start = i
        else:
            if a >= normal:
                durations.append(max(1, i - start))
                start = None
    # start != None am Ende = laufende Episode -> bewusst NICHT werten
    return (sum(durations) / len(durations)) if durations else 0.0


def recovery_factor(trend: str, trend_pct: float) -> float:
    """Swing-Gegenstück zum Daytrade-Einstiegs-Faktor: du willst einen Dip, der
    sich ERHOLT – kein fallendes Messer. Ein noch (steil) fallender Preis wird
    abgewertet, steigend (Erholung bestätigt) oder seitwärts (Boden gefunden)
    voll gewertet. Rückgabe ~0.25–1.0. Rein additiv zu den bestehenden Filtern;
    berührt die Flip-Logik nicht."""
    if trend == "rising":
        return 1.0
    if trend == "sideways":
        return 0.9
    if trend == "falling":
        steep = min(1.0, abs(trend_pct) / 40.0)   # −40 % übers Fenster = voll steil
        return max(0.25, 0.7 - 0.45 * steep)       # leicht fallend 0.7 … steil 0.25
    return 0.85                                    # "unklar"/"—": leicht vorsichtig


def price_spike_pct(history: list, days: int, recent_n: int = 3) -> float:
    """Wie weit liegt der JÜNGSTE Preis über seiner eigenen Vorlauf-Basis?
    >0 = frischer Aufwärts-Spike, <=0 = Drop oder normal.

    Bewusst ASYMMETRISCH gedacht (Nutzer-Vorgabe Daytrade): in einen
    hochgeschossenen Preis kauft man nicht ein - der fällt meist zurück und
    die Buy-Order füllt sich genau dann, wenn es weh tut. Ein plötzlicher
    DROP dagegen ist zum Einkaufen willkommen; deshalb wird ein negativer
    Wert nie bestraft, sondern nur zurückgegeben.

    Basis = MEDIAN der Tage VOR dem jüngsten Fenster (robust gegen einzelne
    Ausreißer), Vergleich = Durchschnitt der letzten `recent_n` Handelstage.
    Unterscheidet sich bewusst von max_over_norm: das misst das NIVEAU gegen
    den Median des ganzen Fensters (ein seit Wochen hoher Preis fällt dort
    nicht auf), das hier misst die frische BEWEGUNG."""
    rows = [r for r in (history[-days:] if days else history) if r.get("average")]
    if len(rows) < recent_n + 5:
        return 0.0                      # zu wenig Historie -> keine Aussage
    base = sorted(r["average"] for r in rows[:-recent_n])
    n = len(base)
    med = base[n // 2] if n % 2 else (base[n // 2 - 1] + base[n // 2]) / 2.0
    if med <= 0:
        return 0.0
    recent = [r["average"] for r in rows[-recent_n:]]
    return (sum(recent) / len(recent) / med - 1.0) * 100.0


def window_stats(history: list, days: int) -> dict:
    rows = history[-days:] if days else history
    if not rows:
        return {"avg": 0.0, "low": 0.0, "high": 0.0, "spread": 0.0,
                "spread_med_isk": 0.0, "vol_med": 0.0,
                "daily_vol": 0.0, "n": 0, "active_ratio": 0.0, "txn_day": 0.0,
                "day_range_pct": 0.0, "trade_score": 0.0}
    avgs = [r["average"] for r in rows if r["average"]]
    vols = [r["volume"] or 0 for r in rows]
    lows = [r["lowest"] for r in rows if r["lowest"]]
    highs = [r["highest"] for r in rows if r["highest"]]
    avg = sum(avgs) / len(avgs) if avgs else 0.0
    low = min(lows) if lows else 0.0
    high = max(highs) if highs else 0.0

    # ---- tradability: will your buy AND sell orders actually get filled? ----
    # Read from the same signals the in-game price-history graph shows:
    #   • how MANY days it actually trades (regularity)   → active_ratio
    #   • how many separate fills per day (order_count)    → txn_day
    #   • the daily high–low band that repeats every day   → day_range_pct
    #     (price bounces between buy side and sell side → both get hit)
    n = len(rows)
    active_days = sum(1 for v in vols if v > 0)
    active_ratio = active_days / n if n else 0.0
    txns = sorted(r.get("order_count") or 0 for r in rows if (r.get("volume") or 0) > 0)
    txn_day = txns[len(txns) // 2] if txns else 0.0        # median transactions/day
    day_ranges = [((r["highest"] - r["lowest"]) / r["average"] * 100.0)
                  for r in rows
                  if r.get("average") and r.get("highest") and r.get("lowest")
                  and (r.get("volume") or 0) > 0]
    day_ranges.sort()
    day_range_pct = day_ranges[len(day_ranges) // 2] if day_ranges else 0.0
    # BUY-ORDER FILL signal (your insight): on a day where lowest == highest, the
    # price didn't span a range → only ONE side of the book traded (in practice the
    # sell side). Your BUY order only fills on days where lowest < highest. So the
    # share of active days with a real range tells you how often your buy order
    # actually gets hit. Low value = a sell-only item → useless for flipping.
    both_sides_days = sum(1 for r in rows
                          if (r.get("volume") or 0) > 0
                          and r.get("highest") and r.get("lowest")
                          and r["highest"] > r["lowest"])
    both_sides_ratio = (both_sides_days / active_days) if active_days else 0.0
    # combined 0–100 score: regularity gates it, liquidity (txns) and a real
    # daily churn band lift it. This isolates the "traded on both sides, every
    # day" items that are ideal for day/hour trading.
    liq = min(1.0, txn_day / 15.0)
    churn = min(1.0, day_range_pct / 6.0)      # ~6%+ daily band = full churn marks
    trade_score = 100.0 * active_ratio * (0.30 + 0.45 * liq + 0.25 * churn)

    # Median-TAGESspread in ISK (nur echte Beide-Seiten-Tage): der Spread, den
    # das Item WIRKLICH täglich hergibt - Basis für den Realitätscheck gegen
    # Wegwerf-Order-Spreads im aktuellen Buch (D1).
    _dsp = sorted(r["highest"] - r["lowest"] for r in rows
                  if r.get("highest") and r.get("lowest")
                  and r["highest"] > r["lowest"] and (r.get("volume") or 0) > 0)
    spread_med_isk = _dsp[len(_dsp) // 2] if _dsp else 0.0
    _va = sorted(v for v in vols if v > 0)
    vol_med = _va[len(_va) // 2] if _va else 0.0
    return {
        "avg": avg,
        "low": low,
        "high": high,
        "spread": ((high - low) / avg * 100.0) if avg else 0.0,
        "spread_med_isk": spread_med_isk,
        "vol_med": vol_med,
        "daily_vol": sum(vols) / len(vols),
        "n": n,
        "active_ratio": active_ratio,
        "txn_day": txn_day,
        "day_range_pct": day_range_pct,
        "both_sides_ratio": both_sides_ratio,
        "trade_score": trade_score,
    }


# ---- deal computation ------------------------------------------------------
def find_deals(snapshot, settings, days, mode, filters, progress=None,
               recipes=None, build_opts=None, region=config.FORGE_REGION,
               should_cancel=None, flip_rank="spanne", diag=None,
               price_snapshot=None) -> list:
    """mode: 'flip' | 'under' | 'drop' | 'build'.
    For 'build', recipes (industry.Recipes) and build_opts must be supplied.

    price_snapshot (optional): Preisquelle, falls sie NICHT mit der
    Kandidatenliste identisch ist. Der Bauen-Tab filtert `snapshot` auf
    verkaufbare Endprodukte der gewaehlten Tech-Stufe herunter - dieselbe
    Liste war bisher auch die einzige Preisquelle, also fehlten saemtliche
    VORPRODUKTE (Mineralien, T1-Bauteile, Mondstoffe, Datacores) im
    price_map. build_cost() bricht ohne Materialpreis komplett ab und liefert
    None: bei einem T2-Scan des Nutzers 602 von 807 Kandidaten als
    "Baukosten nicht berechenbar". Eine Liste, zwei Zwecke - hier getrennt.

    diag (optional, dict): wird mit Ausschluss-Zählern befüllt (no_history,
    vol_filtered, below_margin, no_build_cost, rate_limited_hits,
    fetch_stopped, analyzed) - damit die UI erklären kann, WARUM ein Scan
    wenig/nichts zeigt (z.B. Preishistorie fehlt wegen ESI-Limit), statt
    kommentarlos '0 Treffer'. Im 'under'-Modus (Swing) kommt der komplette
    Trichter dazu: hist_too_short, below_min_margin, under_too_deep,
    falling_skipped, contradictory, exp_nonpositive, exp_pct_low, exp_isk_low,
    exit_thin, dos_high, sell_fill_low, ... plus 'passed' (Treffer vor dem
    max_items-Deckel).

    filters kennt zwei optionale Analyse-Deckel (0/fehlend = altes Verhalten,
    pauschaler max_items-Deckel):
      max_cached_items - so viele Items MIT frisch gecachter Historie werden
                         analysiert (kosten keinen ESI-Abruf)
      max_new_history  - harte Obergrenze für NEU zu holende Historien/Scan"""
    tax = settings["sales_tax_pct"] / 100.0
    broker = settings["broker_fee_pct"] / 100.0
    pmin = filters.get("price_min", 0) or 0
    pmax = filters.get("price_max", 0) or 0
    min_margin = filters.get("min_margin", 0) or 0
    min_vol = filters.get("min_daily_vol", 0) or 0
    # Reaktions-Preset: `is_manufactured` deckt nur MANUFACTURING ab, eine
    # Reaktion faellt sonst als "nicht baubar" raus. EINE Stelle entscheidet
    # das, damit die drei Tore unten nicht auseinanderlaufen.
    _incl_reac = bool(filters.get("include_reactions"))

    def _producible(tid):
        if recipes is None:
            return False
        if recipes.is_manufactured(tid):
            return True
        return _incl_reac and tid in (getattr(recipes, "reaction_products", None) or ())

    # EIN Trichter-Zaehler fuer die ganze Funktion. Vorher war `_d` INNERHALB
    # der Kandidatenschleife definiert - die Nachrechen-Stufe danach hatte ihn
    # deshalb gar nicht in Reichweite und verwarf Items still. Genau das hat
    # die Invariante "analysiert == Treffer + alle Ausschluesse" gebrochen,
    # ohne dass es jemand sehen konnte (Nutzer-Fund: 408 gescannt, 205 im
    # Trichter, 0 Treffer - 203 Items ohne jede Spur).
    def _d(key):
        if diag is not None:
            diag[key] = diag.get(key, 0) + 1
    min_profit = filters.get("min_profit_isk", 0) or 0
    min_roi = filters.get("min_roi", 0) or 0
    max_dos = filters.get("max_dos", 0) or 0
    min_vola = filters.get("min_volatility", 0) or 0
    min_profit_day = filters.get("min_profit_day", 0) or 0
    min_realistic_qty = filters.get("min_realistic_qty", 0) or 0  # realist. Stück/Tag
    min_exit_qty = filters.get("min_exit_qty", 0) or 0            # Swing: realist. Verkauf/Tag
    min_expected_isk = filters.get("min_expected_isk", 0) or 0    # Swing: absoluter Gewinn/Stk-Boden
    avoid_falling = filters.get("avoid_falling", False)
    min_expected = filters.get("min_expected_pct", 0) or 0
    # a real reversion dip is moderate; huge gaps below "normal" are almost always
    # data artefacts (unit/scale glitches, ancient spikes), so cap them out
    max_under = filters.get("max_under_pct", 0) or 0
    min_hist_days = filters.get("min_hist_days", 0) or 0
    min_sell_fill = filters.get("min_sell_fill", 0) or 0
    min_trade_score = filters.get("min_trade_score", 0) or 0
    min_both_sides = filters.get("min_both_sides", 0) or 0   # % of active days that fill buy orders
    max_over_norm = filters.get("max_over_norm", 0) or 0     # % über Normal (hart, 0=aus)
    # Daytrade-Spike-Sperre (Nutzer): frisch hochgeschossene Preise NICHT
    # bekaufen; Drops bleiben ausdrücklich erlaubt (0 = aus).
    max_spike = filters.get("max_spike_pct", 0) or 0
    # hard buy-side floor: average share of the buy<->sell spread the daily lows
    # actually reach (see buy_reach). A sell-only item (skillbooks/blueprints that
    # only trade up at the ask) stays near 0 and gets dropped entirely — used by
    # Gold-Suche so it shows only real two-sided flips.
    min_buy_reach = filters.get("min_buy_reach", 0.0) or 0.0
    # "Beide Seiten taeglich": Mindest-%-Beleg, dass Low UND High jeden Tag
    # beide Order-Seiten erreichen (s. two_sided unten). 0 = aus.
    min_two_sided = filters.get("min_two_sided", 0) or 0
    # flip plausibility: buy must be at least this fraction of sell (real spread,
    # not a 1-ISK ghost order). Default 40% → max ROI roughly ~150%.
    min_buy_ratio = filters.get("min_buy_ratio", 40) or 0
    max_competitors = filters.get("max_competitors", 0) or 0
    cap = filters.get("max_items", 400)

    # Preise IMMER aus der vollen Quelle (s. price_snapshot im Docstring):
    # die Kandidatenliste kann gefiltert sein, die Vorprodukte stehen dann
    # nicht mehr drin - und ohne Materialpreis liefert build_cost() gar nichts.
    price_map = {s["type_id"]: s["sell_min"]
                 for s in (price_snapshot if price_snapshot is not None else snapshot)
                 if s["sell_min"] > 0}
    price_fn = price_map.get
    build_memo = {}
    build_time_memo = {}
    # Aufschluesselung je Item (mat_market/mat_adjusted/job/inv/inv_saved),
    # von build_cost() selbst gefuellt - fuer die beiden Angaben, die eine
    # Trefferzeile ehrlich machen: welcher ANTEIL der Kosten nur aus dem
    # Adjusted-Price-Rueckfall stammt, und wieviel Invention wegen eigener
    # BPCs gar nicht berechnet wurde.
    build_parts = {}
    from . import industry

    pre = []
    for s in snapshot:
        sell, buy = s["sell_min"], s["buy_max"]
        if sell <= 0:
            continue
        if mode == "flip" and buy <= 0:
            continue  # a flip needs a real buy order; swing/build only need a sell
        if pmin and sell < pmin:
            continue
        if pmax and sell > pmax:
            continue
        # Flip: you ACQUIRE via a buy order (broker fee on the buy order) and
        # SELL via a sell order (sales tax + broker fee). Both broker fees count.
        # Other modes buy instantly from sell orders (no broker on the buy).
        net = sell * (1 - tax - broker)
        if mode == "flip":
            buy_cost = buy * (1 + broker)
        else:
            buy_cost = buy
        profit_unit = net - buy_cost
        roi = (profit_unit / buy * 100) if buy else 0
        pre.append((s, profit_unit, roi))

    # Pick which candidates to analyse. The market has ~13k items; fetching
    # history for all is slow, so we choose a subset — but the subset MUST span
    # every price range, otherwise cheap high-turnover commodities crowd out the
    # ships and modules the trader actually wants. Two cases:
    #   • already narrowed (price/category filter) → analyse everything
    #   • full market → stratify by price band and take the most liquid items
    #     from EACH band, so ships (1–100M) and modules always get a fair share.
    #     This also BOUNDS how many market-history calls the first (uncached) run
    #     makes, so a full-market scan doesn't fetch history for 3000+ items.
    # WICHTIG (Bauen/Unter-Baupreis): die Liquiditäts-Sortierung allein weiß
    # nichts von "baubar" - hochliquide, aber NICHT baubare Commodities
    # (Minerale, Munition, PLEX, Fuel Blocks - oft die mit dem höchsten
    # Tagesvolumen überhaupt) konnten dadurch echte T1/T2-Module/Schiffe aus
    # der analysierten Auswahl komplett verdrängen, BEVOR die Bau-Prüfung
    # überhaupt eine Chance hatte - der Kandidat wurde nie erreicht, nicht weil
    # er unprofitabel war, sondern weil er nie in der Stichprobe landete. Für
    # diese beiden Modi daher ZUERST auf baubare Items eingrenzen.
    if mode in ("build", "underbuild") and recipes is not None:
        pre = [x for x in pre if _producible(x[0]["type_id"])]

    def _stratified_pick(pool, per_band, top_isk):
        """Preisband-faire Stichprobe aus `pool`: aus JEDEM Preisband die
        liquidesten Items, dazu die insgesamt wertvollsten Orderbücher."""
        bands = [(0, 1e5), (1e5, 1e6), (1e6, 1e7),
                 (1e7, 1e8), (1e8, 1e10), (1e10, 1e18)]
        picks = {}
        for lo, hi in bands:
            band = [x for x in pool if lo <= x[0].get("sell_min", 0) < hi]
            band.sort(key=lambda x: x[0].get("sell_qty", 0), reverse=True)
            for it in band[:per_band]:
                picks.setdefault(it[0]["type_id"], it)
        # plus the highest on-book ISK value overall (ultra-liquid staples)
        by_isk = sorted(
            pool, key=lambda x: x[0].get("sell_qty", 0) * x[0].get("sell_min", 0),
            reverse=True)
        for it in by_isk[:top_isk]:
            picks.setdefault(it[0]["type_id"], it)
        return list(picks.values())

    # ---- Analyse-Deckel: nur der ABRUF ist teuer, nicht die Analyse ---------
    # Der alte Deckel begrenzte die Kandidaten pauschal, obwohl der einzige
    # echte Kostenfaktor die NEU zu holenden Historien sind (ESI rate-limitet
    # den History-Endpunkt hart). Eine bereits gecachte Historie kostet nur
    # einen DB-Lesevorgang - die darf/soll IMMER mitanalysiert werden.
    # Deshalb zwei getrennte Töpfe (aktiv, sobald max_cached_items gesetzt ist):
    #   • gecacht  -> bis max_cached_items Stück, gratis (kein ESI-Abruf)
    #   • ungecacht-> hart auf max_new_history gedeckelt (das Abruf-Budget)
    # Effekt: jeder Scan holt ~Budget NEUE Historien dazu, die beim nächsten
    # Mal im Gratis-Topf landen - die analysierte Grundgesamtheit wächst über
    # wenige Scans um ein Vielfaches, ohne dass ein Scan teurer wird.
    max_cached = filters.get("max_cached_items", 0) or 0
    fetch_budget = filters.get("max_new_history", 0) or 0
    cached_ids = set()
    if max_cached:
        try:
            cached_ids = store.fresh_history_type_ids(
                region, filters.get("cached_max_age_h") or _CACHE_ANALYZE_MAX_AGE_H)
        except Exception:
            cached_ids = set()          # DB-Problem -> wie "nichts gecacht"
        have = [x for x in pre if x[0]["type_id"] in cached_ids]
        fresh = [x for x in pre if x[0]["type_id"] not in cached_ids]
        if len(have) <= max_cached:
            sel = have                                   # alles Gecachte rein
        else:
            sel = _stratified_pick(have, max(1, max_cached // 5),
                                   max(1, max_cached // 10))
            if len(sel) < max_cached:
                # Bänder sind unterschiedlich dicht besetzt - den Rest des
                # Deckels mit den liquidesten übrigen Items auffüllen, statt
                # ihn ungenutzt zu lassen.
                got = {x[0]["type_id"] for x in sel}
                rest = sorted((x for x in have if x[0]["type_id"] not in got),
                              key=lambda x: x[0].get("sell_qty", 0), reverse=True)
                sel = sel + rest[:max_cached - len(sel)]
            sel = sel[:max_cached]
        # Abruf-Pause, solange der Cache-Topf ÜBER dem Analyse-Deckel liegt:
        # jede neu geholte Historie würde beim nächsten Lauf vom Deckel gleich
        # wieder weggeschnitten - sie kostet einen ESI-Abruf, bringt aber
        # keinen einzigen zusätzlichen Kandidaten. Also gar nicht erst holen;
        # Preset-Wechsel laufen dann rein aus dem Cache (schnell). Sobald der
        # Deckel angehoben wird (Kalibrierung) und wieder Luft hat, laufen
        # die Abrufe automatisch weiter.
        fetch_paused = len(have) > max_cached
        if fetch_paused:
            fetch_budget = 0
        if fetch_budget and fresh:
            if len(fresh) <= fetch_budget:
                new_sel = fresh
            else:
                new_sel = _stratified_pick(fresh, max(1, fetch_budget // 6),
                                           max(1, fetch_budget // 6))[:fetch_budget]
        else:
            new_sel = []
        pre = sel + new_sel
        if diag is not None:
            diag["cached_pool"] = len(have)      # gecacht UND im Preisfenster
            diag["cached_analyzed"] = len(sel)   # davon analysiert (gratis)
            diag["fetch_slots"] = len(new_sel)   # neu zu holende Historien
            diag["fetch_paused"] = fetch_paused  # Topf > Deckel -> nichts Neues
            diag["cached_cap"] = max_cached      # für die Anzeige des Deckels
    elif len(pre) > 1500:
        # Altverhalten (Flip/Bauen/Gold-Suche): pauschaler Deckel.
        _pre_n = len(pre)
        pre = _stratified_pick(pre, max(cap // 2, 220), cap // 2)
        if diag is not None:
            # SICHTBAR MACHEN, dass hier eine Stichprobe gezogen wurde. Sonst
            # sieht "N analysiert" nach der Grundgesamtheit aus, obwohl es nur
            # die Auswahl ist - und die Frage "warum sind es nur so wenige
            # Kandidaten?" laesst sich an der Oberflaeche nicht beantworten.
            diag["sampled_from"] = _pre_n
            diag["sampled_out"] = _pre_n - len(pre)
    if diag is not None:
        diag.setdefault("candidates", len(pre))

    results = []
    total = len(pre)

    import threading
    _state = {"stop_fetch": False, "rl_hits": 0}
    _lock = threading.Lock()
    # GECACHTE HISTORIEN IN EINEM RUTSCH (emm336, Ladezeit-Messung emm237:
    # 1729 Einzelabfragen, je eine neue Verbindung, 8-9 s Rechenzeit). Das
    # Ergebnis ist dasselbe wie get_history je Item; scheitert die
    # Sammelabfrage, liest enrich wie bisher einzeln.
    _hist_vorab = {}
    try:
        _ids_vorab = [x[0]["type_id"] for x in pre if x[0]["type_id"] in cached_ids]
        if _ids_vorab:
            _hist_vorab = store.get_histories(_ids_vorab, region)
    except Exception:
        _hist_vorab = {}

    def enrich(item):
        s, profit_unit, roi = item
        if s["type_id"] in cached_ids:
            # Historie liegt nachweislich frisch im Cache (eine Sammelabfrage
            # oben). Direkt lesen statt über history_cached: spart den
            # Alters-Check pro Item UND macht hart unmöglich, dass ein
            # Gratis-Kandidat doch einen ESI-Abruf auslöst - nur so hält das
            # Abruf-Budget unten wirklich.
            hist = _hist_vorab.get(s["type_id"])
            if hist is None:
                hist = store.get_history(s["type_id"], region)
            return s, profit_unit, roi, window_stats(hist, days), hist
        allow = not _state["stop_fetch"]
        try:
            hist = history_cached(s["type_id"], region, allow_fetch=allow)
        except esi.RateLimited:
            # ESI is rate-limiting us; after a few hits, stop fetching new history
            # for the rest of this run and use only what's cached, so the scan
            # finishes quickly instead of crawling through timeouts.
            with _lock:
                _state["rl_hits"] += 1
                if _state["rl_hits"] >= 5:
                    _state["stop_fetch"] = True
            hist = store.get_history(s["type_id"], region)
        return s, profit_unit, roi, window_stats(hist, days), hist

    ex = cf.ThreadPoolExecutor(max_workers=12)
    try:
        futures = [ex.submit(enrich, it) for it in pre]
        done_n = 0
        for fut in cf.as_completed(futures):
            if should_cancel and should_cancel():
                # user cancelled → stop immediately, don't wait for in-flight calls
                try:
                    ex.shutdown(wait=False, cancel_futures=True)
                except TypeError:
                    ex.shutdown(wait=False)
                return results
            done_n += 1
            if progress:
                progress(done_n, total)
            _d("analysed")   # Bezugsgroesse der Invariante: JEDER Kandidat,
                             # der aus dem Executor zurueckkommt
            try:
                s, profit_unit, roi, st, hist = fut.result()
            except Exception:
                # NICHT still verschlucken: ein Item, dessen Analyse crasht
                # (z.B. transienter DB-Fehler unter Parallellast), muss im
                # Trichter auftauchen, sonst lügt die Invariante
                # "analysiert == Treffer + alle Ausschlüsse" unbemerkt.
                # (Im Testlauf real passiert: ~970 Items verschwanden einmalig
                # spurlos - genau die Klasse stiller Verluste, gegen die die
                # Diagnosezeile gebaut wurde.)
                if diag is not None:
                    diag["errors"] = diag.get("errors", 0) + 1
                continue
            daily_vol = st["daily_vol"]
            # FEHLENDE HISTORIE IST KEIN NULL-ABSATZ (ersetzt das gestrichene
            # "Erstlauf"-Preset): st["n"] == 0 heisst "Historie noch nicht
            # geladen" (ESI-Limit am frischen Hub), NICHT "verkauft sich
            # nicht". Im BAU-Modus darf so ein Item das Volumen-Tor
            # passieren und wird als "Absatz unbekannt" MARKIERT statt still
            # zu verschwinden (Arbeitsregel 6) - die Bewertung im UI traegt
            # den Vorbehalt. Trading-Modi bleiben unveraendert streng: dort
            # IST die Historie die Handelsgrundlage, ohne sie gibt es nichts
            # zu bewerten.
            vol_unknown = bool(st["n"] <= 0)
            if daily_vol < min_vol and not (vol_unknown and mode == "build"):
                # unterscheiden: KEINE Historie geladen (typisch: ESI-Limit beim
                # ersten Scan dieser Items - Tagesvolumen unbekannt, faellt auf 0)
                # vs. Historie da, Volumen wirklich zu niedrig.
                _d("no_history" if st["n"] <= 0 else "vol_filtered")
                continue
            sell, buy = s["sell_min"], s["buy_max"]
            avg = st["avg"]
            # ---- BUY-SIDE FILL: the real "is this a flip?" test ------------
            # A fat daily range means nothing if it all happens up at the SELL
            # price (players undercutting each other, e.g. NPC-priced skillbooks
            # and blueprints). Your BUY order only fills when trading actually
            # reaches DOWN to the buy side. Per active day we measure how far the
            # traded LOW dips into the current buy<->sell spread: 1.0 = down to
            # the buy order (buy fills), 0.0 = stuck at the sell price (buy never
            # fills). Averaged over the window this is the share of the spread the
            # buy side actually gets — the best "real flip" signal readable from
            # daily history, and it correctly rejects a sell-only range that the
            # plain high>low test lets through.
            buy_reach = 0.0
            sell_reach = 0.0
            two_sided = 0.0
            # Pro Handelstag DREI Belege aus Low/High (die "orangen Punkte" der
            # Ingame-Preistabelle):
            #   buy_reach:  wie tief das Tages-LOW in den aktuellen Spread
            #               Richtung Buy-Order reicht (1.0 = deine Buy fuellt)
            #   sell_reach: wie hoch das Tages-HIGH Richtung Sell-Order reicht
            #               (1.0 = deine Sell fuellt)
            #   two_sided:  min(beide) je Tag, gemittelt - DER "perfektes
            #               Daytrade-Item"-Beleg: jeden Tag Low unten UND High
            #               oben = beide Order-Seiten werden taeglich bedient.
            # Ohne Buy-Book (Swing-Fall) misst sell_reach die Naehe der Tages-
            # Hochs zum Ask (high/sell) - Buy-Seite ist dort per Definition egal.
            if sell > 0:
                _span = (sell - buy) if buy > 0 and sell > buy else 0.0
                _brs, _srs, _tws = [], [], []
                for _r in (hist[-days:] if days else hist):
                    if (_r.get("volume") or 0) <= 0:
                        continue
                    _lo = _r.get("lowest") or 0
                    _hi = _r.get("highest") or 0
                    if _span > 0:
                        _b = (max(0.0, min(1.0, (sell - _lo) / _span))
                              if _lo > 0 else None)
                        _s = (max(0.0, min(1.0, (_hi - buy) / _span))
                              if _hi > 0 else None)
                        if _b is not None:
                            _brs.append(_b)
                        if _s is not None:
                            _srs.append(_s)
                        if _b is not None and _s is not None:
                            _tws.append(min(_b, _s))
                    elif _hi > 0:
                        _srs.append(max(0.0, min(1.0, _hi / sell)))
                if _brs:
                    buy_reach = sum(_brs) / len(_brs)
                if _srs:
                    sell_reach = sum(_srs) / len(_srs)
                if _tws:
                    two_sided = sum(_tws) / len(_tws)
            # Handelbarkeit je Modus: Flip lebt davon, dass BEIDE Seiten
            # taeglich bedient werden (two_sided). Swing/Drop kauft im Sell und
            # verkauft im Sell - dort zaehlt allein die EXIT-Seite (sell_reach);
            # ein fehlendes Buy-Book darf einen Swing-Kandidaten nicht mehr
            # abwerten (vorher wurde ueberall mit buy_reach gegated).
            trade_score = st.get("trade_score", 0.0) * (
                two_sided if mode == "flip" else sell_reach)
            if min_buy_reach and buy_reach < min_buy_reach:
                _d("buy_reach_low")
                continue   # buy side barely reached → sell-only (skillbooks etc.)
            if min_two_sided and (two_sided * 100.0) < min_two_sided:
                _d("two_sided_low")
                continue   # nicht beide Seiten taeglich bedient → kein echter Flip
            if min_trade_score and trade_score < min_trade_score:
                _d("trade_score_low")
                continue
            both_sides = st.get("both_sides_ratio", 0.0)
            if min_both_sides and (both_sides * 100.0) < min_both_sides:
                _d("both_sides_low")
                continue   # buy order rarely fills (mostly sell-only days) → skip
            volatility = st["spread"]
            if min_vola and volatility < min_vola:
                _d("vola_low")
                continue
            under_pct = ((avg - sell) / avg * 100) if avg else 0
            # estimate of how much trading happens at the SELL-order price vs the
            # buy side. ESI gives no buy/sell split, so we use the position of the
            # average trade price within the current spread as a proxy:
            #   ~100% -> trades at sell orders (your sell order fills well)
            #   ~0%   -> trades at buy orders (your sell order just sits there)
            if buy <= 0:
                sell_fill = 100.0          # no buy orders → can only buy from sell side
            elif sell > buy:
                sell_fill = max(0.0, min(1.0, (avg - buy) / (sell - buy))) * 100
            else:
                sell_fill = 0.0
            dos = (s["sell_qty"] / daily_vol) if daily_vol else 9_999
            if max_dos and dos > max_dos:
                _d("dos_high")
                continue
            profit_day = profit_unit * daily_vol
            capital = buy * daily_vol
            # Bauzeit/ISK-Std nur im build-Modus gefüllt; sonst 0 (Feld existiert
            # trotzdem im Deal-Dict, damit die UI einheitlich darauf zugreifen kann).
            build_hours = 0.0
            isk_per_hour = 0.0
            # competition proxy: how many orders you'd fight on the worse side.
            # Each competitor typically holds one order per item, so the order
            # count ≈ number of rivals continually 0.01-ing you.
            n_sell = s.get("sell_orders", 0) or 0
            n_buy = s.get("buy_orders", 0) or 0
            competitors = max(n_sell, n_buy)
            if max_competitors and competitors > max_competitors:
                _d("competitors_high")
                continue
            # realistically capturable daily profit: you don't flip the WHOLE daily
            # volume — you share it with the rivals. This is the metric that makes
            # low-competition items (ships, niche modules) rank fairly against
            # heavily-contested commodities.
            capture_day = profit_day / (competitors + 1)
            spike = 1.0
            build_c = None
            build_profit = 0.0
            # reversion fields (filled in 'under' mode)
            normal = 0.0
            trend = "—"
            trend_pct = 0.0
            recovery = 1.0        # Swing: Erholungs-/Trend-Gewichtung (1.0 = neutral)
            # neue Qualitäts-Felder - IMMER pro Item initialisiert (kein
            # Übertrag aus der vorherigen Schleifenrunde)
            profit_real, roi_real, spread_capped = profit_unit, roi, False
            cycle_days = 0.0
            long_norm = 0.0
            spike_distorted = False
            dump_risk = False
            recovery_days = 0.0
            exp_day = 0.0
            over_norm = 0.0        # aktueller Preis über/unter historischem Normal
            target_sell = 0.0
            exp_profit = 0.0
            exp_pct = 0.0

            # Exit-Liquidität (nur Swing, nicht Flip): kannst du die angesammelte
            # Menge realistisch wieder VERKAUFEN? Dein Tagesanteil auf der Sell-Seite
            # = Volumen ÷ (Sell-Konkurrenten+1). Zu dünn → du sitzt auf dem Bestand.
            if mode != "flip" and min_exit_qty and \
                    (daily_vol / (n_sell + 1)) < min_exit_qty:
                _d("exit_thin")
                continue

            if mode == "flip":
                # plausibility: skip ghost flips where the buy order is far below
                # the sell (e.g. a lone 1-ISK buy order) → fantasy ROI
                if min_buy_ratio and sell > 0 and (buy / sell * 100) < min_buy_ratio:
                    _d("ghost_buy_order")
                    continue
                if profit_unit < min_profit:
                    _d("profit_low")
                    continue
                if roi < max(min_roi, min_margin):
                    _d("roi_low")
                    continue
                if min_profit_day and profit_day < min_profit_day:
                    _d("profit_day_low")
                    continue
                # realistischer Tagesanteil: du flippst NICHT das ganze Volumen, du
                # teilst es mit der Konkurrenz. Fängst du realistisch weniger als X
                # Stück/Tag ab, lohnt das Hantieren nicht (die 1-Stück-Fallen).
                if min_realistic_qty and (daily_vol / (competitors + 1)) < min_realistic_qty:
                    _d("realistic_qty_low")
                    continue
                # ---- SPIKE-SPERRE (asymmetrisch, Nutzer-Vorgabe) -------------
                spike_pct = price_spike_pct(hist, days)
                if max_spike and spike_pct > max_spike:
                    _d("spike_skipped")      # frisch hochgeschossen -> nicht kaufen
                    continue
                # rank depends on the chosen Flip sub-mode (all are Buy→Sell, they
                # just hunt different opportunities):
                #   spanne     – best realistic ISK/day overall
                #   stunden    – reliably flippable many times/hour (tradability
                #                × margin × turnover), for active hub trading
                #   konkurrenz – fewest rivals, passive „set & forget“
                #   nische     – overlooked mid-volume, solid-margin items
                import math as _math
                if flip_rank == "stunden":
                    score = trade_score * min(roi, 15) * _math.sqrt(min(daily_vol, 5000))
                elif flip_rank == "konkurrenz":
                    score = capture_day * (6.0 / (6.0 + competitors))
                elif flip_rank == "nische":
                    score = (profit_unit * min(daily_vol, 500) / (competitors + 1)) * \
                            min(2.0, max(0.5, roi / 8.0))
                elif flip_rank == "kapital":
                    # daily profit per bound ISK; a light volume floor avoids ranking
                    # a thin item that only trades a couple units a day at the top
                    cap_eff_score = (capture_day / capital) if capital else 0.0
                    score = cap_eff_score * min(1.0, daily_vol / 20.0)
                else:   # spanne (default)
                    score = capture_day
                # ALWAYS fold in buy-side fillability (see buy_reach above),
                # regardless of filters. An item whose daily trading never reaches
                # the buy side isn't a real flip no matter how fat the paper
                # margin. Full rank once the buy side is reached across >= _BR_FULL
                # of the spread on average; below that the score drops off STEEPLY
                # (squared) toward zero, so sell-only skillbooks/blueprints sink
                # out of the Top instead of merely being nudged down.
                # Jetzt two_sided statt nur buy_reach: der User-Massstab ist
                # "jeden Tag Low an der Buy-Seite UND High an der Sell-Seite".
                _TS_FULL = 0.55
                _ts_g = min(1.0, two_sided / _TS_FULL) if _TS_FULL else 1.0
                score *= _ts_g * _ts_g
                # ---- ENTRY QUALITY: nicht in einen hochgeschossenen Preis kaufen ----
                # Ein Flip taugt nur, wenn du TIEF einsteigst. Liegt der aktuelle Ask
                # deutlich ÜBER dem historischen Normalpreis (Median) – der Preis ist
                # also gerade hochgeschossen – ist eine Buy-Order dort riskant (kann
                # zurückfallen), auch bei fetter Papier-Marge. Wir dämpfen den Score,
                # je weiter der Preis über Normal liegt, und extra bei stark
                # STEIGENDEM Trend (überkauft). Bei Preis unter/nahe Normal: volle
                # Wertung (günstiger Einstieg = gut).
                ts = trend_stats(hist, days)
                normal = ts["normal"]; trend = ts["trend"]; trend_pct = ts["trend_pct"]
                over_norm = (sell / normal - 1.0) if (normal > 0 and sell > 0) else 0.0
                if max_over_norm and over_norm * 100.0 > max_over_norm:
                    _d("over_norm_high")
                    continue                     # zu weit über Normal → ganz raus
                entry_factor = 1.0
                if over_norm > 0.05:            # >5 % über Normal → dämpfen
                    entry_factor *= max(0.15, 1.0 - (over_norm - 0.05) / 0.5)
                if trend == "rising" and trend_pct > 15:   # scharfer Anstieg → extra
                    entry_factor *= max(0.45, 1.0 - (trend_pct - 15) / 70.0)
                score *= entry_factor
                # ---- D1 SPREAD-REALITÄTSCHECK: der Gewinn aus dem AKTUELLEN
                # Orderbuch ist eine Momentaufnahme (eine Wegwerf-Order kann
                # eine Traumspanne vorgaukeln). Die Historie kennt den ECHTEN
                # Median-Tagesspread. Realistischer Exit = min(Ask, Bid +
                # Medianspread); der Score wird auf den realistischen Gewinn
                # normiert - Fassaden-Deals rutschen nach unten.
                spread_med = st.get("spread_med_isk", 0.0) or 0.0
                if spread_med > 0 and buy > 0 and (sell - buy) > spread_med:
                    eff_sell = buy + spread_med
                    profit_real = eff_sell * (1 - tax - broker) - buy * (1 + broker)
                    roi_real = profit_real / buy * 100
                    spread_capped = True
                    if profit_unit > 0:
                        score *= max(0.10, max(0.0, profit_real) / profit_unit)
                # ---- D3 ZYKLUSDAUER: wie lange steht dein Kapital je Flip in
                # der Warteschlange? Buchtiefe je Seite geteilt durch den
                # Tagesdurchsatz, der die jeweilige Seite BEWEISBAR erreicht
                # (Buy-/Sell-Beleg). Grobe, ehrliche Schätzung.
                _thr_b = daily_vol * max(0.05, buy_reach)
                _thr_s = daily_vol * max(0.05, sell_reach)
                t_buy = (s.get("buy_qty", 0) or 0) / _thr_b if _thr_b > 0 else 99.0
                t_sell = (s.get("sell_qty", 0) or 0) / _thr_s if _thr_s > 0 else 99.0
                cycle_days = min(99.0, t_buy + t_sell)
                score *= max(0.15, 1.0 / (1.0 + max(0.0, cycle_days - 1.0) / 4.0))
                # ---- D2 BEST-ORDER-TIEFE (nur wenn der Snapshot die Daten
                # schon hat; 0 = alter Snapshot -> nicht filtern)
                _mbd = filters.get("min_best_depth", 0) or 0
                if _mbd:
                    _sbq = s.get("sell_best_qty", 0) or 0
                    _bbq = s.get("buy_best_qty", 0) or 0
                    if (_sbq and _sbq < _mbd) or (_bbq and _bbq < _mbd):
                        _d("best_depth_thin")
                        continue
            elif mode == "under":
                if min_hist_days and st["n"] < min_hist_days:
                    _d("hist_too_short")
                    continue  # too few history points → unreliable normal level
                ts = trend_stats(hist, days)
                normal = ts["normal"] or avg
                trend = ts["trend"]
                trend_pct = ts["trend_pct"]
                # ---- S3 AUSREISSER-FESTER NORMALPREIS (Nutzer-Fall): liegt im
                # Fenster gerade die Abkling-Phase eines Spikes, ist der
                # Fenster-Median nach OBEN verzerrt - das Tool hielt den ganz
                # normalen Jahrespreis für ein Riesen-Schnäppchen. Gegen die
                # lange Basislinie (Median der vollen Historie) absichern:
                # Normal = min(Fenster-Normal, Basislinie + 5 %).
                long_norm = long_baseline(hist)
                spike_distorted = bool(long_norm > 0 and normal > long_norm * 1.25)
                if long_norm > 0:
                    normal = min(normal, long_norm * 1.10)
                under_pct = ((normal - sell) / normal * 100) if normal else 0
                if under_pct < min_margin:
                    _d("below_min_margin")
                    continue
                if max_under and under_pct > max_under:
                    _d("under_too_deep")
                    continue  # 99%-below "dips" are data artefacts, not real
                if avoid_falling and trend == "falling":
                    _d("falling_skipped")
                    continue
                # consistency: a huge gap below "normal" while the trend points up
                # is contradictory data → skip
                if under_pct > 50 and trend == "rising":
                    _d("contradictory")
                    continue
                # ---- S2 DUMP-VERDACHT: Preissturz bei MASSIV erhöhtem Volumen
                # ist oft eine echte Neubewertung (Patch/Meta) - der alte Preis
                # kommt nicht zurück. Sturz bei normalem Volumen = klassische
                # Swing-Chance. Letzte 7 aktive Tage vs. Median-Volumen.
                # Kein Fenster-Trend-Kriterium: ein scharfer 8-Tage-Sturz am
                # Ende eines 90-Tage-Fensters liest sich in der Regression als
                # "sideways". Unter Normal IST das Item hier ohnehin - das
                # Massen-Volumen der letzten Tage allein ist das Dump-Signal.
                _recent_v = [r.get("volume") or 0 for r in hist[-10:]
                             if (r.get("volume") or 0) > 0][-7:]
                _vmed = st.get("vol_med", 0.0) or 0.0
                dump_risk = bool(_vmed > 0 and _recent_v
                                 and (sum(_recent_v) / len(_recent_v)) >= 2.5 * _vmed)
                target_sell = normal
                exp_profit = normal * (1 - tax - broker) - sell  # buy at sell, sell at normal
                exp_pct = (exp_profit / sell * 100) if sell else 0
                if exp_profit <= 0:
                    _d("exp_nonpositive")
                    continue
                if min_expected and exp_pct < min_expected:
                    _d("exp_pct_low")
                    continue
                # ---- S1 ERHOLUNGSDAUER: wie lange dauerte die Rückkehr nach
                # vergleichbaren Dips historisch? Erwarteter ISK/Tag =
                # Gewinn / Dauer - ein flacher 5-Tage-Dip schlägt damit den
                # tiefen 60-Tage-Dip, statt umgekehrt.
                recovery_days = recovery_days_estimate(hist, normal, sell)
                exp_day = (exp_profit / recovery_days) if recovery_days > 0 else 0.0
                score = exp_pct
                recovery = recovery_factor(trend, trend_pct)   # Erholung gewichten
                score *= recovery
                if recovery_days > 0:
                    score *= min(2.0, 14.0 / max(3.0, recovery_days))
                if dump_risk:
                    score *= 0.4
            elif mode == "underbuild":
                # BUYER's view: das Item notiert UNTER dem Effizienz-Boden
                # (Baukosten des Best-Case-Produzenten, s. UI-Helper
                # _efficiency_floor_build_opts) - unter dem baut niemand
                # dauerhaft, also erholt sich der Preis Richtung Boden.
                # Trichter-Zähler wie im 'under'-Modus, damit die
                # Diagnosezeile auch hier erklärt, wo Kandidaten bleiben.
                if recipes is None:
                    _d("no_recipes")         # war ein stiller Abbruch
                    continue
                if not _producible(s["type_id"]):
                    _d("not_manufactured")   # war ein stiller Abbruch
                    continue
                build_c = industry.build_cost(s["type_id"], price_fn, recipes,
                                              build_opts or {}, build_memo,
                                              parts_memo=build_parts)
                if not build_c or build_c <= 0:
                    _d("no_build_cost")
                    continue
                under_vs_build = ((build_c - sell) / build_c * 100.0) if build_c else 0
                under_pct = under_vs_build         # reuse for display
                if under_vs_build < min_margin:
                    _d("below_min_margin")
                    continue                       # nicht nennenswert unterm Boden
                normal = build_c
                target_sell = build_c              # reversion target = efficiency floor
                exp_profit = build_c * (1 - tax - broker) - sell
                exp_pct = (exp_profit / sell * 100.0) if sell else 0
                if exp_profit <= 0:
                    _d("exp_nonpositive")
                    continue
                if min_expected and exp_pct < min_expected:
                    _d("exp_pct_low")
                    continue
                # a rising trend confirms the recovery; falling means still sinking
                ts = trend_stats(hist, days)
                trend = ts["trend"]
                trend_pct = ts["trend_pct"]
                if avoid_falling and trend == "falling":
                    _d("falling_skipped")
                    continue
                score = exp_pct
            elif mode == "build":
                if recipes is None:
                    _d("no_recipes")         # war ein stiller Abbruch
                    continue
                # only real manufactured end-products (no ore/reaction/NPC-drop)
                if not _producible(s["type_id"]):
                    _d("not_manufactured")   # war ein stiller Abbruch
                    continue
                build_c = industry.build_cost(s["type_id"], price_fn, recipes,
                                              build_opts or {}, build_memo,
                                              parts_memo=build_parts)
                if not build_c or build_c <= 0:
                    _d("no_build_cost")
                    continue
                # a BUILDER's view: is it profitable to manufacture and sell?
                # revenue = sell price minus selling fees; profit vs build cost.
                net_sell = sell * (1 - tax - broker)
                build_profit = net_sell - build_c
                build_margin = (build_profit / build_c * 100) if build_c else 0
                under_pct = build_margin       # reused for display
                # Grenzfälle (nahe der Marge-Schwelle) NICHT sofort verwerfen -
                # die kommen erst mal mit rein, weil die schnelle Pro-Stück-
                # Schätzung Losgrößen-Effekte (Reaktions-Überschuss, Job-Kosten-
                # Verteilung über echte Bau-Runs) nicht kennt und sie deshalb zu
                # pessimistisch einschätzen kann. Ein zweiter, genauerer
                # Rechenschritt NACH der Hauptschleife prüft nur diese wenigen
                # Grenzfälle nach - der ganz überwiegende Rest bleibt bei der
                # schnellen Schätzung (Performance).
                needs_refine = min_margin - _BORDERLINE_MARGIN_WINDOW <= build_margin < min_margin + _BORDERLINE_MARGIN_WINDOW
                if build_margin < min_margin - _BORDERLINE_MARGIN_WINDOW:
                    _d("below_margin")
                    continue
                profit_unit = build_profit
                score = build_margin
                # Bauzeit pro Stück (Sekunden) + ISK/Std. Gemeinsames Memo über
                # den ganzen Scan-Batch, damit das günstig bleibt.
                try:
                    secs_unit = industry.build_time_per_unit(
                        s["type_id"], price_fn, recipes, build_opts or {},
                        build_time_memo, build_memo)
                except Exception:
                    secs_unit = 0.0
                build_hours = secs_unit / 3600.0 if secs_unit > 0 else 0.0
                isk_per_hour = (build_profit / build_hours) if build_hours > 0 else 0.0
                # WICHTIG: "Gewinn/Tag" war bisher Gewinn/Stk × GESAMTES
                # Tagesvolumen des Marktes - das unterstellt, du beliefertest
                # an einem Tag 100% des Marktes, unabhängig von deiner echten
                # Baukapazität (Slots/Bauzeit). Realistischer: an deiner
                # eigenen Baugeschwindigkeit (ISK/Std × 24h) orientieren, NICHT
                # am Marktvolumen. Nur wenn die Bauzeit gar nicht ermittelbar
                # ist (secs_unit=0, z.B. fehlende SDE-Zeitdaten), bleibt die
                # alte Volumen-Schätzung als einzig verfügbarer Anhaltspunkt.
                if build_hours > 0:
                    profit_day = isk_per_hour * 24.0
                    # trotzdem nie mehr, als der Markt überhaupt täglich abnimmt
                    # (sonst baut man an der Nachfrage vorbei)
                    profit_day = min(profit_day, build_profit * daily_vol) \
                        if daily_vol else profit_day
                else:
                    profit_day = build_profit * daily_vol
            else:  # drop = sudden crash vs recent baseline + volume spike
                rows = hist[-days:] if days else hist
                if len(rows) < 6:
                    continue
                base = [r["average"] for r in rows[:-3] if r["average"]]
                base_avg = sum(base) / len(base) if base else 0
                vb = [r["volume"] or 0 for r in rows[:-3]]
                vr = [r["volume"] or 0 for r in rows[-3:]]
                vol_base = (sum(vb) / len(vb)) if vb else 0
                vol_recent = (sum(vr) / len(vr)) if vr else 0
                spike = (vol_recent / vol_base) if vol_base else 1.0
                drop = ((base_avg - sell) / base_avg * 100) if base_avg else 0
                under_pct = drop
                # erwarteter Gewinn bei Erholung zur Vor-Crash-Basis (wie under-Modus)
                target_sell = base_avg
                exp_profit = base_avg * (1 - tax - broker) - sell
                exp_pct = (exp_profit / sell * 100.0) if sell else 0
                if drop < min_margin:
                    continue
                score = drop
                # Trend für Recovery-Gewichtung + Anzeige (drop hatte bisher keinen)
                ts = trend_stats(hist, days)
                trend = ts["trend"]; trend_pct = ts["trend_pct"]
                recovery = recovery_factor(trend, trend_pct)
                score *= recovery

            # absoluter Gewinn-Boden (nur Swing): killt Cent-Items mit toller %-Marge
            # aber winzigem ISK-Gewinn (die Daytrade-„25-ISK“-Lektion in Swing-Form)
            if mode != "flip" and min_expected_isk and exp_profit < min_expected_isk:
                _d("exp_isk_low")
                continue
            if min_sell_fill and sell_fill < min_sell_fill:
                _d("sell_fill_low")
                continue
            # Aufschluesselung dieses Items (nur in den Bau-Modi gefuellt).
            _bp_parts = build_parts.get(s["type_id"]) or {}
            _fallback_pct = ((_bp_parts.get("mat_adjusted", 0.0) / build_c * 100.0)
                             if (_bp_parts and build_c) else 0.0)
            _inv_saved_unit = _bp_parts.get("inv_saved", 0.0)
            results.append({
                "type_id": s["type_id"],
                "buy_max": buy,
                "sell_min": sell,
                "avg": avg,
                "under_pct": under_pct,
                "sell_fill": sell_fill,
                "profit_unit": profit_unit,
                "roi": roi,
                "daily_vol": daily_vol,
                "vol_unknown": vol_unknown,
                "dos": dos,
                "profit_day": profit_day,
                "capture_day": capture_day if mode == "flip" else profit_day,
                "build_hours": build_hours,
                "isk_per_hour": isk_per_hour,
                "competitors": competitors,
                "sell_orders_n": n_sell,
                "buy_orders_n": n_buy,
                "capital": capital,
                # capital efficiency: daily (competition-adjusted) profit per ISK
                # tied up, as % per day. 2%/day on bound capital beats a bigger
                # absolute profit that locks up ten times the ISK.
                "cap_eff": (capture_day / capital * 100.0) if capital else 0.0,
                "volatility": volatility,
                "spike": spike,
                "trade_score": trade_score,
                "active_ratio": st.get("active_ratio", 0.0),
                "txn_day": st.get("txn_day", 0.0),
                "day_range_pct": st.get("day_range_pct", 0.0),
                "both_sides_ratio": st.get("both_sides_ratio", 0.0),
                "buy_reach": buy_reach,
                "sell_reach": sell_reach,
                "two_sided": two_sided,
                "spread_med_isk": st.get("spread_med_isk", 0.0),
                "profit_real": profit_real,
                "roi_real": roi_real,
                "spread_capped": spread_capped,
                "cycle_days": cycle_days,
                "long_normal": long_norm,
                "spike_distorted": spike_distorted,
                "dump_risk": dump_risk,
                "recovery_days": recovery_days,
                "exp_day": exp_day,
                "build_cost": build_c,
                # BEIDE Zahlen stammen aus DERSELBEN Rechnung wie build_cost
                # (parts_memo), nicht aus einer Nebenrechnung.
                # fallback_pct: Anteil der Baukosten, der nur ueber den
                #   Adjusted-Price-Rueckfall bepreist ist (kein Angebot am Hub)
                #   -> je hoeher, desto weniger belastbar ist der Treffer.
                # inv_saved_unit: Invention/Stk, die NICHT berechnet wurde,
                #   weil eigene BPCs/BPOs vorliegen (ausweisen, nicht verstecken).
                "fallback_pct": _fallback_pct,
                "inv_saved_unit": _inv_saved_unit,
                "build_profit": build_profit,
                "needs_refine": needs_refine if mode == "build" else False,
                "sell_orders": s["sell_orders"],
                "flip_margin": roi,
                "normal": normal,
                "trend": trend,
                "recovery": recovery,        # Swing: Erholungs-Gewichtung (0.25–1.0)
                "trend_pct": trend_pct,
                "over_norm_pct": over_norm * 100.0,   # aktueller Preis über Normal (%)
                "target_sell": target_sell,
                "exp_profit": exp_profit,
                "exp_pct": exp_pct,
                "score": score,
            })
    finally:
        ex.shutdown(wait=False)
    if diag is not None:
        diag["rate_limited_hits"] = _state["rl_hits"]
        diag["fetch_stopped"] = _state["stop_fetch"]
        diag["analyzed"] = total
        diag["passed"] = len(results)   # vor Sortierung/max_items-Deckel

    if mode == "build" and recipes is not None:
        # Stufe 2: nur die Grenzfälle (needs_refine) genau nachrechnen, mit
        # einer realistischen Losgröße statt der reinen Pro-Stück-Schätzung -
        # rettet Items, die die schnelle Schätzung fälschlich als "nicht
        # gewinnbringend" verworfen hätte (fehlender Reaktions-Überschuss/
        # Job-Kosten-Verteilung bei kleiner Stückzahl), und wirft welche
        # wieder raus, die die schnelle Schätzung fälschlich durchgelassen hat.
        refined = []
        for r in results:
            bp = recipes.product_to_bp.get(r["type_id"])
            bp_id = bp[0] if bp else None
            needs_invention = bool(bp_id and recipes.invention_for_bpc.get(bp_id))
            if needs_invention:
                # Invention-Items NICHT mit production_plan() nachrechnen: die
                # nutzt dort die ≥75%-Sicherheits-Versuche-Formel (viele
                # Versuche vorab abgesichert), während build_cost() den reinen
                # Erwartungswert nimmt - bei kleinen Losgrößen weicht das stark
                # ab und hätte fast alle T2/T3-Items fälschlich als
                # unprofitabel verworfen. ABER: "needs_refine" heißt nur "lag
                # im Grenzfall-Fenster um die Marge-Schwelle" (bis zu 15 Punkte
                # DARUNTER) - das war fälschlich als "gut genug" durchgelassen
                # worden, ohne die schnelle Schätzung je gegen min_margin zu
                # prüfen. Genau das hat T3-Subsystem-Items mit negativer Marge
                # (z.B. Loki/Legion/Proteus-Subsysteme) unbemerkt durchrutschen
                # lassen. Jetzt: schnelle Schätzung bleibt, aber die
                # Marge-Schwelle gilt trotzdem.
                if r["under_pct"] < min_margin:
                    # WAR EIN STILLER ABBRUCH - und ausgerechnet der, der bei
                    # T2/T3 fast immer greift (jedes Invention-Item laeuft
                    # hier durch). Die Trichterzeile meldete deshalb "0 unter
                    # Marge", obwohl genau hier die Kandidaten starben.
                    _d("below_margin_refine")
                    continue
                refined.append(r)
                continue
            if not r.get("needs_refine"):
                refined.append(r)
                continue
            try:
                qty = _realistic_build_qty(r["sell_min"])
                plan = industry.production_plan(r["type_id"], qty, price_fn,
                                                 recipes, build_opts or {})
                total_cost = float(plan.get("total_cost", 0.0) or 0.0)
                if total_cost <= 0:
                    refined.append(r)
                    continue
                per_unit_cost = total_cost / qty
                net_sell = r["sell_min"] * (1 - tax - broker)
                build_profit = net_sell - per_unit_cost
                build_margin = (build_profit / per_unit_cost * 100) if per_unit_cost else 0
                if build_margin < min_margin:
                    _d("below_margin_refine")   # war ein stiller Abbruch
                    continue   # nach genauer Rechnung doch nicht profitabel genug
                r = dict(r)
                r["build_cost"] = per_unit_cost
                # Der Rueckfall-Anteil MUSS aus derselben Rechnung stammen wie
                # die Kosten daneben - sonst stuende hier der Anteil aus der
                # verworfenen Schnellschaetzung (Arbeitsregel 10).
                r["fallback_pct"] = (float(plan.get("mat_cost_adjusted", 0.0) or 0.0)
                                     / total_cost * 100.0)
                r["build_profit"] = build_profit
                r["profit_unit"] = build_profit
                r["under_pct"] = build_margin
                r["score"] = build_margin
                if r.get("build_hours", 0) > 0:
                    r["isk_per_hour"] = build_profit / r["build_hours"]
                    r["profit_day"] = min(r["isk_per_hour"] * 24.0,
                                          build_profit * r["daily_vol"]) \
                        if r["daily_vol"] else r["isk_per_hour"] * 24.0
                else:
                    r["profit_day"] = build_profit * r["daily_vol"]
                r["refined_qty"] = qty   # zur Transparenz in der UI
                refined.append(r)
            except Exception:
                refined.append(r)   # bei Fehler: schnelle Schätzung behalten
        results = refined

    results.sort(key=lambda r: r["score"], reverse=True)
    if diag is not None and len(results) > cap:
        # KEIN Qualitaetsfilter, sondern der reine Anzeige-Deckel (max_items).
        # Muss trotzdem in den Trichter, sonst stimmt die Invariante nicht -
        # genau diese 15 Kandidaten hat die neue Zeile beim Nutzer gemeldet
        # ("nicht zugeordnet"), und genau dafuer ist sie da.
        diag["over_cap"] = diag.get("over_cap", 0) + (len(results) - cap)
    return results[:cap]


def contract_ship_price(price, included, capital_type_ids,
                        extra_price_fn=None):
    """Schiffspreis EINES Contracts -> (type_id, preis, ist_bundle) oder None.

    NUTZER-FUND (Sitzung 8): Supercarrier/Titanen stehen fast NUR als
    "[Multiple Items]"-Bundles in den Contracts (Schiff + Rigs + Fuel) - der
    alte Scan verwarf alles mit mehr als einem Item und meldete dann
    "kein Contract-Preis", obwohl der Markt existiert.
    Jetzt: der Bundle-Preis MINUS dem Jita-Verkaufswert der Beilagen ist der
    abgeleitete Schiffspreis. HARTE Grenzen, damit keine Fantasiepreise
    entstehen (Regel 6 - lieber ehrlich None als geraten):
      * GENAU EIN Capital im Contract, Stueckzahl 1 (zwei Schiffe oder
        5x Fuel-Block-Bundles sind nicht eindeutig zuordenbar).
      * JEDE Beilage braucht einen Marktpreis > 0 (BPCs & Co. haben keinen
        -> Bundle nicht ableitbar).
      * Der abgeleitete Preis muss > 0 bleiben (Beilagen teurer als der
        Contract = Datenmuell).
      * OHNE extra_price_fn (keine Preisquelle, z. B. kein Markt-Scan)
        gilt das ALTE Verhalten: Bundles zaehlen nicht.
    Pur (kein Netz, kein Qt) - deshalb direkt testbar."""
    caps = [it for it in (included or [])
            if it.get("type_id") in capital_type_ids]
    if len(caps) != 1 or int(caps[0].get("quantity") or 1) != 1:
        return None
    tid = caps[0].get("type_id")
    extras = [it for it in included if it is not caps[0]]
    if not extras:
        return tid, float(price), False
    if extra_price_fn is None:
        return None
    wert = 0.0
    for it in extras:
        try:
            p_it = float(extra_price_fn(it.get("type_id")) or 0)
        except (TypeError, ValueError):
            p_it = 0.0
        if p_it <= 0:
            return None
        wert += p_it * int(it.get("quantity") or 1)
    abgeleitet = float(price) - wert
    if abgeleitet <= 0:
        return None
    return tid, abgeleitet, True


def aggregate_contract_prices(prices_by_type, bundles_by_type=None):
    """{tid: [Preise]} -> {tid: {median, mean, min, max, count}} (pur, ohne
    Netz - deshalb testbar). MEDIAN bleibt der Richtwert, den die Oberflaeche
    zeigt: Contract-Preise haben regelmaessig Ausreisser nach oben (hoffnungs-
    volle Verkaeufer, Scam-Preise), und EIN Fantasiepreis wuerde einen
    Mittelwert spuerbar verziehen, den Median aber nicht. Der Mittelwert wird
    trotzdem mitgerechnet und angezeigt (Nutzer sprach von "Durchschnitt") -
    beide nebeneinander zeigen ehrlich, wie einig sich der Markt ist."""
    import statistics
    out = {}
    for tid, prices in (prices_by_type or {}).items():
        vals = [float(p) for p in prices if p is not None and float(p) > 0]
        if not vals:
            continue
        out[tid] = {"median": statistics.median(vals),
                    "mean": statistics.fmean(vals),
                    "min": min(vals), "max": max(vals), "count": len(vals),
                    # Ehrlich mitfuehren, wie viele der Preise aus Bundles
                    # ABGELEITET sind (Beilagen zum Jita-Preis abgezogen).
                    "from_bundles": int((bundles_by_type or {}).get(tid, 0))}
    return out


def scan_capital_contract_prices_all_regions(capital_type_ids, region_ids=None,
                                             should_cancel=None, progress=None,
                                             extra_price_fn=None):
    """Wie scan_capital_contract_prices, aber ueber GANZ NEW EDEN (Nutzer:
    "den Durchschnitts-Contract-Preis von ganz New Eden"). Capitals werden
    ueberall verkauft, nicht nur im Hub - ein Ein-Regionen-Scan liefert fuer
    viele Typen gar keinen oder nur einen einzigen Preis.

    Die Preise ALLER Regionen wandern in EINEN Topf und werden erst am Ende
    zusammengefasst (nicht je Region gemitteln und dann die Mittelwerte
    mitteln - das gewichtet eine Region mit 1 Contract genauso stark wie
    eine mit 40). Regionen-Listen werden parallel geholt, die teuren
    Item-Abrufe danach - genau wie beim Ein-Regionen-Scan."""
    import concurrent.futures as _cf
    if region_ids is None:
        region_ids = esi.fetch_region_ids()
    region_ids = list(region_ids or [])
    candidates = []
    done_n = 0
    with _cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(esi.fetch_public_contracts, rid,
                          200_000_000, 50_000, should_cancel): rid
                for rid in region_ids}
        for f in _cf.as_completed(futs):
            done_n += 1
            if progress:
                # Erste Haelfte des Fortschritts: die Regionen-Listen.
                progress(done_n, max(1, len(region_ids) * 2))
            if should_cancel and should_cancel():
                break
            try:
                candidates.extend(f.result() or [])
            except Exception:
                continue          # eine stumme Region darf den Rest nicht kippen
    prices_by_type = {}
    bundles_by_type = {}
    total = max(1, len(candidates))
    for i, ct in enumerate(candidates):
        if should_cancel and should_cancel():
            break
        try:
            items = esi.fetch_contract_items(ct["contract_id"])
        except Exception:
            continue
        included = [it for it in items if it.get("is_included", True)]
        hit = contract_ship_price(ct["price"], included, capital_type_ids,
                                  extra_price_fn)
        if hit:
            tid, preis, ist_bundle = hit
            prices_by_type.setdefault(tid, []).append(preis)
            if ist_bundle:
                bundles_by_type[tid] = bundles_by_type.get(tid, 0) + 1
        if progress:
            progress(len(region_ids) + int((i + 1) / total * len(region_ids)),
                     max(1, len(region_ids) * 2))
    return aggregate_contract_prices(prices_by_type, bundles_by_type)


def scan_capital_contract_prices(region_id, capital_type_ids, should_cancel=None,
                                 progress=None, extra_price_fn=None) -> dict:
    """Grober Verkaufspreis-Richtwert für Capital-Schiffe aus öffentlichen ESI-
    Contracts (Capitals haben praktisch nie echte Marktorders in Jita, siehe
    industry.capital_ship_products()). Zwei Schritte:
      1. Alle öffentlichen "Item Exchange"-Contracts der Region holen, aber SOFORT
         nach Preis/Volumen grob vorfiltern (Capitals sind riesig UND teuer) -
         Contracts, die eh nicht in Frage kommen, kosten so keinen einzigen
         zusätzlichen Abruf.
      2. Nur für die übrig gebliebenen Kandidaten die tatsächlichen Items
         abrufen - Contracts mit MEHR als einem Item (Fittings/Rigs dabei)
         werden verworfen, weil sich der Preis dann nicht mehr eindeutig dem
         Schiff allein zuordnen lässt.
    Rückgabe: {type_id: {"median": x, "min": x, "max": x, "count": n}} - nur für
    Typen, zu denen mindestens ein sauberer Einzel-Item-Contract gefunden wurde."""
    candidates = esi.fetch_public_contracts(
        region_id, min_price=200_000_000, min_volume=50_000,
        should_cancel=should_cancel)
    prices_by_type = {}
    bundles_by_type = {}
    total = len(candidates)
    for i, ct in enumerate(candidates):
        if should_cancel and should_cancel():
            break
        try:
            items = esi.fetch_contract_items(ct["contract_id"])
        except Exception:
            continue
        included = [it for it in items if it.get("is_included", True)]
        hit = contract_ship_price(ct["price"], included, capital_type_ids,
                                  extra_price_fn)
        if hit:
            tid, preis, ist_bundle = hit
            prices_by_type.setdefault(tid, []).append(preis)
            if ist_bundle:
                bundles_by_type[tid] = bundles_by_type.get(tid, 0) + 1
        if progress:
            progress(i + 1, total)
    return aggregate_contract_prices(prices_by_type, bundles_by_type)


def firesale_bewertung(ct, items, preis_fn):
    """Bewertet EINEN oeffentlichen Item-Exchange-Contract gegen den Markt
    (emm413, Discord Str1k3r2k4: "verfuegbare Contracts ... mit den
    aktuellen Marktpreisen vergleichen"). Rein und testbar.

    REGEL 3 / SCAM-SCHUTZ - die drei klassischen Contract-Fallen:
      * BPCs (is_blueprint_copy) haben KEINEN Marktpreis und sind der
        haeufigste Fueller wertloser "Schnaeppchen" -> zaehlen 0, werden
        gezaehlt (bpc_n) und in der Zeile angesagt.
      * Items ohne Marktpreis (preis_fn liefert 0/None) zaehlen 0 und
        stehen in `no_price` - der Contract sieht dadurch hoechstens
        SCHLECHTER aus, nie besser.
      * `verlangt=True`: der Contract FORDERT Items vom Kaeufer
        (is_included False) - typisches Tausch-/Scam-Muster; gewinn ist
        dann None (nicht bewertbar), der Aufrufer sortiert ihn aus.

    Rueckgabe: {preis, wert, gewinn, rabatt_pct, enthalten:[(tid, qty)],
    bpc_n, unbekannt:[tid], verlangt, volumen, contract_id, date_issued,
    title}."""
    preis = float(ct.get("price") or 0)
    enthalten = []
    wert = 0.0
    bpc_n = 0
    unbekannt = []
    verlangt = False
    for it in (items or []):
        tid = int(it.get("type_id") or 0)
        qty = int(it.get("quantity") or 0)
        if not it.get("is_included", True):
            verlangt = True
            continue
        if tid <= 0 or qty <= 0:
            continue
        enthalten.append((tid, qty))
        if it.get("is_blueprint_copy"):
            bpc_n += 1
            continue                      # BPC: Marktwert 0, nie schaetzen
        try:
            p = float(preis_fn(tid) or 0)
        except Exception:
            p = 0.0
        if p > 0:
            wert += p * qty
        elif tid not in unbekannt:
            unbekannt.append(tid)
    gewinn = None if verlangt else (wert - preis)
    rabatt = ((gewinn / wert * 100.0)
              if (gewinn is not None and wert > 0) else None)
    return {"preis": preis, "wert": wert, "gewinn": gewinn,
            "rabatt_pct": rabatt, "enthalten": enthalten, "bpc_n": bpc_n,
            "no_price": unbekannt, "verlangt": verlangt,
            "volumen": float(ct.get("volume") or 0),
            "contract_id": int(ct.get("contract_id") or 0),
            "date_issued": str(ct.get("date_issued") or ""),
            "title": str(ct.get("title") or ""),
            # Ort des Contracts (emm421): Station oder Struktur-ID.
            "ort_id": int(ct.get("start_location_id") or 0)}


def scan_firesales(region_id, preis_fn, min_preis=1_000_000,
                   max_contracts=300, should_cancel=None, progress=None):
    """Firesales-Scan (emm413): oeffentliche Item-Exchange-Contracts einer
    Region gegen die Marktpreise des letzten Scans bewerten.

    DECKEL, ehrlich angesagt: die Contract-Liste verraet die Items nicht,
    je Contract kostet der Inhalt einen EIGENEN Abruf (The Forge hat
    tausende). Geprueft werden deshalb hoechstens `max_contracts`, die
    JUENGSTEN zuerst (alte Schnaeppchen sind laengst weg); die Rueckgabe
    nennt gesamt/geprueft/fehler, die Oberflaeche sagt es dazu.

    Rueckgabe: {"zeilen": [firesale_bewertung...], "gesamt": n,
    "geprueft": n, "fehler": n}."""
    cts = esi.fetch_public_contracts(
        region_id, min_price=max(0, float(min_preis or 0)),
        should_cancel=should_cancel)
    gesamt = len(cts)
    cts.sort(key=lambda c: str(c.get("date_issued") or ""), reverse=True)
    cts = cts[:max(1, int(max_contracts or 1))]
    zeilen = []
    roh = []
    fehler = 0
    done_n = 0
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(esi.fetch_contract_items, c["contract_id"]): c
                for c in cts if c.get("contract_id")}
        for f in cf.as_completed(futs):
            done_n += 1
            if progress:
                progress(done_n, max(1, len(futs)))
            if should_cancel and should_cancel():
                break
            try:
                items = f.result() or []
            except Exception:
                fehler += 1              # ein stummer Contract kippt nichts
                continue
            zeilen.append(firesale_bewertung(futs[f], items, preis_fn))
            roh.append((futs[f], items))
    # `roh` (emm421): Contract + Inhalt, damit die Oberflaeche OHNE neuen
    # Abruf auf eine andere Wertbasis umrechnen kann (Sell/Buy).
    return {"zeilen": zeilen, "roh": roh, "gesamt": gesamt,
            "geprueft": len(zeilen), "fehler": fehler}


def firesale_orte(ort_ids, start_system, ort_fn, system_fn, route_fn,
                  max_workers=8):
    """Ort, Sicherheit und Spruenge je Contract-Ort (emm421, Nutzer: "Ort +
    Spruenge"). Rein bis auf die uebergebenen Abruf-Funktionen:
      ort_fn(location_id)  -> {"name", "system_id"} oder None (Struktur
                              ohne Andockrecht: None)
      system_fn(system_id) -> {"name", "security"}
      route_fn(a, b)       -> Spruenge oder None
    Je ORT ein Abruf, je SYSTEM ein Info- und ein Routen-Abruf (parallel).
    Ein Fehler kippt nie den Rest - unbekannt bleibt None.
    Rueckgabe: {ort_id: {"name", "system", "sec", "spruenge"}}."""
    ids = sorted({int(i) for i in (ort_ids or ()) if i})
    orte = {}

    def _ort(i):
        try:
            return i, (ort_fn(i) or {})
        except Exception:
            return i, {}
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for i, o in ex.map(_ort, ids):
            orte[i] = o
    systeme = sorted({int(o.get("system_id")) for o in orte.values()
                      if o.get("system_id")})
    info, spr = {}, {}

    def _sys(s):
        try:
            inf = system_fn(s) or {}
        except Exception:
            inf = {}
        try:
            j = route_fn(start_system, s) if start_system else None
        except Exception:
            j = None
        return s, inf, j
    with cf.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for s, inf, j in ex.map(_sys, systeme):
            info[s] = inf
            spr[s] = j
    out = {}
    for i in ids:
        o = orte.get(i) or {}
        s = int(o.get("system_id") or 0)
        inf = info.get(s) or {}
        out[i] = {"name": o.get("name") or None,
                  "system": inf.get("name"),
                  "sec": inf.get("security"),
                  "spruenge": spr.get(s) if s else None}
    return out
