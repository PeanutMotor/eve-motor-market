#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIMULATIONEN Order-Update-Intervall (emm735), Nutzer 27.10.2026:
"pruefe deine angabe und funktionalitaet, mache simulationen von
verschiedenen szenarien".

Teil A  reine Logik + Datenbank, Zeitreise ueber explizite Zeitpunkte
        (Zeitzone Europe/Zurich, Sommerzeit-Ende 25.10.2026 inklusive).
Teil B  das ECHTE Hauptfenster mit simuliertem ESI (Orders mit `issued`,
        Orderbuecher) und einer verstellbaren Uhr: mehrere Tage am Stueck,
        "Next", Aenderung im Spiel, Intervall-Feld, Ausnahme je Item,
        gefuellte Order, zwei Orders desselben Items, Buy-Seite.
        Es laeuft der echte Ladeweg (`_load_order_mods` -> Worker -> `done`),
        nicht nur die Hilfsfunktionen.

Aufruf: QT_QPA_PLATFORM=offscreen python3 werkzeuge/sim_emm735.py
(Exit 0 = alles gruen). Arbeitet in einem Wegwerf-Ordner - die echten
Einstellungen/Datenbank bleiben unberuehrt.
"""
import datetime as dt
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = tempfile.mkdtemp(prefix="sim735_")
for _k in ("HOME", "APPDATA", "USERPROFILE"):
    os.environ[_k] = HOME
os.environ["TZ"] = "Europe/Zurich"
try:
    time.tzset()
except AttributeError:          # Windows: kein tzset - Zeitzone des Rechners
    pass
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.chdir(ROOT)
sys.path.insert(0, ROOT)

OK = True


def pruefe(name, ist, soll):
    global OK
    gut = (ist == soll)
    OK = OK and gut
    print(("  OK   " if gut else "  ROT  ") + name
          + ("" if gut else f"  ist={ist!r} soll={soll!r}"))


def L(y, mo, d, h=0, mi=0, se=0):
    return dt.datetime(y, mo, d, h, mi, se).timestamp()


from eve_trader import config  # noqa: E402
from eve_trader import store  # noqa: E402
from eve_trader.ui import mw_helpers as H  # noqa: E402

# =====================================================================
print("TEIL A - Logik und Datenbank")
store.init_db()

# --- A1 der Alltag: 3 Tage, abends angefasst ------------------------------
c = L(2026, 10, 27, 20, 0)                       # Di 20:00 "Next"
st = lambda jetzt, n=3: H.order_intervall_status(c, n, jetzt)[0]
pruefe("A1 Di 20:00 angefasst, 3 Tage: Mi 12:00 wartet", st(L(2026, 10, 28, 12)), False)
pruefe("A1 ... Do 23:59 wartet", st(L(2026, 10, 29, 23, 59)), False)
pruefe("A1 ... Fr 00:00:59 wartet noch", st(L(2026, 10, 30, 0, 0, 59)), False)
pruefe("A1 ... Fr 00:01 ist dran", st(L(2026, 10, 30, 0, 1)), True)
pruefe("A1 Anzeige: Di Abend 3 Tage -> 'in 3 Tagen'",
       H.order_intervall_tage_bis(c, 3, L(2026, 10, 27, 21)), 3)
pruefe("A1 ... Mi -> 2", H.order_intervall_tage_bis(c, 3, L(2026, 10, 28, 9)), 2)
pruefe("A1 ... Do -> 1 ('morgen')",
       H.order_intervall_tage_bis(c, 3, L(2026, 10, 29, 9)), 1)
pruefe("A1 ... Fr 00:30 -> 0 (dran)",
       H.order_intervall_tage_bis(c, 3, L(2026, 10, 30, 0, 30)), 0)

# --- A2 Sommerzeit-Ende (So 25.10.2026 03:00 -> 02:00) --------------------
c2 = L(2026, 10, 24, 20, 0)                      # Sa 20:00
pruefe("A2 Sa 20:00, 1 Tag: So 00:01 dran (Tag mit 25 Stunden)",
       H.order_intervall_status(c2, 1, L(2026, 10, 25, 0, 1))[0], True)
pruefe("A2 ... So 00:00:30 noch nicht",
       H.order_intervall_status(c2, 1, L(2026, 10, 25, 0, 0, 30))[0], False)
pruefe("A2 Sa 20:00, 2 Tage: Mo 00:01 dran, So 23:59 nicht",
       (H.order_intervall_status(c2, 2, L(2026, 10, 26, 0, 1))[0],
        H.order_intervall_status(c2, 2, L(2026, 10, 25, 23, 59))[0]),
       (True, False))

# --- A3 Zeitzone: issued kommt in UTC -------------------------------------
# 22:30 UTC am 27.10. = 23:30 MEZ (nach Sommerzeit-Ende: UTC+1) -> Ortstag 27.
# 23:30 UTC am 27.10. = 00:30 MEZ am 28.10. -> Ortstag 28 (nicht der UTC-Tag!).
a = store._iso_ts("2026-10-27T22:30:00Z")
b = store._iso_ts("2026-10-27T23:30:00Z")
pruefe("A3 22:30Z = 23:30 Ortszeit: 1 Tag -> faellig 28.10.",
       dt.datetime.fromtimestamp(H.order_intervall_faellig_ts(a, 1)).date(),
       dt.date(2026, 10, 28))
pruefe("A3 23:30Z = 00:30 Ortszeit: 1 Tag -> faellig 29.10. (Ortstag zaehlt)",
       dt.datetime.fromtimestamp(H.order_intervall_faellig_ts(b, 1)).date(),
       dt.date(2026, 10, 29))

# --- A4 Standard/Ausnahme/Unsinn ------------------------------------------
# HAUPTSCHALTER (emm741/emm785): seit emm785 gilt OHNE den Eintrag
# `ord_intervall_aktiv` AUS (Nutzer 31.10.2026: "der Skip button sollte
# standardmaessig nicht angehackt sein") - die Rechnung selbst wird
# deshalb MIT aktivem Schalter geprueft, der neue Default eigens.
e = {"ord_intervall_aktiv": True, "ord_intervall_tage": 3,
     "ord_intervall_item": {"34": 0, "35": 7, "36": "abc", "37": -4, "38": 2.6}}
pruefe("A4 Standard 3 / Item 0 / Item 7 / Item 'abc' (=0) / -4 (=0) / 2.6 (=3)",
       [H.order_intervall_dauer(e, t)[0] for t in (99, 34, 35, 36, 37, 38)],
       [3, 0, 7, 0, 0, 3])
pruefe("A4 Item-ID kaputt (None/'x') wirft nicht",
       (H.order_intervall_dauer(e, None), H.order_intervall_dauer(e, "x")),
       ((3, 0), (3, 0)))
pruefe("A4 Schalter fehlt (emm785) oder False -> ueberall aus",
       (H.order_intervall_dauer(dict(e, ord_intervall_aktiv=False), 35),
        H.order_intervall_dauer({k: v for k, v in e.items()
                                 if k != "ord_intervall_aktiv"}, 35)),
       ((0, 0), (0, 0)))
pruefe("A4 Einstellungen fehlen ganz -> 0",
       (H.order_intervall_dauer(None, 5), H.order_intervall_dauer({}, 5)),
       ((0, 0), (0, 0)))

# --- A4b Stunden-Modus: genaue Pause -----------------------------------------
cs = L(2026, 10, 27, 23, 59)
pruefe("A4b 12 h ab 23:59: 11:58 wartet, 11:59 dran",
       (H.order_intervall_status(cs, 0, L(2026, 10, 28, 11, 58), 12)[0],
        H.order_intervall_status(cs, 0, L(2026, 10, 28, 11, 59), 12)[0]),
       (False, True))
pruefe("A4b 1 d 6 h = 30 h exakt",
       (H.order_intervall_status(cs, 1, L(2026, 10, 29, 5, 58), 6)[0],
        H.order_intervall_status(cs, 1, L(2026, 10, 29, 5, 59), 6)[0]),
       (False, True))
pruefe("A4b 24 h ab 23:59 ist NICHT schon um 00:01 dran (Randfall geloest)",
       H.order_intervall_status(cs, 0, L(2026, 10, 28, 0, 1), 24)[0], False)
pruefe("A4b Kurzanzeige", (H.order_intervall_dauer_kurz(2 * 86400 + 4 * 3600),
                           H.order_intervall_dauer_kurz(5 * 3600 + 600),
                           H.order_intervall_dauer_kurz(720)),
       ("2 d 4 h", "5 h 10 min", "12 min"))

# --- A5 Intervall NACH dem Start geaendert -> sofort neu bewertet ---------
c5 = L(2026, 10, 27, 9, 0)
jetzt5 = L(2026, 10, 28, 10, 0)                  # einen Tag danach
pruefe("A5 3 Tage: einen Tag nach dem Anfassen wartet",
       H.order_intervall_status(c5, 3, jetzt5)[0], False)
pruefe("A5 auf 1 Tag verkuerzt: dieselbe Order ist SOFORT dran",
       H.order_intervall_status(c5, 1, jetzt5)[0], True)
pruefe("A5 auf 0 (aus): dran", H.order_intervall_status(c5, 0, jetzt5)[0], True)
pruefe("A5 auf 7 verlaengert: wartet weiter",
       H.order_intervall_status(c5, 7, jetzt5)[0], False)

# --- A6 Datenbank: Lebenslauf einer Order ---------------------------------
t0 = L(2026, 10, 20, 12, 0)
S = store.order_intervall_sync
r = S({5001: "2026-10-01T08:00:00Z"}, now=t0)
pruefe("A6 erste Sicht: keine Uhr", r, {5001: None})
r = S({5001: "2026-10-01T08:00:00Z"}, now=t0 + 3600)
pruefe("A6 nochmal gesehen, unveraendert: weiter keine Uhr", r, {5001: None})
store.order_intervall_start(5001, "2026-10-01T08:00:00Z", now=L(2026, 10, 21, 9))
r = S({5001: "2026-10-01T08:00:00Z"}, now=L(2026, 10, 21, 10))
pruefe("A6 'Next' gedrueckt: Uhr steht auf dem Zeitpunkt", r, {5001: L(2026, 10, 21, 9)})
# im Spiel geaendert (erst Next, dann echte Aenderung 3 Minuten spaeter)
iss = "2026-10-21T08:03:30Z"                      # = 10:03:30 Ortszeit (MESZ)
r = S({5001: iss}, now=L(2026, 10, 21, 11))
pruefe("A6 danach im Spiel geaendert: Uhr springt auf den Zeitpunkt der Aenderung",
       abs(r[5001] - store._iso_ts(iss)) < 1, True)
r = S({5001: iss}, now=L(2026, 10, 22))
pruefe("A6 und bleibt dort", abs(r[5001] - store._iso_ts(iss)) < 1, True)
# Order im Spiel ZWEIMAL geaendert -> immer die letzte Aenderung
iss2 = "2026-10-22T07:00:00Z"
r = S({5001: iss2}, now=L(2026, 10, 22, 12))
pruefe("A6 zweite Aenderung im Spiel: Uhr = die neueste",
       abs(r[5001] - store._iso_ts(iss2)) < 1, True)
# kaputtes/fehlendes issued
r = S({5002: ""}, now=t0)
pruefe("A6 Order ohne issued: keine Uhr, kein Absturz", r, {5002: None})
r = S({5002: None}, now=t0)
pruefe("A6 issued=None: gleich", r, {5002: None})
r = S({5003: "2026-10-01T08:00:00Z"}, now=t0)
r = S({5003: "kaputt"}, now=L(2026, 10, 25, 9))
pruefe("A6 unlesbares issued (!= gemerktem): Uhr = jetzt (im Zweifel 'angefasst')",
       r[5003], L(2026, 10, 25, 9))
# leere Eingabe
pruefe("A6 leere Eingabe: leeres Ergebnis", S({}, now=t0), {})
# Order verschwindet -> Zeile wird nach 120 Tagen Nichtsehen geloescht
S({6001: "2026-01-01T00:00:00Z"}, now=t0)
S({6002: "2026-01-01T00:00:00Z"}, now=t0 + 119 * 86400)
with store._conn() as cc:
    ids = {x[0] for x in cc.execute("SELECT order_id FROM order_intervall")}
pruefe("A6 nach 119 Tagen ist die nicht mehr gesehene Order noch da", 6001 in ids, True)
S({6002: "2026-01-01T00:00:00Z"}, now=t0 + 121 * 86400)
with store._conn() as cc:
    ids = {x[0] for x in cc.execute("SELECT order_id FROM order_intervall")}
pruefe("A6 nach 121 Tagen ist sie weg, die gesehene bleibt",
       (6001 in ids, 6002 in ids), (False, True))

# =====================================================================
print("TEIL B - echtes Fenster, simuliertes ESI")
FAKE = [L(2026, 10, 27, 20, 0)]            # "jetzt": Di 27.10.2026 20:00
_real_time = time.time
time.time = lambda: FAKE[0]

from PySide6.QtWidgets import QApplication, QInputDialog  # noqa: E402
from eve_trader import esi  # noqa: E402

app = QApplication.instance() or QApplication([])

store.upsert_character(111, "Tester")
HUB_STATION = 60003760           # Jita 4-4

ORDERS = []                      # wird je Szenario gesetzt


def order(oid, tid, price, buy=False, issued="2026-10-01T08:00:00Z"):
    return {"order_id": oid, "type_id": tid, "price": price,
            "is_buy_order": buy, "location_id": HUB_STATION,
            "volume_remain": 10, "volume_total": 10, "issued": issued,
            "duration": 90, "range": "station", "region_id": 10000002,
            "is_corporation": False}


esi.fetch_character_orders = lambda client_id, cid: [dict(o) for o in ORDERS]
# Verkaufsorders (Preis 100) werden unterboten (bester Sell 80), Buy-Orders
# (Preis 50) ueberboten (bester Buy 60) - Verlustpruefung ohne Einstand aus.
esi.fetch_type_orders = lambda tid, station, region, **kw: {
    "buy": [(60.0, 100)], "sell": [(80.0, 100)], "ids": {}}
esi.resolve_names = lambda tids: {t: f"Item{t}" for t in tids}

from eve_trader.ui.main_window import MainWindow  # noqa: E402

win = MainWindow()
win._erste_einrichtung_pruefen = lambda *a, **k: None   # kein modaler Tutorial-Dialog in der Simulation
win._tutorial_erstfrage = lambda *a, **k: None
win._erststart_rezepte_anbieten = lambda *a, **k: None
win.open_ingame_market = lambda *a, **k: None       # kein Spielfenster
OPENED = []
win.open_ingame_market = lambda tid, *a, **k: OPENED.append(tid)


def laden():
    win._load_order_mods()
    t_ende = _real_time() + 20
    while getattr(win, "_ord_laeuft", False) and _real_time() < t_ende:
        app.processEvents()
        _real_sleep(0.02)
    for _ in range(5):
        app.processEvents()


_real_sleep = time.sleep


def status(tabelle, name, sell=True):
    sp = 5 if sell else 3
    for i in range(tabelle.rowCount()):
        if tabelle.item(i, 0).text() == name:
            return tabelle.item(i, sp).text()
    return None


def namen(tabelle):
    return [tabelle.item(i, 0).text() for i in range(tabelle.rowCount())]


def next_klick(n=1, sell=True):
    gang = []
    win._toggle_order_step(False)
    win._toggle_order_step(True)
    win._orders_inner.setCurrentIndex(1 if sell else 0)
    for _ in range(n):
        OPENED.clear()
        win._ord_step_next()
        gang.extend(OPENED)
    return gang


def wartet(text):
    return text is not None and "⏳" in text


# Seit emm785 ist der Intervall-Hauptschalter OHNE Eintrag AUS - diese
# Simulation prueft die Intervall-MECHANIK, also Schalter ausdruecklich an
# (wie ein Nutzer, der die Checkbox anhakt).
win.settings["ord_intervall_aktiv"] = True
win.settings["ord_intervall_tage"] = 3
win.settings["ord_intervall_item"] = {}
win._ord_int_spin.blockSignals(True)
win._ord_int_spin.setValue(3)
win._ord_int_spin.blockSignals(False)
SELL = win.sellord_table
BUY = win.buyord_table

# --- B1 Erstes Laden: alles dran, keine Uhr ------------------------------
ORDERS[:] = [order(9001, 34, 100.0), order(9002, 35, 100.0),
             order(9003, 36, 100.0), order(9004, 37, 100.0)]
laden()
pruefe("B1 vier Sell-Orders geladen", sorted(namen(SELL)),
       ["Item34", "Item35", "Item36", "Item37"])
pruefe("B1 erste Sicht: keine wartet",
       [wartet(status(SELL, n)) for n in ("Item34", "Item35", "Item36", "Item37")],
       [False] * 4)
rows = {r["order_id"]: r for r in win._ordmod_sell}
pruefe("B1 issued kam aus ESI bis in die Zeilen",
       {o: r["issued"] for o, r in rows.items()},
       {9001: "2026-10-01T08:00:00Z", 9002: "2026-10-01T08:00:00Z",
        9003: "2026-10-01T08:00:00Z", 9004: "2026-10-01T08:00:00Z"})
pruefe("B1 ... und keine Zeile hat eine Uhr",
       [r["clock"] for r in rows.values()], [None] * 4)

# --- B2 Next auf zwei Orders (Di 20:00) -----------------------------------
gang = next_klick(2)
pruefe("B2 zwei Klicks 'Next' oeffnen zwei verschiedene Items", len(set(gang)), 2)
geklickt = set(gang)
laden()
w1 = {n: wartet(status(SELL, n)) for n in ("Item34", "Item35", "Item36", "Item37")}
tid_von = {f"Item{t}": t for t in (34, 35, 36, 37)}
pruefe("B2 nach dem Neuladen warten GENAU die zwei bearbeiteten",
       {tid_von[n] for n, w in w1.items() if w}, geklickt)
n_wart = next(n for n, w in w1.items() if w)
pruefe("B2 Anzeige Di 20:00 + 3 Tage -> 'in 3 Tagen'",
       "3" in status(SELL, n_wart), True)

# --- B3 Tage vergehen -------------------------------------------------------
FAKE[0] = L(2026, 10, 28, 9, 0)
win._rerender_order_tables()
pruefe("B3 Mi 09:00 (ohne Neuladen): 'in 2 Tagen'", "2" in status(SELL, n_wart), True)
FAKE[0] = L(2026, 10, 29, 22, 0)
win._rerender_order_tables()
t_do = status(SELL, n_wart)
pruefe("B3 Do 22:00: 'morgen'", ("morrow" in t_do) or ("morgen" in t_do), True)
FAKE[0] = L(2026, 10, 30, 0, 0, 30)
win._rerender_order_tables()
pruefe("B3 Fr 00:00:30: wartet noch", wartet(status(SELL, n_wart)), True)
FAKE[0] = L(2026, 10, 30, 0, 1)
win._rerender_order_tables()
pruefe("B3 Fr 00:01: wieder dran (nicht mehr grau/wartend)",
       wartet(status(SELL, n_wart)), False)

# --- B4 Next ueberspringt Wartende, solange sie warten --------------------
FAKE[0] = L(2026, 10, 28, 9, 0)
laden()
gang = next_klick(4)
nicht_geklickt = {t for t in (34, 35, 36, 37)} - geklickt
pruefe("B4 vier Klicks: nur die zwei nicht bearbeiteten Items kommen dran",
       set(gang), nicht_geklickt)

# --- B5 Aenderung IM SPIEL (ohne Next) startet die Uhr --------------------
FAKE[0] = L(2026, 10, 28, 9, 0)
ORDERS[:] = [order(9001, 34, 100.0), order(9002, 35, 100.0),
             order(9003, 36, 100.0), order(9004, 37, 100.0)]
for o in ORDERS:                                      # ruhiger Ausgangszustand
    o["issued"] = "2026-10-01T08:00:00Z"
store.order_intervall_sync({o["order_id"]: o["issued"] for o in ORDERS}, now=FAKE[0])
with store._conn() as cc:                              # Uhren zuruecksetzen
    cc.execute("UPDATE order_intervall SET clock_ts=NULL")
laden()
pruefe("B5 Ausgangslage: keiner wartet",
       [wartet(status(SELL, f"Item{t}")) for t in (34, 35, 36, 37)], [False] * 4)
# im Spiel wird Order 9003 (Item36) heute 08:15 MEZ nachgebessert
for o in ORDERS:
    if o["order_id"] == 9003:
        o["issued"] = "2026-10-28T07:15:00Z"           # = 08:15 Ortszeit
laden()
pruefe("B5 nur das im Spiel geaenderte Item wartet",
       [wartet(status(SELL, f"Item{t}")) for t in (34, 35, 36, 37)],
       [False, False, True, False])
pruefe("B5 ... und 'Next' ueberspringt es",
       36 not in set(next_klick(3)), True)

# --- B6 Intervall-Feld: erst bei Enter/Klick woanders --------------------------
_nr = []
_alt_rr = win._rerender_order_tables
def _zaehl():
    _nr.append(1); _alt_rr()
win._rerender_order_tables = _zaehl
win._ord_int_spin.setValue(1); win._ord_int_spin.setValue(2); win._ord_int_spin.setValue(1)
app.processEvents()
pruefe("B6 Tippen im Feld: kein Neuzeichnen, nichts gespeichert",
       (_nr, config.load_settings().get("ord_intervall_tage")), ([], 3))
win._ord_int_spin.editingFinished.emit()
app.processEvents()
t1 = status(SELL, "Item36")
pruefe("B6 Enter: genau ein Neuzeichnen, heute geaenderte Order zeigt 'morgen'",
       (len(_nr), ("morrow" in t1) or ("morgen" in t1)), (1, True))
pruefe("B6 ... Einstellung gespeichert",
       config.load_settings().get("ord_intervall_tage"), 1)
win._ord_int_spin.editingFinished.emit()
pruefe("B6 Enter ohne Aenderung: kein weiteres Neuzeichnen", len(_nr), 1)
win._ord_int_spin.setValue(0); win._ord_int_spin.editingFinished.emit()
app.processEvents()
pruefe("B6 Feld auf 0 (aus): niemand wartet",
       [wartet(status(SELL, f"Item{t}")) for t in (34, 35, 36, 37)], [False] * 4)
win._ord_int_spin.setValue(3); win._ord_int_spin.editingFinished.emit()
app.processEvents()
pruefe("B6 zurueck auf 3: Item36 wartet wieder",
       wartet(status(SELL, "Item36")), True)
# Stundenfeld
win._ord_int_spin.setValue(0); win._ord_int_std_spin.setValue(12)
win._ord_int_std_spin.editingFinished.emit(); app.processEvents()
pruefe("B6 Stundenfeld 12 h: gespeichert",
       (config.load_settings().get("ord_intervall_tage"),
        config.load_settings().get("ord_intervall_stunden")), (0, 12))
pruefe("B6 Stunden-Modus: Anzeige in Stunden, Item36 (heute angefasst) wartet",
       (wartet(status(SELL, "Item36")), " h" in (status(SELL, "Item36") or "")),
       (True, True))
win._ord_int_std_spin.setValue(0); win._ord_int_spin.setValue(3)
win._ord_int_spin.editingFinished.emit(); app.processEvents()
win._rerender_order_tables = _alt_rr

# --- B6b Sichtbarkeit / Optik ---------------------------------------------------
_fe = (win._ord_int_cb, win._ord_int_spin, win._ord_int_std_spin)   # emm741: Checkbox
win._toggle_order_step(False)
_aus = all(w.isHidden() for w in _fe)
win._toggle_order_step(True)
pruefe("B6b Felder nur im Work-through sichtbar",
       (_aus, any(w.isHidden() for w in _fe)), (True, False))
win._toggle_order_step(False)

# --- B7 Ausnahme je Item ----------------------------------------------------
_alt_ab = win._ord_intervall_abfragen
win._ord_intervall_abfragen = lambda *a, **k: (0, 0)
win._ord_intervall_item_setzen(36, "Item36")
pruefe("B7 Ausnahme 0 fuer Item36: es wartet nicht mehr",
       wartet(status(SELL, "Item36")), False)
pruefe("B7 ... gespeichert",
       config.load_settings().get("ord_intervall_item"), {"36": [0, 0]})
win._ord_intervall_abfragen = lambda *a, **k: (7, 0)
win._ord_intervall_item_setzen(36, "Item36")
pruefe("B7 Ausnahme 7 Tage: wartet, 'in 7 Tagen'",
       "7" in (status(SELL, "Item36") or ""), True)
win._ord_intervall_abfragen = lambda *a, **k: (0, 6)
win._ord_intervall_item_setzen(36, "Item36")
pruefe("B7 Ausnahme 6 Stunden: wartet, Anzeige in Stunden",
       (wartet(status(SELL, "Item36")), " h" in (status(SELL, "Item36") or "")),
       (True, True))
win._ord_intervall_item_setzen(36, "Item36", standard=True)
pruefe("B7 'Standard wieder nutzen': Ausnahme weg, Standard 3 gilt",
       (config.load_settings().get("ord_intervall_item"),
        "3" in (status(SELL, "Item36") or "")), ({}, True))
win._ord_intervall_abfragen = _alt_ab

# --- B8 Order wird gefuellt (verschwindet) ---------------------------------
ORDERS[:] = [o for o in ORDERS if o["order_id"] != 9003]
laden()
pruefe("B8 gefuellte Order ist weg aus der Tabelle",
       sorted(namen(SELL)), ["Item34", "Item35", "Item37"])
# neue Order fuer dasselbe Item = neue order_id = neue, leere Uhr
ORDERS.append(order(9010, 36, 100.0, issued="2026-10-28T09:00:00Z"))
laden()
pruefe("B8 neue Order fuer dasselbe Item: eigene Uhr, nicht uebernommen -> dran",
       wartet(status(SELL, "Item36")), False)

# --- B9 zwei Orders desselben Items: getrennte Uhren -----------------------
ORDERS[:] = [order(9020, 50, 100.0), order(9021, 50, 99.0)]
laden()
pruefe("B9 zwei Orders desselben Items, beide dran",
       [wartet(status(SELL, "Item50"))] * 1, [False])
win._toggle_order_step(False); win._toggle_order_step(True)
win._orders_inner.setCurrentIndex(1)
win._ord_step_next()                      # nur die erste bearbeiten
laden()
zeilen = [(SELL.item(i, 0).text(), SELL.item(i, 5).text())
          for i in range(SELL.rowCount())]
pruefe("B9 nur EINE der zwei Orders wartet (Uhr je Order)",
       sorted(wartet(s) for _n, s in zeilen), [False, True])

# --- B10 Buy-Seite ----------------------------------------------------------
ORDERS[:] = [order(9030, 60, 50.0, buy=True), order(9031, 61, 50.0, buy=True)]
laden()
pruefe("B10 zwei Buy-Orders ueberboten, beide dran",
       [wartet(status(BUY, "Item60", sell=False)),
        wartet(status(BUY, "Item61", sell=False))], [False, False])
gang = next_klick(1, sell=False)
laden()
w = [wartet(status(BUY, "Item60", sell=False)),
     wartet(status(BUY, "Item61", sell=False))]
pruefe("B10 nach einem 'Next': genau eine Buy-Order wartet", sorted(w), [False, True])
gang2 = next_klick(2, sell=False)
pruefe("B10 weitere Klicks: nur die andere kommt dran (die wartende nie)",
       set(gang2) == ({60, 61} - set(gang)), True)

# --- B11 alles wartet: Meldung statt Sprung ---------------------------------
for t in (60, 61):
    pass
ORDERS[:] = [order(9040, 70, 100.0)]
laden()
next_klick(1)
laden()
OPENED.clear()
win._toggle_order_step(False); win._toggle_order_step(True)
win._orders_inner.setCurrentIndex(1)
win._ord_step_next()
pruefe("B11 wartet alles: nichts wird geoeffnet", OPENED, [])
pruefe("B11 ... und die Statuszeile sagt warum",
       "interval" in win.statusBar().currentMessage().lower()
       or "intervall" in win.statusBar().currentMessage().lower(), True)

# --- B12 Neustart: Uhr und Einstellung ueberleben ---------------------------
with store._conn() as cc:
    n_uhren = cc.execute(
        "SELECT COUNT(*) FROM order_intervall WHERE clock_ts IS NOT NULL").fetchone()[0]
pruefe("B12 Uhren stehen in der Datenbank (ueberleben einen Neustart)", n_uhren >= 1, True)
pruefe("B12 Standard-Intervall steht in den Einstellungen",
       config.load_settings().get("ord_intervall_tage"), 3)

time.time = _real_time
print()
print("ALLES GRUEN" if OK else "ROT - siehe oben")
sys.stdout.flush()
os._exit(0 if OK else 1)      # Worker-Threads des Fensters nicht abraeumen (sonst Abort)
