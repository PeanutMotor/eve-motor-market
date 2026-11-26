"""Regional / structure arbitrage: compare two trade locations and find items
that are cheaper at the source than they sell for at the target."""
import concurrent.futures as cf


from . import config, esi

_UA = {"User-Agent": "MotorMarket/0.1"}

# DIE 401/403-MELDUNG ALS SCHLUESSEL, NICHT ALS WORTLAUT.
# Bis Sitzung 22 stand in main_window `if "Kein Zugriff" in str(msg)` - und
# `msg` ist der bereits UEBERSETZTE Text. Auf der englischen Oberflaeche
# heisst er "No access to the order book of ...", die Bedingung traf also
# nie zu und die Neupruefung der Struktur lief dort NIE an. Wer eine
# uebersetzte Meldung spaeter wiedererkennen will, muss ueber den Katalog
# gehen - genau das macht `ist_zugriffsfehler`.
KEIN_ZUGRIFF_SCHLUESSEL = (
    "No access to the order book of „{name}“ with the linked "
    "character (check docking/market rights or the token).")


def ist_zugriffsfehler(text):
    """Stammt diese Fehlermeldung aus dem 401/403-Fall? Sprachunabhaengig:
    verglichen wird der Textanfang VOR dem Platzhalter, in beiden
    Fassungen - englischer Schluessel und deutscher Katalogeintrag."""
    from .sprache import KATALOG
    _de = KATALOG.get("de", {}).get(KEIN_ZUGRIFF_SCHLUESSEL,
                                    KEIN_ZUGRIFF_SCHLUESSEL)
    _vorn = [s.split("{name}")[0].strip()
             for s in (KEIN_ZUGRIFF_SCHLUESSEL, _de)]
    return any(v and v in (text or "") for v in _vorn)

# Built-in NPC trade hubs: (key, label, region_id, station_id)
NPC_HUBS = [
    ("jita", "Jita (The Forge)", 10000002, 60003760),
    ("amarr", "Amarr (Domain)", 10000043, 60008494),
    ("dodixie", "Dodixie (Sinq Laison)", 10000032, 60011866),
    ("rens", "Rens (Heimatar)", 10000030, 60004588),
    ("hek", "Hek (Metropolis)", 10000042, 60005686),
]

# Station owner corp + faction per hub — these are the standings that reduce the
# broker fee at that hub (corp reduces 0.02%/pt, faction 0.03%/pt). Verified
# against EVE station ownership.
HUB_OWNERS = {
    "jita":    {"corp": "Caldari Navy",     "faction": "Caldari State"},
    "amarr":   {"corp": "Emperor Family",   "faction": "Amarr Empire"},
    "dodixie": {"corp": "Federation Navy",  "faction": "Gallente Federation"},
    "rens":    {"corp": "Brutor Tribe",     "faction": "Minmatar Republic"},
    "hek":     {"corp": "Boundless Creation", "faction": "Minmatar Republic"},
}


# ---------------------------------------------------------------------------
# ZUSAETZLICHE NPC-STATIONEN ALS HUB (emm952, Discord Robust 18.11.2026: "will
# we be allowed to add another NPC station to Hubs?"; Nutzer: "von Region auf
# Station wuerde generell Sinn machen" / "nicht dass wir da was kaputt machen").
#
# DIE HUB-NUMMER: fuer die fuenf festen Hubs bleibt sie die REGION (so stehen
# ihre Preise seit jeher in der Datenbank - "hub:10000002"; nichts wird
# umgeschluesselt, also kann nichts verloren gehen). Eine ZUSAETZLICHE Station
# traegt ihre STATIONS-Nummer (>= 60 Mio, Regionen liegen bei 10 Mio - die zwei
# Bereiche ueberschneiden sich nie). Damit koennen mehrere Stationen derselben
# Region nebeneinander stehen, ohne einander die Preise zu ueberschreiben.
# ---------------------------------------------------------------------------
STATION_AB = 60_000_000
EXTRA = []          # [(key, label, region_id, station_id)] - s. extra_setzen


def extra_setzen(liste) -> list:
    """Die zusaetzlichen NPC-Stationen aus den Einstellungen uebernehmen
    (`settings["npc_hubs_extra"]` = [{"station_id", "name", "region_id"}]).
    Kaputte Eintraege, die fuenf festen Hubs und Doppelte fallen weg."""
    del EXTRA[:]
    fest = {sid for _k, _l, _r, sid in NPC_HUBS}
    gesehen = set()
    for e in (liste or []):
        try:
            sid = int(e.get("station_id") or 0)
            rid = int(e.get("region_id") or 0)
        except (AttributeError, TypeError, ValueError):
            continue
        if sid < STATION_AB or rid <= 0 or sid in fest or sid in gesehen:
            continue
        gesehen.add(sid)
        EXTRA.append((f"st{sid}", str(e.get("name") or sid), rid, sid))
    return list(EXTRA)


def npc_hubs() -> list:
    """Feste Hubs + zusaetzliche Stationen, als (key, label, region, station)."""
    return list(NPC_HUBS) + list(EXTRA)


def aufloesen(hub_id):
    """Hub-Nummer -> (key, label, region, station) oder None. Stations-Nummer
    (fest ODER zusaetzlich) wird ueber die Station gefunden, eine Region ueber
    den festen Hub dieser Region."""
    try:
        n = int(hub_id)
    except (TypeError, ValueError):
        return None
    if n >= STATION_AB:
        for h in npc_hubs():
            if h[3] == n:
                return h
        return None
    for h in NPC_HUBS:
        if h[2] == n:
            return h
    return None


def ist_extra(hub_id) -> bool:
    try:
        n = int(hub_id)
    except (TypeError, ValueError):
        return False
    return any(h[3] == n for h in EXTRA)


def region_von(hub_id):
    """Die ECHTE Region einer Hub-Nummer (fuer Historie und Orderabruf).
    Unbekanntes bleibt, wie es ist - eine Region ist ihre eigene Antwort."""
    h = aufloesen(hub_id)
    if h is not None:
        return h[2]
    return hub_id


def hub_id_fuer(region_id, station_id):
    """Hub-Nummer eines NPC-Orts: zusaetzliche Station -> ihre Stations-Nummer,
    sonst (fester Hub, unbekannt) die Region wie bisher."""
    if station_id and ist_extra(station_id):
        return int(station_id)
    return region_id


def standings_key(hub_id):
    """`hub_standings`-Schluessel einer Hub-Nummer. Feste Hubs: ihr Schluessel
    (Region wie bisher ueber hub_key_for_region, samt "jita"-Rueckfall).
    ZUSAETZLICHE Station: None - fuer sie sind keine Standings hinterlegt,
    die Broker-Gebuehr rechnet dann OHNE Rabatt (lieber zu hoch als zu tief)."""
    try:
        n = int(hub_id)
    except (TypeError, ValueError):
        return "jita"
    if n >= STATION_AB:
        for key, _l, _r, sid in NPC_HUBS:
            if sid == n:
                return key
        return None
    return hub_key_for_region(n)


def hub_key_for_region(region_id: int) -> str:
    """Map a scan region back to its hub key (defaults to jita)."""
    for key, _label, rid, _sid in NPC_HUBS:
        if rid == region_id:
            return key
    return "jita"


def station_for_region(region_id: int) -> int:
    """The hub STATION for a scan region (so a scan can be limited to the actual
    trade hub, not the whole region). Defaults to Jita 4-4."""
    # Eine Hub-Nummer im Stationsbereich IST die Station (emm952).
    try:
        if int(region_id) >= STATION_AB:
            return int(region_id)
    except (TypeError, ValueError):
        pass
    for _key, _label, rid, sid in NPC_HUBS:
        if rid == region_id:
            return sid
    return NPC_HUBS[0][3]


def fetch_hub_orders(region_id: int, station_id: int, progress=None) -> dict:
    """Best buy/sell + on-book qty per type at a specific NPC station.
    Fehlgeschlagene Seiten werden NICHT still weggelassen (das hieße: falsche
    sell_min/buy_max im Vergleich) - erst Retry pro Seite (esi._get_with_retry),
    dann serieller Nachversuch, sonst harter Fehler."""
    url = f"{config.ESI_BASE}/markets/{region_id}/orders/"
    first = esi._get_with_retry(url, params={"order_type": "all", "page": 1},
                                headers=_UA, timeout=40)
    pages = int(first.headers.get("X-Pages", "1"))
    agg = {}

    def fold(orders):
        for o in orders:
            if o["location_id"] != station_id:
                continue
            tid = o["type_id"]
            a = agg.setdefault(tid, {"sell_min": 0.0, "buy_max": 0.0,
                                     "sell_qty": 0, "buy_qty": 0,
                                     "sell_orders": []})
            if o["is_buy_order"]:
                a["buy_qty"] += o["volume_remain"]
                a["buy_max"] = max(a["buy_max"], o["price"])
            else:
                a["sell_qty"] += o["volume_remain"]
                a["sell_min"] = o["price"] if a["sell_min"] == 0 else min(a["sell_min"], o["price"])
                a["sell_orders"].append((o["price"], o["volume_remain"]))

    fold(first.json())
    if progress:
        progress(1, pages)

    def get_page(p):
        r = esi._get_with_retry(url, params={"order_type": "all", "page": p},
                                headers=_UA, timeout=40)
        return r.json()

    failed_pages = []
    with cf.ThreadPoolExecutor(max_workers=16) as ex:
        futures = {ex.submit(get_page, p): p for p in range(2, pages + 1)}
        done = 1
        for fut in cf.as_completed(futures):
            try:
                fold(fut.result())
            except Exception:
                failed_pages.append(futures[fut])
            done += 1
            if progress:
                progress(done, pages)
    still_failed = []
    for p in sorted(failed_pages):
        try:
            fold(get_page(p))
        except Exception:
            still_failed.append(p)
    if still_failed:
        from .sprache import t as _txt
        raise RuntimeError(_txt(
            "Hub fetch incomplete: {n} of {pages} order book pages could not be "
            "loaded (e.g. page {p}) \u2013 the comparison would be distorted, "
            "please try again.").format(n=len(still_failed), pages=pages,
                                         p=still_failed[0]))
    return agg


def load_location_orders(loc: dict, settings, progress=None) -> dict:
    """loc is a favourite/hub dict: {kind:'hub'|'structure', ...}.
    WICHTIG: liefert für BEIDE Seiten dieselbe Form wie fetch_hub_orders -
    insbesondere sell_orders als PREISLEITER [(preis, menge), …]. Der alte
    Pfad nahm esi.fetch_structure_orders, dessen sell_orders eine ANZAHL
    (int) ist - hubs.arbitrage sortiert die Quell-Leiter und stürzte bei
    Struktur-QUELLE mit "'int' object is not iterable" ab (Nutzer-Fall
    X47L-Q -> 4-HWWF; NPC->Struktur lief nur, weil dort die NPC-Seite die
    Quelle war)."""
    if loc["kind"] == "hub":
        return fetch_hub_orders(loc["region_id"], loc["station_id"], progress)
    try:
        book = esi.fetch_structure_orders_full(
            settings["client_id"], loc["character_id"],
            loc["structure_id"], progress)
    except Exception as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        if code in (401, 403):
            from .sprache import t as _txt
            raise RuntimeError(_txt(KEIN_ZUGRIFF_SCHLUESSEL).format(
                    name=loc.get('name', loc['structure_id']))) from e
        raise
    return {tid: {"sell_min": b["sell_min"], "buy_max": b["buy_max"],
                  "sell_qty": b["sell_qty"], "buy_qty": b["buy_qty"],
                  "sell_orders": list(b["sell"])}
            for tid, b in book.items()}


def leere_zielmaerkte(source: dict, target: dict, deals: list, cap: int = 200) -> list:
    """Kandidaten fuer den Fall "am Ziel liegt NICHTS, obwohl dort gehandelt
    wird" - nach Quell-Wert sortiert, gedeckelt.

    NUTZER (Sitzung 16): "Falls der Zielhub ein Item gar nicht mehr hat, was
    passiert dann mit dem Tool? Eigentlich waere das eine wahre Goldgrube,
    ein Item was Handelsvolumen hat, aber der Markt leer ist. So etwas muss
    gefunden werden!"

    GEMESSEN, WARUM ES BISHER NICHT GEFUNDEN WURDE - `arbitrage` hat zwei
    harte Ausstiege:
      * `t = target.get(tid); if not t: continue`  -> Item am Ziel unbekannt
      * `if sell_price <= 0: continue`             -> keine Sell-Orders da
    Und `load_location_orders` baut das Ziel-Orderbuch AUS den vorhandenen
    Orders: ein Item ohne jede Order ist dort gar kein Eintrag. Genau der
    interessante Fall fiel also raus, BEVOR die Absatzpruefung begann.

    DIESE FUNKTION SUCHT NUR AUS, SIE BEWERTET NICHT. Ob am Ziel wirklich
    gehandelt wird, kann sie nicht wissen - das steht in der Markthistorie
    und wird vom Aufrufer geprueft. Sie liefert die type_ids, fuer die sich
    ein Historien-Abruf lohnt.

    RANGFOLGE nach `sell_min * min(sell_qty, 100)`: ein GROBER Stellvertreter
    fuer "wie viel Kapital koennte diese Luecke aufnehmen". Der echte Wert
    waere (Zielpreis - Quellpreis) x Menge - aber den Zielpreis gibt es ja
    gerade nicht, das ist der ganze Punkt. Die Deckelung bei 100 Stueck
    verhindert, dass ein einziger Riesenstapel billiger Ware die Liste
    belegt. Der Nutzer hat die Top 200 gewaehlt ("Scan bleibt schnell").
    """
    schon = {d.get("type_id") for d in (deals or [])}
    kandidaten = []
    for tid, s in (source or {}).items():
        if tid in schon:
            continue
        sell_min = s.get("sell_min") or 0
        if sell_min <= 0:
            continue                      # in der Quelle gar nicht kaufbar
        t = (target or {}).get(tid)
        # NUR WIRKLICH LEERE ZIELE. Liegt dort eine Sell-Order, ist es der
        # normale Fall und `arbitrage` hat ihn bereits bewertet (oder wegen
        # der Marge verworfen - das ist dann kein leerer Markt).
        if t is not None and (t.get("sell_min") or 0) > 0:
            continue
        menge = min(int(s.get("sell_qty") or 0), 100)
        kandidaten.append((sell_min * max(menge, 1), tid))
    kandidaten.sort(reverse=True)
    return [tid for _w, tid in kandidaten[:max(0, int(cap))]]


def bewerte_leeren_markt(tid, quell_preis, hist, tax, broker, ziel_eintrag=None):
    """Macht aus einem leeren Zielmarkt einen Treffer - oder None.

    ES GIBT AM ZIEL KEINEN PREIS. Das ist der ganze Punkt und zugleich das
    Problem: was dort erzielbar ist, ist eine SCHAETZUNG. Genommen wird der
    30-Tage-DURCHSCHNITT aus der Markthistorie, nicht das Hoch - eine grosse
    gruene Marge, die auf dem Bestpreis eines einzelnen Tages steht, waere
    eine Luege (Regel 3: im Zweifel die schlechtere Zahl).

    ABSATZ IN DER HISTORIE IST NICHT ABSATZ HEUTE. Ein Item mit Umsatz vor
    drei Wochen und nichts seither ist tot, keine Goldgrube. Deshalb wird
    auf TAGE MIT UMSATZ IN DEN LETZTEN 7 gefiltert, nicht auf den
    30-Tage-Schnitt.

    Rueckgabe: dict in derselben Form wie `arbitrage`, zusaetzlich
    `leerer_markt=True` und `sell_geschaetzt=True` - die Oberflaeche MUSS
    das kennzeichnen koennen, sonst sieht eine Schaetzung aus wie ein
    gerechneter Preis.
    """
    if not hist or quell_preis <= 0:
        return None
    # NACH DATUM, NICHT NACH POSITION (emm848, Begruendung bei
    # market.fenster_nach_datum): hist[-7:] waren die letzten 7
    # HANDELSTAGE - bei einem toten Item liegen die Monate zurueck, und
    # genau diese Funktion haette ihn dann "mit nachgewiesenem Absatz"
    # geadelt.
    from . import market as _mk_fnd
    _fnd = _mk_fnd.fenster_nach_datum
    letzte7 = _fnd(hist, 7)
    tage_mit_umsatz = sum(1 for r in letzte7 if (r.get("volume") or 0) > 0)
    if tage_mit_umsatz < 1:
        return None                       # am Ziel wird gar nicht gehandelt
    letzte30 = _fnd(hist, 30)
    preise = [r.get("average") or 0 for r in letzte30
              if (r.get("volume") or 0) > 0 and (r.get("average") or 0) > 0]
    if not preise:
        return None
    schaetzung = sum(preise) / len(preise)
    netto = schaetzung * (1 - tax - broker)
    gewinn = netto - quell_preis
    if gewinn <= 0:
        return None
    tagesmenge = sum((r.get("volume") or 0) for r in letzte30) / 30.0
    t = ziel_eintrag or {}
    return {
        "type_id": tid,
        "source_sell": quell_preis,
        "target_sell": schaetzung,
        "target_buy": t.get("buy_max", 0) or 0,
        "profit_unit": gewinn,
        "margin": gewinn / quell_preis * 100.0,
        "target_demand": t.get("buy_qty", 0) or 0,
        "target_supply": 0,               # genau darum geht es: nichts da
        "sell_orders": [],
        "leerer_markt": True,
        "sell_geschaetzt": True,
        "tage_mit_umsatz_7": tage_mit_umsatz,
        # DAS ZIEL-VOLUMEN GLEICH MITGEBEN. Diese Treffer laufen NICHT durch
        # die normale Absatz-Schleife des Scans (sie standen nie in deren
        # id-Liste) - ohne diesen Wert stuende in der Spalte "Ø daily vol
        # destination" ein Strich, ausgerechnet bei den Zeilen, deren
        # ganzer Sinn der nachgewiesene Absatz ist.
        "target_vol": tagesmenge,
        "target_frisch": _mk_fnd.tage_seit_handel(hist),
        "score": gewinn * max(1, min(int(tagesmenge), 10_000)),
    }


def arbitrage(source: dict, target: dict, settings: dict, filters: dict,
              sell_mode: str = "relist", target_is_structure: bool = False) -> list:
    """Buy at source (sell orders), sell at target. Returns ranked deals.
    In a player Upwell structure the sell-order broker fee is the structure's
    fee (0.5% SCC surcharge + owner %), not the skill-reduced NPC fee."""
    tax = settings["sales_tax_pct"] / 100.0
    if target_is_structure:
        broker = settings.get("structure_broker_pct", 1.0) / 100.0
    else:
        broker = settings["broker_fee_pct"] / 100.0
    pmin = filters.get("price_min", 0) or 0
    pmax = filters.get("price_max", 0) or 0
    min_margin = filters.get("min_margin", 0) or 0
    min_profit = filters.get("min_profit_isk", 0) or 0
    min_liq = filters.get("min_liquidity", 0) or 0
    cap = filters.get("max_items", 400)

    out = []
    for tid, s in source.items():
        # realistic source buy price: average to fill a representative quantity,
        # so a single ghost order at the very bottom can't distort the margin
        ladder = sorted(s.get("sell_orders", []))
        sell_min = s["sell_min"]
        if sell_min <= 0:
            continue
        t = target.get(tid)
        if not t:
            continue
        want = min(max(int(t.get("buy_qty", 0)), 1), 1000)
        filled = 0
        spent = 0.0
        for price, vol in ladder:
            take = min(want - filled, vol)
            spent += take * price
            filled += take
            if filled >= want:
                break
        buy = (spent / filled) if filled else sell_min
        if buy <= 0:
            continue
        if pmin and buy < pmin:
            continue
        if pmax and buy > pmax:
            continue
        if sell_mode == "instant":
            sell_price = t["buy_max"]
            net = sell_price * (1 - tax)
            liquidity = t["buy_qty"]
        else:
            sell_price = t["sell_min"]
            net = sell_price * (1 - tax - broker)
            liquidity = t["buy_qty"]  # demand at target
        if sell_price <= 0:
            continue
        profit = net - buy
        if profit < min_profit:
            continue
        margin = (profit / buy * 100) if buy else 0
        if margin < min_margin:
            continue
        if min_liq and liquidity < min_liq:
            continue
        out.append({
            "type_id": tid,
            "source_sell": buy,
            "target_sell": t["sell_min"],
            "target_buy": t["buy_max"],
            "profit_unit": profit,
            "margin": margin,
            "target_demand": t["buy_qty"],
            "target_supply": t["sell_qty"],
            "sell_orders": sorted(s.get("sell_orders", [])),
            "score": profit * max(1, min(liquidity, 10_000)),
        })
    out.sort(key=lambda r: r["score"], reverse=True)
    return out[:cap]
