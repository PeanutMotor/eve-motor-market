#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIMULATION: MATERIAL, DAS ZWISCHEN ZWEI EIGENEN CHARAKTEREN UNTERWEGS
IST (emm745) - der Fall des Nutzers vom 28.10.2026, nachgestellt.

SEIN ABLAUF, mit seinen Zahlen:
  ~16:50  Uebergabe von Peanut Motor an Leziris Lezflow ("ich habe alles
          von Peanut Motor zu Leziris Lezflow getauscht vor gut 1 stunde",
          17:50; dazu 17:55: "ich schiebe die Items oft ueber den
          Stationshandel rueber, das ist ein Handelsfenster zwischen zwei
          charakteren").
  17:12   Lagerorte-Bericht: Peanut Motor 1'859 -> 582 Zeilen,
          Leziris Lezflow 160 -> 160 (kein einziger Stack bewegt).
  17:11   Stock Locations zeigt 18'240'750 Pyerite als fehlend, der
          Einkaufs-Knopf ist frei. 16:53 dasselbe Muster bei acht
          Blaupausen ("completely missing", obwohl im Hangar sichtbar).

WARUM DAS PASSIERT: jeder Charakter hat seinen EIGENEN /assets/-Cache mit
eigenem Ablauf. Nach einer Uebergabe ist der Absender schon frisch
gelesen (Ware weg), der Empfaenger noch alt (Ware noch nicht da) - das
Material liegt dann in KEINER Antwort, ohne dass etwas kaputt ist. Bei
einem offenen Vertrag gilt dasselbe aus anderem Grund: dort gehoert die
Ware solange NIEMANDEM.

GEPRUEFT WIRD:
  Teil A  die Vertrags-Rechnung (eve_trader/vertraege.py) - Status- und
          Typ-Filter, Doppelzaehlung, nur was der Aussteller hergibt,
          fehlende Positions-Abrufe, unbrauchbare Eingaben.
  Teil B  die Meldung im ECHTEN Fenster: sie nennt die Uebergabe als
          Grund und das Alter der anderen Charaktere, statt "ESI lieferte
          weniger - Refresh druecken" (was beim haeufigsten Grund gar
          nicht hilft). Gerufen wird die echte Methode, nicht nachgebaut.
  Teil C  der Zeitverlauf seines Abends: Uebergabe, Cache-Fenster,
          Erholung - mit dem Riegel aus emm744 davor.

Aufruf: QT_QPA_PLATFORM=offscreen python3 werkzeuge/sim_emm745.py
(Exit 0 = alles gruen). Wegwerf-Ordner, die echten Daten bleiben unberuehrt.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = tempfile.mkdtemp(prefix="sim745_")
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


from eve_trader import lagerorte as L                      # noqa: E402
from eve_trader import vertraege as V                      # noqa: E402

# Seine echten Zahlen
PEANUT_VOR, PEANUT_NACH = 1859, 582
LEZFLOW = 160
STD = 3600.0
T0 = 1_000_000.0

# =====================================================================
print("TEIL A - die Vertrags-Rechnung")

VERTRAEGE = [
    {"contract_id": 7001, "type": "item_exchange", "status": "outstanding",
     "issuer_id": 2115318203, "assignee_id": 2113366524},   # Peanut -> Lezflow
    {"contract_id": 7002, "type": "courier", "status": "in_progress",
     "issuer_id": 2115318203, "assignee_id": 999},
    {"contract_id": 7003, "type": "item_exchange", "status": "finished",
     "issuer_id": 2115318203, "assignee_id": 2113366524},
    {"contract_id": 7004, "type": "loan", "status": "outstanding",
     "issuer_id": 2115318203, "assignee_id": 2113366524},
]
pruefe("A1 nur offene Vertraege, die ueberhaupt Ware halten",
       sorted(V.offene_vertraege(VERTRAEGE)), [7001, 7002])
pruefe("A2 ein abgeschlossener Vertrag haelt nichts mehr fest",
       7003 in V.offene_vertraege(VERTRAEGE), False)
# Beide Seiten verknuepft -> derselbe Vertrag kommt doppelt an.
pruefe("A3 Absender UND Empfaenger verknuepft: Vertrag zaehlt einmal",
       sorted(V.offene_vertraege([VERTRAEGE, list(VERTRAEGE)])),
       [7001, 7002])

ITEMS = {
    7001: [{"type_id": 34, "quantity": 18_240_750, "is_included": True},
           {"type_id": 36, "quantity": 3_336_090, "is_included": True},
           {"type_id": 4315, "quantity": -1, "is_included": True},
           {"type_id": 11890, "quantity": -1, "is_included": True},
           # Gegenleistung: liegt noch beim Empfaenger
           {"type_id": 29668, "quantity": 5, "is_included": False}],
    7002: [{"type_id": 34, "quantity": 250, "is_included": True}],
}
pruefe("A4 nur was der Aussteller hergibt; Blaupausen zaehlen als 1",
       V.posten_aus_items(ITEMS[7001]),
       {34: 18_240_750, 36: 3_336_090, 4315: 1, 11890: 1})
pruefe("A5 Summe ueber alle offenen Vertraege",
       V.unterwegs(VERTRAEGE, ITEMS)[34], 18_241_000)
pruefe("A6 Positionen nicht abrufbar: keine erfundene Menge, aber gemeldet",
       (V.unterwegs(VERTRAEGE, {7001: ITEMS[7001]})[34],
        V.fehlende_items(VERTRAEGE, {7001: ITEMS[7001]})),
       (18_240_750, [7002]))
pruefe("A7 Rolle am Vertrag (fuer den Anzeigetext)",
       [V.beteiligte(VERTRAEGE[0], [2115318203]),
        V.beteiligte(VERTRAEGE[0], [2113366524]),
        V.beteiligte(VERTRAEGE[0], [1])],
       ["aussteller", "empfaenger", "fremd"])
for _mist in (None, [], [None], ["kaputt"], [{"contract_id": "x"}],
              [{"contract_id": 1}]):
    V.offene_vertraege(_mist)
    V.unterwegs(_mist, None)
    V.fehlende_items(_mist, None)
ja("A8 unbrauchbare Eingaben werfen nicht", True)
pruefe("A9 Positionen ohne Inhalt ergeben nichts", V.posten_aus_items(None), {})

# =====================================================================
print("")
print("TEIL B - die Meldung im echten Fenster")

from PySide6.QtWidgets import QApplication                 # noqa: E402

app = QApplication.instance() or QApplication([])
from eve_trader.ui.main_window import MainWindow           # noqa: E402

win = MainWindow()
win._erste_einrichtung_pruefen = lambda *a, **k: None
win._tutorial_erstfrage = lambda *a, **k: None
win._erststart_rezepte_anbieten = lambda *a, **k: None

_res = {"schrumpf": [("Peanut Motor", PEANUT_VOR, PEANUT_NACH)],
        "failed": [], "job_fehler": False, "budget_420": False,
        "asset_alter_je_char": {"Peanut Motor": 120.0,
                                "Leziris Lezflow": 55 * 60.0,
                                "Lezaar": 12 * 60.0}}
_txt = win._lager_unvollstaendig_grund(_res)
# emm767 (Nutzer 30.10.2026: "punkt 4 möchte ich nur eine warnung, keine
# kauf sperre"): der Schrumpf ist seither VERDACHT, kein Scheitern - der
# Kopf ist der weiche ("check before you buy"), nicht mehr der harte.
ja("B1 die Meldung warnt weiter vor dem Kaufen (weicher Kopf, emm767)",
   "Stock may be incomplete" in _txt
   and "do not buy from this list" not in _txt)
ja("B2 sie nennt beide Zahlen und den Charakter",
   "Peanut Motor" in _txt and "582" in _txt and "1859" in _txt)
ja("B3 sie nennt die UEBERGABE als Grund (nicht 'ESI lieferte weniger')",
   "hand items to another character" in _txt
   and "ESI only sent" not in _txt)
ja("B4 sie sagt, wie alt der Bestand der anderen ist (55 min)",
   "55" in _txt and "min old" in _txt)
# Ohne Altersangaben bleibt der Satz trotzdem vollstaendig.
_txt2 = win._lager_unvollstaendig_grund(dict(_res, asset_alter_je_char={}))
ja("B5 ohne bekanntes Alter faellt nur der Zusatz weg",
   "hand items to another character" in _txt2 and "min old" not in _txt2)
# Das Alter des EINGEBROCHENEN Charakters ist uninteressant - seine Daten
# sind ja frisch; gemeint sind die der anderen.
_txt3 = win._lager_unvollstaendig_grund(
    dict(_res, asset_alter_je_char={"Peanut Motor": 9999.0}))
ja("B6 nur das Alter der ANDEREN zaehlt", "min old" not in _txt3)
win._lager_unvollstaendig_zeigen(_res)
_btn = getattr(win, "_lager_kauf_btn", None)
_lbl = getattr(win, "_lager_warn_lbl", None)
# emm767: der Schrumpf allein sperrt nicht mehr - die Warnzeile steht,
# der Knopf bleibt frei (der Nutzer weiss selbst, ob er geschoben hat).
ja("B7 die Warnzeile steht (Schrumpf wird weiter gemeldet)",
   _lbl is not None and _lbl.isVisibleTo(_lbl.parentWidget())
   and "hand items to another character" in _lbl.text())
ja("B7 der Einkaufs-Knopf bleibt FREI (emm767: nur Warnung)",
   _btn is not None and _btn.isEnabled())
# GEGENPROBE: ein WIRKLICH gescheiterter Abruf sperrt weiterhin.
win._lager_unvollstaendig_zeigen(dict(_res, failed=["Lezaar"]))
ja("B7 Gegenprobe: gescheiterter Abruf sperrt weiter",
   not _btn.isEnabled())
win._lager_unvollstaendig_zeigen(dict(_res, failed=[]))

# =====================================================================
print("")
print("TEIL C - sein Abend als Zeitverlauf")

# 16:00 alles bei Peanut, normaler Stand
_st = {}
_w, _st = L.bestand_schrumpf({"Peanut Motor": PEANUT_VOR,
                              "Leziris Lezflow": LEZFLOW}, _st, jetzt=T0)
pruefe("C1 16:00 vor der Uebergabe: nichts zu melden", _w, [])

# ~16:50 Uebergabe im Handelsfenster. 17:12 erster Bericht: Peanut ist
# frisch gelesen (Ware weg), Lezflow noch nicht (160 unveraendert).
_w, _st = L.bestand_schrumpf({"Peanut Motor": PEANUT_NACH,
                              "Leziris Lezflow": LEZFLOW},
                             _st, jetzt=T0 + 72 * 60)
pruefe("C2 17:12 Absender leer, Empfaenger unveraendert: Warnung",
       _w, [("Peanut Motor", PEANUT_VOR, PEANUT_NACH)])
ja("C2 ... und der Empfaenger loest KEINE eigene Warnung aus",
   all(n != "Leziris Lezflow" for n, _v, _j in _w))

# 17:49 zweiter Bericht, nur Minuten spaeter: dieselbe Lage. GENAU HIER
# verstummte die alte Fassung und schrieb 582 als Wahrheit fest.
_w, _st = L.bestand_schrumpf({"Peanut Motor": 589,
                              "Leziris Lezflow": LEZFLOW},
                             _st, jetzt=T0 + 109 * 60)
pruefe("C3 17:49 fast gleiche Zahl: Warnung steht weiter",
       [n for n, _v, _j in _w], ["Peanut Motor"])
pruefe("C3 ... und 582/589 wird nicht zur Wahrheit",
       _st["Peanut Motor"]["ok"], PEANUT_VOR)

# ~18:10 Lezflows Cache laeuft ab, die Ware taucht bei ihm auf. Peanut
# bleibt klein - das ist jetzt RICHTIG so.
_w, _st = L.bestand_schrumpf({"Peanut Motor": 589,
                              "Leziris Lezflow": LEZFLOW + 1277},
                             _st, jetzt=T0 + 130 * 60)
ja("C4 18:10 Ware beim Empfaenger angekommen", True)
pruefe("C4 ... Peanut warnt weiter, bis sich der Stand bewaehrt hat",
       [n for n, _v, _j in _w], ["Peanut Motor"])

# Zwei Stunden nach dem Einbruch ist der kleinere Stand die Wahrheit -
# die Uebergabe war ja echt.
_w, _st = L.bestand_schrumpf(
    {"Peanut Motor": 589, "Leziris Lezflow": LEZFLOW + 1277},
    _st, jetzt=T0 + 109 * 60 + L.SCHRUMPF_BESTAETIGUNG_SEK)
pruefe("C5 danach ist Ruhe - ohne dass jemand etwas abschalten musste",
       _w, [])
pruefe("C5 ... und der neue Stand gilt", _st["Peanut Motor"]["ok"], 589)

# Gegenprobe: haette er NICHT uebergeben, sondern ESI gesponnen, waere
# die Zahl zurueckgesprungen - auch dann ist am Ende Ruhe.
_st2 = {}
_w, _st2 = L.bestand_schrumpf({"P": 1859}, _st2, jetzt=T0)
_w, _st2 = L.bestand_schrumpf({"P": 582}, _st2, jetzt=T0 + 600)
ja("C6 Gegenprobe ESI-Aussetzer: warnt", bool(_w))
_w, _st2 = L.bestand_schrumpf({"P": 1859}, _st2, jetzt=T0 + 1800)
pruefe("C6 ... und beim naechsten vollen Abruf ist die Warnung weg", _w, [])

print("")
print("ALLES GRUEN" if OK else "ES GIBT ROTE PUNKTE")
sys.exit(0 if OK else 1)
