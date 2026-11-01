#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIMULATION: DER PHANTOM-OFEN DES UNBELEGTEN HAKENS (emm748).

SEIN BEFUND, woertlich (28.10.2026):
  "Und warum mhabe ich zu wenig Fernide Carbide, wenn der Bauplan und
   Stocklocations nicht erkennen das ich zu wenig habe? ausserdem habe
   ich auch keine Fernide Carbide mehr in irgenwelchen reaction
   Bauslots am laufen"
  "Dasselbe ist bei Amarr Plan Fermionic Condensates"
  "nur dafür habe ich tatsächlich zu wenig Material um es nachzubauen,
   aber Stock Location sieht es nicht und der Bauplan auch nicht"
und zur Dringlichkeit (zum selben Fehlerbild):
  "ja unbedingt solche fehler dürfen nicht passiern"

GEMESSEN, NICHT VERMUTET. Quellen: seine settings.json (22'045'982 B,
gelesen 28.10.2026 19:00) und sein berichte/diagnose_export.json
(erstellt 28.10.2026 18:28). Beide Faelle liessen sich Ziffer fuer
Ziffer nachrechnen:

  Plan "Minmatar 1" (id 1791918437302)
    Fernite Carbide (16673)   braucht 33'600 · Hangar 12'412 · fehlen 21'188
    319 Runs geplant, 319 abgehakt, 10'000 Stueck je Run
  Plan "Multibuildplan Amarr 1" (id 1791488606728)
    Fermionic Condensates (17317) braucht 4'360 · Hangar 2'905 · fehlen 1'455

DIE URSACHE: `_nachlauf_fuer_plan` bringt seit emm740 abgehakte Runs
OHNE ESI-Beleg auf die OFEN-Seite - also auf die Haben-Seite der
Materialbilanz. Das war fuer das 5-Minuten-Loch gedacht (abgehakt,
Job laeuft wirklich, ESI meldet ihn noch nicht). Unbefristet wird
daraus ein Phantom-Bestand: 319 x 10'000 = 3'190'000 Stueck, die es
nirgends gibt. Gegen einen Restbedarf von 33'600 verschwindet damit
jede Luecke, und `nachlauf_runs` schweigt - genau sein Bild.

DER FIX ist die Regel, die emm747 heute frueh fuer
`_rest_geliefert_jetzt` bekommen hat, an ihrem ZWEITEN Vorkommen
(Arbeitsregel 9): der Haken wird auf `haken_wirksam` gekappt. Nach
Ablauf der Frist zaehlt nur noch, was ESI belegt - und das steckt
ueber `_beleg7` ohnehin schon drin. INNERHALB der Frist bleibt
emm740 unveraendert.

Aufruf: QT_QPA_PLATFORM=offscreen python3 werkzeuge/sim_emm748.py
(Exit 0 = alles gruen). Reine Rechnung, kein Fenster, kein Netz.
"""
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = tempfile.mkdtemp(prefix="sim748_")
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


from eve_trader.ui.main_window import MainWindow as MW      # noqa: E402
from eve_trader.ui.mw_helpers import (HAKEN_FRIST_S,        # noqa: E402
                                      nachlauf_runs)

FRIST = HAKEN_FRIST_S


class Fenster:
    """Genau die Felder, die `_nachlauf_fuer_plan` und
    `_haken_stand_jetzt` lesen - mehr braucht die Rechnung nicht."""

    _nachlauf_fuer_plan = MW._nachlauf_fuer_plan
    _haken_stand_jetzt = MW._haken_stand_jetzt

    def __init__(self, checked=(), by_key=(), jobs=(), sicher=(),
                 erledigt=(), erledigt_ts=(), delivered=()):
        self._bd_runplan_checked = set(checked)
        self._bd_runplan_runs_by_key = dict(by_key)
        self._bd_active_jobs_map = dict(jobs)
        self._bd_runplan_delivered_sicher = dict(sicher)
        self._bd_runplan_erledigt = dict(erledigt)
        self._bd_runplan_erledigt_ts = dict(erledigt_ts)
        self._bd_runplan_delivered = dict(delivered)

    def _log_exception(self, *a):
        raise AssertionError(f"_log_exception: {a}")


# =====================================================================
# SEIN FALL, 1:1 NACHGEBAUT
# Fernite Carbide: 319 Runs geplant, 10'000 je Run.
# Verbraucher Electrolytic Capacitor Unit: 1'400 offene Runs, 24 FC je
# Run = 33'600 Stueck (gerechnet aus seinem build_mats: 247'560 fuer
# 10'315 Runs). Im Hangar liegen 12'412.
FC, ECU, ROH = 16673, 11557, 16656
HANGAR = {FC: 12412}
PLAN = {
    "build_runs": {FC: 319, ECU: 10315},
    "build_made": {FC: 3190000, ECU: 10315},
    "build_mats": {ECU: [(FC, 247560)], FC: [(ROH, 31262)]},
}
# 8'915 der 10'315 ECU-Runs sind erledigt -> 1'400 offen.
REST = {FC: 0, ECU: 1400}
HAKEN = {"reaction_2|2113366524|16673": (FC, 319)}
JETZT = time.time()


def lauf(fenster):
    return fenster._nachlauf_fuer_plan(PLAN, stock=dict(HANGAR),
                                       rest_runs=dict(REST))


# =====================================================================
print("TEIL A - die Zahlen stimmen mit seinen Bildschirmfotos ueberein")

_bedarf = -(-247560 // 10315) * 1400          # aufgerundet je Run, wie der Plan
pruefe("A1 Electrolytic Capacitor Unit, 1'400 offene Runs -> 33'600 "
       "Fernite Carbide", _bedarf, 33600)
pruefe("A2 ... im Hangar liegen 12'412", HANGAR[FC], 12412)
pruefe("A3 ... es fehlen die 21'188 aus seinem Bild",
       _bedarf - HANGAR[FC], 21188)
pruefe("A4 je Run liefert die Reaktion 10'000 Stueck",
       PLAN["build_made"][FC] // PLAN["build_runs"][FC], 10000)

# =====================================================================
print("")
print("TEIL B - der Schaden: 319 abgehakte Runs ohne jeden ESI-Beleg")

# Ohne Zeitstempel ist der Haken "unbestaetigt" erst nach der Frist;
# hier ist er ALT - also genau sein Fall (abgehakt vor Tagen).
_alt = JETZT - FRIST - 60
_schaden = Fenster(checked=set(HAKEN), by_key=HAKEN,
                   erledigt={f"Lezflow|{FC}": 319},
                   erledigt_ts={f"Lezflow|{FC}": _alt})
# Zum Vergleich: dieselbe Rechnung MIT dem Phantom-Ofen von emm740.
_phantom = {FC: 319 * 10000}
_je = {FC: 10000, ECU: 1}
_erl = {FC: 319, ECU: 8915}
_nl_alt, _ = nachlauf_runs(PLAN["build_runs"], PLAN["build_mats"], _je,
                           _erl, HANGAR, _phantom)
pruefe("B1 mit dem Phantom-Ofen (3'190'000 Stueck, die es nirgends "
       "gibt) meldet die Rechnung NICHTS", _nl_alt.get(FC, 0), 0)
pruefe("B2 ... obwohl 21'188 Stueck wirklich fehlen",
       33600 - 12412 > 0, True)
_nl_ohne, _ = nachlauf_runs(PLAN["build_runs"], PLAN["build_mats"], _je,
                            _erl, HANGAR, {})
pruefe("B3 ohne Phantom-Ofen waeren es 3 Nachlauf-Runs "
       "(21'188 / 10'000, aufgerundet)", _nl_ohne.get(FC, 0), 3)

# =====================================================================
print("")
print("TEIL C - mit der Kappung (emm748)")

_nl, _kauf = lauf(_schaden)
pruefe("C1 der alte Haken wird auf das Belegte gekappt -> der Nachlauf "
       "ist wieder da", _nl.get(FC, 0), 3)
ja("C2 ... und die Kette darunter wird mitgerechnet (Fernite Alloy "
   "muss gekauft werden)", _kauf.get(ROH, 0) > 0)

# ESI belegt die Runs doch (Job laeuft): kein Nachlauf mehr noetig,
# der Output kommt wirklich.
_belegt = Fenster(checked=set(HAKEN), by_key=HAKEN,
                  jobs={FC: [{"runs": 319}]},
                  erledigt={f"Lezflow|{FC}": 319},
                  erledigt_ts={f"Lezflow|{FC}": _alt})
_nl_b, _ = lauf(_belegt)
pruefe("C3 ESI sieht die 319 Runs laufen: kein Nachlauf (der Ofen ist "
       "echt)", _nl_b.get(FC, 0), 0)

# Sein echter Stand heute: 2 Runs laufen wirklich (fertig 20:08 UTC).
_zwei = Fenster(checked=set(HAKEN), by_key=HAKEN,
                jobs={FC: [{"runs": 2}]},
                erledigt={f"Lezflow|{FC}": 319},
                erledigt_ts={f"Lezflow|{FC}": _alt},
                delivered={FC: 317})
_nl_z, _ = lauf(_zwei)
pruefe("C4 sein Stand heute (317 belegt + 2 laufende Runs = 20'000 "
       "Stueck unterwegs): 1 Run fehlt noch", _nl_z.get(FC, 0), 1)

# =====================================================================
print("")
print("TEIL D - emm740 bleibt innerhalb der Frist unangetastet")

# Sein 5-Minuten-Loch: eben abgehakt, ESI sieht noch nichts. Der Haken
# muss tragen, sonst springt der Bedarf sofort nach dem Klick hoch
# (sein Befund vom 27.10.: "+242" wurde zu "+183'750").
_frisch = Fenster(checked=set(HAKEN), by_key=HAKEN,
                  erledigt={f"Lezflow|{FC}": 319},
                  erledigt_ts={f"Lezflow|{FC}": JETZT - 60})
_nl_f, _ = lauf(_frisch)
pruefe("D1 eben abgehakt: der Haken traegt weiterhin voll, kein "
       "Nachlauf-Sprung", _nl_f.get(FC, 0), 0)

# Und die Rueckrichtung: faellt der Beleg spaeter doch aus, korrigiert
# sich das von selbst - es wird nichts gespeichert.
_spaet = Fenster(checked=set(HAKEN), by_key=HAKEN,
                 erledigt={f"Lezflow|{FC}": 319},
                 erledigt_ts={f"Lezflow|{FC}": _alt})
pruefe("D2 dieselbe Lage nach Ablauf der Frist: der Nachlauf erscheint, "
       "ohne dass der Nutzer etwas tut", lauf(_spaet)[0].get(FC, 0), 3)

# Eine Attrappe OHNE `_haken_stand_jetzt` (so rufen aeltere Pruefungen)
# darf nicht abstuerzen und behaelt das Verhalten von emm740.
class _Schlank:
    _nachlauf_fuer_plan = MW._nachlauf_fuer_plan

    def __init__(self):
        self._bd_runplan_checked = set(HAKEN)
        self._bd_runplan_runs_by_key = dict(HAKEN)
        self._bd_active_jobs_map = {}
        self._bd_runplan_delivered_sicher = {}

    def _log_exception(self, *a):
        raise AssertionError(f"_log_exception: {a}")


pruefe("D3 Attrappe ohne `_haken_stand_jetzt`: kein Absturz, Verhalten "
       "wie vor emm748",
       _Schlank()._nachlauf_fuer_plan(PLAN, stock=dict(HANGAR),
                                      rest_runs=dict(REST))[0].get(FC, 0), 0)

# =====================================================================
print("")
print("TEIL E - sein zweiter Fall: Fermionic Condensates (Amarr 1)")

# 13 Runs geplant, 200 Stueck je Run, Hangar 2'905, Bedarf 4'360.
# Verbraucher Antimatter Reactor Unit: 2'180 offene Runs zu je 2 Stueck.
FCO, ARU = 17317, 11539
PLAN_A = {
    "build_runs": {FCO: 13, ARU: 2180},
    "build_made": {FCO: 2600, ARU: 2180},
    "build_mats": {ARU: [(FCO, 4360)], FCO: [(ROH, 1300)]},
}
_K_A = "reaction_2|2113366524|17317"
_a = Fenster(checked={_K_A}, by_key={_K_A: (FCO, 13)},
             erledigt={f"Lezflow|{FCO}": 13},
             erledigt_ts={f"Lezflow|{FCO}": _alt})
_nl_a, _ = _a._nachlauf_fuer_plan(PLAN_A, stock={FCO: 2905},
                                  rest_runs={FCO: 0, ARU: 2180})
pruefe("E1 es fehlen 1'455 Stueck - das sind 8 Runs zu 200",
       -(-(4360 - 2905) // 200), 8)
pruefe("E2 ... und genau die meldet der Nachlauf jetzt",
       _nl_a.get(FCO, 0), 8)

print("")
print("ALLES GRUEN" if OK else "ES GIBT ROTE PUNKTE")
sys.exit(0 if OK else 1)
