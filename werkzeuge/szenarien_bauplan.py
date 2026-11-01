"""SZENARIO-WERKSTATT: viele Bauplan-Lagen durchspielen und die Zusagen
pruefen, die der Bauplan gibt.

NUTZER 24.10.2026: "Simuliere viele moeglichkeiten lass pruefungen laufen
simulationen und und. von mir aus lasse 100 verschiedene szenarien
Simulieren um die funktionalitaet des Bauplanes vollstaendig zu
gewaehrleisten".

WARUM DAS ETWAS ANDERES IST ALS DIE TESTSUITEN: aa und b pruefen
EINZELNE Funktionen an festen Zahlen. Der Fehler, den er seit Monaten
meldet, sass aber NICHT in einer Funktion - jede war fuer sich richtig
(siehe emm636, emm638). Er sass im ZUSAMMENSPIEL: mehrere Plaene, ein
geteilter Hangar, Haken zu unguenstigen Zeiten. Genau das wird hier
erzeugt - zufaellig, aber mit festem Samen, also jederzeit wiederholbar.

GERECHNET WIRD MIT DEM ECHTEN PLANER (`industry.production_plan`) auf
synthetischen Rezeptbaeumen. Synthetisch sind nur die Rezepte, nicht die
Rechnung - sonst wuerde das Werkzeug seine eigene Zweitrechnung pruefen
(Regel 9). KEIN ESI, KEINE Datenbank, keine settings.json: dieses
Werkzeug laeuft ueberall, auch ohne den Rechner des Nutzers.

DIE GEPRUEFTEN ZUSAGEN
  Z1 DIE EINKAUFSLISTE REICHT. Wer `buy` kauft und `stock_used` im
     Hangar hat, kann JEDE geplante Stufe in der geplanten Reihenfolge
     bauen, ohne dass irgendwo etwas fehlt. Das ist DIE Zusage des
     Bauplans - und genau die, von der der Nutzer sagt, sie halte nicht.
  Z2 KEIN STUECK ZWEIMAL VERPLANT. Was alle Plaene zusammen aus dem
     Hangar decken, gibt es auch wirklich.
  Z3 DIE RESERVIERUNG HAELT. Ein spaeterer Plan deckt sich nur aus dem,
     was die frueheren uebriglassen.
  Z4 EIN HAKEN SENKT DEN ANSPRUCH, NIE UMGEKEHRT - und nie unter null.
  Z5 EIN HAKEN ERHOEHT DEN FEHLBEDARF NICHT.

AUFRUF:
    python werkzeuge\\szenarien_bauplan.py
    python werkzeuge\\szenarien_bauplan.py --anzahl 500 --samen 7
    python werkzeuge\\szenarien_bauplan.py --zeige 12
"""
import argparse
import os
import random
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import industry as _I                     # noqa: E402
from eve_trader.ui.mw_helpers import MainWindowHelpers    # noqa: E402

FASSUNG = 1
WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BERICHT = os.path.join(WURZEL, "berichte", "szenarien_bericht.txt")


def _z(n):
    try:
        return f"{int(n):,}".replace(",", "'")
    except (TypeError, ValueError):
        return "?"


class _Rez:
    """Rezeptsammlung wie `industry.Recipes`, aber ohne Datenbank - genau
    die Felder, die `production_plan` liest."""

    def __init__(self):
        self.product_to_bp = {}
        self.bp_materials = {}
        self.reaction_products = set()
        self.invention_for_bpc = {}
        self.invention_copy_mats = {}
        self.activity_time = {}
        self.activity_max_runs = {}
        self.bp_products = {}
        self.item_cat = {}

    def is_manufactured(self, t):
        return t in self.product_to_bp


def _baum(rng):
    """Ein zufaelliger Rezeptbaum. Liefert (rezepte, enden, rohstoffe).

    Tiefe 2-4, Verzweigung 2-3 - die Form, die seine echten Plaene haben
    (Endprodukt -> Komponenten -> Composite-Reaktion -> Intermediate ->
    Rohstoff).
    """
    r = _Rez()
    naechste = [1000]
    enden, roh = [], set()
    tiefe = rng.randint(2, 4)
    ebene = [1000 + i for i in range(rng.randint(1, 3))]
    enden = list(ebene)
    tid = 2000
    for stufe in range(tiefe):
        neue = []
        for produkt in ebene:
            bp = produkt + 500000
            akt = (_I.REACTION if stufe >= 2 and rng.random() < 0.6
                   else _I.MANUFACTURING)
            # Ausbringung je Run: Reaktionen liefern viele Stueck.
            menge = rng.choice((1, 1, 10, 100)) if akt == _I.MANUFACTURING \
                else rng.choice((100, 200, 10000))
            r.product_to_bp[produkt] = (bp, akt, menge)
            if akt == _I.REACTION:
                r.reaction_products.add(produkt)
            r.activity_time[(bp, akt)] = 600
            r.activity_max_runs[(bp, akt)] = 0
            mats = []
            for _ in range(rng.randint(2, 3)):
                kind = tid
                tid += 1
                mats.append((kind, rng.randint(2, 50)))
                neue.append(kind)
            r.bp_materials[(bp, akt)] = mats
        ebene = neue
    roh = set(ebene)
    return r, enden, roh


def _preise(rng, rezepte, roh):
    """Preise VON UNTEN NACH OBEN mit Aufschlag - sonst baut der Planer gar
    nichts.

    ERSTER ENTWURF WAR WERTLOS: mit frei gewuerfelten Preisen war Kaufen
    fast immer billiger, die Baukette blieb 1,8 Stufen flach und die
    Szenarien trafen genau das nicht, worum es geht. Jetzt kostet ein
    Produkt das `aufschlag`-fache seiner Zutaten - mal ueber 1 (Bauen
    lohnt), mal darunter (Kaufen lohnt), damit BEIDE Entscheidungen
    vorkommen.
    """
    p = {t: float(rng.randint(5, 500)) for t in roh}
    # Von den Blaettern nach oben: ein Produkt kann erst bepreist werden,
    # wenn alle seine Zutaten einen Preis haben.
    offen = set(rezepte.product_to_bp)
    while offen:
        _fertig = False
        for t in sorted(offen):
            bp, akt, menge = rezepte.product_to_bp[t]
            mats = rezepte.bp_materials.get((bp, akt)) or []
            if any(m not in p for m, _q in mats):
                continue
            kosten = sum(p[m] * q for m, q in mats) / max(1, menge)
            aufschlag = rng.choice((0.8, 1.3, 1.8, 2.5, 4.0))
            p[t] = max(1.0, kosten * aufschlag)
            offen.discard(t)
            _fertig = True
            break
        if not _fertig:
            for t in offen:            # Ringschluss kann es nicht geben,
                p[t] = 1000.0          # aber haengenbleiben darf es nie
            break
    return p


def _out_qty(rezepte, tid):
    e = rezepte.product_to_bp.get(tid)
    return int(e[2]) if e else 0


def _z1_pruefen(plan, rezepte):
    """Z1: kaufe `buy`, lege `stock_used` dazu, baue `build_seq` der Reihe
    nach - nichts darf negativ werden.

    DAS IST DIE ZUSAGE, auf die der Nutzer sich verlaesst. Gerechnet wird
    ausschliesslich mit dem, was der Plan SELBST ausgibt.
    """
    da = {}
    for schl in ("buy", "stock_used", "inv_buy", "inv_stock_used"):
        for t, q in (plan.get(schl) or {}).items():
            da[int(t)] = da.get(int(t), 0) + int(q or 0)
    mats = plan.get("build_mats") or {}
    fehler = []
    for tid, runs in (plan.get("build_seq") or []):
        tid, runs = int(tid), int(runs or 0)
        if runs <= 0:
            continue
        for m, q in (mats.get(tid) or []):
            m, q = int(m), int(q or 0)
            da[m] = da.get(m, 0) - q
            if da[m] < 0:
                fehler.append((m, -da[m], tid))
                da[m] = 0          # weiterzaehlen, alle Luecken sammeln
        da[tid] = da.get(tid, 0) + runs * _out_qty(rezepte, tid)
    return fehler


def _tick_anspruch(snap, anteil, verzug, stempel):
    """Anspruch eines Plans mit abgehakten Runs - die ECHTE Kette.

    `anteil` 0..1 der Runs je Item, `verzug` Sekunden nach `stempel`
    (positiv = ESI hat es noch nicht gesehen).
    """
    basis = MainWindowHelpers._plan_reserve_map(snap) or {}
    ct, hr = {}, {}
    for t, runs in (snap.get("build_runs") or {}).items():
        n = int(int(runs or 0) * anteil)
        if n <= 0:
            continue
        ct[f"component|1|{int(t)}"] = stempel + verzug
        hr[f"component|{int(t)}"] = n
    return MainWindowHelpers._reserve_map_mitlaufend(
        snap, dict(basis), ct, [], stempel, belegt={}, haken_runs=hr)


def _zeitlauf(rng, plaene, hangar, rezepte):
    """DER ZEITLAUF - und der eigentliche Grund fuer dieses Werkzeug.

    Die 500 Szenarien ohne Zeit liefen alle sauber durch, und das ist
    kein Wunder: ein Plan ist in dem Moment, in dem er gerechnet wird,
    immer stimmig. Der Nutzer-Fehler passiert SPAETER - er friert Plan 1
    ein, kauft, baut ein Stueck weit, legt Plan 2 an, kauft, baut, und
    IRGENDWANN fehlt ihm mitten im Bau Material.

    Hier wird genau das nachgespielt: alle Plaene kaufen ihre Liste, dann
    bauen sie DURCHEINANDER (zufaellige Reihenfolge, zufaellige Anteile)
    aus EINEM gemeinsamen Hangar. Verbraucht wird wirklich - eine
    Reservierung haelt Material nur rechnerisch frei, im Hangar schuetzt
    sie nichts.

    Z6 IST DIE ZUSAGE: wer seine Einkaufsliste gekauft hat, muss seine
    Runs auch dann noch bauen koennen, wenn die anderen Plaene
    dazwischenfunken. Scheitert das, ist es GENAU sein Fall.
    """
    # Jeder kauft seine Liste - das hat der Nutzer nachweislich getan.
    for snap, _s in plaene:
        for t2, q in (snap.get("buy") or {}).items():
            hangar[int(t2)] = hangar.get(int(t2), 0) + int(q or 0)
    # Offene Runs je Plan.
    offen = [dict(snap.get("build_runs") or {}) for snap, _s in plaene]
    # JE PLAN BLEIBT DIE BAUREIHENFOLGE ERHALTEN - man kann die obere
    # Stufe nicht vor der unteren bauen. GEMISCHT werden nur die PLAENE
    # untereinander.
    # ERSTER ENTWURF WAR FALSCH UND HAETTE MICH FAST EINEN FEHLALARM
    # MELDEN LASSEN: ein `shuffle` + `sort(key=lambda x: 0)` ist eine
    # stabile Sortierung auf einen konstanten Schluessel - sie laesst die
    # gemischte Folge stehen. Damit baute jeder Plan seine Stufen in
    # zufaelliger Reihenfolge, und 380 von 500 Szenarien "brachen".
    je_plan = {}
    for i, (snap, _s) in enumerate(plaene):
        for tid, runs in (snap.get("build_seq") or []):
            je_plan.setdefault(i, []).append((int(tid), int(runs or 0)))
    reihenfolge = []
    zeiger = {i: 0 for i in je_plan}
    while any(zeiger[i] < len(je_plan[i]) for i in je_plan):
        i = rng.choice([x for x in je_plan if zeiger[x] < len(je_plan[x])])
        reihenfolge.append((i,) + je_plan[i][zeiger[i]])
        zeiger[i] += 1

    fehler = []
    for i, tid, runs in reihenfolge:
        snap = plaene[i][0]
        mats = (snap.get("build_mats") or {}).get(tid) or []
        ges = int((snap.get("build_runs") or {}).get(tid, 0) or 0)
        if ges <= 0 or runs <= 0:
            continue
        anteil = min(1.0, float(runs) / float(ges))
        # Reicht der Hangar fuer diesen Schritt?
        for m, q in mats:
            m, q = int(m), int(int(q or 0) * anteil)
            if hangar.get(m, 0) < q:
                fehler.append((
                    "Z6 Zusage bricht im Zeitlauf",
                    f"Plan {i + 1} kann Stufe {tid} nicht bauen: braucht "
                    f"{_z(q)} von {m}, im Hangar {_z(hangar.get(m, 0))} "
                    f"- obwohl die Einkaufsliste gekauft wurde"))
                break
        else:
            for m, q in mats:
                m = int(m)
                hangar[m] = hangar.get(m, 0) - int(int(q or 0) * anteil)
            hangar[tid] = (hangar.get(tid, 0)
                           + int(runs * _out_qty(rezepte, tid)))
    return fehler


def _ein_szenario(rng, nr):
    """Eine Lage: Rezeptbaum, geteilter Hangar, 2-3 Plaene nacheinander."""
    rezepte, enden, roh = _baum(rng)
    preise = _preise(rng, rezepte, roh)
    pf = preise.get

    # GETEILTER HANGAR: ein Teil der Items liegt da, in zufaelliger Hoehe.
    hangar = {}
    for t in list(roh) + list(rezepte.product_to_bp):
        if rng.random() < 0.5:
            hangar[t] = rng.randint(1, 200000)

    n_plaene = rng.randint(2, 3)
    verbleibend = dict(hangar)
    ansprueche, plaene = [], []
    for i in range(n_plaene):
        ende = rng.choice(enden)
        units = rng.randint(1, 500)
        opts = {
            "me": rng.choice((0, 2, 10)),
            "me_reaction": rng.choice((0, 2)),
            "job_pct": 0,
            "build_reactions": True,
            "tree_depth": 9,
            "max_depth": 12,
            # DER ENTSCHEIDENDE PUNKT: jeder Plan sieht nur, was die
            # frueheren uebriglassen - wie im Programm.
            "stock": dict(verbleibend),
        }
        try:
            snap = _I.production_plan(ende, units, pf, rezepte, dict(opts))
        except Exception as e:
            return {"nr": nr, "fehler": [("AUSNAHME", f"{type(e).__name__}: {e}")],
                    "plaene": 0}
        snap["build_runs"] = {int(k): int(v) for k, v in
                              (snap.get("build_runs") or {}).items()}
        plaene.append((snap, dict(opts["stock"])))
        a = MainWindowHelpers._plan_reserve_map(snap) or {}
        ansprueche.append(a)
        # Reservierung anwenden: der naechste Plan sieht weniger.
        rest = dict(verbleibend)
        MainWindowHelpers.bestand_nach_reservierungen(rest, a, {})
        verbleibend = rest

    fehler = []
    # --- Z1: die Einkaufsliste reicht --------------------------------
    for i, (snap, _s) in enumerate(plaene):
        for m, fehlt, tid in _z1_pruefen(snap, rezepte)[:3]:
            fehler.append(("Z1 Einkaufsliste reicht nicht",
                           f"Plan {i + 1}: beim Bau von {tid} fehlen "
                           f"{_z(fehlt)} von Material {m}"))
    # --- Z2: kein Stueck zweimal verplant ----------------------------
    gedeckt = {}
    for snap, _s in plaene:
        for t, q in (snap.get("stock_used") or {}).items():
            gedeckt[int(t)] = gedeckt.get(int(t), 0) + int(q or 0)
    for t, q in gedeckt.items():
        if q > int(hangar.get(t, 0)):
            fehler.append(("Z2 Bestand doppelt verplant",
                           f"Material {t}: Plaene decken {_z(q)}, "
                           f"im Hangar {_z(hangar.get(t, 0))}"))
    # --- Z3: die Reservierung haelt ----------------------------------
    for i, (snap, sichtbar) in enumerate(plaene):
        for t, q in (snap.get("stock_used") or {}).items():
            if int(q or 0) > int(sichtbar.get(int(t), 0)):
                fehler.append(("Z3 Reservierung haelt nicht",
                               f"Plan {i + 1} deckt {_z(q)} von {t}, "
                               f"sichtbar waren {_z(sichtbar.get(int(t), 0))}"))
    # --- Z4 / Z5: Haken ----------------------------------------------
    stempel = 1_000_000.0
    for i, (snap, _s) in enumerate(plaene):
        ohne = MainWindowHelpers._plan_reserve_map(snap) or {}
        for anteil in (0.25, 0.5, 1.0):
            for verzug in (-60.0, 0.0, 60.0):
                mit = _tick_anspruch(snap, anteil, verzug, stempel)
                for t, q in mit.items():
                    if int(q) > int(ohne.get(int(t), 0)):
                        fehler.append((
                            "Z4 Haken erhoeht den Anspruch",
                            f"Plan {i + 1}, Anteil {anteil}, Verzug "
                            f"{verzug:+.0f}s: {t} {_z(ohne.get(int(t), 0))}"
                            f" -> {_z(q)}"))
                    if int(q) < 0:
                        fehler.append(("Z4 Anspruch negativ",
                                       f"Plan {i + 1}: {t} = {q}"))
    # --- Z6: haelt die Zusage auch im Zeitlauf? ----------------------
    fehler.extend(_zeitlauf(rng, plaene, dict(hangar), rezepte)[:3])
    return {"nr": nr, "fehler": fehler, "plaene": len(plaene),
            "enden": len(enden), "hangar": len(hangar)}


def _chaos_werkstatt(rng, anzahl=120, runden=120):
    # RUNDENZAHL: 40 war zu knapp und meldete eine grosse Werkstatt als
    # "nicht fertig", obwohl sie nur laenger brauchte (mit 120 und mit 400
    # wird sie fertig). Acht Charaktere, die oft "mache nichts" wuerfeln,
    # kommen eben langsam voran - das ist kein Fehler des Plans.
    """Z10: mehrere Plaene, acht fremde Charaktere, falsche Run-Zahlen -
    faengt sich das System von selbst? (emm653)

    NUTZER 24.10.2026: "Dann hat man 8 verschiedene charaktere die
    einfach irgendwelche runs ausführen von irgendwelchen plänen und
    dabei nicht mal die richtige angegeben anzahl runs sonder als
    beispiel Plan sagt mache 10 Runs und völlig fremde charaktere führen
    nur 7 runs aus usw.. wie sich das verhält und ob sich der Runplaner
    von alleine fängt und dynamisch wieder anpasst? So das am schluss
    einfach trotzdem irgendwie alles zu ende gebaut werden kann".

    DAS IST DIE HAERTESTE PRUEFUNG IN DIESER DATEI, weil sie als einzige
    ueber die ZEIT laeuft statt ueber einen Moment: 3-5 Plaene teilen
    sich EINEN Hangar und EINEN Rezeptbaum (sie konkurrieren also
    wirklich), jeder startet in einer anderen Stufe, und dann fahren
    acht Charaktere runden-weise Runs - zufaellig ausgewaehlt, in
    zufaelliger Menge (7 statt 10, manchmal 13), manchmal gar keine.
    Nach jeder Runde darf der Plan nachziehen: er sagt, was zu kaufen
    und was zusaetzlich zu fahren ist, und genau das passiert dann.

    Geprueft wird, was der Nutzer wirklich wissen will:
      K1 ES GEHT ZU ENDE. Jeder Plan ist nach spaetestens `runden`
         Runden fertig - der Runplaner faengt sich also.
      K2 KEIN WEGLAUFEN. Die Einkaufsliste explodiert nicht; insgesamt
         wird nie ein Vielfaches des urspruenglichen Plans gekauft.
      K3 NICHTS WIRD NEGATIV, kein Hangar, keine Forderung.
      K4 KEINE LEERLAUF-RUNDE MIT LUECKE: solange etwas fehlt, sagt der
         Plan auch, was zu tun ist (sonst steht der Nutzer still).
    """
    from eve_trader.ui.mw_helpers import nachlauf_runs as _nr
    fehler, n, nicht_fertig = [], 0, 0
    for _ in range(anzahl):
        rezepte, enden, roh = _baum(rng)
        pf = _preise(rng, rezepte, roh).get
        hangar = {t: rng.randint(100, 40000)
                  for t in list(roh) + list(rezepte.product_to_bp)}
        plaene = []
        for _i in range(rng.randint(3, 5)):
            try:
                sn = _I.production_plan(
                    rng.choice(enden), rng.randint(5, 120), pf, rezepte,
                    {"me": 0, "me_reaction": 0, "job_pct": 0,
                     "build_reactions": True, "tree_depth": 9,
                     "max_depth": 12, "stock": dict(hangar)})
            except Exception as e:
                fehler.append(("K0 Planen wirft", f"{type(e).__name__}: {e}"))
                continue
            _br = {int(k): int(v) for k, v in (sn.get("build_runs") or {}).items()}
            _made = {int(k): int(v) for k, v in (sn.get("build_made") or {}).items()}
            if not _br:
                continue
            plaene.append({
                "br": _br, "mats": sn.get("build_mats") or {},
                "je": {t: max(1, _made.get(t, 0) // _br[t])
                       for t in _br if _br[t] > 0},
                # JEDER PLAN IN EINEM ANDEREN STADIUM (seine Vorgabe):
                # von "nichts gemacht" bis "fast durch".
                "erl": {t: int(g * rng.choice((0.0, 0.25, 0.6, 0.9)))
                        for t, g in _br.items()},
                "gekauft": 0})
            for t, q in (sn.get("buy") or {}).items():
                hangar[int(t)] = hangar.get(int(t), 0) + int(q)
                plaene[-1]["gekauft"] += int(q)
        if not plaene:
            continue
        n += 1
        # K2-MASSSTAB: der Gesamt-Materialbedarf aller Plaene. Erster
        # Entwurf mass gegen den ANFANGSKAUF - war der Hangar voll, kaufte
        # der Plan nichts, und jede Nachbestellung sah aus wie ein
        # Weglaufen (347 gegen 1).
        _start_kauf = max(1, sum(
            int(_q or 0) for _p in plaene
            for _l in (_p["mats"] or {}).values() for _m, _q in (_l or [])))
        _zusatz_kauf = 0
        for _runde in range(runden):
            offen = [p for p in plaene
                     if any(p["br"][t] - p["erl"].get(t, 0) > 0 for t in p["br"])]
            if not offen:
                break
            # 1) Der Plan sagt, was fehlt - und es wird gekauft.
            _was_zu_tun = 0
            for p in plaene:
                e, k = _nr(p["br"], p["mats"], p["je"], p["erl"], hangar)
                for t, q in k.items():
                    if int(q) < 0:
                        fehler.append(("K3 negative Forderung", f"{t}: {q}"))
                    hangar[int(t)] = hangar.get(int(t), 0) + int(q)
                    _zusatz_kauf += int(q)
                for t, r in e.items():
                    p["br"][t] = p["br"].get(t, 0) + int(r)
                _was_zu_tun += len(e) + len(k)
            # 2) ACHT FREMDE CHARAKTERE fahren irgendwas, in falscher Menge.
            _bewegt = False
            _konnte = False          # hat ueberhaupt jemand gekonnt?
            for _c in range(8):
                p = rng.choice(plaene)
                _kand = [t for t in p["br"]
                         if p["br"][t] - p["erl"].get(t, 0) > 0]
                if not _kand:
                    continue
                t = rng.choice(_kand)
                _soll = p["br"][t] - p["erl"].get(t, 0)
                # 7 statt 10, manchmal mehr, manchmal nichts.
                _will = max(0, int(_soll * rng.choice((0.0, 0.3, 0.7, 1.0, 1.3))))
                _will = min(_will, _soll)
                if _will <= 0:
                    continue
                # Nur fahren, was das Material hergibt (wie im Spiel).
                _ges = p["br"][t]
                _moeglich = _will
                for m, q in (p["mats"].get(t) or []):
                    _pro = -(-int(q or 0) // _ges)
                    if _pro > 0:
                        _moeglich = min(_moeglich,
                                        hangar.get(int(m), 0) // _pro)
                if _moeglich <= 0:
                    continue
                _konnte = True
                for m, q in (p["mats"].get(t) or []):
                    _pro = -(-int(q or 0) // _ges)
                    hangar[int(m)] = hangar.get(int(m), 0) - _pro * _moeglich
                    if hangar[int(m)] < 0:
                        fehler.append(("K3 Hangar negativ", f"{m}"))
                        hangar[int(m)] = 0
                hangar[t] = hangar.get(t, 0) + _moeglich * p["je"].get(t, 1)
                p["erl"][t] = p["erl"].get(t, 0) + _moeglich
                _bewegt = True
            # K4 NUR BEI ECHTEM STILLSTAND - und das heisst: KEIN
            # einziges offenes Item in KEINEM Plan laesst sich bauen, und
            # der Plan sagt auch nichts zu kaufen.
            # ZWEI FEHLVERSUCHE VORHER, beide meine Schuld: erst meldete
            # ich auch, wenn die acht Charaktere zufaellig alle "mache
            # nichts" wuerfelten; dann, wenn ihre acht ZUFAELLIGEN Griffe
            # alle auf blockierte Items fielen, obwohl ein anderes
            # baubar gewesen waere. Jetzt wird es erschoepfend geprueft -
            # eine Stichprobe taugt fuer diese Aussage nicht.
            if _was_zu_tun == 0 and offen and not _bewegt:
                _irgendwas_geht = False
                for _p2 in plaene:
                    for _t2, _g2 in _p2["br"].items():
                        if _g2 - _p2["erl"].get(_t2, 0) <= 0:
                            continue
                        if all(hangar.get(int(_m2), 0)
                               >= -(-int(_q2 or 0) // _g2)
                               for _m2, _q2 in (_p2["mats"].get(_t2) or [])):
                            _irgendwas_geht = True
                            break
                    if _irgendwas_geht:
                        break
                if not _irgendwas_geht:
                    fehler.append(("K4 Stillstand trotz offener Runs",
                                   f"Runde {_runde}"))
                    break
        else:
            nicht_fertig += 1
            fehler.append(("K1 nicht fertig geworden",
                           f"{len([p for p in plaene if any(p['br'][t] - p['erl'].get(t, 0) > 0 for t in p['br'])])} Plaene offen"))
        # K2: die Einkaufsliste darf nicht weglaufen.
        if _zusatz_kauf > 25 * _start_kauf:
            fehler.append(("K2 Einkaufsliste laeuft weg",
                           f"{_zusatz_kauf} gegen {_start_kauf} anfangs"))
    return n, fehler, nicht_fertig


def _gleichzeitig_haken(rng, anzahl=300):
    """Z11: ZWEI PLAENE GLEICHZEITIG BAUEN, BEVOR ESI NACHZIEHT. (emm655)

    NUTZER 24.10.2026: "was passiert wenn ich 2 pläne gleichzeitig baue
    bevor ESI hinterher kommt?"

    DIE GEFAHR, in einem Satz: hakt er in Plan A ab, sind die Zutaten
    ingame WEG - aber ESI meldet den Hangar noch eine Stunde lang voll.
    Gibt A seinen Anspruch sofort frei, sieht Plan B dasselbe Material
    als frei, kauft nichts nach, und ihm fehlt es mitten im Bau. Das ist
    exakt die Fehlerklasse, die wir diese Sitzung gejagt haben - nur
    diesmal zwischen zwei Plaenen statt innerhalb eines.

    GESPIELT WIRD: 2-3 Plaene ueber DENSELBEN Rezeptbaum mit EINEM
    Hangar (sie konkurrieren also wirklich), alle mit Schloss. Jeder
    hakt einen zufaelligen Anteil seiner Runs ab, und zwar mit einem
    Verzug von 1 s bis 2 h NACH dem Bestands-Abruf - also immer im
    gefaehrlichen Fenster. Verbraucht wird WIRKLICH: die Zutaten
    verlassen den echten Hangar, das Erzeugnis kommt hinein. Der
    ESI-Hangar bleibt derweil auf dem alten Stand stehen.

    VIER ZUSAGEN:
      K1 Im Verzug gibt ein Haken NICHTS frei (der Anspruch bleibt
         Zeichen fuer Zeichen derselbe wie ohne Haken).
      K2 Zieht ESI nach, gibt er sehr wohl frei - sonst bliebe Material
         fuer immer gesperrt und der naechste Plan kauft umsonst.
      K3 DIE EIGENTLICHE FRAGE: kein Plan sieht Material als verfuegbar,
         das ein ANDERER Plan schon verbraucht hat. Sein eigener
         Verbrauch darf er sehen - den verrechnet er selbst.
      K4 Kein Anspruch wird negativ.

    OHNE SCHLOSS wird dieselbe Lage ein zweites Mal gerechnet - nicht
    als Zusage, sondern als MESSUNG: wie weit traegt der Schutz, wenn er
    die Plaene nicht reserviert? Das Ergebnis gehoert ihm gesagt, nicht
    weginterpretiert.
    """
    fehler, n, ohne_schloss_treffer, ohne_schloss_laeufe = [], 0, 0, 0
    for nr in range(anzahl):
        rezepte, enden, roh = _baum(rng)
        preise = _preise(rng, rezepte, roh)
        pf = preise.get
        hangar = {}
        for t in list(roh) + list(rezepte.product_to_bp):
            if rng.random() < 0.6:
                hangar[t] = rng.randint(1, 200000)
        # Plaene wie im Programm: jeder sieht nur, was die frueheren
        # uebriglassen (Schloss gesetzt, Kartenreihenfolge).
        verbleibend, plaene = dict(hangar), []
        for _i in range(rng.randint(2, 3)):
            opts = {"me": rng.choice((0, 2, 10)),
                    "me_reaction": rng.choice((0, 2)), "job_pct": 0,
                    "build_reactions": True, "tree_depth": 9,
                    "max_depth": 12, "stock": dict(verbleibend)}
            try:
                snap = _I.production_plan(rng.choice(enden),
                                          rng.randint(1, 500), pf, rezepte,
                                          dict(opts))
            except Exception as e:
                fehler.append(("Z11 AUSNAHME", f"{type(e).__name__}: {e}"))
                snap = None
                break
            snap["build_runs"] = {int(k): int(v) for k, v in
                                  (snap.get("build_runs") or {}).items()}
            plaene.append(snap)
            rest = dict(verbleibend)
            MainWindowHelpers.bestand_nach_reservierungen(
                rest, MainWindowHelpers._plan_reserve_map(snap) or {}, {})
            verbleibend = rest
        if len(plaene) < 2:
            continue
        n += 1
        stempel = 1_000_000.0
        # Jeder Plan hakt einen Anteil ab - IM VERZUG (ESI sieht nichts).
        anteile = [rng.choice((0.2, 0.5, 0.8, 1.0)) for _ in plaene]
        verzuege = [float(rng.randint(1, 7200)) for _ in plaene]
        echt = dict(hangar)              # WIRKLICHKEIT (ingame)
        verbrauch = [{} for _ in plaene]  # je Plan: was ER verbraucht hat
        ansprueche_verzug, ansprueche_nach = [], []
        for i, snap in enumerate(plaene):
            ohne = MainWindowHelpers._plan_reserve_map(snap) or {}
            mit = _tick_anspruch(snap, anteile[i], verzuege[i], stempel)
            nach = _tick_anspruch(snap, anteile[i], -verzuege[i], stempel)
            ansprueche_verzug.append(mit)
            ansprueche_nach.append(nach)
            # K1: im Verzug darf sich NICHTS geaendert haben.
            for t in set(ohne) | set(mit):
                if int(mit.get(t, 0)) != int(ohne.get(t, 0)):
                    fehler.append((
                        "K1 Haken gibt im Verzug frei",
                        f"#{nr} Plan {i + 1}, Verzug {verzuege[i]:.0f}s: "
                        f"{t} {_z(ohne.get(t, 0))} -> {_z(mit.get(t, 0))}"))
                    break
            # K4
            for t, q in mit.items():
                if int(q) < 0:
                    fehler.append(("K4 Anspruch negativ",
                                   f"#{nr} Plan {i + 1}: {t} = {q}"))
                    break
            # WIRKLICH VERBRAUCHEN: Zutaten raus, Erzeugnis rein.
            for tid, runs in (snap.get("build_runs") or {}).items():
                tid, runs = int(tid), int(int(runs or 0) * anteile[i])
                ges = int((snap.get("build_runs") or {}).get(tid, 0) or 0)
                if runs <= 0 or ges <= 0:
                    continue
                q_anteil = float(runs) / float(ges)
                for m, q in ((snap.get("build_mats") or {}).get(tid) or []):
                    m, q = int(m), int(int(q or 0) * q_anteil)
                    echt[m] = echt.get(m, 0) - q
                    verbrauch[i][m] = verbrauch[i].get(m, 0) + q
                echt[tid] = echt.get(tid, 0) + runs * _out_qty(rezepte, tid)
        # K2: zieht ESI nach, muss der Anspruch irgendwo kleiner werden -
        # sonst bleibt Material fuer immer gesperrt.
        for i, snap in enumerate(plaene):
            if anteile[i] < 1.0:
                continue
            ohne = MainWindowHelpers._plan_reserve_map(snap) or {}
            if not ohne:
                continue
            if not any(int(ansprueche_nach[i].get(t, 0)) < int(q)
                       for t, q in ohne.items()):
                fehler.append((
                    "K2 Anspruch schrumpft auch nach ESI nicht",
                    f"#{nr} Plan {i + 1}: alle Runs abgehakt, ESI hat es "
                    f"gesehen - trotzdem bleibt jeder Posten reserviert"))
        # K3 DIE FRAGE DES NUTZERS. Der ESI-Hangar steht noch auf dem
        # ALTEN Stand (`hangar`). Was sieht Plan i, nachdem die Ansprueche
        # der ANDEREN abgezogen sind? Das darf nie mehr sein, als
        # wirklich dasteht - zuzueglich dessen, was er SELBST verbraucht
        # hat (das verrechnet er ueber den eigenen Plan).
        for i in range(len(plaene)):
            sichtbar = dict(hangar)
            for j in range(len(plaene)):
                if j == i:
                    continue
                MainWindowHelpers.bestand_nach_reservierungen(
                    sichtbar, ansprueche_verzug[j], {})
            for t, q in sichtbar.items():
                grenze = int(echt.get(t, 0)) + int(verbrauch[i].get(t, 0))
                if int(q) > grenze:
                    fehler.append((
                        "K3 Plan sieht fremdverbrauchtes Material",
                        f"#{nr} Plan {i + 1}: sieht {_z(q)} von {t}, "
                        f"wirklich da {_z(echt.get(t, 0))} "
                        f"(+{_z(verbrauch[i].get(t, 0))} eigener Verbrauch)"))
                    break
        # MESSUNG OHNE SCHLOSS: derselbe Fall, aber kein Plan reserviert.
        # Dann zieht niemand etwas ab - sichtbar bleibt der alte Hangar.
        ohne_schloss_laeufe += 1
        for t, q in hangar.items():
            if int(q) > int(echt.get(t, 0)) + int(verbrauch[0].get(t, 0)):
                ohne_schloss_treffer += 1
                break
    return n, fehler, ohne_schloss_treffer, ohne_schloss_laeufe


def _vorrang_politik(rng, anzahl=300):
    """Z12: WENN ES NICHT FUER ALLE REICHT - WEN TRIFFT ES, UND GEHT ES
    BESSER? (emm658)

    NUTZER 24.10.2026: "wenn doch gesammthaft über alle baupläne runs
    fehlen, muss irgend ein Bauplan diese Runs ausführen, welche werden
    dass sein? ... weisst du vovor ich Angst ahbe? wie ist das wie machen
    wir das" - und danach: "können wir etwas besser machen?"

    HIER WIRD GEMESSEN, NICHT GERATEN. Mehrere Plaene teilen einen
    Hangar, der ABSICHTLICH zu klein ist. Dann werden drei Arten
    verglichen, den knappen Vorrat zu verteilen:

      A  RANG (heute im Programm): Kartenreihenfolge, wer vorn steht
         nimmt zuerst. Entspricht seiner Regel "wenn ich einen Plan
         reserviert habe, dann baue ich ihn IMMER".
      B  ANTEILIG: jeder bekommt denselben Bruchteil seines Bedarfs.
      C  KLEINSTER ZUERST: wer am wenigsten braucht, wird zuerst
         vollstaendig bedient.

    GEMESSEN WIRD, WAS IHM WICHTIG IST - nicht "wie fair", sondern WIE
    VIELE PLAENE WIRKLICH FERTIG WERDEN. Ein Plan, der 99 % seines
    Materials hat, ist nicht zu 99 % fertig; er steht.

    DREI ZUSAGEN AN DIE HEUTIGE ART (A):
      W1 Rang 1 geht nie leer aus, solange der Vorrat seinen Bedarf
         ueberhaupt deckt. Das ist der Kern seiner Steuerung.
      W2 Dasselbe Bild zweimal gerechnet trifft denselben Plan
         (keine wandernden Opfer).
      W3 Kein Plan bekommt mehr, als er braucht - der Vorrat wird nicht
         verschwendet, solange jemand ihn noch braucht.
    """
    fehler, n = [], 0
    besser_c, gleich_c, schlechter_c = 0, 0, 0
    besser_b = 0
    knapp = 0
    gewinn_c = 0
    for nr in range(anzahl):
        rezepte, enden, roh = _baum(rng)
        preise = _preise(rng, rezepte, roh)
        pf = preise.get
        # ABSICHTLICH KNAPP: nur ein Bruchteil liegt da.
        voll = {}
        for t in list(roh) + list(rezepte.product_to_bp):
            voll[t] = rng.randint(1, 200000)
        plaene = []
        for _i in range(rng.randint(2, 5)):
            try:
                snap = _I.production_plan(
                    rng.choice(enden), rng.randint(1, 500), pf, rezepte,
                    {"me": rng.choice((0, 2, 10)),
                     "me_reaction": rng.choice((0, 2)), "job_pct": 0,
                     "build_reactions": True, "tree_depth": 9,
                     "max_depth": 12, "stock": {}})
            except Exception:
                plaene = []
                break
            plaene.append(snap)
        if len(plaene) < 2:
            continue
        # Bedarf je Plan = was seine Runs an ZUTATEN brauchen.
        bedarf = []
        for snap in plaene:
            b = {}
            for tid, mats in (snap.get("build_mats") or {}).items():
                for m, q in (mats or []):
                    b[int(m)] = b.get(int(m), 0) + int(q or 0)
            if b:
                bedarf.append(b)
        if len(bedarf) < 2:
            continue
        # Vorrat knapp halten: ein Bruchteil des Gesamtbedarfs.
        ges = {}
        for b in bedarf:
            for m, q in b.items():
                ges[m] = ges.get(m, 0) + q
        anteil = rng.uniform(0.3, 0.95)
        vorrat0 = {m: int(q * anteil) for m, q in ges.items()}
        n += 1

        def _reicht(b, v):
            return all(v.get(m, 0) >= q for m, q in b.items())

        def _nehmen(b, v):
            for m, q in b.items():
                v[m] = v.get(m, 0) - q

        def _wasserfall(folge, v0):
            """Gibt (fertige Plaene, Opfer-Index-Liste) zurueck."""
            v = dict(v0)
            fertig, opfer = 0, []
            for i in folge:
                if _reicht(bedarf[i], v):
                    _nehmen(bedarf[i], v)
                    fertig += 1
                else:
                    # Er nimmt, was er kriegt - und bleibt stehen.
                    for m, q in bedarf[i].items():
                        v[m] = max(0, v.get(m, 0) - q)
                    opfer.append(i)
            return fertig, opfer

        # --- A: Rang (Kartenreihenfolge) ---
        folge_a = list(range(len(bedarf)))
        fertig_a, opfer_a = _wasserfall(folge_a, vorrat0)
        # --- C: kleinster Bedarf zuerst ---
        folge_c = sorted(range(len(bedarf)),
                         key=lambda i: sum(bedarf[i].values()))
        fertig_c, _ = _wasserfall(folge_c, vorrat0)
        # --- B: ANTEILIG. ERSTER ENTWURF WAR FALSCH und haette eine
        # Behauptung gestuetzt, die nicht stimmt: ich hatte jeden Plan
        # gegen den VOLLEN Vorrat geprueft, als nehme kein anderer etwas
        # weg - damit kam "anteilig besser: 111" heraus, und daneben
        # stand mein Satz "anteilig ist durchweg die schlechteste Art".
        # Zwei Aussagen, die sich widersprechen, und die Zahl war die
        # falsche. Richtig: je Material bekommt jeder den Bruchteil
        # seines Anteils am Gesamtbedarf.
        fertig_b = 0
        for i in range(len(bedarf)):
            _voll_b = True
            for m, q in bedarf[i].items():
                if q <= 0:
                    continue
                _meins_b = vorrat0.get(m, 0) * (q / ges[m]) if ges.get(m) else 0
                if _meins_b < q:
                    _voll_b = False
                    break
            if _voll_b:
                fertig_b += 1
        if opfer_a:
            knapp += 1
        if fertig_c > fertig_a:
            besser_c += 1
            gewinn_c += fertig_c - fertig_a
        elif fertig_c == fertig_a:
            gleich_c += 1
        else:
            schlechter_c += 1
        if fertig_b > fertig_a:
            besser_b += 1

        # --- W1: Rang 1 geht nie leer aus, wenn der Vorrat ihn deckt ---
        if _reicht(bedarf[0], vorrat0) and 0 in opfer_a:
            fehler.append((
                "W1 Rang 1 geht leer aus, obwohl es reicht",
                f"#{nr}: Plan 1 braucht {_z(sum(bedarf[0].values()))}, "
                f"Vorrat deckt ihn - trotzdem Opfer"))
        # --- W2: zweimal gerechnet, dasselbe Opfer ---
        _f2, _o2 = _wasserfall(folge_a, vorrat0)
        if _o2 != opfer_a or _f2 != fertig_a:
            fehler.append((
                "W2 Das Opfer wandert zwischen zwei Rechnungen",
                f"#{nr}: {opfer_a} vs {_o2}"))
        # --- W3: niemand nimmt mehr, als er braucht ---
        _v3 = dict(vorrat0)
        for i in folge_a:
            if _reicht(bedarf[i], _v3):
                _nehmen(bedarf[i], _v3)
        for m, q in _v3.items():
            if q < 0:
                fehler.append(("W3 Vorrat wird negativ",
                               f"#{nr}: {m} = {q}"))
                break
    return (n, fehler, knapp, besser_c, gleich_c, schlechter_c, besser_b,
            gewinn_c)


def _fliessband(rng, anzahl=200):
    """Z13: DIE GESTAFFELTE BAUSTRASSE UEBER MEHRERE PLAENE. (emm659)

    NUTZER 24.10.2026, sein Arbeitsmodell im Klartext:
      "Bauplan 1 ich fange an mit reactions stufe 1 / Bauplan 2
       inzwischen habe ich Bauplan 1 reactions stufe 1 fertig und starte
       Bauplan 2 reactions stufe 1, gleichzeitig starte ich Bauplan 1
       reaction stufe 2 ... Somit kann ich eine geschlossene Bauschleife
       ueber mehrere Baupläne ingame kreiren und meine ingame Bauslots
       und reactions slots werden niemals leer, ich schiebe also immer
       wieder einen Neuen Bauplan unten rein."
      "ich möchte in keinem Bauplan wieder schritte zurück machen
       müssen."

    DIESER LETZTE SATZ IST DIE ZUSAGE, um die es geht. Alles andere
    dieser Sitzung fragt "fehlt Material?". Hier wird etwas Schaerferes
    gefragt: KANN EIN PLAN ZURUECKFALLEN? Ein Plan, der schon
    Komponenten baut und dann wieder Reaktionen Stufe 1 fahren muss,
    hat seine Staffelung verloren - und mit ihr die geschlossene
    Bauschleife, von der seine ganze Arbeitsweise lebt.

    DEFINITION RUECKSCHRITT (hart, nicht gefuehlt): ein Plan steht an
    Position k seiner Baufolge; verlangt `nachlauf_runs` von ihm Runs
    fuer ein Item an Position < k, ist das ein Rueckschritt.

    GESPIELT WIRD: 3-5 Plaene ueber EINEN Rezeptbaum und EINEN Hangar.
    Plan i betritt die Strasse eine Runde nach Plan i-1 - genau seine
    Staffelung. Jeder kauft beim Eintritt seine eigene Liste. Dann
    ruecken alle rundenweise eine Stufe vor, und verbraucht wird
    wirklich.

    DREI ZUSAGEN:
      R1 KEIN RUECKSCHRITT in irgendeinem Plan.
      R2 KEIN LEERLAUF: solange Arbeit offen ist, kann mindestens ein
         Plan eine Stufe fahren (seine Slots bleiben voll).
      R3 Der Hangar wird nie negativ.

    UND DIE GEGENPROBE, die den Wert des Schlosses zeigt: dieselbe
    Lage wird zweimal gerechnet - einmal mit Reservierung (jeder Plan
    sieht beim Erstellen nur, was die frueheren uebriglassen, und kauft
    entsprechend) und einmal OHNE (jeder sieht den vollen Hangar und
    kauft zu wenig). Der Unterschied ist keine Zusage, sondern eine
    Zahl, die er kennen sollte.
    """
    from eve_trader.ui.mw_helpers import nachlauf_runs as _nr13
    fehler, n = [], 0
    rueck_offen, laeufe_offen = 0, 0
    for nr in range(anzahl):
        rezepte, enden, roh = _baum(rng)
        preise = _preise(rng, rezepte, roh)
        pf = preise.get
        hangar0 = {}
        for t in list(roh) + list(rezepte.product_to_bp):
            if rng.random() < 0.5:
                hangar0[t] = rng.randint(1, 150000)

        def _bauen(gesperrt):
            """Eine Fliessband-Runde bauen. Gibt Fehlerliste zurueck."""
            verbleibend, plaene = dict(hangar0), []
            for _i in range(rng.randint(3, 5)):
                opts = {"me": rng.choice((0, 2, 10)),
                        "me_reaction": rng.choice((0, 2)), "job_pct": 0,
                        "build_reactions": True, "tree_depth": 9,
                        "max_depth": 12,
                        # DAS SCHLOSS: gesperrt = der neue Plan sieht nur
                        # den Rest und kauft entsprechend mehr. Offen =
                        # er sieht alles und kauft zu wenig.
                        "stock": dict(verbleibend) if gesperrt
                        else dict(hangar0)}
                try:
                    snap = _I.production_plan(rng.choice(enden),
                                              rng.randint(1, 400), pf,
                                              rezepte, dict(opts))
                except Exception:
                    return None
                snap["build_runs"] = {int(k): int(v) for k, v in
                                      (snap.get("build_runs") or {}).items()}
                plaene.append(snap)
                if gesperrt:
                    rest = dict(verbleibend)
                    MainWindowHelpers.bestand_nach_reservierungen(
                        rest, MainWindowHelpers._plan_reserve_map(snap) or {},
                        {})
                    verbleibend = rest
            if len(plaene) < 2:
                return None

            # Baufolge je Plan = seine Stufen in der richtigen Ordnung.
            folge = []
            for snap in plaene:
                folge.append([(int(t), int(r or 0))
                              for t, r in (snap.get("build_seq") or [])])
            if any(not f for f in folge):
                return None
            hangar = dict(hangar0)
            # Jeder kauft BEIM EINTRITT seine Liste (nicht alle vorab) -
            # so macht er es auch.
            gekauft = [False] * len(plaene)
            pos = [0] * len(plaene)            # wo steht welcher Plan
            eintritt = list(range(len(plaene)))  # Versatz: eine Runde je Plan
            _f = []
            for runde in range(len(plaene) + sum(len(x) for x in folge) + 5):
                etwas_ging = False
                offen_da = False
                for i, snap in enumerate(plaene):
                    if runde < eintritt[i]:
                        continue
                    if not gekauft[i]:
                        for t2, q2 in (snap.get("buy") or {}).items():
                            hangar[int(t2)] = (hangar.get(int(t2), 0)
                                               + int(q2 or 0))
                        gekauft[i] = True
                    if pos[i] >= len(folge[i]):
                        continue
                    offen_da = True
                    tid, runs = folge[i][pos[i]]
                    mats = (snap.get("build_mats") or {}).get(tid) or []
                    ges = int((snap.get("build_runs") or {}).get(tid, 0) or 0)
                    if ges <= 0 or runs <= 0:
                        pos[i] += 1
                        etwas_ging = True
                        continue
                    anteil = min(1.0, float(runs) / float(ges))
                    reicht = all(hangar.get(int(m), 0)
                                 >= int(int(q or 0) * anteil)
                                 for m, q in mats)
                    if not reicht:
                        continue
                    for m, q in mats:
                        hangar[int(m)] = (hangar.get(int(m), 0)
                                          - int(int(q or 0) * anteil))
                    hangar[tid] = (hangar.get(tid, 0)
                                   + int(runs * _out_qty(rezepte, tid)))
                    pos[i] += 1
                    etwas_ging = True
                    # ---- R1: verlangt der Plan jetzt einen Schritt
                    # ZURUECK? `erledigt` = alles bis Position pos[i].
                    _erl = {}
                    for _t3, _r3 in folge[i][:pos[i]]:
                        _erl[_t3] = _erl.get(_t3, 0) + _r3
                    _made = {int(k): int(v or 0) for k, v in
                             (snap.get("build_made") or {}).items()}
                    _br = snap.get("build_runs") or {}
                    _je = {_t: max(1, _made.get(_t, 0) // _br[_t])
                           for _t in _br if _br.get(_t) and _made.get(_t)}
                    try:
                        _extra, _ = _nr13(_br, snap.get("build_mats") or {},
                                          _je, _erl, hangar)
                    except Exception:
                        _extra = {}
                    _schon = {t3 for t3, _ in folge[i][:pos[i]]}
                    _noch = {t3 for t3, _ in folge[i][pos[i]:]}
                    _zurueck = {t3: q3 for t3, q3 in (_extra or {}).items()
                                if int(t3) in _schon and int(t3) not in _noch}
                    if _zurueck:
                        _f.append((
                            "R1 Rueckschritt im Plan",
                            f"#{nr} Plan {i + 1} steht bei Stufe "
                            f"{pos[i]}/{len(folge[i])} und soll zurueck zu "
                            f"{sorted(_zurueck)[:3]}"))
                    for m3, q3 in hangar.items():
                        if q3 < 0:
                            _f.append(("R3 Hangar negativ",
                                       f"#{nr}: {m3} = {q3}"))
                            break
                if not etwas_ging and offen_da:
                    # R2: Leerlauf - aber nur, wenn wirklich NICHTS ging.
                    _f.append((
                        "R2 Leerlauf trotz offener Arbeit",
                        f"#{nr} Runde {runde}: kein Plan kann eine Stufe "
                        f"fahren, obwohl Arbeit offen ist"))
                    break
                if not offen_da:
                    break
            return _f

        _mit = _bauen(True)
        if _mit is None:
            continue
        n += 1
        fehler.extend(_mit[:3])
        # GEGENPROBE OHNE SCHLOSS - keine Zusage, nur eine Zahl.
        _ohne = _bauen(False)
        if _ohne is not None:
            laeufe_offen += 1
            if any(a.startswith("R1") for a, _ in _ohne):
                rueck_offen += 1
    return n, fehler, rueck_offen, laeufe_offen


def _fremde_arbeitsweisen(rng, anzahl=400):
    """Z9: Nutzer, die es ANDERS machen. (emm651)

    NUTZER 24.10.2026: "Wir können nicht davon ausgehen dass die Nutzer
    von EVE MoMa alles so machen wie ich es vorgesehen habe." Richtig -
    und die bisherigen Pruefungen gehen alle von SEINEM Ablauf aus
    (bauen, haken, ESI zieht nach).

    Sechs Arbeitsweisen werden gewuerfelt:
      "nie_haken"      - verlaesst sich nur auf ESI
      "alles_haken"    - hakt sofort alles ab, auch Ungebautes
      "halb"           - hakt die Haelfte
      "chaotisch"      - hakt zufaellig, auch mehr als geplant
      "kauft_zuviel"   - hat ueberall Ueberschuss
      "hat_nichts"     - leerer Hangar

    Geprueft werden Zusagen, die fuer JEDE Arbeitsweise gelten muessen:
      F1 nichts wirft eine Ausnahme,
      F2 keine negative Menge und keine negativen Runs,
      F3 `haken_pruefen` sagt nie "unbestaetigt", wenn ESI deckt,
      F4 `zusammenlegen_noetig` meldet nie, wenn EIN Slot reicht oder
         wenn schon die Summe nicht reicht,
      F5 `start_blocker` ist genau dann leer, wenn alles da ist,
      F6 `run_zustand` ist nie "fertig" ohne ESI-Beleg.
    """
    from eve_trader.ui.mw_helpers import (nachlauf_runs as _nr,
                                          haken_pruefen as _hp,
                                          zusammenlegen_noetig as _zn,
                                          start_blocker as _sb,
                                          run_zustand as _rz)
    arten = ("nie_haken", "alles_haken", "halb", "chaotisch",
             "kauft_zuviel", "hat_nichts")
    fehler, n = [], 0
    for _ in range(anzahl):
        art = rng.choice(arten)
        rezepte, enden, roh = _baum(rng)
        pf = _preise(rng, rezepte, roh).get
        hangar = {t: rng.randint(1, 30000)
                  for t in list(roh) + list(rezepte.product_to_bp)}
        if art == "kauft_zuviel":
            hangar = {t: q * rng.randint(5, 50) for t, q in hangar.items()}
        elif art == "hat_nichts":
            hangar = {}
        try:
            snap = _I.production_plan(
                rng.choice(enden), rng.randint(1, 200), pf, rezepte,
                {"me": 0, "me_reaction": 0, "job_pct": 0,
                 "build_reactions": True, "tree_depth": 9, "max_depth": 12,
                 "stock": dict(hangar)})
            _br = {int(k): int(v) for k, v in (snap.get("build_runs") or {}).items()}
            _made = {int(k): int(v) for k, v in (snap.get("build_made") or {}).items()}
            if not _br:
                continue
            _je = {t: max(1, _made.get(t, 0) // _br[t]) for t in _br if _br[t] > 0}
            _mats = snap.get("build_mats") or {}
            if art == "nie_haken":
                _erl = {}
            elif art == "alles_haken":
                _erl = dict(_br)
            elif art == "halb":
                _erl = {t: g // 2 for t, g in _br.items()}
            else:
                _erl = {t: rng.randint(0, g * 2) for t, g in _br.items()}
            n += 1
            # F1/F2 ------------------------------------------------------
            _e, _k = _nr(_br, _mats, _je, _erl, hangar)
            for _t, _v in list(_e.items()) + list(_k.items()):
                if int(_v) < 0:
                    fehler.append((f"F2 negative Menge [{art}]", f"{_t}: {_v}"))
            # F3 ---------------------------------------------------------
            _ts = {t: 0.0 for t in _erl}
            _hs = _hp(_erl, _ts, dict(_erl), {}, 10 ** 9)
            for _t, (_z, _n1, _n2) in _hs.items():
                if _z == "unbestaetigt" and _n2 >= _n1:
                    fehler.append((f"F3 Warnung trotz ESI-Deckung [{art}]",
                                   f"{_t}: {_n1}/{_n2}"))
            # F4 ---------------------------------------------------------
            _bed = {t: rng.randint(1, 50000) for t in list(hangar)[:8]}
            _wer = {t: {"A": hangar.get(t, 0) // 2,
                        "B": hangar.get(t, 0) - hangar.get(t, 0) // 2}
                    for t in _bed}
            for _t, _d in _zn(_bed, _wer).items():
                if _d["bester_menge"] >= _d["brauch"]:
                    fehler.append((f"F4 gemeldet, obwohl ein Slot reicht [{art}]",
                                   str(_t)))
                if _d["gesamt"] < _d["brauch"]:
                    fehler.append((f"F4 gemeldet, obwohl die Summe fehlt [{art}]",
                                   str(_t)))
            # F5 ---------------------------------------------------------
            _tid5 = next(iter(_br))
            _m5 = _mats.get(_tid5) or []
            _bl = _sb(_m5, _br, hangar)
            _alles_da = all(int(hangar.get(int(_m), 0)) >= int(_q)
                            and not _br.get(int(_m)) for _m, _q in _m5)
            if _alles_da and _bl:
                fehler.append((f"F5 blockiert, obwohl alles da ist [{art}]",
                               str(_tid5)))
            # F6 ---------------------------------------------------------
            if _rz(0, 0, 0, rng.randint(1, 99), rng.randint(0, 99)) == "fertig":
                fehler.append((f"F6 gruen ohne ESI-Beleg [{art}]", ""))
        except Exception as _e:
            fehler.append((f"F1 Ausnahme [{art}]", f"{type(_e).__name__}: {_e}"))
    return n, fehler


def _nachziehen_pruefen(rng, anzahl=200):
    """Z8: zieht der Plan nach, wenn Bestand verschwindet? (emm649)

    NUTZER 24.10.2026: "verliere ich bestand muss auch das die
    einkaufsliste nachziehen können, sie muss erkennen können welche runs
    jetzt nicht mehr ausgeführt werden können". Und zum selben Thema von
    der anderen Seite: "wenn ich mehr runs fahre als geplant ist es mein
    fehler, pech gehabt ABER der Plan muss erkennen dass jetzt vieleicht
    für andere Materialien die grundresourcen wieder fehlen".
    BEIDES IST DERSELBE FALL: der Plan kann nicht wissen, WARUM etwas
    weg ist (verkauft, Vertrag, zerstoert, extra Runs gefahren) - er
    merkt es am Bestand. Also wird genau das geprueft.

    Z8a MONOTONIE: weniger Bestand darf die Forderung nie KLEINER machen.
    Z8b ERKENNEN: verschwindet ein gekauftes Material ganz, muss es auf
        der Einkaufsliste landen.
    Z8c DECKUNG: kauft man, was die Liste sagt, und faehrt die
        geforderten Runs, ist die Luecke zu.
    """
    from eve_trader.ui.mw_helpers import nachlauf_runs as _nr
    fehler, n = [], 0
    for _ in range(anzahl):
        rezepte, enden, roh = _baum(rng)
        pf = _preise(rng, rezepte, roh).get
        hangar = {t: rng.randint(1, 50000)
                  for t in list(roh) + list(rezepte.product_to_bp)}
        try:
            snap = _I.production_plan(
                rng.choice(enden), rng.randint(1, 200), pf, rezepte,
                {"me": 0, "me_reaction": 0, "job_pct": 0,
                 "build_reactions": True, "tree_depth": 9, "max_depth": 12,
                 "stock": dict(hangar)})
        except Exception:
            continue
        _br = {int(k): int(v) for k, v in (snap.get("build_runs") or {}).items()}
        _made = {int(k): int(v) for k, v in (snap.get("build_made") or {}).items()}
        if not _br:
            continue
        _je = {t: max(1, _made.get(t, 0) // _br[t]) for t in _br if _br[t] > 0}
        _mats = snap.get("build_mats") or {}
        # Haelfte der Runs gefahren - der typische Zwischenstand.
        _erl = {t: g // 2 for t, g in _br.items()}
        n += 1
        _e0, _k0 = _nr(_br, _mats, _je, _erl, hangar)
        # JETZT VERSCHWINDET ETWAS (verkauft / extra Runs / Vertrag).
        _weg = dict(hangar)
        _ziel = [t for t in _weg if _weg[t] > 0]
        if not _ziel:
            continue
        for _t in rng.sample(_ziel, max(1, len(_ziel) // 3)):
            _weg[_t] = _weg[_t] // 3
        _e1, _k1 = _nr(_br, _mats, _je, _erl, _weg)
        # Z8a: nie weniger fordern als vorher.
        for _t, _q in _k0.items():
            if _k1.get(_t, 0) < _q:
                fehler.append(("Z8a Forderung schrumpft trotz Verlust",
                               f"{_t}: {_q} -> {_k1.get(_t, 0)}"))
        for _t, _r in _e0.items():
            if _e1.get(_t, 0) < _r:
                fehler.append(("Z8a Runs schrumpfen trotz Verlust",
                               f"{_t}: {_r} -> {_e1.get(_t, 0)}"))
        # Z8b: ein ganz verschwundenes Kauf-Material muss auffallen.
        _leer = dict(hangar)
        _kauf_t = [t for t in roh if _leer.get(t)]
        if _kauf_t:
            _t0 = rng.choice(_kauf_t)
            _leer[_t0] = 0
            _e2, _k2 = _nr(_br, _mats, _je, _erl, _leer)
            _braucht = sum(-(-int(_q) // _br[_t]) * max(0, _br[_t] - _erl.get(_t, 0))
                           for _t, _l in _mats.items() for _m, _q in (_l or [])
                           if int(_m) == _t0 and _br.get(_t))
            if _braucht > 0 and _k2.get(_t0, 0) <= 0 and _e2.get(_t0, 0) <= 0:
                fehler.append(("Z8b Verlust bleibt unbemerkt",
                               f"{_t0}: braucht {_braucht}, Liste sagt nichts"))
        # Z8c: kaufen + fahren schliesst die Luecke.
        _nach = dict(_weg)
        for _t, _q in _k1.items():
            _nach[_t] = _nach.get(_t, 0) + int(_q)
        _erl2 = dict(_erl)
        for _t, _r in _e1.items():
            _nach[_t] = _nach.get(_t, 0) + int(_r) * _je.get(_t, 1)
        _e3, _k3 = _nr(_br, _mats, _je, _erl2, _nach)
        if _k3:
            fehler.append(("Z8c Luecke bleibt nach dem Nachkaufen",
                           f"{len(_k3)} Posten offen"))
    return n, fehler


def _punkte_pruefen():
    """Z7: die ESI-Punkte im Runplaner - erschoepfend statt zufaellig.

    NUTZER 24.10.2026: "solange dann der gruene und Blaue ESI Icon noch
    ueber die verschiedenen Baupläne und Runs funktioniert und richtig
    tracket ... das ist ja meine sicherheit". Die Regel haengt an fuenf
    Zahlen, also wird sie hier VOLLSTAENDIG durchgezaehlt - 6^4 x 3
    Kombinationen sind billiger als jede Stichprobe und lassen keine
    Luecke.

    Geprueft werden die Zusagen, nicht die Formel:
      P1 GRUEN NUR MIT JOB. "fertig" (= gruener Punkt) darf es nur geben,
         wenn ESI geliefert hat oder ein Job abholbereit ist. Bestand
         allein ergibt NIE gruen (emm518: "habe ich nie gebaut aber dazu
         gekauft, warum zeigt ESI gruener Punkt?").
      P2 KEIN BELEG, KEIN PUNKT. Ohne jede Zahl bleibt "nicht_noetig"
         (emm521).
      P3 LAUFEND SCHLAEGT DECKUNG. Ein laufender Job wird nie von
         Bestandsdeckung ueberstimmt.
      P4 FERTIG BLEIBT FERTIG. Ist alles geliefert, macht ein zusaetzlich
         laufender Job daraus kein "laeuft" mehr.
      P5 MONOTONIE. Mehr Geliefertes macht eine Zeile nie wieder
         unfertiger (kein Zurueckfallen auf "bestand"/"nicht_noetig").
    """
    from eve_trader.ui.mw_helpers import run_zustand as _rz
    werte = (0, 1, 2, 5, 9, 10)
    fehler, n = [], 0
    for gel in werte:
        for lauf in werte:
            for fert in werte:
                for best in werte:
                    for plan in (0, 10, 20):
                        n += 1
                        z = _rz(gel, lauf, fert, best, plan)
                        if z == "fertig" and not (gel or fert):
                            fehler.append(("P1 gruen ohne Job",
                                           f"{gel}/{lauf}/{fert}/{best}/{plan}"))
                        if not (gel or lauf or fert or best) \
                                and z != "nicht_noetig":
                            fehler.append(("P2 Punkt ohne Beleg",
                                           f"-> {z}"))
                        if lauf > 0 and gel < plan and z != "laeuft":
                            fehler.append(("P3 Deckung ueberstimmt laufend",
                                           f"{gel}/{lauf}/{best}/{plan} -> {z}"))
                        if gel >= plan and gel > 0 and lauf > 0 \
                                and z != "fertig":
                            fehler.append(("P4 fertig wird wieder laeuft",
                                           f"{gel}/{lauf}/{plan} -> {z}"))
                        if z in ("bestand", "nicht_noetig") and (gel or fert):
                            fehler.append(("P5 Rueckfall trotz Job",
                                           f"{gel}/{fert} -> {z}"))
    return n, fehler


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anzahl", type=int, default=100,
                    help="Zahl der Szenarien (Vorgabe 100)")
    ap.add_argument("--samen", type=int, default=1,
                    help="Zufallssamen - gleicher Samen, gleiche Szenarien")
    ap.add_argument("--zeige", type=int, default=15,
                    help="wie viele Verletzungen im Bericht stehen")
    args = ap.parse_args()

    aus = []
    p = aus.append
    p("=" * 78)
    p(f"SZENARIO-WERKSTATT - Bauplan unter vielen Lagen (Fassung {FASSUNG})")
    p(f"Erstellt: {time.strftime('%Y-%m-%d %H:%M:%S')} (Ortszeit)")
    p("=" * 78)
    p("")
    p(f"  {args.anzahl} Szenarien, Samen {args.samen} (derselbe Samen")
    p("  erzeugt dieselben Szenarien - ein Fund ist also wiederholbar).")
    p("  Synthetische Rezepte, ECHTER Planer (`production_plan`) und die")
    p("  echte Reservierungskette. Kein ESI, keine Datenbank.")
    p("")

    # --- Z7 zuerst: die Punkte sind die Sicherheit des Nutzers --------
    _n7, _f7 = _punkte_pruefen()
    p("=" * 78)
    p("Z7) DIE ESI-PUNKTE IM RUNPLANER (erschoepfend)")
    p("=" * 78)
    p(f"  {_z(_n7)} Kombinationen aus geliefert / laufend / abholbereit /")
    p("  aus Bestand / Plan-Runs durchgezaehlt.")
    if not _f7:
        p("  Alle fuenf Zusagen gehalten: gruen nur mit Job, kein Punkt")
        p("  ohne Beleg, laufend schlaegt Deckung, fertig bleibt fertig,")
        p("  kein Rueckfall.")
    else:
        p(f"  {_z(len(_f7))} VERLETZUNGEN:")
        for art, txt in _f7[:10]:
            p(f"    {art}: {txt}")
    p("")

    rng = random.Random(args.samen)
    # --- Z13: die gestaffelte Baustrasse ------------------------------
    _n13, _f13, _ro13, _lo13 = _fliessband(rng, min(200, max(40, args.anzahl)))
    p("=" * 78)
    p("Z13) DIE GESTAFFELTE BAUSTRASSE UEBER MEHRERE PLAENE")
    p("=" * 78)
    p(f"  {_z(_n13)} Baustrassen: 3-5 Plaene ueber EINEN Rezeptbaum und")
    p("  EINEN Hangar, jeder betritt die Strasse eine Runde nach dem")
    p("  vorigen - die Staffelung aus seiner Arbeitsweise. Jeder kauft")
    p("  beim Eintritt seine Liste, dann ruecken alle rundenweise eine")
    p("  Stufe vor. Verbraucht wird wirklich.")
    p("")
    if not _f13:
        p("  ALLE DREI ZUSAGEN GEHALTEN:")
        p("    R1 KEIN RUECKSCHRITT - kein Plan musste je zu einer Stufe")
        p("       zurueck, die er schon abgeschlossen hatte.")
        p("    R2 KEIN LEERLAUF - solange Arbeit offen war, konnte immer")
        p("       mindestens ein Plan eine Stufe fahren.")
        p("    R3 Der Hangar wurde nie negativ.")
    else:
        p(f"  {_z(len(_f13))} VERLETZUNGEN:")
        for art, txt in _f13[:12]:
            p(f"    {art}: {txt}")
    p("")
    p("  GEGENPROBE OHNE SCHLOSS (keine Zusage, nur eine Zahl): dieselben")
    p(f"  Lagen ohne Reservierung - in {_z(_ro13)} von {_z(_lo13)} kam es zu")
    p("  einem Rueckschritt. Mit Reservierung kauft jeder neue Plan das,")
    p("  was die frueheren schon verplant haben; ohne sie rechnet er mit")
    p("  fremdem Material und schickt einen anderen Plan zurueck.")
    p("")

    # --- Z12: wen trifft es, und geht es besser? ----------------------
    (_n12, _f12, _knapp12, _bc12, _gc12, _sc12, _bb12,
     _gew12) = _vorrang_politik(rng, min(400, max(60, args.anzahl)))
    p("=" * 78)
    p("Z12) WENN ES NICHT FUER ALLE REICHT - WEN TRIFFT ES, UND")
    p("     GEHT ES BESSER?")
    p("=" * 78)
    p(f"  {_z(_n12)} Lagen mit ABSICHTLICH zu kleinem Hangar (30-95 % des")
    p(f"  Gesamtbedarfs). Davon wurden {_z(_knapp12)} wirklich knapp.")
    p("")
    if not _f12:
        p("  DIE HEUTIGE ART (Rang = Kartenreihenfolge) HAELT:")
        p("    W1 Rang 1 geht nie leer aus, solange der Vorrat ihn deckt.")
        p("    W2 Dasselbe Bild trifft zweimal denselben Plan - das Opfer")
        p("       wandert nicht.")
        p("    W3 Niemand nimmt mehr, als er braucht.")
    else:
        p(f"  {_z(len(_f12))} VERLETZUNGEN:")
        for art, txt in _f12[:12]:
            p(f"    {art}: {txt}")
    p("")
    p("  GEHT ES BESSER? Verglichen wurde, WIE VIELE PLAENE WIRKLICH")
    p("  FERTIG WERDEN - ein Plan mit 99 % seines Materials ist nicht zu")
    p("  99 % fertig, er steht.")
    p(f"    \"kleinster Bedarf zuerst\" schafft MEHR Plaene: {_z(_bc12)}")
    p(f"    gleich viele:                                   {_z(_gc12)}")
    p(f"    WENIGER Plaene:                                 {_z(_sc12)}")
    p(f"    anteilig (jeder denselben Bruchteil) besser:    {_z(_bb12)}")
    if _bc12:
        p(f"    Summe der zusaetzlich fertigen Plaene:          {_z(_gew12)}")
    p("")
    if _bc12 > _sc12:
        p("  BEFUND: eine andere Reihenfolge wuerde oft mehr Plaene")
        p("  fertig bekommen. TROTZDEM WIRD DIE REGEL NICHT GEAENDERT -")
        p("  sie ist eine Nutzer-Entscheidung (\"wenn ich einen Plan")
        p("  reserviert habe, dann baue ich ihn IMMER\"), und eine")
        p("  Maschine, die die Reihenfolge heimlich umstellt, nimmt ihm")
        p("  genau die Kontrolle, um die es ihm geht. Richtig ist, ihm")
        p("  den Vorschlag ZU ZEIGEN - er zieht die Karte selbst.")
    else:
        p("  BEFUND: die heutige Reihenfolge ist nicht schlechter als die")
        p("  Alternativen. Kein Grund, etwas umzustellen.")
    if _bb12 == 0:
        p("  \"Anteilig\" hat KEIN EINZIGES Mal mehr Plaene fertig")
        p("  bekommen: alle bekommen etwas, keiner wird fertig. Genau")
        p("  das wollte er nie - und jetzt steht die Zahl dahinter.")
    else:
        p(f"  \"Anteilig\" war in {_z(_bb12)} Lagen besser - das ist")
        p("  unerwartet und gehoert angeschaut, bevor jemand daraus")
        p("  etwas ableitet.")
    p("")

    # --- Z11: zwei Plaene gleichzeitig, bevor ESI nachzieht -----------
    _n11, _f11, _os11, _ol11 = _gleichzeitig_haken(
        rng, min(400, max(60, args.anzahl)))
    p("=" * 78)
    p("Z11) ZWEI PLAENE GLEICHZEITIG BAUEN, BEVOR ESI NACHZIEHT")
    p("=" * 78)
    p(f"  {_z(_n11)} Lagen: 2-3 Plaene mit Schloss ueber DENSELBEN")
    p("  Rezeptbaum und EINEN Hangar. Jeder hakt einen Anteil seiner")
    p("  Runs ab, 1 s bis 2 h nach dem Bestands-Abruf - also immer im")
    p("  gefaehrlichen Fenster. Verbraucht wird wirklich; der ESI-Hangar")
    p("  bleibt derweil auf dem alten Stand stehen.")
    if not _f11:
        p("  ALLE VIER ZUSAGEN GEHALTEN: im Verzug gibt ein Haken nichts")
        p("  frei (K1), nach dem Nachziehen sehr wohl (K2), kein Plan")
        p("  sieht Material, das ein anderer schon verbraucht hat (K3),")
        p("  und kein Anspruch wird negativ (K4).")
    else:
        p(f"  {_z(len(_f11))} VERLETZUNGEN:")
        for art, txt in _f11[:12]:
            p(f"    {art}: {txt}")
    p("")
    p("  MESSUNG OHNE SCHLOSS (keine Zusage, nur eine Zahl): in")
    p(f"  {_z(_os11)} von {_z(_ol11)} derselben Lagen haette ein Plan")
    p("  OHNE Reservierung Material als frei gesehen, das der andere")
    p("  schon verbraucht hatte. Das Schloss ist hier kein Komfort,")
    p("  sondern der Schutz selbst.")
    p("")

    # --- Z10: Chaos-Werkstatt (sein haertester Fall) ------------------
    _n10, _f10, _nf10 = _chaos_werkstatt(rng, min(200, max(40, args.anzahl // 3)))
    p("=" * 78)
    p("Z10) CHAOS-WERKSTATT: VIELE PLAENE, ACHT CHARAKTERE, FALSCHE MENGEN")
    p("=" * 78)
    p(f"  {_z(_n10)} Werkstaetten durchgespielt: 3-5 Plaene teilen EINEN")
    p("  Hangar und EINEN Rezeptbaum, jeder startet in einem anderen")
    p("  Stadium, dann fahren 8 Charaktere runden-weise irgendwelche Runs")
    p("  in falscher Menge (7 statt 10, manchmal 13, manchmal keine).")
    p("  Nach jeder Runde darf der Plan nachziehen.")
    if not _f10:
        p("  ES GEHT ZU ENDE: jede Werkstatt ist fertig geworden, die")
        p("  Einkaufsliste ist nicht weggelaufen, nichts wurde negativ,")
        p("  und es gab keine Runde mit Stillstand trotz offener Runs.")
    else:
        p(f"  {_z(len(_f10))} VERLETZUNGEN (davon {_z(_nf10)} nicht fertig):")
        for art, txt in _f10[:12]:
            p(f"    {art}: {txt}")
    p("")

    # --- Z9: Nutzer, die es anders machen -----------------------------
    _n9, _f9 = _fremde_arbeitsweisen(rng, min(600, max(100, args.anzahl * 2)))
    p("=" * 78)
    p("Z9) FREMDE ARBEITSWEISEN")
    p("=" * 78)
    p(f"  {_z(_n9)} Plaene mit sechs verschiedenen Nutzer-Gewohnheiten")
    p("  (nie haken / alles sofort haken / halb / chaotisch / zu viel")
    p("  gekauft / leerer Hangar).")
    if not _f9:
        p("  Alle sechs Zusagen gehalten - keine Ausnahme, keine negative")
        p("  Menge, keine Warnung trotz ESI-Deckung, kein Fehlalarm beim")
        p("  Zusammenlegen, kein falsches Blockieren, kein Gruen ohne Beleg.")
    else:
        p(f"  {_z(len(_f9))} VERLETZUNGEN:")
        for art, txt in _f9[:12]:
            p(f"    {art}: {txt}")
    p("")

    # --- Z8: zieht der Plan nach, wenn Bestand verschwindet? ----------
    _n8, _f8 = _nachziehen_pruefen(rng, min(300, max(50, args.anzahl)))
    p("=" * 78)
    p("Z8) BESTAND VERSCHWINDET - ZIEHT DER PLAN NACH?")
    p("=" * 78)
    p(f"  {_z(_n8)} Plaene durchgespielt: Haelfte gebaut, dann verschwindet")
    p("  ein Drittel der Posten (verkauft, Vertrag, zerstoert, oder extra")
    p("  Runs gefahren - der Plan sieht nur den fehlenden Bestand).")
    if not _f8:
        p("  Gehalten: die Forderung schrumpft nie, ein Verlust faellt auf,")
        p("  und nach Kaufen + Nachlauf-Runs ist die Luecke zu.")
    else:
        p(f"  {_z(len(_f8))} VERLETZUNGEN:")
        for art, txt in _f8[:10]:
            p(f"    {art}: {txt}")
    p("")

    t0 = time.time()
    treffer, gesamt_fehler, je_art = [], 0, {}
    for i in range(1, args.anzahl + 1):
        erg = _ein_szenario(rng, i)
        if erg["fehler"]:
            treffer.append(erg)
            gesamt_fehler += len(erg["fehler"])
            for art, _txt in erg["fehler"]:
                je_art[art] = je_art.get(art, 0) + 1
    dauer = time.time() - t0

    p("=" * 78)
    p("ERGEBNIS")
    p("=" * 78)
    p(f"  Szenarien gerechnet: {_z(args.anzahl)} in {dauer:.1f} s")
    p(f"  Szenarien mit Verletzung: {_z(len(treffer))}")
    p(f"  Verletzungen gesamt: {_z(gesamt_fehler)}")
    p("")
    if not je_art:
        p("  ALLE ZUSAGEN GEHALTEN. Das heisst NICHT, dass es keinen Fehler")
        p("  gibt - es heisst, dass diese Lagen ihn nicht treffen. Mit")
        p("  einem anderen Samen oder mehr Szenarien weitersuchen.")
    else:
        p(f"  {'ZUSAGE':38} {'VERLETZUNGEN':>13}")
        for art, n in sorted(je_art.items(), key=lambda x: -x[1]):
            p(f"  {art[:38]:38} {_z(n):>13}")
        p("")
        p("  BEISPIELE (mit Szenario-Nummer - mit demselben Samen genau")
        p("  wiederholbar):")
        gezeigt = 0
        for erg in treffer:
            for art, txt in erg["fehler"]:
                p(f"    #{erg['nr']:<4} {art}")
                p(f"           {txt}")
                gezeigt += 1
                if gezeigt >= args.zeige:
                    break
            if gezeigt >= args.zeige:
                break
        if gesamt_fehler > gezeigt:
            p(f"    ... und {_z(gesamt_fehler - gezeigt)} weitere")
    p("")
    p("  Dieses Werkzeug aendert nichts und braucht keinen Netzzugang.")
    os.makedirs(os.path.dirname(BERICHT), exist_ok=True)
    with open(BERICHT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(aus) + "\n")
    print("\n".join(aus))
    print(f"\nBericht: {BERICHT}")
    return 1 if gesamt_fehler else 0


if __name__ == "__main__":
    sys.exit(main())
