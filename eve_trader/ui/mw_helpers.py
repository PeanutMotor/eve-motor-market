"""Pure/statische Helfer der MainWindow - als Mixin ausgelagert
(Sitzung 7, Nutzer: "jetzt wird aufgeraeumt" / main_window.py zerlegen).

REGELN FUER DIESES MODUL:
* Nur Methoden OHNE Qt-Widget-Bau und ohne Dialog-Zustand - alles, was
  sich mit einfachen Eingaben pur testen laesst (die aa-Suite tut genau
  das). Wer hier etwas ergaenzt: zuerst pruefen, ob es wirklich ohne
  `self`-Widget auskommt.
* Verhalten identisch zur alten Inline-Fassung - die Methodenrümpfe sind
  UNVERAENDERT hierher verschoben (nur `MainWindow.`-Selbstbezuege heissen
  jetzt `MainWindowHelpers.`, sonst gaebe es einen Zirkel-Import).
* Die Tests lesen den Quelltext beider Dateien zusammengehaengt
  (`_src_txt` in test_bestand_herkunft.py) - Text-/AST-Pruefungen sehen
  also weiterhin ALLES.
"""


class MainWindowHelpers:
    @staticmethod
    def _bp_copies_by_tid(owned_bp, build_runs, product_to_bp):
        """{type_id: PHYSISCH besessene Blaupausen-Stueck} fuer die Items,
        die der Plan BAUT - die Obergrenze fuer gleichzeitige Jobs.

        NUTZER-VORFALL (Falcon, Sitzung 7): 1 eigene Blackbird-BPO, der
        Runplaner verteilte trotzdem 3+3 Blueprints auf zwei Charaktere.
        Der Blueprints-Tab wusste "Besitze 1" - er liest aber
        `_bd_bp_owned_counts`, waehrend der Runplaner aus
        `_bd_stage_bp_esi` speiste: ZWEI Ableitungen derselben Tatsache
        (Regel 9). Die zweite entsteht nur beim Stufen-Ladelauf und kennt
        deshalb kein Item, das der Plan ERST SPAETER zu bauen beschliesst
        (Kauf -> Bau nach Mengen-/Preisaenderung) - fuer solche Items fiel
        der Runplaner auf die pauschale Stufen-Zahl zurueck und nahm
        beliebig viele Kopien an.

        BPO wie BPC zaehlen gleich: eine BPO erlaubt unbegrenzt RUNS, aber
        pro Stueck immer nur EINEN gleichzeitigen Job. Items ohne eigene
        Blaupause bekommen bewusst KEINEN Eintrag - fuer die gilt weiter
        die pauschale Annahme "kaufst/kopierst du eben", statt den Plan zu
        blockieren."""
        _runs = build_runs or {}
        _p2b = product_to_bp or {}
        by_bp = {}
        for b in (owned_bp or []):
            _bid = b.get("type_id")
            if _bid is None:
                continue
            by_bp[_bid] = by_bp.get(_bid, 0) + int(b.get("quantity", 1) or 1)
        out = {}
        for t, r in _runs.items():
            try:
                if int(r) < 1:
                    continue
            except (TypeError, ValueError):
                continue
            _bp = _p2b.get(t)
            if not _bp:
                continue
            _n = by_bp.get(_bp[0])
            if _n:
                out[t] = int(_n)
        return out

    @staticmethod
    def _bpc_runs_by_tid(owned_bp, build_runs, product_to_bp):
        """{type_id: Runs der KLEINSTEN eigenen BPC} fuer Items, die der Plan
        baut und von denen NUR Kopien (keine BPO) im ESI-Cache liegen. Eine
        BPC hat nur so viele Runs - mehr passen nicht in EINEN Job. Die
        kleinste Kopie zaehlt (Regel 3: lieber ein Job zu viel als einer,
        der im Spiel nicht startet). Liegt eine BPO dabei, gibt es KEINEN
        Eintrag (unbegrenzt)."""
        _runs = build_runs or {}
        _p2b = product_to_bp or {}
        bpo = set()
        min_runs = {}
        for b in (owned_bp or []):
            _bid = b.get("type_id")
            if _bid is None:
                continue
            if b.get("is_bpo"):
                bpo.add(_bid)
                continue
            try:
                _r = int(b.get("runs", 0) or 0)
            except (TypeError, ValueError):
                _r = 0
            if _r >= 1:
                min_runs[_bid] = min(min_runs.get(_bid, _r), _r)
        out = {}
        for t, r in _runs.items():
            try:
                if int(r) < 1:
                    continue
            except (TypeError, ValueError):
                continue
            _bp = _p2b.get(t)
            if not _bp or _bp[0] in bpo:
                continue
            _m = min_runs.get(_bp[0])
            if _m:
                out[t] = int(_m)
        return out

    @staticmethod
    def _bp_teile(R, njobs, max_runs=None, parts=None):
        """Aufteilung einer Runplaner-Zeile in Blaupausen-Jobs: (njobs, Teile).
        Ohne Deckel wie bisher gleichmaessig ueber die geplanten Jobs (divmod).
        Mit `max_runs` (Runs je BPC / maxProductionLimit) GANZE Kopien
        (Nutzer 19.09.2026: "moeglichst alle Blueprints am Ende verbraucht
        haben, nicht dass Blueprints mit angefangenen Runs stehen bleiben"):
        `parts` = die Jobs, wie schedule_build sie gelegt hat, solange ihre
        Summe noch zur Zeile passt; sonst (nach ESI-Fortschritt, R kleiner)
        neu: volle Kopien, der Rest als letzter Job (23 -> 10 + 10 + 3)."""
        R = max(0, int(R or 0))
        try:
            m = int(max_runs or 0)
        except (TypeError, ValueError):
            m = 0
        if R < 1:
            return 1, [0]
        try:
            _p = [int(x) for x in (parts or ()) if int(x) >= 1]
        except (TypeError, ValueError):
            _p = []
        if _p and sum(_p) == R and (m < 1 or max(_p) <= m):
            return len(_p), sorted(_p, reverse=True)
        if m >= 1:
            parts = [m] * (R // m) + ([R % m] if R % m else [])
            return len(parts), parts
        try:
            njobs = max(1, int(njobs or 1))
        except (TypeError, ValueError):
            njobs = 1
        njobs = max(1, min(njobs, R))
        base, extra = divmod(R, njobs)
        return njobs, [base + 1] * extra + [base] * (njobs - extra)

    def _bd_enden(self, type_id, recipes=None):
        """Die Endprodukt-MENGE des offenen Plans (Multi-Bauplan 1.0.9):
        {type_id} - beim Buendel seine Enden aus den Rezepten (Aufrufer-
        Rezepte, sonst self._bd_recipes). Ein Buendel ohne Rezepte kennt
        keine Enden -> leere Menge, nie das Buendel selbst."""
        from .. import industry as _ind
        _rec = recipes if recipes is not None else getattr(self, "_bd_recipes", None)
        if type_id == _ind.BUENDEL_ID and _rec is None:
            return set()
        return _ind.enden_von(type_id, _rec)

    def _run_klick_merken(self, tid, runs, reaktion):
        """Klick auf einen Run-Knopf festhalten (Stufe B, 21.09.2026).

        DER KLICK IST KEIN FORTSCHRITT. Er sagt nur: "diese Zeile, dieser
        Plan, jetzt". Wirksam wird er erst, wenn ESI danach einen passenden
        Job meldet (`job_zuordnen`) - ein Fehlklick bleibt folgenlos, und
        wer die Zahl lieber abtippt, verliert nichts: dann greift wie bisher
        die Reihenfolge Signatur -> Reservierung -> im Zweifel nichts.

        Nur fuer GESPEICHERTE Plaene: ohne Plan-ID gibt es niemanden, dem
        ein Job gehoeren koennte.
        """
        _pid = getattr(self, "_bd_open_plan_id", None)
        if _pid is None:
            return
        try:
            from .. import store as _st
            _st.run_klick_merken(_pid, int(tid), int(runs), bool(reaktion))
        except Exception as _e:
            # Ein nicht gemerkter Klick kostet nur Genauigkeit, nie Material.
            self._log_exception("Run-Klick merken", str(_e))

    def _runplan_klick_bei_kopie(self, items):
        """JEDE Namens-Kopie einer Runplaner-Zeile merkt die Zuordnung mit
        (emm402, Nutzer: "Alle Wege merken mit" - wer den Namen per
        Rechtsklick/Strg+C/Blueprint-Knopf kopiert und die Runs abtippt,
        verlor sonst die Job-Zuordnung bei geteilten Items). Dieselbe
        Wirkung wie der amber Runs-Knopf: ohne spaeteren passenden
        ESI-Job bleibt der Klick folgenlos."""
        from PySide6.QtCore import Qt as _Qt
        for _it in items or []:
            try:
                for _t, _r, _rk in (_it.data(0, _Qt.UserRole + 9) or []):
                    if _t and _r:
                        self._run_klick_merken(int(_t), int(_r), bool(_rk))
            except Exception:
                pass    # Komfortweg - nie kritisch

    def _job_zuordnung_nachfuehren(self, assignments, seit_ts=None):
        """Neue ESI-Jobs den Klicks dieses Plans zuordnen und das MERKEN.

        Laeuft bei jedem Runplaner-Aufbau. Neu ist daran nur eines: die
        Entscheidung wird gespeichert statt jedes Mal neu getroffen. Schon
        vergebene Jobs bleiben unangetastet - auch die anderer Plaene.

        ZWEI QUELLEN, in dieser Reihenfolge (Stufe C, 24.09.2026):
          1. der KLICK (`job_zuordnen`) - der staerkere Beleg, er gilt auch
             bei umstrittenem Item;
          2. die EINDEUTIGKEIT (`job_zuordnen_eindeutig`) - kein anderer
             gespeicherter Plan will dieses Item, also kann der Job nur von
             hier stammen. Erst was zuerst geschrieben wird, gilt; die
             Klick-Zuordnung laeuft deshalb vorher.
        """
        _pid = getattr(self, "_bd_open_plan_id", None)
        if _pid is None:
            return
        from .. import store as _st
        _jobs = []
        for _j in (getattr(self, "_bd_delivered_jobs", None) or []):
            _ts = MainWindowHelpers._iso_job_ts(_j.get("start_date"))
            _fts = MainWindowHelpers._iso_job_ts(_j.get("completed_date"))
            if _j.get("job_id") is None or _ts is None:
                continue          # Alt-Daten ohne job_id: nichts zu merken
            _jobs.append({"job_id": _j.get("job_id"),
                          "product_type_id": _j.get("product_type_id"),
                          "runs": _j.get("runs"),
                          "activity_id": _j.get("activity_id"),
                          "start_ts": _ts,
                          "fertig_ts": _fts})
        # LAUFENDE JOBS GLEICH BEIM START ZUORDNEN (Nutzer 28.09.2026: "wenn
        # ich Plan 1 Intermediates gebaut habe und die Composites starte,
        # dann mit Plan 2 die Intermediates beginne - geht das mit der
        # Bestandsreservierung?" -> "ja genau so"). Das Material eines
        # gestarteten Jobs ist im Spiel weg; bisher hielt Plan 1 seinen
        # Anspruch darauf, bis der Job ABGELIEFERT war, und die frischen
        # Intermediates von Plan 2 galten so lange als Plan 1s. Mit der
        # Zuordnung gibt `_reserve_map_mitlaufend` (ueber `_belegt_fuer_plan`)
        # die Zutaten ab dem naechsten Bestandsabruf frei. Als "fertig" gilt
        # hier der START - er muss nach dem Einfrieren liegen. Fortschritt
        # zaehlt weiter NUR, was abgeliefert ist (`_belegt_s` liest die
        # gelieferten Jobs). SEIT 28.09.2026 (Nutzer "ja, wenn das eine gute
        # Loesung ist ... wir brauchen etwas, was fix haelt"): auch LAUFENDE
        # Jobs gehen durch Prioritaet und Frage - dann ist ein Job ab dem
        # Start zugeordnet, nicht erst beim Abliefern.
        _laufend = []
        _schon_da = {int(_j["job_id"]) for _j in _jobs}
        _roh = getattr(self, "_bd_active_jobs_alle", None)
        if _roh is None:
            _roh = getattr(self, "_bd_active_jobs_map", None) or {}
        for _lj in [_x for _xs in (_roh or {}).values()
                    for _x in (_xs or [])]:
            _ts = MainWindowHelpers._iso_job_ts(_lj.get("start_date"))
            if _lj.get("job_id") is None or _ts is None:
                continue
            if int(_lj["job_id"]) in _schon_da:
                continue
            _laufend.append({"job_id": _lj.get("job_id"),
                             "product_type_id": _lj.get("product_type_id"),
                             "runs": _lj.get("runs"),
                             "activity_id": _lj.get("activity_id"),
                             "start_ts": _ts,
                             "fertig_ts": _ts,
                             "laeuft": True})
        _jobs = _jobs + _laufend
        if not _jobs:
            return
        _plan_runs = {}
        _is_react = {}
        for _a in (assignments or []):
            try:
                _t = int(_a["tid"])
            except (KeyError, TypeError, ValueError):
                continue
            _plan_runs[_t] = _plan_runs.get(_t, 0) + int(_a.get("runs") or 0)
            # EINE Wahrheit fuer "ist das eine Reaktion", s. stufe_ist_reaktion.
            _is_react[_t] = stufe_ist_reaktion(_a.get("stage"))
        import time as _time_jz
        _klicks = _st.run_klicks_fuer_plan(
            _pid, aelter_als=_time_jz.time() - KLICK_FENSTER_SEK)
        _neu = job_zuordnen(_jobs, _klicks, _st.job_zuordnung_alle(),
                            _pid, _plan_runs,
                            fremde_klicks=_st.run_klicks_andere(
                                _pid, aelter_als=_time_jz.time() - KLICK_FENSTER_SEK))
        for _jid, (_t, _r) in _neu.items():
            _st.job_zuordnung_setzen(_jid, _pid, _t, _r, "klick")
        if seit_ts is None:
            return
        _um_seit = self._umstrittene_seit(getattr(self, "settings", None), _pid)
        _eind = job_zuordnen_eindeutig(
            _jobs, _plan_runs, _is_react, _st.job_zuordnung_alle(),
            self._umstrittene_items(getattr(self, "settings", None), _pid),
            seit_ts, umstritten_seit=_um_seit)
        for _jid, (_t, _r) in _eind.items():
            _st.job_zuordnung_setzen(_jid, _pid, _t, _r, "eindeutig")
        # BAU-PRIORITAET (Kartenreihenfolge): was jetzt noch niemandem
        # gehoert, verteilt die Rangfolge - gespeichert, s. dort.
        try:
            self._prio_zuordnung_schreiben(_jobs)
        except Exception as _pe:
            self._log_exception("Bau-Prioritaet: Jobs", str(_pe))
        # WAS DANACH NOCH OFFEN IST, wird EINMAL gefragt (Stufe C, Teil 2).
        # Hier wird nur GESAMMELT - gefragt wird ueber die Zeile im
        # Runplaner, nie von selbst. `_bd_job_offen` ist transient wie
        # `_bd_runplan_auto`: es entsteht bei jedem Aufbau neu.
        self._bd_job_offen = [
            dict(_f, kandidaten=self._job_plan_kandidaten(_f["type_id"]))
            for _f in offene_job_fragen(
                _jobs, _plan_runs, _is_react, _st.job_zuordnung_alle(),
                self._umstrittene_items(getattr(self, "settings", None), _pid),
                seit_ts, umstritten_seit=_um_seit)]
        try:
            self._bd_job_prio = self._prio_zur_pruefung(_plan_runs)
        except Exception as _pp:
            self._bd_job_prio = []
            self._log_exception("Bau-Prioritaet: Pruefliste", str(_pp))

    def _aktive_jobs_filtern(self):
        """Laufende Jobs NUR fuer den Plan, dem sie gehoeren (Nutzer
        28.09.2026, gemessen mit werkzeuge/szenario_prioritaet.py: lief ein
        Job von Plan A, zeigten auch B und C seine Runs als erledigt - der
        Runplaner zaehlte `_bd_active_jobs_map` ungeteilt fuer JEDEN Plan).

        Quelle ist `job_zuordnung` - dieselbe wie bei abgelieferten Jobs:
          * zugeordnet zu DIESEM Plan -> `_bd_active_jobs_map` (zaehlt),
          * zugeordnet zu einem ANDEREN Plan -> nirgends,
          * noch NIEMANDEM zugeordnet (und nach dem Einfrieren gestartet) ->
            `_bd_active_unzugeordnet`: zaehlt NICHT als erledigt, die Zeile
            sagt "laeuft, noch keinem Plan zugeordnet" (Regel 3 - lieber
            eine offene Zeile als Material, das doppelt abgebucht wird).
        Ungespeicherter Plan (keine Plan-Id): wie bisher alles, er kann
        keine Zuordnung haben. Die Rohliste bleibt in `_bd_active_jobs_alle`
        (die Zuordnung selbst braucht ALLE Jobs)."""
        from .. import store as _st
        alle = getattr(self, "_bd_active_jobs_alle", None)
        if alle is None:
            alle = dict(getattr(self, "_bd_active_jobs_map", None) or {})
            self._bd_active_jobs_alle = alle
        pid = getattr(self, "_bd_open_plan_id", None)
        if pid is None:
            self._bd_active_jobs_map = dict(alle)
            self._bd_active_unzugeordnet = {}
            return
        zu = _st.job_zuordnung_fuer_plan(pid) or {}
        verg = _st.job_zuordnung_alle() or {}
        seit = None
        for _p in ((getattr(self, "settings", None) or {}).get("bau_saved_plans") or []):
            if str(_p.get("id")) == str(pid):
                seit = (_p.get("frozen") or {}).get("ts")
                break
        mein, offen = {}, {}
        for _t, _js in (alle or {}).items():
            for _j in (_js or []):
                try:
                    _jid = int(_j.get("job_id"))
                except (TypeError, ValueError):
                    continue          # ohne job_id kein Beleg - zaehlt nicht
                if _jid in zu:
                    mein.setdefault(_t, []).append(_j)
                elif _jid not in verg:
                    _st_ts = MainWindowHelpers._iso_job_ts(_j.get("start_date"))
                    if seit is None or (_st_ts is not None and _st_ts >= float(seit)):
                        offen.setdefault(_t, []).append(_j)
        self._bd_active_jobs_map = mein
        self._bd_active_unzugeordnet = offen

    def _prio_zuordnung_schreiben(self, jobs_geliefert):
        """Noch niemandem gehoerende gelieferte Jobs nach BAU-PRIORITAET
        (Kartenreihenfolge, Nutzer 28.09.2026) verteilen und SPEICHERN
        (Quelle "prioritaet"). Gespeichert, weil Umsortieren sonst schon
        gebaute Jobs rueckwirkend verschob; der Nutzer bestaetigt oder
        haengt sie im Frage-Dialog um (dann "nutzer").

        Gerechnet ueber ALLE offenen, eingefrorenen Plaene mit Rang, damit
        #1 zuerst satt wird (`prio_jobs_zuteilen`, rein). `jobs_geliefert`
        im Format von `_job_zuordnung_nachfuehren` (fertig_ts). Rueckgabe:
        {job_id: plan_id} der neu geschriebenen."""
        from .. import store as _st
        _s = getattr(self, "settings", None) or {}
        _rang = MainWindowHelpers.plan_rang(_s)
        _jobs = [dict(_j, _ts=_j.get("fertig_ts")) for _j in (jobs_geliefert or [])
                 if _j.get("fertig_ts") is not None and _j.get("job_id") is not None]
        if not _rang or not _jobs:
            return {}
        _nach_id = {str(p.get("id")): p for p in (_s.get("bau_saved_plans") or [])}
        _plaene = []
        for _pid_s, _r in sorted(_rang.items(), key=lambda kv: kv[1]):
            _p = _nach_id.get(_pid_s) or {}
            _frz = _p.get("frozen") or {}
            _snap = _frz.get("plan_snapshot")
            if not _snap or not _frz.get("ts"):
                continue
            _seit = float(_frz["ts"])
            _runs = MainWindowHelpers._plan_snapshot_unpack(_snap).get("build_runs") or {}
            _bel = {}
            _zu = _st.job_zuordnung_fuer_plan(_p.get("id")) or {}
            for _jid_z, _e in _zu.items():
                try:
                    _t = int(_e.get("type_id") or 0)
                    _bel[_t] = _bel.get(_t, 0) + int(_e.get("runs") or 0)
                except (TypeError, ValueError):
                    continue
            _plaene.append({"id": _p.get("id"), "runs": _runs, "seit": _seit,
                            "belegt": _bel})
        _rp = set(getattr(getattr(self, "_bd_recipes", None),
                          "reaction_products", None) or ())
        _, _verteilt = prio_jobs_zuteilen(
            _jobs, _plaene, _st.job_zuordnung_alle().keys(),
            lambda _t: int(_t) in _rp)
        _nach_job = {int(_j["job_id"]): _j for _j in _jobs}
        _neu = {}
        for _jid, _pid in _verteilt.items():
            _j = _nach_job.get(int(_jid)) or {}
            if _st.job_zuordnung_setzen(int(_jid), _pid, _j.get("product_type_id"),
                                        _j.get("runs"), "prioritaet"):
                _neu[int(_jid)] = _pid
        return _neu

    def _prio_zur_pruefung(self, plan_runs):
        """Nach Prioritaet verteilte, noch nicht bestaetigte Jobs, die DIESEN
        Plan betreffen (sein Item) - fuer den Frage-Dialog, vorbelegt mit dem
        Plan, dem sie jetzt gehoeren. Format wie `_bd_job_offen`."""
        from .. import store as _st
        _pr = {int(t) for t, r in (plan_runs or {}).items() if int(r or 0) > 0}
        aus = []
        for _jid, _e in sorted((_st.job_zuordnung_mit_quelle("prioritaet") or {}).items()):
            try:
                _t = int(_e.get("type_id") or 0)
            except (TypeError, ValueError):
                continue
            if _t not in _pr:
                continue
            aus.append({"job_id": int(_jid), "type_id": _t,
                        "runs": int(_e.get("runs") or 0),
                        "fertig_ts": _e.get("ts"), "prio_plan": _e.get("plan_id"),
                        "kandidaten": self._job_plan_kandidaten(_t)})
        return aus

    def _job_plan_kandidaten(self, type_id):
        """Welche gespeicherten Plaene kommen fuer diesen Job in Frage?

        Gelesen wird `reserve_map` - dieselbe Quelle wie
        `_umstrittene_items`, also genau die Liste, aus der der Streit
        ueberhaupt entstanden ist. Der OFFENE Plan steht vorn: er ist der
        wahrscheinlichste, und der Dialog soll nicht zum Suchspiel werden.
        Rueckgabe: [(plan_id, Name), ...].
        """
        _tid = int(type_id)
        _pid = getattr(self, "_bd_open_plan_id", None)
        raus, _gesehen = [], set()
        _mitgl = MainWindowHelpers.buendel_mitglieder(getattr(self, "settings", None) or {})
        for _p in ((getattr(self, "settings", None) or {})
                   .get("bau_saved_plans") or []):
            _id = _p.get("id")
            if _id is None:
                continue
            # Buendel-Mitglied: zur Wahl steht das Buendel, nicht sein Teil.
            if str(_id) in _mitgl:
                continue
            # Die Schluessel der reserve_map sind mal Text, mal Zahl (JSON
            # macht daraus Text) - deshalb ueber int() vergleichen, nie
            # ueber die Schreibweise.
            _hat = False
            for _k, _v in (_p.get("reserve_map") or {}).items():
                try:
                    if int(_k) == _tid and int(_v or 0) > 0:
                        _hat = True
                        break
                except (TypeError, ValueError):
                    continue
            if not _hat:
                continue
            if str(_id) in _gesehen:
                continue
            _gesehen.add(str(_id))
            raus.append((_id, str(_p.get("label")
                                  or _p.get("item_name") or "?")))
        # DER OFFENE PLAN GEHOERT IMMER DAZU - er baut das Item ja gerade
        # (sonst waere der Job hier nie aufgetaucht). Seine reserve_map kann
        # trotzdem leer sein: sie entsteht erst beim Speichern.
        if _pid is not None and str(_pid) not in _gesehen:
            for _p in ((getattr(self, "settings", None) or {})
                       .get("bau_saved_plans") or []):
                if str(_p.get("id")) == str(_pid):
                    raus.append((_p.get("id"),
                                 str(_p.get("label")
                                     or _p.get("item_name") or "?")))
                    break
        raus.sort(key=lambda kv: (str(kv[0]) != str(_pid), str(kv[1]).lower()))
        return raus

    def _job_frage_antworten(self, antworten):
        """Die Antworten des Nutzers festschreiben. {job_id: plan_id|None}.

        `None` heisst "zu keinem meiner Plaene" - auch das ist eine Antwort
        und wird gemerkt (`store.PLAN_KEINER`), sonst kaeme dieselbe Frage
        bei jedem Aufbau wieder. Die Quelle ist immer `nutzer`: seine
        Entscheidung steht ueber jeder Automatik und wird deshalb auch
        ueber eine bestehende Zuordnung geschrieben.
        """
        from .. import store as _st
        _offen = {int(_f["job_id"]): _f
                  for _f in (list(getattr(self, "_bd_job_offen", None) or [])
                             + list(getattr(self, "_bd_job_prio", None) or []))}
        _n = 0
        for _jid, _plan in (antworten or {}).items():
            _f = _offen.get(int(_jid))
            if _f is None:
                continue
            _ziel = _st.PLAN_KEINER if _plan is None else _plan
            if not _st.job_zuordnung_setzen(int(_jid), _ziel,
                                            _f["type_id"], _f["runs"],
                                            "nutzer"):
                _st.job_zuordnung_umhaengen(int(_jid), _ziel)
            _n += 1
        return _n

    def _resolve_per_item_runs_cap(self, end_tid=None):
        """{type_id: max Runs je JOB} fuer schedule_build's per_item_runs_cap
        (Nutzer-Befund 19.09.2026, Einherji II: "Der Runplaner denkt ich kann
        17 Stueck mit einem Blueprint bauen ... gibts maximal 10 runs").
        Drei Quellen, je Item die KLEINSTE (Regel 3):
          1. SDE maxProductionLimit (`activity_max_runs`) - der Blueprints-
             Tab rechnet damit schon seine Kopien-Empfehlung;
          2. eigene BPCs aus dem ESI-Cache (kleinste Kopie, ohne BPO);
          3. das Endprodukt aus `_bd_bp["end"]` (Invention: Runs je
             erfundener BPC; eigene BPC: ESI oder "Runs/BPC") - nur wenn
             `runs_known` gesetzt ist, der Platzhalter 1x1 vor dem ersten
             rebuild() zaehlt NICHT."""
        out = {}
        _rec = getattr(self, "_bd_recipes", None)
        _p2b = getattr(_rec, "product_to_bp", None) or {}
        _plan = (getattr(self, "_bd_plan_ref", None) or {}).get("plan") or {}
        _runs = _plan.get("build_runs") or {}
        _amr = getattr(_rec, "activity_max_runs", None) or {}
        for t in _runs:
            _bp = _p2b.get(t)
            if not _bp:
                continue
            try:
                _m = int(_amr.get((_bp[0], _bp[1]), 0) or 0)
            except (TypeError, ValueError):
                _m = 0
            if _m >= 1:
                out[t] = _m
        _cache = getattr(self, "_bd_owned_bp_cache", None)
        if _cache:
            for t, _m in self._bpc_runs_by_tid(_cache, _runs, _p2b).items():
                out[t] = min(out.get(t, _m), _m)
        # MULTI-BAUPLAN, SCHRITT 4: "Runs/BPC" je ENDPRODUKT. `_bd_bp["end"]`
        # unten kennt nur EIN Endprodukt - im Buendel braucht jedes Ende
        # seine eigene Grenze (eine 10er-Kopie kann keinen 40er-Job fahren).
        _mr = getattr(self, "_multi_runs_cap_je_ende", None)
        if _mr is not None:
            out = _mr(out)
        _end = (getattr(self, "_bd_bp", None) or {}).get("end") or {}
        if end_tid is not None and _end.get("runs_known") and not _end.get("bpo"):
            try:
                _m = int(_end.get("runs", 0) or 0)
            except (TypeError, ValueError):
                _m = 0
            if _m >= 1:
                out[end_tid] = min(out.get(end_tid, _m), _m)
        return out

    def _resolve_per_item_bp_cap(self):
        """{type_id: Kopien} für schedule_build's per_item_cap - für JEDES
        Item, das der aktuelle Plan baut und von dem eigene Blaupausen im
        gemeinsamen ESI-Cache liegen (Endprodukt läuft separat über
        end_bp=_cap("end"), braucht hier keinen Eintrag). NUR für die
        live offene Bauplan-Sitzung (nie in den Hintergrund-Recompute für
        andere gespeicherte Pläne einspeisen - das wäre wieder dieselbe Art
        von Cross-Dialog-Bug wie beim Nachfüll-Plan-Fix).

        Basis ist der GEMEINSAME Blaupausen-Cache und der AKTUELLE Plan
        (s. _bp_copies_by_tid) - dieselbe Quelle, aus der auch der
        Blueprints-Tab seine "Besitze"-Spalte speist. Die Stufen-Ladung
        (`_bd_stage_bp_esi`) wird darüber gelegt: sie stammt aus demselben
        Cache, kann aber gezielt zurückgenommen werden ("Rückgängig" je
        Stufe), und diese ausdrückliche Nutzer-Entscheidung gewinnt."""
        out = {}
        _cache = getattr(self, "_bd_owned_bp_cache", None)
        if _cache:
            _plan = (getattr(self, "_bd_plan_ref", None) or {}).get("plan") or {}
            _rec = getattr(self, "_bd_recipes", None)
            out.update(self._bp_copies_by_tid(
                _cache, _plan.get("build_runs"),
                getattr(_rec, "product_to_bp", None)))
        for stage_dict in (getattr(self, "_bd_stage_bp_esi", None) or {}).values():
            out.update(stage_dict)
        # MULTI-BAUPLAN, SCHRITT 4b: Kopien JE ENDPRODUKT. Die Stufen-Zahl
        # `end_bp` gilt fuer alle Enden gemeinsam - beim Buendel beschreibt
        # sie mehrere verschiedene Produkte mit EINER Zahl.
        _mc = getattr(self, "_multi_bp_cap_je_ende", None)
        if _mc is not None:
            out = _mc(out)
        return out

    @staticmethod
    def _icon_fetch_size(size):
        """CCPs Bilder-Server akzeptiert nur feste Groessen - die angefragte
        auf die naechstgroessere gueltige runden. EINE Stelle dafuer (die
        Formel stand vorher dreimal im Code: _icon_html, _item_pixmap,
        Prefetch - Regel 9)."""
        try:
            _s = int(size)
        except (TypeError, ValueError):
            _s = 64
        return next((v for v in (32, 64, 128, 256, 512) if v >= _s), 512)

    @staticmethod
    def _pixmap_im_rahmen(pm, groesse):
        """Ein geladenes Item-Bild so verkleinern, dass es GANZ in seinen
        Rahmen passt.

        Sitzung 17 (Nutzer: "die Bilder ... zu nahe rangezoomt fuer dessen
        Rahmen"). `_item_pixmap` liefert die LADEgroesse des Bildservers
        (48 angefragt -> 64 geliefert, 20 -> 32). Ohne Verkleinern zeigte
        das QLabel nur den mittleren Ausschnitt - gemessen: bei 64 in 48
        fehlten 8 px an jedem Rand.
        """
        from PySide6.QtCore import Qt as _Qt
        if pm is None or pm.isNull():
            return pm
        return pm.scaled(int(groesse), int(groesse), _Qt.KeepAspectRatio,
                         _Qt.SmoothTransformation)

    @staticmethod
    def _icon_cache_name(type_id, kind, fetch_size):
        """Dateiname im icon_cache - ebenfalls nur EINMAL definiert."""
        return f"{int(type_id)}_{kind}_{int(fetch_size)}.png"

    @staticmethod
    def _icon_keys_to_fetch(wanted, tried):
        """Welche Icon-Schluessel muss der Hintergrund-Lauf wirklich holen?
        Alles, was gewuenscht und noch nicht VERSUCHT wurde. Schon versuchte
        bleiben draussen, auch wenn sie fehlgeschlagen sind (404 bei
        Blueprint-typeIDs ist normal) - sonst laeuft der Nachtrag endlos:
        holen -> nichts da -> neu aufbauen -> wieder gewuenscht -> holen ...
        Sortiert zurueck, damit der Lauf reproduzierbar ist."""
        return sorted(set(wanted or ()) - set(tried or ()))

    @staticmethod
    def _icon_prefetch_job(keys, cache_dir, fetch_fn, mkdir_fn, write_fn,
                           should_cancel=None):
        """HINTERGRUND-LAUF (kein Qt, keine self-Zugriffe - deshalb pur
        testbar und thread-sicher): holt die Bilder und legt sie als Datei
        im icon_cache ab. BEWUSST kein QPixmap hier - Qt-Bildobjekte duerfen
        nur im GUI-Thread entstehen; der Thread schreibt nur Bytes, das
        Laden passiert danach wieder im GUI-Thread aus dem Disk-Cache.
        Fehler (404 bei Blueprint-typeIDs ist normal) werden je Icon
        uebersprungen, nicht hochgereicht - ein fehlendes Bild darf den
        Rest nicht aufhalten. Gibt (n_geladen, n_fehler) zurueck."""
        _ok = 0
        _err = 0
        _made = False
        for (tid, fetch_size, kind) in keys:
            if should_cancel and should_cancel():
                break
            try:
                data = fetch_fn(tid, size=fetch_size, kind=kind)
                if not data:
                    _err += 1
                    continue
                if not _made:
                    mkdir_fn(cache_dir)
                    _made = True
                write_fn(cache_dir, MainWindowHelpers._icon_cache_name(
                    tid, kind, fetch_size), data)
                _ok += 1
            except Exception:
                _err += 1
        return _ok, _err

    @staticmethod
    def _cart_need_status(need, own):
        """Ampel fuer „habe ich genug?": (Schluessel, Klartext).
          covered  gruen  - Bestand deckt den Bedarf komplett
          partial  gelb   - etwas da, aber nicht genug
          none     rot    - nichts davon da
          unknown  grau   - Bedarf unbekannt (Aufrufer ohne Mengen)
        """
        from ..sprache import t as _txt   # Sitzung 17: Klartext zweisprachig
        if need is None:
            return ("unknown", _txt("need unknown"))
        own = int(own or 0)
        need = int(need)
        if own >= need:
            return ("covered", _txt("covered \u2713"))
        if own > 0:
            return ("partial", _txt("partial \u2013 {n} missing").format(
                n=f"{need - own:,}".replace(",", "'")))
        return ("none", _txt("missing completely \u2013 {n}").format(
            n=f"{need:,}".replace(",", "'")))

    @staticmethod
    def _copy_mode_status(missing, built, need, own):
        """Ampel im KOPIER-MODUS (Einkaufsliste aus dem Bauplan): dort ist
        der PLAN massgeblich, nicht der rohe Bedarf-vs-Besitz-Vergleich.
        NUTZER-VORFALL (Cerberus, Sitzung 7): der Plan sagte "0 zu kaufen"
        (gebaut/aus Bestand gedeckt), die Zeilen schrien trotzdem
        "teilweise - es fehlen 2'811'881" - und der Kopier-Knopf kopierte
        folgerichtig nichts. Angezeigte und kopierte Zahl kamen aus zwei
        Rechnungen (Regel 10).
        Regeln: plan-missing > 0 -> normale Bedarf/Besitz-Ampel (die sagt,
        WIE VIEL fehlt). plan-missing == 0 -> gruen, mit dem GRUND aus dem
        Plan: "wird gebaut" (built > 0) oder "Plan deckt's" (Bestand/
        eingefuegt/laufende Jobs). "own" bleibt der ECHTE Besitz (aa118)
        und steht weiter in der Spalte daneben."""
        if int(missing or 0) > 0:
            # DIE ZAHL AUS DEM PLAN NENNEN, nicht `Bedarf - Besitz` neu
            # rechnen (Nutzer-Screenshot Sitzung 12: Technetium stand mit
            # "Fehlt 78" und "In den Wagen 78" da, waehrend der Status
            # "teilweise - es fehlen 20" sagte).
            #
            # `_cart_need_status` kennt den Plan nicht: sie sieht nur Bedarf
            # und Besitz. Der Plan weiss dagegen, was reserviert, gebaut
            # oder aus anderem Bestand gedeckt ist - deshalb weichen die
            # Zahlen ab. Zwei Zahlen fuer dieselbe Zeile sind schlimmer als
            # eine unbequeme: der Nutzer weiss sonst nicht, welcher er
            # folgen soll. Genau davor warnt der Kommentar oben schon -
            # diese Stelle war das letzte Schlupfloch.
            from ..sprache import t as _txt   # Sitzung 17
            _fehlt_txt = f"{int(missing):,}".replace(",", "'")
            if int(own or 0) <= 0:
                # GAR NICHTS DA -> ROT. "teilweise" waere gelogen und
                # verharmlost: hier liegt kein einziges Stueck.
                return ("none", _txt("missing completely \u2013 {n}").format(n=_fehlt_txt))
            return ("partial", _txt("partial \u2013 {n} missing").format(n=_fehlt_txt))
        from ..sprache import t as _txt   # Sitzung 17
        if int(built or 0) > 0:
            return ("covered", _txt("covered \u2713 \u2013 being built"))
        return ("covered", _txt("covered \u2713 \u2013 the plan covers it "
                                "(stock/jobs)"))

    @staticmethod
    @staticmethod
    def belegte_runs_seit(zuordnung, stock_seen_ts):
        """{type_id: Runs} aus der Job-Zuordnung eines Plans - NUR Eintraege,
        die ESI im Bestand schon gesehen hat.

        RESERVIERUNG OHNE HAND-HAKEN (Nutzer 26.09.2026: "machen okey, aber
        Handhaken als optischen Marker will ich behalten, weil ESI einfach
        sehr langsam ist"). Bisher gab NUR der Hand-Haken die Zutaten einer
        Zeile frei (`_reserve_map_mitlaufend`). Seit Stufe B/C steht in
        `job_zuordnung`, welche GELIEFERTEN Jobs diesem Plan gehoeren
        (Klick, eindeutig, Nutzer-Antwort) - ihre Zutaten sind im Spiel
        laengst verbraucht, der Plan hielt sie trotzdem fest, bis jemand
        hakte. Der Haken bleibt (Marker und Sofort-Freigabe), der Beleg
        kommt dazu.

        DIESELBE ESI-VERZUGS-SPERRE wie beim Haken: ein Eintrag zaehlt erst,
        wenn der Bestand von NACH der Zuordnung stammt (`ts` <=
        `stock_seen_ts`). Ohne Bestandszeit zaehlt nichts (Regel 3: lieber
        zu viel reserviert als zu wenig). Rein und ohne Fenster pruefbar;
        `zuordnung` ist {job_id: {type_id, runs, ts, ...}} wie
        `store.job_zuordnung_fuer_plan`.
        """
        if not zuordnung or stock_seen_ts is None:
            return {}
        try:
            _grenze = float(stock_seen_ts)
        except (TypeError, ValueError):
            return {}
        aus = {}
        for _e in (zuordnung or {}).values():
            try:
                _t = int(_e.get("type_id"))
                _r = int(_e.get("runs") or 0)
                _ts = float(_e.get("ts") or 0.0)
            except (TypeError, ValueError, AttributeError):
                continue
            if _r <= 0 or _ts > _grenze:
                continue
            aus[_t] = aus.get(_t, 0) + _r
        return aus

    @staticmethod
    def _reserve_map_mitlaufend(plan, reserve_map, checked_ts, assignments,
                                stock_seen_ts, belegt=None, haken_runs=None):
        """Reservierung, die dem Baufortschritt FOLGT statt beim Speichern
        stehenzubleiben.

        NUTZER-FALL (Sitzung 10): "ich arbeite die Runs nach und nach ab, und
        dabei fallen staendig neue Zwischenprodukte von verschiedenen
        Bauplaenen in den Hangar". Die alte Reservierung war eine
        Momentaufnahme vom Speichern und wurde NIE kleiner - ein halb
        abgearbeiteter Plan sperrte weiter seine laengst verbrauchten
        Zutaten. Legte ein anderer Plan frische nach, sah ein dritter sie
        als belegt.

        REGEL: ein abgehakter Run bucht die ZUTATEN dieses Items ab (sie sind
        verbraucht) - das ERZEUGNIS bleibt reserviert (es liegt jetzt im
        Hangar und gehoert diesem Plan). Der Anspruch wandert also mit dem
        Material die Stufen hoch.

        ANTEILIG, NICHT ALLES-ODER-NICHTS: jede Zuteilung traegt ihre eigene
        Run-Zahl, deshalb wird `erledigte Runs / geplante Runs` je Item
        gerechnet. Zwei Charaktere am selben Item, einer fertig -> die Haelfte
        der Zutaten faellt raus.

        ESI-VERZUG (Nutzer: "so schnell gehts nicht, die ESI aktualisiert nur
        alle Stunde"): ein Haken wird ERST beruecksichtigt, wenn der
        Bestand von NACH dem Haken stammt (`stock_seen_ts`). Sonst gaebe der
        Plan seine Zutaten frei, waehrend ESI sie noch als vorhanden meldet -
        und niemand beansprucht sie mehr. IM ZWEIFEL LIEBER ZU VIEL
        RESERVIEREN: zu viel heisst, ein anderer Plan wartet eine Stunde
        laenger; zu wenig heisst, dem Nutzer fehlt mitten im Bau Material.

        BELEGTE RUNS (26.09.2026, `belegt` = {type_id: Runs} aus
        `belegte_runs_seit`): zaehlen wie ein Haken - je Item das MAXIMUM
        aus Haken und Beleg, nie die Summe (derselbe Run kann in beiden
        stehen), gedeckelt auf die geplanten Runs.

        Gibt eine NEUE Karte zurueck, die Eingaben bleiben unangetastet.
        """
        out = {int(t): int(q) for t, q in (reserve_map or {}).items()}
        _br_plan = (plan or {}).get("build_runs") or {}
        if (not checked_ts and not belegt) or (not assignments and not _br_plan):
            return out
        # Geplante und erledigte Runs je Item aus den Zuteilungen.
        geplant, erledigt = {}, {}
        for a in (assignments or []):
            _tid = a.get("tid", a.get("type_id"))
            if _tid is None:
                continue
            _tid = int(_tid)
            _runs = int(a.get("runs", 0) or 0)
            if _runs <= 0:
                continue
            geplant[_tid] = geplant.get(_tid, 0) + _runs
            _key = f"{a.get('stage', 'component')}|{a.get('char_id')}|{_tid}"
            _ts = (checked_ts or {}).get(_key)
            if _ts is None:
                continue
            if stock_seen_ts is None or float(_ts) > float(stock_seen_ts):
                continue          # ESI hat den Verbrauch noch nicht gesehen
            erledigt[_tid] = erledigt.get(_tid, 0) + _runs
        # GESPEICHERTE ZUTEILUNGEN TRUGEN NIE EINE type_id (Befund 28.09.2026,
        # GEMESSEN in der settings.json des Nutzers: alle 17 Plaene haben nur
        # char/item/runs/jobs/seconds/stage/slots/char_done). `geplant` blieb
        # dadurch leer, jeder Beleg fiel oben durch - Multiplan 1 hielt 129'375
        # Phenolic reserviert, obwohl alle Verbraucher laengst gebaut waren
        # (mit Beleg: 2'457), und der Basilisk sah seinen Hangar als leer.
        # Rueckfall: die Plan-Runs aus dem Schnappschuss (`build_runs` ist
        # die Summe der Zuteilungen je Item - dieselbe Zahl).
        for _t_b, _r_b in _br_plan.items():
            try:
                _t_b, _r_b = int(_t_b), int(_r_b or 0)
            except (TypeError, ValueError):
                continue
            if _r_b > 0 and _t_b not in geplant:
                geplant[_t_b] = _r_b
        # HAND-HAKEN ALTER PLAENE (Nutzer 28.09.2026, "ja genau"): ihre
        # Zuteilungen tragen keine tid/char_id, der Schluessel-Abgleich oben
        # findet also nichts. `haken_runs` (= `checked_runplan_runs`,
        # {"stufe|tid": erledigte Runs}) kennt die Runs je Item; der Haken
        # zaehlt erst, wenn der Bestand juenger ist als der JUENGSTE Haken
        # dieses Items (dieselbe ESI-Sperre). Ohne Stempel: nichts.
        _h_ts = {}
        for _k_h, _ts_h in (checked_ts or {}).items():
            _teile = str(_k_h).split("|")
            if len(_teile) != 3:
                continue
            try:
                _sch = (_teile[0], int(_teile[2]))
                _h_ts[_sch] = max(_h_ts.get(_sch, 0.0), float(_ts_h))
            except (TypeError, ValueError):
                continue
        for _k_h, _n_h in (haken_runs or {}).items():
            _st_h, _, _t_h = str(_k_h).rpartition("|")
            try:
                _t_h, _n_h = int(_t_h), int(_n_h or 0)
            except (TypeError, ValueError):
                continue
            _ts_h = _h_ts.get((_st_h, _t_h))
            if _n_h <= 0 or _t_h not in geplant or _ts_h is None:
                continue
            if stock_seen_ts is None or _ts_h > float(stock_seen_ts):
                continue          # ESI hat den Verbrauch noch nicht gesehen
            erledigt[_t_h] = min(geplant[_t_h], max(erledigt.get(_t_h, 0), _n_h))
        for _tid, _n in (belegt or {}).items():
            try:
                _tid = int(_tid)
                _n = int(_n or 0)
            except (TypeError, ValueError):
                continue
            if _n <= 0 or _tid not in geplant:
                continue
            # MAXIMUM, nicht Summe - und nie mehr als geplant.
            erledigt[_tid] = min(geplant[_tid], max(erledigt.get(_tid, 0), _n))
        if not erledigt:
            return out
        _mats = (plan or {}).get("build_mats") or {}
        for _tid, _fertig in erledigt.items():
            _ges = geplant.get(_tid, 0)
            if _ges <= 0:
                continue
            _anteil = min(1.0, float(_fertig) / float(_ges))
            for _m, _q in (_mats.get(_tid) or []):
                _m = int(_m)
                if _m not in out:
                    continue
                _weg = int(_q * _anteil)
                out[_m] = max(0, out[_m] - _weg)
                if out[_m] == 0:
                    out.pop(_m, None)
        return out

    @staticmethod
    def plan_rang(settings):
        """BAU-PRIORITAET = Reihenfolge der Karten in "My build plans"
        (Nutzer-Entscheid 28.09.2026: "vielleicht koennen wir eine Art
        Zuordnung machen, welchen Plan man als erstes baut, als 2tes usw. ...
        und dementsprechend sind die Mats immer klar" -> "Kartenreihenfolge").

        {str(plan_id): Rang 1..n} fuer die OFFENEN Plaene (nicht
        abgeschlossen, kein Buendel-Mitglied). Die Folge ist die eigene
        (Arrange, `bau_plan_reihenfolge`); Plaene, die dort noch fehlen,
        haengen in Speicher-Reihenfolge hinten an. Rang 1 bekommt Bestand und strittige
        Jobs zuerst. Rein und ohne Fenster pruefbar."""
        s = settings or {}
        plaene = list(s.get("bau_saved_plans") or [])
        _mitgl = MainWindowHelpers.buendel_mitglieder(s)
        # NUR DEINE EIGENE FOLGE (Nutzer 28.09.2026, "ja alles bauen"): die
        # Sortierung nach Fortschritt aenderte die Prioritaet von selbst -
        # Material wanderte zwischen Plaenen, ohne dass er etwas tat. Jetzt
        # zaehlt die zuletzt von Hand angeordnete Folge, auch wenn die
        # Karten gerade nach Fortschritt angezeigt werden (die "#n" auf der
        # Karte sagt dann, was gilt).
        folge = MainWindowHelpers.plan_folge(s)
        _pos = {str(p): i for i, p in enumerate(folge)}
        offen = [p for p in plaene
                 if p.get("id") is not None and not p.get("done_manual")
                 and str(p.get("id")) not in _mitgl]
        offen.sort(key=lambda p: (_pos.get(str(p.get("id")), 10 ** 6),
                                  plaene.index(p)))
        return {str(p.get("id")): i + 1 for i, p in enumerate(offen)}

    @staticmethod
    def plan_folge(settings):
        """Die eigene Karten-Folge VOLLSTAENDIG: jeder gespeicherte Plan hat
        einen Platz.

        NEUE PLAENE UEBER DIE FERTIGEN (Nutzer 29.09.2026: "neu erstellte
        Bauplaene sollten nicht ganz unten gelistet werden ... sondern ueber
        den bereits fertigen, in meinem Fall auf Position 3, weil Pos. 1 und
        2 schon angefangen und von mir fixiert wurden"). Vorher bekam ein
        Plan, der noch nicht in `bau_plan_reihenfolge` stand, den Platz
        10**6 - ganz unten, unter allen abgeschlossenen, mit Rang #6.
        Jetzt: fehlende OFFENE Plaene (in Speicher-Reihenfolge) direkt VOR
        den ersten abgeschlossenen, fehlende abgeschlossene ans Ende. Die
        Plaene, die er selbst angeordnet hat, bleiben wo sie sind.
        Rein; aendert die Einstellungen nicht."""
        s = settings or {}
        plaene = [p for p in (s.get("bau_saved_plans") or []) if p.get("id") is not None]
        ids = [str(p.get("id")) for p in plaene]
        _da = set(ids)
        folge = []
        for x in (s.get("bau_plan_reihenfolge") or []):
            if str(x) in _da and str(x) not in folge:
                folge.append(str(x))
        _drin = set(folge)
        fertig = {str(p.get("id")) for p in plaene if p.get("done_manual")}
        fehlt = [i for i in ids if i not in _drin]
        if not fehlt:
            return folge
        neu_offen = [i for i in fehlt if i not in fertig]
        neu_fertig = [i for i in fehlt if i in fertig]
        k = next((n for n, x in enumerate(folge) if x in fertig), len(folge))
        return folge[:k] + neu_offen + folge[k:] + neu_fertig

    @staticmethod
    def buendel_mitglieder(settings):
        """ids der Einzelplaene, die in einem NICHT abgeschlossenen
        Multi-Bauplan stecken (dessen `quellen`).

        NUTZER 26.09.2026: "Flycatcher, Stork und Ametat II sollten gar
        nicht mehr als Einzelplaene gelten, die sind aktuell in einem
        Multiplan verflochten - die sollen NUR noch da existieren, nicht
        doppelt oder sonstwo als einzelner." Vorher galt jeder der drei
        weiter als eigener, offener Plan: seine reserve_map machte Titanium
        Carbide STRITTIG, die 143 gelieferten TC-Runs durfte die Einkaufs-
        liste darum keinem Plan zuschreiben, und der Bauplan verlangte 66
        statt 0 Silicon-Diborite-Runs (zuordnung_bericht 25.09.2026).

        ABGELEITET wie `_multi_gehoert_zu` in mw_multi_bauplan: die Quelle
        ist das Buendel, kein Merker am Einzelplan. Ein abgeschlossenes
        Buendel gibt seine Mitglieder wieder frei - sie sind dann ohnehin
        selbst abgeschlossen oder wieder eigenstaendig.

        Rein und ohne Fenster pruefbar. Rueckgabe: set von str(plan_id).
        """
        raus = set()
        for p in ((settings or {}).get("bau_saved_plans") or []):
            try:
                if int(p.get("type_id", 0) or 0) != -1:   # industry.BUENDEL_ID (kein Import: Zirkel)
                    continue
            except (TypeError, ValueError):
                continue
            if p.get("done_manual"):
                continue
            for qid in (p.get("quellen") or []):
                raus.add(str(qid))
        return raus

    @staticmethod
    def _fremde_reservierungen(settings, exclude_plan_id):
        """{Plan-Name: reserve_map} aller ANDEREN Plaene mit aktivem Schloss.

        `_reserved_by_other_plans` summiert ueber alle Plaene - fuer die
        Job-Zuordnung braucht es die Karten EINZELN, sonst laesst sich kein
        Name nennen.
        """
        raus = {}
        _mitgl = MainWindowHelpers.buendel_mitglieder(settings)
        for p in (settings.get("bau_saved_plans") or []):
            if not p.get("reserve"):
                continue
            # Buendel-Mitglied: sein Anspruch lebt im Buendel, nicht doppelt.
            if str(p.get("id")) in _mitgl:
                continue
            try:
                if exclude_plan_id is not None and int(p.get("id") or 0) == int(exclude_plan_id):
                    continue
            except (TypeError, ValueError):
                pass
            rm = p.get("reserve_map") or {}
            if rm:
                raus[str(p.get("label") or p.get("item_name") or "?")] = {
                    int(k): int(v) for k, v in rm.items()}
        return raus

    @staticmethod
    def _umstrittene_items(settings, exclude_plan_id):
        """type_ids, die mindestens ein ANDERER gespeicherter Plan beansprucht.

        Gelesen wird `reserve_map` - die schreibt jeder Plan beim Speichern,
        UNABHAENGIG vom Schloss. Das ist hier die richtige Quelle: die Frage
        lautet nicht "wer hat reserviert", sondern "wer koennte denselben
        Job gebaut haben". Ein Plan ohne Schloss baut genauso.

        Unterschied zu `_fremde_reservierungen` (die nur Plaene MIT Schloss
        nennt): dort geht es um den Materialpool, hier um die Zuordnung
        eines Jobs.

        ABGESCHLOSSENE PLAENE ZAEHLEN NICHT MEHR (Nutzer 25.09.2026: "die
        Frage war relativ unnoetig, es ist der einzige nicht abgeschlossene
        Bauplan den ich habe"). Die Frage lautet "wer koennte den Job gebaut
        haben" - wer seinen Plan auf FERTIG gestellt hat, baut dafuer nichts
        mehr. Seine `reserve_map` bleibt trotzdem stehen (das Schloss geht
        beim Abschliessen nur auf), und genau daran haengt sonst jedes
        Zwischenprodukt fuer immer im Streit fest: der laufende Plan
        verliert seinen Fortschritt, und gefragt wird ueber Plaene, die
        niemand mehr baut.
        """
        raus = set()
        _mitgl = MainWindowHelpers.buendel_mitglieder(settings)
        for p in ((settings or {}).get("bau_saved_plans") or []):
            if p.get("done_manual"):
                continue
            # BUENDEL-MITGLIEDER ZAEHLEN NICHT (Nutzer 26.09.2026): wer in
            # einem Multiplan steckt, baut nicht noch einmal fuer sich.
            if str(p.get("id")) in _mitgl:
                continue
            try:
                if exclude_plan_id is not None and \
                        int(p.get("id") or 0) == int(exclude_plan_id):
                    continue
            except (TypeError, ValueError):
                pass
            for k in (p.get("reserve_map") or {}):
                try:
                    raus.add(int(k))
                except (TypeError, ValueError):
                    continue
        return raus

    @staticmethod
    def _umstrittene_seit(settings, exclude_plan_id):
        """{type_id: fruehester Einfrier-Zeitpunkt eines ANDEREN Plans, der
        das Item beansprucht}.

        ZEIT ENTSCHEIDET (Nutzer 26.09.2026: "wie koennte man so etwas
        zusaetzlich verhindern im Falle von Einzelplaenen?" - "ja macht
        Sinn"). Ein Plan, der erst NACH dem Start eines Jobs eingefroren
        wurde, kann diesen Job nicht gebaut haben - er existierte in dieser
        Form noch nicht. Bleibt fuer den Job kein anderer Plan uebrig, ist
        er eindeutig, ohne Frage.

        Dieselbe Auswahl wie `_umstrittene_items` (offen, kein Buendel-
        Mitglied, nicht der eigene Plan). Ein Plan OHNE Einfrier-Zeitpunkt
        zaehlt als "schon immer" (0.0) - ohne Beleg gilt der Streit
        (Regel 3). Rein und ohne Fenster pruefbar; s. `job_umstritten`.
        """
        raus = {}
        _mitgl = MainWindowHelpers.buendel_mitglieder(settings)
        for p in ((settings or {}).get("bau_saved_plans") or []):
            if p.get("done_manual"):
                continue
            if str(p.get("id")) in _mitgl:
                continue
            try:
                if exclude_plan_id is not None and \
                        int(p.get("id") or 0) == int(exclude_plan_id):
                    continue
            except (TypeError, ValueError):
                pass
            try:
                _ts = float((p.get("frozen") or {}).get("ts") or 0.0)
            except (TypeError, ValueError):
                _ts = 0.0
            for k in (p.get("reserve_map") or {}):
                try:
                    _t = int(k)
                except (TypeError, ValueError):
                    continue
                raus[_t] = min(raus.get(_t, _ts), _ts)
        return raus

    @staticmethod
    def _plan_mit_anspruch(type_id, fremde_reservierungen):
        """Welcher ANDERE Plan beansprucht dieses Item ebenfalls?

        Unterschied zu `_job_gehoert_anderem_plan`: hier wird der EIGENE
        Anspruch NICHT geprueft. Gerade der Fall "beide Plaene bauen dasselbe
        Zwischenprodukt" soll den Hinweis ausloesen - dort laesst sich der
        laufende Job naemlich gar nicht zuordnen, und der Lauf-Punkt bleibt
        stehen (Regel 3). Statt eine Zuordnung vorzutaeuschen, sagt das
        Werkzeug die Unsicherheit.

        Rueckgabe: Name des anderen Plans, oder None.
        """
        tid = int(type_id)
        for name, karte in (fremde_reservierungen or {}).items():
            if int((karte or {}).get(tid, 0) or 0) > 0:
                return name
        return None

    @staticmethod
    def _job_gehoert_anderem_plan(type_id, fremde_reservierungen, eigene=None):
        """Gehoert ein laufender ESI-Job wahrscheinlich einem ANDEREN Plan?

        NUTZER-BEFUND (Sitzung 16): im Ametat-Plan stand "Phenolic Composites"
        mit dem Lauf-Punkt, obwohl der Job zum Viator-Plan gehoerte. Sein
        Hinweis war der Schluessel: "es muesste doch erkennen, dass der andere
        Bauplan die Materialien reserviert hat."

        WARUM DAS GEHT: ESI sagt NICHT, zu welchem Bauplan ein Job gehoert -
        Baupläne sind unser Begriff, nicht der des Spiels. Reservierungen sind
        das EINZIGE plan-zugeordnete Signal, und `_plan_reserve_map` traegt
        seit Sitzung 15 auch die SELBST GEBAUTEN Zwischenprodukte. Damit
        laesst sich schliessen: reserviert genau ein anderer Plan dieses
        Item, gehoert der Job dorthin.

        WAS ES NICHT IST: ein Beweis. Reservieren beide Plaene dasselbe Item -
        oder keiner -, gibt es keine Aussage, und die Funktion sagt None.
        Dann bleibt es beim bisherigen Verhalten.

        RICHTUNG DER UNSICHERHEIT (Regel 3): im Zweifel NICHTS behaupten.
        Ein Lauf-Punkt zu viel ist harmlos; einer zu wenig liesse den Nutzer
        einen Job doppelt starten.

        Rueckgabe: Name des fremden Plans, oder None.
        """
        tid = int(type_id)
        if int((eigene or {}).get(tid, 0) or 0) > 0:
            return None              # der eigene Plan beansprucht es auch
        for name, karte in (fremde_reservierungen or {}).items():
            if int((karte or {}).get(tid, 0) or 0) > 0:
                return name
        return None

    @staticmethod
    def _plan_reserve_map(plan):
        """Was ein Plan aus dem GETEILTEN Materialpool beansprucht: Einkauf
        (wird beschafft, eingelagert und dann verbraucht) + Bestandsdeckung
        + Invention-Material + WAS ER SELBST BAUT (`build_made`).

        DAS SELBSTGEBAUTE MUSS MIT (Nutzer-Ansage Sitzung 10): "wenn wir ein
        Produkt bauen, darf das nicht fuer einen anderen Bauplan als Bestand
        gewertet werden". Genau das passierte - Plan 1 baute aus eigenen
        Intermediates ein Composite, das Composite lag danach im Hangar, und
        weil nur `buy`/`stock_used` reserviert waren, sah Plan 2 es als freies
        Material und verbaute es. Plan 1 stand am Ende ohne da.

        WARUM DAS NICHT DOPPELT SPERRT (das war die alte Begruendung fuers
        Weglassen): ein Gegenstand existiert immer nur in EINER Form. Solange
        die Intermediates da sind, gibt es das Composite noch nicht - die
        Reservierung darauf zeigt ins Leere und nimmt niemandem etwas weg.
        Sind sie verbaut, zeigt umgekehrt die Reservierung auf die
        Intermediates ins Leere. Beansprucht wird also zu jedem Zeitpunkt nur,
        was tatsaechlich im Hangar liegt. Der EIGENE Plan wird bei der
        Pool-Rechnung ohnehin ausgenommen, er hungert sich nicht selbst aus.

        `build_runs` waere hier FALSCH - das sind Runs, keine Stueckzahlen.
        `build_made` traegt die Einheiten (inkl. Reaktions-Ueberschuss, der
        ebenfalls dem erzeugenden Plan gehoert).
        """
        out = {}
        for key in ("buy", "stock_used", "inv_buy", "inv_stock_used",
                    "build_made"):
            for t, q in ((plan or {}).get(key) or {}).items():
                if q and q > 0:
                    out[int(t)] = out.get(int(t), 0) + int(q)
        return out

    @staticmethod
    def _plan_snapshot_pack(plan):
        """Plan-dict JSON-fest machen (fuer das Einfrieren des PLANS, nicht
        nur der Preise). Sets werden zu SORTIERTEN Listen (deterministisch),
        Tupel zu Listen - alles andere bleibt. Die int-Keys der Mengen-Maps
        macht erst json.dump kaputt (Strings); das dreht _plan_snapshot_unpack
        beim Laden zurueck - dieselbe Falle wie bei den eingefrorenen
        "prices"."""
        def _pack(v):
            if isinstance(v, dict):
                return {str(k): _pack(x) for k, x in v.items()}
            if isinstance(v, (set, frozenset)):
                return sorted(_pack(x) for x in v)
            if isinstance(v, (list, tuple)):
                return [_pack(x) for x in v]
            return v
        return _pack(plan or {})

    @staticmethod
    def _plan_snapshot_unpack(snap):
        """Gegenstueck zu _plan_snapshot_pack: nach JSON-Roundtrip die
        Ziffern-String-Keys wieder zu int machen (Plan-Maps sind mit type_id/
        bp_id verschluesselt; Text-Keys wie "index"/"tax"/"scc" bleiben
        Strings). Negative IDs gibt es im Plan nicht, werden aber der
        Vollstaendigkeit halber genauso behandelt."""
        def _key(k):
            if isinstance(k, str):
                _k = k[1:] if k.startswith("-") else k
                if _k.isdigit():
                    return int(k)
            return k

        def _unpack(v):
            if isinstance(v, dict):
                return {_key(k): _unpack(x) for k, x in v.items()}
            if isinstance(v, list):
                return [_unpack(x) for x in v]
            return v
        return _unpack(snap or {})

    @staticmethod
    def _iso_job_ts(s):
        """ESI-Zeitstempel ('2026-08-04T12:00:00Z') -> Epochensekunden,
        None bei Unlesbarem (Job wird dann NICHT gezaehlt - lieber eine
        Zeile zu wenig automatisch abhaken als eine falsche)."""
        from datetime import datetime
        try:
            return datetime.fromisoformat(
                str(s).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _frozen_auto_checked(delivered_jobs, assignments, frozen_ts):
        """FORTSCHRITT AUS ESI-JOBS (pure Funktion, Nutzer-Spez Punkt 2):
        gelieferte Jobs seit dem Einfrier-Zeitpunkt je Plan-Item aufsummieren.
        Erreicht die Summe die Plan-Runs des Items, gelten ALLE Runplaner-
        Zeilen dieses Items als automatisch abgehakt (dieselben Schluessel
        wie die Hand-Haekchen: "{stage}|{char_id}|{tid}" - EINE Wahrheit).

        Bewusst ueber JOBS statt Bestand: "gebaut und schon in Stufe 2
        verbraucht" ist im Bestand unsichtbar, in der Job-Historie nicht.
        Aktivitaet muss zur Stufe passen (Reaktion 9/11 vs. Fertigung 1),
        sonst zaehlte ein zufaellig gleichnamiger Fertigungs-Job eine
        Reaktions-Zeile ab. Rueckgabe: (keys:set, geliefert:{tid: runs})."""
        plan_runs = {}
        is_react = {}
        keys_by_tid = {}
        for a in (assignments or []):
            try:
                tid = int(a["tid"])
            except (KeyError, TypeError, ValueError):
                continue
            plan_runs[tid] = plan_runs.get(tid, 0) + int(a.get("runs") or 0)
            # EINE Wahrheit, s. stufe_ist_reaktion - "unrefined" ist
            # ebenfalls eine Reaktion und wurde hier frueher uebersehen.
            is_react[tid] = stufe_ist_reaktion(a.get("stage"))
            keys_by_tid.setdefault(tid, set()).add(
                f"{a.get('stage')}|{a.get('char_id')}|{tid}")
        delivered = {}
        try:
            _fts = float(frozen_ts)
        except (TypeError, ValueError):
            return set(), {}
        for j in (delivered_jobs or []):
            pid = j.get("product_type_id")
            try:
                tid = int(pid)
            except (TypeError, ValueError):
                continue
            if tid not in plan_runs:
                continue
            act = j.get("activity_id")
            if is_react.get(tid):
                if act not in (9, 11):
                    continue
            elif act != 1:
                continue
            cts = MainWindowHelpers._iso_job_ts(j.get("completed_date"))
            if cts is None or cts < _fts:
                continue
            delivered[tid] = delivered.get(tid, 0) + int(j.get("runs") or 0)
        keys = set()
        for tid, got in delivered.items():
            if plan_runs.get(tid, 0) > 0 and got >= plan_runs[tid]:
                keys |= keys_by_tid.get(tid, set())
        return keys, delivered

    def _frozen_snapshot_plan(self):
        """Der EINGEFRORENE Plan (entpackt + gecacht). None, wenn nicht
        eingefroren oder wenn ein ALT-Payload ohne plan_snapshot vorliegt
        (Plaene aus der Zeit, als nur die Preise eingefroren wurden -
        die rechnen weiter wie bisher, kein stilles Umdeuten).
        Cache-Schluessel ist der Einfrier-Zeitstempel: neu einfrieren =
        neuer ts = Cache verworfen."""
        fz = getattr(self, "_bd_frozen", None)
        snap = (fz or {}).get("plan_snapshot")
        if not snap:
            return None
        _key = fz.get("ts")
        _c = getattr(self, "_bd_frozen_plan_cache", None)
        if _c and _c[0] == _key:
            return _c[1]
        plan = self._plan_snapshot_unpack(snap)
        self._bd_frozen_plan_cache = (_key, plan)
        return plan

    @staticmethod
    def bestand_nach_reservierungen(stock, fremd, eigen):
        """Verfuegbarer Bestand nach Abzug FREMDER Reservierungen - der eigene
        reservierte Anteil bleibt geschuetzt (Sitzung 17).

        Faire Aufteilung: jeder Plan bekommt zuerst seinen reservierten
        Anteil, vom Rest bedient er sich. Als Deckel gerechnet; beides ist
        dasselbe:  eigen + max(0, Bestand - alle)  ==  max(Bestand - fremd, eigen)

        Aendert `stock` an Ort und Stelle und liefert {type_id: abgezogen}.
        """
        applied = {}
        if not fremd or not stock:
            return applied
        for _t, _q in (fremd or {}).items():
            _have = stock.get(_t, 0)
            if _have <= 0:
                continue
            _schutz = min(int((eigen or {}).get(int(_t), 0) or 0), _have)
            _cut = min(_have - _schutz, int(_q or 0))
            if _cut <= 0:
                continue
            stock[_t] = _have - _cut
            if stock[_t] <= 0:
                stock.pop(_t, None)
            applied[_t] = _cut
        return applied

    @staticmethod
    def _reserved_by_this_plan(settings, plan_id):
        """Was DIESER Plan selbst reserviert hat - {type_id: Menge}.

        Sitzung 17 (Nutzer): seine eigene Reservierung nahm ihn bisher nur
        von der Kuerzung AUS, sie SCHUETZTE aber nichts. Andere Plaene
        durften den Bestand rechnerisch bis auf Null aufbrauchen - auch die
        Einheiten, die er laengst gekauft und fuer sich reserviert hatte.
        Dieselbe mitlaufende Rechnung wie fuer die anderen Plaene, damit
        beide Seiten dieselbe Wahrheit benutzen (Arbeitsregel 9).
        """
        if plan_id is None:
            return {}
        for p in (settings or {}).get("bau_saved_plans", []) or []:
            if p.get("id") != plan_id or not p.get("reserve"):
                continue
            rm = p.get("reserve_map") or {}
            if not rm:
                return {}
            _snap = ((p.get("frozen") or {}).get("plan_snapshot")) or None
            if _snap:
                try:
                    rm = MainWindowHelpers._reserve_map_mitlaufend(
                        MainWindowHelpers._plan_snapshot_unpack(_snap), rm,
                        p.get("checked_runplan_ts") or {},
                        p.get("assignments") or [],
                        (p.get("frozen") or {}).get("stock_seen_ts"),
                        belegt=MainWindowHelpers._belegt_fuer_plan(p),
                        haken_runs=p.get("checked_runplan_runs"))
                except Exception:
                    rm = p.get("reserve_map") or {}
            return {int(t): int(q or 0) for t, q in (rm or {}).items()}
        return {}

    @staticmethod
    def _belegt_fuer_plan(p):
        """Belegte Runs eines gespeicherten Plans (s. `belegte_runs_seit`);
        ohne Speicher oder bei Fehlern leer - dann gilt der Haken allein."""
        try:
            from .. import store as _st
            return MainWindowHelpers.belegte_runs_seit(
                _st.job_zuordnung_fuer_plan(p.get("id")),
                (p.get("frozen") or {}).get("stock_seen_ts"))
        except Exception:
            return {}

    @staticmethod
    def _reserved_by_other_plans(settings, exclude_plan_id):
        """Summierte Reservierungen aller ANDEREN gespeicherten Bauplaene
        mit aktiver 🔒-Reservierung (Nutzer-Fall: Material fuer Plan 1
        liegt schon auf der Station, waehrend Plan 2 eingekauft wird - ohne
        Reservierung zaehlte Plan 2 diese Einkaeufe als freien Bestand und
        die Einkaufsliste wurde falsch klein). Der EIGENE Plan wird
        ausgenommen - er darf sich nicht selbst aushungern.

        MITLAUFEND seit Sitzung 10: je Plan wird nicht mehr die starre Liste
        vom Speichern genommen, sondern das, was er NOCH braucht - abgehakte
        Runs buchen ihre Zutaten ab (s. `_reserve_map_mitlaufend`). Ohne das
        sperrte ein halb abgearbeiteter Plan dauerhaft Material, das er
        laengst verbraucht hatte, und blockierte damit den Nachschub anderer
        Plaene.
        """
        agg = {}
        labels = []
        _mitgl = MainWindowHelpers.buendel_mitglieder(settings)
        # BAU-PRIORITAET (28.09.2026, Nutzer-Entscheid "Kartenreihenfolge"):
        # ein Plan sieht nur die Reservierungen der Plaene VOR ihm. Ein
        # neuerer Plan weiter unten kann ihm also kein Material mehr
        # "wegnehmen"; ein Plan ohne Rang (ungespeichert, abgeschlossen)
        # steht hinten und sieht wie bisher alle.
        _rang = MainWindowHelpers.plan_rang(settings)
        _mein = (_rang.get(str(exclude_plan_id))
                 if exclude_plan_id is not None else None)
        for p in (settings or {}).get("bau_saved_plans", []) or []:
            if not p.get("reserve"):
                continue
            if exclude_plan_id is not None and p.get("id") == exclude_plan_id:
                continue
            _sein = _rang.get(str(p.get("id")))
            if _mein is not None and _sein is not None and _sein > _mein:
                continue
            # Buendel-Mitglied: reserviert nicht noch einmal neben dem Buendel.
            if str(p.get("id")) in _mitgl:
                continue
            # BEIDE RICHTUNGEN (Nutzer-Entscheid Sitzung 16, nach Verlust).
            #
            # HISTORIE, damit niemand die alte Regel zurueckholt:
            # Sitzung 10 fuehrte "Vorrang nach Speicherreihenfolge" ein (der
            # aeltere Plan sieht alles, juengere blockieren ihn nicht), weil
            # bei geteiltem Hangar-Bestand sonst BEIDE Plaene nichts sahen
            # und BEIDE einkauften ("bezahle zu viel Einkaufsmaterialien").
            #
            # SITZUNG 16, WARUM UMGESTELLT WURDE - UND WAS DER ANLASS NICHT
            # WAR. Anlass war ein vermeintlicher Materialverlust: 13'400
            # Thulium Hafnite schienen von einem aelteren Plan aufgebraucht.
            # DAS HAT SICH SPAETER ALS IRRTUM HERAUSGESTELLT - der Nutzer
            # hatte sie mit einem anderen Charakter gebaut und in einem
            # Contract liegen lassen. Das Werkzeug hatte richtig gerechnet.
            # Der Irrtum steht hier, damit niemand aus einer Geschichte
            # Schlüsse zieht, die so nicht passiert ist.
            #
            # DIE REGEL BLEIBT TROTZDEM, aus einem anderen Grund - dem
            # einzigen, der traegt (Nutzer, Sitzung 16 woertlich): "wenn ich
            # einen Plan reserviert habe, dann baue ich ihn IMMER."
            # Reserviert heisst also VERGEBEN. Ein anderer Plan darf mit
            # diesem Material nicht rechnen - egal, welcher Plan aelter ist.
            #
            # WAS ES KOSTET: bei geteiltem Bestand kann Material auf der
            # Kaufliste stehen, das der Nutzer besitzt (es haengt am Schloss
            # eines anderen Plans). Gebundenes ISK, nichts verloren - und er
            # steuert es selbst, indem er das Schloss nur bei Plaenen setzt,
            # die er wirklich baut.
            #
            # Der EIGENE Plan bleibt ausgenommen (oben) - er darf sich nicht
            # selbst aushungern.
            rm = p.get("reserve_map") or {}
            if not rm:
                continue
            # Der eingefrorene Plan traegt den Rezeptbaum (build_mats) - ohne
            # ihn gibt es nichts abzubuchen, dann bleibt die starre Liste
            # stehen. Das ist der SICHERE Rueckfall: lieber zu viel
            # reserviert als zu wenig.
            _snap = ((p.get("frozen") or {}).get("plan_snapshot")) or None
            if _snap:
                try:
                    rm = MainWindowHelpers._reserve_map_mitlaufend(
                        MainWindowHelpers._plan_snapshot_unpack(_snap), rm,
                        p.get("checked_runplan_ts") or {},
                        p.get("assignments") or [],
                        (p.get("frozen") or {}).get("stock_seen_ts"),
                        belegt=MainWindowHelpers._belegt_fuer_plan(p),
                        haken_runs=p.get("checked_runplan_runs"))
                except Exception:
                    rm = p.get("reserve_map") or {}
            if not rm:
                continue
            labels.append(str(p.get("label") or p.get("item_name") or "?"))
            for t, q in rm.items():
                agg[int(t)] = agg.get(int(t), 0) + int(q or 0)
        return agg, labels

    @staticmethod
    def bestand_stand_text(info, jetzt=None):
        """Kopfzeile fuer den Bauplan: wann hat sich der ESI-Bestand zuletzt
        WIRKLICH geaendert - und wann wurde zuletzt nachgesehen.

        NUTZER-WUNSCH (Sitzung 8): "ich will oben im Bauplan sehen, wann die
        letzte erfolgreiche ESI-Aktualisierung war, die Veraenderungen
        festgestellt hat. Das ist wichtig fuer mich."

        Der Unterschied ist der ganze Punkt: `checked_at` heisst nur "ESI hat
        geantwortet", `changed_at` heisst "der Bestand war danach ein anderer".
        Beides steht da, sonst haelt man einen frischen Abruf faelschlich fuer
        eine frische Bestandsaenderung.

        `erstaufzeichnung=True` -> es gab noch keinen Vergleichsstand. Dann
        wird NICHT "zuletzt geaendert" behauptet, sondern ehrlich gesagt, dass
        die Aufzeichnung hier erst beginnt (Arbeitsregel 6: lieber markieren
        als etwas vortaeuschen).
        """
        import time as _t
        from ..sprache import t as _txt      # `t` ist hier kein Name, aber klarer
        jetzt = _t.time() if jetzt is None else jetzt

        def _wann(ts):
            if not ts:
                return None
            alter = max(0.0, jetzt - float(ts))
            uhr = _t.strftime("%d.%m.%Y %H:%M", _t.localtime(float(ts)))
            if alter < 90:
                return uhr + " " + _txt("(just now)")
            if alter < 3600:
                return uhr + " " + _txt("({n} min ago)").format(n=int(alter // 60))
            if alter < 86400:
                return uhr + " " + _txt("({n} h ago)").format(n=int(alter // 3600))
            return uhr + " " + _txt("({n} d ago)").format(n=int(alter // 86400))

        if not info or not info.get("checked_at"):
            return _txt("Stock (ESI): no fetch yet in this installation")
        geprueft = _wann(info.get("checked_at"))
        if info.get("erstaufzeichnung"):
            return _txt("Stock (ESI): last checked {checked} \u00b7 changes are "
                        "recorded from now on").format(checked=geprueft)
        geaendert = _wann(info.get("changed_at"))
        if not geaendert:
            return _txt("Stock (ESI): last checked {checked}").format(checked=geprueft)
        return _txt("Stock (ESI): last detected change {changed} \u00b7 last checked "
                    "{checked}").format(changed=geaendert, checked=geprueft)

    # ---------------------------------------------------------------- #
    # UNTERBIETEN AM AKTIVEN HUB (Nutzer-Wunsch, Sitzung 8)
    # ---------------------------------------------------------------- #
    @staticmethod
    def naechster_tick_darunter(preis):
        """Naechster GUELTIGER EVE-Orderpreis unter `preis` - oder None, wenn
        es keinen gibt.

        EVE erlaubt seit "Broker Relations" nur noch **vier signifikante
        Stellen**; das alte 0,01-Unterbieten ist ungueltig und wuerde vom
        Spiel weggerundet. Die Schrittweite haengt von der Zehnerpotenz ab und
        WECHSELT an der Potenzgrenze - genau dort liegt die Falle:
        ueber 1'000'000 sind es 1'000er-Schritte, direkt darunter 100er.
        Gegenprobe gegen CCPs eigene Beispielliste:
        1'002'000 - 1'001'000 - 1'000'000 - 999'900 - 999'800 - 999'700.

        Untergrenze bleibt 0,01 ISK. Bei sehr billigen Items waeren vier
        signifikante Stellen FEINER als das - dort wird auf 0,01 begrenzt.
        Kann nicht mehr unterboten werden (Preis schon bei 0,01), gibt es
        None zurueck: lieber ehrlich melden als stillschweigend GLEICHziehen,
        denn bei Preisgleichheit steht die aeltere Order vorn.
        """
        import math
        try:
            p = float(preis)
        except (TypeError, ValueError):
            return None
        if p <= 0.01:
            return None
        d = math.floor(math.log10(p))
        tick = 10.0 ** (d - 3)
        stufe = math.floor(round(p / tick, 9)) * tick
        if stufe < p - 1e-9:
            # `preis` lag zwischen zwei Stufen (Altbestand: bestehende Orders
            # durften ihre krummen Preise behalten) - die naechste gueltige
            # Stufe darunter genuegt bereits zum Unterbieten.
            kand = stufe
        else:
            if abs(p - 10.0 ** d) < 1e-9:
                tick = 10.0 ** (d - 4)     # Potenzgrenze: darunter feiner
            kand = p - tick
        # ABWAERTS runden, nicht kaufmaennisch: round() koennte den Wert
        # wieder auf den Ausgangspreis heben und wir stuenden nur gleichauf.
        kand = math.floor(kand * 100.0 + 1e-6) / 100.0
        if kand < 0.01:
            kand = 0.01
        if kand >= p:
            kand = math.floor((p - 0.01) * 100.0 + 1e-6) / 100.0
        return kand if 0.01 <= kand < p else None

    @staticmethod
    def unterbieten_liste(zeilen, sell_min_map, tick_fn):
        """Aus (type_id|None, name) je Zeile die Preisliste bauen.

        Rueckgabe: (preise, notizen) - `preise` hat GENAU so viele Eintraege
        wie `zeilen`, in derselben Reihenfolge.

        DIE REIHENFOLGE IST DER GANZE PUNKT: der Nutzer tabbt die Preise in
        EVEs Verkaufsfenster durch. Faellt eine Zeile aus (Name unbekannt,
        kein Sell-Angebot, Preis nicht unterbietbar), MUSS trotzdem eine
        Zeile ausgegeben werden - sonst verrutscht alles darunter und er
        stellt hunderte Items zum falschen Preis ein. Ausfaelle bekommen
        deshalb eine sichtbare Platzhalterzeile, keine leere.
        """
        from ..sprache import t as _txt
        preise, notizen = [], []
        for tid, name in zeilen:
            if not tid:
                preise.append("?")
                notizen.append(_txt("{name}: name not recognised").format(name=name))
                continue
            sm = (sell_min_map or {}).get(tid)
            if not sm:
                preise.append("?")
                notizen.append(name + ": " + _txt("no sell offer at the hub"))
                continue
            neu = tick_fn(sm)
            if neu is None:
                preise.append("?")
                notizen.append(name + ": " + _txt("{p} cannot be undercut").format(p=f"{sm:.2f}"))
                continue
            preise.append(f"{neu:.2f}")
        return preise, notizen


# Wie lange ein gemerkter Klick einen Job noch an sich binden darf.
# BEGRUENDUNG statt runder Zahl: ein Job wird gestartet, kurz nachdem man
# die Run-Zahl kopiert hat - meist Sekunden, bei einem langen Runplaner-
# Abend auch Stunden. Sieben Tage sind grosszuegig genug, dass niemand
# seinen Fortschritt verliert, und eng genug, dass ein vergessener Klick
# von vorletzter Woche keinen fremden Job mehr schluckt. Die eigentliche
# Bremse ist ohnehin der Plan-Deckel, nicht die Zeit.
KLICK_FENSTER_SEK = 7 * 24 * 3600


def stufe_ist_reaktion(stage) -> bool:
    """Laeuft diese Runplaner-Stufe als REAKTION (ESI-Aktivitaet 9/11)?

    EINE WAHRHEIT FUER EINE REGEL (Befund 21.09.2026). Die Antwort stand
    zweimal im Code, und die zwei Fassungen waren verschieden:
      * `_fill_bauplan_schedule`:  stage.startswith("reaction") or
                                   stage == "unrefined"        - richtig
      * `_frozen_auto_checked`:    stage.startswith("reaction") - FALSCH

    Folge der falschen Fassung: die Stufe "unrefined" galt dort als
    FERTIGUNG, also wurde fuer sie ein Job mit activity_id == 1 verlangt.
    Unrefined-Reaktionen laufen aber als 9/11 - ihre gelieferten Jobs
    wurden deshalb NIE als Fortschritt erkannt. Die Zeilen blieben offen,
    egal wie oft man sie gebaut hat. Nutzer-Bild dazu: "ich muss staendig
    Reactions nachbauen".

    Gemessen: derselbe Job, einmal mit stage "reaction_1" (erkannt: 10 Runs)
    und einmal mit "unrefined" (erkannt: nichts).
    """
    _s = str(stage or "")
    return _s.startswith("reaction") or _s == "unrefined"


def job_zuordnen(jobs, klicks, vergeben, plan_id, plan_runs,
                 fenster_sek=KLICK_FENSTER_SEK, fremde_klicks=None):
    """Welche ESI-Jobs gehoeren DIESEM Plan - belegt durch deine Klicks?

    DIE LOGIK, und sie ist bewusst herum (Skizze 21.09.2026, Punkt 2.1):

        ESI belegt, DASS gebaut wurde. Der Klick belegt, FUER WEN.

    Ein Klick allein bewirkt hier gar nichts. Er wird erst wirksam, wenn ESI
    einen Job mit demselben Item und derselben Run-Zahl meldet, der NACH dem
    Klick gestartet wurde. Ein Fehlklick kann deshalb nichts kaputtmachen -
    ohne passenden Job bleibt er folgenlos. (Meine erste Fassung im Gespraech
    nannte den Klick selbst den Beweis; das war falsch - man kann kopieren
    und den Job dann doch nicht starten.)

    EIN KLICK ORDNET DIE ZEILE ZU, NICHT EINEN JOB (Skizze 2.2): bei "6 x 375"
    klickt man EINMAL und startet SECHS Jobs. Der Klick wird deshalb nicht
    verbraucht. Die Bremse ist der DECKEL: zugeordnet wird nur, solange die
    bereits vergebenen Runs dieses Items unter den Plan-Runs bleiben - wie in
    `delivered_sicher`.

    SCHON VERGEBENE JOBS BLEIBEN, WO SIE SIND. `vergeben` ist {job_id:
    plan_id} ueber ALLE Plaene; ein Job darin wird uebersprungen, egal zu wem
    er gehoert. Genau das macht die Zuordnung stabil: sie wird einmal
    getroffen und nicht bei jedem Abruf neu gewuerfelt.

    AKTIVITAET MUSS PASSEN (wie in `_frozen_auto_checked`): eine Reaktion
    (9/11) darf keine Fertigungs-Zeile abrechnen und umgekehrt.

    Eingaben sind einfache Datentypen, damit das hier ohne Fenster und ohne
    ESI pruefbar bleibt:
      jobs    [{job_id, product_type_id, runs, activity_id, start_ts}]
      klicks  [{tid, runs, ts, reaktion}]
      plan_runs {tid: geplante Runs}   - der Deckel
    Rueckgabe: {job_id: (type_id, runs)} - die neu zuzuordnenden Jobs.

    DER LETZTE KLICK VOR DEM JOBSTART GEWINNT (Nutzer 28.09.2026, "ja alles
    bauen"): `fremde_klicks` sind die Klicks der ANDEREN Plaene. Hat dort
    jemand dasselbe Item mit derselben Run-Zahl SPAETER (aber noch vor dem
    Start) geklickt, gehoert der Job dem anderen Plan - vorher bekam ihn
    der Plan, den man zuerst oeffnete.
    """
    if not jobs or not klicks or plan_id is None:
        return {}
    _fremd = []
    for k in (fremde_klicks or []):
        try:
            _fremd.append((int(k["tid"]), int(k["runs"]), float(k["ts"]),
                           bool(k.get("reaktion"))))
        except (KeyError, TypeError, ValueError):
            continue
    _pr = {int(t): int(r or 0) for t, r in (plan_runs or {}).items()}
    # Runs, die dieser Lauf dem Item schon zugeteilt hat - gegen den Deckel.
    # Was FRUEHERE Laeufe zugeteilt haben, steckt in `vergeben`: jene Jobs
    # werden unten uebersprungen, ihre Runs koennen also nicht doppelt
    # zaehlen.
    _schon = {}
    _klicks = []
    for k in (klicks or []):
        try:
            _klicks.append((int(k["tid"]), int(k["runs"]), float(k["ts"]),
                            bool(k.get("reaktion"))))
        except (KeyError, TypeError, ValueError):
            continue
    if not _klicks:
        return {}
    aus = {}
    # Aelteste Jobs zuerst: wer zuerst gebaut wurde, bekommt den Deckel-Platz.
    # Ohne feste Reihenfolge waere das Ergebnis von der Listenfolge abhaengig
    # und damit nicht reproduzierbar - dieselbe Regel wie in
    # `reprocess.plane_erz_einkauf` (deterministisch, nicht "wie es kommt").
    def _sk(j):
        try:
            return (float(j.get("start_ts") or 0), int(j.get("job_id") or 0))
        except (TypeError, ValueError):
            return (0.0, 0)
    for j in sorted(jobs or [], key=_sk):
        try:
            jid = int(j["job_id"])
            tid = int(j["product_type_id"])
            runs = int(j.get("runs") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if runs <= 0 or jid in (vergeben or {}) or jid in aus:
            continue
        akt = j.get("activity_id")
        ist_reaktion = akt in (9, 11)
        if akt not in (1, 9, 11):
            continue
        try:
            jts = float(j.get("start_ts") or 0)
        except (TypeError, ValueError):
            continue
        # DECKEL: nicht mehr Runs zuordnen, als der Plan fuer dieses Item hat.
        _grenze = _pr.get(tid, 0)
        if _grenze <= 0:
            continue
        if _schon.get(tid, 0) + runs > _grenze:
            continue
        _mein = None
        for k_tid, k_runs, k_ts, k_reaktion in _klicks:
            if k_tid != tid or k_runs != runs:
                continue
            if k_reaktion != ist_reaktion:
                continue
            # Der Job muss NACH dem Klick gestartet sein - ein Klick kann
            # nichts belegen, was vorher schon lief.
            if jts < k_ts or jts - k_ts > float(fenster_sek):
                continue
            _mein = k_ts if _mein is None else max(_mein, k_ts)
        if _mein is None:
            continue
        if any(f_tid == tid and f_runs == runs and f_re == ist_reaktion
               and _mein < f_ts <= jts
               for f_tid, f_runs, f_ts, f_re in _fremd):
            continue          # ein anderer Plan hat danach geklickt
        aus[jid] = (tid, runs)
        _schon[tid] = _schon.get(tid, 0) + runs
    return aus


def job_umstritten(tid, start_ts, umstritten, umstritten_seit=None):
    """Ist DIESER Job umstritten - nicht nur sein Item?

    Ein Item ist umstritten, wenn ein anderer offener Plan es beansprucht.
    Ein JOB ist es nur, wenn so ein Plan beim Start des Jobs schon
    eingefroren war (`umstritten_seit` = fruehester Einfrier-Zeitpunkt je
    Item). Ohne `umstritten_seit`, ohne Startzeit oder ohne Eintrag fuer
    das Item bleibt es bei der Item-Regel - lieber einmal zu viel fragen
    als einen fremden Job anrechnen (Regel 3).
    """
    try:
        _t = int(tid)
    except (TypeError, ValueError):
        return True
    if _t not in {int(x) for x in (umstritten or set())}:
        return False
    if not umstritten_seit or _t not in umstritten_seit or start_ts is None:
        return True
    try:
        return float(umstritten_seit[_t]) <= float(start_ts)
    except (TypeError, ValueError):
        return True


def job_zuordnen_eindeutig(jobs, plan_runs, is_react, vergeben, umstritten,
                           seit_ts, umstritten_seit=None):
    """STUFE C: Jobs, die NUR dieser Plan gebaut haben kann - festgeschrieben.

    WOZU. Bis Stufe B wurde ein gelieferter Job bei JEDEM Abruf neu geraten
    (Item + Aktivitaet + Zeitpunkt). Solange nur ein Plan das Item baut,
    faellt die Raterei immer gleich aus - bis der Nutzer einen ZWEITEN Plan
    mit demselben Zwischenprodukt anlegt. Von da an ist das Item
    "umstritten", `delivered_sicher` verwirft seine Runs, und der
    Fortschritt, den er laengst gebaut hat, verschwindet aus dem alten Plan.
    Das ist sein Bild "es gehen bei anderen Plaenen die Runs zurueck".

    DIE HEILUNG ist nicht eine bessere Vermutung, sondern ein GEDAECHTNIS:
    solange es keinen Streit gibt, ist die Zuordnung eindeutig - und genau
    dann wird sie in `job_zuordnung` geschrieben. Ein spaeter angelegter
    Plan kann sie nicht mehr kippen (`INSERT OR IGNORE`, die erste
    Entscheidung gewinnt). Was heute stimmt, bleibt morgen stehen.

    WAS DAS NICHT IST: ein Beweis wie der Klick. Es ist die Feststellung
    "zum Zeitpunkt der Lieferung wollte kein anderer Plan dieses Item".
    Deshalb aendert sich am RECHNEN nichts: eindeutige Items zaehlten in
    `delivered_sicher` schon bisher voll mit (sie waren ja nicht
    umstritten). Festgeschrieben wird nur, WEM sie gehoeren - die
    Einkaufsliste wird davon in keinem Fall kleiner als vorher.

    Die Sicherungen, dieselben wie in `job_zuordnen`:
      * der Plan muss das Item ueberhaupt bauen (`plan_runs` > 0),
      * die Aktivitaet muss zur Stufe passen (`is_react` je Item),
      * der Job muss NACH `seit_ts` fertig geworden sein (Einfrier-
        Zeitpunkt - dieselbe Grenze wie `_frozen_auto_checked`),
      * DECKEL auf die Plan-Runs,
      * schon vergebene Jobs bleiben, wo sie sind,
      * aelteste Jobs zuerst, damit das Ergebnis nicht an der
        Listenreihenfolge haengt.

    Eingaben sind einfache Datentypen (ohne Fenster und ohne ESI pruefbar):
      jobs   [{job_id, product_type_id, runs, activity_id, fertig_ts}]
    Rueckgabe: {job_id: (type_id, runs)}.
    """
    if not jobs or not plan_runs:
        return {}
    try:
        _seit = float(seit_ts)
    except (TypeError, ValueError):
        return {}
    _pr = {int(t): int(r or 0) for t, r in (plan_runs or {}).items()}
    _um = {int(t) for t in (umstritten or set())}
    _schon = {}
    aus = {}

    def _sk(j):
        try:
            return (float(j.get("fertig_ts") or 0), int(j.get("job_id") or 0))
        except (TypeError, ValueError):
            return (0.0, 0)
    for j in sorted(jobs or [], key=_sk):
        try:
            jid = int(j["job_id"])
            tid = int(j["product_type_id"])
            runs = int(j.get("runs") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if runs <= 0 or jid in (vergeben or {}) or jid in aus:
            continue
        # ZEIT ENTSCHEIDET (26.09.2026): ein anderer Plan, der erst nach
        # dem Start dieses Jobs eingefroren wurde, kann ihn nicht gebaut
        # haben - dann ist der Job eindeutig, obwohl das Item strittig ist.
        if job_umstritten(tid, j.get("start_ts"), _um, umstritten_seit):
            continue          # umstritten: kein Gedaechtnis, nur Vorsicht
        grenze = _pr.get(tid, 0)
        if grenze <= 0:
            continue
        akt = j.get("activity_id")
        if (is_react or {}).get(tid):
            if akt not in (9, 11):
                continue
        elif akt != 1:
            continue
        try:
            fts = float(j.get("fertig_ts") or 0)
        except (TypeError, ValueError):
            continue
        if fts < _seit:
            continue
        if _schon.get(tid, 0) + runs > grenze:
            continue
        aus[jid] = (tid, runs)
        _schon[tid] = _schon.get(tid, 0) + runs
    return aus


def laufend_verbraucht(build_runs, build_mats, laufend):
    """Wie viel von jedem Material steckt schon in LAUFENDEN Jobs?

    WOZU (Nutzer-Befund 25.09.2026: "es fehlen anscheinend Silicon Diborite,
    das ist aber neu, die haben nicht immer gefehlt"). Gemessen an seinen
    Zahlen: der Plan braucht 22'932 Silicon Diborite, im Hangar liegen noch
    9'913, es fehlen 13'019. Gleichzeitig laufen 143 von 194 Runs Titanium
    Carbide, und jeder davon frisst laut SDE 100 Silicon Diborite - 14'300
    Stueck, die im Spiel also laengst weg sind.

    Das ist KEIN Fehler in der Rechnung, sondern eine Luecke in der
    AUSKUNFT: die Einkaufsliste zaehlt den Bedarf eines laufenden Jobs
    weiter mit (sein Erzeugnis ist ja noch nicht da), und der Nutzer sieht
    nur "fehlt". Nutzer-Entscheid: die Rechnung bleibt, wie sie ist (lieber
    zu viel als zu wenig, Regel 3) - aber die Zeile sagt jetzt, warum.

    Gerechnet wird mit denselben Zahlen wie `restbedarf_map`: die Mengen in
    `build_mats[t]` gelten fuer ALLE `build_runs[t]` Runs, also anteilig.
    ABGERUNDET, und die laufenden Runs sind auf die Plan-Runs gedeckelt -
    eine Auskunft darf lieber zu wenig behaupten als zu viel.

    Rein und ohne Fenster pruefbar. `laufend` ist {type_id: laufende Runs}.
    Rueckgabe: {material_id: Menge, die in laufenden Jobs steckt}.
    """
    aus = {}
    for t, mats in (build_mats or {}).items():
        try:
            runs_t = int((build_runs or {}).get(t, 0) or 0)
            lauf_t = int((laufend or {}).get(t, 0) or 0)
        except (TypeError, ValueError):
            continue
        if runs_t <= 0 or lauf_t <= 0:
            continue
        lauf_t = min(lauf_t, runs_t)
        for m in (mats or []):
            try:
                _mid, _jq = int(m[0]), int(m[1])
            except (TypeError, ValueError, IndexError):
                continue
            if _jq <= 0:
                continue
            aus[_mid] = aus.get(_mid, 0) + (_jq * lauf_t) // runs_t
    return {k: v for k, v in aus.items() if v > 0}


def offene_job_fragen(jobs, plan_runs, is_react, vergeben, umstritten,
                      seit_ts, umstritten_seit=None):
    """STUFE C, Teil 2: die Jobs, bei denen die Zuordnung WIRKLICH offen ist.

    Uebrig bleibt genau der Fall, den weder ein Klick noch die
    Eindeutigkeit loesen kann: ZWEI gespeicherte Plaene bauen dasselbe Item,
    ESI meldet einen gelieferten Job, und niemand kann sagen, zu wem er
    gehoert. Bisher zaehlte er deshalb fuer GAR KEINEN Plan (sicher, aber
    man kauft dauerhaft zu viel). Nutzer-Entscheid 24.09.2026: **einmal
    fragen und die Antwort an der job_id merken.**

    Was hier NICHT auftaucht (und warum):
      * Jobs mit Zuordnung - die Frage ist beantwortet, auch wenn die
        Antwort "keiner" war (`store.PLAN_KEINER`);
      * Jobs, deren Aktivitaet nicht zur Stufe passt - die kann der Plan
        gar nicht gebaut haben;
      * Jobs von vor dem Einfrieren;
      * ein Job, dessen Runs ALLEIN schon mehr sind, als der Plan fuer das
        Item ueberhaupt vorhat - der stammt sicher von woanders.

    Rein und ohne Fenster pruefbar. Rueckgabe: Liste
    [{job_id, type_id, runs, fertig_ts}], aelteste zuerst - damit die
    Reihenfolge im Dialog nicht an der Listenfolge von ESI haengt.
    """
    if not jobs or not plan_runs:
        return []
    try:
        _seit = float(seit_ts)
    except (TypeError, ValueError):
        return []
    _pr = {int(t): int(r or 0) for t, r in (plan_runs or {}).items()}
    _um = {int(t) for t in (umstritten or set())}
    raus = []
    for j in (jobs or []):
        try:
            jid = int(j["job_id"])
            tid = int(j["product_type_id"])
            runs = int(j.get("runs") or 0)
        except (KeyError, TypeError, ValueError):
            continue
        if runs <= 0 or jid in (vergeben or {}):
            continue
        # dieselbe Zeit-Regel wie in `job_zuordnen_eindeutig`: was dort
        # eindeutig ist, wird hier nicht gefragt.
        if not job_umstritten(tid, j.get("start_ts"), _um, umstritten_seit):
            continue          # eindeutig - dafuer gibt es keine Frage
        grenze = _pr.get(tid, 0)
        if grenze <= 0 or runs > grenze:
            continue
        akt = j.get("activity_id")
        if (is_react or {}).get(tid):
            if akt not in (9, 11):
                continue
        elif akt != 1:
            continue
        try:
            fts = float(j.get("fertig_ts") or 0)
        except (TypeError, ValueError):
            continue
        if fts < _seit:
            continue
        raus.append({"job_id": jid, "type_id": tid, "runs": runs,
                     "fertig_ts": fts, "laeuft": bool(j.get("laeuft"))})
    raus.sort(key=lambda d: (d["fertig_ts"], d["job_id"]))
    return raus


def delivered_sicher(geliefert, plan_runs, umstritten, belegt=None):
    """Von den ESI-gelieferten Runs NUR das, was diesem Plan sicher gehoert.

    WOZU (Befund 21.09.2026, nachgestellt): `_frozen_auto_checked` ordnet
    einen gelieferten Job allein ueber Item + Aktivitaet + Zeitpunkt zu -
    ESI sagt naemlich NICHT, zu welchem Bauplan ein Job gehoert. Bauen zwei
    eingefrorene Plaene dieselbe Reaktion, bekommen BEIDE dieselben Runs
    angerechnet. In der Messung: ein Job ueber 2'250 Runs, Plan A braucht
    2'250 (richtig), Plan B nur 400 - und bekam trotzdem 2'250 gutge-
    schrieben. Beider Einkaufsliste fiel auf leer, obwohl Plan B nie etwas
    gebaut hatte. Nutzer-Bild dazu: "ich muss staendig Reactions nachbauen,
    es gehen aber bei anderen Plaenen die Runs zurueck".

    DIE TRENNUNG, die diese Funktion durchzieht: eine GERATENE Zuordnung
    darf die ANZEIGE steuern (Zeile einfaerben, Punkt setzen) - dort kostet
    ein Irrtum nichts. Sie darf NICHT den Restbedarf steuern: dort kostet
    ein Irrtum Material, weil die Einkaufsliste zu klein wird und der
    Nutzer vor dem Reaktor steht (Regel 3). Deshalb rechnet die
    Einkaufsliste ab jetzt mit DIESER Karte, die Anzeige weiter mit der
    vollen.

    Zwei Sicherungen:
      1. DECKEL auf die Plan-Runs - kein Job kann mehr abbuchen, als der
         Plan ueberhaupt vorhat.
      2. UMSTRITTENE Items zaehlen GAR NICHT. Beansprucht ein anderer
         gespeicherter Plan dasselbe Item, laesst sich der Job nicht
         zuordnen; dann lieber zu viel einkaufen als zu wenig.

    `belegt` HEBT SICHERUNG 2 AUF - aber nur, wo es etwas zu belegen gibt
    (Stufe B, 21.09.2026): {type_id: Runs} aus Jobs, die diesem Plan
    nachweislich gehoeren, weil du ihre Zeile angeklickt hast und ESI
    danach den passenden Job gemeldet hat. Diese Runs sind keine Vermutung
    mehr, also darf der Streit sie nicht mehr verwerfen - sonst wuerde
    ausgerechnet der belegte Fortschritt verschenkt und du kauftest dauerhaft
    zu viel. Der DECKEL gilt auch fuer sie.

    Rein und ohne Fenster pruefbar. `umstritten` ist die Menge der
    type_ids, die mindestens ein ANDERER Plan ebenfalls beansprucht.
    """
    aus = {}
    _bel = {int(t): int(n or 0) for t, n in (belegt or {}).items() if n}
    for t, n in (geliefert or {}).items():
        t = int(t)
        if t in (umstritten or set()):
            # Umstritten: nur was BELEGT ist, zaehlt - der Rest ist geraten.
            _b = _bel.get(t, 0)
            _d = int((plan_runs or {}).get(t, 0) or 0)
            if _b > 0 and _d > 0:
                aus[t] = min(_b, _d)
            continue
        n = int(n or 0)
        if n <= 0:
            continue
        deckel = int((plan_runs or {}).get(t, 0) or 0)
        if deckel <= 0:
            continue
        aus[t] = min(n, deckel)
    return aus


def fehlt_spalte(fehlt_hangar, fehlt_live):
    """Zahl fuer die Spalte "Missing" im Materialien-Reiter: (menge, von_live).

    Nutzer 27.09.2026 (Basilisk x28): Mexallon "Owned 1.98M, Missing -",
    daneben rot "counted 0 - 748'440 missing for the remaining runs". Die
    Spalte rechnete Benoetigt minus HANGAR, der Status mit dem Bestand, der
    fuer DIESEN Plan zaehlt (andere Plaene haben reserviert). Die Spalte log
    also in die gefaehrliche Richtung - "genug da" -, waehrend die
    Einkaufsliste richtig kaufte. Jetzt zeigt sie mindestens den
    Live-Fehlbedarf; `von_live` sagt, dass die Zahl von dort kommt.
    """
    _h = max(0, int(fehlt_hangar or 0))
    _l = max(0, int(fehlt_live or 0))
    if _l > _h:
        return _l, True
    return _h, False


def inv_kaufmenge(plan_fehlt, benoetigt, bestand):
    """Kaufmenge fuer Datacores/Decryptoren auf der Einkaufsliste.

    Nutzer 27.09.2026: "ich habe hier Decryptoren als Bestand, aber das Tool
    legt mir diese in die Einkaufsliste" (Einkaufsfenster: Datacore 105
    benoetigt, 1'000 besessen, 105 fehlend). `plan_fehlt` ist `inv_buy` des
    Plans - beim EINGEFRORENEN Plan der Stand vom Einfrier-Tag; war der
    Bestand da nicht geladen, bleibt dort fuer immer der volle Bedarf stehen.
    Jetzt zaehlt zusaetzlich der Bestand, den der Materialien-Reiter zeigt:
    gekauft wird hoechstens, was nach Abzug des Bestands wirklich fehlt -
    und nie mehr, als der Plan sagt.
    """
    _f = max(0, int(plan_fehlt or 0))
    _rest = max(0, int(benoetigt or 0) - int(bestand or 0))
    return min(_f, _rest)


def restbedarf_map(build_runs, build_mats, delivered=None):
    """Was die NOCH OFFENEN Runs an Material brauchen.

    Rueckgabe: (rem, need)
      rem  = {type_id: noch offene Runs}   (plan_runs - geliefert, >= 0)
      need = {type_id: Menge fuer genau diese Runs}

    WARUM ALS EIGENE FUNKTION (Sitzung 16, Nutzer-Befund): die
    Einkaufsliste rechnete mit der VOLLEN Planmenge, waehrend die
    Fehlbedarfs-Pruefung laengst nur die Restmenge nahm. Ergebnis: der
    Nutzer sah "absurd viele Materialien", die er zum Teil schon in die
    naechste Stufe verbaut hatte - "ich will ja nicht mehr einkaufen als
    noetig". Beide lesen jetzt DIESELBE Rechnung.

    Anteilig gerundet (ceil): wer 153 von 200 Runs offen hat, braucht auch
    nur 153/200 des Materials - aufgerundet, damit nie zu wenig dasteht.
    """
    import math
    rem = {t: max(0, int(r or 0) - int((delivered or {}).get(t, 0) or 0))
           for t, r in (build_runs or {}).items()}
    need = {}
    for t, mats in (build_mats or {}).items():
        runs_t = int((build_runs or {}).get(t, 0) or 0)
        rem_t = rem.get(t, 0)
        if runs_t <= 0 or rem_t <= 0:
            continue
        for m, jq in mats:
            need[m] = need.get(m, 0) + math.ceil(int(jq) * rem_t / runs_t)
    return rem, need


def fehlbedarf_vorschau(build_runs, build_mats, out_qty_map, delivered,
                        live_stock, im_bestand=None):
    """Was wird beim Abarbeiten der RESTLICHEN Runs fehlen? (pur, testbar)

    NUTZER-VORFAELLE (Sitzung 8): 290 Ferrofluid, 805 Ferrogel, dann Hexite
    und wieder Ferrofluid - immer derselbe Mechanismus: der eingefrorene
    Plan haelt per max(eingefroren, live) am Einfrier-Bestand fest (bewusst,
    damit Verbrauchtes die Einkaufsliste nicht wieder aufreisst), ist aber
    BLIND dafuer, wenn Bestand real verschwindet (verkauft, anderer Bau,
    beim Einfrieren als Pipeline gezaehlt). Diese Vorschau rechnet gegen den
    ROHEN Ist-Bestand (live_stock = aktuelles Lager + Pipeline, NICHT der
    max-Merge) und beantwortet: "wenn ich jetzt alle restlichen Jobs starte,
    was fehlt mir dann - und wie viel?"

    Je Bau-Item: remaining = max(0, plan_runs - geliefert). Der Rest-Bedarf
    je Zutat wird aus den EXAKTEN Planmengen (build_mats) anteilig
    hochgerechnet - ceil je Verbraucher, also hoechstens 1 Stueck zu streng
    pro Verbraucher, nie zu lasch. Die Rest-Produktion eigener Runs wird
    gutgeschrieben (3 restliche Ferrogel-Runs decken den Ferrogel-Bedarf,
    brauchen aber selbst Ferrofluid + Hexite - genau die Kaskade des
    Nutzers).

    Rueckgabe: [(type_id, fehlt, rest_bedarf, da, rest_produktion)],
    absteigend nach Fehlmenge; leer = alles deckt sich."""
    rem, need = restbedarf_map(build_runs, build_mats, delivered)
    # ZWEI ERLEDIGT-BEGRIFFE (Nutzer 30.09.2026: "kann man die Nebenwirkung
    # verhindern?"). `delivered` (inkl. Hand-Haken) sagt, welche Runs ihre
    # ZUTATEN schon verbraucht haben. Ob ihr ERZEUGNIS schon im Bestand
    # steht, sagt nur ESI: `im_bestand` = Runs, deren Output geliefert oder
    # als Pipeline in `live_stock` steckt. Ein abgehakter Run, den ESI noch
    # nicht kennt, zaehlt deshalb weiter als kommende Produktion - sonst
    # fehlte sein Erzeugnis kurz, bis der naechste Abruf ihn sieht.
    # Ohne `im_bestand`: wie bisher dieselbe Karte fuer beides.
    rem_p = (restbedarf_map(build_runs, {}, im_bestand)[0]
             if im_bestand is not None else rem)
    out = []
    for m, bedarf in need.items():
        prod = rem_p.get(m, 0) * int((out_qty_map or {}).get(m, 1) or 1)
        da = int((live_stock or {}).get(m, 0) or 0)
        bilanz = da + prod - bedarf
        if bilanz < 0:
            out.append((m, -bilanz, bedarf, da, prod))
    out.sort(key=lambda x: -x[1])
    return out


def war_gedeckt_status(rest_fehlt, gedeckt_einmal, tids):
    """Welche Materialien waren SCHON EINMAL gedeckt und fehlen JETZT?

    NUTZER-VORFALL (Sitzung 12): "Wie kann Fehlbedarf entstehen, wenn ich
    doch einmal alles komplett eingekauft habe? Das sollte nicht moeglich
    sein." - Richtig. Wenn es doch passiert, ist es KEIN Rechenartefakt,
    sondern ein echter Vorfall: versehentlich weggeworfen, anderweitig
    verbaut, verkauft.

    Genau das unterscheidet diese Funktion. Ein Material, das NIE gedeckt
    war, ist schlicht noch nicht gekauft ("kaufen"). Eines, das gedeckt WAR
    und jetzt fehlt, verdient eine andere Aussage - und nur dort darf die
    Einkaufsliste ueberhaupt wieder wachsen (und auch dann nur auf Klick:
    "gekauft ist gekauft").

    rest_fehlt:      {type_id: fehlende_menge} aus `fehlbedarf_vorschau`
    gedeckt_einmal:  Menge/Liste der type_ids, die frueher gedeckt waren
    tids:            alle type_ids, die der Plan ueberhaupt kennt

    Rueckgabe: (neu_gedeckt, verloren)
      neu_gedeckt = type_ids, die JETZT gedeckt sind und gemerkt werden
                    sollen (Aufrufer legt sie zum Bestand dazu)
      verloren    = {type_id: fehlende_menge} - war gedeckt, fehlt jetzt
    """
    _fehlt = {int(k): int(v) for k, v in (rest_fehlt or {}).items()}
    _frueher = {int(x) for x in (gedeckt_einmal or ())}
    _alle = {int(x) for x in (tids or ())}
    neu_gedeckt = {t for t in _alle if t not in _fehlt}
    verloren = {t: q for t, q in _fehlt.items() if t in _frueher}
    return neu_gedeckt, verloren


def verlust_stabil(verlust_roh, seit, jetzt, mindestdauer=3600.0):
    """Nur Verluste melden, die LANGE GENUG bestehen.

    WARUM (Nutzer, Sitzung 12): "ESI-Daten werden ca. stuendlich geliefert."
    Fuer ASSETS stimmt das - CCP cacht sie bis zu einer Stunde. Wer gerade
    Material gekauft hat, sieht es in ESI also noch nicht: der Bestand
    erscheint zu niedrig, und ein frisch gekauftes Material saehe aus wie
    ein Verlust. Ein Fehlalarm direkt nach dem Einkauf waere das Gegenteil
    von hilfreich - er wuerde zum Doppelkauf verleiten.

    Deshalb zaehlt hier die DAUER: ein Fehlbetrag wird erst gemeldet, wenn
    er die Asset-Cachezeit ueberdauert hat. Was nach einem Kauf wieder
    verschwindet, war nie ein Verlust.

    verlust_roh:   {type_id: menge} - was die Rechnung JETZT als fehlend sieht
    seit:          {type_id: zeitstempel} - seit wann schon (wird gepflegt)
    jetzt:         aktueller Zeitstempel
    mindestdauer:  Sekunden, die ein Fehlbetrag bestehen muss (Vorgabe 1 h)

    Rueckgabe: (zu_melden, seit_neu)
    """
    _roh = {int(k): int(v) for k, v in (verlust_roh or {}).items()}
    _seit = {int(k): float(v) for k, v in (seit or {}).items()}
    # Verschwundene Fehlbetraege vergessen - sonst zaehlte eine alte,
    # laengst behobene Luecke spaeter wieder mit.
    seit_neu = {t: _seit.get(t, jetzt) for t in _roh}
    zu_melden = {t: q for t, q in _roh.items()
                 if (jetzt - seit_neu[t]) >= mindestdauer}
    return zu_melden, seit_neu


def fertig_menge(plan_runs, geliefert, laufend):
    """Wie viele Runs eines Items gelten als ERLEDIGT - gedeckelt auf den Plan.

    NUTZER-VORFALL (Sitzung 13, Screenshot): eingefrorener Plan vom 28.08.,
    Quantum Microprocessor. Der Runplaner verlangte 7'321 Runs, obwohl der
    Materialien-Reiter daneben 3'700 vorhanden und nur 3'661 fehlend auswies.
    Er hatte die Haelfte laengst gebaut - der eingefrorene Plan wusste nur
    nichts davon.

    Gezaehlt wird NUR, was ESI als abgeliefert (`_bd_runplan_delivered`) oder
    als gerade laufend (`_bd_active_jobs_map`) gesehen hat - also Ausführung
    DIESES Plans. Bewusst NICHT der Lagerbestand: der kann gekauft, gelootet
    oder fuer einen anderen Plan gedacht sein.

    Der Deckel ist noetig, weil man MEHR bauen kann als geplant; ohne ihn
    zeigte die naechste Zuteilung negative Runs.
    """
    return max(0, min(int(geliefert or 0) + int(laufend or 0),
                      int(plan_runs or 0)))


def rest_und_budget(runs, budget):
    """Eine Zuteilung gegen das Erledigt-Budget verrechnen.

    Gibt (offene Runs dieser Zuteilung, verbleibendes Budget) zurueck. Die
    Zuteilungen eines Items werden der Reihe nach abgearbeitet; die Summe der
    offenen Runs bleibt dadurch exakt Plan minus Erledigt - es geht nichts
    verloren und nichts wird doppelt abgezogen.

    EINE WAHRHEIT: der Runplaner-Baum rechnet nicht selbst, er ruft das hier.
    """
    r = max(0, int(runs or 0))
    b = max(0, int(budget or 0))
    weg = min(b, r)
    return r - weg, b - weg


def budget_eigene_zuerst(zeilen, budget, eigene_lauf):
    """Erledigt-Budget auf die Runplaner-Zeilen verteilen - LAUFENDE JOBS
    ZUERST BEI DEM CHARAKTER, DER SIE FAEHRT.

    Nutzer 29.09.2026 (Screenshot Basilisk): Nonlinear Metamaterials, 34 Runs
    bei Banana Motor UND 34 bei Peanut Motor. Nur Peanut Motor hatte gebaut -
    trotzdem bekam Banana Motors Zeile den blauen Lauf-Punkt. Das Budget war
    je ITEM und wurde der Reihe nach verbraucht; Banana stand in der Liste
    vor Peanut und nahm sich die 34 laufenden Runs von Peanut.

    `zeilen` = [(schluessel, tid, plan_runs, charakter_name)] in der
    Reihenfolge des Baums, `budget` = {tid: gedeckte Runs (geliefert +
    laufend)}, `eigene_lauf` = {tid: {charakter_name: laufende Runs}}.
    Rueckgabe ({schluessel: gedeckte Runs}, Rest-Budget).
    Runde 1: jeder Charakter bekommt seine EIGENEN laufenden Runs.
    Runde 2: der Rest (geliefert, ohne Charakter) der Reihe nach wie bisher.
    Die Summe bleibt exakt wie vorher - es wird nur anders zugeteilt.
    """
    rest = {int(t): max(0, int(v or 0)) for t, v in (budget or {}).items()}
    eigen = {int(t): {str(c): max(0, int(r or 0)) for c, r in (m or {}).items()}
             for t, m in (eigene_lauf or {}).items()}
    gedeckt = {}
    for sk, tid, runs, cname in zeilen:
        tid = int(tid)
        own = eigen.get(tid, {}).get(str(cname), 0)
        take = min(own, max(0, int(runs or 0)), rest.get(tid, 0))
        if take > 0:
            gedeckt[sk] = take
            rest[tid] -= take
            eigen[tid][str(cname)] = own - take
    for sk, tid, runs, _cname in zeilen:
        tid = int(tid)
        offen = max(0, int(runs or 0)) - gedeckt.get(sk, 0)
        take = min(offen, rest.get(tid, 0))
        if take > 0:
            gedeckt[sk] = gedeckt.get(sk, 0) + take
            rest[tid] -= take
    return gedeckt, rest


def haken_nachtragen(zeilen, gehakt, erledigt):
    """Welche Zeilen bekommen einen Haken ZURUECK (nach einer Umverteilung)?

    Nutzer 29.09.2026: er hakte Peanut Motors Nonlinear-Zeile ab - und
    Banana Motors Zeile bekam einen gruenen Haken, den er nie gesetzt hatte.
    Die Regel "abgehakte Runs je Item ueberleben eine Umverteilung" gab die
    gemerkten Runs der ERSTEN offenen Zeile, bevor die Zeile, die den Haken
    wirklich traegt, sie verbraucht hatte.

    `zeilen` = [(schluessel, item_schluessel, runs)], `gehakt` = Menge der
    gesetzten Haken, `erledigt` = {item_schluessel: abgehakte Runs}.
    Erst verbrauchen die WIRKLICH gehakten Zeilen ihre Runs, nur was dann
    uebrig ist, wandert an offene Zeilen (nur ganze Zeilen). Rueckgabe: die
    Schluessel, die nachgetragen werden.
    """
    rest = {k: max(0, int(v or 0)) for k, v in (erledigt or {}).items()}
    for sk, ik, runs in zeilen:
        if sk in gehakt:
            rest[ik] = max(0, rest.get(ik, 0) - max(0, int(runs or 0)))
    neu = []
    for sk, ik, runs in zeilen:
        r = max(0, int(runs or 0))
        if sk not in gehakt and r > 0 and rest.get(ik, 0) >= r:
            neu.append(sk)
            rest[ik] -= r
    return neu


def plan_fortschritt_runs(plan_runs, geliefert, laufend=None, fremd=None,
                          plan_id=None, laufend_gewicht=0.5):
    """Fortschritt eines Bauplans in RUNS statt in Positionen.
    Gibt (erledigte Runs, geplante Runs) zurueck - beides als float.

    NUTZER 22.09.2026: "es fuehlt sich an, als gaebe es am Anfang kaum
    Fortschritt und dann springt der Fortschrittsbalken von 20 % auf 100 %
    und fertig."

    WARUM ER SPRANG: gezaehlt wurden POSITIONEN - eine Stufe galt als
    erledigt, sobald EIN Job dafuer geliefert war. Ein Plan mit 30 Positionen
    bewegt sich damit in 3,3-%-Spruengen, und eine Position mit 52 Runs sieht
    genauso weit aus wie eine mit 2. Jetzt zaehlen die RUNS: jeder einzelne
    Job schiebt den Balken ein Stueck.

    LAUFENDE JOBS ZAEHLEN HALB (`laufend_gewicht`). Gestartet ist nicht
    fertig - ein 4-Tage-Job darf nicht sofort als erledigt gelten. Aber er
    ist auch nicht nichts: der Nutzer hat Material verbraucht und einen Slot
    belegt. Halb heisst auch: der Balken geht beim Abliefern noch einmal
    HOCH, nie zurueck.

    "FEST ZUGEORDNET" (seine Worte): `fremd` ist {job_id: plan_id} aus der
    Zuordnungs-Tabelle. Ein Job, der nachweislich einem ANDEREN Plan gehoert,
    zaehlt hier nicht mit - sonst steigt der Balken zweier Plaene an
    demselben Job. Ohne Eintrag bleibt es bei der bisherigen Zaehlung
    (die Karte meldet solche Faelle als "shared").

    DECKEL JE POSITION: mehr als geplant kann eine Position nicht beitragen,
    sonst gliche ein einzelner grosser Job einen ganzen Plan aus.
    """
    def _i(v):
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0
    ziel = {int(t): _i(r) for t, r in (plan_runs or {}).items() if _i(r) > 0}
    if not ziel:
        return 0.0, 0.0
    _fremd = fremd or {}
    _pid = None if plan_id is None else str(plan_id)

    def _summe(jobs):
        aus = {}
        for j in (jobs or []):
            _t = j.get("product_type_id")
            if _t is None or int(_t) not in ziel:
                continue
            _jid = j.get("job_id")
            if _jid is not None:
                _gehoert = _fremd.get(int(_jid))
                if _gehoert is not None and str(_gehoert) != _pid:
                    continue      # belegt fremd - nicht meiner
            aus[int(_t)] = aus.get(int(_t), 0) + _i(j.get("runs"))
        return aus

    _gel = _summe(geliefert)
    _lauf = _summe(laufend)
    erledigt = 0.0
    for _t, _soll in ziel.items():
        _g = min(_soll, _gel.get(_t, 0))
        # Der laufende Rest fuellt nur auf, was die Lieferungen offen lassen.
        _l = min(_soll - _g, _lauf.get(_t, 0))
        erledigt += _g + _l * float(laufend_gewicht)
    return erledigt, float(sum(ziel.values()))


def eigene_kopie_lage(noetig, user_runs, esi_runs, esi_kopien=None):
    """Blaupausen-Lage eines Endprodukts mit Haken "Eigene BPC":
    {"copies", "runs"} - oder None, wenn die Kopiengroesse UNBEKANNT ist.

    NUTZER-BEFUND 21.09.2026 (Multi-Bauplan, Runplaner Stufe "End product"):
    "es werden zwar die bpc copy runs vollstaendig aufgeteilt, doch werden
    nicht alle charaktere verwendet und somit steht 51 Tage Bauzeit."
    NACHGESTELLT (aa387, nicht hergeleitet): Flycatcher 52 Runs, 13 eigene
    Kopien a 4 Runs. Hier stand frueher

        je_bpc = max(1, int(obpc_runs.get(tid, 0) or 0) or noetig)

    - ohne getippte "Runs/BPC" wurde also die GESAMTE Run-Zahl als EINE
    Kopie angenommen. Eine Kopie heisst EIN gleichzeitiger Job, ein Job
    heisst EIN Slot, also EIN Charakter und alles hintereinander: aus
    3,97 Tagen wurden 51,63. Dabei wusste der Blaupausen-Cache die Wahrheit
    laengst - der Runs-Deckel des Runplaners kam bereits von dort (die
    Jobs liefen mit 4 Runs), nur die KOPIENZAHL wurde daneben geraten und
    ueberschrieb die echte.

    DIE REGEL DAHINTER (Sitzung 21.09.2026): eine geratene Zahl darf die
    Anzeige steuern, nie die Rechnung. Hier wird nichts mehr geraten:
      1. die kleinste eigene Kopie aus dem ESI-Cache (`esi_runs`, dieselbe
         Quelle, aus der `_bpc_runs_by_tid` schon den Runs-Deckel nimmt -
         EINE Wahrheit);
      2. nur wenn der Cache sie NICHT kennt: das Feld "Runs/BPC"
         (`user_runs`);
      3. sonst None: unbekannt heisst unbegrenzt (wie bei T1/BPO), NICHT
         "eine Riesenkopie".

    REIHENFOLGE GETAUSCHT (Nutzer 28.09.2026, Multiplan 1, Flycatcher: der
    Runplaner wollte 10 x 1 Run je Welle, im Hangar liegen 13 Kopien a 4
    Runs): "man will IMMER die gesamte Blueprint verbrauchen ... ALLE Runs
    durchziehen ... beim Endprodukt, NUR beim Endprodukt". GEMESSEN in
    seiner settings.json: `own_bpc_runs_je_ende` Flycatcher = 1, Stork = 1 -
    das Feld schlug die echte Kopiengroesse, daraus wurde "13 x 1". Kennt
    der Cache die Kopie, gilt jetzt SIE; das Feld ist dann gesperrt.
    Die Kopienzahl ist, was der Plan braucht (`ceil`), gedeckelt auf die
    Stueckzahl, die wirklich im Hangar liegt (`esi_kopien`) - mehr Jobs
    als Blaupausen kann niemand fahren.
    """
    def _i(v):
        try:
            return int(v or 0)
        except (TypeError, ValueError):
            return 0
    n = max(1, _i(noetig))
    je = _i(esi_runs)
    if je < 1:
        je = _i(user_runs)
    if je < 1:
        return None
    kop = -(-n // je)                     # ceil
    hab = _i(esi_kopien)
    if hab >= 1:
        kop = min(kop, hab)
    return {"copies": max(1, kop), "runs": je}


def sell_preis_ziel_modus(ziel_preis, undercut_preis):
    """Welcher Preis gilt im ZIEL-PREIS-MODUS fuer EINE Zeile - und wie
    heisst diese Zahl ehrlich?

    NUTZER-WUNSCH (22.09.2026): "Also wenn der Zielpreis unter dem
    aktuellen Undercut-Preis liegen wuerde, sollten wir vielleicht den
    Undercut-Preis fuer diese spezifischen Einzelfaelle nehmen."

    Er hat recht, und der Grund ist reine Arithmetik: der Ziel-Preis aus
    `_optimal_sell_price` kennt den Markt gar nicht, er rechnet nur
    Einkauf + Ziel-Marge + Gebuehren. Liegt der billigste Sell am Hub
    HOEHER als dieser Ziel-Preis, dann verschenkt die Ziel-Rechnung
    genau die Differenz: die Order verkauft trotzdem sofort (sie ist ja
    die billigste), nur eben unnoetig billig. Sein Beispiel: Triglavian
    Encryption Methods, Ziel 196'745 gegen Markt 234'700 - rund 38'000
    ISK je Stueck verschenkt, bei 12 % Ziel-Marge.

    Der hoehere der beiden Preise ist deshalb IMMER mindestens so gut:
      * Ziel >= Undercut  -> Ziel-Preis (der Markt ist billiger als noetig,
        die Ziel-Marge ist die Untergrenze, unter die nicht gegangen wird);
      * Undercut >  Ziel  -> Undercut-Preis (mehr Marge als das Ziel, und
        trotzdem die billigste Order am Hub).

    Rueckgabe `(preis, quelle)` mit quelle "ziel" oder "markt_statt_ziel".
    Die QUELLE ist kein Schmuck: dieselbe Spalte traegt dann zwei
    verschiedene Zahlen-Arten, und genau daraus entsteht die Fehlerklasse
    aus Sitzung 9 (eine Zahl traegt einen Namen, der etwas anderes
    meint). Anzeige, Tooltip und Zwischenablage-Meldung nehmen ihre
    Formulierung aus dieser Quelle - eine Wahrheit, kein zweites Urteil.
    """
    def _f(v):
        try:
            return float(v or 0.0)
        except (TypeError, ValueError):
            return 0.0
    z = _f(ziel_preis)
    u = _f(undercut_preis)
    if u > z:
        return u, "markt_statt_ziel"
    return z, "ziel"


# ---- Corp-Blaupausen in My Blueprints (1.1.0) -------------------------------
# Discord-Wunsch 27.09.2026 ("Blueprints im Corp-Hangar"). Rein, ohne Qt -
# die aa-Suite prueft sie direkt.

def eigener_preis_live(order_id, preis, buch):
    """Preis der EIGENEN Order, wie das Orderbuch ihn gerade zeigt (emm321).

    Nutzer-Meldung 01.10.2026 (Screenshots): nach dem Aendern im Spiel
    meldete das Order-Update "ueberboten" - der "beste Buy" war seine EIGENE
    neue Order (901'400, im Spiel mit Personen-Symbol), "deine Order" stand
    noch auf dem alten Preis (901'000). Die eigenen Orders kommen von einem
    langsamer aufgefrischten ESI-Endpunkt als das Orderbuch. Steht die
    order_id im Orderbuch, gilt dessen Preis; sonst der ESI-Wert."""
    try:
        _p = ((buch or {}).get("ids") or {}).get(int(order_id))
    except (TypeError, ValueError):
        _p = None
    return float(_p) if _p is not None else float(preis or 0.0)


def reservierung_fragen(eintrag, multi_von=None):
    """Beim SPEICHERN nach der Reservierung fragen? (emm315)

    Nutzer 01.10.2026: "Dafuer muss nicht gefragt werden, nachdem wir einen
    Bauplan schliessen/speichern OHNE zu freezen, dann gibt's auch nichts zu
    reservieren." Gefragt wird nur, wenn der Plan EINGEFROREN ist, noch
    nicht reserviert, etwas zu reservieren hat und kein Mitglied eines
    Multi-Bauplans ist (dort reserviert das Buendel). ERSETZT "jedes
    Speichern fragt" (30.09.2026)."""
    e = eintrag or {}
    return bool(e.get("frozen") and not e.get("reserve")
                and e.get("reserve_map") and not multi_von)


def hub_ort_id(hub_daten):
    """Ort-Nummer des gewaehlten Hubs (emm313): Struktur-Hub = structure_id
    (die Hub-Box traegt dort ein dict), NPC-Hub = Station aus hubs.NPC_HUBS
    (die Hub-Box traegt die Region). None, wenn nicht bestimmbar."""
    from .. import hubs as _hubs
    if isinstance(hub_daten, dict):
        try:
            return int(hub_daten.get("structure_id") or 0) or None
        except (TypeError, ValueError):
            return None
    try:
        _reg = int(hub_daten)
    except (TypeError, ValueError):
        return None
    for _k, _lbl, _rid, _sid in _hubs.NPC_HUBS:
        if int(_rid) == _reg:
            return int(_sid)
    return None


def standort_am_hub(ort, hub_id):
    """Steht der Charakter am Hub? (emm313, Nutzer 01.10.2026: Meldung,
    wenn der Trading-Charakter woanders ist als der gewaehlte Hub.)
    True = angedockt genau dort; False = woanders (auch: im All, selbst im
    Hub-System - Orders gehen dorthin, wo man angedockt ist); None = nicht
    zu sagen (kein Standort oder kein Hub) - dann KEINE Meldung."""
    if not ort or not hub_id:
        return None
    _hier = ort.get("structure_id") or ort.get("station_id")
    try:
        return bool(_hier) and int(_hier) == int(hub_id)
    except (TypeError, ValueError):
        return None


def job_fragen_gruppieren(offen, prio):
    """Zeilen fuer "Which build plan do these jobs belong to?" (emm312).

    Nutzer 01.10.2026: "es kommen enorm viele Fragen" - 4x Item 16679, 2x
    16678 ... je EIN Job eine Zeile, alle schon per Bau-Prioritaet demselben
    Plan gegeben. Prioritaets-Jobs (`prio`) desselben Items und desselben
    Plans werden deshalb EINE Zeile (Runs summiert, eine Antwort fuer alle).
    NICHT zugeordnete (`offen`) bleiben je Job eine Zeile: dort kann jeder
    Job zu einem anderen Plan gehoeren.
    Rueckgabe: [{type_id, runs, job_ids, ts_von, ts_bis, laeuft, prio_plan,
    kandidaten}] - offene zuerst, dann die Gruppen in Reihenfolge des
    ersten Auftretens."""
    def _ts(_f):
        try:
            return float(_f.get("fertig_ts"))
        except (TypeError, ValueError):
            return None
    zeilen = []
    for _f in (offen or []):
        zeilen.append({"type_id": int(_f["type_id"]),
                       "runs": int(_f.get("runs") or 0),
                       "job_ids": [int(_f["job_id"])],
                       "ts_von": _ts(_f), "ts_bis": _ts(_f),
                       "laeuft": bool(_f.get("laeuft")),
                       "prio_plan": _f.get("prio_plan"),
                       "name": _f.get("name"),
                       "kandidaten": list(_f.get("kandidaten") or [])})
    gruppen = {}
    for _f in (prio or []):
        _k = (int(_f["type_id"]), str(_f.get("prio_plan")), bool(_f.get("laeuft")))
        _z = gruppen.get(_k)
        if _z is None:
            _z = gruppen[_k] = {"type_id": int(_f["type_id"]), "runs": 0,
                                "job_ids": [], "ts_von": None, "ts_bis": None,
                                "laeuft": bool(_f.get("laeuft")),
                                "prio_plan": _f.get("prio_plan"),
                                "name": _f.get("name"),
                                "kandidaten": list(_f.get("kandidaten") or [])}
            zeilen.append(_z)
        _z["runs"] += int(_f.get("runs") or 0)
        _z["job_ids"].append(int(_f["job_id"]))
        _t = _ts(_f)
        if _t is not None:
            _z["ts_von"] = _t if _z["ts_von"] is None else min(_z["ts_von"], _t)
            _z["ts_bis"] = _t if _z["ts_bis"] is None else max(_z["ts_bis"], _t)
    return zeilen


def ist_platzhalter_name(name):
    """"#26378" ist KEIN Name, sondern der Ersatz, wenn keiner da war (Nutzer
    30.09.2026: "nur Nummern ... und dann kommen sie auch so in den
    Runplaner"). Wer Namen sammelt, darf so etwas nicht als bekannt merken -
    sonst holt ihn niemand mehr nach."""
    _s = str(name or "").strip()
    return not _s or (_s.startswith("#") and _s[1:].isdigit())


def bp_besitzer_passt(besitzer, want_char, via=None):
    """Filter in My Blueprints: "All" zeigt alles, sonst die Zeilen des
    gewaehlten Charakters. Eine Corp-Zeile (Besitzer = Corp-Nummer) steht
    zusaetzlich beim Charakter, ueber den sie geladen wurde (`via`, der
    Director). SEIT emm301 (Nutzer 30.09.2026) steht die Corp nicht mehr
    selbst im Dropdown - ERSETZT "man waehlt Corp oder Charakter".
    SEIT emm306 darf `via` eine LISTE sein: die Corp-Zeile steht unter JEDEM
    Director der Corp (Nutzer 01.10.2026)."""
    if want_char in (None, "all"):
        return True
    if besitzer == want_char:
        return True
    if isinstance(via, (list, tuple, set, frozenset)):
        return want_char in via
    return via is not None and via == want_char


def corp_bp_ort(b, loc_names=None):
    """Ort-Spalte einer Corp-Blaupause: "<Corp> · Corp hangar N" bzw.
    "<Corp> · several hangars". None fuer eine Charakter-Blaupause. Die
    location_id einer Corp-Blaupause ist das BUERO (ein Item), kein Ort mit
    Namen - ohne Assets-Abruf nicht aufloesbar; deshalb nennt die Zeile Corp
    und Hangar statt "#<Nummer>"."""
    from ..sprache import t as _txt
    _corp = (b or {}).get("_corp_name")
    if not _corp:
        return None
    if b.get("_ort_gemischt"):
        return _txt("{corp} · several hangars").format(corp=_corp)
    _div = int(b.get("division") or 0)
    if _div:
        return _txt("{corp} · Corp hangar {n}").format(corp=_corp, n=_div)
    return str(_corp)


def corp_bp_hinweis(cb):
    """Kurzer Zusatz fuer die Statuszeile von My Blueprints aus dem Ergebnis
    von `_corp_blaupausen`: wie viele Corp-Blaupausen aus welcher Corp, und
    beim Namen, warum eine Corp fehlt (neu verlinken, keine Director-Rolle,
    Abruf gescheitert, kein Hangar gewaehlt). Leer, wenn der Corp-Schalter
    aus ist - dann gibt es nichts zu sagen."""
    from ..sprache import t as _txt
    cb = cb or {}
    if not cb.get("aktiv"):
        return ""
    if cb.get("keine_division"):
        return _txt("Corp blueprints: no corp hangar selected in the settings")
    teile = []
    _corps = [str(c.get("name")) for c in (cb.get("corps") or []) if c.get("name")]
    if _corps:
        _n = sum(int(b.get("quantity", 1) or 1) for b in (cb.get("blueprints") or []))
        teile.append(_txt("{n} corp blueprint(s) from {corps}").format(
            n=_n, corps=", ".join(_corps)))
    if cb.get("relink"):
        teile.append(_txt("re-link for corp access: {names}").format(
            names=", ".join(str(x) for x in cb["relink"])))
    if cb.get("ohne_rolle"):
        teile.append(_txt("no Director role in: {corps}").format(
            corps=", ".join(str(x) for x in cb["ohne_rolle"])))
    teile.extend(str(x) for x in (cb.get("failed") or []))
    return " · ".join(teile)


def vorstufen_erledigt(build_runs, build_mats, erledigt):
    """Vorstufen, die NICHT MEHR GEBRAUCHT werden: {type_id: Plan-Runs}.

    NUTZER 28.09.2026 (Multiplan 1, Phenolic Composites): "wie kann ich mehr
    Composite Reactions brauchen ... ich habe schon alle Komponenten, die
    ich benoetige?" Gemessen: 36 von 40 Runs geliefert, und ALLE Verbraucher
    im Plan (Quantum Microprocessor, Fusion Thruster, Magpulse Thruster) waren
    fertig - den Rest hatte der Hangar gedeckt. Das Werkzeug zeigte trotzdem
    4 offene Runs und rechnete ihr Material in die Einkaufsliste.

    REGEL: ein Bau-Item, von dem JEDER Verbraucher im Plan erledigt ist
    (geliefert, laufend oder abgehakt - `erledigt` >= Plan-Runs), wird
    selbst nicht mehr gebraucht. Weiter nach unten (die Vorstufe der
    Vorstufe), bis sich nichts mehr aendert. Items OHNE Verbraucher im Plan
    (das Endprodukt, die Buendel-Enden) faellt die Regel nie an - dort gibt
    es nichts, woran sie sich halten koennte. Ein einziger offener
    Verbraucher haelt die Vorstufe offen (Regel 3).

    Rein und ohne Fenster pruefbar. Schluessel werden als int gelesen.
    """
    runs = {}
    for _t, _r in (build_runs or {}).items():
        try:
            if int(_r or 0) > 0:
                runs[int(_t)] = int(_r)
        except (TypeError, ValueError):
            continue
    verbraucher = {}
    for _c, _mats in (build_mats or {}).items():
        try:
            _c = int(_c)
        except (TypeError, ValueError):
            continue
        if _c not in runs:
            continue
        for _m in (_mats or []):
            try:
                _mid = int(_m[0])
            except (TypeError, ValueError, IndexError):
                continue
            if _mid in runs and _mid != _c:
                verbraucher.setdefault(_mid, set()).add(_c)
    _erl = {}
    for _t, _n in (erledigt or {}).items():
        try:
            _erl[int(_t)] = int(_n or 0)
        except (TypeError, ValueError):
            continue
    fertig = {t for t, r in runs.items() if _erl.get(t, 0) >= r}
    neu = {}
    geaendert = True
    while geaendert:
        geaendert = False
        for _t, _vs in verbraucher.items():
            if _t in fertig or not _vs:
                continue
            if all(_v in fertig for _v in _vs):
                fertig.add(_t)
                neu[_t] = runs[_t]
                geaendert = True
    return neu


def vorstufen_ins_budget(rest_budget, plan_runs, build_mats, erledigt, schon_fertig=()):
    """Runplaner-Budget {type_id: erledigte Runs} um die Vorstufen-Regel
    ergaenzen - gibt eine NEUE Karte zurueck.

    NUTZER 28.09.2026, nach emm259: "die 4 Runs sind immer noch da".
    GEMESSEN (planer_diagnose, Abschnitt VORSTUFEN-REGEL): Phenolic 40/40
    erledigt, alle drei Verbraucher fertig - und trotzdem "erkannt: 0". Die
    Regel lieferte nur NEU erkannte Items; Phenolic stand in `erledigt`
    aber schon auf 40, weil `_rest_geliefert_jetzt` die Regel selbst
    anwendet. Das Budget des Runplaners (nur ESI: 36) wurde darum nie
    angehoben. Jetzt zaehlt jedes Item, das die Regel hier ODER dort
    (`schon_fertig` = `_bd_vorstufen_fertig`) als nicht mehr gebraucht
    fuehrt; es bekommt seine vollen Plan-Runs.
    """
    out = dict(rest_budget or {})
    try:
        _neu = set(vorstufen_erledigt(plan_runs, build_mats, erledigt))
    except Exception:
        _neu = set()
    for _t in _neu | {int(x) for x in (schon_fertig or ())}:
        if _t in out:
            out[_t] = max(int(out.get(_t, 0) or 0),
                          int((plan_runs or {}).get(_t, 0) or 0))
    return out


def prio_jobs_zuteilen(jobs, plaene, vergeben, ist_reaktion):
    """Strittige, noch NIEMANDEM zugeordnete gelieferte Jobs nach BAU-
    PRIORITAET verteilen (Nutzer-Entscheid 28.09.2026, Kartenreihenfolge).

    `plaene` in Rang-Folge: [{"id", "runs": {tid: Plan-Runs},
    "seit": Einfrier-Zeitpunkt, "belegt": {tid: schon belegte Runs}}].
    `jobs`: gelieferte Jobs mit `job_id`, `product_type_id`, `runs`,
    `activity_id`, `_ts` (Fertig-Zeitpunkt). `vergeben`: job_ids, die schon
    in `job_zuordnung` stehen (Klick, eindeutig, deine Antwort - auch "zu
    keinem") - die bleiben unangetastet. `ist_reaktion(tid)` sagt, ob das
    Item per Reaktion (9/11) oder Fertigung (1) entsteht.

    Aelteste Jobs zuerst; jeder Plan bekommt hoechstens seine offenen Runs
    (Plan - belegt), nur Jobs, die NACH seinem Einfrieren fertig wurden.
    GANZE JOBS (28.09.2026, weil die Zuordnung jetzt GESPEICHERT wird und
    ein Job nur einem Plan gehoeren kann): ein Job geht an den ersten Plan
    in der Rangfolge, in den er ganz passt; passt er nirgends ganz, bleibt
    er eine offene Frage. Rueckgabe ({plan_id: {tid: Runs}},
    {job_id: plan_id}).
    """
    rest = {}
    for p in plaene or []:
        _b = p.get("belegt") or {}
        rest[p["id"]] = {int(t): max(0, int(r or 0) - int(_b.get(int(t), 0) or 0))
                         for t, r in (p.get("runs") or {}).items()}
    out = {p["id"]: {} for p in (plaene or [])}
    verteilt = {}
    _verg = set()
    for _j in (vergeben or ()):
        try:
            _verg.add(int(_j))
        except (TypeError, ValueError):
            continue

    def _schluessel(j):
        return (float(j.get("_ts") or 0.0), int(j.get("job_id") or 0))
    for j in sorted([j for j in (jobs or []) if j.get("job_id") is not None],
                    key=_schluessel):
        try:
            jid = int(j["job_id"])
            tid = int(j.get("product_type_id") or 0)
            n = int(j.get("runs") or 0)
        except (TypeError, ValueError):
            continue
        if jid in _verg or n <= 0 or j.get("_ts") is None:
            continue
        _act = j.get("activity_id")
        if ist_reaktion(tid):
            if _act not in (9, 11):
                continue
        elif _act != 1:
            continue
        for p in plaene or []:
            if float(j["_ts"]) < float(p.get("seit") or 0.0):
                continue
            cap = rest[p["id"]].get(tid, 0)
            if cap < n:
                continue
            out[p["id"]][tid] = out[p["id"]].get(tid, 0) + n
            rest[p["id"]][tid] = cap - n
            verteilt[jid] = p["id"]
            break
    return out, verteilt


# ---------------------------------------------------------------------------
# MULTIPLAN-VORSCHLAG (Nutzer 30.09.2026: "T1-Plan -> nur T1-Vorschlaege, T2-
# Plan -> nur T2, nur Blaupausen, die wir haben, lohnenswert, und sie duerfen
# die Marge nicht nach unten ziehen, nur erhoehen oder gleich halten").
def vorschlag_tech(meta):
    """Tech-Stufe aus meta_group_id: 2 -> "T2", 14 -> "T3", sonst "T1"."""
    try:
        m = int(meta) if meta is not None else 0
    except (TypeError, ValueError):
        m = 0
    return "T2" if m == 2 else ("T3" if m == 14 else "T1")


def vorschlag_kandidaten(econ, techs, vorhanden, plan_marge):
    """Kandidaten aus der Wirtschaftlichkeit von My Blueprints.

    `econ` = {bp_type: entry} (entry: category, meta, product_id, cost_unit,
    profit, isk_h, opt_qty); `techs` = Tech-Stufen der Plan-Enden;
    `vorhanden` = Produkte, die schon im Plan sind; `plan_marge` = Marge des
    Plans in % (Gewinn / Kosten) oder None.
    Nur Endprodukte mit Gewinn > 0, passender Tech-Stufe und eigener Marge
    >= Plan-Marge: dann kann die Buendel-Marge (Summe Gewinn / Summe Kosten)
    rechnerisch nicht sinken. Sortiert nach Marge absteigend."""
    out, gesehen = [], set()
    vorhanden = {int(x) for x in (vorhanden or ())}
    for bp, e in (econ or {}).items():
        pid = e.get("product_id")
        cost, prof = e.get("cost_unit"), e.get("profit")
        if pid is None or cost is None or prof is None:
            continue
        if e.get("category") != "end" or float(cost) <= 0 or float(prof) <= 0:
            continue
        if int(pid) in vorhanden or int(pid) in gesehen:
            continue
        if vorschlag_tech(e.get("meta")) not in set(techs or ()):
            continue
        marge = float(prof) / float(cost) * 100.0
        if plan_marge is not None and marge < float(plan_marge):
            continue
        gesehen.add(int(pid))
        out.append({"bp": bp, "tid": int(pid), "marge": marge,
                    "profit": float(prof), "cost": float(cost),
                    "isk_h": e.get("isk_h"), "opt_qty": e.get("opt_qty")})
    out.sort(key=lambda x: (-x["marge"], x["tid"]))
    return out


def gemeinsam_anteil(kand_buy, plan_buy, preis):
    """Anteil (%) des Einkaufswerts eines Kandidaten, dessen Materialien auch
    der Plan einkauft - wertgewichtet (Menge x Preis). Ohne Preis/Menge None."""
    ges = gem = 0.0
    plan = {int(t) for t, q in (plan_buy or {}).items() if q}
    for t, q in (kand_buy or {}).items():
        try:
            w = float(q or 0) * float(preis(int(t)) or 0)
        except Exception:
            w = 0.0
        if w <= 0:
            continue
        ges += w
        if int(t) in plan:
            gem += w
    return (gem / ges * 100.0) if ges > 0 else None


# INDUSTRY-JOB-UEBERSICHT (emm327, Discord-Wunsch ueber den Nutzer 01.10.2026:
# "Uebersicht ueber alle Indu-Jobs ... welcher Char welche Slots belegt hat mit
# was und wie lange"). Die Anzeige-Namen der Aktivitaeten stehen in
# `_jobs_art_name` (mw_bauplan_tabs), dort mit t().


def job_slot_art(activity_id):
    """Welcher Slot-Typ ein Job belegt - dieselbe Einteilung wie
    `esi.fetch_industry_jobs` (1 Fertigung, 9/11 Reaktion, Rest Science)."""
    a = int(activity_id or 0)
    if a == 1:
        return "mfg"
    if a in (9, 11):
        return "react"
    return "sci"


def jobs_uebersicht(jobs, slots_max, now):
    """Ein Charakter: belegte/maximale/freie Slots je Typ und seine Jobs,
    nach Ende sortiert (zuerst fertig). Rein, ohne Qt.

    jobs: Eintraege wie `esi.fetch_active_jobs` (active/paused/ready).
    slots_max: (mfg, react, sci) aus `industry.job_slots` oder None (Skills
    unbekannt -> keine Freiezahl, nie eine geratene).
    Ein fertiger, nicht abgelieferter Job belegt den Slot WEITER (erst das
    Abliefern gibt ihn frei) - er zaehlt also mit, Restzeit 0, fertig=True.
    """
    from datetime import datetime as _dt
    belegt = {"mfg": 0, "react": 0, "sci": 0}
    zeilen = []
    for j in jobs or []:
        art = job_slot_art(j.get("activity_id"))
        belegt[art] += 1
        try:
            ende = _dt.fromisoformat(
                str(j.get("end_date")).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            ende = None
        try:
            start = _dt.fromisoformat(
                str(j.get("start_date")).replace("Z", "+00:00")).timestamp()
        except (TypeError, ValueError):
            start = None
        st = j.get("status")
        fertig = st == "ready" or (st == "active" and ende is not None
                                   and ende <= now)
        rest = None if ende is None else max(0, int(ende - now))
        if fertig:
            rest = 0
        zeilen.append({"art": art, "activity_id": int(j.get("activity_id") or 0),
                       "tid": int(j.get("product_type_id") or 0),
                       "runs": int(j.get("runs") or 0), "status": st,
                       "ende": ende, "start": start, "rest": rest, "ready": fertig,
                       "paused": st == "paused",
                       "corp": bool(j.get("corporation_id"))})
    zeilen.sort(key=lambda z: (z["ende"] is None,
                               z["ende"] if z["ende"] is not None else 0,
                               z["tid"]))
    mx = frei = None
    if slots_max:
        mx = {"mfg": int(slots_max[0]), "react": int(slots_max[1]),
              "sci": int(slots_max[2])}
        frei = {k: max(0, mx[k] - belegt[k]) for k in mx}
    return {"belegt": belegt, "max": mx, "frei": frei, "zeilen": zeilen}


def job_fortschritt(start, ende, now):
    """Anteil 0..1 eines laufenden Jobs; ohne Zeiten None (kein geratener Wert)."""
    if start is None or ende is None or ende <= start:
        return None
    return max(0.0, min(1.0, (now - start) / (ende - start)))


def jobs_gruppen(zeilen, now):
    """Gleiche Jobs zusammenfassen (emm330, Nutzer: "kein Excel-Tabellen-
    Simulator ... mit wenigen Blicken verstaendlich"): je (Aktivitaet, Item)
    EINE Zeile "5x Scalar Capacitor Unit". Fertige stehen getrennt ("ready"),
    pausierte bekommen eine eigene Gruppe. Eine laufende Gruppe zeigt den
    Job, der ZUERST fertig wird (Restzeit, Fortschritt); alle Enden stehen in
    `enden`. Rein, ohne Qt.
    -> {"ready": [...], "laufend": [...]}, laufend nach Restzeit sortiert."""
    ready, lauf = {}, {}
    for z in zeilen or []:
        key = (z["activity_id"], z["tid"])
        if z["ready"]:
            g = ready.setdefault(key, {"activity_id": z["activity_id"], "tid": z["tid"],
                                       "art": z["art"], "n": 0, "runs": 0,
                                       "corp": False})
            g["n"] += 1
            g["runs"] += int(z["runs"] or 0)
            g["corp"] = g["corp"] or bool(z.get("corp"))
            continue
        key = key + (bool(z["paused"]),)
        g = lauf.setdefault(key, {"activity_id": z["activity_id"], "tid": z["tid"],
                                  "art": z["art"], "paused": bool(z["paused"]),
                                  "n": 0, "runs": 0, "enden": [], "rest": None,
                                  "ende": None, "start": None, "corp": False})
        g["n"] += 1
        g["runs"] += int(z["runs"] or 0)
        g["corp"] = g["corp"] or bool(z.get("corp"))
        if z["ende"] is not None:
            g["enden"].append(z["ende"])
            if g["ende"] is None or z["ende"] < g["ende"]:
                g["ende"], g["start"], g["rest"] = z["ende"], z["start"], z["rest"]
    for g in lauf.values():
        g["enden"].sort()
        g["fortschritt"] = job_fortschritt(g["start"], g["ende"], now)
    _r = sorted(ready.values(), key=lambda g: (-g["n"], g["tid"]))
    _l = sorted(lauf.values(), key=lambda g: (g["paused"], g["rest"] is None,
                                              g["rest"] or 0, g["tid"]))
    return {"ready": _r, "laufend": _l}


def corp_jobs_verteilen(corp_jobs, cids, bekannte_job_ids):
    """Corp-Jobs auf die Charakter-Karten verteilen (emm389, Discord
    HerrLades: "corp jobs still use the normal slots of the character you
    put up the job with"). Rein, ohne Qt.

    -> ({installer_cid: [Jobs]}, uebrige): Jobs eines VERKNUEPFTEN
    Installers landen bei dessen Karte (dort zaehlen sie in die Slots);
    schon bekannte job_ids werden nie doppelt gezaehlt; der Rest (fremde
    Installer) bleibt uebrig - er zaehlt in keine Slot-Zaehlung, die
    Corp-Karte zeigt ihn trotzdem."""
    cids = {int(c) for c in (cids or ())}
    bekannt = {j for j in (bekannte_job_ids or ()) if j is not None}
    je_cid, uebrig = {}, []
    for j in corp_jobs or []:
        jid = j.get("job_id")
        if jid is not None and jid in bekannt:
            continue
        if jid is not None:
            bekannt.add(jid)
        try:
            inst = int(j.get("installer_id") or 0)
        except (TypeError, ValueError):
            inst = 0
        if inst in cids:
            je_cid.setdefault(inst, []).append(j)
        else:
            uebrig.append(j)
    return je_cid, uebrig


def jobs_karten_folge(chars):
    """Reihenfolge der Charakter-Karten (emm331, Nutzer: Vorschlag
    "Handlungsbedarf zuerst" gewaehlt). chars: {cid: {"name", "ueb"}} wie
    `_jobs_laden` sie liefert. -> [cid, ...]
      0. fertige Jobs zum Abliefern (die meisten zuerst),
      1. freie Slots (die meisten zuerst),
      2. der Rest - voll belegt oder Maximum unbekannt - nach dem naechsten
         fertigen Job; ohne laufenden Job ganz hinten.
    Gleichstand: Name. Rein, ohne Qt."""
    def _key(kv):
        cid, e = kv
        u = e.get("ueb") or {}
        zeilen = u.get("zeilen") or []
        name = str(e.get("name") or "").lower()
        fertig = sum(1 for z in zeilen if z.get("ready"))
        if fertig:
            return (0, -fertig, 0.0, name)
        frei = sum((u.get("frei") or {}).values()) if u.get("frei") else 0
        if frei:
            return (1, -frei, 0.0, name)
        enden = [z["ende"] for z in zeilen
                 if z.get("ende") is not None and not z.get("paused")]
        return (2, 0, min(enden) if enden else float("inf"), name)
    return [cid for cid, _e in sorted((chars or {}).items(), key=_key)]


def snapshot_ohne_ende(plan, tid, inv_mats_weg=None):
    """EIN ENDE AUS DEM EINGEFRORENEN BUENDEL NEHMEN, OHNE DIE UEBRIGEN RUNS
    ANZUFASSEN (emm333, Nutzer 02.10.2026: "die Runs im Runplaner duerfen
    sich nicht veraendern, sonst stimmen die Materialien nicht mehr" ->
    Rueckfrage "geteilte Vorstufen?" -> "Alles bleibt").

    Rein, rechnet NICHT neu (kein production_plan): aus dem Schnappschuss
    fallen nur das Ende und die Vorstufen, die AUSSCHLIESSLICH (auch ueber
    mehrere Stufen) von ihm verbraucht wurden, dazu Kauf-/Bestandsmaterial,
    das nur diese brauchten. Alles, was ein uebriges Ende braucht, behaelt
    seine Runs EXAKT; was das entfernte Ende davon verbraucht haette, steht
    als Ueberschuss in `surplus` (Regel 3: lieber zu viel). Wird das Ende
    selbst noch von einem anderen Bau-Item verbraucht (Ende-in-Ende), bleibt
    es als Bau-Item stehen - nur die Ende-Menge faellt weg.
    Kosten: die Posten der entfernten Items werden aus den Summen gezogen
    (Summe der Posten == Gesamt bleibt). Invention-Material (`inv_buy`) ist
    nicht je Item aufgeschluesselt: `inv_mats_weg` {type: Menge} nennt, was
    die Invention des entfernten Endes braucht (emm336, Nutzer: "alle Punkte
    dringend"); das faellt zuerst aus `inv_buy`, der Rest aus
    `inv_stock_used` - nie unter 0. Ohne Angabe bleibt beides stehen.

    Liefert (neuer_plan, {entfernte Bau-Items}). Die Eingabe bleibt unberuehrt."""
    import copy
    p = copy.deepcopy(plan or {})
    tid = int(tid)
    enden = {int(k): v for k, v in (p.get("buendel_enden") or {}).items()}
    if tid not in enden:
        return p, set()
    enden.pop(tid)
    p["buendel_enden"] = enden
    bm = {int(k): v for k, v in (p.get("build_mats") or {}).items()}
    verbr = {}
    for _b, _mats in bm.items():
        for _m, _q in (_mats or []):
            verbr.setdefault(int(_m), {})
            verbr[int(_m)][_b] = verbr[int(_m)].get(_b, 0) + int(_q or 0)
    weg = set()
    if not verbr.get(tid):
        weg.add(tid)
        _neu = True
        while _neu:
            _neu = False
            for _b in bm:
                if _b in weg or _b in enden:
                    continue
                _v = verbr.get(_b)
                if _v and set(_v) <= weg:
                    weg.add(_b)
                    _neu = True

    def _pop(key, k):
        d = p.get(key)
        if isinstance(d, dict):
            for _k in (k, str(k)):
                if _k in d:
                    return d.pop(_k)
        return None

    def _abzug(item_key, summe_key, k):
        c = float(_pop(item_key, k) or 0.0)
        if c:
            p[summe_key] = float(p.get(summe_key) or 0.0) - c
        return c

    abzug = 0.0
    _job_alt = float(p.get("job_cost") or 0.0)
    for k in weg:
        for key in ("build_runs", "build_mats", "build_made", "decision", "surplus"):
            _pop(key, k)
        abzug += _abzug("job_cost_items", "job_cost", k)
        abzug += _abzug("inv_cost_items", "inv_cost", k)
    # Job-Kosten-Aufschluesselung im selben Verhaeltnis (index+tax+scc == job_cost)
    _teile = p.get("job_cost_parts")
    if isinstance(_teile, dict) and _job_alt > 0:
        _f = float(p.get("job_cost") or 0.0) / _job_alt
        p["job_cost_parts"] = {kk: float(vv or 0.0) * _f for kk, vv in _teile.items()}

    def _nur_weg(m):
        v = verbr.get(int(m))
        return bool(v) and set(v) <= weg

    for _key, _items, _summe in (("buy", "buy_cost_items", "mat_cost"),
                                 ("stock_used", "stock_cost_items", "stock_cost")):
        d = p.get(_key)
        if not isinstance(d, dict):
            continue
        for _m in [m for m in list(d) if _nur_weg(m)]:
            d.pop(_m)
            abzug += _abzug(_items, _summe, int(_m))
            if _key == "buy" and (p.get("decision") or {}).get(int(_m)) == "buy":
                _pop("decision", int(_m))
    nk = p.get("nicht_kaufbar")
    if isinstance(nk, (list, set)):
        _bleibt = set(int(x) for x in (p.get("buy") or {})) | set(
            int(x) for x in (p.get("decision") or {}))
        p["nicht_kaufbar"] = [x for x in nk if int(x) in _bleibt]
    if abzug:
        p["total_cost"] = float(p.get("total_cost") or 0.0) - abzug
    # Was die entfernten Items von GEBLIEBENEN Bau-Items verbraucht haetten,
    # wird Ueberschuss - die Runs bleiben, wie sie sind.
    sp = p.get("surplus")
    if not isinstance(sp, dict):
        sp = p["surplus"] = {}
    for _m, _v in verbr.items():
        if _m in weg or _m not in bm:
            continue
        _q = sum(q for b, q in _v.items() if b in weg)
        if _q > 0:
            sp[_m] = int(sp.get(_m, 0) or 0) + _q
    if tid not in weg and tid in bm:
        # Ende-in-Ende: die Ende-Menge wird jetzt Ueberschuss
        _alt_menge = int((plan.get("buendel_enden") or {}).get(
            tid, (plan.get("buendel_enden") or {}).get(str(tid), 0)) or 0)
        if _alt_menge > 0:
            sp[tid] = int(sp.get(tid, 0) or 0) + _alt_menge
    seq = p.get("build_seq")
    if isinstance(seq, list):
        p["build_seq"] = [x for x in seq if int(x[0]) not in weg]
    if tid in weg:
        for _m, _q in (inv_mats_weg or {}).items():
            _rest = int(_q or 0)
            for _key in ("inv_buy", "inv_stock_used"):
                d = p.get(_key)
                if _rest <= 0 or not isinstance(d, dict):
                    continue
                _k = int(_m) if int(_m) in d else (str(_m) if str(_m) in d else None)
                if _k is None:
                    continue
                _ab = min(_rest, int(d[_k] or 0))
                d[_k] = int(d[_k] or 0) - _ab
                _rest -= _ab
                if d[_k] <= 0:
                    d.pop(_k)
    return p, weg


def jobs_dauer_kurz(sek):
    """Restzeit fuer die Job-Karten in den ZWEI groessten Einheiten (emm334,
    Nutzer: "immer noch nicht uebersichtlich genug" - "1 T 5 h 13 m" wurde in
    der Zeile abgeschnitten). Gleiche Buchstaben wie `_fmt_dur` (T/h/m).
    Rein: 0 -> "< 1 m"."""
    s = max(0, int(sek or 0))
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m = s // 60
    if d:
        return f"{d} T {h} h"
    if h:
        return f"{h} h {m} m"
    return f"{m} m" if m else "< 1 m"


def jobs_sichtbar(chars, aus):
    """Nur die eingeschalteten Charaktere (emm334, Nutzer: "verlinkte
    Charaktere ... per On/Off zu- und ausschalten, standardmaessig alle On").
    aus: gespeicherte Liste der AUSgeschalteten (Text oder Zahl). Rein."""
    _aus = {str(x) for x in (aus or ())}
    return {cid: e for cid, e in (chars or {}).items() if str(cid) not in _aus}


def jobs_summe(chars, now):
    """Gesamt-Leiste ueber die gezeigten Charaktere (emm334): fertige Jobs,
    freie Slots je Art (nur Charaktere mit bekanntem Maximum; `ohne_max`
    zaehlt die anderen), naechster fertig werdender Job (Restzeit, Name).
    Pausierte zaehlen nicht als "naechster". Rein."""
    fertig = 0
    frei = {"mfg": 0, "react": 0, "sci": 0}
    ohne_max = 0
    naechst = None
    for _cid, e in (chars or {}).items():
        u = e.get("ueb") or {}
        zeilen = u.get("zeilen") or []
        fertig += sum(1 for z in zeilen if z.get("ready"))
        if u.get("frei"):
            for k in frei:
                frei[k] += int(u["frei"].get(k, 0) or 0)
        else:
            ohne_max += 1
        for z in zeilen:
            if z.get("ready") or z.get("paused") or z.get("ende") is None:
                continue
            rest = max(0, int(z["ende"] - now))
            if naechst is None or rest < naechst[0]:
                naechst = (rest, str(e.get("name") or ""))
    return {"ready": fertig, "free": frei, "no_max": ohne_max,
            "next": naechst}


def jobs_kapazitaet(chars):
    """Slot-Auslastung ueber die gezeigten Charaktere je Art (emm346, Nutzer:
    "den Text oben mehr in eine Grafik umwandeln, damit man schoen sieht,
    wie viele Slots frei sind"): {art: {"running", "ready", "max", "free"}}.
    Nur Charaktere mit bekanntem Maximum - sonst stimmte "frei" nicht. Ein
    fertiger Job belegt seinen Slot weiter (zaehlt als "ready"). Rein."""
    out = {k: {"running": 0, "ready": 0, "max": 0, "free": 0}
           for k in ("mfg", "react", "sci")}
    for _cid, e in (chars or {}).items():
        u = e.get("ueb") or {}
        mx = u.get("max")
        if not mx:
            continue
        bel = u.get("belegt") or {}
        for k in out:
            _rd = sum(1 for z in (u.get("zeilen") or [])
                      if z.get("ready") and z.get("art") == k)
            _b = int(bel.get(k, 0) or 0)
            out[k]["ready"] += _rd
            out[k]["running"] += max(0, _b - _rd)
            out[k]["max"] += int(mx.get(k, 0) or 0)
            out[k]["free"] += max(0, int(mx.get(k, 0) or 0) - _b)
    return out


def fehlende_scopes(gewuenscht, erteilt_je_char):
    """{cid: sortierte fehlende Scopes} - nur Charaktere, bei denen etwas
    fehlt (emm355, Nutzer: "wenn ein ESI-Scope fehlt, steht oben re-link -
    das sieht kein Mensch, da muss beim Login ein Popup kommen").
    `erteilt_je_char`: {cid: set | None}; None = unbekannt (Token nicht
    lesbar) -> dieser Charakter wird NICHT gemeldet (lieber still als
    falsch). "publicData" zaehlt nie. Rein."""
    soll = {str(s) for s in (gewuenscht or ()) if s and s != "publicData"}
    out = {}
    for cid, hat in (erteilt_je_char or {}).items():
        if hat is None:
            continue
        fehlt = sorted(soll - {str(s) for s in hat})
        if fehlt:
            out[cid] = fehlt
    return out


def bp_marge(profit, cost_unit):
    """Marge in % wie im Bauplan: Gewinn / Baukosten (emm354, Spalte "Margin %"
    in My Blueprints). None ohne Gewinn oder ohne positive Kosten. Rein."""
    try:
        p, c = float(profit), float(cost_unit)
    except (TypeError, ValueError):
        return None
    if c <= 0:
        return None
    return p / c * 100.0


HAKEN_FRIST = 1800.0       # so lange nach dem Haken bekommt ESI Zeit
HAKEN_RUECK = 3 * 86400.0  # gelieferte Jobs bis so weit VOR dem Haken zaehlen


def _iso_ts(s):
    from datetime import datetime as _dt
    try:
        return _dt.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return None


def haken_ohne_job(haken_ts, aktiv_tids, geliefert, abruf_ts,
                   frist=HAKEN_FRIST, rueck=HAKEN_RUECK):
    """Hand-Haken im Runplaner, zu denen ESI KEINEN Job kennt -> Fehlklick
    (emm350, Nutzer: "habe ich selbst abgehakt und ESI trackt keinen Job zu
    diesem Item, darf der Bauplan meinen Haken wieder entfernen, dann habe
    ich offensichtlich missklickt"; "ein nicht verknuepfter Charakter ist
    ein falscher Charakter"; "der Job kann auf einem ANDEREN verknuepften
    Charakter gestartet worden sein - das ist okay").

    Je ITEM, nicht je Charakter: ein Job irgendeines verknuepften
    Charakters (oder der Corp) zaehlt. Geprueft wird ein Haken erst, wenn
    der Job-Abruf mindestens `frist` Sekunden NACH dem Haken lag. Es zaehlt
    jeder laufende/fertige Job (`aktiv_tids`) und jeder gelieferte, der
    hoechstens `rueck` vor dem Haken endete. Nur Job-Stufen
    ("stufe|cid|tid"), keine Charakter- oder Reprocessing-Zeilen. Haken
    ohne Zeitstempel bleiben unberuehrt. -> sortierte Schluessel. Rein."""
    if abruf_ts is None:
        return []
    gel = {}
    for j in geliefert or []:
        try:
            pid = int(j.get("product_type_id") or 0)
        except (TypeError, ValueError, AttributeError):
            continue
        ts = _iso_ts(j.get("completed_date")) or _iso_ts(j.get("end_date")) \
            or _iso_ts(j.get("start_date"))
        if pid and ts is not None:
            gel.setdefault(pid, []).append(ts)
    aktiv = set()
    for t in aktiv_tids or ():
        try:
            aktiv.add(int(t))
        except (TypeError, ValueError):
            continue
    out = []
    for key, ts in (haken_ts or {}).items():
        teile = str(key).split("|")
        if len(teile) < 3 or teile[0] in ("char", "repro") or not teile[2].isdigit():
            continue
        try:
            ts = float(ts)
        except (TypeError, ValueError):
            continue
        if float(abruf_ts) < ts + float(frist):
            continue
        tid = int(teile[2])
        if tid in aktiv:
            continue
        if any(g >= ts - float(rueck) for g in gel.get(tid, [])):
            continue
        out.append(key)
    return sorted(out, key=str)


ABSATZ_TAGE = 30           # Fenster fuer das Tagesvolumen
ABSATZ_LANGSAM = 7.0       # ab hier "langsam" (Tage bis verkauft)
ABSATZ_DUENN = 30.0        # ab hier Warnung "Markt zu duenn"


def tagesvolumen(rows, heute=None, tage=ABSATZ_TAGE):
    """Durchschnittlich verkaufte Stueck je Tag am Hub (emm349, Nutzer: "das
    Handelsvolumen haette ich gerne in einer Spalte, damit ich sehen kann,
    ob etwas, das ich baue, auch gekauft wird"). Grundlage: die Markt-
    Historie (je Tag eine Zeile, Tage ohne Handel fehlen bei ESI - sie
    zaehlen als 0). Ueber die letzten `tage` Tage bis `heute` (Datum
    "YYYY-MM-DD", sonst der juengste Tag der Historie). None = keine
    Historie bekannt (nicht: kein Handel). Rein."""
    import datetime as _d
    zeilen = [r for r in (rows or []) if r.get("date")]
    if not zeilen:
        return None
    try:
        ende = _d.date.fromisoformat(str(heute or max(str(r["date"]) for r in zeilen))[:10])
    except ValueError:
        return None
    start = ende - _d.timedelta(days=int(tage) - 1)
    summe = 0.0
    for r in zeilen:
        try:
            tag = _d.date.fromisoformat(str(r["date"])[:10])
        except ValueError:
            continue
        if start <= tag <= ende:
            summe += float(r.get("volume") or 0)
    return summe / float(tage)


def tage_bis_verkauft(menge, vol):
    """Wie viele Tage der Markt braucht, um `menge` aufzunehmen (wenn man
    ALLES selbst verkauft, Konkurrenz nicht mitgerechnet). None = Volumen
    unbekannt, inf = es wird nichts gehandelt. Rein."""
    if vol is None:
        return None
    if vol <= 0:
        return float("inf")
    return float(menge or 0) / float(vol)


def absatz_stufe(tage):
    """"unknown" / "ok" (<= 7 Tage) / "slow" (<= 30) / "thin" (> 30). Rein."""
    if tage is None:
        return "unknown"
    if tage <= ABSATZ_LANGSAM:
        return "ok"
    if tage <= ABSATZ_DUENN:
        return "slow"
    return "thin"


def job_anzeigename(name, activity_id):
    """Bei Science-Jobs (alles ausser Fertigung/Reaktion) ist das Produkt
    eine Blaupause - das Kuerzel davor sagt es schon, " Blueprint" am Ende
    faellt weg (emm334: Zeilen wurden abgeschnitten). Rein."""
    n = str(name or "")
    if int(activity_id or 0) not in (1, 9, 11) and n.endswith(" Blueprint"):
        return n[:-len(" Blueprint")]
    return n


def fracht_als_isk(je_stueck, einkauf):
    """Fracht-Abzeichen in ISK statt Prozent? (emm336, Nutzer: "das 1-ISK-
    Problem loesen" - fuer 1 ISK gekaufte Items stand "+250000.00 %").
    Ja, sobald die Fracht je Stueck groesser ist als der Einkauf je Stueck
    (also ueber +100 %) oder kein Einkaufspreis bekannt ist. Rein."""
    try:
        j, e = float(je_stueck or 0), float(einkauf or 0)
    except (TypeError, ValueError):
        return False
    if j <= 0:
        return False
    return e <= 0 or j > e


def erledigt_ts_aus_haken(haken_ts):
    """Zeitstempel je "stufe|tid" aus den gespeicherten Haken-Stempeln
    (emm336; offen seit emm252: `_bd_runplan_erledigt_ts` wurde nie gesetzt,
    ein nachgetragener Haken bekam "jetzt"). Je Item der JUENGSTE Haken -
    dieselbe Regel wie die ESI-Sperre der Reservierung (emm265): frei wird
    erst, wenn der Bestand juenger ist als der letzte Haken. Schluessel
    "stufe|cid|tid[|w2]"; Charakter-Sammelzeilen ("char|...") und Erz-Zeilen
    ("repro|...") tragen kein Item und fallen weg. Rein."""
    out = {}
    for k, ts in (haken_ts or {}).items():
        teile = str(k).split("|")
        if len(teile) < 3 or teile[0] in ("char", "repro") or not teile[2].isdigit():
            continue
        try:
            v = float(ts)
        except (TypeError, ValueError):
            continue
        key = f"{teile[0]}|{int(teile[2])}"
        if v > out.get(key, 0.0):
            out[key] = v
    return out


def jobs_einzeln(zeilen, now):
    """JEDER laufende Job eine Zeile (emm338, Nutzer: "komplette Anzeige" -
    "9x Sensor Booster II" war 9 Jobs in einer Zeile, er hat die 10/10
    Science-Jobs darunter nicht wiedergefunden). Fertige bleiben
    zusammengefasst (`jobs_gruppen`). Laufende tragen dieselben Schluessel
    wie eine Gruppe mit n=1 und sind nach Restzeit sortiert, pausierte
    hinten. Rein."""
    gr = jobs_gruppen(zeilen, now)
    lauf = []
    for z in zeilen or []:
        if z.get("ready"):
            continue
        ende = z.get("ende")
        lauf.append({"activity_id": z["activity_id"], "tid": z["tid"], "art": z["art"],
                     "paused": bool(z.get("paused")), "n": 1,
                     "corp": bool(z.get("corp")),
                     "runs": int(z.get("runs") or 0),
                     "enden": [ende] if ende is not None else [],
                     "rest": z.get("rest"), "ende": ende, "start": z.get("start"),
                     "fortschritt": job_fortschritt(z.get("start"), ende, now)})
    lauf.sort(key=lambda g: (g["paused"], g["rest"] is None, g["rest"] or 0, g["tid"]))
    return {"ready": gr["ready"], "laufend": lauf}
