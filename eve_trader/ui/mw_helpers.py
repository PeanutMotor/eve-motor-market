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
                            _pid, _plan_runs)
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
                  for _f in (getattr(self, "_bd_job_offen", None) or [])}
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
                                stock_seen_ts, belegt=None):
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
        if (not checked_ts and not belegt) or not assignments:
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
                        belegt=MainWindowHelpers._belegt_fuer_plan(p))
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
        for p in (settings or {}).get("bau_saved_plans", []) or []:
            if not p.get("reserve"):
                continue
            if exclude_plan_id is not None and p.get("id") == exclude_plan_id:
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
                        belegt=MainWindowHelpers._belegt_fuer_plan(p))
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
                 fenster_sek=KLICK_FENSTER_SEK):
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
    """
    if not jobs or not klicks or plan_id is None:
        return {}
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
        for k_tid, k_runs, k_ts, k_reaktion in _klicks:
            if k_tid != tid or k_runs != runs:
                continue
            if k_reaktion != ist_reaktion:
                continue
            # Der Job muss NACH dem Klick gestartet sein - ein Klick kann
            # nichts belegen, was vorher schon lief.
            if jts < k_ts or jts - k_ts > float(fenster_sek):
                continue
            aus[jid] = (tid, runs)
            _schon[tid] = _schon.get(tid, 0) + runs
            break
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
                     "fertig_ts": fts})
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
                        live_stock):
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
    out = []
    for m, bedarf in need.items():
        prod = rem.get(m, 0) * int((out_qty_map or {}).get(m, 1) or 1)
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
      1. was der Nutzer getippt hat, gilt (`user_runs`);
      2. sonst die kleinste eigene Kopie aus dem ESI-Cache (`esi_runs`,
         dieselbe Quelle, aus der `_bpc_runs_by_tid` schon den Runs-Deckel
         nimmt - EINE Wahrheit);
      3. sonst None: unbekannt heisst unbegrenzt (wie bei T1/BPO), NICHT
         "eine Riesenkopie".
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
    je = _i(user_runs)
    if je < 1:
        je = _i(esi_runs)
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
