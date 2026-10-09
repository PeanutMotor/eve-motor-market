"""BUILD FROM STOCK (emm436) - wie viele Runs gibt der Hangar her?

Nutzer 06.10.2026 (Discord HashtagMoDSucks, "Runs from stock"): eigene Seite
in der PRODUCTION-Leiste, je eigener Blaupause die Runs, die das vorhandene
Material hergibt. Entscheide: AUCH VORSTUFEN BAUEN (fehlt eine Komponente,
darf sie aus Hangar-Material gebaut werden - aber nur mit einer eigenen
Blaupause/Formel dafuer) und RESERVIERTES Material zaehlt NICHT (das
erledigt der Aufrufer: `bestand` ist schon der freie Rest).

Rein, ohne Qt und ohne ESI - die Seite liefert Rezepte, Bestand und
Blaupausen-Lage.

SICHERE SEITE (Regel 3): Material je Run aufgerundet
(`industry.material_menge`), nur die ME der eigenen Blaupause - keine
Struktur-/Rig-Boni. Das Ergebnis behauptet also eher zu WENIG Runs als zu
viele: wer danach baut, steht nie vor einem Job, der nicht startet.
"""
import math

from . import industry

TIEFE_MAX = 12            # Rezeptketten sind kuerzer; schuetzt vor Kreisen


class _Fehlt(Exception):
    """Ein Material reicht nicht (und laesst sich nicht nachbauen)."""

    def __init__(self, tid):
        super().__init__(tid)
        self.tid = int(tid)


def blaupausen_lage(owned):
    """Eigene Blaupausen (Format `esi.fetch_blueprints`) ->
    ({bp_id: beste ME in %}, {bp_id: None = Original (unbegrenzt) |
    Summe der Kopie-Runs}). Rein."""
    me, cap = {}, {}
    for b in (owned or []):
        try:
            bp = int(b.get("type_id"))
        except (TypeError, ValueError):
            continue
        me[bp] = max(me.get(bp, 0), int(b.get("material_efficiency") or 0))
        if b.get("is_bpo"):
            cap[bp] = None
        elif cap.get(bp, 0) is not None:
            _r = max(0, int(b.get("runs") or 0)) * max(1, int(b.get("quantity") or 1))
            cap[bp] = int(cap.get(bp, 0) or 0) + _r
    return me, cap


def _versuch(top, runs, p2b, mats, bestand, me_pct, cap, vorstufen):
    """Geht es, `runs` Runs von `top` zu bauen? -> (ok, grenze, gebaut)."""
    pool = {int(k): int(v or 0) for k, v in (bestand or {}).items()}
    benutzt = {}
    gebaut = {}

    def bauen(tid, n, tiefe):
        bp, act, _out = p2b[tid]
        if bp not in cap:
            raise _Fehlt(tid)          # keine eigene Blaupause/Formel
        if cap[bp] is not None:
            benutzt[bp] = benutzt.get(bp, 0) + n
            if benutzt[bp] > cap[bp]:
                raise _Fehlt(tid)      # Kopien-Runs reichen nicht
        me = (1.0 - float(me_pct.get(bp, 0) or 0) / 100.0
              if act == industry.MANUFACTURING else 1.0)
        for m, q in (mats.get((bp, act)) or []):
            hole(int(m), industry.material_menge(q, n, me), tiefe + 1)
        gebaut[tid] = gebaut.get(tid, 0) + n

    def hole(tid, n, tiefe):
        if n <= 0:
            return
        da = pool.get(tid, 0)
        nimm = min(da, n)
        pool[tid] = da - nimm
        rest = n - nimm
        if rest <= 0:
            return
        if not vorstufen or tiefe > TIEFE_MAX or tid not in p2b:
            raise _Fehlt(tid)
        _bp, _act, out = p2b[tid]
        out = max(1, int(out or 1))
        r = int(math.ceil(rest / out))
        bauen(tid, r, tiefe)
        pool[tid] = pool.get(tid, 0) + r * out - rest   # Ueberschuss bleibt

    try:
        bauen(int(top), int(runs), 0)
    except _Fehlt as f:
        return False, f.tid, {}
    except RecursionError:
        return False, None, {}
    gebaut.pop(int(top), None)
    return True, None, gebaut


def max_runs(top, p2b, mats, bestand, me_pct, cap, vorstufen=True,
             obergrenze=1_000_000):
    """Hoechste Run-Zahl von `top` (Produkt-type_id), die der Bestand
    hergibt. -> {"runs", "grenze" (type_id, das den naechsten Run
    verhindert, sonst None), "baut" ({Vorstufe: Runs} fuer diese Runs)}.

    `p2b` {Produkt: (bp, Aktivitaet, Stueck/Run)}, `mats` {(bp, Akt): [(m, q)]},
    `bestand` freier Bestand {type_id: Menge}, `me_pct`/`cap` aus
    `blaupausen_lage`. Suche: verdoppeln bis es nicht mehr geht, dann
    halbieren (die Machbarkeit waechst nie mit mehr Runs). Rein."""
    top = int(top)
    leer = {"runs": 0, "grenze": None, "baut": {}}
    if top not in p2b:
        return leer
    ok, grenze, gebaut = _versuch(top, 1, p2b, mats, bestand, me_pct, cap, vorstufen)
    if not ok:
        return {"runs": 0, "grenze": grenze, "baut": {}}
    lo, lo_baut = 1, gebaut
    hi = None
    n = 2
    while n <= obergrenze:
        ok, grenze, gebaut = _versuch(top, n, p2b, mats, bestand, me_pct, cap,
                                      vorstufen)
        if not ok:
            hi = n
            break
        lo, lo_baut = n, gebaut
        n *= 2
    if hi is None:
        return {"runs": lo, "grenze": None, "baut": lo_baut}
    while hi - lo > 1:
        mid = (lo + hi) // 2
        ok, g, gebaut = _versuch(top, mid, p2b, mats, bestand, me_pct, cap,
                                 vorstufen)
        if ok:
            lo, lo_baut = mid, gebaut
        else:
            hi, grenze = mid, g
    return {"runs": lo, "grenze": grenze, "baut": lo_baut}


def produkte_der_blaupausen(cap, p2b):
    """{bp_id: Produkt} fuer die eigenen Blaupausen, die etwas BAUEN
    (Fertigung oder Reaktion) - Kopieren/Forschung bleiben draussen. Rein."""
    raus = {}
    for prod, v in (p2b or {}).items():
        try:
            bp, act = int(v[0]), int(v[1])
        except (TypeError, ValueError, IndexError):
            continue
        if bp in (cap or {}) and act in (industry.MANUFACTURING, industry.REACTION):
            raus[bp] = int(prod)
    return raus


def bestand_liste(owned, p2b, mats, bestand, vorstufen=True):
    """Je eigener Blaupause, die etwas baut: was gibt der Bestand her?
    -> [{"bp", "produkt", "runs", "units", "grenze", "baut"}], sortiert nach
    Units absteigend, dann Produkt-ID. `units` = Runs x Stueck je Run. Rein."""
    me, cap = blaupausen_lage(owned)
    raus = []
    for bp, prod in sorted(produkte_der_blaupausen(cap, p2b).items()):
        r = max_runs(prod, p2b, mats, bestand, me, cap, vorstufen=vorstufen)
        out = max(1, int((p2b.get(prod) or (0, 0, 1))[2] or 1))
        raus.append({"bp": int(bp), "produkt": int(prod), "runs": r["runs"],
                     "units": r["runs"] * out, "grenze": r["grenze"],
                     "baut": dict(r["baut"])})
    raus.sort(key=lambda z: (-z["units"], z["produkt"]))
    return raus
