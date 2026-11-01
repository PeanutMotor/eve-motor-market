#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIMULATIONEN zum Abend des 28.10.2026 (Nutzer: "ueberpruefe danach alles
was wir gerade hatte, fahre einige Szenarien mittel Simulationen durch und
pruefe ob fehler auftreten oder Fallen finden kannst").

WAS AN DIESEM ABEND PASSIERT IST, IN EINER KETTE:
  ESI lieferte fuer Peanut Motor 582 statt 1'859 Asset-Zeilen (14 Mio
  Stueck fehlten in der ANTWORT, nicht im Hangar). Daraufhin sah kein Plan
  mehr seine gebauten Huellen und Komponenten, plante sie neu und
  verlangte deren Vorprodukte - Mineralien, Morphite, Construction Blocks,
  R.A.M.- Starship Tech. Die Seite zeigte 18 Mio Pyerite als "missing" und
  bot den Einkauf an. Die Warnung, die genau das verhindern soll (emm477),
  schwieg: sie verstummte, sobald zweimal dieselbe zu kleine Zahl ankam -
  bei einem ESI-Cache von einer Stunde also schon beim zweiten Klick.

GEPRUEFT WIRD DESHALB:
  Teil A  der Riegel selbst (emm744) ueber eine Zeitachse, mit allen
          Faellen, die mir als Falle eingefallen sind: schwankende Abrufe,
          echte Hangar-Raeumung, Alt-Einstellungen ohne Zeitstempel,
          gescheiterte Abrufe, Grenzwerte, verdorbene Vergleichsbasis.
  Teil B  das ECHTE Fenster: Banner-Text und gesperrter Einkaufs-Knopf
          ueber `_lager_unvollstaendig_zeigen` - nicht nachgebaut, sondern
          die Methode gerufen (Regel 8a).
  Teil C  die Corp-Luecke (emm743): angekreuzter, aber mangels
          Director-Rolle unlesbarer Hangar zaehlt als Luecke, nicht als
          Lage.

Aufruf: QT_QPA_PLATFORM=offscreen python3 werkzeuge/sim_emm744.py
(Exit 0 = alles gruen). Arbeitet in einem Wegwerf-Ordner - die echten
Einstellungen und die Datenbank bleiben unberuehrt.
"""
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOME = tempfile.mkdtemp(prefix="sim744_")
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

STD = 3600.0
T0 = 1_000_000.0


def namen(warn):
    return sorted(n for n, _v, _j in warn)


# =====================================================================
print("TEIL A - der Riegel gegen den still gekuerzten Abruf (emm744)")

# --- A1 der Fall des Nutzers, Minute fuer Minute --------------------------
w, s = L.bestand_schrumpf({"Peanut": 1859}, {}, jetzt=T0)
pruefe("A1 erster, vollstaendiger Abruf: keine Warnung", namen(w), [])
pruefe("A1 ... und 1'859 ist die bestaetigte Zahl", s["Peanut"]["ok"], 1859)

w, s = L.bestand_schrumpf({"Peanut": 582}, s, jetzt=T0 + 600)
pruefe("A1 Einbruch auf 582: Warnung", w, [("Peanut", 1859, 582)])
pruefe("A1 ... die bestaetigte Zahl bleibt 1'859", s["Peanut"]["ok"], 1859)

# GENAU HIER WAR DER FEHLER: derselbe gekuerzte Stand, fuenf Minuten
# spaeter - ESI hat in der Zwischenzeit gar nicht neu gerechnet (Cache).
w, s = L.bestand_schrumpf({"Peanut": 582}, s, jetzt=T0 + 900)
pruefe("A1 zweiter Klick, gleiche Zahl: Warnung BLEIBT (alt: verstummt)",
       w, [("Peanut", 1859, 582)])
pruefe("A1 ... und 582 wird NICHT zur Wahrheit (alt: ok=582)",
       s["Peanut"]["ok"], 1859)

w, s = L.bestand_schrumpf({"Peanut": 582}, s, jetzt=T0 + 600 + STD)
pruefe("A1 nach einer vollen ESI-Cache-Stunde: immer noch Warnung",
       w, [("Peanut", 1859, 582)])

w, s = L.bestand_schrumpf({"Peanut": 1859}, s, jetzt=T0 + 600 + 1.5 * STD)
pruefe("A1 ESI liefert wieder voll: Warnung weg", namen(w), [])
pruefe("A1 ... Stand wieder 1'859", s["Peanut"]["ok"], 1859)
pruefe("A1 ... und die Uhr ist zurueckgestellt", s["Peanut"]["seit"], 0.0)

# --- A2 echte Raeumung: die Warnung darf nicht ewig stehen ----------------
w, s = L.bestand_schrumpf({"Hans": 900}, {}, jetzt=T0)
w, s = L.bestand_schrumpf({"Hans": 100}, s, jetzt=T0 + 60)
pruefe("A2 Hangar wirklich geleert: erst Warnung", w, [("Hans", 900, 100)])
w, s = L.bestand_schrumpf({"Hans": 100}, s, jetzt=T0 + 60 + 7199)
ja("A2 ... eine Sekunde vor Ablauf noch Warnung", w)
w, s = L.bestand_schrumpf({"Hans": 100}, s, jetzt=T0 + 60 + 7200)
pruefe("A2 ... nach zwei Stunden stabil: akzeptiert", namen(w), [])
pruefe("A2 ... 100 ist jetzt die Wahrheit", s["Hans"]["ok"], 100)
# ... und ab jetzt wird von 100 aus gemessen, nicht mehr von 900.
w, s = L.bestand_schrumpf({"Hans": 60}, s, jetzt=T0 + 20000)
pruefe("A2 ... ein Einbruch DANACH misst sich an 100", w, [("Hans", 100, 60)])

# --- A3 schwankende Abrufe: die Uhr darf nicht durchlaufen ----------------
# FALLE: liefert ESI mal 582, mal 600, mal 582, waere es falsch, die zwei
# Stunden einfach weiterlaufen zu lassen - gewackelt hat es ja gerade.
w, s = L.bestand_schrumpf({"Eva": 1000}, {}, jetzt=T0)
w, s = L.bestand_schrumpf({"Eva": 500}, s, jetzt=T0 + 10)
w, s = L.bestand_schrumpf({"Eva": 600}, s, jetzt=T0 + 20)
pruefe("A3 andere kleine Zahl: Uhr faengt neu an", s["Eva"]["seit"], T0 + 20)
w, s = L.bestand_schrumpf({"Eva": 600}, s, jetzt=T0 + 20 + 7190)
ja("A3 ... kurz vor Ablauf warnt es noch", w)
w, s = L.bestand_schrumpf({"Eva": 500}, s, jetzt=T0 + 20 + 7190 + 5)
pruefe("A3 ... und ein Rueckfall auf 500 stellt wieder zurueck",
       s["Eva"]["seit"], T0 + 20 + 7190 + 5)
ja("A3 ... Warnung steht", w)

# --- A4 Alt-Einstellungen ohne Zeitstempel (Migration) --------------------
# FALLE: wer von der alten Fassung kommt, hat {"ok":…, "letzte":…} ohne
# "seit". Daraus darf kein stilles Durchwinken werden.
_alt = {"Udo": {"ok": 2000, "letzte": 900}}
w, s = L.bestand_schrumpf({"Udo": 900}, _alt, jetzt=T0)
pruefe("A4 alter Stand ohne 'seit': warnt (alt: still durchgewunken)",
       w, [("Udo", 2000, 900)])
pruefe("A4 ... und setzt die Uhr auf jetzt", s["Udo"]["seit"], T0)

# --- A5 gescheiterter Abruf verliert den Vergleichswert nicht -------------
w, s = L.bestand_schrumpf({"Ida": 800}, {}, jetzt=T0)
w2, s2 = L.bestand_schrumpf({}, s, jetzt=T0 + 100)     # Abruf geworfen
pruefe("A5 Charakter fehlt (Abruf gescheitert): Stand bleibt erhalten",
       s2.get("Ida", {}).get("ok"), 800)
w3, s3 = L.bestand_schrumpf({"Ida": 300}, s2, jetzt=T0 + 200)
pruefe("A5 ... der naechste Einbruch faellt weiter auf",
       w3, [("Ida", 800, 300)])

# --- A6 kleine Charaktere schwanken, ohne zu laermen ----------------------
w, s = L.bestand_schrumpf({"Mini": 49}, {}, jetzt=T0)
w, s = L.bestand_schrumpf({"Mini": 1}, s, jetzt=T0 + 10)
pruefe("A6 unter 50 Zeilen wird nicht geurteilt", namen(w), [])

# --- A7 Grenzwerte ---------------------------------------------------------
w, _ = L.bestand_schrumpf({"G": 70}, {"G": {"ok": 100, "letzte": 100,
                                            "seit": 0.0}}, jetzt=T0)
pruefe("A7 genau 70 % ist noch kein Einbruch", namen(w), [])
w, _ = L.bestand_schrumpf({"G": 69}, {"G": {"ok": 100, "letzte": 100,
                                            "seit": 0.0}}, jetzt=T0)
pruefe("A7 69 % ist einer", w, [("G", 100, 69)])
w, _ = L.bestand_schrumpf({"G": 0}, {"G": {"ok": 100, "letzte": 100,
                                           "seit": 0.0}}, jetzt=T0)
pruefe("A7 gar nichts geliefert ist der schlimmste Fall", w, [("G", 100, 0)])

# --- A8 mehrere Charaktere gleichzeitig -----------------------------------
w, s = L.bestand_schrumpf({"Peanut": 1859, "Lezaar": 524, "Fredy": 27},
                          {}, jetzt=T0)
w, s = L.bestand_schrumpf({"Peanut": 582, "Lezaar": 449, "Fredy": 34},
                          s, jetzt=T0 + 600)
# Lezaar 449/524 = 86 % -> kein Einbruch; Fredy ist zu klein zum Urteilen.
pruefe("A8 nur der echte Einbruch meldet sich", namen(w), ["Peanut"])

# --- A9 Mist in den Einstellungen bringt nichts zum Absturz ---------------
for _mist in (None, [], "kaputt", {"X": "kaputt"}, {"X": {"ok": "a"}}):
    try:
        L.bestand_schrumpf({"X": 100}, _mist, jetzt=T0)
    except Exception as e:                               # pragma: no cover
        pruefe(f"A9 unbrauchbarer Stand {_mist!r}", f"{type(e).__name__}", "")
ja("A9 unbrauchbare Einstellungen werfen nicht", True)
w, _ = L.bestand_schrumpf({"X": None, "Y": "zwei", "Z": 100}, {}, jetzt=T0)
ja("A9 unbrauchbare Zahlen werden uebersprungen", True)

# --- A10 DIE FALLE, IN DER DER NUTZER GERADE STECKT -----------------------
# Die alte Fassung hat 582 schon als `ok` festgeschrieben. Von dieser
# verdorbenen Basis aus kann auch die neue Fassung nichts mehr merken -
# sie heilt aber von selbst, sobald ESI wieder vollstaendig liefert.
_verdorben = {"Peanut": {"ok": 582, "letzte": 582}}
w, s = L.bestand_schrumpf({"Peanut": 582}, _verdorben, jetzt=T0)
pruefe("A10 verdorbene Basis: keine Warnung mehr moeglich", namen(w), [])
w, s = L.bestand_schrumpf({"Peanut": 1859}, s, jetzt=T0 + 100)
pruefe("A10 ... ein voller Abruf heilt sie", s["Peanut"]["ok"], 1859)
w, s = L.bestand_schrumpf({"Peanut": 582}, s, jetzt=T0 + 200)
pruefe("A10 ... danach greift der Riegel wieder",
       w, [("Peanut", 1859, 582)])

# =====================================================================
print("")
print("TEIL B - das echte Fenster: Banner (Warnung seit emm767),"
      " Sperre nur bei echtem Fehlschlag")

from PySide6.QtWidgets import QApplication                 # noqa: E402

app = QApplication.instance() or QApplication([])

from eve_trader.ui.main_window import MainWindow           # noqa: E402

win = MainWindow()
win._erste_einrichtung_pruefen = lambda *a, **k: None
win._tutorial_erstfrage = lambda *a, **k: None
win._erststart_rezepte_anbieten = lambda *a, **k: None

_leer = {"schrumpf": [], "failed": [], "job_fehler": False,
         "budget_420": False}
pruefe("B1 vollstaendige Daten: kein Banner",
       win._lager_unvollstaendig_grund(_leer), "")

_mit = dict(_leer, schrumpf=[("Peanut Motor", 1859, 582)])
_txt = win._lager_unvollstaendig_grund(_mit)
# emm767 (Nutzer 30.10.2026: "punkt 4 möchte ich nur eine warnung, keine
# kauf sperre"): der Schrumpf allein traegt seither den WEICHEN Kopf -
# der harte ("do not buy from this list") bleibt den wirklich
# gescheiterten Abrufen vorbehalten (Gegenprobe in B3).
ja("B2 Einbruch: Banner warnt (weicher Kopf, emm767)",
   "Stock may be incomplete" in _txt
   and "do not buy from this list" not in _txt)
ja("B2 ... und nennt Charakter und beide Zahlen",
   "Peanut Motor" in _txt and "582" in _txt and "1859" in _txt)

win._lager_unvollstaendig_zeigen(_mit)
_lbl = getattr(win, "_lager_warn_lbl", None)
_btn = getattr(win, "_lager_kauf_btn", None)
# isVisible() waere hier blind: das Hauptfenster wird in der Simulation nie
# gezeigt, also ist JEDES Kind "unsichtbar". isVisibleTo(Elternteil) fragt
# das, worum es geht - hat jemand setVisible(False) gerufen? (wie b98)
ja("B3 die Warnzeile steht und ist sichtbar",
   _lbl is not None and _lbl.isVisibleTo(_lbl.parentWidget())
   and bool(_lbl.text()))
# emm767: der Schrumpf allein sperrt den Knopf NICHT mehr (der Nutzer
# weiss selbst, ob er gerade Material geschoben hat).
ja("B3 der Einkaufs-Knopf bleibt FREI (emm767: nur Warnung)",
   _btn is not None and _btn.isEnabled())
# GEGENPROBE: ein WIRKLICH gescheiterter Abruf sperrt weiterhin, mit
# hartem Kopf.
_hart = dict(_leer, failed=["Lezaar"])
ja("B3 Gegenprobe: gescheiterter Abruf -> harter Kopf",
   "do not buy from this list"
   in win._lager_unvollstaendig_grund(_hart))
win._lager_unvollstaendig_zeigen(_hart)
ja("B3 Gegenprobe: ... und der Knopf ist gesperrt",
   not _btn.isEnabled())
win._lager_unvollstaendig_zeigen(_leer)
ja("B4 vollstaendige Daten: Zeile weg, Knopf wieder frei",
   _lbl is not None and not _lbl.isVisibleTo(_lbl.parentWidget())
   and _btn is not None and _btn.isEnabled())

# B5: der Weg vom Worker-Ergebnis bis zum Banner, mit der ECHTEN
# Riegel-Funktion dazwischen - zweimal derselbe gekuerzte Abruf. Der
# KERN von emm744 (die Warnung verstummt NICHT beim zweiten Abruf)
# bleibt; seit emm767 ist die Folge eine stehende WARNUNG, keine Sperre.
_stand = {}
_w1, _stand = L.bestand_schrumpf({"Peanut Motor": 1859}, _stand, jetzt=T0)
_w2, _stand = L.bestand_schrumpf({"Peanut Motor": 582}, _stand, jetzt=T0 + 60)
_w3, _stand = L.bestand_schrumpf({"Peanut Motor": 582}, _stand, jetzt=T0 + 300)
ja("B5 der zweite gekuerzte Abruf warnt WEITER (nichts verstummt)",
   bool(_w3))
win._lager_unvollstaendig_zeigen(dict(_leer, schrumpf=_w3))
ja("B5 ... die Warnzeile steht auch beim zweiten Abruf",
   _lbl.isVisibleTo(_lbl.parentWidget()))
ja("B5 ... und der Knopf bleibt frei (emm767)", _btn.isEnabled())

# =====================================================================
print("")
print("TEIL C - Corp-Hangar angekreuzt, aber ohne Director-Rolle (emm743)")

from eve_trader.ui.mw_helpers import corp_bp_luecken       # noqa: E402

# emm808: corp_bp_luecken liefert seitdem DREI Listen - die fehlende
# Rolle bleibt eine Luecke (Sicherheit unveraendert), wird aber als
# BEKANNT markiert und dezent angezeigt statt rot.
_lk, _lg, _bk = corp_bp_luecken({"ohne_rolle": ["WipeOut Inc."]})
pruefe("C1 angekreuzter Hangar ohne Rolle ist eine LUECKE", len(_lk), 1)
ja("C1 ... und nennt die Corp", "WipeOut Inc." in _lk[0])
ja("C1 ... und ist als bekannt markiert (dezente Anzeige, emm808)",
   _bk == _lk and len(_lg) == 1)

_lk, _lg, _bk = corp_bp_luecken({"keine_division": True})
pruefe("C2 kein Hangar angekreuzt bleibt eine LAGE", _lk, [])
pruefe("C2 ... und steht dezent da", len(_lg), 1)

_lk, _lg, _bk = corp_bp_luecken({"failed": ["Corp blueprints: X"],
                                 "relink": ["Peanut"],
                                 "ohne_rolle": ["A", "B"],
                                 "keine_division": True})
pruefe("C3 alle Gruende zusammen: vier Luecken, drei Lagen, zwei bekannt",
       (len(_lk), len(_lg), len(_bk)), (4, 3, 2))

for _mist in (None, {}, [], "kaputt"):
    _lk, _lg, _bk = corp_bp_luecken(_mist)
    pruefe(f"C4 unbrauchbare Eingabe {_mist!r} liefert leer",
           (_lk, _lg, _bk), ([], [], []))

# C5: der Blueprints-Reiter macht aus einer Luecke amber statt rot und
# nimmt die Kaufliste weg - geprueft an der echten Stelle im Quelltext.
_mw = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
ja("C5 die Luecken-Liste sperrt die Kaufliste",
   "self._bd_bp_kaufliste = (None if (owned is None or _bp_fehler) else [" in _mw)
ja("C5 ... und faerbt die Zeile amber statt rot",
   "elif _bp_fehler:" in _mw and "status_col = theme.AMBER" in _mw)
ja("C5 die Corp-Gruende kommen aus EINER Funktion (Regel 9)",
   "corp_bp_luecken as _cbl743" in _mw
   and 'corp_info.append(t("Corp hangar {name} (no Director role)")' not in _mw)

# C6: der Messweg bleibt UNABHAENGIG. Haette das Diagnose-Werkzeug
# dieselbe Funktion benutzt, haette es am 28.10.2026 nichts gemeldet -
# es war die einzige Stelle, die den Einbruch sah.
_wz = open("werkzeuge/zeige_lagerorte.py", encoding="utf-8").read()
ja("C6 das Werkzeug misst weiter mit eigener Rechnung",
   "bestand_schrumpf" not in _wz and "UNVOLLSTAENDIGER ABRUF" in _wz)

print("")
print("ALLES GRUEN" if OK else "ES GIBT ROTE PUNKTE")
sys.exit(0 if OK else 1)
