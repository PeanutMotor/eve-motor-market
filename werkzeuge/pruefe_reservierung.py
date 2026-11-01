"""Haelt ein Plan Material fest, das er gar nicht mehr verbraucht?
(Fassung 1, 23.10.2026)

NUTZER-BEFUND 23.10.2026, Bildschirmfoto "Already on hand" von Gallente 1:
"warum die einkaufsliste Ferrogel kaufen will verstehe ich auch nicht, die
muss ich gar nicht mehr bauen, alles komisch". GEMESSEN: Gallente 1 braucht
17'427 Ferrogel, am Bau-Ort stehen 10'341 - weil "31'095 reserved". Es
EXISTIEREN aber nur 23'836 Stueck. Multibuildplan Amarr 1 haelt davon
23'829, Minmatar 1 die restlichen 7'266.

DIE FRAGE, DIE DIESER BERICHT BEANTWORTET: ist dieser Anspruch BERECHTIGT?
Ein Plan darf das Material festhalten, das seine NOCH OFFENEN Runs
verbrauchen werden - auch das, was er selbst hergestellt hat ("liegt in
meinem Hangar und gehoert diesem Plan"). Haelt er dagegen Material fest,
fuer das es keinen offenen Verbraucher mehr gibt, hungert er alle spaeteren
Plaene grundlos aus - und die melden dann Kaufbedarf fuer Material, das im
Hangar liegt.

JE PLAN UND MATERIAL steht deshalb nebeneinander:
  * ANSPRUCH   - was `plan_anspruch_mitlaufend` reserviert (dieselbe
                 Funktion, mit der der Bauplan rechnet, keine Zweitrechnung)
  * VERBRAUCH  - was die NOCH OFFENEN Runs dieses Plans davon brauchen
                 (offene Runs = Plan-Runs minus `gebaute_runs`, also
                 zugeordnete ESI-Jobs und Hand-Haken, je Item das Maximum)
  * VERBRAUCHER - welche Items das sind, mit ihren offenen Runs
  * URTEIL     - "ok" (Anspruch <= Verbrauch) oder "HAELT ZU VIEL"

Am Ende: je Material die Summe aller Anspruechee gegen den echten Bestand -
dort sieht man sofort, ob mehr reserviert ist als existiert.

Liest nur, aendert nichts. Braucht ESI nur fuer den Bestands-Vergleich am
Schluss; ohne ESI-Zugang bleibt dieser Teil leer, der Rest rechnet.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import config, esi, lagerorte, store   # noqa: E402
from eve_trader.ui.mw_helpers import MainWindowHelpers as MH   # noqa: E402

FASSUNG = 1
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERICHT = os.path.join(WURZEL, "berichte", "reservierung_bericht.txt")


def _z(n):
    try:
        return f"{int(n):,}".replace(",", "'")
    except (TypeError, ValueError):
        return "?"


def _zeit_kurz(ts):
    try:
        return time.strftime("%Y-%m-%d %H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError, OSError):
        return "?"


def _settings_rohe():
    import json
    try:
        with open(config.settings_path(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return config.load_settings()


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


def main():
    aus = []
    p = aus.append
    p("=" * 78)
    p(f"RESERVIERUNG - haelt ein Plan mehr fest, als er noch verbraucht? "
      f"(Fassung {FASSUNG})")
    p(f"Erstellt: {time.strftime('%Y-%m-%d %H:%M:%S')} (Ortszeit)")
    p("=" * 78)
    p("")

    settings = _settings_rohe()
    try:
        zuordnung = store.job_zuordnung_details() or {}
    except Exception as e:
        zuordnung = {}
        p(f"  job_zuordnung nicht lesbar: {type(e).__name__}: {e}")
    p(f"  Zugeordnete ESI-Jobs in der Datenbank: {len(zuordnung)}")
    p("")

    plaene = [pl for pl in (settings.get("bau_saved_plans") or [])
              if isinstance(pl, dict) and not pl.get("done_manual")]
    anspruch_je_plan = {}
    alle_tids = set()
    for pl in plaene:
        lab = str(pl.get("label") or pl.get("item_name") or "?")
        if not pl.get("reserve"):
            continue
        a = MH.plan_anspruch_mitlaufend(pl) or {}
        anspruch_je_plan[lab] = (pl, {int(t): int(q or 0) for t, q in a.items()})
        alle_tids |= set(anspruch_je_plan[lab][1])

    for lab, (pl, ansp) in anspruch_je_plan.items():
        snap = MH._plan_snapshot_unpack(
            (pl.get("frozen") or {}).get("plan_snapshot") or {})
        alle_tids |= set((snap.get("build_runs") or {}))
    namen = _namen(alle_tids)

    gesamt_zuviel = {}
    for lab, (pl, ansp) in anspruch_je_plan.items():
        snap = MH._plan_snapshot_unpack(
            (pl.get("frozen") or {}).get("plan_snapshot") or {})
        runs = {int(k): int(v or 0)
                for k, v in (snap.get("build_runs") or {}).items()}
        mats = snap.get("build_mats") or {}
        if not runs or not mats:
            p(f"PLAN {lab}: kein brauchbarer Schnappschuss - uebersprungen.")
            p("")
            continue
        # SCHON GEBAUT - dieselbe Funktion wie die Stock-locations-Seite.
        gebaut = lagerorte.gebaute_runs(pl, zuordnung) or {}
        offen = {t: max(0, r - int(gebaut.get(t, 0) or 0))
                 for t, r in runs.items()}
        # WAS DIE OFFENEN RUNS NOCH VERBRAUCHEN - anteilig, aufgerundet
        # (dieselbe Regel wie `restbedarf_map`: lieber eins zu viel).
        verbrauch, verbraucher = {}, {}
        for t, r in runs.items():
            if r <= 0 or offen.get(t, 0) <= 0:
                continue
            anteil = float(offen[t]) / float(r)
            for m, q in (mats.get(t) or []):
                m = int(m)
                _n = int(-(-float(q) * anteil // 1))      # ceil
                if _n <= 0:
                    continue
                verbrauch[m] = verbrauch.get(m, 0) + _n
                verbraucher.setdefault(m, []).append(
                    (t, offen[t], r, _n))
        # INVENTION-MATERIAL STEHT NICHT IN `build_mats` (es hat eigene
        # Felder, damit seine Kosten nicht doppelt zaehlen). Ohne diese
        # Zeilen meldete der Bericht JEDEN Datacore als "kein Verbraucher
        # mehr" - ein Fehlalarm des WERKZEUGS, kein Befund. Gezaehlt wird
        # der volle Posten: ob die Invention schon gelaufen ist, sagt der
        # Schnappschuss nicht (das weiss nur der Blueprints-Reiter, s.
        # emm637).
        for _feld in ("inv_stock_used", "inv_buy"):
            for _m, _q in (snap.get(_feld) or {}).items():
                try:
                    _m, _q = int(_m), int(_q or 0)
                except (TypeError, ValueError):
                    continue
                if _q <= 0:
                    continue
                verbrauch[_m] = verbrauch.get(_m, 0) + _q
                verbraucher.setdefault(_m, []).append((-1, 0, 0, _q))

        p("-" * 78)
        p(f"PLAN  {lab}   (Schloss an · {len(ansp)} Posten reserviert)")
        p("-" * 78)
        p(f"  Items im Plan: {len(runs)} · davon noch offen: "
          f"{sum(1 for t in runs if offen.get(t, 0) > 0)}")
        # NUR WAS ZAEHLT (Regel 6): die Mengen werden je Verbraucher
        # AUFGERUNDET - ein Anspruch liegt dadurch fast immer ein paar
        # Stueck ueber dem Verbrauch. Das ist Rundung, kein Befund.
        # Gemeldet wird deshalb nur, was entweder GAR KEINEN offenen
        # Verbraucher mehr hat oder spuerbar darueber liegt (ueber 2 % und
        # mehr als 10 Stueck).
        zuviel = []
        for t, q in ansp.items():
            vb = int(verbrauch.get(t, 0))
            if q <= vb:
                continue
            d = q - vb
            if vb > 0 and (d <= 10 or d < q * 0.02):
                continue                 # Rundungsrest, nicht melden
            zuviel.append((d, t, q, vb))
        zuviel.sort(reverse=True)
        if not zuviel:
            p("  ALLES BERECHTIGT: kein Posten ueber dem, was die offenen")
            p("  Runs noch verbrauchen.")
        else:
            p(f"  {'MATERIAL':30} {'ANSPRUCH':>12} {'VERBRAUCH':>12} "
              f"{'ZU VIEL':>12}  VERBRAUCHER (offene Runs)")
            for d, t, q, vb in zuviel[:30]:
                _vb = verbraucher.get(t) or []
                _txt = ", ".join(
                    f"{str(namen.get(_i) or _i)[:22]} {_o}/{_r}"
                    for _i, _o, _r, _n in sorted(_vb, key=lambda x: -x[3])[:3]
                ) or "KEIN offener Verbraucher mehr"
                p(f"  {str(namen.get(t) or t)[:30]:30} {_z(q):>12} "
                  f"{_z(vb):>12} {_z(d):>12}  {_txt}")
                gesamt_zuviel[t] = gesamt_zuviel.get(t, 0) + d
            if len(zuviel) > 30:
                p(f"  ... und {len(zuviel) - 30} weitere")
            p("")
            p(f"  SUMME zu viel gehalten: {_z(sum(x[0] for x in zuviel))} "
              f"Stueck ueber {len(zuviel)} Posten.")
        p("")

    # ---- WARUM schrumpft der Anspruch nicht? ------------------------------
    p("=" * 78)
    p("WARUM SCHRUMPFT DER ANSPRUCH NICHT? - zwei Fortschritts-Sichten")
    p("=" * 78)
    p("  Der BEDARF rechnet mit `gebaute_runs`: alle Jobs, die laut")
    p("  Datenbank diesem Plan gehoeren, plus Hand-Haken - ohne Zeitfilter.")
    p("  Die RESERVIERUNG rechnet mit `belegte_runs_seit`: dieselben Jobs,")
    p("  aber NUR die, die der Bestands-Stand schon gesehen hat")
    p("  (`ts <= stock_seen_ts`), plus Haken mit Zeitstempel.")
    p("  Sieht die zweite Sicht weniger Fortschritt, bleibt der Anspruch")
    p("  stehen, obwohl der Bedarf laengst gefallen ist - genau das")
    p("  hungert spaetere Plaene aus.")
    p("")
    for lab, (pl, ansp) in anspruch_je_plan.items():
        snap = MH._plan_snapshot_unpack(
            (pl.get("frozen") or {}).get("plan_snapshot") or {})
        runs = {int(k): int(v or 0)
                for k, v in (snap.get("build_runs") or {}).items()}
        if not runs:
            continue
        mats = snap.get("build_mats") or {}
        _geb = lagerorte.gebaute_runs(pl, zuordnung) or {}
        try:
            _bel = MH._belegt_fuer_plan(pl) or {}
        except Exception as _e:
            _bel = {}
            p(f"  {lab}: _belegt_fuer_plan scheiterte: {type(_e).__name__}: {_e}")
        _hak = {}
        for _k, _v in (pl.get("checked_runplan_runs") or {}).items():
            try:
                _hak[int(str(_k).rpartition("|")[2])] = int(_v or 0)
            except (TypeError, ValueError):
                continue
        _sst = (pl.get("frozen") or {}).get("stock_seen_ts")
        p(f"  PLAN {lab}  (stock_seen_ts {_zeit_kurz(_sst)})")
        _diff = []
        for t, r in runs.items():
            g = int(_geb.get(t, 0) or 0)
            b = max(int(_bel.get(t, 0) or 0), int(_hak.get(t, 0) or 0))
            if g > b:
                _diff.append((g - b, t, r, g, b))
        _diff.sort(reverse=True)
        if not _diff:
            p("      beide Sichten sehen denselben Fortschritt.")
        else:
            p(f"      {'ITEM':30} {'PLAN-RUNS':>10} {'BEDARF SIEHT':>13} "
              f"{'RESERV. SIEHT':>14} {'UNTERSCHIED':>12}")
            for d, t, r, g, b in _diff[:20]:
                p(f"      {str(namen.get(t) or t)[:30]:30} {_z(r):>10} "
                  f"{_z(g):>13} {_z(b):>14} {_z(d):>12}")
            if len(_diff) > 20:
                p(f"      ... und {len(_diff) - 20} weitere")
            p(f"      -> {len(_diff)} Items, bei denen die Reservierung "
              f"weniger Fortschritt sieht als der Bedarf.")
            # WARUM SIEHT SIE WENIGER? Der einzige Unterschied ist der
            # Zeitfilter `ts <= stock_seen_ts`. Steht die Zuordnung eines
            # Jobs SPAETER als der letzte Bestands-Stand dieses Plans, faellt
            # sie fuer die Reservierung weg - und `stock_seen_ts` rueckt nur
            # vor, wenn man DIESEN Plan oeffnet und Assets laedt. Ein Plan,
            # den man laenger nicht geoeffnet hat, haelt dadurch alles fest.
            try:
                _zu_pl = store.job_zuordnung_fuer_plan(pl.get("id")) or {}
            except Exception:
                _zu_pl = {}
            _ts_je_item = {}
            for _e in _zu_pl.values():
                try:
                    _t = int(_e.get("type_id") or 0)
                    _ts = float(_e.get("ts") or 0.0)
                except (TypeError, ValueError):
                    continue
                if _t:
                    _ts_je_item[_t] = max(_ts_je_item.get(_t, 0.0), _ts)
            _nach = [(t, _ts_je_item.get(t))
                     for _d, t, _r, _g, _b in _diff
                     if _ts_je_item.get(t) and _sst
                     and _ts_je_item[t] > float(_sst)]
            if _nach:
                p(f"      URSACHE: bei {len(_nach)} davon ist die "
                  f"Job-Zuordnung JUENGER als der Bestands-Stand")
                p(f"      dieses Plans ({_zeit_kurz(_sst)}) - sie zaehlt "
                  f"deshalb nicht:")
                for t, ts in _nach[:8]:
                    p(f"          {str(namen.get(t) or t)[:34]:34} "
                      f"zugeordnet {_zeit_kurz(ts)}")
            else:
                p("      (Zeitfilter ist NICHT die Ursache - die Zuordnungen "
                  "sind aelter als der Bestands-Stand.)")
        # SCHRITT FUER SCHRITT: wo genau bleibt die Abbuchung haengen?
        # `plan_anspruch_mitlaufend` faengt JEDE Ausnahme ab und gibt dann
        # die GESPEICHERTE Karte zurueck (sicherer Rueckfall, Regel 3) -
        # von aussen sieht ein Absturz deshalb aus wie "nichts abzubuchen".
        # Hier wird derselbe Weg offen nachgelaufen.
        _rm_gespeichert = {int(t): int(q or 0)
                           for t, q in (pl.get("reserve_map") or {}).items()}
        try:
            _bel2 = MH._belegt_fuer_plan(pl) or {}
        except Exception as _e:
            _bel2 = {}
            p(f"      _belegt_fuer_plan WIRFT: {type(_e).__name__}: {_e}")
        try:
            # DENSELBEN WEG wie `plan_anspruch_mitlaufend` - inklusive der
            # Reprocessing-Umbuchung (emm524). Ohne sie waere der Vergleich
            # unten schief und meldete einen Unterschied, den es nicht gibt.
            _b2 = dict(MH._plan_reserve_map(snap) or {})
            try:
                from eve_trader import reprocess as _rp
                _b2 = _rp.anspruch_anpassen(
                    _b2, (snap.get("reprocess") or {}).get("schritte"),
                    pl.get("checked_runplan"))
            except Exception:
                pass
            _direkt = MH._reserve_map_mitlaufend(
                snap, _b2,
                pl.get("checked_runplan_ts") or {},
                pl.get("assignments") or [], _sst,
                belegt=_bel2, haken_runs=pl.get("checked_runplan_runs"))
            _fehler = None
        except Exception as _e:
            _direkt, _fehler = None, f"{type(_e).__name__}: {_e}"
        p(f"      ABLAUF: belegt kennt {len(_bel2)} Items "
          f"({_z(sum(int(v or 0) for v in _bel2.values()))} Runs) · "
          f"gespeicherte Karte {len(_rm_gespeichert)} Posten")
        if _fehler:
            p(f"      !! _reserve_map_mitlaufend WIRFT: {_fehler}")
            p("      -> deshalb faellt der Anspruch auf die GESPEICHERTE "
              "Karte zurueck und schrumpft nie.")
        else:
            _summe_d = sum(_direkt.values())
            _summe_a = sum(ansp.values())
            p(f"      direkt gerechnet: {_z(_summe_d)} Stueck · "
              f"was der Plan benutzt: {_z(_summe_a)} Stueck")
            if _summe_d != _summe_a:
                p("      !! UNTERSCHIED - der benutzte Anspruch stammt NICHT "
                  "aus dieser Rechnung.")
                _wie_rm = sum(_rm_gespeichert.values())
                p(f"         (gespeicherte Karte waere: {_z(_wie_rm)})")
            else:
                p("      (beides gleich - die Abbuchung laeuft, sie findet "
                  "nur nichts abzubuchen)")

        # Ueberhaenge dieses Plans HIER neu bilden - die erste Schleife
        # hat ihre eigenen Variablen, ein Zugriff darauf haette die Zahlen
        # des zuletzt gelaufenen Plans gezeigt.
        _offen2 = {t: max(0, r - int(_geb.get(t, 0) or 0))
                   for t, r in runs.items()}
        _verbr2 = {}
        for t, r in runs.items():
            if r <= 0 or _offen2.get(t, 0) <= 0:
                continue
            _a2 = float(_offen2[t]) / float(r)
            for m, q in (mats.get(t) or []):
                _n2 = int(-(-float(q) * _a2 // 1))
                if _n2 > 0:
                    _verbr2[int(m)] = _verbr2.get(int(m), 0) + _n2
        for _feld2 in ("inv_stock_used", "inv_buy"):
            for _m2, _q2 in (snap.get(_feld2) or {}).items():
                try:
                    _verbr2[int(_m2)] = _verbr2.get(int(_m2), 0) + int(_q2 or 0)
                except (TypeError, ValueError):
                    continue
        zuviel = sorted(((int(q) - int(_verbr2.get(t, 0)), int(t), int(q),
                          int(_verbr2.get(t, 0)))
                         for t, q in ansp.items()
                         if int(q) > int(_verbr2.get(t, 0))), reverse=True)

        # JE VERBRAUCHER DER DREI GROESSTEN UEBERHAENGE: welche Zahl hat
        # welche Sicht? Hier kann sich nichts mehr verstecken.
        if zuviel:
            p("      VERBRAUCHER DER DREI GROESSTEN UEBERHAENGE "
              "(Plan-Runs / Bedarf-Sicht / Reservierungs-Sicht / Haken):")
            for _d3, _t3, _q3, _vb3 in zuviel[:3]:
                p(f"        {str(namen.get(_t3) or _t3)[:30]} "
                  f"(Anspruch {_z(_q3)}):")
                _irgend = False
                for _it3, _lst3 in (mats or {}).items():
                    for _m3, _mq3 in (_lst3 or []):
                        if int(_m3) != int(_t3):
                            continue
                        _irgend = True
                        p(f"            {str(namen.get(_it3) or _it3)[:28]:28} "
                          f"braucht {_z(_mq3):>12} · Runs {_z(runs.get(_it3,0)):>8}"
                          f" · Bedarf sieht {_z(_geb.get(_it3,0)):>8}"
                          f" · Reserv. sieht {_z(_bel.get(_it3,0)):>8}"
                          f" · Haken {_z(_hak.get(_it3,0)):>8}")
                if not _irgend:
                    p("            (kein Verbraucher im Rezeptbaum - reines "
                      "Invention-/Restmaterial)")
            p("")

        # WORAUS BESTEHT DER ANSPRUCH? Ein Plan reserviert nicht nur, was er
        # KAUFT, sondern auch, was er SELBST HERSTELLT ("liegt in meinem
        # Hangar und gehoert mir"). Sieht man das nicht, haelt man einen
        # berechtigten Anspruch fuer eine Leiche - und umgekehrt.
        _basis = MH._plan_reserve_map(snap) or {}
        _gross = sorted(((int(q or 0), int(t)) for t, q in ansp.items()
                         if int(q or 0) > 0), reverse=True)[:8]
        if _gross:
            p(f"      HERKUNFT der groessten Posten "
              f"(Basis = was der Schnappschuss reserviert):")
            p(f"      {'MATERIAL':28} {'ANSPRUCH':>11} {'BASIS':>11} "
              f"{'kauft':>10} {'aus Lager':>10} {'baut selbst':>12}")
            for q, t in _gross:
                p(f"      {str(namen.get(t) or t)[:28]:28} {_z(q):>11} "
                  f"{_z(_basis.get(t, 0)):>11} "
                  f"{_z((snap.get('buy') or {}).get(t, 0)):>10} "
                  f"{_z((snap.get('stock_used') or {}).get(t, 0)):>10} "
                  f"{_z((snap.get('build_made') or {}).get(t, 0)):>12}")
        p("")

    # ---- Summe aller Anspruechee gegen den echten Bestand -----------------
    p("=" * 78)
    p("ALLE ANSPRUECHE GEGEN DEN ECHTEN BESTAND")
    p("=" * 78)
    live = {}
    try:
        client_id = settings.get("client_id") or config.EMBEDDED_CLIENT_ID
        ctypes = esi.container_type_ids_safe()
        for ch in (store.list_characters() or []):
            cid = int(ch["character_id"])
            nm = ch.get("character_name") or str(cid)
            try:
                a = esi._fetch_all_assets(client_id, cid)
            except Exception:
                continue
            for zl in lagerorte.zeilen_aus_assets(a, ctypes, nm, "char"):
                live[int(zl["tid"])] = live.get(int(zl["tid"]), 0) \
                    + int(zl.get("menge") or 0)
    except Exception as e:
        p(f"  Bestand nicht abrufbar: {type(e).__name__}: {e}")
    if live:
        summe = {}
        for lab, (pl, ansp) in anspruch_je_plan.items():
            for t, q in ansp.items():
                summe[t] = summe.get(t, 0) + int(q or 0)
        ueber = sorted(((q - int(live.get(t, 0)), t, q, int(live.get(t, 0)))
                        for t, q in summe.items()
                        if q > int(live.get(t, 0))), reverse=True)
        if not ueber:
            p("  Kein Material ist staerker reserviert, als es existiert.")
        else:
            p(f"  {'MATERIAL':30} {'RESERVIERT':>13} {'EXISTIERT':>13} "
              f"{'UEBERBUCHT':>13}  WER HAELT")
            for d, t, q, lv in ueber[:30]:
                wer = " · ".join(
                    f"{lab}: {_z(a.get(t, 0))}"
                    for lab, (pl, a) in anspruch_je_plan.items() if a.get(t))
                p(f"  {str(namen.get(t) or t)[:30]:30} {_z(q):>13} "
                  f"{_z(lv):>13} {_z(d):>13}  {wer[:50]}")
            if len(ueber) > 30:
                p(f"  ... und {len(ueber) - 30} weitere")
    p("")
    p("=" * 78)
    p("URTEIL")
    p("=" * 78)
    if not gesamt_zuviel:
        p("  Kein Plan haelt Material fest, das er nicht mehr verbraucht.")
        p("  Die Reservierungen sind berechtigt - wer spaeter kommt, sieht")
        p("  zu Recht weniger freien Bestand.")
    else:
        p(f"  {len(gesamt_zuviel)} Materialien werden festgehalten, obwohl")
        p("  die offenen Runs sie nicht mehr (ganz) verbrauchen:")
        for t, d in sorted(gesamt_zuviel.items(), key=lambda kv: -kv[1])[:15]:
            p(f"      {str(namen.get(t) or t)[:34]:34} zu viel: {_z(d)}")

    os.makedirs(os.path.dirname(BERICHT), exist_ok=True)
    with open(BERICHT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(aus) + "\n")
    print("\n".join(aus))
    print("")
    print(f"Geschrieben: {BERICHT}")


if __name__ == "__main__":
    main()
