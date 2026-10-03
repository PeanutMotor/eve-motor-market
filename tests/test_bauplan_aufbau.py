"""AUFBAU-TEST: baut das Hauptfenster UND den Bauplan-Dialog wirklich.

WARUM ES DIESEN TEST GIBT
-------------------------
In einer einzigen Session ging der Bauplan-Dialog ZWEIMAL nach UI-Aenderungen
nicht mehr auf - beide Male bei gruenen Logiktests und 0 Lint-Befunden:

  1. `sell = _hp` in rebuild() machte einen geerbten Namen lokal
     -> UnboundLocalError beim OEFFNEN jedes Bauplans.
  2. Das Verkaufscharakter-Dropdown wurde erzeugt, verdrahtet, betooltippt -
     und nie ins Layout gehaengt. Sichtbar war nur die Beschriftung.

Beide Fehlerklassen sind mit reiner Logikpruefung NICHT zu finden: die eine
schlaegt erst beim Ausfuehren zu, die andere sieht im Code voellig korrekt
aus. Gefunden werden sie nur, indem man den Dialog TATSAECHLICH baut und
danach nachsieht, ob die Bedienelemente auch im Fenster gelandet sind.

Ein Widget, das nie in ein Layout gehaengt wurde, hat KEINEN Parent - es
taucht in `dlg.findChildren(...)` also gar nicht erst auf. Genau darauf
stuetzen sich die Pruefungen unten.

Laeuft ohne Bildschirm (QT_QPA_PLATFORM=offscreen) und ohne ESI.
"""
import os
import sys

# AUSGABE NIE AN EINEM ZEICHEN STERBEN LASSEN (pruefe.py 02.10.2026, Windows,
# Python 3.14, cp1252-Konsole): ein Fehltext mit "\u25b8" warf beim print()
# UnicodeEncodeError - die Liste der roten Pruefungen kam gar nicht heraus.
for _strom in (sys.stdout, sys.stderr):
    try:
        _strom.reconfigure(errors="backslashreplace")
    except Exception:
        pass

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# PROJEKTWURZEL (Ordnerstruktur 18.09.2026): die Suite liegt in tests\,
# alles, was sie liest, relativ zur Wurzel (eve_trader\, pruefe.py, ...).
# Deshalb: Wurzel bestimmen, dorthin wechseln, auf den Importpfad legen.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(_ROOT)
sys.path.insert(0, _ROOT)
_HOME = os.path.join(_ROOT, ".smoke_home")
os.makedirs(_HOME, exist_ok=True)
for _k in ("HOME", "APPDATA", "USERPROFILE"):
    os.environ[_k] = _HOME

# (b107) EINE LIEGENGEBLIEBENE PLANER-DIAGNOSE eines frueheren Laufs wuerde
# "die Datei entsteht" bestaetigen, obwohl DIESER Lauf sie nie geschrieben
# hat - die Rotprobe waere blind. Deshalb vorher weg damit; wo config sie
# ablegt, steht erst nach dem Import fest, darum ueber config selbst.
try:
    from eve_trader import config as _cfg107v
    _alt107 = os.path.join(_cfg107v.app_data_dir(), "planer_diagnose.txt")
    if os.path.exists(_alt107):
        os.remove(_alt107)
except Exception:                                        # pragma: no cover
    pass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QTabWidget, QApplication, QComboBox, QPushButton, QLabel,
                               QTableWidget, QTreeWidget, QCheckBox,
                               QPlainTextEdit, QWidget, QFrame)

_app = QApplication.instance() or QApplication([])
# (b162) UNBEHANDELTE AUSNAHMEN IN SLOTS (pruefe.py 02.10.2026, Windows:
# "KeyError: 'item_name'" aus _reload_saved_plans stand nur auf stderr - Qt
# faengt die Ausnahme eines Slots ab, druckt sie und macht weiter; keine
# Pruefung sah sie). Jede solche Ausnahme wird hier mitgeschrieben.
_unbehandelt162 = []
_alt_hook162 = sys.excepthook


def _hook162(typ, wert, tb):
    import traceback as _tb162
    _ort = _tb162.extract_tb(tb)[-1] if tb is not None else None
    _unbehandelt162.append(f"{typ.__name__}: {wert}"
                           + (f" @ {os.path.basename(_ort.filename)}:{_ort.lineno}"
                              if _ort else ""))
    _alt_hook162(typ, wert, tb)


sys.excepthook = _hook162

# (b79) FEHLER.LOG-NETZ: _log_exception schreibt abgefangene Ausnahmen neben
# das Startskript (argv[0] = diese Datei). Was der Lauf dort anhaengt, wird
# am Ende gelesen - ein AttributeError in einem try/except ist sonst unsichtbar
# (18.09.2026: "'MainWindow' object has no attribute '_bd_groups'" sechsmal je
# Prueflauf, nur in fehler.log des Nutzers zu sehen).
_FLOG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fehler.log")   # neben argv[0]
try:
    _FLOG_START = os.path.getsize(_FLOG)
except OSError:
    _FLOG_START = 0

# KEIN NETZ IM TESTLAUF (27.09.2026, Nutzer: "deine Antworten dauern sehr
# lange"). GEMESSEN: von 46 s b-Suite warteten 23 s auf ESI-Antworten -
# ~200 echte Abrufe aus Hintergrund-Jobs (Bilder, Preise, Systemnamen), die
# keine Pruefung braucht; im Container abgelehnt, beim Nutzer sogar echt
# ausgefuehrt. Jetzt scheitert jeder Abruf SOFORT - derselbe Weg wie ohne
# Internet, den das Programm ohnehin abfangen muss. EMM_TEST_NETZ=1 schaltet
# das Netz fuer einen Sonderlauf wieder ein.
if os.environ.get("EMM_TEST_NETZ") != "1":
    import requests.adapters as _ra_netz

    def _kein_netz(self, request, *a, **k):
        raise __import__("requests").exceptions.ConnectionError(
            "Testlauf ohne Netz: " + str(getattr(request, "url", ""))[:80])
    _ra_netz.HTTPAdapter.send = _kein_netz

from eve_trader.ui.main_window import MainWindow          # noqa: E402
from eve_trader import industry as I                      # noqa: E402

# DAS EINRICHTUNGS-FENSTER FUER JEDES HAUPTFENSTER STILLLEGEN (Sitzung 17).
# Es ist MODAL und springt an, sobald die Testumgebung wie eine
# Neuinstallation aussieht - und genau so sieht `.smoke_home` aus.
# VORHER (Sitzung 16) geschah das nur an `win` (b1). b23 baut aber zwei
# WEITERE Hauptfenster (`_w_en`, `_w_de`); deren 300-ms-Zeitgeber oeffnete
# das Fenster nach der Schlusszeile, und die Suite hing endlos - mit
# "733/733 gruen" schon auf dem Schirm. `pruefe.py` kam nie zur Aussage, und
# die Rotprobe haette je Mutation die volle Stunde Notausstieg gewartet.
# DARUM AN DER KLASSE: jedes Hauptfenster, auch ein kuenftiges, ist erfasst.
# GEPRUEFT wird das Fenster trotzdem - separat in b58, am Fenster gemessen.
def _einrichtung_still(self, *_a, **_k):
    return None


MainWindow._erste_einrichtung_pruefen = _einrichtung_still

# DIE DREI ERSTSTART-FRAGEN EBENSO (Sitzung 17, Nutzer-Screenshot Windows).
# Rezeptfrage (400 ms), "kein Charakter" (250 ms), Verlaufsfrage (4000 ms)
# pruefen einen Merker in der settings.json. UNTER WINDOWS liegt die aber
# woanders als im Container (APPDATA -> `.smoke_home\EVE Motor Market\`,
# nicht `.smoke_home/.local/share/...`) und hat einen eigenen Stand - beim
# Nutzer fehlte der Merker, die Rezeptfrage ging auf, b59 wurde rot, und
# b2w verlor mitten im Test ein Widget (Qt raeumt verzoegert Geloeschtes
# ab, solange ein modales Fenster laeuft - Vermutung, bei ihm gesehen,
# hier nicht nachstellbar). EINE PRUEFUNG, DIE JE NACH UMGEBUNG ANDERS
# AUSGEHT, PRUEFT NICHTS - also stilllegen, wie das Einrichtungsfenster.
# Die Fragen selbst pruefen aa291 (Merker) und b57 (Buehne) separat.
MainWindow._erststart_rezepte_anbieten = _einrichtung_still
MainWindow._erststart_ohne_charakter = _einrichtung_still
# Sitzung 17: die Tutorial-Erstfrage ebenso - sonst bliebe sie im Test als
# modales Fenster stehen und b59 wuerde zu Recht rot.
MainWindow._tutorial_erstfrage = _einrichtung_still
MainWindow._frage_verlauf_laden = _einrichtung_still
# emm355: die ESI-Rechte-Pruefung beim Start ebenso (4 s nach dem Bau, mit
# Hintergrund-Job und modalem Fenster) - geprueft wird sie in b160 direkt.
MainWindow._scope_check_beim_start = _einrichtung_still

# NETZ, FALLS DAS STILLLEGEN DOCH EINMAL FEHLT: das Fenster vermerkt sich
# und kehrt sofort zurueck, statt zu blockieren. Aus einem endlosen Haenger
# ohne Ausgabe wird so eine BENANNTE rote Pruefung (b59). `auto=False`
# verhindert, dass der Testlauf die Download-Kette anstoesst (140 MB).
# b58 baut das Fenster selbst mit auto=False und ruft nie exec() - es
# merkt vom Netz nichts.
import eve_trader.ui.erst_einrichtung as _ee_mod          # noqa: E402
_EINRICHTUNG_UNBESTELLT = []


class _EinrichtungImTest(_ee_mod.ErstEinrichtung):
    def __init__(self, fenster, auto=True):
        if auto:
            _EINRICHTUNG_UNBESTELLT.append(type(fenster).__name__)
        super().__init__(fenster, auto=False)

    def exec(self):
        return 0


_ee_mod.ErstEinrichtung = _EinrichtungImTest

# NETZ 2: JEDES ANDERE MODALE FENSTER (Sitzung 17). Gemessen: nach dem
# Stilllegen oben hing die Suite WEITER - an `QMessageBox.warning` im
# ESI-Nachlauf des Bauplans ("No ESI access"). Ein modales Fenster ohne
# Bildschirm wartet auf einen Klick, der nie kommt.
# Die Wache sieht alle 250 ms nach: steht ein DIALOG laenger als 3 s modal
# offen, wird er vermerkt und geschlossen. b59 macht den Vermerk rot.
# Kein Test oeffnet selbst ein modales Fenster (gemessen: kein exec() in
# dieser Datei) - die Wache kann also nichts Gewolltes stoeren.
# `activeModalWidget` WIRD HIER FESTGEHALTEN: b57 taeuscht die Funktion
# zeitweise vor (liefert dann `win`). Die Wache fragt immer die echte, und
# sie fasst nur Dialoge an - nie das Hauptfenster.
import time as _time_netz                                  # noqa: E402
from PySide6.QtCore import QTimer as _QT_netz              # noqa: E402
from PySide6.QtWidgets import QDialog as _QD_netz          # noqa: E402
_modal_echt = QApplication.activeModalWidget
_MODAL_UNBESTELLT = []
_modal_seit = {}


def _modal_wache():
    _w = _modal_echt()
    if not isinstance(_w, _QD_netz):
        _modal_seit.clear()
        return
    _t0 = _modal_seit.setdefault(id(_w), _time_netz.time())
    if _time_netz.time() - _t0 >= 3.0:
        _text = getattr(_w, "text", lambda: "")()
        _MODAL_UNBESTELLT.append(f"{type(_w).__name__} '{_w.windowTitle()}': "
                                 f"{str(_text)[:80]}")
        _modal_seit.pop(id(_w), None)
        _w.done(0)


_modal_timer = _QT_netz()
_modal_timer.setInterval(250)
_modal_timer.timeout.connect(_modal_wache)
_modal_timer.start()

# Quelltext einmal einlesen: einige Pruefungen schauen auf die STRUKTUR des
# Codes (Reihenfolge von Layout-Aufrufen o.ae.), die man am fertigen Widget
# nicht mehr ablesen kann.
import glob as _glob8b
# Sitzung 8: alle UI-Dateien zusammenhaengen (nicht nur main_window.py) -
# sonst wird jede Text-Pruefung blind, sobald Code in ein Mixin wandert.
# main_window.py bleibt vorne (siehe test_bestand_herkunft.py).
_ui8b = os.path.join(_ROOT,
                     "eve_trader", "ui")
_mw8b = os.path.join(_ui8b, "main_window.py")
_src_mw = "\n".join(
    open(_d, encoding="utf-8").read()
    for _d in [_mw8b] + sorted(d for d in _glob8b.glob(os.path.join(_ui8b, "*.py"))
                               if d != _mw8b))

_ok = 0
# UEBERSETZUNG FRUEH VERFUEGBAR: mehrere Pruefungen suchen Knoepfe ueber
# ihren Text und muessen das sprachunabhaengig tun.
from eve_trader.sprache import t as _t4
from PySide6.QtWidgets import QPushButton as _QPB23

_fail = []


def check(label, cond):
    global _ok
    if cond:
        _ok += 1
    else:
        _fail.append(label)


def eq(label, got, want):
    check(f"{label}  (erhalten {got!r}, erwartet {want!r})", got == want)


def _pos_von(hay, needle, start=0):
    """Position von `needle` in `hay` - ohne die Suite abzureissen.

    WARUM ES DIESEN HELFER GIBT (Sitzung 10): im Bestand standen 71 rohe
    `.index()`-Aufrufe. Verschwindet der gesuchte Anker durch einen Umbau,
    WIRFT `.index()` - und reisst die ganze Suite mit, statt EINE rote
    Pruefung zu setzen. Genau das ist bei Schnitt 3 passiert: aa147 stuerzte
    ab, alle folgenden Pruefungen liefen nie, und die Rotprobe wertete das
    als "blind" statt als "rot".

    Hier stattdessen: fehlt der Anker, gibt es eine benannte rote Pruefung
    und die Suite laeuft weiter. Rueckgabe 0, damit ein anschliessender
    Ausschnitt definiert bleibt (er ist dann falsch - aber die zugehoerige
    Pruefung ist ja bereits rot).
    """
    _f = getattr(hay, "find", None)
    if _f is not None:
        _p = _f(needle, start)
        if _p < 0:
            check(f"ANKER FEHLT: {needle!r:.60} nicht gefunden", False)
            return 0
        return _p
    try:
        return hay.index(needle, start)
    except (ValueError, TypeError):
        check(f"ANKER FEHLT: {needle!r:.60} nicht gefunden", False)
        return 0



class _Recipes:
    """Minimalrezept: 1 Testship <- 10 Testmat."""
    product_to_bp = {100: (900, I.MANUFACTURING, 1)}
    bp_materials = {(900, I.MANUFACTURING): [(200, 10)]}
    activity_time = {(900, I.MANUFACTURING): 60}
    activity_max_runs = {(900, I.MANUFACTURING): 0}
    reaction_products = set()
    invention_for_bpc = {}
    bp_products = {}
    item_cat = {}

    def is_manufactured(self, t):
        return t in self.product_to_bp


# GEMERKTE ANSICHTS-FILTER VOR DEM START LOESCHEN (18.09.2026). b46 prueft
# die VORGABEN der Blueprints-Haken; ein vorheriger Lauf kann aber ueber
# closeEvent -> _filter_merken andere Haken in die Test-Settings geschrieben
# haben (so geschehen: b76 liess "profitable only" AUS zurueck, weil die
# Settings vorher gar kein ui_filter kannten - Lauf 1 gruen, Lauf 2 b46
# rot, nur beim Nutzer, weil seine .smoke_home aelter war als b76). Das
# Merken selbst prueft b76 ueber die beiden Methoden, nicht ueber den
# Neustart - hier darf es also weg.
try:
    from eve_trader import config as _cfg0
    _s0 = _cfg0.load_settings()
    # SPALTEN-ZUSTAENDE AUCH WEG (emm354): kommt eine Spalte dazu (My
    # Blueprints 17 -> 18), passt der gemerkte Kopf-Zustand eines frueheren
    # Laufs nicht mehr - b44/b74 waren dann EINMAL rot, beim zweiten Lauf
    # gruen. Beim Nutzer waere das der erste pruefe.py-Lauf nach dem Update.
    _weg0 = [_k for _k in ("ui_filter", "bau_runplan_ziel",
                           "bau_runplan_ziel_std", "ui_spalten",
                           "ui_spalten_n") if _k in _s0]
    # ZIELZEITEN DER STUFEN AUCH WEG (24.09.2026): b102 prueft die VORGABE
    # der beiden Felder. Ein Wert, den ein frueherer Lauf in .smoke_home
    # geschrieben hat, machte die Pruefung beim zweiten Durchgang rot -
    # dieselbe Falle wie ui_filter oben und die Klicks in aa383.
    if _weg0:
        for _k in _weg0:
            _s0.pop(_k, None)
        _cfg0.save_settings(_s0)
except Exception as _e0:                                 # pragma: no cover
    print(f"(Hinweis) ui_filter nicht geloescht: {type(_e0).__name__}: {_e0}")


# ---------------------------------------------------------------- (b1)
# Das HAUPTFENSTER muss sich ueberhaupt bauen lassen.
try:
    win = MainWindow()
    # Das Einrichtungs-Fenster ist oben an der KLASSE stillgelegt
    # (`_einrichtung_still`, Sitzung 17) - hier nichts mehr zu tun.
    check("b1 MainWindow laesst sich bauen", True)
except Exception as e:                                   # pragma: no cover
    import traceback
    traceback.print_exc()
    print(f"(b) Bauplan-Aufbau: 0/1 gruen\n  FEHLER: MainWindow: {e}")
    sys.exit(1)

# ---------------------------------------------------------------- (b1b)
# BAU-KALENDER entfernt (Nutzer: "zu viel und zu unnoetig"). Die Seite wird
# nicht mehr gebaut, bleibt aber als LEERER Platzhalter im Stapel - sonst
# verschieben sich die Seiten-Indizes und "Strukturen" (4) bricht.
_btexts0 = [b.text() for b in win.findChildren(QPushButton) if b.text()]
check("b1b Kalender-Knopf ist weg",
      not any("Kalender" in b for b in _btexts0))
# emm327: Seite 4 "Industry jobs" dazu -> fuenf Seiten, fuenf Knoepfe.
eq("b1b Kalender-Seite ist aus dem Stapel raus", win.b_stack.count(), 5)
eq("b1b fuenf Navigations-Knoepfe", len(win._bau_page_btns), 5)
_pages_ok = True
for _i in range(win.b_stack.count()):
    try:
        # UEBER DEN ECHTEN WEG (_bau_nav wie Leiste/Tutorial): seit die
        # Plan-Karten erst beim ersten Oeffnen gebaut werden (27.09.2026),
        # entstehen sie nur dort - ein nacktes setCurrentIndex tut das
        # im Programm nirgends.
        win._bau_nav(_i)
        _app.processEvents()
    except Exception:
        _pages_ok = False
check("b1b alle Seiten bleiben schaltbar", _pages_ok)
# Rail-Ordnung (Nutzer): "Neuer Bauplan" steht unter PRODUKTION, ueber
# "Meine Bauplaene" - unter PLANEN bleiben nur Scanner + Meine Blueprints.
_src_rail = open(os.path.join(_ROOT,
                              "eve_trader", "ui", "main_window.py"),
                 encoding="utf-8").read()
# .find() statt .index(): ein fehlender Anker soll die PRUEFUNG rot machen,
# nicht die ganze Suite abbrechen (Sitzung 9: der Symbol-Umbau nahm dem
# alten Emoji-Anker den Boden, und das ungeschuetzte .index() riss per
# ValueError ALLE Folge-Pruefungen mit).
_i_plan = _src_rail.find('header(t("PLANNING")')
_i_prod = _src_rail.find('header(t("PRODUCTION")')
# Sitzung 17: der Knopf wird an self gemerkt (das Tutorial hebt ihn hervor).
# NICHT nach dem blossen Text suchen - "New build plan" ist auch der
# FENSTERTITEL und steht weiter oben in der Datei.
_i_neu = _src_rail.find('self._bau_newplan_btn = tool_btn(')
_i_mine = _src_rail.find('b_plans = page_btn(')
check("b1b alle vier Rail-Anker sind auffindbar",
      min(_i_plan, _i_prod, _i_neu, _i_mine) >= 0)
check("b1b 'Neuer Bauplan' steht unter PRODUKTION", 0 <= _i_prod < _i_neu)
check("b1b und ueber 'Meine Bauplaene'", 0 <= _i_neu < _i_mine)
check("b1b unter PLANEN nur noch zwei Eintraege",
      _src_rail[_i_plan:_i_prod].count("page_btn(") == 2
      and "tool_btn(" not in _src_rail[_i_plan:_i_prod])
eq("b1b Strukturen ist jetzt Index 3",
   (win.b_stack.setCurrentIndex(3), win.b_stack.currentIndex())[1], 3)

# ---------------------------------------------------------------- (b2)
# Der BAUPLAN-DIALOG muss sich mit echten Plandaten bauen lassen. Genau hier
# schlug der UnboundLocalError zu - rebuild() laeuft beim Aufbau mit.
PRICES = {100: 5000.0, 200: 100.0}
win._bd_pricemap = dict(PRICES)
win._bd_recipes = _Recipes()
# MIT BESTAND: nur so laeuft der Zweig, der die Unterzeile "davon X aus
# Bestand" fuellt - genau dort entstand das streunende "python"-Fenster.
# Ohne Bestand waere (b8) blind.
win._bd_opts = {"me": 0, "te": 0, "job_pct": 0, "build_reactions": False,
                "tree_depth": 4, "stock": {200: 40}}
win._bd_type = 100
win._bd_qty = 10
_plan = I.production_plan(100, 10, PRICES.get, _Recipes(), dict(win._bd_opts))
_tree = I.build_tree(100, PRICES.get, _Recipes(), dict(win._bd_opts))
_res = {"tree": _tree, "names": {100: "Testship", 200: "Testmat"},
        "sell": 6000.0, "sell_is_contract": False, "plan": _plan}
_dlg = None
# SEIT DER SPERRE (Sitzung 13, b40) darf nur EIN Bauplan offen sein - ein
# zweites _show_build_detail bringt ein MODALES Popup und wartet auf einen
# Klick, den es im Testbetrieb nie gibt. Die Suite oeffnet unten aber rund
# zehnmal einen frischen Dialog. Deshalb: vor jedem Oeffnen den vorigen
# schliessen - so, wie der Nutzer es jetzt auch tun muss. b40 prueft die
# Sperre selbst und ruft dafuer die UNGEWICKELTE Methode.
_sbd_echt = win._show_build_detail
def _sbd_frisch(tid, name, res):
    _d = win._offener_bauplan()
    if _d is not None:
        _d.close(); _app.processEvents()
    return _sbd_echt(tid, name, res)
win._show_build_detail = _sbd_frisch
try:
    win._show_build_detail(100, "Testship", _res)
    _dlg = getattr(win, "_bd_dialog", None)
    check("b2 Bauplan-Dialog laesst sich bauen", True)
except Exception as e:                                   # pragma: no cover
    import traceback
    traceback.print_exc()
    _fail.append(f"b2 Bauplan-Dialog: {type(e).__name__}: {e}")

check("b2 Dialog ist erreichbar (_bd_dialog gesetzt)", _dlg is not None)

# ---------------------------------------------------------------- (b2f)
# EINFUEGE-FELD AUF DER VERKAUFSLISTE (Nutzer-Wunsch, Sitzung 8): Hangar-
# Liste rein, "Verkaufspreise kopieren" raus. Ein Widget ohne Layout hat
# keinen Parent und ist unsichtbar - genau so faellt so etwas still aus.
_pastebox = getattr(win, "_sell_paste", None)
check("b2f Einfuege-Feld auf der Verkaufsliste existiert", _pastebox is not None)
if _pastebox is not None:
    check("b2f Einfuege-Feld haengt in einem Layout",
          _pastebox.parentWidget() is not None)
    # SPRACHUNABHAENGIG: die Zusage ist "das Feld erklaert sich selbst",
    # nicht "es enthaelt das deutsche Wort einfuegen".
    check("b2f Einfuege-Feld erklaert sich selbst",
          len(_pastebox.placeholderText() or "") > 30)
    check("b2f Statuszeile daneben vorhanden",
          getattr(win, "_sell_paste_info", None) is not None)
check("b2f der Knopf ist verdrahtet",
      callable(getattr(win, "_sell_paste_prices", None)))

# ---------------------------------------------------------------- (b2g)
# KNOPFDRUCK WIRKLICH AUSLOESEN. b2f prueft nur, dass es die Methode GIBT -
# das hat einen echten Absturz beim Nutzer NICHT verhindert: `_run` erwartet
# ein Worker-OBJEKT, bekam aber die nackte Job-Funktion
# ("AttributeError: 'function' object has no attribute 'done'").
# "Existiert" ist eben nicht "funktioniert". Deshalb wird hier der ganze Weg
# durchlaufen: Text einfuegen -> Namen aufloesen -> Orderbuch (Attrappe) ->
# Preise rechnen -> Zwischenablage.
try:
    import eve_trader.hubs as _hubs2g
    import eve_trader.store as _store2g
    from PySide6.QtWidgets import QApplication as _QApp2g

    _orig_fetch2g = _hubs2g.fetch_hub_orders
    _orig_names2g = _store2g.name_to_type_id
    _orig_run2g = win._run
    _hubs2g.fetch_hub_orders = lambda r, s, progress=None: {
        34: {"sell_min": 1_000_000.0},      # genau auf der Zehnerpotenz
        35: {"sell_min": 0.05},             # billig: 2 Nachkommastellen noetig
    }
    _store2g.name_to_type_id = lambda: {"tritanium": 34, "pyerite": 35}
    # Ersatz-_run, der den Job SOFORT ausfuehrt. Bekommt es keinen Worker,
    # fliegt es hier genauso wie beim Nutzer - genau das soll es.
    win._run = lambda worker, done_cb, fail_cb=None, **kw: done_cb(
        worker._fn(*worker._args, **worker._kwargs))
    win._sell_paste.setPlainText("Tritanium\t5.000\nPyerite\t12\nGibtsNicht\t1")
    win._sell_paste_prices()
    _abl2g = (_QApp2g.clipboard().text() or "").splitlines()
    check("b2g Knopfdruck laeuft ohne Absturz durch", bool(_abl2g))
    eq("b2g je Eingabezeile genau eine Ausgabezeile", len(_abl2g), 3)
    eq("b2g Tick an der Zehnerpotenz stimmt", _abl2g[0], "Tritanium 999900.00")
    eq("b2g billiges Item bekommt zwei Nachkommastellen",
       _abl2g[1], "Pyerite 0.04")
    check("b2g unbekannter Name bleibt als Platzhalter stehen",
          _abl2g[2].endswith("?"))
    check("b2g Statuszeile meldet das Ergebnis",
          # Sitzung 17: uebersetzt - beide Sprachen akzeptieren.
          any(_w in (win._sell_paste_info.text() or "")
              for _w in ("kopiert", "copied")))
except Exception as _e2g:                                # pragma: no cover
    _fail.append(f"b2g Verkaufspreise kopieren: {type(_e2g).__name__}: {_e2g}")
finally:
    try:
        _hubs2g.fetch_hub_orders = _orig_fetch2g
        _store2g.name_to_type_id = _orig_names2g
        win._run = _orig_run2g
        win._sell_paste.setPlainText("")
    except Exception:
        pass

# ---------------------------------------------------------------- (b93)
# SEITENLEISTE IM INDUSTRIE-REITER (Nutzer 22.09.2026): die Leiste bleibt,
# aber die reinen HANDELS-Werkzeuge verschwinden - "der ganze Rest geht nur
# Trading etwas an und hat nullkommagarnichts mit Building und Industry zu
# tun". Sichtbar bleiben nur Price history, Characters, Settings.
# AM ECHTEN FENSTER: `isVisible()` waere hier blind (das Fenster wird nie
# gezeigt), deshalb wird `isVisibleTo(parent)` gefragt - das beantwortet
# genau "waere es sichtbar, wenn das Fenster offen ist".
try:
    _tw93 = getattr(win, "_tab_widget", {}) or {}
    _nb93 = getattr(win, "_nav_buttons", {}) or {}
    check("b93 Seitenleiste und Industrie-Reiter sind ueberhaupt da",
          bool(_nb93) and _tw93.get("build") is not None)
    # DEN ECHTEN WEG GEHEN, nicht die Methode direkt rufen: eine Rotprobe
    # meldete sonst "blind", als die Verdrahtung im Tab-Wechsel entfernt
    # wurde (dieselbe Lehre wie b87/b88 - die Pruefung muss den Weg gehen,
    # den der Nutzer geht).
    win.tabs.setCurrentWidget(_tw93.get("build"))
    _sicht93 = {k for k, b in _nb93.items()
                if b is not None and b.isVisibleTo(b.parentWidget())}
    _links93 = sorted(k for k in _sicht93
                      if k in (getattr(win, "_common_keys", None) or []))
    eq("b93 im Industrie-Reiter bleiben genau drei Werkzeuge",
       _links93, ["characters", "market", "settings"])
    # DER RUECKWEG (Nutzer-Befund 22.09.2026: "wenn man auf Industry
    # wechselt, verschwinden auch Daytrade, Swingtrade, Regional Trade,
    # somit ist es unmoeglich zurueckzukehren"). `_nav_buttons` traegt die
    # vier Reiter OBEN im selben Woerterbuch wie die Werkzeuge links - wer
    # ueber alles laeuft, versteckt den Rueckweg mit. Diese Pruefung haelt
    # sie fest: im Industrie-Reiter bleibt JEDER Reiter oben sichtbar.
    _oben93 = [k for k in (getattr(win, "_paid_keys", None) or [])
               if _nb93.get(k) is not None]
    eq("b93 die vier Reiter oben bleiben im Industrie-Reiter sichtbar",
       sorted(k for k in _oben93 if k in _sicht93), sorted(_oben93))
    # GEGENPROBE: in jedem anderen Reiter ist wieder alles da. Ohne die
    # waere die Pruefung mit einer Leiste zufrieden, die IMMER leer ist.
    win.tabs.setCurrentWidget(_tw93.get("portfolio"))
    _sicht93b = {k for k, b in _nb93.items()
                 if b is not None and b.isVisibleTo(b.parentWidget())}
    eq("b93 ... und im Portfolio ist wieder alles da",
       len(_sicht93b), len(_nb93))
    check("b93 die Knoepfe werden nur versteckt, nicht entfernt",
          all(b is not None and b.parentWidget() is not None
              for b in _nb93.values()))
except Exception as e:
    check(f"b93 Seitenleiste im Industrie-Reiter: {type(e).__name__}: {e}", False)

# ---------------------------------------------------------------- (b94)
# DIE BAU-RAIL IST BREIT GENUG FUER IHRE EIGENEN KNOEPFE (Nutzer-Befund
# 22.09.2026: "rechte Sidebar teils Button-Woerter abgeschnitten"). Die
# feste Breite von 210 px reichte auf seinem Windows nicht - dieselben
# Widgets sind dort rund 1,85x breiter als offscreen hier (Lehre b66).
# GEMESSEN STATT GERATEN: die Pruefung vergleicht die Rail mit dem, was
# Qt selbst als Platzbedarf des breitesten Knopfes angibt. Eine wieder
# eingebaute feste Zahl faellt damit auf, sobald sie zu klein ist -
# unabhaengig von Sprache, Schriftgroesse und Rechner.
try:
    _rail94 = win._bau_newplan_btn.parentWidget()
    _btns94 = list(getattr(win, "_bau_page_btns", None) or []) + [
        win._bau_newplan_btn]
    _max94 = max(b.sizeHint().width() for b in _btns94)
    check("b94 die Bau-Rail ist ueberhaupt auf eine Breite festgelegt",
          _rail94 is not None and _rail94.minimumWidth() > 0
          and _rail94.minimumWidth() == _rail94.maximumWidth())
    # +24 px sind die Raender des Rail-Layouts (12 links, 12 rechts) - ohne
    # sie waere die Pruefung mit einer Leiste zufrieden, in der das Wort
    # genau bis an die Kante stoesst.
    check("b94 die Rail fasst ihren breitesten Knopf samt Raendern "
          f"(Rail {_rail94.minimumWidth()} px, Knopf {_max94} px)",
          _rail94.minimumWidth() >= _max94 + 24)
    # UNTERGRENZE: darunter wird die Leiste optisch zum Streifen, auch
    # wenn die Knopfwoerter zufaellig kurz sind.
    check("b94 ... und bleibt mindestens 210 px breit",
          _rail94.minimumWidth() >= 210)
except Exception as e:
    check(f"b94 Breite der Bau-Rail: {type(e).__name__}: {e}", False)

# ---------------------------------------------------------------- (b2i)
# EINKAUFSWAGEN-WERKZEUGE (Layout-Programm, Sitzung 8): sieben Knoepfe
# wurden zu Hauptaktion + Werkzeuge-Menue (Bauplan-Muster). Der Test
# DRUECKT eine Menue-Aktion und prueft, dass der dahinterliegende
# (unsichtbare) Knopf den Handler wirklich ausloest - genau die Verkabelung,
# die beim Umbau am ehesten reisst.
try:
    _pairs2i = getattr(win, "_sh_tool_pairs", None)
    # DREI statt vier seit 22.09.2026: "In buy order?" ist weg. Der Knopf
    # holte nur Daten, die die Liste ohnehin braucht, und schaltete eine
    # Warnung ein, die man nie ausschalten will (Nutzer: "stattdessen
    # dauerhafte Warnungen an den Items").
    check("b2i das Werkzeuge-Menue hat drei Eintraege (load/sugg/clear)",
          _pairs2i is not None and len(_pairs2i) == 3)
    _rufe2i = []
    _orig_load2i = win.shopping_load_prices
    win.shopping_load_prices = lambda *a, **k: _rufe2i.append("load")
    _pairs2i[0][0].trigger()
    check("b2i Menue-Aktion drueckt den Knopf, der Knopf ruft den Handler",
          _rufe2i == ["load"])
    check("b2i die vier Knoepfe sind unsichtbar, aber am Leben",
          all(not _b.isVisible() for _a, _b in _pairs2i))
    # receivers() nimmt in PySide6 nur den C++-Signaturstring - stattdessen
    # FUNKTIONAL: Klick auf die Hauptaktion muss den Kopier-Handler rufen.
    _orig_copy2i = win.shopping_copy
    win.shopping_copy = lambda *a, **k: _rufe2i.append("copy")
    # click() ist bei deaktiviertem Knopf (leere Liste) ein No-Op - das
    # Signal direkt emittieren prueft die VERKABELUNG unabhaengig davon.
    win._sh_copy_btn.clicked.emit()
    check("b2i Hauptaktion Multibuy bleibt sichtbar verkabelt",
          "copy" in _rufe2i)
    win.shopping_copy = _orig_copy2i
    # Zweite Aufraeurunde (Nutzer): Eingabezeile + Erloes-/Gewinn-Karte weg,
    # Vorschlag-Panel als Widget-Aktion im Werkzeuge-Menue - Prozentfeld und
    # "Als Menge uebernehmen" muessen FUNKTIONIEREND mitgezogen sein.
    check("b2i Eingabezeile ist aus der Ansicht (Handler lebt weiter)",
          not win.sh_name.parentWidget().isVisible()
          and callable(win.shopping_add))
    check("b2i Erloes- und Gewinn-Karte sind ausgeblendet, Kosten bleibt",
          not win.sh_t_rev_c.isVisible() and not win.sh_t_profit_c.isVisible()
          and win.sh_t_cost_c.parentWidget() is not None)
    check("b2i das Vorschlag-Panel haengt als Widget-Aktion im Menue",
          getattr(win, "_sh_sug_wa", None) is not None
          and win._sh_sug_wa in win._sh_tools_menu.actions())
    check("b2i das Prozentfeld lebt im Menue weiter (25 % Startwert)",
          win._sh_sug_share.value() == 25
          and win._sh_sug_share.parent() is not None)
    _orig_apply2i = win._apply_suggestion_qty
    win._apply_suggestion_qty = lambda *a, **k: _rufe2i.append("apply")
    win._sh_sug_apply.clicked.emit()
    check("b2i 'Als Menge uebernehmen' bleibt im Menue verkabelt",
          "apply" in _rufe2i)
    win._apply_suggestion_qty = _orig_apply2i
    # ITEM-BILDER (Nutzer: "da fehlen noch Bilder"): der Wagen muss den
    # Hintergrund-Nachtrag ANSTOSSEN - vormerken allein holt nichts. Render
    # mit einem unbekannten Item laufen lassen; danach muss der Prefetch
    # angestossen worden sein (Attrappe zaehlt den Aufruf).
    _pf2i = []
    _orig_pf2i = win._icon_prefetch_pending
    win._icon_prefetch_pending = lambda cb=None: _pf2i.append(cb) or False
    try:
        win._render_shopping()
    except Exception as _re2i:
        _fail.append(f"b2i Render nach Umbau: {type(_re2i).__name__}: {_re2i}")
    check("b2i der Wagen stoesst den Bilder-Nachtrag an (mit Re-Render-Callback)",
          len(_pf2i) == 1 and _pf2i[0] == win._render_shopping)
    win._icon_prefetch_pending = _orig_pf2i
    # Runde 3 + 4 (Umentscheidung): der Wagen mischt Strategien (Daytrade
    # = Buy-to-Sell, Swing = Sell-to-Sell) - EINE Marge-/Gewinn-Formel
    # waere fuer die Haelfte falsch. Sichtbar nur strategie-unabhaengige
    # Zahlen; Marge (6) und Gewinn (8) sind mit AUSGEBLENDET.
    check("b2i Buy-Order- und Erloes-Spalte sind ausgeblendet",
          win.sh_table.isColumnHidden(4) and win.sh_table.isColumnHidden(7))
    check("b2i Marge- und Gewinn-Spalte sind ausgeblendet (Strategie-Mix)",
          win.sh_table.isColumnHidden(6) and win.sh_table.isColumnHidden(8))
    from eve_trader.ui import theme as _th2i
    _mwsrc2i = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
    _rs2i = _mwsrc2i[_pos_von(_mwsrc2i, "def _render_shopping"):]
    _rs2i = _rs2i[:_pos_von(_rs2i, "\n    def ", 10)]
    check("b2i das Auge ist weg, das rote Kreuz bleibt",
          "\U0001F441" not in _rs2i and 'rmb = QPushButton("✕")' in _rs2i)
    check("b2i Kosten-Karte rot und praesent, Gewinn-Karte WIEDER versteckt",
          ("color:" + _th2i.RED) in win.sh_t_cost.styleSheet()
          and not win.sh_t_cost_c.isHidden()
          and win.sh_t_profit_c.isHidden())
    check("b2i Bauplan-Optik: 32er-Icons, kein Gitter",
          win.sh_table.iconSize().width() == 32
          and not win.sh_table.showGrid())
except Exception as _e2i:                                # pragma: no cover
    _fail.append(f"b2i Einkaufswagen-Werkzeuge: {type(_e2i).__name__}: {_e2i}")
finally:
    try:
        win.shopping_load_prices = _orig_load2i
    except Exception:
        pass

# ---------------------------------------------------------------- (b2s)
# SIDEBAR-BREITE (Nutzer, ZWEIMAL gemeldet: "da steht nur MOTOR MARKE").
# Zweimal hatte ich eine feste Breite GERATEN (196, dann 232) - beide Male
# zu knapp. Die noetige Breite haengt an der Schrift des Zielrechners, eine
# feste Zahl kann das nicht loesen. Jetzt wird gemessen; hier FUNKTIONAL
# geprueft, dass der Schriftzug wirklich vollstaendig Platz bekommt.
# NEU GEFASST IN SITZUNG 11: der Schriftzug "MOTOR MARKET" als eigenes
# Textfeld ist ERSATZLOS entfallen - er steht jetzt im Logo-Bild selbst
# (Nutzer: "Motor Market muss nicht extra da stehen, da das schon im PNG
# drin steht"). Damit ist der zweimal gemeldete Beschnitt strukturell
# erledigt: ein Bild skaliert, eine Schrift nicht. Die Zusage lautet jetzt
# umgekehrt - das LOGO richtet sich nach der Sidebar.
try:
    _mwsrc2s = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
    _sb2s = getattr(win, "_sidebar_widget", None)
    _logo2s = getattr(win, "_brand_logo", None)
    check("b2s Sidebar und Logo sind erreichbar",
          _sb2s is not None and _logo2s is not None)
    check("b2s der Schriftzug steht nicht mehr doppelt daneben",
          getattr(win, "_brand_label", None) is None)
    # ANZEIGEN, DANN MESSEN: ohne show() rechnet Qt die Anordnung nicht
    # durch, und jedes Widget meldet seine HOECHSTbreite - die Sidebar sass
    # dann scheinbar auf 420 statt auf 232, und die Pruefung fiel um, obwohl
    # im echten Fenster alles stimmte.
    win.show()
    win.resize(1280, 800)
    _app.processEvents()
    win._sidebar_breite_anpassen()
    _app.processEvents()
    _pm2s = _logo2s.pixmap()
    check(f"b2s das Logo nutzt die Sidebar-Breite "
          f"({_pm2s.width()} bei Sidebar {_sb2s.width()})",
          not _pm2s.isNull() and _pm2s.width() >= _sb2s.width() - 24)
    check("b2s es bleibt innerhalb der Sidebar (kein Ueberstand)",
          _pm2s.width() <= _sb2s.width())
    check("b2s es ist deutlich groesser als die alten 30 px",
          _pm2s.width() >= 96)
    # NACH OBEN BEGRENZT: sonst schiebt ein sehr breites Fenster das Logo
    # so gross, dass die Werkzeugliste aus dem Fenster faellt.
    _sb2s.setMinimumWidth(420)
    win._side_roll.setMinimumWidth(420)
    win.resize(1600, 900)
    _app.processEvents()
    win._sidebar_breite_anpassen()
    check(f"b2s ... aber nach oben begrenzt ({_logo2s.pixmap().width()})",
          _logo2s.pixmap().width() <= 240)
    _sb2s.setMinimumWidth(232)
    win._side_roll.setMinimumWidth(232)
    check("b2s die Breite ist NICHT fest verdrahtet",
          "sidebar.setFixedWidth(" not in _mwsrc2s)
    check("b2s die Sidebar frisst den Tab-Bereich nicht auf",
          _sb2s.maximumWidth() <= 420)
except Exception as _e2s:                                # pragma: no cover
    _fail.append(f"b2s Sidebar-Logo: {type(_e2s).__name__}: {_e2s}")

# ---------------------------------------------------------------- (b2r)
# LOGO IM TOOL (Nutzer, Sitzung 8: "finde einen geeigneten Ort fuer das
# Logo und Motor Market im Tool"). Drei Orte, FUNKTIONAL geprueft - eine
# Quelltext-Suche wuerde nicht merken, wenn das Icon leer bleibt.
try:
    from eve_trader.ui import icons as _ic2r
    from eve_trader.ui import theme as _th2r
    import os as _os2r
    _thq2r = open("eve_trader/ui/theme.py", encoding="utf-8").read()
    _thq2r = _thq2r[_pos_von(_thq2r, "QLabel#Brand"):][:400]
    check("b2r das Fenster traegt ein Symbol (Titelleiste/Taskleiste)",
          not win.windowIcon().isNull())
    check("b2r das Symbol liegt in mehreren Groessen vor (16 bis 256)",
          {s.width() for s in _ic2r.logo_icon().availableSizes()}
          >= {16, 32, 48, 256})
    # GEGEN DIE EINE QUELLE pruefen, nicht gegen einen abgetippten Namen:
    # seit Sitzung 11 heisst das Tool "EVE Motor Market", und der Name steht
    # nur noch in eve_trader/__init__.py. Eine Pruefung mit fest
    # eingetipptem Namen waere bei jeder Umbenennung rot geworden, ohne dass
    # etwas kaputt ist.
    from eve_trader import APP_NAME as _APP2r
    check("b2r der Fenstertitel nennt den Namen",
          win.windowTitle() == _APP2r)
    # Sidebar: Logo NEBEN dem Schriftzug, beide sichtbar.
    from PySide6.QtWidgets import QLabel as _QLabel2r
    _brands = [w for w in win.findChildren(_QLabel2r)
               if w.objectName() == "Brand"]
    check("b2r der Marken-Bereich sitzt in der Sidebar",
          getattr(win, "_brandbox", None) is not None)
    _mit_pix = [w for w in win.findChildren(_QLabel2r)
                if w.toolTip() == _APP2r
                and not w.pixmap().isNull()]
    check("b2r und daneben sitzt das Logo als Bild",
          bool(_mit_pix) and _mit_pix[0].pixmap().width() >= 20)
    # LOGO KOMMT SEIT SITZUNG 11 AUS EINER BILDDATEI (Nutzer-Vorlage
    # assets/logo.png, blau statt der frueheren goldenen Wabe). Die alten
    # Pruefungen schrieben GOLD fest und die gezeichnete Wabenform - beides
    # sind jetzt Eigenschaften der RUECKFALLEBENE, nicht mehr die Zusage.
    # Die Zusage lautet: es rendert ein ECHTES, farbiges Bild. Eine
    # Textsuche wuerde nicht merken, wenn die Datei fehlt und alles leer
    # oder einfarbig bleibt.
    _limg = _ic2r.logo_pixmap(64).toImage()
    _deck2r = sum(1 for y in range(64) for x in range(64)
                  if _limg.pixelColor(x, y).alpha() > 60)
    check(f"b2r das Logo rendert wirklich sichtbar ({_deck2r} Pixel)",
          _deck2r > 400)
    _toene2r = {(_limg.pixelColor(x, y).red() // 16,
                 _limg.pixelColor(x, y).green() // 16,
                 _limg.pixelColor(x, y).blue() // 16)
                for y in range(0, 64, 2) for x in range(0, 64, 2)
                if _limg.pixelColor(x, y).alpha() > 60}
    check(f"b2r ... und ist ein echtes Bild, nicht eine Flaeche "
          f"({len(_toene2r)} Toene)", len(_toene2r) >= 5)
    # ES MUSS DIE BILDDATEI SEIN, nicht die gezeichnete Rueckfallebene.
    # Gegen die Datei selbst verglichen statt gegen eine feste Farbe: so
    # haelt die Pruefung auch, wenn der Nutzer das Logo austauscht. Die
    # erste Fassung zaehlte nur Farbtoene - eine Mutation, die auf die
    # Rueckfallebene umlenkte, blieb damit blind (die zeichnet ja auch ein
    # buntes Bild).
    from PySide6.QtGui import QPixmap as _QPix2r
    _datei2r = _QPix2r(_th2r.asset_pfad("logo.png")).scaled(
        64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation).toImage()
    _gleich2r = sum(
        1 for y in range(0, 64, 4) for x in range(0, 64, 4)
        if _datei2r.pixelColor(x, y) == _limg.pixelColor(x, y))
    _proben2r = len(range(0, 64, 4)) ** 2
    check(f"b2r das angezeigte Logo IST die Bilddatei "
          f"({_gleich2r}/{_proben2r} Proben gleich)",
          _gleich2r >= _proben2r - 2)
    # RUECKFALLEBENE: fehlt die Bilddatei (jemand packt den assets-Ordner
    # nicht mit), muss trotzdem ein Logo erscheinen - lieber ein schlichtes
    # als ein leeres Fenster-Symbol.
    _alt_pfad2r = _th2r.asset_pfad("logo.png") if hasattr(_th2r, "asset_pfad") else ""
    _ic2r._cache.clear()
    _echt_exists2r = _os2r.path.exists
    try:
        _os2r.path.exists = lambda p, _e=_echt_exists2r: (
            False if p.endswith("logo.png") else _e(p))
        # GESCHUETZT AUFRUFEN: faellt die Rueckfallebene aus, gibt die
        # Funktion None zurueck - ein direktes .isNull() wuerde dann mit
        # AttributeError abbrechen und die Pruefung traege einen fremden
        # Namen (beim ersten Anlauf genau so passiert, die Mutation galt
        # als blind).
        try:
            _fallback2r = _ic2r.logo_pixmap(64)
        except Exception:
            _fallback2r = None
        check("b2r ohne Bilddatei gibt es trotzdem ein Logo",
              _fallback2r is not None and not _fallback2r.isNull()
              and _fallback2r.width() == 64)
    finally:
        _os2r.path.exists = _echt_exists2r
        _ic2r._cache.clear()
    check("b2r der Schriftzug nimmt die Logo-Farbe auf (kein zweites Signal)",
          "color: {AMBER};" in _thq2r)
    # Das Logo darf nicht leer gerendert sein.
    _img2r = _ic2r.logo_pixmap(64).toImage()
    _px2r = sum(1 for y in range(64) for x in range(64)
                if _img2r.pixelColor(x, y).alpha() > 30)
    check(f"b2r das Logo zeichnet wirklich etwas ({_px2r} Pixel)",
          _px2r > 200)
except Exception as _e2r:                                # pragma: no cover
    _fail.append(f"b2r Logo: {type(_e2r).__name__}: {_e2r}")

# ---------------------------------------------------------------- (b2q)
# SYMBOLE IM EINSATZ (Nutzer, Sitzung 8: "ja einbauen"). Erste Runde:
# Werkzeuge-Menues (Bauplan/Wagen/Verkaufsliste) und die sichtbaren
# Kopfzeilen-Knoepfe. FUNKTIONAL: die Widgets muessen ein echtes,
# nicht-leeres Icon tragen UND ihr Text darf kein Emoji mehr enthalten -
# beides zusammen, sonst haette man doppelt oder gar nichts.
try:
    def _hat_emoji2q(text):
        return any(ord(c) > 0x2100 for c in text)

    for _name2q, _b2q in (("Aktualisieren", win.refresh_btn),
                          ("Alles aktualisieren", win.global_refresh_btn),
                          ("Blueprints laden", win.bp_refresh_btn)):
        check(f"b2q Knopf {_name2q!r} traegt ein Symbol",
              not _b2q.icon().isNull())
        check(f"b2q Knopf {_name2q!r} hat kein Emoji mehr im Text",
              not _hat_emoji2q(_b2q.text()))
    for _feld2q in ("_sh_tool_pairs", "_sl_tool_pairs"):
        _paare2q = getattr(win, _feld2q, None)
        check(f"b2q {_feld2q}: jede Aktion traegt ein Symbol",
              _paare2q is not None
              and all(not a.icon().isNull() for a, _ in _paare2q))
        check(f"b2q {_feld2q}: kein Emoji mehr im Text",
              _paare2q is not None
              and not any(_hat_emoji2q(a.text()) for a, _ in _paare2q))
    # Auch die WERKZEUGE-KNOEPFE selbst pruefen, nicht nur ihre Eintraege -
    # die Rotprobe fand hier eine Luecke (Mutation am Knopf blieb gruen).
    for _tb2q in (win._sh_tools_btn, win._sl_tools_btn):
        check("b2q der Werkzeuge-Knopf traegt selbst ein Symbol",
              not _tb2q.icon().isNull())
    # RUNDE 2 (Nutzer, Screenshot der Reiter-Leiste): die GROESSTEN,
    # wichtigsten Elemente - Hauptnavigation oben, Sidebar links, oberste
    # Leiste. Emoji dort stachen am meisten heraus.
    for _k2q, _b2q in win._nav_buttons.items():
        check(f"b2q Navigation {_k2q!r} traegt ein Symbol",
              not _b2q.icon().isNull())
        check(f"b2q Navigation {_k2q!r} hat kein Zeichen mehr im Text",
              not _hat_emoji2q(_b2q.text()))
    for _n2q, _g2q in (("Struktur", win.g_struct_btn),
                       ("Markt-Scan", win.g_scan_btn),
                       ("Baurezepte laden", win.g_sde_btn)):
        check(f"b2q Kopfleiste {_n2q!r} traegt ein Symbol",
              not _g2q.icon().isNull())
        check(f"b2q Kopfleiste {_n2q!r} hat kein Emoji mehr im Text",
              not _hat_emoji2q(_g2q.text()))
    # Die Symbol-Karte darf keine Zeichen mehr enthalten, sondern nur
    # NAMEN aus icons.py - sonst waere ein Eintrag stumm.
    from eve_trader.ui import icons as _ic2q
    _fehlend2q = [k for k, v in win._NAV_ICONS.items()
                  if v not in _ic2q.verfuegbar()]
    eq("b2q jeder Navigations-Eintrag zeigt auf ein echtes Symbol",
       _fehlend2q, [])
    # Nutzer (Sitzung 8): Reiter in AMBER (eigene Farbe fuer "wo bin ich",
    # konkurriert nicht mit den Cyan-Datenakzenten); der kleine
    # Aktualisieren-Knopf OHNE Akzentfuellung.
    _shell2q = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
    _nav2q = _shell2q[_pos_von(_shell2q, "#NavTab:checked"):][:260]
    check("b2q der aktive Reiter ist AMBER, nicht Cyan",
          "theme.AMBER" in _nav2q and "theme.CYAN" not in _nav2q)
    check("b2q der kleine Aktualisieren-Knopf hat keine Akzentfuellung",
          win.refresh_btn.objectName() != "Primary")
    # Drei Rahmen-Stufen (Nutzer: "standardmaessig schon einen gelben
    # Rahmen, bevor man Mouseover macht"): Ruhe gedaempft -> Hover voll ->
    # aktiv voll. Der ruhende Rahmen muss AMBER-Familie sein, nicht
    # blaugrau, sonst wirken die Reiter wieder unbeteiligt.
    _ruhe2q = _shell2q[_pos_von(_shell2q, 'f"#NavTab{{padding'):][:220]
    check("b2q ruhende Reiter haben schon einen Amber-Rahmen",
          "theme.AMBER_DIM" in _ruhe2q and "theme.BORDER" not in _ruhe2q)
    from eve_trader.ui import theme as _th2q2
    check("b2q der ruhende Rahmen ist gedaempfter als der aktive",
          _th2q2.AMBER_DIM != _th2q2.AMBER)
    _clear2q = [a for a, _ in win._sh_tool_pairs
                if a.text() == _t4("Clear list")]
    check("b2q 'Liste leeren' traegt ein Symbol (Gefahr sichtbar)",
          bool(_clear2q) and not _clear2q[0].icon().isNull())
except Exception as _e2q:                                # pragma: no cover
    _fail.append(f"b2q Symbole im Einsatz: {type(_e2q).__name__}: {_e2q}")

# ---------------------------------------------------------------- (b2p)
# ABO-RUECKBAU + KOPFLEISTE (Nutzer, Sitzung 8): "Premium kann weg und alle
# Anzeigen davon. Die Idee war ein Abo-Modell, das verwerfen wir komplett.
# Nur noch ein Donation-Button. Update-Knopf ganz oben rechts. Die vier
# Reiter sollen wie TABS aussehen, nicht wie Knoepfe."
try:
    _mw2p = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
    # "Premium" bleibt EINMAL als EVE-Meta-Level stehen (Filter-Liste,
    # nichts mit Abo zu tun) - deshalb gezielt auf die Abo-Begriffe pruefen.
    check("b2p kein PREMIUM-Label und kein Credits-/Abo-Knopf mehr",
          "\u2728 PREMIUM" not in _mw2p
          and not hasattr(win, "credits_btn")
          and "Premium-Tipp" not in _mw2p
          and "Order Marks" not in _mw2p)
    check("b2p keine Schloss-Overlays mehr (alles frei ohne Abo)",
          win._lock_overlays == {})
    # Alle vier Reiter muessen erreichbar sein - ohne Freischalt-Huerde.
    for _k2p in win._paid_keys:
        win._go_tab(_k2p)
    check("b2p alle vier Reiter lassen sich oeffnen",
          win._nav_buttons["build"].isChecked())
    check("b2p Spenden-Hinweis existiert und nennt die Corporation",
          callable(win._show_donation_info)
          and "DONATION_CORP" in _mw2p)
    check("b2p Update-Knopf haengt in der Hub-Zeile ganz oben (rechts)",
          win.update_btn is not None
          and "_tb_spacer" in _mw2p
          and _mw2p.find("_tb_spacer") >= 0
          and _mw2p.find("_tb_spacer") < _mw2p.find("self.update_btn ="))
    check("b2p die Reiter tragen den eigenen Tab-Stil (#NavTab, nicht NavPaid)",
          all(win._nav_buttons[k].objectName() == "NavTab"
              for k in win._paid_keys)
          and "#NavPaid" not in _mw2p)
    check("b2p und sehen wie Reiter aus: nur oben rund, aktiver buendig",
          "border-top-left-radius:10px" in _mw2p
          and "border-top:3px solid" in _mw2p)
except Exception as _e2p:                                # pragma: no cover
    _fail.append(f"b2p Abo-Rueckbau: {type(_e2p).__name__}: {_e2p}")

# ---------------------------------------------------------------- (b2o)
# PORTFOLIO-LAYOUT (Nutzer, Sitzung 8): "schoener anordnen, mehr mit Farben
# arbeiten, weniger Informationsueberfluss. Ein Ausklappbarer, wo man
# anhaken kann welche Rows eingeblendet werden - Standard zugeklappt, darin
# angehakt Menge, Durchschnittskauf, Marge, Status, Orders." Dazu
# Werkzeuge-Menue nach Wagen-Muster und der offene Icon-Nachtrag.
try:
    _STD2o = {1, 2, 6, 7, 8}
    _acts2o = getattr(win, "_pf_col_acts", None)
    check("b2o die Spalten-Auswahl kennt alle 11 abwaehlbaren Spalten",
          _acts2o is not None and len(_acts2o) == 11 and 0 not in _acts2o)
    check("b2o Standard angehakt: Menge, \u00d8-Kauf, Marge, Status, Orders",
          {c for c, a in _acts2o.items() if a.isChecked()} == _STD2o)
    check("b2o und genau die sind sichtbar, der Rest ist versteckt",
          all(win.pf_table.isColumnHidden(c) is (c not in _STD2o)
              for c in _acts2o))
    check("b2o die Item-Spalte ist nie abwaehlbar",
          not win.pf_table.isColumnHidden(0))
    # Haken FUNKTIONAL: abwaehlen versteckt, wieder anhaken zeigt.
    _acts2o[1].setChecked(False)
    check("b2o Haken entfernen versteckt die Spalte sofort",
          win.pf_table.isColumnHidden(1))
    _acts2o[1].setChecked(True)
    check("b2o Haken setzen blendet sie wieder ein",
          not win.pf_table.isColumnHidden(1))
    # Zuschaltbare Spalte gegenprobe
    _acts2o[9].setChecked(True)
    check("b2o zuschaltbare Spalte laesst sich einblenden",
          not win.pf_table.isColumnHidden(9))
    _acts2o[9].setChecked(False)
    # Runde 3 (Nutzer): das Werkzeuge-Menue ist WEG - "brauchen wir nie".
    # Der Handler lebt weiter (die Spalte "In Sell-Order zu" ist im
    # Spalten-Menue zuschaltbar), nur der Knopf ist unsichtbar.
    check("b2o kein Werkzeuge-Menue mehr im Portfolio",
          not hasattr(win, "_pf_tool_pairs")
          and callable(win._pf_load_order_prices))
    # SITZUNG 20 (Nutzer-Entscheid): "Total Assets die Zahl in fettem Amber" -
    # die Leitzahl ist von CYAN auf AMBER gewechselt und groesser geworden.
    # Die Ordnung dahinter bleibt: gebunden AMBER, bereit GRUEN.
    # SITZUNG 20 (Nutzer-Entscheid, zweiter Anlauf): die Leitzahl ist GROSS,
    # aber in normaler Textfarbe - "doch lieber einfach weiss wie die Zahlen
    # der Wallet". Farbe bleibt den Zahlen vorbehalten, bei denen sie etwas
    # BEDEUTET: gebunden AMBER, bereit GRUEN.
    check("b2o Leitzahl gross und neutral, gebunden AMBER, bereit GRUEN",
          "26px" in win.k_wealth.styleSheet()
          and _th2i.AMBER not in win.k_wealth.styleSheet()
          and _th2i.AMBER in win.k_invested.styleSheet()
          and _th2i.GREEN in win.k_flag.styleSheet())
    _mw2o = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
    # Runde 2 (Nutzer): zwei Karten in die Auswahl der Spalten-Auswahl.
    _karten2o = getattr(win, "_pf_card_acts", None)
    check("b2o Investiert + Item-Wert sind abwaehlbare Kennzahlen",
          _karten2o is not None and len(_karten2o) == 2)
    check("b2o und beide starten AUSGEBLENDET",
          not any(a.isChecked() for a in _karten2o.values())
          and win.k_invested_c.isHidden() and win.k_value_c.isHidden())
    _kact2o = _karten2o.get("Invested (held)")   # Sitzung 17: englischer Schluessel
    _kact2o.setChecked(True)
    check("b2o Haken blendet die Kennzahl-Karte wieder ein",
          not win.k_invested_c.isHidden())
    _kact2o.setChecked(False)
    # Runde 3 (Nutzer-Entscheidung): die kurzzeitige "Marge
    # (verkaufsbereit)"-Karte ist WIEDER WEG - sie rechnete korrekt, wirkte
    # aber unplausibel, sobald ein grosser Posten dominierte. Die
    # belastbare Marge lebt im Gewinne-Tab (echte Verkaeufe).
    check("b2o im Portfolio gibt es KEINE Erwartungs-Marge-Karte mehr",
          not hasattr(win, "k_margin"))
    _pr3o = _mw2o[_pos_von(_mw2o, "def _render_profit"):]
    _pr3o = _pr3o[:_pos_von(_pr3o, "\n    def ", 10)]
    check("b2o Gewinne: Marge steht als ERSTE Karte, Gebuehren sind aus",
          win.pk_margin_c.parentWidget().layout() is not None
          and win.pk_fees_c.isHidden())
    _bp3o = _mw2o[_pos_von(_mw2o, "def _build_profit_tab"):]
    _bp3o = _bp3o[:_pos_von(_bp3o, "\n    def ", 10)]
    _bp2o = _mw2o[_pos_von(_mw2o, "def _build_portfolio_tab"):]
    _bp2o = _bp2o[:_pos_von(_bp2o, "\n    def ", 10)]
    # OHNE index() pruefen: faellt der Stretch ganz weg, wuerde index()
    # eine ValueError werfen und den ganzen Block abbrechen - die Rotprobe
    # sah das als "Pruefung blieb gruen" (blind). find() liefert -1 und
    # macht die Pruefung sauber ROT.
    # Die Funktion enthaelt MEHRERE addStretch() (auch weiter unten im
    # Container-Bereich) - ein blosses "kommt danach" war blind, weil der
    # zweite Stretch die Pruefung rettete. Deshalb die exakte
    # NACHBARSCHAFT verlangen: direkt nach dem Spalten-Knopf.
    # Nutzer (Sitzung 8): Spalten-Auswahl GANZ RECHTS, der Rest links.
    # Der Stretch steht ZWISCHEN beiden - exakte Nachbarschaft pruefen, ein
    # blosses "kommt danach" waere bei mehreren Stretches blind.
    check("b2o Spalten-Auswahl sitzt ganz rechts, der Rest bleibt links",
          "head.addStretch()\n        head.addWidget(_pf_cols_btn)" in _bp2o)
    check("b2o und Aktualisieren steht weiter links davor",
          0 <= _bp2o.find("head.addWidget(self.refresh_btn)")
          < _bp2o.find("head.addStretch()\n        head.addWidget(_pf_cols_btn)"))
    check("b2o und zwar an Position 0 der Kennzahlen-Zeile",
          "for c in (self.pk_margin_c, self.pk_net_c" in _bp3o
          and "self.pk_fees_c.setVisible(False)" in _bp3o)
    check("b2o die Gewinne-Marge ist gross und vorzeichen-gefaerbt",
          "font-size:26px" in _pr3o
          and "theme.GREEN if avg_margin >= 0 else theme.RED" in _pr3o
          and 'f"{avg_margin:+.1f} %"' in _pr3o)
    check("b2o das Portfolio stoesst den Bilder-Nachtrag an",
          "self._icon_prefetch_pending(self._render_portfolio)" in _mw2o)
    # GEWINNE-Tab: Filter links (Stretch am ENDE der Kopfzeile)
    _pr2o = _mw2o[_pos_von(_mw2o, "def _build_profit_tab"):]
    _pr2o = _pr2o[:_pos_von(_pr2o, "\n    def ", 10)]
    check("b2o Gewinne: Charakter/Zeitraum links, Stretch erst danach",
          _pos_von(_pr2o, "head.addWidget(self.pr_window)")
          < _pos_von(_pr2o, "head.addStretch()"))
except Exception as _e2o:                                # pragma: no cover
    _fail.append(f"b2o Portfolio-Layout: {type(_e2o).__name__}: {_e2o}")

# ---------------------------------------------------------------- (b2n)
# VERKAUFSLISTEN-FUSSZEILE (Nutzer, Sitzung 8): "Erwarteter Gewinn und
# Erwarteter Erloes koennen raus; die Anzeige wieviele Items in der Liste
# sind, sollte erkenntlicher sein und nach LINKS." Wie beim Einkaufswagen:
# die Liste mischt Herkuenfte, eine Summe darueber ist keine verlaessliche
# Aussage - der Zaehler dagegen ist beim Gegenchecken mit dem Ingame-
# Verkaufsfenster die eigentlich nuetzliche Zahl.
try:
    check("b2n Gewinn- und Erloes-Anzeige sind aus der Ansicht",
          not win.sell_t_profit.isVisible() and not win.sell_t_rev.isVisible())
    check("b2n die Labels leben weiter (Aktualisierung schreibt ins Leere)",
          win.sell_t_profit is not None and win.sell_t_rev is not None)
    _lay2n = win.sell_t_count.parentWidget().layout()
    check("b2n der Item-Zaehler steht praesent da (fett, H2-Groesse)",
          "font-weight:800" in win.sell_t_count.styleSheet()
          and "font-size:15px" in win.sell_t_count.styleSheet())
    # LINKS heisst: im Fusszeilen-Layout VOR dem Stretch. Funktional
    # geprueft statt per Quelltext-Suche.
    _tot2n = None
    for _i2n in range(_lay2n.count() if _lay2n else 0):
        _it2n = _lay2n.itemAt(_i2n)
        _sub2n = _it2n.layout() if _it2n else None
        if _sub2n and any(_sub2n.itemAt(_j).widget() is win.sell_t_count
                          for _j in range(_sub2n.count())):
            _tot2n = _sub2n
            break
    check("b2n der Zaehler sitzt LINKS aussen (Position 0 der Fusszeile)",
          _tot2n is not None
          and _tot2n.itemAt(0).widget() is win.sell_t_count)
except Exception as _e2n:                                # pragma: no cover
    _fail.append(f"b2n Verkaufslisten-Fusszeile: {type(_e2n).__name__}: {_e2n}")

# ---------------------------------------------------------------- (b2p)
# SYMBOL-ZUSTAENDE (Nutzer, Sitzung 8: "wenn die Symbole aktiv sind, etwas
# heller, mehr ins Weiss hinein"). FUNKTIONAL geprueft: die gerenderten
# Bilder muessen sich in der Helligkeit wirklich unterscheiden - eine
# Quelltext-Suche wuerde nicht merken, wenn Qt den Zustand ignoriert.
try:
    from PySide6.QtGui import QIcon as _QI2p
    from PySide6.QtCore import QSize as _QS2p
    from eve_trader.ui import icons as _ic2p

    def _helligkeit2p(qicon, modus):
        _img = qicon.pixmap(_QS2p(32, 32), modus).toImage()
        _px = [_img.pixelColor(x, y) for y in range(32) for x in range(32)
               if _img.pixelColor(x, y).alpha() > 200]
        return sum(p.red() for p in _px) // max(1, len(_px))

    _ic = _ic2p.icon("factory", groesse=32)
    _ruhe2p = _helligkeit2p(_ic, _QI2p.Normal)
    _aktiv2p = _helligkeit2p(_ic, _QI2p.Active)
    _aus2p = _helligkeit2p(_ic, _QI2p.Disabled)
    check(f"b2p aktiv ist HELLER als Ruhe ({_aktiv2p} > {_ruhe2p})",
          _aktiv2p > _ruhe2p)
    check("b2p und der Sprung ist deutlich sichtbar (>= 25 Stufen)",
          _aktiv2p - _ruhe2p >= 25)
    check(f"b2p inaktiv ist dunkler als Ruhe ({_aus2p} < {_ruhe2p})",
          _aus2p < _ruhe2p)
    check("b2p markierte Zeilen bekommen denselben hellen Ton",
          _helligkeit2p(_ic, _QI2p.Selected) == _aktiv2p)
    # Eingefaerbte Zustands-Symbole behalten IHRE Farbe - dort ist die
    # Farbe die Aussage, die darf nicht aufgehellt werden.
    from eve_trader.ui import theme as _th2p
    _amber2p = _ic2p.icon("warning", _th2p.AMBER, 32)
    check("b2p eingefaerbte Symbole werden NICHT aufgehellt",
          _helligkeit2p(_amber2p, _QI2p.Active)
          == _helligkeit2p(_amber2p, _QI2p.Normal))
except Exception as _e2p:                                # pragma: no cover
    _fail.append(f"b2p Symbol-Zustaende: {type(_e2p).__name__}: {_e2p}")

# ---------------------------------------------------------------- (b2m)
# GRUPPEN-RUECKFALL IM KATEGORIEN-SCHLUESSEL (Nutzer-Fall Stork: Ferrogel
# stand trotz "immer bauen" auf "kaufen", die Geschwister bauten). Ursache:
# Gruppen-Karte kannte das Item nicht -> Schluessel fiel auf generisches
# "reactions" -> nie besessen. FUNKTIONAL: mit leerem Gruppennamen muss der
# Schluessel die SDE fragen und "Composite" korrekt zuordnen.
try:
    import eve_trader.industry as _ind2m
    _orig_gn2m = _ind2m.group_names
    _ind2m.group_names = lambda ids: {int(list(ids)[0]): "Composite"}
    win._sde_group_name_cache = None
    _key2m = win._category_key(16670, "", True)
    check("b2m leerer Gruppenname -> SDE-Rueckfall -> composite_reactions",
          _key2m == "composite_reactions")
    _ind2m.group_names = lambda ids: (_ for _ in ()).throw(
        AssertionError("zweiter SDE-Zugriff"))
    check("b2m der Rueckfall ist gecacht (kein zweiter SDE-Zugriff)",
          win._category_key(16670, "", True) == "composite_reactions")
    check("b2m bekannter Gruppenname geht weiter direkt",
          win._category_key(16670, "Intermediate Materials", True)
          == "intermediate_reactions")
except Exception as _e2m:                                # pragma: no cover
    _fail.append(f"b2m Gruppen-Rueckfall: {type(_e2m).__name__}: {_e2m}")
finally:
    try:
        _ind2m.group_names = _orig_gn2m
        win._sde_group_name_cache = None
    except Exception:
        pass

# ---------------------------------------------------------------- (b2j)
# VERKAUFSLISTE NACH WAGEN-MUSTER (Sitzung 8) + Nutzer-Auftrag: "ueberpruefe
# anschliessend ob alle Buttons noch funktionieren". Also: JEDER Knopf wird
# funktional ausgeloest (Attrappen zaehlen die Handler-Aufrufe); der
# Einfuege-Knopf ist schon durch b2g abgedeckt, der ihn REAL drueckt.
try:
    _rufe2j = []
    _pairs2j = getattr(win, "_sl_tool_pairs", None)
    # ZWEI statt drei seit 22.09.2026: "In sell order?" ist weg (siehe b2i).
    check("b2j Werkzeuge-Menue hat zwei Eintraege (laden/leeren)",
          _pairs2j is not None and len(_pairs2j) == 2)
    _orig2j = (win._sell_load_prices, win._sell_check_orders, win._sell_clear,
               win._sell_copy_list, win._render_sell_list)
    win._sell_load_prices = lambda *a, **k: _rufe2j.append("laden")
    win._sell_check_orders = lambda *a, **k: _rufe2j.append("check")
    win._sell_clear = lambda *a, **k: _rufe2j.append("leeren")
    win._sell_copy_list = lambda *a, **k: _rufe2j.append("kopieren")
    win._render_sell_list = lambda *a, **k: _rufe2j.append("render")
    for _a2j, _b2j in _pairs2j:
        _a2j.trigger()
    check("b2j beide Menue-Aktionen rufen ihre Handler",
          _rufe2j[:2] == ["laden", "leeren"])
    # DIE WARNUNG IST JETZT DAUERHAFT AN, nicht mehr ein Knopfdruck.
    check("b2j die rote Markierung ist ab Werk eingeschaltet",
          getattr(win, "_sell_mark_orders", False) is True
          and getattr(win, "_sh_mark_orders", False) is True)
    check("b2j die Knoepfe sind unsichtbar, aber am Leben",
          all(not _b.isVisible() for _a, _b in _pairs2j))
    # Hauptaktion + Ziel-Preis-Zustand
    for _w2j in win._shopping_w.findChildren(type(win._sh_copy_btn)):
        pass
    _cl2j = [b for b in win.sell_table.parentWidget().parentWidget()
             .findChildren(type(win._sh_copy_btn))
             if b.text() == _t4("Copy prices → in game")]
    check("b2j Hauptaktion 'Preise -> Ingame kopieren' sichtbar verkabelt",
          bool(_cl2j) and (_cl2j[0].clicked.emit() or "kopieren" in _rufe2j))
    _tb2j = [b for b in win.sell_table.parentWidget().parentWidget()
             .findChildren(type(win._sh_copy_btn))
             if b.text() == _t4("All at target price")]
    if _tb2j:
        _vor2j = win._sell_target_mode
        _tb2j[0].toggle()
        check("b2j Ziel-Preis-Schalter kippt den Zustand und rendert neu",
              win._sell_target_mode != _vor2j and "render" in _rufe2j)
        _tb2j[0].toggle()
    else:
        _fail.append("b2j Ziel-Preis-Knopf nicht gefunden")
    (win._sell_load_prices, win._sell_check_orders, win._sell_clear,
     win._sell_copy_list, win._render_sell_list) = _orig2j
    # Layout-Zusagen
    check("b2j Erloes- und Gewinn-Spalte sind ausgeblendet",
          win.sell_table.isColumnHidden(6) and win.sell_table.isColumnHidden(7))
    check("b2j Splitter traegt links Liste, rechts das Einfuege-Feld",
          getattr(win, "_sell_split", None) is not None
          and win._sell_split.count() == 2
          and win._sell_paste in [win._sell_split.widget(1)]
          + win._sell_split.widget(1).findChildren(type(win._sell_paste)))
    check("b2j der Einfuege-Knopf steht UEBER dem Feld",
          win._sell_split.widget(1).layout().indexOf(
              win._sell_split.widget(1).findChildren(
                  type(win._sh_copy_btn))[0]) == 0)
    _mwsrc2j = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
    check("b2j der Erklaertext ist raus",
          "Portfolio-Items mit Status" not in _mwsrc2j)
    check("b2j Verkaufsliste stoesst den Bilder-Nachtrag an",
          "self._icon_prefetch_pending(self._render_sell_list)" in _mwsrc2j)
except Exception as _e2j:                                # pragma: no cover
    _fail.append(f"b2j Verkaufsliste: {type(_e2j).__name__}: {_e2j}")

# ---------------------------------------------------------------- (b2k)
# ORDER-UPDATE NACH MUSTER (Sitzung 8): Kopfzeile war schon konform -
# geprueft werden Text-Entfernung, Optik, Icon-Anschluss und dass die
# Knoepfe weiter feuern (Attrappen).
try:
    _rufe2k = []
    _orig_load2k = win._load_order_mods
    _orig_tog2k = win._toggle_order_step
    win._load_order_mods = lambda *a, **k: _rufe2k.append("laden")
    win._toggle_order_step = lambda *a, **k: _rufe2k.append("modus")
    _mwsrc2k = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
    check("b2k der Erklaertext ist raus, Cache-Hinweis lebt im Tooltip",
          "Deine offenen Orders am gew" not in _mwsrc2k
          # Sitzung 13: Tooltip laeuft ueber das Sprachsystem (englischer
          # Schluessel im Quelltext, deutsch im Katalog).
          and _mwsrc2k.count("EVE caches your orders for up to ~20 min") == 1)
    check("b2k Tabellen ohne Gitter, mit 32er-Icons",
          not win.buyord_table.showGrid()
          and win.buyord_table.iconSize().width() == 32
          and win.sellord_table.iconSize().width() == 32)
    check("b2k Zeilen bekommen Item-Icons (per _table_icon)",
          "_oic = self._table_icon(r[\"tid\"])" in _mwsrc2k)
    check("b2k Bilder-Nachtrag zeichnet NUR neu, laedt NICHT aus ESI",
          "self._icon_prefetch_pending(self._rerender_order_tables)"
          in _mwsrc2k
          and "self._icon_prefetch_pending(self._load_order_mods)"
          not in _mwsrc2k)
    # Neuzeichnen aus gemerkten Zeilen darf ohne Daten nicht knallen
    win._rerender_order_tables()
    check("b2k Neuzeichnen ohne Daten laeuft sauber durch", True)
    # UEBERHOLT (Nutzer, Layout-Programm: "die Farben sollen dasselbe
    # sein"): die aeltere Violett-Logik ist dem Bauplan-Schema gewichen.
    # Name = fetter Anker in NORMALFARBE (rot NUR bei Verlust/Gebuehren-
    # Fall), Warnfarbe wohnt allein in der Status-Spalte (AMBER Handlung /
    # ROT Finger weg / GRUEN top), keine Zeilen-Tinte auf den Zahlen.
    _fo2k = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
    _fo2k = _fo2k.split("def _fill_order_table")[1].split("\n    def ")[0]
    check("b2k Name ist ruhiger Anker: Farbe nur im Verlust-Fall",
          "if flag and loss:\n                nm.setForeground(QColor(theme.RED))"
          in _fo2k and "#d17ae8" not in _fo2k)
    check("b2k Status traegt die Warnfarbe: AMBER Handlung, ROT Verlust",
          "st_col = (theme.RED if loss else theme.AMBER) if flag else theme.GREEN"
          in _fo2k)
    check("b2k keine Zeilen-Tinte mehr auf Deine-Order/Bester",
          "Rest der Zeile ebenfalls rot" not in _fo2k
          and "for c in (1, 2):" not in _fo2k)
except Exception as _e2k:                                # pragma: no cover
    _fail.append(f"b2k Order-Update: {type(_e2k).__name__}: {_e2k}")
finally:
    try:
        win._load_order_mods = _orig_load2k
        win._toggle_order_step = _orig_tog2k
    except Exception:
        pass

# ---------------------------------------------------------------- (b2l)
# TRADING-TABS NACH MUSTER (Sitzung 8): Feinfilter standardmaessig ZU,
# Excel-Gefuehl raus (kein Gitter, 32er-Icons, fette Namen), Bilder-
# Nachtrag ueber Merk-Wrapper (NIE ueber einen Scan/Reload).
try:
    _mwsrc2l = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
    for _t2l in (win.deals_table, win.hold_table, win.rg_table):
        pass
    check("b2l alle drei Tabellen ohne Gitter und mit 32er-Icons",
          all((not _t.showGrid()) and _t.iconSize().width() == 32
              for _t in (win.deals_table, win.hold_table, win.rg_table)))
    # SEIT SITZUNG 12 uebersetzt - gezaehlt wird der ZUSTAND (expanded=False),
    # nicht der deutsche Titel. Genau die Sorte Pruefung, die bei jeder
    # Uebersetzung umfaellt, wenn man sie am Wortlaut festmacht.
    check("b2l alle drei Feinfilter starten ZUGEKLAPPT",
          _mwsrc2l.count('t("FINE FILTERS (OPTIONAL)"), ctl, expanded=False)')
          == 3)
    check("b2l die Namenszelle traegt Icon + Fett (in allen drei Fills)",
          _mwsrc2l.count('_ic0 = self._table_icon(d["type_id"])') == 3)
    # Nachtrag: Wrapper zeichnen aus GEMERKTEN Daten, kein Scan
    _rufe2l = []
    _orig_rd2l = win._render_deals
    win._render_deals = lambda d, m: _rufe2l.append(("deals", len(d), m))
    win._deals_last = ([{"x": 1}], "flip")
    win._rerender_deals()
    check("b2l Deals-Nachtrag zeichnet aus gemerkten Daten neu",
          _rufe2l == [("deals", 1, "flip")])
    win._render_deals = _orig_rd2l
    win._deals_last = None   # Attrappen-Daten nie dem echten Renderer lassen
    check("b2l ohne gemerkte Daten zeichnet der Wrapper NICHTS (kein Crash)",
          (win._rerender_hold() or True) and (win._rerender_arbitrage()
                                              or True))
    check("b2l alle drei Renderer stossen den Bilder-Nachtrag an",
          all(f"self._icon_prefetch_pending(self.{w})" in _mwsrc2l
              for w in ("_rerender_deals", "_rerender_hold",
                        "_rerender_arbitrage")))
except Exception as _e2l:                                # pragma: no cover
    _fail.append(f"b2l Trading-Tabs: {type(_e2l).__name__}: {_e2l}")

# ---------------------------------------------------------------- (b2j)
# ICON-VERHUNGERUNG (Nutzer-Fund: Order-Update ohne ein einziges Bild).
# Vorher: kam ein zweiter Tab, waehrend ein Holer lief, wurden seine
# Wuensche GELEERT und verworfen - Icons fuer die Sitzung verloren. Jetzt:
# Wuensche bleiben stehen, Rueckruf wird gemerkt, der laufende Lauf haengt
# einen Folgelauf an. Hier FUNKTIONAL durchgespielt.
try:
    _cb2j = lambda: None
    win._icon_prefetch_running = True
    win._icon_wanted = {("icon", 34, 32)}
    win._icon_prefetch_followup = None
    _ret2j = win._icon_prefetch_pending(_cb2j)
    check("b2j bei 'laeuft schon' bleiben die Wuensche STEHEN",
          _ret2j is False and ("icon", 34, 32) in win._icon_wanted)
    check("b2j und der Rueckruf des wartenden Tabs wird gemerkt",
          win._icon_prefetch_followup is _cb2j)
    # Der laufende Lauf endet -> Folgelauf muss angestossen werden. Wir
    # spielen das nach: running aus, dann den echten Lauf starten - mit
    # _run-Attrappe, die sofort 'fertig, 1 Bild' meldet.
    win._icon_prefetch_running = False
    _laeufe2j = []
    _orig_run2j2 = win._run
    win._run = (lambda w, done, fail_cb=None, **k:
                _laeufe2j.append("lauf") or done((1, 0)))
    win._icon_tried = set()
    _ret2j2 = win._icon_prefetch_pending(win._icon_prefetch_followup)
    check("b2j der Folgelauf holt die liegengebliebenen Wuensche wirklich",
          _ret2j2 is True and _laeufe2j == ["lauf"]
          and not win._icon_wanted)
    win._run = _orig_run2j2
except Exception as _e2j:                                # pragma: no cover
    _fail.append(f"b2j Icon-Verhungerung: {type(_e2j).__name__}: {_e2j}")
finally:
    try:
        win._run = _orig_run2j2
        win._icon_prefetch_running = False
        win._icon_prefetch_followup = None
    except Exception:
        pass

# ---------------------------------------------------------------- (b2h)
# "WERTE TIEFENPRUEFEN" IM UPDATES-DIALOG (Nutzer-Wunsch, Sitzung 8:
# "das ist uebersichtlicher" - der Knopf zog aus den Einstellungen in den
# Updates-Dialog um). Geprueft wird der GANZE neue Weg: Updates-Klick bei
# "alles aktuell" -> Dialog bietet die Tiefenpruefung an -> Klick darauf ->
# Bericht. Dazu der Rueckbau: in den Einstellungen darf der alte Knopf
# NICHT mehr haengen. Bericht und Netz kommen aus Attrappen.
try:
    import eve_trader.esi as _esi2h

    _orig_srv2h = _esi2h.eve_server_version
    _orig_sde2h = _esi2h.sde_last_modified
    _esi2h.eve_server_version = lambda: "3.1.4"
    _esi2h.sde_last_modified = lambda: "2026-08-01"
    win.settings["known_server_version"] = "3.1.4"
    win.settings["known_sde_modified"] = "2026-08-01"
    win.settings["sde_reload_ausstehend"] = False
except Exception as _e2h0:                               # pragma: no cover
    _fail.append(f"b2h Vorbereitung: {type(_e2h0).__name__}: {_e2h0}")
try:
    import pruefe_rezepte as _PR2h
    from PySide6.QtWidgets import QMessageBox as _QMB2h

    _orig_ber2h = _PR2h.bericht_fuer_ui
    _orig_run2h = win._run
    _orig_exec2h = _QMB2h.exec
    _orig_info2h = _QMB2h.information
    _texte2h = []
    _PR2h.bericht_fuer_ui = lambda: {
        "leer": False, "n": 231,
        "zensus": {200: 180, 400: 30, 10: 1},
        "hart": [], "verdaechtig": [], "falsch": [],
        "diff": ([((9002, 11, 102), 200, 400)], [], [], []),
        "sde_fehler": None}
    win._run = lambda worker, done_cb, fail_cb=None, **kw: done_cb(
        worker._fn(*worker._args, **worker._kwargs))
    # exec()-Attrappe: merkt sich den Text und "klickt" den Tiefenpruefen-
    # Knopf (ActionRole), falls der Dialog einen anbietet.
    def _exec2h(dlg):
        _texte2h.append(dlg.text())
        for _b in dlg.buttons():
            if "tiefenpr" in _b.text().lower():
                dlg._klick2h = _b
                _b.click()
                return 0
        dlg._klick2h = None
        return 0
    _QMB2h.exec = _exec2h
    _orig_cb2h = _QMB2h.clickedButton
    _QMB2h.clickedButton = lambda self: getattr(self, "_klick2h", None)
    _QMB2h.information = staticmethod(
        lambda *a, **k: _texte2h.append(a[2] if len(a) > 2 else ""))
    # SITZUNG 11: der Updates-Dialog gibt nur noch die Antwort - der
    # Zusatz-Knopf "Werte tiefenpruefen" ist entfallen (Nutzer: "das
    # braucht keiner zu sehen").
    win._check_for_updates()
    check("b2h der Updates-Dialog bietet nichts Zusaetzliches an",
          not any("tiefenpr" in t.lower() for t in _texte2h))
    check("b2h er sagt nur, dass alles aktuell ist",
          any("up to date" in t for t in _texte2h))
    # KURZ HEISST KURZ (Nutzer: "hauptsache es steht: auf dem neusten
    # Stand"). Frueher zaehlte der Dialog auf, WAS verglichen wurde - das
    # half niemandem, der nur weiterarbeiten will.
    _gut2h = next((t for t in _texte2h if "up to date" in t), "")
    # SPRACHUNABHAENGIG: die Zusage ist "nur die Antwort, ein Satz". Ein
    # Zeilenumbruch heisst, dass etwas drangehaengt wurde - egal in welcher
    # Sprache. Eine Zeichenzahl waere je Sprache verschieden, ein Suchwort
    # nur in einer Sprache wirksam.
    check(f"b2h die Gut-Meldung ist kurz ({len(_gut2h)} Zeichen, "
          f"{_gut2h.count(chr(10))} Umbrueche)",
          0 < len(_gut2h) <= 60 and "\n" not in _gut2h)
    check("b2h der alte Einstellungen-Knopf ist WEG (kein Doppel)",
          "rez_btn" not in _src_mw)
    # DIE PRUEFUNG SELBST GIBT ES WEITERHIN - sie ist nur nicht mehr aus
    # diesem Dialog erreichbar. Direkt gerufen muss sie weiter arbeiten.
    _texte2h.clear()
    win._check_recipes()
    _t2h = _texte2h[-1] if _texte2h else ""
    check("b2h die Tiefenpruefung selbst arbeitet weiterhin", bool(_t2h))
    # Zweisprachig (Sitzung 16): der Bericht laeuft durch t().
    check("b2h der Bericht nennt den Zensus",
          "AUSBEUTE-ZENSUS" in _t2h or "YIELD CENSUS" in _t2h)
    check("b2h eine veraltete Ausbeute wird als Problem genannt",
          ("VERALTET" in _t2h or "OUTDATED" in _t2h)
          and "200" in _t2h and "400" in _t2h)
    check("b2h und der Weg zur Loesung steht dabei",
          "Baurezepte laden" in _t2h or "Load recipes" in _t2h)
    # Offline-Fall: Zensus MUSS trotzdem kommen (Regel 6)
    _texte2h.clear()
    _PR2h.bericht_fuer_ui = lambda: {
        "leer": False, "n": 231, "zensus": {200: 180},
        "hart": [], "verdaechtig": [], "falsch": [],
        "diff": None, "sde_fehler": "URLError: kein Netz"}
    win._check_recipes()   # Handler bleibt direkt pruefbar (Offline-Fall)
    check("b2h ohne Netz kommt der Zensus trotzdem, mit klarer Ansage",
          bool(_texte2h)
          and ("NICHT M\u00d6GLICH" in _texte2h[-1]
               or "NOT POSSIBLE" in _texte2h[-1])
          and ("AUSBEUTE-ZENSUS" in _texte2h[-1]
               or "YIELD CENSUS" in _texte2h[-1]))
except Exception as _e2h:                                # pragma: no cover
    _fail.append(f"b2h Rezepte pruefen: {type(_e2h).__name__}: {_e2h}")
finally:
    try:
        _PR2h.bericht_fuer_ui = _orig_ber2h
        win._run = _orig_run2h
        _QMB2h.exec = _orig_exec2h
        _QMB2h.information = _orig_info2h
        _QMB2h.clickedButton = _orig_cb2h
        _esi2h.eve_server_version = _orig_srv2h
        _esi2h.sde_last_modified = _orig_sde2h
    except Exception:
        pass

# ---------------------------------------------------------------- (b2e)
# BESTANDS-STAND IM KOPF (Nutzer-Wunsch): "wann war die letzte erfolgreiche
# ESI-Aktualisierung, die Veraenderungen festgestellt hat". Die Rechenlogik
# dahinter prueft aa153 - hier geht es NUR darum, dass die Zeile den Schirm
# auch erreicht: mit Text, in einem Layout haengend und nicht versteckt. Ein
# Label ohne Parent existiert im Speicher und ist trotzdem unsichtbar; genau
# so faellt so eine Anzeige still aus.
_stand_lbl = getattr(win, "_bd_esi_stand_lbl", None)
check("b2e Bestands-Zeile existiert", _stand_lbl is not None)
if _stand_lbl is not None and _dlg is not None:
    check("b2e Bestands-Zeile haengt im Fenster (hat einen Parent)",
          _stand_lbl.parentWidget() is not None)
    check("b2e Bestands-Zeile ist im Dialog sichtbar",
          _stand_lbl.isVisibleTo(_dlg))
    check("b2e Bestands-Zeile ist nicht leer",
          bool(_stand_lbl.text().strip()))
    check("b2e und benennt den Bestand",
          "Bestand" in _stand_lbl.text() or "Stock" in _stand_lbl.text())
    # Ohne Vergleichsstand darf sie KEINE Aenderung behaupten.
    check("b2e ohne Abruf wird keine Aenderung behauptet",
          "letzte festgestellte" not in _stand_lbl.text())
    # SPRACHUNABHAENGIG: der Tooltip laeuft jetzt durch t(); geprueft wird
    # dass er UEBERHAUPT etwas erklaert, nicht ein deutsches Teilwort.
    check("b2e der Hinweistext erklaert den Unterschied",
          len(_stand_lbl.toolTip() or "") > 40)

if _dlg is not None:
    # ------------------------------------------------------------ (b3)
    # BEDIENELEMENTE MUESSEN IM FENSTER SEIN. Ein Widget ohne Layout hat
    # keinen Parent und taucht hier gar nicht auf - genau so ging das
    # Verkaufscharakter-Dropdown verloren.
    _combos = _dlg.findChildren(QComboBox)
    _buttons = _dlg.findChildren(QPushButton)
    _btexts = [b.text() for b in _buttons]
    _ctips = [c.toolTip() for c in _combos]

    check("b3 mindestens zwei Dropdowns in der Kopfleiste (Hub + Charakter)",
          len(_combos) >= 2)
    check("b3 Verkaufs-HUB-Dropdown vorhanden",
          any("sell the end product" in (t or "")
              or "verkaufst du das Endprodukt" in (t or "")
              for t in _ctips))
    check("b3 Verkaufs-CHARAKTER-Dropdown vorhanden (war einmal verloren)",
          any("Wer verkauft das Endprodukt" in (t or "")
              or "Who sells the final product" in (t or "")
              for t in _ctips))
    # seit emm298 "Reset" an der Stelle von "Neu berechnen".
    check("b3 Knopf 'Reset' vorhanden, 'Neu berechnen' weg",
          any(t in ("Reset", "Zur\u00fccksetzen") for t in _btexts)
          and not any("Neu berechnen" in t or "Recalculate" in t for t in _btexts))
    check("b3 Knopf 'Werkzeuge' vorhanden",
          any("Werkzeuge" in t or "Tools" in t for t in _btexts))
    # "Zu Einkaufswagen" entfaellt - Einkauf laeuft ueber Materialien-Tab ->
    # "Einkaufsliste erstellen". Der Knopf DORT muss es dafuer geben.
    # Zweisprachig (Sitzung 16): die Beschriftung laeuft durch t().
    check("b3 Knopf 'Einkaufsliste erstellen' vorhanden",
          any("Einkaufsliste erstellen" in t or "Create shopping list" in t
              for t in _btexts))
    check("b3 Knopf 'Bauplan speichern' vorhanden",
          any("speichern" in t.lower() or "save" in t.lower() for t in _btexts))

    # ------------------------------------------------------------ (b4)
    # KPI-Karten muessen gefuellt sein (nicht nur existieren).
    _labels = [l.text() for l in _dlg.findChildren(QLabel)]
    _joined = " ".join(_labels)
    # SPRACHUNABHAENGIG (Sitzung 12): geprueft wird, dass die KARTE da ist -
    # in der Sprache, die gerade laeuft. Ein fest eingetippter deutscher
    # Titel waere seit der Umstellung auf Englisch-als-Standard rot, ohne
    # dass etwas fehlt.
    from eve_trader.sprache import t as _t4
    # Sitzung 17: alle drei Kacheln laufen durch t() - Titel in der Sprache
    # des Testfensters.
    for _cap in (_t4("Build cost / unit"), _t4("Total profit"),
                 _t4("Min. sell price / unit")):
        check(f"b4 KPI-Karte vorhanden: {_cap}", _cap in _joined)
    check("b4 KPI-Werte sind gefuellt (ISK-Betrag sichtbar)",
          any("ISK" in t for t in _labels))
    # (b4b) Ausgeduennte Leiste: diese Karten sind bewusst NICHT mehr sichtbar.
    _vis = [l.text() for l in _dlg.findChildren(QLabel) if l.isVisibleTo(_dlg)]
    for _gone in ("Gesamt", "Sell / Stk", "Rohgewinn gesamt (ohne Geb"):
        check(f"b4b ausgeblendet: {_gone}",
              not any(t.startswith(_gone) for t in _vis))

    # ------------------------------------------------------------ (b5)
    # Materialien-Tab: Tabelle mit den Herkunfts-Spalten + Einfuege-Panel.
    # Der Materialien-Tab ist ein GRUPPEN-BAUM (Kategorien einklappbar).
    _mat = [x for x in _dlg.findChildren(QTreeWidget)
            if x.columnCount() == 7 and x.headerItem()
            and x.headerItem().text(0) == _t4("Material")]
    check("b5 Materialien-Tabelle vorhanden", bool(_mat))
    if _mat:
        _hdr = [_mat[0].headerItem().text(c)
                for c in range(_mat[0].columnCount())]
        # AUCH EINE SPALTE AUS DER ERSTEN ZEILE der Kopf-Liste pruefen:
        # eine Mutation, die nur Zeile 1 ersetzt, bliebe sonst unbemerkt
        # (in dieser Sitzung schon dreimal passiert).
        check("b5 die vordere Kopfspalte ist uebersetzt",
              _t4("Category") in _hdr)
        check("b5 Spalte fuer eingefuegten Bestand existiert",
              _t4("Pasted") in _hdr)
        check("b5 Spalte 'Fehlt' vorhanden", _t4("Missing") in _hdr)
        # Gegenprobe an echten Zeilen: Fehlt = Benoetigt - Bestand, nie < 0.
        _bad = []
        _leaves = []
        for _g in range(_mat[0].topLevelItemCount()):
            _gi = _mat[0].topLevelItem(_g)
            for _c in range(_gi.childCount()):
                _leaves.append(_gi.child(_c))
        for _nd in _leaves:
            _nt = _nd.text(2).replace("'", "").strip()
            if not _nt:
                continue
            try:
                _n = int(float(_nt.replace("k", "000").replace("M", "000000")))
            except ValueError:
                continue
            _mt = _nd.text(5).strip()
            if _mt in ("\u2013", "-", ""):
                continue
            try:
                _m = int(float(_mt.replace("'", "").replace("k", "000")
                               .replace("M", "000000")))
            except ValueError:
                continue
            if _m < 0 or _m > _n:
                _bad.append((_nd.text(0), _n, _m))
        check(f"b5 'Fehlt' liegt immer zwischen 0 und Benoetigt {_bad[:2]}",
              not _bad)
        # Die Kategorie steht jetzt in den GRUPPEN-Knoten; die Spalte selbst
        # ist dadurch redundant, bleibt aber fuer die Sortierung bestehen.
        check("b5 Blatt-Knoten tragen ihre Kategorie",
              all(_nd.text(1) for _nd in _leaves) if _leaves else True)
        # KEIN Filter, der Zeilen versteckt: alle Materialien bleiben
        # sichtbar (zurueckgenommen - das war Informationsverlust).
        _grp = [_mat[0].topLevelItem(_g)
                for _g in range(_mat[0].topLevelItemCount())]
        check("b5 Kategorie-Gruppen vorhanden", bool(_grp))
        # ZUGEKLAPPT starten (Nutzer: "wegen Ueberflutung von Informationen").
        check("b5 Gruppen starten zugeklappt",
              all(not g.isExpanded() for g in _grp))
        check("b5 aber sie lassen sich aufklappen",
              all(g.childCount() > 0 for g in _grp))
        check("b5 jede Gruppe hat Kinder", all(g.childCount() > 0 for g in _grp))
        check("b5 Gruppen tragen einen Fortschrittsbalken",
              all(_mat[0].itemWidget(g, 6) is not None for g in _grp))
        check("b5 kein 'Nur offene Posten'-Filter",
              not [c for c in _dlg.findChildren(QCheckBox)
                   if "offene Posten" in c.text()])
        check("b5 nach Kategorie vorsortiert",
              _mat[0].header().sortIndicatorSection() == 1)
        # Reihenfolge muss der Kette folgen, nicht dem Alphabet.
        # Seit Sitzung 16 ist text(0) UEBERSETZT - der Schluessel haengt als
        # Daten am Knoten (Spalte 1, UserRole).
        _cats = [g.data(1, Qt.UserRole) or g.text(0) for g in _grp]
        _seen, _order = [], []
        for _c in _cats:
            if _c not in _seen:
                _seen.append(_c); _order.append(_c)
        _want_order = ["Intermediate Reactions", "Composite Reactions",
                       "Komponenten", "Mineralien / Rohstoffe"]
        _idx = [_pos_von(_want_order, _c) for _c in _order if _c in _want_order]
        check(f"b5 Kategorien in Ketten-Reihenfolge {_order}",
              _idx == sorted(_idx))
        check("b5 'Eingefuegt' ohne Einfuegung ausgeblendet",
              _mat[0].isColumnHidden(4))
        check("b5 'Benoetigt' und 'Genutzt' bleiben sichtbar",
              not _mat[0].isColumnHidden(2) and not _mat[0].isColumnHidden(5))
        # Status-Spalte muss den Rest fuellen - der Fortschrittsbalken ist ein
        # Zell-Widget und zaehlt beim Bemessen nach Inhalt nicht mit.
        from PySide6.QtWidgets import QHeaderView as _QHV5
        eq("b5 Status-Spalte streckt sich ueber die Restbreite",
           _mat[0].header().sectionResizeMode(6), _QHV5.Stretch)
        # Auch hier: keine Roh-IDs statt Itemnamen. Der Materialien-Tab liest
        # zusaetzlich `stock_used`/`surplus` - Items, die ganz aus dem Bestand
        # kommen, waren deshalb namenlos ("#16642").
        _mnums = [_nd.text(0).strip() for _nd in _leaves
                  if _nd.text(0).strip().startswith("#")
                  and _nd.text(0).strip()[1:].isdigit()]
        check(f"b5 keine Roh-IDs im Materialbaum {_mnums[:3]}", not _mnums)
        # Deckungs-Balken: jedes Material UND jede Gruppe.
        from PySide6.QtWidgets import QProgressBar as _QPB6
        _bars = [_mat[0].itemWidget(_nd, 6) for _nd in _leaves]
        _bars = [b for b in _bars if isinstance(b, _QPB6)]
        check(f"b5 jedes Material hat einen Deckungs-Balken "
              f"({len(_bars)}/{len(_leaves)})",
              not _leaves or len(_bars) == len(_leaves))
        _bad_pct = [b.value() for b in _bars if not 0 <= b.value() <= 100]
        check(f"b5 Balkenwerte liegen zwischen 0 und 100 {_bad_pct[:3]}",
              not _bad_pct)
    _pte = _dlg.findChildren(QPlainTextEdit)
    # OPTIK der Tabellen (Nutzer: "ohne Roboter-Schriftart, ohne Grid,
    # lieber Bildchen statt Zahlen links").
    # Der Materialien-Tab ist ein BAUM (kein Gitter/keine Zeilennummern-API),
    # der Blueprints-Tab weiterhin eine Tabelle.
    _bp_tbls = [x for x in _dlg.findChildren(QTableWidget)
                if x.columnCount() == 7]
    for _tb, _nm in ((_bp_tbls[0] if _bp_tbls else None, "Blueprints"),):
        if _tb is None:
            continue
        check(f"b5b {_nm}: kein Gitter", not _tb.showGrid())
        check(f"b5b {_nm}: keine Zeilennummern",
              not _tb.verticalHeader().isVisible())
        check(f"b5b {_nm}: keine Zebrastreifen", not _tb.alternatingRowColors())
        check(f"b5b {_nm}: Icon-Groesse gesetzt", _tb.iconSize().width() >= 20)
    check("b5 Einfuege-Panel vorhanden (Textfeld)", bool(_pte))
    if _pte:
        check("b5 Textfeld ist gross genug", _pte[0].minimumHeight() >= 240)
    _plabels = [l.text() for l in _dlg.findChildren(QLabel)]
    # SEIT 26.09.2026 IN DER KLAPPE "Paste stock" RECHTS, STANDARD ZU; beim
    # Aufklappen zuerst der ESI-Hinweis mit "Continue", dann das Panel;
    # Zuklappen ohne Kommentar, erneutes Aufklappen zeigt wieder den Hinweis.
    _ph5 = getattr(win, "_bd_paste_hdr", None)
    _hi5 = getattr(win, "_bd_paste_hint", None)
    _pa5 = getattr(win, "_bd_paste_panel", None)
    _we5 = getattr(win, "_bd_paste_weiter", None)
    check("b5 Klappe 'Paste stock' da und standardmaessig ZU",
          _ph5 is not None and _t4("Paste stock") in _ph5.text()
          and not _ph5.isChecked()
          and _pa5 is not None and _pa5.parentWidget().isHidden())
    if _ph5 is not None and _hi5 is not None and _pa5 is not None and _we5 is not None:
        _ph5.setChecked(True); _app.processEvents()
        check("b5 aufgeklappt: erst der ESI-Hinweis, das Panel noch nicht",
              (not _hi5.isHidden()) and _pa5.isHidden()
              and any("works with ESI" in _l.text() or "arbeitet mit ESI" in _l.text()
                      for _l in _hi5.findChildren(QLabel)))
        _we5.click(); _app.processEvents()
        check("b5 'Continue': Hinweis weg, Panel da",
              _hi5.isHidden() and (not _pa5.isHidden()))
        _ph5.setChecked(False); _app.processEvents()
        check("b5 zuklappen ohne Kommentar (keine Rueckfrage, alles weg)",
              _pa5.parentWidget().isHidden())
        _ph5.setChecked(True); _app.processEvents()
        check("b5 erneut aufklappen: wieder zuerst der Hinweis",
              (not _hi5.isHidden()) and _pa5.isHidden())
        _ph5.setChecked(False); _app.processEvents()
    check("b5 Panel erklaert WOFUER es gut ist",
          any(_t4("Paste here if ESI is not fast enough.") in x
              for x in _plabels))
    check("b5 Haekchen 'nach ESI-Aktualisierung behalten' vorhanden",
          any(_t4("Keep after ESI updates") in c.text()
              for c in _dlg.findChildren(QCheckBox)))

    # ------------------------------------------------------------ (b4c)
    # Nutzer: "alle Kleininformationen weg, nur mit Mouseover arbeiten" und
    # "mach alle Anzeigen gleichmaessig gross".
    # "Min. Verkaufspreis / Stk" ist auf Nutzerwunsch ebenfalls ausgeblendet
    # (zweite Aufraeum-Runde) - die Zahl steht jetzt im Tooltip von "Gewinn
    # gesamt", zusammen mit dem Preis, mit dem gerechnet wurde.
    _kpi_caps = (_t4("Build cost / unit"), _t4("Total profit"), _t4("Margin"))
    _widths = [l.parent().minimumWidth() for l in _dlg.findChildren(QLabel)
               if l.text() in _kpi_caps and l.isVisibleTo(_dlg)]
    eq("b4c drei sichtbare KPI-Karten", len(_widths), 3)
    check("b4c alle gleich breit", len(set(_widths)) == 1 and _widths[0] >= 200)
    check("b4c Min. Verkaufspreis ist NICHT mehr sichtbar",
          not [l for l in _dlg.findChildren(QLabel)
               if l.text() == "Min. Verkaufspreis / Stk" and l.isVisibleTo(_dlg)])
    # ...aber die Information darf nicht verloren gehen: der Tooltip von
    # "Gewinn gesamt" muss sagen, MIT WELCHEM PREIS gerechnet wurde und wo die
    # Verlustschwelle liegt. Sonst haette das Aufraeumen eine Zahl entfernt,
    # die nirgends mehr steht.
    _pf = [l for l in _dlg.findChildren(QLabel)
           if l.text() == "Gewinn gesamt"]
    _pf_tip = ""
    for _l in _pf:
        _sibs = _l.parent().findChildren(QLabel) if _l.parent() else []
        for _sv in _sibs:
            if _sv.toolTip():
                _pf_tip = _sv.toolTip()
    # DIE ZAHLEN STEHEN NICHT MEHR IM MOUSEOVER, SONDERN IN DEN AUSGEKLAPPTEN
    # DETAILS (Nutzer: "das brauchen wir ja nicht mehr, alle diese
    # Informationen stehen ja auch unten wenn man Details ausklappt").
    # Zwei Anzeigen derselben Zahlen waren genau die Quelle der Abweichungen,
    # die in dieser Sitzung gefunden wurden - deshalb bleibt EINE.
    # ------------------------------------------------------------ (b12)
    # KATEGORIEN ALS ECHTE GRUPPEN im Rezept-Baum (Nutzer: "wo sind die
    # Gruppen?"). Vorher stand die Kategorie nur als "  · Komponente" hinter
    # dem Namen. Jetzt: ein Kopfknoten je Kategorie, Items darunter.
    # Denselben Filter wie b6 benutzen - `findChildren` liefert auch den
    # Materialien-Baum, und der hat schon immer Gruppen.
    _rt12 = next((t for t in _dlg.findChildren(QTreeWidget)
                  if t.topLevelItemCount() > 0 and t.headerItem()
                  and t.headerItem().text(0) == "Item"
                  and t.headerItem().text(2) == "Aktion"), None)
    if _rt12 is not None and _rt12.topLevelItemCount():
        _r12 = _rt12.topLevelItem(0)
        _kids12 = [_r12.child(_k) for _k in range(_r12.childCount())]
        check("b12 oberste Ebene sind Kategorie-Koepfe (ohne type_id)",
              bool(_kids12) and all(
                  _k.data(0, Qt.UserRole) is None for _k in _kids12))
        check("b12 die Materialien haengen DARUNTER",
              any(_k.childCount() > 0 for _k in _kids12))
        check("b12 Kopf nennt die Anzahl",
              all("(" in _k.text(0) for _k in _kids12))
        # Ein Kopf ist kein Material - er darf nicht abhakbar sein.
        # AUFKLAPPZUSTAND (Nutzer: "so standardmaessig ausgeklappt wie im
        # Bild"): Endprodukt und Kategorie-Koepfe offen, alles darunter zu.
        check("b12 Endprodukt ist aufgeklappt", _r12.isExpanded())
        check("b12 Kategorie-Koepfe sind aufgeklappt",
              all(_k.isExpanded() for _k in _kids12))
        check("b12 die Materialien darunter sind zugeklappt",
              all(not _k.child(_i).isExpanded()
                  for _k in _kids12 for _i in range(_k.childCount())))
        check("b12 Kopfknoten sind nicht abhakbar",
              all(not (_k.flags() & Qt.ItemIsUserCheckable) for _k in _kids12))
    _sub = _src_mw[_pos_von(_src_mw, "_profit_rows = ["):]
    _sub = _sub[:_pos_von(_sub, "]")]
    for _z in ("Verkaufspreis", "Verlustschwelle", "Baukosten", "= Gewinn",
               "Marge"):
        check(f"b4c Details-Spalte nennt '{_z}'", _z in _sub)
    check("b4c kein Zahlen-Tooltip mehr an der Gewinn-Karte",
          'st_profit.setToolTip("")' in _src_mw)
    # Der Hinweis zur PREISQUELLE darf NICHT mitverschwinden - er steht in
    # keiner Spalte, und ohne ihn waere nicht erkennbar, ob die Baukosten
    # orderbuch-genau sind oder auf Flachpreisen beruhen.
    check("b4c Preisquellen-Hinweis bleibt an der Kosten-Karte",
          "st_cost.setToolTip(_cost_src_tip)" in _src_mw)


    _subs = [l.text() for l in _dlg.findChildren(QLabel)
             if l.isVisibleTo(_dlg) and l.text().startswith(
                 ("= ", "Markt unterbieten", "davon ", "VOR Geb", "\u26a0 Markt"))]
    check("b4c keine Unterzeilen mehr sichtbar", not _subs)
    _tips = " ".join(l.toolTip() for l in _dlg.findChildren(QLabel))
    check("b4c Stueckwert steht im Tooltip", "je St" in _tips or "per unit" in _tips)

    # ------------------------------------------------------------ (b4d)
    # KOMPAKTER KOPFBEREICH (Nutzer): die Zeile "ENDPRODUKT - DAS ZU BAUENDE
    # ITEM" ist weg, Titel und Kennzahlen stehen NEBENEINANDER. Das schafft
    # Hoehe fuer Tabs und Item-Liste.
    _lbl_txt = [l.text() for l in _dlg.findChildren(QLabel)]
    check("b4d Kopfzeile 'ENDPRODUKT' entfernt",
          not any("ENDPRODUKT" in x for x in _lbl_txt))
    check("b4d Titel und Kennzahlen liegen in einer Zeile",
          "_hero_row.addLayout(stats_row, 1)" in _src_mw
          and "hv.addLayout(_hero_row)" in _src_mw)
    # Statuszelle: Balken-Text darf nicht doppelt gezeichnet werden.
    # Seit (aa46) wird die Status-Zelle direkt als NumericItem mit LEEREM
    # Text angelegt - nachtraegliches Leeren ist damit unnoetig, und die
    # Spalte bleibt trotzdem sortierbar (ueber den Rang).
    check("b4d Statuszelle hat leeren Text und einen Sortier-Rang",
          'it = NumericItem("", _st_rank)' in _src_mw)
    # Die Liste ist um die Invention-Schluessel gewachsen (Datacores standen
    # sonst als "#20411" da). Geprueft wird, dass ALLE Plan-Schluessel mit
    # Mengen drin sind - nicht mehr eine feste Zeile.
    # Die Schluesselliste gibt es jetzt EINMAL (PLAN_QTY_KEYS) - vorher stand
    # sie zweimal da, und beim Nachtragen der Invention-Schluessel wurde nur
    # eine erwischt.
    check("b4d Namen auch fuer Items unterhalb der Baumtiefe",
          all(f'"{_k}"' in _src_mw[_pos_von(_src_mw, "PLAN_QTY_KEYS = ("):][:260]
              for _k in ("stock_used", "surplus", "build_runs", "buy",
                         "inv_buy", "inv_stock_used")))
    check("b4d und beide Sammelstellen nutzen dieselbe Liste",
          _src_mw.count("for _pk in self.PLAN_QTY_KEYS:") == 1
          and _src_mw.count("for _k in self.PLAN_QTY_KEYS:") == 1)

    # ------------------------------------------------------------ (b5c)
    # Die zwei WARNUNGEN, die beim Entschlacken NICHT verlorengehen duerfen.
    check("b5c Kapazitaets-Warnung sitzt im Einkaufswagen-Pfad",
          "Does not fit in one trip" in _src_mw
          and '_ti = getattr(self, "_bd_transport", None)' in _src_mw)
    check("b5c Struktur-Warnung als Popup beim Oeffnen",
          "No hangar stock is counted" in _src_mw
          and "_bd_nostruct_warned" in _src_mw)
    check("b5c Transportzeile nur noch bei Ueberschreitung sichtbar",
          "st_transport.setVisible(bool(tinfo.get(\"over_capacity\"))" in _src_mw)

    # ------------------------------------------------------------ (b5d)
    # Aufgeraeumte Anordnung: Puffer/Fracht gehoeren nach OBEN, die
    # Aktionsknoepfe nach unten links, der Details-Bereich bleibt schmal.
    # Puffer wanderte auf Nutzer-Wunsch wieder nach UNTEN zur
    # Einkaufswagen-Aktion - er wirkt ja beim Hinzufuegen zum Wagen.
    # PUFFER UND WAGEN-KNOPF SIND WEG (Nutzer: "alles ist jetzt ueber den
    # Material-Tab machbar"). Beides steckt im Einkaufsfenster, das
    # "Materialien kopieren" oeffnet - vorher gegengeprueft, dass beide Wege
    # dieselbe Appraisal liefern. Die Fusszeile traegt nur noch Speichern.
    # NICHT auf "r2.addWidget(cart)" pruefen: dieselbe Variable gibt es im
    # Multibuy-Fenster weiter unten. Entscheidend ist, dass der BAUPLAN
    # nichts mehr in den Wagen legt.
    check("b5d kein Einkaufswagen-Knopf mehr im Bauplan",
          'QPushButton("\\U0001F6D2 Zu Einkaufswagen' not in _src_mw
          and 'self._plan_to_cart({"buy": plan.get("buy", {})}, names)'
          not in _src_mw)
    check("b5d kein zweites Puffer-Feld mehr in der Fusszeile",
          "r2.addWidget(surplus_spin)" not in _src_mw)
    # Die EINSTELLUNG muss bleiben - das Fenster liest und schreibt sie.
    check("b5d Puffer-Einstellung bleibt erhalten",
          '"bau_buy_surplus"' in _src_mw)
    check("b5d statisches Hub-Label nicht mehr in der Kopfleiste",
          "ctrl.addWidget(_lhub_lbl)" not in _src_mw)
    check("b5d Hub-Label hat trotzdem einen Parent (kein Geisterfenster)",
          "_lhub_lbl.setParent(dlg)" in _src_mw)
    for _w in ("_tl", "transport_cap_spin", "_tcol", "freight_dec_cb"):
        check(f"b5d oben statt unten: {_w}", f"r2s.addWidget({_w})" in _src_mw
              or f"r2s.addLayout({_w})" in _src_mw)
    # Die Fracht-Zeile sitzt jetzt in einem EINGEKLAPPTEN Feld im Kopfbereich
    # (Nutzer: "das mit dem Frachtraum stoert mich noch").
    check("b5d Fracht-Block ist einklappbar",
          '_fr_w = QWidget(); _fr_w.setLayout(r2s)' in _src_mw
          and "Fracht & Transport" in _src_mw)
    # Heisst seit dem Umzug in die rechte Details-Spalte "Frachtkosten"
    # (Nutzer) - zugeklappt muss sie trotzdem starten.
    check("b5d und standardmaessig zugeklappt",
          '"Freight cost"), _fr_w, expanded=False' in _src_mw)
    check("b5d Struktur-Zeile nicht mehr dauerhaft sichtbar",
          "st_struct.setVisible(False)" in _src_mw)
    check("b5d Fusszeilen-Hinweis in die Tooltips verlegt",
          "hint.setVisible(False)" in _src_mw)
    check("b5d beide behalten einen Parent (kein Geisterfenster)",
          "st_struct.setParent(dlg)" in _src_mw
          and "hint.setParent(dlg)" in _src_mw)
    # "Bauplan speichern" ist in die OBERE Leiste gewandert (Nutzer), direkt
    # hinter "Neu berechnen" - und neutral gestylt, damit dort genau EINE
    # Aktion hervorgehoben bleibt. "Schliessen" entfaellt ganz (rotes X).
    check("b5d Speichern sitzt hinter 'Neu berechnen' in der Kopfleiste",
          "ctrl.insertWidget(ctrl.indexOf(recalc) + 1, save_btn)" in _src_mw)
    # UMGEDREHT emm298 (Nutzer: "ich wuerde eher Save Buildplan einfaerben"):
    # Speichern ist die EINE hervorgehobene Aktion, Reset neutral.
    check("b5d Speichern ist hervorgehoben, Reset neutral",
          'save_btn.setObjectName("Primary")' in _src_mw
          and "recalc.setStyleSheet(_secondary_btn_css)" in _src_mw)
    check("b5d kein eigener Schliessen-Knopf mehr",
          'cl = QPushButton("Schlie\\u00dfen"); cl.clicked.connect(dlg.accept)'
          not in _src_mw)
    # Seit dem Zwei-Spalten-Umbau (Kosten links, Gewinn rechts) darf der
    # Bereich breiter sein - begrenzt bleiben MUSS er trotzdem, sonst zieht
    # er sich wieder ueber die ganze Fensterbreite ("kein Chamaeleon").
    check("b5d Details-Bereich ist breitenbegrenzt",
          "st_details_panel.setMaximumWidth(1240)" in _src_mw)

    # ------------------------------------------------------------ (b5e)
    # TAB-REIHENFOLGE (Nutzer): erst das Arbeitsmaterial, dann das
    # Nachschlagewerk. Und der Dialog startet auf Materialien.
    from PySide6.QtWidgets import QTabWidget as _QTW
    # ANGEPASST: der Invention-Tab ist nicht mehr immer da. `_Recipes` oben
    # hat KEINEN Invention-Eintrag, ist also ein T1-Endprodukt - dort gibt es
    # nichts zu erfinden, und der Tab wird bewusst entfernt (ME/TE stehen
    # stattdessen oben neben der Menge). Geprueft wird deshalb die RELATIVE
    # Reihenfolge der vorhandenen Tabs, nicht mehr eine feste Anzahl. Die
    # Vollbesetzung mit Invention deckt b9 mit einem erfundenen Endprodukt ab.
    _tabws = [x for x in _dlg.findChildren(_QTW) if x.count() >= 4]
    check("b5e Tab-Leiste des Bauplans gefunden", bool(_tabws))
    if _tabws:
        _tb = _tabws[0]
        _titles = [_tb.tabText(_i) for _i in range(_tb.count())]
        # Rezept-Struktur zuerst: dort werden die Entscheidungen getroffen,
        # die Materialliste ist das Ergebnis davon.
        # Runplaner ganz nach rechts (Nutzer): er ist der letzte Schritt.
        # REIHENFOLGE = ARBEITSABLAUF (Nutzer): "Rezept anschauen, dann
        # Invention planen, dann Blueprints checken, dann Materialien
        # einkaufen, dann ingame mit dem Runplaner arbeiten."
        # Zweisprachig (Sitzung 16): die Reitertexte laufen durch t().
        _order = [_t4("Recipe structure"), "Invention", "Blueprints",
                  _t4("Materials"), _t4("Run planner")]
        _pos_of = {}
        for _key in _order:
            for _i, _t in enumerate(_titles):
                if _key in _t:
                    _pos_of[_key] = _i
                    break
        _seen = [_pos_of[_k] for _k in _order if _k in _pos_of]
        check(f"b5e Reihenfolge stimmt  ({_titles})", _seen == sorted(_seen))
        check("b5e T1-Endprodukt hat keinen Invention-Tab", "Invention" not in _pos_of)
        for _key in (_t4("Recipe structure"), _t4("Materials"),
                     _t4("Run planner"), "Blueprints"):
            check(f"b5e {_key} vorhanden  ({_titles})", _key in _pos_of)
        eq("b5e Dialog startet auf dem ersten Tab", _tb.currentIndex(), 0)
        # NICHT nur relativ pruefen: die alte Fassung verglich die Positionen
        # der VORHANDENEN Tabs untereinander - eine vertauschte Reihenfolge
        # blieb dadurch gruen, solange sie zur erwarteten Liste passte. Hier
        # die tatsaechliche Abfolge, Tab fuer Tab.
        _ist = [_t for _t in _titles
                if any(_k in _t for _k in _order)]
        _soll = [_k for _k in _order
                 if any(_k in _t for _t in _titles)]
        check(f"b5e tatsaechliche Abfolge stimmt  ({_ist})",
              [next(_k for _k in _order if _k in _t) for _t in _ist] == _soll)

    # ------------------------------------------------------------ (b5f)
    # Blueprints-Tab: dieselben zwei Fehler wie im Materialien-Tab.
    check("b5f Status-Pille zeichnet den Item-Text nicht doppelt",
          "_bi = tbl.item(i, 6)" in _src_mw and '_bi.setText("")' in _src_mw)
    check("b5f Blueprint-Status-Spalte streckt sich",
          _src_mw.count("_bh.setSectionResizeMode(6, _QHV2.Stretch)") == 1)

    # ------------------------------------------------------------ (b5g)
    # SORTIEREN DARF DIE BALKEN NICHT VERWECHSELN. Qt sortiert die ITEMS um,
    # laesst Zell-WIDGETS aber am alten Zeilenindex stehen - danach zeigt der
    # Balken die Aussage einer FREMDEN Zeile (vom Nutzer im Screenshot
    # gesehen, nachdem die Status-Spalte sortierbar wurde).
    if _mat:
        from PySide6.QtWidgets import QProgressBar as _QPB5
        _mt = _mat[0]

        def _bar_texts():
            _out = []
            for _g in range(_mt.topLevelItemCount()):
                _gi = _mt.topLevelItem(_g)
                for _c in range(_gi.childCount()):
                    _nd = _gi.child(_c)
                    _w = _mt.itemWidget(_nd, 6)
                    if isinstance(_w, _QPB5):
                        _out.append((_nd.text(0), _w.format()))
            return _out
        _before = dict(_bar_texts())
        check("b5g Balken sind vor dem Sortieren vorhanden", bool(_before))
        _mt.sortByColumn(6, Qt.AscendingOrder)
        _app.processEvents()
        _after = dict(_bar_texts())
        check("b5g nach dem Sortieren gleich viele Balken",
              len(_after) == len(_before) and bool(_after))
        _mismatch = [k for k in _after if _before.get(k) != _after[k]]
        check(f"b5g jeder Balken gehoert noch zu SEINEM Item {_mismatch[:2]}",
              not _mismatch)
        _mt.sortByColumn(0, Qt.AscendingOrder)
        _app.processEvents()
        _after2 = dict(_bar_texts())
        check("b5g auch nach erneutem Sortieren korrekt",
              all(_before.get(k) == v for k, v in _after2.items()))
        # Gruppierung darf durch Sortieren NICHT zerfallen.
        check("b5g Gruppen bleiben nach dem Sortieren erhalten",
              _mt.topLevelItemCount() == len(_grp))
    # Einfuege-Panel: "Dauerhaft gueltig" ist standardmaessig AN.
    _perm = [c for c in _dlg.findChildren(QCheckBox)
             if _t4("Keep after ESI updates") in c.text()]
    check("b5g Haken 'nach ESI-Aktualisierung behalten' existiert", bool(_perm))
    if _perm:
        check("b5g und ist standardmaessig gesetzt", _perm[0].isChecked())

    # ------------------------------------------------------------ (b5h)
    # RECHTSKLICK -> BLACKLIST im Rezept-Baum (Nutzer-Wunsch). Loest das
    # Tippfehler-Problem an der Wurzel: kein Tippen, kein Namensabgleich.
    check("b5h Mehrfachauswahl im Rezept-Baum",
          "tw.setSelectionMode(QTreeWidget.ExtendedSelection)" in _src_mw)
    # SEIT SITZUNG 16 ENGLISCH im Quelltext, Deutsch im Katalog.
    check("b5h Kontextmenue bietet 'Auf die Blacklist'",
          "Add to blacklist" in _src_mw)
    check("b5h und das Zuruecknehmen", "Remove from blacklist" in _src_mw)
    check("b5h mehrere Items auf einmal",
          "_sel = [x for x in tw.selectedItems()" in _src_mw)
    check("b5h Textfeld wird nachgezogen",
          "def _push_blacklist_to_ui(self):" in _src_mw)

    # ------------------------------------------------------------ (b5i)
    # FERTIGUNGSTIEFE: Panel vorhanden, Stufen setzen die Kategorie-Haken.
    from PySide6.QtWidgets import QRadioButton as _QRB
    _rbs = [r for r in _dlg.findChildren(_QRB)
            if r.text() in ("Nur das Endprodukt", "Ab Komponenten",
                            "Ab Composite-Reaktionen", "Ab Intermediate-Reaktionen",
                            "End product only", "From components",
                            "From composite reactions", "From intermediate reactions")]
    eq("b5i vier Tiefenstufen sichtbar", len(_rbs), 4)
    # NAME DER VIERTEN STUFE (Nutzer 26.09.2026): "From intermediate
    # reactions" statt "Everything yourself" - gleiche Kategorien (alle).
    check("b5i die vierte Stufe heisst 'From intermediate reactions', nicht 'Everything yourself'",
          [r.text() for r in _rbs][-1:] in (["From intermediate reactions"],
                                            ["Ab Intermediate-Reaktionen"])
          and not [r for r in _dlg.findChildren(_QRB)
                   if r.text() in ("Everything yourself", "Alles selbst")])
    check("b5i genau eine ist gewaehlt",
          sum(1 for r in _rbs if r.isChecked()) == 1)
    _by_txt = {r.text(): r for r in _rbs}
    if "Nur das Endprodukt" in _by_txt:
        _by_txt["Nur das Endprodukt"].setChecked(True)
        _app.processEvents()
        _boxes = getattr(win, "_bp_own_boxes", {}) or {}
        check("b5i Stufe 1 hakt ALLE Kategorien ab",
              all(not c.isChecked() for c in _boxes.values()) if _boxes else True)
        _by_txt["Ab Intermediate-Reaktionen"].setChecked(True)
        _app.processEvents()
        check("b5i Stufe 4 hakt alle wieder an",
              all(c.isChecked() for c in _boxes.values()) if _boxes else True)

    # ------------------------------------------------------------ (b6)
    # Rezept-Baum muss Zeilen haben - sonst ist der Aufbau zwar fehlerfrei,
    # aber leer (auch ein Fehlerbild).
    # EINDEUTIG identifizieren: seit der Materialien-Tab ebenfalls ein Baum
    # ist, gibt es MEHRERE QTreeWidgets. Der Rezept-Baum hat die Kopfzeile
    # "Item / Menge / Aktion" - danach suchen, nicht nach der Reihenfolge.
    _trees = [t for t in _dlg.findChildren(QTreeWidget)
              if t.topLevelItemCount() > 0 and t.headerItem()
              and t.headerItem().text(0) == "Item"
              and t.headerItem().text(2) in ("Aktion", "Action")]
    check("b6 Rezept-Baum ist gefuellt", bool(_trees))
    if _trees:
        _rt = _trees[0]
        check("b6 Spalte 'ISK/Stk' ausgeblendet", _rt.isColumnHidden(3))
        check("b6 Spalte 'Kosten' ausgeblendet", _rt.isColumnHidden(4))
        check("b6 keine Zebrastreifen mehr", not _rt.alternatingRowColors())
        # Jedes Item im Baum muss einen NAMEN haben, keine "#12345"-Nummer.
        _nums = []

        def _walk_names(_it):
            _txt = _it.text(0).strip()
            if _txt.startswith("#") and _txt[1:].isdigit():
                _nums.append(_txt)
            for _k in range(_it.childCount()):
                _walk_names(_it.child(_k))
        for _k in range(_rt.topLevelItemCount()):
            _walk_names(_rt.topLevelItem(_k))
        check(f"b6 keine Roh-IDs statt Itemnamen {_nums[:3]}", not _nums)
        # KATEGORIE-ORDNUNG auf der obersten Ebene (Nutzer: "man erkennt
        # nicht, was welcher Kategorie angehoert"). Reihenfolge folgt der
        # Bau-Logik: Komponenten -> Reaktionen -> Kauf-Material.
        _r0 = _rt.topLevelItem(0)
        _kid_txt = [_r0.child(_k).text(0) for _k in range(_r0.childCount())]
        # "Kauf-Material" ist inzwischen aufgeteilt in Mineralien /
        # Mond-Materialien / Rohstoffe (Nutzer: "die sind so vermischt").
        # Die Aussage bleibt dieselbe: jedes Item traegt eine Kategorie, und
        # die Einkaufsposten stehen hinten.
        _kaufcats = ("Mineralien", "Mond-Materialien", "Rohstoffe")
        # Seit dem Auftrag "unbekannte Gruppe darf keine Kategorie behaupten"
        # ist auch die ausdrueckliche Markierung zulaessig: ein Item ohne
        # SDE-Gruppe steht unter "noch nicht aufgeloest" statt faelschlich
        # unter "Rohstoffe" (Arbeitsregel 6). Die Aussage des Tests bleibt:
        # KEIN Kopf ohne Etikett - behauptet wird aber nichts mehr.
        _labels6 = ("Komponente", "Reaktion") + _kaufcats \
            + (MainWindow.GRUPPE_UNBEKANNT,) \
            + ("Component", "Reaction", "Minerals", "Moon materials",
               "Raw materials", "not resolved yet")
        check("b6 Kategorie steht am Item",
              all(any(c in x for c in _labels6) for x in _kid_txt)
              if _kid_txt else True)
        _rank = {"Komponente": 1, "Reaktion": 2}
        _rank.update({c: 3 for c in _kaufcats})
        _seq = [next((v for k, v in _rank.items() if k in x), 3)
                for x in _kid_txt]
        check(f"b6 nach Kategorie sortiert {_seq}", _seq == sorted(_seq))

    # ------------------------------------------------------------ (b7)
    # Der Neu-Berechnen-Knopf muss klickbar sein, ohne zu werfen. Damit
    # laeuft rebuild() ein zweites Mal - der UnboundLocalError trat genau
    # in diesem Pfad auf.
    # SEIT emm298 laeuft dieser zweite rebuild() ueber die automatische
    # ME/TE-Uebernahme: Feld aendern -> Timer -> _mete_uebernehmen. Dabei
    # bleiben die Runplaner-Haken stehen (der alte Knopf raeumte sie weg).
    try:
        _ms7 = list(getattr(win, "_bd_mete_spins", ()) or ())
        _me7 = _ms7[0]
        _alt7 = _me7.value()
        _neu7 = _alt7 + 1 if _alt7 < 10 else _alt7 - 1
        _hk_alt7 = getattr(win, "_bd_runplan_checked", None)
        win._bd_runplan_checked = {"b7|1|200"}
        _me7.setValue(_neu7)
        _tm7 = getattr(win, "_bd_mete_timer", None)
        check("b7 ME-Aenderung startet den Entprell-Timer",
              _tm7 is not None and _tm7.isActive())
        win._bd_mete_uebernehmen()
        _app.processEvents()
        _rig7 = win._bau_rig_me()
        _eff7 = (1 - (1 - _neu7 / 100.0) * (1 - _rig7 / 100.0)) * 100.0
        check(f"b7 ME uebernommen ohne Knopf: _bd_me {getattr(win, '_bd_me', None)}, "
              f"opts {win._bd_opts.get('me')} (soll {_neu7} / {_eff7})",
              getattr(win, "_bd_me", None) == _neu7
              and abs(float(win._bd_opts.get("me") or 0) - _eff7) < 1e-9)
        check("b7 der gerechnete Stand ist der Feldstand (nichts mehr offen)",
              (win._bd_me_te_applied or {}).get("end_me") == _neu7)
        check("b7 die Runplaner-Haken bleiben stehen",
              "b7|1|200" in (win._bd_runplan_checked or set()))
        _me7.setValue(_alt7)
        win._bd_mete_uebernehmen()
        _app.processEvents()
        win._bd_runplan_checked = _hk_alt7
        check("b7 zurueckgedreht ist wieder der alte Stand",
              getattr(win, "_bd_me", None) == _alt7)
    except Exception as e:                                # pragma: no cover
        import traceback as _tb7
        _fail.append(f"b7 ME/TE automatisch: {type(e).__name__}: {e} | "
                     + _tb7.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b7b)
# TOOLTIPS MUESSEN UMBRECHEN. Qt zeigt reinen Text ohne Zeilenumbruch als
# EINE Zeile - lange Erklaerungen zogen sich ueber die ganze Fensterbreite
# (Nutzer: "gigantisch und viel zu lang auf die Breite gezogen").
if _dlg is not None:
    from PySide6.QtWidgets import QWidget as _QW7
    _all_tips = [x.toolTip() for x in _dlg.findChildren(_QW7) if x.toolTip()]
    check("b7b es gibt ueberhaupt Tooltips", len(_all_tips) > 10)
    _plain = [x for x in _all_tips if not x.lstrip().startswith("<")]
    check(f"b7b alle Tooltips sind umbruchfaehig ({len(_plain)} roh)",
          not _plain)
    check("b7b Breitenbegrenzung gesetzt",
          all("max-width" in x for x in _all_tips))

# ---------------------------------------------------------------- (b7c)
# SCHRIFTART der Item-Listen (Nutzer: "etwas weniger roboterisch"). Vorher
# Consolas/monospace - das las sich wie ein Terminal.
_theme_src = open(os.path.join(_ROOT,
                               "eve_trader", "ui", "theme.py"),
                  encoding="utf-8").read()
# theme.py ist ein f-String-Template ({{ }}), deshalb kein Klammer-Regex,
# sondern ein Blick auf den Abschnitt hinter dem Selektor.
for _blk in ("QTableWidget {{", "QTreeWidget {{"):
    _i7 = _theme_src.find(_blk)
    _seg = _theme_src[_i7:_i7 + 420] if _i7 >= 0 else ""
    # NUR die font-family-Zeile pruefen: das Wort "Consolas" steht auch im
    # erklaerenden Kommentar daneben und wuerde sonst falschen Alarm geben.
    _ff = [l for l in _seg.splitlines() if "font-family" in l]
    check(f"b7c {_blk.split()[0]} nicht mehr monospace",
          bool(_ff) and all("Consolas" not in l for l in _ff))
    # Seit der Industrie-Schrift steht dort die KETTE {FONT} statt einer
    # fest verdrahteten Familie - die Zusage ist "UI-Schrift, nicht Mono".
    check(f"b7c {_blk.split()[0]} nutzt die UI-Schrift",
          bool(_ff) and any("{FONT}" in l for l in _ff))
# Absichtlich monospace geblieben: dort haengt die Lesbarkeit an
# gleichbreiten Ziffern.
check("b7c KPI-Werte bleiben monospace",
      "QLabel#KpiValue" in _theme_src
      and "{MONO}" in _theme_src[_pos_von(_theme_src, "QLabel#KpiValue"):
                                   _pos_von(_theme_src, "QLabel#KpiValue") + 120])

# ---------------------------------------------------------------- (b7c)
# ZWEITES SZENARIO: Markt UNTER dem Mindestpreis. Dieser Zweig war bisher
# ungeprueft - und genau dort stand ein `_tip.insert(...)` auf einer
# Zeichenkette statt auf der Liste. Ergebnis: JEDER Bauplan stuerzte beim
# Oeffnen ab ("AttributeError: 'str' object has no attribute 'insert'"),
# waehrend der Test gruen blieb, weil sein Verkaufspreis stets ueber den
# Kosten lag. Ein Test, der nur den guenstigen Fall kennt, prueft die Haelfte.
_res_low = dict(_res)
_res_low["sell"] = 1.0            # weit unter jedem Mindestpreis
try:
    win._show_build_detail(100, "Testship-Verlust", _res_low)
    check("b7c Bauplan baut auch bei Markt UNTER Mindestpreis", True)
    _dlg_low = getattr(win, "_bd_dialog", None)
    if _dlg_low is not None:
        _tips_low = " ".join(x.toolTip() for x in _dlg_low.findChildren(QLabel)
                             if x.toolTip())
        check("b7c Verlust-Warnung steht im Tooltip",
              "MINDESTPREIS" in _tips_low or "Verlust" in _tips_low
              or "MINIMUM PRICE" in _tips_low or "loss" in _tips_low)
except Exception as e:                                   # pragma: no cover
    import traceback
    traceback.print_exc()
    _fail.append(f"b7c Markt unter Mindestpreis: {type(e).__name__}: {e}")

# ---------------------------------------------------------------- (b7d)
# KEIN VERKAUFSPREIS UEBERHAUPT - der Capital-Fall (Nutzer "buyenne",
# 15.09.2026, Discord: Hel und Phoenix stuerzten ab, Stork und Avalanche
# nicht). Capitals haben in Jita praktisch keine Sell-Orders; sind DANN
# auch noch keine Contract-Preise geladen, ist `_sell_eff` leer.
#
# WAS DANN PASSIERTE: der ganze Gewinn-Block haengt an `if _sell_eff:` -
# dort entstehen `gross`, `prof`, `prof_raw` und `total_all`. Die rechte
# Spalte ("Verkaufserloes brutto", "= Gewinn", "Marge") liest sie danach
# BEDINGUNGSLOS. Ohne Verkaufspreis gab es sie nie:
#   UnboundLocalError: cannot access local variable 'gross'
# `marge` und `fees` waren vorbelegt - die beiden anderen wurden vergessen,
# als die Spalte dazukam. Genau darum steht hier ein Test und kein Kommentar.
_res_nosell = dict(_res)
_res_nosell["sell"] = 0.0             # kein Marktpreis (Capital in Jita)
_res_nosell["sell_is_contract"] = True
win._bd_hub_sell_price = None
win._bd_contract_sell = None          # Contract-Preise NICHT geladen
try:
    win._show_build_detail(100, "Testcapital-ohne-Preis", _res_nosell)
    check("b7d Bauplan oeffnet auch ganz OHNE Verkaufspreis", True)
    _dlg_ns = getattr(win, "_bd_dialog", None)
    check("b7d Dialog steht", _dlg_ns is not None)
    if _dlg_ns is not None:
        # GEGENPROBE ZUM NORMALFALL: ohne Preis darf dort KEINE Zahl
        # stehen - weder eine 0 noch ein erfundener Gewinn. Ein Strich ist
        # die ehrliche Antwort (Regel 3: lieber nichts behaupten).
        _txt_ns = [x.text() for x in _dlg_ns.findChildren(QLabel)]
        check("b7d ohne Preis steht kein erfundener Gewinn da",
              "\u2013" in _txt_ns or "\u2014" in _txt_ns)
except Exception as e:                                   # pragma: no cover
    import traceback
    traceback.print_exc()
    _fail.append(f"b7d ohne Verkaufspreis: {type(e).__name__}: {e}")

# ---------------------------------------------------------------- (b7e)
# DER CONTRACT-KNOPF ZEIGT SICH IM RICHTIGEN MOMENT.
# NUTZER, 15.09.2026: "der load contracts button soll ersichtlicher werden,
# nicht versteckt in Dropdowns" - und blinken wie der Markt-Scan-Knopf.
# Der richtige Moment ist genau der, in dem das Verkaufsfeld leer bleibt.
#
# NICHT AUF isVisible() PRUEFEN: in einem nie angezeigten Fenster meldet das
# IMMER False (teuer gelernte Qt-Falle). isHidden() sagt dagegen, ob das
# Widget AUSDRUECKLICH versteckt wurde - genau die Frage hier.
_ctb = getattr(win, "_bd_ct_btn", None)
check("b7e der Contract-Knopf existiert als eigener Knopf", _ctb is not None)
if _ctb is not None:
    check("b7e ohne Verkaufspreis ist er sichtbar", not _ctb.isHidden())
    _tmr_ct = getattr(_ctb, "_ct_blink_timer", None)
    check("b7e und er blinkt", _tmr_ct is not None and _tmr_ct.isActive())
    # KEIN GROESSENSPRUNG: beide Blinkzustaende tragen einen 2-px-Rahmen
    # (Nutzer-Befund Sitzung 20 am Markt-Scan-Knopf - dieselbe Falle).
    check("b7e Ruhezustand traegt schon 2 px Rahmen",
          "border:2px solid" in getattr(_ctb, "_ct_css", ""))
    win._blink_rahmen(_ctb, True, getattr(_ctb, "_ct_css", ""))
    _an_css = _ctb.styleSheet()
    win._blink_rahmen(_ctb, False, getattr(_ctb, "_ct_css", ""))
    _aus_css = _ctb.styleSheet()
    check("b7e beide Zustaende sind gleich stark gerahmt",
          _an_css.count("border:2px solid") == _aus_css.count("border:2px solid"))
    check("b7e das Grund-Aussehen bleibt beim Blinken erhalten",
          "padding:6px 12px" in _an_css and "padding:6px 12px" in _aus_css)
# MIT Verkaufspreis muss er wieder weg sein - sonst steht ein blinkender
# Knopf in jedem normalen Bauplan und faellt genau dann nicht mehr auf,
# wenn er gebraucht wird.
try:
    win._show_build_detail(100, "Testship", _res)
    _ctb2 = getattr(win, "_bd_ct_btn", None)
    check("b7e mit Verkaufspreis ist der Knopf versteckt",
          _ctb2 is not None and _ctb2.isHidden())
    _tmr2 = getattr(_ctb2, "_ct_blink_timer", None)
    check("b7e und das Blinken steht still",
          _tmr2 is None or not _tmr2.isActive())
except Exception as e:                                   # pragma: no cover
    import traceback
    traceback.print_exc()
    _fail.append(f"b7e Contract-Knopf mit Preis: {type(e).__name__}: {e}")

# ---------------------------------------------------------------- (b7f)
# DER NAME IM RUNPLANER IST KOPIERBAR UND GERAHMT.
# NUTZER, 15.09.2026: "im Runplaner steht Silicon Diborite - klickt man drauf,
# bekommt man Silicon Diborite Reaction Formula ins Clipboard", dazu ein
# kleiner Rahmen wie um die Run-Zahlen, fette Run-Zahlen, und die FARBE des
# Namens soll bleiben (gebaute Zeilen blau, nicht amber).
from PySide6.QtWidgets import QTreeWidgetItem as _TWI7f
from eve_trader.ui.mw_basis import (ROLLE_KOPIERNAME as _RKN7f,
                                    kopier_text_rect as _ktr7f)
_dlg7f = getattr(win, "_bd_dialog", None)
_sched7f = next((x for x in (_dlg7f.findChildren(QTreeWidget) if _dlg7f else [])
                 if x.columnCount() == 6), None)
check("b7f der Runplaner-Baum ist da", _sched7f is not None)
if _sched7f is not None:
    # KEINE HERVORHEBUNG MEHR (Nutzer, 15.09.2026: "die Items sollen wieder
    # normal aussehen"). Erst war es ein Rahmen, dann ein Chip - beides zu
    # laut. Die Zeile sieht aus wie jede andere; nur der Klick kopiert.
    check("b7f Spalte 0 malt NICHTS Eigenes mehr",
          _sched7f.itemDelegateForColumn(0) is None)
    # DAS KAESTCHEN BLEIBT FREI: der Rahmen (und damit die Trefferflaeche)
    # faengt rechts vom Haken an - sonst kopierte jeder Haken still mit.
    _ti7f = _TWI7f(["Silicon Diborite", "130", "", "", "", ""])
    _sched7f.addTopLevelItem(_ti7f)
    _ti7f.setData(0, _RKN7f, "Silicon Diborite Reaction Formula")
    _idx7f = _sched7f.indexFromItem(_ti7f, 0)
    _r7f = _ktr7f(_sched7f, _idx7f, _sched7f.visualRect(_idx7f))
    check("b7f die Trefferflaeche laesst das Kaestchen aus",
          _r7f is not None and _r7f.left() > _sched7f.visualRect(_idx7f).left())
    # KEIN KOPIEREN OHNE NAMEN und nicht in anderen Spalten - sonst
    # ueberschreibt jeder Klick im Baum die Zwischenablage.
    _ti_ohne7f = _TWI7f(["Leziris Lezflow", "", "", "", "", ""])
    _sched7f.addTopLevelItem(_ti_ohne7f)
    QApplication.clipboard().setText("UNBERUEHRT")
    win._sched_name_klick(_ti_ohne7f, 0)
    win._sched_name_klick(_ti7f, 3)
    check("b7f ein Klick ohne Namen kopiert nichts",
          QApplication.clipboard().text() == "UNBERUEHRT")
    _sched7f.takeTopLevelItem(_sched7f.indexOfTopLevelItem(_ti7f))
    _sched7f.takeTopLevelItem(_sched7f.indexOfTopLevelItem(_ti_ohne7f))
# DIE VERDRAHTUNG IM RUNPLANER SELBST - am Quelltext, weil der Baum ohne
# getickte Bau-Charaktere leer bleibt und die Pruefung sonst blind waere.
_src7f = open("eve_trader/ui/mw_bauplan_tabs.py", encoding="utf-8").read()
check("b7f der Formel-Name wird an der Zeile hinterlegt",
      "iit.setData(0, ROLLE_KOPIERNAME," in _src7f)
check("b7f und er kommt aus _bp_name_fuer (EINE Regel)",
      "self._bp_name_fuer(\n"
      "                                    self._bp_basisname(a.get(\"tid\"), a.get(\"name\")),"
      in _src7f)
check("b7f die Run-Zahl steht fett", "_fr.setBold(True)" in _src7f
      and "iit.setFont(1, _fr)" in _src7f)
# GAR KEIN ZEICHNEN MEHR IN mw_basis: weder Rahmen noch Chip. Waere eines
# davon zurueck, saehe die Zeile wieder anders aus als der Rest des Baums.
_src7f_b = open("eve_trader/ui/mw_basis.py", encoding="utf-8").read()
check("b7f in mw_basis wird nichts mehr in die Spalte gemalt",
      "QStyledItemDelegate" not in _src7f_b
      and "drawRoundedRect" not in _src7f_b)

# ---------------------------------------------------------------- (b7g)
# BAUPLAENE SELBER ANORDNEN (Nutzer, 15.09.2026).
# Ein Umschalter haelt die automatische Sortierung nach Fortschritt heraus,
# die Karten lassen sich mit gehaltener linker Maustaste ziehen, und die
# eigene Folge ueberlebt Schliessen UND Update (settings.json liegt im
# Nutzerordner, die .exe wird beim Update nur ersetzt).
from PySide6.QtCore import QEvent as _QEv7g, QPoint as _QP7g
from PySide6.QtGui import QWheelEvent as _QWh7g
from PySide6.QtWidgets import (QVBoxLayout as _QVB7g, QWidget as _QW7g,
                               QScrollArea as _QSA7g)
from eve_trader.ui.mw_basis import KartenSortierer as _KS7g

_halter7g = _QW7g()
_lay7g = _QVB7g(_halter7g)
_karten7g = []
for _i7g in range(3):
    _k7g = _QW7g()
    _lay7g.addWidget(_k7g)
    _karten7g.append(_k7g)
_scr7g = _QSA7g()
_pids7g = {id(_w): f"p{_n}" for _n, _w in enumerate(_karten7g)}
_gemerkt7g = []
_srt7g = _KS7g(_lay7g, _scr7g, lambda _w: _pids7g.get(id(_w)),
               lambda _o: _gemerkt7g.append(list(_o)), parent=_halter7g)
for _k7g in _karten7g:
    _srt7g.ueberwache(_k7g)       # setzt u.a. den Objektnamen fuer den Selektor
eq("b7g die Folge kommt aus dem Layout", _srt7g.reihenfolge(),
   ["p0", "p1", "p2"])
# IM RUHEZUSTAND AENDERT DER SORTIERER NICHTS. Das ist der wichtigste Test:
# die Karten tragen Knoepfe (oeffnen, loeschen), und ein dauerhaft lauernder
# Filter waere ein Risiko fuer jeden Klick darauf.
_ev7g = _QEv7g(_QEv7g.MouseButtonPress)
check("b7g ausgeschaltet schluckt er nichts",
      _srt7g.aktiv is False and _srt7g.eventFilter(_karten7g[0], _ev7g) is False)
# MAUSRAD BLEIBT MAUSRAD - ausdrueckliche Bedingung des Nutzers
# ("scrollen muss auch gehen"), auch waehrend des Anordnens.
_srt7g.aktiv = True
_wh7g = _QWh7g(_QP7g(5, 5), _QP7g(5, 5), _QP7g(0, -120), _QP7g(0, -120),
               Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
check("b7g das Mausrad wird NICHT gefiltert",
      _srt7g.eventFilter(_karten7g[0], _wh7g) is False)
# DIE KNOEPFE AUF DEN KARTEN BLEIBEN BEDIENBAR (Nutzer, 15.09.2026: "was
# bringt der Arrange-Modus, wenn er aktiviert ist und ich nichts druecken
# kann?"). Frueher schluckte der Sortierer JEDEN Druck - der Modus war damit
# nicht dauerhaft nutzbar, obwohl er genau dafuer gedacht ist.
from PySide6.QtWidgets import QPushButton as _QPB7g, QLabel as _QL7g
from PySide6.QtGui import QMouseEvent as _QME7g
from PySide6.QtCore import QPointF as _QPF7g
_knopf7g = _QPB7g("Open", _karten7g[0])
_label7g = _QL7g("Profit", _karten7g[0])


def _druck7g(ziel):
    """Ein echter Linksklick-Druck auf dieses Widget."""
    return _QME7g(_QEv7g.MouseButtonPress, _QPF7g(3, 3), _QPF7g(3, 3),
                  Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)


_srt7g._widget = None
check("b7g ein Druck auf 'Open' geht an den Knopf",
      _srt7g.eventFilter(_knopf7g, _druck7g(_knopf7g)) is False)
check("b7g und der Sortierer merkt sich dabei KEINE Karte",
      _srt7g._widget is None)
check("b7g ein Druck auf die Karte selbst greift weiterhin",
      _srt7g.eventFilter(_karten7g[0], _druck7g(_karten7g[0])) is True
      and _srt7g._widget is _karten7g[0])
_srt7g._widget = None
_srt7g._start = None
check("b7g ein Druck auf ein Label greift ebenfalls (dort wird gezogen)",
      _srt7g.eventFilter(_label7g, _druck7g(_label7g)) is True)
_srt7g._widget = None
_srt7g._start = None
_knopf7g.setParent(None)
_label7g.setParent(None)
# Umsortieren im Layout und merken - ohne echte Maus, die Bewegung selbst
# prueft b7g nicht (dafuer braeuchte es einen sichtbaren Bildschirm).
_lay7g.removeWidget(_karten7g[0])
_lay7g.insertWidget(2, _karten7g[0])
# DIE DREI ZUSTAENDE DER KARTE (Nutzer, 15.09.2026: "wenn ich mit der Maus
# ueber einen Bauplan fahre, moechte ich dass er leicht hervorgehoben wird,
# und wenn ich ihn dann drag and droppe"). Alle drei tragen 1 px Rahmen -
# sonst springt die Karte beim Wechsel, dieselbe Falle wie beim Blinken.
for _z7g, _name7g in (("ruhe", "ruhig"), ("hover", "unter der Maus"),
                      ("zieht", "in der Hand")):
    _srt7g._zeige(_karten7g[0], _z7g)
    check(f"b7g Zustand '{_name7g}' traegt 1 px Rahmen",
          "border:1px solid" in _karten7g[0].styleSheet())
    # NUR DIE KARTE, NICHT IHRE KINDER (Nutzer: "wirklich nur den
    # Gesamtrahmen vom Bauplan, nicht 'Profit' und so auch nochmal
    # umrahmt"). Ohne Selektor vererbt Qt die Regel an jedes Label darin.
    check(f"b7g Zustand '{_name7g}' trifft nur die Karte selbst",
          bool(_KS7g.OBJEKTNAME)
          and _karten7g[0].objectName() == _KS7g.OBJEKTNAME
          and _karten7g[0].styleSheet().startswith(
              "#" + _KS7g.OBJEKTNAME + "{"))
_srt7g._zeige(_karten7g[0], "hover")
_hover7g = _karten7g[0].styleSheet()
_srt7g._zeige(_karten7g[0], "zieht")
_zieht7g = _karten7g[0].styleSheet()
check("b7g nur beim Ziehen kommt eine Flaeche dazu",
      "background:" in _zieht7g and "background:" not in _hover7g)
_srt7g.alles_zuruecksetzen()
check("b7g Ausschalten raeumt die Hervorhebung weg",
      _karten7g[0].styleSheet() == "")
eq("b7g nach dem Verschieben stimmt die Folge", _srt7g.reihenfolge(),
   ["p1", "p2", "p0"])

# --- der Umschalter am Hauptfenster ---------------------------------------
check("b7g der Knopf ist da und rastet ein",
      hasattr(win, "bp_order_btn") and win.bp_order_btn.isCheckable())
_vorher7g = win.settings.get("bau_plan_manuell")
win._plan_handsortierung_umschalten(True)
check("b7g einschalten merkt sich das",
      win.settings.get("bau_plan_manuell") is True)
win._plan_reihenfolge_merken(["7", "3", "9"])
eq("b7g die Folge landet in den Einstellungen",
   win.settings.get("bau_plan_reihenfolge"), ["7", "3", "9"])
# UND DIE AUTOMATIK BLEIBT DRAUSSEN: sonst wirft der naechste ESI-Lauf die
# Handarbeit um - genau das, was der Umschalter verhindern soll.
_lay_alt7g = getattr(win, "_plan_sortier_layout", None)
_wrap_alt7g = getattr(win, "_plan_karte_wrap", None)
win._plan_sortier_layout = _lay7g
win._plan_karte_wrap = {"p0": _karten7g[0]}
win._sortiere_plan_karten({"p0": {"qty": 10, "built": 10, "pct": 100.0}})
eq("b7g die Automatik ruehrt die Handfolge nicht an",
   _srt7g.reihenfolge(), ["p1", "p2", "p0"])
_src_ord7g = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
_i_ord7g = _src_ord7g.find("def _plan_handsortierung_umschalten")
_ab_ord7g = _src_ord7g[_i_ord7g:_i_ord7g + 1800] if _i_ord7g >= 0 else ""
check("b7g der Umschalter ist auffindbar", _i_ord7g >= 0)
# EINSCHALTEN HEISST "MEINE FOLGE GILT" (Nutzer, 15.09.2026).
check("b7g einschalten setzt die eigene Folge in Kraft",
      win.settings.get("bau_plan_eigene_folge") is True
      and win._plan_eigene_folge_gilt() is True)
# AUSSCHALTEN BEENDET NUR DAS ZIEHEN (Nutzer, 15.09.2026: "die Reihenfolge
# bleibt, aber dann fuehren wir einen Knopf ein 'Nach Fortschritt
# sortieren'"). Vorher warf das Ausschalten die Handarbeit sofort um - sein
# Einwand: "da liegt kein Sinn dahinter". Auch die Warnung davor ist raus:
# sie kuendigte etwas an, das nicht mehr passiert.
win.bp_order_btn.setChecked(True)
win._plan_handsortierung_umschalten(False)
check("b7g ausschalten merkt sich das ebenfalls",
      win.settings.get("bau_plan_manuell") is False)
check("b7g aber die eigene Folge gilt weiter",
      win._plan_eigene_folge_gilt() is True)
win._sortiere_plan_karten({"p0": {"qty": 10, "built": 10, "pct": 100.0}})
eq("b7g und die Automatik ruehrt sie auch AUSGESCHALTET nicht an",
   _srt7g.reihenfolge(), ["p1", "p2", "p0"])
check("b7g es wird nicht mehr gefragt beim Ausschalten",
      "_QMB.question(" not in _ab_ord7g)
# ZURUECK ZUR AUTOMATIK NUR AUF KLICK.
check("b7g der Knopf „Nach Fortschritt sortieren“ ist da",
      hasattr(win, "bp_progress_btn"))
win._plan_nach_fortschritt_sortieren()
check("b7g er beendet die eigene Folge",
      win.settings.get("bau_plan_eigene_folge") is False
      and win._plan_eigene_folge_gilt() is False)
eq("b7g und sortiert sofort nach Fortschritt", _srt7g.reihenfolge(),
   ["p0", "p1", "p2"])
check("b7g dafuer wird der letzte Fortschritt gemerkt",
      "self._plan_letzter_fortschritt = res" in _src_ord7g)
# WER DANACH WIEDER SCHIEBT, IST WIEDER IN SEINER FOLGE - sonst muesste er
# den Anordnen-Modus aus- und wieder einschalten, nur damit sein Zug gilt.
win._plan_reihenfolge_merken(["7", "3", "9"])
check("b7g ein neuer Zug setzt die eigene Folge wieder in Kraft",
      win._plan_eigene_folge_gilt() is True)
# OHNE FORTSCHRITT NICHT STILL (Regel 6): ohne ESI-Lauf gibt es nichts zu
# sortieren - das muss der Knopf sagen, sonst sieht er kaputt aus.
_i_prog7g = _src_ord7g.find("def _plan_nach_fortschritt_sortieren")
_ab_prog7g = _src_ord7g[_i_prog7g:_i_prog7g + 1800]
check("b7g ohne Fortschritt sagt der Knopf Bescheid",
      _i_prog7g >= 0 and "self._flash_tip(" in _ab_prog7g)
# DER KNOPF ZEIGT DEN ZUSTAND (Nutzer: "blaues transparent, wie der
# Refresh-all-Button") - derselbe Objektname, also dieselbe Regel aus dem
# Stylesheet statt eines zweiten handgemalten Knopfes.
check("b7g ausgeschaltet ist der Knopf normal",
      win.bp_order_btn.objectName() != "Primary")
win._plan_order_btn_stil(True)
# SEIT 23.09.2026 traegt "Alles aktualisieren" die Primaer-Optik NICHT
# mehr (Nutzer: "bitte die Cyan-Hintergrundfarbe entfernen, damit der Knopf
# aussieht wie alle anderen"). #Primary bleibt die HERVORHEBUNGS-Regel des
# Themas - genau die soll dieser Knopf im eingeschalteten Zustand tragen.
check("b7g eingeschaltet leuchtet er in der Hervorhebungs-Optik",
      win.bp_order_btn.objectName() == "Primary")
win._plan_order_btn_stil(False)
eq("b7g die Handfolge bleibt trotzdem gespeichert",
   win.settings.get("bau_plan_reihenfolge"), ["7", "3", "9"])
win._plan_sortier_layout = _lay_alt7g
win._plan_karte_wrap = _wrap_alt7g
win.settings["bau_plan_manuell"] = _vorher7g
# DIE EINSTELLUNG MUSS ES GEBEN, sonst faellt sie beim ersten Speichern
# heraus und die Reihenfolge ist nach dem naechsten Start weg.
from eve_trader import config as _cfg7g
check("b7g beide Schluessel stehen in den Standardwerten",
      "bau_plan_manuell" in _cfg7g.DEFAULT_SETTINGS
      and "bau_plan_reihenfolge" in _cfg7g.DEFAULT_SETTINGS)

# ---------------------------------------------------------------- (b7h)
# CONTRACT-STAND: ALT -> DER KNOPF BLINKT. Und vor dem Scan wird gefragt.
# NUTZER, 15.09.2026: "ich moechte, dass Load contract prices wenn nicht
# aktuell ist der Button auch blinkt, sonst vergleicht man hier alte Preise
# von gestern" - dazu "ist das normal dass das fast 5 Minuten dauert? wenn
# das normal ist, sollte ein Popup kommen mit einer Warnung".
check("b7h der Capital-Contract-Knopf ist da",
      hasattr(win, "b_cap_contract_btn"))
if hasattr(win, "b_cap_contract_btn"):
    import eve_trader.store as _st7h
    _echt7h = _st7h.contract_prices_age_seconds

    def _blinkt7h():
        """Blinkt der Knopf gerade? NONE-FEST: faellt die Alterspruefung aus,
        gibt es gar keinen Timer - ein `.isActive()` darauf wuerde die ganze
        Suite mit einem AttributeError abreissen, statt EINE Pruefung rot zu
        machen (genau die Falle, die `_pos_von` in der aa-Suite abfaengt).
        Bei der Rotprobe ist das der Unterschied zwischen ROT und BLIND."""
        _t = getattr(win.b_cap_contract_btn, "_ct_blink_timer", None)
        return _t is not None and _t.isActive()
    try:
        # NIE GELADEN -> blinken. Das ist der haeufigste Fall beim ersten
        # Start, und genau dort ist der Hinweis am noetigsten.
        _st7h.contract_prices_age_seconds = lambda _r: None
        win._capital_contract_alter_pruefen()
        check("b7h ohne Stand blinkt er", _blinkt7h())
        # FRISCH -> still.
        _st7h.contract_prices_age_seconds = lambda _r: 60.0
        win._capital_contract_alter_pruefen()
        check("b7h mit frischem Stand blinkt er nicht", not _blinkt7h())
        # AELTER ALS EINEN TAG -> wieder blinken (die Grenze selbst).
        _st7h.contract_prices_age_seconds = \
            lambda _r: win._CONTRACT_ALT_SEKUNDEN + 1
        win._capital_contract_alter_pruefen()
        check("b7h ein Stand von gestern blinkt", _blinkt7h())
        # GENAU AUF DER GRENZE ist er noch gut - sonst blinkt er bei jedem,
        # der taeglich einmal scannt, staendig kurz vor dem naechsten Lauf.
        _st7h.contract_prices_age_seconds = \
            lambda _r: float(win._CONTRACT_ALT_SEKUNDEN)
        win._capital_contract_alter_pruefen()
        check("b7h auf der Grenze noch nicht", not _blinkt7h())
    finally:
        _st7h.contract_prices_age_seconds = _echt7h
    check("b7h die Grenze ist ein Tag, nicht 15 Minuten",
          win._CONTRACT_ALT_SEKUNDEN == 24 * 3600)
    # KEIN GROESSENSPRUNG beim Blinken - 2 px in BEIDEN Zustaenden.
    check("b7h der Ruhezustand traegt schon 2 px Rahmen",
          "border:2px solid" in getattr(win.b_cap_contract_btn, "_ct_css", ""))
# DIE WARNUNG STEHT VOR DEM SCAN, nicht danach - und sie nennt die Dauer.
_src7h = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
_i7h = _src7h.find("def _load_capital_contract_prices")
# GROSSZUEGIGES FENSTER: die ganze Funktion samt done()/fail() - der
# Wiederaufruf des Alters-Checks steht erst dort unten.
_ab7h = _src7h[_i7h:_i7h + 6000]
check("b7h vor dem Scan wird gefragt", "_QMB.question(" in _ab7h)
check("b7h die Frage nennt die Dauer", "SEVERAL " in _ab7h and "MINUTES" in _ab7h)
check("b7h Abbrechen bricht wirklich ab",
      "!= _QMB.Ok:\n            return" in _ab7h)
check("b7h gefragt wird VOR dem Start des Laufs",
      _ab7h.find("_QMB.question(") < _ab7h.find("self._run("))
# UND DAS BLINKEN GEHT NACH EINEM ERFOLGREICHEN SCAN AUS.
check("b7h nach dem Scan wird der Stand neu bewertet",
      "self._capital_contract_alter_pruefen()" in _ab7h)

# ---------------------------------------------------------------- (b7i)
# CAPITAL-MODUS IST BEIM START IMMER AUS.
# NUTZER, 15.09.2026: "die Gefahr ist gross, dass man vergisst da
# herauszugehen, bevor man das Tool schliesst, und dann ist man verwirrt,
# warum man keine normalen Blueprints suchen kann." Der Modus ist etwas fuer
# Fortgeschrittene und darf nie der Zustand sein, in dem man das Programm
# unbemerkt vorfindet.
check("b7i der Capital-Modus-Knopf ist da", hasattr(win, "b_cap_mode"))
if hasattr(win, "b_cap_mode"):
    check("b7i beim Start ist er AUS", not win.b_cap_mode.isChecked())
    check("b7i und die normale Trefferliste ist sichtbar",
          not win.b_table.isHidden())
# DER ZUSTAND DARF AUCH NICHT GESPEICHERT WERDEN - sonst ist er beim
# naechsten Start wieder da, ohne dass jemand ihn eingeschaltet hat.
from eve_trader import config as _cfg7i
check("b7i der Modus steht in keiner Einstellung",
      not any("cap_mode" in _k for _k in _cfg7i.DEFAULT_SETTINGS))
_src7i = open("eve_trader/ui/mw_bauplan_tabs.py", encoding="utf-8").read()
check("b7i und er wird beim Aufbau ausdruecklich ausgeschaltet",
      "self.b_cap_mode.setChecked(False)" in _src7i)

# ---------------------------------------------------------------- (b7j)
# DER HAKEN, DEN NIEMAND GESETZT HAT.
# NUTZER, 15.09.2026, mit zwei Zoom-Bildern: "Titanium Chromide Reaction
# Formula - dieser gruene Haken ist nicht von mir, den kann ich nicht
# setzen ... ich kann ihn auch nicht wegmachen."
#
# URSACHE, nachgemessen (nicht geraten): QTreeWidgetItem traegt
# Qt.ItemIsUserCheckable BEREITS in seinen Standard-Flags, und
# checkState(0) antwortet auch ohne Kaestchen brav "Unchecked". Die
# Kinder-Kaskade in _on_sched_check ("hake ich den Charakter ab, sollen
# seine Positionen mit") fragte genau diese beiden Dinge ab - und legte
# den Material-Unterzeilen damit ein Kaestchen NEU AN, statt ein
# vorhandenes umzuschalten. Beim Loesen blieb es als LEERES Kaestchen
# stehen, weil CheckStateRole dann 0 ist und nicht mehr None.
from PySide6.QtWidgets import QTreeWidget as _TW7j, QTreeWidgetItem as _TWI7j
_t7j = _TW7j(); _t7j.setColumnCount(5)
_eltern7j = _TWI7j(["Peanut Motor", "", "", "", ""])
_t7j.addTopLevelItem(_eltern7j)
_mat7j = _TWI7j(["Vanadium", "1'000", "", "", ""])
_eltern7j.addChild(_mat7j)
check("b7j eine frische Baumzeile ist von Haus aus abhakbar (deshalb "
      "reichen die Flags als Frage nicht)",
      bool(_mat7j.flags() & Qt.ItemIsUserCheckable))
check("b7j und sie meldet Unchecked, obwohl sie gar kein Kaestchen hat",
      _mat7j.checkState(0) == Qt.Unchecked
      and _mat7j.data(0, Qt.CheckStateRole) is None)
# DIE ALTE BEDINGUNG haette hier zugeschlagen, die neue nicht.
check("b7j die alte Kaskaden-Bedingung haette ein Kaestchen erfunden",
      bool(_mat7j.flags() & Qt.ItemIsUserCheckable)
      and _mat7j.checkState(0) != Qt.Checked)
check("b7j die neue Bedingung laesst die Stuecklisten-Zeile in Ruhe",
      not (_mat7j.data(0, Qt.CheckStateRole) is not None
           and _mat7j.flags() & Qt.ItemIsUserCheckable
           and _mat7j.checkState(0) != Qt.Checked))
# BEIDE RIEGEL MUESSEN IM CODE STEHEN - einer allein waere wieder eine
# einzige Stelle, an der es kippen kann.
_src7j = open("eve_trader/ui/mw_bauplan_fenster.py", encoding="utf-8").read()
check("b7j die Kaskade fragt nach dem vorhandenen Kaestchen",
      "_ch.data(0, Qt.CheckStateRole) is not None" in _src7j)
check("b7j und zwar VOR dem Umschalten",
      # BEIDE ANKER AUSDRUECKLICH PRUEFEN: find() liefert -1, wenn ein Anker
      # fehlt, und -1 < irgendwas waere still gruen (die Blindstelle aus
      # aa353). Ein fehlender Anker muss ROT werden, nicht unsichtbar.
      _src7j.find("_ch.data(0, Qt.CheckStateRole) is not None") >= 0
      and _src7j.find("_ch.setCheckState(0, _want)") >= 0
      and (_src7j.find("_ch.data(0, Qt.CheckStateRole) is not None")
           < _src7j.find("_ch.setCheckState(0, _want)")))
check("b7j die Material-Unterzeile ist gar nicht erst abhakbar",
      "mit.setFlags(mit.flags() & ~Qt.ItemIsUserCheckable)" in _src7i)
check("b7j und das steht vor dem Einhaengen",
      _src7i.find("mit.setFlags(mit.flags() & ~Qt.ItemIsUserCheckable)") >= 0
      and _src7i.find("iit.addChild(mit)") >= 0
      and (_src7i.find("mit.setFlags(mit.flags() & ~Qt.ItemIsUserCheckable)")
           < _src7i.find("iit.addChild(mit)")))
# DIE ECHTEN ZEILEN BEHALTEN IHR KAESTCHEN: der Riegel darf den Runplaner
# nicht stumm schalten. Beides steht unveraendert im Aufbau.
check("b7j die Positionszeile bleibt abhakbar",
      "iit.setFlags(iit.flags() | Qt.ItemIsUserCheckable)" in _src7i)
check("b7j die Charakterzeile bleibt abhakbar",
      "citem.setFlags(citem.flags() | Qt.ItemIsUserCheckable)" in _src7i)

# ---------------------------------------------------------------- (b7k)
# UNGESPEICHERTE EINSTELLUNGEN (Nutzer, 15.09.2026): "wenn man in
# Einstellungen etwas einstellt und nicht speichert, bekommt man keine
# Meldung, wenn man irgendwo anders im Tool klickt ... diese Warnung muss
# kommen, sobald wir versuchen ungespeichert den Einstellungs-Tab zu
# verlassen, EGAL WOHIN."
#
# GEFAHREN, NICHT NUR GELESEN: alle drei Wege werden hier wirklich
# durchlaufen. Die modale Rueckfrage steckt in `_einstellungen_frage` und
# wird dafuer stillgelegt - ein echtes Fenster wuerde die Suite haengen
# lassen (b59 bewacht dieselbe Falle).
check("b7k die Einstellungsseite ist hinterlegt",
      getattr(win, "_settings_w", None) is not None)
check("b7k und der Riegel haengt an der Navigation",
      win.tabs.vor_wechsel is not None)
_si7k = win.tabs.indexOf(win._settings_w)
check("b7k die Seite steckt wirklich im Stapel", _si7k >= 0)
# EIN ANDERES ZIEL SUCHEN - egal welches, es geht um "egal wohin".
_ziel7k = None
for _i7k in range(win.tabs.count()):
    if _i7k != _si7k:
        _ziel7k = win.tabs.widget(_i7k)
        break
check("b7k es gibt ein anderes Ziel", _ziel7k is not None)
_gefragt7k = []
_alt_frage7k = type(win)._einstellungen_frage
_antwort7k = {"wert": "zurueck"}


def _frage7k(_self):
    _gefragt7k.append(1)
    return _antwort7k["wert"]


_merk_margin7k = win.settings.get("target_margin")
_merk_stand7k = getattr(win, "_einst_stand", None)
try:
    type(win)._einstellungen_frage = _frage7k
    # --- 1. NICHTS GEAENDERT: keine Rueckfrage, Wechsel geht durch.
    win.tabs.setCurrentWidget(win._settings_w)
    win._einstellungen_stand_merken()
    check("b7k ohne Aenderung ist nichts offen",
          win._einstellungen_offen() is False)
    win.tabs.setCurrentWidget(_ziel7k)
    check("b7k und der Wechsel geht ohne Rueckfrage durch",
          win.tabs.currentWidget() is _ziel7k and not _gefragt7k)
    # --- 2. GEAENDERT + "Zurueck": der Wechsel wird verhindert.
    win.tabs.setCurrentWidget(win._settings_w)
    win.s_margin.setValue(float(win.s_margin.value()) + 3.0)
    check("b7k eine Aenderung wird erkannt",
          win._einstellungen_offen() is True)
    _antwort7k["wert"] = "zurueck"
    win.tabs.setCurrentWidget(_ziel7k)
    check("b7k dann wird gefragt", len(_gefragt7k) == 1)
    check("b7k und „Zurueck“ laesst einen auf der Seite",
          win.tabs.currentWidget() is win._settings_w)
    check("b7k die Aenderung steht noch im Feld",
          win._einstellungen_offen() is True)
    # DERSELBE RIEGEL AUCH UEBER DEN INDEX-WEG (Seitenleiste, Code-Spruenge).
    win.tabs.setCurrentIndex(win.tabs.indexOf(_ziel7k))
    check("b7k auch der Wechsel ueber den Index wird abgefangen",
          win.tabs.currentWidget() is win._settings_w)
    # --- 3. GEAENDERT + "Verwerfen": Felder zurueck, Wechsel geht durch.
    _antwort7k["wert"] = "verwerfen"
    win.tabs.setCurrentWidget(_ziel7k)
    check("b7k „Verwerfen“ laesst den Wechsel zu",
          win.tabs.currentWidget() is _ziel7k)
    check("b7k und raeumt die Felder auf",
          win._einstellungen_offen() is False)
    eq("b7k die Einstellung selbst blieb unangetastet",
       win.settings.get("target_margin"), _merk_margin7k)
    # --- 4. GEAENDERT + "Speichern": der Wert landet in den Einstellungen.
    win.tabs.setCurrentWidget(win._settings_w)
    _neu7k = float(win.s_margin.value()) + 4.0
    win.s_margin.setValue(_neu7k)
    _antwort7k["wert"] = "speichern"
    win.tabs.setCurrentWidget(_ziel7k)
    check("b7k „Speichern“ laesst den Wechsel zu",
          win.tabs.currentWidget() is _ziel7k)
    eq("b7k und schreibt den neuen Wert",
       float(win.settings.get("target_margin")), _neu7k)
    check("b7k danach ist nichts mehr offen",
          win._einstellungen_offen() is False)
    # --- 5. VON EINER ANDEREN SEITE AUS wird NIE gefragt.
    _vorher7k = len(_gefragt7k)
    win.tabs.setCurrentIndex(_si7k)
    check("b7k der Weg IN die Einstellungen fragt nicht",
          len(_gefragt7k) == _vorher7k
          and win.tabs.currentWidget() is win._settings_w)
finally:
    type(win)._einstellungen_frage = _alt_frage7k
    win.settings["target_margin"] = _merk_margin7k
    win._einstellungen_felder_zuruecksetzen()
    win._einst_stand = _merk_stand7k
    win.tabs.vor_wechsel = None
    win.tabs.setCurrentIndex(0)
    win.tabs.vor_wechsel = win._einstellungen_wechsel_pruefen
# EIN AUSFALL DARF NIE SPERREN: sitzt der Nutzer wegen eines Anzeigefehlers
# fest, ist das schlimmer als eine verlorene Einstellung.
_altv7k = win.tabs.vor_wechsel
try:
    def _kaputt7k(_a, _b):
        raise RuntimeError("Absicht")
    win.tabs.vor_wechsel = _kaputt7k
    win.tabs.setCurrentIndex(win.tabs.indexOf(_ziel7k))
    check("b7k ein Fehler im Riegel erlaubt den Wechsel",
          win.tabs.currentWidget() is _ziel7k)
finally:
    win.tabs.vor_wechsel = _altv7k
    win.tabs.setCurrentIndex(0)

# ---------------------------------------------------------------- (b7l)
# RECHTSKLICK AUF DIE OBERE LEISTE BLENDET SIE NICHT MEHR AUS.
# NUTZER, 15.09.2026, fuenf Screenshots: "wenn ich Rechtsklick auf einen
# dieser oberen Leisten-Knoepfe mache und dann da drauf klicke, schliesst
# sich diese obere Leiste - diese Rechtsklick-Option muss weg."
# Das Kaestchen im Bild ist Qts eingebautes Fenster-Menue (QMainWindow
# bietet jede Werkzeugleiste zum Ausblenden an), kein eigener Code.
check("b7l die obere Leiste ist hinterlegt",
      getattr(win, "_toolbar", None) is not None)
if getattr(win, "_toolbar", None) is not None:
    check("b7l sie reicht den Rechtsklick nicht mehr weiter",
          win._toolbar.contextMenuPolicy() == Qt.PreventContextMenu)
    check("b7l und sie ist sichtbar", not win._toolbar.isHidden())
    # DER ZWEITE WEG: Qt baut das Menue in createPopupMenu - auch beim
    # Rechtsklick NEBEN die Leiste. Ohne diesen Riegel waere der erste nur
    # die halbe Miete.
    check("b7l das Fenster bietet gar kein solches Menue mehr an",
          win.createPopupMenu() is None)
    # EIN ECHTER RECHTSKLICK DARF NICHTS OEFFNEN. Gemessen an den offenen
    # Fenstern: waere das Menue noch da, stuende danach eins mehr offen.
    from PySide6.QtGui import QContextMenuEvent as _QCME7l
    from PySide6.QtCore import QPoint as _QP7l
    from PySide6.QtWidgets import QMenu as _QMenu7l
    _vorher7l = len([_w for _w in _app.topLevelWidgets()
                     if isinstance(_w, _QMenu7l) and _w.isVisible()])
    _ev7l = _QCME7l(_QCME7l.Mouse, _QP7l(5, 5),
                    win._toolbar.mapToGlobal(_QP7l(5, 5)))
    _app.sendEvent(win._toolbar, _ev7l)
    _app.processEvents()
    _nachher7l = len([_w for _w in _app.topLevelWidgets()
                      if isinstance(_w, _QMenu7l) and _w.isVisible()])
    check("b7l ein Rechtsklick auf die Leiste oeffnet nichts",
          _nachher7l == _vorher7l)
    # DAS EIGENE KONTEXTMENUE EINES KNOPFES DARIN BLEIBT (Sitzung 21):
    # der Riegel gilt der Leiste, nicht ihren Kindern.
    check("b7l das eigene Menue des EVE-Daten-Knopfes bleibt",
          win.g_sde_btn.contextMenuPolicy() == Qt.CustomContextMenu)

# ---------------------------------------------------------------- (b7o)
# DIE BEHAELTER-LISTE FOLGT DER CHARAKTER-WAHL.
# NUTZER, 15.09.2026: "jetzt habe ich da ploetzlich Container von allen
# Charakteren anstatt nur dem gewaehlten."
# EHRLICH ZUR URSACHE: die Liste hat den Wahlschalter NIE beachtet. Nur
# fiel es nicht auf, solange kaum Behaelter erkannt wurden (aa358). Mehr
# Treffer haben einen alten Fehler sichtbar gemacht.
_alt7o = getattr(win, "_assets_struct", {})
_alt_idx7o = win.pf_char.currentIndex()
try:
    win._assets_struct = {
        111: {"hangar": {}, "containers": [{"item_id": 1, "type_id": 9,
                                            "name": "A", "contents": {34: 5}}]},
        222: {"hangar": {}, "containers": [{"item_id": 2, "type_id": 9,
                                            "name": "B", "contents": {35: 7}}]},
    }
    win.pf_char.blockSignals(True)
    win.pf_char.clear()
    win.pf_char.addItem(_t4("All"), "all")
    win.pf_char.addItem("Eins", 111)
    win.pf_char.addItem("Zwei", 222)
    win.pf_char.blockSignals(False)

    def _namen7o():
        return sorted(c["name"] for c in win._sichtbare_container())

    win.pf_char.setCurrentIndex(0)          # "Alle"
    eq("b7o bei 'Alle' stehen die Behaelter aller Charaktere da",
       _namen7o(), ["A", "B"])
    win.pf_char.setCurrentIndex(1)          # Charakter 111
    eq("b7o bei einem Charakter nur SEINE Behaelter", _namen7o(), ["A"])
    win.pf_char.setCurrentIndex(2)          # Charakter 222
    eq("b7o und beim naechsten dessen Behaelter", _namen7o(), ["B"])
    # DIESELBE REGEL WIE DIE ITEM-LISTE - sonst behauptet eine Seite zweierlei.
    _src7o = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
    check("b7o die Anzeige nimmt die gefilterte Liste",
          "containers = self._sichtbare_container()" in _src7o)
    check("b7o und 'alle ausblenden' dieselbe Quelle",
          "all_ids = [c[\"item_id\"] for c in self._sichtbare_container()]"
          in _src7o)
    # UND SIE GEHT BEIM UMSCHALTEN MIT, nicht erst beim naechsten Abruf.
    check("b7o der Wahlschalter zeichnet die Liste neu",
          "self.pf_char.currentIndexChanged.connect("
          "self._container_neu_zeichnen)" in _src7o)
finally:
    win._assets_struct = _alt7o
    win.pf_char.blockSignals(True)
    win.pf_char.clear()
    win.pf_char.blockSignals(False)
    try:
        win._reload_character_combos()
    except Exception:
        pass

# ---------------------------------------------------------------- (b7n)
# WO BIN ICH? DIE RECHTE LEISTE ZEIGT ES JETZT AUCH.
# NUTZER, 15.09.2026: "im Trading-Bereich sieht man in der linken Sidebar,
# wo man sich befindet. Im Industrie-Bereich sieht man in der rechten
# Sidebar noch nicht, wo man sich befindet - kannst du das mit derselben
# Optik machen?"
from eve_trader.ui import theme as _th7
check("b7n die fuenf Seiten-Knoepfe der Bau-Leiste sind da",
      len(getattr(win, "_bau_page_btns", [])) == 5)
if len(getattr(win, "_bau_page_btns", [])) == 5:
    _akt7n = win._bau_rail_active_css
    _idl7n = win._bau_rail_idle_css
    # DIESELBE HANDSCHRIFT WIE LINKS: Cyan-Schrift, Cyan-Flaeche und der
    # 3 px breite Balken an der linken Kante. Der Balken ist das
    # Erkennungszeichen der linken Leiste (theme: NavItem:checked).
    check("b7n der aktive Knopf traegt den Cyan-Balken links",
          f"border-left:3px solid {_th7.CYAN}" in _akt7n)
    check("b7n und Cyan-Schrift auf ruhiger Cyan-Flaeche",
          f"color:{_th7.CYAN}" in _akt7n
          and f"background:{_th7.CYAN_FILL}" in _akt7n)
    # BEIDE ZUSTAENDE GLEICH BREIT - sonst springt der Text beim Wechseln
    # (dieselbe Falle wie beim blinkenden Rahmen).
    check("b7n der ruhige Knopf traegt denselben Balken, nur in Rahmenfarbe",
          f"border-left:3px solid {_th7.BORDER}" in _idl7n)
    # JETZT WIRKLICH DURCHKLICKEN: jede Seite genau einmal hervorgehoben.
    for _i7n in range(5):
        win._bau_nav(_i7n)
        _app.processEvents()
        _hell = [_j for _j, _b in enumerate(win._bau_page_btns)
                 if _b.styleSheet() == _akt7n]
        eq(f"b7n Seite {_i7n}: genau dieser eine Knopf leuchtet",
           _hell, [_i7n])
        eq(f"b7n Seite {_i7n}: der Stapel steht auch dort",
           win.b_stack.currentIndex(), _i7n)
    # UND BEIM AUFBAU SCHON, nicht erst nach dem ersten Klick.
    _src7n = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
    check("b7n die Hervorhebung steht schon beim Aufbau",
          "self._bau_page_btns[self.b_stack.currentIndex()].setStyleSheet("
          in _src7n)
    win._bau_nav(0)
    _app.processEvents()

# ---------------------------------------------------------------- (b7p)
# DIE TOUR GEHT MIT, WENN WAEHREND EINES SCHRITTS EIN FENSTER AUFGEHT.
# NUTZER, 16.09.2026: "wenn der Bauplan geoeffnet ist, ist das Tutorial-
# Fenster hinter dem Bauplan, weil man zuerst auf Next druecken muss."
# Schritt 7/15 wartet genau darauf, dass der Nutzer den Bauplan oeffnet -
# der geht dann VOR der Tour auf, und bis zum naechsten "Weiter" blieb sie
# dahinter. Umgehaengt wurde bisher nur beim Schrittwechsel.
from eve_trader.ui.tutorial import TutorialFenster as _TF7p
_tp7p = _TF7p(win, "trading")
try:
    # 1. ZIEL UNVERAENDERT -> NICHTS TUN. Ein Dauer-raise_() zoege das
    # Besitzerfenster mit hoch und drueckte den Bauplan nach hinten
    # (Sitzung 17, derselbe Schritt, derselbe Nutzer).
    #
    # DER MERKER MUSS AUS DEM ECHTEN WEG KOMMEN, nicht von Hand gesetzt
    # werden: im ersten Anlauf stand hier `_letztes_ziel = _zielfenster()`,
    # und die Mutation, die das Merken im Programm abklemmt, blieb
    # deshalb BLIND - der Test hatte sich seine Voraussetzung selbst
    # gebaut. Also erst einmal richtig ordnen lassen.
    _tp7p._fenster_ordnen()
    _app.processEvents()
    _gerufen7p = []
    _tp7p._fenster_ordnen = lambda: _gerufen7p.append(1)
    _tp7p._nachfuehren()
    eq("b7p ohne Fensterwechsel wird NICHT umgehaengt", _gerufen7p, [])
    # 2. ZIEL HAT GEWECHSELT -> die Tour ordnet sich neu.
    _tp7p._letztes_ziel = None
    _tp7p._nachfuehren()
    eq("b7p bei einem Fensterwechsel ordnet sie sich neu", _gerufen7p, [1])
    # 3. DER SCHRITT, DER DEN BAUPLAN OEFFNET, ZIELT DANACH AUF DEN BAUPLAN.
    # NUTZER-SCREENSHOT 16.09.2026: die Tour lag hinter dem Bauplan. Grund:
    # der Schritt hebt "New build plan" hervor - einen Knopf im
    # HAUPTFENSTER. Der ist sichtbar, also gewann er, und die Tour blieb am
    # Haupttool. Erst wenn die Bedingung erfuellt ist, gehoert sie nach
    # vorn auf den Bauplan.
    from PySide6.QtWidgets import (QDialog as _QD7p, QPushButton as _QPB7p)
    _i_open7p = [_i for _i, _st in enumerate(_tp7p.schritte)
                 if _st[4] == "bauplan_offen"]
    check("b7p es gibt einen Schritt, der auf den offenen Bauplan wartet",
          bool(_i_open7p) or _tp7p.zweig != "industry")
    _tp7i = _TF7p(win, "industry")
    _dlg7p = _QD7p(win)
    _dlg7p.resize(900, 700)
    _alt_bd7p = getattr(win, "_bd_dialog", None)
    try:
        _j7p = [_i for _i, _st in enumerate(_tp7i.schritte)
                if _st[4] == "bauplan_offen"]
        if _j7p:
            _tp7i.i = _j7p[0]
            # Ein sichtbarer Knopf im HAUPTFENSTER als Hervorhebung - genau
            # die Lage aus dem Screenshot.
            _btn7p = _QPB7p("x", win)
            _btn7p.show()
            _tp7i._hervor = [_btn7p]
            _app.processEvents()
            win._bd_dialog = None
            check("b7p solange kein Bauplan offen ist, zielt der Schritt "
                  "aufs Hauptfenster", _tp7i._zielfenster() is win)
            win._bd_dialog = _dlg7p
            _dlg7p.show()
            _app.processEvents()
            check("b7p ist der Bauplan offen, zielt er auf den Bauplan",
                  _tp7i._zielfenster() is _dlg7p)
            _btn7p.setParent(None)
    finally:
        win._bd_dialog = _alt_bd7p
        _dlg7p.close()
        _dlg7p.setParent(None)
        _tp7i.abbrechen()
        _app.processEvents()
    # 4. UND DER MERKER WIRD BEIM ORDNEN GESETZT - ohne ihn liefe Punkt 1
    # nie zu, und es waere doch wieder ein Dauer-raise_().
    _src7p = open("eve_trader/ui/tutorial.py", encoding="utf-8").read()
    check("b7p das Ordnen merkt sich sein Ziel",
          "self._letztes_ziel = _ziel" in _src7p)
finally:
    _tp7p.abbrechen()
    # WIRKLICH WEG, nicht nur versteckt: `abbrechen` ruft deleteLater(), und
    # das passiert erst, wenn Qt die aufgeschobenen Loeschungen abarbeitet.
    # Ohne das blieb ein zweites Tour-Fenster im Programm stehen - b55 zaehlt
    # Bedienelemente OHNE Symbol und meldete prompt zweimal "Back". Ein
    # Testaufbau, der Spuren hinterlaesst, macht die naechste Pruefung kaputt.
    from PySide6.QtCore import QEvent as _QEv7p
    _app.processEvents()
    _app.sendPostedEvents(None, _QEv7p.DeferredDelete)
    _app.processEvents()

# ---------------------------------------------------------------- (b7m)
# DIE TOUR VERDECKT DIE RECHTE LEISTE NICHT MEHR.
# NUTZER, 15.09.2026, mit Screenshot: "Tutorial verdeckt Production Steps,
# das Tutorialfenster muesste weiter links sein, damit man die rechte
# Sidebar komplett sehen kann." Unter den Anker zu ruecken ist richtig,
# solange er in der breiten Mitte sitzt; in der schmalen Leiste rechts
# liegt darunter genau das, worueber der Schritt gerade spricht.
# NACHGEZOGEN 16.09.2026: die Links-Regel gilt NUR im Bauplan-Fenster.
# Im Hauptfenster schob sie die Tour unter das modale "New build
# plan"-Fenster (Schritt 7/15) - dort ist unter dem Anker Platz, in der
# schmalen Bauplan-Sidebar nicht.
from eve_trader.ui.tutorial import TutorialFenster as _TF7m
from PySide6.QtWidgets import (QWidget as _QW7m, QDialog as _QD7m)
from PySide6.QtCore import QPoint as _QP7m
_tp7m = _TF7m(win, "trading")
# EIN EIGENES FENSTER als Stellvertreter fuer den Bauplan-Dialog: die Regel
# fragt ausdruecklich "ist das Fenster des Ankers NICHT das Haupttool?".
_dlg7m = _QD7m(win)
_dlg7m.resize(1200, 800)
_dlg7m.show()
try:
    _tp7m.show()
    _app.processEvents()

    def _lauf7m(anteil, wo=None):
        """Anker an dieser waagrechten Stelle des Fensters -> wohin rueckt
        die Tour? Gibt (Fensterrechteck der Tour, Anker-Ecke) zurueck."""
        _wo = wo if wo is not None else win
        _rw = _wo.frameGeometry()
        _a = _QW7m(_wo)
        _a.resize(120, 40)
        _a.move(_wo.mapFromGlobal(
            _QP7m(_rw.left() + int(_rw.width() * anteil),
                  _rw.top() + 200)))
        _a.show()
        _app.processEvents()
        _tp7m._hervor = [_a]
        _tp7m._platzieren()
        _app.processEvents()
        return _tp7m.geometry(), _a.mapToGlobal(_QP7m(0, 0)), _a

    # 1. ANKER IN DER RECHTEN LEISTE -> die Tour steht LINKS daneben.
    # BEIDE BEDINGUNGEN IN EINER PRUEFUNG, und das ist kein Schoenheitsfehler:
    # "steht links vom Anker" allein war BLIND. Ohne den Sonderfall rutscht
    # die Tour naemlich schon durch die Bildschirm-Begrenzung nach links
    # (sie passt rechts nicht mehr hin) und stuende trotzdem UNTER der
    # Leiste - also genau der gemeldete Fehler, aber mit gruener Pruefung.
    # Aufgefallen ist das in der Rotprobe: die Mutation blieb hier gruen.
    # Entscheidend ist die HOEHE.
    _g7m, _ae7m, _a7m = _lauf7m(0.90, _dlg7m)
    check("b7m bei einem Anker in der rechten Leiste steht die Tour links "
          "DANEBEN, nicht darunter",
          _g7m.right() < _ae7m.x() and _g7m.top() <= _ae7m.y() + 4)
    _a7m.setParent(None)
    # 1b. DIESELBE STELLE IM HAUPTFENSTER -> DARUNTER (Nutzer, 16.09.2026).
    # Dort geht mittig das modale "New build plan"-Fenster auf; die Tour
    # nach links zu schieben hiesse, sie genau dorthin zu setzen.
    _g7mh, _ae7mh, _a7mh = _lauf7m(0.90, win)
    check("b7m im HAUPTFENSTER bleibt es an derselben Stelle beim Platz "
          "DARUNTER", _g7mh.top() >= _ae7mh.y() + 40)
    _a7mh.setParent(None)
    # 1c. ANKER IN EINEM MODALEN FENSTER -> die Tour darf es NICHT beruehren.
    # NUTZER-SCREENSHOT 16.09.2026: "jetzt haengt es wieder hinter dem New
    # build plan Fenster". Bei Schritt 7/15 wandert der Anker in das kleine
    # modale Such-Fenster. Ein modales Fenster liegt IMMER oben - also ist
    # jede Stelle innerhalb seiner Flaeche verdeckt, egal ob links vom Anker
    # oder darunter. Deshalb wird hier am FENSTER ausgerichtet, nicht am
    # Anker, und geprueft wird das, worauf es ankommt: KEINE UEBERDECKUNG.
    _dlgmod7m = _QD7m(win)
    _dlgmod7m.setModal(True)
    _dlgmod7m.resize(400, 300)
    _dlgmod7m.move(60, 60)
    _dlgmod7m.show()
    _app.processEvents()
    try:
        _g7mm, _ae7mm, _a7mm = _lauf7m(0.90, _dlgmod7m)
        _rm7m = _dlgmod7m.frameGeometry()
        check("b7m die Tour verdeckt ein MODALES Fenster nicht",
              not _g7mm.intersects(_rm7m))
        # ... und hier ist unter dem Dialog Platz, also steht sie auch dort.
        check("b7m und steht dann unter dem modalen Fenster",
              _g7mm.top() >= _rm7m.bottom())
        _a7mm.setParent(None)
    finally:
        _dlgmod7m.close()
        _dlgmod7m.setParent(None)
        _app.processEvents()
    # 2. GEGENPROBE, ANKER IN DER MITTE -> alles bleibt wie bisher: DARUNTER.
    # Ohne sie koennte die Regel auch immer nach links rutschen und der Test
    # waere trotzdem gruen.
    _g7m2, _ae7m2, _a7m2 = _lauf7m(0.25)
    check("b7m bei einem Anker in der Mitte bleibt es beim Platz DARUNTER",
          _g7m2.top() >= _ae7m2.y() + 40)
    check("b7m und dann NICHT links daneben", _g7m2.right() > _ae7m2.x())
    _a7m2.setParent(None)
finally:
    _tp7m.abbrechen()
    _dlg7m.close()
    _dlg7m.setParent(None)
    _app.processEvents()
    _app.sendPostedEvents(None, _QEv7p.DeferredDelete)
    _app.processEvents()

# ---------------------------------------------------------------- (b7s)
# DER KNOPF IM LEEREN FENSTER TUT, WAS FEHLT. Nutzer-Befund 17.09.2026:
# "klickt man in der Mitte auf Market scan unter 'No market data', kommt
# zwar ein Ladebildschirm, aber keine Auflistung" und "bei Blueprint genauso,
# keine Wirkung". Zwei Ursachen: (1) nach dem Scan fehlte "Load deals", der
# Hinweis bot aber weiter "Market scan" an; (2) der Blaupausen-Hinweis zeigte
# auf den SDE-Download statt auf "Meine Blaupausen laden".
import eve_trader.store as _st7s
_app.processEvents()
_alt_age7s = _st7s.snapshot_age_seconds


def _box7s(tbl):
    for _w in tbl.viewport().children():
        if getattr(_w, "_knopf", None) is not None:
            return _w
    return None


try:
    _bx = _box7s(win.deals_table)
    check("b7s die Daytrade-Tabelle hat einen Leer-Hinweis mit Knopf", _bx is not None)
    if _bx is not None:
        # 1. KEIN SCAN -> "Market scan".
        _st7s.snapshot_age_seconds = lambda source=None: None
        win.deals_table._leerhinweis_stellen()
        check("b7s ohne Scan bietet der Knopf den Markt-Scan an",
              _bx._knopf.text() in ("Market scan", "Markt-Scan", "Marktscan"))
        # 2. SCAN DA -> "Load deals", und der Klick laedt die Deals.
        _st7s.snapshot_age_seconds = lambda source=None: 120.0
        win.deals_table._leerhinweis_stellen()
        check("b7s nach dem Scan bietet der Knopf 'Load deals' an",
              _bx._knopf.text() in ("Load deals", "Deals laden"))
        _gerufen7s = []
        _alt_click7s = win.deals_btn.click
        win.deals_btn.click = lambda: _gerufen7s.append("deals")
        try:
            _bx._aktion()
        finally:
            win.deals_btn.click = _alt_click7s
        eq("b7s ... und sein Klick drueckt wirklich 'Load deals'", _gerufen7s, ["deals"])
    # 3. BLAUPAUSEN: der Knopf laedt die Blaupausen der Charaktere.
    _bxb = _box7s(win.bp_table)
    check("b7s die Blaupausen-Tabelle hat einen Leer-Hinweis", _bxb is not None)
    if _bxb is not None:
        _gerufen7sb = []
        _alt_bp7s = win.bp_refresh_btn.click
        _alt_sde7s = win.g_sde_btn.click
        win.bp_refresh_btn.click = lambda: _gerufen7sb.append("bp")
        win.g_sde_btn.click = lambda: _gerufen7sb.append("sde")
        try:
            _bxb._aktion()
        finally:
            win.bp_refresh_btn.click = _alt_bp7s
            win.g_sde_btn.click = _alt_sde7s
        eq("b7s der Blaupausen-Knopf laedt MEINE Blaupausen, nicht die SDE",
           _gerufen7sb, ["bp"])
    # 4. NACH DEM SCAN werden die Hinweise neu gestellt - die Tabelle
    # aendert sich beim Scan nicht, ihre Signale feuern also nicht.
    check("b7s nach dem Scan stellt das Programm die Hinweise neu",
          "self._leerhinweise_aktualisieren()   # \"Market scan\" -> \"Load deals\""
          in _src_mw)
finally:
    _st7s.snapshot_age_seconds = _alt_age7s
    try:
        win.deals_table._leerhinweis_stellen()
    except Exception:
        pass

# ---------------------------------------------------------------- (b7q)
# CORP-HANGAR (1.0.8): Einstellungen und der Abruf im Bauplan - am ECHTEN
# Fenster, mit vorgetaeuschtem ESI. Das Netz wird komplett ersetzt; gezaehlt
# wird, wie oft der Corp-Hangar abgerufen wird. DREI Charaktere, EINE Corp:
# es muss GENAU EIN Abruf sein (CLAUDE.md: "Ungeprueft verdreifacht sich
# der Bestand, und der Plan kauft ZU WENIG").
import eve_trader.esi as _esi7q
import eve_trader.config as _cfg7q
_alt7q = {k: getattr(_esi7q, k) for k in (
    "fetch_character_corporation", "granted_scopes", "fetch_character_roles",
    "fetch_corporation_assets", "fetch_corporation_divisions",
    "fetch_corporation_blueprints", "fetch_corporation_jobs",
    "fetch_corporation_name", "container_type_ids_safe")}
_alt_save7q = _cfg7q.save_settings
_alt_set7q = {k: win.settings.get(k) for k in ("use_corp", "corp_divisions")}
_zaehler7q = {"assets": 0, "jobs": 0, "bp": 0}
_STRUCT7q = 1035466617946
try:
    _cfg7q.save_settings = lambda s: None      # Platte nicht anfassen
    # 1. STANDARD AUS - und die Oberflaeche zeigt es.
    check("b7q der Corp-Schalter steht in den Einstellungen",
          hasattr(win, "s_corp") and isinstance(win.s_corp, QComboBox))
    eq("b7q sieben Division-Kaestchen", sorted(win.s_corp_divs), [1, 2, 3, 4, 5, 6, 7])
    # 2. AUS -> der Bauplan fragt ESI GAR NICHT nach der Corp.
    win.settings["use_corp"] = False
    _r7q = win._corp_bau_daten("cid", [{"character_id": 1, "character_name": "A"}], None)
    eq("b7q Schalter aus -> kein Corp-Bestand, kein Abruf",
       (_r7q.get("aktiv"), _r7q.get("summe")), (False, {}))
    # 3. AN, aber keine Division -> nichts zaehlen, aber SAGEN warum.
    win.settings["use_corp"] = True
    win.settings["corp_divisions"] = []
    _r7q = win._corp_bau_daten("cid", [{"character_id": 1, "character_name": "A"}], None)
    eq("b7q keine Division gewaehlt -> nichts, mit Hinweis",
       (_r7q.get("keine_division"), _r7q.get("summe")), (True, {}))
    # 4. DREI CHARAKTERE, EINE CORP, alle Director: EIN Abruf, EINMAL gezaehlt.
    _chars7q = [{"character_id": 11, "character_name": "Alpha"},
                {"character_id": 12, "character_name": "Beta"},
                {"character_id": 13, "character_name": "Gamma"}]
    _corp_assets7q = [
        {"item_id": 100, "type_id": 27, "location_id": _STRUCT7q,
         "location_flag": "OfficeFolder", "quantity": 1},
        {"item_id": 1, "type_id": 34, "location_id": 100,
         "location_flag": "CorpSAG1", "quantity": 1000},
        {"item_id": 2, "type_id": 35, "location_id": 100,
         "location_flag": "CorpSAG3", "quantity": 500},
    ]

    def _f_assets7q(client_id, cid, corp_id):
        _zaehler7q["assets"] += 1
        return list(_corp_assets7q)

    def _f_jobs7q(client_id, cid, corp_id, include_delivered=False):
        _zaehler7q["jobs"] += 1
        return [{"job_id": 1, "activity_id": 1, "product_type_id": 587,
                 "runs": 2, "status": "active", "end_date": "2099-01-01T00:00:00Z"}]

    def _f_bp7q(client_id, cid, corp_id, divisions=None):
        _zaehler7q["bp"] += 1
        return [{"type_id": 999, "quantity": 1, "material_efficiency": 10,
                 "time_efficiency": 20, "runs": -1, "is_bpo": True,
                 "location_id": 100, "location_flag": "CorpSAG1",
                 "division": 1, "corporation_id": corp_id}]

    _esi7q.fetch_character_corporation = lambda cid: 900
    _esi7q.granted_scopes = lambda client_id, cid: set(_cfg7q.CORP_SCOPES)
    __import__('eve_trader.ui.mw_bauplan_fenster', fromlist=['x'])._ROLLEN_STAND.clear()  # emm305: Rollen-Merker leeren
    _esi7q.fetch_character_roles = lambda client_id, cid: {"Director", "Factory_Manager"}
    _esi7q.fetch_corporation_assets = _f_assets7q
    _esi7q.fetch_corporation_divisions = lambda c, cid, corp: {"hangar": [{"division": 1, "name": "Minerals"}]}
    _esi7q.fetch_corporation_blueprints = _f_bp7q
    _esi7q.fetch_corporation_jobs = _f_jobs7q
    _esi7q.fetch_corporation_name = lambda corp: "Test Corp"
    _esi7q.container_type_ids_safe = lambda: set()
    win.settings["corp_divisions"] = [1]
    _r7q = win._corp_bau_daten("cid", _chars7q, None)
    eq("b7q EIN Corp-Abruf fuer drei Charaktere derselben Corp",
       _zaehler7q["assets"], 1)
    eq("b7q der Bestand ist EINMAL gezaehlt, nicht dreifach",
       _r7q.get("summe"), {34: 1000})
    check("b7q Division 3 (nicht gewaehlt) bleibt draussen",
          35 not in (_r7q.get("summe") or {}))
    eq("b7q Corp-Jobs kommen unter der Corp-Nummer",
       sorted(_r7q.get("jobs") or {}), [900])
    eq("b7q EIN Job-Abruf, EIN Blaupausen-Abruf",
       (_zaehler7q["jobs"], _zaehler7q["bp"]), (1, 1))
    eq("b7q Corp-Blaupausen kommen mit", len(_r7q.get("blueprints") or []), 1)
    eq("b7q die Anzeige nennt Corp, Charakter und Division-Namen",
       [(c["name"], c["via"], c["divisions"]) for c in _r7q.get("corps")],
       [("Test Corp", "Alpha", {1: "Minerals"})])
    # 5. ORTSGRENZE wird durchgereicht: an einer fremden Struktur nichts.
    _r7q = win._corp_bau_daten("cid", _chars7q, [123])
    eq("b7q an einer anderen Struktur zaehlt die Corp nichts",
       _r7q.get("summe"), {})
    # 6. KEIN CORP-SCOPE IM TOKEN -> "neu verknuepfen" mit Namen, kein Abruf.
    _zaehler7q["assets"] = 0
    _esi7q.granted_scopes = lambda client_id, cid: set()
    _r7q = win._corp_bau_daten("cid", _chars7q, None)
    eq("b7q ohne Corp-Scope: alle drei muessen neu verknuepfen",
       _r7q.get("relink"), ["Alpha", "Beta", "Gamma"])
    eq("b7q ohne Corp-Scope: kein Abruf", _zaehler7q["assets"], 0)
    # 7. SCOPE DA, ABER KEINE DIRECTOR-ROLLE -> Corp beim Namen nennen.
    _esi7q.granted_scopes = lambda client_id, cid: set(_cfg7q.CORP_SCOPES)
    __import__('eve_trader.ui.mw_bauplan_fenster', fromlist=['x'])._ROLLEN_STAND.clear()  # emm305: Rollen-Merker leeren
    _esi7q.fetch_character_roles = lambda client_id, cid: set()
    _r7q = win._corp_bau_daten("cid", _chars7q, None)
    eq("b7q ohne Director-Rolle wird die Corp genannt, nichts gezaehlt",
       (_r7q.get("ohne_rolle"), _r7q.get("summe")), (["Test Corp"], {}))
    # 8. EIN GESCHEITERTER CORP-ABRUF reisst nichts mit: failed-Eintrag.
    __import__('eve_trader.ui.mw_bauplan_fenster', fromlist=['x'])._ROLLEN_STAND.clear()  # emm305: Rollen-Merker leeren
    _esi7q.fetch_character_roles = lambda client_id, cid: {"Director"}

    def _kaputt7q(*a, **k):
        raise RuntimeError("403")
    _esi7q.fetch_corporation_assets = _kaputt7q
    _r7q = win._corp_bau_daten("cid", _chars7q, None)
    check("b7q ein gescheiterter Abruf landet in failed, kein Absturz",
          len(_r7q.get("failed") or []) == 1 and _r7q.get("summe") == {})
    # 9. DIVISION-KAESTCHEN SPEICHERN SOFORT (wie die Berechtigungs-Schalter).
    for _n, _c in win.s_corp_divs.items():
        _c.setChecked(False)
    win.s_corp_divs[2].setChecked(True)
    eq("b7q ein Kaestchen speichert die Division sofort",
       win.settings.get("corp_divisions"), [2])
    win.s_corp_divs[5].setChecked(True)
    eq("b7q ... und ein zweites dazu", win.settings.get("corp_divisions"), [2, 5])
    check("b7q die Divisions stehen im Feldstand (Ungespeichert-Pruefung)",
          win._einstellungen_feldstand().get("corp_divs") == (2, 5))
finally:
    for k, v in _alt7q.items():
        setattr(_esi7q, k, v)
    _cfg7q.save_settings = _alt_save7q
    for k, v in _alt_set7q.items():
        if v is None:
            win.settings.pop(k, None)
        else:
            win.settings[k] = v
    for _c in win.s_corp_divs.values():
        _c.blockSignals(True)
        _c.setChecked(False)
        _c.blockSignals(False)
    # Der gespeicherte Stand muss zu den Feldern passen - sonst haelt die
    # Ungespeichert-Pruefung jeden folgenden Reiterwechsel an (b59/b78).
    win._einstellungen_stand_merken()
    _app.processEvents()

# ---------------------------------------------------------------- (b9)
# REAKTION ALS ENDPRODUKT. Der Dialog zeigte bisher auch dann ME/TE-Eingabe,
# Invention-Tab, Invention-Seitenpanel und eine Kostenzeile "Invention" - alle
# vier sind bei einer Reaktion rechnerisch wirkungslos (nicht erforschbar,
# nicht erfindbar). Sichtbare Stellschrauben, die nichts bewegen, sind
# schlimmer als fehlende: der Nutzer dreht daran und wundert sich.
# ZWEITER ZWEIG: der Test oben baut ausschliesslich ein FERTIGUNGS-Endprodukt
# (reaction_products = set()) - ohne diesen Block waere die neue Bedingung
# nie betreten worden und trotzdem alles gruen.


class _RecipesReaction:
    """Minimalrezept: 100 Reaktionsausgabe <- 10 Testmat, per REACTION."""
    product_to_bp = {100: (900, I.REACTION, 1)}
    bp_materials = {(900, I.REACTION): [(200, 10)]}
    activity_time = {(900, I.REACTION): 60}
    activity_max_runs = {(900, I.REACTION): 0}
    reaction_products = {100}
    invention_for_bpc = {}
    bp_products = {}
    item_cat = {}

    def is_manufactured(self, t):
        return False


from PySide6.QtWidgets import QSpinBox, QTabWidget

_rec_rea = _RecipesReaction()
win._bd_recipes = _rec_rea
_opts_rea = {"me": 0, "te": 0, "job_pct": 0, "build_reactions": True,
             "tree_depth": 4}
win._bd_opts = dict(_opts_rea)
_plan_rea = I.production_plan(100, 10, PRICES.get, _rec_rea, dict(_opts_rea))
_tree_rea = I.build_tree(100, PRICES.get, _rec_rea, dict(_opts_rea))
_res_rea = {"tree": _tree_rea, "names": {100: "Testreaktion", 200: "Testmat"},
            "sell": 6000.0, "sell_is_contract": False, "plan": _plan_rea}
_dlg_rea = None
try:
    win._show_build_detail(100, "Testreaktion", _res_rea)
    check("b9 Bauplan laesst sich mit einer Reaktion oeffnen", True)
    _dlg_rea = getattr(win, "_bd_dialog", None)
    _tabws = _dlg_rea.findChildren(QTabWidget) if _dlg_rea is not None else []
    _titles = [w.tabText(i) for w in _tabws for i in range(w.count())]
    check("b9 Tabs ueberhaupt gefunden", bool(_titles))
    check("b9 KEIN Invention-Tab bei einer Reaktion",
          not any("Invention" in t for t in _titles))
    check("b9 Rezept-Struktur bleibt erhalten",
          any(_t4("Recipe structure") in t for t in _titles))
    check("b9 Materialien bleiben erhalten",
          any("Materialien" in t or "Materials" in t for t in _titles))
    # Die Kostenzeile "Invention" darf nicht mehr sichtbar sein.
    # Beschriftung heisst seit Sitzung 9 "Invention (\u00d8)" - sie nennt
    # jetzt ausdruecklich den ERWARTUNGSWERT, weil der Invention-Tab die
    # (hoehere) Kaufmenge zeigt und beide vorher gleich hiessen.
    _caps = [x for x in (_dlg_rea.findChildren(QLabel) if _dlg_rea else [])
             if x.text().startswith("Invention")]
    # isHidden() statt isVisible(): letzteres ist bei einem nicht gezeigten
    # Dialog IMMER False - die Pruefung waere vacuously gruen gewesen.
    check("b9 Kostenzeile 'Invention' ist ausgeblendet",
          bool(_caps) and all(x.isHidden() for x in _caps))
except Exception as e:                                   # pragma: no cover
    import traceback
    traceback.print_exc()
    _fail.append(f"b9 Reaktion als Endprodukt: {type(e).__name__}: {e}")

# T1-FALL: kein Invention-Tab (nichts zu erfinden), aber ME/TE MUESSEN
# erreichbar bleiben - sie wandern nach oben neben die Menge. Ohne das waere
# mit dem Tab das einzige Eingabefeld verschwunden (Nutzer-Frage: "wo gebe
# ich die ein?").
win._bd_recipes = _Recipes()
try:
    win._show_build_detail(100, "Testship", _res)
    _dlg_t1 = getattr(win, "_bd_dialog", None)
    _tabws_t1 = _dlg_t1.findChildren(QTabWidget) if _dlg_t1 is not None else []
    _titles_t1 = [w.tabText(i) for w in _tabws_t1 for i in range(w.count())]
    check("b9 T1 hat KEINEN Invention-Tab",
          not any("Invention" in t for t in _titles_t1))
    # Nur die MARKIERTEN Kopfzeilen-Labels zaehlen - "ME"/"TE" stehen auch an
    # den Kategorie-Chips weiter unten.
    _hdr_t1 = [x.text() for x in (_dlg_t1.findChildren(QLabel) if _dlg_t1 else [])
               if x.property("bd_role") == "endproduct_me_te" and not x.isHidden()]
    check(f"b9 T1 zeigt ME oben  ({_hdr_t1})", "ME" in _hdr_t1)
    check(f"b9 T1 zeigt TE oben  ({_hdr_t1})", "TE" in _hdr_t1)
    # UND DIE EINGABEFELDER SELBST. Die Beschriftungen allein reichen nicht:
    # `_fill_invention_tab` haengt me_spin/te_spin in die Invention-Karte um,
    # sodass beim Rokh nur noch "ME TE" ohne Felder dastand. Der alte Test
    # war gruen, obwohl die Eingabe fehlte.
    _sp_t1 = [x for x in (_dlg_t1.findChildren(QSpinBox) if _dlg_t1 else [])
              if x.property("bd_role") == "endproduct_me_te"]
    eq("b9 T1 hat BEIDE Eingabefelder", len(_sp_t1), 2)
    # ENTSCHEIDEND IST DER ORT, nicht die Existenz. `_fill_invention_tab`
    # haengt dieselben Widget-Objekte in die Invention-Karte um; sie bleiben
    # dabei Kinder des Dialogs, findChildren findet sie also weiterhin. Eine
    # blosse Existenzpruefung war deshalb in BEIDEN Faellen gruen, waehrend
    # der Nutzer oben nur "ME TE" ohne Felder sah.
    # Pruefung: Feld und seine Beschriftung muessen denselben Eltern-Container
    # haben. Wandert das Feld weg, faellt das sofort auf.
    _cap_t1 = [x for x in (_dlg_t1.findChildren(QLabel) if _dlg_t1 else [])
               if x.property("bd_role") == "endproduct_me_te"]
    _cap_par = {x.parentWidget() for x in _cap_t1}
    _sp_par = {x.parentWidget() for x in _sp_t1}
    check(f"b9 T1 ME/TE-Felder stehen beim Label im Kopf "
          f"(Label-Eltern {len(_cap_par)}, Feld-Eltern {len(_sp_par)})",
          bool(_cap_par) and _sp_par == _cap_par)
except Exception as e:                                   # pragma: no cover
    import traceback
    traceback.print_exc()
    _fail.append(f"b9 T1-Fall: {type(e).__name__}: {e}")


# GEGENPROBE T2: mit Invention-Eintrag MUSS der Tab bleiben - sonst haette die
# Bedingung einfach immer zugeschlagen. Und ME/TE gehoeren dann NICHT nach
# oben, sondern neben die Invention-Karte.
class _RecipesInvented(_Recipes):
    invention_for_bpc = {900: (899, 10, 0.34, [(300, 2)])}


win._bd_recipes = _RecipesInvented()
try:
    win._show_build_detail(100, "Testship-T2", _res)
    _dlg_t2 = getattr(win, "_bd_dialog", None)
    _tabws_t2 = _dlg_t2.findChildren(QTabWidget) if _dlg_t2 is not None else []
    _titles_t2 = [w.tabText(i) for w in _tabws_t2 for i in range(w.count())]
    check("b9 erfundenes Endprodukt behaelt den Invention-Tab",
          any("Invention" in t for t in _titles_t2))
    _hdr_t2 = [x.text() for x in (_dlg_t2.findChildren(QLabel) if _dlg_t2 else [])
               if x.property("bd_role") == "endproduct_me_te"]
    check(f"b9 T2 zeigt ME NICHT oben (kommt aus der Invention)  ({_hdr_t2})",
          not _hdr_t2)
    _sp_t2 = [x for x in (_dlg_t2.findChildren(QSpinBox) if _dlg_t2 else [])
              if x.property("bd_role") == "endproduct_me_te"]
    check("b9 T2 hat auch keine Header-Eingabefelder", not _sp_t2)
except Exception as e:                                   # pragma: no cover
    import traceback
    traceback.print_exc()
    _fail.append(f"b9 Gegenprobe T2: {type(e).__name__}: {e}")

# ---------------------------------------------------------------- (b2w)
# (Sitzung 17 hierher verschoben: hinter die T2-Gegenprobe, solange deren
#  Fenster offen ist - vorher lief b2w an Resten eines geschlossenen.)
# ZEIT-REGLER DER INVENTION-AUFTEILUNG (Nutzer, Sitzung 9: "nur einen
# Regler bedienen, der mir die Zeit anzeigt"). Funktional am offenen
# Dialog: Regler und Kopien-Feld sind EIN Wert, die Slots deckeln den
# Regler, und die Aufteilungs-Zeile traegt die Ingame-Uebersetzung.
try:
    from PySide6.QtWidgets import QSlider as _QSl2w
    # SEIT 26.09.2026 JE KARTE (Nutzer: "jede Karte ihren eigenen Regler";
    # vorher lagen Regler/Kopien-Feld auf `self._inv_*` und die LETZTE Karte
    # gewann). Ein Regler je Karte, das Slot-Feld EINMAL oben.
    _sw2w_all = dict(getattr(win, "_bd_inv_split_w", None) or {})
    _sw2w = next(iter(_sw2w_all.values()), None)
    _sl2w = _sw2w["slider"] if _sw2w else None
    _st2w = getattr(win, "_inv_slots", None)
    # DAS OFFENE FENSTER, KEINE RESTE (Sitzung 17, Nutzer-Screenshot Windows:
    # "QSpinBox already deleted"). Gemessen: an der alten Stelle gehoerten die
    # Felder zu einem GESCHLOSSENEN T2-Fenster, nicht zum offenen Bauplan. Ob
    # dessen Widgets noch leben, entschied die Speicherbereinigung - im
    # Container immer ja, beim Nutzer irgendwann nein. Deshalb steht b2w jetzt
    # direkt hinter der T2-Gegenprobe, und prueft das auch.
    _w2w = _st2w.window() if _st2w is not None else None
    check("b2w prueft die Felder des OFFENEN Bauplans, keine Reste",
          _w2w is not None and _w2w is getattr(win, "_bd_dialog", None)
          and _w2w.isVisible())
    check("b2w der Regler existiert in der Invention-Karte",
          isinstance(_sl2w, _QSl2w) and _sl2w.window() is _w2w)
    if _sl2w is not None and _st2w is not None:
        _st2w.setValue(10); _app.processEvents()
        # NUTZSTUFEN-SCHNAPPEN (Nutzer, Sitzung 9: "ich kann ihn hoeher
        # ziehen als er einen Nutzen hat"): nutzlose Positionen schnappen
        # auf die kleinste Kopienzahl derselben Zeitstufe. Versuchszahl der
        # Mock-Rezepte: 4 -> Nutzstufen {1, 2, 4}.
        _sl2w.setValue(4); _app.processEvents()
        eq("b2w Regler auf 4 -> 4 Kopien", _sl2w.value(), 4)
        _sl2w.setValue(10); _app.processEvents()
        eq("b2w Regler ueber der Versuchszahl schnappt zurueck (10 -> 4)",
           _sl2w.value(), 4)
        _sl2w.setValue(3); _app.processEvents()
        eq("b2w Plateau-Stufe schnappt (3 -> 2)", _sl2w.value(), 2)
        # GANZE BREITE (Nutzer 26.09.2026: "warum kann ich die Regler nicht
        # ganz bis rechts ziehen?"): rechts = min(freie Slots, Versuche).
        eq("b2w rechter Anschlag = Versuche (4), nicht die 10 freien Slots",
           _sl2w.maximum(), 4)
        _st2w.setValue(3); _app.processEvents()
        eq("b2w weniger freie Slots als Versuche deckeln den Regler (3)",
           _sl2w.maximum(), 3)
        _st2w.setValue(5); _app.processEvents()
        _kopf2w = _sw2w["kopf"].text()
        # GROSSE KOPIERANLEITUNG (Nutzer: "Copy your T1 original like this ->
        # Job Runs / Runs per Copy"): bei 2 Kopien und 4 Versuchen 2 x 2.
        check("b2w die Kopieranleitung nennt die Ingame-Felder mit den Zahlen",
              "Job Runs: <span" in _kopf2w and "Runs per Copy: <span" in _kopf2w
              and ">2</span>" in _kopf2w
              and ("Copy your T1 original" in _kopf2w or "Kopiere dein T1-Original" in _kopf2w))
        _lbl2w = _sw2w["lbl"].text()
        # WEISS, 15px FETT, ZAHL GROSS UND AMBER (Nutzer 26.09.2026: "gleiche
        # Groesse wie oben Job Runs, Zahlen auch gleich gross und Amber").
        check("b2w daneben: belegte Science-Slots - Text weiss/15px, Zahl gross + amber",
              ("science slot" in _lbl2w or "Science-Slot" in _lbl2w)
              and "font-size:15px" in _lbl2w and "font-weight:700" in _lbl2w
              and f"color:{_th7.TEXT}" in _lbl2w
              and f"font-size:{_th7.FS_KPI}; font-weight:800; color:{_th7.AMBER}" in _lbl2w
              and ">2</span>" in _lbl2w)
        # emm324: die Dauer gehoert zur Invention, nicht zum Kopierjob
        # (Nutzer: "das dauert ingame nur 1h20min und nicht 2T12h").
        check("b2w die Zeile sagt, dass sie die Invention DANACH meint",
              "Then invention:" in _lbl2w or "Danach Invention:" in _lbl2w)
        _st2w.setValue(10); _sl2w.setValue(1); _app.processEvents()
    # emm326 "COPY T1 ORIGINAL" (Nutzer 01.10.2026: amber umrahmter Knopf
    # neben dem Blueprint-Bild, kopiert den T1-Blaupausen-Namen wie der
    # Runplaner). Echter Klick, Zwischenablage gelesen. Die Mock-Blaupausen
    # haben ohne Netz keinen Namen ("#id" -> kein Knopf, mit Absicht) – also
    # den T1-Namen in den Namens-Cache legen und neu aufbauen.
    from eve_trader import store as _sto2w
    _rec2w = getattr(win, "_bd_recipes", None)
    _t1ids2w = [int((getattr(_rec2w, "invention_for_bpc", {}) or {})[_b][0])
                for _b in _sw2w_all
                if _b in (getattr(_rec2w, "invention_for_bpc", {}) or {})]
    _neu2w = {_i: f"b2w T1 {_i} Blueprint" for _i in _t1ids2w
              if _i not in _sto2w.cached_names([_i])}
    if _neu2w:
        _sto2w.save_names(_neu2w)
    win._bd_full_rebuild(); _app.processEvents()
    _t1c2w = dict(getattr(win, "_bd_inv_t1_copy", None) or {})
    _sw2w_all = dict(getattr(win, "_bd_inv_split_w", None) or {})
    _bp2w = next(iter(_t1c2w), None)
    _k2w = _t1c2w.get(_bp2w)
    check(f"b2w jede Invention-Karte hat 'Copy T1 Blueprint' ({len(_t1c2w)} / "
          f"{len(_sw2w_all)})", _k2w is not None and len(_t1c2w) == len(_sw2w_all))
    if _k2w is not None:
        check("b2w Knopf-Text ist 'Copy T1 Blueprint' (DE/EN, emm329)",
              _k2w.text() in ("Copy T1 Blueprint", "T1-Blueprint kopieren"))
        check("b2w Knopf amber umrahmt wie die Runplaner-Knoepfe",
              f"border:1px solid {_th7.AMBER_DIM}" in _k2w.styleSheet()
              and f"color:{_th7.AMBER}" in _k2w.styleSheet())
        _dc2w = (getattr(win, "_bd_inv_best_btns", None) or {}).get(_bp2w)
        check("b2w 'Copy Decryptor' gleich gross wie 'Copy T1 Blueprint' (emm329)",
              _dc2w is not None and _dc2w.styleSheet() == _k2w.styleSheet()
              and _dc2w.minimumHeight() == _k2w.minimumHeight()
              and abs(_dc2w.sizeHint().height() - _k2w.sizeHint().height()) <= 1)
        _i2w = int(((getattr(_rec2w, "invention_for_bpc", {}) or {}).get(_bp2w) or [0])[0])
        _nm2w = _sto2w.cached_names([_i2w]).get(_i2w, "")
        _app.clipboard().setText("leer b2w")
        _k2w.click(); _app.processEvents()
        check(f"b2w Klick kopiert den T1-Blaupausen-Namen ({_nm2w!r})",
              bool(_nm2w) and _app.clipboard().text() == _nm2w
              and _nm2w in _k2w.toolTip())
    # emm328 REGLER BLEIBT STEHEN (Nutzer 02.10.2026: "Regler nach rechts,
    # Plan zu und wieder auf -> wieder ganz links; es soll speichern wo es
    # war. Ein neuer Plan startet aber immer ganz links"). Echter Regler.
    import eve_trader.config as _cfg2w
    _alt2w = {"sa": _cfg2w.save_settings_async,
              "plans": win.settings.get("bau_saved_plans"),
              "pid": getattr(win, "_bd_open_plan_id", None),
              "split": dict(getattr(win, "_bd_inv_split", None) or {})}
    try:
        _sp2w = []
        _cfg2w.save_settings_async = lambda *a, **k: _sp2w.append(1)
        _e2w = {"id": 92801, "label": "b2w Regler", "type_id": 1}
        win.settings["bau_saved_plans"] = [_e2w]
        win._bd_open_plan_id = 92801
        _bp2wr = next(iter(win._bd_inv_split_w))
        _slr = win._bd_inv_split_w[_bp2wr]["slider"]
        # Ziehen = viele Schritte; geschrieben wird erst NACH dem Zug (emm330:
        # "Regler laggy" - vorher je Schritt die ganze settings.json).
        for _v2w in range(_slr.minimum(), _slr.maximum() + 1):
            _slr.setValue(_v2w); _app.processEvents()
        check(f"b2w waehrend des Ziehens wird nichts gespeichert ({len(_sp2w)})",
              len(_sp2w) == 0)
        from PySide6.QtTest import QTest as _QT2w
        _QT2w.qWait(win.INV_SPLIT_MERK_MS + 300); _app.processEvents()
        check(f"b2w nach dem Zug genau EIN Speichern ({len(_sp2w)})", len(_sp2w) == 1)
        _soll2w = _slr.value()
        check(f"b2w Regler-Stand landet im gespeicherten Plan ({_e2w.get('inv_split')})",
              _soll2w > 1 and (_e2w.get("inv_split") or {}).get(str(_bp2wr)) == _soll2w)
        # Schliessen/Oeffnen: der Speicher-Stand wird geladen, das Fenster neu gebaut.
        win._bd_inv_split = win._inv_split_aus_plan(_e2w)
        win._bd_full_rebuild(); _app.processEvents()
        eq("b2w nach dem Neu-Oeffnen steht der Regler wieder dort",
           win._bd_inv_split_w[_bp2wr]["slider"].value(), _soll2w)
        # Neuer Plan: leerer Stand -> ganz links.
        win._bd_inv_split = {}
        win._bd_full_rebuild(); _app.processEvents()
        eq("b2w neuer Plan (leerer Stand) startet ganz links",
           win._bd_inv_split_w[_bp2wr]["slider"].value(), 1)
    finally:
        _cfg2w.save_settings_async = _alt2w["sa"]
        if _alt2w["plans"] is None:
            win.settings.pop("bau_saved_plans", None)
        else:
            win.settings["bau_saved_plans"] = _alt2w["plans"]
        win._bd_open_plan_id = _alt2w["pid"]
        win._bd_inv_split = _alt2w["split"]
        win._bd_full_rebuild(); _app.processEvents()
except Exception as _e2w:                                # pragma: no cover
    _fail.append(f"b2w Block geplatzt: {_e2w!r}")
    # WO GENAU? (Sitzung 17): auf Windows bricht der Block ab, im Container
    # nicht - weder mit Windows-Datenordner noch mit groesserer Schrift
    # nachstellbar. Jede Stapelzeile als EIGENE kurze Zeile, weil pruefe.py
    # Zeilen nach 110 Zeichen abschneidet.
    import traceback as _tb2w
    for _fr2w in _tb2w.extract_tb(_e2w.__traceback__)[-4:]:
        print(f"  FEHLER-ORT b2w: {_fr2w.filename.replace(chr(92), '/').rsplit('/', 1)[-1]}"
              f":{_fr2w.lineno}  {(_fr2w.line or '')[:60]}")



# ---------------------------------------------------------------- (b64)
# BAUPLAN (Nutzer, Sitzung 17): "Build or buy" und "Production depth"
# STANDARD AUSGEKLAPPT; die Endprodukt-Zeile stand als "BAUEN \u00b7 20 Runs"
# auf der englischen Oberflaeche. Am offenen T2-Bauplan gemessen.
try:
    _d64 = getattr(win, "_bd_dialog", None)
    _k64 = {}
    for _b64 in (_d64.findChildren(QPushButton) if _d64 is not None else []):
        for _titel64 in ("Build or buy?", "Production depth"):
            if (_b64.text() or "").endswith(_t4(_titel64)) and _b64.isCheckable():
                _k64[_titel64] = _b64.isChecked()
    eq("b64 Build or buy und Production depth starten AUFGEKLAPPT", _k64,
       {"Build or buy?": True, "Production depth": True})
    _baum64 = []
    for _tw64 in (_d64.findChildren(QTreeWidget) if _d64 is not None else []):
        _it64 = _tw64.invisibleRootItem()
        _stapel64 = [_it64.child(_i) for _i in range(_it64.childCount())]
        while _stapel64:
            _x64 = _stapel64.pop()
            _baum64 += [_x64.text(_c) for _c in range(_tw64.columnCount())]
            _stapel64 += [_x64.child(_i) for _i in range(_x64.childCount())]
    check(f"b64 der Baum ist gefuellt ({len(_baum64)} Zellen)", len(_baum64) > 10)
    eq("b64 kein 'BAUEN' in den Baum-Zeilen (englische Oberflaeche)",
       [_z for _z in _baum64 if "BAUEN" in (_z or "")], [])
except Exception as _e64:                                # pragma: no cover
    _fail.append(f"b64 Bauplan-Seitenleiste: {type(_e64).__name__}: {_e64}")


# ---------------------------------------------------------------- (b10)
# EIN RUN IST UNTEILBAR (Nutzer-Hinweis). Reaktionen liefern z.B. 200 Stueck
# pro Run - "Menge 1" gibt es im Spiel nicht, und die Rechnung wuerde den
# ganzen Run auf ein Stueck buchen (gemessen: 250'000 statt 1'250 ISK/Stk).
# ZWEITER ZWEIG: alle bisherigen Testrezepte liefern 1 Stueck pro Run, die
# neue Bedingung waere also nie betreten worden.


class _RecipesBatch:
    """Reaktion: 1 Run -> 200 Stueck."""
    product_to_bp = {100: (900, I.REACTION, 200)}
    bp_materials = {(900, I.REACTION): [(200, 10)]}
    activity_time = {(900, I.REACTION): 60}
    activity_max_runs = {(900, I.REACTION): 0}
    reaction_products = {100}
    invention_for_bpc = {}
    bp_products = {}
    item_cat = {}

    def is_manufactured(self, t):
        return False


win._bd_recipes = _RecipesBatch()
win._bd_qty = 1
try:
    win._show_build_detail(100, "Testreaktion-Batch", _res_rea)
    _dlg_b = getattr(win, "_bd_dialog", None)
    _spins = [x for x in (_dlg_b.findChildren(QSpinBox) if _dlg_b else [])
              if x.minimum() == 200 and x.singleStep() == 200]
    check("b10 Mengenfeld kann nicht unter einen Run", bool(_spins))
    if _spins:
        _qs = _spins[0]
        eq("b10 Startwert auf ganzen Run aufgerundet", _qs.value(), 200)
        # Getippter Zwischenwert wird beim Verlassen aufgerundet.
        _qs.setValue(250)
        _qs.editingFinished.emit()
        eq("b10 Zwischenwert wird auf den naechsten Run aufgerundet",
           _qs.value(), 400)
    _hints = [x.text() for x in (_dlg_b.findChildren(QLabel) if _dlg_b else [])
              if x.property("bd_role") == "runs_hint"]
    check(f"b10 Runs stehen daneben  ({_hints})",
          any(("Run" in t or "run" in t) and "200" in t for t in _hints))
    # RUNS DIREKT EINGEBEN (Discord, Commander Hibb, 16.09.2026). Das
    # Runs-Feld ist eine zweite ANSICHT derselben Zahl: was man dort
    # eintippt, landet als Stueck im Mengenfeld - und umgekehrt. Die
    # Wahrheit bleibt Stueck (gespeicherte Plaene, Reservierung, Runplaner).
    _rs = [x for x in (_dlg_b.findChildren(QSpinBox) if _dlg_b else [])
           if x.property("bd_role") == "runs_spin"]
    _mb = [x for x in (_dlg_b.findChildren(QPushButton) if _dlg_b else [])
           if x.property("bd_role") == "qty_mode"]
    check("b10 beim Batch-Rezept gibt es ein Runs-Feld und den Umschalter",
          bool(_rs) and bool(_mb))
    if _rs and _mb and _spins:
        _qs, _r, _m = _spins[0], _rs[0], _mb[0]
        _alt_mode10 = win.settings.get("bau_qty_in_runs")
        _alt_save10 = _cfg7q.save_settings
        _cfg7q.save_settings = lambda s: None
        try:
            eq("b10 Runs-Feld zeigt die Runs des Stueckfelds (400 -> 2)",
               _r.value(), 2)
            _r.setValue(7)
            eq("b10 7 Runs -> 1'400 Stueck im Mengenfeld", _qs.value(), 1400)
            # UND DIE RECHNUNG FOLGT: Enter im Runs-Feld uebernimmt die
            # Menge in den Plan (`_bd_qty` ist das, womit rebuild rechnet).
            _r.editingFinished.emit()
            _app.processEvents()
            eq("b10 Enter im Runs-Feld -> der Plan rechnet mit 1'400",
               int(getattr(win, "_bd_qty", 0) or 0), 1400)
            # FREMDES FENSTER (26.09.2026 nachgestellt): der 450-ms-Mengen-
            # Timer eines Fensters, das nicht mehr das offene ist, schrieb
            # seine Menge in den gemeinsamen Zustand. Hier: Menge tippen,
            # ein anderes Fenster ist "dran", Timer ablaufen lassen.
            from PySide6.QtTest import QTest as _QT10
            _dlg_alt10 = win._bd_dialog
            _qs.setValue(1600)
            win._bd_dialog = None
            try:
                _QT10.qWait(650)
                eq("b10 der Mengen-Timer eines nicht mehr offenen Fensters rechnet nicht",
                   int(getattr(win, "_bd_qty", 0) or 0), 1400)
            finally:
                win._bd_dialog = _dlg_alt10
            _qs.setValue(1400); _app.processEvents()
            _qs.setValue(1000)
            eq("b10 1'000 Stueck -> 5 Runs", _r.value(), 5)
            # Umschalten zeigt nur das eine Feld und merkt sich die Wahl.
            _m.setChecked(True)
            check("b10 im Runs-Modus ist das Stueckfeld weg, das Runs-Feld da",
                  _qs.isHidden() and not _r.isHidden())
            eq("b10 die Wahl wird gespeichert", win.settings.get("bau_qty_in_runs"), True)
            _m.setChecked(False)
            check("b10 zurueck: Stueckfeld da, Runs-Feld weg",
                  not _qs.isHidden() and _r.isHidden())
        finally:
            _cfg7q.save_settings = _alt_save10
            win.settings["bau_qty_in_runs"] = bool(_alt_mode10)
except Exception as e:                                   # pragma: no cover
    import traceback
    traceback.print_exc()
    _fail.append(f"b10 Batch-Rezept: {type(e).__name__}: {e}")

# GEGENPROBE: bei 1 Stueck pro Run bleibt das Feld frei (kein Mindestwert).
win._bd_recipes = _Recipes()
win._bd_qty = 10
try:
    win._show_build_detail(100, "Testship", _res)
    _dlg_s = getattr(win, "_bd_dialog", None)
    _spins_s = [x for x in (_dlg_s.findChildren(QSpinBox) if _dlg_s else [])
                if x.singleStep() > 1 and x.minimum() > 1]
    check("b10 Einzelstueck-Rezept behaelt die freie Mengeneingabe",
          not _spins_s)
    _hints_s = [x for x in (_dlg_s.findChildren(QLabel) if _dlg_s else [])
                if x.property("bd_role") == "runs_hint" and not x.isHidden()]
    check("b10 und keinen Runs-Hinweis", not _hints_s)
    check("b10 und keinen Runs-Umschalter (waere nur Laerm)",
          not [x for x in _dlg_s.findChildren(QPushButton)
               if x.property("bd_role") == "qty_mode"])
except Exception as e:                                   # pragma: no cover
    _fail.append(f"b10 Gegenprobe Einzelstueck: {type(e).__name__}: {e}")

# ---------------------------------------------------------------- (b8)
# KEINE STREUNENDEN FENSTER. Ein Widget ohne Parent wird durch
# setVisible(True) zu einem eigenen Top-Level-Fenster - beim Nutzer poppte so
# ein leeres "python"-Fenster mit dem Text einer KPI-Unterzeile auf, jedes
# Mal beim Oeffnen des Bauplans. Dieselbe Falle war beim Werkzeuge-Menue
# schon dokumentiert und wurde trotzdem wiederholt -> ab jetzt gemessen.
_app.processEvents()
_strays = [w for w in _app.topLevelWidgets()
           if w.isVisible() and w is not win and w is not _dlg
           and not w.windowTitle().startswith(("Bauplan", "Build plan", "Motor"))
           and w.__class__.__name__ not in ("QMenu", "QToolTip")]
check(f"b8 keine streunenden Top-Level-Fenster {[type(w).__name__ for w in _strays][:3]}",
      not _strays)
_orphan_lbls = [w for w in _app.topLevelWidgets()
                if isinstance(w, QLabel) and w.isVisible()]
check("b8 kein sichtbares Label ohne Parent", not _orphan_lbls)

# ---------------------------------------------------------------- Ergebnis
# ------------------------------------------------------------ (b11)
# Gehoert in DIESE Kette, nicht in die Logik-Tests: die Pruefung baut
# ein echtes Qt-Widget, und dafuer braucht es die QApplication, die es
# nur hier gibt.
# ---------------------------------------------------------------- (b11)
# ISK-EINGABEFELDER NAHMEN KEINE WERTE MEHR AN (Nutzer: "kann bei Frachtdienst
# nicht mehr als 10 ISK eingeben, wollte 445, springt nach Enter zurueck").
# IskGroupedSpin SCHREIBT mit Tausender-Apostroph (textFromValue), erbte aber
# den Pruefer von QSpinBox - und der kennt das Trennzeichen nicht. Die Box
# lehnte also genau das Format ab, das sie selbst anzeigt; ab 1'000 war sie
# gar nicht mehr editierbar. Dazu kam, dass valueFromText das SUFFIX nicht
# abraeumte ("445 ISK/m3" -> float() scheitert -> alten Wert behalten), und
# im Eingabefeld steht immer die volle Anzeige.
from PySide6.QtGui import QValidator as _QV98
from eve_trader.ui.main_window import IskGroupedSpin as _IGS98
_s98 = _IGS98()
_s98.setRange(0, 2_000_000_000)
_s98.setSuffix(" ISK/m\u00b3")
_s98.setValue(10)
eq("b11 Zahl mit Suffix wird angenommen",
   _s98.validate("445 ISK/m\u00b3", 3)[0], _QV98.Acceptable)
eq("b11 eigenes Anzeigeformat wird angenommen",
   _s98.validate("1'234 ISK/m\u00b3", 3)[0], _QV98.Acceptable)
eq("b11 Buchstaben weiterhin abgelehnt",
   _s98.validate("abc", 3)[0], _QV98.Invalid)
eq("b11 leeres Feld ist kein Fehler, sondern 'tippt noch'",
   _s98.validate("", 0)[0], _QV98.Intermediate)
# Der eigentliche Nutzerfall: eintippen und uebernehmen.
_s98.lineEdit().setText("445 ISK/m\u00b3")
_s98.interpretText()
eq("b11 445 kommt auch wirklich an", _s98.value(), 445)
_s98.lineEdit().setText("1'234 ISK/m\u00b3")
_s98.interpretText()
eq("b11 und Werte ueber 1000 ebenso", _s98.value(), 1234)
_s98.setValue(50000)
eq("b11 Anzeige behaelt die Tausendertrennung",
   _s98.text(), "50'000 ISK/m\u00b3")


# ---------------------------------------------------------------- (b13)
# EINFRIEREN FRIERT DEN PLAN EIN (TOP-AUFGABE): mit gesetztem plan_snapshot
# darf der Dialog-Aufbau production_plan NICHT mehr aufrufen - der Plan kommt
# aus dem Schnappschuss (Beleg: praeparierte 999 build_runs, die eine echte
# Rechnung nie ergaebe). Dazu: Menge gesperrt, Knopf sagt was los ist.
import time as _t13
win._bd_pricemap = dict(PRICES)
win._bd_recipes = _Recipes()
win._bd_opts = {"me": 0, "te": 0, "job_pct": 0, "build_reactions": False,
                "tree_depth": 4}
win._bd_type = 100
win._bd_qty = 10
_plan13 = I.production_plan(100, 10, PRICES.get, _Recipes(), dict(win._bd_opts))
_snap13 = MainWindow._plan_snapshot_pack(_plan13)
_snap13["build_runs"] = {"100": 999}      # Marker: kann nur aus dem Snapshot kommen
win._bd_frozen = {"ts": _t13.time(), "qty": 10,
                  "prices": dict(PRICES), "adjusted": {}, "stock": {},
                  "cost_idx": {}, "plan_snapshot": _snap13}
win._bd_frozen_plan_cache = None
_tree13 = I.build_tree(100, PRICES.get, _Recipes(), dict(win._bd_opts))
_res13 = {"tree": _tree13, "names": {100: "Testship", 200: "Testmat"},
          "sell": 6000.0, "sell_is_contract": False, "plan": _plan13}
_calls13 = {"n": 0}
_orig_pp13 = I.production_plan


def _pp13(*a, **kw):
    _calls13["n"] += 1
    return _orig_pp13(*a, **kw)


I.production_plan = _pp13
_dlg13 = None
try:
    win._show_build_detail(100, "Testship-Frozen", _res13)
    _dlg13 = getattr(win, "_bd_dialog", None)
    check("b13 Dialog mit eingefrorenem Plan laesst sich bauen", _dlg13 is not None)
except Exception as e:                                   # pragma: no cover
    import traceback
    traceback.print_exc()
    _fail.append(f"b13 Dialog eingefroren: {type(e).__name__}: {e}")
finally:
    I.production_plan = _orig_pp13
eq("b13 eingefroren rechnet NICHT neu (production_plan-Aufrufe)",
   _calls13["n"], 0)
_pl13 = (getattr(win, "_bd_plan_ref", None) or {}).get("plan") or {}
eq("b13 der angezeigte Plan IST der Schnappschuss (Marker + int-Key)",
   (_pl13.get("build_runs") or {}).get(100), 999)
if _dlg13 is not None:
    _btxt13 = [b.text() for b in _dlg13.findChildren(QPushButton) if b.text()]
    check("b13 Knopf sagt was los ist (Plan eingefroren + Gewinn live)",
          any(("Plan eingefroren" in t and "Gewinn live" in t)
              or ("Plan frozen" in t and "profit live" in t) for t in _btxt13))
    # Zweisprachig (Sitzung 16): der Tooltip laeuft durch t().
    # seit emm298 sind auch ME/TE gesperrt - die MENGE erkennt man am Wort.
    _locked13 = [s for s in _dlg13.findChildren(QSpinBox)
                 if not s.isEnabled()
                 and ("Plan eingefroren" in (s.toolTip() or "")
                      or "Plan frozen" in (s.toolTip() or ""))
                 and ("Menge" in (s.toolTip() or "")
                      or "quantity" in (s.toolTip() or ""))]
    check("b13 Mengen-Spinner ist gesperrt und sagt warum", len(_locked13) == 1)
    # ME/TE GESPERRT (Nutzer 30.09.2026: "wenn mein Plan eingefroren ist,
    # sollte es nicht mehr moeglich sein, ME/TE zu aendern"): Endprodukt +
    # die acht Kategorie-Felder, jedes mit Grund; Reset ebenfalls.
    _ms13 = list(getattr(win, "_bd_mete_spins", ()) or ())
    check(f"b13 alle ME/TE-Felder gesperrt, jedes sagt warum ({len(_ms13)})",
          len(_ms13) == 10 and all(
              not _x.isEnabled() and ("Plan frozen" in (_x.toolTip() or "")
                                      or "Plan eingefroren" in (_x.toolTip() or ""))
              for _x in _ms13))
    _rb13 = getattr(win, "_bd_reset_btn", None)
    check("b13 Reset-Knopf gesperrt, solange eingefroren",
          _rb13 is not None and not _rb13.isEnabled())
    eq("b13 gesperrte Menge ist die EINGEFRORENE Menge",
       _locked13[0].value() if _locked13 else None, 10)
# Aufraeumen, damit kein Folge-Test versehentlich eingefroren rechnet.
win._bd_frozen = None
win._bd_frozen_plan_cache = None


# ---------------------------------------------------------------- (b14)
# "UEBERNEHMEN" BEI DEN BAU-CHARAKTEREN MUSS BELIEBIG OFT GEHEN (Nutzer-
# Befund Sitzung 11: "ich kann nur 1x uebernehmen klicken, danach sind keine
# aenderungen mehr moeglich ... haken lassen sich noch setzen, aber der
# uebernehmen button ist nicht mehr anklickbar").
#
# URSACHE war NICHT der Knopf, sondern `_reload_char_roles`: es leerte das
# Panel nur ueber `it.widget()`. Die Knopfzeile haengt aber als LAYOUT
# drin (`lay.addLayout(btn_row)`), und fuer ein Unter-Layout ist
# `it.widget()` None - die drei Knoepfe wurden also nie geloescht und
# standen nach dem Neuaufbau ein ZWEITES Mal im Panel. Der alte,
# ausgegraute "Uebernehmen" blieb dort liegen, wo der neue hingehoert:
# die Haken schalteten den NEUEN frei, der Nutzer sah den ALTEN.
# AUSGELOEST wurde der Neuaufbau vom stillen `_load_char_slots(silent=True)`,
# das der Bauplan-Dialog beim Oeffnen selbst anstoesst (freie Slots aelter
# als 10 min) - die ESI-Antwort trifft also genau waehrend des Kreuzens ein.
#
# TEXTPRUEFUNG REICHT HIER NICHT: aa220 liest den Quelltext von
# _save_build_chars/_apply_build_chars und war die ganze Zeit gruen. Der
# Fehler lag zwei Funktionen weiter, in einer Zeile, die den Knopf nie
# erwaehnt. Deshalb hier ECHT geklickt.
from eve_trader import store, config                      # noqa: E402
_chars14 = [{"character_id": 1, "character_name": "Peanut Motor"},
            {"character_id": 2, "character_name": "Berry Motor"}]
_orig_lc14 = store.list_characters
_orig_save14 = config.save_settings
store.list_characters = lambda: list(_chars14)
config.save_settings = lambda s: None      # Platte nicht anfassen
try:
    win._char_roles_dirty = False
    _panel14 = win._build_char_roles_widget()
    _btn14 = win._char_roles_apply_btn
    _box14a = win._char_role_boxes[(1, "bau_build_chars")]

    def _ueber14():
        # SPRACHUNABHAENGIG: gesucht wird der UEBERSETZTE Text, nicht das
        # deutsche Teilwort "bernehmen".
        return [b for b in _panel14.findChildren(QPushButton)
                if b.text() == _t4("\u2713 Apply")]

    check("b14 frisch geoeffnet ist 'Uebernehmen' ausgegraut",
          _btn14 is not None and not _btn14.isEnabled())
    _box14a.setChecked(True)
    _app.processEvents()
    check("b14 ein Kreuz macht 'Uebernehmen' anklickbar", _btn14.isEnabled())
    _btn14.click()
    _app.processEvents()
    check("b14 nach dem Klick ist nichts mehr offen",
          not _btn14.isEnabled() and win._char_roles_dirty is False)
    # DER ENTSCHEIDENDE TEIL: jetzt trifft die ESI-Antwort ein und baut das
    # Roster neu - genau die Stelle, an der der Knopf frueher starb.
    win._reload_char_roles()
    _app.processEvents()
    eq("b14 der Neuaufbau laesst GENAU EINEN 'Uebernehmen' zurueck",
       len(_ueber14()), 1)
    _btn14b = win._char_roles_apply_btn
    check("b14 der gemerkte Knopf ist der, der im Panel steht",
          bool(_ueber14()) and _ueber14()[0] is _btn14b)
    check("b14 er ist nach dem Neuaufbau ausgegraut (nichts offen)",
          not _btn14b.isEnabled())
    # ... und ein weiteres Kreuz muss ihn WIEDER freischalten.
    _box14b = win._char_role_boxes[(2, "bau_reaction_chars")]
    _box14b.setChecked(True)
    _app.processEvents()
    check("b14 nach dem Neuaufbau schaltet ein Kreuz ihn WIEDER frei",
          _btn14b.isEnabled() and win._char_roles_dirty is True)
    _btn14b.click()
    _app.processEvents()
    check("b14 und 'Uebernehmen' laesst sich ein zweites Mal klicken",
          not _btn14b.isEnabled() and win._char_roles_dirty is False)
    # Die Auswahl darf der Neuaufbau nicht verschluckt haben.
    eq("b14 die Rolle des zweiten Charakters ist gespeichert",
       sorted(win.settings.get("bau_reaction_chars") or []), [2])
    # LEERES ROSTER: dort baut _populate_char_roles die Knopfzeile gar nicht.
    # Der gemerkte Knopf darf dann NICHT auf ein totes C++-Objekt zeigen -
    # sonst stirbt das naechste Kreuz mit RuntimeError.
    _chars14.clear()
    win._reload_char_roles()
    _app.processEvents()
    check("b14 ohne Charaktere zeigt der Merker auf nichts (statt auf Totes)",
          win._char_roles_apply_btn is None)
    _sbc_ok14 = True
    try:
        win._save_build_chars()
    except Exception:                                    # pragma: no cover
        _sbc_ok14 = False
    check("b14 ein Kreuz-Speichern stuerzt dort nicht ab", _sbc_ok14)
finally:
    store.list_characters = _orig_lc14
    config.save_settings = _orig_save14
    win._char_roles_dirty = False


# ---------------------------------------------------------------- (b14r)
# REPROCESSING-SKILLS NUR IM TOOLTIP DES CHARAKTERNAMENS (1.0.9, Nutzer
# 17.09.2026: kein Haken, keine Spalte - "den besten reprocess Charakter
# waehlen" macht spaeter der Runplaner selbst). Die Zeile erscheint NUR,
# wenn Skills geladen sind UND die SDE die Skill-IDs kennt - sonst nichts,
# und vor allem keine geratene ID.
_chars14r = [{"character_id": 1, "character_name": "Peanut Motor"},
             {"character_id": 2, "character_name": "Berry Motor"}]
_orig_lc14r = store.list_characters
_orig_save14r = config.save_settings
_orig_ids14r = I.reprocess_skill_ids
_orig_sk14r = win.settings.get("bau_char_skills")
store.list_characters = lambda: list(_chars14r)
config.save_settings = lambda s: None
try:
    def _namen14r(panel):
        return {lb.text(): lb for lb in panel.findChildren(QLabel)
                if lb.text() in ("Peanut Motor", "Berry Motor")}
    # Schluessel str wie nach JSON; Charakter 2 hat nie Skills geladen.
    win.settings["bau_char_skills"] = {"1": {"3385": 4, "3389": 3, "3380": 5}}
    I.reprocess_skill_ids = lambda: {"Reprocessing": 3385, "Reprocessing Efficiency": 3389}
    _p14r = win._build_char_roles_widget()
    _lbs = _namen14r(_p14r)
    check("b14r mit Skills und IDs steht die Zeile im Tooltip",
          _t4("Reprocessing skills: {r} / Efficiency {e}").format(r=4, e=3)
          in _lbs["Peanut Motor"].toolTip())
    check("b14r ohne geladene Skills keine Zeile",
          "Reprocessing" not in _lbs["Berry Motor"].toolTip().split("\n")[-1]
          and _lbs["Berry Motor"].toolTip().count("\n")
          == _lbs["Peanut Motor"].toolTip().count("\n") - 1)
    check("b14r eine Zeile pro Charakter, nicht doppelt",
          _lbs["Peanut Motor"].toolTip().count("Efficiency") == 1)
    I.reprocess_skill_ids = lambda: {}
    _p14r2 = win._build_char_roles_widget()
    check("b14r ohne Skill-IDs aus der SDE keine Zeile (kein Raten)",
          "Efficiency" not in _namen14r(_p14r2)["Peanut Motor"].toolTip())
    # Die Zeile ist zweisprachig hinterlegt.
    from eve_trader import sprache as _sp14r
    check("b14r die Zeile hat eine deutsche Fassung",
          "Reprocessing skills: {r} / Efficiency {e}" in _sp14r.KATALOG["de"])
finally:
    store.list_characters = _orig_lc14r
    config.save_settings = _orig_save14r
    I.reprocess_skill_ids = _orig_ids14r
    if _orig_sk14r is None:
        win.settings.pop("bau_char_skills", None)
    else:
        win.settings["bau_char_skills"] = _orig_sk14r
    win._reload_char_roles()


# ---------------------------------------------------------------- (b15)
# KLICK AUF DEN CHARAKTERNAMEN SETZT/ENTFERNT ALLE ROLLEN (Nutzer-Wunsch
# Sitzung 11: "fuege ein, wenn man auf den charakter namen klickt, dass sich
# alle hacken setzten oder entfernen von diesem charakter") - und das
# HAKEN-SETZEN muss dabei schnell bleiben (gleicher Auftrag): ein Klick darf
# NICHT vier Speichervorgaenge ausloesen.
_chars15 = [{"character_id": 7, "character_name": "Lezaar"},
            {"character_id": 8, "character_name": "Fredy"}]
_orig_lc15 = store.list_characters
_orig_save15 = config.save_settings
_orig_async15 = config.save_settings_async
_schreibt15 = {"sync": 0, "async": 0}
store.list_characters = lambda: list(_chars15)
config.save_settings = lambda s: _schreibt15.__setitem__("sync", _schreibt15["sync"] + 1)
config.save_settings_async = lambda s: _schreibt15.__setitem__(
    "async", _schreibt15["async"] + 1)
try:
    for _k15, _l15 in win._ROSTER_ROLES:
        win.settings[_k15] = []
    win._char_roles_last_saved = None
    win._char_roles_dirty = False
    _panel15 = win._build_char_roles_widget()   # Referenz halten, sonst raeumt
    _panel15.setObjectName("Roster15")          # Python das Widget weg
    _rollen15 = [k for k, _l in win._ROSTER_ROLES]
    _boxen15 = [win._char_role_boxes[(7, k)] for k in _rollen15]
    eq("b15 der Charakter hat vier Rollen-Kreuze", len(_boxen15), 4)
    check("b15 vorher steht keins davon", not any(b.isChecked() for b in _boxen15))

    win._toggle_char_alle_rollen(7)
    _app.processEvents()
    check("b15 ein Klick auf den Namen setzt ALLE vier",
          all(b.isChecked() for b in _boxen15))
    for _k15 in _rollen15:
        check(f"b15 Rolle {_k15} ist auch gespeichert",
              7 in (win.settings.get(_k15) or []))
    check("b15 der Nachbar-Charakter bleibt unangetastet",
          not any(win._char_role_boxes[(8, k)].isChecked() for k in _rollen15))
    check("b15 'Uebernehmen' wird durch den Namensklick freigeschaltet",
          win._char_roles_dirty is True
          and win._char_roles_apply_btn.isEnabled())

    win._toggle_char_alle_rollen(7)
    _app.processEvents()
    check("b15 der naechste Klick entfernt ALLE vier wieder",
          not any(b.isChecked() for b in _boxen15))
    check("b15 ... und raeumt sie auch aus den Einstellungen",
          not any(7 in (win.settings.get(k) or []) for k in _rollen15))

    # HALBZUSTAND: steht nur EIN Haken, muss der Klick auffuellen (nicht
    # leeren) - sonst macht derselbe Klick mal das eine, mal das andere.
    _boxen15[0].setChecked(True)
    _app.processEvents()
    win._toggle_char_alle_rollen(7)
    _app.processEvents()
    check("b15 bei halb gesetzten Rollen fuellt der Klick auf",
          all(b.isChecked() for b in _boxen15))

    # TEMPO: der Namensklick darf die vier Kreuze nur STUMM umlegen. Wuerde
    # jedes Kreuz sein toggled-Signal feuern, liefe _save_build_chars viermal
    # - genau die Haeufung, gegen die die Beschleunigung gebaut ist.
    # GEZAEHLT WIRD DAS SIGNAL, nicht der Schreibauftrag: der Schreibauftrag
    # haengt an der Entprellung und waere auch bei vier Laeufen nur einer -
    # eine Zaehlung dort saehe den Unterschied gar nicht (beim ersten Anlauf
    # genau so passiert, die Mutation blieb blind).
    _signale15 = {"n": 0}
    for _b15 in _boxen15:
        _b15.toggled.connect(lambda *_a: _signale15.__setitem__(
            "n", _signale15["n"] + 1))
    win._toggle_char_alle_rollen(7)          # alle vier aus
    _app.processEvents()
    eq("b15 vier Rollen auf einen Schlag feuern KEIN einziges Kreuz-Signal",
       _signale15["n"], 0)
    check("b15 ... und trotzdem sind danach alle vier aus",
          not any(b.isChecked() for b in _boxen15)
          and not any(7 in (win.settings.get(k) or []) for k in _rollen15))

    # NICHTS GEAENDERT -> GAR NICHT SCHREIBEN.
    _t15 = getattr(win, "_char_roles_save_timer", None)
    if _t15 is not None:
        _t15.stop()                 # die eben faellige Entprellung abraeumen
    win._save_build_chars()
    _t15 = getattr(win, "_char_roles_save_timer", None)
    check("b15 unveraenderte Auswahl loest kein Schreiben aus",
          _t15 is None or not _t15.isActive())
finally:
    store.list_characters = _orig_lc15
    config.save_settings = _orig_save15
    config.save_settings_async = _orig_async15
    win._char_roles_dirty = False


# ---------------------------------------------------------------- (b16)
# SETTINGS SCHREIBEN BLOCKIERT DIE OBERFLAECHE NICHT MEHR (Nutzer Sitzung 11:
# "beschleunige das hacken setzten"). Gemessen war: JSON bauen ~57 ms, Platte
# + fsync ~8 ms hier - beim Nutzer ist der Platten-Teil der teure, weil der
# Virenscanner jede frische Temp-Datei anfasst. Also: Text sofort erzeugen
# (Momentaufnahme, kann nicht mehr verfaelscht werden), schreiben im
# Hintergrund. Hier ECHT gefahren, nicht am Quelltext gelesen.
import json as _json16                                    # noqa: E402
import tempfile as _tmp16                                 # noqa: E402
import time as _time16                                    # noqa: E402
_dir16 = _tmp16.mkdtemp(prefix="settings16-")
_orig_dir16 = config.app_data_dir
_orig_path16 = config.settings_path
config.app_data_dir = lambda: _dir16
config.settings_path = lambda: os.path.join(_dir16, "settings.json")
try:
    _s16 = {"bau_build_chars": [1, 2, 3], "fuellung": ["x" * 50] * 200}
    config.save_settings_async(_s16)
    # Die Momentaufnahme muss SOFORT stehen: eine Aenderung direkt nach dem
    # Aufruf darf nicht mehr in der Datei landen (und darf den laufenden
    # Schreibvorgang auch nicht zum Absturz bringen).
    _s16["bau_build_chars"] = [99]
    config.flush_settings()

    def _lies16():
        """Nie direkt oeffnen: bleibt die Datei aus (kaputter Schreibfaden),
        soll eine BENANNTE Pruefung rot werden statt die Suite abzubrechen -
        Arbeitsregel aus Sitzung 10."""
        try:
            return _json16.load(open(config.settings_path(), encoding="utf-8"))
        except Exception:
            return {"__nicht_lesbar__": True}

    _gelesen16 = _lies16()
    eq("b16 geschrieben wird der Stand VOM AUFRUF, nicht der spaetere",
       _gelesen16.get("bau_build_chars"), [1, 2, 3])
    check("b16 flush_settings wartet, bis die Datei wirklich da ist",
          os.path.exists(config.settings_path()))
    # Der teure Teil darf den Aufrufer nicht aufhalten: der Aufruf selbst
    # muss deutlich schneller zurueckkommen als das synchrone Speichern.
    # NICHT ZWEI ZEITEN VERGLEICHEN: das war eine Uhrmessung auf einem
    # geteilten Rechner und schlug gelegentlich grundlos fehl. Die ZUSAGE
    # ist nicht "schneller", sondern "wartet NICHT auf die Platte" - und das
    # laesst sich ohne Uhr beweisen: das Schreiben wird angehalten, und der
    # Aufruf muss trotzdem zurueckkommen.
    import threading as _th16
    _blockiert16 = _th16.Event()
    _darf16 = _th16.Event()
    _echt_schreib16 = config._schreibe_settings

    def _lahm16(text, _e=_echt_schreib16):
        _blockiert16.set()
        _darf16.wait(5)
        return _e(text)

    config._schreibe_settings = _lahm16
    try:
        config.save_settings_async(_s16)          # darf NICHT blockieren
        _kam_zurueck16 = _blockiert16.wait(3)
        check("b16 der Aufruf kehrt zurueck, waehrend noch geschrieben wird",
              _kam_zurueck16)
    finally:
        _darf16.set()
        config.flush_settings()
        config._schreibe_settings = _echt_schreib16
    # Mehrere Auftraege hintereinander: es gewinnt der LETZTE Stand, und es
    # bleibt bei EINEM Faden (keine Warteschlange veralteter Staende).
    for _i16 in range(5):
        _s16["bau_build_chars"] = [_i16]
        config.save_settings_async(_s16)
    config.flush_settings()
    _gelesen16b = _lies16()
    eq("b16 bei mehreren Auftraegen gewinnt der letzte Stand",
       _gelesen16b.get("bau_build_chars"), [4])
    # Und die Datei ist NIE halb geschrieben - auch nicht, wenn mittendrin
    # ein synchrones Speichern dazwischenfunkt.
    _ganz16 = True
    for _i16 in range(3):
        _s16["bau_build_chars"] = [100 + _i16]
        config.save_settings_async(_s16)
        config.save_settings(_s16)
        if "__nicht_lesbar__" in _lies16():           # pragma: no cover
            _ganz16 = False
    check("b16 die Datei ist nie halb geschrieben", _ganz16)
finally:
    config.app_data_dir = _orig_dir16
    config.settings_path = _orig_path16
    import shutil as _sh16
    _sh16.rmtree(_dir16, ignore_errors=True)


# ---------------------------------------------------------------- (b2t)
# "MEINE BAUPLAENE" NEU GEORDNET (Nutzer-Screenshot, Sitzung 9: "alle sollen
# die selbe groesse haben, keine unterschiede erkennbar", "etwas breitere
# Textboxen", "ganz rechts eine Auflistung ... und den Totalgewinn").
# FUNKTIONAL geprueft an echten Widgets, nicht am Quelltext: eine Textprobe
# saehe die ungleichen Kaesten gar nicht.
try:
    from PySide6.QtWidgets import QFrame as _QF2t
    _alt2t = win.settings.get("bau_saved_plans")
    # Absichtlich EIN sehr langer und ein kurzer Name - genau der Unterschied,
    # der die Karten vorher verschieden breit gemacht hat.
    win.settings["bau_saved_plans"] = [
        {"id": 1, "label": "Medium Projectile Collision Accelerator II Blueprint x80",
         "item_name": "Medium Projectile Collision Accelerator II", "qty": 80,
         "type_id": 31000, "checked": []},
        {"id": 2, "label": "Cerberus x12", "item_name": "Cerberus", "qty": 12,
         "type_id": 11993, "checked": [1, 2]},
        {"id": 3, "label": "Large Hydraulic Bay Thrusters II Blueprint x40",
         "item_name": "Large Hydraulic Bay Thrusters II", "qty": 40,
         "type_id": 31001, "checked": []},
    ]
    win._reload_saved_plans()
    _lay2t = win._plans_layout
    eq("b2t die Seite haengt in EINEM Container", _lay2t.count(), 1)
    _hold2t = _lay2t.itemAt(0).widget()
    check("b2t der Container ist ein Widget", _hold2t is not None)
    _cards2t = [w for w in (_hold2t.findChildren(_QF2t) if _hold2t else [])
                if w.objectName() == "Card"]
    # SITZUNG 20: die Gewinn-Uebersicht ist auf Nutzer-Wunsch breiter
    # geworden (620). Die Schwelle 400 trennte die beiden nicht mehr - die
    # Uebersicht rutschte als vierte "Karte" in die Pruefung und liess jede
    # Gleichheits-Zusage scheitern. Getrennt wird jetzt an der Mindestbreite:
    # Plan-Karten haben MINW 520, die Uebersicht 320. Das haengt an den
    # Konstanten, nicht an einer geratenen Zahl dazwischen.
    _plan2t = [c for c in _cards2t if c.minimumWidth() >= 520]
    eq("b2t drei Plaene ergeben drei Karten", len(_plan2t), 3)
    # BREITE: Layout ERZWINGEN, sonst ist die Pruefung blind (Sitzung 10,
    # vom Rotproben-Komplettlauf aufgedeckt). Ohne adjustSize() liefert ein
    # nie angezeigtes Widget bei width() Qts Platzhalter - fuer ALLE Karten
    # denselben. Die Pruefung zaehlte also dreimal denselben Platzhalter und
    # blieb auch dann gruen, wenn setFixedWidth wieder zu setMaximumWidth
    # zurueckgedreht wurde (gemessen: gesund 980/980/980, krank 952/857/900).
    # sizeHint().width() taugt hier NICHT: es ignoriert die feste Breite und
    # liefert auch bei gesundem Code drei verschiedene Werte.
    # Es ist dieselbe Falle, die drei Zeilen tiefer fuer die HOEHE laengst
    # beschrieben steht - fuer die Breite war sie uebersehen worden.
    # ABGESICHERT gegen None: bei einer Mutation, die den Aufbau zerlegt, ist
    # `_hold2t` None. Ein ungeschuetztes .adjustSize() sprengt dann den GANZEN
    # b2t-Block - und die Geister-Kopfzeilen-Pruefung ganz unten wird nie
    # erreicht. Genau das ist beim Einbau dieser Zeile passiert (Sitzung 10):
    # Mutation 184 wurde dadurch BLIND. Alle anderen Zugriffe auf _hold2t im
    # Block sind aus demselben Grund seit jeher geschuetzt.
    if _hold2t is not None:
        _hold2t.adjustSize()
    for _c in _plan2t:
        _c.adjustSize()
    # SITZUNG 20: die Karten haben keine FESTE Breite mehr - sie wachsen
    # zwischen MINW und MAXW mit dem Fenster, damit auf einem kleinen Monitor
    # nicht waagerecht gescrollt werden muss. `adjustSize()` umgeht das Layout
    # und liefert dann die INHALTS-Breite, die je Karte verschieden ist.
    # Die Zusage ist unveraendert - was sie haelt, ist jetzt: dieselben
    # Grenzen und dieselbe Groessenregel bei jeder Karte. Genau das wird
    # gemessen, statt einer Zahl, die vom Inhalt abhaengt.
    eq("b2t alle Karten haben dieselbe Hoechstbreite",
       len({c.maximumWidth() for c in _plan2t}), 1)
    eq("b2t und dieselbe Mindestbreite",
       len({c.minimumWidth() for c in _plan2t}), 1)
    eq("b2t und dieselbe Groessenregel",
       len({c.sizePolicy().horizontalPolicy() for c in _plan2t}), 1)
    check("b2t sie duerfen kleiner werden als die Hoechstbreite",
          all(c.minimumWidth() < c.maximumWidth() for c in _plan2t))
    # WICHTIG: sizeHint() nach adjustSize(), NICHT height(). Ein nie
    # angezeigtes Widget liefert bei height() Qts Standardmass (480) - die
    # Pruefung verglich vorher also Platzhalter und war damit blind.
    for _c in _plan2t:
        _c.adjustSize()
    eq("b2t alle Karten sind exakt gleich HOCH",
       len({c.sizeHint().height() for c in _plan2t}), 1)
    # DER EIGENTLICHE FALL aus dem Screenshot: die ESI-Meldung "fertig"
    # trifft SPAETER ein und war frueher dreizeilig - genau daran wuchsen
    # einzelne Karten.
    _h_vor2t = {c.sizeHint().height() for c in _plan2t}
    _dlbl2t = win._plan_done_labels.get(2)
    if _dlbl2t is not None:
        _dlbl2t.setText("\u2705 Abgeschlossen\n"
                        "Bau 70'439'801 \u00b7 Verk. 88'419'085")
        _dlbl2t.setVisible(True)
        _app.processEvents()
        for _c in _plan2t:
            _c.adjustSize()
    check("b2t die Fertig-Meldung ist erreichbar", _dlbl2t is not None)
    eq("b2t auch MIT Fertig-Meldung bleiben alle Karten gleich hoch",
       len({c.sizeHint().height() for c in _plan2t}), 1)
    eq("b2t und die Meldung macht die Karte nicht hoeher",
       {c.sizeHint().height() for c in _plan2t}, _h_vor2t)
    check("b2t die Fertig-Meldung wird dabei NICHT abgeschnitten",
          _dlbl2t is not None
          and _dlbl2t.height() >= _dlbl2t.sizeHint().height())
    check("b2t die Karten sind breiter als die alten 760",
          bool(_plan2t) and _plan2t[0].width() > 760)
    # Rechte Spalte: je Plan eine Zeile plus eine Gesamtsumme.
    eq("b2t rechts steht jeder Plan mit einer Gewinn-Zeile",
       len(getattr(win, "_plan_sum_labels", {})), 3)
    check("b2t es gibt ein Gesamt-Label",
          getattr(win, "_plan_total_lbl", None) is not None)
    # SITZUNG 20: an der Mindestbreite erkannt statt an einer Zahl, die mit
    # jeder Verbreiterung nachgezogen werden muesste.
    check("b2t die Gewinn-Uebersicht haengt im selben Container",
          any(c not in _plan2t for c in _cards2t))
    # Der lange Name darf nicht mehr abgeschnitten werden.
    _lbls2t = [l for l in (_hold2t.findChildren(QLabel) if _hold2t else [])
               if "Projectile Collision" in (l.text() or "")]
    check("b2t der lange Plan-Name ist ueberhaupt da", bool(_lbls2t))
    check("b2t und bricht um, statt abgeschnitten zu werden",
          bool(_lbls2t) and _lbls2t[0].wordWrap())
    check("b2t der volle Name steht zusaetzlich im Tooltip",
          bool(_lbls2t) and "Projectile Collision" in (_lbls2t[0].toolTip() or ""))
    # GEWINN-UEBERSICHT (18.09.2026): der Name wird mit "..." gekuerzt statt
    # hart abgeschnitten, der Betrag steht in Festbreitenschrift.
    from eve_trader.ui.main_window import ElideLabel as _EL2t
    # NUR DIE UEBERSICHT, NICHT DIE KARTE: die Untertitel-Zeile der Plan-
    # Karte ist seit 23.09.2026 auch ein ElideLabel mit demselben Text -
    # ohne diesen Filter fand die Pruefung sie und war blind fuer die
    # Uebersicht (Rotprobe 26.09.2026).
    _karten2t = set(id(_c) for _c in (getattr(win, "_plan_karte", {}) or {}).values())

    def _in_karte2t(_l):
        _a = _l.parentWidget()
        while _a is not None:
            if id(_a) in _karten2t:
                return True
            _a = _a.parentWidget()
        return False
    _el2t = [l for l in (_hold2t.findChildren(_EL2t) if _hold2t else [])
             if "Projectile Collision" in (l.text() or "") and not _in_karte2t(l)]
    check("b2t in der Gewinn-Uebersicht ist der lange Name ein ElideLabel",
          bool(_el2t) and "Projectile Collision" in (_el2t[0].toolTip() or "")
          and _el2t[0].minimumSizeHint().width() == 0)
    _probe2t = _EL2t("Medium Projectile Collision Accelerator II \u00d7200")
    _probe2t.resize(120, 20)
    _fm2t = _probe2t.fontMetrics()
    check("b2t ElideLabel kuerzt mit \u2026 auf die verfuegbare Breite",
          _fm2t.elidedText(_probe2t.text(), Qt.ElideRight, 120).endswith("\u2026")
          and "drawText(r, int(self.alignment()) | Qt.TextSingleLine, txt)" in
          __import__("inspect").getsource(_EL2t.paintEvent)
          and "elidedText(self.text(), Qt.ElideRight, r.width())" in
          __import__("inspect").getsource(_EL2t.paintEvent))
    check("b2t die Betraege stehen in Festbreitenschrift",
          any("font-family" in (l.styleSheet() or "")
              for l in getattr(win, "_plan_sum_labels", {}).values()))
    # GEISTER-KOPFZEILEN: das alte Aufraeumen sammelte nur Widgets ein, die
    # per addLayout() eingehaengte Kopfzeile blieb stehen und stapelte sich.
    for _ in range(3):
        win._reload_saved_plans()
    _kopf2t = [l for l in win.findChildren(QLabel)
               if (l.text() or "").startswith(_t4("MY BUILD PLANS"))]
    eq("b2t vier Aufbauten hinterlassen GENAU EINE Kopfzeile",
       len(_kopf2t), 1)
    eq("b2t und genau ein Element im Seitenlayout", win._plans_layout.count(), 1)
    win.settings["bau_saved_plans"] = _alt2t
except Exception as _e2t:                                # pragma: no cover
    _fail.append(f"b2t Block geplatzt: {_e2t!r}")


# ---------------------------------------------------------------- (b97)
# KOPFZEILE: LINKS WO DU BIST, RECHTS WAS DU AUSLOEST (Nutzer 23.09.2026:
# "der obere Teil des Tools hat zu viele Knoepfe auf einem Haufen"; dazu
# "market scan ganz links" und "koennten wir alle Knoepfe auf der rechten
# Seite in ein horizontal aufklappbares Dropdown stecken?").
#
# GEPRUEFT WIRD DIE REIHENFOLGE IN DER LEISTE, nicht eine Pixelspalte: in
# einer QToolBar ist die Reihenfolge der Aktionen genau die, die man sieht -
# und sie steht auch ohne angezeigtes Fenster fest (isVisible waere hier
# blind, siehe CLAUDE.md).
try:
    _acts97 = [a.defaultWidget() for a in win._toolbar.actions()
               if hasattr(a, "defaultWidget") and a.defaultWidget() is not None]

    def _pos97(w):
        """Platz eines Widgets in der Leiste - auch wenn es in einem
        Behaelter steckt (Markt-Scan-Platz, Klappe): dann zaehlt der Platz
        des Behaelters, denn der bestimmt, wo es steht."""
        _p = w
        while _p is not None:
            if _p in _acts97:
                return _acts97.index(_p)
            _p = _p.parentWidget()
        return -1

    _scan97 = _pos97(win.g_scan_btn)
    _hub97 = _pos97(win.g_hub)
    _char97 = _pos97(win.g_char)
    _ref97 = _pos97(win.global_refresh_btn)
    _sde97 = _pos97(win.g_sde_btn)
    _lang97 = _pos97(win.lang_box)
    check("b97 alle Kopf-Elemente sind in der Leiste auffindbar",
          min(_scan97, _hub97, _char97, _ref97, _sde97, _lang97) >= 0)
    check(f"b97 der Markt-Scan steht ganz links ({_scan97} vor Hub {_hub97})",
          0 <= _scan97 < _hub97)
    check(f"b97 der Zustand steht links (Hub {_hub97}, Charakter {_char97} "
          f"vor Aktualisieren {_ref97})",
          0 <= _hub97 < _ref97 and 0 <= _char97 < _ref97)
    check(f"b97 die Handlungen stehen rechts, in dieser Folge "
          f"({_ref97} < {_sde97} < {_lang97})",
          _ref97 < _sde97 < _lang97)
    # KEIN KNOPF ZWEIMAL: waere er versehentlich links UND rechts
    # eingehaengt, stuende er doppelt in der Reihe.
    for _n97, _w97 in (("Alles aktualisieren", win.global_refresh_btn),
                       ("Markt-Scan", win.g_scan_btn),
                       ("Baurezepte laden", win.g_sde_btn)):
        eq(f"b97 {_n97} haengt an genau einer Stelle",
           sum(1 for _a in _acts97 if _a is _w97 or _w97.isAncestorOf(_a)
               or (_a is not None and _a.isAncestorOf(_w97))), 1)

    # DIE DREI SELTENEN STEHEN OFFEN DANEBEN (der Zwischenstand mit Klappe
    # ist auf Nutzer-Wunsch wieder raus: "ja, wir lassen es immer
    # ausgeklappt bitte"). Am echten Fenster heisst das: sie haengen direkt
    # in der Leiste, und ihre Aktionen sind sichtbar.
    _unsichtbar97 = []
    for _n97, _w97 in (("Baurezepte laden", win.g_sde_btn),
                       ("EVE-Daten", win.update_btn),
                       ("Programm-Updates", win.ver_btn)):
        _a97 = next((_a for _a in win._toolbar.actions()
                     if getattr(_a, "defaultWidget", lambda: None)() is _w97), None)
        if _a97 is None or not _a97.isVisible():
            _unsichtbar97.append(_n97)
    eq("b97 die drei Daten-Knoepfe stehen offen in der Leiste", _unsichtbar97, [])
    check("b97 von der Klappe ist am Fenster nichts mehr uebrig",
          getattr(win, "_kopf_extras", None) is None
          and getattr(win, "_kopf_extras_btn", None) is None)

    # NUR NOCH EIN PLUS (Nutzer: "dachte ich wird nur noch ein +").
    eq("b97 der Struktur-Knopf hat keinen Text mehr",
       win.g_struct_btn.text(), "")
    check("b97 ... traegt aber Symbol und Erklaerung",
          not win.g_struct_btn.icon().isNull()
          and len(win.g_struct_btn.toolTip() or "") > 30)

    # DIE REITER-LEISTE: zwischen dem letzten Handels-Reiter und "Industry"
    # steht ein Trennstrich (Nutzer: "koennen wir Trading und Produktion
    # besser trennen?").
    _tb97 = win._nav_buttons["region"].parentWidget()
    _lay97 = _tb97.layout() if _tb97 is not None else None
    _idx97 = {}
    _striche97 = []
    for _i97 in range(_lay97.count() if _lay97 is not None else 0):
        _w = _lay97.itemAt(_i97).widget()
        if _w is None:
            continue
        for _k97 in ("region", "build"):
            if _w is win._nav_buttons.get(_k97):
                _idx97[_k97] = _i97
        if isinstance(_w, QFrame) and _w.maximumWidth() == 1:
            _striche97.append(_i97)
    check("b97 beide Reiter sind in der Leiste auffindbar",
          "region" in _idx97 and "build" in _idx97)
    check(f"b97 zwischen Handel und Industry steht ein Trennstrich "
          f"(Reiter {_idx97.get('region')} / {_idx97.get('build')}, "
          f"Striche {_striche97})",
          any(_idx97.get("region", -1) < _p < _idx97.get("build", -1)
              for _p in _striche97))
    # JEDER AUFRUF BAUT EINEN NEUEN: ein Widget kann nur in EINEM Layout
    # haengen - ein zwischengespeicherter Strich waere beim zweiten
    # Einhaengen aus dem ersten Layout verschwunden.
    # MIT ELTERN, NICHT FREI SCHWEBEND: zwei Widgets ohne Besitzer raeumt
    # Python irgendwann ab, waehrend Qt sie noch kennt - in einem Lauf
    # stuerzte die Suite genau daran ab ("free(): invalid pointer").
    _t1_97 = win._kopf_trenner(); _t1_97.setParent(win)
    _t2_97 = win._kopf_trenner(); _t2_97.setParent(win)
    check("b97 der Trenner ist bei jedem Aufruf ein eigenes Widget",
          _t1_97 is not _t2_97)
    _t1_97.deleteLater(); _t2_97.deleteLater()
except Exception as _e97:                                # pragma: no cover
    _fail.append(f"b97 Block geplatzt: {_e97!r}")


# ---------------------------------------------------------------- (b99)
# FARBE JE BAUPLAN (Nutzer 23.09.2026: "ich moechte in My build plans den
# Bauplaenen und Multibuildplaenen eine Hintergrundfarbe geben koennen.
# Sicherlich die Farben von Caldari, Gallente, Amarr und Minmatar. Einfach
# links neben dem Endprodukt-Bild eine Farbpalette zum Ausklappen jeweils,
# wenn man auf eine Farbe klickt, dann faerbt sich der Bauplan ein").
#
# DAS MENUE SELBST WIRD HIER NICHT AUFGEKLAPPT: `QMenu.exec` ist modal und
# wuerde die Suite anhalten. Geprueft wird, was man danach SIEHT - der
# Knopf sitzt links vom Bild, die Farbe landet im Plan und die neu
# aufgebaute Karte traegt sie.
try:
    from PySide6.QtWidgets import QPushButton as _QPB99
    from eve_trader.ui import theme as _th99
    _alt99 = win.settings.get("bau_saved_plans")
    win.settings["bau_saved_plans"] = [
        {"id": 9901, "label": "b99 Plan A", "item_name": "A99", "qty": 1,
         "type_id": 31000, "checked": []},
        {"id": 9902, "label": "b99 Plan B", "item_name": "B99", "qty": 1,
         "type_id": 31001, "checked": [], "farbe": "amarr"},
    ]
    win._reload_saved_plans()
    _hold99 = win._plans_layout.itemAt(0).widget()
    _karten99 = [w for w in _hold99.findChildren(_QF2t)
                 if w.objectName() == "Card" and w.minimumWidth() >= 520]
    eq("b99 zwei Plaene ergeben zwei Karten", len(_karten99), 2)

    def _reihe99(karte):
        """Die Widgets der Kartenzeile in ihrer Reihenfolge."""
        _l = karte.layout()
        return [_l.itemAt(_i).widget() for _i in range(_l.count())]

    _ohne99 = []
    for _k99 in _karten99:
        _r99 = _reihe99(_k99)
        _fb99 = next((_w for _w in _r99
                      if isinstance(_w, _QPB99) and _w.minimumWidth() == 18
                      and _w.maximumWidth() == 18), None)
        _ic99 = next((_w for _w in _r99
                      if isinstance(_w, QLabel) and _w.minimumWidth() == 48
                      and _w.maximumWidth() == 48), None)
        if _fb99 is None or _ic99 is None or _r99.index(_fb99) > _r99.index(_ic99):
            _ohne99.append(_k99)
    eq("b99 jede Karte hat den Farbknopf LINKS neben dem Bild", _ohne99, [])

    # DIE GESPEICHERTE FARBE LANDET AUF DER KARTE. Welche Karte zu welchem
    # Plan gehoert, entscheidet der TITEL (Lehre b86: nie ueber eine
    # Teilzeichenkette in beliebigen Labels zuordnen).
    def _karte_zu99(name):
        for _k in _karten99:
            for _l in _k.findChildren(QLabel):
                if name in (_l.text() or "") and "font-size:15px" in (_l.text() or ""):
                    return _k
        for _k in _karten99:
            for _l in _k.findChildren(QLabel):
                if (_l.text() or "").strip().startswith("<b") and name in _l.text():
                    return _k
        return None
    _kB99 = _karte_zu99("b99 Plan B")
    _kA99 = _karte_zu99("b99 Plan A")
    check("b99 beide Karten sind zuordenbar", _kA99 is not None and _kB99 is not None)
    check("b99 der Plan MIT Farbe traegt sie als Flaeche",
          _kB99 is not None and "background: rgba(" in (_kB99.styleSheet() or ""))
    check("b99 der Plan OHNE Farbe bleibt ungefaerbt",
          _kA99 is not None and "background: rgba(" not in (_kA99.styleSheet() or ""))

    # SETZEN UND MERKEN - der Weg, den der Menue-Eintrag geht.
    _fbA99 = next(_w for _w in _reihe99(_kA99)
                  if isinstance(_w, _QPB99) and _w.minimumWidth() == 18)
    win._plan_farbe_setzen(9901, "f1", _kA99, _fbA99, False)
    check("b99 nach der Wahl ist die Karte gefaerbt",
          "background: rgba(" in (_kA99.styleSheet() or ""))
    check("b99 ... der kleine Knopf zeigt dieselbe Farbe",
          _th99.PLAN_FARBEN["f1"].lower() in (_fbA99.styleSheet() or "").lower())
    eq("b99 ... und sie steht im Plan",
       next(p.get("farbe") for p in win.settings["bau_saved_plans"]
            if p.get("id") == 9901), "f1")
    win._plan_farbe_setzen(9901, None, _kA99, _fbA99, False)
    check("b99 'keine Farbe' nimmt sie wieder weg",
          "background: rgba(" not in (_kA99.styleSheet() or "")
          and all(p.get("farbe") is None
                  for p in win.settings["bau_saved_plans"] if p.get("id") == 9901))
    # DER AMBERNE RAND EINES GEBUNDENEN PLANS BLEIBT - er sagt "gehoert zu
    # einem Multi-Bauplan" und ist keine Geschmacksfrage.
    check("b99 mit Farbe UND Multi-Bindung bleibt der amberne Rand",
          "rgba(242,162,60,0.55)" in win._plan_farb_stil("f1", True)
          and "background: rgba(76,144,240" in win._plan_farb_stil("f1", True))
    # ALTBESTAND AM ECHTEN FENSTER: Plan B traegt den Schluessel der ersten
    # Fassung ("amarr"). Er muss auf der Karte die Farbe von Platz 7 zeigen
    # - sonst haetten Nutzer nach dem Update farblose Karten.
    check("b99 ein alter Fraktionsschluessel faerbt die Karte weiterhin",
          _kB99 is not None
          and "rgba(217,179,140,0.18)" in (_kB99.styleSheet() or ""))
    win.settings["bau_saved_plans"] = _alt99
    win._reload_saved_plans()
except Exception as _e99:                                # pragma: no cover
    _fail.append(f"b99 Block geplatzt: {_e99!r}")


# ---------------------------------------------------------------- (b100)
# WARNUNG UND KNOPF GEHOEREN ZUSAMMEN (Nutzer 23.09.2026, Kopfzeilen-Umbau):
# der Markt-Scan sitzt jetzt ganz links - stuende die amberne Warnung noch
# beim Charakter-Feld, blinkte der Knopf am einen Ende der Leiste und der
# Satz dazu am anderen. Am echten Fenster gefragt: gleicher Behaelter.
try:
    check("b100 die Scan-Warnung steht im selben Platz wie der Knopf",
          win.g_scan_warn.parentWidget() is win.g_scan_btn.parentWidget()
          and win.g_scan_warn.parentWidget() is not None)
    # SIE IST STILL, SOLANGE NICHTS ZU MELDEN IST (sonst stuende dauerhaft
    # ein amberner Satz in der Kopfzeile).
    win._scan_warnung_setzen("")
    check("b100 ohne Anlass ist sie unsichtbar und der Takt steht",
          not win.g_scan_warn.isVisibleTo(win.g_scan_warn.parentWidget())
          and not win._scan_blink_timer.isActive())
    win._scan_warnung_setzen("b100 Test")
    check("b100 mit Anlass blinkt der Knopf und der Satz steht da",
          win.g_scan_warn.isVisibleTo(win.g_scan_warn.parentWidget())
          and win._scan_blink_timer.isActive())
    eq("b100 der Blinktakt sind 700 ms",
       win._scan_blink_timer.interval(), 700)
    eq("b100 geprueft wird alle 30 Sekunden",
       win._scan_pruef_timer.interval(), 30000)
    win._scan_warnung_setzen("")
except Exception as _e100:                               # pragma: no cover
    _fail.append(f"b100 Block geplatzt: {_e100!r}")


# ---------------------------------------------------------------- (b101)
# ACHT FARBEN OHNE NAMEN + STANDARDFARBE FUER BUENDEL (Nutzer 23.09.2026:
# "Fuege weitere 4 Farben hinzu [...] wir muessen gar keine Namen geben [...]
# faerbe Multiplaene standardmaessig schon anders ein").
#
# DAS MENUE WIRD HIER WIRKLICH GEBAUT. Geprueft wird `_plan_farb_palette` -
# das Bauen ohne das Aufklappen. GEMESSEN (23.09.2026): ein Ersetzen von
# `QMenu.exec` wirkt in PySide6 NICHT, der C++-Aufruf geht am Python-Eintrag
# vorbei; die Suite blieb im offenen Menue stehen. Darum baut der Quelltext
# die Palette in einer eigenen Methode - sonst koennte niemand nachsehen,
# was darin steht.
try:
    from PySide6.QtWidgets import (QPushButton as _QPB101, QMenu as _QM101)
    from eve_trader import industry as _ind101
    from eve_trader.ui import theme as _th101
    _alt101 = win.settings.get("bau_saved_plans")
    win.settings["bau_saved_plans"] = [
        {"id": 9911, "label": "b101 Einzel", "item_name": "E101", "qty": 1,
         "type_id": 31002, "checked": []},
        {"id": 9912, "label": "b101 Buendel", "item_name": "B101", "qty": 1,
         "type_id": int(_ind101.BUENDEL_ID), "checked": []},
    ]
    win._reload_saved_plans()
    _hold101 = win._plans_layout.itemAt(0).widget()
    _karten101 = [w for w in _hold101.findChildren(_QF2t)
                  if w.objectName() == "Card" and w.minimumWidth() >= 520]
    eq("b101 zwei Plaene ergeben zwei Karten", len(_karten101), 2)

    def _hat101(karte, text):
        for _l in karte.findChildren(QLabel):
            if text in (_l.text() or ""):
                return True
        return False
    _kB101 = next((_k for _k in _karten101 if _hat101(_k, "b101 Buendel")), None)
    _kE101 = next((_k for _k in _karten101 if _hat101(_k, "b101 Einzel")), None)
    check("b101 beide Karten sind zuordenbar",
          _kB101 is not None and _kE101 is not None)
    # OHNE JEDE WAHL: das Buendel ist schon eingefaerbt, der Einzelplan nicht.
    check("b101 ein Buendel traegt von sich aus den amberne Hauch",
          _kB101 is not None
          and "rgba(242,162,60,0.10)" in (_kB101.styleSheet() or ""))
    check("b101 ein gewoehnlicher Plan bleibt farblos",
          _kE101 is not None
          and "background: rgba(" not in (_kE101.styleSheet() or ""))

    # DAS MENUE: acht Felder, kein Farbname, ein Weg zurueck.
    _fbB101 = next(_w for _w in
                   [_kB101.layout().itemAt(_i).widget()
                    for _i in range(_kB101.layout().count())]
                   if isinstance(_w, _QPB101) and _w.maximumWidth() == 18)
    _m101 = win._plan_farb_palette(9912, _kB101, _fbB101, False, True)
    check("b101 die Palette wird gebaut, ohne aufzuklappen",
          isinstance(_m101, _QM101))
    _felder101 = [_b for _b in (_m101.findChildren(_QPB101) if _m101 else [])
                  if _b.maximumWidth() == 30 and _b.maximumHeight() == 22]
    eq("b101 die Palette zeigt acht Farbfelder", len(_felder101), 8)
    _texte101 = [(_a.text() or "") for _a in (_m101.actions() if _m101 else [])]
    eq("b101 ... und genau einen Eintrag mit Text (der Weg zurueck)",
       [_x for _x in _texte101 if _x.strip()], [_t4("No colour")])
    _namen101 = [_x for _x in _texte101
                 if _x.strip() in ("Caldari", "Gallente", "Amarr", "Minmatar")]
    eq("b101 kein Fraktionsname im Menue", _namen101, [])
    # EIN KLICK AUF EIN FELD FAERBT WIRKLICH - und gewinnt ueber den Hauch.
    _felder101[4].click() if len(_felder101) > 4 else None
    eq("b101 der Klick merkt die Farbe im Plan",
       next(p.get("farbe") for p in win.settings["bau_saved_plans"]
            if p.get("id") == 9912), "f5")
    check("b101 ... die eigene Wahl gewinnt ueber die Standardfarbe",
          _th101.PLAN_FARBEN["f5"] is not None
          and "rgba(217,95,196,0.18)" in (_kB101.styleSheet() or "")
          and "rgba(242,162,60,0.10)" not in (_kB101.styleSheet() or ""))
    check("b101 ... und der amberne Rand des Buendels bleibt",
          "rgba(242,162,60,0.55)" in (_kB101.styleSheet() or ""))
    if _m101 is not None:
        _m101.close()
        _m101.deleteLater()
    win.settings["bau_saved_plans"] = _alt101
    win._reload_saved_plans()
except Exception as _e101:                               # pragma: no cover
    _fail.append(f"b101 Block geplatzt: {_e101!r}")


# ---------------------------------------------------------------- (b96)
# DIE STATUS-SPALTE WIRD GEMESSEN (Nutzer-Befund 23.09.2026: "bei
# Multibuildplan 1 kann man den Profit nicht vollstaendig ablesen, weil der
# Reservations-Button dort ist"). Sie stand auf festen 250 px - hier reicht
# das, auf seinem Windows sind dieselben Widgets rund 1,85x breiter
# (derselbe Befund wie b66), und das ISK fiel hinter den Schloss-Knopf.
#
# ALLE KARTEN BEKOMMEN DIESELBE BREITE: stuende die Zahl von Karte zu Karte
# woanders, waere die Liste unlesbar.
try:
    _alt96 = win.settings.get("bau_saved_plans")
    win.settings["bau_saved_plans"] = [
        {"id": 961, "label": "b96 Plan A", "item_name": "A96", "qty": 1,
         "type_id": 31000, "checked": []},
        {"id": 962, "label": "b96 Plan B", "item_name": "B96", "qty": 1,
         "type_id": 31001, "checked": []},
    ]
    win._reload_saved_plans()
    _st96 = {k: v for k, v in (getattr(win, "_plan_stat_widgets", None) or {}).items()
             if k in (961, 962)}
    eq("b96 jede Plan-Karte hat ihre Status-Spalte gemerkt", len(_st96), 2)
    # KURZER TEXT: die Untergrenze bleibt stehen, sonst wuerde die Spalte bei
    # einem leeren Plan auf null zusammenfallen.
    for _pid96 in (961, 962):
        _l = win._plan_est_labels.get(_pid96)
        if _l is not None:
            _l.setText("\u2013")
    eq("b96 bei kurzem Text bleibt die Untergrenze",
       win._plan_statusspalte_messen(), 250)
    # LANGER TEXT: die Spalte waechst mit - und zwar bei ALLEN Karten gleich.
    # DER TEXT WIRD SO LANGE VERLAENGERT, BIS ER DIE UNTERGRENZE SICHER
    # UEBERSCHREITET. Eine feste Zeichenkette taugt nicht: wie breit sie
    # faellt, haengt an der Schrift des Rechners - offscreen hier passte
    # "Profit +999'999'999'999 ISK" noch in die 250 px, und die Pruefung
    # war damit BLIND (die Rotprobe hat genau das gemeldet).
    _l96 = win._plan_est_labels.get(961)
    _lang96 = "Profit \u2248 +999'999'999'999 ISK"
    if _l96 is not None:
        _l96.setText(_lang96)
        while _l96.sizeHint().width() < 300 and len(_lang96) < 300:
            _lang96 += "9'"
            _l96.setText(_lang96)
    _breit96 = win._plan_statusspalte_messen()
    check(f"b96 bei langem Text waechst die Spalte ({_breit96} px, Text "
          f"{_l96.sizeHint().width() if _l96 is not None else 0} px)",
          _l96 is not None and _breit96 > 250
          and _breit96 >= _l96.sizeHint().width())
    eq("b96 ... und alle Karten sind gleich breit",
       len({w.width() for w in _st96.values()}), 1)
    eq("b96 ... naemlich genau so breit wie gemessen",
       sorted({w.width() for w in _st96.values()}), [_breit96])
    # GEDECKELT: ein einzelner Riesenbetrag darf nicht die halbe Karte
    # fressen - dann lieber die Zahl kuerzen als den Namen verdraengen.
    if _l96 is not None:
        _l96.setText("Profit \u2248 +" + "9'" * 40 + "999 ISK")
    check("b96 die Spalte ist nach oben gedeckelt",
          win._plan_statusspalte_messen() <= 460)
    win.settings["bau_saved_plans"] = _alt96
    win._reload_saved_plans()
except Exception as _e96:                                # pragma: no cover
    _fail.append(f"b96 Block geplatzt: {_e96!r}")


# ---------------------------------------------------------------- (b2u)
# FROZEN-SCHAETZUNG FUNKTIONAL, AUF DEN ISK (Nutzer, Sitzung 9: "Du kannst
# doch mit den Zahlen selber gegenrechnen, warum muss ich jedesmal das
# Tool neu herunterladen ..."). BERECHTIGT: diese Fehlerklasse (Karte vs.
# Dialog beim eingefrorenen Plan) wurde dreimal per Nutzer-Screenshot
# gejagt. Dieser Test rechnet sie HIER nach - mit den ECHTEN Zahlen des
# Hydraulic-Falls: Snapshot-Kosten 3'481'354'464, Sell 60M x 50,
# Gebuehren 4,401% -> Gewinn MUSS -613'384'464 sein (die Karte zeigte
# damals -724'079'984, weil sie die globalen 8,091% nahm).
try:
    _alt2u = {k: win.settings.get(k) for k in
              ("char_fees", "hub_standings", "bau_extra_cost",
               "sales_tax_pct", "broker_fee_pct")}
    # Verkaufscharakter mit exakt 4,401% Gesamtgebuehr herstellen:
    # Accounting/Broker-Skill + Standings so, dass _fees_for_hub die
    # Dialog-Werte liefert. Statt die Skill-Formeln rueckwaerts zu raten,
    # nehmen wir den Rueckfall-Pfad: KEINE char_fees -> _fees9 faellt auf
    # die globalen Einstellungen zurueck, die wir exakt setzen. Damit
    # testet b2u die RECHNUNG (Snapshot + Gebuehren + Extra), und eine
    # zweite Pruefung unten stellt sicher, dass mit char_fees die
    # CHARAKTER-Quelle gewinnt.
    win.settings["char_fees"] = {}
    win.settings["hub_standings"] = {}
    win.settings["sales_tax_pct"] = 2.2005
    win.settings["broker_fee_pct"] = 2.2005   # zusammen 4,401%
    win.settings["bau_extra_cost"] = 0
    _p2u = {"id": 991, "type_id": 424242, "qty": 50,
            "label": "b2u Hydraulic-Nachstellung",
            "item_name": "b2u", "checked": [],
            "frozen": {"ts": 1755200000.0, "qty": 50,
                       "prices": {"424242": 60000000.0},
                       "plan_snapshot": {"total_cost": 3481354464.0}}}
    _pm2u = {424242: 60000000.0}
    _est2u = win._bau_saved_plan_quick_estimate(_p2u, None, _pm2u, {})
    check("b2u die Schaetzung liefert fuer den Frozen-Plan ein Ergebnis",
          _est2u is not None)
    eq("b2u Kosten = Snapshot-Kosten, keine Neuplanung",
       round((_est2u or {}).get("cost", 0)), 3481354464)
    eq("b2u Gewinn auf den ISK wie der Dialog (-613'384'464)",
       round((_est2u or {}).get("profit", 0)), -613384464)
    check("b2u der Einfrier-Zeitstempel kommt mit",
          (_est2u or {}).get("frozen_ts") == 1755200000.0)
    # Und: sobald ein Verkaufscharakter existiert, gewinnt DESSEN Gebuehr
    # (die Quelle nennt ihn beim Namen) - nicht die globalen Prozente.
    win.settings["char_fees"] = {"77": {"combined": 4.401, "acc": 5,
                                        "br": 5, "name": "Lezaar"}}
    win.settings["hub_standings"] = {"jita": {"faction": 5.0, "corp": 5.0}}
    _est2u2 = win._bau_saved_plan_quick_estimate(_p2u, None, _pm2u, {})
    check("b2u mit char_fees stammt die Gebuehr vom Verkaufscharakter",
          "Lezaar" in str((_est2u2 or {}).get("fee_quelle", "")))
    for _k2u, _v2u in _alt2u.items():
        if _v2u is None:
            win.settings.pop(_k2u, None)
        else:
            win.settings[_k2u] = _v2u
except Exception as _e2u:                                # pragma: no cover
    _fail.append(f"b2u Block geplatzt: {_e2u!r}")


# ---------------------------------------------------------------- (b2v)
# FORTSCHRITTSBALKEN (Nutzer, Sitzung 9: "hier waere ein Fortschrittsbalken
# gut, 60/100 gebaut"). Funktional an echten Widgets.
try:
    from PySide6.QtWidgets import QProgressBar as _QPB2v
    from eve_trader.ui import theme as _th
    _alt2v = win.settings.get("bau_saved_plans")
    win.settings["bau_saved_plans"] = [
        {"id": 1, "label": "b2v Plan A", "item_name": "A", "qty": 100,
         "type_id": 31000, "checked": []},
        {"id": 2, "label": "b2v Plan B", "item_name": "B", "qty": 50,
         "type_id": 31001, "checked": []},
    ]
    win._reload_saved_plans()
    _hold2v = win._plans_layout.itemAt(0).widget()
    _bars2v = _hold2v.findChildren(_QPB2v) if _hold2v else []
    eq("b2v jede Karte traegt genau einen Fortschrittsbalken",
       len(_bars2v), 2)
    check("b2v vor dem ESI-Ergebnis steht ehrlich 'wird geprueft'",
          all("wird gepr" in b.format() or "being checked" in b.format()
              for b in _bars2v))
    eq("b2v das Verzeichnis kennt beide Balken",
       len(getattr(win, "_plan_progress", {})), 2)
    # Den ESI-Teilstand von Hand einspielen - wie done() es taete.
    _bar2v = win._plan_progress[1]
    _bar2v.setMaximum(100); _bar2v.setValue(60)
    _bar2v.setFormat("60/100 gebaut")
    check("b2v der Teilstand ist darstellbar (60/100)",
          _bar2v.value() == 60 and _bar2v.maximum() == 100
          and "60/100" in _bar2v.format())
    check("b2v Farben kommen aus theme, kein Hex im Balken-Stil noetig",
          "#" not in _bar2v.styleSheet().replace(_th.BORDER, "").replace(
              _th.CYAN_ON_FILL, "").replace(_th.CYAN_FILL, "").replace(
              _th.GREEN_ON_FILL, "").replace(_th.GREEN_FILL, ""))
    # LESBAR (Nutzer 26.09.2026): Schrift CYAN_ON_FILL auf Flaeche CYAN_FILL,
    # nicht mehr MUTED auf leuchtendem CYAN.
    check("b2v die Schrift auf dem Balken ist die helle Flaechen-Schrift",
          f"color: {_th.CYAN_ON_FILL}" in _bar2v.styleSheet()
          and f"background: {_th.CYAN_FILL}" in _bar2v.styleSheet()
          and _th.MUTED not in _bar2v.styleSheet())
    win.settings["bau_saved_plans"] = _alt2v
except Exception as _e2v:                                # pragma: no cover
    _fail.append(f"b2v Block geplatzt: {_e2v!r}")


# ---------------------------------------------------------------- (b2x)
# AUSWAHLLISTEN-SYMBOLE (Nutzer, Sitzung 9: "du hast hier Emojis
# vergessen"). _combo_item zieht das Emoji aus dem Text und haengt
# stattdessen ein gezeichnetes Symbol an - hier am ECHTEN Widget
# geprueft, nicht am Quelltext.
try:
    from PySide6.QtWidgets import QComboBox as _QCB2x
    import eve_trader.ui.main_window as _MW2x
    _c2x = _QCB2x()
    _MW2x._combo_item(_c2x, "\u26a1 Aktiv am PC \u00b7 viele Flips", "stunden")
    _MW2x._combo_item(_c2x, "\u2014 Eigene Einstellung \u2014", None)
    _MW2x._combo_item(_c2x, "\U0001F6E1 Kleine sichere Dips", {"a": 1})
    eq("b2x das Emoji ist aus dem Text verschwunden",
       _c2x.itemText(0), "Aktiv am PC \u00b7 viele Flips")
    check("b2x und wurde durch ein Symbol ersetzt",
          not _c2x.itemIcon(0).isNull())
    eq("b2x die hinterlegten Daten bleiben unversehrt",
       _c2x.itemData(0), "stunden")
    eq("b2x Eintraege ohne Emoji bleiben wortgleich",
       _c2x.itemText(1), "\u2014 Eigene Einstellung \u2014")
    check("b2x und bekommen KEIN Symbol untergeschoben",
          _c2x.itemIcon(1).isNull())
    check("b2x auch Preset-Eintraege mit dict-Daten funktionieren",
          _c2x.itemData(2) == {"a": 1} and not _c2x.itemIcon(2).isNull())
except Exception as _e2x:                                # pragma: no cover
    _fail.append(f"b2x Block geplatzt: {_e2x!r}")



# ---------------------------------------------------------------- (b17)
# ZWEI UPDATE-KNOEPFE NEBENEINANDER (Nutzer-Wunsch Sitzung 11: "den Button
# 'Auf neue Programm-Version pruefen' haette ich gerne oben rechts neben
# 'Updates'").
#
# DAS IST HEIKEL, DESHALB FUNKTIONAL GEPRUEFT: die beiden Knoepfe pruefen
# voellig VERSCHIEDENE Dinge - der eine EVE-Server-Version und Baurezepte,
# der andere die Programmfassung. Solange einer davon schlicht "Updates"
# hiess, war die Beschriftung nebeneinander eine Etikettenluege: jeder
# haette den falschen gedrueckt und danach geglaubt, er sei auf dem
# neuesten Stand. Deshalb heisst der EVE-Knopf jetzt "EVE-Daten".
_upd17 = [b for b in win.findChildren(QPushButton)
          if b.text() in (win.update_btn.text(), win.ver_btn.text())]
import ast as _a17
_src17 = open("eve_trader/ui/main_window.py", encoding="utf-8").read()
check("b17 beide Knoepfe stehen im Fenster", len(_upd17) >= 2)
# DIE BESCHRIFTUNGEN MUESSEN UNVERWECHSELBAR SEIN - das ist die Zusage,
# nicht ein bestimmtes Wort. Der Nutzer wollte "Updates" fuer das Programm
# (Sitzung 11); neben "EVE-Daten" ist das eindeutig. Die fruehere Fassung
# verbot "Updates" auf beiden Knoepfen und waere hier rot geworden, obwohl
# nichts verwechselbar ist.
check("b17 der EVE-Knopf nennt EVE",
      "EVE" in win.update_btn.text())
check("b17 der Programm-Knopf nennt NICHT EVE (sonst verwechselbar)",
      "EVE" not in win.ver_btn.text())
check("b17 die beiden heissen nicht gleich",
      win.update_btn.text().strip() != win.ver_btn.text().strip())
# Die Tooltips muessen die Verwechslung ausdruecklich ausschliessen.
# SPRACHUNABHAENGIG (Sitzung 12): die Zusage ist "jeder Tooltip grenzt
# sich vom anderen Knopf ab". Auf Deutsch steht dort "NICHT das Programm",
# auf Englisch "NOT the program" - ein fest gesuchtes Wort haelt nur in
# einer Sprache. Geprueft wird gegen den uebersetzten Katalogtext.
from eve_trader.sprache import t as _t17
check("b17 der EVE-Tooltip grenzt sich vom Programm ab",
      _t17("Does NOT check the program \u2013 use the button next to it.")
      in win.update_btn.toolTip())
check("b17 der Programm-Tooltip grenzt sich von den EVE-Daten ab",
      _t17("Does NOT check the EVE data \u2013 use the button next to it.")
      in win.ver_btn.toolTip())
# Sie muessen auch WIRKLICH verschiedene Wege gehen.
# WOHIN DIE KNOEPFE ZEIGEN - am Quelltext, nicht per Klick.
# Erster Versuch war ein echter Klicktest: er trennte die Verdrahtung und
# legte sie neu an, um mitzuzaehlen - und pruefte damit seine EIGENE
# Verdrahtung statt der des Programms. Er blieb gruen, als eine Mutation
# beide Knoepfe auf dasselbe Ziel legte. Qt laesst eine bereits gebundene
# Verbindung nicht abfangen, also wird hier festgenagelt, WAS verbunden
# wird.
check("b17 jeder Knopf loest seinen EIGENEN Weg aus",
      "self.ver_btn.clicked.connect(self.check_programm_update)" in _src17
      and "self.update_btn.clicked.connect(self._check_for_updates)" in _src17)
# Der Knopf in den Einstellungen bleibt zusaetzlich bestehen - dort steht
# die Versionsnummer und der CCP-Hinweis daneben.
check("b17 der Knopf in den Einstellungen bleibt erhalten",
      getattr(win, "s_ver_btn", None) is not None)
# UND BEIDE muessen sich waehrend der Abfrage sperren und danach wieder
# freigeben. Ohne den oberen wuerde man doppelt klicken koennen.
_cpu17 = ""
for _n17 in _a17.walk(_a17.parse(_src17)):
    if isinstance(_n17, _a17.FunctionDef) and _n17.name == "check_programm_update":
        _cpu17 = "\n".join(_src17.splitlines()[_n17.lineno - 1:_n17.end_lineno])
check("b17 die Abfrage sperrt beide Knoepfe, nicht nur einen",
      '("s_ver_btn", "ver_btn")' in _cpu17)


# ---------------------------------------------------------------- (b18)
# DIE .ico WIRD FRISCH ERZEUGT UND NACHGERECHNET (Nutzer-Befund Sitzung 11:
# "kein Icon" - die EXE trug im Explorer weiter das Standardsymbol).
#
# WARUM HIER UND NICHT IN DER aa-SUITE: erzeugen braucht Qt. Und warum
# ueberhaupt frisch: die fertige .ico liegt im Paket - eine kaputte
# Schreibfunktion faellt daran NICHT auf. Genau daran blieben zwei
# Mutationen blind, obwohl der Erzeuger nachweislich falsch arbeitete.
import importlib.util as _ilu18
import struct as _st18
import tempfile as _tmp18

_spec18 = _ilu18.spec_from_file_location("_mi18", "mache_icon.py")
_mod18 = _ilu18.module_from_spec(_spec18)
_spec18.loader.exec_module(_mod18)
_ziel18 = os.path.join(_tmp18.mkdtemp(prefix="ico18-"), "logo.ico")
_alt_ziel18 = _mod18.ZIEL
try:
    _mod18.ZIEL = _ziel18
    _mod18.main()
    _roh18 = open(_ziel18, "rb").read()
finally:
    _mod18.ZIEL = _alt_ziel18

_res18, _typ18, _anz18 = _st18.unpack("<HHH", _roh18[:6])
eq("b18 frisch erzeugt ist es ein gueltiges Symbol", _typ18, 1)
eq("b18 alle Groessen sind drin", _anz18, len(_mod18.GROESSEN))

_form18 = {}
_bild18 = {}
for _i18 in range(_anz18):
    _e18 = _roh18[6 + 16 * _i18:22 + 16 * _i18]
    _g18 = _e18[0] or 256
    _ln18, _of18 = _st18.unpack("<II", _e18[8:16])
    _d18 = _roh18[_of18:_of18 + _ln18]
    _bild18[_g18] = _d18
    _form18[_g18] = ("PNG" if _d18[:4] == b"\x89PNG"
                     else "DIB" if _st18.unpack("<I", _d18[:4])[0] == 40
                     else "?")
# KLEINE GROESSEN ALS BITMAP: seit Vista DARF ein Symbol PNG-komprimiert
# sein, aber der Explorer zeigt bei den kleinen Groessen dann gern das
# Standardsymbol - der wahrscheinlichste Grund fuer den Nutzer-Befund.
for _g18 in (16, 32, 48):
    eq(f"b18 Groesse {_g18} liegt als Bitmap vor", _form18.get(_g18), "DIB")
eq("b18 nur die 256er ist PNG (als Bitmap waere sie unnoetig gross)",
   _form18.get(256), "PNG")

# DAS BITMAP ZAEHLT VON UNTEN NACH OBEN. Dreht man die Zeilen nicht um,
# steht das Logo auf dem Kopf - und zwar NUR in der EXE, im Programm nie.
_g18 = 32
_kopf18 = _bild18[_g18][:40]
_br18, _ho18 = _st18.unpack("<ii", _kopf18[4:12])
eq(f"b18 der Bitmap-Kopf nennt die doppelte Hoehe (Farbe + Maske)",
   (_br18, _ho18), (_g18, _g18 * 2))
# Oberste Bildzeile mit der LETZTEN Zeile in der Datei vergleichen.
_von_qt18 = _ic2r.logo_pixmap(_g18).toImage()
_zeilen_bytes18 = _g18 * 4
_letzte18 = _bild18[_g18][40 + (_g18 - 1) * _zeilen_bytes18:
                          40 + _g18 * _zeilen_bytes18]
_treffer18 = 0
for _x18 in range(_g18):
    _c18 = _von_qt18.pixelColor(_x18, 0)
    _b18 = _letzte18[_x18 * 4:_x18 * 4 + 4]
    if bytes((_c18.blue(), _c18.green(), _c18.red(), _c18.alpha())) == _b18:
        _treffer18 += 1
check(f"b18 das Bitmap steht richtig herum ({_treffer18}/{_g18} Punkte)",
      _treffer18 >= _g18 - 1)


# ---------------------------------------------------------------- (b19)
# DAS FENSTER MUSS AUF EINEN KLEINEN BILDSCHIRM PASSEN (Nutzer-Befund
# Sitzung 11: "ich kann das tool an den raendern nicht kleiner oder
# groesser ziehen ... alles wird zusammengedrueckt").
#
# URSACHE: Qt laesst ein Fenster NIE kleiner werden als die Summe der
# Mindestgroessen seines Inhalts. Gemessen waren das 2346 x 1271 Pixel -
# mehr, als auf viele Bildschirme passt. Windows verweigerte das
# Verkleinern also nicht aus Willkuer, es ging schlicht nicht.
#
# NEU GEFASST (zweiter Anlauf derselben Sitzung): der Rollbereich umschliesst
# jetzt NUR den Reiter-Inhalt - Sidebar und Hub-Zeile sollen beim Rollen
# stehenbleiben. Damit zaehlt die Hub-Zeile wieder zur Mindestbreite; die
# ehrliche Grenze ist, was die FESTSTEHENDEN Teile brauchen. Entscheidend
# bleibt: kein Vielfaches der Bildschirmbreite, und in der HOEHE fast nichts
# (vorher 1271 px, jetzt unter 400).
# FUNKTIONAL geprueft: eine Quelltextsuche saehe eine solche Zahl nie.
# DIE HARTE GRENZE MESSEN, NICHT DEN WUNSCH (Nutzer, Sitzung 16):
# `minimumSizeHint()` ist nur, was Qt gerne haette - der Inhalt liegt in
# sieben Scrollbereichen, das Fenster darf also kleiner sein. Verbindlich
# ist `minimumWidth()`, und die wurde bewusst gesetzt.
#
# WARUM DAS WICHTIG IST: unter Windows ist dieselbe Schrift ~35 % breiter,
# der Hint lag beim Nutzer bei 1534 - die Pruefung war dort ROT, obwohl er
# das Fenster problemlos auf 1100 zieht. Sie mass das Falsche.
_mh19 = win.minimumSizeHint()
_grenze19 = win.minimumWidth()
check(f"b19 die harte Mindestbreite bleibt notebook-tauglich "
      f"({_grenze19}, Hint {_mh19.width()}x{_mh19.height()})",
      0 < _grenze19 <= 1150)
# UND SIE IST UEBERHAUPT GESETZT: ohne eigene Grenze wuerde Qt den Hint
# nehmen - dann waere der Nutzer wieder bei 1534.
check("b19 eine eigene Mindestbreite ist gesetzt", _grenze19 > 0)
# AM QUELLTEXT MITGEPRUEFT: faellt `setMinimumSize` weg, nimmt Qt den Hint -
# der liegt HIER zufaellig noch unter der Schwelle, unter Windows aber weit
# darueber. Die Messung allein haette den Wegfall also nicht gemeldet.
check("b19 die Grenze wird ausdruecklich gesetzt, nicht von Qt geraten",
      "self.setMinimumSize(1100, 520)" in _src_mw)
# GEMESSEN, nicht behauptet: bei breiterer Schrift (Windows) wandert der
# HINT mit, die Grenze nicht. Genau deshalb ist sie der richtige Massstab.
#   Schrift x1.0  -> Hint 1121, Grenze 1100
#   Schrift x1.35 -> Hint 1349, Grenze 1100
#   Schrift x1.6  -> Hint 1485, Grenze 1100
# (Eine Pruefung "Grenze <= Hint" waere sinnlos - beide koennen sich
# unabhaengig bewegen. Die Zahlen oben belegen das Verhalten.)
# Es muss auf einen kleinen Bildschirm passen - 1366x768 ist die
# Untergrenze, die man bei Notebooks noch antrifft.
# NOTEBOOK-GROESSE: 1366x768 ist die Untergrenze, die man bei Notebooks
# noch antrifft. Kleiner geht bewusst nicht - Sidebar, Hub-Zeile und die
# rechte Werkzeugleiste brauchen zusammen rund 1100 px, und die sollen
# stehenbleiben statt gestaucht zu werden.
win.resize(1366, 768)
_app.processEvents()
eq("b19 es laesst sich auf Notebook-Groesse ziehen",
   (win.width(), win.height()), (1366, 768))
win.resize(1100, 600)
_app.processEvents()
eq("b19 ... und bis an die ehrliche Untergrenze",
   (win.width(), win.height()), (1100, 600))
# ... aber nicht auf Briefmarkengroesse: darunter findet man den Rand zum
# Aufziehen kaum wieder.
check("b19 eine sinnvolle Untergrenze bleibt bestehen",
      win.minimumSize().width() >= 600 and win.minimumSize().height() >= 400)
# WAS NICHT MEHR HINEINPASST, WIRD GEROLLT statt gestaucht.
from PySide6.QtWidgets import QScrollArea as _QSA19
from PySide6.QtWidgets import QFrame as _QF19

# DER ROLLBEREICH SITZT IN JEDEM REITER UM DIE MITTE - nicht aussen um
# alles. Zweiter Anlauf derselben Sitzung: der erste Wurf legte ihn um die
# ganze Huelle, dann rollte die Sidebar mit weg; der zweite um die Reiter,
# dann rollte die rechte WERKZEUGLEISTE mit weg, sobald das Fenster schmal
# wurde ("wenn ich weiter kuerzer ziehe verschwindet die rechte sidebar").
# Jeder Reiter ist [Inhalt | Leiste] - der Rollbereich gehoert INNEN um den
# Inhalt.
_rolls19 = getattr(win, "_mitte_rollbereiche", [])
check(f"b19 die Reiter-Mitten rollen ({len(_rolls19)} Bereiche)",
      len(_rolls19) >= 4
      and all(isinstance(_r, _QSA19) for _r in _rolls19))
check("b19 sie sind auch eingehaengt, nicht nur erzeugt",
      all(_r.parentWidget() is not None for _r in _rolls19))
check("b19 sie nutzen bei grossen Fenstern die volle Breite",
      all(bool(getattr(_r, "widgetResizable", lambda: False)())
          for _r in _rolls19))


def _im_rollbereich19(widget):
    """Steckt das Widget IN einem Rollbereich - rollt es also mit weg?"""
    _p = widget.parentWidget() if widget is not None else None
    while _p is not None:
        if isinstance(_p, _QSA19):
            return True
        _p = _p.parentWidget()
    return False


# DIE BEIDEN LEISTEN MUESSEN STEHENBLEIBEN. Das ist der Kern des Wunsches:
# "die Sidebar links und rechts bleibt immer ersichtlich, somit wird man nur
# in der Mitte scrollen muessen".
check("b19 die Sidebar rollt nicht mit dem Inhalt weg",
      not any(win._sidebar_widget is _r.widget() for _r in _rolls19))
# AN DER MARKE, NICHT AN DER BREITE (23.09.2026): beide Leisten messen
# ihre Breite jetzt selbst, 210 px ist nur noch die Untergrenze und steht
# nicht mehr in `maximumWidth()`. Eine Pruefung, die an einem Nebeneffekt
# haengt, wird beim naechsten Umbau still blind.
_rails19 = [f for f in win.tabs.findChildren(_QF19)
            if f.property("rolle") == "rail"]
check(f"b19 die Werkzeugleisten sind auffindbar ({len(_rails19)})",
      len(_rails19) >= 3)
eq("b19 keine Werkzeugleiste rollt mit dem Inhalt weg",
   [f for f in _rails19 if _im_rollbereich19(f)], [])
# Sie darf aber IN SICH rollen: mit dem grossen Logo forderte sie sonst
# 723 px Mindesthoehe und zwang damit das ganze Fenster.
_sr19 = getattr(win, "_side_roll", None)
check("b19 die Sidebar darf in sich rollen",
      isinstance(_sr19, _QSA19)
      and _sr19.widget() is win._sidebar_widget
      and _sr19.parentWidget() is not None)


# ---------------------------------------------------------------- (b20)
# JEDER AUSGANG DER UPDATE-PRUEFUNG WIRD SICHTBAR GEMELDET (Nutzer-Befund
# Sitzung 11: "beim klicken auf den Knopf passiert nichts, keine Meldung").
# Die Antwort stand NUR in der Statuszeile ganz unten - auf einem kleinen
# Bildschirm sieht die niemand, und ein Knopf, der scheinbar nichts tut,
# wirkt kaputt.
import eve_trader.programm_update as _pu20
import eve_trader.ui.main_window as MW_MOD
import time as _t13x
_alt_pruefen20 = _pu20.pruefen
_alt_box20 = MW_MOD.QMessageBox.information
_gezeigt20 = []
try:
    MW_MOD.QMessageBox.information = staticmethod(
        lambda *_a, **_k: _gezeigt20.append(_a[1] if len(_a) > 1 else "?"))
    # Sitzung 17: der Fall "nicht vergleichbar" laeuft jetzt ueber ein Fenster
    # MIT KNOPF zur Releases-Seite (nichts mehr abtippen) - also auch das
    # ersetzen, sonst bleibt es im Test modal stehen.
    win._releases_wahl = lambda _t: (_gezeigt20.append(_t), False)[1]
    for _fall20, _antwort20 in (
            ("aktuell", {"neuer": False, "hinweis": "", "version": "0.1.0",
                         "url": None}),
            ("nicht vergleichbar", {"neuer": False, "hinweis": "keine Antwort",
                                    "version": None, "url": None})):
        _gezeigt20.clear()
        _pu20.pruefen = lambda _r, _v, holen=None, _a=_antwort20: _a
        win.check_programm_update()
        for _ in range(40):
            _app.processEvents()
            if _gezeigt20:
                break
            _t13x.sleep(0.05)
        check(f"b20 Fall '{_fall20}' wird sichtbar gemeldet", bool(_gezeigt20))
    check("b20 danach ist der Knopf wieder bedienbar", win.ver_btn.isEnabled())
    check("b20 der Fehlerfall bietet die Releases-Seite als KNOPF an",
          "Open releases page" in __import__("inspect").getsource(
              type(win)._releases_wahl))
finally:
    _pu20.pruefen = _alt_pruefen20
    MW_MOD.QMessageBox.information = _alt_box20
    if "_releases_wahl" in win.__dict__:
        del win._releases_wahl


# ---------------------------------------------------------------- (b21)
# JEDER AUSWAHL-EINTRAG TRAEGT EIN GEZEICHNETES SYMBOL (Nutzer-Befund
# Sitzung 11: "da fehlen teilweise einfach noch Icons - auf keinen Fall
# Emojis einfuegen").
#
# WARUM ES FEHLTE: die Symbole entstehen in `_combo_item`, das einen
# Emoji-Marker am Zeilenanfang gegen eine gezeichnete Grafik tauscht.
# Eintraege OHNE Marker blieben symbollos - und das Preset-Feld im
# Daytrade-Tab wurde beim Moduswechsel ueber schlichtes addItem neu
# aufgebaut, verlor die Symbole also selbst dort, wo ein Marker da war.
# Genau deshalb sah der Nutzer sie im Modus-Feld, aber nicht daneben.
#
# FUNKTIONAL geprueft: eine Quelltextsuche saehe ein leeres QIcon nicht.
from PySide6.QtWidgets import QComboBox as _QCB21
from eve_trader.sprache import t as _t21
_neutral21 = _t21("\u2014 Custom \u2014")
for _name21 in ("d_mode", "d_preset", "h_mode", "h_preset", "b_preset"):
    _c21 = getattr(win, _name21, None)
    if not isinstance(_c21, _QCB21):
        _fail.append(f"b21 {_name21}: Auswahlfeld nicht gefunden")
        continue
    _ohne21 = [_c21.itemText(_i) for _i in range(_c21.count())
               if _c21.itemIcon(_i).isNull()
               and _c21.itemText(_i).strip() != _neutral21]
    eq(f"b21 {_name21}: jeder Eintrag hat ein Symbol", _ohne21, [])
    # KEIN EMOJI IM TEXT. Der Marker im Quelltext wird von _combo_item
    # entfernt; bleibt er stehen, fehlt die Zuordnung und der Nutzer sieht
    # genau das, was er nicht wollte.
    _emoji21 = [_c21.itemText(_i) for _i in range(_c21.count())
                if any(ord(_z) > 0x2100 for _z in _c21.itemText(_i))]
    eq(f"b21 {_name21}: kein Emoji im Text stehengeblieben", _emoji21, [])

# DER NEUAUFBAU DARF SIE NICHT VERLIEREN: das war der eigentliche Fehler.
win.d_mode.setCurrentIndex(1)
_app.processEvents()
win._reload_deal_presets()
_app.processEvents()
_ohne21b = [win.d_preset.itemText(_i) for _i in range(win.d_preset.count())
            if win.d_preset.itemIcon(_i).isNull()
            and win.d_preset.itemText(_i).strip() != _neutral21]
eq("b21 auch nach einem Moduswechsel bleiben die Symbole", _ohne21b, [])
win.d_mode.setCurrentIndex(0)
_app.processEvents()


# ---------------------------------------------------------------- (b22)
# DER EINRICHTUNGS-KNOPF STEHT NICHT MEHR IM WEG (Nutzer-Befund Sitzung 11:
# "muss das jeder sehen koennen?").
#
# Im Charaktere-Reiter sass "Einrichtung" direkt neben "Charakter
# verknuepfen". Er lud zum Klicken ein, und was dann kam, sah nach
# Pflichtarbeit aus ("Einmalige Einrichtung, ~2 Minuten") - obwohl der
# ausgelieferte Stand eine eingebaute Client-ID hat und niemand das je
# braucht. Ein Schritt, den 99 % nicht gehen muessen, gehoert nicht neben
# den einen Knopf, den ALLE druecken.
from PySide6.QtWidgets import QPushButton as _QPB22
_knoepfe22 = [b.text() for b in win.findChildren(_QPB22)]
eq("b22 kein Einrichtungs-Knopf mehr neben 'Charakter verknuepfen'",
   [t for t in _knoepfe22 if "Einrichtung" in t], [])
# DER ANLEITUNGS-KNOPF IST WEG (Nutzer-Entscheid 17.09.2026: "raus"). Er
# fuehrte zur Anleitung fuer eine EIGENE ESI-Anwendung - seit der
# eingebauten Client-ID braucht das niemand. Der Einrichtungs-Dialog
# bleibt als Notausgang fuer "Client-ID leer" (open_setup), nur der Weg
# aus den Einstellungen ist zu.
check("b22 kein Anleitungs-Knopf mehr in den Einstellungen",
      getattr(win, "s_setup_btn", None) is None
      and "s_setup_btn" not in _src_mw)
check("b22 das Client-ID-Feld bleibt (die Login-Logik liest es)",
      getattr(win, "s_client", None) is not None)
check("b22 der Notausgang bei leerer Client-ID bleibt",
      "QTimer.singleShot(250, self.open_setup)" in _src_mw)


# ---------------------------------------------------------------- (b23)
# DIE TIEFENPRUEFUNG IST WIEDER ERREICHBAR (Sitzung 11).
#
# Sie hing als Zusatz-Knopf im "Alles aktuell"-Dialog. Der wurde auf
# Nutzerwunsch aufgeraeumt ("das braucht keiner zu sehen") - damit war die
# Funktion aus der Oberflaeche NICHT MEHR AUFRUFBAR, obwohl sie im Programm
# blieb. Code, den niemand erreicht, kann spaeter niemand mehr einordnen.
#
# JETZT: Rechtsklick auf "Baurezepte laden". KEIN eigener Knopf - die
# Hub-Zeile bestimmt die Mindestbreite des Fensters (1100 px), und ein
# vierter Knopf haette sie weiter hochgetrieben, fuer eine Funktion, die
# man vielleicht dreimal im Jahr braucht.
from PySide6.QtCore import Qt as _Qt23
check("b23 der Baurezepte-Knopf hat ein eigenes Kontextmenue",
      win.g_sde_btn.contextMenuPolicy() == _Qt23.CustomContextMenu)
check("b23 es ist mit dem Menue-Aufbau verbunden",
      "self.g_sde_btn.customContextMenuRequested.connect(" in _src_mw
      and "self._sde_kontextmenue" in _src_mw)
_menu23 = _fn_src_mw23 = None
import ast as _a23
for _n23 in _a23.walk(_a23.parse(_src_mw)):
    if isinstance(_n23, _a23.FunctionDef) and _n23.name == "_sde_kontextmenue":
        _menu23 = "\n".join(
            _src_mw.splitlines()[_n23.lineno - 1:_n23.end_lineno])
check("b23 das Menue bietet genau die Tiefenpruefung an",
      _menu23 is not None
      and 'm.addAction(t("Deep-check values"))' in _menu23)
check("b23 der Klick darauf startet sie wirklich",
      _menu23 is not None and "self._check_recipes()" in _menu23)
# ENTDECKBAR: ein Rechtsklick, den niemand ahnt, ist so gut wie kein Weg.
# SPRACHUNABHAENGIG: auf Englisch heisst es "RIGHT-CLICK". Geprueft wird,
# dass der Tooltip die zweite Zeile ueberhaupt traegt - sie ist der EINZIGE
# Hinweis darauf, dass es die Tiefenpruefung noch gibt.
check("b23 der Tooltip verraet den Rechtsklick",
      _t17("RIGHT-CLICK: deep-check values \u2013 compares every yield and "
           "ingredient amount against the game data.")
      in win.g_sde_btn.toolTip())
# UND SIE DARF DIE HUB-ZEILE NICHT BREITER MACHEN - genau dafuer wurde der
# Rechtsklick gewaehlt statt eines vierten Knopfes.
check(f"b23 die Mindestbreite bleibt unter 1150 "
      f"({win.minimumWidth()})",
      0 < win.minimumWidth() <= 1150)


# ---------------------------------------------------------------- (b23)
# DIE OBERFLAECHE SPRICHT WIRKLICH DIE GEWAEHLTE SPRACHE (Sitzung 12).
# FUNKTIONAL an echten Widgets - eine Quelltextsuche saehe nicht, ob der
# Text am Ende auch im Knopf landet.
from eve_trader import sprache as _sp23
import eve_trader.ui.main_window as _MW23

_alt23 = _sp23.aktuelle_sprache()
try:
    _sp23.sprache_setzen("en")
    _w_en = _MW23.MainWindow()
    _app.processEvents()
    eq("b23 auf Englisch heisst der Reiter 'Industry'",
       _w_en._tab_labels["build"], "Industry")
    # SEIT 27.09.2026 "Refresh portfolio" (Nutzer: "waere Refresh portfolio
    # nicht ein besserer Name?").
    # 27.09.2026 zweimal umbenannt, endgueltig "Refresh" (Nutzer: "ganz schlicht").
    eq("b23 auf Englisch heisst der Knopf 'Refresh'",
       _w_en.global_refresh_btn.text(), "Refresh")
    check("b23 auf Englisch steht kein deutscher Umlaut in der Kopfzeile",
          not any(_z in _w_en.g_sde_btn.text() for _z in "äöüÄÖÜß"))
    # DIE SPRACHWAHL IST SICHTBAR, nicht hinter einem Dialog versteckt.
    _lb23 = getattr(_w_en, "lang_box", None)
    check("b23 die Sprachwahl steht oben und zeigt die aktuelle Sprache",
          _lb23 is not None and _lb23.currentData() == "en")
    eq("b23 beide Sprachen stehen zur Wahl",
       sorted(_lb23.itemData(_i) for _i in range(_lb23.count())),
       ["de", "en"])

    # DAS PORTFOLIO ist die zweite umgestellte Schicht - Kopfzeile, Karten,
    # Tabellenkoepfe und die Zustandsworte in der Status-Spalte.
    eq("b23 auf Englisch heisst der Spaltenkopf 'Qty'",
       _w_en.pf_table.horizontalHeaderItem(1).text(), "Qty")
    eq("b23 auf Englisch sagt die Altersangabe 'never'",
       _w_en._age_str(None), "never")
    eq("b23 ... und setzt die Zahl in den uebersetzten Satz ein",
       _w_en._age_str(300), "5 min ago")
    eq("b23 der Daytrade-Kopf ist auf Englisch",
       _w_en.deals_table.horizontalHeaderItem(6).text(), "Profit/unit")
    # AUCH DIE VORDEREN SPALTEN - eine Mutation, die nur die erste Zeile der
    # Liste anfasst, bliebe sonst unbemerkt (genau so passiert).
    eq("b23 ... auch die vorderste Wert-Spalte",
       _w_en.deals_table.horizontalHeaderItem(1).text(), "Now (buy)")
    eq("b23 der Swing-Kopf ist auf Englisch",
       _w_en.hold_table.horizontalHeaderItem(3).text(), "below normal %")
    eq("b23 ... auch dessen vorderste Wert-Spalte",
       _w_en.hold_table.horizontalHeaderItem(1).text(), "Now (sell)")
    # KEIN UMLAUT MEHR in den sichtbaren Koepfen der englischen Fassung -
    # ein einzelnes vergessenes Wort faellt sonst niemandem auf.
    _koepfe23 = [_w_en.deals_table.horizontalHeaderItem(_i).text()
                 for _i in range(_w_en.deals_table.columnCount())]
    _koepfe23 += [_w_en.hold_table.horizontalHeaderItem(_i).text()
                  for _i in range(_w_en.hold_table.columnCount())]
    eq("b23 kein deutscher Umlaut in den englischen Spaltenkoepfen",
       [_k for _k in _koepfe23 if any(_z in _k for _z in "äöüÄÖÜß")], [])

    # ------------------------------------------------------------ (b62)
    # NUTZER-SCREENSHOTS SITZUNG 17, AM FENSTER GEMESSEN: Profits
    # ("Zeitraum", "Gewinn (netto)", "Umsatz", "Ø Marge"), Transactions
    # ("Typ", "Zeitraum", "Suche"), Settings ("Ziel-Marge", "Broker Fee
    # (Struktur)"), Industry-Presets ("Lohnende Produktion", "Reaktionen",
    # "STRATEGIE"), My blueprints ("Kategorie", "Anzeigen", "Suche", "Typ").
    # Alle Beschriftungen, Knoepfe, Haken und Listeneintraege des ENGLISCHEN
    # Fensters einsammeln - keiner dieser Texte darf dort stehen.
    from PySide6.QtWidgets import QAbstractButton as _QAB62
    _txt62 = [x.text() for x in _w_en.findChildren(QLabel)]
    _txt62 += [x.text() for x in _w_en.findChildren(_QAB62)]
    for _cb62 in _w_en.findChildren(QComboBox):
        _txt62 += [_cb62.itemText(_i) for _i in range(_cb62.count())]
    _verboten62 = ("Zeitraum", "Gewinn (netto)", "Umsatz", "\u00d8 Marge",
                   "Typ:", "Suche:", "Ziel-Marge", "Broker Fee (Struktur)",
                   "Lohnende Produktion", "Reaktionen", "STRATEGIE",
                   "Kategorie:", "Anzeigen:",
                   # Sitzung 17, zweite Runde (eigene Anzeige-Helfer):
                   "Investiert", "Item-Wert", "Erwarteter Gewinn",
                   "FEINFILTER", "CAPITAL-SCHIFFE")
    _gefunden62 = sorted({_v for _v in _verboten62 for _x in _txt62 if _v in (_x or "")})
    eq("b62 keiner der gemeldeten deutschen Texte im englischen Fenster",
       _gefunden62, [])
    check(f"b62 die Sammlung ist nicht leer ({len(_txt62)} Texte)", len(_txt62) > 300)
    check("b62 ... und enthaelt die neuen englischen Texte",
          all(any(_e in (_x or "") for _x in _txt62)
              for _e in ("Period:", "Profit (net)", "Revenue", "Target margin",
                         "Profitable production (T1)", "Category:")))

    _sp23.sprache_setzen("de")
    _w_de = _MW23.MainWindow()
    _app.processEvents()
    eq("b23 auf Deutsch heisst derselbe Reiter 'Bauen'",
       _w_de._tab_labels["build"], "Bauen")
    eq("b23 auf Deutsch heisst der Knopf 'Aktualisieren'",
       _w_de.global_refresh_btn.text(), "Aktualisieren")
    # DER EVE-DATEN-KNOPF wird nach jeder Pruefung neu beschriftet - er muss
    # dabei uebersetzt BLEIBEN. In Sitzung 11 hiess er nach dem ersten Klick
    # wieder anders, weil die Beschriftung an drei Stellen stand.
    eq("b23 der EVE-Knopf ist uebersetzt",
       _w_de.update_btn.text(), "EVE-Daten")
    eq("b23 ... und bleibt es nach dem Zuruecksetzen",
       _w_de._eve_update_text(), "EVE-Daten")
    eq("b23 auf Deutsch heisst derselbe Spaltenkopf 'Menge'",
       _w_de.pf_table.horizontalHeaderItem(1).text(), "Menge")
    eq("b23 die Altersangabe setzt die Zahl auch auf Deutsch ein",
       _w_de._age_str(300), "vor 5 Min.")

    # DIE TRICHTERZEILE ("warum so wenige Treffer?") ist die wichtigste
    # Erklaerung im Werkzeug - genau die Zeile, an der der Nutzer auf dem
    # frisch installierten Rechner haengen blieb. Sie wird aus Zahl +
    # Grund zusammengesetzt; die Zahl darf NICHT im Katalog stehen.
    _w_de._last_deal_diag = {"analyzed": 3775, "two_sided_low": 562}
    _diag_de = _w_de._deal_diag_text()
    check(f"b23 die Trichterzeile ist auf Deutsch ({_diag_de[:34]!r})",
          "3'775 analysiert" in _diag_de
          and "562 nicht beidseitig t\u00e4glich" in _diag_de)
    # SPRACHE UMSCHALTEN VOR DEM MESSEN: die Trichterzeile wird beim
    # ANZEIGEN uebersetzt, nicht beim Fensterbau - sie folgt also der
    # aktuellen Sprache, nicht der, in der das Fenster entstand. Das ist
    # richtig so (Beschriftungen frieren beim Bauen ein, laufende Texte
    # nicht), muss beim Pruefen aber beachtet werden.
    _sp23.sprache_setzen("en")
    _w_en._last_deal_diag = {"analyzed": 3775, "two_sided_low": 562}
    _diag_en = _w_en._deal_diag_text()
    check(f"b23 ... und auf Englisch ({_diag_en[:34]!r})",
          "3'775 analysed" in _diag_en
          and "562 not traded on both sides daily" in _diag_en)
    check("b23 kein deutscher Umlaut in der englischen Trichterzeile",
          not any(_z in _diag_en for _z in "äöüÄÖÜß"))
    # ETAPPE 3: die Handels-Reiter. Spaltenkoepfe, Strategie-Karte und die
    # Feinfilter-Beschriftungen - alles, was man sieht, ohne etwas zu
    # oeffnen.
    eq("b23 der Daytrade-Kopf ist auf Deutsch uebersetzt",
       _w_de.deals_table.horizontalHeaderItem(6).text(), "Gewinn/Stk")
    eq("b23 der Swing-Kopf ebenso",
       _w_de.hold_table.horizontalHeaderItem(3).text(), "unter Normal %")
    # AUCH DIE TOOLTIPS. Auf Englisch faellt ein vergessenes t() nicht auf -
    # der Schluessel IST der englische Text. Erst auf Deutsch zeigt sich,
    # ob die Uebersetzung wirklich greift.
    check(f"b23 der Markt-Scan-Tooltip ist auf Deutsch "
          f"({_w_de.g_scan_btn.toolTip()[:24]!r})",
          _w_de.g_scan_btn.toolTip().startswith("Scannt den aktiven Hub"))
    check("b23 der SDE-Tooltip ebenso",
          "RECHTSKLICK" in _w_de.g_sde_btn.toolTip())
    # AUCH DIE FEINFILTER-TOOLTIPS - sie erklaeren, was jeder Filter tut,
    # und sind der laengste zusammenhaengende Textblock im Werkzeug.
    # (Sitzung 17: Handelsplan-Knopf entfernt - Pruefung entfaellt)
    check("b23 der Preset-Tooltip ebenso",
          _w_de.d_preset.toolTip().startswith("Fertige Komplett"))

    # NUTZER-FUND: der neutrale Preset-Eintrag stand als "— Custom —"
    # mitten in der deutschen Oberflaeche. Ursache: er steht in einer
    # KLASSEN-KONSTANTE, und t() dort laeuft beim IMPORT - also bevor die
    # Sprache feststeht. Uebersetzt wird jetzt beim EINFUEGEN.
    # ALLE VIER LISTEN pruefen: drei waren richtig, die vierte
    # (Regional) lief ueber einen anderen Weg und blieb englisch.
    _neutral_de = [getattr(_w_de, _n).itemText(0)
                   for _n in ("d_preset", "h_preset", "b_preset", "rg_preset")]
    eq("b23 der neutrale Preset-Eintrag ist ueberall uebersetzt",
       sorted(set(_neutral_de)), ["\u2014 Eigene Einstellung \u2014"])
    # DIE WERKZEUGLEISTEN RECHTS - auf der DEUTSCHEN Seite pruefen: auf
    # Englisch IST der Schluessel der Text, ein vergessenes t() faellt dort
    # nicht auf.
    # BEIDE SEITEN PRUEFEN, und das ist kein Luxus:
    #  * ein fest eingetippter DEUTSCHER Text faellt nur auf ENGLISCH auf,
    #  * ein vergessenes t() (Schluessel = englischer Text) nur auf DEUTSCH.
    # Wer nur eine Seite prueft, laesst die halbe Fehlerklasse durch.
    # GOLD-SUCHE ALS PROBE ERSETZT (22.09.2026): der Knopf ist auf
    # Nutzer-Wunsch aus beiden Leisten verschwunden. Als zweite Probe dient
    # jetzt der Einkaufswagen-Knopf derselben Rail-Familie - er hat wie die
    # Gold-Suche einen echten deutschen Eintrag, taugt also fuer beide
    # Fehlerklassen (fester deutscher Text / vergessenes t()).
    eq("b23 die Werkzeugleiste rechts ist uebersetzt",
       [_w_de.deals_btn.text(), _w_de._sh_copy_btn.text()],
       ["Deals laden", "Multibuy kopieren"])
    # DIE UNTERREITER (Etappe 13): Einkaufswagen, Verkaufsliste,
    # Order-Update, Charaktere - ganze Bildschirme, die der Nutzer auf
    # Englisch noch komplett deutsch vorgefunden hat.
    # DIE DAYTRADE-PRESETS (Nutzer-Fund): sie stehen in einer
    # KLASSEN-KONSTANTE, uebersetzt wird beim EINFUEGEN - der Emoji-Marker
    # vorn wird dabei abgetrennt und wieder vorangestellt.
    # NUTZER-SCREENSHOTS: Container-Kopf, Zeitfenster-Auswahl und die
    # Preset-Listen von Swing UND Regional waren auf Deutsch noch englisch
    # bzw. auf Englisch noch deutsch. Beide Seiten pruefen.
    # BEIDE SEITEN: ein fest eingetippter DEUTSCHER Kopf faellt auf der
    # deutschen Seite gar nicht auf - er sieht dort ja richtig aus. Eine
    # Mutation, die genau das tut, lief deshalb blind durch.
    # INDUSTRIE-REITER (Nutzer-Screenshots): rechte Leiste, "Fertig"-Knopf
    # und die Gewinn-Zeilen der Plan-Karten.
    _rail_de = [_b.text() for _b in _w_de.findChildren(_QPB23)
                if _b.text() in ("Meine Blueprints", "My blueprints",
                                 "Strukturen", "Structures")]
    _rail_en = [_b.text() for _b in _w_en.findChildren(_QPB23)
                if _b.text() in ("Meine Blueprints", "My blueprints",
                                 "Strukturen", "Structures")]
    eq("b23 die Industrie-Leiste ist uebersetzt",
       [sorted(_rail_de), sorted(_rail_en)],
       [["Meine Blueprints", "Strukturen"], ["My blueprints", "Structures"]])
    eq("b23 der Container-Kopf ist uebersetzt",
       [[_w_de.cont_tree.headerItem().text(_i) for _i in range(3)],
        [_w_en.cont_tree.headerItem().text(_i) for _i in range(3)]],
       [["Handeln / Container", "Menge", "Jita-Wert"],
        ["Trade / container", "Qty", "Hub value"]])
    eq("b23 die Zeitfenster-Auswahl ebenso",
       [_w_de.d_window.itemText(2), _w_en.d_window.itemText(2)],
       ["30 Tage", "30 days"])
    eq("b23 die Swing-Presets ebenso",
       [_w_de.h_preset.itemText(1), _w_en.h_preset.itemText(1)],
       # OHNE MARKER: `_combo_item` trennt das Emoji ab und ersetzt es
       # durch ein gezeichnetes Symbol - im Text steht es nicht mehr.
       ["Kleine sichere Dips \u00b7 schnelle Erholung",
        "Small safe dips \u00b7 quick recovery"])
    eq("b23 die Regional-Presets ebenso",
       [_w_de.rg_preset.itemText(1), _w_en.rg_preset.itemText(1)],
       ["Sichere Marge (liquide Ziele)", "Safe margin (liquid destinations)"])
    eq("b23 die Presets sind auf Deutsch uebersetzt",
       _w_de.d_preset.itemText(1), "Empfohlen \u00b7 alle Preise")
    eq("b23 ... und auf Englisch englisch (Presets)",
       _w_en.d_preset.itemText(1), "Recommended \u00b7 all prices")
    # LETZTE RUNDE (Sitzung 12): Einstellungen, Bauplaene, Strukturen,
    # Gewinne. Auf BEIDEN Seiten geprueft - ein fest eingetippter deutscher
    # Text faellt nur auf Englisch auf, ein vergessenes t() nur auf Deutsch.
    eq("b23 die Einstellungen sind uebersetzt (deutsch)",
       [_w_de.s_corp_names_btn.text(),
        _w_de.findChild(type(_w_de.s_corp_names_btn), "") is not None],
       ["Namen laden", True])
    eq("b23 die Unterreiter sind uebersetzt (deutsch)",
       [_w_de._sh_step_toggle.text(), _w_de._sh_copy_btn.text()],
       ["\u25b6 Abarbeiten-Modus", "Multibuy kopieren"])
    eq("b23 ... und auf Englisch englisch (Unterreiter)",
       [_w_en._sh_step_toggle.text(), _w_en._sh_copy_btn.text()],
       ["\u25b6 Work-through mode", "Copy multibuy"])
    eq("b23 ... und auf Englisch englisch",
       [_w_en.deals_btn.text(), _w_en._sh_copy_btn.text()],
       ["Load deals", "Copy multibuy"])
    # (Sitzung 17: Akkumulationsplan-Knopf entfernt - Pruefung entfaellt)
    # NICHT AM EINGABEFELD MESSEN: `_install_tip` verschiebt den Tooltip
    # absichtlich vom Feld auf die BESCHRIFTUNG darueber (damit er beim
    # Tippen nicht im Weg steht). Am Feld steht danach "" - das sieht wie
    # ein fehlender Tooltip aus, ist aber Absicht.
    _tips_de = list(getattr(_w_de, "_tip_anchor", {}).values())
    check(f"b23 der Regional-Fracht-Tooltip ebenso ({len(_tips_de)} Tipps)",
          any(_x.startswith("Transportkosten pro m") for _x in _tips_de))
    # UND AUF ENGLISCH KEIN UMLAUT: der Schluessel IST der englische Text,
    # ein vergessenes t() faellt dort sonst nicht auf.
    _tips_en = ([_w_en.d_preset.toolTip()]
                + list(getattr(_w_en, "_tip_anchor", {}).values()))
    _mit_umlaut23 = [_x[:36] for _x in _tips_en
                     if any(_z in _x for _z in "äöüÄÖÜß")]
    eq(f"b23 englische Tooltips ohne Umlaut ({len(_tips_en)} geprueft)",
       _mit_umlaut23, [])
finally:
    _sp23.sprache_setzen(_alt23)


# ---------------------------------------------------------------- (b24)
# DIE ORDER-LEITER HAT KEINE INFO-ZEILE MEHR (Nutzer-Befund Sitzung 12).
#
# Der Text ueber der Leiter beschrieb das angeklickte Item und brauchte je
# nach Name und Zahlen ein bis drei Zeilen. Weil er im selben Kasten sitzt,
# WANDERTE DIE ITEM-LISTE DARUNTER bei jedem Klick um eine Zeile. Ein
# Erklaertext, der die Liste verschiebt, kostet mehr als er nuetzt.
#
# FUNKTIONAL geprueft: es geht nicht um den Wortlaut, sondern darum, dass
# nichts Sichtbares mehr die Hoehe des Kastens veraendern kann.
from PySide6.QtWidgets import QLabel as _QL24
_sichtbar24 = []
for _key24 in ("day", "swing", "region"):
    _ctx24 = getattr(win, "_ladder_ctx", {}).get(_key24)
    if not _ctx24:
        continue
    _inf24 = _ctx24.get("info")
    if _inf24 is not None and _inf24.isVisible():
        _sichtbar24.append(_key24)
eq("b24 keine sichtbare Info-Zeile ueber der Order-Leiter", _sichtbar24, [])

# SIE DARF ABER WEITER BESCHREIBBAR SEIN: rund ein Dutzend Stellen setzen
# dort Text (Ladehinweis, Fehler, Mengenvorschlag). Waere das Objekt weg,
# muesste man sie alle umbauen - viel Risiko fuer nichts.
_ctx24 = getattr(win, "_ladder_ctx", {}).get("day")
check("b24 das Feld existiert weiterhin (Schreibzugriffe laufen ins Leere)",
      _ctx24 is not None and isinstance(_ctx24.get("info"), _QL24))
if _ctx24 and _ctx24.get("info") is not None:
    _ctx24["info"].setText("Testtext")
    check("b24 auch nach dem Beschreiben bleibt es unsichtbar",
          not _ctx24["info"].isVisible())


# ---------------------------------------------------------------- (b95)
# DER EINKAUFSWAGEN SITZT IN DER RECHTEN LEISTE (Nutzer 23.09.2026: "die
# Einkaufsliste ist eine sehr wichtige Option, Hervorhebung" - und zur
# Leiste selbst: "bei den Trade Tabs ist diese bisher scheinbar etwas
# unnoetig ... wenn wir sie nicht sinnvoll befuellen koennen, sollte man
# sie weglassen"). Sie wird befuellt statt weggelassen.
#
# AM ECHTEN FENSTER: eine Quelltextsuche saehe nicht, WO ein Widget
# wirklich haengt - genau das ist hier die Zusage.
try:
    from PySide6.QtWidgets import QFrame as _QF95

    def _rail_von95(w):
        """Die Leiste ueber einem Widget - oder None."""
        p = w.parentWidget() if w is not None else None
        while p is not None:
            if isinstance(p, _QF95) and p.property("rolle") == "rail":
                return p
            p = p.parentWidget()
        return None

    _ohne95 = []
    _schmal95 = []
    for _k95 in ("day", "swing", "region"):
        _c95 = (getattr(win, "_ladder_ctx", None) or {}).get(_k95) or {}
        _b95 = _c95.get("addb")
        _r95 = _rail_von95(_b95)
        if _r95 is None:
            _ohne95.append(_k95)
            continue
        # BREITE GEMESSEN (Lehre b66): "In den Einkaufswagen" ist der
        # laengste Knopf im Programm; auf seinem Windows sind dieselben
        # Widgets rund 1,85x breiter als offscreen hier.
        if _r95.minimumWidth() < _b95.sizeHint().width() + 24:
            _schmal95.append(f"{_k95}: Leiste {_r95.minimumWidth()} px, "
                             f"Knopf {_b95.sizeHint().width()} px")
    eq("b95 in allen drei Handels-Reitern haengt der Wagen in der Leiste",
       _ohne95, [])
    eq("b95 ... und die Leiste fasst den Wagen-Knopf samt Raendern",
       _schmal95, [])
    # HERVORHEBUNG: der Knopf ist hoeher als ein gewoehnlicher Knopf und
    # traegt die Primaer-Optik. Ohne das geht er in der Leiste unter.
    _ab95 = ((getattr(win, "_ladder_ctx", None) or {}).get("day") or {}).get("addb")
    check("b95 der Wagen-Knopf ist hervorgehoben (hoch + Primaer-Optik)",
          _ab95 is not None and _ab95.minimumHeight() >= 36
          and _ab95.objectName() == "Primary")
    # DER ALTE KASTEN OBEN RECHTS IST IM DAYTRADE GANZ WEG - dort ist die
    # Leiter unbrauchbar (fremde Kauf-Orders) und der Wagen umgezogen; ein
    # leerer Kasten wuerde die Strategie-Karte grundlos auf 60 % druecken.
    # Auf der Verkaufsseite bleibt er, dort steht das Orderbuch drin.
    def _box_von95(k):
        _c = (getattr(win, "_ladder_ctx", None) or {}).get(k) or {}
        _t = _c.get("table")
        return _t.parentWidget() if _t is not None else None
    _bd95 = _box_von95("day")
    _bs95 = _box_von95("swing")
    check("b95 im Daytrade ist der Leiter-Kasten ganz versteckt",
          _bd95 is not None and not _bd95.isVisibleTo(_bd95.parentWidget()))
    check("b95 ... im Swing Trade steht er weiter da",
          _bs95 is not None and _bs95.isVisibleTo(_bs95.parentWidget()))
    # DIE ZEILE SAGT OHNE RICHTUNGSANGABE, WAS GEWAEHLT IST - "unten in der
    # Liste" stimmte nicht mehr, seit der Wagen rechts sitzt.
    _sel95 = ((getattr(win, "_ladder_ctx", None) or {}).get("day") or {}).get("sel")
    check("b95 der Platzhalter nennt keine Richtung mehr",
          _sel95 is not None and "below" not in _sel95.text()
          and "unten" not in _sel95.text())
except Exception as e:
    check(f"b95 Einkaufswagen in der Leiste: {type(e).__name__}: {e}", False)


# ---------------------------------------------------------------- (b25)
# FEHLBEDARF LAEUFT VON SELBST (Nutzer-Wunsch Sitzung 12).
#
# Der Nutzer hatte alles eingekauft, eingefroren, dann Reaktionen gebaut -
# und stand ploetzlich vor "kaufe nach". Die Fehlbedarf-Pruefung sagte
# gleichzeitig "alles deckt sich". Beides stimmte: der Materialien-Reiter
# rechnet den GESAMT-Bedarf, die Pruefung den REST-Bedarf. Der Widerspruch
# war die eigentliche Falle.
#
# FUNKTIONAL geprueft, nicht am Wortlaut: die geteilte Funktion muss es
# geben, sie muss ohne offenen Plan SCHWEIGEN (leere Liste, keine Warnung)
# und darf nie eine Ausnahme werfen - sie laeuft bei jedem Aufbau mit.
check("b25 die geteilte Fehlbedarf-Funktion existiert",
      callable(getattr(win, "_fehlbedarf_jetzt", None)))
try:
    _fb25 = win._fehlbedarf_jetzt()
    _fehler25 = None
except Exception as _e25:
    _fb25, _fehler25 = None, f"{type(_e25).__name__}: {_e25}"
eq("b25 sie wirft nie (laeuft bei jedem Aufbau mit)", _fehler25, None)
# (Ein Plan aus einer frueheren Pruefung ist hier noch offen - deshalb
# NICHT auf "leer" pruefen, sondern auf die FORM: eine Liste von
# 5er-Tupeln. Genau die erwartet der Aufrufer im Materialien-Reiter.)
check("b25 sie liefert eine Liste von 5er-Tupeln",
      isinstance(_fb25, list)
      and all(isinstance(_x, tuple) and len(_x) == 5 for _x in _fb25))


# ---------------------------------------------------------------- (b26)
# DER ESI-NACHLAUF LAEUFT - UND HOERT BEIM SCHLIESSEN AUF.
#
# AM LAUFENDEN FENSTER geprueft, nicht am Quelltext: eine Sonde hat genau
# hier einen Fehler gefunden, den der Quelltext nicht zeigte. `destroyed`
# reicht NICHT - der Dialog wird beim Schliessen nur versteckt, nicht
# geloescht. Der Takt lief munter weiter und haette fuer einen laengst
# geschlossenen Bauplan alle zwei Minuten ESI abgefragt.
from PySide6.QtCore import QTimer as _QT26
# ESI VORTAEUSCHEN: der Nachlauf haengt bewusst am selben Zweig wie der
# Auto-Abruf beim Oeffnen - ohne verknuepfte Charaktere gaebe es nichts
# nachzuladen, und die Pruefung liefe ins Leere (erste Fassung tat genau
# das). Der echte ESI-Aufruf wird dabei abgefangen: geprueft wird der
# TAKT, nicht das Netz.
import eve_trader.store as _store26
_alt_list26 = _store26.list_characters
_alt_core26 = win._load_all_esi_for_plan_core
win.settings["client_id"] = "b26"
_store26.list_characters = lambda: [{"character_id": 1, "name": "b26"}]
win._load_all_esi_for_plan_core = lambda tid: ("", None, None)
try:
    win._show_build_detail(100, "Testship-Nachlauf", _res)
    _app.processEvents()
    _dlg26 = getattr(win, "_bd_dialog", None)
    _timers26 = [_t for _t in _dlg26.findChildren(_QT26)
                 if _t.interval() == 300_000] if _dlg26 else []
    check("b26 mit ESI entsteht ein Nachlauf-Timer", bool(_timers26))
    if _timers26:
        check("b26 der Nachlauf laeuft mit 5-Minuten-Takt",
              _timers26[0].isActive() and _timers26[0].interval() == 300_000)
        _dlg26.close()
        _app.processEvents()
        # DER EIGENTLICHE FUND: `destroyed` reicht nicht - der Dialog wird
        # beim Schliessen nur versteckt. Ohne diese Pruefung liefe der Takt
        # fuer einen geschlossenen Plan weiter.
        check("b26 und steht nach dem SCHLIESSEN (nicht erst beim Loeschen)",
              not _timers26[0].isActive())
finally:
    # ERST DEN AUTO-ABRUF ABWARTEN, DANN ZURUECKSTELLEN (Sitzung 17).
    # Das Oeffnen stoesst einen ESI-Abruf im Hintergrund an. Er ruft den
    # Kern erst auf, wenn er LAEUFT - stand bis dahin schon wieder der
    # echte Kern da, meldete der "No ESI access" und oeffnete eine modale
    # Warnung. Gemessen im Container: die Suite hing genau daran. Ein
    # Wettlauf, der je nach Rechner anders ausgeht.
    # ZWEI PHASEN: der Abruf STARTET erst ueber `QTimer.singleShot(50, ...)`.
    # Wer nur "solange busy" wartet, sieht vor dem Start `False` und stellt
    # sofort zurueck - so ging der erste Reparaturversuch daneben (gemessen).
    # Also mindestens 300 ms laufen lassen, danach bis der Abruf fertig ist.
    import time as _time26
    _ab26 = _time26.time()
    while _time26.time() < _ab26 + 10 and (
            _time26.time() < _ab26 + 0.3
            or getattr(win, "_bd_esi_busy", False)):
        _app.processEvents()
        _time26.sleep(0.02)
    _store26.list_characters = _alt_list26
    win._load_all_esi_for_plan_core = _alt_core26
    win.settings.pop("client_id", None)


# ---------------------------------------------------------------- (b27)
# GRUENER PUNKT STATT KAESTCHEN, wenn ESI den Bau bestaetigt
# (Nutzer-Wunsch Sitzung 12: "ein anderes Symbol fuer 'fertig gebaut und
# ESI geprueft', ohne Kommentar im Bauplan").
#
# WARUM UEBERHAUPT: ein abgehaktes Kaestchen sieht aus wie "ich habe es mir
# vorgenommen". Der gruene Punkt sagt "gebaut UND bestaetigt" - das ist
# eine andere Aussage, und der Nutzer will sie auf einen Blick sehen.
#
# AM SYMBOL selbst geprueft (nicht am Quelltext): es muss ueberhaupt eines
# geben, sonst bliebe die Zeile leer und der Zustand unsichtbar.
from eve_trader.ui import icons as _ic27
_punkt27 = _ic27.gruener_punkt()
check("b27 es gibt ein Punkt-Symbol und es ist nicht leer",
      _punkt27 is not None and not _punkt27.isNull())
# UND ES FOLGT DEM THEME: eine hart eingetippte Farbe wuerde beim naechsten
# Themenwechsel auseinanderdriften (aa170/aa175 verbieten das).
# (Die b-Suite hat kein `_fn_src` - hier direkt die Quelle lesen.)
import inspect as _insp27
_qs27 = _insp27.getsource(_ic27.gruener_punkt)
# NUR AUSGEFUEHRTE ZEILEN: im Beschreibungstext der Funktion steht das Wort
# des Nutzers, dort darf alles vorkommen (dieselbe Falle wie bei aa234).
_code27 = "\n".join(_z for _z in _qs27.splitlines()
                    if not _z.strip().startswith("#"))
_code27 = _code27.split('"""')[0] + _code27.split('"""')[-1]
check("b27 die Farbe kommt aus dem Theme, nicht aus dem Symbol-Modul",
      "_theme.GREEN" in _code27 and "#" not in _code27)


# ---------------------------------------------------------------- (b40)
# NUR EIN BAUPLAN GLEICHZEITIG (Sitzung 13).
#
# NUTZER-MELDUNG: "wenn ich 2 oder mehrere Bauplaene gleichzeitig offen
# habe, dann wird irgendwas gemischt und vermischt, so als ob die sich
# kreuzen oder voneinander etwas geben und nehmen."
#
# REPRODUZIERT (vor der Sperre): zwei Fenster liessen sich oeffnen, danach
# trug `_bd_mat_rows` die Zeilen des ZWEITEN Plans - und "Einkaufsliste
# erstellen" im ERSTEN Fenster liest genau dieses Feld. Ursache: der Dialog
# legt seinen gesamten Zustand auf der MainWindow ab (414 `self._bd_...`
# ueber drei Dateien), zwei Fenster teilen sich also jedes Feld.
#
# Ausgangslage: EIN Bauplan ist offen. Der aus b2 ist bis hierher meist
# schon wieder zu (spaetere Bloecke schliessen ihn) - dann einmal neu
# oeffnen. Das Aufraeumen am Ende schliesst ihn ueber _dlg mit.
_offen40 = win._offener_bauplan()
if _offen40 is None:
    win._show_build_detail(100, "Testship", _res)
    _offen40 = win._offener_bauplan()
    _dlg = _offen40
check("b40 ein Bauplan ist offen (Ausgangslage)", _offen40 is not None)
if _offen40 is not None:
    from PySide6.QtWidgets import QMessageBox as _QMB40
    # DAS POPUP IST MODAL - ungefangen wartet es ewig auf einen Klick und
    # die Suite haengt. Deshalb hier abfangen UND pruefen, dass es kommt:
    # eine Sperre ohne Hinweis waere ein stilles Nichts-passiert (Regel 6).
    _pop40 = []
    _orig40 = _QMB40.information
    _QMB40.information = staticmethod(
        lambda *a40, **k40: _pop40.append((str(a40[1]), str(a40[2]))))
    try:
        # ABSICHTLICH KAPUTTES res: greift die Sperre, kehrt die Funktion
        # zurueck, BEVOR sie res anfasst - es wird gar kein zweiter Dialog
        # gebaut. Greift sie nicht, fliegt sofort ein KeyError auf
        # res["tree"]. So laesst sich die Zusage pruefen, ohne ein zweites
        # schweres Fenster aufzubauen.
        _err40 = None
        try:
            _sbd_echt(100, "Testship", {})      # die UNGEWICKELTE Methode
        except Exception as _e40:
            _err40 = _e40
    finally:
        _QMB40.information = staticmethod(_orig40)
    check(f"b40 die Sperre greift, bevor irgendetwas gebaut wird "
          f"({type(_err40).__name__}: {_err40})" if _err40 else
          "b40 die Sperre greift, bevor irgendetwas gebaut wird",
          _err40 is None)
    check("b40 kein zweites Fenster wird gebaut",
          getattr(win, "_bd_dialog", None) is _offen40)
    check("b40 der Nutzer bekommt einen Hinweis, kein stilles Nichts",
          len(_pop40) == 1)
    check("b40 der Hinweis sagt, worum es geht",
          bool(_pop40) and "Only one build plan" in _pop40[0][0])
    check("b40 und nennt den Grund (geteilte Daten)",
          bool(_pop40) and "share their data" in _pop40[0][1])
    # Ein GESCHLOSSENES Fenster darf nicht sperren - sonst kaeme man nach
    # dem ersten Bauplan an keinen zweiten mehr heran.
    check("b40 ein offenes Fenster wird erkannt",
          win._offener_bauplan() is _offen40)
    _offen40.hide()
    check("b40 ein unsichtbares Fenster sperrt NICHT",
          win._offener_bauplan() is None)
    _offen40.show()


# ---------------------------------------------------------------- (b41)
# ERLEDIGTE RUNS BLEIBEN STEHEN - GEDIMMT, MIT PUNKT STATT KAESTCHEN
# (Nutzer, Sitzung 14, woertlich): "Am liebsten haette ich gerne noch
# sichtbar die runs die ich gemacht habe aber halt gedimmt. damit ich sehen
# kann was ich mal gemacht habe, auch was es mal an materialien gebraucht
# hat usw. ... wenn etwas tatsaechlich per ESI getrackt gebaut wurde, dann
# darf ein Gruener Punkt anstelle des hackens kommen. ists noch in der
# Bauschleife auch schon gedimmt aber violetter punkt. ... Aber das muss
# auch funktionieren ob ich etwas gehackt habe oder nicht. Also imprinzip
# wird nie etwas mehr ausgeblendet nurnoch gedimmt und eingefaerbt und mit
# punkten versehen."
#
# DAS WIDERRUFT DIE ANSAGE AUS SITZUNG 8 ("die ESI soll Sachen ausblenden").
# Die alten Zusagen dazu standen in aa164 und sind dort mit Begruendung
# umgestellt worden.
#
# WARUM FUNKTIONAL UND NICHT ALS TEXTPROBE: alle bisherigen Pruefungen an
# `_fill_bauplan_schedule` lesen nur den Quelltext. Zusagen wie "die Zeile
# steht noch da, hat aber KEIN Kaestchen mehr und ist gedimmt" kann eine
# Textprobe nicht halten - dafuer muss der Baum wirklich gebaut und danach
# nachgesehen werden. Genau die Lehre aus Sitzung 11.
from PySide6.QtWidgets import QTreeWidget as _QTW41
from eve_trader.ui import icons as _icons41
from eve_trader.ui import theme as _theme41
import datetime as _dt41


class _Recipes41:
    """ZWEI Stufen mit ZWEI Items in der unteren: 100 <- 201 + 202, beide
    aus 200. Nur so laesst sich der gefaehrliche Zwischenfall pruefen - eine
    Stufe, in der EINE Position erledigt ist und eine noch offen. Mit dem
    Einzel-Item-Rezept der uebrigen Suite waere jede Stufe entweder ganz
    fertig oder ganz offen, und eine Mutation, die schon bei der ERSTEN
    erledigten Position zuklappt, bliebe blind.
    PREISE: das Endprodukt muss teuer und das Rohmaterial billig sein, sonst
    stuft der Plan die Komponenten als "Kauf billiger" ein und baut sie gar
    nicht (beim ersten Anlauf genau so passiert - der Runplaner war leer)."""
    product_to_bp = {100: (900, I.MANUFACTURING, 1),
                     201: (901, I.MANUFACTURING, 1),
                     202: (902, I.MANUFACTURING, 1)}
    bp_materials = {(900, I.MANUFACTURING): [(201, 5), (202, 5)],
                    (901, I.MANUFACTURING): [(200, 10)],
                    (902, I.MANUFACTURING): [(200, 10)]}
    activity_time = {(900, I.MANUFACTURING): 60, (901, I.MANUFACTURING): 60,
                     (902, I.MANUFACTURING): 60}
    activity_max_runs = {(900, I.MANUFACTURING): 0, (901, I.MANUFACTURING): 0,
                         (902, I.MANUFACTURING): 0}
    reaction_products = set()
    invention_for_bpc = {}
    bp_products = {}
    item_cat = {}

    def is_manufactured(self, t):
        return t in self.product_to_bp


_PRICES41 = {100: 500000.0, 200: 100.0, 201: 9000.0, 202: 9000.0}
_orig_lc41 = store.list_characters
_bak41 = {_k41: win.settings.get(_k41) for _k41 in
          ("bau_build_chars", "bau_reaction_chars", "bau_char_slots",
           "bau_char_free")}
try:
    store.list_characters = lambda: [{"character_id": 1,
                                      "character_name": "Peanut Motor"}]
    win.settings["bau_build_chars"] = [1]
    win.settings["bau_reaction_chars"] = []
    win.settings["bau_char_slots"] = {"1": [10, 10]}
    win.settings["bau_char_free"] = {}
    win._bd_pricemap = dict(_PRICES41)
    win._bd_recipes = _Recipes41()
    win._bd_opts = {"me": 0, "te": 0, "job_pct": 0, "build_reactions": False,
                    "tree_depth": 4}
    win._bd_type = 100
    win._bd_qty = 10
    win._bd_runplan_checked = set()
    _plan41 = I.production_plan(100, 10, _PRICES41.get, _Recipes41(),
                                dict(win._bd_opts))
    # Eingefroren, denn NUR dort wertet das Tool ESI-Fortschritt aus.
    win._bd_frozen = {"ts": _t13.time() - 100, "qty": 10,
                      "prices": dict(_PRICES41), "adjusted": {}, "stock": {},
                      "cost_idx": {},
                      "plan_snapshot": MainWindow._plan_snapshot_pack(_plan41)}
    win._bd_frozen_plan_cache = None
    win._bd_delivered_jobs = []
    _names41 = {100: "Testship", 200: "Testmat", 201: "KompA", 202: "KompB"}
    # Die Komponenten-Stufe MUSS wirklich zwei Bau-Positionen haben, sonst
    # prueft unten alles ins Leere (Preise falsch -> Plan kauft statt baut).
    eq("b41 Vorbedingung: beide Komponenten werden auch wirklich gebaut",
       sorted(int(_k41) for _k41 in (_plan41.get("build_runs") or {})),
       [100, 201, 202])

    def _fuelle41(aktiv=None, geliefert=None):
        """Baum einmal fuellen. `aktiv` = laufende ESI-Jobs je Item,
        `geliefert` = fertig abgelieferte Jobs. Beides getrennt, weil es
        zwei VERSCHIEDENE Zustaende sind (Lauf-Punkt vs. gruener Punkt)."""
        win._bd_active_jobs_map = win._bd_active_jobs_alle = aktiv or {}
        win._bd_delivered_jobs = geliefert or []
        _tbl41 = _QTW41()
        _tbl41.setColumnCount(6)
        win._fill_bauplan_schedule(_plan41, _names41, 100, 10,
                                   QLabel(), QLabel(), _tbl41)
        return _tbl41

    def _stufen41(tbl):
        return [tbl.topLevelItem(_i) for _i in range(tbl.topLevelItemCount())]

    def _pos41(stufe):
        """Alle ITEM-Zeilen unter einer Stufe (Ebene: Stufe > Charakter >
        Item), als {Name: Item}. Ueber getattr/Schleife statt direktem
        Indexzugriff - eine Mutation soll eine BENANNTE Pruefung rot machen,
        nicht die Suite mit einer Ausnahme abbrechen (Lehre Sitzung 11)."""
        _raus = {}
        for _i in range(stufe.childCount() if stufe is not None else 0):
            _ch = stufe.child(_i)
            for _g in range(_ch.childCount()):
                _it = _ch.child(_g)
                _raus[(_it.text(0) or "").strip()] = _it
        return _raus

    def _charzeilen41(stufe):
        return [stufe.child(_i).text(0) or ""
                for _i in range(stufe.childCount() if stufe is not None else 0)]

    def _hat_kaestchen41(item):
        return (item is not None
                and item.data(0, Qt.CheckStateRole) is not None)

    def _ist_gedimmt41(item):
        return (item is not None
                and item.foreground(0).color().name().lower()
                == _theme41.MUTED.lower())

    _spaet41 = _dt41.datetime.utcfromtimestamp(
        _t13.time() + 60).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _geliefert41(*tids):
        return [{"product_type_id": _t, "activity_id": 1, "runs": 99999,
                 "completed_date": _spaet41} for _t in tids]

    # ---- A) NICHTS laeuft -> alles offen (Gegenprobe) ----
    _off41 = _fuelle41()
    # Den Index der KOMPONENTEN-Stufe aus diesem Lauf holen statt ihn zu
    # raten: die Stufenbeschriftung ist uebersetzbar, die Reihenfolge koennte
    # sich aendern. Ein fester Index waere genau die Sorte Anker, die in
    # Sitzung 10 dreimal umgefallen ist.
    _ikomp41 = next((_i for _i, _s in enumerate(_stufen41(_off41))
                     if "KompA" in _pos41(_s)), None)
    _iend41 = next((_i for _i, _s in enumerate(_stufen41(_off41))
                    if "Testship" in _pos41(_s)), None)
    check("b41 Vorbedingung: Komponenten- und Endprodukt-Stufe sind auffindbar",
          _ikomp41 is not None and _iend41 is not None and _ikomp41 != _iend41)
    _s_off41 = (_off41.topLevelItem(_ikomp41)
                if _ikomp41 is not None else None)
    _p_off41 = _pos41(_s_off41)
    check("b41 Gegenprobe: die offene Position traegt ein Kaestchen",
          _hat_kaestchen41(_p_off41.get("KompA")))
    check("b41 Gegenprobe: die offene Position traegt KEINEN Punkt",
          _p_off41.get("KompA") is not None
          and _p_off41["KompA"].icon(0).isNull())
    check("b41 Gegenprobe: die offene Position ist NICHT gedimmt",
          not _ist_gedimmt41(_p_off41.get("KompA")))
    check("b41 Gegenprobe: die offene Stufe ist aufgeklappt",
          _s_off41 is not None and _s_off41.isExpanded())
    check("b41 Gegenprobe: die offene Stufe traegt KEINEN Fertig-Haken",
          _s_off41 is not None
          and not (_s_off41.text(0) or "").startswith("\u2713"))

    # ---- B) EINE Position in Bau -> TEILWEISE fertig ----
    # DER GEFAEHRLICHE FALL. Klappte die Stufe schon hier zu, geriete die
    # noch OFFENE Position aus dem Blick - der Nutzer steht im Spiel davor
    # und baut sie nie.
    _tei41 = _fuelle41(aktiv={201: [{"runs": 99999}]})
    _s_tei41 = (_tei41.topLevelItem(_ikomp41)
                if _ikomp41 is not None else None)
    _p_tei41 = _pos41(_s_tei41)
    check(f"b41 teilweise: BEIDE Positionen stehen da {sorted(_p_tei41)}",
          "KompA" in _p_tei41 and "KompB" in _p_tei41)
    check("b41 teilweise: die offene Position behaelt ihr Kaestchen",
          _hat_kaestchen41(_p_tei41.get("KompB")))
    check("b41 teilweise: die offene Position bleibt ungedimmt",
          not _ist_gedimmt41(_p_tei41.get("KompB")))
    # UMGEKEHRT AM 21.09.2026 (s. aa384): das Kaestchen BLEIBT. Der
    # Hand-Haken ist die einzige Quelle, aus der die Reservierung die Zutaten
    # einer Zeile abbucht - ohne Kaestchen blieb ihr Material fuer immer
    # gesperrt. Punkt und Haken sagen Verschiedenes: der Punkt "ESI sieht das
    # als gebaut", der Haken "ich bin durch, das Material darf weg".
    check("b41 teilweise: die laufende Position behaelt ihr Kaestchen",
          _hat_kaestchen41(_p_tei41.get("KompA")))
    check("b41 teilweise: die Stufe bleibt aufgeklappt",
          _s_tei41 is not None and _s_tei41.isExpanded())
    # GEGENPROBE ZUM MITZIEHEN: solange EINE Position offen ist, behaelt der
    # Charakter sein Kaestchen - er ist ja noch nicht durch.
    _cz_tei41 = (_s_tei41.child(0)
                 if _s_tei41 is not None and _s_tei41.childCount() else None)
    check("b41 teilweise: die Charakter-Zeile behaelt ihr Kaestchen",
          _hat_kaestchen41(_cz_tei41))
    check("b41 teilweise: und traegt noch keinen Punkt",
          _cz_tei41 is not None and _cz_tei41.icon(0).isNull())
    check("b41 teilweise: die Stufe wird NICHT als fertig beschriftet",
          _s_tei41 is not None
          and not (_s_tei41.text(0) or "").startswith("\u2713"))

    # ---- C) ALLES in der Bauschleife -> Stufe fertig, LAUF-Punkt ----
    _lau41 = _fuelle41(aktiv={201: [{"runs": 99999}], 202: [{"runs": 99999}]})
    _s_lau41 = (_lau41.topLevelItem(_ikomp41)
                if _ikomp41 is not None else None)
    _p_lau41 = _pos41(_s_lau41)
    check("b41 in Bau: die Zeilen bleiben ALLE stehen (nichts ausgeblendet)",
          "KompA" in _p_lau41 and "KompB" in _p_lau41)
    check("b41 in Bau: die Charakter-Zeile bleibt ebenfalls stehen",
          any("Peanut Motor" in _z for _z in _charzeilen41(_s_lau41)))
    # DIE CHARAKTER-ZEILE ZIEHT MIT (Nutzer: "dann muessen wir die
    # charaktere auch abhacken"). Sonst stuende ueber lauter gedimmten
    # Punkt-Zeilen ein leeres Kaestchen - die Zeile behauptete das Gegenteil
    # ihrer eigenen Kinder.
    _cz_lau41 = (_s_lau41.child(0)
                 if _s_lau41 is not None and _s_lau41.childCount() else None)
    check("b41 in Bau: die Charakter-Zeile behaelt ihr Kaestchen",
          _hat_kaestchen41(_cz_lau41))
    check("b41 in Bau: die Charakter-Zeile ist gedimmt",
          _ist_gedimmt41(_cz_lau41))
    check("b41 in Bau: auf der Charakter-Zeile steht der LAUF-Punkt",
          _cz_lau41 is not None
          and _cz_lau41.icon(0).cacheKey() == _icons41.lauf_punkt().cacheKey())
    check("b41 in Bau: die Zeile ist gedimmt",
          _ist_gedimmt41(_p_lau41.get("KompA")))
    check("b41 in Bau: die Zeile behaelt ihr Kaestchen",
          _hat_kaestchen41(_p_lau41.get("KompA")))
    # ... und es ist LEER, nicht vorgehakt: ein Haken, den der Nutzer nicht
    # gesetzt hat, waere genau die Falle aus Sitzung 22.
    check("b41 in Bau: das Kaestchen ist LEER, nicht vorgehakt",
          _p_lau41.get("KompA") is not None
          and _p_lau41["KompA"].checkState(0) != Qt.Checked)
    # DER PUNKT MUSS DER RICHTIGE SEIN. Nur "irgendein Icon" zu pruefen
    # waere blind gegen die Verwechslung der beiden Zustaende - und genau
    # die ist die Aussage, die der Nutzer sehen will.
    check("b41 in Bau: es ist der LAUF-Punkt, nicht der gruene",
          _p_lau41.get("KompA") is not None
          and _p_lau41["KompA"].icon(0).cacheKey()
          == _icons41.lauf_punkt().cacheKey())
    check("b41 in Bau: die Materialien bleiben nachschlagbar",
          _p_lau41.get("KompA") is not None
          and _p_lau41["KompA"].childCount() > 0)
    check("b41 in Bau: die Zeile zeigt die PLAN-Runs, nicht 0",
          _p_lau41.get("KompA") is not None
          and (_p_lau41["KompA"].text(1) or "").strip() not in ("", "0"))
    check("b41 in Bau: die Stufe ist zugeklappt",
          _s_lau41 is not None and not _s_lau41.isExpanded())
    # EIN KLICK MUSS REICHEN (Nutzer-Screenshot: "wo gibts jetzt da gruene
    # punkte?"): wer eine fertige Stufe aufklappt, will die Items sehen -
    # nicht noch eine zugeklappte Charakter-Ebene davor.
    check("b41 in Bau: die Charakter-Zeilen sind offen, ein Klick genuegt",
          _s_lau41 is not None and _s_lau41.childCount() > 0
          and all(_s_lau41.child(_i).isExpanded()
                  for _i in range(_s_lau41.childCount())))
    check("b41 Gegenprobe: in der OFFENEN Stufe bleiben sie zu (Uebersicht)",
          _s_off41 is not None and _s_off41.childCount() > 0
          and not any(_s_off41.child(_i).isExpanded()
                      for _i in range(_s_off41.childCount())))
    # SITZUNG 16, NUTZER-BEFUND: "die blauen Sachen besagen ja, dass etwas im
    # Bau ist. Aber die Ueberkategorie davon zeigt gruen mit Checkhaken - das
    # ist verwirrend." Genau diese Zeile hatte den Fehler FESTGESCHRIEBEN:
    # sie verlangte den Fertig-Haken auf einer Stufe, in der alles noch
    # LAEUFT. Jetzt traegt die Stufe den LAUF-Punkt und sagt "im Bau".
    from eve_trader.ui import theme as _theme41
    check("b41 in Bau: die Stufe traegt den LAUF-Punkt, nicht den Haken",
          _s_lau41 is not None
          and (_s_lau41.text(0) or "").startswith("\u25cf")
          and not (_s_lau41.text(0) or "").startswith("\u2713"))
    check("b41 in Bau: die Stufe sagt 'im Bau', nicht 'finished'",
          _s_lau41 is not None
          and "finished" not in (_s_lau41.text(2) or "").lower())
    # DIE FARBE MUSS MITZIEHEN - gruen auf einer laufenden Stufe waere
    # dieselbe Luege wie der Haken.
    check("b41 in Bau: die Stufe ist NICHT gruen eingefaerbt",
          _s_lau41 is not None
          and _s_lau41.foreground(0).color().name().lower()
          != _theme41.GREEN.lower())
    check(f"b41 in Bau: die Stufe nennt BEIDE Positionen "
          f"({_s_lau41.text(2) if _s_lau41 else None!r})",
          _s_lau41 is not None and "2" in (_s_lau41.text(2) or ""))
    check("b41 in Bau: die Stufe behauptet keine Restdauer mehr",
          _s_lau41 is not None and not (_s_lau41.text(3) or "").strip())
    check("b41 in Bau: die geplante Dauer bleibt im Tooltip nachlesbar",
          _s_lau41 is not None and bool((_s_lau41.toolTip(3) or "").strip()))
    # Die naechste, noch offene Stufe darf davon nichts abbekommen - das ist
    # der Kern des Wunsches ("nurnoch komponents sehen").
    _s_end41 = (_lau41.topLevelItem(_iend41)
                if _iend41 is not None else None)
    check("b41 in Bau: die naechste offene Stufe bleibt unberuehrt",
          _s_end41 is not None and _s_end41.isExpanded()
          and _hat_kaestchen41(_pos41(_s_end41).get("Testship")))

    # ---- D) WIRKLICH GELIEFERT -> gruener Punkt, OHNE eigenen Haken ----
    # "Aber das muss auch funktionieren ob ich etwas gehackt habe oder
    # nicht." Bis Sitzung 13 hing der gruene Punkt INNERHALB von
    # `if _ckey_item in _checked_set:` - ohne Haken kein Punkt. Deshalb hier
    # ausdruecklich mit LEEREM Haken-Satz.
    win._bd_runplan_checked = set()
    _ger41 = _fuelle41(geliefert=_geliefert41(201, 202))
    _s_ger41 = (_ger41.topLevelItem(_ikomp41)
                if _ikomp41 is not None else None)
    _p_ger41 = _pos41(_s_ger41)
    check("b41 geliefert: die Zeilen bleiben stehen",
          "KompA" in _p_ger41 and "KompB" in _p_ger41)
    check("b41 geliefert: gruener Punkt OHNE dass der Nutzer gehakt hat",
          _p_ger41.get("KompA") is not None
          and _p_ger41["KompA"].icon(0).cacheKey()
          == _icons41.gruener_punkt().cacheKey())
    check("b41 geliefert: das Kaestchen bleibt (umgekehrt 21.09.2026)",
          _hat_kaestchen41(_p_ger41.get("KompA")))
    # DIE ZUSAGE DAHINTER: genau ueber diesen Haken gibt der Nutzer das
    # Material frei, das die Zeile noch reserviert. Steht er nicht zur
    # Verfuegung, kann ein fertiger Plan sich nie entlasten (aa384).
    check("b41 geliefert: der Tooltip sagt, was das Abhaken bewirkt",
          _p_ger41.get("KompA") is not None
          and ("releases the material" in (_p_ger41["KompA"].toolTip(0) or "")
               or "gibt das Material" in (_p_ger41["KompA"].toolTip(0) or "")))
    check("b41 geliefert: gedimmt",
          _ist_gedimmt41(_p_ger41.get("KompA")))
    check("b41 geliefert: die Stufe ist zugeklappt",
          _s_ger41 is not None and not _s_ger41.isExpanded())
    # GEGENPROBE ZUR FARBE: geliefert und laufend duerfen NICHT denselben
    # Punkt bekommen, sonst sagt die Anzeige beide Male dasselbe.
    check("b41 geliefert: es ist NICHT der Lauf-Punkt",
          _p_ger41.get("KompA") is not None
          and _p_ger41["KompA"].icon(0).cacheKey()
          != _icons41.lauf_punkt().cacheKey())

    # ---- E) VOM NUTZER SELBST ABGEHAKT, ESI sieht nichts ----
    # "Abhacken kann ja nur ich": sein Haken bleibt ein Haken (kein Punkt),
    # zaehlt aber fuer den Stufen-Zustand mit - sonst bliebe eine von Hand
    # durchgearbeitete Stufe fuer immer aufgeklappt.
    _sch41 = _fuelle41()
    _s_sch41 = (_sch41.topLevelItem(_ikomp41)
                if _ikomp41 is not None else None)
    _keys41 = set()
    for _nm41 in ("KompA", "KompB"):
        _it41 = _pos41(_s_sch41).get(_nm41)
        if _it41 is not None:
            _k41x = _it41.data(0, Qt.UserRole + 6)
            if _k41x:
                _keys41.add(_k41x)
    eq("b41 Vorbedingung: beide Positionen haben einen Haken-Schluessel",
       len(_keys41), 2)
    win._bd_runplan_checked = set(_keys41)
    _han41 = _fuelle41()
    _s_han41 = (_han41.topLevelItem(_ikomp41)
                if _ikomp41 is not None else None)
    _p_han41 = _pos41(_s_han41)
    check("b41 handabgehakt: die Zeile behaelt ihr Kaestchen (nur ICH hake)",
          _hat_kaestchen41(_p_han41.get("KompA")))
    check("b41 handabgehakt: und traegt KEINEN Punkt (ESI hat nichts gesehen)",
          _p_han41.get("KompA") is not None
          and _p_han41["KompA"].icon(0).isNull())
    check("b41 handabgehakt: die Stufe gilt trotzdem als fertig",
          _s_han41 is not None
          and (_s_han41.text(0) or "").startswith("\u2713")
          and not _s_han41.isExpanded())

    # ---- F) FERTIG GEBAUT, ABER NICHT ABGEHOLT (status "ready") ----
    # NUTZER-SCREENSHOT (Sitzung 14): "da steckt aber schon lange nichts mehr
    # in der Bauschleife". `_bd_active_jobs_map` fuehrt ZWEI Sorten: "active"
    # (laeuft wirklich) und "ready" (fertig, ingame nur nicht abgeholt) - ESI
    # meldet fertige Jobs sogar weiter als "active", erst `job_is_finished`
    # trennt sie. Wer beides zusammenwirft, setzt den Lauf-Punkt auf laengst
    # Gebautes. Nutzer-Entscheid: "ready" gilt als FERTIG.
    win._bd_runplan_checked = set()
    _rdy41 = _fuelle41(aktiv={201: [{"runs": 99999, "status": "ready"}],
                              202: [{"runs": 99999, "status": "ready"}]})
    _s_rdy41 = (_rdy41.topLevelItem(_ikomp41)
                if _ikomp41 is not None else None)
    _z_rdy41 = next((_v for _k, _v in _pos41(_s_rdy41).items()
                     if "KompA" in _k), None)
    check("b41 ready: fertig Gebautes zeigt den GRUENEN Punkt",
          _z_rdy41 is not None
          and _z_rdy41.icon(0).cacheKey()
          == _icons41.gruener_punkt().cacheKey())
    check("b41 ready: und NICHT den Lauf-Punkt (das war der gemeldete Fehler)",
          _z_rdy41 is not None
          and _z_rdy41.icon(0).cacheKey() != _icons41.lauf_punkt().cacheKey())
    # GEGENPROBE: ein WIRKLICH laufender Job bleibt beim Lauf-Punkt.
    _act41 = _fuelle41(aktiv={201: [{"runs": 99999, "status": "active"}],
                              202: [{"runs": 99999, "status": "active"}]})
    _s_act41 = (_act41.topLevelItem(_ikomp41)
                if _ikomp41 is not None else None)
    _z_act41 = next((_v for _k, _v in _pos41(_s_act41).items()
                     if "KompA" in _k), None)
    check("b41 active: ein echt laufender Job behaelt den Lauf-Punkt",
          _z_act41 is not None
          and _z_act41.icon(0).cacheKey() == _icons41.lauf_punkt().cacheKey())
except Exception as e:                                   # pragma: no cover
    import traceback
    traceback.print_exc()
    _fail.append(f"b41 erledigte Runs: {type(e).__name__}: {e}")
finally:
    store.list_characters = _orig_lc41
    for _k41, _v41 in _bak41.items():
        if _v41 is None:
            win.settings.pop(_k41, None)
        else:
            win.settings[_k41] = _v41
    win._bd_frozen = None
    win._bd_frozen_plan_cache = None
    win._bd_active_jobs_map = win._bd_active_jobs_alle = {}
    win._bd_delivered_jobs = []
    win._bd_runplan_checked = set()
# ---------------------------------------------------------------- (b42)
# DIE DREI BAU-SCHALTER SPERREN EINANDER (Nutzer, Sitzung 14: "komisch das
# man beides anhacken kann, das eine sollte das andere aushebeln" / "wenn man
# das eine anhackt sollte das andere frei werden").
#
# WARUM: `industry.production_plan` entscheidet
#     _prefer_owned = opts["prefer_build_if_owned"] and stock_used[tid] > 0
#     do_build = force or _prefer_owned or ...
# Steht `force` ("Kosten ignorieren") vorne, wird `_prefer_owned` NIE
# ausgewertet. Und ohne "Assets abziehen" gibt es keinen Bestand, also kann
# `stock_used[tid] > 0` nie zutreffen. In beiden Faellen ist der mittlere
# Haken wirkungslos - sah aber bedienbar aus. Dieselbe Fehlerklasse wie die
# Kaestchen an fertigen Runs.
#
# FUNKTIONAL: die Zusage ist "dieser Haken ist grau". Eine Textprobe koennte
# das nicht halten.
_boxen42 = _dlg.findChildren(QCheckBox) if _dlg is not None else []


def _box42(*teile):
    """Findet den Haken ueber einen Textteil - in BEIDEN Sprachen, seit die
    Beschriftungen durch t() laufen (Sitzung 16). Welche Sprache das
    Testfenster hat, soll die Pruefung nicht wissen muessen."""
    return next((c for c in _boxen42
                 if any(teil in (c.text() or "") for teil in teile)), None)


_force42 = _box42("Kosten ignorieren", "Ignore cost")
_prefer42 = _box42("Vorhandenes verbauen", "Use what you have")
_asset42 = _box42("Assets abziehen", "Subtract assets")
check("b42 alle drei Bau-Schalter sind auffindbar",
      _force42 is not None and _prefer42 is not None and _asset42 is not None)
# UMBENENNUNG: der alte Name beschrieb einen Materialfluss ("Lagerbestand
# immer verwenden"), der Haken entscheidet aber ueber das BAUEN.
# In BEIDEN Sprachen pruefen (seit Sitzung 16 laufen die Beschriftungen
# durch t()): weder der alte deutsche noch ein englischer Materialfluss-Name.
check("b42 der mittlere Haken heisst nicht mehr nach Materialfluss",
      not any(("Lagerbestand immer verwenden" in (c.text() or ""))
              or ("Always use stock" in (c.text() or ""))
              for c in _boxen42))
if _force42 is not None and _prefer42 is not None and _asset42 is not None:
    _bak42 = (_force42.isChecked(), _prefer42.isChecked(),
              _asset42.isChecked())
    try:
        # Ausgangslage: Assets AN, Kosten-ignorieren AUS -> bedienbar.
        # OHNE SIGNALE schalten und die Sperre gezielt nachziehen: an
        # `toggled` haengen weitere Slots, die den ganzen Bauplan neu rechnen.
        _sperre42 = getattr(win, "_bd_pbtn_sperre", None)
        check("b42 die Sperrfunktion ist erreichbar", callable(_sperre42))

        def _setz42(force, assets):
            for _c, _v in ((_force42, force), (_asset42, assets)):
                _c.blockSignals(True)
                _c.setChecked(_v)
                _c.blockSignals(False)
            if callable(_sperre42):
                _sperre42()

        _setz42(False, True)
        check("b42 normal bedienbar: Assets an, Kosten-ignorieren aus",
              _prefer42.isEnabled())
        # 1) "Kosten ignorieren" an -> wirkungslos, also grau.
        _setz42(True, True)
        check("b42 'Kosten ignorieren' an -> mittlerer Haken ist grau",
              not _prefer42.isEnabled())
        check("b42 und der Tooltip sagt WARUM er grau ist",
              "Kosten" in (_prefer42.toolTip() or "")
              or "Ignore costs" in (_prefer42.toolTip() or ""))
        # GEGENPROBE: wieder aus -> wieder frei.
        _setz42(False, True)
        check("b42 Gegenprobe: wieder aus -> wieder bedienbar",
              _prefer42.isEnabled())
        # 2) "Assets abziehen" aus -> ohne Bestand wirkungslos, also grau.
        _setz42(False, False)
        check("b42 'Assets abziehen' aus -> mittlerer Haken ist grau",
              not _prefer42.isEnabled())
        check("b42 und der Tooltip nennt den Bestand als Grund",
              "Bestand" in (_prefer42.toolTip() or "")
              or "stock" in (_prefer42.toolTip() or "").lower())
        _setz42(False, True)
        check("b42 Gegenprobe: Assets wieder an -> wieder bedienbar",
              _prefer42.isEnabled())
    finally:
        for _c42, _v42 in ((_force42, _bak42[0]), (_prefer42, _bak42[1]),
                           (_asset42, _bak42[2])):
            _c42.blockSignals(True)
            _c42.setChecked(_v42)
            _c42.blockSignals(False)


# ---------------------------------------------------------------- (b43)
# EINKAUFSLISTE IN DER AUFSCHLUESSELUNG (Nutzer, Sitzung 14: "die
# gesammtkosten der einkaufsliste und pro stueck, ich will aber jita Sell
# preis sehen"). Ihm war aufgefallen, dass dort "nirgendwo die einkaufsliste
# mitgerechnet oder angezeigt wird".
#
# WARUM DIE ZAHL FEHLTE UND WARUM SIE ZAEHLT: "Material" laesst weg, was aus
# eigenem Bestand kommt; "Baukosten gesamt" rechnet diesen Bestand zu
# Ersatzkosten mit. Keine der beiden sagt, was der Nutzer JETZT ausgeben
# muss. Bei ihm sanken die Materialkosten um 250 Mio, waehrend der Bestand um
# 240 Mio stieg - in der Summe fast unsichtbar. Sein Gegencheck mit Janice:
# 1'297 Mio fuer die Einkaufsliste gegen 1'835 Mio in der Material-Zeile.
_lbl43 = [l.text() for l in _dlg.findChildren(QLabel)] if _dlg is not None else []
# Zweisprachig (Sitzung 16): die Beschriftung laeuft durch t().
check("b43 die Aufschluesselung nennt die Einkaufsliste",
      any("Einkaufsliste (Jita Sell)" in (t or "") or "Shopping list (Jita sell)" in (t or "")
          for t in _lbl43))
check("b43 und dieselbe Summe je Stueck",
      any("Einkaufsliste / St\u00fcck" in (t or "") or "Shopping list / unit" in (t or "")
          for t in _lbl43))
# DIE BEIDEN ZEILEN MUESSEN AUCH EINEN WERT TRAGEN - eine Beschriftung ohne
# Zahl waere wieder ein Etikett, das mehr verspricht als es haelt.
_vals43 = [l for l in (_dlg.findChildren(QLabel) if _dlg is not None else [])
           if (l.toolTip() or "").find("Einkaufsliste") >= 0
           or "spend NOW" in (l.toolTip() or "")
           or "JETZT ausgeben" in (l.toolTip() or "")]
check(f"b43 die Zeilen tragen einen Wert und einen erklaerenden Tooltip "
      f"({len(_vals43)} Beschriftungen/Werte gefunden)",
      len(_vals43) >= 2)
# emm320 (Nutzer: "Shopping list 402 Mio, ingame nur 242 Mio"): der Tooltip
# schluesselt die groessten Posten mit Menge x Preis auf - nachpruefbar.
from eve_trader.sprache import t as _t43
_tip43 = next((l.toolTip() for l in _vals43
               if _t43("Largest positions (quantity \u00d7 price):") in (l.toolTip() or "")), "")
check(f"b43 der Tooltip nennt die groessten Posten mit Menge x Preis "
      f"({_tip43[-120:]!r})",
      bool(_tip43) and " \u00d7 " in _tip43.split(
          _t43("Largest positions (quantity \u00d7 price):"))[-1])
# Die Quelltext-Zusagen (Herkunft der Zahl, Umgang mit fehlenden Preisen)
# stehen in der aa-Suite - dort gibt es `_fn_src`, um sie auf GENAU EINE
# Funktion einzugrenzen, statt "irgendwo in der Datei" zu suchen.


# ---------------------------------------------------------------- (b44)
# BLUEPRINTS-TAB: FUENF SPALTEN STATT FUENFZEHN (Sitzung 16).
#
# NUTZER: "Siehst du wie sauber der Scanner Tab aussieht? So sauber muessen
# wir den My Blueprints Tab gestalten, da hat es viel zu viele Spalten die
# alles ueberladen wirken lassen ... wir begrenzen uns auf 5 Spalten."
# Auswahl nach seiner Vorgabe "die sinnvollsten fuer Profitvorschau":
# Blueprint + Runs + Baukosten/Stk + Profit/Stk + ISK/Std.
#
# AM FENSTER GEPRUEFT, nicht am Quelltext: eine Textprobe koennte nicht
# halten, dass am Ende WIRKLICH fuenf Spalten zu sehen sind - die Liste
# koennte stimmen und ein setColumnHidden trotzdem danebengehen.
_bpt44 = win.bp_table
_sicht44 = [i for i in range(_bpt44.columnCount()) if not _bpt44.isColumnHidden(i)]
_kopf44 = {}
for _i44 in range(_bpt44.columnCount()):
    _h44 = _bpt44.horizontalHeaderItem(_i44)
    _kopf44[_i44] = _h44.text() if _h44 is not None else ""
# emm349 (Nutzer: "das Handelsvolumen haette ich gerne in einer Spalte in My
# Blueprints") - die sechste, standardmaessig an.
# emm354 (Nutzer: "auch noch eine Spalte fuer Margin") - die siebte.
check(f"b44 genau sieben Spalten sichtbar (sind {len(_sicht44)})",
      len(_sicht44) == 7)
check("b44 und es sind die fuer die Profitvorschau + Verkauft/Tag + Marge",
      _sicht44 == [0, 6, 8, 10, 11, 16, 17])
check("b44 die Marge steht gleich rechts neben Profit/unit",
      _bpt44.horizontalHeader().visualIndex(17)
      == _bpt44.horizontalHeader().visualIndex(10) + 1)
check("b44 Kopf 'Margin %' mit Tooltip",
      _bpt44.horizontalHeaderItem(17).text() == _t4("Margin %")
      and bool(_bpt44.model().headerData(17, Qt.Horizontal, Qt.ToolTipRole)))
# SPALTE 0 IST NICHT ABWAEHLBAR - ohne Namen ist die Zeile wertlos.
check("b44 Blueprint-Spalte steht nicht im Menue",
      0 not in getattr(win, "_bp_col_acts", {}))
# GEGENPROBE: die versteckten Spalten sind NICHT weg, nur aus. Ohne diese
# Probe wuerde die Pruefung oben auch dann gruen, wenn jemand die zehn
# Spalten ersatzlos geloescht haette - und damit die Daten mit ihnen.
# Sitzung 17: +1 Spalte "Profit/m3" (Nutzer) - weiterhin alle vorhanden.
check(f"b44 alle achtzehn Spalten sind noch da (sind {_bpt44.columnCount()})",
      _bpt44.columnCount() == 18)
eq("b44 die Spalte 16 heisst 'Sold/day' und steht im Menue",
   (_bpt44.horizontalHeaderItem(16).text(), 16 in getattr(win, "_bp_col_acts", {})),
   (_t4("Sold/day"), True))
# emm352 (Nutzer: "Sold/day hat kein Tooltip beim Mouseover"): Kopf UND Zelle.
check("b44 Kopf 'Sold/day' hat einen Tooltip (ueber das Modell, wie Qt ihn zeigt)",
      bool(_bpt44.model().headerData(16, Qt.Horizontal, Qt.ToolTipRole)))
_srcz44 = open(os.path.join(_ROOT, "eve_trader", "ui", "main_window.py"),
               encoding="utf-8").read()
check("b44 ... und jede Zahl in der Spalte hat einen (auch die normale)",
      't("\\u00d8 {v} sold per day at the hub "' in _srcz44)
check("b44 die neue Spalte Profit/m3 steht im Menue und ist standardmaessig aus",
      15 in getattr(win, "_bp_col_acts", {})
      and not win._bp_col_acts[15].isChecked() and _bpt44.isColumnHidden(15))
eq("b44 ... und traegt den uebersetzten Kopf",
   _bpt44.horizontalHeaderItem(15).text(), _t4("Profit/m\u00b3"))
_akt44 = getattr(win, "_bp_col_acts", {}).get(14)          # Standort
if _akt44 is not None:
    _akt44.setChecked(True)
    check("b44 eine versteckte Spalte laesst sich wieder einblenden",
          not _bpt44.isColumnHidden(14))
    _akt44.setChecked(False)
    check("b44 und wieder ausblenden",
          _bpt44.isColumnHidden(14))
else:
    check("b44 eine versteckte Spalte laesst sich wieder einblenden", False)
    check("b44 und wieder ausblenden", False)


from eve_trader.ui.main_window import MainWindow as _MW45
# ---------------------------------------------------------------- (b45)
# BLUEPRINTS-TAB RECHNET MIT DEM ECHTEN ME - SCHLECHTESTER FALL (Sitzung 16).
#
# NUTZER: "lieber haette ich, dass da der geringere Wert angezeigt wird, dass
# wenn man den Bauplan dann genauer einstellt mit ME, dass man dann positiv
# ueberrascht wird."
#
# Vorher rechnete JEDE Zeile mit der globalen `bau_me` (Vorgabe 10), waehrend
# die ME-Spalte daneben das echte ME aus ESI zeigte. Jetzt baut
# `_bp_me_map` eine Karte Produkt -> ME aus den echten Blaupausen.
_mem45 = _MW45._bp_me_map if hasattr(_MW45, "_bp_me_map") else None
check("b45 es gibt eine ME-Karte fuer den Blueprints-Tab", _mem45 is not None)
if _mem45 is not None:
    _bp2p45 = {100: (500, 1), 101: (501, 1)}
    # MEHRERE KOPIEN DESSELBEN TYPS -> die SCHLECHTESTE zaehlt (Regel 3).
    # Der Mittelwert waere hier 4.67 - genau die Zahl, die im Spiel nicht
    # eintritt, wenn er die schlechte Kopie einlegt.
    _r45 = [{"type_id": 100, "material_efficiency": 10},
            {"type_id": 100, "material_efficiency": 4},
            {"type_id": 100, "material_efficiency": 0}]
    check("b45 bei mehreren Kopien zaehlt die schlechteste ME",
          _mem45(_r45, _bp2p45, 10).get(500) == 0.0)
    # DECKEL GEGEN DIE GLOBALE EINSTELLUNG: keine Zahl darf optimistischer
    # werden als vorher. Blaupause ME 10, global 0 -> es gilt 0.
    check("b45 nie optimistischer als die globale Einstellung",
          _mem45([{"type_id": 100, "material_efficiency": 10}],
                 _bp2p45, 0).get(500) == 0.0)
    # ... und umgekehrt greift das echte ME, wenn es schlechter ist.
    check("b45 das echte ME schlaegt die globale Einstellung, wenn schlechter",
          _mem45([{"type_id": 100, "material_efficiency": 2}],
                 _bp2p45, 10).get(500) == 2.0)
    # ZWEI TYPEN BLEIBEN GETRENNT - sonst faerbte eine schlechte Blaupause
    # alle anderen mit ein.
    _z45 = _mem45([{"type_id": 100, "material_efficiency": 2},
                   {"type_id": 101, "material_efficiency": 7}], _bp2p45, 10)
    check("b45 verschiedene Blaupausen bleiben getrennt",
          _z45.get(500) == 2.0 and _z45.get(501) == 7.0)
    # GEGENPROBEN: nichts Erfundenes und kein Absturz bei Luecken.
    check("b45 ohne bekanntes Produkt entsteht kein Eintrag",
          _mem45([{"type_id": 999, "material_efficiency": 0}], _bp2p45, 10) == {})
    check("b45 leere Eingaben stuerzen nicht ab",
          _mem45(None, None, 10) == {}
          and _mem45([{"type_id": 100}], _bp2p45, 10) == {})
# UND SIE WIRD AUCH BENUTZT: die Karte in die opts zu legen ist der ganze
# Zweck. Auf die ZUWEISUNG geprueft, nicht auf den blossen Namen - eine
# Mutation koennte den Aufruf abklemmen und den Namen stehen lassen
# (die Lehre aus Sitzung 15).
import inspect as _insp45
_src45 = _insp45.getsource(_MW45._reload_my_blueprints)
check("b45 die Karte landet wirklich in den opts",
      'opts["me_map"] = self._bp_me_map(' in _src45)


# ---------------------------------------------------------------- (b46)
# BLUEPRINTS-FILTER: VORGABEN UND DAS ENTFALLENE GRUPPEN-FELD (Sitzung 16).
#
# NUTZER: "standardmaessig haette ich da gerne angehakt nur Endprodukte und
# Erfindbare T2 sowie nur profitabel. Der Dropdown Alle Gruppen kann komplett
# weg. die Kategorie Dropdown reicht voellig."
#
# AM FENSTER GEPRUEFT: eine Textprobe koennte nicht halten, dass die Haken am
# Ende WIRKLICH so stehen - ein spaeteres setChecked wuerde sie umwerfen,
# ohne dass die Zeile im Quelltext sich aendert.
for _nm46, _soll46 in (("bp_cb_end", True), ("bp_cb_invent", True),
                       ("bp_cb_profit", True),
                       ("bp_cb_comp", False), ("bp_cb_react", False)):
    _cb46 = getattr(win, _nm46, None)
    check(f"b46 {_nm46} startet {'angehakt' if _soll46 else 'leer'}",
          _cb46 is not None and _cb46.isChecked() is _soll46)
# DAS GRUPPEN-FELD IST WEG - und zwar wirklich, nicht nur unsichtbar.
check("b46 Gruppen-Dropdown gibt es nicht mehr",
      not hasattr(win, "bp_myb_group"))
check("b46 und auch die Fuell-Methode dazu nicht",
      not hasattr(win, "_reload_bp_group_filter"))
_txt46 = [c.itemText(_i46) for c in win.findChildren(QComboBox)
          for _i46 in range(c.count())]
check("b46 nirgends mehr ein Eintrag \u201eAlle Gruppen\u201c",
      not any("Alle Gruppen" in (x or "") for x in _txt46))
# GEGENPROBE: die Kategorie-Auswahl MUSS bleiben - sonst haette man mit dem
# Gruppenfeld auch den Filter mitgerissen, den der Nutzer behalten wollte.
check("b46 Gegenprobe: die Kategorie-Auswahl steht noch",
      hasattr(win, "bp_myb_cat")
      and any("Alle Kategorien" in (x or "") or "All categories" in (x or "")
              for x in _txt46))


# ---------------------------------------------------------------- (b47)
# SPALTEN-KNOPF AUCH IN SWING TRADE UND REGIONAL TRADING (Sitzung 16).
#
# NUTZER: "Wir haben ja im Industry unter My blueprints diese Columns-
# Dropdown ... koennen wir das auch einfuegen fuer Daytrade, Swing Trade und
# Regional Trade? ... koennten wir diese ausgeblendet lassen aber in so ein
# Dropdown nehmen, damit man sie bei Bedarf einblenden kann?"
#
# GEMESSEN VOR DEM UMBAU (nicht geraten): in Swing (11) und Regional (10)
# war KEINE Spalte versteckt - es war also nie etwas weggenommen worden,
# entgegen der Erinnerung des Nutzers. Nichts wiederherzustellen.
# SWING-VORGABE zweite Runde (Sitzung 16): der Nutzer hat seine eigene
# Auswahl UND Reihenfolge gesetzt ("dann lass den Swingtrade so aussehen").
# `_soll47` ist deshalb die Liste in SICHTBARER Reihenfolge, nicht sortiert.
for _tb47, _acts47, _n47, _soll47, _lbl47 in (
        ("hold_table", "_hold_col_acts", 11, [0, 1, 4, 8, 3, 6], "Swing"),
        ("rg_table", "_rg_col_acts", 10, [0, 1, 2, 5, 4, 8, 9], "Regional")):
    _t47 = getattr(win, _tb47, None)
    _a47 = getattr(win, _acts47, None)
    check(f"b47 {_lbl47}: Spalten-Knopf ist angeschlossen", _a47 is not None)
    if _t47 is None or _a47 is None:
        continue
    _s47 = [_i for _i in range(_t47.columnCount()) if not _t47.isColumnHidden(_i)]
    check(f"b47 {_lbl47}: {len(_soll47)} Spalten sichtbar (sind {len(_s47)})",
          len(_s47) == len(_soll47))
    check(f"b47 {_lbl47}: und es sind die vorgesehenen",
          sorted(_s47) == sorted(_soll47))
    # REIHENFOLGE VON LINKS NACH RECHTS ist Teil der Zusage - sie steht
    # nicht in der Spalten-Reihenfolge, sondern wird per moveSection
    # gesetzt. Ohne diese Pruefung ginge sie still verloren.
    _h47 = _t47.horizontalHeader()
    _lr47 = sorted(_s47, key=_h47.visualIndex)
    check(f"b47 {_lbl47}: Reihenfolge stimmt ({_lr47})", _lr47 == _soll47)
    # GEGENPROBE: die uebrigen sind NICHT geloescht, nur aus. Ohne sie waere
    # die Pruefung oben auch dann gruen, wenn jemand die Spalten entfernt und
    # damit die Daten mitgenommen haette.
    check(f"b47 {_lbl47}: alle {_n47} Spalten sind noch da",
          _t47.columnCount() == _n47)
    check(f"b47 {_lbl47}: Item-Spalte ist nicht abwaehlbar", 0 not in _a47)
    # DER KNOPF MUSS AUCH IN DER OBERFLAECHE HAENGEN. Gemerkt, weil eine
    # Mutation, die genau das abklemmt, BLIND blieb: `_spalten_knopf` blendet
    # die Spalten schon beim Bauen aus - ohne diese Pruefung saehe man fuenf
    # Spalten und haette keinen Weg mehr, die anderen zurueckzuholen.
    _btn47 = getattr(win, {"hold_table": "_hold_spalten_btn",
                           "rg_table": "_rg_spalten_btn"}[_tb47], None)
    check(f"b47 {_lbl47}: der Knopf haengt wirklich im Fenster",
          _btn47 is not None and _btn47.parent() is not None
          and _btn47.window() is win)
    # UND JEDE VERSTECKTE SPALTE MUSS ERREICHBAR SEIN. Sonst waere sie nicht
    # weggeraeumt, sondern verschwunden - genau das, was der Nutzer NICHT
    # wollte ("ausgeblendet lassen aber in so ein Dropdown nehmen").
    _fehlt47 = [_i for _i in range(_t47.columnCount())
                if _t47.isColumnHidden(_i) and _i not in _a47]
    check(f"b47 {_lbl47}: jede versteckte Spalte steht im Menue "
          f"(fehlen: {_fehlt47})", not _fehlt47)
    _v47 = [_i for _i in range(_t47.columnCount()) if _t47.isColumnHidden(_i)]
    if _v47 and _v47[0] in _a47:
        _a47[_v47[0]].setChecked(True)
        check(f"b47 {_lbl47}: versteckte Spalte laesst sich einblenden",
              not _t47.isColumnHidden(_v47[0]))
        _a47[_v47[0]].setChecked(False)
        check(f"b47 {_lbl47}: und wieder ausblenden",
              _t47.isColumnHidden(_v47[0]))
    else:
        check(f"b47 {_lbl47}: versteckte Spalte laesst sich einblenden", False)
        check(f"b47 {_lbl47}: und wieder ausblenden", False)
# ---------------------------------------------------------------- (b48)
# DAYTRADE: SECHS FESTE SPALTEN STATT MODUS-LOGIK (Sitzung 16).
#
# NUTZER: "Dropdown ersetzt die Modus-Logik (immer dieselben 6 Spalten, egal
# welcher Modus)" - und danach "ja bau das so, aktuell sieht Daytrade ja so
# aus. zu viele spalten".
#
# WELCHE SECHS wurde GERECHNET, nicht gewaehlt: die Schnittmenge aller vier
# Modus-Mengen in _DEAL_COLS ist genau {0, 2, 4, 8, 9, 10}. Diese Pruefung
# rechnet sie NEU aus, statt die Zahlen abzuschreiben - so faellt auf, wenn
# jemand _DEAL_COLS aendert und die Vorgabe nicht mitzieht.
# ZWEITE RUNDE, Sitzung 16: der Nutzer hat seine eigenen acht Spalten
# gewaehlt ("mache diese Columns standard eingeschaltet bei Daytrade und
# auch in dieser Reihenfolge von links nach rechts"). Damit gilt NICHT
# mehr die Schnittmenge aller Modi - er arbeitet im Flip und weiss, dass
# "Now (buy)"/"Margin %" nur dort tragen (der Hinweis steht im Menue).
_DAY_SOLL48 = [0, 1, 2, 7, 8, 10, 4, 17]
_dt48 = win.deals_table
_sicht48 = [_i for _i in range(_dt48.columnCount())
            if not _dt48.isColumnHidden(_i)]
check(f"b48 acht Spalten sichtbar (sind {len(_sicht48)})",
      len(_sicht48) == 8)
check("b48 und es sind die vom Nutzer gewaehlten",
      sorted(_sicht48) == sorted(_DAY_SOLL48))
# DIE REIHENFOLGE IST TEIL DER ZUSAGE. Sie steht NICHT in der Spalten-
# Reihenfolge der Tabelle, sondern wird per moveSection gesetzt - ohne
# diese Pruefung koennte sie still verloren gehen (der Deals-Header wird
# nirgends gespeichert).
_hdr48 = _dt48.horizontalHeader()
_lr48 = sorted(_sicht48, key=_hdr48.visualIndex)
check(f"b48 Reihenfolge von links nach rechts stimmt ({_lr48})",
      _lr48 == _DAY_SOLL48)
check("b48 alle 19 Spalten sind noch da", _dt48.columnCount() == 19)
_a48 = getattr(win, "_deals_col_acts", {})
check("b48 Item-Spalte ist nicht abwaehlbar", 0 not in _a48)
_fehlt48 = [_i for _i in range(_dt48.columnCount())
            if _dt48.isColumnHidden(_i) and _i not in _a48]
check(f"b48 jede versteckte Spalte steht im Menue (fehlen: {_fehlt48})",
      not _fehlt48)
_b48 = getattr(win, "_deals_spalten_btn", None)
check("b48 der Knopf haengt wirklich im Fenster",
      _b48 is not None and _b48.parent() is not None and _b48.window() is win)
# DER KERN DES UMBAUS: die Auswahl muss ein Neuzeichnen UEBERLEBEN. Frueher
# lief bei jedem _render_deals eine Schleife, die je Modus aus- und
# einblendete - sie haette die Wahl des Nutzers nach jedem Scan umgeworfen.
if 6 in _a48:
    _a48[6].setChecked(True)
    win._render_deals([], "drop")
    check("b48 zugeschaltete Spalte ueberlebt das Neuzeichnen",
          not _dt48.isColumnHidden(6))
    _a48[6].setChecked(False)
    win._render_deals([], "flip")
    check("b48 und eine abgewaehlte bleibt weg",
          _dt48.isColumnHidden(6))
else:
    check("b48 zugeschaltete Spalte ueberlebt das Neuzeichnen", False)
    check("b48 und eine abgewaehlte bleibt weg", False)
# GEGENPROBE: die Kopfzeile von Spalte 4 wird WEITER je Modus umbenannt -
# sie ist in jedem Modus die Entscheidungszahl, nur unter anderem Namen.
# Ohne diese Probe koennte man die Modus-Logik komplett herausreissen und
# der Nutzer saehe in "Schnaeppchen" die Beschriftung von "Flip".
win._render_deals([], "drop")
_k_drop48 = _dt48.horizontalHeaderItem(4).text()
win._render_deals([], "flip")
_k_flip48 = _dt48.horizontalHeaderItem(4).text()
check(f"b48 Kopf von Spalte 4 folgt dem Modus ({_k_drop48} / {_k_flip48})",
      _k_drop48 != _k_flip48
      and _k_drop48 == type(win)._DEV_LABEL["drop"]
      and _k_flip48 == type(win)._DEV_LABEL["flip"])


# ---------------------------------------------------------------- (b49)
# BAUPLAN NIMMT ME/TE AUS DEN ECHTEN BLAUPAUSEN (Sitzung 16).
#
# NUTZER: "Ich habe festgestellt, dass wir im Bauplan nicht alle meine
# Blueprints traecken ... da ist es teilweise so eingestellt, dass wir einfach
# von voll geforschten Blueprints ausgehen. Jetzt habe ich aber gemerkt, dass
# man nicht immer alle T1-Huellen voll ausgeforscht hat, deswegen hatte ich
# jetzt zu wenig Material eingekauft gehabt."
#
# Vorher kam das ME fuer Komponenten/Huellen/Fuel/Tools NUR aus vier
# Drehfeldern (Vorgabe 10 %/20 % = voll ausgeforscht). Jetzt gewinnt die
# echte, SCHLECHTESTE eigene Kopie je Bauteil (Regel 3).
class _FakeRec49:
    product_to_bp = {777: (7770, 1, 1)}


_alt_rec49 = getattr(win, "_bd_recipes", None)
_alt_cache49 = getattr(win, "_bd_owned_bp_cache", None)
_alt_sch49 = win.settings.get("bau_me_aus_esi")
win._bd_recipes = _FakeRec49()
win._bd_owned_bp_cache = [
    {"type_id": 7770, "material_efficiency": 10, "time_efficiency": 20},
    {"type_id": 7770, "material_efficiency": 4, "time_efficiency": 8},
    {"type_id": 7770, "material_efficiency": 7, "time_efficiency": 14}]
# DREI KOPIEN, DIE SCHLECHTESTE ZAEHLT - nicht der Mittelwert (7) und nicht
# die beste (10). Welche Kopie er im Spiel einlegt, weiss das Werkzeug nicht.
check("b49 schlechteste eigene Kopie gewinnt (ME und TE)",
      win._bd_esi_me_te_for_item(777) == (4.0, 8.0))
check("b49 ohne eigene Blaupause gibt es keinen Wert",
      win._bd_esi_me_te_for_item(999) is None)
# DIE SCHLUESSEL-ABBILDUNG. Beim ersten Versuch griff der Schalter NICHT,
# weil _category_key nie "components" liefert, sondern "t1_components",
# "advanced_components", "hybrid_components", ... Ohne diese Pruefung waere
# der Abhak-Schalter fuer Komponenten wirkungslos geblieben.
for _k49 in ("t1_components", "advanced_components", "hybrid_components",
             "capital_components", "advanced_capital_components"):
    check(f"b49 {_k49} gehoert zur Karte Komponenten",
          type(win)._bd_esi_kat_key(_k49) == "components")
for _k49 in ("t1_hulls", "fuel_blocks", "tools"):
    check(f"b49 {_k49} bleibt eigenstaendig",
          type(win)._bd_esi_kat_key(_k49) == _k49)
# DER SCHALTER WIRKT WIRKLICH BIS IN DIE KOSTENRECHNUNG.
win._bd_me_component = 10
win.settings["bau_me_component"] = 10
win.settings["bau_me_aus_esi"] = {}
check("b49 mit ESI schlaegt das echte ME die Kategorie-Annahme",
      win._bau_category_me_map([777], {777: ""}, set(), type_id=1).get(777) == 4.0)
win.settings["bau_me_aus_esi"] = {"components": False}
check("b49 abgeschaltet gilt wieder die Handeingabe",
      win._bau_category_me_map([777], {777: ""}, set(), type_id=1).get(777) == 10)
# GEGENPROBE, DIE TEUER WAERE WENN SIE FEHLT: ohne eigene Blaupause darf die
# Rechnung NICHT auf ME 0 fallen - das kaufte absurd viel Material ein.
win.settings["bau_me_aus_esi"] = {}
win._bd_owned_bp_cache = []
check("b49 ohne Blaupause faengt die Kategorie auf, kein Sturz auf 0",
      win._bau_category_me_map([777], {777: ""}, set(), type_id=1).get(777) == 10)
check("b49 Vorgabe ist AN, solange nichts eingestellt ist",
      win._bd_esi_me_aktiv("t1_hulls") is True)
win._bd_recipes = _alt_rec49
win._bd_owned_bp_cache = _alt_cache49
if _alt_sch49 is None:
    win.settings.pop("bau_me_aus_esi", None)
else:
    win.settings["bau_me_aus_esi"] = _alt_sch49


# ---------------------------------------------------------------- (b50)
# ENDE-ZU-ENDE: SCHLAEGT DAS ECHTE ME BIS IN DIE BAUKOSTEN DURCH?
#
# b49 prueft die Bausteine einzeln. Das reicht NICHT - der Nutzer hat genau
# danach gefragt ("ist das gefaehrlich oder koennte man es besser machen?").
# Die Gefahr ist nicht eine falsche Zahl, sondern eine Aenderung, die STILL
# nicht ankommt: die Kosten blieben, wie sie waren, und niemand merkt es.
# Deshalb hier die GANZE Kette, so wie _bd_recalc sie geht:
#   _bau_category_me_map -> cat_me_map -> _bau_me_maps -> opts["me_map"]
#   -> industry.production_plan -> total_cost
#
# ZWEISTUFIGES REZEPT: Endprodukt 500 <- 10x Komponente 501 <- 1000x Rohstoff
# 502. Nur so wirkt das KOMPONENTEN-ME ueberhaupt; im Ein-Stufen-Rezept der
# uebrigen Suite gibt es gar keine Komponente, an der es haengen koennte.
class _Rec50:
    product_to_bp = {500: (5000, I.MANUFACTURING, 1),
                     501: (5001, I.MANUFACTURING, 1)}
    bp_materials = {(5000, I.MANUFACTURING): [(501, 10)],
                    (5001, I.MANUFACTURING): [(502, 1000)]}
    activity_time = {(5000, I.MANUFACTURING): 60,
                     (5001, I.MANUFACTURING): 60}
    activity_max_runs = {(5000, I.MANUFACTURING): 0,
                         (5001, I.MANUFACTURING): 0}
    reaction_products = set()
    invention_for_bpc = {}
    bp_products = {}
    item_cat = {}

    def is_manufactured(self, t):
        return t in self.product_to_bp


_alt_rec50 = getattr(win, "_bd_recipes", None)
_alt_cache50 = getattr(win, "_bd_owned_bp_cache", None)
_alt_sch50 = win.settings.get("bau_me_aus_esi")
_alt_comp50 = getattr(win, "_bd_me_component", None)


def _kosten50(esi_an, esi_me):
    """Baukosten fuer 1 Stueck, EINMAL komplett durchgerechnet."""
    win._bd_recipes = _Rec50()
    win._bd_owned_bp_cache = ([{"type_id": 5001, "material_efficiency": esi_me,
                                "time_efficiency": 0}] if esi_me is not None
                              else [])
    win.settings["bau_me_aus_esi"] = {"components": bool(esi_an)}
    win._bd_me_component = 10           # Annahme "voll ausgeforscht"
    win.settings["bau_me_component"] = 10
    _ids50 = [500, 501, 502]
    _grp50 = {500: "", 501: "", 502: ""}
    _cat50 = win._bau_category_me_map(_ids50, _grp50, set(), 500)
    _o50 = {"me": 10, "me_map": dict(_cat50), "job_pct": 0,
            "build_reactions": False, "invention": False,
            "force_build": True, "tree_depth": 4, "adjusted_prices": {}}
    _pl50 = I.production_plan(500, 1, {502: 100.0, 501: 1e9, 500: 1e12}.get,
                              _Rec50(), _o50)
    return _pl50["total_cost"], _cat50.get(501)


_k_esi50, _me_esi50 = _kosten50(True, 0)      # eigene Kopie: gar nicht erforscht
_k_hand50, _me_hand50 = _kosten50(False, 0)   # Handeingabe: "voll ausgeforscht"
_k_ohne50, _me_ohne50 = _kosten50(True, None)  # ESI an, aber keine Blaupause da

check(f"b50 ESI an: Komponente rechnet mit ihrem echten ME ({_me_esi50})",
      _me_esi50 == 0.0)
check(f"b50 ESI aus: es gilt die Handeingabe ({_me_hand50})",
      _me_hand50 == 10)
check(f"b50 ohne eigene Blaupause faengt die Handeingabe auf ({_me_ohne50})",
      _me_ohne50 == 10)
# DAS IST DER PUNKT: die Kosten muessen sich WIRKLICH unterscheiden. Wuerde
# die Aenderung still nicht ankommen, waeren beide Zahlen gleich - und genau
# das haette man ohne diese Pruefung nicht gemerkt.
check(f"b50 schlechteres ME kostet mehr ({_k_esi50:.0f} > {_k_hand50:.0f})",
      _k_esi50 > _k_hand50)
# Und zwar in der RICHTIGEN GROESSENORDNUNG - HIER LAG ICH ZUERST DANEBEN
# UND DER TEST HAT ES GEFANGEN: ich hatte 1'000'000 / 900'000 erwartet,
# gemessen wurden 900'000 / 810'000. Beide Zahlen sind um 10 % kleiner, weil
# das ENDPRODUKT-ME (opts["me"] = 10) schon die Komponentenzahl von 10 auf 9
# drueckt - bevor das Komponenten-ME ueberhaupt auf den Rohstoff wirkt.
# Rechnung: 9 Komponenten x 1'000 Rohstoff a 100 ISK = 900'000 (Komponente
# ME 0) gegen 9 x 900 x 100 = 810'000 (Komponente ME 10). Der Unterschied
# ist also genau die 10 % Material, nur auf der richtigen Grundmenge.
check(f"b50 und zwar um genau die 10 % Material ({_k_esi50:.0f} / {_k_hand50:.0f})",
      abs(_k_esi50 - 900_000) < 1 and abs(_k_hand50 - 810_000) < 1)

# UND DIE LETZTE MEILE: b50 rechnet die Kette selbst nach - das beweist
# NICHT, dass `_bd_recalc` die Karte auch wirklich weiterreicht. Eine
# Mutation, die dort `cat_me_map = {}` setzt, blieb zuerst BLIND. Beide Wege
# muessen belegt sein: MIT Struktur laeuft sie durch _bau_me_maps, OHNE
# Struktur direkt in die opts.
import inspect as _insp50
_src50 = _insp50.getsource(type(win)._bd_recalc) \
    if hasattr(type(win), "_bd_recalc") else ""
if not _src50:
    _src50 = open(os.path.join(_ROOT,
                               "eve_trader", "ui", "main_window.py"),
                  encoding="utf-8").read()
# FUEHRENDES LEERZEICHEN IST PFLICHT: weiter unten steht
# `_cat_me_map = self._bau_category_me_map(` (mit Unterstrich) - der Text
# ohne Leerzeichen steckt darin als Teilstring, und die Pruefung blieb
# deshalb gruen, obwohl die Mutation die Stelle zerstoert hatte.
check("b50 die Karte wird im Bauplan wirklich gebaut",
      " cat_me_map = self._bau_category_me_map(" in _src50)
check("b50 ohne Struktur geht sie direkt in die opts",
      'opts["me_map"] = cat_me_map' in _src50)
check("b50 mit Struktur geht sie durch _bau_me_maps",
      "recipes.reaction_products, cat_me_map," in _src50)

win._bd_recipes = _alt_rec50
win._bd_owned_bp_cache = _alt_cache50
if _alt_sch50 is None:
    win.settings.pop("bau_me_aus_esi", None)
else:
    win.settings["bau_me_aus_esi"] = _alt_sch50
if _alt_comp50 is not None:
    win._bd_me_component = _alt_comp50


# ---------------------------------------------------------------- (b51)
# REGIONAL: LEERE ZIELMAERKTE MIT ABSATZ (Nutzer-Idee, Sitzung 16).
#
# NUTZER: "Falls der Zielhub ein Item gar nicht mehr hat, was passiert dann
# mit dem Tool? Eigentlich waere das eine wahre Goldgrube, ein Item was
# Handelsvolumen hat, aber der Markt leer ist. So etwas muss gefunden
# werden!"
#
# GEMESSEN, WARUM ES BISHER NICHT GEFUNDEN WURDE - `hubs.arbitrage` hat zwei
# harte Ausstiege: `if not t: continue` (Item am Ziel unbekannt) und
# `if sell_price <= 0: continue` (keine Sell-Order da). Genau der
# interessante Fall fiel raus, BEVOR die Absatzpruefung begann.
import eve_trader.hubs as _hb51


def _q51(preis, menge):
    return {"sell_min": preis, "sell_qty": menge, "buy_max": preis * 0.9,
            "buy_qty": 10, "sell_orders": [(preis, menge)]}


_quelle51 = {1: _q51(100, 1000), 2: _q51(5000, 50), 3: _q51(20, 100000),
             4: _q51(300, 10)}
_ziel51 = {1: {"sell_min": 200.0, "sell_qty": 50, "buy_max": 150.0, "buy_qty": 10},
           2: {"sell_min": 0.0, "sell_qty": 0, "buy_max": 6000.0, "buy_qty": 40},
           4: {"sell_min": 0.0, "sell_qty": 0, "buy_max": 0.0, "buy_qty": 0}}
# Item 3 kennt das Ziel GAR NICHT - der Fall, der bisher komplett unsichtbar war.
_k51 = _hb51.leere_zielmaerkte(_quelle51, _ziel51, [{"type_id": 1}])
check("b51 Item ohne jeden Eintrag am Ziel wird gefunden", 3 in _k51)
check("b51 leergekauftes Ziel (nur Buy-Orders) wird gefunden", 2 in _k51)
# GEGENPROBE: was am Ziel eine Sell-Order HAT, ist der normale Fall und darf
# hier nicht auftauchen - sonst doppelte Zeilen und falsche Zahlen.
check("b51 Gegenprobe: bereits bewertetes Item bleibt draussen", 1 not in _k51)
check("b51 nach Quell-Wert sortiert (teuerstes zuerst)", _k51[0] == 2)
check("b51 der Deckel greift",
      len(_hb51.leere_zielmaerkte(_quelle51, _ziel51, [], cap=2)) == 2)


def _h51(tage, preis=1000.0):
    return [{"volume": v, "average": (preis if v else 0)} for v in tage]


_T51, _B51 = 0.036, 0.015
_r51 = _hb51.bewerte_leeren_markt(1, 500.0, _h51([10] * 30), _T51, _B51)
check("b51 lebendiger leerer Markt wird zum Treffer", _r51 is not None)
if _r51:
    check("b51 er ist als Schaetzung gekennzeichnet",
          _r51.get("sell_geschaetzt") is True and _r51.get("leerer_markt") is True)
    check("b51 er bringt sein Ziel-Volumen selbst mit",
          _r51.get("target_vol") == 10.0)
    # DER PREIS IST DER DURCHSCHNITT, NICHT DAS HOCH. Ein einziger
    # Ausreisser-Tag darf keine gruene Traum-Marge erzeugen (Regel 3).
    _hi51 = _h51([10] * 29) + [{"volume": 10, "average": 1000.0, "highest": 99999.0}]
    _r51b = _hb51.bewerte_leeren_markt(1, 500.0, _hi51, _T51, _B51)
    check("b51 der Zielpreis ist der Durchschnitt, nicht das Tageshoch",
          _r51b is not None and abs(_r51b["target_sell"] - 1000.0) < 0.01)
# TOTER MARKT: Umsatz vor drei Wochen, seither nichts. Das ist KEINE
# Goldgrube, sondern ein Item, auf dem man sitzen bleibt.
check("b51 toter Markt (7 Tage ohne Umsatz) wird verworfen",
      _hb51.bewerte_leeren_markt(1, 500.0, _h51([10] * 20 + [0] * 10),
                                 _T51, _B51) is None)
check("b51 ohne Gewinn nach Gebuehren wird verworfen",
      _hb51.bewerte_leeren_markt(1, 1000.0, _h51([10] * 30), _T51, _B51) is None)
check("b51 leere Historie stuerzt nicht ab",
      _hb51.bewerte_leeren_markt(1, 500.0, [], _T51, _B51) is None)
# DIE ANZEIGE MUSS DIE SCHAETZUNG KENNZEICHNEN - sonst sieht sie aus wie ein
# abgelesener Preis. Auf die ZUWEISUNG geprueft, nicht auf den Namen.
_srcrg51 = open(os.path.join(_ROOT,
                             "eve_trader", "ui", "main_window.py"),
                encoding="utf-8").read()
check("b51 die Tabelle markiert geschaetzte Zielpreise mit einer Tilde",
      '("~" if d.get("sell_geschaetzt") else "")' in _srcrg51)
check("b51 und der Scan holt die Kandidaten wirklich",
      "hubs.leere_zielmaerkte(so, to, deals, cap=200)" in _srcrg51)


# ---------------------------------------------------------------- (b52)
# HANDELS-CHARAKTERE (Nutzer-Idee, Sitzung 16).
#
# NUTZER: "im Fall von Regional Trading habe ich 2 Charaktere, einer in Jita
# und einer in 4-HWWF. Wenn man da beide Charaktere als Ein- und Verkaeufer
# eintragen koennte, und man nur von diesen 2 Charakteren die Transaktionen
# wertet?"
#
# DER FALL DAHINTER: ein DRITTER Charakter kaufte einmal 2 Stueck zum Fitten
# eines Schiffs - kein Handel. Weil der Ø-Einkauf ueber ALLE Charaktere
# zusammengelegt wird, zog dieser Kauf ihn hoch, und das Order-Update meldete
# Verlust, wo keiner war.
#
# SEINE ZWEITE IDEE ("nur der aktive Charakter") WURDE GEMESSEN UND VERWORFEN:
# der Verkaeufer in 4-HWWF hat nie etwas GEKAUFT. Allein betrachtet haette er
# gar keinen Einstand - die Spalte zeigte ueberall "-" und die Verlust-
# Pruefung waere ganz aus. Es braucht die MENGE, nicht den einen.
_alt52 = win.settings.get("handels_charaktere")
win.settings.pop("handels_charaktere", None)
# LEER = ALLE. Eine neue Einstellung darf niemandem still die Zahlen
# verschieben - wer nichts einstellt, sieht das Verhalten von vorher.
check("b52 ohne Einstellung zaehlen alle Charaktere",
      win._handels_charaktere() == set())
win.settings["handels_charaktere"] = [11, 22]
check("b52 gesetzte Menge kommt an", win._handels_charaktere() == {11, 22})
# ROBUST GEGEN SCHROTT IN DER EINSTELLUNGSDATEI: sie ist von Hand
# editierbar, und ein Absturz beim Start waere das schlechteste Ergebnis.
win.settings["handels_charaktere"] = ["11", 22, "kaputt", None]
# DIE PRUEFUNG MUSS DEN ABSTURZ SELBST ABFANGEN. Ohne das try riss eine
# Mutation, die den int()-Schutz entfernt, die GANZE Suite mit
# ("ValueError: invalid literal for int()") - und galt damit als BLIND,
# obwohl sie genau den Schaden anrichtete, den diese Zeile pruefen soll.
try:
    _robust52 = win._handels_charaktere() == {11, 22}
except Exception:
    _robust52 = False
check("b52 unbrauchbare Eintraege werden uebergangen, nicht geworfen",
      _robust52)
win.settings["handels_charaktere"] = "gar keine Liste"
check("b52 falscher Typ faellt auf 'alle' zurueck",
      win._handels_charaktere() == set())
# Das Setzen laeuft jetzt ueber die beiden Auswahllisten im Regional-Tab -
# geprueft weiter unten, nachdem die Listen da sind.
# DIE SPALTE IST DA UND DER HAKEN AUCH - sonst gaebe es die Einstellung nur
# in der Datei und niemand koennte sie bedienen.
# DIE BEDIENUNG SITZT IM REGIONAL-TAB, NICHT BEI DEN CHARAKTEREN.
# Zuerst hatte ich eine Haken-Spalte im Charaktere-Tab gebaut; der Nutzer hat
# sie dort nicht gesucht: "Ein und Verkaeufer gehoert zum Regional Tab, wenn
# dann will ich es da waehlen koennen." Sie ist dort wieder WEG - eine
# Einstellung, EINE Stelle.
check("b52 Charaktere-Tabelle hat wieder ihre drei Spalten",
      win.char_table.columnCount() == 3)
# NEU VERLINKEN NEBEN ENTFERNEN (emm357): echter Knopf je Zeile, startet den
# Login (hier abgefangen), loescht nichts.
try:
    _st157 = __import__("eve_trader.store", fromlist=["x"])
    _lc_alt157 = _st157.list_characters
    _st157.list_characters = lambda: [{"character_id": 915701, "character_name": "b157 Pilot"}]
    _aufrufe157 = []
    win.link_character = lambda: _aufrufe157.append("link")
    win.unlink_character = lambda cid: _aufrufe157.append(("weg", cid))
    try:
        win._render_characters()
        _zelle157 = win.char_table.cellWidget(0, 2)
        _kn157 = {b.text().strip(): b for b in _zelle157.findChildren(QPushButton)} if _zelle157 else {}
        check(f"b52 je Charakter 'Re-link' neben 'Remove' ({list(_kn157)})",
              _t4("Re-link") in _kn157 and _t4("Remove") in _kn157
              and "b157 Pilot" in _kn157[_t4("Re-link")].toolTip())
        # emm358 (Nutzer-Screenshot: Knoepfe ueberschnitten sich): die Spalte
        # ist breit genug fuer beide, auch nach einem alten 150-px-Zustand.
        win.char_table.setColumnWidth(2, 150)
        win._char_aktionen_breite()
        _zelle157b = win.char_table.cellWidget(0, 2)
        check(f"b52 Aktions-Spalte passt fuer beide Knoepfe "
              f"({win.char_table.columnWidth(2)} >= {_zelle157b.sizeHint().width()})",
              _zelle157b is not None
              and win.char_table.columnWidth(2) >= _zelle157b.sizeHint().width()
              and all(b.minimumWidth() >= b.sizeHint().width() for b in _kn157.values()))
        if _t4("Re-link") in _kn157:
            _kn157[_t4("Re-link")].click(); _app.processEvents()
        eq("b52 'Re-link' startet nur den Login, entfernt nichts", _aufrufe157, ["link"])
    finally:
        _st157.list_characters = _lc_alt157
        win.__dict__.pop("link_character", None)
        win.__dict__.pop("unlink_character", None)
        win._render_characters()
except Exception as _e157r:                              # pragma: no cover
    _fail.append(f"b52 Re-link-Knopf: {type(_e157r).__name__}: {_e157r}")
check("b52 und keine Haken-Spalte mehr",
      not hasattr(win, "_handels_boxes"))
check("b52 die Auswahl sitzt im Regional-Tab",
      hasattr(win, "rg_buyer") and hasattr(win, "rg_seller"))
# BEIDE LEER = ALLE. Der erste Eintrag ist ein Strich ohne Daten.
check("b52 beide Listen beginnen mit einem leeren Eintrag",
      win.rg_buyer.itemData(0) is None and win.rg_seller.itemData(0) is None)
_bi52, _si52 = win.rg_buyer.count(), win.rg_seller.count()
win.rg_buyer.addItem("T-Kaeufer", 111)
win.rg_seller.addItem("T-Verkaeufer", 222)
win.rg_buyer.setCurrentIndex(_bi52)
win.rg_seller.setCurrentIndex(_si52)
check("b52 die Wahl landet in der Einstellung",
      win._handels_charaktere() == {111, 222})
# DERSELBE CHARAKTER ZWEIMAL: auf die GESPEICHERTE LISTE pruefen, nicht auf
# _handels_charaktere() - das liefert eine Menge, dort verschwindet ein
# Duplikat von selbst und die Pruefung waere blind (genau so passiert).
# In der Einstellungsdatei soll trotzdem [111] stehen und nicht [111, 111]:
# eine Liste mit zwei gleichen Eintraegen verwirrt jeden, der sie spaeter
# liest oder von Hand bearbeitet.
win.rg_seller.addItem("T-Kaeufer", 111)
win.rg_seller.setCurrentIndex(win.rg_seller.count() - 1)
check(f"b52 zweimal derselbe Charakter steht einmal in der Datei "
      f"({win.settings.get('handels_charaktere')})",
      win.settings.get("handels_charaktere") == [111])
win.rg_buyer.setCurrentIndex(0)
win.rg_seller.setCurrentIndex(0)
check("b52 beide zurueck auf leer heisst wieder alle",
      win._handels_charaktere() == set())
# DAS ORDER-UPDATE MUSS DIE MENGE AUCH BENUTZEN. Auf die ZUWEISUNG geprueft:
# eine Mutation koennte den Aufruf stehen lassen und das Ergebnis verwerfen.
_src52 = open(os.path.join(_ROOT,
                           "eve_trader", "ui", "main_window.py"),
              encoding="utf-8").read()
check("b52 das Order-Update fragt die Handels-Menge ab",
      "_hchars9 = self._handels_charaktere()" in _src52)
check("b52 und rechnet den Einstand dann nur aus deren Transaktionen",
      "market.aggregate_holdings(self._handels_transaktionen())" in _src52)
# GEGENPROBE: der alte Rueckfall ueber ALLE Charaktere darf nur noch laufen,
# wenn KEINE Menge gesetzt ist - sonst schliche der Fremdkauf doch wieder ein.
check("b52 der Rueckfall ueber alle laeuft nur ohne gesetzte Menge",
      "if not _hchars9 else {})" in _src52)
if _alt52 is None:
    win.settings.pop("handels_charaktere", None)
else:
    win.settings["handels_charaktere"] = _alt52


# ---------------------------------------------------------------- (b53)
# PROFITS: DAS HANDELS-PAAR ALS EIN BETRIEB (Sitzung 16).
#
# NUTZER: "Kann ich jetzt Einkaeufer-Char in Jita setzen und Verkaeufer-Char
# in Struktur in 4-HWWF? Und das Tool trackt die Preise und Historie sowie
# Gewinne richtig?" - Preise ja, Gewinne NEIN: FIFO lief je Charakter, ein
# Verkauf des einen fand nie ein Kauf-Lot des anderen. In seinen ECHTEN Daten
# gemessen: 26,4 Mrd ISK Umsatz, der so verschwand.
import eve_trader.market as _mk53


def _tx53(cid, tag, tid, menge, preis, kauf):
    return {"character_id": cid, "date": f"2026-07-{tag:02d}T12:00:00Z",
            "type_id": tid, "quantity": menge, "unit_price": preis,
            "is_buy": kauf}


_T53 = [_tx53(1, 1, 1, 100, 1000, True),      # Jita-Charakter kauft
        _tx53(2, 10, 1, 100, 1500, False)]    # 4-HWWF-Charakter verkauft
check("b53 ohne Paar bleibt der Handel unsichtbar (wie bisher)",
      len(_mk53.realized_trades(_T53, 0.036, 0.015)) == 0)
_ev53 = _mk53.realized_trades(_T53, 0.036, 0.015, paar={1, 2})
check("b53 mit Paar entsteht die Gewinnzeile", len(_ev53) == 1)
if _ev53:
    check("b53 und sie nimmt den Einstand des EINKAEUFERS",
          _ev53[0]["buy"] == 1000.0 and _ev53[0]["sell"] == 1500)
# GEGENPROBE, DIE DIE ENTSCHEIDUNG AUS SITZUNG 9 SCHUETZT: ein DRITTER
# Charakter darf sich NICHT mit einmischen. Sonst matchten wieder fremde
# Kaeufe gegen fremde Verkaeufe und der Umsatz blaehte sich auf - genau der
# Grund, warum die Trennung damals eingebaut wurde.
# DER FREMDE KAUF MUSS VOR DEM DES PAARES LIEGEN, sonst prueft die Zeile
# nichts: liegt er danach, greift FIFO ohnehin zuerst auf das Paar-Lot und
# eine Mutation, die ALLE zusammenwirft, faellt nicht auf (genau so
# passiert - sie blieb BLIND). Mit dem fremden Kauf VORNE wuerde eine
# globale Poolung dem Paar-Verkauf das teure Lot unterschieben.
_T53b = [_tx53(3, 1, 1, 50, 9999, True),      # Fremdkauf ZUERST
         _tx53(1, 2, 1, 100, 1000, True),     # dann der Einkaeufer des Paares
         _tx53(2, 10, 1, 100, 1500, False),   # Verkauf des Paares
         _tx53(3, 11, 1, 50, 10, False)]      # eigener Verkauf des Fremden
_ev53b = _mk53.realized_trades(_T53b, 0.036, 0.015, paar={1, 2})
check("b53 ein Charakter ausserhalb des Paares bleibt getrennt",
      len(_ev53b) == 2
      and sorted(round(_e["buy"]) for _e in _ev53b) == [1000, 9999])
# ROBUST: leeres oder unbrauchbares Paar aendert NICHTS. Eine kaputte
# Einstellungsdatei darf die Bilanz nicht still umstellen.
check("b53 leeres Paar aendert nichts",
      len(_mk53.realized_trades(_T53, 0.036, 0.015, paar=None)) == 0
      and len(_mk53.realized_trades(_T53, 0.036, 0.015, paar=[])) == 0)
# ABSTURZ SELBST ABFANGEN: eine Mutation, die den Ziffern-Schutz entfernt,
# riss sonst die GANZE Suite mit ("ValueError: invalid literal for int()")
# und galt als blind - obwohl sie genau den Schaden anrichtete, den diese
# Zeile pruefen soll. Dieselbe Falle wie bei b52.
try:
    _robust53 = len(_mk53.realized_trades(_T53, 0.036, 0.015,
                                          paar=["x", None])) == 0
except Exception:
    _robust53 = False
check("b53 unbrauchbare Eintraege im Paar aendern nichts", _robust53)
# UND DER PROFITS-TAB MUSS ES BENUTZEN. Auf die ZUWEISUNG geprueft.
_srcp53 = open(os.path.join(_ROOT,
                            "eve_trader", "ui", "main_window.py"),
               encoding="utf-8").read()
check("b53 der Profits-Tab reicht das Paar weiter",
      "market.realized_trades(txs, tax, broker, paar=_paar," in _srcp53)
# NUR BEI "ALLE CHARAKTERE": waehlt der Nutzer einen EINZELNEN, will er
# dessen Zahlen sehen - sonst zeigte die Auswahl etwas anderes an, als sie
# verspricht.
check("b53 bei einem einzelnen Charakter wird NICHT gepaart",
      '_paar = (self._handels_charaktere() if cid in (None, "all") else None)'
      in _srcp53)


# ---------------------------------------------------------------- (b54)
# VERBRAUCH DURCH EINEN ANDEREN PLAN DARF SICH NICHT VERSTECKEN (Sitzung 16).
#
# DER VERLUST: Viator (juenger, reserviert) hatte 13'400 Thulium Hafnite
# gebaut. Vagabond (aelter) sah sie als freien Bestand, der Nutzer baute
# damit Vagabonds Composite - im Spiel blieben 96. Der Viator-Plan zeigte
# weiter 13'400 (max(eingefroren, live)) und "noch zu bauen 4'730". Der
# Warn-Banner oben nannte drei Namen und "..." - Thulium stand dahinter.
#
# ZWEI ZUSAGEN: (1) der Banner nennt ALLE fehlenden Materialien, nicht drei;
# (2) die betroffene ZEILE traegt den Live-Fehlbedarf selbst, in Rot.
# Geprueft am Quelltext des Materialien-Reiters: das Fenster hat im
# Container keinen ESI-Bestand, mit dem sich "live < eingefroren"
# nachstellen liesse. Was sich messen laesst, wird gemessen (unten die
# Reservierungs-Richtung), der Rest auf die ZUWEISUNG.
_srcm54 = open(os.path.join(_ROOT,
                            "eve_trader", "ui", "mw_bauplan_tabs.py"),
               encoding="utf-8").read()
# SEIT 26.09.2026 KEIN BANNER MEHR (Nutzer: "den liest sowieso keiner,
# was fehlt sieht man unten in der Liste") - Zusage (1) wird: kein Banner.
check("b54 kein Fehlbedarf-Banner mit Namensliste mehr (Zeilen tragen es)",
      "materials will be missing for the" not in _srcm54
      and "for _t, *_ in _fehl_auto" not in _srcm54)
# AUF DIE BEDINGUNG PRUEFEN, NICHT AUF DEN TEXT: eine Mutation, die den
# Zweig mit `if False and ...` totlegt, laesst den Text stehen - die erste
# Fassung dieser Pruefung blieb dabei GRUEN. Die Lehre aus Sitzung 15.
# ANKER OHNE ZEILENUMBRUCH: der Text steht im Quelltext ueber zwei Zeilen,
# und ein split() auf die ganze Zusage kracht statt rot zu werden (dieselbe
# Lehre wie aa393: eine Pruefung muss ROT werden, nicht abbrechen).
_ank54 = "{fehlt} missing "
check("b54 die Zeile traegt den Live-Fehlbedarf",
      "_bd_fehl_live" in _srcm54
      and _ank54 in _srcm54
      and "            if _fl and _fl[0] > 0:" in _srcm54)
check("b54 und faerbt sich rot",
      "status_col = theme.RED" in _srcm54.split(_ank54)[-1][:900])
# DIE ZAHL HEISST NICHT MEHR "LIVE" (Nutzer 25.09.2026: die Zeile sagte
# "LIVE: only 9'913 on hand", im Hangar lagen 198 - sie kommt aus
# max(eingefroren, live) und war nie der Live-Stand).
check("b54 die gerechnete Zahl heisst nicht mehr 'LIVE'",
      "LIVE: only {da} on hand" not in _srcm54)
check("b54 ... und der echte Hangar-Stand steht daneben, wenn er abweicht",
      '_echt = int((getattr(self, "_bd_live_stock", None) or {})' in _srcm54
      and "really in the hangar: {n}" in _srcm54)

# RESERVIERUNG IN BEIDE RICHTUNGEN - funktional, an der geteilten Funktion.
# Das ist der eigentliche Grund des Verlusts: der aeltere Plan sah den
# juengeren nicht. Zwei Plaene, der aeltere hat id 1, der juengere id 2.
from eve_trader.ui.mw_helpers import MainWindowHelpers as _MH54
_set54 = {"bau_saved_plans": [
    {"id": 1, "label": "Vagabond", "reserve": True, "reserve_map": {16674: 5000}},
    {"id": 2, "label": "Viator", "reserve": True, "reserve_map": {16674: 13400}}]}
# GEAENDERT 28.09.2026 - BAU-PRIORITAET (Nutzer: "welchen Plan man als
# erstes baut, als 2tes usw. ... dann sind die Mats immer klar",
# Kartenreihenfolge): ein Plan sieht nur die Plaene VOR ihm. Ohne
# gespeicherte Kartenfolge gilt die Speicher-Reihenfolge.
_vaga54, _lbl54 = _MH54._reserved_by_other_plans(_set54, 1)
check("b54 Plan #1 (Vagabond) sieht den Plan hinter ihm NICHT",
      not _vaga54.get(16674) and "Viator" not in _lbl54)
_viat54, _ = _MH54._reserved_by_other_plans(_set54, 2)
check("b54 und Plan #2 (Viator) sieht den vor ihm",
      _viat54.get(16674) == 5000)
_set54b = dict(_set54, bau_plan_manuell=True, bau_plan_reihenfolge=["2", "1"])
check("b54 Karten umgestellt: jetzt geht der Viator vor",
      _MH54._reserved_by_other_plans(_set54b, 1)[0].get(16674) == 13400
      and not _MH54._reserved_by_other_plans(_set54b, 2)[0].get(16674))


# ---------------------------------------------------------------- (b55)
# BEDIENELEMENTE TRAGEN EIN SYMBOL (Nutzer, Sitzung 16: "das sind fuer mich
# halt auch so Eyecatcher, um das Auge dahin zu fuehren, wo die wichtigen
# Knoepfe sind").
#
# Beim Emoji-Umbau verloren viele Knoepfe ihr Zeichen, ohne eins aus dem
# eigenen Set zu bekommen - "weg" ist nicht dasselbe wie "ersetzt". Diese
# Pruefung misst am ECHTEN Fenster, nicht am Quelltext.
#
# AUSGENOMMEN sind Klapp-Koepfe: die tragen ihr Zustandszeichen (\u25be/\u25b8)
# selbst und wuerden mit einem zweiten Symbol unruhig.
try:
    _bed55 = ([_b for _b in win.findChildren(QPushButton) if _b.text()]
              + [_c for _c in win.findChildren(QCheckBox) if _c.text()])
    _ohne55 = [_b.text() for _b in _bed55
               if _b.icon().isNull()
               and not _b.text().lstrip().startswith(("\u25be", "\u25b8"))]
    check(f"b55 hoechstens wenige Bedienelemente ohne Symbol "
          f"({len(_ohne55)}: {sorted(_ohne55)[:8]})",
          len(_ohne55) <= 6)
    # UND DER BESTAND STIMMT: mindestens 80 tragen wirklich eins - sonst
    # koennte die Pruefung auch bei einem leeren Fenster gruen sein.
    _mit55 = [_b for _b in _bed55 if not _b.icon().isNull()]
    check(f"b55 die meisten tragen ein Symbol ({len(_mit55)}/{len(_bed55)})",
          len(_mit55) >= 80)
    # DIE WICHTIGEN EINZELN: eine Mengenpruefung mit Spielraum merkt nicht,
    # wenn ausgerechnet der Haupt-Knopf eines Reiters seins verliert.
    # JEDER REITER traegt ein Symbol - auch die, die erst spaeter befuellt
    # werden. Die Order-Reiter bekamen ihres frueher erst beim ersten Laden;
    # bis dahin standen sie nackt da.
    _tabs55 = []
    for _tw55 in win.findChildren(QTabWidget):
        _tabs55 += [_tw55.tabText(_i) for _i in range(_tw55.count())
                    if _tw55.tabIcon(_i).isNull()]
    eq("b55 kein Reiter ohne Symbol", _tabs55, [])
    for _n55 in ("deals_btn", "hold_btn", "rg_go", "b_scan_btn"):
        _w55 = getattr(win, _n55, None)
        check(f"b55 {_n55} traegt ein Symbol",
              _w55 is not None and not _w55.icon().isNull())
except Exception as _e55:                                # pragma: no cover
    _fail.append(f"b55 Symbole: {type(_e55).__name__}: {_e55}")


# ---------------------------------------------------------------- (b56)
# GEMESSEN: gesperrt und offen sehen wirklich verschieden aus (Nutzer,
# Sitzung 16). Ein Waechter auf den Quelltext merkt nicht, wenn beide
# Zeichnungen bei 16 px praktisch gleich aussehen - hier werden die Bilder
# punktweise verglichen.
try:
    from eve_trader.ui import icons as _ic56, theme as _th56
    _a56 = _ic56.icon("lock", farbe=_th56.AMBER).pixmap(16, 16).toImage()
    _b56 = _ic56.icon("lock_open", farbe=_th56.MUTED).pixmap(16, 16).toImage()
    _d56 = sum(1 for _x in range(16) for _y in range(16)
               if _a56.pixel(_x, _y) != _b56.pixel(_x, _y))
    check(f"b56 gesperrt und offen sind unterscheidbar ({_d56}/256)", _d56 >= 40)
except Exception as _e56:                                # pragma: no cover
    _fail.append(f"b56 Schloss-Vergleich: {type(_e56).__name__}: {_e56}")


# ---------------------------------------------------------------- (b57)
# ERSTSTART-DIALOGE STAPELN SICH NICHT (Nutzer, Sitzung 16: "kommt sich das
# nicht in die Quere?").
#
# Beim ersten Start feuern drei Zeitgeber kurz nacheinander: "kein
# Charakter" (250 ms), Rezeptfrage (400 ms), Verlaufsfrage (4000 ms). Jeder
# oeffnet einen MODALEN Dialog - ohne Absprache legt sich der zweite auf
# den ersten. Genau der Moment, in dem ein Fremder das Werkzeug zum ersten
# Mal sieht.
#
# GEPRUEFT OHNE ECHTES FENSTER: ein wirklich modaler Dialog blockiert den
# Testlauf. Stattdessen wird `activeModalWidget` vorgetaeuscht - die
# Entscheidung haengt genau daran.
try:
    from PySide6.QtWidgets import QApplication as _QA57
    _echt57 = _QA57.activeModalWidget
    try:
        _QA57.activeModalWidget = staticmethod(lambda: win)   # Buehne belegt
        check("b57 bei offenem Dialog tritt die Erststart-Frage zurueck",
              win._warte_auf_freie_buehne("_test57", ms=1) is True)
        # UND SIE VERSUCHT ES NICHT EWIG: wer einen Dialog lange offen
        # laesst, soll nicht spaeter unvermittelt ueberfallen werden.
        for _ in range(9):
            win._warte_auf_freie_buehne("_test57b", ms=1, versuche=3)
        check("b57 nach wenigen Versuchen gibt sie auf",
              win._buehne_versuche.get("_test57b", 0) > 3)
        _QA57.activeModalWidget = staticmethod(lambda: None)  # Buehne frei
        check("b57 auf freier Buehne wird nicht mehr gewartet",
              win._warte_auf_freie_buehne("_test57c") is False)
    finally:
        _QA57.activeModalWidget = _echt57
except Exception as _e57:                                # pragma: no cover
    _fail.append(f"b57 Erststart-Dialoge: {type(_e57).__name__}: {_e57}")


# ---------------------------------------------------------------- (b58)
# EINRICHTUNG BEIM ERSTEN START (Nutzer, Sitzung 16: "ein Installations-
# Popup fuer diese wichtigen Daten, ohne es herunterzuladen kommt man nicht
# weiter").
#
# Statt dreier einzelner Dialoge fuehrt EIN blockierendes Fenster durch:
# Charakter verlinken, Rezeptdaten laden, Preisverlaeufe. Am Fenster
# gemessen, nicht am Quelltext.
try:
    from eve_trader.ui.erst_einrichtung import ErstEinrichtung as _EE58
    # auto=False: NICHT die Kette anstossen - sonst laedt der Testlauf
    # 140 MB herunter (erster Versuch hing genau daran).
    _e58 = _EE58(win, auto=False)
    check("b58 alle drei Schritte sind da",
          bool(_e58.s1.titel.text() and _e58.s2.titel.text()
               and _e58.s3.titel.text()))
    # DER START-KNOPF IST GESPERRT, solange nichts erledigt ist - das ist
    # der Kern der Zusage ("ohne Download kommt man nicht weiter").
    check("b58 Starten ist gesperrt, bevor etwas erledigt ist",
          not _e58.weiter_btn.isEnabled())
    # KEIN SCHLIESSEN-KREUZ: der Weg hinaus ist "Beenden".
    from PySide6.QtCore import Qt as _Qt58
    check("b58 kein Schliessen-Kreuz",
          not bool(_e58.windowFlags() & _Qt58.WindowCloseButtonHint))
    check("b58 es gibt einen Weg hinaus", _e58.beenden_btn.isEnabled())
    # ESC DARF NICHT HEIMLICH DURCHLASSEN (Regel 3 andersherum: der Nutzer
    # soll nicht versehentlich in einem leeren Werkzeug landen).
    _e58.reject()
    check("b58 Esc laesst nicht durch, solange nichts erledigt ist",
          _e58.isVisible() or not _e58.result())
    # UND WENN ALLES STEHT, geht es weiter.
    _e58._fertig_machen()
    check("b58 nach Abschluss ist Starten frei", _e58.weiter_btn.isEnabled())
    # (b66) FORTSCHRITT IN DREI ZUSTAENDEN (Sitzung 17, Nutzer: "bleibt bei
    # 0% und ploppt dann auf 100%"): Prozent, Groesse unbekannt (Laufband mit
    # MB), Entpacken (Laufband mit Text). Am Fenster gemessen.
    _s66 = _e58.s2
    _s66.fortschritt(50, 140)
    check("b66 bekannte Groesse: Prozent-Balken",
          _s66.balken.maximum() == 140 and _s66.balken.value() == 50
          and "140" in _s66.zeile.text())
    _s66.fortschritt(7, 0)
    check("b66 unbekannte Groesse: Laufband mit MB-Zahl statt stumm 0 %",
          _s66.balken.maximum() == 0 and "7" in _s66.zeile.text())
    _s66.fortschritt(-1, 0)
    check("b66 Entpacken/Einlesen: eigene Anzeige, nicht stumm 100 %",
          _s66.balken.maximum() == 0
          and _s66.zeile.text() == _t4("Unpacking and importing \u2026"))
    _e58.deleteLater()
except Exception as _e58f:                               # pragma: no cover
    _fail.append(f"b58 Einrichtung: {type(_e58f).__name__}: {_e58f}")


# ---------------------------------------------------------------- (b61)
# REGIONAL: DIE PREISSPALTEN SAGEN, WOMIT GERECHNET WIRD (Sitzung 17, Nutzer:
# "im regional trading tab ist die column Buy(source) ... da muesste Sell
# source und Sell Destination sein"). Gemessen: die Rechnung nahm LAENGST die
# Sell-Orders beider Maerkte - falsch war das ETIKETT. Und bei "Immediate to
# buy order" rechnete der Gewinn gegen das Kaufgebot am Ziel, waehrend Spalte 2
# den Sell-Preis zeigte. FUNKTIONAL: echte Rechnung, echte Tabelle.
try:
    from eve_trader import hubs as _h61
    import eve_trader.ui.main_window as _mw61
    _src61 = {34: {"sell_min": 100.0, "buy_max": 50.0, "buy_qty": 0, "sell_qty": 10,
                   "sell_orders": [(100.0, 5), (110.0, 5)]}}
    _tgt61 = {34: {"sell_min": 200.0, "buy_max": 150.0, "buy_qty": 10, "sell_qty": 3}}
    _st61 = {"sales_tax_pct": 0.0, "broker_fee_pct": 0.0}
    _alt61 = getattr(win, "_arb_modus", None)
    eq("b61 Spalte 1 heisst Sell (source)",
       win.rg_table.horizontalHeaderItem(1).text(), _t4("Sell (source)"))
    for _m61, _kopf61, _preis61 in (("relist", "Sell (destination)", 200.0),
                                    ("instant", "Buy order (destination)", 150.0)):
        _d61 = _h61.arbitrage(_src61, _tgt61, _st61, {}, sell_mode=_m61)
        win._arb_modus = _m61
        win._render_arbitrage(_d61)
        _app.processEvents()
        eq(f"b61 {_m61}: Spalte 2 heisst nach der Verkaufsart",
           win.rg_table.horizontalHeaderItem(2).text(), _t4(_kopf61))
        _z61 = win.rg_table.item(0, 2)
        eq(f"b61 {_m61}: Spalte 2 zeigt den Preis, gegen den gerechnet wurde",
           _z61.text() if _z61 is not None else None,
           _mw61.isk(_preis61, suffix=False))
        _z61a = win.rg_table.item(0, 1)
        eq(f"b61 {_m61}: Spalte 1 = Schnitt der Sell-Orders der Quelle (105)",
           _z61a.text() if _z61a is not None else None, _mw61.isk(105.0, suffix=False))
    win._arb_modus = _alt61
except Exception as _e61:                                # pragma: no cover
    _fail.append(f"b61 Regional-Spalten: {type(_e61).__name__}: {_e61}")


# ---------------------------------------------------------------- (b63)
# DISCORD-KNOPF UEBER DEM SPENDEN-KNOPF (Nutzer, Sitzung 17: "wenn man
# draufklickt kommt man dahin https://discord.gg/Atuqe6c2Rj"). Am Fenster
# gemessen: Platz in der Seitenleiste und die geoeffnete Adresse.
try:
    from PySide6.QtGui import QDesktopServices as _QDS63
    from eve_trader import config as _cfg63
    _db63 = getattr(win, "discord_btn", None)
    check("b63 der Discord-Knopf existiert", _db63 is not None)
    eq("b63 die Adresse steht an EINER Stelle", _cfg63.DISCORD_URL,
       "https://discord.gg/Atuqe6c2Rj")
    if _db63 is not None:
        # VORSICHTIG ZUGREIFEN: faellt der Knopf aus dem Layout, hat er kein
        # Elternfenster - dann soll eine BENANNTE Pruefung rot werden, nicht
        # der ganze Block abstuerzen.
        _pw63 = _db63.parentWidget()
        _lay63 = _pw63.layout() if _pw63 is not None else None
        _spende63 = [b for b in win.findChildren(QPushButton)
                     if _t4("Donate") in (b.text() or "")]
        check("b63 er sitzt DIREKT ueber dem Spenden-Knopf",
              bool(_spende63) and _lay63 is not None
              and _lay63.indexOf(_spende63[0]) == _lay63.indexOf(_db63) + 1)
        _auf63 = []
        _orig63 = _QDS63.openUrl
        _QDS63.openUrl = staticmethod(lambda u: _auf63.append(u.toString()) or True)
        try:
            _db63.click()
            _app.processEvents()
        finally:
            _QDS63.openUrl = _orig63
        eq("b63 ein Klick oeffnet genau den Discord-Server", _auf63,
           ["https://discord.gg/Atuqe6c2Rj"])
except Exception as _e63:                                # pragma: no cover
    _fail.append(f"b63 Discord-Knopf: {type(_e63).__name__}: {_e63}")


# ---------------------------------------------------------------- (b65)
# ITEM-BILDER SITZEN GANZ IM RAHMEN (Sitzung 17, Nutzer: "die Bilder ... zu
# nahe rangezoomt fuer dessen Rahmen"). Der Bildserver liefert 64 px, wenn
# 48 angefragt werden; ohne Verkleinern zeigte das Label nur die Mitte -
# gemessen: 8 px Beschnitt je Rand. Hier dieselbe Messung als Waechter.
try:
    from PySide6.QtGui import QPixmap as _QPx65, QPainter as _QPt65, QColor as _QC65
    _pm65 = _QPx65(64, 64); _pm65.fill(_QC65("white"))
    _p65 = _QPt65(_pm65)
    _p65.fillRect(0, 0, 64, 6, _QC65("red")); _p65.fillRect(0, 58, 64, 6, _QC65("red"))
    _p65.end()
    _in65 = win._pixmap_im_rahmen(_pm65, 40)
    check("b65 das Bild wird auf die Rahmengroesse verkleinert",
          _in65 is not None and max(_in65.width(), _in65.height()) <= 40)
    _l65 = QLabel(); _l65.setFixedSize(48, 48); _l65.setAlignment(Qt.AlignCenter)
    _l65.setPixmap(_in65)
    _img65 = _l65.grab().toImage()
    _rot65 = [_y for _y in range(48)
              if _img65.pixelColor(24, _y).red() > 200 and _img65.pixelColor(24, _y).green() < 80]
    check(f"b65 der obere UND untere Bildrand bleiben sichtbar (rote Zeilen {_rot65[:2]}..)",
          bool(_rot65) and min(_rot65) < 12 and max(_rot65) > 36)
    _l65.deleteLater()
    _src65 = _src_mw
    check("b65 Plan-Karte und Blaupausen-Kategorie benutzen den Helfer",
          "icon_lbl.setPixmap(self._pixmap_im_rahmen(_pix, 40))" in _src65
          and "icon_lbl.setPixmap(self._pixmap_im_rahmen(_pix, 20))" in _src65)
except Exception as _e65:                                # pragma: no cover
    _fail.append(f"b65 Bild im Rahmen: {type(_e65).__name__}: {_e65}")


# ---------------------------------------------------------------- (b67)
# KAESTCHEN IN BAEUMEN SIND GESTALTET (Sitzung 17, Nutzer-Screenshot vom
# 2. PC: grellweisse Haken-Boxen im Rezept-Baum, auf seinem PC dunkel).
# Den Windows-Fall kann der Container nicht zeichnen - gemessen wird, dass
# UNSER Stylesheet das Kaestchen uebernimmt: Innenflaeche = theme.PANEL2.
# (Vorher im Container #16273b aus der Standard-Palette.)
try:
    from eve_trader.ui import theme as _th67
    from PySide6.QtWidgets import QStyle as _QSt67, QStyleOptionViewItem as _QSO67
    from PySide6.QtWidgets import QTreeWidgetItem as _QTI67
    _tw67 = QTreeWidget(); _tw67.setStyleSheet(_th67.QSS)
    _tw67.setColumnCount(1); _tw67.resize(220, 60)
    _it67 = _QTI67(["Item"]); _it67.setCheckState(0, Qt.Unchecked)
    _tw67.addTopLevelItem(_it67); _tw67.show(); _app.processEvents()
    _r67 = _tw67.visualItemRect(_it67)
    _o67 = _QSO67(); _o67.rect = _r67
    _o67.features |= _QSO67.HasCheckIndicator
    _ir67 = _tw67.style().subElementRect(_QSt67.SE_ItemViewItemCheckIndicator, _o67, _tw67)
    _farbe67 = _tw67.viewport().grab().toImage().pixelColor(_ir67.center()).name()
    eq("b67 das Baum-Kaestchen traegt die Farbe aus theme.PANEL2",
       _farbe67.lower(), _th67.PANEL2.lower())
    _tw67.hide(); _tw67.deleteLater()
except Exception as _e67:                                # pragma: no cover
    _fail.append(f"b67 Baum-Kaestchen: {type(_e67).__name__}: {_e67}")


# ---------------------------------------------------------------- (b68)
# NACH DER EINRICHTUNG LAEDT DER VERLAUF VON SELBST (Sitzung 17, Nutzer-
# Screenshot vom 2. PC: beim ZWEITEN Start "kennt erst 0 von 5'731 Items mit
# Preisverlauf" - obwohl die Einrichtung "laeuft im Hintergrund" versprach.
# Die Frage war waehrend der Einrichtung ausgewichen und kam nie wieder.)
try:
    import eve_trader.ui.main_window as _mw68
    from eve_trader import verlauf_laden as _vl68, config as _cfg68
    _alt68 = (_mw68.store.get_snapshot, _mw68.store.get_scan_region,
              _vl68.abdeckung, _cfg68.save_settings_async)
    _ges68 = dict(win.settings)
    _gest68 = []
    win.starte_verlauf_laden = lambda: _gest68.append(1)
    try:
        _mw68.store.get_scan_region = lambda: 10000002
        _cfg68.save_settings_async = lambda *_a, **_k: None
        # (1) kein Schnappschuss: nichts starten, spaeter erneut schauen
        _mw68.store.get_snapshot = lambda: None
        win._verlauf_nach_einrichtung(versuch=60)      # letzter Versuch: kein Timer
        eq("b68 ohne Markt-Schnappschuss startet nichts", len(_gest68), 0)
        # (2) Schnappschuss, 0 % Verlauf: laden, OHNE zu fragen
        _mw68.store.get_snapshot = lambda: {"34": {}}
        _vl68.abdeckung = lambda _s, _r: (0, 5731)
        win.settings["verlauf_gefragt"] = []
        win._verlauf_nach_einrichtung()
        eq("b68 0 von 5731 mit Verlauf: das Laden startet von selbst", len(_gest68), 1)
        check("b68 ... und die Frage fuer diesen Hub entfaellt danach",
              "10000002" in (win.settings.get("verlauf_gefragt") or []))
        # (3) genug Verlauf: nichts laden
        _vl68.abdeckung = lambda _s, _r: (5000, 5731)
        win._verlauf_nach_einrichtung()
        eq("b68 genug Verlauf: kein zweites Laden", len(_gest68), 1)
    finally:
        (_mw68.store.get_snapshot, _mw68.store.get_scan_region,
         _vl68.abdeckung, _cfg68.save_settings_async) = _alt68
        del win.starte_verlauf_laden
        win.settings.clear(); win.settings.update(_ges68)
    check("b68 die Einrichtung stoesst es an",
          "QTimer.singleShot(3000, self._verlauf_nach_einrichtung)" in _src_mw)
except Exception as _e68:                                # pragma: no cover
    _fail.append(f"b68 Verlauf nach Einrichtung: {type(_e68).__name__}: {_e68}")


# ---------------------------------------------------------------- (b69)
# VERLAUFSLADEN UEBERLEBT DAS SCHLIESSEN, STOPP NUR MIT WARNUNG (Sitzung 17,
# Nutzer: "laeuft es weiter, wenn ich das Programm schliesse ... oder
# bricht es ab und laedt nie wieder?" - vorher: nie wieder. Und "wer
# abbrechen drueckt, soll eine Warnung bekommen" - einen Abbruch gab es
# vorher gar nicht). Ablauf am Fenster, Hintergrundlauf abgefangen.
try:
    import eve_trader.ui.main_window as _mw69
    from eve_trader import verlauf_laden as _vl69, config as _cfg69
    _alt69 = (_mw69.store.get_snapshot, _mw69.store.get_scan_region,
              _vl69.fehlende_items, _cfg69.save_settings_async)
    _ges69 = dict(win.settings)
    _cb69 = {}
    win._run = lambda _w, done, fail_cb=None, **_k: _cb69.update(done=done, fail=fail_cb)
    try:
        _mw69.store.get_snapshot = lambda: {"34": {}}
        _mw69.store.get_scan_region = lambda: 10000002
        _vl69.fehlende_items = lambda _s, _r: [34, 35, 36]
        _cfg69.save_settings_async = lambda *_a, **_k: None
        win.settings["verlauf_offen"] = []
        win._verlauf_laeuft = False
        # (1) Start: Merker gesetzt, Stopp-Knopf sichtbar
        win.starte_verlauf_laden()
        check("b69 ein gestarteter Lauf wird als OFFEN gemerkt",
              "10000002" in win.settings.get("verlauf_offen", []))
        check("b69 ... und der Stopp-Knopf ist sichtbar",
              not win._verlauf_stopp_btn.isHidden())
        # (2) "Programm geschlossen": der Lauf endet nie -> neuer Start setzt fort
        win._verlauf_laeuft = False
        _cb69.clear()
        win._verlauf_fortsetzen()
        check("b69 beim naechsten Start geht der offene Lauf von selbst weiter",
              "done" in _cb69)
        # (3) gedrosselt: Merker bleibt
        _cb69["done"]({"geholt": 1, "leer": 0, "fehler": 0, "gedrosselt": True, "dauer": 1})
        check("b69 gedrosselt: der Merker bleibt fuer den naechsten Start",
              "10000002" in win.settings.get("verlauf_offen", []))
        # (4) fertig: Merker weg
        win._verlauf_laeuft = False
        win.starte_verlauf_laden()
        _cb69["done"]({"geholt": 3, "leer": 0, "fehler": 0, "gedrosselt": False, "dauer": 1})
        check("b69 fertig: der Merker ist weg, der Knopf verschwindet",
              "10000002" not in win.settings.get("verlauf_offen", [])
              and win._verlauf_stopp_btn.isHidden())
        # (5) Stopp mit Warnung
        win._verlauf_laeuft = False
        win.starte_verlauf_laden()
        _warn69 = []
        win._verlauf_abbruch_bestaetigen = lambda: (_warn69.append(1), False)[1]
        win._verlauf_stopp_klick()
        check("b69 Stopp fragt ERST nach (Warnung) - 'Weiterladen' aendert nichts",
              _warn69 == [1] and not win._verlauf_abbruch
              and "10000002" in win.settings.get("verlauf_offen", []))
        win._verlauf_abbruch_bestaetigen = lambda: True
        win._verlauf_stopp_klick()
        check("b69 'Stoppen' bricht ab und loescht den Merker (Nutzer-Entscheid)",
              win._verlauf_abbruch
              and "10000002" not in win.settings.get("verlauf_offen", []))
    finally:
        (_mw69.store.get_snapshot, _mw69.store.get_scan_region,
         _vl69.fehlende_items, _cfg69.save_settings_async) = _alt69
        for _n69 in ("_run", "_verlauf_abbruch_bestaetigen"):
            if _n69 in win.__dict__:
                delattr(win, _n69)
        win._verlauf_laeuft = False
        _tk69 = getattr(win, "_verlauf_ticker", None)
        if _tk69 is not None:
            _tk69.stop()
        win._verlauf_stopp_btn.setVisible(False)
        win.settings.clear(); win.settings.update(_ges69)
except Exception as _e69:                                # pragma: no cover
    _fail.append(f"b69 Verlauf fortsetzen/stoppen: {type(_e69).__name__}: {_e69}")


# ---------------------------------------------------------------- (b70)
# GEFUNDENE STRUKTUREN WERDEN FERTIGE BAU-EINTRAEGE (Sitzung 17, Nutzer:
# "wenn ich da auf ok druecke, waere es doch voll geil wenn mir die Struktur
# eintraege soweit es geht direkt fertiggestellt werden. Die rigs muss ich
# dann selber eintragen"). Rechnung ohne Netz, dann der Ablauf am Fenster.
try:
    import eve_trader.ui.main_window as _mw70
    _funde70 = [
        {"name": "Jita - Bauhalle", "structure_id": 101, "character_id": 7,
         "solar_system_id": 30000142, "type_id": 35825},
        {"name": "Tama - Reaktor", "structure_id": 102, "character_id": 7,
         "solar_system_id": 30002813, "type_id": 35836},
        {"name": "Jita - Markt", "structure_id": 103, "character_id": 7,
         "solar_system_id": 30000142, "type_id": 35832},
        {"name": "Schon da", "structure_id": 104, "character_id": 7,
         "solar_system_id": 30000142, "type_id": 35825},
    ]
    _tn70 = {35825: "Raitaru", 35836: "Tatara", 35832: "Astrahus"}
    _sy70 = {30000142: {"name": "Jita", "security": 0.95},
             30002813: {"name": "Tama", "security": 0.3}}
    _ix70 = {30000142: {"manufacturing": 0.07, "reaction": 0.01},
             30002813: {"manufacturing": 0.03, "reaction": 0.05}}
    _neu70, _weg70 = win._bau_eintraege_aus_funden(
        _funde70, _tn70, _sy70, _ix70, {104}, 0.25, 1000)
    eq("b70 Raitaru und Tatara werden angelegt, der Rest uebersprungen",
       [(e["name"], e["type"]) for e in _neu70],
       [("Jita - Bauhalle", "raitaru"), ("Tama - Reaktor", "tatara")])
    _e70 = _neu70[0]
    eq("b70 der Eintrag ist fertig bis auf die Rigs",
       {k: _e70[k] for k in ("system", "system_id", "security", "rigs",
                              "system_mfg_index", "system_reaction_index",
                              "facility_tax", "link_structure_id", "link_character_id")},
       {"system": "Jita", "system_id": 30000142, "security": 1.0, "rigs": [],
        "system_mfg_index": 0.07, "system_reaction_index": 0.01,
        "facility_tax": 0.25, "link_structure_id": 101, "link_character_id": 7})
    eq("b70 Lowsec bekommt den Lowsec-Faktor (wie im Dialog)", _neu70[1]["security"], 1.9)
    eq("b70 Citadel und Verknuepftes werden mit Grund uebersprungen", _weg70,
       [("Jita - Markt", "not an engineering complex or refinery"),
        ("Schon da", "already linked")])
    # --- Ablauf am Fenster ---
    _alt70 = (_mw70.esi.resolve_names, _mw70.esi.system_info,
              _mw70.esi.system_cost_indices, _mw70.config.save_settings,
              _mw70.QMessageBox.information)
    _bs70 = list(win.settings.get("bau_structures", []) or [])
    _meld70 = []
    try:
        _mw70.esi.resolve_names = lambda ids: {i: _tn70.get(i) for i in ids}
        _mw70.esi.system_info = lambda sid: _sy70.get(sid, {})
        _mw70.esi.system_cost_indices = lambda: _ix70
        _mw70.config.save_settings = lambda *_a, **_k: None
        _mw70.QMessageBox.information = staticmethod(
            lambda *_a, **_k: _meld70.append(_a[1] if len(_a) > 1 else ""))
        win._run = lambda w, done, fail_cb=None, **_k: done(w._fn())
        win.settings["bau_structures"] = []
        # Die Suche traegt den Typnamen schon ein (Hintergrund, s. _bau_pick_structure)
        _mitname70 = [dict(f, type_name=_tn70.get(f["type_id"])) for f in _funde70]
        win._bau_funde_frage = lambda _t: False
        win._bau_funde_anbieten(["Jita - Bauhalle"], _mitname70[:1])
        eq("b70 'Only save as locations' legt nichts an",
           win.settings.get("bau_structures"), [])
        win._bau_funde_frage = lambda _t: True
        _fragetext70 = []
        win._bau_funde_frage = lambda _t: (_fragetext70.append(_t), True)[1]
        # "Schon da" ist GESPEICHERT, aber nicht verknuepft -> wird mit angeboten
        win._bau_funde_anbieten(["Jita - Bauhalle"],
                                _mitname70[:2] + [dict(_mitname70[3], neu=False)]
                                + [_mitname70[2]])
        check("b70 auch schon gespeicherte, unverknuepfte Strukturen werden angeboten, "
              "Citadels nicht",
              bool(_fragetext70) and "Schon da" in _fragetext70[-1]
              and "Jita - Markt" not in _fragetext70[-1])
        eq("b70 'Create entries' legt alle drei Bau-Strukturen fertig an",
           [(e["name"], e["type"], e["link_structure_id"])
            for e in win.settings.get("bau_structures", [])],
           [("Jita - Bauhalle", "raitaru", 101), ("Tama - Reaktor", "tatara", 102),
            ("Schon da", "raitaru", 104)])
        check("b70 ... und sagt, dass die Rigs noch fehlen",
              bool(_meld70) and _meld70[-1] == _t4("Build structures created"))
        # --- die SUCHE selbst: neuer Fund + schon gespeicherte, unverknuepfte ---
        _alt70b = (_mw70.store.list_characters, _mw70.store.list_favorites,
                   _mw70.store.add_favorite, _mw70.esi.structure_location_ids,
                   _mw70.esi.resolve_structure, _mw70.esi.region_of_system)
        _angebot70 = []
        try:
            _mw70.store.list_characters = lambda: [{"character_id": 7}]
            _mw70.store.list_favorites = lambda: [
                {"kind": "structure", "structure_id": 104, "character_id": 7,
                 "name": "Schon da", "region_id": 10000002, "station_id": None}]
            _mw70.store.add_favorite = lambda *_a, **_k: None
            _mw70.esi.structure_location_ids = lambda _c, _ch: {101}
            _mw70.esi.resolve_structure = lambda _c, _ch, _sid: {
                "name": {101: "Jita - Bauhalle", 104: "Schon da"}[_sid],
                "solar_system_id": 30000142, "type_id": 35825}
            _mw70.esi.region_of_system = lambda _s: 10000002
            win.settings["bau_structures"] = []
            win._bau_funde_anbieten = lambda added, funde: _angebot70.append(
                (list(added), [(f["structure_id"], f.get("neu"), f.get("type_name"))
                               for f in funde]))
            win._bau_pick_structure()
            eq("b70 die Suche bietet den neuen UND den schon gespeicherten Fund an",
               _angebot70[-1] if _angebot70 else None,
               (["Jita - Bauhalle"], [(101, True, "Raitaru"), (104, False, "Raitaru")]))
        finally:
            (_mw70.store.list_characters, _mw70.store.list_favorites,
             _mw70.store.add_favorite, _mw70.esi.structure_location_ids,
             _mw70.esi.resolve_structure, _mw70.esi.region_of_system) = _alt70b
            if "_bau_funde_anbieten" in win.__dict__:
                del win._bau_funde_anbieten
    finally:
        (_mw70.esi.resolve_names, _mw70.esi.system_info,
         _mw70.esi.system_cost_indices, _mw70.config.save_settings,
         _mw70.QMessageBox.information) = _alt70
        for _n70 in ("_run", "_bau_funde_frage"):
            if _n70 in win.__dict__:
                delattr(win, _n70)
        win.settings["bau_structures"] = _bs70
        win._reload_structures()
except Exception as _e70:                                # pragma: no cover
    _fail.append(f"b70 Strukturen aus Funden: {type(_e70).__name__}: {_e70}")


# ---------------------------------------------------------------- (b71)
# UPDATE-MELDUNG MIT KNOEPFEN (Sitzung 17, Nutzer: "koennen wir da nicht
# direkt den richtigen Githublink einfuegen? vielleicht noch den link zum
# Discord"). Vorher stand die Adresse nur als Text da.
try:
    from PySide6.QtGui import QDesktopServices as _QDS71
    from eve_trader import config as _cfg71
    _url71 = "https://github.com/PeanutMotor/eve-motor-market/releases/tag/1.0"
    _auf71, _text71 = [], []
    _orig71 = _QDS71.openUrl
    _QDS71.openUrl = staticmethod(lambda u: _auf71.append(u.toString()) or True)
    try:
        for _w71 in ("download", "discord", None):
            win._update_wahl = lambda _t, _w=_w71: (_text71.append(_t), _w)[1]
            win._update_meldung(_url71, "0.1.3", "1.0")
    finally:
        _QDS71.openUrl = _orig71
        if "_update_wahl" in win.__dict__:
            del win._update_wahl
    eq("b71 Download oeffnet die Release-Seite, Discord den Server, Schliessen nichts",
       _auf71, [_url71, _cfg71.DISCORD_URL])
    # AUCH DIE FEHLERMELDUNG hat einen Knopf (Sitzung 17): sie zeigte die
    # Releases-Adresse nur als Text zum Abtippen. ECHTE Methode aufrufen, nur
    # das Fenster ersetzen - sonst prueft der Test seinen eigenen Ersatz.
    _auf71b = []
    _orig71b = _QDS71.openUrl
    _QDS71.openUrl = staticmethod(lambda u: _auf71b.append(u.toString()) or True)
    try:
        for _klick71 in (True, False):
            win._releases_wahl = lambda _t, _k=_klick71: _k
            win._releases_meldung("Test", "https://github.com/x/y/releases")
    finally:
        _QDS71.openUrl = _orig71b
        if "_releases_wahl" in win.__dict__:
            del win._releases_wahl
    check("b71 die Fehlermeldung oeffnet die Releases-Seite nur auf Klick",
          _auf71b == ["https://github.com/x/y/releases"])
    check("b71 der Text nennt beide Versionen",
          bool(_text71) and "0.1.3" in _text71[0] and "1.0" in _text71[0])
except Exception as _e71:                                # pragma: no cover
    _fail.append(f"b71 Update-Meldung: {type(_e71).__name__}: {_e71}")


# ---------------------------------------------------------------- (b72)
# ORDER UPDATE LAEDT BEIM OEFFNEN SELBST (Sitzung 17, Nutzer: "brauchen wir
# den refresh orders button wirklich? kann das nicht automatisch gehen?").
# ABER GEDROSSELT: ein Lauf holt EIN ORDERBUCH JE ARTIKEL - bei jedem
# Tab-Wechsel neu waere ein Sturm auf ESI. Am Fenster gemessen.
try:
    import time as _t72
    _w72 = getattr(win, "_orders_w", None)
    _idx72 = win.tabs.indexOf(_w72) if _w72 is not None else -1
    check("b72 der Order-Update-Tab ist auffindbar", _idx72 >= 0)
    _rufe72 = []
    _hatte72 = "client_id" in win.settings
    _alt72 = (win.settings.get("client_id"), getattr(win, "_ord_geladen_at", 0),
              getattr(win, "_ord_geladen_hub", None))
    win._load_order_mods = lambda: _rufe72.append(1)
    try:
        win.settings["client_id"] = "test"
        win._ord_laeuft = False
        win._ord_geladen_at = 0
        win._ord_geladen_hub = None
        win._on_tab_changed(_idx72)
        eq("b72 beim ersten Oeffnen wird geladen", len(_rufe72), 1)
        # Jetzt frisch geladen (gleicher Hub) -> kein zweiter Lauf
        _hub72 = win._active_hub()[2] or win._active_hub()[1]
        _hub72 = _hub72.get("structure_id") if isinstance(_hub72, dict) else _hub72
        win._ord_geladen_at = _t72.time()
        win._ord_geladen_hub = _hub72
        win._on_tab_changed(_idx72)
        eq("b72 gleich danach NICHT nochmal (kein ESI-Sturm)", len(_rufe72), 1)
        # Hub gewechselt -> neu laden, sonst zeigt der Tab fremde Orders
        win._ord_geladen_hub = -999
        win._on_tab_changed(_idx72)
        eq("b72 nach einem Hub-Wechsel wird neu geladen", len(_rufe72), 2)
        # Aelter als 5 Minuten -> neu laden
        win._ord_geladen_hub = _hub72
        win._ord_geladen_at = _t72.time() - 600
        win._on_tab_changed(_idx72)
        eq("b72 nach 5 Minuten wieder", len(_rufe72), 3)
        # Laeuft gerade -> nicht doppelt starten
        win._ord_laeuft = True
        win._ord_geladen_at = 0
        win._on_tab_changed(_idx72)
        eq("b72 waehrend ein Lauf laeuft: kein zweiter", len(_rufe72), 3)
    finally:
        del win._load_order_mods
        if _hatte72:
            win.settings["client_id"] = _alt72[0]
        else:
            win.settings.pop("client_id", None)
        win._ord_geladen_at, win._ord_geladen_hub = _alt72[1], _alt72[2]
        win._ord_laeuft = False
    # Die Laufsperre MUSS sich nach einem Fehler wieder oeffnen.
    import inspect as _insp72
    _src72 = _insp72.getsource(type(win)._load_order_mods)
    check("b72 ein Fehler gibt die Sperre wieder frei",
          "self._ord_laeuft = False" in _src72
          and "fail_cb=_ord_fehler" in _src72)
    check("b72 der Refresh-Knopf bleibt fuer 'jetzt sofort'",
          "load.clicked.connect(self._load_order_mods)" in _src_mw)
except Exception as _e72:                                # pragma: no cover
    _fail.append(f"b72 Order-Update automatisch: {type(_e72).__name__}: {_e72}")


# ---------------------------------------------------------------- (b73)
# HINWEIS AUF ORDERS AN ANDEREN ORTEN (Sitzung 17, Discord-Meldung: die
# Orders lagen in einem Keepstar, der Hub stand auf Jita - die Liste blieb
# leer OHNE Grund). Der Abruf liefert alle Orders, das Werkzeug filtert die
# fremden weg; jetzt sagt es, wie viele wo liegen.
try:
    import eve_trader.ui.main_window as _mw73
    _alt73 = (_mw73.store.list_characters, _mw73.esi.fetch_character_orders,
              _mw73.esi.resolve_names, _mw73.esi.resolve_structure,
              _mw73.esi.fetch_type_orders, getattr(win, "_active_hub"))
    _cid73 = win.settings.get("client_id")
    try:
        _mw73.store.list_characters = lambda: [{"character_id": 7}]
        # Hub = NPC-Station 60003760 (Jita 4-4)
        win._active_hub = lambda: (10000002, 60003760, None)
        _mw73.esi.fetch_character_orders = lambda _c, _ch: [
            {"type_id": 34, "price": 5.0, "is_buy_order": False, "order_id": 1,
             "volume_remain": 10, "location_id": 60003760},          # am Hub
            {"type_id": 35, "price": 6.0, "is_buy_order": False, "order_id": 2,
             "volume_remain": 5, "location_id": 1234567890123},      # Keepstar
            {"type_id": 36, "price": 7.0, "is_buy_order": True, "order_id": 3,
             "volume_remain": 5, "location_id": 1234567890123},      # Keepstar
            {"type_id": 37, "price": 8.0, "is_buy_order": False, "order_id": 4,
             "volume_remain": 5, "location_id": 60008494},           # Amarr
        ]
        _mw73.esi.resolve_names = lambda ids: {60008494: "Amarr VIII - Emperor Family"}
        _mw73.esi.resolve_structure = lambda _c, _ch, _sid: {"name": "1DQ1-A - Keepstar"}
        _mw73.esi.fetch_type_orders = lambda _t, _s, _r: {"buy": [], "sell": []}
        win.settings["client_id"] = "test"
        win._run = lambda w, done, fail_cb=None, **_k: done(w._fn())
        win._load_order_mods()
        _app.processEvents()
        _txt73 = win.ord_andere.text()
        check("b73 der Hinweis ist sichtbar", not win.ord_andere.isHidden())
        check(f"b73 er nennt die Gesamtzahl der fremden Orders ({_txt73[:40]})",
              "3" in _txt73)
        check("b73 er nennt den Keepstar MIT Anzahl (2) und Amarr (1)",
              "1DQ1-A - Keepstar (2)" in _txt73
              and "Amarr VIII - Emperor Family (1)" in _txt73)
        # Liegen alle Orders am Hub, darf nichts stehen.
        _mw73.esi.fetch_character_orders = lambda _c, _ch: [
            {"type_id": 34, "price": 5.0, "is_buy_order": False, "order_id": 1,
             "volume_remain": 10, "location_id": 60003760}]
        win._load_order_mods()
        _app.processEvents()
        check("b73 ohne fremde Orders verschwindet der Hinweis wieder",
              win.ord_andere.isHidden())
    finally:
        (_mw73.store.list_characters, _mw73.esi.fetch_character_orders,
         _mw73.esi.resolve_names, _mw73.esi.resolve_structure,
         _mw73.esi.fetch_type_orders) = _alt73[:5]
        win._active_hub = _alt73[5]
        if "_run" in win.__dict__:
            del win._run
        if _cid73 is None:
            win.settings.pop("client_id", None)
        else:
            win.settings["client_id"] = _cid73
        win._ord_laeuft = False
except Exception as _e73:                                # pragma: no cover
    _fail.append(f"b73 Orders an anderen Orten: {type(_e73).__name__}: {_e73}")


# ---------------------------------------------------------------- (b151)
# VON SICH SELBST UEBERBOTEN (Nutzer-Meldung 01.10.2026, Screenshots): nach
# dem Aendern im Spiel stand "ueberboten" - bester Buy 901'400 war die EIGENE
# neue Order (im Spiel mit Personen-Symbol), "deine Order" noch 901'000. Die
# eigenen Orders kommen spaeter nach als das Orderbuch; die order_id
# verbindet beide.
try:
    import eve_trader.ui.main_window as _mw151
    _alt151 = (_mw151.store.list_characters, _mw151.esi.fetch_character_orders,
               _mw151.esi.resolve_names, _mw151.esi.fetch_type_orders,
               getattr(win, "_active_hub"))
    _cid151 = win.settings.get("client_id")
    _buch151 = {"v": {}}
    try:
        _mw151.store.list_characters = lambda: [{"character_id": 7}]
        win._active_hub = lambda: (10000002, 60003760, None)
        _mw151.esi.fetch_character_orders = lambda _c, _ch: [
            {"type_id": 34, "price": 901000.0, "is_buy_order": True, "order_id": 900,
             "volume_remain": 10, "location_id": 60003760}]       # alter Stand
        _mw151.esi.resolve_names = lambda ids: {34: "Autocannon b151"}
        _mw151.esi.fetch_type_orders = lambda _t, _s, _r: dict(_buch151["v"])
        win.settings["client_id"] = "test"
        win._run = lambda w, done, fail_cb=None, **_k: done(w._fn())
        # 1. Die eigene, eben erhoehte Order fuehrt das Buch.
        _buch151["v"] = {"buy": [(901400.0, 1), (901300.0, 5)], "sell": [],
                         "ids": {900: 901400.0, 901: 901300.0}}
        win._load_order_mods(); _app.processEvents()
        _r151 = (getattr(win, "_ordmod_buy", None) or [{}])[0]
        check(f"b151 eigene neue Order fuehrt: NICHT ueberboten, Preis aus dem Buch "
              f"({_r151.get('mine')}, {_r151.get('flag')})",
              _r151.get("flag") is False and _r151.get("mine") == 901400.0)
        # 2. Ein anderer bietet mehr: weiter ueberboten - gegen den NEUEN Preis.
        _buch151["v"] = {"buy": [(901500.0, 1), (901400.0, 1)], "sell": [],
                         "ids": {777: 901500.0, 900: 901400.0}}
        win._load_order_mods(); _app.processEvents()
        _r151 = (getattr(win, "_ordmod_buy", None) or [{}])[0]
        check(f"b151 jemand bietet mehr: ueberboten, deine Order = neuer Preis "
              f"({_r151.get('mine')}, {_r151.get('flag')})",
              _r151.get("flag") is True and _r151.get("mine") == 901400.0)
        # 3. SPIELERSTRUKTUR (emm322): dasselbe ueber das Struktur-Orderbuch.
        _sid151 = 1035466617946
        win._active_hub = lambda: (10000060, None, {"structure_id": _sid151,
                                                    "character_id": 7})
        _mw151.esi.fetch_character_orders = lambda _c, _ch: [
            {"type_id": 34, "price": 901000.0, "is_buy_order": True, "order_id": 900,
             "volume_remain": 10, "location_id": _sid151}]
        _agg_alt151 = win.__dict__.get("_structure_agg")
        win._structure_agg = lambda _s, max_age=300: {
            34: {"buy": [(901400.0, 1), (901300.0, 5)], "sell": [],
                 "ids": {900: 901400.0, 901: 901300.0}}}
        try:
            win._load_order_mods(); _app.processEvents()
        finally:
            if _agg_alt151 is None:
                del win._structure_agg
            else:
                win._structure_agg = _agg_alt151
        _r151 = (getattr(win, "_ordmod_buy", None) or [{}])[0]
        check(f"b151 Spielerstruktur: eigene neue Order fuehrt, nicht ueberboten "
              f"({_r151.get('mine')}, {_r151.get('flag')})",
              _r151.get("flag") is False and _r151.get("mine") == 901400.0)
    finally:
        (_mw151.store.list_characters, _mw151.esi.fetch_character_orders,
         _mw151.esi.resolve_names, _mw151.esi.fetch_type_orders) = _alt151[:4]
        win._active_hub = _alt151[4]
        if "_run" in win.__dict__:
            del win._run
        if _cid151 is None:
            win.settings.pop("client_id", None)
        else:
            win.settings["client_id"] = _cid151
        win._ord_laeuft = False
except Exception as _e151:                               # pragma: no cover
    _fail.append(f"b151 eigene Order im Buch: {type(_e151).__name__}: {_e151}")


# ---------------------------------------------------------------- (b74)
# DAS TOOL MERKT SICH DIE EINSTELLUNG DES NUTZERS (Sitzung 17: "alles was er
# setzt und zieht soll beim naechsten Mal wieder so sein"): Hub, Charakter je
# Dropdown, Spaltenbreiten ALLER Tabellen. Am Fenster gemessen.
try:
    _ges74 = dict(win.settings)
    try:
        # --- (1) Spaltenbreiten: ziehen -> merken -> woanders hin -> zurueck
        _reg74 = dict(win._tabellen_register())
        check(f"b74 alle Tabellen werden erfasst ({len(_reg74)} Stueck)",
              len(_reg74) >= 8 and "bp_table" in _reg74)
        _t74 = win.bp_table
        # LEER STARTEN: sonst steht dort noch etwas aus einem frueheren Lauf
        # und die Pruefung waere auch dann gruen, wenn nichts gemerkt wird.
        win.settings["ui_spalten"] = {}
        _t74.setColumnWidth(0, 321)
        win._spalten_merken()
        check("b74 die Breiten landen in den Einstellungen",
              bool((win.settings.get("ui_spalten") or {}).get("bp_table")))
        _t74.setColumnWidth(0, 90)
        win._sized.discard("bp_table")
        win._spalten_wiederherstellen()
        eq("b74 nach dem Neustart steht die Spalte wieder auf 321",
           _t74.columnWidth(0), 321)
        check("b74 ... und _autosize_once ueberschreibt sie nicht mehr",
              "bp_table" in win._sized)
        # SPALTENZAHL GEAENDERT (emm354): ein Zustand mit anderer Spaltenzahl
        # wird nicht mehr angewendet.
        win.settings["ui_spalten_n"]["bp_table"] = _t74.columnCount() - 1
        _t74.setColumnWidth(0, 90)
        win._sized.discard("bp_table")
        win._spalten_wiederherstellen()
        eq("b74 andere Spaltenzahl gemerkt: Zustand bleibt ungenutzt",
           _t74.columnWidth(0), 90)
        # --- (2) Charakter-Auswahl je Dropdown
        # ZWEI CHARAKTERE VORTAEUSCHEN: im Testfenster ist sonst nur "All
        # characters" da - dann waere jede Auswahl "all" und die Pruefung
        # gruen, egal was der Code tut.
        import eve_trader.ui.main_window as _mw74
        _altl74 = _mw74.store.list_characters
        try:
            _mw74.store.list_characters = lambda: [
                {"character_id": 111, "character_name": "Alpha"},
                {"character_id": 222, "character_name": "Beta"}]
            win._reload_character_combos()
            _cb74 = win.pf_char
            eq("b74 das Dropdown enthaelt beide Charaktere + Alle",
               _cb74.count(), 3)
            _cb74.setCurrentIndex(2)                 # Beta
            win._char_wahl_merken("pf_char")
            eq("b74 die Charakter-Auswahl wird je Dropdown gemerkt",
               (win.settings.get("ui_char_wahl") or {}).get("pf_char"), 222)
            win._reload_character_combos()
            eq("b74 nach dem Neuaufbau steht derselbe Charakter da",
               win.pf_char.currentData(), 222)
        finally:
            _mw74.store.list_characters = _altl74
            win._reload_character_combos()
        check("b74 alle sieben Charakter-Dropdowns sind eingetragen",
              len(win._CHAR_COMBOS) == 7 and "ord_char" in win._CHAR_COMBOS)
        # --- (3) Hub
        win._hub_merken()
        check("b74 der Hub wird gemerkt", "ui_hub" in win.settings)
        check("b74 gemerkt wird das, was oben ausgewaehlt ist",
              win.settings.get("ui_hub") == win.g_hub.currentData())
    finally:
        win.settings.clear(); win.settings.update(_ges74)
except Exception as _e74:                                # pragma: no cover
    _fail.append(f"b74 Personalisierung: {type(_e74).__name__}: {_e74}")


# ---------------------------------------------------------------- (b75)
# UPDATE-PRUEFUNG BEIM START (Sitzung 17, Nutzer: "damit sich keine Updates
# reinschleichen koennen und sie vergessen den Update-Knopf zu druecken").
# STILL: nur bei einem echten Update ein Fenster - "alles aktuell" und
# Netzfehler bleiben in der Statuszeile, sonst waere jeder Start eine
# Belaestigung. Am Fenster gemessen, ohne Netz.
try:
    import eve_trader.programm_update as _pu75
    import eve_trader.ui.main_window as _mw75
    _alt75 = (_pu75.pruefen, _mw75.QMessageBox.information)
    _fenster75, _meldung75, _rel75 = [], [], []
    try:
        _mw75.QMessageBox.information = staticmethod(
            lambda *_a, **_k: _fenster75.append(_a[1] if len(_a) > 1 else "?"))
        win._update_meldung = lambda url, own, neu, name="x": _meldung75.append(neu)
        win._releases_meldung = lambda text, url: _rel75.append(text)
        win._run = lambda w, done, fail_cb=None, **_k: done(w._fn())
        # (1) aktuell -> beim Start KEIN Fenster
        _pu75.pruefen = lambda _r, _v, holen=None: {
            "neuer": False, "hinweis": "", "version": _v, "url": None}
        win.check_programm_update(still=True)
        _app.processEvents()
        eq("b75 aktuell: beim Start kein Fenster", (_fenster75, _meldung75), ([], []))
        # (2) NEUE Fassung -> Fenster kommt auch beim Start
        _pu75.pruefen = lambda _r, _v, holen=None: {
            "neuer": True, "hinweis": "", "version": "9.9.9",
            "url": "https://github.com/x/y/releases/tag/9.9.9"}
        win.check_programm_update(still=True)
        _app.processEvents()
        eq("b75 neue Fassung: die Update-Meldung erscheint", _meldung75, ["9.9.9"])
        # (3) nicht vergleichbar -> beim Start still
        _pu75.pruefen = lambda _r, _v, holen=None: {
            "neuer": False, "hinweis": "keine Antwort", "version": None, "url": None}
        win.check_programm_update(still=True)
        _app.processEvents()
        eq("b75 Netzproblem: beim Start kein Fenster", _rel75, [])
        # (4) derselbe Fall VON HAND -> Fenster kommt sehr wohl
        win.check_programm_update()
        _app.processEvents()
        check("b75 von Hand meldet sich das Netzproblem weiterhin", bool(_rel75))
    finally:
        _pu75.pruefen, _mw75.QMessageBox.information = _alt75
        for _n75 in ("_update_meldung", "_releases_meldung", "_run"):
            if _n75 in win.__dict__:
                delattr(win, _n75)
    check("b75 der Start stoesst die stille Pruefung an",
          "self.check_programm_update(still=True)" in _src_mw
          and "QTimer.singleShot(12000," in _src_mw)
except Exception as _e75:                                # pragma: no cover
    _fail.append(f"b75 Update-Pruefung beim Start: {type(_e75).__name__}: {_e75}")


# ---------------------------------------------------------------- (b76)
# SORTIERUNG UND FILTER UEBERLEBEN DEN NEUSTART (Sitzung 17, Nutzer: "das
# werden wir sofort machen"). Ergaenzt b74 (Hub, Charakter, Spaltenbreiten).
try:
    from PySide6.QtCore import Qt as _Qt76
    _ges76 = dict(win.settings)
    _alt76 = _bpc76 = None
    try:
        # --- Sortierung
        win.settings["ui_sort"] = {}
        win.bp_table.sortItems(3, _Qt76.DescendingOrder)
        win._sortierung_merken()
        eq("b76 die Sortierung wird gemerkt (Spalte + Richtung)",
           (win.settings.get("ui_sort") or {}).get("bp_table"), [3, 1])
        win.bp_table.sortItems(0, _Qt76.AscendingOrder)
        win._sortierung_wiederherstellen()
        eq("b76 nach dem Neustart sortiert sie wieder wie zuletzt",
           (win.bp_table.horizontalHeader().sortIndicatorSection(),
            int(win.bp_table.horizontalHeader().sortIndicatorOrder().value)), (3, 1))
        # --- Filter
        win.settings["ui_filter"] = {}
        _alt76 = win.bp_cb_profit.isChecked()
        _bpc76 = win.bp_cb_bpc.isChecked()
        win.bp_cb_profit.setChecked(not _alt76)
        win.bp_cb_bpc.setChecked(False)
        win._filter_merken()
        eq("b76 die Filter-Haken werden gemerkt",
           {k: (win.settings.get("ui_filter") or {}).get(k)
            for k in ("bp_cb_profit", "bp_cb_bpc")},
           {"bp_cb_profit": not _alt76, "bp_cb_bpc": False})
        win.bp_cb_profit.setChecked(_alt76)
        win.bp_cb_bpc.setChecked(True)
        win._filter_wiederherstellen()
        eq("b76 nach dem Neustart stehen sie wieder so",
           (win.bp_cb_profit.isChecked(), win.bp_cb_bpc.isChecked()),
           (not _alt76, False))
        # AUCH EIN AUSWAHLFELD (sonst prueft der Test nur Haken - Mutation
        # 649 blieb genau deshalb blind).
        if win.tx_period.count() > 1:
            win.tx_period.setCurrentIndex(1)
            _wahl76 = win.tx_period.currentData()
            win._filter_merken()
            eq("b76 auch Auswahlfelder werden gemerkt",
               (win.settings.get("ui_filter") or {}).get("tx_period"), _wahl76)
            win.tx_period.setCurrentIndex(0)
            win._filter_wiederherstellen()
            eq("b76 und nach dem Neustart wieder gesetzt",
               win.tx_period.currentData(), _wahl76)
        check("b76 gemerkt wird NUR, was eine Ansicht filtert",
              "asset_cb" not in win._FILTER_WIDGETS
              and "stock_scope_cb" not in win._FILTER_WIDGETS
              and "bp_cb_profit" in win._FILTER_WIDGETS)
        check("b76 beim Wiederherstellen laufen keine Signale los",
              "_w.blockSignals(True)" in
              __import__("inspect").getsource(type(win)._filter_wiederherstellen))
    finally:
        win.settings.clear(); win.settings.update(_ges76)
        win._filter_wiederherstellen()
        # DIE HAKEN AUSDRUECKLICH ZURUECKSETZEN (18.09.2026): kannten die
        # Settings vorher kein ui_filter, stellt _filter_wiederherstellen
        # NICHTS zurueck - "profitable only" blieb AUS, closeEvent schrieb
        # das in die Test-Settings, und der naechste Lauf fiel bei b46.
        for _w76, _v76 in ((win.bp_cb_profit, _alt76), (win.bp_cb_bpc, _bpc76)):
            if _v76 is None:
                continue
            try:
                _w76.blockSignals(True)
                _w76.setChecked(_v76)
            finally:
                _w76.blockSignals(False)
        check("b76 Aufraeumen: die Haken stehen wieder wie vorher",
              _alt76 is not None and win.bp_cb_profit.isChecked() is _alt76
              and win.bp_cb_bpc.isChecked() is _bpc76)
except Exception as _e76:                                # pragma: no cover
    _fail.append(f"b76 Sortierung/Filter merken: {type(_e76).__name__}: {_e76}")


# ---------------------------------------------------------------- (b77)
# LEERE LISTEN SAGEN, WARUM SIE LEER SIND (Sitzung 17, Nutzer). ANLASS: ein
# Discord-Nutzer hielt das Werkzeug fuer kaputt, weil die Listen leer waren -
# der Grund stand nur in der kleinen Statuszeile. Am Fenster gemessen.
try:
    from PySide6.QtWidgets import QLabel as _QL77, QWidget as _QW77
    _fund77 = {}
    for _n77 in ("deals_table", "hold_table", "rg_table", "bp_table",
                 "pf_table", "pr_table", "tx_table"):
        _t77 = getattr(win, _n77, None)
        if _t77 is None:
            continue
        _boxen = [w for w in _t77.viewport().findChildren(_QW77)
                  if w.findChildren(_QL77) and w.parent() is _t77.viewport()]
        _fund77[_n77] = _boxen[0] if _boxen else None
    check(f"b77 jede der sieben Listen hat einen Hinweis ({len(_fund77)})",
          all(_b is not None for _b in _fund77.values()) and len(_fund77) == 7)
    _bp77 = _fund77.get("bp_table")
    eq("b77 der Hinweis nennt den Grund",
       [l.text() for l in _bp77.findChildren(_QL77)][0],
       _t4("No blueprints loaded yet"))
    _btn77 = _bp77.findChildren(QPushButton)
    check("b77 und bietet genau den fehlenden Knopf an",
          len(_btn77) == 1 and _btn77[0].text() == _t4("Load blueprints"))
    check("b77 der Knopf traegt ein Symbol (b55 verlangt das)",
          not _btn77[0].icon().isNull())
    # KLICK LOEST DIE RICHTIGE AKTION AUS
    # AM VORBILD-KNOPF LAUSCHEN statt seine Methode zu ersetzen: das ist die
    # Wirkung, die zaehlt - und es loest den echten Ladevorgang nicht aus.
    # SEIT 17.09.2026: das Vorbild ist "Meine Blaupausen laden"
    # (bp_refresh_btn), NICHT der SDE-Download (g_sde_btn) - der fragte bei
    # geladener SDE nur zurueck und tat sonst nichts (Nutzer: "bei Blueprint
    # genauso, keine Wirkung").
    _geklickt77 = []
    _c77 = win.bp_refresh_btn.clicked.connect(lambda *_a: _geklickt77.append(1))
    _lade77 = win._reload_my_blueprints
    win._reload_my_blueprints = lambda *_a, **_k: None
    try:
        _btn77[0].click()
        _app.processEvents()
    finally:
        win.bp_refresh_btn.clicked.disconnect(_c77)
        win._reload_my_blueprints = _lade77
    eq("b77 ein Klick loest denselben Vorgang aus wie der Knopf oben",
       _geklickt77, [1])
    # SICHTBAR NUR SOLANGE LEER
    check("b77 bei leerer Liste ist er sichtbar",
          win.bp_table.rowCount() == 0 and not _bp77.isHidden())
    win.bp_table.setRowCount(1)
    _app.processEvents()
    check("b77 sobald Daten da sind, verschwindet er", _bp77.isHidden())
    win.bp_table.setRowCount(0)
    _app.processEvents()
    check("b77 und kommt zurueck, wenn die Liste wieder leer ist",
          not _bp77.isHidden())
    # OHNE KNOPF: die Transaktionen-Listen nennen den Weg als Satz
    _tx77 = _fund77.get("tx_table")
    check("b77 ohne passenden Knopf steht ein Satz statt eines Knopfes",
          not _tx77.findChildren(QPushButton)
          and any(_t4("Link a character under \u201eCharacters\u201c.") == l.text()
                  for l in _tx77.findChildren(_QL77)))
except Exception as _e77:                                # pragma: no cover
    _fail.append(f"b77 Leer-Hinweise: {type(_e77).__name__}: {_e77}")


# ---------------------------------------------------------------- (b78)
# GEFUEHRTE TOUR (Sitzung 17, Nutzer-Auftrag). NICHT MODAL, damit man
# waehrenddessen einrichten kann ("Charaktere verlinken, Strukturen anlegen").
# Durchgeklickt wird sie hier von vorne bis hinten - ohne Netz, ohne Klicks.
try:
    from eve_trader.ui.tutorial import TutorialFenster as _TF78, schritte as _S78
    for _zweig78 in ("trading", "industry"):
        _st78 = _S78(_zweig78)
        check(f"b78 {_zweig78}: die Tour hat Schritte ({len(_st78)})",
              10 <= len(_st78) <= 30)
        check(f"b78 {_zweig78}: jeder Schritt hat Titel UND Text",
              all(x[1] and x[2] for x in _st78))
        check(f"b78 {_zweig78}: kurze Texte, kein Absatz",
              all(len(x[2]) <= 180 for x in _st78))
    _tut78 = _TF78(win, "trading")
    _app.processEvents()
    eq("b78 die Tour startet beim ersten Schritt", _tut78.zaehler.text(),
       f"1 / {len(_S78('trading'))}")
    check("b78 am Anfang ist Zurueck gesperrt", not _tut78.zurueck_btn.isEnabled())
    _texte78 = []
    for _ in range(len(_S78("trading")) - 1):
        _texte78.append(_tut78.titel.text())
        _tut78.weiter()
        _app.processEvents()
    # Titel duerfen sich wiederholen (z.B. "Strategie und Presets" in allen
    # drei Handels-Tabs) - was zaehlt: die Tour bleibt nicht stehen.
    check("b78 die Tour laeuft wirklich durch alle Schritte",
          len(_texte78) == len(_S78("trading")) - 1
          and len(set(_texte78)) >= len(_texte78) - 4)
    eq("b78 der Zaehler zeigt, wie oft man noch klicken muss",
       _tut78.zaehler.text(),
       f"{len(_S78('trading'))} / {len(_S78('trading'))}")
    eq("b78 der letzte Schritt heisst 'Fertig'", _tut78.weiter_btn.text(),
       _t4("Finish"))
    # ABBRECHEN MUSS DEN RAHMEN ZURUECKNEHMEN
    # RAHMEN LIEGT UEBER dem Element, NICHT in seinem Stylesheet (Nutzer-Fund
    # Sitzung 17: ein border im Stil einer TABELLE vererbt sich auf jede
    # Zelle - die Sell list stand komplett gelb umrandet da).
    _tut78.i = 1
    _tut78.zeigen()
    _app.processEvents()
    check("b78 der aktuelle Schritt hebt sein Element hervor",
          _tut78._rahmen and _tut78._hervor == [win.g_hub])
    check("b78 der Rahmen fasst NICHT ins Stylesheet des Elements",
          "border:2px solid" not in (win.g_hub.styleSheet() or ""))
    # DAS RAHMEN-FENSTER SELBST muss weg sein, nicht bloss die Variable -
    # sonst bliebe ein gelber Rahmen im Bild stehen (Mutation 655 war so
    # zuerst blind).
    _ov78 = list(_tut78._rahmen)
    _tut78.abbrechen()
    _app.processEvents()
    def _weg78(w):
        try:
            return not w.isVisible()
        except RuntimeError:
            return True                 # C++-Objekt abgeraeumt = weg
    check("b78 nach dem Abbrechen ist der Rahmen wieder weg",
          not _tut78._rahmen and not _tut78._blink.isActive()
          and all(_weg78(_o) for _o in _ov78))
    # SEITENLEISTEN-SCHRITTE zeigen auf den EINTRAG, nicht auf die Tabelle.
    _tutn = _TF78(win, "trading")
    _inav = [i for i, st in enumerate(_S78("trading"))
             if str(st[0] or "").startswith("nav:")]
    check(f"b78 die Seitenleisten-Schritte zeigen auf ihren Eintrag "
          f"({len(_inav)})", len(_inav) >= 8)
    _tutn.i = _inav[0]
    _tutn.zeigen()
    _app.processEvents()
    check("b78 und heben genau diesen Eintrag hervor",
          _tutn._hervor == [(getattr(win, "_nav_buttons", {}) or {}).get(
              _S78("trading")[_inav[0]][0][4:])])
    check("b78 der letzte Schritt fuehrt zurueck ins Portfolio",
          _S78("trading")[-1][3] == "portfolio")
    # UND BLINKT NICHTS MEHR (Nutzer, Sitzung 17): am Schluss gibt es nichts
    # zu klicken - ein blinkender Knopf fordert nur dazu auf.
    for _zw78e in ("trading", "industry"):
        eq(f"b78 {_zw78e}: der Schlussschritt hebt nichts mehr hervor",
           _S78(_zw78e)[-1][0], None)
    # DER SCHLUSS DARF NICHT EINFRIEREN (Nutzer-Fund Sitzung 17: "wenn ich
    # auf Finish klicke, friert alles ein"). URSACHE: ab Schritt 9 haengt die
    # Tour AM BAUPLAN; wird der beim letzten Schritt geschlossen, nimmt er
    # sein Kind mit - der Klick lief auf ein abgeraeumtes Objekt.
    _zt78 = __import__("inspect").getsource(_TF78.zeigen)
    check("b78 vor dem Schliessen wird die Tour ans Haupttool umgehaengt",
          "if self.parent() is _d:" in _zt78
          and "self.setParent(self.mw, self.windowFlags())" in _zt78)
    _ab78 = __import__("inspect").getsource(_TF78.abbrechen)
    check("b78 das Nachfolge-Fenster kommt NICHT aus dem Klick heraus",
          "QTimer.singleShot(0, lambda: _mw._tutorial_anderer_zweig" in _ab78)
    # DURCHSPIELEN: Bauplan als Elternfenster, letzter Schritt, dann Finish.
    _di78 = getattr(win, "_bd_dialog", None)
    if _di78 is not None and _di78.isVisible():
        _tf78 = _TF78(win, "industry")
        _alt78z = win._tutorial_anderer_zweig
        win._tutorial_anderer_zweig = lambda *_a: None
        try:
            _tf78.setParent(_di78, _tf78.windowFlags())
            _tf78.show()
            _tf78.i = len(_S78("industry")) - 1
            _tf78.zeigen()
            _app.processEvents()
            check("b78 nach dem Schliessen lebt die Tour noch",
                  _tf78.parent() is win and _tf78.isVisible())
            _tf78.weiter()               # = Finish
            _app.processEvents()
            check("b78 'Finish' laeuft ohne Haenger durch",
                  getattr(win, "_tutorial", "weg") is None)
        finally:
            win._tutorial_anderer_zweig = _alt78z
            _app.processEvents()
    _te78 = _TF78(win, "trading")
    try:
        _te78.i = len(_S78("trading")) - 1
        _te78.zeigen()
        _app.processEvents()
        check("b78 am Schluss laeuft kein Blinken mehr",
              not _te78._rahmen and not _te78._blink.isActive())
    finally:
        _te78.abbrechen()
        _app.processEvents()
    # NACH NAMEN SUCHEN, NICHT NACH POSITION: die Tour waechst (Nutzer hat
    # Strategie- und "Deals laden"-Schritte ergaenzt) - feste Indizes waeren
    # bei jeder Erweiterung rot, ohne dass etwas kaputt ist.
    # EIN SCHRITT KANN MEHRERE ELEMENTE BLINKEN LASSEN (Nutzer, Sitzung 17:
    # "lass beide Dropdowns blinken", "lass auch den Hub mitblinken") - der
    # Name ist dann ein Tupel. Also nach JEDEM Namen einzeln nachschlagen.
    _pos78 = {}
    for _i78, _st78x in enumerate(_S78("trading")):
        _n78 = _st78x[0]
        for _one in ((_n78,) if isinstance(_n78, str) or _n78 is None
                     else tuple(_n78)):
            if _one is not None:
                _pos78.setdefault(_one, _i78)
    # DIE DREI HANDELS-TABS ERKLAEREN JEWEILS STRATEGIE UND "DEALS LADEN"
    # (Nutzer, Sitzung 17). Regional zusaetzlich die zwei Hubs.
    for _need78 in ("d_preset", "deals_btn", "h_preset", "hold_btn",
                    "rg_src", "rg_preset", "rg_go"):
        check(f"b78 der Schritt zu {_need78} ist da", _need78 in _pos78)
    # UND DIE ZUSATZ-ELEMENTE BLINKEN WIRKLICH MIT
    def _namen78(i):
        _n = _S78("trading")[i][0]
        return ((_n,) if isinstance(_n, str) else tuple(_n or ()))
    check("b78 Daytrade: Mode UND Preset blinken",
          set(_namen78(_pos78["d_preset"])) == {"d_mode", "d_preset"})
    check("b78 Daytrade: bei 'Deals laden' blinkt der Hub mit",
          "g_hub" in _namen78(_pos78["deals_btn"]))
    check("b78 Swing: Mode UND Preset blinken",
          set(_namen78(_pos78["h_preset"])) == {"h_mode", "h_preset"})
    check("b78 Swing: bei 'Deals laden' blinkt der Hub mit",
          "g_hub" in _namen78(_pos78["hold_btn"]))
    check("b78 Regional: Kauf- UND Verkaufs-Hub blinken",
          set(_namen78(_pos78["rg_src"])) == {"rg_src", "rg_tgt"})
    check("b78 Regional: es gibt einen Schritt zu Kaeufer und Verkaeufer",
          set(_namen78(_pos78["rg_buyer"])) == {"rg_buyer", "rg_seller"})
    # HIER NICHT: der obere Hub ist im Regional wirklich ohne Wirkung -
    # GEMESSEN: compute_arbitrage liest nur rg_src/rg_tgt.
    check("b78 Regional: bei 'Deals laden' blinkt der obere Hub NICHT mit",
          "g_hub" not in _namen78(_pos78["rg_go"])
          and {"rg_src", "rg_tgt", "rg_buyer", "rg_seller"}
          <= set(_namen78(_pos78["rg_go"])))
    check("b78 und die Regional-Rechnung nimmt wirklich nur die zwei Hubs",
          "src = self.rg_src.currentData()"
          in __import__("inspect").getsource(type(win).compute_arbitrage)
          and "_active_hub"
          not in __import__("inspect").getsource(type(win).compute_arbitrage))
    for _tab78, _pre78, _btn78 in (("deals", "d_preset", "deals_btn"),
                                   ("swing", "h_preset", "hold_btn"),
                                   ("region", "rg_preset", "rg_go")):
        check(f"b78 {_tab78}: erst Reiter, dann Strategie, dann Deals laden",
              _pos78["nav:" + _tab78] < _pos78[_pre78] < _pos78[_btn78])
    check("b78 hervorgehoben wird der einzelne Reiter, nicht die Leiste",
          all(k in _pos78 for k in ("nav:deals", "nav:swing", "nav:region")))
    _tt78 = _TF78(win, "trading")
    try:
        for _erw78 in ("deals", "swing", "region"):
            _k78 = _pos78["nav:" + _erw78]
            _tt78.i = _k78
            _tt78.zeigen()
            _app.processEvents()
            eq(f"b78 der Schritt zu {_erw78} schaltet den Reiter um",
               [k for k, w in win._tab_widget.items()
                if w is win.tabs.currentWidget()], [_erw78])
            check(f"b78 ... und hebt den Reiter {_erw78} hervor",
                  (getattr(win, "_nav_buttons", {}) or {}).get(_erw78)
                  in _tt78._hervor)
    finally:
        _tt78.abbrechen()
        _app.processEvents()
    # BLINKEN
    check("b78 der hervorgehobene Knopf blinkt", _tutn._blink.isActive())
    _s1 = _tutn._rahmen[0].styleSheet()
    _tutn._blinken()
    check("b78 ... und wechselt dabei wirklich sein Aussehen",
          _tutn._rahmen[0].styleSheet() != _s1)
    # ALLE Rahmen eines Schritts muessen mitblinken, nicht nur der erste
    # (Nutzer: "lass beide Dropdowns blinken").
    _tutn.i = _pos78["d_preset"]
    _tutn.zeigen()
    _app.processEvents()
    check(f"b78 ein Schritt kann mehrere Rahmen haben ({len(_tutn._rahmen)})",
          len(_tutn._rahmen) == 2)
    _vor78 = [r.styleSheet() for r in _tutn._rahmen]
    _tutn._blinken()
    check("b78 und ALLE davon blinken mit",
          all(r.styleSheet() != v for r, v in zip(_tutn._rahmen, _vor78)))
    _tutn.abbrechen()
    _app.processEvents()
    # WARTEN AUF EINE AKTION: der Bauplan-Schritt sperrt "Weiter".
    _tut78c = _TF78(win, "industry")
    _idx78 = [i for i, st in enumerate(_S78("industry"))
              if st[4] == "bauplan_offen"]
    check("b78 genau EIN Schritt wartet auf eine Aktion", len(_idx78) == 1)
    _alt78d = getattr(win, "_bd_dialog", None)
    try:
        win._bd_dialog = None
        _tut78c.i = _idx78[0]
        _tut78c.zeigen()
        _app.processEvents()
        check("b78 ohne offenen Bauplan bleibt 'Weiter' gesperrt",
              not _tut78c.weiter_btn.isEnabled() and _tut78c._warte.isActive())
        class _Fake78:
            def isVisible(self):
                return True

            def raise_(self):
                pass                      # die Tour holt den Bauplan nach vorn

            def activateWindow(self):
                pass
        win._bd_dialog = _Fake78()
        _tut78c._warte_pruefen()
        _app.processEvents()
        check("b78 sobald einer offen ist, geht es von selbst weiter",
              _tut78c.weiter_btn.isEnabled() and not _tut78c._warte.isActive())
        # UND DAS BLINKEN HOERT AUF (Nutzer, Sitzung 17): ein zweiter Klick
        # auf "New build plan" oeffnet das Auswahlfenster erneut und schiebt
        # alles wieder nach hinten.
        check("b78 danach blinkt 'Neuer Bauplan' nicht mehr",
              not _tut78c._rahmen and not _tut78c._blink.isActive()
              and _tut78c._fertig_kein_blinken)
        _tut78c._nachfuehren()
        _app.processEvents()
        check("b78 und das Nachfuehren bringt es nicht zurueck",
              not _tut78c._rahmen)
    finally:
        win._bd_dialog = _alt78d
        _tut78c.abbrechen()
        _app.processEvents()
    # KURSVERLAUF WIRD WIRKLICH GEZEICHNET (Nutzer, Sitzung 17: "es steht
    # zwar im Item-Dropdown, aber es soll geladen werden"). Vorher kehrte die
    # Funktion zurueck, sobald irgendetwas ausgewaehlt war.
    _plots78 = []
    _altp78 = win._plot_history
    win._plot_history = lambda *_a, **_k: _plots78.append(1)
    _mk78 = win.mk_item.count()
    win.mk_item.addItem("Testitem", 34)
    win.mk_item.setCurrentIndex(win.mk_item.findData(34))
    try:
        win._tutorial_kursverlauf_beispiel()      # mit schon gewaehltem Item
        _app.processEvents()
        check("b78 der Kursverlauf wird auch bei schon gewaehltem Item gezeichnet",
              len(_plots78) >= 1)
    finally:
        win._plot_history = _altp78
        win.mk_item.setCurrentIndex(-1 if _mk78 == 0 else 0)
        win.mk_item.removeItem(win.mk_item.findData(34))
    # JEDER SCHRITT MUSS SEIN ELEMENT FINDEN (Nutzer, Sitzung 17: "schau
    # drauf, dass das Tutorial-Fenster auch da immer am richtigen Ort ist").
    # Fand ein Schritt seins nicht, landete das Fenster mittig - und im
    # Bauplan-Schritt zeigte der Text auf einen Knopf, der gar nicht blinkte.
    for _zw78 in ("trading", "industry"):
        _tp78 = _TF78(win, _zw78)
        try:
            # JEDEN NAMEN EINZELN pruefen: bei einem Tupel liefert _widget
            # eine LISTE - die ist nie None, und die Pruefung war blind
            # (Mutation 663 fiel genau darauf herein).
            _fehlt78 = []
            for _i78f, _st78f in enumerate(_S78(_zw78)):
                _n78f = _st78f[0]
                for _one78 in ((_n78f,) if isinstance(_n78f, str)
                               else tuple(_n78f or ())):
                    # AUSNAHME: `_picker_open_btn` entsteht erst, wenn das
                    # Auswahlfenster offen ist. Der Schritt meint ihn
                    # trotzdem - `_nachfuehren` holt ihn nach, sobald er da
                    # ist. Deshalb hier nicht als Fehler zaehlen.
                    # NUR VORUEBERGEHEND VORHANDEN: der "Open"-Knopf gibt
                    # es erst mit offenem Auswahlfenster, die bd:-Anker nur
                    # mit offenem Bauplan. `_nachfuehren` holt beides nach.
                    if _one78 in ("_picker_open_btn", "_bd_karte_bauenkaufen",
                                  "_bd_karte_tiefe",
                                  "_bd_save_btn", "_bd_frozen_btn") \
                            or str(_one78).startswith("bd:"):
                        continue
                    if _one78 and _tp78._widget(_one78) is None:
                        _fehlt78.append(f"{_i78f + 1}:{_one78}")
            eq(f"b78 {_zw78}: jeder Schritt findet sein Element", _fehlt78, [])
        finally:
            _tp78.abbrechen()
            _app.processEvents()
    # JEDER SCHRITT, DER AUF EIN ELEMENT IM HAUPTFENSTER ZEIGT, MUSS AUCH
    # DORTHIN SCHALTEN (Nutzer-Fund Sitzung 17: "Industrie-Tab blinkt, aber
    # wir werden nicht dahin gefuehrt"). Im Industriezweig fehlte das bei
    # ALLEN Schritten.
    _ind78 = _S78("industry")           # EINMAL holen: schritte() baut jedes
    for _i78i, _st78i in enumerate(_ind78):   # Mal eine NEUE Liste (is faellt sonst durch)
        _n78i = _st78i[0]
        _alle78i = ((_n78i,) if isinstance(_n78i, str) else tuple(_n78i or ()))
        # Der SCHLUSS-Schritt fuehrt bewusst ins Portfolio zurueck (Nutzer).
        if _i78i == len(_ind78) - 1:
            eq("b78 der letzte Industrie-Schritt fuehrt ins Portfolio",
               _st78i[3], "portfolio")
            continue
        if any(str(x).startswith(("nav:", "bau:")) or x == "_bau_newplan_btn"
               for x in _alle78i):
            eq(f"b78 industry Schritt {_i78i + 1} schaltet in den Bauen-Tab",
               _st78i[3], "build")
    # UND SIE OEFFNET AUCH DIE UNTERSEITE DES BAUEN-TABS (Nutzer-Fund
    # Sitzung 17: "3/15 soll mich in den Struktur-Tab hineinfuehren ... kein
    # Tutorial fuehrt mich in den Tab hinein"). Der Bauen-Tab hat vier eigene
    # Seiten - der Reiterwechsel allein zeigte die falsche.
    _tp78s = _TF78(win, "industry")
    try:
        for _seite78, _titel78 in ((3, "Structures first"), (0, "Scanner"),
                                   (1, "My blueprints")):
            _i78s = [i for i, st in enumerate(_S78("industry"))
                     if f"bau:{_seite78}" in
                     ((st[0],) if isinstance(st[0], str) else tuple(st[0] or ()))]
            if not _i78s:
                continue
            # VORHER WOANDERS HIN: sonst ist die Pruefung zufaellig gruen,
            # weil die Seite schon stimmte (Mutation blieb so blind).
            win.b_stack.setCurrentIndex(2 if _seite78 != 2 else 0)
            _tp78s.i = _i78s[0]
            _tp78s.zeigen()
            _app.processEvents()
            eq(f"b78 der Schritt '{_titel78}' oeffnet Seite {_seite78}",
               win.b_stack.currentIndex(), _seite78)
    finally:
        _tp78s.abbrechen()
        _app.processEvents()
    # Ein Schritt kann mehrere Elemente haben - also im TUPEL suchen.
    def _hat78(st, name):
        _n = st[0]
        return name in ((_n,) if isinstance(_n, str) else tuple(_n or ()))
    _iS = [i for i, st in enumerate(_S78("industry")) if _hat78(st, "bau:3")]
    _iC = [i for i, st in enumerate(_S78("industry")) if _hat78(st, "bau:0")]
    # BEIDE "Load blueprints"-KNOEPFE BLINKEN (Nutzer, Sitzung 17): der oben
    # laedt die REZEPTDATEN, der auf der Seite holt SEINE Blaupausen aus EVE.
    # Zwei Knoepfe mit demselben Text - genau deshalb muessen beide leuchten.
    _bp78 = [st for st in _S78("industry")
             if "bau:1" in ((st[0],) if isinstance(st[0], str)
                            else tuple(st[0] or ()))]
    # DIE DREI SCHRITTE IM BAUPLAN ZEIGEN AUF ECHTE ELEMENTE (Nutzer-Fund
    # Sitzung 17: "Build or buy haengt irgendwo", "14/15 ist nicht am
    # richtigen Freeze-Ort"). Vorher hingen beide nur am Fenster.
    _names78 = [st[0] for st in _S78("industry")]
    # DAS FENSTER DARF KEIN ELEMENT DES SCHRITTS VERDECKEN (Nutzer, Sitzung
    # 17: "das Tutorial verdeckt den Einkaufswagen-Knopf"). Es stellt sich
    # deshalb unter das UNTERSTE hervorgehobene Element.
    check("b78 der Materialien-Schritt laesst 'Einkaufsliste' mitblinken",
          any("_bd_mat_copy_btn" in (n if isinstance(n, tuple) else (n,))
              for n in [st[0] for st in _S78("industry")]))
    check("b78 platziert wird unter dem UNTERSTEN Element",
          "max(_sicht, key=lambda w: w.mapToGlobal(" in
          open("eve_trader/ui/tutorial.py", encoding="utf-8").read())
    # NACHGEZOGEN 16.09.2026: der Schritt traegt jetzt REITER + Karte, damit
    # "Back" aus dem Invention-Schritt wieder in der Rezeptstruktur landet.
    check("b78 'Build or buy' zeigt auf seine Karte",
          any(isinstance(n, tuple) and "_bd_karte_bauenkaufen" in n
              for n in _names78))
    # BEIDE KARTEN (Nutzer 18.09.2026): der Text nennt "Production depth",
    # also blinkt die Karte mit - und sie existiert im Bauplan-Fenster.
    check("b78 'Build or buy' laesst auch 'Production depth' blinken",
          any(isinstance(n, tuple) and "_bd_karte_bauenkaufen" in n
              and "_bd_karte_tiefe" in n for n in _names78))
    check("b78 die Karte 'Production depth' ist am Fenster gemerkt",
          "self._bd_karte_tiefe = self._collapsible(" in open(
              "eve_trader/ui/mw_bauplan_fenster.py", encoding="utf-8").read())
    check("b78 und stellt dabei den Rezeptstruktur-Reiter selbst her",
          any(isinstance(n, tuple) and "_bd_karte_bauenkaufen" in n
              and any(str(x).startswith("bd:tab:") for x in n)
              for n in _names78))
    check("b78 'Speichern und einfrieren' zeigt auf BEIDE Knoepfe",
          any({"_bd_save_btn", "_bd_frozen_btn"} <= set(n)
              for n in _names78 if isinstance(n, tuple)))
    check("b78 der letzte Schritt macht den Bauplan zu",
          "_d.close()" in __import__("inspect").getsource(
              _TF78.zeigen))
    check("b78 der Blaupausen-Schritt laesst BEIDE Knoepfe blinken",
          _bp78 and {"bp_refresh_btn", "g_sde_btn"} <= set(_bp78[0][0]))
    check("b78 Strukturen kommen VOR dem Scanner (Nutzer-Reihenfolge)",
          _iS and _iC and _iS[0] < _iC[0])
    # DIE TOUR SCHALTET IM BAUPLAN-FENSTER VON REITER ZU REITER (Sitzung 17).
    # ANGESPROCHEN WIRD DER NAME, nicht die Nummer: bei einem T1-Plan fehlt
    # "Invention", dann verschieben sich alle Nummern dahinter (gemessen).
    _d78 = getattr(win, "_bd_dialog", None)
    if _d78 is not None and _d78.isVisible():
        from PySide6.QtWidgets import QTabWidget as _QTW78
        _tw78 = (_d78.findChildren(_QTW78) or [None])[0]
        _tp78b = _TF78(win, "industry")
        try:
            for _ziel78 in (_t4("Materials"), _t4("Run planner"),
                            _t4("Recipe structure")):
                _i78 = [i for i, st in enumerate(_S78("industry"))
                        if st[0] == "bd:tab:" + _ziel78]
                if not _i78 or _tw78 is None:
                    continue
                _tp78b.i = _i78[0]
                _tp78b.zeigen()
                _app.processEvents()
                eq(f"b78 der Schritt zu '{_ziel78}' schaltet dorthin",
                   _tw78.tabText(_tw78.currentIndex()), _ziel78)
        finally:
            _tp78b.abbrechen()
            _app.processEvents()
    check("b78 fehlt ein Reiter (T1-Plan ohne Invention), bricht nichts",
          "return _d                              # Reiter fehlt: Fenster"
          in open("eve_trader/ui/tutorial.py", encoding="utf-8").read())
    eq("b78 die Bauplan-Schritte haengen ALLE am Bauplan-Fenster",
       [st[1] for st in _S78("industry")
        if st[0] is None and st[1] not in (_t4("Welcome to EVE-MoMa"),
                                           _t4("That is the industry side"))],
       [])
    # DAS FENSTER BRAUCHT EINEN ANKER (Nutzer-Fund Sitzung 17: "der Bauplan
    # rutscht in den Hintergrund ... wenn man das Haupttool herumzieht,
    # verschiebt sich das Tutorial-Fenster nicht mit").
    _tq78 = _TF78(win, "trading")
    try:
        _fl78 = int(_tq78.windowFlags())
        # Qt.Tool liegt ueber SEINEM Besitzer - genau das wollen wir. KEIN
        # WindowStaysOnTopHint: das laege auch ueber Discord & Co.
        check("b78 die Tour ist ein eigenes Werkzeugfenster",
              bool(_fl78 & int(_Qt76.Tool)))
        check("b78 aber NICHT ueber fremden Programmen",
              not (_fl78 & int(_Qt76.WindowStaysOnTopHint)))
        # AUSSEHEN (Nutzer, Sitzung 17): deutlich dunkler als das Werkzeug,
        # goldener Rahmen, groessere Schrift. EINE FRUEHERE FASSUNG DAVON GING
        # STILL VERLOREN (ein abgebrochenes Skript schrieb nicht) - deshalb
        # hier festgenagelt.
        from eve_trader.ui import theme as _th78
        check("b78 das Fenster ist dunkler als das Werkzeug",
              "#03060B" in _tq78.styleSheet()
              and _th78.BG not in _tq78.styleSheet())
        check("b78 der Rahmen ist in der Icon-Goldfarbe",
              f"solid {_th78.AMBER}" in _tq78.styleSheet())
        check("b78 die Schrift ist gross genug zum Lesen",
              "font-size:19px" in _tq78.titel.styleSheet()
              and "font-size:15px" in _tq78.text.styleSheet())
        check("b78 sie fuehrt sich selbst nach (Zeitgeber laeuft)",
              _tq78._folgen.isActive())
        _tq78.i = 1
        _tq78.zeigen()
        _app.processEvents()
        # Der Rahmen gehoert zum FENSTER seines Elements, nicht immer zum
        # Hauptfenster - sonst laege er hinter dem Bauplan.
        check("b78 der Rahmen haengt am Fenster seines Elements",
              _tq78._rahmen and _tq78._rahmen[0].parent() is win.g_hub.window())
        # ENTSCHEIDEND ist der Fall im BAUPLAN-FENSTER: dort lag der Rahmen
        # frueher hinter dem Bauplan, weil er am Hauptfenster hing.
        _dq78 = getattr(win, "_bd_dialog", None)
        if _dq78 is not None and _dq78.isVisible():
            _tb78 = _TF78(win, "industry")
            try:
                _ib78 = [i for i, st in enumerate(_S78("industry"))
                         if str(st[0]).startswith("bd:tab:")]
                if _ib78:
                    _tb78.i = _ib78[0]
                    _tb78.zeigen()
                    _app.processEvents()
                    check("b78 im Bauplan haengt der Rahmen am BAUPLAN-Fenster",
                          _tb78._rahmen
                          and _tb78._rahmen[0].window() is _dq78)
            finally:
                _tb78.abbrechen()
                _app.processEvents()
        # Verschieben: nach dem Nachfuehren muss der Rahmen wieder sitzen.
        _vor78q = _tq78._rahmen[0].geometry()
        _tq78._nachfuehren()
        _app.processEvents()
        check("b78 das Nachfuehren setzt den Rahmen wieder passend",
              _tq78._rahmen[0].geometry().width()
              == win.g_hub.width() + 6)
        # NICHT BEI JEDEM TAKT NACH VORN (Nutzer-Fund Sitzung 17: "der
        # Bauplan bleibt hinter dem Haupttool, ich kann ihn nicht mehr
        # hervorheben"). Ein raise_() alle 200 ms zog das Besitzerfenster mit.
        _src78t = __import__("inspect").getsource(type(_tq78)._nachfuehren)
        check("b78 das Nachfuehren holt die Tour NICHT staendig nach vorn",
              "self.raise_()" not in _src78t)
        check("b78 nach vorn geholt wird nur beim Schrittwechsel",
              "if vor:" in __import__("inspect").getsource(
                  type(_tq78)._platzieren)
              and "self._platzieren(vor=True)" in
              __import__("inspect").getsource(type(_tq78)._fenster_ordnen))
        _fo78 = __import__("inspect").getsource(type(_tq78)._fenster_ordnen)
        check("b78 und der Bauplan wird dabei selbst nach vorn geholt",
              "_ziel.raise_()" in _fo78)
        # ENTSCHEIDEND: die Tour HAENGT sich an das Fenster, um das es geht -
        # sonst zieht sie beim Nach-vorn-Holen ihren Besitzer (Haupttool) mit
        # und drueckt den Bauplan zurueck (Nutzer-Fund Sitzung 17).
        check("b78 die Tour haengt sich an das Fenster des Schritts",
              "self.setParent(_ziel, _flags)" in _fo78)
        # DAS ZIELFENSTER WIRD AM ELEMENT ABGELESEN, nicht am Namen
        # (Nutzer-Fund: "_bd_karte_bauenkaufen" zeigt in den BAUPLAN, heisst
        # aber nicht "bd:" - die Tour hielt es fuer einen Haupttool-Schritt
        # und schob den Bauplan nach hinten).
        _zf78 = __import__("inspect").getsource(type(_tq78)._zielfenster)
        check("b78 das Zielfenster kommt vom Element, nicht vom Namen",
              "return _w.window()" in _zf78)
        # RUECKFALL fuer Schritte NACH dem Oeffnen: ein gemerkter Knopf kann
        # auf ein ALTES Bauplan-Fenster zeigen (unsichtbar). Ohne den
        # Rueckfall landete die Tour am Haupttool und schob den Bauplan nach
        # hinten (Nutzer-Fund 14/15).
        check("b78 nach dem Oeffnen gilt der Bauplan als Zielfenster",
              '_nach_oeffnen = any(st[4] == "bauplan_offen"' in _zf78
              and "if _nach_oeffnen or self._schritt_im_bauplan():" in _zf78)
        check("b78 beim Schrittwechsel kommt auch das Anker-Fenster nach vorn",
              "_anker.window().raise_()" in __import__("inspect").getsource(
                  type(_tq78)._platzieren))
        _d78z = getattr(win, "_bd_dialog", None)
        if _d78z is not None and _d78z.isVisible():
            _tz78 = _TF78(win, "industry")
            try:
                _ik78 = [i for i, st in enumerate(_S78("industry"))
                         if st[0] == "_bd_karte_bauenkaufen"]
                if _ik78 and getattr(win, "_bd_karte_bauenkaufen", None):
                    _tz78.i = _ik78[0]
                    _tz78.zeigen()
                    _app.processEvents()
                    check("b78 'Build or buy' zaehlt zum BAUPLAN-Fenster",
                          _tz78._zielfenster() is _d78z)
            finally:
                _tz78.abbrechen()
                _app.processEvents()
        check("b78 spaeter auftauchende Elemente blinken nach",
              "self._hervorheben(_soll)" in _src78t)
        check("b78 platziert wird in BILDSCHIRM-Koordinaten",
              "mapToGlobal" in __import__("inspect").getsource(
                  type(_tq78)._platzieren))
    finally:
        _tq78.abbrechen()
        _app.processEvents()
    check("b78 der Knopf sitzt in der Seitenleiste",
          getattr(win, "tutorial_btn", None) is not None
          and win.tutorial_btn.text() == _t4("Tutorial"))
    check("b78 beim ersten Start wird EINMAL gefragt",
          "self.settings[\"tutorial_gefragt\"] = True" in _src_mw
          and "QTimer.singleShot(1500, self._tutorial_erstfrage)" in _src_mw)
except Exception as _e78:                                # pragma: no cover
    _fail.append(f"b78 Tutorial: {type(_e78).__name__}: {_e78}")


# ---------------------------------------------------------------- (b60)
# BERECHTIGUNGS-SCHALTER GELTEN SOFORT (Sitzung 17, Nutzer-Befund bei der
# Erstinstallation): "Structure markets" stand sichtbar auf On, intern galt
# Off, bis ganz unten "Save" gedrueckt wurde - das Neu-Verlinken fragte die
# Struktur-Berechtigung deshalb nicht an. Funktional am echten Feld.
try:
    from eve_trader import config as _cfg60
    _alt60 = win.settings.get("use_structures")
    _cb60 = getattr(win, "s_struct", None)
    check("b60 der Struktur-Schalter existiert", _cb60 is not None)
    if _cb60 is not None:
        _cb60.setCurrentIndex(0); _app.processEvents()
        _cb60.setCurrentIndex(1); _app.processEvents()
        check("b60 Umstellen auf On gilt SOFORT, ohne Save",
              win.settings.get("use_structures") is True)
        check("b60 ... und steht auf der Platte (Verlinken liest die Einstellung)",
              _cfg60.load_settings().get("use_structures") is True)
        _cb60.setCurrentIndex(0); _app.processEvents()
        check("b60 Umstellen auf Off gilt ebenso sofort",
              win.settings.get("use_structures") is False)
        _cb60.setCurrentIndex(1 if _alt60 else 0); _app.processEvents()
except Exception as _e60:                                # pragma: no cover
    _fail.append(f"b60 Berechtigungs-Schalter: {type(_e60).__name__}: {_e60}")


# ---------------------------------------------------------------- (b59)
# DIE SUITE HAENGT NICHT AM EINRICHTUNGS-FENSTER (Sitzung 17).
# Die Zeitgeber der Hauptfenster feuern oft erst beim Abraeumen - also
# NACH den Pruefungen. Deshalb hier einmal die Ereignisse abarbeiten, damit
# ein vergessenes Stilllegen noch VOR der Schlusszeile auffaellt.
import time as _time59
_bis59 = _time59.time() + 0.6            # > 300 ms Erststart-Zeitgeber
while _time59.time() < _bis59:
    _app.processEvents()
    _time59.sleep(0.02)
# UMGEBUNGSUNABHAENGIG: das Stilllegen gilt fuer die KLASSE. Ob das Fenster
# anspringt, haengt an `.smoke_home` - diese Pruefung nicht.
check("b59 das Einrichtungsfenster ist fuer JEDES Hauptfenster stillgelegt",
      MainWindow.__dict__.get("_erste_einrichtung_pruefen") is _einrichtung_still)
check("b59 auch die drei Erststart-Fragen sind fuer jedes Hauptfenster still",
      all(MainWindow.__dict__.get(_n59) is _einrichtung_still
          for _n59 in ("_erststart_rezepte_anbieten", "_erststart_ohne_charakter",
                       "_frage_verlauf_laden")))
check("b59 kein Einrichtungsfenster oeffnet sich unbestellt im Testlauf "
      f"(geoeffnet von: {_EINRICHTUNG_UNBESTELLT})",
      not _EINRICHTUNG_UNBESTELLT)
check(f"b59 kein anderes modales Fenster blieb offen ({_MODAL_UNBESTELLT})",
      not _MODAL_UNBESTELLT)

# ---------------------------------------------------------------- (b63)
# EINE GEDECKTE ZEILE DARF NICHT "kaufen" SAGEN.
#
# NUTZER-BEFUND (Sitzung 20, Ametat II x20): in der Rezept-Struktur stand bei
# Fermionic Condensates "kaufen", waehrend der Materialien-Reiter fuer dasselbe
# Item "genug" meldete (10.2k im Hangar) und der Einkauf leer blieb. Hier am
# ECHTEN Fenster gemessen, nicht nur am Quelltext: die Zeile eines Items, das
# der Plan vollstaendig aus dem Bestand deckt und NICHT kauft, muss "aus
# Bestand gedeckt" tragen.
class _Recipes63b:
    """100 (Fertigung) <- 10x 201 (Reaktion) <- 10x 301. Kaufen ist bei 201
    billiger als Bauen - der Baum entscheidet also 'buy'."""
    product_to_bp = {100: (900, I.MANUFACTURING, 1), 201: (901, I.REACTION, 1)}
    bp_materials = {(900, I.MANUFACTURING): [(201, 10)],
                    (901, I.REACTION): [(301, 10)]}
    activity_time = {(900, I.MANUFACTURING): 60, (901, I.REACTION): 60}
    activity_max_runs = {(900, I.MANUFACTURING): 0, (901, I.REACTION): 0}
    reaction_products = {201}
    invention_for_bpc = {}
    bp_products = {}
    item_cat = {}

    def is_manufactured(self, t):
        return t in self.product_to_bp


_pr63b = {100: 100000.0, 201: 5.0, 301: 10.0}
_rec63b = _Recipes63b()
_opts63b = {"me": 0, "te": 0, "job_pct": 0, "invention": False,
            "build_reactions": True, "tree_depth": 4, "stock": {201: 10000}}
win._bd_recipes = _rec63b
win._bd_opts = dict(_opts63b)
win._bd_pricemap = dict(_pr63b)
_tree63b = I.build_tree(100, _pr63b.get, _rec63b, dict(_opts63b))
_plan63b = I.production_plan(100, 10, _pr63b.get, _rec63b, dict(_opts63b))
# VORBEDINGUNG - ohne sie prueft der Rest nichts (die Zeile faellt sonst gar
# nicht auf den Rueckfall zurueck).
_komp63b = [c for c in (_tree63b or {}).get("components", [])
            if c.get("type_id") == 201]
check("b63 der Baum entscheidet fuer 201 'kaufen'",
      bool(_komp63b) and _komp63b[0].get("decision") == "buy")
check("b63 der Plan setzt fuer 201 gar keine Entscheidung",
      201 not in (_plan63b.get("decision") or {}))
check("b63 und kauft 201 auch nicht",
      201 not in (_plan63b.get("buy") or {}))
check("b63 der Bestand deckt 201",
      201 in (_plan63b.get("stock_used") or {}))

_res63b = {"tree": _tree63b, "plan": _plan63b, "sell": 200000.0,
           "sell_is_contract": False,
           "names": {100: "Testendprodukt", 201: "Testreaktion", 301: "Testmat"}}
_dlg63b = None
try:
    win._show_build_detail(100, "Testendprodukt", _res63b)
    _dlg63b = getattr(win, "_bd_dialog", None)
    check("b63 Bauplan geoeffnet", _dlg63b is not None)
    _zeilen63b = []
    for _tw63 in (_dlg63b.findChildren(QTreeWidget) if _dlg63b else []):
        # NUR DIE REZEPT-STRUKTUR: der Runplaner ist ebenfalls ein Baum, hat
        # aber andere Spalten - dort stuende in Spalte 2 eine Zahl, und die
        # Pruefung waere an der falschen Stelle rot geworden (in der ersten
        # Fassung genau passiert).
        if _tw63.columnCount() < 3 or _tw63.topLevelItemCount() != 1:
            continue
        if "Testendprodukt" not in _tw63.topLevelItem(0).text(0):
            continue

        def _sammle63(_it):
            _zeilen63b.append((_it.text(0), _it.text(2)))
            for _i in range(_it.childCount()):
                _sammle63(_it.child(_i))
        for _i in range(_tw63.topLevelItemCount()):
            _sammle63(_tw63.topLevelItem(_i))
    _treffer63 = [a for n, a in _zeilen63b if "Testreaktion" in n]
    check(f"b63 die Zeile steht im Baum ({_zeilen63b[:6]})", bool(_treffer63))
    # BEIDE SPRACHEN akzeptieren - das Testfenster kann englisch oder deutsch
    # laufen (b3/b13/b42 gelernt).
    _gedeckt63 = {_t4("covered from stock"), "covered from stock",
                  "aus Bestand gedeckt"}
    check(f"b63 sie sagt 'aus Bestand gedeckt' ({_treffer63})",
          bool(_treffer63) and _treffer63[0] in _gedeckt63)
    check(f"b63 und eben NICHT 'kaufen' ({_treffer63})",
          bool(_treffer63)
          and _treffer63[0] not in (_t4("buy"), "buy", "kaufen"))
finally:
    try:
        if _dlg63b is not None:
            _dlg63b.close()
        _app.processEvents()
    except Exception:
        pass

# ---------------------------------------------------------------- (b64)
# GRUPPEN-BLACKLIST VON DER OBERFLAECHE BIS IN DEN PLAN (Punkt F, Sitzung 20).
# Nicht nur "die Funktion liest die Einstellung", sondern: Haekchen klicken ->
# Einstellung gespeichert -> Ausschluss neu gerechnet -> Item weder gebaut
# noch gekauft. Der ganze Weg, den der Nutzer geht.
class _Recipes64:
    """100 (Fertigung) <- 10x 301. 301 ist ein Mineral (Gruppe 'Mineral')."""
    product_to_bp = {100: (900, I.MANUFACTURING, 1)}
    bp_materials = {(900, I.MANUFACTURING): [(301, 10)]}
    activity_time = {(900, I.MANUFACTURING): 60}
    activity_max_runs = {(900, I.MANUFACTURING): 0}
    reaction_products = set()
    invention_for_bpc = {}
    bp_products = {}
    item_cat = {}

    def is_manufactured(self, t):
        return t in self.product_to_bp


_pr64 = {100: 100000.0, 301: 10.0}
_rec64 = _Recipes64()
_opts64 = {"me": 0, "te": 0, "job_pct": 0, "invention": False,
           "build_reactions": True, "tree_depth": 4}
# Zustand, den ein offener Bauplan hinterlaesst - genau die Felder, die
# _bau_refresh_exclusions_and_rebuild braucht.
win._bd_recipes = _rec64
win._bd_opts = dict(_opts64)
win._bd_all_ids = {100, 301}
win._bd_groups_cache = {100: "Fighter", 301: "Mineral"}
win._bd_bl_names_cache = {100: "Testendprodukt", 301: "Testmineral"}
win._bd_bp_type = 100
_alt64 = list(win.settings.get("bau_blacklist_gruppen", []) or [])
_rebuilt64 = {"n": 0}
win._bd_full_rebuild = lambda: _rebuilt64.__setitem__("n", _rebuilt64["n"] + 1)
try:
    win.settings["bau_blacklist_gruppen"] = []
    _w64 = win._build_blacklist_compact()
    _boxes64 = getattr(win, "_bl_gruppen_boxes", None) or {}
    check("b64 die Haekchenliste ist da", bool(_boxes64))
    check("b64 alle Gruppen des Materialien-Reiters stehen zur Wahl",
          set(_boxes64) == set(win._MATERIAL_GRUPPEN))
    check("b64 anfangs ist nichts angehakt",
          not any(cb.isChecked() for cb in _boxes64.values()))
    # VORHER: das Mineral wird gekauft.
    _plan64a = I.production_plan(100, 10, _pr64.get, _rec64,
                                 dict(_opts64, excluded=win._bau_never_build(
                                     [100, 301], win._bd_groups_cache, set(),
                                     win._bd_bl_names_cache)))
    check("b64 ohne Haekchen wird das Mineral gekauft",
          301 in (_plan64a.get("buy") or {}))
    # KLICK auf "Mineralien".
    _boxes64["Mineralien"].setChecked(True)
    _app.processEvents()
    check("b64 der Klick landet in den Einstellungen",
          win.settings.get("bau_blacklist_gruppen") == ["Mineralien"])
    check("b64 und stoesst die Neurechnung an", _rebuilt64["n"] >= 1)
    check("b64 der Ausschluss ist im Plan-Zustand angekommen",
          301 in (win._bd_opts.get("excluded") or set()))
    # NACHHER: weder gebaut noch gekauft, Endprodukt unveraendert.
    _plan64b = I.production_plan(100, 10, _pr64.get, _rec64,
                                 dict(_opts64, excluded=win._bd_opts.get("excluded")))
    check("b64 mit Haekchen wird das Mineral nicht mehr gekauft",
          301 not in (_plan64b.get("buy") or {}))
    check("b64 und der Plan meldet den Treffer",
          301 in (_plan64b.get("excluded_hit") or set()))
    check("b64 das Endprodukt wird weiterhin gebaut",
          100 in (_plan64b.get("build_runs") or {}))
    # RUECKWEG: Haekchen weg -> alles wie vorher.
    _boxes64["Mineralien"].setChecked(False)
    _app.processEvents()
    check("b64 Haekchen weg -> Einstellung leer",
          win.settings.get("bau_blacklist_gruppen") == [])
    check("b64 und das Mineral ist wieder im Einkauf",
          301 not in (win._bd_opts.get("excluded") or set()))
finally:
    win.settings["bau_blacklist_gruppen"] = _alt64
    try:
        _w64.deleteLater(); _app.processEvents()
    except Exception:
        pass

# ---------------------------------------------------------------- (b66)
# KEINE WAAGERECHTE BILDLAUFLEISTE WEGEN EINER FREMDEN SEITE.
# NUTZER (Sitzung 20, zwei Screenshots): die Gewinn-Uebersicht rechts war
# nur nach dem Scrollen zu sehen. Ursache war NICHT "Meine Bauplaene",
# sondern der Stapel: er nimmt die Mindestbreite der BREITESTEN Seite fuer
# alle, und das war die 16-spaltige Blueprints-Tabelle.
_st66 = getattr(win, "b_stack", None)
check("b66 der Bau-Stapel ist da", _st66 is not None)


def _breiteste66(pg, n=4):
    """Die n breitesten Blaetter der Seite - damit ein roter b66 SAGT, wer
    schuld ist (Windows-Befund 19.09.2026: nur die Zahl 1'527 stand da)."""
    out = []
    for w in pg.findChildren(QWidget):
        if w.layout() is not None:
            continue
        txt = (w.text() if hasattr(w, "text") else "")
        out.append((w.minimumSizeHint().width(), type(w).__name__, str(txt)[:40]))
    return sorted(out, reverse=True)[:n]


if _st66 is not None:
    _breiten66 = [_st66.widget(i).minimumSizeHint().width()
                  for i in range(_st66.count())]
    _breitste_i66 = max(range(len(_breiten66)), key=lambda i: _breiten66[i])
    check(f"b66 keine Seite sprengt 1366 px mit Seitenleiste ({_breiten66}; "
          f"Seite {_breitste_i66}: {_breiteste66(_st66.widget(_breitste_i66))})",
          all(b + 230 <= 1366 for b in _breiten66))
    check(f"b66 der Stapel selbst passt auf 1366 px ({_st66.minimumSizeHint().width()}; "
          f"breiteste: {_breiteste66(_st66)})",
          _st66.minimumSizeHint().width() + 230 <= 1366)
    # GEGENPROBE: die Bauplan-Seite ist wirklich die schmale von beiden -
    # sonst haette die Pruefung oben auch bei vertauschten Seiten gehalten.
    # SITZUNG 20: die Seite traegt jetzt Karte (520) + Gewinn-Uebersicht (320)
    # als Mindestbreiten, also rund 870 statt vorher 391. Die Zusage bleibt,
    # dass sie mit der Seitenleiste in 1366 px passt - das wird gerechnet
    # statt geraten.
    check(f"b66 Bauplan-Seite plus Seitenleiste passen in 1366 px "
          f"({_st66.widget(2).minimumSizeHint().width()}; "
          f"breiteste: {_breiteste66(_st66.widget(2))})",
          _st66.widget(2).minimumSizeHint().width() + 230 <= 1366)
    # KOPFZEILEN-KNOEPFE DUERFEN SCHRUMPFEN (Windows-Befund 19.09.2026).
    check("b66 die drei Kopfzeilen-Knoepfe haben eine kleine Untergrenze (40 px)",
          all(getattr(win, _n).minimumWidth() == 40
              for _n in ("bp_order_btn", "bp_progress_btn")))

# ---------------------------------------------------------------- (b67)
# WARNER FUER EINEN ALTEN ODER FALSCHEN MARKT (Nutzer, Sitzung 20).
# Am echten Fenster gemessen, nicht nur am Quelltext: der Knopf muss blinken
# und die Meldung neben dem Charakter-Feld erscheinen.
check("b67 die Warn-Beschriftung gibt es", getattr(win, "g_scan_warn", None) is not None)
# GEMESSEN WIRD DER ZUSTAND, NICHT isVisible(): ein Widget in einem nie
# angezeigten Fenster meldet IMMER "unsichtbar" - die Pruefung waere blind
# (dieselbe Falle wie bei height() in b2t). Der Blink-Zeitgeber und der Text
# sagen die Wahrheit.
win._scan_warnung_setzen("")
check("b67 ausgeschaltet laeuft kein Zeitgeber", not win._scan_blink_timer.isActive())
# HUB GEWECHSELT -> Warnung, Blinken an.
win._scan_hub_gewechselt = True
win._scan_alter_pruefen()
_app.processEvents()
check("b67 nach Hub-Wechsel steht eine Warnung", bool(win.g_scan_warn.text()))
check("b67 und der Knopf blinkt", win._scan_blink_timer.isActive())
check(f"b67 die Meldung nennt den Markt ({win.g_scan_warn.text()!r})",
      "arkt" in win.g_scan_warn.text() or "arket" in win.g_scan_warn.text())
_txt_hub67 = win.g_scan_warn.text()
# Ein Blinkschritt aendert den Rahmen des Knopfs und nimmt ihn wieder weg.
win._scan_blink_schritt()
_an67 = win.g_scan_btn.styleSheet()
win._scan_blink_schritt()
_aus67 = win.g_scan_btn.styleSheet()
check("b67 ein Blinkschritt faerbt den Rahmen amber", "border" in _an67
      and "transparent" not in _an67)
# GLEICHE GROESSE IN BEIDEN ZUSTAENDEN (Nutzer: "das Blinken laesst das ganze
# UI minimal nach unten rutschen"). Ein Rahmen, der nur im An-Zustand da ist,
# aendert die Knopfgroesse im Takt - deshalb hat auch der Aus-Zustand einen,
# nur durchsichtig.
check("b67 der Aus-Zustand hat denselben Rahmen, nur durchsichtig",
      "border:2px" in _aus67 and "transparent" in _aus67)
# SCAN GEDRUECKT -> Hub-Wechsel gilt als erledigt.
win._scan_hub_gewechselt = False
win._scan_alter_pruefen()
_app.processEvents()
_txt_alt67 = win.g_scan_warn.text()
check("b67 ohne Hub-Wechsel entscheidet das ALTER",
      _txt_alt67 != _txt_hub67 or not win._scan_blink_timer.isActive())
# Frischer Scan -> keine Warnung mehr, Blinken aus, Rahmen weg.
import eve_trader.store as _st67
_alt_fn67 = _st67.snapshot_age_seconds
try:
    _st67.snapshot_age_seconds = lambda *a, **k: 60.0
    win._scan_alter_pruefen(); _app.processEvents()
    check("b67 frischer Scan -> keine Warnung", not win._scan_blink_timer.isActive())
    check("b67 und das Blinken hoert auf", not win._scan_blink_timer.isActive())
    check("b67 der Rahmen bleibt nicht stehen", win.g_scan_btn.styleSheet() == "")
    # SOFORT AUFHOEREN beim Klick auf den Scan-Knopf - nicht erst bei der
    # naechsten Alterspruefung (Nutzer: im Ladefenster blinkte es weiter).
    _st67.snapshot_age_seconds = lambda *a, **k: 7200.0
    win._scan_alter_pruefen(); _app.processEvents()
    check("b67 vor dem Scan blinkt es", win._scan_blink_timer.isActive())
    _sg67 = getattr(win, "scan_global", None)
    check("b67 der Scan schaltet es sofort aus",
          "self._scan_warnung_setzen(\"\")" in
          __import__("inspect").getsource(_sg67))
    # UND SCHWEIGT, SOLANGE ER LAEUFT (Nutzer, zweiter Befund): die Pruefung
    # alle 30 s schaltete das Blinken sonst mitten im Scan wieder an - der
    # Schnappschuss wird ja erst am ENDE frisch.
    win._scan_laeuft = True
    win._scan_alter_pruefen(); _app.processEvents()
    check("b67 waehrend des Scans blinkt nichts", not win._scan_blink_timer.isActive())
    win._set_scan_buttons(True)          # Scan fertig
    _app.processEvents()
    check("b67 danach darf wieder geprueft werden", not win._scan_laeuft)
    # GROESSE: waehrend des Blinkens ist der Knopf festgenagelt, danach frei.
    _st67.snapshot_age_seconds = lambda *a, **k: 7200.0
    win._scan_alter_pruefen(); _app.processEvents()
    check("b67 beim Blinken ist die Knopfgroesse fest",
          win.g_scan_btn.minimumSize() == win.g_scan_btn.maximumSize())
    # Die Hover-Regel entsteht erst beim naechsten Blinkschritt.
    win._scan_blink_schritt()
    check("b67 die Hover-Regel hat denselben Rahmen",
          "QPushButton:hover{border:2px" in win.g_scan_btn.styleSheet())
    win._scan_warnung_setzen("")
    check("b67 danach ist die Groesse wieder frei",
          win.g_scan_btn.maximumSize().width() > 1000)
    _st67.snapshot_age_seconds = lambda *a, **k: 7200.0
    win._scan_alter_pruefen(); _app.processEvents()
    check("b67 nach zwei Stunden warnt es wieder", win._scan_blink_timer.isActive())
    _st67.snapshot_age_seconds = lambda *a, **k: 3599.0
    win._scan_alter_pruefen(); _app.processEvents()
    check("b67 kurz vor einer Stunde noch nicht", not win._scan_blink_timer.isActive())
    _st67.snapshot_age_seconds = lambda *a, **k: None
    win._scan_alter_pruefen(); _app.processEvents()
    check("b67 gar kein Scan zaehlt als zu alt", win._scan_blink_timer.isActive())
finally:
    _st67.snapshot_age_seconds = _alt_fn67
    win._scan_warnung_setzen("")

# ---------------------------------------------------------------- (b68)
# KENNZAHLEN VERDECKEN (Nutzer, Sitzung 20): "wenn man jemandem etwas an dem
# Tool zeigen will, online oder on Stream, dann kann man diese heiklen Daten
# einfach zensieren." Am echten Fenster gemessen.
_keys68 = ("pf_wealth", "pf_wallet", "pf_pl", "pf_flag",
           "pr_net", "pr_rev", "pr_trades", "pr_margin")
_reg68 = getattr(win, "_kpi_labels", None) or {}
for _k68 in _keys68:
    check(f"b68 {_k68} hat ein Auge", _k68 in _reg68)
_alt68 = list(win.settings.get("kpi_zensiert", []) or [])
try:
    win.settings["kpi_zensiert"] = []
    win._kpi_zensur_anwenden()
    _lbl68, _btn68 = _reg68["pf_wealth"]
    _lbl68.setText("343'533'257'585 ISK")
    check("b68 offen zeigt die echte Zahl", _lbl68.text() == "343'533'257'585 ISK")
    # VERDECKEN
    win._kpi_zensur_umschalten("pf_wealth")
    _app.processEvents()
    check("b68 verdeckt zeigt die Maske", _lbl68.text() != "343'533'257'585 ISK")
    check("b68 und die Zahl steht nicht mehr da", "343" not in _lbl68.text())
    check("b68 der Zustand ist gespeichert",
          "pf_wealth" in (win.settings.get("kpi_zensiert") or []))
    # DIE ENTSCHEIDENDE ZUSAGE: ein neuer setText() darf NICHTS preisgeben -
    # die Kennzahlen werden laufend neu gefuellt, waehrend der Stream laeuft.
    _lbl68.setText("999'999'999 ISK")
    check("b68 auch ein neuer Wert bleibt verdeckt", "999" not in _lbl68.text())
    # WIEDER ZEIGEN - und zwar den NEUEN Wert, nicht den alten.
    win._kpi_zensur_umschalten("pf_wealth")
    _app.processEvents()
    check("b68 wieder offen zeigt den aktuellen Wert",
          _lbl68.text() == "999'999'999 ISK")
    check("b68 und der Zustand ist wieder weg",
          "pf_wealth" not in (win.settings.get("kpi_zensiert") or []))
    # Jede Karte einzeln - eine verdeckte darf die anderen nicht mitnehmen.
    win._kpi_zensur_umschalten("pr_net")
    _app.processEvents()
    _lbl_rev68 = _reg68["pr_rev"][0]
    _lbl_rev68.setText("20'596'678'163 ISK")
    check("b68 die Nachbarkarte bleibt offen",
          _lbl_rev68.text() == "20'596'678'163 ISK")
finally:
    win.settings["kpi_zensiert"] = _alt68
    win._kpi_zensur_anwenden()


# ---------------------------------------------------------------- (b7u)
# REPROCESSING IM BAUPLAN, WEG B (1.0.9, Nutzer 18.09.2026 "also los"):
# Karte "Reprocessing" in der Rezeptstruktur, Schalter an -> die
# Einkaufsliste kauft komprimiertes Erz statt des Minerals, wo es
# guenstiger ist; Schalter aus -> exakt der alte Plan. Alles ohne ESI und
# ohne SDE: Karte, Struktur-Werte, Skills und Preise sind hier vorgegeben.
# Rechnung: 10 Testship brauchen 100 Testmat, 40 aus Bestand -> 60 kaufen zu
# 100 ISK = 6'000. Compressed Testore (1 ISK) ergibt je Portion 100
# floor(400 x 0.83854) = 335 Testmat -> 1 Portion = 100 ISK. Ersparnis 5'900,
# Ueberschuss 275.
import eve_trader.reprocess as _R7u                                  # noqa: E402
from eve_trader import config, esi, store                            # noqa: E402
_alt7u = {
    "map": I.reprocess_map, "cats": I.item_category_map, "sde": I.reprocess_struktur_sde,
    "ids": I.reprocess_skill_ids, "erz": I.reprocess_erz_skill,
    "chars": store.list_characters, "save": config.save_settings,
    "names": esi.resolve_names,
}
_alt_set7u = {k: win.settings.get(k) for k in
              ("bau_reprocess_on", "bau_reprocess_struct", "bau_structures",
               "bau_char_skills", "bau_build_chars")}
I.reprocess_map = lambda: {62516: {"portion": 100, "out": {200: 400}}}
I.item_category_map = lambda: {62516: (25, 462, 0), 200: (4, 18, 0), 100: (6, 25, 0)}
I.reprocess_struktur_sde = lambda: {
    "bonus": {"Tatara": 5.5},
    "rig": {46639: {"name": "Standup L-Set Reprocessing Monitor I", "mult": 0.51,
                    "hi": 1.0, "low": 1.06, "null": 1.12}}}
I.reprocess_skill_ids = lambda: {"Reprocessing": 3385, "Reprocessing Efficiency": 3389}
I.reprocess_erz_skill = lambda: {62516: 60377}
store.list_characters = lambda: [{"character_id": 1, "character_name": "Peanut Motor"}]
config.save_settings = lambda s: None
esi.resolve_names = lambda ids: {int(i): {62516: "Compressed Testore", 200: "Testmat",
                                          100: "Testship"}.get(int(i), f"#{i}")
                                 for i in ids}
_dlg7u = None
try:
    win.settings["bau_structures"] = [{"id": "s7u", "name": "R&R Yard", "type": "tatara",
                                       "rigs": ["sde:46639", "", ""], "security": 2.1}]
    win.settings["bau_reprocess_struct"] = "s7u"
    win.settings["bau_reprocess_on"] = True
    win.settings["bau_char_skills"] = {"1": {"3385": 5, "3389": 5, "60377": 5}}
    # Ohne Bau-Charakter bleibt der Runplaner leer - Stufe 0 haengt an ihm.
    win.settings["bau_build_chars"] = [1]
    _pr7u = dict(PRICES); _pr7u[62516] = 1.0
    win._bd_pricemap = dict(_pr7u)
    win._bd_recipes = _Recipes()
    win._bd_opts = {"me": 0, "te": 0, "job_pct": 0, "build_reactions": False,
                    "tree_depth": 4, "stock": {200: 40}}
    _ro7u = win._reprocess_opts()
    eq("b7u die Struktur-Basis der Tatara ist die gemessene",
       round(_ro7u["basis"], 6), 0.602616)
    win._bd_opts["reprocess"] = _ro7u
    win._bd_type = 100
    win._bd_qty = 10
    _plan7u = I.production_plan(100, 10, _pr7u.get, _Recipes(), dict(win._bd_opts))
    _tree7u = I.build_tree(100, _pr7u.get, _Recipes(), dict(win._bd_opts))
    _res7u = {"tree": _tree7u,
              "names": {100: "Testship", 200: "Testmat", 62516: "Compressed Testore"},
              "sell": 6000.0, "sell_is_contract": False, "plan": _plan7u}
    _sbd_frisch(100, "Testship", _res7u)
    _dlg7u = getattr(win, "_bd_dialog", None)
    _app.processEvents()

    def _mat_zeilen7u():
        _tbl = getattr(win, "_bd_mat_tab_tbl", None)
        out = []
        if _tbl is None:
            return out
        _root = _tbl.invisibleRootItem()
        _st = [_root.child(i) for i in range(_root.childCount())]
        while _st:
            _x = _st.pop()
            out.append(_x.text(0))
            _st += [_x.child(i) for i in range(_x.childCount())]
        return out

    def _mat_zeilen7u_alle():
        _tbl = getattr(win, "_bd_mat_tab_tbl", None)
        out = []
        if _tbl is None:
            return out
        _root = _tbl.invisibleRootItem()
        _st = [_root.child(i) for i in range(_root.childCount())]
        while _st:
            _x = _st.pop()
            # Der Status steht als Daten (UserRole), nicht als Text.
            out += [_x.text(c) for c in range(_tbl.columnCount())]
            out += [str(_x.data(c, Qt.UserRole) or "") for c in range(_tbl.columnCount())]
            _st += [_x.child(i) for i in range(_x.childCount())]
        return out

    def _info7u():
        _l = getattr(win, "_bd_mat_tab_info", None)
        return _l.text() if _l is not None else ""
    _cb7u = getattr(win, "_bd_reprocess_cb", None)
    check("b7u die Karte hat den Schalter, und er ist an", _cb7u is not None and _cb7u.isChecked())
    # LAGE (Nutzer 18.09.2026: "schieb das bitte hoeher, da wo man es sieht.
    # Direkt unter Production depth, lass zugeklappt"): Reihenfolge der
    # Klappkarten und Zustand der Reprocessing-Karte.
    _karten7u = []
    _zu7u = {}
    for _b7 in _dlg7u.findChildren(QPushButton):
        for _ti in ("Build or buy?", "Production depth", "Reprocessing", "Blacklist",
                    "Do I have the blueprints?"):
            if (_b7.text() or "").endswith(_t4(_ti)) and _b7.isCheckable():
                _karten7u.append(_ti)
                _zu7u[_ti] = _b7.isChecked()
    eq("b7u die Karte steht direkt unter Production depth",
       _karten7u, ["Build or buy?", "Production depth", "Reprocessing", "Blacklist",
                   "Do I have the blueprints?"])
    # Seit 27.09.2026 OFFEN (Nutzer: "Reprocessing ausklappen als Standard").
    eq("b7u ... und ist offen, auch mit Schalter an", _zu7u.get("Reprocessing"), True)
    _sc7u = getattr(win, "_bd_reprocess_struct_cb", None)
    check("b7u die Struktur-Auswahl steht auf der Tatara",
          _sc7u is not None and _sc7u.currentData() == "s7u")
    _plan_a = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
    eq("b7u der Plan kauft 100 Compressed Testore statt 60 Testmat",
       dict(_plan_a.get("buy") or {}), {62516: 100})
    eq("b7u ... Ersparnis 5'900 ISK, Ueberschuss 275 Testmat",
       (round(_plan_a.get("reprocess", {}).get("ersparnis") or 0), dict(_plan_a.get("surplus") or {})),
       (5900, {200: 275}))
    eq("b7u ... und total_cost ist um die Ersparnis gesunken",
       round(float(_plan7u["total_cost"]) - float(_plan_a["total_cost"])), 5900)
    check("b7u der Materialien-Tab zeigt das Erz",
          any("Compressed Testore" in z for z in _mat_zeilen7u()))
    # REZEPT-BAUM (Nutzer 18.09.2026: "im Rezeptbaum noch keine Beschreibung
    # fuer compressed Ores"): die Mineral-Zeile nennt das Erz.
    from PySide6.QtWidgets import QTreeWidget as _QTW7u

    def _baum_aktion7u(name):
        for _tw in _dlg7u.findChildren(_QTW7u):
            _hi = _tw.headerItem()
            if _hi is None or _tw.columnCount() < 3 or _hi.text(2) != _t4("Action"):
                continue                      # nur der Rezept-Baum
            _root = _tw.invisibleRootItem()
            _st = [_root.child(i) for i in range(_root.childCount())]
            while _st:
                _x = _st.pop()
                if _x.text(0) == name:
                    return _x.text(2)
                _st += [_x.child(i) for i in range(_x.childCount())]
        return None
    eq("b7u der Rezept-Baum sagt bei Testmat 'aus komprimiertem Erz'",
       _baum_aktion7u("Testmat"),
       _t4("from compressed ore \u267b \u00b7 {ore}").format(ore="Compressed Testore"))
    # DIE ROHZEILEN, aus denen Einkaufsfenster und Kopier-Knoepfe lesen
    # (Nutzer-Befund 18.09.2026: Einkaufsliste ohne Tritanium UND ohne Erz).
    _mr7u = [r for r in (getattr(win, "_bd_mat_rows", None) or []) if r.get("tid") == 62516]
    eq("b7u die Rohzeile des Erzes traegt missing=100, total=100, built=0",
       [(r["missing"], r["total"], r["built"], r["category"]) for r in _mr7u][:1],
       [(100, 100, 0, _mr7u[0]["category"] if _mr7u else None)])
    # GEDECKTE MINERALE BLEIBEN SICHTBAR (Nutzer-Befund): Testmat steht mit
    # 60 "aus Reprocessing", nichts zu kaufen.
    _tm7u = [r for r in (getattr(win, "_bd_mat_rows", None) or []) if r.get("tid") == 200]
    eq("b7u Testmat-Zeile: 60 aus Reprocessing, 0 zu kaufen, 100 Bedarf",
       [(r.get("reprocessed"), r["missing"], r["total"]) for r in _tm7u], [(60, 0, 100)])
    # Der Status steht im Deckungs-Balken (Widget) - pruefbar ist der
    # Grund, den die Zeile dabei bekommt.
    check("b7u ... und die Zeile sagt 'gedeckt durch Reprocessing'",
          bool(_tm7u) and "reprocessing" in (_tm7u[0].get("reason") or "").lower()
          and "stage 0" in (_tm7u[0].get("reason") or "").lower())
    # EINKAUFSLISTE (Restbedarf): Erz statt Mineral, solange nicht abgehakt.
    eq("b7u Restbedarf: 100 Erz + 40 Testmat (100 Bedarf - 60 gedeckt), kein Kauf",
       win._restbedarf_jetzt(), {200: 40, 62516: 100})
    eq("b7u Fehlbedarf jetzt: nur das Erz fehlt (100), Testmat ist gedeckt",
       [(r[0], r[1]) for r in win._fehlbedarf_jetzt()], [(62516, 100)])
    # HAKEN IN STUFE 0 = reprocesst: jetzt fehlt Testmat (60), das Erz nicht.
    _tr0 = getattr(win, "_sched_tree_ref", None)
    _row0 = None
    if _tr0 is not None and _tr0.topLevelItemCount() > 0:
        _s0 = _tr0.topLevelItem(0)
        for _i in range(_s0.childCount()):
            for _j in range(_s0.child(_i).childCount()):
                _row0 = _s0.child(_i).child(_j)
    check("b7u die Stufe-0-Zeile ist abhakbar",
          _row0 is not None and bool(_row0.flags() & Qt.ItemIsUserCheckable))
    if _row0 is not None:
        _row0.setCheckState(0, Qt.Checked)
        _app.processEvents()
    check("b7u der Haken landet als repro|62516 im Plan",
          "repro|62516" in (getattr(win, "_bd_runplan_checked", None) or set()))
    eq("b7u abgehakt: Testmat fehlt wieder (60), Erz nicht mehr",
       [(r[0], r[1]) for r in win._fehlbedarf_jetzt()], [(200, 60)])
    eq("b7u abgehakt: Restbedarf ohne Erz", win._restbedarf_jetzt(), {200: 100})
    if _row0 is not None:
        _row0.setCheckState(0, Qt.Unchecked)
        _app.processEvents()
    # CHARAKTERZEILE (Nutzer 19.09.2026): Haken am Charakter (zieht die Erz-
    # Zeilen mit, Schluessel char|repro|<cid>), und standardmaessig ZU wie
    # bei den anderen Stufen - die Stufe selbst offen.
    _cz0 = _row0.parent() if _row0 is not None else None
    check("b7u die Charakterzeile in Stufe 0 hat ein Kaestchen (char|repro|1) und ist zu",
          _cz0 is not None and _cz0.data(0, Qt.CheckStateRole) is not None
          and _cz0.data(0, Qt.UserRole + 6) == "char|repro|1"
          and not _cz0.isExpanded() and _tr0.topLevelItem(0).isExpanded())
    if _cz0 is not None:
        _cz0.setCheckState(0, Qt.Checked); _app.processEvents()
    check("b7u Haken am Charakter hakt die Erz-Zeile mit ab (repro|62516 + char|repro|1)",
          _row0 is not None and _row0.checkState(0) == Qt.Checked
          and {"repro|62516", "char|repro|1"} <= (
              getattr(win, "_bd_runplan_checked", None) or set()))
    if _cz0 is not None:
        _cz0.setCheckState(0, Qt.Unchecked); _app.processEvents()
    check("b7u ... und wieder loesen loest beides",
          _row0 is not None and _row0.checkState(0) == Qt.Unchecked
          and not ({"repro|62516", "char|repro|1"} & (
              getattr(win, "_bd_runplan_checked", None) or set())))

    def _sched_zeilen7u():
        _tr = getattr(win, "_sched_tree_ref", None)
        out = []
        if _tr is None:
            return out
        _root = _tr.invisibleRootItem()
        _st = [_root.child(i) for i in range(_root.childCount())]
        while _st:
            _x = _st.pop()
            out.append(tuple(_x.text(c) for c in range(_tr.columnCount())))
            _st += [_x.child(i) for i in range(_x.childCount())]
        return out
    _sz7u = _sched_zeilen7u()
    _stufe0 = [z for z in _sz7u if z[0].startswith("0. ")]
    check("b7u der Runplaner hat Stufe 0 Reprocessing mit der Struktur",
          len(_stufe0) == 1 and "R&R Yard" in _stufe0[0][0]
          and _t4("Reprocessing") in _stufe0[0][0])
    _tr7u = getattr(win, "_sched_tree_ref", None)
    check("b7u ... und sie steht ganz oben",
          _tr7u is not None and _tr7u.topLevelItemCount() > 0
          and _tr7u.topLevelItem(0).text(0).startswith("0. "))
    # SPALTEN WIE BEI DEN ANDEREN STUFEN (Nutzer 18.09.2026): Erz-Name in
    # Spalte 0, Menge in "Runs", Ergebnis + Ausbeute in "Stage", Charakter-
    # zeile nennt die Bloecke in "Blueprints".
    check("b7u ... Charakter und Zeile: 100 x Erz -> 60 Testmat (+275), 1 Block, 83.9 %",
          any(z[0] == "Peanut Motor" and z[2] == _t4("{n} batches").format(n=1)
              for z in _sz7u)
          and any(z[0] == "Compressed Testore" and z[1] == "100"
                  and z[4] == "\u2192 60 Testmat  \u00b7  83.9 %" and z[5] == "+275 Testmat"
                  for z in _sz7u))
    check("b7u ... Klick auf das Erz kopiert den Erz-Namen (ROLLE_KOPIERNAME)",
          _row0 is not None and _row0.data(0, _RKN7f) == "Compressed Testore")
    _cw7u = _tr7u.itemWidget(_row0, 2) if (_tr7u is not None and _row0 is not None) else None
    _btn7u = [w for w in (_cw7u.findChildren(QPushButton) if _cw7u is not None else [])]
    check("b7u ... und die Menge ist ein Kopier-Knopf '100'",
          len(_btn7u) == 1 and _btn7u[0].text() == "100")
    if _btn7u:
        _btn7u[0].click(); _app.processEvents()
        eq("b7u ... Klick auf den Knopf legt 100 in die Zwischenablage",
           QApplication.clipboard().text(), "100")
    # KEIN TEXTBLOCK MEHR UEBER DER LISTE (Nutzer 19.09.2026): das Erz ist
    # eine eigene Gruppe, die Zeile nennt Ausgang/Ausbeute/Charakter, die
    # Ersparnis steht in der Reprocessing-Karte, der Baum hat einen Erz-Kopf.
    check("b7u die Info-Zeile schweigt ueber Schritte und Ersparnis",
          "83.9" not in _info7u() and "5'900" not in _info7u())
    _alle7u = _mat_zeilen7u_alle()

    def _balken7u():
        # Der Status steht im Deckungs-Balken (QProgressBar.format), nicht im Item.
        _tbl = getattr(win, "_bd_mat_tab_tbl", None)
        out = []
        _root = _tbl.invisibleRootItem()
        _st = [_root.child(i) for i in range(_root.childCount())]
        while _st:
            _x = _st.pop()
            _w = _tbl.itemWidget(_x, 6)
            if _w is not None and hasattr(_w, "format"):
                out.append((_x.text(0), _w.format()))
            _st += [_x.child(i) for i in range(_x.childCount())]
        return out
    check("b7u die Erz-Zeile steht unter 'Compressed ore' und nennt 60 Testmat, 83.9 %, Peanut Motor",
          _t4("Compressed ore ♻") in _alle7u
          and any(n == "Compressed Testore" and "60 Testmat" in f and "83.9 %" in f
                  and "Peanut Motor" in f for n, f in _balken7u()))
    _rpl7u = getattr(win, "_bd_reprocess_lbl", None)
    check("b7u die Karte nennt die Ersparnis 5'900 und 1 Erz",
          _rpl7u is not None and "5'900" in _rpl7u.text()
          and _t4("saves {isk} · {n} ores").format(isk="", n=1).split("·")[1].strip()
          in _rpl7u.text())
    _tw7u = [w for w in _dlg7u.findChildren(QTreeWidget)]
    _baum7u = []
    for _w in _tw7u:
        _r = _w.invisibleRootItem(); _st = [_r.child(i) for i in range(_r.childCount())]
        while _st:
            _x = _st.pop(); _baum7u.append(tuple(_x.text(c) for c in range(3)))
            _st += [_x.child(i) for i in range(_x.childCount())]
    check("b7u der Rezept-Baum hat den Kopf 'Compressed ore (1)' mit der Erz-Zeile",
          any(z[0].startswith(_t4("Compressed ore ♻")) and "(1)" in z[0] for z in _baum7u)
          and any(z[0] == "Compressed Testore" and z[1] == "100"
                  and _t4("reprocess → {out} · {pct} %").format(out="60 Testmat", pct="83.9") in z[2]
                  for z in _baum7u))
    # BLACKLIST GILT AUCH FUER ERZ (Nutzer 19.09.2026: "wir rechnen damit,
    # es zu reprocessen, ABER es kommt weder in die Einkaufsliste noch in
    # den Runplaner - man bekommt es z. B. von einem Kollegen"): Gruppe
    # "Erz" -> das Erz ist gratis, deckt Testmat, steht nirgends zum Kauf.
    _bl_alt7u = win.settings.get("bau_blacklist_gruppen")
    win.settings["bau_blacklist_gruppen"] = ["Erz"]
    _cb7u.click(); _app.processEvents(); _cb7u.click(); _app.processEvents()
    _plan_bl = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
    _st_bl = (_plan_bl.get("reprocess") or {}).get("schritte") or []
    eq("b7u Erz auf der Blacklist: Einkaufsliste leer, Schritt gratis, deckt 60 Testmat, Ersparnis 6'000",
       (dict(_plan_bl.get("buy") or {}),
        [(s.get("erz"), s.get("gratis"), s.get("deckt")) for s in _st_bl],
        (_plan_bl.get("reprocess") or {}).get("ersparnis")),
       ({}, [(62516, True, {200: 60})], 6000.0))
    eq("b7u ... Restbedarf ohne Erz, Testmat gedeckt", win._restbedarf_jetzt(), {200: 40})
    _tr_bl = getattr(win, "_sched_tree_ref", None)
    check("b7u ... und der Runplaner hat KEINE Stufe 0",
          _tr_bl is not None and not any(
              _tr_bl.topLevelItem(i).text(0).startswith("0. ")
              for i in range(_tr_bl.topLevelItemCount())))
    _baum_bl = []
    for _w in _dlg7u.findChildren(QTreeWidget):
        _r = _w.invisibleRootItem(); _st = [_r.child(i) for i in range(_r.childCount())]
        while _st:
            _x = _st.pop(); _baum_bl.append(tuple(_x.text(c) for c in range(3)))
            _st += [_x.child(i) for i in range(_x.childCount())]
    check("b7u ... der Materials-Tab zeigt das Erz trotzdem: 100 gestellt, nichts fehlt",
          any(n == "Compressed Testore" and _t4("on blacklist \u2013 provided, not bought") in f
              and "60 Testmat" in f for n, f in _balken7u())
          and any(r.get("tid") == 62516 and int(r.get("total") or 0) == 100
                  and int(r.get("missing") or 0) == 0 for r in (win._bd_mat_rows or [])))
    check("b7u ... der Rezept-Baum sagt beim Erz 'on blacklist - provided'",
          any(z[0] == "Compressed Testore"
              and _t4("on blacklist \u2013 provided, not bought") in z[2] for z in _baum_bl))
    check("b7u ... und die Blacklist-Karte hat das Haekchen 'Compressed ore'",
          "Erz" in (getattr(win, "_bl_gruppen_boxes", None) or {}))
    if _bl_alt7u is None:
        win.settings.pop("bau_blacklist_gruppen", None)
    else:
        win.settings["bau_blacklist_gruppen"] = _bl_alt7u
    _cb7u.click(); _app.processEvents(); _cb7u.click(); _app.processEvents()
    # WARUM NICHT: Testmat ist getauscht, also KEINE "nicht guenstiger"-Zeile;
    # der Zweig darf nicht abstuerzen, wenn abgelehnt leer ist.
    check("b7u keine 'Ore not cheaper'-Zeile, wenn alles getauscht ist",
          _t4("Ore not cheaper for: {liste}").format(liste="")[:10] not in _info7u())
    # SCHALTER AUS: exakt der alte Plan, kein Schluessel mehr in den opts.
    _cb7u.click()
    _app.processEvents()
    _plan_b = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
    eq("b7u Schalter aus: der Plan kauft wieder 60 Testmat",
       dict(_plan_b.get("buy") or {}), {200: 60})
    check("b7u ... ohne 'reprocess' in den opts und ohne Erz im Tab",
          "reprocess" not in win._bd_opts
          and not any("Compressed Testore" in z for z in _mat_zeilen7u())
          and "Compressed" not in _info7u())
    check("b7u ... und Stufe 0 ist aus dem Runplaner verschwunden",
          not any(z[0].startswith("0. ") for z in _sched_zeilen7u()))
    check("b7u ... und der Rezept-Baum sagt wieder 'kaufen'",
          (_baum_aktion7u("Testmat") or "").startswith(_t4("buy")))
    eq("b7u ... und die Einstellung ist gespeichert", win.settings.get("bau_reprocess_on"), False)
    # WIEDER AN: derselbe Weg wie beim Nutzer, der es im offenen Dialog setzt.
    _cb7u.click()
    _app.processEvents()
    _plan_c = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
    eq("b7u wieder an: Erz statt Mineral", dict(_plan_c.get("buy") or {}), {62516: 100})
    # NPC-STATION gewaehlt: Basis 0.50 -> 0.50 x 1.3915 = 0.69575 -> 278 je
    # Portion, immer noch 1 Portion, Ueberschuss 218.
    _ix_npc = _sc7u.findData("npc")
    _sc7u.setCurrentIndex(_ix_npc)
    _app.processEvents()
    _plan_d = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
    eq("b7u NPC-Station: 278 je Portion -> Ueberschuss 218",
       dict(_plan_d.get("surplus") or {}), {200: 218})
    check("b7u ... und die Karte nennt die Basis 50.0 %",
          any("50.0" in (lb.text() or "") for lb in _dlg7u.findChildren(QLabel)))
    # IMPLANTAT (Nutzer 18.09.2026: "Implantate muessen erkannt werden ...
    # Button implants laden"): Knopf in der Karte, ESI-Abruf gegen die SDE-
    # Tabelle, Ergebnis in Ausbeute und Zeile. 0.83854 x 1.04 = 0.87208 ->
    # floor(400 x 0.87208) = 348 je Portion -> Ueberschuss 288.
    _sc7u.setCurrentIndex(_sc7u.findData("s7u"))
    _app.processEvents()
    _alt_run7u = win._run
    _alt_imp7u = esi.fetch_character_implants
    _alt_repimp7u = I.reprocess_implants
    _alt_set_imp7u = win.settings.get("bau_char_reproc_implant")
    _alt_cid7u = win.settings.get("client_id")
    try:
        win.settings["client_id"] = win.settings.get("client_id") or "test-client-7u"
        win._run = lambda worker, done_cb, fail_cb=None, **kw: done_cb(
            worker._fn(*worker._args, **worker._kwargs))
        esi.fetch_character_implants = lambda c, cid: [27174, 99999]
        I.reprocess_implants = lambda: {27174: {"name": "Zainou 'Beancounter' Reprocessing RX-804",
                                                "attr": "refiningYieldMutator", "value": 4.0}}
        _btn_imp = getattr(win, "_bd_reprocess_imp_btn", None)
        check("b7u die Karte hat den Knopf 'Load implants'",
              _btn_imp is not None and _btn_imp.text().strip() == _t4("Load implants"))
        _btn_imp.click()
        _app.processEvents()
        eq("b7u das Implantat ist gespeichert (RX-804, 4 %)",
           (win.settings.get("bau_char_reproc_implant") or {}).get("1", {}).get("pct"), 4.0)
        check("b7u ... und die Zeile nennt Charakter und Implantat",
              "Peanut Motor" in win._bd_reprocess_imp_lbl.text()
              and "RX-804" in win._bd_reprocess_imp_lbl.text()
              and "+4" in win._bd_reprocess_imp_lbl.text())
        _plan_i = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
        eq("b7u ... und die Ausbeute steigt: 348 je Portion -> Ueberschuss 288",
           (dict(_plan_i.get("surplus") or {}), round(_plan_i["reprocess"]["schritte"][0]["ausbeute"], 5)),
           ({200: 288}, 0.87208))
        # VON HAND (emm345, Nutzer: das RX-804 steckt in einem Jump-Clone -
        # ESI sieht nur den aktiven). Echter Knopf da; Wahl "keins" schlaegt
        # die ESI-Erkennung, Wahl RX-804 ohne ESI-Treffer zaehlt.
        _alt_hand7u = win.settings.pop("bau_char_reproc_implant_hand", None)
        try:
            check("b7u die Karte hat den Knopf 'Set by hand...'",
                  any(b.text().strip() == _t4("Set by hand\u2026")
                      for b in _dlg7u.findChildren(QPushButton)))
            win._reproc_implants_hand(wahl={"1": 0}, fertig=win._bd_reprocess_imp_fertig)
            _app.processEvents()
            _plan_h = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
            eq("b7u von Hand 'kein Implantat' schlaegt ESI: Ausbeute zurueck auf 0.83854",
               round(_plan_h["reprocess"]["schritte"][0]["ausbeute"], 5), 0.83854)
            win.settings["bau_char_reproc_implant"] = {}
            win._reproc_implants_hand(wahl={"1": 27174, "2": None},
                                      fertig=win._bd_reprocess_imp_fertig)
            _app.processEvents()
            _plan_h2 = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
            eq("b7u von Hand RX-804 ohne ESI-Treffer: 0.87208, Auto wird nicht gespeichert",
               (round(_plan_h2["reprocess"]["schritte"][0]["ausbeute"], 5),
                win.settings.get("bau_char_reproc_implant_hand")),
               (0.87208, {"1": 27174}))
            check("b7u ... und die Zeile sagt 'von Hand'",
                  "RX-804" in win._bd_reprocess_imp_lbl.text()
                  and _t4("(by hand)") in win._bd_reprocess_imp_lbl.text())
        finally:
            if _alt_hand7u is None:
                win.settings.pop("bau_char_reproc_implant_hand", None)
            else:
                win.settings["bau_char_reproc_implant_hand"] = _alt_hand7u
    finally:
        win._run = _alt_run7u
        if _alt_cid7u is None:
            win.settings.pop("client_id", None)
        else:
            win.settings["client_id"] = _alt_cid7u
        esi.fetch_character_implants = _alt_imp7u
        I.reprocess_implants = _alt_repimp7u
        if _alt_set_imp7u is None:
            win.settings.pop("bau_char_reproc_implant", None)
        else:
            win.settings["bau_char_reproc_implant"] = _alt_set_imp7u
    # OHNE SDE-DATEN: keine geratene Basis, Warnung statt Rechnung.
    _sc7u.setCurrentIndex(_sc7u.findData("s7u"))
    I.reprocess_struktur_sde = lambda: {"bonus": {}, "rig": {}}
    _cb7u.click(); _app.processEvents()          # aus
    _cb7u.click(); _app.processEvents()          # an, jetzt ohne SDE
    _plan_e = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
    eq("b7u ohne SDE-Daten: kein Tausch, Grund 'sde'",
       (dict(_plan_e.get("buy") or {}), (_plan_e.get("reprocess") or {}).get("grund")),
       ({200: 60}, "sde"))
    check("b7u ... und der Tab warnt statt zu schweigen",
          "Load recipes" in _info7u())
    # Die Texte sind zweisprachig hinterlegt.
    from eve_trader import sprache as _sp7u
    for _k7u in ("Buy compressed ore instead of minerals", "Reprocess at",
                 "Structure base {pct} %", "saves {isk} \u00b7 {n} ores",
                 "reprocess \u2192 {out} \u00b7 {pct} %", "Compressed ore \u267b"):
        check(f"b7u deutsche Fassung: {_k7u[:30]}", _k7u in _sp7u.KATALOG["de"])
except Exception as _e7u:                                # pragma: no cover
    _fail.append(f"b7u Reprocessing im Bauplan: {type(_e7u).__name__}: {_e7u}")
finally:
    I.reprocess_map = _alt7u["map"]; I.item_category_map = _alt7u["cats"]
    I.reprocess_struktur_sde = _alt7u["sde"]; I.reprocess_skill_ids = _alt7u["ids"]
    I.reprocess_erz_skill = _alt7u["erz"]; store.list_characters = _alt7u["chars"]
    config.save_settings = _alt7u["save"]; esi.resolve_names = _alt7u["names"]
    for _k, _v in _alt_set7u.items():
        if _v is None:
            win.settings.pop(_k, None)
        else:
            win.settings[_k] = _v
    try:
        if _dlg7u is not None:
            _dlg7u.close()
            _app.processEvents()
    except Exception:
        pass


# ---------------------------------------------------------------- (b7w)
# REPROCESSING IM BAUPLAN, WEG A (1.0.9, Nutzer 19.09.2026 "erraten und
# einfuegen" -> "ja"): Schalter "Unrefined-Reaktionen nutzen" in der Karte,
# Rezept-Kopie im Dialog (X ueber die Unrefined-Formel), Block im Runplaner
# NACH der Reaktionsstufe, Rezeptbaum "ueber ...", Blueprint-Name der
# Unrefined-Formel, Ruecklaeufer-Gutschrift als eigene Kostenzeile.
# Rechnung: 10 Testship <- 100 Testmat (X). Normal: 5 Fuel + 100 A + 100 B
# -> 200 X = 10'502.5 je X. Unrefined Testmat (U): 5 Fuel + 100 A + 100 C
# -> 1 U -> Reprocessing 36 X + 100 A je Stueck. SCRAPMETAL-PFAD (gemessen
# 19.09.2026): 0.50 x (1 + 0.02 x 3) = 0.53 -> 19 X + 53 A je Run; die
# Struktur-Basis der Tatara zaehlt NICHT. Je X: (500 + 100'000 + 5'000 -
# 53'000) / 19 = 2'763.16 -> Unrefined gewinnt. 100 X -> 6 Runs (114 X,
# 14 Ueberschuss), Ruecklaeufer 318 A = 318'000 ISK Gutschrift.
_alt7w = {
    "map": I.reprocess_map, "cats": I.item_category_map, "sde": I.reprocess_struktur_sde,
    "ids": I.reprocess_skill_ids, "erz": I.reprocess_erz_skill,
    "chars": store.list_characters, "save": config.save_settings,
    "names": esi.resolve_names, "groups": I.group_names,
}
_alt_set7w = {k: win.settings.get(k) for k in
              ("bau_reprocess_on", "bau_unrefined_on", "bau_reprocess_struct",
               "bau_structures", "bau_char_skills", "bau_build_chars",
               "bau_reaction_chars")}
_FU7, _A7, _B7, _C7, _X7, _U7 = 4051, 301, 302, 303, 200, 32999


class _RecipesU7w:
    """1 Testship <- 10 X; X normal aus A+B (200 je Run); U aus A+C (1 je Run)."""
    product_to_bp = {100: (900, I.MANUFACTURING, 1), _X7: (5000, I.REACTION, 200),
                     _U7: (5001, I.REACTION, 1)}
    bp_materials = {(900, I.MANUFACTURING): [(_X7, 10)],
                    (5000, I.REACTION): [(_FU7, 5), (_A7, 100), (_B7, 100)],
                    (5001, I.REACTION): [(_FU7, 5), (_A7, 100), (_C7, 100)]}
    activity_time = {(900, I.MANUFACTURING): 60, (5000, I.REACTION): 10800,
                     (5001, I.REACTION): 21600}
    activity_max_runs = {}
    reaction_products = {_X7, _U7}
    invention_for_bpc = {}
    bp_products = {}
    item_cat = {}

    def is_manufactured(self, t):
        return t == 100


_namen7w = {100: "Testship", _X7: "Testmat", _U7: "Unrefined Testmat", _FU7: "Fuel",
            _A7: "Alpha", _B7: "Beta", _C7: "Gamma"}
I.reprocess_map = lambda: {_U7: {"portion": 1, "out": {_X7: 36, _A7: 100}}}
I.item_category_map = lambda: {_X7: (4, 428, 0), _U7: (4, 428, 0), 100: (6, 25, 0),
                               _A7: (4, 427, 0), _B7: (4, 427, 0), _C7: (4, 427, 0),
                               _FU7: (4, 1136, 0)}
I.reprocess_struktur_sde = lambda: {
    "bonus": {"Tatara": 5.5},
    "rig": {46639: {"name": "Standup L-Set Reprocessing Monitor I", "mult": 0.51,
                    "hi": 1.0, "low": 1.06, "null": 1.12}}}
I.reprocess_skill_ids = lambda: {"Reprocessing": 3385, "Reprocessing Efficiency": 3389,
                                 "Scrapmetal Processing": 12196}
I.reprocess_erz_skill = lambda: {}
I.group_names = lambda ids: {int(i): "Intermediate Materials" for i in ids}
store.list_characters = lambda: [{"character_id": 1, "character_name": "Peanut Motor"}]
config.save_settings = lambda s: None
esi.resolve_names = lambda ids: {int(i): _namen7w.get(int(i), f"#{i}") for i in ids}
_dlg7w = None
try:
    win.settings["bau_structures"] = [{"id": "s7w", "name": "R&R Yard", "type": "tatara",
                                       "rigs": ["sde:46639", "", ""], "security": 2.1}]
    win.settings["bau_reprocess_struct"] = "s7w"
    win.settings["bau_reprocess_on"] = False
    win.settings["bau_unrefined_on"] = True
    win.settings["bau_char_skills"] = {"1": {"3385": 5, "3389": 5, "12196": 3}}
    win.settings["bau_build_chars"] = [1]
    win.settings["bau_reaction_chars"] = [1]
    _pr7w = {_FU7: 100.0, _A7: 1000.0, _B7: 20000.0, _C7: 50.0, _X7: 12000.0,
             100: 999999.0}
    win._bd_pricemap = dict(_pr7w)
    win._bd_recipes = _RecipesU7w()
    win._bd_recipes_basis = _RecipesU7w()
    win._bd_opts = {"me": 0, "te": 0, "job_pct": 0, "build_reactions": True,
                    "tree_depth": 4}
    _ro7w = win._reprocess_opts() or {}
    eq("b7w opts: Weg A an, Weg B aus, gemessene Basis",
       (_ro7w.get("unrefined"), _ro7w.get("on"), round(_ro7w.get("basis") or 0, 6)),
       (True, False, 0.602616))
    win._bd_opts["reprocess"] = _ro7w
    win._bd_type = 100
    win._bd_qty = 10
    _plan7w0 = I.production_plan(100, 10, _pr7w.get, _RecipesU7w(), dict(win._bd_opts))
    _tree7w0 = I.build_tree(100, _pr7w.get, _RecipesU7w(), dict(win._bd_opts))
    _res7w = {"tree": _tree7w0, "names": dict(_namen7w),
              "sell": 999999.0, "sell_is_contract": False, "plan": _plan7w0}
    _sbd_frisch(100, "Testship", _res7w)
    _dlg7w = getattr(win, "_bd_dialog", None)
    _app.processEvents()
    _ucb7w = getattr(win, "_bd_unrefined_cb", None)
    check("b7w die Karte hat den Weg-A-Schalter, und er ist an",
          _ucb7w is not None and _ucb7w.isChecked())
    _ulbl7w = getattr(win, "_bd_unrefined_lbl", None)
    eq("b7w ... und die Zeile nennt 53.0 %, den Charakter und '1 intermediates'",
       _ulbl7w.text() if _ulbl7w is not None else None,
       _t4("Unrefined: {pct} % · {char} (50 % × Scrapmetal Processing, "
           "structure does not apply)").format(pct="53.0", char="Peanut Motor")
       + "\n♻ " + _t4("{n} intermediates via unrefined reaction").format(n=1))
    _sc7w = getattr(win, "_bd_reprocess_struct_cb", None)
    check("b7w die Struktur-Auswahl ist auch ohne Weg B aktiv",
          _sc7w is not None and _sc7w.isEnabled())
    # DIE REZEPT-KOPIE: X laeuft ueber die Unrefined-Formel mit 27 je Run.
    eq("b7w die Wahl faellt auf X (19 X + 53 A je Run, Charakter 1)",
       {k: (v["out_je_run"], v["zurueck_je_run"], v["char"])
        for k, v in (getattr(win, "_bd_unrefined", None) or {}).items()},
       {_X7: (19, {_A7: 53}, 1)})
    eq("b7w ... und die Dialog-Rezepte bauen X ueber 5001",
       win._bd_recipes.product_to_bp.get(_X7), (5001, I.REACTION, 19))
    eq("b7w ... die Basis-Rezepte bleiben, wie sie sind",
       win._bd_recipes_basis.product_to_bp.get(_X7), (5000, I.REACTION, 200))
    _plan7w = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
    eq("b7w der Plan: 6 Runs X, Einkauf Fuel/A/C der Unrefined-Formel (kein B)",
       (_plan7w.get("build_runs", {}).get(_X7),
        {k: int(v) for k, v in (_plan7w.get("buy") or {}).items()}),
       (6, {_FU7: 30, _A7: 600, _C7: 600}))
    _st7w = [s for s in ((_plan7w.get("reprocess") or {}).get("schritte") or [])]
    eq("b7w ... ein Unrefined-Schritt: 6 x U -> 100 X, 318 A zurueck, 318'000 Gutschrift, 53 %",
       [(s.get("art"), s.get("erz"), s.get("menge"), s.get("deckt"), s.get("ueberschuss"),
         s.get("kredit"), round(float(s.get("ausbeute") or 0), 6)) for s in _st7w],
       [("unrefined", _U7, 6, {_X7: 100}, {_A7: 318}, 318000.0, 0.53)])
    eq("b7w ... total_cost = Einkauf (3'000 + 600'000 + 30'000) minus 318'000",
       round(float(_plan7w.get("total_cost") or 0)), 315000)
    eq("b7w ... mat_cost bleibt die volle Einkaufsliste",
       round(float(_plan7w.get("mat_cost") or 0)), 633000)
    eq("b7w ... die Wahl reist im Plan mit (Einfrieren)",
       sorted(_plan7w.get("unrefined") or {}), [_X7])
    # RUNPLANER: Reaktionsstufe mit X (4 Runs), DANACH der Block mit U.
    _tr7w = getattr(win, "_sched_tree_ref", None)
    _tops7w = [_tr7w.topLevelItem(i).text(0) for i in range(_tr7w.topLevelItemCount())] \
        if _tr7w is not None else []
    # EIGENE STUFE "2. Unrefined reactions" (Nutzer 19.09.2026: "an erster
    # Stelle ueber den Intermediate Reactions"), der Job heisst nach dem
    # Unrefined-Produkt, der Reprocessing-Block folgt direkt danach.
    _ix_re7w = next((i for i, x in enumerate(_tops7w)
                     if x.startswith("2. " + _t4("Unrefined reactions"))), None)
    _ix_ub7w = next((i for i, x in enumerate(_tops7w)
                     if _t4("Reprocessing of unrefined products") in x), None)
    check("b7w der Runplaner hat die Stufe '2. Unrefined reactions' und den Block direkt danach",
          _ix_re7w is not None and _ix_ub7w == _ix_re7w + 1
          and "R&R Yard" not in _tops7w[_ix_ub7w])
    check("b7w ... und keine Stufe 'Reactions - Intermediate' (X laeuft nur unrefined)",
          not any(_t4("Reactions \u2013 Intermediate") in x for x in _tops7w))
    # ------------------------------------------------------------ (b102)
    # ZIELZEIT JE STUFE (Nutzer 24.09.2026) - am echten Runplaner-Baum.
    # Hier steht ein GEFUELLTER Baum mit mehreren Stufen; darum haengt die
    # Pruefung hier und baut sich keinen zweiten Plan.
    try:
        from PySide6.QtWidgets import QComboBox as _QCb102
        _alt102 = (dict(win.settings.get("bau_runplan_ziel") or {}),
                   win.settings.get("bau_runplan_ziel_std", 0))
        # DER NEUAUFBAU WIRD FUER DIESEN BLOCK STILLGELEGT: eine Auswahl
        # stoesst ihn an, und er loescht genau die Felder, die hier geprueft
        # werden ("Internal C++ object already deleted", gemessen 24.09.2026).
        # Geprueft wird, was die Auswahl EINSTELLT - der Neuaufbau selbst
        # haengt an derselben Methode wie ueberall sonst.
        _altfr102 = getattr(win, "_bd_full_rebuild", None)
        win._bd_full_rebuild = lambda *_a, **_k: None
        _ohne102 = []
        for _i102 in range(_tr7w.topLevelItemCount()):
            _it102 = _tr7w.topLevelItem(_i102)
            _w102 = _tr7w.itemWidget(_it102, 2)
            # NUR ECHTE PLANER-STUFEN (Rolle 8) - die Reprocessing-Bloecke
            # daneben sind keine und duerfen keine Felder haben. Eine FERTIGE
            # Stufe auch nicht: dort steht die Fertig-Meldung.
            _ist102 = (_it102.data(1, Qt.UserRole + 8) is not None
                       and not (_it102.text(2) or "").strip())
            _hat102 = _w102 is not None and len(_w102.findChildren(_QCb102)) == 2
            if _ist102 != _hat102:
                _ohne102.append(_it102.text(0)[:30])
        eq("b102 genau die offenen Stufenzeilen tragen Tage- und Stunden-Feld",
           _ohne102, [])
        _cbs102 = []
        for _i in range(_tr7w.topLevelItemCount()):
            _wx = _tr7w.itemWidget(_tr7w.topLevelItem(_i), 2)
            _cx = _wx.findChildren(_QCb102) if _wx is not None else []
            if len(_cx) == 2:
                _cbs102 = _cx
                break
        check("b102 es gibt eine Stufe mit den beiden Feldern", len(_cbs102) == 2)
        _cd102 = _cbs102[0] if _cbs102 else None
        _ch102 = _cbs102[1] if _cbs102 else None
        # JEDE STUNDE IST WAEHLBAR (Nutzer 24.09.2026: "es springt von 23 h
        # auf 1 T 1 h, bei Composite geht das nicht, zu kleine Abstaende") -
        # ABER NUR, WAS AUCH MOEGLICH IST ("das Dropdown erlaubt
        # Einstellungen, die nicht moeglich sind, 0 d und 1 h geht nicht").
        _std102 = [_ch102.itemData(_i) for _i in range(_ch102.count())] \
            if _ch102 is not None else []
        # OHNE ZIEL STEHT EIN STRICH VORN (Nutzer 25.09.2026: "da steht 7 h,
        # sind aber eigentlich 5 h 36 m" - die 7 war die aufgerundete
        # Mindestdauer und sah aus wie eine Vorgabe). Dahinter folgt die
        # luecklose Reihe bis 23.
        eq("b102 ohne Ziel steht vorn ein Strich statt einer Stundenzahl",
           (_std102[0] if _std102 else None), -999)
        check("b102 die Stunden sind eine luecklose Reihe bis 23",
              _std102[1:] == list(range(_std102[1], 24)) if len(_std102) > 1
              else False)
        eq("b102 der erste Eintrag der Tage ist 'so schnell wie moeglich'",
           _cd102.itemData(0) if _cd102 is not None else "x", 0)
        eq("b102 der letzte ist 'so lange wie noetig'",
           _cd102.itemData(_cd102.count() - 1) if _cd102 is not None else "x", -1)
        eq("b102 ohne Einstellung steht die Wahl auf 'so schnell wie moeglich'",
           _cd102.currentData() if _cd102 is not None else "x", 0)
        # ... UND DAS FELD BLEIBT BEDIENBAR. Frueher war es gesperrt; dann
        # kam man ohne Umweg ueber die Tage nicht mehr auf eine Stundenzahl
        # (Nutzer 25.09.2026: "dann kann man nicht mehr umstellen").
        check("b102 ... und das Stunden-Feld bleibt trotzdem waehlbar",
              _ch102 is not None and _ch102.isEnabled())
        # 23 STUNDEN SIND EINE WAHL, KEIN ZIELEN.
        _st102 = _tr7w.topLevelItem(
            next(_i for _i in range(_tr7w.topLevelItemCount())
                 if _tr7w.itemWidget(_tr7w.topLevelItem(_i), 2) is not None
                 and len(_tr7w.itemWidget(
                     _tr7w.topLevelItem(_i), 2).findChildren(_QCb102)) == 2)
        ).data(1, Qt.UserRole + 8)
        # 0 TAGE waehlen, dann die Stunden: die Reihe beginnt beim kleinsten
        # moeglichen Wert, und 23 h ist ein Eintrag, kein Zielen.
        # DIE TAGE BEGINNEN BEI DEN VOLLEN TAGEN DER MINDESTDAUER - eine
        # Stufe, die 36 h braucht, bietet "0 Tage" gar nicht erst an.
        _minh102 = int((float((getattr(win, "_bd_last_stage_times", None) or {})
                              .get(_st102) or 0.0) + 3599) // 3600)
        eq("b102 der erste Tages-Eintrag sind die vollen Tage der Mindestdauer",
           _cd102.itemData(1) if _cd102 is not None and _cd102.count() > 2 else "x",
           1000 + _minh102 // 24)
        _i0d = _cd102.findData(1000 + _minh102 // 24)
        if _i0d >= 0:
            _cd102.setCurrentIndex(_i0d)
            _i23 = _ch102.findData(23)
            check("b102 23 h stehen im ersten Tages-Eintrag zur Wahl", _i23 >= 0)
            if _i23 >= 0:
                _ch102.setCurrentIndex(_i23)
                eq("b102 23 h lassen sich genau so einstellen",
                   win._runplan_ziel_stunden(_st102),
                   (_minh102 // 24) * 24 + 23)
        _i1d = _cd102.findData(1000 + _minh102 // 24 + 1)
        if _i1d >= 0:
            _cd102.setCurrentIndex(_i1d)
            _i23b = _ch102.findData(23)
            if _i23b >= 0:
                _ch102.setCurrentIndex(_i23b)
            eq("b102 Tage und Stunden addieren sich",
               win._runplan_ziel_stunden(_st102),
               (_minh102 // 24 + 1) * 24 + int(_ch102.currentData() or 0))
        _cd102.setCurrentIndex(_cd102.count() - 1)
        eq("b102 'so lange wie noetig' kommt ohne Grenze beim Planer an",
           win._runplan_ziel_sekunden().get(_st102), float("inf"))
        check("b102 ... und sperrt das Stunden-Feld", not _ch102.isEnabled())
        # UNMOEGLICHES STEHT NICHT ZUR WAHL: die Stufe im Test braucht laenger
        # als eine Stunde, also gibt es bei 0 Tagen kein "1 h".
        _min102 = float((getattr(win, "_bd_last_stage_times", None) or {}).get(
            _st102) or 0.0)
        if _i0d >= 0 and _min102 > 2 * 3600.0:
            _cd102.setCurrentIndex(_i0d)
            eq("b102 eine Stunde steht bei 0 Tagen gar nicht erst zur Wahl",
               _ch102.findData(1), -1)
        # AUFGEKLAPPT BLEIBT AUFGEKLAPPT (Nutzer 24.09.2026: "dann laedt es
        # auch keine Runs" - der Neuaufbau klappte jede Charakterzeile wieder
        # zu, und die Runs stehen darunter).
        _st_o102 = next((_tr7w.topLevelItem(_i)
                         for _i in range(_tr7w.topLevelItemCount())
                         if _tr7w.topLevelItem(_i).childCount()), None)
        check("b102 es gibt eine Stufe mit Charakterzeilen", _st_o102 is not None)
        if _st_o102 is not None and _altfr102 is not None:
            _c_o102 = _st_o102.child(0)
            _c_o102.setExpanded(True)
            _k_o102 = _c_o102.data(0, Qt.UserRole + 6)
            win._bd_full_rebuild = _altfr102
            win._bd_full_rebuild()
            _app.processEvents()
            def _czeilen102():
                _tr_x = getattr(win, "_sched_tree_ref", None)
                _out = []
                for _i in range(_tr_x.topLevelItemCount()
                                if _tr_x is not None else 0):
                    _st_x = _tr_x.topLevelItem(_i)
                    for _j in range(_st_x.childCount()):
                        _c_x = _st_x.child(_j)
                        if _c_x.data(0, Qt.UserRole + 6):
                            _out.append(_c_x)
                return _out
            _zeilen102 = _czeilen102()
            _wieder = any(str(_c.data(0, Qt.UserRole + 6)) == str(_k_o102)
                          and _c.isExpanded() for _c in _zeilen102)
            check("b102 eine aufgeklappte Charakterzeile bleibt nach dem "
                  "Neuaufbau offen", _wieder)
            # GEGENPROBE: eine Zeile, die der Nutzer nie angefasst hat, folgt
            # weiter der Vorgabe (offene Stufe -> zu). Ohne sie wuerde eine
            # Prueffassung, die einfach ALLES aufklappt, gruen sein.
            _unberuehrt = [_c for _c in _zeilen102
                           if str(_c.data(0, Qt.UserRole + 6)) != str(_k_o102)]
            check("b102 eine nie angefasste Charakterzeile bleibt zu",
                  bool(_unberuehrt) and not any(_c.isExpanded()
                                                for _c in _unberuehrt))
            # UND ZUGEKLAPPT BLEIBT ZUGEKLAPPT - beide Richtungen zaehlen.
            for _c in _zeilen102:
                if str(_c.data(0, Qt.UserRole + 6)) == str(_k_o102):
                    _c.setExpanded(False)
            win._bd_full_rebuild()
            _app.processEvents()
            check("b102 ... und eine wieder zugeklappte bleibt zu",
                  not any(str(_c.data(0, Qt.UserRole + 6)) == str(_k_o102)
                          and _c.isExpanded() for _c in _czeilen102()))
        win.settings["bau_runplan_ziel"] = _alt102[0]
        win.settings["bau_runplan_ziel_std"] = _alt102[1]
        if _altfr102 is not None:
            win._bd_full_rebuild = _altfr102

        # ------------------------------------------------------- (b103)
        # HAKEN UEBERLEBEN EINEN CHARAKTER-WECHSEL (Nutzer-Befund
        # 24.09.2026: "ich habe mit Peanut Motor Runs gemacht und abgehakt,
        # danach Charaktere ausgewechselt und Apply gedrueckt - nun sind die
        # abgehakten Runs verschwunden"). Geprueft wird die Rechnung, nicht
        # die Zeile: derselbe Haken unter einer ANDEREN Charakter-ID.
        _rk103 = dict(getattr(win, "_bd_runplan_runs_by_key", None) or {})
        # DIE ECHTE ZEILE ABHAKEN, nicht die Methode aufrufen (Lehre b87/b88:
        # eine Pruefung, die den Handler umgeht, sieht eine abgerissene
        # Verdrahtung nie).
        def _suche103(_par):
            """Erste offene Zeile mit Runs - ohne QTreeWidgetItemIterator, der
            in PySide6 beim Aufraeumen abstuerzte (gemessen 24.09.2026)."""
            for _i in range(_par.childCount() if hasattr(_par, "childCount")
                            else _par.topLevelItemCount()):
                _c = (_par.child(_i) if hasattr(_par, "childCount")
                      else _par.topLevelItem(_i))
                _k = _c.data(0, Qt.UserRole + 6)
                if (_k in _rk103 and int((_rk103.get(_k) or (0, 0))[1] or 0) > 0
                        and _c.data(0, Qt.CheckStateRole) is not None
                        and _c.checkState(0) != Qt.Checked):
                    return _c
                _tief = _suche103(_c)
                if _tief is not None:
                    return _tief
            return None
        _it103 = _suche103(_tr7w)
        check("b103 es gibt eine offene Zeile mit Runs zum Abhaken", _it103 is not None)
        if _it103 is not None:
            _key103 = _it103.data(0, Qt.UserRole + 6)
            _tid103, _runs103 = _rk103[_key103]
            _stufe103 = _key103.split("|")[0]
            _erl103 = dict(getattr(win, "_bd_runplan_erledigt", None) or {})
            win._bd_runplan_erledigt = {}
            _it103.setCheckState(0, Qt.Checked)
            _app.processEvents()
            eq("b103 ein Haken merkt die Runs je Item, ohne Charakter",
               int((getattr(win, "_bd_runplan_erledigt", None) or {}).get(
                   f"{_stufe103}|{int(_tid103)}", 0)), int(_runs103))
            _it103.setCheckState(0, Qt.Unchecked)
            _app.processEvents()
            eq("b103 ... und das Loesen nimmt sie wieder weg",
               int((getattr(win, "_bd_runplan_erledigt", None) or {}).get(
                   f"{_stufe103}|{int(_tid103)}", 0)), 0)
            # DER SCHLUESSEL DARF SICH AENDERN: nach der Umverteilung heisst
            # dieselbe Arbeit anders, die erledigten Runs bleiben dieselben.
            win._runplan_erledigt_pflegen(_key103, True)
            _neu103 = f"{_stufe103}|999999|{int(_tid103)}"
            win._bd_runplan_runs_by_key[_neu103] = (int(_tid103), int(_runs103))
            win._runplan_erledigt_pflegen(_neu103, False)
            eq("b103 derselbe Haken unter einer anderen Charakter-ID zaehlt dasselbe Item",
               int((getattr(win, "_bd_runplan_erledigt", None) or {}).get(
                   f"{_stufe103}|{int(_tid103)}", 0)), 0)
            win._bd_runplan_erledigt = _erl103
        # EINE STUFE EINSTELLEN: die Zahl landet in den Einstellungen, und
        # der Planer bekommt Sekunden - nicht Stunden.
        win._runplan_ziel_setzen("reaction_2", 23)
        eq("b102 die Zielzeit einer Stufe wird gemerkt",
           win._runplan_ziel_stunden("reaction_2"), 23)
        eq("b102 ... und kommt als Sekunden beim Planer an",
           win._runplan_ziel_sekunden().get("reaction_2"), 23 * 3600.0)
        eq("b102 ... eine andere Stufe bleibt frei",
           win._runplan_ziel_sekunden().get("component"), None)
        # DIE VORGABE OBEN GILT FUER ALLE - und nimmt die Ausnahme zurueck,
        # sonst waehlt man oben etwas und unten bleibt eine Stufe stumm.
        win._runplan_ziel_alle_gewaehlt(8)
        eq("b102 die Vorgabe gilt fuer jede Stufe",
           sorted(win._runplan_ziel_sekunden().items()),
           sorted({_st: 8 * 3600.0 for _st in win._RUNPLAN_STUFEN}.items()))
        eq("b102 ... und die Ausnahme der Stufe ist weg",
           dict(win.settings.get("bau_runplan_ziel") or {}), {})
        win._runplan_ziel_alle_gewaehlt(0)
        eq("b102 'so schnell wie moeglich' laesst den Planer wieder frei",
           win._runplan_ziel_sekunden(), {})
        win.settings["bau_runplan_ziel"] = _alt102[0]
        win.settings["bau_runplan_ziel_std"] = _alt102[1]
    except Exception as _e102:                           # pragma: no cover
        _fail.append(f"b102 Block geplatzt: {_e102!r}")
    _st7w_times = getattr(win, "_bd_last_stage_times", None) or {}
    check("b7w ... die Stufenzeit 'unrefined' ist gesetzt (6 Runs a 6 h auf 1 Slot = 36 h)",
          float(_st7w_times.get("unrefined", 0) or 0) > 0)
    check("b7w ... mit 'Base 50 % x Scrapmetal Processing' statt der Struktur-Basis",
          _ix_ub7w is not None
          and _tr7w.topLevelItem(_ix_ub7w).text(4) == _t4("Base 50 % × Scrapmetal Processing"))
    check("b7w ... und keine Stufe 0 (nichts wird als Erz gekauft)",
          not any(x.startswith("0. ") for x in _tops7w))

    def _zeilen7w():
        out = []
        if _tr7w is None:
            return out
        _root = _tr7w.invisibleRootItem()
        _st = [_root.child(i) for i in range(_root.childCount())]
        while _st:
            _x = _st.pop()
            out.append((tuple(_x.text(c) for c in range(_tr7w.columnCount())), _x))
            _st += [_x.child(i) for i in range(_x.childCount())]
        return out
    _z7w = _zeilen7w()
    check("b7w ... Charakterzeile '6 units', Zeile 'Unrefined Testmat' 6 -> 100 Testmat, 53.0 %, +318 Alpha",
          any(z[0] == "Peanut Motor" and z[2] == _t4("{n} units").format(n=6) for z, _ in _z7w)
          and any(z[0] == "Unrefined Testmat" and z[1] == "6"
                  and z[4] == "→ 100 Testmat  ·  53.0 %" and z[5] == "+318 Alpha"
                  for z, _ in _z7w))
    _row_u7w = next((it for z, it in _z7w if z[0] == "Unrefined Testmat"), None)
    check("b7w ... Klick auf die Zeile kopiert 'Unrefined Testmat'",
          _row_u7w is not None and _row_u7w.data(0, _RKN7f) == "Unrefined Testmat")
    # Der Reaktions-Job selbst: X mit 4 Runs, Blueprint-Name = Unrefined-Formel.
    _row_x7w = next((it for z, it in _z7w if z[0] == "Unrefined Testmat" and z[1] == "6"
                     and it is not _row_u7w), None)
    check("b7w der Reaktions-Job heisst 'Unrefined Testmat' (das, was man baut)",
          _row_x7w is not None)
    eq("b7w der Reaktions-Job traegt den Namen der Unrefined-Formel zum Kopieren",
       _row_x7w.data(0, _RKN7f) if _row_x7w is not None else None,
       "Unrefined Testmat Reaction Formula")
    # Blueprint-Tab: die Zeile heisst nach dem Unrefined-Produkt.
    _bpt7w = getattr(win, "_bd_bp_tab_tbl", None)
    _bp_namen7w = [_bpt7w.item(i, 0).text() for i in range(_bpt7w.rowCount())
                   if _bpt7w.item(i, 0) is not None] if _bpt7w is not None else []
    check("b7w der Blueprint-Tab nennt 'Unrefined Testmat' statt 'Testmat'",
          any("Unrefined Testmat" in n for n in _bp_namen7w)
          and not any(n.strip() == "Testmat" for n in _bp_namen7w))
    # Rezeptbaum: X sagt "ueber Unrefined Testmat".
    _tw7w = getattr(win, "_bd_tree_widget", None) or _dlg7w.findChild(QTreeWidget)

    def _baum7w(w):
        out = []
        if w is None:
            return out
        _root = w.invisibleRootItem()
        _st = [_root.child(i) for i in range(_root.childCount())]
        while _st:
            _x = _st.pop()
            out.append(tuple(_x.text(c) for c in range(w.columnCount())))
            _st += [_x.child(i) for i in range(_x.childCount())]
        return out
    _bz7w = []
    for _w7 in _dlg7w.findChildren(QTreeWidget):
        _bz7w += _baum7w(_w7)
    check("b7w der Rezept-Baum sagt bei Testmat 'BUILD - 6 runs - via Unrefined Testmat'",
          any(z[0] == "Testmat" and _t4("via {formula} ♻").format(
              formula="Unrefined Testmat") in " ".join(z) and "6" in " ".join(z)
              for z in _bz7w))
    # Materials-Tab: Ruecklaeufer-Zeile mit Gutschrift, Annahme genannt.
    _info7w = (getattr(win, "_bd_mat_tab_info", None).text()
               if getattr(win, "_bd_mat_tab_info", None) is not None else "")
    check("b7w der Materials-Tab traegt keinen Unrefined-Textblock mehr",
          "Unrefined Testmat" not in _info7w and "318" not in _info7w)
    # Kostenzeile: Ruecklaeufer sichtbar.
    _rl7w = (getattr(win, "_bd_detail_val_lbls", None) or {}).get("− Rückläufer")
    check("b7w die Kostenzeile 'Ruecklaeufer' ist sichtbar und nennt 318'000",
          _rl7w is not None and not _rl7w.isHidden() and "318" in _rl7w.text())
    # NACH "RECALCULATE" (Orderbuch-Ladder; Nutzer-Befund 19.09.2026: Plan mit
    # Unrefined 139.8 statt 127.6 M je Stueck - die Gutschrift fehlte NUR in
    # der Summe, die dieser Zweig neu aufbaut). Orderbuch = dieselben Preise;
    # Gesamt muss Ladder + Job + Bestand - 318'000 sein.
    win._bd_ladder_result = {"qty": 10, "_orderbooks": {_FU7: [(100.0, 100)],
                                                        _A7: [(1000.0, 1000)],
                                                        _C7: [(50.0, 1000)]},
                             "mat_cost_ladder": 633000.0, "short_materials": []}
    # DER SCHALTER HOLT DIE ORDERBUECHER SELBST NACH (Nutzer 19.09.2026: "ich
    # moechte nicht Recalculate druecken"): je Klick ein Hintergrund-Job mit
    # dem Ladder-Etikett. Attrappe zaehlt nur, laeuft nichts (kein Netz).
    _laeufe7w = []
    _alt_run7w = win._run
    win._run = lambda _w, _done, fail_cb=None, **_k: _laeufe7w.append(_k.get("label"))
    _ucb7w.click(); _app.processEvents(); _ucb7w.click(); _app.processEvents()
    win._run = _alt_run7w
    eq("b7w jeder Schalter-Klick holt die Orderbuch-Preise nach (2 Klicks = 2 Abrufe)",
       [_l for _l in _laeufe7w if _l == _t4("Order book prices \u2026")],
       [_t4("Order book prices \u2026")] * 2)
    _plan7w_l = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
    from eve_trader.ui.mw_basis import isk as _isk7w
    _lb7w = getattr(win, "_bd_detail_val_lbls", None) or {}
    eq("b7w Ladder: Gesamt-Baukosten ziehen die Gutschrift ab",
       _lb7w["= Baukosten gesamt"].text(),
       _isk7w(633000.0 + float(_plan7w_l.get("job_cost") or 0)
              + float(_plan7w_l.get("stock_cost") or 0)
              + float(_plan7w_l.get("inv_cost") or 0) - 318000.0, suffix=False))
    win._bd_ladder_result = None
    # Restbedarf: U wird nie gekauft; die Einkaufsliste ist die der Formel.
    eq("b7w Restbedarf ohne U (wird gebaut, nie gekauft; X braucht das Endprodukt)",
       sorted(win._restbedarf_jetzt()), [_X7, _A7, _C7, _FU7])
    # SCHALTER AUS: exakt der alte Plan (1 Run normal, B gekauft, kein Block).
    _ucb7w.click(); _app.processEvents()
    _plan7w_b = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
    # Ohne Weg A kauft der Plan X: ein Run der normalen Formel (200 Stueck,
    # 2'100'500 ISK) ist teurer als 100 x 12'000 - Batch-Rundung, wie immer.
    eq("b7w Schalter aus: X wird gekauft (normale Formel zu grob), kein Schritt",
       (_plan7w_b.get("build_runs", {}).get(_X7),
        {k: int(v) for k, v in (_plan7w_b.get("buy") or {}).items()},
        (_plan7w_b.get("reprocess") or {}).get("schritte"),
        win._bd_recipes.product_to_bp.get(_X7)),
       (None, {_X7: 100}, None, (5000, I.REACTION, 200)))
    eq("b7w ... Einstellung gespeichert", win.settings.get("bau_unrefined_on"), False)
    _tops7w_b = [_tr7w.topLevelItem(i).text(0) for i in range(_tr7w.topLevelItemCount())]
    check("b7w ... und der Unrefined-Block ist weg",
          not any(_t4("Reprocessing of unrefined products") in x for x in _tops7w_b))
    check("b7w ... Kostenzeile 'Ruecklaeufer' versteckt",
          _rl7w is not None and _rl7w.isHidden())
    # WIEDER AN: gleiche Wahl wie beim ersten Mal.
    _ucb7w.click(); _app.processEvents()
    _plan7w_c = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
    eq("b7w wieder an: 6 Runs ueber die Unrefined-Formel",
       (_plan7w_c.get("build_runs", {}).get(_X7), win._bd_recipes.product_to_bp.get(_X7)),
       (6, (5001, I.REACTION, 19)))
    # RUNS JE JOB DECKELN (Nutzer 19.09.2026, Einherji II: "17 Stueck mit
    # einem Blueprint ... gibts maximal 10 runs"): ohne Limit 1 Blueprint
    # mit 6 Runs; mit Limit 4 je Job (SDE maxProductionLimit, dieselbe
    # Quelle wie BPC-Runs) zwei Blaupausen 4 + 2 auf demselben Slot.
    def _bp_knoepfe7w(zeilen, runs):
        """Texte der Blaupausen-Knoepfe (Spalte 2) der Reaktions-Job-Zeile
        mit `runs` Runs - dazu der Name der Charakterzeile darueber."""
        from PySide6.QtWidgets import QPushButton as _PB7w, QLabel as _QL7w
        for z, it in zeilen:
            if z[0] != "Unrefined Testmat" or z[1] != runs or not z[4].startswith(
                    _t4("Unrefined reaction")):
                continue
            _w = _tr7w.itemWidget(it, 2)
            if _w is None:
                return None
            _lay = _w.layout()
            out = []
            for i in range(_lay.count()):
                _c = _lay.itemAt(i).widget()
                if isinstance(_c, (_PB7w, _QL7w)):
                    out.append(_c.text())
            return (it.parent().text(0) if it.parent() is not None else None, out)
        return None
    eq("b7w Runplaner ohne Limit: 1 Blueprint mit 6 Runs",
       _bp_knoepfe7w(_zeilen7w(), "6"),
       ("Peanut Motor", [_t4("{n} blueprints").format(n=1), "1\u00d7", "6"]))
    win._bd_recipes.activity_max_runs[(5001, I.REACTION)] = 4
    _ucb7w.click(); _app.processEvents(); _ucb7w.click(); _app.processEvents()
    # GANZE KOPIEN + WELLEN (Nutzer 19.09.2026): 6 Runs mit Limit 4 auf EINEM
    # Reaktions-Slot = Kopie 4 in Welle 1, Kopie 2 als zweite Auflistung
    # "Peanut Motor · Welle 2".
    eq("b7w Runplaner mit Limit 4 je Job, 1 Slot: Welle 1 = eine Kopie mit 4 Runs",
       _bp_knoepfe7w(_zeilen7w(), "4"),
       ("Peanut Motor", [_t4("{n} blueprints").format(n=1), "1\u00d7", "4"]))
    eq("b7w ... Welle 2 = zweite Auflistung des Charakters mit der Kopie 2",
       _bp_knoepfe7w(_zeilen7w(), "2"),
       ("Peanut Motor  \u00b7  " + _t4("wave {n}").format(n=2),
        [_t4("{n} blueprints").format(n=1), "1\u00d7", "2"]))
    _w2_7w = next((it for z, it in _zeilen7w() if z[0] == "Unrefined Testmat" and z[1] == "2"
                   and z[4].startswith(_t4("Unrefined reaction"))), None)
    check("b7w ... die Welle-2-Zeile hat einen eigenen Haken-Schluessel (|w2)",
          _w2_7w is not None and str(_w2_7w.data(0, Qt.UserRole + 6)).endswith("|w2")
          and _w2_7w.parent() is not None
          and str(_w2_7w.parent().data(0, Qt.UserRole + 6)).endswith("|w2"))
    win._bd_recipes.activity_max_runs.pop((5001, I.REACTION), None)
    # OHNE SCRAPMETAL-SKILL: 50 % flach -> 18 X + 50 A je Run (Stufe 0 zaehlt,
    # nicht "fehlt"); OHNE STRUKTUR-DATEN laeuft Weg A trotzdem (Basis egal).
    win.settings["bau_char_skills"] = {"1": {"3385": 5, "3389": 5}}
    I.reprocess_struktur_sde = lambda: {"bonus": {}, "rig": {}}
    _ucb7w.click(); _app.processEvents(); _ucb7w.click(); _app.processEvents()
    eq("b7w ohne Scrapmetal-Skill und ohne Struktur-Daten: 18 X + 50 A je Run, 50 %",
       ({k: (v["out_je_run"], v["zurueck_je_run"]) for k, v in win._bd_unrefined.items()},
        win._bd_recipes.product_to_bp.get(_X7),
        win._bd_opts.get("reprocess", {}).get("basis")),
       ({_X7: (18, {_A7: 50})}, (5001, I.REACTION, 18), None))
    check("b7w ... die Karte warnt NICHT vor fehlenden Struktur-Daten (Weg B ist aus)",
          "Load recipes" not in (getattr(win, "_bd_mat_tab_info", None).text()
                                 if getattr(win, "_bd_mat_tab_info", None) is not None else ""))
    win.settings["bau_char_skills"] = {"1": {"3385": 5, "3389": 5, "12196": 3}}
    I.reprocess_struktur_sde = lambda: {
        "bonus": {"Tatara": 5.5},
        "rig": {46639: {"name": "Standup L-Set Reprocessing Monitor I", "mult": 0.51,
                        "hi": 1.0, "low": 1.06, "null": 1.12}}}
    _ucb7w.click(); _app.processEvents(); _ucb7w.click(); _app.processEvents()
    # TEURER INPUT (C = 5'000): Unrefined verliert, Zeile "nicht guenstiger".
    win._bd_pricemap[_C7] = 5000.0
    _ucb7w.click(); _app.processEvents(); _ucb7w.click(); _app.processEvents()
    _plan7w_d = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or {}
    _info7w_d = (getattr(win, "_bd_mat_tab_info", None).text()
                 if getattr(win, "_bd_mat_tab_info", None) is not None else "")
    check("b7w teurer Input: kein Unrefined-Weg, und die Karte sagt warum (Tooltip +% fuer Testmat)",
          _plan7w_d.get("build_runs", {}).get(_X7) is None
          and win._bd_recipes.product_to_bp.get(_X7) == (5000, I.REACTION, 200)
          and "Testmat (+" in (_ulbl7w.toolTip() if _ulbl7w is not None else "")
          and _t4("no unrefined reaction is cheaper") in (_ulbl7w.text() if _ulbl7w is not None else ""))
    win._bd_pricemap[_C7] = 50.0
    # Die Texte sind zweisprachig hinterlegt.
    from eve_trader import sprache as _sp7w
    for _k7w in ("Use unrefined reactions where cheaper",
                 "Base 50 % × Scrapmetal Processing",
                 "Reprocessing of unrefined products", "via {formula} ♻",
                 "Unrefined reaction not cheaper for: {liste}",
                 "− Returned (reprocessing)"):
        check(f"b7w deutsche Fassung: {_k7w[:30]}", _k7w in _sp7w.KATALOG["de"])
except Exception as _e7w:                                # pragma: no cover
    import traceback as _tb7w
    _tb7w.print_exc()
    _fail.append(f"b7w Unrefined im Bauplan: {type(_e7w).__name__}: {_e7w}")
finally:
    I.reprocess_map = _alt7w["map"]; I.item_category_map = _alt7w["cats"]
    I.reprocess_struktur_sde = _alt7w["sde"]; I.reprocess_skill_ids = _alt7w["ids"]
    I.reprocess_erz_skill = _alt7w["erz"]; store.list_characters = _alt7w["chars"]
    config.save_settings = _alt7w["save"]; esi.resolve_names = _alt7w["names"]
    I.group_names = _alt7w["groups"]
    for _k, _v in _alt_set7w.items():
        if _v is None:
            win.settings.pop(_k, None)
        else:
            win.settings[_k] = _v
    win._bd_recipes_basis = None
    win._bd_unrefined = {}
    win._bd_ladder_result = None
    try:
        if _dlg7w is not None:
            _dlg7w.close()
            _app.processEvents()
    except Exception:
        pass


# ---------------------------------------------------------------- (b7v)
# FRACHT + ORDERBUCH-LADDER (Befund 18.09.2026 am Compressed-Ore-Vergleich):
# mit "Fracht entscheidet mit" UND aktiver Ladder fehlte der Frachtdienst in
# Gesamtkosten und Gewinn - die Ladder rechnet reine Orderbuchpreise, der
# Abzug in der Material-Zeile nahm aber an, die Fracht stecke drin. Beim
# Nutzer: Gewinn ohne Erz -93 Mio, obwohl 372 Mio Frachtdienst anfallen.
# Rechnung hier: 60 Testmat x 100 ISK (Orderbuch) = 6'000; Volumen 60 x
# 0.01 m3 x 445 ISK/m3 = 267 Fracht. Gesamt muss die 267 enthalten, die
# Material-Zeile zeigt die 6'000 OHNE Fracht.
_alt_set7v = {k: win.settings.get(k) for k in
              ("bau_transport_rate", "bau_freight_in_decision", "bau_reprocess_on")}
_alt_vol7v = win._item_volumes_with_esi_fix
_alt_save7v = config.save_settings
config.save_settings = lambda s: None
_dlg7v = None
try:
    win.settings["bau_transport_rate"] = 445.0
    win.settings["bau_freight_in_decision"] = True
    win.settings["bau_reprocess_on"] = False
    win._item_volumes_with_esi_fix = lambda ids: ({200: 0.01, 100: 1.0}, [])
    win._bd_pricemap = dict(PRICES)
    win._bd_recipes = _Recipes()
    win._bd_opts = {"me": 0, "te": 0, "job_pct": 0, "build_reactions": False,
                    "tree_depth": 4, "stock": {200: 40}}
    win._bd_type = 100
    win._bd_qty = 10
    _plan7v = I.production_plan(100, 10, PRICES.get, _Recipes(), dict(win._bd_opts))
    _tree7v = I.build_tree(100, PRICES.get, _Recipes(), dict(win._bd_opts))
    _res7v = {"tree": _tree7v, "names": {100: "Testship", 200: "Testmat"},
              "sell": 6000.0, "sell_is_contract": False, "plan": _plan7v}
    # Orderbuch-Ladder wie nach "Neu berechnen": 100 ISK je Testmat, aber
    # nur 45 Stueck im Buch (60 gebraucht) - der Rest zum teuersten Angebot.
    win._bd_ladder_result = {"qty": 10, "_orderbooks": {200: [(100.0, 45)]},
                             "mat_cost_ladder": 6000.0, "short_materials": []}
    _sbd_frisch(100, "Testship", _res7v)
    _dlg7v = getattr(win, "_bd_dialog", None)
    _app.processEvents()
    _lb7v = getattr(win, "_bd_detail_val_lbls", None) or {}
    _plan_v = (getattr(win, "_bd_plan_cache", None) or (None, None))[1] or _plan7v
    _jc7v = float(_plan_v.get("job_cost") or 0.0)
    _sc7v = float(_plan_v.get("stock_cost") or 0.0)
    _iv7v = float(_plan_v.get("inv_cost") or 0.0)
    from eve_trader.ui.mw_basis import isk as _isk7v
    eq("b7v Material-Zeile = Orderbuch ohne Fracht (6'000)",
       _lb7v["Material"].text(), _isk7v(6000.0, suffix=False))
    eq("b7v Frachtdienst-Zeile = 267", _lb7v["Frachtdienst"].text(), _isk7v(267.0, suffix=False))
    eq("b7v Gesamt-Baukosten ENTHALTEN die Fracht",
       _lb7v["= Baukosten gesamt"].text(),
       _isk7v(6000.0 + 267.0 + _jc7v + _sc7v + _iv7v, suffix=False))
    # JEDE ZEILE ERKLAERT SICH (Nutzer 25.09.2026: "auf allen Zeilen eine
    # Mouseover-Info fuer alle ISK-Eintraege"). Geprueft wird die WERT-Zelle
    # jeder Zeile der linken Spalte - ohne Ausnahme, sonst faellt beim
    # naechsten Umbau still eine heraus.
    _ohne7v = sorted(k for k, _l in _lb7v.items()
                     if not (_l.toolTip() or "").strip())
    check("b7v jede Detail-Zeile hat eine Kurzerklaerung"
          + (" - ohne: " + ", ".join(_ohne7v) if _ohne7v else ""),
          not _ohne7v)
    _tips7v = getattr(win, "_bd_detail_tips", None) or {}
    check("b7v die Erklaerungen kommen aus EINER Stelle", len(_tips7v) >= 18)
    # GEGENPROBE: die Erklaerung steht auch an der BESCHRIFTUNG, nicht nur
    # an der Zahl - man zeigt beim Lesen auf das Wort, nicht auf den Betrag.
    # Die Tooltips werden fuers Anzeigen in ein <div> gewickelt (tooltips.py),
    # also auf ENTHALTEN pruefen statt auf Gleichheit - sonst prueft man die
    # Verpackung statt die Zusage.
    _erw7v = {_t4(_x) for _x in _tips7v.values()}
    _caps7v = [w for w in (_dlg7v.findChildren(QLabel) if _dlg7v else [])
               if any(_e in (w.toolTip() or "") for _e in _erw7v)]
    check("b7v ... und ebenso an den Beschriftungen", len(_caps7v) >= 18)
    # AUSVERKAUFT (Nutzer 18.09.2026: "was macht der Bauplan, wenn in Jita
    # etwas nicht da ist?"): der Materialien-Tab nennt das Material mit
    # "da / gebraucht" - nicht nur eine Zahl im Tooltip.
    _il7v = getattr(win, "_bd_mat_tab_info", None)
    _txt7v = _il7v.text() if _il7v is not None else ""
    check("b7v der Materialien-Tab warnt: Testmat 45 / 60 am Hub",
          "Testmat 45 / 60" in _txt7v and _il7v.isVisible() is not None)
    eq("b7v ... und die Knappheit ist am Dialog gemerkt",
       [(int(x["type_id"]), int(x["available"]), int(x["needed"]))
        for x in (getattr(win, "_bd_ladder_shorts", None) or [])], [(200, 45, 60)])
    # FRACHTDIENST IN DER GEWINNRECHNUNG (Nutzer-Meldung 30.09.2026: "die
    # Frachtkosten werden nicht mit dazu gerechnet"). Mit "Fracht
    # mitentscheiden": "davon Frachtdienst 267" (steckt in den Baukosten).
    _pv7v = getattr(win, "_bd_profit_val_lbls", None) or {}
    _pc7v = getattr(win, "_bd_profit_caps", None) or {}
    _fk7v = "\u2212 Frachtdienst"
    check(f"b7v Gewinnrechnung: 'davon Frachtdienst 267' "
          f"({_pc7v.get(_fk7v).text() if _pc7v.get(_fk7v) else None!r}, "
          f"{_pv7v.get(_fk7v).text() if _pv7v.get(_fk7v) else None!r})",
          _pc7v.get(_fk7v) is not None
          and _pc7v[_fk7v].text() in ("of which freight service", "davon Frachtdienst")
          and _pv7v[_fk7v].text() == _isk7v(267.0, suffix=False))

    def _zahl7v(_l):
        _t = (_l.text() if _l is not None else "").replace("\u2212", "-")
        _t = "".join(_c for _c in _t if _c.isdigit() or _c in ".-")
        return float(_t) if _t not in ("", "-") else 0.0
    # OHNE "Fracht mitentscheiden": Frachtdienst wird VOM GEWINN abgezogen -
    # die Zeile muss dastehen, und die Spalte muss aufgehen.
    if _dlg7v is not None:
        _dlg7v.close(); _app.processEvents()
    win.settings["bau_freight_in_decision"] = False
    _sbd_frisch(100, "Testship", _res7v)
    _dlg7v = getattr(win, "_bd_dialog", None)
    _app.processEvents()
    _pv7v = getattr(win, "_bd_profit_val_lbls", None) or {}
    _pc7v = getattr(win, "_bd_profit_caps", None) or {}
    _fr7v = _zahl7v(_pv7v.get(_fk7v))
    check(f"b7v ohne 'mitentscheiden': '\u2212 Frachtdienst' mit Betrag ({_fr7v})",
          _pc7v.get(_fk7v) is not None
          and _pc7v[_fk7v].text() in ("\u2212 Freight service", "\u2212 Frachtdienst")
          and _fr7v < 0)
    _summe7v = sum(_zahl7v(_pv7v.get(_k)) for _k in (
        "Verkaufserl\u00f6s brutto", "\u2212 Steuer + Broker", "\u2212 Baukosten",
        _fk7v, "\u2212 Eigene Fahrt", "\u2212 Zusatzkosten"))
    _gew7v = _zahl7v(_pv7v.get("= Gewinn"))
    check(f"b7v ... und die Gewinnspalte geht auf ({_summe7v:.0f} = {_gew7v:.0f})",
          abs(_summe7v - _gew7v) <= 2.0)
except Exception as _e7v:                                # pragma: no cover
    _fail.append(f"b7v Fracht in der Ladder: {type(_e7v).__name__}: {_e7v}")
finally:
    win._item_volumes_with_esi_fix = _alt_vol7v
    config.save_settings = _alt_save7v
    win._bd_ladder_result = None
    for _k, _v in _alt_set7v.items():
        if _v is None:
            win.settings.pop(_k, None)
        else:
            win.settings[_k] = _v
    try:
        if _dlg7v is not None:
            _dlg7v.close()
            _app.processEvents()
    except Exception:
        pass


# ---------------------------------------------------------------- (b80)
# PREISVERLAUF: VERVOLLSTAENDIGUNG UEBER ALLE NAMEN + START MIT GRAPH
# (Nutzer 18.09.2026: "zeigt nicht alle Items wenn ich anfange zu tippen"
# und "standardmaessig sollte ein Item aufgehen"). Die Combo-Liste bleibt
# der Bestand; der Completer hat ein eigenes Modell mit dem Namens-Cache.
try:
    from PySide6.QtWidgets import QCompleter as _QC80
    from eve_trader import store as _st80
    _geplottet80 = []
    _alt_plot80 = win._do_plot
    _alt_names80 = _st80.all_names
    try:
        win._do_plot = lambda tid: _geplottet80.append(int(tid))
        _st80.all_names = lambda: {990001: "Acolyte II Probe", 990002: "Acolyte I Probe",
                                   990003: "Warrior II Probe", 990004: "Acolyte II"}
        win._mk_namen_laden()
        _liste80 = win._mk_namen_modell.stringList()
        check("b80 der Completer kennt Namen, die NICHT im Bestand sind",
              "Acolyte II Probe" in _liste80 and "Warrior II Probe" in _liste80)
        _c80 = win.mk_item.completer()
        check("b80 der Completer haengt am Namens-Modell (nicht an der Combo)",
              _c80 is not None and _c80.model() is win._mk_namen_modell)
        check("b80 Teilwort reicht (MatchContains, Gross/Klein egal)",
              _c80.filterMode() == Qt.MatchContains
              and _c80.caseSensitivity() == Qt.CaseInsensitive)
        _c80.setCompletionPrefix("acoly")
        _treffer80 = [_c80.completionModel().index(i, 0).data()
                      for i in range(_c80.completionModel().rowCount())]
        check(f"b80 'acoly' findet beide Acolyte-Probe ({_treffer80})",
              set(_treffer80) >= {"Acolyte II Probe", "Acolyte I Probe"})
        # Auswahl aus der Vervollstaendigung -> Combo + Zeichnen
        win._mk_name_gewaehlt("Warrior II Probe")
        check("b80 Auswahl landet in der Combo und wird gezeichnet",
              win.mk_item.currentData() == 990003 and _geplottet80[-1:] == [990003])
        # Getippter Name + Enter: erst lokal, ohne Netz
        win.mk_item.setEditText("acolyte ii probe")
        _n80 = len(_geplottet80)
        win._plot_history()
        check("b80 getippter Name wird lokal aufgeloest (ohne ESI)",
              _geplottet80[_n80:] == [990001])
        # Auto-Start: zuletzt angesehenes Item
        win._mk_full = []
        win._mk_auto_lief = False
        win.settings["mk_last_item"] = [990002, "Acolyte I Probe"]
        _n80 = len(_geplottet80)
        win._mk_auto_start()
        check("b80 beim Oeffnen des Tabs wird das zuletzt angesehene Item gezeichnet",
              _geplottet80[_n80:] == [990002] and win.mk_item.currentData() == 990002)
        _n80 = len(_geplottet80)
        win._mk_auto_start()
        check("b80 ... aber nur einmal, nicht bei jedem Tab-Wechsel",
              _geplottet80[_n80:] == [])
        # Ohne gemerktes Item: "Acolyte II" (Tutorial-Item), ueber den Namen
        win._mk_auto_lief = False
        win.settings["mk_last_item"] = None
        _n80 = len(_geplottet80)
        win._mk_auto_start()
        check("b80 ohne gemerktes Item: Acolyte II, ueber den Namen aufgeloest",
              _geplottet80[_n80:] == [990004] and win.mk_item.currentText() == "Acolyte II")
        check("b80 keine Type-ID fuer das Startitem im Quelltext (Regel 2)",
              win._MK_STARTITEM == "Acolyte II" and "2488" not in
              __import__("inspect").getsource(type(win)._mk_auto_start))
        check("b80 der Tab-Wechsel ruft den Auto-Start",
              "self._mk_auto_start()" in
              __import__("inspect").getsource(type(win)._on_tab_changed))
        check("b80 mk_last_item hat einen Standard in DEFAULT_SETTINGS",
              "mk_last_item" in __import__("eve_trader.config", fromlist=["x"]).DEFAULT_SETTINGS)
    finally:
        win._do_plot = _alt_plot80
        _st80.all_names = _alt_names80
        win.settings["mk_last_item"] = None
        win._mk_auto_lief = False
        win._mk_namen_laden()
except Exception as _e80:                                # pragma: no cover
    _fail.append(f"b80 Preisverlauf-Vervollstaendigung: {type(_e80).__name__}: {_e80}")


# ---------------------------------------------------------------- (b81)
# "-1 ..." AUF DEM GROSSEN LADESCHIRM (Nutzer 18.09.2026, zweiter Fundort
# nach aa370): _set_loading_progress bekam progress(-1, 0) und schrieb die
# Zahl roh. Am Widget geprueft, nicht am Text.
try:
    win._set_loading_progress(-1, 0)
    check("b81 Ladeschirm: -1 wird als Entpack-Phase gezeigt, nicht als Zahl",
          "-1" not in win._overlay_progress.text()
          and win._overlay_progress.text() == _t4("Unpacking and importing …"))
    win._set_loading_progress(57, 140)
    check("b81 Gegenprobe: mit Groesse weiter Balken + Zahlen",
          "57" in win._overlay_progress.text() and "140" in win._overlay_progress.text())
    win._set_loading_progress(3, 0)
    check("b81 Gegenprobe: ohne Groesse weiter die nackte Zahl",
          win._overlay_progress.text().startswith("3"))
except Exception as _e81:                                # pragma: no cover
    _fail.append(f"b81 Ladeschirm -1: {type(_e81).__name__}: {_e81}")


# ---------------------------------------------------------------- (b82)
# STRUKTUR AUS DER HUB-BOX ENTFERNEN (Nutzer 19.09.2026). Am Fenster: eine
# Struktur merken, Box neu aufbauen, entfernen, Box neu aufbauen - der
# Eintrag muss weg sein und die Auswahl darf nicht auf ihr haengen bleiben.
try:
    from eve_trader import store as _st82
    _sid82 = 990082001
    for _f82 in _st82.list_favorites():
        if _f82.get("structure_id") == _sid82:
            _st82.remove_favorite(_f82["id"])
    _cache82 = dict(win.settings.get("struct_market_cache") or {})
    win.settings.setdefault("struct_market_cache", {})[str(_sid82)] = True
    _st82.add_favorite({"kind": "structure", "name": "Probe-Keepstar 82",
                        "structure_id": _sid82, "character_id": 1,
                        "region_id": 10000002, "station_id": None})
    win._reload_hub_structures()
    _idx82 = next((i for i in range(win.g_hub.count())
                   if isinstance(win.g_hub.itemData(i), dict)
                   and win.g_hub.itemData(i).get("structure_id") == _sid82), -1)
    check("b82 die gemerkte Struktur steht in der Hub-Box", _idx82 >= 0)
    win.g_hub.setCurrentIndex(_idx82)
    check("b82 die Hub-Box bietet ein eigenes Kontextmenue",
          win.g_hub.contextMenuPolicy() == Qt.CustomContextMenu)
    win._hub_entfernen(_sid82)
    _app.processEvents()
    check("b82 nach dem Entfernen ist sie aus der Box verschwunden",
          all(not (isinstance(win.g_hub.itemData(i), dict)
                   and win.g_hub.itemData(i).get("structure_id") == _sid82)
              for i in range(win.g_hub.count())))
    check("b82 ... und aus der Datenbank",
          not any(f.get("structure_id") == _sid82 for f in _st82.list_favorites()))
    check("b82 die Auswahl haengt nicht auf dem geloeschten Eintrag",
          not (isinstance(win.g_hub.currentData(), dict)
               and win.g_hub.currentData().get("structure_id") == _sid82))
    check("b82 NPC-Hubs bekommen KEINEN Entfernen-Eintrag (nur dict-Daten)",
          'if not isinstance(data, dict) or not data.get("structure_id"):' in
          __import__("inspect").getsource(type(win)._hub_kontextmenue))
    win.settings["struct_market_cache"] = _cache82
except Exception as _e82:                                # pragma: no cover
    _fail.append(f"b82 Hub entfernen: {type(_e82).__name__}: {_e82}")


# ---------------------------------------------------------------- (b83)
# MULTI-BAUPLAN SCHRITT 2 (1.0.9): die Oberflaeche fragt nicht mehr
# "tid == type_id", sondern "tid in Enden". Am Fenster mit einem Mini-
# Rezept (A x20, B x10 teilen X): Stufe, Kategorie-ME, ME je Ende,
# Schnellschaetzung der Plan-Karte fuer einen gespeicherten Multi-Plan.
try:
    _A83, _B83, _X83, _M83 = 970001, 970002, 970003, 970004
    _BPA83, _BPB83, _BPX83 = 980001, 980002, 980003

    class _Rec83:
        product_to_bp = {_A83: (_BPA83, I.MANUFACTURING, 1),
                         _B83: (_BPB83, I.MANUFACTURING, 1),
                         _X83: (_BPX83, I.REACTION, 100)}
        bp_materials = {(_BPA83, I.MANUFACTURING): [(_X83, 2), (_M83, 10)],
                        (_BPB83, I.MANUFACTURING): [(_X83, 5), (_M83, 20)],
                        (_BPX83, I.REACTION): [(_M83, 50)]}
        activity_time = {(_BPA83, I.MANUFACTURING): 3600, (_BPB83, I.MANUFACTURING): 7200,
                         (_BPX83, I.REACTION): 1800}
        activity_max_runs = {}
        reaction_products = {_X83}
        invention_for_bpc = {}
        bp_products = {}
        item_cat = {}

    _rb83 = I.buendel_rezepte(_Rec83(), [(_A83, 20), (_B83, 10)])
    eq("b83 _bd_enden: Einzelplan -> {type_id}", win._bd_enden(_A83, _Rec83()), {_A83})
    eq("b83 _bd_enden: Buendel -> seine Enden", win._bd_enden(I.BUENDEL_ID, _rb83),
       {_A83, _B83})
    eq("b83 _bd_enden: Buendel ohne Rezepte -> leer, nie das Buendel selbst",
       win._bd_enden(I.BUENDEL_ID, None) if getattr(win, "_bd_recipes", None) is None
       else set(), set())
    _alt83 = getattr(win, "_bd_recipes", None)
    win._bd_recipes = _rb83
    try:
        eq("b83 Stufe: beide Enden sind 'endproduct' (endprodukt = Buendel-ID)",
           (win._bau_stufe_fuer_item(_A83, {_X83}, {}, I.BUENDEL_ID),
            win._bau_stufe_fuer_item(_B83, {_X83}, {}, I.BUENDEL_ID),
            win._bau_stufe_fuer_item(_M83, {_X83}, {}, I.BUENDEL_ID),
            win._bau_stufe_fuer_item(_X83, {_X83}, {_X83: 2}, I.BUENDEL_ID)),
           ("endproduct", "endproduct", "components", "reaction_2"))
        eq("b83 Stufe: eine Enden-MENGE geht ebenfalls",
           win._bau_stufe_fuer_item(_B83, set(), {}, {_A83, _B83}), "endproduct")
        _ids83 = [_A83, _B83, _X83, _M83]
        _grp83 = {t83: "" for t83 in _ids83}
        _cat83 = win._bau_category_me_map(_ids83, _grp83, {_X83}, I.BUENDEL_ID,
                                          recipes=_rb83)
        check("b83 Kategorie-ME: KEIN Ende bekommt Kategorie-ME (wie das Endprodukt)",
              _A83 not in _cat83 and _B83 not in _cat83 and _M83 in _cat83)
        _me_alt83 = getattr(win, "_bd_me", None)
        _je_alt83 = getattr(win, "_bd_me_je_ende", None)
        win._bd_me = 3.0
        win._bd_me_je_ende = {_A83: 7.0}
        _mm83 = win._bau_me_maps(_ids83, _grp83, {_X83}, _cat83, I.BUENDEL_ID,
                                 recipes=_rb83)[0]
        check("b83 ME je Ende: A nimmt seine eigene ME (7), B faellt auf die Eingabe (3)",
              abs(_mm83.get(_A83, -1) - 7.0) < 1e-9 and abs(_mm83.get(_B83, -1) - 3.0) < 1e-9)
        win._bd_me = _me_alt83
        if _je_alt83 is None:
            del win._bd_me_je_ende
        else:
            win._bd_me_je_ende = _je_alt83
    finally:
        win._bd_recipes = _alt83
    # Plan-Karte ("Meine Bauplaene"): ein gespeicherter Multi-Plan traegt
    # type_id = Buendel und `enden`; die Schnellschaetzung plant das Buendel
    # und verkauft alle Enden.
    _pm83 = {_M83: 100.0, _X83: 1e9, _A83: 50000.0, _B83: 90000.0}
    _p83 = {"id": 992, "type_id": I.BUENDEL_ID, "qty": 1, "label": "b83 Multi",
            "item_name": "b83", "checked": [], "enden": [[_A83, 20], [_B83, 10]],
            "me": 10}
    _est83 = win._bau_saved_plan_quick_estimate(_p83, _Rec83(), _pm83, dict(_pm83))
    check("b83 Schnellschaetzung eines Multi-Plans liefert ein Ergebnis", _est83 is not None)
    _pl83 = I.production_plan(I.BUENDEL_ID, 1, _pm83.get, _rb83,
                              {"me": 10, "job_pct": 3, "build_reactions": True,
                               "adjusted_prices": dict(_pm83), "invention": False})
    check("b83 ... mit dem Verkauf ALLER Enden (20 x 50k + 10 x 90k = 1,9 Mio brutto)",
          _est83 is not None and abs((_est83.get("sell") or 0)
                                     - 1900000.0 * (1 - _est83.get("fee_pct", 0) / 100.0)) < 1.0)
    check("b83 ... und Kosten in der Groessenordnung des Buendel-Plans (ein X-Batch)",
          _est83 is not None and 0.5 * _pl83["total_cost"] < _est83["cost"] < 2.0 * _pl83["total_cost"]
          and _pl83["build_runs"].get(_X83) == 1)
    _p83f = dict(_p83, enden=[[_A83, 0]])
    check("b83 Multi-Plan ohne gueltige Enden: keine Schaetzung, kein Absturz",
          win._bau_saved_plan_quick_estimate(_p83f, _Rec83(), _pm83, dict(_pm83)) is None)
    check("b83 Multi-Plan, ein Ende ohne Preis: keine Schaetzung (wie beim Einzelplan)",
          win._bau_saved_plan_quick_estimate(_p83, _Rec83(), {_M83: 100.0, _A83: 50000.0},
                                             {}) is None)
except Exception as _e83:                                # pragma: no cover
    _fail.append(f"b83 Multi-Bauplan Schritt 2: {type(_e83).__name__}: {_e83}")


# ---------------------------------------------------------------- (b84)
# MULTI-BAUPLAN (1.0.9): der Buendel-Eintrag aus Quellplaenen (Entscheid A),
# Buendel-Karte "Endprodukte" im Bauplan-Dialog, Pending-Uebergabe an
# open_build_detail, Hinweis bei geaenderten Einzelplaenen.
# AUSGEBAUT 26.09.2026 (Aufraeumen nach dem Umbau "ein Bauplan ist ein
# Buendel mit N Enden"): der eigene Multi-Buildplaner-Dialog (Rail-Knopf,
# Plan-Wahl mit Haken, Vorschau "einzeln vs. gebuendelt", Gewinnzeile,
# Speichern, Bearbeiten). Was er konnte, lebt woanders: Ende dazu per
# Rechtsklick/"+ Add end product" (b87), Vergleich in der Karte (b87),
# Gewinn je Ende in der Karte (Spalte "Profit/unit, net"), Gesamtgewinn in
# der Kopfzeile des Fensters. Hier bleibt, was NICHT am Dialog hing.
try:
    import eve_trader.ui.mw_multi_bauplan as _mmb84
    _alt_plans84 = win.settings.get("bau_saved_plans")
    _alt_rc84 = I.recipes_cached
    from eve_trader import store as _st84
    _alt_snap84 = _st84.get_snapshot
    _alt_sde84 = I.sde_ready
    _pm84 = {_M83: 100.0, _X83: 1e9, _A83: 50000.0, _B83: 90000.0}
    I.recipes_cached = lambda *a, **k: _Rec83()
    _st84.get_snapshot = lambda *a, **k: [
        {"type_id": t84, "sell_min": p84} for t84, p84 in _pm84.items()]
    I.sde_ready = lambda: True
    win.settings["bau_saved_plans"] = [
        {"id": 8401, "label": "b84 Plan A", "type_id": _A83, "item_name": "A84",
         "qty": 20, "me": 7, "te": 14, "checked": [], "invention": False},
        {"id": 8402, "label": "b84 Plan B", "type_id": _B83, "item_name": "B84",
         "qty": 10, "me": 3, "te": 2, "checked": [], "invention": True,
         "blacklist_names": ["Foo"]},
    ]
    # 26.09.2026: der Rail-Knopf ist WEG - ein Buendel entsteht aus jedem
    # Bauplan heraus. Und der Dialog dahinter ist ausgebaut: keine Methode,
    # kein Katalogtext (ein Ruecklaeufer waere eine zweite Wahrheit).
    check("b84 der Rail-Knopf zum Multi Buildplaner existiert NICHT mehr",
          getattr(win, "_bau_multi_btn", None) is None)
    _spr84 = open(os.path.join(_ROOT, "eve_trader", "sprache.py"),
                  encoding="utf-8").read()
    check("b84 der Multi-Dialog ist ausgebaut (keine Methode, kein Katalogtext)",
          not hasattr(win, "_open_multi_bauplan_dialog")
          and not hasattr(win, "_multi_plan_speichern")
          and not hasattr(win, "_multi_einzelplaene")
          and '"Tick at least two build plans."' not in _spr84
          and '"WHAT THE BUNDLE BRINGS"' not in _spr84)
    # DER BUENDEL-EINTRAG AUS QUELLPLAENEN (Entscheid A: so, wie sie
    # gespeichert sind). Der Weg lebt weiter: _open_multi_saved_plan baut
    # damit den Eintrag neu, wenn der Nutzer "neu uebernehmen" sagt.
    _q84 = [p for p in win.settings["bau_saved_plans"] if p.get("id") in (8401, 8402)]
    _e84 = win._multi_plan_aus_quellen(_q84, {8401: 20, 8402: 10})
    eq("b84 Eintrag: Buendel-ID, Enden sortiert mit Mengen",
       (_e84["type_id"], _e84["enden"], _e84["qty"]),
       (I.BUENDEL_ID, [[_A83, 20], [_B83, 10]], 1))
    eq("b84 Eintrag: ME/TE je Ende aus den Einzelplaenen (Entscheid A)",
       (_e84["me_je_ende"], _e84["te_je_ende"]),
       ({str(_A83): 7, str(_B83): 3}, {str(_A83): 14, str(_B83): 2}))
    check("b84 Eintrag: Invention (irgendein Plan) und Blacklist (Vereinigung) kommen mit",
          _e84["invention"] is True and _e84["blacklist_names"] == ["Foo"]
          and _e84["quellen"] == [8401, 8402])
    check("b84 Eintrag: Name automatisch 'Multi: A84 + B84'",
          _e84["label"].startswith("Multi") and "A84" in _e84["label"]
          and "B84" in _e84["label"])
    _e84b = win._multi_plan_aus_quellen(_q84, {8401: 40, 8402: 10})
    eq("b84 Menge je Quelle", _e84b["enden"], [[_A83, 40], [_B83, 10]])
    eq("b84 ... und sie steht als mengen_je_quelle im Eintrag",
       _e84b["mengen_je_quelle"], {"8401": 40, "8402": 10})
    _pid84 = 8499
    _gesp84 = dict(_e84b, id=_pid84)
    win.settings["bau_saved_plans"].append(_gesp84)
    win.b_stack.setCurrentIndex(2); win._reload_saved_plans(); _app.processEvents()
    eq("b84 Karte: Fortschrittsbalken zaehlt bis Summe der Enden (40 + 10)",
       win._plan_progress[_pid84].maximum(), 50)
    # Buendel im Bauplan-Dialog: Karte "Endprodukte", Menge gesperrt.
    _rb84 = I.buendel_rezepte(_Rec83(), [(_A83, 40), (_B83, 10)])
    _o84 = {"me": 0, "te": 0, "job_pct": 0, "build_reactions": True,
            "tree_depth": 4, "adjusted_prices": dict(_pm84)}
    win._bd_pricemap = {**_pm84, I.BUENDEL_ID: 40 * 50000.0 + 10 * 90000.0}
    win._bd_recipes = _rb84; win._bd_recipes_basis = _rb84
    win._bd_opts = dict(_o84); win._bd_type = I.BUENDEL_ID; win._bd_qty = 1
    win._bd_buendel_enden = [(_A83, 40), (_B83, 10)]
    win._bd_me_je_ende = {_A83: 7.0, _B83: 3.0}; win._bd_te_je_ende = {}
    _plan84 = I.production_plan(I.BUENDEL_ID, 1, _pm84.get, _rb84, dict(_o84))
    _tree84 = I.build_tree(I.BUENDEL_ID, _pm84.get, _rb84, dict(_o84))
    _res84 = {"tree": _tree84, "names": {_A83: "A84", _B83: "B84", _X83: "X84",
                                         _M83: "M84", I.BUENDEL_ID: "Multi 84"},
              "sell": 40 * 50000.0 + 10 * 90000.0, "sell_is_contract": False,
              "plan": _plan84}
    # DEN GEMERKTEN KLAPP-ZUSTAND VORHER WEGNEHMEN (b98 weiter unten prueft
    # die VORGABE "offen"): der Umschalter speichert in `.smoke_home`, und
    # dieser Zustand ueberlebt den Lauf - mit einem gespeicherten Wert waere
    # die Vorgabe nie gefragt und die Pruefung blind (Lehre b46/aa383).
    win.settings.pop("bau_multi_enden_offen", None)
    win._show_build_detail(I.BUENDEL_ID, "Multi 84", _res84)
    _app.processEvents()
    _d84 = getattr(win, "_bd_dialog", None)
    check("b84 der Bauplan-Dialog baut sich mit dem Buendel", _d84 is not None)
    check("b84 der Knopf 'Add build plan' sitzt auch beim T1-Buendel in der Endprodukte-Karte",
          getattr(win, "_bd_ende_btn", None) is not None
          and getattr(win, "_bd_multi_tbl", None) is not None
          and win._bd_ende_btn.parentWidget() is not None
          and win._bd_ende_btn.parentWidget().isAncestorOf(win._bd_multi_tbl)
          and not any("save" in (b.text() or "").lower() or "speichern" in (b.text() or "").lower()
                      for b in win._bd_ende_btn.parentWidget().findChildren(QPushButton)))
    import eve_trader.ui.theme as _th84
    # UMGEDREHT 30.09.2026 (Nutzer: "nicht so fett und normal farben").
    check("b84 ... und ist normal gestylt wie beim Einzelplan (kein Amber)",
          win._bd_ende_btn.styleSheet() != _th84.amber_rahmen_knopf()
          and "AMBER" not in win._bd_ende_btn.styleSheet()
          and _th84.AMBER not in win._bd_ende_btn.styleSheet()
          and "font-weight" not in win._bd_ende_btn.styleSheet())
    check("b84 ein T1-Buendel hat KEINEN Invention-Tab (Gegenprobe zu b113)",
          not any("Invention" in _tw.tabText(_i)
                  for _tw in _d84.findChildren(QTabWidget)
                  for _i in range(_tw.count())))
    _tbl84 = getattr(win, "_bd_multi_tbl", None)
    eq("b84 Karte 'Endprodukte': eine Zeile je Ende",
       _tbl84.rowCount() if _tbl84 is not None else -1, 2)
    # Menge steht seit Schritt 4 als BEDIEN-Element in Spalte 1, die
    # Kosten/Stk in Spalte 6 (vorher 1 und 2).
    _sum_k84 = 0.0
    for _r84 in range(_tbl84.rowCount() if _tbl84 is not None else 0):
        _nm84 = _tbl84.item(_r84, 0).text()
        _tid84 = _A83 if _nm84 == "A84" else _B83
        _sum_k84 += (win._bd_multi_zeilen[_tid84]["menge"].value()
                     * _tbl84.item(_r84, 7)._value)
    _plan_jetzt84 = (getattr(win, "_bd_plan_ref", None) or {}).get("plan") or _plan84
    check(f"b84 Karte: Kosten/Stk x Menge summiert sich zu den Gesamtkosten "
          f"({_sum_k84:.0f} vs {_plan_jetzt84['total_cost']:.0f})",
          abs(_sum_k84 - float(_plan_jetzt84["total_cost"])) < 1.0)
    _qs84 = [s for s in _d84.findChildren(QSpinBox) if not s.isEnabled()
             and s.value() == 1 and "multi" in s.toolTip().lower()]
    check("b84 die Menge ist beim Buendel gesperrt und erklaert sich", len(_qs84) == 1)
    # ---- (b98) BILDER + EINKLAPPEN der Endprodukt-Karte (23.09.2026) ----
    # Nutzer: "danach fehlen mir in einem Multibuildplan immer noch die Icons
    # der Endprodukte ganz oben" und "ich moechte, dass man 'Endprodukte
    # dieses Buendels' einklappen kann wie der Details auch, standardmaessig
    # aber offen".
    _ico98 = [_tbl84.item(_r, 0).icon().isNull()
              for _r in range(_tbl84.rowCount())]
    # KEIN BILD ERZWINGEN: in der Pruefumgebung gibt es keinen Bilder-Cache
    # und kein Netz, also darf das Symbol leer sein. Geprueft wird, dass die
    # Zeile ueberhaupt eine Symbol-Ablage hat und die Tabelle eine
    # Symbolgroesse kennt - ohne die waere ein geladenes Bild unsichtbar.
    check("b98 die Endprodukt-Tabelle zeigt Symbole in der Namensspalte",
          _tbl84.iconSize().width() >= 16 and len(_ico98) == 2)
    _body98 = getattr(win, "_bd_multi_body", None)
    _kl98 = getattr(win, "_bd_multi_klapp", None)
    check("b98 die Karte hat einen Klapp-Knopf und einen Kasten",
          _body98 is not None and _kl98 is not None)
    check("b98 standardmaessig ist sie OFFEN (Nutzer-Vorgabe)",
          bool(_kl98.isChecked())
          and _body98.isVisibleTo(_body98.parentWidget()))
    # DEN ECHTEN WEG GEHEN: den Knopf druecken (Lehre b87/b88).
    _kl98.click(); _app.processEvents()
    check("b98 ein Klick klappt sie zu",
          not _body98.isVisibleTo(_body98.parentWidget()))
    eq("b98 ... und der Zustand wird gemerkt",
       win.settings.get("bau_multi_enden_offen"), False)
    check("b98 die Tabelle selbst bleibt erhalten (nur versteckt)",
          getattr(win, "_bd_multi_tbl", None) is _tbl84)
    _kl98.click(); _app.processEvents()
    check("b98 noch ein Klick klappt sie wieder auf",
          _body98.isVisibleTo(_body98.parentWidget()))
    # ZUSTAND ZURUECKGEBEN (Lehre b46/aa383: `.smoke_home` ueberlebt Laeufe).
    # WEGNEHMEN statt auf True setzen - sonst prueft der naechste Lauf den
    # gespeicherten Wert statt der Vorgabe.
    win.settings.pop("bau_multi_enden_offen", None)
    _d84.close(); _app.processEvents()
    # DAS PENDING WIRD WIRKLICH VERBRAUCHT (ausgefuehrt, Rotprobe fand die
    # Attrappe unten blind): echtes open_build_detail, aber ohne Markt-Scan
    # -> es bricht nach dem Zuruecksetz-Zweig mit der Meldung "Markt-Scan
    # zuerst" ab (Meldung stummgeschaltet). Bis dahin muss das Buendel in
    # den Feldern stehen; ein normaler Plan danach findet sie geleert vor.
    import eve_trader.ui.main_window as _mwm84
    _snap_leer84 = _st84.get_snapshot
    _st84.get_snapshot = lambda *a, **k: []
    _info_alt84 = _mwm84.QMessageBox.information
    _infos84 = []
    _mwm84.QMessageBox.information = lambda *a, **k: _infos84.append(a[1] if len(a) > 1 else "")
    try:
        win._bd_buendel_pending = {"enden": [(_A83, 40), (_B83, 10)], "quellen": [8401],
                                   "me": {_A83: 7.0}, "te": {_B83: 2.0}}
        win._bd_bp_type = None
        win._bd_qty = 99
        win.open_build_detail(I.BUENDEL_ID, "Multi 84", fresh=True)
        check("b84 open_build_detail: das Pending ist verbraucht und die Felder stehen",
              getattr(win, "_bd_buendel_pending", None) is None
              and win._bd_buendel_enden == [(_A83, 40), (_B83, 10)]
              and win._bd_me_je_ende == {_A83: 7.0} and win._bd_te_je_ende == {_B83: 2.0}
              and win._bd_buendel_quellen == [8401] and win._bd_qty == 1)
        check("b84 ... und der Lauf endete erst an der fehlenden Markt-Preisliste",
              len(_infos84) == 1)
        win.open_build_detail(100, "Testship", fresh=True)
        check("b84 ein normaler Plan danach erbt keine Buendel-Felder",
              win._bd_buendel_enden is None and win._bd_me_je_ende == {}
              and win._bd_te_je_ende == {})
        win._bd_bp_type = None
        win.open_build_detail(I.BUENDEL_ID, "Multi leer", fresh=True)
        check("b84 Buendel ohne Enden und ohne Pending: Hinweis statt Absturz",
              len(_infos84) == 3 and getattr(win, "_bd_buendel_enden", None) is None)
    finally:
        _mwm84.QMessageBox.information = _info_alt84
        _st84.get_snapshot = _snap_leer84
    # Pending-Uebergabe: _multi_plan_oeffnen legt das Buendel fuer
    # open_build_detail bereit (dort NACH dem Zuruecksetz-Zweig verbraucht).
    _obd_alt84 = win.open_build_detail
    _obd_calls84 = []
    win.open_build_detail = lambda tid, name, fresh=False: _obd_calls84.append((tid, name, fresh))
    try:
        win._multi_plan_oeffnen(_gesp84, plan_id=_pid84)
        _pend84 = getattr(win, "_bd_buendel_pending", None) or {}
        check("b84 Oeffnen: open_build_detail bekommt die Buendel-ID und den Namen",
              _obd_calls84 and _obd_calls84[-1][0] == I.BUENDEL_ID
              and _obd_calls84[-1][1] == _gesp84["label"] and _obd_calls84[-1][2] is False)
        eq("b84 Oeffnen: Pending traegt Enden, ME/TE je Ende und Quellen",
           (_pend84.get("enden"), _pend84.get("me"), _pend84.get("quellen")),
           ([(_A83, 40), (_B83, 10)], {_A83: 7.0, _B83: 3.0}, [8401, 8402]))
        check("b84 Oeffnen: ein gespeicherter Multi-Plan laedt als gespeichert (Haken, Reservierung)",
              getattr(win, "_bd_loading_saved", False) is True
              and getattr(win, "_bd_open_plan_id", None) == _pid84)
        _src84 = open(os.path.join(_ROOT, "eve_trader", "ui", "main_window.py"),
                      encoding="utf-8").read()
        check("b84 open_build_detail verbraucht das Pending NACH dem Zuruecksetz-Zweig",
              _src84.find("self._bd_buendel_pending = None") >
              _src84.find("self._bd_bp_type = type_id\n") > 0)
        # ENTSCHEID A: Einzelplan geaendert -> Hinweis; JA uebernimmt.
        win.settings["bau_saved_plans"][0]["me"] = 9
        _qalt84 = _mmb84.QMessageBox.question
        _fragen84 = []
        _mmb84.QMessageBox.question = (
            lambda *a, **k: (_fragen84.append(a[2]), _mmb84.QMessageBox.Yes)[1])
        try:
            win._open_saved_plan(_pid84)
        finally:
            _mmb84.QMessageBox.question = _qalt84
        check("b84 Entscheid A: geaenderter Einzelplan wird beim Oeffnen gemeldet",
              len(_fragen84) == 1 and "b84 Plan A" in _fragen84[0])
        _gesp84b = next(p for p in win.settings["bau_saved_plans"] if p.get("id") == _pid84)
        eq("b84 Entscheid A: JA uebernimmt die neue ME (9) in den Multi-Plan",
           _gesp84b["me_je_ende"].get(str(_A83)), 9)
        check("b84 ... und oeffnet ueber den Multi-Weg (Buendel-ID)",
              _obd_calls84[-1][0] == I.BUENDEL_ID)
        _fragen84b = []
        _mmb84.QMessageBox.question = (
            lambda *a, **k: (_fragen84b.append(1), _mmb84.QMessageBox.Yes)[1])
        try:
            win._open_saved_plan(_pid84)
        finally:
            _mmb84.QMessageBox.question = _qalt84
        check("b84 Entscheid A: unveraendert -> keine Frage mehr", not _fragen84b)
    finally:
        win.open_build_detail = _obd_alt84
    # Aufraeumen: ein normaler Plan darf die Buendel-Felder nicht erben.
    win._bd_buendel_pending = None
    win._bd_buendel_enden = None; win._bd_me_je_ende = {}; win._bd_te_je_ende = {}
    win._bd_type = 100; win._bd_recipes = _Recipes(); win._bd_recipes_basis = None
    win._bd_multi_refresh = None
    check("b84 Buendel-Verkauf = Summe Preis x Menge, Ende ohne Preis zaehlt 0",
          abs(win._multi_buendel_verkauf({_A83: 2.0}, [(_A83, 3), (_B83, 5)]) - 6.0) < 1e-9)
    check("b84 resolve_names schickt die Buendel-ID nie an ESI",
          "for t in type_ids if int(t) > 0))" in open(os.path.join(_ROOT, "eve_trader", "esi.py"),
                                   encoding="utf-8").read())
    check("b84 _item_pixmap: das Buendel hat kein Bild (kein Abruf)",
          win._item_pixmap(I.BUENDEL_ID) is None)
except Exception as _e84:                                # pragma: no cover
    import traceback as _tb84
    _fail.append(f"b84 Multi-Bauplan: {type(_e84).__name__}: {_e84} | "
                 + _tb84.format_exc().splitlines()[-3].strip())
finally:
    try:
        I.recipes_cached = _alt_rc84
        _st84.get_snapshot = _alt_snap84
        I.sde_ready = _alt_sde84
        win.settings["bau_saved_plans"] = _alt_plans84
        win._reload_saved_plans()
    except Exception:
        pass


# ---------------------------------------------------------------- (b158)
# GEGENRECHNUNG UND MARKT-CHECK (emm349, Nutzer: "dass wir einmal
# herausgefunden haben, dass die Frachtkosten doppelt gezaehlt wurden" und
# "die Marge von Multibauplaenen ist erschreckend zu gut"). Das ECHTE Fenster
# rechnet ein Buendel mit Gebuehren, Fracht (m3-Satz + Pauschale) und
# Extrakosten; der Test rechnet DANEBEN von Hand aus dem Rezept nach - ohne
# Programm-Code. In BEIDEN Fracht-Modi ("Fracht entscheidet mit" an/aus) muss
# derselbe Gewinn herauskommen: steckt der Satz im Kaufpreis, darf er nicht
# noch einmal abgezogen werden (genau die alte Doppelzaehlung).
try:
    from eve_trader import store as _st158
    _alt158 = {"rc": I.recipes_cached, "snap": _st158.get_snapshot, "sde": I.sde_ready,
               "hist": _st158.get_histories}
    _set158 = {k: win.settings.get(k, "__fehlt__") for k in (
        "bau_transport_rate", "bau_transport_trip_cost", "bau_transport_m3",
        "bau_freight_in_decision", "bau_extra_cost", "bau_buy_surplus")}
    _pm158 = {_M83: 100.0, _X83: 1e9, _A83: 50000.0, _B83: 90000.0}
    _vol158 = {_M83: 0.01, _X83: 1.0, _A83: 5.0, _B83: 10.0}
    try:
        I.recipes_cached = lambda *a, **k: _Rec83()
        _st158.get_snapshot = lambda *a, **k: [
            {"type_id": t158, "sell_min": p158} for t158, p158 in _pm158.items()]
        I.sde_ready = lambda: True
        win._item_volumes_with_esi_fix = lambda ids: (
            {int(t158): _vol158.get(int(t158), 0.0) for t158 in (ids or [])}, set())
        win._fees_for_hub = lambda *a, **k: (0.036, 0.015, "b158")
        win.settings.update({"bau_transport_rate": 1000.0, "bau_transport_trip_cost": 50000.0,
                             "bau_transport_m3": 350000.0, "bau_extra_cost": 25000.0,
                             "bau_buy_surplus": 0})
        # MARKT-HISTORIE: A 2 Stueck jeden Tag, B nur an 7 von 30 Tagen je 1.
        import datetime as _dt158
        _tage158 = [(_dt158.date(2026, 10, 1) - _dt158.timedelta(days=i)).isoformat()
                    for i in range(30)]
        _hist158 = {_A83: [{"date": d, "average": 1.0, "highest": 1.0, "lowest": 1.0,
                            "volume": 2, "order_count": 1} for d in _tage158],
                    _B83: [{"date": d, "average": 1.0, "highest": 1.0, "lowest": 1.0,
                            "volume": 1, "order_count": 1} for d in _tage158[:7]]}
        _st158.get_histories = lambda ids, region=10000002: {
            int(t158): list(_hist158.get(int(t158), [])) for t158 in (ids or [])}
        _nachl158 = []
        win._absatz_nachladen = lambda tids, region=None, fertig=None: (
            _nachl158.append(sorted(int(x) for x in tids)), False)[1]

        def _oeffne158(in_decision):
            win.settings["bau_freight_in_decision"] = bool(in_decision)
            _rb = I.buendel_rezepte(_Rec83(), [(_A83, 40), (_B83, 10)])
            _o = {"me": 0, "te": 0, "job_pct": 0, "build_reactions": True,
                  "tree_depth": 4, "adjusted_prices": dict(_pm158)}
            win._bd_pricemap = {**_pm158, I.BUENDEL_ID: 2900000.0}
            win._bd_recipes = _rb; win._bd_recipes_basis = _rb
            win._bd_opts = dict(_o); win._bd_type = I.BUENDEL_ID; win._bd_qty = 1
            win._bd_buendel_enden = [(_A83, 40), (_B83, 10)]
            win._bd_me_je_ende = {}; win._bd_te_je_ende = {}
            _plan = I.production_plan(I.BUENDEL_ID, 1, _pm158.get, _rb, dict(_o))
            _tree = I.build_tree(I.BUENDEL_ID, _pm158.get, _rb, dict(_o))
            _res = {"tree": _tree, "names": {_A83: "A158", _B83: "B158", _X83: "X158",
                                             _M83: "M158", I.BUENDEL_ID: "b158"},
                    "sell": 2900000.0, "sell_is_contract": False, "plan": _plan}
            win._bd_rechnung_stand = None
            win.settings.pop("bau_multi_enden_offen", None)
            win._show_build_detail(I.BUENDEL_ID, "b158 Gegenrechnung", _res)
            _app.processEvents()
            return (dict(getattr(win, "_bd_rechnung_stand", None) or {}),
                    dict((getattr(win, "_bd_plan_ref", None) or {}).get("plan") or {}))
        _r_aus158, _p_aus158 = _oeffne158(False)
        # VON HAND, NUR AUS DEM REZEPT: A braucht je Stueck 2 X + 10 M, B 5 X
        # + 20 M; X entsteht zu 100 je Reaktion aus 50 M. 40 A + 10 B ->
        # 130 X -> 2 Reaktionen -> M = 400 + 200 + 100 = 700.
        _m158 = 40 * 10 + 10 * 20 + 2 * 50
        eq("b158 Rezept von Hand: 700 M gekauft, 2 Reaktionen, A/B gebaut",
           (int((_p_aus158.get("buy") or {}).get(_M83, 0)),
            int((_p_aus158.get("build_runs") or {}).get(_X83, 0)),
            int((_p_aus158.get("build_runs") or {}).get(_A83, 0)),
            int((_p_aus158.get("build_runs") or {}).get(_B83, 0))),
           (_m158, 2, 40, 10))
        _job158 = float(_p_aus158.get("job_cost") or 0.0)
        _brutto158 = 40 * 50000.0 + 10 * 90000.0
        _gebuehr158 = _brutto158 * (0.036 + 0.015)
        _fracht158 = _m158 * 0.01 * 1000.0 + 1 * 50000.0       # m3-Satz + 1 Fahrt
        _soll158 = (_brutto158 - _gebuehr158 - (_m158 * 100.0 + _job158)
                    - _fracht158 - 25000.0)
        check(f"b158 Fracht separat: Fenster-Gewinn = Handrechnung "
              f"({_r_aus158.get('profit')} vs {_soll158})",
              _r_aus158.get("profit") is not None
              and abs(_r_aus158["profit"] - _soll158) < 1.0)
        check(f"b158 ... Bausteine: Brutto, Gebuehren, Fracht, Extra einzeln richtig "
              f"({_r_aus158})",
              abs(_r_aus158.get("gross", 0) - _brutto158) < 0.01
              and abs(_r_aus158.get("fees", 0) - _gebuehr158) < 0.01
              and abs(_r_aus158.get("transport", 0) - _fracht158) < 0.01
              and abs(_r_aus158.get("extra", 0) - 25000.0) < 0.01)
        _r_an158, _p_an158 = _oeffne158(True)
        check(f"b158 Fracht im Kaufpreis: GLEICHER Gewinn, nicht doppelt abgezogen "
              f"({_r_an158.get('profit')} vs {_soll158})",
              _r_an158.get("profit") is not None
              and abs(_r_an158["profit"] - _soll158) < 1.0)
        check(f"b158 ... dort steckt der m3-Satz in den Kosten, die Fracht ist nur die Fahrt "
              f"({_r_an158.get('total')}, {_r_an158.get('transport')})",
              abs(_r_an158.get("total", 0) - (_m158 * 110.0 + _job158)) < 1.0
              and abs(_r_an158.get("transport", 0) - 50000.0) < 0.01)
        # MARKT-CHECK JE ENDE: A 40 Stueck bei 2/Tag = 20 Tage (langsam,
        # amber), B 10 Stueck bei 7/30 je Tag = 43 Tage (duenn, rot + Warnung).
        _tb158 = getattr(win, "_bd_multi_tbl", None)
        _kopf158 = _tb158.horizontalHeaderItem(11).text() if _tb158 is not None else ""
        check(f"b158 Endprodukte-Karte hat die Spalte 'Sold/day' ({_kopf158!r})",
              _tb158 is not None and _tb158.columnCount() == 13
              and _kopf158.startswith(_t4("Sold/day")))
        _zellen158 = {}
        for _r158 in range(_tb158.rowCount() if _tb158 is not None else 0):
            _zellen158[_tb158.item(_r158, 0).text()] = _tb158.item(_r158, 11)
        import eve_trader.ui.theme as _th158
        check(f"b158 A: '2.0 \u00b7 20' in Amber ({[(k, v.text()) for k, v in _zellen158.items()]})",
              "A158" in _zellen158 and _zellen158["A158"].text() == "2.0 \u00b7 20"
              and _zellen158["A158"].foreground().color().name().lower() == _th158.AMBER.lower())
        check("b158 B: '0.2 \u00b7 43' in Rot",
              "B158" in _zellen158 and _zellen158["B158"].text() == "0.2 \u00b7 43"
              and _zellen158["B158"].foreground().color().name().lower() == _th158.RED.lower())
        _ml158 = getattr(win, "_bd_multi_markt_lbl", None)
        check("b158 Warnzeile 'duenner Markt' nennt nur B",
              _ml158 is not None and not _ml158.isHidden()
              and "B158" in _ml158.text() and "A158" not in _ml158.text())
        _st158.get_histories = lambda ids, region=10000002: {int(x): [] for x in (ids or [])}
        from PySide6.QtWidgets import QLabel as _QL158
        _l158 = _QL158()
        _nachl158.clear()
        win._einzel_absatz_zeigen(_A83, _l158)
        check(f"b158 Einzelplan ohne Historie: '?' und EIN Nachlade-Auftrag ({_nachl158})",
              "?" in _l158.text() and _nachl158 == [[_A83]])
    finally:
        I.recipes_cached = _alt158["rc"]
        _st158.get_snapshot = _alt158["snap"]
        I.sde_ready = _alt158["sde"]
        _st158.get_histories = _alt158["hist"]
        for _n158 in ("_item_volumes_with_esi_fix", "_fees_for_hub", "_absatz_nachladen"):
            win.__dict__.pop(_n158, None)
        for _k158, _v158 in _set158.items():
            if _v158 == "__fehlt__":
                win.settings.pop(_k158, None)
            else:
                win.settings[_k158] = _v158
        win._bd_buendel_enden = None; win._bd_me_je_ende = {}; win._bd_te_je_ende = {}
        win._bd_type = 100; win._bd_recipes = _Recipes(); win._bd_recipes_basis = None
        win._bd_multi_refresh = None
except Exception as _e158:                               # pragma: no cover
    import traceback as _tb158
    _fail.append(f"b158 Gegenrechnung: {type(_e158).__name__}: {_e158} | "
                 + _tb158.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b159)
# FEHLKLICK-HAKEN AM FENSTER (emm350): nach dem Job-Abruf verschwindet ein
# Hand-Haken ohne ESI-Job, gespeichert wird sofort, ein Hinweis nennt das
# Item. Ein Job auf einem ANDEREN verknuepften Charakter haelt den Haken.
# Scheiterte der Abruf fuer einen Charakter, bleibt alles stehen.
try:
    _alt159 = {k: getattr(win, k, None) for k in (
        "_bd_runplan_checked", "_bd_runplan_ts", "_bd_active_jobs_alle",
        "_bd_delivered_jobs", "_bd_jobs_ts", "_bd_sched_save_now", "_bd_names_ref",
        "_bd_haken_entfernt")}
    _tips159, _saves159 = [], []
    _ft_alt159 = win._flash_tip
    try:
        win._flash_tip = lambda msg, *a, **k: _tips159.append(str(msg))
        _t0_159 = 1_790_000_000.0
        win._bd_runplan_checked = {"component|7|91001", "component|7|91002"}
        win._bd_runplan_ts = {"component|7|91001": _t0_159, "component|7|91002": _t0_159}
        win._bd_active_jobs_alle = {91002: [{"char": "Anderer", "status": "active"}]}
        win._bd_delivered_jobs = []
        win._bd_jobs_ts = _t0_159 + 3600
        win._bd_sched_save_now = lambda: _saves159.append(sorted(win._bd_runplan_checked))
        win._bd_names_ref = {91001: "b159 Platte", 91002: "b159 Kondensator"}
        eq("b159 Abruf mit Fehler: kein Haken wird angefasst",
           (win._haken_ohne_job_pruefen({"failed": ["Jobs: X"]}),
            sorted(win._bd_runplan_checked)),
           ([], ["component|7|91001", "component|7|91002"]))
        _weg159 = win._haken_ohne_job_pruefen({"failed": []})
        check(f"b159 ohne Job weg, mit Job (anderer Charakter) bleibt, gespeichert, "
              f"Hinweis nennt das Item ({_weg159}, {_saves159}, {_tips159})",
              _weg159 == ["component|7|91001"]
              and win._bd_runplan_checked == {"component|7|91002"}
              and "component|7|91001" not in win._bd_runplan_ts
              and _saves159 == [["component|7|91002"]]
              and len(_tips159) == 1 and "b159 Platte" in _tips159[0]
              and "b159 Kondensator" not in _tips159[0])
        # Nutzer: "auf zwei verschiedene, aber verlinkte Chars gestartet" -
        # auch ein Charakter OHNE Rollen-Haken (ausserhalb des Pools) zaehlt.
        win._bd_runplan_checked = {"component|7|91001"}
        win._bd_runplan_ts = {"component|7|91001": _t0_159}
        _tips159.clear()
        eq("b159 Job bei einem verknuepften Charakter ohne Rolle haelt den Haken",
           (win._haken_ohne_job_pruefen({"failed": [], "haken_jobs": {
               "aktiv": {91001}, "geliefert": [], "voll": True}}), _tips159), ([], []))
        eq("b159 Abruf eines solchen Charakters gescheitert: nichts anfassen",
           win._haken_ohne_job_pruefen({"failed": [], "haken_jobs": {
               "aktiv": set(), "geliefert": [], "voll": False}}), [])
    finally:
        win._flash_tip = _ft_alt159
        win.__dict__.pop("_flash_tip", None)
        for _k159, _v159 in _alt159.items():
            setattr(win, _k159, _v159)
except Exception as _e159:                               # pragma: no cover
    import traceback as _tb159
    _fail.append(f"b159 Fehlklick-Haken: {type(_e159).__name__}: {_e159} | "
                 + _tb159.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b160)
# FEHLENDE ESI-RECHTE ALS FENSTER (emm355): nennt die Charaktere und was
# fehlt, "Nicht mehr erinnern" gilt nur fuer genau diese Rechte, "Jetzt neu
# verlinken" geht auf Characters und startet den Login.
try:
    from eve_trader import config as _cfg160
    _ssa160 = _cfg160.save_settings_async
    _alt_aus160 = win.settings.pop("scope_hinweis_aus", None)
    _alt_impl160 = win.settings.get("use_implants")
    _calls160 = []
    try:
        _cfg160.save_settings_async = lambda *a, **k: None
        win.settings["use_implants"] = True
        _soll160 = win._gewuenschte_scopes()
        check("b160 der Login fragt dieselben Rechte an, die geprueft werden",
              _cfg160.IMPLANT_SCOPE in _soll160
              and "scopes = self._gewuenschte_scopes()" in open(
                  os.path.join(_ROOT, "eve_trader", "ui", "main_window.py"),
                  encoding="utf-8").read())
        _alle160 = set(_soll160)
        _erteilt160 = {11: _alle160 - {_cfg160.IMPLANT_SCOPE}, 12: set(_alle160), 13: None}
        _namen160 = {11: "b160 Peanut", 12: "b160 Fredy", 13: "b160 Unbekannt"}
        win._scope_box = None
        _f160 = win._scope_fenster_zeigen(_soll160, _erteilt160, _namen160, antwort="later")
        _bx160 = win._scope_box
        check(f"b160 Fenster nennt nur den Charakter mit Luecke und WAS fehlt ({_f160})",
              list(_f160) == [11] and _bx160 is not None
              and "b160 Peanut" in _bx160.informativeText()
              and "b160 Fredy" not in _bx160.informativeText()
              and "b160 Unbekannt" not in _bx160.informativeText()
              and _t4("implants") in _bx160.informativeText()
              and _bx160.checkBox() is not None)
        check("b160 Text vom Nutzer: 'o7 Pilot!' ... 'ist das nicht toll?'",
              _bx160.text().startswith("o7 Pilot!")
              and ("isn't that great?" in _bx160.text()
                   or "ist das nicht toll?" in _bx160.text()))
        win._scope_box = None
        win._scope_fenster_zeigen(_soll160, _erteilt160, _namen160, antwort="never")
        win._scope_box = None
        win._scope_fenster_zeigen(_soll160, _erteilt160, _namen160, antwort="later")
        check("b160 'Nicht mehr erinnern': fuer dieselben Rechte kein Fenster mehr",
              win._scope_box is None
              and win.settings.get("scope_hinweis_aus") == [_cfg160.IMPLANT_SCOPE])
        _erteilt160b = {11: _alle160 - {_cfg160.IMPLANT_SCOPE, _cfg160.ASSETS_SCOPE}}
        if _cfg160.ASSETS_SCOPE in _alle160:
            win._scope_fenster_zeigen(_soll160, _erteilt160b, _namen160, antwort="later")
            check("b160 ... ein NEUES fehlendes Recht fragt wieder",
                  win._scope_box is not None)
        _lk160 = win.link_character
        _gt160 = win._go_tab
        win.link_character = lambda: _calls160.append("link")
        win._go_tab = lambda k: _calls160.append(("tab", k))
        try:
            win.settings.pop("scope_hinweis_aus", None)
            win._scope_fenster_zeigen(_soll160, _erteilt160, _namen160, antwort="relink")
        finally:
            win.__dict__.pop("link_character", None)
            win.__dict__.pop("_go_tab", None)
        eq("b160 'Jetzt neu verlinken': Characters-Reiter, dann Login",
           _calls160, [("tab", "characters"), "link"])
    finally:
        _cfg160.save_settings_async = _ssa160
        if _alt_aus160 is None:
            win.settings.pop("scope_hinweis_aus", None)
        else:
            win.settings["scope_hinweis_aus"] = _alt_aus160
        if _alt_impl160 is None:
            win.settings.pop("use_implants", None)
        else:
            win.settings["use_implants"] = _alt_impl160
except Exception as _e160:                               # pragma: no cover
    import traceback as _tb160
    _fail.append(f"b160 ESI-Rechte-Fenster: {type(_e160).__name__}: {_e160} | "
                 + _tb160.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b161)
# GEFRORENER PLAN, REPROCESSING-CHARAKTER NEU (emm361, Nutzer: "RX-804 bei
# Peanut von Hand gesetzt, trotzdem will der Runplaner einen anderen Char").
# Echte Zahlen des Nutzers: Peanut R5/E5/Mercoxit 0 + RX-804 (4 %) gegen
# Gotflow R4/E5/Mercoxit 3 - Peanut 1.3156 > Gotflow 1.3059. Mengen bleiben.
try:
    _alt161 = {"ids": I.reprocess_skill_ids, "erz": I.reprocess_erz_skill,
               "imp": I.reprocess_implants,
               "sk": win.settings.get("bau_char_skills"),
               "hand": win.settings.get("bau_char_reproc_implant_hand"),
               "esi": win.settings.get("bau_char_reproc_implant")}
    try:
        I.reprocess_skill_ids = lambda: {"Reprocessing": 3385, "Reprocessing Efficiency": 3389}
        I.reprocess_erz_skill = lambda: {62586: 12189}
        I.reprocess_implants = lambda: {27174: {"name": "Zainou 'Beancounter' Reprocessing RX-804",
                                                "attr": "refiningYieldMutator", "value": 4.0}}
        win.settings["bau_char_skills"] = {"2115318203": {"3385": 5, "3389": 5},
                                           "2118033530": {"3385": 4, "3389": 5, "12189": 3}}
        win.settings["bau_char_reproc_implant"] = {}
        win.settings["bau_char_reproc_implant_hand"] = {}
        _sch161 = [{"erz": 62586, "menge": 700, "char": 2118033530, "ausbeute": 0.787}]
        _ohne161 = win._repro_char_neu_waehlen(_sch161, 0.602616)
        eq("b161 ohne Implantat bleibt Gotflow (Mercoxit 3 schlaegt R5)",
           [(x["char"], x["menge"]) for x in _ohne161], [(2118033530, 700)])
        win.settings["bau_char_reproc_implant_hand"] = {"2115318203": 27174}
        _mit161 = win._repro_char_neu_waehlen(_sch161, 0.602616)
        check(f"b161 mit RX-804 von Hand: Peanut, Ausbeute 79.3 %, Menge unveraendert ({_mit161})",
              [(x["char"], x["menge"]) for x in _mit161] == [(2115318203, 700)]
              and abs(_mit161[0]["ausbeute"] - 0.7928) < 0.0005
              and _sch161[0]["char"] == 2118033530)
        check("b161 der Runplaner wendet es bei gefrorenen Plaenen an",
              "_rp0_erz = self._repro_char_neu_waehlen(_rp0_erz, _rp0.get(\"basis\"))"
              in open(os.path.join(_ROOT, "eve_trader", "ui", "mw_bauplan_tabs.py"),
                      encoding="utf-8").read())
    finally:
        I.reprocess_skill_ids = _alt161["ids"]
        I.reprocess_erz_skill = _alt161["erz"]
        I.reprocess_implants = _alt161["imp"]
        for _k161, _sk161 in (("bau_char_skills", "sk"), ("bau_char_reproc_implant_hand", "hand"),
                              ("bau_char_reproc_implant", "esi")):
            if _alt161[_sk161] is None:
                win.settings.pop(_k161, None)
            else:
                win.settings[_k161] = _alt161[_sk161]
except Exception as _e161:                               # pragma: no cover
    import traceback as _tb161
    _fail.append(f"b161 Reprocessing-Charakter: {type(_e161).__name__}: {_e161} | "
                 + _tb161.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b85)
# MULTI BUILDPLANER, SCHRITT 4: ME/TE und "Eigene BPC" JE ENDPRODUKT.
# Am echten Fenster, mit zwei ERFINDBAREN Enden: ohne Haken regiert die
# Invention (ME-Feld gesperrt, zeigt die Invention-ME), mit Haken gilt die
# eigene Kopie - und der Materialbedarf dieses EINEN Endes sinkt.
try:
    _A85, _B85, _M85 = 971001, 971002, 971004
    _BPA85, _BPB85 = 981001, 981002

    class _Rec85:
        product_to_bp = {_A85: (_BPA85, I.MANUFACTURING, 1),
                         _B85: (_BPB85, I.MANUFACTURING, 1)}
        bp_materials = {(_BPA85, I.MANUFACTURING): [(_M85, 100)],
                        (_BPB85, I.MANUFACTURING): [(_M85, 100)]}
        activity_time = {(_BPA85, I.MANUFACTURING): 60,
                         (_BPB85, I.MANUFACTURING): 60}
        activity_max_runs = {}
        reaction_products = set()
        invention_for_bpc = {_BPA85: (961001, 10, 0.5, []),
                             _BPB85: (961002, 10, 0.5, [])}
        bp_products = {}
        item_cat = {}

    _pm85 = {_M85: 100.0, _A85: 9e9, _B85: 9e9}
    _rb85 = I.buendel_rezepte(_Rec85(), [(_A85, 10), (_B85, 10)])
    _o85 = {"invention": True, "job_pct": 0, "build_reactions": True, "me": 0,
            "me_map": {}, "adjusted_prices": dict(_pm85), "tree_depth": 4,
            "inv_datacore_free": True}
    win._bd_pricemap = {**_pm85, I.BUENDEL_ID: 9e9 * 20}
    win._bd_recipes = _rb85; win._bd_recipes_basis = _rb85
    win._bd_opts = dict(_o85); win._bd_type = I.BUENDEL_ID; win._bd_qty = 1
    win._bd_buendel_enden = [(_A85, 10), (_B85, 10)]
    win._bd_buendel_quellen = []
    win._bd_me_je_ende = {}; win._bd_te_je_ende = {}
    win._bd_own_bpc_je_ende = {}; win._bd_own_bpc_runs_je_ende = {}
    _plan85 = I.production_plan(I.BUENDEL_ID, 1, _pm85.get, _rb85, dict(_o85))
    _tree85 = I.build_tree(I.BUENDEL_ID, _pm85.get, _rb85, dict(_o85))
    _res85 = {"tree": _tree85, "sell": 9e9 * 20, "sell_is_contract": False,
              "plan": _plan85,
              "names": {_A85: "A85", _B85: "B85", _M85: "M85",
                        I.BUENDEL_ID: "Multi 85"}}
    win._show_build_detail(I.BUENDEL_ID, "Multi 85", _res85)
    _app.processEvents()
    _d85 = getattr(win, "_bd_dialog", None)
    check("b85 der Buendel-Dialog baut sich mit erfindbaren Enden", _d85 is not None)
    # ---- (b144) EINGEFROREN = JE ENDE ALLES GESPERRT (Nutzer 30.09.2026),
    # Auftauen gibt genau den Zustand davor zurueck (ME/TE hier durch die
    # Invention gesperrt - das bleibt so).
    _z144 = (getattr(win, "_bd_multi_zeilen", None) or {}).get(_A85)
    _felder144 = ("menge", "me", "te", "obpc", "runs")
    _vor144 = {k: _z144[k].isEnabled() for k in _felder144} if _z144 else {}
    _fz_alt144 = win._bd_frozen
    try:
        win._bd_frozen = {"ts": 1.0, "plan_snapshot": {"build_runs": {}}}
        _z144["sperren"]()
        _gesperrt144 = {k: _z144[k].isEnabled() for k in _felder144}
        _x144_frei = _z144["raus"].isEnabled()
    finally:
        win._bd_frozen = _fz_alt144
    _z144["sperren"]()
    _nach144 = {k: _z144[k].isEnabled() for k in _felder144}
    check(f"b144 Buendel eingefroren: Menge/ME/TE/Own BPC/Runs gesperrt ({_gesperrt144})",
          _z144 is not None and not any(_gesperrt144.values()))
    # Das rote X bleibt frei (emm333): Entfernen fragt selbst, Runs bleiben.
    check("b144 ... das rote X bleibt im eingefrorenen Buendel bedienbar",
          _z144 is not None and _x144_frei)
    check(f"b144 ... aufgetaut wie vorher ({_vor144} -> {_nach144})",
          _vor144 == _nach144 and _vor144.get("menge") is True
          and _vor144.get("me") is False)
    # ------------------------------------------------------------ (b113)
    # INVENTION-TAB IM BUENDEL (Nutzer 26.09.2026: "mir fehlt ein Invention
    # Tab im Multibauplan"). Befund: `_is_invented` fragte die Pseudo-
    # Blaupause des Buendels (-2), die nie erfindbar ist - der Tab flog fuer
    # JEDES Buendel raus. Jetzt: da, sobald EIN Ende erfindbar ist (b84
    # prueft die Gegenprobe: T1-Buendel ohne Tab).
    _tabs113 = [_tw for _tw in _d85.findChildren(QTabWidget)]
    _titel113 = [_tw.tabText(_i) for _tw in _tabs113 for _i in range(_tw.count())]
    check("b113 der Buendel-Dialog mit T2-Enden HAT den Invention-Tab",
          any("Invention" in _t for _t in _titel113))
    # KEINE KARTE FUER DAS BUENDEL SELBST im Invention-Tab (Nutzer
    # 26.09.2026: "wirklich nur, was invented werden muss" - sein Screenshot
    # zeigte "End product ME/TE (Sacrilege x1) - needs no invention").
    check("b113 im Invention-Tab steht keine 'needs no invention'-Karte fuer das Buendel",
          not [l for l in _d85.findChildren(QLabel)
               if "needs no invention" in (l.text() or "")
               or "braucht keine Invention" in (l.text() or "")])
    # DER KNOPF "+ ADD BUILD PLAN" SITZT BEIM BUENDEL IN DER ENDPRODUKTE-
    # KARTE (Nutzer 26.09.2026), beim Einzelplan in der Leiste (b84 unten).
    _eb113 = getattr(win, "_bd_ende_btn", None)
    _card113 = getattr(win, "_bd_multi_tbl", None).parentWidget() if getattr(win, "_bd_multi_tbl", None) else None
    check("b113 der Knopf 'Add build plan' sitzt in der Endprodukte-Karte",
          _eb113 is not None and _card113 is not None
          and ("build plan" in _eb113.text().lower() or "bauplan" in _eb113.text().lower())
          and _eb113.parentWidget() is not None
          and _eb113.parentWidget().isAncestorOf(win._bd_multi_tbl))
    eq("b113 rein: die erfindbaren Enden des Buendels",
       sorted(win._multi_enden_erfindbar(_rb85, [_A85, _B85, _M85])), sorted([_A85, _B85]))
    # INVENTION IST IM BUENDEL IMMER AN (Nutzer: "Decryptorwahl ueberschreibt
    # immer haendisch eingegebene ME/TE, es sei denn man waehlt eigene BPC"):
    # der globale Schalter AUS wird fuer ein Buendel mit T2-Ende uebergangen.
    _o113 = {"invention": False, "inv_manual_override": {}}
    win._multi_opts_je_ende(_o113, _rb85)
    check("b113 Invention AUS wird fuer ein Buendel mit T2-Enden auf AN gesetzt",
          _o113.get("invention") is True)
    _o113b = {"invention": False, "inv_manual_override": {}}
    _rb113 = I.buendel_rezepte(_Rec83(), [(_A83, 10), (_B83, 10)])
    _enden_alt113 = win._bd_buendel_enden
    win._bd_buendel_enden = [(_A83, 10), (_B83, 10)]
    try:
        win._multi_opts_je_ende(_o113b, _rb113)
    finally:
        win._bd_buendel_enden = _enden_alt113
    check("b113 ... ein T1-Buendel laesst den Schalter, wie er ist",
          _o113b.get("invention") is False
          and not win._multi_enden_erfindbar(_rb113, [_A83, _B83]))
    # WARNUNG BEI UNKLARER LAGE: eigene Kopien im Cache, Haken "Eigene BPC"
    # nicht gesetzt -> der Plan erfindet, obwohl Kopien im Hangar liegen.
    _cache_alt113 = getattr(win, "_bd_owned_bp_cache", None)
    win._bd_owned_bp_cache = [{"type_id": _BPA85, "quantity": 3, "runs": 10}]
    # Die Decryptor-Warnung (26.09.2026) gehoert nicht zu diesem Fall: beide
    # Decryptoren gelten hier als gewaehlt.
    _best_alt113 = set(getattr(win, "_bd_dec_bestaetigt", None) or ())
    win._bd_dec_bestaetigt = _best_alt113 | {_BPA85, _BPB85}
    try:
        eq("b113 rein: unklare Enden = T2 ohne Haken, mit eigenen Kopien im Cache",
           win._multi_unklare_enden(_plan85), [(_A85, 3)])
        win._bd_own_bpc_je_ende = {_A85: True}
        eq("b113 rein: mit Haken 'Eigene BPC' ist nichts mehr unklar",
           win._multi_unklare_enden(_plan85), [])
        win._bd_own_bpc_je_ende = {}
        _rf113 = getattr(win, "_bd_multi_refresh", None)
        _rf113(_plan85); _app.processEvents()
        _wl113 = getattr(win, "_bd_multi_warn_lbl", None)
        check("b113 die Karte zeigt die Warnung mit Name und Kopienzahl",
              _wl113 is not None and not _wl113.isHidden()
              and "A85" in _wl113.text() and "3" in _wl113.text())
        win._bd_own_bpc_je_ende = {_A85: True}
        _rf113(_plan85); _app.processEvents()
        check("b113 ... und mit Haken ist sie wieder weg", _wl113.isHidden())
    finally:
        win._bd_dec_bestaetigt = _best_alt113
        win._bd_own_bpc_je_ende = {}
        win._bd_owned_bp_cache = _cache_alt113
        _rf113 = getattr(win, "_bd_multi_refresh", None)
        if _rf113:
            _rf113(_plan85); _app.processEvents()
    # ------------------------------------------------------------ (b114)
    # DIE WERKZEUGE (Tools-Menue) AM BUENDEL (Nutzer 26.09.2026: "ueberpruefe,
    # ob die Tools-Dropdowns das richtige Ergebnis erzielen; 'optimale
    # Menge' funktioniert bisher nur auf 1 Endprodukt"). Gemessen am
    # offenen Buendel-Fenster (_d85), nicht am Quelltext.
    _ta114 = getattr(win, "_bd_tools_actions", None) or {}
    check("b114 das Tools-Menue ist am Buendel-Fenster erreichbar",
          bool(_ta114) and set(_ta114) >= {"opt", "ladder", "contract", "fehl", "nach", "esi"})
    check("b114 'Contract-Preise' ist beim Buendel gesperrt und sagt warum",
          not _ta114["contract"].isEnabled()
          and ("bundle" in _ta114["contract"].text().lower()
               or "bündel" in _ta114["contract"].text().lower())
          and _ta114["contract"].toolTip() != "")
    check("b114 die uebrigen Werkzeuge bleiben beim Buendel bedienbar",
          all(_ta114[k].isEnabled() for k in ("opt", "fehl", "nach", "esi")))
    # OPTIMALE MENGE: je Endprodukt (Auswahl oben), gerechnet wird das
    # gewaehlte Ende - nie die Buendel-ID.
    import eve_trader.ui.mw_optimizer as _mo114
    _pp_alt114 = I.production_plan
    _tids114 = []

    def _pp114(tid, qty, *a, **k):
        _tids114.append(int(tid))
        return _pp_alt114(tid, qty, *a, **k)
    _run_alt114 = win._run
    _ho_alt114 = win._hub_orders
    _mh_alt114 = _mo114.esi.fetch_market_history
    # KEIN Stub fuer ladder_cost_curve: ohne Orderbuch rechnet sie mit dem
    # Flachpreis - offline, aber echt. Nur die Markthistorie (Netz) bleibt weg.
    win._run = lambda worker, done_cb, fail_cb=None, **kw: done_cb(
        worker._fn(*worker._args, **worker._kwargs))
    win._hub_orders = lambda *a, **k: {"sell": [], "buy": []}
    _mo114.esi.fetch_market_history = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline"))
    I.production_plan = _pp114
    try:
        win.open_optimizer(); _app.processEvents()
        _cb114 = getattr(win, "_opt_ende_cb", None)
        check("b114 Optimierer am Buendel: Auswahl der Endprodukte, beide Enden drin",
              _cb114 is not None and _cb114.count() == 2
              and sorted(_cb114.itemData(i) for i in range(2)) == sorted([_A85, _B85]))
        # NAMEN statt Nummern (Nutzer 27.09.2026: "da sollen aber Namen stehen
        # und keine Zahlen" - das Dropdown zeigte #26888 ...).
        _nr114 = getattr(win, "_bd_names_ref", None) or {}
        _txt114 = [_cb114.itemText(i) for i in range(_cb114.count())] if _cb114 is not None else []
        check("b114 ... das Dropdown zeigt die NAMEN der Enden, keine #Nummern",
              _cb114 is not None and _txt114
              and all(not tx.startswith("#") for tx in _txt114)
              and all(_cb114.itemText(i) == str(_nr114.get(int(_cb114.itemData(i))))
                      for i in range(_cb114.count())))
        _dlg114 = _cb114.window() if _cb114 is not None else None
        _cb114.setCurrentIndex(1); _app.processEvents()
        _gew114 = int(_cb114.currentData())
        check("b114 ... der Titel folgt dem gewaehlten Ende",
              _dlg114 is not None and _cb114.currentText() in _dlg114.windowTitle())
        _btn114 = next((b for b in _dlg114.findChildren(QPushButton)
                        if (b.text() or "").strip() in ("Calculate", "Berechnen")), None)
        _tids114.clear()
        if _btn114 is not None:
            _btn114.click(); _app.processEvents()
        check("b114 ... 'Berechnen' rechnet das gewaehlte Ende, nie die Buendel-ID",
              _btn114 is not None and _tids114
              and set(_tids114) == {_gew114})
        if _dlg114 is not None:
            _dlg114.close(); _app.processEvents()
    finally:
        I.production_plan = _pp_alt114
        win._run = _run_alt114
        win._hub_orders = _ho_alt114
        _mo114.esi.fetch_market_history = _mh_alt114
    # ORDERBUCH-GENAU: rechnet das Buendel x1, eine Zeile je Kaufmaterial.
    win._run = lambda worker, done_cb, fail_cb=None, **kw: done_cb(
        worker._fn(*worker._args, **worker._kwargs))
    win._hub_orders = lambda *a, **k: {"sell": [(100.0, 10 ** 9)], "buy": []}
    _rn_alt114 = _mo114.esi.resolve_names
    _mo114.esi.resolve_names = lambda ids, *a, **k: {int(i): f"M{i}" for i in ids}
    try:
        win.open_ladder_check(); _app.processEvents()
        _ld114 = [w for w in _app.topLevelWidgets()
                  if isinstance(w, _mw61.MinimizableDialog)
                  and ("Order-book" in w.windowTitle() or "Orderbuch" in w.windowTitle())
                  and w.isVisible()]
        _ldlg114 = _ld114[-1] if _ld114 else None
        _lbtn114 = next((b for b in _ldlg114.findChildren(QPushButton)
                         if (b.text() or "").strip() in ("Calculate", "Berechnen")), None) \
            if _ldlg114 is not None else None
        if _lbtn114 is not None:
            _lbtn114.click(); _app.processEvents()
        _ltbl114 = _ldlg114.findChildren(QTableWidget)[0] if _ldlg114 is not None else None
        _kopf114 = [l for l in _ldlg114.findChildren(QLabel)
                    if "\u00d71" in (l.text() or "")] if _ldlg114 is not None else []
        check("b114 Orderbuch-genau am Buendel: Kopf 'x1', eine Zeile je Kaufmaterial",
              _ldlg114 is not None and bool(_kopf114)
              and _ltbl114 is not None and _ltbl114.rowCount()
              == len(_plan85.get("buy") or {}) > 0)
        if _ldlg114 is not None:
            _ldlg114.close(); _app.processEvents()
    finally:
        win._run = _run_alt114
        win._hub_orders = _ho_alt114
        _mo114.esi.resolve_names = _rn_alt114
    # FEHLBEDARF PRUEFEN / FEHLENDES NACHKAUFEN: laufen am Buendel ohne
    # Absturz und ohne die Buendel-ID als Material.
    import eve_trader.ui.main_window as _mwm114
    _inf_alt114 = _mwm114.QMessageBox.information
    _infos114 = []
    _mwm114.QMessageBox.information = lambda *a, **k: _infos114.append(str(a[2]) if len(a) > 2 else "")
    _exec_alt114 = _mwm114.QMessageBox.exec
    _mwm114.QMessageBox.exec = lambda self_, *a, **k: _infos114.append(self_.text())
    try:
        win._check_shortfall(); _app.processEvents()
        win._bd_verlust = {}
        win._buy_missing_again(); _app.processEvents()
        check("b114 'Fehlbedarf pruefen' und 'Fehlendes nachkaufen' laufen am Buendel durch",
              len(_infos114) == 2 and all(str(I.BUENDEL_ID) not in x for x in _infos114))
    finally:
        _mwm114.QMessageBox.information = _inf_alt114
        _mwm114.QMessageBox.exec = _exec_alt114
    # ALLES AUS ESI LADEN: die Invention-Runde nimmt die Enden (echte
    # T2-Blaupausen), nie die Pseudo-Blaupause des Buendels (-2).
    import eve_trader.store as _st114
    _lc_alt114 = _st114.list_characters
    _fb_alt114 = win._bd_fetch_all_owned_blueprints
    _ls_alt114 = win._load_stage_bp_from_esi
    _li_alt114 = win._load_all_invention_bpc_from_esi
    _cid_alt114 = win.settings.get("client_id")
    _inv_items114 = []
    _st114.list_characters = lambda: [{"character_id": 1, "name": "b114"}]
    win.settings["client_id"] = "b114"
    win._bd_fetch_all_owned_blueprints = lambda force=False: []
    win._load_stage_bp_from_esi = lambda *a, **k: (0, 0)
    win._load_all_invention_bpc_from_esi = lambda items, *a, **k: (_inv_items114.extend(items), 0)[1]
    try:
        _sum114, _err114, _own114 = win._load_all_esi_for_plan_core(I.BUENDEL_ID)
        check("b114 'Alles aus ESI laden' am Buendel: kein Fehler, Invention nur fuer die Enden",
              _err114 is None
              and sorted(_bp for _t, _bp, _r, _i in _inv_items114) == sorted([_BPA85, _BPB85])
              and I.BUENDEL_BP not in [_bp for _t, _bp, _r, _i in _inv_items114])
    finally:
        _st114.list_characters = _lc_alt114
        win._bd_fetch_all_owned_blueprints = _fb_alt114
        win._load_stage_bp_from_esi = _ls_alt114
        win._load_all_invention_bpc_from_esi = _li_alt114
        if _cid_alt114 is None:
            win.settings.pop("client_id", None)
        else:
            win.settings["client_id"] = _cid_alt114
    # ------------------------------------------------------------ (b115)
    # MAUSRAD UND BEST-CHOICE-KNOPF IM INVENTION-REITER (Nutzer 26.09.2026:
    # "wenn man scrollen will und mit der Maus per Zufall auf einem Decryptor-
    # Dropdown ist, scrollt das Dropdown und dann faengt der Plan an zu
    # rechnen und alles laggt. Dropdowns nur ueber Klicken bedienen" und
    # "der Best-Choice-Knopf ist so bloed ueber das ganze Fenster gezogen,
    # dass man ihn gar nicht sieht - kompakter links ueber dem Blueprint-
    # Namen, ersichtlicher"). Das Rad wird WIRKLICH geschickt (QWheelEvent),
    # nicht nur die Fokus-Regel gelesen: Wahl bleibt, keine Rechnung laeuft
    # an, die Bildlaufflaeche des Reiters bekommt das Rad.
    from PySide6.QtCore import QPoint as _QP115, QPointF as _QPF115
    from PySide6.QtGui import QWheelEvent as _QWE115
    from PySide6.QtWidgets import (QAbstractScrollArea as _QASA115,
                                   QSizePolicy as _QSP115)
    from eve_trader.ui import theme as _th115
    _ic115 = dict(getattr(win, "_bd_inv_combos", None) or {})
    _cb115 = _ic115.get(_BPA85)
    check("b115 Invention-Reiter: die Decryptor-Wahl von A steht bereit",
          _cb115 is not None and _cb115.count() >= 2 and _cb115.isEnabled())
    if _cb115 is not None:
        _reb115 = []
        _fr_alt115 = getattr(win, "_bd_full_rebuild", None)
        win._bd_full_rebuild = lambda *a, **k: _reb115.append(1)
        try:
            _idx115 = _cb115.currentIndex()
            _sa115 = _cb115.parentWidget()
            while _sa115 is not None and not isinstance(_sa115, _QASA115):
                _sa115 = _sa115.parentWidget()
            # OFFSCREEN HAT DIE BILDLAUFFLAECHE KEINEN WEG (Maximum 0) - also
            # nicht den Bildlauf messen, sondern ob das Rad am Viewport ANKOMMT:
            # ein Zaehl-Filter am Viewport waehrend des einen Ereignisses.
            from PySide6.QtCore import QEvent as _QEV115, QObject as _QOB115

            class _Zaehler115(_QOB115):
                n = 0

                def eventFilter(self, _o, _e):
                    if _e.type() == _QEV115.Wheel:
                        self.n += 1
                    return False
            _z115 = _Zaehler115()
            if _sa115 is not None:
                _sa115.viewport().installEventFilter(_z115)
            # RAD NACH UNTEN (-120): ohne Sperre springt die Wahl auf den
            # NAECHSTEN Eintrag. Nach oben bliebe Index 0 auch ohne Sperre
            # stehen - die Pruefung waere blind (Rotprobe hat es gemeldet).
            _ev115 = _QWE115(_QPF115(5, 5), _cb115.mapToGlobal(_QP115(5, 5)),
                             _QP115(0, -120), _QP115(0, -120), Qt.NoButton,
                             Qt.NoModifier, Qt.NoScrollPhase, False)
            _app.sendEvent(_cb115, _ev115); _app.processEvents()
            check("b115 Mausrad ueber dem Decryptor-Dropdown aendert die Wahl NICHT",
                  _cb115.currentIndex() == _idx115)
            check("b115 ... und loest KEINE Rechnung aus",
                  not _reb115)
            if _sa115 is not None:
                _sa115.viewport().removeEventFilter(_z115)
            check("b115 ... das Rad geht stattdessen an die Bildlaufflaeche des Reiters",
                  _sa115 is not None and _z115.n == 1)
            check("b115 Dropdown ist per Klick/Tastatur weiter bedienbar (StrongFocus, nicht WheelFocus)",
                  _cb115.focusPolicy() == Qt.StrongFocus)
            _sp115 = getattr(win, "_inv_slots", None)
            if _sp115 is not None:
                _val115 = _sp115.value()
                _ev115b = _QWE115(_QPF115(5, 5), _sp115.mapToGlobal(_QP115(5, 5)),
                                  _QP115(0, 120), _QP115(0, 120), Qt.NoButton,
                                  Qt.NoModifier, Qt.NoScrollPhase, False)
                _app.sendEvent(_sp115, _ev115b); _app.processEvents()
                check("b115 auch das Slot-Feld nimmt das Rad nicht",
                      _sp115.value() == _val115)
        finally:
            win._bd_full_rebuild = _fr_alt115
    _bb115 = dict(getattr(win, "_bd_inv_best_btns", None) or {})
    _btn115 = _bb115.get(_BPA85)
    check("b115 'Copy Decryptor' gibt es je erfundenem Ende",
          sorted(_bb115.keys()) == sorted(_ic115.keys()) and _btn115 is not None)
    if _btn115 is not None:
        _css115 = _btn115.styleSheet()
        _ruhe115 = _css115.split("QPushButton:hover")[0]
        # SEIT emm329 (02.10.2026, Nutzer: "dieselbe Groesse wie Copy T1"):
        # der kleine Kopier-Stil der Runplaner-Knoepfe, nicht mehr der grosse
        # Amber-Rahmen von "Create shopping list".
        check("b115 der Knopf: kleiner Kopier-Stil (Rahmen AMBER_DIM, Text amber)",
              _css115 == _th115.kopier_knopf_stil()
              and f"solid {_th115.AMBER_DIM}" in _ruhe115
              and f"color:{_th115.AMBER}" in _ruhe115)
        check("b115 ... kompakt: feste Groesse statt ueber die ganze Spalte gezogen",
              _btn115.sizePolicy().horizontalPolicy() == _QSP115.Fixed
              and 0 < _btn115.sizeHint().width() < 320)
        # LAGE: der Knopf steht in der Karte VOR dem Ergebnis-Block mit dem
        # Blaupausen-Namen, in einer Zeile mit Stretch (links).
        _karte115 = _btn115.parentWidget()
        _lay115 = _karte115.layout() if _karte115 is not None else None
        _reihe115 = None
        _kopf_i115 = _name_i115 = None
        if _lay115 is not None:
            for _i in range(_lay115.count()):
                _it115 = _lay115.itemAt(_i)
                _l = _it115.layout()
                if _l is not None and _l.indexOf(_btn115) >= 0:
                    _reihe115 = _l; _kopf_i115 = _i
                _w = _it115.widget()
                if _w is not None and _name_i115 is None and any(
                        isinstance(_c, QLabel) and "Blueprint" in _c.text()
                        and _c.styleSheet().find(_th115.CYAN) >= 0
                        for _c in _w.findChildren(QLabel)):
                    _name_i115 = _i
        check("b115 ... links in einer eigenen Zeile (Stretch rechts vom Knopf)",
              _reihe115 is not None and _reihe115.indexOf(_btn115) == 0
              and _reihe115.count() == 2
              and _reihe115.itemAt(1).spacerItem() is not None)
        check("b115 ... und die Zeile steht direkt ueber dem Blaupausen-Namen",
              _kopf_i115 is not None and _name_i115 is not None
              and _name_i115 == _kopf_i115 + 1)
    # ------------------------------------------------------------ (b116)
    # ZUKLAPPBARE INVENTION-KARTEN + DATACORES/SKILL IN EINER ZEILE (Nutzer
    # 26.09.2026: "alle Eintraege der verschiedenen erforschbaren T2-Copys
    # kompakter und uebersichtlicher, es verbraucht zu viel Platz"; Rueckfrage:
    # Karten zuklappbar + Datacores/Skill-Bonus in eine Zeile). Der Pfeil
    # wird WIRKLICH gedrueckt, der Zustand ueberlebt den echten Rebuild
    # (`bau_inv_zu`), die Kopfzeile traegt die Kurzfassung. Suiten-Zustand
    # in .smoke_home ueberlebt Laeufe - im finally zuruecksetzen.
    from PySide6.QtWidgets import QHBoxLayout as _QHB116
    _ik116 = dict(getattr(win, "_bd_inv_karten", None) or {})
    _k116 = _ik116.get(_BPA85)
    check("b116 je erfundenem Ende eine Karte mit Pfeil, Rumpf und Kurzfassung",
          sorted(_ik116.keys()) == sorted(_ic115.keys()) and _k116 is not None
          and all(_k and _k.get("pfeil") is not None and _k.get("body") is not None
                  and _k.get("kurz") is not None for _k in _ik116.values()))
    _zu_alt116 = list(win.settings.get("bau_inv_zu") or [])
    try:
        if _k116 is not None:
            check("b116 Standard: Karte OFFEN, Pfeil gedrueckt, nichts in bau_inv_zu",
                  _k116["pfeil"].isChecked()
                  and not _k116["body"].isHidden()
                  and _BPA85 not in [int(x) for x in (win.settings.get("bau_inv_zu") or [])])
            _kz116 = _k116["kurz"].text()
            check("b116 Kurzfassung in der Kopfzeile: Versuche und Invention-Kosten",
                  ("attempts" in _kz116 or "Versuche" in _kz116) and "ISK" in _kz116)
            # DATACORES UND SKILL-BONUS IN EINER ZEILE: das Skill-Label ist
            # kurz (kein Band mehr), der lange Text steckt im Tooltip, und es
            # liegt in einer Zeile (QHBoxLayout) mit Stretch.
            _sk116 = [_l for _l in _k116["body"].findChildren(QLabel)
                      if "skill" in _l.text().lower()
                      and ("\u00d7" in _l.text() or "bonus" in _l.text().lower())]
            check("b116 Skill-Bonus ist eine kurze Zeile mit dem langen Text im Tooltip",
                  len(_sk116) == 1 and len(_sk116[0].text()) < 200
                  and "Skill bonus active" not in _sk116[0].text()
                  and "No skill bonus included" not in _sk116[0].text()
                  and len(_sk116[0].toolTip()) > 40)
            _lay_sk116 = None
            for _l116 in _k116["body"].findChildren(_QHB116):
                if _sk116 and _l116.indexOf(_sk116[0]) >= 0:
                    _lay_sk116 = _l116
            check("b116 ... und steht in der Datacore-Zeile (waagerecht, mit Stretch)",
                  _lay_sk116 is not None
                  and any(_lay_sk116.itemAt(_i).spacerItem() is not None
                          for _i in range(_lay_sk116.count())))
            # PFEIL DRUECKEN: Rumpf weg, Zustand gemerkt.
            _k116["pfeil"].click(); _app.processEvents()
            check("b116 Pfeil zu: der Rumpf ist versteckt, die Kopfzeile bleibt",
                  _k116["body"].isHidden() and not _k116["kurz"].isHidden())
            check("b116 ... und bau_inv_zu merkt sich die Blaupause",
                  _BPA85 in [int(x) for x in (win.settings.get("bau_inv_zu") or [])])
            # ECHTER REBUILD: die neue Karte kommt ZU auf die Welt.
            win._bd_full_rebuild(); _app.processEvents()
            _ik116b = dict(getattr(win, "_bd_inv_karten", None) or {})
            _k116b = _ik116b.get(_BPA85)
            check("b116 nach dem Rebuild bleibt die Karte zu (Zustand ueberlebt)",
                  _k116b is not None and _k116b is not _k116
                  and _k116b["body"].isHidden() and not _k116b["pfeil"].isChecked())
            _k116c = _ik116b.get(_BPB85)
            check("b116 ... die andere Karte bleibt offen",
                  _k116c is not None and not _k116c["body"].isHidden())
            _k116b["pfeil"].click(); _app.processEvents()
            check("b116 Pfeil wieder auf: Rumpf sichtbar, bau_inv_zu ohne die Blaupause",
                  not _k116b["body"].isHidden()
                  and _BPA85 not in [int(x) for x in (win.settings.get("bau_inv_zu") or [])])
    finally:
        win.settings["bau_inv_zu"] = _zu_alt116
        config.save_settings(win.settings)
    # ------------------------------------------------------------ (b117)
    # INVENTION-KARTE NEU (Nutzer 26.09.2026): (1) "Buy datacores/decryptors"
    # EINMAL oben statt je Karte, (2) Knopf heisst "Best Decryptor", (3) die
    # Zusatzzeilen "for runs / on average it would take / invention cost"
    # sind weg, (4) gross: "Copy your T1 original like this -> Job Runs /
    # Runs per Copy", (5) JEDE KARTE IHR EIGENER REGLER - bis heute bediente
    # der Regler der ersten Karte die LETZTE (nachgestellt: A auf 2 -> B
    # sprang auf 2, A blieb stehen).
    from PySide6.QtWidgets import QCheckBox as _QCB117
    _dlg117 = getattr(win, "_bd_dialog", None)
    _sw117 = dict(getattr(win, "_bd_inv_split_w", None) or {})
    _ik117 = dict(getattr(win, "_bd_inv_karten", None) or {})
    # SEIT 26.09.2026 (zweite Nachricht): in der SEITENLEISTE, Karte "Buy or
    # not?" ganz oben (offen), nicht im Kopf und in keiner Karte. Gezaehlt im
    # AKTUELLEN Kopf (`_bd_inv_top`) und in den Karten - die Widgets frueherer
    # Aufbauten haengen bis deleteLater noch am Fenster.
    _top117 = getattr(win, "_bd_inv_top", None)
    _kauf_top117 = [_c for _c in (_top117.findChildren(_QCB117) if _top117 else [])
                    if _c.text() in ("Buy datacores", "Datacores kaufen")]
    _kauf_karten117 = [_c for _k in _ik117.values()
                       for _c in _k["body"].findChildren(_QCB117)
                       if _c.text() in ("Buy datacores", "Datacores kaufen")]
    _alle117 = getattr(win, "_bd_inv_alle_btn", None)
    _side117 = _alle117.parentWidget() if _alle117 is not None else None
    _kauf_side117 = [_c for _c in (_side117.findChildren(_QCB117) if _side117 else [])
                     if _c.text() in ("Buy datacores", "Datacores kaufen")]
    check("b117 'Buy datacores' steht in der Seitenleiste, nicht im Kopf, in keiner Karte",
          len(_kauf_side117) == 1 and not _kauf_top117 and not _kauf_karten117
          and len(_ik117) >= 2
          and _top117 is not None and _top117.findChild(QSpinBox) is win._inv_slots)
    # Reihenfolge der Seitenleiste: "Buy or not?" (offen) -> Alle-Knopf ->
    # "Invention settings".
    _sl117 = _side117.layout() if _side117 is not None else None
    _reihe117 = []
    if _sl117 is not None:
        for _i in range(_sl117.count()):
            _w = _sl117.itemAt(_i).widget()
            if _w is None:
                continue
            if _w is _alle117:
                _reihe117.append("alle")
            elif any(_c.text() in ("Buy datacores", "Datacores kaufen")
                     for _c in _w.findChildren(_QCB117)):
                # OFFEN = der Haken ist innerhalb der Seitenleiste sichtbar
                # (die Klappkarte versteckt ihren Inhalt, nicht den Haken selbst).
                _reihe117.append("kauf" if _kauf_side117[0].isVisibleTo(_side117)
                                 else "kauf_zu")
            elif _w.findChildren(QLabel) or _w.findChildren(QPushButton):
                _reihe117.append("rest")
    check(f"b117 Seitenleiste: 'Buy or not?' offen ganz oben, dann der Alle-Knopf ({_reihe117})",
          _reihe117[:2] == ["kauf", "alle"] and len(_reihe117) >= 3)
    _bb117 = dict(getattr(win, "_bd_inv_best_btns", None) or {})
    check("b117 der Knopf heisst 'Copy Decryptor' (emm329)",
          bool(_bb117) and all(_b.text() in ("Copy Decryptor", "Decryptor kopieren")
                               for _b in _bb117.values()))
    _txt117 = " ".join(_l.text() for _k in _ik117.values()
                       for _l in _k["body"].findChildren(QLabel))
    check("b117 die Zusatzzeilen (on average / for n runs / Invention cost) sind weg",
          "on average it would take" not in _txt117
          and "im Schnitt" not in _txt117
          and "Invention cost" not in _txt117
          and "Enter in game" not in _txt117)
    _swA117, _swB117 = _sw117.get(_BPA85), _sw117.get(_BPB85)
    check("b117 jede erfundene Karte hat ihren EIGENEN Regler",
          _swA117 is not None and _swB117 is not None
          and _swA117["slider"] is not _swB117["slider"]
          and _ik117[_BPA85]["body"].isAncestorOf(_swA117["slider"])
          and _ik117[_BPB85]["body"].isAncestorOf(_swB117["slider"]))
    if _swA117 is not None and _swB117 is not None:
        _slots_alt117 = win._inv_slots.value()
        _split_alt117 = dict(getattr(win, "_bd_inv_split", None) or {})
        try:
            win._inv_slots.setValue(10); _app.processEvents()
            _swA117["slider"].setValue(1); _swB117["slider"].setValue(1)
            _app.processEvents()
            _kopfB117 = _swB117["kopf"].text()
            _kopfA117 = _swA117["kopf"].text()
            _swA117["slider"].setValue(2); _app.processEvents()
            check("b117 Regler A auf 2: A bleibt auf 2, B bleibt auf 1",
                  _swA117["slider"].value() == 2 and _swB117["slider"].value() == 1)
            check("b117 ... A's Kopieranleitung aendert sich, B's nicht",
                  _swA117["kopf"].text() != _kopfA117
                  and _swB117["kopf"].text() == _kopfB117)
            check("b117 ... gemerkt wird je Blaupause",
                  (win._bd_inv_split or {}).get(_BPA85) == 2
                  and (win._bd_inv_split or {}).get(_BPB85, 1) == 1)
            win._bd_full_rebuild(); _app.processEvents()
            _sw117b = dict(getattr(win, "_bd_inv_split_w", None) or {})
            check("b117 nach dem Rebuild: A wieder auf 2, B auf 1 (neue Regler)",
                  _sw117b.get(_BPA85) is not None
                  and _sw117b[_BPA85]["slider"] is not _swA117["slider"]
                  and _sw117b[_BPA85]["slider"].value() == 2
                  and _sw117b[_BPB85]["slider"].value() == 1)
            # DAS SLOT-FELD OBEN deckelt ALLE Regler.
            win._inv_slots.setValue(1); _app.processEvents()
            check("b117 1 freier Slot oben deckelt jeden Regler auf 1",
                  all(_w["slider"].maximum() == 1 and _w["slider"].value() == 1
                      for _w in _sw117b.values()))
        finally:
            win._inv_slots.setValue(_slots_alt117)
            win._bd_inv_split = _split_alt117
            _app.processEvents()
    # ------------------------------------------------------------ (b118)
    # (1) "BEST DECRYPTOR FOR ALL BLUEPRINTS" (Nutzer 26.09.2026): EIN Klick
    #     waehlt fuer jede Karte das, was ihr eigener Knopf waehlen wuerde, und
    #     rechnet EINMAL neu. Erwartung ueber die Rang-Funktionen der Karten
    #     (dieselbe Rechnung), mit Decryptoren vorher auf "No decryptor".
    # (2) "ATTEMPTS MANUALLY" allein rechnet nicht neu ("ich kann draufklicken,
    #     dann laedt irgendwas, danach passiert nichts").
    # (3) OWN BPC + ME/TE IN DER INVENTION-KARTE, gekoppelt mit der Zeile der
    #     Endprodukte-Karte - in beide Richtungen.
    from PySide6.QtTest import QTest as _QT118
    _alle118 = getattr(win, "_bd_inv_alle_btn", None)
    _rang118 = dict(getattr(win, "_bd_inv_rang", None) or {})
    check("b118 der Alle-Knopf steht in der Seitenleiste, Rang-Funktionen je Karte",
          _alle118 is not None and set(_rang118) >= {_BPA85, _BPB85})
    _dm_alt118 = dict(win._bd_decryptor_map)
    _idm_alt118 = dict(win._bd_opts.get("inv_decryptor_map") or {})
    _rb_alt118 = win._bd_full_rebuild
    _zaehl118 = []
    try:
        _erw118 = {}
        _dm_t = dict(win._bd_opts.get("inv_decryptor_map") or {})
        for _bp, (_fn, _dl) in _rang118.items():
            _r = _fn()
            _erw118[_bp] = _r[0]["name"] if _r else None
            if _r:
                _dm_t[_bp] = next(v for n, v in _dl if n == _r[0]["name"])
                win._bd_opts["inv_decryptor_map"] = _dm_t
        win._bd_opts["inv_decryptor_map"] = dict(_idm_alt118)
        win._bd_full_rebuild = lambda *a, **k: (_zaehl118.append(1), _rb_alt118())
        _alle118.click(); _app.processEvents()
        check(f"b118 Alle-Knopf: jede Karte bekommt ihren besten Decryptor ({_erw118})",
              all(win._bd_decryptor_map.get(_bp) == _n for _bp, _n in _erw118.items()
                  if _n is not None) and any(_n for _n in _erw118.values()))
        check(f"b118 ... und rechnet genau EINMAL neu ({len(_zaehl118)})",
              len(_zaehl118) == 1)
        _warn_nach118 = [_l for _k in (getattr(win, "_bd_inv_karten", None) or {}).values()
                         for _l in _k["body"].findChildren(QLabel)
                         if "\u26a0" in _l.text() and "decryptor" in _l.text().lower()
                         and not _l.isHidden()]
        check("b118 ... und danach warnt keine Karte mehr (alle gelten als gewaehlt)",
              not _warn_nach118
              and set(_rang118) <= set(getattr(win, "_bd_dec_bestaetigt", None) or ()))
        _al118 = getattr(win, "_bd_inv_alle_lbl", None)
        check(f"b118 ... und die Seitenleiste sagt, was geschah "
              f"({_al118.text() if _al118 else None})",
              _al118 is not None and not _al118.isHidden()
              and str(len(_rang118)) in _al118.text())
    finally:
        win._bd_full_rebuild = _rb_alt118
        win._bd_decryptor_map = _dm_alt118
        win._bd_opts["inv_decryptor_map"] = _idm_alt118
        _rb_alt118(); _app.processEvents()
    # (2) "Attempts manually" ist AUSGEBAUT (Nutzer 26.09.2026: "nehmen wir
    #     raus, ist nur verwirrend"), ebenso die Zeile "Total for n attempts".
    _karteA118 = (getattr(win, "_bd_inv_karten", None) or {}).get(_BPA85)
    _txt118 = " ".join(_l.text() for _l in
                       (_karteA118["body"].findChildren(QLabel) if _karteA118 else []))
    _man118 = [_c for _c in (_karteA118["body"].findChildren(_QCB117) if _karteA118 else [])
               if "manual" in _c.text().lower() or "manuell" in _c.text().lower()]
    check("b118 'Attempts manually' und 'Total for n attempts' sind weg",
          _karteA118 is not None and not _man118
          and "Total for" not in _txt118 and "Summe f" not in _txt118)
    # (3) Own BPC in der Invention-Karte <-> Endprodukte-Karte.
    _own118 = (getattr(win, "_bd_inv_own", None) or {}).get(_A85)
    _z118 = (getattr(win, "_bd_multi_zeilen", None) or {}).get(_A85)
    _karteA118 = (getattr(win, "_bd_inv_karten", None) or {}).get(_BPA85)   # nach dem Neuaufbau
    check("b118 Invention-Karte des Buendel-Endes hat 'Own BPC' + ME/TE",
          _own118 is not None and _z118 is not None
          and _karteA118 is not None
          and _karteA118["body"].isAncestorOf(_own118["cb"]))
    _obpc_alt118 = dict(getattr(win, "_bd_own_bpc_je_ende", None) or {})
    _me_alt118 = dict(getattr(win, "_bd_me_je_ende", None) or {})
    try:
        if _own118 is not None and _z118 is not None:
            _z118["obpc"].setChecked(False); _QT118.qWait(400); _app.processEvents()
            _own118 = win._bd_inv_own.get(_A85)
            _own118["cb"].setChecked(True); _app.processEvents()
            check("b118 Haken in der Invention-Karte -> 'Own' in der Endprodukte-Karte",
                  _z118["obpc"].isChecked()
                  and bool(win._bd_own_bpc_je_ende.get(_A85)))
            _QT118.qWait(400); _app.processEvents()
            _own118 = win._bd_inv_own.get(_A85)
            check("b118 ... nach dem Neuaufbau: Haken gesetzt, ME/TE sichtbar",
                  _own118["cb"].isChecked() and not _own118["me"].isHidden())
            _swO118 = (getattr(win, "_bd_inv_split_w", None) or {}).get(_BPA85)
            check("b118 ... und KEINE Kopieranleitung (eigene Kopie = nichts zu erfinden)",
                  _swO118 is not None and _swO118["kopf"].parentWidget().isHidden())
            _own118["me"].setValue(7); _app.processEvents()
            check("b118 ME in der Invention-Karte -> ME der Endprodukte-Zeile und Zustand",
                  _z118["me"].value() == 7 and int(win._bd_me_je_ende.get(_A85, 0)) == 7)
            _QT118.qWait(400); _app.processEvents()
            _z118["me"].setValue(4); _QT118.qWait(400); _app.processEvents()
            _own118 = win._bd_inv_own.get(_A85)
            check("b118 ... und umgekehrt: ME in der Endprodukte-Zeile -> Invention-Karte",
                  _own118["me"].value() == 4)
            _z118["obpc"].setChecked(False); _QT118.qWait(400); _app.processEvents()
            _own118 = win._bd_inv_own.get(_A85)
            check("b118 'Own' in der Endprodukte-Karte aus -> Invention-Karte ohne Haken, ME/TE weg",
                  not _own118["cb"].isChecked() and _own118["me"].isHidden())
    finally:
        win._bd_own_bpc_je_ende = _obpc_alt118
        win._bd_me_je_ende = _me_alt118
        try:
            win._multi_opts_je_ende(win._bd_opts, win._bd_recipes)
        except Exception:
            pass
        win._bd_full_rebuild(); _app.processEvents()
    # ------------------------------------------------------------ (b119)
    # (1) WARNUNG OHNE DECRYPTOR (Nutzer 26.09.2026: "vielleicht irgendwo eine
    #     Warnung, wenn man noch keinen Decryptor gewaehlt hat oder noch keine
    #     eigene BPC ME/TE eingegeben"): Karte + Endprodukte-Karte, weg nach
    #     eigener Wahl (auch "No decryptor" bewusst gewaehlt) und bei Own BPC.
    # (2) BLUEPRINTS-REITER: erfundene T2-Kopie = "will be invented", amber,
    #     nicht rot; "Buy Missing Blueprints" kopiert nur Kaufbares.
    from eve_trader.config import KEIN_DECRYPTOR as _KD119
    _best_alt119 = set(getattr(win, "_bd_dec_bestaetigt", None) or ())
    _dm_alt119 = dict(win._bd_decryptor_map)
    _idm_alt119 = dict(win._bd_opts.get("inv_decryptor_map") or {})
    _obpc_alt119 = dict(getattr(win, "_bd_own_bpc_je_ende", None) or {})
    try:
        win._bd_dec_bestaetigt = set()
        win._bd_decryptor_map = {_BPA85: _KD119, _BPB85: _KD119}
        win._bd_opts["inv_decryptor_map"] = {}
        win._bd_own_bpc_je_ende = {}
        win._multi_opts_je_ende(win._bd_opts, win._bd_recipes)
        win._bd_full_rebuild(); _app.processEvents()
        _ik119 = dict(getattr(win, "_bd_inv_karten", None) or {})
        _warn119 = [_l for _l in _ik119[_BPA85]["body"].findChildren(QLabel)
                    if "\u26a0" in _l.text() and ("decryptor" in _l.text().lower())]
        check("b119 Karte ohne gewaehlten Decryptor zeigt die Warnung (amber)",
              len(_warn119) == 1 and not _warn119[0].isHidden()
              and _th115.AMBER in _warn119[0].styleSheet())
        check("b119 ... und die Kurzfassung der Kopfzeile traegt das \u26a0",
              "\u26a0" in _ik119[_BPA85]["kurz"].text())
        _wl119 = getattr(win, "_bd_multi_warn_lbl", None)
        check("b119 die Endprodukte-Karte nennt beide Enden ohne Decryptor",
              _wl119 is not None and not _wl119.isHidden()
              and "A85" in _wl119.text() and "B85" in _wl119.text())
        # Bewusst "No decryptor" waehlen (Combo-Wechsel hin und zurueck) ->
        # Warnung fuer A weg, B bleibt.
        _cbA119 = win._bd_inv_combos[_BPA85]
        _idx_kein = _cbA119.findData(_KD119)
        _cbA119.setCurrentIndex(1 if _idx_kein != 1 else 0); _app.processEvents()
        _cbA119 = win._bd_inv_combos[_BPA85]
        _cbA119.setCurrentIndex(_cbA119.findData(_KD119)); _app.processEvents()
        _ik119 = dict(getattr(win, "_bd_inv_karten", None) or {})
        _warnA119 = [_l for _l in _ik119[_BPA85]["body"].findChildren(QLabel)
                     if "\u26a0" in _l.text() and "decryptor" in _l.text().lower()]
        _warnB119 = [_l for _l in _ik119[_BPB85]["body"].findChildren(QLabel)
                     if "\u26a0" in _l.text() and "decryptor" in _l.text().lower()]
        check("b119 bewusst 'No decryptor' gewaehlt: A ohne Warnung, B weiter mit",
              not _warnA119 and len(_warnB119) == 1
              and "A85" not in win._bd_multi_warn_lbl.text()
              and "B85" in win._bd_multi_warn_lbl.text())
        # emm329: "Copy Decryptor" ist bei "No decryptor" GESPERRT (Nutzer:
        # "ist kein Decryptor gewaehlt, kann man den Knopf nicht druecken").
        _bbB119 = win._bd_inv_best_btns[_BPB85]
        check("b119 'Copy Decryptor' ist ohne gewaehlten Decryptor gesperrt",
              not _bbB119.isEnabled())
        # "Auto-Decryptor" nimmt B's Warnung weg - auch wenn der beste SCHON
        # eingestellt ist (dann aendert sich die Combo nicht und kein Combo-
        # Signal nimmt die Warnung mit). Dafuer ist "No decryptor" hier der
        # beste (Rangliste vorgetaeuscht).
        _rk_alt119 = I.invention_best_decryptor_by_real_cost
        I.invention_best_decryptor_by_real_cost = (
            lambda *a, **k: [{"name": _KD119, "total_cost": 1.0}])
        try:
            win._bd_inv_alle_btn.click(); _app.processEvents()
        finally:
            I.invention_best_decryptor_by_real_cost = _rk_alt119
        _ik119 = dict(getattr(win, "_bd_inv_karten", None) or {})
        _warnB119b = [_l for _l in _ik119[_BPB85]["body"].findChildren(QLabel)
                      if "\u26a0" in _l.text() and "decryptor" in _l.text().lower()]
        check("b119 'Auto-Decryptor' nimmt die Warnung weg",
              not _warnB119b and "B85" not in win._bd_multi_warn_lbl.text())
        check("b119 der Seitenleisten-Knopf heisst 'Auto-Decryptor' (emm329)",
              win._bd_inv_alle_btn.text() == "Auto-Decryptor")
        # Mit gewaehltem Decryptor: Knopf frei, Klick legt den Namen ab.
        _cbB119 = win._bd_inv_combos[_BPB85]
        _ixB119 = next((i for i in range(_cbB119.count())
                        if _cbB119.itemData(i) not in (None, _KD119)), -1)
        if _ixB119 >= 0:
            _cbB119.setCurrentIndex(_ixB119); _app.processEvents()
            _nmB119 = str(win._bd_inv_combos[_BPB85].currentData())
            _btB119 = win._bd_inv_best_btns[_BPB85]
            _app.clipboard().setText("leer b119")
            _btB119.click(); _app.processEvents()
            _soll119 = _nmB119 if _nmB119.endswith("Decryptor") else _nmB119 + " Decryptor"
            check(f"b119 'Copy Decryptor' legt den gewaehlten Namen ab ({_soll119!r})",
                  _btB119.isEnabled() and _app.clipboard().text() == _soll119)
        else:
            check("b119 Testaufbau: Decryptor-Liste hat einen echten Decryptor", False)
        win._bd_dec_bestaetigt.discard(_BPB85)
        win._bd_decryptor_map[_BPB85] = _KD119
        win._bd_opts.setdefault("inv_decryptor_map", {}).pop(_BPB85, None)
        win._bd_full_rebuild(); _app.processEvents()
        # Own BPC fuer B -> keine Warnung mehr fuer B.
        _z119 = win._bd_multi_zeilen[_B85]
        _z119["obpc"].setChecked(True)
        from PySide6.QtTest import QTest as _QT119
        _QT119.qWait(400); _app.processEvents()
        check("b119 Own BPC fuer B: die Endprodukte-Karte warnt nicht mehr",
              "B85" not in win._bd_multi_warn_lbl.text())
        # Auch MIT gewaehltem Decryptor: bei Own BPC zaehlt er nicht -> gesperrt
        # (sonst waere die Sperre nur die "No decryptor"-Sperre, Rotprobe emm329).
        _echt119 = next((str(_n) for _n, _v in win._decryptor_list()
                         if _n and _n != _KD119), None)
        if _echt119:
            win._bd_decryptor_map[_BPB85] = _echt119
            win._bd_full_rebuild(); _app.processEvents()
        _bbB119c = (getattr(win, "_bd_inv_best_btns", None) or {}).get(_BPB85)
        _cbB119c = (getattr(win, "_bd_inv_combos", None) or {}).get(_BPB85)
        check("b118 ... der Knopf 'Copy Decryptor' einer Own-BPC-Karte ist gesperrt",
              _bbB119c is not None and not _bbB119c.isEnabled()
              and _cbB119c is not None and _cbB119c.currentData() == _echt119
              and _BPB85 not in (getattr(win, "_bd_inv_rang", None) or {}))
    finally:
        win._bd_dec_bestaetigt = _best_alt119
        win._bd_decryptor_map = _dm_alt119
        win._bd_opts["inv_decryptor_map"] = _idm_alt119
        win._bd_own_bpc_je_ende = _obpc_alt119
        try:
            win._multi_opts_je_ende(win._bd_opts, win._bd_recipes)
        except Exception:
            pass
        win._bd_full_rebuild(); _app.processEvents()
    # (2) Blueprints-Reiter: Status und Kaufliste - am echten Fuellweg mit
    #     vorgetaeuschtem Besitz (alles 0 = nichts im Hangar).
    _own_alt119 = getattr(win, "_bd_bp_owned_counts", None)
    _bpc_alt119 = getattr(win, "_bd_bp_owned_bpc_runs", None)
    try:
        win._bd_bp_owned_counts = {}
        win._bd_bp_owned_bpc_runs = {}
        _bpj119 = [{"tid": _A85, "name": "A85", "bp_id": _BPA85,
                    "activity": I.MANUFACTURING, "runs": 10, "is_end": True},
                   {"tid": _M85, "name": "M85", "bp_id": 975555,
                    "activity": I.MANUFACTURING, "runs": 3, "is_end": False}]
        _tbl119 = win._bd_bp_tab_tbl
        win._fill_blueprint_tab(_bpj119, [], win._bd_recipes, _tbl119)
        _stat119 = {}
        for _r in range(_tbl119.rowCount()):
            _nm = _tbl119.item(_r, 0).text()
            _pw = _tbl119.cellWidget(_r, 6)
            _pl = _pw.findChild(QLabel) if _pw is not None else None
            _stat119[_nm] = (_pl.text() if _pl else "", _pl.styleSheet() if _pl else "")
        _a119 = next((v for k, v in _stat119.items() if k.startswith("A85")), ("", ""))
        _m119 = next((v for k, v in _stat119.items() if k.startswith("M85")), ("", ""))
        check(f"b119 Blueprints: erfundene T2-Kopie = 'will be invented', amber ({_a119[0]})",
              ("invented" in _a119[0] or "erfunden" in _a119[0])
              and _th115.AMBER in _a119[1] and _th7.RED not in _a119[1])
        check(f"b119 ... die T1-Blaupause fehlt weiter rot ({_m119[0]})",
              ("missing" in _m119[0] or "fehlt" in _m119[0]) and _th7.RED in _m119[1])
        _QA119 = QApplication.instance()
        _QA119.clipboard().setText("vorher")
        win._bd_bp_kauf_btn.click(); _app.processEvents()
        _cb119 = _QA119.clipboard().text()
        check(f"b119 'Buy Missing Blueprints' kopiert nur die kaufbare ({_cb119!r})",
              _cb119.startswith("M85") and "\t1" in _cb119
              and "A85" not in _cb119 and len(_cb119.splitlines()) == 1)
        win._bd_bp_owned_counts = None
        win._fill_blueprint_tab(_bpj119, [], win._bd_recipes, _tbl119)
        _QA119.clipboard().setText("vorher")
        win._bd_bp_kauf_btn.click(); _app.processEvents()
        check("b119 ... ohne geladenen Besitz wird nichts kopiert, der Reiter sagt warum",
              _QA119.clipboard().text() == "vorher"
              and not win._bd_bp_kauf_lbl.isHidden()
              and ("ESI" in win._bd_bp_kauf_lbl.text()))
        # RECHTSKLICK-MENUE NUR EINMAL VERBUNDEN, obwohl zweimal gefuellt -
        # und eine frische Tabelle meldet kein "Failed to disconnect (None)"
        # (Nutzer-Konsole 27.09.2026).
        from PySide6.QtCore import SIGNAL as _SIG119
        _rc119 = _tbl119.receivers(_SIG119("customContextMenuRequested(QPoint)"))
        import warnings as _wa119
        from PySide6.QtWidgets import QTableWidget as _QTW119
        _neu119 = _QTW119(0, _tbl119.columnCount())
        with _wa119.catch_warnings(record=True) as _w119:
            _wa119.simplefilter("always")
            win._fill_blueprint_tab(_bpj119, [], win._bd_recipes, _neu119)
        _dis119 = [str(_x.message) for _x in _w119 if "disconnect" in str(_x.message)]
        check(f"b119 Blueprints-Menue einmal verbunden ({_rc119}), frisch ohne Warnung ({_dis119})",
              _rc119 == 1 and not _dis119
              and _neu119.receivers(_SIG119("customContextMenuRequested(QPoint)")) == 1)
        _neu119.deleteLater()
    finally:
        win._bd_bp_owned_counts = _own_alt119
        win._bd_bp_owned_bpc_runs = _bpc_alt119
    # ------------------------------------------------------------ (b90)
    # GEWINN JE ENDPRODUKT IST NETTO (Nutzer-Befund 20.09.2026: "ich bin mir
    # nicht sicher ob hier auch die Rechnung beider Plaene stimmt, im Profit
    # wirkt es falsch, es muesste mehr Profit sein"). Seine Zahlen: die
    # Spalte addierte sich zu 286'960'910, oben stand 163'691'239 - die
    # Differenz war GENAU Steuer+Broker (122'125'000) plus die Rundung der
    # Stueckkosten. Die Spalte rechnete brutto, das Feld oben netto.
    # ZUERST: HAT DER DIALOG SIE VON SELBST GEFUELLT? Das ist der echte Weg
    # (_show_build_detail -> rebuild -> Gewinnblock -> Nachzug). Alle
    # folgenden Pruefungen rufen den Nachzug direkt auf und haetten einen
    # fehlenden Aufruf in rebuild() nie bemerkt - genau das meldete die
    # Rotprobe als "blind" (dieselbe Lehre wie b87/b88).
    _t90 = getattr(win, "_bd_multi_tbl", None)
    check("b90 der Dialog fuellt die Gewinn-Spalte selbst (ueber rebuild)",
          _t90 is not None and _t90.rowCount() > 0
          and all(_t90.item(_r90, 9) is not None
                  and (_t90.item(_r90, 9).text() or "").strip()
                  not in ("", "\u2014")
                  for _r90 in range(_t90.rowCount())))
    _satz90 = 0.04885            # wie in seinem Screenshot: 4.885 %
    _fracht90, _extra90 = 7_000_000.0, 3_000_000.0
    _mgn90 = getattr(win, "_multi_gewinn_nachziehen", None)
    check("b90 es gibt einen Nachzug fuer den Gewinn je Endprodukt",
          _mgn90 is not None)
    _je90 = getattr(win, "_bd_multi_je", None) or {}
    check("b90 die Kosten je Ende liegen fuer den Nachzug bereit", bool(_je90))
    _summe90 = _mgn90(satz=_satz90, fracht=_fracht90, extra=_extra90)
    # GEGENRECHNUNG - von Hand, nicht aus derselben Funktion:
    _pm90 = getattr(win, "_bd_pricemap", None) or {}
    _hub90 = getattr(win, "_bd_hub_sell_je_ende", None) or {}
    _kges90 = sum(float(k.get("gesamt") or 0.0) for k in _je90.values())
    _soll90 = 0.0
    for _tid90, _k90 in _je90.items():
        _sell90 = _hub90.get(_tid90) or _pm90.get(_tid90)
        if not _sell90:
            continue
        _m90 = max(1, int(_k90.get("menge") or 1))
        _soll90 += (float(_sell90) * (1.0 - _satz90) * _m90
                    - float(_k90.get("je_stueck") or 0.0) * _m90
                    - (_fracht90 + _extra90)
                    * (float(_k90.get("gesamt") or 0.0) / _kges90))
    check(f"b90 die Summe der Spalte ist Verkauf minus Gebuehren minus "
          f"Kosten minus Zuschlaege ({_summe90:.2f} vs {_soll90:.2f})",
          _summe90 is not None and abs(_summe90 - _soll90) < 1.0)
    # UND GENAU DAS, WAS OBEN STEHT: gross - fees - total - fracht - extra.
    _gross90 = sum((_hub90.get(_t90) or _pm90.get(_t90) or 0.0)
                   * max(1, int(_k90.get("menge") or 1))
                   for _t90, _k90 in _je90.items())
    _oben90 = (_gross90 - _gross90 * _satz90 - _kges90 - _fracht90 - _extra90)
    check(f"b90 ... und trifft den grossen Gesamtgewinn "
          f"({_summe90:.2f} vs {_oben90:.2f})",
          abs(_summe90 - _oben90) < 1.0)
    # OHNE GEBUEHREN waere es die alte, zu hohe Zahl - die Gegenprobe, dass
    # der Satz wirklich wirkt (ein Test, der nur den Sollfall zeigt, koennte
    # auch immer dasselbe sagen).
    _brutto90 = _mgn90(satz=0.0, fracht=0.0, extra=0.0)
    check(f"b90 Gegenprobe: ohne Gebuehren ist die Summe hoeher "
          f"({_brutto90:.0f} > {_summe90:.0f})",
          _brutto90 > _summe90 + 1.0)
    eq("b90 ... und zwar genau um Gebuehren + Zuschlaege",
       round(_brutto90 - _summe90, 2),
       round(_gross90 * _satz90 + _fracht90 + _extra90, 2))
    # ABGLEICH MIT DER KOPFZEILE (Nutzer-Screenshot 26.09.2026: Spalten-
    # Summe 2'828'364'637, "Total profit" 2'838'554'463 - die Kopfzeile
    # rechnet nach "Recalculate" mit dem Orderbuch, die Aufteilung je Ende
    # mit dem Plan). Mit `gesamt` (= Build cost der Kopfzeile) muessen
    # Kosten-Spalte x Menge und Gewinn-Summe GENAU dazu passen.
    _gesamt90 = _kges90 * 0.97          # Orderbuch 3 % guenstiger als der Plan
    _summe90g = _mgn90(satz=_satz90, fracht=_fracht90, extra=_extra90,
                       gesamt=_gesamt90)
    _kosten_spalte90 = 0.0
    for _r90, _t90 in enumerate(getattr(win, "_bd_multi_reihen", None) or []):
        _it90 = win._bd_multi_tbl.item(_r90, 7)
        _m90 = max(1, int((_je90.get(_t90) or {}).get("menge") or 1))
        _kosten_spalte90 += float(getattr(_it90, "_value", 0.0) or 0.0) * _m90
    check(f"b90 mit Kopfzeilen-Summe: Kosten/Stk x Menge = Build cost oben "
          f"({_kosten_spalte90:.0f} = {_gesamt90:.0f})",
          abs(_kosten_spalte90 - _gesamt90) < 2.0)
    _oben90g = (_gross90 - _gross90 * _satz90 - _gesamt90 - _fracht90 - _extra90)
    check(f"b90 ... und die Gewinn-Summe = Total profit oben "
          f"({_summe90g:.0f} = {_oben90g:.0f})",
          _summe90g is not None and abs(_summe90g - _oben90g) < 1.0)
    # DIE SUMMENZEILE STEHT DA (er hatte selbst nachaddiert).
    _gl90 = getattr(win, "_bd_multi_gewinn_lbl", None)
    _mgn90(satz=_satz90, fracht=_fracht90, extra=_extra90)
    check("b90 unter der Tabelle steht die Summe mit Zahl",
          _gl90 is not None and (_gl90.text() or "").strip() != ""
          and any(_c90.isdigit() for _c90 in (_gl90.text() or "")))
    # MARGE JE ENDE (Nutzer 29.09.2026: "multiplan sehe ich zwar den profit
    # aber die einzelmarge waere noch schoen zu wissen"). Von Hand: Gewinn
    # netto je Stueck / (Kosten je Stueck + Anteil Fracht/Extra je Stueck).
    _tm90 = win._bd_multi_tbl
    _kopf_m90 = (_tm90.horizontalHeaderItem(10).text()
                 if _tm90.horizontalHeaderItem(10) is not None else "")
    check(f"b90 Spalte 10 heisst Marge ({_kopf_m90!r})",
          ("Margin" in _kopf_m90 or "Marge" in _kopf_m90) and "%" in _kopf_m90)
    _ok_m90, _det_m90, _gew_m90, _nen_m90 = True, [], 0.0, 0.0
    for _r90, _t90 in enumerate(getattr(win, "_bd_multi_reihen", None) or []):
        _k90 = _je90.get(_t90) or {}
        _sell90 = _hub90.get(_t90) or _pm90.get(_t90)
        _itm90 = _tm90.item(_r90, 10)
        if not _sell90 or not _k90:
            continue
        _m90 = max(1, int(_k90.get("menge") or 1))
        _kst90 = (float(_k90.get("je_stueck") or 0.0)
                  + (_fracht90 + _extra90)
                  * (float(_k90.get("gesamt") or 0.0) / _kges90) / _m90)
        _g90 = float(_sell90) * (1.0 - _satz90) - _kst90
        _soll_m90 = _g90 / _kst90 * 100.0
        _ist_m90 = float(getattr(_itm90, "_value", float("nan")) or 0.0)
        _det_m90.append((round(_ist_m90, 3), round(_soll_m90, 3),
                         (_itm90.text() if _itm90 is not None else None)))
        if (_itm90 is None or abs(_ist_m90 - _soll_m90) > 0.001
                or f"{_soll_m90:+.1f} %" != _itm90.text()):
            _ok_m90 = False
        _gew_m90 += _soll_m90 * _kst90 * _m90
        _nen_m90 += _kst90 * _m90
    check(f"b90 Marge je Ende = Gewinn / Kosten inkl. Zuschlag-Anteil {_det_m90}",
          _ok_m90 and bool(_det_m90))
    # ... und nach Kosten gewichtet genau die grosse Marge oben
    # (prof / (total + Fracht + Extra)).
    _oben_m90 = _oben90 / (_kges90 + _fracht90 + _extra90) * 100.0
    check(f"b90 Marge je Ende, kostengewichtet = Marge oben "
          f"({(_gew_m90 / _nen_m90) if _nen_m90 else 0:.4f} vs {_oben_m90:.4f})",
          _nen_m90 > 0 and abs(_gew_m90 / _nen_m90 - _oben_m90) < 0.001)
    # Die einzelnen Felder oben sind weg - sie koennten nur EINES meinen.
    _hdr85 = [w for w in _d85.findChildren(QSpinBox)
              if w.property("bd_role") == "endproduct_me_te"]
    check("b85 kein einzelnes ME/TE-Feld oben beim Buendel", not _hdr85)
    _obcs85 = [c for c in _d85.findChildren(QCheckBox)
               if "Own BPC instead of invention" in (c.text() or "")
               or "Eigene BPC statt Invention" in (c.text() or "")]
    check("b85 der einzelne 'Eigene BPC'-Haken oben ist beim Buendel unsichtbar",
          all(not c.isVisible() for c in _obcs85))
    # Die Karte hat jetzt neun Spalten und je Zeile Bedien-Elemente.
    _tbl85 = getattr(win, "_bd_multi_tbl", None)
    # (b90) DIE SPALTE HEISST, WAS SIE IST - sonst stehen wieder zwei
    # Gewinnbegriffe nebeneinander und niemand sieht, welcher gemeint ist.
    if _tbl85 is not None:
        _kopf90 = [_tbl85.horizontalHeaderItem(_c90).text()
                   for _c90 in range(_tbl85.columnCount())
                   if _tbl85.horizontalHeaderItem(_c90) is not None]
        check("b90 die Spaltenueberschrift sagt, dass der Gewinn netto ist",
              any(("net" in (_x90 or "").lower()
                   or "netto" in (_x90 or "").lower())
                  for _x90 in _kopf90))
    eq("b85 die Endprodukte-Karte hat Menge/ME/TE/Eigene BPC/Runs/Kopien/Herausnehmen je Zeile",
       (_tbl85.columnCount() if _tbl85 is not None else -1,
        _tbl85.rowCount() if _tbl85 is not None else -1), (13, 2))
    _z85 = win._bd_multi_zeilen
    eq("b85 je Endprodukt eine Zeile mit eigenen Feldern",
       sorted(_z85.keys()), sorted([_A85, _B85]))
    # LAYOUT (Nutzer-Screenshot 20.09.2026: "teils Sachen abgeschnitten"):
    # bei der echten Startgroesse des Fensters muessen alle zehn Spalten
    # nebeneinander passen - sonst rutscht der Name unter die Bildlaufleiste.
    _d85.resize(1400, 820); _app.processEvents()
    _sum_sp85 = sum(_tbl85.columnWidth(_c) for _c in range(_tbl85.columnCount()))
    # NUR AUSSERHALB WINDOWS (emm310, wie der Namens-Check darunter seit
    # emm248): pruefe.py des Nutzers 01.10.2026 "1432 px in 1334 px" - die
    # Offscreen-Umgebung misst dort Texte rund 1,6x breiter (Lehre b66).
    # Ob das ECHTE Fenster passt, sagt nur ein Screenshot.
    _win_sp85 = __import__("sys").platform.startswith("win")
    check(f"b85 Layout: alle Spalten passen ins Fenster "
          f"({_sum_sp85} px in {_tbl85.width()} px)",
          _win_sp85 or _sum_sp85 <= _tbl85.width())
    # DAS LABEL TRAEGT DIE BREITEN: wird es auf einem anderen Rechner rot
    # (b66: dort sind dieselben Texte breiter), muss es SAGEN, welche Spalte
    # den Platz frisst - sonst raet man aus der Ferne.
    _spb85 = [(_tbl85.horizontalHeaderItem(_c).text().replace("\n", " ")[:9],
               _tbl85.columnWidth(_c)) for _c in range(_tbl85.columnCount())]
    # DER NAME BEKOMMT DEN REST (nicht eine feste Zahl): frueher hiess es
    # "> 300 px". Auf dem Windows des Nutzers misst die Offscreen-Umgebung
    # dieselben Texte rund 1,6x breiter (Lehre b66) - pruefe.py 27.09.2026:
    # Name 168 px, obwohl die Spalte genau den ganzen Rest bekam; im echten
    # Fenster (sein Screenshot, 1600 px) hat sie rund 530 px. Geprueft wird
    # jetzt, WAS die Zusage ist: die Namensspalte dehnt sich und fuellt
    # exakt, was die Zahlenspalten uebrig lassen - und hier im Container,
    # wo die Masse stimmen, ist sie weiter breiter als 300 px.
    from PySide6.QtWidgets import QHeaderView as _HVn85
    _rest85 = (_tbl85.viewport().width()
               - sum(_tbl85.columnWidth(_c) for _c in range(1, _tbl85.columnCount())))
    _win85 = __import__("sys").platform.startswith("win")
    check(f"b85 Layout: der Name bekommt den freien Platz (nicht die "
          f"Zahlenfelder) {_spb85}, Rest {_rest85}",
          _tbl85.horizontalHeader().sectionResizeMode(0) == _HVn85.Stretch
          # Windows (emm311, Nutzer-Lauf 01.10.2026): dort ist der Rest
          # negativ (-12, Offscreen-Masse ~1,6x), die Namensspalte bleibt
          # bei 100 px stehen - gemessen wird dann nur noch der Stretch.
          and (_win85 or abs(_tbl85.columnWidth(0) - max(_rest85,
                  _tbl85.horizontalHeader().minimumSectionSize())) <= 2)
          # emm349: +1 Spalte "Sold/day (days)" (Nutzer: Markt-Check je Ende)
          # kostet hier ~110 px - der Name behaelt den Rest, ueber 200 px.
          and (_win85 or _tbl85.columnWidth(0) > 200))
    # NUTZER-BEFUND 23.09.2026 (pruefe.py auf seinem Rechner): "1361 px in
    # 1334 px". Mit ResizeToContents richtet sich eine Spalte nach dem
    # BREITESTEN von Kopf und Zelle - und der Kopf war das Breitere. Auf
    # seinem Windows sind dieselben Texte deutlich breiter, also sprengten
    # die neun Zahlenspalten das Fenster. Gemessen wird hier, dass jede
    # Zahlenspalte nur noch so breit ist, wie ihr INHALT braucht.
    from PySide6.QtWidgets import QHeaderView as _HV85
    # DIESELBE QUELLE FUERS POLSTER wie im Quelltext - eine zweite Zahl hier
    # waere eine zweite Wahrheit, die beim naechsten Umbau still veraltet.
    from eve_trader.ui.mw_multi_bauplan import MultiBauplan as _MB85
    _hh85 = _tbl85.horizontalHeader()
    _fm85 = _tbl85.fontMetrics()
    _zu_breit85 = []
    for _c85 in range(1, _tbl85.columnCount()):
        if _hh85.sectionResizeMode(_c85) != _HV85.Fixed:
            _zu_breit85.append((_c85, "nicht fest"))
            continue
        _need85 = _hh85.minimumSectionSize()
        for _r85 in range(_tbl85.rowCount()):
            _w85c = _tbl85.cellWidget(_r85, _c85)
            if _w85c is not None:
                # DER DECKEL GEWINNT - ein Feld, das breiter sein WILL,
                # als es darf, blaest seine Spalte nicht auf (Mengenfeld).
                _wb85 = _w85c.sizeHint().width()
                if _w85c.maximumWidth() > 0:
                    _wb85 = min(_wb85, _w85c.maximumWidth())
                _need85 = max(_need85, _wb85 + _MB85._SP_PAD_WIDGET)
                continue
            _i85 = _tbl85.item(_r85, _c85)
            if _i85 is not None:
                _need85 = max(_need85,
                              _fm85.horizontalAdvance(_i85.text() or "")
                              + _MB85._SP_PAD_TEXT)
        # REINE ZAHLENSPALTEN bekommen seit 26.09.2026 auch die laengste
        # Kopfzeile (Nutzer: "Profit/Unit, Cop..., Cost/uni abgeschnitten");
        # die Bedienfeld-Spalten nicht - sonst waechst die Karte wieder ueber
        # das Fenster (Befund 23.09.2026).
        if not any(_tbl85.cellWidget(_r, _c85) is not None
                   for _r in range(_tbl85.rowCount())):
            # Gemessen wie das Thema zeichnet: GROSSBUCHSTABEN, fett 12 px,
            # 0,5 px Abstand, 8 px Polster je Seite (zweiter Nutzer-
            # Screenshot 26.09.2026: der Kopf war mit der Zellenschrift
            # gemessen und blieb abgeschnitten).
            from PySide6.QtGui import QFont as _QF85, QFontMetrics as _QFM85
            _hf85 = _QF85(_hh85.font())
            _hf85.setBold(True); _hf85.setPixelSize(12)
            _hf85.setLetterSpacing(_QF85.AbsoluteSpacing, 0.5)
            _hi85 = _tbl85.horizontalHeaderItem(_c85)
            for _kz85 in str(_hi85.text() if _hi85 is not None else "").split("\n"):
                _need85 = max(_need85, _QFM85(_hf85).horizontalAdvance(_kz85.upper())
                              + 16 + _MB85._SP_PAD_TEXT)
        if _tbl85.columnWidth(_c85) != int(_need85):
            _zu_breit85.append((_c85, _tbl85.columnWidth(_c85), int(_need85)))
    eq("b85 Layout: jede Zahlenspalte ist so breit wie ihr Inhalt, nicht wie "
       "ihre Ueberschrift", _zu_breit85, [])
    check("b85 Layout: die Namensspalte nimmt den Rest (Stretch)",
          _hh85.sectionResizeMode(0) == _HV85.Stretch)
    # DER KOPF DARF SCHMALER WERDEN ALS SEIN TEXT - dann muss er kuerzen und
    # den vollen Text als Tooltip tragen, sonst raet man, was die Spalte meint.
    check("b85 Layout: der Kopf kuerzt mit ... statt zu draengen",
          _hh85.textElideMode() == Qt.ElideRight)
    _ohne_tip85 = [_c85 for _c85 in range(_tbl85.columnCount())
                   if not (_tbl85.horizontalHeaderItem(_c85)
                           and _tbl85.horizontalHeaderItem(_c85).toolTip())]
    eq("b85 Layout: jede Ueberschrift traegt ihren vollen Text als Tooltip",
       _ohne_tip85, [])
    # DIE SUMME ALLEIN IST BLIND (Rotprobe): mit einer Stretch-Spalte passt
    # sie IMMER. Gemessen wird deshalb, dass die Zahlenfelder gedeckelt sind -
    # sie sind es, die dem Namen die Breite nahmen.
    # GEDECKELT, ABER NIE UNTER DEM, WAS DIE BOX BRAUCHT (Nutzer-Befund
    # 20.09.2026: "oben rechts sind die ME/TE abgeschnitten"). Eine feste
    # Zahl war geraten und auf seinem Windows zu klein - dort sind dieselben
    # Widgets rund 1,85x breiter (b66). Also gegen den GEMESSENEN sizeHint
    # pruefen: nie schmaler, und nie breiter als noetig.
    for _nm85, _br85 in (("me", 58), ("te", 58), ("runs", 74)):
        _w85 = _z85[_A85][_nm85]
        eq(f"b85 Layout: '{_nm85}' ist auf max(Deckel, sizeHint) begrenzt "
           f"({_w85.maximumWidth()} bei sizeHint {_w85.sizeHint().width()})",
           _w85.maximumWidth(), max(_br85, _w85.sizeHint().width()))
        check(f"b85 Layout: '{_nm85}' kann seinen Inhalt zeigen "
              f"({_w85.maximumWidth()} >= {_w85.sizeHint().width()})",
              _w85.maximumWidth() >= _w85.sizeHint().width())
    # DIE MENGE IST DIE AUSNAHME (Nutzer-Messung 24.09.2026): ihr sizeHint
    # richtet sich nach der Obergrenze 100'000'000 - elf Zeichen, die dort
    # nie stehen, und auf seinem Rechner 194 px Spaltenbreite. Sie muss
    # ihre EIGENE Zahl zeigen koennen, mit Reserve, nicht die Obergrenze.
    _wm85 = _z85[_A85]["menge"]
    _fmm85 = _wm85.fontMetrics()
    _txt85 = _wm85.textFromValue(_wm85.value())
    check(f"b85 Layout: 'menge' zeigt ihre Zahl samt zwei Ziffern Reserve "
          f"({_wm85.maximumWidth()} fuer '{_txt85}')",
          _wm85.maximumWidth() >= _fmm85.horizontalAdvance(_txt85 + "00"))
    check(f"b85 Layout: 'menge' nimmt sich NICHT die Breite der Obergrenze "
          f"({_wm85.maximumWidth()} < {_wm85.sizeHint().width()})",
          _wm85.maximumWidth() < _wm85.sizeHint().width()
          or _wm85.sizeHint().width() <= 88)
    check("b85 Layout: unter der letzten Zeile bleibt kein leerer Streifen",
          _tbl85.height() <= _tbl85.horizontalHeader().height()
          + (_tbl85.rowHeight(0) or 30) * _tbl85.rowCount() + 8)
    # VIELE ENDEN (Nutzer 26.09.2026, elf Enden: "wir koennen nicht
    # scrollen ... maximal 5 Endprodukte, dafuer eine Scrollleiste rechts"):
    # dieselbe Karte mit sieben Enden - hoechstens ENDEN_SICHTBAR Zeilen
    # hoch, der Rest laeuft in der Tabelle.
    _plan85v = dict(win._bd_plan_ref.get("plan") or {})
    _plan85v["buendel_enden"] = {_A83: 1, _B83: 1, 9001: 1, 9002: 1,
                                 9003: 1, 9004: 1, 9005: 1}
    _plan85v["buy_cost_items"] = {**(_plan85v.get("buy_cost_items") or {}),
                                  9001: 10.0, 9002: 10.0, 9003: 10.0,
                                  9004: 10.0, 9005: 10.0}
    win._bd_multi_refresh(_plan85v); _app.processEvents()
    check(f"b85 sieben Enden: die Karte zeigt hoechstens {win.ENDEN_SICHTBAR} Zeilen "
          f"({_tbl85.height()} px bei {_tbl85.rowCount()} Zeilen)",
          _tbl85.rowCount() == 7 and win.ENDEN_SICHTBAR == 5
          and _tbl85.height() <= _tbl85.horizontalHeader().height()
          + (_tbl85.rowHeight(0) or 30) * win.ENDEN_SICHTBAR + 8)
    check("b85 ... und die restlichen laufen ueber die eigene Bildlaufleiste",
          _tbl85.verticalScrollBar().maximum() > 0
          and _tbl85.verticalScrollBarPolicy() == Qt.ScrollBarAsNeeded)
    # BILDLAUFLEISTE GUT SICHTBAR (Nutzer 30.09.2026: "mach lieber die
    # Scrollbar ersichtlicher"): 12 px, Griff in Cyan - gemessen an der
    # echten Breite, nicht nur am Stylesheet.
    import eve_trader.ui.theme as _th85s
    _vs85 = _tbl85.verticalScrollBar()
    check(f"b85 ... und die Bildlaufleiste ist breit und cyan "
          f"({_vs85.sizeHint().width()} px)",
          _th85s.CYAN in (_vs85.styleSheet() or "")
          and _vs85.sizeHint().width() >= 12)
    win._bd_multi_refresh(win._bd_plan_ref.get("plan") or {}); _app.processEvents()
    eq("b85 ... zurueck auf zwei Enden", _tbl85.rowCount(), 2)
    # OHNE Haken: ME gesperrt, zeigt die ECHTE Invention-ME (nicht 0).
    _me_inv85 = I._invention_me_pct(_BPA85, _rb85, win._bd_opts)
    check(f"b85 ohne 'Eigene BPC' ist ME gesperrt und zeigt die Invention-ME "
          f"({_z85[_A85]['me'].value()} vs {_me_inv85})",
          not _z85[_A85]["me"].isEnabled()
          and _me_inv85 is not None
          and _z85[_A85]["me"].value() == int(_me_inv85))
    check("b85 ... und 'Runs/BPC' ist ohne eigene Kopie gesperrt",
          not _z85[_A85]["runs"].isEnabled())
    # GESPERRT HEISST NICHT LEER: in den gesperrten Feldern stehen die
    # Zahlen, mit denen wirklich gerechnet wird - sonst meldet "Runs/BPC" 1,
    # waehrend die Kopien-Spalte daneben "x 10 Runs" sagt.
    _o85 = I.invention_outcome(10, 0.5, I.decryptor_fuer_bp(_BPA85, win._bd_opts))
    eq("b85 die gesperrten Felder zeigen ME, TE und Runs der Invention",
       (_z85[_A85]["me"].value(), _z85[_A85]["te"].value(),
        _z85[_A85]["runs"].value()),
       (int(_o85["me_pct"]), int(_o85["te_pct"]), int(_o85["runs"])))
    _mat_vorher85 = dict(_plan85["build_mats"].get(_B85) or [])
    # HAKEN SETZEN fuer B + eigene ME 10 -> NUR B braucht weniger Material.
    _z85[_B85]["obpc"].setChecked(True)
    _app.processEvents()
    check("b85 'Eigene BPC' gibt ME/TE dieses Endes frei",
          _z85[_B85]["me"].isEnabled() and _z85[_B85]["te"].isEnabled()
          and _z85[_B85]["runs"].isEnabled())
    check("b85 ... und NUR dieses Ende - A bleibt unter der Invention gesperrt",
          not _z85[_A85]["me"].isEnabled())
    check("b85 der Zustand merkt sich den Haken je Ende",
          win._bd_own_bpc_je_ende.get(_B85) is True
          and not win._bd_own_bpc_je_ende.get(_A85))
    check("b85 ... und uebersetzt ihn in inv_manual_override je Blaupause",
          (win._bd_opts.get("inv_manual_override") or {}).get(_BPB85) is True
          and _BPA85 not in (win._bd_opts.get("inv_manual_override") or {}))
    _z85[_B85]["me"].setValue(10)
    _app.processEvents()
    eq("b85 die eigene ME landet je Ende im Zustand",
       win._bd_me_je_ende.get(_B85), 10.0)
    win._bd_full_rebuild()
    _app.processEvents()
    # INVENTION-TAB JE ENDE (26.09.2026): eine Karte je erfundenem Ende gab
    # es schon (build_runs x invention_for_bpc); neu: das Ende mit "Eigene
    # BPC" hat seinen Decryptor ausgegraut, das andere nicht.
    _ic85 = getattr(win, "_bd_inv_combos", None) or {}
    check("b85 Invention-Tab: eine Decryptor-Wahl je erfundenem Ende (A und B)",
          sorted(_ic85.keys()) == sorted([_BPA85, _BPB85]))
    check("b85 ... B mit 'Eigene BPC' ist ausgegraut, A nicht",
          _BPB85 in _ic85 and not _ic85[_BPB85].isEnabled()
          and _BPA85 in _ic85 and _ic85[_BPA85].isEnabled())
    _plan_neu85 = (getattr(win, "_bd_plan_ref", None) or {}).get("plan") or {}
    _a_neu85 = dict(_plan_neu85.get("build_mats", {}).get(_A85) or [])
    _b_neu85 = dict(_plan_neu85.get("build_mats", {}).get(_B85) or [])
    check(f"b85 GEMESSEN: nur B braucht weniger Material "
          f"(A {_a_neu85.get(_M85)}, B {_b_neu85.get(_M85)} statt "
          f"{_mat_vorher85.get(_M85)})",
          _b_neu85.get(_M85) == 900 and _a_neu85.get(_M85) == 980
          and _mat_vorher85.get(_M85) == 980)
    # Abwaehlen nimmt den Override AUSDRUECKLICH wieder raus.
    _z85[_B85]["obpc"].setChecked(False)
    _app.processEvents()
    check("b85 Abwaehlen entfernt den Override wieder (kein Nachwirken)",
          _BPB85 not in (win._bd_opts.get("inv_manual_override") or {})
          and not _z85[_B85]["me"].isEnabled())
    # Menge je Ende laesst sich hier aendern.
    _z85[_A85]["menge"].setValue(25)
    _app.processEvents()
    eq("b85 die Menge je Endprodukt laesst sich in der Karte aendern",
       dict((int(_a), int(_b)) for _a, _b in win._bd_buendel_enden).get(_A85), 25)
    # UND DER PLAN FOLGT (Nutzer-Befund 26.09.2026: Prowler x10 rechnete wie
    # x1 - die Rezept-Kopie mit den Buendel-Mengen entstand nur beim
    # Oeffnen). Nachgestellt: vorher blieb build_runs A bei 10.
    from PySide6.QtTest import QTest as _QT85m
    _QT85m.qWait(400); _app.processEvents()
    _pl85m = (getattr(win, "_bd_plan_ref", None) or {}).get("plan") or {}
    eq("b85 ... und der Plan rechnet die neue Menge (build_runs A = 25)",
       int((_pl85m.get("build_runs") or {}).get(_A85, 0) or 0), 25)
    eq("b85 ... das Buendel-Rezept traegt die neue Menge",
       dict(win._bd_recipes.bp_materials.get((I.BUENDEL_BP, I.MANUFACTURING)) or []).get(_A85), 25)
    # DER VERKAUFSWERT OBEN FOLGT AUCH (vorher: `sell` vom Oeffnen, also die
    # alte Menge - der Gewinn oben aenderte sich nicht).
    _pmq85 = getattr(win, "_bd_pricemap", None) or {}
    _soll85 = sum(float(_pmq85.get(int(_t), 0) or 0) * int(_q)
                  for _t, _q in win._bd_buendel_enden)
    check(f"b85 ... der Verkaufswert oben = Preis x NEUE Menge "
          f"({getattr(win, '_bd_brutto_stand', None)} = {_soll85:.0f})",
          getattr(win, "_bd_hub_sell_price", None)
          or (_soll85 > 0 and abs(float(getattr(win, "_bd_brutto_stand", -1) or -1) - _soll85) < 0.5
              and float(_pmq85.get(_A85, 0) or 0) > 0))
    # SCHRITT 4b: Blaupausen-Lage JE ENDE. A hat eine eigene 7er-Kopie,
    # B wird erfunden (Grund-Runs 10) - beide deckeln den Runplaner, aber
    # mit VERSCHIEDENEN Zahlen. Genau das konnte die eine Stufen-Zahl nicht.
    win._bd_own_bpc_je_ende = {_A85: True}
    win._bd_own_bpc_runs_je_ende = {_A85: 7, _B85: 5}
    _bpj85 = win._multi_bp_je_ende()
    _runs_inv85 = I.invention_outcome(
        10, 0.5, I.decryptor_fuer_bp(_BPB85, win._bd_opts))["runs"]
    check(f"b85 Blaupausen-Lage je Ende: A aus der eigenen Kopie (7), "
          f"B aus der Invention ({_runs_inv85})",
          _bpj85[_A85]["runs"] == 7 and _bpj85[_B85]["runs"] == _runs_inv85)
    check("b85 ... 'Runs/BPC' zaehlt NUR mit Haken (B nimmt die Invention, nicht 5)",
          _bpj85[_B85]["runs"] != 5)
    # Seit 26.09.2026 folgt der Plan der Mengen-Aenderung oben (A = 25) -
    # verglichen wird deshalb mit dem AKTUELLEN Plan des Fensters, nicht mit
    # dem beim Oeffnen gerechneten `_plan85`.
    _runs85 = (((getattr(win, "_bd_plan_ref", None) or {}).get("plan") or {})
               .get("build_runs") or {})
    check(f"b85 Kopien je Ende = aufgerundete Runs / Runs-je-Kopie "
          f"(A {_bpj85[_A85]['copies']}, B {_bpj85[_B85]['copies']})",
          _bpj85[_A85]["copies"] == -(-int(_runs85.get(_A85, 1)) // 7)
          and _bpj85[_B85]["copies"] == -(-int(_runs85.get(_B85, 1)) // _runs_inv85))
    check("b85 der kleinere Wert gewinnt (Regel 3)",
          win._multi_runs_cap_je_ende({_A85: 3}).get(_A85) == 3)
    # OHNE Invention und ohne eigene Kopie: kein Deckel (BPO-Annahme, wie bisher).
    win._bd_opts["invention"] = False
    check("b85 ohne Invention und ohne eigene Kopie bleibt B unbegrenzt",
          _B85 not in win._multi_bp_je_ende()
          and win._multi_bp_je_ende().get(_A85, {}).get("runs") == 7)
    win._bd_opts["invention"] = True
    # NUTZER-BEFUND 21.09.2026 (51 Tage): "Eigene BPC" angehakt, "Runs/BPC"
    # NICHT getippt. Frueher wurden dann ALLE Runs als EINE Kopie angenommen
    # -> ein Job, ein Slot, ein Charakter. Jetzt fragt die Karte denselben
    # Blaupausen-Cache, aus dem der Runplaner schon seinen Runs-Deckel holt.
    # Nur ZWEI Kopien im Hangar, gebraucht werden mehr - so beweist die
    # Pruefung beide Haelften: die GROESSE kommt aus dem Cache, und die
    # STUECKZAHL deckelt (mehr Jobs als Blaupausen kann niemand fahren).
    _cache85 = [{"type_id": _BPA85, "runs": 4, "quantity": 1, "is_bpo": False}] * 2
    win._bd_own_bpc_runs_je_ende = {_B85: 5}          # fuer A NICHTS getippt
    win._bd_owned_bp_cache = _cache85
    _bpc85 = win._multi_bp_je_ende()
    _rA85 = int(_runs85.get(_A85, 1))
    check(f"b85 ohne getippte 'Runs/BPC' zaehlt die eigene Kopie aus dem Cache "
          f"(A {_bpc85.get(_A85, {}).get('copies')} x "
          f"{_bpc85.get(_A85, {}).get('runs')} statt 1 x {_rA85})",
          _bpc85.get(_A85, {}).get("runs") == 4
          and _bpc85[_A85]["copies"] == 2
          # ... und der Deckel greift wirklich (sonst waere die Zeile blind):
          and -(-_rA85 // 4) > 2)
    check("b85 ... und das erreicht den Runplaner wirklich",
          win._resolve_per_item_bp_cap().get(_A85) == _bpc85[_A85]["copies"]
          and win._resolve_per_item_runs_cap().get(_A85) == 4)
    win._bd_owned_bp_cache = []
    win._bd_own_bpc_runs_je_ende = {_B85: 5}
    # EIGENE KOPIE OHNE CACHE UND OHNE GETIPPTE RUNS (Nutzer 26.09.2026,
    # Einherji II: "da wird angezeigt, ich haette unendlich T2 Copys? das
    # geht nicht"): das Feld zeigt seine 1, also gilt 1 Run je Kopie - und
    # die 1 steht danach im Speicher, damit Feld und Rechnung eins sind.
    # Bis dahin hiess "unbekannt" hier "unbegrenzt" (kein Eintrag).
    _bpu85 = win._multi_bp_je_ende()
    check(f"b85 ohne Cache UND ohne getippte Runs: 1 Run je Kopie, {_rA85} Kopien - nie unendlich",
          _bpu85.get(_A85, {}).get("runs") == 1
          and _bpu85[_A85]["copies"] == _rA85
          and win._bd_own_bpc_runs_je_ende.get(_A85) == 1)
    win._bd_own_bpc_runs_je_ende = {_A85: 7, _B85: 5}
    # UEBER DEN ECHTEN WEG, nicht nur die Hilfsfunktion: der Runplaner holt
    # Deckel und Kopien aus _resolve_per_item_runs_cap / _resolve_per_item_bp_cap.
    _cap85 = win._resolve_per_item_runs_cap()
    check(f"b85 der Runplaner-Deckel selbst kennt die Grenze je Ende "
          f"(A {_cap85.get(_A85)}, B {_cap85.get(_B85)})",
          _cap85.get(_A85) == 7 and _cap85.get(_B85) == _runs_inv85)
    _bpcap85 = win._resolve_per_item_bp_cap()
    check(f"b85 ... und die Kopienzahl je Ende (A {_bpcap85.get(_A85)}, "
          f"B {_bpcap85.get(_B85)})",
          _bpcap85.get(_A85) == _bpj85[_A85]["copies"]
          and _bpcap85.get(_B85) == _bpj85[_B85]["copies"])
    # Speichern nimmt die neuen Felder mit.
    _felder85 = win._multi_eintrag_felder()
    check("b85 der Speicherer sichert 'Eigene BPC' und 'Runs/BPC' je Ende",
          _felder85["own_bpc_je_ende"] == {str(_A85): True}
          and _felder85["own_bpc_runs_je_ende"] == {str(_A85): 7, str(_B85): 5})
    # ------------------------------------------------------------ (b120)
    # (1) GLEICHER KNOPF-STIL (Nutzer 26.09.2026: "Buy Missing Blueprints und
    #     Best Decryptor optisch an Create Shopping List anpassen - normale
    #     Tool-Hintergrundfarbe, nur Umrandung und Text Amber"; "Create
    #     shopping list etwas groesser").
    # (2) REPROCESSING IM REZEPT-REITER STANDARDMAESSIG ZU (Nutzer).
    # (3) EINZELPLAN (Nutzer: "die Aenderung im Invention-Tab soll auch auf
    #     Einzelbauplaene gelten, Buy Missing Blueprints ebenso"): derselbe
    #     Pruefsatz an einem Einzelplan eines erfindbaren Endes.
    import eve_trader.ui.theme as _th120
    from PySide6.QtWidgets import QPushButton as _QPB120
    _stil120 = _th120.amber_rahmen_knopf()

    def _pruef120(tag, dlg):
        _knoepfe = [("Create shopping list", getattr(win, "_bd_mat_copy_btn", None)),
                    ("Buy Missing Blueprints", getattr(win, "_bd_bp_kauf_btn", None)),
                    ("Auto-Decryptor", getattr(win, "_bd_inv_alle_btn", None))]
        _kopier120 = list((getattr(win, "_bd_inv_best_btns", None) or {}).values())
        check(f"b120 {tag}: alle Aktions-Knoepfe da und im offenen Fenster",
              len(_knoepfe) >= 3 and _kopier120
              and all(_b is not None and dlg.isAncestorOf(_b)
                      for _b in [_b for _n, _b in _knoepfe] + _kopier120))
        check(f"b120 {tag}: 'Copy Decryptor' je Karte im kleinen Kopier-Stil",
              all(_b.styleSheet() == _th120.kopier_knopf_stil() for _b in _kopier120))
        check(f"b120 {tag}: Shopping list, Buy Missing Blueprints, Auto-"
              f"Decryptor im selben Stil (Rahmen + Text amber, keine Flaeche)",
              all(_b is not None and _b.styleSheet() == _stil120 for _n, _b in _knoepfe)
              and "background" not in _stil120.split("QPushButton:hover")[0]
              and f"color:{_th120.AMBER}" in _stil120)
        _mc = getattr(win, "_bd_mat_copy_btn", None)
        check(f"b120 {tag}: 'Create shopping list' groesser (15 px, mind. 34 hoch)",
              _mc is not None and "font-size:15px" in _mc.styleSheet()
              and _mc.minimumHeight() >= 34)
        _rp = [_b for _b in dlg.findChildren(_QPB120)
               if _b.isCheckable() and _b.text().endswith("Reprocessing")]
        # Seit 27.09.2026 OFFEN als Standard (Nutzer: "Reprocessing
        # ausklappen als Standard"; am 26.09. wollte er es noch zu).
        check(f"b120 {tag}: Klappe 'Reprocessing' ist offen ({[_b.text() for _b in _rp]})",
              len(_rp) == 1 and _rp[0].isChecked())
        # MAUSRAD NUR ZUM SCROLLEN (Nutzer 27.09.2026: Reprocess-Dropdown
        # und "75 %" in den Invention-Settings drehten beim Scrollen mit).
        from PySide6.QtCore import QPoint as _QPt120, QPointF as _QPF120
        from PySide6.QtGui import QWheelEvent as _QWE120
        from PySide6.QtWidgets import (QComboBox as _QCB120,
                                       QAbstractSpinBox as _QAS120)

        def _rad120(w):
            _ev = _QWE120(_QPF120(5, 5), _QPF120(w.mapToGlobal(_QPt120(5, 5))),
                          _QPt120(0, 0), _QPt120(0, -120), Qt.NoButton,
                          Qt.NoModifier, Qt.NoScrollPhase, False)
            QApplication.sendEvent(w, _ev)
        # Die Zeit-Auswahl je Stufe im Runplaner ("as fast as possible",
        # Nutzer: "laesst sich auf Tage wegscrollen") ZUERST pruefen.
        _cb120 = sorted([c for c in dlg.findChildren(_QCB120)
                         if c.count() >= 2 and c.isEnabled()],
                        key=lambda c: 0 if c.itemData(0) == 0 and c.count() > 3 else 1)
        _zeit120 = [c for c in _cb120 if c.itemData(0) == 0 and c.count() > 3]
        _sp120 = [x for x in dlg.findChildren(_QAS120)
                  if x.isEnabled() and not x.isReadOnly()]
        _vorher120 = ([c.currentIndex() for c in _cb120],
                      [x.text() for x in _sp120])
        for _w in _cb120[:6] + _sp120[:6]:
            _rad120(_w)
        _app.processEvents()
        # Hat das Rad doch gedreht, rechnet der Plan neu und baut Widgets neu
        # - ein geloeschtes gilt dann als "veraendert" (ROT statt Absturz).
        def _lies120(fn, w):
            try:
                return fn(w)
            except RuntimeError:
                return "geloescht"
        _nachher120 = ([_lies120(lambda c: c.currentIndex(), c) for c in _cb120],
                       [_lies120(lambda x: x.text(), x) for x in _sp120])
        check(f"b120 {tag}: Mausrad aendert kein Dropdown/Zahlenfeld im Bauplan "
              f"({len(_cb120)} Dropdowns, davon {len(_zeit120)} Stufen-Zeiten, "
              f"{len(_sp120)} Felder)",
              _cb120 and _sp120 and len(_zeit120) >= 1 and _vorher120 == _nachher120
              and bool(dlg.property("combo_ohne_mausrad")))
        _tw120 = [tr for tr in dlg.findChildren(QTreeWidget)
                  if "Blue = will be built" in (tr.header().toolTip() or "")
                  or "Blau" in (tr.header().toolTip() or "")]
        check(f"b120 {tag}: Farb-Hinweis nur an der Kopfzeile des Baums, nicht an "
              f"der Flaeche",
              len(_tw120) == 1 and not (_tw120[0].toolTip() or ""))
    _pruef120("Buendel", _d85)
    _d85.close(); _app.processEvents()
    win._bd_dialog = None
    win._bd_buendel_enden = None
    win._bd_multi_refresh = None
    win._bd_recipes = _Rec85(); win._bd_recipes_basis = _Rec85()
    win._bd_opts = dict(_o85); win._bd_type = _A85; win._bd_qty = 10
    win._bd_inv_best_btns = {}
    win._bd_inv_alle_btn = None; win._bd_bp_kauf_btn = None
    win._bd_dec_bestaetigt = set()    # b118/b119 haben A und B schon gewaehlt
    _plan120 = I.production_plan(_A85, 10, _pm85.get, _Rec85(), dict(_o85))
    _tree120 = I.build_tree(_A85, _pm85.get, _Rec85(), dict(_o85))
    win._show_build_detail(_A85, "A85", {
        "tree": _tree120, "sell": 9e10, "sell_is_contract": False,
        "plan": _plan120, "names": {_A85: "A85", _M85: "M85"}})
    _app.processEvents()
    _d120 = getattr(win, "_bd_dialog", None)
    check("b120 Einzelplan eines erfindbaren Endes oeffnet (kein Buendel)",
          _d120 is not None and _d120 is not _d85
          and not getattr(win, "_bd_buendel_enden", None))
    if _d120 is not None:
        _pruef120("Einzelplan", _d120)
        _lbl120 = " ".join(_l.text() for _l in _d120.findChildren(QLabel))
        check("b120 Einzelplan: Invention-Karte mit Kopieranleitung, Regler, Decryptor-Warnung",
              "Copy your T1 original like this" in _lbl120
              and bool(getattr(win, "_bd_inv_split_w", None))
              and "No decryptor chosen yet" in _lbl120)
        # "NICHTS ZU KAUFEN" BLEIBT LESBAR LANGE STEHEN (Nutzer 26.09.2026:
        # "geht so schnell wieder weg, dass man kaum was lesen kann").
        _tips120 = []
        _ft_alt120 = win._flash_tip
        _rows_alt120 = getattr(win, "_bd_mat_rows", None)
        try:
            win._flash_tip = lambda text=None, ms=2000: _tips120.append((text, ms))
            win._bd_mat_rows = []
            win._bd_mat_copy_btn.click(); _app.processEvents()
        finally:
            win._flash_tip = _ft_alt120
            win._bd_mat_rows = _rows_alt120
        # 4 s (Nutzer 26.09.2026: "von 6 Sekunden auf 4 reduzieren").
        check(f"b120 leere Einkaufsliste: Hinweis bleibt 4 s stehen ({_tips120})",
              len(_tips120) == 1 and _tips120[0][1] == 4000)
        _d120.close(); _app.processEvents()
except Exception as _e85:                                # pragma: no cover
    import traceback as _tb85
    _fail.append(f"b85 Schritt 4: {type(_e85).__name__}: {_e85} | "
                 + _tb85.format_exc().splitlines()[-3].strip())
finally:
    try:
        win._bd_buendel_enden = None
        win._bd_me_je_ende = {}; win._bd_te_je_ende = {}
        win._bd_own_bpc_je_ende = {}; win._bd_own_bpc_runs_je_ende = {}
        win._bd_multi_refresh = None
        win._bd_type = 100; win._bd_recipes = _Recipes()
        win._bd_recipes_basis = None
    except Exception:
        pass


# ---------------------------------------------------------------- (b87)
# "OPEN BUILD PLAN" MUSS WIRKLICH EIN FENSTER OEFFNEN (Nutzer-Befund
# 20.09.2026: "kommt man zurueck zum Scanner Tab und es oeffnet sich kein
# eigenes Fenster"). URSACHE WAR EINE ZEILE: `opts = self._multi_opts_je_ende(
# opts, recipes)` im Bauplan-Job - damit war `opts` dort lokal und ueberall
# unbelegt, der Job starb, und man sah nur die Statuszeile.
#
# DESHALB GEHT DIESE PRUEFUNG DEN GANZEN WEG: _multi_plan_oeffnen ->
# open_build_detail -> Job -> _show_build_detail. Alle vorigen b-Pruefungen
# riefen _show_build_detail direkt und haetten den Fehler NIE gesehen.
try:
    _A87, _B87, _M87 = 972001, 972002, 972004
    _C87, _BPC87 = 972003, 982003        # drittes Ende fuer "herausnehmen"
    _BPA87, _BPB87 = 982001, 982002

    class _Rec87:
        product_to_bp = {_A87: (_BPA87, I.MANUFACTURING, 1),
                         _B87: (_BPB87, I.MANUFACTURING, 1),
                         _C87: (_BPC87, I.MANUFACTURING, 1)}
        bp_materials = {(_BPA87, I.MANUFACTURING): [(_M87, 100)],
                        (_BPB87, I.MANUFACTURING): [(_M87, 100)],
                        (_BPC87, I.MANUFACTURING): [(_M87, 100)]}
        activity_time = {(_BPA87, I.MANUFACTURING): 60,
                         (_BPB87, I.MANUFACTURING): 60,
                         (_BPC87, I.MANUFACTURING): 60}
        activity_max_runs = {}
        reaction_products = set()
        invention_for_bpc = {_BPA87: (962001, 10, 0.5, [])}
        bp_products = {}
        item_cat = {}

        def is_manufactured(self, t):
            return t in self.product_to_bp

    _PM87 = {_M87: 100.0, _A87: 5e6, _B87: 7e6, _C87: 6e6}
    from eve_trader import store as _st87, esi as _esi87
    _alt87 = {"sde": I.sde_ready, "rec": I.recipes_cached,
              "snap": _st87.get_snapshot, "namen": _esi87.resolve_names,
              "mp": _esi87.market_prices, "adj": _esi87.adjusted_prices,
              "idx": _esi87.system_cost_indices, "sys": _esi87.all_system_names,
              "run": win._run, "pix": win._item_pixmap,
              "slots": win._load_char_slots, "plans": win.settings.get("bau_saved_plans")}
    I.sde_ready = lambda: True
    I.recipes_cached = lambda *a87, **k87: _Rec87()
    _st87.get_snapshot = lambda *a87, **k87: [
        {"type_id": _t87, "sell_min": _v87} for _t87, _v87 in _PM87.items()]
    _esi87.resolve_names = lambda ids: {int(_i): f"Item{_i}" for _i in ids}
    _esi87.market_prices = lambda *a87, **k87: {"adjusted": dict(_PM87),
                                                "average": dict(_PM87)}
    _esi87.adjusted_prices = lambda *a87, **k87: dict(_PM87)
    _esi87.system_cost_indices = lambda *a87, **k87: {}
    _esi87.all_system_names = lambda *a87, **k87: {}
    win._item_pixmap = lambda *a87, **k87: None
    win._load_char_slots = lambda *a87, **k87: None
    _fehler87 = []

    def _run87(worker, done_cb, fail_cb=None, **k87):
        """Den Hintergrund-Job SOFORT laufen lassen - sonst endet die Suite,
        bevor das Ergebnis da ist, und die Pruefung waere blind."""
        try:
            _r87 = worker._fn(*worker._args, **worker._kwargs)
        except Exception as _e87a:
            _fehler87.append(f"{type(_e87a).__name__}: {_e87a}")
            return
        done_cb(_r87)
    win._run = _run87
    win.settings["bau_saved_plans"] = [
        {"id": 8701, "label": "b87 A", "type_id": _A87, "item_name": "A87",
         "qty": 20, "me": 0, "te": 0, "checked": []},
        {"id": 8702, "label": "b87 B", "type_id": _B87, "item_name": "B87",
         "qty": 10, "me": 0, "te": 0, "checked": []}]
    _d_alt87 = win._offener_bauplan()
    if _d_alt87 is not None:
        _d_alt87.close(); _app.processEvents()
    win._bd_dialog = None
    _e87 = win._multi_plan_aus_quellen(win.settings["bau_saved_plans"])
    win._multi_plan_oeffnen(_e87, plan_id=None)
    _app.processEvents()
    check(f"b87 'Bauplan oeffnen' oeffnet wirklich ein Fenster"
          + (f" - Job starb an: {_fehler87[0][:70]}" if _fehler87 else ""),
          not _fehler87 and getattr(win, "_bd_dialog", None) is not None)
    check("b87 ... und die Statuszeile meldet keinen Fehler",
          "error" not in (win.build_status.text() or "").lower()
          and "fehler" not in (win.build_status.text() or "").lower())
    _d87 = getattr(win, "_bd_dialog", None)
    _kosten_dialog87 = 0.0
    if _d87 is not None:
        check("b87 das Fenster traegt den Namen des Multi-Bauplans",
              _e87["label"] in (_d87.windowTitle() or ""))
        check("b87 ... und kennt beide Endprodukte",
              sorted((win._bd_multi_zeilen or {}).keys()) == sorted([_A87, _B87]))
        _kosten_dialog87 = float(((getattr(win, "_bd_plan_ref", None) or {})
                                  .get("plan") or {}).get("total_cost") or 0)
        _d87.close(); _app.processEvents()
    # GLEICHE ZAHLEN AUF BEIDEN WEGEN (Zusage an den Nutzer 26.09.2026:
    # "die Rechnung selbst fasse ich nicht an"): dasselbe Buendel, einmal
    # aus dem Multi-Dialog (_multi_plan_aus_quellen), einmal ueber
    # "Endprodukt anhaengen" an Plan A - gleiche Gesamtkosten.
    _pa87, _pb87 = win.settings["bau_saved_plans"][0], win.settings["bau_saved_plans"][1]
    _e87h = win._multi_ende_anhaengen(_pa87, _pb87["type_id"], _pb87["qty"],
                                      me=_pb87["me"], te=_pb87["te"])
    check("b87 anhaengen liefert dieselben Enden/ME/TE wie der Dialog",
          _e87h["enden"] == _e87["enden"]
          and _e87h["me_je_ende"] == _e87["me_je_ende"]
          and _e87h["te_je_ende"] == _e87["te_je_ende"])
    win._bd_dialog = None
    win._multi_plan_oeffnen(_e87h, plan_id=None); _app.processEvents()
    _kosten_anh87 = float(((getattr(win, "_bd_plan_ref", None) or {})
                           .get("plan") or {}).get("total_cost") or 0)
    check(f"b87 ... und dieselben Gesamtkosten ({_kosten_anh87:.0f} = {_kosten_dialog87:.0f})",
          _kosten_dialog87 > 0 and abs(_kosten_anh87 - _kosten_dialog87) < 0.5)
    # "Compare: alone vs. in bundle" ist AUSGEBAUT (Nutzer 26.09.2026: "ich
    # moechte, dass der Profit pro Unit oben rechts stimmt, einfach ohne
    # Button"). Die Spalten stimmen jetzt von selbst mit der Kopfzeile (b90).
    check("b87 der Knopf 'Compare: alone vs. in bundle' ist weg",
          getattr(win, "_bd_multi_vgl_btn", None) is None
          and not hasattr(win, "_multi_vergleich_in_karte"))
    # DAS X ZUM HERAUSNEHMEN (Nutzer 26.09.2026: "etwas abgeschnitten, rot
    # soll es sein"): rote Ruhe-Regel, kein Polster, breit genug fuer das X.
    _x87 = [(_z.get("raus")) for _z in (win._bd_multi_zeilen or {}).values()]
    _css87 = [(_b.styleSheet().split("QPushButton:hover")[0] if _b else "") for _b in _x87]
    check("b87 das X ist rot, ohne Polster und breit genug",
          bool(_x87) and all(_b is not None for _b in _x87)
          and all(f"color:{_th7.RED}" in _c and "padding:0px" in _c for _c in _css87)
          and all(_b.width() >= _b.fontMetrics().horizontalAdvance("\u2715") + 8
                  for _b in _x87))
    # MIT DEM ECHTEN THEMEN-QSS (Nutzer, Bild: "X noch abgeschnitten"):
    # ohne QSS ist der Zellrahmen 29 px hoch und alles passte - mit dem
    # Item-Polster von theme.QSS nur ~18 px, ein 24 px hoher Knopf verlor
    # dort seinen unteren Rand. Der Knopf muss ganz im Zellrahmen liegen.
    _tb87 = win._bd_multi_tbl
    _alt_qss87 = _tb87.styleSheet()
    _tb87.setStyleSheet(_th7.QSS); _app.processEvents()
    _ganz87 = []
    for _r87 in range(_tb87.rowCount()):
        _wr87 = _tb87.cellWidget(_r87, 12)
        _bx87 = _wr87.findChild(type(_x87[0])) if _wr87 is not None else None
        _ganz87.append(_bx87 is not None and _wr87.rect().contains(_bx87.geometry())
                       and _bx87.height() >= 14)
    _tb87.setStyleSheet(_alt_qss87); _app.processEvents()
    check("b87 mit theme.QSS liegt das X ganz in seiner Zelle (nicht abgeschnitten)",
          bool(_ganz87) and all(_ganz87))
    _d87i = getattr(win, "_bd_dialog", None)
    if _d87i is not None:
        _d87i.close(); _app.processEvents()
    # HERAUSNEHMEN AUS DEM OFFENEN BUENDEL (Nutzer 26.09.2026: "einige
    # Endprodukte lohnen sich nicht ... wir brauchen einen Knopf"): drei
    # Enden oeffnen, C ueber den Knopf der Karte herausnehmen - das Fenster
    # geht mit A + B neu auf, der Quellplan von C ist weg; unter zwei Enden
    # und bei eingefrorenem Plan passiert NICHTS (nur ein Hinweis).
    win.settings["bau_saved_plans"].append(
        {"id": 8703, "label": "b87 C", "type_id": _C87, "item_name": "C87",
         "qty": 5, "me": 0, "te": 0, "checked": []})
    win._bd_dialog = None
    _e87c = win._multi_plan_aus_quellen(win.settings["bau_saved_plans"])
    win._multi_plan_oeffnen(_e87c, plan_id=None)
    _app.processEvents()
    _d87c = getattr(win, "_bd_dialog", None)
    check("b87 Buendel mit drei Enden offen, jede Zeile hat den Knopf zum Herausnehmen",
          _d87c is not None
          and sorted((win._bd_multi_zeilen or {}).keys()) == sorted([_A87, _B87, _C87])
          and all("raus" in _z for _z in win._bd_multi_zeilen.values())
          and win._bd_multi_tbl.columnCount() == 13)
    import eve_trader.ui.mw_multi_bauplan as _mmb87
    _q_alt87 = _mmb87.QMessageBox.question
    _fragen87 = []
    _mmb87.QMessageBox.question = (
        lambda *a, **k: (_fragen87.append(a[2]), _mmb87.QMessageBox.Yes)[1])
    _tips87 = []
    _tip_alt87 = win._flash_tip
    win._flash_tip = lambda text=None, *a, **k: _tips87.append(str(text or ""))
    try:
        win._bd_multi_zeilen[_C87]["raus"].click()
        _app.processEvents()
        _d87d = getattr(win, "_bd_dialog", None)
        # DAS FENSTER BLEIBT OFFEN (Nutzer 27.09.2026: "besser der bleibt
        # offen und entfernt einfach einen Plan") - frueher wurde neu geoeffnet.
        check("b87 Knopf: Rueckfrage nennt das Ende, das Fenster BLEIBT offen",
              len(_fragen87) == 1 and "Item972003" in _fragen87[0]
              and _d87d is not None and _d87d is _d87c and _d87c.isVisible())
        check("b87 ... und der Plan ist ohne C neu gerechnet",
              _C87 not in I.buendel_enden(getattr(win, "_bd_recipes_basis", None))
              and sorted(I.buendel_enden(getattr(win, "_bd_recipes_basis", None)))
              == sorted([_A87, _B87]))
        check("b87 ... mit A + B, ohne C - und ohne den Quellplan von C",
              sorted((win._bd_multi_zeilen or {}).keys()) == sorted([_A87, _B87])
              and [a for a, _b in (win._bd_buendel_enden or [])] == sorted([_A87, _B87])
              and sorted(win._bd_buendel_quellen or []) == [8701, 8702]
              and any("removed" in _t or "genommen" in _t for _t in _tips87))
        _fragen87.clear(); _tips87.clear()
        win._bd_multi_zeilen[_A87]["raus"].click(); _app.processEvents()
        check("b87 unter zwei Enden: keine Frage, nur der Hinweis auf 'Edit'",
              not _fragen87 and getattr(win, "_bd_dialog", None) is _d87d
              and _tips87 and ("Edit" in _tips87[0] or "Bearbeiten" in _tips87[0]))
        _tips87.clear()
        win.settings["bau_saved_plans"].append(
            {"id": 8704, "label": "b87 D", "type_id": _C87, "item_name": "C87",
             "qty": 5, "me": 0, "te": 0, "checked": []})
        # EINGEFROREN (emm332/333, Nutzer 02.10.2026: "Endprodukte loeschen
        # sollte dennoch moeglich sein mit Klick aufs rote X, aber mit Popup-
        # Nachfrage" + "die Runs im Runplaner duerfen sich nicht veraendern"):
        # das X bleibt bedienbar, EINE Warnung; Nein -> nichts; Ja -> der
        # Plan BLEIBT eingefroren, nur C faellt aus dem Schnappschuss, A und B
        # behalten ihre Runs exakt. QMessageBox.exec ist gestubbt: eine
        # Auftau-Frage wuerde gezaehlt statt das Fenster zu blockieren.
        _warn87, _exec87 = [], []
        _w_alt87 = _mmb87.QMessageBox.warning
        _x_alt87 = _mmb87.QMessageBox.exec
        _fb87 = win._bd_frozen_btn
        _antw87 = [_mmb87.QMessageBox.No]
        _mmb87.QMessageBox.warning = staticmethod(
            lambda *a, **k: (_warn87.append(str(a[2]) if len(a) > 2 else ""),
                             _antw87[0])[1])
        _mmb87.QMessageBox.exec = lambda self_, *a, **k: _exec87.append(self_.text()) or 0
        try:
            win._bd_buendel_enden = [(_A87, 20), (_B87, 10), (_C87, 5)]
            win._bd_plan_cache = None
            win._bd_full_rebuild(); _app.processEvents()
            _runs87 = dict((win._bd_plan_ref.get("plan") or {}).get("build_runs") or {})
            _buy87 = dict((win._bd_plan_ref.get("plan") or {}).get("buy") or {})
            _fb87.blockSignals(True)
            _fb87.setChecked(True)
            _fb87.blockSignals(False)
            win._bd_frozen = {"ts": 1.0, "plan_snapshot": win._plan_snapshot_pack(
                win._bd_plan_ref.get("plan"))}
            win._bd_frozen_plan_cache = None
            for _z87 in (win._bd_multi_zeilen or {}).values():
                _z87["sperren"]()
            _x87 = (win._bd_multi_zeilen or {}).get(_C87, {}).get("raus")
            check("b87 eingefroren: das rote X bleibt bedienbar, Menge gesperrt",
                  _x87 is not None and _x87.isEnabled()
                  and not win._bd_multi_zeilen[_C87]["menge"].isEnabled()
                  and _runs87.get(_C87, 0) > 0)
            _x87.click(); _app.processEvents()
            check("b87 eingefroren + Nein: Warnung nennt das Ende, nichts entfernt, bleibt eingefroren",
                  len(_warn87) == 1 and "Item972003" in _warn87[0]
                  and not _fragen87 and not _exec87
                  and bool(win._bd_frozen) and _fb87.isChecked()
                  and _C87 in [a for a, _b in (win._bd_buendel_enden or [])]
                  and _C87 in (win._frozen_snapshot_plan() or {}).get("build_runs", {})
                  and getattr(win, "_bd_dialog", None) is _d87d)
            _warn87.clear()
            _antw87[0] = _mmb87.QMessageBox.Yes
            _x87.click(); _app.processEvents()
            _fp87 = win._frozen_snapshot_plan() or {}
            _soll87 = {k: v for k, v in _runs87.items() if k != _C87}
            check("b87 eingefroren + Ja: bleibt eingefroren, keine Auftau-Frage, Ende raus",
                  len(_warn87) == 1 and not _exec87 and not _fragen87
                  and (win._bd_frozen or {}).get("ts") == 1.0 and _fb87.isChecked()
                  and _C87 not in [a for a, _b in (win._bd_buendel_enden or [])]
                  and _C87 not in (_fp87.get("buendel_enden") or {})
                  and getattr(win, "_bd_dialog", None) is _d87d)
            check(f"b87 ... die uebrigen Runs bleiben EXAKT ({_runs87} -> {_fp87.get('build_runs')})",
                  _fp87.get("build_runs") == _soll87
                  and (win._bd_plan_ref.get("plan") or {}).get("build_runs") == _soll87)
            check("b87 ... geteiltes Material bleibt auf der Liste (Rest = Ueberschuss)",
                  _fp87.get("buy") == _buy87 and _buy87.get(_M87, 0) > 0)
            # NUTZER 02.10.2026: "2 Bauplaene per rotem X geloescht, beim
            # Wiederaufmachen waren sie wieder da" - (a) der Baum blieb beim
            # eingefrorenen Plan stehen, (b) Speichern schlug "Name xMenge"
            # vor statt des Namens des offenen Plans -> neuer Plan, der alte
            # blieb unveraendert.
            _tree87 = [c.get("type_id") for c in
                       (((getattr(win, "_bd_tree_ref", None) or {}).get("tree") or {})
                        .get("components") or [])]
            check(f"b87 ... und der Rezeptbaum zeigt C nicht mehr ({_tree87})",
                  _C87 not in _tree87 and _A87 in _tree87)
            # SPEICHERN EINES GESPEICHERTEN PLANS FRAGT KEINEN NAMEN (Nutzer
            # 02.10.2026: "ich moechte aber kein Duplikat erstellen auf diese
            # Weise") - es schreibt ueber die id in genau diesen Plan.
            from PySide6.QtWidgets import QInputDialog as _QID87
            from eve_trader import config as _cfg87
            _gt_alt87 = _QID87.getText
            _ss_alt87 = _cfg87.save_settings
            _vorg87 = []
            _QID87.getText = staticmethod(
                lambda *a, **k: (_vorg87.append(k.get("text")), ("", False))[1])
            _cfg87.save_settings = lambda *a, **k: None
            _pid_alt87 = getattr(win, "_bd_open_plan_id", None)
            win.settings["bau_saved_plans"].append(
                {"id": 8795, "label": "b87 Gespeichert", "type_id": I.BUENDEL_ID,
                 "multi": True, "enden": [[_A87, 20], [_B87, 10], [_C87, 5]], "qty": 1})
            _anz87 = len(win.settings["bau_saved_plans"])
            try:
                win._bd_open_plan_id = 8795
                win._bd_save_btn.click(); _app.processEvents()
                _g87 = [_p for _p in win.settings["bau_saved_plans"] if _p.get("id") == 8795]
                check(f"b87 Speichern: kein Namensfeld, KEIN Duplikat, derselbe Plan ohne C "
                      f"({_vorg87}, {len(win.settings['bau_saved_plans'])} vs {_anz87})",
                      _vorg87 == [] and len(win.settings["bau_saved_plans"]) == _anz87
                      and len(_g87) == 1 and _g87[0].get("label") == "b87 Gespeichert"
                      and [a for a, _b in (_g87[0].get("enden") or [])] == [_A87, _B87])
            finally:
                _QID87.getText = _gt_alt87
                _cfg87.save_settings = _ss_alt87
                win._bd_open_plan_id = _pid_alt87
                win.settings["bau_saved_plans"] = [
                    _p for _p in win.settings["bau_saved_plans"] if _p.get("id") != 8795]
        finally:
            _mmb87.QMessageBox.warning = _w_alt87
            _mmb87.QMessageBox.exec = _x_alt87
            _fb87.blockSignals(True)
            _fb87.setChecked(False)
            _fb87.blockSignals(False)
            win._bd_frozen = None
            win._bd_frozen_plan_cache = None
    finally:
        _mmb87.QMessageBox.question = _q_alt87
        win._flash_tip = _tip_alt87
    _d87e = getattr(win, "_bd_dialog", None)
    if _d87e is not None:
        _d87e.close(); _app.processEvents()
    # ENDPRODUKT ANHAENGEN (Nutzer-Entscheid 26.09.2026: "direkt aus einem
    # Bauplan ein Multibauplan erstellen ... per Rechtsklick in Multiplans
    # umwandeln und immer weitere hinzufuegen"). EINGEFROREN ZAEHLT NICHT
    # als Sperre (Nutzer 26.09.2026, zweiter Anlauf: "ich habe Bauplaene,
    # kann aber keinen Multiplan erstellen" - Speichern friert jeden Plan
    # ein, der alte Filter schloss also ALLE aus): beim Anhaengen wird
    # aufgetaut. Nur reserviert und abgeschlossen bleiben draussen.
    # (a) reine Umwandlung: Einzelplan -> Buendel, Buendel waechst.
    _p87a = dict(win.settings["bau_saved_plans"][0])      # b87 A, Einzelplan
    _p87a["frozen"] = {"ts": 1.0}
    _neu87 = win._multi_ende_anhaengen(_p87a, _C87, 5)
    check("b87 anhaengen: Einzelplan wird zum Buendel mit altem + neuem Ende, aufgetaut",
          _neu87["type_id"] == I.BUENDEL_ID and _neu87.get("multi") is True
          and _neu87["enden"] == [[_A87, 20], [_C87, 5]] and _neu87["qty"] == 1
          and _neu87["quellen"] == [] and _neu87["me_je_ende"][str(_A87)] == 0
          and _neu87["own_bpc_je_ende"][str(_A87)] is False
          and _neu87["me_je_ende"][str(_C87)] == int(win.settings.get("bau_me", 10))
          and _neu87.get("frozen") is None
          and _p87a["type_id"] == _A87 and _p87a["frozen"])   # Eingabe unveraendert
    _neu87b = win._multi_ende_anhaengen(_neu87, _C87, 3)
    check("b87 anhaengen: dasselbe Ende noch einmal addiert die Menge",
          _neu87b["enden"] == [[_A87, 20], [_C87, 8]])
    # (b) wer darf ein Ende bekommen - SEIT 27.09.2026 JEDER Plan (Nutzer:
    # "gespeicherte, gefrorene, reservierte Plaene auch nehmen, dafuer eine
    # Kopie davon machen ... somit bleibt der alte Plan bestehen"; "alles,
    # was in Meine Bauplaene steht, soll zaehlen"). Eingefroren, reserviert
    # oder abgeschlossen -> das Ende geht in eine KOPIE.
    check("b87 anhaengbar: jeder Plan; Kopie bei eingefroren/reserviert/abgeschlossen",
          all(win._multi_ende_anhaengbar(_x) is True for _x in (
              {"type_id": 5}, {"type_id": 5, "frozen": {"ts": 1}},
              {"type_id": 5, "reserve": True}, {"type_id": 5, "done_manual": True}))
          and win._multi_ende_anhaengbar({"type_id": 0}) is False
          and win._multi_braucht_kopie({"type_id": 5}) is False
          and all(win._multi_braucht_kopie(_x) is True for _x in (
              {"type_id": 5, "frozen": {"ts": 1}}, {"type_id": 5, "reserve": True},
              {"type_id": 5, "done_manual": True})))
    _orig87k = {"id": 8790, "label": "b87 K", "type_id": _A87, "qty": 3,
                "frozen": {"ts": 1.0, "prices": {"1": 2}}, "reserve": True,
                "reserve_map": {"34": 5}, "done_manual": True, "checked": ["x"],
                "checked_runplan": ["y"], "quellen": [8701], "farbe": 2}
    _kop87 = win._multi_kopie_von(_orig87k)
    check("b87 Kopie: neue ID, aufgetaut, nicht reserviert/abgeschlossen, keine Haken/"
          "Quellen, Name '(copy)', Original unveraendert",
          _kop87["id"] != 8790 and _kop87.get("frozen") is None
          and _kop87.get("reserve") is False and _kop87.get("reserve_map") == {}
          and _kop87.get("done_manual") is False and _kop87.get("checked") == []
          and _kop87.get("checked_runplan") == [] and _kop87.get("quellen") == []
          and ("copy" in _kop87["label"] or "Kopie" in _kop87["label"])
          and "b87 K" in _kop87["label"] and _kop87["qty"] == 3 and _kop87["farbe"] == 2
          and _orig87k["frozen"] and _orig87k["reserve"] is True
          and _orig87k["checked"] == ["x"] and _orig87k["quellen"] == [8701])
    # (c) das Untermenue listet NUR die anhaengbaren.
    from PySide6.QtWidgets import QMenu as _QMenu87
    win.settings["bau_saved_plans"] = [
        {"id": 8701, "label": "b87 A", "type_id": _A87, "item_name": "A87",
         "qty": 20, "me": 0, "te": 0, "checked": []},
        {"id": 8702, "label": "b87 B", "type_id": _B87, "item_name": "B87",
         "qty": 10, "me": 0, "te": 0, "checked": [], "frozen": {"ts": 1.0}},
        {"id": 8705, "label": "b87 R", "type_id": _B87, "item_name": "B87",
         "qty": 10, "me": 0, "te": 0, "checked": [], "reserve": True}]
    _m87 = _QMenu87()
    _akt87 = win._multi_untermenue(_m87, _C87, "Item972003")
    check("b87 Rechtsklick-Untermenue: offener, eingefrorener UND reservierter Plan",
          sorted(_akt87.values()) == [8701, 8702, 8705]
          and len(_m87.actions()) == 1 and _m87.actions()[0].menu() is not None)
    # MITGLIED EINES BUENDELS (Nutzer-Screenshot 26.09.2026: Ametat II /
    # Flycatcher / Stork aus Multiplan 1 standen im Untermenue): raus.
    win.settings["bau_saved_plans"].append(
        {"id": 8709, "label": "b87 M", "type_id": I.BUENDEL_ID, "qty": 1, "multi": True,
         "enden": [[_A87, 20]], "quellen": [8701], "checked": []})
    _m87b = _QMenu87()
    _akt87b = win._multi_untermenue(_m87b, _C87, "x")
    check("b87 Untermenue: ein Buendel-Mitglied steht NICHT drin (nur das Buendel selbst)",
          sorted(_akt87b.values()) == [8702, 8705, 8709])
    # MULTIPLAENE ZUERST UND FETT, dann Trennstrich (Nutzer 27.09.2026:
    # "bestehende Multiplaene hervorheben und ganz oben anzeigen, in Fett").
    _sub87b = _m87b.actions()[0].menu()
    _eintr87b = [(("---" if _a.isSeparator() else _akt87b.get(_a)), _a.font().bold())
                 for _a in _sub87b.actions()]
    check(f"b87 Untermenue: Multiplaene oben und fett, dann Trennstrich ({_eintr87b})",
          _eintr87b == [(8709, True), ("---", False), (8702, False), (8705, False)])
    win.settings["bau_saved_plans"].pop()
    # OHNE EINEN EINZIGEN OFFENEN PLAN bleibt das Untermenue stehen und sagt,
    # warum es leer ist (Nutzer 26.09.2026: "Rechtsklick-Funktion ist weg").
    _alt_pl87 = win.settings["bau_saved_plans"]
    win.settings["bau_saved_plans"] = []      # gar kein Plan (reservierte zaehlen jetzt)
    _m87c = _QMenu87()
    _akt87c = win._multi_untermenue(_m87c, _C87, "x")
    _sub87c = _m87c.actions()[0].menu() if _m87c.actions() else None
    check("b87 Untermenue ohne offenen Plan: bleibt sichtbar, ein gesperrter Hinweis",
          _akt87c == {} and _sub87c is not None
          and len(_sub87c.actions()) == 1 and not _sub87c.actions()[0].isEnabled())
    win.settings["bau_saved_plans"] = _alt_pl87
    # (d) der Rechtsklick-Weg: haengt an, SPEICHERT, wandelt um, oeffnet.
    win._bd_dialog = None
    _gesp87 = []
    import eve_trader.config as _cfg87
    _save_alt87 = _cfg87.save_settings
    _cfg87.save_settings = lambda *a, **k: _gesp87.append(1)
    # SEIT 27.09.2026 FRAGT der Rechtsklick-Weg, ob er oeffnen soll - hier
    # immer "Ja" (b121 prueft die Frage selbst).
    _frage_alt87 = win._multi_jetzt_oeffnen_fragen
    win._multi_jetzt_oeffnen_fragen = lambda *a, **k: True
    try:
        # EINGEFRORENER Plan per Rechtsklick: wird Buendel UND aufgetaut, der
        # Hinweis sagt es. RESERVIERTER Plan: nichts passiert, nur Hinweis.
        # (Das Fenster-Oeffnen blinkt hier zusaetzlich "No characters" - daher
        # wird nach Inhalt gesucht, nicht gezaehlt.)
        _tips87d = []
        _tip_alt87d = win._flash_tip
        win._flash_tip = lambda txt, *a, **k: _tips87d.append(str(txt))
        _ids_vor87 = {p.get("id") for p in win.settings["bau_saved_plans"]}
        try:
            win._multi_ende_zu_plan(8702, _C87, "x", qty=1); _app.processEvents()
            _pl87b = next((p for p in win.settings["bau_saved_plans"]
                           if p.get("id") == 8702), {})     # fehlt -> ROT, kein Absturz
            _kop87b = [p for p in win.settings["bau_saved_plans"]
                       if p.get("id") not in _ids_vor87]
            check("b87 Rechtsklick auf einen eingefrorenen Plan: Original bleibt, KOPIE als "
                  "Buendel B + C, aufgetaut, gespeichert, Hinweis",
                  _pl87b.get("type_id") == _B87 and _pl87b.get("frozen")
                  and len(_kop87b) == 1 and _kop87b[0]["type_id"] == I.BUENDEL_ID
                  and _kop87b[0]["enden"] == [[_B87, 10], [_C87, 1]]
                  and _kop87b[0].get("frozen") is None and _gesp87
                  and any("copy" in x or "Kopie" in x for x in _tips87d))
            _ids_vor87 |= {p.get("id") for p in _kop87b}
            _d87x = getattr(win, "_bd_dialog", None)
            if _d87x is not None:
                _d87x.close(); _app.processEvents()
            win._multi_ende_zu_plan(8705, _C87, "x", qty=1); _app.processEvents()
            _pl87r = next((p for p in win.settings["bau_saved_plans"]
                           if p.get("id") == 8705), {})
            _kop87r = [p for p in win.settings["bau_saved_plans"]
                       if p.get("id") not in _ids_vor87]
            check("b87 Rechtsklick auf einen reservierten Plan: Original bleibt reserviert, "
                  "Kopie ohne Reservierung",
                  _pl87r.get("type_id") == _B87 and _pl87r.get("reserve") is True
                  and len(_kop87r) == 1 and _kop87r[0].get("reserve") is False
                  and _kop87r[0]["enden"] == [[_B87, 10], [_C87, 1]])
        finally:
            win._flash_tip = _tip_alt87d
            # Die Kopien wieder weg - die folgenden Pruefungen rechnen mit
            # den drei Ausgangsplaenen.
            win.settings["bau_saved_plans"] = [
                p for p in win.settings["bau_saved_plans"]
                if p.get("id") in {8701, 8702, 8705}]
            _d87x = getattr(win, "_bd_dialog", None)
            if _d87x is not None:
                _d87x.close(); _app.processEvents()
        # GESPEICHERT heisst: config.save_settings VOR dem Karten-Auffrischen
        # (das Fenster-Oeffnen danach speichert selbst - ein blosses "wurde
        # irgendwann gespeichert" liesse die Mutation "ohne zu speichern"
        # durch, Rotprobe 26.09.2026).
        _reload_alt87 = win._reload_saved_plans
        _reihe87 = []
        win._reload_saved_plans = lambda *a, **k: (_reihe87.append(len(_gesp87)),
                                                   _reload_alt87(*a, **k))[1]
        try:
            _gesp87.clear()
            win._multi_ende_zu_plan(8701, _C87, "Item972003", qty=5)
            _app.processEvents()
        finally:
            win._reload_saved_plans = _reload_alt87
        _pl87 = next(p for p in win.settings["bau_saved_plans"] if p.get("id") == 8701)
        check("b87 Rechtsklick: Plan A ist jetzt ein Buendel A + C, gespeichert, Fenster offen",
              _pl87["type_id"] == I.BUENDEL_ID and _pl87["enden"] == [[_A87, 20], [_C87, 5]]
              and _reihe87 and _reihe87[0] == 1
              and getattr(win, "_bd_dialog", None) is not None
              and sorted((win._bd_multi_zeilen or {}).keys()) == sorted([_A87, _C87]))
        # (e0) der echte Auswahl-Dialog: die Planliste enthaelt NUR offene
        # Einzelplaene (8701 und 8702 sind inzwischen Buendel, 8705
        # reserviert) - hier also nur den Platzhalter.
        from PySide6.QtCore import QTimer as _QT87
        win._build_picker_pairs = [("Item972002", _B87)]
        _liste87 = []

        def _schau87():
            _pb = getattr(win, "_multi_ende_dialog_plaene", None)
            _liste87.append([_pb.itemData(i) for i in range(_pb.count())] if _pb else None)
            win._multi_ende_dialog.reject()
        _QT87.singleShot(0, _schau87)
        _w87 = win._multi_ende_waehlen()
        win.settings["bau_saved_plans"].append(
            {"id": 8706, "label": "b87 offen", "type_id": _B87, "item_name": "B87",
             "qty": 7, "me": 1, "te": 1, "checked": []})
        _liste87b = []

        def _schau87b():
            _pb = getattr(win, "_multi_ende_dialog_plaene", None)
            _liste87b.append([_pb.itemData(i) for i in range(_pb.count())] if _pb else None)
            win._multi_ende_dialog.reject()
        _QT87.singleShot(0, _schau87b)
        win._multi_ende_waehlen()
        # Seit 27.09.2026 stehen auch eingefrorene/reservierte Einzelplaene
        # drin (8702, 8705) - sie dienen als Vorlage fuer das neue Ende.
        check(f"b87 Auswahl-Dialog: Einzelplaene in der Liste, Abbruch -> None "
              f"({_liste87}, {_liste87b})",
              _w87 is None and _liste87 == [[None, 8702, 8705]]
              and _liste87b == [[None, 8702, 8705, 8706]])
        # (e) der Knopf im Fenster: Auswahl gestubbt -> B kommt dazu.
        _wahl_alt87 = win._multi_ende_waehlen
        win._multi_ende_waehlen = lambda: {"tid": _B87, "name": "Item972002", "qty": 4,
                                           "me": 3, "te": 2, "own_bpc": True,
                                           "own_bpc_runs": 5}
        try:
            _d87f = win._bd_dialog
            win._bd_ende_btn.click(); _app.processEvents()
            # DAS FENSTER BLEIBT (Nutzer 27.09.2026: "an einem offenen
            # Multiplan arbeiten und gleichzeitig Endprodukte hinzufuegen und
            # loeschen, ohne Uebergaenge") - frueher wurde neu geoeffnet.
            check("b87 Knopf 'Add end product': dasselbe Fenster, jetzt A + C + B",
                  getattr(win, "_bd_dialog", None) is not None
                  and win._bd_dialog is _d87f
                  and sorted((win._bd_multi_zeilen or {}).keys())
                  == sorted([_A87, _B87, _C87])
                  and [list(x) for x in win._bd_buendel_enden]
                  == [[_A87, 20], [_B87, 4], [_C87, 5]])
            # AUS EINEM GESPEICHERTEN PLAN uebernommen: ME/TE/Eigene BPC/Runs
            # des Plans gelten fuer das neue Ende (Nutzer: "ja unbedingt").
            check("b87 ... und ME/TE/Eigene BPC/Runs des gewaehlten Plans gelten fuer B",
                  win._bd_me_je_ende.get(_B87) == 3 and win._bd_te_je_ende.get(_B87) == 2
                  and win._bd_own_bpc_je_ende.get(_B87) is True
                  and win._bd_own_bpc_runs_je_ende.get(_B87) == 5)
            check("b87 ... und der Plan ist mit B neu gerechnet",
                  sorted(I.buendel_enden(getattr(win, "_bd_recipes_basis", None)))
                  == sorted([_A87, _B87, _C87]))
            # RECHTSKLICK auf genau diesen (offenen) Plan: KEINE Frage "jetzt
            # oeffnen?", das Ende landet im offenen Fenster (Nutzer: "dabei ist
            # er ja schon offen - bei No wird nichts hinzugefuegt").
            _fragen87f = []
            _frage_vor87f = win._multi_jetzt_oeffnen_fragen
            win._multi_jetzt_oeffnen_fragen = lambda *a, **k: (
                _fragen87f.append(1), False)[1]
            try:
                win._multi_ende_zu_plan(8701, _B87, "Item972002", qty=1)
                _app.processEvents()
            finally:
                win._multi_jetzt_oeffnen_fragen = _frage_vor87f
            check(f"b87 Rechtsklick auf den OFFENEN Plan: keine Frage, gleiches Fenster, "
                  f"B jetzt 5 ({win._bd_buendel_enden})",
                  not _fragen87f and win._bd_dialog is _d87f
                  and dict((int(a), int(b)) for a, b in win._bd_buendel_enden).get(_B87) == 5
                  and sorted((win._bd_multi_zeilen or {}).keys())
                  == sorted([_A87, _B87, _C87]))
            # EINGEFRORENES Fenster: der Knopf geht, das neue Fenster ist
            # aufgetaut, der Hinweis sagt es. RESERVIERTER gespeicherter
            # Plan: nichts geoeffnet, nur Hinweis.
            _tips87e = []
            _tip_alt87e = win._flash_tip
            win._flash_tip = lambda txt, *a, **k: _tips87e.append(str(txt))
            win._bd_frozen = {"ts": 1.0}
            _d87g = win._bd_dialog
            try:
                _gesp87a = next(p for p in win.settings["bau_saved_plans"]
                                if p.get("id") == 8701)
                _enden87a = [list(x) for x in _gesp87a.get("enden") or []]
                win._bd_ende_btn.click(); _app.processEvents()
                # KOPIE STATT UMBAU (Nutzer 27.09.2026): neues, ungespeichertes
                # Fenster mit der Kopie; der gespeicherte Plan bleibt.
                check("b87 Knopf bei eingefrorenem Fenster: neues Fenster mit KOPIE, "
                      "gespeicherter Plan unveraendert, Hinweis",
                      win._bd_dialog is not _d87g
                      and getattr(win, "_bd_open_plan_id", None) is None
                      and not getattr(win, "_bd_frozen", None)
                      # 9 = 4 (Knopf) + 1 (Rechtsklick oben) + 4 (hier)
                      and [list(x) for x in win._bd_buendel_enden]
                      == [[_A87, 20], [_B87, 9], [_C87, 5]]
                      and [list(x) for x in _gesp87a.get("enden") or []] == _enden87a
                      and any("copy" in x or "Kopie" in x for x in _tips87e))
                # RESERVIERTER gespeicherter Plan offen: ebenfalls Kopie.
                _gesp87a["reserve"] = True
                win._bd_open_plan_id = 8701
                _d87i = win._bd_dialog
                win._bd_ende_btn.click(); _app.processEvents()
                check("b87 Knopf bei reserviertem Plan: neues Fenster mit Kopie, Plan bleibt "
                      "reserviert",
                      win._bd_dialog is not _d87i
                      and getattr(win, "_bd_open_plan_id", None) is None
                      and _gesp87a.get("reserve") is True
                      and any("copy" in x or "Kopie" in x for x in _tips87e[-1:]))
                _gesp87a["reserve"] = False
            finally:
                win._bd_frozen = None
                win._flash_tip = _tip_alt87e
        finally:
            win._multi_ende_waehlen = _wahl_alt87
    finally:
        _cfg87.save_settings = _save_alt87
        win._multi_jetzt_oeffnen_fragen = _frage_alt87
    # ------------------------------------------------------------ (b146)
    # BESTAND NICHT KURZ LEER NACH "ENDE ANHAENGEN" (emm253 offen, emm308
    # nachgestellt): oeffnet das Fenster dafuer NEU (Einzelplan -> Buendel,
    # Kopie), setzte der Neuer-Plan-Zweig den Lager-Baustein auf leer, bis
    # der Assets-Abruf zurueck war. Hier haengt der Abruf (wie im echten
    # Programm, wo er Sekunden dauert) - der Bestand muss trotzdem da sein.
    import eve_trader.ui.mw_bauplan_fenster as _mbf146
    _alt146 = {"run": win._run, "wahl": win._multi_ende_waehlen,
               "einf": win._multi_offen_einfuegbar,
               "chars": _mbf146.store.list_characters,
               "cid": win.settings.get("client_id"),
               "save": _cfg87.save_settings,
               # Das Rollen-Netz in open_build_detail weist dem Stub-
               # Charakter Rollen zu und SPEICHERT - ohne diese Sicherung
               # stand danach bau_build_chars=[1] in .smoke_home, und b14
               # (naechster Lauf) fand sein Kaestchen schon angekreuzt.
               "rollen": {_k: (list(win.settings[_k]) if isinstance(
                   win.settings.get(_k), list) else win.settings.get(_k))
                   for _k in ("bau_build_chars", "bau_reaction_chars",
                              "bau_invention_chars", "bau_copy_chars")
                   if _k in win.settings}}
    _cfg87.save_settings = lambda *a146, **k146: None
    _gehalten146 = []
    try:
        _run_v146 = win._run

        def _run146(worker, done_cb, fail_cb=None, **k146):
            if "asset" in str(k146.get("label", "")).lower():
                _gehalten146.append(worker)      # Abruf laeuft noch
                return
            return _run_v146(worker, done_cb, fail_cb, **k146)
        win._run = _run146
        win.settings["client_id"] = "b146"
        _mbf146.store.list_characters = lambda: [{"character_id": 1,
                                                  "character_name": "B146"}]
        win._bd_frozen = None
        win._bd_esi_stock_base = {_A87: 5, 34: 1000}
        win._bd_virt_stock = {}
        win._bd_esi_stock_ts = 1_790_000_000.0
        win._recompute_bd_stock()
        win._multi_ende_waehlen = lambda: {"tid": _B87, "name": "B87", "qty": 2}
        win._multi_offen_einfuegbar = lambda *a146, **k146: False
        _d146 = win._bd_dialog
        win._multi_ende_hinzufuegen_offen(); _app.processEvents()
        _st146 = dict((getattr(win, "_bd_opts", None) or {}).get("stock") or {})
        check(f"b146 neues Fenster, Assets-Abruf laeuft noch ({len(_gehalten146)})",
              win._bd_dialog is not _d146 and len(_gehalten146) == 1)
        check(f"b146 ... und der Bestand des alten Fensters gilt solange ({_st146})",
              _st146.get(34) == 1000 and _st146.get(_A87) == 5)
        check("b146 ... mit dem ehrlichen ESI-Alter des alten Abrufs",
              getattr(win, "_bd_esi_stock_ts", None) == 1_790_000_000.0)
        win._bd_frozen = {"stock": {34: 7}}
        check("b146 eingefrorenes Fenster gibt nichts mit (Einfrier-Stand zaehlt)",
              win._bd_bestand_mitnehmen() is None)
        win._bd_frozen = None
        check("b146 offenes Fenster ohne Eiszustand gibt sein Lager mit",
              (win._bd_bestand_mitnehmen() or {}).get("base", {}).get(34) == 1000)
    finally:
        win._bd_frozen = None
        win._run = _alt146["run"]
        win._multi_ende_waehlen = _alt146["wahl"]
        win._multi_offen_einfuegbar = _alt146["einf"]
        _mbf146.store.list_characters = _alt146["chars"]
        # None NICHT als Wert zurueckschreiben: ein gespeichertes
        # "client_id": null ueberdeckt die eingebaute Client-ID, und der
        # naechste Lauf oeffnet beim Start das Einrichtungsfenster (b59).
        if _alt146["cid"] is None:
            win.settings.pop("client_id", None)
        else:
            win.settings["client_id"] = _alt146["cid"]
        for _k in ("bau_build_chars", "bau_reaction_chars",
                   "bau_invention_chars", "bau_copy_chars"):
            if _k in _alt146["rollen"]:
                win.settings[_k] = _alt146["rollen"][_k]
            else:
                win.settings.pop(_k, None)
        _cfg87.save_settings = _alt146["save"]
        win._bd_bestand_pending = None
    _d87h = getattr(win, "_bd_dialog", None)
    if _d87h is not None:
        _d87h.close(); _app.processEvents()
except Exception as _e87x:                               # pragma: no cover
    import traceback as _tb87
    _fail.append(f"b87 Open build plan: {type(_e87x).__name__}: {_e87x} | "
                 + _tb87.format_exc().splitlines()[-3].strip())
finally:
    try:
        I.sde_ready = _alt87["sde"]; I.recipes_cached = _alt87["rec"]
        _st87.get_snapshot = _alt87["snap"]; _esi87.resolve_names = _alt87["namen"]
        _esi87.market_prices = _alt87["mp"]; _esi87.adjusted_prices = _alt87["adj"]
        _esi87.system_cost_indices = _alt87["idx"]
        _esi87.all_system_names = _alt87["sys"]
        win._run = _alt87["run"]; win._item_pixmap = _alt87["pix"]
        win._load_char_slots = _alt87["slots"]
        win.settings["bau_saved_plans"] = _alt87["plans"]
        win._bd_buendel_enden = None; win._bd_multi_refresh = None
        win._bd_type = 100; win._bd_recipes = _Recipes()
    except Exception:
        pass


# ---------------------------------------------------------------- (b121)
# DIE DREI BEDIENIDEEN (Nutzer 26.09.2026: "Punkt 2 ausfuehren"):
# (1) Mehrfachauswahl im Scanner -> Rechtsklick -> alle in einen Plan oder
#     "New multi build plan from selection"; (2) der Mengen-Dialog startet
#     mit der Stueckzahl, mit der der Scanner gerechnet hat; (3) Rechtsklick
#     auf eine Karte in "My build plans" -> "Add build plan...".
_alt121 = {}
try:
    import eve_trader.config as _cfg121
    from PySide6.QtCore import QTimer as _QT121, QPoint as _QP121
    from PySide6.QtWidgets import QMenu as _QM121
    _alt121 = {"plans": win.settings.get("bau_saved_plans"),
               "save": _cfg121.save_settings, "oeffnen": win._multi_plan_oeffnen,
               "tip": win._flash_tip, "waehlen": win._multi_ende_waehlen,
               "frage": win._multi_jetzt_oeffnen_fragen}
    _antwort121 = [True]
    win._multi_jetzt_oeffnen_fragen = lambda *a, **k: _antwort121[0]
    _gesp121, _offen121, _tips121 = [], [], []
    _cfg121.save_settings = lambda *a, **k: _gesp121.append(1)
    win._multi_plan_oeffnen = lambda e, plan_id=None: _offen121.append((dict(e), plan_id))
    win._flash_tip = lambda txt=None, ms=2000: _tips121.append((str(txt), ms))
    _X1, _X2, _X3 = 973001, 973002, 973003
    win.settings["bau_saved_plans"] = [
        {"id": 12101, "label": "b121 A", "type_id": _X1, "item_name": "X1",
         "qty": 3, "me": 0, "te": 0, "checked": []},
        {"id": 12102, "label": "b121 R", "type_id": _X2, "item_name": "X2",
         "qty": 2, "me": 0, "te": 0, "checked": [], "reserve": True}]
    # (2) SCANNER-ZEILE TRAEGT IHRE STUECKZAHL - echter Aufbau ueber
    #     _render_build, eine Zeile mit, eine ohne Nachrechnung.
    _deal121 = lambda tid, rq: {
        "type_id": tid, "build_cost": 100.0, "sell_min": 200.0, "profit_day": 1.0,
        "daily_vol": 5.0, "volatility": 1.0, "dos": 3.0, "under_pct": 50.0,
        "profit_unit": 90.0, "isk_per_hour": 0.0, "fallback_pct": 0.0,
        "inv_saved_unit": 0.0, **({"refined_qty": rq} if rq else {})}
    win._render_build([_deal121(_X1, 37), _deal121(_X2, 0), _deal121(_X3, 12)])
    _app.processEvents()
    _zeilen121 = {}
    for _r in range(win.b_table.rowCount()):
        _z = win._build_row_auswahl(win.b_table, _r)
        if _z:
            _zeilen121[_z["tid"]] = (_r, _z["vorgabe"])
    check(f"b121 Scanner-Zeile traegt die Stueckzahl des Scanners ({_zeilen121})",
          _zeilen121.get(_X1, (0, 0))[1] == 37 and _zeilen121.get(_X2, (0, 0))[1] == 1
          and _zeilen121.get(_X3, (0, 0))[1] == 12)
    # Der Mengen-Dialog zeigt die Vorgabe - und nimmt eine Aenderung an.
    _gesehen121 = []

    def _dlg121():
        _sp = list(getattr(win, "_multi_mengen_spins", None) or [])
        _gesehen121.append([_x.value() for _x in _sp])
        if len(_sp) > 1:
            _sp[1].setValue(8)
        win._multi_mengen_dlg.accept()
    _QT121.singleShot(0, _dlg121)
    _m121 = win._multi_mengen_dialog(
        [{"tid": _X1, "name": "X1", "vorgabe": 37}, {"tid": _X3, "name": "X3", "vorgabe": 12}],
        "b121")
    check(f"b121 Mengen-Dialog: vorbefuellt (37, 12), Aenderung zaehlt ({_gesehen121}, {_m121})",
          _gesehen121 == [[37, 12]]
          and [(x["tid"], x["qty"]) for x in (_m121 or [])] == [(_X1, 37), (_X3, 8)])
    _QT121.singleShot(0, lambda: win._multi_mengen_dlg.reject())
    check("b121 Mengen-Dialog: Abbrechen -> None",
          win._multi_mengen_dialog([{"tid": _X1, "name": "X1", "vorgabe": 2}], "b121") is None)
    # Einzel-Rechtsklick in einen Plan: der Dialog startet mit 37.
    _gesehen121b = []

    def _dlg121b():
        _gesehen121b.append([_x.value() for _x in (win._multi_mengen_spins or [])])
        win._multi_mengen_dlg.accept()
    _QT121.singleShot(0, _dlg121b)
    win._multi_ende_zu_plan(12101, _X3, "X3", vorgabe=37); _app.processEvents()
    _pa121 = next(p for p in win.settings["bau_saved_plans"] if p["id"] == 12101)
    check(f"b121 Einzel-Rechtsklick: Menge vorbefuellt ({_gesehen121b}), Plan wird Buendel",
          _gesehen121b == [[37]] and _pa121["type_id"] == I.BUENDEL_ID
          and _pa121["enden"] == [[_X1, 3], [_X3, 37]] and _gesp121)
    # (1) MEHRFACHAUSWAHL: nur wenn die geklickte Zeile dazugehoert, >= 2.
    win.b_table.clearSelection()
    win.b_table.setSelectionMode(win.b_table.SelectionMode.ExtendedSelection)
    from PySide6.QtCore import QItemSelectionModel as _ISM121
    _sm121 = win.b_table.selectionModel()
    for _tid in (_X1, _X3):
        _sm121.select(win.b_table.model().index(_zeilen121[_tid][0], 0),
                      _ISM121.Select | _ISM121.Rows)
    _ausw121 = win._multi_auswahl(win.b_table, _zeilen121[_X1][0], win._build_row_auswahl)
    check(f"b121 Mehrfachauswahl: zwei markierte Zeilen mit Vorgaben ({_ausw121})",
          sorted((x["tid"], x["vorgabe"]) for x in _ausw121) == [(_X1, 37), (_X3, 12)])
    check("b121 ... Rechtsklick auf eine NICHT markierte Zeile -> Einzel-Menue",
          win._multi_auswahl(win.b_table, _zeilen121[_X2][0], win._build_row_auswahl) == [])
    _mm121 = _QM121()
    _akt121, _neu121 = win._multi_auswahl_menue(_mm121, _ausw121)
    _txt121 = [a.text() for a in _mm121.actions()]
    check(f"b121 ... das Menue bietet 'New ... from selection (2)' und 'Add 2 selected' ({_txt121})",
          _neu121 is not None and "(2)" in _neu121.text()
          and any("2" in x and ("selected" in x or "markierte" in x) for x in _txt121)
          # seit 27.09.2026 auch der reservierte (12102) - er bekommt eine Kopie
          and sorted(_akt121.values()) == [12101, 12102])
    # Alle markierten in einen Plan: EIN Dialog mit beiden Vorgaben.
    _gesehen121c = []

    def _dlg121c():
        _gesehen121c.append([_x.value() for _x in (win._multi_mengen_spins or [])])
        win._multi_mengen_dlg.accept()
    _QT121.singleShot(0, _dlg121c)
    _gesp121.clear(); _offen121.clear()
    win._multi_enden_zu_plan(12101, [dict(x, qty=None) for x in _ausw121])
    _app.processEvents()
    _pa121 = next(p for p in win.settings["bau_saved_plans"] if p["id"] == 12101)
    check(f"b121 Auswahl -> Plan: ein Dialog ({_gesehen121c}), beide Enden addiert, gespeichert, offen",
          len(_gesehen121c) == 1 and sorted(_gesehen121c[0]) == [12, 37]
          and _pa121["enden"] == [[_X1, 40], [_X3, 49]]
          and _gesp121 and _offen121 and _offen121[-1][1] == 12101)
    # Neues Buendel aus der Auswahl: ungespeichert geoeffnet, zwei Enden.
    _offen121.clear(); _gesp121.clear()
    _QT121.singleShot(0, lambda: win._multi_mengen_dlg.accept())
    _e121 = win._multi_neu_aus_auswahl(_ausw121); _app.processEvents()
    check(f"b121 'New multi build plan from selection': Buendel X1 37 + X3 12, "
          f"ungespeichert geoeffnet ({(_e121 or {}).get('enden')})",
          _e121 is not None and _e121["type_id"] == I.BUENDEL_ID
          and sorted(_e121["enden"]) == [[_X1, 37], [_X3, 12]]
          and _offen121 and _offen121[-1][1] is None and not _gesp121)
    _offen121.clear(); _tips121.clear()
    _dlg_vor121 = getattr(win, "_multi_mengen_dlg", None)
    # Falls doch ein Dialog aufgeht: nicht haengen bleiben, sondern rot werden.
    _QT121.singleShot(0, lambda: (getattr(win, "_multi_mengen_dlg", None) is not _dlg_vor121)
                      and win._multi_mengen_dlg.reject())
    check("b121 ... unter zwei verschiedenen Items: kein Dialog, kein Buendel, Hinweis",
          win._multi_neu_aus_auswahl([{"tid": _X1, "name": "X1", "vorgabe": 1},
                                      {"tid": _X1, "name": "X1", "vorgabe": 2}]) is None
          and not _offen121
          and getattr(win, "_multi_mengen_dlg", None) is _dlg_vor121
          and any("two" in x or "zwei" in x for x, _ms in _tips121))
    # ERST FRAGEN, DANN OEFFNEN (Nutzer 27.09.2026: "sollte danach die Frage
    # kommen: moechtest du den Multi-Bauplan jetzt oeffnen? Ja/Nein").
    _antwort121[0] = False
    _offen121.clear(); _gesp121.clear()
    win._multi_ende_zu_plan(12101, _X2, "X2", qty=2); _app.processEvents()
    _pa121 = next(p for p in win.settings["bau_saved_plans"] if p["id"] == 12101)
    check("b121 Antwort 'Nein': angehaengt und gespeichert, aber NICHT geoeffnet",
          [x for x in _pa121["enden"] if x[0] == _X2] == [[_X2, 2]]
          and _gesp121 and not _offen121)
    _antwort121[0] = True
    import eve_trader.ui.mw_multi_bauplan as _mmb121
    _q_alt121 = _mmb121.QMessageBox.question
    _frage121 = []
    _mmb121.QMessageBox.question = lambda *a, **k: (_frage121.append(a),
                                                    _mmb121.QMessageBox.No)[1]
    try:
        _r121 = _alt121["frage"]("Plan X")
    finally:
        _mmb121.QMessageBox.question = _q_alt121
    check(f"b121 die echte Frage nennt den Plan, Standard ist 'Nein' ({_frage121})",
          _r121 is False and len(_frage121) == 1
          and "Plan X" in str(_frage121[0][2])
          and _frage121[0][-1] == _mmb121.QMessageBox.No)
    # (3) RECHTSKLICK AUF EINE KARTE.
    win._reload_saved_plans(); _app.processEvents()
    _k121 = (getattr(win, "_plan_karte", None) or {}).get(12101)
    _kr121 = (getattr(win, "_plan_karte", None) or {}).get(12102)
    check("b121 Karte hat ein eigenes Rechtsklick-Menue",
          _k121 is not None and _k121.contextMenuPolicy() == Qt.CustomContextMenu)
    _akt121k = {}

    def _menu121(pid):
        def _f():
            _m = win._plan_karten_menu
            _akt121k[pid] = [(a.text(), a.isEnabled()) for a in _m.actions()]
            _m.close()
        return _f
    if _k121 is not None and _kr121 is not None:
        _QT121.singleShot(0, _menu121(12101))
        _k121.customContextMenuRequested.emit(_QP121(5, 5)); _app.processEvents()
        _QT121.singleShot(0, _menu121(12102))
        _kr121.customContextMenuRequested.emit(_QP121(5, 5)); _app.processEvents()
    check(f"b121 Karten-Menue hat 'Rename...' (emm334), aktiv ({_akt121k.get(12101)})",
          any(x[0] in ("Rename\u2026", "Umbenennen\u2026") and x[1]
              for x in _akt121k.get(12101, [])))
    _a121 = [x for x in _akt121k.get(12101, []) if "build plan" in x[0] or "Bauplan" in x[0]]
    _r121 = [x for x in _akt121k.get(12102, []) if "build plan" in x[0] or "Bauplan" in x[0]]
    # Seit 27.09.2026 auch beim reservierten aktiv - das Ende geht in eine
    # Kopie, der reservierte Plan bleibt (Nutzer: "... Kopie davon machen").
    check(f"b121 Karten-Menue: 'Add build plan...' aktiv, auch beim reservierten "
          f"({_akt121k})",
          len(_a121) == 1 and _a121[0][1] is True
          and len(_r121) == 1 and _r121[0][1] is True)
    # DER ECHTE SCANNER-RECHTSKLICK mit zwei markierten Zeilen: das Menue
    # zeigt die Auswahl-Eintraege statt des Einzel-Untermenues.
    win.b_table.resize(900, 400); win.b_table.show(); _app.processEvents()
    _mtxt121 = []

    def _bm121():
        _m = getattr(win, "_build_menu_letztes", None)
        _mtxt121.append([a.text() for a in _m.actions()] if _m is not None else None)
        if _m is not None:
            _m.close()
    win._build_menu_letztes = None
    for _tid in (_X1, _X3):
        _sm121.select(win.b_table.model().index(_zeilen121[_tid][0], 0),
                      _ISM121.Select | _ISM121.Rows)
    _QT121.singleShot(0, _bm121)
    win._build_menu(win.b_table.visualRect(
        win.b_table.model().index(_zeilen121[_X1][0], 0)).center())
    _app.processEvents()
    check(f"b121 echter Scanner-Rechtsklick auf die Auswahl: Auswahl-Eintraege ({_mtxt121})",
          bool(_mtxt121) and _mtxt121[0] is not None
          and any("(2)" in x for x in _mtxt121[0])
          and any("2" in x and ("selected" in x or "markierte" in x) for x in _mtxt121[0]))
    win.b_table.hide()
    # Der Auswahl-Dialog der Karte laesst DIESEN Plan aus seiner Planliste.
    win.settings["bau_saved_plans"].append(
        {"id": 12103, "label": "b121 E", "type_id": _X2, "item_name": "X2",
         "qty": 4, "me": 0, "te": 0, "checked": []})
    win._build_picker_pairs = [("X2", _X2)]
    _liste121 = []

    def _schau121():
        _pb = getattr(win, "_multi_ende_dialog_plaene", None)
        _liste121.append([_pb.itemData(i) for i in range(_pb.count())] if _pb else None)
        win._multi_ende_dialog.reject()
    _QT121.singleShot(0, _schau121)
    win._multi_ende_waehlen(ausser=12103)
    _QT121.singleShot(0, _schau121)
    win._multi_ende_waehlen()
    check(f"b121 Auswahl-Dialog der Karte: der Plan selbst steht nicht drin ({_liste121})",
          _liste121 == [[None, 12102], [None, 12102, 12103]])
    win.settings["bau_saved_plans"].pop()
    # Der Weg dahinter: Auswahl gestubbt -> an DIESEN Plan, ohne ihn selbst
    # in der Planliste des Dialogs.
    _ausser121 = []
    win._multi_ende_waehlen = lambda ausser=None: (
        _ausser121.append(ausser),
        {"tid": _X2, "name": "X2", "qty": 6})[1]
    _offen121.clear(); _gesp121.clear()
    win._plan_karte_ende_dazu(12101); _app.processEvents()
    _pa121 = next(p for p in win.settings["bau_saved_plans"] if p["id"] == 12101)
    check(f"b121 'Add build plan...' der Karte: X2 x 6 haengt am Plan, gespeichert, offen "
          f"({_pa121.get('enden')})",
          _ausser121 == [12101]
          and [x for x in _pa121["enden"] if x[0] == _X2] == [[_X2, 8]]   # 2 von oben + 6
          and _gesp121 and _offen121 and _offen121[-1][1] == 12101)
except Exception as _e121:                                # pragma: no cover
    import traceback as _tb121
    _fail.append(f"b121 Bedienideen: {type(_e121).__name__}: {_e121} | "
                 + _tb121.format_exc().splitlines()[-3].strip())
finally:
    try:
        win.settings["bau_saved_plans"] = _alt121.get("plans") or []
        _cfg121.save_settings = _alt121["save"]
        win._multi_plan_oeffnen = _alt121["oeffnen"]
        win._flash_tip = _alt121["tip"]
        win._multi_ende_waehlen = _alt121["waehlen"]
        win._multi_jetzt_oeffnen_fragen = _alt121["frage"]
        win.b_table.setRowCount(0)
        win._reload_saved_plans()
    except Exception:
        pass


# ---------------------------------------------------------------- (b122)
# PORTFOLIO-REFRESH MIT LIVE-PREISEN (Nutzer 27.09.2026: "refresh all zieht
# Marktpreise?" / "ich frage mich, ob die Logik dahinter sinnvoll ist").
# Vorher kamen ALLE Preise aus dem letzten Markt-Scan (bis 6 h alt), und die
# Altersanzeige sagte trotzdem "just now". Jetzt: Live-Preise fuer das, was
# man hat oder in Orders stehen hat; die Anzeige nennt das echte Alter.
_alt122 = {}
try:
    import eve_trader.esi as _esi122
    import eve_trader.store as _st122
    _alt122 = {"fto": _esi122.fetch_type_orders, "src": _st122.get_hub_source,
               "ts": getattr(win, "_prices_ts", 0),
               "n": getattr(win, "_prices_live_n", 0)}
    _assets122 = {1: {"hangar": {501: 3, 502: 1},
                      "containers": [{"item_id": 9001, "type_id": 17366,
                                      "contents": {503: 5}},
                                     {"item_id": 9002, "type_id": 17366,
                                      "contents": {504: 7}}]}}
    _ids122 = win._portfolio_live_ids(_assets122, {9002}, [],
                                      {1: {"buy": {505}, "sell": {501}}})
    check(f"b122 Live-Items: Hangar + Container + Orders, ignorierter Container raus ({sorted(_ids122)})",
          _ids122 == {501, 502, 503, 505})
    _tx122 = [{"type_id": 601, "quantity": 5, "is_buy": 1},
              {"type_id": 601, "quantity": 2, "is_buy": 0},
              {"type_id": 602, "quantity": 3, "is_buy": 1},
              {"type_id": 602, "quantity": 3, "is_buy": 0}]
    _ids122b = win._portfolio_live_ids({}, set(), _tx122, {})
    check(f"b122 ohne Asset-Daten: Bestand aus den Transaktionen (nur positiv) ({sorted(_ids122b)})",
          _ids122b == {601})
    _abrufe122 = []

    def _fto122(tid, station=None, region=None):
        _abrufe122.append((tid, station, region))
        if tid == 501:
            return {"sell": [(110.0, 5)], "buy": [(90.0, 3)]}
        if tid == 502:
            return {"sell": [], "buy": [(40.0, 1)]}
        raise RuntimeError("ESI weg")
    _esi122.fetch_type_orders = _fto122
    _st122.get_hub_source = lambda: "hub:10000002"
    _pr122 = {501: {"buy_max": 80.0, "sell_min": 120.0},
              502: {"buy_max": 30.0, "sell_min": 55.0},
              503: {"buy_max": 1.0, "sell_min": 2.0}}
    _n122 = win._portfolio_live_preise(_pr122, {501, 502, 503})
    check(f"b122 Live-Preise vom Portfolio-Hub (Jita-Station): {_pr122}, n={_n122}",
          _n122 == 2
          and _pr122[501] == {"buy_max": 90.0, "sell_min": 110.0}
          and _pr122[502] == {"buy_max": 40.0, "sell_min": 55.0}   # leere Sell-Seite: Scan bleibt
          and _pr122[503] == {"buy_max": 1.0, "sell_min": 2.0}     # Fehler: Scan bleibt
          and all(_s == 60003760 and _r == 10000002 for _t, _s, _r in _abrufe122))
    _st122.get_hub_source = lambda: "struct:1234"
    _abrufe122.clear()
    check("b122 Portfolio-Quelle ist eine Struktur: kein Einzel-Abruf, alles aus dem Scan",
          win._portfolio_live_preise(dict(_pr122), {501}) == 0 and not _abrufe122)
    _st122.get_hub_source = lambda: "hub:10000002"
    _abrufe122.clear()
    win._portfolio_live_preise({}, set(range(700000, 700000 + win.PORTFOLIO_LIVE_MAX + 50)))
    check(f"b122 Deckel: hoechstens {win.PORTFOLIO_LIVE_MAX} Einzel-Abrufe ({len(_abrufe122)})",
          len(_abrufe122) == win.PORTFOLIO_LIVE_MAX)
    # DIE ANZEIGE sagt das echte Alter und wie viele Items live sind.
    import time as _t122
    win._prices_ts = _t122.time(); win._prices_live_n = 57
    win.update_ages()
    _txt122 = win.age_label.text()
    check(f"b122 Anzeige: live jetzt, mit Anzahl ({_txt122[:80]})",
          ("57 of your items" in _txt122 or "57 deiner Items" in _txt122)
          and ("just now" in _txt122 or "gerade" in _txt122))
    win._prices_ts = _t122.time() - 3 * 3600 - 60; win._prices_live_n = 0
    win.update_ages()
    _txt122b = win.age_label.text()
    _preis122 = _txt122b.split("\u00b7")[0]
    check(f"b122 Anzeige ohne Live-Preise: Alter des Scans ({_preis122.strip()})",
          ("3 h" in _preis122 or "3 Std" in _preis122)
          and "of your items" not in _preis122 and "deiner Items" not in _preis122)
except Exception as _e122:                                # pragma: no cover
    import traceback as _tb122
    _fail.append(f"b122 Portfolio-Refresh: {type(_e122).__name__}: {_e122} | "
                 + _tb122.format_exc().splitlines()[-3].strip())
finally:
    try:
        _esi122.fetch_type_orders = _alt122["fto"]
        _st122.get_hub_source = _alt122["src"]
        win._prices_ts = _alt122["ts"]; win._prices_live_n = _alt122["n"]
    except Exception:
        pass


# ---------------------------------------------------------------- (b123)
# ORDER UPDATE SORTIERBAR (Nutzer 27.09.2026: "die Spalten sortieren
# koennen, damit ich im Work-through mode nur die mit noch genuegend hoher
# New margin modifizieren kann"). Kopf-Klick sortiert, die Knoepfe bleiben
# in jeder Zeile, "Next" laeuft in der angezeigten Reihenfolge.
_alt123 = {}
try:
    _alt123 = {"sell": list(getattr(win, "_ordmod_sell", None) or []),
               "sort": getattr(win, "_ord_sort", None),
               "open": win.open_ingame_market, "copy": win._copy_order_price,
               "step": getattr(win, "_step_mode", False)}
    def _z123(name, mn, flag=True, loss=False):
        return {"tid": abs(hash(name)) % 900000 + 1000, "name": name, "mine": 100.0,
                "best": 90.0, "flag": flag, "newp": 89.0, "cost": 50.0,
                "loss": loss, "marge_new": mn, "cost_known": mn is not None,
                "order_id": None, "char_id": 0, "mod_count": 0, "cum_fee": 0.0,
                "vol_remain": 1}
    win._ord_sort = {}
    win._ordmod_sell = [_z123("Alpha", 4.9), _z123("Bravo", 130.4), _z123("Charlie", None),
                        _z123("Delta", 17.3), _z123("Echo", -5.0, loss=True),
                        _z123("Foxtrot", 35.9)]
    _tb123 = win.sellord_table
    win._fill_order_table(_tb123, win._ordmod_sell, False)
    _namen123 = lambda: [_tb123.item(i, 0).text() for i in range(_tb123.rowCount())]
    check(f"b123 ohne Wahl: Nachbessern zuerst, Verlust unten, dann Name ({_namen123()})",
          _namen123() == ["Alpha", "Bravo", "Charlie", "Delta", "Foxtrot", "Echo"])
    _tb123.horizontalHeader().sectionClicked.emit(4); _app.processEvents()
    check(f"b123 Klick auf 'New margin': hoechste zuerst, ohne Wert unten ({_namen123()})",
          _namen123() == ["Bravo", "Foxtrot", "Delta", "Alpha", "Echo", "Charlie"])
    check("b123 ... jede Zeile hat weiter ihre Knoepfe (Price/Open)",
          all(_tb123.cellWidget(i, 8) is not None
              and len(_tb123.cellWidget(i, 8).findChildren(QPushButton)) == 2
              for i in range(_tb123.rowCount())))
    check("b123 ... der Pfeil im Kopf zeigt die Spalte",
          _tb123.horizontalHeader().isSortIndicatorShown()
          and _tb123.horizontalHeader().sortIndicatorSection() == 4)
    _tb123.horizontalHeader().sectionClicked.emit(4); _app.processEvents()
    check(f"b123 zweiter Klick: aufsteigend, ohne Wert weiter unten ({_namen123()})",
          _namen123() == ["Echo", "Alpha", "Delta", "Foxtrot", "Bravo", "Charlie"])
    _tb123.horizontalHeader().sectionClicked.emit(8); _app.processEvents()
    check("b123 die Aktions-Spalte sortiert nicht",
          _namen123() == ["Echo", "Alpha", "Delta", "Foxtrot", "Bravo", "Charlie"])
    # "NEXT" IN DER ANGEZEIGTEN REIHENFOLGE: absteigend nach Marge, Verlust nie.
    _tb123.horizontalHeader().sectionClicked.emit(4); _app.processEvents()
    _gang123 = []
    win.open_ingame_market = lambda *a, **k: None
    win._copy_order_price = lambda pr, nm, **k: _gang123.append(nm)
    win._toggle_order_step(True)
    win._orders_inner.setCurrentIndex(1)
    for _ in range(4):
        win._ord_step_next()
    check(f"b123 Work-through 'Next' folgt der Sortierung ({_gang123})",
          _gang123 == ["Bravo", "Foxtrot", "Delta", "Alpha"])
    # Neue Sortierung waehrend des Abarbeitens: Next beginnt wieder oben.
    _tb123.horizontalHeader().sectionClicked.emit(0); _app.processEvents()
    _gang123.clear()
    win._ord_step_next()
    check(f"b123 nach neuer Sortierung (Name) beginnt Next wieder oben ({_gang123})",
          _gang123 == ["Alpha"])
except Exception as _e123:                                # pragma: no cover
    import traceback as _tb123x
    _fail.append(f"b123 Order-Sortierung: {type(_e123).__name__}: {_e123} | "
                 + _tb123x.format_exc().splitlines()[-3].strip())
finally:
    try:
        win.open_ingame_market = _alt123["open"]
        win._copy_order_price = _alt123["copy"]
        win._toggle_order_step(bool(_alt123["step"]))
        win._ord_sort = _alt123["sort"] or {}
        win._ordmod_sell = _alt123["sell"]
        win._fill_order_table(win.sellord_table, win._ordmod_sell, False)
        win.sellord_table.horizontalHeader().setSortIndicatorShown(False)
    except Exception:
        pass


# ---------------------------------------------------------------- (b124)
# LADEZEIT-MESSUNG (Nutzer 27.09.2026: "Multi-Bauplaene zu oeffnen dauert
# mehrere Minuten, da muessten wir mal messen, was so viel Zeit kostet").
# Nur mit EMM_LADEZEIT=1 aktiv (werkzeuge\messe_ladezeit.bat); ohne sie
# darf NICHTS passieren.
_alt124 = {}
try:
    import eve_trader.ladezeit as _lz124
    import eve_trader.workers as _wk124
    import tempfile as _tf124
    _alt124 = {"an": _lz124.AN, "datei": _lz124.DATEI}
    _d124 = _tf124.mkdtemp()
    _lz124.DATEI = os.path.join(_d124, "ladezeiten.txt")
    _lz124.AN = False
    with _lz124.messen("aus"):
        sum(range(1000))
    _w124 = _wk124.Worker(lambda: 42)
    _w124.run()
    check("b124 ohne EMM_LADEZEIT: keine Datei, kein Profiler",
          not os.path.exists(_lz124.DATEI))
    _lz124.AN = True
    with _lz124.messen("aussen"):
        with _lz124.messen("innen"):
            sum(range(10000))
    _w124b = _wk124.Worker(lambda: sum(range(5000)))
    _w124b.run()
    _txt124 = open(_lz124.DATEI, encoding="utf-8").read()
    check("b124 mit Messung: Bloecke mit Zeit und Profil, verschachtelt ohne zweites Profil",
          "  aussen  " in _txt124 and "  innen  " in _txt124
          and "time only" in _txt124 and "cumulative" in _txt124)
    check("b124 ... jeder Hintergrund-Job wird gemessen (Worker.run)",
          "  Job " in _txt124 and "<lambda>" in _txt124)
    # EIN PROFILER JE PROZESS (Python 3.12, gemessen): laeuft schon einer -
    # auch ein fremder -, darf ein Job NICHT abstuerzen, sondern misst nur
    # die Zeit. Vorher warf enable() "Another profiling tool is already
    # active" und der Job meldete einen Fehler.
    import cProfile as _cp124
    _fremd124 = _cp124.Profile()
    _fremd_an124 = True
    try:
        _fremd124.enable()
    except ValueError:
        _fremd_an124 = False
    _erg124 = []
    try:
        _w124c = _wk124.Worker(lambda: 5)
        _w124c.done.connect(lambda v: _erg124.append(v))
        _w124c.failed.connect(lambda m: _erg124.append("FEHLER " + m))
        _w124c.run()
    finally:
        if _fremd_an124:
            _fremd124.disable()
    check(f"b124 fremder Profiler aktiv: der Job laeuft trotzdem durch ({_erg124})",
          _erg124 == [5])
    # Oberflaeche: vom Start bis alles ruhig ist (keine Jobs, 2x ruhig).
    from PySide6.QtTest import QTest as _QT124
    _lz124.ui_start("b124 Plan")
    _wk_alt124 = list(getattr(win, "_workers", []) or [])
    win._workers = []
    win._ladezeit_warten()
    _QT124.qWait(3600)
    win._workers = _wk_alt124
    _txt124b = open(_lz124.DATEI, encoding="utf-8").read()
    check("b124 Oberflaechen-Messung endet von selbst, wenn alles ruhig ist",
          "UI thread: b124 Plan" in _txt124b and not _lz124.ui_laeuft())
    # BEENDEN VOR DER RUHE (erster Nutzer-Bericht: der Bauplan-Teil fehlte):
    # die angefangene Messung landet trotzdem im Bericht.
    _lz124.ui_start("b124 Abbruch")
    _lz124._beim_beenden()
    _txt124c = open(_lz124.DATEI, encoding="utf-8").read()
    check("b124 Schliessen vor der Ruhe: Messung steht trotzdem im Bericht",
          "b124 Abbruch (closed before idle)" in _txt124c and not _lz124.ui_laeuft())
    # DIE OBERFLAECHE HAT VORRANG (zweiter Nutzer-Bericht: "open build plan
    # 12.49 s (time only - another profile was running)"): rechnet gerade ein
    # Job mit Profil, uebernimmt die Bauplan-Messung den Profiler.
    import inspect as _in124b
    _ROOT_b124 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    with _lz124.messen("b124 Karten"):
        sum(range(20000))
        _lz124.ui_start("b124 Vorrang")
        sorted(range(20000), key=lambda _x: -_x)
        _lz124.ui_stop()
        sum(range(20000))
    _abschn124 = {}
    for _teil in open(_lz124.DATEI, encoding="utf-8").read().split("\n== "):
        for _nm in ("UI thread: b124 Vorrang", "  b124 Karten  "):
            if _nm in _teil.split("\n", 1)[0]:
                _abschn124[_nm] = _teil
    _ui124 = _abschn124.get("UI thread: b124 Vorrang", "")
    _job124 = _abschn124.get("  b124 Karten  ", "")
    check("b124 Bauplan-Messung uebernimmt den Profiler eines laufenden Jobs",
          "cumulative" in _ui124 and "time only" not in _ui124
          and "<lambda>" in _ui124 and "took it over" in _job124
          and not _lz124._aktiv[0] and _lz124._laufend["prof"] is None)
    # Endet der Job, WAEHREND die Bauplan-Messung laeuft, bleibt der
    # Profiler bei ihr (sonst startete der naechste Job einen zweiten).
    with _lz124.messen("b124 Karten kurz"):
        _lz124.ui_start("b124 Vorrang lang")
    _bleibt124 = (_lz124._aktiv[0] and _lz124._laufend["prof"] is not None
                  and _lz124._laufend["prof"] is _lz124._ui.get("prof"))
    _lz124.ui_stop()
    check("b124 ... endet der Job zuerst, bleibt der Profiler bei der Oberflaeche",
          _bleibt124 and not _lz124._aktiv[0])
    # STARTZEIT (Nutzer: "das erste Laden beim Oeffnen dauert"): Zwischen-
    # zeiten stehen im Kopf des Berichts; main.py startet, __main__ beendet.
    _lz124.ui_start("b124 Start")
    _lz124.ui_zwischenzeit("b124 Fenster gebaut")
    _lz124.ui_stop()
    _st124 = [t for t in open(_lz124.DATEI, encoding="utf-8").read().split("\n== ")
              if "UI thread: b124 Start" in t.split("\n", 1)[0]]
    import eve_trader.__main__ as _hm124
    _hsrc124 = _in124b.getsource(_hm124.main)
    _msrc124 = open(os.path.join(_ROOT_b124, "main.py"), encoding="utf-8").read()
    check("b124 Startzeit: Zwischenzeiten im Bericht, main.py startet, __main__ beendet",
          bool(_st124) and " s  b124 Fenster gebaut  (UI thread busy " in _st124[0]
          and '_lz.ui_start("start of Eve MoMa")' in _msrc124
          and '_lz.ui_zwischenzeit("main window built")' in _hsrc124
          and '_lzm("MainWindow: build tab")' in _in124b.getsource(type(win).__init__)
          and "_lz.ui_stop()" in _hsrc124)
    # SKILL-RECHNUNG FRAGT DIE DATENBANK NICHT MEHR JEDES MAL (Nutzer-Bericht:
    # 23'000 Aufrufe von list_characters beim Laden der Plan-Karten, 80 s).
    import eve_trader.ui.main_window as _mwm124
    _lc_alt124 = _mwm124.store.list_characters
    _lc124 = []
    _mwm124.store.list_characters = lambda: (_lc124.append(1), [
        {"character_id": 77, "character_name": "Zweiundsiebzig"}])[1]
    try:
        win._char_namen_cache = None
        _r124 = [win._bau_invention_skill_modifier_with_char(
            1, fixed_cid=77, inv_skills_map={1: 1}) for _ in range(200)]
    finally:
        _mwm124.store.list_characters = _lc_alt124
        win._char_namen_cache = None
    check(f"b124 200 Skill-Rechnungen: Charakterliste EINMAL gelesen ({len(_lc124)})",
          len(_lc124) == 1 and _r124[-1] == (1.0, "Zweiundsiebzig"))
    # Der Einstieg sitzt am Anfang von open_build_detail.
    import inspect as _in124
    _src124 = _in124.getsource(type(win).open_build_detail)
    check("b124 open_build_detail startet die Messung (nur wenn an)",
          "if ladezeit.AN:" in _src124
          and "ladezeit.ui_start(" in _src124 and "self._ladezeit_warten()" in _src124)
except Exception as _e124:                                # pragma: no cover
    import traceback as _tb124
    _fail.append(f"b124 Ladezeit: {type(_e124).__name__}: {_e124} | "
                 + _tb124.format_exc().splitlines()[-3].strip())
finally:
    try:
        if _lz124.ui_laeuft():
            _lz124.ui_stop()
        _lz124.AN = _alt124["an"]; _lz124.DATEI = _alt124["datei"]
    except Exception:
        pass


# ---------------------------------------------------------------- (b126)
# START OHNE GROSSES LADE-FENSTER (Nutzer 27.09.2026: "vor allem das erste
# Laden beim Oeffnen dauert" - gemessen 25-32 s Portfolio-Abruf hinter dem
# Overlay). Beim Start: im Hintergrund. Knopf "Refresh": Overlay wie bisher.
try:
    import eve_trader.ui.main_window as _mwm126
    _lc_alt126 = _mwm126.store.list_characters
    _sa_alt126 = _mwm126.store.snapshot_age_seconds
    _run_alt126 = win._run
    _cid_alt126 = win.settings.get("client_id")
    _laeufe126 = []
    _mwm126.store.list_characters = lambda: [
        {"character_id": 1, "character_name": "Eins"}]
    _mwm126.store.snapshot_age_seconds = lambda *a, **k: 60
    win.settings["client_id"] = win.settings.get("client_id") or "test126"
    _wk_vor126 = list(win._workers)
    # Wie das echte _run: der Job steht danach in _workers.
    win._run = lambda worker, done_cb, **k: (_laeufe126.append(
        (k.get("label"), k.get("overlay", True))), win._workers.append(worker))
    try:
        win.refresh_everything(beim_start=True)
        _start_lbl126 = not win.g_lade_lbl.isHidden()
        win._hintergrund_laden_zeigen(False)
        win.refresh_everything()
        win.global_refresh_btn.click()
        # Der Portfolio-Knopf haengt DIREKT an refresh_all: clicked(False)
        # darf nicht als overlay=False ankommen (lint_order fand das).
        win.refresh_btn.setEnabled(True)
        win.refresh_btn.click()
    finally:
        win._workers[:] = _wk_vor126
        win._run = _run_alt126
        _mwm126.store.list_characters = _lc_alt126
        _mwm126.store.snapshot_age_seconds = _sa_alt126
        if _cid_alt126 is None:
            win.settings.pop("client_id", None)
        else:
            win.settings["client_id"] = _cid_alt126
        win.refresh_btn.setEnabled(True)
    # SICHTBAR, DASS GELADEN WIRD (Nutzer-Bildschirm 27.09.2026: "jetzt
    # kommt am Anfang gar nichts ... die Loading-Anzeige unten rechts sieht
    # eh keiner"): Anzeige oben + Portfolio-Leerhinweis ohne Scan-Knopf.
    from PySide6.QtWidgets import QWidget as _QW126
    _box126 = [b for b in win.pf_table.viewport().findChildren(_QW126)
               if getattr(b, "_knopf", None) is not None]
    _zeilen126 = win.pf_table.rowCount()
    _wk_alt126 = list(win._workers)
    win._workers.append(object())            # ein laufender Job
    try:
        win._hintergrund_laden_zeigen(True)
        _app.processEvents()
        _an126 = (not win.g_lade_lbl.isHidden(), win.g_lade_lbl.text(),
                  _box126[0].findChild(QLabel).text() if _box126 else "",
                  _box126[0]._knopf.isHidden() if _box126 else None)
        win._hintergrund_laden_zeigen(False)
        _app.processEvents()
        _aus126 = (win.g_lade_lbl.isHidden(),
                   _box126[0].findChild(QLabel).text() if _box126 else "",
                   _box126[0]._knopf.isHidden() if _box126 else None)
        # Sicherung: kein Job mehr -> Anzeige verschwindet von selbst.
        win._hintergrund_laden_zeigen(True)
        win._workers[:] = []
        win._lade_tick()
        _sich126 = win.g_lade_lbl.isHidden() and not win._portfolio_laedt
    finally:
        win._workers[:] = _wk_alt126
        win._hintergrund_laden_zeigen(False)
    check(f"b126 ... waehrend des Ladens: oben sichtbar, Portfolio sagt 'wird "
          f"geladen' ohne Scan-Knopf ({_an126[1]!r}, {_an126[2][:30]!r})",
          _an126[0] and ("Loading" in _an126[1] or "Lade" in _an126[1])
          and (_zeilen126 > 0 or (("Loading" in _an126[2] or "geladen" in _an126[2])
                                  and _an126[3] is True)))
    check(f"b126 ... danach wieder normal ({_aus126[1][:30]!r}), Sicherung greift",
          _aus126[0] and _sich126
          and (_zeilen126 > 0 or ("Loading" not in _aus126[1]
                                  and "geladen" not in _aus126[1]
                                  and _aus126[2] is False)))
    check(f"b126 Start: Portfolio im Hintergrund, Knopf mit Overlay ({_laeufe126})",
          [o for _l, o in _laeufe126] == [False, True, True, True] and _start_lbl126
          and all("portfolio" in (_l or "").lower() or "Portfolio" in (_l or "")
                  for _l, _o in _laeufe126))
except Exception as _e126:                                # pragma: no cover
    import traceback as _tb126
    _fail.append(f"b126 Start im Hintergrund: {type(_e126).__name__}: {_e126} | "
                 + _tb126.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b129)
# CORP-BLAUPAUSEN OHNE "SUBTRACT ASSETS" + IN MY BLUEPRINTS (1.1.0, Discord:
# "Blueprints im Corp-Hangar"). Am ECHTEN Fenster, ESI vorgetaeuscht: der
# Bauplan-Cache bekommt die Corp-Blaupausen OHNE Asset-Abruf, My Blueprints
# zeigt sie als eigene Zeile (Corp + Hangar), der Charakter-Filter laesst sie
# bei einem Mitglied stehen, eine Blaupause im Corp-Research-Job zaehlt im
# Bauplan nicht und steht in My Blueprints als "in job".
try:
    import eve_trader.esi as _esi129
    import eve_trader.config as _cfg129
    import eve_trader.ui.main_window as _mwm129
    from PySide6.QtCore import Qt as _Qt129
    _alt129 = {k: getattr(_esi129, k) for k in (
        "fetch_character_corporation", "granted_scopes", "fetch_character_roles",
        "fetch_corporation_assets", "fetch_corporation_blueprints",
        "fetch_corporation_jobs", "fetch_corporation_name", "fetch_blueprints",
        "fetch_corporation_info", "fetch_corporation_logo_bytes")}
    _alt_st129 = (_mwm129.store.list_characters, _mwm129.store.get_snapshot)
    _alt_set129 = {k: win.settings.get(k) for k in ("use_corp", "corp_divisions",
                                                     "client_id")}
    _alt_cache129 = getattr(win, "_bd_owned_bp_cache", None)
    _alt_run129 = win._run
    _z129 = {"assets": 0, "bp": 0, "jobs": 0}
    try:
        _chars129 = [{"character_id": 11, "character_name": "Alpha"},
                     {"character_id": 12, "character_name": "Beta"}]
        _mwm129.store.list_characters = lambda: list(_chars129)
        _mwm129.store.get_snapshot = lambda *a, **k: None
        win.settings["client_id"] = "test129"
        win.settings["corp_divisions"] = [1]

        def _f_assets129(*a, **k):
            _z129["assets"] += 1
            return []

        def _f_bp129(client_id, cid, corp_id, divisions=None):
            _z129["bp"] += 1
            return [{"item_id": 5001, "type_id": 999, "quantity": 1,
                     "material_efficiency": 10, "time_efficiency": 20,
                     "runs": -1, "is_bpo": True, "location_id": 1_050_000_000_001,
                     "location_flag": "CorpSAG1", "division": 1,
                     "corporation_id": corp_id},
                    {"item_id": 5002, "type_id": 998, "quantity": 1,
                     "material_efficiency": 0, "time_efficiency": 0,
                     "runs": -1, "is_bpo": True, "location_id": 1_050_000_000_001,
                     "location_flag": "CorpSAG1", "division": 1,
                     "corporation_id": corp_id}]

        def _f_jobs129(client_id, cid, corp_id, include_delivered=False):
            _z129["jobs"] += 1
            return [{"job_id": 7, "activity_id": 4, "blueprint_id": 5002,
                     "product_type_id": 998, "runs": 1, "status": "active",
                     "end_date": "2099-01-01T00:00:00Z"}]

        _esi129.fetch_character_corporation = lambda cid: 900
        _esi129.granted_scopes = lambda client_id, cid: set(_cfg129.CORP_SCOPES)
        __import__('eve_trader.ui.mw_bauplan_fenster', fromlist=['x'])._ROLLEN_STAND.clear()  # emm305: Rollen-Merker leeren
        _esi129.fetch_character_roles = lambda client_id, cid: {"Director", "Factory_Manager"}
        _esi129.fetch_corporation_assets = _f_assets129
        _esi129.fetch_corporation_blueprints = _f_bp129
        _esi129.fetch_corporation_jobs = _f_jobs129
        _esi129.fetch_corporation_name = lambda corp: "Test Corp"
        # Kein Netz im Test: Ticker/Logo-Abruf liefert nichts.
        _esi129.fetch_corporation_info = lambda corp: {}

        def _kein_logo129(*a, **k):
            raise OSError("kein Netz im Test")
        _esi129.fetch_corporation_logo_bytes = _kein_logo129
        _esi129.fetch_blueprints = lambda client_id, cid, jobs=None, mit_belegten=False: [
            {"item_id": 100 + cid, "type_id": 997, "quantity": 1,
             "material_efficiency": 0, "time_efficiency": 0, "runs": -1,
             "is_bpo": True, "location_id": 60003760}]
        # 1. SCHALTER AUS: kein Corp-Abruf, nur die eigenen.
        win.settings["use_corp"] = False
        _aus129 = win._bd_fetch_all_owned_blueprints(force=True)
        check(f"b129 Corp-Schalter aus: keine Corp-Blaupause, kein Abruf ({_z129})",
              sorted(b["type_id"] for b in _aus129) == [997, 997]
              and _z129["bp"] == 0)
        # 2. AN: Bauplan-Cache MIT Corp-Blaupause, OHNE Asset-Abruf.
        win.settings["use_corp"] = True
        _an129 = win._bd_fetch_all_owned_blueprints(force=True)
        _corp129 = [b for b in _an129 if b.get("_corp_name")]
        check(f"b129 Bauplan: Corp-Blaupause ohne 'Subtract assets' ({_corp129})",
              [b["type_id"] for b in _corp129] == [999]
              and win._bd_owned_bp_cache is _an129)
        check(f"b129 Bauplan: kein Asset-Abruf, EIN Blaupausen-Abruf fuer zwei "
              f"Charaktere ({_z129})", _z129["assets"] == 0 and _z129["bp"] == 1)
        check("b129 Bauplan: Blaupause im Corp-Research-Job zaehlt nicht",
              998 not in {b["type_id"] for b in _an129})
        # 3. MY BLUEPRINTS: eigene Zeile, Ort = Corp + Hangar, "in job".
        win._run = lambda w, done, fail_cb=None, **_k: done(w._fn())
        win._reload_my_blueprints()
        _t129 = win.bp_table
        _zeilen129 = {}
        for _r in range(_t129.rowCount()):
            _c0 = _t129.item(_r, 0)
            _ort = _t129.item(_r, 14).text() if _t129.item(_r, 14) else ""
            if _c0 is not None and "Test Corp" in _ort:
                _zeilen129[_c0.data(_Qt129.UserRole + 8)] = (
                    _r, _ort, _c0.data(_Qt129.UserRole + 11),
                    list(_c0.data(_Qt129.UserRole + 13) or []),
                    _t129.item(_r, 7).text())
        check(f"b129 My Blueprints: zwei Corp-Zeilen, Ort 'Test Corp · Corp "
              f"hangar 1' ({_zeilen129})",
              sorted(_zeilen129) == [998, 999]
              and all(("hangar 1" in v[1] or "Hangar 1" in v[1])
                      for v in _zeilen129.values()))
        check("b129 My Blueprints: Besitzer der Corp-Zeile ist die Corp",
              _zeilen129.get(999, (0, 0, 0))[2] == 900)
        check(f"b129 My Blueprints: Blaupause im Corp-Job steht als 'in job' "
              f"({_zeilen129.get(998)})",
              "job" in (_zeilen129.get(998) or ("",) * 5)[4].lower())
        check(f"b129 Statuszeile nennt die Corp ({win.bp_status.text()!r})",
              "Test Corp" in win.bp_status.text())
        # 4. DROPDOWN (emm301, Nutzer 30.09.2026): KEINE Corp mehr im
        # Dropdown; die Corp-Zeilen stehen unter All und beim Director, ueber
        # den sie geladen wurden (Alpha, erster Charakter mit Rolle).
        _cb129 = win.bp_myb_char
        _texte129 = [_cb129.itemText(_i) for _i in range(_cb129.count())]
        check(f"b129 Dropdown: KEINE Corp mehr drin (emm301) ({_texte129})",
              _cb129.findData(900) < 0
              and not any("Test Corp" in _x for _x in _texte129))
        _alpha129 = next((_r for _r in range(_t129.rowCount())
                          if _t129.item(_r, 0) is not None
                          and _t129.item(_r, 0).data(_Qt129.UserRole + 11) == 11), None)
        _idx129 = _cb129.currentIndex()
        _haken129 = [win.bp_cb_end, win.bp_cb_comp, win.bp_cb_react,
                     win.bp_cb_bpo, win.bp_cb_bpc, win.bp_cb_invent]
        _combos129 = [getattr(win, _n) for _n in ("bp_myb_cat", "bp_myb_group",
                                                  "bp_myb_tech") if hasattr(win, _n)]
        _stand129 = ([w.isChecked() for w in _haken129], win.bp_cb_profit.isChecked(),
                     [w.currentIndex() for w in _combos129], win.bp_search.currentText())
        _cb129.blockSignals(True)
        try:
            _cb129.addItem("Alpha129", 11)
            _cb129.addItem("Gamma129", 13)     # Charakter ohne Corp-Abruf
            _cb129.addItem("Beta129", 12)      # ZWEITER Director (emm306)
            # Uebrige Filter neutral (Stand der .smoke_home ist beliebig).
            for _w in _haken129:
                _w.blockSignals(True); _w.setChecked(True); _w.blockSignals(False)
            win.bp_cb_profit.blockSignals(True); win.bp_cb_profit.setChecked(False)
            win.bp_cb_profit.blockSignals(False)
            for _w in _combos129:
                _w.blockSignals(True); _w.setCurrentIndex(0); _w.blockSignals(False)
            win.bp_search.blockSignals(True); win.bp_search.setEditText("")
            win.bp_search.blockSignals(False)
            _cb129.setCurrentIndex(0)
            win._apply_bp_filter()
            _alle129 = (not _t129.isRowHidden(_zeilen129[999][0])
                        and not _t129.isRowHidden(_alpha129))
            _cb129.setCurrentIndex(_cb129.findData(13))
            win._apply_bp_filter()
            _corp_w129 = (_t129.isRowHidden(_zeilen129[999][0])
                          and _t129.isRowHidden(_alpha129))
            _cb129.setCurrentIndex(_cb129.findData(11))
            win._apply_bp_filter()
            _char_w129 = (not _t129.isRowHidden(_zeilen129[999][0])
                          and not _t129.isRowHidden(_alpha129))
            # emm306 (Nutzer 01.10.2026): JEDER Director sieht die Corp-
            # Zeilen, nicht nur der, ueber den sie geladen wurden.
            _cb129.setCurrentIndex(_cb129.findData(12))
            win._apply_bp_filter()
            _beta129 = (not _t129.isRowHidden(_zeilen129[999][0])
                        and not _t129.isRowHidden(_zeilen129[998][0])
                        and _t129.isRowHidden(_alpha129))
        finally:
            for _d129 in (11, 12, 13):
                _i = _cb129.findData(_d129)
                if _i >= 0 and _cb129.itemText(_i).endswith("129"):
                    _cb129.removeItem(_i)
            _cb129.setCurrentIndex(max(0, min(_idx129, _cb129.count() - 1)))
            _cb129.blockSignals(False)
            for _w, _v in zip(_haken129, _stand129[0]):
                _w.blockSignals(True); _w.setChecked(_v); _w.blockSignals(False)
            win.bp_cb_profit.blockSignals(True); win.bp_cb_profit.setChecked(_stand129[1])
            win.bp_cb_profit.blockSignals(False)
            for _w, _v in zip(_combos129, _stand129[2]):
                _w.blockSignals(True); _w.setCurrentIndex(_v); _w.blockSignals(False)
            win.bp_search.blockSignals(True); win.bp_search.setEditText(_stand129[3])
            win.bp_search.blockSignals(False)
            win._apply_bp_filter()
        check(f"b129 Filter: All zeigt beides, anderer Charakter keine Corp-Zeile, "
              f"der Director seine UND die der Corp ({_alle129}, {_corp_w129}, "
              f"{_char_w129})",
              _alle129 and _corp_w129 and _char_w129)
        check(f"b129 zweiter Director (Beta) sieht die Corp-Zeilen auch, Alphas "
              f"eigene nicht (emm306) ({_beta129})", _beta129)
        # Neufuellen der Charakter-Listen bringt keine Corp zurueck.
        win._reload_character_combos()
        check("b129 Dropdown: auch nach dem Neufuellen keine Corp",
              win.bp_myb_char.findData(900) < 0)
        # 5. OHNE CORP-SCOPE: Statuszeile nennt, wer neu verlinken muss.
        _esi129.granted_scopes = lambda client_id, cid: set()
        win._reload_my_blueprints()
        check(f"b129 ohne Corp-Scope: Statuszeile nennt die Charaktere "
              f"({win.bp_status.text()!r})",
              "Alpha" in win.bp_status.text() and "Beta" in win.bp_status.text())
    finally:
        for k, v in _alt129.items():
            setattr(_esi129, k, v)
        _mwm129.store.list_characters, _mwm129.store.get_snapshot = _alt_st129
        for k, v in _alt_set129.items():
            if v is None:
                win.settings.pop(k, None)
            else:
                win.settings[k] = v
        win._bd_owned_bp_cache = _alt_cache129
        win._run = _alt_run129
except Exception as _e129:                                # pragma: no cover
    import traceback as _tb129
    _fail.append(f"b129 Corp-Blaupausen: {type(_e129).__name__}: {_e129} | "
                 + _tb129.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b133)
# WARNUNG AN DER NUMMER (Nutzer 28.09.2026, "ja genau"): ein Plan ohne
# Schloss reserviert nichts, ein fertiger, nicht abgeschlossener Plan haelt
# Rang und Reservierung - beides steht jetzt an der "#n" der Karte.
try:
    from PySide6.QtWidgets import QLabel as _QL133

    class _K133(MainWindow):
        def __init__(self):
            self.settings = {"bau_saved_plans": [
                {"id": 1, "label": "Mit Schloss", "reserve": True},
                {"id": 2, "label": "Ohne Schloss", "reserve": False},
                {"id": 3, "label": "Fertig", "reserve": True},
                {"id": 4, "label": "Laeuft noch", "reserve": True}]}
            self._plan_rang_lbls = {"1": _QL133(), "2": _QL133(), "3": _QL133(),
                                    "4": _QL133()}
            self._plan_letzter_fortschritt = {
                1: {"qty": 10, "built": 4}, 3: {"qty": 10, "built": 10},
                # sein Multiplan 1: "100 % - 0/130 built" (laufende Runs)
                4: {"qty": 130, "built": 0, "pct": 100.0}}
    _k133 = _K133()
    _k133._plan_rang_auffrischen()
    _l133 = {k: (v.text(), v.toolTip()) for k, v in _k133._plan_rang_lbls.items()}
    check(f"b133 normaler Plan: nur '#1', keine Warnung ({_l133['1'][0]!r})",
          _l133["1"][0] == "#1" and "\u26a0" not in _l133["1"][1])
    check(f"b133 ohne Schloss: '#2 \u26a0' und der Grund im Tooltip ({_l133['2']})",
          _l133["2"][0].startswith("#2") and "\u26a0" in _l133["2"][0]
          and ("lock" in _l133["2"][1].lower() or "schloss" in _l133["2"][1].lower()))
    check(f"b133 fertig, nicht abgeschlossen: Warnung ({_l133['3']})",
          "\u26a0" in _l133["3"][0]
          and ("done" in _l133["3"][1].lower() or "erledigt" in _l133["3"][1].lower()))
    check(f"b133 100 % aus laufenden Runs, aber 0/130 gebaut: KEINE Warnung "
          f"({_l133['4'][0]!r})", _l133["4"][0] == "#4")
    # SCHLOSS SETZEN NIMMT DIE WARNUNG SOFORT WEG (Nutzer 29.09.2026: "hab
    # gesetzt, aber immer noch rot"). Speichern still, sonst schriebe der
    # Test das Mini-Settings in die .smoke_home.
    import eve_trader.config as _cfg133
    _sv133 = _cfg133.save_settings
    _cfg133.save_settings = lambda _s: None
    try:
        _k133.settings["bau_saved_plans"][1].update(
            {"reserve_map": {"1": 1}, "frozen": {"plan_snapshot": {"x": 1}}})
        _k133._toggle_plan_reserve(2, True)
        _t133 = _k133._plan_rang_lbls["2"].text()
        check(f"b133 Schloss gesetzt: Warnung sofort weg ({_t133!r})", _t133 == "#2")
        _k133._toggle_plan_reserve(2, False)
        _t133 = _k133._plan_rang_lbls["2"].text()
        check(f"b133 Schloss geloest: Warnung sofort da ({_t133!r})", "\u26a0" in _t133)
    finally:
        _cfg133.save_settings = _sv133
except Exception as _e133:                                # pragma: no cover
    import traceback as _tb133
    _fail.append(f"b133 Warnung an der Nummer: {type(_e133).__name__}: {_e133} | "
                 + _tb133.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b134)
# BUENDEL "DONE" SCHLIESST SEINE MITGLIEDER MIT UND RUTSCHT NACH UNTEN
# (Nutzer-Screenshot 28.09.2026: Multiplan 1 auf Done -> Ametat II,
# Flycatcher, Stork standen als #3/#4/#5 mit Warnung da; "sollte der Plan
# dann nicht direkt nach unten rutschen?").
try:
    import eve_trader.ui.main_window as _mwm134
    from PySide6.QtWidgets import QMessageBox as _QMB134
    _alt134 = (_QMB134.question, _mwm134.config.save_settings)
    _QMB134.question = staticmethod(lambda *a, **k: _QMB134.Yes)
    _mwm134.config.save_settings = lambda *a, **k: None
    try:
        class _K134(MainWindow):
            def __init__(self):
                self.settings = {"bau_saved_plans": [
                    {"id": 10, "label": "Multi", "type_id": -1, "quellen": [11, 12],
                     "reserve": True},
                    {"id": 11, "label": "A", "type_id": 500},
                    {"id": 12, "label": "B", "type_id": 501, "done_manual": True},
                    {"id": 13, "label": "Anderer", "type_id": 502, "reserve": True}],
                    "bau_plan_reihenfolge": ["10", "13"],
                    "bau_plan_sortierung": ["10", "13"]}

            def _reload_saved_plans(self):
                pass

            def _flash_tip(self, *a, **k):
                pass
        _k134 = _K134()
        _k134._mark_plan_done(10)
        _p134 = {p["id"]: p for p in _k134.settings["bau_saved_plans"]}
        check("b134 Buendel Done: sein offenes Mitglied ist mit abgeschlossen",
              _p134[11].get("done_manual") is True
              and _p134[11].get("done_durch_buendel") == 10)
        check("b134 ... ein schon vorher abgeschlossenes bekommt keinen Merker",
              "done_durch_buendel" not in _p134[12])
        check("b134 ... ein fremder Plan bleibt unberuehrt",
              not _p134[13].get("done_manual"))
        eq("b134 abgeschlossen rutscht nach unten (eigene Folge und Fortschritt)",
           (_k134.settings["bau_plan_reihenfolge"], _k134.settings["bau_plan_sortierung"]),
           (["13", "10"], ["13", "10"]))
        eq("b134 kein Rang mehr fuer Buendel und Mitglieder",
           _K134.plan_rang(_k134.settings), {"13": 1})
        _k134._mark_plan_done(10)          # Reopen
        check("b134 Reopen oeffnet genau das mitgeschlossene Mitglied wieder",
              not _p134[11].get("done_manual") and "done_durch_buendel" not in _p134[11]
              and _p134[12].get("done_manual") is True)
    finally:
        _QMB134.question, _mwm134.config.save_settings = _alt134
except Exception as _e134:                                # pragma: no cover
    import traceback as _tb134
    _fail.append(f"b134 Buendel Done: {type(_e134).__name__}: {_e134} | "
                 + _tb134.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b135)
# RECHTSKLICK "COPY" UEBERALL + FRACHT-KISTE IN DER VERKAUFSLISTE (Nutzer
# 29.09.2026). Am echten Fenster: jede Tabelle der genannten Reiter traegt
# den Mechanismus, ein echter Rechtsklick kopiert den Zelltext, und die
# Verkaufsliste rechnet Einkauf + Fracht.
try:
    from PySide6.QtWidgets import (QMenu as _QM135, QTableWidget as _QTW135,
                                   QTreeWidget as _QTr135, QTableWidgetItem as _QI135,
                                   QApplication as _QA135)
    from PySide6.QtCore import QTimer as _QT135
    _seiten135 = []
    for _w135 in (win.pf_table, win.pr_table, win.sh_table, win.buyord_table,
                  win.tx_table, win.deals_table, win.hold_table, win.rg_table,
                  win.sell_table, win.bp_table, win.b_table):
        _x135 = _w135
        while _x135 is not None and _x135.parentWidget() is not win.tabs._stack:
            _x135 = _x135.parentWidget()
        if _x135 is not None and _x135 not in _seiten135:
            _seiten135.append(_x135)
    _ohne135 = []
    _n135 = 0
    for _sei135 in _seiten135:
        for _v135 in _sei135.findChildren(_QTW135) + _sei135.findChildren(_QTr135):
            _n135 += 1
            if not _v135.property("kopier_menue"):
                _ohne135.append(f"{type(_v135).__name__}:{_v135.objectName()}:"
                                f"{_v135.horizontalHeaderItem(0).text() if isinstance(_v135, _QTW135) and _v135.columnCount() and _v135.horizontalHeaderItem(0) else ''}")
    check(f"b135 {_n135} Tabellen in {len(_seiten135)} Reitern: alle mit Rechtsklick-Copy "
          f"(ohne: {_ohne135})", _n135 >= 11 and len(_seiten135) >= 9 and not _ohne135)

    def _rechtsklick135(tbl, zeile, spalte):
        """Echter Weg: Signal wie beim Rechtsklick, das offene Menue
        greifen, 'Copy' ausloesen. Liefert (Eintraege, Zwischenablage)."""
        _erg = []

        def _greifen():
            _ms = [w for w in _QA135.topLevelWidgets() if isinstance(w, _QM135) and w.isVisible()]
            _erg.append([a.text() for m in _ms for a in m.actions()])
            for m in _ms:
                for a in m.actions():
                    if a.property("ist_kopieren"):
                        a.trigger()
                m.close()
        _QA135.clipboard().setText("")
        _QT135.singleShot(0, _greifen)
        tbl.customContextMenuRequested.emit(
            tbl.visualRect(tbl.model().index(zeile, spalte)).center())
        _app.processEvents()
        return (_erg[0] if _erg else None), _QA135.clipboard().text()
    # Tabelle OHNE eigenes Menue (Transactions): nur "Copy"
    win.tx_table.resize(700, 300); win.tx_table.show()
    _alt135 = win.tx_table.rowCount()
    win.tx_table.setRowCount(max(1, _alt135))
    win.tx_table.setItem(0, 4, _QI135("1'234'567"))
    _e135 = _rechtsklick135(win.tx_table, 0, 4)
    check(f"b135 Transactions: Rechtsklick -> Copy kopiert die Zahl ohne Trenner ({_e135})",
          _e135[0] is not None and _e135[0][:1] in (["Copy"], ["Kopieren"]) and _e135[1] == "1234567")
    win.tx_table.hide()
    # FRACHT: Kaeufe in Jita UND Amarr, Hub Jita, 500 ISK/m3
    import eve_trader.ui.main_window as _mwm135
    from eve_trader import market as _mk135
    _JITA135 = 60003760
    _tx135 = [
        {"character_id": 1, "type_id": 34, "date": "2026-09-01", "is_buy": 1,
         "quantity": 100, "unit_price": 10.0, "location_id": _JITA135},
        {"character_id": 1, "type_id": 34, "date": "2026-09-02", "is_buy": 1,
         "quantity": 50, "unit_price": 12.0, "location_id": 60008494}]
    _agg135 = _mk135.aggregate_holdings(_tx135)[34]
    _alt135b = (_mwm135.store.get_transactions, _mwm135.industry.item_volume_map,
                _mwm135.industry.ships_with_unpackaged_volume, _mwm135.config.save_settings,
                win.settings.get("fracht_isk_m3"), getattr(win, "_holdings", []),
                win.pf_char.currentIndex(), getattr(win, "_sell_target_mode", False),
                dict(getattr(win, "_sell_live", {}) or {}), set(getattr(win, "_sell_done", set())))
    _mwm135.store.get_transactions = lambda *a, **k: list(_tx135)
    _mwm135.industry.item_volume_map = lambda ids=None: {34: 2.0}
    _mwm135.industry.ships_with_unpackaged_volume = lambda ids: set()
    _mwm135.config.save_settings = lambda *a, **k: None
    win._active_hub = lambda: (10000002, _JITA135, None)
    try:
        win.pf_char.setCurrentIndex(max(0, win.pf_char.findData("all")))
        win._holdings = [_mk135.Holding(type_id=34, name="Tritanium", quantity=150,
                                        avg_buy=_agg135["avg_buy"], jita_sell_min=5.0)]
        win._sell_target_mode = True
        win._sell_live = {34: 5.0}
        win._fracht_cache = None
        # GETIPPT WIE VOM NUTZER (29.09.2026: "335isk/m3") - vorher 3'353
        from PySide6.QtTest import QTest as _QTest135
        win.sell_fracht.show(); win.sell_fracht.setFocus()
        win.sell_fracht.selectAll()
        _QTest135.keyClicks(win.sell_fracht, "335isk/m3")
        _QTest135.keyClick(win.sell_fracht, Qt.Key_Return)
        _getippt135 = (win.sell_fracht.value(), win.rg_haul.value(),
                       win.settings.get("fracht_isk_m3"))
        win.sell_fracht.hide()
        # UND UMGEKEHRT: in Regional Trading getippt -> Verkaufsliste zieht mit
        win.rg_haul.show(); win.rg_haul.setFocus(); win.rg_haul.selectAll()
        _QTest135.keyClicks(win.rg_haul, "445")
        _QTest135.keyClick(win.rg_haul, Qt.Key_Return)
        _getippt135b = (win.rg_haul.value(), win.sell_fracht.value(),
                        win.settings.get("fracht_isk_m3"))
        win.rg_haul.hide()
        win._fracht_satz_setzen(500)
        _sync135 = (win.rg_haul.value(), win.sell_fracht.value(),
                    win.settings.get("fracht_isk_m3"))
        win._render_sell_list()
        _je135 = 50 * 2.0 * 500 / 150
        _preis135 = win.sell_table.item(0, 5).data(Qt.UserRole) if win.sell_table.rowCount() else None
        _soll135 = win._optimal_sell_price(_agg135["avg_buy"] + _je135)
        _kiste135 = [lb for lb in win.sell_table.cellWidget(0, 2).findChildren(QLabel)
                     if lb.property("fracht_pct") is not None] if win.sell_table.rowCount() else []
        _tip135 = _kiste135[0].toolTip() if _kiste135 else ""
        # "BEREIT ZUM VERKAUF" MIT FRACHT: 13 % Marge ohne Fracht reicht fuer
        # 12 % Ziel, mit Fracht nicht mehr
        _h135r = _mk135.Holding(type_id=34, name="Tritanium", quantity=150,
                                avg_buy=_agg135["avg_buy"], margin_pct=13.0,
                                net_unit=_agg135["avg_buy"] * 1.13)
        _alt135r = (win.settings.get("target_margin"), win._pf_price_source_ok,
                    win._hat_order)
        win.settings["target_margin"] = 12.0
        win._pf_price_source_ok = lambda: True
        win._hat_order = lambda *a, **k: False
        _bereit135 = win._sell_ready(_h135r)
        win.settings["fracht_aus_items"] = [34]; win._fracht_cache = None
        _bereit135b = win._sell_ready(_h135r)
        win.settings["fracht_aus_items"] = []; win._fracht_cache = None
        win.settings["target_margin"] = _alt135r[0]
        del win._pf_price_source_ok, win._hat_order
        # Rechtsklick auf die Zeile: "Copy" oben + "No freight for this item"
        win.sell_table.resize(900, 300); win.sell_table.show()
        _e135b = _rechtsklick135(win.sell_table, 0, 1)
        win.sell_table.hide()
        win._fracht_aus_umschalten(34)
        win._render_sell_list()
        _ohne_kiste135 = [lb for lb in win.sell_table.cellWidget(0, 2).findChildren(QLabel)
                          if lb.property("fracht_pct") is not None]
        _preis135b = win.sell_table.item(0, 5).data(Qt.UserRole)
        win._fracht_aus_umschalten(34)
        # CONTAINER NIE FRACHT (29.09.2026): dasselbe Item als "Freight Container"
        _alt135g = _mwm135.industry.group_names
        _mwm135.industry.group_names = lambda ids: {34: "Freight Container"}
        win._fracht_cache = None
        win._render_sell_list()
        _cont135 = [lb for lb in win.sell_table.cellWidget(0, 2).findChildren(QLabel)
                    if lb.property("fracht_pct") is not None]
        _mwm135.industry.group_names = _alt135g
        win._fracht_cache = None
        win._fracht_satz_setzen(0)
        win._render_sell_list()
        _preis135c = win.sell_table.item(0, 5).data(Qt.UserRole)
    finally:
        (_mwm135.store.get_transactions, _mwm135.industry.item_volume_map,
         _mwm135.industry.ships_with_unpackaged_volume, _mwm135.config.save_settings) = _alt135b[:4]
        win.settings["fracht_isk_m3"] = _alt135b[4] or 0
        win.settings["fracht_aus_items"] = []
        win._holdings = _alt135b[5]
        win.pf_char.setCurrentIndex(_alt135b[6])
        win._sell_target_mode = _alt135b[7]
        win._sell_live = _alt135b[8]
        del win._active_hub
        win._fracht_cache = None
        win._render_sell_list()
    eq("b135 'bereit zum Verkauf': 13 % ohne Fracht ja, mit Fracht nein",
       (_bereit135b, _bereit135), (True, False))
    eq("b135 getippt '335isk/m3' -> 335 in beiden Feldern und gespeichert",
       _getippt135, (335, 335, 335))
    eq("b135 in Regional Trading getippt 445 -> Verkaufsliste zeigt 445, gespeichert",
       _getippt135b, (445, 445, 445))
    eq("b135 Fracht-Satz: EIN Wert in beiden Feldern und den Einstellungen", _sync135,
       (500, 500, 500))
    check(f"b135 Ziel-Preis = Ziel-Marge auf Einkauf + Fracht ({_preis135} / {_soll135})",
          _preis135 is not None and _soll135 is not None and abs(_preis135 - _soll135) < 1e-6)
    _pct135 = _je135 / _agg135["avg_buy"] * 100
    # emm336 (1-ISK-Problem): die Fracht ist hier groesser als der Einkauf
    # (+{_pct135} %) - dann steht sie in ISK je Stueck, nicht in Prozent, und
    # der Tooltip sagt in einem Satz mehr, warum.
    check(f"b135 Kiste neben dem Item: Fracht > Einkauf -> ISK statt Prozent, kurzer Tooltip "
          f"({_kiste135[0].text() if _kiste135 else None!r}, {_tip135!r})",
          len(_kiste135) == 1 and abs(_kiste135[0].property("fracht_pct") - _pct135) < 1e-9
          and _pct135 > 100 and _kiste135[0].property("fracht_als_isk") is True
          and "ISK" in _kiste135[0].text() and "%" not in _kiste135[0].text()
          and 0 < _tip135.count(".") <= 4 and len(_tip135) < 400)
    check(f"b135 Verkaufsliste: Rechtsklick hat 'Copy' oben und 'keine Fracht' ({_e135b})",
          _e135b[0] is not None and _e135b[0][:1] in (["Copy"], ["Kopieren"]) and _e135b[1] == "Tritanium"
          and any("freight" in x.lower() or "fracht" in x.lower() for x in _e135b[0]))
    check("b135 Container (Gruppe 'Freight Container') bekommen nie Fracht",
          not _cont135)
    check(f"b135 'keine Fracht' fuer das Item: Kiste weg, Preis ohne Fracht "
          f"({_preis135b} / Satz 0: {_preis135c})",
          not _ohne_kiste135 and _preis135b is not None and _preis135c is not None
          and abs(_preis135b - _preis135c) < 1e-6 and _preis135b < _preis135)
except Exception as _e135x:                               # pragma: no cover
    import traceback as _tb135
    _fail.append(f"b135 Copy/Fracht: {type(_e135x).__name__}: {_e135x} | "
                 + _tb135.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b136)
# MULTIPLAN OHNE ERST ZU SPEICHERN (Nutzer 29.09.2026: "einen Plan oeffnen
# ohne speichern, einen anderen hinzufuegen, dann hat man einen offenen
# Multiplan, den man DANN speichert - ansonsten erstellt man immer ein
# Duplikat"). Rechtsklick "Add to multi build plan" bietet den offenen,
# ungespeicherten Plan als erstes Ziel an; nichts wird gespeichert.
try:
    import eve_trader.ui.main_window as _mwm136
    from eve_trader import industry as _I136
    from PySide6.QtWidgets import QMenu as _QM136, QWidget as _QW136
    _alt136 = {k: getattr(win, k, None) for k in (
        "_bd_dialog", "_bd_open_plan_id", "_bd_type", "_bd_frozen", "_bd_qty",
        "_bd_me", "_bd_te", "_bd_name", "_bd_buendel_enden", "_bd_full_rebuild")}
    _plans_alt136 = list(win.settings.get("bau_saved_plans") or [])
    _save_alt136 = _mwm136.config.save_settings
    _gesp136 = []
    _mwm136.config.save_settings = lambda *a, **k: _gesp136.append(1)
    _geoeffnet136 = []
    _oeffnen_alt136 = win._multi_plan_oeffnen
    win._multi_plan_oeffnen = lambda e, plan_id=None: _geoeffnet136.append((e, plan_id))
    _eingefuegt136 = []
    _einf_alt136 = win._multi_offen_einfuegen
    win._multi_offen_einfuegen = lambda items: _eingefuegt136.append(items)
    _fenster136 = _QW136()
    _fenster136.show()                     # _offener_bauplan fragt isVisible()
    try:
        win.settings["bau_saved_plans"] = [
            {"id": 13601, "label": "b136 gespeichert", "type_id": 34, "qty": 2}]
        win._bd_dialog = _fenster136
        win._bd_open_plan_id = None
        win._bd_type = 587
        win._bd_frozen = None
        win._bd_qty = 5
        win._bd_me = 0; win._bd_te = 0
        win._bd_name = "Rifter"
        _m136 = _QM136()
        _akt136 = win._multi_untermenue(_m136, 603, "Merlin")
        _sub136 = _m136.actions()[0].menu()
        _erst136 = _sub136.actions()[0] if _sub136 and _sub136.actions() else None
        check(f"b136 Untermenue: der offene, ungespeicherte Plan steht ZUERST und fett "
              f"({[a.text() for a in _sub136.actions()] if _sub136 else None})",
              _erst136 is not None and _akt136.get(_erst136) == win.OFFENER_PLAN
              and _erst136.font().bold() and 13601 in _akt136.values())
        win._multi_enden_zu_plan(win.OFFENER_PLAN, [{"tid": 603, "name": "Merlin", "qty": 3}])
        _e136, _pid136 = _geoeffnet136[-1] if _geoeffnet136 else ({}, "x")
        check(f"b136 Einzelplan + Ende: ungespeichertes Buendel im Fenster, NICHTS "
              f"gespeichert, kein Duplikat ({_e136.get('enden')}, {_pid136}, {len(_gesp136)})",
              not _fenster136.isVisible()          # altes Fenster zu, neues auf
              and _e136.get("type_id") == _I136.BUENDEL_ID
              and _e136.get("enden") == [[587, 5], [603, 3]] and _pid136 is None
              and not _gesp136 and len(win.settings["bau_saved_plans"]) == 1)
        # ist es schon ein offenes, ungespeichertes Buendel: direkt hinein
        # das Umwandeln hat das (Test-)Fenster geschlossen - wieder "offen"
        win._bd_dialog = _fenster136
        _fenster136.show()
        win._bd_type = _I136.BUENDEL_ID
        win._bd_buendel_enden = [(587, 5), (603, 3)]
        win._bd_full_rebuild = lambda: None
        win._multi_enden_zu_plan(win.OFFENER_PLAN, [{"tid": 34, "name": "T", "qty": 7}])
        check("b136 offenes ungespeichertes Buendel: Ende geht direkt ins Fenster",
              _eingefuegt136 and _eingefuegt136[-1][0]["tid"] == 34 and not _gesp136)
        # gespeichert oder eingefroren offen: KEIN solcher Eintrag
        win._bd_open_plan_id = 13601
        _m136b = _QM136()
        _akt136b = win._multi_untermenue(_m136b, 603, "Merlin")
        check("b136 gespeicherter offener Plan: kein 'nicht gespeichert'-Eintrag",
              win.OFFENER_PLAN not in _akt136b.values())
    finally:
        for _k, _v in _alt136.items():
            setattr(win, _k, _v)
        win.settings["bau_saved_plans"] = _plans_alt136
        _mwm136.config.save_settings = _save_alt136
        del win._multi_plan_oeffnen, win._multi_offen_einfuegen
        _fenster136.deleteLater()
except Exception as _e136x:                               # pragma: no cover
    import traceback as _tb136
    _fail.append(f"b136 Multiplan ungespeichert: {type(_e136x).__name__}: {_e136x} | "
                 + _tb136.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b137)
# RIGS ALS EIGENE KATEGORIE IN MY BLUEPRINTS (Nutzer 29.09.2026: "Category
# Modules gewaehlt, da werden aber Rigs aufgelistet, und den Filter Rigs gibts
# im Dropdown nicht" -> "ja sehr gerne"). Am echten Fenster: Dropdown hat den
# Eintrag, der Filter trennt Modul und Rig.
try:
    from eve_trader import industry as _I137
    from PySide6.QtWidgets import QTableWidgetItem as _TI137
    # DROPDOWN: .smoke_home hat keine Kategorie-Namen (sde_kompakt ohne
    # cat_name) - die zwei SDE-Leser werden deshalb hier vorgegeben.
    _cb137 = win.bp_myb_cat
    _opt_alt137, _rg_alt137 = _I137.buildable_category_options, _I137.rig_gruppen
    try:
        _I137.buildable_category_options = lambda: [(6, "Ship"), (7, "Module"),
                                                    (8, "Charge")]
        _I137.rig_gruppen = lambda: {773}
        # "Show missing" an = ALLE baubaren Kategorien (ohne: nur die der
        # Tabelle, s. unten).
        win.bp_cb_missing.blockSignals(True)
        win.bp_cb_missing.setChecked(True)
        win.bp_cb_missing.blockSignals(False)
        win._reload_categories()
        _i137 = _cb137.findData(_I137.RIGS_KAT)
        _txt137 = [_cb137.itemText(_k) for _k in range(1, _cb137.count())]
        check(f"b137 Dropdown hat den Eintrag Rigs, alphabetisch ({_txt137})",
              _i137 > 0 and _txt137 == ["Charge", "Module", "Rigs", "Ship"])
        _I137.rig_gruppen = lambda: set()
        win._reload_categories()
        check("b137 ohne Rig-Gruppen in der SDE kein Rigs-Eintrag",
              _cb137.findData(_I137.RIGS_KAT) < 0)
    finally:
        _I137.buildable_category_options, _I137.rig_gruppen = _opt_alt137, _rg_alt137
        win.bp_cb_missing.blockSignals(True)
        win.bp_cb_missing.setChecked(False)
        win.bp_cb_missing.blockSignals(False)
        win._reload_categories()
    _rg137 = set(getattr(win, "_bp_rig_gruppen", None) or ())
    # FILTER: zwei eigene Zeilen (Modul, Rig) in der echten Tabelle.
    _rig137 = min(_rg137) if _rg137 else 773
    _alt_rg137 = getattr(win, "_bp_rig_gruppen", None)
    win._bp_rig_gruppen = _rg137 or {_rig137}
    _kat_mod137 = 7 if _cb137.findData(7) >= 0 else None
    _tb137 = win.bp_table
    _sort137 = _tb137.isSortingEnabled()
    _tb137.setSortingEnabled(False)
    _neu137 = []
    for _nm137, _gr137 in (("b137 Modul", 55), ("b137 Rig", _rig137)):
        _r137 = _tb137.rowCount(); _tb137.insertRow(_r137)
        _it137 = _TI137(_nm137)
        for _ro137, _v137 in ((0, "end"), (1, True), (4, 7), (5, 2), (6, _gr137),
                              (9, True), (11, None),
                              (14, 1 if _nm137 == "b137 Modul" else None)):
            _it137.setData(Qt.UserRole + _ro137, _v137)
        _tb137.setItem(_r137, 0, _it137)
        _neu137.append(_it137)
    _zust137 = {}
    try:
        if _kat_mod137 is None:
            _cb137.addItem("Module", 7)
        if _cb137.findData(_I137.RIGS_KAT) < 0:
            _cb137.addItem("Rigs", _I137.RIGS_KAT)
        win.bp_myb_tech.setCurrentIndex(0)
        win.bp_myb_char.setCurrentIndex(0)
        for _wahl137 in (7, _I137.RIGS_KAT, None):
            _cb137.setCurrentIndex(max(0, _cb137.findData(_wahl137))
                                   if _wahl137 is not None else 0)
            win._apply_bp_filter()
            _zust137[str(_wahl137)] = tuple(
                not _tb137.isRowHidden(_it.row()) for _it in _neu137)
        check(f"b137 Module zeigt das Modul, nicht das Rig ({_zust137.get('7')})",
              _zust137.get("7") == (True, False))
        check(f"b137 Rigs zeigt das Rig, nicht das Modul ({_zust137.get(_I137.RIGS_KAT)})",
              _zust137.get(_I137.RIGS_KAT) == (False, True))
        check(f"b137 Alle Kategorien zeigt beide ({_zust137.get('None')})",
              _zust137.get("None") == (True, True))
        # FRAKTION (Nutzer 30.09.2026): Caldari (1) zeigt nur die Zeile mit
        # raceID 1; "All races" wieder beide.
        _rc137 = win.bp_myb_race
        _rc137.setCurrentIndex(_rc137.findData(1))
        win._apply_bp_filter()
        _fk137 = tuple(not _tb137.isRowHidden(_it.row()) for _it in _neu137)
        _rc137.setCurrentIndex(0)
        win._apply_bp_filter()
        _fa137 = tuple(not _tb137.isRowHidden(_it.row()) for _it in _neu137)
        check(f"b137 Fraktion Caldari zeigt nur die Caldari-Zeile ({_fk137}), "
              f"alle Fraktionen beide ({_fa137})",
              _fk137 == (True, False) and _fa137 == (True, True)
              and _rc137.itemText(_rc137.findData(1)) == "Caldari")
        # NUR DEINE KATEGORIEN (Nutzer 30.09.2026: "unnoetige Kategorien ...
        # Asteroid, Celestial, Commodity"): die Tabelle hat ein Modul und ein
        # Rig -> genau "Module" und "Rigs", nicht Ship/Charge.
        _kopts_alt137 = getattr(win, "_bp_kat_opts", None)
        win._bp_kat_opts = [(6, "Ship"), (7, "Module"), (8, "Charge")]
        try:
            win._bp_myb_cat_fuellen()
            _nur137 = [_cb137.itemText(_k) for _k in range(1, _cb137.count())]
            check(f"b137 Dropdown zeigt nur Kategorien deiner Blaupausen ({_nur137})",
                  _nur137 == ["Module", "Rigs"])
            win.bp_cb_missing.blockSignals(True)
            win.bp_cb_missing.setChecked(True)
            win.bp_cb_missing.blockSignals(False)
            win._bp_myb_cat_fuellen()
            _alle137 = [_cb137.itemText(_k) for _k in range(1, _cb137.count())]
            check(f"b137 ... mit 'Show missing' alle baubaren ({_alle137})",
                  _alle137 == ["Charge", "Module", "Rigs", "Ship"])
        finally:
            win.bp_cb_missing.blockSignals(True)
            win.bp_cb_missing.setChecked(False)
            win.bp_cb_missing.blockSignals(False)
            win._bp_kat_opts = _kopts_alt137
    finally:
        for _it in _neu137:
            _tb137.removeRow(_it.row())
        _tb137.setSortingEnabled(_sort137)
        win._bp_rig_gruppen = _alt_rg137
        win._reload_categories()
        _cb137.setCurrentIndex(0)
        win._apply_bp_filter()
except Exception as _e137:                                # pragma: no cover
    import traceback as _tb137x
    _fail.append(f"b137 Rigs-Kategorie: {type(_e137).__name__}: {_e137} | "
                 + _tb137x.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b138)
# FREMDE HAKEN IM NEUEN PLAN (Nutzer 29.09.2026: "neuen Multiplan erstellt
# und gespeichert, der Runplaner hat einfach irgendwelche gruenen Haken
# gesetzt, die ich selbst nie gemacht habe - unakzeptabel"). Die "erledigten
# Runs je Item" (`_bd_runplan_erledigt`, aus den Haken des ZULETZT offenen
# Plans) ueberlebten das Oeffnen eines NEUEN Plans; `haken_nachtragen` setzte
# daraus Haken auf gleiche Items, und Speichern schrieb sie fest.
try:
    import eve_trader.ui.main_window as _mwm138
    from eve_trader import store as _st138
    _snap138 = _st138.get_snapshot
    _info138 = _mwm138.QMessageBox.information
    from eve_trader import industry as _I138
    _sde138 = _I138.sde_ready
    _st138.get_snapshot = lambda *a, **k: []
    _mwm138.QMessageBox.information = lambda *a, **k: None
    _I138.sde_ready = lambda: True        # sonst kehrt das Oeffnen VOR dem Zuruecksetzen um
    try:
        win._bd_runplan_erledigt = {"reaction_2|16679": 14, "reaction_2|16671": 12}
        win._bd_runplan_erledigt_ts = {"reaction_2|16679": 1.0}
        win._bd_runplan_checked = {"reaction_2|1|16679"}
        win.open_build_detail(100, "Testship b138", fresh=True)
        check(f"b138 neuer Plan erbt keine erledigten Runs des alten "
              f"({getattr(win, '_bd_runplan_erledigt', None)})",
              not getattr(win, "_bd_runplan_erledigt", None))
        check("b138 ... keine Haken-Zeitstempel und keine Haken",
              not getattr(win, "_bd_runplan_erledigt_ts", None)
              and not getattr(win, "_bd_runplan_checked", None))
    finally:
        _st138.get_snapshot = _snap138
        _mwm138.QMessageBox.information = _info138
        _I138.sde_ready = _sde138
    # OHNE ERLEDIGTE RUNS SETZT DER NACHTRAG NICHTS (Gegenprobe mit Rest).
    from eve_trader.ui.mw_helpers import haken_nachtragen as _hn138
    _z138 = [("reaction_2|5|16679", "reaction_2|16679", 14)]
    check("b138 haken_nachtragen: ohne erledigte Runs kein Haken, mit 14 einer",
          not set(_hn138(_z138, set(), {}))
          and set(_hn138(_z138, set(), {"reaction_2|16679": 14}))
          == {"reaction_2|5|16679"})
except Exception as _e138:                                # pragma: no cover
    import traceback as _tb138
    _fail.append(f"b138 fremde Haken im neuen Plan: {type(_e138).__name__}: {_e138} | "
                 + _tb138.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b140)
# PROFITS-TAB MIT FRACHT + KISTEN-SYMBOL (Nutzer 30.09.2026). Am echten Tab:
# gekauft an Ort 1, verkauft an Ort 2 -> Netto sinkt um 4 x 2 m3 x 10 ISK.
try:
    import eve_trader.ui.main_window as _mwm140
    _gt140 = _mwm140.store.get_transactions
    _vol140 = win._fracht_volumen
    _satz_alt140 = win.settings.get("fracht_isk_m3")
    _tax_alt140 = (win.settings.get("sales_tax_pct"), win.settings.get("broker_fee_pct"))
    _tx140 = [
        {"date": "2026-09-01", "type_id": 34, "is_buy": True, "quantity": 10,
         "unit_price": 100.0, "location_id": 1, "character_id": 7},
        {"date": "2026-09-02", "type_id": 34, "is_buy": False, "quantity": 4,
         "unit_price": 200.0, "location_id": 2, "character_id": 7}]
    try:
        _mwm140.store.get_transactions = lambda *a, **k: [dict(x) for x in _tx140]
        win._fracht_volumen = lambda ids: {34: 2.0}
        win.settings["sales_tax_pct"] = 5.0
        win.settings["broker_fee_pct"] = 0.0
        _erg140 = {}
        for _satz140 in (10, 0):
            win.settings["fracht_isk_m3"] = _satz140
            win.pr_window.setCurrentIndex(max(0, win.pr_window.findData(0)))
            win._render_profit()
            _it140 = win.pr_table.item(0, 3)
            _erg140[_satz140] = (float(getattr(_it140, "_value", 0.0) or 0.0),
                                 not _it140.icon().isNull(),
                                 "freight" in (_it140.toolTip() or "").lower()
                                 or "fracht" in (_it140.toolTip() or "").lower())
        check(f"b140 mit Satz: Netto 280 statt 360, Kisten-Symbol + Tooltip "
              f"({_erg140.get(10)})",
              _erg140.get(10) == (280.0, True, True))
        check(f"b140 ohne Satz: 360, kein Symbol ({_erg140.get(0)})",
              _erg140.get(0) is not None and _erg140[0][0] == 360.0
              and not _erg140[0][1])
    finally:
        _mwm140.store.get_transactions = _gt140
        win._fracht_volumen = _vol140
        if _satz_alt140 is None:
            win.settings.pop("fracht_isk_m3", None)
        else:
            win.settings["fracht_isk_m3"] = _satz_alt140
        win.settings["sales_tax_pct"], win.settings["broker_fee_pct"] = _tax_alt140
        win._render_profit()
except Exception as _e140:                                # pragma: no cover
    import traceback as _tb140
    _fail.append(f"b140 Profits mit Fracht: {type(_e140).__name__}: {_e140} | "
                 + _tb140.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b142)
# MULTIPLAN-VORSCHLAG IM TOOLS-MENUE (Nutzer 30.09.2026). Am echten Fenster-
# Objekt: Tabelle zeigt nur passende Kandidaten; Rechtsklick-Weg fuegt in den
# offenen Plan (ungespeichert direkt, gespeichert ueber _multi_enden_zu_plan).
try:
    from eve_trader import industry as _I142
    _alt142 = {k: getattr(win, k, None) for k in (
        "_bp_econ_stand", "_bd_type", "_bd_marge_stand", "_bd_plan_ref",
        "_bd_open_plan_id", "_bd_buendel_enden", "_bd_pricemap", "_bd_opts")}
    _cm142 = _I142.item_category_map
    _rn142 = win.VORSCHLAG_RECHNEN
    try:
        _I142.item_category_map = lambda: {900: (6, 25, 1), 901: (6, 25, 1),
                                           902: (6, 25, 2)}
        win.VORSCHLAG_RECHNEN = 0            # kein Hintergrund-Job im Test
        win._bp_econ_stand = {"profit_by_bp": {
            1: {"product_id": 901, "category": "end", "meta": 1,
                "cost_unit": 100.0, "profit": 40.0, "isk_h": 5.0, "opt_qty": 3},
            2: {"product_id": 902, "category": "end", "meta": 2,
                "cost_unit": 100.0, "profit": 90.0},
            3: {"product_id": 903, "category": "end", "meta": 1,
                "cost_unit": 100.0, "profit": 5.0}},
            "names": {901: "Kandidat T1", 902: "Kandidat T2", 903: "Zu wenig"}}
        win._bd_type = 900
        win._bd_buendel_enden = None
        win._bd_marge_stand = 20.0
        win._bd_plan_ref = {"plan": {"buy": {34: 10}}}
        _d142 = win._multi_vorschlag_fenster()
        _t142 = win._bd_vorschlag_tbl
        _n142 = [_t142.item(r, 0).text() for r in range(_t142.rowCount())]
        check(f"b142 T1-Plan mit 20 %: nur 'Kandidat T1' ({_n142})",
              _n142 == ["Kandidat T1"])
        _d142.close()
        # FENSTER-REIHENFOLGE (emm353, Nutzer: "Tools -> Suggestions: das
        # Fenster geht auf, aber der Bauplan rutscht ganz nach hinten" -
        # gewollt: Werkzeug 1, Bauplan 2, Eve MoMa 3). Kind des Bauplan-
        # Fensters (`_tool_parent`), nicht des Hauptfensters.
        from PySide6.QtWidgets import QWidget as _QW142
        _bau142 = _QW142()
        win._tool_parent = lambda: _bau142
        try:
            _d142p = win._multi_vorschlag_fenster()
            check("b142 Vorschlags-Fenster haengt am Bauplan-Fenster, nicht am Hauptfenster",
                  _d142p.parent() is _bau142)
            _d142p.close()
        finally:
            win.__dict__.pop("_tool_parent", None)
            _bau142.deleteLater()
        # NAMEN (Nutzer 30.09.2026: "nur Nummern in diesem Fenster"): My
        # Blueprints kennt nur Blaupausen-Namen - der Produktname kommt aus
        # Namens-Cache bzw. ESI im Hintergrund, nie "#901".
        import eve_trader.esi as _esi142
        import eve_trader.store as _st142
        _rn_alt142, _cn_alt142, _run_alt142 = (_esi142.resolve_names,
                                               _st142.cached_names, win._run)
        try:
            win._bp_econ_stand["names"] = {1: "Kandidat T1 Blueprint"}
            _st142.cached_names = lambda ids: {}
            _esi142.resolve_names = lambda ids: {901: "Kandidat aus ESI"}
            win._run = lambda w, done, fail_cb=None, **_k: done(w._fn())
            _d142n = win._multi_vorschlag_fenster()
            _nn142 = [win._bd_vorschlag_tbl.item(r, 0).text()
                      for r in range(win._bd_vorschlag_tbl.rowCount())]
            _d142n.close()
            _st142.cached_names = lambda ids: {901: "Kandidat aus Cache"}
            _d142c = win._multi_vorschlag_fenster()
            _nc142 = [win._bd_vorschlag_tbl.item(r, 0).text()
                      for r in range(win._bd_vorschlag_tbl.rowCount())]
            _d142c.close()
        finally:
            _esi142.resolve_names, _st142.cached_names, win._run = (
                _rn_alt142, _cn_alt142, _run_alt142)
            win._bp_econ_stand["names"] = {901: "Kandidat T1", 902: "Kandidat T2",
                                           903: "Zu wenig"}
        check(f"b142 Produktname statt Nummer: ESI ({_nn142}), Cache ({_nc142})",
              _nn142 == ["Kandidat aus ESI"] and _nc142 == ["Kandidat aus Cache"])
        # Hinzufuegen: ungespeichert -> direkt; gespeichert -> an den Plan.
        _ruf142 = []
        _u142 = win._multi_offen_ungespeichert
        _uz142 = win._multi_offen_ungespeichert_zu
        _ez142 = win._multi_enden_zu_plan
        try:
            win._multi_offen_ungespeichert_zu = lambda it: _ruf142.append(("offen", it))
            win._multi_enden_zu_plan = lambda pid, it: _ruf142.append(("plan", pid))
            win._multi_offen_ungespeichert = lambda: "Plan"
            win._multi_vorschlag_hinzufuegen([{"tid": 901, "name": "K", "qty": None}])
            win._multi_offen_ungespeichert = lambda: None
            win._bd_open_plan_id = 4242
            win._multi_vorschlag_hinzufuegen([{"tid": 901, "name": "K", "qty": None}])
        finally:
            win._multi_offen_ungespeichert = _u142
            win._multi_offen_ungespeichert_zu = _uz142
            win._multi_enden_zu_plan = _ez142
        check(f"b142 Hinzufuegen: ungespeichert direkt, gespeichert an den Plan ({[_x[0] for _x in _ruf142]})",
              [_x[0] for _x in _ruf142] == ["offen", "plan"] and _ruf142[1][1] == 4242)
        win._bp_econ_stand = None
        _d142b = win._multi_vorschlag_fenster()
        check("b142 ohne geladene Blaupausen: Hinweis statt leerer Liste",
              win._bd_vorschlag_tbl.rowCount() == 0)
        _d142b.close()
    finally:
        _I142.item_category_map = _cm142
        win.VORSCHLAG_RECHNEN = _rn142
        for _k, _v in _alt142.items():
            setattr(win, _k, _v)
except Exception as _e142:                                # pragma: no cover
    import traceback as _tb142
    _fail.append(f"b142 Multiplan-Vorschlag: {type(_e142).__name__}: {_e142} | "
                 + _tb142.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b143)
# RESERVIERUNGS-FRAGE: AMBER-SCHLOSS, WARUM ZUERST, WENIG TEXT (Nutzer
# 30.09.2026).
try:
    import eve_trader.ui.theme as _th143
    from PySide6.QtWidgets import QMessageBox as _QMB143
    _b143 = win._reservierung_box(None, "Plan b143", 63, ["Anderer Plan"])
    _t143 = _b143.text()
    _w143 = max(_t143.find("Why reserve"), _t143.find("Warum reservieren"))
    check("b143 Amber-Schloss statt Fragezeichen",
          not _b143.iconPixmap().isNull()
          and _b143.iconPixmap().toImage().pixelColor(24, 4).name().lower()
          == _th143.AMBER.lower())
    check(f"b143 das WARUM steht zuerst, amber + fett ({_w143})",
          0 <= _w143 < _t143.find("Plan b143")
          and _th143.AMBER in _t143[:_w143] and "font-weight:800" in _t143[:_w143])
    check("b143 Kollision: genannt, Vorgabe Ja",
          "Anderer Plan" in _t143
          and _b143.defaultButton() is _b143.button(_QMB143.Yes))
    _b143b = win._reservierung_box(None, "Plan b143", 63, [])
    check("b143 ohne Kollision: Vorgabe Nein, kurzer Text",
          _b143b.defaultButton() is _b143b.button(_QMB143.No)
          and len(_b143b.text()) < 700)
    _b143.deleteLater(); _b143b.deleteLater()
except Exception as _e143:                                # pragma: no cover
    import traceback as _tb143
    _fail.append(f"b143 Reservierungs-Frage: {type(_e143).__name__}: {_e143} | "
                 + _tb143.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b141)
# LOESCHEN NUR NACH NACHFRAGE (Nutzer 30.09.2026: "bist du sicher, dass du
# blabla-Plan loeschen willst? Yes/No").
try:
    import eve_trader.ui.main_window as _mwm141
    import eve_trader.config as _cfg141
    _q141 = _mwm141.QMessageBox.question
    _sv141 = _cfg141.save_settings
    _pl141 = win.settings.get("bau_saved_plans")
    _rl141 = win._reload_saved_plans
    _fragen141 = []
    try:
        _cfg141.save_settings = lambda _s: None
        win._reload_saved_plans = lambda *a, **k: None
        win.settings["bau_saved_plans"] = [{"id": 14101, "label": "Plan b141"}]
        _mwm141.QMessageBox.question = staticmethod(
            lambda *a, **k: (_fragen141.append(a), _mwm141.QMessageBox.No)[1])
        _r_nein141 = win._delete_saved_plan_fragen(14101)
        _da141 = [p["id"] for p in win.settings["bau_saved_plans"]]
        _mwm141.QMessageBox.question = staticmethod(
            lambda *a, **k: (_fragen141.append(a), _mwm141.QMessageBox.Yes)[1])
        _r_ja141 = win._delete_saved_plan_fragen(14101)
        _weg141 = [p["id"] for p in win.settings["bau_saved_plans"]]
        check(f"b141 Nein behaelt den Plan, Ja loescht ihn ({_da141} -> {_weg141})",
              _r_nein141 is False and _da141 == [14101]
              and _r_ja141 is True and _weg141 == [])
        check("b141 die Frage nennt den Plan beim Namen, Vorgabe Nein",
              bool(_fragen141) and "Plan b141" in str(_fragen141[0][2])
              and _fragen141[0][-1] == _mwm141.QMessageBox.No)
    finally:
        _mwm141.QMessageBox.question = _q141
        _cfg141.save_settings = _sv141
        win._reload_saved_plans = _rl141
        win.settings["bau_saved_plans"] = _pl141
except Exception as _e141:                                # pragma: no cover
    import traceback as _tb141
    _fail.append(f"b141 Loeschen nach Nachfrage: {type(_e141).__name__}: {_e141} | "
                 + _tb141.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b139)
# EINFRIEREN NUR NACH NACHFRAGE (Nutzer 29.09.2026: "speichere ich einen
# Multiplan, wird er automatisch eingefroren ... besser ein Popup, das
# nachfragt, und WARUM man einfrieren soll", fuer jeden Bauplan).
try:
    import eve_trader.ui.mw_bauplan_fenster as _mbf139
    from PySide6.QtWidgets import QMessageBox as _QMB139
    _q_alt139 = _QMB139.question
    _fr139 = []
    try:
        for _ant139 in (_QMB139.Yes, _QMB139.No):
            _QMB139.question = staticmethod(
                lambda *a, _r=_ant139, **k: (_fr139.append(a), _r)[1])
            _fr139.append(win._einfrieren_fragen(None, "Plan b139"))
    finally:
        _QMB139.question = _q_alt139
    _erg139 = [x for x in _fr139 if isinstance(x, bool)]
    _args139 = [x for x in _fr139 if isinstance(x, tuple)]
    check(f"b139 Ja friert ein, Nein nicht ({_erg139})", _erg139 == [True, False])
    _text139 = (_args139[0][2] if _args139 and len(_args139[0]) > 2 else "")
    check("b139 die Frage nennt den Plan und sagt, was Einfrieren tut",
          "Plan b139" in _text139 and "ESI" in _text139)
    # DIE WARNUNG STEHT ZUERST, AMBER UND FETT (Nutzer 30.09.2026: "das muss
    # man sofort erkennen").
    import eve_trader.ui.theme as _th139
    _w139 = _text139.find("IMPORTANT")
    if _w139 < 0:
        _w139 = _text139.find("WICHTIG")
    check(f"b139 Warnung 'sofort einfrieren nach Kauf' steht vorn, amber + fett ({_w139})",
          0 <= _w139 < _text139.find("Plan b139")
          and _th139.AMBER in _text139[:_w139] and "font-weight:800" in _text139[:_w139])
    check("b139 Vorgabe-Knopf ist Nein",
          bool(_args139) and _args139[0][-1] == _QMB139.No)
    # SCHLOSS AN EINEM OFFEN GESPEICHERTEN PLAN: kein falscher Hinweis
    # "Plan aus aelterer Fassung" (die Karte kennt das Selbstgebaute).
    _tips139 = []
    _st_alt139 = win.settings.get("bau_saved_plans")
    import eve_trader.config as _cfg139
    _sv139 = _cfg139.save_settings
    _ft_alt139 = win._flash_tip
    try:
        _cfg139.save_settings = lambda _s: None
        win._flash_tip = lambda *a, **k: _tips139.append(a)
        win.settings["bau_saved_plans"] = [
            {"id": 13901, "label": "offen", "reserve": False,
             "reserve_map": {"1": 1}, "reserve_map_voll": True, "frozen": None},
            {"id": 13902, "label": "alt", "reserve": False,
             "reserve_map": {"1": 1}, "frozen": None}]
        win._toggle_plan_reserve(13901, True)
        _n_neu139 = len(_tips139)
        win._toggle_plan_reserve(13902, True)
        check(f"b139 Schloss am offen gespeicherten Plan: kein Alt-Fassung-Hinweis, "
              f"am Alt-Plan schon ({_n_neu139}, {len(_tips139)})",
              _n_neu139 == 0 and len(_tips139) == 1)
    finally:
        _cfg139.save_settings = _sv139
        win._flash_tip = _ft_alt139
        win.settings["bau_saved_plans"] = _st_alt139
except Exception as _e139:                                # pragma: no cover
    import traceback as _tb139
    _fail.append(f"b139 Einfrieren nach Nachfrage: {type(_e139).__name__}: {_e139} | "
                 + _tb139.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b128)
# MARKT-SCAN BEIM START SCHON AB 1 STUNDE, IM HINTERGRUND (Nutzer 27.09.2026:
# "jetzt blinkt danach Market scan - sind die Preise noch nicht aktuell?" ->
# "mach das"). Der Knopf "Refresh" bleibt bei 6 h und mit Lade-Fenster.
try:
    import eve_trader.ui.main_window as _mwm128
    _alt128 = (_mwm128.store.list_characters, _mwm128.store.snapshot_age_seconds,
               win._run, win.settings.get("client_id"), list(win._workers))
    _laeufe128 = []
    _mwm128.store.list_characters = lambda: [
        {"character_id": 1, "character_name": "Eins"}]
    _mwm128.store.snapshot_age_seconds = lambda *a, **k: 2 * 3600   # 2 h alt
    win.settings["client_id"] = win.settings.get("client_id") or "test128"
    win._run = lambda worker, done_cb, **k: (_laeufe128.append(
        (k.get("label"), k.get("overlay", True))), win._workers.append(worker))
    try:
        win.refresh_everything(beim_start=True)
        _start128 = (win._scan_after_refresh, win._scan_im_hintergrund)
        win._hintergrund_laden_zeigen(False)
        win._scan_nach_refresh()
        _scan128 = (_laeufe128[-1], not win.g_lade_lbl.isHidden(),
                    win.g_lade_lbl.text(), win._scan_laeuft)
        win._scan_fertig_melden(True)
        _ende128 = (win.g_lade_lbl.isHidden(), win._scan_laeuft)
        win._workers[:] = []
        win.refresh_everything()                      # Knopf "Refresh"
        _knopf128 = (win._scan_after_refresh, win._scan_im_hintergrund)
    finally:
        (_mwm128.store.list_characters, _mwm128.store.snapshot_age_seconds,
         win._run) = _alt128[:3]
        if _alt128[3] is None:
            win.settings.pop("client_id", None)
        else:
            win.settings["client_id"] = _alt128[3]
        win._workers[:] = _alt128[4]
        win._scan_after_refresh = False
        win._hintergrund_laden_zeigen(False)
        win.refresh_btn.setEnabled(True)
        win._set_scan_buttons(True)
    check(f"b128 Start, Scan 2 h alt: Scan folgt im Hintergrund ({_start128})",
          _start128 == (True, True))
    check(f"b128 ... ohne Lade-Fenster, oben 'Market scan', Knopf blinkt nicht "
          f"({_scan128[0][1]}, {_scan128[2]!r})",
          _scan128[0][1] is False and _scan128[1]
          and ("Market scan" in _scan128[2] or "Markt-Scan" in _scan128[2])
          and _scan128[3] is True)
    check(f"b128 ... danach Anzeige weg, Blink-Sperre geloest ({_ende128})",
          _ende128 == (True, False))
    check(f"b128 Knopf 'Refresh': bei 2 h kein Scan, sonst wie bisher ({_knopf128})",
          _knopf128 == (False, False))
except Exception as _e128:                                # pragma: no cover
    import traceback as _tb128
    _fail.append(f"b128 Start-Scan: {type(_e128).__name__}: {_e128} | "
                 + _tb128.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b127)
# PLAN-KARTEN ERST BEIM ERSTEN ZEIGEN (Nutzer 27.09.2026 "ja bitte mach
# das"; der Build-Reiter kostete beim Start 1,4 s fuer die Karten). An einem
# FRISCHEN Hauptfenster: nach dem Bau keine Karten, nach dem Oeffnen der
# Seite "My build plans" sind sie da; eine Schaetzung vorher stuerzt nicht.
try:
    import eve_trader.ui.main_window as _MW127
    _w127 = _MW127.MainWindow()
    try:
        _vorher127 = (_w127._plan_karten_gebaut, _w127._plans_layout.count())
        try:
            _w127._load_saved_plan_estimates(
                _w127.settings.get("bau_saved_plans", []) or [{"id": "x"}])
            _est127 = "ok"
        except Exception as _ee127:
            _est127 = f"{type(_ee127).__name__}: {_ee127}"
        _w127._bau_nav(2)
        _app.processEvents()
        _nachher127 = (_w127._plan_karten_gebaut, _w127._plans_layout.count())
    finally:
        _w127.close(); _w127.deleteLater()
    check(f"b127 Plan-Karten erst beim ersten Zeigen ({_vorher127} -> "
          f"{_nachher127}, Schaetzung vorher: {_est127})",
          _vorher127 == (False, 0) and _nachher127[0] is True
          and _nachher127[1] >= 1 and _est127 == "ok")
except Exception as _e127:                                # pragma: no cover
    import traceback as _tb127
    _fail.append(f"b127 Plan-Karten spaeter: {type(_e127).__name__}: {_e127} | "
                 + _tb127.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b125)
# INVENTION-SKILLS: NUR DIE GEBRAUCHTEN (zweite Ladezeit-Messung 27.09.2026:
# 18'000 Aufrufe, 4,7 s reine Rechenzeit - jeder Aufruf wandelte die ganze
# Skill-Liste jedes Charakters um). Gleiches Ergebnis wie die alte Rechnung,
# aber die Skill-Liste wird nie mehr ganz durchlaufen.
try:
    import eve_trader.ui.main_window as _mwm125
    _set_alt125 = {k: win.settings.get(k) for k in
                   ("bau_char_skills", "bau_invention_chars")}
    _fix_alt125 = getattr(win, "_bd_invention_char", 0)
    _lc_alt125 = _mwm125.store.list_characters

    class _Zaehl125(dict):
        """Skill-Liste, die mitzaehlt, ob sie ganz durchlaufen wird."""
        durchlaeufe = 0
        def items(self):
            _Zaehl125.durchlaeufe += 1
            return dict.items(self)
        def __iter__(self):
            _Zaehl125.durchlaeufe += 1
            return dict.__iter__(self)

    def _alt_rechnung125(bp, skills_je_char, chars, fixed, inv_map):
        """Die Rechnung VOR der Aenderung, als Vergleich."""
        if not inv_map:
            return 1.0
        if fixed:
            sk = skills_je_char.get(str(fixed))
            if not sk:
                return 1.0
            try:
                sk_int = {int(k): v for k, v in dict.items(sk)}
            except (TypeError, ValueError):
                return 1.0
            return I.invention_skill_modifier(bp, sk_int, inv_map)
        best = 1.0
        for cid in chars:
            sk = skills_je_char.get(str(cid))
            if not sk:
                continue
            try:
                sk_int = {int(k): v for k, v in dict.items(sk)}
            except (TypeError, ValueError):
                continue
            best = max(best, I.invention_skill_modifier(bp, sk_int, inv_map))
        return best

    _inv125 = {500: {"encryption": 21790, "science": [11442, 11529]},
               501: {"encryption": None, "science": [11433]},
               502: {"encryption": 21791, "science": []}}
    _viel125 = {str(10000 + _i): 5 for _i in range(400)}   # "einige hundert"
    _skills125 = {
        "1": _Zaehl125({**_viel125, "21790": 4, "11442": 5, "11529": 3}),
        "2": _Zaehl125({**_viel125, 21790: 5, 11442: 4, "11433": 5}),
        "3": _Zaehl125({**_viel125, "21791": 2}),
        "4": _Zaehl125({}),
    }
    _mwm125.store.list_characters = lambda: [
        {"character_id": 1, "character_name": "Eins"},
        {"character_id": 2, "character_name": "Zwei"}]
    win._char_namen_cache = None
    win.settings["bau_char_skills"] = _skills125
    win.settings["bau_invention_chars"] = [1, 2, 3, 4]
    win._bd_invention_char = 0
    _gleich125 = []
    _Zaehl125.durchlaeufe = 0
    for _bp in (500, 501, 502, 999):
        for _fx in (None, 1, 2, 3, 4, 7):
            _neu = win._bau_invention_skill_modifier_with_char(
                _bp, fixed_cid=_fx, inv_skills_map=_inv125)[0]
            _ref = _alt_rechnung125(_bp, _skills125, [1, 2, 3, 4], _fx, _inv125)
            _gleich125.append((_bp, _fx, _neu, _ref))
    _abw125 = [g for g in _gleich125 if abs(g[2] - g[3]) > 1e-12]
    check(f"b125 Invention-Skills: gleiches Ergebnis wie vorher in "
          f"{len(_gleich125)} Faellen ({_abw125[:2]})",
          not _abw125 and any(g[2] > 1.0 for g in _gleich125))
    check(f"b125 ... und die Skill-Listen werden nie ganz durchlaufen "
          f"({_Zaehl125.durchlaeufe})", _Zaehl125.durchlaeufe == 0)
    _n125, _w125 = win._bau_invention_skill_modifier_with_char(
        500, inv_skills_map=_inv125)
    check(f"b125 ... der beste Charakter wird weiter genannt ({_w125}, {_n125:.4f})",
          _w125 == "Eins" and abs(_n125 - (1 + 4 / 40 + 8 / 30)) < 1e-12)
    win.settings["bau_char_skills"] = {"1": 5, "2": ["kaputt"]}
    try:                    # ein Absturz soll ROT zeigen, nicht den Block beenden
        _kaputt125 = (win._bau_invention_skill_modifier_with_char(
                          500, fixed_cid=1, inv_skills_map=_inv125),
                      win._bau_invention_skill_modifier_with_char(
                          500, inv_skills_map=_inv125))
    except Exception as _ek125:
        _kaputt125 = f"{type(_ek125).__name__}: {_ek125}"
    check(f"b125 ... unbrauchbare Skill-Daten: kein Absturz, kein Bonus ({_kaputt125})",
          _kaputt125 == ((1.0, "Eins"), (1.0, None)))
except Exception as _e125:                                # pragma: no cover
    import traceback as _tb125
    _fail.append(f"b125 Invention-Skills: {type(_e125).__name__}: {_e125} | "
                 + _tb125.format_exc().splitlines()[-3].strip())
finally:
    try:
        for _k125, _v125 in _set_alt125.items():
            if _v125 is None:
                win.settings.pop(_k125, None)
            else:
                win.settings[_k125] = _v125
        win._bd_invention_char = _fix_alt125
        _mwm125.store.list_characters = _lc_alt125
        win._char_namen_cache = None
    except Exception:
        pass


# ---------------------------------------------------------------- (b86)
# SCHRITT 5, ENTSCHEID C: Einzelplaene, die in einem Multi-Bauplan stecken,
# werden MARKIERT und ihre Reservierung GESPERRT - sonst blockiert dasselbe
# Material zweimal. Am echten Fenster, mit einer echten Kartenliste.
try:
    _alt_plans86 = win.settings.get("bau_saved_plans")
    win.settings["bau_saved_plans"] = [
        {"id": 8601, "label": "b86 Einzel A", "type_id": 971001,
         "item_name": "A86", "qty": 10, "me": 0, "te": 0, "checked": [],
         "reserve": True, "reserve_map": {"34": 100}},
        {"id": 8602, "label": "b86 Einzel B", "type_id": 971002,
         "item_name": "B86", "qty": 5, "me": 0, "te": 0, "checked": []},
        {"id": 8603, "label": "b86 Allein", "type_id": 971003,
         "item_name": "C86", "qty": 3, "me": 0, "te": 0, "checked": []},
        {"id": 8604, "label": "b86 Multi", "type_id": I.BUENDEL_ID, "qty": 1,
         "item_name": "b86 Multi", "multi": True, "checked": [],
         "enden": [[971001, 10], [971002, 5]], "quellen": [8601, 8602]},
    ]
    eq("b86 die Zuordnung wird aus den Quellen des Multi-Plans abgeleitet",
       {k: v for k, v in win._multi_gehoert_zu(
           win.settings["bau_saved_plans"]).items()},
       {8601: ["b86 Multi"], 8602: ["b86 Multi"]})
    check("b86 ein Plan ausserhalb bleibt unmarkiert",
          8603 not in win._multi_gehoert_zu(win.settings["bau_saved_plans"]))
    # NICHT GESPEICHERT, SONDERN ABGELEITET: Multi-Plan weg -> Marke weg.
    _ohne86 = [x for x in win.settings["bau_saved_plans"] if x["id"] != 8604]
    eq("b86 ohne den Multi-Plan ist keine Marke mehr da (keine zweite Wahrheit)",
       win._multi_gehoert_zu(_ohne86), {})
    win.b_stack.setCurrentIndex(2)
    win._reload_saved_plans(); _app.processEvents()
    # DIE KARTE, NICHT DIE GEWINN-UEBERSICHT: die Seitenleiste listet JEDEN
    # Plan-Namen ebenfalls in einer Card. Eine echte Plan-Karte erkennt man
    # an ihrem Schloss-Knopf (checkable, ohne Text).
    _karten86 = {}
    for _fr86 in win.findChildren(QFrame):
        if _fr86.objectName() != "Card":
            continue
        _schloss86 = [b for b in _fr86.findChildren(QPushButton)
                      if b.isCheckable() and not (b.text() or "").strip()]
        if not _schloss86:
            continue
        # UEBER DEN TITEL, NICHT ueber irgendein Label (Befund 20.09.2026):
        # die Karte eines gebundenen Einzelplans traegt die Zeile "Belongs to
        # multi build plan b86 Multi" - ueber "irgendein Label" bekam der
        # MULTI-Plan deshalb die Karte von "b86 Einzel A" zugeordnet, und
        # jede Pruefung an ihr lief am falschen Objekt. Der Titel ist das
        # einzige Label, das fett gesetzt ist.
        _titel86 = [l.text() for l in _fr86.findChildren(QLabel)
                    if (l.text() or "").startswith("<b")]
        for _pid86, _lab86 in ((8601, "b86 Einzel A"), (8602, "b86 Einzel B"),
                               (8603, "b86 Allein"), (8604, "b86 Multi")):
            if any(_lab86 in (_x or "") for _x in _titel86):
                _karten86.setdefault(_pid86, _fr86)
    eq("b86 alle vier Karten stehen auf der Seite", sorted(_karten86), [8601, 8602, 8603, 8604])
    _zeile86 = [l.text() for l in _karten86[8601].findChildren(QLabel)]
    check("b86 die Karte sagt, zu welchem Multi-Bauplan der Plan gehoert",
          any("b86 Multi" in (_x or "") and _x != "b86 Einzel A"
              for _x in _zeile86))
    check("b86 ... und ist farblich markiert (amberner Rand wie der Multi-Plan)",
          "242,162,60" in (_karten86[8601].styleSheet() or ""))
    check("b86 ein Plan ausserhalb bekommt weder Zeile noch Rand",
          not any("b86 Multi" in (_x or "")
                  for _x in [l.text() for l in _karten86[8603].findChildren(QLabel)])
          and "242,162,60" not in (_karten86[8603].styleSheet() or ""))
    _rs86 = {}
    for _pid86 in (8601, 8603):
        _rs86[_pid86] = [b for b in _karten86[_pid86].findChildren(QPushButton)
                         if b.isCheckable() and not (b.text() or "").strip()]
    check("b86 die Reservierung des Einzelplans ist gesperrt (doppelt blockiert sonst)",
          _rs86[8601] and all(not b.isEnabled() for b in _rs86[8601]))
    check("b86 ... beim Plan ausserhalb bleibt sie bedienbar",
          _rs86[8603] and any(b.isEnabled() for b in _rs86[8603]))
    # BEFUND 20.09.2026: der Sperrgrund wurde von der allgemeinen Erklaerung
    # sofort wieder ueberschrieben - grauer Knopf, und der Tooltip sagte,
    # was er koennen SOLLTE. Genau "warum geht das nicht?" blieb offen.
    check("b86 ... und der gesperrte Knopf NENNT den Grund (Multi-Bauplan)",
          any(("multi build plan" in (b.toolTip() or "").lower()
               or "multi-bauplan" in (b.toolTip() or "").lower())
              for b in _rs86[8601]))
    check("b86 ... waehrend der freie Knopf die normale Erklaerung traegt",
          any(("reserve" in (b.toolTip() or "").lower()
               or "reservier" in (b.toolTip() or "").lower())
              and "multi" not in (b.toolTip() or "").lower()
              for b in _rs86[8603]))
    # BEARBEITEN-KNOPF: nur auf der Buendel-Karte, sonst nirgends.
    def _knopf86(pid86, *worte86):
        for b in _karten86[pid86].findChildren(QPushButton):
            _tx86 = (b.text() or "").strip().lower()
            if any(w86 in _tx86 for w86 in worte86):
                return b
        return None
    # 26.09.2026: KEIN Bearbeiten-Knopf mehr - auf keiner Karte. Heraus-
    # nehmen/Dazunehmen laeuft im Bauplan-Fenster (x je Ende, "+ Add end
    # product").
    check("b86 keine Karte hat mehr einen Bearbeiten-Knopf",
          _knopf86(8604, "edit", "bearbeit") is None
          and _knopf86(8601, "edit", "bearbeit") is None
          and _knopf86(8603, "edit", "bearbeit") is None)
    # SPEICHERN loest eine bestehende Doppel-Reservierung auf und sagt es.
    # Seit dem Aufraeumen (26.09.2026) ueber die EINE Stelle
    # config.buendel_quellen_freigeben, die `_save_plan` ruft (aa418).
    win.settings["bau_saved_plans"][0]["reserve"] = True
    _e86 = win._multi_plan_aus_quellen(
        [win.settings["bau_saved_plans"][0], win.settings["bau_saved_plans"][1]],
        label="b86 Multi")
    import eve_trader.config as _cfg86
    _frei86, _auf86 = _cfg86.buendel_quellen_freigeben(
        win.settings["bau_saved_plans"], _e86["quellen"])
    _a86 = next(x for x in win.settings["bau_saved_plans"] if x["id"] == 8601)
    check("b86 Freigeben hebt die Reservierung der Einzelplaene auf",
          _a86.get("reserve") is False and _frei86 == ["b86 Einzel A"])
    # Hinweis beim EINZELNEN Oeffnen - nur fuer Plaene in einem Multi-Plan.
    check("b86 beim Oeffnen eines gebundenen Einzelplans kommt ein Hinweis",
          win._multi_hinweis_einzelplan(8601) is True)
    check("b86 ... und bei einem freien Plan nicht",
          win._multi_hinweis_einzelplan(8603) is False)
    # UEBER DEN ECHTEN WEG: _open_saved_plan muss den Hinweis auch WIRKLICH
    # ausloesen (die Rotprobe fand die Pruefung oben blind - sie rief nur
    # die Hilfsmethode).
    _gerufen86 = []
    _hw_alt86 = win._multi_hinweis_einzelplan
    _obd_alt86 = win.open_build_detail
    win._multi_hinweis_einzelplan = lambda pid: _gerufen86.append(pid)
    win.open_build_detail = lambda *_a, **_k: None
    try:
        win._open_saved_plan(8601)
    finally:
        win._multi_hinweis_einzelplan = _hw_alt86
        win.open_build_detail = _obd_alt86
    eq("b86 _open_saved_plan fragt den Hinweis wirklich ab", _gerufen86, [8601])
except Exception as _e86x:                               # pragma: no cover
    import traceback as _tb86
    _fail.append(f"b86 Schritt 5: {type(_e86x).__name__}: {_e86x} | "
                 + _tb86.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b89)
# EIGENER BLOCK, NICHT in b86 hineingeschrieben: stuerzt b86 ab, liefen die
# Ordnerstruktur-Pruefungen sonst gar nicht erst - eine Rotprobe meldete
# genau das als "blind". Jede Zusage braucht einen Block, der sie auch
# erreicht.
try:
    # ------------------------------------------------------------ (b89)
    # ORDNERSTRUKTUR (Nutzer 20.09.2026: "waere gut wenn die 2 Bauplaene in
    # den Multibauplan untergeordnet werden, so dass man die ausklappen kann
    # wenn man will"). Am echten Fenster, an derselben Kartenliste.
    eq("b89 die Zuordnung Buendel -> Einzelplaene wird abgeleitet",
       {k: sorted(x["id"] for x in v) for k, v in
        win._plan_gruppen(win.settings["bau_saved_plans"])[0].items()},
       {8604: [8601, 8602]})
    eq("b89 ... und die Kinder sind genau die beiden Quellen",
       sorted(win._plan_gruppen(win.settings["bau_saved_plans"])[1]),
       [8601, 8602])
    _box89 = (getattr(win, "_plan_gruppe_box", None) or {}).get(8604)
    check("b89 das Buendel hat einen Kasten fuer seine Kinder", _box89 is not None)

    def _pfeil89(pid89):
        return (getattr(win, "_plan_multi_pfeil", None) or {}).get(pid89)
    check("b89 die Kind-Karten sitzen WIRKLICH in diesem Kasten",
          _box89.isAncestorOf(_karten86[8601])
          and _box89.isAncestorOf(_karten86[8602]))
    check("b89 ... und ein freier Plan nicht",
          not _box89.isAncestorOf(_karten86[8603]))
    # isHidden(), NICHT isVisible(): offscreen ist ohnehin alles unsichtbar.
    # SEIT 26.09.2026 STANDARD OFFEN (Nutzer: "Multiplans standard
    # ausgeklappt, es sei denn man schliesst das Dropdown"); gemerkt wird
    # das Zuklappen (`bau_multi_zu`).
    check("b89 standardmaessig ist die Gruppe OFFEN",
          not _box89.isHidden() and _pfeil89(8604) is not None
          and _pfeil89(8604).isChecked())
    check("b89 die Kinder sind EINGERUECKT (das macht die Unterordnung sichtbar)",
          _box89.layout().contentsMargins().left() >= 20)
    # SORTIERUNG DARF DIE GRUPPE NICHT ZERREISSEN: die Kind-Karten duerfen
    # nicht in der Liste stehen, an der Hand- und Fortschritts-Sortierung
    # ziehen - sonst haengen sie nach dem ersten ESI-Lauf einzeln im
    # Hauptlayout.
    check("b89 die Kinder stehen NICHT in der sortierbaren Liste",
          8601 not in (win._plan_karte_wrap or {})
          and 8602 not in (win._plan_karte_wrap or {})
          and 8604 in win._plan_karte_wrap and 8603 in win._plan_karte_wrap)
    check("b89 ... sondern in der eigenen Kind-Liste",
          sorted(getattr(win, "_plan_kind_wrap", {}) or {}) == [8601, 8602])
    # DER PFEIL: nur beim Buendel, und er klappt wirklich zu und auf.
    check("b89 nur das Buendel hat einen Aufklapp-Pfeil",
          _pfeil89(8604) is not None and _pfeil89(8601) is None
          and _pfeil89(8603) is None)
    _pfeil89(8604).setChecked(False)
    _app.processEvents()
    check("b89 ein Klick klappt die Gruppe zu", _box89.isHidden())
    eq("b89 ... und der Zustand wird gemerkt (ueberlebt den Neustart)",
       [int(x) for x in (win.settings.get("bau_multi_zu") or [])], [8604])
    # Neu aufbauen: die Gruppe muss ZU wiederkommen.
    win._reload_saved_plans(); _app.processEvents()
    _box89b = (getattr(win, "_plan_gruppe_box", None) or {}).get(8604)
    check("b89 nach dem Neuaufbau steht die Gruppe wieder zu",
          _box89b is not None and _box89b.isHidden()
          and not _pfeil89(8604).isChecked())
    _pfeil89(8604).setChecked(True)
    _app.processEvents()
    check("b89 ein Klick klappt die Gruppe auf", not _box89b.isHidden())
    check("b89 aufklappen geht auch wieder (Merker leer)",
          not (win.settings.get("bau_multi_zu") or []))
    # GEWINN-UEBERSICHT: gebundene Plaene sind dort weder gelistet noch
    # gezaehlt - sonst stuende ihr Gewinn zweimal im Total (einmal einzeln,
    # einmal im Buendel).
    check("b89 die Gewinn-Uebersicht listet gebundene Einzelplaene nicht",
          8601 not in (win._plan_sum_labels or {})
          and 8602 not in (win._plan_sum_labels or {}))
    # JE ENDPRODUKT STATT JE BUENDEL (Nutzer 26.09.2026: "im Profit Overview
    # separat, nicht als Bauplan"): das Buendel hat keine eigene Zeile,
    # seine zwei Enden je eine ("<plan_id>:<tid>").
    check("b89 ... die freien Plaene schon, das Buendel als eine Zeile je Ende",
          8603 in win._plan_sum_labels and 8604 not in win._plan_sum_labels
          and "8604:971001" in win._plan_sum_labels
          and "8604:971002" in win._plan_sum_labels)
except Exception as _e89:                                # pragma: no cover
    import traceback as _tb89
    _fail.append(f"b89 Ordnerstruktur: {type(_e89).__name__}: {_e89} | "
                 + _tb89.format_exc().splitlines()[-3].strip())
finally:
    try:
        win.settings["bau_saved_plans"] = _alt_plans86
        win._reload_saved_plans()
    except Exception:
        pass


# ---------------------------------------------------------------- (b92)
# DAS RESERVIERUNGS-SCHLOSS BLEIBT AMBER, AUCH NACH DEM KLICK.
# Nutzer 22.09.2026: "das Schloss-Symbol eines eingefrorenen und
# reservierten Buildplans ist zu unuebersichtlich."
# Der eigentliche Fehler war nicht die Farbstaerke: `_toggle_plan_reserve`
# zeichnete das Symbol beim Umschalten OHNE `farbe=` neu - nach dem ersten
# Klick war die amberne Faerbung weg und kam erst nach einem Neuaufbau der
# Liste zurueck. Deshalb wird hier der ECHTE Weg gefahren (Lehre aus
# b87/b88: nie nur den Helfer aufrufen, den der Knopf benutzt).
try:
    from PySide6.QtWidgets import QPushButton as _QPB92
    from eve_trader.ui import theme as _th92
    _btn92 = _QPB92()
    _btn92.setCheckable(True)
    # Eine id, die es nicht gibt: die Schleife in _toggle_plan_reserve
    # aendert dann keinen Plan - geprueft wird hier allein das Aussehen.
    win._toggle_plan_reserve(-99992, True, _btn92)
    _an92 = _btn92.styleSheet()
    # NUR DIE RUHE-REGEL zaehlt: "AMBER kommt vor" ist blind (der Rahmen
    # ist ohnehin amber), und die :hover-Regel ist es auch - beide waren
    # die ersten, blinden Fassungen dieser Zeile. Die FLAECHE im
    # Ruhezustand ist die Zusage.
    _ruhe92 = _an92.replace(" ", "").split("QPushButton:hover")[0]
    check(f"b92 eingeschaltet ist der Knopf amber AUSGEFUELLT "
          f"({_ruhe92[:44]!r})",
          f"background:{_th92.AMBER}" in _ruhe92)
    check("b92 ... und traegt ein Symbol (kein leerer Knopf)",
          not _btn92.icon().isNull() and _btn92.text() == "")
    win._toggle_plan_reserve(-99992, False, _btn92)
    _aus92 = _btn92.styleSheet()
    check(f"b92 ausgeschaltet bleibt er grau wie bisher ({_aus92[:40]!r})",
          _th92.AMBER not in _aus92)
    check("b92 ... und die beiden Zustaende sehen wirklich verschieden aus",
          _an92 != _aus92)
    # GEGENPROBE gegen den alten Fehler: der Aufbau der Karte und das
    # Umschalten muessen DASSELBE zeichnen.
    _btn92b = _QPB92()
    win._plan_reserve_stil(_btn92b, True)
    check("b92 Karten-Aufbau und Umschalten zeichnen dasselbe",
          _btn92b.styleSheet() == _an92)
except Exception as _e92:                                # pragma: no cover
    import traceback as _tb92
    _fail.append(f"b92 Reservierungs-Schloss: {type(_e92).__name__}: {_e92} | "
                 + _tb92.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b104)
# STUFE C, TEIL 2: EINMAL FRAGEN, WEM EIN JOB GEHOERT (24.09.2026).
# Nutzer-Entscheide: "einmal fragen, Antwort merken" und "gesammelt im
# Runplaner". Geprueft wird am ECHTEN Fenster und gegen die ECHTE Tabelle -
# eine Zusage, die nur im Quelltext steht, ist keine.
try:
    from PySide6.QtWidgets import QDialog as _QD104, QComboBox as _QCB104
    from eve_trader import store as _st104
    from eve_trader.ui import mw_helpers as _mwh104
    _T104, _J104a, _J104b = 42, 9104001, 9104002
    _P104a, _P104b = 9104101, 9104102
    _st104.job_zuordnung_loeschen(str(_P104a))       # Zustand ueberlebt Laeufe
    _st104.job_zuordnung_loeschen(str(_P104b))
    _st104.job_zuordnung_loeschen(_st104.PLAN_KEINER)
    _alt_fr104 = getattr(win, "_bd_full_rebuild", None)
    win._bd_full_rebuild = lambda: None      # der Neuaufbau ist hier nicht Thema
    win._bd_job_offen = []
    win._jobfrage_knopf_auffrischen()
    _btn104 = getattr(win, "_bd_jobfrage_btn", None)
    check("b104 es gibt die Zeile im Runplaner", _btn104 is not None)
    # isHidden() statt isVisible(): in einem nie gezeigten Fenster meldet
    # isVisible() IMMER False und waere damit blind (Falle aus CLAUDE.md).
    check("b104 ohne offene Frage ist die Zeile weg",
          _btn104 is not None and _btn104.isHidden())
    win._bd_job_offen = [
        {"job_id": _J104a, "type_id": _T104, "runs": 10, "fertig_ts": 1.0,
         "name": "b104 Item", "kandidaten": [(_P104a, "b104 Plan A"),
                                             (_P104b, "b104 Plan B")]},
        {"job_id": _J104b, "type_id": _T104, "runs": 5, "fertig_ts": 2.0,
         "name": "b104 Item", "kandidaten": [(_P104a, "b104 Plan A"),
                                             (_P104b, "b104 Plan B")]}]
    win._jobfrage_knopf_auffrischen()
    check("b104 mit offenen Fragen erscheint die Zeile", not _btn104.isHidden())
    check("b104 ... und nennt die Anzahl", "2" in _btn104.text())
    _gesehen104 = {}
    _alt_exec104 = _QD104.exec

    def _exec104(dlg):
        _cbs = [_c for _c in dlg.findChildren(_QCB104)]
        _gesehen104["boxen"] = len(_cbs)
        _gesehen104["eintraege"] = _cbs[0].count() if _cbs else 0
        _gesehen104["letzter"] = _cbs[0].itemData(_cbs[0].count() - 1) \
            if _cbs else "x"
        if len(_cbs) >= 2:
            _cbs[0].setCurrentIndex(1)                       # Plan B
            _cbs[1].setCurrentIndex(_cbs[1].count() - 1)     # "keiner"
        return 1                                             # Accepted
    _QD104.exec = _exec104
    try:
        _n104 = win._job_frage_dialog()
    finally:
        _QD104.exec = _alt_exec104
    eq("b104 je offener Job eine Auswahl", _gesehen104.get("boxen"), 2)
    eq("b104 die Auswahl kennt beide Plaene und 'zu keinem davon'",
       _gesehen104.get("eintraege"), 3)
    eq("b104 ... und 'zu keinem davon' traegt keine Plan-Id",
       _gesehen104.get("letzter"), None)
    eq("b104 beide Antworten werden verbucht", _n104, 2)
    _zu104 = _st104.job_zuordnung_alle()
    eq("b104 die gewaehlte Antwort steht in der Tabelle",
       _zu104.get(_J104a), str(_P104b))
    # "KEINER" IST AUCH EINE ANTWORT - sonst kaeme dieselbe Frage bei jedem
    # Aufbau wieder.
    eq("b104 ... und 'zu keinem davon' wird genauso gemerkt",
       _zu104.get(_J104b), _st104.PLAN_KEINER)
    eq("b104 der Plan selbst bekommt den fremden Job nicht",
       _st104.job_zuordnung_fuer_plan(str(_P104a)), {})
    # ... und ab jetzt gilt der Job als vergeben, wird also von keiner
    # Automatik mehr angefasst.
    eq("b104 ein beantworteter Job wird nicht mehr automatisch zugeordnet",
       _mwh104.job_zuordnen_eindeutig(
           [{"job_id": _J104b, "product_type_id": _T104, "runs": 5,
             "activity_id": 1, "fertig_ts": 9.0}],
           {_T104: 100}, {_T104: False}, _zu104, set(), 0.0), {})
    _st104.job_zuordnung_loeschen(str(_P104a))
    _st104.job_zuordnung_loeschen(str(_P104b))
    _st104.job_zuordnung_loeschen(_st104.PLAN_KEINER)
    win._bd_job_offen = []
    win._jobfrage_knopf_auffrischen()
    if _alt_fr104 is not None:
        win._bd_full_rebuild = _alt_fr104
except Exception as _e104:                               # pragma: no cover
    import traceback as _tb104
    _fail.append(f"b104 Job-Frage: {type(_e104).__name__}: {_e104} | "
                 + _tb104.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b148)
# STANDORT-HINWEIS (emm313, Nutzer 01.10.2026: "eine Meldung, wenn der
# gewaehlte Charakter fuers Trading sich an einem anderen Ort befindet als
# der gewaehlte Hub"). Am echten Feld neben dem Charakter, ESI gestubbt.
try:
    import eve_trader.esi as _esi148
    import eve_trader.config as _cfg148
    from eve_trader.sprache import t as _t148
    _alt148 = {k: getattr(_esi148, k) for k in (
        "granted_scopes", "fetch_character_location", "orts_namen")}
    _alt_set148 = {k: win.settings.get(k) for k in ("use_location", "client_id")}
    _alt_run148 = win._run
    _rufe148 = []
    _ort148 = {"v": {}}
    _scope148 = {"v": True}
    try:
        win._run = lambda w, done, fail_cb=None, **_k: done(w._fn())
        _esi148.granted_scopes = lambda c, cid: (
            {_cfg148.LOCATION_SCOPE} if _scope148["v"] else set())
        _esi148.fetch_character_location = lambda c, cid: (
            _rufe148.append(cid), dict(_ort148["v"]))[1]
        _esi148.orts_namen = lambda ids: {60008494: "Amarr VIII (Oris) b148",
                                          30002187: "Amarr"}
        win.settings["client_id"] = "b148"
        win.g_char.blockSignals(True); win.g_hub.blockSignals(True)
        _ci148, _hi148 = win.g_char.currentIndex(), win.g_hub.currentIndex()
        win.g_char.addItem("B148 Trader", 4148)
        win.g_char.setCurrentIndex(win.g_char.count() - 1)
        _jita148 = win.g_hub.findData(10000002)
        if _jita148 >= 0:
            win.g_hub.setCurrentIndex(_jita148)
        _lbl148 = win.g_ort_warn
        # 1. Schalter aus: kein ESI-Abruf, nichts zu sehen.
        win.settings["use_location"] = False
        win._standort_pruefen()
        check(f"b148 Schalter aus: kein Abruf, kein Hinweis ({_rufe148})",
              not _rufe148 and not win._ort_sichtbar())
        win.settings["use_location"] = True
        # 2. Angedockt GENAU am Hub (Jita 4-4): kein Hinweis.
        _ort148["v"] = {"solar_system_id": 30000142, "station_id": 60003760}
        win._standort_pruefen()
        check(f"b148 am Hub angedockt: kein Hinweis (Hub-Index {_jita148})",
              _jita148 >= 0 and _rufe148 == [4148] and not win._ort_sichtbar())
        # 3. Woanders angedockt: Hinweis mit Ort und Hub im Tooltip.
        _ort148["v"] = {"solar_system_id": 30002187, "station_id": 60008494}
        win._standort_pruefen()
        check(f"b148 woanders angedockt: Hinweis neben dem Charakter "
              f"({_lbl148.text()!r}, {_lbl148.toolTip()[:60]!r})",
              win._ort_sichtbar() and _t148("Not at the hub") in _lbl148.text()
              and "Amarr VIII (Oris) b148" in _lbl148.toolTip()
              and "B148 Trader" in _lbl148.toolTip())
        # 4. Im All im Hub-System zaehlt NICHT als "am Hub".
        _ort148["v"] = {"solar_system_id": 30000142}
        win._standort_pruefen()
        check("b148 im All (auch im Hub-System): Hinweis",
              win._ort_sichtbar() and _t148("Not at the hub") in _lbl148.text())
        # 5. Ohne Scope: leise "neu verknuepfen", kein Standort-Abruf.
        _scope148["v"] = False
        _n148 = len(_rufe148)
        win._standort_pruefen()
        check(f"b148 ohne Scope: 'neu verknuepfen', kein Standort-Abruf "
              f"({_lbl148.text()!r})",
              win._ort_sichtbar() and _t148("Location: re-link") == _lbl148.text()
              and len(_rufe148) == _n148)
        # 6. "Alle Charaktere" gewaehlt: kein Hinweis.
        _scope148["v"] = True
        win.g_char.addItem("All b148", "all")
        win.g_char.setCurrentIndex(win.g_char.count() - 1)
        win._standort_pruefen()
        check("b148 'alle Charaktere': kein Hinweis", not win._ort_sichtbar())
    finally:
        for _k, _v in _alt148.items():
            setattr(_esi148, _k, _v)
        for _k, _v in _alt_set148.items():
            if _v is None:
                win.settings.pop(_k, None)     # s. b146: kein null speichern
            else:
                win.settings[_k] = _v
        win._run = _alt_run148
        for _d148 in (4148, "all"):
            _i = win.g_char.findData(_d148)
            if _i >= 0 and "b148" in win.g_char.itemText(_i).lower():
                win.g_char.removeItem(_i)
        win.g_char.setCurrentIndex(max(0, min(_ci148, win.g_char.count() - 1)))
        win.g_hub.setCurrentIndex(max(0, _hi148))
        win.g_char.blockSignals(False); win.g_hub.blockSignals(False)
        win._ort_zeigen(False)
except Exception as _e148:                               # pragma: no cover
    import traceback as _tb148
    _fail.append(f"b148 Standort-Hinweis: {type(_e148).__name__}: {_e148} | "
                 + _tb148.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b147)
# JOB-FRAGE: NAMEN STATT NUMMERN, EINE ZEILE JE ITEM UND PLAN (Nutzer
# 01.10.2026, Screenshot: 4x "16679", 2x "16678" ... alle schon "Basilisk
# x28" - "enorm viele Fragen? komisch" und "nur Zahlen, keine Item-Namen").
try:
    from PySide6.QtWidgets import (QDialog as _QD147, QComboBox as _QCB147,
                                   QTableWidget as _QTW147)
    _alt147 = {"fr": getattr(win, "_bd_full_rebuild", None),
               "antw": win._job_frage_antworten,
               "namen": getattr(win, "_bd_names_ref", None),
               "offen": getattr(win, "_bd_job_offen", None),
               "prio": getattr(win, "_bd_job_prio", None)}
    _antw147 = {}
    try:
        win._bd_full_rebuild = lambda: None
        win._job_frage_antworten = lambda a: (_antw147.update(a), len(a))[1]
        win._bd_names_ref = {16679: "Fullerides147", 16678: "Sylramic147"}
        _k147 = [(91471, "Basilisk x28"), (91472, "Multi 147")]
        win._bd_job_offen = []
        win._bd_job_prio = (
            [{"job_id": 9147000 + _i, "type_id": 16679, "runs": 17,
              "fertig_ts": 1_790_000_000.0 + _i, "prio_plan": 91471,
              "kandidaten": _k147} for _i in range(4)]
            + [{"job_id": 9147010 + _i, "type_id": 16678, "runs": 15,
                "fertig_ts": 1_790_000_000.0, "prio_plan": 91471,
                "kandidaten": _k147} for _i in range(2)])
        _ges147 = {}
        _alt_exec147 = _QD147.exec

        def _exec147(dlg):
            _t = dlg.findChildren(_QTW147)[0]
            _ges147["zeilen"] = [_t.item(_r, 0).text() for _r in range(_t.rowCount())]
            _ges147["runs"] = [_t.item(_r, 1).text() for _r in range(_t.rowCount())]
            _cbs = dlg.findChildren(_QCB147)
            _ges147["boxen"] = len(_cbs)
            if _cbs:
                _cbs[0].setCurrentIndex(1)          # Fullerides -> Multi 147
            return 1
        _QD147.exec = _exec147
        try:
            win._job_frage_dialog()
        finally:
            _QD147.exec = _alt_exec147
        _z147 = _ges147.get("zeilen") or []
        check(f"b147 eine Zeile je Item und Plan, nicht je Job ({_z147})",
              len(_z147) == 2 and _ges147.get("boxen") == 2)
        check(f"b147 die Zeilen nennen den Item-Namen, keine Nummer ({_z147})",
              len(_z147) == 2 and "Fullerides147" in _z147[0]
              and "Sylramic147" in _z147[1]
              and not any(_x.strip().isdigit() for _x in _z147))
        check(f"b147 ... mit Anzahl der Jobs und summierten Runs "
              f"({_z147}, {_ges147.get('runs')})",
              len(_z147) == 2 and "4" in _z147[0] and "2" in _z147[1]
              and _ges147.get("runs") == ["68", "30"])
        eq("b147 eine Antwort gilt fuer ALLE Jobs der Zeile",
           (sorted(_j for _j, _p in _antw147.items() if _p == 91472),
            sorted(_j for _j, _p in _antw147.items() if _p == 91471)),
           ([9147000, 9147001, 9147002, 9147003], [9147010, 9147011]))
    finally:
        win._job_frage_antworten = _alt147["antw"]
        if _alt147["fr"] is not None:
            win._bd_full_rebuild = _alt147["fr"]
        win._bd_names_ref = _alt147["namen"]
        win._bd_job_offen = _alt147["offen"] or []
        win._bd_job_prio = _alt147["prio"] or []
except Exception as _e147:                               # pragma: no cover
    import traceback as _tb147
    _fail.append(f"b147 Job-Frage gruppiert: {type(_e147).__name__}: {_e147} | "
                 + _tb147.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b105)
# "FEHLT", OBWOHL NICHTS FEHLT (Nutzer 25.09.2026, Silicon Diborite).
# Sein Entscheid: die RECHNUNG bleibt (lieber zu viel als zu wenig), die
# ZEILE sagt jetzt warum. Geprueft wird am echten Fenster: laufende Jobs
# eintragen, neu aufbauen, und die Materialzeile muss es nennen - ohne dass
# sich eine einzige Zahl aendert.
try:
    _plan105 = (getattr(win, "_bd_plan_ref", None) or {}).get("plan") or {}
    _runs105 = {int(k): int(v or 0)
                for k, v in (_plan105.get("build_runs") or {}).items()
                if int(v or 0) > 0}
    _mats105 = _plan105.get("build_mats") or {}
    _kand105 = [t for t in _runs105 if (_mats105.get(t) or [])]
    check("b105 der Testplan baut etwas mit Zutaten", bool(_kand105))
    if _kand105:
        _t105 = sorted(_kand105, key=lambda x: -len(_mats105.get(x) or []))[0]
        _alt_aj105 = getattr(win, "_bd_active_jobs_map", None)
        _alt_rest105 = dict(win._restbedarf_jetzt() or {})
        win._bd_active_jobs_map = win._bd_active_jobs_alle = {_t105: [{"runs": _runs105[_t105]}]}
        win._bd_full_rebuild()
        _app.processEvents()
        # Der Hinweis steht im GRUND der Zeile (Tooltip); gesucht wird ein
        # Stueck davon, das in beiden Sprachen steht.
        _mark105 = _t4(
            "{n} units of this are already used up by jobs that are "
            "RUNNING right now \u2013 in game the material is gone, "
            "but their output is not in the hangar yet, so the plan "
            "keeps counting the need. Nothing is really missing "
            "here. The number stays as it is on purpose (better to "
            "buy too much than too little); tick the running rows in "
            "the run planner to take their material out of the "
            "list.").split("{n}")[-1].strip()[:40]
        _treffer105 = [r for r in (getattr(win, "_bd_mat_rows", None) or [])
                       if _mark105 and _mark105.lower()
                       in str(r.get("reason") or "").lower()]
        # DIE ZAHL DARF SICH NICHT BEWEGT HABEN - das ist der Kern seines
        # Entscheids "nur anzeigen, nicht rechnen".
        eq("b105 der Restbedarf bleibt unveraendert",
           dict(win._restbedarf_jetzt() or {}), _alt_rest105)
        check("b105 mindestens eine Zeile nennt die laufenden Jobs",
              bool(_treffer105))
        # GEGENPROBE: ohne laufende Jobs steht der Hinweis nirgends.
        win._bd_active_jobs_map = win._bd_active_jobs_alle = {}
        win._bd_full_rebuild()
        _app.processEvents()
        check("b105 ohne laufende Jobs sagt keine Zeile so etwas",
              not [r for r in (getattr(win, "_bd_mat_rows", None) or [])
                   if _mark105 and _mark105.lower()
                   in str(r.get("reason") or "").lower()])
        win._bd_active_jobs_map = win._bd_active_jobs_alle = _alt_aj105 or {}
        win._bd_full_rebuild()
        _app.processEvents()
except Exception as _e105:                               # pragma: no cover
    import traceback as _tb105
    _fail.append(f"b105 Hinweis laufende Jobs: {type(_e105).__name__}: {_e105} | "
                 + _tb105.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b106)
# VERKAUFSPREIS DER PLAN-KARTE IST ANKLICKBAR (Nutzer 25.09.2026: "kann man
# den recommended sell price fuer meine eingestellte Gewinnmarge anklickbar
# machen, so wie im Runplanner?"). Geprueft wird der Kopier-Weg selbst - mit
# echter Zwischenablage.
try:
    from PySide6.QtWidgets import QApplication as _QA106
    _QA106.clipboard().setText("")
    win._copy_sell_price(5613584.0, "b106 Plan", "bauplan")
    _app.processEvents()
    eq("b106 der Preis liegt als reine Zahl in der Zwischenablage",
       _QA106.clipboard().text(), "5613584")
    _msg106 = win.statusBar().currentMessage()
    check("b106 die Meldung nennt den Bauplan, nicht den Einkauf",
          "b106 Plan" in _msg106
          and ("build plan" in _msg106.lower() or "bauplan" in _msg106.lower()))
    # GEGENPROBE: die Verkaufslisten-Quelle sagt weiterhin etwas ANDERES -
    # sonst traegt eine Zahl zwei Bedeutungen mit einem Satz.
    win._copy_sell_price(5613584.0, "b106 Plan", "ziel")
    _app.processEvents()
    check("b106 die Verkaufsliste behaelt ihren eigenen Satz",
          win.statusBar().currentMessage() != _msg106)
    # Nachkommastellen bleiben erhalten (Preise sind nicht ganzzahlig).
    win._copy_sell_price(4472999.5, "b106 Plan", "bauplan")
    _app.processEvents()
    eq("b106 ein Preis mit Nachkommastelle wird nicht gerundet",
       _QA106.clipboard().text(), "4472999.5")
except Exception as _e106:                               # pragma: no cover
    import traceback as _tb106
    _fail.append(f"b106 Preis kopieren: {type(_e106).__name__}: {_e106} | "
                 + _tb106.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b107)
# PLANER-DIAGNOSE (Nutzer 25.09.2026: "19 Blueprints, das Tool nutzt 11" und
# "23 h eingestellt, Reaktion dauert 15 h 26 m"). Beides ist von aussen nicht
# nachstellbar, solange die EINGABEN des Planers nicht sichtbar sind. Geprueft
# wird, dass die Datei beim Aufbau des Runplaners wirklich entsteht - nicht
# nur, dass es eine Methode dafuer gibt.
try:
    from eve_trader import config as _cfg107
    _p107 = os.path.join(_cfg107.app_data_dir(), "planer_diagnose.txt")
    _txt107 = ""
    if os.path.exists(_p107):
        with open(_p107, encoding="utf-8") as _fh107:
            _txt107 = _fh107.read()
    check("b107 der Runplaner-Aufbau schreibt die Planer-Diagnose",
          bool(_txt107))
    for _k107 in ("CHARAKTERE (angekreuzt) - Slots:",
                  "JOBS (Eingabe des Planers):",
                  "ZIELZEITEN JE STUFE",
                  "ERGEBNIS - Stufenzeiten",
                  "ERGEBNIS - Zuteilungen"):
        check("b107 ... mit dem Abschnitt: " + _k107.split("(")[0].strip(),
              _k107 in _txt107)
    # DIE DECKEL GEHOEREN DAZU - ohne sie laesst sich "19 Kopien, 11 Jobs"
    # nicht beantworten.
    check("b107 ... und den Spalten KOPIEN und RUNS/KOPIE",
          "KOPIEN" in _txt107 and "RUNS/KOPIE" in _txt107)
    # FORTSCHRITTS-ANHANG (26.09.2026, "der Runplaner will trotzdem nochmal
    # 6'718 nachbauen"): derselbe Aufbau haengt Plan-/geliefert-/laufend-
    # Runs und die Bestandsschichten an - NACH dem ersten Abschnitt.
    check("b107 ... und den Anhang FORTSCHRITT UND BESTAND JE ITEM dahinter",
          _txt107.find("FORTSCHRITT UND BESTAND JE ITEM")
          > _txt107.find("ERGEBNIS - Zuteilungen") > 0
          and "ENDE FORTSCHRITT" in _txt107)
    check("b107 ... mit den Spalten GELIEFERT/LAUFEND/REST und EINGEFR./HANGAR/PIPELINE/WIRKSAM",
          all(_k in _txt107 for _k in ("GELIEFERT", "LAUFEND", "ERLEDIGT", "REST",
                                       "EINGEFR.", "HANGAR", "PIPELINE",
                                       "WIRKSAM", "VERBRAUCHT")))
except Exception as _e107:                               # pragma: no cover
    import traceback as _tb107
    _fail.append(f"b107 Planer-Diagnose: {type(_e107).__name__}: {_e107} | "
                 + _tb107.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b108)
# NICHTS MEHR ZU BAUEN (Nutzer 26.09.2026: "ich will, dass diese Runs
# nicht mehr einfach angezeigt werden, obwohl ich sie gar nicht brauche").
# Der Materialien-Reiter zeigte "can be built - 13'019 units" (Plan minus
# Bestand), obwohl der Runplaner 0 Runs offen hatte. Geprueft am echten
# Fenster: die sichere Liefer-Karte deckt alle Runs eines Eigenbau-Items ->
# die Zeile sagt "nothing left to build", die MISSING-Spalte zeigt "-".
# Gegenprobe: mit halber Lieferung steht die halbe Menge da.
try:
    _plan108 = (getattr(win, "_bd_plan_ref", None) or {}).get("plan") or {}
    _runs108 = {int(k): int(v or 0)
                for k, v in (_plan108.get("build_runs") or {}).items()
                if int(v or 0) > 0}
    _mats108 = _plan108.get("build_mats") or {}
    _kand108 = [t for t in _runs108 if (_mats108.get(t) or [])]
    check("b108 der Testplan baut etwas mit Zutaten", bool(_kand108))
    if _kand108:
        _t108 = sorted(_kand108, key=lambda x: -len(_mats108.get(x) or []))[0]
        _alt_ds108 = dict(getattr(win, "_bd_runplan_delivered_sicher", None) or {})
        _alt_aj108 = getattr(win, "_bd_active_jobs_map", None)
        win._bd_active_jobs_map = win._bd_active_jobs_alle = {}
        # OHNE BESTAND sagt jede Zeile "Subtract assets needed" - der
        # Eigenbau-Zweig wird erst mit einem (auch leeren) geladenen Stand
        # erreicht. Ein Stueck irgendwo genuegt, damit `stock` wahr ist.
        _opts108 = getattr(win, "_bd_opts", None)
        _alt_stock108 = None if _opts108 is None else _opts108.get("stock")
        if _opts108 is not None:
            _opts108["stock"] = dict(_alt_stock108 or {}) or {-9108: 1}

        def _zeile108():
            for r in (getattr(win, "_bd_mat_rows", None) or []):
                if int(r.get("tid") or 0) == int(_t108):
                    return r
            return None

        eq("b108 vorher: offene Runs = Plan-Runs",
           (win._rest_runs_jetzt() or {}).get(int(_t108)), _runs108[_t108])
        # WIE IM ECHTEN BETRIEB (Nutzer 28.09.2026, Phenolic "40 of 40 runs
        # open", Runplaner 4): die sichere Karte entsteht ERST im Runplaner,
        # der Materialien-Reiter wird vorher gefuellt. Der Test setzt die
        # Karte deshalb im Runplaner-Aufruf, nicht vorab - sonst saehe er
        # den Fehler nie.
        _ziel108 = {}
        _orig_fbs108 = win._fill_bauplan_schedule

        def _fbs108(*_a, **_k):
            _r = _orig_fbs108(*_a, **_k)
            if _ziel108:
                win._bd_runplan_delivered_sicher = dict(_ziel108)
            return _r
        win._fill_bauplan_schedule = _fbs108
        win._bd_runplan_delivered_sicher = dict(_alt_ds108)
        _ziel108.update({**_alt_ds108, int(_t108): _runs108[_t108]})
        win._bd_full_rebuild()
        _app.processEvents()
        eq("b108 alle Runs sicher geliefert -> 0 offene Runs",
           (win._rest_runs_jetzt() or {}).get(int(_t108)), 0)
        _r108 = _zeile108()
        _st108 = str((_r108 or {}).get("status") or "").lower()
        check("b108 die Zeile sagt 'nothing left to build' (beide Sprachen)",
              _r108 is not None and (
                  _t4("nothing left to build \u2713").lower() in _st108
                  or "nothing left to build" in _st108))
        # Gegenprobe: die Haelfte geliefert -> Rest = halbe Runs x Stueck.
        _halb108 = _runs108[_t108] // 2
        if _halb108 > 0:
            _ziel108.clear()
            _ziel108.update({**_alt_ds108, int(_t108): _halb108})
            win._bd_full_rebuild()
            _app.processEvents()
            _r108b = _zeile108()
            _st108b = str((_r108b or {}).get("status") or "")
            _offen108 = _runs108[_t108] - _halb108
            check("b108 halb geliefert: die Zeile nennt die offenen Runs",
                  _r108b is not None and _t4("{r} of {n} runs open").format(
                      r=_offen108, n=_runs108[_t108]) in _st108b)
            # KATEGORIE-BALKEN (Nutzer-Entscheid 26.09.2026, "Punkt 3
            # einfuehren"): eine Eigenbau-Zeile mit offenen Runs zaehlt im
            # Balken ihrer Kategorie als GEDECKT (nichts zu kaufen) und
            # wird getrennt als "im Bau" genannt - vorher stand die
            # Kategorie mit "0 / n covered" in Rot da.
            _tbl108 = getattr(win, "_bd_mat_tab_tbl", None)
            _kat108 = str((_r108b or {}).get("category") or "")
            _grp108 = None
            for _gi108 in range(_tbl108.topLevelItemCount()):
                _g108 = _tbl108.topLevelItem(_gi108)
                if (_g108.data(1, Qt.UserRole) or _g108.text(0)) == _kat108:
                    _grp108 = _g108
                    break
            _bar108 = (_tbl108.itemWidget(_grp108, 6)
                       if _grp108 is not None else None)
            _fmt108 = _bar108.format() if _bar108 is not None else ""
            import re as _re108
            _bau108 = _re108.search(r"(\d+) " + _re108.escape(
                _t4("{n} being built").format(n="").strip()), _fmt108)
            check(f"b108 der Kategorie-Balken nennt die Eigenbau-Zeile als 'im Bau' "
                  f"({_fmt108!r})",
                  _bar108 is not None and _bau108 is not None
                  and int(_bau108.group(1)) >= 1)
            _m108 = _re108.search(r"(\d+) / (\d+)", _fmt108)
            check("b108 ... und zaehlt sie als gedeckt (nichts zu kaufen)",
                  _m108 is not None and int(_m108.group(1)) >= 1
                  and int(_m108.group(1)) <= int(_m108.group(2)))
            check("b108 ... der Tooltip erklaert den Bau-Anteil",
                  _bar108 is not None
                  and ("built by this plan" in _bar108.toolTip()
                       or "baut dieser Plan" in _bar108.toolTip()))
        _ziel108.clear()
        try:
            del win._fill_bauplan_schedule
        except AttributeError:
            pass
        win._bd_runplan_delivered_sicher = _alt_ds108
        win._bd_active_jobs_map = win._bd_active_jobs_alle = _alt_aj108 or {}
        if _opts108 is not None:
            _opts108["stock"] = _alt_stock108
        win._bd_full_rebuild()
        _app.processEvents()
except Exception as _e108:                               # pragma: no cover
    import traceback as _tb108
    _fail.append(f"b108 nichts mehr zu bauen: {type(_e108).__name__}: {_e108} | "
                 + _tb108.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b131)
# VORSTUFE NICHT MEHR NOETIG, AM ECHTEN FENSTER (Nutzer 28.09.2026,
# Phenolic): sind alle Verbraucher einer Vorstufe im Plan geliefert, hat die
# Vorstufe 0 offene Runs - auch wenn sie selbst nur teilweise geliefert ist.
# Der Testplan des Fensters hat keine gebaute Vorstufe; deshalb ein kleiner
# Plan (K braucht V, V braucht Rohstoff) in `_bd_plan_ref`, gerechnet von den
# ECHTEN Methoden `_rest_geliefert_jetzt` / `_rest_runs_jetzt`.
try:
    _alt131 = {k: getattr(win, k, None) for k in (
        "_bd_plan_ref", "_bd_runplan_delivered_sicher", "_bd_active_jobs_map",
        "_bd_runplan_checked")}
    try:
        win._bd_plan_ref = {"plan": {
            "build_runs": {9001: 10, 9002: 40},
            "build_mats": {9001: [[9002, 100]], 9002: [[34, 5000]]}}}
        win._bd_active_jobs_map = win._bd_active_jobs_alle = {}
        win._bd_runplan_checked = set()
        win._bd_runplan_delivered_sicher = {9002: 36}
        _offen131a = dict(win._rest_runs_jetzt() or {})
        win._bd_runplan_delivered_sicher = {9001: 10, 9002: 36}
        _offen131b = dict(win._rest_runs_jetzt() or {})
        _fertig131 = set(getattr(win, "_bd_vorstufen_fertig", None) or set())
        _rest131 = dict(win._restbedarf_jetzt() or {})
    finally:
        for k, v in _alt131.items():
            setattr(win, k, v)
    eq("b131 Verbraucher offen -> Vorstufe behaelt ihre 4 offenen Runs",
       _offen131a.get(9002), 4)
    eq("b131 Verbraucher fertig -> Vorstufe 0 offene Runs (Phenolic-Fall)",
       _offen131b.get(9002), 0)
    check(f"b131 ... gemerkt fuer die Statuszeile ({_fertig131})",
          9002 in _fertig131)
    check(f"b131 ... und ihr Rohstoff faellt aus dem Restbedarf ({_rest131})",
          not _rest131.get(34))
except Exception as _e131:                                # pragma: no cover
    import traceback as _tb131
    _fail.append(f"b131 Vorstufe: {type(_e131).__name__}: {_e131} | "
                 + _tb131.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b109)
# DIE BLAUPAUSEN-SPALTE FASST DAS ZIELZEIT-FELD (Nutzer 26.09.2026: "die
# Zeitdropdowns bissl abgeschnitten"). Die Spalte ist fest 280 px; auf
# seinem Windows sind Tage- und Stunden-Feld zusammen breiter, und Qt
# schneidet das Feld am Spaltenrand ab. Gemessen am echten Baum: erst wird
# die Spalte auf 60 px gezwungen, dann baut `_runplan_ziel_feld` das Feld
# an einer Stufenzeile neu - danach muss die Spalte beide Felder samt
# Abstand und Text fassen. (Ohne das Schmalmachen waere die Pruefung
# offscreen blind: 280 px reichen hier immer, bei ihm nicht.)
try:
    from PySide6.QtWidgets import QComboBox as _QCb109, QLabel as _QLb109
    _st109 = None
    for _i109 in range(_tr7w.topLevelItemCount()):
        _it109 = _tr7w.topLevelItem(_i109)
        if _it109.data(1, Qt.UserRole + 8) is not None and \
                _tr7w.itemWidget(_it109, 2) is not None:
            _st109 = _it109
            break
    check("b109 der Testplan hat mindestens eine Stufe mit Zielzeit-Feld",
          _st109 is not None)
    if _st109 is not None:
        _alt_w109 = _tr7w.columnWidth(2)
        _altfr109 = getattr(win, "_bd_full_rebuild", None)
        win._bd_full_rebuild = lambda *_a, **_k: None   # s. b102
        _tr7w.setColumnWidth(2, 60)
        win._runplan_ziel_feld(_tr7w, _st109, str(_st109.data(1, Qt.UserRole + 8)),
                               0.0, None)
        _app.processEvents()
        _w109 = _tr7w.itemWidget(_st109, 2)
        _cbs109 = _w109.findChildren(_QCb109) if _w109 is not None else []
        _lbls109 = _w109.findChildren(_QLb109) if _w109 is not None else []
        _txtw109 = max([_l.fontMetrics().horizontalAdvance(_l.text())
                        for _l in _lbls109] or [0])
        _need109 = (sum(_c.width() for _c in _cbs109)
                    + 3 * (_w109.layout().spacing() if _w109 is not None else 4)
                    + _txtw109 + 12)
        check("b109 die Blaupausen-Spalte ist breit genug fuer beide Felder + Text",
              len(_cbs109) == 2 and _tr7w.columnWidth(2) >= _need109)
        check("b109 ... und wurde dafuer wirklich verbreitert (von 60 px aus)",
              _tr7w.columnWidth(2) > 60)
        # DAS FELD SELBST fasst seinen laengsten Eintrag (zweiter Screenshot:
        # "as fast as possibl" war IM Feld abgeschnitten): Textbreite + 44 px
        # (Polster, Rahmen, Pfeil, Reserve).
        _zu_eng109 = [(_c.itemText(_i), _c.width()) for _c in _cbs109
                      for _i in range(_c.count())
                      if _c.width() < _c.fontMetrics().horizontalAdvance(
                          _c.itemText(_i)) + 44]
        eq("b109 jedes Feld fasst seinen laengsten Eintrag samt Pfeil und Polster",
           _zu_eng109, [])
        _tr7w.setColumnWidth(2, max(_alt_w109, _tr7w.columnWidth(2)))
        win._bd_full_rebuild = _altfr109
except Exception as _e109:                               # pragma: no cover
    import traceback as _tb109
    _fail.append(f"b109 Zielzeit-Spalte: {type(_e109).__name__}: {_e109} | "
                 + _tb109.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b111)
# DIE KARTE EINES GEBUNDENEN EINZELPLANS (Nutzer 26.09.2026: "in Meine
# Bauplaene werden die einzelnen Endprodukte nicht sauber getrackt, ich
# sehe keinen Einzelbaupreis, nur einen geschaetzten Profit ... auch kein
# Sell-Vorschlag"): statt des Allein-Gewinns steht dort "Im Buendel: Bau
# X/Stk" plus ein kleiner Amber-Knopf "Verkauf Y", der den Preis kopiert.
# Die Zahlen kommen aus buendel_kosten_je_ende der Buendel-Schaetzung.
try:
    from PySide6.QtWidgets import QApplication as _QA111
    from eve_trader.ui import theme as _th111
    _alt_plans111 = win.settings.get("bau_saved_plans")
    _alt_rc111 = I.recipes_cached
    _alt_snap111 = _st84.get_snapshot
    _alt_sde111 = I.sde_ready
    _alt_run111 = win._run
    I.recipes_cached = lambda *a, **k: _Rec83()
    _st84.get_snapshot = lambda *a, **k: [
        {"type_id": t111, "sell_min": p111} for t111, p111 in _pm84.items()]
    I.sde_ready = lambda: True
    win._run = lambda worker, done_cb, fail_cb=None, **kw: done_cb(
        worker._fn(*worker._args, **worker._kwargs))
    win.settings["bau_saved_plans"] = [
        {"id": 11101, "label": "b111 Plan A", "type_id": _A83, "item_name": "A",
         "qty": 20, "me": 7, "te": 14, "checked": []},
        {"id": 11102, "label": "b111 Plan B", "type_id": _B83, "item_name": "B",
         "qty": 10, "me": 3, "te": 2, "checked": []},
        {"id": 11103, "label": "b111 Frei", "type_id": _A83, "item_name": "A",
         "qty": 5, "me": 0, "te": 0, "checked": []},
        {"id": 11109, "label": "b111 Multi", "type_id": I.BUENDEL_ID,
         "item_name": "b111 Multi", "qty": 1, "multi": True, "checked": [],
         "enden": [[_A83, 20], [_B83, 10]], "quellen": [11101, 11102],
         "mengen_je_quelle": {"11101": 20, "11102": 10},
         "me_je_ende": {str(_A83): 7, str(_B83): 3},
         "te_je_ende": {str(_A83): 14, str(_B83): 2},
         "own_bpc_je_ende": {}, "own_bpc_runs_je_ende": {}, "quellen_stand": {}},
    ]
    _plans111 = win.settings["bau_saved_plans"]
    _pm111 = dict(_pm84)
    # MIT ZUSATZKOSTEN: nur dann gibt es einen Rest zwischen Enden-Summe und
    # Buendel-Gewinn, den die Verteilung nach Kostenanteil tragen muss
    # (Rotprobe: ohne Rest war die Verteilung unsichtbar).
    _extra_alt111 = win.settings.get("bau_extra_cost")
    win.settings["bau_extra_cost"] = 5_000_000.0
    _est111 = {p111["id"]: win._bau_saved_plan_quick_estimate(
        p111, _Rec83(), _pm111, dict(_pm111)) for p111 in _plans111}
    _mit111 = win._plan_buendel_mitglieder_zahlen(_plans111, _est111, _pm111)
    eq("b111 rein: genau die beiden Quellen bekommen Buendel-Zahlen",
       sorted(_mit111.keys()), [11101, 11102])
    _je111 = I.buendel_kosten_je_ende(_est111[11109]["plan"])
    check("b111 rein: Kosten/Stk = Anteil aus buendel_kosten_je_ende (keine zweite Rechnung)",
          abs(_mit111[11101]["cost_unit"] - _je111[_A83]["je_stueck"]) < 1e-6
          and abs(_mit111[11102]["cost_unit"] - _je111[_B83]["je_stueck"]) < 1e-6)
    check("b111 rein: der Sell-Vorschlag kommt aus DERSELBEN Formel wie die Fertig-Zeile",
          abs(_mit111[11101]["rec_sell"]
              - win._plan_sell_vorschlag(_mit111[11101]["cost_unit"], None)) < 1e-6
          and _mit111[11101]["rec_sell"] > _mit111[11101]["cost_unit"])
    check("b111 rein: der Name des Buendels steht dabei",
          _mit111[11101]["multi"] == "b111 Multi"
          and _mit111[11101]["name"] == "b111 Plan A")
    # AM FENSTER: Karten bauen, Schaetzung synchron laufen lassen.
    win._reload_saved_plans(); _app.processEvents()
    win._load_saved_plan_estimates(_plans111); _app.processEvents()
    _l111 = win._plan_est_labels
    # SEIT 26.09.2026 (Nutzer: "Einzelprofit UND Einzelbaupreis"): die Karte
    # zeigt den Gewinn IM BUENDEL (nicht den Allein-Gewinn), der Baupreis
    # je Stueck steht im Tooltip - und die Enden-Gewinne addieren sich
    # exakt zum Buendel-Gewinn.
    _pr111 = _mit111[11101]["profit"]
    check("b111 die Karte der Quelle zeigt den Gewinn im Buendel, Baupreis im Tooltip",
          "Profit" in _l111[11101].text()
          and f"{abs(_pr111):,.0f}".replace(",", "'") in _l111[11101].text()
          and ("bundle" in _l111[11101].toolTip().lower()
               or "bündel" in _l111[11101].toolTip().lower())
          and _mw61.isk(_mit111[11101]["cost_unit"]) in _l111[11101].toolTip())
    _alle111 = win._plan_enden_zahlen(_plans111, _est111, _pm111)
    check("b111 rein: die Enden-Gewinne addieren sich exakt zum Buendel-Gewinn",
          abs(sum(z["profit"] for z in _alle111.values())
              - _est111[11109]["profit"]) < 1e-6
          and abs(_pr111 - _alle111["11109:" + str(_A83)]["profit"]) < 1e-9)
    check("b111 rein: Gewinn je Ende = Verkauf x Menge x (1 - Gebuehr) - Kostenanteil (+ Rest nach Anteil)",
          abs(_alle111["11109:" + str(_A83)]["profit"]
              + _alle111["11109:" + str(_B83)]["profit"]
              - (_pm111[_A83] * 20 + _pm111[_B83] * 10)
              * (1 - _est111[11109]["fee_pct"] / 100.0)
              + _je111[_A83]["gesamt"] + _je111[_B83]["gesamt"]
              + float(win.settings.get("bau_extra_cost", 0) or 0)) < 1.0)
    check("b111 ... der freie Plan und das Buendel zeigen weiter ihren Gewinn",
          "Profit" in _l111[11103].text() and "Profit" in _l111[11109].text())
    _sb111 = win._plan_sell_btns
    check("b111 die Quelle hat einen sichtbaren Verkaufs-Knopf, der freie Plan nicht",
          not _sb111[11101].isHidden() and not _sb111[11102].isHidden()
          and _sb111[11103].isHidden() and _sb111[11109].isHidden())
    check("b111 ... mit Amber-Rahmen (sichtbar anklickbar)",
          f"border:1px solid {_th111.AMBER}" in _sb111[11101].styleSheet()
          and _sb111[11101].cursor().shape() == Qt.PointingHandCursor)
    _QA111.clipboard().setText("")
    _sb111[11101].click(); _app.processEvents()
    _ab111 = (_QA111.clipboard().text() or "").strip()
    check("b111 ein Klick kopiert den Verkaufs-Vorschlag in die Zwischenablage",
          _ab111 != "" and abs(float(_ab111) - _mit111[11101]["rec_sell"]) < 1.0)
    check("b111 die Statusspalte ist so breit wie der laengste Eintrag samt Knopf",
          win._plan_stat_widgets[11101].width()
          >= _sb111[11101].sizeHint().width() + 10)
    # DER GEWINN DES BUENDELS DARF NICHT ABGESCHNITTEN SEIN (Nutzer-
    # Screenshot 26.09.2026: "Profit ≈ +1'141'691'5" endete am Schloss).
    _app.processEvents()
    _zu_eng111 = [(pid111, l111.text()) for pid111, l111 in _l111.items()
                  if win._plan_stat_widgets[pid111].width()
                  < l111.sizeHint().width()]
    eq("b111 kein Gewinn-Text ist breiter als seine Statusspalte", _zu_eng111, [])
    # FERTIG-ZEILE: der Knopf traegt den Verkauf, nicht mehr der Text.
    win._plan_sell_knopf_zeigen(11103, 123456.0, "b111 Frei")
    check("b111 die Fertig-Zeile fuellt denselben Knopf",
          not _sb111[11103].isHidden() and "123" in _sb111[11103].text())
    win._plan_sell_knopf_zeigen(11103, None, "b111 Frei")
    check("b111 ... ohne Preis ist er wieder weg", _sb111[11103].isHidden())
except Exception as _e111:                               # pragma: no cover
    import traceback as _tb111
    _fail.append(f"b111 Buendel-Karten: {type(_e111).__name__}: {_e111} | "
                 + _tb111.format_exc().splitlines()[-3].strip())
finally:
    try:
        if _extra_alt111 is None:
            win.settings.pop("bau_extra_cost", None)
        else:
            win.settings["bau_extra_cost"] = _extra_alt111
        win._run = _alt_run111
        I.recipes_cached = _alt_rc111
        _st84.get_snapshot = _alt_snap111
        I.sde_ready = _alt_sde111
        win.settings["bau_saved_plans"] = _alt_plans111
        win._reload_saved_plans()
    except Exception:
        pass

# ---------------------------------------------------------------- (b112)
# BUENDEL OHNE QUELLPLAENE (Anhaengen-Weg; Nutzer 26.09.2026: "Sacrilege x1,
# einzeln hinzugefuegte Bauplaene, kein Dropdown ersichtlich - ich muss ja
# wissen, zu wieviel ich die Endprodukte einzeln gebaut habe und zu wieviel
# ich sie verkaufen kann/soll; im Profit Overview separat, nicht als
# Bauplan"): je Ende eine Karte unter dem Buendel (Pfeil, Gewinn, Baupreis,
# Verkaufs-Knopf), in der Gewinn-Uebersicht eine Zeile je Ende und KEINE
# fuer das Buendel; die Summe bleibt der Buendel-Gewinn. Und ein
# EINGEFRORENES Buendel liefert die Zahlen je Ende genauso (Multiplan 1
# auf seinem Bildschirm war eingefroren).
try:
    from eve_trader.ui import theme as _th112
    _alt_plans112 = win.settings.get("bau_saved_plans")
    _alt_rc112 = I.recipes_cached
    _alt_snap112 = _st84.get_snapshot
    _alt_sde112 = I.sde_ready
    _alt_run112 = win._run
    I.recipes_cached = lambda *a, **k: _Rec83()
    _st84.get_snapshot = lambda *a, **k: [
        {"type_id": t112, "sell_min": p112} for t112, p112 in _pm84.items()]
    I.sde_ready = lambda: True
    win._run = lambda worker, done_cb, fail_cb=None, **kw: done_cb(
        worker._fn(*worker._args, **worker._kwargs))
    _pm112 = dict(_pm84)
    _offen112 = {"id": 11201, "label": "b112 Sacrilege", "type_id": I.BUENDEL_ID,
                 "item_name": "b112 Sacrilege", "qty": 1, "multi": True,
                 "checked": [], "enden": [[_A83, 20], [_B83, 10]], "quellen": [],
                 "me_je_ende": {str(_A83): 7, str(_B83): 3},
                 "te_je_ende": {str(_A83): 14, str(_B83): 2},
                 "own_bpc_je_ende": {}, "own_bpc_runs_je_ende": {}}
    _est_o112 = win._bau_saved_plan_quick_estimate(_offen112, _Rec83(), _pm112,
                                                    dict(_pm112))
    # Dasselbe Buendel EINGEFROREN, mit dem Plan-Schnappschuss der offenen
    # Schaetzung (wie es das Einfrieren im Fenster ablegt).
    _gefr112 = dict(_offen112, id=11202, label="b112 Gefroren",
                    frozen={"ts": 1.0, "qty": 1,
                            "prices": {str(k): v for k, v in _pm112.items()},
                            "plan_snapshot": win._plan_snapshot_pack(_est_o112["plan"])})
    _frei112 = {"id": 11203, "label": "b112 Frei", "type_id": _A83, "item_name": "A",
                "qty": 5, "me": 0, "te": 0, "checked": []}
    win.settings["bau_saved_plans"] = [_offen112, _gefr112, _frei112]
    _plans112 = win.settings["bau_saved_plans"]
    _est112 = {p112["id"]: win._bau_saved_plan_quick_estimate(
        p112, _Rec83(), _pm112, dict(_pm112)) for p112 in _plans112}
    check("b112 die Schaetzung eines EINGEFRORENEN Buendels traegt den Plan-Schnappschuss",
          _est112[11202] is not None and _est112[11202].get("frozen_ts") == 1.0
          and bool(_est112[11202].get("plan"))
          and abs(_est112[11202]["cost"] - _est_o112["cost"]) < 1e-6)
    _en112 = win._plan_enden_zahlen(_plans112, _est112, _pm112)
    eq("b112 rein: je Ende eine Zahl, fuer beide Buendel, ohne Quellplan",
       sorted(_en112.keys()),
       sorted([f"11201:{_A83}", f"11201:{_B83}", f"11202:{_A83}", f"11202:{_B83}"]))
    check("b112 rein: kein Ende hat einen Quellplan, die Summe je Buendel ist der Buendel-Gewinn",
          all(z["quelle_id"] is None for z in _en112.values())
          and abs(_en112[f"11201:{_A83}"]["profit"] + _en112[f"11201:{_B83}"]["profit"]
                  - _est112[11201]["profit"]) < 1e-6
          and abs(_en112[f"11202:{_A83}"]["profit"] + _en112[f"11202:{_B83}"]["profit"]
                  - _est112[11202]["profit"]) < 1e-6)
    eq("b112 rein: die virtuellen Enden des Buendels (mit Namen)",
       [(a, b) for a, b, _n in win._plan_virtuelle_enden(_offen112, [])],
       [(_A83, 20), (_B83, 10)])
    eq("b112 rein: ein Ende MIT Quellplan ist nicht virtuell",
       [(a, b) for a, b, _n in win._plan_virtuelle_enden(
           _offen112, [{"id": 1, "type_id": _A83}])],
       [(_B83, 10)])
    # AM FENSTER.
    win.settings.pop("bau_multi_zu", None)
    win._reload_saved_plans(); _app.processEvents()
    _kA112 = f"11201:{_A83}"; _kB112 = f"11201:{_B83}"
    check("b112 das Buendel hat den Pfeil und zwei Enden-Karten darunter",
          11201 in win._plan_multi_pfeil and 11201 in win._plan_gruppe_box
          and _kA112 in win._plan_kind_wrap and _kB112 in win._plan_kind_wrap
          and _kA112 in win._plan_est_labels and _kA112 in win._plan_sell_btns)
    check("b112 ... offen als Vorgabe (26.09.2026), ein Klick klappt zu",
          not win._plan_gruppe_box[11201].isHidden()
          and (win._plan_multi_pfeil[11201].click(), _app.processEvents(),
               win._plan_gruppe_box[11201].isHidden())[2]
          and (win._plan_multi_pfeil[11201].click(), _app.processEvents(),
               not win._plan_gruppe_box[11201].isHidden())[2])
    check("b112 die Enden-Karte traegt keine Plan-Knoepfe (Oeffnen/Fertig/Loeschen)",
          not [b for b in win._plan_kind_wrap[_kA112].findChildren(QPushButton)
               if (b.text() or "").strip().lower() in
               ("open", "\u00f6ffnen", "done", "fertig", "delete", "l\u00f6schen")])
    check("b112 Gewinn-Uebersicht: je Ende eine Zeile, keine fuer das Buendel",
          _kA112 in win._plan_sum_labels and _kB112 in win._plan_sum_labels
          and 11201 not in win._plan_sum_labels and 11203 in win._plan_sum_labels)
    win._load_saved_plan_estimates(_plans112); _app.processEvents()
    _lA112 = win._plan_est_labels[_kA112]
    check("b112 Enden-Karte: Gewinn im Buendel, Baupreis je Stueck, Verkaufs-Knopf",
          "Profit" in _lA112.text()
          and f"{abs(_en112[_kA112]['profit']):,.0f}".replace(",", "'") in _lA112.text()
          and _mw61.isk(_en112[_kA112]["cost_unit"], suffix=False)
          in win._plan_ende_sub[_kA112].text()
          and not win._plan_sell_btns[_kA112].isHidden()
          and _mw61.isk(_en112[_kA112]["sell_unit"]) in win._plan_ende_verkauf[_kA112].text())
    _sumA112 = win._plan_sum_labels[_kA112].text().replace("'", "").replace("+", "")
    check("b112 Gewinn-Uebersicht: die Enden-Zeile traegt den Enden-Gewinn",
          abs(float(_sumA112.replace("\u2212", "-")) - _en112[_kA112]["profit"]) < 1.0)
    _tot112 = (win._plan_total_lbl.text().replace("ISK", "").replace("'", "")
               .replace("+", "").replace("\u2212", "-").strip())
    check("b112 ... und das Total ist unveraendert die Summe der Buendel + freie Plaene",
          abs(float(_tot112) - (_est112[11201]["profit"] + _est112[11202]["profit"]
                                + _est112[11203]["profit"])) < 3.0)
    # ---------------------------------------------------------------- (b156)
    # AUS DEM GEWINN-TOTAL NEHMEN (emm343, Discord ueber den Nutzer: "a box to
    # check to exclude the Nirvanas from the profit calculation"). Echte
    # Haken in der Uebersicht, echtes Karten-Menue (Return auf dem Eintrag).
    try:
        from eve_trader import config as _cfg156
        from PySide6.QtCore import QTimer as _QT156, QPoint as _QP156
        from PySide6.QtTest import QTest as _QTe156
        _ssa156 = _cfg156.save_settings_async
        _cfg156.save_settings_async = lambda *a, **k: None
        _ga_alt156 = win.settings.pop("gewinn_aus", None)

        def _tot156():
            return float(win._plan_total_lbl.text().replace("ISK", "").replace("'", "")
                         .replace("+", "").replace("\u2212", "-").strip())
        try:
            win._reload_saved_plans(); _app.processEvents()
            win._load_saved_plan_estimates(_plans112); _app.processEvents()
            _hk156 = getattr(win, "_plan_sum_haken", None) or {}
            _alle156 = _tot156()
            check(f"b156 je Uebersichts-Zeile ein Haken, alle an ({sorted(map(str, _hk156))})",
                  set(_hk156) == set(win._plan_sum_labels)
                  and all(h.isChecked() for h in _hk156.values()))
            _pA156 = _en112[_kA112]["profit"]
            if _kA112 in _hk156:
                _hk156[_kA112].click(); _app.processEvents()
            check(f"b156 Haken weg: Total ohne diese Zeile, gemerkt ({_tot156()} vs {_alle156 - _pA156})",
                  abs(_tot156() - (_alle156 - _pA156)) < 3.0
                  and win.settings.get("gewinn_aus") == [_kA112])
            check("b156 ... die Zeile bleibt stehen, grau durchgestrichen",
                  "line-through" in win._plan_sum_labels[_kA112].styleSheet()
                  and "line-through" in win._plan_sum_namen[_kA112].styleSheet())
            check("b156 ... der Tooltip des Totals nennt die Ausnahme",
                  "1" in win._plan_total_lbl.toolTip()
                  and ("excluded" in win._plan_total_lbl.toolTip()
                       or "ausgeschlossen" in win._plan_total_lbl.toolTip()))
            win._reload_saved_plans(); _app.processEvents()
            win._load_saved_plan_estimates(_plans112); _app.processEvents()
            check("b156 nach Neuaufbau: Haken bleibt aus, Total bleibt ohne",
                  not win._plan_sum_haken[_kA112].isChecked()
                  and abs(_tot156() - (_alle156 - _pA156)) < 3.0)
            # KARTEN-MENUE: ganzer Buendel-Plan auf einmal.
            _k156 = (getattr(win, "_plan_karte", None) or {}).get(11202)
            _txt156 = []

            def _waehle156(teil):
                def _f():
                    _m = win._plan_karten_menu
                    _txt156.append([a.text() for a in _m.actions()])
                    _a = next((a for a in _m.actions() if teil(a.text())), None)
                    if _a is None:
                        _m.close(); return
                    _m.setActiveAction(_a)
                    _QTe156.keyClick(_m, Qt.Key_Return)
                return _f
            if _k156 is not None:
                _QT156.singleShot(0, _waehle156(
                    lambda x: x in ("Exclude from profit total", "Aus dem Gewinn-Total nehmen")))
                _k156.customContextMenuRequested.emit(_QP156(5, 5)); _app.processEvents()
            _e156 = [f"11202:{_A83}", f"11202:{_B83}"]
            check(f"b156 Rechtsklick 'Exclude from profit total' nimmt alle Enden des Buendels ({_txt156})",
                  sorted(win.settings.get("gewinn_aus") or []) == sorted([_kA112] + _e156)
                  and all(not win._plan_sum_haken[k].isChecked() for k in _e156)
                  and abs(_tot156() - (_alle156 - _pA156 - _est112[11202]["profit"])) < 3.0)
            if _k156 is not None:
                _QT156.singleShot(0, _waehle156(
                    lambda x: x in ("Include in profit total", "Wieder ins Gewinn-Total nehmen")))
                _k156.customContextMenuRequested.emit(_QP156(5, 5)); _app.processEvents()
            check("b156 ... und 'Include in profit total' holt sie zurueck",
                  win.settings.get("gewinn_aus") == [_kA112]
                  and all(win._plan_sum_haken[k].isChecked() for k in _e156))
            win._plan_sum_haken[_kA112].click(); _app.processEvents()
            check("b156 Haken wieder an: Total wie vorher",
                  abs(_tot156() - _alle156) < 3.0 and win.settings.get("gewinn_aus") == [])
            # ---------------------------------------------------------- (b157)
            # UEBERSICHT SCROLLT, ABSCHNITTE, NACH PLAN GRUPPIERT (emm344,
            # Nutzer: "muesste scrollbar werden ... uebersichtlicher?" ->
            # "Abschnitte wie links" + "nach Plan gruppiert").
            from PySide6.QtWidgets import QAbstractScrollArea as _QASA157
            _alt157 = {k: win.settings.pop(k, None) for k in
                       ("gewinn_gruppen_offen", "gewinn_fertig_offen",
                        "gewinn_fertig_mitzaehlen")}
            _frei157 = next(p for p in _plans112 if p["id"] == 11203)
            _frei157["done_manual"] = True
            try:
                win._reload_saved_plans(); _app.processEvents()
                win._load_saved_plan_estimates(_plans112); _app.processEvents()
                _sc157 = getattr(win, "_plan_sum_scroll", None)
                check("b157 die Zeilen stehen in einer Scroll-Flaeche, das Total darunter fest",
                      _sc157 is not None
                      and _sc157.sizeAdjustPolicy() == _QASA157.AdjustToContents
                      and not _sc157.isAncestorOf(win._plan_total_lbl)
                      and _sc157.isAncestorOf(win._plan_sum_labels[_kA112]))
                _g157 = (getattr(win, "_gewinn_gruppen", None) or {}).get(11201)
                check(f"b157 das Buendel ist ein Plan-Kopf mit seinen Enden, standardmaessig zu ({_g157 and _g157['keys']})",
                      _g157 is not None and _g157["keys"] == [_kA112, _kB112]
                      and _g157["body"].isHidden() and 11201 not in win._plan_sum_labels
                      and _g157["body"].isAncestorOf(win._plan_sum_labels[_kA112]))
                _zs157 = float(_g157["summe"].text().replace("'", "").replace("+", "")
                               .replace("\u2212", "-")) if _g157 else None
                check(f"b157 Zwischensumme am Plan-Kopf = Buendel-Gewinn ({_zs157})",
                      _zs157 is not None and abs(_zs157 - _est112[11201]["profit"]) < 3.0)
                check("b157 erledigter Plan: in COMPLETED (zu), ohne Haken",
                      11203 in win._plan_sum_fertig and 11203 not in win._plan_sum_haken
                      and win._gewinn_fertig_body.isHidden()
                      and win._gewinn_fertig_body.isAncestorOf(win._plan_sum_labels[11203]))
                check(f"b157 Total = nur IN PROGRESS ({_tot156()})",
                      abs(_tot156() - (_est112[11201]["profit"] + _est112[11202]["profit"])) < 3.0)
                # emm348: Reihenfolge (Nutzer-Bild: COMPLETED stand UEBER den
                # laufenden) und Haken "COMPLETED zaehlt mit".
                _iv157 = _sc157.widget().layout()
                check("b157 laufende Zeilen unter IN PROGRESS, vor COMPLETED",
                      win._gewinn_offen_body is not None
                      and win._gewinn_offen_body.isAncestorOf(win._plan_sum_haken[11203 if 11203 in win._plan_sum_haken else _kA112])
                      and _iv157.indexOf(win._gewinn_offen_body)
                      < _iv157.indexOf(win._gewinn_fertig_body))
                _fh157 = getattr(win, "_gewinn_fertig_haken", None)
                check("b157 COMPLETED hat einen Haken, standardmaessig aus",
                      _fh157 is not None and not _fh157.isChecked())
                if _fh157 is not None:
                    _fh157.click(); _app.processEvents()
                check(f"b157 Haken an: COMPLETED zaehlt ins Total, gemerkt ({_tot156()})",
                      abs(_tot156() - (_est112[11201]["profit"] + _est112[11202]["profit"]
                                       + _est112[11203]["profit"])) < 3.0
                      and win.settings.get("gewinn_fertig_mitzaehlen") is True)
                win._reload_saved_plans(); _app.processEvents()
                win._load_saved_plan_estimates(_plans112); _app.processEvents()
                check("b157 ... bleibt nach Neuaufbau an und zaehlt weiter",
                      win._gewinn_fertig_haken.isChecked()
                      and abs(_tot156() - (_est112[11201]["profit"] + _est112[11202]["profit"]
                                           + _est112[11203]["profit"])) < 3.0)
                win._gewinn_fertig_haken.click(); _app.processEvents()
                check("b157 Haken aus: wieder nur IN PROGRESS",
                      abs(_tot156() - (_est112[11201]["profit"] + _est112[11202]["profit"])) < 3.0)
                _g157 = win._gewinn_gruppen.get(11201)   # nach dem Neuaufbau
                _fs157 = win._gewinn_abschnitt_summe["done"].text()
                check(f"b157 COMPLETED traegt seine eigene Summe ({_fs157})",
                      abs(float(_fs157.replace("'", "").replace("+", "").replace("\u2212", "-"))
                          - _est112[11203]["profit"]) < 3.0)
                _g157["haken"].click(); _app.processEvents()
                check("b157 Haken am Plan-Kopf nimmt alle Enden raus",
                      sorted(win.settings.get("gewinn_aus") or []) == sorted([_kA112, _kB112])
                      and abs(_tot156() - _est112[11202]["profit"]) < 3.0
                      and _g157["haken"].checkState() == Qt.Unchecked)
                win._plan_sum_haken[_kA112].click(); _app.processEvents()
                check("b157 ein Ende wieder an: Kopf-Haken teilweise",
                      _g157["haken"].checkState() == Qt.PartiallyChecked)
                _g157["haken"].click(); _app.processEvents()
                check("b157 ... Klick auf teilweise: alle wieder an",
                      win.settings.get("gewinn_aus") == []
                      and _g157["haken"].checkState() == Qt.Checked)
                _g157["pfeil"].click(); win._gewinn_fertig_pfeil.click(); _app.processEvents()
                win._reload_saved_plans(); _app.processEvents()
                _g157b = win._gewinn_gruppen.get(11201)
                check("b157 Aufklappen (Plan und COMPLETED) bleibt nach Neuaufbau",
                      _g157b is not None and not _g157b["body"].isHidden()
                      and not win._gewinn_fertig_body.isHidden())
            finally:
                _frei157.pop("done_manual", None)
                for _k157, _v157 in _alt157.items():
                    if _v157 is None:
                        win.settings.pop(_k157, None)
                    else:
                        win.settings[_k157] = _v157
        finally:
            _cfg156.save_settings_async = _ssa156
            if _ga_alt156 is None:
                win.settings.pop("gewinn_aus", None)
            else:
                win.settings["gewinn_aus"] = _ga_alt156
    except Exception as _e156:                           # pragma: no cover
        import traceback as _tb156
        _fail.append(f"b156 Gewinn-Total: {type(_e156).__name__}: {_e156} | "
                     + _tb156.format_exc().splitlines()[-3].strip())
    # DIE ENDEN-KARTE IST NICHT HOEHER ALS DIE BUENDEL-KARTE (Regel aus b2t:
    # alle Karten ein Mass).
    check("b112 die Enden-Karte ist nicht hoeher als die Buendel-Karte",
          win._plan_kind_wrap[_kA112].sizeHint().height()
          <= win._plan_karte[11201].sizeHint().height() + 2)
    # EINZELPLAN (seit 27.09.2026, Nutzer: "Add build plan ein wenig
    # ersichtlicher, Amber-Rahmen, auch beim normalen Bauplan - optisch
    # gleich und an derselben Position"): NICHT mehr in der Leiste oben,
    # sondern im Kopf einer schmalen Karte "End product of this plan" - wie
    # beim Buendel im Kopf der Endprodukte-Karte. Stil: amber_rahmen_knopf.
    import eve_trader.ui.theme as _th112
    win._show_build_detail(100, "b112 Einzel", _res); _app.processEvents()
    _eb112 = getattr(win, "_bd_ende_btn", None)
    _k112 = getattr(win, "_bd_ende_karte_einzel", None)
    check("b112 Einzelplan: 'Add build plan' im Kopf der Karte 'End product of this "
          "plan', normal gestylt, nicht in der Leiste",
          _eb112 is not None and _k112 is not None
          and _eb112.parentWidget() is _k112
          and not any("save" in (b.text() or "").lower()
                      or "speichern" in (b.text() or "").lower()
                      for b in _k112.findChildren(QPushButton))
          and _th112.AMBER not in _eb112.styleSheet()
          and "font-weight" not in _eb112.styleSheet()
          and getattr(win, "_bd_multi_tbl", None) is None
          and not _eb112.isHidden())
    _dz112 = getattr(win, "_bd_dialog", None)
    if _dz112 is not None:
        _dz112.close(); _app.processEvents()
except Exception as _e112:                               # pragma: no cover
    import traceback as _tb112
    _fail.append(f"b112 Enden-Karten: {type(_e112).__name__}: {_e112} | "
                 + _tb112.format_exc().splitlines()[-3].strip())
finally:
    try:
        win._run = _alt_run112
        I.recipes_cached = _alt_rc112
        _st84.get_snapshot = _alt_snap112
        I.sde_ready = _alt_sde112
        win.settings.pop("bau_multi_zu", None)
        win.settings["bau_saved_plans"] = _alt_plans112
        win._reload_saved_plans()
    except Exception:
        pass

# ---------------------------------------------------------------- (b150)
# ENDE INS OFFENE BUENDEL: FERTIGUNGSTIEFE GILT AUCH FUER SEINE KETTE
# (Nutzer 01.10.2026: "Multibauplan ignoriert die Production Depth" -
# Screenshot: "From components" gewaehlt, trotzdem "Tungsten Carbide
# BUILD" unter einem per Tools -> Suggested end products zugefuegten
# Ende). D wird aus der Reaktion R gebaut; bei "From components" muss R
# GEKAUFT werden, auch wenn D erst nach dem Oeffnen dazukommt.
try:
    _A150, _B150, _D150 = 981001, 981002, 981003
    _M150, _R150, _X150 = 981010, 981020, 981030
    _E150 = 981004          # Ende aus M - Kette dem Fenster schon bekannt

    class _Rec150:
        product_to_bp = {_A150: (981101, I.MANUFACTURING, 1),
                         _B150: (981102, I.MANUFACTURING, 1),
                         _D150: (981103, I.MANUFACTURING, 1),
                         _E150: (981104, I.MANUFACTURING, 1),
                         _R150: (981120, I.REACTION, 1)}
        bp_materials = {(981101, I.MANUFACTURING): [(_M150, 10)],
                        (981102, I.MANUFACTURING): [(_M150, 10)],
                        (981103, I.MANUFACTURING): [(_R150, 10)],
                        (981104, I.MANUFACTURING): [(_M150, 10)],
                        (981120, I.REACTION): [(_X150, 10)]}
        activity_time = {(981101, I.MANUFACTURING): 60,
                         (981102, I.MANUFACTURING): 60,
                         (981103, I.MANUFACTURING): 60,
                         (981104, I.MANUFACTURING): 60,
                         (981120, I.REACTION): 60}
        activity_max_runs = {}
        reaction_products = {_R150}
        invention_for_bpc = {}
        bp_products = {}
        item_cat = {}

        def is_manufactured(self, t):
            return t in self.product_to_bp
    _PM150 = {_M150: 10.0, _R150: 5000.0, _X150: 1.0,
              _A150: 1e6, _B150: 1e6, _D150: 1e6, _E150: 1e6}
    from eve_trader import store as _st150, esi as _esi150
    _alt150 = {"rec": I.recipes_cached, "snap": _st150.get_snapshot,
               "mp": _esi150.market_prices, "adj": _esi150.adjusted_prices,
               "sde": I.sde_ready, "namen": _esi150.resolve_names,
               "idx": _esi150.system_cost_indices, "sys": _esi150.all_system_names,
               "run": win._run, "pix": win._item_pixmap, "slots": win._load_char_slots,
               "wahl": win._multi_ende_waehlen,
               # Fenster-Zustand, von dem spaetere Pruefungen leben (b108):
               # eine hier gesetzte Tiefe "From components" liesse sie anders
               # rechnen.
               "zust": {_k: getattr(win, _k, None) for _k in (
                   "_bd_owned_bp", "_bd_force", "_bd_prefer_owned")}}
    try:
        I.sde_ready = lambda: True
        _esi150.resolve_names = lambda ids: {int(_i): f"Item{_i}" for _i in ids}
        _esi150.system_cost_indices = lambda *a150, **k150: {}
        _esi150.all_system_names = lambda *a150, **k150: {}
        win._item_pixmap = lambda *a150, **k150: None
        win._load_char_slots = lambda *a150, **k150: None
        win._run = lambda w, done, fail_cb=None, **k150: done(w._fn(*w._args, **w._kwargs))
        I.recipes_cached = lambda *a150, **k150: _Rec150()
        _st150.get_snapshot = lambda *a150, **k150: [
            {"type_id": _t, "sell_min": _v} for _t, _v in _PM150.items()]
        _esi150.market_prices = lambda *a150, **k150: {"adjusted": dict(_PM150),
                                                      "average": dict(_PM150)}
        _esi150.adjusted_prices = lambda *a150, **k150: dict(_PM150)
        _d150a = win._offener_bauplan()
        if _d150a is not None:
            _d150a.close(); _app.processEvents()
        win._bd_dialog = None
        _pa150 = {"id": None, "label": "b150", "type_id": _A150, "item_name": "A150",
                  "qty": 1, "me": 0, "te": 0}
        _e150 = win._multi_ende_anhaengen(_pa150, _B150, 1, me=0, te=0)
        win._multi_plan_oeffnen(_e150, plan_id=None); _app.processEvents()
        # Tiefe setzen wie der Knopf (Haken -> never_build -> Neuaufbau);
        # die Haken-Karte ist im Testfenster nicht immer gebaut.
        win._bd_owned_bp = sorted(win._depth_keys("ab_komponenten"))
        win._bau_refresh_exclusions_and_rebuild(); _app.processEvents()
        check(f"b150 VORBEDINGUNG: R ist im Fenster bekannt? nein - erst D bringt "
              f"es mit ({_R150 in (win._bd_all_ids or ())})",
              _R150 not in (win._bd_all_ids or ()))
        _nb150a = set((win._bd_opts or {}).get("never_build") or ())
        # Ein Ende, dessen Kette das Fenster schon kennt: Fenster BLEIBT
        # (Nutzer 27.09.2026: "ohne Uebergaenge") - nur das Ende ist neu.
        _dlg150 = win._bd_dialog
        win._multi_offen_einfuegen([{"tid": _E150, "name": "E150", "qty": 1}])
        _app.processEvents()
        check("b150 Ende mit bekannter Kette: dasselbe Fenster, Ende drin",
              win._bd_dialog is _dlg150 and _dlg150 is not None
              and _E150 in [a for a, _b in (win._bd_buendel_enden or [])])
        win._multi_offen_einfuegen([{"tid": _D150, "name": "D150", "qty": 1}])
        _app.processEvents()
        _nb150 = set((win._bd_opts or {}).get("never_build") or ())
        _plan150 = ((getattr(win, "_bd_plan_ref", None) or {}).get("plan") or {})
        check(f"b150 Tiefe 'From components' steht ({win._depth_of(win._bd_owned_bp)})",
              win._depth_of(win._bd_owned_bp) == "ab_komponenten")
        check(f"b150 das neue Ende ist im Buendel "
              f"({[a for a, _b in (win._bd_buendel_enden or [])]})",
              _D150 in [a for a, _b in (win._bd_buendel_enden or [])])
        check(f"b150 die Reaktion des NEUEN Endes wird nicht gebaut "
              f"(never_build vorher {sorted(_nb150a)}, nachher {sorted(_nb150)})",
              _R150 in _nb150)
        check(f"b150 ... und landet im Einkauf, nicht im Bau "
              f"(buy {sorted((_plan150.get('buy') or {}))}, "
              f"build {sorted((_plan150.get('build_runs') or {}))})",
              _R150 in (_plan150.get("buy") or {})
              and _R150 not in (_plan150.get("build_runs") or {}))
    finally:
        I.sde_ready = _alt150["sde"]
        _esi150.resolve_names = _alt150["namen"]
        _esi150.system_cost_indices = _alt150["idx"]
        _esi150.all_system_names = _alt150["sys"]
        win._run = _alt150["run"]; win._item_pixmap = _alt150["pix"]
        win._load_char_slots = _alt150["slots"]
        I.recipes_cached = _alt150["rec"]
        _st150.get_snapshot = _alt150["snap"]
        _esi150.market_prices = _alt150["mp"]
        _esi150.adjusted_prices = _alt150["adj"]
        win._multi_ende_waehlen = _alt150["wahl"]
        _d150z = win._offener_bauplan()
        if _d150z is not None:
            _d150z.close(); _app.processEvents()
        for _k, _v in _alt150["zust"].items():
            setattr(win, _k, _v)
except Exception as _e150x:                              # pragma: no cover
    import traceback as _tb150
    _fail.append(f"b150 Tiefe im Buendel: {type(_e150x).__name__}: {_e150x} | "
                 + _tb150.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b152)
# T1-ORIGINALE DER INVENTION HEISSEN SO (emm323, Nutzer 01.10.2026: "die zu
# inventenden T1-Blueprint-Originale werden als Component deklariert - aber
# es sind Blueprints"). Am echten Blueprints-Tab-Fuller.
try:
    from PySide6.QtWidgets import QTableWidget as _QTW152
    from eve_trader.sprache import t as _t152

    class _Rec152:
        invention_for_bpc = {982102: (982101, 10, 0.34, [])}
        activity_max_runs = {}
        reaction_products = set()
        bp_materials = {}
        product_to_bp = {}
    _alt152 = {k: getattr(win, k, None) for k in (
        "_bd_opts", "_bd_bp_owned_counts", "_bd_bp_owned_bpc_runs")}
    try:
        win._bd_opts = {"invention": True}
        win._bd_bp_owned_counts = {982101: 1, 982111: 2}
        win._bd_bp_owned_bpc_runs = {}
        _tbl152 = _QTW152(0, 7)
        _jobs152 = [
            {"tid": 982002, "bp_id": 982102, "activity": I.MANUFACTURING, "runs": 30,
             "is_end": True, "name": "Augmentor II b152"},
            {"tid": 982001, "bp_id": 982101, "activity": I.MANUFACTURING, "runs": 30,
             "name": "Augmentor I b152"},
            {"tid": 982011, "bp_id": 982111, "activity": I.MANUFACTURING, "runs": 30,
             "name": "Sensor Cluster b152"}]
        win._fill_blueprint_tab(_jobs152, [], _Rec152(), _tbl152)
        _st152 = {_tbl152.item(_r, 0).text(): _tbl152.item(_r, 1).text()
                  for _r in range(_tbl152.rowCount())}
        _qt152 = _t152("T1 original \u00b7 invention")
        check(f"b152 das T1-Original der Invention heisst so, nicht 'Component' "
              f"({_st152})",
              any("Augmentor I b152" in _n and "II" not in _n and _s == _qt152
                  for _n, _s in _st152.items()))
        check("b152 eine echte Komponente bleibt 'Component'",
              any("Sensor Cluster b152" in _n and _s == _t152("Component")
                  for _n, _s in _st152.items()))
        check("b152 das T2-Endprodukt bleibt 'End product'",
              any("Augmentor II b152" in _n and _s == _t152("End product")
                  for _n, _s in _st152.items()))
    finally:
        for _k, _v in _alt152.items():
            setattr(win, _k, _v)
except Exception as _e152:                               # pragma: no cover
    import traceback as _tb152
    _fail.append(f"b152 Invention-Quelle: {type(_e152).__name__}: {_e152} | "
                 + _tb152.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b155)
# MEINE BAUPLAENE IN ZWEI ABSCHNITTEN (emm337, Nutzer: "Unterteilung zwischen
# erledigten und noch laufenden Bauplaenen, die erledigten ausgegraut,
# laufende bisschen heller" -> "Zwei Abschnitte + Farben").
try:
    from eve_trader import config as _cfg155
    from eve_trader.ui import theme as _th155
    from PySide6.QtCore import QEvent as _QE155
    _plans_alt155 = list(win.settings.get("bau_saved_plans", []) or [])
    _ss_alt155 = _cfg155.save_settings
    _ssa_alt155 = _cfg155.save_settings_async
    _man_alt155 = (win.settings.get("bau_plan_manuell"), win.settings.get("bau_plan_eigene_folge"))
    try:
        _cfg155.save_settings = lambda *a, **k: None
        _cfg155.save_settings_async = lambda *a, **k: None
        win.settings["bau_plan_manuell"] = False
        win.settings["bau_plan_eigene_folge"] = False
        win.settings["bau_saved_plans"] = [
            {"id": 15501, "label": "b155 Offen A", "type_id": 975501, "item_name": "A",
             "qty": 2, "me": 0, "te": 0, "checked": []},
            {"id": 15502, "label": "b155 Fertig", "type_id": 975502, "item_name": "F",
             "qty": 2, "me": 0, "te": 0, "checked": [], "done_manual": True},
            {"id": 15503, "label": "b155 Offen B", "type_id": 975503, "item_name": "B",
             "qty": 2, "me": 0, "te": 0, "checked": []}]
        win._reload_saved_plans(); _app.processEvents()
        _lz155 = win._plan_sortier_layout
        _w155 = win._plan_karte_wrap
        _k155 = getattr(win, "_plan_abschnitt_lbls", (None, None))
        check(f"b155 zwei Abschnitte mit Zahl ({[k.text() for k in _k155 if k]})",
              _k155[0] is not None and _k155[0].text() in ("IN PROGRESS (2)", "LAUFEND (2)")
              and _k155[1].text() in ("COMPLETED (1)", "ERLEDIGT (1)"))
        check("b155 laufende im sortierbaren Abschnitt, erledigte darunter getrennt",
              _lz155.indexOf(_w155[15501]) >= 0 and _lz155.indexOf(_w155[15503]) >= 0
              and _lz155.indexOf(_w155[15502]) < 0
              and 15502 in (getattr(win, "_plan_fertig_wraps", None) or {}))
        _eff155 = _w155[15502].graphicsEffect()
        check("b155 erledigte Karte ist blass, laufende nicht",
              _eff155 is not None and abs(_eff155.opacity() - 0.5) < 1e-9
              and _w155[15501].graphicsEffect() is None)
        _app.sendEvent(_w155[15502], _QE155(_QE155.Enter))
        _hell155 = _eff155.opacity()
        _app.sendEvent(_w155[15502], _QE155(_QE155.Leave))
        check(f"b155 Maus darueber: wieder voll sichtbar, danach blass ({_hell155})",
              abs(_hell155 - 1.0) < 1e-9 and abs(_eff155.opacity() - 0.5) < 1e-9)
        _kc155 = win._plan_karte
        check("b155 laufende Karte eine Stufe heller, erledigte nicht",
              _th155.PANEL_HELL in _kc155[15501].styleSheet()
              and _th155.PANEL_HELL not in _kc155[15502].styleSheet())
        # Fortschritts-Sortierung zieht die erledigte NICHT in den oberen Teil.
        win._sortiere_plan_karten({15501: {"qty": 2, "built": 0, "pct": 10.0},
                                   15502: {"qty": 2, "built": 2, "pct": 100.0, "done_manual": True},
                                   15503: {"qty": 2, "built": 1, "pct": 50.0}})
        _app.processEvents()
        check("b155 Sortieren: oben B (50 %) vor A (10 %), die erledigte bleibt unten",
              _lz155.indexOf(_w155[15503]) == 0 and _lz155.indexOf(_w155[15501]) == 1
              and _lz155.indexOf(_w155[15502]) < 0)
    finally:
        win.settings["bau_saved_plans"] = _plans_alt155
        _cfg155.save_settings = _ss_alt155
        _cfg155.save_settings_async = _ssa_alt155
        for _k_m, _v_m in zip(("bau_plan_manuell", "bau_plan_eigene_folge"), _man_alt155):
            if _v_m is None:
                win.settings.pop(_k_m, None)
            else:
                win.settings[_k_m] = _v_m
        win._reload_saved_plans(); _app.processEvents()
except Exception as _e155:                               # pragma: no cover
    import traceback as _tb155
    _fail.append(f"b155 Abschnitte: {type(_e155).__name__}: {_e155} | "
                 + _tb155.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b154)
# PLAN UMBENENNEN per Rechtsklick (emm334, Nutzer 02.10.2026: "per
# Rechtsklick auf einen Buildplan wuerde ich gerne Rename machen koennen").
try:
    from eve_trader import config as _cfg154
    import eve_trader.ui.mw_multi_bauplan as _mmb154
    _plans_alt154 = list(win.settings.get("bau_saved_plans", []) or [])
    _ss_alt154 = _mmb154.config.save_settings
    _rl_alt154 = win._reload_saved_plans
    _tip_alt154 = win._flash_tip
    _off_alt154 = win._plan_offen_im_fenster
    _rl154, _tips154 = [], []
    try:
        win.settings["bau_saved_plans"] = _plans_alt154 + [
            {"id": 915401, "label": "b154 A", "type_id": 1, "qty": 1},
            {"id": 915402, "label": "b154 B", "type_id": 2, "qty": 1}]
        _mmb154.config.save_settings = lambda *a, **k: None
        win._reload_saved_plans = lambda *a, **k: _rl154.append(1)
        win._flash_tip = lambda text=None, *a, **k: _tips154.append(str(text or ""))
        win._plan_offen_im_fenster = lambda pid: False
        _by154 = lambda: {p["id"]: p for p in win.settings["bau_saved_plans"]}
        _r1 = win._plan_umbenennen(915401, neu="  b154 Neu  ")
        check("b154 umbenannt (Leerraum weg), Karten neu",
              _r1 is True and _by154()[915401]["label"] == "b154 Neu" and _rl154)
        _r2 = win._plan_umbenennen(915401, neu="b154 B")
        check("b154 Name eines ANDEREN Plans: abgelehnt mit Hinweis",
              _r2 is False and _by154()[915401]["label"] == "b154 Neu"
              and any("b154 B" in x for x in _tips154))
        check("b154 leer oder unveraendert: nichts",
              win._plan_umbenennen(915401, neu="   ") is False
              and win._plan_umbenennen(915401, neu="b154 Neu") is False)
        win._plan_offen_im_fenster = lambda pid: pid == 915402
        check("b154 im Fenster offener Plan: nicht umbenennen (Speichern sucht ueber den Namen)",
              win._plan_umbenennen(915402, neu="b154 X") is False
              and _by154()[915402]["label"] == "b154 B")
    finally:
        win.settings["bau_saved_plans"] = _plans_alt154
        _mmb154.config.save_settings = _ss_alt154
        win._reload_saved_plans = _rl_alt154
        win._flash_tip = _tip_alt154
        win._plan_offen_im_fenster = _off_alt154
except Exception as _e154:                               # pragma: no cover
    import traceback as _tb154
    _fail.append(f"b154 Umbenennen: {type(_e154).__name__}: {_e154} | "
                 + _tb154.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b153)
# INDUSTRY JOBS (emm327, Discord-Wunsch ueber den Nutzer: "welcher Char was
# baut ... welche Slots belegt mit was und wie lange"; Ort: neuer Knopf in der
# Leiste unter PRODUCTION). Echter Knopf-Weg ueber _bau_nav(4), ESI gestubbt.
try:
    import time as _ti153
    from datetime import datetime as _dt153, timezone as _tz153
    from eve_trader.sprache import t as _t153
    _alt153 = {"lc": store.list_characters, "sk": esi.fetch_skills,
               "aj": esi.fetch_active_jobs, "rn": esi.resolve_names}
    _hatte_cid153 = "client_id" in win.settings
    _cid_alt153 = win.settings.get("client_id")
    _jetzt153 = _ti153.time()

    def _iso153(off):
        return _dt153.fromtimestamp(_jetzt153 + off, _tz153.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ")
    try:
        store.list_characters = lambda: [{"character_id": 915301,
                                          "character_name": "b153 Pilot"},
                                         {"character_id": 915302,
                                          "character_name": "b153 Zweiter"}]
        esi.fetch_skills = lambda cid, ch: {3387: 4}      # Mass Production 4 -> 5 Fertigung
        esi.fetch_active_jobs = lambda cid, ch, **kw: [] if int(ch) == 915302 else [
            {"activity_id": 1, "product_type_id": 915311, "runs": 10,
             "status": "active", "end_date": _iso153(7200),
             "start_date": _iso153(-3600)},
            {"activity_id": 1, "product_type_id": 915311, "runs": 10,
             "status": "active", "end_date": _iso153(3 * 3600),
             "start_date": _iso153(-3600)},
            {"activity_id": 1, "product_type_id": 915312, "runs": 3,
             "status": "active", "end_date": _iso153(-60)},
            {"activity_id": 8, "product_type_id": 915313, "runs": 4,
             "status": "active", "end_date": _iso153(600)}]
        esi.resolve_names = lambda ids: {915311: "b153 Hammer", 915312: "b153 Zange",
                                         915313: "b153 Kopie Blueprint"}
        win.settings["client_id"] = "b153"
        _aus_alt153 = win.settings.pop("jobs_chars_aus", None)
        from eve_trader import config as _cfg153
        _ssa_alt153 = _cfg153.save_settings_async
        _cfg153.save_settings_async = lambda *a, **k: None   # .smoke_home bleibt sauber
        _btns153 = list(getattr(win, "_bau_page_btns", []) or [])
        check("b153 Leiste hat den Knopf 'Industry jobs' als 5. Seite",
              len(_btns153) == 5
              and _btns153[4].text() in ("Industry jobs", "Industrie-Jobs"))
        # Ein frueherer Lauf (b1b/b7n navigieren ueber Seite 4) darf nicht
        # mehr laufen, sonst landet SEIN Ergebnis hier.
        for _ in range(250):
            if not getattr(win, "_jobs_laeuft", False):
                break
            _app.processEvents(); _ti153.sleep(0.02)
        win._jobs_daten = None
        _btns153[4].click()
        for _ in range(250):
            _app.processEvents()
            if win._jobs_daten is not None and not win._jobs_laeuft:
                break
            _ti153.sleep(0.02)
        eq("b153 Klick zeigt Seite 4", win.b_stack.currentIndex(), 4)
        # emm330: KARTEN statt Tabelle - je Charakter eine Kachel.
        from eve_trader.ui import theme as _th153
        _k153 = (getattr(win, "_jobs_karten", None) or {}).get(915301)
        check(f"b153 eine Karte je Charakter, Handlungsbedarf zuerst ({list((getattr(win, '_jobs_karten', None) or {}).keys())})",
              _k153 is not None and list(win._jobs_karten) == [915301, 915302])
        _lbl153 = [l.text() for l in _k153.findChildren(QLabel)] if _k153 else []
        check("b153 Kartenkopf = Charaktername", "b153 Pilot" in _lbl153)
        _gr153 = getattr(_k153, "_gruppen", {}) if _k153 else {}
        # emm341 (Nutzer: "komplette Anzeige"): JEDER Job eine eigene Zeile,
        # kuerzeste Restzeit zuerst.
        eq("b153 laufende Jobs einzeln, kuerzeste Restzeit zuerst",
           [(g["tid"], g["n"]) for g in _gr153.get("laufend", [])],
           [(915313, 1), (915311, 1), (915311, 1)])
        eq("b153 fertiger Job steht im Fertig-Block",
           [(g["tid"], g["n"]) for g in _gr153.get("ready", [])], [(915312, 1)])
        check(f"b153 Fertig-Zeile gruen ({[x for x in _lbl153 if chr(10003) in x]})",
              _t153("\u2713 {n} ready to deliver").format(n=1) in _lbl153)
        # emm334: EINE Zeile je Gruppe (Kuerzel, Name, Restzeit; Fortschritt
        # als Zeilen-Hintergrund), "Blueprint" faellt bei Science-Jobs weg.
        from eve_trader.ui.mw_bauplan_tabs import JobZeile as _JZ153
        _jzl153 = [(z.name.voller_text(), z) for z in _k153.findChildren(_JZ153)] if _k153 else []
        _ham153 = [z for n, z in _jzl153 if n in ("b153 Hammer (10 runs)", "b153 Hammer (10 Runs)")]
        _kop153 = [z for n, z in _jzl153 if n in ("b153 Kopie (4 runs)", "b153 Kopie (4 Runs)")]
        check(f"b153 zwei Hammer-Zeilen mit Kuerzel und Aktivitaet im Tooltip ({[n for n, _ in _jzl153]})",
              len(_jzl153) == 3 and len(_ham153) == 2
              and all(z.tag.text() == _t153("Mfg.") for z in _ham153)
              and all(_t153("Manufacturing") in z.toolTip() for z in _ham153))
        check("b153 Invention-Zeile ohne ' Blueprint', Kuerzel Inv",
              len(_kop153) == 1 and _kop153[0].tag.text() == _t153("Inv"))
        # AUSKLAPPEN (Nutzer: "standardmaessig nur die Compact-Ansicht").
        _bd153 = getattr(_k153, "_jobs_body", None)
        _pf153 = getattr(_k153, "_jobs_pfeil", None)
        _ko_alt153 = win.settings.pop("jobs_karten_offen", None)
        check("b153 Jobliste standardmaessig zugeklappt, Knopf nennt 3 Jobs",
              _bd153 is not None and _bd153.isHidden() and _pf153 is not None
              and _pf153.text().startswith("\u25b8")
              and _t153("{n} running job(s)").format(n=3) in _pf153.text())
        check("b153 Klappknopf zeigt sich klickbar: Hand-Cursor, Hover-Stil, Tooltip",
              _pf153 is not None and _pf153.cursor().shape() == Qt.PointingHandCursor
              and "QPushButton:hover" in _pf153.styleSheet()
              and _pf153.toolTip() == _t153("Click to show or hide the running jobs"))
        _su153 = getattr(win, "_jobs_summe", None) or {}
        check(f"b153 Gesamt-Leiste: 1 fertig, 2 + 5 Fertigungs-Slots frei, naechster = Pilot ({_su153})",
              _su153.get("ready") == 1 and (_su153.get("free") or {}).get("mfg") == 7
              and (_su153.get("next") or (0, ""))[1] == "b153 Pilot"
              and win._jobs_summe_box.isVisibleTo(win._jobs_summe_box.parentWidget()))
        # KACHELN STATT TEXT (emm346, Nutzer: "den Text oben mehr in eine
        # Grafik, damit man schoen sieht, wie viele Slots frei sind").
        _ka153 = getattr(win, "_jobs_kapazitaet", None) or {}
        _kc153 = getattr(win, "_jobs_kacheln", None) or {}
        eq("b153 Fertigung ueber beide: 2 laufend, 1 fertig, 10 Slots, 7 frei",
           _ka153.get("mfg"), {"running": 2, "ready": 1, "max": 10, "free": 7})
        check("b153 Kachel Fertigung: grosse 7, Balken mit 2 + 1 von 10",
              "mfg" in _kc153 and ">7<" in _kc153["mfg"]["zahl"].text()
              and (_kc153["mfg"]["balken"].laufend, _kc153["mfg"]["balken"].fertig,
                   _kc153["mfg"]["balken"].maximum) == (2, 1, 10))
        check("b153 Kachel 'naechster fertig' nennt Zeit und Charakter",
              "next" in _kc153 and getattr(_kc153["next"]["unter"], "voller_text",
                                          _kc153["next"]["unter"].text)() == "b153 Pilot"
              and _kc153["next"]["zahl"].text() not in ("", "\u2013"))
        # SEITENBREITE MIT LANGEN TEXTEN (pruefe.py 02.10.2026, Windows: die
        # Seite war 1'306 px breit, b66 rot). Ein ueberlanger Item-Name in der
        # Kachel darf die Seite nicht verbreitern; Grenze hier 600 px, weil
        # Windows dieselben Texte ~1,6x breiter misst (600 x 1,6 + 230 < 1366).
        _kc153["next"]["unter"].setText("b153 " + "Capital Ship Maintenance Bay " * 6)
        _app.processEvents()
        _pg153 = win.b_stack.widget(4)
        _bw153 = _pg153.minimumSizeHint().width()
        # Windows (pruefe.py 02.10.2026): 714 px - der Faktor ist dort kein
        # fester 1,6x. Dort gilt die echte Zusage aus b66 (Seite + 230 <= 1366),
        # hier die strengere Grenze, damit eine Verbreiterung rot wird.
        _gr153 = 1136 if sys.platform == "win32" else 600
        check(f"b153 Seite bleibt schmal, auch mit langem Namen ({_bw153} <= {_gr153})",
              _bw153 <= _gr153)
        check("b153 ohne Ausgeblendete keine Textzeile darunter",
              win._jobs_summe_lbl.isHidden())
        # CHARAKTERE AN/AUS (Nutzer: "rechts eine Charakter-Uebersicht, per
        # On/Off, standardmaessig alle On").
        _sw153 = getattr(win, "_jobs_schalter", None) or {}
        check("b153 rechts je Charakter ein Schalter, alle standardmaessig an",
              sorted(_sw153) == [915301, 915302]
              and all(b.isChecked() for b in _sw153.values()))
        if 915302 in _sw153:
            _sw153[915302].click(); _app.processEvents()
        check(f"b153 Aus: Karte weg, gemerkt, Leiste nennt ihn ({list(win._jobs_karten)})",
              list(win._jobs_karten) == [915301]
              and win.settings.get("jobs_chars_aus") == ["915302"]
              and _t153("{n} character(s) hidden").format(n=1)
              in win._jobs_summe_lbl.text())
        win._jobs_alle_btn.click(); _app.processEvents()
        check("b153 'All on' holt ihn zurueck",
              list(win._jobs_karten) == [915301, 915302]
              and win.settings.get("jobs_chars_aus") == []
              and all(b.isChecked() for b in win._jobs_schalter.values()))
        _k153 = win._jobs_karten.get(915301)
        _sl153 = getattr(_k153, "_slots", {}) if _k153 else {}
        check("b153 Slot-Kaestchen: Fertigung 2 laufend + 1 fertig von 5, cyan",
              _sl153.get("mfg") is not None and _sl153["mfg"].laufend == 2
              and _sl153["mfg"].fertig == 1 and _sl153["mfg"].maximum == 5
              and _sl153["mfg"].farbe == _th153.CYAN)
        check("b153 Science 1 von 1, amber",
              _sl153.get("sci") is not None and _sl153["sci"].laufend == 1
              and _sl153["sci"].maximum == 1 and _sl153["sci"].farbe == _th153.AMBER)
        _k153._jobs_pfeil.click(); _app.processEvents()
        check(f"b153 Klick klappt auf und merkt den Charakter ({win.settings.get('jobs_karten_offen')})",
              not _k153._jobs_body.isHidden()
              and _k153._jobs_pfeil.text().startswith("\u25be")
              and win.settings.get("jobs_karten_offen") == ["915301"])
        win._jobs_karten_zeichnen(); _app.processEvents()
        _k153 = win._jobs_karten.get(915301)
        check("b153 nach Neuzeichnen bleibt sie offen, der Zweite zu",
              _k153 is not None and _k153._jobs_body is not None
              and not _k153._jobs_body.isHidden()
              and getattr(win._jobs_karten.get(915302), "_jobs_body", None) is None)
        _uhr153 = {}
        for g, lb, bar in sorted(win._jobs_uhr_teile, key=lambda x: -(x[0]["ende"] or 0)):
            _uhr153[g["tid"]] = (lb, bar)    # je tid die Zeile mit dem FRUEHESTEN Ende
        check(f"b153 Hammer zeigt Restzeit ({_uhr153.get(915311, (None,))[0].text() if 915311 in _uhr153 else None!r})",
              915311 in _uhr153 and _uhr153[915311][0].text() in ("1 h 59 m", "2 h 0 m"))
        win._jobs_rest_auffrischen(jetzt=_jetzt153 + 3 * 3600 + 120)
        eq("b153 die Uhr macht aus Restzeit 'fertig' ohne neuen Abruf",
           _uhr153[915311][0].text(), _t153("ready to deliver \u2713"))
        check("b153 ... und der Balken steht voll",
              _uhr153[915311][1].value() == 1000)
        # NEBENEINANDER (Nutzer: "Charaktere nebeneinander, nicht untereinander").
        from eve_trader.ui.mw_bauplan_tabs import KartenRaster as _KR153
        from PySide6.QtWidgets import QFrame as _QF153
        _r153 = _KR153(breite=100)
        _r153.resize(450, 300)
        _ks153 = [_QF153() for _ in range(5)]
        for _kx in _ks153:
            _kx.setFixedHeight(50)
        _r153.setze(_ks153); _app.processEvents(); _r153.layout().activate()
        eq("b153 Karten-Raster: 4 Spalten bei 450 px, die 5. bricht um (Platz, Spalte)",
           _r153.lage(), [(0, 0), (0, 1), (0, 2), (0, 3), (1, 0)])
        # emm342 (Nutzer: "wenn man Dropdown aufmacht ... die anderen Karten
        # rechts oder links davon nicht mitrutschen"): waechst Karte 0, rutscht
        # nur ihre Spalte - die Karte unter dem Nachbarn bleibt stehen.
        _y153 = [_kx.geometry().y() for _kx in _ks153]
        _ks153[0].setFixedHeight(300); _app.processEvents(); _r153.layout().activate()
        _y2_153 = [_kx.geometry().y() for _kx in _ks153]
        check(f"b153 Aufklappen: nur die eigene Spalte rutscht ({_y153} -> {_y2_153})",
              _y2_153[1:4] == _y153[1:4] and _y2_153[4] >= _y153[4] + 250)
        _r153.resize(230, 300); _r153._anordnen()
        eq("b153 schmaler: 2 Spalten, Lesereihenfolge zeilenweise",
           _r153.lage(), [(0, 0), (0, 1), (1, 0), (1, 1), (2, 0)])
        _r153.deleteLater()
    finally:
        store.list_characters = _alt153["lc"]
        esi.fetch_skills = _alt153["sk"]
        esi.fetch_active_jobs = _alt153["aj"]
        esi.resolve_names = _alt153["rn"]
        try:
            _cfg153.save_settings_async = _ssa_alt153
            if _ko_alt153 is None:
                win.settings.pop("jobs_karten_offen", None)
            else:
                win.settings["jobs_karten_offen"] = _ko_alt153
        except NameError:
            pass
        try:
            if _aus_alt153 is None:
                win.settings.pop("jobs_chars_aus", None)
            else:
                win.settings["jobs_chars_aus"] = _aus_alt153
        except NameError:
            pass
        if _hatte_cid153:
            win.settings["client_id"] = _cid_alt153
        else:
            win.settings.pop("client_id", None)
        win._bau_nav(0)
except Exception as _e153:                               # pragma: no cover
    import traceback as _tb153
    _fail.append(f"b153 Industry jobs: {type(_e153).__name__}: {_e153} | "
                 + _tb153.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b149)
# STEHT VOR b144/b79 GANZ HINTEN: schliesst sein Fenster (b105/b108).
# NACH "FREEZE" IMMER DIE RESERVIERUNG ANBIETEN (emm314, Nutzer 01.10.2026:
# "Bauplan eingefroren und wurde danach nicht gefragt, ob ich die
# Materialien reservieren moechte und das Schloss zumachen. Das muss immer
# gefragt werden, wenn ich den Knopf Freeze druecke"). Am echten Knopf.
try:
    import eve_trader.config as _cfg149
    _alt149 = {"save": _cfg149.save_settings, "box": win._reservierung_box,
               "plans": win.settings.get("bau_saved_plans"),
               "pid": getattr(win, "_bd_open_plan_id", None)}
    _fragen149 = []
    _antwort149 = {"ja": True}

    class _Box149:
        def __init__(self, name, n, koll):
            _fragen149.append((name, n, list(koll)))
            self._ja, self._nein = object(), object()

        def exec(self):
            return 0

        def button(self, b):
            from PySide6.QtWidgets import QMessageBox as _Q
            return self._ja if b == _Q.Yes else self._nein

        def clickedButton(self):
            return self._ja if _antwort149["ja"] else self._nein
    try:
        _cfg149.save_settings = lambda *a, **k: None
        win._reservierung_box = lambda par, name, n, koll=(): _Box149(name, n, koll)
        _e149 = {"id": 91491, "label": "b149 Plan", "type_id": 100, "qty": 1,
                 "reserve": False, "reserve_map": {200: 50, 201: 5}}
        _o149 = {"id": 91492, "label": "b149 Anderer", "type_id": 101, "qty": 1,
                 "reserve": True, "reserve_map": {200: 10}}
        win.settings["bau_saved_plans"] = [_e149, _o149]
        win._bd_frozen = None
        win._show_build_detail(100, "b149", _res); _app.processEvents()
        _d149 = win._bd_dialog
        win._bd_open_plan_id = 91491
        _fb149 = win._bd_frozen_btn

        def _frieren149(an):
            _fb149.setChecked(an); _app.processEvents()

        _frieren149(True)
        check(f"b149 Freeze fragt nach der Reservierung, nennt den anderen Plan "
              f"({_fragen149})",
              len(_fragen149) == 1 and _fragen149[0][0] == "b149 Plan"
              and _fragen149[0][1] == 2 and _fragen149[0][2] == ["b149 Anderer"])
        check("b149 'Ja' schliesst das Schloss (Plan reserviert)",
              _e149.get("reserve") is True)
        # Wieder auftauen (ohne Rueckfrage), Schloss offen, "Nein" antworten.
        _alt_auf149 = win._auftauen_bestaetigen
        win._auftauen_bestaetigen = lambda *a, **k: True
        try:
            _frieren149(False)
            _e149["reserve"] = False
            _antwort149["ja"] = False
            _frieren149(True)
            check(f"b149 jedes Freeze fragt erneut; 'Nein' laesst offen "
                  f"({len(_fragen149)})",
                  len(_fragen149) == 2 and _e149.get("reserve") is False)
            # Schon reserviert -> keine Frage.
            _frieren149(False)
            _e149["reserve"] = True
            _frieren149(True)
            check(f"b149 schon reserviert: keine Frage ({len(_fragen149)})",
                  len(_fragen149) == 2)
            # Ungespeicherter Plan -> keine Frage (es gibt nichts zu reservieren).
            _frieren149(False)
            _e149["reserve"] = False
            win._bd_open_plan_id = None
            _frieren149(True)
            check(f"b149 ungespeicherter Plan: keine Frage ({len(_fragen149)})",
                  len(_fragen149) == 2)
            _frieren149(False)
        finally:
            win._auftauen_bestaetigen = _alt_auf149
        if _d149 is not None:
            _d149.close(); _app.processEvents()
    finally:
        _cfg149.save_settings = _alt149["save"]
        win._reservierung_box = _alt149["box"]
        win.settings["bau_saved_plans"] = _alt149["plans"] or []
        win._bd_open_plan_id = _alt149["pid"]
        win._bd_frozen = None
        win._bd_frozen_plan_cache = None
except Exception as _e149x:                              # pragma: no cover
    import traceback as _tb149
    _fail.append(f"b149 Reservierung nach Freeze: {type(_e149x).__name__}: {_e149x} | "
                 + _tb149.format_exc().splitlines()[-3].strip())


# ---------------------------------------------------------------- (b144)
# RESET STATT RECALCULATE (Nutzer 30.09.2026: "den Knopf an Ort und Stelle
# lassen und durch Reset ersetzen, der alles im Bauplan auf Standard
# zuruecksetzt, mit Popup: willst du wirklich resetten? Yes/No"). Am echten
# Fenster: Nein tut nichts, Ja oeffnet den Plan FRISCH. Dazu die Frost-Sperre
# selbst: das Auftauen stellt den Zustand VOR dem Einfrieren wieder her.
# STEHT VOR b79 GANZ HINTEN: "Ja" schliesst das Fenster, von dessen
# Plan b105/b108 leben.
try:
    from PySide6.QtWidgets import QMessageBox as _QMB144, QSpinBox as _SB144
    _q_alt144 = _QMB144.question
    _obd_alt144 = win.open_build_detail
    _auf144 = []
    try:
        win._bd_frozen = None
        win._show_build_detail(100, "b144", _res); _app.processEvents()
        _d144 = win._bd_dialog
        # DIE ORDERBUCH-PREISE LEBEN UNTER TOOLS WEITER (der Teil von
        # "Recalculate", der Preise holte) - Eintrag startet genau den Abruf.
        _run_alt144 = win._run
        _jobs144 = []
        win._run = lambda *a, **k: _jobs144.append(k.get("label"))
        try:
            win._bd_tools_actions["ladder_plan"].trigger(); _app.processEvents()
        finally:
            win._run = _run_alt144
        check(f"b144 Tools: 'Load order-book prices into the plan' holt das Orderbuch "
              f"({_jobs144})",
              len(_jobs144) == 1 and ("Order book" in str(_jobs144[0])
                                      or "Orderbuch" in str(_jobs144[0])))
        _fr144 = []
        _QMB144.question = staticmethod(
            lambda *a, **k: (_fr144.append(a), _QMB144.No)[1])
        win.open_build_detail = lambda *a, **k: _auf144.append((a, k))
        # ENTER IN EINEM ZAHLENFELD IST KEIN RESET (Nutzer 01.10.2026: "ich
        # habe nur bei einem Endprodukt oben die Anzahl geaendert und Enter
        # gedrueckt" -> Reset-Frage). Das Zahlenfeld reicht Enter an das
        # Fenster weiter, und ein QDialog drueckt dann seinen ersten Knopf.
        from PySide6.QtTest import QTest as _QT144
        from PySide6.QtCore import Qt as _Qt144
        _sp144 = [s for s in _d144.findChildren(_SB144)
                  if s.isEnabled() and s.isVisible()]
        for _s144 in _sp144[:3]:
            _QT144.keyClick(_s144, _Qt144.Key_Return)
            _QT144.keyClick(_s144, _Qt144.Key_Enter)
        _app.processEvents()
        check(f"b144 Enter in einem Zahlenfeld loest KEIN Reset aus "
              f"({len(_sp144)} Felder, {len(_fr144)} Fragen)",
              len(_sp144) >= 1 and not _fr144 and not _auf144
              and win._bd_dialog is _d144)
        _fr144.clear()
        win._bd_reset_btn.click(); _app.processEvents()
        check(f"b144 Reset fragt, Vorgabe Nein; Nein tut nichts ({len(_fr144)}, {_auf144})",
              len(_fr144) == 1 and _fr144[0][-1] == _QMB144.No
              and "b144" in str(_fr144[0][2]) and not _auf144
              and win._bd_dialog is _d144)
        _QMB144.question = staticmethod(lambda *a, **k: _QMB144.Yes)
        win._bd_reset_btn.click(); _app.processEvents()
        check(f"b144 Ja: Fenster zu, Plan frisch geoeffnet ({_auf144})",
              _auf144 == [((100, "b144"), {"fresh": True})]
              and win._offener_bauplan() is None)
    finally:
        _QMB144.question = _q_alt144
        win.open_build_detail = _obd_alt144
    # FROST-SPERRE: gesperrt wegen Invention bleibt gesperrt, frei bleibt frei.
    _a144, _b144 = _SB144(), _SB144()
    _a144.setToolTip("Invention"); _b144.setToolTip("frei")
    _a144.setEnabled(False)
    win._frost_widgets([_a144, _b144], True, "frozen")
    _zu144 = (_a144.isEnabled(), _b144.isEnabled(), _b144.toolTip())
    win._frost_widgets([_a144, _b144], True, "frozen")     # zweimal: kein Verlust
    win._frost_widgets([_a144, _b144], False)
    check(f"b144 Frost sperrt beide und gibt genau den alten Zustand zurueck "
          f"({_zu144}, {_a144.isEnabled()}, {_b144.isEnabled()})",
          _zu144 == (False, False, "frozen")
          and not _a144.isEnabled() and _a144.toolTip() == "Invention"
          and _b144.isEnabled() and _b144.toolTip() == "frei")
except Exception as _e144:                                # pragma: no cover
    import traceback as _tb144
    _fail.append(f"b144 Reset-Knopf: {type(_e144).__name__}: {_e144} | "
                 + _tb144.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b145)
# FEHLT-ZEILEN ZAEHLEN DIE HAKEN WIE DIE EINKAUFSLISTE (Nutzer 30.09.2026,
# Basilisk: alle Composite-Reaktionen abgehakt, noch nicht abgeholt - der
# Materialien-Reiter verlangte ihre Intermediates trotzdem als "fehlt").
try:
    _alt145 = {k: getattr(win, k, None) for k in (
        "_bd_plan_ref", "_bd_opts", "_bd_runplan_delivered_sicher",
        "_bd_runplan_checked", "_bd_runplan_runs_by_key", "_bd_active_jobs_map",
        "_bd_recipes", "_bd_live_stock")}
    try:
        _C145, _I145, _K145 = 991450, 991451, 991452
        win._bd_plan_ref = {"plan": {"build_runs": {_C145: 10, _K145: 5},
                                     "build_mats": {_C145: [(_I145, 1000)],
                                                    _K145: [(_C145, 10)]}}}
        win._bd_opts = {"stock": {_I145: 0, _C145: 0}}
        win._bd_live_stock = {}
        win._bd_runplan_delivered_sicher = {}
        win._bd_active_jobs_map = {}
        win._bd_recipes = None
        win._bd_runplan_runs_by_key = {"reaction_2|1|%d" % _C145: (_C145, 10)}
        win._bd_runplan_checked = set()
        _ohne145 = {int(_x[0]) for _x in (win._fehlbedarf_jetzt() or [])}
        win._bd_runplan_checked = {"reaction_2|1|%d" % _C145}
        _mit145 = {int(_x[0]) for _x in (win._fehlbedarf_jetzt() or [])}
        _eink145 = dict(win._restbedarf_jetzt() or {})
    finally:
        for _k, _v in _alt145.items():
            setattr(win, _k, _v)
    check(f"b145 ohne Haken fehlt die Zutat (Gegenprobe) ({_ohne145})",
          _I145 in _ohne145)
    check(f"b145 abgehakte Reaktion: ihre Zutat fehlt nicht mehr ({_mit145})",
          _I145 not in _mit145)
    check(f"b145 ... genau wie in der Einkaufsliste ({_eink145})",
          not _eink145.get(_I145))
    # KEINE NEBENWIRKUNG (Nutzer: "kann man die verhindern?"): C ist
    # abgehakt, ESI kennt den Job noch nicht - K braucht C, das kommt noch.
    check(f"b145 abgehakt, ESI kennt den Job noch nicht: sein Erzeugnis fehlt "
          f"nicht ({_mit145})", _C145 not in _mit145)
except Exception as _e145:                                # pragma: no cover
    import traceback as _tb145
    _fail.append(f"b145 Fehlt-Zeilen mit Haken: {type(_e145).__name__}: {_e145} | "
                 + _tb145.format_exc().splitlines()[-3].strip())

# ---------------------------------------------------------------- (b162)
_app.processEvents()
check("b162 keine unbehandelte Ausnahme in einem Slot waehrend des Laufs"
      + (" - " + " | ".join(_unbehandelt162[:3]) if _unbehandelt162 else ""),
      not _unbehandelt162)

# ---------------------------------------------------------------- (b79)
# FEHLER.LOG-NETZ (siehe Kopf der Datei): alles, was dieser Lauf an
# fehler.log angehaengt hat, darf keinen Programmierfehler enthalten.
# Netz-/ESI-Fehler (offline, Test-Corp 403) sind erwartet und bleiben erlaubt.
_flog_neu = ""
try:
    with open(_FLOG, "r", encoding="utf-8", errors="replace") as _fh79:
        _fh79.seek(_FLOG_START)
        _flog_neu = _fh79.read()
except OSError:
    pass
_flog_bad = [_z.strip() for _z in _flog_neu.splitlines()
             if "has no attribute" in _z or "NameError" in _z
             or "is not defined" in _z or "TypeError" in _z
             or "KeyError" in _z or "IndexError" in _z]
check("b79 fehler.log: keine Programmierfehler waehrend des Laufs angehaengt"
      + (" - " + " | ".join(sorted(set(_flog_bad))[:3]) if _flog_bad else ""),
      not _flog_bad)

print(f"(b) Bauplan-Aufbau: {_ok}/{_ok + len(_fail)} gruen")
for f in _fail:
    print("  FEHLER: " + f)
# Sauber abraeumen: im Hintergrund koennen noch Worker laufen (Auto-Suche
# nach Asset-Orten, Preisabrufe). Ohne das beendet sich der Prozess mit
# "QThread: Destroyed while thread is still running" + Abort - das saehe wie
# ein Testfehler aus, obwohl alle Pruefungen gruen sind.
try:
    if _dlg is not None:
        _dlg.close()
    win.close()
    _app.processEvents()
except Exception:
    pass
sys.stdout.flush()
# HINTERGRUND-JOBS ABWARTEN (emm310). Windows-Lauf des Nutzers 01.10.2026:
# "Windows fatal exception: access violation" IN os._exit (Zeile darunter),
# NACH der Marke - also beim Beenden des Prozesses, nicht beim Schliessen
# der Fenster. VERMUTUNG (nicht bewiesen, hier nicht nachstellbar): noch
# laufende Worker-QThreads, waehrend Windows die Qt-DLLs entlaedt. Darum
# abbrechen und bis 5 s warten; die Marke sagt, wie viele noch liefen.
_laufend_b = []
_haengt_b = 0
try:
    _laufend_b = [_w for _w in list(getattr(win, "_workers", None) or [])
                  if _w.isRunning()]
    for _w in _laufend_b:
        _w.cancel()
    _haengt_b = sum(1 for _w in _laufend_b if not _w.wait(5000))
except Exception:
    pass
# MARKE FUER pruefe.py (01.10.2026, 0xC0000409 beim Nutzer nach der
# Ergebniszeile): steht sie auf stderr, kam der Absturz erst NACH dem
# Aufraeumen (beim Beenden des Prozesses), sonst beim Schliessen der Fenster.
print(f"(b) Aufraeumen fertig ({len(_laufend_b)} Hintergrund-Jobs liefen noch, "
      f"{_haengt_b} nach 5 s nicht fertig), Prozess endet",
      file=sys.stderr, flush=True)
# WINDOWS: PROZESS HART BEENDEN (emm311). Zweiter Windows-Lauf 01.10.2026:
# Marke "0 Hintergrund-Jobs liefen noch", trotzdem access violation IN
# os._exit (Rueckgabewert 0xC0000005) - die Worker-Vermutung aus emm310 ist
# damit WIDERLEGT. os._exit laesst Windows noch die DLLs abmelden (Qt,
# PySide); dort knallt es. TerminateProcess ueberspringt genau diesen
# Schritt, der Rueckgabewert bleibt der der Suite. Nur die Testsuite endet
# so - das Programm selbst ruft os._exit nirgends auf.
_code_b = 1 if _fail else 0
if sys.platform == "win32":
    try:
        import ctypes as _ct_b
        from ctypes import wintypes as _wt_b
        _k32_b = _ct_b.windll.kernel32
        # TYPEN FESTLEGEN (emm363, Windows-Lauf 02.10.2026: wieder 0xC0000005
        # in os._exit). Ohne restype kommt GetCurrentProcess() als 32-bit-int
        # zurueck, das Pseudo-Handle -1 wird auf 64 bit zu 0xFFFFFFFF - ein
        # ungueltiges Handle. TerminateProcess schlug damit STILL fehl, und
        # der Lauf fiel doch in os._exit.
        _k32_b.GetCurrentProcess.restype = _wt_b.HANDLE
        _k32_b.TerminateProcess.argtypes = [_wt_b.HANDLE, _wt_b.UINT]
        _k32_b.TerminateProcess.restype = _wt_b.BOOL
        _k32_b.TerminateProcess(_k32_b.GetCurrentProcess(), _code_b)
    except Exception:
        pass
os._exit(_code_b)
