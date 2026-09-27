"""Run from source:  python main.py"""
import os
import sys
import traceback
import datetime


def _log_path():
    """Wohin das Fehlerprotokoll GESCHRIEBEN WUERDE - ohne es anzulegen.

    Nutzer-Frage: "welches Konsolenfenster?" - berechtigt. Wer das Tool per
    Doppelklick startet, sieht NIE einen Traceback; ein Fehler aeussert sich
    dann nur als halb gefuellte Tabelle. Ohne Protokoll ist jede Ferndiagnose
    Raten (in einer Session zweimal danebengelegen, genau deswegen).

    ANGELEGT WIRD DIE DATEI ERST IM FEHLERFALL (Sitzung 11). Vorher legte
    schon der Start eine leere Datei an, damit der Schreibzugriff geprueft
    ist. Fuer den Entwickler egal - fuer einen fremden Nutzer steht dann
    nach dem ersten Start eine Datei namens "fehler" neben dem Programm,
    und er fragt sich, was schiefgegangen ist. Nichts ist schiefgegangen.
    Eine leere Fehlerdatei ist eine Behauptung, die nicht stimmt.
    """
    base = os.path.dirname(os.path.abspath(sys.argv[0])) or os.getcwd()
    return os.path.join(base, "fehler.log")


def _rueckfall_pfad():
    """Wenn neben der Anwendung nicht geschrieben werden darf (z. B. bei
    einer Installation in einen geschuetzten Ordner), landet das Protokoll
    im Benutzerverzeichnis - lieber dort als gar nicht."""
    return os.path.join(os.path.expanduser("~"), "motor_market_fehler.log")


def _install_error_log():
    """Jede unbehandelte Ausnahme ins Protokoll schreiben - und trotzdem
    weiterlaufen lassen, wie Qt es ohnehin tut."""
    path = _log_path()
    _prev = sys.excepthook

    def hook(exc_type, exc, tb):
        for _ziel in (path, _rueckfall_pfad()):
            try:
                with open(_ziel, "a", encoding="utf-8") as fh:
                    fh.write("\n" + "=" * 70 + "\n")
                    fh.write(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                             + "\n")
                    traceback.print_exception(exc_type, exc, tb, file=fh)
                break
            except Exception:
                continue      # naechstes Ziel versuchen
        try:
            _prev(exc_type, exc, tb)
        except Exception:
            pass
    sys.excepthook = hook
    return path


if __name__ == "__main__":
    # STARTZEIT MESSEN (Nutzer 27.09.2026: "vor allem das erste Laden beim
    # Oeffnen des Tools dauert"). Nur mit EMM_LADEZEIT=1, sonst nichts.
    if os.environ.get("EMM_LADEZEIT") == "1":
        from eve_trader import ladezeit as _lz
        _lz.ui_start("start of Eve MoMa")
    _p = _install_error_log()
    print(f"Fehlerprotokoll: {_p}")
    from eve_trader.__main__ import main
    if os.environ.get("EMM_LADEZEIT") == "1":
        _lz.ui_zwischenzeit("modules loaded")
    main()
