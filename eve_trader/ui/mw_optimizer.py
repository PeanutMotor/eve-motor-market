"""Optimierer, Markt-Charts und Orderbuch-Leiter des Bauplan-Fensters.

Schnitt 2 der main_window-Zerlegung (Sitzung 10). Herausgeloest sind die
fuenf Methoden hinter den Werkzeug-Knoepfen "Optimierer" und "Orderbuch-
genaue Materialkosten" samt der Voreinstellungs-Logik und der
Mengen-Nachrechnung:

  open_optimizer            Optimierer-Fenster inkl. der beiden Markt-Charts
  open_ladder_check         Orderbuch-genaue Materialkosten (Leiter-Pruefung)
  _build_preset_to_custom   Voreinstellung auf "Eigene" zuruecksetzen
  _apply_build_preset       Voreinstellung auf die Bau-Filter anwenden
  _refine_all_optimal_qty   optimale Menge fuer alle Treffer nachrechnen

Die Ruempfe sind WOERTLICH aus main_window.py verschoben, kein Zeichen
geaendert. Sie greifen weiter per `self.` auf MainWindow-Methoden zu
(`_tool_parent`, `_run`, `_show_tool_window`, `_flash_tip`, `_active_hub`,
`_active_hub_label`, `_hub_orders`, `_persist_window`,
`_register_tool_hub_label`, `_render_build`) - das loest sich zur Laufzeit
an der zusammengesetzten Klasse auf. Direkte `MainWindow.`-Bezuege gibt es
hier KEINE (vorher per AST geprueft), deshalb konnte alles unveraendert
umziehen.

`MinimizableDialog` liegt seit diesem Schnitt in `mw_basis.py` - haetten
wir es aus main_window geholt, waere es ein Zirkel-Import geworden
(main_window importiert dieses Mixin ja selbst). Gleicher Weg wie bei
`isk`/`NumericItem` in Sitzung 8.
"""
import pyqtgraph as pg
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDoubleSpinBox, QFrame, QHBoxLayout, QHeaderView,
                               QLabel, QPushButton, QSpinBox, QTableWidget,
                               QTableWidgetItem, QVBoxLayout)

from .. import config, esi, industry, store
from ..sprache import t
from ..workers import Worker
from . import icons
from . import theme
from .mw_basis import MinimizableDialog, NumericItem, isk


class Optimizer:
    """Mixin: Optimierer-, Chart- und Leiter-Fenster des Bauplan-Dialogs."""

    def open_optimizer(self):
        from ..sprache import t as _txt   # `t` ist hier lokal belegt
        recipes = getattr(self, "_bd_recipes", None)
        tid = getattr(self, "_bd_type", None)
        if not recipes or not tid:
            self._flash_tip(_txt("Calculate a build plan first ( Build plan)"))
            return
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
                                       QSpinBox, QDoubleSpinBox, QPushButton,
                                       QTableWidget, QTableWidgetItem)
        name = getattr(self, "_bd_name", None) or str(tid)
        # BUENDEL (Nutzer 26.09.2026: "Optimale Menge funktioniert bisher nur
        # auf 1 Endprodukt - entweder auf Multibauplaene anpassen oder
        # entfernen"): die Kurve "wie viel bauen?" gehoert zu EINEM Produkt
        # (Verkaufspreis, Markttiefe, Absorption sind je Item). Fuer ein
        # Buendel fragt der Optimierer deshalb JE ENDPRODUKT - Auswahl oben
        # im Fenster, gerechnet wird das gewaehlte Ende allein mit den
        # Rezepten und Einstellungen des Buendels (ME/TE je Ende, Decryptor,
        # "Eigene BPC" stecken in denselben opts). Die Buendel-ID selbst
        # (-1) darf nie an production_plan/ESI als "das Produkt" gehen: ihre
        # Menge ist fest 1, ein Verkaufspreis je "Buendel" waere sinnlos,
        # und die Markthistorie einer negativen ID gibt es nicht.
        _ist_buendel = (tid == industry.BUENDEL_ID)
        _enden_opt = []
        if _ist_buendel:
            # `_bd_names_ref` ist die Namensliste des Bauplans (27.09.2026:
            # hier stand `_bd_names`, das es nie gab -> Dropdown zeigte #IDs).
            _namen_b = getattr(self, "_bd_names_ref", None) or {}
            for _e in sorted(self._bd_enden(tid, recipes)):
                _enden_opt.append((int(_e), str(_namen_b.get(int(_e)) or f"#{_e}")))
            if not _enden_opt:
                self._flash_tip(_txt("Calculate a build plan first ( Build plan)"))
                return
            name = _enden_opt[0][1]
        # Bewusst KEINE Übernahme der Bauplan-Menge (_bd_qty): der Optimierer ist
        # rein item-abhängig, sonst lieferte dieselbe Anfrage je nach Hintergrund-
        # Menge unterschiedliche Kurven.
        dlg = MinimizableDialog(self._tool_parent()); dlg.setWindowTitle(_txt("Optimiser \u2013 {name}").format(name=name))
        dlg.resize(900, 860)
        v = QVBoxLayout(dlg); v.setContentsMargins(18, 14, 18, 14); v.setSpacing(9)

        head_card = QFrame(); head_card.setObjectName("Card")
        head_card.setStyleSheet(
            f"QFrame#Card {{ border: 1px solid rgba(79,209,122,0.4); }}")
        head_v = QVBoxLayout(head_card)
        head_v.setContentsMargins(14, 10, 14, 10); head_v.setSpacing(8)
        head_title = QLabel(_txt("OPTIMAL BUILD QUANTITY \u2013 {name}").format(name=name))
        head_title.setStyleSheet(
            f"color:{theme.GREEN}; font-size:13px; font-weight:800; letter-spacing:1px;")
        head_v.addWidget(head_title)
        head_desc = QLabel(_txt("Where is the unit cost lowest before buying the "
                                "materials on the market gets too expensive \u2013 and "
                                "where does the reaction batch divide up best?"))
        head_desc.setWordWrap(True); head_desc.setObjectName("Muted")
        head_v.addWidget(head_desc)
        row = QHBoxLayout()
        _ahub_lbl = QLabel(_txt("Hub: ") + self._active_hub_label())
        _ahub_lbl.setObjectName("Muted")
        _ahub_lbl.setToolTip(_txt(
            "The buy and sell hub is chosen at the top left of the "
              "tool and applies to all tabs."))
        self._register_tool_hub_label(_ahub_lbl)
        row.addWidget(_ahub_lbl)
        # ENDPRODUKT-WAHL nur beim Buendel (s. o.). Gemerkt fuer die b-Suite.
        ende_cb = None
        if _ist_buendel:
            row.addWidget(QLabel(_txt("End product:")))
            ende_cb = QComboBox()
            for _e, _n in _enden_opt:
                ende_cb.addItem(_n, _e)
            ende_cb.setToolTip(_txt(
                "A bundle has several end products; the quantity curve is "
                "calculated for ONE of them at a time (with the bundle's "
                "settings for that product)."))
            row.addWidget(ende_cb)
        self._opt_ende_cb = ende_cb

        def _produkt_tid():
            """Das Produkt, um das es geht: beim Buendel das gewaehlte Ende."""
            if ende_cb is not None:
                return int(ende_cb.currentData())
            return getattr(self, "_bd_type", None)
        row.addWidget(QLabel(_txt("Sale price/unit:")))
        sell_spin = QDoubleSpinBox(); sell_spin.setRange(0, 1_000_000_000_000)
        sell_spin.setDecimals(0); sell_spin.setGroupSeparatorShown(True)
        # de_scan3: aus  (Einheit, in beiden Sprachen gleich)
        sell_spin.setSuffix(" ISK"); sell_spin.setMinimumWidth(150)
        # de_scan3: an
        default_sell = float((getattr(self, "_bd_pricemap", None) or {}).get(
            _produkt_tid()) or 0.0)
        sell_spin.setValue(default_sell)
        if ende_cb is not None:
            # Beim Wechsel des Endes: Verkaufspreis und Titel des gewaehlten
            # Endes vorbelegen - die Kurve kommt erst mit "Berechnen".
            def _ende_gewechselt(*_a):
                _t = _produkt_tid()
                sell_spin.setValue(float((getattr(self, "_bd_pricemap", None)
                                          or {}).get(_t) or 0.0))
                _n = ende_cb.currentText()
                dlg.setWindowTitle(_txt("Optimiser \u2013 {name}").format(name=_n))
                head_title.setText(_txt("OPTIMAL BUILD QUANTITY \u2013 {name}").format(
                    name=_n))
            ende_cb.currentIndexChanged.connect(_ende_gewechselt)
        sell_spin.setToolTip(_txt(
            "Your actual sell price per unit – FIXED, independent of "
              "quantity (you sell at your own price, no price decay on "
              "selling is assumed). Pre-filled with the sell/unit price "
              "from the build plan dialog, editable here. It only "
              "determines where the curve stops automatically (at the "
              "loss point) – the recommended build quantity does not "
              "depend on it."))
        row.addWidget(sell_spin)
        row.addWidget(QLabel(_txt("Cargo hold/trip:")))
        vol = QSpinBox(); vol.setRange(0, 2_000_000_000); vol.setSingleStep(10000)
        # de_scan3: aus  (Einheit, in beiden Sprachen gleich)
        vol.setGroupSeparatorShown(True); vol.setSuffix(" m\u00b3")
        # de_scan3: an
        # `bau_freight_m3` stand hier als Fallback - UNERREICHBAR, seit
        # load_settings() die Defaults mergt (bau_transport_m3 existiert
        # immer) und nirgends geschrieben ("gelesen, aber nirgends
        # einstellbar"-Abgleich, Kandidat 1 von 5; die anderen vier waren
        # Fehlalarm). Der Alt-Schluessel ist mitsamt Default entfernt.
        vol.setValue(int(self.settings.get("bau_transport_m3", 350000)
                         or 350000))
        vol.setToolTip(_txt(
            "Cargo space PER TRIP for the SHOPPING LIST (build "
              "materials) – NOT for the finished ships/items, which are "
              "completed at the build location. 0 = freight trips are "
              "not calculated."))
        row.addWidget(vol)
        btn = QPushButton(_txt("Calculate"))
        btn.setIcon(icons.icon("check"))
        btn.setObjectName("Primary")
        btn.setMinimumHeight(34)
        btn.setStyleSheet("font-size:13px; font-weight:800; padding:6px 18px;")
        row.addWidget(btn)
        spin_lbl = QLabel("")
        spin_lbl.setStyleSheet(f"color:{theme.CYAN}; font-size:13px; font-weight:700;")
        row.addWidget(spin_lbl)
        row.addStretch()
        head_v.addLayout(row)
        v.addWidget(head_card)
        # DREI Antworten, bewusst getrennt: (1) Effizienz-Menge = kleinste Menge,
        # ab der die Stückkosten praktisch am Minimum sind (die eigentliche
        # "wie viel bauen"-Antwort -- verkaufsunabhängig). (2) Reaktions-Überschuss:
        # wo gehen die Chargen am besten auf (wenig Verschnitt). (3) Markt-
        # Absorption: wie viel verkauft sich wirklich (baumengenunabhängig).
        score_summary = QLabel("")
        score_summary.setWordWrap(True)
        score_summary.setStyleSheet(f"font-size:15px; font-weight:800; color:{theme.AMBER};")
        v.addWidget(score_summary)
        eff_summary = QLabel(_txt("Choose hub + sale price, then \u201eCalculate\u201c. The "
                                  "tool finds the upper end of the curve by itself."))
        eff_summary.setWordWrap(True)
        eff_summary.setStyleSheet(f"font-size:15px; font-weight:700; color:{theme.GREEN};")
        v.addWidget(eff_summary)
        surplus_summary = QLabel("")
        surplus_summary.setWordWrap(True)
        surplus_summary.setStyleSheet(f"font-size:13px; font-weight:600; color:{theme.VIOLET};")
        v.addWidget(surplus_summary)
        market_summary = QLabel("")
        market_summary.setWordWrap(True)
        market_summary.setStyleSheet(f"font-size:13px; font-weight:600; color:{theme.CYAN};")
        v.addWidget(market_summary)
        summary = QLabel("")
        summary.setObjectName("Muted")
        summary.setWordWrap(True); summary.setStyleSheet("font-size:13px;")
        v.addWidget(summary)

        import pyqtgraph as pg

        class _IskAxis(pg.AxisItem):
            """Y-Achse in lesbarem ISK-Format (25M / 1,2B) statt wissenschaftlicher
            Notation (2.5e+07) \u2013 dieselbe Kurzschreibweise wie sonst im Tool."""
            def tickStrings(self, values, scale, spacing):
                out = []
                for v in values:
                    av = abs(v)
                    if av >= 1e9:
                        s = f"{v / 1e9:.2g}".rstrip("0").rstrip(".") + "B"
                    elif av >= 1e6:
                        s = f"{v / 1e6:.0f}M"
                    elif av >= 1e3:
                        s = f"{v / 1e3:.0f}k"
                    else:
                        s = f"{v:.0f}"
                    out.append(s)
                return out

        def _make_chart(height, ylabel, iskaxis=True):
            """Normales Diagramm (KEIN Log-Modus \u2013 bei log wurden die Achsen
            unlesbar/verwirrend). Zoom ist auf den sinnvollen Datenbereich begrenzt
            (kein endloses Heraus-Zoomen), Rechtsklick setzt einfach die Ansicht
            zur\u00fcck statt ein technisches Men\u00fc zu \u00f6ffnen."""
            axis = {"left": _IskAxis(orientation="left")} if iskaxis else None
            c = pg.PlotWidget(axisItems=axis)
            c.setBackground(theme.PANEL2)
            c.setMinimumHeight(height)
            c.showGrid(x=True, y=True, alpha=0.15)
            c.getAxis("left").setTextPen(theme.MUTED)
            c.getAxis("bottom").setTextPen(theme.MUTED)
            c.setLabel("left", ylabel)
            c.setLabel("bottom", _txt("Quantity (units)"))
            vb = c.getPlotItem().getViewBox()
            vb.setMenuEnabled(False)             # kein Transforms/Downsample/... Men\u00fc

            def _reset_view(ev):
                if ev.button() == Qt.RightButton:
                    c.getPlotItem().enableAutoRange()
                    ev.accept()
            c.scene().sigMouseClicked.connect(_reset_view)
            return c, vb

        # Kurztitel je Chart (was zeigt die Kurve, in einem Satz) + Hover-Tooltip
        # (Crosshair mit Wertanzeige) -- gleiches Muster wie im Kursverlauf-Tab
        # (_on_mouse_move dort), hier lokal pro Chart mit eigenen Daten.
        _chart_data = {"xs": [], "profit": [], "cost": [], "rev": [], "surplus": []}

        def _chart_caption(text, color):
            lbl = QLabel(text)
            lbl.setStyleSheet(f"color:{color}; font-size:13px; font-weight:700;")
            lbl.setWordWrap(True)
            return lbl

        def _attach_hover(ch, fmt_fn):
            vline = pg.InfiniteLine(angle=90, pen=pg.mkPen(theme.MUTED, width=1,
                                                            style=Qt.DashLine))
            hline = pg.InfiniteLine(angle=0, pen=pg.mkPen(theme.MUTED, width=1,
                                                           style=Qt.DashLine))
            lbl = pg.TextItem(color=theme.TEXT, anchor=(0, 1), fill=pg.mkBrush(theme.PANEL2))

            def _readd():
                # chart.clear() (bei jeder Neu-Berechnung) entfernt ALLE Items,
                # auch diese hier -- deshalb nach jedem clear() erneut anhängen,
                # sonst zeigt der Hover nichts mehr (Referenz existiert, ist aber
                # nicht mehr in der Szene).
                ch.addItem(vline, ignoreBounds=True)
                ch.addItem(hline, ignoreBounds=True)
                ch.addItem(lbl, ignoreBounds=True)
                vline.hide(); hline.hide(); lbl.hide()
            _readd()

            def _on_move(pos):
                xs = _chart_data["xs"]
                if not xs or not ch.sceneBoundingRect().contains(pos):
                    vline.hide(); hline.hide(); lbl.hide()
                    return
                mp = ch.getViewBox().mapSceneToView(pos)
                idx = min(range(len(xs)), key=lambda i: abs(xs[i] - mp.x()))
                px = xs[idx]
                res = fmt_fn(idx, px)
                if res is None:
                    vline.hide(); hline.hide(); lbl.hide()
                    return
                text, py = res
                vline.show(); hline.show(); lbl.show()
                vline.setPos(px); hline.setPos(py)
                lbl.setText(text); lbl.setPos(px, py)
            ch.scene().sigMouseMoved.connect(_on_move)
            return _readd

        def _g(n):
            return f"{int(n):,}".replace(",", "'")

        # EINHEIT DES FENSTERS (Nutzer-Entscheid): bei Batch-Rezepten wird in
        # RUNS geredet, nicht in Stueck. Ein Run ist die kleinste Einheit, die
        # man im Spiel starten kann - Reaktionen liefern z.B. 2'200 Stueck pro
        # Run, T2-Munition 100. "20 Stueck bauen" ist dort keine
        # Handlungsanweisung. Die Stueckzahl bleibt als Klammerwert stehen,
        # weil Preise und Baukosten weiter je Stueck verglichen werden.
        # Kriterium ist die RUN-AUSGABE, nicht "ist Reaktion": Munition hat
        # dasselbe Problem und ist keine Reaktion.
        _obp0 = recipes.product_to_bp.get(tid)
        _opt_batch = int((_obp0[2] if _obp0 else 1) or 1)

        # EINHEIT BEIDER FENSTER: STUECK (Nutzer-Entscheid). Der Bauplan zeigt
        # "Menge 2200 - = 1 Run a 2200 Stk"; der Optimierer macht es genauso
        # herum: Stueckzahl fuehrt, die Run-Zahl steht als Zusatz dahinter.
        # Ein Zwischenstand hatte die Runs nach vorne gezogen - dann sagten die
        # beiden Fenster dasselbe auf zwei Arten, was schlimmer ist als die
        # urspruengliche Ungenauigkeit.
        # Was BLEIBT: die Stuetzstellen liegen auf ganzen Runs (weiter unten),
        # denn Mengen dazwischen gibt es im Spiel nicht. Nur benannt werden sie
        # jetzt wieder in Stueck.
        # Bei prod_qty == 1 (T2-Module, Schiffe - der Normalfall, der vorher
        # funktioniert hat) ist JEDE dieser Funktionen die Identitaet: gleiche
        # Ausgabe wie vor dem ganzen Reaktions-Umbau.
        def _qty_full(_q):
            """Menge fuer Fliesstext: '6'600 Stueck (= 3 Runs)' bzw. '20 Stueck'."""
            _q = int(_q)
            if _opt_batch <= 1:
                return _txt("{n} units").format(n=_g(_q))
            _r = -(-_q // _opt_batch)
            return (_txt("{n} units (= {r} run{s})").format(
                n=_g(_r * _opt_batch), r=_g(_r), s='s' if _r != 1 else ''))

        def _qty_short(_q):
            """Menge fuer Chart-Beschriftung - knapp, ohne Klammerwert."""
            return _txt("{n} units").format(n=_g(int(_q)))

        def _x_of(_q):
            """X-Wert der Charts. Die Achse laeuft in STUECK, also identisch
            fuer alle Rezepte - dadurch bleibt das T2-Verhalten unveraendert."""
            return int(_q)

        def _q_of_x(_x):
            """Umkehrung von _x_of - fuer die Hover-Beschriftung, die den
            X-Wert der Maus bekommt und daraus wieder eine Menge macht."""
            return int(round(float(_x)))

        v.addWidget(_chart_caption(
            _txt("Total profit \u2013 total profit by build quantity "
                 "(dots = efficiency quantity and "
                 "recommendation)"),
            theme.GREEN))
        chart, vb1 = _make_chart(190, _txt("Total profit (ISK)"))
        v.addWidget(chart)

        def _fmt_profit(idx, px):
            ys = _chart_data["profit"]
            if idx >= len(ys):
                return None
            return (f"{_qty_short(_q_of_x(px))}\n" + _txt("Profit: ") + isk(ys[idx]),
                    ys[idx])
        _readd1 = _attach_hover(chart, _fmt_profit)

        v.addWidget(_chart_caption(
            _txt("\u2696\ufe0f Cost vs. revenue per unit \u2013 your build cost "
                 "against your fixed sale price"), theme.AMBER))
        chart2, vb2 = _make_chart(150, _txt("ISK / unit"))
        chart2.setXLink(chart)   # gleiche Menge-Achse wie oben, gemeinsam zoombar
        chart2.addLegend(offset=(10, 10))
        v.addWidget(chart2)

        def _fmt_cost(idx, px):
            cost = _chart_data["cost"]; rev = _chart_data["rev"]
            if idx >= len(cost):
                return None
            txt = f"{_qty_short(_q_of_x(px))}\n" + _txt("Cost/unit: ") + isk(cost[idx])
            if idx < len(rev):
                txt += "\n" + _txt("Revenue/unit: ") + isk(rev[idx])
            return txt, cost[idx]
        _readd2 = _attach_hover(chart2, _fmt_cost)

        # Eigenes Chart für den Reaktions-Überschuss in % (andere Einheit als ISK,
        # deshalb NICHT in die ISK-Charts gemischt -- sonst wären beide unlesbar).
        v.addWidget(_chart_caption(
            _txt("\u267b\ufe0f Reaction surplus % \u2013 how much material is left over "
                 "from the reaction batches (less is better)"), theme.VIOLET))
        chart3, vb3 = _make_chart(130, _txt("Reaction surplus (%)"), iskaxis=False)
        chart3.setXLink(chart)
        v.addWidget(chart3)

        def _fmt_surplus(idx, px):
            ys = _chart_data["surplus"]
            if idx >= len(ys):
                return None
            return (f"{_qty_short(_q_of_x(px))}\n" + _txt("Surplus: ") + f"{ys[idx]:.1f} %",
                    ys[idx])
        _readd3 = _attach_hover(chart3, _fmt_surplus)

        # Kein eigenes 4. Chart (Gesamt-Score) mehr -- wirkte neben den anderen drei
        # nur verwirrend. Die Empfehlung bleibt als Text (score_summary) UND als
        # gelber Punkt im Gewinn-Chart sichtbar (sc_marker2 weiter unten).

        note = QLabel(_txt("Recommendation (best score) \u00b7 Efficiency "
                           "quantity (lowest unit cost)  \u00b7  \u26a0 Bottlenecks = material "
                           "not available at the hub in full depth (rest estimated "
                           "conservatively)"))
        note.setObjectName("Muted"); note.setWordWrap(True); v.addWidget(note)


        def compute():
            # Bauplan-Kontext frisch lesen -- so kann man im Hintergrund das
            # Endprodukt wechseln und hier bei offenem Fenster neu berechnen.
            cur_recipes = getattr(self, "_bd_recipes", None)
            cur_tid = _produkt_tid()
            if not cur_recipes or not cur_tid \
                    or not cur_recipes.product_to_bp.get(cur_tid):
                eff_summary.setText(_txt("Calculate a build plan first ( Build plan)."))
                return
            region, station, structure = self._active_hub()
            self.settings["bau_transport_m3"] = int(vol.value())
            config.save_settings(self.settings)
            freight = vol.value() or None
            sell_price = float(sell_spin.value())
            eff_summary.setText(_txt("Calculating \u2026 (one live fetch per required "
                                     "material, may take a moment)"))
            surplus_summary.setText("")
            market_summary.setText("")
            summary.setText("")
            score_summary.setText("")
            btn.setEnabled(False)
            _busy_frames = "\u280b\u2819\u2839\u2838\u283c\u2834\u2826\u2827\u2807\u280f"
            _busy_i = {"n": 0}

            def _busy_tick():
                _busy_i["n"] = (_busy_i["n"] + 1) % len(_busy_frames)
                spin_lbl.setText(_busy_frames[_busy_i["n"]] + "  " + _txt("calculating \u2026"))
            _busy_timer = QTimer(dlg)
            _busy_timer.setInterval(80)
            _busy_timer.timeout.connect(_busy_tick)
            _busy_tick()
            _busy_timer.start()

            def job():
                opts = dict(self._bd_opts)

                def plan_fn(n):
                    return industry.production_plan(cur_tid, n, self._bd_pricemap.get,
                                                     cur_recipes, opts)

                def orderbook_fn(mtid):
                    try:
                        ob = self._hub_orders(int(mtid), region, station, structure)
                        return ob.get("sell", [])
                    except Exception:
                        return []

                def batch_size_of(mtid):
                    bp = cur_recipes.product_to_bp.get(mtid)
                    return (bp[2] if bp else 1) or 1

                # --- Auto-Obergrenze: die Kurve soll dort aufhören, wo eine echte
                # Grenze greift, statt bei einer willkürlichen Zahl. Bewusst
                # UNABHÄNGIG von der im Bauplan eingestellten Menge (sonst würde
                # dieselbe Anfrage je nach Hintergrund-Menge andere Kurven liefern).
                # Grenzen: (1) Verlustpunkt (Materialeinkauf teurer als
                # Verkaufspreis), (2) Frachtraum voll (Materialvolumen füllt eine
                # Fahrt), (3) Markt-Absorption (so viel wie realistisch pro Monat
                # verkaufbar). Es gewinnt, was zuerst kommt. Verlust-/Fracht-Grenze
                # über die billige Flachpreis-Vorschau geschätzt (keine ESI nötig),
                # der echte Ladder-Lauf folgt danach.
                probe_qtys = industry._sweep_points(1, 2000, n=28)
                loss_at = None
                if sell_price > 0:
                    for q in probe_qtys:
                        p = plan_fn(q)
                        cu = p["total_cost"] / q if q else 0.0
                        if sell_price - cu < 0:
                            loss_at = q
                            break
                # Frachtraum-Grenze: Volumen pro Stück aus einer festen Referenz-
                # menge (Materialmengen skalieren ~linear mit der Stückzahl), dann
                # die Menge, bei der EINE Frachtladung voll ist. Referenzmenge fest
                # (10), NICHT von der Bauplan-Menge abhängig.
                freight_at = None
                # ENTSCHEID (Nutzer): die Frachtgrenze bleibt eine WARNUNG, kein
                # Limit. Sie zaehlt das Volumen der EINKAUFSLISTE (Material),
                # nicht der fertigen Schiffe - beim Flycatcher 52'119 m3 je
                # Schiff Material gegenueber ~5'000 m3 fuer die verpackte
                # Huelle. Mehrere Fahrten kosten Zeit, nicht Marge; deshalb
                # darf die Untergrenze `max(20, ...)` unten sie ueberstimmen.
                # Die Empfehlung nennt die noetigen Fahrten trotzdem.
                surplus_pct = float(self.settings.get("bau_buy_surplus", 0) or 0)
                _puf = 1 + surplus_pct / 100.0
                if freight:
                    ref_n = 10
                    ref_plan = plan_fn(ref_n)
                    ref_buy = ref_plan.get("buy") or {}
                    ref_vols = industry.item_volume_map(list(ref_buy.keys())) if ref_buy else {}
                    ref_vol = sum(float(ref_vols.get(t, 0.0)) * q * _puf
                                  for t, q in ref_buy.items())
                    vol_per_unit = (ref_vol / ref_n) if ref_n else 0.0
                    if vol_per_unit > 0:
                        freight_at = max(1, int(freight / vol_per_unit))
                # Absorptions-Grenze: über die Monats-Absorption hinaus zu bauen ist
                # (für die Baumengen-Frage) uninteressant -- das kriegt man eh nicht
                # los. Als weiche Obergrenze, damit die Kurve bei sehr profitablen,
                # gut lieferbaren Items nicht ins Uferlose läuft.
                abso_at = None
                _abso_probe = None
                try:
                    _hist_probe = esi.fetch_market_history(cur_tid, region)
                    _abso_probe = industry.market_absorption(_hist_probe)
                    if _abso_probe:
                        abso_at = int(_abso_probe["per_month"])
                except Exception:
                    abso_at = None
                    _abso_probe = None
                # Obergrenze = kleinste greifende Grenze (+Puffer), damit man den
                # jeweiligen Punkt auf der Kurve auch noch sieht. Rein item-abhängig.
                bounds = [b for b in (loss_at, freight_at, abso_at) if b]
                if bounds:
                    upper = max(20, int(min(bounds) * 1.3))
                else:
                    # Keine Grenze greift (kein Verkaufspreis, kein Frachtraum, keine
                    # Historie) -> feste, mengenunabhängige Obergrenze.
                    upper = 100
                # NUR GANZE RUNS ALS STUETZSTELLEN (Nutzer-Fund). Bei einem
                # Batch-Rezept - Reaktionen liefern z.B. 2'200 Stueck pro Run,
                # Munition 100 - ist jede Menge dazwischen physisch unmoeglich:
                # man bezahlt den ganzen Run und wirft den Rest weg. Der
                # Optimierer schlug deshalb "20 Stueck" bei 88,8 % Verschnitt
                # und 201'147 ISK/Stk vor, waehrend der Markt bei 788 ISK steht
                # - eine Empfehlung, die es im Spiel gar nicht gibt.
                # Gerechnet und ANGEZEIGT wird durchgehend in STUECK; nur die
                # Stuetzstellen liegen auf Vielfachen der Run-Ausgabe.
                _obp = cur_recipes.product_to_bp.get(cur_tid)
                _batch = int((_obp[2] if _obp else 1) or 1)

                if _batch > 1:
                    # DECKEL IN RUNS, NICHT IN STUECK. Die harte Grenze 5000 ist
                    # fuer Einzelstueck-Rezepte gedacht (5000 Stueck = 5000
                    # Runs). Bei 2'200 Stueck pro Run waren das ganze DREI
                    # Stuetzstellen - daher die unsinnig kurze Kurve, die dem
                    # Nutzer aufgefallen ist ("3 Runs finde ich komisch wenig").
                    # 60 Runs sind die gleiche Groessenordnung an Achsenpunkten
                    # wie 5000 Einzelstuecke an Aussagekraft.
                    _runs_up = max(8, -(-int(upper) // _batch))
                    _runs_up = min(_runs_up, 60)
                    qtys_practical = [r * _batch
                                      for r in industry._sweep_points(1, _runs_up, n=40)]
                    upper = qtys_practical[-1]
                else:
                    upper = min(upper, 5000)   # harte Deckelung, Achse lesbar
                    qtys_practical = industry._sweep_points(1, upper, n=40)                # Zusätzliche Punkte NUR für die Chart-Anzeige (zeigt, wie sich
                # Gewinn/Kosten JENSEITS der empfohlenen Menge weiterentwickeln,
                # z. B. der Abfall nach dem Verlust-Punkt) -- fließen NICHT in
                # Score/Empfehlung/Zusammenfassung ein (siehe done(): dort wird
                # wieder auf "upper" zurückgeschnitten). Kostet KEINEN einzigen
                # zusätzlichen Live-Abruf: ladder_cost_curve() holt das Orderbuch
                # pro Material genau einmal und rechnet alle Mengen daraus lokal.
                upper_wide = min(int(upper * 3), max(5000, upper))
                if _batch > 1:
                    _rw = -(-upper_wide // _batch)
                    qtys_tail = [r * _batch for r in industry._sweep_points(
                        -(-upper // _batch), _rw, n=15)] if _rw > (upper // _batch) else []
                else:
                    qtys_tail = (industry._sweep_points(upper, upper_wide, n=15)
                                 if upper_wide > upper else [])
                qtys = sorted(set(qtys_practical) | set(qtys_tail))
                curve = industry.ladder_cost_curve(
                    qtys, plan_fn, orderbook_fn, price_fn=self._bd_pricemap.get)
                # Reaktions-Überschuss + Frachtvolumen pro Kurvenpunkt anreichern.
                all_mat_ids = set()
                for c in curve:
                    all_mat_ids |= set((c.get("buy") or {}).keys())
                vols = industry.item_volume_map(list(all_mat_ids)) if all_mat_ids else {}
                def _with_surplus(q):
                    # Gleicher Material-Puffer wie im Bauplan (_buy_surplus_qty),
                    # damit Volumen/Frachtfahrten zwischen beiden übereinstimmen.
                    import math as _m
                    return max(1, int(_m.ceil(q * (1 + surplus_pct / 100.0))))

                for c in curve:
                    plan = plan_fn(c["qty"])
                    # ENDPRODUKT AUSKLAMMERN, wenn es selbst eine Reaktion ist:
                    # seine Menge waehlt der Nutzer, sie liegt seit der
                    # Run-Rundung immer auf ganzen Chargen und hat daher per
                    # Konstruktion 0 Ueberschuss. Da der Wert nach Stueckzahl
                    # gewichtet ist und das Endprodukt die groesste Charge hat,
                    # zog es den Prozentwert nach unten - bei Phenolic
                    # Composites erschienen 51,0 % Verschnitt bei den
                    # Zwischenprodukten als 4,25 %, und die Zusammenfassung
                    # meldete "Chargen gehen glatt auf" fuer eine Menge, bei der
                    # nur das Endprodukt selbst lief.
                    sp = industry.reaction_surplus_pct(
                        plan, cur_recipes.reaction_products, batch_size_of,
                        exclude=(cur_tid,))
                    c["surplus_pct"] = sp["pct"]
                    # MITNEHMEN, WIE VIEL UEBERHAUPT REAGIERT WIRD. 0 % heisst
                    # zweierlei: "Chargen gehen glatt auf" ODER "es wird gar
                    # nichts reagiert" (alles aus Bestand gedeckt oder
                    # gekauft). Ohne diese Zahl kann die Zusammenfassung die
                    # beiden Faelle nicht unterscheiden - und behauptete beim
                    # Nutzer "Chargen gehen fast glatt auf bei 2'200 Stueck",
                    # obwohl dort schlicht keine Reaktion lief.
                    c["reacted_units"] = sp.get("produced_units", 0) or 0
                    buy = c.get("buy") or {}
                    bv = sum(float(vols.get(t, 0.0)) * _with_surplus(q)
                             for t, q in buy.items())
                    c["buy_volume"] = bv
                    if freight:
                        c["trips"] = int(-(-bv // freight)) if bv > 0 else 0
                    else:
                        c["trips"] = None
                    # Verkaufsgebühren (Sales Tax + Broker Fee) abziehen -- konsistent
                    # mit dem Bauplan, sonst zeigt der Optimierer zu viel Gewinn.
                    _tax = float(self.settings.get("sales_tax_pct", 0) or 0) / 100.0
                    _brk = float(self.settings.get("broker_fee_pct", 0) or 0) / 100.0
                    _gross = sell_price * c["qty"]
                    c["profit"] = _gross * (1 - _tax - _brk) - c["total_cost"]
                # Absorption schon oben (für die Obergrenze) geholt -> wiederverwenden,
                # nur als Fallback erneut versuchen.
                abso = _abso_probe
                if abso is None:
                    try:
                        abso = industry.market_absorption(
                            esi.fetch_market_history(cur_tid, region))
                    except Exception:
                        abso = None
                return {"curve": curve, "abso": abso, "loss_at": loss_at,
                        "freight_at": freight_at, "upper_practical": upper}

            def done(r):
                _busy_timer.stop(); spin_lbl.setText(""); btn.setEnabled(True)
                curve_wide = r["curve"]; abso = r["abso"]
                upper_practical = r.get("upper_practical")

                def g(n):
                    return f"{int(n):,}".replace(",", "'")

                if not curve_wide:
                    eff_summary.setText(_txt("No curve data calculated."))
                    _chart_data["xs"] = []
                    return
                curve_wide.sort(key=lambda c: c["qty"])
                # Score/Empfehlung/Zusammenfassung IMMER nur auf dem praktischen
                # Bereich (wie vor der Chart-Erweiterung) -- die zusätzlichen
                # Punkte jenseits davon sind NUR fürs Diagramm, sie dürfen die
                # Empfehlung nicht beeinflussen.
                curve = ([c for c in curve_wide if c["qty"] <= upper_practical]
                         if upper_practical else curve_wide)
                if not curve:
                    curve = curve_wide

                # --- Ausgewogener Score über die ganze Kurve. Braucht einen
                # Verkaufspreis (sonst kein Gewinn -> kein sinnvoller Score). ---
                score_best = None
                if sell_price > 0:
                    monthly = int(abso["per_month"]) if abso else None
                    curve, score_best = industry.balanced_score(
                        curve, monthly_absorption=monthly)
                    if score_best:
                        sp = score_best.get("score_parts", {})
                        # Was bremst die Empfehlung nach oben? Die schwächste Achse
                        # nennen, damit die Zahl nachvollziehbar ist.
                        weakest = min(sp.items(), key=lambda kv: kv[1])[0] if sp else None
                        why = {"profit": _txt("profit holds"),
                               "capital": _txt("capital efficiency optimal"),
                               "surplus": _txt("batches divide up well"),
                               "absorption": _txt("still fully sellable at the market")
                               }.get(weakest, "")
                        # `why` stand hier seit jeher berechnet, aber NIE im
                        # Text (pyflakes-Fund emm485) - der Kommentar oben
                        # versprach es ("die schwaechste Achse nennen").
                        score_summary.setText(_txt(
                            "RECOMMENDATION: build {qty} \u00b7 profit {profit} "
                            "\u00b7 {cost}/unit (balanced score {score}/100)").format(
                            qty=_qty_full(score_best['qty']), profit=isk(score_best['profit']),
                            cost=isk(score_best['cost_unit']),
                            score=f"{score_best['score']:.0f}")
                            + ((" \u00b7 " + why) if why else ""))
                else:
                    score_summary.setText(_txt(
                        "Enter a sale price to get a quantity recommendation "
                        "(no price, no profit/score)."))

                # --- Effizienz-Menge: kleinste Menge innerhalb 1% des minimalen
                # Stückkosten-Werts (verkaufsunabhängig -- die eigentliche
                # "wie viel bauen"-Antwort). ---
                min_cost = min(c["cost_unit"] for c in curve)
                max_cost = max(c["cost_unit"] for c in curve)
                tol = min_cost * 1.01
                eff = next((c for c in curve if c["cost_unit"] <= tol), curve[-1])
                # "Flach" = die Stückkosten schwanken über die ganze Kurve um
                # weniger als 2%. Dann bringt Mehr-Bauen keine spürbar tieferen
                # Kosten, und die Effizienz-Menge ist eine irreführende Antwort:
                # die echte Grenze ist Absorption/Kapital/Frachtraum.
                flat = (max_cost <= min_cost * 1.02)
                if flat:
                    # Klartext für "es lohnt sich einfach durchgehend": die
                    # begrenzenden Faktoren nennen, die WIRKLICH zählen.
                    limits = []
                    if r.get("freight_at"):
                        limits.append(_txt("cargo hold fits ~{n} units per trip").format(
                            n=g(r['freight_at'])))
                    if abso:
                        limits.append(_txt("realistically you sell ~{n}/week").format(
                            n=g(abso['per_week'])))
                    lim_txt = (_txt(" \u2013 your real limit: ")
                               + ", ".join(limits)) if limits else ""
                    eff_summary.setText(_txt(
                        "Building pays off throughout: the unit cost stays "
                        "almost the same (~{cost}/unit) no matter how many you build. "
                        "So there is NO \u201eoptimal\u201c upper quantity{limit}."
                    ).format(cost=isk(min_cost), limit=lim_txt))
                else:
                    eff_summary.setText(_txt(
                        "Efficiency quantity: {qty} \u00b7 {cost}/unit \u2013 from "
                        "here on, building more hardly gets any cheaper (minimum "
                        "{minimum}/unit). Building less would cost more per unit."
                    ).format(qty=_qty_full(eff['qty']), cost=isk(eff['cost_unit']),
                             minimum=isk(min_cost)))

                # --- Reaktions-Überschuss: Menge im Test-Bereich mit dem wenigsten
                # Verschnitt (nur Mengen ab der Effizienz-Menge sind interessant,
                # sonst würde 1 Stück mit evtl. 0% gewinnen, ist aber unwirtschaftlich). ---
                cand = [c for c in curve if c["qty"] >= eff["qty"]] or curve
                # Nur Mengen vergleichen, bei denen ueberhaupt reagiert wird -
                # sonst gewinnt eine Menge mit 0 %, weil dort nichts laeuft.
                _cand_reacting = [c for c in cand if c.get("reacted_units")]
                low_surplus = min(_cand_reacting or cand,
                                  key=lambda c: c["surplus_pct"])
                if _cand_reacting and any(c["surplus_pct"] > 0 for c in curve):
                    # Den Stückpreis-Effekt sichtbar machen: bei der verschnittarmen
                    # Menge sind die bezahlten Reaktions-Chargen voll genutzt ->
                    # Stückpreis tendenziell niedriger. Wir vergleichen den
                    # Stückpreis der verschnittarmen Menge mit dem Median der Kurve,
                    # damit der "das senkt deinen Stückpreis"-Effekt greifbar wird.
                    import statistics as _st
                    med_unit = _st.median(c["cost_unit"] for c in cand)
                    saved = med_unit - low_surplus["cost_unit"]
                    extra = ""
                    if saved > 0:
                        extra = _txt(
                            " \u2013 unit price here {cost}/unit, ~{saved}/unit cheaper "
                            "than at odd quantities (paid batches fully used)"
                        ).format(cost=isk(low_surplus['cost_unit']), saved=isk(saved))
                    surplus_summary.setText(_txt(
                        "\u2697 Batches divide up almost evenly at {qty}: only {pct}% "
                        "surplus{extra}"
                    ).format(qty=_qty_full(low_surplus['qty']),
                             pct=f"{low_surplus['surplus_pct']:.1f}", extra=extra))
                elif not any(c.get("reacted_units") for c in curve):
                    surplus_summary.setText(_txt(
                        "\u2697 No reaction is run at all in this range \u2013 the need is "
                        "covered from stock or bought. The surplus value says nothing "
                        "here."))
                else:
                    surplus_summary.setText(_txt(
                        "\u2697 No reaction surplus in this range \u2013 the batches divide "
                        "up evenly."))

                # --- Markt-Absorption (baumengenunabhängig). ---
                if abso:
                    market_summary.setText(_txt(
                        "Market absorption at the hub (\u00d8 last {days} days): "
                        "~{week} units/week \u00b7 ~{month} units/month"
                    ).format(days=abso['days_used'], week=g(abso['per_week']),
                             month=g(abso['per_month'])))
                else:
                    market_summary.setText(_txt(
                        "Market absorption: no trade history available for "
                        "this item at the hub."))

                # --- Zusatz: Gewinn-Optimum (falls Verkaufspreis gesetzt) + Grenzen. ---
                parts = []
                if sell_price > 0:
                    best = max(curve, key=lambda c: c["profit"])
                    max_q = max(c["qty"] for c in curve)
                    # "Bester Gewinn" NUR nennen, wenn das Maximum auch INNEN
                    # liegt. Sitzt es am Rand, ist es kein Optimum, sondern das
                    # Ende des gerechneten Bereichs - der Nutzer sah "Bester
                    # Gewinn: 20 Stueck . 620 Mio", waehrend die Kurve daneben
                    # bis 60 Stueck auf ~1,8 Mrd weiterlief. Die alte Bedingung
                    # verlangte zusaetzlich `flat`; bei schwankenden
                    # Stueckkosten (hier durch Chargen-Rundung der Vorstufen)
                    # griff sie nicht und die irrefuehrende Zeile erschien doch.
                    if best["qty"] == max_q:
                        parts.append(
                            _txt("profit keeps growing to the end of the calculated range "
                                 "({qty}, ~{per}/unit) \u2013 no profit maximum within").format(
                                qty=_qty_full(max_q), per=isk(best['profit'] / max_q)))
                    else:
                        parts.append(_txt("Best profit: {qty} \u00b7 {isk}").format(
                            qty=_qty_full(best['qty']), isk=isk(best['profit'])))
                    profitable = [c["qty"] for c in curve if c["profit"] >= 0]
                    if profitable and max(profitable) == max_q:
                        # "Profitabel bis 20" las sich wie eine Obergrenze, ab
                        # der es kippt. Tatsaechlich war einfach alles bis zum
                        # Rand profitabel.
                        parts.append(_txt(
                            "Profitable throughout the calculated range "
                            "(up to {qty})").format(qty=_qty_full(max_q)))
                    elif profitable:
                        parts.append(_txt("Profitable up to {qty}, not beyond").format(
                            qty=_qty_full(max(profitable))))
                    else:
                        parts.append(_txt("Not profitable at any quantity in this range"))
                short_qtys = [c["qty"] for c in curve if c.get("short_materials")]
                if short_qtys:
                    parts.append(_txt("\u26a0 material bottlenecks from {qty}").format(
                        qty=_qty_full(min(short_qtys))))
                # Volumen/Frachtfahrten für die EMPFOHLENE Menge (score_best) --
                # das ist die Menge, die du wirklich baust. Bei fehlendem Score
                # (kein Verkaufspreis) auf die Effizienz-Menge zurückfallen.
                ref_pt = score_best or eff
                if ref_pt and ref_pt.get("trips") is not None:
                    bv = ref_pt.get("buy_volume") or 0.0
                    tr = ref_pt["trips"]
                    lbl = (_txt("Recommendation") if score_best
                           else _txt("Efficiency quantity"))
                    _fahrten = (_txt("{n} freight trip") if tr == 1
                                else _txt("{n} freight trips")).format(n=tr)
                    txt = _txt("Shopping list at {which} ({qty}): {vol} m\u00b3 "
                               "\u00b7 {trips}").format(
                        which=lbl, qty=_qty_full(ref_pt['qty']),
                        vol=f"{bv:,.0f}".replace(",", "'"), trips=_fahrten)
                    if tr > 1:
                        txt += " " + _txt("\u26a0 does not fit in one trip")
                    parts.append(txt)
                summary.setText("   \u00b7   ".join(parts))

                chart.clear(); chart2.clear(); chart3.clear()
                _readd1(); _readd2(); _readd3()
                _chart_data["xs"] = []; _chart_data["profit"] = []
                _chart_data["cost"] = []; _chart_data["rev"] = []
                _chart_data["surplus"] = []
                if len(curve_wide) >= 2:
                    # X-Achse in RUNS, sobald ein Run mehr als ein Stueck
                    # liefert - sonst stuende "Runs" an der Achse und
                    # Stueckzahlen darunter. Die Y-Werte bleiben unveraendert
                    # (Gewinn gesamt, Kosten JE STUECK).
                    xs = [_x_of(c["qty"]) for c in curve_wide]
                    profit_ys = [c["profit"] for c in curve_wide]
                    cost_ys = [c["cost_unit"] for c in curve_wide]
                    rev_ys = [sell_price for _c in curve_wide]
                    surplus_ys = [c["surplus_pct"] for c in curve_wide]
                    _chart_data["xs"] = xs
                    _chart_data["profit"] = profit_ys
                    _chart_data["cost"] = cost_ys
                    _chart_data["rev"] = rev_ys if sell_price > 0 else []
                    _chart_data["surplus"] = surplus_ys
                    chart.plot(xs, profit_ys, pen=pg.mkPen(theme.GREEN, width=3))
                    if not flat:
                        eff_marker1 = pg.ScatterPlotItem(
                            [_x_of(eff["qty"])], [eff["profit"]], size=13,
                            brush=pg.mkBrush(theme.GREEN), pen=pg.mkPen(theme.BG, width=2))
                        chart.addItem(eff_marker1)
                    chart2.plot(xs, cost_ys, pen=pg.mkPen(theme.AMBER, width=2),
                               name=_txt("Cost/unit"))
                    if sell_price > 0:
                        chart2.plot(xs, rev_ys, pen=pg.mkPen(theme.CYAN, width=2),
                                   name=_txt("Revenue/unit (fixed)"))
                    if not flat:
                        eff_marker2 = pg.ScatterPlotItem(
                            [_x_of(eff["qty"])], [eff["cost_unit"]], size=13,
                            brush=pg.mkBrush(theme.GREEN), pen=pg.mkPen(theme.BG, width=2))
                        chart2.addItem(eff_marker2)
                    chart3.plot(xs, surplus_ys, pen=pg.mkPen(theme.VIOLET, width=2))
                    ls_marker = pg.ScatterPlotItem(
                        [_x_of(low_surplus["qty"])], [low_surplus["surplus_pct"]],
                        size=12,
                        brush=pg.mkBrush(theme.VIOLET), pen=pg.mkPen(theme.BG, width=2))
                    chart3.addItem(ls_marker)
                    # Kein eigenes Score-Chart mehr -- die Empfehlung markieren wir
                    # trotzdem im Gewinn-Chart (gut sichtbar, kein Extra-Diagramm).
                    if score_best is not None:
                        sc_marker2 = pg.ScatterPlotItem(
                            [_x_of(score_best["qty"])], [score_best["profit"]],
                            size=14,
                            brush=pg.mkBrush(theme.AMBER), pen=pg.mkPen(theme.BG, width=2))
                        chart.addItem(sc_marker2)
                    x_lo, x_hi = min(xs), max(xs)
                    pad = max(1, (x_hi - x_lo) * 0.1)
                    for c, vb in ((chart, vb1), (chart2, vb2), (chart3, vb3)):
                        vb.setLimits(xMin=x_lo - pad, xMax=x_hi + pad,
                                    minXRange=(x_hi - x_lo) / 20 or 1,
                                    maxXRange=(x_hi - x_lo) + 2 * pad)
                        # X-BEREICH EXPLIZIT SETZEN, nicht nur autoRange
                        # anschalten. setLimits(minXRange=...) klemmt die noch
                        # leere Standard-Ansicht (0..1) sofort auf die
                        # Mindestbreite hoch - beim Flycatcher (x 1..60) sind
                        # das 59/20 = 2.95. Genau das sah der Nutzer: die Kurve
                        # war vollstaendig da, aber auf x 0..2.9 gezoomt, und
                        # erst ein Rechtsklick (_reset_view -> enableAutoRange)
                        # holte sie zurueck. enableAutoRange() allein wirkt hier
                        # nicht, weil nach dem Klemmen kein Datenereignis mehr
                        # folgt, das eine Neuberechnung ausloest.
                        vb.setXRange(x_lo, x_hi, padding=0.05)
                        vb.enableAutoRange(axis=pg.ViewBox.YAxis)

            def fail(msg):
                _busy_timer.stop(); spin_lbl.setText(""); btn.setEnabled(True)
                eff_summary.setText(_txt("\u26a0 Error while calculating: ") + str(msg))
                eff_summary.setStyleSheet(f"font-size:13px; color:{theme.RED};")
            self._run(Worker(job), done, fail_cb=fail, label=_txt("Optimising \u2026"))

        btn.clicked.connect(compute)
        self._persist_window(dlg, "optimizer")
        self._show_tool_window(dlg)

    def open_ladder_check(self):
        """Ersetzt den flachen Materialpreis der aktuellen Einkaufsliste durch
        ECHTE Orderbuch-Preise (ein Live-Abruf pro ben\u00f6tigtem Material) \u2013
        zeigt, wie stark die Baukosten-Sch\u00e4tzung bei d\u00fcnnen M\u00e4rkten daneben
        liegt. Bewusst Opt-in (eigener Button), nicht automatisch bei jeder
        Bauplan-Berechnung \u2013 sonst w\u00e4re jede Mengen\u00e4nderung durch viele
        ESI-Abrufe langsam."""
        if getattr(self, "_bd_frozen", None):
            self._flash_tip(t("Prices are frozen \u2013 unfreeze first "
                              "( button at the top)"))
            return
        recipes = getattr(self, "_bd_recipes", None)
        tid = getattr(self, "_bd_type", None)
        if not recipes or not tid:
            self._flash_tip(t("Calculate a build plan first ( Build plan)"))
            return
        qty = int(getattr(self, "_bd_qty", 1) or 1)
        name = getattr(self, "_bd_name", None) or str(tid)
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
                                       QPushButton, QTableWidget, QTableWidgetItem)
        dlg = MinimizableDialog(self._tool_parent()); dlg.setWindowTitle(t("Order-book-exact material cost \u2013 {name}").format(name=name))
        dlg.resize(880, 640)
        v = QVBoxLayout(dlg); v.setContentsMargins(18, 14, 18, 14); v.setSpacing(9)
        qtxt = f"{qty:,}".replace(",", "'")

        head_card = QFrame(); head_card.setObjectName("Card")
        head_card.setStyleSheet(
            f"QFrame#Card {{ border: 1px solid rgba(70,224,200,0.4); }}")
        head_v = QVBoxLayout(head_card)
        head_v.setContentsMargins(14, 10, 14, 10); head_v.setSpacing(8)
        head_title = QLabel(t("ORDER-BOOK EXACT \u2013 {name} \u00d7{qty}").format(name=name, qty=qtxt))
        head_title.setStyleSheet(
            f"color:{theme.CYAN}; font-size:13px; font-weight:800; letter-spacing:1px;")
        head_v.addWidget(head_title)
        head_desc = QLabel(t("Replaces the flat price of the shopping list with real "
                             "order-book prices \u2013 one live fetch per material, may "
                             "take a moment with many reaction materials."))
        head_desc.setWordWrap(True); head_desc.setObjectName("Muted")
        head_v.addWidget(head_desc)
        row = QHBoxLayout()
        _ahub_lbl = QLabel(t("Hub: ") + self._active_hub_label())
        _ahub_lbl.setObjectName("Muted")
        _ahub_lbl.setToolTip(t(
            "The hub is chosen at the top left of the tool and applies "
              "to all tabs."))
        self._register_tool_hub_label(_ahub_lbl)
        row.addWidget(_ahub_lbl)
        btn = QPushButton(t("Calculate"))
        btn.setIcon(icons.icon("check"))
        btn.setObjectName("Primary")
        btn.setMinimumHeight(34)
        btn.setStyleSheet("font-size:13px; font-weight:800; padding:6px 18px;")
        row.addWidget(btn); row.addStretch()
        head_v.addLayout(row)
        v.addWidget(head_card)
        summary = QLabel(t("Choose a hub, then \u201eCalculate\u201c."))
        summary.setWordWrap(True); summary.setStyleSheet("font-size:15px; font-weight:600;")
        v.addWidget(summary)
        tbl = QTableWidget(0, 4)
        tbl.setHorizontalHeaderLabels([t("Material"), t("Quantity"), t("Markup %"), t("Status")])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        v.addWidget(tbl, 1)
        note = QLabel(t("\u201eMarkup %\u201c = how much more your purchase costs because "
                        "you clear out the cheap sell orders (order-book price vs. best "
                        "ask). Traffic light: green up to +5 % \u00b7 "
                        "yellow +5\u201320 % \u00b7 red above +20 % (market too thin "
                        "for this quantity). Sorted by markup \u2013 most expensive first. "
                        "Double-click shows the individual sell orders. \u201eNo order "
                        "book\u201c: no offer at the hub. \u201eShort\u201c: not enough for the "
                        "full quantity."))
        note.setObjectName("Muted"); note.setWordWrap(True); v.addWidget(note)

        def compute():
            # Bauplan-Kontext FRISCH lesen -- so kann man im Hintergrund die Menge
            # (oder das Endprodukt) ändern und hier bei offenem Fenster einfach
            # erneut "Berechnen" klicken, ohne das Fenster zu schließen.
            cur_recipes = getattr(self, "_bd_recipes", None)
            cur_tid = getattr(self, "_bd_type", None)
            if not cur_recipes or not cur_tid:
                summary.setText(t("Calculate a build plan first ( Build plan)."))
                return
            cur_qty = int(getattr(self, "_bd_qty", 1) or 1)
            region, station, structure = self._active_hub()
            summary.setText(t("Calculating \u2026 (\u00d7{qty}, one live fetch per material, "
                              "please wait)").format(qty=f"{cur_qty:,}".replace(",", "'")))
            opts = dict(self._bd_opts)

            def job():
                plan = industry.production_plan(cur_tid, cur_qty,
                                                self._bd_pricemap.get, cur_recipes, opts)
                buy = plan.get("buy") or {}
                orderbooks = {}
                for mtid in buy:
                    try:
                        ob = self._hub_orders(int(mtid), region, station, structure)
                        orderbooks[mtid] = ob.get("sell", [])
                    except Exception:
                        orderbooks[mtid] = []
                res = industry.refine_plan_with_ladder(plan, orderbooks,
                                                       price_fn=self._bd_pricemap.get)
                names = esi.resolve_names(list(buy.keys())) if buy else {}
                return {"res": res, "names": names, "orderbooks": orderbooks,
                        "buy": dict(buy), "station": station, "region": region}

            def done(r):
                res = r["res"]; names = r["names"]
                # Für die Verifikation per Doppelklick merken (rohe Orderbücher
                # + benötigte Mengen + Hub), damit man jede Zahl gegen das
                # tatsächliche In-Game-Orderbuch gegenchecken kann.
                self._ladder_verify = {
                    "orderbooks": r.get("orderbooks", {}),
                    "buy": r.get("buy", {}),
                    "names": names,
                    "station": r.get("station"),
                    "region": r.get("region"),
                }
                parts = [t("Flat estimate: ") + isk(res['flat_cost']),
                        t("Order-book exact: ") + isk(res['total_cost']),
                        t("Total markup: {pct} % ({isk})").format(
                            pct=f"{res['delta_pct']:+.1f}", isk=isk(res['delta']))]
                summary.setText("   \u00b7   ".join(parts))
                rows = res["rows"]

                # Aufschlag % je Material (Orderbuch vs. Flachpreis) berechnen und
                # danach sortieren -- die teuersten Materialien zuerst.
                def _markup(rr):
                    fu = rr.get("flat_unit"); lu = rr.get("ladder_unit")
                    if fu and fu > 0 and lu is not None:
                        return (lu - fu) / fu * 100.0
                    return None
                for rr in rows:
                    rr["_markup"] = _markup(rr)
                rows = sorted(rows, key=lambda rr: (rr["_markup"] if rr["_markup"]
                                                    is not None else -1), reverse=True)

                tbl.setSortingEnabled(False)
                tbl.setRowCount(len(rows))
                for i, rr in enumerate(rows):
                    mtid = rr["type_id"]
                    nm_it = QTableWidgetItem(names.get(mtid, f"#{mtid}"))
                    nm_it.setData(Qt.UserRole, mtid)   # für Doppelklick-Verifikation
                    q_it = NumericItem(f"{rr['qty']:,}".replace(",", "'"), rr["qty"])
                    mk = rr["_markup"]
                    if mk is not None:
                        mk_it = NumericItem(f"+{mk:.1f} %" if mk >= 0 else f"{mk:.1f} %", mk)
                        # Ampel-Farbe nach Schwellen 5 / 20 %.
                        if mk <= 5:
                            mk_it.setForeground(QColor(theme.GREEN))
                        elif mk <= 20:
                            mk_it.setForeground(QColor(theme.AMBER))
                        else:
                            mk_it.setForeground(QColor(theme.RED))
                    else:
                        mk_it = NumericItem("\u2013", -1)
                    # Status: Ampel-Symbol nach Aufschlag + Knapp/Kein-Orderbuch.
                    if not rr["has_orderbook"]:
                        status = QTableWidgetItem(t("\u2014 No order book"))
                        status.setForeground(QColor(theme.MUTED))
                    elif mk is None:
                        status = QTableWidgetItem("\u2014")
                        status.setForeground(QColor(theme.MUTED))
                    else:
                        if mk <= 5:
                            txt = "OK"; col = theme.GREEN
                        elif mk <= 20:
                            txt = t("expensive"); col = theme.AMBER
                        else:
                            txt = t("too expensive"); col = theme.RED
                        if rr["short"] > 0:
                            txt += t(" \u00b7 short (-{n})").format(
                                n=f"{rr['short']:,}".replace(",", "'"))
                        status = QTableWidgetItem(txt)
                        status.setForeground(QColor(col))
                    for it in (q_it, mk_it):
                        it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    status.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    tbl.setItem(i, 0, nm_it); tbl.setItem(i, 1, q_it)
                    tbl.setItem(i, 2, mk_it); tbl.setItem(i, 3, status)
                tbl.setSortingEnabled(True)

            def fail(msg):
                summary.setText(t("\u26a0 Error while calculating: ") + str(msg))
                summary.setStyleSheet(f"font-size:13px; color:{theme.RED};")
            self._run(Worker(job), done, fail_cb=fail, label=t("Fetching order book \u2026"))

        note2 = QLabel(t("Double-click a material to see the INDIVIDUAL sell "
                         "orders the order-book price was calculated from \u2013 so you can "
                         "check every number directly against the in-game market "
                         "(price \u00d7 quantity, cheapest first)."))
        note2.setObjectName("Muted"); note2.setWordWrap(True); v.addWidget(note2)

        def _verify_material(item):
            row_i = item.row()
            name_item = tbl.item(row_i, 0)
            if not name_item:
                return
            mtid = name_item.data(Qt.UserRole)
            vinfo = getattr(self, "_ladder_verify", None)
            if not mtid or not vinfo:
                return
            ob = (vinfo["orderbooks"] or {}).get(mtid) or []
            need = int(round((vinfo["buy"] or {}).get(mtid, 0)))
            mname = (vinfo["names"] or {}).get(mtid, f"#{mtid}")
            from PySide6.QtWidgets import (QDialog, QVBoxLayout, QTableWidget,
                                           QTableWidgetItem)
            d2 = MinimizableDialog(self)
            d2.setWindowTitle(t("Order-book proof \u2013 {name}").format(name=mname))
            d2.resize(560, 560)
            v2 = QVBoxLayout(d2)
            need_txt = f"{need:,}".replace(",", "'")
            v2.addWidget(QLabel(t(
                "Required quantity of <b>{name}</b>: {need} units. Below are the real "
                "sell orders at the hub (cheapest first) \u2013 the tool buys them from "
                "top to bottom until the required quantity is reached. \u201eUsed\u201c = "
                "how many units from this order went into the calculation."
            ).format(name=mname, need=need_txt)))
            t2 = QTableWidget(0, 4)
            t2.setHorizontalHeaderLabels([t("Price/unit"), t("Available"), t("Used"),
                                          t("Cost of this order")])
            t2.verticalHeader().setVisible(False)
            t2.setEditTriggers(QTableWidget.NoEditTriggers)
            t2.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
            v2.addWidget(t2, 1)
            # Ladder nachvollziehen: günstigste zuerst, bis need erfüllt.
            orders = sorted(ob, key=lambda x: x[0])
            remaining = need
            used_cost = 0.0
            # Sortieren waehrend des Fuellens AUS - sonst ordnet Qt die
            # Zeilen um, waehrend setItem noch auf alte Indizes zielt.
            t2.setSortingEnabled(False)
            t2.setRowCount(len(orders))
            for i, (price, avail) in enumerate(orders):
                used = int(min(avail, remaining)) if remaining > 0 else 0
                remaining -= used
                line = used * price
                used_cost += line
                p_it = NumericItem(isk(price, suffix=False), price)
                a_it = NumericItem(f"{int(avail):,}".replace(",", "'"), avail)
                u_it = NumericItem(f"{used:,}".replace(",", "'"), used)
                l_it = NumericItem(isk(line, suffix=False), line)
                for it in (p_it, a_it, u_it, l_it):
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if used > 0:
                    u_it.setForeground(QColor(theme.GREEN))
                    l_it.setForeground(QColor(theme.GREEN))
                else:
                    for it in (p_it, a_it, u_it, l_it):
                        it.setForeground(QColor(theme.MUTED))
                t2.setItem(i, 0, p_it); t2.setItem(i, 1, a_it)
                t2.setItem(i, 2, u_it); t2.setItem(i, 3, l_it)
            t2.setSortingEnabled(True)
            avg = (used_cost / (need - max(0, remaining))) if (need - max(0, remaining)) else 0.0
            foot = t("Total used: {isk} for {n} units \u2192 \u00d8 {avg}/unit").format(
                isk=isk(used_cost),
                n=need_txt if remaining <= 0 else str(need - remaining), avg=isk(avg))
            if remaining > 0:
                foot += "   \u2014   " + t(
                    "\u26a0 order book not deep enough: {n} units missing (estimated "
                    "conservatively at the most expensive price in the tool).").format(
                    n=f"{remaining:,}".replace(",", "'"))
            fl = QLabel(foot); fl.setWordWrap(True)
            fl.setStyleSheet("font-size:13px; font-weight:600;")
            v2.addWidget(fl)
            if not orders:
                fl.setText(t("No sell offer for this material at the chosen hub \u2013 "
                             "the tool keeps the flat price here."))
            self._show_tool_window(d2)

        tbl.itemDoubleClicked.connect(_verify_material)

        btn.clicked.connect(compute)
        self._persist_window(dlg, "ladder_check", {"table": tbl.horizontalHeader()})
        self._show_tool_window(dlg)

    def _build_preset_to_custom(self, *args):
        if getattr(self, "_applying_build_preset", False):
            return
        if hasattr(self, "b_preset") and self.b_preset.currentIndex() != 0:
            self.b_preset.blockSignals(True)
            self.b_preset.setCurrentIndex(0)
            self.b_preset.blockSignals(False)

    def _apply_build_preset(self):
        p = self.b_preset.currentData()
        if not p:
            # "Eigene Einstellung": Sonderschalter zuruecksetzen, sonst bliebe
            # "Nur Reaktionen" nach einem Preset-Wechsel faelschlich aktiv.
            self._build_reactions_only = False
            self._build_rigs_only = False
            if hasattr(self, "b_only_cap_lbl"):
                self.b_only_cap_lbl.setText("")
            return
        self._applying_build_preset = True
        try:
            wi = self.b_window.findData(p.get("window", 30))
            if wi >= 0:
                self.b_window.setCurrentIndex(wi)
            self.b_margin.setValue(p.get("margin", 10))
            self.b_vol.setValue(p.get("vol", 20))
            ti = self.b_tech.findData(p.get("tech"))
            self.b_tech.setCurrentIndex(ti if ti >= 0 else 0)
            self.b_pmin.setValue(p.get("pmin", 0))
            self.b_pmax.setValue(p.get("pmax", 0))
            self._build_reactions_only = bool(p.get("reactions", False))
            self._build_rigs_only = bool(p.get("rigs", False))
            # EINE ZEILE, DREI MOEGLICHE AUSSAGEN. Sie muss auch LEER werden
            # koennen: bleibt "Nur Reaktionen" nach dem Wechsel auf ein
            # anderes Preset stehen, behauptet die Oberflaeche einen Filter,
            # der gar nicht mehr laeuft (Nutzer-Fall aus Sitzung 11).
            if hasattr(self, "b_only_cap_lbl"):
                if self._build_reactions_only:
                    _nur = t("\u2705 Reactions only (from preset)")
                elif self._build_rigs_only:
                    _nur = t("\u2705 Rigs only (from preset)")
                else:
                    _nur = ""
                self.b_only_cap_lbl.setText(_nur)
        finally:
            self._applying_build_preset = False
        # kein Auto-Laden – der Nutzer klickt selbst „🔍 Blaupausen suchen“.
        self.build_status.setText(t("Preset set \u2013 now \u201eFind blueprints\u201c."))

    def _refine_all_optimal_qty(self):
        """Rechnet für JEDES aktuelle Scanner-Ergebnis die genaue production_plan()-
        Rechnung nach (Losgrößen-/Rundungseffekte, echte Job-Kosten) statt der
        schnellen Pro-Stück-Schätzung von find_deals(). Menge = Ø Tagesvolumen
        (gedeckelt) als realistische "wie viel würde ich wirklich bauen"-Annahme -
        der volle interaktive Optimierer bräuchte pro Item einen festen Verkaufs-
        preis/Frachtraum, den man für 40 Items nicht sinnvoll raten kann. Cache
        NUR im RAM (self._optimal_qty_cache, LRU-gedeckelt auf 400 Einträge) -
        bewusst keine Datei, wie gewünscht kein Datenmüll auf der Platte."""
        from .. import industry as _ind
        deals = getattr(self, "_last_build_deals", None)
        if not deals:
            self._flash_tip(t("Run \u201eFind blueprints\u201c first."))
            return
        if not _ind.sde_ready():
            self.build_status.setText(t("Run \u201eLoad recipes\u201c first."))
            return
        snapshot = store.get_snapshot()
        if not snapshot:
            return
        build_opts = dict(getattr(self, "_last_build_opts", None) or {})
        snap_ts = store.snapshot_timestamp()
        structures = self.settings.get("bau_structures", []) or []
        struct_key = tuple(sorted(s["id"] for s in structures))
        me_key = round(float(build_opts.get("me", 0) or 0), 3)
        self.b_refine_btn.setEnabled(False)
        self.build_status.setText(t("Recalculating exact build quantities \u2026"))

        def job(progress=None, should_cancel=None):
            pm = {s["type_id"]: s["sell_min"] for s in snapshot if s["sell_min"] > 0}
            recipes = _ind.recipes_cached()
            cache = self._optimal_qty_cache
            tax = float(self.settings.get("sales_tax_pct", 0) or 0) / 100.0
            broker = float(self.settings.get("broker_fee_pct", 0) or 0) / 100.0
            n = len(deals)
            updated = []
            for i, d in enumerate(deals):
                if should_cancel and should_cancel():
                    break
                tid = d["type_id"]
                # Ø Tagesvolumen als Losgröße - realistischer als "1 Stück", aber
                # gedeckelt (500), sonst wird's bei Munition/Mineralien-artigen
                # Massengütern pro Item unnötig langsam.
                qty = max(1, min(500, round(d.get("daily_vol", 0) or 1)))
                # AUF EIN VIELFACHES DER RUN-AUSGABE AUFRUNDEN. Ein Run liefert
                # bei Reaktionen und Munition viele Stueck auf einmal; eine
                # Losgroesse mittendrin bezahlt einen ganzen Run und wirft den
                # Rest als Ueberschuss weg. Gemessen an einer 200er-Reaktion:
                # 200 Stk = 1'250 ISK/Stk, 500 Stk = 1'500 ISK/Stk (+20 %),
                # 5'000 Stk wieder 1'250. Der Deckel von 500 traf also
                # ausgerechnet den teuersten Punkt - eine reine Artefakt-Marge,
                # die nichts mit dem Item zu tun hat. So baut auch niemand.
                _bp_r = recipes.product_to_bp.get(tid)
                _per_run = int((_bp_r[2] if _bp_r else 1) or 1)
                if _per_run > 1:
                    qty = -(-qty // _per_run) * _per_run   # aufrunden
                key = (tid, qty, me_key, struct_key, snap_ts)
                cached = cache.get(key)
                if cached is not None:
                    cache.move_to_end(key)     # LRU: gerade genutzt -> nach hinten
                else:
                    try:
                        plan = _ind.production_plan(tid, qty, pm.get, recipes, build_opts)
                        total_cost = plan.get("total_cost", 0) or 0
                        sell = pm.get(tid, d.get("sell_min", 0)) or 0
                        net_sell = sell * (1 - tax - broker)
                        cost_per_unit = (total_cost / qty) if qty else 0
                        profit_unit = net_sell - cost_per_unit
                        margin = ((profit_unit / cost_per_unit * 100.0)
                                 if cost_per_unit else 0.0)
                        cached = {"qty": qty, "build_cost": cost_per_unit,
                                  "profit_unit": profit_unit, "under_pct": margin}
                        cache[key] = cached
                        if len(cache) > 400:      # RAM-Deckel, kein Datenmüll
                            cache.popitem(last=False)
                    except Exception:
                        cached = None
                if cached:
                    nd = dict(d)
                    nd["build_cost"] = cached["build_cost"]
                    nd["profit_unit"] = cached["profit_unit"]
                    nd["under_pct"] = cached["under_pct"]
                    nd["refined_qty"] = cached["qty"]
                    nd["profit_day"] = cached["profit_unit"] * (d.get("daily_vol", 0) or 0)
                    updated.append(nd)
                else:
                    updated.append(d)
                if progress:
                    progress(i + 1, n)
            return updated

        def done(updated):
            self.b_refine_btn.setEnabled(True)
            self._last_build_deals = updated
            self._render_build(updated)
            n_hit = sum(1 for d in updated if d.get("refined_qty"))
            self.build_status.setText(
                t("{hit}/{all} hits recalculated exactly ( marker) \u2713"
                  ).format(hit=n_hit, all=len(updated)))

        def fail(msg):
            self.b_refine_btn.setEnabled(True)
            self.build_status.setText(t("Error: ") + str(msg))
        self._run(Worker(job, with_progress=True, with_cancel=True), done,
                  fail_cb=fail, label=t("Calculating optimal quantity \u2026"))
