"""Entry point: python -m eve_trader  (or the built .exe)."""
import datetime as dt
import os
import sys
import traceback

from PySide6.QtCore import QLocale, QObject, QEvent, Qt
from PySide6.QtWidgets import QApplication, QMessageBox, QDialog, QPushButton

from .ui.main_window import MainWindow
from .ui import theme
from . import config


class _HandCursor(QObject):
    """Gibt JEDEM Button beim Überfahren einen Zeigefinger-Cursor – app-weit,
    auch für dynamisch erzeugte Buttons (Zellen-Buttons, Dialoge). So muss das
    nicht an jedem Button einzeln gesetzt werden."""
    def eventFilter(self, obj, event):
        try:
            if event.type() == QEvent.Enter and isinstance(obj, QPushButton):
                if obj.isEnabled() and obj.cursor().shape() != Qt.PointingHandCursor:
                    obj.setCursor(Qt.PointingHandCursor)
        except Exception:
            pass
        return False


class _DialogClamp(QObject):
    """Keeps every dialog fully inside the visible screen. Fixes dialogs that
    would otherwise open partly/entirely off-screen on some setups (they look
    like they 'disappeared')."""
    def eventFilter(self, obj, event):
        try:
            if event.type() == QEvent.Show and isinstance(obj, QDialog):
                self._clamp(obj)
        except Exception:
            pass
        return False

    @staticmethod
    def _clamp(dlg):
        from PySide6.QtGui import QGuiApplication
        scr = dlg.screen() or QGuiApplication.primaryScreen()
        if not scr:
            return
        avail = scr.availableGeometry()
        g = dlg.frameGeometry()
        x, y, moved = g.left(), g.top(), False
        if g.width() <= avail.width() and g.right() > avail.right():
            x = avail.right() - g.width(); moved = True
        if g.height() <= avail.height() and g.bottom() > avail.bottom():
            y = avail.bottom() - g.height(); moved = True
        if x < avail.left():
            x = avail.left(); moved = True
        if y < avail.top():
            y = avail.top(); moved = True
        if moved:
            dlg.move(x, y)


def _crash_log_path():
    try:
        d = config.app_data_dir()
    except Exception:
        d = os.path.expanduser("~")
    return os.path.join(d, "motor_market_crash.log")


def _install_excepthook(app):
    """Log any unhandled exception to a file and show it, instead of silently
    closing the window."""
    def hook(exc_type, exc, tb):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        path = _crash_log_path()
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"\n===== {dt.datetime.now():%Y-%m-%d %H:%M:%S} =====\n")
                f.write(text)
        except Exception:
            pass
        try:
            # UEBERSETZT (Sitzung 16, Nutzer: "jedes noch so einzelne deutsche
            # Wort, das sichtbar ist"). Der Import steht HIER und nicht am
            # Dateikopf: der Hook laeuft auch dann, wenn beim Start selbst
            # etwas schiefging - dann soll ein kaputtes sprache-Modul den
            # Fehlerdialog nicht gleich mit reissen. Faellt der Import, bleibt
            # der englische Text.
            try:
                from .sprache import t as _t
            except Exception:
                def _t(x):
                    return x
            box = QMessageBox()
            box.setIcon(QMessageBox.Critical)
            box.setWindowTitle(_t("Error"))
            box.setText(_t("An error occurred \u2013 the app keeps running.\n\n"
                           "Details were saved to:").rstrip() + f"\n{path}")
            box.setDetailedText(text)
            box.exec()
        except Exception:
            pass
    sys.excepthook = hook


def main():
    # Consistent High-DPI behaviour BEFORE the QApplication exists. Without this,
    # Qt can suddenly re-round the scale factor on DPI events (e.g. when a window
    # is moved or a screen changes), which shows up as "everything suddenly tiny"
    # or huge. PassThrough keeps the OS scale factor as-is (crisp at 100 %).
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QGuiApplication
    try:
        QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    except Exception:
        pass
    app = QApplication(sys.argv)
    _install_excepthook(app)
    # SPRACHE VOR DEM FENSTERBAU SETZEN (Sitzung 12). Die Beschriftungen
    # entstehen beim Erzeugen der Widgets - wer die Sprache erst danach
    # setzt, sieht sie erst beim naechsten Start. Standard ist ENGLISCH:
    # das Spiel ist es, die Item-Namen sind es, und ein fremder Nutzer
    # kann mit einer deutschen Oberflaeche nichts anfangen.
    try:
        from . import config as _cfg_sprache, sprache as _sprache
        _sprache.sprache_setzen(
            (_cfg_sprache.load_settings() or {}).get("sprache", "en"))
    except Exception:
        pass          # ohne Einstellung bleibt es bei Englisch
    # Swiss German uses the apostrophe as thousands separator (12'234), which
    # reads much clearer than a dot. Applies to all spin boxes / number inputs.
    swiss = QLocale(QLocale.German, QLocale.Switzerland)
    QLocale.setDefault(swiss)
    # Eigene Schriften aus assets/fonts registrieren (falls vorhanden) -
    # MUSS vor setStyleSheet laufen, weil der Loader die Schrift-Kette im
    # QSS anpasst. Ohne eigene Dateien bleibt es bei Bahnschrift.
    try:
        theme.load_custom_fonts()
    except Exception:
        pass          # eine kaputte Schriftdatei darf den Start nicht killen
    # ORT 3: anwendungsweites Symbol - greift auch fuer Fenster, die VOR
    # dem Hauptfenster erscheinen (Einrichtungs-Assistent, Fehlerdialoge).
    try:
        from eve_trader.ui import icons as _ic
        app.setWindowIcon(_ic.logo_icon())
    except Exception:
        pass
    # ORT 4: TASKLEISTE (Nutzer 18.09.2026: "ich glaube das Logo erscheint
    # nicht in der Taskleiste"). Windows gruppiert Fenster nach der
    # AppUserModelID des PROZESSES - bei `python main.py` ist das python.exe,
    # und die Taskleiste zeigt dann das Python-Symbol, egal was Qt am
    # Fenster setzt. Eine eigene ID vor dem ersten Fenster loest das; fuer
    # die EXE ist sie zusaetzlich die Klammer fuer angeheftete Verknuepfungen.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "PeanutMotor.EVEMotorMarket")
        except Exception:
            pass
    app.setStyleSheet(theme.QSS)
    # ALLE TOOLTIPS GLEICH (Sitzung 20) - vor dem Hauptfenster, damit jeder
    # setToolTip im Aufbau schon durch die eine Stelle laeuft.
    from eve_trader.ui import tooltips as _tt
    _tt.aktivieren()
    app._dialog_clamp = _DialogClamp()      # keep a reference so it isn't GC'd
    app.installEventFilter(app._dialog_clamp)
    app._hand_cursor = _HandCursor()        # pointing-hand cursor on every button
    app.installEventFilter(app._hand_cursor)
    from . import ladezeit as _lz
    _lz.ui_zwischenzeit("Qt, language, fonts, style ready")
    win = MainWindow()
    _lz.ui_zwischenzeit("main window built")
    win.show()
    _lz.ui_zwischenzeit("window shown")
    if _lz.AN and _lz.ui_laeuft():
        # STARTMESSUNG ENDET, wenn das Fenster zum ersten Mal gezeichnet ist
        # und die Ereignisschleife laeuft - das ist die Wartezeit, die der
        # Nutzer beim Oeffnen spuert. Was danach im Hintergrund nachlaedt,
        # messen die Job-Berichte einzeln.
        from PySide6.QtCore import QTimer as _QT_lz

        def _start_fertig():
            _lz.ui_zwischenzeit("first screen drawn")
            _lz.ui_stop()
        _QT_lz.singleShot(0, _start_fertig)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
