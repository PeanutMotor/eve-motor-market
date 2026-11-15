"""Refresh-token storage. Prefers the OS keyring (Windows Credential Manager).
Falls back to a local file if no keyring backend is available."""
import json
import os
import threading

from . import config

# EIN TOKEN-ZUGRIFF NACH DEM ANDEREN (emm869): seit emm866 laufen bis
# zu 4 Charaktere nebeneinander. Der Windows-Anmeldeinformations-
# speicher ist fuer parallele Zugriffe aus mehreren Threads nicht
# zugesagt, und die Fallback-Datei tokens.json waere bei zwei
# gleichzeitigen Schreibern schlicht kaputt. Das Lock serialisiert NUR
# die Token-Ablage - die ESI-Abrufe selbst bleiben parallel.
_LOCK = threading.Lock()

# SCHLUESSEL IM WINDOWS-ANMELDEINFORMATIONSSPEICHER.
# WIRD NICHT UMBENANNT, auch wenn das Programm inzwischen "EVE Motor Market"
# heisst (Sitzung 11). Unter diesem Namen liegen die Refresh-Token aller
# verknuepften Charaktere. Ein neuer Name findet die alten Eintraege nicht:
# beim naechsten Start waeren alle Charaktere abgemeldet und muessten von
# Hand neu verknuepft werden - bei jedem Nutzer, ohne Vorwarnung und ohne
# erkennbaren Grund. Der Name ist ein interner Schluessel, kein Anzeigename;
# sichtbar wird er nur, wenn jemand den Anmeldeinformationsspeicher oeffnet.
SERVICE = "EveTradeLedger"

try:
    import keyring
    _HAS_KEYRING = True
except Exception:
    _HAS_KEYRING = False

_FALLBACK = os.path.join(config.app_data_dir(), "tokens.json")


def _fallback_load() -> dict:
    if os.path.exists(_FALLBACK):
        try:
            with open(_FALLBACK, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _fallback_save(data: dict) -> None:
    with open(_FALLBACK, "w", encoding="utf-8") as f:
        json.dump(data, f)


def set_token(character_id: int, refresh_token: str) -> None:
    with _LOCK:
        if _HAS_KEYRING:
            keyring.set_password(SERVICE, str(character_id), refresh_token)
        else:
            data = _fallback_load()
            data[str(character_id)] = refresh_token
            _fallback_save(data)


def get_token(character_id: int):
    with _LOCK:
        if _HAS_KEYRING:
            return keyring.get_password(SERVICE, str(character_id))
        return _fallback_load().get(str(character_id))


def delete_token(character_id: int) -> None:
    with _LOCK:
        if _HAS_KEYRING:
            try:
                keyring.delete_password(SERVICE, str(character_id))
            except Exception:
                pass
        else:
            data = _fallback_load()
            data.pop(str(character_id), None)
            _fallback_save(data)
