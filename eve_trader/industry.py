"""Recursive build-cost estimation (relative nullsec producer).

Uses the EVE SDE recipe tables (downloaded once from Fuzzwork) to compute an
approximate per-unit build cost. T2 intermediates from reactions are built from
scratch (that is where most of the margin sits), other components are built if
cheaper than buying, raw materials are priced from the market.

The result is a *relative* average, not an exact figure: it assumes a flat
material efficiency and a flat job-cost overhead rather than your specific
structure, rigs and system index.
"""
import csv
import io
import json
import math
import os
import sqlite3
import time

import requests

from . import config

MANUFACTURING = 1
COPYING = 5
INVENTION = 8
REACTION = 11
ACTIVITIES = (MANUFACTURING, REACTION)

# MULTI-BAUPLAN (1.0.9, Weg 1 "Buendel-Plan"): ein Multi-Plan ist ein normaler
# Bauplan, dessen Endprodukt ein PSEUDO-ITEM ist - Rezept "1 Buendel = 20 Viator
# + 10 Ishtar + ...". Negative IDs, damit sie nie mit einer EVE-Type-ID
# kollidieren. Das Buendel selbst hat ME 0, keine Job-Kosten, keine Zeit, wird
# nie gekauft und taucht in keinem Job auf - seine direkten Zutaten sind die
# Endprodukte des Multi-Plans (werden IMMER gebaut, wie ein Endprodukt).
BUENDEL_ID = -1
BUENDEL_BP = -2


def buendel_rezepte(recipes, enden):
    """Flache Rezept-Kopie mit dem Buendel als baubarem Pseudo-Item.
    `enden`: [(type_id, stueck), ...] - die Endprodukte des Multi-Plans mit
    ihren Mengen. Doppelte Type-IDs werden addiert, Mengen <= 0 fallen weg.
    Das Original bleibt unberuehrt (Prozess-Cache). Kombinierbar mit
    reprocess.rezepte_mit_unrefined (beide kopieren ihre Tabellen)."""
    import copy as _copy
    summe = {}
    for t, q in enden or ():
        t, q = int(t), int(q)
        if q > 0:
            summe[t] = summe.get(t, 0) + q
    if not summe:
        raise ValueError("bundle without end products")
    neu = _copy.copy(recipes)
    neu.product_to_bp = dict(recipes.product_to_bp)
    neu.bp_materials = dict(recipes.bp_materials)
    neu.activity_time = dict(recipes.activity_time)
    neu.product_to_bp[BUENDEL_ID] = (BUENDEL_BP, MANUFACTURING, 1)
    neu.bp_materials[(BUENDEL_BP, MANUFACTURING)] = sorted(summe.items())
    neu.activity_time[(BUENDEL_BP, MANUFACTURING)] = 0
    neu.buendel_enden = dict(summe)
    return neu


def buendel_enden(recipes) -> dict:
    """{type_id: stueck} der Endprodukte, wenn `recipes` ein Buendel traegt,
    sonst leer. EINE Stelle, an der die Kopie erkannt wird."""
    return dict(getattr(recipes, "buendel_enden", None) or {})


def enden_von(type_id, recipes) -> set:
    """Die Endprodukt-MENGE eines Plans: {type_id} - beim Buendel seine
    Enden. Jede Stelle, die frueher `tid == type_id` fragte ("ist das das
    Endprodukt?"), fragt jetzt `tid in enden_von(...)` - sonst waeren die
    Enden eines Multi-Bauplans ueberall "Komponenten" (falsche Stufe,
    Kategorie-ME statt eigener ME, Fortschritt am falschen Item)."""
    if type_id == BUENDEL_ID:
        return set(buendel_enden(recipes))
    return {type_id}


def ist_ende(tid, type_id, recipes) -> bool:
    """Kurzform von `tid in enden_von(type_id, recipes)`."""
    return tid == type_id or (type_id == BUENDEL_ID and tid in buendel_enden(recipes))


def buendel_kosten_je_ende(plan: dict) -> dict:
    """Was kostet JEDES Endprodukt eines Buendels - obwohl der Plan geteilte
    Zwischenprodukte nur EINMAL kauft oder baut?

    Zuordnung ANTEILIG NACH BEDARF: die Gesamtkosten eines Items (gekauft:
    Kaufpreis x Menge; gebaut: seine Zutaten zu deren Stueckkosten + Job +
    Invention; dazu verbrauchter Bestand) werden durch die Gesamtnachfrage
    geteilt und jedem Verbraucher mit seiner Menge belastet. Ueberschuss
    (Batch-Rundung) verteilt sich damit auf alle, die das Item brauchen -
    braucht A 2'000 X und B 1'000 X, traegt A zwei Drittel der X-Kosten.
    Ein Endprodukt, das selbst Zutat eines anderen Endes ist, gibt den
    Anteil weiter, den das andere Ende verbraucht.

    Rechnet NUR mit den Zahlen, die production_plan() exportiert
    (build_mats, *_cost_items) - kein zweiter Preisabruf, keine Nachrechnung
    (Arbeitsregel 9). Invariante: Summe von "gesamt" ueber alle Enden ==
    plan["total_cost"] (bis auf Gleitkomma).

    Rueckgabe {ende: {"menge", "gesamt", "je_stueck"}}; ohne Buendel {}."""
    enden = dict(plan.get("buendel_enden") or {})
    if not enden:
        return {}
    build_mats = plan.get("build_mats") or {}
    jc = plan.get("job_cost_items") or {}
    iv = plan.get("inv_cost_items") or {}
    kauf = plan.get("buy_cost_items") or {}
    bestand = plan.get("stock_cost_items") or {}
    # Gesamtnachfrage je Item = alles, was Verbraucher (Bau-Items + das
    # Buendel selbst) davon anfordern - VOR dem Bestandsabzug, denn auch der
    # verbrauchte Bestand kostet (stock_cost) und gehoert den Verbrauchern.
    bedarf = {}
    for tid, zutaten in build_mats.items():
        for m, jq in zutaten or ():
            bedarf[m] = bedarf.get(m, 0.0) + float(jq)
    for e, q in enden.items():
        bedarf[e] = bedarf.get(e, 0.0) + float(q)
    memo = {}
    unterwegs = set()

    def _gesamt(tid):
        """Alle Kosten, die dieses Item im Plan verursacht."""
        if tid in memo:
            return memo[tid]
        if tid in unterwegs:            # Kreis - production_plan laesst keinen zu
            return 0.0
        unterwegs.add(tid)
        k = float(kauf.get(tid, 0.0)) + float(bestand.get(tid, 0.0))
        if tid in build_mats:
            k += float(jc.get(tid, 0.0)) + float(iv.get(tid, 0.0))
            for m, jq in build_mats[tid] or ():
                k += float(jq) * _je_stueck(m)
        unterwegs.discard(tid)
        memo[tid] = k
        return k

    def _je_stueck(tid):
        b = bedarf.get(tid, 0.0)
        return _gesamt(tid) / b if b > 0 else 0.0

    aus = {}
    for e, q in enden.items():
        js = _je_stueck(e)
        aus[e] = {"menge": int(q), "gesamt": js * float(q), "je_stueck": js}
    # NACHGELAGERTE ERSPARNISSE ANTEILIG (Erz statt Mineral, Unrefined-
    # Ruecklaeufer): _reprocess_anwenden senkt plan["total_cost"], ohne die
    # Einzelposten zu aendern. Die Differenz zur Summe der Enden wird im
    # Verhaeltnis ihrer Kosten verteilt - so bleibt die Invariante
    # "Summe der Enden == total_cost" auch nach dem Reprocessing.
    summe = sum(k["gesamt"] for k in aus.values())
    tc = plan.get("total_cost")
    if summe > 0 and tc is not None and abs(float(tc) - summe) > 1e-6:
        f = float(tc) / summe
        for k in aus.values():
            k["gesamt"] *= f
            k["je_stueck"] *= f
    return aus


def _db_path():
    return os.path.join(config.app_data_dir(), "industry.db")


def type_id_for_name(name):
    """type_id für einen exakten Item-Namen, oder None. Für repräsentative
    Kategorie-Icons (z.B. "Meine Blueprints"-Panel) - kein Massen-Lookup,
    nur vereinzelte, feste Namen. Nutzt store.type_names (aus Markt-Scans/
    ESI gefüllt) - industry.db hat keine Namen, nur die rohe SDE-Struktur."""
    from . import store as _store
    try:
        with _store._conn() as c:
            row = c.execute("SELECT type_id FROM type_names WHERE name = ? LIMIT 1",
                            (name,)).fetchone()
            return int(row["type_id"]) if row else None
    except Exception:
        return None


def _conn():
    c = sqlite3.connect(_db_path(), timeout=30)
    c.row_factory = sqlite3.Row
    try:
        c.execute("PRAGMA journal_mode=WAL")
        c.execute("PRAGMA busy_timeout=30000")
    except Exception:
        pass
    return c


def init_db():
    # Tabellen `reprocess` / `reprocess_portion` (1.0.9, Vorbereitung): was
    # ein Erz oder ein Unrefined-Mineral beim Reprocessen ergibt - BASISWERT
    # je Portion laut SDE, ohne Ausbeute. Die Ausbeute (Struktur, Skills,
    # Implantat) kommt spaeter obendrauf. Kein SQL-Kommentar im Schema: der
    # steht in einem String, und de_scan4 liest Strings.
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS materials (
                blueprint_id INTEGER, activity_id INTEGER,
                material_id INTEGER, quantity INTEGER
            );
            CREATE TABLE IF NOT EXISTS products (
                blueprint_id INTEGER, activity_id INTEGER,
                product_id INTEGER, quantity INTEGER
            );
            CREATE TABLE IF NOT EXISTS probabilities (
                blueprint_id INTEGER, activity_id INTEGER,
                product_id INTEGER, probability REAL
            );
            CREATE TABLE IF NOT EXISTS activities (
                blueprint_id INTEGER, activity_id INTEGER, time INTEGER,
                max_runs INTEGER
            );
            CREATE INDEX IF NOT EXISTS ix_act ON activities(blueprint_id, activity_id);
            CREATE INDEX IF NOT EXISTS ix_mat ON materials(blueprint_id, activity_id);
            CREATE INDEX IF NOT EXISTS ix_prod ON products(product_id, activity_id);
            CREATE INDEX IF NOT EXISTS ix_prob ON probabilities(product_id, activity_id);
            CREATE TABLE IF NOT EXISTS meta (k TEXT PRIMARY KEY, v TEXT);
            CREATE TABLE IF NOT EXISTS item_cat (
                type_id INTEGER PRIMARY KEY, group_id INTEGER,
                category_id INTEGER, meta_group_id INTEGER, meta_level INTEGER
            );
            CREATE TABLE IF NOT EXISTS cat_name (category_id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE IF NOT EXISTS group_name (group_id INTEGER PRIMARY KEY, name TEXT);
            CREATE TABLE IF NOT EXISTS rigs (
                type_id INTEGER PRIMARY KEY, name TEXT, group_name TEXT,
                time_bonus REAL, material_bonus REAL, cost_bonus REAL, effects TEXT
            );
            CREATE TABLE IF NOT EXISTS decryptors (
                type_id INTEGER PRIMARY KEY, name TEXT,
                prob_mult REAL, me_mod REAL, te_mod REAL, run_mod REAL
            );
            CREATE TABLE IF NOT EXISTS implant_time_bonus (
                type_id INTEGER PRIMARY KEY, name TEXT, activity TEXT, pct REAL
            );
            CREATE TABLE IF NOT EXISTS bp_science_skills (
                blueprint_id INTEGER, skill_id INTEGER
            );
            CREATE INDEX IF NOT EXISTS ix_bpsci ON bp_science_skills(blueprint_id);
            CREATE TABLE IF NOT EXISTS bp_invention_skills (
                blueprint_id INTEGER, skill_id INTEGER, is_encryption INTEGER
            );
            CREATE INDEX IF NOT EXISTS ix_bpinvsci ON bp_invention_skills(blueprint_id);
            CREATE INDEX IF NOT EXISTS ix_itemcat ON item_cat(category_id);
            CREATE INDEX IF NOT EXISTS ix_itemcat_meta ON item_cat(meta_group_id);
            CREATE TABLE IF NOT EXISTS reprocess (
                type_id INTEGER, material_id INTEGER, quantity INTEGER
            );
            CREATE INDEX IF NOT EXISTS ix_repro ON reprocess(type_id);
            CREATE TABLE IF NOT EXISTS reprocess_portion (
                type_id INTEGER PRIMARY KEY, portion_size INTEGER
            );
            CREATE TABLE IF NOT EXISTS reprocess_skill_ids (
                name TEXT PRIMARY KEY, type_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS reprocess_erz_skill (
                type_id INTEGER PRIMARY KEY, skill_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS reprocess_implant (
                type_id INTEGER PRIMARY KEY, name TEXT, attr TEXT, value REAL
            );
            CREATE TABLE IF NOT EXISTS reprocess_struktur (
                type_id INTEGER PRIMARY KEY, name TEXT, bonus_pct REAL
            );
            CREATE TABLE IF NOT EXISTS reprocess_rig (
                type_id INTEGER PRIMARY KEY, name TEXT, mult REAL,
                hi REAL, low REAL, null_sec REAL
            );
            """
        )
        # migration for DBs created before meta_level existed
        try:
            c.execute("ALTER TABLE item_cat ADD COLUMN meta_level INTEGER")
        except Exception:
            pass   # column already present
        try:
            c.execute("ALTER TABLE item_cat ADD COLUMN volume REAL")
        except Exception:
            pass   # column already present
        try:
            c.execute("ALTER TABLE item_cat ADD COLUMN packaged_volume REAL")
        except Exception:
            pass   # column already present
        try:
            c.execute("ALTER TABLE item_cat ADD COLUMN race_id INTEGER")
        except Exception:
            pass   # column already present
        try:
            c.execute("ALTER TABLE rigs ADD COLUMN effects TEXT")
        except Exception:
            pass   # column already present
        try:
            c.execute("ALTER TABLE activities ADD COLUMN max_runs INTEGER")
        except Exception:
            pass   # column already present


_KATMAP_CACHE = {"sig": None, "obj": None}
# SDE-STAND: wird bei jedem Neueinlesen der SDE hochgezaehlt. Der Datei-
# Schluessel allein reicht NICHT (gemessen, aa425): industry.db laeuft im
# WAL-Modus, neue Zeilen stehen zuerst in der -wal-Datei, und die Hauptdatei
# aendert Groesse und Zeit erst beim Checkpoint - solange noch Verbindungen
# offen sind, kann das dauern. Deshalb verwirft download_sde die gemerkten
# Kopien ausdruecklich, und eine Lesung, waehrend der die SDE neu kam, wird
# nicht gemerkt.
_SDE_STAND = [0]


def _sde_caches_verwerfen():
    """Gemerkte SDE-Kopien (Kategorien, Rezepte) verwerfen - nach jedem
    Neueinlesen der SDE."""
    _SDE_STAND[0] += 1
    _KATMAP_CACHE.update({"sig": None, "obj": None})
    _RECIPES_CACHE.update({"sig": None, "obj": None})


def _industry_db_sig():
    """(Groesse, Aenderungszeit) von industry.db - dasselbe Prinzip und
    derselbe Schluessel wie `recipes_cached`: die Datei selbst, kein Zaehler.
    Die -wal-Datei zaehlt bewusst NICHT mit: sqlite legt sie beim Oeffnen an
    und loescht sie beim Schliessen der letzten Verbindung wieder - der
    Schluessel wuerde dann bei jedem Aufruf kippen (gemessen, aa425)."""
    try:
        _st = os.stat(_db_path())
        return (_st.st_size, int(_st.st_mtime_ns))
    except OSError:
        return None


def item_category_map() -> dict:
    """type_id -> (category_id, group_id, meta_group_id).

    GEMERKT (Ladezeit-Messung des Nutzers, 27.09.2026): die ganze Tabelle
    item_cat wurde bei JEDEM Aufruf neu gelesen - 309 Mal beim Oeffnen eines
    Bauplans samt Plan-Karten, 21 s reine Rechenzeit. Die Daten aendern sich
    nur, wenn die SDE neu eingelesen wird; dann aendert sich die Datei und
    die Kopie wird verworfen. NUR LESEN: niemand im Programm schreibt in das
    zurueckgegebene Woerterbuch (gemessen, wie bei recipes_cached)."""
    if not os.path.exists(_db_path()):
        return {}
    sig = _industry_db_sig()
    if sig is not None and _KATMAP_CACHE["sig"] == sig and _KATMAP_CACHE["obj"] is not None:
        return _KATMAP_CACHE["obj"]
    stand = _SDE_STAND[0]
    try:
        with _conn() as c:
            obj = {r["type_id"]: (r["category_id"], r["group_id"], r["meta_group_id"])
                   for r in c.execute(
                       "SELECT type_id,category_id,group_id,meta_group_id FROM item_cat")}
    except Exception:
        return {}
    if stand == _SDE_STAND[0]:           # waehrenddessen keine neue SDE
        _KATMAP_CACHE["sig"] = sig
        _KATMAP_CACHE["obj"] = obj
    return obj


# Standard-Rassen-IDs (feste EVE-Konstanten, seit Spielbeginn unverändert):
RACE_NAMES = {1: "Caldari", 2: "Minmatar", 4: "Amarr", 8: "Gallente"}


def item_race_map() -> dict:
    """type_id -> race_id (1=Caldari, 2=Minmatar, 4=Amarr, 8=Gallente), nur für
    Items mit einer echten Rassen-Zuordnung (v.a. Schiffe) - andere (Module,
    Munition usw.) haben meist KEINE raceID in der SDE und fehlen hier
    entsprechend. Separat von item_category_map(), damit dessen bestehende
    3-Tupel-Auswertungen im restlichen Code unverändert bleiben."""
    if not os.path.exists(_db_path()):
        return {}
    try:
        with _conn() as c:
            return {r["type_id"]: r["race_id"]
                    for r in c.execute(
                        "SELECT type_id, race_id FROM item_cat WHERE race_id IS NOT NULL")}
    except Exception:
        return {}


def bp_science_skills_map() -> dict:
    """blueprint_id -> set(skill_id) der zeitrelevanten Science-Skills (je −1 %
    Fertigungszeit/Level). Leer, wenn die SDE (noch) keine solchen Daten hat –
    dann einmal „Baurezepte laden“ (neuer SDE-Download) ausführen."""
    if not os.path.exists(_db_path()):
        return {}
    try:
        out = {}
        with _conn() as c:
            for r in c.execute(
                    "SELECT blueprint_id, skill_id FROM bp_science_skills"):
                out.setdefault(r["blueprint_id"], set()).add(r["skill_id"])
        return out
    except Exception:
        return {}


def bp_invention_skills_map() -> dict:
    """blueprint_id (T1-BP, das für Invention genutzt wird) -> {"encryption":
    skill_id oder None, "science": [skill_id, ...]} - die Skills, die laut SDE
    (industryActivitySkills, activityID=INVENTION) für die Erfolgschance
    dieses Items zählen. Leer, wenn die SDE (noch) keine solchen Daten hat."""
    if not os.path.exists(_db_path()):
        return {}
    try:
        out = {}
        with _conn() as c:
            for r in c.execute(
                    "SELECT blueprint_id, skill_id, is_encryption "
                    "FROM bp_invention_skills"):
                d = out.setdefault(r["blueprint_id"], {"encryption": None, "science": []})
                if r["is_encryption"]:
                    d["encryption"] = r["skill_id"]
                else:
                    d["science"].append(r["skill_id"])
        return out
    except Exception:
        return {}


def invention_skill_modifier(bp_id, char_skills, invention_skills_map):
    """Offizielle EVE-Formel: SkillModifier = 1 + Encryption-Level/40 +
    (Datacore-Skill-1-Level + Datacore-Skill-2-Level)/30 - multipliziert
    direkt auf die Basis-Erfolgschance (VOR dem Decryptor-Modifikator).
    Ohne SDE-Daten für dieses Blueprint (invention_skills_map leer) oder ohne
    Charakter-Skilldaten: 1.0 (keine Änderung, alter Pfad bleibt aktiv statt
    zu raten). char_skills: {skill_id: level}, normalisierte int-Keys."""
    info = (invention_skills_map or {}).get(bp_id)
    if not info:
        return 1.0
    cs = char_skills or {}
    enc_id = info.get("encryption")
    enc_level = int(cs.get(enc_id, 0) or 0) if enc_id else 0
    sci_levels = sorted((int(cs.get(sid, 0) or 0) for sid in (info.get("science") or [])),
                        reverse=True)
    sci_sum = sum(sci_levels[:2])
    return 1.0 + enc_level / 40.0 + sci_sum / 30.0


def item_volume_map(type_ids=None) -> dict:
    """type_id -> packaged volume (m³) from the SDE. Uses invVolumes (packaged/
    cargo size) when the SDE has it — this is what matters for freight, and is
    the ONLY correct value for ships/capital modules (their invTypes volume is
    the as-fit size, e.g. ~15'000 m³ for a Vagabond vs. ~2'500 m³ packaged).
    Falls back to the invTypes volume when no packaged value is in the SDE
    (some SDE conversions don't ship invVolumes, or miss individual items —
    in that case ships will be overstated here; re-load the SDE to check).
    Empty if the SDE predates the volume column (re-load fixes it)."""
    if not os.path.exists(_db_path()):
        return {}
    try:
        with _conn() as c:
            if type_ids:
                ids = [int(t) for t in type_ids]
                q = ("SELECT type_id, COALESCE(packaged_volume, volume) AS v "
                     "FROM item_cat WHERE COALESCE(packaged_volume, volume) IS NOT NULL "
                     "AND type_id IN (%s)" % ",".join("?" * len(ids)))
                rows = c.execute(q, ids)
            else:
                rows = c.execute(
                    "SELECT type_id, COALESCE(packaged_volume, volume) AS v FROM item_cat "
                    "WHERE COALESCE(packaged_volume, volume) IS NOT NULL")
            return {r["type_id"]: (r["v"] or 0.0) for r in rows}
    except Exception:
        return {}


def transport_estimate(buy: dict, volumes: dict, capacity_m3: float = 0.0,
                        mode: str = None, rate_per_m3: float = 0.0,
                        trip_cost: float = 0.0) -> dict:
    """Cargo volume + transport cost for a buy-list (type_id -> qty).

    volumes: type_id -> m³/unit (from item_volume_map). Items with an unknown
    volume count as 0 m³ and are listed in "missing" (SDE has no volume for
    them yet, or they're not in the buy list's category coverage).
    capacity_m3: cargo capacity per trip, e.g. ~350'000 m³ for one jump
    freighter. 0/None = unbegrenzt (no trip count, no over-capacity warning).
    BEIDE Kostenarten zaehlen IMMER und werden ADDIERT (Nutzer-Fall: ein
    Frachtdienst nach ISK/m3 UND zusaetzlich eigene Spruenge mit dem
    Jumpfrachter, deren Fuel als Pauschale pro Fahrt anfaellt):
        cost = total_volume * rate_per_m3  +  trips * trip_cost
    Ein Wert von 0 faellt dabei einfach weg - kein Entweder/Oder mehr.
    `mode` ist nur noch fuer Altaufrufer da: "per_m3" bzw. "per_trip"
    blenden die jeweils ANDERE Komponente aus (altes Verhalten).
    """
    total = 0.0
    missing = []
    for tid, qty in (buy or {}).items():
        v = volumes.get(tid)
        if v is None:
            missing.append(tid)
            v = 0.0
        total += float(v) * float(qty)
    cap = float(capacity_m3 or 0)
    trips = (int(-(-total // cap)) if cap > 0 else (1 if total > 0 else 0))
    over_capacity = bool(cap > 0 and total > cap)
    _c_m3 = total * float(rate_per_m3 or 0)
    _c_trip = trips * float(trip_cost or 0)
    if mode == "per_trip":
        _c_m3 = 0.0            # Altverhalten
    elif mode == "per_m3":
        _c_trip = 0.0          # Altverhalten
    cost = _c_m3 + _c_trip
    return {"volume": total, "capacity": cap, "trips": trips,
            "over_capacity": over_capacity, "cost": cost,
            "cost_m3": _c_m3, "cost_trip": _c_trip,
            "missing_volume": missing}


def freight_adjusted_price_fn(price_fn, volumes, rate_per_m3):
    """Kaufpreis INKLUSIVE Frachtaufschlag (Nutzer-Wunsch).

    Ohne das entscheidet `production_plan`/`build_cost` pro Knoten allein
    ueber den reinen Marktpreis - dass eine Variante deutlich mehr Frachtraum
    frisst, sah das Tool nicht. Der Aufschlag `Volumen x ISK/m3` macht die
    Entscheidung frachtbewusst, OHNE die Entscheidungslogik anzufassen: sie
    rechnet einfach mit dem LANDEPREIS statt dem Hub-Preis.

    NUR die ISK/m3-Komponente laesst sich so verteilen. Eine Pauschale pro
    Fahrt ist eine Sprungfunktion (ein einzelnes Item kostet nichts extra,
    bis es die Fahrt kippt) - die bleibt bewusst eine Kostenposition auf
    Plan-Ebene und wird NICHT pro Item umgelegt.

    rate_per_m3 = 0 -> die Original-Funktion wird unveraendert zurueckgegeben
    (kein Wrapper, keine Kosten, kein Verhaltensunterschied).
    """
    rate = float(rate_per_m3 or 0)
    if rate <= 0:
        return price_fn
    vols = volumes or {}

    def _fn(tid):
        p = price_fn(tid)
        if p is None:
            return None
        return float(p) + float(vols.get(tid, 0) or 0) * rate
    return _fn


def ships_with_unpackaged_volume(type_ids) -> set:
    """type_ids (aus category 6 Ship / 65 Structure) deren SDE-Zeile KEIN
    packaged_volume (invVolumes) hat — item_volume_map() musste dann auf die
    AS-FIT-Größe zurückfallen, die für Fracht viel zu groß ist (z.B. Vagabond
    ~15'000 m³ as-fit vs. ~2'500 m³ gepackt). Zum Warnen, bevor man den
    Frachtraum-Zahlen für Schiffe/Strukturen im Plan blind vertraut."""
    ids = list(type_ids or [])
    if not os.path.exists(_db_path()) or not ids:
        return set()
    try:
        with _conn() as c:
            q = ("SELECT type_id FROM item_cat WHERE category_id IN (6,65) "
                 "AND packaged_volume IS NULL AND type_id IN (%s)"
                 % ",".join("?" * len(ids)))
            return {r["type_id"] for r in c.execute(q, [int(t) for t in ids])}
    except Exception:
        return set()


def item_meta_level_map() -> dict:
    """type_id -> metaLevel (0 = base T1, 1-4 = named 'Compact/Enduring/...'
    modules). Empty if the SDE predates the meta_level column (re-load fixes it)."""
    if not os.path.exists(_db_path()):
        return {}
    try:
        with _conn() as c:
            return {r["type_id"]: (r["meta_level"] or 0)
                    for r in c.execute(
                        "SELECT type_id, meta_level FROM item_cat "
                        "WHERE meta_level IS NOT NULL")}
    except Exception:
        return {}


def _gids_matching_from(names_by_gid, substrings) -> set:
    """group_ids, deren Name eines der Teilworte enthaelt - EIN Helfer fuer
    alle Gruppenregeln (LP-gesperrt, Capital-Bau-Teile, Booster), statt
    dreimal derselben Schleife (Arbeitsregel 9). PURE Funktion, ohne DB
    testbar; leere Eingabe -> leeres Set (Schutzgitter der Aufrufer)."""
    out = set()
    for gid, name in (names_by_gid or {}).items():
        low = (name or "").lower()
        if any(sub in low for sub in substrings):
            out.add(gid)
    return out


def _booster_gids_from(names_by_gid) -> set:
    """Booster-/Drogen-Gruppen ("Booster" im Gruppennamen). Nutzer: "Drogen
    und Booster haben im Reaktionen-Preset nix verloren" - die "Pure ..."-
    Booster sind SDE-Reaktionsprodukte (Gas -> Reaktion -> Pure Booster)
    und tauchten deshalb dort auf; gemeint sind mit dem Preset aber die
    Mond-/Hybrid-Ketten."""
    # NACHGEMESSEN (Nutzer-Screenshot: Booster standen weiter im
    # Reaktionen-Preset): die "Pure ..."-Booster heissen in der SDE-Gruppe
    # NICHT "Booster", sondern "Biochemical Material" (Gruppe 712, enthaelt
    # laut Item-DB ausschliesslich Pure-Booster). "booster" bleibt fuer die
    # Endprodukt-Gruppe drin, falls sie je als Reaktionsprodukt auftaucht.
    return _gids_matching_from(names_by_gid,
                               ("booster", "biochemical material"))


def booster_group_ids() -> set:
    """group_ids der Booster-Gruppen aus der lokalen SDE (Schutzgitter wie
    bei den Schwester-Funktionen: leere Tabelle -> nichts filtern)."""
    if not os.path.exists(_db_path()):
        return set()
    try:
        with _conn() as c:
            rows = {r["group_id"]: r["name"]
                    for r in c.execute("SELECT group_id, name FROM group_name")}
        return _booster_gids_from(rows)
    except Exception:
        return set()


def _container_gids_from(names_by_gid) -> set:
    """Gruppen ECHTER Behaelter - PURE Funktion, ohne DB testbar.

    NUTZER-BEFUND 15.09.2026: "das Portfolio trackt nur Items in Station
    Containern und in keinen anderen Containern". Der Grund lag darin, dass
    ein Behaelter bisher NICHT an seinem Typ erkannt wurde, sondern daran,
    dass sein Inhalt die ESI-Markierung `Unlocked`/`Locked` trug - und die
    tragen nur die abschliessbaren Station-Container. Was ein Freight
    Container meldet, weiss von aussen niemand sicher; deshalb wird der
    BEHAELTER erkannt, nicht sein Inhalt.

    Kriterium ist der Gruppenname ("... Container"), wie bei den
    Schwesterregeln - keine gepflegte Item-Liste, die bei jedem EVE-Update
    veraltet. Blaupausen fliegen raus ("Container Blueprints").

    "FREIGHT" DARF NICHT DAS KRITERIUM SEIN: die Gruppen "Freighter",
    "Jump Freighter" und "Irregular Freighter" sind SCHIFFE. Nur "container"
    im Namen trifft sie nicht - "Freight Container" dagegen schon.

    Gemessen an der mitgelieferten SDE: Cargo Container, Secure Cargo
    Container, Audit Log Secure Container, Freight Container, Spawn/Mission/
    Scatter/Irregular/Salvage Container.
    """
    out = set()
    for gid, name in (names_by_gid or {}).items():
        low = (name or "").lower()
        if "container" in low and "blueprint" not in low:
            out.add(gid)
    return out


def container_group_ids() -> set:
    """group_ids der Behaelter-Gruppen aus der lokalen SDE (Schutzgitter wie
    bei den Schwesterfunktionen: keine Datenbank -> leeres Set. Dann gilt
    wieder allein die alte Inhalts-Regel, statt gar nichts zu finden)."""
    if not os.path.exists(_db_path()):
        return set()
    try:
        with _conn() as c:
            rows = {r["group_id"]: r["name"]
                    for r in c.execute("SELECT group_id, name FROM group_name")}
        return _container_gids_from(rows)
    except Exception:
        return set()


def container_type_ids() -> set:
    """type_ids ALLER Behaelter-Typen - das, was der Assets-Abruf braucht.

    Leeres Set, wenn die SDE fehlt: der Aufrufer faellt dann auf die alte
    Inhalts-Regel zurueck (Station-Container werden also weiter erkannt).
    """
    gids = container_group_ids()
    if not gids:
        return set()
    try:
        return {t for t, v in item_category_map().items() if v[1] in gids}
    except Exception:
        return set()


# ---- Reprocessing-Ausgang (1.0.9, Vorbereitung) ------------------------------
# Datengrundlage fuer zwei kommende Rechenwege (Nutzer, 17.09.2026):
#   A) Unrefined-Reaktionen: Prismaticite + Gas -> "Unrefined X" -> reprocess
#      -> Mineral X   (1 Eingang -> 1 Mineral)
#   B) Compressed Ore statt Minerale kaufen: Erz -> reprocess -> mehrere
#      Minerale, gegen Volumen/Transport gerechnet
# Hier liegt NUR der SDE-Basiswert je Portion. Die Ausbeute (Struktur x
# Skills x Implantat) und "variable Menge" bei Unrefined sind offen und
# werden erst nach der Messung im Spiel gebaut - vorher rechnet nichts damit.

def reprocess_map() -> dict:
    """{type_id: {"portion": n, "out": {material_id: Stueck je Portion}}}
    aus der lokalen Rezeptdatenbank. Leer, wenn die SDE fehlt oder die
    Tabelle noch nie gefuellt wurde (Fassung vor 1.0.9)."""
    if not os.path.exists(_db_path()):
        return {}
    try:
        with _conn() as c:
            portion = {int(r["type_id"]): int(r["portion_size"] or 1)
                       for r in c.execute("SELECT type_id, portion_size "
                                          "FROM reprocess_portion")}
            out = {}
            for r in c.execute("SELECT type_id, material_id, quantity "
                               "FROM reprocess"):
                t = int(r["type_id"])
                e = out.setdefault(t, {"portion": portion.get(t, 1), "out": {}})
                e["out"][int(r["material_id"])] = int(r["quantity"] or 0)
            return out
    except Exception:
        return {}


def reprocess_ergebnis(basis: dict, portion: int, menge: int, ausbeute: float) -> dict:
    """{material_id: Stueck} fuer `menge` Eingangs-Items bei `ausbeute` (0..1).

    PURE Funktion, ohne DB pruefbar. Zwei Regeln, beide Regel 3 (im Zweifel
    weniger, nie mehr):
    - nur VOLLE Portionen zaehlen - ein Rest unter der Portionsgroesse wird
      im Spiel nicht reprocessed;
    - je Portion wird ABGERUNDET, nicht gerundet.
    Ausbeute ausserhalb 0..1 oder Portion < 1 -> leeres Ergebnis (lieber
    nichts als eine Fantasiezahl).
    """
    try:
        portion = int(portion)
        menge = int(menge)
        ausbeute = float(ausbeute)
    except (TypeError, ValueError):
        return {}
    if portion < 1 or menge < portion or not (0.0 < ausbeute <= 1.0):
        return {}
    portionen = menge // portion
    out = {}
    for mat, q in (basis or {}).items():
        try:
            je_portion = int(math.floor(int(q) * ausbeute))
        except (TypeError, ValueError):
            continue
        if je_portion > 0:
            out[int(mat)] = je_portion * portionen
    return out


def reprocess_skill_ids() -> dict:
    """{Skillname: type_id} der Gruppe, in der 'Reprocessing' liegt - aus der
    SDE, nicht hartkodiert. Leer ohne Datenbank / vor dem ersten Load."""
    if not os.path.exists(_db_path()):
        return {}
    try:
        with _conn() as c:
            return {str(r["name"]): int(r["type_id"])
                    for r in c.execute("SELECT name, type_id FROM reprocess_skill_ids")}
    except Exception:
        return {}


def reprocess_erz_skill() -> dict:
    """{type_id: skill_id} - welcher Erz-Skill zu welchem Erz / Unrefined-
    Produkt gehoert (SDE-Attribut reprocessingSkillType). Leer, wenn die SDE
    das Attribut nicht kennt."""
    if not os.path.exists(_db_path()):
        return {}
    try:
        with _conn() as c:
            return {int(r["type_id"]): int(r["skill_id"])
                    for r in c.execute("SELECT type_id, skill_id FROM reprocess_erz_skill")}
    except Exception:
        return {}


def reprocess_implants() -> dict:
    """{type_id: {"name", "attr", "value"}} der Beancounter-Reprocessing-
    Implantate mit dem SDE-Attribut, das den Bonus traegt - MIT Namen, weil
    die Bedeutung des Werts erst gegen die Messung im Spiel geprueft wird."""
    if not os.path.exists(_db_path()):
        return {}
    try:
        with _conn() as c:
            return {int(r["type_id"]): {"name": str(r["name"] or ""),
                                        "attr": str(r["attr"] or ""),
                                        "value": float(r["value"] or 0.0)}
                    for r in c.execute("SELECT type_id, name, attr, value "
                                       "FROM reprocess_implant")}
    except Exception:
        return {}


def reprocess_struktur_sde() -> dict:
    """{"bonus": {name: pct}, "rig": {type_id: {"name","mult","hi","low","null"}}}
    aus der SDE (strRefiningYieldBonus der Refineries, refiningYieldMultiplier
    + Sicherheits-Faktoren der Standup-Reprocessing-Rigs). Leer vor dem
    ersten "Load recipes" mit dem Stand vom 18.09.2026."""
    if not os.path.exists(_db_path()):
        return {"bonus": {}, "rig": {}}
    out = {"bonus": {}, "rig": {}}
    try:
        with _conn() as c:
            for r in c.execute("SELECT name, bonus_pct FROM reprocess_struktur"):
                out["bonus"][str(r["name"])] = float(r["bonus_pct"] or 0.0)
            for r in c.execute("SELECT type_id, name, mult, hi, low, null_sec "
                               "FROM reprocess_rig"):
                out["rig"][int(r["type_id"])] = {
                    "name": str(r["name"] or ""), "mult": float(r["mult"] or 0.0),
                    "hi": float(r["hi"] or 1.0), "low": float(r["low"] or 1.0),
                    "null": float(r["null_sec"] or 1.0)}
    except Exception:
        return {"bonus": {}, "rig": {}}
    return out


# AUSBEUTE-FORMEL (gegen die Messung des Nutzers vom 18.09.2026 geprueft,
# Tatara "R&R Yard", Null, Standup L-Set Reprocessing Monitor I):
#   Struktur-Basis  = Rig-Multiplikator (0.51 / 0.53; ohne Rig 0.50 des
#                     Service-Moduls) x Sicherheits-Faktor des Rigs
#                     (hiSec 1.0 / lowSec 1.06 / nullSec 1.12, Attribute
#                     2355-2357 des Rigs) x (1 + Struktur-Bonus/100)
#                     (Athanor 2.0, Tatara 5.5, strRefiningYieldBonus)
#   Charakter-Faktor = (1 + 0.03 * Reprocessing) * (1 + 0.02 * Reprocessing
#   Efficiency) * (1 + 0.02 * Erz-Skill) * (1 + Implantat-% / 100)
#   Ausbeute        = Struktur-Basis * Charakter-Faktor, je Ausgang abgerundet
# BELEG: 0.51 x 1.12 x 1.055 = 0.60262; x 1.15 x 1.1 (Skills 5/5, Erz-Skill 0)
# = 0.76231 -> Compressed Arkonor 3200/1200/120 -> 2439/914/91 (Spiel: genau
# das); x 1.1 (Simple Ore Processing 5) = 0.83854 -> Compressed Veldspar 400
# -> 335 (Spiel: 335). Die Prozentsaetze stammen aus der SDE (Attribut
# refiningYieldMutator: Reprocessing 3, Efficiency 2, Erz-Skills 2, Implantat
# RX-801/802/804 = 1/2/4). NICHT gemessen: Struktur OHNE Rig (0.50 x Bonus)
# und das Implantat - beide folgen derselben Bauart, bleiben aber bis zu
# einer Messung als "aus der SDE abgeleitet" markiert. Wer die Formel
# aendert, aendert sie HIER - kein Korrekturfaktor anderswo.
REPRO_JE_STUFE = 0.03
REPRO_EFF_JE_STUFE = 0.02
REPRO_ERZ_JE_STUFE = 0.02
REPRO_SERVICE_BASIS = 0.50
# SCRAPMETAL-PFAD (gemessen 19.09.2026, Unrefined Titanium Chromide): Basis
# 50 % x (1 + 0.02 x Scrapmetal Processing) - sonst nichts. Reprocessing,
# Reprocessing Efficiency, Erz-Skill, Rig und Struktur-Bonus tauchten in der
# Vorschau nicht auf (Skills 5/5 vorhanden, Struktur mit Rig). 36 -> 19 und
# 164 -> 86 bei 53,0 %: abgerundet je Stueck, wie reprocess_ergebnis rechnet.
REPRO_SCRAP_JE_STUFE = 0.02


def reprocess_struktur_basis(rig_multiplikator=None, sicherheits_faktor=1.0,
                             struktur_bonus_pct=0.0):
    """Struktur-Basis 0..1. Ohne Rig gilt das Service-Modul (0.50); ein Rig
    ERSETZT diesen Wert (0.51 / 0.53) und wird mit dem Sicherheits-Faktor
    des Rigs multipliziert (1.0 / 1.06 / 1.12); der Struktur-Bonus (Athanor
    2.0, Tatara 5.5) wirkt multiplikativ. NPC-Station: alles leer -> 0.50.
    None bei Muell oder ueber 100 %."""
    try:
        basis = REPRO_SERVICE_BASIS if rig_multiplikator is None else float(rig_multiplikator)
        sec = float(sicherheits_faktor if sicherheits_faktor is not None else 1.0)
        bonus = float(struktur_bonus_pct or 0.0)
    except (TypeError, ValueError):
        return None
    if not (0.0 < basis <= 1.0) or sec < 1.0 or bonus < 0.0 or bonus > 100.0:
        return None
    a = basis * sec * (1.0 + bonus / 100.0)
    return a if a <= 1.0 else None


def _stufe(x):
    try:
        v = int(x)
    except (TypeError, ValueError):
        return None
    return v if 0 <= v <= 5 else None


def reprocess_char_faktor(reprocessing, efficiency, erz_skill, implant_pct=0.0):
    """Skill-x-Implantat-Faktor eines Charakters (>= 1.0) oder None bei
    Muell (Stufe ausserhalb 0..5, Implantat negativ / keine Zahl)."""
    r, e, s = _stufe(reprocessing), _stufe(efficiency), _stufe(erz_skill)
    if r is None or e is None or s is None:
        return None
    try:
        imp = float(implant_pct or 0.0)
    except (TypeError, ValueError):
        return None
    if imp < 0.0 or imp > 100.0:
        return None
    return ((1.0 + REPRO_JE_STUFE * r) * (1.0 + REPRO_EFF_JE_STUFE * e)
            * (1.0 + REPRO_ERZ_JE_STUFE * s) * (1.0 + imp / 100.0))


def reprocess_ausbeute(struktur_basis, char_faktor):
    """Ausbeute 0..1 aus Struktur-Basis (0..1, Rig schon eingerechnet) und
    Charakter-Faktor. None, wenn das Ergebnis keine Ausbeute mehr ist
    (ueber 100 %, Basis ausserhalb 0..1, Faktor unter 1)."""
    try:
        b = float(struktur_basis)
        f = float(char_faktor)
    except (TypeError, ValueError):
        return None
    if not (0.0 < b <= 1.0) or f < 1.0:
        return None
    a = b * f
    return a if a <= 1.0 else None


def scrap_char_faktor(scrapmetal):
    """Faktor des Scrapmetal-Pfads (>= 1.0) oder None bei Muell."""
    s = _stufe(scrapmetal)
    if s is None:
        return None
    return 1.0 + REPRO_SCRAP_JE_STUFE * s


def scrap_ausbeute(char_faktor):
    """Ausbeute 0..1 fuer Items ohne Erz-Skill (Unrefined-Produkte, Module):
    feste 50 % x Charakter-Faktor. Struktur, Rig und Implantat: NICHT
    beteiligt.

    DAS IMPLANTAT IST JETZT GEMESSEN (Nutzer 25.09.2026, Vorschau mit
    gestecktem Zainou 'Beancounter' Reprocessing RX-804): Unrefined Titanium
    Chromide liefert weiterhin 164 -> 86 Titanium und 36 -> 19 Titanium
    Chromide - exakt dieselben Zahlen wie ohne Implantat (53,0 %). Mit
    Implantat waeren es 90 und 19 gewesen. Das Implantat sagt es selbst:
    "4% bonus to ore and ice reprocessing yield" - ein Unrefined-Reaktions-
    produkt ist weder Erz noch Eis. Auf dem ERZ-Pfad (Weg B) zaehlt es
    weiterhin, dort ist es richtig angeschlossen. Wer hier ein Implantat
    einrechnen will, rechnet gegen eine Messung."""
    return reprocess_ausbeute(REPRO_SERVICE_BASIS, char_faktor)


def bester_scrap_char(skills_by_char, skill_ids):
    """(character_id, faktor) des Charakters mit der hoechsten Scrapmetal-
    Processing-Stufe - (None, None) ohne Skills oder ohne Skill-ID. Ohne den
    Skill zaehlt Stufe 0 (Faktor 1.0). Gleichstand: kleinere ID."""
    sid = (skill_ids or {}).get("Scrapmetal Processing")
    if not sid:
        return (None, None)
    best = (None, None)
    for cid, sk in (skills_by_char or {}).items():
        try:
            cid_i = int(cid)
        except (TypeError, ValueError):
            continue
        sk = {int(k): v for k, v in (sk or {}).items()} if sk else {}
        if not sk:
            continue
        f = scrap_char_faktor(sk.get(int(sid), 0))
        if f is None:
            continue
        if best[1] is None or f > best[1] or (f == best[1] and cid_i < best[0]):
            best = (cid_i, f)
    return best


def bester_reprocess_char(skills_by_char, implant_by_char, skill_ids, erz_skill_id):
    """(character_id, faktor) des Charakters mit dem hoechsten Skill-x-
    Implantat-Faktor fuer dieses Erz - oder (None, None), wenn niemand Skills
    geladen hat oder die Skill-IDs fehlen. Gleichstand: kleinere ID, damit
    das Ergebnis reproduzierbar ist. Ein Charakter ohne den Erz-Skill zaehlt
    mit Stufe 0, nicht als fehlend - er darf ja reprocessen, nur schlechter.

    skills_by_char: {cid: {skill_id: level}} (bau_char_skills, Schluessel
    duerfen str sein), implant_by_char: {cid: prozent}, skill_ids: Ergebnis
    von reprocess_skill_ids()."""
    rid = (skill_ids or {}).get("Reprocessing")
    eid = (skill_ids or {}).get("Reprocessing Efficiency")
    if not rid or not eid:
        return (None, None)
    best = (None, None)
    for cid, sk in (skills_by_char or {}).items():
        try:
            cid_i = int(cid)
        except (TypeError, ValueError):
            continue
        sk = {int(k): v for k, v in (sk or {}).items()} if sk else {}
        if not sk:
            continue
        imp = (implant_by_char or {}).get(cid_i, (implant_by_char or {}).get(str(cid_i), 0.0))
        f = reprocess_char_faktor(sk.get(int(rid), 0), sk.get(int(eid), 0),
                                  sk.get(int(erz_skill_id), 0) if erz_skill_id else 0,
                                  imp)
        if f is None:
            continue
        if best[1] is None or f > best[1] or (f == best[1] and cid_i < best[0]):
            best = (cid_i, f)
    return best


def _rig_gids_from(names_by_gid) -> set:
    """Die Rig-Gruppen ("Rig Armor", "Rig Shield", ...) - PURE Funktion,
    ohne DB testbar.

    NUTZER-WUNSCH 15.09.2026: "ich moechte auch Rigs finden koennen fuers
    Bauen". Rigs sind im Scanner nie ausgeschlossen gewesen (Kategorie 7 =
    Modul, Meta 1/2 - beides erlaubt), gehen aber zwischen allen anderen
    Modulen unter. Diese Gruppenliste ist die Grundlage fuers Preset.

    ANFANG DES NAMENS, NICHT IRGENDWO DARIN - und das ist kein Geschmack:
    der gemeinsame Helfer `_gids_matching_from` sucht Teilworte, und "rig"
    steckt auch in "F-r-i-g-ate". Mit der Teilwortsuche waeren alle
    Fregatten-Gruppen Rigs geworden. "rig " mit Leerzeichen trifft
    umgekehrt "Rigging" (Gruppe 269, ein Skill) nicht.

    BLAUPAUSEN RAUS: "Rig Blueprint" ist eine eigene Gruppe. Im Scanner
    kaeme sie nie vor (dort stehen Produkte), aber eine Regel, die nur
    zufaellig richtig liegt, ist keine Regel.

    Gemessen an der mitgelieferten SDE: 16 Gruppen, 632 Rigs - 316 T1 und
    316 T2.
    """
    out = set()
    for gid, name in (names_by_gid or {}).items():
        low = (name or "").lower()
        if low.startswith("rig ") and "blueprint" not in low:
            out.add(gid)
    return out


def rig_group_ids() -> set:
    """group_ids der Rig-Gruppen aus der lokalen SDE (Schutzgitter wie bei
    den Schwester-Funktionen: keine Datenbank -> leeres Set, also nichts
    filtern statt alles wegfiltern)."""
    if not os.path.exists(_db_path()):
        return set()
    try:
        with _conn() as c:
            rows = {r["group_id"]: r["name"]
                    for r in c.execute("SELECT group_id, name FROM group_name")}
        return _rig_gids_from(rows)
    except Exception:
        return set()


def _lp_locked_gids_from(names_by_gid) -> set:
    """Namensregel fuer LP-gesperrte EDENCOM-Gruppen - PURE Funktion, damit
    sie ohne Datenbank testbar ist. Kriterium ist der GRUPPENNAME, keine
    gepflegte Item-Liste (Arbeitsregel wie bei den Mond-Materialien):
    "Vorton ..." und "Condenser Pack" sind eigene SDE-Gruppen; ihre T1-BPCs
    gibt es NUR im DED-LP-Store (LP + ISK), und diese Beschaffungskosten
    kennt die Baukosten-Rechnung nicht -> Fantasie-Margen (Nutzer-Fund:
    Medium Vorton Projector II 1058 %, Vorton Tuning System II 7984 %).
    Der Invention-Filter greift hier NICHT: die T2-Vorton-BPCs SIND
    erfindbar (EVE-Uni: "Tech 2 BPC of them are only available from
    invention") - verzerrt ist die LP-only-T1-Grundlage der Invention."""
    return _gids_matching_from(names_by_gid, ("vorton", "condenser pack"))


def _capital_part_gids_from(names_by_gid) -> set:
    """Namensregel fuer Capital-BAU-TEILE (Capital Construction Components,
    Advanced ...) - PURE Funktion, ohne DB testbar. Das sind ZULIEFER-Teile
    fuer Capital-Schiffe, keine verkaufsfertigen Items; in den normalen
    T1/T2-Scans haben sie nichts verloren. Capital-MODULE und -WAFFEN
    ("Capital Shield Extender II" ...) sind dagegen normale Marktware und
    laufen ueber ihre Meta-Gruppe regulaer mit (Nutzer-Entscheidung: das
    fruehere Namens-Praefix "Capital " versteckte BEIDES pauschal)."""
    return _gids_matching_from(names_by_gid,
                               ("capital construction components",))


def capital_part_group_ids() -> set:
    """group_ids der Capital-Bau-Teile aus der lokalen SDE (Schutzgitter
    wie bei lp_locked_group_ids: leere Tabelle -> nichts filtern)."""
    if not os.path.exists(_db_path()):
        return set()
    try:
        with _conn() as c:
            rows = {r["group_id"]: r["name"]
                    for r in c.execute("SELECT group_id, name FROM group_name")}
        return _capital_part_gids_from(rows)
    except Exception:
        return set()


def lp_locked_group_ids() -> set:
    """group_ids der LP-gesperrten EDENCOM-Gruppen aus der lokalen SDE.
    Schutzgitter wie beim published-Filter: leere/alte group_name-Tabelle
    -> leeres Set, es wird dann NICHT gefiltert (alte DBs nicht kastrieren)."""
    if not os.path.exists(_db_path()):
        return set()
    try:
        with _conn() as c:
            rows = {r["group_id"]: r["name"]
                    for r in c.execute("SELECT group_id, name FROM group_name")}
        return _lp_locked_gids_from(rows)
    except Exception:
        return set()


def group_names(type_ids) -> dict:
    """type_id -> group name (e.g. 'Intermediate Materials', 'Composite',
    'Fuel Block', 'Construction Components') for job categorisation."""
    ids = list(type_ids)
    if not os.path.exists(_db_path()) or not ids:
        return {}
    try:
        out = {}
        with _conn() as c:
            for i in range(0, len(ids), 900):
                chunk = ids[i:i + 900]
                q = ("SELECT ic.type_id AS tid, gn.name AS gn FROM item_cat ic "
                     "LEFT JOIN group_name gn ON gn.group_id=ic.group_id "
                     "WHERE ic.type_id IN (%s)" % ",".join("?" * len(chunk)))
                for r in c.execute(q, chunk):
                    out[r["tid"]] = r["gn"] or ""
        return out
    except Exception:
        return {}


def reaction_stage_map(recipes):
    """Ordnet jedem Reaktionsprodukt eine STUFE zu, abgeleitet aus der ECHTEN
    Rezept-Kette (nicht aus Gruppennamen \u2013 die weichen zwischen SDE-Versionen
    und Marktnamen ab). Beantwortet die Frage, die den User beim Planen
    interessiert: "ist das eine fr\u00fche Reaktion (deren Produkt ich nochmal
    verreagiere) oder eine sp\u00e4te (deren Produkt direkt in den Schiffbau geht)?"

    Stufe 1 = Produkt wird SELBST wieder als Material einer ANDEREN Reaktion
              verbraucht (z. B. Titanium Chromide -> geht in weitere Reaktion).
              Das ist die "erste, kleine" Stufe aus rohem Moon-Material.
    Stufe 2 = Produkt geht NUR ins Manufacturing / Endprodukt, nicht mehr in
              eine Reaktion (z. B. Fullerides, Sylramic Fibers).

    recipes: industry.Recipes()-Instanz (nutzt reaction_products + bp_materials).
        Als Parameter \u00fcbergeben, damit die Funktion ohne globalen DB-Zugriff
        testbar ist.
    Returns {type_id: 1|2} nur f\u00fcr Reaktionsprodukte."""
    rp = set(recipes.reaction_products)
    consumed_in_reaction = set()
    for (bp_id, act), mats in recipes.bp_materials.items():
        if act == REACTION:
            for mtid, _q in mats:
                consumed_in_reaction.add(mtid)
    out = {}
    for tid in rp:
        out[tid] = 1 if tid in consumed_in_reaction else 2
    return out


# --- Kategorie-spezifische Rig-Wirkung ------------------------------------
# Aus der SDE-Diagnose: ein Fertigungs-/Reaktions-Rig trägt Effekte der Form
# rig<Domäne>Manufacture<Material|Time>Bonus (bzw. ...Reaction...). Die Domäne im
# Effekt-Namen sagt, auf WELCHE Item-Art der Rig wirkt. Ein Rig kann mehrere
# Domänen abdecken (z. B. „Advanced Component“ → advanced_component UND
# advanced_capital_component). Wir mappen Effekt→Domäne und Item→Domäne(n) und
# lassen den Rig nur greifen, wenn sich die Domänen überschneiden.

# Effekt-Namens-Fragment → Domänen-Tag. Reihenfolge: spezifisch vor allgemein.
# de_scan5: aus  (SDE-Effektnamen von CCP, englisch; "Charge" ist der
# EVE-Begriff fuer Munition, kein deutsches Wort - und kein Anzeigetext)
_RIG_EFFECT_DOMAINS = [
    ("AdvCapComponent", "advanced_capital_component"),
    ("AdvComponent", "advanced_component"),
    ("BasCapComp", "capital_component"),
    ("BasicCapitalComponent", "capital_component"),
    ("CapitalComponent", "capital_component"),
    ("CapComponent", "capital_component"),
    ("Component", "component"),
    ("Equipment", "equipment"),
    ("CapShip", "capital_ship"),
    ("CapitalShip", "capital_ship"),
    ("AdvLargeShip", "advanced_large_ship"),
    ("AdvMediumShip", "advanced_medium_ship"),
    ("AdvSmallShip", "advanced_small_ship"),
    ("AdvShip", "advanced_ship"),
    ("BasicLargeShip", "basic_large_ship"),
    ("BasicMediumShip", "basic_medium_ship"),
    ("BasicSmallShip", "basic_small_ship"),
    ("LargeShip", "basic_large_ship"),
    ("MediumShip", "basic_medium_ship"),
    ("SmallShip", "basic_small_ship"),
    ("Structure", "structure"),
    ("Ammo", "ammo"),
    ("Charge", "ammo"),
    ("Drone", "drone"),
    ("Fighter", "drone"),
    ("Reaction", "reaction"),
    ("Reactor", "reaction"),
]
# de_scan5: an


def rig_domains(effect_names) -> set:
    """Domänen, auf die ein Rig wirkt – aus seinen SDE-Effekt-Namen abgeleitet.
    Nur echte Bonus-Effekte (rig...Material/TimeBonus) zählen."""
    doms = set()
    for eff in (effect_names or []):
        e = eff or ""
        if not e.startswith("rig") or "Bonus" not in e:
            continue
        for frag, dom in _RIG_EFFECT_DOMAINS:
            if frag in e:
                doms.add(dom)
                break
    return doms


# Metagruppen, die „advanced“ (T2/T3) bedeuten
_ADV_META = {2, 14}          # 2=Tech II, 14=Tech III
# Ship-Gruppen-Namensfragmente, die Capital-Schiffe kennzeichnen.
# ACHTUNG: Das ist die HANDELS-Bedeutung von "Capital" (Capital-Tab, Scan,
# Contract-Preise) - dort zaehlen Freighter mit. Fuer die RIG-Zuordnung gilt
# etwas anderes, s. _RIG_CAP_SHIP_HINTS. Zwei verschiedene Fragen, deshalb
# bewusst zwei Listen - NICHT wieder zusammenlegen.
_CAP_SHIP_HINTS = ("Carrier", "Command Carrier", "Dreadnought", "Titan",
                   "Supercarrier", "Force Auxiliary", "Capital Industrial",
                   "Freighter")
# Fuer die RIG-Zuordnung ist ein Freighter KEIN Capital: laut CCP deckt das
# "Basic Large Ship"-Rig Battleships, Freighter und Industrial Command Ships
# ab, das "Advanced Large Ship"-Rig T2-Battleships und Jump Freighter. Ein
# Capital-Ship-Rig wirkt NICHT auf Freighter. (Sitzung 8, gegen die
# CCP-Itembeschreibungen auf everef.net geprueft.)
# "Command Carrier" (Cradle of War, 09.06.2026: Simurgh/Salvation/Gaia/Ymir)
# steht hier AUSDRUECKLICH, obwohl der Teilstring "Carrier" ihn ohnehin
# treffen wuerde. Zufallstreffer sind keine Zuordnung: faellt der Kurzname
# irgendwann weg oder heisst eine Gruppe anders, faellt das Schiff still auf
# "groesse_unbekannt" und bekommt 0 % - genau der Fall, den wir hier jagen.
# aa184 nagelt die vier Command Carrier einzeln fest.
_RIG_CAP_SHIP_HINTS = ("Carrier", "Command Carrier", "Dreadnought", "Titan",
                       "Supercarrier", "Force Auxiliary", "Capital Industrial")

# Schiffsgroesse je SDE-Gruppenname - die Achse, die den Falcon-Fehlbau
# verursacht hat. Vorher trug ein Schiff nur "advanced_ship"/"basic_ship" ohne
# Groesse, konnte sich also mit KEINEM groessenspezifischen Rig
# ("advanced_medium_ship" & Co.) schneiden - kein Nicht-Capital-Schiff bekam je
# einen Rig-Bonus. Quelle: CCPs eigene Rig-Itembeschreibungen.
#   Basic Small  : Fregatten, Zerstoerer, Shuttles
#   Basic Medium : Cruiser, Battlecruiser, Industrials, Mining Barges
#   Basic Large  : Battleships, Freighter, Industrial Command Ships
#   Adv Small    : T2-Fregatten, T2-/T3-Zerstoerer
#   Adv Medium   : T2-Cruiser, T2-Battlecruiser, T2-Hauler, T3-Cruiser,
#                  T3-Subsysteme, Exhumer
#   Adv Large    : T2-Battleships, Jump Freighter
# EXAKTER Gruppenname, kein Teilstring-Vergleich: sonst wuerde "Freighter"
# auch auf "Jump Freighter" passen und die T1/T2-Trennung zerstoeren.
_SHIP_SIZE_GROUPS = {
    "small": {
        "Corvette", "Shuttle", "Frigate", "Assault Frigate", "Interceptor",
        "Covert Ops", "Electronic Attack Ship", "Stealth Bomber",
        "Expedition Frigate", "Logistics Frigate", "Destroyer",
        "Interdictor", "Command Destroyer", "Tactical Destroyer",
    },
    "medium": {
        "Cruiser", "Combat Battlecruiser", "Attack Battlecruiser",
        "Heavy Assault Cruiser", "Heavy Interdiction Cruiser", "Logistics",
        "Force Recon Ship", "Combat Recon Ship", "Strategic Cruiser",
        "Command Ship", "Industrial", "Blockade Runner",
        "Deep Space Transport", "Mining Barge", "Exhumer",
    },
    "large": {
        "Battleship", "Marauder", "Black Ops", "Elite Battleship",
        "Freighter", "Jump Freighter", "Industrial Command Ship",
    },
}


GROESSE_UNBEKANNT = "groesse_unbekannt"


def ship_size(group_name) -> str:
    """'small' | 'medium' | 'large' | GROESSE_UNBEKANNT fuer einen
    Schiffs-Gruppennamen. Unbekannte Gruppen werden MARKIERT statt geraten
    (Arbeitsregel 6) - sie bekommen dann keinen Rig-Bonus, was zu wenig Bonus
    bedeutet und damit zu viel Material. Das ist die sichere Richtung: lieber
    Material uebrig als ein Job, der nicht startet."""
    g = (group_name or "").strip()
    for groesse, namen in _SHIP_SIZE_GROUPS.items():
        if g in namen:
            return groesse
    return GROESSE_UNBEKANNT


def item_domains(category_id, group_name, meta_group_id, is_reaction=False) -> set:
    """Domänen-Tags eines Items – für den Abgleich mit rig_domains().
    Nutzt SDE-Kategorie + Gruppenname + Metagruppe (nichts geraten)."""
    if is_reaction:
        # Reaktionen nach Typ unterscheiden: das Reactor-Efficiency-Rig wirkt laut
        # EVE nur auf COMPOSITE / HYBRID / BIOCHEMICAL – NICHT auf Intermediate.
        # Ohne diese Unterscheidung bekäme eine Intermediate-Reaktion (z.B.
        # Platinum Technite) fälschlich den Rig-Zeitbonus.
        g = (group_name or "").lower()
        tags = {"reaction"}
        if "intermediate" in g:
            tags.add("reaction_intermediate")
        elif "composite" in g:
            tags.add("reaction_composite")
        elif "hybrid" in g:
            tags.add("reaction_hybrid")
        elif "biochem" in g:
            tags.add("reaction_biochem")
        elif "molecular" in g:
            tags.add("reaction_molecular")
        else:
            tags.add("reaction_other")
        return tags
    g = group_name or ""
    adv = meta_group_id in _ADV_META
    # Module / Ladung / Drohnen
    if category_id == 7:
        return {"equipment"}
    if category_id == 8:
        return {"ammo"}
    # DROHNEN UND FIGHTER SIND KEIN "EQUIPMENT" (Nutzer-Beleg, Sitzung 20).
    # Hier stand zusaetzlich "equipment" - dadurch griff ein
    # "Standup L-Set Equipment Manufacturing Efficiency" auch auf Fighter.
    # GEMESSEN am Industriefenster (Ametat I, Azbel "Dockside Innovations" mit
    # genau diesem Rig): das Tooltip "JOB DURATION MODIFIERS" listet NUR
    #   Blueprint Time Efficiency -20 % · Skills and Implants -32 %
    #   Structure Role Bonus -20 %
    # und KEINE Rig-Zeile. Nachgerechnet: 9'000 s x 0.8 x 0.68 x 0.8
    # = 3'917 s = 1:05:17 - exakt die angezeigte JOB DURATION. Das Equipment-
    # Rig wirkt also nicht auf Fighter.
    # RICHTUNG: die falsche Domaene machte Zeit UND Material zu guenstig
    # (-2 % Mat je Rig) - also zu wenig eingekauft, die Richtung, die wehtut.
    # Drohnen (18) laufen ueber dasselbe Rig-Paar "Drone and Fighter";
    # AM QUELLTEXT VERFOLGT, NICHT GEMESSEN - fuer Drohnen fehlt ein
    # Gegenbeleg aus dem Spiel. Die sichere Richtung ist dieselbe.
    if category_id == 18:
        return {"drone"}
    if category_id == 87:
        # Fighter: die SDE-Rig-Effekte fassen Drohnen und Fighter zusammen
        # (s. _RIG_EFFECT_DOMAINS: ("Fighter", "drone")), also dieselbe
        # Domaene wie Drohnen. Nicht geraten - die Zuordnung steht in der
        # Effekt-Tabelle, die aus der SDE kommt.
        return {"drone"}
    # Schiffe (Kategorie 6): Capital vs. Größe × Tier
    if category_id == 6:
        if any(h in g for h in _RIG_CAP_SHIP_HINTS):
            return {"capital_ship"}
        # Tier UND Groesse - der generische Tag bleibt zusaetzlich erhalten,
        # damit ein Rig ohne Groessenangabe weiterhin passt.
        stufe = "advanced" if adv else "basic"
        groesse = ship_size(g)
        allgemein = {"advanced_ship"} if adv else {"basic_ship"}
        if groesse == GROESSE_UNBEKANNT:
            # Markiert statt geraten: schneidet sich mit keinem Rig -> 0 %.
            return allgemein | {f"{stufe}_ship_{GROESSE_UNBEKANNT}"}
        return allgemein | {f"{stufe}_{groesse}_ship"}
    # T3-Subsysteme haengen laut CCP am Advanced-MEDIUM-Ship-Rig, nicht am
    # Komponenten-Rig. Ueberraschend, aber so steht es in der Itembeschreibung.
    if category_id == 32:
        return {"advanced_medium_ship", "advanced_ship"}
    # Strukturen / Strukturkomponenten
    if "Structure" in g:
        return {"structure"}
    # Komponenten nach Gruppenname (deckt den Endprodukt-Baum ab)
    if "Advanced Capital" in g:
        return {"advanced_capital_component"}
    if "Capital Construction" in g or "Capital Component" in g:
        return {"capital_component"}
    if "Construction Component" in g:
        return {"advanced_component"}
    if "Component" in g:
        return {"component"}
    return set()


def group_name_map() -> dict:
    """group_id -> Gruppenname (Englisch, aus der SDE)."""
    if not os.path.exists(_db_path()):
        return {}
    try:
        with _conn() as c:
            return {r["group_id"]: r["name"]
                    for r in c.execute("SELECT group_id, name FROM group_name")}
    except Exception:
        return {}


def capital_ship_products(recipes: "Recipes") -> list:
    """(product_id, blueprint_id, group_name) für alle Capital-Schiffe (Carrier,
    Dreadnought, Titan, Supercarrier, Force Auxiliary, Capital Industrial Ship,
    Freighter/Jump Freighter), die laut SDE tatsächlich eine Blaupause haben.
    Nutzt dieselbe _CAP_SHIP_HINTS-Erkennung wie item_domains() (Rig-Bonus-
    Zuordnung) - eine Quelle für "ist das ein Capital", nicht zwei getrennte
    Definitionen, die auseinanderlaufen könnten."""
    catmap = item_category_map()
    gnames = group_name_map()
    out = []
    for product_id, (bp_id, activity, _oq) in recipes.product_to_bp.items():
        if activity not in (MANUFACTURING, REACTION):
            continue
        info = catmap.get(product_id)
        if not info:
            continue
        cat_id, group_id, _meta = info
        if cat_id != 6:          # nur Kategorie "Ship"
            continue
        gname = gnames.get(group_id) or ""
        if any(h in gname for h in _CAP_SHIP_HINTS):
            out.append((product_id, bp_id, gname))
    return out


def category_options() -> list:
    """List of (category_id, name) for the categories actually present, sorted."""
    if not os.path.exists(_db_path()):
        return []
    try:
        with _conn() as c:
            return [(r["category_id"], r["name"]) for r in c.execute(
                "SELECT DISTINCT ic.category_id, cn.name FROM item_cat ic "
                "LEFT JOIN cat_name cn ON cn.category_id=ic.category_id "
                "WHERE cn.name IS NOT NULL ORDER BY cn.name")]
    except Exception:
        return []


def buildable_category_options() -> list:
    """Wie category_options(), aber NUR Kategorien, die mindestens ein Item
    enthalten, das laut SDE tatsächlich über eine Blaupause (Fertigung ODER
    Reaktion) hergestellt wird - für Dropdowns rund um „Meine Blueprints“, wo
    z.B. Kleidung/Antike Relikte/SKINs/Blaupausen-von-Blaupausen (die es nicht
    gibt) nur unnötig Rauschen wären."""
    if not os.path.exists(_db_path()):
        return []
    try:
        with _conn() as c:
            placeholders = ",".join("?" * len(ACTIVITIES))
            return [(r["category_id"], r["name"]) for r in c.execute(
                "SELECT DISTINCT ic.category_id, cn.name FROM item_cat ic "
                "JOIN products p ON p.product_id = ic.type_id "
                "LEFT JOIN cat_name cn ON cn.category_id=ic.category_id "
                f"WHERE cn.name IS NOT NULL AND p.activity_id IN ({placeholders}) "
                "ORDER BY cn.name", ACTIVITIES)]
    except Exception:
        return []


def group_options(category_id=None) -> list:
    """List of (group_id, name) for groups actually present, optionally
    beschränkt auf eine Kategorie - für einen "Kategorie -> Gruppe"-Filter
    (z.B. Ship -> Frigate), damit man z.B. exakt "T1 -> Schiffe -> Fregatten"
    filtern kann statt nur die grobe Kategorie "Schiffe"."""
    if not os.path.exists(_db_path()):
        return []
    try:
        with _conn() as c:
            if category_id is not None:
                rows = c.execute(
                    "SELECT DISTINCT ic.group_id, gn.name FROM item_cat ic "
                    "LEFT JOIN group_name gn ON gn.group_id=ic.group_id "
                    "WHERE gn.name IS NOT NULL AND ic.category_id=? ORDER BY gn.name",
                    (category_id,)).fetchall()
            else:
                rows = c.execute(
                    "SELECT DISTINCT ic.group_id, gn.name FROM item_cat ic "
                    "LEFT JOIN group_name gn ON gn.group_id=ic.group_id "
                    "WHERE gn.name IS NOT NULL ORDER BY gn.name").fetchall()
            return [(r["group_id"], r["name"]) for r in rows]
    except Exception:
        return []


def buildable_group_options(category_id=None) -> list:
    """Wie group_options(), aber NUR Gruppen mit mindestens einem tatsächlich
    baubaren Produkt (siehe buildable_category_options())."""
    if not os.path.exists(_db_path()):
        return []
    try:
        with _conn() as c:
            placeholders = ",".join("?" * len(ACTIVITIES))
            params = list(ACTIVITIES)
            cat_clause = ""
            if category_id is not None:
                cat_clause = "AND ic.category_id=? "
                params.append(category_id)
            rows = c.execute(
                "SELECT DISTINCT ic.group_id, gn.name FROM item_cat ic "
                "JOIN products p ON p.product_id = ic.type_id "
                "LEFT JOIN group_name gn ON gn.group_id=ic.group_id "
                f"WHERE gn.name IS NOT NULL AND p.activity_id IN ({placeholders}) "
                f"{cat_clause}ORDER BY gn.name", params).fetchall()
            return [(r["group_id"], r["name"]) for r in rows]
    except Exception:
        return []


def sde_ready() -> bool:
    if not os.path.exists(_db_path()):
        return False
    try:
        with _conn() as c:
            n = c.execute("SELECT COUNT(*) AS n FROM products").fetchone()
        return n and n["n"] > 0
    except Exception:
        return False


def times_ready() -> bool:
    """True if the build-time table (industryActivity) is populated."""
    if not os.path.exists(_db_path()):
        return False
    try:
        with _conn() as c:
            n = c.execute("SELECT COUNT(*) AS n FROM activities").fetchone()
        return bool(n and n["n"] > 0)
    except Exception:
        return False


_BASE = "https://www.fuzzwork.co.uk/dump/latest/"
_TABLES = {
    "materials": "industryActivityMaterials",
    "products": "industryActivityProducts",
    "probabilities": "industryActivityProbabilities",
}


_SQLITE_URL = "https://www.fuzzwork.co.uk/dump/latest-sqlite.db.gz"


# de_scan4: aus - ENTWICKLER-DIAGNOSEN (Sitzung 17): die _write_*_diagnostic-
# Funktionen schreiben nur Textdateien zum Nachsehen, nie in die Oberflaeche.
def _write_max_runs_diagnostic(src, act_has_max_runs):
    """DIAGNOSE (rein lesend): schreibt app_data_dir/max_runs_diagnose.txt.
    Zweck: der Blueprints-Tab zeigte 'MAX RUNS/JOB' überall als '-' (0), was
    'Empf. Kopien' immer auf 1 zwingt, egal wie viele Runs gebraucht werden.
    Diese Diagnose zeigt die ROHEN maxProductionLimit-Werte für ein paar
    bekannte Items (Komponente + Reaktion + Endprodukt), damit klar wird, ob
    a) die Spalte gar nicht gelesen wurde (act_has_max_runs=False) oder
    b) sie gelesen wurde, aber echte 0-Werte liefert (= laut SDE kein Limit
       für diese Items, meine Annahme war dann falsch)."""
    import os as _os

    def q(sql, params=()):
        try:
            return src.execute(sql, params).fetchall()
        except Exception:
            return None

    L = [f"MOTOR MARKET — MAX-RUNS-DIAGNOSE (maxProductionLimit)",
        f"act_has_max_runs (Spalte gefunden?): {act_has_max_runs}",
        "=" * 70]
    sample_names = ["Nanoelectrical Microprocessor", "Antimatter Reactor Unit",
                    "Retribution", "Tesseract Capacitor Unit", "Punisher"]
    for nm in sample_names:
        row = q("SELECT typeID FROM invTypes WHERE typeName=?", (nm,))
        if not row:
            L.append(f"\n[{nm}]  NICHT in invTypes gefunden")
            continue
        tid = row[0][0]
        act = q("SELECT activityID, typeID, maxProductionLimit, time "
                "FROM industryActivity WHERE typeID=?", (tid,))
        L.append(f"\n[{nm}  (typeID {tid})]")
        if act:
            for a in act:
                L.append(f"    activityID={a[0]} maxProductionLimit={a[2]} time={a[3]}")
        else:
            L.append("    KEIN industryActivity-Eintrag (evtl. kein Blueprint-Rezept)")
    path = _os.path.join(config.app_data_dir(), "max_runs_diagnose.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


def _write_decryptor_diagnostic(dec_records):
    """DIAGNOSE (rein lesend): schreibt app_data_dir/decryptor_diagnose.txt.
    Dump der aus der SDE extrahierten Decryptor-Werte (prob_mult, me_mod,
    te_mod, run_mod je type_id), um sie gegen die Ingame-Tooltips zu
    verifizieren (Quelle der Wahrheit: Rechtsklick -> Info auf den Decryptor)."""
    import os as _os
    L = ["MOTOR MARKET — DECRYPTOR-DIAGNOSE (aus SDE extrahiert)",
        "Format: Name (typeID): prob_mult=X me_mod=X te_mod=X run_mod=X",
        "Vergleich mit Ingame-Tooltip: prob_mult 1.20 = '+20%', 0.60 = '-40%' usw.",
        "=" * 70]
    for tid, name, prob, me, te, runs in sorted(dec_records, key=lambda r: r[1]):
        L.append(f"{name} ({tid}): prob_mult={prob} me_mod={me} te_mod={te} "
                 f"run_mod={runs}")
    path = _os.path.join(config.app_data_dir(), "decryptor_diagnose.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


def _write_struct_role_diagnostic(src):
    """DIAGNOSE (rein lesend): schreibt app_data_dir/struct_role_diagnose.txt.
    Zweck: pr\u00fcfen, WIE die SDE die Struktur-Rollen-Zeitboni (Raitaru -15%,
    Azbel -20%, Sotiyo -30% Fertigung; Tatara -25% Reaktion; Athanor 0%)
    dokumentiert. Type-IDs werden per NAME aus invTypes gesucht (nicht
    hartkodiert), damit auch das aus der SDE kommt. Bricht den SDE-Load nie ab."""
    import os as _os

    def q(sql, params=()):
        try:
            return src.execute(sql, params).fetchall()
        except Exception:
            return None

    names = ["Raitaru", "Azbel", "Sotiyo", "Athanor", "Tatara"]
    L = []
    L.append("MOTOR MARKET — STRUKTUR-ROLLEN-BONI-DIAGNOSE (Job-Zeit-Prozentsätze)")
    L.append("Zweck: herausfinden, ob/wie die SDE die Struktur-Zeitboni "
             "(Raitaru -15%, Azbel -20%, Sotiyo -30% Fertigung; Tatara -25% "
             "Reaktion) selbst dokumentiert. Type-IDs per Name aus invTypes.")
    L.append("=" * 70)

    for nm in names:
        row = q("SELECT typeID FROM invTypes WHERE typeName=?", (nm,))
        if not row:
            L.append(f"\n[{nm}]  NICHT in invTypes gefunden (Name-Mismatch?)")
            continue
        tid = row[0][0]
        L.append(f"\n[{nm}  (typeID {tid})]")
        desc = q("SELECT description FROM invTypes WHERE typeID=?", (tid,))
        if desc and desc[0][0]:
            L.append("  invTypes.description:")
            for line in str(desc[0][0]).splitlines():
                L.append(f"    {line}")
        eff = q("SELECT te.effectID, e.effectName FROM dgmTypeEffects te "
                "JOIN dgmEffects e ON e.effectID=te.effectID WHERE te.typeID=?",
                (tid,))
        if eff:
            L.append("  dgmTypeEffects:")
            for e in eff:
                L.append(f"    effectID={e[0]}  {e[1]}")
        at = q("SELECT ta.attributeID, at.attributeName, ta.valueInt, ta.valueFloat "
               "FROM dgmTypeAttributes ta "
               "LEFT JOIN dgmAttributeTypes at ON at.attributeID=ta.attributeID "
               "WHERE ta.typeID=?", (tid,))
        if at:
            L.append("  dgmTypeAttributes:")
            for a in at:
                val = a[2] if a[2] is not None else a[3]
                L.append(f"    attr {a[0]:>5} {str(a[1] or '?'):<40} = {val}")
        else:
            L.append("  dgmTypeAttributes: (keine)")

    L.append("\n[Breite Suche] Attribute mit 'Structure'/'Role'/'Job' im Namen, "
             "die auf einen Zeitbonus hindeuten könnten:")
    wide = q("SELECT attributeID, attributeName FROM dgmAttributeTypes "
             "WHERE (attributeName LIKE '%Structure%' OR attributeName LIKE '%Role%') "
             "AND (attributeName LIKE '%Time%' OR attributeName LIKE '%Job%' "
             "OR attributeName LIKE '%Bonus%')")
    for r in sorted(wide or [], key=lambda x: x[1] or ""):
        L.append(f"    attr {r[0]:>5}  {r[1]}")

    L.append("\n[Breite Suche 2] Attribute mit 'Manufactur'/'Research'/'Industry' "
             "im Namen (unabhängig von 'Structure'/'Role'):")
    wide2 = q("SELECT attributeID, attributeName FROM dgmAttributeTypes "
              "WHERE attributeName LIKE '%Manufactur%' "
              "OR attributeName LIKE '%esearch%' "
              "OR (attributeName LIKE '%ndustry%' AND attributeName LIKE '%ime%')")
    for r in sorted(wide2 or [], key=lambda x: x[1] or ""):
        L.append(f"    attr {r[0]:>5}  {r[1]}")

    L.append("\n[attr 2562 attributeStructureManufactureTimeMultiplier] "
             "Welche Typen haben dieses Attribut gesetzt? (erste 30, um zu sehen "
             "ob es Rigs, Skills, oder doch Strukturen sind):")
    owners = q("SELECT ta.typeID, t.typeName, ta.valueInt, ta.valueFloat "
              "FROM dgmTypeAttributes ta LEFT JOIN invTypes t ON t.typeID=ta.typeID "
              "WHERE ta.attributeID=2562 LIMIT 30")
    for o in (owners or []):
        val = o[2] if o[2] is not None else o[3]
        L.append(f"    typeID={o[0]:>6}  {str(o[1] or '?'):<45} = {val}")
    if not owners:
        L.append("    (kein Typ in der SDE hat attr 2562 gesetzt)")

    path = _os.path.join(config.app_data_dir(), "struct_role_diagnose.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


def _write_implant_diagnostic(src):
    """DIAGNOSE (rein lesend): schreibt app_data_dir/implant_diagnose.txt.
    Zweck: das Tool berücksichtigt bisher KEINE Implantate für die Fertigungs-
    /Reaktionszeit (nur Skills). Diese Diagnose sucht alle Implantat-Typen mit
    'Beancounter' im Namen (die bekannte Fertigungszeit-Serie, z.B. BX-804)
    UND generell alles mit 'Industry'/'Reaction' im Namen unter den Implant-
    Market-Gruppen, dumpt deren dgmTypeAttributes, damit klar wird, WELCHES
    Attribut den %-Bonus trägt (Vermutung: dasselbe 'manufacturingTimeBonus'
    wie beim Industry-Skill - aber NICHT geraten, sondern hier verifiziert)."""
    import os as _os

    def q(sql, params=()):
        try:
            return src.execute(sql, params).fetchall()
        except Exception:
            return None

    L = ["MOTOR MARKET — IMPLANTAT-DIAGNOSE (Fertigungs-/Reaktionszeit-Boni)",
        "Zweck: welche Implantate geben Zeit-Boni, und über welches SDE-"
        "Attribut? Bisher hartkodiert NICHTS berücksichtigt.",
        "=" * 70]
    rows = q("SELECT typeID, typeName FROM invTypes WHERE typeName LIKE "
            "'%Beancounter%' ORDER BY typeName")
    if not rows:
        L.append("\nKEINE 'Beancounter'-Implantate in invTypes gefunden.")
    for tid, nm in (rows or []):
        L.append(f"\n[{nm}  (typeID {tid})]")
        desc = q("SELECT description FROM invTypes WHERE typeID=?", (tid,))
        if desc and desc[0][0]:
            L.append("  invTypes.description:")
            for line in str(desc[0][0]).splitlines():
                L.append(f"    {line}")
        at = q("SELECT ta.attributeID, at.attributeName, ta.valueInt, ta.valueFloat "
               "FROM dgmTypeAttributes ta "
               "LEFT JOIN dgmAttributeTypes at ON at.attributeID=ta.attributeID "
               "WHERE ta.typeID=?", (tid,))
        if at:
            L.append("  dgmTypeAttributes:")
            for a in at:
                val = a[2] if a[2] is not None else a[3]
                L.append(f"    attr {a[0]:>5} {str(a[1] or '?'):<40} = {val}")
        else:
            L.append("  dgmTypeAttributes: (keine)")
    path = _os.path.join(config.app_data_dir(), "implant_diagnose.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


def _write_reprocess_diagnostic(src):
    """DIAGNOSE (rein lesend): schreibt app_data_dir/reprocess_diagnose.txt.
    Zweck (1.0.9): BEVOR eine Ausbeuteformel in den Bauplan kommt, muss
    sichtbar sein, was die SDE ueber Reprocessing weiss - Attributnamen,
    die Skills der Gruppe "Reprocessing", die Beancounter-Reprocessing-
    Implantate, und die Attribute von Veldspar / Compressed Veldspar /
    Unrefined Hexite / Athanor / Tatara / Reprocessing-Rigs. Nichts wird
    interpretiert, nur gezeigt. Bricht den SDE-Load nie ab."""
    import os as _os

    def q(sql, params=()):
        try:
            return src.execute(sql, params).fetchall()
        except Exception:
            return None

    def attrs(tid):
        at = q("SELECT ta.attributeID, at.attributeName, ta.valueInt, ta.valueFloat "
               "FROM dgmTypeAttributes ta "
               "LEFT JOIN dgmAttributeTypes at ON at.attributeID=ta.attributeID "
               "WHERE ta.typeID=? ORDER BY ta.attributeID", (tid,))
        if not at:
            return ["    dgmTypeAttributes: (keine)"]
        return [f"    attr {a[0]:>5} {str(a[1] or '?'):<44} = "
                f"{a[2] if a[2] is not None else a[3]}" for a in at]

    def block(title, rows):
        L.append("")
        L.append(f"== {title} ==")
        if not rows:
            L.append("  (nichts gefunden)")
            return
        for tid, nm in rows:
            L.append(f"  [{nm}  (typeID {tid})]")
            L.extend(attrs(tid))

    L = ["MOTOR MARKET - REPROCESSING-DIAGNOSE (1.0.9)",
         "Zweck: was die SDE ueber Reprocessing-Ausbeute weiss. Nur gezeigt, "
         "nicht interpretiert.",
         "=" * 70, "",
         "== Attributnamen mit 'reproc' oder 'refin' =="]
    names = q("SELECT attributeID, attributeName FROM dgmAttributeTypes "
              "WHERE LOWER(attributeName) LIKE '%reproc%' "
              "OR LOWER(attributeName) LIKE '%refin%' ORDER BY attributeID")
    for aid, an in (names or []):
        L.append(f"  {aid:>5}  {an}")
    if not names:
        L.append("  (keine)")
    grp = q("SELECT groupID FROM invTypes WHERE typeName='Reprocessing'")
    block("Skills in der Gruppe von 'Reprocessing'",
          q("SELECT typeID, typeName FROM invTypes WHERE groupID=? ORDER BY typeName",
            (grp[0][0],)) if grp else [])
    block("Implantate 'Beancounter Reprocessing'",
          q("SELECT typeID, typeName FROM invTypes "
            "WHERE typeName LIKE '%Beancounter%Reprocessing%' ORDER BY typeName"))
    block("Erze / Unrefined (Beispiele)",
          q("SELECT typeID, typeName FROM invTypes WHERE typeName IN "
            "('Veldspar','Compressed Veldspar','Unrefined Hexite','Hexite') "
            "ORDER BY typeName"))
    block("Refineries", q("SELECT typeID, typeName FROM invTypes "
                          "WHERE typeName IN ('Athanor','Tatara') ORDER BY typeName"))
    block("Reprocessing-Rigs (Standup)",
          q("SELECT typeID, typeName FROM invTypes "
            "WHERE typeName LIKE 'Standup%Reprocessing%' ORDER BY typeName"))
    path = _os.path.join(config.app_data_dir(), "reprocess_diagnose.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path


def _write_skill_diagnostic(src):
    """DIAGNOSE (rein lesend): schreibt app_data_dir/skill_diagnose.txt.
    Zweck: prüfen, WIE/OB die SDE die Job-Zeit-Prozentsätze der Skills Industry
    (3380, hartkodiert -4%/Stufe), Advanced Industry (3388, hartkodiert -3%/Stufe)
    und Reactions (45746, hartkodiert -4%/Stufe) selbst dokumentiert – entweder
    als Dogma-Attribut/-Effekt ODER (wahrscheinlicher, da alter Kern-Mechanismus
    von vor dem generischen Skill-Bonus-System) im Klartext der invTypes.description.
    Bricht den SDE-Load nie ab."""
    import os as _os

    def q(sql, params=()):
        try:
            return src.execute(sql, params).fetchall()
        except Exception:
            return None

    skill_ids = {3380: "Industry", 3388: "Advanced Industry", 45746: "Reactions"}

    L = []
    L.append("MOTOR MARKET — SKILL-DIAGNOSE (Job-Zeit-Prozentsätze)")
    L.append("Zweck: herausfinden, ob/wie die SDE die -4%/-3%/-4%-pro-Stufe-Werte")
    L.append("von Industry/Advanced Industry/Reactions selbst dokumentiert.")
    L.append("=" * 70)

    for sid, sname in skill_ids.items():
        L.append(f"\n[{sname}  (typeID {sid})]")
        # 1) Klartext-Beschreibung (invTypes.description) - oft die Quelle für
        #    solche alten, nicht-generischen Skill-Boni.
        desc = q("SELECT description FROM invTypes WHERE typeID=?", (sid,))
        if desc and desc[0][0]:
            L.append("  invTypes.description:")
            for line in str(desc[0][0]).splitlines():
                L.append(f"    {line}")
        else:
            L.append("  invTypes.description: (leer / nicht gefunden)")
        # 2) Dogma-Effekte des Skills
        eff = q("SELECT te.effectID, e.effectName FROM dgmTypeEffects te "
                "JOIN dgmEffects e ON e.effectID=te.effectID WHERE te.typeID=?",
                (sid,))
        if eff:
            L.append("  dgmTypeEffects:")
            for e in eff:
                L.append(f"    effectID={e[0]}  {e[1]}")
        else:
            L.append("  dgmTypeEffects: (keine)")
        # 3) Dogma-Attribute des Skills (Wert könnte der %-Satz selbst sein)
        at = q("SELECT ta.attributeID, at.attributeName, ta.valueInt, ta.valueFloat "
               "FROM dgmTypeAttributes ta "
               "LEFT JOIN dgmAttributeTypes at ON at.attributeID=ta.attributeID "
               "WHERE ta.typeID=?", (sid,))
        if at:
            L.append("  dgmTypeAttributes:")
            for a in at:
                val = a[2] if a[2] is not None else a[3]
                L.append(f"    attr {a[0]:>5} {str(a[1] or '?'):<38} = {val}")
        else:
            L.append("  dgmTypeAttributes: (keine)")

    # 4) Breite Suche: alle Dogma-Attribut-NAMEN, die auf einen generischen
    #    Job-Zeit-Bonus-Mechanismus hindeuten könnten (falls Punkt 1-3 oben leer
    #    sind, damit wir wissen, wonach wir stattdessen suchen müssten).
    L.append("\n[Breite Suche] Attribute mit 'Job' oder 'Industry' oder 'Time' im "
             "Namen (evtl. Kandidat für einen generischen Mechanismus):")
    wide = q("SELECT attributeID, attributeName FROM dgmAttributeTypes "
             "WHERE attributeName LIKE '%Job%' OR attributeName LIKE '%Industry%' "
             "OR (attributeName LIKE '%Time%' AND attributeName LIKE '%Bonus%')")
    for r in sorted(wide or [], key=lambda x: x[1] or ""):
        L.append(f"    attr {r[0]:>5}  {r[1]}")

    path = _os.path.join(config.app_data_dir(), "skill_diagnose.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


def _write_rig_diagnostic(src, rig_rows, time_attr_ids=None, mat_attr_ids=None,
                          cost_attr_ids=None):
    """DIAGNOSE (rein lesend): schreibt app_data_dir/rig_diagnose.txt und zeigt,
    WIE die SDE die betroffenen Item-Gruppen eines Struktur-Rigs speichert.
    Grundlage für die kategorie-spezifische Rig-Wirkung. Bricht den SDE-Load nie ab.
    """
    import os as _os

    def q(sql, params=()):
        try:
            return src.execute(sql, params).fetchall()
        except Exception:
            return None

    def names_for(ids, table, id_col, name_col):
        out = {}
        if not ids:
            return out
        rows = q(f"SELECT {id_col},{name_col} FROM {table} "
                 f"WHERE {id_col} IN ({','.join('?' * len(ids))})", tuple(ids)) or []
        for r in rows:
            out[int(r[0])] = r[1]
        return out

    L = []
    L.append("MOTOR MARKET — RIG-DIAGNOSE (Rig -> betroffene Item-Gruppen)")
    L.append("Zweck: herausfinden, wie CCP/SDE speichert, worauf ein Rig wirkt.")
    L.append("=" * 70)

    # 0) ALLE rohen "Standup..."-Namen aus der SDE, unverändert – für die Suche nach
    # Dubletten/fehlenden Rigs (z. B. Tatara: Reactor Efficiency, Reprocessing Monitor).
    L.append("\n[0] ALLE rohen Standup-Items aus der SDE (typeID, Name) – ungefiltert:")
    for r in sorted((rig_rows or []), key=lambda x: (x[1] or "")):
        L.append(f"    #{r[0]}  {r[1]!r}")

    # 0b) Welche Attribut-IDs wurden für Zeit-/Material-/Kosten-Bonus über den
    # Attributnamen gefunden (dynamisch, s. download_sde)? Falls hier nur der
    # Fallback (2593/2594/2595) drinsteht, hat die Namenssuche NICHTS gefunden –
    # dann liegt der Rig-Bonus vermutlich auf ganz anderen IDs oder einem ganz
    # anderen Mechanismus (z.B. industryModifierSources statt dgmTypeAttributes).
    L.append("\n[0b] Für Rig-Boni verwendete Attribut-IDs (per Namenssuche gefunden):")
    L.append(f"    Zeit-Bonus-IDs:     {sorted(time_attr_ids or [2593])}")
    L.append(f"    Material-Bonus-IDs: {sorted(mat_attr_ids or [2594])}")
    L.append(f"    Kosten-Bonus-IDs:   {sorted(cost_attr_ids or [2595])}")
    attr_name_hits = q(
        "SELECT attributeID, attributeName FROM dgmAttributeTypes "
        "WHERE attributeName LIKE '%Rig%Bonus%'") or []
    L.append("    ALLE Attribute in der SDE, deren Name '...Rig...Bonus...' enthält:")
    for r in sorted(attr_name_hits, key=lambda x: x[1] or ""):
        L.append(f"      attr {r[0]:>5}  {r[1]}")

    # 1) Welche relevanten Tabellen gibt es ueberhaupt im Dump?
    tabs = q("SELECT name FROM sqlite_master WHERE type='table'") or []
    tnames = sorted(t[0] for t in tabs)
    rel = [t for t in tnames if any(k in t.lower() for k in
           ("industr", "modifier", "buff", "filter", "effect", "dgm"))]
    L.append("\n[1] Relevante Tabellen im SDE-Dump:")
    for t in rel:
        L.append(f"    - {t}")

    # 2) Zielrigs = genau die Kategorien aus deinem Setup + die beiden Tatara-Rigs
    # (Reactor Efficiency / Reprocessing Monitor müssen IMMER dabei sein, nicht nur
    # lose per "Reactor"-Teilstring – sonst gewinnt z.B. "Reactor Control Unit"
    # [ein irrelevantes altes POS-Modul] den Platz und die echten Rigs fehlen).
    want_tokens = ["Advanced Component", "Equipment", "Capital Ship",
                   "Basic Capital Component", "Structure"]
    must_have = ["Reactor Efficiency", "Reprocessing Monitor"]
    targets = []
    for r in (rig_rows or []):
        nm = r[1] or ""
        if any(tok in nm for tok in must_have):
            targets.append((int(r[0]), nm))     # IMMER dabei, keine Dedup-Auswahl
    for r in (rig_rows or []):
        nm = r[1] or ""
        if "Manufacturing Efficiency" in nm and any(tok in nm for tok in want_tokens):
            targets.append((int(r[0]), nm))
    # pro Kategorie-Token nur EIN Rig (das erste), damit der Report kurz bleibt –
    # gilt NICHT für must_have (die kommen immer alle rein).
    seen = set(); picked = []
    for tid, nm in targets:
        if any(tok in nm for tok in must_have):
            picked.append((tid, nm))
            continue
        tok = next((t for t in want_tokens if t in nm), nm)
        if tok in seen:
            continue
        seen.add(tok); picked.append((tid, nm))
    if not picked:                                   # Fallback: irgendein Mfg-Rig
        picked = [(int(r[0]), r[1]) for r in (rig_rows or [])
                  if "Manufacturing Efficiency" in (r[1] or "")][:5]

    # Attribut-Namen einmalig laden
    L.append("\n[2] Ziel-Rigs (aus deinem Setup):")
    for tid, nm in picked:
        L.append(f"    #{tid}  {nm}")

    for tid, nm in picked:
        L.append("\n" + "-" * 70)
        L.append(f"RIG #{tid}  {nm}")

        # 2a) industryModifierSources / aehnliche Tabellen (das waere die Gold-Quelle)
        for tbl in ("industryModifierSources", "industryTargetFilters",
                    "industryActivityModifiers", "ramInstallationTypeContents"):
            if tbl not in tnames:
                continue
            cols = q(f"PRAGMA table_info({tbl})") or []
            colnames = [c[1] for c in cols]
            # nach typeID-Spalte filtern, wenn vorhanden
            tcol = next((c for c in colnames if c.lower() in
                         ("typeid", "structuretypeid", "sourcetypeid")), None)
            if tcol:
                rows = q(f"SELECT * FROM {tbl} WHERE {tcol}=?", (tid,)) or []
            else:
                rows = q(f"SELECT * FROM {tbl} LIMIT 3") or []
            if rows:
                L.append(f"  [{tbl}] Spalten: {colnames}")
                for row in rows[:8]:
                    L.append(f"    {tuple(row)}")

        # 2b) Dogma-Effekte des Rigs
        eff = q("SELECT e.effectID, e.effectName FROM dgmTypeEffects te "
                "JOIN dgmEffects e ON e.effectID=te.effectID WHERE te.typeID=?",
                (tid,)) or []
        if eff:
            L.append("  [dgmTypeEffects] Effekte:")
            for e in eff[:12]:
                L.append(f"    effectID={e[0]}  {e[1]}")

        # 2c) Dogma-Attribute des Rigs (Werte koennten Gruppen-/Kategorie-IDs sein)
        at = q("SELECT ta.attributeID, at.attributeName, ta.valueInt, ta.valueFloat "
               "FROM dgmTypeAttributes ta "
               "LEFT JOIN dgmAttributeTypes at ON at.attributeID=ta.attributeID "
               "WHERE ta.typeID=?", (tid,)) or []
        if at:
            L.append("  [dgmTypeAttributes] Attribute:")
            grp_ids = set(); cat_ids = set()
            for a in at:
                val = a[2] if a[2] is not None else a[3]
                L.append(f"    attr {a[0]:>5} {str(a[1] or '?'):<38} = {val}")
                # Werte, die wie Gruppen-/Kategorie-IDs aussehen, spaeter aufloesen
                nm2 = (a[1] or "").lower()
                if "group" in nm2 and a[2]:
                    grp_ids.add(int(a[2]))
                if "categor" in nm2 and a[2]:
                    cat_ids.add(int(a[2]))
            gm = names_for(list(grp_ids), "invGroups", "groupID", "groupName")
            cm = names_for(list(cat_ids), "invCategories", "categoryID", "categoryName")
            for gid, gn in gm.items():
                L.append(f"      -> Gruppe {gid} = {gn}")
            for cid, cn in cm.items():
                L.append(f"      -> Kategorie {cid} = {cn}")

    path = _os.path.join(config.app_data_dir(), "rig_diagnose.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L))
    return path


# de_scan4: an


def download_sde(progress=None):
    """Download the complete Fuzzwork SDE SQLite database and read the recipe
    tables directly. This is robust against the per-table files being renamed or
    removed (which is what broke the old approach). progress(done, total)."""
    import gzip
    import os as _os
    import shutil
    import sqlite3
    import tempfile
    init_db()
    agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
        "MotorMarket/1.0 (+EVE trading tool)",
    ]

    # 1) stream the (large, ~140 MB) gzipped database to a temp file
    tmp_gz = tempfile.NamedTemporaryFile(suffix=".db.gz", delete=False).name
    last_err = None
    ok = False
    for ua in agents:
        try:
            with requests.get(_SQLITE_URL, headers={"User-Agent": ua},
                              stream=True, timeout=600) as r:
                if r.status_code != 200:
                    last_err = f"HTTP {r.status_code}"
                    continue
                total = int(r.headers.get("Content-Length", 0))
                done = 0
                with open(tmp_gz, "wb") as f:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            f.write(chunk)
                            done += len(chunk)
                            # IMMER melden (Sitzung 17, Nutzer: "bleibt bei 0%
                            # und ploppt dann auf 100%"). Nachgestellt: ohne
                            # Content-Length kam KEINE Meldung. total 0 heisst
                            # "Groesse unbekannt" - die Anzeige laeuft dann als
                            # Laufband mit MB-Zahl statt als Prozent.
                            if progress:
                                progress(done // (1 << 20), total // (1 << 20))
                ok = True
                break
        except Exception as e:  # noqa: BLE001
            last_err = f"{type(e).__name__}: {e}"
    if not ok:
        try:
            _os.remove(tmp_gz)
        except Exception:
            pass
        from .sprache import t as _txt   # `t` ist hier lokal belegt
        raise RuntimeError(_txt("Recipe database download failed: {err}").format(
            err=last_err))

    # 2) decompress to a temp .db
    # PHASE "ENTPACKEN + EINLESEN" melden (-1): dauert Sekunden bis Minuten,
    # und ohne Meldung stand der Balken so lange stumm auf 100 %.
    if progress:
        progress(-1, 0)
    tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False).name
    try:
        with gzip.open(tmp_gz, "rb") as fin, open(tmp_db, "wb") as fout:
            shutil.copyfileobj(fin, fout, length=1 << 20)
    finally:
        try:
            _os.remove(tmp_gz)
        except Exception:
            pass

    # 3) read the recipe tables straight out of the SDE database
    try:
        src = sqlite3.connect(tmp_db)
        mat = src.execute(
            "SELECT typeID,activityID,materialTypeID,quantity "
            "FROM industryActivityMaterials").fetchall()
        prod = src.execute(
            "SELECT typeID,activityID,productTypeID,quantity "
            "FROM industryActivityProducts").fetchall()
        try:
            prob = src.execute(
                "SELECT typeID,activityID,productTypeID,probability "
                "FROM industryActivityProbabilities").fetchall()
        except Exception:
            prob = []
        try:
            act = src.execute(
                "SELECT typeID,activityID,time,maxProductionLimit "
                "FROM industryActivity").fetchall()
            _act_has_max_runs = True
        except Exception:
            # Spalte heißt evtl. anders / existiert in dieser SDE-Version nicht ->
            # NICHT raten. Fallback ohne max_runs (wie bisher) + Diagnose, damit
            # wir beim nächsten Mal den echten Spaltennamen sehen.
            try:
                act = src.execute(
                    "SELECT typeID,activityID,time FROM industryActivity").fetchall()
            except Exception:
                act = []
            _act_has_max_runs = False
            try:
                _cols = src.execute("PRAGMA table_info(industryActivity)").fetchall()
                _p = os.path.join(config.app_data_dir(), "industry_activity_columns.txt")
                with open(_p, "w", encoding="utf-8") as _f:
                    # de_scan4: aus - Diagnose-Datei, nicht Oberflaeche
                    _f.write("industryActivity Spalten (maxProductionLimit nicht "
                            "gefunden):\n")
                    for _c in _cols:
                        _f.write(f"  {_c}\n")
                    # de_scan4: an
            except Exception:
                pass
        try:
            _write_max_runs_diagnostic(src, _act_has_max_runs)
        except Exception:
            pass
        # category / group / tech-level metadata for the item-category filter.
        # Prefer invTypes.metaGroupID (authoritative & complete in modern SDE);
        # fall back to invMetaTypes for older dumps.
        types_rows = []
        have_meta_col = False
        for q in (
            "SELECT t.typeID, t.groupID, g.categoryID, t.metaGroupID, t.raceID "
            "FROM invTypes t LEFT JOIN invGroups g ON g.groupID=t.groupID "
            "WHERE t.published=1",
            "SELECT t.typeID, t.groupID, g.categoryID, t.metaGroupID, t.raceID "
            "FROM invTypes t LEFT JOIN invGroups g ON g.groupID=t.groupID",
        ):
            try:
                types_rows = src.execute(q).fetchall()
                have_meta_col = True
                break
            except Exception:
                continue
        if not types_rows:
            for q in (
                "SELECT t.typeID, t.groupID, g.categoryID, t.raceID "
                "FROM invTypes t LEFT JOIN invGroups g ON g.groupID=t.groupID "
                "WHERE t.published=1",
                "SELECT t.typeID, t.groupID, g.categoryID, t.raceID "
                "FROM invTypes t LEFT JOIN invGroups g ON g.groupID=t.groupID",
            ):
                try:
                    types_rows = src.execute(q).fetchall()
                    break
                except Exception:
                    continue
        try:
            cat_rows = src.execute(
                "SELECT categoryID, categoryName FROM invCategories").fetchall()
        except Exception:
            cat_rows = []
        try:
            grp_rows = src.execute(
                "SELECT groupID, groupName FROM invGroups").fetchall()
        except Exception:
            grp_rows = []
        try:
            meta_rows = src.execute(
                "SELECT typeID, metaGroupID FROM invMetaTypes").fetchall()
        except Exception:
            meta_rows = []
        # metaLevel (dogma attribute 633): 0 = base T1, 1-4 = named "Compact/
        # Enduring/Scoped/..." modules that NPCs drop. Lets us target those
        # cheap-buy / pricey-sell named modules even though they're metaGroup 1.
        try:
            metalevel_rows = src.execute(
                "SELECT typeID, valueInt, valueFloat FROM dgmTypeAttributes "
                "WHERE attributeID = 633").fetchall()
        except Exception:
            metalevel_rows = []
        try:
            vol_rows = src.execute("SELECT typeID, volume FROM invTypes").fetchall()
        except Exception:
            vol_rows = []
        # Blueprint-Skill-Anforderungen (industryActivitySkills): pro Blueprint +
        # Aktivität die benötigten Skill-typeIDs. Die zeitrelevanten Science-Skills
        # darunter (Molecular Engineering & Co., je −1 % Fertigungszeit/Level)
        # brauchen wir, um die Job-Zeit exakt wie im Spiel zu berechnen.
        try:
            bp_skill_rows = src.execute(
                "SELECT typeID, activityID, skillID FROM industryActivitySkills"
            ).fetchall()
        except Exception:
            bp_skill_rows = []
        # Welche Skills geben −1 % Fertigungszeit/Level? Das sind genau die 20
        # Wissenschafts-Skills aus der offiziellen EVE-Doku ("Science skills with 1%
        # reduction in manufacturing time per level"). Diese Liste ist eindeutig und
        # stabil – anders als eine Attribut-Namenssuche, die auch den allgemeinen
        # Industry-Skill (−4 %/Level) fälschlich mitnehmen würde. Wir lesen die
        # typeIDs per Name aus der SDE (nichts geraten – die IDs kommen aus den Daten).
        _sci_names = (
            "Advanced Small Ship Construction", "Advanced Medium Ship Construction",
            "Advanced Large Ship Construction", "Advanced Industrial Ship Construction",
            "Amarr Starship Engineering", "Caldari Starship Engineering",
            "Gallente Starship Engineering", "Minmatar Starship Engineering",
            "Electromagnetic Physics", "Electronic Engineering", "Graviton Physics",
            "High Energy Physics", "Hydromagnetic Physics", "Laser Physics",
            "Mechanical Engineering", "Molecular Engineering", "Nuclear Physics",
            "Plasma Physics", "Quantum Physics", "Rocket Science",
        )
        science_skill_ids = set()
        try:
            _q = ("SELECT typeID FROM invTypes WHERE typeName IN (%s)"
                  % ",".join("?" * len(_sci_names)))
            _rows = src.execute(_q, _sci_names).fetchall()
            science_skill_ids = {int(r[0]) for r in _rows}
        except Exception:
            science_skill_ids = set()
        # Encryption-Methods-Skills (racial + Sleeper für T3) - der eine Skill
        # neben den 2 Datacore-Skills, der laut offizieller Formel
        # (SkillModifier = 1 + Encryption/40 + (Datacore1+Datacore2)/30) die
        # Invention-Erfolgschance beeinflusst. Namen aus SDE, nichts geraten.
        _enc_names = ("Amarr Encryption Methods", "Caldari Encryption Methods",
                     "Gallente Encryption Methods", "Minmatar Encryption Methods",
                     "Sleeper Encryption Methods")
        encryption_skill_ids = set()
        try:
            _q = ("SELECT typeID FROM invTypes WHERE typeName IN (%s)"
                  % ",".join("?" * len(_enc_names)))
            _rows = src.execute(_q, _enc_names).fetchall()
            encryption_skill_ids = {int(r[0]) for r in _rows}
        except Exception:
            encryption_skill_ids = set()
        # Invention-Skill-Zuordnung: pro T1-Blueprint (typeID bei
        # activityID=INVENTION) die 1 Encryption- + 2 Datacore-Skills, die
        # laut SDE für die Erfolgschance zählen - direkt aus denselben
        # industryActivitySkills-Zeilen wie oben gefiltert, nur die Invention-
        # Aktivität statt Fertigung.
        invention_skill_rows = []
        for r in bp_skill_rows:
            if int(r[1]) != INVENTION:
                continue
            sid = int(r[2])
            if sid in encryption_skill_ids or sid in science_skill_ids:
                invention_skill_rows.append(
                    (int(r[0]), sid, 1 if sid in encryption_skill_ids else 0))
        # Gepacktes Volumen (v.a. Schiffe/Kapitalmodule): invTypes.volume ist die
        # AS-FIT-Größe (z.B. Vagabond ~15'000 m³), invVolumes.volume die Fracht-
        # Größe (~2'500 m³ für Cruiser). Für Transport/Frachtraum zählt IMMER die
        # gepackte Größe. Manche SDE-Konvertierungen haben die Tabelle nicht oder
        # nur teilweise befüllt -> dann Fallback auf invTypes.volume (s. u.).
        try:
            pkg_vol_rows = src.execute("SELECT typeID, volume FROM invVolumes").fetchall()
        except Exception:
            pkg_vol_rows = []
        # REPROCESSING-AUSGANG (1.0.9, Vorbereitung; Nutzer 17.09.2026:
        # Unrefined-Reaktionen und Compressed Ore statt Minerale). NUR die
        # Typen, um die es geht: Kategorie 25 (Asteroid = Erze, komprimiert
        # und roh) und Kategorie 4 (Material - dort liegen die Unrefined-
        # Minerale, Gruppe "Unrefined Mineral"). Alles andere (Module ->
        # Minerale) waere Ballast. Fehlt die Tabelle in einer SDE-Fassung,
        # bleibt die Liste leer - kein Absturz, kein Raten.
        try:
            repro_rows = src.execute(
                "SELECT m.typeID, m.materialTypeID, m.quantity "
                "FROM invTypeMaterials m JOIN invTypes t ON t.typeID=m.typeID "
                "JOIN invGroups g ON g.groupID=t.groupID "
                "WHERE g.categoryID IN (25, 4)").fetchall()
        except Exception:
            repro_rows = []
        try:
            portion_rows = src.execute(
                "SELECT t.typeID, t.portionSize FROM invTypes t "
                "JOIN invGroups g ON g.groupID=t.groupID "
                "WHERE g.categoryID IN (25, 4)").fetchall()
        except Exception:
            portion_rows = []
        # REPROCESSING-SKILLS, ERZ->SKILL, IMPLANTATE (1.0.9, Vorbereitung 2,
        # 17.09.2026). Nichts davon rechnet schon im Bauplan - es wird nur
        # gesammelt, damit die Ausbeuteformel gegen die Messung im Spiel
        # geprueft werden kann (Regel 1/2). Keine ID ist hier geraten: die
        # Skill-Gruppe kommt ueber den Namen "Reprocessing", das Erz->Skill-
        # Attribut ueber seinen Namen in dgmAttributeTypes, das Implantat-
        # Attribut wird MIT NAMEN gespeichert, damit man spaeter sieht, was
        # es war. Fehlt etwas in einer SDE-Fassung: leer, kein Absturz.
        try:
            _rs_grp = src.execute(
                "SELECT groupID FROM invTypes WHERE typeName='Reprocessing'").fetchone()
            repro_skill_rows = src.execute(
                "SELECT typeID, typeName FROM invTypes WHERE groupID=?",
                (_rs_grp[0],)).fetchall() if _rs_grp else []
        except Exception:
            repro_skill_rows = []
        try:
            _aid = src.execute(
                "SELECT attributeID FROM dgmAttributeTypes "
                "WHERE attributeName='reprocessingSkillType'").fetchone()
            erz_skill_rows = src.execute(
                "SELECT ta.typeID, ta.valueInt, ta.valueFloat FROM dgmTypeAttributes ta "
                "JOIN invTypes t ON t.typeID=ta.typeID "
                "JOIN invGroups g ON g.groupID=t.groupID "
                "WHERE ta.attributeID=? AND g.categoryID IN (25, 4)",
                (_aid[0],)).fetchall() if _aid else []
        except Exception:
            erz_skill_rows = []
        try:
            repro_imp_rows = src.execute(
                "SELECT t.typeID, t.typeName, at.attributeName, ta.valueInt, ta.valueFloat "
                "FROM invTypes t JOIN dgmTypeAttributes ta ON ta.typeID=t.typeID "
                "JOIN dgmAttributeTypes at ON at.attributeID=ta.attributeID "
                "WHERE t.typeName LIKE '%Beancounter%Reprocessing%' "
                "AND (LOWER(at.attributeName) LIKE '%reproc%' "
                "OR LOWER(at.attributeName) LIKE '%refin%')").fetchall()
        except Exception:
            repro_imp_rows = []
        # STRUKTUR-BONUS und RIG-WERTE fuers Reprocessing (18.09.2026, nach der
        # Messung): Athanor/Tatara tragen strRefiningYieldBonus (2.0 / 5.5),
        # die Standup-Reprocessing-Rigs refiningYieldMultiplier (0.51 / 0.53)
        # plus hi/low/nullSecModifier (1.0 / 1.06 / 1.12). Alle IDs ueber den
        # Attributnamen, wie bei den Skills.
        def _attr_id(name):
            try:
                _r = src.execute("SELECT attributeID FROM dgmAttributeTypes "
                                 "WHERE attributeName=?", (name,)).fetchone()
                return int(_r[0]) if _r else None
            except Exception:
                return None
        try:
            _a_bonus = _attr_id("strRefiningYieldBonus")
            repro_struct_rows = src.execute(
                "SELECT t.typeID, t.typeName, ta.valueInt, ta.valueFloat "
                "FROM invTypes t JOIN dgmTypeAttributes ta ON ta.typeID=t.typeID "
                "WHERE ta.attributeID=?", (_a_bonus,)).fetchall() if _a_bonus else []
        except Exception:
            repro_struct_rows = []
        try:
            _a_mult, _a_hi, _a_low, _a_null = (
                _attr_id("refiningYieldMultiplier"), _attr_id("hiSecModifier"),
                _attr_id("lowSecModifier"), _attr_id("nullSecModifier"))
            repro_rig_rows = []
            if _a_mult:
                for _tid, _nm, _vi, _vf in src.execute(
                        "SELECT t.typeID, t.typeName, ta.valueInt, ta.valueFloat "
                        "FROM invTypes t JOIN dgmTypeAttributes ta ON ta.typeID=t.typeID "
                        "WHERE ta.attributeID=?", (_a_mult,)).fetchall():
                    _mods = []
                    for _aid in (_a_hi, _a_low, _a_null):
                        _v = None
                        if _aid:
                            _r = src.execute(
                                "SELECT valueInt, valueFloat FROM dgmTypeAttributes "
                                "WHERE typeID=? AND attributeID=?", (_tid, _aid)).fetchone()
                            if _r:
                                _v = _r[0] if _r[0] is not None else _r[1]
                        _mods.append(_v)
                    repro_rig_rows.append((_tid, _nm, _vi if _vi is not None else _vf,
                                           _mods[0], _mods[1], _mods[2]))
        except Exception:
            repro_rig_rows = []
        try:
            _write_reprocess_diagnostic(src)   # Diagnose: Reprocessing in der SDE
        except Exception:
            pass
        # Struktur-Rigs (Standup) + ihre Boni. Die Attribut-IDs 2593/2594/2595 sind
        # NUR für Fertigungs-Rigs bestätigt (Name "attributeEngRig...Bonus" - "Eng" =
        # Engineering). Reaktions-/Refinery-Rigs könnten andere IDs mit demselben
        # Namensmuster benutzen -> IDs über dgmAttributeTypes.attributeName suchen,
        # statt sie zu erraten. Fallback auf 2593/2594/2595, falls die Namenssuche
        # nichts findet (z. B. sehr alte SDE ohne dgmAttributeTypes-Namen).
        try:
            attr_name_rows = src.execute(
                "SELECT attributeID, attributeName FROM dgmAttributeTypes "
                "WHERE attributeName LIKE '%RigTimeBonus%' "
                "OR attributeName LIKE '%RigMatBonus%' "
                "OR attributeName LIKE '%RigMaterialBonus%' "
                "OR attributeName LIKE '%RigCostBonus%'").fetchall()
        except Exception:
            attr_name_rows = []
        time_attr_ids, mat_attr_ids, cost_attr_ids = set(), set(), set()
        for _aid, _aname in attr_name_rows:
            try:
                _aid = int(_aid)
            except (TypeError, ValueError):
                continue
            _n = (_aname or "").lower()
            if "timebonus" in _n:
                time_attr_ids.add(_aid)
            elif "matbonus" in _n or "materialbonus" in _n:
                mat_attr_ids.add(_aid)
            elif "costbonus" in _n:
                cost_attr_ids.add(_aid)
        if not time_attr_ids:
            time_attr_ids = {2593}
        if not mat_attr_ids:
            mat_attr_ids = {2594}
        if not cost_attr_ids:
            cost_attr_ids = {2595}
        _all_rig_attr_ids = time_attr_ids | mat_attr_ids | cost_attr_ids
        try:
            rig_rows = src.execute(
                "SELECT t.typeID, t.typeName, g.groupName "
                "FROM invTypes t LEFT JOIN invGroups g ON g.groupID=t.groupID "
                "WHERE t.typeName LIKE 'Standup%' AND t.published=1").fetchall()
        except Exception:
            rig_rows = []
        try:
            _ids_str = ",".join(str(i) for i in _all_rig_attr_ids)
            rig_attr_rows = src.execute(
                "SELECT typeID, attributeID, valueFloat, valueInt "
                f"FROM dgmTypeAttributes WHERE attributeID IN ({_ids_str})").fetchall()
        except Exception:
            rig_attr_rows = []
        # Rig-Effekt-Namen (rig<Domäne>Manufacture/Reaction...Bonus) → betroffene
        # Item-Art. Nur für Standup-Rigs, nur echte Bonus-Effekte.
        try:
            rig_eff_rows = src.execute(
                "SELECT te.typeID, e.effectName FROM dgmTypeEffects te "
                "JOIN dgmEffects e ON e.effectID=te.effectID "
                "JOIN invTypes t ON t.typeID=te.typeID "
                "WHERE t.typeName LIKE 'Standup%' AND e.effectName LIKE 'rig%Bonus'"
                ).fetchall()
        except Exception:
            rig_eff_rows = []
        # Decryptors + ihre Boni: 1112=Chance, 1113=ME, 1114=TE, 1124=Runs
        try:
            dec_rows = src.execute(
                "SELECT t.typeID, t.typeName FROM invTypes t "
                "LEFT JOIN invGroups g ON g.groupID=t.groupID "
                "WHERE g.groupName='Generic Decryptor' AND t.published=1").fetchall()
        except Exception:
            dec_rows = []
        try:
            dec_attr_rows = src.execute(
                "SELECT typeID, attributeID, valueFloat, valueInt "
                "FROM dgmTypeAttributes WHERE attributeID IN (1112, 1113, 1114, 1124)").fetchall()
        except Exception:
            dec_attr_rows = []
        try:
            _write_rig_diagnostic(src, rig_rows, time_attr_ids, mat_attr_ids,
                                  cost_attr_ids)   # Diagnose: Rig→Gruppen-Mapping
        except Exception:
            pass
        try:
            _write_skill_diagnostic(src)   # Diagnose: Skill-Zeitboni-Quelle in SDE
        except Exception:
            pass
        try:
            _write_struct_role_diagnostic(src)   # Diagnose: Struktur-Rollen-Boni in SDE
        except Exception:
            pass
        try:
            _write_implant_diagnostic(src)   # Diagnose: Implantat-Zeitboni in SDE
        except Exception:
            pass
        # Fertigungszeit-Implantate (Zainou 'Beancounter' Industry BX-80X) aus der
        # SDE extrahieren. Nutzt dasselbe Attribut (440 manufacturingTimeBonus),
        # das für den Industry-SKILL bereits verifiziert ist - plausibelste Quelle,
        # da CCP denselben Mechanismus für Skill UND Implantat verwendet. Wird
        # zusätzlich per implant_diagnose.txt gegengecheckt, NICHT blind vertraut.
        try:
            _imp_rows = src.execute(
                "SELECT t.typeID, t.typeName, ta.valueFloat, ta.valueInt "
                "FROM invTypes t JOIN dgmTypeAttributes ta ON ta.typeID=t.typeID "
                "WHERE t.typeName LIKE '%Beancounter%Industry%' AND ta.attributeID=440"
            ).fetchall()
            _imp_records = []
            for tid, nm, vf, vi in _imp_rows:
                val = vf if vf is not None else vi
                if val is not None:
                    _imp_records.append((tid, nm, "manufacturing", float(val)))
            if _imp_records:
                with _conn() as _c:
                    _c.execute("DELETE FROM implant_time_bonus")
                    _c.executemany(
                        "INSERT OR REPLACE INTO implant_time_bonus"
                        "(type_id,name,activity,pct) VALUES (?,?,?,?)", _imp_records)
        except Exception:
            pass
        # Skill-Zeitboni SELBST aus der SDE lesen (nicht mehr hartkodiert). Namen
        # per skill_diagnose.txt verifiziert: manufacturingTimeBonus (Industry),
        # advancedIndustrySkillIndustryJobTimeBonus (Advanced Industry),
        # reactionTimeBonus (Reactions). Bei Namensänderung in künftigen SDE-
        # Releases bricht das NICHT den Load (try/except) – nur skill_time_factor()
        # fällt dann auf die zuletzt bekannten Werte zurück (s. dort).
        try:
            _skill_attr_names = {
                3380: "manufacturingTimeBonus",
                3388: "advancedIndustrySkillIndustryJobTimeBonus",
                45746: "reactionTimeBonus",
            }
            _skill_pct = {}
            for _sid, _aname in _skill_attr_names.items():
                _row = src.execute(
                    "SELECT ta.valueFloat, ta.valueInt FROM dgmTypeAttributes ta "
                    "JOIN dgmAttributeTypes at ON at.attributeID=ta.attributeID "
                    "WHERE ta.typeID=? AND at.attributeName=?",
                    (_sid, _aname)).fetchone()
                if _row is not None:
                    _v = _row[0] if _row[0] is not None else _row[1]
                    if _v is not None:
                        _skill_pct[_sid] = float(_v)
            if _skill_pct:
                with _conn() as _c:
                    _c.execute(
                        "INSERT OR REPLACE INTO meta(k,v) VALUES('skill_time_bonus_pct', ?)",
                        (json.dumps(_skill_pct),))
        except Exception:
            pass
        src.close()
    finally:
        try:
            _os.remove(tmp_db)
        except Exception:
            pass

    def clean_int(rows, n):
        out = []
        for r in rows:
            try:
                out.append(tuple(int(r[i]) for i in range(n)))
            except (TypeError, ValueError):
                continue
        return out

    mat_rows = clean_int(mat, 4)
    prod_rows = clean_int(prod, 4)
    prob_rows = []
    for r in prob:
        try:
            prob_rows.append((int(r[0]), int(r[1]), int(r[2]), float(r[3])))
        except (TypeError, ValueError):
            continue
    act_rows = []
    for r in act:
        try:
            mr = int(r[3]) if _act_has_max_runs and len(r) > 3 and r[3] is not None else 0
            act_rows.append((int(r[0]), int(r[1]), int(r[2] or 0), mr))
        except (TypeError, ValueError):
            continue

    # meta-group per type (T1=1, T2=2, Storyline=3, Faction=4, Officer=5,
    # Deadspace=6, T3=14 …). 0 = unknown (NOT assumed Tech I, so LP/Faction items
    # missing from the meta source are not mistaken for buildable T1).
    meta_map = {}
    for r in meta_rows:
        try:
            meta_map[int(r[0])] = int(r[1])
        except (TypeError, ValueError):
            continue
    metalevel_map = {}
    for r in metalevel_rows:
        try:
            tid = int(r[0])
            val = r[1] if r[1] is not None else r[2]
            if val is not None:
                metalevel_map[tid] = int(val)
        except (TypeError, ValueError):
            continue
    vol_map = {}
    for r in vol_rows:
        try:
            vol_map[int(r[0])] = float(r[1] or 0)
        except (TypeError, ValueError):
            continue
    pkg_vol_map = {}
    for r in pkg_vol_rows:
        try:
            pkg_vol_map[int(r[0])] = float(r[1] or 0)
        except (TypeError, ValueError):
            continue
    item_cat_rows = []
    for r in types_rows:
        try:
            tid = int(r[0])
            gid = int(r[1]) if r[1] is not None else 0
            cid = int(r[2]) if r[2] is not None else 0
        except (TypeError, ValueError):
            continue
        meta = 0
        if have_meta_col and len(r) > 3 and r[3] is not None:
            try:
                meta = int(r[3])
            except (TypeError, ValueError):
                meta = 0
        if not meta:
            meta = meta_map.get(tid, 0)
        race_idx = 4 if have_meta_col else 3
        race_id = None
        if len(r) > race_idx and r[race_idx] is not None:
            try:
                race_id = int(r[race_idx])
            except (TypeError, ValueError):
                race_id = None
        item_cat_rows.append((tid, gid, cid, meta, metalevel_map.get(tid, 0),
                              vol_map.get(tid, 0.0), pkg_vol_map.get(tid), race_id))
    cat_name_rows = []
    for r in cat_rows:
        try:
            cat_name_rows.append((int(r[0]), str(r[1])))
        except (TypeError, ValueError):
            continue
    grp_name_rows = []
    for r in grp_rows:
        try:
            grp_name_rows.append((int(r[0]), str(r[1])))
        except (TypeError, ValueError):
            continue

    # 4) write into our own small recipe DB
    rig_attr = {}   # type_id -> {2593:zeit, 2594:material, 2595:kosten}
    for r in rig_attr_rows:
        try:
            tid = int(r[0]); aid = int(r[1])
            val = r[2] if r[2] is not None else r[3]
            rig_attr.setdefault(tid, {})[aid] = float(val or 0)
        except (TypeError, ValueError):
            continue
    rig_records = []
    rig_effs = {}   # type_id -> "eff1,eff2,..."
    for r in rig_eff_rows:
        try:
            tid = int(r[0])
        except (TypeError, ValueError):
            continue
        rig_effs.setdefault(tid, []).append(str(r[1] or ""))
    for r in rig_rows:
        try:
            tid = int(r[0])
        except (TypeError, ValueError):
            continue
        name = r[1] or ""
        # Struktur-Rigs heißen "... M-Set/L-Set/XL-Set ..." – Service-Module (z. B.
        # „Manufacturing Plant“, „Research Lab“) NICHT. So kommen auch Research-/
        # Kopier-/Invention-Accelerators rein, deren Zeit-Bonus auf anderen
        # Attributen als 2593/2594/2595 liegt (die stünden sonst auf 0 → wären raus).
        if "-Set" not in name:
            continue
        # NUR ECHTE BLAUPAUSEN AUSSORTIEREN (Nutzer-Fund, Sitzung 20).
        # Hier stand `if "blueprint" in name.lower()` - das warf auch RIGS
        # raus, die das Wort im Namen tragen: "Standup M-Set Blueprint Copy
        # Accelerator I" ist ein Rig, keine Blaupause. Der Nutzer konnte es
        # in "Struktur bearbeiten" nicht auswaehlen, obwohl es in seiner
        # Struktur steckt.
        # EVE benennt Blaupausen IMMER "<Item> Blueprint" - also auf das
        # ENDE pruefen, nicht auf ein Vorkommen irgendwo im Namen.
        if name.strip().lower().endswith(" blueprint"):
            continue                        # die Blaupause des Rigs, nicht das
                                            # Rig selbst - schon HIER raus (nicht
                                            # erst beim Anzeigen), damit
                                            # load_rigs() sauber ist.
        a = rig_attr.get(tid, {})
        t = next((a[i] for i in time_attr_ids if i in a), 0.0)
        m = next((a[i] for i in mat_attr_ids if i in a), 0.0)
        co = next((a[i] for i in cost_attr_ids if i in a), 0.0)
        effs = ",".join(rig_effs.get(tid, []))
        rig_records.append((tid, name, r[2] or "", t, m, co, effs))

    dec_attr = {}   # type_id -> {1112:prob, 1113:me, 1114:te, 1124:runs}
    for r in dec_attr_rows:
        try:
            tid = int(r[0]); aid = int(r[1])
            val = r[2] if r[2] is not None else r[3]
            dec_attr.setdefault(tid, {})[aid] = float(val or 0)
        except (TypeError, ValueError):
            continue
    dec_records = []
    for r in dec_rows:
        try:
            tid = int(r[0])
        except (TypeError, ValueError):
            continue
        a = dec_attr.get(tid, {})
        dec_records.append((tid, r[1], a.get(1112, 1.0), a.get(1113, 0.0),
                            a.get(1114, 0.0), a.get(1124, 0.0)))
    try:
        _write_decryptor_diagnostic(dec_records)
    except Exception:
        pass

    # Pro Blueprint (nur Fertigung, activityID=1) die benötigten Science-Skills, die
    # −1 %/Level Fertigungszeit geben. Nur diese wenigen zählen für die Job-Zeit.
    bp_science_records = []
    for r in bp_skill_rows:
        try:
            bp_id = int(r[0]); act_id = int(r[1]); sk_id = int(r[2])
        except (TypeError, ValueError):
            continue
        if act_id != 1:               # nur Manufacturing
            continue
        if sk_id in science_skill_ids:
            bp_science_records.append((bp_id, sk_id))
    bp_invention_records = list(invention_skill_rows)
    repro_records = clean_int(repro_rows, 3)
    portion_records = []
    for r in portion_rows:
        try:
            portion_records.append((int(r[0]), int(r[1] or 1)))
        except (TypeError, ValueError):
            continue
    repro_skill_records = []
    for r in repro_skill_rows:
        try:
            repro_skill_records.append((str(r[1]), int(r[0])))
        except (TypeError, ValueError):
            continue
    erz_skill_records = []
    for r in erz_skill_rows:
        try:
            _v = r[1] if r[1] is not None else r[2]
            erz_skill_records.append((int(r[0]), int(_v)))
        except (TypeError, ValueError):
            continue
    repro_imp_records = []
    for r in repro_imp_rows:
        try:
            _v = r[3] if r[3] is not None else r[4]
            repro_imp_records.append((int(r[0]), str(r[1]), str(r[2]), float(_v)))
        except (TypeError, ValueError):
            continue
    repro_struct_records = []
    for r in repro_struct_rows:
        try:
            _v = r[2] if r[2] is not None else r[3]
            repro_struct_records.append((int(r[0]), str(r[1]), float(_v)))
        except (TypeError, ValueError):
            continue
    repro_rig_records = []
    for r in repro_rig_rows:
        try:
            # Fehlt ein Sicherheits-Faktor (Service-Modul hat keinen), gilt 1.0.
            repro_rig_records.append((int(r[0]), str(r[1]), float(r[2]),
                                      float(r[3] if r[3] is not None else 1.0),
                                      float(r[4] if r[4] is not None else 1.0),
                                      float(r[5] if r[5] is not None else 1.0)))
        except (TypeError, ValueError):
            continue

    with _conn() as c:
        c.execute("DELETE FROM materials")
        c.execute("DELETE FROM products")
        c.execute("DELETE FROM probabilities")
        c.execute("DELETE FROM activities")
        c.executemany(
            "INSERT INTO materials(blueprint_id,activity_id,material_id,quantity) "
            "VALUES (?,?,?,?)", mat_rows)
        c.executemany(
            "INSERT INTO products(blueprint_id,activity_id,product_id,quantity) "
            "VALUES (?,?,?,?)", prod_rows)
        c.executemany(
            "INSERT INTO probabilities(blueprint_id,activity_id,product_id,probability) "
            "VALUES (?,?,?,?)", prob_rows)
        c.executemany(
            "INSERT INTO activities(blueprint_id,activity_id,time,max_runs) "
            "VALUES (?,?,?,?)",
            act_rows)
        if item_cat_rows:
            c.execute("DELETE FROM item_cat")
            c.executemany(
                "INSERT OR REPLACE INTO item_cat"
                "(type_id,group_id,category_id,meta_group_id,meta_level,volume,"
                "packaged_volume,race_id) VALUES (?,?,?,?,?,?,?,?)", item_cat_rows)
        if cat_name_rows:
            c.execute("DELETE FROM cat_name")
            c.executemany("INSERT OR REPLACE INTO cat_name(category_id,name) VALUES (?,?)",
                          cat_name_rows)
        if grp_name_rows:
            c.execute("DELETE FROM group_name")
            c.executemany("INSERT OR REPLACE INTO group_name(group_id,name) VALUES (?,?)",
                          grp_name_rows)
        if rig_records:
            c.execute("DELETE FROM rigs")
            c.executemany(
                "INSERT OR REPLACE INTO rigs"
                "(type_id,name,group_name,time_bonus,material_bonus,cost_bonus,effects) "
                "VALUES (?,?,?,?,?,?,?)", rig_records)
        if dec_records:
            c.execute("DELETE FROM decryptors")
            c.executemany(
                "INSERT OR REPLACE INTO decryptors"
                "(type_id,name,prob_mult,me_mod,te_mod,run_mod) VALUES (?,?,?,?,?,?)",
                dec_records)
        c.execute("DELETE FROM bp_science_skills")
        if bp_science_records:
            c.executemany(
                "INSERT INTO bp_science_skills(blueprint_id,skill_id) VALUES (?,?)",
                bp_science_records)
        c.execute("DELETE FROM bp_invention_skills")
        if bp_invention_records:
            c.executemany(
                "INSERT INTO bp_invention_skills(blueprint_id,skill_id,is_encryption) "
                "VALUES (?,?,?)", bp_invention_records)
        # NUR ERSETZEN, WENN ETWAS ANKAM: eine SDE-Fassung ohne die Tabelle
        # darf einen frueheren, vollen Stand nicht durch Leere ersetzen.
        if repro_records:
            c.execute("DELETE FROM reprocess")
            c.executemany(
                "INSERT INTO reprocess(type_id,material_id,quantity) VALUES (?,?,?)",
                repro_records)
        if portion_records:
            c.execute("DELETE FROM reprocess_portion")
            c.executemany(
                "INSERT OR REPLACE INTO reprocess_portion(type_id,portion_size) "
                "VALUES (?,?)", portion_records)
        if repro_skill_records:
            c.execute("DELETE FROM reprocess_skill_ids")
            c.executemany(
                "INSERT OR REPLACE INTO reprocess_skill_ids(name,type_id) VALUES (?,?)",
                repro_skill_records)
        if erz_skill_records:
            c.execute("DELETE FROM reprocess_erz_skill")
            c.executemany(
                "INSERT OR REPLACE INTO reprocess_erz_skill(type_id,skill_id) VALUES (?,?)",
                erz_skill_records)
        if repro_imp_records:
            c.execute("DELETE FROM reprocess_implant")
            c.executemany(
                "INSERT OR REPLACE INTO reprocess_implant(type_id,name,attr,value) "
                "VALUES (?,?,?,?)", repro_imp_records)
        if repro_struct_records:
            c.execute("DELETE FROM reprocess_struktur")
            c.executemany(
                "INSERT OR REPLACE INTO reprocess_struktur(type_id,name,bonus_pct) "
                "VALUES (?,?,?)", repro_struct_records)
        if repro_rig_records:
            c.execute("DELETE FROM reprocess_rig")
            c.executemany(
                "INSERT OR REPLACE INTO reprocess_rig(type_id,name,mult,hi,low,null_sec) "
                "VALUES (?,?,?,?,?,?)", repro_rig_records)
        c.execute("INSERT OR REPLACE INTO meta(k,v) VALUES('updated', ?)",
                  (str(time.time()),))
    # ERST NACH DEM SCHREIBEN: gemerkte Kategorien/Rezepte verwerfen (der
    # Datei-Schluessel allein sieht die neue SDE im WAL-Modus nicht sicher).
    _sde_caches_verwerfen()
    _meta_counts = {}
    for _row in item_cat_rows:
        _meta_counts[_row[3]] = _meta_counts.get(_row[3], 0) + 1
    return {"materials": len(mat_rows), "products": len(prod_rows),
            "probabilities": len(prob_rows), "items": len(item_cat_rows),
            "activities": len(act_rows), "rigs": len(rig_records),
            "bp_science": len(bp_science_records),
            "bp_invention_skills": len(bp_invention_records),
            "reprocess": len(repro_records),
            "reprocess_skills": len(repro_skill_records),
            "reprocess_erz_skill": len(erz_skill_records),
            "reprocess_implants": len(repro_imp_records),
            "reprocess_struktur": len(repro_struct_records),
            "reprocess_rigs": len(repro_rig_records),
            "have_meta_col": have_meta_col,
            # Diagnose: wie viele Items je Tech-Stufe geladen wurden (1=T1,
            # 2=T2, 14=T3, 0=unbekannt/nicht zugeordnet) - macht sofort
            # sichtbar, ob z.B. gar keine T2-Items in der Quelle ankamen,
            # statt das erst über leere Scanner-Ergebnisse zu vermuten.
            "meta_counts": _meta_counts}


# ---- in-memory recipe index (built once per scan) --------------------------
_RECIPES_CACHE = {"sig": None, "obj": None}


def recipes_cached():
    """Gemeinsame, wiederverwendete `Recipes`-Instanz.

    NUTZER-WUNSCH (Sitzung 20): "koennen wir das Laden der Bauplaene beim
    Oeffnen beschleunigen?" GEMESSEN, woran es liegt:
        Recipes laden        310 ms
        item_category_map     34 ms
        build_tree             1 ms
        production_plan        1 ms
    Die Rechnung ist also nicht das Problem - das Einlesen der Rezepte ist es.
    Es passierte bei JEDEM Oeffnen neu, obwohl sich die Daten nur aendern,
    wenn die SDE neu geladen wird.

    DER SCHLUESSEL IST DIE DATEI SELBST (Groesse + Aenderungszeit der
    industry.db). Wird die SDE neu eingelesen, aendert sich beides, und die
    Kopie wird verworfen - ohne dass irgendwer daran denken muss. Ein Zaehler,
    den man von Hand hochsetzt, waere genau die Falle, die hier schon oft
    zugeschnappt ist.

    DIE INSTANZ WIRD NUR GELESEN: im ganzen Programm setzt niemand ein Feld
    auf einer Recipes-Instanz (gemessen). Waere das anders, teilten sich zwei
    Bauplaene stillschweigend einen Zustand.
    """
    import os as _os
    try:
        _st = _os.stat(_db_path())
        sig = (_st.st_size, int(_st.st_mtime_ns))
    except Exception:
        return Recipes()                 # kein Schluessel -> lieber frisch
    if _RECIPES_CACHE["sig"] == sig and _RECIPES_CACHE["obj"] is not None:
        return _RECIPES_CACHE["obj"]
    obj = Recipes()
    _RECIPES_CACHE["sig"] = sig
    _RECIPES_CACHE["obj"] = obj
    return obj


class Recipes:
    def __init__(self):
        self.product_to_bp = {}   # product_id -> (blueprint_id, activity_id, qty)
        self.bp_materials = {}     # (blueprint_id, activity_id) -> [(mat_id, qty)]
        self.reaction_products = set()
        self.invention_for_bpc = {}  # t2_bpc_id -> (t1_bp, runs, prob, [(dc,qty)])
        self.activity_time = {}      # (blueprint_id, activity_id) -> base time (s)
        self.activity_max_runs = {}  # (blueprint_id, activity_id) -> max Runs/Job
                                      # (0/fehlt = kein Limit laut SDE)
        with _conn() as c:
            # SDE-Altlasten-Filter (Nutzer-Fund: Eis + gepresste Erze
            # erschienen als "baubar" unter Baupreis): die SDE enthält noch
            # UNVERÖFFENTLICHTE Legacy-Blueprints (z.B. die 2016 entfernten
            # "Compression Blueprints" für Erz/Eis). item_cat wird beim
            # SDE-Import aus invTypes WHERE published=1 befüllt - Blueprints,
            # die dort fehlen, sind ingame nicht erhältlich und ihre Produkte
            # damit für Spieler NICHT baubar. Schutzgitter: nur filtern, wenn
            # item_cat plausibel gefüllt ist (alte/leere lokale DBs sonst
            # nicht kastrieren).
            published = set()
            try:
                published = {row["type_id"] for row in
                             c.execute("SELECT type_id FROM item_cat")}
            except Exception:
                published = set()
            use_pub = len(published) > 1000
            inv_products = {}   # t2_bpc -> (t1_bp, runs)
            for r in c.execute("SELECT * FROM products"):
                if use_pub and r["blueprint_id"] not in published:
                    continue     # unveröffentlichter Legacy-Blueprint
                pid = r["product_id"]
                act = r["activity_id"]
                if act in ACTIVITIES:
                    cur = self.product_to_bp.get(pid)
                    if cur is None or act == MANUFACTURING:
                        self.product_to_bp[pid] = (r["blueprint_id"], act, r["quantity"] or 1)
                    if act == REACTION:
                        self.reaction_products.add(pid)
                elif act == INVENTION:
                    inv_products[pid] = (r["blueprint_id"], r["quantity"] or 1)
            probs = {}
            for r in c.execute("SELECT * FROM probabilities WHERE activity_id=?", (INVENTION,)):
                probs[r["product_id"]] = r["probability"]
            for r in c.execute("SELECT * FROM materials"):
                key = (r["blueprint_id"], r["activity_id"])
                self.bp_materials.setdefault(key, []).append(
                    (r["material_id"], r["quantity"]))
            try:
                for r in c.execute("SELECT * FROM activities"):
                    self.activity_time[(r["blueprint_id"], r["activity_id"])] = r["time"]
                    try:
                        mr = r["max_runs"]
                    except Exception:
                        mr = None
                    self.activity_max_runs[(r["blueprint_id"], r["activity_id"])] = mr or 0
            except Exception:
                pass
            # assemble invention info keyed by the produced T2 BPC
            for t2_bpc, (t1_bp, runs) in inv_products.items():
                datacores = self.bp_materials.get((t1_bp, INVENTION), [])
                prob = probs.get(t2_bpc, 0.0)
                if prob > 0 and datacores:
                    self.invention_for_bpc[t2_bpc] = (t1_bp, runs, prob, datacores)

    def is_manufactured(self, type_id) -> bool:
        """True only for real MANUFACTURING end-products. Excludes reaction-only
        outputs (moon goo like Tungsten Carbide), ores/compressed ore, minerals
        and NPC-drop items, which have no manufacturing blueprint.
        PLATZHALTER-REZEPTE zaehlen NICHT als baubar (Nutzer-Fund im
        T1-Scan: Praxis/Gnosis/Sunesis/Metamorphosis mit Milliarden-%-
        Margen). Die SoCT-Event-Blueprints stehen published=true in der SDE,
        ihre komplette Materialliste ist aber "1x Tritanium" (SDE-Referenz,
        z.B. Praxis Blueprint 47716) - ein Schiff fuer 4 ISK Baukosten.
        Kriterium: Gesamt-Materialmenge <= 1 ist kein echtes Rezept; kein
        reales Fertigungsprodukt entsteht aus einem einzigen Stueck
        Material. Folge ueberall gleich (EINE Regel): der Scanner bietet
        das Item nicht als Bau-Treffer an, der Bauplan sagt "kaufen"."""
        bp = self.product_to_bp.get(type_id)
        if not (bp and bp[1] == MANUFACTURING):
            return False
        mats = self.bp_materials.get((bp[0], MANUFACTURING)) or []
        if sum(q for _m, q in mats) <= 1:
            return False
        return True


def owned_bp_runs(blueprints, target_bp_ids=None):
    """ESI-Blaupausenliste -> ({bp_id: Summe verbleibender BPC-Runs}, {bp_ids mit BPO}).

    EINE Ableitung fuer BEIDE Nutzer - den Invention-Tab des Bauplan-Dialogs
    und den Bau-Scan. Vorher rechnete das nur der Dialog, direkt in
    _load_all_invention_bpc_from_esi(); der Scan kannte eigene BPCs deshalb
    gar nicht und stellte JEDEM T2-Item die vollen Invention-Kosten in
    Rechnung. Eine zweite Ableitung danebenzustellen waere genau die
    Zwei-Wahrheiten-Falle - also hier, einmal, ohne Qt und ohne Dialog-
    Zustand (damit auch ohne offenen Bauplan aufrufbar UND testbar).

    Regeln (unveraendert aus dem Dialog uebernommen):
    * Eine BPO deckt unbegrenzt viele Runs ab -> der bp_id landet in
      `bpo_ids` und NICHT in `runs` (eine Zahl waere dort gelogen).
    * BPCs stapeln: quantity x runs, ueber alle Charaktere summiert.
    * Eintraege ohne verbleibende Runs fallen raus (0 ist kein Besitz).
    `target_bp_ids=None` heisst "alles", sonst wird auf diese bp_ids gefiltert.
    """
    runs = {}
    bpo_ids = set()
    matches = {}
    for b in blueprints or []:
        bid = b.get("type_id")
        if bid is None:
            continue
        if target_bp_ids is not None and bid not in target_bp_ids:
            continue
        matches.setdefault(bid, []).append(b)
    for bid, rows in matches.items():
        if any(r.get("is_bpo") for r in rows):
            bpo_ids.add(bid)
            continue
        total = sum(int(r.get("quantity", 1) or 1) * int(r.get("runs", 0) or 0)
                    for r in rows)
        if total > 0:
            runs[bid] = total
    return runs, bpo_ids


def _job_cost(mats, activity, prod_qty, opts, parts_out=None, type_id=None):
    """EIV-basierte Job-Kosten pro Run – oder None, wenn keine adjusted prices da sind.
      EIV = Σ(Basis-Menge × adjusted_price der Inputs)
      Job = EIV × Index × (1 − Rollenbonus) + EIV × (Facility-Tax + 4 % SCC)
    Ohne adjusted prices → None (dann greift die alte Pauschale).
    `parts_out` (optional, dict) ist ein AUSGABE-Kanal wie `mats_out` bei
    _inv_cost: die drei Bestandteile werden AUFADDIERT ("index" = EIV×Index
    nach Rollenbonus/Cost-Rig, "tax" = EIV×Facility-Tax, "scc" = EIV×SCC).
    Gegenprobe: die Summe der drei ist EXAKT der Rueckgabewert - dieselbe
    Rechnung, nur in Teilen gemeldet, keine zweite daneben."""
    adj = opts.get("adjusted_prices")
    if adj is None:
        return None
    eiv = 0.0
    for mat_id, qty in mats:
        eiv += qty * (adj.get(mat_id, 0) or 0)
    if activity == REACTION:
        idx = opts.get("system_index_reaction", 0.0) or 0.0
        cost_rig = opts.get("cost_rig_reaction", 0.0) or 0.0
    else:
        idx = opts.get("system_index_mfg", 0.0) or 0.0
        cost_rig = opts.get("cost_rig_mfg", 0.0) or 0.0
    # STEUER UND ROLLENBONUS JE AKTIVITAET: gebaut und reagiert wird in
    # VERSCHIEDENEN Strukturen (der Plan waehlt sie automatisch), und die
    # haben verschiedene Besitzer-Steuern und Strukturtypen. Vorher galt ein
    # Wert fuer beides - der aus der Standard-Struktur, auch wenn ganz
    # woanders gebaut wurde. Fallback auf die alten Schluessel, damit
    # Aufrufer ohne die neuen weiterhin funktionieren.
    if activity == REACTION:
        rbonus = opts.get("role_bonus_reaction", opts.get("role_bonus", 0.0)) or 0.0
        ftax = opts.get("facility_tax_reaction",
                        opts.get("facility_tax", 0.0)) or 0.0
    else:
        rbonus = opts.get("role_bonus", 0.0) or 0.0
        ftax = opts.get("facility_tax", 0.0) or 0.0
    scc = opts.get("scc_surcharge", 0.04)      # CCP-Policy-Wert, einstellbar
    # JE-ITEM-UEBERSCHREIBUNG (Sitzung 9, Simurgh): der Bau waehlt seit
    # Sitzung 8 pro STUFE eine Struktur, die Werte oben sind aber je
    # AKTIVITAET pauschal - beim Endprodukt kamen so Index, Cost-Rig,
    # Rollenbonus und Steuer der KOMPONENTEN-Struktur zum Zug. Steht fuer
    # dieses Produkt ein Eintrag in opts["jobcost_by_tid"], gilt DER.
    _ov = (opts.get("jobcost_by_tid") or {}).get(type_id) \
        if type_id is not None else None
    if _ov:
        idx = _ov.get("system_index", idx)
        cost_rig = _ov.get("cost_rig", cost_rig)
        rbonus = _ov.get("role_bonus", rbonus)
        ftax = _ov.get("facility_tax", ftax)
    # Cost-Rig der Struktur senkt den Index-Anteil (EIV × Index) der Job-Kosten.
    _p_index = eiv * idx * (1 - rbonus) * (1 - cost_rig / 100.0)
    _p_tax = eiv * ftax
    _p_scc = eiv * scc
    if parts_out is not None:
        parts_out["index"] = parts_out.get("index", 0.0) + _p_index
        parts_out["tax"] = parts_out.get("tax", 0.0) + _p_tax
        parts_out["scc"] = parts_out.get("scc", 0.0) + _p_scc
    return _p_index + _p_tax + _p_scc


def build_cost(type_id, price_fn, recipes: Recipes, opts: dict,
               memo=None, visiting=None, depth=0, parts_memo=None):
    """Per-unit build cost, or None if it can't be priced/built.
    price_fn(type_id) -> market unit price (or None).

    `parts_memo` (optional, {type_id: dict|None}) ist ein AUSGABE-Kanal: wird
    ein dict uebergeben, legt jeder berechnete Eintrag dort seine
    Aufschluesselung PRO STUECK ab - aus DERSELBEN Rechnung, die die Zahl
    liefert (keine zweite Ableitung daneben):
        mat_market   Material zum Marktpreis (inkl. selbst gebauter Stufen)
        mat_adjusted Material ueber den Adjusted-Price-Rueckfall bepreist
        job          Job-Kosten (EIV-Formel oder Pauschale)
        inv          verrechnete Invention-Kosten
    Die ersten vier ergeben zusammen exakt den Rueckgabewert. Dazu kommt
        inv_saved    Invention, die wegen EIGENER BPCs NICHT berechnet wurde
    - KEIN Summand, sondern der Ausweis einer Annahme (Arbeitsregel 6: nichts
    stillschweigend guenstiger rechnen, sondern es sichtbar machen).

    BEWUSSTE NÄHERUNG (kein Bug): ME wird hier KONTINUIERLICH gerechnet
    (qty x (1 - ME)), OHNE die EVE-Rundung "aufrunden je Run, mindestens 1
    Material pro Run" - diese Pro-Stück-Funktion kennt keine Run-Zahl und wird
    vom Scanner für hunderte Items auf einmal genutzt. Deshalb weichen die
    Zahlen minimal vom Ingame-Industriefenster ab (v.a. bei kleinen
    Materialmengen). production_plan() rundet exakt wie EVE - für den
    verbindlichen Bauplan gelten DESSEN Zahlen."""
    if memo is None:
        memo = {}
    if visiting is None:
        visiting = set()

    def _no_parts(tid):
        """Kein Ergebnis -> auch keine Aufschluesselung. Der Eintrag wird
        trotzdem gesetzt, sonst gilt der Posten unten als 'Aufschluesselung
        fehlt noch' und wuerde bei jedem Aufruf neu gerechnet."""
        if parts_memo is not None:
            parts_memo[tid] = None

    # Ein memoisierter Wert wird nur dann wiederverwendet, wenn auch seine
    # Aufschluesselung schon vorliegt - sonst kaeme bei gemeinsam genutztem
    # memo (Scanner: ein memo fuer hunderte Items) eine leere parts-Zeile raus.
    if type_id in memo and (parts_memo is None or type_id in parts_memo):
        return memo[type_id]
    if type_id in visiting or depth > opts.get("max_depth", 12):
        return None

    bp = recipes.product_to_bp.get(type_id)
    if not bp:
        memo[type_id] = None
        _no_parts(type_id)
        return None
    bp_id, activity, prod_qty = bp
    mats = recipes.bp_materials.get((bp_id, activity))
    if not mats:
        memo[type_id] = None
        _no_parts(type_id)
        return None

    me_map = opts.get("me_map")
    if type_id == BUENDEL_ID:
        me = 0.0                     # Buendel: Stueckzahlen sind exakt, kein ME
    elif activity == MANUFACTURING:
        inv_me = _invention_me_pct(bp_id, recipes, opts)
        if inv_me is not None:
            rig_me = (opts.get("rig_me_map") or {}).get(type_id, 0) or 0
            me_pct = me_invented_pct(inv_me, rig_me,
                                     (opts.get("ec_me_map") or {}).get(type_id, 0) or 0)
        else:
            me_pct = (me_map.get(type_id) if me_map and type_id in me_map
                      else opts.get("me", 0))
        me = (me_pct or 0) / 100.0
    elif activity == REACTION:
        rmap = opts.get("me_map_reaction")
        me_pct = (rmap.get(type_id) if rmap and type_id in rmap
                  else (opts.get("me_reaction", 0) or 0))
        me = (me_pct or 0) / 100.0   # Reaktions-ME-Rig (nur passende Domäne)
    else:
        me = 0.0
    visiting.add(type_id)
    total = 0.0
    ok = True
    _adj = opts.get("adjusted_prices") or {}
    # Aufschluesselung JE RUN (wird unten zusammen mit run_cost durch prod_qty
    # geteilt), damit sie am Ende garantiert auf per_unit aufgeht.
    _p_market = 0.0
    _p_adj = 0.0
    _p_job = 0.0
    _p_inv = 0.0
    _p_inv_saved = 0.0

    def _buy(tid):
        """(Preis, aus_Rueckfall). Das zweite Feld ist der Grund, warum es
        diese Aufschluesselung gibt: ein Adjusted-Price ist ein ESI-Mittelwert,
        kein Angebot am Hub - Kosten, die daraus stammen, sind unsicherer."""
        p = price_fn(tid)
        if p is not None and p > 0:
            return p, False
        a = _adj.get(tid)                 # kein Marktpreis → Adjusted (wie im Plan)
        return (a, True) if (a and a > 0) else (None, False)
    for mat_id, qty in mats:
        qeff = qty * (1 - me)
        rc = build_cost(mat_id, price_fn, recipes, opts, memo, visiting, depth + 1,
                        parts_memo)
        buy, from_adj = _buy(mat_id)
        is_reaction = mat_id in recipes.reaction_products
        _never = opts.get("never_build") or set()
        if rc is not None and mat_id not in _never and (
                (is_reaction and opts.get("build_reactions", True))
                or opts.get("force_build")
                or buy is None
                or rc < buy):
            unit = rc
            _built = True
        elif buy is not None:
            unit = buy
            _built = False
        elif rc is not None:
            unit = rc
            _built = True
        else:
            ok = False
            break
        if parts_memo is not None:
            _sub = parts_memo.get(mat_id) if _built else None
            if _sub:
                # Selbst gebaut: die Anteile der Unterstufe zaehlen in DERSELBEN
                # Kategorie weiter (Material bleibt Material, Job bleibt Job).
                _p_market += _sub["mat_market"] * qeff
                _p_adj += _sub["mat_adjusted"] * qeff
                _p_job += _sub["job"] * qeff
                _p_inv += _sub["inv"] * qeff
                _p_inv_saved += _sub["inv_saved"] * qeff
            elif _built:
                # gebaut, aber ohne Aufschluesselung (nur bei Rekursionsabbruch)
                _p_market += unit * qeff
            elif from_adj:
                _p_adj += unit * qeff
            else:
                _p_market += unit * qeff
        total += unit * qeff
    visiting.discard(type_id)

    if not ok:
        memo[type_id] = None
        _no_parts(type_id)
        return None
    jc = (0.0 if type_id == BUENDEL_ID
          else _job_cost(mats, activity, prod_qty, opts, type_id=type_id))
    if jc is not None:
        run_cost = total + jc
        _p_job += jc
    else:
        run_cost = total * (1 + opts.get("job_pct", 0) / 100.0)
        _p_job += total * (opts.get("job_pct", 0) / 100.0)
    per_unit = run_cost / prod_qty if prod_qty else run_cost
    _div = prod_qty if prod_qty else 1
    _p_market /= _div
    _p_adj /= _div
    _p_job /= _div
    _p_inv /= _div
    _p_inv_saved /= _div

    # T2: add invention cost (datacores / success chance) spread over output.
    # HINWEIS: eigene, einfachere Formel als _inv_cost (dort: ≥75%-Sicherheits-
    # Versuche für eine konkrete Bauplan-Menge). Hier, in der PRO-STÜCK-
    # Funktion (kennt keine Ziel-Menge, wird u.a. vom Scanner "Bauplan Suchen"
    # für hunderte Items auf einmal genutzt), bleibt bewusst der reine
    # Erwartungswert (dc_cost/prob) - aber jetzt mit denselben Korrekturen wie
    # _inv_cost: per-Item-Decryptor, Skill-Modifier, "Eigene BPC"-Override.
    # Vorher fehlten alle drei hier, obwohl sie in _inv_cost längst gefixt waren.
    # "Eigene BPC"-Override (BPO im Hangar / wird gekauft statt erfunden) hebt
    # den Posten auf - die Rechnung laeuft trotzdem durch, damit der entfallene
    # Betrag unten als `inv_saved` ausgewiesen werden kann statt spurlos zu
    # verschwinden. Am Rueckgabewert aendert das nichts.
    _inv_override = bp_id in (opts.get("inv_manual_override") or {})
    if activity == MANUFACTURING and opts.get("invention", True):
        inv = recipes.invention_for_bpc.get(bp_id)
        if inv:
            t1_bp, runs, prob, datacores = inv
            dc_cost = 0.0
            for dc_id, dc_qty in datacores:
                p = price_fn(dc_id)
                if p:
                    dc_cost += p * dc_qty
            per_item_dv = (opts.get("inv_decryptor_map") or {}).get(bp_id)
            if per_item_dv is not None:
                prob *= per_item_dv[0]
                runs += per_item_dv[1]
                dcy = per_item_dv[4]
            else:
                prob *= opts.get("inv_prob_mult", 1.0)
                runs += opts.get("inv_run_mod", 0)
                dcy = opts.get("inv_decryptor_id")
            prob = min(1.0, prob * (opts.get("inv_skill_modifier") or {}).get(bp_id, 1.0))
            if dcy:
                dc_cost += (price_fn(dcy) or 0)
            if prob > 0:
                cost_per_success = dc_cost / prob
                items_per_success = max(1, runs * prod_qty)
                _add = cost_per_success / items_per_success
                # EIGENE BPCs (opts["inv_owned_runs"], dieselbe Quelle wie
                # _inv_cost im Bauplan): wer die Kopien schon im Hangar hat,
                # zahlt fuer sie keine Invention mehr. Der Scanner rechnete
                # bisher fuer JEDES T2-Item die vollen Kosten und hielt
                # deshalb Dinge fuer unrentabel, die es nicht sind.
                # BEWUSST ALLES-ODER-NICHTS: diese Funktion rechnet PRO STUECK
                # und kennt keine Losgroesse. Ein anteiliger Abzug braeuchte
                # eine Referenzmenge, die es hier nicht gibt - und weil der
                # Scanner EIN memo ueber hunderte Items teilt, wuerde ein
                # mengenabhaengiger Wert den Cache vergiften. Der nicht
                # berechnete Betrag wird als "inv_saved" gemeldet, damit die
                # Zeile die Annahme ausweisen kann statt sie zu verstecken.
                if _inv_override or int(
                        (opts.get("inv_owned_runs") or {}).get(bp_id, 0) or 0) > 0:
                    _p_inv_saved += _add
                else:
                    per_unit += _add
                    _p_inv += _add

    # WEG A: RUECKLAEUFER-GUTSCHRIFT (Nutzer-Befund 19.09.2026, Ishtar x10:
    # Thulium Hafnite wurde GEKAUFT, obwohl die Unrefined-Wahl es fuer
    # 9'730 statt 18'560 je Stueck bauen wollte). Die Rezept-Kopie
    # (reprocess.rezepte_mit_unrefined) fuehrt X ueber die Unrefined-Formel,
    # deren Kosten je Run OHNE die zurueckkommenden 91 Hafnium 28'601 je
    # Stueck sind - production_plan sah nur diese Zahl und kaufte. Die Wahl
    # hatte die Gutschrift schon eingerechnet; hier zaehlt sie genauso,
    # damit build_cost, Rezeptbaum und Plan EINE Entscheidung treffen.
    _uw = (getattr(recipes, "unrefined", None) or {}).get(type_id)
    if _uw and prod_qty:
        _kr = float(_uw.get("kredit_je_run") or 0.0) / prod_qty
        if _kr > 0:
            per_unit = max(0.0, per_unit - _kr)
            _p_market = max(0.0, _p_market - _kr)
    memo[type_id] = per_unit
    if parts_memo is not None:
        parts_memo[type_id] = {"mat_market": _p_market, "mat_adjusted": _p_adj,
                               "job": _p_job, "inv": _p_inv,
                               "inv_saved": _p_inv_saved}
    return per_unit


def build_time_per_unit(type_id, price_fn, recipes: Recipes, opts: dict,
                        time_memo=None, cost_memo=None, visiting=None, depth=0):
    """Gesamt-Bauzeit (Sekunden) für EIN fertiges Stück von type_id, inklusive
    der Zeit für selbst gebaute Zwischenprodukte. „Selbst gebaut vs. gekauft“
    wird wie bei build_cost entschieden (billigere Option) -- gekaufte Materialien
    kosten keine Bauzeit. Ergebnis ist pro Stück (Run-Zeit / Output-Menge).

    Für den Scanner gedacht: mit gemeinsamem time_memo/cost_memo über viele Items
    aufrufen, dann ist es günstig. Gibt 0.0 zurück, wenn keine Zeitdaten da sind.

    te_factor/te_factor_reaction aus opts skalieren die Basiszeit (Rig/Skill-Boni)."""
    if time_memo is None:
        time_memo = {}
    if cost_memo is None:
        cost_memo = {}
    if visiting is None:
        visiting = set()
    if type_id in time_memo:
        return time_memo[type_id]
    if type_id in visiting or depth > opts.get("max_depth", 12):
        return 0.0
    bp = recipes.product_to_bp.get(type_id)
    if not bp:
        time_memo[type_id] = 0.0
        return 0.0
    bp_id, activity, out_qty = bp
    out_qty = out_qty or 1
    mats = recipes.bp_materials.get((bp_id, activity))
    if not mats:
        time_memo[type_id] = 0.0
        return 0.0
    te_fallback = opts.get("te_factor", 1.0)
    te = (opts.get("te_factor_reaction", te_fallback) if activity == REACTION
          else opts.get("te_factor_mfg", te_fallback))
    # JE-ITEM-TE (Sitzung 9, Simurgh): die Struktur wird pro STUFE gewaehlt,
    # der Pauschalwert oben stammt aber aus der Komponenten-Struktur. Steht
    # fuer dieses Item ein eigener Faktor in opts["te_by_tid"], gilt der.
    te = (opts.get("te_by_tid") or {}).get(type_id, te)
    base_t = (recipes.activity_time.get((bp_id, activity), 0) or 0) * te
    own_per_unit = base_t / out_qty if out_qty else base_t

    visiting.add(type_id)
    sub = 0.0
    _never = opts.get("never_build") or set()
    for m, base_qty in mats:
        # Nur selbst gebaute Sub-Materialien kosten zusätzlich Bauzeit. Die
        # Bau-vs-Kauf-Entscheidung ist EXAKT dieselbe Regel wie in build_cost
        # (vorher wurden never_build und force_build hier ignoriert: Items auf
        # der Blacklist zählten mit Bauzeit, obwohl sie laut Plan GEKAUFT
        # werden - Zeit überschätzt; und mit "Alles selbst bauen" fehlten
        # teurere erzwungene Eigenbauten - Zeit unterschätzt).
        b_cost = build_cost(m, price_fn, recipes, dict(opts, force_build=False), cost_memo)
        p = price_fn(m)
        is_reaction = m in recipes.reaction_products
        build_it = (b_cost is not None and m not in _never and (
            (is_reaction and opts.get("build_reactions", True))
            or opts.get("force_build")
            or p is None
            or b_cost < p))
        if build_it:
            per = base_qty / out_qty     # Sub-Menge je 1 Endprodukt-Stück
            sub += build_time_per_unit(m, price_fn, recipes, opts,
                                       time_memo, cost_memo, visiting, depth + 1) * per
    visiting.discard(type_id)
    total = own_per_unit + sub
    time_memo[type_id] = total
    return total


def alle_items_der_kette(type_id, recipes, max_depth=12):
    """JEDES Item, das im Rezeptbaum von `type_id` vorkommt - unabhängig
    davon, ob der Plan es kauft oder baut.

    WARUM ES DIESE FUNKTION GIBT (Nutzer-Befund Sitzung 14: "der runplaner
    zeigt immer dasselbe egal was man in der Fertigungsschleife ankreuzt").
    Die Item-Liste, aus der `never_build` gebildet wird, entstand bisher aus
    `build_tree` - und dort haengt ein Teilbaum an der Kauf/Bau-Entscheidung:
    `if decision == "build" and depth + 1 < tree_depth`. Bei "buy" ist
    `subtree` None. IM CONTAINER GEMESSEN: wird ein Zwischenprodukt gekauft,
    fehlen SEINE Materialien komplett in der Liste (Kette 100 -> 201 -> 301
    -> 401: gebaut ergab {201,301,401}, gekauft nur {201}).

    Die Folge war ein Kreis: Item wird gekauft -> kein Teilbaum -> seine
    Materialien nicht in der Liste -> nie auf "never_build" geprueft ->
    werden gebaut, egal was der Nutzer ankreuzt. Das Ergebnis entschied damit
    ueber seine eigene Eingabe.

    Diese Funktion beantwortet die reine Struktur-Frage "was kommt in dieser
    Kette ueberhaupt vor" - ohne jede Bewertung. Genau das braucht die
    Ausschluss-Rechnung als Eingabe.

    Blaetter (Rohstoffe ohne Rezept) sind ENTHALTEN: auch fuer sie gibt es
    Kategorien, und ein fehlendes Item waere wieder eines, das keine
    Einstellung erreichen kann.
    """
    raus = set()
    gesehen = set()

    def _geh(tid, tiefe):
        if tiefe > max_depth or tid in gesehen:
            return
        gesehen.add(tid)
        bp = recipes.product_to_bp.get(tid)
        if not bp:
            return                      # Rohstoff - selbst schon aufgenommen
        mats = recipes.bp_materials.get((bp[0], bp[1])) or []
        for mtid, _q in mats:
            raus.add(mtid)
            _geh(mtid, tiefe + 1)

    _geh(type_id, 0)
    return raus


def build_tree(type_id, price_fn, recipes: Recipes, opts: dict,
               memo=None, visiting=None, depth=0):
    """Like build_cost, but returns the full build-vs-buy decision tree for the
    detail view. Node:
      {type_id, activity, output_qty, per_unit, material_per_unit,
       invention_per_unit, components:[{type_id, qty, decision, unit_cost,
       buy_price, build_cost, subtree}]}
    `opts["force_build"]` = build every component that CAN be built (ignore price).
    `opts["tree_depth"]` limits how deep sub-trees are expanded (default 4)."""
    import math
    if memo is None:
        memo = {}
    if visiting is None:
        visiting = set()
    if type_id in visiting or depth > opts.get("max_depth", 12):
        return None
    bp = recipes.product_to_bp.get(type_id)
    if not bp:
        return None
    bp_id, activity, prod_qty = bp
    mats = recipes.bp_materials.get((bp_id, activity))
    if not mats:
        return None

    me_map = opts.get("me_map")
    if type_id == BUENDEL_ID:
        me = 0.0                     # Buendel: Stueckzahlen sind exakt, kein ME
    elif activity == MANUFACTURING:
        inv_me = _invention_me_pct(bp_id, recipes, opts)
        if inv_me is not None:
            rig_me = (opts.get("rig_me_map") or {}).get(type_id, 0) or 0
            me_pct = me_invented_pct(inv_me, rig_me,
                                     (opts.get("ec_me_map") or {}).get(type_id, 0) or 0)
        else:
            me_pct = (me_map.get(type_id) if me_map and type_id in me_map
                      else opts.get("me", 0))
        me = (me_pct or 0) / 100.0
    elif activity == REACTION:
        rmap = opts.get("me_map_reaction")
        me_pct = (rmap.get(type_id) if rmap and type_id in rmap
                  else (opts.get("me_reaction", 0) or 0))
        me = (me_pct or 0) / 100.0
    else:
        me = 0.0
    force = opts.get("force_build", False)
    tree_depth = opts.get("tree_depth", 4)
    excluded = opts.get("excluded") or set()
    visiting.add(type_id)
    comps = []
    total = 0.0
    ok = True
    _adj = opts.get("adjusted_prices") or {}

    def _buy(tid):
        p = price_fn(tid)
        if p is not None and p > 0:
            return p
        a = _adj.get(tid)                 # kein Marktpreis → Adjusted (wie im Plan)
        return a if (a and a > 0) else None
    for mat_id, qty in mats:
        # WICHTIG (korrigiert): CCP rundet NICHT pro Run auf, sondern EINMAL
        # auf die Summe des GESAMTEN Jobs (offizielle Doku, Material-
        # Efficiency-Research-Artikel: "Material Efficiency calculations are
        # applied to the whole job, not individual runs [...] rounded up to
        # the next significant digit, meaning 14.4 Tritanium for 10 items
        # rounds to 15" - NICHT 10× einzeln aufgerundet). qty bleibt hier
        # deshalb ein durchgehender Float pro Run; die eine, korrekte
        # Aufrundung passiert in add_node() (main_window.py), NACHDEM mit der
        # Run-Zahl des Eltern-Jobs multipliziert wurde - nicht hier vorher.
        qeff = qty * (1 - me)
        if mat_id in excluded:
            comps.append({"type_id": mat_id, "qty": qeff, "decision": "owned",
                          "unit_cost": 0.0, "buy_price": None, "build_cost": None,
                          "subtree": None})
            continue
        rc = build_cost(mat_id, price_fn, recipes, opts, memo, visiting, depth + 1)
        buy = _buy(mat_id)
        is_reaction = mat_id in recipes.reaction_products
        _never = opts.get("never_build") or set()
        buildable = rc is not None and mat_id not in _never
        # Bau-vs-Kauf-Entscheidung -- IDENTISCH zu production_plan(), damit
        # Rezept-Struktur und Runplaner nie widersprechen:
        #  - Reaktion + build_reactions=False  -> kaufen
        #  - sonst bauen, wenn: force ODER kein Kaufpreis ODER Bauen <= Kaufen
        # (Früher wurden Reaktionen IMMER gebaut -> das war der Widerspruch.)
        # reaction_min (Boden-Modus): Reaktionen NICHT hart abschalten,
        # sondern wie alles andere per "billiger gewinnt" entscheiden -
        # deckungsgleich mit build_cost, das bei build_reactions=False
        # ohnehin das Minimum nimmt (nur das ERZWINGEN fällt weg). Ohne
        # dieses Flag bleibt das bisherige production_plan-Verhalten
        # (False = Reaktionen immer kaufen) unverändert.
        react_off = (is_reaction and not opts.get("build_reactions", True)
                     and not opts.get("reaction_min"))
        if buildable and not react_off and (force or buy is None or rc <= buy):
            unit = rc
            decision = "build"
        elif buy is not None:
            unit = buy
            decision = "buy"
        elif rc is not None and not react_off:
            unit = rc
            decision = "build"
        else:
            ok = False
            break
        sub = None
        if decision == "build" and depth + 1 < tree_depth:
            sub = build_tree(mat_id, price_fn, recipes, opts, memo, visiting, depth + 1)
        comps.append({"type_id": mat_id, "qty": qeff, "decision": decision,
                      "unit_cost": unit, "buy_price": buy, "build_cost": rc,
                      "subtree": sub})
        total += unit * qeff
    visiting.discard(type_id)
    if not ok:
        return None

    jc = (0.0 if type_id == BUENDEL_ID
          else _job_cost(mats, activity, prod_qty, opts, type_id=type_id))
    if jc is not None:
        run_cost = total + jc
    else:
        run_cost = total * (1 + opts.get("job_pct", 0) / 100.0)
    mat_per_unit = run_cost / prod_qty if prod_qty else run_cost
    inv_per_unit = 0.0
    if activity == MANUFACTURING and opts.get("invention", True):
        inv = recipes.invention_for_bpc.get(bp_id)
        if inv:
            _t1_bp, runs, prob, datacores = inv
            dc_cost = sum((price_fn(dc_id) or 0) * dc_qty for dc_id, dc_qty in datacores)
            # Parität zu build_cost (dort seit dem T2-Boden-Fix vorhanden,
            # hier fehlte es - die Detailansicht zeigte sonst höhere
            # Invention-Kosten als der Scan): per-Item-Decryptor +
            # Skill-Modifier.
            per_item_dv = (opts.get("inv_decryptor_map") or {}).get(bp_id)
            if per_item_dv is not None:
                prob *= per_item_dv[0]
                runs += per_item_dv[1]
                dcy = per_item_dv[4]
            else:
                prob *= opts.get("inv_prob_mult", 1.0)
                runs += opts.get("inv_run_mod", 0)
                dcy = opts.get("inv_decryptor_id")
            prob = min(1.0, prob * (opts.get("inv_skill_modifier") or {}).get(bp_id, 1.0))
            if dcy:
                dc_cost += (price_fn(dcy) or 0)
            if prob > 0:
                inv_per_unit = (dc_cost / prob) / max(1, runs * prod_qty)
    return {"type_id": type_id, "activity": activity, "output_qty": prod_qty,
            "per_unit": mat_per_unit + inv_per_unit, "material_per_unit": mat_per_unit,
            "invention_per_unit": inv_per_unit, "components": comps}


def material_menge(base_qty, runs, me):
    """Materialmenge fuer `runs` Runs eines Items - SICHER gegen die Aufteilung
    in mehrere Jobs. EINE Wahrheit fuer Plan, Einkaufsliste und Anzeige.

    NUTZER-VORFALL (Sitzung 13, Screenshot Vanadium Hafnite): eingekauft nach
    Plan, und im Industry-Fenster stand beim letzten Job "195 / 196" - EIN
    Stueck zu wenig. Sein Satz: "mir passiert es oft, dass ich nicht genuegend
    Materialien bekomme vom Einkaufsfenster".

    URSACHE, GEMESSEN: CCP rundet den ME-Abzug EINMAL auf den ganzen JOB auf
    (offizielle Regel, s. recipe_tree). Der Plan rechnete deshalb
    `ceil(base * ALLE_runs * me)` - also so, als liefe alles in EINEM Job.
    Der Runplaner verteilt dieselben Runs aber auf mehrere Slots/Charaktere
    (`schedule_build`), und JEDER dieser Jobs rundet fuer sich auf. Sobald
    `base * me` keine ganze Zahl ist, kostet jede zusaetzliche Aufteilung bis
    zu 1 Stueck mehr; die Luecke ist (Anzahl Jobs - 1) je Material.
    Gemessen: 8 Runs, ME 2,2 %, 4 Jobs -> Plan kaufte 783, EVE brauchte 784.

    WARUM PRO RUN GERUNDET WIRD (REGEL 3, Nutzer woertlich: "in jedem fall
    gilt immer, lieber zu viel als zu wenig" / "lieber bisschen mehr
    einkaufen als zu wenig"): wie viele Jobs es am Ende werden, steht beim
    Planen noch nicht fest - es haengt an den angekreuzten Charakteren, den
    freien Slots und den Blaupausen-Kopien, und der Nutzer kann ingame
    anders aufteilen als geplant. Die Rundung PRO RUN ist der schlechteste
    Fall (jeder Run ein eigener Job) und damit die einzige Menge, die bei
    JEDER Aufteilung reicht. Beweis: ceil(base*r*me) <= r*ceil(base*me) fuer
    ganzzahliges r >= 1, also ist die Summe ueber beliebig viele Jobs nie
    groesser als diese Zahl.

    PREIS DAFUER (ehrlich): wer alle Runs doch in EINEM Job faehrt, kauft bis
    zu (runs - 1) Stueck je Material zu viel. Bei grossen Grundmengen ist das
    unter 1 %; bei kleinen Grundmengen faellt es staerker ins Gewicht. Das
    ist bewusst so gewaehlt - Material uebrig kostet einmal ISK, ein Job der
    nicht startet kostet einen Abend.

    base_qty: Grundmenge je Run laut Rezept
    runs:     Anzahl Runs dieses Items
    me:       ME-FAKTOR (0.978 = 2,2 % Abzug), NICHT die Prozentzahl
    """
    import math
    r = int(runs or 0)
    if r < 1:
        return 0
    pro_run = int(math.ceil(float(base_qty) * float(me) - 1e-9))
    return max(1, pro_run) * r


def plan_mats_pro_run(plan, tid):
    """Zutaten JE RUN eines Bau-Items, abgeleitet aus dem PLAN - fuer Anzeigen,
    die nur einen Teil der Runs zeigen (Runplaner-Baum je Charakter, "Selber
    aufteilen"). Liefert [(material_id, menge_je_run)] oder None, wenn der Plan
    das Item nicht baut oder keine build_mats mitfuehrt (alte Schnappschuesse).

    WARUM NICHT SELBST RECHNEN (Sitzung 13): der Runplaner-Baum rechnete die
    Zutaten mit einem globalen ME nach und setzte ihn bei Reaktionen auf
    1,0 - er zeigte 1'000 Vanadium, der Materialien-Reiter 980, EVE
    verlangt 980. Zwei Zahlen fuer dieselbe Sache. Nutzer: "es muss einfach
    stimmen am Ende". Jetzt kommt die Zahl aus build_mats, also aus DERSELBEN
    Rechnung wie die Einkaufsliste.

    Die Teilung ist exakt, weil material_menge PRO RUN rundet und
    build_mats[tid] = je_run x build_runs[tid] ist. Fuer aeltere Plaene, die
    noch einmal auf die Summe gerundet haben, wird AUFgerundet (Regel 3) -
    lieber ein Stueck zu viel anzeigen als zu wenig.
    """
    bm = (plan or {}).get("build_mats") or {}
    br = (plan or {}).get("build_runs") or {}
    runs = int(br.get(tid, 0) or 0)
    mats = bm.get(tid)
    if not mats or runs < 1:
        return None
    return [(m, -(-int(q) // runs)) for m, q in mats]


def full_build_chain(type_id, units, recipes: Recipes, opts: dict,
                     max_depth: int = 20) -> dict:
    """Reiner Struktur-Durchlauf des Rezeptbaums, OHNE jede Kauf/Bau-
    Preisentscheidung - jedes Item mit eigener Blaupause/Reaktionsformel wird
    bedingungslos "gebaut" angenommen, komplett unabhängig von Preisen oder ob
    Unterpreise fehlen. Anders als production_plan(force_build=True): dort kann
    ein Item trotz force_build noch als "kaufen" enden (z.B. wenn ein
    Unter-Material weder bau- noch bepreisbar ist - eine Sicherheitsbremse, die
    dort bewusst Vorrang vor "force" hat). Für Referenz-Ansichten wie den
    Blueprints-Tab gedacht, wo man die KOMPLETTE Rezept-Kette von den ersten
    Reaktionen bis zum Endprodukt sehen will, nicht die kostenoptimierte
    Teilmenge.
    Returns: {type_id: runs} für jedes Item, das in der Kette gebaut würde."""
    import math
    build_runs: dict = {}
    me_map = opts.get("me_map") or {}
    me_map_reaction = opts.get("me_map_reaction") or {}

    # FERTIGUNGSTIEFE BEACHTEN (Nutzer: "wenn im Rezept-Baum auf 'nur
    # Endprodukt' geschaltet wird, sollen die nicht gebrauchten Blaupausen
    # verschwinden"). `never_build` ist genau diese Auswahl - dieselbe Quelle,
    # aus der auch production_plan seine Entscheidung zieht. Vorher lief
    # full_build_chain bedingungslos durch die ganze Kette, und der
    # Blueprints-Tab zeigte Blaupausen fuer Stufen, die der Plan gar nicht
    # baut. Das Endprodukt bleibt IMMER drin, auch wenn es in der Liste steht -
    # ohne das waere die Tabelle leer.
    _never = opts.get("never_build") or set()

    def recurse(tid, demand, depth):
        if demand <= 1e-9 or depth > max_depth:
            return
        if tid in _never and depth > 0:
            return                      # diese Stufe wird gekauft, nicht gebaut
        bp = recipes.product_to_bp.get(tid)
        if not bp:
            return                      # kein Rezept -> Blatt (Rohstoff), Ende
        bp_id, activity, out_qty = bp
        mats = recipes.bp_materials.get((bp_id, activity))
        if not mats or not out_qty:
            return
        runs = int(math.ceil(demand / out_qty))
        build_runs[tid] = build_runs.get(tid, 0) + runs
        if activity == REACTION:
            me_pct = (me_map_reaction.get(tid) if tid in me_map_reaction
                     else (opts.get("me_reaction", 0) or 0))
        else:
            me_pct = me_map.get(tid) if tid in me_map else (opts.get("me", 0) or 0)
        me = (me_pct or 0) / 100.0
        for m, base_qty in mats:
            jq = material_menge(base_qty, runs, me)
            recurse(m, jq, depth + 1)

    recurse(type_id, units, 0)
    return build_runs


def plan_materials(jobs, price_fn, recipes: Recipes, opts: dict, stocks=None):
    """Aggregate the full build tree across several jobs, subtracting stock.
    jobs = [(type_id, units)] – how many finished units of each you want.
    stocks = {type_id: available qty} – what you already have; consumed greedily
    at the level it applies, so having an intermediate part cuts BOTH that build
    and its sub-materials.
    Returns {to_buy:{tid:qty}, to_build:{tid:qty}, buy_cost, end:{tid:units},
             used:{tid:qty}} (used = how much stock was consumed)."""
    from collections import defaultdict
    to_buy = defaultdict(float)
    to_build = defaultdict(float)
    end = defaultdict(float)
    used = defaultdict(float)
    have = dict(stocks or {})          # remaining stock, consumed as we go
    memo = {}
    topts = dict(opts)
    topts["tree_depth"] = 99          # fully expand; max_depth still caps recursion

    def take_stock(tid, need):
        avail = have.get(tid, 0)
        if avail <= 0 or need <= 0:
            return need
        u = min(avail, need)
        have[tid] = avail - u
        used[tid] += u
        return need - u

    def walk(node, mult):
        for c in node["components"]:
            need = take_stock(c["type_id"], c["qty"] * mult)
            if need <= 0:
                continue
            if c["decision"] == "build" and c.get("subtree"):
                to_build[c["type_id"]] += need
                walk(c["subtree"], need)      # nur den Rest bauen → weniger Sub-Material
            else:
                to_buy[c["type_id"]] += need

    for tid, units in jobs:
        if units <= 0:
            continue
        tree = build_tree(tid, price_fn, recipes, topts, memo)
        if not tree:
            continue
        end[tid] += units
        walk(tree, units)
    buy_cost = sum((price_fn(t) or 0) * q for t, q in to_buy.items())
    te_fallback = opts.get("te_factor", 1.0)
    te_mfg = opts.get("te_factor_mfg", te_fallback)
    te_reaction = opts.get("te_factor_reaction", te_fallback)
    runs = {}
    times = {}                 # tid -> Gesamt-Jobzeit (s) über alle Runs
    cat_time = {"reaction": 0.0, "component": 0.0, "end": 0.0}
    cat_jobs = {"reaction": 0, "component": 0, "end": 0}
    end_ids = set(end)
    for tid, q in list(to_build.items()) + list(end.items()):
        bp = recipes.product_to_bp.get(tid)
        if not bp:
            continue
        bp_id, act, oq = bp
        oq = oq or 1
        rr = int(-(-q // oq))
        if tid in to_build:
            runs[tid] = rr
        base_t = recipes.activity_time.get((bp_id, act), 0) or 0
        te = te_reaction if act == REACTION else te_mfg
        # Gleiche Je-Item-Ueberschreibung wie in build_time (Sitzung 9).
        te = (opts.get("te_by_tid") or {}).get(tid, te)
        t = base_t * rr * te
        times[tid] = t
        if tid in end_ids:
            cat_time["end"] += t; cat_jobs["end"] += rr
        elif tid in recipes.reaction_products:
            cat_time["reaction"] += t; cat_jobs["reaction"] += rr
        else:
            cat_time["component"] += t; cat_jobs["component"] += rr
    total_time = sum(times.values())
    return {"to_buy": dict(to_buy), "to_build": dict(to_build),
            "buy_cost": buy_cost, "end": dict(end), "used": dict(used), "runs": runs,
            "times": times, "cat_time": cat_time, "cat_jobs": cat_jobs,
            "total_time": total_time}


def science_job_fee(eiv_run, runs, cost_index, structure_bonus=0.0,
                    facility_tax=0.0):
    """Jobgebuehr fuer Wissenschafts-Aktivitaeten (Invention UND Kopieren)
    nach der EVE-Formel - per EVE-Ref-Beispiel ISK-genau verifiziert
    (Sitzung 9, docs.everef.net/api/industry-cost):
      Basis   = EIV x 0.02          (EIV skaliert mit den Runs;
                                     Fertigung nutzt EIV OHNE die 0.02)
      Gebuehr = Basis x Index x (1 + Strukturbonus)
              + Basis x Facility-Tax + Basis x 0.04 (SCC-Surcharge)
    GOLDENE KONTROLLZAHLEN (EVE-Ref Invention, 10 Runs, EIV 16'852'252,
    Index 0.1171, Raitaru -3%, Tax 0.5%): Basis 337'045 - Index-Anteil
    39'468 - Bonus -1'184 - Tax 1'685 - SCC 13'482 - GESAMT 53'451.
    aa204 rechnet genau diese Zahlen nach."""
    base = 0.02 * float(eiv_run or 0.0) * float(runs or 0.0)
    if base <= 0:
        return 0.0
    idx_part = base * float(cost_index or 0.0)
    idx_part += idx_part * float(structure_bonus or 0.0)
    return idx_part + base * (float(facility_tax or 0.0) + 0.04)


def _inv_cost(bp_id, runs, recipes, price_fn, opts, mats_out=None):
    """Invention-Kosten (Datacores + Decryptor) für `runs` Fertigungs-Runs -
    auf Basis der ≥75%-Sicherheits-Versuchszahl (wie im Invention-Tab
    angezeigt), NICHT mehr des reinen Wahrscheinlichkeits-Erwartungswerts
    (der bei Pech oft zu wenige Versuche unterstellt). Ein manueller
    Versuchs-Override aus dem Invention-Tab (opts['inv_manual_attempts'])
    hat Vorrang, falls der Nutzer dort selbst eine Zahl vorgibt. Items, die
    der Nutzer explizit als "Eigene BPC" markiert hat (bereits im Besitz oder
    wird gekauft statt erfunden - opts['inv_manual_override'][bp_id]),
    kosten hier 0 - keine Invention nötig."""
    if bp_id in (opts.get("inv_manual_override") or {}):
        return 0.0
    if not opts.get("invention", True):
        return 0.0
    inv = recipes.invention_for_bpc.get(bp_id)
    if not inv:
        return 0.0
    adj = opts.get("adjusted_prices") or {}

    def _p(t):                                 # Markt-Preis, sonst Adjusted-Price
        v = price_fn(t)
        if v is not None and v > 0:
            return v
        return adj.get(t, 0.0) or 0.0
    _t1, inv_runs, prob, datacores = inv
    # Offizielle EVE-Formel: SkillModifier VOR dem Decryptor auf die Basis-
    # Erfolgschance anwenden (opts["inv_skill_modifier"][bp_id], vom
    # Invention-Tab/UI berechnet - 1.0, wenn keine Skill-Daten vorhanden).
    prob = min(1.0, prob * (opts.get("inv_skill_modifier") or {}).get(bp_id, 1.0))
    dc = sum(_p(d) * q for d, q in datacores)
    # Per-Item-Decryptor (aus dem Invention-Tab, opts["inv_decryptor_map"]) hat
    # Vorrang vor dem einen globalen Decryptor-Setting - so kann jedes Item
    # seinen eigenen Decryptor nutzen statt nur EINEN für den ganzen Bauplan.
    per_item = (opts.get("inv_decryptor_map") or {}).get(bp_id)
    if per_item is not None:
        prob_mult, run_mod, _me_mod, _te_mod, dcy = per_item
    else:
        prob_mult = opts.get("inv_prob_mult", 1.0)
        run_mod = opts.get("inv_run_mod", 0)
        dcy = opts.get("inv_decryptor_id")
    prob *= prob_mult
    inv_runs += run_mod
    if dcy:
        dc += _p(dcy)
    if prob <= 0 or inv_runs <= 0:
        return 0.0
    manual = (opts.get("inv_manual_attempts") or {}).get(bp_id)
    if manual is not None:
        attempts = max(0.0, float(manual))
    else:
        # Bereits per ESI geladene, vorhandene BPCs (opts["inv_owned_runs"])
        # decken einen Teil der benötigten Runs schon ab - nur der REST muss
        # noch neu erfunden werden.
        owned = (opts.get("inv_owned_runs") or {}).get(bp_id, 0) or 0
        remaining = max(0, int(runs or 0) - int(owned))
        successes_needed = -(-remaining // inv_runs)   # aufrunden
        confidence = opts.get("inv_confidence", DEFAULT_INVENTION_CONFIDENCE)
        attempts = invention_attempts_for_confidence(successes_needed, prob, confidence) or 0
    # MENGEN MELDEN (optional): Datacores und Decryptor sind echtes Material,
    # das man einkaufen muss - bisher tauchten sie NUR als Geldbetrag auf und
    # standen deshalb auf keiner Einkaufsliste. `mats_out` ist derselbe
    # Ausgabe-Kanal wie `parts_memo` bei build_cost: die Rechnung meldet ihre
    # Mengen SELBST, statt sie anderswo nachzubauen (Arbeitsregel 9).
    # ACHTUNG: die KOSTEN bleiben hier (Rueckgabewert). Wer die Mengen
    # zusaetzlich als Material verbucht, darf sie NICHT noch einmal bepreisen.
    if mats_out is not None and attempts > 0:
        _n = int(-(-float(attempts) // 1))      # angefangener Versuch zaehlt
        for _d, _q in datacores:
            mats_out[_d] = mats_out.get(_d, 0) + _n * int(_q)
        if dcy:
            mats_out[dcy] = mats_out.get(dcy, 0) + _n
    # JOBGEBUEHREN Kopieren + Invention (Sitzung 9, Formel oben in
    # science_job_fee verifiziert). Beide Aktivitaeten skalieren mit der
    # Versuchszahl: 1 Invention-Versuch verbraucht 1 T1-Kopie-Run, also
    # laufen auch genau `attempts` Kopie-Runs. EIV je Run: Invention nutzt
    # die Fertigungs-EIV des T2-PRODUKTS (per EVE-Ref-Sin-Beispiel
    # rueckgerechnet, Abweichung < 0,001%), Kopieren die des T1-Produkts.
    # v1-GRENZE (dokumentiert): als Science-System gilt das BAU-System des
    # Plans (opts["sci_index_*"], vom Dialog aus esi.system_cost_indices()
    # gefuellt); Struktur-Bonus/-Steuer der Science-Struktur sind 0, solange
    # das Tool keine eigene Science-Struktur-Wahl kennt. Fehlen die Indizes
    # (aeltere Aufrufer), bleibt alles beim alten Verhalten.
    fee = 0.0
    _idx_inv = opts.get("sci_index_invention")
    _idx_cp = opts.get("sci_index_copying")
    if attempts > 0 and (_idx_inv is not None or _idx_cp is not None):
        def _eiv_run(_bpid):
            _m = recipes.bp_materials.get((_bpid, MANUFACTURING)) or []
            return sum(_q * (adj.get(_t, 0) or 0) for _t, _q in _m)
        _sb = float(opts.get("sci_structure_bonus", 0.0) or 0.0)
        _sx = float(opts.get("sci_facility_tax", 0.0) or 0.0)
        if _idx_inv is not None:
            fee += science_job_fee(_eiv_run(bp_id), attempts,
                                   _idx_inv, _sb, _sx)
        if _idx_cp is not None:
            fee += science_job_fee(_eiv_run(_t1), attempts,
                                   _idx_cp, _sb, _sx)
    return attempts * dc + fee


def production_plan(type_id, units, price_fn, recipes: Recipes, opts: dict):
    """Aggregated build/buy plan with per-quantity decisions. For each item the plan
    compares — at its AGGREGATE demand — the batch-rounded build cost vs simply buying
    it, and picks the cheaper (unless force). So at 1 unit, batch reactions are bought
    (cheap); at scale they are built once (shared, surplus counted once) and the
    per-unit cost falls. Never exceeds the buy price.
    Returns {total_cost, buy:{tid:qty}, build_runs:{tid:runs}, build_seq:[(tid,runs)],
             surplus:{tid:overproduced}}."""
    import math
    from collections import defaultdict, deque
    me_factor = 1 - opts.get("me", 0) / 100.0
    me_factor_reaction = 1 - (opts.get("me_reaction", 0) or 0) / 100.0
    me_map = opts.get("me_map") or {}
    me_map_reaction = opts.get("me_map_reaction") or {}

    # MULTI-BAUPLAN: die direkten Zutaten des Buendels sind Endprodukte -
    # sie werden wie DAS Endprodukt behandelt (immer bauen, kein Bestand,
    # keine Blacklist). Ohne Buendel ist die Menge leer und nichts aendert sich.
    _enden = set(buendel_enden(recipes)) if type_id == BUENDEL_ID else set()

    def _ist_ende(tid):
        return tid == type_id or tid in _enden

    def _me_of(tid, activity):
        """ME-Faktor pro Item: Rig wirkt nur auf die passende Item-Domäne (me_map),
        sonst der pauschale Wert (Blueprint-ME ohne passenden Rig). Für invented
        T2-Items gilt die ECHTE Invention-ME (2% Basis + Decryptor-Bonus) statt
        der Kategorie-/Blueprint-Annahme - siehe _invention_me_pct."""
        if tid == BUENDEL_ID:
            return 1.0                  # Buendel: Stueckzahlen exakt, kein ME
        if activity == MANUFACTURING:
            bp = recipes.product_to_bp.get(tid)
            inv_me = _invention_me_pct(bp[0], recipes, opts) if bp else None
            if inv_me is not None:
                rig_me = (opts.get("rig_me_map") or {}).get(tid, 0) or 0
                pct = me_invented_pct(inv_me, rig_me,
                                      (opts.get("ec_me_map") or {}).get(tid, 0) or 0)
            else:
                pct = me_map.get(tid, opts.get("me", 0))
            return 1 - (pct or 0) / 100.0
        if activity == REACTION:
            pct = me_map_reaction.get(tid, (opts.get("me_reaction", 0) or 0))
            return 1 - (pct or 0) / 100.0
        return 1.0

    force = opts.get("force_build", False)
    maxd = opts.get("max_depth", 12)
    never = opts.get("never_build") or set()
    excluded = opts.get("excluded") or set()   # „hab ich schon“ → ganz aus dem Plan
    stock = dict(opts.get("stock") or {})      # {tid: qty} vorhandene Assets → abziehen
    stock_used = {}
    marg_opts = dict(opts); marg_opts["force_build"] = False

    eff_memo = {}
    adj_prices = opts.get("adjusted_prices") or {}

    def buy_price_src(tid):
        """(Preis, aus_Rueckfall) - EINE Stelle entscheidet, woher der Preis
        kommt. `buy_price_of` ist nur die Kurzform davon, damit der Rueckfall-
        Anteil unten nicht ein zweites Mal (und womoeglich anders) abgeleitet
        werden muss."""
        p = price_fn(tid)
        if p is not None and p > 0:
            return p, False
        a = adj_prices.get(tid)
        return (a, True) if (a and a > 0) else (None, False)

    def buy_price_of(tid):
        """Kaufpreis: Sell-Order-Preis, sonst Fallback auf den Adjusted-Price (ESI),
        damit Items ohne Marktpreis nicht als gratis (0) gerechnet werden."""
        return buy_price_src(tid)[0]

    _stock_pfn = opts.get("stock_price_fn")

    def stock_price_of(tid):
        """Bewertung des VERBRAUCHTEN Bestands.

        Standard: derselbe Kaufpreis wie fuer Zukaeufe. Ist eine eigene
        Preisfunktion gesetzt, gilt die - der Dialog uebergibt dort den Preis
        OHNE Frachtaufschlag. Grund (Nutzer-Klarstellung): der Frachtdienst
        transportiert NUR, was auf der Einkaufsliste steht. Material, das
        bereits am Bau-Ort liegt, verursacht keine Fracht - es mit dem
        Landepreis zu bewerten waere zu hoch.
        Der Adjusted-Price-Fallback bleibt identisch, damit Items ohne
        Marktpreis auch hier nicht als gratis durchrutschen.
        """
        # WAS KOSTET DICH DAS ITEM WIRKLICH? Der guenstigere der beiden Wege:
        # kaufen ODER selbst bauen. Ein selbst reagiertes Zwischenprodukt zum
        # MARKTPREIS zu bewerten rechnet die Marge fremder Produzenten in die
        # eigenen Kosten - genau dadurch verdoppelten sich beim Nutzer die
        # Baukosten (42 -> 64 Mio/Stk), sobald eine Reaktions-Struktur voller
        # Zwischenprodukte dazukam. `eff()` ist dieselbe Groesse, mit der der
        # Plan auch kaufen-oder-bauen entscheidet.
        _mk = buy_price_of(tid) if _stock_pfn is None else _stock_pfn(tid)
        if _mk is not None and _mk <= 0:
            _mk = None
        try:
            _bw = eff(tid)
        except Exception:
            _bw = None
        if _bw is not None and _bw > 0:
            return min(_mk, _bw) if _mk else _bw
        if _mk is not None:
            return _mk
        if _stock_pfn is None:
            return buy_price_of(tid)
        p = _stock_pfn(tid)
        if p is not None and p > 0:
            return p
        a = adj_prices.get(tid)
        return a if (a and a > 0) else None

    def eff(tid):
        if tid in eff_memo:
            return eff_memo[tid]
        b = build_cost(tid, price_fn, recipes, marg_opts)
        p = buy_price_of(tid)
        cands = [x for x in (b, p) if x is not None]
        v = min(cands) if cands else None
        eff_memo[tid] = v
        return v

    recipe_of = {}
    depth_of = {}
    buildable = {}
    nicht_kaufbar = set()   # Items OHNE echte Sell-Order am Hub. Der Preis
                            # stammt dann aus dem ESI-Adjusted-Price - eine
                            # Schaetzung, keine Kaufoption. Wird gemeldet,
                            # damit die Rezept-Struktur es kennzeichnen kann
                            # (Nutzer, Sitzung 14: "aber mit vermerk dazu in
                            # Rezeptstruktur sollte etwas stehen").
    never_hit = set()   # Items, die NUR wegen "never_build" (Meine Blueprints -
                        # Kategorie nicht als besessen markiert) nicht gebaut
                        # werden - separat von der Blacklist (excluded) und
                        # "hat gar kein Rezept" getrackt, für eine genaue
                        # Fehlerursache in der UI statt nur "kaufen".

    def discover(tid, depth, path):
        depth_of[tid] = max(depth_of.get(tid, 0), depth)
        if tid in buildable:
            return
        bp = recipes.product_to_bp.get(tid)
        mats = recipes.bp_materials.get((bp[0], bp[1])) if bp else None
        # Die Enden eines Buendels kennen weder never_build noch Blacklist -
        # sie sind Endprodukte und werden gebaut. (Das EINE Endprodukt eines
        # normalen Plans bleibt hier bewusst wie bisher: bestehendes Verhalten
        # nicht mitveraendern.)
        _sperre = (tid in never or tid in excluded) and tid not in _enden
        if bp and mats and tid not in path and depth <= maxd and tid in never \
                and tid not in excluded and tid not in _enden:
            never_hit.add(tid)
        if not bp or not mats or tid in path or depth > maxd or _sperre:
            buildable[tid] = False
            return
        buildable[tid] = True
        recipe_of[tid] = (bp[0], bp[1], bp[2] or 1, mats)
        for m, _q in mats:
            discover(m, depth + 1, path | {tid})

    discover(type_id, 0, frozenset())

    consumers = defaultdict(int)
    for tid, ok in buildable.items():
        if ok:
            for m, _q in recipe_of[tid][3]:
                consumers[m] += 1

    demand = defaultdict(float); demand[type_id] = units
    decision = {}; build_runs = {}; surplus = {}; build_mats = {}
    # WIEVIEL STUECK dieser Plan selbst HERSTELLT (nicht Runs, sondern
    # Einheiten inkl. Ueberschuss). Gebraucht fuer die 🔒-Reservierung:
    # was ein Plan baut, liegt danach im Hangar und darf von einem
    # ANDEREN Plan nicht als freier Bestand gezaehlt werden (Nutzer-Fall
    # Sitzung 10: Composite aus eigenen Intermediates gebaut, zweiter
    # Plan verbaute es, erster Plan stand am Ende ohne da).
    # HIER exportiert statt in der UI nachgerechnet, damit die
    # Reservierung mit DENSELBEN Zahlen arbeitet, mit denen geplant
    # wurde (Arbeitsregel 9).
    build_made = {}
    buy = defaultdict(float)
    jc_total = 0.0; inv_total = 0.0
    jc_parts = {}          # Index/Tax/SCC, von _job_cost aufaddiert (parts_out)
    inv_mats = {}          # Datacores/Decryptoren, von _inv_cost gemeldet
    # JE ITEM (Multi-Bauplan, Kosten je Endprodukt): dieselben Zahlen, die
    # unten in jc_total/inv_total/mat_cost/stock_cost einfliessen - nur
    # nicht zusammengeworfen. Invariante: Summe der Werte == Gesamtwert.
    jc_items = {}; inv_items = {}; buy_cost_items = {}; stock_cost_items = {}
    queue = deque(t for t in buildable if consumers[t] == 0)
    processed = set()

    def build_estimate(tid, D):
        bp_id, activity, out_qty, mats = recipe_of[tid]
        runs = int(math.ceil(D / out_qty)) if D > 0 else 0
        me = _me_of(tid, activity)
        c = 0.0; eiv = []; complete = True
        for m, base_qty in mats:
            jq = material_menge(base_qty, runs, me)
            em = eff(m)
            if em is None:               # Material weder bau- noch bepreisbar
                complete = False
            c += jq * (em or 0)
            eiv.append((m, base_qty * runs))
        if tid != BUENDEL_ID:           # das Buendel ist kein Job
            c += _job_cost(eiv, activity, out_qty, opts) or 0.0
            if activity == MANUFACTURING:
                c += _inv_cost(bp_id, runs, recipes, price_fn, opts)
        # WEG A: Ruecklaeufer-Gutschrift je Run (s. build_cost, gleiche
        # Quelle recipes.unrefined) - sonst kauft der Plan X, das die Wahl
        # gerade als guenstiger befunden hat (Thulium-Hafnite-Fund).
        _uw = (getattr(recipes, "unrefined", None) or {}).get(tid)
        if _uw and runs > 0:
            c = max(0.0, c - runs * float(_uw.get("kredit_je_run") or 0.0))
        return c, runs, eiv, activity, out_qty, bp_id, complete

    while queue:
        tid = queue.popleft()
        if tid in processed or consumers[tid] > 0:
            continue
        processed.add(tid)
        if tid in excluded and not _ist_ende(tid):
            decision[tid] = "owned"          # vorhanden → raus aus dem Plan
            continue
        D = demand[tid]
        if stock and not _ist_ende(tid):
            owned = stock.get(tid, 0)
            if owned > 0:
                used = min(owned, D)
                if used > 0:
                    D -= used
                    demand[tid] = D
                    stock_used[tid] = stock_used.get(tid, 0) + used
        if D <= 1e-9:                       # nichts gebraucht → weder bauen noch kaufen
            if buildable.get(tid) and tid in recipe_of:
                for m, _q in recipe_of[tid][3]:
                    consumers[m] -= 1
                    if consumers[m] <= 0 and m not in processed:
                        queue.append(m)
            continue
        ok = buildable.get(tid, False)
        buy_price = buy_price_of(tid)
        do_build = False
        if ok:
            bcost, runs, eiv, activity, out_qty, bp_id, complete = build_estimate(tid, D)
            buy_est = (buy_price * D) if buy_price is not None else None
            if _ist_ende(tid):
                # Endprodukt wird IMMER gebaut, nie gekauft. Sonst würde bei
                # bcost > Marktpreis der Bauplan das Endprodukt „kaufen“ →
                # total_cost = Marktpreis × Menge, Baukosten/Stk konstant und
                # Gewinn exakt 0 (Sell = Baukosten). Das ist der Root-Kauf-Bug.
                do_build = True
            elif activity == REACTION and not opts.get("build_reactions", True):
                do_build = False           # Reaktionen global auf „kaufen“
            elif not complete and buy_price is not None and not force:
                # Ein Material ist weder bau- noch bepreisbar → nicht „gratis“ bauen,
                # sondern kaufen (konsistent mit dem Rezept-Baum). ABER: bei "Alles
                # selbst bauen" (force) hat das keine Ausnahme mehr - force soll
                # wirklich ALLES bauen, was baubar ist, auch wenn irgendein tief
                # verschachteltes Unter-Material gerade keinen Preis hat (dann eben
                # mit 0 ISK für den unbepreisten Teil - besser als ein Item trotz
                # "Alles selbst bauen: AN" munter zu kaufen).
                do_build = False
            else:
                # bauen nur, wenn es (inkl. günstigster Sub-Materialien) billiger ist -
                # ES SEI DENN "prefer_build_if_owned" ist an UND für dieses Item wurde
                # schon (mindestens teilweise) eigener Bestand verwendet (stock_used) -
                # dann bauen, ohne den Preis zu vergleichen (Reste/Kapazität, die man
                # eh schon hat, nicht künstlich liegen lassen, nur weil der Markt
                # gerade minimal billiger wäre). Bei Besitze=0 bleibt der normale
                # Kostenvergleich unverändert aktiv.
                _prefer_owned = bool(opts.get("prefer_build_if_owned") and
                                     stock_used.get(tid, 0) > 0)
                # AM HUB NICHT KAUFBAR -> BAUEN (Nutzer, Sitzung 14: "der
                # Bauplan will immer dass ich Ametat I kaufe,.. ja aber in
                # Jita gibts gar keine. Auch wenns da einen
                # durchschnitspreis jetzt gibt,.. sollte der Bauplan sich
                # dafuer entscheiden das zu bauen, weil ich koennte es ja
                # gar nicht kaufen").
                #
                # `buy_price_src` sagt, WOHER der Preis kommt: aus einer
                # echten Sell-Order am Hub - oder aus dem
                # ESI-Adjusted-Price als Rueckfall. Der Rueckfall war
                # richtig gedacht (Items ohne Marktpreis sollen nicht als
                # gratis durchgehen), er liess den Plan aber so tun, als
                # koenne man kaufen. Ein Preis, den niemand anbietet, ist
                # keine Kaufoption.
                #
                # SEIN FALL: Ametat I hat in Jita 4-4 keine einzige
                # Sell-Order (Verkaeufer nur in Obe VI, 10 Spruenge weg -
                # die filtert der Scanner korrekt weg, weil sie nicht an der
                # Hub-Station liegen). Dasselbe bei Solerium: "No orders
                # found".
                #
                # NUR WENN BAUBAR: ist das Item nicht baubar, bleibt es beim
                # Rueckfall - sonst rutschte es als gratis durch.
                # NICHT gegen `never_build`: dort steht oft, dass der Nutzer
                # die Blaupause GAR NICHT BESITZT. Ihm dann einen Job
                # einzuplanen, den er nicht starten kann, waere schlimmer
                # als der Kauf. Dieser Fall wird stattdessen GEMELDET
                # (`nicht_kaufbar`), damit er ihn vor dem Einkauf sieht.
                _fallback = buy_price_src(tid)[1] if buy_est is not None else False
                if _fallback or buy_est is None:
                    nicht_kaufbar.add(tid)
                do_build = (force or _prefer_owned or buy_est is None
                            or _fallback or bcost <= buy_est)
        if not do_build:
            decision[tid] = "buy"
            buy[tid] += D
            if ok:
                for m, _q in recipe_of[tid][3]:
                    consumers[m] -= 1
                    if consumers[m] <= 0 and m not in processed:
                        queue.append(m)
            continue
        decision[tid] = "build"
        build_runs[tid] = runs
        # EXAKTE Zutatenmengen DIESES Bau-Items (inkl. ME, je Job gerundet) -
        # exportiert als plan["build_mats"], damit die UI ("kann gebaut
        # werden") gegen DIESELBEN Zahlen prueft, mit denen hier geplant
        # wird, statt sie nachzubauen (Arbeitsregel 9). Nutzer-Ansage:
        # "es soll genau passen, ich will so guenstig wie moeglich bauen".
        build_mats[tid] = []
        made = runs * out_qty
        if made > 0:
            build_made[tid] = build_made.get(tid, 0) + int(made)
        if made - D > 0:
            surplus[tid] = made - D
        me = _me_of(tid, activity)
        for m, base_qty in recipe_of[tid][3]:
            jq = material_menge(base_qty, runs, me)
            build_mats[tid].append((m, jq))
            demand[m] += jq
            consumers[m] -= 1
            if consumers[m] <= 0 and m not in processed:
                queue.append(m)
        # AUFSCHLUESSELUNG (Nutzer: Index-Anteil, Facility-Tax und SCC
        # einzeln sehen): NUR an dieser Stelle mitschreiben - build_estimate
        # oben rechnet auch fuer Items, die am Ende GEKAUFT werden (reine
        # Entscheidungs-Schaetzung); dort mitzuzaehlen wuerde die Teile
        # groesser machen als die Summe.
        if tid != BUENDEL_ID:               # das Buendel ist kein Job
            _jc1 = _job_cost(eiv, activity, out_qty, opts,
                             parts_out=jc_parts, type_id=tid) or 0.0
            jc_total += _jc1
            jc_items[tid] = jc_items.get(tid, 0.0) + _jc1
            if activity == MANUFACTURING:
                _iv1 = _inv_cost(bp_id, runs, recipes, price_fn, opts,
                                 mats_out=inv_mats)
                inv_total += _iv1
                inv_items[tid] = inv_items.get(tid, 0.0) + _iv1

    # INVENTION-MATERIAL (Datacores/Decryptoren) als echter Bedarf, aufgeteilt
    # in "aus dem Bestand gedeckt" und "muss gekauft werden" - genau das
    # Muster, das jedes andere Material durchlaeuft.
    # BEWUSST EIGENE SCHLUESSEL, NICHT `buy`/`stock_used`: die KOSTEN stecken
    # bereits in `inv_cost` und damit in `total_cost`. Waeren die Mengen in
    # `buy`, wuerde `mat_cost` sie ein ZWEITES Mal bepreisen und die
    # Baukosten je Stueck stiegen ohne Grund. `total_cost` bleibt deshalb
    # unveraendert - das ist die Gegenprobe fuer diesen Umbau.
    inv_buy = {}
    inv_stock_used = {}
    for _t, _q in inv_mats.items():
        # `stock` wird oben NICHT heruntergezaehlt, `stock_used` haelt fest,
        # was die Fertigung schon verbraucht hat - also hier abziehen, sonst
        # wuerde derselbe Bestand zweimal vergeben.
        _have = int(stock.get(_t, 0) or 0) - int(stock_used.get(_t, 0) or 0)
        _use = max(0, min(int(_q), _have))
        if _use:
            inv_stock_used[_t] = _use
        _rest = int(_q) - _use
        if _rest > 0:
            inv_buy[_t] = _rest

    mat_cost = 0.0
    # Wieviel der EINGEKAUFTEN Materialkosten haengt nur am Adjusted-Price
    # (kein Angebot am Hub)? Gleiche Frage wie parts["mat_adjusted"] in
    # build_cost, hier aus DIESER Rechnung beantwortet - damit die Trefferzeile
    # des Scanners nach der genauen Nachrechnung nicht mit einem Anteil aus der
    # Schnellschaetzung danebensteht (Arbeitsregel 10).
    # NUR die Kaufseite: verbrauchter Bestand (stock_cost) wird mit
    # min(Kaufpreis, eigene Baukosten) bewertet und ist eine andere Groesse.
    mat_cost_adjusted = 0.0
    for t, q in buy.items():
        _p, _from_adj = buy_price_src(t)
        _c = (_p or 0) * q
        mat_cost += _c
        buy_cost_items[t] = _c
        if _from_adj:
            mat_cost_adjusted += _c
    # BESTAND IST NICHT GRATIS (Nutzer-Entscheid: "alles was ich habe hat
    # einmal ISK gekostet"). Frueher reduzierte vorhandenes Material nur die
    # Nachfrage und verschwand damit spurlos aus den Kosten - der Bau sah
    # dadurch billiger aus, als er ist, und der Gewinn war um den Wert des
    # verbrauchten Bestands zu hoch.
    # DIE BEGRUENDUNG IST ERSATZ, NICHT ENTGANGENER VERKAUF. Hier stand
    # frueher "Opportunitaetskosten: was hier verbaut wird, kann nicht
    # verkauft werden" - das trifft es nicht: der Nutzer verkauft
    # ausschliesslich Endprodukte, nie Zwischenprodukte. Es gibt also gar
    # keinen entgangenen Verkauf. Was der Bestand kostet, ist das, was es
    # kostet, ihn zu ERSETZEN - und zwar auf dem guenstigeren der beiden
    # offenen Wege. Genau das liefert stock_price_of() mit
    # min(Kaufpreis, eigene Baukosten); zum reinen Kaufpreis zu bewerten
    # rechnete die Marge fremder Produzenten in die eigenen Kosten (Sprung
    # 42 -> 64 Mio/Stk, sobald die Reaktions-Struktur dazukam).
    # (Ist der Frachtaufschlag aktiv, steckt er nur im Kauf-Zweig; Material,
    # das schon am Bau-Ort liegt, verursacht keine Fracht - s. _stock_pfn.)
    # opts["stock_at_market"]=False stellt das alte Verhalten wieder her.
    stock_cost = 0.0
    if opts.get("stock_at_market", True):
        stock_cost_items = {t: (stock_price_of(t) or 0) * q
                            for t, q in stock_used.items()}
        stock_cost = sum(stock_cost_items.values())
    total = mat_cost + stock_cost + jc_total + inv_total
    # DAS BUENDEL IST KEIN JOB: aus Runs, Zutaten, Herstellung und Entscheidung
    # streichen - die Endprodukte darunter bleiben als echte Jobs stehen.
    # `buendel_enden` nennt sie, damit UI und Runplaner die Stufe "Endprodukt"
    # ueber die Menge statt ueber EIN Item bestimmen koennen.
    if type_id == BUENDEL_ID:
        for _d in (build_runs, build_mats, build_made, decision, surplus, demand):
            _d.pop(BUENDEL_ID, None)
    seq = sorted(build_runs.keys(), key=lambda t: -depth_of.get(t, 0))
    build_seq = [(t, build_runs[t]) for t in seq if build_runs[t] > 0]
    # "owned" wird NUR für Blacklist-Treffer vergeben (s. oben) - daraus lässt
    # sich ableiten, welche Items in DIESEM Plan wirklich rausgefallen sind
    # (nicht nur, was auf der Blacklist STEHT, sondern was hier auch wirklich
    # gebraucht worden wäre) - für einen sichtbaren Hinweis in der UI, statt
    # dass Items einfach kommentarlos verschwinden.
    excluded_hit = {tid for tid, dec in decision.items() if dec == "owned"}
    # never_build_hit wurde nur für Items gesetzt, die TATSÄCHLICH im Baum
    # gebraucht wurden (discover() läuft nur für erreichte Items) - trotzdem
    # gegen buy/decision filtern, falls ein Item am Ende doch anders behandelt
    # wurde (z.B. Bestand hat es komplett gedeckt).
    never_build_hit = {tid for tid in never_hit if tid in buy or tid in decision}
    return {"inv_buy": inv_buy, "inv_stock_used": inv_stock_used,
            "total_cost": total, "mat_cost": mat_cost, "stock_cost": stock_cost,
            "mat_cost_adjusted": mat_cost_adjusted,
            "job_cost": jc_total,
            # Bestandteile von job_cost, ueber alle Stufen aufsummiert.
            # Invariante: index + tax + scc == job_cost (dieselbe Rechnung).
            "job_cost_parts": {k: jc_parts.get(k, 0.0)
                               for k in ("index", "tax", "scc")},
            "inv_cost": inv_total, "buy": dict(buy), "build_runs": build_runs,
            "build_made": build_made,
            "build_seq": build_seq, "surplus": surplus, "stock_used": stock_used,
            "decision": dict(decision), "build_mats": build_mats,
            "excluded_hit": excluded_hit,
            "never_build_hit": never_build_hit,
            "buendel_enden": dict(buendel_enden(recipes)) if type_id == BUENDEL_ID else {},
            # Je Item (Summe je Schluessel == job_cost / inv_cost / mat_cost /
            # stock_cost) - Eingabe fuer buendel_kosten_je_ende().
            "job_cost_items": jc_items, "inv_cost_items": inv_items,
            "buy_cost_items": buy_cost_items, "stock_cost_items": stock_cost_items,
            # NUR die Items, die am Ende auch wirklich im Plan stehen -
            # sonst meldete die Anzeige Positionen, die gar nicht vorkommen.
            "nicht_kaufbar": {t for t in nicht_kaufbar
                              if t in buy or t in decision}}



def buy_cost(sell_orders, qty):
    """Cost of buying `qty` units immediately from the sell-order book, cheapest
    first (the price you actually pay rises as you eat up the cheap orders).
    sell_orders: list of (price, volume_remaining) \u2013 wie von
    esi.fetch_type_orders(...)['sell']. Returns (cost, bought_qty). Wenn qty
    das verf\u00fcgbare Volumen \u00fcbersteigt, ist bought_qty < qty (der Rest ist am
    Hub nicht sofort kaufbar \u2013 man m\u00fcsste eine eigene Buy-Order stellen)."""
    orders = sorted(sell_orders or [], key=lambda x: x[0])   # cheapest first
    cost = 0.0
    bought = 0
    for price, avail in orders:
        if bought >= qty:
            break
        take = int(min(avail, qty - bought))
        if take < 1:
            continue
        cost += take * price
        bought += take
    return cost, bought


def refine_plan_with_ladder(plan, orderbooks, price_fn=None):
    """Verfeinert plan["buy"] (type_id -> Menge) mit ECHTEN Orderbuch-Preisen
    statt dem flachen price_fn-Wert, den production_plan() sonst nutzt.
    orderbooks: {type_id: [(price, qty), ...]} \u2013 die 'sell'-Liste aus
    esi.fetch_type_orders() je ben\u00f6tigtem Material (separater Live-Abruf pro
    Material \u2013 die SDE/der Markt-Scan-Cache haben keine echte Orderbuch-Tiefe).
    price_fn (optional): dieselbe Preisfunktion, die production_plan() f\u00fcr den
    Flachpreis nutzte \u2013 f\u00fcr den Zeilen-Vergleich Flach vs. Orderbuch je Material.
    Returns {"total_cost", "flat_cost", "delta", "delta_pct", "rows": [
    {type_id, qty, flat_unit, flat_line_cost, ladder_unit, ladder_cost, bought,
    short, has_orderbook}]} sortiert nach absoluter Kostenabweichung (die
    auff\u00e4lligsten Materialien zuerst)."""
    buy = plan.get("buy") or {}
    flat_cost = float(plan.get("total_cost", 0.0))
    rows = []
    ladder_total = 0.0
    for tid, qty in buy.items():
        q = int(round(qty))
        if q < 1:
            continue
        ob = orderbooks.get(tid) or []
        ladder_c, bought = buy_cost(ob, q)
        short = q - bought
        if short > 0 and ob:
            # Rest ist am Hub gerade nicht in dieser Menge kaufbar -> teuersten
            # bekannten Preis als konservative Sch\u00e4tzung f\u00fcr den Rest ansetzen,
            # damit "kein Orderbuch" nicht faelschlich wie "gratis" aussieht.
            worst = max(p for p, _v in ob)
            ladder_c += short * worst
        elif short > 0:
            ladder_c = float("nan")   # kein Orderbuch da -> nicht sch\u00e4tzbar
        ladder_total += ladder_c if ladder_c == ladder_c else 0.0  # NaN-sicher
        flat_unit = float(price_fn(tid)) if (price_fn and price_fn(tid) is not None) else None
        rows.append({"type_id": tid, "qty": q, "ladder_cost": ladder_c,
                     "ladder_unit": (ladder_c / q) if (q and ladder_c == ladder_c) else None,
                     "flat_unit": flat_unit,
                     "flat_line_cost": (flat_unit * q) if flat_unit is not None else None,
                     "bought": bought, "short": max(0, short),
                     "has_orderbook": bool(ob)})
    # nicht in der Kaufliste bepreiste Anteile (Job-Kosten, Invention, Endprodukt-
    # eigener Bau) bleiben vom flachen Plan \u00fcbernommen \u2013 nur der reine
    # Material-Einkauf wird durch die Ladder-Summe ersetzt.
    other_cost = flat_cost - float(plan.get("mat_cost", flat_cost))
    total_cost = ladder_total + other_cost
    rows.sort(key=lambda r: r["ladder_cost"] if r["ladder_cost"] == r["ladder_cost"]
              else -1.0, reverse=True)
    delta = total_cost - flat_cost
    return {"total_cost": total_cost, "flat_cost": flat_cost, "delta": delta,
           "delta_pct": (delta / flat_cost * 100.0) if flat_cost else 0.0,
           "rows": rows}


def ladder_cost_curve(qtys, plan_fn, orderbook_fn, price_fn=None):
    """Echte, orderbuch-basierte Baukosten \u00fcber mehrere Baumengen hinweg \u2013
    Ersatz f\u00fcr den Flachpreis-Materialeinkauf, den production_plan() sonst
    nutzt. Beantwortet: "ab welcher Baumenge wird der MATERIAL-EINKAUF am
    Markt so teuer (weil die billigen Sell-Orders aufgebraucht sind), dass
    sich das Bauen nicht mehr lohnt" \u2013 UNABH\u00c4NGIG vom Verkaufspreis des
    Endprodukts (der bleibt beim Aufrufer flach/fix, siehe Bauplan-Dialog).

    Anders als production_plan() (ein Preis pro Material, egal wie viel man
    kauft) l\u00e4uft diese Funktion pro Menge das Sell-Order-Buch JEDES ben\u00f6tigten
    Materials herunter (buy_cost()): je mehr man von einem Material braucht,
    desto teurer wird der Durchschnittspreis, weil billige Orders zuerst
    verbraucht werden.

    plan_fn(qty) -> production_plan()-Ergebnis f\u00fcr GENAU diese St\u00fcckzahl.
        Der Aufrufer bindet type_id/price_fn/recipes/opts vorher ein (z. B.
        via functools.partial oder lambda) \u2013 diese Funktion selbst kennt
        weder Recipes noch die SDE, damit sie ohne echte Bauplan-Daten
        (Mock plan_fn) testbar ist.
    orderbook_fn(type_id) -> [(price, qty_remaining), ...] Sell-Orders am
        gew\u00e4hlten Einkaufs-Hub. Wird PRO MATERIAL GENAU EINMAL aufgerufen und
        f\u00fcr ALLE qtys wiederverwendet \u2013 das Orderbuch selbst \u00e4ndert sich
        zum Berechnungszeitpunkt nicht zwischen den Kurvenpunkten, nur die
        BEN\u00d6TIGTE Menge \u00e4ndert sich. Das h\u00e4lt die Zahl der Live-Abrufe klein,
        selbst wenn die Kurve viele Mengen-Stufen hat.
    price_fn(type_id) -> Flachpreis, NUR als Fallback f\u00fcr Materialien OHNE
        Sell-Orders am Hub (sonst w\u00fcrde so ein Material f\u00e4lschlich "gratis").

    Returns [{"qty", "total_cost", "mat_cost_ladder", "job_cost", "inv_cost",
              "cost_unit", "short_materials"}] sortiert nach qty aufsteigend.
    "short_materials": [{"type_id", "needed", "available", "short"}] \u2013 NICHT
    leer, sobald das Orderbuch f\u00fcr ein Material bei dieser St\u00fcckzahl nicht
    mehr genug Volumen hat (der fehlende Rest wird konservativ zum teuersten
    bekannten Orderbuch-Preis gesch\u00e4tzt, oder zum Flachpreis als letzter
    Fallback) \u2013 das ist der eigentliche Fingerzeig auf "hier wird der Markt
    zu d\u00fcnn f\u00fcr diese Menge"."""
    all_qtys = sorted(set(int(q) for q in (qtys or []) if q and q >= 1))
    if not all_qtys:
        return []
    ref_qty = all_qtys[-1]
    ref_plan = plan_fn(ref_qty)
    material_ids = set((ref_plan.get("buy") or {}).keys())
    orderbooks = {}
    for tid in material_ids:
        try:
            orderbooks[tid] = orderbook_fn(tid) or []
        except Exception:
            orderbooks[tid] = []

    out = []
    for q in all_qtys:
        plan = ref_plan if q == ref_qty else plan_fn(q)
        buy = plan.get("buy") or {}
        mat_cost = 0.0
        shorts = []
        for tid, need in buy.items():
            need_i = int(round(need))
            if need_i < 1:
                continue
            ob = orderbooks.get(tid)
            if ob is None:
                # Material taucht bei dieser Menge neu auf (selten \u2013 z. B.
                # wenn sich eine Bau/Kauf-Entscheidung mit der Stückzahl
                # \u00e4ndert): nachtr\u00e4glich abrufen statt ihn zu \u00fcbergehen.
                try:
                    ob = orderbook_fn(tid) or []
                except Exception:
                    ob = []
                orderbooks[tid] = ob
            ladder_c, bought = buy_cost(ob, need_i)
            short = need_i - bought
            if short > 0:
                if ob:
                    worst = max(p for p, _v in ob)
                    ladder_c += short * worst
                elif price_fn:
                    flat = price_fn(tid)
                    if flat is not None:
                        ladder_c += short * flat
                shorts.append({"type_id": tid, "needed": need_i,
                               "available": bought, "short": short})
            mat_cost += ladder_c
        job_cost = float(plan.get("job_cost", 0.0))
        inv_cost = float(plan.get("inv_cost", 0.0))
        total = mat_cost + job_cost + inv_cost
        out.append({"qty": q, "total_cost": total, "mat_cost_ladder": mat_cost,
                    "job_cost": job_cost, "inv_cost": inv_cost,
                    "cost_unit": (total / q) if q else 0.0,
                    "short_materials": shorts, "buy": dict(buy),
                    "_orderbooks": orderbooks})
    return out


def ladder_detail_for_buy(buy, orderbooks, price_fn=None, avg_fn=None):
    """Wie ladder_cost_for_buy, aber MIT den Warnungen statt nur der Summe.

    Rückgabe {"mat_cost", "short_materials", "no_book", "avg_priced",
    "unpriced"}:
      short_materials: [{type_id, needed, available, short}] - Orderbuch am Hub
        reicht bei DIESER Menge nicht; der Rest ist konservativ zum teuersten
        bekannten Preis geschätzt.
      no_book: [type_id] - für dieses Material liegt gar kein gecachtes Buch
        vor (taucht erst bei der aktuellen Menge in der Einkaufsliste auf) →
        Flachpreis. Beides muss sichtbar bleiben, sobald die Bücher für eine
        ANDERE Menge geholt wurden als die gerade angezeigte - sonst sähe eine
        grobe Schätzung wie eine orderbuch-genaue Zahl aus.
      avg_priced: [type_id] - weder Buch noch Hub-Preis; bewertet mit dem
        serverweiten CCP-Durchschnitt (`avg_fn`).
      unpriced: [type_id] - überhaupt kein Preis zu bekommen. Diese Menge
        FEHLT in `mat_cost` und muss angezeigt werden.

    STILLE NULL BESEITIGT (Nutzer-Befund Sitzung 14: "es ist nicht möglich
    dass eine Ametat II nur 10 mio kostet"). Vorher endete der Zweig ohne
    Orderbuch bei `if flat is not None: ...` - war auch der Flachpreis None,
    ging das Material mit 0 ISK in die Summe. Es landete zwar in `no_book`,
    aber `short_materials` blieb leer, sodass die Knappheits-Warnung nicht
    ansprang. Sichtbare Folge: die Baukosten halbierten sich, sobald ein
    Wechsel der Fertigungstiefe neue Materialien in die Einkaufsliste brachte,
    für die nie Bücher geholt worden waren.

    RÜCKFALL-KETTE (sein Vorschlag): Orderbuch → Hub-Flachpreis →
    CCP-Durchschnitt → als ungeschätzt MELDEN. Nie mehr stillschweigend 0.
    """
    mat_cost = 0.0
    shorts = []
    no_book = []
    avg_priced = []
    unpriced = []
    for tid, need in (buy or {}).items():
        need_i = int(round(need))
        if need_i < 1:
            continue
        ob = (orderbooks or {}).get(tid) or []
        if not ob:
            no_book.append(tid)
        ladder_c, bought = buy_cost(ob, need_i)
        short = need_i - bought
        if short > 0:
            if ob:
                worst = max(p for p, _v in ob)
                ladder_c += short * worst
                shorts.append({"type_id": tid, "needed": need_i,
                               "available": bought, "short": short})
            else:
                _flat = price_fn(tid) if price_fn else None
                if _flat is None and avg_fn:
                    # NICHTS AM MARKT -> CCP-DURCHSCHNITT. Grob, aber ehrlich:
                    # dass in Jita gerade nichts liegt, merkt man beim
                    # Einkaufen ohnehin; eine fehlende Position im Plan merkt
                    # man nicht.
                    _flat = avg_fn(tid)
                    if _flat is not None:
                        avg_priced.append(tid)
                if _flat is None:
                    # KEIN PREIS ZU BEKOMMEN: die Menge fehlt in der Summe.
                    # Das wird GEMELDET, nicht als 0 behauptet (Regel 6).
                    unpriced.append(tid)
                else:
                    ladder_c += short * _flat
        mat_cost += ladder_c
    return {"mat_cost": mat_cost, "short_materials": shorts,
            "no_book": no_book, "avg_priced": avg_priced,
            "unpriced": unpriced}


def ladder_cost_for_buy(buy, orderbooks, price_fn=None):
    """Rechnet die orderbuch-basierten Materialkosten für eine BELIEBIGE
    Bedarfsliste (`buy`: {type_id: Menge}) anhand bereits gecachter
    Orderbücher (`orderbooks`, aus ladder_cost_curve()['_orderbooks']) neu -
    OHNE erneuten Live-Abruf. Wichtig, weil sich die benötigte MENGE pro
    Material ändert, sobald der Nutzer im Invention-Tab einen anderen
    Decryptor (andere ME) wählt ODER die Stückzahl dreht - die Orderbuch-
    PREISE selbst ändern sich in der Zwischenzeit nicht so schnell, dass man
    dafür jedes Mal neu abrufen müsste. Gleiche buy_cost()-Logik wie in
    ladder_cost_curve, nur auf einer bereits vorhandenen Bedarfsliste statt
    einer neu geplanten. Nur die Summe; Warnungen liefert
    ladder_detail_for_buy()."""
    return ladder_detail_for_buy(buy, orderbooks, price_fn)["mat_cost"]


def reaction_surplus_pct(plan, reaction_products, batch_size_of, exclude=None):
    """Prozentualer Reaktions-\u00dcberschuss eines Plans. Reaktionen laufen in
    festen Chargen (man kann keine halbe Charge machen), also f\u00e4llt fast immer
    etwas \u00dcberproduktion an. Bei "glatten" Baumengen gehen die Chargen fast auf
    (wenig \u00dcberschuss), bei "krummen" bleibt viel \u00fcbrig -- genau der Punkt, den
    man beim Optimieren minimieren will.

    plan: production_plan()-Ergebnis (nutzt "surplus" {tid: \u00fcberproduziert} und
        "build_runs" {tid: runs}).
    reaction_products: set/dict der type_ids, die per Reaktion entstehen
        (recipes.reaction_products) -- nur diese z\u00e4hlen als Reaktions-\u00dcberschuss.
    batch_size_of(tid) -> Output-St\u00fcck pro Run (Chargengr\u00f6\u00dfe), z. B.
        recipes.product_to_bp[tid][2].
    exclude: type_ids, die NICHT mitz\u00e4hlen. Gedacht f\u00fcr das ENDPRODUKT, wenn
        das selbst eine Reaktion ist: dessen Menge w\u00e4hlt der Nutzer, sie liegt
        (seit der Run-Rundung) immer auf ganzen Chargen und hat daher per
        Konstruktion 0 \u00dcberschuss. Weil der Wert nach St\u00fcckzahl gewichtet ist
        und das Endprodukt die mit Abstand gr\u00f6\u00dfte Charge hat, dr\u00fcckte es den
        Prozentwert massiv: gemessen an Phenolic Composites erschienen 51,0 %
        Verschnitt bei den Zwischenprodukten als 4,25 %. Entscheidungsrelevant
        ist genau der Zwischenprodukt-Verschnitt.

    Returns {"pct", "surplus_units", "produced_units", "per_item": [{type_id,
    surplus, produced, pct}]}. "pct" = gesamter \u00fcberproduzierter Reaktions-
    Output / gesamter produzierter Reaktions-Output * 100 (gewichtet nach
    St\u00fcckzahl, also z\u00e4hlen gro\u00dfe Chargen st\u00e4rker). 0.0 wenn keine Reaktionen
    gebaut werden."""
    surplus = plan.get("surplus") or {}
    build_runs = plan.get("build_runs") or {}
    rp = reaction_products if hasattr(reaction_products, "__contains__") else set(reaction_products)
    total_surplus = 0.0
    total_produced = 0.0
    per_item = []
    _skip = set(exclude or ())
    for tid, runs in build_runs.items():
        if tid not in rp or runs <= 0 or tid in _skip:
            continue
        batch = int(batch_size_of(tid) or 1) or 1
        produced = runs * batch
        over = float(surplus.get(tid, 0) or 0)
        if produced <= 0:
            continue
        total_surplus += over
        total_produced += produced
        per_item.append({"type_id": tid, "surplus": over, "produced": produced,
                         "pct": (over / produced * 100.0) if produced else 0.0})
    pct = (total_surplus / total_produced * 100.0) if total_produced else 0.0
    per_item.sort(key=lambda r: r["pct"], reverse=True)
    return {"pct": pct, "surplus_units": total_surplus,
            "produced_units": total_produced, "per_item": per_item}


def balanced_score(curve, monthly_absorption=None, w_profit=0.45,
                   w_capital=0.25, w_surplus=0.15, w_absorption=0.15):
    """Ausgewogener 'beste Menge'-Score pro Kurvenpunkt (0..100). Verrechnet vier
    teils widerspr\u00fcchliche Ziele, damit man nicht mehrere Kurven im Kopf
    gegeneinander abw\u00e4gen muss. KEIN Kapital-BUDGET (der Nutzer entscheidet die
    absolute H\u00f6he selbst) -- Kapital geht nur als *relative* Effizienz ein
    (Gewinn pro gebundenem ISK), damit nicht stumpf 'immer mehr' gewinnt.

    Bewertet jeden Punkt auf vier normalisierten Achsen (0..1, h\u00f6her = besser):
      - profit: Gewinn gesamt, linear normiert auf [min..max] der Kurve.
        Haupttreiber (w_profit).
      - capital: Kapital-Effizienz = Gewinn / gebundene Baukosten (Marge-Rendite).
        D\u00e4mpft 'immer mehr bauen', wenn der Zusatzgewinn pro gebundenem ISK
        sinkt (steigende Materialkosten). Normiert auf [min..max].
      - surplus: 1 - Reaktions-\u00dcberschuss%/100 (weniger Verschnitt = besser).
      - absorption: 1.0 solange qty <= Monats-Absorption, danach linear
        fallend (mehr bauen als der Markt/Monat aufnimmt wird abgewertet, aber
        nicht hart gekappt -- Einlagern/l\u00e4nger verkaufen ist ja m\u00f6glich).
        Ohne monthly_absorption neutral (1.0 f\u00fcr alle).

    curve: Liste von Punkten mit mind. {qty, profit, cost_unit, surplus_pct}.
        (cost_unit*qty = gebundene Baukosten je Punkt.)
    Returns dieselbe Liste, jeder Punkt um "score" (0..100) erweitert, plus die
    Einzelachsen unter "score_parts" f\u00fcr Transparenz/Tooltips. Gibt zus\u00e4tzlich
    den besten Punkt als zweites Element zur\u00fcck: (curve, best_point)."""
    pts = [c for c in (curve or []) if c.get("qty")]
    if not pts:
        return curve, None

    profits = [c.get("profit", 0.0) for c in pts]
    caps = []
    for c in pts:
        bound = c.get("cost_unit", 0.0) * c["qty"]      # gebundenes Kapital
        caps.append((c.get("profit", 0.0) / bound) if bound > 0 else 0.0)

    def _norm(vals):
        lo, hi = min(vals), max(vals)
        rng = hi - lo
        if rng <= 0:
            return [1.0 for _ in vals]      # alle gleich -> neutral (nicht 0)
        return [(x - lo) / rng for x in vals]

    profit_n = _norm(profits)
    cap_n = _norm(caps)

    for i, c in enumerate(pts):
        surplus_n = max(0.0, 1.0 - (c.get("surplus_pct", 0.0) / 100.0))
        if monthly_absorption and monthly_absorption > 0:
            if c["qty"] <= monthly_absorption:
                abso_n = 1.0
            else:
                # linear fallend: bei 2x Monats-Absorption auf 0
                over = (c["qty"] - monthly_absorption) / monthly_absorption
                abso_n = max(0.0, 1.0 - over)
        else:
            abso_n = 1.0
        raw = (w_profit * profit_n[i] + w_capital * cap_n[i]
               + w_surplus * surplus_n + w_absorption * abso_n)
        total_w = w_profit + w_capital + w_surplus + w_absorption
        c["score"] = round(raw / total_w * 100.0, 1) if total_w else 0.0
        c["score_parts"] = {"profit": round(profit_n[i], 3),
                            "capital": round(cap_n[i], 3),
                            "surplus": round(surplus_n, 3),
                            "absorption": round(abso_n, 3)}
    best = max(pts, key=lambda c: c["score"])
    return curve, best


def _sweep_points(lo, hi, n=48):
    """A log-spaced set of candidate quantities between lo and hi (inclusive)."""
    lo = max(1, int(lo))
    hi = max(lo, int(hi))
    if hi == lo:
        return [lo]
    pts = {lo, hi}
    ratio = hi / lo
    for i in range(n):
        f = i / (n - 1)
        pts.add(int(round(lo * (ratio ** f))))
    return sorted(p for p in pts if p >= 1)


def market_absorption(history_entries, days=30):
    """Wie viel von einem Item sich an einem Hub durchschnittlich wirklich
    verkauft -- KOMPLETT unabhängig von der Baumenge/den Baukosten. Nutzt die
    letzten `days` Tage aus der ESI-Markt-Historie (rohes fetch_market_history()-
    Ergebnis, unsortiert ok). Returns {"avg_daily", "per_week", "per_month",
    "days_used"} oder None, wenn keine Historie da ist."""
    if not history_entries:
        return None
    entries = sorted(history_entries, key=lambda e: e.get("date", ""))
    recent = entries[-days:] if len(entries) > days else entries
    vols = [float(e.get("volume") or 0) for e in recent]
    if not vols:
        return None
    avg = sum(vols) / len(vols)
    return {"avg_daily": avg, "per_week": avg * 7, "per_month": avg * 30,
           "days_used": len(vols)}


# EVE-Skill-IDs für parallele Job-Slots
_SLOT_SKILLS_MFG = (3387, 24625)       # Mass Production, Advanced Mass Production
_SLOT_SKILLS_REACTION = (45748, 45749)  # Mass Reactions, Advanced Mass Reactions
_SLOT_SKILLS_SCIENCE = (3406, 24624)   # Laboratory Operation, Advanced Lab. Operation
                                        # (Science-Slots: Invention + Kopieren)

_TIME_SKILL_INDUSTRY = 3380            # Industry: −4 % Fertigungszeit/Stufe
_TIME_SKILL_ADV_INDUSTRY = 3388        # Advanced Industry: −3 % Job-Zeit/Stufe
_TIME_SKILL_REACTIONS = 45746          # Reactions: −4 % Reaktionszeit/Stufe
                                        # (gilt EXKLUSIV für Reaktionen; Advanced
                                        # Industry wirkt NICHT auf Reaktionen)
                                        # Die -4/-3/-4-Werte sind Fallbacks, falls
                                        # die SDE-Werte (noch) fehlen. Verifiziert
                                        # gegen skill_diagnose.txt (SDE-Attribute
                                        # manufacturingTimeBonus=-4.0,
                                        # advancedIndustrySkillIndustryJobTimeBonus=
                                        # -3.0, reactionTimeBonus=-4.0) - siehe
                                        # _skill_time_bonus_pct().

_skill_time_bonus_cache = None


def _skill_time_bonus_pct(skill_id, fallback):
    """%-Bonus/Stufe (positiv) für einen Zeit-Skill, aus der SDE gelesen (meta-
    Tabelle 'skill_time_bonus_pct', beim SDE-Download befüllt, s. download_sde).
    Fallback auf den zuletzt verifizierten Wert, falls die SDE-Daten fehlen
    (alte DB vor diesem Feature, oder Attributname ändert sich in künftigem
    SDE-Release -> download_sde() bricht dann still ab, s. dort)."""
    global _skill_time_bonus_cache
    if _skill_time_bonus_cache is None:
        _skill_time_bonus_cache = {}
        try:
            with _conn() as c:
                row = c.execute(
                    "SELECT v FROM meta WHERE k='skill_time_bonus_pct'").fetchone()
            if row and row[0]:
                _skill_time_bonus_cache = {
                    int(k): float(v) for k, v in json.loads(row[0]).items()}
        except Exception:
            _skill_time_bonus_cache = {}
    return abs(_skill_time_bonus_cache.get(skill_id, fallback))


def skill_time_bonus_pct(skill_id, fallback):
    """Öffentlicher Wrapper um _skill_time_bonus_pct (fürs UI, z.B. Anzeige-Labels)."""
    return _skill_time_bonus_pct(skill_id, fallback)


def load_rigs():
    """Struktur-Rigs direkt aus der SDE: [{type_id, name, group, time, material, cost}].
    time/material/cost sind die Basis-Boni in % (negativ). Leer, wenn die SDE noch
    ohne Rig-Daten ist (dann nutzt das UI einen verifizierten Fallback)."""
    try:
        with _conn() as c:
            try:
                rows = c.execute(
                    "SELECT type_id,name,group_name,time_bonus,material_bonus,"
                    "cost_bonus,effects FROM rigs ORDER BY name").fetchall()
            except Exception:
                rows = c.execute(          # ältere DB ohne effects-Spalte
                    "SELECT type_id,name,group_name,time_bonus,material_bonus,"
                    "cost_bonus FROM rigs ORDER BY name").fetchall()
    except Exception:
        return []
    out = []
    for r in rows:
        keys = r.keys()
        effs = (r["effects"] or "") if "effects" in keys else ""
        out.append({"type_id": r["type_id"], "name": r["name"] or "",
                    "group": r["group_name"] or "",
                    "time": r["time_bonus"] or 0.0,
                    "material": r["material_bonus"] or 0.0,
                    "cost": r["cost_bonus"] or 0.0,
                    "effects": [e for e in effs.split(",") if e]})
    return out


def load_implant_time_bonuses():
    """Fertigungszeit-Implantate aus der SDE: {type_id: {"name","activity","pct"}}.
    Leer, wenn die SDE (noch) ohne Implantat-Daten ist."""
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT type_id,name,activity,pct FROM implant_time_bonus").fetchall()
    except Exception:
        return {}
    return {r["type_id"]: {"name": r["name"] or "", "activity": r["activity"] or "",
                           "pct": r["pct"] or 0.0} for r in rows}


def load_decryptors():
    """Decryptors aus der SDE: [{type_id, name, prob_mult, me_mod, te_mod, run_mod}].
    Leer, wenn die SDE (noch) ohne Decryptor-Daten ist (dann Fallback im UI)."""
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT type_id,name,prob_mult,me_mod,te_mod,run_mod "
                "FROM decryptors ORDER BY name").fetchall()
    except Exception:
        return []
    out = []
    for r in rows:
        out.append({"type_id": r["type_id"], "name": r["name"] or "",
                    "prob_mult": r["prob_mult"] if r["prob_mult"] is not None else 1.0,
                    "me_mod": r["me_mod"] or 0.0, "te_mod": r["te_mod"] or 0.0,
                    "run_mod": r["run_mod"] or 0.0})
    return out


def _norm_skill_keys(skills):
    """Skill-Dict mit int-Keys zurückgeben. Nötig, weil gespeicherte Skills aus
    JSON String-Keys haben (\"3380\"), die Skill-ID-Konstanten aber int sind."""
    out = {}
    for k, v in (skills or {}).items():
        try:
            out[int(k)] = int(v or 0)
        except (TypeError, ValueError):
            continue
    return out


def recommended_bp_copies(total_runs, max_runs_per_job, available_slots):
    """Wie viele Kopien eines Blueprints (BPO, unbegrenzt Runs, voll erforscht)
    du besitzen solltest, um dieses Item mit möglichst wenig Wellen zu bauen -
    ohne mehr Kopien zu empfehlen, als ohnehin sinnvoll nutzbar sind (die
    verfügbaren Slots sind eine harte Obergrenze; keine 500 Kopien für ein
    Item mit nur 3 nutzbaren Slots).
    - total_runs: wie viele Runs insgesamt gebraucht werden.
    - max_runs_per_job: max. Runs, die EIN einzelner Job dieses Blueprints auf
      einmal bauen kann (SDE maxProductionLimit; 0/None = kein Limit).
    - available_slots: wie viele parallele Job-Slots realistisch für DIESES
      Item zur Verfügung stehen (Summe der Fertigungs-/Reaktions-Slots der
      dafür eingeplanten Charaktere).
    Rückgabe: (empfohlene_kopien, jobs_insgesamt_nötig, wellen_mit_dieser_kopienzahl).
    """
    total_runs = max(0, int(total_runs or 0))
    available_slots = max(1, int(available_slots or 1))
    if total_runs <= 0:
        return 0, 0, 0
    if max_runs_per_job and max_runs_per_job > 0:
        jobs_needed = -(-total_runs // max_runs_per_job)   # aufrunden
    else:
        jobs_needed = 1        # ein Job kann theoretisch alle Runs auf einmal
    copies = min(jobs_needed, available_slots)
    waves = -(-jobs_needed // copies) if copies > 0 else jobs_needed
    return copies, jobs_needed, waves


def _binomial_p_at_least(n, k, prob):
    """P(X >= k) für X ~ Binomial(n, prob). Numerisch stabil über PMF-Rekursion
    (pmf(j+1) = pmf(j) · (n-j)/(j+1) · p/(1-p)) statt math.comb, das bei
    größeren n/k schnell zu riesigen Zwischenwerten führt."""
    n = max(0, int(n or 0)); k = max(0, int(k or 0))
    prob = max(0.0, min(1.0, float(prob or 0)))
    if k <= 0:
        return 1.0
    if k > n:
        return 0.0
    if prob <= 0.0:
        return 0.0
    if prob >= 1.0:
        return 1.0
    pmf = (1.0 - prob) ** n          # P(X=0)
    cdf_below = pmf                  # Summe P(X=0..k-1)
    for j in range(0, k - 1):
        pmf = pmf * (n - j) / (j + 1) * (prob / (1.0 - prob))
        cdf_below += pmf
    return max(0.0, min(1.0, 1.0 - cdf_below))


def invention_attempts_for_confidence(successes_needed, prob, confidence=0.75,
                                      max_attempts=200000):
    """Kleinste Versuchszahl n, sodass P(mind. `successes_needed` Erfolge bei n
    Versuchen, Erfolgschance `prob`) >= `confidence` ist. Das ist die Zahl, die
    das Tool jetzt standardmäßig vorschlägt (statt nur des Erwartungswerts) -
    mit reinem Erwartungswert liegt die tatsächliche Trefferchance oft nur bei
    ~50-60%, das reicht dem User nicht."""
    successes_needed = max(0, int(successes_needed or 0))
    if successes_needed == 0:
        return 0
    prob = max(0.0, min(1.0, float(prob or 0)))
    if prob <= 0.0:
        return None
    if prob >= 1.0:
        return successes_needed
    n = successes_needed
    while n <= max_attempts:
        if _binomial_p_at_least(n, successes_needed, prob) >= confidence:
            return n
        n += 1
    return max_attempts


def me_invented_pct(inv_me, rig_me, ec_me=0.0):
    """Effektive ME einer INVENTED Blaupause: Invention-ME x Rig x Struktur-
    Rollenbonus (Engineering Complex 1 %), multiplikativ wie im Spiel.
    NUTZER-BEFUND 19.09.2026 (Viator x20, ME 3 % Parity, Azbel): von JEDER
    Komponente blieb ~1 % uebrig (Plates 580 von 58'200, Fusion Reactor 10
    von 740, Ion Thruster 25 von 2'200). Nachgerechnet: 38 x 4 Runs x 0,97
    x 0,99 = 145,96 -> 146 je Job, 5 Jobs = 730 -> genau 10 uebrig. Der
    invented-Pfad nahm nur Invention-ME x Rig - der 1-%-Bonus des Complexes
    stand zwar in me_map (T1-Pfad), wurde hier aber uebersprungen. EINE
    Formel fuer build_cost, build_time_per_unit, Rezeptbaum und
    production_plan."""
    return (1 - (1 - float(inv_me or 0) / 100.0) * (1 - float(rig_me or 0) / 100.0)
            * (1 - float(ec_me or 0) / 100.0)) * 100.0


def decryptor_fuer_bp(bp_id, opts):
    """Welcher Decryptor gilt fuer DIESE Blaupause?

    Erst die Wahl je Item aus dem Invention-Tab
    (`opts["inv_decryptor_map"][bp_id]`), sonst die globale Einstellung,
    sonst "Kein Decryptor". EINE Stelle dafuer (Arbeitsregel 9): die Frage
    stellen `_invention_me_pct` (fuer die ME) und der Multi-Bauplan (fuer
    Runs je erfundener BPC) - stuende sie zweimal im Code, koennten ME und
    Kopienzahl irgendwann von VERSCHIEDENEN Decryptoren ausgehen."""
    per_item = (opts.get("inv_decryptor_map") or {}).get(bp_id)
    if per_item is not None:
        return per_item
    return (opts.get("inv_prob_mult", 1.0), opts.get("inv_run_mod", 0),
            opts.get("inv_me_mod", 0), opts.get("inv_te_mod", 0),
            opts.get("inv_decryptor_id"))


def _invention_me_pct(bp_id, recipes, opts):
    """ECHTE ME einer invented BPC (2% Basis-Invention-ME + Decryptor-Bonus)
    statt der geschätzten Kategorie-/Blueprint-ME - eine invented BPC hat NIE
    eine frei recherchierte ME, nur die feste Invention-ME. Nutzt den per-Item
    gewählten Decryptor (opts['inv_decryptor_map'][bp_id]) falls vorhanden,
    sonst den globalen Decryptor (opts['inv_prob_mult']/'inv_run_mod'/
    'inv_me_mod'/'inv_te_mod'/'inv_decryptor_id'), sonst 'Kein Decryptor'
    (2% Basis). None, wenn dieses Item keine Invention braucht oder Invention
    in den opts ausgeschaltet ist (dann bleibt der bisherige me_map-Pfad
    unverändert aktiv). Auch None, wenn der Nutzer dieses Item explizit als
    "Eigene BPC" markiert hat (opts['inv_manual_override'][bp_id]) - dann
    sollen die manuell eingetragene ME (me_map, normaler Pfad) gelten, nicht
    die Invention-Rechnung."""
    if bp_id in (opts.get("inv_manual_override") or {}):
        return None
    if not opts.get("invention", True):
        return None
    inv = recipes.invention_for_bpc.get(bp_id)
    if not inv:
        return None
    _t1_bp, base_runs, base_prob, _datacores = inv
    return invention_outcome(base_runs, base_prob,
                             decryptor_fuer_bp(bp_id, opts))["me_pct"]


def invention_outcome(base_runs, base_prob, decryptor):
    """Ergebnis einer Invention mit gewähltem Decryptor (oder None/'Kein Decryptor').
    decryptor: (prob_mult, run_mod, me_mod, te_mod, type_id) oder None.
    base_runs/base_prob: aus der SDE (Invention-Basiswerte OHNE Decryptor,
    z.B. base_runs=1, base_prob=0.385 für Flycatcher laut Ingame-Panel).
    Rückgabe: {"prob", "runs", "me_pct", "te_pct"} - "me_pct"/"te_pct" sind die
    FESTEN EVE-Invention-Basiswerte (2%/4%, dokumentierte Spielkonstante seit
    Einführung der T2-Invention, nicht SDE-abhängig) + Decryptor-Modifikator."""
    pm, rm, me_mod, te_mod = (1.0, 0, 0, 0) if not decryptor else decryptor[:4]
    prob = min(1.0, max(0.0, float(base_prob or 0) * pm))
    runs = max(1, int(base_runs or 1) + int(rm or 0))
    me_pct = max(0, 2 + int(me_mod or 0))
    te_pct = max(0, 4 + int(te_mod or 0))
    return {"prob": prob, "runs": runs, "me_pct": me_pct, "te_pct": te_pct}


DEFAULT_INVENTION_CONFIDENCE = 0.75    # User will >=75% Trefferchance, nicht nur Ø


def invention_attempt_plan(runs_needed, outcome, datacore_unit_costs, decryptor_cost,
                           job_cost_per_attempt=0.0, confidence=DEFAULT_INVENTION_CONFIDENCE):
    """Wie viele Invention-Versuche nötig sind, um `runs_needed` Runs zu
    bekommen (bei `outcome["runs"]` Runs pro Erfolg, `outcome["prob"]`
    Erfolgschance) - sowohl im Durchschnitt (expected_attempts, nur zur Info)
    ALS AUCH die Versuchszahl für eine `confidence`-Erfolgswahrscheinlichkeit
    (confident_attempts/confident_cost - das ist jetzt die Zahl, die das Tool
    empfiehlt). datacore_unit_costs: Liste der Gesamtkosten aller Datacores
    für EINEN Versuch (schon × Menge)."""
    runs_needed = max(0, int(runs_needed or 0))
    if runs_needed <= 0:
        return {"successes_needed": 0, "expected_attempts": 0.0, "total_cost": 0.0,
               "datacore_cost_per_attempt": 0.0, "confidence": confidence,
               "confident_attempts": 0, "confident_cost": 0.0}
    successes_needed = -(-runs_needed // outcome["runs"])          # aufrunden
    prob = max(1e-6, outcome["prob"])
    expected_attempts = successes_needed / prob
    dc_cost = sum(datacore_unit_costs or [])
    cost_per_attempt = dc_cost + (decryptor_cost or 0.0) + (job_cost_per_attempt or 0.0)
    total_cost = expected_attempts * cost_per_attempt
    confident_attempts = invention_attempts_for_confidence(successes_needed, prob, confidence)
    confident_cost = (confident_attempts or 0) * cost_per_attempt
    return {"successes_needed": successes_needed, "expected_attempts": expected_attempts,
            "total_cost": total_cost, "datacore_cost_per_attempt": dc_cost,
            "confidence": confidence, "confident_attempts": confident_attempts,
            "confident_cost": confident_cost}


def kopien_aufteilung(attempts, runs_per_success, slots=None, kopien=None,
                      max_runs_je_kopie=None, prob=None):
    """Wie teile ich die Invention-Versuche auf T1-Kopien auf? (pur, testbar)

    NUTZER-PROBLEM (Sitzung 8): "Ich kann nicht aufteilen, in wievielen Tagen
    ich die Invention gemacht haben will. Wenn ich 500 T2-Runs brauche, macht
    es mehr Sinn, das auf 10 Kopien aufzuteilen - also erst aus dem Original
    10x T1-Kopie mit je 50 Runs ziehen."

    DER KERN, warum das ueberhaupt zaehlt: EIN Invention-Job verbraucht EINEN
    Run EINER Kopie - und eine Kopie kann immer nur EINEN Job gleichzeitig
    tragen. Mit einer einzigen 500-Run-Kopie laufen die 500 Versuche also
    NACHEINANDER. Mit 10 Kopien laufen 10 Jobs PARALLEL (soweit
    Wissenschafts-Slots frei sind) - dieselbe Arbeit in einem Zehntel der
    Wandzeit.

    Argumente:
      attempts          - benoetigte Versuche (aus der 75%-Sicherheit)
      runs_per_success  - T2-Runs je gelungener Invention (Decryptor-abhaengig)
      slots             - freie Wissenschafts-Slots (begrenzt die Parallelitaet)
      kopien            - gewuenschte Kopienzahl; None = automatisch = slots
      max_runs_je_kopie - Kopier-Obergrenze der Blaupause (None = egal)

    Rueckgabe-Schluessel: kopien, runs_je_kopie, versuche_gesamt (kann durch
    das Aufrunden ueber `attempts` liegen - Rest bleibt als Reserve auf der
    letzten Kopie), parallel (tatsaechlich gleichzeitig laufende Jobs),
    wellen (wie oft nacheinander), rest_reserve, und - NUR mit `prob` -
    erfolge_erwartet / t2_runs_erwartet.

    ACHTUNG (eigener Fehler, Sitzung 8 korrigiert): t2_runs_erwartet hiess
    frueher `runs_per_success x KOPIEN` - das war Unsinn (10 Kopien haetten
    "100 Runs" ergeben, unabhaengig von den Versuchen). Richtig ist
    Versuche x Erfolgschance x Runs-je-Erfolg; ohne `prob` gibt es den Wert
    gar nicht mehr, statt eine Zahl zu erfinden."""
    attempts = max(0, int(attempts or 0))
    if attempts <= 0:
        return {"kopien": 0, "runs_je_kopie": 0, "versuche_gesamt": 0,
                "parallel": 0, "wellen": 0, "rest_reserve": 0}
    frei = max(1, int(slots or 1))
    n = int(kopien) if kopien else frei
    n = max(1, min(n, attempts))          # nie mehr Kopien als Versuche
    runs_je = -(-attempts // n)           # aufrunden
    if max_runs_je_kopie:
        runs_je = min(runs_je, int(max_runs_je_kopie))
        # Deckelt die Blaupause die Runs, braucht es entsprechend MEHR Kopien.
        n = max(n, -(-attempts // runs_je))
    gesamt = n * runs_je
    parallel = min(n, frei)
    out = {"kopien": n, "runs_je_kopie": runs_je, "versuche_gesamt": gesamt,
           "parallel": parallel,
           "wellen": -(-runs_je * n // parallel) if parallel else 0,
           "rest_reserve": gesamt - attempts}
    if prob:
        # Nur MIT Erfolgschance sinnvoll: nicht jeder Versuch gelingt.
        out["erfolge_erwartet"] = attempts * float(prob)
        out["t2_runs_erwartet"] = (attempts * float(prob)
                                   * int(runs_per_success or 0))
    return out


def kopien_fuers_bauen(assignments, nur_stufen=None, ohne_tids=None,
                       hat_original=True):
    """Welche T1-Blaupausen-KOPIEN braucht es, um den Plan parallel zu bauen?
    (pur, testbar)

    NUTZER-PROBLEM (Sitzung 8): "Zusaetzlich brauche ich ja noch T1-Kopien,
    um genuegend T1 bauen zu koennen wie im Runplaner angegeben. Ich muesste
    3 Blueprint-Copys mit jeweils 28 Runs haben, damit alle 3 Charaktere
    gleichzeitig das T1 bauen koennen."

    DER KERN: eine Blaupause traegt immer nur EINEN Job. Der Runplaner teilt
    z. B. 245 Runs auf 9 gleichzeitige Jobs auf - dafuer braucht es 9
    Blaupausen desselben Items. Wer nur EIN Original besitzt, muss vorher 9
    KOPIEN ziehen (bzw. 8, wenn das Original selbst mitlaeuft). Der
    Runplaner zeigt die Aufteilung, sagte aber nie, dass es Kopien SIND.

    ZWEI KORREKTUREN nach Nutzer-Screenshots (Sitzung 8):
    1. `ohne_tids` = Items, deren Blaupausen aus der INVENTION stammen. Bei
       Rigs (z. B. Medium Projectile Collision Accelerator II) braucht das
       T2 KEIN T1-Modul; die 9 "Blueprints" der Endprodukt-Stufe sind die
       erfundenen T2-BPCs. Die kopiert man NICHT - sie fallen bei der
       Invention an. Ohne diesen Filter haette das Tool geraten, sie zu
       kopieren: schlicht falsch.
    2. `hat_original`: wer das Original besitzt, kann damit EINEN der Jobs
       fahren - es braucht also nur jobs-1 Kopien. Items mit nur einem Job
       tauchen dann gar nicht auf (das Original genuegt).

    assignments: Liste der Runplaner-Zuteilungen, je Eintrag mindestens
    {"tid", "name", "jobs", "runs"} (mehrere Eintraege je Item moeglich -
    einer pro Charakter).

    Rueckgabe je Item: {"tid", "name", "kopien", "gruppen": [(runs, anzahl)],
    "runs_gesamt"} - "gruppen" absteigend nach Run-Zahl, exakt wie die
    Anzeige im Runplaner."""
    from collections import Counter
    je_item = {}
    for a in assignments or []:
        stufe = a.get("stage")
        if nur_stufen and stufe not in nur_stufen:
            continue
        tid = a.get("tid")
        if tid is None or tid in (ohne_tids or ()):
            continue
        njobs = int(a.get("jobs", 1) or 1)
        runs = int(a.get("runs") or 0)
        if runs <= 0 or njobs <= 0:
            continue
        # Gleiche Aufteilung wie der Runplaner: Rest auf die ersten Jobs.
        basis, rest = divmod(runs, njobs)
        teile = [basis + 1] * rest + [basis] * (njobs - rest)
        eintrag = je_item.setdefault(
            tid, {"tid": tid, "name": a.get("name") or f"#{tid}",
                  "teile": [], "runs_gesamt": 0})
        eintrag["teile"] += [t for t in teile if t > 0]
        eintrag["runs_gesamt"] += runs
    out = []
    for e in je_item.values():
        if not e["teile"]:
            continue
        cnt = Counter(e["teile"])
        blaupausen = len(e["teile"])
        # Mit Original in der Hand deckt dieses EINEN Job ab.
        kopien = blaupausen - 1 if hat_original else blaupausen
        if kopien <= 0:
            continue          # ein Job - das Original genuegt
        out.append({"tid": e["tid"], "name": e["name"],
                    "kopien": kopien, "blaupausen": blaupausen,
                    "gruppen": sorted(cnt.items(), reverse=True),
                    "runs_gesamt": e["runs_gesamt"]})
    out.sort(key=lambda x: (-x["kopien"], x["name"]))
    return out


def invention_manual_plan(attempts, outcome, datacore_unit_costs, decryptor_cost,
                          job_cost_per_attempt=0.0, successes_needed=None):
    """Umkehrung von invention_attempt_plan: gibt der Nutzer selbst eine
    Versuchszahl vor (statt Ziel-Runs), wie viele Runs/Erfolge er damit im
    Schnitt bekommt + die Gesamtkosten. Wenn `successes_needed` übergeben
    wird, zusätzlich die TATSÄCHLICHE Erfolgswahrscheinlichkeit (Binomial),
    genau die Zahl an Erfolgen oder mehr zu erreichen - nicht nur den Ø."""
    attempts = max(0.0, float(attempts or 0))
    prob = max(0.0, min(1.0, outcome["prob"]))
    expected_successes = attempts * prob
    expected_runs = expected_successes * outcome["runs"]
    dc_cost = sum(datacore_unit_costs or [])
    cost_per_attempt = dc_cost + (decryptor_cost or 0.0) + (job_cost_per_attempt or 0.0)
    total_cost = attempts * cost_per_attempt
    result = {"expected_successes": expected_successes, "expected_runs": expected_runs,
              "total_cost": total_cost, "cost_per_attempt": cost_per_attempt}
    if successes_needed is not None:
        result["confidence_actual"] = _binomial_p_at_least(
            int(round(attempts)), int(successes_needed), prob)
    return result


DEFAULT_INVENTION_TIME_THRESHOLD_DAYS = 3.0   # nur noch Info-Anzeige, kein Auswahlkriterium
_INVENTION_HIGH_STAKES_RUNS = 3               # nur noch Info-Anzeige, kein Auswahlkriterium


def invention_decryptor_options(base_runs, base_prob, target_runs, decryptor_list,
                                datacore_unit_costs, material_cost_per_run_0me,
                                decryptor_price_fn, build_seconds_per_run_0decryptor=None,
                                time_threshold_days=DEFAULT_INVENTION_TIME_THRESHOLD_DAYS):
    """Vergleicht ALLE Decryptoren (inkl. 'Kein Decryptor') nach der GESAMTEN
    ISK-Wirkung: Invention-Kosten (≥75%-Sicherheits-Versuchszahl × Datacores+
    Decryptor) PLUS der Materialkosten, die aus der resultierenden BPC-ME für
    `target_runs` Bau-Runs entstehen. Reine Gesamtgewinn-Optimierung - der
    Decryptor mit dem niedrigsten total_score gewinnt IMMER, ohne Ausnahme.

    (Frühere Versionen hatten hier zusätzlich Zeit-/Risiko-Tiebreaks, die bei
    ISK-mäßig "nahen" Optionen abseits der reinen Kostenrechnung wählten -
    das führte bei teuren Items wie Capitals dazu, dass eine scheinbar
    "kleine" Prozent-Toleranz in Wirklichkeit zig Millionen ISK Unterschied
    bedeutete und das Tool nicht mehr den wirklich gewinnstärksten Decryptor
    vorschlug. Auf Nutzerwunsch entfernt - `build_days`/`is_time_critical`
    werden weiter berechnet und zurückgegeben, dienen aber nur noch der
    Anzeige im Invention-Tab, nicht mehr der Auswahl.)

    material_cost_per_run_0me: Materialkosten EINES Bau-Runs dieses Items bei
    0% ME (aus build_cost mit me=0 nur für dieses Item isoliert) - die Basis,
    auf die die BPC-ME (2% Standard, je nach Decryptor modifiziert) angewandt
    wird. Struktur-/Rig-ME wird hier bewusst NICHT eingerechnet, da sie für
    jeden Decryptor gleich ausfällt und den Vergleich nicht verändert - nur
    der von der Decryptor-Wahl selbst abhängige Unterschied zählt.

    Rückgabe: nach total_score sortierte Liste (günstigster/gewinnstärkster
    zuerst, `out[0]["chosen_reason"]` ist immer "cost") von Dicts: {name,
    decryptor, outcome, successes_needed, expected_attempts, invention_cost,
    material_cost, total_score, actual_runs, waste_runs, build_days,
    is_time_critical, is_high_stakes}."""
    target_runs = max(0, int(target_runs or 0))
    dc_cost = sum(datacore_unit_costs or [])
    out = []
    for name, dv in (decryptor_list or []):
        outcome = invention_outcome(base_runs, base_prob, dv)
        if target_runs > 0:
            successes_needed = -(-target_runs // outcome["runs"])   # aufrunden
        else:
            successes_needed = 0
        prob = max(1e-6, outcome["prob"])
        expected_attempts = successes_needed / prob
        # WICHTIG: für die Kosten-Rechnung dieselbe ≥75%-Sicherheits-Versuchszahl
        # nutzen wie überall sonst im Tool (Kopfzeile/_inv_cost, Invention-Tab-
        # Anzeige) - sonst optimiert "Beste Wahl" den Erwartungswert, während
        # die tatsächliche Kopfzeile (Gewinn gesamt) längst die höhere,
        # realistischere ≥75%-Zahl nutzt und am Ende einen ANDEREN Decryptor
        # günstiger zeigt als den vorgeschlagenen.
        confident_attempts = invention_attempts_for_confidence(
            successes_needed, prob, DEFAULT_INVENTION_CONFIDENCE) or 0
        dcy_tid = dv[4] if dv else None
        dcy_cost = (decryptor_price_fn(dcy_tid) or 0.0) if dcy_tid else 0.0
        invention_cost = confident_attempts * (dc_cost + dcy_cost)
        material_cost = (material_cost_per_run_0me or 0.0) * \
            (1 - outcome["me_pct"] / 100.0) * target_runs
        actual_runs = successes_needed * outcome["runs"]
        build_days = None
        if build_seconds_per_run_0decryptor is not None:
            build_days = (build_seconds_per_run_0decryptor *
                          (1 - outcome["te_pct"] / 100.0) * target_runs) / 86400.0
        out.append({
            "name": name, "decryptor": dv, "outcome": outcome,
            "successes_needed": successes_needed,
            "expected_attempts": expected_attempts,
            "invention_cost": invention_cost, "material_cost": material_cost,
            "total_score": invention_cost + material_cost,
            "actual_runs": actual_runs,
            "waste_runs": max(0, actual_runs - target_runs),
            "build_days": build_days,
        })
    out.sort(key=lambda r: r["total_score"])
    is_time_critical = False
    if build_seconds_per_run_0decryptor is not None and target_runs > 0:
        ref_days = (build_seconds_per_run_0decryptor * (1 - 4 / 100.0) *
                   target_runs) / 86400.0     # "Kein Decryptor" = 4% TE Basis
        is_time_critical = ref_days > time_threshold_days
    is_high_stakes = 0 < target_runs <= _INVENTION_HIGH_STAKES_RUNS
    for r in out:
        r["is_time_critical"] = is_time_critical
        r["is_high_stakes"] = is_high_stakes
        r["chosen_reason"] = "cost"
    return out


def invention_best_decryptor_by_real_cost(type_id, qty, price_fn, recipes, opts,
                                          bp_id, decryptor_list):
    """Testet JEDEN Decryptor mit der ECHTEN production_plan-Rechnung (exakt
    dieselbe Formel, die die Bauplan-Kopfzeile für Material/Job-Kosten/
    Invention/Gewinn nutzt) - statt der Näherung in invention_decryptor_options
    (die nur die eigenen Materialien dieses einen Items isoliert schätzt, ohne
    z.B. mitzurechnen, dass eine höhere ME auch die Job-Installationskosten
    senkt, welche vom Materialwert abhängen). Damit kann das Ranking nicht
    mehr von dem abweichen, was am Ende wirklich in "Gewinn gesamt" steht -
    etwas teurer (ein production_plan-Aufruf pro Decryptor), aber nur bei
    Klick auf "Beste Wahl" nötig, nicht bei jeder Anzeige-Aktualisierung.

    type_id/qty: das TOP-LEVEL-Endprodukt und seine Bauplan-Menge (nicht
    zwingend dasselbe Item wie bp_id - bp_id kann auch eine T2-Zwischen-
    komponente sein, deren Decryptor-Wahl über production_plan korrekt durch
    den ganzen Baum propagiert).

    Rückgabe: nach total_cost sortierte Liste (günstigster/gewinnstärkster
    zuerst) von {name, decryptor, total_cost}."""
    out = []
    for name, dv in (decryptor_list or []):
        test_opts = dict(opts)
        dm = dict(opts.get("inv_decryptor_map") or {})
        dm[bp_id] = dv
        test_opts["inv_decryptor_map"] = dm
        try:
            test_plan = production_plan(type_id, qty, price_fn, recipes, test_opts)
            total_cost = float(test_plan["total_cost"]) if test_plan else float("inf")
        except Exception:
            total_cost = float("inf")
        out.append({"name": name, "decryptor": dv, "total_cost": total_cost})
    out.sort(key=lambda r: r["total_cost"])
    return out


def skill_time_factor(skills, is_reaction=False):
    """Zeit-Multiplikator aus Skills (kleiner = schneller).
    Fertigung: Industry −4 %/Stufe · Advanced Industry −3 %/Stufe.
    Reaktionen: NUR der Reactions-Skill −4 %/Stufe (Advanced Industry und die
    anderen Industry-Skills wirken laut CCP NICHT auf Reaktionen).
    Die %/Stufe kommen jetzt aus der SDE (_skill_time_bonus_pct), nicht mehr
    hartkodiert."""
    s = _norm_skill_keys(skills)
    if is_reaction:
        rea = s.get(_TIME_SKILL_REACTIONS, 0)
        pct = _skill_time_bonus_pct(_TIME_SKILL_REACTIONS, 4.0) / 100.0
        return max(0.1, 1.0 - pct * rea)
    adv = s.get(_TIME_SKILL_ADV_INDUSTRY, 0)
    ind = s.get(_TIME_SKILL_INDUSTRY, 0)
    pct_adv = _skill_time_bonus_pct(_TIME_SKILL_ADV_INDUSTRY, 3.0) / 100.0
    pct_ind = _skill_time_bonus_pct(_TIME_SKILL_INDUSTRY, 4.0) / 100.0
    return max(0.1, (1.0 - pct_adv * adv) * (1.0 - pct_ind * ind))


def science_time_factor(char_skills, needed_science_skills):
    """Zeit-Multiplikator (<=1) aus den item-spezifischen Science-Skills eines
    Charakters. Jeder von diesem Item benötigte Science-Skill gibt −1 %
    Fertigungszeit pro trainiertem Level. Multiplikativ, wie im Spiel.
    char_skills: {skill_id: level} · needed_science_skills: iterable skill_ids."""
    s = _norm_skill_keys(char_skills)
    f = 1.0
    for sid in (needed_science_skills or ()):
        try:
            sid = int(sid)
        except (TypeError, ValueError):
            continue
        lvl = s.get(sid, 0)
        if lvl:
            f *= (1.0 - 0.01 * lvl)
    return f


def job_slots(skills):
    """{skill_id: level} -> (mfg_slots, reaction_slots, science_slots). Basis 1 pro
    Typ; jede Mass-Production-/Mass-Reactions-/Laboratory-Operation-Stufe (+Advanced)
    gibt +1 parallelen Slot. Science-Slots gelten für Invention UND Kopieren.
    Max 11 Fertigungs-, 11 Reaktions- und 11 Science-Slots."""
    s = skills or {}
    mfg = 1 + sum(int(s.get(sid, 0) or 0) for sid in _SLOT_SKILLS_MFG)
    rea = 1 + sum(int(s.get(sid, 0) or 0) for sid in _SLOT_SKILLS_REACTION)
    sci = 1 + sum(int(s.get(sid, 0) or 0) for sid in _SLOT_SKILLS_SCIENCE)
    return mfg, rea, sci


def schedule_build(jobs, chars, te_factor=1.0, mfg_bp=1, react_bp=1, end_bp=None,
                   fuel_ids=None,
                   per_item_cap=None, per_item_runs_cap=None, stage_ziel=None):
    """Verteilt die Runs eines Bauplans auf Charaktere/Slots, damit alles möglichst
    gleichzeitig fertig wird – mit Aufteilung großer Items über mehrere Slots/Chars.
      jobs:  [{tid, name, runs, activity, base_time, is_end, te_factor?}]  (base_time
        = s/Run; optionales te_factor pro Job überschreibt den globalen te_factor
        – für Kategorie-TE wie T1-Hüllen/Fuel Blocks/Tools, die meist voll
        ausgeforscht sind, während das Endprodukt oft 0 % TE hat.)
      chars: [{id, name, mfg_slots, reaction_slots, can_mfg, can_react}]
      mfg_bp / react_bp / end_bp: wie viele Kopien JEDER benötigten Bau-/Reaktions-/
        Endprodukt-Blaupause du hast → so viele parallele Jobs eines Items sind maximal
        möglich. end_bp=None → wie mfg_bp (rückwärtskompatibel).
      per_item_cap: optional {tid: copies} - überschreibt mfg_bp/react_bp/end_bp für
        EINZELNE Items mit der ECHTEN Anzahl deiner Blaupausen dieses Items (z.B. aus
        ESI geladen) - für Items ohne Eintrag gilt weiter die pauschale Stufen-Zahl.
      per_item_runs_cap: optional {tid: max Runs je JOB} - eine BPC hat nur so
        viele Runs (bzw. SDE maxProductionLimit). Das Item wird dann in GANZEN
        Kopien geplant (Einheiten von m Runs, nur die letzte kleiner), die
        nacheinander auf einem Slot laufen koennen. Nutzer 19.09.2026 (Einherji
        II): "Der Runplaner denkt ich kann 17 Stueck mit einem Blueprint bauen
        ... gibts maximal 10 runs" und "moeglichst alle Blueprints am Ende
        verbraucht haben, nicht dass Blueprints mit angefangenen Runs stehen
        bleiben". Zuteilungen tragen dann "max_runs" und "parts".
      stage_ziel: optional {stage: Sekunden} - wie lange diese Stufe LAUFEN
        DARF. Nutzer 24.09.2026: "90 % der Nutzer setzen sich abends an den PC,
        lassen die Reactions laufen und loggen aus [...] am nächsten Tag um
        dieselbe Uhrzeit bauen sie weiter". Eine Stufe, die nachts ohnehin 23
        Stunden Zeit hat, braucht keine zehn Blaupausen mit je einem Run - sie
        braucht so WENIGE Jobs wie möglich, die in der Zeit fertig werden.
        Ohne Eintrag (oder 0) wird nur gestrafft: die Stufe ist ohnehin erst
        fertig, wenn ihr LÄNGSTES Item fertig ist, also dürfen alle kürzeren
        auf genau diese Zeit gestreckt werden - das kostet keine Minute und
        spart Slots und Blaupausen. Eine Zielzeit UNTER der so erreichbaren
        Dauer verkürzt nichts (dann fehlt es an Slots, nicht am Willen).
    Modell: drei Stufen nacheinander (Reaktionen → Komponenten → Endprodukt). Je Stufe
    ist jeder Slot eines geeigneten Chars ein „Track“. Ein Item wird über bis zu
    min(bp, #Tracks, runs) Tracks aufgeteilt (längster Job zuerst, auf die am wenigsten
    ausgelasteten Tracks). Zeit ≈ Runs·base_time. Rückgabe: assignments/stage_times/
    total_seconds/per_char."""
    from collections import defaultdict
    if end_bp is None:
        end_bp = mfg_bp

    def elig(activity):
        if activity == REACTION:
            key, flag = "reaction_slots", "can_react"
        else:
            key, flag = "mfg_slots", "can_mfg"
        # WER ANGEKREUZT IST, IST DABEI (Nutzer-Befund Sitzung 11: drei
        # Bau-Charaktere angekreuzt, alle Komponenten landeten auf EINEM).
        # Frueher stand hier zusaetzlich `and int(c.get(key, 0) or 0) >= 1` -
        # ein Charakter mit 0 Slots fiel damit KOMPLETT aus der Stufe, statt
        # nur wenig Arbeit zu bekommen. Zusammen mit der frueheren Planung
        # nach FREIEN Slots hiess das: wer gerade baute, war im Plan nicht
        # mehr vorhanden. Jetzt zaehlt nur noch das Kreuz; eine fehlende oder
        # 0-Slot-Angabe wird als EIN Slot gelesen, nicht als Ausschluss.
        return [(c["id"], c["name"], max(1, int(c.get(key, 0) or 0)))
                for c in chars if c.get(flag, True)]

    # FUEL IST EINE EIGENE STUFE VOR DEN REAKTIONEN (Nutzer, Sitzung 8:
    # "Fuel brauche ich um die Stufe 1 Reactions zu bauen"). Fuel Blocks sind
    # FERTIGUNGS-Jobs und landeten deshalb bei den Komponenten - also HINTER
    # den Reaktionen, die sie verbrauchen. Wer den Runplaner von oben nach
    # unten abarbeitet, stand damit ohne Treibstoff da.
    # UNREFINED-REAKTIONEN ALS EIGENE STUFE VOR DEN INTERMEDIATES (Nutzer
    # 19.09.2026: "an erster Stelle ueber den Intermediate Reactions - schon
    # aus Zeitgruenden, weil sie mehr Zeit brauchen"; erst danach kann das
    # Unrefined-Produkt reprocesst werden). Job-Feld "is_unrefined".
    stages = {"fuel": [], "unrefined": [], "reaction_1": [], "reaction_2": [],
              "component": [], "end": []}
    _fuel = set(fuel_ids or ())
    for j in jobs:
        if j["activity"] == REACTION and j.get("is_unrefined"):
            stages["unrefined"].append(j)
        elif j["activity"] == REACTION:
            # Stufe 1 (Intermediate) MUSS fertig sein, bevor Stufe 2 (Composite)
            # sie als Zutat verbrauchen kann - deshalb zwei getrennte, nacheinander
            # laufende Phasen statt einer gemeinsamen "reaction"-Phase (die
            # Composite-Jobs vorher fälschlich parallel zu ihren eigenen
            # Zutaten-Reaktionen einplante, statt zu warten, bis die fertig sind).
            tier = j.get("reaction_tier") or 2
            stages["reaction_1" if tier == 1 else "reaction_2"].append(j)
        elif j.get("is_end"):
            stages["end"].append(j)
        elif j.get("is_fuel") or j.get("tid") in _fuel:
            stages["fuel"].append(j)
        else:
            stages["component"].append(j)

    assignments = []
    stage_times = {"fuel": 0.0, "unrefined": 0.0, "reaction_1": 0.0, "reaction_2": 0.0,
                   "component": 0.0, "end": 0.0}
    # WIE KURZ KOENNTE DIESE STUFE? Die gestraffte Dauer OHNE Zielzeit - also
    # das, was mit den vorhandenen Slots ueberhaupt geht. Der Regler in der
    # Oberflaeche beginnt genau dort: links steht die Zeit, die man sowieso
    # braucht, nach rechts verlaengert man sie (Nutzer 24.09.2026).
    stage_min_times = {"fuel": 0.0, "unrefined": 0.0, "reaction_1": 0.0,
                       "reaction_2": 0.0, "component": 0.0, "end": 0.0}
    # WER SETZT DIESE UNTERGRENZE? {stage: {tid, name, runs, slots, seconds}}
    stage_min_by = {}
    per_char = defaultdict(float)
    per_char_stage = {}
    job_durs = {}          # (cid, stage) -> Liste einzelner Job-Dauern (Sekunden)
    name_of = {c["id"]: c["name"] for c in chars}

    for stage in ("fuel", "unrefined", "reaction_1", "reaction_2", "component", "end"):
        jlist = stages[stage]
        if not jlist:
            continue
        is_reaction = stage.startswith("reaction") or stage == "unrefined"
        act = REACTION if is_reaction else MANUFACTURING
        if is_reaction:
            bp_cap = max(1, int(react_bp))
        elif stage == "end":
            bp_cap = max(1, int(end_bp))
        else:
            bp_cap = max(1, int(mfg_bp))
        # Pro-Item-Override (echte Blaupausen-Anzahl EINES bestimmten Items,
        # z.B. aus ESI geladen) - hat Vorrang vor der pauschalen Stufen-Zahl.
        _pic = per_item_cap or {}

        def _cap_for(tid):
            v = _pic.get(tid)
            return max(1, int(v)) if v else bp_cap
        _prc = per_item_runs_cap or {}

        def _rcap_for(tid):
            """Max Runs je Job dieses Items - None = kein Limit bekannt."""
            v = _prc.get(tid)
            try:
                v = int(v or 0)
            except (TypeError, ValueError):
                v = 0
            return v if v >= 1 else None
        machines = elig(act)
        if not machines:
            continue
        factor = {c["id"]: (c.get("react_time", 1.0) if is_reaction
                            else c.get("mfg_time", 1.0)) for c in chars}
        # Science-Skill-Zeitbonus PRO (Charakter, Job): jedes Item braucht bestimmte
        # Science-Skills (je −1 %/Level), und jeder Charakter hat andere Level. Nur
        # für Fertigung relevant (Reaktionen haben keine solchen Skills).
        _char_all_skills = {c["id"]: (c.get("all_skills") or {}) for c in chars}
        sci_factor = {}
        if not is_reaction:
            for j in jlist:
                need = j.get("sci_skills") or ()
                if not need:
                    continue
                for c in chars:
                    sci_factor[(c["id"], j["tid"])] = science_time_factor(
                        _char_all_skills.get(c["id"], {}), need)
        # Tracks pro Char gruppiert – ein Item bleibt komplett bei EINEM Char, der
        # dafür bis zu bp_cap seiner Slots nutzt. Verschiedene Items werden über die
        # Chars verteilt (das am wenigsten ausgelastete zuerst).
        # Tracks VERSCHRÄNKT über die Chars aufbauen (round-robin): so verteilt die
        # „am wenigsten ausgelastet zuerst“-Wahl gleiche Last automatisch über mehrere
        # Chars, statt ein Item komplett auf den ersten Char zu legen.
        char_tracks = {cid: [] for cid, _nm, _s in machines}
        tracks = []
        maxslots = max((s for _c, _n, s in machines), default=0)
        for si in range(maxslots):
            for cid, _nm, slots in machines:
                if si < slots:
                    char_tracks[cid].append(len(tracks))
                    tracks.append(cid)
        load = [0.0] * len(tracks)
        tr_runs = defaultdict(float)                 # (track, tid, name) → runs
        item_dur = {}                                # (cid, tid, name) → Sekunden
        tv_by_track = {}                             # (track, tid, name) → Zeit/Run
        # Last je Charakter (für "ganze Items pro Char"-Zuteilung).
        char_load = {cid: 0.0 for cid, _nm, _s in machines}
        cid_slots = {cid: s for cid, _nm, s in machines}
        # RUNS-DECKEL -> GANZE KOPIEN (Nutzer 19.09.2026: "Bei fertig
        # geforschten Blueprints moechte man moeglichst alle Blueprints am
        # Ende verbraucht haben, nicht dass Blueprints mit angefangenen Runs
        # stehen bleiben"). Ein Item mit Deckel m wird in EINHEITEN von m
        # Runs geplant (330 Runs / 10 = 33 Jobs a 10) - die Einheiten werden
        # auf Charaktere und Slots verteilt, nie die Runs einzeln. Nur die
        # letzte Einheit ist kleiner (Rest). Preis: ein Slot kann statt 17
        # Runs (10 + 7) 20 Runs (10 + 10) bekommen - dafuer bleibt keine
        # halbe Kopie liegen. Die Job-Rechnung unten arbeitet mit
        # `runs` = Einheiten und `base_time` = m x Zeit je Run; erst
        # _place_on_tracks rechnet in Runs zurueck.
        _unit = {}                                   # tid -> (m, Runs gesamt)
        _jl = []
        for j in jlist:
            _m = _rcap_for(j["tid"])
            _R0 = int(j["runs"])
            if _m and _R0 >= 1:
                # auch unter dem Deckel: 8 Runs = EINE Kopie mit 8 Runs,
                # nicht 8 Kopien mit je 1 Run (jede davon bliebe angefangen).
                _unit[j["tid"]] = (_m, _R0)
                _jl.append({**j, "runs": -(-_R0 // _m), "base_time": j["base_time"] * _m})
            else:
                _jl.append(j)
        jlist = _jl
        tr_chunks = {}                               # (track, tid, name) → Runs je Job

        def _place_on_tracks(track_ids, tid, name, R, tbase):
            """Verteilt R Runs eines Items auf die gegebenen Tracks (Wasserfüllung),
            aktualisiert load/tr_runs. Gibt die Dauer (max belegte Zeit) zurück.
            Bei einem Item mit Runs-Deckel ist R die Zahl der EINHEITEN (ganze
            Kopien) und tbase die Zeit je Einheit."""
            P = len(track_ids)
            if P < 1:
                return 0.0
            tv = [tbase * factor.get(tracks[i], 1.0)
                  * sci_factor.get((tracks[i], tid), 1.0) for i in track_ids]
            lo = min(load[i] for i in track_ids)
            hi = max(load[i] for i in track_ids) + R * max(tv)
            for _ in range(60):
                T = (lo + hi) / 2
                cap = sum(max(0.0, (T - load[track_ids[k]]) / tv[k]) for k in range(P))
                if cap >= R:
                    hi = T
                else:
                    lo = T
            T = hi
            rf = [max(0.0, (T - load[track_ids[k]]) / tv[k]) for k in range(P)]
            ri = [int(x) for x in rf]
            for k in sorted(range(P), key=lambda k: -(rf[k] - ri[k]))[:R - sum(ri)]:
                ri[k] += 1
            _um = _unit.get(tid)
            if _um:
                # Einheiten -> Runs: jede Einheit ist eine volle Kopie (m
                # Runs); der Rest (letzte Einheit) liegt auf dem Slot, der
                # am spaetesten fertig wuerde - dort spart er am meisten.
                _m, _R0 = _um
                _rem = _R0 % _m
                runs_k = [ri[k] * _m for k in range(P)]
                chunks_k = [[_m] * ri[k] for k in range(P)]
                if _rem and sum(ri) > 0:
                    _kr = max((k for k in range(P) if ri[k] >= 1),
                              key=lambda k: (load[track_ids[k]] + ri[k] * tv[k], -k))
                    runs_k[_kr] -= (_m - _rem)
                    chunks_k[_kr][-1] = _rem
                tv_run = [x / _m for x in tv]
            else:
                runs_k = list(ri)
                chunks_k = [[ri[k]] for k in range(P)]
                tv_run = tv
            dur = 0.0
            for k, ti in enumerate(track_ids):
                if ri[k] < 1:
                    continue
                _d = runs_k[k] * tv_run[k]
                load[ti] += _d
                tr_runs[(ti, tid, name)] += runs_k[k]
                tr_chunks[(ti, tid, name)] = list(chunks_k[k])
                tv_by_track[(ti, tid, name)] = tv_run[k]
                key = (tracks[ti], tid, name)
                item_dur[key] = max(item_dur.get(key, 0.0), _d)
                dur = max(dur, _d)
            return dur

        jobs_sorted = sorted(jlist, key=lambda x: -(x["runs"] * x["base_time"]
                                                    * x.get("te_factor", te_factor)))

        # ===== Phase 1: Items als GANZES auf die Chars verteilen (Balance) =====
        # Jedes Item kommt komplett zu einem Char (kein BPO-Schieben). Zuteilung
        # nach geschätzter Last, längstes Item zuerst an den am wenigsten belasteten
        # Char. Split eines Items über mehrere Chars nur, wenn es allein den Plan
        # massiv verlängern würde (>1.5x faire Ziel-Last).
        n_chars = max(1, len(char_load))
        total_slots = len(tracks)
        n_items = len([j for j in jobs_sorted if int(j["runs"]) >= 1])

        # ----- 1-WELLE-MODUS (Priorität des Nutzers): alle Slots als EIN Pool -----
        # Wenn mind. so viele Slots wie Items da sind, passt (mit Aufteilung großer
        # Items) alles in EINE Welle. Dann verteilen wir die Jobs global über ALLE
        # Slots aller Chars, statt Items fest an je einen Char zu binden. So bleibt
        # kein Slot leer und niemand muss eine zweite Welle fahren.
        if total_slots >= n_items and n_items > 0:
            # Jedes Item bekommt zunächst so viele Slots, wie es fair braucht
            # (proportional zur Arbeit), mind. 1, höchstens bp_cap bzw. Runs.
            work_of = {}
            for j in jobs_sorted:
                R = int(j["runs"])
                if R < 1:
                    continue
                tb = j["base_time"] * j.get("te_factor", te_factor)
                work_of[j["tid"]] = R * tb
            total_w = sum(work_of.values()) or 1.0
            # Slot-Budget je Item proportional zur Arbeit, gerundet, dann auf die
            # verfügbaren Slots einpegeln. WICHTIG (korrigiert): zusätzlich auf
            # höchstens 2 Charaktere Kapazität deckeln (der bisherige Deckel war
            # nur die Blaupausen-Kopien-Zahl - wer viele BPCs per ESI geladen hat,
            # bekam dadurch ein Budget quer über 5+ Charaktere, obwohl 1-2 Chars
            # mit voll ausgelasteten Slots dasselbe in vergleichbarer Zeit
            # geschafft hätten, nur ohne die Blaupausen/Material auf 5 Leute
            # verteilen zu müssen).
            max_char_slots = max((s for _c, _n, s in machines), default=1)
            max_reasonable = max(1, 2 * max_char_slots)

            def _deckel_slots(tid):
                # GANZE KOPIEN (Nutzer 19.09.2026: "ich kann nicht 18
                # Blueprints laufen lassen ... auf andere Charaktere
                # verteilen"): ein Item mit Runs-Deckel darf ALLE Slots aller
                # angekreuzten Charaktere nutzen - die Kopien liegen ohnehin
                # getrennt vor, der 2-Charaktere-Deckel gilt hier nicht.
                return R if tid in _unit else max_reasonable
            budget = {}
            for j in jobs_sorted:
                R = int(j["runs"])
                if R < 1:
                    continue
                cap_i = min(int(_cap_for(j["tid"])), R, _deckel_slots(j["tid"]))
                want = max(1, round(total_slots * work_of[j["tid"]] / total_w))
                budget[j["tid"]] = min(want, cap_i)
            # Rest-Slots (falls Summe < total_slots) an die Items mit der höchsten
            # Zeit-pro-Slot geben (die profitieren am meisten), bis alles verteilt
            # oder alle bei bp_cap/Runs sind.
            def _slot_used():
                return sum(budget.values())
            guard = 0
            while _slot_used() < total_slots and guard < total_slots * 4:
                guard += 1
                best = None; best_t = -1
                for j in jobs_sorted:
                    R = int(j["runs"])
                    if R < 1:
                        continue
                    s = budget[j["tid"]]
                    if s >= min(int(_cap_for(j["tid"])), R, _deckel_slots(j["tid"])):
                        continue
                    tb = j["base_time"] * j.get("te_factor", te_factor)
                    t_per = (R * tb) / s
                    if t_per > best_t:
                        best_t = t_per; best = j["tid"]
                if best is None:
                    break
                budget[best] += 1
            # ===== ZIELZEIT / STRAFFUNG (Nutzer 24.09.2026) =====
            # BIS HIERHER wurde so breit wie moeglich verteilt - das ergibt die
            # SCHNELLSTE Stufe, aber auch zehn Blaupausen mit je einem Run.
            # Die Stufe ist jedoch erst fertig, wenn ihr LAENGSTES Item fertig
            # ist; jedes kuerzere darf bis dahin gestreckt werden, ohne dass
            # der Plan eine Minute spaeter fertig ist. Genau das passiert hier:
            # jedes Item behaelt nur so viele Slots, wie es fuer die Zeit T
            # braucht. T ist die Dauer der Stufe - oder die Zielzeit des
            # Nutzers, wenn er mehr Zeit hat als noetig (nachts, ueber Tage).
            # EINE ZIELZEIT UNTER DER ERREICHBAREN DAUER AENDERT NICHTS: mehr
            # Slots als hier verteilt gibt es nicht, also waere jede kuerzere
            # Zahl ein Versprechen, das der Plan nicht halten kann.
            # DIE ZEIT JE RUN, WIE DER SLOT SIE WIRKLICH SIEHT (Nutzer
            # 25.09.2026, planer_diagnose.txt nachgestellt: "as fast as
            # possible" zeigte 7 h, das Spiel 5 h 36 m; "23 h eingestellt"
            # ergab 15 h 26 m). `work_of` rechnet mit base_time x TE - OHNE
            # den Zeitfaktor des Charakters (Reactions V = x0.8, bei ihm
            # 6'318 s statt 5'054 s je Run). Damit war jede Mindestdauer
            # ein Viertel zu lang und die Straffung hielt ein Slot mehr als
            # noetig (66 Runs: ceil(66x6318/82800) = 6 Slots a 11 Runs =
            # 15 h 26 m statt 5 Slots a 14 Runs = 19 h 40 m). Hier zaehlt
            # der SCHNELLSTE zulaessige Charakter - er bekommt die Slots
            # auch zuerst (char_cycle unten ist nach factor sortiert).
            # Und: eine Kopie faehrt GANZE Runs. 66 Runs auf 19 Kopien sind
            # 4 Runs auf der vollsten, nicht 3,47 - die Stufe dauert
            # 4 x 5'054 s = 5 h 37 m, exakt was das Spiel zeigt.
            def _sek_je_run(j):
                _tb = j["base_time"] * j.get("te_factor", te_factor)
                _fb = min((factor.get(_c, 1.0)
                           * sci_factor.get((_c, j["tid"]), 1.0)
                           for _c, _n, _s in machines), default=1.0)
                return _tb * _fb
            _dauer_st = 0.0
            _wer_st = None
            for j in jobs_sorted:
                _s0 = budget.get(j["tid"]) or 0
                if _s0 >= 1 and work_of.get(j["tid"]):
                    _d_j = (math.ceil(int(j["runs"]) / _s0)
                            * _sek_je_run(j))
                    if _d_j > _dauer_st:
                        # WER BREMST? (Nutzer 24.09.2026: "es ist mir nicht
                        # moeglich, bei Composite Reactions 2 Stunden
                        # einzustellen".) Eine Untergrenze ohne Begruendung
                        # sieht aus wie eine Sperre. Der Verursacher ist das
                        # Item mit der laengsten Arbeit je Slot - genau das,
                        # was auch die Stufendauer setzt.
                        _dauer_st = _d_j
                        _wer_st = (j["tid"], j.get("name") or "", int(j["runs"]),
                                   _s0)
            if _wer_st is not None:
                stage_min_by[stage] = {
                    "tid": _wer_st[0], "name": _wer_st[1],
                    "runs": _wer_st[2], "slots": _wer_st[3],
                    "seconds": _dauer_st}
            stage_min_times[stage] = _dauer_st
            if _dauer_st > 0:
                _T_st = max(_dauer_st, float((stage_ziel or {}).get(stage) or 0.0))
                for j in jobs_sorted:
                    _tid_st = j["tid"]
                    _s0 = budget.get(_tid_st) or 0
                    if _s0 <= 1 or not work_of.get(_tid_st):
                        continue
                    # GANZE KOPIEN WERDEN NICHT GESTRAFFT (Nutzer-Befund
                    # 24.09.2026: "bei Endprodukt hat Peanut Motor 2 Wellen
                    # bekommen, warum? da gibt es noch mehr Charaktere zur
                    # Auswahl [...] da koennte man sich die 2. Welle sparen").
                    # Bei einem Item mit Runs-Deckel liegt die ZAHL DER JOBS
                    # fest - 13 Kopien a 4 Runs bleiben 13 Jobs, ob sie
                    # nebeneinander oder nacheinander laufen. Weniger Slots
                    # sparen dort also keine einzige Blaupause; sie zwingen
                    # denselben Charakter nur, spaeter noch einmal ranzugehen
                    # (die zweite Welle). Gespart wird nur, wo der Planer die
                    # Runs wirklich zusammenfassen kann.
                    if _tid_st in _unit:
                        continue
                    # WIE VIELE GANZE RUNS PASSEN IN T? So viele bekommt jede
                    # Kopie, und daraus folgt die Zahl der Kopien. So bleibt
                    # die Stufe unter T (ceil(R/n) x t <= T), und bei 23 h
                    # Ziel bekommt eine Kopie 16 Runs a 1 h 24 m = 22 h 28 m
                    # statt 11 (Nutzer: "obwohl man bis auf 3 Tage+
                    # hochschrauben koennte"). 1e-9: sonst macht ein
                    # Rundungsrest aus genau passenden Runs einen Run weniger.
                    _je = max(1, int(math.floor(_T_st / _sek_je_run(j) + 1e-9)))
                    _noetig = max(1, int(math.ceil(int(j["runs"]) / _je)))
                    if _noetig < _s0:
                        budget[_tid_st] = _noetig
            # Jetzt die Slots (Tracks) den Items zuweisen. WICHTIG (korrigiert):
            # NICHT mehr strikt round-robin pro einzelnem Slot - das hat ein Item
            # unnötig über ALLE Chars verteilt, selbst wenn ein einzelner Char mit
            # genug freien Slots die komplette Menge genauso schnell geschafft
            # hätte (z.B. 19 Runs auf EINEM 10-Slot-Char in 2 Wellen statt auf 7
            # Chars mit je nur 1 belegten Slot - gleiche Zeit, aber plötzlich
            # müssen Blueprint UND Material zu 7 statt zu 1-2 Chars geschoben
            # werden). Jetzt: der aktuell schnellste Char mit noch freien Slots
            # bekommt so viele Slots wie er hat, ERST wenn er ausgeschöpft ist,
            # kommt der nächste dran - Streuung über mehrere Chars passiert
            # weiterhin automatisch, aber nur wenn wirklich nötig (Item braucht
            # mehr Slots, als ein einzelner Char hat, oder der nächste Char in
            # der Zuteilungsreihenfolge ist für ein ANDERES Item dran, weil
            # dieser hier schon ausgelastet ist).
            tracks_by_char = {}
            for i in range(len(tracks)):
                tracks_by_char.setdefault(tracks[i], []).append(i)
            char_cycle = sorted(tracks_by_char.keys(),
                               key=lambda c: factor.get(c, 1.0))
            free_ptr = {c: 0 for c in char_cycle}
            ci = 0

            def _next_free_track():
                nonlocal ci
                for _ in range(len(char_cycle)):
                    c = char_cycle[ci % len(char_cycle)]
                    if free_ptr[c] < len(tracks_by_char[c]):
                        ti = tracks_by_char[c][free_ptr[c]]
                        free_ptr[c] += 1
                        return ti
                    ci += 1   # dieser Char ist ausgeschöpft -> erst DANN weiter
                return None

            # Items nach Arbeit absteigend zuweisen (große zuerst -> streuen breit).
            for j in sorted(jobs_sorted, key=lambda x: -work_of.get(x["tid"], 0)):
                R = int(j["runs"])
                if R < 1:
                    continue
                s = budget[j["tid"]]
                use = []
                for _ in range(s):
                    ti = _next_free_track()
                    if ti is None:
                        break
                    use.append(ti)
                if not use:
                    ti = _next_free_track()
                    if ti is not None:
                        use = [ti]
                if not use and tracks:
                    # SLOTS ERSCHOEPFT - trotzdem einplanen (Fund Sitzung 7,
                    # beim Blackbird-Vorfall aufgefallen): frueher blieb `use`
                    # leer und das Item fiel STILL aus dem Runplaner heraus -
                    # 6 gebrauchte Blackbird-Runs waren schlicht nicht mehr da,
                    # ohne Hinweis. Ein Slot kann zwei Items nacheinander
                    # fahren; der am wenigsten belastete Track ist dafuer die
                    # ehrlichste Wahl (das Item laeuft dort in einer spaeteren
                    # Welle). Lieber eine zweite Welle zeigen als Arbeit
                    # verschweigen (Regel 6).
                    use = [min(range(len(tracks)), key=lambda i: load[i])]
                if use:
                    tbase = j["base_time"] * j.get("te_factor", te_factor)
                    _place_on_tracks(use, j["tid"], j["name"], R, tbase)
            # Fertig für diese Stufe – agg/Rückgabe unten übernimmt.
            _single_wave = True
        else:
            _single_wave = False

        fair_target = 0.0
        if not _single_wave:
            total_work = 0.0
            for j in jobs_sorted:
                R0 = int(j["runs"])
                if R0 < 1:
                    continue
                tb0 = j["base_time"] * j.get("te_factor", te_factor)
                total_work += (R0 * tb0) / max(1, _cap_for(j["tid"]))
            fair_target = total_work / n_chars if n_chars else total_work
        # char_items[cid] = Liste von (tid, name, runs, tbase, split_over_chars?)
        char_items = {cid: [] for cid, _nm, _s in machines}
        est_load = {cid: 0.0 for cid, _nm, _s in machines}
        split_jobs = []      # Items, die über mehrere Chars gesplittet werden
        if not _single_wave:
          for j in jobs_sorted:
            R = int(j["runs"])
            if R < 1:
                continue
            tbase = j["base_time"] * j.get("te_factor", te_factor)
            _sf = lambda c: factor.get(c, 1.0) * sci_factor.get((c, j["tid"]), 1.0)
            cand = sorted(est_load.keys(),
                          key=lambda c: (est_load[c], tbase * _sf(c)))
            best_cid = cand[0]
            # grobe Item-Dauer auf bp_cap eigenen Slots (für Split-Entscheidung)
            item_time = (R * tbase * _sf(best_cid)) / max(1, _cap_for(j["tid"]))
            if len(char_load) > 1 and fair_target > 0 and item_time > fair_target * 1.5:
                split_jobs.append(j)          # später über alle Chars verteilen
            else:
                char_items[best_cid].append((j["tid"], j["name"], R, tbase))
                est_load[best_cid] += item_time

        # ===== Phase 2: pro Char die SLOTS zuweisen =====
        # Ziel (deine Priorität): ALLE Items eines Chars sollen in EINE Welle passen
        # -> jedes Item bekommt erst 1 Slot. Übrige freie Slots dann auf die längsten
        # Items verteilen (bis zu bp_cap pro Item), um Zeit zu sparen.
        for cid, items in char_items.items():
            cslots = cid_slots[cid]
            my_tracks = char_tracks[cid]
            if not items:
                continue
            n_items = len(items)
            # Slot-Budget je Item bestimmen.
            slots_per_item = {}
            if n_items >= cslots:
                # Mehr (oder gleich viele) Items als Slots -> jedes 1 Slot, der Rest
                # läuft in weiteren Wellen (unvermeidbar).
                for (tid, nm, R, tb) in items:
                    slots_per_item[(tid, nm)] = 1
            else:
                # Alle Items passen gleichzeitig: jedes mind. 1 Slot.
                for (tid, nm, R, tb) in items:
                    slots_per_item[(tid, nm)] = 1
                free = cslots - n_items
                # Freie Slots auf die Items verteilen, die am meisten davon
                # profitieren (längste Rest-Zeit pro belegtem Slot), bis bp_cap.
                while free > 0:
                    # aktuelle Zeit je Item = R*tb / slots
                    best = None; best_time = -1
                    for (tid, nm, R, tb) in items:
                        s = slots_per_item[(tid, nm)]
                        if s >= min(_cap_for(tid), R):        # nicht über bp_cap / runs
                            continue
                        cur = (R * tb) / s
                        if cur > best_time:
                            best_time = cur; best = (tid, nm)
                    if best is None:
                        break
                    slots_per_item[best] += 1
                    free -= 1
            # Items auf ihre zugewiesenen Slots legen (die Tracks des Chars).
            next_track = 0
            for (tid, nm, R, tb) in items:
                s = slots_per_item[(tid, nm)]
                use = my_tracks[next_track:next_track + s]
                if not use:            # Slots erschöpft (mehr Items als Slots)
                    use = [my_tracks[next_track % len(my_tracks)]]
                _place_on_tracks(use, tid, nm, R, tb)
                next_track = (next_track + s)
                if next_track >= len(my_tracks):
                    next_track = 0     # nächste Welle auf denselben Slots
        # Gesplittete Items über alle Chars verteilen. WICHTIG: nicht stur die
        # bp_cap leersten Tracks nehmen (die liegen oft alle auf EINEM leeren Char
        # -> das Item landet doch nur dort). Stattdessen die Slots über möglichst
        # VIELE verschiedene Chars streuen, damit die Last sich verteilt. bp_cap
        # (= besessene Blueprints/Kopien) bleibt die harte Obergrenze paralleler
        # Jobs – wir splitten nie auf mehr Slots, als du Blaupausen hast.
        for j in split_jobs:
            R = int(j["runs"]); tbase = j["base_time"] * j.get("te_factor", te_factor)
            P = max(1, min(_cap_for(j["tid"]), len(tracks), R))
            # Tracks nach Char gruppieren, innerhalb jedes Chars nach Last sortiert.
            by_char = {}
            for i in range(len(tracks)):
                by_char.setdefault(tracks[i], []).append(i)
            for cid in by_char:
                by_char[cid].sort(key=lambda i: load[i])
            # Chars nach aktueller Char-Last (leerster zuerst) durchgehen und
            # reihum je einen Slot picken (round-robin), bis P Slots gewählt sind.
            char_order = sorted(by_char.keys(),
                                key=lambda c: min((load[i] for i in by_char[c]),
                                                  default=0.0))
            picks = []
            ptr = {c: 0 for c in by_char}
            while len(picks) < P:
                progressed = False
                for c in char_order:
                    if len(picks) >= P:
                        break
                    lst = by_char[c]
                    if ptr[c] < len(lst):
                        picks.append(lst[ptr[c]]); ptr[c] += 1
                        progressed = True
                if not progressed:
                    break
            _place_on_tracks(picks, j["tid"], j["name"], R, tbase)
        stage_times[stage] = max(load) if load else 0.0
        agg = defaultdict(lambda: [0.0, 0])          # (cid, tid, name) → [runs, #jobs]
        agg_parts = {}                               # (cid, tid, name) → Runs je Job (nur mit Deckel)
        # Einzelne Job-Dauern je Track sammeln (für die Wellen-Berechnung: jeder
        # Job belegt einen Slot für seine Dauer). tv_by_track = Zeit/Run je Track.
        for (ti, tid, nm), r in tr_runs.items():
            a = agg[(tracks[ti], tid, nm)]
            cid = tracks[ti]
            _tv = tv_by_track.get((ti, tid, nm), 0.0)
            # RUNS-DECKEL JE JOB (BPC-Runs / maxProductionLimit): die Runs
            # dieses Slots sind Jobs von hoechstens `_m` Runs (ganze Kopien,
            # s. _unit), die NACHEINANDER auf demselben Slot laufen - jede
            # Kopie ist ein Start und zaehlt bei den Wellen mit.
            _chunks = [c for c in tr_chunks.get((ti, tid, nm), [int(round(r))]) if c >= 1]
            if not _chunks:
                _chunks = [int(round(r))]
            a[0] += r; a[1] += len(_chunks)
            if _rcap_for(tid):
                agg_parts.setdefault((cid, tid, nm), []).extend(_chunks)
            for _ch in _chunks:
                dur = _ch * _tv
                if dur > 0:
                    job_durs.setdefault((cid, stage), []).append(dur)
        for (cid, tid, nm), (r, njobs) in agg.items():
            _asg = {"char_id": cid, "char_name": name_of.get(cid, str(cid)),
                    "tid": tid, "name": nm, "runs": int(round(r)),
                    "jobs": njobs, "seconds": item_dur.get((cid, tid, nm), 0.0),
                    "activity": act, "stage": stage}
            _m = _rcap_for(tid)
            if _m:
                _asg["max_runs"] = _m
                # Runs je Job, groesste zuerst (10 + 7 statt 9 + 8): so, wie
                # die Slots sie wirklich fahren - die Anzeige uebernimmt das.
                _asg["parts"] = sorted(agg_parts.get((cid, tid, nm), []), reverse=True)
                # Sekunden je Run (laengster Slot) - fuer die Wellen-Zeilen
                # im Runplaner (Zeit einer Welle = groesste Kopie x tv).
                _asg["tv"] = max((tv_by_track.get((ti, tid, nm), 0.0)
                                  for ti in range(len(tracks)) if tracks[ti] == cid), default=0.0)
            assignments.append(_asg)
        char_load = defaultdict(float)               # Char-Zeit = max seiner Tracks
        for ti, cid in enumerate(tracks):
            char_load[cid] = max(char_load[cid], load[ti])
        for cid, cl in char_load.items():
            per_char[cid] += cl
            # Pro Stufe pro Char die echte Last merken (wann dieser Char in dieser
            # Stufe mit ALLEN seinen Slots durch ist – Wasserfüll-Ergebnis).
            per_char_stage[(cid, stage)] = cl

    # Wellen je Char+Stufe: bei deinem Workflow ("erst wenn ALLE Slots leer sind,
    # alle neu befüllen") laufen die Jobs in Runden von je 'slots' Stück. Jede
    # Runde dauert so lang wie ihr LÄNGSTER Job. Die längsten Jobs zuerst.
    slots_lookup = {}
    for c in chars:
        slots_lookup[c["id"]] = (max(1, int(c.get("mfg_slots", 1) or 1)),
                                 max(1, int(c.get("reaction_slots", 1) or 1)))
    waves_by_char_stage = {}
    for (cid, stage), durs in job_durs.items():
        mfg_c, react_c = slots_lookup.get(cid, (1, 1))
        # "unrefined" ist eine Reaktionsstufe (siehe is_reaction oben).
        cslots = (react_c if (stage.startswith("reaction") or stage == "unrefined")
                  else mfg_c)
        ds = sorted(durs, reverse=True)
        waves = []
        for i in range(0, len(ds), cslots):
            batch = ds[i:i + cslots]
            if batch:
                waves.append(max(batch))    # Runde dauert wie ihr längster Job
        waves_by_char_stage[f"{cid}|{stage}"] = waves

    total = (stage_times["fuel"] + stage_times["unrefined"] + stage_times["reaction_1"]
            + stage_times["reaction_2"]
            + stage_times["component"] + stage_times["end"])
    return {"assignments": assignments, "stage_times": stage_times,
            "stage_min_times": stage_min_times,
            "stage_min_by": stage_min_by,
            "total_seconds": total, "per_char": dict(per_char),
            "per_char_stage": {f"{cid}|{st}": v
                               for (cid, st), v in per_char_stage.items()},
            "waves_by_char_stage": waves_by_char_stage}
