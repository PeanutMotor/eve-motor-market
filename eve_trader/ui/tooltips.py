"""Tooltips ueberall gleich: Schrift, Farbe, Breite.

NUTZER-AUFTRAG (Sitzung 20, Screenshot des Tooltips ueber "Total assets"):
"Schriftgroesse anpassen, die ist gigantisch. Farbe anpassen, alle weiss.
Breite anpassen, alle gleich breit."

WARUM DER TOOLTIP DORT RIESIG WAR: die Kennzahl traegt ein eigenes Stylesheet
mit `font-size:26px`, und Qt vererbt so ein Widget-Stylesheet an den Tooltip
dieses Widgets. Die globale `QToolTip{...}`-Regel greift dann nicht mehr.
Jedes Widget einzeln zu bereinigen hiesse ueber 400 Stellen anzufassen - und
jedes neue Stylesheet irgendwo brächte die Falle zurueck.

DESHALB EINE STELLE: `setToolTip` wird anwendungsweit umgeleitet. Jeder Text
wird als Rich-Text mit fester Schrift, fester Farbe und fester Breite gesetzt.
Was das Widget an Schrift vererbt, wird damit ueberstimmt. Plain-Text bleibt
lesbar (HTML-Zeichen werden maskiert, Zeilenumbrueche bleiben).

BREITE: Qt bricht nur Rich-Text um, und auch dann ohne Obergrenze. Die
Tabelle mit fester Breite ist der verlaessliche Weg, sie zu setzen.
"""
from html import escape as _escape

from PySide6.QtWidgets import QWidget

from . import theme

# Etwa 5 cm bei ueblicher Bildschirmdichte (Nutzer: "ca. 5 cm, nicht mehr").
BREITE_PX = 320
SCHRIFT_PX = 13         # aus der Skala des Themes (11/13/15/19)


def _einheitlich(text):
    """Text in die gemeinsame Form bringen. Leer bleibt leer (= Tooltip aus)."""
    if not text:
        return text
    if text.lstrip().startswith("<") and "</" in text:
        inhalt = text                     # schon Rich-Text - nur einrahmen
    else:
        inhalt = _escape(text).replace("\n", "<br>")
    return (f"<qt><table width='{BREITE_PX}'><tr><td style=\""
            f"font-family:{theme.FONT}; font-size:{SCHRIFT_PX}px; "
            f"font-weight:normal; color:{theme.TEXT};\">"
            f"{inhalt}</td></tr></table></qt>")


# DIE ENTSCHEIDENDE REGEL. Qt reicht das Stylesheet eines Widgets an DESSEN
# Tooltip weiter, und ein Widget-Stylesheet schlaegt jedes Inline-CSS im
# Tooltip-Text. Der erste Anlauf setzte nur die Schrift im HTML - der Umbruch
# griff, die Groesse nicht (Nutzer: "Tooltip ist immernoch riesig").
# Deshalb wird JEDEM Widget-Stylesheet diese Regel angehaengt. Dort gewinnt
# sie, weil sie aus derselben Quelle kommt wie die 26px daneben.
_QSS_REGEL = (
    "\nQToolTip{{ font-family:{font}; font-size:{px}px; font-weight:normal; "
    "color:{fg}; background:{bg}; border:1px solid {rand}; "
    "border-radius:{rad}; padding:7px 10px; }}")


def _regel():
    return _QSS_REGEL.format(font=theme.FONT, px=SCHRIFT_PX, fg=theme.TEXT,
                             bg=theme.PANEL2, rand=theme.CYAN,
                             rad=theme.RAD)          # emm885


_original_tip = QWidget.setToolTip
_original_qss = QWidget.setStyleSheet


def _mit_regel(sheet):
    """Stylesheet um die Tooltip-Regel ergaenzen - leere bleiben leer.

    ZWEI FORMEN VON STYLESHEET, und nur eine vertraegt eine zweite Regel:
    viele Stellen setzen eine nackte Eigenschaftsliste ("color:X;
    font-weight:800;") ohne Selektor. Haengt man dort eine Regel mit Selektor
    an, kann Qt die ganze Datei nicht mehr lesen - gemessen am echten Fenster:
    "Could not parse stylesheet of object KpiLabel". Die nackte Liste wird
    deshalb erst in `*{...}` eingefasst.
    """
    if not sheet or "QToolTip" in sheet:
        return sheet
    if "{" not in sheet:
        sheet = "*{" + sheet + "}"
    return sheet + _regel()


def _setToolTip(self, text):
    _original_tip(self, _einheitlich(text))
    # Traegt das Widget schon ein Stylesheet, muss die Regel JETZT hinein -
    # sonst erbt der Tooltip dessen Schriftgroesse.
    _sheet = self.styleSheet()
    if _sheet and "QToolTip" not in _sheet:
        _original_qss(self, _mit_regel(_sheet))


def _setStyleSheet(self, sheet):
    # Und andersherum: wird das Stylesheet SPAETER gesetzt (die Render-Laeufe
    # tun das laufend), darf es die Regel nicht wieder wegnehmen.
    _original_qss(self, _mit_regel(sheet))


def aktivieren():
    """Einmal beim Start rufen, VOR dem Bau des Hauptfensters."""
    if getattr(QWidget, "_tooltips_einheitlich", False):
        return
    QWidget.setToolTip = _setToolTip
    QWidget.setStyleSheet = _setStyleSheet
    QWidget._tooltips_einheitlich = True
