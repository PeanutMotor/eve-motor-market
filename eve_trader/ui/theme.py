"""Qt style sheet - Caldari 'data terminal' look: tiefes Blauschwarz,
Teal-Daten, Amber-Warnungen, helle Schrift.

FARB-RUNDE (Nutzer, Sitzung 8): "mach das ganze Tool etwas dunkler,
coolere futuristischere Farben als Hintergrund - aber nicht komplett
schwarz." Umgesetzt als TIEFENSTAFFELUNG statt Einheitsschwarz: der
Hintergrund geht ins Blauschwarz (#080D16, sichtbarer Blaustich - kein
reines Schwarz), die Flaechen darueber sind kuehler und satter blau.
GEGENGEPRUEFT mit Kontrastrechnung: alle Text-Kombinationen liegen ueber
13:1 (vorher 11-16:1), und Panels/Kanten heben sich BESSER ab als zuvor
(Panel/BG 1.31 statt 1.38 bei dunklerem Grund, Border/Panel 2.02 statt
1.91). Dunkler UND kontrastreicher, nicht dunkler auf Kosten der
Lesbarkeit."""

import os as _os
import sys as _sys


def asset_pfad(*teile):
    """Pfad zu einer Datei in eve_trader/ui/assets - auch in der EXE.

    WARUM NICHT EINFACH `dirname(__file__)`: PyInstaller packt im
    --onefile-Modus nur die PYTHON-MODULE. Datendateien (unsere SVGs, spaeter
    Schriften) kommen ausschliesslich ueber `--add-data` mit und werden beim
    Start in ein temporaeres Verzeichnis ausgepackt, dessen Wurzel in
    `sys._MEIPASS` steht. Ohne diesen Umweg zeigte der Pfad in der
    ausgelieferten Fassung ins Leere - die Haken in den Checkboxen und die
    Hoch/Runter-Pfeile der Zahlenfelder waeren einfach nicht da gewesen,
    und zwar NUR in der EXE, wo man es beim Entwickeln nie sieht. Genau der
    Fehler, den der Nutzer in Sitzung 8 schon einmal gemeldet hatte
    ("ich kann bei allen Eingabefenstern die Pfeile nicht sehen").
    """
    basis = _os.path.dirname(_os.path.abspath(__file__))
    _mei = getattr(_sys, "_MEIPASS", None)
    if _mei:
        basis = _os.path.join(_mei, "eve_trader", "ui")
    # Vorwaertsschraegstriche: der Pfad landet in Qt-Stylesheets, und dort
    # wuerde ein Windows-Backslash als Escape gelesen.
    return _os.path.join(basis, "assets", *teile).replace("\\", "/")


BG = "#080D16"        # Tiefes Blauschwarz - Weltraum, nicht Loch
PANEL = "#16273B"     # Karten/Panels: kuehles Marine
PANEL2 = "#0E1A29"    # Sidebar/Tabellenkopf: dazwischen
PANEL_HELL = "#1D334E"  # laufende Bauplan-Karten: eine Stufe heller als PANEL (emm337)
BORDER = "#345876"    # Kante: klar sichtbar, blau statt grau
TEXT = "#E8F1F8"      # eine Spur kuehler und heller als vorher
MUTED = "#9DB4C6"
CYAN = "#3EE5CE"      # Leuchtakzent, minimal satter fuers dunklere Umfeld
# NUTZER (Sitzung 8): "das Leuchten der Buttons ist etwas zu stark, bitte
# reduzieren." Vorher waren Primary-Knoepfe FLAECHIG cyan - gegen den neuen
# dunklen Grund ein Scheinwerfer (12.3:1). Jetzt eine gedaempfte
# Teal-Fuellung mit cyanfarbener Schrift und Kante: der Knopf bleibt die
# klar erkennbare Hauptaktion (2.1:1 gegen den Grund), blendet aber nicht.
# Beschriftung bleibt mit 5.8:1 gut lesbar.
# SYMBOL-TON (Nutzer, Sitzung 8: "die Symbole sind gut, aber ich haette
# lieber ein futuristisches Grau/Schwarz, kein EVE-Caldari-Leuchtblau").
# Symbole sind Werkzeug, kein Signal - sie sollen die Zeile begleiten, nicht
# um Aufmerksamkeit kaempfen. Kuehles Stahlgrau (leichter Blaustich, damit
# es zur Palette passt, aber ohne Leuchten): 7.5:1 gegen den Grund, also
# klar erkennbar. Zustands-Symbole faerben die Aufrufer weiterhin bewusst
# ein (AMBER Handlung, RED Verlust, GREEN gut) - DA soll Farbe schreien.
# DREI HELLIGKEITSSTUFEN (Nutzer, Sitzung 8: "wenn die Symbole aktiv sind,
# etwas heller, mehr ins Weiss hinein"). Der Sprung von RUHE zu AKTIV ist
# bewusst gross (1.8-fache Leuchtkraft) - sonst merkt man ihn im Augenwinkel
# nicht. Bewusst NICHT reinweiss: das wuerde heller strahlen als der
# Fliesstext und die Rangfolge umdrehen.
# GOLDTON STATT GRAU (Nutzer, Sitzung 9: "ich finde alle Symbole doch
# etwas duester, wenn sie einfach nur grau sind"). Gewaehlt wurde ein
# GEDAEMPFTES Gold - es nimmt die Logofarbe auf, ist aber bewusst matter
# und weniger gesaettigt als das Signal-AMBER (#F2A23C). Diese Distanz
# ist Absicht: Amber bedeutet im Tool "eingefroren / Warnung / fehlt" -
# waeren die ~190 Symbole ebenso satt, verloere die Warnfarbe ihre
# Signalwirkung. Der DIM- und der ACTIVE-Ton folgen demselben Farbton
# (dunkler bzw. heller), damit die Rangfolge erhalten bleibt.
ICON_DIM = "#8A7550"         # inaktiv/nebensaechlich
ICON = "#C9A06A"             # Ruhe: Standard-Ton aller Symbole
ICON_ACTIVE = "#E4C79A"      # aktiv/gehovert/ausgewaehlt
CYAN_FILL = "#15514A"        # ruhige Akzentflaeche (Primary-Knopf)
# NUTZER (Sitzung 8): "Aktualisierungsbutton hat Kontrastprobleme."
# Die Beschriftung war CYAN auf CYAN_FILL - gleiche Farbfamilie, nur
# 5.8:1, und die geringe FARB-Distanz liess es matschig wirken (der reine
# Helligkeitswert verschweigt das). Jetzt ein stark aufgehelltes Cyan:
# 8.3:1 und deutlich abgesetzt, ohne den Akzentcharakter zu verlieren.
CYAN_ON_FILL = "#DFFAF4"
CYAN_FILL_HOVER = "#1B6A60"  # beim Hovern etwas heller
CYAN_FILL_PRESS = "#0F3C37"  # beim Druecken dunkler
# FORTSCHRITTSBALKEN DER PLAN-KARTEN (Nutzer 26.09.2026: "die
# Fortschrittsbalken kann man kaum lesen in der Farbkombination von der
# Schrift drinnen"): der Balken war leuchtendes CYAN mit MUTED-Schrift
# darueber. Jetzt dieselbe ruhige Flaeche wie der Primary-Knopf und
# dieselbe helle Beschriftung (CYAN_ON_FILL, >= 7:1 - aa173) - fertig
# in einem gleich gedaempften Gruen.
GREEN_FILL = "#1E5A3A"
GREEN_ON_FILL = "#E3F8EA"
AMBER = "#F2A23C"
# NUTZER (Sitzung 8): "standardmaessig schon einen gelben Rahmen darum
# machen, bevor man Mouseover macht." Gedaempftes Amber fuer den RUHENDEN
# Reiter - erkennbar als zur Navigation gehoerig, laesst aber Luft nach
# oben: Hover und aktiver Reiter bekommen das volle AMBER. Drei Stufen
# also, wie bei den Symbolen. (2.7:1 gegen die Reiterflaeche, damit sogar
# etwas praesenter als die alte blaugraue Kante mit 2.3:1.)
AMBER_DIM = "#7A5626"
# LOGO-PALETTE (Wabe mit Innenkante, Sitzung 8). Gehoert ins Theme, nicht
# ins Symbol-Modul - die Waechter aa170/aa175 haben genau das eingefordert.
GOLD_HELL = "#FFD98A"     # oberer Verlaufspunkt
GOLD = "#F2A23C"          # Mitte (= AMBER, bewusst identisch)
GOLD_TIEF = "#B87326"     # unterer Verlaufspunkt + Innenkante
LOGO_KERN = "#0B0F17"     # Wabenfuellung, dunkler als BG fuer Kontrast
RED = "#E5544B"
# PLAN-FARBEN (Nutzer 23.09.2026: "Schau mal die Farben, Blau sieht man
# kaum, waehle anderes Blau / Fuege weitere 4 Farben hinzu / Benenne alle 8
# Farben anders, waehle keine EVE-Fraktionen als Namen [...] wir muessen gar
# keine Namen geben, die Farbe sagt schon genug aus / Nimm kein Rot oder Full
# Green [...] Das Rot sieht aus wie Verlustzahlen. nimm ein anderes Rot").
#
# DIE SCHLUESSEL SIND ABSICHTLICH NUMMERN. Sie werden im Plan GESPEICHERT.
# Ein Name ("caldari") waere eine Aussage ueber den Plan, die der Nutzer nie
# gemacht hat - und beim naechsten Umfaerben eine Luege. Eine Nummer ist nur
# ein Platz in dieser Tabelle; wer den Farbwert aendert, aendert die Farbe
# aller Plaene auf diesem Platz und nichts sonst.
#
# ZWEI FARBEN SIND HIER VERBOTEN, weil sie im ganzen Werkzeug etwas anderes
# bedeuten: RED (#E5544B) = Verlust und GREEN (#4FD17A) = Gewinn. Eine Karte
# in Signalrot laese sich wie eine Verlustmeldung, ohne eine zu sein. Darum
# steht auf Platz 6 ein Rose - das "andere Rot", blasser und kuehler als
# RED - und Gruen fehlt ganz; Petrol (Platz 2) ist der naechste Ton, der
# nicht nach "Gewinn" aussieht. Geprueft wird das in aa402: jeder Wert haelt
# im RGB-Raum Abstand zu RED, GREEN und GREEN_BRIGHT, und die acht halten
# Abstand untereinander - sonst waeren zwei Plaene nicht unterscheidbar.
#
# HELLIGKEIT: die Flaeche liegt mit 18 % auf PANEL (#16273B). Unter etwa 60 %
# Helligkeit verschwindet ein Ton darin - daran ist das alte Blau (#3A6EA5)
# gescheitert ("Blau sieht man kaum"). Alle acht Werte liegen darueber.
PLAN_FARBEN = {
    "f1": "#4C90F0",   # Blau - hell genug, um auf PANEL zu stehen
    "f2": "#2FB2D4",   # Petrol - der Platz, an dem sonst Gruen staende
    "f3": "#8C7BF0",   # Indigo
    "f4": "#B36BE0",   # Violett
    "f5": "#D95FC4",   # Magenta
    "f6": "#DE7E9B",   # Rose - das "andere Rot", kein Verlustrot
    "f7": "#D9B38C",   # Sand
    "f8": "#93A8C4",   # Stahl
}
# ALTBESTAND: die vier Fraktionsschluessel der ersten Fassung stecken schon in
# gespeicherten Plaenen. Sie werden beim Lesen auf den naechstliegenden neuen
# Platz gebogen, damit keine Karte ihre Farbe verliert (gelesen wird ueber
# MainWindow._plan_farb_norm - EINE Stelle).
PLAN_FARBEN_ALT = {
    "caldari": "f1",
    "gallente": "f2",
    "amarr": "f7",
    "minmatar": "f6",
}
GREEN = "#4FD17A"
VIOLET = "#9D7FE8"    # Reaktionen-Phase 1 (Intermediate) im Runplaner
VIOLET_2 = "#C79BE8"  # Reaktionen-Phase 2 (Composite) - HELLER, damit sich
                      # die beiden Reaktions-Stufen unterscheiden
                      # (Nutzer, Sitzung 12: "aktuell ist es dasselbe wie
                      # 3. Reaktionen - Composite")
CYAN_RUN = "#4FC3E8"  # "wird gerade gebaut" (ESI-Job laeuft). BEWUSST NICHT
                      # violett: violett ist die Farbe der Reaktions-STUFE,
                      # ein laufender Job ist ein ZUSTAND - zwei
                      # verschiedene Aussagen brauchen zwei Farben.
GREEN_BRIGHT = "#7CE8A4"   # Zusage-Gruen ("kann gebaut werden") - bewusst
                           # heller als GREEN (Handlung, nicht Status)

# TYPOGRAFIE-SKALA (Nutzer, Sitzung 8: "jeder Tab dieselbe Schrift, Groessen
# und Farben einheitlich"). GENAU VIER Groessen + Display (>=25 fuer grosse
# Zahlen/Symbole). Die aa-Suite erzwingt die Skala - neue Zwischengroessen
# fallen rot.
FS_SMALL = "11px"     # dichte Nebeninfo (Tabellen-Details, Balkentext)
FS_BASE = "13px"      # Grundschrift (globales QSS unten)
FS_H2 = "15px"        # Ueberschriften, Tabs, KPI-Titel
FS_KPI = "19px"       # grosse Kennzahlen (Karten)
MONO = "Consolas, monospace"   # NUR fuer Zahlen/Kennwerte (Terminal-Optik)

# INDUSTRIE-SCHRIFT (Nutzer, Sitzung 8: "haettest du einen Industry-Font im
# Petto?"). EVEs eigene UI-Schrift (Shentox) ist lizenziert und darf nicht
# mitgeliefert werden. Gewaehlt wurde eine Kette, die OHNE Download
# funktioniert:
#   1. Bahnschrift - liegt auf JEDEM Windows 10/11 (Microsofts DIN-Variante:
#      technisch, schmal, gerade Schnitte - genau die Industrie-Optik).
#   2. dann die frueheren Schriften als Rueckfall, damit nichts bricht.
# Wer eine eigene Schrift will (z.B. Rajdhani, Chakra Petch, Saira), legt
# die .ttf/.otf einfach in eve_trader/ui/assets/fonts/ - load_custom_fonts()
# registriert beim Start ALLES, was dort liegt, und FONT_CUSTOM zieht die
# erste gefundene Familie nach vorn. Kein Code-Eingriff noetig.
FONT_STACK = ['"Bahnschrift"', '"Segoe UI"', '"Inter"', "sans-serif"]
FONT = ", ".join(FONT_STACK)



def load_custom_fonts():
    """Registriert alle Schriften aus assets/fonts und stellt die erste
    gefundene Familie an den Anfang der Kette. Ohne eigene Dateien bleibt
    es bei Bahnschrift. Fehler sind bewusst folgenlos - eine kaputte
    Schriftdatei darf den Programmstart nicht verhindern."""
    global FONT, QSS
    ordner = asset_pfad("fonts")
    if not _os.path.isdir(ordner):
        return []
    from PySide6.QtGui import QFontDatabase
    familien = []
    for name in sorted(_os.listdir(ordner)):
        if not name.lower().endswith((".ttf", ".otf")):
            continue
        try:
            kennung = QFontDatabase.addApplicationFont(
                _os.path.join(ordner, name))
            if kennung >= 0:
                familien += QFontDatabase.applicationFontFamilies(kennung)
        except Exception:
            continue
    if familien:
        alt = FONT
        FONT = ", ".join([f'"{familien[0]}"'] + FONT_STACK)
        QSS = QSS.replace(alt, FONT)
    return familien

# FARB-PALETTEN (einzige erlaubte Hex-Quellen ausserhalb der Konstanten):
TIER_PALETTE = [AMBER, CYAN, "#8FB8F0", "#C4A5E8", "#E0A0C8",
                "#9AA0B0", MUTED]                      # Fertigungs-Tiefen
CHART_PALETTE = [CYAN, AMBER, GREEN, "#7AA2F2", "#E56AB3",
                 "#C8D14F", "#8A7AF2", "#4FD1C5", "#F27A7A", "#9AD14F"]
BLUE = "#5B9DE8"      # Komponenten-Phase (Runplaner)

_CHECK_ICON = asset_pfad("check.svg")
# NUTZER-FUND (Sitzung 8): "ich kann bei allen Eingabefenstern die Pfeile
# fuer hoch/runter nicht sehen." URSACHE: sobald man QSpinBox::up-button im
# Stylesheet anfasst, zeichnet Qt die eingebauten Pfeile NICHT mehr - der
# Knopf blieb eine leere Flaeche. Also eigene Pfeil-Grafiken im
# Symbol-Stahlton (dieselbe Formsprache wie icons.py).
_SPIN_UP = asset_pfad("spin_up.svg")
_SPIN_DOWN = asset_pfad("spin_down.svg")

# de_scan2: aus  (das Stylesheet ist CSS mit deutschen BEGRUENDUNGS-Kommentaren - nichts davon ist Anzeigetext)
QSS = f"""
* {{
    font-family: {FONT};
    font-size: 13px;
    color: {TEXT};
}}
QWidget {{ background: transparent; }}
QMainWindow, QDialog {{ background: {BG}; }}

QTabWidget::pane {{ border: 1px solid {BORDER}; top: -1px; background: {BG}; }}
QTabBar::tab {{
    background: {PANEL2};
    color: {MUTED};
    padding: 10px 20px;
    font-size: 15px;
    font-weight: 600;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    margin-right: 3px;
}}
QTabBar::tab:selected {{
    color: {CYAN};
    background: {PANEL};
    font-weight: 800;
    border-top: 3px solid {CYAN};
    padding-top: 8px;
}}
QTabBar::tab:hover {{ color: {TEXT}; }}

QLabel#H1 {{ color: {CYAN}; font-size: 15px; font-family: {MONO}; }}
QLabel#Muted {{ color: {MUTED}; }}
QLabel#KpiValue {{ font-family: {MONO}; font-size: 15px; color: {TEXT}; }}

QFrame#Card {{
    background: {PANEL};
    border: 1.5px solid {BORDER};
    border-radius: 8px;
}}

QCheckBox {{
    spacing: 8px;
    color: {TEXT};
}}
/* KAESTCHEN IN BAEUMEN, TABELLEN UND LISTEN GENAUSO (Sitzung 17, Nutzer-
   Screenshot vom 2. PC: grellweisse Haken-Boxen im Rezept-Baum). Vorher war
   nur QCheckBox gestaltet - die Kaestchen der Item-Ansichten zeichnete
   Windows selbst, und das je nach System-Farbschema hell oder dunkel. */
QCheckBox::indicator, QTreeView::indicator, QTableView::indicator,
QListView::indicator {{
    width: 16px;
    height: 16px;
    border: 1.5px solid {MUTED};
    border-radius: 3px;
    background: {PANEL2};
}}
QCheckBox::indicator:hover, QTreeView::indicator:hover,
QTableView::indicator:hover, QListView::indicator:hover {{
    border-color: {CYAN};
}}
QCheckBox::indicator:checked, QTreeView::indicator:checked,
QTableView::indicator:checked, QListView::indicator:checked {{
    background: {PANEL2};
    border: 1.5px solid {GREEN};
    image: url({_CHECK_ICON});
}}
QCheckBox::indicator:checked:hover, QTreeView::indicator:checked:hover,
QTableView::indicator:checked:hover, QListView::indicator:checked:hover {{
    border-color: {CYAN};
}}
QTreeView::indicator:indeterminate, QTableView::indicator:indeterminate,
QListView::indicator:indeterminate {{
    background: {PANEL2};
    border: 1.5px solid {AMBER};
}}
QCheckBox::indicator:disabled, QTreeView::indicator:disabled,
QTableView::indicator:disabled, QListView::indicator:disabled {{
    border-color: {BORDER};
    background: {PANEL};
}}

QPushButton {{
    background: {PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    padding: 5px 12px;
    color: {TEXT};
}}
QPushButton:hover {{ border-color: {CYAN}; color: {CYAN}; padding: 3px 12px 7px 12px; }}
QPushButton:pressed {{ background: {PANEL2}; padding: 7px 12px 3px 12px; }}
QPushButton#Primary {{ background: {CYAN_FILL}; color: {CYAN_ON_FILL}; border: 1px solid {CYAN}; font-weight: 600; }}
QPushButton#Primary:hover {{ background: {CYAN_FILL_HOVER}; border: 1px solid {CYAN}; padding: 3px 12px 7px 12px; }}
QPushButton#Primary:pressed {{ background: {CYAN_FILL_PRESS}; border: 1px solid {CYAN}; padding: 7px 12px 3px 12px; }}
QPushButton#Danger:hover {{ border-color: {RED}; color: {RED}; padding: 3px 12px 7px 12px; }}
QPushButton#Danger:pressed {{ background: {PANEL2}; padding: 7px 12px 3px 12px; }}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
    background: {PANEL2};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 3px 6px;
    color: {TEXT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {CYAN};
}}
QComboBox::drop-down {{ border: none; }}
QSpinBox::up-button, QDoubleSpinBox::up-button,
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    width: 18px;
    border: none;
    border-left: 1px solid {BORDER};
    background: {PANEL};
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background: {BORDER};
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url({_SPIN_UP}); width: 11px; height: 11px;
}}
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url({_SPIN_DOWN}); width: 11px; height: 11px;
}}
QComboBox QAbstractItemView {{
    background: {PANEL2}; border: 1px solid {BORDER};
    selection-background-color: {CYAN}; selection-color: {BG};
}}

QTableWidget {{
    background: {PANEL};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    alternate-background-color: {PANEL2};
    /* Nutzer: "eine etwas weniger roboterische Schriftart". Vorher stand
       hier Consolas/monospace - das las sich wie ein Terminal. Zahlenspalten
       sind ohnehin rechtsbuendig, die Kante stimmt also weiterhin. */
    font-family: {FONT};
    color: {TEXT};
}}
QHeaderView::section {{
    background: {PANEL2};
    color: {CYAN};
    border: none;
    border-bottom: 2px solid rgba(70,224,200,0.4);
    padding: 7px 8px;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}
QTableWidget::item {{ padding: 5px 6px; border-bottom: 1px solid {PANEL2}; }}
QTableWidget::item:selected {{ background: #1E3A40; color: {CYAN}; }}
QTreeWidget {{ background: {PANEL}; border: 1px solid {BORDER}; color: {TEXT};
    alternate-background-color: {PANEL2};
    font-family: {FONT}; }}
QTreeWidget::item {{ padding: 2px; }}
QTreeWidget::item:selected {{ background: #1E3A40; color: {CYAN}; }}

QStatusBar {{ background: {PANEL2}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
QScrollBar:vertical {{ background: {BG}; width: 10px; }}
QScrollBar::handle:vertical {{ background: {BORDER}; border-radius: 5px; }}
QScrollBar::handle:vertical:hover {{ background: {CYAN}; }}
QToolTip {{
    background: {PANEL2};
    color: {TEXT};
    border: 1px solid {CYAN};
    border-radius: 6px;
    padding: 7px 10px;
    font-family: {FONT};
    font-size: 13px;
}}

QMenu {{
    background: {PANEL};
    border: 1px solid {BORDER};
    padding: 4px;
}}
QMenu::item {{
    padding: 7px 18px;
    border-radius: 4px;
    color: {TEXT};
}}
QMenu::item:selected {{
    background: {CYAN};
    color: {BG};
}}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 6px; }}

/* ---- Haupt-Navigation: Sidebar (links, freie Tools) ---- */
QFrame#Sidebar {{
    background: {PANEL2};
    border-right: 1px solid {BORDER};
}}
QLabel#Brand {{
    /* Mit dem goldenen MM-Wappen daneben wirkte das Cyan wie ein zweites,
       konkurrierendes Signal (Sitzung 8). Der Schriftzug nimmt jetzt die
       Logo-Farbe auf - Wappen und Wortmarke lesen sich als EIN Zeichen.
       Etwas kleiner, damit das Wappen die Fuehrung behaelt. */
    color: {AMBER};
    font-size: 19px;
    font-weight: 800;
    letter-spacing: 1px;
    padding: 8px 4px 16px 4px;
}}
QLabel#NavSection {{
    color: {MUTED};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 2px;
    padding: 12px 6px 6px 6px;
}}
QPushButton#NavItem {{
    text-align: left;
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0px;
    padding: 10px 10px 10px 9px;
    margin: 1px 0px;
    color: {MUTED};
    font-size: 15px;
    font-weight: 500;
}}
QPushButton#NavItem:hover {{
    background: rgba(70,224,200,0.08);
    color: {TEXT};
}}
QPushButton#NavItem:checked {{
    background: rgba(70,224,200,0.14);
    color: {CYAN};
    font-weight: 700;
    border-left: 3px solid {CYAN};
}}
QPushButton#NavGhost {{
    text-align: left;
    background: transparent;
    border: 1px dashed {BORDER};
    border-radius: 7px;
    padding: 9px 10px;
    color: {MUTED};
    font-size: 12px;
    font-weight: 600;
}}
QPushButton#NavGhost:hover {{ border-color: {AMBER}; color: {AMBER}; }}

/* ---- Haupt-Navigation: TopBar (Daytrade/Swing/Regional/Bauen) ---- */
QFrame#TopBar {{
    background: {PANEL};
    border-bottom: 1px solid {BORDER};
}}
QPushButton#NavPaid {{
    background: transparent;
    border: 2px solid transparent;
    border-radius: 10px;
    padding: 12px 22px;
    margin: 7px 4px;
    color: {MUTED};
    font-size: 15px;
    font-weight: 700;
}}
QPushButton#NavPaid:hover {{
    background: rgba(242,162,60,0.14);
    border-color: rgba(242,162,60,0.5);
    color: {TEXT};
}}
QPushButton#NavPaid:checked {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #F7B75C, stop:1 #E08A22);
    border: 2px solid #FBCB82;
    color: {BG};
    font-weight: 800;
}}
QPushButton#CreditsTag {{
    background: rgba(242,162,60,0.12);
    border: 1px solid rgba(242,162,60,0.45);
    border-radius: 14px;
    padding: 7px 16px;
    color: {AMBER};
    font-weight: 700;
    font-size: 13px;
}}
QPushButton#CreditsTag:hover {{ background: rgba(242,162,60,0.22); }}

/* ---- Ganz oben: die Toolbar (Alles aktualisieren / Hub / Markt-Scan / ...) ---- */
QToolBar {{
    background: {PANEL2};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 8px 10px;
    spacing: 8px;
}}
QToolBar QPushButton {{
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 600;
}}
QToolBar QComboBox {{
    padding: 6px 10px;
    min-height: 18px;
    font-size: 13px;
}}
QToolBar QLabel {{
    font-size: 13px;
}}
"""
# de_scan2: an



# NACH dem QSS: aa311 schneidet die Knopf-Regel des QSS von "QPushButton {{"
# bis zum ersten "QPushButton:hover" aus - davor stuende diese hier.
def amber_rahmen_knopf():
    """EIN Stil fuer die amber umrandeten Aktions-Knoepfe (Nutzer 26.09.2026:
    "Buy Missing Blueprints und Best Decryptor optisch an Create Shopping
    List anpassen - Hintergrund normale Tool-Farbe, nur Umrandung und Text
    Amber"; "Create shopping list etwas groesser" - 15 px, naechste Stufe der
    Skala FS_*, 14 px ist verboten, aa170). Kein eigener
    Hintergrund in Ruhe - der Knopf behaelt die Flaeche des Themas; Hover
    toent leicht amber. Gesperrt: gedaempftes Amber, damit ein gesperrter
    Knopf nicht wie ein aktiver aussieht. Rahmen in allen Zustaenden gleich
    dick, sonst springt das Layout."""
    return (f"QPushButton{{border:1.5px solid {AMBER}; border-radius:6px; "
            f"padding:7px 16px; color:{AMBER}; font-weight:700; "
            f"font-size:15px;}}"
            f"QPushButton:hover{{background:rgba(242,162,60,0.16);}}"
            f"QPushButton:disabled{{border:1.5px solid {AMBER_DIM}; "
            f"color:{AMBER_DIM};}}")


def kopier_knopf_stil():
    """Kleiner Kopier-Knopf wie die Run-Knoepfe im Runplaner (emm329): duenner
    AMBER_DIM-Rahmen, Amber-Text, Hover heller. Fuer "Copy T1 Blueprint" und
    "Copy Decryptor" in der Invention-Karte - beide gleich gross (Nutzer
    02.10.2026). Gesperrt: gedaempft, damit man ihn nicht fuer aktiv haelt."""
    return (f"QPushButton{{background:{PANEL2}; border:1px solid {AMBER_DIM}; "
            f"color:{AMBER}; border-radius:5px; padding:0px 8px;}}"
            f"QPushButton:hover{{border-color:{AMBER}; background:{PANEL};}}"
            f"QPushButton:disabled{{border:1px solid {BORDER}; color:{MUTED};}}")

