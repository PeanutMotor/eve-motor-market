#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIMULATION: ZWEI BAUPLAENE, DIE GLEICHZEITIG LADEN (emm746).

DER AUFTRAG, woertlich (Nutzer 28.10.2026, 16:53): "prüfe diesen möglich
pfad simuliere ihn bitte" - gemeint war die Frage aus meiner
emm742-Abschlussmeldung: kann sich ein Bauplan-Fenster auch dann mit
fremden Daten fuellen, wenn man gar keinen zweiten Plan oeffnen wollte?

SEIN BEFUND VOM 27.10.2026, 21:23: "ich habe einen Minmatar Plan offen,
doch da kommen plötzlich alles Amarr Components vor WTF" - im Titel
stand "Build plan - Gallente 1". Drei verschiedene Plaene in einem
Fenster.

WAS DER CODE HERGIBT (gelesen, nicht vermutet):
  * emm742 sperrt ueber `_bauplan_sperre_meldung()` - die erkannte bis
    heute nur ein SICHTBARES Dialog-Fenster.
  * Zwischen Klick und Fenster liegt ein Worker-Lauf. Beim Nutzer dauert
    der bei Multi-Bauplaenen Minuten (27.09.2026: "das Oeffnen dauert
    sehr lange, Multi-Bauplaene mehrere Minuten"). Solange ist
    `_bd_dialog` None.
  * `job()` in open_build_detail setzt 19 geteilte Felder AUS DEM FADEN,
    darunter `_bd_recipes`, `_bd_name`, `_bd_type`, `_bd_groups`,
    `_bd_pricemap`, `_bd_reaction_stages`.
  * Wer zuerst fertig wird, baut das Fenster - sein Titel kommt aus dem
    LOKALEN `name`-Parameter, nicht aus den Feldern. Der zweite wird vom
    Auffangnetz in `_show_build_detail` abgewiesen, seine Felder bleiben.

=> Fenstertitel von Plan A, Inhalt von Plan B. Genau sein Bild.

Dieses Skript stellt das nach: Teil A zeigt den SCHADEN ohne Schloss
(die Sperre wird dafuer stillgelegt), Teil B zeigt, dass das Schloss ihn
verhindert, Teil C prueft die Notbremsen - Verfallsfrist, Abbrechen,
Fehlschlag -, damit das Schloss niemandem den Bauplan zusperrt.

Aufruf: QT_QPA_PLATFORM=offscreen python3 werkzeuge/sim_emm746.py
(Exit 0 = alles gruen). Wegwerf-Ordner, echte Daten bleiben unberuehrt.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = tempfile.mkdtemp(prefix="sim746_")
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


def ja(name, bedingung):
    pruefe(name, bool(bedingung), True)


from PySide6.QtWidgets import QApplication                 # noqa: E402

app = QApplication.instance() or QApplication([])

from eve_trader import industry as I                       # noqa: E402
from eve_trader import store                               # noqa: E402
from eve_trader.ui import main_window as _MW               # noqa: E402
from eve_trader.ui.main_window import MainWindow           # noqa: E402

store.init_db()
win = MainWindow()
win._erste_einrichtung_pruefen = lambda *a, **k: None
win._tutorial_erstfrage = lambda *a, **k: None
win._erststart_rezepte_anbieten = lambda *a, **k: None

# Meldungen abfangen statt anzeigen (sonst wartet ein modaler Dialog).
MELDUNGEN = []
_MW.QMessageBox.information = lambda *a, **k: MELDUNGEN.append(
    " ".join(str(x) for x in a[1:3]))

# ---------------------------------------------------------------------
# DER WORKER WIRD ANGEHALTEN. `self._run` sammelt die Jobs nur ein,
# statt sie zu starten - so laesst sich exakt die Reihenfolge nachstellen,
# die beim Nutzer durch die lange Ladezeit entsteht:
#   Klick A -> Klick B -> A rechnet fertig -> B rechnet fertig
GESAMMELT = []


def _run_sammeln(worker, done_cb, fail_cb=None, err_prefix=None, label=None,
                 overlay=True):
    # WIE DIE ECHTE `_run`: ihr erster Schritt ist
    # `self._workers.append(worker)`. Daran haengt das Lade-Schloss (es
    # fragt, ob der Worker noch laeuft) - ohne diese Zeile stellt die
    # Simulation ein Rennen nach, das es so nicht gibt, und meldet einen
    # Fehler, der keiner ist. (Erster Lauf dieser Datei: genau das.)
    win._workers.append(worker)
    GESAMMELT.append({"job": worker, "done": done_cb, "fail": fail_cb,
                      "label": label})


win._run = _run_sammeln
# sde_ready/Snapshot: der Lauf soll bis zum Worker kommen.
I.sde_ready = lambda: True
store.get_snapshot = lambda *a, **k: [{"type_id": 100, "sell": 1.0}]
win._bau_rollen_netz = lambda *a, **k: None
win._maybe_autodiscover_structures = lambda *a, **k: None

A_TID, A_NAME = 601, "Gallente 1"
B_TID, B_NAME = 602, "Minmatar 1"


def klick(tid, name):
    """Ein Klick auf einen Bauplan - der echte Weg."""
    vorher = len(GESAMMELT)
    MELDUNGEN.clear()
    win.open_build_detail(tid, name, fresh=True)
    return len(GESAMMELT) > vorher          # True = Worker gestartet


# =====================================================================
print("TEIL A - der Schaden OHNE Schloss (so war es bis emm746)")

win._bd_lade_frei()
_echt = win._bd_laedt_gerade
win._bd_laedt_gerade = lambda: False        # Schloss stilllegen
try:
    pruefe("A1 erster Klick startet einen Ladevorgang",
           klick(A_TID, A_NAME), True)
    pruefe("A1 ... und es ist noch KEIN Fenster offen (die emm742-Sperre "
           "kann hier nichts sehen)", win._offener_bauplan(), None)
    pruefe("A2 zweiter Klick waehrend des Ladens startet einen ZWEITEN",
           klick(B_TID, B_NAME), True)
    pruefe("A2 ... ohne jede Meldung an den Nutzer", MELDUNGEN, [])
    pruefe("A3 zwei Worker gleichzeitig unterwegs", len(GESAMMELT), 2)
    # Die Felder tragen schon den ZWEITEN Plan, obwohl der erste laeuft.
    pruefe("A4 die geteilten Felder gehoeren bereits Plan B",
           getattr(win, "_bd_bp_type", None), B_TID)
finally:
    win._bd_laedt_gerade = _echt

# =====================================================================
print("")
print("TEIL B - mit Schloss (emm746)")

GESAMMELT.clear()
win._bd_lade_frei()
win._bd_bp_type = None
pruefe("B1 erster Klick startet den Ladevorgang", klick(A_TID, A_NAME), True)
ja("B1 ... das Schloss ist zu", win._bd_laedt_gerade())
pruefe("B1 ... und es merkt sich, WER laedt",
       getattr(win, "_bd_lade_name", None), A_NAME)

_vorher_felder = {k: getattr(win, k, None) for k in
                  ("_bd_bp_type", "_bd_name", "_bd_type", "_bd_recipes",
                   "_bd_buendel_enden", "_bd_me", "_bd_te", "_bd_qty")}
pruefe("B2 zweiter Klick startet KEINEN zweiten Worker",
       klick(B_TID, B_NAME), False)
ja("B2 ... der Nutzer bekommt gesagt, warum",
   MELDUNGEN and "already loading" in MELDUNGEN[0].lower())
ja("B2 ... und der Name des laufenden Plans steht drin",
   MELDUNGEN and A_NAME in MELDUNGEN[0])
_nachher = {k: getattr(win, k, None) for k in _vorher_felder}
pruefe("B3 KEIN geteiltes Feld wurde angefasst", _nachher, _vorher_felder)
pruefe("B3 ... es laeuft weiterhin genau EIN Worker", len(GESAMMELT), 1)

# Der laufende Lauf kommt an - und darf sich nicht selbst aussperren.
_res = {"tree": {}, "names": {}, "sell": 0.0, "plan": {}}
MELDUNGEN.clear()
GESAMMELT[0]["done"](_res)        # leerer Baum -> Hinweis, kein Fenster
ja("B4 nach `done` ist das Schloss wieder auf", not win._bd_laedt_gerade())
ja("B4 ... und die Meldung war die ueber den leeren Baum, nicht die Sperre",
   MELDUNGEN and "already loading" not in MELDUNGEN[0].lower())
GESAMMELT.clear()
pruefe("B5 jetzt laesst sich der naechste Plan oeffnen",
       klick(B_TID, B_NAME), True)

# =====================================================================
print("")
print("TEIL C - die Notbremsen (ein Schloss darf nie dauerhaft zusperren)")

GESAMMELT.clear()
win._bd_lade_frei()
klick(A_TID, A_NAME)
GESAMMELT[0]["fail"]("Testfehler")
ja("C1 ein gescheiterter Lauf gibt das Schloss frei",
   not win._bd_laedt_gerade())

GESAMMELT.clear()
win._bd_lade_frei()
klick(A_TID, A_NAME)
ja("C2 Abbrechen gibt es ebenfalls frei",
   (win._cancel_all(), not win._bd_laedt_gerade())[1])

# Abgestuerzter Faden: weder done noch fail. Dann endet das Schloss von
# selbst - sonst liesse sich der Bauplan nie wieder oeffnen.
import time as _t                                          # noqa: E402
win._bd_lade_zu("Haenger")
win._bd_lade_ts = _t.time() - win.BD_LADE_FRIST - 1
ja("C3 nach Ablauf der Frist ist das Schloss von selbst auf",
   not win._bd_laedt_gerade())
GESAMMELT.clear()
pruefe("C3 ... und das Oeffnen geht wieder", klick(A_TID, A_NAME), True)

win._bd_lade_ts = "kaputt"
ja("C4 ein unbrauchbarer Zeitstempel sperrt nicht",
   not win._bd_laedt_gerade())

# Das offene FENSTER sperrt weiterhin (emm742) - beide Haelften zusammen.
GESAMMELT.clear()
win._bd_lade_frei()


class _FakeDlg:
    def isVisible(self):
        return True

    def showNormal(self):
        pass

    def raise_(self):
        pass

    def activateWindow(self):
        pass


win._bd_dialog = _FakeDlg()
MELDUNGEN.clear()
pruefe("C5 bei offenem Fenster sperrt weiterhin emm742",
       klick(B_TID, B_NAME), False)
ja("C5 ... mit der Fenster-Meldung, nicht der Lade-Meldung",
   MELDUNGEN and "already loading" not in MELDUNGEN[0].lower()
   and "one build plan" in MELDUNGEN[0].lower())
win._bd_dialog = None

print("")
print("ALLES GRUEN" if OK else "ES GIBT ROTE PUNKTE")
sys.exit(0 if OK else 1)
