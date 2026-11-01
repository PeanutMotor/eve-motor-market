"""Warum fehlt ingame Material, obwohl der Bauplan sagt, es sei da?
(Fassung 1, 23.10.2026)

NUTZER-BEFUND 23.10.2026: "mir fehlt ploetzlich immer wieder irgendwelches
material, obwohl ich fuer jeden Plan alles einkaufe, dann einfriere, dann
reserviere ... dann fange ich ingame an zu bauen, und ploetzlich fehlt mir
material. Stock locations zeigt auch nicht an, dass mir dieses Material
fehlt." Beispiel aus seinem Bildschirmfoto: Sylramic Fibers, 255 Runs offen,
ingame zu wenig Ceramic Powder - Eve MoMa meldete 26'150 am R&R Yard.

WAS DIESER BERICHT BEANTWORTET - und zwar mit Zahlen nebeneinander statt
mit einer Vermutung:

  1. ABRUF-GESUNDHEIT: hat jeder Charakter (und die Corp) seine Assets
     wirklich geliefert? Ein stiller Fehlschlag sieht aus wie "ist weg".

  2. WAS DER BAUPLAN ZEIGT GEGEN WAS WIRKLICH DA IST. Ein EINGEFRORENER
     Plan zeigt je Material max(Einfrier-Bestand, live) - bewusst, damit
     ein Einkauf die Liste nicht wieder aufreisst. Er ist damit aber BLIND
     dafuer, wenn Bestand real verschwindet (anderer Plan, Verkauf, falsch
     geklickter Job). Genau diese Luecke steht hier je Material: wie viel
     der Plan rechnet und wie viel ESI wirklich sieht.

  3. UEBERBUCHUNG: rechnen MEHRERE aktive Plaene mit DENSELBEN Einheiten?
     Summe des offenen Bedarfs aller Plaene gegen den echten Bestand.

  4. VERTEILUNG: wo liegt das Material - je Ort, je Charakter, je
     Behaelter. (Alle Charaktere zaehlen als EIN Bestand - Nutzer-Ansage
     23.10.2026 -, aber ein Job kann im Spiel nur nehmen, was im Hangar
     DES startenden Charakters liegt. Wer wie viel hat, steht deshalb da.)

  5. RESERVIERUNGEN: wer haelt wie viel, und was bleibt diesem Plan.

GERECHNET WIRD MIT DEN FUNKTIONEN DES WERKZEUGS SELBST (`lagerorte`,
`mw_helpers`) - keine zweite Rechnung, die anders ausgehen koennte.
Liest nur, aendert nichts.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import (config, corp, esi, lagerorte, store)   # noqa: E402

FASSUNG = 1
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERICHT = os.path.join(WURZEL, "berichte", "bestand_luecke_bericht.txt")


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


def _unpack(v):
    """Ziffern-String-Keys nach dem JSON-Roundtrip wieder zu int - dieselbe
    Regel wie `mw_helpers._plan_snapshot_unpack`."""
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


def _settings_rohe():
    """settings.json ROH lesen - OHNE `config.load_settings()`, das
    Migrationen ausfuehrt und dabei schreiben wuerde."""
    import json
    pfad = config.settings_path()
    try:
        with open(pfad, "r", encoding="utf-8") as fh:
            roh = json.load(fh)
    except Exception:
        return config.load_settings()
    return roh


def _namen(tids):
    out = {}
    tids = sorted({int(t) for t in tids if int(t or 0) > 0})
    if not tids:
        return out
    try:
        out.update(store.cached_names(tids) or {})
    except Exception:
        pass
    fehlt = [t for t in tids if not out.get(t)]
    if fehlt:
        try:
            out.update(esi.resolve_names(fehlt) or {})
        except Exception:
            pass
    return out


def _ort_namen(settings, orte):
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
    p = aus.append
    p("=" * 78)
    p(f"BESTANDS-LUECKE - Bauplan gegen Wirklichkeit (Fassung {FASSUNG})")
    p(f"Erstellt: {time.strftime('%Y-%m-%d %H:%M:%S')} (Ortszeit)")
    p("=" * 78)
    p("")

    settings = _settings_rohe()
    client_id = settings.get("client_id") or config.EMBEDDED_CLIENT_ID
    try:
        chars = store.list_characters()
    except Exception as e:
        chars = []
        p(f"DATENBANK NICHT LESBAR: {type(e).__name__}: {e}")
    try:
        zuordnung = store.job_zuordnung_details() or {}
    except Exception as e:
        zuordnung = {}
        p(f"job_zuordnung nicht lesbar: {type(e).__name__}: {e}")

    # AKTIVE PLAENE = nicht abgeschlossen (dieselbe Auswahl wie die Seite).
    plaene = lagerorte.plaene_fuer_lagerorte(settings)
    p(f"Verlinkte Charaktere: {len(chars)} · aktive Plaene: {len(plaene)}")
    for pl in plaene:
        fr = (pl.get("frozen") or {})
        p(f"  · {pl.get('label') or pl.get('item_name')}  "
          f"(id {pl.get('id')}) eingefroren {_zeit(fr.get('ts'))} "
          f"· Schloss {'an' if pl.get('reserve') else 'AUS'} "
          f"· Einfrier-Bestand {len(fr.get('stock') or {})} Posten")
    p("")

    # ---- 1. ABRUF-GESUNDHEIT ----------------------------------------------
    p("=" * 78)
    p("1. ABRUF-GESUNDHEIT - hat jeder Besitzer seine Assets geliefert?")
    p("=" * 78)
    try:
        ctypes = esi.container_type_ids_safe()
    except Exception:
        ctypes = set()
    zeilen = []
    failed = []
    stat = {}
    for ch in chars:
        cid = int(ch["character_id"])
        nm = ch.get("character_name") or str(cid)
        try:
            assets = esi._fetch_all_assets(client_id, cid)
        except Exception as e:
            failed.append(nm)
            stat[nm] = (None, None, f"{type(e).__name__}: {e}")
            continue
        zn = lagerorte.zeilen_aus_assets(assets, ctypes, nm, "char")
        stat[nm] = (len(zn), sum(int(z.get("menge") or 0) for z in zn), "")
        zeilen.extend(zn)
    if settings.get("use_corp"):
        divs = corp.divisions_bereinigt(settings.get("corp_divisions"))
        corp_von, rollen_von = {}, {}
        for ch in chars:
            cid = int(ch["character_id"])
            try:
                corp_von[cid] = esi.fetch_character_corporation(cid)
                rollen_von[cid] = esi.fetch_character_roles(client_id, cid)
            except Exception:
                rollen_von[cid] = None
        try:
            _plan, _ = corp.abrufplan(chars, corp_von, rollen_von,
                                      corp.ROLLE_ASSETS)
        except Exception:
            _plan = {}
        for corp_id, via in sorted(_plan.items()):
            try:
                cname = f"Corp: {esi.fetch_corporation_name(corp_id)}"
            except Exception:
                cname = f"Corp: #{corp_id}"
            try:
                ca = esi.fetch_corporation_assets(client_id, via, corp_id)
            except Exception as e:
                failed.append(cname)
                stat[cname] = (None, None, f"{type(e).__name__}: {e}")
                continue
            zn = lagerorte.zeilen_aus_assets(ca, ctypes, cname, "corp",
                                             divisions=divs)
            stat[cname] = (len(zn), sum(int(z.get("menge") or 0) for z in zn), "")
            zeilen.extend(zn)
    p(f"  {'BESITZER':24} {'ZEILEN':>8} {'STUECK':>14}  FEHLER")
    for nm in sorted(stat):
        n, st, err = stat[nm]
        p(f"  {nm[:24]:24} {('-' if n is None else _z(n)):>8} "
          f"{('-' if st is None else _z(st)):>14}  {err}")
    if failed:
        p("")
        p("  !! UNVOLLSTAENDIG - diese Besitzer fehlen im Bestand unten:")
        for f in failed:
            p(f"     {f}")
        p("     Ein gescheiterter Abruf sieht aus wie 'Material ist weg'.")
    p("")

    # ---- Bestand aufsummieren ---------------------------------------------
    _aus = set()
    for o in (settings.get("lager_orte_aus") or []):
        try:
            _aus.add(int(o))
        except (TypeError, ValueError):
            continue
    try:
        from eve_trader.ui.mw_helpers import verlinkte_struktur_ids
        _struct = {int(x) for x in (verlinkte_struktur_ids(settings) or [])}
    except Exception:
        _struct = set()

    live_gesamt = {}        # tid -> Stueck ueberall
    live_an = {}            # tid -> Stueck an eingeschalteten Orten
    live_struct = {}        # tid -> Stueck an den verlinkten Bau-Strukturen
    je_ort = {}             # tid -> {ort: {besitzer: menge}}
    for z in zeilen:
        tid = int(z.get("tid") or 0)
        if tid <= 0:
            continue
        m = int(z.get("menge") or 0)
        ort = int(z.get("ort") or 0)
        live_gesamt[tid] = live_gesamt.get(tid, 0) + m
        if ort not in _aus:
            live_an[tid] = live_an.get(tid, 0) + m
        if ort in _struct:
            live_struct[tid] = live_struct.get(tid, 0) + m
        je_ort.setdefault(tid, {}).setdefault(ort, {})
        b = str(z.get("besitzer"))
        if z.get("pfad"):
            b += "  [in Behaelter]"
        je_ort[tid][ort][b] = je_ort[tid][ort].get(b, 0) + m

    # ---- Bedarf je Plan ----------------------------------------------------
    bedarf = lagerorte.bedarf_aus_plaenen(plaene, zuordnung)   # {tid: [(label, menge)]}
    bedarf_summe = {t: sum(int(q or 0) for _l, q in v)
                    for t, v in (bedarf or {}).items()}

    # ---- Was ZEIGT der eingefrorene Plan? max(Einfrier, live) --------------
    zeigt = {}              # (plan_label, tid) -> (frozen, live, gezeigt)
    for pl in plaene:
        lab = str(pl.get("label") or pl.get("item_name") or "?")
        fs = _unpack((pl.get("frozen") or {}).get("stock") or {})
        for t, q in fs.items():
            try:
                t = int(t); q = int(q or 0)
            except (TypeError, ValueError):
                continue
            lv = int(live_gesamt.get(t, 0))
            zeigt[(lab, t)] = (q, lv, max(q, lv))

    namen = _namen(set(bedarf_summe) | set(live_gesamt)
                   | {t for _l, t in zeigt})
    ort_namen = _ort_namen(settings, {o for d in je_ort.values() for o in d})

    def onm(o):
        return ort_namen.get(o) or f"#{o}"

    # ---- 2. BAUPLAN GEGEN WIRKLICHKEIT -------------------------------------
    p("=" * 78)
    p("2. WAS DER PLAN RECHNET GEGEN WAS ESI WIRKLICH SIEHT")
    p("=" * 78)
    p("  Ein eingefrorener Plan zeigt je Material max(Einfrier-Bestand, live).")
    p("  Steht links MEHR als rechts, rechnet der Plan mit Material, das es")
    p("  real nicht mehr gibt - genau das faellt erst ingame auf.")
    p("")
    luecken = []
    for (lab, t), (fz, lv, gz) in zeigt.items():
        if gz > lv and bedarf_summe.get(t):
            luecken.append((gz - lv, lab, t, fz, lv, gz))
    luecken.sort(reverse=True)
    if not luecken:
        p("  KEINE LUECKE: kein Material, bei dem ein Plan mehr rechnet als da ist.")
    else:
        p(f"  {'MATERIAL':34} {'PLAN':22} {'PLAN RECHNET':>13} {'ESI LIVE':>12} {'LUECKE':>12}")
        for d, lab, t, fz, lv, gz in luecken[:60]:
            p(f"  {str(namen.get(t) or t)[:34]:34} {lab[:22]:22} "
              f"{_z(gz):>13} {_z(lv):>12} {_z(d):>12}")
        if len(luecken) > 60:
            p(f"  ... und {len(luecken) - 60} weitere")
    p("")

    # ---- 3. UEBERBUCHUNG ---------------------------------------------------
    p("=" * 78)
    p("3. UEBERBUCHUNG - rechnen mehrere Plaene mit denselben Einheiten?")
    p("=" * 78)
    p("  Offener Bedarf ALLER aktiven Plaene gegen den echten Bestand.")
    p("")
    ueber = []
    for t, soll in bedarf_summe.items():
        ist = int(live_an.get(t, 0))
        if soll > ist:
            ueber.append((soll - ist, t, soll, ist))
    ueber.sort(reverse=True)
    if not ueber:
        p("  NICHTS UEBERBUCHT: jeder offene Bedarf ist gedeckt.")
    else:
        p(f"  {'MATERIAL':34} {'BEDARF ALLE':>13} {'VORHANDEN':>12} {'FEHLT':>12}  JE PLAN")
        for d, t, soll, ist in ueber[:60]:
            teile = " · ".join(f"{l}: {_z(q)}" for l, q in (bedarf.get(t) or []))
            p(f"  {str(namen.get(t) or t)[:34]:34} {_z(soll):>13} {_z(ist):>12} "
              f"{_z(d):>12}  {teile[:60]}")
        if len(ueber) > 60:
            p(f"  ... und {len(ueber) - 60} weitere")
    p("")

    # ---- 4. VERTEILUNG der knappen Materialien -----------------------------
    p("=" * 78)
    p("4. WO LIEGT DAS MATERIAL - je Ort und Besitzer")
    p("=" * 78)
    p("  Alle Charaktere zaehlen als EIN Bestand. Ein Job im Spiel kann aber")
    p("  nur nehmen, was im Hangar DES startenden Charakters liegt - deshalb")
    p("  steht hier, wer wie viel hat.")
    p("")
    knapp = [t for _d, t, _s, _i in ueber] + [t for _d, _l, t, _f, _lv, _g in luecken]
    # NACHGESCHAERFT (27.10.2026, Vorfall T1 Battlecruisers): die Liste war
    # leer, obwohl ingame Material fehlte - "gedeckt" hiess nur "irgendwo
    # vorhanden". Ein Job nimmt aber nur aus dem Hangar SEINES Charakters an
    # SEINER Struktur. Deshalb stehen hier jetzt auch alle Materialien mit
    # offenem Bedarf, von denen an den BAU-Strukturen weniger liegt als der
    # Bedarf - plus alles, was auf der Kommandozeile genannt wurde
    # (pruefe_bestand_luecke.bat Tritanium Pyerite ...).
    knapp += sorted((t for t, b in bedarf_summe.items()
                     if b > 0 and live_struct.get(t, 0) < b),
                    key=lambda t: live_struct.get(t, 0) - bedarf_summe.get(t, 0))
    # ... und IMMER die zwoelf groessten offenen Posten (27.10.2026, zweiter
    # Anlauf desselben Vorfalls): "an den Bau-Strukturen genug" war wieder
    # wahr und der Abschnitt wieder leer - das Material lag an der richtigen
    # Struktur, aber beim falschen BESITZER. Wer hier nachschaut, will die
    # Verteilung sehen, nicht eine zweite Beruhigung.
    knapp += sorted((t for t, b in bedarf_summe.items() if b > 0),
                    key=lambda t: -bedarf_summe.get(t, 0))[:12]
    _wunsch = [a.strip().lower() for a in sys.argv[1:] if a.strip()]
    if _wunsch:
        _nm_zu_tid = {str(v).lower(): k for k, v in namen.items()}
        for _w in _wunsch:
            _t = _nm_zu_tid.get(_w)
            if _t is not None:
                knapp.append(_t)
            else:
                _tref = [k for k, v in namen.items() if _w in str(v).lower()]
                knapp += _tref[:3]
    gesehen = set()
    for t in knapp:
        if t in gesehen:
            continue
        gesehen.add(t)
        if len(gesehen) > 40:
            p("  ... (gekuerzt)")
            break
        p(f"  {namen.get(t) or t}   Bedarf {_z(bedarf_summe.get(t, 0))} ·"
          f" gesamt {_z(live_gesamt.get(t, 0))} ·"
          f" an eingeschalteten Orten {_z(live_an.get(t, 0))} ·"
          f" an Bau-Strukturen {_z(live_struct.get(t, 0))}")
        for ort, bes in sorted((je_ort.get(t) or {}).items(),
                               key=lambda kv: -sum(kv[1].values())):
            mark = "AUS" if ort in _aus else ("BAU" if ort in _struct else "ein")
            p(f"      {mark}  {onm(ort)[:40]:40} {_z(sum(bes.values())):>12}")
            for b, m in sorted(bes.items(), key=lambda kv: -kv[1]):
                p(f"             {b[:44]:44} {_z(m):>12}")
        p("")

    # ---- 4b. ALT GEGEN NEU (emm636) ---------------------------------------
    p("=" * 78)
    p("4b. WAS DER FEHLBEDARFS-MELDER VORHER SAGTE - UND JETZT SAGT (emm636)")
    p("=" * 78)
    p("  VORHER rechnete `_fehlbedarf_jetzt` gegen max(Einfrier-Bestand,")
    p("  live) - also gegen die Zahl, die ein verschwundenes Material")
    p("  versteckt. JETZT gegen den echten Live-Stand. Diese Tabelle zeigt,")
    p("  was dadurch ueberhaupt erst sichtbar wird.")
    p("")
    _verschwiegen = []
    for pl in plaene:
        lab = str(pl.get("label") or pl.get("item_name") or "?")
        fs = _unpack((pl.get("frozen") or {}).get("stock") or {})
        if not fs:
            continue
        for t in bedarf_summe:
            # JE PLAN, nicht die Summe: ein Plan kann nur verschweigen, was
            # er selbst braucht. `bedarf` ist {tid: [(Plan, Menge), ...]}.
            soll = sum(int(q or 0) for _l, q in (bedarf.get(t) or [])
                       if str(_l) == lab)
            if soll <= 0:
                continue
            _fz = int(fs.get(t, 0) or 0)
            _lv = int(live_an.get(t, 0))
            _alt = max(0, soll - max(_fz, _lv))     # mit Einfrier-Merge
            _neu = max(0, soll - _lv)               # echter Stand
            if _neu > _alt:
                _verschwiegen.append((_neu - _alt, lab, t, soll, _fz, _lv,
                                      _alt, _neu))
    _verschwiegen.sort(reverse=True)
    # SCHARF, BEISST ABER GERADE NICHT: Einfrier-Stand ueber dem echten,
    # aber dieser Plan braucht das Material im Moment nicht mehr. Sobald er
    # es wieder braucht (oder der Bestand weiter faellt), verschweigt der
    # alte Melder genau diese Menge. Ohne diese zweite Tabelle sieht ein
    # ruhender Fehler aus wie "gibt es nicht" - genau die Verwechslung,
    # die diesen Bericht ueberhaupt noetig gemacht hat (Regel 6).
    _scharf = []
    for pl in plaene:
        lab = str(pl.get("label") or pl.get("item_name") or "?")
        fs = _unpack((pl.get("frozen") or {}).get("stock") or {})
        for t, q in fs.items():
            try:
                t, q = int(t), int(q or 0)
            except (TypeError, ValueError):
                continue
            _lv = int(live_an.get(t, 0))
            _soll = sum(int(_q or 0) for _l, _q in (bedarf.get(t) or [])
                        if str(_l) == lab)
            if q > _lv and _soll <= 0:
                _scharf.append((q - _lv, lab, t, q, _lv))
    _scharf.sort(reverse=True)
    if not _verschwiegen:
        p("  BEISST GERADE NICHT: bei keinem Material mit offenem Bedarf")
        p("  liegt der Einfrier-Stand ueber dem echten - alter und neuer")
        p("  Melder saegen hier dasselbe. Das heisst NICHT, dass der Fehler")
        p("  weg ist: er ruht, solange genug da ist (s. naechste Tabelle).")
    else:
        p(f"  {'MATERIAL':30} {'PLAN':20} {'BEDARF':>10} {'ECHT':>10} "
          f"{'MELDUNG ALT':>12} {'MELDUNG NEU':>12} {'VERSCHWIEGEN':>13}")
        for d, lab, t, soll, fz, lv, alt, neu in _verschwiegen[:40]:
            p(f"  {str(namen.get(t) or t)[:30]:30} {lab[:20]:20} "
              f"{_z(soll):>10} {_z(lv):>10} {_z(alt):>12} {_z(neu):>12} "
              f"{_z(d):>13}")
        p("")
        p(f"  SUMME: {len(_verschwiegen)} Posten, zusammen "
          f"{_z(sum(x[0] for x in _verschwiegen))} Stueck, die der alte")
        p("  Melder NICHT verlangt hat - genau die Menge, die spaeter im")
        p("  Spiel fehlt.")
    p("")
    p("  SCHARF, BEISST ABER GERADE NICHT (Einfrier-Stand ueber dem echten,")
    p("  dieser Plan braucht das Material im Moment nicht):")
    if not _scharf:
        p("      (nichts)")
    else:
        p(f"      {'MATERIAL':30} {'PLAN':22} {'PLAN RECHNET':>13} "
          f"{'ECHT':>10} {'WUERDE VERSCHWEIGEN':>20}")
        for d, lab, t, q, lv in _scharf[:25]:
            p(f"      {str(namen.get(t) or t)[:30]:30} {lab[:22]:22} "
              f"{_z(q):>13} {_z(lv):>10} {_z(d):>20}")
        if len(_scharf) > 25:
            p(f"      ... und {len(_scharf) - 25} weitere")
        p(f"      SUMME: {len(_scharf)} Posten, zusammen "
          f"{_z(sum(x[0] for x in _scharf))} Stueck.")
    p("")

    # ---- 5. RESERVIERUNGEN -------------------------------------------------
    p("=" * 78)
    p("5. RESERVIERUNGEN - wer haelt wie viel")
    p("=" * 78)
    try:
        from eve_trader.ui.mw_helpers import MainWindowHelpers as _MH
        p(f"  Bau-Prioritaet (Rang): {settings.get('bau_plan_reihenfolge')}")
        _rang = _MH.plan_rang(settings)
        p(f"  plan_rang(): {_rang}")
        p("")
        for pl in plaene:
            pid = pl.get("id")
            lab = str(pl.get("label") or pl.get("item_name") or "?")
            res, who = _MH._reserved_by_other_plans(settings, pid)
            eigen = _MH._reserved_by_this_plan(settings, pid)
            p(f"  PLAN {lab}  (Rang {_rang.get(str(pid), '-')})")
            p(f"     sieht Reservierungen von: {', '.join(who) or '(keine)'}")
            p(f"     fremd reserviert: {len(res)} Posten · "
              f"eigen reserviert: {len(eigen)} Posten")
            # Die Posten, die diesem Plan wirklich wehtun
            weh = []
            for t, q in res.items():
                if bedarf_summe.get(t):
                    frei = int(live_an.get(t, 0)) - int(q or 0)
                    if frei < int(bedarf_summe.get(t, 0)):
                        weh.append((int(q or 0), t, frei))
            weh.sort(reverse=True)
            for q, t, frei in weh[:12]:
                p(f"       {str(namen.get(t) or t)[:34]:34} fremd {_z(q):>12} "
                  f"· bleibt {_z(frei):>12} · Bedarf {_z(bedarf_summe.get(t, 0)):>12}")
            p("")
    except Exception as e:
        p(f"  Reservierungs-Abschnitt scheiterte: {type(e).__name__}: {e}")

    os.makedirs(os.path.dirname(BERICHT), exist_ok=True)
    with open(BERICHT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(aus) + "\n")
    print("\n".join(aus[:40]))
    print("")
    print(f"Geschrieben: {BERICHT}")


if __name__ == "__main__":
    main()
