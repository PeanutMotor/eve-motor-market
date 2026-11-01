"""WO IST DAS MATERIAL HIN? - die Gegenrichtung zu simuliere_reservierung.

NUTZER 24.10.2026: "bei mir ist es aktuell so, dass ich Sachen nachkaufen
muesste die ich eben nicht im hangar habe! Obwohl ich alles eingekauft
habe fuer alle Bauplaene exakt damals nach Einkaufsliste, halt eine nach
der anderen".

Das ist NICHT der Fehler aus emm638 (der laesst dich Material kaufen, das
DA IST). Hier fehlt wirklich etwas. Dieser Bericht beantwortet drei
Fragen, und zwar mit Belegen statt mit Vermutungen:

  1) HAST DU DIE LISTE WIRKLICH GEKAUFT?
     Was der eingefrorene Plan damals verlangt hat (`buy` im
     Schnappschuss) gegen das, was seit dem Einfrieren wirklich im
     Handelsjournal steht. Kauft jemand die Liste ab, muessen die Zahlen
     zusammenpassen - tun sie es nicht, liegt es am Einkauf. Tun sie es,
     war die LISTE zu klein, und dann ist das ein Programmfehler.

  2) WAS HAT DER PLAN AUS DEM HANGAR EINGEPLANT, DAS NICHT MEHR DA IST?
     Ein Plan deckt einen Teil seines Bedarfs aus dem Bestand
     (`stock_used`) - dafuer steht NICHTS auf der Einkaufsliste. Ist das
     Material inzwischen weg, faellt es durch jedes Raster: die Liste
     fragt nicht danach, und bezahlt hast du es nie. GENAU DAS ist das
     Muster "ich muesste Zeug nachkaufen, das die Liste nie verlangt hat".

  3) WO IST ES HIN?
     Materialbilanz je Luecke: Bestand beim Einfrieren + seither gekauft
     - was die abgehakten Runs ALLER Plaene verbraucht haben (auch der
     abgeschlossenen!) + was sie produziert haben = erwartet. Dagegen der
     echte Hangar. Was dann noch fehlt, ist auf einem anderen Weg
     gegangen (verkauft, vertraglich weg, umgelagert, von Hand verbaut).

Liest nur: settings.json, das Handelsjournal, die Job-Zuordnung und ESI.
Aendert NICHTS.

AUFRUF:
    python werkzeuge\\pruefe_materialbilanz.py
    python werkzeuge\\pruefe_materialbilanz.py --plan Minmatar
    python werkzeuge\\pruefe_materialbilanz.py --zeilen 40
"""
import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import config, store                      # noqa: E402
from eve_trader.ui.mw_helpers import MainWindowHelpers    # noqa: E402

FASSUNG = 1
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERICHT = os.path.join(WURZEL, "berichte", "materialbilanz_bericht.txt")


def _z(n):
    try:
        return f"{int(n):,}".replace(",", "'")
    except (TypeError, ValueError):
        return "?"


def _zeit(ts):
    try:
        return time.strftime("%d.%m.%Y %H:%M", time.localtime(float(ts)))
    except (TypeError, ValueError):
        return "-"


def _settings_rohe():
    try:
        with open(config.settings_path(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return config.load_settings()


def _namen(tids):
    try:
        return store.cached_names(sorted(tids)) or {}
    except Exception:
        return {}


def _out_qty_map(tids):
    """{type_id: Stueck je Run} aus der SDE - fuer die Gutschrift der
    Produktion in der Bilanz."""
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


def _hangar(p):
    """Echter Bestand ueber ESI, alle Charaktere als EIN Hangar (so will es
    der Nutzer: "alle meine Accounts/charaktere haben quasi EIN Bestand")."""
    live = {}
    try:
        from eve_trader import esi, lagerorte
        s = _settings_rohe()
        client_id = s.get("client_id") or config.EMBEDDED_CLIENT_ID
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
        p(f"  ESI nicht erreichbar: {type(e).__name__}: {e}")
        return live
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
    return live


def _laufende_jobs(p):
    """{type_id: Runs}, die GERADE in der Bauschleife sind - Charaktere UND
    Corp, Status active/paused/ready.

    NUTZER 24.10.2026: "wird auch das gechecket was sich aktuell in meinen
    Bauschleifen befindet?" - NEIN, und das war eine echte Luecke. Ein
    laufender Job ist in den Assets ZWEIMAL unsichtbar: seine Zutaten sind
    im Moment des Starts aus dem Hangar verschwunden, und sein Erzeugnis
    gibt es noch nicht. Ohne diese Liste meldet der Bericht genau das als
    "fehlt echt", was gerade voellig planmaessig in der Anlage steht.
    "ready" zaehlt mit: fertig, aber nicht abgeliefert - das Material ist
    weg, das Produkt noch nicht da.

    GIBT (Runs, Liste der Fehlschlaege) ZURUECK (24.10.2026). Vorher
    verschluckte ein `except: continue` jeden Abruffehler still - und
    genau das passierte beim Nutzer um 13:02: ESI lieferte fuenfmal
    hintereinander "504 Gateway Timeout" auf die Job-Endpunkte. Ohne die
    laufenden Jobs eines Charakters meldet die Bilanz Material als
    fehlend, das voellig planmaessig in der Anlage steht - ein
    FALSCHALARM, erzeugt von einer stillen Luecke. Eine Bilanz, die nicht
    sagen kann, worauf sie sich stuetzt, darf kein Urteil faellen.
    """
    aus, luecken = {}, []
    # `jobs` traegt die Rohliste (job_id, product_type_id, runs) - emm694
    # braucht sie, um zugeordnete von unzugeordneten laufenden Jobs zu
    # trennen (Abschnitt 6).
    herkunft = {"char": 0, "corp": 0, "corp_ok": 0, "jobs": []}
    try:
        from eve_trader import esi as _e3
        s3 = _settings_rohe()
        _cid3 = s3.get("client_id") or config.EMBEDDED_CLIENT_ID
        for ch in (store.list_characters() or []):
            try:
                for j in (_e3.fetch_active_jobs(_cid3,
                                                int(ch["character_id"])) or []):
                    _pt = j.get("product_type_id")
                    if not _pt:
                        continue
                    aus[int(_pt)] = aus.get(int(_pt), 0) + int(j.get("runs") or 0)
                    herkunft["char"] += int(j.get("runs") or 0)
                    herkunft["jobs"].append((j.get("job_id"), int(_pt),
                                             int(j.get("runs") or 0)))
            except Exception as _e_ch:
                luecken.append(f"{ch.get('character_name') or ch.get('character_id')}: "
                               f"{type(_e_ch).__name__}")
                continue
        if s3.get("use_corp"):
            _fertig3, _corp_fehl3 = set(), {}
            for ch in (store.list_characters() or []):
                _c = int(ch["character_id"])
                try:
                    _corp_id = _e3.fetch_character_corporation(_c)
                except Exception:
                    continue
                if not _corp_id or int(_corp_id) in _fertig3:
                    continue
                try:
                    _js = _e3.fetch_corporation_jobs(_cid3, _c, int(_corp_id))
                except Exception as _e_co:
                    # WEITERPROBIEREN, ABER NUR EINMAL MELDEN.
                    # ZWEI FEHLER AN DERSELBEN STELLE, BEIDE MEINE:
                    # (1) Urspruenglich wurde der Fehler ganz
                    #     verschluckt - eine stille Luecke.
                    # (2) Dann habe ich die Corp beim Fehlschlag
                    #     ABGEHAKT, damit die Meldung nicht sechsmal
                    #     dasteht. Das war schlimmer: der Nutzer hat
                    #     genau EINEN Charakter mit Corp-Rolle unter
                    #     neun ("ich habe nur 1 charakter der Corp Rolle
                    #     hat ... das ist mein trading char"). Steht der
                    #     nicht an erster Stelle, gibt der Abruf nach
                    #     dem ersten Fehlschlag auf und die Corp-Jobs
                    #     waeren NIE mehr gekommen - aus einer
                    #     Lesbarkeits-Verbesserung waere ein echter
                    #     Datenverlust geworden.
                    # RICHTIG: jeden Charakter probieren (einer hat die
                    # Rolle), und erst NACH der Schleife melden, wenn
                    # KEINER durchkam. Genau so macht es der
                    # Corp-Hangar oben schon seit emm-Zeiten.
                    _corp_fehl3[int(_corp_id)] = type(_e_co).__name__
                    continue
                _fertig3.add(int(_corp_id))
                herkunft["corp_ok"] += 1
                for j in (_js or []):
                    _pt = j.get("product_type_id")
                    if not _pt:
                        continue
                    aus[int(_pt)] = aus.get(int(_pt), 0) + int(j.get("runs") or 0)
                    herkunft["corp"] += int(j.get("runs") or 0)
                    herkunft["jobs"].append((j.get("job_id"), int(_pt),
                                             int(j.get("runs") or 0)))
            # Erst JETZT melden - und nur Corps, bei denen KEIN einziger
            # Charakter durchkam. Eine Corp, die ueber irgendeinen
            # Charakter erreichbar war, ist vollstaendig gelesen.
            for _cid_f, _art_f in _corp_fehl3.items():
                if int(_cid_f) not in _fertig3:
                    luecken.append(f"Corp {_cid_f}: {_art_f} "
                                   f"(kein Charakter mit Rolle)")
    except Exception as e:
        p(f"  Laufende Jobs nicht abrufbar: {type(e).__name__}: {e}")
        luecken.append(f"gesamt: {type(e).__name__}")
    return aus, luecken, herkunft


def _gekauft_seit(ts):
    """{type_id: Stueck}, die seit `ts` WIRKLICH gekauft wurden - ueber alle
    Charaktere, aus dem Handelsjournal. Das ist der harte Beleg dafuer, ob
    eine Einkaufsliste abgearbeitet wurde."""
    aus = {}
    if ts is None:
        return aus
    try:
        seit = time.strftime("%Y-%m-%d", time.localtime(float(ts)))
    except (TypeError, ValueError):
        return aus
    try:
        for r in (store.get_transactions(cid="all", since=seit,
                                         is_buy=True) or []):
            try:
                aus[int(r["type_id"])] = (aus.get(int(r["type_id"]), 0)
                                          + int(r["quantity"] or 0))
            except (TypeError, ValueError, KeyError):
                continue
    except Exception:
        pass
    return aus


def _verbraucht_und_gebaut(settings):
    """Was die ABGEHAKTEN Runs ALLER Plaene verbraucht und erzeugt haben -
    auch die der abgeschlossenen (`done_manual`). Die haben genauso aus
    demselben Hangar gegessen, und beim Suchen nach fehlendem Material
    waere es ein Kunstfehler, sie wegzulassen.

    Anteilig je Item: erledigte Runs / geplante Runs, wie
    `_reserve_map_mitlaufend` es auch rechnet.
    """
    weg, her = {}, {}
    for p in (settings.get("bau_saved_plans") or []):
        snap = MainWindowHelpers._plan_snapshot_unpack(
            (p.get("frozen") or {}).get("plan_snapshot") or {})
        runs = {int(t): int(q or 0)
                for t, q in (snap.get("build_runs") or {}).items()}
        mats = snap.get("build_mats") or {}
        if not runs or not mats:
            continue
        haken = {}
        for k, n in ((p.get("checked_runplan_runs") or {})).items():
            _st, _, _t = str(k).rpartition("|")
            try:
                haken[int(_t)] = max(haken.get(int(_t), 0), int(n or 0))
            except (TypeError, ValueError):
                continue
        try:
            for e in (store.job_zuordnung_fuer_plan(p.get("id"))
                      or {}).values():
                _t, _r = int(e.get("type_id")), int(e.get("runs") or 0)
                haken[_t] = max(haken.get(_t, 0), _r)
        except Exception:
            pass
        # AUSSTOSS JE RUN AUS DEM PLAN, NICHT AUS DER SDE (emm695).
        # `_out_qty_map` nimmt `SELECT ... LIMIT 1` - bei Items mit
        # ZWEI Rezepten (Tungsten Carbide: 20 und 10'000 je Run) ist
        # das Faktor 500 daneben (aa647). Der Plan hat mit
        # `build_made` / `build_runs` gerechnet; die SDE bleibt nur
        # Rueckfall fuer Items ohne Plan-Ausstoss. Dieselbe Heilung
        # wie in Abschnitt 6 (emm694) - REGEL 9: eine Ursache, ALLE
        # Fundstellen.
        made = {int(t): int(q or 0)
                for t, q in (snap.get("build_made") or {}).items()}
        out_pl = {t: max(1, made[t] // runs[t])
                  for t in runs if runs[t] > 0 and made.get(t)}
        oq = _out_qty_map(set(runs) - set(out_pl))
        for t, fertig in haken.items():
            ges = runs.get(t, 0)
            if ges <= 0 or fertig <= 0:
                continue
            anteil = min(1.0, float(fertig) / float(ges))
            for m, q in (mats.get(t) or []):
                weg[int(m)] = weg.get(int(m), 0) + int(q * anteil)
            her[t] = her.get(t, 0) + int(min(fertig, ges)
                                         * (out_pl.get(t) or oq.get(t, 1)))
    return weg, her


def _erledigte_runs(pl):
    """{type_id: Runs}, die fuer DIESEN Plan nachweislich schon gelaufen
    sind - aus der Job-Zuordnung (`job_zuordnung_fuer_plan`).

    WARUM DAS FEHLTE, UND WAS ES GEKOSTET HAT (24.10.2026). Abschnitt 6
    meldete "Atmospheric Gases fehlen 31'824" und "Evaporite Deposits
    fehlen 31'444". Der Nutzer hielt dagegen: "vorher hast du noch
    gesagt ich muss nur Platinum kaufen alles andere haette ich, Stock
    locations sagt das ja auch". ER HATTE RECHT, und die Zahl hat es
    bewiesen: beide Stoffe gehen ausschliesslich in Sulfuric Acid, sein
    Plan hat dort 325 Runs, und 325 x 100 x 0,98 (ME) = 31'850 - exakt
    der GEBRAUCHT-Wert im Bericht. Diese Runs sind laengst GELAUFEN
    (auf seinem Screenshot abgehakt, gruener ESI-Punkt).
    `_bedarf` zog bis hier nur Hand-Haken und GERADE LAUFENDE Jobs ab -
    ein FERTIGER, abgelieferter Job war in beiden nicht mehr zu finden,
    also galt sein Run wieder als offen und seine Zutaten wurden ein
    zweites Mal verlangt. Genau die Fehlerklasse, die diese Sitzung
    jagt, diesmal von mir selbst in den Bericht gebaut.
    Die Job-Zuordnung ist die richtige Quelle: sie sagt, welche Jobs zu
    welchem Plan gehoeren - auch die abgeschlossenen.
    """
    aus = {}
    try:
        for _j in (store.job_zuordnung_fuer_plan(pl.get("id")) or {}).values():
            _t = _j.get("type_id")
            if _t is None:
                continue
            aus[int(_t)] = aus.get(int(_t), 0) + int(_j.get("runs") or 0)
    except Exception:
        return {}
    return aus


def _bedarf(pl, laufend=None):
    """Was dieser Plan fuer seine NOCH OFFENEN Runs braucht.

    Abgehakte Runs sind verbraucht und zaehlen nicht mehr - und seit der
    Nutzer-Frage vom 24.10.2026 auch die, die GERADE LAUFEN (`laufend`):
    deren Zutaten sind aus dem Hangar weg, der Run ist angefangen. Sie
    hier als offen zu fuehren, haette das Material zweimal verlangt.
    Konservativ gerundet: ein laufender Job wird dem Item gutgeschrieben,
    auch wenn er zu einem anderen Plan gehoert - lieber ein Alarm zu
    wenig als ein falscher."""
    snap = MainWindowHelpers._plan_snapshot_unpack(
        (pl.get("frozen") or {}).get("plan_snapshot") or {})
    runs = {int(t): int(q or 0)
            for t, q in (snap.get("build_runs") or {}).items()}
    mats = snap.get("build_mats") or {}
    hak = {}
    for k, n in ((pl.get("checked_runplan_runs") or {})).items():
        _s, _, _t = str(k).rpartition("|")
        try:
            hak[int(_t)] = max(hak.get(int(_t), 0), int(n or 0))
        except (TypeError, ValueError):
            continue
    for t, n in (laufend or {}).items():
        hak[int(t)] = max(hak.get(int(t), 0), int(n or 0))
    # ABGESCHLOSSENE, DIESEM PLAN ZUGEORDNETE JOBS (s. `_erledigte_runs`):
    # ohne sie galt ein laengst gebauter Run wieder als offen und seine
    # Zutaten standen ein zweites Mal im Bedarf. MAXIMUM, nicht Summe -
    # derselbe Run kann in Haken, Lauf UND Zuordnung stehen.
    for t, n in (_erledigte_runs(pl) or {}).items():
        hak[int(t)] = max(hak.get(int(t), 0), int(n or 0))
    aus = {}
    for t, ges in runs.items():
        if ges <= 0:
            continue
        a = max(0.0, 1.0 - min(1.0, float(hak.get(t, 0)) / float(ges)))
        if a <= 0:
            continue
        for m, q in (mats.get(t) or []):
            aus[int(m)] = aus.get(int(m), 0) + int(int(q or 0) * a)
    return aus


def _schreiben(aus):
    os.makedirs(os.path.dirname(BERICHT), exist_ok=True)
    with open(BERICHT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(aus) + "\n")
    print("\n".join(aus))
    print(f"\nBericht: {BERICHT}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", default=None, help="nur Plaene mit diesem "
                                                 "Namensteil")
    ap.add_argument("--zeilen", type=int, default=25,
                    help="Zeilen je Tabelle (Vorgabe 25)")
    args = ap.parse_args()

    aus = []
    p = aus.append
    p("=" * 78)
    p(f"MATERIALBILANZ - wo ist das Material hin? (Fassung {FASSUNG})")
    p(f"Erstellt: {time.strftime('%Y-%m-%d %H:%M:%S')} (Ortszeit)")
    p("=" * 78)
    p("")
    p("  Nutzer: \"ich muesste Sachen nachkaufen die ich eben nicht im")
    p("  hangar habe, obwohl ich alles eingekauft habe fuer alle Bauplaene")
    p("  exakt nach Einkaufsliste\".")
    p("")

    settings = _settings_rohe()
    alle = [pl for pl in (settings.get("bau_saved_plans") or [])
            if isinstance(pl, dict) and not pl.get("done_manual")
            and ((pl.get("frozen") or {}).get("plan_snapshot"))]
    if args.plan:
        alle = [pl for pl in alle if args.plan.lower() in
                str(pl.get("label") or pl.get("item_name") or "").lower()]
    if not alle:
        p("  Keine aktiven, eingefrorenen Plaene gefunden.")
        _schreiben(aus)
        return

    live = _hangar(p)
    if not live:
        p("  OHNE ESI-BESTAND kann dieser Bericht nichts belegen - er")
        p("  braucht den echten Hangar. Starte das Programm einmal, damit")
        p("  die Anmeldung frisch ist, und versuch es noch einmal.")
        _schreiben(aus)
        return
    p(f"  Hangar (alle Charaktere zusammen): {_z(len(live))} Materialien, "
      f"{_z(sum(live.values()))} Stueck")
    laufend, _job_luecken, _job_herk = _laufende_jobs(p)
    if _job_luecken:
        p("")
        # CHARAKTER ODER CORP - DAS IST EIN UNTERSCHIED (24.10.2026).
        # Der erste Entwurf verweigerte bei JEDEM Fehlschlag das Urteil.
        # Sein Lauf um 13:31 hatte acht Fehlschlaege, ALLE von derselben
        # Corp - und er sagte danach: "ich habe keine Corp auftraege in
        # der Bauschleife laufen". Dann war die Verweigerung falsch: es
        # fehlte nichts, der Bericht hat sich nur selbst blind gestellt.
        # Wissen kann das Werkzeug es nicht - ER kann es. Also wird
        # GENAU GESAGT, was fehlt, und das Urteil nur dort verweigert,
        # wo wirklich etwas fehlen koennte.
        _ein, _corp_f, _char_f = [], 0, 0
        for _l in _job_luecken:
            if _l not in _ein:
                _ein.append(_l)
            if _l.startswith("Corp "):
                _corp_f += 1
            else:
                _char_f += 1
        p("")
        p(f"  ACHTUNG: {len(_job_luecken)} Job-Abruf(e) sind FEHLGESCHLAGEN")
        p(f"  ({'; '.join(_ein[:6])}).")
        if _char_f:
            p(f"  Davon {_z(_char_f)} bei einem CHARAKTER - was dort laeuft,")
            p("  fehlt in dieser Rechnung, und dann sieht Material wie")
            p("  verschwunden aus, das planmaessig in der Anlage steht.")
            p("  Spaeter nochmal laufen lassen.")
        if _corp_f and not _char_f:
            p(f"  ALLE {_z(_corp_f)} betreffen CORP-Jobs. Laufen bei dir")
            p("  keine Corp-Auftraege in der Bauschleife, fehlt dieser")
            p("  Rechnung NICHTS und das Urteil unten gilt. Laufen welche,")
            p("  sieht es zu knapp aus - dann spaeter nochmal.")
            p("  (Ein dauerhafter Fehler statt eines Zeitausfalls heisst")
            p("  meist: diesem Charakter fehlt die Rolle fuer die")
            p("  Corp-Jobs. Dann wird es auch beim naechsten Mal nicht")
            p("  gehen - und muss es nicht.)")
        p("")
    if laufend:
        p(f"  In der Bauschleife: {_z(len(laufend))} Erzeugnisse, "
          f"{_z(sum(laufend.values()))} Runs (Charaktere + Corp, Status")
        p("  active/paused/ready). Diese Runs gelten als ERLEDIGT - ihre")
        p("  Zutaten sind aus dem Hangar weg, ihr Erzeugnis noch nicht da.")
    else:
        p("  In der Bauschleife: nichts gefunden (oder nicht abrufbar).")
    # WOHER DIE RUNS KOMMEN - EXPLIZIT (24.10.2026, Nutzer: "es gibt
    # durchaus nutzer die gar keine Corp haben nur einzelne charaktere,
    # es gibt aber auch nutzer die Alles über Corp-Charaktere machen
    # damit sie eben den geteillten Corp hangar und Corp Jobs nutzen
    # können. für die Leute muss auch alles reibungslos funktionieren").
    # ER HAT RECHT, UND DER BERICHT DARF KEINE FORM RATEN. Fuer ihn sind
    # Corp-Jobs belanglos; fuer jemanden, der ALLES ueber die Corp
    # faehrt, ist ein fehlgeschlagener Corp-Abruf der Totalausfall.
    # Also wird die Aufteilung HINGESCHRIEBEN - dann liest jede Form
    # ihre eigene Lage ab, ohne dass das Werkzeug eine Annahme trifft.
    # `settings`, NICHT `s` - in `main()` heisst die Variable so. Der
    # erste Entwurf hatte `s.get(...)` und liess den ganzen Lauf mit
    # NameError abstuerzen, BEVOR der Bericht geschrieben wurde
    # (Nutzer 13:48: "bat ausgefuehrt, sieht komisch aus"). Ein Werkzeug,
    # das ich nicht einmal selbst laufen lassen kann, muss wenigstens
    # durch einen Linter - s. unten `pruefe.py`.
    if settings.get("use_corp"):
        p(f"  Davon aus Charakter-Bauschleifen: "
          f"{_z(_job_herk.get('char', 0))} Runs, aus Corp-Bauschleifen: "
          f"{_z(_job_herk.get('corp', 0))} Runs "
          f"({_z(_job_herk.get('corp_ok', 0))} Corporation(en) gelesen).")
        if not _job_herk.get("corp_ok") and _job_luecken:
            p("  KEINE Corporation konnte gelesen werden. Faehrst du alles")
            p("  ueber Corp-Jobs, ist dieser Bericht fuer dich BLIND -")
            p("  dann braucht einer deiner Charaktere die Rolle")
            p("  \"Factory Manager\" (fuer den Hangar reicht sie nicht).")
            p("  Baust du wie bisher auf Charakteren, fehlt nichts.")
    else:
        p("  Corp ist abgeschaltet - es wird nur auf Charakteren gesucht,")
        p("  und das ist dann auch vollstaendig.")
    _frueh = min(float((pl.get("frozen") or {}).get("ts") or 0) for pl in alle)
    p(f"  Aeltester aktiver Plan eingefroren: {_zeit(_frueh)}")
    p("")

    # ---- 1) Hast du die Liste wirklich gekauft? --------------------------
    p("=" * 78)
    p("1) HAST DU DIE EINKAUFSLISTEN WIRKLICH ABGEARBEITET?")
    p("=" * 78)
    p("  Links: was die eingefrorenen Plaene zusammen verlangt haben.")
    p("  Rechts: was seit dem aeltesten Einfrieren wirklich im")
    p("  Handelsjournal steht (alle Charaktere, nur Kaeufe).")
    p("")
    p("  WICHTIG BEIM LESEN: Kaeufe lassen sich keinem Plan zuordnen - ein")
    p("  Kauf kann fuer jeden der Plaene gewesen sein. Darum wird hier")
    p("  SUMMIERT verglichen, nicht je Plan. Und: hast du ein Material")
    p("  schon VOR dem Einfrieren gekauft, taucht es rechts nicht auf -")
    p("  dann ist eine Luecke hier kein Beweis.")
    p("")
    verlangt = {}
    for pl in alle:
        snap = MainWindowHelpers._plan_snapshot_unpack(
            (pl.get("frozen") or {}).get("plan_snapshot") or {})
        for schl in ("buy", "inv_buy"):
            for t, q in (snap.get(schl) or {}).items():
                if q and int(q) > 0:
                    verlangt[int(t)] = verlangt.get(int(t), 0) + int(q)
    gekauft = _gekauft_seit(_frueh)
    if not gekauft:
        p("  Kein einziger Kauf seit dem Einfrieren im Journal - entweder")
        p("  ist das Journal nicht aktuell, oder die Kaeufe liegen davor.")
        p("  Abschnitt 1 sagt dann nichts aus.")
    else:
        luecke = sorted(((v - int(gekauft.get(t, 0)), t, v,
                          int(gekauft.get(t, 0)))
                         for t, v in verlangt.items()
                         if v - int(gekauft.get(t, 0)) > 0), reverse=True)
        namen = _namen(set(verlangt) | set(gekauft))
        p(f"  Verlangt: {_z(len(verlangt))} Posten / "
          f"{_z(sum(verlangt.values()))} Stueck")
        p(f"  Gekauft:  {_z(len(gekauft))} Posten / "
          f"{_z(sum(gekauft.values()))} Stueck")
        p("")
        if not luecke:
            p("  JEDE Position der Listen ist mindestens in der verlangten")
            p("  Menge gekauft worden. Am Einkauf liegt es also nicht.")
        else:
            p(f"  {'MATERIAL':30} {'LISTE WOLLTE':>13} {'GEKAUFT':>13} "
              f"{'FEHLT':>13}")
            for d, t, v, g in luecke[:args.zeilen]:
                p(f"  {str(namen.get(t) or t)[:30]:30} {_z(v):>13} "
                  f"{_z(g):>13} {_z(d):>13}")
            if len(luecke) > args.zeilen:
                p(f"  ... und {len(luecke) - args.zeilen} weitere")
    p("")

    # ---- 2) Deckungsluecke ----------------------------------------------
    p("=" * 78)
    p("2) AUS DEM HANGAR EINGEPLANT - ABER NICHT MEHR DA")
    p("=" * 78)
    p("  Diese Posten standen NIE auf einer Einkaufsliste: der Plan hat")
    p("  sie aus dem Bestand gedeckt. Ist der Bestand inzwischen weg,")
    p("  fehlt dir Material, fuer das du nie eine Rechnung gesehen hast.")
    p("")
    namen2 = set()
    luecken = {}
    for pl in alle:
        lab = str(pl.get("label") or pl.get("item_name") or pl.get("id"))
        snap = MainWindowHelpers._plan_snapshot_unpack(
            (pl.get("frozen") or {}).get("plan_snapshot") or {})
        su = {int(t): int(q or 0)
              for t, q in (snap.get("stock_used") or {}).items()}
        su.update({int(t): su.get(int(t), 0) + int(q or 0)
                   for t, q in (snap.get("inv_stock_used") or {}).items()})
        # Was dieser Plan noch bauen muss - fuer ERLEDIGTE Runs braucht er
        # die Deckung nicht mehr.
        # DRITTE FUNDSTELLE DERSELBEN LUECKE (25.10.2026). Hier stand nur
        # der Hand-Haken: weder gelieferte noch laufende Jobs wurden
        # abgezogen. Damit galt praktisch jeder Run als offen, der nicht
        # von Hand abgehakt war - und Abschnitt 2 verlangte Material fuer
        # Runs, die laengst gebaut sind. Von hier kamen seine drei Posten
        # (Evaporite Deposits 13'854, Ceramic Powder 3'308, Ferrofluid
        # 622).
        # ICH HABE DIESE LUECKE AN EINEM TAG DREIMAL GEFUNDEN - erst in
        # `_bedarf` (Abschnitt 6), dann in Abschnitt 4, jetzt hier. Zwei
        # Mal davon, weil ich nach der ersten Reparatur nicht nach
        # weiteren Fundstellen gesucht habe. Deshalb steht die Rechnung
        # jetzt an allen drei Stellen gleich: Haken, laufende Jobs UND
        # zugeordnete fertige Jobs, verknuepft mit max().
        _hak = {}
        for k, n in ((pl.get("checked_runplan_runs") or {})).items():
            _st, _, _t = str(k).rpartition("|")
            try:
                _hak[int(_t)] = max(_hak.get(int(_t), 0), int(n or 0))
            except (TypeError, ValueError):
                continue
        # `laufend` ist PLANUEBERGREIFEND - dieselbe Einschraenkung, die
        # Abschnitt 6 in seiner Warnung nennt. Hier ist sie trotzdem
        # richtig herum: Material, das gerade im Reaktor steckt, ist
        # verbraucht und nicht "nachzukaufen". Und drei verschiedene
        # Definitionen von "offen" in EINEM Bericht sind genau der
        # Naehrboden, auf dem dieser Fehler dreimal ueberlebt hat.
        for _t2l, _n2l in (laufend or {}).items():
            _hak[int(_t2l)] = max(_hak.get(int(_t2l), 0), int(_n2l or 0))
        for _t2e, _n2e in (_erledigte_runs(pl) or {}).items():
            _hak[int(_t2e)] = max(_hak.get(int(_t2e), 0), int(_n2e or 0))
        runs = {int(t): int(q or 0)
                for t, q in (snap.get("build_runs") or {}).items()}
        offen_anteil = {}
        for t, ges in runs.items():
            if ges > 0:
                offen_anteil[t] = max(0.0, 1.0 - min(1.0, _hak.get(t, 0) / ges))
        # Deckung anteilig auf die noch offenen Runs herunterrechnen.
        mats = snap.get("build_mats") or {}
        noch = {}
        for t, ges in runs.items():
            a = offen_anteil.get(t, 1.0)
            if a <= 0:
                continue
            for m, q in (mats.get(t) or []):
                noch[int(m)] = noch.get(int(m), 0) + int(q * a)
        for t, q in su.items():
            braucht = min(int(q), int(noch.get(t, 0)))
            da = int(live.get(t, 0))
            if braucht > da:
                luecken[(lab, t)] = (braucht, da, braucht - da)
                namen2.add(t)
    namen = _namen(namen2)
    if not luecken:
        p("  Keine Luecke - alles, was die Plaene aus dem Bestand decken")
        p("  wollten, liegt noch im Hangar.")
    else:
        ges = sum(v[2] for v in luecken.values())
        p(f"  {_z(len(luecken))} Posten, zusammen {_z(ges)} Stueck, die du")
        p("  nachkaufen musst, obwohl keine Liste danach gefragt hat.")
        p("")
        p(f"  {'PLAN':22} {'MATERIAL':28} {'EINGEPLANT':>11} {'IM HANGAR':>11} "
          f"{'FEHLT':>11}")
        for (lab, t), (b, d, f) in sorted(
                luecken.items(), key=lambda x: -x[1][2])[:args.zeilen]:
            p(f"  {lab[:22]:22} {str(namen.get(t) or t)[:28]:28} "
              f"{_z(b):>11} {_z(d):>11} {_z(f):>11}")
        if len(luecken) > args.zeilen:
            p(f"  ... und {len(luecken) - args.zeilen} weitere")
    p("")

    # ---- 3) Wo ist es hin? ----------------------------------------------
    p("=" * 78)
    p("3) WO IST ES HIN? - Bilanz je Luecke")
    p("=" * 78)
    p("  Bestand beim Einfrieren + seither gekauft - was die abgehakten")
    p("  Runs ALLER Plaene verbraucht haben + was sie erzeugt haben")
    p("  = erwartet. Dagegen der echte Hangar.")
    p("")
    p("  UNERKLAERT heisst: auf einem Weg weg, den das Programm nicht")
    p("  kennt - verkauft, verschenkt, in einen Vertrag gelegt, von Hand")
    p("  verbaut, oder in einem Job, der keinem Plan zugeordnet ist.")
    p("")
    weg, her = _verbraucht_und_gebaut(settings)
    _t_liste = sorted({t for (_l, t) in luecken},
                      key=lambda x: -max(v[2] for (l2, t2), v in
                                         luecken.items() if t2 == x))
    if not _t_liste:
        p("  Nichts zu bilanzieren - Abschnitt 2 hat keine Luecke gefunden.")
    else:
        p(f"  {'MATERIAL':26} {'EINGEFR.':>10} {'GEKAUFT':>10} "
          f"{'VERBAUT':>10} {'ERZEUGT':>9} {'ERWARTET':>11} {'ECHT':>10} "
          f"{'UNERKL.':>10}")
        for t in _t_liste[:args.zeilen]:
            # Bestand beim Einfrieren: der frueheste aktive Plan.
            _fr = min(alle, key=lambda x: float(
                (x.get("frozen") or {}).get("ts") or 0))
            _st0 = int((MainWindowHelpers._plan_snapshot_unpack(
                (_fr.get("frozen") or {}).get("stock") or {})).get(t, 0) or 0)
            _g = int(gekauft.get(t, 0))
            _w = int(weg.get(t, 0))
            _h = int(her.get(t, 0))
            _erw = _st0 + _g - _w + _h
            _echt = int(live.get(t, 0))
            p(f"  {str(namen.get(t) or t)[:26]:26} {_z(_st0):>10} "
              f"{_z(_g):>10} {_z(_w):>10} {_z(_h):>9} {_z(_erw):>11} "
              f"{_z(_echt):>10} {_z(_erw - _echt):>10}")
        if len(_t_liste) > args.zeilen:
            p(f"  ... und {len(_t_liste) - args.zeilen} weitere")
        p("")
        p("  LIES DIE SPALTE \"UNERKL.\" VORSICHTIG: sie ist eine Schaetzung.")
        p("  \"EINGEFR.\" ist der Bestand, den der AELTESTE aktive Plan sah -")
        p("  Material, das du davor schon verbraucht oder danach aus einer")
        p("  Reaktion bekommen hast, steht nirgends. Eine kleine Abweichung")
        p("  sagt nichts; eine grosse zeigt, wo es sich lohnt, nachzusehen.")
    p("")

    # ---- 4) Runplaner gegen Wirklichkeit --------------------------------
    p("=" * 78)
    p("4) DIE OFFENEN RUNS GEGEN DEN ECHTEN HANGAR")
    p("=" * 78)
    p("  Fuer JEDEN noch offenen Run: liegen seine Zutaten wirklich da?")
    p("  Und wenn nicht - ist das schlimm oder nur die Reihenfolge?")
    p("")
    p("    KOMMT NOCH  = die Zutat baust du selbst, ihre Runs sind noch")
    p("                  offen. Kein Verlust, nur noch nicht dran.")
    p("    ERZ FEHLT   = die Zutat kommt aus dem Reprocessing, und das")
    p("                  Erz dafuer liegt noch unverarbeitet im Hangar.")
    p("    IN ARBEIT   = die Zutat steht gerade in der Bauschleife.")
    p("    NACHLEGEN   = der Plan baut die Zutat selbst, aber die")
    p("                  geplanten Runs sind aufgebraucht und die")
    p("                  naechste Stufe braucht mehr - leg die genannten")
    p("                  Runs nach (dasselbe sagt der Runplaner als")
    p("                  '+n to run').")
    p("    ANDERER PLAN= ein anderer Plan hat noch offene Runs dieser")
    p("                  Zutat - sein Ausstoss landet im selben Hangar,")
    p("                  er hat ihn aber fuer sich eingeplant (Rangfolge,")
    p("                  s. Abschnitt 5).")
    p("    FEHLT ECHT  = niemand baut es mehr, kein Erz dafuer da. Das")
    p("                  ist das Material, das wirklich weg ist.")
    p("")
    # Erz, das noch unverarbeitet herumliegt, und was es ergeben wuerde.
    erz_deckt, erz_liegt = {}, {}
    for pl in alle:
        snap = MainWindowHelpers._plan_snapshot_unpack(
            (pl.get("frozen") or {}).get("plan_snapshot") or {})
        for st in ((snap.get("reprocess") or {}).get("schritte") or []):
            try:
                _e = int(st.get("erz"))
                _m = int(st.get("menge") or 0)
            except (TypeError, ValueError):
                continue
            if _m <= 0 or int(live.get(_e, 0)) < _m:
                continue          # Erz ist weg -> also verarbeitet
            erz_liegt[_e] = erz_liegt.get(_e, 0) + _m
            for m, q in (st.get("deckt") or {}).items():
                erz_deckt[int(m)] = erz_deckt.get(int(m), 0) + int(q or 0)
    if erz_liegt:
        p(f"  {_z(len(erz_liegt))} Erzsorten liegen noch unverarbeitet da -")
        p(f"  sie wuerden {_z(sum(erz_deckt.values()))} Stueck Mineral")
        p("  ergeben, die der Plan bereits als gedeckt fuehrt.")
        p("")

    zeilen4, summe4 = [], {"KOMMT NOCH": 0, "IN ARBEIT": 0,
                           "ERZ FEHLT": 0, "NACHLEGEN": 0,
                           "ANDERER PLAN": 0, "FEHLT ECHT": 0}
    namen4 = set()
    # ZWEI DURCHGAENGE (emm692). Die Einstufung kannte nur den EIGENEN
    # Plan: `offen.get(m)` fragte, ob DIESER Plan die Zutat noch baut.
    # Zwei Faelle stufte sie damit falsch als "FEHLT ECHT - niemand baut
    # es mehr" ein, beide vom Nutzer am 25.10.2026 aufgedeckt:
    #   * der NACHLAUF (emm646): die geplanten Runs der Zutat sind
    #     aufgebraucht, die naechste Stufe braucht mehr. Sein Fernite
    #     Carbide: 24'810 Stueck als "wirklich weg" gemeldet -
    #     tatsaechlich fehlten 3 Reaktions-Runs a 10'000. Er fragte zu
    #     Recht nach ("bist du auch sicher, dass ich die nicht gerade am
    #     bauen bin irgendwo?") - die Antwort gehoert in den Bericht,
    #     nicht in eine Rueckfrage.
    #   * EIN ANDERER PLAN baut die Zutat noch: die Schleife ist je Plan,
    #     die Frage "baut es noch jemand?" ist planuebergreifend.
    # Durchgang 1 sammelt deshalb zuerst ueber ALLE Plaene, was offen ist
    # und was ein Run je Item ausbringt; Durchgang 2 stuft erst dann ein.
    _plaene4, _offen_alle4, _out4 = [], {}, {}
    for pl in alle:
        lab = str(pl.get("label") or pl.get("item_name") or pl.get("id"))
        snap = MainWindowHelpers._plan_snapshot_unpack(
            (pl.get("frozen") or {}).get("plan_snapshot") or {})
        runs = {int(t2): int(q or 0)
                for t2, q in (snap.get("build_runs") or {}).items()}
        mats = snap.get("build_mats") or {}
        hak = {}
        for k, n in ((pl.get("checked_runplan_runs") or {})).items():
            _s2, _, _t2 = str(k).rpartition("|")
            try:
                hak[int(_t2)] = max(hak.get(int(_t2), 0), int(n or 0))
            except (TypeError, ValueError):
                continue
        # Was laeuft, ist angefangen - nicht offen (Nutzerfrage 24.10.).
        for _t3, _n3 in (laufend or {}).items():
            hak[int(_t3)] = max(hak.get(int(_t3), 0), int(_n3 or 0))
        # UND WAS FERTIG GELIEFERT IST, IST ERST RECHT NICHT OFFEN
        # (25.10.2026). Genau diese Zeile fehlte hier. `_erledigte_runs`
        # war am Vortag geschrieben und in Abschnitt 6 eingebaut worden -
        # aber DIESER Abschnitt rechnet sein `offen` selbst aus und zog
        # nur Haken und GERADE LAUFENDE Jobs ab. Ein FERTIGER,
        # abgelieferter Job steht in keinem von beiden: sein Run galt
        # wieder als offen, und seine Zutaten wurden ein zweites Mal
        # verlangt.
        # DER NUTZER HAT ES GEMERKT, NICHT ICH: "unmoeglich gestern hast
        # du etwa 10 mal gesagt ich habe alles, stock locations sagt auch
        # ich habe alles". Und die Zahl gab ihm recht - es stand wieder
        # exakt 31'850 da (325 Sulfuric-Acid-Runs x 100 x 0,98 ME),
        # dieselbe Zahl, die ich einen Tag vorher schon einmal als
        # Artefakt genau dieses Fehlers entlarvt hatte. Ich habe die
        # Ursache behoben und die zweite Fundstelle nicht gesucht.
        # GEGENPROBE IM BERICHT SELBST: Abschnitt 6, der `_erledigte_runs`
        # benutzt, fuehrte Atmospheric Gases und Evaporite Deposits NICHT
        # als fehlend - nur dieser Abschnitt tat es.
        # max() STATT SUMME, bewusst: Haken, laufender Job und
        # gelieferter Job koennen DENSELBEN Run meinen. Zu addieren
        # hiesse, zu viel als erledigt zu buchen - und das ist die
        # gefaehrliche Richtung, denn dann fehlt ihm im Spiel Material.
        for _t4, _n4 in (_erledigte_runs(pl) or {}).items():
            hak[int(_t4)] = max(hak.get(int(_t4), 0), int(_n4 or 0))
        offen = {t2: max(0, g - hak.get(t2, 0)) for t2, g in runs.items()}
        _plaene4.append((lab, runs, mats, offen))
        for _t2, _n2 in offen.items():
            if _n2 > 0:
                _offen_alle4[_t2] = _offen_alle4.get(_t2, 0) + _n2
        # AUSBRINGUNG AUS DEM PLAN, NICHT AUS DER SDE (aa647: Tungsten
        # Carbide hat ZWEI Rezepte, 20 und 10'000 je Run - `_out_qty_map`
        # nimmt LIMIT 1 und kann die falsche erwischen; Abschnitt 6 ist
        # dafuer schon am 24.10. umgestellt worden, hier gilt dasselbe).
        _md4 = {int(k): int(v or 0)
                for k, v in (snap.get("build_made") or {}).items()}
        for _t2 in runs:
            if runs[_t2] > 0 and _md4.get(_t2):
                _out4.setdefault(_t2, max(1, _md4[_t2] // runs[_t2]))
    _nachlegen4 = {}
    for lab, runs, mats, offen in _plaene4:
        bedarf4 = {}
        for t2, g in runs.items():
            if g <= 0 or offen.get(t2, 0) <= 0:
                continue
            a = float(offen[t2]) / float(g)
            for m, q in (mats.get(t2) or []):
                bedarf4[int(m)] = bedarf4.get(int(m), 0) + int(q * a)
        for m, b in bedarf4.items():
            fehlt = b - int(live.get(m, 0))
            if fehlt <= 0:
                continue
            if int((laufend or {}).get(m, 0)) > 0:
                art = "IN ARBEIT"
            elif offen.get(m, 0) > 0:
                art = "KOMMT NOCH"
            elif int(erz_deckt.get(m, 0)) >= fehlt:
                art = "ERZ FEHLT"
            elif runs.get(m, 0) > 0:
                # Der Plan baut die Zutat SELBST, ihre Runs sind nur
                # aufgebraucht - das ist der Nachlauf-Fall, und die
                # Handlung heisst "nachlegen", nicht "kaufen".
                art = "NACHLEGEN"
                _o4 = int(_out4.get(m, 0) or 0)
                if _o4 > 0:
                    _nachlegen4[(lab, m)] = (fehlt + _o4 - 1) // _o4
            elif int(_offen_alle4.get(m, 0) or 0) > 0:
                art = "ANDERER PLAN"
            else:
                art = "FEHLT ECHT"
            summe4[art] += fehlt
            zeilen4.append((fehlt, lab, m, b, int(live.get(m, 0)), art))
            namen4.add(m)
    namen = _namen(namen4)
    p(f"  KOMMT NOCH (selbst gebaut): {_z(summe4['KOMMT NOCH'])} Stueck")
    p(f"  IN ARBEIT  (laeuft gerade):  {_z(summe4['IN ARBEIT'])} Stueck")
    p(f"  ERZ FEHLT  (nur verarbeiten): {_z(summe4['ERZ FEHLT'])} Stueck")
    p(f"  NACHLEGEN  (Runs nachlegen): {_z(summe4['NACHLEGEN'])} Stueck")
    p(f"  ANDERER PLAN (baut es noch): {_z(summe4['ANDERER PLAN'])} Stueck")
    p(f"  FEHLT ECHT (wirklich weg):  {_z(summe4['FEHLT ECHT'])} Stueck")
    p("")
    # NACHLEGEN zuerst - das ist eine HANDLUNG, keine Luecke. Die
    # Run-Zahl kommt aus der Ausbringung des Plans selbst (aa647).
    if _nachlegen4:
        p(f"  {'NACHLEGEN':20} {'MATERIAL':26} {'FEHLT':>12} {'RUNS':>8}")
        for (_lab_n, _m_n), _r_n in sorted(_nachlegen4.items(),
                                           key=lambda kv: -kv[1]):
            _f_n = next((z[0] for z in zeilen4
                         if z[1] == _lab_n and z[2] == _m_n
                         and z[5] == "NACHLEGEN"), 0)
            p(f"  {_lab_n[:20]:20} {str(namen.get(_m_n) or _m_n)[:26]:26} "
              f"{_z(_f_n):>12} {_z(_r_n):>8}")
        p("")
    _fremd4 = [z for z in zeilen4 if z[5] == "ANDERER PLAN"]
    if _fremd4:
        p("  EIN ANDERER PLAN baut noch (Zuteilung s. Rangfolge, Absch. 5):")
        for fehlt, lab, m, b, da, _a in sorted(_fremd4, reverse=True)[:8]:
            p(f"    {lab[:20]:20} {str(namen.get(m) or m)[:26]:26} "
              f"fehlen {_z(fehlt)}")
        p("")
    _echt4 = [z for z in zeilen4 if z[5] == "FEHLT ECHT"]
    if not _echt4:
        p("  NICHTS ist wirklich weg. Alles, was dir gerade fehlt, baust du")
        p("  selbst oder steckt noch im Erz. Dann ist es keine Luecke,")
        p("  sondern die Reihenfolge - und das waere eine Anzeige-Frage,")
        p("  kein verlorenes Material.")
    else:
        p(f"  {'PLAN':20} {'MATERIAL':26} {'BRAUCHT':>12} {'HANGAR':>12} "
          f"{'FEHLT':>12}")
        for fehlt, lab, m, b, da, _a in sorted(_echt4,
                                               reverse=True)[:args.zeilen]:
            p(f"  {lab[:20]:20} {str(namen.get(m) or m)[:26]:26} "
              f"{_z(b):>12} {_z(da):>12} {_z(fehlt):>12}")
        if len(_echt4) > args.zeilen:
            p(f"  ... und {len(_echt4) - args.zeilen} weitere")
    p("")

    # ---- 5) Ueberbuchung des PHYSISCHEN Bestands ------------------------
    p("=" * 78)
    p("5) ZAEHLEN MEHRERE PLAENE AUF DIESELBEN STUECKE? (Rangfolge)")
    p("=" * 78)
    p("  Die Bauprioritaet wirkt nur in EINE Richtung: ein Plan sieht nur")
    p("  die Reservierungen der Plaene VOR ihm. Der Plan auf Rang 1 sieht")
    p("  also NIEMANDEN - fuer ihn ist auch das Material frei, das ein")
    p("  spaeterer Plan laengst eingeplant oder sogar gekauft hat.")
    p("")
    p("  Solange genug da ist, macht das nichts. Hier wird gerechnet, wo")
    p("  es NICHT reicht:")
    p("")
    p("      eigener Restbedarf aus dem Bestand + fremder Anspruch")
    p("      > was wirklich im Hangar liegt")
    p("")
    _rang5 = MainWindowHelpers.plan_rang(settings)
    p(f"  {'PLAN':24} {'RANG':>5} {'SIEHT FREMDE RESERV.':>21} {'BLIND FUER':>14}")
    _ansp5 = {}
    for pl in alle:
        lab = str(pl.get("label") or pl.get("item_name") or pl.get("id"))
        _ansp5[lab] = {int(t2): int(q or 0) for t2, q in
                       (MainWindowHelpers.plan_anspruch_mitlaufend(pl)
                        or {}).items()}
    _blind5, _namen5 = {}, set()
    for pl in alle:
        lab = str(pl.get("label") or pl.get("item_name") or pl.get("id"))
        _sieht, _l5 = MainWindowHelpers._reserved_by_other_plans(
            settings, pl.get("id"))
        _andere = {}
        for lab2, a2 in _ansp5.items():
            if lab2 == lab:
                continue
            for t2, q2 in a2.items():
                _andere[t2] = _andere.get(t2, 0) + q2
        _offen = 0
        for t2, q2 in _andere.items():
            _ungesehen = q2 - int((_sieht or {}).get(t2, 0))
            if _ungesehen > 0:
                _offen += _ungesehen
        p(f"  {lab[:24]:24} {str(_rang5.get(str(pl.get('id')), '-')):>5} "
          f"{_z(sum((_sieht or {}).values())):>21} {_z(_offen):>14}")
        # Wo es wirklich knapp wird: eigener Bedarf + fremder Anspruch
        # gegen das, was DA ist.
        _bedarf5 = _bedarf(pl, laufend) or {}
        for t2, b2 in _bedarf5.items():
            _ges = b2 + int(_andere.get(t2, 0))
            _da = int(live.get(t2, 0))
            if _ges > _da and int(_andere.get(t2, 0)) > 0 and b2 > 0:
                _knapp = min(b2, _ges - _da)
                _blind5[(lab, t2)] = (b2, int(_andere.get(t2, 0)), _da, _knapp)
                _namen5.add(t2)
    namen = _namen(_namen5)
    p("")
    if not _blind5:
        p("  Kein Material ist knapp - jeder Posten reicht fuer alle Plaene")
        p("  zusammen. Die Rangfolge beisst hier also nicht.")
    else:
        p(f"  {_z(len(_blind5))} Posten sind UEBERBUCHT: zusammen fehlen")
        p(f"  {_z(sum(v[3] for v in _blind5.values()))} Stueck, wenn jeder")
        p("  Plan baut, was er geplant hat.")
        p("")
        p(f"  {'PLAN':20} {'MATERIAL':24} {'BRAUCHT':>11} {'ANDERE':>11} "
          f"{'HANGAR':>11} {'FEHLT':>10}")
        for (lab, t2), (b2, a2, d2, k2) in sorted(
                _blind5.items(), key=lambda x: -x[1][3])[:args.zeilen]:
            p(f"  {lab[:20]:20} {str(namen.get(t2) or t2)[:24]:24} "
              f"{_z(b2):>11} {_z(a2):>11} {_z(d2):>11} {_z(k2):>10}")
        if len(_blind5) > args.zeilen:
            p(f"  ... und {len(_blind5) - args.zeilen} weitere")
        p("")
        p("  SO LIEST DU DAS: \"BRAUCHT\" ist der eigene Restbedarf,")
        p("  \"ANDERE\" der Anspruch der uebrigen Plaene, \"HANGAR\" was")
        p("  wirklich da ist. Wo die ersten beiden zusammen groesser sind")
        p("  als der Hangar, wird einer der Plaene leer ausgehen - und der")
        p("  mit dem besseren Rang merkt es nicht einmal.")
    p("")

    # ---- 6) GESAMTBILANZ: geht es am Ende auf? --------------------------
    # NUTZER 24.10.2026, die eigentliche Frage: "am Ende ist nur wichtig,
    # wieviel in meinem Hangar landet und zwar zum schluss die exakte
    # Anzahl Items muss stimmen ... ueber alle Baupläne, runs, Hangare,
    # und bauschleifen kommt am ende wenn alles fertig ist die richtige
    # Anzahl fuer alle Bauplaene heraus und es kann weiter gebaut
    # werden. So das ist es was ich wissen muss am Ende".
    #
    # ALLE BISHERIGEN ABSCHNITTE SCHAUEN ZURUECK (was fehlt, wo ist es
    # hin, wer hat ueberbucht). DIESER SCHAUT NACH VORN und rechnet EINE
    # Zahl je Material ueber ALLES:
    #     Angebot = Hangar (Charaktere + Corp)
    #             + Ausstoss aller LAUFENDEN Jobs
    #             + Ausstoss aller NOCH OFFENEN geplanten Runs
    #     Bedarf  = was die noch offenen Runs ALLER Plaene an Zutaten
    #               brauchen
    # Ist das Saldo ueberall >= 0, geht es auf: dann kann am Ende jeder
    # Plan fertig gebaut werden, egal wer welchen Run gefahren hat.
    # Ist es irgendwo < 0, ist GENAU das die Menge, die er nachkaufen
    # muss - ueber alle Plaene auf einmal, nicht je Plan.
    #
    # WARUM DAS DIE EHRLICHERE AUSKUNFT IST als die Zeilen-Warnung im
    # Runplaner: ob ESI einen einzelnen Haken belegen kann, haengt an der
    # Job-Zuordnung. Ob am Ende die richtige Stueckzahl herauskommt,
    # haengt nur an Mengen - und Mengen luegen nicht.
    p("=" * 78)
    p("6) GESAMTBILANZ - GEHT ES AM ENDE AUF?")
    p("=" * 78)
    p("  Die offenen Runs werden hier je Plan bestimmt, wie der")
    p("  Runplaner es tut: Plan-Runs minus Beleg DIESES Plans (Haken")
    p("  oder zugeordnete Jobs, das Groessere von beiden). Laufende")
    p("  Jobs OHNE Plan-Zuordnung werden genau EINMAL verrechnet, in")
    p("  Kartenreihenfolge - nicht mehr in jedem Plan, der das Item")
    p("  baut (der Fehler vom 24.10., der 248 Sylramic-Runs erfand).")
    p("")
    p("  GRENZEN: Setzt du einen Haken fuer Runs, die noch laufen und")
    p("  KEINEM Plan zugeordnet sind, zieht die Rechnung sie doppelt ab")
    p("  und sieht zu wenig offene Runs. Haken gehoeren auf Geliefertes.")
    p("  Und ein Kauf bleibt ein Entscheid aus mehreren Quellen: Plan-")
    p("  Einkaufsliste und Stock Locations daneben halten.")
    p("")
    # OFFEN JE PLAN, OHNE DIE PLANUEBERGREIFENDE LAUFEND-KARTE (emm694).
    # Genau hier sass der Fehler, der den Abschnitt [NICHT VERLAESSLICH]
    # gemacht hat: `_weg6 = max(hak, laufend[t], zu)` zog die GLOBALE Zahl
    # laufender Runs in JEDEM Plan ab, der das Item baut. 603 laufende
    # Sylramic-Runs loeschten damit offene Runs im Amarr- UND im
    # Gallente-Plan - dieselben Runs doppelt weg, ihr kuenftiger Ausstoss
    # nur einmal gutgeschrieben. Die Rekursion erfand daraus die "248
    # zusaetzlichen Sylramic-Runs" vom 24.10., die laengst im Plan standen.
    # JETZT: je Plan zaehlen nur die EIGENEN Belege (Haken + Jobs, die
    # laut `job_zuordnung` DIESEM Plan gehoeren - laufende wie fertige).
    # Unzugeordnete LAUFENDE Jobs werden danach GENAU EINMAL von den
    # offenen Runs abgezogen, im Wasserfall der Kartenreihenfolge (wie
    # die Reservierung) - denn ihr Ausstoss ist unten schon als
    # "laufend" gutgeschrieben, und ein Run darf nie doppelt zaehlen
    # (weder doppelt offen noch doppelt erledigt).
    _zuord_ids6 = set()
    try:
        _zuord_ids6 = {int(_j) for _j in (store.job_zuordnung_alle() or {})}
    except Exception as _ez6:
        p(f"  (Job-Zuordnung nicht lesbar: {type(_ez6).__name__} - "
          "unzugeordnete laufende Jobs werden dann nicht verrechnet.)")
    _unz6 = {}
    for _jid6, _pt6, _r6 in (_job_herk.get("jobs") or []):
        try:
            if _jid6 is not None and int(_jid6) in _zuord_ids6:
                continue                      # gehoert einem Plan
        except (TypeError, ValueError):
            pass
        _unz6[int(_pt6)] = _unz6.get(int(_pt6), 0) + int(_r6 or 0)
    _plaene6 = []
    for pl in alle:
        _snap6 = MainWindowHelpers._plan_snapshot_unpack(
            (pl.get("frozen") or {}).get("plan_snapshot") or {})
        _runs6 = {int(t): int(q or 0)
                  for t, q in (_snap6.get("build_runs") or {}).items()}
        _mats6 = {int(t): v for t, v in
                  (_snap6.get("build_mats") or {}).items()}
        _hak6 = {}
        for _k6, _n6 in ((pl.get("checked_runplan_runs") or {})).items():
            _s6, _, _t6 = str(_k6).rpartition("|")
            try:
                _hak6[int(_t6)] = max(_hak6.get(int(_t6), 0), int(_n6 or 0))
            except (TypeError, ValueError):
                continue
        _zu6 = _erledigte_runs(pl) or {}
        _off6 = {}
        for _t6, _ges6 in _runs6.items():
            if _ges6 <= 0:
                continue
            # MAXIMUM, nicht Summe: Haken und Zuordnung koennen DENSELBEN
            # Run meinen.
            _weg6 = max(int(_hak6.get(_t6, 0)), int(_zu6.get(_t6, 0)))
            _off6[_t6] = max(0, _ges6 - _weg6)
        _plaene6.append((str(pl.get("id")),
                         str(pl.get("label") or pl.get("item_name")
                             or pl.get("id")),
                         _off6, _runs6, _mats6))
    _rest_unz6 = dict(_unz6)
    for _pid6, _lab6, _off6, _r6m, _m6m in _plaene6:
        for _t6, _o6 in list(_off6.items()):
            _u6 = min(_o6, int(_rest_unz6.get(_t6, 0) or 0))
            if _u6 > 0:
                _off6[_t6] = _o6 - _u6
                _rest_unz6[_t6] -= _u6
    # Aggregat UND Bedarf aus DENSELBEN offenen Runs (eine Wahrheit) -
    # dieselbe Anteils-Rechnung wie `_bedarf`, nur ohne dessen globale
    # Laufend-Karte.
    _out6 = {}
    _offen6, _bedarf6, _jeplan6, _label6 = {}, {}, {}, {}
    for _pid6, _lab6, _off6, _r6m, _m6m in _plaene6:
        _b_pl6 = {}
        for _t6, _o6 in _off6.items():
            _offen6[_t6] = _offen6.get(_t6, 0) + _o6
            _ges6 = int(_r6m.get(_t6, 0) or 0)
            if _o6 <= 0 or _ges6 <= 0:
                continue
            _a6 = float(_o6) / float(_ges6)
            for _m6, _q6 in (_m6m.get(_t6) or []):
                _b_pl6[int(_m6)] = (_b_pl6.get(int(_m6), 0)
                                    + int(int(_q6 or 0) * _a6))
        _jeplan6[_pid6] = _b_pl6
        _label6[_pid6] = _lab6
        for _m6, _q6 in _b_pl6.items():
            _bedarf6[int(_m6)] = _bedarf6.get(int(_m6), 0) + int(_q6 or 0)
    # AUSSTOSS JE RUN AUS DEM PLAN, NICHT AUS DER SDE (24.10.2026,
    # SEIN BERICHT HAT ES SOFORT GEZEIGT): Abschnitt 6 meldete
    # "Tungsten Carbide fehlen 14'454'615". Das ist der Phantom-Posten
    # von heute frueh, und ich habe ihn selbst wieder eingebaut.
    # Tungsten Carbide hat ZWEI Rezepte (20 und 10'000 je Run);
    # `_out_qty_map` nimmt `SELECT ... LIMIT 1` und erwischt die 20 -
    # Faktor 500 daneben. Genau davor warnt aa647, und genau das habe
    # ich hier wiederholt. Der Plan WEISS es besser: `build_made` /
    # `build_runs` ist die Ausbringung, mit der er gerechnet hat. Die
    # SDE bleibt nur Rueckfall fuer Items, die kein Plan baut.
    _out6 = {}
    for pl in alle:
        _sn6 = MainWindowHelpers._plan_snapshot_unpack(
            (pl.get("frozen") or {}).get("plan_snapshot") or {})
        _br6 = {int(k): int(v or 0)
                for k, v in (_sn6.get("build_runs") or {}).items()}
        _md6 = {int(k): int(v or 0)
                for k, v in (_sn6.get("build_made") or {}).items()}
        for _t6 in _br6:
            if _br6[_t6] > 0 and _md6.get(_t6):
                _out6.setdefault(_t6, max(1, _md6[_t6] // _br6[_t6]))
    _sde6 = _out_qty_map({t for t in (set(_offen6) | set(laufend or {}))
                          if t not in _out6})
    for _t6, _q6 in _sde6.items():
        _out6.setdefault(int(_t6), int(_q6))
    angebot6 = dict(live)
    for _t6, _r6 in (laufend or {}).items():
        angebot6[int(_t6)] = (angebot6.get(int(_t6), 0)
                              + int(_r6 or 0) * int(_out6.get(int(_t6), 0)))
    for _t6, _r6 in _offen6.items():
        angebot6[int(_t6)] = (angebot6.get(int(_t6), 0)
                              + int(_r6 or 0) * int(_out6.get(int(_t6), 0)))
    # ---- REKURSIV AUFLOESEN (24.10.2026) --------------------------------
    # NUTZER, direkt nach dem ersten brauchbaren Urteil: "sind denn
    # genuegend materialien vorhanden um diese selbstgebauten posten
    # auch selber zu bauen?" GENAU DIE FRAGE blieb bisher offen - ich
    # hatte die Grenze selbst eingeraeumt ("rechnet eine Ebene tief"),
    # und eine eingeraeumte Luecke ist immer noch eine Luecke.
    # Fehlen 1'487'237 Sylramic Fibers, sind das ~N Runs, und DIE
    # brauchen Ceramic Powder, Evaporite Deposits und so weiter - was
    # wieder fehlen kann. Also wird so lange nachgerechnet, bis sich
    # nichts mehr aendert, genau wie `nachlauf_runs` es im Runplaner
    # tut. Jede Reaktionskette endet irgendwann bei kaufbarem Material.
    # ZUTATEN JE RUN AUS DEM PLAN (`build_mats` / `build_runs`), nie aus
    # der SDE - dieselbe Lehre wie beim Ausstoss (Tungsten Carbide hat
    # zwei Rezepte, Faktor 500).
    _rez6 = {}
    for pl in alle:
        _sn_r = MainWindowHelpers._plan_snapshot_unpack(
            (pl.get("frozen") or {}).get("plan_snapshot") or {})
        _br_r = {int(k): int(v or 0)
                 for k, v in (_sn_r.get("build_runs") or {}).items()}
        for _t_r, _mats_r in (_sn_r.get("build_mats") or {}).items():
            _t_r = int(_t_r)
            if _t_r in _rez6 or not _br_r.get(_t_r):
                continue
            _rez6[_t_r] = [(int(_m), int(_q or 0) / float(_br_r[_t_r]))
                           for _m, _q in (_mats_r or [])]

    def _fehlstand6(bed, ang):
        _o = {}
        for _t, _b in bed.items():
            _d = int(ang.get(int(_t), 0)) - int(_b or 0)
            if _d < 0:
                _o[int(_t)] = (-_d, int(ang.get(int(_t), 0)), int(_b or 0))
        return _o

    _bedarf6 = dict(_bedarf6)
    _zusatz6 = {}            # {tid: zusaetzliche Runs}
    for _runde6 in range(12):
        _fehl6 = _fehlstand6(_bedarf6, angebot6)
        _neu6 = False
        for _t6, (_f6, _a6, _b6) in list(_fehl6.items()):
            _je6 = int(_out6.get(int(_t6), 0) or 0)
            if int(_t6) not in _rez6 or _je6 <= 0:
                continue                      # kaufbar - Kette endet hier
            _runs6 = -(-_f6 // _je6)
            if _runs6 <= 0:
                continue
            _zusatz6[int(_t6)] = _zusatz6.get(int(_t6), 0) + _runs6
            angebot6[int(_t6)] = angebot6.get(int(_t6), 0) + _runs6 * _je6
            for _m6, _pr6 in _rez6[int(_t6)]:
                _bedarf6[int(_m6)] = (_bedarf6.get(int(_m6), 0)
                                      + int(-(-_pr6 * _runs6 // 1)))
            _neu6 = True
        if not _neu6:
            break
    _fehl6 = _fehlstand6(_bedarf6, angebot6)
    # `_zusatz6` MIT AUFNEHMEN - die Zusatz-Runs koennen Erzeugnisse
    # nennen, die in der Fehlliste gar nicht mehr stehen (weil sie
    # durch genau diese Runs gedeckt sind). Ohne sie stuenden dort
    # nackte type_ids.
    _namen6 = _namen(set(_fehl6) | set(_zusatz6)
                     | set(list(_bedarf6)[:200]))
    p(f"  {_z(len(alle))} aktive Plaene, {_z(len(_bedarf6))} Materialien im")
    p("  Gesamtbedarf. Gerechnet wird VORWAERTS: Hangar + Ausstoss der")
    p("  laufenden Jobs + Ausstoss der noch offenen geplanten Runs gegen")
    p("  die Zutaten, die diese offenen Runs brauchen.")
    p("")
    # NUR CHARAKTER-LUECKEN machen blind (s.o.) - eine Corp ohne
    # Auftraege kann nichts verstecken.
    # Blind machen Charakter-Luecken IMMER. Eine Corp-Luecke macht blind,
    # wenn KEINE Corporation gelesen werden konnte UND auf Charakteren
    # nichts laeuft - dann faehrt der Nutzer offensichtlich ueber die
    # Corp, und genau die fehlt. Wer wie er auf Charakteren baut, sieht
    # seine Runs und bekommt sein Urteil.
    _blind6 = [_l for _l in _job_luecken if not _l.startswith("Corp ")]
    if (_job_luecken and not _job_herk.get("corp_ok")
            and not _job_herk.get("char")):
        _blind6 = list(_job_luecken)
    if _blind6:
        p("  KEIN URTEIL MOEGLICH: oben sind Job-Abrufe fehlgeschlagen.")
        p("  Ohne die laufenden Jobs ist jede Aussage hier geraten - und")
        p("  zwar in die gefaehrliche Richtung (es saehe zu knapp aus).")
        p("  Die Zahlen unten stehen trotzdem da, aber nimm sie als")
        p("  Anhaltspunkt, nicht als Antwort.")
        p("")
    if not _fehl6 and not _blind6:
        p("  ES GEHT AUF. Ueber alle Plaene, alle Hangare (Charaktere und")
        p("  Corp), alle Bauschleifen und alle offenen Runs hinweg kommt")
        p("  am Ende fuer JEDES Material mindestens die geplante Menge")
        p("  heraus. Du kannst alles zu Ende bauen, ohne etwas")
        p("  nachzukaufen - unabhaengig davon, welcher Charakter welchen")
        p("  Run faehrt und ob ESI einen einzelnen Haken belegen kann.")
    elif not _fehl6:
        p("  Nach den vorhandenen Daten fehlt nichts - aber s. oben.")
    else:
        p(f"  ES GEHT NICHT AUF: {_z(len(_fehl6))} Material(ien) fehlen")
        p("  ueber ALLE Plaene zusammen. Das ist die Einkaufsliste, die")
        p("  wirklich zaehlt - nicht die eines einzelnen Plans.")
        p("")
        # KAUFEN ODER BAUEN - DAS IST DER UNTERSCHIED, DER ZAEHLT
        # (24.10.2026). Sein Lauf um 13:53 liess genau vier Posten
        # uebrig, und ALLE VIER baut er selbst (Sylramic Fibers, Fernite
        # Carbide, Hypersynaptic Fibers, Ferrogel). Darunter stand
        # trotzdem "es muss gekauft werden" - fuer einen selbstgebauten
        # Posten ist das schlicht falsch und schickt ihn an den Markt
        # statt an den Reaktor. Ein Bericht, der die falsche Handlung
        # nahelegt, ist schlimmer als einer, der schweigt.
        _baut6 = set()
        for pl in alle:
            _sn_b = MainWindowHelpers._plan_snapshot_unpack(
                (pl.get("frozen") or {}).get("plan_snapshot") or {})
            for _t_b, _r_b in (_sn_b.get("build_runs") or {}).items():
                if int(_r_b or 0) > 0:
                    _baut6.add(int(_t_b))
        p(f"  {'MATERIAL':30} {'VORHANDEN+KOMMT':>16} {'GEBRAUCHT':>13} "
          f"{'FEHLT':>12}  WAS TUN")
        for _t6, (_f6, _a6, _b6) in sorted(_fehl6.items(),
                                           key=lambda x: -x[1][0]
                                           )[:args.zeilen]:
            _tun6 = "bauen" if int(_t6) in _baut6 else "KAUFEN"
            p(f"  {str(_namen6.get(_t6) or _t6)[:30]:30} {_z(_a6):>16} "
              f"{_z(_b6):>13} {_z(_f6):>12}  {_tun6}")
        if len(_fehl6) > args.zeilen:
            p(f"  ... und {_z(len(_fehl6) - args.zeilen)} weitere")
        p("")
        p("  \"VORHANDEN+KOMMT\" ist Hangar plus alles, was aus laufenden")
        p("  und noch offenen Runs noch entsteht.")
        p("  Was hier steht, ist VOLLSTAENDIG aufgeloest: die Kette wurde")
        p("  so lange nachgerechnet, bis sich nichts mehr aenderte. Was")
        p("  uebrig bleibt, entsteht nirgends mehr von selbst.")
    p("")

    if _zusatz6:
        p("  DAFUER MUSST DU ZUSAETZLICH BAUEN (ueber alle Plaene, rekursiv")
        p("  aufgeloest - die Antwort auf \"sind denn genuegend Materialien")
        p("  vorhanden um diese selbstgebauten Posten auch selber zu")
        p("  bauen?\"):")
        p("")
        p(f"  {'ERZEUGNIS':38} {'ZUSAETZLICHE RUNS':>18}")
        for _t6, _r6 in sorted(_zusatz6.items(), key=lambda x: -x[1]
                               )[:args.zeilen]:
            p(f"  {str(_namen6.get(_t6) or _t6)[:38]:38} {_z(_r6):>18}")
        p("")
        p("  Diese Runs sind IN DEN ZAHLEN OBEN schon eingerechnet - die")
        p("  Fehlliste zeigt also, was auch DANN noch fehlt. Steht oben")
        p("  nichts mehr, reicht dein Material fuer die ganze Kette.")
        p("")

    # ---- 6b) WEN TRIFFT ES? ---------------------------------------------
    # NUTZER 24.10.2026: "wenn doch gesammthaft über alle baupläne runs
    # fehlen, muss irgend ein Bauplan diese Runs ausführen, welche werden
    # dass sein? Also primär sollte schon darauf geachtet werden dass alle
    # Baupläne in erster Linie einfach 'ihre Runs' absolvieren müssen.
    # sonst schiebt ja diese Logik alle runs immer weiter zum nächsten
    # Bauplan das wäre auch schlecht."
    #
    # SEINE SORGE IST BERECHTIGT UND TRIFFT HIER NICHT ZU - beides
    # gehoert gesagt:
    #   * RUNS WERDEN NIE VERSCHOBEN. Jeder Plan hat seine eigenen
    #     `build_runs`, und `nachlauf_runs` bekommt ausschliesslich die
    #     `build_runs`/`build_mats` DIESES Plans. Ein Nachlauf-Run
    #     entsteht nur dort, wo das Erzeugnis auch gebraucht wird - er
    #     kann einem anderen Plan gar nichts zuschieben.
    #   * DIESER BERICHT TEILT NICHTS ZU. Er ist eine Auskunft: geht die
    #     Summe auf, ja oder nein. Er aendert keinen Plan.
    # WAS ER ABER BEANTWORTEN MUSS, ist seine Frage "welche werden das
    # sein?". Die Antwort steht schon fest, lange bevor etwas fehlt: die
    # KARTENREIHENFOLGE. Rang 1 zieht null fremde Reservierungen ab, der
    # letzte zieht alle ab - wer hinten steht, geht leer aus. Hier wird
    # genau dieser Wasserfall einmal durchgerechnet, damit er es SIEHT
    # und die Reihenfolge danach selbst bestimmen kann.
    if _fehl6 and not _blind6:
        p("=" * 78)
        p("6b) WEN TRIFFT ES? (Wasserfall nach Kartenreihenfolge)")
        p("=" * 78)
        try:
            _rang6 = MainWindowHelpers.plan_rang(settings) or {}
        except Exception:
            _rang6 = {}
        _folge6 = sorted(_jeplan6, key=lambda k: _rang6.get(k, 10 ** 6))
        _vorrat6 = dict(angebot6)
        _trifft6 = {}
        for _pid6 in _folge6:
            for _t6, _n6 in sorted((_jeplan6.get(_pid6) or {}).items(),
                                   key=lambda x: -x[1]):
                _da6 = int(_vorrat6.get(int(_t6), 0))
                _nimmt6 = max(0, min(int(_n6 or 0), _da6))
                _vorrat6[int(_t6)] = _da6 - _nimmt6
                if _nimmt6 < int(_n6 or 0):
                    _trifft6.setdefault(_pid6, []).append(
                        (int(_t6), int(_n6) - _nimmt6))
        p("  Die Plaene nehmen sich der Reihe nach, was sie brauchen -")
        p("  genau so, wie die Reservierung es im Programm tut. Wer")
        p("  uebrig bleibt, steht hier:")
        if _zusatz6:
            p("")
            p("  LIES DAS MIT VORSICHT, solange oben Zusatz-Runs stehen:")
            p("  dieser Wasserfall verteilt den DIREKTEN Bedarf der Plaene.")
            p("  Die Zutaten der rekursiv ergaenzten Runs lassen sich nicht")
            p("  sauber EINEM Plan zuordnen - sie gehoeren der Kette. Was")
            p("  am Ende wirklich fehlt, steht deshalb oben, nicht hier.")
        p("")
        for _pid6 in _folge6:
            _lst6 = _trifft6.get(_pid6)
            _r6 = _rang6.get(_pid6, "?")
            if not _lst6:
                p(f"  #{_r6} {_label6.get(_pid6, _pid6)[:40]:40} "
                  f"kommt durch")
                continue
            p(f"  #{_r6} {_label6.get(_pid6, _pid6)[:40]:40} "
              f"GEHT LEER AUS bei {_z(len(_lst6))} Material(ien):")
            for _t6, _f6 in sorted(_lst6, key=lambda x: -x[1])[:6]:
                p(f"        {str(_namen6.get(_t6) or _t6)[:34]:34} "
                  f"fehlen {_z(_f6)}")
            if len(_lst6) > 6:
                p(f"        ... und {_z(len(_lst6) - 6)} weitere")
        p("")
        # ---- 6c) GEHT ES BESSER? (emm658, gemessen in Z12) ----------
        # Z12 hat drei Arten verglichen, einen knappen Vorrat zu
        # verteilen, und zwar an dem Massstab, der ihm wichtig ist: WIE
        # VIELE PLAENE WERDEN WIRKLICH FERTIG. Ergebnis ueber 450 knappe
        # Lagen: "kleinster Bedarf zuerst" schafft in rund einem Drittel
        # MEHR Plaene, in gut der Haelfte gleich viele, in 1-2 % weniger.
        # "Anteilig" war KEIN EINZIGES Mal besser - alle bekommen etwas,
        # keiner wird fertig.
        # DIE REGEL WIRD TROTZDEM NICHT GEAENDERT. Sie ist seine
        # Entscheidung ("wenn ich einen Plan reserviert habe, dann baue
        # ich ihn IMMER"), und eine Maschine, die die Reihenfolge
        # heimlich umstellt, nimmt ihm genau die Kontrolle, um die es
        # ihm geht. Also: rechnen, zeigen, ihn ziehen lassen.
        def _fertige6(_folge):
            _v = dict(angebot6)
            _n = 0
            for _p in _folge:
                _br = (_jeplan6.get(_p) or {})
                if all(_v.get(int(_t), 0) >= int(_q)
                       for _t, _q in _br.items()):
                    for _t, _q in _br.items():
                        _v[int(_t)] = _v.get(int(_t), 0) - int(_q)
                    _n += 1
                else:
                    for _t, _q in _br.items():
                        _v[int(_t)] = max(0, _v.get(int(_t), 0) - int(_q))
            return _n
        _best6 = sorted(_jeplan6, key=lambda k: sum(
            (_jeplan6.get(k) or {}).values()))
        _na6, _nc6 = _fertige6(_folge6), _fertige6(_best6)
        if _nc6 > _na6:
            p("  GEHT ES BESSER? JA: mit deiner jetzigen Reihenfolge")
            p(f"  werden {_z(_na6)} von {_z(len(_folge6))} Plaenen fertig.")
            p(f"  Mit dieser Reihenfolge waeren es {_z(_nc6)}:")
            for _i6, _pid6 in enumerate(_best6):
                p(f"        {_i6 + 1}. {_label6.get(_pid6, _pid6)[:50]}")
            p("")
            p("  WARUM DAS NICHT VON SELBST PASSIERT: die Reihenfolge ist")
            p("  deine Entscheidung. Ein Werkzeug, das sie heimlich")
            p("  umstellt, nimmt dir genau die Kontrolle, um die es hier")
            p("  geht. Du entscheidest - das hier ist nur die Rechnung.")
        elif _na6 >= len(_folge6):
            # SEIN LAUF UM 14:00 zeigte "3 von 3 Plaenen durch" - und
            # darunter stand trotzdem "Es fehlt schlicht Material".
            # Unsinn, wenn alle durchkommen. Der Satz gehoerte in den
            # Fall, in dem wirklich jemand leer ausgeht.
            p(f"  ALLE {_z(len(_folge6))} PLAENE KOMMEN DURCH - an der")
            p("  Reihenfolge gibt es nichts zu verbessern.")
        else:
            p("  GEHT ES BESSER? NEIN: deine Reihenfolge bringt")
            p(f"  {_z(_na6)} von {_z(len(_folge6))} Plaenen durch, und keine")
            p("  andere schafft mehr. Es fehlt schlicht Material.")
        p("")
        p("  SO AENDERST DU ES: die Reihenfolge ist deine - zieh in \"My")
        p("  build plans\" den Plan nach oben, der zuerst fertig werden")
        p("  soll. Dann trifft es einen anderen. Was NICHT passiert: dass")
        p("  ein Plan die Runs eines anderen uebernimmt. Jeder faehrt")
        p("  seine eigenen - nur das Material folgt dem Rang.")
        p("")

    p("=" * 78)
    p("URTEIL")
    p("=" * 78)
    if luecken:
        p(f"  {_z(sum(v[2] for v in luecken.values()))} Stueck in "
          f"{_z(len(luecken))} Posten hat ein Plan aus dem Bestand")
        p("  eingeplant, ohne dass sie heute da sind. GENAU DAS ist das")
        p("  Muster, das du beschreibst: nie auf einer Liste, nie bezahlt,")
        p("  und trotzdem weg. Abschnitt 3 sagt, wohin.")
    else:
        p("  Keine Deckungsluecke gefunden. Dann liegt dein Fall woanders -")
        p("  schau in Abschnitt 1, ob eine Liste unvollstaendig abgearbeitet")
        p("  wurde.")
    p("")
    p("  Dieses Werkzeug aendert nichts.")
    _schreiben(aus)


if __name__ == "__main__":
    main()
