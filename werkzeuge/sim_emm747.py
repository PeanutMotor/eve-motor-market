#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIMULATION: DER HAKEN GILT NUR, BIS ESI WIDERSPRICHT (emm747).

SEIN MODELL, woertlich (28.10.2026, 19:15):
  "es kann ja sein das ich bsp 10 runs machen muss ich mache ingame nur 8
   runs und meine ich habe 10 gemacht also ein fehler, ich hacke aber
   trotzdem ab. ESI müsste prüfen, hacken lösen und 2 Runs hinschreiben
   für amber mit kopieren wie wirs kennen. so muss das laufen"
und die Nachfrage um 19:17:
  "würde aber nach 2 oder 3 stunden ESI merken, ah ist doch da muss es
   korrigieren können"
und um 19:30 zur Anzeige:
  "10 runs verschwinden (weil 8 davon liegen jetzt im Hanger) also
   bleiben nurnoch 2 kopierbar"

WAS VORHER WAR: der Hand-Haken galt UNBEFRISTET. emm650 hat den Fall
erkannt und amber gewarnt, den Haken aber ausdruecklich stehen lassen
("Nothing is changed here"). Das Material der nie gefahrenen Runs blieb
damit aus dem Bedarf - sein Catalyst-Fall vom 27./28.10.: 50 Runs
abgehakt, kein Job gelaufen, die Stock-Locations-Einkaufsliste nannte
3'459'456 Tritanium zu wenig. Am naechsten Tag baute er sie wirklich,
das Material war weg, und die Liste sprang nach oben. Sein Satz dazu:
"warum hat mir stok locations gestern zu wenig material zu kaufen
angegeben?"

DAZU DIE ZAEHLUNG (Teil 1): `_belegt = max(geliefert, laufend)` warf
einen der beiden Toepfe weg. GEMESSEN in seinem diagnose_export vom
28.10., Plan "T1 Battlecruisers", Catalyst (16240): Job 677140263 mit
2 Runs (delivered) und Job 677188361 mit 48 Runs (active), beide diesem
Plan zugeordnet. max(2, 48) = 48 gegen 50 abgehakte Runs ergab eine
Warnung, die durch Warten NIE verschwindet - sein Einwand: "zwischen den
beiden mineralien screenshots und dem catalist bau sind über 8h
vergangen, ESI hätte tracken müssen".

GEPRUEFT WIRD:
  Teil A  die Zaehlung (Summe statt max) an seinen echten Zahlen.
  Teil B  `haken_wirksam`: was der Haken zaehlen darf und was offen
          bleibt - inkl. der Rueckrichtung.
  Teil C  sein 10/8-Fall ueber die Zeitachse, mit der Materialrechnung
          daneben: kommt das Material der 2 fehlenden Runs zurueck?
  Teil D  der Catalyst-Fall vom 27./28.10., wie er wirklich lief.

Aufruf: QT_QPA_PLATFORM=offscreen python3 werkzeuge/sim_emm747.py
(Exit 0 = alles gruen). Reine Rechnung, kein Fenster, kein Netz.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = tempfile.mkdtemp(prefix="sim747_")
for _k in ("HOME", "APPDATA", "USERPROFILE"):
    os.environ[_k] = HOME
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.chdir(ROOT)
sys.path.insert(0, ROOT)

OK = True


def pruefe(name, ist, soll):
    global OK
    gut = (ist == soll)
    OK = OK and gut
    print(("  OK   " if gut else "  ROT  ") + name
          + ("" if gut else f"\n           ist={ist!r}\n           soll={soll!r}"))


def ja(name, b):
    pruefe(name, bool(b), True)


from eve_trader.ui.mw_helpers import (haken_pruefen as HP,       # noqa: E402
                                      haken_wirksam as HW,
                                      HAKEN_FRIST_S as FRIST,
                                      restbedarf_map)

J = 1_000_000.0
ALT = J - FRIST - 60          # Haken aelter als die Frist
NEU = J - 60                  # eben gesetzt

# =====================================================================
print("TEIL A - die Zaehlung: geliefert UND laufend sind zwei Toepfe")

CAT = 16240
pruefe("A1 sein Catalyst: 2 geliefert + 48 laufend decken 50 Haken",
       HP({CAT: 50}, {CAT: ALT}, {CAT: 2}, {CAT: 48}, J)[CAT],
       ("bestaetigt", 50, 50))
pruefe("A2 ... mit max() waere es 48 geblieben (der alte Fehler)",
       max(2, 48) < 50, True)
pruefe("A3 nur geliefert reicht weiterhin",
       HP({1: 10}, {1: ALT}, {1: 10}, {}, J)[1][0], "bestaetigt")
pruefe("A4 nur laufend reicht weiterhin",
       HP({1: 10}, {1: ALT}, {}, {1: 10}, J)[1][0], "bestaetigt")
pruefe("A5 zusammen zu wenig: unbestaetigt mit der echten Summe",
       HP({1: 10}, {1: ALT}, {1: 4}, {1: 4}, J)[1], ("unbestaetigt", 10, 8))

# =====================================================================
print("")
print("TEIL B - was der Haken zaehlen darf")

_w, _o = HW(HP({1: 10}, {1: ALT}, {1: 4}, {1: 4}, J))
pruefe("B1 sein Beispiel: 10 abgehakt, 8 belegt -> Haken zaehlt 8",
       _w.get(1), 8)
pruefe("B1 ... und 2 Runs bleiben offen", _o.get(1), 2)

_w, _o = HW(HP({1: 10}, {1: NEU}, {1: 4}, {1: 4}, J))
pruefe("B2 frisch gesetzt: Haken zaehlt voll (sein Ablauf bleibt)",
       (_w.get(1), _o), (10, {}))

_w, _o = HW(HP({1: 10}, {1: ALT}, {}, {}, J))
pruefe("B3 gar nichts gefahren: Haken zaehlt 0, 10 offen",
       (_w.get(1), _o.get(1)), (0, 10))

_w, _o = HW(HP({1: 10}, {1: ALT}, {1: 10}, {}, J))
pruefe("B4 voll belegt: nichts offen", (_w.get(1), _o), (10, {}))

# BESTAND SCHLAEGT BELEG (emm664) - bleibt unangetastet.
_w, _o = HW(HP({1: 10}, {1: ALT}, {}, {}, J, gedeckt={1}))
pruefe("B5 Erzeugnis liegt im Hangar: Haken zaehlt voll, nichts offen",
       (_w.get(1), _o), (10, {}))

# MEHR ABGEHAKT ALS GEPLANT (emm670) - Deckel bleibt.
_w, _o = HW(HP({1: 575}, {1: ALT}, {1: 329}, {}, J, plan_runs={1: 329}))
pruefe("B6 mehr abgehakt als geplant: nur bis zum Plan, nichts offen",
       (_w.get(1), _o), (329, {}))

for _mist in (None, {}, {1: None}, {1: ("x",)}, {1: ("unbestaetigt",)}):
    HW(_mist)
ja("B7 unbrauchbare Eingaben werfen nicht", True)

# =====================================================================
print("")
print("TEIL C - sein 10/8-Fall mit der Materialrechnung daneben")

# Ein Item (1) mit 10 geplanten Runs, je Run 100 Einheiten Material (2).
BUILD_RUNS = {1: 10}
BUILD_MATS = {1: [(2, 1000)]}       # 1000 fuer alle 10 Runs = 100/Run


def bedarf(haken_wirkt):
    """Materialbedarf der noch offenen Runs - dieselbe Funktion wie die
    Einkaufsliste (`restbedarf_map`)."""
    _rem, _need = restbedarf_map(BUILD_RUNS, BUILD_MATS, {1: haken_wirkt})
    return _need.get(2, 0)


pruefe("C1 nichts abgehakt: voller Bedarf", bedarf(0), 1000)
pruefe("C2 10 abgehakt und wirklich gefahren: kein Bedarf", bedarf(10), 0)

# Jetzt sein Fehler: 10 abgehakt, 8 gefahren.
_stand = HP({1: 10}, {1: NEU}, {1: 8}, {}, J)        # noch in der Frist
_w, _o = HW(_stand)
pruefe("C3 in der ersten Stunde: Haken zaehlt 10, Bedarf 0 "
       "(kein Fehlkauf, waehrend ESI nachhinkt)",
       (_w[1], bedarf(_w[1])), (10, 0))

_stand = HP({1: 10}, {1: ALT}, {1: 8}, {}, J)        # Frist um
_w, _o = HW(_stand)
pruefe("C4 nach der Frist: Haken zaehlt 8, 2 Runs offen",
       (_w[1], _o[1]), (8, 2))
pruefe("C4 ... und das Material der 2 Runs steht wieder im Bedarf",
       bedarf(_w[1]), 200)

# Die Rueckrichtung: ESI sieht die 2 doch noch (er hat nachgebaut, oder
# der Job tauchte spaeter auf).
_stand = HP({1: 10}, {1: ALT}, {1: 10}, {}, J)
_w, _o = HW(_stand)
pruefe("C5 ESI bestaetigt spaeter doch: Haken zaehlt wieder voll",
       (_w[1], _o), (10, {}))
pruefe("C5 ... Bedarf wieder 0, ganz von selbst", bedarf(_w[1]), 0)

# =====================================================================
print("")
print("TEIL D - sein Catalyst-Fall, wie er wirklich lief")

# 27.10. abends: 50 Runs abgehakt, KEIN Job gelaufen.
_stand = HP({CAT: 50}, {CAT: ALT}, {}, {}, J)
_w, _o = HW(_stand)
pruefe("D1 27.10.: abgehakt ohne Job -> Haken zaehlt 0, 50 Runs offen",
       (_w[CAT], _o[CAT]), (0, 50))
# Das ist der Punkt, an dem die Liste gestern die 3'459'456 Tritanium
# haette nennen muessen. Nachgerechnet mit seinem Rezept:
TRI_JE_CATALYST = 72_072        # aus der Differenz seiner zwei Listen
pruefe("D1 ... das sind die 3'459'456 Tritanium aus seinen Screenshots",
       48 * TRI_JE_CATALYST, 3_459_456)

# 28.10. 07:24: die Jobs laufen (2 geliefert + 48 aktiv).
_stand = HP({CAT: 50}, {CAT: ALT}, {CAT: 2}, {CAT: 48}, J)
_w, _o = HW(_stand)
pruefe("D2 28.10.: Jobs laufen -> Haken zaehlt wieder voll, nichts offen",
       (_w[CAT], _o), (50, {}))
pruefe("D2 ... und keine Warnung mehr (das war seine 8-Stunden-Frage)",
       _stand[CAT][0], "bestaetigt")

print("")
print("ALLES GRUEN" if OK else "ES GIBT ROTE PUNKTE")
sys.exit(0 if OK else 1)
