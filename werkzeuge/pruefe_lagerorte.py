"""WOHER KOMMT JEDER ORT IN "STOCK LOCATIONS"? (emm906)

WOZU: Nutzer 13.11.2026 mit Bildschirmfoto - "Stock Locations sind
einfach neu voellig zufaellig Stationen hinzugefuegt worden. das will ich
so nicht". 29 Orte standen in der Liste, 15 davon abgeschaltet, und
darunter Stationen quer durch New Eden (Thera, Amarr, Amamake, mehrere
Nullsec-Strukturen) sowie zweimal "Structure (no docking access)".

DIE LISTE IST KEINE EINSTELLUNG: `lagerorte.orte_mit_bestand` nimmt
schlicht JEDEN Ort, an dem irgendetwas liegt. "Hinzugefuegt" werden
Orte also nie - sie tauchen auf, weil dort etwas liegt. Die Frage ist
damit nicht "wer hat die eingetragen", sondern **WAS liegt dort, von
WEM, und AUS WELCHER QUELLE**. Genau das beantwortet dieser Bericht, je
Ort:
  * Stueckzahl und Zahl der Stapel,
  * je Charakter aufgeschluesselt,
  * QUELLE: eigener Hangar (Assets), Corp-Hangar, oder offener Vertrag
    (seit emm760 zaehlt Vertragsmaterial mit, und zwar am START-Ort des
    Vertrags - ein Kurier-Vertrag bringt so Stationen herein, in denen
    nie etwas gelagert wurde),
  * ob der Ort gerade EIN- oder AUSGESCHALTET ist.

NUR LESEN: ausser den ESI-Abfragen aendert dieser Bericht nichts; die
Einstellungen werden roh gelesen (wie in `zeige_lagerorte.py`, und aus
demselben Grund: `config.load_settings()` fuehrt Migrationen aus und
SCHREIBT dabei).

ORTSNAMEN: nur aus bekannten Quellen (Bau-Strukturen, gemerkte Namen,
NPC-Stationen). KEIN `resolve_structure` - das kostet bei fehlendem
Andockrecht 403er aufs ESI-Fehlerbudget (emm462). Ein Ort ohne Namen
steht mit seiner Nummer da, und das genuegt zum Wiedererkennen.

AUFRUF: werkzeuge\\pruefe_lagerorte.bat doppelklicken, danach
`berichte\\lagerorte_quelle.txt` hochladen.
"""
import os
import sys
import time

_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _WURZEL)

from eve_trader import (config, corp, esi, lagerorte,   # noqa: E402
                        store, vertraege)

FASSUNG = 1


def _z(n):
    return f"{int(n):,}".replace(",", "'")


def _settings_rohe():
    """settings.json ROH lesen - OHNE `config.load_settings()`.

    Derselbe Grund wie in `zeige_lagerorte.py`: `load_settings` fuehrt
    Migrationen aus und schreibt dabei die Datei. Dieser Bericht sagt im
    Kopf zu, nichts zu veraendern.
    """
    data = dict(config.DEFAULT_SETTINGS)
    try:
        import json as _j
        with open(config.settings_path(), encoding="utf-8") as fh:
            data.update(_j.load(fh) or {})
    except Exception:
        data = config.load_settings() or {}
        data["_ueber_load_settings"] = True
    return data


def _ort_namen(settings, orte):
    """Nur BEKANNTE Quellen - siehe Modulkopf (kein resolve_structure)."""
    namen = {}
    for bs in (settings.get("bau_structures") or []):
        sid = bs.get("link_structure_id")
        if sid and bs.get("name"):
            try:
                namen[int(sid)] = str(bs["name"])
            except (TypeError, ValueError):
                continue
    for k, v in (settings.get("lager_ort_namen") or {}).items():
        try:
            if v:
                namen.setdefault(int(k), str(v))
        except (TypeError, ValueError):
            continue
    stationen = [o for o in orte if o not in namen and 0 < o < 2 ** 31]
    if stationen:
        try:
            namen.update(esi.orts_namen(stationen) or {})
        except Exception:
            pass
    return namen


def main():
    aus = []

    def p(s=""):
        aus.append(s)
        print(s)

    p("=" * 78)
    p(f"STOCK LOCATIONS - WOHER KOMMT JEDER ORT? (Fassung {FASSUNG})")
    p(f"Erstellt: {time.strftime('%d.%m.%Y %H:%M:%S')}")
    p("=" * 78)
    p("")

    settings = _settings_rohe()
    if settings.get("_ueber_load_settings"):
        p("HINWEIS: settings.json war nicht direkt lesbar - gelesen ueber")
        p("den normalen Weg des Programms (der fuehrt Migrationen aus).")
        p("")
    client_id = settings.get("client_id") or config.EMBEDDED_CLIENT_ID
    try:
        chars = store.list_characters()
    except Exception as e:
        p(f"DATENBANK NICHT LESBAR: {type(e).__name__}: {e}")
        _schreiben(aus)
        return 1

    try:
        ctypes = esi.container_type_ids_safe()
    except Exception:
        ctypes = set()

    # ---- 1. ASSETS JE CHARAKTER ----------------------------------------
    # quelle: {(ort, quelle, wer): [stapel, stueck]}
    quelle = {}
    fehler = []
    char_namen = {}

    def _buchen(ort, q, wer, zeilen):
        _s = quelle.setdefault((int(ort or 0), q, wer), [0, 0])
        for _z0 in zeilen:
            _s[0] += 1
            _s[1] += int(_z0.get("menge") or 0)

    for ch in chars:
        cid = int(ch["character_id"])
        nm = ch.get("character_name") or ch.get("name") or str(cid)
        char_namen[cid] = nm
        try:
            assets = esi._fetch_all_assets(client_id, cid)
        except Exception as e:
            fehler.append(f"Assets {nm}: {type(e).__name__}: {e}")
            continue
        _zn = lagerorte.zeilen_aus_assets(assets, ctypes, cid, "char")
        _je_ort = {}
        for _z0 in _zn:
            _je_ort.setdefault(int(_z0.get("ort") or 0), []).append(_z0)
        for _o, _lst in _je_ort.items():
            _buchen(_o, "Hangar", nm, _lst)

    # ---- 2. CORP-HANGAR ------------------------------------------------
    if settings.get("use_corp"):
        # DERSELBE WEG WIE IN MoMa UND IN zeige_lagerorte.py (Regel 9):
        # `corp.abrufplan` waehlt EINEN Charakter je Corporation - sonst
        # liefert ESI denselben Hangar mehrfach und der Bericht zaehlte
        # doppelt.
        divs = corp.divisions_bereinigt(settings.get("corp_divisions"))
        corp_von, rollen_von = {}, {}
        for ch in chars:
            cid = int(ch["character_id"])
            try:
                corp_von[cid] = esi.fetch_character_corporation(cid)
                rollen_von[cid] = esi.fetch_character_roles(client_id, cid)
            except Exception as e:
                fehler.append(f"Corp-Rollen {char_namen.get(cid, cid)}: "
                              f"{type(e).__name__}: {e}")
                rollen_von[cid] = None
        _plan, _ = corp.abrufplan(chars, corp_von, rollen_von,
                                  corp.ROLLE_ASSETS)
        for _corp_id, _via in sorted(_plan.items()):
            try:
                _cname = esi.fetch_corporation_name(_corp_id)
            except Exception:
                _cname = f"#{_corp_id}"
            try:
                _ca = esi.fetch_corporation_assets(client_id, _via, _corp_id)
            except Exception as e:
                fehler.append(f"Corp {_cname}: {type(e).__name__}: {e}")
                continue
            _zc = lagerorte.zeilen_aus_assets(
                _ca, ctypes, int(_corp_id), "corp", divisions=divs)
            _je_ort = {}
            for _z0 in _zc:
                _je_ort.setdefault(int(_z0.get("ort") or 0), []).append(_z0)
            for _o, _lst in _je_ort.items():
                _buchen(_o, "Corp-Hangar", f"Corp: {_cname}", _lst)

    # ---- 3. OFFENE VERTRAEGE (emm760) ----------------------------------
    # DER WAHRSCHEINLICHSTE GRUND fuer fremd wirkende Orte: gezaehlt wird
    # am START-Ort des Vertrags.
    _v_listen, _v_scope_fehlt = [], []
    for ch in chars:
        cid = int(ch["character_id"])
        nm = char_namen.get(cid, str(cid))
        try:
            _sc = esi.granted_scopes(client_id, cid) or set()
        except Exception:
            _sc = set()
        if config.CONTRACTS_SCOPE not in _sc:
            _v_scope_fehlt.append(nm)
            continue
        try:
            _v_listen.append(esi.fetch_character_contracts(client_id, cid)
                             or [])
        except Exception as e:
            fehler.append(f"Vertraege {nm}: {type(e).__name__}: {e}")
    _eigene = [int(c["character_id"]) for c in chars]
    _offen = {k: v for k, v in vertraege.offene_vertraege(_v_listen).items()
              if vertraege.beteiligte(v, _eigene) == "aussteller"}
    _items = {}
    for _vid, _v in sorted(_offen.items()):
        try:
            _items[_vid] = esi.fetch_character_contract_items(
                client_id, int(_v.get("issuer_id") or 0), _vid)
        except Exception as e:
            _items[_vid] = None
            fehler.append(f"Vertrags-Posten #{_vid}: {type(e).__name__}: {e}")
    _vz, _benutzt = vertraege.lager_zeilen(_offen, _items)
    _vertrag_info = {}          # ort -> [Beschreibung je Vertrag]
    for _vid, _v in _benutzt.items():
        _o = int(_v.get("start_location_id") or 0)
        _iss = char_namen.get(int(_v.get("issuer_id") or 0), "?")
        _typ = str(_v.get("type") or "")
        _vertrag_info.setdefault(_o, []).append(
            f"#{_vid} ({_typ or 'item_exchange'}) von {_iss}")
    _je_ort = {}
    for _z0 in _vz:
        _je_ort.setdefault(int(_z0.get("ort") or 0), []).append(_z0)
    for _o, _lst in _je_ort.items():
        _buchen(_o, "Vertrag", "offener Vertrag", _lst)

    # ---- 4. AUSWERTUNG --------------------------------------------------
    _orte = sorted({o for o, _q, _w in quelle})
    namen = _ort_namen(settings, _orte)
    _aus_ids = {str(x) for x in (settings.get("lager_orte_aus") or [])}
    _bekannt = settings.get("lager_orte_bekannt")

    _summe = {}
    for (_o, _q, _w), (_st, _mg) in quelle.items():
        _s = _summe.setdefault(_o, [0, 0])
        _s[0] += _st
        _s[1] += _mg

    p(f"Verlinkte Charaktere: {len(chars)}")
    p(f"Orte mit Bestand:     {len(_orte)}")
    p(f"davon ausgeschaltet:  {len([o for o in _orte if str(o) in _aus_ids])}")
    p(f"Offene eigene Vertraege: {len(_offen)}"
      + (f"  (Posten gezaehlt bei {len(_benutzt)})" if _benutzt else ""))
    if _bekannt is None:
        p("Neue-Orte-Merker (emm905): NOCH NICHT angelegt - beim naechsten")
        p("  Aufbau in MoMa wird der IST-Zustand gemerkt, nichts geschaltet.")
    else:
        p(f"Neue-Orte-Merker (emm905): {len(_bekannt)} Orte bekannt")
    if _v_scope_fehlt:
        p(f"Ohne Vertrags-Scope (nicht gezaehlt): "
          f"{', '.join(sorted(set(_v_scope_fehlt)))}")
    p("")

    p("=" * 78)
    p("JE ORT - GROESSTER ZUERST")
    p("=" * 78)
    for _o in sorted(_orte, key=lambda x: -_summe[x][1]):
        _nm = namen.get(_o) or (f"#{_o}" if _o else
                                "(kein Ort - Vertrag ohne Startort)")
        _an = "AUS" if str(_o) in _aus_ids else "AN "
        _st, _mg = _summe[_o]
        p("")
        p(f"[{_an}] {_nm}")
        p(f"       {_z(_mg)} Stueck in {_z(_st)} Stapel   (ID {_o})")
        for (_oo, _q, _w), (_s2, _m2) in sorted(
                quelle.items(), key=lambda kv: -kv[1][1]):
            if _oo != _o:
                continue
            p(f"       - {_q:<12} {_w:<24} {_z(_m2):>14} Stueck / "
              f"{_z(_s2)} Stapel")
        for _info in _vertrag_info.get(_o, []):
            p(f"         Vertrag: {_info}")
    p("")

    # ---- 5. WAS DAVON IST "FREMD"? -------------------------------------
    # Die Frage des Nutzers war, warum Orte auftauchen, an denen er nie
    # etwas gelagert hat. Zwei Gruppen beantworten das direkt.
    p("=" * 78)
    p("ORTE, DIE NUR AUS VERTRAEGEN KOMMEN")
    p("=" * 78)
    _nur_v = [o for o in _orte
              if all(_q == "Vertrag" for (_oo, _q, _w) in quelle if _oo == o)]
    if _nur_v:
        p("An diesen Orten liegt NICHTS in deinem Hangar - sie stehen nur")
        p("in der Liste, weil dort ein offener Vertrag startet (emm760).")
        for _o in _nur_v:
            p(f"  {namen.get(_o) or ('#' + str(_o))}  "
              f"({_z(_summe[_o][1])} Stueck)")
    else:
        p("Keine - jeder Ort hat auch eigenen Hangar-Bestand.")
    p("")
    p("=" * 78)
    p("KLEINE ORTE (unter 1'000 Stueck)")
    p("=" * 78)
    p("Hier liegen meist Reste - genau die Orte, die eine Liste zumuellen.")
    _klein = [o for o in _orte if _summe[o][1] < 1000]
    for _o in sorted(_klein, key=lambda x: _summe[x][1]):
        p(f"  {_z(_summe[_o][1]):>8} Stueck  "
          f"{namen.get(_o) or ('#' + str(_o))}")
    p(f"  --> {len(_klein)} von {len(_orte)} Orten")
    p("")

    if fehler:
        p("=" * 78)
        p("FEHLER (unvollstaendige Daten - bitte mitschicken)")
        p("=" * 78)
        for f in fehler:
            p(f"  {f}")
        p("")
    _schreiben(aus)
    return 0


def _schreiben(zeilen):
    os.makedirs(os.path.join(_WURZEL, "berichte"), exist_ok=True)
    with open(os.path.join(_WURZEL, "berichte", "lagerorte_quelle.txt"),
              "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")


if __name__ == "__main__":
    sys.exit(main())
