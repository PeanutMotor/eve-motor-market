"""Basis-Bausteine der Oberflaeche: ISK-Formatierung, sortierende
Tabellenzelle und die beiden ISK-Eingabefelder.

Ausgelagert in Sitzung 8, damit `mw_bauplan_tabs.py` sie nutzen kann, ohne
`main_window` zu importieren (das waere ein Zirkel-Import - main_window
importiert die Mixins ja selbst).

Die Ruempfe sind WOERTLICH aus main_window.py verschoben, kein Zeichen
geaendert. ACHTUNG beim Aufraeumen: `__lt__`, `textFromValue`,
`valueFromText` und `validate` sehen "nie aufgerufen" aus - sie sind
Qt-Overrides und werden vom Framework gerufen. Nicht loeschen.
"""
from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (QAbstractButton, QAbstractScrollArea,
                               QAbstractSpinBox, QApplication, QComboBox, QDialog,
                               QDoubleSpinBox, QLineEdit, QSlider, QSpinBox, QStyle,
                               QStyleOptionViewItem, QTableWidgetItem,
                               QWidget)

from ..config import KEIN_DECRYPTOR
from ..sprache import t
from . import icons, theme

# KEIN_DECRYPTOR steht in config.py, wo die uebrigen gespeicherten Werte
# liegen - EINE Wahrheit. Hier nur weitergereicht, damit die UI-Module ihn
# zusammen mit `dec_anzeige` aus derselben Datei holen.
__all__ = ["KEIN_DECRYPTOR", "dec_anzeige", "isk", "tab_icon", "tab_icon_at",
           "NumericItem", "IskMillionSpin", "IskGroupedSpin",
           "MinimizableDialog", "ohne_mausrad", "combos_ohne_mausrad",
           "kopier_menue", "kontext_menue", "kopier_wert", "zellen_text",
           "ZahlVorneSpin"]


def dec_anzeige(nm):
    """Decryptor-Name fuer die ANZEIGE. Der gespeicherte Schluessel bleibt
    deutsch (s. KEIN_DECRYPTOR), die Beschriftung nicht - sonst stand
    "Kein Decryptor" mitten in der englischen Oberflaeche. Echte
    Decryptor-Namen sind EVE-Eigennamen und bleiben, wie sie sind."""
    return t("No decryptor") if nm == KEIN_DECRYPTOR else nm


def tab_icon(tabs, widget, text, name):
    """Reiter mit GEZEICHNETEM Symbol statt Emoji im Reitertext.

    Gleiche Bauweise wie `_btn_icon` (Sitzung 9, Knoepfe) und
    `_combo_item` (Auswahllisten): der TEXT bleibt sauber lesbar - wichtig
    fuer Suche, Screenreader und die Prueftexte -, das Symbol kommt aus dem
    eigenen Set und sieht damit auf jedem Betriebssystem gleich aus statt
    je nach Emoji-Font zu variieren.

    Faellt das Symbol aus, bleibt der Reiter voll bedienbar und beschriftet -
    er hat dann eben keins. Der Reiter darf NIE an einem fehlenden Bild
    haengen, deshalb wird er ZUERST angelegt und das Symbol danach gesetzt.

    Gibt den Index des neuen Reiters zurueck.
    """
    _i = tabs.addTab(widget, text)
    try:
        tabs.setTabIcon(_i, icons.icon(name))
    except Exception:
        pass
    return _i


def tab_icon_at(tabs, pos, widget, text, name):
    """Wie `tab_icon`, nur an einer festen POSITION eingefuegt.

    Drei Bauplan-Reiter werden nachtraeglich einsortiert (Blueprints vor
    Materialien vor Runplaner) und liefen deshalb ueber `insertTab` mit
    Emoji im Text. Emojis sehen je nach Betriebssystem-Font anders aus -
    genau dafuer gibt es das eigene Symbol-Set (Sitzung 9).

    Auch hier: Reiter ZUERST anlegen, Symbol danach. Faellt es aus, bleibt
    der Reiter voll bedienbar und beschriftet.
    """
    tabs.insertTab(pos, widget, text)
    try:
        tabs.setTabIcon(pos, icons.icon(name))
    except Exception:
        pass
    return pos


# ---- KOPIERBARE NAMEN IN EINER BAUM-SPALTE --------------------------------
# NUTZER, 15.09.2026 (Runplaner): "im Runplaner steht Silicon Diborite - klickt
# man drauf, bekommt man Silicon Diborite Reaction Formula ins Clipboard", und
# der Name soll einen kleinen Rahmen tragen wie die Run-Zahlen daneben.
#
# OHNE JEDE HERVORHEBUNG (Nutzer, 15.09.2026, nach dem Ausprobieren: "ich
# moechte, dass die Items also Tungsten Carbide wieder normal aussehen, also
# ohne Amber-Rahmen und einfach wieder weiss - oder blau, wenn in Bau").
# Ein Rahmen und ein Chip waren beide zu laut. Die Zeile sieht jetzt wieder
# genau so aus wie vorher; klickbar ist sie trotzdem.
#
# WAS BLEIBT, ist die Trefferflaeche: `kopier_text_rect` sagt, wo der TEXT
# steht. Nur dort kopiert ein Klick - das Kaestchen daneben bleibt frei,
# sonst ueberschriebe jeder Haken still die Zwischenablage.
ROLLE_KOPIERNAME = Qt.UserRole + 8


def kopier_text_rect(option_oder_view, index, item_rect=None):
    """Das Rechteck, in dem der TEXT dieser Zelle steht.

    Dieselbe Rechnung fuer das Zeichnen und fuer den Klick - sonst sitzt der
    Rahmen woanders als die Trefferflaeche, und der Nutzer klickt ins Leere.
    Faellt die Style-Rechnung aus, bleibt ein ehrlicher Rueckfall: alles
    rechts vom Kaestchen.
    """
    try:
        if isinstance(option_oder_view, QStyleOptionViewItem):
            opt, widget = option_oder_view, option_oder_view.widget
        else:
            widget = option_oder_view
            opt = QStyleOptionViewItem()
            opt.initFrom(widget)
            opt.rect = item_rect
            opt.features |= QStyleOptionViewItem.HasCheckIndicator
            opt.text = str(index.data(Qt.DisplayRole) or "")
        style = widget.style() if widget is not None else QApplication.style()
        r = style.subElementRect(QStyle.SE_ItemViewItemText, opt, widget)
        # DER TEXT KOMMT AUS DEM MODELL, nicht aus opt.text: der Delegate
        # leert opt.text, weil er die Beschriftung selbst auf den Chip malt.
        # Wuerde die Breite aus opt.text kommen, waere der Chip 0 px breit.
        _txt = str(index.data(Qt.DisplayRole) or "") if index is not None else ""
        # AM TEXT KLEBEN, NICHT AN DER SPALTE: ein Chip ueber die ganze
        # Spaltenbreite saehe aus wie ein Eingabefeld.
        breite = QFontMetrics(opt.font).horizontalAdvance(_txt) + 8
        if breite > 0:
            r.setWidth(min(r.width(), breite))
        return r
    except Exception:
        _r = (option_oder_view.rect
              if isinstance(option_oder_view, QStyleOptionViewItem)
              else item_rect)
        return _r.adjusted(24, 0, 0, 0) if _r is not None else None


# ---- KARTEN VON HAND ANORDNEN ---------------------------------------------
# NUTZER, 15.09.2026: "koennen wir einen Button einfuehren 'Baupläne selber
# anordnen' und dann kann man die per Drag and Drop so ziehen wie man will.
# Linksklick halten und ziehen, aber scrollen muss auch gehen." Die eigene
# Reihenfolge soll das Schliessen UND ein Update ueberleben.
#
# WARUM KEIN Qt-DRAG-AND-DROP: die Karten haengen in einem QVBoxLayout, nicht
# in einer Liste. Echtes QDrag braeuchte ein Modell, eine MIME-Kodierung und
# eine Drop-Zone - fuer "Widget im Layout verschieben" ist das Verschieben im
# Layout selbst der kuerzere und ruhigere Weg: die Karte folgt der Maus in
# Sprüngen von Platz zu Platz, es gibt kein zweites schwebendes Bild.
#
# MAUSRAD BLEIBT MAUSRAD: gefiltert werden nur Druecken/Bewegen/Loslassen der
# LINKEN Taste. Wheel-Ereignisse laufen unangetastet an die Bildlaufleiste -
# ausdrueckliche Nutzer-Bedingung ("scrollen muss auch gehen").
class KartenSortierer(QObject):
    """Macht Widgets in einem QVBoxLayout mit der Maus verschiebbar.

    Nur aktiv, solange `aktiv` True ist - im Ruhezustand sieht und aendert
    diese Klasse nichts. Das ist Absicht: die Karten tragen Knoepfe, und ein
    dauerhaft lauernder Filter waere ein Risiko fuer jeden Klick darauf.

    `beim_ablegen` wird nach dem Loslassen mit der neuen Reihenfolge der
    Nutzdaten (was `schluessel_von` je Widget liefert) aufgerufen.
    """
    # DIE DREI ZUSTAENDE EINER KARTE IM ANORDNEN-MODUS (Nutzer, 15.09.2026:
    # "wenn ich mit der Maus ueber einen Bauplan fahre, moechte ich dass er
    # leicht hervorgehoben wird, und wenn ich ihn dann drag and droppe, damit
    # man erkennt: ja okay, ich bewege etwas").
    # Ruhig -> nichts. Darunter -> zarter Rahmen. In der Hand -> kraeftiger
    # Rahmen und Flaeche. Alle drei tragen 1 px Rahmen, damit die Karte beim
    # Wechsel nicht springt.
    # NUR DIE KARTE SELBST, NICHT IHRE KINDER (Nutzer, 15.09.2026: "wirklich
    # nur den Gesamtrahmen vom Bauplan, nicht 'Profit' und so auch nochmal
    # umrahmt"). Ein Stylesheet OHNE Selektor vererbt sich an jedes Label und
    # jeden Knopf darin - genau das sah man. Mit `#Name` gilt es fuer das eine
    # Widget, das diesen Objektnamen traegt.
    OBJEKTNAME = "SortierKarte"
    _CSS_RUHE = "#" + OBJEKTNAME + "{border:1px solid transparent; border-radius:8px;}"
    _CSS_HOVER = "#" + OBJEKTNAME + "{{border:1px solid {a}; border-radius:8px;}}"
    _CSS_ZIEHT = ("#" + OBJEKTNAME + "{{border:1px solid {a}; "
                  "border-radius:8px; background:{f};}}")

    def __init__(self, layout, scrollbereich, schluessel_von, beim_ablegen,
                 akzent=None, flaeche=None, parent=None):
        super().__init__(parent)
        self._lay = layout
        self._scroll = scrollbereich
        self._key = schluessel_von
        self._fertig = beim_ablegen
        # ALLE FARBEN AUS theme.py (aa170: keine Hex-Werte am Theme vorbei).
        self._akzent = akzent or theme.CYAN
        self._flaeche = flaeche or theme.CYAN_FILL
        self.aktiv = False
        self._widget = None
        self._start = None
        self._zieht = False
        self._unter_maus = None
        self._roll = QTimer(self)
        self._roll.setInterval(40)
        self._roll.timeout.connect(self._rollen)
        self._roll_richtung = 0

    # -- an- und abmelden ---------------------------------------------------
    def ueberwache(self, widget):
        """Dieses Widget und ALLE seine Kinder beobachten.

        Auch die Kinder: sonst liesse sich die Karte nur an ihrem schmalen
        Rand greifen - ueberall sonst faengt ein Label den Klick ab, bevor
        der Rahmen ihn sieht.

        DIE KNOEPFE BLEIBEN TROTZDEM BEDIENBAR (Nutzer, 15.09.2026):
        *"was bringt der Arrange-Modus, wenn er aktiviert ist und ich nichts
        druecken kann?"* - der Modus ist zum Anlassen gedacht. Frueher stand
        hier "Nutzer-Bedingung": das war ein LESEFEHLER meinerseits, seine
        Zeile *"Open, Done, Delete geht nicht"* war eine Meldung, keine
        Anforderung. `_ist_bedienelement` laesst diese Klicks jetzt durch.
        """
        widget.installEventFilter(self)
        widget.setAttribute(Qt.WA_Hover, True)
        # Der Objektname ist der Selektor, mit dem die Hervorhebung NUR
        # dieses Widget trifft (s. OBJEKTNAME oben).
        widget.setObjectName(self.OBJEKTNAME)
        for kind in widget.findChildren(QWidget):
            kind.installEventFilter(self)

    def _zeige(self, widget, zustand):
        """Karte in einen der drei Zustaende versetzen."""
        if widget is None:
            return
        try:
            if zustand == "zieht":
                widget.setStyleSheet(self._CSS_ZIEHT.format(
                    a=self._akzent, f=self._flaeche))
            elif zustand == "hover":
                widget.setStyleSheet(self._CSS_HOVER.format(a=self._akzent))
            else:
                widget.setStyleSheet(self._CSS_RUHE)
        except Exception:
            pass

    def alles_zuruecksetzen(self):
        """Jede Karte in den Ruhezustand - beim Ausschalten des Modus."""
        for i in range(self._lay.count()):
            _it = self._lay.itemAt(i)
            _w = _it.widget() if _it is not None else None
            if _w is not None:
                try:
                    _w.setStyleSheet("")
                except Exception:
                    pass
        self._unter_maus = None

    def _ist_bedienelement(self, obj):
        """Sitzt dieser Klick auf einem Knopf (oder einem anderen
        Bedienelement) INNERHALB der Karte?

        Dann gehoert er dem Knopf, nicht dem Sortierer: gezogen wird an
        Name, Zahlen und freier Flaeche, gedrueckt wird auf "Open", "Done",
        "Delete" und das Schloss. Ohne diese Unterscheidung war der
        Anordnen-Modus ein Modus, in dem man nichts mehr tun kann - und
        genau deshalb nicht dauerhaft nutzbar.

        Gesucht wird nach OBEN bis zur Karte: der Klick kommt oft auf einem
        Kind des Knopfes an (Beschriftung, Symbol), nicht auf dem Knopf
        selbst. Ueber die Karte hinaus wird nicht gesucht - sonst zaehlte
        irgendein Knopf weiter oben im Fenster mit.
        """
        w = obj if isinstance(obj, QWidget) else None
        while w is not None:
            if isinstance(w, (QAbstractButton, QAbstractSpinBox, QComboBox,
                              QLineEdit)):
                return True
            if self._lay.indexOf(w) >= 0:
                return False        # bei der Karte angekommen: kein Knopf
            w = w.parentWidget()
        return False

    def _karte_zu(self, obj):
        """Zu welchem der verwalteten Widgets gehoert dieses Objekt?"""
        w = obj if isinstance(obj, QWidget) else None
        while w is not None:
            if self._lay.indexOf(w) >= 0:
                return w
            w = w.parentWidget()
        return None

    # -- der eigentliche Griff ---------------------------------------------
    def eventFilter(self, obj, ev):
        if not self.aktiv:
            return False
        try:
            typ = ev.type()
            if typ in (QEvent.Enter, QEvent.HoverEnter, QEvent.HoverMove):
                _k = self._karte_zu(obj)
                if _k is not None and _k is not self._unter_maus \
                        and not self._zieht:
                    self._zeige(self._unter_maus, "ruhe")
                    self._unter_maus = _k
                    self._zeige(_k, "hover")
                return False        # Hover NUR anzeigen, nie schlucken
            if typ in (QEvent.Leave, QEvent.HoverLeave):
                if not self._zieht and self._unter_maus is not None \
                        and self._karte_zu(obj) is self._unter_maus:
                    self._zeige(self._unter_maus, "ruhe")
                    self._unter_maus = None
                return False
            if typ == QEvent.MouseButtonPress and ev.button() == Qt.LeftButton:
                # KNOEPFE GEHOEREN DEM KNOPF (Nutzer, 15.09.2026). Nichts
                # merken und nichts schlucken - sonst haengt der Sortierer
                # an einem Klick, den er gar nicht bekommen hat, und die
                # naechste Mausbewegung zoege die Karte hinter dem
                # geoeffneten Plan her.
                if self._ist_bedienelement(obj):
                    self._widget = None
                    self._start = None
                    self._zieht = False
                    return False
                self._widget = self._karte_zu(obj)
                self._start = ev.globalPosition().toPoint()
                self._zieht = False
                # SCHLUCKEN, damit der Klick auf der freien Kartenflaeche
                # nicht zusaetzlich als Auswahl o.ae. durchgeht.
                return self._widget is not None
            if typ == QEvent.MouseMove and self._widget is not None:
                pos = ev.globalPosition().toPoint()
                if not self._zieht:
                    if (pos - self._start).manhattanLength() < \
                            QApplication.startDragDistance():
                        return True
                    self._zieht = True
                    # JETZT SIEHT MAN, DASS ETWAS IN DER HAND IST.
                    self._zeige(self._widget, "zieht")
                self._einsortieren(pos)
                self._rollen_pruefen(pos)
                return True
            if typ == QEvent.MouseButtonRelease and self._widget is not None:
                self._roll.stop()
                self._roll_richtung = 0
                _hat_gezogen = self._zieht
                # Zurueck in den Hover-Zustand: die Maus steht ja noch darauf.
                self._zeige(self._widget, "hover")
                self._unter_maus = self._widget
                self._widget = None
                self._start = None
                self._zieht = False
                if _hat_gezogen and self._fertig is not None:
                    self._fertig(self.reihenfolge())
                return True
        except Exception:
            # Eine Bequemlichkeit darf die Seite nie kosten. Beim kleinsten
            # Zweifel: Griff loslassen und Qt weitermachen lassen.
            self._widget = None
            self._zieht = False
            self._roll.stop()
        return False

    def _einsortieren(self, global_pos):
        """Die gegriffene Karte an die Stelle setzen, ueber der die Maus steht."""
        eltern = self._widget.parentWidget()
        if eltern is None:
            return
        y = eltern.mapFromGlobal(global_pos).y()
        alt = self._lay.indexOf(self._widget)
        neu = alt
        for i in range(self._lay.count()):
            _it = self._lay.itemAt(i)
            _w = _it.widget() if _it is not None else None
            if _w is None or _w is self._widget:
                continue
            _m = _w.y() + _w.height() // 2
            if y < _m:
                neu = min(neu, i)
                break
            neu = max(neu, i)
        if neu != alt:
            self._lay.removeWidget(self._widget)
            self._lay.insertWidget(neu, self._widget)

    def _rollen_pruefen(self, global_pos):
        """Am oberen/unteren Rand mitscrollen, solange gezogen wird.

        Ohne das laesst sich eine Karte nicht ueber den sichtbaren Bereich
        hinaus verschieben - bei zehn Plaenen waere Ziehen nutzlos.
        """
        if self._scroll is None:
            self._roll.stop()
            return
        vp = self._scroll.viewport()
        y = vp.mapFromGlobal(global_pos).y()
        rand = 28
        if y < rand:
            self._roll_richtung = -1
        elif y > vp.height() - rand:
            self._roll_richtung = 1
        else:
            self._roll_richtung = 0
        if self._roll_richtung and not self._roll.isActive():
            self._roll.start()
        elif not self._roll_richtung:
            self._roll.stop()

    def _rollen(self):
        try:
            bar = self._scroll.verticalScrollBar()
            bar.setValue(bar.value() + self._roll_richtung * 14)
        except Exception:
            self._roll.stop()

    def reihenfolge(self):
        """Die Nutzdaten der Karten in der jetzigen Layout-Reihenfolge."""
        raus = []
        for i in range(self._lay.count()):
            _it = self._lay.itemAt(i)
            _w = _it.widget() if _it is not None else None
            if _w is None:
                continue
            _k = self._key(_w)
            if _k is not None:
                raus.append(_k)
        return raus


# MAUSRAD GEHOERT DER BILDLAUFLEISTE (Nutzer 26.09.2026, Invention-Reiter:
# "wenn man scrollen will und mit der Maus per Zufall auf einem Decryptor-
# Dropdown ist, scrollt das Dropdown und dann faengt der Plan automatisch an
# zu rechnen und alles laggt. Dropdowns nur ueber Klicken bedienen"). Ein
# QComboBox/QSpinBox/QSlider nimmt das Rad von Haus aus als Wertaenderung -
# in einem langen, scrollbaren Reiter ist das eine Falle: jede Aenderung
# loest die Rechnung aus. Der Filter schluckt das Rad am Bedienelement und
# gibt es der naechsten umgebenden Bildlaufflaeche (QAbstractScrollArea,
# ueber ihren Viewport). NICHT einfach an den Eltern-Widget schicken: ein
# per sendEvent erzeugtes Rad-Ereignis wandert in Qt nicht mehr die
# Eltern-Kette hoch (nur spontane tun das) - gemessen, es kam nie an.
# Bedienen: Klick/Tastatur.
class _RadSperre(QObject):
    def eventFilter(self, obj, ev):
        try:
            if ev.type() == QEvent.Wheel:
                _w = obj.parentWidget() if isinstance(obj, QWidget) else None
                while _w is not None and not isinstance(_w, QAbstractScrollArea):
                    _w = _w.parentWidget()
                if _w is not None:
                    QApplication.sendEvent(_w.viewport(), ev)
                return True
        except Exception:
            pass
        return False


class _FensterComboRadSperre(QObject):
    """ANWENDUNGSWEIT, aber nur in Fenstern mit der Eigenschaft
    "combo_ohne_mausrad" (Nutzer 27.09.2026, Bauplan-Seitenleiste:
    "wenn ich aus Versehen mit der Maus bei Reprocessing stehe und das
    Scrollrad nutze, scrollt das Dropdown und nicht die rechte Sidebar -
    Dropdown bitte nur klickbar machen"; gleich danach: "dasselbe in den
    Invention-Settings, 75 % laesst sich scrollen" - also auch Zahlenfelder
    und Regler). Als App-Filter erfasst er auch Bedienelemente, die erst
    spaeter entstehen (Runplaner-Zeilen, Karten nach einem Neuaufbau) -
    ohne dass jede Stelle daran denken muss. Das Rad geht an die naechste
    Bildlaufflaeche, wie bei `ohne_mausrad`; die offene Liste eines
    Dropdowns (eigenes Popup) rollt weiter normal."""
    def eventFilter(self, obj, ev):
        try:
            if ev.type() == QEvent.Wheel and isinstance(
                    obj, (QComboBox, QAbstractSpinBox, QSlider)):
                _fen = obj.window()
                if _fen is not None and _fen.property("combo_ohne_mausrad"):
                    return _RadSperre().eventFilter(obj, ev) or True
        except Exception:
            pass
        return False


_FENSTER_RAD_SPERRE = []


def combos_ohne_mausrad(fenster):
    """Alle Dropdowns, Zahlenfelder und Regler in `fenster` (auch spaeter
    entstehende) nur per Klick/Tastatur - das Mausrad scrollt die Seite."""
    from PySide6.QtWidgets import QApplication as _QA
    fenster.setProperty("combo_ohne_mausrad", True)
    _app = _QA.instance()
    if _app is not None and not _FENSTER_RAD_SPERRE:
        _f = _FensterComboRadSperre(_app)
        _app.installEventFilter(_f)
        _FENSTER_RAD_SPERRE.append(_f)
    return fenster


def ohne_mausrad(w):
    """Bedienelement nur per Klick/Tastatur: das Mausrad scrollt die Seite."""
    w.installEventFilter(_RadSperre(w))
    # WheelFocus (Vorgabe bei Combo/Spin) wuerde beim Rad zusaetzlich den
    # Fokus holen; StrongFocus reicht fuer Klick und Tab.
    w.setFocusPolicy(Qt.StrongFocus)
    return w


# ---- RECHTSKLICK "COPY" IN JEDER TABELLE (Nutzer 29.09.2026) --------------
# "per Rechtsklick dann 'Copy' klicken, dann kopiert es Item Name oder Zahlen
# die da stehen je nach Column, und zwar ueberall im ganzen Tool ... An
# gewissen Orten gibt es schon Rechtsklick-Informationen, dann fuegen wir
# 'Copy' einfach auch dazu." Und ausdruecklich: NICHT per Linksklick.
#
# EIN MECHANISMUS fuer alle Tabellen: `kopier_menue(view, handler)` haengt
# statt des alten Menue-Handlers einen Verteiler an. Er merkt sich Tabelle +
# Klickpunkt, ruft den alten Handler, und jedes Menue, das dieser ueber
# `kontext_menue()` baut, bekommt "Copy" als ersten Eintrag. Baut der
# Handler GAR KEIN Menue (leere Zeile, keine Type-ID ...), zeigt der
# Verteiler selbst eines mit nur "Copy" - sonst gaebe es genau dort, wo der
# alte Handler frueh aussteigt, kein Kopieren.
KOPIER_ZIELE = []           # Stapel [view, pos, verbraucht]


def kopier_wert(text):
    """Was "Copy" in die Zwischenablage legt.

    Namen und Texte wie angezeigt. Eine reine ZAHL ohne Tausender-
    Trennzeichen und ohne " ISK" - so nimmt sie das Preisfeld im Spiel an
    ("1'234'567 ISK" -> "1234567"). Prozent, m³ usw. bleiben Text, weil
    dort die Einheit zur Zahl gehoert.
    """
    s = str(text or "").strip()
    if not s:
        return ""
    roh = s[:-4].strip() if s.endswith(" ISK") else s
    zahl = (roh.replace("'", "").replace("’", "").replace(" ", "")
            .replace(" ", "").replace(" ", ""))
    try:
        float(zahl)
    except ValueError:
        return s
    return zahl if zahl not in ("nan", "inf", "-inf") else s


def zellen_text(view, pos):
    """Angezeigter Text der Zelle unter `pos` (Viewport-Koordinaten) oder
    None. Zelle ohne Text, aber mit Zell-Widget: der Text seiner Labels
    (ein Knopf ist eine Handlung, keine Angabe - der zaehlt nicht)."""
    try:
        idx = view.indexAt(pos)
    except RuntimeError:
        return None
    if not idx.isValid():
        return None
    txt = str(idx.data(Qt.DisplayRole) or "").strip()
    if txt:
        return txt
    try:
        w = view.indexWidget(idx)
    except RuntimeError:
        w = None
    if w is None:
        return None
    _eigen = w.property("kopier_text")
    if _eigen:
        return str(_eigen)
    from PySide6.QtGui import QTextDocument
    from PySide6.QtWidgets import QLabel
    teile = []
    for lb in ([w] if isinstance(w, QLabel) else []) + w.findChildren(QLabel):
        _t = lb.text() or ""
        if "<" in _t:
            _d = QTextDocument(); _d.setHtml(_t); _t = _d.toPlainText()
        _t = _t.strip()
        if _t:
            teile.append(_t)
    return " ".join(teile) or None


def _kopieren_ausfuehren(view, text):
    wert = kopier_wert(text)
    QApplication.clipboard().setText(wert)
    try:
        fen = view.window()
        _pop = getattr(fen, "_flash_tip", None)
        if callable(_pop):
            _pop(t("copied: {name}").format(name=wert))
    except RuntimeError:
        pass


def kopier_aktion(menu, view, pos):
    """"Copy" als ERSTEN Eintrag in `menu`, danach ein Trennstrich. Ohne
    Text in der Zelle steht der Eintrag ausgegraut da (nicht weg - sonst
    wirkt das Menue an manchen Stellen anders als an anderen)."""
    text = zellen_text(view, pos)
    erste = menu.actions()[0] if menu.actions() else None
    from PySide6.QtGui import QAction
    a = QAction(icons.icon("copy"), t("Copy"), menu)
    a.setEnabled(bool(text))
    if text:
        a.setToolTip(kopier_wert(text))
        a.triggered.connect(lambda *_a, v=view, x=text: _kopieren_ausfuehren(v, x))
    menu.insertAction(erste, a)
    if erste is not None:
        menu.insertSeparator(erste)
    a.setProperty("ist_kopieren", True)
    return a


def kontext_menue(parent=None):
    """Statt `QMenu(parent)` in jedem Rechtsklick-Handler einer Tabelle:
    dasselbe Menue, das beim Oeffnen "Copy" oben einfuegt.

    KEIN QMenu-UNTERKLASSE MIT exec(): `super().exec()` aus einer
    Python-Unterklasse stuerzt PySide6 ab (Segfault, nachgestellt
    29.09.2026). Deshalb ein normales QMenu, und "Copy" kommt ueber
    `aboutToShow` hinein - dann stehen die Eintraege des Handlers schon."""
    from PySide6.QtWidgets import QMenu
    m = QMenu(parent)
    if KOPIER_ZIELE and not KOPIER_ZIELE[-1][2]:
        _z = KOPIER_ZIELE[-1]
        _z[2] = True
        _getan = []

        def _vor_dem_zeigen(menu=m, v=_z[0], pos=_z[1]):
            if not _getan:
                _getan.append(True)
                kopier_aktion(menu, v, pos)
        m.aboutToShow.connect(_vor_dem_zeigen)
    return m


def kopier_menue(view, handler=None):
    """Rechtsklick auf `view` bekommt "Copy". `handler(pos)` ist der
    bisherige Menue-Handler (oder None: dann NUR "Copy")."""
    view.setContextMenuPolicy(Qt.CustomContextMenu)

    def _verteiler(pos, v=view, h=handler):
        ziel = [v, pos, False]
        KOPIER_ZIELE.append(ziel)
        try:
            if h is not None:
                h(pos)
        finally:
            KOPIER_ZIELE.pop()
        if not ziel[2]:
            # der alte Handler hat kein Menue gebaut -> eines mit nur "Copy"
            m = kontext_menue(v)
            kopier_aktion(m, v, pos)
            m.exec(v.viewport().mapToGlobal(pos))
    view.customContextMenuRequested.connect(_verteiler)
    view.setProperty("kopier_menue", True)
    return view


def isk(n, suffix=True):
    if n is None:
        return "—"
    s = f"{round(n):,}".replace(",", "'")
    return s + " ISK" if suffix else s



class NumericItem(QTableWidgetItem):
    """Table cell that sorts by a numeric value but displays formatted text."""
    def __init__(self, text, value):
        super().__init__(text)
        self._value = value if value is not None else float("-inf")

    def __lt__(self, other):
        other_val = getattr(other, "_value", None)
        if other_val is not None:
            return self._value < other_val
        # Zellentyp-Mismatch (z.B. eine normale QTableWidgetItem in derselben
        # Spalte) - NIE super().__lt__() aufrufen: das kann in PySide6 bei
        # gemischten Zelltypen in einer sortierten Spalte unbegrenzt rekursiv
        # zurück in genau dieses __lt__ springen -> Stack overflow/Absturz.
        # Text-Vergleich ist immer sicher (keine Rekursion möglich).
        return self.text() < other.text()


class IskMillionSpin(QDoubleSpinBox):
    """Value is held in MILLIONS of ISK, but displayed human-readably:
    850 → '850M', 1000 → '1B', 1150 → '1,15B'. Accepts typing with M/B too."""
    def textFromValue(self, v):
        if v >= 1000:
            s = f"{v / 1000:.2f}".rstrip("0").rstrip(".").replace(".", ",")
            return f"{s}B"
        return f"{v:.0f}M"

    def valueFromText(self, text):
        t = text.strip().upper().replace(" ", "").replace(",", ".")
        try:
            if t.endswith("B"):
                return float(t[:-1]) * 1000.0
            if t.endswith("M"):
                return float(t[:-1])
            return float(t)
        except ValueError:
            return self.value()

    def validate(self, text, pos):
        from PySide6.QtGui import QValidator
        return (QValidator.Acceptable, text, pos)


class IskGroupedSpin(QSpinBox):
    """Plain-ISK integer spin box with apostrophe thousand separators
    (50000 -> '50'000'), so it stays readable without switching to M/B."""
    def textFromValue(self, v):
        return f"{v:,}".replace(",", "'")

    def _plain(self, text):
        """Angezeigten Text -> reine Ziffernfolge. Muss Prefix UND Suffix
        abraeumen: im Eingabefeld steht immer die volle Anzeige (z.B.
        "445 ISK/m3"), nicht nur die Zahl."""
        t = text or ""
        _p, _s = self.prefix(), self.suffix()
        if _p and t.startswith(_p):
            t = t[len(_p):]
        if _s and t.endswith(_s):
            t = t[:-len(_s)]
        return t.strip().replace("'", "").replace("\u2019", "").replace(" ", "")

    def validate(self, text, pos):
        """MUSSTE ueberschrieben werden (Nutzer: "kann bei Frachtdienst nicht
        mehr als 10 ISK eingeben, springt nach Enter zurueck"). Die Klasse
        SCHREIBT Werte mit Tausender-Apostroph (textFromValue), der geerbte
        Pruefer von QSpinBox kennt dieses Trennzeichen aber nicht und wies
        genau das Format als ungueltig zurueck, das die Box selbst anzeigt -
        eine Zahl ab 1'000 liess sich dadurch gar nicht mehr bearbeiten.
        Zusammen mit dem Suffix im Feld landete jede Eingabe im
        Rueckfall "alten Wert behalten"."""
        from PySide6.QtGui import QValidator
        raw = self._plain(text)
        if raw in ("", "+", "-"):
            return (QValidator.Intermediate, text, pos)   # noch am Tippen
        if not raw.lstrip("+-").isdigit():
            return (QValidator.Invalid, text, pos)
        return ((QValidator.Acceptable
                 if self.minimum() <= int(raw) <= self.maximum()
                 else QValidator.Intermediate), text, pos)

    def valueFromText(self, text):
        try:
            return int(round(float(self._plain(text))))
        except ValueError:
            return self.value()


class ZahlVorneSpin(IskGroupedSpin):
    """ISK-Feld, das die Zahl VORNE nimmt und den Rest ignoriert.

    Nutzer 29.09.2026 tippte "335isk/m3" ins Fracht-Feld. Die geerbte
    Pruefung weist jeden Buchstaben einzeln ab - die "3" aus "m3" aber
    nicht: heraus kam 3'353 statt 335 (nachgestellt). Hier zaehlt nur die
    fuehrende Ziffernfolge; was danach kommt ("isk/m3", " ISK"), faellt weg.
    """
    def _vorne(self, text):
        import re
        m = re.match(r"\s*\+?(\d+)", self._plain(text))
        return int(m.group(1)) if m else None

    def validate(self, text, pos):
        from PySide6.QtGui import QValidator
        raw = self._plain(text)
        if raw in ("", "+"):
            return (QValidator.Intermediate, text, pos)
        z = self._vorne(text)
        if z is None:
            return (QValidator.Invalid, text, pos)
        return ((QValidator.Acceptable if self.minimum() <= z <= self.maximum()
                 else QValidator.Intermediate), text, pos)

    def valueFromText(self, text):
        z = self._vorne(text)
        return z if z is not None else self.value()


class MinimizableDialog(QDialog):
    """Plain QDialog zeigt standardmäßig NUR einen Schließen-Button in der
    Titelleiste, kein Minimieren - man kann so ein offenes Bauplan-/Optimierer-/
    Kalender-Fenster nicht kurz wegklicken, ohne es zu schließen. Diese
    Basisklasse erzwingt den Minimieren-Button für ALLE Werkzeug-Dialoge im
    Tool, damit man z.B. kurz ins Spiel wechseln kann, ohne den Bauplan-Dialog
    zu verlieren."""
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        # WICHTIG: KEIN Qt.CustomizeWindowHint (siehe vorheriger Versuch - das
        # hat auf manchen Windows-Systemen zu einem KOMPLETT rahmenlosen
        # Fenster geführt). Aber auch nur Qt.WindowMinimizeButtonHint auf die
        # bestehenden Flags draufzupacken reichte NICHT: der Fenstertyp bleibt
        # dabei Qt.Dialog, und Qt.Dialog-Fenster unterstützen unter Windows
        # das Minimieren strukturell oft gar nicht zuverlässig, egal welche
        # Zusatz-Hints gesetzt sind. Deshalb jetzt der Fenstertyp selbst
        # explizit auf Qt.Window umgestellt (normales Top-Level-Fenster,
        # kein Dialog-Typ mehr) - dafür sind Minimieren/Maximieren/Verschieben
        # von Haus aus vorgesehen.
        flags = self.windowFlags()
        flags &= ~Qt.WindowType_Mask
        flags |= Qt.Window
        flags |= Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
        self.setWindowFlags(flags)

    # ENTER DRUECKT KEINEN KNOPF (emm312, Nutzer 01.10.2026: "nur bei einem
    # Endprodukt die Anzahl geaendert und Enter gedrueckt" -> Reset-Frage).
    # Ein Zahlenfeld reicht Enter an das Fenster weiter, und ein QDialog
    # drueckt dann seinen ersten Knopf - im Bauplan ist das "Reset". Wer das
    # will, setzt `enter_ohne_knopf = True` (der Bauplan tut es); das Feld
    # selbst hat den Wert dann schon uebernommen.
    enter_ohne_knopf = False

    def keyPressEvent(self, event):
        if (self.enter_ohne_knopf
                and event.key() in (Qt.Key_Return, Qt.Key_Enter)):
            event.accept()
            return
        super().keyPressEvent(event)
