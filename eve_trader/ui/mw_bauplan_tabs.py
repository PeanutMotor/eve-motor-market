"""Die vier grossen Fuell-Funktionen der Bauplan-Tabs - als Mixin
ausgelagert (Sitzung 8, Nutzer: "wir haben zu viel Code, es ist zu
unuebersichtlich").

REGELN FUER DIESES MODUL (wie mw_helpers.py):
* Die Methodenruempfe sind WOERTLICH aus main_window.py verschoben - kein
  Zeichen geaendert. Verhalten ist damit identisch.
* Es gibt hier KEINE `MainWindow.`-Selbstbezuege (vor dem Schnitt per AST
  geprueft: null Treffer). Falls jemand welche ergaenzt: sie muessten
  `BauplanTabs.` heissen, sonst Zirkel-Import.
* `isk`/`NumericItem` kommen aus `mw_basis.py`, NICHT aus main_window -
  genau dafuer wurde mw_basis angelegt.
* Die aa-Suite liest alle Dateien in eve_trader/ui/ zusammengehaengt
  (`_ui_dateien8` in test_bestand_herkunft.py), Text- und AST-Pruefungen
  sehen diese Datei also mit.
"""
import os

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QIcon
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QFrame, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSizePolicy, QSlider, QSpinBox,
    QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from .. import config, esi, hubs, industry, reprocess, store
from ..workers import Worker
from . import icons, theme
from ..sprache import t
from .mw_basis import (KEIN_DECRYPTOR, ROLLE_KOPIERNAME, NumericItem,
                       dec_anzeige, isk, kopier_menue, ohne_mausrad)


class SlotKaestchen(QWidget):
    """Job-Slots als Kaestchen (emm330): fertig gruen, laufend in der Farbe
    der Aktivitaet, frei nur umrandet. Ohne bekanntes Maximum nur die belegten."""
    GROESSE, ABSTAND = 11, 3

    def __init__(self, laufend, fertig, maximum, farbe, parent=None, breite=None,
                 abstand=None):
        super().__init__(parent)
        if abstand is not None:
            self.ABSTAND = int(abstand)
        self.laufend, self.fertig = int(laufend or 0), int(fertig or 0)
        self.maximum = None if maximum is None else int(maximum)
        self.farbe = farbe
        n = self.anzahl()
        # emm334: drei Slot-Arten NEBENEINANDER - die Kaestchen passen sich
        # der gegebenen Breite an (mindestens 4 px), statt je 11 px zu nehmen.
        self._g = self.GROESSE
        if breite:
            self._g = max(4, min(self.GROESSE, int(breite) // max(1, n) - self.ABSTAND))
        self.setFixedSize(max(1, n) * (self._g + self.ABSTAND), self._g + 2)

    def anzahl(self):
        belegt = self.laufend + self.fertig
        return max(belegt, self.maximum) if self.maximum is not None else belegt

    def paintEvent(self, _ev):
        from PySide6.QtGui import QPainter, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        g = self._g
        for i in range(self.anzahl()):
            x = i * (g + self.ABSTAND)
            if i < self.fertig:
                p.setPen(Qt.NoPen); p.setBrush(QColor(theme.GREEN))
            elif i < self.fertig + self.laufend:
                p.setPen(Qt.NoPen); p.setBrush(QColor(self.farbe))
            else:
                p.setPen(QPen(QColor(theme.BORDER), 1)); p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(x + 0.5, 1.5, g - 1, g - 1, 2, 2)
        p.end()


class KapazitaetsBalken(QWidget):
    """Ein Balken ueber ALLE Slots einer Art (emm346): fertig gruen, laufend
    in der Farbe der Aktivitaet, der Rest frei (dunkel mit Rand)."""

    def __init__(self, farbe, parent=None):
        super().__init__(parent)
        self.farbe = farbe
        self.laufend = self.fertig = self.maximum = 0
        self.setFixedHeight(10)
        self.setMinimumWidth(60)

    def setze(self, laufend, fertig, maximum):
        self.laufend, self.fertig = int(laufend or 0), int(fertig or 0)
        self.maximum = int(maximum or 0)
        self.update()

    def paintEvent(self, _ev):
        from PySide6.QtCore import QRectF
        from PySide6.QtGui import QPainter, QPen
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor(theme.BORDER), 1)); p.setBrush(QColor(theme.BG))
        p.drawRoundedRect(r, 4, 4)
        gesamt = max(self.maximum, self.laufend + self.fertig, 1)
        x = r.left()
        p.setPen(Qt.NoPen)
        for n, farbe in ((self.fertig, theme.GREEN), (self.laufend, self.farbe)):
            if n <= 0:
                continue
            w = r.width() * n / gesamt
            p.setBrush(QColor(farbe))
            p.drawRoundedRect(QRectF(x, r.top(), w, r.height()), 4, 4)
            x += w
        p.end()


class KurzLabel(QLabel):
    """Einzeiliger Text, der bei Platzmangel mit "..." gekuerzt wird statt
    abgeschnitten (emm334: "Plasma Pulse Generator Blueprint \u00b7 TE rese").
    Der volle Text steht im Tooltip und in `voller_text()`."""

    def __init__(self, text, parent=None):
        super().__init__(parent)
        self._voll = str(text)
        self.setToolTip(self._voll)
        self.setMinimumWidth(30)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        QLabel.setText(self, self._voll)

    def voller_text(self):
        return self._voll

    def setText(self, text):
        # Neuer Text: voll merken, Tooltip nachziehen, sofort gekuerzt zeigen.
        self._voll = str(text)
        self.setToolTip(self._voll)
        QLabel.setText(self, self.fontMetrics().elidedText(
            self._voll, Qt.ElideRight, max(10, self.width())))

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        QLabel.setText(self, self.fontMetrics().elidedText(
            self._voll, Qt.ElideRight, max(10, self.width())))


class JobZeile(QFrame):
    """Eine Job-Gruppe in EINER Zeile (emm334, Nutzer: "immer noch nicht
    uebersichtlich genug"): Kuerzel der Aktivitaet, "9x Name", Restzeit. Der
    Fortschritt fuellt den Hintergrund der Zeile in der Farbe der Art - keine
    eigene Balken-Zeile mehr. value()/setValue() 0..1000 wie ein Balken."""

    def __init__(self, kuerzel, text, rest, farbe, parent=None, corp=False):
        super().__init__(parent)
        self._farbe = QColor(farbe)
        self._wert = 0
        h = QHBoxLayout(self)
        h.setContentsMargins(6, 3, 8, 3)
        h.setSpacing(6)
        self.tag = QLabel(kuerzel)
        self.tag.setAlignment(Qt.AlignCenter)
        self.tag.setMinimumWidth(40)
        self.tag.setStyleSheet(
            f"color:{farbe}; border:1px solid {farbe}; border-radius:3px; "
            f"padding:0px 3px; font-size:{theme.FS_SMALL}; font-weight:700; "
            f"background:transparent;")
        h.addWidget(self.tag)
        # CORP-ABZEICHEN (emm396, Nutzer: "fehlt mir an Uebersicht zwischen
        # Corp und nicht Corp jobs"): amber Abzeichen statt des frueheren
        # " · Corp"-Textanhangs - faellt zwischen den Zeilen sofort auf.
        self.corp_tag = None
        if corp:
            self.corp_tag = QLabel(t("Corp"))
            self.corp_tag.setAlignment(Qt.AlignCenter)
            self.corp_tag.setStyleSheet(
                f"color:{theme.AMBER}; border:1px solid {theme.AMBER}; "
                f"border-radius:3px; padding:0px 3px; "
                f"font-size:{theme.FS_SMALL}; font-weight:700; "
                f"background:transparent;")
            h.addWidget(self.corp_tag)
        self.name = KurzLabel(text)
        self.name.setStyleSheet("font-weight:700; background:transparent;")
        h.addWidget(self.name, 1)
        self.rest = QLabel(rest)
        self.rest.setStyleSheet(f"font-family:{theme.MONO}; background:transparent;")
        h.addWidget(self.rest)

    def setValue(self, v):
        self._wert = max(0, min(1000, int(v or 0)))
        self.update()

    def value(self):
        return self._wert

    def paintEvent(self, ev):
        from PySide6.QtGui import QPainter
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, True)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.PANEL2))
        p.drawRoundedRect(self.rect(), 4, 4)
        if self._wert > 0:
            _c = QColor(self._farbe)
            _c.setAlpha(70)
            p.setBrush(_c)
            _r = self.rect()
            _r.setWidth(int(_r.width() * self._wert / 1000))
            p.drawRoundedRect(_r, 4, 4)
        p.end()
        super().paintEvent(ev)


class KartenRaster(QWidget):
    """Kacheln nebeneinander, so viele Spalten wie in die Breite passen
    (emm330: "Charaktere nebeneinander, nicht untereinander").

    emm398 (Nutzer: "so sehen die Karten nicht schoen angeordnet aus" ->
    "Buendige Reihen"): GITTER statt freier Spalten - alle Karten einer
    Reihe beginnen auf derselben Hoehe (AlignTop), die Reihe ist so hoch
    wie ihre hoechste Karte. Die emm342-Zusage bleibt dabei erfuellt:
    waechst eine Karte (Dropdown auf), bleiben die Nachbarn IHRER Reihe
    oben stehen, nur die Reihen darunter rutschen nach unten."""

    def __init__(self, breite=340, parent=None):
        super().__init__(parent)
        self._breite = int(breite)
        self._karten = []
        self._spalten = 0
        self._gitter = QGridLayout(self)
        self._gitter.setContentsMargins(0, 0, 0, 0)
        self._gitter.setHorizontalSpacing(12)
        self._gitter.setVerticalSpacing(12)

    def spalten(self):
        return max(1, (self.width() + 12) // (self._breite + 12))

    def _abhaengen(self):
        for k in self._karten:
            self._gitter.removeWidget(k)

    def setze(self, karten):
        self._abhaengen()
        for k in self._karten:
            # ERST ABHAENGEN, dann loeschen (emm461): `deleteLater` wirkt erst
            # in der naechsten Runde der Ereignisschleife - bis dahin blieben
            # die alten Karten SICHTBAR und lagen ueber den neuen (beim
            # Rendern gesehen). `setParent(None)` nimmt sie sofort vom Schirm.
            k.setParent(None)
            k.deleteLater()
        self._karten = list(karten)
        self._anordnen(neu=True)

    def lage(self):
        """[(Reihe, Spalte)] je Karte, aus dem echten Layout."""
        out = []
        for k in self._karten:
            i = self._gitter.indexOf(k)
            if i >= 0:
                r, c, _rs, _cs = self._gitter.getItemPosition(i)
                out.append((r, c))
            else:
                out.append(None)
        return out

    def _anordnen(self, neu=False):
        n = self.spalten()
        if n == self._spalten and not neu:
            return
        self._spalten = n
        self._abhaengen()
        for i, k in enumerate(self._karten):
            self._gitter.addWidget(k, i // n, i % n, Qt.AlignTop)
        # Unter der letzten Reihe faengt eine Stretch-Reihe den Rest ab,
        # rechts von der letzten Spalte nichts (aktive Spalten teilen sich
        # die Breite gleichmaessig).
        reihen = (len(self._karten) + n - 1) // n
        for r in range(max(self._gitter.rowCount(), reihen + 1)):
            self._gitter.setRowStretch(r, 1 if r == reihen else 0)
        for c in range(max(self._gitter.columnCount(), n)):
            self._gitter.setColumnStretch(c, 1 if c < n else 0)

    def resizeEvent(self, ev):
        super().resizeEvent(ev)
        self._anordnen()


class BauplanTabs:
    def _inv_alle_besten(self):
        """"Best Decryptor for all Blueprints" (Nutzer 26.09.2026).

        NACHEINANDER, nicht gleichzeitig: die Rangliste jeder Karte rechnet den
        GANZEN Plan (Materialkosten haengen an der ME aller erfundenen Teile).
        Nach jeder Wahl stehen deshalb die neuen Decryptoren schon in
        `_bd_opts`, die naechste Karte rechnet damit weiter. Am Ende EIN
        Neuaufbau statt einer je Karte (jede Combo-Aenderung loeste sonst
        einen eigenen aus - bei 5 Karten 5 volle Rechnungen)."""
        from PySide6.QtWidgets import QApplication as _QA
        _rang = dict(getattr(self, "_bd_inv_rang", None) or {})
        _alle = len(getattr(self, "_bd_inv_combos", None) or {})
        _lbl = getattr(self, "_bd_inv_alle_lbl", None)
        _geaendert = 0
        _QA.setOverrideCursor(Qt.WaitCursor)
        try:
            for _bp, (_fn, _dl) in _rang.items():
                try:
                    _ranked = _fn()
                except Exception as _e:
                    self._log_exception("Best Decryptor for all", str(_e))
                    continue
                if not _ranked:
                    continue
                _name = _ranked[0]["name"]
                _dv = next((v for n, v in _dl if n == _name), None)
                if _dv is None:
                    continue
                if self._bd_decryptor_map.get(_bp) != _name:
                    _geaendert += 1
                self._bd_dec_bestaetigt = set(getattr(self, "_bd_dec_bestaetigt", None) or ())
                self._bd_dec_bestaetigt.add(int(_bp))
                self._bd_decryptor_map[_bp] = _name
                self._bd_opts.setdefault("inv_decryptor_map", {})[_bp] = _dv
        finally:
            _QA.restoreOverrideCursor()
        _cb = getattr(self, "_bd_full_rebuild", None)
        if _cb is not None:
            _cb()
        # RUECKMELDUNG (Nutzer 26.09.2026: "der Knopf macht nichts"). Bei ihm
        # stand die einzige erfundene Karte schon auf ihrem besten Decryptor,
        # die andere hatte "Own BPC" - also aenderte sich sichtbar nichts. Jetzt
        # sagt die Seitenleiste, was geschah: gewechselt / schon beste /
        # uebersprungen. Jede Blaupause bekommt IHREN besten Decryptor.
        if _lbl is not None:
            try:
                _lbl.setText(t(
                    "Checked {n} blueprint(s): {chg} changed, {same} already on "
                    "their best decryptor, {skip} skipped (Own BPC).").format(
                        n=len(_rang), chg=_geaendert,
                        same=len(_rang) - _geaendert,
                        skip=max(0, _alle - len(_rang))))
                _lbl.show()
            except RuntimeError:
                pass
        return _geaendert

    # REIHENFOLGE DER BAU-STUFEN in der Blaupausen-Warnzeile - dieselbe wie
    # `_stage_order` im Blaupausen-Reiter (main_window). Die Werte sind die
    # SCHLUESSEL, die dort vergeben werden; angezeigt wird uebersetzt.
    # de_scan4: aus - Stufen-SCHLUESSEL, Anzeige via _kategorie_anzeige
    # de_scan2: aus
    _BP_STUFEN_FOLGE = ("Endprodukt", "Komponente", "H\u00fcllen", "Fuel", "Tools",
                        "Reaktion \u00b7 Stufe 1", "Reaktion \u00b7 Stufe 2",
                        "Reaktion")
    # de_scan2: an
    # de_scan4: an

    @classmethod
    def _bp_stufen_liste(cls, by_stage):
        """Aufschluesselung "Stufe Anzahl" fuer die Blaupausen-Warnzeile.

        SITZUNG 17 (Nutzer: "warum sollte man sie nicht korrigieren?"): die
        alte Fassung kannte nur "Endprodukt"/"Komponente"/"Reaktion". Die
        Stufen heissen laengst "Reaktion \u00b7 Stufe 1/2", "H\u00fcllen", "Fuel",
        "Tools" - die fielen STILL heraus. Nachgestellt: 7 fehlende
        Blaupausen, angezeigt wurde "Components 3".

        Unbekannte Stufen werden HINTEN ANGEHAENGT statt weggelassen (Regel 3:
        lieber ein Eintrag zu viel als ein verschwiegener) - kommt je eine neue
        Stufe dazu, steht sie da, auch bevor jemand die Reihenfolge pflegt.
        """
        folge = [s for s in cls._BP_STUFEN_FOLGE if (by_stage or {}).get(s)]
        folge += sorted(s for s in (by_stage or {})
                        if by_stage.get(s) and s not in cls._BP_STUFEN_FOLGE)
        # Doppelpunkt: "Reaktion \u00b7 Stufe 1: 2" - ohne ihn las sich die Stufe
        # und die Anzahl wie eine Zahl ("Stufe 1 2").
        return [f"{cls._kategorie_anzeige(s)}: {by_stage[s]}" for s in folge]

    def _ist_fuel_block(self, tid, groups, reaction_products):
        """Ist dieses Item ein Fuel Block? EINE Wahrheit (Arbeitsregel 9):
        derselbe Klassifizierer wie im Materialien-Baum und im Blueprints-Tab
        (`_category_key` -> "fuel_blocks"), nicht ein zweiter Gruppennamen-
        Vergleich, der davon abdriften kann.

        Gebraucht fuer die eigene Runplaner-Stufe VOR den Reaktionen: Fuel
        Blocks sind FERTIGUNGS-Jobs und landeten deshalb bei den Komponenten -
        also hinter den Reaktionen, die sie verbrauchen (Nutzer, Sitzung 8:
        "Oxygen Fuel Block müsste ich vor Reactions bauen").
        """
        if tid in (reaction_products or set()):
            return False
        try:
            return self._category_key(
                tid, (groups or {}).get(tid, ""), False) == "fuel_blocks"
        except Exception as _err:
            self._log_exception("Runplaner: Fuel-Erkennung", str(_err))
            return False
    # REGLER "INVENTION JOBS AT ONCE" BLEIBT STEHEN (emm328, Nutzer 02.10.2026:
    # "Regler nach rechts geschoben, Plan zugemacht und wieder aufgemacht, dann
    # waren die Regler wieder ganz links - es soll speichern wo es war. Ein
    # neuer Plan startet aber immer ganz links"). Gemerkt je Blaupause im
    # gespeicherten Plan ("inv_split"), SOFORT beim Ziehen - wie die Felder je
    # Ende (`_multi_je_ende_merken`): beim eingefrorenen Plan drueckt man
    # "Save" nicht. Der Regler aendert nur die Aufteilung der Kopien, nie die
    # Einkaufsliste - darum darf er auch am eingefrorenen Plan geschrieben werden.
    @staticmethod
    def _inv_split_aus_plan(p):
        out = {}
        for k, v in ((p or {}).get("inv_split") or {}).items():
            try:
                if int(v) >= 1:
                    out[int(k)] = int(v)
            except (TypeError, ValueError):
                continue
        return out

    def _inv_split_fuer_plan(self):
        """Regler-Stand als speicherbares {"bp_id": Kopien}."""
        d = getattr(self, "_bd_inv_split", None)
        return {str(int(k)): int(v) for k, v in
                (d if isinstance(d, dict) else {}).items()}

    # ENTPRELLT (emm330, Nutzer 02.10.2026: "der Regler laeuft nicht mehr
    # fluessig, fuehlt sich laggy an"). emm328 schrieb bei JEDEM Reglerschritt
    # die ganze settings.json: `save_settings_async` erzeugt den JSON-Text im
    # UI-Faden (json.dumps mit indent ohne C-Beschleuniger, emm239 gemessen
    # 4 x 0,77 s). Jetzt: Stand sofort im Speicher, geschrieben erst 800 ms
    # nach der letzten Bewegung - einmal je Zug statt je Schritt.
    INV_SPLIT_MERK_MS = 800

    def _inv_split_merken_spaeter(self):
        tm = getattr(self, "_inv_split_timer", None)
        if tm is None:
            tm = QTimer(self)
            tm.setSingleShot(True)
            tm.timeout.connect(lambda: self._inv_split_merken())
            self._inv_split_timer = tm
        tm.start(self.INV_SPLIT_MERK_MS)

    def _inv_split_merken(self):
        """Regler-Stand in den gespeicherten Plan schreiben. Ungespeichert ->
        nichts (kommt mit "Save build plan"). True = geschrieben."""
        pid = getattr(self, "_bd_open_plan_id", None)
        if pid is None:
            return False
        stand = self._inv_split_fuer_plan()
        for p in (self.settings.get("bau_saved_plans", []) or []):
            if p.get("id") != pid:
                continue
            if p.get("inv_split") != stand:
                p["inv_split"] = stand
                from .. import config as _cfg
                _cfg.save_settings_async(self.settings)
            return True
        return False

    # ------------------------------------------------------------------
    # INDUSTRY JOBS (emm327, Discord-Wunsch ueber den Nutzer 01.10.2026:
    # "wo man sieht welcher Charakter was baut ... welche Slots belegt hat mit
    # was und wie lange"; Ort laut Nutzer: neuer Knopf in der Leiste unter
    # PRODUCTION). Nur Anzeige - liest ESI, schreibt nichts in die Settings.
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # BUILD FROM STOCK (emm436, Discord HashtagMoDSucks "Runs from stock";
    # Nutzer-Entscheide: eigene Seite in der PRODUCTION-Leiste, Vorstufen
    # duerfen aus dem Hangar gebaut werden, Material gesperrter Plaene
    # zaehlt NICHT). Je eigener Blaupause: wie viele Runs gibt der Hangar
    # her. Die Rechnung ist rein (`aus_bestand`), hier nur Abruf + Anzeige.
    # ------------------------------------------------------------------
    # + "vs. 90d avg" (emm499): Sell-Preis gegen den 90-Tage-Schnitt der
    # Markthistorie - NEUTRAL (Scam-Warnlampe), nie gefaerbt.
    BFS_SPALTEN = ("Item", "Runs", "Units", "Limited by", "Builds sub-steps",
                   "Profit/unit", "Profit total", "vs. 90d avg")

    def _bfs_seite_bauen(self):
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(8)
        kopf = QHBoxLayout(); kopf.setSpacing(10)
        titel = QLabel(t("BUILD FROM STOCK (BETA)"))
        titel.setStyleSheet(f"font-size:13px; letter-spacing:2px; font-weight:800; "
                            f"color:{theme.GREEN};")
        # Erklaerung NUR als Tooltip (Nutzer: Texte "nerven", emm391/emm404).
        titel.setToolTip(t(
            "How many runs of each of your own blueprints the material in your "
            "hangar allows - the same stock rules as the build plan (structures, "
            "characters, corp hangar). Material reserved by locked build plans "
            "does not count. Missing components may be built from stock too, if "
            "you own their blueprint. Rounded up per run, only your blueprint "
            "ME - never more runs than really work."))
        kopf.addWidget(titel)
        kopf.addStretch()
        self._bfs_nur_cb = QCheckBox(t("Only buildable"))
        self._bfs_nur_cb.setChecked(bool(self.settings.get("bfs_nur_baubar", True)))
        self._bfs_nur_cb.setIcon(icons.icon("hammer"))   # b55: Bedienelemente tragen ein Symbol
        self._bfs_nur_cb.toggled.connect(lambda _on: self._bfs_filter_umschalten())
        kopf.addWidget(self._bfs_nur_cb)
        self._bfs_refresh_btn = QPushButton(t("Refresh"))
        self._bfs_refresh_btn.setIcon(icons.icon("refresh"))
        self._bfs_refresh_btn.setStyleSheet(theme.amber_rahmen_knopf())
        self._bfs_refresh_btn.clicked.connect(lambda: self._bfs_laden())
        kopf.addWidget(self._bfs_refresh_btn)
        v.addLayout(kopf)
        # FILTERLEISTE WIE MY BLUEPRINTS (emm489, Nutzer: "die selben Filter
        # und Dropdown Einstellungen wie My Blueprints Tab"). Gefiltert wird
        # ueber DIESELBEN reinen Helfer (industry.bp_kategorie_passt,
        # RACE_NAMES, Tech-Mengen wie bp_myb_tech) - kein Nachbau. Bewusst
        # NICHT uebernommen: BPO/BPC, Show missing und Inventable T2 (diese
        # Seite kennt weder fehlende noch erfindbare Zeilen, Kopien sind je
        # Item zusammengefasst) und der Charakter-Filter (der Hangar ist
        # gemeinsam, jede Zeile rechnet ueber alle Charaktere).
        f1 = QHBoxLayout(); f1.setSpacing(10)
        _sl = QLabel(t("Show:"))
        _sl.setStyleSheet(f"color:{theme.MUTED}; font-weight:700;")
        f1.addWidget(_sl)
        self._bfs_cb_end = QCheckBox(t("End products"))
        self._bfs_cb_end.setIcon(icons.icon("target"))
        self._bfs_cb_comp = QCheckBox(t("Components"))
        self._bfs_cb_comp.setIcon(icons.icon("wrench"))
        self._bfs_cb_react = QCheckBox(t("Reactions"))
        self._bfs_cb_react.setIcon(icons.icon("flask"))
        self._bfs_cb_profit = QCheckBox(t("profitable only"))
        self._bfs_cb_profit.setIcon(icons.icon("coins"))
        for _cb in (self._bfs_cb_end, self._bfs_cb_comp, self._bfs_cb_react):
            _cb.setChecked(True)
        self._bfs_cb_profit.setChecked(False)
        for _cb in (self._bfs_cb_end, self._bfs_cb_comp,
                    self._bfs_cb_react, self._bfs_cb_profit):
            _cb.toggled.connect(lambda _on: self._bfs_zeichnen())
            f1.addWidget(_cb)
        f1.addStretch()
        _su = QLabel(t("Search:"))
        _su.setStyleSheet(f"color:{theme.MUTED}; font-weight:700;")
        f1.addWidget(_su)
        self._bfs_suche = QLineEdit()
        self._bfs_suche.setPlaceholderText(t("Item name …"))
        # DARF SCHRUMPFEN (emm500, b66 auf seinem Windows rot: Seite 1180 px,
        # weil die Texte dort ~1,4-1,6x breiter messen und das feste
        # 220-px-Feld obendrauf kam). Breit, wenn Platz ist; unter Druck
        # gibt das Feld nach, nie die Filter-Haken (deren Text ist fest).
        self._bfs_suche.setMinimumWidth(120)
        self._bfs_suche.setMaximumWidth(220)
        self._bfs_suche.setClearButtonEnabled(True)
        self._bfs_suche.textChanged.connect(lambda _tx: self._bfs_zeichnen())
        f1.addWidget(self._bfs_suche)
        v.addLayout(f1)
        f2 = QHBoxLayout(); f2.setSpacing(10)
        _cl = QLabel(t("Category:"))
        _cl.setStyleSheet(f"color:{theme.MUTED}; font-weight:700;")
        f2.addWidget(_cl)
        self._bfs_cat = QComboBox(); self._bfs_cat.setMinimumWidth(160)
        self._bfs_cat.addItem(t("All categories"), None)
        self._bfs_cat.currentIndexChanged.connect(
            lambda _i: self._bfs_zeichnen())
        f2.addWidget(self._bfs_cat)
        self._bfs_tech = QComboBox(); self._bfs_tech.setMinimumWidth(120)
        for _lab, _mset in [(t("All tech levels"), None), ("Tech I", {0, 1}),
                            ("Tech II", {2}), ("Tech III", {14})]:
            self._bfs_tech.addItem(_lab, _mset)
        self._bfs_tech.currentIndexChanged.connect(
            lambda _i: self._bfs_zeichnen())
        f2.addWidget(self._bfs_tech)
        self._bfs_race = QComboBox(); self._bfs_race.setMinimumWidth(110)
        self._bfs_race.addItem(t("All races"), None)
        for _rid, _rname in sorted(industry.RACE_NAMES.items(),
                                   key=lambda x: x[1]):
            self._bfs_race.addItem(_rname, _rid)
        self._bfs_race.currentIndexChanged.connect(
            lambda _i: self._bfs_zeichnen())
        f2.addWidget(self._bfs_race)
        f2.addStretch()
        v.addLayout(f2)
        self._bfs_stand_lbl = QLabel("")
        self._bfs_stand_lbl.setObjectName("Muted")
        self._bfs_stand_lbl.setWordWrap(True)
        v.addWidget(self._bfs_stand_lbl)
        self._bfs_warn_lbl = QLabel("")
        self._bfs_warn_lbl.setWordWrap(True)
        self._bfs_warn_lbl.setStyleSheet(f"color:{theme.AMBER};")
        self._bfs_warn_lbl.hide()
        v.addWidget(self._bfs_warn_lbl)
        tbl = QTableWidget(0, len(self.BFS_SPALTEN))
        tbl.setHorizontalHeaderLabels([t(s) for s in self.BFS_SPALTEN])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.setAlternatingRowColors(True)
        from PySide6.QtWidgets import QHeaderView
        tbl.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)
        tbl.horizontalHeader().setStretchLastSection(True)
        # "vs. 90d avg" steht VISUELL vor Profit total (emm500, Nutzer:
        # "die ist ca 60% zu breit"): stretchLastSection dehnt die letzte
        # SICHTBARE Spalte - seit emm499 war das die schmale Trend-Spalte,
        # die damit allen Restplatz bekam. Jetzt dehnt wieder Profit total
        # (letzte visuelle Spalte), die Trend-Spalte behaelt ihre
        # Inhaltsbreite. Logische Indizes unveraendert (Spalte 7 = Trend).
        _hb500 = tbl.horizontalHeader()
        _hb500.moveSection(_hb500.visualIndex(7), _hb500.visualIndex(6))
        tbl.horizontalHeaderItem(5).setToolTip(t(
            "From My Blueprints (materials valued at market price). Load My "
            "Blueprints once to see it."))
        tbl.horizontalHeaderItem(7).setToolTip(t(
            "Current sell price vs. the 90-day average of the market "
            "history. Deliberately NOT colored: a price far above the "
            "average can mean market manipulation (scam) rather than "
            "profit. ? = history not loaded yet."))
        kopier_menue(tbl, lambda pos: self._bfs_menue(pos))
        self._bfs_table = tbl
        v.addWidget(tbl, 1)
        self._bfs_daten = None
        self._bfs_stand_ts = 0.0
        self._bfs_laeuft = False
        # LEER-HINWEIS IN DER TABELLE (emm493, Nutzer: "genau am selben Ort
        # wie bei My blueprints den Knopf machen, auch blinken wenn nicht
        # geladen"): dieselbe Infrastruktur (_leerhinweis) und derselbe Look
        # (_bp_leer_stil) wie der Knopf in der leeren bp_table. Was der
        # Hinweis sagt, entscheidet _bfs_leer_zustand bei jedem Einblenden.
        try:
            _box = self._leerhinweis(
                tbl, t("Loading blueprints and stock …"),
                knopf_text=t("Load blueprints"),
                aktion=self._bfs_mb_laden,
                symbol=icons.icon("blueprint"),
                zustand=self._bfs_leer_zustand)
            self._bfs_leer_box = _box
            self._bfs_leer_knopf = getattr(_box, "_knopf", None)
            if self._bfs_leer_knopf is not None:
                self._bfs_leer_an = False
                self._bp_leer_stil(self._bfs_leer_knopf, False)
                _btmr = QTimer(self)
                _btmr.setInterval(700)
                _btmr.timeout.connect(lambda: self._bfs_leer_blink_schritt())
                _btmr.start()
                self._bfs_leer_timer = _btmr
        except Exception as _lh:               # pragma: no cover
            self._log_exception("Leerhinweis Build from stock", str(_lh))
        return page

    def _bfs_seite_gezeigt(self):
        """Aus _bau_nav(5): beim ersten Zeigen und ab 10 min Alter laden."""
        import time as _t
        if self._bfs_daten is None or _t.time() - self._bfs_stand_ts > 600:
            self._bfs_laden()

    def _bfs_leer_zustand(self):
        """Was der Leer-Hinweis der BFS-Tabelle sagt (emm493) ->
        (titel, knopf_text, symbolname, aktion). Der Knopf kommt IMMER,
        solange My Blueprints nicht geladen sind (Nutzer-Screenshot
        emm494, Tech-II-Filter + "profitable only" AUS: "da ist kein load
        blueprints button") - nicht nur, wenn der Gewinn-Filter der Grund
        der Leere ist."""
        if getattr(self, "_bfs_laeuft", False) or \
                getattr(self, "_bfs_daten", None) is None:
            return (t("Loading blueprints and stock …"), None, None, None)
        econ = (getattr(self, "_bp_econ_stand", None) or {}).get("profit_by_bp")
        if econ is None:
            return (t("Profit unknown - load My Blueprints first."),
                    t("Load blueprints"), "blueprint", self._bfs_mb_laden)
        return (t("Nothing matches the filters."), None, None, None)

    def _bfs_mb_laden(self):
        """Knopf im Leer-Hinweis: My Blueprints nachladen (emm371-Mechanik:
        Rueckruf ueber `_bp_geladen_rueckrufe`), danach neu zeichnen - der
        Gewinn-Filter sieht dann Zahlen."""
        def _fertig(_ok, _msg=""):
            try:
                self._bfs_zeichnen()
            except Exception as _e:
                self._log_exception("Build from stock: Rueckruf", str(_e))
        self._bp_geladen_rueckrufe = (
            list(getattr(self, "_bp_geladen_rueckrufe", None) or []) + [_fertig])
        self._reload_my_blueprints(overlay=False)

    def _bfs_leer_blink_schritt(self):
        """Blinkt den Leer-Knopf, solange er der naechste Handgriff ist.
        BEWUSST NICHT ueber isVisible (in nie gezeigten Fenstern immer False,
        CLAUDE.md-Falle): leer UND der Zustand will einen Knopf = blinken.
        Stil ueber die EINE Stelle `_bp_leer_stil` - exakt der Look des
        My-Blueprints-Knopfs."""
        btn = getattr(self, "_bfs_leer_knopf", None)
        tbl = getattr(self, "_bfs_table", None)
        if btn is None or tbl is None:
            return
        try:
            if tbl.rowCount() == 0 and bool(self._bfs_leer_zustand()[1]):
                self._bfs_leer_an = not getattr(self, "_bfs_leer_an", False)
            else:
                self._bfs_leer_an = False
            self._bp_leer_stil(btn, self._bfs_leer_an)
        except RuntimeError:                   # Knopf schon geloescht
            pass

    def _bfs_bestand_holen(self, client_id, chars):
        """Freier Hangar-Bestand nach den REGELN DES BAUPLANS (Strukturen /
        Scope, Rollen-Pool, Hangar der Corp) - ohne Pipeline (fertige, nicht
        abgeholte Jobs zaehlen nicht: lieber zu wenig Runs, Regel 3).
        -> (bestand, kein_ort, failed)."""
        s = self.settings
        scope = s.get("bau_stock_scope") or "structures"   # "plan" = wie Strukturen
        # EINE Stelle fuer "welche Struktur ist verlinkt" (emm490) - dieselbe
        # Liste laesst den Strukturen-Knopf in der Leiste blinken.
        from .mw_helpers import verlinkte_struktur_ids
        locs = verlinkte_struktur_ids(s)
        if scope != "all" and not locs:
            return {}, True, []
        ids = self._runplan_pool_char_ids(s)
        pool = [c for c in chars if c["character_id"] in ids] if ids else list(chars)
        agg, failed = {}, []
        for ch in pool:
            cid = ch["character_id"]
            try:
                if scope == "all":
                    a = esi.fetch_assets(client_id, cid)
                else:
                    a = esi.assets_at_locations(client_id, cid, locs)
                for tid, q in (a or {}).items():
                    agg[int(tid)] = agg.get(int(tid), 0) + int(q)
            except Exception:
                failed.append(ch.get("character_name") or str(cid))
        try:
            _c = self._corp_bau_daten(client_id, chars,
                                      None if scope == "all" else locs)
            for tid, q in (_c.get("summe") or {}).items():
                agg[int(tid)] = agg.get(int(tid), 0) + int(q)
            failed.extend(_c.get("failed") or [])
        except Exception:
            failed.append("Corp")
        return agg, False, failed

    def _bfs_laden(self):
        if getattr(self, "_bfs_laeuft", False):
            return
        client_id = self.settings.get("client_id")
        chars = store.list_characters()
        if not client_id or not chars:
            self._bfs_stand_lbl.setText(t("No characters linked."))
            return

        def job():
            from .. import aus_bestand
            import time as _t
            owned = self._bd_fetch_all_owned_blueprints(force=True, merken=False) or []
            rec = industry.recipes_cached()
            bestand, kein_ort, failed = self._bfs_bestand_holen(client_id, chars)
            try:
                reserv = self._reserved_by_other_plans(self.settings, None)[0] or {}
            except Exception:
                reserv = {}
            frei = {}
            for tid, q in bestand.items():
                r = int(q) - int(reserv.get(int(tid), 0) or 0)
                if r > 0:
                    frei[int(tid)] = r
            zeilen = aus_bestand.bestand_liste(owned, rec.product_to_bp,
                                               rec.bp_materials, frei)
            # FILTER-METADATEN je Zeile (emm489): Kategorie/Gruppe/Tech aus
            # derselben Quelle wie My Blueprints (item_category_map), Rasse
            # aus item_race_map, die Show-Einteilung mit DERSELBEN Regel wie
            # dort (classify: Reaktion -> Gruppenname "Component"/
            # "Construction" -> sonst Endprodukt).
            catmap = industry.item_category_map() or {}
            rmap = industry.item_race_map() or {}
            try:
                rig_ids = set(industry.rig_gruppen() or ())
            except Exception:
                rig_ids = set()
            try:
                gnamen = industry.group_names(
                    [z["produkt"] for z in zeilen]) or {}
            except Exception:
                gnamen = {}
            for z in zeilen:
                _tid = int(z["produkt"])
                _cgm = catmap.get(_tid) or (None, None, None)
                z["cat"], z["grp"], z["meta"] = _cgm[0], _cgm[1], _cgm[2]
                z["race"] = rmap.get(_tid)
                if _tid in (getattr(rec, "reaction_products", None)
                            or set()):
                    z["art"] = "reaction"
                else:
                    _gn = str(gnamen.get(_tid) or "")
                    z["art"] = ("component"
                                if ("Component" in _gn or "Construction" in _gn)
                                else "end")
            tids = set()
            for z in zeilen:
                tids.add(z["produkt"])
                if z["grenze"]:
                    tids.add(int(z["grenze"]))
                tids.update(z["baut"])
            namen = dict(store.cached_names(list(tids)) or {}) if tids else {}
            fehlt = [x for x in tids if x not in namen]
            if fehlt:
                try:
                    namen.update(esi.resolve_names(fehlt) or {})
                except Exception:
                    pass
            n_res = sum(1 for tid in bestand if int(reserv.get(int(tid), 0) or 0) > 0)
            # PREIS-TREND (emm499): dieselbe lokale Historie wie Sold/day.
            try:
                trend = self._preis_trend_je_typ(
                    [int(z["produkt"]) for z in zeilen])
            except Exception:
                trend = {}
            return {"zeilen": zeilen, "namen": namen, "kein_ort": kein_ort,
                    "failed": failed, "n_res": n_res, "rig_ids": rig_ids,
                    "trend": trend, "ts": _t.time()}

        def done(res):
            self._bfs_laeuft = False
            self._bfs_daten = res
            self._bfs_stand_ts = res.get("ts") or 0.0
            self._bfs_cat_fuellen()
            self._bfs_zeichnen()

        def fail(_err):
            self._bfs_laeuft = False
            self._bfs_stand_lbl.setText(t("Loading failed."))

        self._bfs_laeuft = True
        self._bfs_stand_lbl.setText(t("Loading blueprints and stock …"))
        self._run(Worker(job), done, fail, overlay=False)

    def _bfs_filter_umschalten(self):
        self.settings["bfs_nur_baubar"] = bool(self._bfs_nur_cb.isChecked())
        try:
            config.save_settings_async(self.settings)
        except Exception:
            pass
        self._bfs_zeichnen()

    def _bfs_cat_fuellen(self):
        """Kategorie-Dropdown aus den eigenen Zeilen - dieselbe Regel wie
        My Blueprints (`industry.bp_kategorien_zeigen`, emm489)."""
        cb = getattr(self, "_bfs_cat", None)
        if cb is None:
            return
        zeilen = [(z.get("cat"), z.get("grp"))
                  for z in ((self._bfs_daten or {}).get("zeilen") or [])]
        try:
            opts = industry.bp_kategorien_zeigen(
                industry.category_options(), zeilen or None,
                (self._bfs_daten or {}).get("rig_ids"), t("Rigs"))
        except Exception:
            opts = []
        alt = cb.currentData()
        cb.blockSignals(True)
        cb.clear()
        cb.addItem(t("All categories"), None)
        for _cid, _nm in opts:
            cb.addItem(str(_nm), _cid)
        ix = cb.findData(alt) if alt is not None else 0
        cb.setCurrentIndex(ix if ix >= 0 else 0)
        cb.blockSignals(False)

    def _bfs_breiten_setzen(self):
        """Spaltenbreiten EINMAL beim ersten Fuellen (danach bleiben vom
        Nutzer gezogene Breiten stehen).

        BUILDS SUB-STEPS IST GEDECKELT (emm490, Nutzer: "Build substeps ist
        viel zu breit, man sieht die anderen Columns nicht" und, nach dem
        ersten Wurf, "immer noch 50% zu breit"): ein blosses
        `resizeColumnsToContents()` gab der Spalte die Breite ihrer
        LAENGSTEN Zeile ("2x Hydrogen Fuel Block, 5x Oxygen Fuel Block,
        12x Silicon Diborite, 12x Vanadium Hafnite") - Profit/unit und
        Profit total standen damit rechts ausserhalb des Bildes.

        Der Deckel ist KEINE Pixelzahl (die waere auf seinem Windows
        falsch - dieselben Widgets sind dort rund 1,6x breiter, b66),
        sondern ein ANTEIL der Tabelle: hoechstens EIN DRITTEL. Die
        Unterschritte sind Nebeninfo; was uebrig bleibt, bekommt die
        Spalte ITEM (dort stehen die langen Namen). Qt kuerzt den
        Zelltext dann mit "…", die volle Liste steht im Tooltip."""
        tbl = self._bfs_table
        tbl.resizeColumnsToContents()
        fm = tbl.fontMetrics()
        sub_spalte, name_spalte = 4, 0
        breit = tbl.viewport().width()

        def _kopf_w(i):
            kopf = tbl.horizontalHeaderItem(i)
            return (fm.horizontalAdvance(kopf.text()) + 34) if kopf else 0
        for i in range(tbl.columnCount()):
            tbl.setColumnWidth(i, max(tbl.columnWidth(i) + 22, _kopf_w(i), 70))
        tbl.setColumnWidth(sub_spalte,
                           max(_kopf_w(sub_spalte),
                               min(tbl.columnWidth(sub_spalte), breit // 3)))
        belegt = sum(tbl.columnWidth(i) for i in range(tbl.columnCount())
                     if i != name_spalte)
        tbl.setColumnWidth(name_spalte,
                           max(tbl.columnWidth(name_spalte), breit - belegt))

    def _bfs_zeichnen(self):
        res = self._bfs_daten or {}
        tbl = self._bfs_table
        namen = res.get("namen") or {}
        nur = self._bfs_nur_cb.isChecked()
        econ = (getattr(self, "_bp_econ_stand", None) or {}).get("profit_by_bp")
        zeilen = list(res.get("zeilen") or [])
        baubar = [z for z in zeilen if z["runs"] > 0]
        zeigen = baubar if nur else zeilen

        def _name(tid):
            return namen.get(int(tid)) or f"#{tid}"

        # FILTER WIE MY BLUEPRINTS (emm489) - dieselben Helfer, dieselbe
        # Bedeutung. `art` / `cat` / `meta` / `race` haengen an der Zeile
        # (im Lade-Job gerechnet).
        show489 = {"end": self._bfs_cb_end.isChecked(),
                   "component": self._bfs_cb_comp.isChecked(),
                   "reaction": self._bfs_cb_react.isChecked()}
        only_profit489 = self._bfs_cb_profit.isChecked()
        want_cat489 = self._bfs_cat.currentData()
        want_meta489 = self._bfs_tech.currentData()
        want_race489 = self._bfs_race.currentData()
        such489 = self._bfs_suche.text().strip().lower()
        rig_ids489 = res.get("rig_ids") or set()

        def _passt489(z):
            if not show489.get(z.get("art") or "end", True):
                return False
            if only_profit489:
                _e = (econ or {}).get(z["bp"]) or {}
                if not ((_e.get("profit") or 0) > 0):
                    return False
            if not industry.bp_kategorie_passt(want_cat489, z.get("cat"),
                                               z.get("grp"), rig_ids489):
                return False
            if want_meta489 is not None and \
                    int(z.get("meta") or 0) not in want_meta489:
                return False
            if want_race489 is not None and z.get("race") != want_race489:
                return False
            if such489 and such489 not in _name(z["produkt"]).lower():
                return False
            return True
        zeigen = [z for z in zeigen if _passt489(z)]

        tbl.setSortingEnabled(False)
        tbl.setRowCount(len(zeigen))
        for r, z in enumerate(zeigen):
            nm = _name(z["produkt"])
            it = QTableWidgetItem(nm)
            it.setData(Qt.UserRole, (z["produkt"], z["units"], nm))
            tbl.setItem(r, 0, it)
            tbl.setItem(r, 1, NumericItem(f"{z['runs']:,}".replace(",", "'"), z["runs"]))
            tbl.setItem(r, 2, NumericItem(f"{z['units']:,}".replace(",", "'"), z["units"]))
            g = z.get("grenze")
            if g is None:
                gt = "—"
            elif int(g) == int(z["produkt"]):
                gt = t("blueprint copy runs")
            else:
                gt = _name(g)
            tbl.setItem(r, 3, QTableWidgetItem(gt))
            baut = ", ".join(f"{n}× {_name(tid)}"
                             for tid, n in sorted(z["baut"].items(),
                                                  key=lambda kv: _name(kv[0])))
            bi = QTableWidgetItem(baut or "—")
            if baut:
                # VOLLE LISTE IN DEN TOOLTIP (emm490): die Spalte ist
                # gedeckelt, lange Listen kuerzt Qt mit "…" - ohne den
                # Tooltip waere der Rest nicht mehr lesbar.
                bi.setToolTip(baut + "\n" + t(
                    "Runs of these components are built from stock first."))
            tbl.setItem(r, 4, bi)
            e = (econ or {}).get(z["bp"]) or {}
            pu = e.get("profit")
            if pu is None:
                tbl.setItem(r, 5, NumericItem("—", None))
                tbl.setItem(r, 6, NumericItem("—", None))
            else:
                ges = float(pu) * z["units"]
                for c, w in ((5, float(pu)), (6, ges)):
                    ni = NumericItem(isk(w, suffix=False), w)
                    ni.setForeground(QBrush(QColor(theme.GREEN if w >= 0 else theme.RED)))
                    tbl.setItem(r, c, ni)
            # vs. 90d avg (emm499): Sell gegen den 90-Tage-Schnitt - NEUTRAL
            # weiss, bewusst NICHT gefaerbt (Scam-Warnlampe). b186/b198-
            # Fixtures setzen _bfs_daten ohne "trend" -> res.get tolerieren.
            from .mw_helpers import preis_abweichung as _pabw499
            _tr499 = (res.get("trend") or {}).get(int(z["produkt"]))
            _txt499, _val499 = self._trend_pct_zelle(
                _pabw499(e.get("sell"), (_tr499 or {}).get("o90")), True)
            _ti499 = NumericItem(_txt499, _val499)
            if _tr499:
                def _tt499(w):
                    return (f"{w:+,.0f} %".replace(",", "'")
                            if w is not None else "?")
                def _ts499(w):
                    return isk(w, suffix=False) if w is not None else "?"
                _ti499.setToolTip(t(
                    "Current sell price vs. the 90-day average "
                    "of the market history.\n"
                    "Ø 7d: {o7} · Ø 30d: {o30} "
                    "· Ø 90d: {o90}\n"
                    "Change: 7d {d7} · 30d {d30} "
                    "· 90d {d90}").format(
                    o7=_ts499(_tr499.get("o7")),
                    o30=_ts499(_tr499.get("o30")),
                    o90=_ts499(_tr499.get("o90")),
                    d7=_tt499(_tr499.get("d7")),
                    d30=_tt499(_tr499.get("d30")),
                    d90=_tt499(_tr499.get("d90"))))
            tbl.setItem(r, 7, _ti499)
            for c in (1, 2, 5, 6, 7):
                tbl.item(r, c).setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        tbl.setSortingEnabled(True)
        if not getattr(self, "_bfs_sortiert", False):
            tbl.sortItems(2, Qt.DescendingOrder)
            self._bfs_sortiert = True
        if not getattr(self, "_bfs_breiten_gesetzt", False) and zeigen:
            self._bfs_breiten_setzen()
            self._bfs_breiten_gesetzt = True
        txt = t("{n} blueprints · {k} buildable from stock").format(
            n=len(zeilen), k=len(baubar)) \
            + "  ·  " + t("{n} shown").format(n=len(zeigen))
        if res.get("n_res"):
            txt += " · " + t("{n} item types partly reserved by locked plans "
                             "(not counted)").format(n=res["n_res"])
        if econ is None:
            txt += " · " + t("profit: load My Blueprints first")
        self._bfs_stand_lbl.setText(txt)
        warn = []
        if res.get("kein_ort"):
            warn.append(t("⚠ No build structure linked - no stock counted. Link "
                          "one under Structures or set stock to Everywhere."))
        if res.get("failed"):
            warn.append(t("⚠ Could not read: {names}").format(
                names=", ".join(res["failed"])))
        self._bfs_warn_lbl.setText("\n".join(warn))
        self._bfs_warn_lbl.setVisible(bool(warn))
        # LEER-HINWEIS NACHSTELLEN (emm493): bleibt die Tabelle bei 0 Zeilen,
        # feuern die Model-Signale nicht - ein umgelegter Filter aendert aber
        # den Zustand (Knopf rein/raus). Deshalb hier ausdruecklich.
        _st493 = getattr(tbl, "_leerhinweis_stellen", None)
        if _st493 is not None:
            _st493()

    def _bfs_menue(self, pos):
        from .mw_basis import kontext_menue
        tbl = self._bfs_table
        it = tbl.itemAt(pos)
        if it is None:
            return
        z = tbl.item(it.row(), 0)
        d = z.data(Qt.UserRole) if z is not None else None
        if not d:
            return
        prod, units, nm = d
        m = kontext_menue(tbl)
        if units > 0:
            a = m.addAction(t("Open build plan with {n} units").format(
                n=f"{units:,}".replace(",", "'")))
        else:
            a = m.addAction(t("Open build plan"))
        a.triggered.connect(lambda _c=False, p=prod, u=units, n=nm:
                            self._bfs_plan_oeffnen(p, u, n))
        m.exec(tbl.viewport().mapToGlobal(pos))

    def _bfs_plan_oeffnen(self, produkt, units, name):
        """Neuer Bauplan mit der Menge aus dem Bestand (`_bd_qty_pending`
        wird im Neu-Zweig von open_build_detail verbraucht)."""
        self._bd_qty_pending = max(1, int(units or 1))
        self.open_build_detail(int(produkt), name, fresh=True)

    # ------------------------------------------------------------------
    # MY BLUEPRINTS vs BAUPLAN (emm437, Discord elglebo: Golem in My
    # Blueprints +64.8M Gewinn, im Bauplan -7.3M; Nutzer: "woher kommt diese
    # Abweichung? koennen wir das testen?" -> "nicht noch mehr Tools im
    # Bauplan, das Tool will ich als bat"). NUR mit EMM_MB_VERGLEICH=1
    # (gesetzt von werkzeuge\vergleiche_mb.bat): nach jeder Bauplan-Rechnung
    # geht `kosten_zerlegen` vom GEMERKTEN Eingang der My-Blueprints-Zeile
    # Schritt fuer Schritt zum Bauplan und haengt das Ergebnis an
    # berichte\mb_vergleich_bericht.txt. Keine Oberflaeche, aendert nichts.
    # ------------------------------------------------------------------
    MB_VERGLEICH_AN = os.environ.get("EMM_MB_VERGLEICH") == "1"

    def _mb_vergleich_pfad(self):
        return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__)))), "berichte", "mb_vergleich_bericht.txt")

    def _mb_vergleich_notiz(self, text):
        """Eine Zeile in den Vergleichsbericht (emm449, Nutzer: "es entsteht
        irgendwie kein Bericht") - nur mit EMM_MB_VERGLEICH=1. So zeigt der
        Bericht auch, WAS passiert ist, wenn kein Vergleich entsteht."""
        if not self.MB_VERGLEICH_AN:
            return
        try:
            pfad = self._mb_vergleich_pfad()
            os.makedirs(os.path.dirname(pfad), exist_ok=True)
            with open(pfad, "a", encoding="utf-8") as f:
                f.write(text.rstrip("\n") + "\n")
        except Exception:
            pass

    def _mb_vergleich_nachziehen(self):
        """Aus rebuild(): je Item und Menge EINMAL (sonst schriebe jedes
        Umschalten einen Abschnitt)."""
        if not self.MB_VERGLEICH_AN:
            return
        z = getattr(self, "_bd_rechen_eingang", None)
        if not z:
            self._mb_vergleich_notiz("Build plan: no calculation input yet")
            return
        k = (int(z["type_id"]), int(z["qty"]))
        fertig = getattr(self, "_mb_vergleich_fertig", None)
        if fertig is None:
            fertig = self._mb_vergleich_fertig = set()
        if k in fertig:
            return
        fertig.add(k)
        try:
            self._mb_vergleich_bericht()
        except Exception as _ex:
            self._mb_vergleich_notiz("ERROR (build plan side): %s: %s"
                                     % (type(_ex).__name__, str(_ex)[:300]))

    def _mb_vergleich_bericht(self):
        from .mw_helpers import kosten_zerlegen
        stand = getattr(self, "_bp_econ_stand", None) or {}
        mb = stand.get("eingang")
        ziel = getattr(self, "_bd_rechen_eingang", None)
        pfad = self._mb_vergleich_pfad()
        if not ziel:
            return
        tid = int(ziel["type_id"])
        name = (stand.get("names") or {}).get(tid) or str(tid)

        def _schreiben(text):
            try:
                os.makedirs(os.path.dirname(pfad), exist_ok=True)
                with open(pfad, "a", encoding="utf-8") as f:
                    f.write(text)
            except Exception:
                pass

        _bpi = (mb["recipes"].product_to_bp or {}).get(tid) if mb else None
        e = (stand.get("profit_by_bp") or {}).get(int(_bpi[0])) if _bpi else None
        if not mb or not e or e.get("cost_unit") is None:
            _schreiben(f"\n=== {name} (type {tid}) ===\nNO COMPARISON: My Blueprints "
                       "not loaded, or no profit row for this item.\n")
            return
        # SOFORT eine Zeile (Nutzer 06.10.2026: "nix da" - der Bericht entstand
        # erst am Ende des Hintergrund-Jobs; wer vorher schloss, bekam nichts).
        _schreiben(f"\n=== {name} (type {tid}) === started, wait for "
                   "'Report written' before closing\n")
        try:
            self.statusBar().showMessage(t("Comparison running \u2026"), 60000)
        except Exception:
            pass
        bp = int(_bpi[0])
        o0 = dict(mb["opts"])
        if mb.get("jc_fuer"):
            o0["jobcost_by_tid"] = mb["jc_fuer"](tid)   # Stufen dieser Zeile
        if mb.get("me_fuer"):
            o0.update(mb["me_fuer"](tid))              # Struktur-ME (emm445)
        if e.get("mb_dv") is not None:
            o0["inv_decryptor_map"] = {bp: e["mb_dv"]}
        start = {"qty": int(e.get("mb_qty") or 1), "pfn": mb["pm"].get,
                 "recipes": mb["recipes"], "opts": o0}

        _namen = dict(stand.get("names") or {})
        _namen.update(getattr(self, "_bd_names_ref", None) or {})

        def job():
            from .mw_helpers import me_vergleich
            schritte = kosten_zerlegen(
                lambda q, pf, rc, op: industry.production_plan(tid, q, pf, rc, op),
                start, ziel)
            # JE ITEM: wer macht den ME-Unterschied (emm446)? Nur gebaute
            # Fertigungs-Items des Bauplans.
            try:
                _pl = industry.production_plan(tid, ziel["qty"], ziel["pfn"],
                                               ziel["recipes"], dict(ziel["opts"]))
                _rc = ziel["recipes"]
                _fert = [x for x in ((_pl or {}).get("build_runs") or {})
                         if x not in (getattr(_rc, "reaction_products", None)
                                      or set())]
                me_zeilen = me_vergleich(_fert, start["opts"], ziel["opts"])
            except Exception as _mx:
                me_zeilen = [("ERROR", str(_mx)[:120], None)]
            return schritte, me_zeilen

        def done(erg):
            schritte, me_zeilen = erg
            self._mb_vergleich_ergebnis = schritte

            def _z(v):
                return "-" if v is None else f"{v:,.0f}".replace(",", "'")
            zl = [f"\n=== {name} (type {tid}) ===",
                  f"My Blueprints: cost/unit {_z(e.get('cost_unit'))}, sell "
                  f"{_z(e.get('sell'))}, profit/unit {_z(e.get('profit'))}, decryptor "
                  f"{e.get('decryptor') or '-'}, quantity {start['qty']}",
                  f"Build plan: quantity {ziel['qty']}",
                  "step | cost/unit | delta | material | job | invention | stock"]
            for s in schritte:
                tl = s.get("teile") or {}
                zl.append(" | ".join([s["schritt"], _z(s.get("je_stk")),
                                      _z(s.get("delta")), _z(tl.get("mat")),
                                      _z(tl.get("job")), _z(tl.get("inv")),
                                      _z(tl.get("stock"))])
                          + (f" | ERROR {s['fehler']}" if s.get("fehler") else ""))
            zl.append("(order matters: interactions land on the later step. "
                      "Last row = build plan.)")
            if me_zeilen:
                zl.append("ME per item (blueprint ME / rig / role, in %) - "
                          "My Blueprints vs build plan:")
                for _t, _a, _b in me_zeilen:
                    if _t == "ERROR":
                        zl.append("  ERROR " + str(_a))
                        continue
                    zl.append("  %s: %s / %s / %s  vs  %s / %s / %s" % (
                        _namen.get(_t) or _t, _a[0], _a[1], _a[2],
                        _b[0], _b[1], _b[2]))
            zl.append("")
            _schreiben("\n".join(zl))
            try:
                self.statusBar().showMessage(t("Report written: {datei}").format(
                    datei=os.path.basename(pfad)), 8000)
            except Exception:
                pass

        def fail(err):
            _schreiben(f"ERROR: {str(err)[:300]}\n")

        self._run(Worker(job), done, fail, overlay=False)

    def _jobs_art_name(self, activity_id):
        return {1: t("Manufacturing"), 3: t("TE research"), 4: t("ME research"),
                5: t("Copying"), 7: t("Reverse engineering"), 8: t("Invention"),
                9: t("Reaction"), 11: t("Reaction")}.get(
                    int(activity_id or 0), f"#{activity_id}")

    # KARTEN STATT TABELLE (emm330, Nutzer 02.10.2026: "kein Excel-Tabellen-
    # Simulator bitte, mehr Uebersicht, mit wenigen Blicken verstaendlich, mit
    # Farben arbeiten, Charaktere nebeneinander" -> Vorschlag "Karten
    # nebeneinander" gewaehlt). Je Charakter eine Kachel: drei Slot-Leisten
    # (Fertigung cyan, Reaktion violett, Science amber; fertig gruen), darunter
    # gleiche Jobs zusammengefasst mit Fortschrittsbalken.
    _JOB_FARBE = {"mfg": "CYAN", "react": "VIOLET", "sci": "AMBER"}

    def _jobs_farbe(self, art):
        return getattr(theme, self._JOB_FARBE.get(art, "CYAN"))

    # ------------------------------------------------------------------
    # STOCK LOCATIONS (emm458, Nutzer 07.10.2026: "wo die Materialien der
    # Bauplaene rumliegen, bei welchem Charakter was liegt ... Strukturen,
    # Container, Frachtcontainer ... Suchspalte ... neuer Tab wie Industry
    # Jobs"; Rueckfrage: Name "Stock locations", Item zuerst, Material der
    # gespeicherten + eingefrorenen Plaene, Bedarf daneben).
    # Logik rein in eve_trader/lagerorte.py; hier nur Abruf + Anzeige.
    # ------------------------------------------------------------------

    def _lager_seite_bauen(self):
        """STOCK LOCATIONS als KARTEN je Ort (emm461, Nutzer: "hier erkenne
        ich gar nichts, weder Charaktere noch Karten ... ich haette lieber
        die Locations als Karten, meistens hat man nur 4-5 Baustrukturen,
        vielleicht eine Legende rechts, wo man waehlen kann, auf welchen
        Strukturen / NPC-Stationen Materialien ueberhaupt getrackt werden
        sollen ... generell etwas aehnlich wie der Industry-Jobs-Tab").
        ERSETZT den einen grossen Baum aus emm458."""
        from PySide6.QtWidgets import QPlainTextEdit, QScrollArea
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(8)
        kopf = QHBoxLayout(); kopf.setSpacing(10)
        titel = QLabel(t("STOCK LOCATIONS (BETA)"))
        titel.setStyleSheet(f"font-size:13px; letter-spacing:2px; font-weight:800; "
                            f"color:{theme.GREEN};")
        titel.setToolTip(t(
            "Where the material of your saved, frozen build plans is lying: "
            "one card per station or structure, per item the character (or "
            "corp hangar) and the container, nested containers included. The "
            "game only takes material from the hangar of the character who "
            "starts the job - this page shows who has to move what. Counted "
            "as needed is only what the runs you have NOT built yet still "
            "take. Ship cargo and fittings do not count, like everywhere in "
            "Eve MoMa."))
        kopf.addWidget(titel)
        kopf.addStretch()
        self._lager_stand_lbl = QLabel("")
        self._lager_stand_lbl.setObjectName("Muted")
        kopf.addWidget(self._lager_stand_lbl)
        self._lager_plan_cb = QComboBox()
        self._lager_plan_cb.setMinimumWidth(220)
        self._lager_plan_cb.setToolTip(t(
            "Which plans' material to list. Saved, frozen plans that are not "
            "completed. The search below finds any item regardless."))
        self._lager_plan_cb.currentIndexChanged.connect(lambda _i: self._lager_zeichnen())
        ohne_mausrad(self._lager_plan_cb)
        kopf.addWidget(self._lager_plan_cb)
        self._lager_kauf_btn = QPushButton(t("Copy shopping list"))
        self._lager_kauf_btn.setIcon(icons.icon("cart"))
        self._lager_kauf_btn.setStyleSheet(theme.amber_rahmen_knopf())
        self._lager_kauf_btn.setToolTip(t(
            "Everything that is really missing across ALL listed plans, as "
            "Name<TAB>quantity for EVE's multibuy. Only material your plans "
            "BUY - anything they build themselves stays out, so you never buy "
            "what you are about to produce. Your saved shopping list is not "
            "touched."))
        self._lager_kauf_btn.clicked.connect(lambda: self._lager_kaufliste_kopieren())
        # DIE KOPF-KNOEPFE DUERFEN SCHRUMPFEN (emm500, b66 auf seinem
        # Windows rot: Seite 1281 px - dort messen dieselben Texte
        # ~1,4-1,6x breiter, Lehre vom 19.09.2026, drei Kopfzeilen-Knoepfe
        # in Meine Bauplaene). Volle Breite, solange Platz ist.
        self._lager_kauf_btn.setMinimumWidth(40)
        kopf.addWidget(self._lager_kauf_btn)
        self._lager_auf_btn = QPushButton(t("Expand all"))
        self._lager_auf_btn.setIcon(icons.icon("plus"))   # b55: Bedienelemente tragen ein Symbol
        self._lager_auf_btn.clicked.connect(lambda: self._lager_aufklappen())
        self._lager_auf_btn.setMinimumWidth(40)
        kopf.addWidget(self._lager_auf_btn)
        self._lager_refresh_btn = QPushButton(t("Refresh"))
        self._lager_refresh_btn.setIcon(icons.icon("refresh"))
        self._lager_refresh_btn.setStyleSheet(theme.amber_rahmen_knopf())
        self._lager_refresh_btn.clicked.connect(lambda: self._lager_laden())
        self._lager_refresh_btn.setMinimumWidth(40)
        kopf.addWidget(self._lager_refresh_btn)
        v.addLayout(kopf)
        # UNVOLLSTAENDIGE DATEN SIND KEINE EINKAUFSLISTE (emm476, Nutzer:
        # "jetzt ist es noch schlimmer geworden"): scheitert ein Asset- oder
        # Job-Abruf, fehlt Bestand bzw. Fortschritt - die roten Fehlbetraege
        # sind dann ZU HOCH, und genau daraus entsteht ein unnoetiger
        # Nachkauf. Die Zeile stand bisher nur hinten in der Statuszeile und
        # wurde dort abgeschnitten. Jetzt steht sie rot und breit oben, und
        # "Copy shopping list" ist in dem Fall gesperrt.
        self._lager_warn_lbl = QLabel("")
        self._lager_warn_lbl.setWordWrap(True)
        self._lager_warn_lbl.setStyleSheet(
            f"background:#3A1A18; color:{theme.RED}; "
            f"border:1px solid {theme.RED}; border-radius:6px; "
            f"padding:6px 10px; font-weight:700;")
        self._lager_warn_lbl.hide()
        v.addWidget(self._lager_warn_lbl)
        # SUCHFELD - mehrzeilig, damit eine Hangar-Kopie (Name<TAB>Menge je
        # Zeile) oder eine Einkaufsliste direkt eingefuegt werden kann.
        self._lager_suche = QPlainTextEdit()
        self._lager_suche.setPlaceholderText(t(
            "Type or paste item names - one per line (a hangar copy with "
            "quantities works too)"))
        self._lager_suche.setFixedHeight(52)
        self._lager_suche.setTabChangesFocus(True)
        self._lager_suche_timer = QTimer(page)
        self._lager_suche_timer.setSingleShot(True)
        self._lager_suche_timer.timeout.connect(lambda: self._lager_zeichnen())
        # SICHTBARER WEG ZURUECK (emm487, Nutzer nach Rechtsklick "Search
        # for this item": "jetzt komme ich nicht mehr zurueck, die Karte von
        # Dockside ist klein geworden") - die Suche filtert die Karten,
        # solange Text im Feld steht, aber das sah man nirgends. Der Knopf
        # erscheint nur bei aktiver Suche und leert sie mit einem Klick.
        self._lager_suche_leeren = QPushButton(t("Clear search"))
        self._lager_suche_leeren.setIcon(icons.icon("close"))
        self._lager_suche_leeren.setStyleSheet(theme.amber_rahmen_knopf())
        self._lager_suche_leeren.setToolTip(t(
            "Back to all items – the search filters the cards as long "
            "as text is in the box."))
        self._lager_suche_leeren.setVisible(False)
        self._lager_suche_leeren.clicked.connect(
            lambda: (self._lager_suche.setPlainText(""),
                     self._lager_suche_timer.stop(),
                     self._lager_zeichnen()))
        self._lager_suche.textChanged.connect(
            lambda: (self._lager_suche_leeren.setVisible(
                bool(self._lager_suche.toPlainText().strip())),
                self._lager_suche_timer.start(250)))
        _s_reihe = QHBoxLayout()
        _s_reihe.setContentsMargins(0, 0, 0, 0)
        _s_reihe.setSpacing(8)
        _s_reihe.addWidget(self._lager_suche, 1)
        _s_reihe.addWidget(self._lager_suche_leeren, 0,
                           Qt.AlignTop)
        v.addLayout(_s_reihe)
        # GESAMT-LEISTE wie bei Industry Jobs (emm346/emm461): getrackte
        # Orte, Items, Fehlbetraege - auf einen Blick, bevor man die Karten
        # liest.
        self._lager_summe_box = QWidget()
        _sb = QHBoxLayout(self._lager_summe_box)
        _sb.setContentsMargins(0, 0, 0, 0); _sb.setSpacing(10)
        self._lager_kacheln = {}
        for _schl, _titel, _farbe in (("locs", t("LOCATIONS"), theme.CYAN),
                                      ("items", t("ITEMS"), theme.GREEN),
                                      ("short", t("MISSING"), theme.RED)):
            _k, _zl, _ul = self._industrie_kachel(_titel, _farbe)
            _sb.addWidget(_k, 1)
            self._lager_kacheln[_schl] = {"rahmen": _k, "zahl": _zl, "unter": _ul}
        v.addWidget(self._lager_summe_box)
        body = QHBoxLayout(); body.setSpacing(12)
        self._lager_raster = KartenRaster(breite=440)
        _sc = QScrollArea(); _sc.setWidgetResizable(True)
        _sc.setFrameShape(QScrollArea.NoFrame)
        _sc.setWidget(self._lager_raster)
        body.addWidget(_sc, 1)
        # ORTE AN/AUS (Nutzer: "eine Legende rechts, wo man waehlen kann,
        # auf welchen Strukturen / NPC-Stationen Materialien ueberhaupt
        # getrackt werden sollen"). Gemerkt in settings["lager_orte_aus"]
        # (die AUSgeschalteten) - ein neuer Ort ist damit von selbst an.
        panel = QFrame(); panel.setObjectName("Card")
        panel.setFixedWidth(240)
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(10, 10, 10, 10); pv.setSpacing(6)
        _pt = QLabel(t("LOCATIONS"))
        _pt.setStyleSheet(f"font-size:13px; letter-spacing:2px; font-weight:800; "
                          f"color:{theme.CYAN};")
        pv.addWidget(_pt)
        _ph = QLabel(t("Material at a location you switch off counts nowhere - "
                       "not in the shortfall either."))
        _ph.setObjectName("Muted"); _ph.setWordWrap(True)
        _ph.setStyleSheet(f"font-size:{theme.FS_SMALL};")
        pv.addWidget(_ph)
        self._lager_schalter_box = QVBoxLayout(); self._lager_schalter_box.setSpacing(4)
        pv.addLayout(self._lager_schalter_box)
        self._lager_alle_btn = QPushButton(t("All on"))
        self._lager_alle_btn.setIcon(icons.icon("check"))   # b55: Bedienelemente mit Symbol
        self._lager_alle_btn.setToolTip(t(
            "Switch every location on - or, when all are on, off at once."))
        self._lager_alle_btn.clicked.connect(lambda: self._lager_alle_umschalten())
        pv.addWidget(self._lager_alle_btn)
        pv.addStretch()
        body.addWidget(panel)
        v.addLayout(body, 1)
        self._lager_daten = None
        self._lager_stand_ts = 0.0
        self._lager_laeuft = False
        self._lager_karten = {}          # {ort_id: Karte} - b-Suite
        self._lager_schalter = {}        # {ort_id: Knopf} - b-Suite
        self._lager_schalter_orte = None
        return page

    def _lager_seite_gezeigt(self):
        """Aus _bau_nav(6): beim ersten Zeigen und ab 10 min Alter laden
        (ESI cacht Assets ohnehin bis zu einer Stunde)."""
        import time as _t
        self._lager_plaene_fuellen()
        # SUCHE BEIM BETRETEN LEEREN (emm488, Nutzer: "wenn ich die Tabs
        # wechsle ... und wieder zurueck soll das Suchfeld leer sein").
        # Signale geblockt, sonst zeichnete der 250-ms-Timer doppelt;
        # folgt kein Laden, zeichnet die Seite einmal selbst neu.
        # "Where is it?" (emm459) setzt seinen Suchtext NACH diesem Aufruf
        # und bleibt damit erhalten.
        _suche_war = bool(self._lager_suche.toPlainText())
        if _suche_war:
            self._lager_suche.blockSignals(True)
            self._lager_suche.setPlainText("")
            self._lager_suche.blockSignals(False)
            self._lager_suche_timer.stop()
            self._lager_suche_leeren.setVisible(False)
        if self._lager_daten is None or _t.time() - self._lager_stand_ts > 600:
            self._lager_laden()
        elif _suche_war:
            self._lager_zeichnen()

    def _lager_plaene_fuellen(self):
        from .. import lagerorte
        cb = self._lager_plan_cb
        alt = cb.currentData()
        cb.blockSignals(True)
        cb.clear()
        cb.addItem(t("All frozen plans"), None)
        for p in lagerorte.plaene_fuer_lagerorte(self.settings):
            cb.addItem(str(p.get("label") or p.get("item_name") or p.get("id")),
                       p.get("id"))
        ix = cb.findData(alt) if alt is not None else 0
        cb.setCurrentIndex(ix if ix >= 0 else 0)
        cb.blockSignals(False)

    def _lager_ort_namen(self, orte, char_fuer_ort):
        """{ort_id: Name} aus den bekannten Quellen - Bau-Strukturen, Hubs/
        Favoriten, FRUEHER AUFGELOESTE Namen, NPC-Stationen (oeffentlich);
        unbekannte STRUKTUREN ueber die Charaktere, die dort Assets haben.

        emm462 (Nutzer-Screenshot: zwei Orte standen als "#1045682518989"):
        (1) es wird JEDER Charakter mit Assets an diesem Ort probiert, nicht
        nur der erste - Andockrecht hat oft nur einer (Muster aus
        `_reload_locations`); (2) ein 420 (ESI-Fehlerbudget erschoepft)
        bricht sofort ab, danach bringt Weiterprobieren nur noch mehr 420er;
        (3) ein einmal aufgeloester Name wird in `lager_ort_namen` gemerkt
        und beim naechsten Laden ohne Abruf benutzt - so bleibt er auch da,
        wenn das Fehlerbudget gerade knapp ist."""
        namen = {}
        for bs in (self.settings.get("bau_structures") or []):
            sid = bs.get("link_structure_id")
            if sid and bs.get("name"):
                namen[int(sid)] = str(bs["name"])
        try:
            for o in self._link_orte():
                if o.get("structure_id") and o.get("name"):
                    namen.setdefault(int(o["structure_id"]), str(o["name"]))
        except Exception:
            pass
        _gemerkt = dict(self.settings.get("lager_ort_namen") or {})
        for k, v in _gemerkt.items():
            try:
                if v:
                    namen.setdefault(int(k), str(v))
            except (TypeError, ValueError):
                continue
        offen = [o for o in orte if o not in namen]
        stationen = [o for o in offen if 0 < o < 2 ** 31]
        if stationen:
            try:
                namen.update(esi.orts_namen(stationen) or {})
            except Exception:
                pass
        client_id = self.settings.get("client_id")
        fehl = 0
        budget_weg = False
        neu = {}
        for o in offen:
            if o in namen or o < 2 ** 31 or fehl >= 8 or budget_weg:
                continue
            _cands = char_fuer_ort.get(o) or []
            if not isinstance(_cands, (list, tuple)):
                _cands = [_cands]
            for cid in _cands:
                if not cid or not client_id:
                    continue
                try:
                    info = esi.resolve_structure(client_id, int(cid), int(o)) or {}
                except Exception as _se:
                    _code = getattr(getattr(_se, "response", None),
                                    "status_code", None)
                    if _code == 420:
                        budget_weg = True
                        break
                    continue
                if info.get("name"):
                    namen[o] = str(info["name"])
                    neu[str(o)] = str(info["name"])
                    break
            if o not in namen:
                fehl += 1
        # Bleibt eine Struktur namenlos, sagt die Liste WARUM - eine nackte
        # Nummer sieht aus wie ein Fehler (Nutzer: "in der Locations-Legende
        # gibts noch 2 Strukturen ohne Namen, nur Zahlen mit #"). Den Namen
        # einer Struktur gibt EVE nur Charakteren mit Andockrecht.
        for o in orte:
            if o not in namen and o >= 2 ** 31:
                namen[o] = t("Structure (no docking access) \u00b7 #{id}").format(id=o)
        if neu:
            _gemerkt.update(neu)
            self.settings["lager_ort_namen"] = _gemerkt
            config.save_settings_async(self.settings)
        return namen

    def _lager_laden(self):
        if getattr(self, "_lager_laeuft", False):
            return
        client_id = self.settings.get("client_id")
        chars = store.list_characters()
        if not client_id or not chars:
            self._lager_stand_lbl.setText(t("No characters linked."))
            return
        settings = self.settings

        def job():
            from .. import lagerorte
            import time as _t
            ctypes = esi.container_type_ids_safe()
            zeilen, failed = [], []
            # WIE VIEL hat ESI je Charakter/Corp geliefert (emm477)? Nur so
            # faellt ein STILL zu kleiner Abruf auf - er macht den
            # Fehlbetrag zu hoch, und genau daraus wurde ein Nachkauf.
            asset_n = {}
            besitzer_namen = {}
            beh_namen = {}
            char_fuer_ort = {}      # {ort: [cid, ...]} - ALLE, die dort Assets haben
            for ch in chars:
                cid = int(ch["character_id"])
                name = ch.get("character_name") or ch.get("name") or str(cid)
                besitzer_namen[("char", cid)] = name
                try:
                    assets = esi._fetch_all_assets(client_id, cid)
                except Exception as _ae:
                    self._log_exception(f"Stock locations: assets {name}", str(_ae))
                    failed.append(name)
                    continue
                z = lagerorte.zeilen_aus_assets(assets, ctypes, cid, "char")
                asset_n[name] = len(z)
                for r in z:
                    _l = char_fuer_ort.setdefault(r["ort"], [])
                    if cid not in _l:
                        _l.append(cid)
                ids = lagerorte.behaelter_ids(z)
                if ids:
                    try:
                        for k, nm in (esi.fetch_asset_names(client_id, cid, sorted(ids))
                                      or {}).items():
                            if nm:
                                beh_namen[k] = nm
                    except Exception:
                        pass
                zeilen.extend(z)
            # CORP-HANGARS (nur mit dem Corp-Schalter, EIN Abruf je Corp wie
            # ueberall - corp.abrufplan ueber _corp_rollen).
            _corp_jobs_plan = {}      # {corp_id: via_cid} fuer den Job-Abruf
            if settings.get("use_corp"):
                from .. import corp as _corp
                _co = {"ohne_rolle": [], "relink": [], "failed": [],
                       "keine_division": False, "aktiv": True, "bp_ok": True}
                try:
                    _, plan, _pj = self._corp_rollen(client_id, chars, _co)
                    _corp_jobs_plan = dict(_pj or {})
                except Exception:
                    plan = {}
                    # Rollen unbekannt -> Corp-Jobs unbekannt. None heisst
                    # unten "ehrlich als Fehler melden", nicht "keine Corp".
                    _corp_jobs_plan = None
                divs = _corp.divisions_bereinigt(settings.get("corp_divisions"))
                for corp_id, via in sorted((plan or {}).items()):
                    try:
                        cname = esi.fetch_corporation_name(corp_id)
                    except Exception:
                        cname = f"#{corp_id}"
                    besitzer_namen[("corp", int(corp_id))] = t("Corp: {name}").format(name=cname)
                    try:
                        ca = esi.fetch_corporation_assets(client_id, via, corp_id)
                    except Exception as _ce:
                        self._log_exception(f"Stock locations: corp assets {cname}", str(_ce))
                        failed.append(t("Corp: {name}").format(name=cname))
                        continue
                    zc = lagerorte.zeilen_aus_assets(ca, ctypes, int(corp_id), "corp",
                                                     divisions=divs)
                    asset_n[t("Corp: {name}").format(name=cname)] = len(zc)
                    for r in zc:
                        _l = char_fuer_ort.setdefault(r["ort"], [])
                        if via not in _l:
                            _l.append(via)
                    zeilen.extend(zc)
            plaene = lagerorte.plaene_fuer_lagerorte(settings)
            # NOCH OFFENER Bedarf (emm463): die lokale Job-Zuordnung sagt,
            # welche Runs dieser Plan schon gebaut hat - kein ESI-Abruf.
            try:
                _zuord = store.job_zuordnung_details()
            except Exception as _ze:
                self._log_exception("Stock locations: job assignments", str(_ze))
                _zuord = {}
            # NOCH NICHT ZUGEORDNETE JOBS (emm475, Nutzer: "jetzt habe ich
            # schon nachgekauft, das darf auf keinen Fall jemals wieder
            # passieren"): die Job-Zuordnung laeuft nur beim Aufbau des
            # Runplaners eines Plans. Wer einen Job startet und den Plan
            # danach nicht oeffnet, hat sein Material im Spiel weg, waehrend
            # die Seite den Bedarf noch voll zeigt - genau so entstand der
            # unnoetige Nachkauf. Jobs, die GENAU EIN Plan gebaut haben
            # kann, zaehlen deshalb hier mit; mehrdeutige kommen als
            # sichtbare Warnung (`job_offen`), nie still.
            _jobs_alle, _job_fehler = [], False
            for ch in chars:
                try:
                    _jobs_alle += esi.fetch_active_jobs(
                        client_id, int(ch["character_id"]),
                        include_delivered=True) or []
                except Exception as _je:
                    _job_fehler = True
                    self._log_exception(
                        f"Stock locations: jobs {ch.get('character_name')}",
                        str(_je))
            # CORP-JOBS ZAEHLEN WIE CHARAKTER-JOBS (emm482, Nutzer 09.10.2026:
            # "Corp Jobs funktionieren exakt gleich wie normale Jobs?" - hier
            # NICHT: die Seite holte nur Charakter-Jobs. Ein Corp-Job wurde
            # weder festgeschrieben noch mitgezaehlt, sein Material war im
            # Spiel weg, der Fehlbetrag blieb zu hoch - dieselbe Luecke wie
            # emm475, nur fuer Corp-Bauer). Ein Abruf je Corp (corp.abrufplan,
            # Rolle Factory_Manager); scheitert er oder sind die Rollen
            # unbekannt, gilt dieselbe Regel wie bei den Charakteren: nichts
            # festschreiben, rote Zeile (emm476). Doppelte job_ids filtert
            # zuteilbare_jobs; /characters/.../industry/jobs enthaelt keine
            # Corp-Jobs (geprueft, emm389).
            if _corp_jobs_plan is None:
                _job_fehler = True
            else:
                for _c482, _v482 in sorted(_corp_jobs_plan.items()):
                    try:
                        _jobs_alle += esi.fetch_corporation_jobs(
                            client_id, int(_v482), int(_c482),
                            include_delivered=True) or []
                    except Exception as _je:
                        _job_fehler = True
                        self._log_exception(
                            f"Stock locations: corp jobs #{_c482}", str(_je))
            try:
                _vergeben = store.job_zuordnung_alle() or {}
            except Exception as _ve:
                self._log_exception("Stock locations: job assignments 2", str(_ve))
                _vergeben = {}
                _job_fehler = True
            # Items, die NOCH ANDERE offene Plaene bauen (auch nicht
            # eingefrorene) - damit ist ein Job nicht mehr eindeutig.
            from .mw_helpers import MainWindowHelpers as _MH475
            _ids = {str(p.get("id")) for p in plaene}
            _fremd = set()
            for _p in (settings.get("bau_saved_plans") or []):
                if not isinstance(_p, dict) or _p.get("done_manual"):
                    continue
                if str(_p.get("id")) in _ids:
                    continue
                _fremd |= set(_MH475.plan_baut_items(_p))
            _extra, _job_offen, _fest = ({}, [], 0)
            if not _job_fehler:
                _tr, _job_offen = lagerorte.zuteilbare_jobs(
                    _jobs_alle, plaene, _vergeben, _fremd)
                # FESTSCHREIBEN (emm478, Nutzer-Entscheid "still
                # festschreiben"): bisher lief die Zuordnung NUR beim Aufbau
                # des Runplaners eines Plans - wer 30 Jobs startet und den
                # Plan nicht oeffnet, hatte sie nirgends. Eindeutig heisst:
                # GENAU EIN offener Plan baut das Item, der Job startete
                # nach dessen Einfrieren. Die erste Entscheidung gewinnt
                # (INSERT OR IGNORE); korrigieren kann der Nutzer sie im
                # Runplaner unter "Job assignments".
                for _jid, _pid, _tid, _runs, _akt in _tr:
                    _e = _extra.setdefault(_pid, {})
                    _e[_tid] = _e.get(_tid, 0) + _runs
                    try:
                        if store.job_zuordnung_setzen(
                                _jid, _pid, _tid, _runs, "eindeutig"):
                            _fest += 1
                    except Exception as _fe:
                        self._log_exception(
                            "Stock locations: assign job", str(_fe))
                # STUFEN RUN-ZAHL + BAU-PRIORITAET (emm484, Nutzer: "ja
                # unbedingt genau so bauen!"): bauen ZWEI Plaene dasselbe
                # Item, blieb der Job bisher eine Warnung, bis man einen
                # Plan im Runplaner oeffnete - nur dort liefen die Stufen
                # aus emm430. Jetzt laufen DIESELBEN Helfer auch hier.
                _job_offen, _fest2 = self._lager_stufen_zuordnen(
                    _job_offen, _extra, _vergeben)
                _fest += _fest2
            gebaut_tids = lagerorte.gebaute_tids(plaene)
            bedarf = lagerorte.bedarf_aus_plaenen(plaene, _zuord, _extra)
            bedarf_je_plan = {p.get("id"): lagerorte.bedarf_aus_plaenen(
                [p], _zuord, _extra) for p in plaene}
            tids = {r["tid"] for r in zeilen} | set(bedarf)
            # Behaelter ohne eigenen Namen heissen nach ihrem Typ.
            beh_typ = lagerorte.behaelter_typen(zeilen)
            tids |= set(beh_typ.values())
            namen = dict(store.cached_names(sorted(tids)) or {}) if tids else {}
            fehlt = [x for x in tids if x not in namen]
            if fehlt:
                try:
                    namen.update(esi.resolve_names(fehlt) or {})
                except Exception:
                    pass
            for i, tid in beh_typ.items():
                if not beh_namen.get(i):
                    beh_namen[i] = namen.get(tid) or f"#{tid}"
            orte = {r["ort"] for r in zeilen}
            ort_namen = self._lager_ort_namen(orte, char_fuer_ort)
            # STILL ZU KLEINER ABRUF (emm477): zweimal gemessen am
            # 08.10.2026 - 3'886 -> 2'501 Asset-Zeilen, 38 Mio Stueck weg,
            # ohne einen einzigen ESI-Fehler. Sinkt die Zeilenzahl eines
            # Charakters deutlich, ist der Fehlbetrag zu hoch.
            _schrumpf = []
            try:
                _schrumpf, _stand_neu = lagerorte.bestand_schrumpf(
                    asset_n, settings.get("lager_asset_stand") or {})
                settings["lager_asset_stand"] = _stand_neu
                config.save_settings_async(settings)
            except Exception as _se:
                self._log_exception("Stock locations: asset count", str(_se))
            return {"zeilen": zeilen, "namen": namen, "ort_namen": ort_namen,
                    "besitzer_namen": besitzer_namen, "beh_namen": beh_namen,
                    "bedarf": bedarf, "bedarf_je_plan": bedarf_je_plan,
                    "built": gebaut_tids,
                    "job_extra": _extra, "job_offen": _job_offen,
                    "job_fehler": _job_fehler, "schrumpf": _schrumpf,
                    "job_fest": _fest,
                    # ESI-FEHLERBUDGET (emm480): ein 420 waehrend des Abrufs
                    # beantwortet GAR NICHTS mehr - dann sind diese Zahlen
                    # unvollstaendig, auch wenn kein einzelner Abruf geworfen
                    # hat (die Lage vom 09.10.2026, fehler.log 13:33).
                    "budget_420": esi.budget_erschoepft(),
                    "failed": failed, "ts": _t.time()}

        def done(res):
            self._lager_laeuft = False
            self._lager_daten = res
            self._lager_stand_ts = res.get("ts") or 0.0
            self._lager_plaene_fuellen()
            self._lager_zeichnen()

        def fail(_err):
            self._lager_laeuft = False
            self._lager_stand_lbl.setText(t("Loading failed."))

        self._lager_laeuft = True
        self._lager_stand_lbl.setText(t("Loading assets of all characters \u2026"))
        self._run(Worker(job), done, fail, overlay=False)

    def _lager_aus(self):
        """Die AUSgeschalteten Orte (Strings) - ein neuer Ort ist von selbst an."""
        return {str(x) for x in (self.settings.get("lager_orte_aus") or [])}

    def _lager_ort_schalten(self, ort, an):
        aus = self._lager_aus()
        if an:
            aus.discard(str(ort))
        else:
            aus.add(str(ort))
        self.settings["lager_orte_aus"] = sorted(aus)
        config.save_settings_async(self.settings)
        _b = (getattr(self, "_lager_schalter", None) or {}).get(int(ort))
        if _b is not None:
            self._jobs_schalter_stil(_b, an)
        self._lager_alle_btn_stand()
        self._lager_zeichnen()

    def _lager_alle_umschalten(self):
        """EIN Knopf fuer beides (emm462, Nutzer: "ausserdem man einen
        All On/Off toggle"): sind alle Orte an, schaltet er alle aus - sonst
        alle an. Der Knopftext sagt immer, was der naechste Klick tut."""
        orte = [int(o) for o in (self._lager_schalter_orte or [])]
        alle_an = not (self._lager_aus() & {str(o) for o in orte})
        self.settings["lager_orte_aus"] = sorted(str(o) for o in orte) if alle_an else []
        config.save_settings_async(self.settings)
        for _b in (getattr(self, "_lager_schalter", None) or {}).values():
            _b.blockSignals(True)
            _b.setChecked(not alle_an)
            _b.blockSignals(False)
            self._jobs_schalter_stil(_b, not alle_an)
        self._lager_alle_btn_stand()
        self._lager_zeichnen()

    def _lager_alle_btn_stand(self):
        """Beschriftung des Toggles: "All off", solange alle an sind."""
        btn = getattr(self, "_lager_alle_btn", None)
        if btn is None:
            return
        orte = [int(o) for o in (self._lager_schalter_orte or [])]
        alle_an = bool(orte) and not (self._lager_aus() & {str(o) for o in orte})
        btn.setText(t("All off") if alle_an else t("All on"))
        btn.setIcon(icons.icon("close" if alle_an else "check"))

    def _lager_schalter_bauen(self, orte):
        """Eine Zeile je Ort: Name + An/Aus-Knopf (wie die Charaktere bei
        Industry Jobs - dieselbe Knopf-Stelle `_jobs_schalter_stil`)."""
        box = self._lager_schalter_box
        while box.count():
            it = box.takeAt(0)
            _w = it.widget()
            if _w is not None:
                _w.deleteLater()
            elif it.layout() is not None:
                while it.layout().count():
                    _x = it.layout().takeAt(0).widget()
                    if _x is not None:
                        _x.deleteLater()
        self._lager_schalter = {}
        aus = self._lager_aus()
        for ort, name, menge in orte:
            row = QHBoxLayout(); row.setSpacing(6)
            nl = KurzLabel(str(name))
            nl.setToolTip(t("{name} \u00b7 {n} units").format(
                name=name, n=f"{int(menge):,}".replace(",", "'")))
            row.addWidget(nl, 1)
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedWidth(52)
            _an = str(ort) not in aus
            btn.setChecked(_an)
            self._jobs_schalter_stil(btn, _an)
            btn.toggled.connect(lambda an, _o=ort: self._lager_ort_schalten(_o, an))
            row.addWidget(btn)
            box.addLayout(row)
            self._lager_schalter[int(ort)] = btn
        self._lager_schalter_orte = [int(o) for o, _n, _m in orte]
        self._lager_alle_btn_stand()

    def _lager_baum_hoehe(self, baum):
        """Hoehe aus den SICHTBAREN Zeilen - die Karte waechst beim
        Aufklappen, statt eine eigene Bildlaufleiste zu bekommen."""
        n = 0

        def _zaehl(it):
            nonlocal n
            for i in range(it.childCount()):
                n += 1
                c = it.child(i)
                if c.isExpanded():
                    _zaehl(c)
        for i in range(baum.topLevelItemCount()):
            n += 1
            _t = baum.topLevelItem(i)
            if _t.isExpanded():
                _zaehl(_t)
        zh = baum.sizeHintForRow(0) if baum.topLevelItemCount() else 20
        return max(26, n * max(18, zh) + 8)

    def _lager_hoehe_nachziehen(self, baum):
        baum.setFixedHeight(self._lager_baum_hoehe(baum))

    def _lager_karte(self, k, fehlt=False):
        """Eine Karte je Ort (emm461): Kopf = Ort, darunter je Item eine
        aufklappbare Zeile (Charakter -> Container). `fehlt` = die Karte der
        Items, die an keinem eingeschalteten Ort liegen."""
        from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
        card = QFrame(); card.setObjectName("Card")
        card.setMinimumWidth(420)
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10); v.setSpacing(5)
        kopf = QHBoxLayout(); kopf.setSpacing(8)
        name = QLabel(str(k["name"]))
        name.setStyleSheet(f"color:{theme.RED if fehlt else theme.CYAN}; "
                           f"font-weight:800; font-size:{theme.FS_H2};")
        name.setToolTip(str(k["name"]))
        kopf.addWidget(name, 1)
        if k["short"]:
            _b = QLabel(t("{n} items missing").format(n=k["short"]))
            _b.setStyleSheet(f"background:{theme.RED}; color:{theme.BG}; "
                             f"font-weight:800; border-radius:4px; padding:1px 7px;")
            kopf.addWidget(_b)
        v.addLayout(kopf)
        unter = QLabel(t("{i} item(s) \u00b7 {n} units").format(
            i=len(k["items"]), n=f"{int(k['menge']):,}".replace(",", "'")))
        unter.setObjectName("Muted")
        unter.setStyleSheet(f"font-size:{theme.FS_SMALL};")
        v.addWidget(unter)
        if not k["items"] and not fehlt:
            # Eingeschalteter Ort, an dem nichts Gesuchtes liegt.
            _leer = QLabel(t("Nothing your plans still need lies here."))
            _leer.setObjectName("Muted")
            _leer.setStyleSheet(f"font-size:{theme.FS_SMALL};")
            _leer.setWordWrap(True)
            v.addWidget(_leer)
            card._lager_baum = None      # b-Suite
            card._lager_ort = k["ort"]
            return card
        baum = QTreeWidget()
        baum.setColumnCount(3)
        baum.setHeaderHidden(True)
        baum.setRootIsDecorated(True)
        baum.setIndentation(14)
        baum.setUniformRowHeights(True)
        baum.setFrameShape(QFrame.NoFrame)
        baum.setSelectionMode(QTreeWidget.ExtendedSelection)
        baum.setStyleSheet("QTreeWidget{background:transparent;}")
        baum.setColumnWidth(0, 230)
        baum.setColumnWidth(1, 90)
        kopier_menue(baum, lambda pos, _b=baum: self._lager_karte_menue(_b, pos))
        _amber = QBrush(QColor(theme.AMBER))
        _rot = QBrush(QColor(theme.RED))
        _mut = QBrush(QColor(theme.MUTED))

        def _z(n):
            return f"{int(n):,}".replace(",", "'")
        for it in k["items"]:
            top = QTreeWidgetItem([it["name"], _z(it["menge"]), ""])
            top.setData(0, Qt.UserRole, it["tid"])
            top.setData(0, ROLLE_KOPIERNAME, it["name"])
            top.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
            f = top.font(0); f.setBold(True); top.setFont(0, f)
            _bd = " \u00b7 ".join(f"{_z(q)} {pl}" for pl, q in it["bedarf"])
            if it["short"] > 0:
                _st = t("missing {n}").format(n=_z(it["short"]))
                top.setText(2, _st)
                top.setForeground(2, _rot)
            elif it["bedarf"]:
                top.setText(2, "\u2713")
            if _bd:
                top.setToolTip(2, t("Still needed by plans: {b}").format(b=_bd)
                               + "\n" + t("{n} across all tracked locations").format(
                                   n=_z(it["gesamt"])))
            baum.addTopLevelItem(top)
            for bes in it.get("besitzer") or []:
                bi = QTreeWidgetItem([bes["name"], _z(bes["menge"]), ""])
                bi.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                bi.setForeground(0, _amber if bes["art"] == "corp" else _mut)
                top.addChild(bi)
                for pfad, q in bes["pfade"]:
                    txt = " \u203a ".join(pfad) if pfad else t("in hangar (no container)")
                    pi = QTreeWidgetItem([txt, _z(q), ""])
                    pi.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                    pi.setForeground(0, _mut)
                    if pfad:
                        pi.setIcon(0, icons.icon("package"))
                    bi.addChild(pi)
        baum.expanded.connect(lambda _i, _b=baum: (
            self._lager_hoehe_nachziehen(_b), self._lager_auf_btn_stand()))
        baum.collapsed.connect(lambda _i, _b=baum: (
            self._lager_hoehe_nachziehen(_b), self._lager_auf_btn_stand()))
        v.addWidget(baum)
        self._lager_hoehe_nachziehen(baum)
        card._lager_baum = baum          # b-Suite
        card._lager_ort = k["ort"]
        return card

    def _lager_karte_menue(self, baum, pos):
        """Rechtsklick in einer Orts-Karte: "Copy" kommt vom Verteiler,
        dazu "Where is it?" (springt auf dieses Item in der Suche)."""
        from .mw_basis import kontext_menue
        it = baum.itemAt(pos)
        if it is None:
            return
        top = it
        while top.parent() is not None:
            top = top.parent()
        tid = top.data(0, Qt.UserRole)
        if not tid:
            return
        m = kontext_menue(baum)
        a = m.addAction(icons.icon("search"), t("Search for this item"))
        a.triggered.connect(lambda _c=False, _n=top.text(0): (
            self._lager_suche.setPlainText(_n), self._lager_zeichnen()))
        m.exec(baum.viewport().mapToGlobal(pos))

    def _lager_zeichnen(self):
        from .. import lagerorte
        res = self._lager_daten
        if not res:
            self._lager_raster.setze([])
            return
        zeilen = res.get("zeilen") or []
        namen = res.get("namen") or {}
        ort_namen = res.get("ort_namen") or {}
        orte = lagerorte.orte_mit_bestand(zeilen, ort_namen)
        if [o for o, _n, _m in orte] != (self._lager_schalter_orte or None):
            self._lager_schalter_bauen(orte)
        aus = self._lager_aus()
        aktiv = [o for o, _n, _m in orte if str(o) not in aus]
        begriffe = lagerorte.suchbegriffe(self._lager_suche.toPlainText())
        pid = self._lager_plan_cb.currentData()
        bedarf = (res.get("bedarf_je_plan") or {}).get(pid) if pid is not None \
            else res.get("bedarf")
        bedarf = bedarf or {}
        nur = None if begriffe else set(bedarf)
        karten, fehlt = lagerorte.karten(
            zeilen, namen, ort_namen, res.get("besitzer_namen") or {},
            res.get("beh_namen") or {}, bedarf=bedarf, nur_tids=nur,
            begriffe=begriffe, nur_orte=aktiv,
            selbst_gebaut=res.get("built") or set())
        # Der Einkaufslisten-Knopf nimmt GENAU das, was hier steht - je Item
        # einmal (ein Item liegt oft an mehreren Orten).
        _fehl_items = {}
        for _k in karten:
            for _i in _k["items"]:
                _fehl_items.setdefault(int(_i["tid"]), _i)
        for _i in fehlt:
            _fehl_items.setdefault(int(_i["tid"]), _i)
        self._lager_fehl_items = list(_fehl_items.values())
        self._lager_karten = {}
        widgets = []
        if fehlt:
            # Bedarf, der an keinem eingeschalteten Ort liegt - eigene Karte
            # ganz vorn (Handlungsbedarf zuerst, wie die Job-Karten).
            _k = {"ort": 0, "name": t("Not at any tracked location"),
                  "menge": 0, "short": len(fehlt),
                  "items": [{"tid": x["tid"], "name": x["name"], "menge": 0,
                             "gesamt": 0, "bedarf": x["bedarf"],
                             "short": x["short"], "besitzer": []} for x in fehlt]}
            widgets.append(self._lager_karte(_k, fehlt=True))
        for k in karten:
            w = self._lager_karte(k)
            self._lager_karten[int(k["ort"])] = w
            widgets.append(w)
        self._lager_raster.setze(widgets)
        # KACHELN
        _n_items = len({i["tid"] for k in karten for i in k["items"]}) + len(fehlt)
        _n_short = len({i["tid"] for k in karten for i in k["items"]
                        if i["short"] > 0}) + len(fehlt)
        kc = self._lager_kacheln
        kc["locs"]["zahl"].setText(
            f'<span style="color:{theme.CYAN};">{len(aktiv)}</span>'
            f'<span style="color:{theme.MUTED}; font-size:{theme.FS_BASE}; '
            f'font-weight:400;"> / {len(orte)}</span>')
        kc["locs"]["unter"].setText(t("tracked"))
        kc["items"]["zahl"].setText(
            f'<span style="color:{theme.GREEN};">{_n_items}</span>')
        kc["items"]["unter"].setText(
            t("searched") if begriffe else t("still needed by your plans"))
        kc["short"]["zahl"].setText(
            f'<span style="color:{theme.RED if _n_short else theme.MUTED};">'
            f'{_n_short}</span>')
        kc["short"]["unter"].setText(t("not enough across all characters"))
        # STAND
        from datetime import datetime as _dt
        teile = []
        if self._lager_stand_ts:
            teile.append(t("as of {zeit}").format(
                zeit=_dt.fromtimestamp(self._lager_stand_ts).strftime("%H:%M")))
        # WARNUNGEN ZUERST (emm476): die Statuszeile wird rechts
        # abgeschnitten - was wichtig ist, steht vorn.
        # NIE STILL (emm475): ein Job, dessen Material im Spiel schon weg
        # ist, senkt den Bedarf nur, wenn er EINDEUTIG einem Plan gehoert.
        # Alles andere steht hier - sonst kauft der Nutzer nach, was er
        # gerade verbaut (genau der Schaden vom 08.10.2026).
        _n_of = len(res.get("job_offen") or [])
        if _n_of:
            teile.append(t("\u26a0 {n} job(s) belong to no plan - assign them")
                         .format(n=_n_of))
        _ex = res.get("job_extra") or {}
        _n_ex = sum(len(v or {}) for v in _ex.values())
        if _n_ex:
            # Gezaehlt werden ITEMS, nicht Jobs (emm478 - der alte Text sagte
            # "2 job(s)", gemeint waren 2 Materialien aus 33 Jobs).
            teile.append(t("{n} item(s) covered by jobs not yet assigned")
                         .format(n=_n_ex))
        if res.get("job_fest"):
            teile.append(t("{n} job(s) assigned automatically").format(
                n=res["job_fest"]))
        if len(aktiv) < len(orte):
            teile.append(t("{n} location(s) switched off").format(
                n=len(orte) - len(aktiv)))
        self._lager_stand_lbl.setText("  \u00b7  ".join(teile))
        self._lager_unvollstaendig_zeigen(res)
        self._lager_auf_btn_stand()

    def _lager_stufen_zuordnen(self, offen, extra, vergeben):
        """RUN-ZAHL und BAU-PRIORITAET auch beim stillen Festschreiben der
        Stock-locations-Seite (emm484, Nutzer: "ja unbedingt genau so
        bauen!").

        DIESELBEN Helfer wie der Runplaner (Regel 9 - kein Nachbau):
        `signatur_zuteilen` (genau EIN Plan hat exakt so viele offene Runs
        wie der Job -> ihm, Quelle "signatur"; ZWEI exakte Treffer ->
        mehrdeutig, die Prioritaet laesst sie liegen, emm430) und
        `prio_jobs_zuteilen` (Plan #1 der Bau-Reihenfolge, in den der Job
        GANZ passt, Quelle "prioritaet" - still seit emm430). Die Plaene
        kommen aus `_prio_plaene()` - exakt die Liste des Runplaners, samt
        schon belegter Runs aus der Zuordnungs-Tabelle. Was keine Stufe
        nimmt, bleibt die sichtbare Warnung (emm475: gerechnet oder
        gemeldet, nie still). Korrigierbar wie immer ueber "Job
        assignments" im Runplaner.

        Gezaehlt (in `extra`, je Plan) wird NUR, was wirklich geschrieben
        wurde: kam ein anderer dazwischen (INSERT OR IGNORE -> False),
        koennte der Job einem anderen Plan gehoeren - dann lieber eine
        Warnung fuer einen Ladevorgang als ein falscher Abzug (Regel 3).
        -> (offene Jobs ohne die zugeteilten, Anzahl festgeschrieben)."""
        from .mw_helpers import (MainWindowHelpers as _MH,
                                 prio_jobs_zuteilen, signatur_zuteilen)
        if not offen:
            return offen, 0
        try:
            _rx = set(industry.recipes_cached().reaction_products or ())
        except Exception as _re:
            # Ohne Rezeptdaten keine Aktivitaets-Pruefung - dann lieber
            # NICHT zuteilen (Regel 3); die Jobs bleiben sichtbare Warnung.
            self._log_exception("Stock locations: recipes for stages",
                                str(_re))
            return offen, 0

        def _ir(_t):
            return int(_t) in _rx

        def _ts(j):
            # Geliefert zaehlt ab dem ABLIEFERN, laufend ab dem START -
            # dieselbe Lesart wie der Runplaner (emm263/268).
            if (j or {}).get("status") == "delivered":
                return _MH._iso_job_ts(j.get("completed_date"))
            return _MH._iso_job_ts(j.get("start_date"))

        _js = []
        for j in offen:
            _t = _ts(j)
            if _t is None or j.get("job_id") is None:
                continue
            _js.append(dict(j, _ts=_t))
        if not _js:
            return offen, 0
        _verg = set()
        for _k in (vergeben or {}):
            try:
                _verg.add(int(_k))
            except (TypeError, ValueError):
                continue
        fest, zugeteilt = 0, {}
        _nach = {int(j["job_id"]): j for j in _js}
        _plaene = self._prio_plaene()
        _mehr = set()
        if _plaene:
            _vert, _mehr = signatur_zuteilen(_js, _plaene, _verg, _ir)
            for _jid, _pid in _vert.items():
                _j = _nach.get(int(_jid)) or {}
                try:
                    if store.job_zuordnung_setzen(
                            int(_jid), _pid, _j.get("product_type_id"),
                            _j.get("runs"), "signatur"):
                        fest += 1
                        zugeteilt[int(_jid)] = (_pid, _j)
                except Exception as _fe:
                    self._log_exception(
                        "Stock locations: assign job (run count)", str(_fe))
            _rest_js = [j for j in _js
                        if int(j["job_id"]) not in zugeteilt
                        and int(j["job_id"]) not in _mehr]
            if _rest_js:
                # Frisch gerechnet: `belegt` enthaelt jetzt auch die
                # Signatur-Treffer von eben (dieselbe Reihenfolge wie
                # _job_zuordnung_nachfuehren im Runplaner).
                _plaene2 = self._prio_plaene()
                _, _vert2 = prio_jobs_zuteilen(
                    _rest_js, _plaene2, _verg | set(zugeteilt), _ir)
                for _jid, _pid in _vert2.items():
                    _j = _nach.get(int(_jid)) or {}
                    try:
                        if store.job_zuordnung_setzen(
                                int(_jid), _pid, _j.get("product_type_id"),
                                _j.get("runs"), "prioritaet"):
                            fest += 1
                            zugeteilt[int(_jid)] = (_pid, _j)
                    except Exception as _fe:
                        self._log_exception(
                            "Stock locations: assign job (priority)",
                            str(_fe))
        for _jid, (_pid, _j) in zugeteilt.items():
            try:
                _t = int(_j.get("product_type_id") or 0)
                _r = int(_j.get("runs") or 0)
            except (TypeError, ValueError):
                continue
            if _t > 0 and _r > 0:
                _e = extra.setdefault(str(_pid), {})
                _e[_t] = _e.get(_t, 0) + _r
        rest = []
        for j in offen:
            try:
                if int(j.get("job_id")) in zugeteilt:
                    continue
            except (TypeError, ValueError):
                pass
            rest.append(j)
        return rest, fest

    def _lager_unvollstaendig_grund(self, res):
        """Warum die Zahlen dieser Seite ZU HOCH sein koennen - oder "".

        emm476 (Nutzer: "jetzt ist es noch schlimmer geworden"): scheitert
        ein Asset-Abruf, fehlt der Bestand dieses Charakters komplett;
        scheitert die Job-Liste, fehlt der Fortschritt. In beiden Faellen
        zeigt die Seite einen zu grossen Fehlbetrag, und genau daraus wurde
        am 08.10.2026 ein unnoetiger Nachkauf. EINE Stelle fuer die rote
        Zeile UND die Sperre des Einkaufs-Knopfs (Regel 9)."""
        from ..sprache import t as _txt
        teile = []
        # ESI-FEHLERBUDGET ERSCHOEPFT (emm480, gemessen in seiner fehler.log
        # vom 09.10.2026 13:33): bei 420 antwortet CCP auf NICHTS mehr - weder
        # Assets noch Jobs noch Blaupausen. Das steht VOR allem anderen, weil
        # es die Ursache der uebrigen Meldungen ist.
        if (res or {}).get("budget_420") or esi.budget_erschoepft():
            teile.append(_txt(
                "ESI error budget used up (420) - CCP is answering nothing "
                "right now. Wait a minute, then press Refresh."))
        if (res or {}).get("failed"):
            teile.append(_txt(
                "Stock not loaded for: {names} - what is lying there is "
                "missing here.").format(names=", ".join(res["failed"])))
        if (res or {}).get("job_fehler"):
            teile.append(_txt(
                "Industry jobs not loaded - runs you have already built are "
                "missing here."))
        for _nm, _vor, _jetzt in ((res or {}).get("schrumpf") or []):
            teile.append(_txt(
                "{name}: ESI only sent {jetzt} of {vor} stacks - press "
                "Refresh.").format(name=_nm, jetzt=_jetzt, vor=_vor))
        if not teile:
            return ""
        return _txt("⚠ INCOMPLETE DATA - do not buy from this list!") \
            + "  " + "  ".join(teile)

    def _lager_unvollstaendig_zeigen(self, res):
        """Rote Zeile oben + Einkaufs-Knopf sperren (emm476)."""
        from ..sprache import t as _txt
        grund = self._lager_unvollstaendig_grund(res)
        lbl = getattr(self, "_lager_warn_lbl", None)
        if lbl is not None:
            lbl.setText(grund)
            lbl.setVisible(bool(grund))
        btn = getattr(self, "_lager_kauf_btn", None)
        if btn is not None:
            btn.setEnabled(not grund)
            if grund:
                btn.setToolTip(grund)
            else:
                btn.setToolTip(_txt(
                    "Everything that is really missing across ALL listed "
                    "plans, as Name<TAB>quantity for EVE's multibuy. Only "
                    "material your plans BUY - anything they build "
                    "themselves stays out, so you never buy what you are "
                    "about to produce. Your saved shopping list is not "
                    "touched."))

    def _lager_kaufliste_kopieren(self):
        """"Giant Shopping List" (emm464, Nutzer: "ueber alle Baupläne hinweg
        sehen, was fehlt, und eine Giant Shopping List erstellen"): alles mit
        Fehlbetrag ausser dem, was die Plaene selbst bauen - als Multibuy-Text
        in die Zwischenablage. Die gespeicherte Einkaufsliste bleibt
        unberuehrt (Nutzer-Entscheid: "in die Zwischenablage").

        Ein ABGESCHALTETER Ort senkt den Einkauf NICHT (emm467, Nutzer:
        "nein da wird nix verschoben, sonst wuerde ich ja zbsp Jita
        einschalten wenn ich von da material nehmen wollte")."""
        from .. import lagerorte
        from PySide6.QtWidgets import QApplication
        # KEINE EINKAUFSLISTE AUS UNVOLLSTAENDIGEN DATEN (emm476): fehlt der
        # Bestand eines Charakters oder die Job-Liste, sind die Fehlbetraege
        # zu hoch - der Nutzer wuerde kaufen, was er schon hat.
        _grund = self._lager_unvollstaendig_grund(self._lager_daten or {})
        if _grund:
            self._flash_tip(_grund)
            return
        posten = lagerorte.einkaufsliste(
            getattr(self, "_lager_fehl_items", None) or [],
            (self._lager_daten or {}).get("built") or set())
        if not posten:
            self._flash_tip(t("Nothing is missing \u2013 nothing to buy."))
            return
        QApplication.clipboard().setText(lagerorte.multibuy_text(posten))
        self._flash_tip(t("{n} materials copied for EVE's multibuy.").format(
            n=len(posten)))

    def _lager_aufklappen(self):
        """Ein Knopf, zwei Richtungen (Nutzer: "der Expand all Knopf soll auch
        Toggle sein und wieder alles zusammenziehen")."""
        _auf = not self._lager_alles_offen()
        for w in (getattr(self, "_lager_karten", None) or {}).values():
            _b = getattr(w, "_lager_baum", None)
            if _b is not None:
                _b.expandAll() if _auf else _b.collapseAll()
                self._lager_hoehe_nachziehen(_b)
        self._lager_auf_btn_stand()

    def _lager_alles_offen(self):
        """Ist JEDE Item-Zeile aufgeklappt? GEMESSEN, nicht gemerkt - nach
        einem Neuzeichnen sind die Karten wieder zu, und zugeklappt wird auch
        von Hand."""
        n = 0
        for w in (getattr(self, "_lager_karten", None) or {}).values():
            _b = getattr(w, "_lager_baum", None)
            if _b is None:
                continue
            for i in range(_b.topLevelItemCount()):
                n += 1
                if not _b.topLevelItem(i).isExpanded():
                    return False
        return n > 0

    def _lager_auf_btn_stand(self):
        """Der Knopf sagt immer, was der NAECHSTE Klick tut (wie 'All on/off')."""
        _b = getattr(self, "_lager_auf_btn", None)
        if _b is None:
            return
        _auf = self._lager_alles_offen()
        _b.setText(t("Collapse all") if _auf else t("Expand all"))
        _b.setIcon(icons.icon("minus" if _auf else "plus"))

    def _lager_zeigen(self, tid, name=None, plan_id=None):
        """Aus einem Bauplan-Fenster heraus: Stock locations mit DIESEM Item
        im Suchfeld und dem Plan im Dropdown oeffnen (emm459, Rechtsklick
        "Where is it?" im Runplaner und im Materialien-Reiter)."""
        if not hasattr(self, "_lager_suche"):
            return
        # Der Vorne-Halter des Bauplan-Fensters (emm416) wuerde das
        # Hauptfenster sonst in den ersten 20 s wieder nach hinten draengen.
        _vh = getattr(self, "_bd_vorne_halter", None)
        if _vh is not None:
            try:
                _vh.abschalten()
            except Exception:
                pass
        try:
            self._go_tab("build")
        except Exception:
            pass
        self._bau_nav(6)
        cb = self._lager_plan_cb
        ix = cb.findData(plan_id) if plan_id is not None else -1
        cb.blockSignals(True)
        cb.setCurrentIndex(ix if ix >= 0 else 0)
        cb.blockSignals(False)
        _nm = str(name or "").strip()
        if not _nm or _nm.startswith("#"):
            _nm = ((self._lager_daten or {}).get("namen") or {}).get(int(tid)) \
                or _nm or f"#{int(tid)}"
        self._lager_suche.setPlainText(_nm)
        self._lager_zeichnen()
        try:
            self.raise_()
            self.activateWindow()
        except Exception:
            pass

    def _wo_liegt_aktion(self, menu, tid, name):
        """Menue-Eintrag "Where is it?" (emm459) - EINE Stelle fuer Runplaner
        und Materialien-Reiter."""
        a = menu.addAction(icons.icon("map"), t("Where is it? (Stock locations)"))
        _pid = getattr(self, "_bd_open_plan_id", None)
        a.triggered.connect(lambda _c=False, _t=int(tid), _n=name, _p=_pid:
                            self._lager_zeigen(_t, _n, _p))
        return a

    def _mat_tab_menue(self, pos):
        """Rechtsklick im Materialien-Reiter (emm459): "Copy" kommt vom
        Verteiler, dazu "Where is it?" fuer Zeilen mit type_id."""
        from .mw_basis import kontext_menue
        tbl = getattr(self, "_bd_mat_tab_tbl", None)
        if tbl is None:
            return
        it = tbl.itemAt(pos)
        if it is None:
            return
        tid = it.data(0, Qt.UserRole)
        if not tid:
            return
        m = kontext_menue(tbl)
        self._wo_liegt_aktion(m, int(tid), it.text(0))
        m.exec(tbl.viewport().mapToGlobal(pos))

    def _industrie_kachel(self, titel, farbe, balken=None):
        """Kachel der Industrie-Seiten: Titel, grosse Zahl, optionaler
        Balken, Unterzeile. EINE Stelle fuer "Industry jobs" (emm346) und
        "Stock locations" (emm461) - zwei Kopien desselben Stils waeren
        zwei Wahrheiten darueber, wie eine Kachel aussieht.
        -> (Rahmen, Zahl-Label, Unter-Label)."""
        k = QFrame(); k.setObjectName("Card")
        k.setStyleSheet(f"QFrame#Card{{background:{theme.PANEL2}; "
                        f"border:1px solid {theme.BORDER}; border-radius:6px;}}")
        kv = QVBoxLayout(k)
        kv.setContentsMargins(12, 8, 12, 8); kv.setSpacing(3)
        tl = QLabel(titel)
        tl.setStyleSheet(f"color:{farbe}; font-size:{theme.FS_SMALL}; "
                         f"font-weight:800; letter-spacing:1px; background:transparent;")
        kv.addWidget(tl)
        zl = QLabel("\u2013")
        zl.setTextFormat(Qt.RichText)
        zl.setWordWrap(True)              # "n free slots" bricht um statt zu draengen
        zl.setStyleSheet(f"font-size:{theme.FS_KPI}; font-weight:800; "
                         f"background:transparent;")
        kv.addWidget(zl)
        if balken is not None:
            kv.addWidget(balken)
        # Unterzeile gekuerzt mit "..." (sie traegt Item- und Ortsnamen
        # beliebiger Laenge - sie darf die Seite nie verbreitern).
        ul = KurzLabel("")
        ul.setObjectName("Muted")
        ul.setStyleSheet(f"font-size:{theme.FS_SMALL}; background:transparent;")
        kv.addWidget(ul)
        return k, zl, ul

    def _jobs_seite_bauen(self):
        from PySide6.QtWidgets import QScrollArea
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(8)
        kopf = QHBoxLayout(); kopf.setSpacing(10)
        titel = QLabel(t("INDUSTRY JOBS"))
        titel.setStyleSheet(f"font-size:13px; letter-spacing:2px; font-weight:800; "
                            f"color:{theme.GREEN};")
        kopf.addWidget(titel)
        # Legende in EIGENER Zeile (pruefe.py 02.10.2026, Windows: Titel +
        # Legende + Knopf in einer Zeile machten die Seite 1'306 px breit,
        # b66 rot - Texte sind dort ~1,6x breiter als offscreen hier).
        legende = QHBoxLayout(); legende.setSpacing(10)
        # Legende: dieselben Farben wie in den Karten.
        for _art, _txt_l in (("mfg", t("Manufacturing")), ("react", t("Reaction")),
                             ("sci", t("Science"))):
            _lg = QLabel(f'<span style="color:{self._jobs_farbe(_art)};">\u25a0</span> {_txt_l}')
            _lg.setStyleSheet(f"color:{theme.MUTED}; font-size:{theme.FS_SMALL};")
            legende.addWidget(_lg)
        _lgf = QLabel(f'<span style="color:{theme.GREEN};">\u25a0</span> '
                      + t("ready to deliver \u2713"))
        _lgf.setStyleSheet(f"color:{theme.MUTED}; font-size:{theme.FS_SMALL};")
        legende.addWidget(_lgf)
        legende.addStretch()
        kopf.addStretch()
        self._jobs_stand_lbl = QLabel("")
        self._jobs_stand_lbl.setObjectName("Muted")
        kopf.addWidget(self._jobs_stand_lbl)
        self._jobs_refresh_btn = QPushButton(t("Refresh"))
        self._jobs_refresh_btn.setIcon(icons.icon("refresh"))
        self._jobs_refresh_btn.setStyleSheet(theme.amber_rahmen_knopf())
        self._jobs_refresh_btn.clicked.connect(lambda: self._jobs_laden())
        kopf.addWidget(self._jobs_refresh_btn)
        v.addLayout(kopf)
        v.addLayout(legende)
        hinweis = QLabel(t("All linked characters: busy and free job slots, and every "
                           "running job with what it builds and how long it still "
                           "takes. A finished job keeps its slot until you deliver it."))
        hinweis.setObjectName("Muted"); hinweis.setWordWrap(True)
        v.addWidget(hinweis)
        # GESAMT-LEISTE (emm334): fertige Jobs, freie Slots, naechster Job -
        # ueber alle EINGESCHALTETEN Charaktere, auf einen Blick. emm346
        # (Nutzer: "den Text mehr in eine Grafik umwandeln, damit man schoen
        # sieht, wie viele Slots frei sind"): KACHELN - fertig, je Slot-Art
        # die freie Zahl gross mit Balken ueber alle Slots, naechster Job.
        self._jobs_summe_box = QWidget()
        _sb = QHBoxLayout(self._jobs_summe_box)
        _sb.setContentsMargins(0, 0, 0, 0); _sb.setSpacing(10)
        self._jobs_kacheln = {}
        for _schl, _titel, _farbe in (("ready", t("READY"), theme.GREEN),
                                      ("mfg", t("MANUFACTURING"), self._jobs_farbe("mfg")),
                                      ("react", t("REACTIONS"), self._jobs_farbe("react")),
                                      ("sci", t("SCIENCE"), self._jobs_farbe("sci")),
                                      ("next", t("NEXT DONE"), theme.CYAN)):
            _bal = KapazitaetsBalken(_farbe) if _schl in ("mfg", "react", "sci") else None
            _k, _zl, _ul = self._industrie_kachel(_titel, _farbe, balken=_bal)
            _sb.addWidget(_k, 1)
            self._jobs_kacheln[_schl] = {"rahmen": _k, "zahl": _zl, "balken": _bal,
                                         "unter": _ul}
        v.addWidget(self._jobs_summe_box)
        self._jobs_summe_lbl = QLabel("")
        self._jobs_summe_lbl.setTextFormat(Qt.RichText)
        self._jobs_summe_lbl.setWordWrap(True)
        self._jobs_summe_lbl.setStyleSheet(f"font-size:{theme.FS_SMALL};")
        v.addWidget(self._jobs_summe_lbl)
        body = QHBoxLayout(); body.setSpacing(12)
        self._jobs_raster = KartenRaster(breite=380)
        _sc = QScrollArea(); _sc.setWidgetResizable(True)
        _sc.setFrameShape(QScrollArea.NoFrame)
        _sc.setWidget(self._jobs_raster)
        body.addWidget(_sc, 1)
        # CHARAKTERE AN/AUS (emm334, Nutzer: "verlinkte Charaktere, die man
        # nicht sehen moechte, ausblenden ... rechts eine Charakter-Uebersicht
        # mit On/Off, standardmaessig alle On"). Gemerkt in
        # settings["jobs_chars_aus"] (die AUSgeschalteten) - neue Charaktere
        # sind damit von selbst an.
        panel = QFrame(); panel.setObjectName("Card")
        panel.setFixedWidth(230)
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(10, 10, 10, 10); pv.setSpacing(6)
        _pt = QLabel(t("CHARACTERS"))
        _pt.setStyleSheet(f"font-size:13px; letter-spacing:2px; font-weight:800; "
                          f"color:{theme.CYAN};")
        pv.addWidget(_pt)
        self._jobs_schalter_box = QVBoxLayout(); self._jobs_schalter_box.setSpacing(4)
        pv.addLayout(self._jobs_schalter_box)
        self._jobs_alle_btn = QPushButton(t("All on"))
        self._jobs_alle_btn.clicked.connect(lambda: self._jobs_alle_an())
        pv.addWidget(self._jobs_alle_btn)
        pv.addStretch()
        body.addWidget(panel)
        v.addLayout(body, 1)
        self._jobs_daten = None          # {"chars": {...}} nach dem ersten Laden
        self._jobs_stand_ts = 0.0
        self._jobs_laeuft = False
        self._jobs_karten = {}           # {cid: Karte} - b-Suite
        self._jobs_schalter = {}         # {cid: Knopf} - b-Suite
        self._jobs_uhr_teile = []        # [(Gruppe, Restzeit-Label, JobZeile)]
        # DIE RESTZEIT LAEUFT MIT, OHNE NEUEN ABRUF: einmal je Minute werden
        # Restzeit und Balken aus dem gemerkten Ende neu gerechnet.
        self._jobs_uhr = QTimer(page)
        self._jobs_uhr.setInterval(60_000)
        self._jobs_uhr.timeout.connect(lambda: self._jobs_rest_auffrischen())
        self._jobs_uhr.start()
        return page

    def _jobs_seite_gezeigt(self):
        """Aus _bau_nav(4): beim ersten Zeigen und wenn der Stand aelter als
        5 min ist, im Hintergrund neu laden (ESI cacht Jobs ohnehin ~5 min)."""
        import time as _t
        if self._jobs_daten is None or _t.time() - self._jobs_stand_ts > 300:
            self._jobs_laden()

    def _jobs_laden(self):
        if getattr(self, "_jobs_laeuft", False):
            return
        client_id = self.settings.get("client_id")
        chars = store.list_characters()
        if not client_id or not chars:
            self._jobs_stand_lbl.setText(t("No characters linked."))
            return
        slots_alt = dict(self.settings.get("bau_char_slots") or {})

        def job():
            from .mw_helpers import jobs_uebersicht, corp_jobs_verteilen
            import time as _t
            out, tids = {}, set()
            jetzt = _t.time()
            roh, mx_je = {}, {}
            for ch in chars:
                cid = int(ch["character_id"])
                e = {"name": ch.get("character_name") or ch.get("name") or str(cid),
                     "fehler": None, "ueb": None}
                mx = None
                try:
                    mx = industry.job_slots(esi.fetch_skills(client_id, cid))
                except Exception:
                    mx = slots_alt.get(str(cid))   # zuletzt geladene Slots
                try:
                    jobs = esi.fetch_active_jobs(client_id, cid)
                except Exception as ex:
                    e["fehler"] = str(ex)[:120]
                    jobs = []
                roh[cid], mx_je[cid] = jobs, mx
                out[cid] = e
            # CORP-JOBS (emm389, Discord HerrLades: "it only shows private
            # jobs?"): mit dem Corp-Schalter und Factory_Manager kommen die
            # Corp-Jobs dazu - sie laufen auf den SLOTS des startenden
            # Charakters (installer_id), zaehlen also in DESSEN Karte mit;
            # dazu je Corp eine eigene Karte mit ALLEN Corp-Jobs.
            if self.settings.get("use_corp"):
                _co = {"ohne_rolle": [], "relink": [], "failed": [],
                       "keine_division": False, "aktiv": True, "bp_ok": True}
                try:
                    _, _, plan_jobs = self._corp_rollen(client_id, chars, _co)
                except Exception:
                    plan_jobs = {}
                _bekannt = {j.get("job_id") for js in roh.values() for j in js}
                for corp_id, via_cid in sorted((plan_jobs or {}).items()):
                    ec = {"name": "", "fehler": None, "ueb": None, "ist_corp": True}
                    try:
                        cjobs = esi.fetch_corporation_jobs(client_id, via_cid, corp_id)
                    except Exception as ex:
                        ec["fehler"] = str(ex)[:120]
                        cjobs = []
                    try:
                        ec["name"] = t("Corp: {name}").format(
                            name=esi.fetch_corporation_name(corp_id))
                    except Exception:
                        ec["name"] = t("Corp: {name}").format(name=f"#{corp_id}")
                    je_cid, _rest = corp_jobs_verteilen(cjobs, list(roh), _bekannt)
                    for _c, _js in je_cid.items():
                        roh[_c] = list(roh[_c]) + _js
                    # NUR die uebrigen Jobs (fremde Installer) auf die
                    # Corp-Karte (emm396, Nutzer: "es sind die selben Jobs
                    # Lezaar und corp" - vorher standen ALLE Corp-Jobs dort,
                    # der Job eines verknuepften Installers damit doppelt).
                    # Ohne uebrige Jobs und ohne Fehler faellt die Karte weg
                    # (eine leere "no running jobs"-Corp-Karte wuerde luegen,
                    # die Jobs laufen ja - auf den Charakter-Karten).
                    ec["ueb"] = jobs_uebersicht(_rest, None, jetzt)
                    if _rest or ec["fehler"]:
                        out[-int(corp_id)] = ec
            for cid in roh:
                out[cid]["ueb"] = jobs_uebersicht(roh[cid], mx_je[cid], jetzt)
            for e in out.values():
                tids.update(z["tid"] for z in (e["ueb"] or {}).get("zeilen", ())
                            if z["tid"])
            try:
                namen = esi.resolve_names(list(tids)) if tids else {}
            except Exception:
                namen = store.cached_names(list(tids)) if tids else {}
            return {"chars": out, "namen": namen, "ts": jetzt}

        def done(res):
            self._jobs_laeuft = False
            self._jobs_daten = res
            self._jobs_stand_ts = res.get("ts") or 0.0
            self._jobs_zeichnen()

        def fail(_err):
            self._jobs_laeuft = False
            self._jobs_stand_lbl.setText(t("Loading jobs failed."))

        self._jobs_laeuft = True
        self._jobs_stand_lbl.setText(t("Loading jobs …"))
        self._run(Worker(job), done, fail, overlay=False)

    def _jobs_ende_text(self, ende):
        if not ende:
            return "—"
        from datetime import datetime as _dt
        return _dt.fromtimestamp(ende).strftime("%d.%m. %H:%M")

    def _jobs_rest_text(self, g):
        from .mw_helpers import jobs_dauer_kurz
        if g.get("ready"):
            return t("ready to deliver \u2713")
        if g.get("paused"):
            return t("paused")
        if g.get("rest") is None:
            return "\u2014"
        return jobs_dauer_kurz(g["rest"])

    # Kuerzel je Aktivitaet in der Job-Zeile (emm334); der volle Name steht
    # im Tooltip.
    _JOB_KUERZEL = {1: "Mfg.", 3: "TE", 4: "ME", 5: "Copy", 7: "RE", 8: "Inv",
                    9: "React.", 11: "React."}

    def _jobs_slot_gruppe(self, label, art, belegt, fertig, maximum):
        box = QVBoxLayout(); box.setSpacing(2)
        zahl = f"{belegt}/{maximum}" if maximum is not None else str(belegt)
        _frei = (maximum is not None and belegt < maximum)
        lb = QLabel(f'{label} <span style="font-family:{theme.MONO}; color:'
                    f'{theme.GREEN if _frei else theme.MUTED};">{zahl}</span>')
        lb.setTextFormat(Qt.RichText)
        lb.setStyleSheet(f"color:{theme.MUTED}; font-size:13px;")
        box.addWidget(lb)
        # GROESSER (emm338, Nutzer: "dafuer etwas groesser und sichtbarer"):
        # Kaestchen bis 10 px bei 2 px Abstand, Zahl in normaler Groesse.
        sk = SlotKaestchen(belegt - fertig, fertig, maximum, self._jobs_farbe(art),
                           breite=104, abstand=2)
        box.addWidget(sk)
        return box, sk

    def _jobs_karte(self, cid, e, namen, jetzt):
        from .mw_helpers import jobs_einzeln, job_anzeigename
        card = QFrame(); card.setObjectName("Card")
        card.setMinimumWidth(360)
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10); v.setSpacing(5)
        u = e["ueb"]
        gr = jobs_einzeln(u["zeilen"], jetzt)
        card._gruppen = gr
        kopf = QHBoxLayout(); kopf.setSpacing(8)
        name = QLabel(str(e["name"]))
        name.setStyleSheet(f"color:{theme.CYAN}; font-weight:800; font-size:{theme.FS_H2};")
        kopf.addWidget(name)
        kopf.addStretch()
        _n_fertig = sum(g["n"] for g in gr["ready"])
        # CORP-ABZEICHEN IM KOPF (emm398, Nutzer: "wenn zugeklappt sieht man
        # nicht dass ein Corpjob laeuft"): laufende + fertige Corp-Jobs
        # dieser Karte, sichtbar auch bei zugeklappter Job-Liste. Nicht auf
        # der Corp-Karte selbst (dort ist alles Corp, der Kopf ist amber).
        card._corp_badge = None
        _n_corp = (sum(g["n"] for g in gr["laufend"] if g.get("corp"))
                   + sum(g["n"] for g in gr["ready"] if g.get("corp")))
        if _n_corp and not e.get("ist_corp"):
            _cb = QLabel(t("Corp") if _n_corp == 1 else f"{t('Corp')} {_n_corp}")
            _cb.setToolTip(t("{n} corp job(s) \u2013 they run on this "
                             "character's job slots.").format(n=_n_corp))
            _cb.setStyleSheet(f"color:{theme.AMBER}; border:1px solid {theme.AMBER}; "
                              f"border-radius:4px; padding:1px 7px; "
                              f"font-size:{theme.FS_SMALL}; font-weight:800; "
                              f"background:transparent;")
            kopf.addWidget(_cb)
            card._corp_badge = _cb
        if _n_fertig:
            _badge = QLabel(f"\u2713 {_n_fertig}")
            _badge.setToolTip(t("\u2713 {n} ready to deliver").format(n=_n_fertig))
            _badge.setStyleSheet(f"background:{theme.GREEN}; color:{theme.BG}; "
                                 f"font-weight:800; border-radius:4px; padding:1px 7px;")
            kopf.addWidget(_badge)
        v.addLayout(kopf)
        _fertig_je = {"mfg": 0, "react": 0, "sci": 0}
        for z in u["zeilen"]:
            if z["ready"]:
                _fertig_je[z["art"]] += 1
        card._slots = {}
        if e.get("ist_corp"):
            # CORP-KARTE (emm389): die Corp hat keine eigenen Slots - ihre
            # Jobs belegen die Slots des startenden Charakters und zaehlen
            # DORT. Deshalb hier keine Slot-Zeile, nur der Hinweis.
            _ch = QLabel(t("Corp jobs run on the installer's job slots – "
                           "they count on that character's card."))
            _ch.setObjectName("Muted"); _ch.setWordWrap(True)
            v.addWidget(_ch)
            name.setStyleSheet(f"color:{theme.AMBER}; font-weight:800; "
                               f"font-size:{theme.FS_H2};")
        else:
            slots = QHBoxLayout(); slots.setSpacing(12)
            for art, lab in (("mfg", t("Mfg.")), ("react", t("React.")), ("sci", t("Science"))):
                _mx = (u["max"] or {}).get(art) if u["max"] else None
                box, sk = self._jobs_slot_gruppe(lab, art, u["belegt"][art],
                                                 _fertig_je[art], _mx)
                card._slots[art] = sk
                slots.addLayout(box)
            slots.addStretch()
            v.addLayout(slots)
        if e["fehler"]:
            fz = QLabel(t("ESI error: {e}").format(e=e["fehler"]))
            fz.setWordWrap(True)
            fz.setStyleSheet(f"color:{theme.RED};")
            v.addWidget(fz)
        if gr["ready"]:
            rk = QLabel(t("\u2713 {n} ready to deliver").format(n=_n_fertig))
            rk.setStyleSheet(f"color:{theme.GREEN}; font-weight:700; padding-top:4px;")
            v.addWidget(rk)
            # Fertig-Zeile mit Corp-Marke (emm397, Nutzer "ja"): ein fertiger
            # Corp-Job traegt sein amber "Corp" auch hier - Rich-Text, weil
            # die Zeile EIN Label ist (Namen escaped, Marke als Span).
            from html import escape as _esc
            _rt = []
            for g in gr["ready"]:
                _s = f"{g['n']}\u00d7 " + _esc(
                    str(namen.get(g["tid"]) or "#" + str(g["tid"])))
                if g.get("corp"):
                    _s += (f" <span style=\"color:{theme.AMBER}; "
                           f"font-weight:700;\">" + _esc(t("Corp")) + "</span>")
                _rt.append(_s)
            rl = QLabel(" \u00b7 ".join(_rt))
            rl.setTextFormat(Qt.RichText)
            rl.setWordWrap(True)
            rl.setStyleSheet(f"color:{theme.GREEN}; font-size:{theme.FS_SMALL}; "
                             f"padding-left:14px;")
            v.addWidget(rl)
            card._ready_lbl = rl
        # JOBS ZUM AUSKLAPPEN (emm338, Nutzer: "die Fortschrittsbalken als
        # Dropdown zum Ausklappen, damit man standardmaessig nur die Compact-
        # Ansicht von jedem Char hat"). Zustand je Charakter gemerkt
        # (`jobs_karten_offen`, die AUFgeklappten) - Standard zu.
        card._jobs_body = None
        card._jobs_pfeil = None
        if gr["laufend"]:
            _offen = str(cid) in {str(x) for x in
                                  (self.settings.get("jobs_karten_offen") or [])}
            pf = QPushButton()
            pf.setCheckable(True)
            pf.setChecked(_offen)
            # KLICKBAR ERKENNEN (emm347, Nutzer: "beim Mouseover soll man
            # erkennen, dass es etwas zum Anklicken ist"): Hand-Cursor, beim
            # Darueberfahren cyan Rand + hellere Flaeche, Tooltip.
            pf.setCursor(Qt.PointingHandCursor)
            pf.setToolTip(t("Click to show or hide the running jobs"))
            pf.setStyleSheet(
                f"QPushButton{{text-align:left; background:{theme.PANEL2}; "
                f"color:{theme.TEXT}; border:1px solid {theme.BORDER}; "
                f"border-radius:4px; padding:3px 8px; font-weight:700;}}"
                f"QPushButton:hover{{background:{theme.CYAN_FILL}; "
                f"border:1px solid {theme.CYAN}; color:{theme.CYAN};}}"
                f"QPushButton:checked{{border:1px solid {theme.CYAN};}}"
                f"QPushButton:checked:hover{{background:{theme.CYAN_FILL_HOVER};}}")
            _n_lauf = len(gr["laufend"])

            def _pfeil_text(on, _n=_n_lauf, _b=pf):
                _b.setText(("\u25be " if on else "\u25b8 ")
                           + t("{n} running job(s)").format(n=_n))
            _pfeil_text(_offen)
            v.addWidget(pf)
            body = QWidget()
            bv = QVBoxLayout(body)
            bv.setContentsMargins(0, 2, 0, 0); bv.setSpacing(4)
            for g in gr["laufend"]:
                farbe = self._jobs_farbe(g["art"])
                nm = job_anzeigename(namen.get(g["tid"]) or f"#{g['tid']}", g["activity_id"])
                zeile = JobZeile(t(self._JOB_KUERZEL.get(int(g["activity_id"] or 0), "?")),
                                 t("{name} ({n} runs)").format(name=nm, n=g["runs"]),
                                 self._jobs_rest_text(g), farbe,
                                 corp=bool(g.get("corp")))   # emm396: amber Corp-Abzeichen
                zeile.setMinimumHeight(26)
                _tip = [str(namen.get(g["tid"]) or g["tid"]),
                        self._jobs_art_name(g["activity_id"]),
                        t("{n} job(s) \u00b7 {r} runs").format(n=g["n"], r=g["runs"])]
                _tip += [self._jobs_ende_text(_e) for _e in g["enden"]]
                zeile.setToolTip("\n".join(_tip))
                zeile.name.setToolTip("\n".join(_tip))
                if g["paused"]:
                    zeile.rest.setStyleSheet(f"font-family:{theme.MONO}; color:{theme.AMBER}; "
                                             f"background:transparent;")
                zeile.setValue(int(round((g.get("fortschritt") or 0.0) * 1000)))
                bv.addWidget(zeile)
                self._jobs_uhr_teile.append((g, zeile.rest, zeile))
            v.addWidget(body)
            body.setVisible(_offen)          # erst im Layout, dann schalten (b8)
            pf.toggled.connect(lambda on, _c=cid, _bd=body, _f=_pfeil_text:
                               self._jobs_karte_klappen(_c, on, _bd, _f))
            card._jobs_body = body
            card._jobs_pfeil = pf
        if not gr["ready"] and not gr["laufend"] and not e["fehler"]:
            lz = QLabel(t("no running jobs"))
            lz.setStyleSheet(f"color:{theme.MUTED};")
            v.addWidget(lz)
        v.addStretch()
        return card

    def _jobs_karte_klappen(self, cid, on, body, pfeil_text):
        body.setVisible(bool(on))
        pfeil_text(bool(on))
        offen = {str(x) for x in (self.settings.get("jobs_karten_offen") or [])}
        if on:
            offen.add(str(cid))
        else:
            offen.discard(str(cid))
        self.settings["jobs_karten_offen"] = sorted(offen)
        config.save_settings_async(self.settings)

    def _jobs_aus(self):
        return {str(x) for x in (self.settings.get("jobs_chars_aus") or [])}

    def _jobs_schalter_stil(self, btn, an):
        btn.setText(t("On") if an else t("Off"))
        btn.setStyleSheet(
            f"QPushButton{{background:{theme.GREEN}; color:{theme.BG}; font-weight:800; "
            f"border:1px solid {theme.GREEN}; border-radius:4px; padding:2px 6px;}}"
            if an else
            f"QPushButton{{background:transparent; color:{theme.MUTED}; "
            f"border:1px solid {theme.BORDER}; border-radius:4px; padding:2px 6px;}}")

    def _jobs_schalter_bauen(self, chars):
        """Eine Zeile je verlinktem Charakter: Name + An/Aus-Knopf."""
        box = self._jobs_schalter_box
        while box.count():
            it = box.takeAt(0)
            _w = it.widget()
            if _w is not None:
                _w.deleteLater()
            elif it.layout() is not None:
                while it.layout().count():
                    _x = it.layout().takeAt(0).widget()
                    if _x is not None:
                        _x.deleteLater()
        self._jobs_schalter = {}
        aus = self._jobs_aus()
        for cid, e in sorted((chars or {}).items(),
                             key=lambda kv: str(kv[1].get("name") or "").lower()):
            row = QHBoxLayout(); row.setSpacing(6)
            nl = KurzLabel(str(e.get("name") or cid))
            row.addWidget(nl, 1)
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedWidth(52)
            _an = str(cid) not in aus
            btn.setChecked(_an)
            self._jobs_schalter_stil(btn, _an)
            btn.toggled.connect(lambda an, _c=cid: self._jobs_char_schalten(_c, an))
            row.addWidget(btn)
            box.addLayout(row)
            self._jobs_schalter[int(cid)] = btn
        self._jobs_schalter_cids = set(int(c) for c in (chars or {}))

    def _jobs_char_schalten(self, cid, an):
        aus = self._jobs_aus()
        if an:
            aus.discard(str(cid))
        else:
            aus.add(str(cid))
        self.settings["jobs_chars_aus"] = sorted(aus)
        config.save_settings_async(self.settings)
        _b = (getattr(self, "_jobs_schalter", None) or {}).get(int(cid))
        if _b is not None:
            self._jobs_schalter_stil(_b, an)
        self._jobs_karten_zeichnen()

    def _jobs_alle_an(self):
        self.settings["jobs_chars_aus"] = []
        config.save_settings_async(self.settings)
        for _b in (getattr(self, "_jobs_schalter", None) or {}).values():
            _b.blockSignals(True)
            _b.setChecked(True)
            _b.blockSignals(False)
            self._jobs_schalter_stil(_b, True)
        self._jobs_karten_zeichnen()

    def _jobs_zeichnen(self):
        d = self._jobs_daten or {}
        _chars = d.get("chars") or {}
        if set(int(c) for c in _chars) != getattr(self, "_jobs_schalter_cids", None):
            self._jobs_schalter_bauen(_chars)
        self._jobs_karten_zeichnen()
        if not _chars:
            self._jobs_stand_lbl.setText(t("No characters linked."))
            return
        from datetime import datetime as _dt
        self._jobs_stand_lbl.setText(t("as of {zeit}").format(
            zeit=_dt.fromtimestamp(self._jobs_stand_ts or 0).strftime("%H:%M")))

    def _jobs_karten_zeichnen(self):
        import time as _t
        from .mw_helpers import jobs_karten_folge, jobs_sichtbar
        d = self._jobs_daten or {}
        namen = d.get("namen") or {}
        self._jobs_uhr_teile = []
        self._jobs_karten = {}
        jetzt = self._jobs_stand_ts or _t.time()
        alle = d.get("chars") or {}
        _chars = jobs_sichtbar(alle, self.settings.get("jobs_chars_aus"))
        karten = []
        for cid in jobs_karten_folge(_chars):
            k = self._jobs_karte(cid, _chars[cid], namen, jetzt)
            self._jobs_karten[int(cid)] = k
            karten.append(k)
        self._jobs_raster.setze(karten)
        self._jobs_summe_zeigen(_chars, len(alle) - len(_chars), jetzt)
        self._jobs_rest_auffrischen()

    def _jobs_summe_zeigen(self, chars, versteckt, jetzt):
        from .mw_helpers import jobs_summe, jobs_dauer_kurz, jobs_kapazitaet
        # OHNE die Corp-Karten (emm389): deren Jobs stecken schon in den
        # Charakter-Karten der Installer - sie doppelt zu zaehlen wuerde die
        # Kacheln verfaelschen.
        chars = {k: v for k, v in (chars or {}).items() if not v.get("ist_corp")}
        if not chars and not versteckt:
            self._jobs_summe_lbl.setText("")
            self._jobs_summe_lbl.hide()
            self._jobs_summe_box.hide()
            return
        su = jobs_summe(chars, jetzt)
        ka = jobs_kapazitaet(chars)
        self._jobs_summe = su                       # b-Suite
        self._jobs_kapazitaet = ka                  # b-Suite
        kc = self._jobs_kacheln
        _farbe_f = theme.GREEN if su["ready"] else theme.MUTED
        kc["ready"]["zahl"].setText(
            f'<span style="color:{_farbe_f};">\u2713 {su["ready"]}</span>')
        kc["ready"]["unter"].setText(t("ready to deliver"))
        for art in ("mfg", "react", "sci"):
            a = ka[art]
            _fa = self._jobs_farbe(art) if a["free"] else theme.MUTED
            kc[art]["zahl"].setText(
                f'<span style="color:{_fa};">{a["free"]}</span>'
                f'<span style="color:{theme.MUTED}; font-size:{theme.FS_BASE}; '
                f'font-weight:400;"> {t("free slots")}</span>')
            kc[art]["balken"].setze(a["running"], a["ready"], a["max"])
            kc[art]["unter"].setText(
                t("{r} running \u00b7 {f} ready \u00b7 {m} slots").format(
                    r=a["running"], f=a["ready"], m=a["max"]))
        if su["next"] is not None:
            kc["next"]["zahl"].setText(jobs_dauer_kurz(su["next"][0]))
            kc["next"]["unter"].setText(su["next"][1])
        else:
            kc["next"]["zahl"].setText("\u2013")
            kc["next"]["unter"].setText("")
        self._jobs_summe_box.show()
        teile = []
        if su.get("no_max"):
            teile.append(t("{n} character(s) without known slot maximum (skills not "
                           "loaded) \u2013 not counted in the slots.").format(n=su["no_max"]))
        if versteckt:
            teile.append(t("{n} character(s) hidden").format(n=versteckt))
        self._jobs_summe_lbl.setText(
            f'<span style="color:{theme.MUTED};">' + "  \u00b7  ".join(teile) + "</span>")
        self._jobs_summe_lbl.setVisible(bool(teile))

    def _jobs_rest_auffrischen(self, jetzt=None):
        """Nur Restzeit und Balken neu rechnen (Uhr, ohne ESI)."""
        import time as _t
        from .mw_helpers import job_fortschritt
        jetzt = _t.time() if jetzt is None else jetzt
        for g, lbl, bar in list(getattr(self, "_jobs_uhr_teile", []) or []):
            try:
                if g.get("ende") is not None and not g.get("paused"):
                    g["rest"] = max(0, int(g["ende"] - jetzt))
                    if g["rest"] == 0:
                        g["ready"] = True
                        lbl.setStyleSheet(f"font-family:{theme.MONO}; color:{theme.GREEN}; "
                                          f"background:transparent;")
                    _f = job_fortschritt(g.get("start"), g["ende"], jetzt)
                    if _f is not None:
                        bar.setValue(int(round(_f * 1000)))
                lbl.setText(self._jobs_rest_text(g))
            except RuntimeError:
                pass          # Karte schon geloescht (neu gezeichnet)

    def _build_build_tab(self):
        w = QWidget()
        outer = QHBoxLayout(w)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.b_stack = QStackedWidget()
        outer.addWidget(self._roll_mitte(self.b_stack), 1)

        # Seite „Scanner“ – die Haupt-Arbeitsansicht (Tabelle + Filter)
        scan_page = QWidget()
        # BAUPLAN-MUSTER (Nutzer: "Strategie offen, Feinfilter geschlossen,
        # rechts am Rand wie im Bauplan - dann kann die Itemliste hoeher
        # sein"): links die Liste in voller Hoehe, rechts eine schmale
        # Spalte mit den Einstell-Karten. `root` bleibt der LINKE Strang,
        # damit alle bestehenden root.addWidget-Stellen (Status, Tabelle,
        # Capital-Karte) unveraendert weiterfunktionieren; die Karten
        # wandern unten explizit in `b_side` statt in `root`.
        _sp = QHBoxLayout(scan_page)
        _sp.setContentsMargins(14, 8, 14, 8)
        _sp.setSpacing(10)
        _left = QWidget()
        root = QVBoxLayout(_left)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(7)
        _side_w = QWidget()
        _side_w.setFixedWidth(380)
        self.b_side = QVBoxLayout(_side_w)
        self.b_side.setContentsMargins(0, 0, 0, 0)
        self.b_side.setSpacing(7)
        _sp.addWidget(_left, 1)
        _sp.addWidget(_side_w, 0, Qt.AlignTop)

        # Seite „Setup“ – Profil + Bau-Setup + Blacklist (einmal einstellen)
        setup_page = QWidget()
        sroot = QVBoxLayout(setup_page)
        sroot.setContentsMargins(14, 8, 14, 8)
        sroot.setSpacing(7)

        # hub + scan live in the top toolbar now; keep objects as synced state only
        self.b_hub = QComboBox()
        for _key, _label, _region_id, _station_id in hubs.NPC_HUBS:
            self.b_hub.addItem(_label, _region_id)
        self.b_hub.currentIndexChanged.connect(self._on_hub_change_build)
        self.b_scan_btn = QPushButton(t("Market scan"))
        self.b_scan_btn.setIcon(icons.icon("satellite"))
        self.b_scan_btn.clicked.connect(self.scan_build)
        self.b_preset = QComboBox()
        self.b_preset.setMinimumWidth(230)
        for label, p in self._BUILD_PRESETS:
            # Symbol aus dem Preset (Sitzung 11) - hier fehlte es ganz.
            _sym = (p or {}).get("sym")
            if _sym:
                try:
                    # Sitzung 17: t() beim Einfuegen (Schluessel englisch)
                    self.b_preset.addItem(icons.icon(_sym), t(label), p)
                    continue
                except Exception:
                    pass
            # Der neutrale Eintrag kommt als SCHLUESSEL aus der
            # Klassen-Konstante - hier uebersetzen, nicht dort.
            self.b_preset.addItem(t(label) if p is None else label, p)
        self.b_preset.currentIndexChanged.connect(self._apply_build_preset)
        self.b_load_btn = QPushButton(t("Load recipes"))   # kept for load_sde refs
        self.b_load_btn.setIcon(icons.icon("blueprint"))
        self.b_load_btn.clicked.connect(self.load_sde)
        # GEZEICHNETES SYMBOL STATT EMOJI (Nutzer-Fund Sitzung 16, "wir machen
        # keine Emojis in dem Tool"). Das Emoji sah je nach Emoji-Schriftart
        # des Betriebssystems anders aus als der Rest; icons.icon() liefert
        # dasselbe Set wie ueberall sonst. Der TEXT bleibt sauber - daran
        # haengen Suche, Screenreader und die Prueftexte.
        self.b_compute_btn = QPushButton(t("Find blueprints"))
        self.b_compute_btn.setIcon(icons.icon("search"))
        self.b_compute_btn.clicked.connect(self.compute_build)
        # Primaer-Stil (cyan): das ist DER Ausloese-Knopf des Tabs.
        self.b_compute_btn.setStyleSheet(
            f"QPushButton{{background:{theme.CYAN_FILL}; color:{theme.CYAN}; "
            f"border:none; border-radius:6px; font-weight:800; "
            f"padding:6px 14px;}}"
            f"QPushButton:hover{{background:{theme.BLUE};}}")

        # ---- STRATEGIE-KARTE: Preset + Blaupausen-Suche, gleiche Optik wie bei
        # Daytrade/Swing (dort: Modus + Preset) ------------------------------
        strat = QFrame(); strat.setObjectName("StrategyCard")
        strat.setStyleSheet(
            f"#StrategyCard {{ background:{theme.PANEL2}; border:1px solid "
            f"{theme.CYAN}; border-radius:10px; }}")
        sg = QGridLayout(strat)
        sg.setContentsMargins(16, 12, 16, 12)
        sg.setHorizontalSpacing(14); sg.setVerticalSpacing(8)
        b_strat_title = QLabel(t("What you want to build"))
        b_strat_title.setStyleSheet(f"color:{theme.CYAN}; font-size:13px; "
                                    f"font-weight:700; letter-spacing:1px;")
        # dito - gezeichnetes Symbol statt Emoji (Sitzung 16).
        self.b_cap_mode = QPushButton(t("Capital mode"))
        self.b_cap_mode.setIcon(icons.icon("satellite"))
        self.b_cap_mode.setCheckable(True)
        self.b_cap_mode.setToolTip(t(
            "Hides the normal result list and fine filters and shows "
              "ONLY the capital ships "
              "(carrier/dreadnought/FAX/titan/supercarrier/freighter) "
              "filling the window – since capitals have no market "
              "price, they need different filters anyway. Right-click "
              "a ship to open its build plan directly."))
        self.b_cap_mode.setStyleSheet(
            f"QPushButton{{background:{theme.PANEL2}; border:1px solid {theme.BORDER}; "
            f"border-radius:6px; color:{theme.MUTED}; font-weight:700; padding:6px 12px;}} "
            f"QPushButton:checked{{background:{theme.CYAN_FILL}; "
            f"color:{theme.CYAN}; "
            f"border-color:{theme.CYAN};}}")
        # BEIM START IMMER AUS (Nutzer, 15.09.2026: "die Gefahr ist gross,
        # dass man vergisst da herauszugehen, bevor man das Tool schliesst,
        # und dann ist man verwirrt, warum man keine normalen Blueprints
        # suchen kann"). Der Zustand wird deshalb BEWUSST NICHT gespeichert -
        # der Capital-Modus ist etwas fuer Fortgeschrittene und soll nie der
        # Zustand sein, in dem man das Programm unbemerkt vorfindet.
        # Ausdruecklich gesetzt statt sich auf den Qt-Standard zu verlassen:
        # so steht die Zusage im Code und kann geprueft werden (b7i).
        self.b_cap_mode.setChecked(False)
        self.b_cap_mode.toggled.connect(self._toggle_capital_mode)
        # SCHMALE SPALTE: Titel allein oben, die beiden Knoepfe als eigene
        # Zeile in voller Breite darunter (Titel + zwei Knoepfe nebeneinander
        # wuerden bei 380 px quetschen). "Blaupausen suchen" bekommt den
        # Stretch - der Primaer-Knopf darf der breiteste sein.
        title_row = QHBoxLayout(); title_row.setContentsMargins(0, 0, 0, 0)
        title_row.setSpacing(8)
        title_row.addWidget(b_strat_title, 1)
        sg.addLayout(title_row, 0, 0, 1, 2)
        btn_row = QHBoxLayout(); btn_row.setContentsMargins(0, 0, 0, 0)
        btn_row.setSpacing(8)
        btn_row.addWidget(self.b_compute_btn, 1)
        btn_row.addWidget(self.b_cap_mode)
        sg.addLayout(btn_row, 3, 0, 1, 2)

        # BLAUPAUSEN-TIPPFELD + BAUPLAN-KNOPF ENTFERNT (Nutzer: "kann weg").
        # Beide Wege existieren woanders sauberer: Rechtsklick auf einen
        # Treffer oeffnet den Bauplan direkt, und "Neuer Bauplan" in der
        # rechten Leiste hat die volle Tipp-Suche. Zwei Eingaenge fuer
        # dieselbe Sache waren Redundanz, kein Komfort. Die Karte traegt
        # jetzt nur noch das Preset.
        b_plab = QLabel(t("Preset"))
        b_plab.setStyleSheet(f"color:{theme.TEXT}; font-size:15px; font-weight:600;")
        self.b_preset.setMinimumHeight(34)
        self.b_preset.setStyleSheet("font-size:15px; padding:2px 8px;")
        sg.addWidget(b_plab, 1, 0)
        sg.addWidget(self.b_preset, 2, 0)
        # DAUERTEXT ENTFERNT (Nutzer: "so textfrei und sauber wie der
        # Bauplan") - die Aussage steht als Tooltip am Element selbst.
        self.b_preset.setToolTip(t("Sets the fine filters automatically."))
        sg.setColumnStretch(0, 1)
        b_strat_card = self._collapsible(t("STRATEGY"), strat, accent=theme.CYAN)

        # ---- Profil: gesamtes Bau-Setup speichern / laden -----------------------
        prow = QHBoxLayout()
        pl = QLabel(t("Profile:")); pl.setObjectName("Muted")
        prow.addWidget(pl)
        self.bs_profile = QComboBox(); self.bs_profile.setMinimumWidth(240)
        self.bs_profile.setToolTip(t(
            "Save and load the whole build setup (system, structure, "
              "rigs, ME/TE, decryptor, surplus …) as a profile – so "
              "you do not have to set everything up again."))
        prow.addWidget(self.bs_profile)
        pload = QPushButton(t("Load")); pload.clicked.connect(self._load_bau_profile)
        pload.setIcon(icons.icon("package"))
        prow.addWidget(pload)
        psave = QPushButton(t("Save as \u2026"))
        psave.setIcon(icons.icon("check"))
        psave.clicked.connect(self._save_bau_profile)
        prow.addWidget(psave)
        pdel = QPushButton(t("Delete")); pdel.clicked.connect(self._delete_bau_profile)
        pdel.setIcon(icons.icon("trash"))
        prow.addWidget(pdel)
        prow.addStretch()
        sroot.addLayout(prow)

        # ---- 🏭 Bau-Setup: Struktur + Rigs bestimmen ME/Zeit/Job-Kosten ----------
        setup = QFrame(); setup.setObjectName("Card")
        sg = QGridLayout(setup); sg.setContentsMargins(14, 8, 14, 8)
        sg.setHorizontalSpacing(14); sg.setVerticalSpacing(6)
        stitle = QLabel(t("Manufacturing \u2014 structure & rigs determine material efficiency "
                        "(job cost & build time follow)"))
        stitle.setObjectName("Muted")
        sg.addWidget(stitle, 0, 0, 1, 4)
        self.bs_loc = QComboBox(); self.bs_loc.setMinimumWidth(220)
        self._reload_bau_loc()
        self.bs_sec = QComboBox()
        for lab, v in [("Highsec (×1.0)", 1.0), ("Lowsec (×1.9)", 1.9),
                       ("Null / WH (×2.1)", 2.1)]:
            self.bs_sec.addItem(lab, v)
        self._combo_select(self.bs_sec, float(self.settings.get("bau_security", 1.0)))
        self.bs_ftax = QDoubleSpinBox(); self.bs_ftax.setRange(0, 20)
        self.bs_ftax.setDecimals(2); self.bs_ftax.setSuffix(" %")
        self.bs_ftax.setValue(float(self.settings.get("bau_facility_tax", 0.25)))
        self.bs_ftax.setToolTip(t("Facility tax charged by the structure owner "
                                  "(shown in the structure info). Goes into the job cost."))
        self.bs_bpme = QSpinBox(); self.bs_bpme.setRange(0, 10); self.bs_bpme.setSuffix(" %")
        self.bs_bpme.setValue(int(self.settings.get("bau_me", 10)))
        self.bs_bpme.setToolTip(t("Assumed blueprint material efficiency "
                                  "(fully researched BPO = 10 %)."))
        self.bs_bpte = QSpinBox(); self.bs_bpte.setRange(0, 20); self.bs_bpte.setSuffix(" %")
        self.bs_bpte.setValue(int(self.settings.get("bau_te", 0)))
        self.bs_bpte.setToolTip(t("Blueprint time efficiency (fully researched = 20 %). "
                                  "Reduces build time."))
        self.bs_react = QComboBox()
        self.bs_react.addItem(t("Build reactions yourself"), True)
        self.bs_react.addItem(t("Buy reactions"), False)
        self.bs_react.setCurrentIndex(0 if self.settings.get("bau_reactions", True) else 1)
        self.bs_inv = QComboBox()
        self.bs_inv.addItem(t("Include invention"), True)
        self.bs_inv.addItem(t("Ignore invention"), False)
        self.bs_inv.setCurrentIndex(0)       # emm385: Invention immer an
        self.bs_decry = QComboBox()
        for nm, _v in self._decryptor_list():
            # ANZEIGE uebersetzt, DATEN nicht: `_combo_select` waehlt ueber
            # itemData, und genau dieser Wert wandert in die Einstellungen.
            self.bs_decry.addItem(dec_anzeige(nm), nm)
        self._combo_select(self.bs_decry, self.settings.get("bau_decryptor", KEIN_DECRYPTOR))
        self.bs_decry.setToolTip(t(
            "Decryptor for invention (changes success chance and "
              "runs → invention cost per unit)."))
        from PySide6.QtWidgets import QCompleter
        self.bs_syspick = QComboBox(); self.bs_syspick.setEditable(True)
        self.bs_syspick.setMinimumWidth(150)
        self.bs_syspick.setInsertPolicy(QComboBox.NoInsert)
        self.bs_syspick.completer().setCompletionMode(QCompleter.PopupCompletion)
        self.bs_syspick.completer().setFilterMode(Qt.MatchContains)
        self.bs_syspick.completer().setCaseSensitivity(Qt.CaseInsensitive)
        # BEISPIEL IM TOOLTIP NEUTRAL HALTEN: hier stand "A-DDGY", das
        # Heimatsystem des Entwicklers. In einer oeffentlichen Fassung ist
        # das erstens verwirrend (kein Fremder kennt es) und zweitens eine
        # unnoetige Angabe ueber den, der das Werkzeug gebaut hat. Jita
        # kennt jeder und erklaert dieselbe Sache.
        self.bs_syspick.setToolTip(t("Search for the build system (e.g. type \u201eJita\u201c). "
                                     "Sets the cost index (live from ESI) and the security "
                                     "automatically."))
        for c, (lab, wdg) in enumerate([("System", self.bs_syspick),
                                        (t("Build location (structure)"), self.bs_loc),
                                        (t("Security"), self.bs_sec)]):
            l = QLabel(lab); l.setObjectName("Muted")
            sg.addWidget(l, 1, c); sg.addWidget(wdg, 2, c)
        for c, (lab, wdg) in enumerate([(t("Facility tax"), self.bs_ftax),
                                        (t("Blueprint ME"), self.bs_bpme),
                                        (t("Blueprint TE"), self.bs_bpte),
                                        (t("Reactions"), self.bs_react),
                                        (t("Invention"), self.bs_inv)]):
            l = QLabel(lab); l.setObjectName("Muted")
            sg.addWidget(l, 3, c); sg.addWidget(wdg, 4, c)
        ldc = QLabel(t("Decryptor")); ldc.setObjectName("Muted")
        sg.addWidget(ldc, 5, 0); sg.addWidget(self.bs_decry, 6, 0)
        self.bs_eff = QLabel("")
        self.bs_eff.setStyleSheet(f"color:{theme.AMBER}; font-weight:700; font-size:13px;")
        sg.addWidget(self.bs_eff, 7, 0, 1, 5)
        self.bs_sys = QLabel("")
        self.bs_sys.setObjectName("Muted"); self.bs_sys.setWordWrap(True)
        sg.addWidget(self.bs_sys, 8, 0, 1, 5)
        self.bs_loc.currentIndexChanged.connect(self._on_bau_loc_change)
        self.bs_syspick.activated.connect(self._on_bau_syspick)
        self.bs_syspick.lineEdit().editingFinished.connect(self._on_bau_syspick)
        self.bs_bpme.valueChanged.connect(self._save_bau_setup)
        self.bs_bpte.valueChanged.connect(self._save_bau_setup)
        self.bs_ftax.valueChanged.connect(self._save_bau_setup)
        for wdg in (self.bs_sec, self.bs_react,
                    self.bs_inv, self.bs_decry):
            wdg.currentIndexChanged.connect(self._save_bau_setup)
        self._update_bau_eff()
        self._update_bau_sys()
        # BAU-SETUP wird NICHT mehr angezeigt: System/Sicherheit/Facility-Tax kommen aus
        # der Struktur, ME/TE stellst du im Bauplan, Reaktionen/Invention sind Standard,
        # Decryptor-Wahl steckt im Invention-Tab des Bauplan-Dialogs. Das setup-Widget
        # wird nur noch für gespeicherte Werte + Profile gebaut (Referenz halten, damit
        # bs_* nicht vom Garbage Collector gelöscht werden – NICHT ins Layout gehängt).
        self._bau_setup_hidden = setup
        setup.hide()
        self._reload_bau_profiles()

        ctl = QFrame(); ctl.setObjectName("Card")
        g = QGridLayout(ctl); g.setContentsMargins(14, 6, 14, 6)
        g.setHorizontalSpacing(16); g.setVerticalSpacing(2)
        self.b_cat = QComboBox(); self.b_cat.setMinimumWidth(170)
        self.b_cat.addItem(t("All categories"), None)
        self.b_tech = QComboBox(); self.b_tech.setMinimumWidth(130)
        # WICHTIG: als String-Key speichern, NICHT als Python-Set - QComboBox.
        # findData() (in _apply_build_preset für die Presets gebraucht) vergleicht
        # über QVariant und matcht Sets zuverlässig NIE (immer -1) - das ließ
        # JEDES Preset mit Tech-Filter beim Setzen lautlos auf "Alle baubaren"
        # zurückfallen, ohne Fehlermeldung. String-Keys vergleichen korrekt.
        # "t1" deckt hier auch meta_level 0 ab (in der SDE oft unget) T1-Items).
        for label, key in [(t("All buildable (T1\u2013T3)"), "all"), ("Tech I", "t1"),
                           ("Tech II", "t2"), ("Tech III", "t3")]:
            self.b_tech.addItem(label, key)
        self.b_window = QComboBox()
        for label, days in [(t("{n} days").format(n=_d), _d)
                            for _d in (5, 14, 30, 90, 180)]:
            self.b_window.addItem(label, days)
        self.b_window.setCurrentIndex(2)
        self.b_margin = QDoubleSpinBox(); self.b_margin.setRange(0, 100000)
        self.b_margin.setValue(10); self.b_margin.setSuffix(" %")
        self.b_vol = QSpinBox(); self.b_vol.setRange(0, 10_000_000); self.b_vol.setValue(20)
        self.b_pmin = QSpinBox(); self.b_pmin.setRange(0, 2_000_000_000)
        self.b_pmin.setGroupSeparatorShown(True)
        self.b_pmax = QSpinBox(); self.b_pmax.setRange(0, 2_000_000_000)
        self.b_pmax.setGroupSeparatorShown(True)
        self.b_race = QComboBox(); self.b_race.setMinimumWidth(130)
        self.b_race.addItem(t("All races"), None)
        for rid, rname in sorted(industry.RACE_NAMES.items(), key=lambda x: x[1]):
            self.b_race.addItem(rname, rid)

        self.b_cat.setToolTip(t("Only items of this category (ships, modules, ammo \u2026). "
                                "Needs the SDE \u2013 \u201eLoad recipes\u201c."))
        self.b_tech.setToolTip(t(
            "Tech level. LP/faction items are excluded on principle "
              "because their BPC cost (LP + ISK) cannot be calculated "
              "reliably."))
        self.b_margin.setToolTip(t("Minimum build margin: (sale \u2212 build cost) / "
                                   "build cost. 10 %+ counts as usable, below that it "
                                   "hardly pays."))
        self.b_vol.setToolTip(t("Minimum daily volume \u2013 so you can actually sell what you build."))
        self.b_pmin.setToolTip(t("Only items from this sale price upwards."))
        self.b_pmax.setToolTip(t("Only items up to this sale price (0 = \u221e)."))
        self.b_race.setToolTip(t("Only items of this race (mainly relevant for ships - "
                                 "modules/ammo usually have no race assigned in the SDE "
                                 "and stay visible whatever you choose)."))

        bcontrols = [
            (t("Category"), self.b_cat), ("Tech", self.b_tech),
            (t("Race/faction"), self.b_race),
            (t("Time window"), self.b_window), (t("Min build margin %"), self.b_margin),
            (t("Min \u00d8 daily volume"), self.b_vol),
            (t("Price from"), self.b_pmin), (t("Price to (0=∞)"), self.b_pmax),
        ]
        for i, (label, wdg) in enumerate(bcontrols):
            wdg.setMaximumWidth(190); wdg.setMinimumWidth(90)
            lab = QLabel(label); lab.setObjectName("Muted")
            r = (i // 5) * 2
            g.addWidget(lab, r, i % 5)
            g.addWidget(wdg, r + 1, i % 5)
            self._install_tip(wdg, lab)
            if hasattr(wdg, "valueChanged"):
                wdg.valueChanged.connect(self._build_preset_to_custom)
            elif hasattr(wdg, "currentIndexChanged"):
                wdg.currentIndexChanged.connect(self._build_preset_to_custom)
        g.setColumnStretch(5, 1)
        # Zeigt an, wenn das Reaktions-Preset aktiv ist, damit der Schalter
        # nicht unsichtbar im Hintergrund wirkt. (only_cap gibt es nicht
        # mehr - Capital-Module laufen regulaer unter T1/T2 mit.)
        self.b_only_cap_lbl = QLabel("")
        self.b_only_cap_lbl.setStyleSheet(f"color:{theme.CYAN}; font-size:11px;")
        g.addWidget(self.b_only_cap_lbl, 4, 0, 1, 4)
        self.b_refine_btn = QPushButton(" " + t("Optimal quantity"))
        self.b_refine_btn.setIcon(icons.icon("trend_up"))
        self.b_refine_btn.setToolTip(t(
            "Recomputes the exact build-plan maths for EVERY result "
              "below (batch size and rounding effects, real job costs) "
              "instead of the quick per-unit estimate – quantity = Ø "
              "daily volume (a realistic build and sell size). Takes a "
              "few seconds to a minute depending on the number of "
              "hits. Results are kept for this session only (RAM, no "
              "file) – no data litter on the disk."))
        self.b_refine_btn.clicked.connect(self._refine_all_optimal_qty)
        g.addWidget(self.b_refine_btn, 4, 4, 1, 2)
        # ZUGEKLAPPT starten (Nutzer: "keine ueberladenen Layouts, ich will
        # nur 3-4 Knoepfe"). Die Feinfilter setzt normalerweise das
        # Preset - wer sie braucht, klappt sie auf. Nichts entfernt,
        # nur weggeraeumt; dasselbe Muster wie im Materialien-Tab des
        # Bauplans, unserem Vorbild.
        self.b_filter_card = self._collapsible(t("FINE FILTERS"), ctl,
                                               expanded=False)
        b_filter_card = self.b_filter_card
        # STRATEGIE (offen) + FEINFILTER (zu) rechts uebereinander -
        # gleiche Anmutung wie die "Bauen oder kaufen?"-Spalte im Bauplan.
        self.b_side.addWidget(b_strat_card)
        self.b_side.addWidget(b_filter_card)
        self.b_side.addStretch(1)

        self.build_status = QLabel(t("\u201eLoad recipes\u201c, then \u201eFind blueprints\u201c "
                                     "(after a hub scan in the Daytrade or Swing tab)."))
        self.build_status.setObjectName("Muted")
        self.build_status.setWordWrap(True)
        root.addWidget(self.build_status)

        # VIER SPALTEN STATT ELF (Nutzer: "nur die zwei Zahlen, die
        # entscheiden"). Item, Bau-Marge, Gewinn/Stk und ein Bewertungs-
        # Balken wie im Materialien-Tab des Bauplans. Alle uebrigen
        # Kennzahlen (Baukosten, Sell, Gewinn/m3, Tagesvolumen,
        # Volatilitaet, Bestandstage, Gewinn/Tag, ISK/Std) stehen im
        # Zeilen-Tooltip - nichts ist verloren, nur nicht mehr im Weg.
        # + "vs. 90d avg" (emm499): Sell-Preis gegen den 90-Tage-Schnitt der
        # Markthistorie - NEUTRAL, als Scam-Warnlampe (Nutzer: hohe Marge
        # kann Markt-Manipulation sein). Der Balken rueckt auf Spalte 4.
        self.b_table = QTableWidget(0, 5)
        self.b_table.setHorizontalHeaderLabels(
            [t("Item"), t("Build margin"), t("Profit/unit"),
             t("vs. 90d avg"), t("Rating")])
        self.b_table.horizontalHeaderItem(3).setToolTip(
            t("Current sell price vs. the 90-day average of the market "
              "history. Deliberately NOT colored: a price far above the "
              "average can mean market manipulation (scam) rather than "
              "profit. ? = history not loaded yet."))
        self._make_columns_friendly(self.b_table)
        # WENIGER DATENBLATT (Nutzer: "weniger wie ne Excel-Tabelle"): das
        # Zellen-GITTER ist der staerkste Excel-Ausloeser - weg damit; die
        # Zeilen trennt weiterhin die Selektion/Hover-Farbe. Dazu etwas
        # Luft pro Zeile, damit Icons und Bewertungs-Balken atmen.
        self.b_table.setShowGrid(False)
        # KARTEN-GEFUEHL STATT DATENZEILE (Nutzer-Liste "weniger Excel",
        # Punkt 1): grosses Icon als visueller Anker links, kraeftiger
        # Item-Name, mehr Luft je Zeile. Werte aus der Nutzer-Liste
        # (32 px Icon, ~38 px Zeile) - nicht neu erfinden.
        self.b_table.setIconSize(QSize(32, 32))
        self.b_table.verticalHeader().setDefaultSectionSize(38)
        self.b_table.setSortingEnabled(True)
        self.b_table.verticalHeader().setVisible(False)
        self.b_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.b_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.b_table.cellDoubleClicked.connect(self._build_to_chart)
        kopier_menue(self.b_table, self._build_menu)
        root.addWidget(self.b_table, 1)

        # ---- Capital-Schiffe: eigene, klar getrennte Sektion ------------------
        # Carrier/Dread/FAX/Titan/Supercarrier/Freighter haben in Jita fast nie
        # echte Marktorders (Handel läuft über Contracts, oft Allianz-intern) -
        # deshalb NICHT in die normale, nach Marge/ISK-Std sortierte b_table
        # mischen (dort bräuchte jede Zeile einen echten Verkaufspreis, sonst
        # verzerrt eine erfundene "0 ISK Gewinn"-Zeile das Ranking). Stattdessen
        # eine eigene Tabelle, NUR Baukosten (aus SDE-Materialbedarf + Jita-
        # Materialpreisen), klar als "kein Marktpreis" gekennzeichnet.
        cap_inner = QWidget()
        self.b_cap_inner = cap_inner
        cap_v = QVBoxLayout(cap_inner); cap_v.setContentsMargins(0, 4, 0, 0)
        cap_head = QHBoxLayout()
        cap_info = QLabel(t(
            "These ships are practically never traded in Jita via normal market "
            "orders, but via contracts (often alliance-internal, null/lowsec). "
            "\u201eLoad contract prices\u201c looks up public contracts as a reference - "
            "\u00d8 daily volume/volatility do not exist for them (no price history "
            "for contracts in ESI), so you get \u201eActive contracts\u201c/\u201ePrice "
            "range\u201c instead."))
        cap_info.setObjectName("Muted"); cap_info.setWordWrap(True)
        cap_head.addWidget(cap_info, 1)
        cap_srch_lbl = QLabel()
        cap_srch_lbl.setPixmap(icons.pixmap("search", groesse=16))
        cap_head.addWidget(cap_srch_lbl)
        from PySide6.QtWidgets import QCompleter as _QCompleter2
        self.b_cap_search = QComboBox(); self.b_cap_search.setEditable(True)
        self.b_cap_search.setMinimumWidth(180)
        self.b_cap_search.setInsertPolicy(QComboBox.NoInsert)
        self.b_cap_search.lineEdit().setPlaceholderText(t("Ship name \u2026"))
        self.b_cap_search.completer().setCompletionMode(_QCompleter2.PopupCompletion)
        self.b_cap_search.completer().setFilterMode(Qt.MatchContains)
        self.b_cap_search.completer().setCaseSensitivity(Qt.CaseInsensitive)
        self.b_cap_search.editTextChanged.connect(self._apply_cap_filter)
        cap_head.addWidget(self.b_cap_search)
        # dito - gezeichnetes Symbol statt Emoji (Sitzung 16). Dieser Knopf
        # sitzt in derselben Capital-Karte wie b_cap_mode; ein Emoji auf dem
        # einen und ein Symbol auf dem anderen haetten nebeneinander gestanden.
        self.b_cap_btn = QPushButton(t("Estimate capital build cost"))
        self.b_cap_btn.setIcon(icons.icon("satellite"))
        self.b_cap_btn.clicked.connect(self._compute_capital_costs)
        cap_head.addWidget(self.b_cap_btn)
        self.b_cap_contract_btn = QPushButton(
            t("Load contract prices (all of New Eden)"))
        self.b_cap_contract_btn.setIcon(icons.icon("globe"))
        self.b_cap_contract_btn.setToolTip(t(
            "Searches public contracts in ALL regions for capital "
              "sales and derives a reference value per ship type. "
              "Capitals are sold everywhere, not only in the hub – a "
              "scan over a single region yields no price at all for "
              "many types, or just one.\nTAKES LONGER (all of New Eden "
              "instead of one region, several minutes depending on "
              "time of day).\nThe MEDIAN is shown (the middle price): "
              "contract prices regularly have outliers on the high "
              "side that would skew an average. The average is in the "
              "tooltip of the cell next to it.\nPublic offers only – "
              "ESI sees alliance-internal contracts only through a "
              "character with the director or accountant role in that "
              "corp, which this scan does not cover."))
        self.b_cap_contract_btn.clicked.connect(self._load_capital_contract_prices)
        cap_head.addWidget(self.b_cap_contract_btn)
        cap_v.addLayout(cap_head)
        self.b_cap_status = QLabel("")
        self.b_cap_status.setObjectName("Muted"); self.b_cap_status.setWordWrap(True)
        cap_v.addWidget(self.b_cap_status)
        # 4-SPALTEN-SCHEMA wie die Hauptliste (Nutzer-Liste "weniger
        # Excel", Punkt 3 - vorher 11 Spalten). Der Rest steht im
        # Zeilen-Tooltip; Bewertung kommt aus derselben _bau_bewertung.
        self.b_cap_table = QTableWidget(0, 4)
        self.b_cap_table.setHorizontalHeaderLabels(
            [t("Ship"), t("Build cost"), t("Contract reference"), t("Rating")])
        self._make_columns_friendly(self.b_cap_table)
        self.b_cap_table.setShowGrid(False)   # gleiche Optik wie die Liste oben
        self.b_cap_table.setIconSize(QSize(32, 32))
        self.b_cap_table.verticalHeader().setDefaultSectionSize(38)
        self.b_cap_table.setSortingEnabled(True)
        self.b_cap_table.verticalHeader().setVisible(False)
        self.b_cap_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.b_cap_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.b_cap_table.setMinimumHeight(320)
        self.b_cap_table.setMaximumHeight(560)
        kopier_menue(self.b_cap_table, self._build_menu_cap)
        cap_v.addWidget(self.b_cap_table)
        self.b_cap_wrap = self._collapsible(
            t("CAPITAL SHIPS (BUILD COST, NO MARKET PRICE)"), cap_inner,
            expanded=False, header_attr="b_cap_header",
            tip=t("Carrier/Dreadnought/FAX/Titan/Supercarrier/Freighter - trading "
                  "runs via contracts instead of market orders, hence separate from "
                  "the normal profit table above. Does NOT run automatically with the "
                  "normal search - only when expanded or in Capital mode."))
        root.addWidget(self.b_cap_wrap)
        # Erst beim tatsächlichen Aufklappen berechnen (nicht bei jeder normalen
        # "Blaupausen suchen"-Suche mitlaufen lassen - das gehörte hier vorher
        # nicht her und ist jetzt sauber getrennt vom Capital-Modus).
        self.b_cap_header.toggled.connect(self._on_cap_header_toggled)
        # AUSSERHALB des Capital-Modus KOMPLETT unsichtbar (Nutzer: "das
        # gehoert nicht dahin"). Capitals haben ihren eigenen Modus - der
        # Umschalter sitzt oben in der Strategie-Karte; eine zweite,
        # dauerhaft sichtbare Capital-Sektion unter der normalen Liste war
        # Redundanz und Platzfresser. _toggle_capital_mode blendet die
        # Karte beim Einschalten ein.
        self.b_cap_wrap.setVisible(False)

        # Seite „Aktuelle Baupläne“ (gespeicherte Baupläne zum Abarbeiten)
        plans_page = QWidget()
        self._plans_layout = QVBoxLayout(plans_page)
        self._plans_layout.setContentsMargins(14, 8, 14, 8); self._plans_layout.setSpacing(7)
        # Struktur-Fitting-Seite enthält jetzt auch das frühere „Setup“ (Profile + Basiswerte)
        from PySide6.QtWidgets import QScrollArea
        _combined = QWidget()
        _cv = QVBoxLayout(_combined); _cv.setContentsMargins(0, 0, 0, 0); _cv.setSpacing(6)
        _cv.addWidget(setup_page)                        # Profile + BAU-SETUP (oben)
        _cv.addWidget(self._build_structures_page(), 1)  # Strukturen (darunter)
        _struct_scroll = QScrollArea(); _struct_scroll.setWidgetResizable(True)
        _struct_scroll.setFrameShape(QScrollArea.NoFrame); _struct_scroll.setWidget(_combined)
        # Seite „Meine Blueprints“ (ESI-getrackt: welche BPs besitze ich, was ist
        # baubar/profitabel). Wird per Button aktualisiert (ESI-Abruf pro Char).
        bp_page = QWidget()
        self._bp_page_layout = QVBoxLayout(bp_page)
        self._bp_page_layout.setContentsMargins(14, 8, 14, 8)
        self._bp_page_layout.setSpacing(7)
        self._build_my_blueprints_page()
        from PySide6.QtWidgets import QScrollArea
        _combined = QWidget()
        _cv = QVBoxLayout(_combined); _cv.setContentsMargins(0, 0, 0, 0); _cv.setSpacing(6)
        _cv.addWidget(setup_page)                        # Profile + BAU-SETUP (oben)
        _cv.addWidget(self._build_structures_page(), 1)  # Strukturen (darunter)
        _struct_scroll = QScrollArea(); _struct_scroll.setWidgetResizable(True)
        _struct_scroll.setFrameShape(QScrollArea.NoFrame); _struct_scroll.setWidget(_combined)
        # BAU-KALENDER VOLLSTAENDIG ENTFERNT (Nutzer: "wir werden nie einen
        # Kalender einbauen") - Seite, Knopf UND Code (Sitzung 7: 1977 Zeilen,
        # 18 Methoden). Seiten-Indizes sind nachgezogen, "Strukturen" ist 3.
        # VORSICHT bei kuenftigem Aufraeumen: `_cal_fit_top_fns` ist trotz
        # des Namens KEIN Kalender-Code, sondern ein allgemeiner Layout-Helfer.
        self.b_stack.addWidget(scan_page)       # 0 – Scanner
        # MEINE BLUEPRINTS IN EINEN EIGENEN ROLLBEREICH (Nutzer, Sitzung 20:
        # "ich muss immernoch nach rechts scrollen wenn ich die profits sehen
        # will").
        # GEMESSEN: ein QStackedWidget nimmt die MINDESTBREITE der BREITESTEN
        # Seite fuer ALLE. Die Seiten waren
        #   0 Scanner 488 · 1 Meine Blueprints 1861 · 2 Bauplaene 391 ·
        #   3 Strukturen 68
        # Die 16-spaltige Blueprints-Tabelle zwang also auch "Meine
        # Bauplaene" auf 1861 px - daher die waagerechte Bildlaufleiste,
        # obwohl auf dieser Seite viel Luft ist.
        # Ein eigener Rollbereich kappt das, GENAU WIE bei Seite 3 weiter
        # oben: die breite Seite rollt fuer sich, die anderen nicht mehr mit.
        _bp_scroll = QScrollArea(); _bp_scroll.setWidgetResizable(True)
        _bp_scroll.setFrameShape(QScrollArea.NoFrame)
        _bp_scroll.setWidget(bp_page)
        self.b_stack.addWidget(_bp_scroll)      # 1 – Meine Blueprints
        self.b_stack.addWidget(plans_page)      # 2 – Aktuelle Baupläne
        self.b_stack.addWidget(_struct_scroll)  # 3 – Struktur-Fitting (+ Setup)
        self.b_stack.addWidget(self._jobs_seite_bauen())  # 4 – Industry jobs (emm327)
        self.b_stack.addWidget(self._bfs_seite_bauen())   # 5 – Build from stock (emm436)
        self.b_stack.addWidget(self._lager_seite_bauen()) # 6 – Stock locations (emm458)
        # PLAN-KARTEN ERST BEIM ERSTEN ZEIGEN (Nutzer 27.09.2026: "ja bitte
        # mach das"; Start-Messung: der Build-Reiter kostete 1,4 s, fast
        # alles fuer die Karten aller gespeicherten Plaene - dazu starteten
        # sie zwei Hintergrund-Jobs (Schaetzung, ESI-Fertigstatus), die beim
        # Start mitrechneten). Gebaut wird, sobald Seite 2 "My build plans"
        # erscheint (Leiste und Tutorial gehen beide ueber _bau_nav).
        # Jeder andere Aufruf von _reload_saved_plans baut wie bisher sofort.
        # KEIN eigener Seiten-Waechter: _bau_nav(2) baut die Karten ohnehin
        # bei jedem Oeffnen neu, und es ist der einzige Weg auf die Seite
        # (b_stack.setCurrentIndex steht nur dort). Ein zweiter Waechter
        # haette beim ersten Oeffnen doppelt gebaut (Rotprobe fand das).
        self._plan_karten_gebaut = False
        outer.addWidget(self._build_bau_rail())

        self.tabs.addTab(w, t("Build"))
        from PySide6.QtCore import QTimer
        if industry.sde_ready():
            QTimer.singleShot(0, self._reload_build_picker)
        QTimer.singleShot(0, self._reload_system_picker)   # Systemnamen für die Suche

    def _fill_invention_tab(self, plan, recipes, names, cards_layout, top_type_id=None,
                            own_bpc_widgets=None):
        """Baut die Invention-Tab-Karten neu: ein Panel pro Item, das über
        Invention entsteht. Datacores sind fix (aus dem Blueprint-Rezept),
        der Decryptor ist wählbar - Erfolgschance/Runs/ME/TE aktualisieren sich
        live (industry.invention_outcome), und der Gesamtbedarf (Versuche/
        Datacores/Kosten) für die aktuelle Bauplan-Menge wird direkt gezeigt.
        Ein Decryptor-Wechsel schreibt in self._bd_opts['inv_decryptor_map']
        und löst self._bd_full_rebuild() aus, damit auch die Kopfzeile
        (Invention-Kosten, Gewinn) sofort den neuen Wert zeigt."""
        import html as _h_sum      # Kurzfassung in der Kopfzeile (Decryptor-Name)

        def _kv_rows(rows):
            """Kompakte Zwei-Spalten-Liste: Beschriftung links (gedaempft),
            Wert rechts. Ersetzt die frueheren Fliesstext-Zeilen, die mit
            Mittelpunkten getrennt ueber die volle Breite liefen und sich
            schlecht ueberfliegen liessen (Nutzer)."""
            _out = ["<table cellspacing='0' cellpadding='0' "
                    "style='font-size:11px;'>"]
            for _lbl, _val, _col in rows:
                _st = f"color:{_col};font-weight:700;" if _col else ""
                _out.append(
                    f"<tr><td style='color:{theme.MUTED}; "
                    f"padding:0 10px 1px 0;'>{_lbl}</td>"
                    f"<td style='{_st}'>{_val}</td></tr>")
            _out.append("</table>")
            return "".join(_out)

        # KOMPLETT LEEREN und danach genau EINEN Stretch ans Ende. Die alte
        # Schleife liess das LETZTE Element stehen - solange das der Stretch
        # war, ging das gut. Seit Struktur/Skills in der Seitenleiste sitzen,
        # standen die Karten aber HINTER dem Stretch (s. insert_at unten), und
        # das letzte Element war die Gesamtzeile: die blieb stehen und bekam
        # bei jedem Rebuild eine zweite dazu ("Invention gesamt" doppelt,
        # Nutzer-Screenshot) - plus eine riesige Luecke, weil der Stretch
        # oberhalb der Karten sass.
        # ZWEITE ABSICHERUNG GEGEN DEN TE-ABSTURZ: me/te/Eigene-BPC sind
        # DIESELBEN Widget-Objekte ueber alle Rebuilds hinweg (sie werden unten
        # nur neu einsortiert). Solange sie noch Kinder einer Karte sind,
        # nimmt deleteLater() der Karte sie MIT ins Grab - danach zeigt der
        # Dialog auf ein totes C++-Objekt und der naechste Klick beendet die
        # App. Bisher ging das nur gut, weil sie weiter unten rechtzeitig neu
        # eingehaengt wurden; jeder Pfad, der das nicht tut (Ausnahme mitten im
        # Aufbau, Endprodukt ohne Karte), war ein Absturz. Deshalb VORHER
        # ausklinken - `setParent(None)` loest sie aus der Karte, ohne sie zu
        # zerstoeren.
        if own_bpc_widgets is not None:
            for _shared in own_bpc_widgets:
                if _shared is not None:
                    _shared.setParent(None)
        while cards_layout.count():
            it = cards_layout.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()
        cards_layout.addStretch()
        self._bd_inv_combos = {}          # je Blaupause die Decryptor-Wahl
        self._bd_inv_best_btns = {}       # je Blaupause der Best-Choice-Knopf
        self._bd_inv_t1_copy = {}         # je Blaupause "Copy T1 Original"
        self._bd_inv_karten = {}          # je Blaupause Pfeil/Rumpf/Kurzfassung
        self._bd_inv_own = {}             # je Buendel-Ende: Own-BPC-Haken + ME/TE
        # SEITENLEISTE EBENFALLS LEEREN. Diese Funktion laeuft bei JEDEM
        # Rebuild - ohne das stapeln sich Struktur-Zeile und Skill-Auswahl
        # bei jeder Mengenaenderung erneut untereinander.
        _side_clear = getattr(self, "_bd_inv_side_v", None)
        if _side_clear is not None:
            while _side_clear.count():
                _it = _side_clear.takeAt(0)
                _w = _it.widget()
                if _w:
                    _w.deleteLater()
        if not plan:
            return
        items = []
        for tid, runs in (plan.get("build_runs") or {}).items():
            if runs < 1:
                continue
            bp = recipes.product_to_bp.get(tid)
            if not bp:
                continue
            bp_id, activity, _oq = bp
            if activity != industry.MANUFACTURING:
                continue
            inv = recipes.invention_for_bpc.get(bp_id)
            if not inv:
                continue
            items.append((tid, bp_id, runs, inv))

        def _own_bpc_fallback_card():
            """Kleine eigenständige Karte NUR für ME/TE/Eigene-BPC, falls das
            Endprodukt selbst keine Invention braucht (reines T1/BPO) - sonst
            wären diese Felder nirgends mehr zu finden."""
            if own_bpc_widgets is None:
                return
            # KEINE KARTE FUER DAS BUENDEL SELBST (Nutzer 26.09.2026: "das
            # T1-Item soll da nicht angezeigt sein, wirklich nur, was
            # invented werden muss"): die Pseudo-Blaupause (-2) braucht
            # keine Invention, ME/TE je Ende stehen in der Karte
            # "Endprodukte". T1-Enden stehen ohnehin nicht im Tab - nur
            # Items mit Eintrag in invention_for_bpc bekommen eine Karte.
            if top_type_id == industry.BUENDEL_ID:
                return
            _me_sp, _te_sp, _obc_cb, _obc_runs_lbl, _obc_runs_sp = own_bpc_widgets
            fb_card = QFrame(); fb_card.setObjectName("Card")
            fb_v = QVBoxLayout(fb_card)
            fb_v.setContentsMargins(14, 10, 14, 10); fb_v.setSpacing(6)
            fb_title = QLabel(t("\u2699 End product ME/TE ({name})").format(name=names.get(top_type_id, "")))
            fb_title.setStyleSheet(f"color:{theme.CYAN}; font-weight:700;")
            fb_v.addWidget(fb_title)
            fb_info = QLabel(t("This item needs no invention (T1/BPO) - ME/TE still "
                               "apply, e.g. if your own blueprint is already researched."))
            fb_info.setObjectName("Muted"); fb_info.setWordWrap(True)
            fb_v.addWidget(fb_info)
            fb_row1 = QHBoxLayout(); fb_row1.setSpacing(6)
            _me_cap = QLabel(t("ME:")); _me_cap.setStyleSheet("font-size:11px;")
            fb_row1.addWidget(_me_cap); fb_row1.addWidget(_me_sp)
            _te_cap = QLabel(t("TE:")); _te_cap.setStyleSheet("font-size:11px;")
            fb_row1.addWidget(_te_cap); fb_row1.addWidget(_te_sp)
            fb_row1.addStretch()
            fb_v.addLayout(fb_row1)
            fb_row2 = QHBoxLayout(); fb_row2.setSpacing(6)
            fb_row2.addWidget(_obc_cb); fb_row2.addWidget(_obc_runs_lbl)
            fb_row2.addWidget(_obc_runs_sp); fb_row2.addStretch()
            fb_v.addLayout(fb_row2)
            cards_layout.insertWidget(0, fb_card)
        if not items:
            empty = QLabel(t("No item in this build plan needs invention (either "
                             "everything is T1/BPO, or invention is switched off in the "
                             "build settings)."))
            empty.setObjectName("Muted"); empty.setWordWrap(True)
            cards_layout.insertWidget(cards_layout.count() - 1, empty)
            _own_bpc_fallback_card()
            return
        need_names = set()
        for _tid, _bp_id, _runs, inv in items:
            t1_bp, _br, _pr, datacores = inv
            need_names.add(t1_bp)
            for d, _q in datacores:
                need_names.add(d)
        # Decryptor-Namen gleich mit auflösen - die Gesamt-Zeilen (je Karte +
        # Gesamt-Karte) nennen sie namentlich statt "#34201". WICHTIG: über
        # die METHODE self._decryptor_list(), nicht die lokale Variable
        # decryptor_list - die wird erst WEITER UNTEN in dieser Funktion
        # definiert (UnboundLocalError beim Öffnen des Bauplans, Nutzer-
        # Traceback 28.07.).
        try:
            for _nm, _dv in self._decryptor_list():
                if _dv and _dv[4]:
                    need_names.add(_dv[4])
        except Exception:
            pass
        try:
            extra_names = esi.resolve_names(list(need_names))
        except Exception:
            extra_names = {}
        # Struktur für Invention (zugewiesen oder Auto-Wahl) - Warnung, wenn
        # noch gar keine Struktur angelegt ist.
        has_structs = bool(self.settings.get("bau_structures"))
        inv_struct = self._struct_for_activity("invention") if has_structs else None
        assigned_map = self.settings.get("bau_activity_struct", {}) or {}
        struct_lbl = QLabel()
        if not has_structs:
            struct_lbl.setText(t("\u26a0 No structure set up - please add an "
                                 "invention-capable structure in the Structures tab."))
            struct_lbl.setStyleSheet(f"color:{theme.AMBER}; font-weight:700;")
        elif inv_struct:
            # "Auto" heisst in beiden Sprachen gleich und bleibt.
            tag = t("assigned") if assigned_map.get("invention") else "Auto"
            struct_lbl.setText(t("Structure: ") + f"<b>{inv_struct.get('name','?')}</b> "
                               f"({tag})")
            struct_lbl.setStyleSheet(f"color:{theme.MUTED};")
        else:
            struct_lbl.setText(t("\u26a0 Please choose a structure for invention in the "
                                 "Structures tab."))
            struct_lbl.setStyleSheet(f"color:{theme.AMBER}; font-weight:700;")
        # IN DIE SEITENLEISTE (Nutzer). Faellt sie mal weg, landet alles wie
        # frueher oben in der Kartenspalte - kein harter Bruch.
        _side_v = getattr(self, "_bd_inv_side_v", None)
        if _side_v is not None:
            struct_lbl.setWordWrap(True)
            _side_v.addWidget(struct_lbl)
        else:
            cards_layout.insertWidget(0, struct_lbl)

        # Charakter-Wahl für den Skill-Modifier (Encryption+Datacore-Skills):
        # Standard "Bester automatisch" (wie bisher), oder gezielt EINEN der
        # "Für Invention"-markierten Charaktere fixieren - rein für die
        # Erfolgschance-Berechnung, KEINE Job-/Slot-Zuteilung. Auffälliger
        # gestaltet (auf Nutzerwunsch), da das direkt beeinflusst, was als
        # Erfolgschance angezeigt wird.
        # Kein eigener blauer Karten-Stil mehr: in der Seitenleiste sitzt das
        # in der amber Klapp-Karte wie ueberall sonst. Senkrecht statt
        # waagerecht, weil 380px fuer Label + Dropdown + Knopf nebeneinander
        # nicht reichen.
        char_row = QFrame()
        char_row_l = QVBoxLayout(char_row)
        char_row_l.setContentsMargins(0, 0, 0, 0); char_row_l.setSpacing(4)
        # SICHERHEIT DER PLANUNG - einstellbar (Nutzer), Vorgabe 75 %.
        # Sie aendert NICHT die Erfolgschance je Versuch, sondern nur, fuer
        # wieviel Pech Material eingekauft wird: 12 Cerberus bei 33,8 % sind
        # 41 Versuche bei 75 %, aber 47 bei 90 %. Je kleiner die Serie, desto
        # teurer wird jedes Prozent - bei 1 Erfolg sind es 4 gegen 6 Versuche.
        _conf_lbl = QLabel(t("Planned certainty:"))
        _conf_lbl.setObjectName("Muted"); _conf_lbl.setStyleSheet("font-size:11px;")
        char_row_l.addWidget(_conf_lbl)
        _conf_sp = QSpinBox()
        _conf_sp.setRange(50, 99)
        _conf_sp.setSuffix(" %")
        _conf_sp.setValue(int(round(self._bd_inv_confidence() * 100)))
        _conf_sp.setToolTip(t(
            "How likely the planned attempts are really enough.\n"
            "Higher = more attempts, more datacores, more certain to finish - but "
            "more expensive.\nThis does NOT change the success chance per attempt.\n"
            "Also affects \u201eAuto-Decryptor\u201c: at high certainty, "
            "decryptors with a better success chance pay off sooner.\n"
            "Applies to this build plan only; a new one starts again at {pct} %."
        ).format(pct=int(industry.DEFAULT_INVENTION_CONFIDENCE * 100)))

        def _conf_changed(_v):
            self._bd_inv_conf = float(_v) / 100.0
            _cb = getattr(self, "_bd_full_rebuild", None)
            if _cb:
                QTimer.singleShot(0, _cb)   # entprellt wie die anderen Felder
        _conf_sp.valueChanged.connect(_conf_changed)
        char_row_l.addWidget(_conf_sp)

        char_row_lbl = QLabel(t("Skills for success chance of:"))
        char_row_lbl.setObjectName("Muted")
        char_row_lbl.setStyleSheet("font-size:11px;")
        char_row_l.addWidget(char_row_lbl)
        inv_char_combo = QComboBox()
        inv_char_combo.addItem(t("\u2014 Best automatically \u2014"), 0)
        _char_names_map = {c["character_id"]: (c.get("character_name") or c.get("name")
                                                or str(c["character_id"]))
                           for c in store.list_characters()}
        for cid in (self.settings.get("bau_invention_chars", []) or []):
            icon = self._character_icon(cid, size=24)
            name = _char_names_map.get(cid, str(cid))
            if icon:
                inv_char_combo.addItem(icon, name, cid)
            else:
                inv_char_combo.addItem(name, cid)
        inv_char_combo.setMinimumWidth(240)
        inv_char_combo.setStyleSheet("font-size:13px; font-weight:700; padding:4px 8px;")
        self._combo_select(inv_char_combo, getattr(self, "_bd_invention_char", 0) or 0)

        def _on_inv_char_change(_i, combo=inv_char_combo):
            self._bd_invention_char = combo.currentData() or 0
            cb = getattr(self, "_bd_full_rebuild", None)
            if cb:
                cb()
        inv_char_combo.currentIndexChanged.connect(_on_inv_char_change)
        ohne_mausrad(inv_char_combo)
        char_row_l.addWidget(inv_char_combo)
        # Der einzelne Lade-Knopf wurde entfernt (Übersichtlichkeit) - "🛰 Alles
        # aus ESI laden" oben im Dialog deckt das jetzt mit ab. Nur der
        # Zurücksetzen-Knopf bleibt hier.
        esi_undo_btn = QPushButton("\u21ba " + t("Reset"))
        esi_undo_btn.setIcon(icons.icon("refresh"))
        esi_undo_btn.setStyleSheet("font-size:11px; padding:4px 10px;")
        esi_undo_btn.setVisible(bool(getattr(self, "_bd_owned_bpc_by_id", None)))
        char_row_l.addWidget(esi_undo_btn)
        esi_undo_btn.clicked.connect(lambda: self._undo_all_invention_bpc_esi(esi_undo_btn))
        if _side_v is not None:
            _side_v.addWidget(char_row)
        else:
            cards_layout.insertWidget(1, char_row)

        decryptor_list = self._decryptor_list()
        adj_prices = (getattr(self, "_bd_opts", None) or {}).get("adjusted_prices", {}) or {}
        total_box = QLabel(); total_box.setStyleSheet(
            f"color:{theme.AMBER}; font-weight:800; font-size:15px;")
        _card_costs = {}
        self._bd_invention_needs = {}   # bp_id -> {datacores:[(id,qty)], decryptor_id, decryptor_qty}
        # Welche Items entstehen per INVENTION? Ihre Blaupausen sind
        # erfundene BPCs - die kopiert man NICHT (Nutzer-Fund, Sitzung 8:
        # bei Rigs braucht das T2 kein T1-Modul, die Endprodukt-"Blueprints"
        # im Runplaner sind die Invention-Ergebnisse).
        self._bd_invention_targets = set()

        def _dv_label(nm, v):
            """Decryptor-Name + Boni fürs Dropdown, z.B. 'Parity (+50% success,
            +3 Runs, ME+1%, TE-2%)' - damit man die Wahl sieht, ohne extra
            nachzuschlagen. Die Boni laufen durch t(), der Name ist ein
            EVE-Eigenname und bleibt."""
            pm, rm, me, te, tid = v
            if tid is None:
                return dec_anzeige(nm)
            bits = []
            if abs(pm - 1.0) > 1e-9:
                # "% Erfolg" stand hier bis Sitzung 22 als nackter f-String und
                # KEIN Scanner sah es: de_scan folgt `addItem(_dv_label(...))`
                # nicht in den Helfer hinein, und "Erfolg" stand in keiner
                # Wortliste. Dafuer gibt es jetzt de_scan5.
                bits.append(t("{v}% success").format(
                    v=f"{'+' if pm >= 1 else ''}{(pm - 1) * 100:.0f}"))
            if rm:
                bits.append(f"{'+' if rm >= 0 else ''}{rm} Runs")
            if me:
                bits.append(f"ME{'+' if me >= 0 else ''}{me}%")
            if te:
                bits.append(f"TE{'+' if te >= 0 else ''}{te}%")
            return f"{nm}  ({', '.join(bits)})" if bits else nm

        def _update_total():
            # Die Summe enthaelt seit Sitzung 9 auch die Jobgebuehren fuer
            # Kopieren und Invention (Formel in industry.science_job_fee,
            # EVE-Ref-verifiziert). Der Klammer-Zusatz dazu ist auf
            # NUTZER-ANSAGE wieder RAUS ("die Info stoert und ist
            # selbsterklaerend") - die Zeile ist ohnehin lang. Nicht
            # erneut anbieten.
            txt = (t("Invention total (all items): ")
                   + isk(sum(_card_costs.values())))
            dc, dcy, att = self._aggregate_invention_needs(
                getattr(self, "_bd_invention_needs", None))
            if att:
                stock = (getattr(self, "_bd_opts", None) or {}).get("stock") or {}
                bits = []
                for tid, q in sorted(dc.items(), key=lambda kv: -kv[1]):
                    have = int(stock.get(tid, 0) or 0)
                    bits.append(f"{q}\u00d7 {extra_names.get(tid, f'#{tid}')}"
                                + (t(" ({n} in the hangar)").format(n=min(have, q))
                                   if have else ""))
                for tid, q in sorted(dcy.items(), key=lambda kv: -kv[1]):
                    have = int(stock.get(tid, 0) or 0)
                    bits.append(f"{q}\u00d7 {extra_names.get(tid, f'#{tid}')}"
                                + (t(" ({n} in the hangar)").format(n=min(have, q))
                                   if have else ""))
                if bits:
                    txt += (t("  \u00b7  {n} attempts in total \u2192 ").format(n=att)
                            + " \u00b7 ".join(bits))
            # KOPIEN FUERS BAUEN (Nutzer, Sitzung 8): "Zusaetzlich brauche
            # ich ja noch T1-Kopien, um genuegend T1 bauen zu koennen wie im
            # Runplaner angegeben - 3 Blueprint-Copys mit jeweils 28 Runs,
            # damit alle 3 Charaktere gleichzeitig bauen koennen."
            # Eine Blaupause traegt EINEN Job: wer 9 Jobs parallel fahren
            # will, braucht 9 Blaupausen desselben Items. Der Runplaner
            # zeigte die Aufteilung, sagte aber nie, dass es KOPIEN sind.
            try:
                _zut = getattr(self, "_bd_last_assignments", None) or []
                _kop = industry.kopien_fuers_bauen(
                    _zut,
                    ohne_tids=getattr(self, "_bd_invention_targets", set()))
                if _kop:
                    _z = []
                    for _e in _kop[:6]:
                        _g = " / ".join(f"{_n}\u00d7{_r}"
                                        for _r, _n in _e["gruppen"])
                        _z.append(t("{name}: <b>{k}</b> copies ({j} jobs \u2013 {g} "
                                    "runs)").format(name=_e["name"], k=_e["kopien"],
                                                    j=_e["blaupausen"], g=_g))
                    _mehr = (t(" \u00b7 +{n} more").format(n=len(_kop) - 6)
                             if len(_kop) > 6 else "")
                    txt += (f'<br><span style="color:{theme.CYAN};">'
                            + t("Copy first for building (1 blueprint = 1 "
                                "simultaneous job, the original covers one of them): ")
                            + '</span>' + " \u00b7 ".join(_z) + _mehr)
            except Exception:
                pass          # Zusatzinfo darf den Tab nie blockieren
            total_box.setText(txt)
        # 0, nicht mehr 2: struct_lbl und char_row sitzen jetzt in der
        # Seitenleiste, die Kartenspalte beginnt also bei 0. Mit 2 landete
        # alles hinter dem Stretch.
        insert_at = 0
        self._bd_inv_rang = {}            # je Blaupause: Rang-Funktion fuer "Best Decryptor for all"
        # EINMAL OBEN STATT JE KARTE (Nutzer 26.09.2026: "Buy-Haken nur
        # einmal oben"). "Buy datacores/decryptors" sind globale Einstellungen
        # (ein Haken gilt fuer alle Karten), und die freien Science-Slots sind
        # DIESELBEN fuer jede Invention - beides stand bisher in jeder Karte.
        self._bd_inv_split_w = {}         # je Blaupause Regler/Anzeige/Fuellung
        _mem_sp = getattr(self, "_bd_inv_split", None)
        if not isinstance(_mem_sp, dict):
            # Alte Form (kopien, slots) aus einer frueheren Fassung: die
            # Slot-Zahl uebernehmen, die Kopienzahl galt fuer KEINE bestimmte
            # Karte (sie hing an der letzten) - verwerfen.
            if isinstance(_mem_sp, (tuple, list)) and len(_mem_sp) == 2:
                self._bd_inv_slots = int(_mem_sp[1] or 10)
            self._bd_inv_split = {}
        if items:
            _top = QFrame(); _top.setObjectName("Card")
            _tl = QHBoxLayout(_top)
            _tl.setContentsMargins(12, 6, 12, 6); _tl.setSpacing(12)
            # "Buy datacores/decryptors" stehen seit 26.09.2026 (Nutzer) in der
            # Seitenleiste, Karte "Buy or not?" ganz oben (mw_bauplan_fenster).
            _tl.addStretch()
            _tl.addWidget(QLabel(t("Free science slots:")))
            self._inv_slots = QSpinBox()
            self._inv_slots.setRange(1, 30)
            self._inv_slots.setValue(int(getattr(self, "_bd_inv_slots", 10) or 10))
            self._inv_slots.setToolTip(t(
                "Your simultaneously usable science slots (in game at the bottom "
                "left of the industry window, e.g. \u201eScience jobs 4/10\u201c). "
                "Limits how many copies can really work in parallel."))
            ohne_mausrad(self._inv_slots)
            _tl.addWidget(self._inv_slots)

            def _slots_neu(v):
                self._bd_inv_slots = int(v)
                for _sw in (getattr(self, "_bd_inv_split_w", None) or {}).values():
                    try:
                        # Den rechten Anschlag setzt die Fuellung (EINE Stelle:
                        # min(freie Slots, Versuche)).
                        if _sw.get("fill"):
                            _sw["fill"]()
                    except Exception:
                        pass       # Anzeige darf den Bauplan nie blockieren
            self._inv_slots.valueChanged.connect(_slots_neu)
            cards_layout.insertWidget(insert_at, _top)
            self._bd_inv_top = _top          # b-Suite
            insert_at += 1
        for tid, bp_id, runs_needed, inv in items:
            self._bd_invention_targets.add(tid)
            t1_bp, base_runs, base_prob_sde, datacores = inv
            # Offizielle Formel: SkillModifier = 1 + Encryption/40 +
            # (Datacore1+Datacore2)/30, VOR dem Decryptor-Modifikator auf die
            # Basis-Erfolgschance angewandt. Ohne passende Charakter-/SDE-
            # Daten bleibt der Modifier bei 1.0 (reiner SDE-Basiswert, wie
            # bisher) - kein Raten.
            _skill_mod, _skill_char = self._bau_invention_skill_modifier_with_char(t1_bp)
            base_prob = min(1.0, base_prob_sde * _skill_mod)
            card = QFrame(); card.setObjectName("Card")
            outer = QVBoxLayout(card); outer.setContentsMargins(14, 10, 14, 10)
            outer.setSpacing(6)
            # ZUKLAPPBARE KARTE (Nutzer 26.09.2026: "alle Eintraege der
            # verschiedenen erforschbaren T2-Copys kompakter und
            # uebersichtlicher, es verbraucht zu viel Platz"). Die Kopfzeile
            # bleibt immer stehen und traegt rechts die Kurzfassung
            # (Decryptor · Versuche · Invention-Kosten, `sum_lbl`, gefuellt
            # in _recompute); alles andere liegt in `_body` und klappt mit
            # dem Pfeil weg. Zustand je Blaupause in `bau_inv_zu` (Liste der
            # zugeklappten Blaupausen-IDs, Standard OFFEN - wie `bau_multi_zu`).
            head_row = QHBoxLayout(); head_row.setSpacing(6)
            _pf = QPushButton()
            _pf.setCheckable(True)
            _pf.setFixedWidth(26)
            _pf.setFlat(True)
            _pf.setToolTip(t("Show or hide the details of this invention"))
            head_row.addWidget(_pf)
            head = QLabel(f"{self._icon_html(t1_bp, size=22, kind='bp')}\u2699 "
                         f"{extra_names.get(t1_bp, f'#{t1_bp}')}")
            head.setStyleSheet(f"color:{theme.CYAN}; font-size:15px; font-weight:700;")
            head_row.addWidget(head)
            head_row.addStretch()
            sum_lbl = QLabel("")
            sum_lbl.setObjectName("Muted")
            sum_lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
            head_row.addWidget(sum_lbl)
            outer.addLayout(head_row)
            _body = QWidget()
            body = QVBoxLayout(_body); body.setContentsMargins(0, 0, 0, 0)
            body.setSpacing(6)
            outer.addWidget(_body)
            self._bd_inv_karten = getattr(self, "_bd_inv_karten", None) or {}
            self._bd_inv_karten[int(bp_id)] = {"pfeil": _pf, "body": _body,
                                               "kurz": sum_lbl}   # b-Suite

            def _klapp(_on, _b=_body, _btn=_pf, _bp=int(bp_id)):
                _b.setVisible(bool(_on))
                _btn.setIcon(icons.icon("chevron" if _on else "arrow_right"))
                try:
                    _zu = [int(x) for x in (self.settings.get("bau_inv_zu") or [])]
                except (TypeError, ValueError):
                    _zu = []
                _zu = [x for x in _zu if x != _bp]
                if not _on:
                    _zu.append(_bp)
                if _zu != list(self.settings.get("bau_inv_zu") or []):
                    self.settings["bau_inv_zu"] = _zu
                    from .. import config as _cfg_k
                    _cfg_k.save_settings(self.settings)
            _pf.toggled.connect(_klapp)
            try:
                _offen0 = int(bp_id) not in [int(x) for x in
                                             (self.settings.get("bau_inv_zu") or [])]
            except (TypeError, ValueError):
                _offen0 = True
            _pf.setChecked(_offen0)
            _klapp(_offen0)          # Symbol und Sichtbarkeit auch ohne Wechsel

            # DATACORES UND SKILL-BONUS IN EINER ZEILE (Nutzer 26.09.2026,
            # kompakter). Vorher: gruenes Band ueber die ganze Breite plus
            # zwei zweizeilige Datacore-Bloecke mit 32-px-Symbolen. Jetzt:
            # "[Symbol] Name x8 · [Symbol] Name x8 · Skills x1.392 Name".
            # Der lange Erklaertext bleibt als Tooltip erhalten.
            _via_txt = (t("pinned") if getattr(self, "_bd_invention_char", 0)
                       else t("best character marked \u201eFor invention\u201c"))
            import html as _h_sk
            if _skill_mod > 1.0 + 1e-9:
                # DER CHARAKTERNAME IST DIE WICHTIGSTE INFORMATION (Nutzer:
                # "welcher Charakter den besten Skillbonus hat, sollte farblich
                # hervorgehoben werden") - amber und fett; `html.escape`, weil
                # EVE-Namen & enthalten duerfen.
                _skill_lbl = QLabel(
                    f'<span style="color:{theme.GREEN}; font-weight:700;">'
                    + t("Skills \u00d7{mod}").format(mod=f"{_skill_mod:.3f}")
                    + f'</span> <span style="color:{theme.AMBER}; font-weight:800;">'
                    f'{_h_sk.escape(str(_skill_char))}</span>')
                _skill_lbl.setToolTip(t(
                    "<b>Skill bonus active: \u00d7{mod}</b> on the base success "
                    "chance \u2013 skills of <span style='color:{color}; font-size:15px; "
                    "font-weight:800;'>{name}</span> ({via})"
                ).format(mod=f"{_skill_mod:.3f}", color=theme.AMBER,
                         name=_h_sk.escape(str(_skill_char)), via=_via_txt))
            else:
                _skill_lbl = QLabel(
                    f'<span style="color:{theme.AMBER}; font-weight:700;">'
                    + t("\u26A0 No skill bonus") + '</span>')
                _skill_lbl.setToolTip(t(
                    "\u26A0 <b>No skill bonus included</b> (base SDE value) - mark a "
                    "character as \u201eFor invention\u201c in the build characters tab "
                    "+ \u201eLoad job slots\u201c for the real, higher success chance."))
            _skill_lbl.setStyleSheet("font-size:13px;")

            # Ingame-Layout nachgebaut: LINKS Input (Datacores + Decryptor mit
            # Icons, wie die zwei Slots + der Decryptor-Slot im Spiel), Pfeil,
            # RECHTS Outcome (Ziel-Icon + Erfolgschance/ME/TE/Runs als Balken-
            # artige Zeilen, wie das "OUTCOME"-Panel im Ingame-Fenster).
            row = QHBoxLayout(); row.setSpacing(14)
            left = QVBoxLayout(); left.setSpacing(4)
            dc_row = QHBoxLayout(); dc_row.setSpacing(6)
            for d, q in datacores:
                dc_row.addWidget(self._icon_label(d, size=20))
                _dc_name = extra_names.get(d, f'#{d}')
                # "Datacore - " steht im Namen jedes Datacores; das Symbol
                # sagt es schon. Voller Name im Tooltip (so heisst er im Spiel
                # und auf der Einkaufsliste).
                # de_scan6: aus  (Item-Name-Praefix aus der SDE, kein Anzeigetext)
                _dc_kurz = _dc_name[11:] if _dc_name.startswith("Datacore - ") else _dc_name
                # de_scan6: an
                dc_lbl = QLabel(f"{_dc_kurz} <b>\u00d7{q}</b>")
                dc_lbl.setStyleSheet("font-size:11px;")
                dc_lbl.setToolTip(_dc_name + " \u2013 " + t("\u00d7{n} per attempt").format(n=q)
                                  + ("\n" + t("Needed for copying the T1 original "
                                               "(one copy run per attempt).")
                                     if d in {int(_m) for _m, _ in (getattr(
                                         recipes, "invention_copy_mats", {}) or {}).get(bp_id, [])}
                                     else ""))
                dc_row.addWidget(dc_lbl)
                _dc_sep = QLabel("\u00b7"); _dc_sep.setObjectName("Muted")
                dc_row.addWidget(_dc_sep)
            dc_row.addWidget(_skill_lbl)
            dc_row.addStretch()
            left.addLayout(dc_row)
            dec_row = QHBoxLayout(); dec_row.setSpacing(6)
            dec_icon_lbl = QLabel(); dec_icon_lbl.setFixedSize(32, 32)
            dec_row.addWidget(dec_icon_lbl)
            combo = QComboBox()
            for nm, v in decryptor_list:
                combo.addItem(_dv_label(nm, v), nm)
            self._combo_select(combo, self._bd_decryptor_map.get(bp_id, KEIN_DECRYPTOR))
            # NUR PER KLICK (Nutzer 26.09.2026): das Mausrad ueber dem
            # Dropdown scrollt den Reiter, statt den Decryptor zu wechseln
            # und damit eine Rechnung auszuloesen. Gilt fuer alle Bedien-
            # elemente dieses Reiters (Combo, Spinner, Regler) - `ohne_mausrad`.
            ohne_mausrad(combo)
            dec_row.addWidget(combo, 1)
            left.addLayout(dec_row)
            # Die Zeile "Total for n attempts: ..." ist seit 26.09.2026 weg
            # (Nutzer: "diese Zusammenfassung sieht man auch so"). Die Summe
            # steht unten im Reiter ("Invention total (all items)").
            # WARNUNG OHNE DECRYPTOR (Nutzer 26.09.2026: "vielleicht irgendwo eine
            # Warnung, wenn man noch keinen Decryptor gewaehlt hat oder noch keine
            # eigene BPC ME/TE eingegeben - das ist wichtig beim Bauen von T2").
            # Gefuellt in _recompute (kennt Wahl und Own-BPC-Zustand).
            dec_warn_lbl = QLabel("")
            dec_warn_lbl.setWordWrap(True)
            dec_warn_lbl.setStyleSheet(f"color:{theme.AMBER}; font-weight:700;")
            left.addWidget(dec_warn_lbl)
            dec_warn_lbl.hide()
            # "COPY DECRYPTOR" STATT "BEST DECRYPTOR" (emm329, Nutzer 02.10.2026:
            # "der Knopf soll Copy Decryptor heissen, dieselbe Groesse wie Copy
            # T1 und den oben gewaehlten Decryptor-Namen ins Clipboard legen; ist
            # kein Decryptor gewaehlt, kann man ihn nicht druecken"). Das
            # Waehlen des besten macht jetzt nur noch "Auto-Decryptor" in der
            # Seitenleiste (`_inv_alle_besten`, rechnet weiter ueber
            # `_bd_inv_rang`). Name `best_btn`/`_bd_inv_best_btns` bleibt.
            best_btn = QPushButton(t("Copy Decryptor"))
            best_btn.setCursor(Qt.PointingHandCursor)
            # KOMPAKT, LINKS, GEFUELLT (Nutzer 26.09.2026: "der Best-Choice-
            # Knopf ist so bloed ueber das ganze Fenster gezogen, dass man ihn
            # gar nicht sieht. Kompakter links ueber dem Blueprint-Namen,
            # ersichtlicher"). Vorher: nur Rahmen, ueber die volle Breite der
            # Spalte gestreckt - ein amberner Strich mit Text in der Mitte.
            # Jetzt: amberne FLAECHE mit dunkler Schrift (wie das Reservierungs-
            # Schloss "an"), in einer Zeile mit Stretch, damit er so breit ist
            # wie sein Text; die Zeile sitzt direkt ueber dem Ergebnis-Block
            # (Blaupausen-Name), s. u. `_best_row`. Rahmen in Ruhe und Hover
            # gleich stark, sonst springt das Layout.
            # SEIT 26.09.2026 WIE "CREATE SHOPPING LIST" (Nutzer: "Best
            # Decryptor optisch anpassen - Hintergrund normale Tool-Farbe,
            # nur Umrandung und Text Amber"). Kompakt und links bleibt.
            best_btn.setMinimumHeight(24)
            best_btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
            best_btn.setStyleSheet(theme.kopier_knopf_stil())
            _best_row = QHBoxLayout(); _best_row.setSpacing(6)
            _best_row.addWidget(best_btn); _best_row.addStretch()
            self._bd_inv_best_btns = getattr(self, "_bd_inv_best_btns", None) or {}
            self._bd_inv_best_btns[int(bp_id)] = best_btn   # b-Suite
            # Die zwei Einkaufs-Haken stehen seit 26.09.2026 EINMAL oben im
            # Reiter (s. `_top`), nicht mehr in jeder Karte.
            # "ATTEMPTS MANUALLY" IST SEIT 26.09.2026 WEG (Nutzer: "nehmen wir
            # raus, ist nur verwirrend"). Die Versuchszahl kommt immer aus der
            # Sicherheit unter "Invention settings" (Standard 75 %); eigene
            # T2-Kopien im Hangar zieht die Rechnung selbst ab. Alte gespeicherte
            # Handwerte wirken nicht mehr (`_resolve_inv_manual_attempts`).
            # EINSPALTIG (Nutzer: "Flycatcher-Blueprint nach links nehmen,
            # unter Datacores und Decryptor-Dropdown"). Vorher lag das Ergebnis
            # RECHTS neben der Eingabe, mit einem Pfeil dazwischen - das war
            # dem Ingame-Fenster nachgebaut, passte aber nicht zu den anderen
            # Tabs, die ihren Inhalt links stapeln und rechts eine Seitenleiste
            # haben. Jetzt: Datacores -> Decryptor -> Ergebnis untereinander.
            # Der Pfeil entfaellt; die Reihenfolge von oben nach unten sagt
            # dasselbe.
            row.addLayout(left, 1)

            right = QHBoxLayout(); right.setSpacing(10)
            out_icon_lbl = self._icon_label(bp_id, size=48, kind="bp")
            right.addWidget(out_icon_lbl)
            # "COPY T1 ORIGINAL" NEBEN DEM BILD (Nutzer 01.10.2026: "einen
            # amber umrahmten Button 'Copy T1 Original' damit ich den
            # Blueprint kopieren und ingame ins Industriefenster einfuegen
            # kann um das T1 zu bearbeiten - selber Kopier-Button wie im
            # Runplaner"). Kopiert den Namen des T1-ORIGINALS (Kopf der
            # Karte), nicht den des T2-Ergebnisses daneben: kopiert und
            # erfunden wird ingame vom T1. Gleicher Rahmen und gleicher
            # Kopierweg (`_copy_bp_name_value`) wie die Runplaner-Knoepfe.
            _t1_nm = str(extra_names.get(t1_bp) or "").strip()
            if _t1_nm and not _t1_nm.startswith("#"):
                _t1_copy = QPushButton(t("Copy T1 Blueprint"))
                _t1_copy.setCursor(Qt.PointingHandCursor)
                _t1_copy.setMinimumHeight(24)
                _t1_copy.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                _t1_copy.setToolTip(t("Click copies the blueprint name:") + f"\n{_t1_nm}")
                _t1_copy.setStyleSheet(theme.kopier_knopf_stil())
                _t1_copy.clicked.connect(
                    lambda _c=False, _nm=_t1_nm: self._copy_bp_name_value(_nm))
                right.addWidget(_t1_copy, 0, Qt.AlignVCenter)
                self._bd_inv_t1_copy = getattr(self, "_bd_inv_t1_copy", None) or {}
                self._bd_inv_t1_copy[int(bp_id)] = _t1_copy   # b-Suite
            out_col = QVBoxLayout(); out_col.setSpacing(2)
            out_name = QLabel("<b>" + t("{name} Blueprint").format(name=names.get(tid, f"#{tid}")) + "</b>")
            out_name.setStyleSheet(f"color:{theme.CYAN};")
            out_col.addWidget(out_name)
            outcome_lbl = QLabel(); outcome_lbl.setWordWrap(True)
            out_col.addWidget(outcome_lbl)
            if own_bpc_widgets is not None and tid == top_type_id:
                # Diese Karte ist die des tatsächlichen Endprodukts (nicht
                # irgendeines Zwischen-T2-Items) - hier gehören ME/TE/Eigene-BPC
                # hin, direkt neben der Erfolgschance/ME/TE-Zeile. Dieselben
                # Widget-Objekte wie vorher oben im Dialog-Header (nur der Ort
                # hat sich geändert) - ihre ganze bestehende Logik funktioniert
                # unverändert weiter.
                _me_sp, _te_sp, _obc_cb, _obc_runs_lbl, _obc_runs_sp = own_bpc_widgets
                # BUGFIX: Decryptor-Dropdown blieb bisher immer aktiv, auch wenn
                # "Eigene BPC statt Invention" angehakt ist - dabei wird die
                # ganze Invention-Rechnung für DIESES Item ignoriert, der
                # Decryptor spielt dann gar keine Rolle mehr. Jetzt ausgegraut,
                # solange die Checkbox an ist. own_bpc_cb löst beim Umschalten
                # bereits einen kompletten Rebuild aus (_bd_full_rebuild), der
                # diese ganze Funktion samt combo neu aufbaut - hier reicht also
                # der reine Ist-Zustand, KEIN zusätzliches .toggled.connect()
                # nötig (das hätte sich bei jedem Rebuild ein weiteres Mal auf
                # die alte, längst zerstörte combo verbunden -> Absturz beim
                # nächsten Umschalten, siehe Test).
                combo.setEnabled(not _obc_cb.isChecked())
                combo.setToolTip(
                    t("With \u201eOwn BPC instead of invention\u201c the invention is "
                      "skipped - the decryptor no longer matters.")
                    if _obc_cb.isChecked() else "")
                # SAGEN, WESSEN ME/TE HIER GEFRAGT SIND (Sitzung 19). Mit
                # "Eigene BPC" wird nicht mehr erfunden - die Felder darunter
                # meinen dann DEINE Kopie, nicht die erfundene. Sie starten
                # deshalb bei 0/0, und wer nichts eintraegt, rechnet mit 0/0.
                # Das ist die vorsichtige Richtung: mehr Material, laengere
                # Zeit, kein zu schoener Gewinn.
                if _obc_cb.isChecked():
                    # SAGEN, WAS GERADE GILT - nicht beide Faelle aufzaehlen
                    # (Nutzer, Sitzung 19: "also meine 3/2 zaehlt jetzt als
                    # 0/0 oder wie?"). Der alte Text erklaerte das Wenn-Dann
                    # und las sich, als seien die gefundenen Werte doch
                    # verworfen worden.
                    _obc_gefunden = self._bd_lookup_owned_bp_for_item(top_type_id)
                    if _obc_gefunden:
                        _obc_txt = t(
                            "\u26a0 Own BPC: the invention settings above do not "
                            "apply. ME {me} % / TE {te} % come from your own copy "
                            "(the worst-researched one you own) and are what is "
                            "being calculated. Change them if you want.").format(
                                me=int(_obc_gefunden.get("me", 0) or 0),
                                te=int(_obc_gefunden.get("te", 0) or 0))
                    else:
                        _obc_txt = t(
                            "\u26a0 Own BPC: the invention settings above do not "
                            "apply. No copy of your own was found via ESI, so ME/TE "
                            "stay at 0/0 and 0/0 is what is being calculated \u2013 "
                            "enter your own values.")
                    _obc_hint = QLabel(_obc_txt)
                    _obc_hint.setWordWrap(True)
                    _obc_hint.setStyleSheet(f"color:{theme.AMBER}; font-size:11px;")
                    out_col.addWidget(_obc_hint)
                _own_row1 = QHBoxLayout(); _own_row1.setSpacing(6)
                _me_cap = QLabel(t("ME:")); _me_cap.setStyleSheet("font-size:11px;")
                _own_row1.addWidget(_me_cap); _own_row1.addWidget(_me_sp)
                _te_cap = QLabel(t("TE:")); _te_cap.setStyleSheet("font-size:11px;")
                _own_row1.addWidget(_te_cap); _own_row1.addWidget(_te_sp)
                _own_row1.addStretch()
                out_col.addLayout(_own_row1)
                _own_row2 = QHBoxLayout(); _own_row2.setSpacing(6)
                _own_row2.addWidget(_obc_cb)
                _own_row2.addWidget(_obc_runs_lbl)
                _own_row2.addWidget(_obc_runs_sp)
                _own_row2.addStretch()
                out_col.addLayout(_own_row2)
            elif int(getattr(self, "_bd_type", 0) or 0) == industry.BUENDEL_ID \
                    and (getattr(self, "_bd_own_bpc_je_ende", None) or {}).get(int(tid)):
                # BUENDEL, ENDE MIT "EIGENE BPC" (26.09.2026, Invention je
                # Ende): der Haken sitzt in der Karte "Endprodukte", die
                # Rechnung laesst die Invention fuer DIESES Ende aus
                # (_multi_opts_je_ende -> inv_manual_override). Der Decryptor
                # ist dann bedeutungslos - ausgrauen und sagen, warum, sonst
                # stuende hier eine Wahl, die nichts bewegt.
                combo.setEnabled(False)
                combo.setToolTip(t(
                    "With \u201eOwn BPC instead of invention\u201c the invention is "
                    "skipped - the decryptor no longer matters."))
                _obc_hint = QLabel(t(
                    "\u26a0 Own BPC for this end product: the invention is skipped, "
                    "your ME/TE count (below or in the \u201eEnd products\u201c card)."))
                _obc_hint.setWordWrap(True)
                _obc_hint.setStyleSheet(f"color:{theme.AMBER}; font-size:11px;")
                out_col.addWidget(_obc_hint)
            # EIGENE ME/TE DIREKT IN DER INVENTION-KARTE (Nutzer 26.09.2026:
            # "eigentlich sollte man da manuell ME/TE eingeben koennen, und dann
            # sollte es oben in der Endprodukt-Anzeige automatisch auf 'Own'
            # wechseln und die eigene ME/TE uebernehmen - und auch umgekehrt").
            # EIN ZUSTAND, ZWEI GRIFFE: die Felder hier schreiben NICHT selbst in
            # den Zustand, sondern bedienen die Zeile der Endprodukte-Karte
            # (`_bd_multi_zeilen[tid]`) - deren Handler setzen Zustand, Override
            # und den entprellten Neuaufbau; der baut diese Karte aus dem
            # Zustand neu (= die Gegenrichtung). keyboardTracking aus: erst
            # Enter/Verlassen uebernimmt, sonst zerstoert der Neuaufbau das
            # Feld mitten im Tippen (Sitzung-8-Falle).
            _mz_i = (getattr(self, "_bd_multi_zeilen", None) or {}).get(int(tid))
            if int(getattr(self, "_bd_type", 0) or 0) == industry.BUENDEL_ID \
                    and _mz_i is not None:
                _own_an = bool((getattr(self, "_bd_own_bpc_je_ende", None) or {}).get(int(tid)))
                _own_row = QHBoxLayout(); _own_row.setSpacing(8)
                _own_cb = QCheckBox(t("Own BPC (your own ME/TE)"))
                _own_cb.setChecked(_own_an)
                _own_cb.setToolTip(t(
                    "Ticked = you build from your own researched copy: the invention "
                    "for this end product is skipped and your ME/TE count. Same "
                    "switch as \u201eOwn\u201c in the \u201eEnd products\u201c card."))
                _own_row.addWidget(_own_cb)
                _me_lbl_i = QLabel(t("ME:")); _own_row.addWidget(_me_lbl_i)
                _me_i = QSpinBox(); _me_i.setRange(0, 10); _me_i.setKeyboardTracking(False)
                _me_i.setValue(int((getattr(self, "_bd_me_je_ende", None) or {}).get(int(tid), 0) or 0))
                ohne_mausrad(_me_i); _own_row.addWidget(_me_i)
                _te_lbl_i = QLabel(t("TE:")); _own_row.addWidget(_te_lbl_i)
                _te_i = QSpinBox(); _te_i.setRange(0, 20); _te_i.setKeyboardTracking(False)
                _te_i.setValue(int((getattr(self, "_bd_te_je_ende", None) or {}).get(int(tid), 0) or 0))
                ohne_mausrad(_te_i); _own_row.addWidget(_te_i)
                _own_row.addStretch()
                out_col.addLayout(_own_row)
                if not _own_an:
                    # nur hide(): setVisible(True) auf Widgets ohne fertige
                    # Eltern-Kette macht Fenster daraus (b8-Falle).
                    for _w_h in (_me_lbl_i, _me_i, _te_lbl_i, _te_i):
                        _w_h.hide()
                _own_cb.toggled.connect(
                    lambda v, _z=_mz_i: _z["obpc"].setChecked(bool(v)))
                _me_i.valueChanged.connect(
                    lambda v, _z=_mz_i: _z["me"].setValue(int(v)))
                _te_i.valueChanged.connect(
                    lambda v, _z=_mz_i: _z["te"].setValue(int(v)))
                self._bd_inv_own = getattr(self, "_bd_inv_own", None) or {}
                self._bd_inv_own[int(tid)] = {"cb": _own_cb, "me": _me_i, "te": _te_i}
            self._bd_inv_combos = getattr(self, "_bd_inv_combos", None) or {}
            self._bd_inv_combos[int(bp_id)] = combo      # b-Suite / Diagnose
            right.addLayout(out_col, 1)
            body.addLayout(row)          # Eingabe (Datacores + Decryptor)
            body.addLayout(_best_row)    # "Best Decryptor" links, ueber dem Namen
            _out_w = QWidget(); _out_w.setLayout(right)
            body.addWidget(_out_w)       # Ergebnis DARUNTER, nicht daneben

            need_lbl = QLabel(); need_lbl.setWordWrap(True)
            body.addWidget(need_lbl)

            # KOPIERANLEITUNG JE KARTE (Nutzer 26.09.2026: "Alles, was ich pro
            # T2-Blueprint sehen will, ist, wie ich kopieren muss und wie viel -
            # schoen angezeigt und groesser: Copy your T1 original like this ->
            # Job Runs / Runs per Copy"; "jede Karte ihren eigenen Regler";
            # "eine Anzeige, wie lange es dauert und wie viele Science-Slots
            # belegt werden").
            # DER GRUND FUER DEN REGLER (Sitzung 8): EIN Invention-Job
            # verbraucht EINEN Run EINER Kopie, und eine Kopie traegt nur EINEN
            # Job gleichzeitig. Mehr Kopien = mehr Jobs parallel = mehr
            # belegte Science-Slots, kuerzere Wartezeit. Wie viele T2-
            # Blaupausen am Ende herauskommen, aendert der Regler NICHT (das
            # machen Menge und Decryptor).
            # FEHLER BIS 26.09.2026 (nachgestellt): Regler, Kopien-Feld und
            # Anzeige lagen auf `self._inv_*` - JEDE Karte ueberschrieb sie,
            # also bediente der Regler der ersten Karte die LETZTE. Jetzt
            # gehoert alles der Karte (`_bd_inv_split_w[bp_id]`), gemerkt wird
            # je Blaupause (`_bd_inv_split` {bp_id: Kopien}).
            _sp_box = QFrame(); _sp_box.setObjectName("Card")
            _spl = QVBoxLayout(_sp_box)
            _spl.setContentsMargins(12, 8, 12, 8); _spl.setSpacing(6)
            _cp_kopf = QLabel("\u2013")
            _cp_kopf.setTextInteractionFlags(Qt.TextSelectableByMouse)
            _spl.addWidget(_cp_kopf)
            _inv_row = QHBoxLayout(); _inv_row.setSpacing(10)
            _inv_row.addWidget(QLabel(t("Invention jobs at once:")))
            _sl = QSlider(Qt.Horizontal)
            _sl.setRange(1, max(1, int(getattr(self, "_bd_inv_slots", 10) or 10)))
            _sl.setValue(max(1, int((self._bd_inv_split or {}).get(int(bp_id), 1) or 1)))
            _sl.setMinimumWidth(140)
            _sl.setMaximumWidth(260)
            ohne_mausrad(_sl)
            _sl.setToolTip(t(
                "How many invention jobs run at the same time \u2013 one T1 copy "
                "each, one science slot each.\n"
                "Left = 1 job (slow, 1 slot busy),\n"
                "right = all free science slots (as fast as possible).\n"
                "It does NOT change how many T2 blueprints you get \u2013 that "
                "depends on quantity and decryptor."))
            _inv_row.addWidget(_sl)
            _inv_lbl = QLabel("")
            _inv_lbl.setWordWrap(True)
            _inv_row.addWidget(_inv_lbl, 1)
            _spl.addLayout(_inv_row)
            body.addWidget(_sp_box)
            # EIGENE BPC IM BUENDEL: keine Invention fuer dieses Ende, also
            # auch nichts zu kopieren - die Kopieranleitung waere irrefuehrend.
            if int(getattr(self, "_bd_type", 0) or 0) == industry.BUENDEL_ID \
                    and (getattr(self, "_bd_own_bpc_je_ende", None) or {}).get(int(tid)):
                _sp_box.hide()
            self._bd_inv_split_w[int(bp_id)] = {"slider": _sl, "kopf": _cp_kopf,
                                                "lbl": _inv_lbl, "fill": None,
                                                "att": 0}
            # ZEILE "Materialkosten / Bauzeit / Invention-Zeit" ENTFERNT
            # (Nutzer: "unnoetige Ueberlastung des UI"). Alle drei Werte sind
            # NEBENINFORMATION: die Materialkosten stehen als Gesamtsumme oben
            # in der Kopfzeile, die Bauzeit im Runplaner, und die
            # Invention-Zeit war laut eigenem Hinweis ohnehin "nur zur Info".
            # Das Label bleibt als TOOLTIP-Traeger - die drei Zahlen sind fuer
            # den Decryptor-Vergleich weiterhin abrufbar, nur nicht mehr
            # dauerhaft sichtbar.
            score_lbl = QLabel(); score_lbl.setWordWrap(True)
            score_lbl.setObjectName("Muted"); score_lbl.setStyleSheet("font-size:11px;")
            score_lbl.setVisible(False)
            body.addWidget(score_lbl)
            cards_layout.insertWidget(insert_at, card)
            insert_at += 1

            # Materialkosten EINES Bau-Runs bei 0% ME (isoliert für dieses Item,
            # Sub-Komponenten behalten ihre normale Bau-vs-Kauf-Logik) - Basis,
            # auf die die BPC-ME (vom Decryptor) angewandt wird, damit "Beste
            # Wahl für Profit" nicht nur Invention-, sondern auch Material-
            # kosten mit einrechnet. Rig-/Struktur-ME bleibt hier bewusst außen
            # vor (siehe industry.invention_decryptor_options).
            try:
                _prod_qty = (recipes.product_to_bp.get(tid) or (0, 0, 1))[2] or 1
                _opts0 = dict(getattr(self, "_bd_opts", None) or {})
                _opts0["me_map"] = dict(_opts0.get("me_map") or {})
                _opts0["me_map"][tid] = 0
                _opts0["invention"] = False
                _pm = (getattr(self, "_bd_pricemap", None) or {}).get
                mc0_per_run = (industry.build_cost(tid, _pm, recipes, _opts0) or 0.0) * _prod_qty
            except Exception:
                mc0_per_run = 0.0

            # Bauzeit EINES Runs mit aktuellen Struktur-/Skill-Boni, aber OHNE
            # Decryptor-TE (direkt aus SDE: recipes.activity_time) - Basis für
            # die Zeitgewichtung in invention_decryptor_options (Schritt 2/3).
            try:
                _te_mfg = (getattr(self, "_bd_opts", None) or {}).get(
                    "te_factor_mfg", (getattr(self, "_bd_opts", None) or {})
                    .get("te_factor", 1.0))
                build_seconds_0dec = (recipes.activity_time.get(
                    (bp_id, industry.MANUFACTURING), 0) or 0) * _te_mfg
            except Exception:
                build_seconds_0dec = 0.0

            # Invention-JOB-Zeit (nicht Bauzeit!) direkt aus der SDE
            # (recipes.activity_time für activity_id=INVENTION), mit dem
            # Zeit-Rig-Bonus der für Invention gewählten Struktur (Struktur-
            # Tab zeigte den bisher nur an, ohne ihn irgendwo zu verrechnen -
            # das war die Lücke hinter "noch nicht in Baurechnung genutzt").
            # Decryptoren wirken NICHT auf die Job-Zeit selbst (nur auf Runs/
            # ME/TE/Erfolgschance der fertigen BPC), deshalb hier fix pro Item.
            _inv_time_base = recipes.activity_time.get((t1_bp, industry.INVENTION), 0) or 0
            # ROLLE, SICHERHEIT UND SKILLS (emm325, s. industry.science_jobzeit):
            # Engineering Complex wirkt auf Science-Jobs wie auf Fertigung,
            # der Rig mal Sicherheit, Advanced Industry/Science vom
            # Invention-Charakter (gepinnt oder der mit dem besten Bonus).
            _sec_i = float((inv_struct or {}).get("security", 1.0) or 1.0)
            _inv_struct_pct = ((self._struct_extra_rig_pct(inv_struct, "invention")
                                if inv_struct else 0) or 0) * _sec_i
            _copy_rig_pct = ((self._struct_extra_rig_pct(inv_struct, "copy")
                              if inv_struct else 0) or 0) * _sec_i
            _rolle_i = self._STRUCT_ROLE_TIME.get(
                (inv_struct or {}).get("type", "npc"), {}).get("mfg", 0.0)
            _adv_i, _sci_i = self._inv_zeit_skills(_skill_char)
            _inv_time_per_attempt = industry.science_jobzeit(
                _inv_time_base, "invention", _rolle_i, _inv_struct_pct, _adv_i)
            _copy_time_per_run = industry.science_jobzeit(
                recipes.activity_time.get((t1_bp, industry.COPYING), 0) or 0,
                "copy", _rolle_i, _copy_rig_pct, _adv_i, _sci_i)

            def _recompute(combo=combo, bp_id=bp_id, base_runs=base_runs,
                          base_prob=base_prob, datacores=datacores,
                          runs_needed=runs_needed, outcome_lbl=outcome_lbl,
                          need_lbl=need_lbl, dec_icon_lbl=dec_icon_lbl,
                          dec_warn_lbl=dec_warn_lbl,
                          score_lbl=score_lbl, mc0_per_run=mc0_per_run,
                          build_seconds_0dec=build_seconds_0dec,
                          inv_time_per_attempt=_inv_time_per_attempt,
                          inv_struct_pct=_inv_struct_pct,
                          copy_secs_per_attempt=_copy_time_per_run):
                key = combo.currentData()
                dv = next((v for n, v in decryptor_list if n == key),
                          (1.0, 0, 0, 0, None))
                dec_icon_lbl.clear()
                if dv[4]:
                    pm = self._item_pixmap(dv[4], size=32)
                    if pm:
                        dec_icon_lbl.setPixmap(
                            pm.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                outcome = industry.invention_outcome(base_runs, base_prob, dv)
                outcome_lbl.setText(
                    f'<span style="color:{theme.MUTED};">' + t("Success chance") + '</span> '
                    f'<b>{outcome["prob"]*100:.1f}%</b>  \u00b7  '
                    f'<span style="color:{theme.MUTED};">' + t("Runs/success") + '</span> '
                    f'<b>{outcome["runs"]}</b>  \u00b7  '
                    # de_scan3: aus  (HTML-Geruest, die Woerter laufen durch t())
                    f'<span style="color:{theme.MUTED};">' + t("ME")
                    # FEHLENDES f (Nutzer, Sitzung 19): ohne das Praefix stand
                    # der Platzhalter woertlich in der Zeile - "ME
                    # {outcome["me_pct"]}%". Die TE-Haelfte darunter war eine
                    # f-Zeichenkette und zeigte richtig 4 %, deshalb fiel es
                    # lange nicht auf.
                    + f'</span> <b>{outcome["me_pct"]}%</b>'
                    # de_scan3: an
                    f'  \u00b7  <span style="color:{theme.MUTED};">' + t("TE") + '</span> '
                    f'<b>{outcome["te_pct"]}%</b>')
                dc_cost = sum((adj_prices.get(d, 0) or 0) * q for d, q in datacores)
                dcy_tid = dv[4]
                dcy_cost = (adj_prices.get(dcy_tid, 0) or 0) if dcy_tid else 0.0
                # Bereits per ESI geladene, eigene BPC-Runs decken einen Teil
                # ab - egal ob Endprodukt oder Komponente, für JEDES Item hier
                # mit eigenem bp_id-Eintrag (aus "Eigene BPCs für alle Items
                # laden" bzw. dem Endprodukt-spezifischen ESI-Laden im
                # "Blaupausen je Stufe"-Panel).
                _owned_runs = self._resolve_inv_owned_runs().get(bp_id, 0)
                _runs_still_needed = max(0, runs_needed - _owned_runs)
                ap = industry.invention_attempt_plan(
                    _runs_still_needed, outcome, [dc_cost], dcy_cost,
                    confidence=self._bd_inv_confidence())
                # KEINE ZUSATZZEILEN (Nutzer 26.09.2026: "for runs = successes,
                # on average it would take, invention cost - die koennen weg").
                # Geblieben ist nur der Hinweis auf eigene T2-Kopien - der
                # aendert die Zahl.
                need_lbl.setText(
                    f'<span style="color:{theme.CYAN};">'
                    + t("{n} runs already on hand as own BPC \u2013 fewer "
                        "attempts needed").format(n=_owned_runs) + '</span>'
                    if _owned_runs else "")
                need_lbl.setVisible(bool(_owned_runs))
                total_cost = ap["confident_cost"]
                _inv_attempts_n = int(ap["confident_attempts"] or 0)
                # WARNUNG OHNE DECRYPTOR: "No decryptor" steht, der Nutzer hat
                # ihn nie selbst gewaehlt (Combo, "Best Decryptor", "for all"
                # oder gespeicherter Plan -> `_bd_dec_bestaetigt`) und die Karte
                # rechnet wirklich mit Invention (Combo nicht gesperrt = keine
                # eigene BPC).
                _dec_offen = (key == KEIN_DECRYPTOR and combo.isEnabled()
                              and int(bp_id) not in
                              (getattr(self, "_bd_dec_bestaetigt", None) or set()))
                dec_warn_lbl.setText(t(
                    "\u26a0 No decryptor chosen yet \u2013 pick one or press "
                    "\u201eAuto-Decryptor\u201c; building from your own copy? "
                    "Tick \u201eOwn BPC\u201c and enter its ME/TE.") if _dec_offen else "")
                dec_warn_lbl.setVisible(_dec_offen)
                self._bd_inv_dec_offen = getattr(self, "_bd_inv_dec_offen", None) or {}
                self._bd_inv_dec_offen[int(bp_id)] = _dec_offen
                material_cost = mc0_per_run * (1 - outcome["me_pct"] / 100.0) * runs_needed
                _bz_txt = _iz_txt = _iz_tip_extra = ""
                time_txt = ""
                if build_seconds_0dec:
                    days = (build_seconds_0dec * (1 - outcome["te_pct"] / 100.0)
                           * runs_needed) / 86400.0
                    time_txt = "x"          # nur noch Bedingung
                    _bz_txt = t("\u2248{d} days").format(d=f"{days:.2f}")
                # KOPIERANLEITUNG DIESER KARTE fuellen (je Karte, s. `_sp_box`).
                # Als Funktion an der Karte gemerkt, damit Regler und Slot-
                # Feld sie ohne vollen Rebuild aufrufen koennen.
                def _fuelle_aufteilung(_att=_inv_attempts_n, _oc=outcome,
                                       _ipa=inv_time_per_attempt, _bp=int(bp_id),
                                       _cpr=copy_secs_per_attempt):
                    _sw = (getattr(self, "_bd_inv_split_w", None) or {}).get(_bp)
                    if not _sw:
                        return
                    # Regler/Slots geaendert -> Runplaner-Science folgt (emm425).
                    self._science_spaeter()
                    # Versuchszahl fuer die Nutzstufen des Reglers merken.
                    _sw["att"] = int(_att or 0)
                    # GANZE BREITE NUTZBAR (Nutzer 26.09.2026: "warum kann ich
                    # die Regler nicht ganz bis rechts ziehen?"): der Regler
                    # reichte bis zu den freien Slots (10), aber mehr Kopien als
                    # Versuche gibt es nicht - bei 4 Versuchen blieb er bei 4/10
                    # stehen. Rechts = min(freie Slots, Versuche).
                    _max_sl = max(1, min(int(getattr(self, "_bd_inv_slots", 10) or 10),
                                         int(_att or 0) or 1))
                    if _sw["slider"].maximum() != _max_sl:
                        _sw["slider"].blockSignals(True)
                        _sw["slider"].setMaximum(_max_sl)
                        _sw["slider"].blockSignals(False)
                    _auf = industry.kopien_aufteilung(
                        _att, int(_oc.get("runs") or 1),
                        slots=int(getattr(self, "_bd_inv_slots", 10) or 10),
                        kopien=_sw["slider"].value(),
                        prob=_oc.get("prob"))
                    if not _auf["kopien"]:
                        _sw["kopf"].setText("\u2013")
                        _sw["lbl"].setText("")
                        return
                    # GROSS, WIE IM SPIEL ZU TIPPEN. "Job Runs" und "Runs per
                    # Copy" heissen im Kopierfenster so und bleiben englisch, in
                    # JEDER Sprachfassung.
                    _zahl = (f'font-size:{theme.FS_KPI}; font-weight:800; '
                             f'color:{theme.AMBER}; font-family:{theme.MONO};')
                    _sw["kopf"].setText(
                        f'<div style="color:{theme.MUTED}; font-size:{theme.FS_BASE};">'
                        + t("Copy your T1 original like this \u2192") + '</div>'
                        # de_scan3: aus  (EVE-Feldnamen, bleiben in jeder Sprache englisch)
                        + f'<div style="font-size:15px; font-weight:700;">'
                        f'Job Runs: <span style="{_zahl}">{_auf["kopien"]}</span>'
                        f'</div><div style="font-size:15px; font-weight:700;">'
                        f'Runs per Copy: <span style="{_zahl}">'
                        f'{_auf["runs_je_kopie"]}</span></div>'
                        # de_scan3: an
                        # KOPIERDAUER (emm325, Nutzer: "wie lange das Kopieren
                        # dauert, koennen wir nicht anzeigen?"): EIN Job mit
                        # Kopien x Runs je Kopie Kopier-Runs.
                        + (f'<div style="font-size:15px; font-weight:700;">'
                           + t("Copy job: \u2248{d}").format(
                               d=f'<span style="{_zahl}">'
                                 f'{self._fmt_dur(_cpr * _auf["kopien"] * _auf["runs_je_kopie"])}'
                                 f'</span>') + '</div>' if _cpr else ""))
                    # DAUER UND BELEGTE SLOTS (Nutzer: "eine Anzeige, wo man
                    # sieht, wie lange es dauert und wie viele Science-Slots
                    # belegt werden"). Wandzeit = Wellen x Zeit je Versuch.
                    # WEISS UND SO GROSS WIE "Job Runs", ZAHLEN AMBER (Nutzer
                    # 26.09.2026: "zeige deutlicher, wie viele Science-Slots
                    # belegt werden ... in Weiss und gleiche Groesse wie oben
                    # Job Runs und Runs per Copy, Zahlen auch gleich gross und
                    # Amber").
                    _teile = [t("{n} science slot(s) busy").format(
                        n=f'<span style="{_zahl}">{_auf["parallel"]}</span>')]
                    if _ipa:
                        _teile.append(t("done in \u2248{d}").format(
                            d=f'<span style="{_zahl}">'
                              f'{self._fmt_dur(_ipa * _auf["wellen"])}</span>'))
                    if _auf["rest_reserve"]:
                        _teile.append(t("{n} runs in reserve").format(
                            n=_auf["rest_reserve"]))
                    # "DANACH INVENTION:" (emm324, Nutzer 01.10.2026: "das
                    # dauert ingame nur 1h20min und nicht 2T12h"): die Zeile
                    # stand direkt unter der KOPIER-Anleitung und las sich
                    # wie die Dauer des Kopierjobs - gemeint sind die
                    # Invention-Jobs danach (Wellen x Zeit je Versuch).
                    _sw["lbl"].setText(
                        f'<span style="color:{theme.TEXT}; font-size:15px; '
                        f'font-weight:700;">'
                        + t("Then invention:") + " "
                        + " \u00b7 ".join(_teile) + '</span>')
                    _sw["lbl"].setToolTip(t(
                        "{total} copy runs in total for {att} required attempts.\n"
                        "{waves} job waves one after another (each wave {par} jobs "
                        "in parallel).\n"
                        "You have to make the copies yourself first \u2013 with ONE "
                        "original, copy jobs run one after another."
                    ).format(total=_auf["versuche_gesamt"], att=_att,
                             waves=_auf["wellen"], par=_auf["parallel"]))
                _sw0 = (getattr(self, "_bd_inv_split_w", None) or {}).get(int(bp_id))
                if _sw0 is not None:
                    _sw0["fill"] = _fuelle_aufteilung
                try:
                    _fuelle_aufteilung()
                except Exception:
                    pass          # Anzeige darf den Bauplan nie blockieren

                inv_time_txt = ""
                if inv_time_per_attempt:
                    total_inv_secs = inv_time_per_attempt * _inv_attempts_n
                    inv_time_txt = "x"      # nur noch Bedingung
                    # Der Rig-Bonus ist im Wert schon DRIN - er stand vorher
                    # als Klammer daneben. Gehoert in den Tooltip, nicht in
                    # die Zeile.
                    _iz_txt = (f"\u2248{self._fmt_dur(total_inv_secs)} "
                               f"({_inv_attempts_n}\u00d7)")
                    if inv_struct_pct:
                        _iz_tip_extra = t(
                            "Invention time includes {pct}% structure rig bonus."
                        ).format(pct=f"{inv_struct_pct:.0f}")
                # Auch hier zeilenweise; die Klammer-Erklaerungen wandern in
                # den Tooltip, statt die Zeile zu verdoppeln.
                _sc_rows = [(t("Material cost ({me}% ME)").format(
                                 me=outcome["me_pct"]),
                             f"\u2248{isk(material_cost)}", None)]
                if time_txt:
                    _sc_rows.append((t("Build time"), _bz_txt, None))
                if inv_time_txt:
                    _sc_rows.append((t("Invention time"), _iz_txt, None))
                score_lbl.setText(_kv_rows(_sc_rows))
                # Unsichtbar, aber die Zahlen bleiben abrufbar: derselbe Text
                # haengt am Ergebnis-Block, wo man den Decryptor waehlt.
                _sc_plain = " \u00b7 ".join(
                    f"{_l}: {_v}" for _l, _v, _c in _sc_rows)
                outcome_lbl.setToolTip(_sc_plain)
                score_lbl.setToolTip(t(
                    "Material cost: only the base ME of this item \u2013 structure and "
                    "rig ME apply on top and are the same for all decryptors.\n"
                    "Build time is for information only \u2013 \u201eAuto-Decryptor\u201c looks "
                    "at total profit alone.\n"
                    "Invention time is sequential with 1 free science slot; faster "
                    "accordingly with more slots.")
                    + (("\n" + _iz_tip_extra) if _iz_tip_extra else ""))
                self._bd_decryptor_map[bp_id] = key
                _card_costs[bp_id] = total_cost
                _attempts_n = max(0, int(_inv_attempts_n or 0))
                self._bd_invention_needs[bp_id] = {
                    "datacores": [(d, q * _attempts_n) for d, q in datacores],
                    "decryptor_id": dv[4], "decryptor_qty": _attempts_n if dv[4] else 0,
                    "attempts": _attempts_n, "successes_needed": ap["successes_needed"],
                    # für die Runplaner-Gesamtzeile: Invention + Kopieren
                    # (1 x 1-Run-BPC je Versuch; Kopierzeit aus der SDE,
                    # Struktur-/Skill-Boni bewusst weggelassen -> "grob")
                    "inv_secs": int((inv_time_per_attempt or 0) * _attempts_n),
                    "copy_secs": int((copy_secs_per_attempt or 0) * _attempts_n),
                    # SCIENCE-BLOCK IM RUNPLANER (emm411): dieselben Zahlen
                    # wie die Kopieranleitung der Karte - EINE Quelle.
                    "runs_je_kopie": int(outcome.get("runs") or 1),
                    "prob": outcome.get("prob"),
                    "ipa": float(inv_time_per_attempt or 0),
                    "cpr": float(copy_secs_per_attempt or 0),
                    "t1": int(t1_bp or 0),
                }
                # Runplaner-Science-Block folgt der Karte (emm425).
                self._science_spaeter()
                # KURZFASSUNG IN DER KOPFZEILE (zugeklappte Karte): Decryptor,
                # Versuche, Invention-Kosten - dieselben Zahlen wie unten.
                _kz = (getattr(self, "_bd_inv_karten", None) or {}).get(int(bp_id))
                if _kz and _kz.get("kurz") is not None:
                    _kz["kurz"].setText(
                        (f'<span style="color:{theme.AMBER}; font-weight:700;">\u26a0 </span>'
                         if _dec_offen else "")
                        + f"{_h_sum.escape(dec_anzeige(key))}  \u00b7  "
                        + t("{n} attempts").format(n=_attempts_n)
                        + f'  \u00b7  <span style="color:{theme.AMBER};">'
                          f'\u2248{isk(total_cost)}</span>')
                _update_total()

            def _on_change(_idx, bp_id=bp_id, combo=combo):
                key = combo.currentData()
                self._bd_decryptor_map[bp_id] = key
                # selbst gewaehlt -> keine Warnung mehr (auch "No decryptor")
                self._bd_dec_bestaetigt = set(getattr(self, "_bd_dec_bestaetigt", None) or ())
                self._bd_dec_bestaetigt.add(int(bp_id))
                dv = next((v for n, v in decryptor_list if n == key),
                          (1.0, 0, 0, 0, None))
                self._bd_opts.setdefault("inv_decryptor_map", {})[bp_id] = dv
                cb = getattr(self, "_bd_full_rebuild", None)
                if cb:
                    cb()
            combo.currentIndexChanged.connect(_on_change)

            # NUTZER-FUND (Sitzung 8): "ich kann hier gar nichts eingeben."
            # URSACHE damals: der Regler rief _bd_full_rebuild, das baute den
            # Reiter neu und ZERSTOERTE das Bedienelement unter der Maus. Der
            # Regler ruft deshalb NUR die Fuellung seiner Karte - kein Rebuild.
            # NUTZSTUFEN-SCHNAPPEN (Sitzung 9: "ich kann ihn hoeher ziehen als
            # er einen Nutzen hat"): die Wandzeit haengt an ceil(Versuche/
            # Kopien) - jede Kopienzahl, die dieselben Runs je Kopie ergibt
            # wie eine kleinere, bringt NICHTS. Der Regler schnappt auf die
            # KLEINSTE Kopienzahl derselben Zeitstufe: ceil(att / ceil(att / N)).
            _sw_k = self._bd_inv_split_w[int(bp_id)]

            def _nutzstufe(v, _sw=_sw_k):
                import math
                _att = int(_sw.get("att", 0) or 0)
                v = int(v)
                if _att <= 0 or v <= 1:
                    return v
                return math.ceil(_att / math.ceil(_att / min(v, _att)))

            # SPAETE BINDUNG (emm497, Nutzer: "aendert man bei den
            # endprodukten die anzahl, kann man den regler nurnoch bis in
            # die Mitte ziehn"): `_nutzstufe` wird in DIESER Schleife je
            # Karte neu definiert - ein nackter `_nutzstufe(v)`-Aufruf im
            # Handler zeigte zur Laufzeit IMMER auf die zuletzt definierte
            # Fassung, also auf die Versuchszahl der LETZTEN Karte. Solange
            # alle Karten gleich viele Versuche hatten, fiel das nicht auf;
            # nach einer Mengenaenderung schnappte der Regler von Karte A
            # auf das att von Karte B (gemessen: att=44, Schnapp auf 2).
            # Dieselbe Fehlerklasse wie der Multi-Knopf vom 20.09.2026 -
            # deshalb als Vorgabewert binden.
            def _regler_zieht(v, _sw=_sw_k, _bp=int(bp_id), _stufe=_nutzstufe):
                v2 = _stufe(v)
                _s = _sw["slider"]
                if _s.value() != v2:
                    _s.blockSignals(True)
                    _s.setValue(v2)
                    _s.blockSignals(False)
                self._bd_inv_split[_bp] = int(v2)
                self._inv_split_merken_spaeter()
                if _sw.get("fill"):
                    try:
                        _sw["fill"]()
                    except Exception:
                        pass
            _sw_k["slider"].valueChanged.connect(_regler_zieht)

            def _rangliste(combo=combo, base_runs=base_runs,
                           base_prob=base_prob, datacores=datacores,
                           runs_needed=runs_needed, mc0_per_run=mc0_per_run,
                           build_seconds_0dec=build_seconds_0dec, score_lbl=score_lbl,
                           bp_id=bp_id, top_type_id=top_type_id):
                """Rechnet ALLE Decryptoren (inkl. 'Kein Decryptor') mit der
                ECHTEN production_plan-Formel durch (exakt dieselbe wie die
                Kopfzeile: Material inkl. Job-Kosten-Kopplung an den
                Materialwert, Invention-Kosten) und wählt den mit dem
                niedrigsten Gesamtpreis = höchstem Gewinn - keine separate
                Näherungsformel mehr, die von der Kopfzeile abweichen könnte."""
                if top_type_id is not None:
                    ranked = industry.invention_best_decryptor_by_real_cost(
                        top_type_id, self._bd_qty, self._bd_pricemap.get,
                        self._bd_recipes, self._bd_opts, bp_id, decryptor_list)
                    # Ist gerade eine Orderbuch-Ladder aktiv (nach "Neu
                    # berechnen"), muss das Ranking dieselbe ladder-korrigierte
                    # Materialkosten-Basis nutzen wie die Kopfzeile - sonst
                    # könnte "Beste Wahl" wieder von "Gesamt" abweichen, genau
                    # wie der zuletzt gefundene Bug.
                    # Gueltigkeit NUR ueber _bd_ladder_ctx - sonst faellt das
                    # Ranking bei geaenderter Menge auf Flachpreise zurueck,
                    # waehrend die Kopfzeile schon orderbuch-genau rechnet.
                    _lctx = self._bd_ladder_ctx(self._bd_qty)
                    _obs = (_lctx or {}).get("obs")
                    if _obs is not None:
                        for _r in ranked:
                            _test_opts = dict(self._bd_opts)
                            _dm = dict(self._bd_opts.get("inv_decryptor_map") or {})
                            _dm[bp_id] = _r["decryptor"]
                            _test_opts["inv_decryptor_map"] = _dm
                            try:
                                _tp = industry.production_plan(
                                    top_type_id, self._bd_qty, self._bd_pricemap.get,
                                    self._bd_recipes, _test_opts)
                                _mat_ladder = industry.ladder_cost_for_buy(
                                    (_tp or {}).get("buy") or {}, _obs,
                                    self._bd_pricemap.get)
                                # BESTAND NICHT VERGESSEN. Die Kopfzeile rechnet
                                # mat_ladder + job + inv + stock_cost; hier
                                # fehlte der letzte Summand. Folge: Decryptoren,
                                # die weniger KAUFEN und dafuer mehr aus dem
                                # BESTAND ziehen, sahen kuenstlich guenstig aus -
                                # "Beste Wahl" nahm Attainment (27,8 % Marge)
                                # statt Parity (30,8 %), obwohl die Kopfzeile
                                # Parity als besser auswies (Nutzer-Fund).
                                # Der ungefilterte Rang aus
                                # invention_best_decryptor_by_real_cost war
                                # richtig - erst diese Korrektur hat ihn
                                # verdorben.
                                _r["total_cost"] = (_mat_ladder
                                                    + float((_tp or {}).get("job_cost", 0.0))
                                                    + float((_tp or {}).get("inv_cost", 0.0))
                                                    + float((_tp or {}).get("stock_cost", 0.0)))
                            except Exception:
                                pass
                        ranked.sort(key=lambda r: r["total_cost"])
                else:
                    dc_cost = sum((adj_prices.get(d, 0) or 0) * q for d, q in datacores)
                    ranked = industry.invention_decryptor_options(
                        base_runs, base_prob, runs_needed, decryptor_list, [dc_cost],
                        mc0_per_run, lambda t: adj_prices.get(t, 0) or 0.0,
                        build_seconds_per_run_0decryptor=build_seconds_0dec)
                return ranked

            def _dec_name_kopieren(_checked=False, combo=combo):
                _nm = combo.currentData()
                if not _nm or _nm == KEIN_DECRYPTOR:
                    return
                _nm = str(_nm)
                # Fallback-Liste ohne SDE kennt nur "Augmentation" usw. - im
                # Spiel heisst das Item "Augmentation Decryptor".
                if not _nm.endswith("Decryptor"):
                    _nm = _nm + " Decryptor"
                self._copy_bp_name_value(_nm)

            def _dec_knopf_stand(_i=None, combo=combo, _b=best_btn):
                _an = (combo.isEnabled() and bool(combo.currentData())
                       and combo.currentData() != KEIN_DECRYPTOR)
                _b.setEnabled(_an)
                _b.setToolTip(t("Click copies the name of the decryptor chosen above "
                                "\u2013 paste it into the in-game search.") if _an else
                              t("No decryptor chosen \u2013 nothing to copy."))
            best_btn.clicked.connect(_dec_name_kopieren)
            combo.currentIndexChanged.connect(_dec_knopf_stand)
            _dec_knopf_stand()
            # "BEST DECRYPTOR FOR ALL BLUEPRINTS" (Nutzer 26.09.2026: "damit man
            # nicht jeden Blueprint separat ansteuern muss"). Nur Karten, deren
            # Decryptor-Wahl ueberhaupt gilt (bei "Own BPC" ist sie gesperrt).
            # EIGENE BPC (Combo gesperrt): keine Rangliste - "Auto-Decryptor"
            # laesst die Karte aus (Nutzer-Screenshot 26.09.2026: Sacrilege mit
            # Own BPC bekam "Parity"); "Copy Decryptor" sperrt `_dec_knopf_stand`.
            if combo.isEnabled():
                self._bd_inv_rang[int(bp_id)] = (_rangliste, decryptor_list)

            _recompute()
            # Direkt beim Aufbau auch in opts eintragen (falls schon ein
            # Decryptor gewählt war, z.B. nach einer Mengenänderung).
            _dv0 = next((v for n, v in decryptor_list
                        if n == self._bd_decryptor_map.get(bp_id, KEIN_DECRYPTOR)),
                       None)
            if _dv0 and _dv0[4] is not None:
                self._bd_opts.setdefault("inv_decryptor_map", {})[bp_id] = _dv0
        _update_total()
        cards_layout.insertWidget(insert_at, total_box)
        # DIE ZWEI EINKAUFS-HAKEN GEHOEREN HIERHER (Nutzer-Entscheid,
        # Sitzung 20). Sie standen als eigene Mini-Karte in der Seitenleiste
        # des Bauplans, danach kurz als Anhaengsel der Kategorien-Karte -
        # beides falsch am Platz: die Kategorien-Karte beantwortet "habe ich
        # die Blaupausen", diese zwei "soll das Invention-Material in die
        # Einkaufsliste". Hier stehen sie direkt unter der Rechnung, aus der
        # ihre Mengen stammen (Versuche x Datacores je Versuch).
        # (Die zwei Einkaufs-Haekchen stehen seit Sitzung 20 oben unter
        # "Best choice for profit", nicht mehr am Reiterende.)
        _top_covered = any(tid == top_type_id for tid, _bp_id, _runs, _inv in items)
        if not _top_covered:
            _own_bpc_fallback_card()

    def _knappheit_zeile(self, names):
        """Warnzeile "zu wenig am Hub" aus self._bd_ladder_shorts - oder "".
        Eine Stelle fuer den Tab-Aufbau UND das Nachziehen, sobald die
        Ladder nach dem Tab-Aufbau fertig ist (rebuild-Reihenfolge)."""
        _shorts = getattr(self, "_bd_ladder_shorts", None) or []
        if not _shorts:
            return ""
        _teile = []
        for _sh in _shorts:
            _tid_s = int(_sh.get("type_id") or 0)
            _teile.append("{name} {da} / {soll}".format(
                name=str((names or {}).get(_tid_s) or _tid_s),
                da=f"{int(_sh.get('available') or 0):,}".replace(",", "'"),
                soll=f"{int(_sh.get('needed') or 0):,}".replace(",", "'")))
        return "\u26a0 " + t("Not enough at the hub (order book, available / "
                             "needed): {liste} \u2013 the rest is priced at the "
                             "most expensive order, you may have to buy "
                             "elsewhere or wait.").format(liste=", ".join(_teile))

    def _knappheit_nachziehen(self, names):
        """Die Warnzeile im Materialien-Tab ersetzen/anhaengen, ohne den
        ganzen Tab neu zu bauen (die Ladder ist erst NACH dem Tab-Aufbau
        fertig)."""
        _il = getattr(self, "_bd_mat_tab_info", None)
        if _il is None:
            return
        _marke = "\u26a0 " + t("Not enough at the hub (order book, available / "
                               "needed): {liste} \u2013 the rest is priced at the "
                               "most expensive order, you may have to buy "
                               "elsewhere or wait.")[:24]
        _zeilen = [z for z in (_il.text() or "").split("\n")
                   if z and not z.startswith(_marke)]
        _kz = self._knappheit_zeile(names)
        if _kz:
            _zeilen.append(_kz)
        _il.setText("\n".join(_zeilen))
        _il.setVisible(bool(_zeilen))

    def _fill_material_tab(self, plan, names, tbl, status_lbl=None):
        """Füllt den 'Materialien'-Tab: jedes Rohmaterial, das laut production_plan()
        tatsächlich eingekauft werden muss (plan["buy"]) plus, was schon durch
        Bestand gedeckt ist (plan["stock_used"]) - macht zusammen den GESAMTEN
        Bedarf. Bestand kommt aus self._bd_opts["stock"] - derselben Quelle, die
        "Assets abziehen" oben schon befüllt, kein zweiter ESI-Abruf nötig.
        Genau dasselbe genug/fehlt-Muster wie im Blueprints-Tab."""
        # QTreeWidgetItem wird fuer die Kategorie-Gruppen gebraucht.
        from PySide6.QtWidgets import QTreeWidgetItem
        from PySide6.QtWidgets import QTableWidgetItem
        tbl.setSortingEnabled(False)
        stock = (getattr(self, "_bd_opts", None) or {}).get("stock") or {}
        _virt_tab = getattr(self, "_bd_virt_stock", None) or {}
        # GESAMTBESITZ (Portfolio, ALLE Orte) - nur fuer den Tooltip, EINMAL
        # geholt statt je Zeile. Die Spalte selbst bleibt unveraendert: sie
        # zaehlt weiter nur, was der Plan wirklich verplanen kann.
        try:
            _besitz_gesamt = self._owned_and_selling()[0]
        except Exception:
            _besitz_gesamt = {}
        # Herkunft je Item (s. _resolve_stock_sources). Fehlt sie (sehr alter
        # Zustand / noch kein Abruf), wird die effektive Zahl ehrlich als
        # „ESI" ausgewiesen statt eine Einfügung zu erfinden.
        src_map = getattr(self, "_bd_stock_src", None) or {}
        # SPALTENBESCHRIFTUNG ehrlich halten (Nutzer-Fund): bei EINGEFRORENEN
        # Plänen steht in der "ESI"-Spalte gar nicht der rohe ESI-Wert,
        # sondern max(Einfrier-Stand, live) je Item - der Einfrier-Stand hält
        # verbrauchtes Material bewusst fest. "Besitze (ESI)" wäre dort
        # schlicht falsch. Dieselbe Ehrlichkeits-Regel wie überall sonst:
        # jede angezeigte Zahl muss sagen, woher sie kommt.
        _is_frozen = bool(getattr(self, "_bd_frozen", None))
        _esi_hdr = (t("Owned ( frozen+live)") if _is_frozen
                    else t("Owned (ESI)"))
        if _is_frozen:
            _esi_hdr_tip = t(
                "FROZEN plan: this shows max(frozen state, live stock) \u2013 NOT the "
                "raw ESI value.\nThe frozen state records what you had bought on the "
                "freeze day; anything built since is credited live.\nCan therefore be "
                "higher than your real hangar. Reset: Tools \u2192 \u201eReset frozen "
                "stock\u201c.")
        else:
            _esi_hdr_tip = t(
                "Hangar stock per ESI \u2013 only the locations/characters of the "
                "chosen stock scope.\nWhat ESI does not see, you can paste on the right.")
        _hi = tbl.headerItem()
        if _hi is not None:
            _hi.setText(3, _esi_hdr)
            _hi.setToolTip(3, _esi_hdr_tip)
        _info_lbl = getattr(self, "_bd_mat_tab_info", None)
        if _info_lbl is not None:
            # NUR die Warnung, kein Dauertext mehr - und nur dann sichtbar.
            _zeilen_info = []
            if _is_frozen:
                _zeilen_info.append(
                    "\u26a0 " + t(
                        "FROZEN: the left stock column shows "
                        "max(frozen state, live)."))
            # FEHLBEDARF AUTOMATISCH (Nutzer-Wunsch Sitzung 12: "fuer den
            # Check-Shortfall-Knopf haette ich lieber eine staendige
            # automatische Loesung").
            #
            # WARUM ALS EIGENE ZEILE UND NICHT IN DER EINKAUFSLISTE: der
            # Nutzer will ausdruecklich, dass die Einkaufsliste NICHT wieder
            # waechst ("gekauft ist gekauft"). Ein real verschwundenes
            # Material darf ihn trotzdem nicht am Reaktor ueberraschen -
            # also warnen, ohne die Liste anzufassen.
            try:
                _fehl_auto = self._fehlbedarf_jetzt()
            except Exception:
                _fehl_auto = None          # Anzeige, nie kritisch
            if _fehl_auto:
                # KEIN BANNER MEHR (Nutzer 26.09.2026: "Dieser riesige
                # Informationstext ist unnoetig, den liest sowieso keiner.
                # Was fehlt, sieht man ja unten in der Liste"). Bei einem
                # Capital stand dort eine Liste von 51 Namen ueber der
                # Tabelle. Der Live-Fehlbedarf bleibt - in der ZEILE des
                # Materials (rot, "{fehlt} missing"), s. `_bd_fehl_live`.
                # FUER DIE TABELLE MERKEN: die Zeile des Materials soll den
                # Live-Fehlbedarf selbst tragen, nicht nur der Banner oben.
                self._bd_fehl_live = {int(_t): (int(_f or 0), int(_da or 0))
                                      for _t, _f, _rb, _da, *_ in _fehl_auto}
            else:
                self._bd_fehl_live = {}
            _verl_vor = getattr(self, "_bd_verlust", None) or {}
            if _verl_vor:
                _zeilen_info.append(
                    "\u26a0 " + t(
                        "{n} materials were already covered and are missing "
                        "now \u2013 check „{action}“ in the tools menu."
                    ).format(n=len(_verl_vor),
                             action=t("Buy missing again")))
            # REPROCESSING (1.0.9): hier NUR noch Warnungen. Die Schritte,
            # die Ersparnis und "warum nicht" standen als Textblock ueber der
            # Liste - Nutzer 19.09.2026: "komisch und ueberladen". Jetzt: das
            # Erz ist eine eigene Gruppe in der Liste (Status nennt Ausgang,
            # Ausbeute, Charakter), "warum nicht" steht im Tooltip des
            # Minerals, die Ersparnis in der Reprocessing-Karte.
            _rp = (plan or {}).get("reprocess")
            if _rp is not None:
                if _rp.get("grund") == "sde":
                    _zeilen_info.append(
                        "\u26a0 " + t("Reprocessing: no structure data \u2013 run "
                                      "\u201eLoad recipes\u201c once (Setup)."))
                elif _rp.get("grund") == "fehler":
                    _zeilen_info.append(
                        "\u26a0 " + t("Reprocessing could not be calculated \u2013 "
                                      "see fehler.log."))
            # AUSVERKAUFT / ZU WENIG AM HUB (nach "Neu berechnen", Orderbuch):
            # je Material "da von gebraucht". Ohne Ladder gibt es diese
            # Information nicht - dann steht hier nichts, statt etwas
            # Beruhigendes.
            _kz = self._knappheit_zeile(names)
            if _kz:
                _zeilen_info.append(_kz)
            _info_lbl.setText("\n".join(_zeilen_info))
            _info_lbl.setVisible(bool(_zeilen_info))
        # REST-BEDARF STATT GESAMT-BEDARF (Nutzer-Vorfall Sitzung 12).
        #
        # `buy` ist der Bedarf des GANZEN Plans, als finge man bei null an.
        # Wer die halbe Kette schon gebaut hat, liest dort weiter "noch 78
        # kaufen" - obwohl alles gedeckt ist. Genau das hat den Nutzer fast
        # zu unnoetigen Kaeufen gebracht.
        #
        # Die Zeilen-Mengen bleiben unveraendert (sie sind die Plan-Wahrheit),
        # aber der STATUS wird gegen den Rest-Bedarf gestellt: was fuer die
        # restlichen Runs gedeckt ist, meldet nicht mehr "kaufen".
        # `_fehlbedarf_jetzt` ist dieselbe Rechnung wie der Werkzeuge-Knopf -
        # zwei Wahrheiten waeren hier der schlimmste Ausgang.
        try:
            _rest_fehlt = {int(_r[0]): int(_r[1])
                           for _r in (self._fehlbedarf_jetzt() or [])}
            _rest_bekannt = True
        except Exception:
            _rest_fehlt, _rest_bekannt = {}, False
        # WAS DER RUNPLANER NOCH BAUT (Nutzer 26.09.2026: "ich will, dass
        # diese Runs nicht mehr einfach angezeigt werden, obwohl ich sie gar
        # nicht brauche"). Silicon Diborite stand mit "can be built - 13'019
        # units" da - Plan-Bedarf minus Bestand -, waehrend der Runplaner
        # 0 Runs offen hatte (39 geliefert, 27 laufend). Die Eigenbau-Zeile
        # zeigt jetzt die OFFENEN Runs x Stueck je Run; laufende Jobs
        # zaehlen dabei als gestartet (dieselbe Regel wie `_rest_budget` im
        # Runplaner: geliefert + laufend). Nur Anzeige - die Einkaufsliste
        # rechnet weiter ueber `_restbedarf_jetzt` / `_fehlbedarf_jetzt`.
        _rest_runs = None
        try:
            _rest_runs = self._rest_runs_jetzt()
        except Exception as _rr_e:
            self._log_exception("Materialien: offene Runs", str(_rr_e))
        _out_je_run = {}
        try:
            _rz = getattr(self, "_bd_recipes", None)
            for _t_o in (plan.get("build_runs") or {}):
                _bp_o = _rz.product_to_bp.get(_t_o) if _rz is not None else None
                if _bp_o:
                    _out_je_run[int(_t_o)] = int(_bp_o[2] or 1)
        except Exception:
            _out_je_run = {}
        buy = plan.get("buy") or {}
        stock_used = plan.get("stock_used") or {}
        build_runs = plan.get("build_runs") or {}
        surplus = plan.get("surplus") or {}
        _root = getattr(self, "_bd_type", None)
        excluded_hit = plan.get("excluded_hit") or set()
        never_hit = plan.get("never_build_hit") or set()
        # Items ohne echte Sell-Order am Hub - der Preis ist dort nur eine
        # Schaetzung. Kommt aus dem Plan, wird NICHT hier neu abgeleitet
        # (Arbeitsregel 9: eine Wahrheit, eine Stelle).
        _nicht_kaufbar = plan.get("nicht_kaufbar") or set()
        _recipes = getattr(self, "_bd_recipes", None)
        # Gebauter Netto-Anteil je Item: Runs x Ausstoß - Überschuss. Ohne den
        # log der Tab: bei einem Item, das teils aus Bestand kommt und teils
        # GEBAUT wird, war "Benötigt" = nur der Bestandsanteil -> exakt gleich
        # "Besitze" -> fälschlich "genug ✓", während der Runplaner korrekt den
        # ungedeckten Rest als Reaktions-/Bau-Runs einplante (gemeldeter Bug:
        # "Materialien sagt alles da, Runplaner will trotzdem bauen").
        built_net = {}
        _enden_mat = self._bd_enden(_root, _recipes) if _root is not None else set()
        for tid, runs in build_runs.items():
            if tid in _enden_mat:
                continue          # das Endprodukt selbst ist kein "Material"
            out_qty = 1
            if _recipes is not None:
                bp = _recipes.product_to_bp.get(tid)
                if bp:
                    out_qty = int(bp[2]) or 1
            net = int(runs) * out_qty - int(surplus.get(tid, 0) or 0)
            if net > 0:
                built_net[tid] = net
        try:
            _stage_map = industry.reaction_stage_map(_recipes) if _recipes else {}
        except Exception:
            _stage_map = {}
        _react_products = (getattr(_recipes, "reaction_products", None) or set()) \
            if _recipes else set()
        _CAT_ORDER = ["Intermediate Reactions", "Composite Reactions",
                     # de_scan2: aus  (Kategorie-SCHLUESSEL, Anzeige via _kategorie_anzeige)
                     "Komponenten", "H\u00fcllen", "Fuel", "Tools", "PI",
                     # de_scan2: an
                     t("Datacores and decryptors"),
                     # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                     "Erz", "Mineralien", "Mond-Materialien", "Rohstoffe",
                     # de_scan4: an
                     # Markierung, keine Kategorie: Items, deren SDE-Gruppe
                     # (noch) fehlt. Eigener Kopf ganz unten, damit sie
                     # SICHTBAR bleiben (Arbeitsregel 6) statt faelschlich
                     # unter "Rohstoffe" zu stehen.
                     self.GRUPPE_UNBEKANNT]
        _CAT_RANK = {c: i for i, c in enumerate(_CAT_ORDER)}

        # EIGENE GRUPPEN fuer Fuel und Tools (Nutzer-Wunsch). Bisher landeten
        # Fuel Blocks und R.A.M. unter "Komponenten" - dabei sind es in der
        # Bau-Logik laengst eigene Kategorien (`_category_key` kennt
        # "fuel_blocks" und "tools"). Genau der Klassifizierer wird hier
        # wiederverwendet, statt eine zweite Einteilung zu erfinden.
        _catmap_disp = industry.item_category_map() or {}
        # Gruppen-Namen: derselbe Cache, den auch die Bau-Kategorien nutzen.
        _groups_disp = (getattr(self, "_bd_groups", None)
                        or getattr(self, "_bd_groups_cache", None) or {})

        def _category_for(tid):
            # EINE Wahrheit (Sitzung 20): die Einteilung steht seit dem Umbau
            # als `_bd_material_gruppe` an EINER Stelle - die Gruppen-Blacklist
            # im Bauplan benutzt genau dieselbe. Vorher lag sie nur hier als
            # geschachtelte Funktion; eine zweite Kopie waere ein zweiter
            # Wahrheitsstand gewesen.
            return self._bd_material_gruppe(
                tid, recipes=_recipes, groups=_groups_disp,
                stage_map=_stage_map, react_products=_react_products,
                catmap=_catmap_disp, inv_ids=_inv_ids)

        # INVENTION-MATERIAL (Datacores/Decryptoren): production_plan meldet
        # sie in EIGENEN Schluesseln, weil ihre Kosten bereits in `inv_cost`
        # stecken - sie duerfen nicht in `buy` landen, sonst zaehlt `mat_cost`
        # sie doppelt. Fuer die ANZEIGE sind sie aber ganz normales Material:
        # Bedarf, Bestand, Fehlmenge. Damit stehen sie automatisch auch im
        # Einkaufsfenster, das `self._bd_mat_rows` liest.
        _inv_buy = (plan or {}).get("inv_buy") or {}
        _inv_stock = (plan or {}).get("inv_stock_used") or {}
        _inv_ids = set(_inv_buy) | set(_inv_stock)
        # REPROCESSING (1.0.9, Weg B): Minerale, die das Erz deckt, stehen
        # weder in buy noch in build_runs - ohne diese Zeilen waeren sie aus
        # dem Reiter verschwunden (Nutzer-Befund 18.09.2026).
        _rp_deckt = {}
        # JE ERZ: was es liefert, Ausbeute, Charakter - fuer die Statusspalte
        # der Erz-Zeile (Nutzer 19.09.2026: Textblock ueber der Liste weg).
        _rp_erz_info = {}
        # JE MINERAL: das beste geprueft Erz und sein Aufpreis - Tooltip.
        _rp_warum_nicht = {}
        # ERZ, DESSEN MINERALE SCHON IM BESTAND LIEGEN (28.09.2026): nicht
        # mehr gebraucht, auch ohne Haken in Stufe 0.
        try:
            _rp_erz_bestand = {int(str(_k).split("|")[1])
                               for _k in self._erz_durch_bestand()}
        except Exception:
            _rp_erz_bestand = set()
        _rp_alle = (plan or {}).get("reprocess") or {}
        try:
            _cn_rp = {int(_c["character_id"]): (_c.get("character_name")
                                                or str(_c["character_id"]))
                      for _c in store.list_characters()}
        except Exception:
            _cn_rp = {}
        # GRATIS-ERZ (Blacklist = "bekomme ich"): steht nicht auf der
        # Einkaufsliste, aber der Nutzer muss sehen, WIEVIEL er bekommen
        # muss (Nutzer 19.09.2026: "wo sind denn hier die Compressed Ores?").
        _rp_gratis = {}
        for _st in (_rp_alle.get("schritte") or []):
            for _m, _q in (_st.get("deckt") or {}).items():
                _rp_deckt[int(_m)] = _rp_deckt.get(int(_m), 0) + int(_q or 0)
            if _st.get("art") == "unrefined":
                continue
            if _st.get("gratis"):
                _rp_gratis[int(_st.get("erz") or 0)] = (
                    _rp_gratis.get(int(_st.get("erz") or 0), 0) + int(_st.get("menge") or 0))
            _rp_erz_info[int(_st.get("erz") or 0)] = (
                "\u267b \u2192 " + ", ".join(
                    f"{int(_q):,}".replace(",", "'") + " " + str((names or {}).get(_m) or _m)
                    for _m, _q in sorted((_st.get("deckt") or {}).items()))
                + f"  \u00b7  {float(_st.get('ausbeute') or 0) * 100.0:.1f} %"
                + f"  \u00b7  {_cn_rp.get(_st.get('char'), '?')}")
        for _m, _e in (_rp_alle.get("abgelehnt") or {}).items():
            if _e.get("erz") is None:
                continue
            if _e.get("markt_leer"):
                # MARKT LEER (emm491, Nutzer: "leider lassen die vorhandenen
                # market orders in Jita es nicht zu"): das Erz waere evtl.
                # sogar guenstiger - es liegt nur nicht genug am Hub. Der
                # Grund ist der Markt, nicht der Preis.
                _rp_warum_nicht[int(_m)] = t(
                    "Compressed ore checked: not enough {ore} on sell orders "
                    "at the hub - the rest stays bought as mineral.").format(
                    ore=str((names or {}).get(_e["erz"]) or _e["erz"]))
            elif _e.get("aufpreis_pct") is not None:
                _rp_warum_nicht[int(_m)] = t(
                    "Compressed ore checked: {ore} would be {pct} % more expensive "
                    "than buying the mineral.").format(
                    ore=str((names or {}).get(_e["erz"]) or _e["erz"]),
                    pct=f"{float(_e['aufpreis_pct']):+.0f}")
        all_ids = (set(buy) | set(stock_used) | set(built_net) | _inv_ids | set(_rp_deckt)
                   | set(_rp_gratis))
        rows = []
        # Die ZAHLEN dieser Funktion werden auch vom Einkaufsfenster gebraucht.
        # Sie dort aus den angezeigten Texten zurueckzulesen war ein Fehler:
        # die Tabelle kuerzt ("5.53M", "368.7k"), float() scheitert daran und
        # machte daraus 0 - im Fenster stand ueberall 0 (Nutzer-Screenshot).
        # Deshalb hier die Rohwerte hinterlegen (Arbeitsregel 9/10: dieselbe
        # Quelle, nicht die Anzeige davon).
        self._bd_mat_rows = rows
        # "WAR GEDECKT - JETZT FEHLEN X" (Nutzer-Vorfall Sitzung 12).
        # Der Nutzer hatte recht: wer einmal alles gekauft hat, KANN keinen
        # Fehlbedarf haben. Tritt trotzdem einer auf, ist es ein echter
        # Vorfall (weggeworfen, anderweitig verbaut) - und nur DANN darf die
        # Einkaufsliste ueberhaupt wieder wachsen.
        _verloren = {}
        # SPERRE BEI VERALTETEN JOB-DATEN.
        #
        # Die Verlust-Warnung ist nur so gut wie der Fortschritts-Stand. Weiss
        # die Rechnung nichts von schon gebauten Runs, haelt sie ALLE Runs fuer
        # offen - und meldet verbrauchtes Grundmaterial als "fehlt". Genau der
        # Fall, den der Nutzer beschrieben hat: "wenn ich ein Zwischenkomponent
        # gebaut habe, sind die Grundmaterialien weg, brauche sie aber nicht
        # mehr".
        #
        # Bei frischen Job-Daten stimmt die Rechnung (nachgerechnet: alle Runs
        # geliefert -> Grundmaterial wird NICHT mehr gebraucht, keine Warnung).
        # Sind die Daten alt, wird lieber GESCHWIEGEN als falsch gewarnt: ein
        # Fehlalarm sieht genauso aus wie ein echter Verlust und wuerde den
        # Nutzer zu unnoetigen Kaeufen bringen.
        import time as _t_frisch
        _jobs_ts = float(getattr(self, "_bd_jobs_ts", 0) or 0)
        _jobs_frisch = bool(_jobs_ts) and (_t_frisch.time() - _jobs_ts) < 600
        try:
            from eve_trader.ui.mw_helpers import war_gedeckt_status
            _gd_alt = set(getattr(self, "_bd_covered_once", None) or ())
            _neu_gd, _verl_roh = war_gedeckt_status(
                _rest_fehlt, _gd_alt, list(all_ids))
            if _rest_bekannt:
                self._bd_covered_once = _gd_alt | _neu_gd
            # ZWEI HUERDEN, gegen zwei verschiedene Fehlalarme:
            #  1) JOB-DATEN FRISCH? Sonst haelt die Rechnung schon gebaute
            #     Runs fuer offen und meldet VERBRAUCHTES Material als weg.
            #  2) BESTEHT DER FEHLBETRAG LANGE GENUG? CCP cacht Assets bis
            #     zu einer Stunde - frisch gekauftes Material ist in ESI noch
            #     nicht sichtbar und saehe sonst aus wie ein Verlust.
            #     Ein Fehlalarm direkt nach dem Einkauf wuerde zum
            #     Doppelkauf verleiten - genau das, was der Nutzer nicht will.
            from eve_trader.ui.mw_helpers import verlust_stabil
            _verl_stab, _seit_neu = verlust_stabil(
                _verl_roh if _jobs_frisch else {},
                getattr(self, "_bd_verlust_seit", None) or {},
                _t_frisch.time())
            self._bd_verlust_seit = _seit_neu
            _verloren = _verl_stab
        except Exception:
            _verloren = {}          # Anzeige, nie kritisch
        # Fuer den Nachkauf-Knopf merken: NUR echte Verluste, nie der
        # gewoehnliche Rest-Bedarf. Sonst waere der Knopf ein Weg, die
        # Einkaufsliste doch wieder wachsen zu lassen - genau das, was der
        # Nutzer nicht will.
        self._bd_verlust = dict(_verloren)
        # DATACORES/DECRYPTOREN, DIE GESTARTETE INVENTION-JOBS SCHON
        # VERBRAUCHT HABEN (emm431, ESI statt Haken): sie fallen aus Bedarf
        # und Einkaufsliste - so wie gebaute Runs beim Fertigungsmaterial.
        try:
            _inv_esi = self._inv_verbraucht_esi() if _inv_ids else {}
        except Exception as _ie:
            self._log_exception("Invention: ESI-Verbrauch", str(_ie))
            _inv_esi = {}
        for tid in all_ids:
            missing = (buy.get(tid, 0) or 0) + (_inv_buy.get(tid, 0) or 0)
            used = (stock_used.get(tid, 0) or 0) + (_inv_stock.get(tid, 0) or 0)
            built = built_net.get(tid, 0) or 0
            reprocessed = _rp_deckt.get(tid, 0) or 0
            gratis_q = _rp_gratis.get(tid, 0) or 0
            total = missing + used + built + reprocessed + gratis_q
            _inv_vb = 0
            if tid in _inv_ids and _inv_esi.get(tid):
                _inv_vb = min(int(_inv_esi[tid]), int(total))
                total -= _inv_vb
                missing = min(int(missing), int(total))
            if total <= 0 and not _inv_vb:
                continue
            has_recipe = False
            if _recipes is not None:
                has_recipe = (tid in _recipes.product_to_bp
                             or tid in (getattr(_recipes, "reaction_products", None) or ()))
            reason = None
            # GRUND-KENNUNG statt Emoji-Praefix (Sitzung 16): frueher stand
            # vor dem Text ein Zeichen (\U0001F6AB / \U0001F527), an dem die
            # Faerbung weiter unten haengt. Mit dem Emoji-Umbau fiel es weg
            # und die Faerbung griff ins Leere. Die Kennung ist unsichtbar
            # und uebersteht jede Uebersetzung.
            grund_art = None
            if tid in excluded_hit:
                grund_art = "blacklist"
                reason = t("On the blacklist (\u201ealready have it\u201c, recipe "
                           "structure tab) - therefore NEVER built, not even with "
                           "\u201eBuild everything yourself: ON\u201c. Untick it there to make "
                           "it buildable again.")
            elif tid in never_hit:
                grund_art = "kein_bp"
                reason = t("Blueprint category in \u201eMy blueprints\u201c (recipe "
                           "structure tab) not marked as owned - the tool assumes you do "
                           "not have the blueprint/reaction formula and therefore buys, "
                           "even with \u201eBuild everything yourself: ON\u201c (cannot build "
                           "what you do not own). If you really have it: tick the matching "
                           "category there.")
            elif not has_recipe:
                reason = t("No recipe of its own in the SDE (real raw material/commodity) "
                           "- cannot be built, MUST be bought.")
                if tid in _nicht_kaufbar:
                    # SCHLIMMSTER FALL: nicht kaufbar UND nicht baubar. Das
                    # muss der Nutzer VOR dem Einkauf sehen, nicht vor dem
                    # leeren Marktfenster.
                    reason += t("\n\u26d4 AND there is no sell order for it at the chosen "
                                "hub. The price above is an estimate (ESI average), not an "
                                "offer - you will not be able to buy it there.")
            elif tid in _nicht_kaufbar:
                # AM HUB NICHT KAUFBAR (Nutzer, Sitzung 14: "aber mit vermerk
                # dazu in Rezeptstruktur sollte etwas stehen"). Ohne den
                # Vermerk staende hier ploetzlich BAUEN, ohne erkennbaren
                # Grund - und beim naechsten Scan, wenn wieder Orders da
                # sind, waere es stillschweigend wieder KAUFEN.
                reason = t("There is NO sell order for this item at the chosen "
                           "hub. The plan therefore builds it itself instead of planning a "
                           "purchase you could not make.\nThe price in the cost is an "
                           "estimate (ESI average), not an offer. As soon as someone sells "
                           "at the hub again, the normal cost comparison decides.")
            _si = src_map.get(tid) or {}
            _used_q = stock.get(tid, 0) or 0
            rows.append({"tid": tid, "name": names.get(tid, f"#{tid}"),
                        "total": total, "owned": _used_q,
                        "missing": missing, "built": built, "reason": reason,
                        "reprocessed": reprocessed,
                        "gratis": gratis_q,
                        "grund_art": grund_art,
                        "category": _category_for(tid),
                        # Herkunfts-Bausteine: ohne src_map fällt alles auf
                        # „ESI" zurück (kein erfundener Einfüge-Wert).
                        "src": _si.get("src", "esi"),
                        "q_esi": int(_si.get("esi", _used_q) or 0),
                        "q_manual": _si.get("manual"),
                        "q_job": int(_si.get("job", 0) or 0),
                        "inv_esi": int(_inv_vb)})
        rows.sort(key=lambda r: (_CAT_RANK.get(r["category"], 99),
                                 -r["missing"], r["name"]))
        # Daten fuer die Deckungs-Balken; angehaengt wird erst nach
        # setSortingEnabled(), weil das Sortieren Zell-Widgets verwirft.
        _bar_data = {}
        # GRUPPEN nach Kategorie, in der Reihenfolge der Produktionskette.
        tbl.clear()
        tbl.setHeaderLabels([t("Material"), t("Category"), t("Required"),
                             t("Owned"), t("Pasted"), t("Missing"),
                             t("Status")])
        _groups, _gstat = {}, {}
        # WAS STECKT SCHON IN LAUFENDEN JOBS? (Nutzer 25.09.2026, Silicon
        # Diborite.) Reine Auskunft - die Rechnung bleibt unberuehrt
        # (Nutzer-Entscheid: "koennen wir 2 und 3 kombinieren?", also
        # anzeigen statt umrechnen). Quelle ist dieselbe wie beim Runplaner
        # (`_bd_active_jobs_map`), damit nicht zwei Stellen verschieden
        # zaehlen.
        try:
            from .mw_helpers import laufend_verbraucht as _mwh_lv
            _lauf_runs = {}
            for _t_l, _js_l in ((getattr(self, "_bd_active_jobs_map", None)
                                 or {}).items()):
                _n_l = sum(int(_j.get("runs") or 0) for _j in (_js_l or []))
                if _n_l > 0:
                    _lauf_runs[int(_t_l)] = _n_l
            _lauf_verbr = _mwh_lv(plan.get("build_runs") or {},
                                  plan.get("build_mats") or {}, _lauf_runs)
            # GESPEICHERTER PLAN (emm422): seine zugeordneten laufenden Jobs
            # zaehlen in der Rechnung schon als erledigt - der Satz "der Plan
            # zaehlt den Bedarf weiter, hake ab" waere dort falsch.
            if getattr(self, "_bd_open_plan_id", None):
                _lauf_verbr = {}
        except Exception as _lv_e:
            _lauf_verbr = {}
            self._log_exception("Materialien: laufend verbraucht", str(_lv_e))
        # ESI HINKT HINTERHER (emm424, Nutzer: "die Warnung finde ich gut"):
        # Jobs, die NACH dem ESI-Bestandsstand gestartet wurden, haben ihr
        # Material im Spiel schon verbraucht, der Bestand hier zeigt es noch.
        # Nur Auskunft an der Zeile, keine Zahl aendert sich.
        try:
            from .mw_helpers import lag_verbrauch as _mwh_lag
            _rec_l = getattr(self, "_bd_recipes", None)

            def _mats_l(pid, act):
                if _rec_l is None or act not in (1, 9, 11):
                    return None
                _bp_l = (getattr(_rec_l, "product_to_bp", None) or {}).get(int(pid))
                if not _bp_l:
                    return None
                return (getattr(_rec_l, "bp_materials", None) or {}).get(
                    (_bp_l[0], _bp_l[1]))
            _lag_verbr = _mwh_lag(getattr(self, "_bd_active_jobs_alle", None) or {},
                                  getattr(self, "_bd_esi_stock_ts", None), _mats_l)
        except Exception as _lg_e:
            _lag_verbr = {}
            self._log_exception("Materialien: ESI-Verzug", str(_lg_e))

        def _baubereit(tid):
            """True, wenn die Zutaten fuer die geplanten Runs dieses Items
            JETZT im Bestand liegen - dann kann der Job sofort starten.

            Nutzer-Wunsch (Sitzung 8): "wenn wir genuegend Materialien haben
            um die fehlenden Komponenten zu bauen, soll 'kann gebaut werden'
            stehen und gruen sein" - und auf Nachfrage: "es soll GENAU
            passen, ich will so guenstig wie moeglich bauen". Deshalb wird
            gegen `plan["build_mats"]` geprueft - die EXAKTEN Mengen (inkl.
            ME, je Job gerundet), mit denen der Plan selbst rechnet. EINE
            Quelle (Arbeitsregel 9), nichts nachgebaut, nichts doppelt.
            Grenze der Zusage: haengt eine Zutat SELBST am Bau (Ferrogel
            wartet auf Ferrofluid), ist das Item NICHT startbereit - gruen
            darf nichts versprechen, was erst nach einem anderen Job stimmt
            (genau die Kette des Ferrofluid-Vorfalls)."""
            mats = (plan.get("build_mats") or {}).get(tid)
            if not mats:
                return False
            # NUTZER-VORFALL (Sitzung 8, 805 Ferrogel): der Gesamtbestand
            # enthaelt den PIPELINE-Anteil (laufende/fertige, noch nicht
            # abgelieferte Jobs) - fuer die Einkaufsliste richtig ("ein
            # laufender Run ist ein Run"), fuer die SOFORT-Start-Zusage
            # falsch: der Reaktor-Inhalt liegt nicht im Hangar. Ingame stand
            # 830/1'635, das Tool sagte "genug". Die Zusage rechnet deshalb
            # NUR mit dem, was wirklich im Lager liegt.
            _virt = getattr(self, "_bd_virt_stock", None) or {}
            for m, jq in mats:
                if build_runs.get(m):
                    return False          # Zutat haengt selbst am Bau
                _lager = (int(stock.get(m, 0) or 0)
                          - int(_virt.get(m, 0) or 0))
                if _lager < jq:
                    return False
            return True

        for _c in _CAT_ORDER:
            if not any(r["category"] == _c for r in rows):
                continue
            _g = QTreeWidgetItem(tbl, [self._kategorie_anzeige(_c),
                                       self._kategorie_anzeige(_c), "", "", "", "", ""])
            # SCHLUESSEL AM KNOTEN: der Fortschrittsbalken schlug die Gruppe
            # ueber text(0) nach - seit die Anzeige uebersetzt ist, ist das
            # nicht mehr der Schluessel. Der Schluessel haengt als Daten dran.
            _g.setData(1, Qt.UserRole, _c)
            _gf = _g.font(0); _gf.setBold(True); _g.setFont(0, _gf)
            _g.setForeground(0, QColor(theme.CYAN))
            _groups[_c] = _g
            _gstat[_c] = [0, 0, 0.0, 0.0, 0]   # gedeckt, gesamt, ist, soll, im Bau
        n_missing = 0
        n_built = 0
        for i, r in enumerate(rows):
            owned = r["owned"]
            built = r.get("built", 0)
            # NOCH ZU BAUEN statt URSPRUENGLICH GEPLANT (Sitzung 13).
            # `built` stammt aus plan["build_runs"] und ist bei EINGEFRORENEN
            # Plaenen der Stand vom Einfrier-Tag. `owned` ist live. Der Reiter
            # zeigte deshalb "Rest wird gebaut 7'321", waehrend zwei Spalten
            # weiter links 3'700 besessen und 3'661 fehlend standen - zwei
            # Zahlen fuer dieselbe Sache auf EINEM Bildschirm (Nutzer-Fund
            # mit Screenshot). Gerechnet wird jetzt aus DENSELBEN Zahlen wie
            # die MISSING-Spalte, damit die Zeile in sich stimmt.
            _noch_bauen = max(0, int(r["total"]) - int(owned))
            # OFFENE RUNS statt Plan-minus-Bestand (s. `_rest_runs` oben):
            # geliefert und laufend sind abgezogen, gedeckelt auf den Plan.
            _offen_runs = None
            _lauf_runs = 0
            if _rest_runs is not None and int(r["tid"]) in _rest_runs:
                _lauf_runs = sum(
                    int(_j.get("runs") or 0) for _j in
                    ((getattr(self, "_bd_active_jobs_map", None) or {})
                     .get(int(r["tid"])) or []))
                _offen_runs = max(0, int(_rest_runs[int(r["tid"])]) - _lauf_runs)
                _noch_bauen = _offen_runs * int(_out_je_run.get(int(r["tid"]), 1))
            if not stock:
                status_txt, status_col = t("Subtract assets needed"), theme.MUTED
            elif (r.get("gratis", 0) or 0) > 0:
                # ERZ AUF DER BLACKLIST: wird gestellt, nicht gekauft - die
                # Zeile zeigt die Menge, zaehlt aber nirgends als fehlend.
                status_txt = t("on blacklist \u2013 provided, not bought")
                status_col = theme.VIOLET
            elif (r.get("reprocessed", 0) or 0) > 0 and r["missing"] <= 0 and built <= 0:
                # GEDECKT DURCH REPROCESSING (1.0.9, Weg B): nicht "genug" -
                # im Hangar liegt noch nichts, das Erz muss erst durch die
                # Anlage. Die Zeile sagt, woher es kommt.
                status_txt = t("from reprocessing \u267b \u00b7 {n} units").format(
                    n=f"{int(r['reprocessed']):,}".replace(",", "'"))
                status_col = theme.GREEN_BRIGHT
                r["reason"] = t("Covered by reprocessing compressed ore (run planner, "
                                "stage 0) \u2013 nothing to buy. Once the ore is "
                                "reprocessed and ticked there, the minerals must lie "
                                "in stock.")
            elif r["missing"] <= 0 and built <= 0:
                _virt_n = int(_virt_tab.get(r["tid"], 0) or 0)
                if _virt_n > 0:
                    # NUTZER-VORFALL (805 Ferrogel): "genug" stimmte nur
                    # inklusive Pipeline - im Hangar lagen 830 von 1'635.
                    # Ehrlich trennen: gedeckt ja, aber X davon stecken noch
                    # in laufenden/fertigen Jobs und liegen erst nach der
                    # ABLIEFERUNG im Hangar. Ausserdem landet der Output der
                    # Reaktionen in der REAKTIONS-Struktur - ggf. umziehen.
                    status_txt = t("enough \u2713 \u00b7 {n} of them in build").format(
                        n=f"{min(_virt_n, int(owned)):,}".replace(",", "'"))
                    status_col = theme.CYAN
                    r["reason"] = t("Covered \u2013 but {n} units are still in running/"
                                    "finished jobs (pipeline) and only land in the hangar "
                                    "after delivery. For the SHOPPING LIST that rightly "
                                    "counts (nothing to rebuy!); for the JOB START it has "
                                    "to be delivered first and possibly moved to the build "
                                    "structure.").format(
                        n=f"{min(_virt_n, int(owned)):,}".replace(",", "'"))
                else:
                    status_txt = t("enough \u2713")
                status_col = status_col if _virt_n > 0 else theme.GREEN
                if _virt_n <= 0:
                    status_txt, status_col = t("enough \u2713"), theme.GREEN
            elif r["missing"] <= 0:
                # nichts zu KAUFEN - aber der Rest über dem Bestand wird laut
                # Plan selbst GEBAUT (Runplaner). Vorher stand hier fälschlich
                # "genug ✓", weil der gebaute Anteil in "Benötigt" fehlte.
                # NUTZER-FUND: "Rest wird gebaut" klang so, als h\u00e4tte man
                # schon Bestand - bei owned=0 wird aber die GANZE Menge
                # gebaut, da ist kein "Rest".
                _runs_hint = ""
                if _offen_runs is not None:
                    _runs_hint = " \u00b7 " + t("{r} of {n} runs open").format(
                        r=_offen_runs,
                        n=int((plan.get("build_runs") or {}).get(int(r["tid"]), 0) or 0))
                    if _lauf_runs > 0:
                        _runs_hint += " \u00b7 " + t("{n} running").format(n=_lauf_runs)
                if _offen_runs == 0 and int(r["tid"]) in (
                        getattr(self, "_bd_vorstufen_fertig", None) or set()):
                    # NICHT MEHR GEBRAUCHT (28.09.2026): alle Verbraucher im
                    # Plan sind erledigt - die restlichen Runs braucht niemand.
                    status_txt = t("not needed any more \u2713")
                    status_col = theme.GREEN
                    r["reason"] = t("Everything in this plan that uses this item is "
                                    "already built or running - the remaining runs "
                                    "are not needed. Nothing to buy, nothing to start.")
                elif _offen_runs == 0:
                    # NICHTS MEHR ZU BAUEN: alle Runs geliefert oder gestartet.
                    # Vorher stand hier "can be built - 13'019 units" (Nutzer
                    # 26.09.2026) - eine Zahl, die vom Bauen nichts wusste.
                    status_txt = t("nothing left to build \u2713") + _runs_hint
                    status_col = theme.GREEN
                    r["reason"] = t("Every planned run of this item is delivered or "
                                    "running according to ESI (or ticked in the run "
                                    "planner). Nothing to buy, nothing to start.")
                elif _baubereit(r["tid"]):
                    # Zutaten liegen KOMPLETT im Bestand -> Job kann sofort
                    # starten. Helleres Gruen als "genug" (das hier ist eine
                    # Handlungs-Zusage, kein blosser Deckungs-Status).
                    status_txt = t("can be built \u2713 \u00b7 {n} units").format(
                        n=f"{int(_noch_bauen):,}".replace(",", "'")) + _runs_hint
                    status_col = theme.GREEN_BRIGHT
                    r["reason"] = t("All ingredients for the planned runs are in stock "
                                    "NOW \u2013 the build job can be started right away "
                                    "(see run planner). Nothing to buy.")
                elif owned > 0:
                    status_txt = t("still to build \u00b7 {n} units").format(
                        n=f"{int(_noch_bauen):,}".replace(",", "'")) + _runs_hint
                    status_col = theme.BLUE
                    r["reason"] = t("Stock covers part of it, the rest is BUILT per plan "
                                    "(see run planner) \u2013 nothing to buy here.")
                else:
                    status_txt = t("will be built \u00b7 {n} units").format(
                        n=f"{int(_noch_bauen):,}".replace(",", "'")) + _runs_hint
                    status_col = theme.BLUE
                    r["reason"] = t("Built entirely per plan (see run planner) \u2013 "
                                    "nothing to buy, no stock needed.")
                n_built += 1
            elif _rest_bekannt and int(r["tid"]) not in _rest_fehlt:
                # FUER DIE RESTLICHEN RUNS GEDECKT. Der Gesamt-Bedarf oben
                # sagt zwar noch "es fehlt etwas", aber das bezieht sich auf
                # Runs, die laengst gebaut oder in der Bauschleife sind.
                # Hier steht deshalb, was WIRKLICH gilt - sonst kauft der
                # Nutzer nach, was er nicht braucht.
                status_txt = t("covered for the remaining runs \u2713")
                status_col = theme.GREEN
            elif int(r["tid"]) in _verloren:
                # WAR SCHON EINMAL GEDECKT und fehlt jetzt. Das ist eine
                # andere Aussage als "noch nicht gekauft": hier ist wirklich
                # etwas passiert (weggeworfen, anderweitig verbaut). Der
                # Nutzer soll das SEHEN und nicht mit einem gewoehnlichen
                # Kauf-Posten verwechseln - nur an dieser Stelle darf die
                # Einkaufsliste ueberhaupt wieder wachsen, und auch dann nur
                # auf seinen Klick ("gekauft ist gekauft").
                status_txt = t("was covered \u2013 {n} missing now").format(
                    n=f"{int(_verloren[int(r['tid'])]):,}".replace(",", "'"))
                status_col = theme.RED
                n_missing += 1
            elif owned > 0:
                # teilweise vorhanden - ein Teil ist "gratis" (Bestand), der Rest
                # muss noch dazugekauft werden. Eigene Farbe (Orange), damit klar
                # ist: nicht bei NULL, nur eben nicht ganz genug.
                status_txt = t("partly \u2013 {n} still to buy").format(
                    n=f"{int(_rest_fehlt.get(int(r['tid']), r['missing'])):,}"
                      .replace(",", "'"))
                status_col = theme.AMBER
                n_missing += 1
            else:
                # komplett nichts davon vorhanden (oder außerhalb der verknüpften
                # Bau-/Reaktions-Struktur bzw. -Charaktere, siehe Info-Text oben).
                status_txt = t("missing completely \u2013 buy {n}").format(
                    n=f"{int(r['missing']):,}".replace(",", "'"))
                status_col = theme.RED
                n_missing += 1
            # WARUM ES "FEHLT", OBWOHL NICHTS FEHLT (Nutzer 25.09.2026):
            # steckt ein Teil davon in JETZT laufenden Jobs, ist es im Spiel
            # schon verbraucht - der Plan zaehlt seinen Bedarf aber weiter
            # mit, weil das Erzeugnis noch nicht da ist. Nur eine Auskunft,
            # die Zahlen bleiben unveraendert.
            _lv_n = int(_lauf_verbr.get(int(r["tid"]), 0) or 0)
            if _lv_n > 0 and (int(r["missing"]) > 0 or int(built or 0) > 0):
                status_txt += " · " + t("{n} in running jobs").format(
                    n=f"{_lv_n:,}".replace(",", "'"))
                r["reason"] = ((r.get("reason") or "") + "\n\n" + t(
                    "{n} units of this are already used up by jobs that are "
                    "RUNNING right now – in game the material is gone, "
                    "but their output is not in the hangar yet, so the plan "
                    "keeps counting the need. Nothing is really missing "
                    "here. The number stays as it is on purpose (better to "
                    "buy too much than too little); tick the running rows in "
                    "the run planner to take their material out of the "
                    "list.").format(n=f"{_lv_n:,}".replace(",", "'"))).strip()
            # ESI-VERZUG (emm424): nur wo Bestand gezeigt wird - genau dort
            # taeuscht ein "covered", wenn ein frischer Job es schon frass.
            _lag_n = int(_lag_verbr.get(int(r["tid"]), 0) or 0)
            if _lag_n > 0 and owned > 0:
                _lag_txt = f"{min(_lag_n, int(owned)):,}".replace(",", "'")
                status_txt += " · \u26a0 " + t(
                    "up to {n} used since the stock check").format(n=_lag_txt)
                status_col = theme.AMBER
                r["reason"] = ((r.get("reason") or "") + "\n\n" + t(
                    "ESI reports your hangar only about once an hour. Jobs "
                    "started after the last stock check have already used up "
                    "to {n} of this in game - the stock shown here may not be "
                    "there any more. Nothing is recalculated; check in game "
                    "before you rely on it.").format(n=_lag_txt)).strip()
            if int(r.get("inv_esi") or 0) > 0:
                _ie_txt = f"{int(r['inv_esi']):,}".replace(",", "'")
                status_txt += " · " + t("{n} used by started invention jobs").format(
                    n=_ie_txt)
                r["reason"] = ((r.get("reason") or "") + "\n\n" + t(
                    "ESI shows invention jobs of this plan started after it was "
                    "frozen - they have already used {n} of this. It no longer "
                    "counts as needed and is not on the shopping list.").format(
                        n=_ie_txt)).strip()
            if r.get("grund_art") == "blacklist":
                # Blacklist ist der einzige Grund, den "Alles selbst bauen" NICHT
                # überstimmen kann - eigene, klar sichtbare Farbe statt normalem Rot.
                status_txt = t("on blacklist \u2013 never built")
                status_col = theme.VIOLET
            elif r.get("grund_art") == "kein_bp":
                # "Meine Blueprints"-Kategorie nicht als besessen markiert - auch
                # das überstimmt "Alles selbst bauen" nicht (kann ja nicht ohne
                # eigene Blaupause bauen). Eigene Farbe (Cyan), damit man's von
                # Blacklist UND von "wirklich kein Rezept" unterscheiden kann.
                status_txt = t("Blueprint not marked as owned")
                status_col = theme.CYAN
            # ---- Herkunft getrennt ausweisen (Nutzer-Kernwunsch) -----------
            # Bisher stand hier EINE Spalte „Besitze", in der der eingefügte
            # Wert den ESI-Wert still überschrieb. Jetzt: beide Quellen als
            # eigene Spalten, die tatsächlich benutzte fett/farbig, die
            # abgelöste gedämpft - und „Genutzt" als die Zahl, mit der der
            # Plan rechnet (inkl. Pipeline aus laufenden/fertigen Jobs).
            _is_manual = (r.get("src") == "manuell")
            _q_esi, _q_man, _q_job = r["q_esi"], r.get("q_manual"), r["q_job"]
            if not stock:
                esi_txt, man_txt = "\u23f3 \u2026", "\u23f3 \u2026"
            else:
                esi_txt = f"{int(_q_esi):,}".replace(",", "'")
                man_txt = ("\u2013" if _q_man is None
                           else f"{int(_q_man):,}".replace(",", "'"))
            _dim, _act = QColor(theme.MUTED), QColor(theme.CYAN)
            esi_col = _dim if (_is_manual or not _q_esi) else QColor(theme.TEXT)
            man_col = _act if _is_manual else _dim
            _job_hint = ""
            if _q_job:
                _job_hint = (
                    "\n\u2795 " + t("{n} units from running/finished jobs (pipeline) - "
                                     "they ALWAYS count, whichever source wins (job "
                                     "output is in no hangar).").format(
                        n=f"{int(_q_job):,}".replace(",", "'")))
            esi_tip = ((t("Frozen state, merged with the live stock (max per item).")
                        if _is_frozen else
                        t("Hangar stock per ESI in the chosen scope."))
                       + (t("\nCurrently NOT used \u2013 the pasted stock is newer.")
                          if _is_manual else t("\nThis source counts right now."))
                       + _job_hint)
            man_tip = (t("Pasted quantity (panel on the right).")
                       if _q_man is not None else
                       t("Nothing was pasted for this item."))
            if _q_man is not None:
                man_tip += (t("\nThis source counts right now.") if _is_manual else
                            t("\nSuperseded \u2013 the ESI data is fresher. Can be "
                              "forced with \u201ePermanent\u201c."))
            man_tip += _job_hint
            _src_word = (t("pasted") if _is_manual
                         else (t("frozen+live") if _is_frozen else "ESI"))
            _src_qty = int(_q_man or 0) if _is_manual else int(_q_esi)
            used_tip = (t("The plan calculates with this.\nSource: ") + _src_word
                        + " (" + f"{_src_qty:,}".replace(",", "'") + ")"
                        + _job_hint)
            # FEHLT statt GENUTZT (Nutzer: "ich will wissen, wie viele
            # Materialien mir fehlen"). "Genutzt" wiederholte im Wesentlichen
            # den Bestand; die offene Menge musste man sich aus Benoetigt
            # minus Bestand selbst ausrechnen.
            _missing_q = max(0, int(r["total"]) - int(_src_qty))
            if (r.get("gratis", 0) or 0) > 0:
                _missing_q = 0          # wird gestellt - fehlt nicht
            # EIGENBAU MIT BEKANNTEN OFFENEN RUNS: die Spalte zeigt, was der
            # Runplaner noch baut - nicht Plan minus Bestand (Nutzer
            # 26.09.2026). Der Tooltip nennt die Herkunft.
            _bau_hint = ""
            if (_offen_runs is not None and r["missing"] <= 0
                    and int(built or 0) > 0):
                _missing_q = int(_noch_bauen)
                _bau_hint = "\n" + t("Still to build for the open runs: {n} "
                                     "({r} runs open, delivered and running "
                                     "runs deducted).").format(
                    n=f"{int(_noch_bauen):,}".replace(",", "'"), r=_offen_runs)
            # FEHLT HEISST FEHLT (27.09.2026, s. mw_helpers.fehlt_spalte): die
            # Spalte zeigt mindestens, was fuer DIESEN Plan wirklich fehlt -
            # auch wenn der Hangar voll ist, weil andere Plaene reserviert haben.
            from eve_trader.ui.mw_helpers import fehlt_spalte
            _fl_sp = (getattr(self, "_bd_fehl_live", None) or {}).get(int(r["tid"]))
            _missing_q, _miss_live = fehlt_spalte(
                _missing_q, (_fl_sp[0] if _fl_sp else 0))
            miss_txt = ("\u2013" if _missing_q <= 0
                        else f"{_missing_q:,}".replace(",", "'"))
            if int(r["tid"]) in _rp_erz_bestand:
                # Nutzer 28.09.2026: "ich habe das compressed Ore zu
                # Mineralien verarbeitet" - die Minerale liegen da, das Erz
                # braucht der Plan nicht mehr (reprocess.schritte_durch_bestand).
                _missing_q, _miss_live, miss_txt = 0, False, "\u2013"
                status_txt = t("not needed \u2013 its minerals are already in stock \u2713")
                status_col = theme.GREEN
                r["reason"] = t("Every mineral this ore was planned for is already "
                                "in stock for this plan (reprocessed or bought). "
                                "The ore is no longer needed and not on the "
                                "shopping list.")
            # DIE FARBE FOLGT DER AUSSAGE (Sitzung 17, Nutzer: "es sieht auf
            # den ersten Blick so aus, als haette ich nicht alles - dabei
            # habe ich es, weil ich es noch bauen werde"). Die Spalte rechnet
            # stur Benoetigt minus Bestand; was der Plan SELBST baut, stand
            # deshalb bernsteinfarben da, obwohl nichts zu kaufen ist.
            # GEDECKT = gruen, egal ob aus dem Bestand oder aus Eigenbau.
            # Bernstein/Rot bleibt dem vorbehalten, was wirklich fehlt.
            _gedeckt = status_col in (theme.GREEN, theme.GREEN_BRIGHT, theme.BLUE)
            if _missing_q <= 0:
                miss_col = theme.MUTED
            elif _gedeckt and not _miss_live:
                miss_col = theme.GREEN
            else:
                miss_col = theme.AMBER
            used_tip = (t("What still has to be procured after deducting your stock "
                          "(buy or build).\n")
                        + t("Required ") + f"{int(r['total']):,}".replace(",", "'")
                        + " \u2212 " + _src_word + " "
                        + f"{_src_qty:,}".replace(",", "'")
                        + " = " + f"{_missing_q:,}".replace(",", "'")
                        + _job_hint + _bau_hint)
            # GROSSE ZAHLEN KUERZEN (Nutzer): 21'957'687 -> 21.96M. Der
            # exakte Wert steht im Tooltip der jeweiligen Zelle, es geht also
            # keine Information verloren.
            _exact = {}

            def _sq(_v, _col):
                _exact[_col] = f"{int(_v):,}".replace(",", "'")
                return self._short_qty(_v)
            # LIVE-FEHLBEDARF IN DER ZEILE SELBST (Sitzung 16).
            # Der eingefrorene Bestand zeigt max(eingefroren, live) - das ist
            # richtig fuer den EIGENEN Verbrauch (die Einkaufsliste darf nicht
            # wieder aufreissen). Aber jeder Schwund DANACH versteckt sich
            # dahinter, egal woher er kommt: anderer Plan, anderer Charakter,
            # in einen Contract gelegt. Der Anlassfall war Letzteres - die
            # Zeile sagte "noch zu bauen 4'730", waehrend im Hangar 96 lagen,
            # und der Nutzer suchte stundenlang. Deshalb traegt die Zeile den
            # LIVE-Stand mit, wenn er den Bedarf nicht deckt - rot, nicht zu
            # ueberlesen.
            _fl = (getattr(self, "_bd_fehl_live", None) or {}).get(int(r["tid"]))
            if _fl and _fl[0] > 0:
                # DIE ZAHL HIESS "LIVE" UND WAR ES NICHT (Nutzer-Befund
                # 25.09.2026): sie kommt aus `_bd_opts["stock"]`, und das ist
                # bei einem eingefrorenen Plan max(eingefroren, live). Bei ihm
                # stand deshalb "LIVE: only 9'913 on hand", waehrend im Hangar
                # 198 lagen - er hat gesucht. Genau die Fehlerklasse aus
                # Sitzung 9: eine Zahl traegt einen Namen, der etwas anderes
                # meint. Die Rechnung bleibt (max ist gewollt, sonst reisst
                # die Einkaufsliste fuer laengst gekauftes Material wieder
                # auf) - nur der Name wird ehrlich, und der ECHTE Hangar-Stand
                # steht daneben, wenn er abweicht.
                _echt = int((getattr(self, "_bd_live_stock", None) or {})
                            .get(int(r["tid"]), _fl[1]) or 0)
                status_txt = (t("\u26a0 counted {da} \u2013 {fehlt} missing "
                                "for the remaining runs").format(
                    da=f"{_fl[1]:,}".replace(",", "'"),
                    fehlt=f"{_fl[0]:,}".replace(",", "'"))
                              + ("" if _echt >= int(_fl[1]) else
                                 "  \u00b7  " + t("really in the hangar: {n}")
                                 .format(n=f"{_echt:,}".replace(",", "'")))
                              + "  \u00b7  " + status_txt)
                status_col = theme.RED
            # WIEVIEL DAVON IST SCHON VERGEBEN? (Nutzer, Sitzung 19)
            # In der Spalte OWNED stand der ROHE Bestand, in der roten
            # LIVE-Zeile daneben der Bestand NACH Abzug der Reservierungen
            # anderer Plaene - "1'266 vorhanden" und "only 0 on hand"
            # nebeneinander. Beide Zahlen stimmen, der Widerspruch war nur
            # nicht erklaert. Reine Anzeige: an der Deckungslogik und an der
            # Einkaufsliste aendert sich NICHTS (dort gilt weiter "gekauft
            # ist gekauft"; verbaute Grundmaterialien duerfen nicht wieder
            # auf die Liste).
            _res_row = int((getattr(self, "_bd_reserved_applied", None)
                            or {}).get(int(r["tid"]), 0) or 0)
            _esi_zelle = (_sq(int(_q_esi), 3)
                          if esi_txt not in ("\u2013", "?") else esi_txt)
            if _res_row > 0 and 3 in _exact:
                # IN DEN TOOLTIP, NICHT IN DIE ZELLE (Nutzer, Sitzung 19).
                # Erst stand " (53.1k reserved)" in der Spalte - die ist zu
                # schmal, es wurde zu "53.1k (53.1k r...". Ein Emoji als
                # Kuerzel verbietet aa285 zu Recht. Der Tooltip traegt die
                # Zahl ungekuerzt, die Spalte bleibt lesbar.
                _exact[3] = _exact[3] + t(", of which {n} reserved by other "
                                          "build plans").format(
                    n=f"{_res_row:,}".replace(",", "'"))
            # UND WIEVIEL BESITZT DU INSGESAMT? (Nutzer, Sitzung 20:
            # "Tritanium 20'076'549 besitze ich - ich weiss nicht, woher
            # diese Zahlen im Tool kommen.") Die Spalte zaehlt nur, was an
            # den Strukturen DIESES Plans liegt; der Rest ist unsichtbar.
            # Dass eine Zahl kleiner ist als der eigene Besitz, muss die
            # Zeile sagen - sonst sieht es aus, als haette das Werkzeug den
            # Bestand verloren. Im Dialog gibt es die Unterscheidung
            # ("0 - not on site") laengst, hier fehlte sie.
            _ges_row = int((_besitz_gesamt or {}).get(int(r["tid"]), 0) or 0)
            if _ges_row > int(_q_esi) and 3 in _exact:
                _exact[3] = _exact[3] + t(
                    " \u2013 you own {n} in total, the rest is not at this "
                    "plan's structures").format(
                        n=f"{_ges_row:,}".replace(",", "'"))
            # ERZ-ZEILE: Ausgang, Ausbeute, Charakter vor dem Kaufstatus;
            # MINERAL-ZEILE: "warum kein Erz" als Tooltip des Status.
            _rp_zeile = _rp_erz_info.get(int(r["tid"]))
            if _rp_zeile:
                status_txt = _rp_zeile + "  \u00b7  " + status_txt
            _rp_wn = _rp_warum_nicht.get(int(r["tid"]))
            if _rp_wn:
                r["reason"] = ((r.get("reason") + "\n") if r.get("reason") else "") + _rp_wn
            cells = [r["name"], self._kategorie_anzeige(r["category"]),
                    _sq(int(r["total"]), 2),
                    _esi_zelle,
                    man_txt,
                    _sq(_missing_q, 5) if _missing_q > 0 else miss_txt,
                    status_txt]
            # STATUS + KATEGORIE SORTIERBAR (Nutzer). Nach TEXT zu sortieren
            # waere sinnlos: "genug" kaeme vor "Rest wird gebaut", und
            # "Composite" vor "Intermediate" - die Kette stuende auf dem Kopf.
            # Deshalb NumericItem mit einem RANG.
            # Status-Reihenfolge wie gewuenscht: was fehlt zuerst, dann was
            # gebaut wird, zuletzt was gedeckt ist.
            # RANG AUS DER FARBE, NICHT AUS DEM TEXT (Sitzung 17). Vorher:
            # `"fehlt" in status_txt.lower()` - seit der Status uebersetzt ist,
            # fand das auf Englisch nichts ("partly - ... still to buy"), und
            # fehlendes Material rutschte beim Sortieren nach UNTEN. Die Farbe
            # traegt dieselbe Aussage in jeder Sprache.
            if status_col in (theme.RED, theme.AMBER, theme.VIOLET):
                _st_rank = 0          # muss beschafft werden -> nach oben
            elif status_col in (theme.BLUE, theme.GREEN_BRIGHT):
                _st_rank = 1          # laeuft ueber die eigene Produktion
            else:
                _st_rank = 2          # gedeckt -> nach unten
            _cells_out = []
            for col, text in enumerate(cells):
                if col == 1:
                    # Kategorie nach Ketten-RANG, nicht alphabetisch.
                    it = NumericItem(text, _CAT_RANK.get(r["category"], 99))
                elif col == 6:
                    # Leerer Text: der Balken traegt die Aussage, das Item
                    # nur den Sortier-Rang.
                    it = NumericItem("", _st_rank)
                    it.setData(Qt.UserRole, status_txt)
                else:
                    it = QTableWidgetItem(text)
                if col >= 2:
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if col == 1:
                    it.setForeground(QColor(theme.MUTED))
                if col == 3:
                    it.setForeground(esi_col)
                    it.setToolTip(esi_tip)
                if col == 4:
                    it.setForeground(man_col)
                    if _is_manual:
                        _f = it.font(); _f.setBold(True); it.setFont(_f)
                    it.setToolTip(man_tip)
                if col == 5:
                    it.setForeground(QColor(miss_col))
                    if _missing_q > 0:
                        _f = it.font(); _f.setBold(True); it.setFont(_f)
                    it.setToolTip(used_tip)
                if col in _exact:
                    it.setToolTip((it.toolTip() + "\n" if it.toolTip() else "")
                                  + t("Exact: ") + _exact[col])
                if col == 6:
                    it.setForeground(QColor(status_col))
                    if r.get("reason"):
                        it.setToolTip(r["reason"])
                if col == 0:
                    it.setData(Qt.UserRole, r["tid"])
                    icon = self._table_icon(r["tid"])
                    if icon:
                        it.setIcon(icon)
                _cells_out.append(it)
            # Knoten an seine Kategorie-Gruppe haengen. Ohne passende Gruppe
            # kommt er auf die oberste Ebene - so verschwindet nie eine Zeile.
            _par = _groups.get(r["category"])
            _node = QTreeWidgetItem(_par if _par is not None else tbl)
            for _ci, _src_it in enumerate(_cells_out):
                _node.setText(_ci, _src_it.text())
                _node.setTextAlignment(_ci, _src_it.textAlignment())
                _node.setForeground(_ci, _src_it.foreground())
                _node.setFont(_ci, _src_it.font())
                if _src_it.toolTip():
                    _node.setToolTip(_ci, _src_it.toolTip())
            _node.setData(0, Qt.UserRole, r["tid"])
            _node.setData(6, Qt.UserRole + 1, _st_rank)
            _ic0 = self._table_icon(r["tid"])
            if _ic0:
                _node.setIcon(0, _ic0)
            if _par is not None:
                _s = _gstat[r["category"]]
                _s[1] += 1
                # EIGENBAU ZAEHLT ALS GEDECKT (Nutzer-Entscheid 26.09.2026,
                # "Punkt 3 einfuehren"): seit MISSING bei Eigenbau-Zeilen
                # die offenen Runs zeigt, stand eine Kategorie, die man
                # komplett selbst baut, mit "0 / 11 covered" in Rot da -
                # obwohl nichts zu KAUFEN fehlt. Der Balken beantwortet
                # jetzt die Frage "muss ich noch etwas kaufen?": eine
                # Zeile, die der Plan selbst baut (_gedeckt, gruen), ist
                # gedeckt und wird getrennt als "im Bau" gezaehlt.
                _im_bau = bool(_gedeckt and _missing_q > 0)
                if not _missing_q or _im_bau:
                    _s[0] += 1
                if _im_bau:
                    _s[4] += 1
                    _s[2] += float(r["total"])
                else:
                    _s[2] += float(min(int(_src_qty), int(r["total"])))
                _s[3] += float(r["total"])
            # STATUS AN DER ZEILE MERKEN (26.09.2026): `_bd_mat_rows` traegt
            # ihn fuer Pruefungen und Nachzuege - dieselbe Zeichenkette wie
            # der Balken, keine zweite Rechnung.
            r["status"] = status_txt
            # Daten fuer den Deckungs-Balken merken - angehaengt wird er
            # ERST NACH setSortingEnabled(), s. unten.
            _bar_data[int(r["tid"])] = (
                int(min(100, max(0, round(int(_src_qty)
                                          / max(1, int(r["total"])) * 100)))),
                status_txt, status_col, used_tip)
        tbl.setSortingEnabled(True)
        # DECKUNGS-BALKEN erst JETZT anhaengen (Nutzer: "weniger wie eine
        # Excel-Tabelle, mehr wie ein Spiel"). WICHTIG: nach
        # setSortingEnabled() - das sortiert die Zeilen um und verwirft dabei
        # gesetzte Zell-Widgets. Deshalb wird die Zeile ueber die Item-Id
        # gesucht statt ueber den Schleifenindex.
        from PySide6.QtWidgets import QProgressBar as _QPB

        def _apply_bars():
            """Deckungs-Balken (neu) an die Zeilen haengen.

            MUSS nach JEDEM Sortieren erneut laufen. Qt sortiert die ITEMS um,
            laesst die ZELL-WIDGETS aber an ihrem alten Zeilenindex stehen -
            danach zeigt der Balken die Aussage einer FREMDEN Zeile. Genau das
            ist passiert, als die Status-Spalte sortierbar wurde: der Nutzer
            sah "teilweise - noch 94 kaufen" neben einer Zeile, zu der
            "Rest wird gebaut - 7'699 Stk" gehoerte.
            Die Zuordnung laeuft ueber die type_id aus Spalte 0, nie ueber den
            Schleifenindex.
            """
            _nodes = []
            for _gi in range(tbl.topLevelItemCount()):
                _g = tbl.topLevelItem(_gi)
                _nodes.append(_g)
                for _ci in range(_g.childCount()):
                    _nodes.append(_g.child(_ci))
            for _node in _nodes:
                _tid0 = _node.data(0, Qt.UserRole)
                if _tid0 is None:
                    # GRUPPENZEILE: Fortschritt der ganzen Kategorie.
                    _s = _gstat.get(_node.data(1, Qt.UserRole) or _node.text(0))
                    if not _s or not _s[1]:
                        continue
                    _pct = int(min(100, max(0, round(
                        _s[2] / max(1.0, _s[3]) * 100))))
                    _stxt = t("{a} / {b} covered").format(a=_s[0], b=_s[1])
                    _scol = (theme.GREEN if _s[0] == _s[1]
                             else theme.AMBER if _s[0] else theme.RED)
                    _stip = t("{a} of {b} materials of this category are fully "
                              "covered.").format(a=_s[0], b=_s[1])
                    if _s[4]:
                        _stxt += "  \u00b7  " + t("{n} being built").format(n=_s[4])
                        _stip += "\n" + t(
                            "{n} of them are built by this plan itself \u2013 "
                            "nothing to buy, the open runs are in the run "
                            "planner.").format(n=_s[4])
                else:
                    _d = _bar_data.get(_tid0)
                    if not _d:
                        continue
                    _pct, _stxt, _scol, _stip = _d
                _bar = _QPB()
                _bar.setRange(0, 100); _bar.setValue(_pct)
                _bar.setTextVisible(True); _bar.setFormat(_stxt)
                _bar.setFixedHeight(20)
                # Diese Balken entstehen auch NACH dem zentralen
                # Umbruch-Lauf neu (bei jedem Sortieren) - deshalb selbst
                # umbrechen, sonst zieht der Tooltip sich ueber die volle
                # Fensterbreite.
                _bar.setToolTip(t("{pct} % covered\n").format(pct=_pct) + _stip)
                self._wrap_tooltips(_bar)
                _bar.setStyleSheet(
                    f"QProgressBar{{background:rgba(255,255,255,0.05); "
                    f"border:none; border-radius:5px; color:{_scol}; "
                    f"font-size:11px; text-align:center;}}"
                    f"QProgressBar::chunk{{background:rgba(255,255,255,0.10); "
                    f"border-radius:5px;}}")
                tbl.setItemWidget(_node, 6, _bar)
        _apply_bars()
        # Nach jedem Klick auf eine Spaltenueberschrift neu zuordnen.
        _hdr_mat = tbl.header()
        # Auch hier: nur die EIGENE alte Verbindung loesen (disconnect()
        # ohne Argument toetet Qts internes Sortieren, s. Capital-Fund).
        # NUR AM SELBEN KOPF LOESEN (pruefe.py beim Nutzer 27.09.2026:
        # "RuntimeWarning: libpyside: Failed to disconnect ... _alt_mat"):
        # nach einem Neuaufbau ist die Tabelle neu, der alte Slot hing am
        # ALTEN Kopf - dort gibt es nichts zu loesen, PySide warnte nur.
        _alt_mat = getattr(self, "_mat_bars_sort_slot", None)
        if (_alt_mat is not None
                and getattr(self, "_mat_bars_sort_kopf", None) is _hdr_mat):
            try:
                _hdr_mat.sortIndicatorChanged.disconnect(_alt_mat)
            except (TypeError, RuntimeError):
                pass
        # WIEDEREINTRITTS-SCHUTZ (Sitzung 16): `_apply_bars` setzt fuer jede
        # Zeile ein Widget. Laeuft waehrenddessen erneut ein Sortier-Signal
        # ein, ruft es sich selbst - im Betrieb faellt das nicht auf (der
        # Nutzer klickt nicht schnell genug), im Testlauf mit
        # `processEvents()` schon: die b-Suite blieb an genau dieser Stelle
        # haengen. Kostet nichts und kann nur helfen.
        def _sort_slot(*_a):
            if getattr(self, "_mat_bars_laeuft", False):
                return
            self._mat_bars_laeuft = True
            try:
                _apply_bars()
            finally:
                self._mat_bars_laeuft = False

        self._mat_bars_sort_slot = _sort_slot
        self._mat_bars_sort_kopf = _hdr_mat
        _hdr_mat.sortIndicatorChanged.connect(self._mat_bars_sort_slot)
        # Startzustand: nach Kategorie gruppiert. Wer nach Status sortiert,
        # bekommt weiterhin "fehlt zuerst" - ein Klick auf "Kategorie" holt
        # die Gruppierung zurueck.
        # Sortiert INNERHALB der Gruppen - die Gliederung bleibt erhalten.
        tbl.sortByColumn(1, Qt.AscendingOrder)
        # ZUGEKLAPPT starten (Nutzer: "wegen Ueberflutung von Informationen").
        # Man sieht die Kategorien mit ihrem Fortschrittsbalken und klappt
        # gezielt auf, was einen interessiert - statt 51 Zeilen auf einmal.
        # WICHTIG: der Zustand pro Gruppe bleibt ueber "Neu berechnen"
        # erhalten, sonst waere jede Aenderung ein Rueckschritt.
        _open_before = getattr(self, "_bd_mat_open_groups", None)
        for _gi2 in range(tbl.topLevelItemCount()):
            _g2 = tbl.topLevelItem(_gi2)
            _g2.setExpanded(bool(_open_before) and _g2.text(0) in _open_before)

        def _remember_open(*_a):
            self._bd_mat_open_groups = {
                tbl.topLevelItem(_i).text(0)
                for _i in range(tbl.topLevelItemCount())
                if tbl.topLevelItem(_i).isExpanded()}
        if not getattr(self, "_bd_mat_expand_connected", False):
            tbl.itemExpanded.connect(_remember_open)
            tbl.itemCollapsed.connect(_remember_open)
            self._bd_mat_expand_connected = True
        # SPALTEN NUR ZEIGEN, WENN SIE ETWAS AUSSAGEN (Nutzer-Linie).
        # MUSS nach dem Aufbau von `rows` stehen - beim ersten Versuch stand
        # es im Kopfbereich und knallte als UnboundLocalError; der
        # Aufbau-Test hat es sofort gemeldet.
        # "Kategorie" ist Kontext, kein Wert. "Eingefuegt" ist ohne
        # Einfuegung eine Spalte voller Striche.
        # KATEGORIE WIEDER SICHTBAR (Nutzer: "Materialien-Tab wirkt
        # ueberladen, kann man nach Reaktionen/Komponenten aufteilen?").
        # Sichere Zwischenloesung statt Umbau auf einen Baum: die Zeilen sind
        # ohnehin schon nach Kategorie sortiert (s. rows.sort weiter oben) -
        # mit sichtbarer Spalte stehen gleichartige Materialien erkennbar
        # beieinander, ohne dass an Sortierung, Balken oder Einfuege-Panel
        # etwas geaendert werden muss.
        tbl.setColumnHidden(1, False)
        # setColumnHidden(False) stellt die FRUEHERE Breite wieder her - und
        # die kann 0 sein, wenn die Spalte vorher versteckt war. Dann waere
        # sie zwar "sichtbar", aber null Pixel breit (Nutzer: "es sieht alles
        # aus wie vorher"). Deshalb eine Mindestbreite erzwingen.
        if tbl.columnWidth(1) < 60:
            tbl.setColumnWidth(1, 165)
        tbl.setColumnHidden(4, not any(r.get("q_manual") is not None
                                       for r in rows))
        # `_autosize_once` ist auf QTableWidget zugeschnitten (rowCount).
        # Fuer den Baum die Spalten einmalig selbst bemessen.
        _sz_key = f"mat_tree_{id(tbl)}"
        if _sz_key not in self._sized and tbl.topLevelItemCount():
            for _c in range(tbl.columnCount()):
                tbl.resizeColumnToContents(_c)
                tbl.setColumnWidth(_c, max(tbl.columnWidth(_c) + 18, 80))
            self._sized.add(_sz_key)
        # STATUS-Spalte fuellt den Rest der Breite. Sie wird sonst nach INHALT
        # bemessen - und der Fortschrittsbalken ist ein Zell-WIDGET, das dabei
        # nicht mitzaehlt. Ergebnis war eine gequetschte Spalte, in der der
        # Text abgeschnitten wurde (Nutzer zog sie jedes Mal von Hand breit).
        # Nach _autosize_once gesetzt, sonst ueberschreibt das die Vorgabe.
        from PySide6.QtWidgets import QHeaderView as _QHV
        _mh = tbl.header()
        _mh.setSectionResizeMode(6, _QHV.Stretch)
        # Kein setMinimumSectionSize - s. Blueprints-Tab: es holt versteckte
        # Spalten zurueck. Stattdessen die Ausblendung danach bestaetigen.
        tbl.setColumnHidden(4, not any(r.get("q_manual") is not None
                                       for r in rows))
        if status_lbl is not None:
            if not stock:
                status_lbl.setText(t(
                    "\u2139 No stock data yet - \u201e Subtract assets\u201c above "
                    "normally runs automatically on opening."))
            else:
                _n_man = sum(1 for r in rows if r.get("src") == "manuell")
                _txt = t("{types} material types \u00b7 {buy} to buy \u00b7 {build} "
                         "will be built \u00b7 {stock} covered from stock \u2713").format(
                    types=len(rows), buy=n_missing, build=n_built,
                    stock=len(rows) - n_missing - n_built)
                # Herkunft NICHT verschweigen: wenn eingefügte Zahlen mitspielen,
                # muss das in der Kopfzeile stehen, nicht nur in den Spalten.
                if _n_man:
                    _txt += t(" \u00b7 {n} of them from PASTED stock").format(
                        n=_n_man)
                elif getattr(self, "_bd_manual_stock", None):
                    _txt += t(" \u00b7 pasted stock present, but superseded "
                              "(ESI data is fresher)")
                status_lbl.setText(_txt)
        return n_missing

    # ZIELZEIT JE STUFE (Nutzer 24.09.2026: "wie lange moechtest du
    # Reactions fahren? -> Regler 1-24 h / Tage / Wochen"). Die Werte sind
    # STUNDEN; 0 heisst "so schnell wie moeglich" (die Stufe wird dann nur
    # gestrafft, s. industry.schedule_build). Die Auswahl deckt den Abend
    # (4-12 h), die Nacht bis zum naechsten Abend (16-24 h) und das
    # Wochenende ab - laenger als eine Woche plant niemand einen Bauabend.
    # OBERGRENZE EINE WOCHE (Nutzer 24.09.2026: "bis 1 Woche hoch"). Die
    # Untergrenze ist keine feste Zahl, sondern die GEMESSENE Mindestdauer
    # der Stufe - s. `_runplan_ziel_feld`.
    _RUNPLAN_ZIEL_MAX = 168
    # Die sechs Stufen, wie schedule_build sie nennt. Reihenfolge = Bau-
    # reihenfolge, damit die Auswahl oben genauso steht wie der Plan unten.
    _RUNPLAN_STUFEN = ("fuel", "unrefined", "reaction_1", "reaction_2",
                       "component", "end")

    def _runplan_erledigt_pflegen(self, key, an):
        """Die abgehakten RUNS je (Stufe, Item) nachfuehren.

        Der Haken-Schluessel traegt die Charakter-ID (`stufe|cid|item`).
        Wechselt der Nutzer die Bau-Charaktere und drueckt "Apply", verteilt
        der Planer neu - die alten Schluessel zeigen dann ins Leere, und die
        abgehakten Runs standen wieder als offen da (Nutzer 24.09.2026:
        "jetzt weiss ich nicht mehr, was ich bauen muss, bis die ESI
        aktualisiert"). Was der Haken WIRKLICH sagt, ist "so viele Runs
        dieses Items habe ich gestartet" - ohne Charakter. Genau das steht
        hier, und daraus werden die Haken nach einer Umverteilung wieder
        aufgebaut.
        """
        _rk = getattr(self, "_bd_runplan_runs_by_key", None) or {}
        _paar = _rk.get(key)
        if not _paar:
            return          # Charakter- und Reprocessing-Zeilen tragen keine Runs
        _tid, _runs = int(_paar[0]), int(_paar[1] or 0)
        if _runs <= 0:
            return
        _stufe = str(key).split("|")[0]
        _erl = getattr(self, "_bd_runplan_erledigt", None)
        if _erl is None:
            _erl = {}
            self._bd_runplan_erledigt = _erl
        _k = f"{_stufe}|{_tid}"
        _alt = int(_erl.get(_k, 0) or 0)
        if an:
            _erl[_k] = max(0, _alt + _runs)
        else:
            # NUTZER LOEST DEN HAKEN (emm417, "Oxygen Fuel Block wird
            # staendig angehakt obwohl ich nichts anhacke"): ein ALTER
            # Ueberhang (z. B. aus einer frueheren Verteilung mit mehr
            # Runs) trug den Haken sonst bei JEDEM Neuaufbau wieder ein -
            # der ESI-Autorefresh baut alle paar Minuten neu, Abhaken
            # senkte den Rest nur um die Zeilen-Runs, und solange Rest >=
            # Zeilen-Runs blieb, kam der Haken zurueck (haken_nachtragen).
            # Deshalb KAPPEN auf das, was WIRKLICH noch angehakt ist:
            # die Summe der Runs aller noch gehakten Zeilen dieses Items
            # dieser Stufe. Haken-Zeilen, deren Schluessel der aktuelle
            # Aufbau nicht kennt, zaehlen 0 - der Rest wird dadurch
            # hoechstens KLEINER, also wird hoechstens MEHR gekauft
            # (Regel 3, sichere Richtung).
            _chk = getattr(self, "_bd_runplan_checked", None) or set()
            _summe = 0
            for _k2 in _chk:
                if _k2 == key:
                    continue
                _p2 = _rk.get(_k2)
                if (_p2 and int(_p2[0]) == _tid
                        and str(_k2).split("|")[0] == _stufe):
                    _summe += max(0, int(_p2[1] or 0))
            _erl[_k] = min(max(0, _alt - _runs), _summe)
        # Zeitpunkt je Item mitfuehren (emm336): beim Setzen der juengste
        # Haken, ist nichts mehr erledigt, faellt er weg.
        _ets = getattr(self, "_bd_runplan_erledigt_ts", None)
        if _ets is None:
            _ets = {}
            self._bd_runplan_erledigt_ts = _ets
        if an:
            import time as _t_erl
            _ets[_k] = max(float(_ets.get(_k, 0) or 0), _t_erl.time())
        elif _erl[_k] <= 0:
            _ets.pop(_k, None)

    def _runplan_ziel_stunden(self, stage):
        """Zielzeit DIESER Stufe in Stunden - 0 = so schnell wie moeglich."""
        _z = (self.settings.get("bau_runplan_ziel") or {})
        try:
            _v = int(_z.get(str(stage), 0) or 0)
        except (TypeError, ValueError):
            _v = 0
        if _v == 0:
            try:
                _v = int(self.settings.get("bau_runplan_ziel_std", 0) or 0)
            except (TypeError, ValueError):
                _v = 0
        return _v if _v >= 0 else -1

    def _runplan_ziel_sekunden(self):
        """{stage: Sekunden} fuer `schedule_build` - leere Eintraege weg.

        EINE Stelle fuer die Umrechnung: die Einstellung steht in STUNDEN
        (so steht sie auch im Auswahlfeld), der Planer rechnet in Sekunden.
        """
        _out = {}
        for _st in self._RUNPLAN_STUFEN:
            _h = self._runplan_ziel_stunden(_st)
            if _h < 0:
                # "SO LANGE WIE MOEGLICH" (Nutzer 24.09.2026): keine Grenze -
                # der Planer nimmt dann so wenige Jobs wie ueberhaupt
                # moeglich. Unendlich statt einer grossen Zahl, damit
                # niemand spaeter raetselt, was "999999" bedeuten sollte.
                _out[_st] = float("inf")
            elif _h > 0:
                _out[_st] = float(_h) * 3600.0
        return _out

    def _runplan_ziel_setzen(self, stage, stunden):
        """Zielzeit einer Stufe merken (stage=None -> Vorgabe fuer alle)."""
        if stage is None:
            self.settings["bau_runplan_ziel_std"] = int(stunden or 0)
        else:
            _z = dict(self.settings.get("bau_runplan_ziel") or {})
            if int(stunden or 0) != 0:
                _z[str(stage)] = int(stunden)
            else:
                _z.pop(str(stage), None)
            self.settings["bau_runplan_ziel"] = _z
        try:
            from .. import config as _cfgz
            _cfgz.save_settings(self.settings)
        except Exception:
            pass

    # DIE ZWEI FELDER: Tage und Stunden (Nutzer 24.09.2026: "es springt von
    # 23 h auf 1 T 1 h automatisch [...] vielleicht sollten wir den Regler
    # weglassen und stattdessen 2 Dropdowns einfuegen, Tage Stunden").
    # GEMESSEN: der Regler hatte in der Spalte rund 150 px fuer 27 Rasten -
    # 5 Pixel je Stunde. Ein Auswahlfeld trifft jede Stunde, ohne Zielen.
    _RUNPLAN_TAGE_MAX = 7

    def _planer_diagnose_schreiben(self, jobs, chars, te, res, names, type_id):
        """Die EINGABEN und das ERGEBNIS des Runplaners in eine Textdatei.

        WOZU: Fragen wie "warum nur 11 von 19 Blaupausen" oder "warum sind
        es bei 23 h Ziel nur 15 h 26 m" lassen sich ohne die echten Eingaben
        nicht nachstellen - jede Antwort waere geraten (Regel 5). Hier
        stehen sie: Jobs mit Runs und Zeit je Run, die angekreuzten
        Charaktere mit ihren Slots, alle Deckel, die Zielzeiten - und was
        der Planer daraus gemacht hat.

        NUR LESEN UND SCHREIBEN, keine Rechnung: die Datei darf nie
        beeinflussen, was der Planer tut.
        """
        import os as _os
        import time as _zt
        # `config` ist in dieser Datei NICHT importiert (nur esi, hubs,
        # industry, reprocess, store) - hier holen, nicht oben, damit der
        # Import-Kopf der Datei unveraendert bleibt.
        from .. import config as _cfg
        _z = (lambda v: f"{int(v):,}".replace(",", "'"))
        _pfad = _os.path.join(_cfg.app_data_dir(), "planer_diagnose.txt")
        _cap = self._resolve_per_item_bp_cap() or {}
        _rcap = self._resolve_per_item_runs_cap(type_id) or {}
        _ziel = self._runplan_ziel_sekunden() or {}
        _nm = (lambda t: str((names or {}).get(int(t)) or t))
        _z2 = []
        _a = _z2.append
        # de_scan4: aus - Diagnosedatei fuer die Fehlersuche (planer_diagnose.txt),
        # bewusst deutsch wie unrefined_diagnose.txt; erscheint nie auf dem Schirm.
        _a("=" * 78)
        _a(f"PLANER-DIAGNOSE  (Plan {type_id})")
        _a(f"Erstellt: {_zt.strftime('%Y-%m-%d %H:%M:%S')}")
        _a("=" * 78)
        _a(f"TE-Faktor: {te}")
        _a("")
        _a("ZIELZEITEN JE STUFE (Sekunden; inf = so lange wie noetig):")
        for _k, _v in sorted(_ziel.items()):
            _a(f"  {_k}: {_v}")
        if not _ziel:
            _a("  (keine - 'so schnell wie moeglich')")
        _a("")
        _a("CHARAKTERE (angekreuzt) - Slots:")
        for _c in (chars or []):
            _a(f"  {_c.get('name')}  mfg={_c.get('mfg_slots')} "
               f"react={_c.get('reaction_slots')} "
               f"can_mfg={_c.get('can_mfg')} can_react={_c.get('can_react')} "
               f"zeit_mfg={_c.get('mfg_time')} zeit_react={_c.get('react_time')}")
        _a("")
        _a("JOBS (Eingabe des Planers):")
        _a("  ITEM                          RUNS   ZEIT/RUN(s)  AKTIV  "
           "KOPIEN  RUNS/KOPIE  ENDE  TE-JOB")
        for _j in (jobs or []):
            _t = int(_j.get("tid") or 0)
            _a(f"  {_nm(_t)[:28]:<28} {_z(_j.get('runs') or 0):>6} "
               f"{_z(_j.get('base_time') or 0):>12} "
               f"{str(_j.get('activity')):>6} "
               f"{str(_cap.get(_t, '-')):>7} {str(_rcap.get(_t, '-')):>11}  "
               f"{'ja' if _j.get('is_end') else '  '}    "
               f"{_j.get('te_factor', te)}")
        _a("")
        _a("ERGEBNIS - Stufenzeiten (Sekunden):")
        for _k, _v in sorted((res or {}).get("stage_times", {}).items()):
            _a(f"  {_k}: {_v}")
        _a("")
        _a("ERGEBNIS - Mindestdauer je Stufe (stage_min_times):")
        for _k, _v in sorted((res or {}).get("stage_min_times", {}).items()):
            _a(f"  {_k}: {_v}")
        _a("")
        _a("ERGEBNIS - Zuteilungen (je Item/Charakter):")
        _a("  ITEM                          CHARAKTER          RUNS  JOBS  "
           "TEILE                STUFE")
        for _x in ((res or {}).get("assignments") or []):
            _a(f"  {_nm(_x.get('tid'))[:28]:<28} "
               f"{str(_x.get('char_name'))[:17]:<17} "
               f"{_z(_x.get('runs') or 0):>6} {str(_x.get('njobs') or ''):>5}  "
               f"{str(_x.get('parts') or '')[:20]:<20} {_x.get('stage')}")
        _a("")
        _a("ENDE")
        # de_scan4: an
        with open(_pfad, "w", encoding="utf-8") as _fh:
            _fh.write("\n".join(_z2) + "\n")

    def _runplan_ziel_feld(self, tbl, item, stage, min_sek=0.0, min_info=None):
        """Zielzeit einer Stufe: zwei Auswahlfelder, Tage und Stunden.

        NUTZER 24.09.2026: "vielleicht sollten wir den Regler weglassen und
        stattdessen 2 Dropdowns einfuegen, Tage Stunden" - und danach: "das
        Dropdown erlaubt Einstellungen, die nicht moeglich sind, 0 d und 1 h
        geht nicht".

        WAS NICHT GEHT, STEHT NICHT ZUR WAHL. Die Stufe braucht eine
        Mindestdauer (`stage_min_times`, gemessen) - jede Zeit darunter
        aendert am Plan nichts. Ein Auswahlfeld, das sie trotzdem anbietet,
        verspricht etwas, das nicht eintritt; deshalb beginnen die Stunden
        beim kleinsten moeglichen Wert, und die Tage beginnen bei den vollen
        Tagen der Mindestdauer. Der erste Eintrag heisst "so schnell wie
        moeglich" und ist genau diese Mindestdauer.
        """
        import math
        from PySide6.QtWidgets import (QComboBox as _QCb, QHBoxLayout as _QHb,
                                       QWidget as _QWd, QLabel as _QLb)
        _LEER = -999      # "keine Stundenangabe" (Strich), s. _stunden_fuellen
        _min_h = max(0, int(math.ceil(float(min_sek or 0.0) / 3600.0)))
        _ziel = self._runplan_ziel_stunden(stage)
        _box = _QWd()
        _lay = _QHb(_box)
        _lay.setContentsMargins(2, 0, 4, 0)
        _lay.setSpacing(4)
        _cd = _QCb(_box)          # Tage (plus die zwei Sonderfaelle)
        _cd.addItem(t("as fast as possible"), 0)
        for _d in range(_min_h // 24, self._RUNPLAN_TAGE_MAX + 1):
            _cd.addItem(t("{n} d").format(n=_d), _d + 1000)   # +1000 = echte Tage
        _cd.addItem(t("as long as it takes"), -1)
        # BREITE GEMESSEN, NICHT GERATEN (Nutzer 25.09.2026: "as fast as
        # possible ist abgeschnitten"). Die festen 120 px reichten hier
        # offscreen; auf seinem Windows sind dieselben Widgets rund 1,6-1,85x
        # breiter - derselbe Befund wie b66 und die ME/TE-Felder im
        # Multi-Bauplan. Deshalb der groessere von Vorgabe und gemessenem
        # Bedarf.
        _cd.setSizeAdjustPolicy(_QCb.AdjustToContents)

        def _combo_breite(_cb, _mindest):
            """Breite eines Auswahlfelds aus dem LAENGSTEN Eintrag - nicht
            nur aus sizeHint. Zweiter Nutzer-Screenshot 26.09.2026: "as fast
            as possibl" blieb im Feld selbst abgeschnitten, obwohl das Feld
            seine sizeHint-Breite hatte. sizeHint kennt das Polster des
            Themas (QComboBox: padding 3px 6px, 1 px Rahmen) und den Pfeil
            nur ungefaehr; auf seinem Windows fehlten ein paar Pixel.
            Gemessen: Textbreite + 12 px Polster + 2 px Rahmen + 24 px Pfeil
            + 6 px Reserve, mindestens sizeHint + 8."""
            _fmc = _cb.fontMetrics()
            _txtw = max([_fmc.horizontalAdvance(_cb.itemText(_i))
                         for _i in range(_cb.count())] or [0])
            return max(_mindest, _cb.sizeHint().width() + 8, _txtw + 44)

        _cd.setFixedWidth(_combo_breite(_cd, 120))
        _ch = _QCb(_box)          # Stunden
        _tip = t(
            "How long may THIS stage run? Days and hours together. The first "
            "entry is \u201eas fast as possible\u201c \u2013 the time the stage "
            "needs anyway; anything shorter is not offered because it would "
            "not change the plan. The more time you give it, the fewer "
            "blueprints and slots the planner uses.")
        if min_info and min_info.get("name"):
            _tip += "\n\n" + t(
                "Shorter than {d} is not possible: {name} needs {runs} run(s) "
                "and can use {slots} slot(s) at once. More characters or more "
                "blueprint copies for that item would shorten it."
            ).format(d=self._fmt_dur(float(min_sek or 0.0)),
                     name=min_info.get("name"),
                     runs=int(min_info.get("runs") or 0),
                     slots=int(min_info.get("slots") or 1))
        _cd.setToolTip(_tip)
        _ch.setToolTip(_tip)

        def _stunden_fuellen(tage, wunsch=0, leer=False):
            """Nur Stunden anbieten, die zusammen mit den Tagen ueber der
            Mindestdauer liegen - sonst waere die Wahl folgenlos.

            `leer=True` stellt einen Strich voran und waehlt ihn: ohne
            gesetzte Zielzeit darf hier KEINE Stundenzahl stehen. Der Nutzer
            las sonst eine Vorgabe, die es nicht gibt (25.09.2026: "da steht
            7 h, sind aber eigentlich 5 h 36 m"; die 7 war bloss die
            aufgerundete Mindestdauer). Auswaehlbar bleibt das Feld
            trotzdem - wer eine Stunde waehlt, setzt damit ein Ziel."""
            _ab = max(0, _min_h - int(tage) * 24) if int(tage) * 24 < _min_h else 0
            _alt = _ch.blockSignals(True)
            _ch.clear()
            if leer:
                _ch.addItem("\u2013", _LEER)
            for _h in range(min(_ab, 23), 24):
                _ch.addItem(t("{n} h").format(n=_h), _h)
            _i = _ch.findData(_LEER if leer else int(wunsch))
            _ch.setCurrentIndex(_i if _i >= 0 else 0)
            _ch.setSizeAdjustPolicy(_QCb.AdjustToContents)
            _ch.setFixedWidth(_combo_breite(_ch, 76))
            _ch.blockSignals(_alt)

        _st_lbl = _QLb(_box)
        _st_lbl.setStyleSheet(f"color:{theme.CYAN}; font-weight:700;")
        _st_lbl.setText(self._runplan_ziel_text(_ziel, _min_h))
        if int(_ziel or 0) < 0:
            _cd.setCurrentIndex(_cd.count() - 1)
            _stunden_fuellen(0, leer=True)
            _ch.setEnabled(False)
        elif int(_ziel or 0) > 0:
            _z = int(_ziel)
            _i = _cd.findData(min(_z // 24, self._RUNPLAN_TAGE_MAX) + 1000)
            _cd.setCurrentIndex(_i if _i >= 0 else 0)
            _stunden_fuellen(_z // 24, _z % 24)
        else:
            # KEIN ZIEL = KEINE STUNDENZAHL, aber bedienbar: wer hier eine
            # Stunde waehlt, setzt damit das Ziel (die Tage springen auf 0 d).
            _cd.setCurrentIndex(0)
            _stunden_fuellen(0, leer=True)
        _lay.addWidget(_cd)
        _lay.addWidget(_ch)
        _lay.addWidget(_st_lbl, 1)

        def _gewaehlt(*_a):
            _d = int(_cd.currentData() or 0)
            _hd = _ch.currentData()
            if _d < 0:                      # so lange wie noetig
                _ch.setEnabled(False)
                _stunden_fuellen(0, leer=True)
                _neu = -1
            elif _d == 0 and _hd is not None and int(_hd) != _LEER:
                # STUNDE OHNE TAGE: das ist ein Ziel, kein "so schnell wie
                # moeglich". Die Tage springen sichtbar auf 0 d, sonst
                # stuenden zwei Aussagen nebeneinander.
                _neu = int(_hd)
                _alt_d = _cd.blockSignals(True)
                _i0 = _cd.findData(1000)
                if _i0 >= 0:
                    _cd.setCurrentIndex(_i0)
                _cd.blockSignals(_alt_d)
            elif _d == 0:                   # so schnell wie moeglich
                _ch.setEnabled(True)
                _stunden_fuellen(0, leer=True)
                _neu = 0
            else:
                _ch.setEnabled(True)
                _tage = _d - 1000
                _stunden_fuellen(_tage, int(_ch.currentData() or 0))
                _neu = _tage * 24 + int(_ch.currentData() or 0)
            _st_lbl.setText(self._runplan_ziel_text(_neu, _min_h))
            self._runplan_ziel_gewaehlt(stage, _neu)
        _cd.currentIndexChanged.connect(_gewaehlt)
        _ch.currentIndexChanged.connect(_gewaehlt)
        tbl.setItemWidget(item, 2, _box)
        # DIE SPALTE MUSS DAS FELD FASSEN (Nutzer 26.09.2026: "die
        # Zeitdropdowns bissl abgeschnitten"). Die Blaupausen-Spalte ist
        # 280 px breit (mw_bauplan_fenster); auf seinem Windows sind beide
        # Auswahlfelder zusammen breiter - Qt schneidet das Feld dann am
        # Spaltenrand ab, egal wie sauber seine eigene Breite gemessen ist.
        # Gemessen: feste Breiten der zwei Felder + Abstand + Platz fuer
        # die Textzeile daneben.
        _need = (_cd.width() + _ch.width() + 3 * _lay.spacing()
                 + _st_lbl.fontMetrics().horizontalAdvance(_st_lbl.text()) + 12)
        if tbl.columnWidth(2) < _need:
            tbl.setColumnWidth(2, int(_need))
        return _cd

    def _runplan_ziel_alle_gewaehlt(self, stunden):
        """Die Vorgabe fuer ALLE Stufen setzen (und Ausnahmen zuruecknehmen).

        Sonst waehlte man oben etwas, und unten bliebe eine Stufe stumm bei
        ihrem alten Regler stehen - zwei Aussagen ueber dieselbe Sache.
        """
        _h = int(stunden or 0)
        if (_h == int(self.settings.get("bau_runplan_ziel_std", 0) or 0)
                and not (self.settings.get("bau_runplan_ziel") or {})):
            return
        self.settings["bau_runplan_ziel"] = {}
        self._runplan_ziel_setzen(None, _h)
        _fn = getattr(self, "_bd_full_rebuild", None)
        if _fn is not None:
            QTimer.singleShot(0, _fn)

    def _runplan_ziel_gewaehlt(self, stage, stunden):
        """Auswahl uebernehmen und den Plan neu rechnen lassen."""
        if int(stunden or 0) == self._runplan_ziel_stunden(stage):
            return
        self._runplan_ziel_setzen(stage, stunden)
        _fn = getattr(self, "_bd_full_rebuild", None)
        if _fn is not None:
            QTimer.singleShot(0, _fn)

    @staticmethod
    def _runplan_ziel_text(stunden, min_h=0):
        """Beschriftung eines Zielwerts. 0 und -1 bekommen einen eigenen
        Satz - eine Zahl waere dort eine Behauptung ueber eine Dauer, die
        gar nicht eingestellt ist."""
        _h = int(stunden or 0)
        if _h < 0:
            return t("as long as it takes")
        if _h <= 0 or (min_h and _h <= int(min_h)):
            return t("as fast as possible")
        if _h < 24:
            return t("{n} h").format(n=_h)
        if _h % 24 == 0:
            return t("{n} d").format(n=_h // 24)
        return t("{d} d {h} h").format(d=_h // 24, h=_h % 24)

    def _planer_diagnose_fortschritt(self, plan, names, plan_runs, rest_budget):
        """Anhang an planer_diagnose.txt: WOHER der Rest je Item kommt.

        NUTZER 26.09.2026 (Titanium Diborite Armor Plate): "schau wieviel ich
        baue und der Runplaner will trotzdem nochmal 6'718 nachbauen ...
        genau das passiert die ganze Zeit". Vom Schirm ist das nicht
        nachrechenbar - hier stehen je Item: Plan-Runs, gelieferte und
        laufende Runs (ESI), das Rest-Budget, dazu der Bestand in seinen
        Schichten (Einfrier-Stand, Hangar live, Pipeline, Einfuegung,
        wirksam) und was der Plan davon verbraucht (stock_used). NUR
        SCHREIBEN, keine Rechnung - die Datei darf nie beeinflussen, was
        der Planer tut (wie _planer_diagnose_schreiben)."""
        import os as _os
        import time as _zt
        from .. import config as _cfg
        _z = (lambda v: f"{int(v or 0):,}".replace(",", "'"))
        _nm = (lambda t: str((names or {}).get(int(t)) or t))
        _pfad = _os.path.join(_cfg.app_data_dir(), "planer_diagnose.txt")
        _frz = getattr(self, "_bd_frozen", None) or {}
        _fz_stock = {int(k): int(v or 0) for k, v in (_frz.get("stock") or {}).items()}
        _hangar = getattr(self, "_bd_hangar_only", None) or {}
        _pipe = getattr(self, "_bd_pipeline_live", None) or {}
        _manual = getattr(self, "_bd_manual_stock", None) or {}
        _wirksam = (getattr(self, "_bd_opts", None) or {}).get("stock") or {}
        _used = (plan or {}).get("stock_used") or {}
        _gel = getattr(self, "_bd_runplan_delivered", None) or {}
        _gel_s = getattr(self, "_bd_runplan_delivered_sicher", None) or {}
        _akt = getattr(self, "_bd_active_jobs_map", None) or {}
        _dlv = getattr(self, "_bd_delivered_jobs", None) or []
        _zl = []
        _a = _zl.append
        # de_scan4: aus - Diagnosedatei (planer_diagnose.txt), nie auf dem Schirm
        # de_scan2: aus  (dieselbe Diagnosedatei, deutsch wie planer_diagnose)
        _a("")
        _a("=" * 78)
        _a(f"FORTSCHRITT UND BESTAND JE ITEM  ({_zt.strftime('%Y-%m-%d %H:%M:%S')})")
        _a(f"Plan eingefroren: "
           + (_zt.strftime('%Y-%m-%d %H:%M', _zt.localtime(float(_frz.get('ts'))))
              if _frz.get("ts") else "nein")
           + f"   Schnappschuss: {'ja' if _frz.get('plan_snapshot') else 'nein'}"
           + f"   Einfrier-Bestand: {len(_fz_stock)} Items")
        _a(f"ESI-Jobdaten von: "
           + (_zt.strftime('%Y-%m-%d %H:%M:%S',
                           _zt.localtime(float(getattr(self, '_bd_jobs_ts', 0) or 0)))
              if getattr(self, "_bd_jobs_ts", None) else "(noch kein Abruf)"))
        _a("")
        _a("RUNS:  Plan = Summe der Zuteilungen; geliefert = ESI-Jobs seit dem "
           "Einfrieren (sicher zugeordnet); laufend = aktive Jobs; "
           "erledigt = min(Plan, geliefert + laufend); Rest = Plan - erledigt "
           "(das zeigt der Runplaner)")
        _a("  ITEM                            PLAN   GELIEFERT  (unsicher)  "
           "LAUFEND  ERLEDIGT      REST")
        for _t in sorted(plan_runs, key=lambda t: -int(plan_runs.get(t) or 0)):
            _lauf = sum(int(_j.get("runs") or 0) for _j in (_akt.get(_t) or []))
            _erl = int(rest_budget.get(_t) or 0)
            _a(f"  {_nm(_t)[:30]:<30} {_z(plan_runs.get(_t)):>7} "
               f"{_z(_gel_s.get(_t)):>10} {_z(_gel.get(_t)):>11} "
               f"{_z(_lauf):>8} {_z(_erl):>9} "
               f"{_z(int(plan_runs.get(_t) or 0) - _erl):>9}")
            for _j in (_akt.get(_t) or []):
                _a(f"      laufend: {_z(_j.get('runs')):>7} Runs  {_j.get('status')}"
                   f"  {_j.get('char')}  Ende {_j.get('end_date')}")
            for _j in _dlv:
                if int(_j.get("product_type_id") or 0) != int(_t):
                    continue
                _a(f"      geliefert: {_z(_j.get('runs')):>5} Runs  Job {_j.get('job_id')}"
                   f"  Start {_j.get('start_date')}  fertig {_j.get('completed_date')}")
        _a("")
        _a("BESTAND je Item (Stueck): Einfrier-Stand | Hangar live (ESI) | "
           "Pipeline (Jobs) | Einfuegung | WIRKSAM (= max(eingefroren, "
           "Hangar+Pipeline) bei eingefrorenen Plaenen) | vom Plan verbraucht")
        _a("  ITEM                          EINGEFR.    HANGAR  PIPELINE  "
           "EINFUEG.   WIRKSAM  VERBRAUCHT")
        _alle = set(plan_runs) | set(_used)
        for _t in sorted(_alle, key=lambda t: -int(_wirksam.get(int(t), 0) or 0)):
            _t = int(_t)
            _a(f"  {_nm(_t)[:28]:<28} {_z(_fz_stock.get(_t)):>9} {_z(_hangar.get(_t)):>9} "
               f"{_z(_pipe.get(_t)):>9} {_z(_manual.get(_t)):>9} "
               f"{_z(_wirksam.get(_t)):>9} {_z(_used.get(_t)):>11}")
        # VORSTUFEN-REGEL (Nutzer 28.09.2026, Phenolic: "die 4 Runs sind
        # immer noch da"): je Bau-Item mit Verbrauchern im Plan, wer es
        # verbraucht und wie weit der ist - warum die Regel griff oder nicht.
        _vd = tuple(getattr(self, "_bd_vorstufen_diag", None) or ({}, {}, {}))
        _vd_erl = {}
        for _k, _v in (_vd[0] or {}).items():
            try:
                _vd_erl[int(_k)] = int(_v or 0)
            except (TypeError, ValueError):
                continue
        _vd_fertig = {int(_k) for _k in (_vd[1] or {})}
        _vd_bm = _vd[2] or {}
        _a("")
        _a(f"VORSTUFEN-REGEL: build_mats im Plan: {len(_vd_bm)} Items, "
           f"als nicht mehr gebraucht erkannt: {len(_vd_fertig)}")
        _a("  ITEM (Plan/erledigt)  <- VERBRAUCHER (Plan/erledigt)")
        _verbr = {}
        for _c, _ms in _vd_bm.items():
            try:
                _c = int(_c)
            except (TypeError, ValueError):
                continue
            for _m in (_ms or []):
                try:
                    _verbr.setdefault(int(_m[0]), []).append(_c)
                except (TypeError, ValueError, IndexError, KeyError):
                    continue
        for _t in sorted(plan_runs, key=lambda t: -int(plan_runs.get(t) or 0)):
            _vs = [c for c in _verbr.get(int(_t), []) if c in plan_runs and c != int(_t)]
            if not _vs:
                continue
            _a(f"  {_nm(_t)[:28]:<28} {_z(plan_runs.get(_t))}/{_z(_vd_erl.get(int(_t)))}"
               f"{'  -> NICHT MEHR GEBRAUCHT' if int(_t) in _vd_fertig else ''}")
            for _c in _vs:
                _offen = _vd_erl.get(_c, 0) < int(plan_runs.get(_c) or 0)
                _a(f"      <- {_nm(_c)[:28]:<28} {_z(plan_runs.get(_c))}/{_z(_vd_erl.get(_c))}"
                   f"{'  OFFEN' if _offen else ''}")
        _a("ENDE FORTSCHRITT")
        # de_scan2: an
        # de_scan4: an
        with open(_pfad, "a", encoding="utf-8") as _fh:
            _fh.write("\n".join(_zl) + "\n")

    def _stufe_abschluss(self, tbl, kopf, status, zeilen=()):
        """Stufen-Kopf nach `stufe_status` beschriften und einfaerben
        (emm433/434, eine Stelle fuer Reprocessing und Science; die Bau-
        Stufen machen dasselbe im eigenen Block): "bereit" -> Zusatz
        "(Ready to deliver)", bleibt farbig; "erledigt" -> "(Completed)",
        Kopf und Zeilen grau, Hintergrund weg, Symbol im Disabled-Modus."""
        from ..sprache import t as _txt
        if status == "bereit":
            kopf.setText(0, kopf.text(0) + "  (" + _txt("Ready to deliver") + ")")
            kopf.setData(0, Qt.UserRole + 11, "bereit")
        elif status == "erledigt":
            kopf.setText(0, kopf.text(0) + "  (" + _txt("Completed") + ")")
            kopf.setData(0, Qt.UserRole + 11, "erledigt")
            for _c in range(tbl.columnCount()):
                kopf.setForeground(_c, QColor(theme.MUTED))
                kopf.setBackground(_c, QBrush())
            try:
                _ic = kopf.icon(0)
                if not _ic.isNull():
                    kopf.setIcon(0, QIcon(_ic.pixmap(18, QIcon.Disabled)))
            except Exception:
                pass
            for _z in (zeilen or ()):
                for _c in range(tbl.columnCount()):
                    _z.setForeground(_c, QColor(theme.MUTED))

    def _science_block(self, tbl, names, klapp_vorher):
        """Kopieren + Invention als eigene Runplaner-Bloecke (emm411, v2 emm425).

        emm425 (Nutzer: "die Job Runs und Runs/Copy stimmen nicht, nicht so
        wie ich es im Invention-Tab eingebe ... charaktere hinzuschalten wenn
        die Slots nicht reichen ... der richtig gewaehlte Decryptor als amber
        kopierbarer Knopf ... ein 4-Eck zum selber abhaken ... blauer/gruener
        Punkt sobald ESI gegenprueft"):
          * Zahlen = Invention-Karte: `_bd_invention_needs` + Regler
            (`_bd_inv_split`) + Slots; die Karte frischt den Block nach jeder
            Neuberechnung auf (`_science_block_auffrischen`) - vorher wurde er
            nur beim Runplaner-Aufbau gezeichnet und zeigte veraltete Werte.
          * Verteilung auf die Charaktere mit Haken "Copy" bzw. "Inv"
            (`bau_copy_chars` / `bau_invention_chars`) nach ihren MAXIMALEN
            Science-Slots (wie die Bau-Stufen, Entscheid Sitzung 11);
            reichen sie nicht, kommt eine zweite Auflistung ("wave 2").
          * Haken je Zeile (Schluessel "copy|cid|t1bp" / "inv|cid|t2bp",
            Charakter "char|copy|cid" / "char|inv|cid") - gespeichert wie die
            Bau-Haken, der Fehlklick-Abgleich (haken_ohne_job) prueft sie mit
            gegen ESI (Produkt-ID der Science-Jobs = Blaupause). Sie wirken
            auf KEINE Rechnung (die Schluessel stehen nicht in
            `_bd_runplan_runs_by_key`).
          * ESI-Punkt: laufender Kopier-/Invention-Job dieses Charakters =
            blauer Punkt, fertig (abholbereit) = gruener Punkt."""
        from ..sprache import t as _txt
        from PySide6.QtWidgets import QTreeWidgetItem
        from .mw_helpers import science_verteilen
        self._bd_science_names = names          # fuer _science_block_auffrischen
        needs = {int(b): i for b, i in
                 (getattr(self, "_bd_invention_needs", None) or {}).items()
                 if int((i or {}).get("attempts") or 0) > 0}
        if not needs:
            return
        split = getattr(self, "_bd_inv_split", None) or {}
        slots = int(getattr(self, "_bd_inv_slots", 10) or 10)
        aktiv = getattr(self, "_bd_active_jobs_alle", None) or {}
        checked = getattr(self, "_bd_runplan_checked", None)
        if checked is None:
            checked = set()
        dec_map = getattr(self, "_bd_decryptor_map", None) or {}
        # Namen: erst die des Plans, Luecken aus dem Namens-Cache (ohne Netz).
        _ids = set(needs) | {int(i.get("t1") or 0) for i in needs.values()}
        nm = dict(names or {})
        _fehlen = [i for i in _ids if i and not nm.get(i)]
        if _fehlen:
            try:
                nm.update(store.cached_names(_fehlen) or {})
            except Exception:
                pass

        def _name(tid):
            return str(nm.get(int(tid)) or f"#{tid}")

        try:
            _cnames = {int(c["character_id"]): c.get("character_name")
                       for c in (store.list_characters() or [])}
        except Exception:
            _cnames = {}
        _max = self.settings.get("bau_char_slots") or {}

        def _chars(key):
            """[(cid, science-slots)] der Charaktere mit diesem Haken."""
            out = []
            for c in (self.settings.get(key) or []):
                try:
                    _m = (_max.get(str(c)) or [0, 0, 0])
                    out.append((int(c), int(_m[2]) if len(_m) > 2 else 0))
                except (TypeError, ValueError):
                    continue
            return out

        def _punkt(tid, act, cname):
            """'run' / 'done' / None je ESI-Job dieses Charakters."""
            _st = None
            for j in (aktiv.get(int(tid)) or []):
                if int(j.get("activity_id") or 0) != act:
                    continue
                if cname and j.get("char") and j.get("char") != cname:
                    continue
                if j.get("status") == "ready":
                    _st = _st or "done"
                elif j.get("status") in ("active", "paused"):
                    _st = "run"
            return _st

        # GANZ OBEN (emm434, Nutzer: "Copy und Invention wuerde ich ganz nach
        # oben setzen ueber Fuel, weil das kann man direkt ganz am Anfang
        # machen"): die Koepfe kommen an Position 0 und 1 des Baums.
        _pos_sc = [0]

        def _kopf(text, key, tip):
            it = QTreeWidgetItem([text, "", "", "", "", ""])
            _f = it.font(0); _f.setBold(True); _f.setPointSize(_f.pointSize() + 2)
            it.setFont(0, _f)
            _bg = QColor(theme.VIOLET); _bg.setAlpha(38)
            for _c in range(6):
                it.setBackground(_c, QBrush(_bg))
            it.setForeground(0, QColor(theme.VIOLET))
            it.setIcon(0, icons.icon("flask", farbe=theme.VIOLET))
            it.setToolTip(0, tip)
            it.setFlags(it.flags() & ~Qt.ItemIsUserCheckable)
            tbl.insertTopLevelItem(_pos_sc[0], it)
            _pos_sc[0] += 1
            # de_scan5: aus - interner Klapp-Schluessel, nie sichtbar
            it.setData(0, Qt.UserRole + 6, "stufe|" + key)
            # de_scan5: an
            return it

        def _struck(it):
            for c in range(tbl.columnCount()):
                f = it.font(c); f.setStrikeOut(True); it.setFont(c, f)
                if it.data(c, Qt.UserRole + 5) is None:
                    it.setData(c, Qt.UserRole + 5, it.foreground(c))
                it.setForeground(c, QColor(theme.GREEN))

        def _haken(it, key):
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setData(0, Qt.UserRole + 6, key)
            if key in checked:
                it.setCheckState(0, Qt.Checked)
                _struck(it)
            else:
                it.setCheckState(0, Qt.Unchecked)

        def _char_zeile(parent, cid, welle, jobs, cap, art):
            _wsuf = f"|w{welle}" if welle > 1 else ""
            _cn = _cnames.get(int(cid)) or (str(cid) if cid else _txt(
                "no character ticked"))
            ci = QTreeWidgetItem([
                _cn + ("  ·  " + _txt("wave {n}").format(n=welle)
                       if welle > 1 else ""),
                "", _txt("{n}/{cap} slots").format(n=jobs, cap=cap), "", ""])
            ci.setForeground(0, QColor(theme.CYAN))
            if not cid:
                ci.setToolTip(0, _txt(
                    "Tick characters for „Copy“ / „Inv“ under "
                    "Build characters – then the jobs are spread over "
                    "their science slots."))
            _haken(ci, f"char|{art}|{cid}{_wsuf}")
            parent.addChild(ci)
            return ci, _wsuf, _cn

        def _knopf(text, tip, slot):
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            b.setMinimumHeight(24)
            b.setToolTip(tip)
            b.setStyleSheet(
                f"QPushButton{{background:{theme.PANEL2}; "
                f"border:1px solid {theme.AMBER_DIM}; color:{theme.AMBER}; "
                f"border-radius:5px; padding:0px 10px; font-weight:700;}}"
                f"QPushButton:hover{{border-color:{theme.AMBER}; "
                f"background:{theme.PANEL};}}")
            b.clicked.connect(slot)
            return b

        def _knopf_zeile(z, knoepfe):
            _cw = QWidget(); _cl = QHBoxLayout(_cw)
            _cl.setContentsMargins(4, 2, 4, 2); _cl.setSpacing(6)
            for _b in knoepfe:
                _cl.addWidget(_b)
            _cl.addStretch()
            _cw.adjustSize()
            _h9 = max(30, _cw.sizeHint().height() + 6)
            z.setSizeHint(2, QSize(0, _h9))
            tbl.setItemWidget(z, 2, _cw)

        # ABGELIEFERT (emm434): ESI-Jobs dieser Aktivitaet, NACH dem
        # Einfrieren gestartet (ungespeichert/nicht eingefroren: nur Haken).
        _seit_sc = None
        _pid_sc = getattr(self, "_bd_open_plan_id", None)
        if _pid_sc is not None:
            for _p_sc in (self.settings.get("bau_saved_plans") or []):
                if str(_p_sc.get("id")) == str(_pid_sc):
                    _seit_sc = (_p_sc.get("frozen") or {}).get("ts")
                    break
        _gel_sc = getattr(self, "_bd_delivered_jobs", None) or []

        def _geliefert(tid, act):
            if _seit_sc is None:
                return False
            for _j in _gel_sc:
                try:
                    if (int(_j.get("product_type_id") or 0) != int(tid)
                            or int(_j.get("activity_id") or 0) != act):
                        continue
                except (TypeError, ValueError):
                    continue
                _ts = self._iso_job_ts(_j.get("start_date"))
                if _ts is not None and float(_ts) >= float(_seit_sc):
                    return True
            return False

        def _zeilen_zustand(tid, act, cname, key):
            """offen / laeuft / bereit / erledigt einer Science-Zeile."""
            _p = _punkt(tid, act, cname)
            if _p == "run":
                return "laeuft"
            if _p == "done":
                return "bereit"
            if _geliefert(tid, act) or key in checked:
                return "erledigt"
            return "offen"

        def _abschluss(kopf, zust, zeilen):
            from .mw_helpers import stufe_status as _ss
            _st = _ss(bool(zust) and all(z != "offen" for z in zust),
                      zust.count("laeuft"), zust.count("bereit"))
            self._stufe_abschluss(tbl, kopf, _st, zeilen)
            return _st

        def _setze_punkt(z, st):
            if st == "geliefert":
                z.setIcon(0, icons.gruener_punkt())
                z.setToolTip(0, _txt("ESI: this job is delivered."))
            if st == "done":
                z.setIcon(0, icons.gruener_punkt())
                z.setToolTip(0, _txt("ESI: this job is finished – ready "
                                     "to deliver."))
            elif st == "run":
                z.setIcon(0, icons.lauf_punkt())
                z.setToolTip(0, _txt("ESI: this job is running."))

        _sortiert = sorted(needs.items(), key=lambda kv: _name(kv[0]).lower())
        _auf = {}
        for bp, info in _sortiert:
            _auf[bp] = industry.kopien_aufteilung(
                int(info.get("attempts") or 0),
                int(info.get("runs_je_kopie") or 1), slots=slots,
                kopien=int(split.get(int(bp)) or split.get(str(bp)) or 1),
                prob=info.get("prob"))

        # ---- Kopieren: EIN Kopierjob je T1-Original -----------------------
        _k = _kopf("⚗ " + _txt("Copying") + "  ·  "
                   + _txt("science slots – runs parallel to the build"),
                   "copying",
                   _txt("Copy your T1 originals for invention. Same numbers "
                        "as the Invention tab – the slider there sets the "
                        "parallel copies."))
        _copy_auftr = [(bp, 1) for bp, _i in _sortiert if _auf[bp].get("kopien")]
        _k_zust, _k_zeilen = [], []
        _copy_chars = _chars("bau_copy_chars") or [(0, max(1, slots))]
        for cid, welle, liste in science_verteilen(_copy_auftr, _copy_chars):
            _cap = dict(_copy_chars).get(cid, 0) or max(1, slots)
            ci, _wsuf, _cn = _char_zeile(_k, cid, welle,
                                         sum(n for _b, n in liste), _cap, "copy")
            for bp, _n in liste:
                info = needs[bp]
                a = _auf[bp]
                _t1 = int(info.get("t1") or 0)
                _t1nm = _name(_t1)
                _basis1 = (_t1nm[:-len(" Blueprint")]
                           if _t1nm.endswith(" Blueprint") else _t1nm)
                _dauer = (float(info.get("cpr") or 0)
                          * a["kopien"] * a["runs_je_kopie"])
                z = QTreeWidgetItem([_t1nm, str(a["kopien"]), "",
                                     ("≈" + self._fmt_dur(_dauer)) if _dauer else "",
                                     _txt("Copy job"), ""])
                z.setTextAlignment(1, Qt.AlignCenter)
                # Rechtsklick/Strg+C: Basis OHNE " Blueprint" - _bp_name_for
                # haengt das Suffix selbst an (sonst stuende es doppelt da).
                z.setData(0, Qt.UserRole + 8, _basis1)
                z.setData(0, Qt.UserRole + 7, 1)
                _haken(z, f"copy|{cid}|{_t1}{_wsuf}")
                ci.addChild(z)
                _setze_punkt(z, _punkt(_t1, 5, _cnames.get(int(cid))))
                # de_scan6: aus - interner Haken-Schluessel, nie sichtbar
                _zz = _zeilen_zustand(_t1, 5, _cnames.get(int(cid)),
                                      f"copy|{cid}|{_t1}{_wsuf}")
                # de_scan6: an
                if _zz == "erledigt" and _geliefert(_t1, 5):
                    _setze_punkt(z, "geliefert")
                _k_zust.append(_zz)
                _k_zeilen += [z, ci]
                # de_scan6: aus - "Job Runs"/"Runs/Copy" sind die EVE-
                # Feldnamen im Kopierfenster und bleiben in jeder
                # Sprachfassung englisch (wie in der Invention-Karte).
                _knopf_zeile(z, ([
                    _knopf(_txt("Copy T1 Blueprint"),
                           _txt("Click copies {name} – search for it in the "
                                "industry window.").format(name=_t1nm),
                           lambda _c=False, _v=_t1nm: self._copy_bp_name_value(_v))]
                    if _t1nm and not _t1nm.startswith("#") else []) + [
                    _knopf(f"Job Runs: {a['kopien']}",
                           _txt("Click copies {r} – paste it into the "
                                "field in game.").format(r=a["kopien"]),
                           lambda _c=False, _v=a["kopien"], _n=_t1nm:
                           self._copy_runs_value(_v, _n)),
                    _knopf(f"Runs/Copy: {a['runs_je_kopie']}",
                           _txt("Click copies {r} – paste it into the "
                                "field in game.").format(r=a["runs_je_kopie"]),
                           lambda _c=False, _v=a["runs_je_kopie"], _n=_t1nm:
                           self._copy_runs_value(_v, _n))])
                # de_scan6: an
            # Charakterzeilen ZU wie bei den Bau-Stufen; der Nutzer-Klapp
            # gewinnt (emm400-Gedaechtnis).
            ci.setExpanded(bool(klapp_vorher.get(f"char|copy|{cid}{_wsuf}", False)))
        _k_st = _abschluss(_k, _k_zust, _k_zeilen)
        _k.setExpanded(bool(klapp_vorher.get("stufe|copying",
                                             _k_st != "erledigt")))

        # ---- Invention: je Kopie ein Job, verteilt auf die Inv-Charaktere -
        _i = _kopf("⚗ " + _txt("Invention") + "  ·  "
                   + _txt("science slots – runs parallel to the build"),
                   "invention",
                   _txt("Invention attempts after copying. Datacores and "
                        "decryptors are on the shopping list."))
        _inv_auftr = [(bp, int(_auf[bp].get("kopien") or 0))
                      for bp, _i2 in _sortiert if _auf[bp].get("kopien")]
        _inv_chars = _chars("bau_invention_chars") or [(0, max(1, slots))]
        _i_zust, _i_zeilen = [], []
        for cid, welle, liste in science_verteilen(_inv_auftr, _inv_chars):
            _cap = dict(_inv_chars).get(cid, 0) or max(1, slots)
            ci, _wsuf, _cn = _char_zeile(_i, cid, welle,
                                         sum(n for _b, n in liste), _cap, "inv")
            for bp, n_jobs in liste:
                info = needs[bp]
                a = _auf[bp]
                _rpk = int(a.get("runs_je_kopie") or 1)
                _dauer = float(info.get("ipa") or 0) * _rpk
                _nm2 = _name(bp)
                z = QTreeWidgetItem([
                    _nm2, str(_rpk),
                    "", ("≈" + self._fmt_dur(_dauer)) if _dauer else "",
                    _txt("{n} job(s)").format(n=n_jobs), ""])
                z.setTextAlignment(1, Qt.AlignCenter)
                z.setData(0, Qt.UserRole + 8,
                          _nm2[:-len(" Blueprint")]
                          if _nm2.endswith(" Blueprint") else _nm2)
                z.setData(0, Qt.UserRole + 7, 1)
                _haken(z, f"inv|{cid}|{bp}{_wsuf}")
                ci.addChild(z)
                _setze_punkt(z, _punkt(bp, 8, _cnames.get(int(cid))))
                # de_scan6: aus - interner Haken-Schluessel, nie sichtbar
                _zz = _zeilen_zustand(bp, 8, _cnames.get(int(cid)),
                                      f"inv|{cid}|{bp}{_wsuf}")
                # de_scan6: an
                if _zz == "erledigt" and _geliefert(bp, 8):
                    _setze_punkt(z, "geliefert")
                _i_zust.append(_zz)
                _i_zeilen += [z, ci]
                # T1-BLAUPAUSE ALS KOPIER-KNOPF (emm435, Nutzer: "es gibt
                # keinen amber Copy-Knopf, um den Blueprint zu holen, den ich
                # inventen moechte"): ins Invention-Fenster kommt die T1-Kopie.
                _t1_inv = _name(int(info.get("t1") or 0)) if info.get("t1") else ""
                _kn = []
                if _t1_inv and not _t1_inv.startswith("#"):
                    _kn.append(_knopf(
                        _txt("Copy T1 Blueprint"),
                        _txt("Click copies {name} – search for it in the "
                             "industry window.").format(name=_t1_inv),
                        lambda _c=False, _v=_t1_inv: self._copy_bp_name_value(_v)))
                _kn += [_knopf(f"{n_jobs}× {_rpk}",
                              _txt("{n} invention job(s) with {r} runs each "
                                   "– click copies {r}.").format(
                                       n=n_jobs, r=_rpk),
                              lambda _c=False, _v=_rpk, _n=_nm2:
                              self._copy_runs_value(_v, _n))]
                # DECRYPTOR DER KARTE als Kopier-Knopf (Nutzer emm425).
                _dec = dec_map.get(int(bp)) or dec_map.get(str(bp))
                if _dec and _dec != KEIN_DECRYPTOR:
                    _dec_nm = str(_dec)
                    # de_scan6: aus - EVE-Itemname ("Accelerant Decryptor"),
                    # in jeder Sprachfassung gleich (wie in der Karte)
                    if not _dec_nm.endswith("Decryptor"):
                        _dec_nm += " Decryptor"
                    # de_scan6: an
                    _kn.append(_knopf(
                        _dec_nm,
                        _txt("Click copies the decryptor name – the one "
                             "chosen on the Invention tab."),
                        lambda _c=False, _v=_dec_nm: self._copy_bp_name_value(_v)))
                _knopf_zeile(z, _kn)
            ci.setExpanded(bool(klapp_vorher.get(f"char|inv|{cid}{_wsuf}", False)))
        _i_st = _abschluss(_i, _i_zust, _i_zeilen)
        _i.setExpanded(bool(klapp_vorher.get("stufe|invention",
                                             _i_st != "erledigt")))

    def _science_block_auffrischen(self):
        """Science-Bloecke im offenen Runplaner neu zeichnen (emm425), damit
        sie der Invention-Karte folgen (Decryptor, Regler, Slots) - ohne den
        ganzen Runplaner neu zu bauen. Entprellt ueber `_science_timer`."""
        tbl = getattr(self, "_sched_tree_ref", None)
        if tbl is None:
            return
        try:
            _klapp = dict(getattr(self, "_bd_sched_klapp", None) or {})
            tbl.blockSignals(True)
            try:
                for _i in reversed(range(tbl.topLevelItemCount())):
                    _it = tbl.topLevelItem(_i)
                    # de_scan5: aus - interne Klapp-Schluessel, nie sichtbar
                    if str(_it.data(0, Qt.UserRole + 6) or "") in (
                            "stufe|copying", "stufe|invention"):
                        # de_scan5: an
                        _k_alt = str(_it.data(0, Qt.UserRole + 6))
                        _klapp.setdefault(_k_alt, _it.isExpanded())
                        tbl.takeTopLevelItem(_i)
                self._science_block(tbl, getattr(self, "_bd_science_names", None)
                                    or {}, _klapp)
            finally:
                tbl.blockSignals(False)
        except RuntimeError:
            pass                      # Baum schon abgeraeumt (Fenster zu)
        except Exception as _e:
            self._log_exception("Runplaner: Science auffrischen", str(_e))

    def _science_spaeter(self):
        """Entprellt: die Karte rechnet beim Aufbau/Auto-Decryptor oft
        mehrmals hintereinander - der Block wird nur EINMAL neu gezeichnet."""
        _tm = getattr(self, "_science_timer", None)
        if _tm is None:
            _tm = self._science_timer = QTimer()
            _tm.setSingleShot(True)
            _tm.setInterval(150)
            _tm.timeout.connect(lambda: self._science_block_auffrischen())
        _tm.start()

    def _fill_bauplan_schedule(self, plan, names, type_id, qty, hdr, sub, tbl, bp_tbl=None,
                               bp_warn_lbl=None):
        from ..sprache import t as _txt   # `t` ist hier lokal belegt
        from PySide6.QtWidgets import QTableWidgetItem
        mfg_sel = set(self.settings.get("bau_build_chars", []) or [])
        react_sel = set(self.settings.get("bau_reaction_chars", []) or [])
        all_sel = mfg_sel | react_sel
        if not all_sel:
            hdr.setText(_txt("Tick characters in the setup (\u201eFor building\u201c / "
                             "\u201eFor reactions\u201c) + \u201eLoad skills\u201c, then the run "
                             "planner appears here."))
            sub.setText(""); tbl.clear()
            # Kalender-Zeit trotzdem aktuell halten (seriell, da keine Parallelität).
            self._bd_last_sched_seconds = self._serial_plan_seconds(plan, type_id)
            return
        recipes = getattr(self, "_bd_recipes", None)
        if not plan or not recipes:
            tbl.clear()
            self._bd_last_sched_seconds = self._serial_plan_seconds(plan, type_id)
            return
        slots_map = self.settings.get("bau_char_slots", {}) or {}
        free_map = self.settings.get("bau_char_free", {}) or {}
        skills_map = self.settings.get("bau_char_skills", {}) or {}
        cmap = {c["character_id"]: (c.get("character_name") or str(c["character_id"]))
                for c in store.list_characters()}
        sched_chars = []
        for cid in all_sel:
            mx = slots_map.get(str(cid)) or [1, 1]
            fr = free_map.get(str(cid))
            # BESETZTE SLOTS WERDEN IGNORIERT (Nutzer-Entscheid Sitzung 11:
            # "die besetzten slots sollen ignoriert werden").
            #
            # Vorher wurden hier die FREIEN Slots bevorzugt - geplant wurde
            # also
            # mit den FREIEN Slots vom letzten "Skills laden". Das hatte eine
            # Folge, die niemand wollte: `elig()` in schedule_build wirft
            # jeden Charakter mit weniger als EINEM Slot komplett aus der
            # Stufe. Wer gerade baute, hatte 0 freie Fertigungs-Slots und war
            # damit im Plan nicht mehr vorhanden - je weiter der Nutzer den
            # Plan abarbeitete, desto weniger Charaktere benutzte der Planer.
            # Sein Befund: drei Bau-Charaktere angekreuzt, alle neun
            # Komponenten landeten auf EINEM (nachgerechnet: 9,4 Tage, sein
            # Bildschirm zeigte 9 T 10 h 34 m - derselbe Fall).
            #
            # Der Plan laeuft ueber TAGE; die jetzt belegten Slots sind
            # laengst wieder frei, wenn die Stufe drankommt. Deshalb jetzt
            # immer das Maximum laut Skills. Die freien Slots gehen NICHT
            # verloren, sie stehen weiter im Tooltip der Zeile (Regel 6) -
            # sie steuern nur die Planung nicht mehr.
            sl = mx
            sk = skills_map.get(str(cid), {}) or {}
            # Skill-Keys als int normalisieren (gespeichert evtl. als str) – für den
            # Science-Skill-Lookup pro Item.
            sk_int = {}
            for _k, _v in sk.items():
                try:
                    sk_int[int(_k)] = int(_v or 0)
                except (TypeError, ValueError):
                    pass
            sched_chars.append({"id": cid, "name": cmap.get(cid, str(cid)),
                                "mfg_slots": sl[0], "reaction_slots": sl[1],
                                # MAXIMUM laut Skills mitfuehren (Sitzung 9).
                                # Seit Sitzung 11 ist `sl` selbst schon das
                                # Maximum - die Felder bleiben trotzdem, weil
                                # Anzeige und Rechnung getrennt lesbar sein
                                # sollen und _transform_schedule_result sie
                                # weiterreicht.
                                "mfg_slots_max": mx[0],
                                "reaction_slots_max": mx[1],
                                # NUR FUER DIE ANZEIGE: was war beim letzten
                                # "Skills laden" frei? Steuert nichts mehr.
                                "frei_slots": tuple(fr) if fr else (),
                                "can_mfg": cid in mfg_sel, "can_react": cid in react_sel,
                                "mfg_time": (industry.skill_time_factor(sk, False)
                                            * self._char_implant_mfg_mult(cid)),
                                "react_time": industry.skill_time_factor(sk, True),
                                "all_skills": sk_int})
        # Hinweis, falls Reaktions-Chars gewählt sind, aber die gespeicherten Skills
        # den Reactions-Skill (45746) noch nicht kennen (z.B. nach einem Update mit
        # neuer Skill-ID). Dann fehlt der Reaktions-Zeitbonus -> Zeiten zu lang.
        self._bd_react_skill_missing = False
        if react_sel:
            # SCHLUESSEL-TYP IST NICHT VERLASSBAR (Nutzer-Befund Sitzung 9:
            # "ich habe auf Skills laden gedrueckt und die Warnung
            # verschwindet nicht"). Frisch von ESI geladen sind die
            # Skill-IDs INTs, nach einem Neustart aus der JSON-Datei
            # STRINGS. Die Pruefung verglich nur gegen str(45746) - direkt
            # nach "Skills laden" fand sie den Skill also NIE und die
            # Warnung blieb stehen, obwohl alles geladen war. Genau
            # deshalb normalisiert der Code ein paar Zeilen weiter oben
            # ebenfalls auf int; hier fehlte es.
            def _hat_react(_cid):
                _sk = skills_map.get(str(_cid)) or skills_map.get(_cid) or {}
                for _k in _sk:
                    try:
                        if int(_k) == 45746:
                            return True
                    except (TypeError, ValueError):
                        continue
                return False
            if not any(_hat_react(cid) for cid in react_sel):
                self._bd_react_skill_missing = True
        te = (getattr(self, "_bd_opts", None) or {}).get("te_factor", 1.0)
        _groups = getattr(self, "_bd_groups", {}) or {}
        _mfg_struct = getattr(self, "_bd_mfg_struct", None)
        _react_struct = getattr(self, "_bd_react_struct", None)
        _sci_map = industry.bp_science_skills_map()   # bp_id -> set(science_skill_id)
        # Flag: fehlen die Science-Skill-Daten ganz (alte SDE ohne die neue Tabelle)?
        # Dann fehlt der item-spezifische Zeitbonus -> Fertigungszeiten etwas zu lang.
        self._bd_science_data_missing = not _sci_map
        # Stufen-Map (1=Intermediate, 2=Composite) - jetzt schon gebraucht, um
        # jeden Reaktions-Job mit seiner Stufe zu taggen (für die zwei
        # getrennten, nacheinander laufenden Reaktions-Phasen im Scheduler).
        try:
            _stage_map_rp = industry.reaction_stage_map(self._bd_recipes)
        except Exception:
            _stage_map_rp = {}
        jobs = []
        _enden_jobs = self._bd_enden(type_id, recipes)   # Buendel: alle Enden
        # ENDE, DAS EIN ANDERES ENDE BRAUCHT (emm432): laeuft in der Stufe
        # davor; die Zeile sagt, wie viel davon Endprodukt bleibt.
        from .mw_helpers import enden_als_zutat as _eaz
        _zutat_enden = _eaz(_enden_jobs, plan.get("build_runs") or {},
                            recipes.product_to_bp,
                            getattr(recipes, "bp_materials", None) or {})
        _buendel_qty = industry.buendel_enden(recipes)
        self._bd_ende_als_zutat = {int(_zt): int(_buendel_qty.get(_zt, 0) or 0)
                                   for _zt in _zutat_enden}
        _enden_jobs = set(_enden_jobs) - _zutat_enden
        if _zutat_enden:
            # HAKEN ZIEHEN MIT (emm432): Zeilen-Haken und erledigte Runs, die
            # noch auf der alten End-Stufe stehen, gehoeren jetzt zur
            # Komponenten-Stufe.
            from .mw_helpers import haken_stufe_umziehen as _hsu
            for _hattr in ("_bd_runplan_checked", "_bd_runplan_ts",
                           "_bd_runplan_erledigt", "_bd_runplan_erledigt_ts"):
                _hval = getattr(self, _hattr, None)
                if _hval:
                    _hneu = _hsu(_hval, _zutat_enden)
                    if isinstance(_hval, set):
                        _hval.clear()
                        _hval.update(_hneu)
                    else:
                        _hval.clear()
                        _hval.update(_hneu)
        for _tid, runs in plan.get("build_runs", {}).items():
            if runs < 1:
                continue
            bp = recipes.product_to_bp.get(_tid)
            if not bp:
                continue
            bp_id, activity, _oq = bp
            base_t = recipes.activity_time.get((bp_id, activity), 0) or 0
            _sci = _sci_map.get(bp_id, set())
            # STRUKTUR JE STUFE (Sitzung 9, Simurgh): vorher bekam JEDER
            # Fertigungs-Job die Komponenten-Struktur - auch das Endprodukt.
            _s_item = self._bau_struct_fuer_item(
                _tid, recipes.reaction_products, _stage_map_rp, type_id)
            _tef = self._bau_category_te_factor(
                _tid, _groups, recipes.reaction_products, type_id,
                mfg_struct=_s_item or _mfg_struct,
                react_struct=_s_item or _react_struct)
            # WEG A: der Job heisst nach dem, was er baut - "Unrefined Hexite",
            # nicht "Hexite" (Nutzer 19.09.2026: "erst muss man Unrefined
            # Hexite bauen, danach reprocessen"). Eigene Stufe "unrefined".
            _is_unref = _tid in (getattr(self, "_bd_unrefined", None) or {})
            jobs.append({"tid": _tid,
                         "name": self._bp_basisname(_tid, names.get(_tid, f"#{_tid}")),
                         "runs": runs,
                         "activity": activity, "base_time": base_t,
                         "is_unrefined": _is_unref,
                         "is_end": (_tid in _enden_jobs), "bp_id": bp_id,
                         "is_fuel": self._ist_fuel_block(_tid, _groups,
                                                         recipes.reaction_products),
                         "sci_skills": _sci,
                         "te_factor": _tef,
                         "reaction_tier": (_stage_map_rp.get(_tid, 2)
                                          if activity == industry.REACTION else None)})
        if bp_tbl is not None:
            try:
                # Für den Blueprints-Tab NICHT den kostenoptimierten Plan nehmen
                # (der zeigt nur, was gerade gekauft statt gebaut wird), und auch
                # NICHT production_plan(force_build=True) - das kann trotz "force"
                # noch einzelne Items als "kaufen" behandeln (z.B. wenn irgendein
                # Unter-Material weder bau- noch bepreisbar ist - eine
                # Sicherheitsbremse dort, die Vorrang vor "force" hat und dadurch
                # ganze Intermediate-Reaktionsketten aus der Liste kippen konnte).
                # Stattdessen: reiner Struktur-Durchlauf (full_build_chain), der
                # jedes Item mit eigenem Rezept bedingungslos "baut", komplett
                # unabhängig von Preisen - damit ist wirklich die KOMPLETTE
                # Rezept-Kette sichtbar. Der Runplaner selbst nutzt weiterhin die
                # echten, kostenoptimierten "jobs" oben - hier geht's nur um die
                # Übersichts-Tabelle.
                _force_opts = dict(getattr(self, "_bd_opts", None) or {})
                _bp_build_runs = industry.full_build_chain(
                    type_id, qty, recipes, _force_opts)
                # NAMEN NACHLADEN (Nutzer: "sind noch Zahlen statt Item-
                # namen"). `names` wird nur fuer PLAN-Items aufgeloest
                # (build_runs/buy/stock_used). full_build_chain enthaelt aber
                # auch Stufen, die der Plan gar nicht anfasst - deren IDs
                # blieben als "#17769" stehen. Ein Abruf fuer alle fehlenden
                # zusammen, nicht je Zeile.
                _bp_miss = [_i for _i in _bp_build_runs if _i not in names]
                if _bp_miss:
                    try:
                        names.update(esi.resolve_names(_bp_miss))
                    except Exception as _nm_err:
                        # Nicht still schlucken - sonst sucht man die "#"-Namen
                        # spaeter wieder im Rechenweg statt im Netz.
                        self._log_exception("Blueprints-Tab: Namen", str(_nm_err))
                _bp_jobs = []
                for _tid, runs in _bp_build_runs.items():
                    if runs < 1:
                        continue
                    bp = recipes.product_to_bp.get(_tid)
                    if not bp:
                        continue
                    bp_id, activity, _oq = bp
                    base_t = recipes.activity_time.get((bp_id, activity), 0) or 0
                    _sci = _sci_map.get(bp_id, set())
                    _s_item = self._bau_struct_fuer_item(
                        _tid, recipes.reaction_products, _stage_map_rp, type_id)
                    _tef = self._bau_category_te_factor(
                        _tid, _groups, recipes.reaction_products, type_id,
                        mfg_struct=_s_item or _mfg_struct,
                        react_struct=_s_item or _react_struct)
                    _bp_jobs.append({"tid": _tid, "name": names.get(_tid, f"#{_tid}"),
                                     "runs": runs, "activity": activity,
                                     "base_time": base_t, "is_end": (_tid in _enden_jobs),
                                     "bp_id": bp_id, "sci_skills": _sci,
                                     "is_fuel": self._ist_fuel_block(
                                         _tid, _groups, recipes.reaction_products),
                                     "te_factor": _tef,
                                     "reaction_tier": (_stage_map_rp.get(_tid, 2)
                                                       if activity == industry.REACTION
                                                       else None)})
                (_n_missing, _n_low, _n_missing_by_stage,
                 _n_low_by_stage) = self._fill_blueprint_tab(_bp_jobs, sched_chars,
                                                             recipes, bp_tbl)
            except Exception:
                # NICHT MEHR STUMM SCHLUCKEN. Genau dieses except hat den
                # Blueprints-Tab kaputt aussehen lassen, ohne dass irgendwo
                # etwas davon stand: die Fuell-Funktion brach mittendrin ab,
                # der Tab blieb halb leer, und der Nutzer fragte zu Recht
                # "welches Konsolenfenster?". Ab jetzt landet der Traceback
                # im Fehlerprotokoll (s. main.py) und ein Hinweis im Tab.
                import traceback as _tb
                _err = _tb.format_exc()
                try:
                    self._log_exception("Blueprints-Tab", _err)
                except Exception:
                    pass
                if bp_warn_lbl is not None:
                    bp_warn_lbl.setText(_txt(
                        "\u26a0 The Blueprints tab could not be built completely. "
                        "Details are in fehler.log next to the application."))
                    bp_warn_lbl.setStyleSheet(f"color:{theme.RED};")
                _n_missing, _n_low = 0, 0
                _n_missing_by_stage, _n_low_by_stage = {}, {}
            if bp_warn_lbl is not None:
                # Sitzung 17: ALLE Stufen, nicht nur drei (s. _bp_stufen_liste).
                _breakdown = self._bp_stufen_liste
                # Fehlt NUR das Endprodukt (keine Komponenten/Reaktionen) -> meist
                # normal, das T2-BPC wird ja meist erst NACH der Planung per
                # Invention erzeugt, nicht vorher schon besessen. Dezenter Hinweis
                # statt Alarm-Rot. Fehlen aber auch Komponenten/Reaktionen -> das
                # sind echte Engpässe, die man vor dem Bauen beheben muss -> Alarm.
                # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                _only_end_missing = (_n_missing and set(_n_missing_by_stage) <= {"Endprodukt"}
                # de_scan4: an
                                     and not _n_low_by_stage)
                if _n_missing and not _only_end_missing:
                    _word = (t("\u26a0 {n} item missing completely:") if _n_missing == 1
                             else t("\u26a0 {n} items missing completely:")).format(n=_n_missing)
                    _lines = _breakdown(_n_missing_by_stage)
                    # NICHT `_txt` NENNEN (Absturz-Fund Sitzung 14): das ist
                    # in dieser Funktion die UEBERSETZUNGSFUNKTION
                    # (`from ..sprache import t as _txt`, Zeile oben). Die
                    # Zuweisung machte daraus einen String - jeder spaetere
                    # `_txt(...)`-Aufruf riss den Bauplan mit
                    # "TypeError: 'str' object is not callable" ab. Der
                    # Nutzer stand mitten im Bauen davor, ausgeloest vom
                    # 10-Minuten-ESI-Lauf.
                    _warn_html = (_word + "<br>" + "<br>".join(_lines))
                    if _n_low:
                        _warn_html += ("<br>" + t("Also {n} too few: ").format(n=_n_low)
                                       + ", ".join(_breakdown(_n_low_by_stage)))
                    _warn_html += ("<br><span style='font-size:11px;'>"
                                   + t("Details in the Blueprints tab.")
                                   + "</span>")
                    bp_warn_lbl.setText(_warn_html)
                    bp_warn_lbl.setStyleSheet(
                        f"background:rgba(226,54,54,0.12); color:{theme.RED}; "
                        f"border:1px solid {theme.RED}; border-radius:6px; "
                        f"padding:6px 10px; font-weight:600;")
                    bp_warn_lbl.setVisible(True)
                elif _only_end_missing:
                    bp_warn_lbl.setText(_txt(
                        "\u2139 End product blueprint ({n}) still missing - normal if you "
                        "create the T2 BPC via invention only AFTER planning."
                    # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                    ).format(n=_n_missing_by_stage.get('Endprodukt', _n_missing)))
                    # de_scan4: an
                    bp_warn_lbl.setStyleSheet(
                        f"background:rgba(107,114,128,0.12); color:{theme.MUTED}; "
                        f"border:1px solid {theme.BORDER}; border-radius:6px; "
                        f"padding:6px 10px;")
                    bp_warn_lbl.setVisible(True)
                elif _n_low:
                    bp_warn_lbl.setText(
                        _txt("\u26a0 {n} item(s) have too few blueprint copies for the "
                             "fastest possible build:<br>").format(n=_n_low)
                        + "<br>".join(_breakdown(_n_low_by_stage))
                        + "<br><span style='font-size:11px;'>"
                        + _txt("Details in the Blueprints tab.") + "</span>")
                    bp_warn_lbl.setStyleSheet(
                        f"background:rgba(224,177,44,0.12); color:{theme.AMBER}; "
                        f"border:1px solid {theme.AMBER}; border-radius:6px; "
                        f"padding:6px 10px; font-weight:600;")
                    bp_warn_lbl.setVisible(True)
                else:
                    bp_warn_lbl.setVisible(False)
        if not jobs:
            hdr.setText(_txt("Nothing to build yourself (all bought?).")); sub.setText("")
            tbl.clear()
            return
        bpset = getattr(self, "_bd_bp", None) or {}

        def _cap(key, default=1):
            d = bpset.get(key) or {}
            return int(d.get("copies", default) or default)
        # Kapazitäts-Anzeige je Stufe (Kopien × Runs vs. größter Job) aktualisieren
        max_runs = {"end": 0, "component": 0, "reaction": 0}
        for j in jobs:
            st = ("reaction" if j["activity"] == industry.REACTION
                  else "end" if j.get("is_end") else "component")
            max_runs[st] = max(max_runs[st], int(j["runs"]))
        for key, lbl in (getattr(self, "_bd_bp_widgets", {}) or {}).items():
            d = bpset.get(key) or {}
            need = max_runs.get(key, 0)
            capw = lbl.get("cap")
            if not capw:
                continue
            if d.get("bpo"):
                capw.setText(_txt("\u221e \u00b7 largest job {need}").format(need=need))
                capw.setStyleSheet(f"color:{theme.GREEN};")
            else:
                cap = int(d.get("copies", 1)) * int(d.get("runs", 1))
                ok = cap >= need
                capw.setText(_txt("Cap. {cap} \u00b7 largest job {need}").format(cap=cap, need=need)
                             + ("" if ok else _txt(" \u26a0 not enough")))
                capw.setStyleSheet(f"color:{theme.GREEN if ok else theme.AMBER};")
        # „Selber aufteilen“: nur alle Runs je Item listen, ohne Charakter-Zuteilung.
        if bpset.get("manual"):
            self._fill_schedule_manual(jobs, recipes, names, hdr, sub, tbl, plan=plan)
            # Ohne Char-Zuteilung gibt es keine Parallelität -> serielle Zeit merken
            # (sonst behält der Kalender eine veraltete Zeit).
            self._bd_last_sched_seconds = self._serial_plan_seconds(plan, type_id)
            return
        res = industry.schedule_build(
            jobs, sched_chars, te_factor=te,
            mfg_bp=_cap("component"), react_bp=_cap("reaction"), end_bp=_cap("end"),
            # ZIELZEIT JE STUFE (Nutzer 24.09.2026) - siehe
            # `_runplan_ziel_sekunden`. Leeres Ergebnis = nur straffen.
            stage_ziel=self._runplan_ziel_sekunden(),
            fuel_ids={j["tid"] for j in jobs if j.get("is_fuel")},
            per_item_cap=self._resolve_per_item_bp_cap(),
            # RUNS JE JOB DECKELN (Nutzer 19.09.2026: "17 Stueck mit einem
            # Blueprint ... gibts maximal 10 runs"): BPC-Runs / SDE-Limit.
            per_item_runs_cap=self._resolve_per_item_runs_cap(type_id))
        # PLANER-DIAGNOSE (Nutzer 25.09.2026: "ich habe 19 Blueprints und
        # nicht nur 11, as fast as possible nutzt nicht alle" und "stelle ich
        # 23 h ein, dauert die Reaktion 15 h 26 m"). Beides laesst sich von
        # aussen nicht nachstellen, solange die EINGABEN des Planers nicht
        # sichtbar sind - genau die schreibt diese Datei, roh und
        # unkommentiert. Dieselbe Bauart wie `unrefined_diagnose.txt`:
        # schreiben, nie darauf verlassen (jede Zeile in try/except).
        try:
            self._planer_diagnose_schreiben(jobs, sched_chars, te, res,
                                            names, type_id)
        except Exception as _pd:
            self._log_exception("Planer-Diagnose", str(_pd))
        # FORTSCHRITT AUS ESI-JOBS (nur eingefrorene Plaene, Nutzer-Spez
        # Punkt 2): gelieferte Runs seit dem Einfrieren je Item aufsummieren;
        # deckt die Summe die Plan-Runs, wird die Zeile automatisch abgehakt -
        # ueber DENSELBEN checked_runplan-Mechanismus wie die Hand-Haekchen
        # (EINE Wahrheit; nicht loeschen, sonst verliert man die Uebersicht,
        # was lief). _bd_runplan_auto traegt nur den Tooltip-Zusatz und wird
        # hier bei JEDEM Aufbau neu bestimmt (transient, nichts Gespeichertes).
        self._bd_runplan_auto = {}
        self._bd_runplan_delivered = {}
        # NUR DAS SICHER ZUGEORDNETE (Befund 21.09.2026): dieselbe Zahl
        # steuerte bisher die ANZEIGE und den RESTBEDARF. Die beiden haben
        # voellig verschiedene Fehlerkosten - eine falsch eingefaerbte Zeile
        # kostet nichts, eine zu kleine Einkaufsliste kostet Material.
        # Deshalb zwei Karten: `_bd_runplan_delivered` faerbt weiter (darf
        # raten), `_bd_runplan_delivered_sicher` speist `_restbedarf_jetzt`
        # und `_fehlbedarf_jetzt` (darf NICHT raten).
        self._bd_runplan_delivered_sicher = {}
        # OFFENE ZUORDNUNGS-FRAGEN (Stufe C, Teil 2) - transient wie
        # `_bd_runplan_auto`, entsteht bei jedem Aufbau neu.
        self._bd_job_offen = []
        self._bd_job_prio = []
        self._bd_runplan_runs_by_key = {}
        # WAS IST SCHON ERLEDIGT? Kopie der gemerkten Runs je (Stufe, Item);
        # sie wird beim Bauen der Zeilen aufgebraucht (s. `_k_erl` unten).
        import time as _zeit_mod
        _rest_erl = dict(getattr(self, "_bd_runplan_erledigt", None) or {})
        # Fremde Reservierungen EINMAL je Aufbau (fuer die Job-Zuordnung).
        _fremd_res = self._fremde_reservierungen(
            self.settings, getattr(self, "_bd_open_plan_id", None))
        # Der EIGENE Anspruch: dieselbe Karte, die beim Speichern geschrieben
        # wird. Beansprucht dieser Plan das Item auch, gibt es keine Aussage -
        # dann bleibt der Lauf-Punkt stehen (Regel 3: lieber einer zu viel).
        try:
            _eigene_res = self._plan_reserve_map(
                (getattr(self, "_bd_plan_ref", None) or {}).get("plan") or {})
        except Exception:
            _eigene_res = {}
        _frz_sched = getattr(self, "_bd_frozen", None)
        if _frz_sched and _frz_sched.get("plan_snapshot") and _frz_sched.get("ts"):
            _auto_keys, _auto_runs = self._frozen_auto_checked(
                getattr(self, "_bd_delivered_jobs", None) or [],
                res["assignments"], float(_frz_sched["ts"]))
            # Geliefert-Stand JE ITEM auch fuer teilweise gelieferte merken -
            # der Nutzer will sehen "ESI hat 12 von 24 Runs gesehen", nicht
            # erst beim Vollstand ein Zeichen bekommen (Sitzung 8).
            # STUFE B (21.09.2026): erst die BELEGTE Zuordnung, dann der Rest.
            #
            # Ein Job, den ein Klick dieses Plans belegt, gehoert ihm - und
            # zwar dauerhaft (`store.job_zuordnung_setzen` laesst eine
            # bestehende Zuordnung stehen). Damit wandert Fortschritt nicht
            # mehr zwischen Plaenen, die dasselbe Zwischenprodukt bauen.
            #
            # Das ERSETZT die Raterei nicht, es geht ihr VOR: was kein Klick
            # belegt, laeuft weiter durch `_frozen_auto_checked` und wird
            # fuer die Materialrechnung durch `delivered_sicher` gefiltert.
            try:
                self._job_zuordnung_nachfuehren(res["assignments"],
                                                float(_frz_sched["ts"]))
                # Nach dem Zuordnen: der Runplaner sieht nur noch die
                # laufenden Jobs DIESES Plans (Nutzer 28.09.2026).
                self._aktive_jobs_filtern()
                # NAMEN AUS DEM PARAMETER `names` (s. der Hinweis weiter
                # oben: `_bd_names` gibt es hier nicht) - im Frage-Dialog
                # soll das Item stehen, nicht seine Typ-Nummer.
                for _of in (getattr(self, "_bd_job_offen", None) or []):
                    _of["name"] = str((names or {}).get(_of["type_id"])
                                      or _of["type_id"])
                self._jobfrage_knopf_auffrischen()
            except Exception as _jz:
                # Zuordnen ist eine VERBESSERUNG, kein Muss: faellt sie aus,
                # gilt exakt das bisherige Verhalten (Regel 3).
                self._log_exception("Job-Zuordnung", str(_jz))
            self._bd_runplan_delivered = dict(_auto_runs or {})
            # Die sichere Karte: Deckel auf die Plan-Runs, und umstrittene
            # Items (ein anderer gespeicherter Plan beansprucht sie auch)
            # zaehlen gar nicht. s. mw_helpers.delivered_sicher.
            try:
                _plan_runs_s = {}
                for _a_s in (res["assignments"] or []):
                    _t_s = int(_a_s["tid"])
                    _plan_runs_s[_t_s] = (_plan_runs_s.get(_t_s, 0)
                                          + int(_a_s.get("runs") or 0))
                from .mw_helpers import delivered_sicher as _mwh_sicher
                # BELEGTE RUNS (Stufe B): Jobs, die MIR gehoeren, weil ich
                # ihre Zeile angeklickt habe - und die ESI als geliefert
                # meldet. Beides muss zusammenkommen: die Zuordnung sagt
                # "wem", ESI sagt "ob ueberhaupt". Ein im Spiel abgebrochener
                # Job faellt aus der Liste und zaehlt damit von selbst nicht
                # mehr (Skizze 2.4 - die Tabelle ist ein Adressbuch, kein
                # Fortschrittsspeicher).
                _belegt_s = {}
                try:
                    _zu_s = store.job_zuordnung_fuer_plan(
                        getattr(self, "_bd_open_plan_id", None))
                    if _zu_s:
                        for _dj in (getattr(self, "_bd_delivered_jobs",
                                            None) or []):
                            _jid_s = _dj.get("job_id")
                            if _jid_s is None or int(_jid_s) not in _zu_s:
                                continue
                            # NUR seit dem Einfrieren (dieselbe Grenze wie
                            # `_frozen_auto_checked`): ein Job aus einem
                            # FRUEHEREN Durchlauf desselben Plans ist kein
                            # Fortschritt dieses Durchlaufs - sonst schrumpfte
                            # die Einkaufsliste nach dem Neu-Einfrieren um
                            # Material, das laengst verbaut ist (Regel 3).
                            _fts_b = self._iso_job_ts(
                                _dj.get("completed_date"))
                            if _fts_b is None or _fts_b < float(
                                    _frz_sched["ts"]):
                                continue
                            _t_b = int(_dj.get("product_type_id") or 0)
                            if _t_b:
                                _belegt_s[_t_b] = (_belegt_s.get(_t_b, 0)
                                                   + int(_dj.get("runs") or 0))
                except Exception as _be:
                    _belegt_s = {}
                    self._log_exception("Belegte Runs", str(_be))
                self._bd_runplan_delivered_sicher = _mwh_sicher(
                    self._bd_runplan_delivered, _plan_runs_s,
                    self._umstrittene_items(
                        self.settings,
                        getattr(self, "_bd_open_plan_id", None)),
                    _belegt_s)
                # EINE KARTE (Stufe C, Abschluss - Nutzer 26.09.2026 "machen
                # okey"): die Anzeige liest ab jetzt DIESELBE sichere Karte
                # wie die Einkaufsliste. Bis hierher durfte sie raten
                # (Befund 21.09.2026) - seit Klick, Eindeutigkeit, Zeitregel
                # und Frage-Dialog bleibt nur noch der Job ungeraten, den
                # wirklich niemand zuordnen kann; der steht als offene Frage
                # in der Leiste statt als gruener Punkt. Zwei Karten hiessen
                # zwei Wahrheiten auf einem Bildschirm ("building 16/40"
                # neben "13'019 fehlen").
                self._bd_runplan_delivered = dict(
                    self._bd_runplan_delivered_sicher)
            except (KeyError, TypeError, ValueError) as _se:
                # Im Zweifel NICHTS abbuchen (Regel 3) - lieber eine zu
                # grosse Einkaufsliste als eine zu kleine.
                self._bd_runplan_delivered_sicher = {}
                self._log_exception("Runplaner: sichere Liefer-Karte", str(_se))
            # NUTZER-ENTSCHEIDUNG (Sitzung 8): "nur ich darf streichen" -
            # Haekchen setzt AUSSCHLIESSLICH der Nutzer (das fruehere
            # Auto-Abhaken ist raus). ESI blendet stattdessen voll gedeckte
            # Items AUS: geliefert + in der Bauschleife laufend >= Plan-Runs
            # ("schon dass es aktiv gebaut wird soll reichen, damit der
            # Bauplan nach und nach kleiner wird"). AUSBLENDEN heisst NICHT
            # loeschen - der eingefrorene Plan bleibt intakt, und je Stufe
            # bleibt eine Zaehl-Zeile sichtbar (Regel 6). Teilweise gedeckte
            # Items bleiben stehen (ihre Rest-Runs waeren sonst unsichtbar).
            # HIER WURDE `_bd_runplan_hidden` BEFUELLT - ERSATZLOS ENTFERNT
            # (Sitzung 14). Es diente allein dem Ausblenden voll gedeckter
            # Positionen, und das ist per Nutzer-Ansage weggefallen
            # ("imprinzip wird nie etwas mehr ausgeblendet nurnoch gedimmt").
            # Die Zusage "laufende Jobs zaehlen zur Deckung, die Bauschleife
            # reicht" (Sitzung 8) gilt UNVERAENDERT weiter - sie steckt jetzt
            # in `_rest_budget` oben, das aus genau denselben Zahlen entsteht
            # (geliefert + laufend, gedeckelt auf die Plan-Runs).
            # Stehengeblieben waere es toter Code, der aussieht, als taete er
            # etwas.
        stt = res["stage_times"]; tot = res["total_seconds"]
        self._bd_last_sched_seconds = tot        # für den Bau-Kalender merken
        # Frisches Ergebnis auch für "Bauplan speichern" merken, damit der
        # Kalender-Nachfüll-Plan sofort dieselben Zuteilungen zeigt wie hier
        # im Runplaner-Tab - nicht erst nach dem nächsten (zeitversetzten)
        # Hintergrund-Recompute, der zu anderen/veralteten Werten führen kann.
        # Gleiche Transformation wie der Hintergrund-Recompute (geteilte
        # Funktion), sonst passen die Feldnamen nicht zur Kalender-Anzeige.
        (self._bd_last_assignments, self._bd_last_waves,
         self._bd_last_stage_times) = self._transform_schedule_result(res, sched_chars)
        react_total = (stt.get("unrefined", 0) + stt.get("reaction_1", 0)
                       + stt.get("reaction_2", 0))
        # Nutzer-Frage "wo steht die Gesamtzeit?": Bau-Durchlauf stand hier,
        # Invention nur im anderen Tab, Kopierzeit NIRGENDS. Jetzt eine Zeile:
        _needs_t = getattr(self, "_bd_invention_needs", None) or {}
        _inv_s = sum(int(i.get("inv_secs") or 0) for i in _needs_t.values())
        _cp_s = sum(int(i.get("copy_secs") or 0) for i in _needs_t.values())
        _extra_t = ""
        if _inv_s or _cp_s:
            _bits_t = []
            if _cp_s:
                _bits_t.append(_txt("Copying \u2248{d}").format(d=self._fmt_dur(_cp_s)))
            if _inv_s:
                _bits_t.append(_txt("Invention \u2248{d}").format(d=self._fmt_dur(_inv_s)))
            _extra_t = ("   \u00b7   " + _txt("plus ") + " + ".join(_bits_t)
                        + _txt(" (rough, sequential \u2013 runs parallel to the build)"))
        hdr.setText(_txt("Total (rough): {tot}   \u00b7   Reactions {react} \u2192 "
                         "Components {comp} \u2192 End product {end}").format(
            tot=self._fmt_dur(tot), react=self._fmt_dur(react_total),
            comp=self._fmt_dur(stt.get('component', 0)),
            end=self._fmt_dur(stt.get('end', 0))) + _extra_t)
        # Der Header zeigt bereits die Gesamtzeiten (Reaktionen → Komponenten →
        # Endprodukt). Die frühere „Zeit je Charakter“-Detailzeile war zu überladen
        # und wurde entfernt. Der Sub-Text ist jetzt für WARNUNGEN reserviert und
        # wird nur dann sichtbar/auffällig, wenn wirklich etwas fehlt.
        warns = []
        if getattr(self, "_bd_science_data_missing", False):
            warns.append(_txt("\u26a0 Science skill data missing \u2013 press \u201eLoad "
                              "recipes\u201c once (reload SDE), otherwise the manufacturing "
                              "times are too long."))
        if getattr(self, "_bd_react_skill_missing", False):
            warns.append(_txt("\u26a0 Reaction skill not loaded \u2013 press \u201eLoad skills "
                              "\u2192 Job slots\u201c, otherwise the reaction times are too "
                              "long."))
        if warns:
            sub.setText("\n".join(warns))
            sub.setStyleSheet(
                f"color:{theme.AMBER}; font-weight:700; font-size:13px; padding:4px 0;")
        else:
            sub.setText("")
            sub.setStyleSheet("")
        sd = {"fuel": t("Fuel"), "unrefined": t("Unrefined reaction"),
              "reaction_1": t("Reaction"), "reaction_2": t("Reaction"),
              "component": t("Component"), "end": t("End product")}
        _cat_short = {
            "intermediate_reactions": "Intermediate", "composite_reactions": "Composite",
            "hybrid_reactions": "Hybrid Poly", "biochemical_reactions": "Biochem",
            "molecular_reactions": "Molecular", "unrefined_reactions": "Unrefined",
            "reactions": _txt("Other"),
            "advanced_components": "Advanced", "capital_components": "Capital",
            "advanced_capital_components": "Adv. Capital", "hybrid_components": "Hybrid",
            "t1_hulls": _txt("T1 hull"), "fuel_blocks": "Fuel Block", "tools": "Tool",
        }
        _catmap_fine = industry.item_category_map() or {}
        # _stage_map_rp wurde schon weiter oben (vor dem jobs-Aufbau) berechnet.

        def _stufe_label(a):
            """Feinere Stufen-Anzeige. Bei Reaktionen wird zus\u00e4tzlich die STUFE
            (1 = geht in weitere Reaktion, 2 = geht in den Bau) gezeigt, konsistent
            mit der Rezept-Struktur \u2013 plus der Materialtyp (Composite etc.), damit
            klar ist, welche \u201eMeine Blueprints\u201c-Checkbox zust\u00e4ndig ist."""
            stage = a["stage"]
            if stage == "end":
                # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                return "Endprodukt"
                # de_scan4: an
            tid = a["tid"]
            is_react = stage.startswith("reaction") or stage == "unrefined"
            info = _catmap_fine.get(tid)
            cat = info[0] if info else None
            meta = info[2] if info else None
            key = self._category_key(tid, _groups.get(tid, ""), is_react, cat, meta)
            fine = _cat_short.get(key)
            base = sd.get(stage, stage)
            if is_react and stage != "unrefined":
                # Die Stufe steht jetzt schon direkt im Stage-Namen (reaction_1/2) -
                # kein erneutes Nachschlagen nötig, das war vorher pro Item einzeln.
                st = 1 if stage == "reaction_1" else 2
                base = f"{base} \u00b7 " + t("stage {n}").format(n=st)
            return f"{base} \u00b7 {fine}" if fine else base
        from PySide6.QtWidgets import QTreeWidgetItem
        from collections import defaultdict as _dd
        import math as _math
        me_pct = float((getattr(self, "_bd_opts", None) or {}).get("me", 0))
        # Nach PHASE gruppieren (nicht nach Charakter) – so steht von oben nach
        # unten exakt die Reihenfolge, in der wirklich gebaut wird: erst ALLE
        # Intermediate-Reaktionen fertig, DANN Composite-Reaktionen (die brauchen
        # die Intermediate-Produkte als Zutat!), DANN Komponenten, DANN
        # Endprodukt. Innerhalb jeder Phase steht, wer was macht.
        by_stage_char = _dd(lambda: _dd(list))
        for a in res["assignments"]:
            by_stage_char[a["stage"]][a["char_id"]].append(a)
        # Überschuss (aus production_plan()) ist eine Eigenschaft des GANZEN
        # Items, nicht pro Charakter - wenn ein Item auf mehrere Charaktere
        # aufgeteilt ist (z.B. Titanium Chromide auf Elrasier UND Peanut
        # Motor), wird der Überschuss proportional zum jeweiligen Runs-Anteil
        # aufgeteilt, statt ihn irreführend bei JEDEM Charakter voll zu zeigen.
        _surplus_all = (plan or {}).get("surplus") or {}
        _runs_by_tid = _dd(float)
        for a in res["assignments"]:
            _runs_by_tid[a["tid"]] += float(a.get("runs", 0) or 0)
        # TEILWEISE GEBAUTE POSITIONEN: REST-RUNS STATT URSPRUNGSZAHL
        # (Sitzung 13, Nutzer-Fund mit Screenshot).
        #
        # VORFALL: eingefrorener Plan vom 28.08., Quantum Microprocessor.
        # Der Runplaner verlangte 7'321 Runs, obwohl der Materialien-Reiter
        # daneben 3'700 im Bestand und nur noch 3'661 fehlend auswies. Zwei
        # Zahlen fuer dieselbe Sache auf EINEM Bildschirm. Nutzer: "erstens
        # habe ich nicht genuegend Materialien dafuer gebaut".
        #
        # URSACHE (Stand Sitzung 13): `_bd_runplan_hidden` blendete nur
        # ALLES-ODER-NICHTS aus (geliefert + laufend >= Plan-Runs). Halb
        # fertige Items blieben mit ihrer URSPRUENGLICHEN Run-Zahl stehen -
        # als haette man noch nichts gemacht. Der Kommentar dort ("Teilweise
        # gedeckte Items bleiben stehen, ihre Rest-Runs waeren sonst
        # unsichtbar") hatte die richtige Sorge, loeste sie aber nur halb:
        # die Zeile blieb, die Zahl war alt.
        # SEIT SITZUNG 14 gibt es das Ausblenden gar nicht mehr (Nutzer-
        # Ansage), `_bd_runplan_hidden` ist ersatzlos weg. Das Rest-Budget
        # unten leistet beides: jede Zeile bleibt stehen UND zeigt ihre
        # aktuelle Zahl.
        #
        # WARUM NICHT DER LAGERBESTAND ABGEZOGEN WIRD: Bestand kann gekauft,
        # gelootet oder fuer einen anderen Plan gedacht sein. Abgezogen wird
        # deshalb NUR, was ESI als abgelieferte oder gerade laufende Jobs
        # DIESES Plans gesehen hat (`_bd_runplan_delivered` +
        # `_bd_active_jobs_map`) - dieselbe Quelle, aus der auch das
        # Ausblenden gespeist wird.
        #
        # REGEL 3 GILT HIER NICHT: "lieber zu viel als zu wenig" ist eine
        # Regel fuers EINKAUFEN (Material uebrig ist harmlos). Sie ist keine
        # Erlaubnis, jemanden 7'321 Runs fahren zu lassen, wenn 3'661 offen
        # sind - dafuer fehlt ihm das Material.
        #
        # Der eingefrorene Plan bleibt UNANGETASTET; nur die Anzeige zeigt
        # den Rest, und die Ursprungszahl steht daneben (Regel 6: nichts
        # verschwindet spurlos).
        from .mw_helpers import fertig_menge as _mwh_fertig
        _rest_budget = {}
        _plan_runs_tid = {}
        for _t_r, _r_r in _runs_by_tid.items():
            _plan_runs_tid[int(_t_r)] = int(_r_r)
        for _t_r, _pl_r in _plan_runs_tid.items():
            _fertig = int((getattr(self, "_bd_runplan_delivered", None)
                           or {}).get(_t_r, 0) or 0)
            _fertig += sum(int(_j.get("runs") or 0) for _j in
                           ((getattr(self, "_bd_active_jobs_map", None) or {})
                            .get(_t_r) or []))
            # nie mehr abziehen als geplant war - sonst wuerde ein Item, von
            # dem man MEHR gebaut hat als der Plan vorsah, negative Runs
            # zeigen.
            _rest_budget[_t_r] = _mwh_fertig(_pl_r, _fertig, 0)
        # VORSTUFEN OHNE OFFENEN VERBRAUCHER (Nutzer 28.09.2026, Phenolic):
        # dieselbe Regel wie im Materialien-Reiter (`_rest_geliefert_jetzt`,
        # dort samt Haken) - der Runplaner zeigt ihre Rest-Runs nicht mehr.
        self._bd_vorstufen_diag = ()
        try:
            _erl_v = dict(_rest_budget)
            for _t_v, _n_v in (self._rest_geliefert_jetzt() or {}).items():
                _erl_v[int(_t_v)] = max(int(_erl_v.get(int(_t_v), 0) or 0), int(_n_v))
            from .mw_helpers import (vorstufen_erledigt as _mwh_vorstufen,
                                     vorstufen_ins_budget as _mwh_vs_budget)
            _vs_schon = set(getattr(self, "_bd_vorstufen_fertig", None) or ())
            _vs_neu = dict(_mwh_vorstufen(_plan_runs_tid, (plan or {}).get("build_mats"),
                                          _erl_v))
            for _t_v in _vs_schon:
                _vs_neu.setdefault(int(_t_v), int(_plan_runs_tid.get(int(_t_v), 0) or 0))
            # fuer planer_diagnose.txt (nur schreiben, nie rechnen)
            self._bd_vorstufen_diag = (dict(_erl_v), dict(_vs_neu),
                                       dict((plan or {}).get("build_mats") or {}))
            _rest_budget = _mwh_vs_budget(_rest_budget, _plan_runs_tid,
                                          (plan or {}).get("build_mats"), _erl_v,
                                          _vs_schon)
        except Exception as _ve:
            self._log_exception("Runplaner: Vorstufen erledigt", str(_ve))
        # FORTSCHRITTS-DIAGNOSE (26.09.2026, Nutzer: "der Runplaner will
        # trotzdem nochmal 6'718 nachbauen ... genau das passiert die ganze
        # Zeit"): dieselben Zahlen, aus denen das Rest-Budget eben entstand,
        # in planer_diagnose.txt anhaengen - nur schreiben, nie rechnen.
        try:
            self._planer_diagnose_fortschritt(plan, names, _plan_runs_tid,
                                              _rest_budget)
        except Exception as _pdf:
            self._log_exception("Planer-Diagnose Fortschritt", str(_pdf))
        # WAS WAR AUFGEKLAPPT? (Nutzer 24.09.2026: "dann laedt es auch keine
        # Runs".) Es lud sie sehr wohl - der Neuaufbau klappte nur jede
        # Charakterzeile wieder zu, und die Runs stehen darunter. Nach einer
        # Zielzeit-Aenderung baut sich der Baum neu, also war nach jedem Klick
        # alles zu. Hier wird der Stand gemerkt und unten wiederhergestellt.
        # Der Stand liegt am FENSTER (`_bd_sched_klapp`, gepflegt von den
        # Klapp-Signalen) - beim Neuaufbau ist der alte Baum schon leer.
        # Angewandt wird er an EINER Stelle, unten bei `_stage_citems`: dort
        # setzt die Vorgabe "fertige Stufe auf, offene zu" den Zustand
        # ohnehin, ein zweites setExpanded weiter oben wuerde sie nur wieder
        # ueberschrieben bekommen (genau daran ist die erste Fassung
        # gescheitert - gemessen, nicht vermutet).
        _klapp_vorher = dict(getattr(self, "_bd_sched_klapp", None) or {})
        tbl.blockSignals(True)
        tbl.clear()
        cslots = {c["id"]: (c["mfg_slots"], c["reaction_slots"]) for c in sched_chars}
        cmax = {c["id"]: (c.get("mfg_slots_max"), c.get("reaction_slots_max"))
                for c in sched_chars}
        # FREIE Slots vom letzten "Skills laden" - seit Sitzung 11 steuern sie
        # die Planung NICHT mehr (Nutzer: "die besetzten slots sollen ignoriert
        # werden"). Verloren gehen sie trotzdem nicht: sie stehen weiter im
        # Tooltip der Charakter-Zeile, damit man sieht, was gerade laeuft.
        cfree = {c["id"]: tuple(c.get("frei_slots") or ()) for c in sched_chars}
        stage_meta = {
            # OHNE Klammer-Zusaetze: "(Zutaten)" / "(braucht Stufe 1)" haben den
            # Strukturnamen aus der Zeile gedraengt (bei Stufe 2 stand nur noch
            # "R&..."). Die Reihenfolge steht schon in der Nummerierung, und
            # dass eine Stufe auf die vorige wartet, sagt der Tooltip der Zeile.
            # Der BAU-ORT ist die wichtigere Information - er ist die
            # Handlungsanweisung.
            # FUEL ZUERST: die Reaktionen verbrauchen es (Nutzer, Sitzung 8).
            # Vorher stand es bei den Komponenten, also HINTER seinen eigenen
            # Verbrauchern.
            # SYMBOL-NAMEN statt Emoji (Sitzung 16) - gesetzt per setIcon.
            "fuel": ("1. " + t("Fuel"), "package", "ms", theme.GREEN),
            # UNREFINED ZUERST (Nutzer 19.09.2026): eigene Stufe vor den
            # Intermediates, dahinter der Reprocessing-Block - erst dann
            # gibt es das Zwischenmaterial. Die Nummern ruecken um eins,
            # sobald die Stufe vorkommt (sonst alles wie bisher).
            "unrefined": ("2. " + t("Unrefined reactions"), "flask", "rs", theme.VIOLET),
            "reaction_1": ("2. " + t("Reactions \u2013 Intermediate"),
                          "flask", "rs", theme.VIOLET),
            # EIGENE FARBE fuer die zweite Reaktions-Stufe (Nutzer,
            # Sitzung 12): beide Stufen sahen gleich aus, obwohl sie
            # nacheinander laufen und getrennt geplant werden.
            "reaction_2": ("3. " + t("Reactions \u2013 Composite"),
                          "flask", "rs", theme.VIOLET_2),
            "component": ("4. " + t("Components"), "wrench", "ms", theme.BLUE),
            "end": ("5. " + t("End product"), "target", "ms", theme.AMBER)}
        if by_stage_char.get("unrefined"):
            for _sk, _nr in (("reaction_1", 3), ("reaction_2", 4), ("component", 5), ("end", 6)):
                _l, _i, _s, _c = stage_meta[_sk]
                stage_meta[_sk] = (f"{_nr}. " + _l.split(". ", 1)[1], _i, _s, _c)
        # STUFE 0: REPROCESSING (1.0.9, Weg B; Nutzer: "im Runplaner als
        # aller erste Kategorie ganz oben"). Nur, wenn der Plan wirklich Erz
        # statt Mineral kauft - sonst keine Zeile. OPTIK WIE DIE ANDEREN
        # STUFEN (Nutzer 18.09.2026: "dass das Reprocessing mehr aussieht wie
        # das andere"): Stufenkopf mit Farbe und Symbol, Charakterzeile in
        # Cyan, je Erz eine Zeile mit denselben Spalten - Name (Klick
        # kopiert den Erz-Namen), Menge fett, Kopier-Knopf fuer die Menge,
        # Ergebnis in der Stufen-Spalte, Ueberschuss rechts. Haken = reprocesst.
        _rp0 = (plan or {}).get("reprocess") or {}
        _rp0_alle = _rp0.get("schritte") or []
        # Gratis-Erz (Blacklist: bekommt man, kauft man nicht) bleibt aus dem
        # Runplaner draussen (Nutzer 19.09.2026).
        _rp0_erz = [_s for _s in _rp0_alle
                    if _s.get("art") != "unrefined" and not _s.get("gratis")]
        # EINGEFROREN: Charakter mit HEUTIGEN Skills/Implantaten neu waehlen,
        # Mengen bleiben (emm361, `_repro_char_neu_waehlen`).
        if getattr(self, "_bd_frozen", None) and _rp0_erz:
            try:
                _rp0_erz = self._repro_char_neu_waehlen(_rp0_erz, _rp0.get("basis"))
            except Exception as _rce:
                self._log_exception("Runplaner: Reprocessing-Charakter", str(_rce))
        _rp0_unref = [_s for _s in _rp0_alle if _s.get("art") == "unrefined"]

        def _repro_block(_lbl0, _rp0_sch, _kopf_tip, _kopf_rechts=None, _ckey0="repro"):
            """Ein Reprocessing-Block (Kopf, Charakterzeilen, je Erz/Produkt
            eine Zeile) - fuer Stufe 0 (gekauftes Erz) und fuer die Unrefined-
            Schritte nach der Reaktionsstufe (Weg A). Gleiche Optik, gleiche
            Haken-Mechanik."""
            if not _rp0_sch:
                return
            _farbe0 = theme.GREEN
            _basis0 = _rp0.get("basis")
            _item0 = QTreeWidgetItem([
                _lbl0, "", "", "",
                (_kopf_rechts if _kopf_rechts is not None else
                 _txt("Structure base {pct} %").format(pct=f"{float(_basis0) * 100.0:.1f}")
                 if _basis0 else ""), ""])
            _item0.setIcon(0, icons.icon("package", farbe=_farbe0))
            _sf0 = _item0.font(0)
            _sf0.setBold(True); _sf0.setPointSize(_sf0.pointSize() + 2)
            _item0.setFont(0, _sf0)
            _bg0 = QColor(_farbe0); _bg0.setAlpha(38)
            for _c0 in range(5):
                _item0.setBackground(_c0, QBrush(_bg0))
            _item0.setForeground(0, QColor(_farbe0))
            _item0.setForeground(4, QColor(_farbe0))
            _item0.setToolTip(0, _kopf_tip)
            tbl.addTopLevelItem(_item0)
            _by_char0 = {}
            for _st0 in _rp0_sch:
                _by_char0.setdefault(_st0.get("char"), []).append(_st0)
            _hakt_alle0 = getattr(self, "_bd_runplan_checked", None) or set()
            _rp_zeilen0, _rp_erl0 = [], 0      # emm434: Stufen-Abschluss
            try:
                _erz_bestand0 = set(self._erz_durch_bestand())
            except Exception:
                _erz_bestand0 = set()
            for _cid0, _steps0 in sorted(_by_char0.items(),
                                         key=lambda kv: (kv[0] is None, kv[0] or 0)):
                _cname0 = cmap.get(_cid0, str(_cid0) if _cid0 is not None else "?")
                _n_bl0 = sum(int(_s.get("portionen") or 0) for _s in _steps0)
                _unref0 = all(_s.get("art") == "unrefined" for _s in _steps0)
                _citem0 = QTreeWidgetItem([
                    _cname0, "",
                    (_txt("{n} units") if _unref0 else _txt("{n} batches")).format(
                        n=f"{_n_bl0:,}".replace(",", "'")),
                    "", "", ""])
                _citem0.setForeground(0, QColor(theme.CYAN))
                _citem0.setToolTip(0, _txt(
                    "Best reprocessing character for these ores (skills x implant) "
                    "\u2013 log in with this one."))
                # HAKEN AM CHARAKTER (Nutzer 19.09.2026: "hinter dem
                # Charakternamen gibt es noch keinen Haken") - wie bei den
                # Stufen: der Haken zieht die Erz-Zeilen darunter mit
                # (_on_sched_check), gesichert unter "char|repro|<cid>".
                _f0c = _citem0.font(0); _f0c.setBold(True); _citem0.setFont(0, _f0c)
                _citem0.setFlags(_citem0.flags() | Qt.ItemIsUserCheckable)
                _ckey_c0 = f"char|{_ckey0}|{_cid0}"
                _citem0.setData(0, Qt.UserRole + 6, _ckey_c0)
                _citem0.setCheckState(0, Qt.Checked if _ckey_c0 in _hakt_alle0
                                      else Qt.Unchecked)
                if _ckey_c0 in _hakt_alle0:
                    for _c0 in range(tbl.columnCount()):
                        _fc0 = _citem0.font(_c0); _fc0.setStrikeOut(True)
                        _citem0.setFont(_c0, _fc0)
                        _citem0.setData(_c0, Qt.UserRole + 5, _citem0.foreground(_c0))
                        _citem0.setForeground(_c0, QColor(theme.GREEN))
                _item0.addChild(_citem0)
                for _st0 in _steps0:
                    _erz_nm0 = str((names or {}).get(_st0.get("erz")) or _st0.get("erz"))
                    _menge0 = int(_st0.get("menge") or 0)
                    _ausg0 = ", ".join(
                        f"{int(_q0):,}".replace(",", "'") + " "
                        + str((names or {}).get(_m0) or _m0)
                        for _m0, _q0 in sorted((_st0.get("deckt") or {}).items()))
                    _ueb0 = ", ".join(
                        "+" + f"{int(_q0):,}".replace(",", "'") + " "
                        + str((names or {}).get(_m0) or _m0)
                        for _m0, _q0 in sorted((_st0.get("ueberschuss") or {}).items()))
                    _row0 = QTreeWidgetItem([
                        _erz_nm0,
                        f"{_menge0:,}".replace(",", "'"),
                        "", "",
                        "\u2192 " + _ausg0 + "  \u00b7  "
                        + f"{float(_st0.get('ausbeute') or 0) * 100.0:.1f} %",
                        _ueb0 or "\u2013"])
                    _row0.setTextAlignment(1, Qt.AlignCenter)
                    _fr0 = _row0.font(1); _fr0.setBold(True); _row0.setFont(1, _fr0)
                    _row0.setForeground(4, QColor(theme.MUTED))
                    if _ueb0:
                        _row0.setForeground(5, QColor(theme.AMBER))
                    _ic0 = self._table_icon(_st0.get("erz"))
                    if _ic0:
                        _row0.setIcon(0, _ic0)
                    # Der Erz-Name haengt an der Zeile (Rechtsklick/Strg+C
                    # kopiert ihn); der Linksklick-Kopierweg ist raus (emm401).
                    _row0.setData(0, ROLLE_KOPIERNAME, _erz_nm0)
                    _row0.setData(0, Qt.UserRole, _st0.get("erz"))
                    if _st0.get("art") == "unrefined":
                        _row0.setToolTip(0, _txt(
                            "{n} units from the reaction stage above. Yield {pct} % "
                            "with this character: 50 % \u00d7 Scrapmetal Processing \u2013 "
                            "structure, rig and ore skills do not apply here.\nTick = "
                            "reprocessed (progress mark only).").format(
                            n=int(_st0.get("menge") or 0),
                            pct=f"{float(_st0.get('ausbeute') or 0) * 100.0:.1f}"))
                    else:
                        _row0.setToolTip(0, _txt(
                            "{n} batches of {p} units. Yield {pct} % with this "
                            "character at this structure.\nTick = reprocessed: from then "
                            "on the minerals must be in stock and the ore no longer "
                            "counts as needed.").format(
                            n=int(_st0.get("portionen") or 0), p=int(_st0.get("portion") or 0),
                            pct=f"{float(_st0.get('ausbeute') or 0) * 100.0:.1f}"))
                    _row0.setToolTip(4, _txt("What the ore yields for this plan; the "
                                             "rest is surplus (right)."))
                    # HAKEN = REPROCESST (Nutzer-Befund 18.09.2026: die
                    # Einkaufsliste kannte weder Erz noch gedeckte Minerale).
                    # Derselbe Mechanismus wie bei den Runs (_on_sched_check,
                    # _bd_runplan_checked, im Plan gesichert); der Schluessel
                    # "repro|<erz>" wird von _restbedarf_jetzt /
                    # _fehlbedarf_jetzt gelesen, sonst von niemandem.
                    _row0.setFlags(_row0.flags() | Qt.ItemIsUserCheckable)
                    _key0 = reprocess.schritt_key(_st0)
                    _row0.setData(0, Qt.UserRole + 6, _key0)
                    _hakt0 = _key0 in _hakt_alle0
                    if not _hakt0 and _key0 in _erz_bestand0:
                        # MINERALE LIEGEN SCHON DA (28.09.2026): gruen und
                        # gesagt, ohne Haken zu setzen (den setzt nur der
                        # Nutzer, Sitzung 8).
                        _row0.setText(4, _row0.text(4) + "  \u00b7  " + _txt(
                            "minerals already in stock \u2713"))
                        for _c0 in range(tbl.columnCount()):
                            _row0.setForeground(_c0, QColor(theme.GREEN))
                        _row0.setToolTip(4, _txt(
                            "Every mineral this ore was planned for is already "
                            "in stock for this plan (reprocessed or bought). "
                            "The ore is no longer needed and not on the "
                            "shopping list."))
                    _row0.setCheckState(0, Qt.Checked if _hakt0 else Qt.Unchecked)
                    _rp_zeilen0.append(_row0)
                    if _hakt0 or _key0 in _erz_bestand0:
                        _rp_erl0 += 1
                    if _hakt0:
                        for _c0 in range(tbl.columnCount()):
                            _f0 = _row0.font(_c0); _f0.setStrikeOut(True); _row0.setFont(_c0, _f0)
                            _row0.setData(_c0, Qt.UserRole + 5, _row0.foreground(_c0))
                            _row0.setForeground(_c0, QColor(theme.GREEN))
                    _citem0.addChild(_row0)
                    # KOPIER-KNOPF FUER DIE MENGE (Nutzer: "Zahlen koennen
                    # nicht kopiert werden ... da moechte ich nur draufklicken
                    # koennen") - dieselbe Optik wie die Run-Knoepfe.
                    try:
                        _cw0 = QWidget()
                        _cl0 = QHBoxLayout(_cw0)
                        _cl0.setContentsMargins(0, 3, 0, 3)
                        _cl0.setSpacing(3)
                        _b0 = QPushButton(f"{_menge0:,}".replace(",", "'"))
                        _b0.setCursor(Qt.PointingHandCursor)
                        _b0.setMinimumHeight(24)
                        _b0.setToolTip(_txt("Click copies {r} \u2013 paste it into the "
                                            "quantity field in game (Ctrl+V).").format(
                            r=f"{_menge0:,}".replace(",", "'")))
                        _b0.setStyleSheet(
                            f"QPushButton{{background:{theme.PANEL2}; "
                            f"border:1px solid {theme.AMBER_DIM}; "
                            f"color:{theme.AMBER}; border-radius:5px; "
                            f"padding:0px 10px; font-weight:700;}}"
                            f"QPushButton:hover{{border-color:"
                            f"{theme.AMBER}; background:{theme.PANEL};}}")
                        _b0.clicked.connect(
                            lambda _c=False, _v=_menge0, _n=_erz_nm0:
                            self._copy_runs_value(_v, _n))
                        _cl0.addWidget(_b0)
                        _cl0.addStretch()
                        _cw0.adjustSize()
                        _h0 = max(34, _cw0.sizeHint().height() + 10)
                        _row0.setSizeHint(2, QSize(0, _h0))
                        _row0.setSizeHint(0, QSize(0, _h0))
                        tbl.setItemWidget(_row0, 2, _cw0)
                    except Exception:
                        pass       # Knoepfe sind Komfort, nie kritisch
                # Charakter ZU, Stufe AUF - wie bei den anderen Stufen
                # (Nutzer 19.09.2026, Screenshot); was der Nutzer selbst
                # geklappt hat, gewinnt (emm400).
                _citem0.setExpanded(bool(_klapp_vorher.get(_ckey_c0, False)))
            # ERLEDIGT OHNE ESI (emm434, Nutzer: "Komprimieren habe ich
            # theoretisch gemacht, aber dafuer gibt es keine ESI-Tracking-
            # Funktion und somit graut es nicht aus"): Reprocessing kennt
            # ESI nicht - erledigt ist die Stufe, wenn JEDE Zeile gehakt ist
            # (oder ihre Minerale schon im Bestand liegen).
            _rp_fertig0 = bool(_rp_zeilen0) and _rp_erl0 == len(_rp_zeilen0)
            if _rp_fertig0:
                self._stufe_abschluss(
                    tbl, _item0, "erledigt",
                    _rp_zeilen0 + [_item0.child(_i)
                                   for _i in range(_item0.childCount())])
            # de_scan5: aus - interner Klapp-Schluessel, nie sichtbar
            _item0.setData(0, Qt.UserRole + 6, "stufe|" + str(_ckey0))
            _item0.setExpanded(bool(_klapp_vorher.get(
                "stufe|" + str(_ckey0), not _rp_fertig0)))
            # de_scan5: an

        _lbl_st0 = "0. " + _txt("Reprocessing")
        if _rp0.get("struct"):
            _lbl_st0 += f"  \u00b7  {_rp0['struct']}"
        _repro_block(_lbl_st0, _rp0_erz, _txt(
            "Buy the compressed ore, reprocess it with the named character at "
            "this structure \u2013 then the minerals are in stock for the stages "
            "below. Ore is reprocessed in batches of 100; the number in the "
            "Runs column is the number of batches."))
        # WEG A: die Unrefined-Produkte entstehen erst in der Reaktionsstufe -
        # ihr Reprocessing-Block steht deshalb DAHINTER, nicht oben.
        _ub_nach = "unrefined" if by_stage_char.get("unrefined") else None

        def _unref_block():
            # Kein Strukturname: der Scrapmetal-Pfad ist ueberall 50 % Basis.
            _repro_block("\u21b3 " + _txt("Reprocessing of unrefined products"),
                         _rp0_unref, _txt(
                "After the reaction: reprocess the unrefined products with the "
                "named character (any station or structure) \u2013 only then is the "
                "intermediate material in stock for the next stage. The returned "
                "input (surplus, right) comes back here as well."),
                _kopf_rechts=_txt("Base 50 % \u00d7 Scrapmetal Processing"),
                _ckey0="urepro")
        if _ub_nach is None:
            _unref_block()
        for stage in ("fuel", "unrefined", "reaction_1", "reaction_2", "component", "end"):
            char_map = by_stage_char.get(stage)
            if not char_map:
                continue
            label, icon, slot_kind, stage_color = stage_meta[stage]
            # WO wird das gebaut? (Nutzer-Wunsch) Ohne den Strukturnamen ist der
            # Runplaner keine Arbeitsanweisung: bei zwei Azbels mit
            # unterschiedlichen Rigs sieht man weder, welche gemeint ist, noch
            # warum die Zeiten sich unterscheiden. Genau daran hat ein ganzer
            # Abend Fehlersuche gehangen. Nur der NAME - keine Prozent-Liste,
            # die die Zeile zumuellt; die Boni stehen weiter im Struktur-Dialog.
            # KORREKTUR Sitzung 9: pro STUFE nachschlagen. Vorher stand hier
            # fuer JEDE Fertigungsstufe die Komponenten-Struktur - "1.
            # Treibstoff", "4. Komponenten" und "5. Endprodukt" zeigten
            # zwangslaeufig denselben Namen, auch wenn die Auto-Wahl fuers
            # Endprodukt eine andere Struktur genommen hatte.
            _stufe_key = {"fuel": "components", "component": "components",
                          "end": "endproduct", "reaction_1": "reaction_1",
                          "unrefined": "reaction_1",
                          "reaction_2": "reaction_2"}.get(stage)
            _stage_struct = (getattr(self, "_bd_stage_structs", {}) or {}).get(
                _stufe_key)
            if _stage_struct is None:
                # Rueckfall auf die alten Sammelvariablen, wenn die Stufen-Karte
                # (noch) fehlt - z.B. bei eingefrorenen Alt-Plaenen.
                _stage_struct = (getattr(self, "_bd_react_struct", None)
                                 if (stage.startswith("reaction") or stage == "unrefined")
                                 else getattr(self, "_bd_mfg_struct", None))
            _sname = (_stage_struct or {}).get("name")
            if _sname:
                label = f"{label}  \u00b7  {_sname}"
            dur = res["stage_times"].get(stage, 0.0)
            stage_item = QTreeWidgetItem([label, "", "",
                                          self._fmt_dur(dur), ""])
            stage_item.setIcon(0, icons.icon(icon, farbe=stage_color))
            # WARUM DIESE STRUKTUR? (Nutzer, Sitzung 8: "theoretisch
            # muesste das Tool fuer ein Capital-Schiff den Bauort auf
            # Capslock aendern.") Die Auto-Wahl vergleicht den RIG-Nutzen
            # fuer genau die Items dieser Stufe. Der Tooltip legt die
            # Rangliste offen - so sieht man sofort, ob eine Struktur
            # gewonnen hat oder ob alle bei 0 % lagen und schlicht die
            # erste genommen wurde.
            try:
                _rang = (getattr(self, "_bd_struct_choice", {}) or {}).get(
                    _stufe_key or stage) or []
                if _rang:
                    _zeilen = "\n".join(
                        f"  {'\u2713' if i == 0 else '\u00b7'} {_n}: "
                        f"{_b:+.1f} % " + _txt("material rig")
                        for i, (_n, _b) in enumerate(_rang))
                    _gleich = (len({b for _, b in _rang}) == 1
                               and len(_rang) > 1)
                    # Die EINORDNUNG der Items dazu - daran haengt alles.
                    # Steht dort "advanced_large_ship" statt "capital_ship",
                    # ist sofort klar, warum das Capital-Rig nicht greift.
                    _dg = (getattr(self, "_bd_struct_diag", {}) or {}).get(
                        _stufe_key or stage) or []
                    _einordnung = ""
                    if _dg:
                        _einordnung = (
                            "\n\n" + t("Classification of the items (group \u2192 "
                                       "rig category):") + "\n"
                            + "\n".join(f"  {_g} \u2192 {', '.join(_d)}"
                                        for _g, _d in _dg))
                    stage_item.setToolTip(
                        0, _txt("Auto-choice by rig benefit for the items of THIS "
                                "stage:\n") + _zeilen
                        + (_txt("\n\nAll level \u2013 no rig fits this item type, so the "
                                "order decides. A capital rig, for instance, does NOT "
                                "affect freighters (they count as Large Ship).")
                           if _gleich else "")
                        + _einordnung)
            except Exception:
                pass
            # SICHTBAR statt versteckt (Nutzer, Sitzung 9: "weiss nicht wo das
            # stehen soll"). Der Tooltip oben ist ein schlechtes
            # Diagnosewerkzeug: man muss die richtige Stelle treffen, und wenn
            # die Daten fehlen, wird er still gar nicht gesetzt - Zeigen auf
            # die Zeile ergibt dann einfach nichts, ohne dass jemand erfaehrt
            # warum. Die Rig-Kategorie gehoert deshalb in die ZEILE.
            try:
                # SCHLUESSEL-FALLE (Nutzer-Screenshot, Sitzung 9: "Rig: keine
                # Einordnung" bei 4 von 5 Stufen): die Diagnose liegt unter den
                # RECHEN-Schluesseln (components/endproduct/...), diese Schleife
                # laeuft aber ueber die ANZEIGE-Schluessel (fuel/component/end).
                # Nur reaction_1/reaction_2 stimmen zufaellig ueberein - genau
                # die eine Stufe, die Daten zeigte. Deshalb hier _stufe_key.
                _dg2 = (getattr(self, "_bd_struct_diag", {}) or {}).get(
                    _stufe_key or stage) or []
                _kat = []
                for _g, _d in _dg2:
                    for _x in _d:
                        if _x not in _kat:
                            _kat.append(_x)
                # BESCHRIFTUNG KORRIGIERT (Nutzer, Sitzung 9: "Dann werden da
                # Rigs frei erfunden"): hier steht die Rig-KATEGORIE der
                # ITEMS dieser Stufe - nicht die verbauten Rigs der Struktur.
                # Mit dem Wort "Rig:" davor las sich das zwangslaeufig wie
                # eine erfundene Rig-Liste. Jetzt "Item-Art:" plus Tooltip,
                # der den Unterschied ausspricht.
                stage_item.setText(
                    4, _txt("Item type: ") + ", ".join(_kat[:3]) if _kat
                    else _txt("Item type: not classified"))
                stage_item.setToolTip(
                    4, _txt("Rig CATEGORY of the items of this stage \u2013 NOT the rigs "
                            "fitted to the structure (those are in the Structures "
                            "tab).\nA material/time rig of the chosen structure only "
                            "applies if it covers this category.\nFull ranking with "
                            "classification: hover over the stage name on the left."))
            except Exception:
                stage_item.setText(4, _txt("Item type: not classified"))
            sf = stage_item.font(0)
            sf.setBold(True); sf.setPointSize(sf.pointSize() + 2)
            stage_item.setFont(0, sf)
            f4 = stage_item.font(3); f4.setBold(True); f4.setPointSize(f4.pointSize() + 1)
            stage_item.setFont(3, f4)
            # Farbiger HINTERGRUND (nicht nur Text) über die ganze Zeile – so sieht
            # die Phase wirklich wie eine Abschnitts-Überschrift aus, statt nur eine
            # andersfarbige Tabellenzeile zu sein ("Excel-Look" vermeiden).
            bg = QColor(stage_color); bg.setAlpha(38)
            for col in range(5):
                stage_item.setBackground(col, QBrush(bg))
            stage_item.setForeground(0, QColor(stage_color))
            stage_item.setForeground(4, QColor(stage_color))
            stage_item.setToolTip(0, _txt("This phase only starts once the previous one is "
                                          "completely finished \u2013 never at the same time."))
            tbl.addTopLevelItem(stage_item)
            # ZIELZEIT DIESER STUFE (Nutzer 24.09.2026). Das Feld sitzt in der
            # Runs-Spalte der Stufenzeile - dort steht bei einer Stufe nie
            # etwas, und es steht DIREKT neben der Dauer, die es beeinflusst.
            # Keine eigene Leiste, kein Dialog: die Zeile, die die Zeit zeigt,
            # ist auch die Zeile, an der man sie einstellt.
            # DIE STUFE HAENGT AN DER ZEILE (Rolle 8), nicht am Text: der
            # Kopf heisst je nach Struktur und Nummerierung anders, und die
            # Reprocessing-Bloecke daneben sind gar keine Planer-Stufen.
            # BEWUSST HIER und nicht im Feld-Aufbau: sonst verschwaende mit
            # dem Feld auch die Markierung, und eine Pruefung "genau die
            # Stufenzeilen haben ein Feld" waere tautologisch (die Rotprobe
            # hat genau das gemeldet).
            stage_item.setData(1, Qt.UserRole + 8, str(stage))
            # KLAPP-GEDAECHTNIS AUCH FUER DIE STUFE (emm400, Nutzer: der
            # ESI-Autorefresh "schliesst leider auch alle aufgeklappten job
            # runs wieder"): mit dem Schluessel landet jeder Nutzer-Klapp in
            # `_bd_sched_klapp` (dieselben Signale wie die Charakterzeilen).
            # de_scan5: aus - interner Klapp-Schluessel, nie sichtbar
            stage_item.setData(0, Qt.UserRole + 6, "stufe|" + str(stage))
            # de_scan5: an
            self._runplan_ziel_feld(
                tbl, stage_item, stage,
                (res.get("stage_min_times") or {}).get(stage, 0.0),
                (res.get("stage_min_by") or {}).get(stage))
            _checked_set = getattr(self, "_bd_runplan_checked", None) or set()

            def _apply_struck(titem):
                """Durchgestrichen-Optik manuell anwenden (Signale sind während
                des Baumaufbaus geblockt, also löst setCheckState hier KEIN
                itemChanged/_on_sched_check aus - beim Wiederherstellen eines
                gespeicherten Häkchens sonst nur die Box an, aber kein Strich)."""
                for c in range(tbl.columnCount()):
                    f = titem.font(c); f.setStrikeOut(True); titem.setFont(c, f)
                    if titem.data(c, Qt.UserRole + 5) is None:
                        titem.setData(c, Qt.UserRole + 5, titem.foreground(c))
                    titem.setForeground(c, QColor(theme.GREEN))
            # ZAEHLER FUER DEN STUFEN-ZUSTAND (Nutzer, Sitzung 14). Eine
            # Stufe gilt als fertig, wenn JEDE ihrer Positionen erledigt ist
            # (ESI-belegt oder vom Nutzer abgehakt). Entschieden wird NACH
            # der Charakter-Schleife - vorher kann niemand wissen, ob noch
            # eine offene Position kommt.
            _stage_citems = []
            _stage_items = 0
            _stage_erledigt = 0
            # LAUFENDE POSITIONEN SEPARAT (Nutzer, Sitzung 16): "die blauen
            # Sachen besagen ja, dass etwas im Bau ist. Aber die
            # Ueberkategorie davon zeigt gruen mit Checkhaken. Das ist
            # verwirrend - wenn noch etwas im Bau ist, sollte auch die
            # Kategorie blau sein mit (building) / (im Bau)."
            # Bis hierher zaehlte `_zustand is not None` AUCH "laeuft" als
            # erledigt - eine Stufe mit laufenden Jobs bekam den Haken.
            _stage_laeuft = 0
            # FERTIG, ABER NOCH NICHT ABGELIEFERT (emm433, Nutzer: "wenn die
            # Vorstufen komplett abgeschlossen sind ... (Bereit zum
            # ausliefern)", danach "(Erledigt)" und alles grau).
            _stage_bereit = 0

            def _wellen(alist, cap):
                """[(Welle, Zuteilungen)] - ganze Kopien (`parts`) eines
                Charakters, die nicht in seine Slots passen, als ZWEITE
                Auflistung desselben Charakters (Nutzer 19.09.2026: "ich kann
                nicht 18 Blueprints laufen lassen ... wenn alle Slots voll
                sind, muss der Charakter zweimal aufgelistet werden, um den
                Rest am naechsten Tag zu bauen"). Ohne `parts` (keine ganzen
                Kopien) bleibt es bei einer Zeile mit dem Wellen-Hinweis."""
                _jobs = sum(max(1, int(a.get("jobs") or 1)) for a in alist)
                if _jobs <= cap or not all(a.get("parts") for a in alist):
                    return [(1, alist)]
                out = []
                welle, frei, akt = 1, cap, []
                for a in alist:
                    _tv = float(a.get("tv") or 0.0)
                    if not _tv and a.get("parts"):
                        _tv = float(a.get("seconds") or 0.0) / max(1, max(a["parts"]))
                    for p in sorted(a["parts"], reverse=True):
                        if frei == 0:
                            out.append((welle, akt))
                            welle, frei, akt = welle + 1, cap, []
                        if akt and akt[-1]["tid"] == a["tid"]:
                            akt[-1]["parts"].append(p)
                            akt[-1]["runs"] += p
                            akt[-1]["jobs"] += 1
                        else:
                            akt.append({**a, "parts": [p], "runs": p, "jobs": 1,
                                        "seconds": p * _tv, "welle": welle})
                        frei -= 1
                if akt:
                    out.append((welle, akt))
                return out
            _eintraege = []
            for cid, alist in char_map.items():
                ms, rs = cslots.get(cid, (1, 1))
                for _welle, _al in _wellen(alist, rs if slot_kind == "rs" else ms):
                    _eintraege.append((cid, _welle, _al))
            # VORAB JE STUFE (Nutzer 29.09.2026, Nonlinear Metamaterials bei
            # Banana UND Peanut Motor, gebaut hatte nur Peanut): laufende
            # Jobs decken ZUERST die Zeile des Charakters, der sie faehrt
            # (`budget_eigene_zuerst`), und nachgetragene Haken bekommt eine
            # Zeile erst, nachdem die wirklich gehakten Zeilen ihre Runs
            # verbraucht haben (`haken_nachtragen`). Vorher nahm sich die
            # erste Zeile der Liste beides - blauer Punkt und fremder Haken.
            from .mw_helpers import (budget_eigene_zuerst as _mwh_eigen,
                                     haken_nachtragen as _mwh_haken)
            _zeilen_b, _zeilen_h = [], []
            for _cid_v, _welle_v, _al_v in _eintraege:
                _wsuf_v = f"|w{_welle_v}" if _welle_v > 1 else ""
                _cn_v = cmap.get(_cid_v, str(_cid_v))
                for _a_v in sorted(_al_v, key=lambda x: -x["runs"]):
                    _t_v = int(_a_v["tid"])
                    _zeilen_b.append(((_cid_v, _welle_v, _t_v), _t_v,
                                      int(_a_v["runs"]), _cn_v))
                    _zeilen_h.append((f"{stage}|{_cid_v}|{_a_v['tid']}{_wsuf_v}",
                                      f"{stage}|{_t_v}", int(_a_v.get("runs") or 0)))
            _lauf_je_char = {}
            for _t_l, _js_l in (getattr(self, "_bd_active_jobs_map", None) or {}).items():
                for _j_l in (_js_l or []):
                    if _j_l.get("char"):
                        _m_l = _lauf_je_char.setdefault(int(_t_l), {})
                        _m_l[str(_j_l["char"])] = (_m_l.get(str(_j_l["char"]), 0)
                                                   + int(_j_l.get("runs") or 0))
            _tids_v = {z[1] for z in _zeilen_b}
            _gedeckt_v, _rest_neu_v = _mwh_eigen(
                _zeilen_b, {_tb: _rest_budget.get(_tb, 0) for _tb in _tids_v}, _lauf_je_char)
            for _t_v in _tids_v:
                _rest_budget[_t_v] = _rest_neu_v.get(_t_v, 0)
            _haken_neu = set(_mwh_haken(_zeilen_h, _checked_set, _rest_erl))
            for cid, _welle, alist in _eintraege:
                ms, rs = cslots.get(cid, (1, 1))
                cap = rs if slot_kind == "rs" else ms
                # Zweite Auflistung: eigener Schluessel-Zusatz fuer die Haken.
                _wsuf = f"|w{_welle}" if _welle > 1 else ""
                _mx2 = cmax.get(cid, (None, None))
                cap_max = _mx2[1] if slot_kind == "rs" else _mx2[0]
                jobs_sum = sum(a.get("jobs", 1) for a in alist)
                # WORTWAHL (Nutzer, Sitzung 9: "wie kann Banana Motor 11
                # Reaction-Auftraege bekommen? Er hat ingame nur 10 Slots
                # frei"): die Zahl links sind die STARTS (Blaupausen-Jobs)
                # dieser Stufe insgesamt - nicht gleichzeitig laufende Jobs.
                # Ueberzaehlige startet man nach, sobald ein Slot frei wird
                # (2. Welle); der Scheduler stapelt sie zeitlich hinter die
                # laufenden Jobs desselben Slots, die Stufenzeit enthaelt
                # dieses Warten also bereits. Das alte "11/10 gleichzeitig"
                # behauptete dagegen elf PARALLELE Jobs - dieselbe
                # Fehlerklasse wie das "Rig:"-Praefix: die Beschriftung log,
                # die Rechnung nicht.
                if jobs_sum > cap:
                    slot_txt = _txt("{n} starts on {cap} slots \u00b7 waves").format(
                        n=jobs_sum, cap=cap)
                else:
                    slot_txt = _txt("{n}/{cap} slots").format(n=jobs_sum, cap=cap)
                citem = QTreeWidgetItem([
                    cmap.get(cid, str(cid))
                    + ("  \u00b7  " + _txt("wave {n}").format(n=_welle) if _welle > 1 else ""),
                    "", slot_txt, "", ""])
                if _welle > 1:
                    citem.setToolTip(0, _txt(
                        "Second listing of this character: start these copies once "
                        "the first wave has freed the slots (e.g. the next day)."))
                # BESETZTE SLOTS: seit Sitzung 11 plant das Tool mit dem
                # MAXIMUM (Nutzer-Entscheid: "die besetzten slots sollen
                # ignoriert werden") - der Plan laeuft ueber Tage, die jetzt
                # laufenden Jobs sind dann laengst fertig. Die Zahl bleibt
                # aber sichtbar, damit niemand raten muss, warum ingame
                # gerade weniger geht als hier steht.
                _fr2 = cfree.get(cid) or ()
                _frei_jetzt = None
                if len(_fr2) == 2:
                    _frei_jetzt = _fr2[1] if slot_kind == "rs" else _fr2[0]
                if _frei_jetzt is not None and cap_max and _frei_jetzt < cap_max:
                    _ts9 = self.settings.get("bau_char_free_ts")
                    try:
                        from datetime import datetime as _dt9
                        _wann9 = (_dt9.fromtimestamp(float(_ts9))
                                  .strftime("%d.%m. %H:%M") if _ts9 else None)
                    except Exception:
                        _wann9 = None
                    citem.setToolTip(2, _txt(
                        "Planning uses {cap} slots (maximum per skills).\nIn game, at "
                        "the last \u201eLoad skills\u201c{when} only {free} of them were "
                        "free \u2013 the rest were busy.\nThis is DELIBERATELY ignored: "
                        "by the time this stage comes up, those jobs are done. "
                        "Previously a character with 0 free slots dropped out of the "
                        "plan entirely and all the work landed on a single one.\nWhen "
                        "opening a build plan the tool refreshes this state "
                        "automatically if it is older than 10 minutes."
                    ).format(cap=cap_max, free=_frei_jetzt,
                             when=(_txt(" on {d}").format(d=_wann9) if _wann9 else "")))
                citem.setForeground(0, QColor(theme.CYAN))  # alle Charaktere gleiche
                                                            # Farbe (Personen-Ebene),
                                                            # unterscheidet sich von
                                                            # den Phasen-Farben oben
                citem.setFlags(citem.flags() | Qt.ItemIsUserCheckable)
                _ckey_char = f"char|{stage}|{cid}{_wsuf}"
                citem.setData(0, Qt.UserRole + 6, _ckey_char)
                if _ckey_char in _checked_set:
                    citem.setCheckState(0, Qt.Checked)
                    _apply_struck(citem)
                else:
                    citem.setCheckState(0, Qt.Unchecked)
                if jobs_sum > cap:
                    citem.setForeground(2, QColor(theme.AMBER))
                    citem.setToolTip(2, _txt(
                        "More starts ({jobs}) than simultaneous slots ({cap}) \u2013 you "
                        "start the surplus ones as soon as a slot frees up (next "
                        "wave). The stage time already includes this waiting."
                    ).format(jobs=jobs_sum, cap=cap)
                        + (_txt("\n({cap} = FREE slots at the last \u201eLoad skills\u201c, "
                                "maximum {max} per skills.)").format(cap=cap, max=cap_max)
                           if cap_max and cap < cap_max else ""))
                f0 = citem.font(0); f0.setBold(True); citem.setFont(0, f0)
                # ZUSTAND JE CHARAKTER-ZEILE (Nutzer, Sitzung 14: "dann
                # muessen wir die charaktere auch abhacken"). Sind ALLE
                # Positionen dieses Charakters in dieser Stufe erledigt oder
                # in Bau, soll auch seine Zeile so aussehen - sonst steht
                # ueber lauter gedimmten Punkt-Zeilen ein leeres Kaestchen,
                # das wieder nach Arbeit aussieht.
                _c_items = 0
                _c_zustand = 0
                _c_laeuft = 0
                for a in sorted(alist, key=lambda x: -x["runs"]):
                    njobs = a.get("jobs", 1) or 1
                    R_plan = int(a["runs"])
                    # Vom Rest-Budget dieses Items abknabbern (siehe oben).
                    # Die Zuteilungen eines Items werden in fester Reihenfolge
                    # abgearbeitet, deshalb reicht ein laufender Zaehler - die
                    # Summe ueber alle Zuteilungen bleibt exakt.
                    _tid_a = int(a["tid"])
                    # verteilt VORAB (`budget_eigene_zuerst`, s. oben)
                    R = max(0, R_plan - int(_gedeckt_v.get((cid, _welle, _tid_a), 0)))
                    _weg = R_plan - R
                    # ---- ZUSTAND STATT AUSBLENDEN (Nutzer, Sitzung 14) ------
                    # WIDERRUFT DIE ANSAGE AUS SITZUNG 8 ("die ESI soll
                    # Sachen ausblenden ... damit der Bauplan nach und nach
                    # kleiner wird"). Neue Ansage, woertlich: "imprinzip wird
                    # nie etwas mehr ausgeblendet nurnoch gedimmt und
                    # eingefaerbt und mit punkten versehen. Somit kann ich
                    # immer nachsehen was und wie ich etwas gebaut habe,
                    # weiss aber gleichzeitig okey. ich muss da nicht mehr
                    # ran". Die Zeile bleibt also stehen - samt ihren
                    # Material-Unterzeilen, denn genau die wollte er
                    # nachschlagen koennen ("auch was es mal an materialien
                    # gebraucht hat").
                    #
                    # `_zustand` ist die EINE Wahrheit fuer diese Zeile:
                    #   None     - offen, normales Kaestchen
                    #   "fertig" - ESI hat die Runs geliefert -> gruener Punkt
                    #   "laeuft" - steckt in der Bauschleife -> CYAN_RUN-Punkt
                    # Gedimmt werden beide erledigten Faelle.
                    _zustand = None
                    if R <= 0:
                        # Rest-Budget dieses Items ist auf: die Runs dieser
                        # Zuteilung sind gedeckt. ANZEIGE mit den PLAN-Runs,
                        # nicht mit der 0 - sonst stuende dort "0 Runs" und
                        # die Zeile waere als Rueckblick wertlos.
                        #
                        # GEDECKT HEISST NICHT GEBAUT: `mw_helpers.
                        # fertig_menge` zaehlt geliefert UND laufend
                        # zusammen. Ein pauschales "fertig" haette hier also
                        # einen gruenen Punkt auf eine Position gesetzt, die
                        # noch in der Bauschleife steckt - eine
                        # Falschaussage. Gefunden von der Rotprobe
                        # (Sitzung 14). Deshalb dieselbe Unterscheidung wie
                        # unten beim ESI-Befund, aus denselben Rohdaten.
                        _gel_r = int((getattr(self, "_bd_runplan_delivered",
                                              None) or {}).get(_tid_a, 0) or 0)
                        # NUR ECHT LAUFENDE JOBS ZAEHLEN (Nutzer-Screenshot,
                        # Sitzung 14: "da steckt aber schon lange nichts mehr
                        # in der Bauschleife"). `_bd_active_jobs_map` enthaelt
                        # ZWEI Sorten: status "active" (laeuft wirklich) und
                        # status "ready" - fertig gebaut, ingame nur noch
                        # nicht abgeholt. ESI meldet fertige Jobs sogar
                        # weiter als "active"; das Tool korrigiert sie ueber
                        # das abgelaufene end_date zu "ready" (s.
                        # esi.job_is_finished). Wer beide zusammenwirft,
                        # setzt den Lauf-Punkt auf laengst gebaute Sachen -
                        # genau das ist passiert.
                        # NUTZER-ENTSCHEID (Sitzung 14): "ready" gilt als
                        # FERTIG - gedimmt, gruener Punkt. Der Output
                        # existiert; dass er noch abgeholt werden muss, sagt
                        # weiterhin das ✅ vor dem Namen samt Tooltip aus dem
                        # bestehenden Zweig weiter unten.
                        _lauf_r = sum(
                            int(_j.get("runs") or 0) for _j in
                            ((getattr(self, "_bd_active_jobs_map", None)
                              or {}).get(_tid_a) or [])
                            if _j.get("status") != "ready")
                        # JOB-ZUORDNUNG (Nutzer, Sitzung 16): laeuft der Job
                        # fuer einen ANDEREN Plan? ESI verraet das nicht -
                        # aber Reservierungen sind plan-zugeordnet, und die
                        # Karte enthaelt auch selbst gebaute Zwischenprodukte.
                        # Reserviert genau ein fremder Plan dieses Item und
                        # dieser nicht, gehoert der Job dorthin - dann hier
                        # KEIN "laeuft" behaupten.
                        if _lauf_r > 0 and self._job_gehoert_anderem_plan(
                                _tid_a, _fremd_res, eigene=_eigene_res):
                            _lauf_r = 0
                        # de_scan4: aus - interner Zustands-Schluessel, nie angezeigt
                        _zustand = ("laeuft"
                                    if (_lauf_r > 0 and _gel_r < R_plan)
                                    else "fertig")
                        # de_scan4: an
                        R = R_plan
                        # BEREIT ZUM ABLIEFERN (emm433): Jobs dieses Items,
                        # die ESI fertig meldet, aber noch nicht abgeholt.
                        if _zustand != "laeuft" and any(
                                _j.get("status") == "ready" for _j in
                                ((getattr(self, "_bd_active_jobs_map", None)
                                  or {}).get(_tid_a) or [])):
                            _stage_bereit += 1
                    # Aufteilung in Blaupausen-Jobs - MIT Runs-Deckel je Job
                    # (`max_runs` aus schedule_build: BPC-Runs / SDE-Limit),
                    # kein Teil groesser als eine Kopie hergibt (17 -> 10 + 7).
                    njobs, parts = self._bp_teile(R, njobs, a.get("max_runs"),
                                                  a.get("parts"))
                    # Klare, schnell lesbare Blaupausen-Angabe: wie viele BPs muss
                    # ich diesem Char geben und mit wie vielen Runs je BP. Bei
                    # ungleichen Runs die Gruppen zeigen, z. B. "5×42 / 1×43 Runs".
                    if njobs == 1:
                        bp_txt = f"1 Blueprint \u00b7 {R} Runs"
                    else:
                        from collections import Counter as _Cnt
                        cnt = _Cnt(parts)
                        # nach Run-Zahl absteigend gruppieren
                        grp = " / ".join(f"{n}\u00d7{runs}"
                                         for runs, n in sorted(cnt.items(), reverse=True))
                        bp_txt = f"{njobs} Blueprints \u00b7 {grp} Runs"
                    # KEIN ZWEITER WEG ZUM ZUSTAND (Rotprobe-Fund,
                    # Sitzung 14): hier stand ein zweiter Block, der den
                    # Zustand nochmals aus `_bd_runplan_hidden` bestimmte.
                    # Er war VOLLSTAENDIG REDUNDANT - `_rest_budget` oben
                    # entsteht aus genau denselben Zahlen (geliefert +
                    # laufend, gedeckelt auf die Plan-Runs des Items). Ist
                    # `_bd_runplan_hidden[tid]` gesetzt, ist das Budget also
                    # zwangslaeufig voll und jede Zuteilung landet bei R <= 0.
                    # Aufgefallen ist es, weil eine Mutation den Block
                    # abklemmte und KEINE einzige Pruefung rot wurde: er
                    # aenderte nichts mehr. Zwei Stellen mit derselben
                    # Meinung sind zwei Wahrheiten, die auseinanderlaufen
                    # koennen - deshalb bleibt nur der Weg ueber das
                    # Rest-Budget.
                    _tid_total_runs = _runs_by_tid.get(a["tid"], 0) or 0
                    _surp_total = _surplus_all.get(a["tid"], 0) or 0
                    _surp_here = (round(_surp_total * (a["runs"] / _tid_total_runs))
                                 if _surp_total and _tid_total_runs else 0)
                    iit = QTreeWidgetItem([a["name"], f"{R:,}".replace(",", "'"),
                                           bp_txt, self._fmt_dur(a.get("seconds", 0)),
                                           _stufe_label(a),
                                           (f"+{_surp_here:,}".replace(",", "'")
                                            if _surp_here else "\u2013")])
                    iit.setTextAlignment(1, Qt.AlignCenter)   # Runs mittig
                    if _weg:
                        # NICHTS VERSCHWINDET SPURLOS: die Zeile zeigt den
                        # REST, der Tooltip nennt Plan und bereits Gebautes.
                        iit.setForeground(1, QColor(theme.CYAN))
                        iit.setToolTip(
                            1, _txt("{rest} of {plan} runs still open \u2013 {done} "
                                 "already delivered or currently building "
                                 "(seen via ESI). The frozen plan itself stays "
                                 "unchanged.").format(
                                     rest=f"{R:,}".replace(",", "'"),
                                     plan=f"{R_plan:,}".replace(",", "'"),
                                     done=f"{_weg:,}".replace(",", "'")))
                    iit.setTextAlignment(3, Qt.AlignRight | Qt.AlignVCenter)  # Zeit rechts
                    iit.setTextAlignment(5, Qt.AlignCenter)
                    if _surp_here:
                        iit.setForeground(5, QColor(theme.AMBER))
                        iit.setToolTip(5, _txt(
                            "{n} units surplus in total for this item (reaction batch "
                            "size) - split here proportionally by runs."
                        ).format(n=int(round(_surp_total))))
                    iit.setFlags(iit.flags() | Qt.ItemIsUserCheckable)
                    _ckey_item = f"{stage}|{cid}|{a['tid']}{_wsuf}"
                    iit.setData(0, Qt.UserRole + 6, _ckey_item)
                    # HAND-HAEKCHEN FUER DIE EINKAUFSLISTE MERKEN (Sitzung 16,
                    # Nutzer: "die Einkaufsliste zeigt absurd viele
                    # Materialien ... die ich schon hergebaut habe").
                    # `_bd_runplan_delivered` traegt NUR ESI-gelieferte Runs.
                    # Wer von Hand abhakt (weil ESI den Job nicht mehr sieht
                    # oder er ausserhalb lief), galt fuer den Restbedarf
                    # weiter als OFFEN - und das Material stand wieder auf
                    # der Liste. Diese Zuordnung Schluessel -> (Item, Runs)
                    # macht die Haken fuer `_restbedarf_jetzt` lesbar.
                    self._bd_runplan_runs_by_key[_ckey_item] = (
                        int(a["tid"]), int(a.get("runs") or 0))
                    # HAKEN UEBERLEBEN EINE UMVERTEILUNG (Nutzer 24.09.2026):
                    # kennt der Plan noch offene "erledigte Runs" dieses
                    # Items, bekommt diese Zeile den Haken zurueck, auch wenn
                    # sie jetzt einem anderen Charakter gehoert. Der
                    # Zeitstempel wandert mit - ohne ihn duerfte die
                    # mitlaufende Reservierung nichts freigeben.
                    _k_erl = f"{stage}|{int(a['tid'])}"
                    # ERST die wirklich gehakten Zeilen, dann der Rest
                    # (`haken_nachtragen`, vorab je Stufe berechnet)
                    if _ckey_item in _haken_neu and _ckey_item not in _checked_set:
                        _checked_set.add(_ckey_item)
                        _cs_alle = getattr(self, "_bd_runplan_checked", None)
                        if _cs_alle is not None:
                            _cs_alle.add(_ckey_item)
                        _tsm_e = getattr(self, "_bd_runplan_ts", None)
                        if _tsm_e is not None and _ckey_item not in _tsm_e:
                            _tsm_e[_ckey_item] = float(
                                (getattr(self, "_bd_runplan_erledigt_ts", None)
                                 or {}).get(_k_erl) or _zeit_mod.time())
                    if _ckey_item in _checked_set:
                        iit.setCheckState(0, Qt.Checked)
                        _apply_struck(iit)
                        # HIER STAND EIN ZWEITER WEG ZUM GRUENEN PUNKT -
                        # ENTFERNT (Nutzer-Freigabe, Sitzung 14: "das mit dem
                        # Runplaner mach mal so").
                        #
                        # Er verglich `geliefert + laufend` (Stand des GANZEN
                        # Items) gegen `a["runs"]` (Runs NUR DIESER
                        # Zuteilung). Das ist ein anderer Massstab als der
                        # Zustands-Weg oben, der das Rest-Budget ueber alle
                        # Zuteilungen des Items verteilt. Bei einem Item, das
                        # auf MEHRERE Charaktere aufgeteilt ist, sagte der
                        # alte Weg deshalb zu frueh "fertig": sind 50 von 100
                        # Runs geliefert und je 50 auf zwei Charaktere
                        # verteilt, gilt 50 >= 50 fuer BEIDE Zeilen - beide
                        # bekamen den gruenen Punkt, obwohl nur die Haelfte
                        # gebaut ist. Mit dem Punkt verschwindet das
                        # Kaestchen, der Nutzer koennte seinen eigenen Haken
                        # auf der offenen Zeile also nicht mehr loesen.
                        # Nach Regel 3 ist das die unsichere Richtung.
                        #
                        # Dass der Fall ihn trifft, ist belegt: in seinem
                        # Vagabond-Plan steht Ferrogel bei Elrasier mit 19
                        # und bei Peanut Motor mit 4 Runs.
                        #
                        # Die Rotprobe hatte den Block unabhaengig als
                        # ueberfluessig ausgewiesen: die Mutation, die ihn
                        # abklemmt, machte KEINE einzige Pruefung rot
                        # (Fehlerliste leer) - dieselbe Signatur wie beim
                        # redundanten `_bd_runplan_hidden`-Block. Der
                        # Zustands-Weg oben setzt den Punkt ohnehin, nur mit
                        # dem richtigen Massstab.
                        # Von Hand gestrichen (NUR der Nutzer streicht,
                        # seine Entscheidung Sitzung 8): KEIN automatisches
                        # Entstreichen - ESI-Jobs erscheinen verzoegert, und
                        # der Strich ist seine Arbeitsnotiz. Der Tooltip
                        # ordnet ehrlich ein, was ESI dazu sieht.
                        if not iit.toolTip(0):
                            _del_n = (getattr(self, "_bd_runplan_delivered",
                                              None) or {}).get(a["tid"], 0)
                            iit.setToolTip(0, (_txt("Ticked by hand. ESI: ")
                                               + (_txt("{n} runs delivered.").format(n=_del_n)
                                                  if _del_n else
                                                  _txt("no delivered jobs seen for it yet "
                                                       "(may lag behind)."))))
                    else:
                        iit.setCheckState(0, Qt.Unchecked)
                        # TEILFORTSCHRITT sichtbar machen: ESI hat schon
                        # geliefert, aber noch nicht alle Plan-Runs - genau
                        # das "in der Bauschleife"-Signal des Nutzers.
                        _del_n = ((getattr(self, "_bd_runplan_delivered",
                                            None) or {}).get(a["tid"], 0)
                                  + sum(int(_jj.get("runs") or 0) for _jj in
                                        ((getattr(self, "_bd_active_jobs_map",
                                                  None) or {})
                                         .get(a["tid"]) or [])))
                        if _del_n:
                            # ESI-N/M AUS DER ZEILE ENTFERNT (Nutzer,
                            # Sitzung 9: "unnoetige Info" - und berechtigt
                            # verwirrend: die Zahl ist der GLOBALE Stand des
                            # Items ueber ALLE Plaene/Jobs, nicht der Anteil
                            # dieser Zeile; bei reservierten Items in
                            # mehreren Bauplaenen zeigt jeder Plan dieselbe
                            # Zahl). Punkt + Faerbung bleiben als Signal,
                            # das Detail steht im Tooltip auf Abruf.
                            iit.setForeground(0, QColor(theme.CYAN))
                            iit.setToolTip(0, _txt(
                                "ESI sees {seen} runs of this item (delivered or in the "
                                "build pipeline, across ALL plans) \u2013 this row needs "
                                "{need}. Once fully covered, the item is HIDDEN from "
                                "the plan."
                            ).format(seen=_del_n, need=int(a.get('runs') or 0)))
                        # LAEUFT, GEHOERT ABER NOCH KEINEM PLAN (Nutzer
                        # 28.09.2026): zaehlt nirgends als erledigt - die
                        # Zeile sagt es, damit niemand denselben Job ein
                        # zweites Mal startet.
                        _unz = ((getattr(self, "_bd_active_unzugeordnet", None)
                                 or {}).get(a["tid"]) or [])
                        if _unz:
                            iit.setText(0, iit.text(0) + " " + _txt(
                                "(running: {n} runs, not assigned to a plan yet)"
                            ).format(n=sum(int(_ju.get("runs") or 0) for _ju in _unz)))
                            iit.setToolTip(0, _txt(
                                "A job for this item is running, but more than one "
                                "plan builds it and it is not assigned yet. It "
                                "counts for no plan until you assign it (button "
                                "\u201e\u2026 not assigned \u2013 assign\u201c)."))
                    _cname_here = cmap.get(cid, str(cid))
                    _active_all = (getattr(self, "_bd_active_jobs_map", None)
                                  or {}).get(a["tid"]) or []
                    # NUR die Einträge, die zu DIESEM Charakter gehören - sonst
                    # markierte ein einzelner laufender Job (z.B. bei Elrasier)
                    # fälschlich JEDE Zeile desselben Items bei ALLEN anderen
                    # Charakteren als "läuft gerade" mit, obwohl nur einer es
                    # wirklich tut.
                    _active = [j for j in _active_all if j.get("char") == _cname_here]
                    # DIESELBE ZUORDNUNG WIE BEIM LAUF-PUNKT (Sitzung 16):
                    # sonst sagen Punkt und "(building)" Verschiedenes - genau
                    # der Widerspruch, den der Nutzer gesehen hat.
                    if _active and self._job_gehoert_anderem_plan(
                            a["tid"], _fremd_res, eigene=_eigene_res):
                        _active = []
                    # NUR MARKIEREN, WENN DIE JOBS ZU DIESER ZEILE PASSEN
                    # (Nutzer, Sitzung 9: "Es koennte ja sein, dass das Item
                    # in der Bauschleife ist fuer einen ANDEREN Bauplan").
                    # Sein Kriterium: exakt die Menge und/oder die richtigen
                    # Runs wie im Plan. Umsetzung: die geplante Aufteilung
                    # dieser Zeile ist aus runs/jobs herleitbar (dieselbe
                    # Rechnung wie die Blaupausen-Anzeige); ein laufender
                    # Job zaehlt nur, wenn seine Run-Zahl in diese Aufteilung
                    # passt (Teilmenge mit Vielfachheit - auch teilweise
                    # gestartete Kopien-Saetze passen) ODER die Summe aller
                    # laufenden Jobs exakt der Zeilen-Menge entspricht
                    # (anders geschnitten, aber dieselbe Bestellung). Fremde
                    # Jobs (falsche Run-Zahlen) markieren NICHTS mehr - die
                    # globale Aktivitaet zeigt weiterhin die CYAN-Faerbung
                    # samt Tooltip oben.
                    if _active:
                        _pl_runs9 = int(a.get("runs") or 0)
                        # DIESELBE Aufteilung wie die Blaupausen-Anzeige
                        # (inkl. Runs-Deckel je Job) - eine Rechnung.
                        _split9 = self._bp_teile(
                            _pl_runs9, a.get("jobs"), a.get("max_runs"),
                            a.get("parts"))[1]
                        _lauf9 = [int(j.get("runs") or 0) for j in _active]
                        _rest9 = list(_split9)
                        _passt9 = True
                        for _x9 in _lauf9:
                            if _x9 in _rest9:
                                _rest9.remove(_x9)
                            else:
                                _passt9 = False
                                break
                        # TEILWEISE GESTARTET ZAEHLT AUCH (Nutzer-Befund
                        # 24.09.2026, Screenshot der Bauschleife: ingame
                        # laufen 64 Runs Titanium Carbide, die Zeile
                        # verlangt 130 - und blieb voellig unmarkiert).
                        # Die alten zwei Regeln verlangten, dass die
                        # laufenden Jobs GENAU in die geplante Aufteilung
                        # passen oder die Zeile voll decken. Seit man die
                        # Zeit je Stufe einstellen kann, schneidet der Plan
                        # aber anders als das Spiel (130 in EINEM Job gegen
                        # 5 Jobs a 13) - dann traf keine der beiden Regeln
                        # mehr zu, obwohl die Arbeit sichtbar laeuft.
                        # Weniger als die Zeile braucht ist kein Widerspruch,
                        # sondern der Normalfall eines angefangenen Satzes.
                        _teil9 = 0 < sum(_lauf9) < _pl_runs9
                        if not _passt9 and sum(_lauf9) != _pl_runs9 and not _teil9:
                            _active = []
                    if _active:
                        _ready = [j for j in _active if j.get("status") == "ready"]
                        _running = [j for j in _active if j.get("status") != "ready"]
                        if _ready and not _running:
                            # Fertig, aber noch nicht abgeliefert: grün markieren -
                            # der Output existiert schon, er muss nur ins Lager.
                            _green = QColor(theme.GREEN)
                            for c in range(tbl.columnCount()):
                                iit.setForeground(c, _green)
                            _who = ", ".join(f"{j.get('runs') or '?'} Runs"
                                             for j in _ready)
                            iit.setToolTip(0, _txt(
                                "\u2705 DONE per ESI at {name} ({who}) - only DELIVER in "
                                "game now. It can then take up to 1 h until ESI updates "
                                "the stock (CCP cache)."
                            ).format(name=_cname_here, who=_who))
                            iit.setText(0, "\u2705 " + iit.text(0))
                        else:
                            # "WIRD GEBAUT" (Nutzer-Wunsch Sitzung 12).
                            #
                            # Frueher: violettes Symbol vor dem Namen. Violett
                            # ist aber die Farbe der Reaktions-STUFE - ein
                            # laufender Job ist ein ZUSTAND. Zwei verschiedene
                            # Aussagen in derselben Farbe verwirren.
                            #
                            # Jetzt: eigene Farbe + Klartext hinter dem Namen.
                            # Beides verschwindet, sobald der Job fertig ist -
                            # die Zeile sieht dann wieder normal aus.
                            _lauf = QColor(theme.CYAN_RUN)
                            for c in range(tbl.columnCount()):
                                iit.setForeground(c, _lauf)
                            _who = ", ".join(
                                f"{j.get('runs') or '?'} Runs"
                                + (t(" (ready!)") if j.get("status") == "ready" else "")
                                for j in _active)
                            iit.setToolTip(0, _txt(
                                "Already running according to ESI at {who} "
                                "({what}) - before starting this again, check "
                                "whether it is already enough.").format(
                                    who=_cname_here, what=_who))
                            # WIE VIEL laeuft, wenn es weniger ist als die
                            # Zeile braucht - sonst sagt "(building)" dasselbe
                            # bei 5 wie bei 130 Runs.
                            _lauf_n9 = sum(int(j.get("runs") or 0) for j in _active)
                            _soll_n9 = int(a.get("runs") or 0)
                            # VOLL GEDECKT (Nutzer 26.09.2026): bei 0 offenen
                            # Runs zeigt die Zeile ihre PLAN-Runs (Rueckblick),
                            # und "(building 16/40)" las sich wie "24 fehlen
                            # noch". Sind Plan-Runs = geliefert + laufend,
                            # steht jetzt die ganze Rechnung des ITEMS da.
                            _gel_i9 = int((getattr(self, "_bd_runplan_delivered",
                                                   None) or {}).get(_tid_a, 0) or 0)
                            _lauf_i9 = sum(
                                int(_j.get("runs") or 0) for _j in
                                ((getattr(self, "_bd_active_jobs_map", None)
                                  or {}).get(_tid_a) or []))
                            _plan_i9 = int(_plan_runs_tid.get(_tid_a, 0) or 0)
                            if _weg >= R_plan and _plan_i9 > 0 and \
                                    _gel_i9 + _lauf_i9 >= _plan_i9:
                                iit.setText(0, iit.text(0) + " " + _txt(
                                    "(covered \u2713 {plan}/{plan}: {gel} delivered "
                                    "\u00b7 {lauf} running)").format(
                                        plan=_plan_i9, gel=_gel_i9, lauf=_lauf_i9))
                            else:
                                iit.setText(0, iit.text(0) + " " + (
                                    _txt("(building {n}/{m})").format(
                                        n=_lauf_n9, m=_soll_n9)
                                    if 0 < _lauf_n9 < _soll_n9 else _txt("(building)")))
                    # Aktivität merken (für "Blueprint-Name kopieren": Reaktion vs
                    # Fertigung -> "Reaction Formula" bzw. "Blueprint").
                    iit.setData(0, Qt.UserRole + 7, a.get("activity"))
                    iit.setData(0, Qt.UserRole + 12, int(a["tid"]))   # Stock locations (emm459)
                    _ez_n = (getattr(self, "_bd_ende_als_zutat", None) or {}).get(
                        int(a.get("tid") or 0))
                    if _ez_n is not None:
                        iit.setText(0, iit.text(0) + " \u00b7 " + _txt(
                            "also end product: {n}").format(
                                n=f"{int(_ez_n):,}".replace(",", "'")))
                        iit.setToolTip(0, _txt(
                            "This end product is also an ingredient of another "
                            "end product in the bundle, so it is built in this "
                            "earlier stage. {n} of it stay as end product, the "
                            "rest goes into the other end products.").format(
                                n=f"{int(_ez_n):,}".replace(",", "'")))
                    # Der Blaupausen-Name haengt an der Zeile - fuer
                    # Rechtsklick/Strg+C (der Linksklick-Kopierweg ist seit
                    # emm401 raus: er kopierte, ohne den Run-Klick zu merken).
                    # EINE Quelle fuer den Namen: _bp_name_fuer, dieselbe
                    # Regel wie im Rechtsklick-Menue und in der BP-Spalte.
                    iit.setData(0, ROLLE_KOPIERNAME,
                                self._bp_name_fuer(
                                    self._bp_basisname(a.get("tid"), a.get("name")),
                                    a.get("activity")))
                    # KLICK-WERTE DER ZEILE (emm402): Rueckfall = volle
                    # Run-Zahl; kennt die Zeile Kopien-Teile, ueberschreibt
                    # der Knopf-Block unten mit den Werten je Kopie.
                    iit.setData(0, Qt.UserRole + 9,
                                [(int(a.get("tid") or 0), int(a.get("runs") or 0),
                                  a.get("activity") in (9, 11))])
                    # RUNS FETT (Nutzer, 15.09.2026): das ist die Zahl, nach
                    # der man ingame den Job einstellt - sie soll sich vom
                    # Rest der Zeile abheben.
                    _fr = iit.font(1)
                    _fr.setBold(True)
                    iit.setFont(1, _fr)
                    # BP-Spalte hervorheben, wenn mehr als 1 BP nötig (das ist die
                    # Info, wie viele Blueprints du aufteilen musst).
                    fb = iit.font(2)
                    fb.setBold(njobs > 1)
                    iit.setFont(2, fb)
                    if njobs > 1:
                        iit.setForeground(2, QColor(theme.AMBER))
                        iit.setToolTip(2, _txt(
                            "{name}: split {runs} runs across {n} blueprints ("
                        ).format(name=a["name"], runs=R, n=njobs)
                                       + "+".join(str(p) for p in parts)
                                       + _txt(" = {runs}). ~{n}\u00d7 faster than 1 BP."
                                              ).format(runs=R, n=njobs))
                    else:
                        iit.setForeground(2, QColor(theme.MUTED))
                    bp = recipes.product_to_bp.get(a["tid"])
                    # ZUTATEN AUS DEM PLAN, nicht nachgerechnet (Sitzung 13):
                    # die alte Rechnung hier kannte nur den globalen
                    # Fertigungs-ME und setzte Reaktionen auf 1,0 - der Baum
                    # zeigte 1'000 Vanadium, der Materialien-Reiter 980.
                    # plan_mats_pro_run liefert die Menge je Run aus
                    # build_mats; Rueckfall auf die Nachrechnung nur, wenn ein
                    # alter Schnappschuss keine build_mats hat.
                    # OFFENE Runs, nicht die Plan-Runs (Sitzung 13): steht in
                    # der Zeile "5'000 Runs offen", muss die Zutat darunter die
                    # Menge fuer 5'000 Runs nennen. Sonst widerspricht das
                    # Kind seiner eigenen Elternzeile - genau die Sorte
                    # Doppel-Wahrheit, die der Nutzer gemeldet hat.
                    _pr = industry.plan_mats_pro_run(plan, a["tid"])
                    if _pr is not None:
                        _zut = [(m, pr * int(R)) for m, pr in _pr]
                    elif bp:
                        bp_id, activity, _oq = bp
                        mfac = (1 - me_pct / 100.0) if activity == industry.MANUFACTURING else 1.0
                        _zut = [(m, industry.material_menge(bq, R, mfac))
                                for m, bq in recipes.bp_materials.get((bp_id, activity), [])]
                    else:
                        _zut = []
                    for mat_id, q in _zut:
                        mit = QTreeWidgetItem([names.get(mat_id, f"#{mat_id}"),
                                               f"{int(q):,}".replace(",", "'"),
                                               "", "", ""])
                        mit.setTextAlignment(1, Qt.AlignCenter)
                        mit.setForeground(0, QColor(theme.MUTED))
                        mit.setForeground(1, QColor(theme.MUTED))
                        mit.setData(0, Qt.UserRole + 12, int(mat_id))  # Stock locations (emm459)
                        # NIE ABHAKBAR (Nutzer, 15.09.2026, mit Zoom-Bild:
                        # "dieser gruene Haken ist nicht von mir, den kann
                        # ich nicht setzen ... ich kann ihn auch nicht
                        # wegmachen"). Eine Material-Unterzeile ist eine
                        # Stueckliste, keine Entscheidung - sie hatte nie ein
                        # Kaestchen und soll auch keins bekommen.
                        #
                        # WARUM SIE TROTZDEM EINS BEKAM: QTreeWidgetItem
                        # traegt Qt.ItemIsUserCheckable BEREITS in seinen
                        # Standard-Flags (nachgemessen). Sichtbar wird ein
                        # Kaestchen zwar erst mit CheckStateRole - aber die
                        # Kinder-Kaskade in _on_sched_check ("hake ich den
                        # Charakter ab, sollen seine Positionen mit") fragte
                        # nur die Flags ab und setzte dann setCheckState.
                        # Damit malte sie den Stuecklisten-Zeilen ein
                        # Kaestchen samt Haken hin, und ein Loesen liess das
                        # LEERE Kaestchen stehen (CheckStateRole ist dann 0,
                        # nicht mehr None) - genau der Haken, der "von
                        # niemandem" kam und nicht wegging.
                        mit.setFlags(mit.flags() & ~Qt.ItemIsUserCheckable)
                        iit.addChild(mit)
                    # ---- ZUSTAND ANWENDEN: PUNKT STATT KAESTCHEN, GEDIMMT ---
                    # GANZ ZUM SCHLUSS, damit es die Faerbungen davor
                    # (CYAN_RUN, GREEN, AMBER) bewusst ueberschreibt - sonst
                    # haetten zwei Stellen eine Meinung zur selben Zeile und
                    # es entstuenden wieder zwei Wahrheiten.
                    #
                    # WARUM DAS KAESTCHEN VERSCHWINDET: "Abhacken kann ja nur
                    # ich" - ein Kaestchen ist eine offene Entscheidung. Ist
                    # die Position von ESI belegt, gibt es nichts mehr zu
                    # entscheiden, und ein Kaestchen saehe wieder nach Arbeit
                    # aus. Das war der ganze Ausgangspunkt.
                    #
                    # UNABHAENGIG VOM HAKEN (Nutzer: "das muss auch
                    # funktionieren ob ich etwas gehackt habe oder nicht"):
                    # bis Sitzung 13 hing `icons.gruener_punkt()` INNERHALB
                    # von `if _ckey_item in _checked_set:` - ohne eigenen
                    # Haken also kein Punkt. Aufgefallen ist das nie, weil
                    # voll gedeckte Zeilen ohnehin ausgeblendet wurden. Jetzt
                    # entscheidet allein der ESI-Befund.
                    if _zustand is not None:
                        # DAS KAESTCHEN BLEIBT (Nutzer-Entscheid 21.09.2026:
                        # "ist der Tool gruene Hacken da kann ich selber kein
                        # gruenen Hacken mehr setzen").
                        #
                        # WARUM DAS EIN MATERIAL-FEHLER WAR, nicht nur eine
                        # Unbequemlichkeit: der HAND-Haken ist die einzige
                        # Quelle, aus der `_reserve_map_mitlaufend` die
                        # Zutaten einer Zeile abbucht. Wurde das Kaestchen
                        # entfernt, sobald ESI die Zeile als fertig/laufend
                        # meldete, konnte fuer sie NIE ein Haken entstehen -
                        # und ihr Material blieb fuer immer reserviert.
                        # Nachgerechnet (aa384): mit Haken bleiben von
                        # 1'000 + 500 + 100 reservierten Einheiten nur die
                        # 100 des Erzeugnisses uebrig, ohne Haken alle 1'600.
                        # Je weiter ein Plan gebaut wurde, desto mehr Zeilen
                        # verloren ihr Kaestchen - ein fertiger Plan konnte
                        # sich per Bauart nicht mehr entlasten. Genau so kam
                        # ein laengst gebauter Plan dazu, 380'000 Einheiten
                        # festzuhalten und jeden Nachschub abzufangen.
                        #
                        # Der Entscheid aus Sitzung 14 bleibt gewahrt: die
                        # Zeile wird gedimmt und bekommt ihren Punkt, sie
                        # verschwindet nicht. Sie bleibt nur bedienbar.
                        if iit.data(0, Qt.CheckStateRole) is None:
                            iit.setCheckState(0, Qt.Unchecked)
                        # de_scan4: aus - interner Zustands-Schluessel
                        if _zustand == "fertig":
                            # de_scan4: an
                            iit.setIcon(0, icons.gruener_punkt())
                        else:
                            iit.setIcon(0, icons.lauf_punkt())
                            # UNSICHERE ZUORDNUNG BENENNEN (Nutzer, Sitzung
                            # 16): bauen zwei Plaene dasselbe Zwischen-
                            # produkt, beansprucht es jeder - dann laesst
                            # sich der Job nicht zuordnen und der Punkt
                            # bleibt. Statt eine Zuordnung vorzutaeuschen:
                            # kurz sagen, dass sie unsicher ist.
                            _mit_anspruch = self._plan_mit_anspruch(
                                _tid_a, _fremd_res)
                            # ZUGEORDNET = NICHT MEHR UNSICHER (emm418,
                            # Nutzer: "nach save assignment sind die
                            # Fragezeichen immer noch da"). Die Marke
                            # stammt aus Sitzung 16, VOR der Job-
                            # Zuordnung. Seit emm268 stehen im
                            # _bd_active_jobs_map eines GESPEICHERTEN
                            # Plans nur Jobs, die laut job_zuordnung
                            # DIESEM Plan gehoeren (Klick, eindeutig,
                            # Prioritaet oder Nutzer-Antwort) - der
                            # Anspruch des anderen Plans ist damit
                            # beantwortet. Nur ein UNGESPEICHERTER Plan
                            # kennt keine Zuordnung; dort bleibt die
                            # Marke ehrlich stehen.
                            if (_mit_anspruch
                                    and not getattr(self, "_bd_open_plan_id",
                                                    None)):
                                iit.setText(0, iit.text(0) + "  "
                                            + _txt("\u2753 could belong to "
                                                   "another build plan"))
                                iit.setToolTip(0, _txt(
                                    "A job for this item is running - but "
                                    "\u201e{plan}\u201c claims it too. ESI does not "
                                    "say which build plan a job belongs to."
                                ).format(plan=_mit_anspruch))
                        # GEDIMMT, ABER LESBAR: alle Spalten auf MUTED,
                        # einschliesslich der Material-Unterzeilen (die sind
                        # ohnehin schon MUTED). Der Nutzer will nachschlagen
                        # koennen, nicht raten muessen.
                        _dim = QColor(theme.MUTED)
                        for _c_z in range(tbl.columnCount()):
                            iit.setForeground(_c_z, _dim)
                        # WOFUER DAS KAESTCHEN JETZT NOCH GUT IST, und das
                        # muss dastehen - sonst sieht es nach Arbeit aus, die
                        # laengst erledigt ist (Regel 6).
                        _frei_tip = "\n" + _txt(
                            "Tick it once you are really done: that releases "
                            "the material this line still reserves for other "
                            "build plans.")
                        if not iit.toolTip(0):
                            iit.setToolTip(0, (_txt(
                                "Nothing left to do here \u2013 ESI has this "
                                "covered. The line stays so you can look up "
                                "later what was built and what it needed.")
                                # de_scan4: aus - interner Zustands-Schluessel
                                if _zustand == "fertig" else _txt(
                                # de_scan4: an
                                "Currently in the build queue according to "
                                "ESI \u2013 nothing to do here.")) + _frei_tip)
                        else:
                            iit.setToolTip(0, iit.toolTip(0) + _frei_tip)
                    citem.addChild(iit)
                    _stage_items += 1
                    _c_items += 1
                    if _zustand is not None:
                        _c_zustand += 1
                        if _zustand == "laeuft":
                            _c_laeuft += 1
                    # ERLEDIGT ist entweder ESI-belegt ODER vom Nutzer selbst
                    # abgehakt - seine Arbeitsnotiz zaehlt genauso, sonst
                    # bliebe eine von Hand durchgearbeitete Stufe fuer immer
                    # aufgeklappt.
                    if _zustand is not None or _ckey_item in _checked_set:
                        _stage_erledigt += 1
                    if _zustand == "laeuft":
                        _stage_laeuft += 1
                    # KOPIER-KNOEPFE fuer die Run-Zahlen (Nutzer, Sitzung 8):
                    # "ich moechte Buttons, in denen die Zahl steht - draufklicken
                    # kopiert sie ins Clipboard, damit ich ingame nichts tippen
                    # muss." Je VERSCHIEDENER Run-Zahl ein Knopf (bei
                    # '2x28 / 7x27' also zwei: 28 und 27), Reihenfolge wie im
                    # Text. Die Knoepfe leben in Spalte 2 NEBEN dem Text.
                    try:
                        # NUTZER (Sitzung 8): "es laesst sich nicht gut
                        # erkennen, wieviel mal ich 28 kopieren muss und
                        # wieviel mal 27 - es soll stehen 2x (28) 7x (27)."
                        # Also die ANZAHL direkt vor den Knopf, und der
                        # Knopf traegt nur noch die Zahl, die kopiert wird.
                        # Reihenfolge wie im alten Text: groesste Run-Zahl
                        # zuerst.
                        from collections import Counter as _Cnt2
                        _cnt2 = _Cnt2(parts)
                        _gruppen = sorted(_cnt2.items(), reverse=True)
                        if _gruppen:
                            _cw = QWidget()
                            _cl = QHBoxLayout(_cw)
                            _cl.setContentsMargins(0, 3, 0, 3)
                            _cl.setSpacing(3)
                            # DER BLAUPAUSEN-NAME IST JETZT ANKLICKBAR
                            # (Nutzer, Sitzung 20): "moechte ich auf
                            # Crystallite Alloy klicken und dann Crystallite
                            # Alloy Reaction Formula ins Clipboard bekommen."
                            # Die Run-Zahlen daneben tun das seit Sitzung 8;
                            # den Namen gab es nur ueber das Rechtsklick-Menue,
                            # und das findet man nicht.
                            _bp_nm = self._bp_name_fuer(
                                self._bp_basisname(a.get("tid"), a.get("name")),
                                a.get("activity"))
                            _kopf = QPushButton(
                                _txt("{n} blueprints").format(n=njobs))
                            _kopf.setCursor(Qt.PointingHandCursor)
                            _kopf.setMinimumHeight(24)
                            _kopf.setToolTip(
                                _txt("Click copies the blueprint name:")
                                + f"\n{_bp_nm}")
                            # GERAHMT WIE DIE RUN-ZAHLEN (Nutzer,
                            # 15.09.2026: "alle anderen blueprints die da
                            # vorkommen" sollen denselben kleinen Rahmen
                            # tragen). Vorher war der Rahmen erst beim
                            # Darueberfahren da - man sah dem Knopf nicht an,
                            # dass er ueberhaupt einer ist.
                            _kopf.setStyleSheet(
                                f"QPushButton{{background:{theme.PANEL2}; "
                                f"border:1px solid {theme.AMBER_DIM}; "
                                f"color:{theme.AMBER}; border-radius:5px; "
                                f"padding:0px 8px;}}"
                                f"QPushButton:hover{{border-color:"
                                f"{theme.AMBER}; background:{theme.PANEL};}}")
                            # AUCH DER NAME-KNOPF MERKT DIE ZUORDNUNG
                            # (emm402): je Kopien-Groesse ein Klick - wie
                            # die amber Runs-Knoepfe daneben.
                            iit.setData(0, Qt.UserRole + 9,
                                        [(int(a.get("tid") or 0), int(_r9),
                                          a.get("activity") in (9, 11))
                                         for _r9, _a9 in _gruppen])
                            _kopf.clicked.connect(
                                lambda _c=False, _nm=_bp_nm, _it9=iit: (
                                    self._copy_bp_name_value(_nm),
                                    self._runplan_klick_bei_kopie([_it9])))
                            _cl.addWidget(_kopf)
                            for _r, _anz in _gruppen:
                                _mal = QLabel(f"{_anz}\u00d7")
                                _mal.setStyleSheet(
                                    f"color:{theme.AMBER}; font-weight:700;")
                                _cl.addWidget(_mal)
                                _b = QPushButton(str(_r))
                                _b.setCursor(Qt.PointingHandCursor)
                                _b.setMinimumHeight(24)
                                _b.setToolTip(
                                    (_txt("{n} blueprints with {r} runs each.")
                                     if _anz != 1 else
                                     _txt("{n} blueprint with {r} runs.")).format(n=_anz, r=_r)
                                    + _txt("\nClick copies {r} \u2013 paste it into the "
                                           "\u201eRuns\u201c field in game (Ctrl+V).").format(r=_r))
                                _b.setStyleSheet(
                                    f"QPushButton{{background:{theme.PANEL2}; "
                                    f"border:1px solid {theme.AMBER_DIM}; "
                                    f"color:{theme.AMBER}; border-radius:5px; "
                                    f"padding:0px 10px; font-weight:700;}}"
                                    f"QPushButton:hover{{border-color:"
                                    f"{theme.AMBER}; background:{theme.PANEL};}}")
                                # DER KLICK WIRD GEMERKT (Stufe B, 21.09.2026).
                                # Er kopiert weiterhin nur die Zahl; zusaetzlich
                                # haelt das Tool fest, WELCHE Zeile welches
                                # Plans du gerade ins Spiel uebertraegst. Das
                                # ist die einzige Stelle, an der diese
                                # Zuordnung ueberhaupt entstehen kann - ESI
                                # liefert sie nicht.
                                # `activity` statt `stage`: die Unrefined-Stufe
                                # ist ebenfalls eine Reaktion (9/11), heisst
                                # aber nicht "reaction_x".
                                _b.clicked.connect(
                                    lambda _c=False, _v=_r, _n=a["name"],
                                    _t=a.get("tid"), _ak=a.get("activity"): (
                                        self._copy_runs_value(_v, _n),
                                        self._run_klick_merken(
                                            _t, _v, _ak in (9, 11))))
                                _cl.addWidget(_b)
                            _cl.addStretch()
                            # Der Text steckt jetzt IM Widget - die Spalte
                            # selbst leeren, sonst stuende er doppelt da.
                            iit.setText(2, "")
                            # NUTZER (zweimal gemeldet): "Knoepfe sind unten
                            # leicht abgeschnitten." Erster Versuch war eine
                            # GERATENE feste Hoehe (30 px) - zu knapp.
                            # Jetzt MESSEN statt raten: das fertige Widget
                            # nach seiner eigenen Wunschhoehe fragen und
                            # etwas Luft draufgeben. Damit passt es auch,
                            # wenn sich Schriftgroesse oder Knopf-Rahmen
                            # spaeter aendern.
                            _cw.adjustSize()
                            # DRITTER ANLAUF (Nutzer, 15.09.2026: "der Rahmen
                            # ist an der Unterkante etwas abgeschnitten").
                            # Mehr Luft UND dieselbe Hoehe fuer Spalte 0 -
                            # dort sitzt seit heute der Rahmen um den
                            # Formel-Namen, und die Zeilenhoehe richtet sich
                            # nach der GROESSTEN Wunschhoehe der Zeile.
                            _hoehe = max(34, _cw.sizeHint().height() + 10)
                            iit.setSizeHint(2, QSize(0, _hoehe))
                            iit.setSizeHint(0, QSize(0, _hoehe))
                            tbl.setItemWidget(iit, 2, _cw)
                    except Exception:
                        pass       # Knoepfe sind Komfort, nie kritisch
                # ---- CHARAKTER-ZEILE: PUNKT STATT KAESTCHEN, GEDIMMT -------
                # Dieselbe Regel wie eine Ebene tiefer, damit die Zeile nicht
                # das Gegenteil ihrer eigenen Kinder behauptet.
                # WELCHER PUNKT: laeuft auch nur EINE Position noch, ist der
                # Charakter nicht fertig - dann der Lauf-Punkt. Gruen erst,
                # wenn wirklich alles geliefert ist. Die vorsichtigere
                # Aussage gewinnt (Regel 3).
                if _c_items > 0 and _c_zustand == _c_items:
                    # KAESTCHEN BLEIBT - wie bei den Positionen darunter
                    # (Nutzer-Entscheid 21.09.2026, s. aa384). Es waere
                    # inkonsequent und in der Praxis muehsam, wenn man jede
                    # Position einzeln abhaken muesste, aber nicht mehr den
                    # ganzen Charakter auf einmal: der Sammel-Haken zieht die
                    # Positionen mit, und genau darueber gibt die
                    # Reservierung ihr Material frei.
                    if citem.data(0, Qt.CheckStateRole) is None:
                        citem.setCheckState(0, Qt.Unchecked)
                    citem.setIcon(0, icons.lauf_punkt() if _c_laeuft
                                  else icons.gruener_punkt())
                    _dim_c = QColor(theme.MUTED)
                    for _c_cc in range(tbl.columnCount()):
                        citem.setForeground(_c_cc, _dim_c)
                stage_item.addChild(citem)
                _stage_citems.append(citem)
            # ---- FERTIGE STUFE: ZUGEKLAPPT, ABER VOLLSTAENDIG -------------
            # NUTZER (Sitzung 14): "wie koennte man die darstellung schoener
            # machen fuer fertige Runs? aktuell kann ich da immernoch haken
            # setzen und es sieht aus als gaebe es noch was zu tun bei 2-4",
            # dazu "am liebsten solls weg sein. ich will wenn ich reactions
            # gemacht habe nurnoch komponents sehen" - und, wichtiger:
            # "imprinzip wird nie etwas mehr ausgeblendet nurnoch gedimmt".
            #
            # BEIDES ZUSAMMEN heisst ZUKLAPPEN, nicht wegnehmen (sein
            # Entscheid: "Zugeklappt - ein Klick holt alles zurueck"). Die
            # Charakter-Zeilen, die Item-Zeilen und ihre Material-Unterzeilen
            # bleiben also ALLE erhalten; die Stufe faltet sich nur auf ihre
            # Kopfzeile zusammen. So sieht er beim Arbeiten nur die offene
            # Stufe, kann aber jederzeit nachschlagen, was er gebaut hat und
            # was es gebraucht hat.
            #
            # WANN IST EINE STUFE FERTIG: wenn JEDE ihrer Positionen einen
            # Zustand hat - ESI-belegt (gebaut oder in der Bauschleife) oder
            # vom Nutzer selbst abgehakt. Bewusst NICHT "keine Zeilen mehr
            # da": seit dieser Sitzung wird nichts mehr ausgeblendet, es gibt
            # also immer Zeilen. Die alte Bedingung waere still nie wieder
            # wahr geworden - eine Zusage, die niemand mehr haelt.
            #
            # `_stage_items > 0` ist Absicht: eine Stufe ohne jede Position
            # ist nicht "fertig", sondern leer. Ohne die Bedingung bekaeme
            # sie faelschlich einen Haken.
            # ALLE POSITIONEN ABGEDECKT - aber "abgedeckt" heisst nicht
            # "fertig": laufende Jobs zaehlen mit, sind aber noch im Bau.
            _stufe_abgedeckt = (_stage_items > 0
                                and _stage_erledigt == _stage_items)
            # ECHT FERTIG ist die Stufe nur ohne laufende Position.
            _stufe_fertig = _stufe_abgedeckt and _stage_laeuft == 0
            # emm433: fertig + noch etwas abzuholen = "Bereit zum Ausliefern"
            # (bleibt farbig, es gibt noch zu tun); fertig + alles abgeholt
            # = "Erledigt", die ganze Stufe grau (Nutzer: "somit ist immer
            # nur das farbig, was zu erledigen gilt").
            from .mw_helpers import stufe_status
            _stufe_status = stufe_status(_stufe_abgedeckt, _stage_laeuft,
                                         _stage_bereit)
            if _stufe_abgedeckt:
                if _stufe_fertig:
                    stage_item.setText(0, f"\u2713  {label}" + (
                        "  (" + _txt("Ready to deliver") + ")"
                        if _stufe_status == "bereit" else
                        "  (" + _txt("Completed") + ")"))
                    # DER ZEIT-REGLER WEICHT DER MELDUNG: eine fertige Stufe
                    # stellt niemand mehr ein, und die Zeile soll sagen, was
                    # sie geschafft hat - nicht, was man haette einstellen
                    # koennen.
                    tbl.removeItemWidget(stage_item, 2)
                    stage_item.setText(2, _txt("finished \u00b7 {n} position(s) "
                                               "completed").format(
                                                   n=_stage_erledigt))
                else:
                    # IM BAU: derselbe Punkt und dieselbe Farbe wie bei den
                    # laufenden Kindzeilen - sonst sagt die Stufe etwas
                    # anderes als das, was darunter steht.
                    stage_item.setText(0, f"\u25cf  {label}")
                    stage_item.setText(2, _txt(
                        "in build \u00b7 {n} of {ges} position(s) running").format(
                        n=_stage_laeuft, ges=_stage_items))
                # DAUER RAUS: die Stufenzeit ist die GEPLANTE Dauer. In einer
                # fertigen Stufe liest man sie als "so lange dauert es noch" -
                # und genau das waere gelogen. Sie bleibt im Tooltip.
                stage_item.setToolTip(3, _txt("Planned duration of this stage "
                                              "was {d}.").format(
                                                  d=self._fmt_dur(dur)))
                stage_item.setText(3, "")
                stage_item.setText(4, "")     # Item-Art: hier ohne Belang
                _bg_f = QColor(stage_color); _bg_f.setAlpha(12)
                for _c_f in range(5):
                    stage_item.setBackground(_c_f, QBrush(_bg_f))
                    stage_item.setForeground(_c_f, QColor(theme.MUTED))
                # CYAN_RUN, nicht CYAN: die laufenden Kindzeilen nutzen
                # denselben Ton (icons.lauf_punkt -> theme.CYAN_RUN,
                # Nutzer-Entscheid Sitzung 14). Dieselbe Aussage, dieselbe
                # Farbe - sonst haette "laeuft" zwei Erscheinungsbilder.
                _stufe_farbe = (QColor(theme.GREEN) if _stufe_fertig
                                else QColor(theme.CYAN_RUN))
                stage_item.setForeground(0, _stufe_farbe)
                stage_item.setForeground(2, _stufe_farbe)
                if _stufe_status == "erledigt":
                    # ALLES GRAU: Text, Hintergrund, Symbol - keine Farbe mehr.
                    for _c_g in range(tbl.columnCount()):
                        stage_item.setForeground(_c_g, QColor(theme.MUTED))
                        stage_item.setBackground(_c_g, QBrush())
                    try:
                        _ic_g = stage_item.icon(0)
                        if not _ic_g.isNull():
                            stage_item.setIcon(0, QIcon(_ic_g.pixmap(18, QIcon.Disabled)))
                    except Exception:
                        pass
                    for _cf_g in _stage_citems:
                        for _c_g in range(tbl.columnCount()):
                            _cf_g.setForeground(_c_g, QColor(theme.MUTED))
                    stage_item.setData(0, Qt.UserRole + 11, "erledigt")
                elif _stufe_status == "bereit":
                    stage_item.setData(0, Qt.UserRole + 11, "bereit")
            # DIE ZAEHL-ZEILE IST WEG (Nutzer, Sitzung 14). Sie war das
            # Gegenstueck zum Ausblenden ("Regel 6: nichts verschwindet
            # spurlos") - sie fasste zusammen, was der Baum nicht mehr zeigte.
            # Seit nichts mehr ausgeblendet wird, steht jede Position wieder
            # selbst da, gedimmt und mit Punkt. Eine Zusammenfassung von
            # Zeilen, die daneben vollstaendig sichtbar sind, waere eine
            # zweite Wahrheit ueber dieselbe Sache.
            #
            # ZUGEKLAPPT, WENN FERTIG - offene Stufen bleiben offen.
            # AUFKLAPP-ZUSTAND DER CHARAKTER-ZEILEN (Nutzer-Screenshot,
            # Sitzung 14: "wo gibts jetzt da gruene punkte?"). Bei einer
            # OFFENEN Stufe bleiben sie zu wie bisher - dort zaehlt die
            # Uebersicht. Bei einer FERTIGEN Stufe ist es umgekehrt: sie ist
            # ohnehin zugeklappt, und wer sie aufklappt, will genau EINES
            # sehen - was gebaut wurde und was es gebraucht hat. Blieben die
            # Charakter-Zeilen dann auch noch zu, muesste er zweimal
            # aufklappen, um die Punkte ueberhaupt zu finden. Genau daran ist
            # er haengengeblieben.
            # ZUKLAPPEN HAENGT AN "ABGEDECKT", NICHT AN "FERTIG": eine Stufe
            # im Bau hat nichts zu tun und soll zu bleiben - genau so hat der
            # Nutzer sie gesehen ("die Ueberkategorie davon, wenn zugeklappt").
            # Haenge das Zuklappen an _stufe_fertig, klappte sie ploetzlich auf.
            # WAS DER NUTZER SELBST GEKLAPPT HAT, GEWINNT (`_klapp_vorher`,
            # s. oben): die Vorgabe gilt nur fuer Zeilen, die er nie
            # angefasst hat. Sonst klappte jeder Neuaufbau - und den loest
            # schon eine geaenderte Zielzeit aus - seine offene Zeile wieder
            # zu ("dann laedt es auch keine Runs").
            for _cf in _stage_citems:
                _k_cf = str(_cf.data(0, Qt.UserRole + 6) or "")
                _cf.setExpanded(bool(_klapp_vorher.get(_k_cf,
                                                       _stufe_abgedeckt)))
                # AUFGEKLAPPTE RUN-ZEILE BLEIBT AUF (emm400, Nutzer:
                # "Runplaner bei aufgeklappten Runs per character ist am
                # meisten betroffen"): gemerkt war der Klapp schon
                # (UserRole+6 -> _bd_sched_klapp), wiederhergestellt nie.
                # HIER und nicht beim addChild: setExpanded wirkt erst,
                # wenn die Zeile im Baum haengt (b102 war sonst rot).
                for _jx in range(_cf.childCount()):
                    _it_x = _cf.child(_jx)
                    _k_x = str(_it_x.data(0, Qt.UserRole + 6) or "")
                    if _k_x and _klapp_vorher.get(_k_x):
                        _it_x.setExpanded(True)
            # de_scan5: aus - interner Klapp-Schluessel, nie sichtbar
            stage_item.setExpanded(bool(_klapp_vorher.get(
                "stufe|" + str(stage), not _stufe_abgedeckt)))   # emm400
            # de_scan5: an
            if stage == _ub_nach:
                _unref_block()
        # ---- ℹ NICHT EINGEPLANT: Kauf billiger / Bestand deckt --------------
        # Nutzer-Fall Magpulse Thruster: eine baubare Komponente fehlte im
        # Runplaner und sah "vergessen" aus - in Wahrheit hatte der Plan sie
        # als KAUF eingestuft (Markt billiger als Bauen) bzw. der Bestand
        # deckte sie. Der Runplaner zeigte bisher NUR Bau-Zeilen; jetzt sagt
        # er ausdrücklich, was er bewusst NICHT einplant und warum - dieselbe
        # Ehrlichkeits-Regel wie die Swing-Trichterzeile.
        _built_tids = {a["tid"] for a in res["assignments"]}
        # Herkunft auch HIER ausweisen (Nutzer-Auftrag Punkt 2): „durch Bestand
        # gedeckt" ist eine andere Aussage, je nachdem ob die Zahl aus ESI, aus
        # einer eingefügten Liste oder aus der Job-Pipeline stammt.
        _src_map = getattr(self, "_bd_stock_src", None) or {}

        def _why_for(_tid, _kind):
            if _kind != "stock":
                return _txt("BUY \u2013 market cheaper than building "
                            "(is on the shopping list)")
            _i = _src_map.get(_tid) or {}
            if _i.get("src") == "manuell":
                return _txt("covered by PASTED stock ( Materials tab) \u2013 "
                            "nothing to do")
            if _i.get("job") and not _i.get("esi"):
                return _txt("covered by the pipeline (running/finished jobs) \u2013 "
                            "nothing to do")
            return _txt("covered by ESI stock \u2013 nothing to do")
        _info = [(_i, q, _why_for(_i, k)) for _i, q, k in
                 self._unscheduled_build_items(
                     plan, _built_tids,
                     # NICHT is_manufactured: das deckt nur MANUFACTURING ab
                     # und haette jede Reaktion aus dem "Nicht eingeplant"-
                     # Segment verschwinden lassen - obwohl der Plan sie
                     # bewusst kauft statt sie zu fahren. Genau die Zeile
                     # will der Nutzer sehen. Reaktionen sind selbst
                     # herstellbar, also gehoeren sie hier hin.
                     self._bd_producible_fn(recipes))]
        if _info:
            _ihdr = QTreeWidgetItem(
                [_txt("\u2139  Not planned \u2013 buying cheaper / stock covers ")
                 + _txt("({n} buildable items)").format(n=len(_info)), "", "", "", ""])
            _f = _ihdr.font(0); _f.setBold(True); _ihdr.setFont(0, _f)
            _mut = QColor(theme.MUTED)
            _ihdr.setForeground(0, _mut)
            _ihdr.setToolTip(0, _txt(
                "Buildable items the plan DELIBERATELY does not build: either buying "
                "at the current hub is cheaper than building (then they are on the "
                "shopping list), or your stock (incl. pipeline) covers the need. If "
                "an item you expected is missing here, THAT is the answer - not the "
                "plan forgetting it."))
            _shown = 0
            for _tid, _q, _why in _info:
                if _shown >= 40:
                    _more = QTreeWidgetItem(
                        [_txt("\u2026 and {n} more").format(n=len(_info) - _shown),
                         "", "", "", ""])
                    _more.setForeground(0, _mut)
                    _ihdr.addChild(_more)
                    break
                _iit = QTreeWidgetItem(
                    [names.get(_tid, f"#{_tid}"),
                     f"{_q:,}".replace(",", "'"), _why, "", ""])
                _iit.setTextAlignment(1, Qt.AlignCenter)
                for _c in range(3):
                    _iit.setForeground(_c, _mut)
                _ihdr.addChild(_iit)
                _shown += 1
            tbl.addTopLevelItem(_ihdr)
            # de_scan5: aus - interner Klapp-Schluessel, nie sichtbar
            _ihdr.setData(0, Qt.UserRole + 6, "stufe|info")
            _ihdr.setExpanded(bool(_klapp_vorher.get("stufe|info", False)))
            # de_scan5: an

        # --- SCIENCE-STUFEN: Kopieren + Invention (emm411, Nutzer "jaa";
        # Discord Robust: "adding the Invention into the build planner").
        # REINE ANZEIGE (v1, ohne Haken): nichts wird gespeichert, der Block
        # laesst sich rueckstandsfrei wieder ausbauen. Zahlen aus DERSELBEN
        # Quelle wie die Invention-Karte (_bd_invention_needs +
        # industry.kopien_aufteilung) - keine zweite Rechnung (Regel 9).
        # ANS ENDE gestellt (nach allen Stufen und der Info-Zeile): die
        # Stufen-Positionen (b7u: Repro = topLevelItem(0)) bleiben unberuehrt.
        try:
            self._science_block(tbl, names, _klapp_vorher)
        except Exception as _sb_e:
            self._log_exception("Runplaner: Science-Block", str(_sb_e))
        tbl.blockSignals(False)
