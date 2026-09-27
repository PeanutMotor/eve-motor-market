"""Zeigt, WELCHE offenen Market-Orders das Tool von ESI bekommt - und woher
ein falsches "Buy" in der Orders-Spalte des Portfolios kommen kann
(Fassung 1, 22.09.2026).

WOZU: Nutzer-Befund 22.09.2026 - "das Portfolio zeigt, ich haette Items in
Buy Orders, dem ist aber nicht so". Das Tool baut dafuer genau EINE Menge
(`_buy_order_ids` in `_fetch_open_orders`): alle type_ids, fuer die
IRGENDEIN verlinkter Charakter IRGENDWO eine offene Kauf-Order hat.
Gespeichert wird dabei nur die type_id - kein Ort, keine Restmenge, kein
Charakter. Dieser Bericht zeigt die ROHDATEN dahinter, damit sichtbar wird,
woher ein falsches "Buy" stammt:

  * gehoert die Order einem ANDEREN deiner Charaktere? Das Portfolio
    filtert nach dem oben gewaehlten Charakter, diese Menge NICHT - dann
    markiert die Order der Alt die Zeile der Main.
  * liegt sie an einem ANDEREN Ort als dein Bestand?
  * hat sie ueberhaupt noch eine Restmenge (`volume_remain`)?
  * oder ist sie im Spiel laengst weg und ESI liefert noch den alten Stand?
    CCP cached diesen Abruf - darum steht die Uhrzeit im Bericht, und
    `issued` + `duration` zeigen, wie alt jede Order ist.

GERATEN WIRD HIER NICHTS: der Bericht zeigt, was ESI liefert, und rechnet
die Menge exakt so zusammen wie das Tool.

VORAUSSETZUNG: mindestens ein verlinkter Charakter (der Scope
esi-markets.read_character_orders.v1 haengt an jeder Verknuepfung).

AUFRUF: werkzeuge\\zeige_orders.bat doppelklicken.
Danach liegt `berichte\\orders_bericht.txt` da - die hochladen.
Es wird NUR GELESEN: weder deine Datenbank noch deine Orders im Spiel
werden veraendert.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import config, esi, store   # noqa: E402

FASSUNG = 1
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERICHT = os.path.join(WURZEL, "berichte", "orders_bericht.txt")


def _z(n):
    """Ganze Zahl mit Hochkomma-Trennung."""
    try:
        return f"{int(n):,}".replace(",", "'")
    except (TypeError, ValueError):
        return "?"


def _preis(n):
    """Preise NIE auf ganze ISK kuerzen: bei Mineralen (5,50) waere die
    Nachkommastelle genau die Information, an der man seine Order im Spiel
    wiedererkennt."""
    try:
        v = float(n)
    except (TypeError, ValueError):
        return "?"
    txt = f"{v:,.2f}".replace(",", "'")
    return txt[:-3] if txt.endswith(".00") else txt


def _zeit(s):
    return (s or "?").replace("T", " ").replace("Z", "")


def _ortsname(loc_id, cache):
    """NPC-Station per oeffentlichem Endpunkt, Struktur nur als ID.

    Strukturen brauchen Andockrecht; ein Fehlschlag darf den Bericht nicht
    kosten, deshalb bleibt es dann bei der nackten ID (ehrlicher als ein
    erfundener Name)."""
    if loc_id in cache:
        return cache[loc_id]
    name = f"#{loc_id}"
    try:
        if esi.is_npc_station(loc_id):
            name = esi.resolve_station(int(loc_id)).get("name") or name
        else:
            name = f"Struktur #{loc_id}"
    except Exception:
        pass
    cache[loc_id] = name
    return name


def main():
    aus = []
    p = aus.append
    p("=" * 78)
    p(f"OFFENE MARKET-ORDERS - was ESI dem Tool liefert (Fassung {FASSUNG})")
    p(f"Erstellt: {time.strftime('%Y-%m-%d %H:%M:%S')} (Ortszeit deines Rechners)")
    p("=" * 78)
    p("")

    try:
        chars = store.list_characters()
    except Exception as e:
        p(f"DATENBANK NICHT LESBAR: {type(e).__name__}: {e}")
        p("Das Tool einmal starten (es legt die Tabellen an), dann erneut.")
        _schreib(aus)
        return 0
    if not chars:
        p("KEIN CHARAKTER VERLINKT - es gibt nichts abzurufen.")
        _schreib(aus)
        return 0

    client_id = (config.load_settings() or {}).get("client_id") \
        or config.EMBEDDED_CLIENT_ID
    p(f"Verlinkte Charaktere: {len(chars)}")
    for c in chars:
        p(f"  - {c.get('character_name') or '?'}  (id {c.get('character_id')})")
    p("")
    p("WICHTIG ZUM VERSTAENDNIS: das Portfolio zeigt nur den Bestand des oben")
    p("gewaehlten Charakters - die Kauf-Order-Markierung stammt aber aus der")
    p("Summe ALLER hier aufgefuehrten Charaktere. Steht bei einem Item 'Buy',")
    p("obwohl DIESER Charakter keine Order hat, steht sie moeglicherweise bei")
    p("einem anderen weiter unten.")
    p("")

    buy_ids, sell_ids = set(), set()
    je_char = {}
    fehler = {}
    for c in chars:
        cid = c["character_id"]
        try:
            je_char[cid] = list(esi.fetch_character_orders(client_id, cid))
        except Exception as e:
            je_char[cid] = []
            fehler[cid] = f"{type(e).__name__}: {e}"

    # Namen und Orte einmal aufloesen (Sammelabruf statt je Zeile).
    tids = sorted({int(o.get("type_id") or 0)
                   for lst in je_char.values() for o in lst
                   if int(o.get("type_id") or 0) > 0})
    try:
        namen = esi.resolve_names(tids) if tids else {}
    except Exception:
        namen = {}
    ortcache = {}

    for c in chars:
        cid = c["character_id"]
        lst = je_char.get(cid) or []
        p("-" * 78)
        p(f"CHARAKTER {c.get('character_name') or '?'} (id {cid})")
        if cid in fehler:
            p(f"  ABRUF FEHLGESCHLAGEN: {fehler[cid]}")
            p("  -> fuer diesen Charakter weiss das Tool NICHTS; seine Orders")
            p("     markieren dann auch nichts. Das ist kein falsches 'Buy'.")
            p("")
            continue
        kauf = [o for o in lst if o.get("is_buy_order")]
        verkauf = [o for o in lst if not o.get("is_buy_order")]
        p(f"  offene Orders gesamt: {len(lst)}  "
          f"(Kauf {len(kauf)} / Verkauf {len(verkauf)})")
        p("")
        for titel, gruppe, menge in (("KAUF-ORDERS", kauf, buy_ids),
                                     ("VERKAUFS-ORDERS", verkauf, sell_ids)):
            p(f"  {titel}: {len(gruppe)}")
            if not gruppe:
                p("    (keine)")
                p("")
                continue
            p(f"    {'type_id':>9}  {'Item':<40} {'Preis':>16} "
              f"{'Rest/Gesamt':>14}  {'Ausgestellt':<20} {'Tage':>5}  Ort")
            for o in sorted(gruppe, key=lambda x: (namen.get(
                    int(x.get('type_id') or 0), '') or '').lower()):
                tid = int(o.get("type_id") or 0)
                if tid > 0:
                    menge.add(tid)
                rest = o.get("volume_remain")
                ges = o.get("volume_total")
                p(f"    {tid:>9}  {(namen.get(tid) or '?')[:40]:<40} "
                  f"{_preis(o.get('price')):>16} "
                  f"{_z(rest) + '/' + _z(ges):>14}  "
                  f"{_zeit(o.get('issued')):<20} "
                  f"{str(o.get('duration', '?')):>5}  "
                  f"{_ortsname(o.get('location_id'), ortcache)}")
                if rest is not None and int(rest or 0) <= 0:
                    p("               ^^^ RESTMENGE 0 - diese Order ist erfuellt, "
                      "das Tool zaehlt sie trotzdem mit.")
            p("")

    p("=" * 78)
    p("DIE MENGE, DIE DAS TOOL DARAUS BAUT")
    p("=" * 78)
    p("")
    p(f"_buy_order_ids  ({len(buy_ids)} type_ids) - diese Items tragen im")
    p("Portfolio 'Buy' und fallen aus der Verkaufsliste:")
    if buy_ids:
        for tid in sorted(buy_ids, key=lambda x: (namen.get(x, '') or '').lower()):
            wer = [str(c.get("character_name") or c["character_id"]) for c in chars
                   if any(int(o.get("type_id") or 0) == tid and o.get("is_buy_order")
                          for o in (je_char.get(c["character_id"]) or []))]
            p(f"  {tid:>9}  {(namen.get(tid) or '?'):<40} "
              f"Order(s) bei: {', '.join(wer) or '?'}")
    else:
        p("  (leer - dann kann das Portfolio auch bei keinem Item 'Buy' zeigen,")
        p("   solange es diesen Abruf gemacht hat)")
    p("")
    p(f"_sell_order_ids ({len(sell_ids)} type_ids) - diese Items zeigen")
    p("'● on market' statt einer Verkaufs-Empfehlung.")
    p("")
    p("=" * 78)
    p("WENN HIER ETWAS STEHT, DAS ES IM SPIEL NICHT GIBT")
    p("=" * 78)
    p("")
    p("Dann liefert ESI selbst einen veralteten Stand (CCP cached diesen")
    p("Abruf). Pruefen laesst sich das so: diese .bat in ein paar Minuten")
    p("noch einmal laufen lassen und die beiden Berichte vergleichen -")
    p("verschwindet die Order dann, war es der Cache. Bleibt sie, existiert")
    p("sie wirklich noch (dann lohnt der Blick ins Order-Fenster im Spiel,")
    p("Reiter 'Buy orders', auch bei den anderen Charakteren).")
    p("")
    _schreib(aus)
    return 0


def _schreib(zeilen):
    os.makedirs(os.path.dirname(BERICHT), exist_ok=True)
    with open(BERICHT, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    print("\n".join(zeilen))
    print("")
    print(f"Bericht geschrieben: {BERICHT}")


if __name__ == "__main__":
    sys.exit(main())
