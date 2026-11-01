#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIMULATIONEN Multi-Hub-Einkauf (emm722-724), Nutzer 25.10.2026:
"mache selber ein paar simulationen mit verschiedensten szenarien".

Gerechnet wird AUSSCHLIESSLICH mit den echten Funktionen
(industry.multihub_leiter / multihub_split / multihub_pfn) - jede
Erwartung ist von Hand nachgerechnet und steht als Zahl im Code.

Szenarien:
  A  Ein Hub ist flach guenstiger             -> alles von dort
  B  Markttiefe: billigste Order zu klein     -> Split ueber die Leiter
  C  Fracht kippt die Wahl (445 vs 0 ISK/m3)  -> sperrig wandert,
     kompakt-teuer bleibt (der Fall des Nutzers: "spannend wirds wenn
     1 Hub keine Frachtkosten hat")
  D  Drei Hubs, verzahnte Leitern             -> Reihenfolge korrekt
  E  Item nur an einem Hub / an keinem        -> voll dort / Rueckfall
  F  Markt zu duenn                           -> rest wird GEMELDET
  G  mit_fracht True/False                    -> gleicher Hub, anderer
     Preis (Landepreis vs roher Orderpreis)
  H  Doppelzaehlungs-Probe: Landepreis-Summe == Rohkosten + Frachtsumme
     (genau die emm724-Verrechnung: Fracht steckt ENTWEDER im
     Materialpreis ODER in der Transportzeile, nie doppelt)
  I  Plan-Wechsel danach (Nutzer 25.10.: "simuliere auch was mit den
     einkaufslisten passiert wenn man nacher noch build from Reactions
     auf components wechselt"): die Hub-Kopierlisten rechnen bei JEDEM
     Klick frisch aus den aktuellen Plan-Zeilen (einkauf_posten +
     multihub_split) - gewechselte Bau/Kauf-Entscheidung = andere Liste,
     nichts Altes bleibt haengen. Die Buecher decken die GANZE Rezept-
     Kette (Scan ueber alle_items_der_kette), nicht nur die Kaufliste
     vom Scan-Zeitpunkt.
  J  Decryptor-Wechsel danach: ein NEU gewaehltes Item, das es zum
     Scan-Zeitpunkt im Plan nicht gab, hat kein Orderbuch -> es faellt
     sichtbar auf den gescannten Hub zurueck (nur im Copy-ALL-Knopf,
     im Hinweis gezaehlt) statt still zu verschwinden; erst ein neuer
     Scan holt es in die Hub-Listen.

Aufruf: QT_QPA_PLATFORM=offscreen python3 werkzeuge/sim_emm724.py
(Exit 0 = alles gruen; offscreen wegen des einkauf_posten-Imports aus
eve_trader.ui.mw_helpers fuer I/J)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from eve_trader import industry as I  # noqa: E402

OK = True


def pruefe(name, ist, soll):
    global OK
    gut = (ist == soll)
    OK = OK and gut
    print(("  OK   " if gut else "  ROT  ") + name
          + ("" if gut else f"  ist={ist} soll={soll}"))


T = 34          # Tritanium-artig: billig und (relativ) sperrig
M = 40          # Megacyte-artig: teuer und kompakt
X = 100
VOL = {T: 0.01, M: 0.01, X: 1.0}

print("A: Ein Hub flach guenstiger -> alles von dort")
b = {"jita": {X: [(100.0, 10000)]}, "hub2": {X: [(120.0, 10000)]}}
lt = I.multihub_leiter(b, X, {}, VOL[X])
sp, rest = I.multihub_split(lt, 500)
pruefe("A alles aus jita", (sp, rest), ({"jita": (500, 50000.0, 50000.0)}, 0))

print("B: Markttiefe - billigste Order deckt nur 200 von 500")
b = {"jita": {X: [(100.0, 200), (130.0, 9999)]},
     "hub2": {X: [(110.0, 9999)]}}
sp, rest = I.multihub_split(I.multihub_leiter(b, X, {}, VOL[X]), 500)
# 200 @100 jita, dann 300 @110 hub2 (130er-jita-Stufe bleibt liegen)
pruefe("B 200 jita + 300 hub2, exakte Kosten",
       (sp["jita"][0], sp["jita"][1], sp["hub2"][0], sp["hub2"][1], rest),
       (200, 20000.0, 300, 33000.0, 0))

print("C: Fracht kippt die Wahl (Nutzer-Fall Jita 445 / Heimat 0 ISK/m3)")
fracht = {"jita": 445.0}
# Tritanium: jita 5.00, heimat 8.00 - Landepreis jita 5+0.01*445=9.45
#   -> HEIMAT gewinnt trotz hoeherem Rohpreis (8.00 < 9.45)
b = {"jita": {T: [(5.0, 10**7)]}, "heim": {T: [(8.0, 10**7)]}}
lt = I.multihub_leiter(b, T, fracht, VOL[T])
pruefe("C sperrig-billig wandert zum frachtfreien Heimat-Hub",
       lt[0][2], "heim")
# Megacyte: jita 2'500, heimat 2'600 - Fracht 0.01*445=4.45 faellt nicht
#   ins Gewicht -> JITA bleibt (2'504.45 < 2'600)
b2 = {"jita": {M: [(2500.0, 10**6)]}, "heim": {M: [(2600.0, 10**6)]}}
pruefe("C kompakt-teuer bleibt in Jita",
       I.multihub_leiter(b2, M, fracht, VOL[M])[0][2], "jita")
# Kippunkt nachgerechnet: gleicher Rohpreis-Abstand (100), aber Volumen
# 0.3 m3 -> Fracht 133.50 > 100 -> jetzt kippt auch das teure Item.
pruefe("C ... bis das Volumen die Fracht ueber den Preisabstand hebt",
       I.multihub_leiter(b2, M, fracht, 0.3)[0][2], "heim")

print("D: Drei Hubs, verzahnte Leitern")
b = {"jita": {X: [(100.0, 50), (118.0, 50)]},
     "amarr": {X: [(104.0, 50)]},
     "rens": {X: [(101.0, 50), (200.0, 50)]}}
lt = I.multihub_leiter(b, X, {}, VOL[X])
pruefe("D Reihenfolge 100 jita < 101 rens < 104 amarr < 118 jita < 200 rens",
       [(e[3], e[2]) for e in lt],
       [(100.0, "jita"), (101.0, "rens"), (104.0, "amarr"),
        (118.0, "jita"), (200.0, "rens")])
sp, rest = I.multihub_split(lt, 170)
pruefe("D 170 Stueck = 50+50+50+20, Kosten exakt",
       (sp["jita"], sp["rens"], sp["amarr"], rest),
       ((70, 100.0 * 50 + 118.0 * 20, 100.0 * 50 + 118.0 * 20),
        (50, 5050.0, 5050.0), (50, 5200.0, 5200.0), 0))

print("E: Item nur an einem Hub / an keinem Hub")
b = {"jita": {}, "hub2": {X: [(300.0, 1000)]}}
sp, rest = I.multihub_split(I.multihub_leiter(b, X, {}, 1.0), 10)
pruefe("E nur hub2 hat Orders -> alles von dort",
       (sp, rest), ({"hub2": (10, 3000.0, 3000.0)}, 0))
basis = {X: 777.0, 999: 55.0}.get
fn = I.multihub_pfn(basis, b, {}, VOL)
pruefe("E unbekanntes Item faellt auf den gescannten Hub zurueck",
       fn(999), 55.0)
pruefe("E leere Buecher geben die Basisfunktion IDENTISCH zurueck",
       I.multihub_pfn(basis, {}, {}) is basis, True)

print("F: Markt zu duenn - der Rest wird gemeldet, nicht verschwiegen")
b = {"jita": {X: [(100.0, 30)]}, "hub2": {X: [(110.0, 40)]}}
sp, rest = I.multihub_split(I.multihub_leiter(b, X, {}, 1.0), 100)
pruefe("F 30+40 gedeckt, 30 bleiben offen",
       (sp["jita"][0], sp["hub2"][0], rest), (30, 40, 30))

print("G: mit_fracht entscheidet nur den PREIS, nie die Hub-Wahl")
b = {"jita": {T: [(5.0, 10**7)]}, "heim": {T: [(8.0, 10**7)]}}
fn_roh = I.multihub_pfn(basis, b, fracht, VOL, mit_fracht=False)
fn_land = I.multihub_pfn(basis, b, fracht, VOL, mit_fracht=True)
pruefe("G roher Orderpreis des GEWAEHLTEN Hubs (heim, 8.00)",
       fn_roh(T), 8.0)
pruefe("G Landepreis desselben Hubs (heim ohne Fracht = 8.00)",
       fn_land(T), 8.0)
b2 = {"jita": {T: [(5.0, 10**7)]}}        # nur Jita -> Fracht sichtbar
pruefe("G Landepreis traegt die Hub-Fracht (5 + 0.01 x 445 = 9.45)",
       round(I.multihub_pfn(basis, b2, fracht, VOL,
                            mit_fracht=True)(T), 2), 9.45)
pruefe("G roher Preis ohne Fracht (5.00)",
       I.multihub_pfn(basis, b2, fracht, VOL, mit_fracht=False)(T), 5.0)

print("H: Keine Doppelzaehlung - Landepreis-Summe == Rohkosten + Fracht")
# Gemischter Einkauf ueber zwei Hubs mit verschiedenen Saetzen; die
# emm724-Verrechnung sagt: Fracht steckt ENTWEDER im Materialpreis
# (Landepreise) ODER in der Transportzeile (Rohkosten + Frachtsumme) -
# beide Wege muessen auf denselben Gesamtbetrag kommen.
fracht_h = {"jita": 445.0, "hub2": 120.0}
b = {"jita": {X: [(100.0, 300)]}, "hub2": {X: [(102.0, 300)]}}
vol_x = 0.02
lt = I.multihub_leiter(b, X, fracht_h, vol_x)
sp, rest = I.multihub_split(lt, 500)
roh = sum(v[1] for v in sp.values())
landed = sum(v[2] for v in sp.values())
fracht_sum = sum(v[0] * vol_x * fracht_h[h] for h, v in sp.items())
pruefe("H landed == roh + Frachtsumme (auf den Cent)",
       round(landed, 6), round(roh + fracht_sum, 6))
pruefe("H ... und der Split selbst: hub2 zuerst (102+2.4 < 100+8.9)",
       (sp["hub2"][0], sp["jita"][0], rest), (300, 200, 0))

print("I: Build-from-Wechsel danach - Hub-Listen folgen dem Plan")
from eve_trader.ui.mw_helpers import einkauf_posten  # noqa: E402
# Kette: Komponente 501 (gebaut aus Moon-Mats 601/602). Die Buecher
# kennen ALLE DREI (Scan geht ueber alle_items_der_kette, nicht nur
# ueber die Kaufliste vom Scan-Zeitpunkt).
b_i = {"jita": {501: [(1000.0, 10**6)],
                601: [(10.0, 10**7)], 602: [(20.0, 10**7)]},
       "heim": {501: [(980.0, 10**6)],
                601: [(12.0, 10**7)], 602: [(18.0, 10**7)]}}


def hub_listen(rows, baut):
    """Genau der Rechenweg der Copy:-Knoepfe (_copy_rows_hub): Posten
    aus den AKTUELLEN Zeilen, je Posten Leiter+Split, je Hub die
    Stueckzahlen. Kein Zwischenspeicher - wie im Dialog."""
    posten, _, _ = einkauf_posten(rows, "missing", baut)
    aus = {}
    for _tid, _nm, _q in posten:
        _lt = I.multihub_leiter(b_i, _tid, {}, 0.0)
        if not _lt:
            aus.setdefault("_nur_scan", []).append(_nm)
            continue
        _sp, _r = I.multihub_split(_lt, _q)
        for _h, (_n, _, _) in _sp.items():
            aus.setdefault(_h, []).append((_nm, _n))
    return aus


# Stand 1: "build from Reactions" - 501 wird GEBAUT, gekauft werden
# die Moon-Mats. Die Komponente steht in den Zeilen, faellt aber als
# Gebautes raus (einkauf_posten-Regel 1).
rows1 = [{"tid": 501, "name": "Komponente", "missing": 150},
         {"tid": 601, "name": "MoonA", "missing": 300},
         {"tid": 602, "name": "MoonB", "missing": 200}]
l1 = hub_listen(rows1, baut={501})
pruefe("I Stand 1: nur Moon-Mats, 601 nach Jita (10<12), 602 nach Heim",
       (l1.get("jita"), l1.get("heim")),
       ([("MoonA", 300)], [("MoonB", 200)]))
# Stand 2: auf "build from Components" gewechselt - 501 wird GEKAUFT,
# die Moon-Mats verschwinden aus den Zeilen (Plan braucht sie nicht
# mehr). Dieselben Knoepfe, frisch gerechnet: nichts Altes haengt.
rows2 = [{"tid": 501, "name": "Komponente", "missing": 150}]
l2 = hub_listen(rows2, baut=set())
pruefe("I Stand 2: nur noch die Komponente, nach Heim (980<1000)",
       (l2.get("heim"), l2.get("jita"), l2.get("_nur_scan")),
       ([("Komponente", 150)], None, None))

print("J: Decryptor-Wechsel danach - neues Item ohne Buch faellt "
      "sichtbar zurueck")
# Beim Scan war Decryptor 701 im Plan (Buch da), 703 = Datacore.
b_j = {"jita": {701: [(500000.0, 1000)], 703: [(80000.0, 10**6)]},
       "heim": {703: [(75000.0, 10**6)]}}
rows_j = [{"tid": 702, "name": "DecryptorNeu", "missing": 10},
          {"tid": 703, "name": "Datacore", "missing": 72}]
posten_j, _, _ = einkauf_posten(rows_j, "missing", set())
aus_j = {}
for _tid, _nm, _q in posten_j:
    _lt = I.multihub_leiter(b_j, _tid, {}, 0.0)
    if not _lt:
        aus_j.setdefault("_nur_scan", []).append(_nm)
        continue
    _sp, _ = I.multihub_split(_lt, _q)
    for _h, (_n, _, _) in _sp.items():
        aus_j.setdefault(_h, []).append((_nm, _n))
pruefe("J neuer Decryptor: kein Buch -> nur-Scan-Hub (Copy-ALL, "
       "Hinweis zaehlt ihn)", aus_j.get("_nur_scan"), ["DecryptorNeu"])
pruefe("J Datacore-Menge folgt dem NEUEN Plan (72, nach Heim 75k<80k)",
       aus_j.get("heim"), [("Datacore", 72)])
pruefe("J alter Decryptor 701 taucht nirgends mehr auf",
       any("701" in str(v) or any(_n == 701 for _n, *_ in v)
           for k, v in aus_j.items() if k != "_nur_scan"), False)

print()
print("ALLE SZENARIEN GRUEN" if OK else "MINDESTENS EIN SZENARIO ROT")
sys.exit(0 if OK else 1)
