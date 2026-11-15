"""Reiter "Market Stocks" - sind die Allianz-Doctrinen am Handelsplatz
kaufbar? (emm824, Nutzer 03./04.11.2026)

NUTZER-AUFTRAG (03.11.2026): "Ich moechte jetzt gerne einen Neuen
Industry Tab erstellen also rechts neben Industry. Soll Heissen Market
Stocks. Da soll man verschiedene Allianz Doctrinen per ingame Clipboard
posten koennen, Abspeichern mit Name, es wird eine Doctrine Liste
erstellt wo man prozentual sieht ob sie komplett vorhanden ist. Und
zusaetzlich eine komplette Liste aller Items von Allen Doctrinen und man
muss sehen wieviel Stueck auf dem Markt sind und wie lange sie etwa
halten. damit das funktioniert muss man da natuerlich separat seinen
Tradhub eingeben meistens wird das eine Player Structure wie eine
Keepstar sein."

AUFGABENTEILUNG: geparst wird in `doctrinen.py`, gerechnet in
`marktdeckung.py` - beide ohne Qt, von der aa-Suite direkt prueftbar.
HIER steht nur die Oberflaeche: der eigene Handelsplatz (bewusst
GETRENNT vom globalen Hub-Dropdown - "separat seinen Tradhub eingeben"),
der Abruf-Job, die Doctrine-Karten mit Haken und die Doctrine-
Uebersicht rechts (emm853 - die fruehere Gesamt-Itemliste unten ist auf
Nutzerwunsch weg, ihre Spalten "on book" und "days" leben in der
Positions-Tabelle jeder Karte weiter; Baukosten/Profit je Doctrine
rechnet `_bau_saved_plan_quick_estimate`, dieselbe Schaetzung wie
"My build plans").

DER ABRUF holt vier Dinge in EINEM Job: die Order-Leitern des
Handelsplatzes (Spielerstruktur per `fetch_structure_orders_full`,
NPC-Hub per `hubs.fetch_hub_orders`), die Jita-Preise der Doctrine-Items
(`fetch_type_orders`, je Item eine Anfrage - nur die gebrauchten Items,
kein Voll-Scan), die Markthistorie der HUB-REGION je Item (fuer die
Reichweite; ESI kennt keine Historie je Struktur, die Spalte sagt das)
und daraus das Tagesvolumen. Ergebnis bleibt im Speicher
(`self._ms_markt`) - Order-Leitern sind ein Schnappschuss, kein
Dauerzustand fuer die settings.
"""
import time

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog,
                               QDialogButtonBox, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QMenu, QPlainTextEdit,
                               QProgressBar, QPushButton, QScrollArea,
                               QSpinBox, QSplitter, QTableWidget,
                               QTableWidgetItem, QVBoxLayout, QWidget)

from .. import config, doctrinen, esi, hubs, marktdeckung, store
from ..sprache import t
from ..workers import Worker
from . import icons, theme
from .mw_basis import isk_kurz, kontext_menue, kopier_menue, tab_icon


def _ms_leer():
    return {"hub": None, "aufschlag_pct": marktdeckung.AUFSCHLAG_STANDARD,
            "ziel_standard": doctrinen.ZIEL_STANDARD, "doctrinen": [],
            "abgewaehlt": {},
            # WELCHE KARTEN OFFEN SIND (emm841). Vorher stand der
            # Klappzustand nur im Widget - und JEDES _ms_render baut die
            # Karten neu. Folge beim Nutzer: Haken setzen, Regel aendern
            # oder Markt abrufen klappte alles wieder zu ("Das
            # ein/ausklappen ... funktioniert nicht richtig").
            "aufgeklappt": [],
            # ANGELEGTE DOCTRINEN (emm936): Namen, die es auch OHNE
            # Schiff gibt. Vorher entstand eine Doctrine nur nebenbei
            # beim Einfuegen eines Schiffs.
            "ordner_leer": []}


class MarketStocks:
    # Schwellen fuer die Balkenfarbe - dieselbe Dreiteilung wie ueberall:
    # gruen erst, wenn es verdient ist, rot nur wenn es weh tut.
    MS_PCT_GUT = 90.0
    MS_PCT_OK = 40.0

    # ------------------------------------------------------------ Zustand
    def _ms_state(self):
        """settings["market_stocks"] - EINE Stelle, die fehlende Schluessel
        nachzieht (alte Staende, Mist-Eingaben)."""
        st = self.settings.get("market_stocks")
        if not isinstance(st, dict):
            st = _ms_leer()
            self.settings["market_stocks"] = st
        for k, v in _ms_leer().items():
            st.setdefault(k, v)
        # emm868: alte Staende ohne Ordner-Feld nachziehen (jede alte
        # Karte wird ein Ordner mit ihrem Fit als erstem Schiff).
        doctrinen.ordner_nachruesten(st.get("doctrinen"))
        return st

    def _ms_speichern(self):
        config.save_settings(self.settings)

    def _ms_gruppen(self, st=None):
        """[(doctrine, [schiffe])] - die Doctrinen aus den Schiffen PLUS
        die angelegten ohne Schiff (emm936). EINE Stelle fuer Karte,
        Uebersicht, Dialog und Zaehler."""
        st = st or self._ms_state()
        g = doctrinen.ordner_gruppen(st["doctrinen"])
        hat = {o for o, _d in g}
        for o in (st.get("ordner_leer") or []):
            o = str(o).strip()
            if o and o not in hat:
                hat.add(o)
                g.append((o, []))
        return g

    # ------------------------------------------------------------- Aufbau
    def _build_market_stocks_tab(self):
        w = QWidget()
        root = QVBoxLayout(w)
        root.setContentsMargins(10, 8, 10, 8)
        root.setSpacing(6)
        st = self._ms_state()

        # --- Handelsplatz-Karte -----------------------------------------
        hub_inner = QWidget()
        hv = QVBoxLayout(hub_inner)
        hv.setContentsMargins(6, 4, 6, 6)
        hv.setSpacing(4)
        self.ms_hub = QComboBox()
        self.ms_hub.setToolTip(t(
            "Where your doctrines are SOLD and stock is measured. Usually "
            "a player structure (e.g. a Keepstar) - NPC hubs work too. "
            "Kept separate from the global trading place on purpose."))
        self.ms_hub.currentIndexChanged.connect(self._ms_hub_gewaehlt)
        hv.addWidget(self.ms_hub)
        zeile = QHBoxLayout()
        zeile.setSpacing(6)
        self.ms_fetch_btn = QPushButton(" " + t("Fetch market"))
        self.ms_fetch_btn.setIcon(icons.icon("refresh"))
        self.ms_fetch_btn.setCursor(Qt.PointingHandCursor)
        self.ms_fetch_btn.clicked.connect(self._ms_fetch)
        zeile.addWidget(self.ms_fetch_btn, 0)
        # VOR DEM ABRUF SAGT DIESE ZEILE, WAS ZU TUN IST (emm919) - statt
        # "no data yet" auf jeder Karte.
        self.ms_alter_lbl = QLabel(t("no data yet - press „Fetch market“"))
        self.ms_alter_lbl.setStyleSheet(f"color:{theme.MUTED};")
        zeile.addWidget(self.ms_alter_lbl, 1)
        hv.addLayout(zeile)
        # DAS ALTER LEBT (emm854): die Zeile "data N min old" stand nur
        # beim Render fest und alterte unsichtbar weiter. Jede Minute
        # nachziehen, ab 60 min orange - alte Deckungszahlen sehen sonst
        # aus wie frische.
        self._ms_alter_timer = QTimer(self)
        self._ms_alter_timer.setInterval(60_000)
        self._ms_alter_timer.timeout.connect(self._ms_alter_zeigen)
        self._ms_alter_timer.start()
        hub_card = self._collapsible(t("TRADE HUB"), hub_inner)

        # --- Regeln-Karte ------------------------------------------------
        regel_inner = QWidget()
        rv = QVBoxLayout(regel_inner)
        rv.setContentsMargins(6, 4, 6, 6)
        rv.setSpacing(4)
        r1 = QHBoxLayout()
        r1.setSpacing(6)
        _l1 = QLabel(t("Buyable up to"))
        r1.addWidget(_l1, 0)
        self.ms_aufschlag = QSpinBox()
        self.ms_aufschlag.setRange(0, 500)
        self.ms_aufschlag.setSuffix(" %")
        self.ms_aufschlag.setValue(int(st.get("aufschlag_pct") or 30))
        self.ms_aufschlag.setToolTip(t(
            "Sell orders count as buyable only up to Jita price plus this "
            "margin. Without a cap a single order at 50x price would make "
            "a doctrine look covered. Jita is the reference most of EVE "
            "uses as the normal price."))
        self.ms_aufschlag.editingFinished.connect(self._ms_regel_gesetzt)
        r1.addWidget(self.ms_aufschlag, 0)
        _l2 = QLabel(t("over Jita"))
        r1.addWidget(_l2, 0)
        r1.addStretch(1)
        rv.addLayout(r1)
        r2 = QHBoxLayout()
        r2.setSpacing(6)
        _l3 = QLabel(t("Full at"))
        r2.addWidget(_l3, 0)
        self.ms_ziel = QSpinBox()
        self.ms_ziel.setRange(1, 100000)
        self.ms_ziel.setValue(int(st.get("ziel_standard") or 250))
        self.ms_ziel.setToolTip(t(
            "A doctrine counts as 100% when this many COMPLETE ships are "
            "buyable. Every item scales with its own quantity per fit: "
            "250 ships with 100 rounds each means 25,000 rounds, not 250. "
            "New doctrines start with this target; each doctrine can "
            "override it."))
        self.ms_ziel.editingFinished.connect(self._ms_regel_gesetzt)
        r2.addWidget(self.ms_ziel, 0)
        _l4 = QLabel(t("complete ships"))
        r2.addWidget(_l4, 0)
        r2.addStretch(1)
        rv.addLayout(r2)
        regel_card = self._collapsible(t("RULES"), regel_inner)

        # FLACHE KOPFZEILE wie die Trading-Tabs nach der Kur (emm813/815):
        # Karten nebeneinander, oben buendig, die Listen kriegen den Platz.
        kopf = QHBoxLayout()
        kopf.setSpacing(8)
        kopf.addWidget(hub_card, 2, Qt.AlignTop)
        kopf.addWidget(regel_card, 2, Qt.AlignTop)
        root.addLayout(kopf)

        # Kurze Statuszeile, volle Diagnose im Tooltip (Muster emm812).
        self.ms_status = QLabel("")
        self.ms_status.setStyleSheet(f"color:{theme.MUTED};")
        root.addWidget(self.ms_status)

        # --- Doctrine-Karten links, Doctrine-Uebersicht rechts ----------
        # DIE GESAMT-ITEMLISTE IST WEG (emm853, Nutzer 06.11.2026: "unten
        # was ist das fuer eine zusaetzliche Item Liste? ich brauche nur
        # das oben 1doctrine Retribution und darunter alles was darin an
        # Items dazugehoet"). Ihre Informationen sind NICHT verloren: die
        # Positions-Tabelle jeder Karte traegt jetzt auch "on book" und
        # "days (region volume)" - dieselben Werte, nur dort, wo sie
        # hingehoeren. Rechts stattdessen die Doctrine-Uebersicht ("wie
        # in my Buildplans Tab da werden auch alle Plaene gelistet"):
        # je Doctrine Deckung, Baukosten und Profit.
        self.ms_doc_box = QVBoxLayout()
        self.ms_doc_box.setSpacing(6)
        _doc_wrap = QWidget()
        _dv = QVBoxLayout(_doc_wrap)
        _dv.setContentsMargins(0, 0, 0, 0)
        _dv.addLayout(self.ms_doc_box)
        # Die Leere unter der letzten Karte sagt, wie es weitergeht
        # (emm860) - dezent, kein Alarm.
        _leer860 = QLabel(t("Start with „Create new doctrine“ on the "
                            "right, then add the ships inside the "
                            "doctrine."))
        _leer860.setStyleSheet(f"color:{theme.MUTED}; padding:8px 2px;")
        _dv.addWidget(_leer860, 0)
        _dv.addStretch(1)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(_doc_wrap)
        self.ms_scroll = scroll       # fuer "zur Karte springen" (emm854)

        rechts = QWidget()
        rv2 = QVBoxLayout(rechts)
        rv2.setContentsMargins(0, 0, 0, 0)
        rv2.setSpacing(4)
        # KEINE UEBERSCHRIFT MEHR (emm939, Nutzer-Screenshot 14.11.2026:
        # "Karten sind nicht auf selber Hoehe"): das Label schob die rechte
        # Seite um eine Zeile nach unten; der Knopf und der Tabellenkopf
        # sagen ohnehin "Doctrine".
        # DER EINSTIEG (emm936, Nutzer 14.11.2026: "Ersetze button Paste
        # Ship mit einem groesseren besser zu erkennenden Button
        # auffaellige Amber umrahmung -> Create New Doctrine"). Ablauf:
        # Doctrine anlegen, dann Schiffe IN der Doctrine einfuegen.
        self.ms_neu_btn = QPushButton(" " + t("Create new doctrine"))
        self.ms_neu_btn.setIcon(icons.icon("plus", farbe=theme.AMBER))
        self.ms_neu_btn.setCursor(Qt.PointingHandCursor)
        self.ms_neu_btn.setMinimumHeight(38)
        self.ms_neu_btn.setStyleSheet(
            f"QPushButton {{ border:2px solid {theme.AMBER}; "
            f"color:{theme.AMBER}; font-weight:800; font-size:{theme.FS_H2}; "
            f"padding:6px 14px; border-radius:{theme.RAD_GROSS}; }} "
            f"QPushButton:hover {{ border:2px solid {theme.AMBER}; "
            f"background:{theme.PANEL_HELL}; }}")
        self.ms_neu_btn.setToolTip(t(
            "Create a doctrine first, then add its ships inside it "
            "(„Add ship“ on the doctrine card)."))
        self.ms_neu_btn.clicked.connect(
            lambda _c=False: self._ms_doctrine_neu())
        rv2.addWidget(self.ms_neu_btn)
        self.ms_docs = QTableWidget(0, 5)
        self.ms_docs.setHorizontalHeaderLabels([
            t("Doctrine"), t("stock %"), t("build cost (1 set)"),
            t("profit (1 set)"), t("note")])
        self.ms_docs.setEditTriggers(QTableWidget.NoEditTriggers)
        self.ms_docs.setSelectionBehavior(QTableWidget.SelectRows)
        self.ms_docs.setSelectionMode(QTableWidget.ExtendedSelection)
        self.ms_docs.verticalHeader().setVisible(False)
        self.ms_docs.verticalHeader().setDefaultSectionSize(34)
        # ALLES BEDIENBAR AM PANEL (emm854, Nutzer: "open multiplan per
        # rechtsklick soll auch auf die doctrine gehen in der liste" /
        # "alle columns muessen sortierbar sein"): Rechtsklick-Menue,
        # Doppelklick springt zur Karte, Kopfklick sortiert (manuell -
        # die Kosten-Zellen sind Texte wie "37,234,988 ISK", Qt wuerde
        # sie als Strings sortieren).
        self.ms_docs.setContextMenuPolicy(Qt.CustomContextMenu)
        self.ms_docs.customContextMenuRequested.connect(self._ms_docs_menue)
        self.ms_docs.cellDoubleClicked.connect(self._ms_doc_zeigen)
        # EIN KLICK OEFFNET DIE DOCTRINE LINKS (emm932).
        self.ms_docs.cellClicked.connect(
            lambda r, c: self._ms_doc_zeigen(r, c))
        _hh854 = self.ms_docs.horizontalHeader()
        # KEIN QUERBALKEN (emm919, Nutzer-Screenshot 14.11.2026: die
        # Spalte "profit" war halb abgeschnitten, unten ein Rollbalken).
        # Name und Notiz duerfen schrumpfen (Text wird gekuerzt, voller
        # Text im Tooltip), die drei Zahlenspalten bleiben so breit wie
        # ihr Inhalt. `resizeColumnsToContents` beim Fuellen aendert an
        # Stretch-Spalten nichts.
        from PySide6.QtWidgets import QHeaderView as _QHV919
        # emm938: Spalte 0 traegt die Doctrine-KNOEPFE - ihre Breite setzt
        # `_ms_docs_breite` (breitester Knopf); nur die Notiz dehnt sich.
        for _c919, _m919 in ((0, _QHV919.Interactive),
                             (1, _QHV919.ResizeToContents),
                             (2, _QHV919.ResizeToContents),
                             (3, _QHV919.ResizeToContents),
                             (4, _QHV919.Stretch)):
            _hh854.setSectionResizeMode(_c919, _m919)
        self.ms_docs.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        _hh854.setSectionsClickable(True)
        _hh854.sectionClicked.connect(self._ms_docs_sortieren)
        self.ms_docs.horizontalHeaderItem(2).setToolTip(t(
            "Build cost for ONE complete set of this doctrine (every "
            "fit once) - the same quick estimate as My build plans: "
            "your ME/structure defaults and job fee from the settings, "
            "scanned market prices for the materials. Buy-only items "
            "(faction set to buy, or no recipe) are counted at market "
            "price; only items without any price stay out, named in "
            "the note column."))
        self.ms_docs.horizontalHeaderItem(3).setToolTip(t(
            "Sell value of one set at the GLOBAL trading place minus "
            "fees and the build cost. Items without a price there use "
            "the Jita sell price instead - the note column says so."))
        rv2.addWidget(self.ms_docs, 1)
        self.ms_multi_btn = QPushButton(
            " " + t("Selected doctrines → one multi build plan"))
        self.ms_multi_btn.setIcon(icons.icon("package"))
        self.ms_multi_btn.setCursor(Qt.PointingHandCursor)
        self.ms_multi_btn.setToolTip(t(
            "Select one or more doctrines in the list (Ctrl/Shift) and "
            "turn everything they are missing into ONE multi build "
            "plan. Same rules as per doctrine: unticked, faction-buy "
            "and no-recipe items are named and left out."))
        self.ms_multi_btn.clicked.connect(self._ms_multiplan_auswahl)
        _kn933 = QHBoxLayout()
        _kn933.addWidget(self.ms_multi_btn, 0)
        # BAU-RANGLISTE (emm933, Nutzer 14.11.2026: Idee 4 - "ja").
        self.ms_rang_btn = QPushButton(" " + t("Build ranking"))
        self.ms_rang_btn.setIcon(icons.icon("trophy"))
        self.ms_rang_btn.setCursor(Qt.PointingHandCursor)
        self.ms_rang_btn.setToolTip(t(
            "All items of all doctrines, ranked by build profit per unit "
            "times the missing quantity - what earns most when you fill "
            "the hub. Needs \u201eFetch market\u201c."))
        self.ms_rang_btn.clicked.connect(lambda: self._ms_rangliste_zeigen())
        _kn933.addWidget(self.ms_rang_btn, 0)
        _kn933.addStretch(1)
        rv2.addLayout(_kn933)
        # SPRUNG ZUR INDUSTRIE (emm860, Nutzer: "haette ich gerne das
        # Die Rechte Sidebar von Industry mitkommt, und zwar ... My
        # Buildplans, Industry Jobs, Stock Locations, Structures").
        # Die Seiten LEBEN im Industry-Reiter (ein Qt-Widget hat genau
        # einen Platz) - statt einer Kopie springen diese Knoepfe mit
        # EINEM Klick dorthin: Reiter wechseln + Seite waehlen,
        # derselbe Weg wie die Industry-Rail selbst (_bau_nav).
        _ue3 = QLabel(t("INDUSTRY"))
        _ue3.setStyleSheet(f"color:{theme.MUTED}; font-weight:800; "
                           f"padding-top:6px;")
        rv2.addWidget(_ue3)
        from PySide6.QtWidgets import QGridLayout as _QG860
        _ig = _QG860()
        _ig.setHorizontalSpacing(6)
        _ig.setVerticalSpacing(6)
        self._ms_ind_knoepfe = []
        for _i860, (_txt, _ikn, _seite) in enumerate((
                (t("My build plans"), "copy", 2),
                (t("Industry jobs"), "clock", 4),
                (t("Stock locations"), "map", 6),
                (t("Structures"), "factory", 3))):
            _kn = QPushButton(" " + _txt)
            _kn.setIcon(icons.icon(_ikn))   # b55: Symbolpflicht
            _kn.setCursor(Qt.PointingHandCursor)
            _kn.setToolTip(t("Jumps to this page in the Industry tab."))
            _kn.clicked.connect(
                lambda _c=False, s=_seite: self._ms_industrie_sprung(s))
            _ig.addWidget(_kn, _i860 // 2, _i860 % 2)
            self._ms_ind_knoepfe.append((_kn, _seite))
        rv2.addLayout(_ig)

        split = QSplitter(Qt.Horizontal)
        split.addWidget(scroll)
        split.addWidget(rechts)
        # KARTEN BEKOMMEN DEN PLATZ (emm860, Nutzer: "zu viel leere
        # Platz"): die Uebersicht rechts braucht seit den Kurz-Notizen
        # und kompakten ISK weniger Breite.
        split.setStretchFactor(0, 5)
        split.setStretchFactor(1, 2)
        # DIE KARTEN DUERFEN NICHT VERSCHWINDEN (emm841). Stretch-
        # Faktoren wirken erst beim Ziehen; die ANFANGSverteilung nimmt
        # Qt aus den sizeHints - und eine zugeklappte Karte ist winzig.
        # Feste Startgroessen und ein Kollaps-Verbot fuer beide Seiten
        # gelten auch fuer die neue horizontale Teilung ("Die Doctrine
        # karte muss nicht so breit sein wie das ganze MoMa Fenster").
        split.setCollapsible(0, False)
        split.setCollapsible(1, False)
        scroll.setMinimumWidth(340)
        # emm939: die Uebersicht traegt jetzt Knoepfe mit vollem Namen -
        # sie braucht mehr Breite ("Doctrine Row darf laenger sein doppel
        # so lang"; die Profit-Spalte war abgeschnitten).
        rechts.setMinimumWidth(480)
        split.setSizes([640, 560])
        root.addWidget(split, 1)

        # NAME (emm919, Nutzer 14.11.2026: "eigentlich auch ein nicht
        # passender Name"): der Reiter fuellt Doktrinen am Markt auf.
        tab_icon(self.tabs, w, t("Doctrines"), "clipboard")
        self._ms_markt = None
        self._ms_worker = None
        # Doctrine-Schaetzungen (emm853): {doc_id: dict|None}, dazu eine
        # Generation gegen verspaetete Worker-Ergebnisse (waehrend der
        # Rechnung kann der Nutzer Doctrinen loeschen oder neu abrufen).
        self._ms_est = {}
        self._ms_est_gen = 0
        self._ms_est_worker = None
        # emm854: Sortierzustaende (Spalte, absteigend?) fuer die
        # Positions-Tabellen aller Karten und die Doctrine-Uebersicht,
        # Blink-Timer des Fetch-Knopfs, Rezept-Nachlade-Cache.
        self._ms_pos_sort = None
        self._ms_docs_sort = None
        self._ms_blink_timer = None
        self._ms_rec854 = None
        self._ms_reload_hubs()
        self._ms_render()

    # ------------------------------------------------------ Hub-Dropdown
    def _ms_reload_hubs(self):
        """NPC-Hubs + Markt-Strukturen, dasselbe Befuellmuster wie das
        globale `g_hub` (emm824 bewusst als EIGENE Auswahl: der Verkaufs-
        platz der Doctrinen ist nicht zwangslaeufig der Ort, an dem man
        gerade tradet)."""
        if not hasattr(self, "ms_hub"):
            return
        st = self._ms_state()
        self.ms_hub.blockSignals(True)
        self.ms_hub.clear()
        for _k, label, rid, sid in hubs.NPC_HUBS:
            self.ms_hub.addItem(label, {"region_id": rid, "station_id": sid,
                                        "name": label})
        try:
            structs = [f for f in store.list_favorites()
                       if f.get("kind") == "structure"]
        except Exception:
            structs = []
        cache = self.settings.get("struct_market_cache", {}) or {}
        gezeigt = [f for f in structs
                   if cache.get(str(f.get("structure_id"))) is not False]
        if gezeigt:
            self.ms_hub.insertSeparator(self.ms_hub.count())
            for f in gezeigt:
                # MIT REGION (emm919) - dieselbe Stelle wie die Hub-Auswahl
                # oben (`_struktur_hub_text`).
                self.ms_hub.addItem(self._struktur_hub_text(f), {
                    "structure_id": f.get("structure_id"),
                    "region_id": f.get("region_id"),
                    "character_id": f.get("character_id"),
                    "name": f.get("name") or ""})
        merk = st.get("hub")
        if isinstance(merk, dict):
            for i in range(self.ms_hub.count()):
                d = self.ms_hub.itemData(i)
                if not isinstance(d, dict):
                    continue
                if (merk.get("structure_id")
                        and d.get("structure_id") == merk.get("structure_id")) \
                   or (not merk.get("structure_id")
                        and d.get("station_id")
                        and d.get("station_id") == merk.get("station_id")):
                    self.ms_hub.setCurrentIndex(i)
                    break
        self.ms_hub.blockSignals(False)
        self._regionen_nachladen(gezeigt, self._ms_reload_hubs)

    def _ms_hub_gewaehlt(self, _i=0):
        d = self.ms_hub.currentData()
        if isinstance(d, dict):
            st = self._ms_state()
            st["hub"] = d
            self._ms_speichern()

    def _ms_regel_gesetzt(self):
        st = self._ms_state()
        neu = (int(self.ms_aufschlag.value()), int(self.ms_ziel.value()))
        alt = (int(st.get("aufschlag_pct") or 30),
               int(st.get("ziel_standard") or 250))
        if neu == alt:
            return
        st["aufschlag_pct"], st["ziel_standard"] = neu
        self._ms_speichern()
        self._ms_render()

    # ------------------------------------------------- Doctrine-Verwaltung
    def _ms_doctrine_dialog(self, _c=False, vorhanden=None,
                            ordner_vorgabe=None):
        """Schiff einfuegen (oder bearbeiten): Ordner, Name, Ziel,
        EFT-Text. Unbekannte Namen werden VOR dem Speichern angezeigt -
        eine Doctrine, von der die Haelfte fehlt, darf nicht still als
        gedeckt durchgehen (doctrinen.fit_aufloesen meldet sie)."""
        st = self._ms_state()
        dlg = QDialog(self)
        dlg.setWindowTitle(t("Paste ship fit from clipboard"))
        v = QVBoxLayout(dlg)
        v.setSpacing(6)
        # DER UEBERORDNER (emm868, Nutzer: "normalerweise benennt man
        # die Doctrine nach dem DPS schiff, ich muesste also Doctrinen
        # als Ueberordner erstellen koennen"): frei tippbar fuer einen
        # NEUEN Ordner, Liste = die bestehenden.
        oz = QHBoxLayout()
        oz.addWidget(QLabel(t("Doctrine")), 0)
        ordner_feld = QComboBox()
        # emm936: NICHT mehr tippbar - eine Doctrine entsteht ueber
        # "Create new doctrine", hier wird nur gewaehlt (bzw. beim
        # Bearbeiten umgehaengt).
        for _o868, _d868 in self._ms_gruppen(st):
            ordner_feld.addItem(_o868)
        # VORGEWAEHLT: die Doctrine des Schiffs, sonst die links offene
        # (emm932, Nutzer: "beim Einfuegen des Schiffes soll schon die
        # Doctrine gewaehlt werden koennen, wo sie hineingehoert").
        ordner_feld.setCurrentText(
            str((vorhanden or {}).get("ordner") or ordner_vorgabe
                or self._ms_offener_ordner(st) or ""))
        ordner_feld.setToolTip(t("The doctrine this ship belongs to."))
        oz.addWidget(ordner_feld, 1)
        v.addLayout(oz)
        self._ms_dlg_ordner = ordner_feld        # b-Suite
        name_feld = QLineEdit()
        name_feld.setPlaceholderText(t("Ship/fit name (e.g. Retribution DPS)"))
        v.addWidget(name_feld)
        z = QHBoxLayout()
        z.addWidget(QLabel(t("Full at")), 0)
        ziel_feld = QSpinBox()
        ziel_feld.setRange(1, 100000)
        ziel_feld.setValue(int(st.get("ziel_standard") or 250))
        z.addWidget(ziel_feld, 0)
        z.addWidget(QLabel(t("complete ships")), 0)
        z.addStretch(1)
        fac = QCheckBox(t("Build faction items myself (LP blueprints)"))
        fac.setToolTip(t(
            "Some players bought faction blueprints with loyalty points. "
            "ON: faction items go into the build plan too (only those "
            "that actually have a recipe). OFF: faction items stay on "
            "the buy side."))
        z.addWidget(fac, 0)
        v.addLayout(z)
        text_feld = QPlainTextEdit()
        # de_scan3: aus - das ist EVE-FITTING-SYNTAX, kein Anzeigetext:
        # ein EFT-Beispiel sieht in jeder Sprache exakt so aus (Item-Namen
        # sind im Spiel englisch). Eine Uebersetzung waere eine Luege ueber
        # das erwartete Eingabeformat. Ohne Ellipse, die gilt dem Scanner
        # als Ladetext-Indiz.
        text_feld.setPlaceholderText(
            "[Rifter, WC Tackle v1.1]\n200mm AutoCannon II")
        # de_scan3: an
        text_feld.setMinimumSize(420, 260)
        v.addWidget(text_feld, 1)
        hinweis = QLabel("")
        hinweis.setWordWrap(True)
        hinweis.setStyleSheet(f"color:{theme.AMBER};")
        v.addWidget(hinweis)
        kn = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        kn.accepted.connect(dlg.accept)
        kn.rejected.connect(dlg.reject)
        v.addWidget(kn)
        if vorhanden:
            name_feld.setText(vorhanden.get("name") or "")
            ziel_feld.setValue(int(vorhanden.get("ziel")
                                   or st.get("ziel_standard") or 250))
            fac.setChecked(bool(vorhanden.get("faction_bauen")))

        def _vorpruefen():
            txt = text_feld.toPlainText()
            fits = doctrinen.fits_lesen(txt)
            if not fits:
                hinweis.setText(t("No fit header found - the first line "
                                  "must look like [Rifter, My Fit]."))
                return
            try:
                nm = store.name_to_type_id()
            except Exception:
                nm = {}
            unbekannt = []
            for f in fits:
                _p, u = doctrinen.fit_aufloesen(f, nm)
                unbekannt += [x for x in u if x not in unbekannt]
            if unbekannt:
                hinweis.setText(t("Unknown names (need a market scan "
                                  "first?): {namen}").format(
                    namen=", ".join(unbekannt[:8])
                    + ("…" if len(unbekannt) > 8 else "")))
            else:
                hinweis.setText(t("{n} fit(s) recognised, all names "
                                  "resolved.").format(n=len(fits)))

        text_feld.textChanged.connect(_vorpruefen)
        if dlg.exec() != QDialog.Accepted:
            return
        txt = text_feld.toPlainText()
        try:
            nm = store.name_to_type_id()
        except Exception:
            nm = {}
        doc = doctrinen.doctrine_aus_text(
            name_feld.text() or t("Unnamed doctrine"), txt, nm,
            ziel=ziel_feld.value())
        doc["faction_bauen"] = bool(fac.isChecked())
        # emm868: leerer Ordner -> eigener Name (gleiches Verhalten wie
        # die Migration alter Staende).
        doc["ordner"] = (ordner_feld.currentText().strip()
                         or doc["name"] or "?")
        if not doc["fits"]:
            self._flash_tip(t("No fit header found - the first line "
                              "must look like [Rifter, My Fit]."))
            return
        if vorhanden:
            doc["id"] = vorhanden.get("id")
            st["doctrinen"] = [doc if d.get("id") == doc["id"] else d
                               for d in st["doctrinen"]]
        else:
            doc["id"] = max([int(d.get("id") or 0)
                             for d in st["doctrinen"]] + [0]) + 1
            st["doctrinen"].append(doc)
            # Frisch eingefuegt -> offen zeigen (emm841): wer gerade
            # eine Doctrine eingefuegt hat, will ihre Positionen sehen,
            # nicht eine zugeklappte Zeile suchen.
            st.setdefault("aufgeklappt", [])
            if int(doc["id"]) not in st["aufgeklappt"]:
                st["aufgeklappt"].append(int(doc["id"]))
        # Geaenderte/neue Fits -> die gemerkte Schaetzung dieser id ist
        # Geschichte (emm854).
        self._ms_est.pop(int(doc["id"] or 0), None)
        self._ms_speichern()
        self._ms_render()

    def _ms_doctrine_loeschen(self, doc_id):
        st = self._ms_state()
        _d = next((x for x in st["doctrinen"] if x.get("id") == doc_id), None)
        if _d is None:
            return
        from PySide6.QtWidgets import QMessageBox
        if QMessageBox.question(
                self, t("Delete ship?"),
                t("Remove ship „{name}“ from its doctrine? "
                  "The saved fit is lost.").format(
                      name=_d.get("name") or "?"),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No) != QMessageBox.Yes:
            return
        st["doctrinen"] = [x for x in st["doctrinen"]
                           if x.get("id") != doc_id]
        # emm936: das LETZTE Schiff zu loeschen loescht nicht die
        # Doctrine - sie bleibt leer stehen (weg geht sie nur ueber
        # "Delete doctrine").
        _o936 = str(_d.get("ordner") or _d.get("name") or "?").strip() or "?"
        st.setdefault("ordner_leer", [])
        if _o936 not in st["ordner_leer"]:
            st["ordner_leer"].append(_o936)
        st["abgewaehlt"].pop(str(doc_id), None)
        st["aufgeklappt"] = [i for i in (st.get("aufgeklappt") or [])
                             if int(i) != int(doc_id)]
        self._ms_est.pop(int(doc_id or 0), None)
        self._ms_speichern()
        self._ms_render()

    # ------------------------------------------- Doctrine anlegen (emm936)
    def _ms_doctrine_anlegen(self, name):
        """Leere Doctrine anlegen und links oeffnen. False bei leerem
        oder schon vergebenem Namen (dann wird die vorhandene geoeffnet)."""
        st = self._ms_state()
        name = str(name or "").strip()
        if not name:
            return False
        if name in [o for o, _d in self._ms_gruppen(st)]:
            self._flash_tip(t("A doctrine named „{name}“ already exists.")
                            .format(name=name))
            self._ms_ordner_oeffnen(name)
            return False
        st.setdefault("ordner_leer", []).append(name)
        st["offen_ordner"] = name
        self._ms_speichern()
        self._ms_render()
        return True

    def _ms_doctrine_neu(self):
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, t("New doctrine"), t("Doctrine name:"))
        if ok:
            self._ms_doctrine_anlegen(name)

    def _ms_ordner_umbenennen(self, alt, neu):
        """Doctrine umbenennen: Schiffe, Leer-Liste, offene Doctrine und
        Deckungs-Verlauf ziehen mit. False, wenn der Name leer/vergeben."""
        st = self._ms_state()
        alt, neu = str(alt), str(neu or "").strip()
        if not neu or neu == alt:
            return False
        if neu in [o for o, _d in self._ms_gruppen(st)]:
            self._flash_tip(t("A doctrine named „{name}“ already exists.")
                            .format(name=neu))
            return False
        for d in st["doctrinen"]:
            _o = str(d.get("ordner") or d.get("name") or "?").strip() or "?"
            if _o == alt:
                d["ordner"] = neu
        st["ordner_leer"] = [neu if str(o) == alt else o
                             for o in (st.get("ordner_leer") or [])]
        if str(st.get("offen_ordner") or "") == alt:
            st["offen_ordner"] = neu
        try:
            store.doctrine_verlauf_umbenennen(alt, neu)
        except Exception:
            pass
        self._ms_speichern()
        self._ms_render()
        return True

    def _ms_ordner_umbenennen_dialog(self, ordner):
        from PySide6.QtWidgets import QInputDialog
        neu, ok = QInputDialog.getText(
            self, t("Rename doctrine"), t("Doctrine name:"),
            text=str(ordner))
        if ok:
            self._ms_ordner_umbenennen(ordner, neu)

    def _ms_ordner_loeschen(self, ordner, fragen=True):
        """Ganze Doctrine samt ihren Schiffen loeschen."""
        st = self._ms_state()
        ordner = str(ordner)
        weg = [d for d in st["doctrinen"]
               if (str(d.get("ordner") or d.get("name") or "?").strip()
                   or "?") == ordner]
        if fragen:
            from PySide6.QtWidgets import QMessageBox
            if QMessageBox.question(
                    self, t("Delete doctrine?"),
                    t("Delete doctrine „{name}“ with its {n} ship(s)? "
                      "The saved fits are lost.").format(
                          name=ordner, n=len(weg)),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No) != QMessageBox.Yes:
                return False
        _ids = {d.get("id") for d in weg}
        st["doctrinen"] = [d for d in st["doctrinen"]
                           if d.get("id") not in _ids]
        st["ordner_leer"] = [o for o in (st.get("ordner_leer") or [])
                             if str(o) != ordner]
        for i in _ids:
            st["abgewaehlt"].pop(str(i), None)
            self._ms_est.pop(int(i or 0), None)
        st["aufgeklappt"] = [i for i in (st.get("aufgeklappt") or [])
                             if i not in _ids]
        self._ms_speichern()
        self._ms_render()
        return True

    # ---------------------------------------------------------- Marktabruf
    def _ms_fetch(self):
        # Der Klick beweist: der Knopf ist gefunden - die Blink-
        # Erinnerung (emm854) endet auch, wenn der Abruf gleich an
        # fehlendem Hub oder fehlender Doctrine scheitert.
        self._ms_blink_stopp()
        st = self._ms_state()
        hub = self.ms_hub.currentData()
        if not isinstance(hub, dict):
            self._flash_tip(t("Pick a trade hub first."))
            return
        tids = sorted(doctrinen.alle_items(st["doctrinen"]))
        if not tids:
            self._flash_tip(t("Paste a doctrine first - there is nothing "
                              "to measure yet."))
            return
        cid = self.settings.get("client_id")
        region = hub.get("region_id") or config.FORGE_REGION
        # BAUKOSTEN WIE MARKET STATS (emm930): Material vom globalen Hub
        # oben, kein Jita-Rueckfall (Nutzer-Entscheid 14.11.2026). Quelle
        # und Name im GUI-Thread lesen, gerechnet wird im Hintergrund.
        _bq930 = self._ms_bau_quelle()
        _bn930 = self.g_hub.currentText() if hasattr(self, "g_hub") else ""

        def job(progress=None, should_cancel=None):
            import concurrent.futures as cf
            if hub.get("structure_id"):
                voll = esi.fetch_structure_orders_full(
                    cid, hub.get("character_id"), hub["structure_id"],
                    progress=progress)
                buch = {int(k): {"sell": v.get("sell") or []}
                        for k, v in (voll or {}).items()}
            else:
                agg = hubs.fetch_hub_orders(region, hub.get("station_id"),
                                            progress=progress)
                buch = {int(k): {"sell": sorted(v.get("sell_orders") or [])}
                        for k, v in (agg or {}).items()}
            jita, vol = {}, {}
            # NUR die Doctrine-Items - kein Voll-Scan. Jita-Buch und
            # Regions-Historie je Item, acht gleichzeitig (ESI-schonend,
            # dieselbe Groessenordnung wie der Struktur-Abruf selbst).
            from .mw_helpers import tagesvolumen as _tv

            def _eins(tid):
                if should_cancel and should_cancel():
                    return tid, None, None
                _j = None
                try:
                    _b = esi.fetch_type_orders(tid)
                    if _b.get("sell"):
                        _j = float(_b["sell"][0][0])
                except Exception:
                    _j = None
                _v = None
                try:
                    _v = _tv(esi.fetch_market_history(tid, region))
                except Exception:
                    _v = None
                return tid, _j, _v
            with cf.ThreadPoolExecutor(max_workers=8) as ex:
                for i, (tid, _j, _v) in enumerate(
                        ex.map(_eins, tids)):
                    if _j is not None:
                        jita[tid] = _j
                    if _v is not None:
                        vol[tid] = _v
                    if progress:
                        progress(i + 1, len(tids))
            # HANDEL + BAUKOSTEN JE ITEM (emm930): die Historie hat der
            # Abruf eben selbst geschrieben (fetch_market_history).
            try:
                handel = store.item_handel(region, tids, self.MSTATS_TAGE)
            except Exception:
                handel = {}
            try:
                baukosten = self._ms_baukosten(tids, _bq930)
            except Exception:
                baukosten = {}
            return {"buch": buch, "jita": jita, "vol": vol,
                    "ts": time.time(), "hub_name": hub.get("name") or "",
                    "handel": handel, "baukosten": baukosten,
                    "bau_hub": _bn930}

        self.ms_fetch_btn.setEnabled(False)
        self.ms_alter_lbl.setText(t("fetching…"))

        def done(res):
            self.ms_fetch_btn.setEnabled(True)
            self._ms_markt = res
            # Neue Hub-/Jita-Preise -> alte Schaetzungen verwerfen
            # (emm854; der Render rechnet Fehlendes nach).
            self._ms_est = {}
            # DECKUNGS-VERLAUF (emm933): jeder Abruf ist ein Messpunkt.
            try:
                self._ms_verlauf_merken(self._ms_state(), res)
            except Exception as _e933:
                self._log_exception("Doctrines: Verlauf merken", str(_e933))
            self._ms_render()

        def failed(msg):
            self.ms_fetch_btn.setEnabled(True)
            self.ms_alter_lbl.setText(t("fetch failed: {err}").format(
                err=str(msg)[:120]))

        w = Worker(job, with_progress=True, with_cancel=True)
        w.done.connect(done)
        w.failed.connect(failed)
        self._ms_worker = w
        w.start()

    # ------------------------------------------------------------- Anzeige
    def _ms_render(self):
        """Karten + Itemliste aus den gespeicherten Doctrinen und dem
        letzten Marktstand neu bauen. Ohne Abruf stehen die Karten mit
        "no data yet" da - die Doctrinen selbst sieht man sofort."""
        if not hasattr(self, "ms_doc_box"):
            return
        st = self._ms_state()
        markt = getattr(self, "_ms_markt", None) or {}
        buch = markt.get("buch") or {}
        jita = markt.get("jita") or {}
        auf = float(st.get("aufschlag_pct") or 30)
        # Alte Karten weg
        while self.ms_doc_box.count():
            it = self.ms_doc_box.takeAt(0)
            if it.widget() is not None:
                it.widget().deleteLater()
        namen = store.cached_names(list(doctrinen.alle_items(
            st["doctrinen"]).keys()))
        # EINE KARTE JE ORDNER (emm868, Nutzer: "normalerweise benennt
        # man die Doctrine nach dem DPS schiff ... Doctrinen als
        # Ueberordner ... darin die einzelnen Schiffe mit ihren
        # Fittings"; Rueckfrage beantwortet: Ordner-Karte, Ziel je
        # Schiff, Bestand automatisch uebernommen).
        self._ms_ordner_karten = {}
        # NUR DIE GEWAEHLTE DOCTRINE (emm932, Nutzer 14.11.2026: "ich will
        # rechts alle Doctrine gelistet haben. klickt man eine an, geht sie
        # links auf mit den jeweiligen Schiffsdropdowns").
        _offen932 = self._ms_offener_ordner(st)
        for _ord868, _docs868 in self._ms_gruppen(st):
            if _ord868 != _offen932:
                continue
            self.ms_doc_box.addWidget(self._ms_ordner_karte(
                _ord868, _docs868, buch, jita, auf, namen, bool(markt)))
        self._ms_alter_zeigen()
        n_doc = len(st["doctrinen"])
        n_items = len(doctrinen.alle_items(st["doctrinen"]))
        n_ord = len(self._ms_gruppen(st))
        self.ms_status.setText(t("{o} doctrine(s) · {d} ship(s) · {i} "
                                 "distinct item(s)").format(
                                     o=n_ord, d=n_doc, i=n_items)
                               + "  ⓘ")
        self.ms_status.setToolTip(t(
            "Buyable = sell orders at the hub up to Jita + {pct} %. "
            "A doctrine is full at its target of complete ships; every "
            "item scales with its quantity per fit. Unknown names and "
            "items without a Jita price are flagged on their rows.")
            .format(pct=int(auf)))
        self._ms_docs_fuellen(st, markt)
        # FEHLENDE ICONS EINMAL IM HINTERGRUND HOLEN (emm841), dann
        # genau EIN Nachtrag - dasselbe Muster wie Portfolio/Scanner.
        # _table_icon merkt Fehlendes nur vor; wer hier nicht holt,
        # zeigt fuer immer leere Zellen.
        try:
            self._icon_prefetch_pending(self._ms_render)
        except Exception:
            pass

    def _ms_ordner_deckung(self, docs, markt, auf):
        """Deckung einer Doctrine = ihr SCHWAECHSTES Schiff (emm933 -
        dieselbe Regel wie die Uebersicht, emm932). None ohne Markt."""
        if not markt:
            return None
        _ergs = [marktdeckung.doctrine_deckung(
            d, markt.get("buch") or {}, markt.get("jita") or {}, auf)
            for d in docs]
        return min(_ergs, key=lambda e: e["pct"]) if _ergs else None

    def _ms_verlauf_merken(self, st, markt):
        """Je Doctrine einen Messpunkt in den Verlauf (emm933)."""
        auf = float(st.get("aufschlag_pct") or 30)
        _hub = str((markt or {}).get("hub_name") or "")
        _ts = float((markt or {}).get("ts") or time.time())
        eintraege = []
        for _o, _docs in doctrinen.ordner_gruppen(st["doctrinen"]):
            _e = self._ms_ordner_deckung(_docs, markt, auf)
            if _e is not None:
                eintraege.append((_o, _hub, _ts, float(_e["pct"]),
                                  int(_e["fits"]), int(_e["ziel"])))
        if eintraege:
            store.doctrine_verlauf_merken(eintraege)

    def _ms_verlauf_widget(self, punkte):
        """Kleine Kurve der Deckung (emm933): QLabel mit gezeichnetem
        Bild, 0-100 % hoch. Unter zwei Punkten: None (eine Kurve aus
        einem Punkt ist keine)."""
        if not punkte or len(punkte) < 2:
            return None
        from PySide6.QtGui import QPainter, QPen, QPixmap
        from PySide6.QtCore import QPointF
        b, h = 120, 22
        pm = QPixmap(b, h)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        _letzt = punkte[-1][1]
        p.setPen(QPen(QColor(self._ms_balken_farbe(_letzt)), 1.6))
        n = len(punkte)
        pts = [QPointF(2 + i * (b - 4) / (n - 1),
                       h - 2 - max(0.0, min(100.0, pc)) / 100.0 * (h - 4))
               for i, (_ts, pc) in enumerate(punkte)]
        for a, c in zip(pts, pts[1:]):
            p.drawLine(a, c)
        p.end()
        lbl = QLabel()
        lbl.setPixmap(pm)
        lbl.setToolTip(t("Coverage history: {first} % \u2192 {last} % "
                         "over {n} market fetches.").format(
                             first=f"{punkte[0][1]:.0f}",
                             last=f"{_letzt:.0f}", n=n))
        lbl._punkte933 = list(punkte)            # b-Suite
        return lbl

    def _ms_rangliste_daten(self):
        """Bau-Rangliste (emm933): je Item ueber ALLE Doctrinen die
        fehlende Menge (dieselbe Quelle wie Multibauplan/Multibuy,
        `_ms_fehl_paare`, also mit den Haken) und der Baugewinn je Stueck
        (`_ms_handel_zeile`, dieselbe Zahl wie die Kartenspalte). Nur
        Items mit Fehlmenge UND Baugewinn-Zahl; Gesamt = Menge x Gewinn,
        absteigend."""
        st = self._ms_state()
        markt = getattr(self, "_ms_markt", None) or {}
        if not markt:
            return []
        fehlt = {}
        for doc in st["doctrinen"]:
            _erg, paare = self._ms_fehl_paare(doc, st, markt)
            for tid, q in paare:
                if q > 0:
                    fehlt[int(tid)] = fehlt.get(int(tid), 0) + int(q)
        out = []
        for tid, q in fehlt.items():
            _z = self._ms_handel_zeile(tid)
            _gw = _z[2][1]
            if _gw is None:
                continue
            out.append({"tid": tid, "qty": q, "gw": float(_gw),
                        "gesamt": float(_gw) * q, "stk_tag": _z[1][1]})
        out.sort(key=lambda x: (-x["gesamt"], x["tid"]))
        return out

    def _ms_rangliste_zeigen(self):
        """Fenster mit der Bau-Rangliste (emm933) - Tabelle wie Market
        Stats (`_ms_item_tabelle`: Bilder, Sortierung, Rechtsklick)."""
        if not getattr(self, "_ms_markt", None):
            self._flash_tip(t("Press \u201eFetch market\u201c first."))
            return
        daten = self._ms_rangliste_daten()
        if not daten:
            self._flash_tip(t("Nothing missing with a build profit number."))
            return
        zeilen = []
        for x in daten:
            _f = x["gw"] >= 0
            zeilen.append((x["tid"], [
                (f"{x['qty']:,}".replace(",", "'"), x["qty"], None, None),
                (("+" if _f else "") + isk_kurz(x["gw"]), x["gw"],
                 theme.GREEN if _f else theme.RED, None),
                (("+" if x["gesamt"] >= 0 else "") + isk_kurz(x["gesamt"]),
                 x["gesamt"], theme.GREEN if x["gesamt"] >= 0 else theme.RED,
                 t("{n} missing \u00d7 {gw} build profit per unit").format(
                     n=x["qty"], gw=isk_kurz(x["gw"]))),
                (f"{x['stk_tag']:,.0f}".replace(",", "'")
                 if x["stk_tag"] is not None else "\u2013",
                 x["stk_tag"], None, None)]))
        tbl = self._ms_item_tabelle(
            [t("Item"), t("missing"), t("Build profit/unit"),
             t("Total profit"), t("Units/day")], zeilen)
        dlg = QDialog(self)
        dlg.setWindowTitle(t("Build ranking"))
        lay = QVBoxLayout(dlg)
        _roll = QScrollArea()
        _roll.setWidgetResizable(True)
        _roll.setWidget(tbl)
        lay.addWidget(_roll)
        dlg.resize(820, 560)
        dlg.setModal(False)
        self._ms_rang_dlg = dlg                   # b-Suite / gegen GC
        self._ms_rang_tbl = tbl
        dlg.show()

    def _ms_offener_ordner(self, st=None):
        """Welche Doctrine links offen ist (emm932): die gemerkte, wenn es
        sie noch gibt, sonst die erste. Leer, wenn es keine gibt."""
        st = st or self._ms_state()
        _alle = [o for o, _d in self._ms_gruppen(st)]
        if not _alle:
            return ""
        _o = str(st.get("offen_ordner") or "")
        return _o if _o in _alle else _alle[0]

    def _ms_ordner_oeffnen(self, ordner):
        """Doctrine links oeffnen (emm932) - gemerkt, dann neu zeichnen."""
        st = self._ms_state()
        if str(st.get("offen_ordner") or "") != str(ordner):
            st["offen_ordner"] = str(ordner)
            self._ms_speichern()
        self._ms_render()

    def _ms_balken_farbe(self, pct):
        if pct >= self.MS_PCT_GUT:
            return theme.GREEN
        if pct >= self.MS_PCT_OK:
            return theme.AMBER
        return theme.RED

    def _ms_ordner_karte(self, ordner, docs, buch, jita, auf, namen,
                         mit_markt):
        """EINE Karte je Doctrine-ORDNER (emm868): Kopf mit Ordnername,
        Summen (ships/gap ueber alle Schiffe) und "Add ship"; darunter
        je Schiff der bisherige Abschnitt mit EIGENEM Ziel, eigener
        Deckung und eigenem gap (DPS 250, Logi 20 ...)."""
        card = QFrame()
        card.setObjectName("Card")
        v = QVBoxLayout(card)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)
        kopf = QHBoxLayout()
        kopf.setSpacing(8)
        titel = QLabel(str(ordner))
        titel.setStyleSheet(f"color:{theme.AMBER}; font-weight:800; "
                            f"font-size:15px;")
        kopf.addWidget(titel, 1)
        summe = QLabel("")
        summe.setStyleSheet(f"color:{theme.MUTED};")
        kopf.addWidget(summe, 0)
        # DECKUNGS-VERLAUF (emm933) - neben den Summen, am aktuellen Hub.
        _mk933 = getattr(self, "_ms_markt", None) or {}
        try:
            _vw933 = self._ms_verlauf_widget(store.doctrine_verlauf(
                str(ordner), str(_mk933.get("hub_name") or "")))
        except Exception:
            _vw933 = None
        if _vw933 is not None:
            kopf.addWidget(_vw933, 0)
        add_kn = QPushButton(" " + t("Add ship"))
        add_kn.setIcon(icons.icon("plus"))        # b55: Symbolpflicht
        add_kn.setCursor(Qt.PointingHandCursor)
        add_kn.setToolTip(t("Paste another ship fit into this doctrine "
                            "folder."))
        add_kn.clicked.connect(
            lambda _c=False, o=str(ordner):
            self._ms_doctrine_dialog(ordner_vorgabe=o))
        kopf.addWidget(add_kn, 0)
        # emm936: die Doctrine selbst umbenennen / loeschen.
        _ren936 = QPushButton()
        _ren936.setIcon(icons.icon("wrench"))
        _ren936.setToolTip(t("Rename doctrine…"))
        _ren936.setCursor(Qt.PointingHandCursor)
        _ren936.setFixedSize(28, 28)
        _ren936.clicked.connect(
            lambda _c=False, o=str(ordner):
            self._ms_ordner_umbenennen_dialog(o))
        kopf.addWidget(_ren936, 0)
        _del936 = QPushButton()
        _del936.setIcon(icons.icon("trash"))
        _del936.setToolTip(t("Delete doctrine"))
        _del936.setCursor(Qt.PointingHandCursor)
        _del936.setFixedSize(28, 28)
        _del936.clicked.connect(
            lambda _c=False, o=str(ordner): self._ms_ordner_loeschen(o))
        kopf.addWidget(_del936, 0)
        card._ren_kn, card._del_kn = _ren936, _del936   # b-Suite
        v.addLayout(kopf)
        card._leer_lbl = None
        if not docs:
            # LEERE DOCTRINE: sagen, wie es weitergeht, und den Knopf
            # dafuer hervorheben.
            card._leer_lbl = QLabel(t(
                "No ships yet – press „Add ship“ and paste a fit from "
                "the game."))
            card._leer_lbl.setStyleSheet(
                f"color:{theme.MUTED}; padding:10px 2px;")
            v.addWidget(card._leer_lbl)
            add_kn.setStyleSheet(
                f"QPushButton {{ border:2px solid {theme.AMBER}; "
                f"color:{theme.AMBER}; font-weight:800; }} "
                f"QPushButton:hover {{ border:2px solid {theme.AMBER}; "
                f"background:{theme.PANEL_HELL}; }}")
        _fits = _ziel = 0
        _gap = 0.0
        _mit = False
        card._schiffe = []                        # b-Suite
        card._add_kn = add_kn                     # b-Suite
        for d in docs:
            k = self._ms_doc_karte(d, buch, jita, auf, namen, mit_markt)
            k._ms_doc_id932 = int(d.get("id") or 0)   # emm932: hinscrollen
            card._schiffe.append(k)
            v.addWidget(k)
            _e = getattr(k, "_ms_erg868", None)
            if _e is not None:
                _mit = True
                _fits += int(_e.get("fits") or 0)
                _ziel += int(_e.get("ziel") or 0)
            _gap += float(getattr(k, "_ms_gap868", 0.0) or 0.0)
        if _mit:
            summe.setText(t("ships {fits}/{ziel} · gap {isk} ISK")
                          .format(fits=_fits, ziel=_ziel,
                                  isk=isk_kurz(_gap)))
            summe.setToolTip(t("Sum over all ships in this folder - "
                               "each ship keeps its own target and "
                               "coverage below."))
        else:
            summe.setText(t("{n} ship(s)").format(n=len(docs)))
        card._summe_lbl = summe                   # b-Suite
        card._verlauf933 = _vw933                 # b-Suite
        self._ms_ordner_karten[str(ordner)] = card
        return card

    def _ms_doc_karte(self, doc, buch, jita, auf, namen, mit_markt):
        """Eine Doctrine als Karte: Kopf mit Balken, Koerper mit allen
        Positionen und Haken (Standard AN - Nutzer 04.11.2026:
        "Ausgeklappte Doctrine haben alle hacken 'ON' auf allen Modulen
        und gesamten Cargo inhalt")."""
        st = self._ms_state()
        erg = marktdeckung.doctrine_deckung(doc, buch, jita, auf) \
            if mit_markt else None
        card = QFrame()
        card.setObjectName("MsDocCard")
        card.setStyleSheet(
            f"QFrame#MsDocCard{{border:1px solid {theme.BORDER}; "
            f"border-radius:{theme.RAD_GROSS}; background:{theme.schleier(0.03)};}}")
        v = QVBoxLayout(card)
        v.setContentsMargins(8, 6, 8, 6)
        v.setSpacing(4)
        kopf = QHBoxLayout()
        kopf.setSpacing(8)
        pfeil = QPushButton("▸ " + (doc.get("name") or "?"))
        pfeil.setCheckable(True)
        pfeil.setCursor(Qt.PointingHandCursor)
        pfeil.setStyleSheet(
            f"QPushButton{{text-align:left; border:none; background:none; "
            f"color:{theme.AMBER}; font-weight:800; font-size:15px;}}")
        pfeil.setToolTip(t("Click to expand/collapse this doctrine."))
        # DAS SCHIFF ALS GESICHT DER KARTE (emm841, Nutzer: "keine Icons
        # der Schiffe/Items ... man erkennt die Doctrine kaum"). Das
        # Icon des ERSTEN Fit-Rumpfs, aus demselben Cache wie ueberall
        # (_table_icon holt nie synchron aus dem Netz; fehlt das Bild,
        # merkt es sich vor und der Nachtrag traegt es ein).
        _schiff_tid = self._ms_schiff_tid(doc)
        if _schiff_tid:
            from PySide6.QtCore import QSize
            _sic = self._table_icon(int(_schiff_tid), size=32)
            if _sic:
                pfeil.setIcon(_sic)
                pfeil.setIconSize(QSize(26, 26))
        kopf.addWidget(pfeil, 1)
        balken = QProgressBar()
        balken.setRange(0, 100)
        balken.setFixedWidth(260)
        if erg is not None:
            balken.setValue(int(round(erg["pct"])))
            _f = self._ms_balken_farbe(erg["pct"])
            # DER BALKEN SAGT, WAS ER MISST (emm860, Nutzer: "Was ist
            # die prozentangabe bei Doctrin Retribution 0% ?" - ein
            # nackter Prozentwert erklaert sich nicht selbst):
            # Beschriftung IM Balken, Farbe = dieselbe Ampel wie die
            # Prozent-Texte; das frühere "x/y ships"-Label daneben ist
            # damit drin statt doppelt.
            balken.setFormat(t("coverage {pct} % · {fits}/{ziel} "
                               "ships").format(
                pct=f"{erg['pct']:.0f}", fits=erg["fits"],
                ziel=erg["ziel"]))
            balken.setStyleSheet(
                f"QProgressBar{{border:1px solid {theme.BORDER}; "
                f"border-radius:{theme.RAD_KLEIN}; background:{theme.schleier(0.05)}; "
                f"color:{theme.TEXT}; font-weight:700;}} "
                f"QProgressBar::chunk{{background:{_f};}}")
            balken.setToolTip(t(
                "{fits} of {ziel} complete ships buyable - the scarcest "
                "item decides. 95% of the positions are worth nothing "
                "if the ammo is missing.").format(fits=erg["fits"],
                                                  ziel=erg["ziel"]))
            info = None
        else:
            # VOR DEM ABRUF KEIN LEERER BALKEN (emm919, Nutzer-Screenshot
            # 14.11.2026): je Schiff eine lange leere Linie plus "no data
            # yet" war nur Rauschen. Der Balken bleibt im Layout (gleiche
            # Breite, sonst springen die Knoepfe), ist aber unsichtbar;
            # was zu tun ist, sagt EINMAL die Zeile oben neben
            # "Fetch market".
            balken.setValue(0)
            balken.setFormat("")
            _sp919 = balken.sizePolicy()
            _sp919.setRetainSizeWhenHidden(True)
            balken.setSizePolicy(_sp919)
            balken.hide()
            info = QLabel(t("{n} fit(s)").format(
                n=len(doc.get("fits") or [])))
        kopf.addWidget(balken, 0)
        if info is not None:
            info.setStyleSheet(f"color:{theme.MUTED};")
            kopf.addWidget(info, 0)
        # DIE LOCH-SUMME IM KOPF (emm854): was das Auffuellen DIESER
        # Doctrine beim einfachen Einkauf kostet - die Summe der
        # gap-cost-Zellen unten (dieselbe Rechnung, nur addiert),
        # gefuellt nach dem Tabellen-Bau.
        gap_lbl = QLabel("")
        gap_lbl.setStyleSheet(f"color:{theme.MUTED};")
        kopf.addWidget(gap_lbl, 0)
        # BAUGEWINN JE KOMPLETTEM SCHIFF (emm930, Nutzer 14.11.2026: "Alles
        # auch fuer das komplette Schiff in der Doctrine"): Summe der
        # Zeilen "Baugewinn/Stk" x Menge je Fit, gefuellt nach der Tabelle.
        bau_lbl = QLabel("")
        bau_lbl.setStyleSheet(f"color:{theme.MUTED};")
        kopf.addWidget(bau_lbl, 0)
        # BEARBEITEN UND LOESCHEN SICHTBAR (emm841, Nutzer: "Loeschen
        # kann man sie auch nicht wieder"). Beides gab es - aber nur im
        # Rechtsklick-Menue, und ein Menue, das man nicht sieht,
        # existiert fuer den Nutzer nicht. Die Knoepfe rufen DIESELBEN
        # Handler wie das Menue (eine Stelle, Arbeitsregel 9); das
        # Loeschen fragt dort nach wie bisher.
        _knopf_stil = (
            f"QPushButton{{border:none; background:none; padding:2px;}}"
            f"QPushButton:hover{{background:{theme.schleier(0.08)}; "
            f"border-radius:{theme.RAD_KLEIN};}}")
        edit_kn = QPushButton()
        edit_kn.setIcon(icons.icon("wrench"))
        edit_kn.setToolTip(t("Edit ship…"))
        edit_kn.setCursor(Qt.PointingHandCursor)
        edit_kn.setStyleSheet(_knopf_stil)
        edit_kn.setFixedSize(26, 26)
        edit_kn.clicked.connect(
            lambda _c=False, d=doc: self._ms_doctrine_dialog(vorhanden=d))
        kopf.addWidget(edit_kn, 0)
        del_kn = QPushButton()
        del_kn.setIcon(icons.icon("trash"))
        del_kn.setToolTip(t("Delete ship"))
        del_kn.setCursor(Qt.PointingHandCursor)
        del_kn.setStyleSheet(_knopf_stil)
        del_kn.setFixedSize(26, 26)
        del_kn.clicked.connect(
            lambda _c=False, d=doc: self._ms_doctrine_loeschen(d.get("id")))
        kopf.addWidget(del_kn, 0)
        self._ms_del_knopf_letzter = del_kn       # b-Suite
        kopf_w = QWidget()
        kopf_w.setLayout(kopf)
        kopf_w.setContextMenuPolicy(Qt.CustomContextMenu)
        kopf_w.customContextMenuRequested.connect(
            lambda pos, d=doc, kw=kopf_w: self._ms_doc_menue(d, kw, pos))
        v.addWidget(kopf_w)

        koerper = QWidget()
        kv = QVBoxLayout(koerper)
        kv.setContentsMargins(0, 0, 0, 0)
        kv.setSpacing(4)
        if erg is not None and (erg["fehlt_ganz"] or erg["ohne_preis"]):
            warn = []
            if erg["fehlt_ganz"]:
                warn.append(t("{n} item(s) not on the market at all")
                            .format(n=len(erg["fehlt_ganz"])))
            if erg["ohne_preis"]:
                warn.append(t("{n} item(s) without a Jita price "
                              "(counted uncapped)")
                            .format(n=len(erg["ohne_preis"])))
            wl = QLabel("⚠ " + " · ".join(warn))
            wl.setStyleSheet(f"color:{theme.AMBER};")
            wl.setWordWrap(True)
            kv.addWidget(wl)
        kn_zeile = QHBoxLayout()
        kn_zeile.setSpacing(6)
        # ALLE ANHAKEN (emm862, Nutzer: "Ebenso gibts keine button
        # 'tick all'"): das Gegenstueck zu "Untick fully covered" -
        # vorher kam man nur Zeile fuer Zeile zurueck.
        alle_an = QPushButton(" " + t("Tick all"))
        alle_an.setIcon(icons.icon("check"))       # b55: Symbolpflicht
        alle_an.setCursor(Qt.PointingHandCursor)
        alle_an.setToolTip(t(
            "Ticks every position of this card again – the counterpart "
            "of „Untick fully covered“."))
        kn_zeile.addWidget(alle_an, 0)
        self._ms_tickall_letzter = alle_an        # b-Suite
        voll_weg = QPushButton(" " + t("Untick fully covered"))
        voll_weg.setIcon(icons.icon("minus"))      # b55: Symbolpflicht
        voll_weg.setCursor(Qt.PointingHandCursor)
        voll_weg.setToolTip(t(
            "Unticks every position that is already at 100% - what is "
            "left ticked is exactly your remaining work. You can still "
            "tick/untick every row by hand."))
        kn_zeile.addWidget(voll_weg, 0)
        # DER WEG ZUM MULTIBAUPLAN SICHTBAR (emm853, Nutzer: "ich moechte
        # aber auch eine ganze doctrine ... zu einem Multibauplan
        # machen"). Die Mechanik gab es seit emm841 - aber nur im
        # Rechtsklick-Menue, und ein Menue, das man nicht sieht,
        # existiert fuer den Nutzer nicht (dieselbe Lehre wie beim
        # Loesch-Knopf). Der Knopf ruft DENSELBEN Handler (Regel 9).
        multi_kn = QPushButton(" " + t("Multi build plan"))
        multi_kn.setIcon(icons.icon("package"))   # b55: Symbolpflicht
        multi_kn.setCursor(Qt.PointingHandCursor)
        multi_kn.setToolTip(t(
            "New multi build plan from ticked positions"))
        multi_kn.clicked.connect(
            lambda _c=False, d=doc: self._ms_multiplan(d))
        kn_zeile.addWidget(multi_kn, 0)
        self._ms_multi_knopf_letzter = multi_kn   # b-Suite
        # KAUFEN STATT BAUEN (emm854): die Fehlmengen direkt als EVE-
        # Multibuy - fuer alles, was man nicht baut, der schnellste Weg.
        buy_kn = QPushButton(" " + t("Copy missing (multibuy)"))
        buy_kn.setIcon(icons.icon("clipboard"))   # b55: Symbolpflicht
        buy_kn.setCursor(Qt.PointingHandCursor)
        buy_kn.setToolTip(t(
            "Copies every ticked position that is missing as "
            "Name<TAB>quantity - paste straight into EVE's multibuy."))
        buy_kn.clicked.connect(
            lambda _c=False, d=doc: self._ms_multibuy([d]))
        kn_zeile.addWidget(buy_kn, 0)
        self._ms_buy_knopf_letzter = buy_kn       # b-Suite
        fac_info = QLabel(t("Faction items: {art}").format(
            art=t("build myself") if doc.get("faction_bauen")
            else t("buy only")))
        fac_info.setStyleSheet(f"color:{theme.MUTED};")
        kn_zeile.addWidget(fac_info, 0)
        kn_zeile.addStretch(1)
        kv.addLayout(kn_zeile)

        # SECHS SPALTEN STATT ZWOELF (emm874, Nutzer 08.11.2026 zum
        # Screenshot: "meiner meinung nach viel zu viel Zahlen"). Er hat
        # recht - die Tabelle zeigte dieselbe Aussage mehrfach: die
        # Fehlmenge stand zweimal da (Stueck und Prozent), die
        # Voll-Menge war nur Menge-je-Fit mal Ziel, und die Luecke mit
        # und ohne Fracht unterschied sich bei Modulen um Rauschen
        # (249.62m gegen 249.92m). Beim Auffuellen zaehlen drei Fragen:
        # WAS fehlt, WAS kostet es, WO kaufe ich. Alles andere steht
        # weiter da - im Tooltip der Spalte, zu der es gehoert.
        # (Spaltennamen hier bewusst NICHT woertlich: sonst halten die
        # Katalog-Scans tote Eintraege fuer benutzt.)
        # DREI SPALTEN AUS MARKET STATS (emm930): wie schnell es sich am
        # Trade-Hub verkauft, und was das Bauen je Stueck bringt.
        # ANZAHL JE SCHIFF (emm931, Nutzer 14.11.2026: "es braucht also auch
        # noch vor dem Item Name ein Anzahl Column" - 4x Small Focused Beam
        # Laser II sah aus wie 1x). Logisch die LETZTE Spalte (9), sichtbar
        # vor den Namen geschoben (moveSection): so bleiben alle Spalten-
        # nummern der Rechnung, Sortierung und Pruefungen unveraendert.
        tbl = QTableWidget(0, 10)
        tbl.setHorizontalHeaderLabels([
            "", t("Item"), t("missing"), t("cost"), t("cheaper at"),
            t("on book"), t("Trades/day"), t("Units/day"),
            t("Build profit/unit"), t("per ship")])
        tbl.horizontalHeader().moveSection(9, 1)
        tbl.horizontalHeaderItem(9).setToolTip(t(
            "How many of this item ONE ship of the doctrine needs (all "
            "fits added up) - the build profit per ship counts it this "
            "many times."))
        tbl.horizontalHeaderItem(2).setToolTip(t(
            "How many units are missing for your target. Hover a row for "
            "the full picture: per fit, the full target quantity and how "
            "much of it is covered."))
        tbl.horizontalHeaderItem(3).setToolTip(t(
            "What filling this gap costs: missing quantity times the Jita "
            "price, PLUS freight at your own rate once you have set one. "
            "The freight part is an estimate - your number, not a "
            "measured price. The row tooltip splits it up."))
        tbl.horizontalHeaderItem(4).setToolTip(t(
            "Buying one unit HERE (cheapest sell order on the book, "
            "cap ignored) against buying it in Jita and hauling it in. "
            "Grey means one of the two sides is missing - then it is no "
            "comparison, just the only option left."))
        tbl.horizontalHeaderItem(5).setToolTip(t(
            "Units sitting in the sell orders at your trade hub. The "
            "tooltip says how many of them are under your price cap and "
            "how long the stock lasts at the region's daily volume."))
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSelectionBehavior(QTableWidget.SelectRows)
        tbl.verticalHeader().setVisible(False)
        # RECHTSKLICK WIE MARKET STATS + "Copy" (emm930).
        kopier_menue(tbl, lambda pos, d=doc, tb=tbl:
                     self._ms_pos_menue(d, tb, pos))
        abgew = set((st.get("abgewaehlt") or {}).get(
            str(doc.get("id")), []) or [])
        positionen = (erg["positionen"] if erg is not None
                      else self._ms_positionen_ohne_markt(doc))
        vol = (getattr(self, "_ms_markt", None) or {}).get("vol") or {}
        # m3 je Posten fuer die Fracht-Spalten (emm872). Derselbe Helfer
        # wie in der Verkaufsliste: SDE-gepackt, Container raus, Schiffe
        # ohne gepacktes Volumen nur aus dem Cache. Er blockiert nicht -
        # ein fehlendes Schiffsvolumen holt er im Hintergrund nach.
        try:
            _m3map = self._fracht_volumen([int(p["tid"]) for p in positionen])
        except Exception:
            _m3map = {}
        # ALLE SPALTEN SORTIERBAR (emm854, Nutzer). NICHT ueber Qt:
        # Spalte 0 traegt Haken-WIDGETS, Qt sortierte nur die Items und
        # liesse die Haken kleben (dieselbe Lage wie emm852 im Buendel).
        # Stattdessen werden die POSITIONEN vor dem Bau sortiert - nach
        # den Werten, die in den Zellen stehen. EIN Zustand fuer alle
        # Karten, damit der Blick beim Vergleichen nicht springt.
        _hh = tbl.horizontalHeader()
        _hh.setSectionsClickable(True)
        _hh.sectionClicked.connect(self._ms_pos_sortieren)
        _sort = getattr(self, "_ms_pos_sort", None)
        if _sort is not None:
            _nm_sort = namen
            positionen = sorted(
                positionen,
                key=lambda p: self._ms_pos_wert(
                    p, _sort[0], _nm_sort, abgew, vol, jita, _m3map),
                reverse=bool(_sort[1]))
            _hh.setSortIndicatorShown(True)
            _hh.setSortIndicator(_sort[0], Qt.DescendingOrder
                                 if _sort[1] else Qt.AscendingOrder)
        _gap_summe = 0.0
        _gap_ohne = 0
        _gap_fh_summe = 0.0        # dieselbe Luecke frei Haus (emm872)
        tbl.setRowCount(len(positionen))
        for r, p in enumerate(positionen):
            cb = QCheckBox()
            cb.setChecked(int(p["tid"]) not in abgew)
            cb.toggled.connect(lambda on, d=doc, t_=p["tid"]:
                               self._ms_haken(d, t_, on))
            holder = QWidget()
            hl = QHBoxLayout(holder)
            # HAKEN-BOX NICHT MEHR ABGESCHNITTEN (emm940, Nutzer
            # 14.11.2026: "die hacken boxen sind noch etwas abgeschnitten
            # wie immer"). GEMESSEN unter Windows: das Zell-Widget bekommt
            # die Zelle MINUS das Item-Polster aus dem QSS (5px oben/unten,
            # 6px links/rechts) - bei 30px Zeile und 35px Spalte blieben
            # 22x18 fuer eine Box von 20x20. Deshalb: Box fest 20x20, kein
            # Zusatzrand, Zeile und Spalte gross genug (MS_HAKEN_*).
            hl.setContentsMargins(0, 0, 0, 0)
            cb.setFixedSize(self.MS_HAKEN_BOX, self.MS_HAKEN_BOX)
            hl.addWidget(cb, 0, Qt.AlignCenter)
            tbl.setCellWidget(r, 0, holder)
            tbl.setRowHeight(r, self.MS_HAKEN_ZEILE)
            nm = namen.get(int(p["tid"])) or f"#{p['tid']}"
            it_nm = QTableWidgetItem(nm)
            it_nm.setData(Qt.UserRole, int(p["tid"]))
            _ic = self._table_icon(int(p["tid"]))
            if _ic:
                it_nm.setIcon(_ic)
            tbl.setItem(r, 1, it_nm)
            _jf931 = int(p.get("je_fit") or 0)
            _it931 = QTableWidgetItem(f"{_jf931:,}\u00d7".replace(",", "'"))
            _it931.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            tbl.setItem(r, 9, _it931)
            if erg is None:
                # OHNE MARKTABRUF KEINE ZAHLEN ERFINDEN (Regel 1, wie
                # emm841 in der alten Gesamt-Itemliste): 0 ist eine
                # Messung, "noch nicht gemessen" ist ein Strich.
                for c in (2, 3, 4, 5, 6, 7, 8):
                    it = QTableWidgetItem("\u2014")
                    it.setToolTip(t("Not measured yet \u2013 press "
                                    "\u201eFetch market\u201c first."))
                    tbl.setItem(r, c, it)
                continue
            # ---- (2) FEHLT: die eine Zahl, auf die es ankommt --------
            _fe = int(p.get("fehlt_stk", 0) or 0)
            pct = p.get("pct")
            it_fe = QTableWidgetItem(f"{_fe:,}")
            it_fe.setForeground(QColor(theme.RED if _fe > 0
                                       else theme.GREEN))
            # DIE WEGGEFALLENEN SPALTEN LEBEN HIER WEITER (emm874):
            # je Fit, Voll-Menge und Deckung in EINEM Satz.
            it_fe.setToolTip(t(
                "{je} per fit \u00d7 {ziel} = {voll} needed, {pct} covered.")
                .format(je=f"{p['je_fit']:,}", ziel=f"{int(erg.get('ziel') or 0):,}",
                        voll=f"{p['voll_stk']:,}",
                        pct=(f"{pct:.0f} %" if pct is not None else "\u2014")))
            tbl.setItem(r, 2, it_fe)
            # ---- (3) KOSTET: frei Haus, sonst nackt -----------------
            _jp = (jita or {}).get(int(p["tid"]))
            _luecke = _fe * float(_jp or 0.0)
            if _jp:
                _gap_summe += _luecke
            elif _fe > 0:
                _gap_ohne += 1
            _fr872, _vg872, _lkfh872 = self._ms_fracht_zeile(p, jita, _m3map)
            if _lkfh872 is not None:
                _gap_fh_summe += _lkfh872
            # Mit Frachtsatz zeigt die Spalte die Luecke FREI HAUS -
            # ohne ihn die nackte, damit nie eine Null-Fracht so
            # aussieht, als waere der Transport umsonst (Regel 1).
            _zeig874 = _lkfh872 if _lkfh872 is not None else (
                _luecke if _jp else None)
            it_lk = QTableWidgetItem(
                f"{isk_kurz(_zeig874)} ISK" if _zeig874 is not None else "\u2014")
            if _zeig874 is not None:
                it_lk.setForeground(QColor(theme.AMBER))
            if _lkfh872 is not None:
                it_lk.setToolTip(
                    t("Jita {jita} + freight {fr} = {fh} per unit, times "
                      "{n} missing.").format(
                        jita=isk_kurz(_jp or 0.0), fr=isk_kurz(_fr872 or 0.0),
                        fh=isk_kurz(_vg872["jita_frei_haus"]),
                        n=f"{_fe:,}")
                    + " " + t("Exactly: {isk} ISK").format(
                        isk=f"{_lkfh872:,.0f}"))
            elif _jp:
                it_lk.setToolTip(
                    t("Missing quantity times the Jita price - "
                      "what filling the gap costs if you simply "
                      "bought it.")
                    + " " + t("Exactly: {isk} ISK").format(
                        isk=f"{_luecke:,.0f}")
                    + (" " + t("No freight rate set - enter one in the "
                               "sell list or in Regional Trading, then "
                               "this column fills.")
                       if self._fracht_satz() <= 0 else ""))
            else:
                it_lk.setToolTip(t("No Jita price or no volume for this "
                                   "item - nothing is invented here."))
            tbl.setItem(r, 3, it_lk)
            # ---- (4) GUENSTIGER BEI ---------------------------------
            if _vg872["guenstiger"] is None:
                it_cw = QTableWidgetItem("\u2014")
                it_cw.setForeground(QColor(theme.MUTED))
            elif _vg872["nur_eine_seite"]:
                # KEIN Preisvergleich, nur die uebrige Moeglichkeit -
                # darum grau und ohne Prozentzahl (Regel 3).
                it_cw = QTableWidgetItem(
                    t("here") if _vg872["guenstiger"] == "here"
                    else "Jita")          # Eigenname, nicht uebersetzt
                it_cw.setForeground(QColor(theme.MUTED))
                it_cw.setToolTip(
                    t("Nothing on the book here - Jita is simply the only "
                      "source, not the cheaper one.")
                    if _vg872["guenstiger"] == "jita" else
                    t("No Jita price or no freight rate - the other side "
                      "cannot be priced, so this is no comparison."))
            else:
                _wo872 = (t("here") if _vg872["guenstiger"] == "here"
                          else "Jita")
                it_cw = QTableWidgetItem(
                    f"{_wo872}  \u2212{_vg872['diff_pct']:.0f} %")
                it_cw.setForeground(QColor(
                    theme.GREEN if _vg872["guenstiger"] == "here"
                    else theme.AMBER))
                it_cw.setToolTip(t(
                    "Here {local} vs. Jita delivered {fh} - saves {diff} per "
                    "unit, {ges} over the {n} missing.").format(
                        local=isk_kurz(_vg872["local"]),
                        fh=isk_kurz(_vg872["jita_frei_haus"]),
                        diff=isk_kurz(_vg872["diff_stk"]),
                        ges=isk_kurz(_vg872["diff_stk"] * _fe),
                        n=f"{_fe:,}"))
            tbl.setItem(r, 4, it_cw)
            # ---- (5) IM BUCH: mit Deckel und Reichweite im Tooltip ---
            it_ob = QTableWidgetItem(f"{p.get('im_buch', 0):,}")
            _tage = marktdeckung.reichweite_tage(
                p.get("im_buch", 0), vol.get(int(p["tid"])))
            _ob_tip = t("{n} of them under your price cap.").format(
                n=f"{p.get('kaufbar_stk', 0):,}")
            if _tage is not None:
                _ob_tip += " " + t(
                    "Lasts {d} days at the region's daily volume.").format(
                        d=f"{_tage:,.0f}")
            else:
                _ob_tip += " " + t("No region history known for this "
                                   "item - no number is invented.")
            it_ob.setToolTip(_ob_tip)
            tbl.setItem(r, 5, it_ob)
            zusatz = []
            if p.get("leer"):
                zusatz.append(t("not on the market at all"))
            if p.get("wucher"):
                zusatz.append(t("offers exist, but above Jita + cap"))
            if p.get("ohne_preis"):
                zusatz.append(t("no Jita price - counted uncapped"))
            if zusatz:
                it_nm.setToolTip(" · ".join(zusatz))
                it_nm.setForeground(QColor(theme.AMBER))
        # SPALTEN 6-8 (emm930): Handel und Baugewinn je Zeile, und die
        # Summe je komplettem Schiff in den Kopf.
        _set930, _ohne930 = 0.0, 0
        if erg is not None:
            for r, p in enumerate(positionen):
                _z = self._ms_handel_zeile(int(p["tid"]))
                for c, (txt, wert, farbe, tip) in zip((6, 7, 8), _z):
                    it = QTableWidgetItem(txt)
                    it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if farbe:
                        it.setForeground(QColor(farbe))
                    if tip:
                        it.setToolTip(tip)
                    tbl.setItem(r, c, it)
                _gw = _z[2][1]
                if _gw is None:
                    _ohne930 += 1
                else:
                    _set930 += _gw * int(p.get("je_fit") or 0)
            if positionen and _ohne930 < len(positionen):
                bau_lbl.setText(t("build profit per ship: {isk}").format(
                    isk=("+" if _set930 >= 0 else "") + isk_kurz(_set930)))
                bau_lbl.setStyleSheet(
                    f"color:{theme.GREEN if _set930 >= 0 else theme.RED};")
                bau_lbl.setToolTip(t(
                    "Build profit/unit times quantity per ship, summed. "
                    "{n} position(s) without a number (not buildable, no "
                    "build cost or no sell order at the hub) are NOT in "
                    "it.").format(n=_ohne930))
        self._ms_bau_lbl_letzter = bau_lbl        # b-Suite
        tbl.resizeColumnsToContents()
        tbl.setColumnWidth(0, self.MS_HAKEN_SPALTE)          # emm940
        for _r940 in range(tbl.rowCount()):
            tbl.setRowHeight(_r940, self.MS_HAKEN_ZEILE)
        # emm862: die "rechts beschnittenen" Haken-Boxen waren NICHT die
        # Spaltenbreite (die liegt mit 36px ueber dem Bedarf), sondern
        # das Checkbox-WIDGET selbst - Fix im Theme (QCheckBox
        # min-width), nicht hier.
        tbl.setMinimumHeight(min(360, 40 + 26 * max(1, len(positionen))))
        kv.addWidget(tbl)
        if erg is not None:
            # emm872: die zweite Zahl ist dieselbe Luecke FREI HAUS -
            # sie steht nur daneben, wenn ein Frachtsatz gesetzt ist
            # (sonst waere sie eine Kopie der ersten).
            _fh_txt = ""
            if self._fracht_satz() > 0 and _gap_fh_summe > 0:
                _fh_txt = "  ·  " + t("delivered: {isk} ISK").format(
                    isk=isk_kurz(_gap_fh_summe))
            gap_lbl.setText(t("gap: {isk} ISK").format(
                isk=isk_kurz(_gap_summe)) + _fh_txt)
            gap_lbl.setStyleSheet(
                f"color:{theme.GREEN if _gap_summe <= 0 else theme.AMBER};")
            _gt = t("Sum of the gap-cost column: missing quantity times "
                    "the Jita price, over all positions.") \
                + " " + t("Exactly: {isk} ISK").format(
                    isk=f"{_gap_summe:,.0f}")
            if _gap_ohne:
                _gt += " " + t("{n} missing position(s) have no Jita "
                               "price and are NOT in this sum.")\
                    .format(n=_gap_ohne)
            if _fh_txt:
                _gt += "\n" + t(
                    "„delivered“ adds the freight at your rate ({satz} "
                    "ISK/m3) - an estimate, your own number.").format(
                        satz=f"{self._fracht_satz():,}")
            gap_lbl.setToolTip(_gt)

        def _voll_weg():
            if erg is None:
                return
            st2 = self._ms_state()
            ab = set((st2.get("abgewaehlt") or {}).get(
                str(doc.get("id")), []) or [])
            ab |= {int(p["tid"]) for p in erg["positionen"]
                   if (p.get("pct") or 0) >= 100.0}
            st2["abgewaehlt"][str(doc.get("id"))] = sorted(ab)
            self._ms_speichern()
            self._ms_render()
        voll_weg.clicked.connect(_voll_weg)

        def _alle_an():
            # emm862: Abwahl-Liste der Karte leeren = alles angehakt.
            # Braucht keinen Marktabruf - Haken gibt es auch davor.
            st2 = self._ms_state()
            (st2.get("abgewaehlt") or {}).pop(str(doc.get("id")), None)
            self._ms_speichern()
            self._ms_render()
        alle_an.clicked.connect(_alle_an)

        koerper.setVisible(False)
        v.addWidget(koerper)

        def _klappen(on):
            pfeil.setText(("▾ " if on else "▸ ")
                          + (doc.get("name") or "?"))
            koerper.setVisible(on)
            # ZUSTAND UEBERLEBT DEN NEUBAU (emm841): _ms_render baut die
            # Karten bei jedem Haken/Regelwechsel/Abruf neu - ohne das
            # hier klappte dabei alles zu.
            st3 = self._ms_state()
            st3.setdefault("aufgeklappt", [])
            _did = int(doc.get("id") or 0)
            if on and _did not in st3["aufgeklappt"]:
                st3["aufgeklappt"].append(_did)
            elif not on and _did in st3["aufgeklappt"]:
                st3["aufgeklappt"].remove(_did)
            # NUR AUF KLICK SPEICHERN (emm873, UI-Wache-Befund): beim
            # AUFBAU der Karte wird der gemerkte Zustand nur
            # wiederhergestellt - da steht derselbe Wert schon in den
            # settings. Trotzdem lief hier je aufgeklappter Karte ein
            # volles config.save_settings (json.dumps ueber ALLE
            # Einstellungen plus Schreiben), und zwar bei JEDEM
            # _ms_render - die Wache hat es mit 1.3 s Blockade erwischt.
            if not getattr(self, "_ms_aufbau873", False):
                self._ms_speichern()
        pfeil.toggled.connect(_klappen)
        if int(doc.get("id") or 0) in set(
                int(i) for i in (st.get("aufgeklappt") or [])):
            self._ms_aufbau873 = True
            try:
                pfeil.setChecked(True)  # loest _klappen(True) aus
            finally:
                self._ms_aufbau873 = False
        # emm868: Deckung und gap-Summe fuer den Ordner-Kopf mitgeben -
        # DIESELBE Rechnung, nur dort addiert (Regel 9: keine zweite).
        card._ms_erg868 = erg
        card._ms_gap868 = _gap_summe if erg is not None else 0.0
        return card

    @staticmethod
    def _ms_positionen_ohne_markt(doc):
        """Karten-Zeilen VOR dem ersten Abruf: Mengen ja, Markt nein."""
        try:
            ziel = max(1, int(doc.get("ziel") or doctrinen.ZIEL_STANDARD))
        except (TypeError, ValueError):
            ziel = doctrinen.ZIEL_STANDARD
        out = []
        for tid, q in sorted(doctrinen.doctrine_bedarf(doc).items()):
            je = q // ziel
            out.append({"tid": tid, "je_fit": je, "voll_stk": q,
                        "kaufbar_stk": 0, "fehlt_stk": q, "pct": None,
                        "reicht_fuer": 0, "ohne_preis": False,
                        "wucher": False, "leer": False})
        return out

    def _ms_haken(self, doc, tid, an):
        st = self._ms_state()
        key = str(doc.get("id"))
        ab = set((st.get("abgewaehlt") or {}).get(key, []) or [])
        if an:
            ab.discard(int(tid))
        else:
            ab.add(int(tid))
        st["abgewaehlt"][key] = sorted(ab)
        self._ms_speichern()

    # --------------------------------------------------------- Kontextmenü
    def _ms_doc_menue(self, doc, w, pos):
        menu = QMenu(w)
        a_multi = menu.addAction(icons.icon("package"), t(
            "New multi build plan from ticked positions"))
        a_edit = menu.addAction(icons.icon("wrench"),
                                t("Edit ship…"))
        a_fac = menu.addAction(icons.icon("star"), t(
            "Faction items: build myself") if not doc.get("faction_bauen")
            else t("Faction items: buy only"))
        a_del = menu.addAction(icons.icon("trash"), t("Delete ship"))
        self._ms_doc_menu_letztes = menu          # b-Suite
        akt = menu.exec(w.mapToGlobal(pos))
        if akt is a_multi:
            self._ms_multiplan(doc)
        elif akt is a_edit:
            self._ms_doctrine_dialog(vorhanden=doc)
        elif akt is a_fac:
            doc["faction_bauen"] = not bool(doc.get("faction_bauen"))
            self._ms_speichern()
            self._ms_render()
        elif akt is a_del:
            self._ms_doctrine_loeschen(doc.get("id"))

    def _ms_pos_menue(self, doc, tbl, pos):
        item = tbl.itemAt(pos)
        if item is None:
            return
        r = item.row()
        zelle = tbl.item(r, 1)
        if zelle is None:
            return
        tid = zelle.data(Qt.UserRole)
        if tid is None:
            return
        # DASSELBE MENUE WIE MARKET STATS (emm930): Markt im Spiel,
        # Einkaufsliste, Bauplan, Multibauplan - EINE Stelle
        # (`_ms_item_menue_bauen`), "Copy" kommt ueber kopier_menue.
        menu, akt_map = self._ms_item_menue_bauen(
            int(tid), zelle.text(), menu=kontext_menue(tbl))
        self._ms_pos_menu_letztes = menu          # b-Suite
        akt = menu.exec(tbl.viewport().mapToGlobal(pos))
        if akt is not None and akt in akt_map:
            self._ms_item_menue_ausfuehren(akt_map[akt], int(tid),
                                           zelle.text())

    def _ms_industrie_sprung(self, seite):
        """Ein Klick von Market Stocks zur Industry-Seite (emm860):
        Reiter wechseln und DIESELBE Navigation nutzen wie die
        Industry-Rail (_bau_nav, Regel 9)."""
        _bw = (getattr(self, "_tab_widget", None) or {}).get("build")
        if _bw is not None:
            self.tabs.setCurrentWidget(_bw)
        try:
            self._bau_nav(int(seite))
        except Exception:
            pass

    def _ms_alter_zeigen(self):
        """Die "data N min old"-Zeile lebendig halten (emm854): jede
        Minute nachgefuehrt, ab 60 Minuten orange mit Klartext - alte
        Deckungszahlen sehen sonst aus wie frische."""
        markt = getattr(self, "_ms_markt", None) or {}
        if not markt.get("ts"):
            # OHNE ABRUF DER HINWEIS, WAS ZU TUN IST (emm919) - er
            # ersetzt das "no data yet" auf jeder einzelnen Karte.
            self.ms_alter_lbl.setText(t(
                "no data yet - press „Fetch market“"))
            self.ms_alter_lbl.setStyleSheet(f"color:{theme.MUTED};")
            self.ms_alter_lbl.setToolTip("")
            return
        _min = int((time.time() - markt["ts"]) // 60)
        self.ms_alter_lbl.setText(t("{name}: data {m} min old").format(
            name=markt.get("hub_name") or "?", m=_min))
        if _min >= 60:
            self.ms_alter_lbl.setStyleSheet(f"color:{theme.AMBER};")
            self.ms_alter_lbl.setToolTip(t(
                "This data is over an hour old - the market has moved "
                "on. Fetch again before you act on it."))
        else:
            self.ms_alter_lbl.setStyleSheet(f"color:{theme.MUTED};")
            self.ms_alter_lbl.setToolTip("")

    def _ms_tab_geoeffnet(self):
        """Beim Oeffnen des Reiters ohne geholten Markt BLINKT der
        Fetch-Knopf kurz (emm854, Nutzer: "fetch market button soll
        blinken wenn man den Tab das erstma mal öffnen, da es sich
        anscheinend nicht vonalleine fetched"). Bewusst bei JEDEM
        Oeffnen ohne Daten (nicht nur dem ersten) und bewusst nur acht
        Schlaege: ein Hinweis, kein Alarm."""
        if getattr(self, "_ms_markt", None):
            return
        if getattr(self, "_ms_blink_timer", None) is not None:
            return                                   # blinkt schon
        self._ms_blink_n = 0

        def _tick():
            self._ms_blink_n += 1
            if self._ms_blink_n > 8:
                self._ms_blink_stopp()
                return
            if self._ms_blink_n % 2:
                self.ms_fetch_btn.setStyleSheet(
                    f"QPushButton{{background:{theme.AMBER}; "
                    f"color:#111111; font-weight:800;}}")
            else:
                self.ms_fetch_btn.setStyleSheet("")
        tm = QTimer(self)
        tm.setInterval(420)
        tm.timeout.connect(_tick)
        self._ms_blink_timer = tm
        tm.start()
        _tick()

    def _ms_blink_stopp(self):
        tm = getattr(self, "_ms_blink_timer", None)
        if tm is not None:
            tm.stop()
            tm.deleteLater()
        self._ms_blink_timer = None
        self.ms_fetch_btn.setStyleSheet("")

    def _ms_doc_zeigen(self, row, _col=0):
        """Doppelklick (oder Menue) in der Uebersicht -> zur Karte
        springen und sie aufklappen (emm854). Bei vielen Doctrinen ist
        die Karte sonst Scroll-Arbeit."""
        it = self.ms_docs.item(int(row), 0)
        if it is None or it.data(Qt.UserRole) is None:
            return
        # emm932: die Zeile ist eine DOCTRINE - links oeffnen.
        if it.data(Qt.UserRole + 1):
            self._ms_ordner_oeffnen(str(it.data(Qt.UserRole + 1)))
            return
        self._ms_doc_zeigen_id(int(it.data(Qt.UserRole)))

    def _ms_doc_knopf(self, ordner):
        """Klick auf einen Doctrine-Knopf rechts (emm936): die Zeile
        markieren (fuer "Selected doctrines -> multi build plan"; mit
        Strg kommt sie zur Auswahl dazu) und die Doctrine links oeffnen."""
        from PySide6.QtWidgets import QApplication, QAbstractItemView
        tbl = self.ms_docs
        _strg = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)
        _sel = ({i.row() for i in tbl.selectedIndexes()} if _strg else set())
        _namen = []
        for r in range(tbl.rowCount()):
            it = tbl.item(r, 0)
            _n = str(it.data(Qt.UserRole + 1)) if it is not None else ""
            if r in _sel or _n == str(ordner):
                _namen.append(_n)
        self._ms_ordner_oeffnen(str(ordner))
        # _ms_render baut die Tabelle neu - Auswahl ueber die NAMEN
        # wiederherstellen (die Zeilen koennen gewandert sein).
        _alt = tbl.selectionMode()
        tbl.clearSelection()
        tbl.setSelectionMode(QAbstractItemView.MultiSelection)
        for r in range(tbl.rowCount()):
            it = tbl.item(r, 0)
            if it is not None and str(it.data(Qt.UserRole + 1)) in _namen:
                tbl.selectRow(r)
        tbl.setSelectionMode(_alt)

    def _ms_doc_zeigen_id(self, did):
        """Ein SCHIFF zeigen (emm932): seine Doctrine links oeffnen, das
        Schiff aufklappen und hinscrollen."""
        st = self._ms_state()
        st.setdefault("aufgeklappt", [])
        _doc = next((d for d in st["doctrinen"]
                     if int(d.get("id") or 0) == did), None)
        if _doc is None:
            return
        _ord = str(_doc.get("ordner") or _doc.get("name") or "?").strip() or "?"
        if did not in st["aufgeklappt"]:
            st["aufgeklappt"].append(did)
        st["offen_ordner"] = _ord
        self._ms_speichern()
        self._ms_render()
        _karte = (getattr(self, "_ms_ordner_karten", None) or {}).get(_ord)
        if _karte is not None:
            for _k in getattr(_karte, "_schiffe", []):
                if int(getattr(_k, "_ms_doc_id932", 0) or 0) == did:
                    self.ms_scroll.ensureWidgetVisible(_k)
                    break

    def _ms_docs_menue(self, pos):
        """Rechtsklick in der Doctrine-Uebersicht (emm854, Nutzer:
        "open multiplan per rechtsklick soll auch auf die doctrine
        gehen in der liste nicht nur über den button unten rechts").
        Gilt fuer die MARKIERTEN Doctrinen; ohne Markierung fuer die
        Zeile unter dem Zeiger. Dieselben Handler wie Knopf und
        Karte (Regel 9)."""
        zeilen = sorted({i.row() for i in self.ms_docs.selectedIndexes()})
        _unter = self.ms_docs.itemAt(pos)
        if not zeilen and _unter is not None:
            zeilen = [_unter.row()]
        st = self._ms_state()
        ids = self._ms_docs_ids(zeilen)           # emm932: alle Schiffe
        docs = [d for d in st["doctrinen"] if int(d.get("id") or 0) in ids]
        # emm936: genau EINE Doctrine -> auch umbenennen / loeschen
        # (gilt auch fuer eine leere).
        _it936 = self.ms_docs.item(zeilen[0], 0) if len(zeilen) == 1 else None
        _ord936 = (str(_it936.data(Qt.UserRole + 1) or "")
                   if _it936 is not None else "")
        if not docs and not _ord936:
            return
        menu = QMenu(self.ms_docs)
        a_multi = a_buy = a_karte = a_ren = a_del = None
        if docs:
            a_multi = menu.addAction(icons.icon("package"),
                                     t("New multi build plan"))
            a_buy = menu.addAction(icons.icon("clipboard"),
                                   t("Copy missing (multibuy)"))
            a_karte = menu.addAction(icons.icon("search"), t("Show card"))
        if _ord936:
            if docs:
                menu.addSeparator()
            a_ren = menu.addAction(icons.icon("wrench"),
                                   t("Rename doctrine…"))
            a_del = menu.addAction(icons.icon("trash"),
                                   t("Delete doctrine"))
        self._ms_docs_menu_letztes = menu         # b-Suite
        akt = menu.exec(self.ms_docs.viewport().mapToGlobal(pos))
        if akt is None:
            return
        if akt is a_ren:
            self._ms_ordner_umbenennen_dialog(_ord936)
        elif akt is a_del:
            self._ms_ordner_loeschen(_ord936)
        elif akt is a_multi:
            self._ms_multiplan_docs(docs)
        elif akt is a_buy:
            self._ms_multibuy(docs)
        elif akt is a_karte:
            self._ms_doc_zeigen_id(int(docs[0].get("id") or 0))

    def _ms_docs_sortieren(self, col):
        """Kopfklick in der Uebersicht (emm854: "alle columns muessen
        sortierbar sein") - manuell, weil die Kosten-Zellen Texte sind;
        zweiter Klick dreht die Richtung."""
        alt = getattr(self, "_ms_docs_sort", None)
        if alt and alt[0] == col:
            self._ms_docs_sort = (col, not alt[1])
        else:
            self._ms_docs_sort = (col, False)
        self._ms_docs_fuellen(self._ms_state(),
                              getattr(self, "_ms_markt", None) or {})

    def _ms_pos_sortieren(self, col):
        """Kopfklick in der Positions-Tabelle einer Karte - EIN
        Sortierzustand fuer alle Karten (konsistent beim Vergleichen),
        angewandt beim Neubau in _ms_doc_karte."""
        alt = getattr(self, "_ms_pos_sort", None)
        if alt and alt[0] == col:
            self._ms_pos_sort = (col, not alt[1])
        else:
            self._ms_pos_sort = (col, False)
        self._ms_render()

    def _ms_fracht_zeile(self, p, jita, m3map):
        """Fracht und Platz-Vergleich EINER Karten-Zeile - die EINE
        Stelle dafuer (Regel 9): Zellen UND Sortierung lesen von hier
        (emm872).

        Rueckgabe (fracht_stk, vergleich, luecke_frei_haus); jeder Wert
        darf None sein - ohne Frachtsatz, ohne Volumen oder ohne
        Jita-Preis wird NICHT gerechnet, sondern ein Strich gezeigt."""
        tid = int(p["tid"])
        _jp = (jita or {}).get(tid)
        _fr = marktdeckung.fracht_je_stueck(
            (m3map or {}).get(tid), self._fracht_satz())
        _vg = marktdeckung.fracht_vergleich(_jp, p.get("bester_sell"), _fr)
        _fehlt = int(p.get("fehlt_stk", 0) or 0)
        _lk_fh = (_fehlt * _vg["jita_frei_haus"]
                  if _vg["jita_frei_haus"] is not None else None)
        return _fr, _vg, _lk_fh

    def _ms_pos_wert(self, p, col, namen, abgew, vol, jita, m3map=None):
        """Sortierwert einer Karten-Zeile - dieselben Werte, die auch
        in den Zellen stehen (keine zweite Rechnung); Unmessbares
        sortiert ans Ende (-1). Seit emm874 sechs Spalten:
        Haken | Item | fehlt | kostet | guenstiger bei | im Buch."""
        tid = int(p["tid"])
        if col == 0:
            return 0 if tid in abgew else 1
        if col == 1:
            return (namen.get(tid) or f"#{tid}").lower()
        if col == 2:
            return p.get("fehlt_stk") or 0
        if col == 3:
            # DIESELBE Zahl wie in der Zelle: frei Haus, wenn es einen
            # Frachtsatz gibt, sonst die nackte Luecke.
            _fr, _vg, _lkfh = self._ms_fracht_zeile(p, jita, m3map)
            if _lkfh is not None:
                return _lkfh
            _jp = (jita or {}).get(tid)
            return ((p.get("fehlt_stk", 0) or 0) * float(_jp)
                    if _jp else -1.0)
        if col == 4:
            # Nach Ersparnis sortieren: "hier guenstiger" positiv,
            # "Jita guenstiger" negativ - so stehen die beiden Lager
            # getrennt, das groesste Sparpotenzial aussen.
            _fr, _vg, _lkfh = self._ms_fracht_zeile(p, jita, m3map)
            if _vg["diff_stk"] is None:
                return 0.0
            return (_vg["diff_stk"] if _vg["guenstiger"] == "here"
                    else -_vg["diff_stk"])
        if col == 5:
            return p.get("im_buch") or 0
        if col == 9:
            return int(p.get("je_fit") or 0)      # emm931: pro Schiff
        if col in (6, 7, 8):
            # DIESELBEN Werte wie in den Zellen (emm930).
            _w = self._ms_handel_zeile(tid)[col - 6][1]
            return _w if _w is not None else -1e18
        return 0

    def _ms_handel_zeile(self, tid):
        """Die drei Zellen (Abschluesse/Tag, Stueck/Tag, Baugewinn/Stk)
        einer Doctrine-Zeile als [(text, wert, farbe, tooltip)] (emm930).
        Quelle: der letzte "Fetch market" (`handel`, `baukosten`, Buch
        des Trade-Hubs). Baugewinn = guenstigste Sell-Order AM HUB nach
        Steuer+Broker minus Baukosten - ohne Sell-Order oder ohne
        Baukosten ein Strich, kein Ersatzpreis (wie Bauplan)."""
        markt = getattr(self, "_ms_markt", None) or {}
        _tg = max(1, int(self.MSTATS_TAGE))
        _h = (markt.get("handel") or {}).get(int(tid))
        _strich = ("\u2013", None, theme.MUTED, None)
        if _h:
            _ab = _h["abs"] / _tg
            _un = _h["vol"] / _tg
            _hz = [(f"{_ab:,.0f}".replace(",", "'"), _ab, None, None),
                   (f"{_un:,.0f}".replace(",", "'"), _un, None, None)]
        else:
            _hz = [_strich, _strich]
        _bk = (markt.get("baukosten") or {}).get(int(tid))
        _sells = ((markt.get("buch") or {}).get(int(tid)) or {}).get("sell") or []
        try:
            _vk = float(min(float(_e[0]) for _e in _sells)) if _sells else 0.0
        except (TypeError, ValueError, IndexError):
            _vk = 0.0
        if _bk and _vk > 0:
            _netto = _vk * (1 - self._ms_gebuehren())
            _gw = _netto - float(_bk)
            _gz = (("+" if _gw >= 0 else "") + isk_kurz(_gw), _gw,
                   theme.GREEN if _gw >= 0 else theme.RED,
                   t("Build profit per unit: sells here for {sell} ({net} "
                     "after tax and broker), build cost {cost} with "
                     "material prices from {hub}.").format(
                         sell=isk_kurz(_vk), net=isk_kurz(_netto),
                         cost=isk_kurz(float(_bk)),
                         hub=markt.get("bau_hub") or "?"))
        else:
            _gz = _strich
        return _hz + [_gz]

    def _ms_fehl_paare(self, doc, st, markt):
        """(deckung, [(tid, fehlende Stueckzahl)]) einer Doctrine nach
        Haken - die EINE Quelle fuer Multibauplan UND Multibuy
        (emm854). Ohne Marktabruf ist die Fehlmenge die volle
        Zielmenge (doctrine_deckung mit leerem Buch)."""
        erg = marktdeckung.doctrine_deckung(
            doc, markt.get("buch") or {}, markt.get("jita") or {},
            float(st.get("aufschlag_pct") or 30))
        abgew = set((st.get("abgewaehlt") or {}).get(
            str(doc.get("id")), []) or [])
        paare = [(int(p["tid"]), int(p.get("fehlt_stk") or 0))
                 for p in erg["positionen"]
                 if int(p["tid"]) not in abgew]
        return erg, paare

    def _ms_multibuy(self, docs):
        """Fehlmengen (nach Haken) als EVE-Multibuy in die
        Zwischenablage (emm854): dasselbe Name<TAB>Menge-Format wie
        Einkaufsliste und Stock Locations (lagerorte.multibuy_text,
        Regel 9). Unaufgeloeste Namen ("#123") kann EVEs Multibuy
        nicht lesen (emm359) - sie werden GEZAEHLT weggelassen, nie
        still mitkopiert."""
        from .. import lagerorte
        st = self._ms_state()
        markt = getattr(self, "_ms_markt", None) or {}
        sammel = {}
        for doc in docs:
            _erg, paare = self._ms_fehl_paare(doc, st, markt)
            for tid, q in paare:
                if q > 0:
                    sammel[tid] = sammel.get(tid, 0) + q
        if not sammel:
            self._flash_tip(t("Nothing ticked is missing - there is "
                              "nothing to build."))
            return
        namen = store.cached_names(sorted(sammel))
        posten, ohne_name = [], 0
        for tid, q in sammel.items():
            nm = namen.get(int(tid))
            if not nm:
                ohne_name += 1
                continue
            posten.append((nm, q))
        if not posten:
            self._flash_tip(t("Nothing copied: {n} missing item(s), but "
                              "none with a resolved name.")
                            .format(n=len(sammel)))
            return
        posten.sort(key=lambda nq: nq[0].lower())
        QGuiApplication.clipboard().setText(
            lagerorte.multibuy_text(posten))
        _zusatz = ""
        if ohne_name:
            _zusatz = " " + t("({n} without a resolved name skipped)")\
                .format(n=ohne_name)
        self._flash_tip(t("{n} item(s) copied for EVE multibuy.")
                        .format(n=len(posten)) + _zusatz)

    def _ms_baubar(self, tid, rec=None):
        """Hat dieses Item ein Rezept? Je ITEM gegen product_to_bp, nie
        pauschal ueber die Meta-Gruppe (04.11.2026: 735 Faction-Produkte
        HABEN eins - "es gibt Leute die haben faction blueprints ueber
        Loality Points gekauft und koennen sie selber bauen").
        `rec` laesst den Schaetz-Worker (emm853) seine eigenen,
        frisch geladenen Rezepte vorgeben - dieselbe EINE Pruefung."""
        if rec is None:
            rec = getattr(self, "_bd_recipes", None)
        p2b = getattr(rec, "product_to_bp", None) or {}
        return int(tid) in p2b

    def _ms_faction(self, tid):
        try:
            from .. import industry
            info = (industry.item_category_map() or {}).get(int(tid))
            return bool(info and len(info) > 2 and int(info[2] or 0) == 4)
        except Exception:
            return False

    def _ms_bau_items(self, doc, paare, namen, rec=None):
        """Gemeinsame Aufteilung "Doctrine-Posten -> Plan-Posten"
        (emm853/emm859, EINE Stelle fuer Einzel-Doctrine, Mehrfach-
        Auswahl und die Kosten-Schaetzung der Uebersicht):
        (baubare, benannt, kauf_posten). Faction folgt dem Schalter der
        Doctrine, und was kein Rezept hat, kann nicht gebaut werden -
        seit emm859 fliegen diese Posten aber NICHT mehr raus (Nutzer
        07.11.2026: "ja aber wenn nur kaufen, muss das in die
        Einkaufsliste vom Multiplan selber"): sie kommen als KAUF-Enden
        mit in den Plan. Ein Ende ohne Rezept ist im Buendel-Baum eine
        Kauf-Komponente und steht damit genau dort, wo der Nutzer es
        will - in der Einkaufsliste des Plans."""
        items, raus, kauf = [], [], []
        for tid, menge in paare:
            tid = int(tid)
            if int(menge or 0) <= 0:
                continue
            nm = namen.get(tid) or f"#{tid}"
            if self._ms_faction(tid) and not doc.get("faction_bauen"):
                raus.append(nm + " " + t("(faction, set to buy)"))
                kauf.append({"tid": tid, "name": nm, "qty": int(menge),
                             "kauf": True})
                continue
            if not self._ms_baubar(tid, rec=rec):
                raus.append(nm + " " + t("(no recipe - buy only)"))
                kauf.append({"tid": tid, "name": nm, "qty": int(menge),
                             "kauf": True})
                continue
            items.append({"tid": tid, "name": nm, "qty": int(menge)})
        return items, raus, kauf

    def _ms_multiplan(self, doc):
        """Karte/Rechtsklick auf die Doctrine -> "nur angewaehltes zu
        Multibauplan machen" (Nutzer 04.11.2026)."""
        self._ms_multiplan_docs([doc])

    def _ms_multiplan_auswahl(self):
        """Knopf unter der Doctrine-Uebersicht (emm853, Nutzer
        06.11.2026: "ich moechte aber auch eine ganze doctrine oder gar
        mehrere Doctrinen zu einem Multibauplan machen"): die in der
        Liste markierten Doctrinen werden zu EINEM Plan."""
        st = self._ms_state()
        zeilen = sorted({i.row() for i in self.ms_docs.selectedIndexes()})
        ids = self._ms_docs_ids(zeilen)           # emm932: alle Schiffe
        docs = [d for d in st["doctrinen"] if int(d.get("id") or 0) in ids]
        if not docs:
            self._flash_tip(t("Select one or more doctrines in the "
                              "list first."))
            return
        self._ms_multiplan_docs(docs)

    def _ms_multiplan_docs(self, docs):
        """Eine ODER mehrere Doctrinen -> EIN Multibauplan. Mengen = die
        FEHLENDE Stueckzahl je Doctrine; voll gedeckte oder abgewaehlte
        Zeilen bleiben draussen, gleiche Items ueber mehrere Doctrinen
        werden ADDIERT (der Markt muss alle zugleich tragen - dieselbe
        Logik wie in der Deckungsrechnung)."""
        st = self._ms_state()
        markt = getattr(self, "_ms_markt", None) or {}
        # OHNE REZEPTE PASSIERTE HIER "NICHTS" (emm854, Nutzer: "das
        # klicken auf multibuildplan macht bisher nichts"). _bd_recipes
        # wird erst beim ersten Bauplan-Rechnen gesetzt - wer direkt in
        # Market Stocks arbeitet, hatte nur einen leisen Hinweis. Jetzt
        # laedt der Knopf die Rezepte SELBST nach (industry.
        # recipes_cached, dieselbe EINE Ladequelle wie ueberall) und
        # macht danach weiter.
        rec = getattr(self, "_bd_recipes", None) \
            or getattr(self, "_ms_rec854", None)
        if rec is None:
            from .. import industry
            if not industry.sde_ready():
                self._flash_tip(t("EVE data (SDE) is missing - press "
                                  "„EVE data“ (top right) first."))
                return
            self._flash_tip(t("Loading build recipes…"))

            def _job854():
                return industry.recipes_cached()

            def _done854(r):
                self._ms_rec854 = r
                self._ms_multiplan_docs(docs)

            w = Worker(_job854)
            w.done.connect(_done854)
            w.failed.connect(lambda m: self._flash_tip(
                t("fetch failed: {err}").format(err=str(m)[:80])))
            self._ms_rec_worker854 = w
            w.start()
            return
        sammel, namen_akk, raus, kauf_tids = {}, {}, [], set()
        for doc in docs:
            erg, paare = self._ms_fehl_paare(doc, st, markt)
            namen = store.cached_names(
                [p["tid"] for p in erg["positionen"]])
            items, _raus, _kauf = self._ms_bau_items(doc, paare, namen,
                                                     rec=rec)
            raus += [x for x in _raus if x not in raus]
            # KAUF-POSTEN KOMMEN MIT (emm859, Nutzer: "ja aber wenn nur
            # kaufen, muss das in die Einkaufsliste vom Multiplan
            # selber"): als Enden ohne Rezept kauft der Plan sie und
            # fuehrt sie in seiner Einkaufsliste - vorher wurden sie
            # nur GENANNT und fehlten im Plan.
            for x in items + _kauf:
                sammel[x["tid"]] = sammel.get(x["tid"], 0) + x["qty"]
                namen_akk[x["tid"]] = x["name"]
                if x.get("kauf"):
                    kauf_tids.add(x["tid"])
        # KURZ (Nutzer 07.11.2026: "zu viel text"): die Kauf-Posten
        # stehen ja schon als "(buy)"-Zeilen IM Dialog - der Hinweis
        # erklaert nur noch das Etikett, ohne die Liste zu wiederholen.
        hinweis = None
        if raus:
            hinweis = t("(buy) = bought, not built (no recipe, or "
                        "faction set to buy) – lands in the plan's "
                        "shopping list.")
        items = [{"tid": tid, "name": namen_akk[tid], "qty": q,
                  "kauf": tid in kauf_tids}
                 for tid, q in sorted(sammel.items())]
        if len(items) < 2:
            if raus:
                self._flash_tip(hinweis,
                                ms=getattr(self, "FLASH_LESEN_MS", 2000))
            if len(items) == 1:
                self.open_build_detail(items[0]["tid"], items[0]["name"],
                                       fresh=True)
            else:
                self._flash_tip(t("Nothing ticked is missing - there is "
                                  "nothing to build."))
            return
        self._multi_neu_aus_auswahl(items, hinweis=hinweis)

    # --------------------------------------------- Doctrine-Uebersicht
    def _ms_docs_fuellen(self, st, markt):
        """Rechtes Panel (emm853): "in Market Stock haette ich gerene
        eine auflistung aller Doctrine und infos dazu Baukosten/ Profit
        usw." - je Doctrine eine Zeile; Deckung sofort, Baukosten und
        Profit traegt der Schaetz-Worker nach ("…" solange er rechnet)."""
        if not hasattr(self, "ms_docs"):
            return
        buch = (markt or {}).get("buch") or {}
        jita = (markt or {}).get("jita") or {}
        auf = float(st.get("aufschlag_pct") or 30)
        tbl = self.ms_docs

        def _zeile(doc):
            erg = (marktdeckung.doctrine_deckung(doc, buch, jita, auf)
                   if markt else None)
            return (doc, erg,
                    (self._ms_est or {}).get(int(doc.get("id") or 0)))
        # ALLE SPALTEN SORTIERBAR (emm854) - manuell, nach den Werten
        # hinter den Zellen; seit emm868 INNERHALB jedes Ordners.
        _sort = getattr(self, "_ms_docs_sort", None)

        def _wert854(z):
            _doc, _erg, _e = z
            _col, _desc = _sort
            if _col == 0:
                return str(_doc.get("name") or "").lower()
            if _col == 1:
                return _erg["pct"] if _erg is not None else -1.0
            _est = (_e or {}).get("est")
            if _col == 2:
                return _est["cost"] if _est else -1.0
            if _col == 3:
                return (float(_est.get("profit") or 0.0)
                        if _est else float("-inf"))
            if _col == 4:
                return (int((_e or {}).get("raus") or 0)
                        + int((_e or {}).get("jita_n") or 0))
            return 0
        if _sort is not None:
            _hh = tbl.horizontalHeader()
            _hh.setSortIndicatorShown(True)
            _hh.setSortIndicator(_sort[0], Qt.DescendingOrder
                                 if _sort[1] else Qt.AscendingOrder)
        # EINE ZEILE JE DOCTRINE (emm932, Nutzer 14.11.2026: "das rechts wo
        # steht doctrines, sind nur einzelne Schiffe der Doctrine, nicht die
        # Doctrine selbst"). Die Zeile traegt: UserRole = erstes Schiff
        # (Kompatibilitaet), UserRole+1 = Doctrine-Name, UserRole+2 = alle
        # Schiffs-ids. Deckung = das SCHWAECHSTE Schiff, Kosten/Gewinn =
        # Summe eines kompletten Satzes (je Schiff einmal).
        gruppen = []
        for _o868, _docs868 in self._ms_gruppen(st):
            gruppen.append((_o868, [_zeile(d) for d in _docs868]))

        def _gwert932(g):
            _o, _z = g
            if _sort[0] == 0:
                return str(_o).lower()
            _w = [_wert854(z) for z in _z]
            if not _w:                        # leere Doctrine (emm936)
                return -1.0
            if _sort[0] == 1:
                return min(_w)
            return sum(_w)
        if _sort is not None and gruppen:
            gruppen.sort(key=_gwert932, reverse=bool(_sort[1]))
        tbl.clearSpans()
        tbl.setRowCount(len(gruppen))
        _offen932 = self._ms_offener_ordner(st)
        self._ms_doc_kn = {}                      # {doctrine: Knopf}
        for r, (_o932, _z932) in enumerate(gruppen):
            _ids932 = [int(d.get("id") or 0) for d, _e1, _e2 in _z932]
            it0 = QTableWidgetItem(str(_o932))
            it0.setData(Qt.UserRole, _ids932[0] if _ids932 else 0)
            it0.setData(Qt.UserRole + 1, str(_o932))
            it0.setData(Qt.UserRole + 2, _ids932)
            it0.setToolTip(t("{name} \u00b7 {n} ship(s)").format(
                name=_o932, n=len(_ids932)))
            if _o932 == _offen932:
                _f932 = it0.font()
                _f932.setBold(True)
                it0.setFont(_f932)
                it0.setForeground(QColor(theme.AMBER))
            # emm939: das Schiffsbild sitzt NUR auf dem Knopf - an der
            # Zelle darunter stand es doppelt daneben.
            _ic939 = None
            _stid = self._ms_schiff_tid(_z932[0][0]) if _z932 else None
            if _stid:
                _ic939 = self._table_icon(int(_stid))
            tbl.setItem(r, 0, it0)
            # ECHTE KNOEPFE (emm936, Nutzer 14.11.2026: "mache die
            # Doctrine Liste rechts wirklich Knoepfe um auf die Doctrine
            # zu klicken nicht so Listen wie jetzt"). Der Knopf liegt
            # UEBER der Zelle; die Zelle behaelt Name und ids (Sortierung,
            # Rechtsklick, Mehrfachauswahl fuer den Multiplan).
            _kn936 = QPushButton(" " + str(_o932))
            _kn936.setIcon(_ic939 or icons.icon("package"))
            _kn936.setCursor(Qt.PointingHandCursor)
            _kn936.setToolTip(it0.toolTip())
            _an936 = (_o932 == _offen932)
            _kn936.setStyleSheet(
                f"QPushButton {{ text-align:left; padding:4px 10px; "
                f"margin:0px; border-radius:{theme.RAD_KLEIN}; "
                f"background:{theme.PANEL_HELL if _an936 else theme.PANEL}; "
                f"border:1px solid "
                f"{theme.AMBER if _an936 else theme.BORDER}; "
                f"color:{theme.AMBER if _an936 else theme.TEXT}; "
                f"font-weight:{800 if _an936 else 600}; }} "
                f"QPushButton:hover {{ border:1px solid {theme.AMBER}; "
                f"background:{theme.PANEL_HELL}; }}")
            _kn936.clicked.connect(
                lambda _c=False, o=str(_o932): self._ms_doc_knopf(o))
            # Rechtsklick auf dem Knopf = Rechtsklick in der Zeile.
            _kn936.setContextMenuPolicy(Qt.CustomContextMenu)
            _kn936.customContextMenuRequested.connect(
                lambda _p, k=_kn936: self._ms_docs_menue(
                    self.ms_docs.viewport().mapFromGlobal(
                        k.mapToGlobal(_p))))
            # NICHT ZUSAMMENGEDRUECKT (emm938, Nutzer-Screenshot
            # 14.11.2026: Knopf winzig, Name abgeschnitten, Bild doppelt):
            # der Knopf fuellt die ganze Zelle (kein Rand, durch den das
            # Bild der Zelle darunter schaut), die Zeile hat feste Hoehe,
            # kein Fokusrahmen.
            _kn936.setFocusPolicy(Qt.NoFocus)
            _kn936.setMinimumHeight(30)
            tbl.setCellWidget(r, 0, _kn936)
            tbl.setRowHeight(r, self.MS_DOC_ZEILE)
            self._ms_doc_kn[str(_o932)] = _kn936
            _ergs = [e for _d, e, _x in _z932 if e is not None]
            if _ergs and len(_ergs) == len(_z932):
                _schwach = min(_ergs, key=lambda e: e["pct"])
                it1 = QTableWidgetItem(f"{_schwach['pct']:.0f} %")
                it1.setForeground(QColor(
                    self._ms_balken_farbe(_schwach["pct"])))
                it1.setToolTip(t("weakest ship: {fits}/{ziel} ships")
                               .format(fits=_schwach["fits"],
                                       ziel=_schwach["ziel"]))
            else:
                it1 = QTableWidgetItem("\u2014")
                it1.setToolTip(t("Not measured yet – press "
                                 "„Fetch market“ first."))
            tbl.setItem(r, 1, it1)
            for c in (2, 3, 4):
                tbl.setItem(r, c, QTableWidgetItem("\u2026"))
        tbl.resizeColumnsToContents()
        self._ms_docs_breite()
        # VORHANDENE SCHAETZUNGEN SOFORT, gerechnet wird nur Fehlendes
        # (emm854): sortieren oder rendern wirft die Zahlen nicht mehr
        # weg - der Cache wird bei neuem Abruf und bei Doctrine-
        # Aenderungen geleert.
        self._ms_docs_zellen()
        _fehlt854 = [d for d in st["doctrinen"]
                     if int(d.get("id") or 0) not in (self._ms_est or {})]
        if _fehlt854:
            self._ms_docs_schaetzen()

    def _ms_schiff_tid(self, doc):
        """type_id des ERSTEN Fit-Rumpfs (fuers Gesicht der Karte und
        der Uebersichts-Zeile) - EINE Stelle (emm853, vorher inline in
        der Karte)."""
        try:
            _n2t = getattr(self, "_ms_name2tid", None)
            if _n2t is None:
                _n2t = self._ms_name2tid = store.name_to_type_id()
            for _f in (doc.get("fits") or []):
                _tid = (_n2t or {}).get(
                    str(_f.get("schiff") or "").strip().lower())
                if _tid:
                    return int(_tid)
        except Exception:
            return None
        return None

    def _ms_docs_schaetzen(self):
        """Baukosten/Profit je Doctrine im Hintergrund rechnen (emm853).

        DIESELBE RECHNUNG WIE "MY BUILD PLANS" (Regel 9): je Doctrine
        wird ein Buendel-Plan ueber die baubaren Posten EINES Satzes
        gebaut und durch `_bau_saved_plan_quick_estimate` geschickt -
        keine zweite Kostenformel. "Baukosten werden durch meine
        angegebenen strukturen berechnet und der profit wert muss
        abhaengig vom global hub sein. wenn da fuer ITems kein Preis
        gelistet ist, nehmen wir Jita sell Preis mit der info" (Nutzer
        06.11.2026): Verkaufsseite = Scan des globalen Handelsplatzes;
        fehlt dort ein Preis, springt der im Marktabruf geholte
        Jita-Preis ein und die note-Spalte sagt es."""
        st = self._ms_state()
        docs = [dict(d) for d in st["doctrinen"]]
        if not docs or not hasattr(self, "ms_docs"):
            return
        from .. import industry
        if not industry.sde_ready():
            self._ms_docs_zellen_text(t("Load recipes needed"))
            return
        try:
            snapshot = store.get_snapshot()
        except Exception:
            snapshot = None
        if not snapshot:
            self._ms_docs_zellen_text(t("no market scan"))
            return
        jita_ms = dict((getattr(self, "_ms_markt", None) or {})
                       .get("jita") or {})
        # Namen VOR dem Worker aufloesen - store gehoert dem GUI-Thread.
        _tids = set()
        for doc in docs:
            _tids |= set(doctrinen.doctrine_satz(doc).keys())
        namen = store.cached_names(sorted(_tids))
        self._ms_est_gen += 1
        gen = self._ms_est_gen

        def job():
            pm = {s["type_id"]: s["sell_min"]
                  for s in snapshot if s["sell_min"] > 0}
            try:
                adj = esi.adjusted_prices() or {}
            except Exception:
                adj = {}
            if not adj:
                adj = dict(pm)
            recipes = industry.recipes_cached()
            out = {}
            for doc in docs:
                out[int(doc.get("id") or 0)] = self._ms_doc_est(
                    doc, recipes, pm, adj, jita_ms, namen)
            return out

        def done(res):
            # Verspaetete Ergebnisse (laengst neu gerendert/geloescht)
            # duerfen die Tabelle nicht mehr anfassen.
            if gen != getattr(self, "_ms_est_gen", -1):
                return
            self._ms_est = res or {}
            self._ms_docs_zellen()

        def failed(msg):
            if gen != getattr(self, "_ms_est_gen", -1):
                return
            self._ms_docs_zellen_text(t("fetch failed: {err}").format(
                err=str(msg)[:80]))

        w = Worker(job)
        w.done.connect(done)
        w.failed.connect(failed)
        self._ms_est_worker = w
        w.start()

    def _ms_doc_est(self, doc, recipes, pm, adj, jita_ms, namen):
        """Schaetzung fuer EINEN Satz einer Doctrine: Buendel-Plan aus
        den baubaren Posten, Preise vom globalen Handelsplatz mit
        Jita-Rueckfall je Item (gezaehlt, nicht verschwiegen)."""
        satz = sorted(doctrinen.doctrine_satz(doc).items())
        items, raus, kauf = self._ms_bau_items(doc, satz, namen,
                                               rec=recipes)
        pm2 = dict(pm)
        jita_n = unpriced = 0
        for x in items + kauf:
            if (pm2.get(x["tid"]) or 0) > 0:
                continue
            _j = jita_ms.get(x["tid"])
            if _j and float(_j) > 0:
                pm2[x["tid"]] = float(_j)
                jita_n += 1
            else:
                unpriced += 1
        # KAUF-POSTEN RECHNEN MIT (emm859): mit Preis gehen sie als
        # Kauf-Enden in Kosten UND Verkaufswert des Satzes ein - die
        # Doctrine wird ja als Ganzes angeboten. NUR die ohne jeden
        # Preis bleiben draussen (ein preisloses Ende wuerde den
        # ganzen Baum kippen); sie stehen GEZAEHLT in "unpriced".
        kauf_mit_preis = [x for x in kauf
                          if (pm2.get(x["tid"]) or 0) > 0]
        items = items + kauf_mit_preis
        if not items:
            return {"est": None, "raus": len(raus), "jita_n": jita_n,
                    "unpriced": unpriced}
        from .. import industry
        if len(items) == 1:
            p = {"type_id": int(items[0]["tid"]),
                 "qty": int(items[0]["qty"])}
        else:
            p = {"type_id": industry.BUENDEL_ID, "qty": 1,
                 "enden": [[int(x["tid"]), int(x["qty"])]
                           for x in items]}
        est = self._bau_saved_plan_quick_estimate(p, recipes, pm2, adj)
        return {"est": est, "raus": len(raus), "jita_n": jita_n,
                "unpriced": unpriced}

    def _ms_docs_zellen_text(self, text):
        """Alle Kosten/Profit-Zellen auf denselben Hinweis setzen (keine
        Rechnung moeglich: Rezepte oder Scan fehlen)."""
        tbl = getattr(self, "ms_docs", None)
        if tbl is None:
            return
        for r in range(tbl.rowCount()):
            for c in (2, 3):
                it = QTableWidgetItem("—")
                it.setToolTip(text)
                tbl.setItem(r, c, it)
            tbl.setItem(r, 4, QTableWidgetItem(text))
        tbl.resizeColumnsToContents()

    def _ms_est_summe(self, ids):
        """Schaetzung einer Doctrine = Summe der Schiffs-Schaetzungen
        (emm932). None, solange eine fehlt; est None, wenn ein Schiff
        nicht schaetzbar ist (dann ist der Satz es auch nicht)."""
        _e = [(self._ms_est or {}).get(int(i)) for i in (ids or [])]
        if not _e or any(x is None for x in _e):
            return None
        if len(_e) == 1:
            return _e[0]
        out = {k: sum(int(x.get(k) or 0) for x in _e)
               for k in ("raus", "unpriced", "jita_n")}
        if any(x.get("est") is None for x in _e):
            out["est"] = None
        else:
            out["est"] = {
                "cost": sum(float(x["est"]["cost"]) for x in _e),
                "profit": sum(float(x["est"].get("profit") or 0.0)
                              for x in _e)}
        return out

    MS_DOC_KNOPF_MAX = 460
    # emm940: Haken-Box der Fit-Tabelle (Indikator 16 + 2x2 Rahmen = 20);
    # Zeile/Spalte = Box + Item-Polster des QSS (2x5 bzw. 2x6) + Luft.
    MS_HAKEN_BOX = 20
    MS_HAKEN_ZEILE = 32
    MS_HAKEN_SPALTE = 40
    MS_DOC_KNOPF_MIN = 260
    MS_DOC_ZEILE = 36

    def _ms_docs_breite(self):
        """Spalte 0 der Uebersicht = der breiteste Doctrine-Knopf
        (emm938). `resizeColumnsToContents` misst nur den Zellinhalt,
        nicht den Knopf darueber - der Name war abgeschnitten."""
        tbl = getattr(self, "ms_docs", None)
        if tbl is None:
            return
        # emm939: `sizeHint` kennt die FETTE Schrift aus dem Stylesheet
        # noch nicht (auf Windows war der Name weiter abgeschnitten) -
        # der Text wird deshalb selbst in fetter Schrift gemessen.
        from PySide6.QtGui import QFont, QFontMetrics
        _b = 0
        for r in range(tbl.rowCount()):
            _w = tbl.cellWidget(r, 0)
            if _w is not None:
                _f = QFont(_w.font())
                _f.setBold(True)
                _b = max(_b, _w.sizeHint().width(),
                         QFontMetrics(_f).horizontalAdvance(_w.text()) + 64)
            tbl.setRowHeight(r, self.MS_DOC_ZEILE)
        if tbl.rowCount():
            tbl.setColumnWidth(0, max(self.MS_DOC_KNOPF_MIN,
                                      min(self.MS_DOC_KNOPF_MAX, _b + 12)))

    def _ms_docs_ids(self, zeilen):
        """Alle Schiffs-ids der genannten Uebersichts-Zeilen (emm932)."""
        ids = []
        for r in zeilen:
            it = self.ms_docs.item(r, 0)
            if it is None:
                continue
            _l = it.data(Qt.UserRole + 2)
            if not _l and it.data(Qt.UserRole) is not None:
                _l = [int(it.data(Qt.UserRole))]
            ids += [int(x) for x in (_l or []) if int(x) not in ids]
        return ids

    def _ms_docs_zellen(self):
        """Die fertigen Schaetzungen in die Uebersicht eintragen."""
        tbl = getattr(self, "ms_docs", None)
        if tbl is None:
            return
        for r in range(tbl.rowCount()):
            it0 = tbl.item(r, 0)
            if it0 is None:
                continue
            # EINE DOCTRINE = SUMME IHRER SCHIFFE (emm932). Fehlt noch
            # eine Schaetzung, bleibt "…" stehen.
            e = self._ms_est_summe(
                it0.data(Qt.UserRole + 2) or [int(it0.data(Qt.UserRole) or 0)])
            if not e:
                continue
            est = e.get("est")
            # KURZE NOTE, LANGER TOOLTIP (emm860, Nutzer: die Spalte
            # war abgeschnitten "...at market pri"): die Zelle traegt
            # Kuerzel, der volle Satz wohnt im Tooltip.
            kurz, lang = [], []
            if e.get("raus"):
                kurz.append(t("{n}× buy").format(n=e["raus"]))
                lang.append(t("{n} buy item(s) included at market "
                              "price").format(n=e["raus"]))
            if e.get("unpriced"):
                kurz.append(t("{n}× no price").format(
                    n=e["unpriced"]))
                lang.append(t("{n} item(s) without any price not "
                              "included").format(n=e["unpriced"]))
            if e.get("jita_n"):
                kurz.append(t("{n}× Jita").format(n=e["jita_n"]))
                lang.append(t("no price on global hub – Jita sell "
                              "used for {n} item(s)")
                            .format(n=e["jita_n"]))
            if est is None:
                it2 = QTableWidgetItem("—")
                it2.setToolTip(t("Not estimable: an end product has no "
                                 "sell price anywhere (global hub or "
                                 "Jita), or nothing is buildable."))
                tbl.setItem(r, 2, it2)
                tbl.setItem(r, 3, QTableWidgetItem("—"))
            else:
                it2 = QTableWidgetItem(f"{isk_kurz(est['cost'])} ISK")
                it2.setToolTip(t("Exactly: {isk} ISK").format(
                    isk=f"{est['cost']:,.0f}"))
                tbl.setItem(r, 2, it2)
                _pr = float(est.get("profit") or 0.0)
                it3 = QTableWidgetItem(
                    ("+" if _pr >= 0 else "−")
                    + f"{isk_kurz(abs(_pr))} ISK")
                it3.setForeground(QColor(
                    theme.GREEN if _pr >= 0 else theme.RED))
                it3.setToolTip(t("Exactly: {isk} ISK").format(
                    isk=f"{_pr:,.0f}"))
                tbl.setItem(r, 3, it3)
            it4 = QTableWidgetItem(" · ".join(kurz))
            if kurz:
                it4.setForeground(QColor(theme.AMBER))
                it4.setToolTip("\n".join(lang))
            tbl.setItem(r, 4, it4)
        tbl.resizeColumnsToContents()
        self._ms_docs_breite()
