"""Reiter "Assets" (emm863) - was liegt wo, ueber alle Charaktere.

NUTZER-AUFTRAG (08.11.2026): "ich moechte einen neuen MainTab
hinzufuegen 'Assets'. Ich will da auch alle charakterkarten haben genau
gleich aussehen wie in Industry Jobs tab. Aber halt mit allen
Stationen/Strukturen der charaktere und was darin fuer Items sind, als
dropdown. Ein ersichtliches such-Eingabefenster, und wenn man da
anfaengt zu tippen werden automatisch die sachen ... herausgefiltert
... bsp ich gebe ein: 'Retribution' und dann sehe ich nur noch die
charakter karten die Retributions besitzen, und in jeder charakterkarte
sehe ich auf welcher station die sind, dann kann ich die station
ausklappen je karte und sehe wieviele Retris da sind." Nachtrag: "auch
charakterkarten zu und ausschaltung auf der rechten seite genau gleich
wie in industry Tab aufbauen."

AUFGABENTEILUNG: gerechnet wird in `char_assets.py` (orte_mengen,
suche_filter - pur, aa-prueftbar); HIER steht nur die Oberflaeche.
Karten-Optik, rechtes Charakter-Panel und Schalter-Stil kommen aus dem
Industry-jobs-Muster; der Schalter-STIL ist dieselbe Funktion
(`_jobs_schalter_stil`, Regel 9), gemerkt wird getrennt in
settings["assets_chars_aus"].
"""
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit,
                               QPushButton, QScrollArea, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .. import char_assets, config, esi, store
from ..sprache import t
from ..workers import Worker
from . import icons, theme


class AssetsTab:
    def _build_assets_tab(self):
        from .mw_bauplan_tabs import KartenRaster
        page = QWidget()
        v = QVBoxLayout(page)
        v.setContentsMargins(14, 10, 14, 10)
        v.setSpacing(8)
        kopf = QHBoxLayout(); kopf.setSpacing(10)
        titel = QLabel(t("ASSETS"))
        titel.setStyleSheet(f"font-size:13px; letter-spacing:2px; "
                            f"font-weight:800; color:{theme.GREEN};")
        kopf.addWidget(titel)
        kopf.addStretch()
        self._as_stand_lbl = QLabel("")
        self._as_stand_lbl.setObjectName("Muted")
        kopf.addWidget(self._as_stand_lbl)
        self._as_refresh_btn = QPushButton(t("Refresh"))
        self._as_refresh_btn.setIcon(icons.icon("refresh"))
        self._as_refresh_btn.setStyleSheet(theme.amber_rahmen_knopf())
        self._as_refresh_btn.clicked.connect(lambda: self._assets_laden())
        kopf.addWidget(self._as_refresh_btn)
        v.addLayout(kopf)
        hinweis = QLabel(t("Everything your linked characters own, grouped "
                           "by station/structure. Start typing to filter: "
                           "only characters and locations holding a "
                           "matching item stay visible."))
        hinweis.setObjectName("Muted"); hinweis.setWordWrap(True)
        v.addWidget(hinweis)
        # DAS SUCHFELD IST DER KERN DES REITERS ("Ein ersichtliches
        # such-Eingabefenster"): eigene Zeile, volle Breite, Lupe.
        self.as_search = QLineEdit()
        self.as_search.setPlaceholderText(
            t("Search items … e.g. „Retribution“"))
        self.as_search.addAction(icons.icon("search"),
                                 QLineEdit.LeadingPosition)
        self.as_search.setClearButtonEnabled(True)
        self.as_search.setMinimumHeight(32)
        v.addWidget(self.as_search)
        # Tipp-Debounce (Muster emm855): erst wenn die Finger kurz ruhen
        # wird neu gezeichnet - sonst baut jeder Buchstabe alle Karten.
        self._as_such_timer = QTimer(page)
        self._as_such_timer.setSingleShot(True)
        self._as_such_timer.setInterval(250)
        self._as_such_timer.timeout.connect(lambda: self._assets_zeichnen())
        self.as_search.textChanged.connect(
            lambda _txt: self._as_such_timer.start())
        body = QHBoxLayout(); body.setSpacing(12)
        self._as_raster = KartenRaster(breite=380)
        _sc = QScrollArea(); _sc.setWidgetResizable(True)
        _sc.setFrameShape(QScrollArea.NoFrame)
        _sc.setWidget(self._as_raster)
        body.addWidget(_sc, 1)
        # CHARAKTERE AN/AUS - "genau gleich wie in industry Tab":
        # gleiches Panel, gleicher Schalter-Stil (_jobs_schalter_stil,
        # EINE Stelle), eigener Merker assets_chars_aus.
        panel = QFrame(); panel.setObjectName("Card")
        panel.setFixedWidth(230)
        pv = QVBoxLayout(panel)
        pv.setContentsMargins(10, 10, 10, 10); pv.setSpacing(6)
        _pt = QLabel(t("CHARACTERS"))
        _pt.setStyleSheet(f"font-size:13px; letter-spacing:2px; "
                          f"font-weight:800; color:{theme.AMBER};")
        pv.addWidget(_pt)
        self._as_schalter_box = QVBoxLayout()
        self._as_schalter_box.setSpacing(4)
        pv.addLayout(self._as_schalter_box)
        self._as_alle_btn = QPushButton(" " + t("All on"))
        self._as_alle_btn.setIcon(icons.icon("check"))   # b55: Symbolpflicht
        self._as_alle_btn.clicked.connect(lambda: self._assets_alle_an())
        pv.addWidget(self._as_alle_btn)
        pv.addStretch()
        body.addWidget(panel)
        v.addLayout(body, 1)
        self._as_daten = None
        self._as_laeuft = False
        self._as_stand_ts = 0.0
        self._as_schalter = {}           # {cid: Knopf} - b-Suite
        self._as_schalter_cids = None
        self._as_karten = {}             # {cid: Karte} - b-Suite
        self._as_offen = set()           # {(cid, ort)} aufgeklappt
        # SEITE IM INDUSTRY-REITER STATT EIGENEM HAUPTREITER (emm887,
        # Nutzer: "Assets kommt in den Industry Tab unterhalb von
        # Industry Jobs"). Der Stapel existiert hier schon:
        # `_build_build_tab()` laeuft frueher als dieser Aufbau. Index 7
        # ist die naechste freie Nummer (0 Scanner, 1 Blueprints,
        # 2 Plaene, 3 Strukturen, 4 Jobs, 5 Build from stock,
        # 6 Lagerorte) und steht so auch am Rail-Knopf.
        self.b_stack.addWidget(page)            # 7 - Assets
        self._as_w = page

    # ---- Charaktere an/aus (Muster Industry jobs, emm334) ------------

    def _assets_aus(self):
        return {str(x) for x in (self.settings.get("assets_chars_aus")
                                 or [])}

    def _assets_char_schalten(self, cid, an):
        aus = self._assets_aus()
        if an:
            aus.discard(str(cid))
        else:
            aus.add(str(cid))
        self.settings["assets_chars_aus"] = sorted(aus)
        config.save_settings_async(self.settings)
        _b = (self._as_schalter or {}).get(int(cid))
        if _b is not None:
            self._jobs_schalter_stil(_b, an)
        self._assets_zeichnen()

    def _assets_alle_an(self):
        self.settings["assets_chars_aus"] = []
        config.save_settings_async(self.settings)
        for _b in (self._as_schalter or {}).values():
            _b.blockSignals(True)
            _b.setChecked(True)
            _b.blockSignals(False)
            self._jobs_schalter_stil(_b, True)
        self._assets_zeichnen()

    def _assets_schalter_bauen(self, chars):
        from .mw_bauplan_tabs import KurzLabel
        box = self._as_schalter_box
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
        self._as_schalter = {}
        aus = self._assets_aus()
        for cid, e in sorted((chars or {}).items(),
                             key=lambda kv:
                             str(kv[1].get("name") or "").lower()):
            row = QHBoxLayout(); row.setSpacing(6)
            nl = KurzLabel(str(e.get("name") or cid))
            row.addWidget(nl, 1)
            btn = QPushButton()
            btn.setCheckable(True)
            btn.setFixedWidth(52)
            _an = str(cid) not in aus
            btn.setChecked(_an)
            self._jobs_schalter_stil(btn, _an)
            btn.toggled.connect(
                lambda an, _c=cid: self._assets_char_schalten(_c, an))
            row.addWidget(btn)
            box.addLayout(row)
            self._as_schalter[int(cid)] = btn
        self._as_schalter_cids = set(int(c) for c in (chars or {}))

    # ---- Laden --------------------------------------------------------

    def _assets_seite_gezeigt(self):
        """Beim ersten Oeffnen von selbst laden (Muster PI emm801) -
        danach entscheidet der Refresh-Knopf: CCP cacht /assets/
        serverseitig ohnehin ~1 Stunde."""
        if self._as_daten is None and not self._as_laeuft:
            self._assets_laden()

    def _assets_laden(self):
        if self._as_laeuft:
            return
        client_id = self.settings.get("client_id")
        chars = store.list_characters()
        if not client_id or not chars:
            self._as_stand_lbl.setText(t("No characters linked."))
            return

        def job():
            from .. import nebenlaeufig
            out, tids, orte_alle = {}, set(), {}
            _namen_je = {int(ch["character_id"]):
                         (ch.get("character_name") or ch.get("name")
                          or str(ch["character_id"])) for ch in chars}

            def _hole(cid):
                # Ein Charakter = ein Abruf; Fehler bleiben AUF seiner
                # Karte (je_charakter isoliert sie ohnehin).
                try:
                    _sc = esi.granted_scopes(client_id, cid) or set()
                except Exception:
                    _sc = set()
                if config.ASSETS_SCOPE not in _sc:
                    return {"fehler": t("No assets scope granted – "
                                        "re-link this character."),
                            "orte": {}}
                return {"fehler": None,
                        "orte": char_assets.orte_mengen(
                            esi.fetch_assets_raw(client_id, cid))}
            # NEBENEINANDER STATT NACHEINANDER (emm866, Nutzer: "das
            # laden ... dauert lange"; Assets je Charakter sind mehrere
            # ESI-Seiten): dieselbe Schiene wie das Portfolio.
            for cid, _r, _f in nebenlaeufig.je_charakter(
                    [int(ch["character_id"]) for ch in chars], _hole,
                    max_parallel=4):
                e = {"name": _namen_je.get(int(cid), str(cid)),
                     "fehler": (_r or {}).get("fehler") if _f is None
                     else str(_f)[:120],
                     "orte": (_r or {}).get("orte") or {}}
                for mengen in e["orte"].values():
                    tids.update(mengen)
                for _o in e["orte"]:
                    orte_alle.setdefault(int(_o), []).append(int(cid))
                out[int(cid)] = e
            try:
                namen = esi.resolve_names(list(tids)) if tids else {}
            except Exception:
                namen = store.cached_names(list(tids)) if tids else {}
            # ORTSNAMEN (Muster emm421; emm865 nach Nutzer-Screenshot
            # "teilweise nur zahlen ... koennten auch WH's sein wie
            # Terra"): die ID-ART entscheidet den Abruf. Sonnensysteme
            # (Assets im All, auch Wurmloecher) gehen ueber das
            # oeffentliche /universe/systems/ - vorher liefen sie in den
            # Struktur-Abruf, scheiterten und frassen das Fehlerbudget
            # leer, wonach auch echte Strukturen namenlos blieben.
            # Strukturen brauchen Andockrecht: je Struktur werden bis zu
            # ZWEI besitzende Charaktere probiert (der erste hat
            # vielleicht keins mehr), nach 8 Fehlschlaegen insgesamt
            # keine weitere Anfrage (420er-Budget, emm305).
            _fehl = [0]
            ortsnamen = {}
            for lid, cids in orte_alle.items():
                art = char_assets.ort_art(lid)
                try:
                    if art == "station":
                        s = esi.resolve_station(lid) or {}
                        ortsnamen[lid] = s.get("name")
                    elif art == "system":
                        _nm = (esi.system_info(lid) or {}).get("name")
                        if _nm:
                            ortsnamen[lid] = (str(_nm) + " "
                                              + t("(in space)"))
                    elif art == "structure":
                        for _cid in cids[:2]:
                            if _fehl[0] >= 8:
                                break
                            try:
                                s = esi.resolve_structure(
                                    client_id, _cid, lid) or {}
                                if s.get("name"):
                                    ortsnamen[lid] = s.get("name")
                                    break
                            except Exception:
                                _fehl[0] += 1
                except Exception:
                    _fehl[0] += 1
            # Was dann noch namenlos ist (seltene andere IDs), versucht
            # /universe/names/ in EINEM Rutsch - OHNE Strukturen, die
            # kennt der Sammelabruf nicht und er lehnte sonst den ganzen
            # Block ab.
            _offen = [l for l in orte_alle
                      if not ortsnamen.get(l)
                      and char_assets.ort_art(l) != "structure"]
            if _offen:
                try:
                    ortsnamen.update(esi.resolve_names(_offen) or {})
                except Exception:
                    pass
            return {"chars": out, "namen": namen, "ortsnamen": ortsnamen,
                    "ts": time.time()}

        def done(res):
            self._as_laeuft = False
            self._as_daten = res
            self._as_stand_ts = res.get("ts") or 0.0
            _n_ch = len(res.get("chars") or {})
            _n_orte = len(res.get("ortsnamen") or {})
            self._as_stand_lbl.setText(
                t("{n} character(s) · {m} location(s)").format(
                    n=_n_ch, m=_n_orte))
            self._assets_zeichnen()

        def fail(_err):
            self._as_laeuft = False
            self._as_stand_lbl.setText(t("Loading assets failed."))

        self._as_laeuft = True
        self._as_stand_lbl.setText(t("Loading assets …"))
        self._run(Worker(job), done, fail, overlay=False)

    # ---- Zeichnen -----------------------------------------------------

    def _assets_zeichnen(self):
        d = self._as_daten or {}
        chars = d.get("chars") or {}
        if set(int(c) for c in chars) != self._as_schalter_cids:
            self._assets_schalter_bauen(chars)
        namen = d.get("namen") or {}
        ortsnamen = d.get("ortsnamen") or {}
        suche = self.as_search.text() if hasattr(self, "as_search") else ""
        sucht = bool(str(suche).strip())
        aus = self._assets_aus()
        karten = []
        self._as_karten = {}
        for cid, e in sorted(chars.items(),
                             key=lambda kv:
                             str(kv[1].get("name") or "").lower()):
            if str(cid) in aus:
                continue
            orte = char_assets.suche_filter(e.get("orte") or {}, namen,
                                            suche)
            # DIE KARTE VERSCHWINDET, WENN NICHTS PASST ("dann sehe ich
            # nur noch die charakter karten die Retributions besitzen").
            # Ohne Suche bleibt jede Karte stehen, auch eine leere oder
            # eine mit Fehler - sonst saehe ein 403 wie "kein Besitz"
            # aus (Regel 3: lieber zu viel zeigen als stumm zu wenig).
            if sucht and not orte and not e.get("fehler"):
                continue
            k = self._assets_karte(cid, e, orte, namen, ortsnamen, sucht)
            karten.append(k)
            self._as_karten[int(cid)] = k
        self._as_raster.setze(karten)

    def _assets_karte(self, cid, e, orte, namen, ortsnamen, sucht):
        card = QFrame(); card.setObjectName("Card")
        card.setMinimumWidth(360)
        v = QVBoxLayout(card)
        v.setContentsMargins(12, 10, 12, 10); v.setSpacing(5)
        kopf = QHBoxLayout(); kopf.setSpacing(8)
        name = QLabel(str(e.get("name") or cid))
        # AMBER statt Cyan (emm865, Nutzer: "Ich wuensche Alle
        # uebertitel auch Columnnamen in Amber farbe nicht in diesen
        # Cyan blau") - gilt fuer DIESEN Reiter; die anderen Reiter
        # behalten ihre Farben, bis er es dort auch sagt.
        name.setStyleSheet(f"color:{theme.AMBER}; font-weight:800; "
                           f"font-size:{theme.FS_H2};")
        kopf.addWidget(name)
        kopf.addStretch()
        _n_st = sum(len(m) for m in orte.values())
        zahl = QLabel(t("{n} item type(s)").format(n=_n_st))
        zahl.setObjectName("Muted")
        kopf.addWidget(zahl)
        v.addLayout(kopf)
        if e.get("fehler"):
            fz = QLabel(t("ESI error: {e}").format(e=e["fehler"]))
            fz.setWordWrap(True)
            fz.setStyleSheet(f"color:{theme.RED};")
            v.addWidget(fz)
        card._orte_knoepfe = {}          # {ort: Knopf} - b-Suite
        card._orte_tabellen = {}         # {ort: Tabelle} - b-Suite
        for ort in sorted(orte,
                          key=lambda o: str(ortsnamen.get(o) or o).lower()):
            mengen = orte[ort]
            onm = ortsnamen.get(ort)
            if not onm:
                # emm865: ehrlich sagen, WAS die nackte Zahl ist - eine
                # Struktur ohne Andockrecht laesst ESI namenlos.
                onm = (t("structure {id} (no access)").format(id=ort)
                       if char_assets.ort_art(ort) == "structure"
                       else f"#{ort}")
            auf = (int(cid), int(ort)) in self._as_offen
            kn = QPushButton(("▾ " if auf else "▸ ")
                             + f"{onm} · {len(mengen)}")
            kn.setCursor(Qt.PointingHandCursor)
            kn.setStyleSheet(
                f"QPushButton{{background:transparent; border:none; "
                f"color:{theme.TEXT}; text-align:left; font-weight:600; "
                f"padding:2px 0;}}"
                f"QPushButton:hover{{color:{theme.AMBER};}}")
            kn.setToolTip(t("Click to fold this location's items in or "
                            "out."))
            v.addWidget(kn)
            tbl = QTableWidget(0, 2)
            tbl.setHorizontalHeaderLabels([t("Item"), t("Qty")])
            tbl.verticalHeader().setVisible(False)
            tbl.setEditTriggers(QTableWidget.NoEditTriggers)
            tbl.setVisible(auf)
            if auf:
                self._assets_ort_fuellen(tbl, mengen, namen)
            v.addWidget(tbl)
            kn.clicked.connect(
                lambda _=False, _c=int(cid), _o=int(ort), _t=tbl, _k=kn,
                       _m=mengen, _n=onm:
                self._assets_ort_klappen(_c, _o, _t, _k, _m, _n, namen))
            card._orte_knoepfe[int(ort)] = kn
            card._orte_tabellen[int(ort)] = tbl
        return card

    def _assets_ort_klappen(self, cid, ort, tbl, kn, mengen, onm, namen):
        auf = (cid, ort) in self._as_offen
        if auf:
            self._as_offen.discard((cid, ort))
        else:
            self._as_offen.add((cid, ort))
            if not tbl.rowCount():          # lazy: erst beim Oeffnen
                self._assets_ort_fuellen(tbl, mengen, namen)
        tbl.setVisible(not auf)
        kn.setText(("▸ " if auf else "▾ ")
                   + f"{onm} · {len(mengen)}")

    def _assets_ort_fuellen(self, tbl, mengen, namen):
        # KOMPAKT (emm865, Nutzer-Screenshot: "Beim ausklappen des
        # Dropdowns sieht man nicht alles. 'ITEM' muss nicht so gross
        # stehen, lieber Item und QTY kleiner, dafuer sieht man welche
        # Items/Schiffe da sind"): kleiner Amber-Spaltenkopf, schlanke
        # Zeilen - und eine FESTE Hoehe aus den echten Massen. Das alte
        # setMaximumHeight liess das Layout die Tabelle unter ihren
        # Inhalt quetschen, die einzige Zeile war halb abgeschnitten.
        hh = tbl.horizontalHeader()
        hh.setStyleSheet(
            f"QHeaderView::section{{color:{theme.AMBER}; "
            f"font-size:{theme.FS_SMALL}; font-weight:600; "
            f"padding:1px 4px;}}")
        hh.setFixedHeight(20)
        tbl.verticalHeader().setDefaultSectionSize(22)
        zeilen = sorted(((int(q), str(namen.get(int(t_)) or f"#{t_}"))
                         for t_, q in (mengen or {}).items()),
                        key=lambda z: (-z[0], z[1].lower()))
        tbl.setRowCount(len(zeilen))
        for i, (q, nm) in enumerate(zeilen):
            it = QTableWidgetItem(nm)
            it.setToolTip(nm)
            tbl.setItem(i, 0, it)
            qi = QTableWidgetItem(f"{q:,}")
            qi.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tbl.setItem(i, 1, qi)
        tbl.resizeColumnsToContents()
        from PySide6.QtWidgets import QHeaderView
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        # Bis 8 Zeilen ganz zu sehen, darueber scrollt die Tabelle.
        tbl.setFixedHeight(2 * tbl.frameWidth() + 20
                           + 22 * min(8, max(1, len(zeilen))))
