"""PRUEFT DIE FRACHT DER VERKAUFSLISTE AN DEINEN ECHTEN KAEUFEN
(Fassung 2, 29.09.2026: Container nie Fracht).

WOZU: Nutzer 29.09.2026: "koennen wir pruefen, ob das auch zuverlaessig
funktioniert?" Die Fracht (emm272) haengt an den Wallet-Kaeufen mit Kaufort.
Dieser Bericht rechnet sie fuer DEINE Daten nach - und zwar ZWEIMAL:

  1. mit der Funktion des Programms (`market.fracht_je_item`),
  2. mit einer zweiten, hier unabhaengig geschriebenen FIFO-Rechnung.

Stimmen beide nicht ueberein, steht "ABWEICHUNG" am Item. Dazu je Item:
wie viele Stueck noch liegen, WO sie gekauft wurden, welche davon Fracht
tragen, Fracht je Stueck, Aufschlag in Prozent und der Ziel-Preis ohne und
mit Fracht. Am Ende eine Liste der Faelle, in denen KEINE Fracht gerechnet
wird, obwohl Stueck woanders gekauft wurden (unbekanntes Volumen, Schiff
ohne gepacktes Volumen, Rechtsklick "keine Fracht"), und Stueck mit
unbekanntem Kaufort (alte Daten).

GERATEN WIRD NICHTS: kein ESI-Abruf, nur deine Datenbank und settings.json.
Es wird NUR GELESEN.

AUFRUF: werkzeuge\\pruefe_fracht.bat doppelklicken, danach
`berichte\\fracht_bericht.txt` hochladen.
"""
import os
import sys
import time
from collections import defaultdict, deque

_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _WURZEL)

from eve_trader import config, hubs, industry, market, store   # noqa: E402

FASSUNG = 2
BEISPIEL_SATZ = 500      # nur wenn im Tool 0 steht - im Bericht gekennzeichnet


def _hub_ort(settings):
    """Kaufort, der als 'am Hub' gilt - genau wie `_active_hub` im Fenster
    (Struktur-ID, sonst die NPC-Station der gemerkten Region, sonst Jita)."""
    g = settings.get("ui_hub")
    if isinstance(g, dict) and g.get("structure_id"):
        return int(g["structure_id"]), str(g.get("name") or g["structure_id"])
    try:
        rid = int(g) if g is not None else None
    except (TypeError, ValueError):
        rid = None
    for _k, label, r, s in hubs.NPC_HUBS:
        if r == rid:
            return s, label
    return config.JITA_STATION, "Jita (Standard)"


def _fifo_zweitrechnung(tx):
    """UNABHAENGIG von market.py geschrieben: je (Charakter, Item) eine
    Schlange von [Menge, Ort]; Verkaeufe fressen die aeltesten Kaeufe.
    Kaeufe vor Verkaeufen am selben Zeitpunkt. -> {tid: {ort: Menge}}"""
    schl = defaultdict(deque)
    for x in sorted(tx, key=lambda x: (x["date"], 0 if x["is_buy"] else 1)):
        k = (x.get("character_id"), x["type_id"])
        if x["is_buy"]:
            schl[k].append([int(x["quantity"]), int(x.get("location_id") or 0)])
            continue
        rest = int(x["quantity"])
        while rest > 0 and schl[k]:
            n = min(rest, schl[k][0][0])
            schl[k][0][0] -= n
            rest -= n
            if schl[k][0][0] == 0:
                schl[k].popleft()
    aus = defaultdict(lambda: defaultdict(int))
    for (_c, tid), q in schl.items():
        for menge, ort in q:
            if menge > 0:
                aus[tid][ort] += menge
    return aus


def _zahl(n):
    return f"{n:,.0f}".replace(",", "'")


def main():
    zeilen = []

    def p(s=""):
        zeilen.append(s)
        print(s)

    s = config.load_settings()
    satz_tool = int(s.get("fracht_isk_m3", 0) or 0)
    satz = satz_tool or BEISPIEL_SATZ
    ohne = {int(x) for x in (s.get("fracht_aus_items") or []) if str(x).lstrip("-").isdigit()}
    hub, hub_name = _hub_ort(s)
    tax = float(s.get("sales_tax_pct", 0)) / 100
    broker = float(s.get("broker_fee_pct", 0)) / 100
    ziel = float(s.get("target_margin", 0)) / 100
    nenner = 1 - tax - broker

    p(f"FRACHT-PRUEFUNG Fassung {FASSUNG} - {time.strftime('%d.%m.%Y %H:%M')}")
    p(f"Hub (Verkaufsort): {hub_name}  [Ort-ID {hub}]")
    if satz_tool:
        p(f"Frachtsatz im Tool: {_zahl(satz_tool)} ISK/m3")
    else:
        p(f"Frachtsatz im Tool: 0 (Fracht AUS) - der Bericht rechnet ZUR PROBE "
          f"mit {BEISPIEL_SATZ} ISK/m3")
    p(f"Ziel-Marge {ziel*100:.1f} %, Steuer {tax*100:.2f} %, Broker {broker*100:.2f} %")
    p(f"Rechtsklick 'keine Fracht' bei: {sorted(ohne) or '-'}")
    p()

    tx = store.get_transactions()
    p(f"Transaktionen in der Datenbank: {len(tx)} "
      f"(Kaeufe {sum(1 for x in tx if x['is_buy'])}, "
      f"ohne Kaufort {sum(1 for x in tx if x['is_buy'] and not x.get('location_id'))})")
    agg = market.aggregate_holdings(tx)
    zweit = _fifo_zweitrechnung(tx)
    ids = sorted(agg)
    vols = industry.item_volume_map(ids) if ids else {}
    gruppen = industry.group_names(ids) if ids else {}
    container = {t for t, g in gruppen.items() if market.ist_container(g)}
    for t in container:
        vols.pop(t, None)            # wie im Programm: Container nie Fracht
    try:
        schiffe = industry.ships_with_unpackaged_volume(ids) if ids else set()
    except Exception:
        schiffe = set()
    if schiffe:
        _c = store.cached_volumes(sorted(schiffe))
        for t in schiffe:
            if _c.get(t):
                vols[t] = _c[t]
            else:
                vols.pop(t, None)
    tool = market.fracht_je_item(tx, {hub}, satz, vols, ohne)
    namen = store.cached_names(ids)
    orte_namen = {h[3]: h[1] for h in hubs.NPC_HUBS}
    try:
        for f in store.list_favorites():
            if f.get("structure_id"):
                orte_namen[int(f["structure_id"])] = f.get("name") or ""
    except Exception:
        pass

    abweichungen, ohne_fracht, unbekannt = [], [], []
    mit = 0
    p(f"Noch liegende Items laut FIFO: {len(ids)}")
    p("=" * 78)
    for tid in sorted(ids, key=lambda t: namen.get(t, "")):
        a = agg[tid]
        orte = zweit.get(tid, {})
        liegend2 = sum(orte.values())
        fremd = sum(m for o, m in orte.items() if o and o != hub)
        ohne_ort = orte.get(0, 0)
        m3 = float(vols.get(tid) or 0)
        soll_fracht = fremd * m3 * satz if (tid not in ohne and m3 > 0) else 0.0
        info = tool.get(tid) or {}
        ist_fracht = float(info.get("fracht") or 0.0)
        fehler = []
        if liegend2 != a["quantity"]:
            fehler.append(f"Menge FIFO {a['quantity']} / Zweitrechnung {liegend2}")
        if abs(ist_fracht - soll_fracht) > 1e-6:
            fehler.append(f"Fracht Tool {ist_fracht:.2f} / Zweitrechnung {soll_fracht:.2f}")
        if info and info.get("menge") != a["quantity"]:
            fehler.append(f"Fracht-Menge {info.get('menge')} / FIFO {a['quantity']}")
        if ohne_ort:
            unbekannt.append(f"{namen.get(tid, tid)}: {ohne_ort} Stueck ohne Kaufort")
        if fremd and not ist_fracht:
            grund = ("Rechtsklick 'keine Fracht'" if tid in ohne
                     else "Container (nie Fracht)" if tid in container
                     else "Schiff ohne gepacktes Volumen (noch nicht aus ESI geholt)"
                     if tid in schiffe else "Volumen unbekannt (Rezepte/SDE laden)")
            ohne_fracht.append(f"{namen.get(tid, tid)}: {fremd} Stueck woanders gekauft - {grund}")
        if not (fremd or fehler):
            continue            # nur am Hub gekauft: nichts zu zeigen
        mit += 1
        p(f"{namen.get(tid, f'#{tid}')}  (type {tid})")
        p(f"  liegend {_zahl(a['quantity'])}, Einkauf avg {a['avg_buy']:,.2f} ISK, "
          f"Volumen {m3:g} m3")
        for o, m in sorted(orte.items(), key=lambda x: -x[1]):
            wo = ("AM HUB" if o == hub else "ohne Ort" if not o
                  else orte_namen.get(o) or f"Ort {o}")
            p(f"    {_zahl(m):>10} Stueck gekauft: {wo}")
        if ist_fracht:
            je = info["je_stueck"]
            ohne_p = a["avg_buy"] * (1 + ziel) / nenner if nenner > 0 else 0
            mit_p = (a["avg_buy"] + je) * (1 + ziel) / nenner if nenner > 0 else 0
            p(f"  Fracht {_zahl(fremd)} x {m3:g} m3 x {_zahl(satz)} = {_zahl(ist_fracht)} ISK"
              f" -> je Stueck {je:,.2f} ISK = +{je / a['avg_buy'] * 100:.2f} %")
            p(f"  Ziel-Preis ohne Fracht {ohne_p:,.2f}  |  mit Fracht {mit_p:,.2f}")
        p("  " + ("ABWEICHUNG: " + "; ".join(fehler) if fehler else "Nachrechnung stimmt"))
        if fehler:
            abweichungen.append(f"{namen.get(tid, tid)}: {'; '.join(fehler)}")
    p("=" * 78)
    p(f"Items mit Fracht oder Abweichung: {mit}")
    p(f"ABWEICHUNGEN zwischen Tool und Zweitrechnung: {len(abweichungen)}")
    for z in abweichungen:
        p("  " + z)
    p(f"Woanders gekauft, aber OHNE Fracht: {len(ohne_fracht)}")
    for z in ohne_fracht:
        p("  " + z)
    p(f"Stueck ohne Kaufort (alte Daten, nie Fracht): {len(unbekannt)}")
    for z in unbekannt:
        p("  " + z)
    p()
    p("ERGEBNIS: " + ("ALLES STIMMT" if not abweichungen else "ABWEICHUNG - bitte Bericht schicken"))

    os.makedirs(os.path.join(_WURZEL, "berichte"), exist_ok=True)
    with open(os.path.join(_WURZEL, "berichte", "fracht_bericht.txt"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    return 1 if abweichungen else 0


if __name__ == "__main__":
    sys.exit(main())
