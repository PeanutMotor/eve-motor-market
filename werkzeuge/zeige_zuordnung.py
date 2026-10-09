"""Zeigt, WARUM ein Material im eingefrorenen Bauplan plötzlich fehlt - und
wem das Tool welchen Industrie-Job zuordnet (Fassung 1, 25.09.2026).

WOZU: Nutzer-Befund 25.09.2026 - "es fehlen anscheinend Silicon Diborite,
das ist aber neu, die haben nicht immer gefehlt, plötzlich soll ich wieder
davon bauen". Ein eingefrorener Plan rechnet NICHT mehr: sein Bedarf steht
fest. Bewegen kann sich also nur die andere Seite - der Bestand und das, was
das Tool an gebauten Runs anrechnet. Genau diese Zahlen stehen hier
nebeneinander, damit man SIEHT, welche sich bewegt hat, statt zu raten
(Regel 5).

Je Position eines Plans zeigt der Bericht:
  * Plan-Runs (aus dem eingefrorenen Schnappschuss - unveränderlich),
  * ABGELIEFERTE Runs seit dem Einfrieren (die zählen als Fortschritt),
  * LAUFENDE Jobs (deren Material ist im Spiel schon WEG, ihr Erzeugnis
    aber noch nicht da - das ist der häufigste Grund für "fehlt plötzlich"),
  * den aktuellen Bestand,
  * ob ein anderer, NICHT abgeschlossener Plan dasselbe Item beansprucht
    (dann ist die Zuordnung strittig).

Dazu die Tabelle `job_zuordnung`: welcher Job gehört laut Werkzeug welchem
Plan, und woher diese Entscheidung stammt (Klick, Eindeutigkeit, deine
Antwort).

GERATEN WIRD HIER NICHTS. Der Bericht rechnet mit denselben Funktionen wie
das Werkzeug und schreibt die Rohdaten daneben.

AUFRUF: werkzeuge\\zeige_zuordnung.bat doppelklicken.
Danach liegt `berichte\\zuordnung_bericht.txt` da - die hochladen.
Es wird NUR GELESEN: weder Datenbank noch Einstellungen werden verändert.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import config, esi, store   # noqa: E402

FASSUNG = 5
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERICHT = os.path.join(WURZEL, "berichte", "zuordnung_bericht.txt")


def _z(n):
    try:
        return f"{int(n):,}".replace(",", "'")
    except (TypeError, ValueError):
        return "?"


def _zeit(ts):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError, OSError):
        return "?"


def _iso(s):
    """ESI-Zeitstempel -> Epochensekunden (wie mw_helpers._iso_job_ts)."""
    if not s:
        return None
    try:
        import datetime as _dt
        _t = str(s).replace("Z", "+00:00")
        return _dt.datetime.fromisoformat(_t).timestamp()
    except (TypeError, ValueError):
        return None


def _unpack(v):
    """Ziffern-String-Keys nach dem JSON-Roundtrip wieder zu int - dieselbe
    Regel wie `mw_helpers._plan_snapshot_unpack`. Bewusst hier nachgebaut,
    damit dieses Werkzeug ohne Qt laeuft."""
    def _key(k):
        if isinstance(k, str):
            _k = k[1:] if k.startswith("-") else k
            if _k.isdigit():
                return int(k)
        return k
    if isinstance(v, dict):
        return {_key(k): _unpack(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_unpack(x) for x in v]
    return v


def _schreib(zeilen):
    os.makedirs(os.path.dirname(BERICHT), exist_ok=True)
    with open(BERICHT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(zeilen) + "\n")
    print("\n".join(zeilen))
    print("")
    print(f"Geschrieben: {BERICHT}")


def main():
    aus = []
    p = aus.append
    p("=" * 78)
    p(f"JOB-ZUORDNUNG UND FEHLENDES MATERIAL (Fassung {FASSUNG})")
    p(f"Erstellt: {time.strftime('%Y-%m-%d %H:%M:%S')} (Ortszeit)")
    p("=" * 78)
    p("")

    try:
        chars = store.list_characters()
    except Exception as e:
        # NICHT ABBRECHEN: die Plaene stehen in settings.json, nicht in der
        # Datenbank. Ohne Charaktere fehlen nur Jobs und Bestand - der Rest
        # des Berichts ist trotzdem etwas wert.
        chars = []
        p(f"DATENBANK NICHT LESBAR: {type(e).__name__}: {e}")
        p("")
    settings = config.load_settings() or {}
    client_id = settings.get("client_id") or config.EMBEDDED_CLIENT_ID
    plaene = settings.get("bau_saved_plans") or []
    p(f"Verlinkte Charaktere: {len(chars)} · Gespeicherte Baupläne: "
      f"{len(plaene)}")
    p("")

    # ---- 1. DIE PLAENE ----------------------------------------------------
    p("-" * 78)
    p("GESPEICHERTE BAUPLÄNE")
    p("-" * 78)
    from eve_trader.ui.mw_helpers import MainWindowHelpers as _MWH0
    _mitgl0 = _MWH0.buendel_mitglieder({"bau_saved_plans": plaene})
    for pl in plaene:
        _fz = pl.get("frozen") or {}
        p(f"  id {pl.get('id')}  {pl.get('label') or pl.get('item_name') or '?'}"
          + ("  [MITGLIED EINES MULTIPLANS - zaehlt nicht als eigener Plan]"
             if str(pl.get('id')) in _mitgl0 else ""))
        p(f"      abgeschlossen: {'JA' if pl.get('done_manual') else 'nein'}"
          f" · Schloss: {'an' if pl.get('reserve') else 'aus'}"
          f" · eingefroren: {_zeit(_fz.get('ts')) if _fz.get('ts') else 'nein'}"
          f" · Positionen in der reserve_map:"
          f" {len(pl.get('reserve_map') or {})}")
    p("")
    # ---- WARUM DIE KARTE ANDERS RECHNET ALS DER DIALOG -------------------
    # Nutzer 25.09.2026: "der Bauplan sagt 3'894'389/Stk, die Profituebersicht
    # behauptet 4'767'286 und damit Minus". Die Karte nimmt fuer einen
    # eingefrorenen Plan den PLAN-SCHNAPPSCHUSS - aber nur, wenn es einen
    # gibt UND seine Menge zur Plan-Menge passt. Sonst plant sie neu, und
    # eine Neuplanung kauft auch das Material, das damals schon im Hangar
    # lag. Genau das steht hier, je Plan, ohne Deutung.
    p("-" * 78)
    p("EINGEFRORENE PL\u00c4NE \u2013 rechnet die Karte aus dem Schnappschuss?")
    p("-" * 78)
    for pl in plaene:
        _fz = pl.get("frozen") or {}
        if not _fz:
            continue
        _snap = _fz.get("plan_snapshot") or {}
        _qty_p = int(pl.get("qty") or 1)
        _qty_f = int(_fz.get("qty") or 0)
        _tc = 0.0
        try:
            _tc = float((_unpack(_snap) or {}).get("total_cost", 0.0) or 0.0)
        except (TypeError, ValueError):
            _tc = 0.0
        _aus_snap = bool(_snap) and _qty_f == _qty_p and _tc > 0
        p(f"  {pl.get('label') or pl.get('item_name') or '?'}")
        p(f"      Schnappschuss: {'ja' if _snap else 'NEIN'}"
          f" \u00b7 Menge im Schnappschuss: {_qty_f or '-'} / Plan: {_qty_p}"
          f" \u00b7 Bestandspositionen beim Einfrieren:"
          f" {len(_fz.get('stock') or {})}")
        p(f"      Gesamtkosten im Schnappschuss: {_z(_tc) if _tc else '-'}"
          f" \u00b7 je St\u00fcck: "
          f"{_z(_tc / _qty_p) if (_tc and _qty_p) else '-'}")
        # DIE EINZELTEILE (Fassung 3): nur so laesst sich sagen, WELCHER
        # Posten zwischen Karte und Dialog auseinanderlaeuft - Material,
        # Bestand, Job oder Invention.
        try:
            _s2 = _unpack(_snap) or {}
            _mat = float(_s2.get("mat_cost", 0.0) or 0.0)
            _stk = float(_s2.get("stock_cost", 0.0) or 0.0)
            _job = float(_s2.get("job_cost", 0.0) or 0.0)
            _inv = float(_s2.get("inv_cost", 0.0) or 0.0)
            _rw = float((_s2.get("reprocess") or {}).get(
                "ruecklaeufer_wert", 0.0) or 0.0)
            p(f"      davon: Material {_z(_mat)} \u00b7 Bestand {_z(_stk)}"
              f" \u00b7 Job {_z(_job)} \u00b7 Invention {_z(_inv)}"
              + (f" \u00b7 \u2212 R\u00fcckl\u00e4ufer {_z(_rw)}" if _rw else ""))
            _summe = _mat + _stk + _job + _inv - _rw
            p(f"      Probe: Material+Bestand+Job+Invention = {_z(_summe)}"
              + ("  (= Gesamtkosten)" if abs(_summe - _tc) < 1.0 else
                 f"  (WEICHT AB um {_z(_summe - _tc)})"))
            p(f"      Kaufliste im Schnappschuss (Posten): "
              f"{len(_s2.get('buy') or {})}"
              f" \u00b7 daraus Bestand genommen (Posten): "
              f"{len(_s2.get('stock_used') or {})}")
        except (TypeError, ValueError, AttributeError):
            p("      davon: nicht lesbar")
        p("      -> Karte rechnet: "
          + ("AUS DEM SCHNAPPSCHUSS (gleiche Zahl wie der Dialog)"
             if _aus_snap else
             "NEU (Rueckfall) \u2013 die Zahl kann hoeher sein als im Dialog"))
    p("")
    p("WICHTIG: ein ABGESCHLOSSENER Plan macht seit dem 25.09.2026 kein Item")
    p("mehr strittig - er baut ja nichts mehr. Seine reserve_map bleibt aber")
    p("gespeichert; in aelteren Fassungen hat genau sie jede Frage ausgeloest.")
    p("")

    # ---- 2. DIE TABELLE job_zuordnung -------------------------------------
    try:
        zu = store.job_zuordnung_fuer_plan  # nur zur Existenzpruefung
        alle = store.job_zuordnung_alle()
    except Exception as e:
        alle = {}
        p(f"job_zuordnung nicht lesbar: {type(e).__name__}: {e}")
    _ = zu
    p("-" * 78)
    p(f"TABELLE job_zuordnung – {len(alle)} Einträge")
    p("-" * 78)
    _namen_plan = {str(x.get("id")): str(x.get("label")
                                         or x.get("item_name") or "?")
                   for x in plaene}
    for pl in plaene:
        try:
            _rows = store.job_zuordnung_fuer_plan(str(pl.get("id")))
        except Exception:
            _rows = {}
        if not _rows:
            continue
        p(f"  {_namen_plan.get(str(pl.get('id')), '?')}:")
        for _jid, _r in sorted(_rows.items()):
            p(f"      Job {_jid}  Item {_r.get('type_id')}  "
              f"{_z(_r.get('runs'))} Runs  Quelle {_r.get('quelle')}  "
              f"{_zeit(_r.get('ts'))}")
    _keiner = [j for j, pid in alle.items() if str(pid) == "-"]
    if _keiner:
        p(f"  „zu keinem Plan“ (deine Antwort): {len(_keiner)} Job(s)")
    p("")

    # ---- 3. JOBS VON ESI --------------------------------------------------
    jobs = []
    fehler = {}
    for c in chars:
        cid = c["character_id"]
        try:
            jobs += [dict(j, _char=c.get("character_name") or "?")
                     for j in esi.fetch_active_jobs(client_id, cid,
                                                    include_delivered=True)]
        except Exception as e:
            fehler[c.get("character_name") or cid] = f"{type(e).__name__}: {e}"
    # CORP-JOBS ZAEHLEN WIE CHARAKTER-JOBS (emm483, REGEL CORP = CHARAKTER):
    # auch ein Corp-Job kann einem Plan zugeordnet sein - ohne ihn fehlte in
    # diesem Bericht genau die Zeile, um die es geht. Ein Abruf je Corp
    # (corp.abrufplan); /characters/.../industry/jobs enthaelt keine
    # Corp-Jobs (geprueft, emm389). Der BESTAND weiter unten bleibt bewusst
    # nur die Charakter-Hangare - Corp-Bestand zeigen Stock locations und
    # zeige_lagerorte.
    if settings.get("use_corp"):
        from eve_trader import corp
        _cv, _rv = {}, {}
        for c in chars:
            cid = int(c["character_id"])
            try:
                _cv[cid] = esi.fetch_character_corporation(cid)
                _rv[cid] = esi.fetch_character_roles(client_id, cid)
            except Exception as e:
                _rv[cid] = None
                fehler[f"Corp-Rollen {c.get('character_name') or cid}"] = \
                    f"{type(e).__name__}: {e}"
        _pjobs, _ = corp.abrufplan(chars, _cv, _rv, corp.ROLLE_JOBS)
        for _cjid, _cvia in sorted(_pjobs.items()):
            try:
                jobs += [dict(j, _char=f"Corp #{_cjid}")
                         for j in esi.fetch_corporation_jobs(
                             client_id, _cvia, _cjid,
                             include_delivered=True) or []]
            except Exception as e:
                fehler[f"Corp-Jobs #{_cjid}"] = f"{type(e).__name__}: {e}"
    p("-" * 78)
    p(f"INDUSTRIE-JOBS von ESI: {len(jobs)} (aktiv, fertig und abgeliefert)")
    p("-" * 78)
    for _n, _f in fehler.items():
        p(f"  ABRUF FEHLGESCHLAGEN {_n}: {_f}")
    p("")

    # ---- 4. BESTAND -------------------------------------------------------
    bestand = {}
    for c in chars:
        try:
            for t, q in (esi.fetch_assets(client_id,
                                          c["character_id"]) or {}).items():
                bestand[int(t)] = bestand.get(int(t), 0) + int(q or 0)
        except Exception as e:
            fehler[f"assets {c.get('character_name')}"] = \
                f"{type(e).__name__}: {e}"

    # ---- 5. JE OFFENEM, EINGEFRORENEM PLAN --------------------------------
    offen = [x for x in plaene
             if not x.get("done_manual") and (x.get("frozen") or {}).get("ts")]
    p("-" * 78)
    p(f"OFFENE, EINGEFRORENE BAUPLÄNE: {len(offen)}")
    p("-" * 78)
    if not offen:
        p("  (keiner – dann kann auch nichts „ploetzlich fehlen“)")
    for pl in offen:
        _fz = pl.get("frozen") or {}
        snap = _unpack(_fz.get("plan_snapshot") or {})
        _ts = float(_fz.get("ts") or 0)
        runs = {int(k): int(v or 0)
                for k, v in (snap.get("build_runs") or {}).items()}
        mats = snap.get("build_mats") or {}
        # BEDARF wie `restbedarf_map`: die Mengen in build_mats gelten fuer
        # ALLE Runs der Position, nicht je Run.
        bedarf = {}
        for _t, _liste in mats.items():
            for _m in (_liste or []):
                try:
                    bedarf[int(_m[0])] = bedarf.get(int(_m[0]), 0) + int(_m[1])
                except (TypeError, ValueError, IndexError):
                    continue
        # Wer beansprucht dasselbe Item? NUR nicht abgeschlossene Plaene -
        # und KEINE Buendel-Mitglieder (Fassung 4, Nutzer 26.09.2026): wer in
        # einem Multiplan steckt, baut nicht noch einmal fuer sich. Dieselbe
        # Regel wie im Werkzeug (mw_helpers.buendel_mitglieder).
        from eve_trader.ui.mw_helpers import MainWindowHelpers as _MWH
        _mitgl = _MWH.buendel_mitglieder({"bau_saved_plans": plaene})
        streit = {}
        for _o in plaene:
            if _o.get("done_manual") or str(_o.get("id")) == str(pl.get("id")):
                continue
            if str(_o.get("id")) in _mitgl:
                continue
            # Fassung 5 (emm427): strittig nur, wenn der andere Plan das Item
            # SELBST BAUT - dieselbe Regel wie im Werkzeug (plan_baut_items).
            for _k in _MWH.plan_baut_items(_o):
                streit.setdefault(int(_k), []).append(
                    str(_o.get("label") or _o.get("item_name") or "?"))
        namen = {}
        try:
            namen = esi.resolve_names(sorted(set(runs) | set(bedarf)))
        except Exception:
            pass
        p("")
        p(f"### {pl.get('label') or pl.get('item_name') or '?'}  "
          f"(id {pl.get('id')}, eingefroren {_zeit(_ts)})")
        p("")
        p("  POSITION                        PLAN   GELIEFERT   LAEUFT   "
          "BESTAND   BEDARF  STRITTIG")
        for t in sorted(runs, key=lambda x: str(namen.get(x, x)).lower()):
            _gel = _lauf = 0
            for j in jobs:
                if int(j.get("product_type_id") or 0) != int(t):
                    continue
                if j.get("status") == "delivered":
                    _c = _iso(j.get("completed_date"))
                    if _c is not None and _c >= _ts:
                        _gel += int(j.get("runs") or 0)
                else:
                    _lauf += int(j.get("runs") or 0)
            _nm = str(namen.get(t, t))[:30]
            p(f"  {_nm:<30} {_z(runs[t]):>6} {_z(_gel):>11} {_z(_lauf):>8} "
              f"{_z(bestand.get(int(t), 0)):>9} {_z(bedarf.get(int(t), 0)):>8}  "
              + (", ".join(streit.get(int(t), [])) or "-"))
        p("")
        p("  LESEHILFE: steht bei einer Position etwas unter LAEUFT, ist ihr")
        p("  Material im Spiel bereits verbraucht, das Erzeugnis aber noch")
        p("  nicht im Hangar. Der Bestand der VORSTUFE sinkt dann, und der")
        p("  eingefrorene Plan meldet sie als fehlend - obwohl nichts fehlt.")
        p("  Steht etwas unter STRITTIG, beansprucht ein anderer offener Plan")
        p("  dasselbe Item; dann fragt das Werkzeug einmal nach.")
    p("")
    p("=" * 78)
    p("ENDE")
    _schreib(aus)
    return 0


if __name__ == "__main__":
    sys.exit(main())
