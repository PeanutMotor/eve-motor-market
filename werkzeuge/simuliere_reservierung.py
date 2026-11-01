"""Stellt den Fall nach, der emm638 ausgeloest hat - OHNE darauf zu warten.

NUTZER 23.10.2026: "simuliere mache tests".

DER FALL (gemessen an seiner settings.json, Plan "Minmatar 1"):
einfrieren um 19:23:53, ingame bauen, um 20:03 abhaken, Plan NICHT wieder
oeffnen. Die ESI-Verzugs-Sperre verlangt `Haken-ts <= stock_seen_ts`, und
`stock_seen_ts` waechst NUR beim Oeffnen GENAU DIESES Plandialogs. Also
gilt der Haken nie - der Plan haelt Material fest, das laengst verbaut
ist, und NIMMT ES DEN ANDEREN PLAENEN WEG. Die kaufen es dann nach,
obwohl es im Hangar liegt.

WAS DIESES WERKZEUG MACHT: es rechnet DEINE echten Plaene zweimal durch,
mit DENSELBEN Funktionen des Programms (`plan_anspruch_mitlaufend`,
`_reserved_by_other_plans`, `bestand_nach_reservierungen`,
`fehlbedarf_vorschau`) - keine nachgebaute Zweitrechnung:

  ALT  `bestand_gesehen_bis` = nur der plan-eigene `frozen.stock_seen_ts`
       So lief es bis emm638.
  NEU  `bestand_gesehen_bis` = max(plan-eigener Stempel, globaler
       `asset_snapshot_info()["checked_at"]`)
       So laeuft es seit emm638 - "wann hat ESI den Bestand gesehen" ist
       eine Eigenschaft der ASSET-DATEN, nicht eines einzelnen Plans.

Und es stellt den Fall KUENSTLICH her (`--verzug`): alle Haken werden in
einer Arbeitskopie auf `stock_seen_ts + N Sekunden` gesetzt - genau die
Lage, die bei dir entsteht, wenn du nach dem Einfrieren baust und hakst.
Vorgabe 2400 s = dein gemessener Abstand (19:23:53 -> 20:03/20:04).

Liest nur, aendert NICHTS an der settings.json. ESI wird fuer den echten
Hangar-Bestand versucht; ohne ESI nimmt der Bericht den Einfrier-Bestand
und sagt das dazu.

AUFRUF:
    python werkzeuge\\simuliere_reservierung.py
    python werkzeuge\\simuliere_reservierung.py --verzug 7200
    python werkzeuge\\simuliere_reservierung.py --echt
    python werkzeuge\\simuliere_reservierung.py --plan Minmatar
"""
import argparse
import copy
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import config, store                      # noqa: E402
from eve_trader.ui.mw_helpers import (MainWindowHelpers,   # noqa: E402
                                      fehlbedarf_vorschau,
                                      restbedarf_map)

FASSUNG = 1
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERICHT = os.path.join(WURZEL, "berichte", "reservierung_simulation_bericht.txt")


def _z(n):
    try:
        return f"{int(n):,}".replace(",", "'")
    except (TypeError, ValueError):
        return "?"


def _zeit(ts):
    try:
        return time.strftime("%d.%m. %H:%M:%S", time.localtime(float(ts)))
    except (TypeError, ValueError):
        return "-"


def _unpack(v):
    """settings.json speichert int-Schluessel als Text ("-" = negativ)."""
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
    try:
        with open(config.settings_path(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return config.load_settings()


def _out_qty_map(tids):
    out = {}
    for pfad in (os.path.join(WURZEL, "sde_kompakt.db"),
                 os.path.join(config.app_data_dir(), "industry.db")):
        if not os.path.exists(pfad):
            continue
        try:
            con = sqlite3.connect(f"file:{pfad}?mode=ro", uri=True)
            for t in tids:
                if t in out:
                    continue
                r = con.execute(
                    "SELECT quantity FROM products WHERE product_id=? LIMIT 1",
                    (int(t),)).fetchone()
                if r and int(r[0] or 0) > 0:
                    out[int(t)] = int(r[0])
            con.close()
        except Exception:
            continue
    return out


def _namen(tids):
    try:
        return store.cached_names(sorted(tids)) or {}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# ALT / NEU umschalten - EINE Stelle, und zwar die echte Funktion des
# Programms. Nichts nachgebaut: der Unterschied zwischen beiden Laeufen ist
# genau der Stempel, den `bestand_gesehen_bis` liefert.
# ---------------------------------------------------------------------------
_NEU = MainWindowHelpers.bestand_gesehen_bis


def _alt_stempel(p):
    """Der Stand VOR emm638: nur der plan-eigene Stempel."""
    _v = ((p or {}).get("frozen") or {}).get("stock_seen_ts")
    try:
        return float(_v) if _v is not None else None
    except (TypeError, ValueError):
        return None


class _Weg:
    """`with _Weg("alt"):` schaltet die Rechnung um und raeumt wieder auf."""

    def __init__(self, welcher):
        self.welcher = welcher

    def __enter__(self):
        MainWindowHelpers.bestand_gesehen_bis = staticmethod(
            _alt_stempel if self.welcher == "alt" else _NEU)
        return self

    def __exit__(self, *_a):
        MainWindowHelpers.bestand_gesehen_bis = staticmethod(_NEU)
        return False


def _anspruch_je_plan(settings, plaene):
    return {str(pl.get("label") or pl.get("item_name") or pl.get("id")):
            {int(t): int(q or 0) for t, q in
             (MainWindowHelpers.plan_anspruch_mitlaufend(pl) or {}).items()}
            for pl in plaene}


def _verzug_einbauen(settings, sek):
    """Arbeitskopie, in der JEDER Haken `stock_seen_ts + sek` traegt.

    Genau die Lage beim Nutzer: einfrieren, bauen, haken, Plan nicht
    wieder oeffnen. Die echte settings.json wird NICHT angefasst.
    """
    s = copy.deepcopy(settings)
    getroffen = []
    for pl in (s.get("bau_saved_plans") or []):
        _sst = (pl.get("frozen") or {}).get("stock_seen_ts")
        _ts = pl.get("checked_runplan_ts") or {}
        if _sst is None or not _ts:
            continue
        try:
            _neu = float(_sst) + float(sek)
        except (TypeError, ValueError):
            continue
        pl["checked_runplan_ts"] = {k: _neu for k in _ts}
        getroffen.append((str(pl.get("label") or pl.get("id")), len(_ts),
                          float(_sst), _neu))
    return s, getroffen


def _hangar(p):
    """Echter Bestand ueber ESI; schlaegt das fehl, wird es gesagt."""
    live, quelle = {}, "ESI (echter Hangar, alle Charaktere)"
    try:
        from eve_trader import esi, lagerorte
        settings = _settings_rohe()
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
                live[int(zl["tid"])] = (live.get(int(zl["tid"]), 0)
                                        + int(zl.get("menge") or 0))
    except Exception as e:
        p(f"  ESI nicht erreichbar ({type(e).__name__}) - Rueckfall.")
    # CORP-HANGAR (use_corp). OHNE DIESEN TEIL LUEGT DER BERICHT: am
    # 24.10.2026 schien Gallente 1 9'718'312 Crystalline Carbonide verloren
    # zu haben - es lag im Corp-Hangar. Der Bauplan selbst zaehlt ihn mit
    # (`_corp_bau_daten`), also muss dieser Bericht es auch.
    # EIN Abruf je Corporation (derselbe Riegel gegen die Verdreifachung
    # wie in `corp.abrufplan`): drei Charaktere derselben Corp liefern
    # denselben Hangar, dreifach gezaehlt waere es schlimmer als gar nicht.
    try:
        from eve_trader import corp as _corp, esi as _esi2
        s2 = _settings_rohe()
        if s2.get("use_corp"):
            _div = _corp.divisions_bereinigt(s2.get("corp_divisions"))
            _cid2 = s2.get("client_id") or config.EMBEDDED_CLIENT_ID
            _ct2 = _esi2.container_type_ids_safe()
            _fertig = set()
            for ch in (store.list_characters() or []):
                _c = int(ch["character_id"])
                try:
                    _corp_id = _esi2.fetch_character_corporation(_c)
                except Exception:
                    continue
                if not _corp_id or int(_corp_id) in _fertig:
                    continue
                try:
                    _a2 = _esi2.fetch_corporation_assets(_cid2, _c,
                                                         int(_corp_id))
                except Exception:
                    continue      # keine Rolle / kein Scope - naechster
                _fertig.add(int(_corp_id))
                _summe, _je = _corp.corp_bestand(_a2, _div, None, _ct2)
                for _t2, _q2 in (_summe or {}).items():
                    live[int(_t2)] = live.get(int(_t2), 0) + int(_q2 or 0)
            if _fertig:
                p(f"  Corp-Hangar mitgezaehlt: {_z(len(_fertig))} "
                  f"Corporation(en), Divisions {_div}")
            else:
                p("  use_corp ist AN, aber kein Corp-Abruf ging durch "
                  "(Rolle/Scope?) - die Zahlen unten sind dann zu klein.")
    except Exception as e:
        p(f"  Corp-Bestand nicht abrufbar: {type(e).__name__}: {e}")
    if not live:
        quelle = ("EINFRIER-Bestand aus settings.json (ESI nicht abrufbar) "
                  "- die absoluten Zahlen sind damit nur ein Naeherungswert, "
                  "der Unterschied ALT/NEU bleibt aussagekraeftig")
        for pl in (_settings_rohe().get("bau_saved_plans") or []):
            for t, q in (_unpack((pl.get("frozen") or {}).get("stock")
                                 or {})).items():
                try:
                    live[int(t)] = max(live.get(int(t), 0), int(q or 0))
                except (TypeError, ValueError):
                    continue
    return live, quelle


def _bedarf(pl):
    """Was dieser Plan fuer seine noch offenen Runs braucht - dieselbe
    Funktion wie das Programm (`restbedarf_map`)."""
    snap = _unpack((pl.get("frozen") or {}).get("plan_snapshot") or {})
    runs = {int(k): int(v or 0)
            for k, v in (snap.get("build_runs") or {}).items()}
    mats = snap.get("build_mats") or {}
    if not runs or not mats:
        return None
    _r, need = restbedarf_map(runs, mats, {})
    return {int(t): int(q or 0) for t, q in (need or {}).items()}


def _fremd_je_plan(settings, plaene):
    """{Plan: {type_id: was ihm ALLE ANDEREN Plaene wegnehmen}} - die echte
    Funktion des Programms, mit allen Rang- und Buendel-Regeln."""
    aus = {}
    for pl in plaene:
        lab = str(pl.get("label") or pl.get("item_name") or pl.get("id"))
        fremd, _l = MainWindowHelpers._reserved_by_other_plans(
            settings, pl.get("id"))
        aus[lab] = {int(t): int(q or 0) for t, q in (fremd or {}).items()}
    return aus


def _schreiben(aus):
    os.makedirs(os.path.dirname(BERICHT), exist_ok=True)
    with open(BERICHT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(aus) + "\n")
    print("\n".join(aus))
    print(f"\nBericht: {BERICHT}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verzug", type=int, default=2400,
                    help="Sekunden, die der Haken NACH dem Einfrieren "
                         "gesetzt wird (Vorgabe 2400 = gemessener Fall)")
    ap.add_argument("--echt", action="store_true",
                    help="nichts nachstellen, nur deinen echten Stand "
                         "alt gegen neu")
    ap.add_argument("--plan", default=None,
                    help="nur Plaene mit diesem Namensteil")
    args = ap.parse_args()

    aus = []
    p = aus.append
    p("=" * 78)
    p(f"RESERVIERUNGS-SIMULATION - der Fall aus emm638 (Fassung {FASSUNG})")
    p(f"Erstellt: {time.strftime('%Y-%m-%d %H:%M:%S')} (Ortszeit)")
    p("=" * 78)
    p("")
    p("  Echte Plaene, echte Haken, echte Zeitstempel aus deiner")
    p("  settings.json. Gerechnet wird mit den Funktionen des Programms,")
    p("  zweimal - einmal mit dem alten Stempel, einmal mit dem neuen.")
    p("")

    settings = _settings_rohe()
    alle = [pl for pl in (settings.get("bau_saved_plans") or [])
            if isinstance(pl, dict) and not pl.get("done_manual")]
    if args.plan:
        alle = [pl for pl in alle if args.plan.lower() in
                str(pl.get("label") or pl.get("item_name") or "").lower()]
    plaene = [pl for pl in alle
              if ((pl.get("frozen") or {}).get("plan_snapshot"))]
    if not plaene:
        p("  Keine aktiven, eingefrorenen Plaene gefunden - nichts zu zeigen.")
        _schreiben(aus)
        return

    try:
        _glob = (store.asset_snapshot_info() or {}).get("checked_at")
    except Exception:
        _glob = None

    # ---- 1) Ausgangslage --------------------------------------------------
    p("=" * 78)
    p("1) AUSGANGSLAGE - welche Stempel stehen da?")
    p("=" * 78)
    p(f"  Globaler Bestands-Abruf (`asset_snapshot_info.checked_at`): "
      f"{_zeit(_glob)}")
    if _glob is None:
        p("  ACHTUNG: kein globaler Stempel - dann kann emm638 nichts")
        p("  verbessern (max() von einem Wert ist dieser Wert). Das ist der")
        p("  Fall direkt nach dem Start, bevor der erste vollstaendige")
        p("  Abruf durch ist.")
    p("")
    p(f"  {'PLAN':28} {'EINGEFROREN (stock_seen_ts)':>28} {'HAKEN':>7} "
      f"{'DAVON SPAETER':>14}")
    for pl in plaene:
        lab = str(pl.get("label") or pl.get("item_name") or "?")
        _sst = (pl.get("frozen") or {}).get("stock_seen_ts")
        _ts = pl.get("checked_runplan_ts") or {}
        try:
            _spaet = sum(1 for v in _ts.values()
                         if _sst is not None and float(v) > float(_sst))
        except (TypeError, ValueError):
            _spaet = 0
        p(f"  {lab[:28]:28} {_zeit(_sst):>28} {len(_ts):>7} {_spaet:>14}")
    p("")
    p("  \"DAVON SPAETER\" = Haken, die NACH dem Einfrieren gesetzt wurden.")
    p("  Genau die hat der alte Weg verworfen - fuer immer, solange der")
    p("  Plan nicht wieder geoeffnet wird.")
    p("")

    laeufe = [("DEIN ECHTER STAND", settings, None)]
    if not args.echt:
        s2, getroffen = _verzug_einbauen(settings, args.verzug)
        laeufe.append((f"NACHGESTELLT: jeder Haken {args.verzug} s nach dem "
                       f"Einfrieren", s2, getroffen))

    nummer = 1
    for titel, s_lauf, getroffen in laeufe:
        nummer += 1
        pl_lauf = [pl for pl in (s_lauf.get("bau_saved_plans") or [])
                   if isinstance(pl, dict) and not pl.get("done_manual")
                   and ((pl.get("frozen") or {}).get("plan_snapshot"))
                   and (not args.plan or args.plan.lower() in
                        str(pl.get("label") or pl.get("item_name")
                            or "").lower())]
        p("=" * 78)
        p(f"{nummer}) {titel}")
        p("=" * 78)
        if getroffen:
            p("  Arbeitskopie im Speicher - deine settings.json bleibt, wie")
            p("  sie ist. Verschoben:")
            for lab, n, _alt_ts, _neu_ts in getroffen:
                p(f"    {lab[:30]:30} {n:>3} Haken  "
                  f"{_zeit(_alt_ts)} -> {_zeit(_neu_ts)}")
            p("")

        with _Weg("alt"):
            a_alt = _anspruch_je_plan(s_lauf, pl_lauf)
        with _Weg("neu"):
            a_neu = _anspruch_je_plan(s_lauf, pl_lauf)

        namen_sammler = set()
        for d in list(a_alt.values()) + list(a_neu.values()):
            namen_sammler.update(d)
        namen = _namen(namen_sammler)

        p(f"  {'PLAN':28} {'ANSPRUCH ALT':>14} {'ANSPRUCH NEU':>14} "
          f"{'ZU VIEL GEHALTEN':>17}")
        ges_alt = ges_neu = 0
        for lab in a_alt:
            sa, sn = sum(a_alt[lab].values()), sum(a_neu.get(lab, {}).values())
            ges_alt += sa
            ges_neu += sn
            p(f"  {lab[:28]:28} {_z(sa):>14} {_z(sn):>14} {_z(sa - sn):>17}")
        p(f"  {'SUMME':28} {_z(ges_alt):>14} {_z(ges_neu):>14} "
          f"{_z(ges_alt - ges_neu):>17}")
        p("")

        # Die groessten Einzelposten, die der alte Weg festgehalten haette.
        diff = {}
        for lab in a_alt:
            for t, q in a_alt[lab].items():
                d = q - int(a_neu.get(lab, {}).get(t, 0))
                if d > 0:
                    diff[(lab, t)] = d
        if not diff:
            p("  Kein Plan haelt in diesem Lauf etwas zu Unrecht fest.")
        else:
            p("  GROESSTE POSTEN, DIE DER ALTE WEG FESTGEHALTEN HAETTE:")
            p(f"  {'PLAN':24} {'MATERIAL':30} {'ZU VIEL':>13}")
            for (lab, t), d in sorted(diff.items(), key=lambda x: -x[1])[:15]:
                p(f"  {lab[:24]:24} {str(namen.get(t) or t)[:30]:30} "
                  f"{_z(d):>13}")
            if len(diff) > 15:
                p(f"  ... und {len(diff) - 15} weitere Posten")
        p("")

    # ---- Letzter Abschnitt: was es die anderen Plaene kostet --------------
    nummer += 1
    p("=" * 78)
    p(f"{nummer}) WAS DAS DEN ANDEREN PLAENEN WEGNIMMT")
    p("=" * 78)
    p("  Der festgehaltene Anspruch ist nur die halbe Geschichte - weh tut")
    p("  er erst, wenn ein ANDERER Plan genau dieses Material braucht und")
    p("  es im Hangar liegt. Genau das wird hier gerechnet, Posten fuer")
    p("  Posten:")
    p("")
    p("      umsonst = min( was die anderen Plaene ZU VIEL halten,")
    p("                     was dieser Plan noch braucht,")
    p("                     was wirklich im Hangar liegt )")
    p("")
    p("  Alle drei Groessen kommen aus den Funktionen des Programms")
    p("  (`_reserved_by_other_plans`, `restbedarf_map`, Hangar s.u.).")
    p("")
    live, quelle = _hangar(p)
    p(f"  Hangar-Quelle: {quelle}")
    p(f"  {_z(len(live))} verschiedene Materialien, "
      f"{_z(sum(live.values()))} Stueck")
    p("")
    s_lauf = laeufe[-1][1]
    pl_lauf = [pl for pl in (s_lauf.get("bau_saved_plans") or [])
               if isinstance(pl, dict) and not pl.get("done_manual")
               and ((pl.get("frozen") or {}).get("plan_snapshot"))
               and (not args.plan or args.plan.lower() in
                    str(pl.get("label") or pl.get("item_name") or "").lower())]
    if laeufe[-1][2]:
        p(f"  Gerechnet auf dem NACHGESTELLTEN Stand (Haken "
          f"{args.verzug} s nach dem Einfrieren).")
    else:
        p("  Gerechnet auf deinem ECHTEN Stand.")
    p("")

    with _Weg("alt"):
        f_alt = _fremd_je_plan(s_lauf, pl_lauf)
    with _Weg("neu"):
        f_neu = _fremd_je_plan(s_lauf, pl_lauf)

    umsonst, namen_sammler = {}, set()
    for pl in pl_lauf:
        lab = str(pl.get("label") or pl.get("item_name") or pl.get("id"))
        bedarf = _bedarf(pl)
        if not bedarf:
            continue
        namen_sammler.update(bedarf)
        for t, q_alt in (f_alt.get(lab) or {}).items():
            zuviel = int(q_alt) - int((f_neu.get(lab) or {}).get(t, 0))
            if zuviel <= 0:
                continue
            menge = min(zuviel, int(bedarf.get(t, 0)), int(live.get(t, 0)))
            if menge > 0:
                umsonst[(lab, t)] = menge
    namen = _namen(namen_sammler)

    p(f"  {'PLAN':28} {'POSTEN':>8} {'UMSONST GEKAUFT (Stueck)':>26}")
    ges = 0
    for pl in pl_lauf:
        lab = str(pl.get("label") or pl.get("item_name") or pl.get("id"))
        _p = {k: v for k, v in umsonst.items() if k[0] == lab}
        ges += sum(_p.values())
        p(f"  {lab[:28]:28} {len(_p):>8} {_z(sum(_p.values())):>26}")
    p(f"  {'SUMME':28} {len(umsonst):>8} {_z(ges):>26}")
    p("")
    if umsonst:
        p("  GROESSTE POSTEN, DIE UMSONST GEKAUFT WORDEN WAEREN:")
        p(f"  {'PLAN':24} {'MATERIAL':30} {'STUECK':>13}")
        for (lab, t), d in sorted(umsonst.items(), key=lambda x: -x[1])[:15]:
            p(f"  {lab[:24]:24} {str(namen.get(t) or t)[:30]:30} {_z(d):>13}")
        if len(umsonst) > 15:
            p(f"  ... und {len(umsonst) - 15} weitere Posten")
    else:
        p("  In diesem Lauf wuerde kein Plan Material kaufen, das ein")
        p("  anderer zu Unrecht festhaelt.")
    p("")


    # ---- Urteil ----------------------------------------------------------
    p("=" * 78)
    p("URTEIL")
    p("=" * 78)
    if _glob is None:
        p("  OFFEN: ohne globalen Bestands-Stempel kann der Fix nicht")
        p("  greifen. Lass das Programm einmal einen vollstaendigen")
        p("  Asset-Abruf machen und starte diesen Bericht neu.")
    elif ges > 0:
        p(f"  Der alte Weg haette in diesem Lauf {_z(ges)} Stueck Material")
        p("  nachkaufen lassen, das im Hangar liegt. Genau das ist der")
        p("  Fehler, den du seit Monaten meldest. Mit emm638 faellt er weg.")
    else:
        p("  In diesem Lauf nimmt kein Plan einem anderen etwas weg - der")
        p("  Fehler BEISST GERADE NICHT. Das heisst NICHT, dass er weg")
        p("  waere: er braucht Haken, die nach dem Einfrieren gesetzt")
        p("  wurden, und einen Hangar, der knapp ist. Mit --verzug laesst")
        p("  sich die Lage erzwingen.")
    p("")
    p("  Dieses Werkzeug aendert nichts. Es liest settings.json, die")
    p("  Job-Zuordnung und (wenn moeglich) ESI.")
    _schreiben(aus)


if __name__ == "__main__":
    main()
