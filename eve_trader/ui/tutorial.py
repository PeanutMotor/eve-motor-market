"""Gefuehrte Tour durch EVE-MoMa (Sitzung 17, Nutzer-Auftrag).

WARUM EIN EIGENES FENSTER UND KEIN MODALER DIALOG: der Nutzer soll waehrend
der Tour WEITERARBEITEN koennen - "damit man nebenbei gleichzeitig das Tool
einrichtet", also Charaktere verlinken und Strukturen anlegen. Ein modaler
Dialog wuerde genau das verhindern.

AUFBAU (mit dem Nutzer abgestimmt):
  * kleines Fenster neben dem Element, um das es geht; das Element bekommt
    einen farbigen Rahmen
  * hoechstens zwei Saetze je Schritt - "keine Textueberflutung"
  * Schrittzaehler ("5 / 15"), Knoepfe Zurueck / Weiter / Abbrechen
  * zwei Zweige: Trading und Industrie; am Ende wird der andere angeboten
  * jederzeit abbrechbar und ueber den Knopf links unten neu startbar
"""

from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton,
                               QVBoxLayout, QWidget)

from ..sprache import t
from . import icons, theme


def schritte(zweig):
    """Die Schrittfolge eines Zweigs.

    Jeder Schritt: (Widget-Name, Ueberschrift, Text, Tab-Schluessel,
    Warte-Bedingung). Solange eine Bedingung nicht erfuellt ist, bleibt
    "Weiter" gesperrt - an dieser Stelle soll der Nutzer wirklich etwas TUN
    (Nutzer, Sitzung 17). Der Widget-Name wird erst beim Anzeigen
    aufgeloest - fehlt das Widget, wird der Schritt trotzdem gezeigt, nur
    ohne Rahmen. So bricht die Tour nie ab, bloss weil ein Reiter noch nicht
    gebaut ist.
    """
    if zweig == "trading":
        return [
            (None, t("Welcome to EVE-MoMa"),
             t("This tour shows you the trading side in a few short steps. "
               "You can keep clicking in the tool while it runs."), None, None),
            ("g_hub", t("Your hub"),
             t("Everything is calculated for this market. Pick the station "
               "you trade at - your own structures can be added later."),
             None, None),
            ("g_scan_btn", t("Market scan"),
             t("This fetches the prices. Without it the deal lists stay "
               "empty."), None, None),
            ("nav:characters", t("Characters"),
             t("Link your characters here - wallet, assets and orders come "
               "from them. Only once a character sits in a player structure "
               "can you add it as a hub with \u201e+ Structure\u201c above."),
             "characters", None),
            ("nav:portfolio", t("Portfolio"),
             t("Shows you when to sell an item and when to hold it a "
               "little longer until the margin is right \u2013 you read "
               "that off the \u201eStatus\u201c column."),
             "portfolio", None),
            ("nav:profit", t("Profits"),
             t("Real profit per item after your sales tax and broker fees."),
             "profit", None),
            ("nav:shopping", t("Shopping list"),
             t("Your buying list for TRADING. Right-click an item in "
               "Daytrade, Swing or Regional to put it in here."),
             "shopping", None),
            ("nav:sell", t("Sell list"),
             t("What is ready to be sold, with the price it should fetch."),
             "sell", None),
            ("nav:orders", t("Order update"),
             t("Shows which of your orders were undercut and what the new "
               "price would be."), "orders", None),
            ("nav:transactions", t("Transactions"),
             t("Every buy and sell EVE reports. This is where profit comes "
               "from."), "transactions", None),
            ("nav:market", t("Price history"),
             t("The price of a single item over time - useful before you "
               "commit to a big buy."), "market", None),
            ("nav:settings", t("Settings"),
             t("Sales tax, broker fees and your structures. Worth a look "
               "once."), "settings", None),
            ("nav:deals", t("Daytrade"),
             t("Buy and sell at the SAME station: you profit from the gap "
               "between buy and sell orders."), "deals", None),
            (("d_mode", "d_preset"), t("Strategy and presets"),
             t("The two dropdowns decide WHAT is searched for. Start with a "
               "preset - it sets all the filters below for you."),
             "deals", None),
            (("deals_btn", "g_hub"), t("Load deals"),
             t("Nothing loads without a hub: the list is built for the hub "
               "selected at the top."), "deals", None),
            ("nav:swing", t("Swing Trade"),
             t("Buy low now, sell later when the price returns to normal. "
               "Needs patience, not a second station."), "swing", None),
            (("h_mode", "h_preset"), t("Strategy and presets"),
             t("Same idea as in Daytrade: the preset sets the filters. Here "
               "they look for prices that dropped below their usual level."),
             "swing", None),
            (("hold_btn", "g_hub"), t("Load deals"),
             t("Same here: without a hub selected at the top nothing is "
               "loaded."), "swing", None),
            ("nav:region", t("Regional Trading"),
             t("Buy in one region, sell in another. You can enter your own "
               "freight cost per m\u00b3 - the profit is calculated after it."),
             "region", None),
            (("rg_src", "rg_tgt"), t("Two hubs instead of one"),
             t("Different from the other two: here you pick where you BUY and "
               "where you SELL. The hub at the top is not used."),
             "region", None),
            (("rg_buyer", "rg_seller"), t("Who buys, who sells"),
             t("The character who buys and the one who sells - their skills "
               "set the fees. The same character twice is fine."),
             "region", None),
            ("rg_preset", t("Strategy and presets"),
             t("The preset sets the filters - for example freight-efficient, "
               "which prefers profit per cubic metre."), "region", None),
            (("rg_go", "rg_src", "rg_tgt", "rg_buyer", "rg_seller"),
             t("Load deals"),
             t("Nothing loads until BOTH hubs are picked. The hub at the top "
               "does not matter here."), "region", None),
            # KEIN BLINKEN AM SCHLUSS (Nutzer, Sitzung 17): es gibt nichts
            # mehr zu klicken - ein blinkender Knopf fordert nur dazu auf.
            (None, t("That is the trading side"),
             t("You can start this tour again any time with the button on the "
               "bottom left."), "portfolio", None),
        ]
    return [
        (None, t("Welcome to EVE-MoMa"),
         t("This tour shows you the industry side. You can set things up as "
           "you go."), None, None),
        ("nav:build", t("The Industry tab"),
         t("Everything about building lives here. The panel on the right is "
           "your starting point."), "build", None),
        (("bau:3", "_struct_add_btn", "_struct_link_btn"),
         t("Structures first"),
         t("Without a structure nothing is calculated correctly. Add yours "
           "now - and do not forget to enter the rigs, they change your "
           "material use."), "build", None),
        (("bau:0", "b_compute_btn"), t("Scanner"),
         t("Finds what is worth building right now, from the market data."),
         "build", None),
        (("bau:1", "bp_refresh_btn", "g_sde_btn"), t("My blueprints"),
         t("The button on this page fetches YOUR blueprints from EVE; the one "
           "at the top loads the recipe data. It also shows what the T2 "
           "version of your T1 blueprint would earn."), "build", None),
        ("_bau_newplan_btn", t("Create a build plan"),
         t("Three ways: right-click a blueprint in the scanner or in My "
           "blueprints, or click 'New build plan' here."), "build", None),
        (("_bau_newplan_btn", "_picker_open_btn"), t("Open a build plan now"),
         t("Click the highlighted button and type an item, for example "
           "\u201eRetribution\u201c - the next steps then explain the tabs on "
           "YOUR plan."), "build", "bauplan_offen"),
        ("bd:tab:" + t("Recipe structure"), t("Recipe structure"),
         t("The full tree from the finished item down to ore. Blue means you "
           "build it, grey means you buy it."), None, None),
        # DER REITER GEHOERT ZUM SCHRITT (Nutzer-Befund 16.09.2026): "gehe ich
        # Back einen Schritt zurueck, haengt es im Invention-Tab fest". Die
        # Karte "Build or buy?" steht neben der REZEPTSTRUKTUR, schaltete den
        # Reiter aber nicht - wer von Schritt 10 (Invention) zurueckging,
        # blieb dort. Ein Schritt muss seinen Zustand selbst herstellen,
        # sonst haengt er davon ab, WOHER man kommt. Dieselbe Schreibweise
        # wie bei "Materials" weiter unten: Reiter zuerst, dann das Element.
        # BEIDE KARTEN BLINKEN (Nutzer 18.09.2026): der Text spricht von
        # "Production depth", geblinkt hat nur "Build or buy?".
        (("bd:tab:" + t("Recipe structure"), "_bd_karte_bauenkaufen",
          "_bd_karte_tiefe"),
         t("Build or buy?"),
         t("Decides what you make yourself. 'Production depth' switches whole "
           "stages at once."), None, None),
        ("bd:tab:" + t("Invention"), t("Invention"),
         t("For T2: how many attempts you need, which decryptor, and how many "
           "datacores that costs."), None, None),
        ("bd:tab:" + t("Blueprints"), t("Blueprints"),
         t("Which of your blueprints the plan uses, with their ME and TE."),
         None, None),
        (("bd:tab:" + t("Materials"), "_bd_mat_copy_btn"), t("Materials"),
         t("What is missing and what is covered. 'Create shopping list' puts "
           "exactly that into your cart."), None, None),
        ("bd:tab:" + t("Run planner"), t("Run planner"),
         t("Splits the jobs across your characters by skills and free job "
           "slots."), None, None),
        (("_bd_save_btn", "_bd_frozen_btn"), t("Save and freeze"),
         t("Freezing keeps prices and quantities of the day you bought. A "
           "frozen plan cannot be changed until you unfreeze it."), None, None),
        (None, t("That is the industry side"),
         t("You can start this tour again any time with the button on the "
           "bottom left."), "portfolio", None),
    ]


class TutorialFenster(QFrame):
    """Das kleine Fenster selbst. Kennt das Hauptfenster, damit es Reiter
    umschalten und Elemente hervorheben kann."""

    def __init__(self, mw, zweig):
        super().__init__(mw)
        self.mw = mw
        self.zweig = zweig
        self.i = 0
        self.schritte = schritte(zweig)
        self._hervor = []
        self._rahmen = []
        # BLINKEN (Nutzer, Sitzung 17: "lass alle Knoepfe die man im Tutorial
        # druecken soll blinken damit man sie erkennt"). Ein Zeitgeber
        # wechselt den Rahmen - kein Dauerleuchten, das man uebersieht.
        self._blink_an = False
        self._blink = QTimer(self)
        self._blink.setInterval(600)
        self._blink.timeout.connect(self._blinken)
        # WARTEN AUF EINE AKTION: solange die Bedingung nicht erfuellt ist,
        # bleibt "Weiter" gesperrt. Alle 400 ms nachsehen - der Nutzer soll
        # nichts extra druecken muessen, damit es weitergeht.
        # LAUFEND NACHFUEHREN: Fenster verschieben, Groesse aendern, Bauplan
        # aufziehen - alles ohne Ereignis, das man sauber abfangen koennte.
        # Ein Zeitgeber ist hier ehrlicher als ein Dutzend Ereignisfilter.
        self._folgen = QTimer(self)
        self._folgen.setInterval(200)
        self._folgen.timeout.connect(self._nachfuehren)
        self._folgen.start()
        self._warte = QTimer(self)
        self._warte.setInterval(400)
        self._warte.timeout.connect(self._warte_pruefen)

        # EIGENES FENSTER, DAS OBEN BLEIBT (Nutzer-Fund Sitzung 17: "der
        # Bauplan rutscht in den Hintergrund" / "wenn man das Haupttool
        # herumzieht, verschiebt sich das Tutorial-Fenster nicht mit").
        # Als KIND des Hauptfensters lag es zwangslaeufig hinter jedem
        # eigenen Fenster (Bauplan) und klebte an festen Koordinaten.
        # NUR UEBER DEM EIGENEN FENSTER, nicht ueber allen Programmen
        # (Nutzer, Sitzung 17: "das Tutorial-Fenster ist jetzt generell ueber
        # allen Programmen ganz vorne"). Ein Qt.Tool-Fenster liegt IMMER ueber
        # seinem Besitzer - und den haengen wir passend um. Ein
        # WindowStaysOnTopHint waere darueber hinaus vor Discord & Co. und
        # damit zu aufdringlich.
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint)
        self.setObjectName("TutorFrame")
        # DEUTLICH DUNKLER ALS DAS WERKZEUG UND GOLDENER RAHMEN (Nutzer,
        # Sitzung 17: "es laesst sich kaum unterscheiden ... die Umrandung in
        # unserer Icon-Goldfarbe faende ich schoener"). #03060B liegt klar
        # unter BG (#080D16); das Gold stammt aus dem Programmsymbol.
        self.setStyleSheet(
            f"#TutorFrame{{background:#03060B; "
            f"border:2px solid {theme.AMBER}; border-radius:8px;}}")
        self.setFixedWidth(380)

        v = QVBoxLayout(self)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)
        self.titel = QLabel("")
        self.titel.setWordWrap(True)
        self.titel.setStyleSheet(
            f"color:{theme.GOLD_HELL}; font-size:19px; font-weight:700; "
            f"background:transparent;")
        v.addWidget(self.titel)
        self.text = QLabel("")
        self.text.setWordWrap(True)
        self.text.setStyleSheet(
            f"color:{theme.TEXT}; font-size:15px; background:transparent;")
        v.addWidget(self.text)

        z = QHBoxLayout()
        self.zaehler = QLabel("")
        self.zaehler.setStyleSheet(
            f"color:{theme.MUTED}; font-size:13px; background:transparent;")
        z.addWidget(self.zaehler)
        z.addStretch()
        self.zurueck_btn = QPushButton(t("Back"))
        self.zurueck_btn.setObjectName("NavGhost")
        self.zurueck_btn.clicked.connect(self.zurueck)
        z.addWidget(self.zurueck_btn)
        self.weiter_btn = QPushButton(t("Next"))
        self.weiter_btn.setObjectName("Primary")
        self.weiter_btn.setIcon(icons.icon("arrow_right"))
        self.weiter_btn.clicked.connect(self.weiter)
        z.addWidget(self.weiter_btn)
        v.addLayout(z)

        _ab = QPushButton(t("Cancel tour"))
        _ab.setObjectName("NavGhost")
        _ab.setIcon(icons.icon("close"))
        _ab.clicked.connect(self.abbrechen)
        v.addWidget(_ab)

        self.zeigen()
        self.show()

    def _widget(self, name):
        """Element zum Schritt. "nav:xyz" meint den Eintrag in der linken
        Leiste - dort soll das Fenster stehen und dort soll es blinken
        (Nutzer, Sitzung 17: "Portfolio befindet sich das Tutorial-Fenster
        nicht neben Portfolio ... lass hier z.B. den Portfolio-Tab blinken").
        Frueher zeigten diese Schritte auf die TABELLE - das Fenster landete
        irgendwo mittig und der Rahmen umfasste die halbe Seite."""
        if not name:
            return None
        if isinstance(name, (list, tuple)):
            return [self._widget(_n) for _n in name]
        if name.startswith("nav:"):
            return (getattr(self.mw, "_nav_buttons", None) or {}).get(name[4:])
        if name.startswith("bau:"):
            # Die vier Knoepfe der rechten Industrie-Leiste liegen in einer
            # LISTE (_bau_page_btns), nicht unter eigenen Namen.
            # UND: der Bauen-Tab hat EIGENE UNTERSEITEN (Scanner, Meine
            # Blaupausen, Meine Bauplaene, Strukturen). Der Reiterwechsel
            # allein bringt einen dort nicht hin - der Nutzer sah einen
            # blinkenden Knopf, aber die falsche Seite dahinter. Also
            # hinschalten, genau wie ein Klick es taete.
            _l = getattr(self.mw, "_bau_page_btns", None) or []
            try:
                _i = int(name[4:])
                self.mw._bau_nav(_i)
                return _l[_i]
            except (ValueError, IndexError, AttributeError):
                return None
        if name.startswith("bd:tab:"):
            # REITER IM BAUPLAN-FENSTER ueber seinen NAMEN, nicht ueber eine
            # Nummer: bei einem T1-Plan fehlt "Invention", dann verschieben
            # sich alle Nummern dahinter (gemessen).
            _d = getattr(self.mw, "_bd_dialog", None)
            try:
                if _d is None or not _d.isVisible():
                    return None
                from PySide6.QtWidgets import QTabWidget as _QTW
                _ziel = name[7:]
                for _tw in _d.findChildren(_QTW):
                    for _i in range(_tw.count()):
                        if _tw.tabText(_i).strip() == _ziel.strip():
                            _tw.setCurrentIndex(_i)   # hinschalten
                            return _tw.tabBar()
                return _d                              # Reiter fehlt: Fenster
            except RuntimeError:
                return None
        if name == "bd:dialog":
            # Die Bauplan-Schritte gehoeren zum EIGENEN Fenster - das Tutorial
            # soll dort stehen, nicht mittig im Hauptfenster.
            _d = getattr(self.mw, "_bd_dialog", None)
            try:
                return _d if (_d is not None and _d.isVisible()) else None
            except RuntimeError:
                return None
        return getattr(self.mw, name, None)

    # ---- Warten und Blinken --------------------------------------------
    def _bedingung_erfuellt(self, was):
        """Ist die Bedingung dieses Schritts erfuellt?"""
        if not was:
            return True
        if was == "bauplan_offen":
            _d = getattr(self.mw, "_bd_dialog", None)
            try:
                return _d is not None and _d.isVisible()
            except RuntimeError:
                return False
        return True

    def _warte_pruefen(self):
        _was = self.schritte[self.i][4]
        if self._bedingung_erfuellt(_was):
            self._warte.stop()
            self.weiter_btn.setEnabled(True)
            self.weiter_btn.setToolTip("")
            # Der frisch geoeffnete Bauplan soll SICHTBAR bleiben.
            if _was == "bauplan_offen":
                # BLINKEN AUS (Nutzer, Sitzung 17): "New build plan" weiter
                # blinken zu lassen laedt zum zweiten Klick ein - und der
                # oeffnet das Auswahlfenster erneut, wodurch alles wieder
                # nach hinten rutscht. Der Schritt ist getan, also Ruhe.
                self._fertig_kein_blinken = True
                self._hervorheben(None)
                _d = getattr(self.mw, "_bd_dialog", None)
                try:
                    if _d is not None and _d.isVisible():
                        _d.raise_()
                except RuntimeError:
                    pass

    def _blinken(self):
        if not self._rahmen:
            return
        self._blink_an = not self._blink_an
        _farbe = theme.AMBER if self._blink_an else "transparent"
        for _r in list(self._rahmen):
            try:
                _r.setStyleSheet(
                    f"background:transparent; border:3px solid {_farbe}; "
                    f"border-radius:6px;")
                _r.raise_()
            except RuntimeError:
                self._blink.stop()

    # ---- Ablauf -------------------------------------------------------
    def zeigen(self):
        name, titel, text, tab, warten = self.schritte[self.i]
        self.titel.setText(titel)
        self.text.setText(text)
        self.zaehler.setText(f"{self.i + 1} / {len(self.schritte)}")
        self.zurueck_btn.setEnabled(self.i > 0)
        self.weiter_btn.setText(
            t("Finish") if self.i == len(self.schritte) - 1 else t("Next"))
        # LETZTER SCHRITT: den Bauplan zumachen (Nutzer, Sitzung 17: "schliesse
        # den Bauplan wieder und lass mich zurueck ins Portfolio kommen").
        # Sonst endet die Tour hinter einem Fenster, das man erst wegklicken
        # muss.
        if self.i == len(self.schritte) - 1:
            _d = getattr(self.mw, "_bd_dialog", None)
            try:
                if _d is not None and _d.isVisible():
                    # ERST UMHAENGEN, DANN SCHLIESSEN (Nutzer-Fund Sitzung 17:
                    # "wenn ich auf Finish klicke, friert alles ein"). Ab
                    # Schritt 9 haengt die Tour AM BAUPLAN - wird der
                    # geschlossen, nimmt er sein Kind mit ins Grab, und der
                    # naechste Klick lief auf ein abgeraeumtes Objekt.
                    if self.parent() is _d:
                        self.setParent(self.mw, self.windowFlags())
                        self.show()
                    _d.close()
            except RuntimeError:
                pass
        if tab:
            try:
                self.mw._go_tab(tab)
            except Exception:
                pass
        # KURSVERLAUF OHNE ITEM IST LEER (Nutzer): dann versteht niemand, was
        # der Reiter zeigt. Also das erste Item aus dem Portfolio eintragen -
        # echte Daten des Nutzers, nichts Erfundenes.
        if tab == "market":
            try:
                self.mw._tutorial_kursverlauf_beispiel()
            except Exception:
                pass
        self._fertig_kein_blinken = False
        self._hervorheben(self._widget(name))
        # "Weiter" sperren, solange die Aktion aussteht.
        if warten and not self._bedingung_erfuellt(warten):
            self.weiter_btn.setEnabled(False)
            self.weiter_btn.setToolTip(
                t("Do the highlighted step first \u2013 then this continues by "
                  "itself."))
            self._warte.start()
        else:
            self._warte.stop()
            self.weiter_btn.setEnabled(True)
            self.weiter_btn.setToolTip("")
        QTimer.singleShot(0, self._fenster_ordnen)

    def weiter(self):
        if self.i >= len(self.schritte) - 1:
            self.abbrechen(fertig=True)
            return
        self.i += 1
        self.zeigen()

    def zurueck(self):
        if self.i > 0:
            self.i -= 1
            self.zeigen()

    def abbrechen(self, fertig=False):
        self._blink.stop()
        self._warte.stop()
        self._folgen.stop()
        self._hervorheben(None)
        try:
            self.mw._tutorial = None
        except Exception:
            pass
        _zweig, _mw = self.zweig, self.mw
        self.hide()
        self.deleteLater()
        if fertig:
            # NICHT AUS DEM KLICK HERAUS: der Knopf gehoert zu diesem Fenster,
            # das gerade abgeraeumt wird - ein modales Fenster von hier aus zu
            # oeffnen liess das Programm haengen (Nutzer-Fund Sitzung 17).
            QTimer.singleShot(0, lambda: _mw._tutorial_anderer_zweig(_zweig))

    # ---- Hervorheben und Platzieren ------------------------------------
    def _hervorheben(self, w):
        """Rahmen UEBER die Elemente legen, nicht in ihren Stil schreiben.

        WARUM KEIN STYLESHEET (Nutzer-Fund Sitzung 17): ein `border:` im Stil
        einer TABELLE vererbt sich auf JEDE ZELLE - die Sell list stand
        komplett gelb umrandet da und die Item-Bilder waren weg.

        `w` darf eine LISTE sein: manche Schritte haengen an MEHREREN
        Bedienelementen (Nutzer: "lass beide Dropdowns blinken", "lass auch
        den Hub mitblinken") - dann blinken alle zugleich.
        """
        self._blink.stop()
        for _r in (self._rahmen or []):
            try:
                _r.hide()
                _r.setParent(None)
                _r.deleteLater()
            except RuntimeError:
                pass
        self._rahmen, self._hervor = [], []
        for _w in ([w] if w is not None and not isinstance(w, (list, tuple))
                   else list(w or [])):
            if _w is None:
                continue
            try:
                # AN DAS FENSTER DES ELEMENTS, nicht immer ans Hauptfenster:
                # ein Element im Bauplan-Fenster braucht seinen Rahmen DORT,
                # sonst laege er hinter dem Bauplan (Nutzer-Fund).
                _r = QWidget(_w.window())
                _r.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                _p = _w.mapTo(_w.window(), QPoint(0, 0))
                _r.setGeometry(_p.x() - 3, _p.y() - 3,
                               _w.width() + 6, _w.height() + 6)
                _r.show()
                _r.raise_()
                self._rahmen.append(_r)
                self._hervor.append(_w)
            except RuntimeError:
                continue
        if self._rahmen:
            self._blink_an = True
            self._blinken()
            self._blink.start()

    def _platzieren(self, vor=False):
        def _sichtbar(w):
            try:
                return w is not None and w.isVisible()
            except RuntimeError:
                return False
        """Neben das erste hervorgehobene Element - in BILDSCHIRM-Koordinaten.

        Frueher wurde INNERHALB des Hauptfensters gerechnet. Sobald ein
        eigenes Fenster (Bauplan) im Spiel war oder der Nutzer das Hauptfenster
        verschob, stimmte nichts mehr (Nutzer-Fund Sitzung 17).
        """
        try:
            self.adjustSize()
            _b, _h = self.width(), self.height()
            # UNTER DAS UNTERSTE Element stellen (Nutzer, Sitzung 17: "das
            # Tutorial verdeckt den Einkaufswagen-Knopf"). Unter dem ERSTEN
            # zu stehen verdeckte alles, was darunter lag und ebenfalls zum
            # Schritt gehoert.
            _sicht = [w for w in (self._hervor or []) if _sichtbar(w)]
            _anker = (max(_sicht, key=lambda w: w.mapToGlobal(
                QPoint(0, w.height())).y()) if _sicht else None)
            if _anker is not None:
                _win = _anker.window()
                _r = _win.frameGeometry()
                _p = _anker.mapToGlobal(QPoint(0, _anker.height() + 8))
                x, y = _p.x(), _p.y()
                # SEITENLEISTE: DANEBEN STATT DARUNTER (Nutzer, 15.09.2026:
                # "Tutorial verdeckt Production Steps, das Tutorialfenster
                # muesste weiter links sein, damit man die rechte Sidebar
                # komplett sehen kann").
                #
                # "Unter den Anker" ist die richtige Regel, solange der Anker
                # in der breiten Mitte sitzt - darunter ist dann Platz. Sitzt
                # er aber in der schmalen Leiste RECHTS, ist unter ihm der
                # Rest genau dieser Leiste, und die Tour deckt zu, worueber
                # sie gerade spricht. Dann gehoert sie links DANEBEN, auf
                # Hoehe des Ankers.
                #
                # DIE GRENZE IST DAS RECHTE DRITTEL des Fensters, nicht die
                # Haelfte: die Leiste ist schmal, die Mitte soll weiter die
                # bewaehrte Platzierung behalten.
                #
                # NUR IM BAUPLAN-FENSTER (Nutzer-Befund 16.09.2026, Schritt
                # 7/15): im HAUPTFENSTER schob dieselbe Regel die Tour nach
                # links - mitten unter das modale "New build plan"-Fenster,
                # das dort aufgeht. Vorher stand sie am rechten Rand und war
                # frei. Die Regel war fuer die schmale Sidebar IM Bauplan
                # gedacht, wo unter dem Anker wirklich nur mehr Sidebar
                # kommt; in der Werkzeugleiste des Haupttools ist darunter
                # Platz. Also gilt sie dort auch nur.
                _a_links = _anker.mapToGlobal(QPoint(0, 0))
                # EIN MODALES FENSTER LIEGT IMMER OBEN (Nutzer-Screenshot
                # 16.09.2026: "jetzt haengt es wieder hinter dem New-build-
                # plan-Fenster"). Bei Schritt 7/15 wandert der Anker in das
                # kleine Such-Fenster (`dlg.exec()`), sobald es offen ist.
                # Egal WO die Tour dann relativ zum Anker steht - steht sie
                # im Bereich dieses Fensters, ist sie verdeckt.
                #
                # DESHALB NICHT AM ANKER AUSRICHTEN, SONDERN AM FENSTER:
                # unter den ganzen Dialog. Dort ist sie frei, und der Blick
                # geht ohnehin von der Eingabe nach unten zur Erklaerung.
                _modal = False
                try:
                    _modal = bool(_win.isModal()) and _win is not self.mw
                except (AttributeError, RuntimeError):
                    _modal = False
                if _modal:
                    # ERST DARUNTER, sonst RECHTS, sonst LINKS: was auf den
                    # Bildschirm passt. Nur "darunter" waere zu wenig - sitzt
                    # der Dialog weit unten, schoebe die Bildschirm-Grenze die
                    # Tour gleich wieder in ihn hinein.
                    _sm = _win.screen()
                    _gm = _sm.availableGeometry() if _sm else _r
                    if _r.bottom() + 8 + _h <= _gm.bottom() - 8:
                        x, y = _r.left(), _r.bottom() + 8
                    elif _r.right() + 12 + _b <= _gm.right() - 8:
                        x, y = _r.right() + 12, _r.top()
                    else:
                        x, y = _r.left() - _b - 12, _r.top()
                elif (_win is not self.mw and _r.width() > 0
                        and _a_links.x() >= _r.left() + (_r.width() * 2) // 3):
                    x, y = _a_links.x() - _b - 12, _a_links.y()
            else:
                _win = (getattr(self.mw, "_bd_dialog", None)
                        if self._schritt_im_bauplan() else None) or self.mw
                try:
                    if not _win.isVisible():
                        _win = self.mw
                except RuntimeError:
                    _win = self.mw
                _r = _win.frameGeometry()
                x, y = _r.center().x() - _b // 2, _r.center().y() - _h // 2
            # Im sichtbaren Bereich HALTEN - notfalls am Bildschirm.
            _scr = self.screen() or _win.screen()
            _sg = _scr.availableGeometry() if _scr else _r
            x = max(_sg.left() + 8, min(x, _sg.right() - _b - 8))
            y = max(_sg.top() + 8, min(y, _sg.bottom() - _h - 8))
            self.move(x, y)
            # NUR BEIM SCHRITTWECHSEL nach vorn holen. Ein raise_() alle
            # 200 ms zog das BESITZERFENSTER mit hoch - der Bauplan rutschte
            # dadurch hinter das Haupttool und liess sich nicht mehr nach
            # vorne holen (Nutzer-Fund Sitzung 17).
            if vor:
                # Erst das Fenster des Ankers, dann die Tour darueber.
                try:
                    if _anker is not None and _anker.window() is not self.mw:
                        _anker.window().raise_()
                except RuntimeError:
                    pass
                self.raise_()
        except Exception:
            pass

    def _zielfenster(self):
        """Das Fenster, zu dem der aktuelle Schritt gehoert.

        AM ELEMENT ABLESEN, nicht am Namen (Nutzer-Fund Sitzung 17: "ab 9/15
        verschwindet der Bauplan wieder"). Schritte wie
        `_bd_karte_bauenkaufen` oder `_bd_save_btn` zeigen auf Elemente IM
        BAUPLAN, heissen aber nicht "bd:" - nach dem Namen zu gehen war eine
        Abkuerzung, die genau hier danebenging.
        """
        # DER SCHRITT, DER DEN BAUPLAN OEFFNET, GEHOERT DANACH DEM BAUPLAN
        # (Nutzer-Screenshot 16.09.2026: die Tour lag hinter dem Bauplan).
        #
        # WARUM DIE WIDGET-SCHLEIFE HIER NICHT REICHT: Schritt 7/15 hebt
        # "New build plan" hervor - einen Knopf im HAUPTFENSTER. Der ist
        # sichtbar, also gewann er unten und die Tour blieb am Haupttool
        # haengen, obwohl der Bauplan laengst davor stand. Auch der
        # Rueckfall weiter unten griff nicht: der sieht nur die Schritte VOR
        # dem aktuellen.
        #
        # SOBALD DIE BEDINGUNG ERFUELLT IST, ist die Aufgabe dieses Schritts
        # erledigt und der Nutzer schaut auf den Bauplan - dorthin gehoert
        # dann auch die Tour. Bewusst NUR fuer diese eine Bedingung: ein
        # Schritt, der auf etwas anderes wartet, behaelt sein Fenster.
        try:
            if self.schritte[self.i][4] == "bauplan_offen":
                _d0 = getattr(self.mw, "_bd_dialog", None)
                if _d0 is not None and _d0.isVisible():
                    return _d0
        except (RuntimeError, AttributeError, IndexError):
            pass
        for _w in (self._hervor or []):
            try:
                if _w is not None and _w.isVisible():
                    return _w.window()
            except RuntimeError:
                continue
        # RUECKFALL: sind wir NACH dem Schritt "Bauplan oeffnen" und ein
        # Bauplan ist offen, gehoert der Schritt dorthin - auch wenn sein
        # Element gerade nicht auffindbar ist. GEMESSEN: ein gemerkter Knopf
        # kann auf ein ALTES Bauplan-Fenster zeigen (unsichtbar); ohne diesen
        # Rueckfall landete die Tour am Haupttool und schob den Bauplan
        # nach hinten (Nutzer-Fund 14/15, Sitzung 17).
        _nach_oeffnen = any(st[4] == "bauplan_offen"
                            for st in self.schritte[:self.i])
        if _nach_oeffnen or self._schritt_im_bauplan():
            _d = getattr(self.mw, "_bd_dialog", None)
            try:
                if _d is not None and _d.isVisible():
                    return _d
            except RuntimeError:
                pass
        return self.mw

    def _fenster_ordnen(self):
        """Beim Schrittwechsel: die Tour an das Fenster HAENGEN, um das es
        geht, dann beide nach vorn.

        WARUM UMHAENGEN (Nutzer-Fund Sitzung 17): ein Werkzeugfenster zieht
        beim Nach-vorn-Holen seinen BESITZER mit. Blieb die Tour am Haupttool
        haengen, drueckte sie den Bauplan bei jedem "Weiter" wieder nach
        hinten - "es heftet sich nicht auf die Bauplan-Ebene".
        """
        _ziel = self._zielfenster()
        # WOHIN ZULETZT GEORDNET WURDE - Grundlage fuer `_nachfuehren`:
        # aendert sich das Zielfenster MITTEN in einem Schritt (der Nutzer
        # oeffnet den Bauplan), muss die Tour mit. Ohne den Merker liefe
        # entweder gar nichts oder ein Dauer-raise_() (Sitzung 17: das zog
        # den Bauplan bei jedem Tick nach hinten).
        self._letztes_ziel = _ziel
        try:
            if self.parent() is not _ziel:
                _flags = self.windowFlags()
                self.setParent(_ziel, _flags)   # nimmt das Fenster mit
                self.show()
        except (RuntimeError, TypeError):
            pass
        try:
            if _ziel is not self.mw:
                _ziel.raise_()
                _ziel.activateWindow()
        except RuntimeError:
            pass
        self._platzieren(vor=True)

    def _schritt_im_bauplan(self):
        _n = self.schritte[self.i][0]
        return isinstance(_n, str) and _n.startswith("bd:")

    def _nachfuehren(self):
        """Rahmen und Fenster den Elementen hinterherziehen (Zeitgeber)."""
        # DAS FENSTER KANN SICH MITTEN IM SCHRITT AENDERN (Nutzer-Befund
        # 16.09.2026): Schritt 7/15 wartet darauf, dass der Nutzer den
        # Bauplan oeffnet. Der geht dann VOR der Tour auf, und sie
        # verschwindet dahinter - bis zum naechsten "Weiter", denn nur der
        # Schrittwechsel hat bisher umgehaengt.
        #
        # NUR BEI ECHTEM WECHSEL, nicht bei jedem Tick: ein Dauer-raise_()
        # zieht das Besitzerfenster mit hoch und drueckte den Bauplan wieder
        # nach hinten (Sitzung 17, derselbe Nutzer, derselbe Schritt).
        try:
            _jetzt = self._zielfenster()
            if _jetzt is not getattr(self, "_letztes_ziel", None):
                self._fenster_ordnen()
                return
        except Exception:
            pass
        try:
            # SPAETER AUFTAUCHENDE ELEMENTE MITNEHMEN: der "Open"-Knopf gibt
            # es erst, wenn das Auswahlfenster offen ist. Ohne das bliebe er
            # stumm, obwohl der Schritt genau ihn meint (Nutzer, Sitzung 17).
            if getattr(self, "_fertig_kein_blinken", False):
                return          # Schritt erledigt - nichts mehr hervorheben
            _soll = [w for w in
                     (self._widget(self.schritte[self.i][0]) or [])
                     if w is not None] if isinstance(
                         self.schritte[self.i][0], (list, tuple)) else None
            if _soll is not None and len(_soll) != len(self._hervor):
                self._hervorheben(_soll)
                self._platzieren()
                return
        except Exception:
            pass
        try:
            for _r, _w in zip(list(self._rahmen), list(self._hervor)):
                try:
                    if not _w.isVisible():
                        _r.hide()
                        continue
                    _p = _w.mapTo(_w.window(), QPoint(0, 0))
                    _r.setGeometry(_p.x() - 3, _p.y() - 3,
                                   _w.width() + 6, _w.height() + 6)
                    _r.show()
                    _r.raise_()
                except RuntimeError:
                    continue
            self._platzieren()
        except Exception:
            pass
