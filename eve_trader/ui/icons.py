"""Eigenes Symbol-Set (Strichgrafik, 24x24-Raster).

WARUM SELBST GEZEICHNET (Nutzer-Wunsch, Sitzung 8: "ich moechte fuer jedes
Symbol ein eigenes kleines Bild - vielleicht stellt die SDE welche zur
Verfuegung"):

* Die SDE stellt KEINE Symbole bereit. Sie ist reine Datenbank (Rezepte,
  Typen, Gruppen) - der Download von Fuzzwork enthaelt kein einziges Bild.
* Der EVE-Bildserver (images.evetech.net) liefert nur ITEM-Icons,
  Charakter-Portraets und Corp-/Allianz-Logos. Fuer Gegenstaende nutzen wir
  ihn bereits; fuer Oberflaechen-Aktionen (kopieren, suchen, aktualisieren)
  gibt es dort nichts.
* CCPs eigene UI-Symbole (die Neocom-Leiste im Spiel) stecken in den
  Client-Ressourcen und sind CCPs Eigentum - die duerfen wir nicht
  mitliefern.

Also: eigene Strichgrafik. STANDARD-TON ist theme.ICON (kuehles Stahlgrau),
NICHT Cyan (Nutzer, Sitzung 8: "futuristisches Grau/Schwarz, kein
EVE-Caldari-Leuchtblau"): Symbole BEGLEITEN die Zeile, sie sind kein
Signal. Farbe bekommen sie nur, wo sie etwas AUSSAGT - AMBER "Handlung
noetig", RED "Verlust/Warnung", GREEN "alles gut". So bleibt das Auge frei
fuer die wenigen Stellen, die wirklich rufen.

Weitere Vorteile, die keine der Alternativen bietet -
sie nimmt die Theme-FARBE an (gleiche Symbole in Cyan, Amber, Rot je nach
Zustand), skaliert scharf auf jede Groesse, braucht kein Netz und keine
Dateien.

Verwendung:
    from eve_trader.ui import icons
    knopf.setIcon(icons.icon("refresh"))              # Standardfarbe
    knopf.setIcon(icons.icon("warning", theme.AMBER)) # eingefaerbt
"""

import os as _os_ic

from PySide6.QtCore import Qt, QByteArray, QSize
from PySide6.QtGui import QIcon, QPixmap, QPainter
from PySide6.QtSvg import QSvgRenderer

from . import theme

# Strichgrafik auf 24x24. Bewusst EINE Formsprache: 2px Strich, runde
# Enden, keine Flaechen - dadurch wirken alle Symbole wie aus einem Guss
# und bleiben bei 16px noch lesbar.
_PFADE = {
    # --- Grundaktionen ---------------------------------------------------
    "check": "M5 12.5 L10 17.5 L19 6.5",
    "close": "M6 6 L18 18 M18 6 L6 18",
    "plus": "M12 5 V19 M5 12 H19",
    "minus": "M5 12 H19",
    "refresh": ("M20 12 A8 8 0 1 1 12 4 M12 4 L16.5 4 M12 4 L12 8.5"),
    "search": "M11 4 A7 7 0 1 0 11 18 A7 7 0 1 0 11 4 M16 16 L20 20",
    "copy": ("M9 3 H19 V15 M5 7 H15 V21 H5 Z"),
    "trash": ("M5 7 H19 M9 7 V5 H15 V7 M7 7 L8 21 H16 L17 7 "
              "M11 11 V17 M13 11 V17"),
    "menu": "M6 12 h0.01 M12 12 h0.01 M18 12 h0.01",
    "columns": "M4 5 H20 V19 H4 Z M10 5 V19 M15 5 V19",
    "play": "M8 5 L18 12 L8 19 Z",
    "eye": ("M2 12 C6 6 18 6 22 12 C18 18 6 18 2 12 Z "
            "M12 9 A3 3 0 1 0 12 15 A3 3 0 1 0 12 9"),
    "chevron": "M8 10 L12 14 L16 10",
    "arrow_right": "M4 12 H19 M13 6 L19 12 L13 18",

    # --- Zustaende / Signale ---------------------------------------------
    "warning": "M12 4 L22 20 H2 Z M12 10 V14 M12 17 h0.01",
    "info": "M12 3 A9 9 0 1 0 12 21 A9 9 0 1 0 12 3 M12 11 V16 M12 8 h0.01",
    "lock": ("M6 11 H18 V20 H6 Z M9 11 V8 A3 3 0 0 1 15 8 V11"),
    "lock_open": ("M6 11 H18 V20 H6 Z M9 11 V8 A3 3 0 0 1 15 8"),
    "star": ("M12 3 L14.6 9.3 L21.4 9.8 L16.2 14.2 L17.8 20.8 "
             "L12 17.2 L6.2 20.8 L7.8 14.2 L2.6 9.8 L9.4 9.3 Z"),
    "clock": "M12 3 A9 9 0 1 0 12 21 A9 9 0 1 0 12 3 M12 7 V12 L15.5 14",

    # --- Handel / Bestand ------------------------------------------------
    # Karte mit Nadel (Stock locations, emm458).
    "map": ("M12 21 C12 21 5 14.5 5 9.5 A7 7 0 0 1 19 9.5 C19 14.5 12 21 12 21 Z "
            "M12 12 A2.5 2.5 0 1 0 12 7 A2.5 2.5 0 1 0 12 12"),
    "package": ("M12 3 L21 7.5 V16.5 L12 21 L3 16.5 V7.5 Z "
                "M3 7.5 L12 12 L21 7.5 M12 12 V21"),
    "cart": ("M3 4 H6 L8.5 15 H18 L20 8 H7 M9 19 h0.01 M17 19 h0.01"),
    "coins": ("M12 5 C16.5 5 20 6.4 20 8 C20 9.6 16.5 11 12 11 "
              "C7.5 11 4 9.6 4 8 C4 6.4 7.5 5 12 5 Z "
              "M4 8 V16 C4 17.6 7.5 19 12 19 C16.5 19 20 17.6 20 16 V8"),
    "chart": "M4 20 V4 M4 20 H20 M8 16 V11 M12.5 16 V7 M17 16 V13",
    "trend_up": "M4 17 L10 11 L13.5 14.5 L20 8 M15 8 H20 V13",

    # --- Industrie -------------------------------------------------------
    "factory": ("M3 20 V10 L9 13.5 V10 L15 13.5 V10 L21 13.5 V20 Z "
                "M6 20 V16 M12 20 V16 M18 20 V16"),
    "hammer": ("M14 3 L21 10 L18 13 L11 6 Z M11.5 8.5 L4 16 V20 H8 L15.5 12.5"),
    "flask": ("M9 3 H15 M10.5 3 V10 L5 19 H19 L13.5 10 V3 M7.7 15 H16.3"),
    "blueprint": ("M5 4 H19 V20 H5 Z M8 8 H16 M8 12 H16 M8 16 H12"),
    "satellite": ("M4 20 L10 14 M8 12 A8 8 0 0 1 16 4 M9.5 16 "
                  "A4 4 0 0 0 13.5 12 M14 9 L20 3 M17 12 L21 8"),
    "target": ("M12 3 A9 9 0 1 0 12 21 A9 9 0 1 0 12 3 "
               "M12 8 A4 4 0 1 0 12 16 A4 4 0 1 0 12 8 M12 12 h0.01"),

    # --- Ersatz fuer Emojis (Sitzung 16) ---------------------------------
    # Der Nutzer hat die Entwuerfe gesehen und freigegeben. Dieselbe
    # Formsprache wie oben: 24x24, 2px, runde Enden, keine Flaechen -
    # sonst faellt ein Symbol im Set auf.
    "clipboard": ("M9 4 H15 V7 H9 Z M9 5.5 H6.5 V20 H17.5 V5.5 H15 "
                  "M9 11 H15 M9 15 H13"),
    "wrench": ("M14.5 4.5 A5 5 0 1 0 19.5 9.5 L15.5 13.5 L10.5 8.5 Z "
               "M10.5 8.5 L4.5 14.5 V19.5 H9.5 L15.5 13.5"),
    "link": ("M10 14 A4 4 0 0 1 10 8.5 L12.5 6 A4 4 0 0 1 18 11.5 L16.5 13 "
             "M14 10 A4 4 0 0 1 14 15.5 L11.5 18 A4 4 0 0 1 6 12.5 L7.5 11"),
    "trophy": ("M8 4 H16 V9 A4 4 0 0 1 8 9 Z M8 5.5 H5 V7.5 A3 3 0 0 0 8 10.5 "
               "M16 5.5 H19 V7.5 A3 3 0 0 1 16 10.5 M12 13 V17 M9 20 H15 "
               "M10 17 H14"),
    "globe": ("M12 3 A9 9 0 1 0 12 21 A9 9 0 1 0 12 3 M3.5 12 H20.5 "
              "M12 3 A13 13 0 0 0 12 21 M12 3 A13 13 0 0 1 12 21"),
    "ban": ("M12 3 A9 9 0 1 0 12 21 A9 9 0 1 0 12 3 M5.6 5.6 L18.4 18.4"),
    # Sprechblase fuer den Community-Knopf (Sitzung 17) - bewusst NEUTRAL,
    # kein nachgezeichnetes Discord-Logo (fremdes Markenzeichen).
    "chat": ("M4 5 H20 V15 H10 L6 19 V15 H4 Z M8.5 10 h0.01 M12 10 h0.01 "
             "M15.5 10 h0.01"),
}

_cache = {}

# ---- Logo ---------------------------------------------------------------
# MM IN DER WABE (Nutzer-Entscheidung, Sitzung 8: "bleiben wir beim
# Doppel-M, daraus machen wir ein Logo fuer Motor Market MM" - im
# Gold/Amber-Stil der sechseckigen EVE-Embleme, Variante "Wabe mit
# Innenkante").
# Aufbau: Pointy-Top-Wabe wie im Spiel, dunkler Kern, goldener Rahmen mit
# Verlauf, dazu eine feine zweite Kante innen - die macht den Tiefeneindruck
# der EVE-Zellen. Darin das Doppel-M im selben Verlauf.
# TECHNISCHE GRENZE (geprueft, nicht vermutet): Qts SVG-Renderer kann
# VERLAEUFE, aber KEINE Filter (feGaussianBlur). Ein echtes weiches Leuchten
# wie im Spiel ist damit nicht moeglich - deshalb Verlauf statt Schein.
_LOGO = (
    '<defs><linearGradient id="mmg" x1="0" y1="0" x2="0.6" y2="1">'
    '<stop offset="0" stop-color="{hell}"/>'
    '<stop offset="0.55" stop-color="{mitte}"/>'
    '<stop offset="1" stop-color="{tief}"/></linearGradient></defs>'
    # Aussenwabe: dunkler Kern, goldener Rahmen
    '<path d="M32 4 L56.2 18 V46 L32 60 L7.8 46 V18 Z" fill="{kern}" '
    'stroke="url(#mmg)" stroke-width="2.8" stroke-linejoin="round"/>'
    # Innenkante - der EVE-Zellen-Look
    '<path d="M32 10 L51 21 V43 L32 54 L13 43 V21 Z" fill="none" '
    'stroke="{tief}" stroke-width="1.2" stroke-linejoin="round" '
    'opacity="0.75"/>'
    # Doppel-M
    '<polyline points="16,40 16,25 23,33 30,25 30,40" fill="none" '
    'stroke="url(#mmg)" stroke-width="3.4" stroke-linecap="round" '
    'stroke-linejoin="round"/>'
    '<polyline points="34,40 34,25 41,33 48,25 48,40" fill="none" '
    'stroke="url(#mmg)" stroke-width="3.4" stroke-linecap="round" '
    'stroke-linejoin="round"/>')


def logo_svg(hell=None, mitte=None, tief=None, kern=None):
    """Logo als SVG-Text. Ohne Argumente im Gold-Verlauf; die Farben lassen
    sich ueberschreiben (z. B. alle gleich fuer eine einfarbige Variante auf
    hellen Systemen)."""
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
            + _LOGO.format(hell=hell or theme.GOLD_HELL,
                           mitte=mitte or theme.GOLD,
                           tief=tief or theme.GOLD_TIEF,
                           kern=kern or theme.LOGO_KERN) + '</svg>')


def logo_pixmap(groesse=32, **farben):
    """Das Programm-Logo in der gewuenschten Kantenlaenge.

    QUELLE IST assets/logo.png (Nutzer-Vorlage, Sitzung 11). Frueher wurde
    das Logo hier gezeichnet; die gezeichnete Fassung bleibt als
    RUECKFALLEBENE bestehen - fehlt die Bilddatei (etwa weil jemand den
    assets-Ordner nicht mitgepackt hat), zeigt das Programm lieber ein
    schlichtes Logo als gar keines.

    `farben` wirkt nur noch auf die gezeichnete Rueckfallebene; die
    Bilddatei bringt ihre Farben mit. Der Parameter bleibt, weil Aufrufer
    ihn uebergeben duerfen, ohne dass es kracht.
    """
    schluessel = ("__logo__", int(groesse), tuple(sorted(farben.items())))
    fertig = _cache.get(schluessel)
    if fertig is not None:
        return fertig
    pm = None
    if not farben:
        _pfad = theme.asset_pfad("logo.png")
        if _os_ic.path.exists(_pfad):
            _roh = QPixmap(_pfad)
            if not _roh.isNull():
                # GLATT SKALIEREN und Seitenverhaeltnis halten: bei 16 px
                # (Titelleiste) wird sonst aus feinen Linien Matsch.
                pm = _roh.scaled(int(groesse), int(groesse),
                                 Qt.KeepAspectRatio, Qt.SmoothTransformation)
    if pm is None:
        pm = QPixmap(int(groesse), int(groesse))
        pm.fill(Qt.transparent)
        r = QSvgRenderer(QByteArray(logo_svg(**farben).encode("utf-8")))
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing, True)
        r.render(p)
        p.end()
    _cache[schluessel] = pm
    return pm


def logo_icon(**farben):
    """QIcon mit MEHREREN Groessen - Windows waehlt je nach Ort selbst
    (Taskleiste 32, Titelleiste 16, Alt-Tab 48, Verknuepfung 256). Ein
    einzelnes 32er-Bild wuerde beim Hochskalieren unscharf."""
    ic = QIcon()
    for g in (16, 20, 24, 32, 48, 64, 128, 256):
        ic.addPixmap(logo_pixmap(g, **farben))
    return ic


def verfuegbar():
    """Namen aller Symbole - fuer Tests und Uebersichten."""
    return sorted(_PFADE)


def svg(name, farbe=None, strich=2.0):
    """Rohes SVG als Text (fuer Einbettung in HTML-Tooltips o.ae.)."""
    pfad = _PFADE.get(name)
    if pfad is None:
        return ""
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
        f'<path d="{pfad}" fill="none" stroke="{farbe or theme.ICON}" '
        f'stroke-width="{strich}" stroke-linecap="round" '
        f'stroke-linejoin="round"/></svg>')


def pixmap(name, farbe=None, groesse=16, strich=2.0):
    """Gerendertes Bild. Gecacht je (Name, Farbe, Groesse) - die Symbole
    werden in Tabellen tausendfach gebraucht, neu rendern waere teuer."""
    schluessel = (name, farbe or theme.ICON, int(groesse), float(strich))
    fertig = _cache.get(schluessel)
    if fertig is not None:
        return fertig
    quelle = svg(name, farbe, strich)
    if not quelle:
        return QPixmap()
    pm = QPixmap(int(groesse), int(groesse))
    pm.fill(Qt.transparent)
    r = QSvgRenderer(QByteArray(quelle.encode("utf-8")))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    r.render(p)
    p.end()
    _cache[schluessel] = pm
    return pm


def html(name, farbe=None, groesse=14, strich=2.0):
    """Symbol als <img>-Schnipsel fuer Rich-Text-Beschriftungen.

    WOZU (Sitzung 16): Qt kann in einen normalen Beschriftungstext kein
    Bild setzen - `setIcon` gibt es nur an Knoepfen, Reitern und
    Listeneintraegen. Fuer die Faelle, in denen frueher ein Emoji MITTEN im
    Text stand ("Plan eingefroren", Karten-Marken), liefert das hier ein
    eingebettetes SVG, das QLabel im Rich-Text-Modus darstellt.

    Faellt es aus, kommt ein leerer String zurueck - die Beschriftung bleibt
    dann eben ohne Symbol, aber nie kaputt.
    """
    import base64
    try:
        d = _PFADE[name]
        f = farbe or theme.TEXT
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" '
               f'width="{groesse}" height="{groesse}">'
               f'<path d="{d}" fill="none" stroke="{f}" stroke-width="{strich}" '
               f'stroke-linecap="round" stroke-linejoin="round"/></svg>')
        b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return (f'<img src="data:image/svg+xml;base64,{b64}" '
                f'width="{groesse}" height="{groesse}">')
    except Exception:
        return ""


def icon(name, farbe=None, groesse=16, strich=2.0):
    """QIcon fuer Knoepfe, Menue-Eintraege und Tabellenzellen.

    Qt waehlt selbst zwischen den hinterlegten Zustaenden: Normal (Ruhe),
    Active (Maus darueber), Selected (in markierten Zeilen) und Disabled.
    Wer eine eigene Farbe uebergibt, bekommt SIE in allen Zustaenden - dann
    ist die Farbe ja die Aussage (AMBER/RED/GREEN)."""
    ic = QIcon(pixmap(name, farbe, groesse, strich))
    if farbe is None:
        # NUTZER (Sitzung 8): "wenn die Symbole aktiv sind, etwas heller,
        # mehr ins Weiss hinein." Nur der neutrale Ton bekommt die
        # Aufhellung - eingefaerbte Zustands-Symbole behalten ihre Farbe.
        ic.addPixmap(pixmap(name, theme.ICON_ACTIVE, groesse, strich),
                     QIcon.Active)
        ic.addPixmap(pixmap(name, theme.ICON_ACTIVE, groesse, strich),
                     QIcon.Selected)
        ic.addPixmap(pixmap(name, theme.ICON_DIM, groesse, strich),
                     QIcon.Disabled)
    return ic


_PUNKT_CACHE = {}


def _punkt(farbe, groesse):
    """Gefuellter Kreis in `farbe` als QIcon. Gemeinsamer Unterbau fuer
    gruener_punkt() und lauf_punkt() - zwei fast gleiche Malroutinen waeren
    zwei Stellen, an denen Groesse oder Rand auseinanderlaufen koennen."""
    from PySide6.QtGui import QColor
    from PySide6.QtCore import Qt as _Qt
    g = int(groesse)
    _key = (farbe, g)
    if _key in _PUNKT_CACHE:
        return _PUNKT_CACHE[_key]
    pm = QPixmap(g, g)
    pm.fill(QColor(0, 0, 0, 0))
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing, True)
    p.setPen(_Qt.NoPen)
    p.setBrush(QColor(farbe))
    p.drawEllipse(1, 1, g - 2, g - 2)
    p.end()
    _PUNKT_CACHE[_key] = QIcon(pm)
    return _PUNKT_CACHE[_key]


def gruener_punkt(groesse: int = 14):
    """Ein gefuellter gruener Kreis als QIcon.

    NUTZER-WUNSCH (Sitzung 12): "wenn wir die Sachen gebaut haben, bleibt
    das Viereck zum Ab- und Anhaken da. Ich haette gerne, dass das zu einem
    gruenen Kreis wird - ein anderes Symbol fuer 'fertig gebaut und ESI
    geprueft', ohne Kommentar im Bauplan."

    Bewusst OHNE Text: die Zeile soll auf einen Blick als erledigt lesbar
    sein, nicht durch einen weiteren Hinweis erklaert werden.
    """
    # FARBE AUS DEM THEME, nie hart hier (aa170/aa175): Paletten wohnen in
    # theme.py, sonst driften Symbole und Oberflaeche auseinander.
    from . import theme as _theme
    return _punkt(_theme.GREEN, groesse)


def lauf_punkt(groesse: int = 14):
    """Ein gefuellter Kreis in der Lauf-Farbe: "steckt in der Bauschleife".

    NUTZER-WUNSCH (Sitzung 14): "ists noch in der Bauschleife auch schon
    gedimmt aber violetter punkt."

    FARBE IST BEWUSST NICHT VIOLETT, und das ist mit ihm abgestimmt: violett
    ist im Runplaner die Farbe der Reaktions-STUFEN (theme.VIOLET /
    VIOLET_2). Ein violetter Punkt saesse dort in der Farbe der Zeile, in der
    er steht. Fuer "laeuft gerade" gibt es seit Sitzung 12 bereits
    theme.CYAN_RUN - dieselbe Aussage bekommt dieselbe Farbe, sonst haette
    ein laufender Job zwei Erscheinungsbilder. Nutzer-Entscheid Sitzung 14:
    "CYAN_RUN behalten".
    """
    from . import theme as _theme
    return _punkt(_theme.CYAN_RUN, groesse)
