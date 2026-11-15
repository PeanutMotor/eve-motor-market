"""SYSTEMWEITES TASTENKUERZEL (emm901).

WOZU: Nutzer 12.11.2026 - "in Order update den 'next' button einer Taste
zuweisen also rechtsklick auf den 'next button' und dann kann man da eine
Taste wie bsp 'b' zuweisen, wenn man dann b drueckt waehrend MoMa im
hintergrund offen ist, wird der next button verwendet und das naechste
markt Item geht auf".

"WAEHREND MOMA IM HINTERGRUND OFFEN IST" ist der ganze Punkt - und genau
das kann Qt nicht. Ein `QShortcut` braucht den Tastaturfokus; sobald EVE
vorne ist, bekommt MoMa keine Tastendruecke mehr. Dafuer gibt es unter
Windows `RegisterHotKey`: das Betriebssystem schickt die Taste an unser
Fenster, egal welches Programm vorne ist.

WAS DAS KOSTET, offen gesagt: eine so registrierte Taste gehoert MoMa
ALLEIN, solange MoMa laeuft. Bei einer nackten Taste ("b") heisst das: im
EVE-Chat, im Browser, ueberall kommt dieses "b" nicht mehr an. Mit
Zusatztaste (Strg+B) ist die Gefahr praktisch weg. Der Nutzer hat am
12.11.2026 entschieden, BEIDES zu erlauben und beim Zuweisen zu warnen.

NUR WINDOWS: `registrieren` gibt auf jedem anderen System einen Grund
zurueck statt zu scheitern. Dieses Modul laeuft darum auch unter Linux
durch (die Testsuiten) - nur die Registrierung selbst tut dort nichts.

WARUM EIGENES MODUL: `zerlege` und `teile` sind reine Textarbeit und
damit ohne Fenster, ohne Qt und ohne Windows pruefbar. Genau dort sitzen
die Fehler, die man sonst erst beim Nutzer sieht (falsche VK-Nummer,
Zusatztaste verschluckt).
"""
import sys

# ---- die Zahlen von Windows (user32) --------------------------------------
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
# MOD_NOREPEAT: ein gehaltener Knopf loest EINMAL aus, nicht dauernd.
# Ohne das wuerde ein versehentlich liegengebliebener Finger die ganze
# Orderliste durchblaettern.
MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312

# Eigene Kennung je Kuerzel. Beliebig, muss nur innerhalb des Prozesses
# eindeutig sein.
ID_ORD_NEXT = 0xB901

_MODS = (("Ctrl", MOD_CONTROL), ("Alt", MOD_ALT),
         ("Shift", MOD_SHIFT), ("Win", MOD_WIN))


def teile(text):
    """"Ctrl+Shift+B" -> (["Ctrl", "Shift"], "B").

    Reine Textarbeit, keine Pruefung auf Gueltigkeit - dafuer ist
    `zerlege` da. Die Reihenfolge der Zusatztasten wird vereinheitlicht
    (Ctrl, Alt, Shift, Win), damit "Shift+Ctrl+B" und "Ctrl+Shift+B"
    nicht als zwei verschiedene Kuerzel in den Einstellungen landen.
    """
    _roh = [_s.strip() for _s in str(text or "").split("+") if _s.strip()]
    if not _roh:
        return [], ""
    _klein = {_s.lower() for _s in _roh[:-1]}
    _mods = [_n for _n, _ in _MODS if _n.lower() in _klein]
    return _mods, _roh[-1].upper()


def normal(text):
    """Die Schreibweise, die in den Einstellungen landet: "Ctrl+B"."""
    _mods, _taste = teile(text)
    if not _taste:
        return ""
    return "+".join(_mods + [_taste])


def ist_nackt(text):
    """Taste OHNE Zusatztaste? Die ist gefaehrlich (siehe Modulkopf)."""
    _mods, _taste = teile(text)
    return bool(_taste) and not _mods


def zerlege(text):
    """"Ctrl+B" -> (MOD_CONTROL | MOD_NOREPEAT, 0x42).

    Rueckgabe (None, None), wenn die Taste nicht unterstuetzt wird. Erlaubt
    sind A-Z, 0-9 und F1-F12 - das deckt den Fall des Nutzers ab, und jede
    weitere Taste waere eine VK-Tabelle, die niemand nachprueft. Lieber
    eine klare Absage im Zuweis-Fenster als eine stille Falschbelegung.
    """
    _mods, _taste = teile(text)
    _m = MOD_NOREPEAT
    for _name, _wert in _MODS:
        if _name in _mods:
            _m |= _wert
    if len(_taste) == 1 and ("A" <= _taste <= "Z" or "0" <= _taste <= "9"):
        return _m, ord(_taste)          # VK_A..VK_Z / VK_0..VK_9 == ASCII
    if (len(_taste) in (2, 3) and _taste[0] == "F"
            and _taste[1:].isdigit() and 1 <= int(_taste[1:]) <= 12):
        return _m, 0x70 + int(_taste[1:]) - 1       # VK_F1 == 0x70
    return None, None


def moeglich():
    """Kann dieses System systemweite Kuerzel? (Nur Windows.)"""
    return sys.platform.startswith("win")


def registrieren(hwnd, kennung, text):
    """Kuerzel beim Betriebssystem anmelden.

    Rueckgabe (True, "") oder (False, grund). Der Grund ist fuer den
    Nutzer bestimmt - es gibt genau drei, die wirklich vorkommen:
    kein Windows, unbekannte Taste, oder ein anderes Programm hat das
    Kuerzel schon. Letzteres MUSS gemeldet werden: sonst glaubt der
    Nutzer, die Taste sei zugewiesen, und sie tut nie etwas.
    """
    if not moeglich():
        return False, "windows-only"
    _m, _vk = zerlege(text)
    if _vk is None:
        return False, "key-unknown"
    try:
        import ctypes
        if not ctypes.windll.user32.RegisterHotKey(
                int(hwnd), int(kennung), int(_m), int(_vk)):
            return False, "already-taken"
    except Exception as _e:                              # pragma: no cover
        return False, f"fehler: {_e}"
    return True, ""


def loesen(hwnd, kennung):
    """Kuerzel wieder freigeben. Nie laut - beim Beenden ist es egal."""
    if not moeglich():
        return False
    try:
        import ctypes
        return bool(ctypes.windll.user32.UnregisterHotKey(
            int(hwnd), int(kennung)))
    except Exception:                                    # pragma: no cover
        return False


def ist_hotkey_nachricht(event_type, message, kennung):
    """Ist diese Windows-Nachricht unser Kuerzel? (fuer `nativeEvent`)

    Qt gibt `message` als Zeiger auf eine MSG-Struktur. Wir lesen daraus
    nur `message` und `wParam` - mehr brauchen wir nicht, und jede
    weitere Annahme ueber das Speicherbild waere eine Fehlerquelle.
    """
    if not moeglich():
        return False
    if event_type not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
        return False
    try:
        import ctypes
        import ctypes.wintypes as _wt

        class _MSG(ctypes.Structure):
            _fields_ = [("hwnd", _wt.HWND), ("message", _wt.UINT),
                        ("wParam", _wt.WPARAM), ("lParam", _wt.LPARAM),
                        ("time", _wt.DWORD), ("pt", _wt.POINT)]

        _msg = ctypes.cast(int(message), ctypes.POINTER(_MSG)).contents
        return (_msg.message == WM_HOTKEY
                and int(_msg.wParam) == int(kennung))
    except Exception:                                    # pragma: no cover
        return False
