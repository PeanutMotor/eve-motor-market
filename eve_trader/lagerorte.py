"""Lagerorte - WO liegt das Material der Bauplaene? (emm458, 07.10.2026)

Nutzer: "etwas Globaleres, wo man schnell sehen kann, wo die Materialien
der Bauplaene rumliegen, bei welchem Charakter was liegt ... oft auf
verschiedenen Strukturen und dann noch in Containern oder Frachtcontainern".
Anlass: fuer 10 Ion Blaster Cannon II fehlten Berry Motor im Spiel 5
Particle Accelerator Units, waehrend Eve MoMa 4'186 ueber alle Charaktere
zaehlte - das Spiel nimmt nur den Hangar des Charakters, der den Job
startet.

Reine Logik ohne Qt und ohne ESI: aus rohen Asset-Listen wird je Item der
Weg Ort -> Besitzer -> Behaelter(kette) mit Menge. Dieselben Regeln wie die
Bestandszaehlung (esi.hangar_und_container, corp.corp_bestand): in
Behaelter wird hinabgestiegen, auch verschachtelt; in SCHIFFE nicht
(Fittings/Ladung sind kein Lagerbestand). Was hier steht, ist also genau
das, was der Bauplan als Bestand zaehlt - nur mit Adresse.
"""
from __future__ import annotations

import time as _time

from . import corp as _corp

ART_CHAR = "char"
ART_CORP = "corp"


def zeilen_aus_assets(assets, container_typen, besitzer, art=ART_CHAR,
                      divisions=None, ist_behaelter=None):
    """Flache Zeilen aus einer rohen Asset-Liste EINES Besitzers.

    -> [{"tid", "menge", "ort", "besitzer", "art", "flag", "pfad", "item_id"}]
    `pfad` = item_ids der Behaelter von aussen nach innen ([] = lose im
    Hangar), `flag` = location_flag des obersten Eintrags ("Hangar" bzw.
    "CorpSAG3"). `ort` = Station/Struktur (bei Corp-Items ueber Buero und
    Division hochgelaufen, corp.wurzel_ort).

    Charakter: zaehlt, was mit Flag "Hangar" direkt an einer Station/Struktur
    haengt. Corp: zaehlt die Hangar-Divisions (`divisions`, Vorgabe alle 7).
    """
    by_id, by_parent = {}, {}
    for a in assets or []:
        iid = a.get("item_id")
        if iid is not None:
            by_id[iid] = a
        by_parent.setdefault(a.get("location_id"), []).append(a)
    if ist_behaelter is None:
        from .esi import _behaelter_pruefer
        ist_behaelter = _behaelter_pruefer(by_parent, container_typen)
    if art == ART_CORP:
        gew = set(_corp.divisions_bereinigt(divisions)
                  if divisions is not None else _corp.ALLE_DIVISIONS)

    def _oben(a):
        """Ist dieser Eintrag ein Hangar-Eintrag oberster Ebene?"""
        if art == ART_CORP:
            return _corp.division_von(a.get("location_flag")) in gew
        return (a.get("location_flag") == "Hangar"
                and a.get("location_id") not in by_id)

    out = []
    gesehen = set()
    for a in assets or []:
        if not _oben(a):
            continue
        ort = _corp.wurzel_ort(a, by_id)
        try:
            ort = int(ort or 0)
        except (TypeError, ValueError):
            ort = 0
        flag = a.get("location_flag")
        stack = [(a, [])]
        while stack:
            e, pfad = stack.pop()
            iid = e.get("item_id")
            if iid in gesehen:
                continue
            gesehen.add(iid)
            try:
                menge = int(e.get("quantity", 1) or 1)
            except (TypeError, ValueError):
                menge = 1
            out.append({"tid": int(e.get("type_id") or 0), "menge": menge,
                        "ort": ort, "besitzer": besitzer, "art": art,
                        "flag": flag, "pfad": list(pfad), "item_id": iid})
            if ist_behaelter(e):
                for c in by_parent.get(iid, []):
                    stack.append((c, pfad + [iid]))
    return [z for z in out if z["tid"] > 0]


def behaelter_ids(zeilen):
    """Alle Behaelter-item_ids, die in Pfaden vorkommen (fuer die Namen)."""
    out = set()
    for z in zeilen or []:
        out.update(z.get("pfad") or [])
    return out


def behaelter_typen(zeilen):
    """{item_id: type_id} der Behaelter in den Pfaden - ein Behaelter ohne
    eigenen Namen heisst in der Anzeige nach seinem Typ ("Station Container")."""
    ids = behaelter_ids(zeilen)
    return {z["item_id"]: z["tid"] for z in zeilen or []
            if z.get("item_id") in ids}


def umstrittene_tids(plaene):
    """{type_id, ...} - von MINDESTENS ZWEI der uebergebenen Plaene selbst
    gebaut (emm626). Fuer sie darf ein GERATENER (nicht per job_zuordnung
    bestaetigter) abgelieferter ESI-Job keinem der beiden gutgeschrieben
    werden - ESI sagt nicht, welcher Plan ihn gestartet hat (dieselbe Regel
    wie `_umstrittene_items` im Bauplan, hier aber ueber ALLE Plaene dieser
    Seite auf einmal statt je einem offenen Dialog)."""
    from .ui.mw_helpers import MainWindowHelpers as _MH
    bauer = {}
    for p in plaene or []:
        for t in _MH.plan_baut_items(p):
            try:
                t = int(t)
            except (TypeError, ValueError):
                continue
            bauer[t] = bauer.get(t, 0) + 1
    return {t for t, n in bauer.items() if n > 1}


def delivered_geraten(frozen_ts, plan_runs, delivered_jobs, recipes,
                      vergeben=None, plan_id=None):
    """{type_id: Runs} - ESI-Jobs, die seit `frozen_ts` abgeliefert wurden
    und zu den Runs dieses Plans (`plan_runs`, aus `build_runs`) passen
    (emm626, dieselbe Grundannahme wie `_frozen_auto_checked` im Bauplan -
    NUR OHNE SCHEDULER-LAUF: die Aktivitaet des Produkts, Reaktion 9/11
    oder Fertigung 1, kommt direkt aus den globalen Rezepten
    (`recipes.product_to_bp[tid][1]`), nicht aus einer frisch gerechneten
    Runplaner-Zuteilung - die kann diese Seite nicht fuer jeden ange-
    zeigten Plan einzeln neu rechnen, ohne Charaktere/Slots/Blaupausen-
    Deckel jedes Plans zu laden. GERATEN bleibt es trotzdem: welchem Plan
    ein Job gehoert, weiss nur `delivered_sicher` ueber Deckel + Streit.

    FREMD ZUGEORDNETE JOBS ZAEHLEN NICHT (emm791, Audit 31.10.2026 -
    dieselbe Regel wie `_frozen_auto_checked`): `vergeben`
    ({job_id: plan_id}) + `plan_id` sieben Jobs aus, die laut Zuordnung
    einem ANDEREN Plan oder ausdruecklich KEINEM gehoeren."""
    try:
        _fts = float(frozen_ts)
    except (TypeError, ValueError):
        return {}
    _runs = {int(t): int(r or 0) for t, r in (plan_runs or {}).items()}
    if not _runs or recipes is None:
        return {}
    from .ui.mw_helpers import MainWindowHelpers as _MH
    _p2b = getattr(recipes, "product_to_bp", None) or {}
    _eig_id = None if plan_id is None else str(plan_id)
    out = {}
    for j in (delivered_jobs or []):
        try:
            tid = int(j.get("product_type_id"))
        except (TypeError, ValueError):
            continue
        if _runs.get(tid, 0) <= 0:
            continue
        if vergeben is not None and j.get("job_id") is not None:
            try:
                _wem = vergeben.get(int(j.get("job_id")))
            except (TypeError, ValueError):
                _wem = None
            if _wem is not None and str(_wem) != _eig_id:
                continue
        _rez = _p2b.get(tid)
        _ist_react = bool(_rez) and _rez[1] in (9, 11)
        _akt_job = j.get("activity_id")
        if _ist_react:
            if _akt_job not in (9, 11):
                continue
        elif _akt_job != 1:
            continue
        cts = _MH._iso_job_ts(j.get("completed_date"))
        if cts is None or cts < _fts:
            continue
        out[tid] = out.get(tid, 0) + int(j.get("runs") or 0)
    return out


def gebaute_runs(plan, zuordnung=None, extra=None, delivered_jobs=None,
                  recipes=None, umstritten=None, frozen_ts=None,
                  plan_runs=None):
    """{type_id: schon gebaute Runs} eines gespeicherten Plans - OHNE ESI,
    nur aus dem, was lokal belegt ist (emm463).

    Zwei Quellen, je Item das MAXIMUM (sie meinen dieselben Runs, nicht
    zwei verschiedene - genau wie `_rest_geliefert_jetzt` im Bauplan):
      * die ESI-Jobs, die laut `job_zuordnung` DIESEM Plan gehoeren
        (`zuordnung` = store.job_zuordnung_details()) - laufende zaehlen
        mit, ihr Material ist im Spiel laengst verbraucht (emm422),
      * die Hand-Haken des Runplaners (`checked_runplan_runs`,
        {"stufe|tid": Runs}).

    DRITTE QUELLE, NUR WENN `delivered_jobs`/`recipes`/`frozen_ts`
    mitgegeben werden (emm626, Nutzer: "ich hatte mal alle Materialien
    gruen, dann fehlt immer wieder Zeug, fast so als ob der Runplaner
    einfach manchmal quatsch angiebt"): GERATENE Ablieferungen seit dem
    Einfrieren (`delivered_geraten`), gedeckelt auf die Plan-Runs und bei
    `umstritten`-Items VERWORFEN, es sei denn `zuordnung`/`extra` haben sie
    bereits BELEGT (`delivered_sicher`). Ohne diese Quelle blieb diese
    Seite auf dem Stand des letzten Haekchens/der letzten eindeutigen
    Job-Zuordnung stehen, waehrend der Bauplan selbst (ueber dieselbe
    Grundannahme, nur mit einer frisch gerechneten Runplaner-Zuteilung
    statt den globalen Rezepten) laengst mehr Fortschritt sah - zwei
    Karten auf verschiedenem Stand sehen aus wie "mal gruen, mal rot ohne
    Grund", obwohl beide fuer sich konsistent rechnen.
    """
    aus_jobs, aus_haken = {}, {}
    _pid = (plan or {}).get("id")
    for _j, e in (zuordnung or {}).items():
        if str((e or {}).get("plan_id")) != str(_pid):
            continue
        try:
            t = int(e.get("type_id") or 0)
            r = int(e.get("runs") or 0)
        except (TypeError, ValueError):
            continue
        if t > 0 and r > 0:
            aus_jobs[t] = aus_jobs.get(t, 0) + r
    for k, v in ((plan or {}).get("checked_runplan_runs") or {}).items():
        try:
            t = int(str(k).split("|")[-1])
            r = int(v or 0)
        except (TypeError, ValueError):
            continue
        if t > 0 and r > 0:
            aus_haken[t] = aus_haken.get(t, 0) + r
    # DER HAKEN GILT AUCH HIER NUR, BIS ESI WIDERSPRICHT (emm749).
    # DRITTES VORKOMMEN DERSELBEN URSACHE. emm747 hat die Regel heute
    # frueh fuer `_rest_geliefert_jetzt` gebaut, emm748 fuer den
    # Nachlauf-Ofen - und DIESE Stelle, die Stock Locations speist,
    # stand sogar woertlich in der emm747-Dokumentation ("`gebaute_runs`
    # zaehlt einen Haken als GEBAUT (`max(aus_jobs, aus_haken)`)") und
    # blieb trotzdem liegen. Arbeitsregel 9 heisst: alle Vorkommen.
    #
    # SEIN BEFUND (28.10.2026): "nur dafür habe ich tatsächlich zu wenig
    # Material um es nachzubauen, aber Stock Location sieht es nicht und
    # der Bauplan auch nicht" - und zuvor "warum hat mir stok locations
    # gestern zu wenig material zu kaufen angegeben?".
    # GEMESSEN an seiner settings.json, Plan "Minmatar 1": die Haken auf
    # Fernite Carbide (319 Runs) und Fermionic Condensates sind 192
    # STUNDEN alt - acht Tage. Die Haken-Frist betraegt 65 Minuten. Ohne
    # Kappung zaehlte `max()` diese Runs unbefristet als gebaut, ihr
    # Material fiel aus dem Bedarf, und die Einkaufsliste nannte zu
    # wenig. Genau sein Catalyst-Fall vom 27./28.10. (3'459'456
    # Tritanium), nur an der Stelle, die ihn wirklich verursacht hat.
    #
    # Gekappt wird nur, wenn der Plan Zeitstempel mitbringt
    # (`checked_runplan_ts`). Fehlen sie - alte Plaene, fremde Aufrufer -,
    # bleibt es beim bisherigen Verhalten (Regel 3: lieber das alte
    # Ergebnis als gar keines).
    _haken_wirk = dict(aus_haken)
    _ts_roh = (plan or {}).get("checked_runplan_ts") or {}
    if aus_haken and _ts_roh:
        try:
            from .ui.mw_helpers import (haken_pruefen as _hp749,
                                        haken_wirksam as _hw749)
            _ts749 = {}
            for _k, _v in _ts_roh.items():
                # Derselbe Schluessel-Schnitt wie oben bei `aus_haken`
                # und wie in `_haken_stand_jetzt`: hinten steht die
                # type_id. Zeilen der Bauart "char|stufe|char_id" tragen
                # dort eine Charakter-Id - die ist keine Bau-Stufe
                # dieses Plans und faellt beim Abgleich unten durch.
                try:
                    _t749 = int(str(_k).rpartition("|")[2])
                    _f749 = float(_v)
                except (TypeError, ValueError):
                    continue
                if _t749 in aus_haken:
                    _ts749[_t749] = max(_ts749.get(_t749, 0.0), _f749)
            # BELEG = die zugeordneten ESI-Jobs. `geliefert` und
            # `laufend` sind in `aus_jobs` bereits zusammengefasst
            # (emm422: ein laufender Job hat sein Material verbraucht),
            # deshalb steht alles im ersten Topf - `haken_pruefen`
            # addiert beide und kaeme sonst auf das Doppelte.
            # Ein Haken OHNE Zeitstempel bekommt keinen Eintrag in
            # `_ts749` und gilt damit als unbefristet gueltig, also wie
            # bisher - die sichere Richtung fuer alte Plaene.
            _st749 = _hp749({_t: _n for _t, _n in aus_haken.items()
                             if _t in _ts749},
                            _ts749, aus_jobs, {}, _time.time(),
                            plan_runs=plan_runs)
            _wk749, _ = _hw749(_st749)
            for _t, _n in _wk749.items():
                _haken_wirk[_t] = int(_n)
        except Exception:
            # Eine Kappung, die scheitert, darf die Seite nicht
            # zerreissen - dann gilt der Haken wie vor emm749.
            _haken_wirk = dict(aus_haken)
    out = {t: max(aus_jobs.get(t, 0), _haken_wirk.get(t, 0))
           for t in set(aus_jobs) | set(aus_haken)}
    # NOCH NICHT ZUGEORDNETE, aber EINDEUTIGE Jobs (emm475): sie sind ein
    # zusaetzlicher Beleg, nicht derselbe - deshalb ADDIERT, nicht Maximum.
    # Der Deckel auf die Plan-Runs kommt aus `restbedarf_map` (offen =
    # max(0, Plan - gebaut)), es kann also nie "mehr als geplant" werden.
    for t, r in (extra or {}).items():
        try:
            t = int(t)
            r = int(r or 0)
        except (TypeError, ValueError):
            continue
        if r > 0:
            out[t] = out.get(t, 0) + r
    # GERATENE ABLIEFERUNGEN SEIT DEM EINFRIEREN (emm626) - MAXIMUM wie
    # aus_jobs/aus_haken (dieselben Runs, nicht zusaetzliche): `belegt=out`
    # gibt `delivered_sicher` genau das bereits BESTAETIGTE weiter, damit
    # ein umstrittenes Item trotzdem zaehlt, sobald eine Job-Zuordnung oder
    # ein Haken es diesem Plan eindeutig zuspricht.
    if delivered_jobs is not None and recipes is not None and frozen_ts:
        from .ui.mw_helpers import delivered_sicher as _delivered_sicher626
        # emm791: Jobs, die laut Zuordnung einem anderen Plan (oder
        # "keinem") gehoeren, raten wir hier gar nicht erst mit.
        _vergeben791 = ({int(_j): (_e or {}).get("plan_id")
                         for _j, _e in (zuordnung or {}).items()}
                        if zuordnung else None)
        _geraten = delivered_geraten(frozen_ts, plan_runs, delivered_jobs,
                                      recipes, vergeben=_vergeben791,
                                      plan_id=_pid)
        _sicher = _delivered_sicher626(_geraten, plan_runs, umstritten,
                                        belegt=out)
        for t, r in _sicher.items():
            out[t] = max(out.get(t, 0), r)
    return out


def unzugeordnete_runs(jobs, plaene, vergeben, fremde_bauer=None):
    """({plan_id: {tid: Runs}}, [offene Jobs]) - Jobs, die MATERIAL AUS DEM
    HANGAR gefressen haben, aber in `job_zuordnung` noch keinem Plan
    gehoeren (emm475).

    DER SCHADEN, der das ausgeloest hat (Nutzer 08.10.2026): "ja toll jetzt
    habe ich schon nachgekauft, das darf auf keinen fall jemals wieder
    passieren". Vier laufende Jobs "Large Energy Locus Coordinator II"
    (je 10 Runs, 07.10. 18:47) gehoerten keinem Plan - ihr Material war im
    Spiel weg, Riggs 1 senkte seinen Bedarf aber nicht, weil die Zuordnung
    nur beim Aufbau des RUNPLANERS laeuft und das letzte Mal eine Minute
    VOR ihrem Start lief. Ergebnis: 888 / 772 / 624 roter Fehlbetrag -
    und ein unnoetiger Nachkauf.

    DIE REGEL IST DIESELBE wie "eindeutig" in der Job-Zuordnung (emm427):
    baut GENAU EIN Plan dieses Item, gehoert der Job ihm. Zaehlt werden
    darf nur, was eindeutig ist - alles andere kommt als `offen` zurueck
    und wird auf der Seite als WARNUNG gezeigt. So gibt es keinen stillen
    zu hohen Fehlbetrag mehr: entweder mitgezaehlt oder sichtbar gemeldet.

    `jobs`: ESI-Jobs mit job_id/activity_id/product_type_id/runs/start_date
            (auch geliefert - was verbraucht ist, bleibt verbraucht).
    `plaene`: die eingefrorenen, offenen Plaene dieser Seite.
    `vergeben`: {job_id: plan_id} aus `store.job_zuordnung_alle`.
                "-" = der Nutzer hat "zu keinem Plan" geantwortet: dann
                zaehlt der Job nicht und wird auch nicht gemeldet.
    `fremde_bauer`: type_ids, die NOCH ANDERE offene Plaene bauen (auch
                nicht eingefrorene) - damit ist es nicht eindeutig.
    """
    treffer, offen = zuteilbare_jobs(jobs, plaene, vergeben, fremde_bauer)
    zu = {}
    for _jid, _pid, _tid, _runs, _akt in treffer:
        _z = zu.setdefault(_pid, {})
        _z[_tid] = _z.get(_tid, 0) + _runs
    return zu, offen


def zuteilbare_jobs(jobs, plaene, vergeben, fremde_bauer=None):
    """([(job_id, plan_id, type_id, runs, activity_id)], [offene Jobs]) -
    die EINE Stelle, die entscheidet, welcher nicht zugeordnete Job zu
    welchem Plan gehoert (emm478).

    `unzugeordnete_runs` zaehlt daraus nur zusammen; die Seite schreibt die
    Treffer zusaetzlich dauerhaft in `job_zuordnung` fest (Nutzer-Entscheid
    08.10.2026: "still festschreiben"). Vorher lief die Zuordnung NUR beim
    Aufbau des Runplaners eines Plans - wer 30 Jobs startet und den Plan
    nicht oeffnet, hatte sie nirgends (gemessen: Modules 1 Multiplan,
    Warp Scrambler II, Spalte JOBS 0 bei 30 laufenden Jobs).
    """
    from .ui.mw_helpers import MainWindowHelpers as _MH
    treffer, offen = [], []
    # JE JOB EINMAL (gefunden von b194, 08.10.2026): ESI liefert denselben
    # Job bei mehreren Charakteren (Corp-Jobs, emm389) - zweimal gezaehlt
    # waere der Bedarf ZU KLEIN, also zu wenig Material. Dieselbe Regel wie
    # `corp_jobs_verteilen`: Dedupe ueber job_id, ein Job ohne job_id zaehlt
    # gar nicht (ohne Kennung ist nicht entscheidbar, ob er doppelt ist).
    gesehen = set()
    _fremd = {int(t) for t in (fremde_bauer or set())}
    # Wer baut was? NUR ueber die Bau-Runs des Schnappschusses
    # (plan_baut_items, emm427) - ein Plan, der ein Item nur VERBRAUCHT,
    # startet dafuer keinen Job.
    bauer = {}
    frost = {}
    for p in plaene or []:
        _pid = str((p or {}).get("id"))
        try:
            frost[_pid] = float(((p or {}).get("frozen") or {}).get("ts") or 0)
        except (TypeError, ValueError):
            frost[_pid] = 0.0
        for t in _MH.plan_baut_items(p):
            bauer.setdefault(int(t), []).append(_pid)
    for j in jobs or []:
        try:
            akt = int((j or {}).get("activity_id") or 0)
            tid = int((j or {}).get("product_type_id") or 0)
            runs = int((j or {}).get("runs") or 0)
        except (TypeError, ValueError):
            continue
        if akt not in (1, 9, 11) or tid <= 0 or runs <= 0:
            continue        # Forschung/Kopieren/Invention nehmen nichts hier
        _jid = (j or {}).get("job_id")
        if _jid is None:
            continue
        try:
            _jid = int(_jid)
        except (TypeError, ValueError):
            continue
        if _jid in gesehen:
            continue
        gesehen.add(_jid)
        _v = str((vergeben or {}).get(_jid, "") or "")
        if _v:
            continue        # schon zugeordnet oder "zu keinem Plan"
        kand = list(bauer.get(tid) or [])
        if not kand:
            continue        # kein Plan baut das - sein Fehlbetrag ist echt
        _ts = _MH._iso_job_ts((j or {}).get("start_date"))
        # NUR DER LAUFENDE DURCHLAUF (emm476, Nutzer: "jetzt ist es noch
        # schlimmer geworden" - die Seite meldete 218 Jobs, die "keinem Plan
        # gehoeren"): ein Job, der VOR dem Einfrieren JEDES in Frage
        # kommenden Plans gestartet wurde, gehoert zu einem frueheren
        # Durchlauf - er hat das Material von damals genommen, nicht das von
        # heute. Vorher wurde so ein Job gemeldet, sobald zwei Plaene das
        # Item bauen; mit den abgelieferten Jobs mehrerer Monate wurde die
        # Warnung dadurch unlesbar - und eine unlesbare Warnung ist keine.
        # Die Pruefung steht VOR der Eindeutigkeit, damit ein alter Plan
        # einen heutigen Job nicht mehrdeutig macht.
        if _ts is not None:
            kand = [p for p in kand if _ts >= frost.get(p, 0.0)]
            if not kand:
                continue
        if len(kand) > 1 or tid in _fremd or _ts is None:
            offen.append(j)
            continue
        treffer.append((_jid, kand[0], tid, runs, akt))
    return treffer, offen


def bedarf_aus_plaenen(plaene, zuordnung=None, extra_runs=None, out_qty=None,
                        delivered_jobs=None, recipes=None, umstritten=None):
    """{type_id: [(plan_label, menge)]} - was die NOCH OFFENEN Runs der
    uebergebenen Plaene an Material brauchen (Zutaten aller Bau-Schritte +
    Datacores/Decryptoren), aus dem eingefrorenen Schnappschuss.
    Endprodukte sind kein Bedarf; Plaene ohne Schnappschuss liefern nichts.

    emm463 (Nutzer: "von allen aktiven Bauplaenen bin ich schon beim
    Endprodukt, ich braeuchte nichts mehr - da steht aber viel auf Rot"):
    vorher stand hier die VOLLE Planmenge. Wer seine Vorstufen laengst
    gebaut hat, sah damit fuer jedes verbaute Material einen Fehlbetrag.

    emm527, NUTZER 11.10.2026, zwei Beschwerden und ZWEI Messungen:

      (a) "Das alles fehlt mir, wenn ich die Einkaufslisten zusammenrechne.
          Stock locations will aber viel weniger kaufen." GEMESSEN: die
          Keule `selbst_gebaut` (emm465: "baut auch nur EIN Plan es, bleibt
          es draussen") galt ueber ALLE Plaene - sie traf auch Plaene, die
          dasselbe Teil ZUKAUFEN. Hangar Cleaner braucht 110 R.A.M.-
          Armor/Hull Tech und baut davon 0; die Zeile war trotzdem nie rot,
          weil Riggs 1 sie baut. BEHOBEN: die Regel gilt JE PLAN. Wer ein
          Teil selbst baut, meldet dafuer keinen Bedarf (sein Nachschub
          kommt aus der eigenen Produktion) - wer es kauft, meldet ihn.

      (b) Der erste Versuch ging weiter und rechnete hier dieselbe Bilanz
          wie die Einkaufsliste (`fehlbedarf_vorschau`, Eigenbau anteilig
          gutgeschrieben). DAS WAR FALSCH und ist zurueckgenommen - sein
          Bildschirm meldete danach 30 fehlende Posten, darunter 133'254
          Rolled Tungsten Alloy und 721 Datacores ("das ist nicht moeglich,
          ich habe fast 60 Bauschleifen belegt" / "ich habe alle T2
          Blueprints schon inventet"). GEMESSEN, warum: diese Seite kennt
          den Baufortschritt viel schlechter als der Bauplan. Ihre Quelle
          ist nur `gebaute_runs` (Job-Zuordnung + Haken); bei Riggs 1 standen
          damit alle fuenf Endprodukte auf 200/200 offen und ganze 2 Items
          galten als gebaut. Die Einkaufsliste nutzt dagegen
          `_rest_geliefert_jetzt`: sicher gelieferte UND laufende Jobs,
          Vorstufen-Regel, Bestandsdeckung. Mit der duennen Karte wird aus
          der anteiligen Gutschrift eine Fantasiezahl: ein fertig gebautes
          Zwischenprodukt hat 0 offene Runs (= keine Gutschrift), waehrend
          seine Verbraucher als voll offen gelten.
          -> Solange diese Seite den Fortschritt nicht so gut kennt wie der
          Bauplan, nimmt sie die SICHERE Annahme: was ein Plan selbst baut,
          deckt er selbst. Lieber eine Zeile zu wenig als ein Fehlkauf -
          den genauen Rest zeigt der Bauplan selbst (Regel 3).

    OFFEN (eigene Messung): die Erledigt-Karte dieser Seite auf denselben
    Stand bringen wie `_rest_geliefert_jetzt`. Erst dann darf hier anteilig
    gerechnet werden.

    `out_qty` wird nicht mehr gebraucht und bleibt nur, damit die Aufrufer
    unveraendert bleiben koennen.

    emm626 (Nutzer: "einkaufsliste und stock locations behaupten
    wiedermal etwas unterschiedliches" / Ziel: "ueber die
    Gesamteinkaufsliste aller Baupläne im Stock Locations Tab einkaufen
    kann ich alles auf einmal und es passt dann"): `delivered_jobs`,
    `recipes`, `umstritten` sind NEU und optional - geben sie
    `gebaute_runs()` eine DRITTE Quelle (gedeckelt-und-strittig-sichere
    ESI-Ablieferung seit dem Einfrieren, dieselbe Bauart wie
    `delivered_sicher()` im Bauplan selbst). Das ist KEIN anteiliges
    Gutschreiben wie der zurueckgenommene Versuch in (b) oben - nur ein
    staerkeres Signal fuer dieselbe, bereits bestehende max()-Kombination.
    Wird keiner der drei Parameter uebergeben, verhaelt sich die Funktion
    exakt wie vorher (reines `zuordnung`/`extra`).
    """
    from .ui.mw_helpers import MainWindowHelpers as _MH, restbedarf_map
    _umstritten626 = umstritten if umstritten is not None else umstrittene_tids(plaene)
    out = {}
    for p in plaene or []:
        snap = ((p or {}).get("frozen") or {}).get("plan_snapshot")
        if not isinstance(snap, dict):
            continue
        try:
            plan = _MH._plan_snapshot_unpack(snap)
        except Exception:
            continue
        label = str(p.get("label") or p.get("item_name") or p.get("id") or "?")
        _runs = {int(t): int(r or 0)
                 for t, r in (plan.get("build_runs") or {}).items()}
        _gebaut = gebaute_runs(
            p, zuordnung, (extra_runs or {}).get(str(p.get("id"))),
            delivered_jobs=delivered_jobs, recipes=recipes,
            umstritten=_umstritten626,
            frozen_ts=((p.get("frozen") or {}).get("ts")),
            plan_runs=_runs)
        _mats = {int(t): v for t, v in (plan.get("build_mats") or {}).items()}
        rem, summe = restbedarf_map(_runs, _mats, _gebaut)
        # WAS DIESER PLAN SELBST BAUT, MELDET ER NICHT (emm527 (a)+(b)):
        # je Plan, nicht mehr global ueber alle. Ein Plan, der dasselbe Teil
        # ZUKAUFT, meldet seinen Bedarf weiter - genau sein R.A.M.-Fall.
        for _sb in list(summe):
            if int(_runs.get(int(_sb), 0) or 0) > 0:
                summe.pop(_sb, None)
        # OHNE Run-Zahl kein Anteil: ein alter Schnappschuss ohne
        # `build_runs` wuerde sonst GAR KEINEN Bedarf melden. Dann zaehlt
        # das Material dieses Schrittes voll (Regel 3 - lieber zu viel).
        for _t, _ml in _mats.items():
            if int(_runs.get(int(_t), 0) or 0) > 0:
                continue
            for m, q in _ml or []:
                try:
                    summe[int(m)] = summe.get(int(m), 0) + int(q or 0)
                except (TypeError, ValueError):
                    continue
        # DATACORES/DECRYPTOREN: Anteil = groesster offener Rest der
        # ENDPRODUKTE, und 0 sobald der Plan baut. Invention laeuft VOR dem
        # Bau - wer schon baut, hat seine Kopien (emm465). Der Versuch,
        # hier den vollen Bedarf zu zeigen, ist zurueckgenommen: sein
        # Bildschirm meldete 721 fehlende Datacores, obwohl er alle T2
        # laengst inventet hat ("fast nicht moeglich"). Den genauen Rest
        # rechnet der Invention-Reiter des Plans ueber die ESI-Jobs (emm431).
        _enden = [int(t) for t, _q in (p.get("enden") or [])] or \
            ([int(p["type_id"])] if p.get("type_id") else [])
        _anteil = 0.0
        for _e in _enden:
            _r = int(_runs.get(_e, 0) or 0)
            if _r > 0:
                _anteil = max(_anteil, rem.get(_e, 0) / _r)
        if not _enden or not any(int(_runs.get(_e, 0) or 0) > 0 for _e in _enden):
            _anteil = 1.0
        import math as _math
        if _gebaut:
            _anteil = 0.0
        for feld in ("inv_buy", "inv_stock_used"):
            for m, q in (plan.get(feld) or {}).items():
                try:
                    _q = _math.ceil(int(q or 0) * _anteil)
                except (TypeError, ValueError):
                    continue
                if _q > 0:
                    summe[int(m)] = summe.get(int(m), 0) + _q
        for m, q in summe.items():
            if q > 0:
                out.setdefault(int(m), []).append((label, int(q)))
    return out


def plaene_fuer_lagerorte(settings):
    """Gespeicherte, EINGEFRORENE, nicht abgeschlossene Plaene (Nutzer
    07.10.2026: "nur fuer gespeicherte und eingefrorene Plaene") - ohne
    Buendel-Mitglieder (die zaehlt das Buendel). Kein Schloss noetig."""
    from .ui.mw_helpers import MainWindowHelpers as _MH
    plans = list((settings or {}).get("bau_saved_plans") or [])
    try:
        mitglieder = set(_MH.buendel_mitglieder(settings))
    except Exception:
        mitglieder = set()
    out = []
    for p in plans:
        if not isinstance(p, dict) or p.get("done_manual"):
            continue
        if str(p.get("id")) in mitglieder or p.get("id") in mitglieder:
            continue
        if not ((p.get("frozen") or {}).get("plan_snapshot")):
            continue
        out.append(p)
    return out


def suchbegriffe(text):
    """Suchfeld -> Menge kleingeschriebener Namen. Mehrzeilig (Hangar-Kopie
    mit Tab + Menge, Einkaufsliste "Name<TAB>Menge") wird je Zeile der
    Item-Name genommen (store.hangar_name: erste Tab-Spalte, '*' weg)."""
    from .store import hangar_name
    out = set()
    for zeile in str(text or "").splitlines():
        n = hangar_name(zeile).strip().lower()
        if n:
            out.add(n)
    return out


def passt(name, begriffe):
    """Ein Item passt, wenn ein Begriff in seinem Namen vorkommt - oder bei
    genau EINEM Begriff auch als Teilwort (Tippen)."""
    if not begriffe:
        return True
    n = str(name or "").lower()
    return any(b in n for b in begriffe)


def baum(zeilen, namen, ort_namen, besitzer_namen, behaelter_namen,
         bedarf=None, nur_tids=None, begriffe=None, lag=None,
         fremd_abzug=None, eigen_schutz=None):
    """Zeilen -> Baum fuer die Anzeige, Item zuerst (Nutzer: "Item zuerst").

    -> [{"tid", "name", "menge", "bedarf": [(plan, menge)], "short": n,
         "orte": [{"ort", "name", "menge",
                   "besitzer": [{"besitzer", "name", "art", "menge",
                                 "pfade": [(["Box A", "Box B"], menge)]}]}]}]
    Sortiert: Items mit Bedarf zuerst (groesster Fehlbetrag oben), dann nach
    Name; Orte und Besitzer nach Menge absteigend.
    `nur_tids`: nur diese Items (None = alle), `begriffe`: Namenssuche
    (siehe suchbegriffe) - mit Begriffen gilt `nur_tids` nicht, die Suche
    findet jedes Item.

    KEINE SONDERREGEL FUER SELBSTGEBAUTES mehr (emm527): bis dahin stand
    hier `selbst_gebaut` - eine Liste von Items, die NIE einen Fehlbetrag
    bekamen, weil irgendein Plan sie selbst baut (emm465). Gemessen hat das
    63 Posten verschluckt, auch bei Plaenen, die dasselbe Teil zukaufen.
    Die Gutschrift steht jetzt dort, wo sie hingehoert: im Bedarf je Plan
    (`bedarf_aus_plaenen`), anteilig statt alles-oder-nichts. Was hier
    ankommt, ist bereits der NETTO-Bedarf - `short` ist wieder einfach
    "Bedarf minus Bestand".

    `lag` (emm620, s. `_lager_laden`/`mw_helpers.lag_verbrauch`): {tid:
    Menge}, die Jobs NACH dem letzten ESI-Bestandsstand schon verbraucht
    haben - im Spiel weg, aber in `zeilen` (ESI, bis zu 1 h gecacht) noch
    sichtbar. NUTZER: "Moma sagt ich haette genuegend Material aber ingame
    kan ich die letzten 2 Runs von Tungsten Carbide wiedermal nicht
    machen" - 3 von 5 Blaupausenkopien liefen schon, ihr Material war im
    Hangar weg, der ESI-Bestand zeigte es (noch) voll. `short` zaehlte
    gegen den VOLLEN `it_menge`, meldete also faelschlich "genug". Jetzt
    wird vom Bestand abgezogen, was laut `lag` schon weg ist, bevor
    verglichen wird - NUR fuer den Vergleich, `menge` in der Anzeige bleibt
    der ehrliche ESI-Wert (Regel 8, Nutzer soll sehen, was ESI wirklich
    meldet)."""
    bedarf = bedarf or {}
    lag = lag or {}
    agg = {}
    for z in zeilen or []:
        tid = int(z["tid"])
        if begriffe:
            if not passt(namen.get(tid, f"#{tid}"), begriffe):
                continue
        elif nur_tids is not None and tid not in nur_tids:
            continue
        pf = tuple(behaelter_namen.get(i) or f"#{i}" for i in (z.get("pfad") or []))
        k = (tid, int(z.get("ort") or 0), (z.get("art"), z.get("besitzer")), pf)
        agg[k] = agg.get(k, 0) + int(z.get("menge") or 0)
    items = {}
    for (tid, ort, bes, pf), m in agg.items():
        it = items.setdefault(tid, {})
        o = it.setdefault(ort, {})
        b = o.setdefault(bes, {})
        b[pf] = b.get(pf, 0) + m
    out = []
    for tid, orte in items.items():
        it_menge = 0
        orte_l = []
        # WIE VIEL LIEGT NICHT LOSE IM HANGAR? (emm770) Nutzer 30.10.2026
        # mit Spiel-Bildschirmfoto: "mir fehlt Tritanium obwohl Bauplan
        # und Stocklocations sagt, ich habe alles". GEMESSEN an seinem
        # Fall: Eve MoMa zaehlte 51'638'400 an Bau-Strukturen, das Spiel
        # bot 48'656'779 an - die Differenz war AUF DIE EINHEIT der
        # Inhalt EINES Containers (2'981'621 bei Peanut Motor auf
        # Dockside). Ein Industry-Job zieht nur aus dem ITEM-HANGAR;
        # was in einer Kiste liegt, muss erst ausgepackt werden. Die
        # Zahl bleibt richtig (es IST sein Material), sie braucht nur
        # die Fussnote. Ein nicht-leerer `pfad` heisst "in einem
        # Behaelter" - das gilt auch fuer die synthetischen
        # Vertrags-Behaelter aus emm760, und zwar zu Recht: Ware in
        # einem offenen Vertrag kann ein Job genauso wenig nehmen.
        it_verpackt = 0
        for ort, bes_map in orte.items():
            o_menge = 0
            bes_l = []
            for (art, besitzer), pf_map in bes_map.items():
                bm = sum(pf_map.values())
                o_menge += bm
                it_verpackt += sum(q for pf, q in pf_map.items() if pf)
                bes_l.append({"besitzer": besitzer, "art": art,
                              "name": besitzer_namen.get((art, besitzer))
                              or besitzer_namen.get(besitzer) or str(besitzer),
                              "menge": bm,
                              "pfade": sorted(((list(p), q) for p, q in pf_map.items()),
                                              key=lambda x: (-x[1], x[0]))})
            it_menge += o_menge
            bes_l.sort(key=lambda x: (-x["menge"], x["name"]))
            orte_l.append({"ort": ort, "name": ort_namen.get(ort) or f"#{ort}",
                           "menge": o_menge, "besitzer": bes_l})
        orte_l.sort(key=lambda x: (-x["menge"], x["name"]))
        bd = list(bedarf.get(tid) or [])
        ges = sum(q for _, q in bd)
        # FREMDE ANSPRUECHE ZAEHLEN AUCH HIER (emm789, Audit 31.10.2026,
        # KRITISCH K1/M1): `short` verglich gegen den vollen Rohbestand -
        # mit Einzelplan-Dropdown meldete die Einkaufsliste "0 fehlt",
        # obwohl ein zweiter Plan dieselben 100 Stueck beansprucht, und
        # reservierte, nie eingefrorene Plaene fehlten der Seite komplett.
        # DIESELBE faire Aufteilung wie bestand_nach_reservierungen
        # (mw_helpers): verfuegbar = max(Basis - fremd, min(eigen, Basis)).
        _basis789 = it_menge - int(lag.get(tid, 0) or 0)
        _fr789 = int((fremd_abzug or {}).get(tid, 0) or 0)
        _ei789 = int((eigen_schutz or {}).get(tid, 0) or 0)
        _verfuegbar = max(0, max(_basis789 - _fr789, min(_ei789, _basis789)))
        out.append({"tid": tid, "name": namen.get(tid, f"#{tid}"),
                    "menge": it_menge, "bedarf": bd,
                    "short": max(0, ges - _verfuegbar) if bd else 0,
                    # emm770: davon in Behaeltern/Vertraegen - ein Job
                    # im Spiel kann nur den losen Hangar-Anteil nehmen.
                    "verpackt": it_verpackt,
                    "orte": orte_l})
    # Items mit Bedarf, aber OHNE Bestand sollen trotzdem erscheinen
    # (sonst sieht man nicht, dass etwas ganz fehlt).
    if not begriffe:
        for tid, bd in bedarf.items():
            if tid in items or (nur_tids is not None and tid not in nur_tids):
                continue
            ges = sum(q for _, q in bd)
            if ges > 0:
                out.append({"tid": tid, "name": namen.get(tid, f"#{tid}"),
                            "menge": 0, "bedarf": list(bd),
                            "short": ges, "verpackt": 0, "orte": []})
    out.sort(key=lambda x: (0 if x["bedarf"] else 1, -x["short"], x["name"]))
    return out


def orte_mit_bestand(zeilen, ort_namen=None):
    """[(ort_id, Name, Menge)] - alle Orte, an denen etwas liegt, Menge
    absteigend (emm461: die Liste rechts, in der man Orte an- und abwaehlt).
    Unabhaengig von Bedarf und Suche: ein Ort verschwindet nicht aus der
    Liste, nur weil dort gerade kein Plan-Material liegt."""
    summe = {}
    for z in zeilen or []:
        o = int(z.get("ort") or 0)
        summe[o] = summe.get(o, 0) + int(z.get("menge") or 0)
    namen = ort_namen or {}
    out = [(o, namen.get(o) or f"#{o}", m) for o, m in summe.items()]
    out.sort(key=lambda x: (-x[2], x[1]))
    return out


def karten(zeilen, namen, ort_namen, besitzer_namen, behaelter_namen,
           bedarf=None, nur_tids=None, begriffe=None, nur_orte=None, lag=None,
           fremd_abzug=None, eigen_schutz=None):
    """Dieselben Daten wie `baum`, aber JE ORT gebuendelt - eine Karte je
    Station/Struktur (emm461, Nutzer: "ich haette lieber die Locations als
    Karten ... meistens hat man nur 4-5 Baustrukturen").

    -> ([{"ort", "name", "menge", "short", "items": [{"tid", "name",
          "menge" (AN DIESEM ORT), "gesamt" (ueberall), "bedarf", "short",
          "besitzer": [...]}]}], fehlt_ganz)
    `fehlt_ganz` = Bedarf, der an keinem gewaehlten Ort liegt (eigene Karte).

    `nur_orte` (None = alle): abgewaehlte Orte zaehlen NIRGENDS mit, auch
    nicht im Fehlbetrag - wer Jita abwaehlt, sieht, was ihm an seinen
    Bau-Strukturen wirklich fehlt (mehr Fehlbetrag ist die sichere
    Richtung, Regel 3).

    Sortierung: Karten mit den meisten fehlenden Items zuerst (Handlungs-
    bedarf, wie die Job-Karten), dann die mit den meisten Items; in der
    Karte die Items mit Fehlbetrag zuerst, groesster zuerst.
    """
    if nur_orte is not None:
        _nur = {int(o) for o in nur_orte}
        zeilen = [z for z in (zeilen or []) if int(z.get("ort") or 0) in _nur]
    b = baum(zeilen, namen, ort_namen, besitzer_namen, behaelter_namen,
             bedarf=bedarf, nur_tids=nur_tids, begriffe=begriffe, lag=lag,
             fremd_abzug=fremd_abzug, eigen_schutz=eigen_schutz)
    karten_map = {}
    fehlt_ganz = []
    for it in b:
        if not it["orte"]:
            # Ohne Bestand UND ohne Fehlbetrag gibt es nichts zu zeigen und
            # nichts zu tun.
            if it["bedarf"] and it["short"] > 0:
                fehlt_ganz.append(it)
            continue
        for o in it["orte"]:
            k = karten_map.get(o["ort"])
            if k is None:
                k = karten_map[o["ort"]] = {"ort": o["ort"], "name": o["name"],
                                            "menge": 0, "short": 0, "items": []}
            k["items"].append({"tid": it["tid"], "name": it["name"],
                               "menge": o["menge"], "gesamt": it["menge"],
                               "bedarf": it["bedarf"], "short": it["short"],
                               # emm770: ueber ALLE Orte, nicht nur diesen -
                               # die Fussnote gilt dem Item, nicht der Karte.
                               "verpackt": it.get("verpackt", 0),
                               "besitzer": o["besitzer"]})
            k["menge"] += o["menge"]
            if it["short"] > 0:
                k["short"] += 1
    # JEDER eingeschaltete Ort bekommt eine Karte - auch wenn dort gerade
    # nichts liegt, was die Plaene noch brauchen (Nutzer: "R&R Yard und Space
    # Resources Institute sehe ich nicht, die Karten muessten da sein, denn
    # da liegt Material"). Eine fehlende Karte sieht aus wie ein Fehler; eine
    # leere sagt, dass dort nichts Gesuchtes liegt.
    if nur_orte is not None:
        _on = ort_namen or {}
        for o in nur_orte:
            o = int(o)
            if o not in karten_map:
                karten_map[o] = {"ort": o, "name": _on.get(o) or f"#{o}",
                                 "menge": 0, "short": 0, "items": []}
    out = []
    for k in karten_map.values():
        k["items"].sort(key=lambda x: (0 if x["short"] else (1 if x["bedarf"] else 2),
                                       -x["short"], x["name"]))
        out.append(k)
    out.sort(key=lambda k: (-k["short"], -len(k["items"]), k["name"]))
    fehlt_ganz.sort(key=lambda x: (-x["short"], x["name"]))
    return out, fehlt_ganz


def gebaute_tids(plaene):
    """Alle Items, die IRGENDEIN Plan selbst baut (build_runs > 0).

    STEUERT SEIT emm527 NICHTS MEHR - nur noch Diagnose (zeige_lagerorte).
    Bis dahin bekam jedes Item dieser Menge NIE einen Fehlbetrag (emm465:
    "Baut es auch nur EIN Plan, bleibt es draussen"). Gemessen hat diese
    Keule 63 Posten verschluckt, darunter Teile, die der betroffene Plan
    gar nicht baut, sondern KAUFT (Hangar Cleaner: 110 R.A.M.- Armor/Hull
    Tech, Eigenbau 0 - unsichtbar, weil Riggs 1 sie baut). Die Gutschrift
    sitzt jetzt anteilig im Bedarf je Plan (`bedarf_aus_plaenen`)."""
    from .ui.mw_helpers import MainWindowHelpers as _MH
    out = set()
    for p in plaene or []:
        snap = ((p or {}).get("frozen") or {}).get("plan_snapshot")
        if not isinstance(snap, dict):
            continue
        try:
            plan = _MH._plan_snapshot_unpack(snap)
        except Exception:
            continue
        for t, r in (plan.get("build_runs") or {}).items():
            try:
                if int(r or 0) > 0:
                    out.add(int(t))
            except (TypeError, ValueError):
                continue
    return out


def einkaufsliste(items):
    """[(Name, Menge)] fuer EVEs Multibuy aus dem Baum von `baum`/`karten`
    (emm464, Nutzer: "eine Giant Shopping List ueber alle Baupläne").

    Genommen wird NUR, was wirklich fehlt (`short` > 0). Items ohne
    aufgeloesten Namen ("#123") bleiben draussen - im Spiel waere die Zeile
    unbrauchbar. Groesster Fehlbetrag zuerst.

    Der frueher noetige `gebaut`-Filter ist weg (emm527): `short` ist seit
    dem Umbau der NETTO-Fehlbetrag - was ein Plan selbst herstellt, ist im
    Bedarf schon gutgeschrieben und kann hier gar nicht mehr auftauchen.
    Ein Teil, das er zur Haelfte baut und zur Haelfte zukauft, steht jetzt
    mit seiner echten Restmenge drin, statt ganz zu fehlen.

    KEIN Abzug fuer Material an ABGESCHALTETEN Orten (emm467, Nutzer: "nein
    da wird nix verschoben, sonst wuerde ich ja zbsp Jita einschalten wenn
    ich von da material nehmen wollte"). Ein abgeschalteter Ort existiert
    fuer Eve MoMa nicht - er senkt den Einkauf also auch nicht."""
    out = []
    for it in items or []:
        try:
            int(it.get("tid"))      # kaputte Zeile faellt hier heraus
            n = int(it.get("short") or 0)
        except (TypeError, ValueError):
            continue
        name = str(it.get("name") or "")
        if n <= 0 or not name or name.startswith("#"):
            continue
        out.append((name, n))
    out.sort(key=lambda x: (-x[1], x[0]))
    return out


def multibuy_text(posten):
    """"Name<TAB>Menge" je Zeile - dasselbe Format wie die Einkaufsliste des
    Bauplans (`_materials_multibuy`), direkt in EVEs Multibuy einfuegbar."""
    return "\n".join(f"{n}\t{int(q)}" for n, q in posten or [])


# Ein Abruf gilt als verdaechtig klein, wenn weniger als dieser Anteil der
# zuletzt bestaetigten Asset-Zeilen ankommt; unter SCHRUMPF_MIN Zeilen wird
# gar nicht geurteilt (kleine Charaktere schwanken stark).
SCHRUMPF_ANTEIL = 0.7
SCHRUMPF_MIN = 50
# WIE LANGE EIN EINBRUCH VERDAECHTIG BLEIBT (emm744, 28.10.2026). Vorher
# galt "zweimal dieselbe kleinere Zahl = neue Wahrheit" - das reichte nicht:
# ESI cacht Assets rund eine Stunde, zwei Aktualisierungen liegen also oft
# nur Minuten auseinander und liefern zwangslaeufig DIESELBE zu kleine Zahl.
# Die Warnung verstummte dadurch beim zweiten Abruf, und der gekuerzte Stand
# wurde als `ok` festgeschrieben. Eine echte Hangar-Raeumung ueberdauert
# zwei Stunden muehelos, eine CCP-Stoerung meist nicht - erst danach gilt
# die kleinere Zahl.
SCHRUMPF_BESTAETIGUNG_SEK = 7200
# WIE WEIT DIE ZAHL WAEHREND DER BESTAETIGUNG SCHWANKEN DARF (emm762).
# Ein gekuerzter Abruf liefert nicht jedes Mal exakt dieselbe Zeilenzahl -
# der Charakter baut weiter, Jobs liefern ab, Stacks wachsen zusammen.
# Innerhalb dieses Bandes um den Startwert der kleinen Phase laeuft die
# Bestaetigungs-Uhr weiter; ausserhalb beginnt eine neue Phase. 10 %
# faengt das normale Rauschen ab und liegt deutlich unter der
# Erkennungsschwelle (30 % Einbruch), die unveraendert bleibt.
SCHRUMPF_BAND = 0.1
# ... MINDESTENS ABER SO VIELE ZEILEN (emm767). Ein rein relatives Band
# ist bei kleinen Zahlen winzig: gemessen an seinem Stand vom 29.10.
# (Leziris Lezflow, ok 1445 -> basis 34) waren 10 % genau 3,4 Zeilen -
# ein einziger abgelieferter Job wirft die Bestaetigungs-Uhr damit
# zurueck, und die Warnung bleibt ewig stehen. Unter rund 100 Zeilen
# zaehlt deshalb diese absolute Schranke.
SCHRUMPF_BAND_MIN = 10


def bestand_schrumpf(neu, stand, jetzt=None):
    """([(Name, vorher, jetzt)], neuer Stand) - WELCHER Abruf war wohl
    unvollstaendig, obwohl ESI keinen Fehler gemeldet hat (emm477).

    GEMESSEN am 08.10.2026 (zwei Berichte des Nutzers, eine Stunde
    auseinander): die Dockside fiel von 41'464'561 auf 3'079'105 Stueck,
    die Asset-Zeilen von 3'886 auf 2'501 - 16 andere Orte blieben gleich.
    Material verdampft nicht; der Abruf hat nicht alles geliefert. Wirft
    ESI dabei einen Fehler, faengt ihn `failed` (emm476); liefert es
    stattdessen STILL zu wenig, fiel das bisher niemandem auf - und genau
    daraus wurde ein Nachkauf.

    `neu`: {Name: Asset-Zeilen dieses Laufs} - nur GELUNGENE Abrufe.
    `stand`: {Name: {"ok": bestaetigte Zeilen, "letzte": Zeilen des
             letzten Laufs, "seit": Zeitstempel des ersten kleinen Abrufs}}
             aus den Einstellungen.
    `jetzt`: Zeitstempel (nur zum Pruefen; sonst die Uhr).

    DIE KLEINERE ZAHL MUSS SICH BEWAEHREN (emm744, s.
    SCHRUMPF_BESTAETIGUNG_SEK). Bis dahin steht die Warnung bei JEDEM
    Abruf - nicht nur beim ersten. Haelt der kleinere Stand laenger als
    zwei Stunden, hat der Nutzer wirklich geraeumt, und er wird zur neuen
    Wahrheit; die Warnung verschwindet dann von selbst.

    NUTZER-BEFUND 28.10.2026 ("Stock Locations, ploetzlich fehlt ueberall
    Material, ich habe nix gemacht"): ESI lieferte fuer einen Charakter
    582 statt 1'859 Asset-Zeilen. Der erste Abruf warnte noch, der zweite
    - Minuten spaeter, derselbe ESI-Cache, dieselbe gekuerzte Antwort -
    schrieb 582 als `ok` fest. Danach zeigte die Seite Fehlbetraege von
    18 Mio Pyerite und bot den Einkauf an, ohne ein Wort der Warnung.
    """
    warn, out = [], {}
    _alt = stand if isinstance(stand, dict) else {}
    _jetzt = float(jetzt) if jetzt is not None else _time.time()
    for name, n in (neu or {}).items():
        try:
            n = int(n)
        except (TypeError, ValueError):
            continue
        e = _alt.get(name) if isinstance(_alt.get(name), dict) else {}
        try:
            ok = int(e.get("ok") or 0)
        except (TypeError, ValueError):
            ok = 0
        # `letzte` wird nur noch GESCHRIEBEN (Diagnose: was der letzte
        # Abruf lieferte, sichtbar in settings.json - genau daraus kam
        # am 29.10. der Befund "Lezflow 172 statt 1445"). Gelesen wurde
        # es bis emm762 fuer die Bedingung "exakt dieselbe Zahl"; die
        # ist durch das Toleranzband um `basis` ersetzt.
        try:
            seit = float(e.get("seit") or 0.0)
        except (TypeError, ValueError):
            seit = 0.0
        try:
            basis = int(e.get("basis") or 0)
        except (TypeError, ValueError):
            basis = 0
        _klein = ok >= SCHRUMPF_MIN and n < ok * SCHRUMPF_ANTEIL
        if not _klein:
            out[name] = {"ok": max(n, 0), "letzte": n, "seit": 0.0,
                         "basis": 0}
            continue
        # DIE UHR LAEUFT WEITER, SOLANGE DIE ZAHL IM SELBEN BEREICH BLEIBT
        # (emm762). Bis dahin stand hier "letzte != n -> Uhr zurueck", also
        # ZWEI STUNDEN LANG EXAKT DIESELBE Zeilenzahl. Nutzer 29.10.2026:
        # "hart gesperrt ist okey, aber die warnung scheint selten nicht da
        # zu sein". SIMULIERT (werkzeuge/sim_emm762.py) mit seinen Zahlen:
        # ein RUHENDER Charakter (sein Lezflow, 1445 -> 172 weggeschoben)
        # verstummt nach 2,5 h - ein ARBEITENDER (Peanut Motor 1859 -> 582
        # vom 28.10., Abruf schwankt um +-2 Zeilen, weil Jobs abliefern und
        # Stacks wachsen) warnte in 8 von 8 Abrufen auch nach 4 Stunden,
        # weil JEDE einzelne Zeile Abweichung die Uhr auf null warf. Genau
        # dort sitzt der gekuerzte Abruf aber - der Fall, fuer den die
        # Bestaetigung gedacht war, konnte sie nie erreichen.
        # `basis` ist die Zahl, mit der die kleine Phase begann; bleibt der
        # Abruf in ihrem Band, laeuft die Uhr weiter. Ein WEITERER Einbruch
        # (oder ein Sprung nach oben, der die Lage neu beurteilt) beginnt
        # eine neue Phase - die Erkennungsschwelle SCHRUMPF_ANTEIL und die
        # Sperre des Einkaufsknopfs bleiben unangetastet.
        _band = max(basis * SCHRUMPF_BAND, SCHRUMPF_BAND_MIN)
        if seit <= 0.0 or basis <= 0 or abs(n - basis) > _band:
            seit = _jetzt
            basis = n
        if _jetzt - seit >= SCHRUMPF_BESTAETIGUNG_SEK:
            out[name] = {"ok": max(n, 0), "letzte": n, "seit": 0.0,
                         "basis": 0}
        else:
            warn.append((name, ok, n))
            out[name] = {"ok": ok, "letzte": n, "seit": seit,
                         "basis": basis}
    # Charaktere, die diesmal gar nicht geladen wurden (Fehler), behalten
    # ihren bestaetigten Wert - sonst faellt der naechste zu kleine Abruf
    # nicht mehr auf.
    for name, e in _alt.items():
        if name not in out and isinstance(e, dict):
            out[name] = e
    return warn, out
