"""EIN Lauf, der ALLES mitbringt, was eine Ferndiagnose braucht.

NUTZER 24.10.2026: "Und falls du bessere wege kennst als so wie wir
gerade arbeiten dann sag sie mir!"

DAS PROBLEM MIT DEM BISHERIGEN WEG: jede Frage kostete einen eigenen
Lauf auf seinem Rechner - Corp-Hangar vergessen, laufende Jobs
vergessen, Abschnitt nachgeruestet, nochmal, nochmal. Die Daten liegen
alle auf seinem PC (ESI, ledger.db 535 MB, industry.db), die Rechnung
findet woanders statt.

WAS DIESES WERKZEUG MACHT: es holt die Daten EINMAL und legt sie als
eine Datei ab (`berichte/diagnose_export.json`). Die ist klein genug zum
Verschicken, und damit laesst sich jede weitere Frage beantworten, ohne
dass er noch einmal etwas anklicken muss.

DRIN IST (alles NUR LESEND):
  * hangar      {type_id: Menge} - Charaktere UND Corp, derselbe
                Bestandsbegriff wie im Bauplan
  * laufend     {type_id: Runs} - was gerade in der Bauschleife steht
                (active/paused/ready, Charaktere und Corp)
  * jobs        die laufenden Jobs einzeln (Typ, Runs, Status, Ende)
  * zuordnung   die Job-Zuordnung je gespeichertem Plan
  * abruf       wann ESI den Bestand zuletzt vollstaendig gesehen hat
  * kaeufe      je type_id die gekaufte Menge seit `--seit` (Vorgabe:
                60 Tage), aus dem Handelsjournal
  * namen       Klartextnamen zu allen vorkommenden type_ids
  * umgebung    Fassung, Zeit, use_corp, Divisions

NICHT DRIN: Preise, ISK-Betraege, Charakternamen, Token. Es geht um
Mengen - alles andere waere Beifang.

AUFRUF:
    python werkzeuge\\exportiere_diagnose.py
    python werkzeuge\\exportiere_diagnose.py --seit 2026-09-01
"""
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import config, store                      # noqa: E402

FASSUNG = 1
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIEL = os.path.join(WURZEL, "berichte", "diagnose_export.json")


def _settings_rohe():
    try:
        with open(config.settings_path(), "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return config.load_settings()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seit", default=None,
                    help="Kaeufe ab diesem Datum (JJJJ-MM-TT), "
                         "Vorgabe: vor 60 Tagen")
    args = ap.parse_args()
    seit = args.seit or time.strftime("%Y-%m-%d",
                                      time.localtime(time.time() - 60 * 86400))

    aus = {"fassung": FASSUNG, "erstellt": time.strftime("%Y-%m-%d %H:%M:%S"),
           "seit": seit, "fehler": []}
    s = _settings_rohe()
    aus["use_corp"] = bool(s.get("use_corp"))
    aus["corp_divisions"] = s.get("corp_divisions")

    def meckern(was, e):
        aus["fehler"].append(f"{was}: {type(e).__name__}: {e}")
        print(f"  ! {was}: {type(e).__name__}: {e}")

    print("Diagnose-Export")
    # ---- Bestand: Charaktere ------------------------------------------
    hangar, laufend, jobs, verteilung = {}, {}, [], {}
    try:
        from eve_trader import esi, lagerorte, corp as _corp
        cid = s.get("client_id") or config.EMBEDDED_CLIENT_ID
        ctypes = esi.container_type_ids_safe()
        chars = store.list_characters() or []
        print(f"  Charaktere: {len(chars)}")
        for ch in chars:
            c = int(ch["character_id"])
            nm = ch.get("character_name") or str(c)
            try:
                a = esi._fetch_all_assets(cid, c)
                for zl in lagerorte.zeilen_aus_assets(a, ctypes, nm, "char"):
                    hangar[int(zl["tid"])] = (hangar.get(int(zl["tid"]), 0)
                                              + int(zl.get("menge") or 0))
                    # JE BESITZER UND ORT (Nutzerfall 24.10.2026): MoMa
                    # zaehlt alle Charaktere als EINEN Topf (so gewollt),
                    # ein EVE-Job sieht aber nur den Hangar SEINES
                    # Charakters. Gemessen: Ceramic Powder 26'150 im Topf,
                    # 3'750 dort, wo der Job laufen soll. Ohne diese
                    # Aufteilung ist der Unterschied nicht nachweisbar.
                    _k = f"{nm}|{zl.get('ort')}"
                    verteilung.setdefault(str(int(zl["tid"])), {})
                    verteilung[str(int(zl["tid"]))][_k] = (
                        verteilung[str(int(zl["tid"]))].get(_k, 0)
                        + int(zl.get("menge") or 0))
            except Exception as e:
                meckern(f"Assets {nm}", e)
            try:
                for j in (esi.fetch_active_jobs(cid, c) or []):
                    _pt = j.get("product_type_id")
                    if not _pt:
                        continue
                    laufend[int(_pt)] = (laufend.get(int(_pt), 0)
                                         + int(j.get("runs") or 0))
                    jobs.append({"tid": int(_pt), "runs": int(j.get("runs") or 0),
                                 "status": j.get("status"),
                                 "aktivitaet": j.get("activity_id"),
                                 "ende": j.get("end_date"), "quelle": "char"})
            except Exception as e:
                meckern(f"Jobs {nm}", e)
        # ---- Bestand und Jobs: Corp (EIN Abruf je Corporation) --------
        if s.get("use_corp"):
            div = _corp.divisions_bereinigt(s.get("corp_divisions"))
            fertig = set()
            for ch in chars:
                c = int(ch["character_id"])
                try:
                    corp_id = esi.fetch_character_corporation(c)
                except Exception:
                    continue
                if not corp_id or int(corp_id) in fertig:
                    continue
                try:
                    ca = esi.fetch_corporation_assets(cid, c, int(corp_id))
                except Exception:
                    continue          # keine Rolle - naechster Charakter
                fertig.add(int(corp_id))
                summe, _je = _corp.corp_bestand(ca, div, None, ctypes)
                for t, q in (summe or {}).items():
                    hangar[int(t)] = hangar.get(int(t), 0) + int(q or 0)
                    verteilung.setdefault(str(int(t)), {})
                    verteilung[str(int(t))]["CORP"] = (
                        verteilung[str(int(t))].get("CORP", 0) + int(q or 0))
                try:
                    for j in (esi.fetch_corporation_jobs(cid, c,
                                                         int(corp_id)) or []):
                        _pt = j.get("product_type_id")
                        if not _pt:
                            continue
                        laufend[int(_pt)] = (laufend.get(int(_pt), 0)
                                             + int(j.get("runs") or 0))
                        jobs.append({"tid": int(_pt),
                                     "runs": int(j.get("runs") or 0),
                                     "status": j.get("status"),
                                     "aktivitaet": j.get("activity_id"),
                                     "ende": j.get("end_date"),
                                     "quelle": "corp"})
                except Exception as e:
                    meckern("Corp-Jobs", e)
            print(f"  Corporations abgerufen: {len(fertig)}")
    except Exception as e:
        meckern("ESI", e)
    aus["hangar"] = {str(k): int(v) for k, v in hangar.items()}
    aus["laufend"] = {str(k): int(v) for k, v in laufend.items()}
    aus["jobs"] = jobs
    aus["verteilung"] = verteilung
    print(f"  Hangar: {len(hangar)} Materialien, {sum(hangar.values()):,} Stueck")
    print(f"  Bauschleife: {len(laufend)} Erzeugnisse, {len(jobs)} Jobs")

    # ---- Wann hat ESI den Bestand zuletzt gesehen ---------------------
    try:
        aus["abruf"] = (store.asset_snapshot_info() or {})
    except Exception as e:
        meckern("asset_snapshot_info", e)
        aus["abruf"] = {}

    # ---- Job-Zuordnung je Plan ----------------------------------------
    zu = {}
    try:
        for pl in (s.get("bau_saved_plans") or []):
            pid = pl.get("id")
            if pid is None:
                continue
            d = store.job_zuordnung_fuer_plan(pid) or {}
            if d:
                zu[str(pid)] = {str(k): {"type_id": v.get("type_id"),
                                         "runs": v.get("runs"),
                                         "ts": v.get("ts")}
                                for k, v in d.items()}
    except Exception as e:
        meckern("Job-Zuordnung", e)
    aus["zuordnung"] = zu
    print(f"  Job-Zuordnung: {len(zu)} Plaene")

    # ---- Kaeufe aus dem Handelsjournal --------------------------------
    kauf = {}
    try:
        for r in (store.get_transactions(cid="all", since=seit,
                                         is_buy=True) or []):
            t = int(r["type_id"])
            kauf[t] = kauf.get(t, 0) + int(r["quantity"] or 0)
    except Exception as e:
        meckern("Handelsjournal", e)
    aus["kaeufe"] = {str(k): int(v) for k, v in kauf.items()}
    print(f"  Kaeufe seit {seit}: {len(kauf)} Posten")

    # ---- Namen ---------------------------------------------------------
    ids = set(hangar) | set(laufend) | set(kauf)
    for pl in (s.get("bau_saved_plans") or []):
        snap = ((pl.get("frozen") or {}).get("plan_snapshot")) or {}
        for schl in ("build_runs", "buy", "stock_used", "build_made"):
            for k in (snap.get(schl) or {}):
                try:
                    ids.add(int(k))
                except (TypeError, ValueError):
                    continue
        for lst in (snap.get("build_mats") or {}).values():
            for m, _q in (lst or []):
                try:
                    ids.add(int(m))
                except (TypeError, ValueError):
                    continue
    try:
        aus["namen"] = {str(k): v for k, v in
                        (store.cached_names(sorted(ids)) or {}).items()}
    except Exception as e:
        meckern("Namen", e)
        aus["namen"] = {}
    print(f"  Namen: {len(aus['namen'])} von {len(ids)} type_ids")

    os.makedirs(os.path.dirname(ZIEL), exist_ok=True)
    with open(ZIEL, "w", encoding="utf-8") as fh:
        json.dump(aus, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"\nFertig: {ZIEL} ({os.path.getsize(ZIEL):,} Bytes)")
    if aus["fehler"]:
        print(f"Mit {len(aus['fehler'])} Problemen - sie stehen in der Datei.")


if __name__ == "__main__":
    main()
