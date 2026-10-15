"""Zeigt, WELCHE Blaupausen Eve MoMa von dir sieht - und welche der
Blueprints-Reiter deshalb rot als "completely missing" meldet
(Fassung 3, 11.10.2026).

WOZU: Nutzer-Befund 11.10.2026 - der Blueprints-Reiter zeigte zehn
Reaktionsformeln rot als "completely missing", dazu "mir fehlen keine
blaupausen". Eine der beiden Aussagen ist falsch, und ich will sie nicht
raten (Regel 5): dieser Bericht holt GENAU dieselben Daten wie der Bauplan
(`esi.fetch_blueprints` mit `mit_belegten=True`, Corp-Hangar ueber
`esi.fetch_corporation_blueprints`) und stellt daneben, was der Reiter
daraus macht.

Je Charakter steht hier:
  * wie viele Blaupausen ESI geschickt hat, getrennt in FREI und IM JOB,
  * wie viele davon Originale (BPO) und wie viele Kopien (BPC) sind,
  * der Fehlertext, falls der Abruf scheiterte (ein gescheiterter Abruf ist
    KEIN "du hast sie nicht" - emm479/emm516).

Dann die Corp-Seite, weil genau dort der stille Verlust sitzt: ohne
Schalter `use_corp`, ohne angekreuzten Hangar, ohne Director-Rolle oder
ohne Corp-Scope im Token liefert ESI die Corp-Blaupausen gar nicht - und
eine Formel im Corp-Hangar sah im Reiter aus wie "besitzt du nicht".

Danach je gespeichertem, nicht abgeschlossenem Bauplan: JEDE Blaupause
seiner Rezept-Kette mit dem Urteil BPO / BPC / IM JOB / FEHLT - dieselbe
Reihenfolge der Fragen wie im Reiter. Was hier "FEHLT" heisst, heisst dort
rot; steht es hier als BPO da, ist der Reiter schuld.

Zum Schluss der Stand des ESI-Fehlerbudgets (emm480): bei 420 antwortet
CCP auf JEDEN Abruf mit einem Fehler - dann sagt dieser Bericht nichts
ueber deinen Hangar aus, sondern nur, dass gerade nichts abrufbar ist.

AUFRUF: werkzeuge\\zeige_blaupausen.bat doppelklicken.
Danach liegt `berichte\\blaupausen_bericht.txt` da.
Es wird NUR GELESEN: settings.json wird direkt gelesen (NICHT ueber
`config.load_settings`, das beim Laden Migrationen ausfuehrt und dabei
speichern wuerde), die Datenbank nur lesend abgefragt, ESI nur per GET.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import config, corp, esi, industry, store   # noqa: E402

FASSUNG = 3
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERICHT = os.path.join(WURZEL, "berichte", "blaupausen_bericht.txt")


def _z(n):
    try:
        return f"{int(n):,}".replace(",", "'")
    except (TypeError, ValueError):
        return "?"


def _settings_rohe():
    """settings.json ROH lesen - OHNE `config.load_settings()` (dasselbe
    Vorgehen wie zeige_lagerorte Fassung 2: load_settings fuehrt
    Migrationen aus und wuerde dabei SCHREIBEN)."""
    data = dict(config.DEFAULT_SETTINGS)
    try:
        import json as _j
        with open(config.settings_path(), encoding="utf-8") as fh:
            data.update(_j.load(fh) or {})
    except Exception:
        data = config.load_settings() or {}
        data["_ueber_load_settings"] = True
    return data


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


def _besitz_karte(frei, im_job):
    """(counts, bpc_runs, job_n) - NACHBAU der vier Zeilen aus
    `_apply_bp_ownership` (mw_bauplan_fenster): `is_bpo` erhoeht die Zahl
    der Originale, alles andere summiert Runs x Stueck als Kopien. Bewusst
    hier nachgebaut, weil die Produkt-Stelle in einem Qt-Mixin steckt und
    dieses Werkzeug ohne Qt laufen muss - die Regel steht in EINEM Satz
    daneben, damit ein Auseinanderlaufen auffaellt."""
    counts, bpc_runs = {}, {}
    for b in frei or []:
        tid = b.get("type_id")
        if not tid:
            continue
        if b.get("is_bpo"):
            counts[tid] = counts.get(tid, 0) + int(b.get("quantity", 1) or 1)
        else:
            bpc_runs[tid] = (bpc_runs.get(tid, 0)
                             + int(b.get("quantity", 1) or 1)
                             * int(b.get("runs", 0) or 0))
    job_n = {int(k): len(v or []) for k, v in (im_job or {}).items()}
    return counts, bpc_runs, job_n


def _schreib(zeilen):
    os.makedirs(os.path.dirname(BERICHT), exist_ok=True)
    with open(BERICHT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(zeilen) + "\n")
    print("\n".join(zeilen))
    print("")
    print(f"Geschrieben: {BERICHT}")


def main():
    z = []
    z.append(f"BLAUPAUSEN-BERICHT (Fassung {FASSUNG})")
    z.append("=" * 72)
    settings = _settings_rohe()
    if settings.get("_ueber_load_settings"):
        z.append("HINWEIS: settings.json war nicht direkt lesbar - gelesen "
                 "ueber den normalen Weg.")
    client_id = settings.get("client_id")
    chars = store.list_characters() or []
    if not client_id or not chars:
        z.append("Kein client_id oder kein verknuepfter Charakter - Abbruch.")
        _schreib(z)
        return

    # ---- 1. je Charakter ------------------------------------------------
    frei_alle, im_job = [], {}
    fehler = []
    z.append("")
    z.append("1. BLAUPAUSEN JE CHARAKTER (wie der Bauplan sie holt)")
    z.append("-" * 72)
    z.append(f"{'Charakter':28s} {'frei':>7s} {'im Job':>7s} "
             f"{'BPO-Typen':>10s} {'BPC-Typen':>10s}  Fehler")
    for c in chars:
        name = str(c.get("character_name") or c.get("character_id"))
        try:
            rows = esi.fetch_blueprints(client_id, c["character_id"],
                                        mit_belegten=True)
        except Exception as e:
            fehler.append(name)
            z.append(f"{name[:28]:28s} {'?':>7s} {'?':>7s} {'?':>10s} "
                     f"{'?':>10s}  ABRUF GESCHEITERT: {e}")
            continue
        for b in rows:                       # WER hat sie (Fassung 3)
            b["char"] = name
        _f = [b for b in rows if not b.get("in_job")]
        _j = [b for b in rows if b.get("in_job")]
        for b in _j:
            im_job.setdefault(int(b.get("type_id") or 0), []).append(b)
        frei_alle.extend(_f)
        _bpo = len({b.get("type_id") for b in _f if b.get("is_bpo")})
        _bpc = len({b.get("type_id") for b in _f if not b.get("is_bpo")})
        z.append(f"{name[:28]:28s} {_z(len(_f)):>7s} {_z(len(_j)):>7s} "
                 f"{_z(_bpo):>10s} {_z(_bpc):>10s}")

    # ---- 2. Corp --------------------------------------------------------
    z.append("")
    z.append("2. CORP-HANGAR (hier sitzt der stille Verlust)")
    z.append("-" * 72)
    if not settings.get("use_corp"):
        z.append("Schalter 'Corp-Hangar mitzaehlen' ist AUS - Blaupausen im "
                 "Corp-Hangar zaehlen nirgends.")
        fehler.append("Corp aus")
    else:
        divisions = corp.divisions_bereinigt(settings.get("corp_divisions"))
        z.append(f"Angekreuzte Hangars: "
                 f"{', '.join(str(d) for d in divisions) or '(keine)'}")
        if not divisions:
            z.append("KEIN Hangar angekreuzt - der Abruf laeuft gar nicht.")
            fehler.append("Corp ohne Hangar")
        else:
            corp_von, rollen_von = {}, {}
            for c in chars:
                cid = c["character_id"]
                corp_von[cid] = esi.fetch_character_corporation(cid)
                try:
                    rollen_von[cid] = esi.fetch_character_roles(client_id, cid)
                except Exception as e:
                    rollen_von[cid] = None
                    z.append(f"  Rollen von {c.get('character_name')} nicht "
                             f"abrufbar: {e}")
            plan, ohne_rolle = corp.abrufplan(chars, corp_von, rollen_von,
                                              corp.ROLLE_BLUEPRINTS)
            for corp_id in (ohne_rolle or {}):
                nm = esi.fetch_corporation_name(corp_id)
                z.append(f"  {nm}: KEIN Charakter mit Director-Rolle - "
                         f"Corp-Blaupausen werden nicht geholt.")
                fehler.append(f"Corp ohne Rolle: {nm}")
            if not plan:
                z.append("  Keine Corp abrufbar.")
            for corp_id, cid in plan.items():
                nm = esi.fetch_corporation_name(corp_id)
                try:
                    _cb = esi.fetch_corporation_blueprints(
                        client_id, cid, corp_id, divisions)
                except Exception as e:
                    z.append(f"  {nm}: ABRUF GESCHEITERT: {e}")
                    fehler.append(f"Corp-Blaupausen: {nm}")
                    continue
                _cf = [b for b in _cb if not b.get("in_job")]
                frei_alle.extend(_cf)
                _bpo = len({b.get("type_id") for b in _cf if b.get("is_bpo")})
                z.append(f"  {nm}: {_z(len(_cf))} Blaupausen, "
                         f"{_z(_bpo)} BPO-Typen (ueber "
                         f"{(rollen_von.get(cid) and 'Director') or '?'})")

    counts, bpc_runs, job_n = _besitz_karte(frei_alle, im_job)
    z.append("")
    z.append(f"BESITZ GESAMT: {_z(len(counts))} BPO-Typen, "
             f"{_z(len(bpc_runs))} BPC-Typen, "
             f"{_z(len(job_n))} Typen in laufenden Jobs")
    if fehler:
        z.append("UNVOLLSTAENDIG: " + ", ".join(fehler)
                 + "  -> was hier 'FEHLT' heisst, kann sehr wohl im Hangar "
                   "liegen.")

    # ---- 3. je Plan -----------------------------------------------------
    z.append("")
    z.append("3. BLAUPAUSEN DER GESPEICHERTEN PLAENE")
    z.append("-" * 72)
    try:
        recipes = industry.recipes_cached()
    except Exception as e:
        z.append(f"Rezepte nicht lesbar ({e}) - Abschnitt entfaellt.")
        recipes = None
    plaene = [p for p in (settings.get("bau_saved_plans") or [])
              if isinstance(p, dict) and not p.get("done_manual")]
    if recipes is not None and not plaene:
        z.append("Kein offener gespeicherter Plan.")
    for p in (plaene if recipes is not None else []):
        label = str(p.get("label") or p.get("item_name") or p.get("id"))
        z.append("")
        z.append(f"PLAN: {label}")
        try:
            _enden = [(int(a), int(b)) for a, b in (p.get("enden") or [])]
            if _enden:
                _rz = industry.buendel_rezepte(recipes, _enden)
                _kette = industry.full_build_chain(
                    industry.BUENDEL_ID, 1, _rz, {})
            else:
                _rz = recipes
                _kette = industry.full_build_chain(
                    int(p.get("type_id")), int(p.get("qty") or 1), _rz, {})
        except Exception as e:
            z.append(f"  Kette nicht rechenbar: {e}")
            continue
        _zeilen = []
        for tid, runs in sorted(_kette.items()):
            if int(runs or 0) < 1:
                continue
            bp = _rz.product_to_bp.get(tid)
            if not bp:
                continue
            bp_id = bp[0]
            if bp_id == industry.BUENDEL_BP:
                continue
            # WIRD ERFUNDEN ist KEIN Fehlen (Fassung 2, 11.10.2026): eine
            # T2-Kopie, die der Plan selbst per Invention erzeugt, zeigt der
            # Reiter amber "will be invented" - dieselbe Bedingung wie dort
            # (Fertigung + Blaupause steht in invention_for_bpc). Fassung 1
            # schrieb sie als FEHLT und machte damit aus fuenf erfundenen
            # T2-Schiffen eine Falschmeldung.
            _erf = (bp[1] == industry.MANUFACTURING
                    and bp_id in (getattr(_rz, "invention_for_bpc", None) or {}))
            _zeilen.append((tid, bp_id, int(runs), _erf))
        namen = _namen([t for t, _b, _r, _e in _zeilen]
                       + [b for _t, b, _r, _e in _zeilen])
        _fehlt = 0
        z.append(f"  {'Blaupause':38s} {'Runs':>6s}  Urteil")
        for tid, bp_id, runs, _erf in sorted(
                _zeilen, key=lambda x: namen.get(x[1], str(x[1]))):
            nm = namen.get(bp_id) or f"#{bp_id}"
            if _erf and not counts.get(bp_id) and not bpc_runs.get(bp_id):
                urteil = "WIRD ERFUNDEN"
            elif counts.get(bp_id):
                urteil = f"BPO x{_z(counts[bp_id])}"
            elif bpc_runs.get(bp_id):
                urteil = f"BPC {_z(bpc_runs[bp_id])} Runs"
            elif job_n.get(bp_id):
                urteil = f"IM JOB ({job_n[bp_id]})"
            else:
                urteil = "FEHLT"
                _fehlt += 1
            z.append(f"  {nm[:38]:38s} {_z(runs):>6s}  {urteil}")
        z.append(f"  -> {_z(_fehlt)} Blaupause(n) stehen als FEHLT da "
                 f"(im Reiter rot).")

    # ---- 3b. EIN BLAUPAUSEN-TYP GANZ GENAU --------------------------------
    # WOZU (Fassung 3, 11.10.2026): der Runplaner zeigte "4 blueprints" fuer
    # Hobgoblin I, der Blueprints-Reiter "OWNED 1" - zwei Zahlen fuer
    # dieselbe Tatsache. Der Grund ist NICHT zu erraten: die zwei Stellen
    # zaehlen verschieden (der Reiter nur `is_bpo`, der Runplaner BPO+BPC
    # als Stueck). Dieser Abschnitt zeigt deshalb die ROHEN ESI-Eintraege
    # je Blaupausen-Typ UND laesst die ECHTE Produktfunktion
    # `_bp_copies_by_tid` darueber laufen (Regel 8a: die Funktion rufen,
    # nicht nachbauen) - damit steht nebeneinander, was ESI schickt, was
    # der Reiter daraus macht und was der Runplaner als Deckel bekommt.
    # SUCHWORT: Umgebungsvariable BP_SUCHE, Vorgabe "Hobgoblin".
    suche = (os.environ.get("BP_SUCHE") or "Hobgoblin").strip()
    z.append("")
    z.append(f"3b. EIN BLAUPAUSEN-TYP GANZ GENAU - Suchwort: {suche!r}")
    z.append("-" * 72)
    z.append("Jede Zeile ist EIN Eintrag, so wie ESI ihn schickt. 'BPO' heisst")
    z.append("Original (runs -1 / quantity -1), 'BPC' eine Kopie mit Runs.")
    z.append("Der Reiter zaehlt NUR BPO-Stueck, der Runplaner BPO+BPC.")
    z.append("Zeigt der Runplaner eine ANDERE Zahl als hier, stammt sie aus")
    z.append("der Stufen-Ladung des offenen Bauplans (_bd_stage_bp_esi) -")
    z.append("die kennt dieses Werkzeug nicht, sie steht nur im Fenster.")
    try:
        alle_bp = sorted({int(b.get("type_id") or 0)
                          for b in frei_alle} |
                         {int(k) for k in (im_job or {})})
        alle_bp = [t for t in alle_bp if t > 0]
        nm_bp = _namen(alle_bp)
        treffer = [t for t in alle_bp
                   if suche.lower() in str(nm_bp.get(t) or "").lower()]
        if not treffer:
            z.append(f"  Kein Blaupausen-Typ mit {suche!r} im Namen gefunden.")
        # Produkt je Blaupause (Umkehrung von product_to_bp) - nur fuer die
        # Deckel-Rechnung; ohne Rezepte bleibt es bei der Roh-Liste.
        bp_zu_produkt = {}
        if recipes is not None:
            for _pid, _bp in (getattr(recipes, "product_to_bp", None) or {}).items():
                try:
                    bp_zu_produkt.setdefault(int(_bp[0]), int(_pid))
                except (TypeError, ValueError, IndexError):
                    continue
        nm_prod = _namen([bp_zu_produkt[t] for t in treffer if t in bp_zu_produkt])
        for bp_id in treffer:
            nm = nm_bp.get(bp_id) or f"#{bp_id}"
            z.append("")
            z.append(f"  {nm}  (Blaupausen-Typ {bp_id})")
            eintraege = [b for b in frei_alle
                         if int(b.get("type_id") or 0) == bp_id]
            belegte = list((im_job or {}).get(bp_id) or [])
            if not eintraege and not belegte:
                z.append("      (ESI schickt dazu gar nichts)")
            for b in eintraege + belegte:
                art = "BPO" if b.get("is_bpo") else "BPC"
                runs = b.get("runs")
                z.append(f"      {str(b.get('char') or '?')[:20]:20s} "
                         f"{art}  Stueck {_z(b.get('quantity', 1) or 1):>6s}  "
                         f"Runs {str(runs):>6s}  "
                         f"Ort {b.get('location_id')}"
                         + ("  IM JOB" if b.get("in_job") else ""))
            # Was die zwei Stellen daraus machen - mit den ECHTEN Funktionen.
            _bpo = sum(int(b.get("quantity", 1) or 1)
                       for b in eintraege if b.get("is_bpo"))
            z.append(f"      -> Blueprints-Reiter (nur BPO):  {_z(_bpo)}")
            _pid = bp_zu_produkt.get(bp_id)
            if _pid is None:
                z.append("      -> Runplaner-Deckel: kein Produkt in den "
                         "Rezepten (keine Fertigung?)")
                continue
            try:
                from eve_trader.ui.mw_helpers import MainWindowHelpers as _MH
                _cap = _MH._bp_copies_by_tid(
                    frei_alle, {_pid: 1}, recipes.product_to_bp)
                _w = _cap.get(_pid)
                z.append(f"      -> Runplaner-Deckel (BPO+BPC) fuer "
                         f"{nm_prod.get(_pid) or _pid}: "
                         f"{'kein Eintrag (pauschale Stufen-Zahl!)' if not _w else max(1, int(_w))}")
            except Exception as e:
                z.append(f"      -> Runplaner-Deckel nicht rechenbar: {e}")
    except Exception as e:
        z.append(f"  Abschnitt nicht rechenbar: {e}")

    # ---- 4. Fehlerbudget ------------------------------------------------
    z.append("")
    z.append("4. ESI-FEHLERBUDGET (emm480)")
    z.append("-" * 72)
    try:
        z.append(f"  {esi.fehlerbudget()}")
        if esi.budget_erschoepft():
            z.append("  ERSCHOEPFT (420): CCP weist gerade JEDEN Abruf ab - "
                     "dieser Bericht sagt dann nichts ueber deinen Hangar.")
    except Exception as e:
        z.append(f"  nicht lesbar: {e}")

    z.append("")
    z.append("LESEHILFE")
    z.append("-" * 72)
    z.append("1) Steht unter UNVOLLSTAENDIG etwas, ist jedes 'FEHLT' "
             "unzuverlaessig - erst die Ursache beheben.")
    z.append("2) Steht eine Blaupause hier als BPO/BPC/IM JOB, der Reiter "
             "aber rot: Fehler im Reiter, bitte melden.")
    z.append("3) Steht sie hier als FEHLT und du hast sie im Spiel: dann "
             "liegt sie in einem Hangar, den Eve MoMa nicht liest "
             "(Corp-Hangar ohne Haken/Rolle, anderer Account).")
    _schreib(z)


if __name__ == "__main__":
    main()
