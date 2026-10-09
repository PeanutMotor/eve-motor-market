"""Zeigt, WARUM „Stock locations" ein Material als fehlend meldet - Bedarf
und Bestand nebeneinander, mit jeder Zwischenzahl (Fassung 1, 07.10.2026).

WOZU: Nutzer-Befund 07.10.2026 - „Stock locations zeigt an, dass mir diese
Materialien fehlen, wahrscheinlich für den Rig-Plan. Aber ich habe für den
Rig-Plan damals schon alles eingekauft und alles nach Dockside gebracht
gehabt - gibt es einen Rechenfehler irgendwo?"

Die Seite rechnet seit emm463 nicht mehr mit der VOLLEN Planmenge, sondern
mit dem NOCH OFFENEN Bedarf: Plan-Runs minus die Runs, die laut lokaler
Job-Zuordnung oder Hand-Haken schon gebaut sind. Bewegen kann sich also
genau zweierlei - was als „schon gebaut" erkannt wird, und der Bestand an
den eingeschalteten Orten. Dieser Bericht stellt beide Seiten mit allen
Zwischenzahlen hin, damit man SIEHT, welche sich bewegt hat, statt zu raten
(Regel 5).

Je Plan steht hier:
  * die Endprodukte mit ihren Plan-Runs,
  * JE POSITION: Plan-Runs, Runs aus zugeordneten ESI-Jobs, Runs aus
    Hand-Haken, die daraus gerechnete Zahl (das Maximum beider) und die
    daraus folgenden offenen Runs,
  * JE MATERIAL: offener Bedarf gegen den vollen Plan-Bedarf,
  * ausdrücklich die Zeile „KEINE GEBAUTEN RUNS ERKANNT", wenn das Werkzeug
    für diesen Plan gar keinen Fortschritt kennt - dann verlangt er das
    Material zu Recht noch einmal, und die Frage ist, warum die Jobs nicht
    zugeordnet sind (Runplaner -> „Job assignments").

Danach je Material mit Bedarf: der Bestand JE ORT, getrennt nach ein- und
ausgeschalteten Orten (ein abgeschalteter Ort zählt nirgends - emm461), und
der Fehlbetrag, den die Seite daraus bildet.

FASSUNG 2 (08.10.2026, nach dem ersten Bericht des Nutzers): die
Bedarfsseite ging dort auf den Stueck genau auf, im Hangar fehlten aber
888 Interface Circuit / 772 Micro Circuit / 624 Current Pump - und an den
abgeschalteten Orten lag davon nichts. Die Frage ist damit nicht mehr
"rechnet es falsch", sondern "wer hat es verbraucht". Deshalb stehen jetzt
auch die drei Verbraucher da, die in keinem Abschnitt vorkamen:
  * ESI-Jobs, die KEINEM Plan zugeordnet sind (Fertigung/Reaktion, aktiv,
    fertig oder abgeliefert) - ihr Material ist weg, ohne dass irgendein
    Plan seinen Bedarf dafuer senkt,
  * was genau diese Jobs an den FEHLENDEN Materialien genommen haben
    (Obergrenze, ohne ME-Bonus der fremden Blaupause),
  * ABGESCHLOSSENE Plaene, die dasselbe Material brauchten: sie zaehlen im
    Bedarf zu Recht nicht mehr, haben aber aus demselben Hangar genommen.

GERATEN WIRD HIER NICHTS: gerechnet wird mit denselben Funktionen wie das
Werkzeug (`lagerorte`, `mw_helpers.restbedarf_map`), die Rohdaten stehen
daneben.

FASSUNG 3 (08.10.2026, nach dem zweiten Bericht): zwischen 20:44 und 21:46
fiel der Bestand an der Dockside von 41'464'561 auf 3'079'105 Stueck (Asset-
Zeilen 3'886 -> 2'501), alle anderen 16 Orte blieben fast gleich. Mexallon
3'177'313 -> 0, Interface Circuit 17'513 -> 0, Tritanium 33'893'717 ->
3'046'441. Material verdampft nicht - der ABRUF war unvollstaendig. Was
fehlte, um das zu belegen: WELCHER Charakter. Deshalb steht jetzt vor dem
Bestand eine Tabelle JE CHARAKTER (Asset-Zeilen, Stueck, Fehlertext) und
daneben die Zahlen des VORIGEN Laufs aus `berichte/lagerorte_stand.json`;
sinkt eine Zeilenzahl deutlich, sagt der Bericht es laut. Dazu steht je
Material und Ort, WEM der Stapel gehoert - sonst sieht man nicht, dass ein
Ort nur noch die Stapel EINES Charakters zeigt.

AUFRUF: werkzeuge\\zeige_lagerorte.bat doppelklicken.
Danach liegt `berichte\\lagerorte_bericht.txt` da - die hochladen.
Es wird NUR GELESEN: settings.json wird direkt gelesen (NICHT ueber
`config.load_settings`, das beim Laden Migrationen ausfuehrt und dabei
speichern wuerde), die Datenbank nur lesend abgefragt.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import (config, corp, esi, industry, lagerorte,   # noqa: E402
                        store)

FASSUNG = 3
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERICHT = os.path.join(WURZEL, "berichte", "lagerorte_bericht.txt")


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


def _restbedarf(runs, mats, gebaut):
    """(rest_runs, material) - DIESELBE Funktion, mit der das Werkzeug
    rechnet (`mw_helpers.restbedarf_map`), nicht nachgebaut: zwei
    Rechnungen fuer dieselbe Zahl waeren zwei Wahrheiten (Regel 9)."""
    from eve_trader.ui.mw_helpers import restbedarf_map
    return restbedarf_map(runs or {}, mats or {}, gebaut or {})


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
    """Nur BEKANNTE Quellen - Bau-Strukturen, gemerkte Namen, NPC-Stationen.
    KEIN resolve_structure: das kostet bei fehlendem Andockrecht 403er aufs
    ESI-Fehlerbudget (emm462), und fuer den Bericht genuegt die Nummer."""
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


def _settings_rohe():
    """settings.json ROH lesen - OHNE `config.load_settings()`.

    Grund (gemessen 08.10.2026): `load_settings` fuehrt Migrationen aus und
    archiviert faellige erledigte Plaene; laeuft eine davon, SCHREIBT es
    settings.json. Dieses Werkzeug sagt im Kopf zu, nichts zu veraendern -
    also liest es die Datei selbst und mischt nur die Vorgaben darunter
    (dieselben zwei Schritte wie load_settings, nur ohne den dritten)."""
    data = dict(config.DEFAULT_SETTINGS)
    try:
        import json as _j
        with open(config.settings_path(), encoding="utf-8") as fh:
            data.update(_j.load(fh) or {})
    except Exception:
        # Unlesbar: dann doch den normalen Weg, sonst gibt es gar keinen
        # Bericht. Steht im Kopf des Berichts.
        data = config.load_settings() or {}
        data["_ueber_load_settings"] = True
    return data


def _archiv_plaene():
    """Die ins Archiv verschobenen Plaene (`bauplan_archiv.json`, emm388).
    Ein Plan, der seit 30 Tagen abgeschlossen ist, steht NICHT mehr in
    bau_saved_plans - sein Materialverbrauch waere sonst unsichtbar."""
    try:
        import json as _j
        with open(config.bauplan_archiv_path(), encoding="utf-8") as fh:
            out = _j.load(fh) or []
        return [x for x in out if isinstance(x, dict)]
    except Exception:
        return []


def _stand_pfad():
    return os.path.join(WURZEL, "berichte", "lagerorte_stand.json")


def _stand_lesen():
    """Die Asset-Zahlen des VORIGEN Laufs - oder {} (Fassung 3).

    Damit sieht man einen unvollstaendigen Abruf SOFORT: sinkt die
    Zeilenzahl eines Charakters stark, hat ESI nicht alles geliefert
    (gemessen am 08.10.2026: 3'886 -> 2'501 Zeilen, 38 Mio Stueck weg).
    Nur lesen/schreiben in `berichte` - die Einstellungen bleiben unberuehrt.
    """
    try:
        import json as _j
        with open(_stand_pfad(), encoding="utf-8") as fh:
            d = _j.load(fh) or {}
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _stand_schreiben(chars_stat):
    try:
        import json as _j
        os.makedirs(os.path.dirname(_stand_pfad()), exist_ok=True)
        with open(_stand_pfad(), "w", encoding="utf-8") as fh:
            _j.dump({"ts": time.time(), "chars": chars_stat}, fh)
    except Exception:
        pass


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
    p(f"STOCK LOCATIONS - BEDARF UND BESTAND (Fassung {FASSUNG})")
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
        p("")
    try:
        zuordnung = store.job_zuordnung_details() or {}
    except Exception as e:
        zuordnung = {}
        p(f"job_zuordnung nicht lesbar: {type(e).__name__}: {e}")
        p("")

    if settings.get("_ueber_load_settings"):
        p("HINWEIS: settings.json war nicht direkt lesbar - gelesen ueber den")
        p("normalen Weg des Programms (der fuehrt Migrationen aus).")
        p("")
    plaene = lagerorte.plaene_fuer_lagerorte(settings)
    alle = list(settings.get("bau_saved_plans") or [])
    archiv = _archiv_plaene()
    p(f"Verlinkte Charaktere: {len(chars)} · Gespeicherte Baupläne: "
      f"{len(alle)} · davon in Stock locations: {len(plaene)}")
    p("")
    p("NICHT in Stock locations (und warum):")
    _ids = {str(x.get("id")) for x in plaene}
    for x in alle:
        if str(x.get("id")) in _ids:
            continue
        grund = ("abgeschlossen" if x.get("done_manual")
                 else "nicht eingefroren (kein Schnappschuss)"
                 if not ((x.get("frozen") or {}).get("plan_snapshot"))
                 else "Mitglied eines Multiplans")
        p(f"  {x.get('label') or x.get('item_name') or x.get('id')}: {grund}")
    if len(alle) == len(plaene):
        p("  (keiner)")
    p("")

    # ---- 1. JE PLAN: WAS GILT ALS GEBAUT -----------------------------------
    bedarf_je_plan = {}
    for pl in plaene:
        pid = pl.get("id")
        label = str(pl.get("label") or pl.get("item_name") or pid or "?")
        snap = _unpack(((pl.get("frozen") or {}).get("plan_snapshot")) or {})
        runs = {int(t): int(r or 0)
                for t, r in (snap.get("build_runs") or {}).items()}
        mats = {int(t): v for t, v in (snap.get("build_mats") or {}).items()}
        gebaut = lagerorte.gebaute_runs(pl, zuordnung)
        rest_runs, rest_mat = _restbedarf(runs, mats, gebaut)
        _, voll_mat = _restbedarf(runs, mats, {})

        # Die beiden Quellen getrennt, damit sichtbar ist, WOHER die Zahl kommt.
        aus_jobs, jobs_liste = {}, []
        for jid, e in (zuordnung or {}).items():
            if str((e or {}).get("plan_id")) != str(pid):
                continue
            try:
                t = int(e.get("type_id") or 0)
                r = int(e.get("runs") or 0)
            except (TypeError, ValueError):
                continue
            if t > 0 and r > 0:
                aus_jobs[t] = aus_jobs.get(t, 0) + r
                jobs_liste.append((jid, t, r, e.get("quelle"), e.get("ts")))
        aus_haken = {}
        for k, v in (pl.get("checked_runplan_runs") or {}).items():
            try:
                t = int(str(k).split("|")[-1])
                r = int(v or 0)
            except (TypeError, ValueError):
                continue
            if t > 0 and r > 0:
                aus_haken[t] = aus_haken.get(t, 0) + r

        enden = [(int(t), int(q or 0)) for t, q in (pl.get("enden") or [])]
        if not enden and pl.get("type_id"):
            try:
                enden = [(int(pl["type_id"]), int(pl.get("qty") or 1))]
            except (TypeError, ValueError):
                enden = []
        namen = _namen(set(runs) | set(rest_mat) | set(voll_mat)
                       | {t for t, _q in enden})

        p("-" * 78)
        p(f"PLAN  {label}   (id {pid})")
        p("-" * 78)
        p(f"  eingefroren: {_zeit((pl.get('frozen') or {}).get('ts'))}"
          f" · Schloss: {'an' if pl.get('reserve') else 'aus'}"
          f" · Positionen im Schnappschuss: {len(runs)}")
        for t, q in enden:
            p(f"  Endprodukt: {namen.get(t, t)} × {_z(q)}"
              f"   (Plan-Runs {_z(runs.get(t, 0))},"
              f" offen {_z(rest_runs.get(t, 0))})")
        if not gebaut:
            p("")
            p("  >>> KEINE GEBAUTEN RUNS ERKANNT. Dieser Plan verlangt sein")
            p("  >>> Material deshalb in VOLLER Höhe - das ist die sichere")
            p("  >>> Richtung (Regel 3), aber wenn du längst gebaut hast,")
            p("  >>> fehlt die Zuordnung der ESI-Jobs. Siehe unten.")
        p("")
        p("  POSITION                          PLAN   JOBS  HAKEN  "
          "GERECHNET   OFFEN")
        for t in sorted(runs, key=lambda x: str(namen.get(x, x)).lower()):
            p(f"  {str(namen.get(t, t))[:32]:<32} {_z(runs[t]):>6} "
              f"{_z(aus_jobs.get(t, 0)):>6} {_z(aus_haken.get(t, 0)):>6} "
              f"{_z(gebaut.get(t, 0)):>10} {_z(rest_runs.get(t, 0)):>7}")
        p("")
        p(f"  ZUGEORDNETE ESI-JOBS: {len(jobs_liste)}")
        for jid, t, r, quelle, ts in sorted(jobs_liste,
                                            key=lambda x: str(x[0])):
            p(f"      Job {jid}  {str(namen.get(t, t))[:28]:<28} "
              f"{_z(r):>6} Runs  Quelle {quelle}  {_zeit(ts)}")
        if not jobs_liste:
            p("      (keiner - dann zählt nur, was von Hand abgehakt ist)")
        p("")
        p("  MATERIAL                       OFFENER BEDARF   VOLLER BEDARF")
        for t in sorted(set(rest_mat) | set(voll_mat),
                        key=lambda x: str(namen.get(x, x)).lower()):
            p(f"  {str(namen.get(t, t))[:30]:<30} {_z(rest_mat.get(t, 0)):>14} "
              f"{_z(voll_mat.get(t, 0)):>15}")
        p("")
        try:
            bedarf_je_plan[pid] = lagerorte.bedarf_aus_plaenen([pl], zuordnung)
        except Exception as e:
            bedarf_je_plan[pid] = {}
            p(f"  bedarf_aus_plaenen scheiterte: {type(e).__name__}: {e}")
            p("")

    # ---- 2. DER BEDARF, DEN DIE SEITE ANZEIGT ------------------------------
    bedarf = lagerorte.bedarf_aus_plaenen(plaene, zuordnung)
    gebaut_tids = lagerorte.gebaute_tids(plaene)

    # ---- 3. BESTAND (ESI, ALLE ORTE) ---------------------------------------
    zeilen, failed = [], []
    char_namen = {}
    try:
        ctypes = esi.container_type_ids_safe()
    except Exception:
        ctypes = set()
    # JE CHARAKTER MITZAEHLEN (Fassung 3): nur so ist belegbar, ob ein
    # Abruf unvollstaendig war - der Bericht vom 08.10.2026 verlor 1'385
    # Asset-Zeilen und 38 Mio Stueck an EINEM Ort, ohne ein Wort darueber.
    chars_stat = {}
    for ch in chars:
        cid = int(ch["character_id"])
        nm = ch.get("character_name") or ch.get("name") or str(cid)
        char_namen[("char", cid)] = nm
        try:
            assets = esi._fetch_all_assets(client_id, cid)
        except Exception as e:
            failed.append(f"{nm}: {type(e).__name__}: {e}")
            chars_stat[nm] = {"zeilen": None, "stueck": None,
                              "fehler": f"{type(e).__name__}: {e}"}
            continue
        _z_neu = lagerorte.zeilen_aus_assets(assets, ctypes, cid, "char")
        chars_stat[nm] = {
            "zeilen": len(_z_neu),
            "stueck": sum(int(z.get("menge") or 0) for z in _z_neu),
            "roh": len(assets or []), "fehler": ""}
        zeilen.extend(_z_neu)
    if settings.get("use_corp"):
        divs = corp.divisions_bereinigt(settings.get("corp_divisions"))
        # DIESELBE Regel wie im Werkzeug (corp.abrufplan): EIN Charakter je
        # Corporation - sonst liefert ESI denselben Hangar mehrfach.
        corp_von, rollen_von = {}, {}
        for ch in chars:
            cid = int(ch["character_id"])
            try:
                corp_von[cid] = esi.fetch_character_corporation(cid)
                rollen_von[cid] = esi.fetch_character_roles(client_id, cid)
            except Exception as e:
                failed.append(f"Corp-Rollen {ch.get('character_name')}: "
                              f"{type(e).__name__}: {e}")
                rollen_von[cid] = None
        _plan, _ = corp.abrufplan(chars, corp_von, rollen_von,
                                  corp.ROLLE_ASSETS)
        for corp_id, via in sorted(_plan.items()):
            try:
                cname = esi.fetch_corporation_name(corp_id)
            except Exception:
                cname = f"#{corp_id}"
            char_namen[("corp", int(corp_id))] = f"Corp: {cname}"
            try:
                ca = esi.fetch_corporation_assets(client_id, via, corp_id)
            except Exception as e:
                failed.append(f"Corp {cname}: {type(e).__name__}: {e}")
                chars_stat[f"Corp: {cname}"] = {
                    "zeilen": None, "stueck": None,
                    "fehler": f"{type(e).__name__}: {e}"}
                continue
            _z_corp = lagerorte.zeilen_aus_assets(
                ca, ctypes, int(corp_id), "corp", divisions=divs)
            chars_stat[f"Corp: {cname}"] = {
                "zeilen": len(_z_corp),
                "stueck": sum(int(z.get("menge") or 0) for z in _z_corp),
                "roh": len(ca or []), "fehler": ""}
            zeilen.extend(_z_corp)

    orte = {int(z.get("ort") or 0) for z in zeilen}
    ort_namen = _ort_namen(settings, orte)
    _aus = set()
    for o in (settings.get("lager_orte_aus") or []):
        try:
            _aus.add(int(o))
        except (TypeError, ValueError):
            continue

    namen = _namen(set(bedarf) | {z["tid"] for z in zeilen})
    p("=" * 78)
    p("BESTAND UND FEHLBETRAG - so rechnet die Seite")
    p("=" * 78)
    for f in failed:
        p(f"  ABRUF FEHLGESCHLAGEN {f}")
    p(f"  Asset-Zeilen: {_z(len(zeilen))} · Orte: {len(orte)} ·"
      f" davon abgeschaltet: {len(_aus & orte)}")
    p("")
    # JE CHARAKTER + VERGLEICH MIT DEM VORIGEN LAUF (Fassung 3).
    _vor = (_stand_lesen().get("chars") or {})
    p("  JE CHARAKTER / CORP (Asset-Zeilen und Stueck; VORIGER LAUF daneben):")
    _verdacht = []
    for nm in sorted(chars_stat):
        st = chars_stat[nm] or {}
        v = _vor.get(nm) or {}
        _zl, _st = st.get("zeilen"), st.get("stueck")
        _vz, _vs = v.get("zeilen"), v.get("stueck")
        _txt = (f"      {nm[:28]:<28} "
                f"{('FEHLER' if _zl is None else _z(_zl)):>9} Zeilen "
                f"{('-' if _st is None else _z(_st)):>14} Stueck")
        if _vz is not None:
            _txt += (f"   |  vorher {_z(_vz):>9} Zeilen "
                     f"{_z(_vs or 0):>14} Stueck")
        p(_txt)
        if st.get("fehler"):
            p(f"          ABRUF FEHLGESCHLAGEN: {st['fehler']}")
            _verdacht.append(f"{nm}: Abruf fehlgeschlagen")
        elif (_vz or 0) >= 50 and _zl is not None and _zl < _vz * 0.7:
            _verdacht.append(
                f"{nm}: {_z(_vz)} -> {_z(_zl)} Zeilen (ESI lieferte weniger)")
    p("")
    if _verdacht:
        p("  " + "!" * 70)
        p("  !! UNVOLLSTAENDIGER ABRUF - DIE FEHLBETRAEGE UNTEN SIND ZU HOCH.")
        p("  !! KAUF NICHTS NACH, BEVOR DAS BEHOBEN IST.")
        for v in _verdacht:
            p(f"  !!   {v}")
        p("  " + "!" * 70)
        p("")
    elif not _vor:
        p("  (erster Lauf - ab dem naechsten Mal stehen die Vorwerte daneben)")
        p("")
    # Gemerkt wird nur ein GELUNGENER Abruf - sonst waere nach einem
    # Fehlschlag der Vergleichswert weg, und der naechste unvollstaendige
    # Lauf faellt nicht mehr auf.
    _stand_neu = dict(_vor)
    for _nm, _st in chars_stat.items():
        if (_st or {}).get("zeilen") is not None:
            _stand_neu[_nm] = _st
    _stand_schreiben(_stand_neu)
    p("  ORTE (abgeschaltet = zählt NIRGENDS, auch nicht im Fehlbetrag):")
    for o, nm, menge in lagerorte.orte_mit_bestand(zeilen, ort_namen):
        p(f"      {'AUS' if o in _aus else 'ein'}  {nm[:46]:<46} "
          f"{_z(menge):>12} Stück   #{o}")
    p("")

    fehl_items = {}            # {tid: (noetig, da_ein, fehlt)} - nur ROTE
    for t in sorted(bedarf, key=lambda x: str(namen.get(x, x)).lower()):
        posten = bedarf.get(t) or []
        noetig = sum(int(q or 0) for _l, q in posten)
        je_ort = {}
        for z in zeilen:
            if int(z.get("tid") or 0) != int(t):
                continue
            o = int(z.get("ort") or 0)
            je_ort[o] = je_ort.get(o, 0) + int(z.get("menge") or 0)
        da_ein = sum(m for o, m in je_ort.items() if o not in _aus)
        da_aus = sum(m for o, m in je_ort.items() if o in _aus)
        fehlt = max(0, noetig - da_ein)
        selbst = int(t) in gebaut_tids
        if fehlt > 0 and not selbst:
            fehl_items[int(t)] = (noetig, da_ein, fehlt)
        p(f"  {str(namen.get(t, t))[:40]}")
        p(f"      noch gebraucht {_z(noetig)}"
          + "".join(f" · {_l}: {_z(q)}" for _l, q in posten))
        p(f"      an eingeschalteten Orten {_z(da_ein)}"
          f" · an abgeschalteten {_z(da_aus)}"
          f" · FEHLT {_z(fehlt)}"
          + ("   (baut der Plan selbst -> nie rot)" if selbst else ""))
        for o, m in sorted(je_ort.items(), key=lambda x: -x[1]):
            # WEM gehoert der Stapel (Fassung 3)? Ohne das sieht man nicht,
            # dass ein Ort nur noch die Stapel EINES Charakters zeigt.
            _wem = {}
            for z in zeilen:
                if int(z.get("tid") or 0) != int(t):
                    continue
                if int(z.get("ort") or 0) != int(o):
                    continue
                _k = char_namen.get(
                    (z.get("art"), int(z.get("besitzer") or 0)),
                    str(z.get("besitzer")))
                _wem[_k] = _wem.get(_k, 0) + int(z.get("menge") or 0)
            _wtxt = ", ".join(
                f"{k}: {_z(q)}" for k, q in
                sorted(_wem.items(), key=lambda x: -x[1]))
            p(f"          {'AUS' if o in _aus else 'ein'}  "
              f"{(ort_namen.get(o) or f'#{o}')[:44]:<44} {_z(m):>12}"
              + (f"   [{_wtxt}]" if _wtxt else ""))
        if not je_ort:
            p("          (liegt an keinem Ort deiner Charaktere/Corp)")
    if not bedarf:
        p("  (kein offener Bedarf - dann kann auch nichts fehlen)")
    p("")

    # ---- 4. WOHIN IST ES WEG (Fassung 2) ----------------------------------
    # Nutzer-Befund 08.10.2026 am ersten Bericht: die BEDARFS-Seite ging auf
    # den Stueck genau auf (Riggs 1: voller Bedarf minus die 200 gebauten
    # Runs), es fehlten aber 888 Interface Circuit / 772 Micro Circuit /
    # 624 Current Pump im Hangar - und an den abgeschalteten Orten lag davon
    # nichts. Die Frage ist damit nicht mehr "rechnet es falsch", sondern
    # "wer hat es verbraucht". Die drei Verbraucher, die in keinem der
    # Abschnitte oben vorkommen, stehen hier.
    jobs, job_fehler = [], []
    for ch in chars:
        cid = int(ch["character_id"])
        nm = ch.get("character_name") or ch.get("name") or str(cid)
        try:
            for j in esi.fetch_active_jobs(client_id, cid,
                                           include_delivered=True) or []:
                jobs.append(dict(j, _char=nm))
        except Exception as e:
            job_fehler.append(f"{nm}: {type(e).__name__}: {e}")
    # CORP-JOBS ZAEHLEN WIE CHARAKTER-JOBS (emm483, REGEL CORP = CHARAKTER,
    # Nutzer: "ob ein Spieler eine Corp hat oder nicht sollte keinen
    # Unterschied machen"). corp_von/rollen_von stammen aus dem Corp-
    # Bestandsblock oben (nur mit use_corp vorhanden); ein Job kommt nie
    # doppelt - /characters/.../industry/jobs enthaelt keine Corp-Jobs
    # (geprueft, emm389).
    if settings.get("use_corp"):
        try:
            _pjobs, _ = corp.abrufplan(chars, corp_von, rollen_von,
                                       corp.ROLLE_JOBS)
        except Exception as e:
            _pjobs = {}
            job_fehler.append(f"Corp-Rollen: {type(e).__name__}: {e}")
        for _cjid, _cvia in sorted(_pjobs.items()):
            try:
                for j in esi.fetch_corporation_jobs(
                        client_id, _cvia, _cjid,
                        include_delivered=True) or []:
                    jobs.append(dict(j, _char=f"Corp #{_cjid}"))
            except Exception as e:
                job_fehler.append(f"Corp-Jobs #{_cjid}: "
                                  f"{type(e).__name__}: {e}")
    try:
        vergeben = store.job_zuordnung_alle() or {}
    except Exception as e:
        vergeben = {}
        job_fehler.append(f"job_zuordnung: {type(e).__name__}: {e}")

    # Nur Jobs, die MATERIAL AUS DEM HANGAR fressen: Fertigung (1) und
    # Reaktion (9/11). Forschung/Kopieren/Invention nehmen Datacores bzw.
    # nichts aus diesem Stapel.
    _herstellend = (1, 9, 11)
    ohne_plan = [j for j in jobs
                 if int(j.get("activity_id") or 0) in _herstellend
                 and str(vergeben.get(int(j.get("job_id") or 0), "")) in ("", "-")]
    namen.update(_namen({int(j.get("product_type_id") or 0) for j in ohne_plan}))
    p("=" * 78)
    p("ESI-JOBS, DIE KEINEM PLAN GEHÖREN")
    p("=" * 78)
    for f in job_fehler:
        p(f"  ABRUF FEHLGESCHLAGEN {f}")
    p(f"  Industrie-Jobs von ESI: {len(jobs)} ·"
      f" davon Fertigung/Reaktion ohne Plan: {len(ohne_plan)}")
    p("  (ESI liefert nur die letzten Wochen - ältere Jobs sind nicht mehr")
    p("   abrufbar, ihr Verbrauch kann hier also fehlen.)")
    p("")
    _summe_jobs = {}
    for j in sorted(ohne_plan, key=lambda x: str(x.get("start_date"))):
        t = int(j.get("product_type_id") or 0)
        r = int(j.get("runs") or 0)
        _summe_jobs[t] = _summe_jobs.get(t, 0) + r
        _marke = "zu keinem Plan (deine Antwort)" \
            if str(vergeben.get(int(j.get("job_id") or 0), "")) == "-" else ""
        p(f"      Job {j.get('job_id')}  {str(namen.get(t, t))[:26]:<26} "
          f"{_z(r):>6} Runs  {str(j.get('status'))[:9]:<9} "
          f"{str(j.get('start_date'))[:16]}  {j.get('_char')}  {_marke}")
    if not ohne_plan:
        p("      (keiner - dann hat kein unbekannter Job Material genommen)")
    p("")

    # Was diese Jobs an den FEHLENDEN Materialien verbraucht haben. Mengen
    # OHNE ME-Bonus = Obergrenze ("bis zu"), wie `mw_helpers.lag_verbrauch`:
    # die ME der fremden Blaupause kennt das Werkzeug nicht.
    if fehl_items and ohne_plan:
        try:
            rec = industry.recipes_cached()
        except Exception as e:
            rec = None
            p(f"  Rezepte nicht lesbar: {type(e).__name__}: {e}")
        verbrauch = {}
        if rec is not None:
            for j in ohne_plan:
                bp = j.get("blueprint_type_id")
                akt = int(j.get("activity_id") or 0)
                mats = rec.bp_materials.get((bp, akt))
                if not mats:
                    _pb = rec.product_to_bp.get(
                        int(j.get("product_type_id") or 0))
                    if _pb:
                        mats = rec.bp_materials.get((_pb[0], _pb[1]))
                for m, q in mats or []:
                    if int(m) not in fehl_items:
                        continue
                    verbrauch.setdefault(int(m), []).append(
                        (int(j.get("job_id") or 0),
                         int(j.get("product_type_id") or 0),
                         int(q or 0) * int(j.get("runs") or 0)))
        p("  WAS DIESE JOBS AN DEN FEHLENDEN MATERIALIEN GENOMMEN HABEN")
        p("  (Obergrenze - ohne ME-Bonus der fremden Blaupause gerechnet)")
        for t, (noetig, da_ein, fehlt) in sorted(
                fehl_items.items(), key=lambda x: str(namen.get(x[0], x[0])).lower()):
            _l = verbrauch.get(t) or []
            _s = sum(x[2] for x in _l)
            p(f"      {str(namen.get(t, t))[:40]:<40} fehlt {_z(fehlt):>10}"
              f" · diese Jobs: bis zu {_z(_s)}")
            for jid, prod, menge in sorted(_l, key=lambda x: -x[2])[:8]:
                p(f"          Job {jid}  für {str(namen.get(prod, prod))[:26]:<26}"
                  f" {_z(menge):>10}")
        p("")

    # Abgeschlossene Plaene, die DASSELBE Material brauchten: sie zaehlen im
    # Bedarf nicht mehr (zu Recht - sie bauen nichts mehr), haben aber vom
    # selben Stapel genommen.
    if fehl_items:
        p("=" * 78)
        p("ABGESCHLOSSENE PLÄNE, DIE DASSELBE MATERIAL BRAUCHTEN")
        p("=" * 78)
        p("  Sie zählen im Bedarf oben NICHT mehr (sie bauen nichts mehr),")
        p("  haben aber aus demselben Hangar genommen.")
        p("")
        p(f"  Abgeschlossen in den Einstellungen:"
          f" {sum(1 for x in alle if x.get('done_manual'))} ·"
          f" im Archiv (seit 30+ Tagen fertig): {len(archiv)}")
        p("")
        _treffer = False
        for x in list(alle) + list(archiv):
            if not x.get("done_manual"):
                continue
            snap = _unpack(((x.get("frozen") or {}).get("plan_snapshot")) or {})
            if not snap:
                continue
            _r = {int(a): int(b or 0)
                  for a, b in (snap.get("build_runs") or {}).items()}
            _m = {int(a): b for a, b in (snap.get("build_mats") or {}).items()}
            _, _voll = _restbedarf(_r, _m, {})
            _hit = {k: v for k, v in _voll.items() if k in fehl_items and v > 0}
            if not _hit:
                continue
            _treffer = True
            p(f"  {x.get('label') or x.get('item_name') or x.get('id')}"
              f"   (abgeschlossen {_zeit(x.get('done_ts'))}"
              + (" · ARCHIV" if x.get("archiviert_ts") else "") + ")")
            for k, v in sorted(_hit.items(),
                               key=lambda y: str(namen.get(y[0], y[0])).lower()):
                p(f"      {str(namen.get(k, k))[:40]:<40} {_z(v):>12}")
        if not _treffer:
            p("  (keiner - dann kommt die Lücke nicht von dort)")
        p("")

    p("=" * 78)
    p("LESEHILFE")
    p("=" * 78)
    p("1. Steht bei einem Plan „KEINE GEBAUTEN RUNS ERKANNT\", kennt das")
    p("   Werkzeug für ihn keinen Fortschritt: weder ein zugeordneter")
    p("   ESI-Job noch ein Hand-Haken. Dann verlangt er das Material noch")
    p("   einmal in voller Höhe - obwohl du längst gebaut hast. Abhilfe:")
    p("   Bauplan öffnen -> Runplaner -> „Job assignments\" und die Jobs")
    p("   dem Plan zuordnen (oder die gebauten Zeilen abhaken).")
    p("2. Steht unter JOBS eine Zahl, aber unter OFFEN noch viel, hat das")
    p("   Werkzeug nur einen Teil der Jobs zugeordnet (ESI behält Jobs nur")
    p("   begrenzt; ältere Jobs sind nicht mehr abrufbar).")
    p("3. Liegt Material an einem ABGESCHALTETEN Ort, senkt es den")
    p("   Fehlbetrag NICHT (deine Entscheidung: von dort nimmst du nichts).")
    p("4. „Voller Bedarf\" ist, was der Plan von Anfang an brauchte;")
    p("   „offener Bedarf\" ist, was nach den erkannten Runs übrig ist.")
    p("   Weichen sie weit auseinander, liegt die Antwort in Punkt 1/2.")
    p("5. Geht die Bedarfsseite auf (voller minus gebauter Bedarf passt zum")
    p("   Rezept) und fehlt trotzdem etwas, hat es jemand anders verbraucht.")
    p("   Die drei Kandidaten stehen in den Abschnitten darüber: ESI-Jobs")
    p("   ohne Plan, deren Materialverbrauch, und abgeschlossene Pläne.")
    p("6. Bleibt danach ein Rest übrig, ist er im Spiel verloren gegangen")
    p("   (Fehlklick, zu viel verbraucht, anderweitig benutzt). Dafür ist")
    p("   der Knopf „Copy shopping list\" auf der Stock-locations-Seite da:")
    p("   er kauft genau die Fehlbeträge nach, ohne neue Bauschleifen.")
    p("")
    p("ENDE")
    _schreib(aus)
    return 0


if __name__ == "__main__":
    sys.exit(main())
