"""Planetary Industry (PI): Daten holen und fuer die PI-Karten aufbereiten.

emm801, Discord-Wunsch 31.10.2026 (HashtagMoDSucks): "PI timers, most
definitely ... how much you have stored on a planet ... not only isk value,
but cargo space taken up ... see when your planets reset, what they're doing
and how much in terms of m3 is there".

AUFBAU: `karten_bauen` ist REINE RECHNUNG (bekommt fertige Rohdaten und
Nachschlagetabellen, kein Netz) - damit in tests/ ohne ESI pruefbar.
`pi_uebersicht` ist der eine Orchestrierungs-Einstieg fuer die Oberflaeche.

GRENZEN, OFFEN GESAGT STATT STILL FALSCH:
- POCO-Inhalte gibt ESI NICHT her (es gibt keinen Endpunkt dafuer) - die
  Uebersicht zeigt nur, was in den Kolonie-Pins liegt. Steht als Hinweis
  in der Oberflaeche.
- Die ISK-Spalte ist der serverweite CCP-Durchschnitt (esi.average_prices),
  KEIN Hub-Preis - die Anzeige sagt das in ihrer Hinweiszeile offen.
"""
import time
from datetime import datetime


def _iso_ts(s):
    """ESI-Zeitstempel ("2026-10-31T12:00:00Z") -> Unix-Sekunden, sonst None."""
    try:
        return datetime.fromisoformat(
            str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def rohdaten_holen(client_id, chars, granted=None):
    """Alle Kolonien aller verknuepften Charaktere von ESI.

    granted: optional {character_id: set(Scopes) | None} - Charaktere, deren
    Token config.PI_SCOPE nachweislich NICHT traegt, landen in `fehlt`
    (Neu-Verlinken noetig) statt einen 403 zu produzieren; None/unbekannt
    wird versucht.

    Rueckgabe (planeten, fehlt, fehler):
      planeten: [{char, char_id, planet_id, planet_type, upgrade_level,
                  detail (ESI-Pins/Routen), info ({name, type_id, system_id})}]
      fehlt:    [Charaktername] (Berechtigung fehlt)
      fehler:   ["Name: Fehlertext"] (Netz/ESI, je Vorfall einer)
    """
    from . import config, esi
    planeten, fehlt, fehler = [], [], []
    for ch in (chars or []):
        cid = int(ch["character_id"])
        name = ch.get("character_name") or str(cid)
        _sc = (granted or {}).get(cid)
        if _sc is not None and config.PI_SCOPE not in _sc:
            fehlt.append(name)
            continue
        try:
            kolonien = esi.fetch_planets(client_id, cid)
        except Exception as e:
            fehler.append(f"{name}: {type(e).__name__}: {str(e)[:120]}")
            continue
        for k in kolonien or []:
            pid = k.get("planet_id")
            if pid is None:
                continue
            try:
                detail = esi.fetch_planet_detail(client_id, cid, pid)
            except Exception as e:
                fehler.append(
                    f"{name}/{pid}: {type(e).__name__}: {str(e)[:120]}")
                continue
            try:
                info = esi.planet_info(pid)
            except Exception:
                info = {"name": str(pid), "type_id": None, "system_id": None}
            planeten.append({"char": name, "char_id": cid,
                             "planet_id": int(pid),
                             "planet_type": k.get("planet_type"),
                             "upgrade_level": k.get("upgrade_level"),
                             "detail": detail or {}, "info": info})
    return planeten, fehlt, fehler


def karten_bauen(planeten, namen=None, volumen=None, preise=None,
                 schemata=None, jetzt=None):
    """Rohdaten -> PI-Karten, eine je Kolonie. REINE RECHNUNG, kein Netz.

    namen:    {type_id: Name}     (esi.resolve_names)
    volumen:  {type_id: m3/Stk}   (industry.item_volume_map)
    preise:   {type_id: ISK/Stk}  (esi.average_prices - CCP-Durchschnitt)
    schemata: {schematic_id: Rezeptname} (esi.schematic_info)

    Pin-Einteilung OHNE hartcodierte Gebaeude-Listen (die type_ids der
    PI-Gebaeude stehen nicht verlaesslich in der Kompakt-SDE):
      extractor_details vorhanden -> Extraktor (expiry_time = Ablauf),
      schematic_id vorhanden      -> Fabrik,
      contents nicht leer         -> zaehlt zum Lager (auch Launchpad/
      Command Center/Extraktor mit Inhalt - das Zeug liegt wirklich dort).

    Karte: {char, char_id, planet_id, planet, planet_type, upgrade_level,
            extraktoren: [{produkt_tid, produkt, ende_ts, laeuft, je_stunde}],
            fabriken:    [{schematic_id, name, anzahl}],
            lager:       [{pin_tid, pin_name, m3, isk,
                           items: [{tid, name, menge, m3, isk}]}],
            m3_gesamt, isk_gesamt, naechster_ablauf_ts}
    Sortierung: Charakter, dann Planetname. naechster_ablauf_ts ist das
    FRUEHESTE Extraktor-Ende (auch wenn schon vorbei - genau das will man
    sehen); None, wenn kein Extraktor laeuft.
    """
    namen = namen or {}
    volumen = volumen or {}
    preise = preise or {}
    schemata = schemata or {}
    if jetzt is None:
        jetzt = time.time()
    karten = []
    for p in (planeten or []):
        pins = (p.get("detail") or {}).get("pins") or []
        extraktoren, lager = [], []
        fabrik_zahl = {}
        for pin in pins:
            ed = pin.get("extractor_details")
            if ed:
                _tid = ed.get("product_type_id")
                _ende = _iso_ts(pin.get("expiry_time"))
                # Foerderrate je Stunde aus Zyklus + Menge/Zyklus - das ist
                # das "what they're doing" aus dem Wunsch.
                _je_h = None
                try:
                    _ct = float(ed.get("cycle_time") or 0)
                    _qty = float(ed.get("qty_per_cycle") or 0)
                    if _ct > 0 and _qty > 0:
                        _je_h = _qty * 3600.0 / _ct
                except Exception:
                    _je_h = None
                extraktoren.append({
                    "produkt_tid": _tid,
                    "produkt": namen.get(int(_tid)) if _tid else None,
                    "ende_ts": _ende,
                    "laeuft": bool(_ende and _ende > jetzt),
                    "je_stunde": _je_h,
                })
            _sid = pin.get("schematic_id")
            if _sid:
                fabrik_zahl[int(_sid)] = fabrik_zahl.get(int(_sid), 0) + 1
            inhalt = pin.get("contents") or []
            if inhalt:
                _items = []
                for c in inhalt:
                    try:
                        _ctid = int(c.get("type_id"))
                        _menge = int(c.get("amount") or 0)
                    except (TypeError, ValueError):
                        continue
                    if _menge <= 0:
                        continue
                    _m3 = _menge * float(volumen.get(_ctid) or 0.0)
                    _isk = _menge * float(preise.get(_ctid) or 0.0)
                    _items.append({"tid": _ctid,
                                   "name": namen.get(_ctid) or str(_ctid),
                                   "menge": _menge, "m3": _m3, "isk": _isk})
                if _items:
                    # Groesstes zuerst - darum geht es dem Blick.
                    _items.sort(key=lambda i: (-i["m3"], -i["isk"], i["tid"]))
                    _ptid = pin.get("type_id")
                    try:
                        _ptid = int(_ptid)
                    except (TypeError, ValueError):
                        _ptid = None
                    lager.append({
                        "pin_tid": _ptid,
                        "pin_name": (namen.get(_ptid) or str(_ptid or "?")),
                        "m3": sum(i["m3"] for i in _items),
                        "isk": sum(i["isk"] for i in _items),
                        "items": _items,
                    })
        lager.sort(key=lambda l: (-l["m3"], -l["isk"], str(l["pin_name"])))
        fabriken = [{"schematic_id": s,
                     "name": schemata.get(s) or str(s),
                     "anzahl": n}
                    for s, n in sorted(fabrik_zahl.items())]
        # Fruehester Ablauf zuerst in der Extraktor-Liste.
        extraktoren.sort(key=lambda e: (e["ende_ts"] is None,
                                        e["ende_ts"] or 0.0))
        _enden = [e["ende_ts"] for e in extraktoren if e["ende_ts"]]
        karten.append({
            "char": p.get("char"), "char_id": p.get("char_id"),
            "planet_id": p.get("planet_id"),
            "planet": (p.get("info") or {}).get("name")
                      or str(p.get("planet_id")),
            "planet_type": p.get("planet_type"),
            "upgrade_level": p.get("upgrade_level"),
            "extraktoren": extraktoren,
            "fabriken": fabriken,
            "lager": lager,
            "m3_gesamt": sum(l["m3"] for l in lager),
            "isk_gesamt": sum(l["isk"] for l in lager),
            "naechster_ablauf_ts": min(_enden) if _enden else None,
        })
    karten.sort(key=lambda k: (str(k["char"] or ""), str(k["planet"] or "")))
    return karten


def karten_spalten(schluessel, anordnung, max_spalten=5):
    """Selbst gezogene Spalten-Anordnung der PI-Karten (emm802) - dieselbe
    Mechanik wie jobs_hand_spalten (emm775), nur mit STRING-Schluesseln
    ("charakter_id:planet_id"), weil zwei Charaktere Kolonien auf DEMSELBEN
    Planeten haben koennen und die planet_id allein nicht eindeutig ist.

    schluessel: die Karten in Anzeige-Reihenfolge (Charakter, Planet).
    anordnung:  [[key, ...], ...] wie zuletzt gespeichert, oder None.
    Abgeglichen mit der Wirklichkeit: verschwundene Karten fallen heraus,
    neue haengen an die KUERZESTE Spalte, leere Spalten fallen weg, mehr
    als max_spalten werden zusammengelegt. Ohne Anordnung: reihum auf
    max_spalten verteilt. Rein, ohne Qt.
    """
    _da = [str(s) for s in (schluessel or [])]
    _da_set = set(_da)
    try:
        _mx = max(1, int(max_spalten or 1))
    except (TypeError, ValueError):
        _mx = 5
    spalten, gesehen = [], set()
    for _g in (anordnung or []):
        _sp = [str(k) for k in (_g or [])
               if str(k) in _da_set and str(k) not in gesehen]
        for _k in _sp:
            gesehen.add(_k)
        if _sp:
            spalten.append(_sp)
    # Ueberhang-Spalten in die kuerzeste erlaubte legen.
    while len(spalten) > _mx:
        _rest = spalten.pop()
        _ziel = min(range(len(spalten)), key=lambda i: len(spalten[i]))
        spalten[_ziel].extend(_rest)
    _neu = [k for k in _da if k not in gesehen]
    if not spalten:
        spalten = [[] for _ in range(min(_mx, max(1, len(_neu))))]
        for _i, _k in enumerate(_neu):
            spalten[_i % len(spalten)].append(_k)
    else:
        for _k in _neu:
            _ziel = min(range(len(spalten)), key=lambda i: len(spalten[i]))
            spalten[_ziel].append(_k)
    return [s for s in spalten if s]


def pi_uebersicht(client_id, chars, granted=None):
    """EIN Einstieg fuer die PI-Seite: Rohdaten + alle Nachschlagetabellen
    -> (karten, fehlt, fehler). Netz: 1 Abruf je Charakter + 1 je Kolonie;
    Planeten-/Rezeptnamen danach aus dem Sitzungs-Cache (esi.planet_info/
    schematic_info), Preise aus dem 15-min-TTL-Cache."""
    from . import esi
    planeten, fehlt, fehler = rohdaten_holen(client_id, chars, granted)
    tids = set()
    schemata = {}
    for p in planeten:
        for pin in (p.get("detail") or {}).get("pins") or []:
            try:
                if pin.get("type_id"):
                    tids.add(int(pin["type_id"]))
            except (TypeError, ValueError):
                pass
            ed = pin.get("extractor_details") or {}
            if ed.get("product_type_id"):
                tids.add(int(ed["product_type_id"]))
            for c in (pin.get("contents") or []):
                try:
                    tids.add(int(c.get("type_id")))
                except (TypeError, ValueError):
                    pass
            _sid = pin.get("schematic_id")
            if _sid and int(_sid) not in schemata:
                try:
                    schemata[int(_sid)] = (esi.schematic_info(_sid).get("name")
                                           or str(_sid))
                except Exception:
                    schemata[int(_sid)] = str(_sid)
    try:
        namen = esi.resolve_names(tids) if tids else {}
    except Exception:
        namen = {}
    try:
        from . import industry
        volumen = industry.item_volume_map(tids) if tids else {}
    except Exception:
        volumen = {}
    try:
        preise = esi.average_prices()
    except Exception:
        preise = {}
    karten = karten_bauen(planeten, namen=namen, volumen=volumen,
                          preise=preise, schemata=schemata)
    return karten, fehlt, fehler
