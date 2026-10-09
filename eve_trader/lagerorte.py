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


def gebaute_runs(plan, zuordnung=None, extra=None):
    """{type_id: schon gebaute Runs} eines gespeicherten Plans - OHNE ESI,
    nur aus dem, was lokal belegt ist (emm463).

    Zwei Quellen, je Item das MAXIMUM (sie meinen dieselben Runs, nicht
    zwei verschiedene - genau wie `_rest_geliefert_jetzt` im Bauplan):
      * die ESI-Jobs, die laut `job_zuordnung` DIESEM Plan gehoeren
        (`zuordnung` = store.job_zuordnung_details()) - laufende zaehlen
        mit, ihr Material ist im Spiel laengst verbraucht (emm422),
      * die Hand-Haken des Runplaners (`checked_runplan_runs`,
        {"stufe|tid": Runs}).
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
    out = {t: max(aus_jobs.get(t, 0), aus_haken.get(t, 0))
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


def bedarf_aus_plaenen(plaene, zuordnung=None, extra_runs=None):
    """{type_id: [(plan_label, menge)]} - was die NOCH OFFENEN Runs der
    uebergebenen Plaene an Material brauchen (Zutaten aller Bau-Schritte +
    Datacores/Decryptoren), aus dem eingefrorenen Schnappschuss.
    Endprodukte sind kein Bedarf; Plaene ohne Schnappschuss liefern nichts.

    emm463 (Nutzer: "von allen aktiven Bauplaenen bin ich schon beim
    Endprodukt, ich braeuchte nichts mehr - da steht aber viel auf Rot"):
    vorher stand hier die VOLLE Planmenge. Wer seine Vorstufen laengst
    gebaut hat, sah damit fuer jedes verbaute Material einen Fehlbetrag.
    Jetzt dieselbe Rechnung wie die Einkaufsliste
    (`mw_helpers.restbedarf_map`): Plan-Runs minus die schon gebauten
    (`gebaute_runs`), Material anteilig AUFgerundet (Regel 3).
    Invention-Material (Datacores/Decryptoren) zaehlt anteilig zum
    groessten offenen Rest der ENDPRODUKTE - es haengt an deren Kopien.
    """
    from .ui.mw_helpers import MainWindowHelpers as _MH, restbedarf_map
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
        _gebaut = gebaute_runs(p, zuordnung,
                               (extra_runs or {}).get(str(p.get("id"))))
        _mats = {int(t): v for t, v in (plan.get("build_mats") or {}).items()}
        rem, summe = restbedarf_map(_runs, _mats, _gebaut)
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
        # Invention haengt an den Endprodukt-Kopien: Anteil = groesster
        # offener Rest der Enden (sichere Richtung), ohne Enden voll.
        _enden = [int(t) for t, _q in (p.get("enden") or [])] or \
            ([int(p["type_id"])] if p.get("type_id") else [])
        _anteil = 0.0
        for _e in _enden:
            _r = int(_runs.get(_e, 0) or 0)
            if _r > 0:
                _anteil = max(_anteil, rem.get(_e, 0) / _r)
        if not _enden or not any(int(_runs.get(_e, 0) or 0) > 0 for _e in _enden):
            _anteil = 1.0
        # DATACORES/DECRYPTOREN (emm465, Nutzer: "ich habe alle T2 Blueprints
        # schon inventet und bin bei allen Plaenen am Endprodukt, deswegen
        # koennen sie nicht fehlen"): Invention laeuft VOR dem Bau. Sobald
        # der Plan auch nur einen Run gebaut hat, sind die Kopien da und das
        # Invention-Material ist verbraucht - der Invention-Reiter des Plans
        # rechnet den Rest genau (emm431, ueber die ESI-Jobs).
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
         bedarf=None, nur_tids=None, begriffe=None, selbst_gebaut=None):
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

    `selbst_gebaut` (emm465, Nutzer: "andere Sachen sind aktuell in der
    Bauschleife von Charakteren und werden auch nicht fehlen in Zukunft"):
    diese Items bekommen NIE einen Fehlbetrag. Ihr Nachschub kommt aus der
    eigenen Produktion des Plans - sie stehen weiter mit Menge und Ort da
    (zum Nachsehen), aber rot bedeutet auf dieser Seite "musst du kaufen",
    und kaufen will man ein Zwischenprodukt gerade nicht.
    """
    bedarf = bedarf or {}
    _gebaut = {int(x) for x in (selbst_gebaut or ())}
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
        for ort, bes_map in orte.items():
            o_menge = 0
            bes_l = []
            for (art, besitzer), pf_map in bes_map.items():
                bm = sum(pf_map.values())
                o_menge += bm
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
        out.append({"tid": tid, "name": namen.get(tid, f"#{tid}"),
                    "menge": it_menge, "bedarf": bd,
                    "short": (max(0, ges - it_menge)
                              if bd and tid not in _gebaut else 0),
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
                            "short": 0 if tid in _gebaut else ges,
                            "orte": []})
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
           bedarf=None, nur_tids=None, begriffe=None, nur_orte=None,
           selbst_gebaut=None):
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
             bedarf=bedarf, nur_tids=nur_tids, begriffe=begriffe,
             selbst_gebaut=selbst_gebaut)
    karten_map = {}
    fehlt_ganz = []
    for it in b:
        if not it["orte"]:
            # Ohne Bestand UND ohne Fehlbetrag (= der Plan baut es selbst)
            # gibt es nichts zu zeigen und nichts zu tun.
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

    Sie gehoeren nie auf eine Einkaufsliste (Nutzer 07.10.2026: "immer
    nachkaufen, keine kompletten neuen Bauschleifen entstehen lassen" -
    und schon gar nichts kaufen, was man gerade produziert). Baut es auch
    nur EIN Plan, bleibt es draussen: ein Fehlkauf aergert mehr als eine
    fehlende Zeile, die der Bauplan selbst zeigt."""
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


def einkaufsliste(items, gebaut=None):
    """[(Name, Menge)] fuer EVEs Multibuy aus dem Baum von `baum`/`karten`
    (emm464, Nutzer: "eine Giant Shopping List ueber alle Baupläne").

    Genommen wird NUR, was wirklich fehlt (`short` > 0) und was kein Plan
    selbst baut (`gebaut`, siehe `gebaute_tids`). Items ohne aufgeloesten
    Namen ("#123") bleiben draussen - im Spiel waere die Zeile unbrauchbar.
    Groesster Fehlbetrag zuerst.

    KEIN Abzug fuer Material an ABGESCHALTETEN Orten (emm467, Nutzer: "nein
    da wird nix verschoben, sonst wuerde ich ja zbsp Jita einschalten wenn
    ich von da material nehmen wollte"). Ein abgeschalteter Ort existiert
    fuer Eve MoMa nicht - er senkt den Einkauf also auch nicht."""
    _geb = {int(x) for x in (gebaut or ())}
    out = []
    for it in items or []:
        try:
            tid = int(it.get("tid"))
            n = int(it.get("short") or 0)
        except (TypeError, ValueError):
            continue
        name = str(it.get("name") or "")
        if n <= 0 or tid in _geb or not name or name.startswith("#"):
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


def bestand_schrumpf(neu, stand):
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
             letzten Laufs}} aus den Einstellungen.

    Zweimal dieselbe kleinere Zahl gilt als neue Wahrheit (der Nutzer hat
    dann wirklich geleert) - so bleibt die Warnung nicht fuer immer
    stehen, meldet sich aber bei JEDEM schwankenden Abruf wieder.
    """
    warn, out = [], {}
    _alt = stand if isinstance(stand, dict) else {}
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
        try:
            letzte = int(e.get("letzte") or 0)
        except (TypeError, ValueError):
            letzte = 0
        _klein = ok >= SCHRUMPF_MIN and n < ok * SCHRUMPF_ANTEIL
        if _klein and letzte != n:
            warn.append((name, ok, n))
            out[name] = {"ok": ok, "letzte": n}
        else:
            out[name] = {"ok": max(n, 0), "letzte": n}
    # Charaktere, die diesmal gar nicht geladen wurden (Fehler), behalten
    # ihren bestaetigten Wert - sonst faellt der naechste zu kleine Abruf
    # nicht mehr auf.
    for name, e in _alt.items():
        if name not in out and isinstance(e, dict):
            out[name] = e
    return warn, out
