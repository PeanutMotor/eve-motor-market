"""Local SQLite persistence: linked characters, imported transactions,
and a cache of typeID -> item name."""
import os
import shutil
import sqlite3
import time

from . import config


def backup_db(reason: str = "") -> str | None:
    """Sichere Kopie der gesamten Datenbank anlegen, BEVOR etwas Unwiderrufliches
    passiert (z. B. Charakter löschen -> löscht dessen Transaktions-Historie).
    ESI liefert nur die jüngsten ~30 Tage zurück, ältere Historie wächst lokal
    über die Zeit an -- einmal gelöscht ist sie also weg. Diese Backups sind das
    Sicherheitsnetz.

    Legt die Kopie in <appdata>/backups/ledger-<zeitstempel>[-reason].db ab und
    hält nur die letzten 15 Backups (ältere werden entfernt). Gibt den Pfad der
    Kopie zurück, oder None, wenn keine DB existiert / das Backup fehlschlägt.

    WICHTIG: Vor dem Kopieren wird der WAL-Inhalt in die Haupt-DB geschrieben
    (checkpoint), sonst würde eine reine Datei-Kopie die letzten, noch nur im
    -wal liegenden Änderungen verpassen."""
    src = config.db_path()
    if not os.path.exists(src):
        return None
    try:
        # WAL in die Haupt-DB einchecken, damit die Kopie wirklich vollständig ist.
        try:
            c = sqlite3.connect(src, timeout=30)
            c.execute("PRAGMA wal_checkpoint(FULL)")
            c.close()
        except Exception:
            pass
        bdir = os.path.join(config.app_data_dir(), "backups")
        os.makedirs(bdir, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        safe = "".join(ch for ch in reason if ch.isalnum() or ch in "-_")[:40]
        name = f"ledger-{stamp}" + (f"-{safe}" if safe else "") + ".db"
        dest = os.path.join(bdir, name)
        shutil.copy2(src, dest)
        # Rotation: nur die neuesten 15 Backups behalten.
        backups = sorted(
            (os.path.join(bdir, f) for f in os.listdir(bdir)
             if f.startswith("ledger-") and f.endswith(".db")),
            key=os.path.getmtime)
        for old in backups[:-15]:
            try:
                os.remove(old)
            except Exception:
                pass
        return dest
    except Exception:
        return None


_WAL_GESETZT = set()


def _conn():
    pfad = config.db_path()
    try:
        c = sqlite3.connect(pfad, timeout=30)
    except sqlite3.OperationalError:
        # DER ORDNER IST WEG ODER UMGEZOGEN (emm873): seit der
        # Drosselung in config.app_data_dir kann die gemerkte Antwort
        # bis zu PRUEF_INTERVALL_S alt sein. HIER faellt es auf - also
        # die Merkung wegwerfen und EINMAL richtig nachsehen;
        # app_data_dir zieht dabei den alten Ordner um oder legt ihn neu
        # an (die Zusage "lieber der alte Ordner als verlorene Daten").
        # Ein zweiter Fehlschlag gehoert dem Aufrufer.
        config.vergiss_datenordner()
        pfad = config.db_path()
        c = sqlite3.connect(pfad, timeout=30)
    c.row_factory = sqlite3.Row
    # WAL + a busy timeout let many threads read/write the same file safely
    # instead of crashing or raising "database is locked".
    # journal_mode=WAL steht IN DER DATEI und gilt danach fuer jede
    # Verbindung - einmal je Datei reicht (Ladezeit-Messung 27.09.2026:
    # 27'000 Verbindungen beim Start). busy_timeout und synchronous gelten
    # je Verbindung und bleiben.
    try:
        if pfad not in _WAL_GESETZT:
            c.execute("PRAGMA journal_mode=WAL")
            _WAL_GESETZT.add(pfad)
        c.execute("PRAGMA busy_timeout=30000")
        c.execute("PRAGMA synchronous=NORMAL")
    except Exception:
        pass
    return c


def init_db() -> None:
    with _conn() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS characters (
                character_id   INTEGER PRIMARY KEY,
                character_name TEXT NOT NULL,
                added_at       REAL,
                tx_synced_at   REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER,
                character_id   INTEGER,
                date           TEXT,
                type_id        INTEGER,
                quantity       INTEGER,
                unit_price     REAL,
                is_buy         INTEGER,
                location_id    INTEGER,
                PRIMARY KEY (transaction_id, character_id)
            );
            CREATE TABLE IF NOT EXISTS type_names (
                type_id   INTEGER PRIMARY KEY,
                name      TEXT
            );
            CREATE TABLE IF NOT EXISTS market_snapshot (
                type_id     INTEGER,
                source      TEXT DEFAULT '',
                sell_min    REAL,
                buy_max     REAL,
                sell_qty    INTEGER,
                buy_qty     INTEGER,
                sell_orders INTEGER,
                buy_orders  INTEGER,
                updated_at  REAL,
                PRIMARY KEY (type_id, source)
            );
            CREATE TABLE IF NOT EXISTS history (
                type_id     INTEGER,
                region      INTEGER DEFAULT 10000002,
                date        TEXT,
                average     REAL,
                highest     REAL,
                lowest      REAL,
                volume      INTEGER,
                order_count INTEGER,
                PRIMARY KEY (type_id, region, date)
            );
            CREATE TABLE IF NOT EXISTS history_meta (
                type_id    INTEGER,
                region     INTEGER DEFAULT 10000002,
                updated_at REAL,
                PRIMARY KEY (type_id, region)
            );
            CREATE TABLE IF NOT EXISTS history_tot (
                type_id INTEGER,
                region  INTEGER DEFAULT 10000002,
                seit    REAL,
                PRIMARY KEY (type_id, region)
            );
            CREATE TABLE IF NOT EXISTS scan_meta (
                k TEXT PRIMARY KEY,
                v TEXT
            );
            CREATE TABLE IF NOT EXISTS contract_prices (
                type_id      INTEGER,
                region       INTEGER,
                median_price REAL,
                mean_price   REAL,
                min_price    REAL,
                max_price    REAL,
                count        INTEGER,
                updated_at   REAL,
                PRIMARY KEY (type_id, region)
            );
            CREATE TABLE IF NOT EXISTS order_mod_counts (
                order_id     INTEGER PRIMARY KEY,
                type_id      INTEGER,
                is_buy       INTEGER,
                character_id INTEGER,
                mod_count    INTEGER DEFAULT 0,
                updated_at   REAL
            );
            CREATE TABLE IF NOT EXISTS order_intervall (
                order_id     INTEGER PRIMARY KEY,
                last_issued  TEXT,
                clock_ts     REAL,
                seen_at      REAL,
                klick_issued TEXT
            );
            """
        )
    _migrate_history_region()
    _migrate_order_mod_counts()
    _migrate_contract_prices_mean()
    _migrate_snapshot_source()
    _migrate_order_intervall_klick()


def _migrate_order_intervall_klick() -> None:
    """order_intervall aus einer frueheren Version kannte `klick_issued`
    noch nicht (emm883). Echte Nutzerdaten (laufende Uhren) - NICHT
    droppen, nur ergaenzen. Alte Zeilen bekommen NULL und gelten damit
    als bestaetigt; das ist das bisherige Verhalten und behauptet
    nichts, was wir nicht wissen."""
    with _conn() as c:
        cols = [r[1] for r in
                c.execute("PRAGMA table_info(order_intervall)").fetchall()]
        if cols and "klick_issued" not in cols:
            c.execute("ALTER TABLE order_intervall "
                      "ADD COLUMN klick_issued TEXT")


def _migrate_snapshot_source() -> None:
    """market_snapshot bekommt eine QUELLEN-Spalte (Nutzer-Befund Sitzung 9).

    Vorher lag GENAU EIN Snapshot in der Tabelle: jeder Scan machte
    'DELETE FROM market_snapshot' und schrieb seine Preise hinein - auch
    ein STRUKTUR-Scan. Das Portfolio rechnete danach seine Margen gegen
    die paar ueberteuerten Sell-Orders einer Spielerstruktur (gemeldet:
    +105% statt -4%). Jetzt haelt die Tabelle je Quelle EINEN Satz, PK
    ist (type_id, source): ein Struktur-Scan kann die Hub-Preise nicht
    mehr ueberschreiben.
    Die Altdaten werden der zuletzt gescannten Quelle zugeschlagen (die
    steht in scan_meta) - sie stammen ja genau von dort."""
    with _conn() as c:
        cols = [r["name"] for r in c.execute("PRAGMA table_info(market_snapshot)")]
        if not cols or "source" in cols:
            return
        row = c.execute("SELECT v FROM scan_meta WHERE k='source'").fetchone()
        if row and row["v"]:
            src = row["v"]
        else:
            reg = c.execute("SELECT v FROM scan_meta WHERE k='region'").fetchone()
            src = f"hub:{reg['v']}" if reg and reg["v"] else "hub:10000002"
        c.execute("ALTER TABLE market_snapshot RENAME TO market_snapshot_old")
        c.execute("""CREATE TABLE market_snapshot (
                type_id     INTEGER,
                source      TEXT DEFAULT '',
                sell_min    REAL,
                buy_max     REAL,
                sell_qty    INTEGER,
                buy_qty     INTEGER,
                sell_orders INTEGER,
                buy_orders  INTEGER,
                updated_at  REAL,
                sell_best_qty INTEGER DEFAULT 0,
                buy_best_qty  INTEGER DEFAULT 0,
                PRIMARY KEY (type_id, source)
            )""")
        _old = [r["name"] for r in
                c.execute("PRAGMA table_info(market_snapshot_old)")]
        _shared = [x for x in _old if x != "source"]
        c.execute(
            f"INSERT OR REPLACE INTO market_snapshot "
            f"(source,{','.join(_shared)}) "
            f"SELECT ?,{','.join(_shared)} FROM market_snapshot_old", (src,))
        c.execute("DROP TABLE market_snapshot_old")


def _migrate_order_mod_counts() -> None:
    """order_mod_counts aus einer früheren Version hatte noch keine
    last_price/last_vol_remain Spalten (für die Portfolio-Gebührenschätzung).
    Echte Nutzerdaten (Zählerstände) - NICHT droppen, nur ergänzen."""
    with _conn() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(order_mod_counts)").fetchall()]
        if cols and "last_price" not in cols:
            c.execute("ALTER TABLE order_mod_counts ADD COLUMN last_price REAL DEFAULT 0")
        if cols and "last_vol_remain" not in cols:
            c.execute(
                "ALTER TABLE order_mod_counts ADD COLUMN last_vol_remain INTEGER DEFAULT 0")
        # emm907/emm908: der zuletzt GESEHENE Preis (zum Erkennen einer
        # echten Aenderung) und die daraus wirklich angefallene
        # Gebuehrensumme. BEWUSST NEUE SPALTEN statt `last_price`
        # mitzubenutzen: dort steht der von MoMa VORGESCHLAGENE Preis aus
        # einem "Next"-Klick, nicht der, den die Order wirklich hatte.
        if cols and "preis_gesehen" not in cols:
            c.execute("ALTER TABLE order_mod_counts "
                      "ADD COLUMN preis_gesehen REAL")
        if cols and "vol_gesehen" not in cols:
            c.execute("ALTER TABLE order_mod_counts "
                      "ADD COLUMN vol_gesehen INTEGER")
        if cols and "gebuehr_summe" not in cols:
            c.execute("ALTER TABLE order_mod_counts "
                      "ADD COLUMN gebuehr_summe REAL DEFAULT 0")


def _migrate_contract_prices_mean() -> None:
    """contract_prices aus einer frueheren Version hatte keine mean_price-
    Spalte (Mittelwert neben dem Median, Nutzer-Wunsch Sitzung 7). Der alte
    Stand ist echter Nutzer-Scan - NICHT droppen, nur ergaenzen; die alten
    Zeilen behalten mean=NULL und fallen im UI auf den Median zurueck."""
    with _conn() as c:
        cols = [r[1] for r in c.execute(
            "PRAGMA table_info(contract_prices)").fetchall()]
        if cols and "mean_price" not in cols:
            c.execute("ALTER TABLE contract_prices ADD COLUMN mean_price REAL")


# ---- characters -------------------------------------------------------------
def upsert_character(cid: int, name: str) -> None:
    with _conn() as c:
        c.execute(
            "INSERT INTO characters(character_id,character_name,added_at) "
            "VALUES(?,?,?) ON CONFLICT(character_id) DO UPDATE SET character_name=?",
            (cid, name, time.time(), name),
        )


def list_characters() -> list:
    """Alle verknuepften Charaktere - ALPHABETISCH (emm954, Discord Robust
    18.11.2026: "for players with many characters, can all lists where you
    need to select a character be alphabetical"). EINE Stelle fuer jede
    Liste im Programm. Vorher stand hier die Reihenfolge des Verknuepfens;
    wer genau DEN zuerst verknuepften braucht (Vorgabe-Charakter), fragt
    `erst_verknuepfter_id()`."""
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM characters "
            "ORDER BY character_name COLLATE NOCASE, added_at")]


def erst_verknuepfter_id():
    """character_id des ZUERST verknuepften Charakters - oder None. Das war
    bis emm954 `list_characters()[0]`: der Vorgabe-Charakter, wenn oben
    "All characters" steht. Bei gleichem (oder fehlendem) Zeitpunkt gewinnt
    der erste der Liste."""
    chars = list_characters()
    if not chars:
        return None

    def _wann(c):
        try:
            return float(c.get("added_at") or 0)
        except (TypeError, ValueError):
            return 0.0
    return min(chars, key=_wann)["character_id"]


def remove_character(cid: int) -> None:
    # HISTORIE BEHALTEN (Nutzer, Sitzung 9: das Tool soll den Einstand auch
    # nach 2 Jahren noch kennen). Transaktionen sind das Langzeit-Gedaechtnis
    # fuer den Oe-Einkauf - ESI liefert nur ~30 Tage rueckwirkend, geloeschte
    # Historie ist also UNWIEDERBRINGLICH. Vorher loeschte das Entfernen
    # eines Charakters (z.B. wegen Token-Aerger, mit Neu-Verknuepfen danach)
    # die komplette Historie mit. Jetzt bleibt sie liegen: save_transactions
    # arbeitet mit INSERT OR IGNORE (transaction_id ist eindeutig), ein
    # neu verknuepfter Charakter erzeugt also KEINE Dubletten, und
    # get_transactions joint nicht gegen die Charakter-Tabelle - verwaiste
    # Zeilen bleiben lesbar.
    with _conn() as c:
        c.execute("DELETE FROM characters WHERE character_id=?", (cid,))


def set_tx_synced(cid: int) -> None:
    with _conn() as c:
        c.execute("UPDATE characters SET tx_synced_at=? WHERE character_id=?",
                  (time.time(), cid))


def tx_is_fresh(cid: int, max_minutes: float) -> bool:
    with _conn() as c:
        row = c.execute("SELECT tx_synced_at FROM characters WHERE character_id=?",
                        (cid,)).fetchone()
    if not row or not row["tx_synced_at"]:
        return False
    return (time.time() - row["tx_synced_at"]) < max_minutes * 60


# ---- transactions -----------------------------------------------------------
def save_transactions(cid: int, txs: list) -> None:
    with _conn() as c:
        c.executemany(
            "INSERT OR IGNORE INTO transactions "
            "(transaction_id,character_id,date,type_id,quantity,unit_price,"
            "is_buy,location_id) VALUES (?,?,?,?,?,?,?,?)",
            [(t["transaction_id"], cid, t["date"], t["type_id"], t["quantity"],
              t["unit_price"], 1 if t["is_buy"] else 0, t.get("location_id", 0))
             for t in txs],
        )


def get_transactions(cid=None, since=None, is_buy=None, name_like=None,
                     limit=None) -> list:
    """Filtered transaction rows, newest first. `since` = ISO date string,
    `is_buy` = True/False, `name_like` = item-name substring, `limit` caps the
    number of rows returned so the UI never has to render tens of thousands."""
    where = []
    params = []
    if cid not in (None, "all"):
        where.append("t.character_id=?"); params.append(cid)
    if since:
        where.append("t.date>=?"); params.append(since)
    if is_buy is not None:
        where.append("t.is_buy=?"); params.append(1 if is_buy else 0)
    join = ""
    if name_like:
        join = "LEFT JOIN type_names n ON n.type_id=t.type_id"
        where.append("n.name LIKE ?"); params.append(f"%{name_like}%")
    sql = "SELECT t.* FROM transactions t " + join
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY t.date DESC"
    if limit:
        sql += " LIMIT ?"; params.append(int(limit))
    with _conn() as c:
        return [dict(r) for r in c.execute(sql, params)]


def transaction_stats(cid=None, since=None, is_buy=None, name_like=None) -> dict:
    """Aggregate counts/sums in SQL (fast even for very large tables), so the
    summary never loads every row into memory."""
    where = []
    params = []
    if cid not in (None, "all"):
        where.append("t.character_id=?"); params.append(cid)
    if since:
        where.append("t.date>=?"); params.append(since)
    if is_buy is not None:
        where.append("t.is_buy=?"); params.append(1 if is_buy else 0)
    join = ""
    if name_like:
        join = "LEFT JOIN type_names n ON n.type_id=t.type_id"
        where.append("n.name LIKE ?"); params.append(f"%{name_like}%")
    wsql = (" WHERE " + " AND ".join(where)) if where else ""
    with _conn() as c:
        row = c.execute(
            "SELECT COUNT(*) n, "
            "COALESCE(SUM(CASE WHEN t.is_buy=1 THEN t.unit_price*t.quantity END),0) bought, "
            "COALESCE(SUM(CASE WHEN t.is_buy=0 THEN t.unit_price*t.quantity END),0) sold "
            "FROM transactions t " + join + wsql, params).fetchone()
    # "total" war früher eine zweite COUNT-Abfrage mit exakt denselben Filtern
    # und damit immer identisch zu n - der Schlüssel bleibt für die UI erhalten
    # (Vergleich gegen die Anzeige-Obergrenze), die Abfrage aber nicht.
    return {"n": row["n"], "bought": row["bought"], "sold": row["sold"],
            "total": row["n"]}


# ---- type names -------------------------------------------------------------
def name_to_type_id() -> dict:
    """{name_kleingeschrieben: type_id} aus dem Namens-Cache - für das
    Einfügen von Bestandslisten aus dem Spiel (Ingame-Kopie liefert nur
    Namen, keine IDs). Bewusst kleingeschrieben und getrimmt, damit
    Groß-/Kleinschreibung und Leerzeichen aus dem Clipboard egal sind."""
    with _conn() as c:
        rows = c.execute("SELECT type_id, name FROM type_names").fetchall()
    return {(r["name"] or "").strip().lower(): r["type_id"]
            for r in rows if r["name"]}


def all_names() -> dict:
    """{type_id: name} - der GANZE Namens-Cache (nach einem Market scan
    ~13k). Fuer die Vervollstaendigung im Preisverlauf; cached_names() mit
    13k Parametern liefe in die SQLite-Grenze fuer Platzhalter."""
    with _conn() as c:
        rows = c.execute("SELECT type_id, name FROM type_names").fetchall()
    return {r["type_id"]: r["name"] for r in rows if r["name"]}


def cached_names(type_ids) -> dict:
    if not type_ids:
        return {}
    with _conn() as c:
        q = "SELECT type_id,name FROM type_names WHERE type_id IN (%s)" % \
            ",".join("?" * len(type_ids))
        return {r["type_id"]: r["name"] for r in c.execute(q, list(type_ids))}


def save_names(mapping: dict) -> None:
    with _conn() as c:
        c.executemany("INSERT OR REPLACE INTO type_names(type_id,name) VALUES(?,?)",
                      list(mapping.items()))


# ---- structure resolution cache (emm553) -----------------------------------
# WOZU (Nutzer 15.10.2026, Fund in seiner eigenen fehler.log beim Start):
# esi.resolve_structure() hatte KEIN Caching, und wird von 10 Stellen in der
# Oberflaeche aufgerufen - bei JEDEM Start fragte das Werkzeug ALLE in
# gespeicherten Plaenen referenzierten Strukturen frisch ab, viele davon ohne
# Andockrecht (403). Jeder 403 zaehlt gegen das GEMEINSAME ESI-Fehlerbudget
# (CCP, ~100 je Fenster) und blockierte dadurch nachfolgende, wichtigere
# Abrufe (Orders/Assets/Blueprints/Industry-Jobs mehrerer Charaktere) fuer
# die Dauer der Sperre. Name/System einer Struktur aendern sich praktisch
# nie - Erfolge duerfen daher lange gecached werden. Ein verweigerter
# Zugriff dagegen KANN sich aendern (Standings, Rollen, neue Struktur) -
# deshalb fuer Fehlschlaege eine deutlich kuerzere Frist.
STRUCT_CACHE_OK_TAGE = 30
STRUCT_CACHE_FAIL_TAGE = 1


def init_structure_cache():
    # SELBSTSTAENDIG WIE init_volumes() (nicht Teil von init_db()'s
    # executescript): resolve_structure() in esi.py soll funktionieren,
    # auch wenn irgendein Aufrufpfad init_db() je ausliess - idempotent
    # und billig genug fuer "vor jedem Zugriff".
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS structure_cache (
                         structure_id    INTEGER PRIMARY KEY,
                         name            TEXT,
                         solar_system_id INTEGER,
                         type_id         INTEGER,
                         ok              INTEGER DEFAULT 1,
                         updated_at      REAL)""")


def cached_structure(structure_id: int):
    """Gecachtes resolve_structure()-Ergebnis, oder None (nie gecacht).
    {"name","solar_system_id","type_id","ok","updated_at"} - "ok"=0 heisst:
    ein frueherer Versuch ist gescheitert (kein Andockrecht o.ae.) und wird
    erinnert, damit ESI nicht bei jedem Start erneut gefragt wird. Die
    Frischepruefung (TTL) macht der Aufrufer (esi.py) - hier nur Lesen."""
    init_structure_cache()
    with _conn() as c:
        row = c.execute(
            "SELECT name, solar_system_id, type_id, ok, updated_at "
            "FROM structure_cache WHERE structure_id=?",
            (int(structure_id),)).fetchone()
    return dict(row) if row else None


def save_structure(structure_id: int, name=None, solar_system_id=None,
                    type_id=None, ok: bool = True) -> None:
    init_structure_cache()
    with _conn() as c:
        c.execute(
            "INSERT OR REPLACE INTO structure_cache"
            "(structure_id,name,solar_system_id,type_id,ok,updated_at) "
            "VALUES(?,?,?,?,?,?)",
            (int(structure_id), name, solar_system_id, type_id,
             1 if ok else 0, time.time()))


# ---- market snapshot (all Jita items) --------------------------------------
def hub_source(region: int = 10000002) -> str:
    """Quellen-Schluessel eines NPC-Hub-Scans."""
    return f"hub:{int(region)}"


def struct_source(structure_id: int) -> str:
    """Quellen-Schluessel eines Struktur-Scans."""
    return f"struct:{int(structure_id)}"


def get_scan_source(default: str = "") -> str:
    """Quelle des ZULETZT gefahrenen Scans (fuer Scanner-Ansichten)."""
    with _conn() as c:
        row = c.execute("SELECT v FROM scan_meta WHERE k='source'").fetchone()
    if row and row["v"]:
        return row["v"]
    return default or hub_source(get_scan_region())


def get_hub_source() -> str:
    """Quelle des zuletzt gefahrenen HUB-Scans - die Preisbasis fuers
    Portfolio. Ein Struktur-Scan aendert sie NICHT mehr (Nutzer-Befund
    Sitzung 9: Struktur-Preise hatten das ganze Portfolio verfaelscht)."""
    with _conn() as c:
        row = c.execute("SELECT v FROM scan_meta WHERE k='hub_source'").fetchone()
    if row and row["v"]:
        return row["v"]
    return hub_source(get_scan_region())


def save_snapshot(rows: list, region: int = 10000002, source: str = None,
                  hub_id: int = None) -> None:
    import time
    now = time.time()
    with _conn() as c:
        # Migration: Best-Order-Tiefe (Menge am jeweils besten Preis) - ein
        # Spread hinter nur 1 Stück ist keiner. Alte Snapshots lesen 0 =
        # "unbekannt"; der Filter greift dann bewusst nicht.
        for col in ("sell_best_qty", "buy_best_qty"):
            try:
                c.execute(f"ALTER TABLE market_snapshot ADD COLUMN {col} "
                          f"INTEGER DEFAULT 0")
            except Exception:
                pass    # Spalte existiert schon
        # NUR DIE EIGENE QUELLE ersetzen (Sitzung 9): frueher loeschte jeder
        # Scan die GANZE Tabelle - ein Struktur-Scan nahm damit dem
        # Portfolio seine Hub-Preise weg und ersetzte sie durch die
        # Fantasiepreise einer einzelnen Spielerstruktur.
        # `hub_id` (emm952): eine ZUSAETZLICHE NPC-Station legt ihre Preise
        # unter ihrer Stations-Nummer ab ("hub:<station>") - sonst loeschte
        # ihr Scan die Preise des festen Hubs derselben Region. Ohne hub_id
        # bleibt alles beim Schluessel der Region.
        src = source or hub_source(hub_id if hub_id else region)
        c.execute("DELETE FROM market_snapshot WHERE source=?", (src,))
        c.executemany(
            "INSERT OR REPLACE INTO market_snapshot "
            "(type_id,source,sell_min,buy_max,sell_qty,buy_qty,sell_orders,"
            "buy_orders,updated_at,sell_best_qty,buy_best_qty)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(r["type_id"], src, r["sell_min"], r["buy_max"], r["sell_qty"],
              r["buy_qty"], r["sell_orders"], r["buy_orders"], now,
              r.get("sell_best_qty", 0) or 0, r.get("buy_best_qty", 0) or 0)
             for r in rows],
        )
        # REGION UNBEKANNT WIRD ALS 0 FESTGEHALTEN, nicht als Jita
        # (emm838). Eine Struktur ohne bekannte Region darf nicht stumm
        # die Forge-Historie erben - dann stuenden in "Sold/day" Zahlen
        # aus einer Region, in der der Nutzer gar nicht handelt. Die 0
        # ist das Signal an die Anzeige, "kein Handelsvolumen" zu
        # schreiben statt einer erfundenen Zahl.
        c.execute("INSERT OR REPLACE INTO scan_meta(k,v) VALUES('region', ?)",
                  (str(int(region) if region else 0),))
        c.execute("INSERT OR REPLACE INTO scan_meta(k,v) VALUES('source', ?)",
                  (src,))
        # Die HUB-NUMMER des Scans (emm952) - bei allem ausser einer
        # zusaetzlichen Station dieselbe Zahl wie die Region.
        c.execute("INSERT OR REPLACE INTO scan_meta(k,v) VALUES('hub_id', ?)",
                  (str(int(hub_id) if hub_id else (int(region) if region else 0)),))
        if src.startswith("hub:"):
            c.execute("INSERT OR REPLACE INTO scan_meta(k,v) "
                      "VALUES('hub_source', ?)", (src,))


def get_snapshot(source: str = None) -> list:
    """Preise EINER Quelle. `source=None` = zuletzt gescannte Quelle
    (Scanner-Ansichten); das Portfolio fragt ausdruecklich nach
    get_hub_source(), damit ein Struktur-Scan es nicht verfaelscht."""
    src = source or get_scan_source()
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM market_snapshot WHERE source=?", (src,))]


def snapshot_age_seconds(source: str = None):
    import time
    with _conn() as c:
        row = c.execute("SELECT MAX(updated_at) AS u FROM market_snapshot "
                        "WHERE source=?",
                        (source or get_scan_source(),)).fetchone()
    if not row or not row["u"]:
        return None
    return time.time() - row["u"]


def snapshot_timestamp():
    """Roher (stabiler) Zeitstempel des letzten Markt-Scans - für Cache-Keys, wo
    ein sich jede Sekunde änderndes "Alter in Sekunden" ungeeignet wäre."""
    with _conn() as c:
        row = c.execute("SELECT MAX(updated_at) AS u FROM market_snapshot").fetchone()
    return row["u"] if row else None


# ---- Bestand: wann hat sich wirklich etwas geaendert? -----------------------
# NUTZER-WUNSCH (Sitzung 8): "ich will oben im Bauplan sehen, wann die letzte
# erfolgreiche ESI-Aktualisierung war, die Veraenderungen festgestellt hat".
# Der ESI-Header `Last-Modified` taugt dafuer NICHT: er wandert bei jedem
# Cache-Zyklus von CCP weiter, auch wenn sich am Bestand nichts geaendert hat.
# Deshalb vergleicht das Programm den Bestand selbst - ueber einen
# Fingerabdruck der Menge {type_id: qty}. Aendert der sich, ist das eine echte
# Veraenderung.

def asset_fingerprint(bestand) -> str:
    """Stabiler Fingerabdruck einer Bestandsmenge {type_id: menge}.
    Sortiert, damit die Reihenfolge des Abrufs egal ist - sonst haette jeder
    Abruf einen neuen Fingerabdruck und ALLES waere staendig 'geaendert'.
    Nullmengen fliegen raus: ein Item, das von 0 auf 0 geht, ist keine
    Aenderung, wuerde die Menge aber je nach Abruf mal enthalten sein."""
    import hashlib
    teile = ";".join(f"{int(t)}:{int(q)}"
                     for t, q in sorted((bestand or {}).items())
                     if int(q) != 0)
    return hashlib.sha256(teile.encode("utf-8")).hexdigest()


def note_asset_snapshot(bestand, vollstaendig=True, daten_ts=None) -> dict:
    """Einen erfolgreichen Bestands-Abruf vermerken. Gibt den Stand zurueck
    (dieselben Felder wie asset_snapshot_info()).

    `vollstaendig=False` (ein Charakter-Abruf ist fehlgeschlagen) schreibt
    NICHTS: aus einem unvollstaendigen Bestand wuerde sonst eine
    'Veraenderung' - genau die Sorte Falschmeldung, die die Anzeige wertlos
    macht. Lieber ein aelterer, ehrlicher Zeitpunkt als ein frischer falscher.

    `daten_ts` (emm797, Audit 31.10.2026, M5): der Zeitpunkt, zu dem ESI
    die DATEN gesehen hat (Last-Modified), nicht die Wanduhr des Abrufs.
    ESI cached Assets bis ~1 h: ein Abruf um 12:05 kann Daten von 11:10
    liefern - `checked_at` auf 12:05 zu setzen liess die ESI-Verzugs-
    Sperre (`bestand_gesehen_bis` nimmt das MAXIMUM) Belege durch, deren
    Verbrauch der benutzte Bestand noch gar nicht zeigt: dieselben
    Einheiten zaehlten doppelt (freigegebener Anspruch UND alter Bestand).
    Ohne `daten_ts` (None, alte Aufrufer) gilt die Wanduhr wie bisher.
    """
    import time
    if not vollstaendig:
        return asset_snapshot_info()
    fp = asset_fingerprint(bestand)
    jetzt = time.time()
    try:
        _stempel = min(jetzt, float(daten_ts)) if daten_ts else jetzt
    except (TypeError, ValueError):
        _stempel = jetzt
    with _conn() as c:
        row = c.execute(
            "SELECT v FROM scan_meta WHERE k='assets_fingerprint'").fetchone()
        alt = row["v"] if row else None
        c.execute("INSERT OR REPLACE INTO scan_meta(k,v) "
                  "VALUES('assets_checked_at', ?)", (str(_stempel),))
        if alt != fp:
            c.execute("INSERT OR REPLACE INTO scan_meta(k,v) "
                      "VALUES('assets_fingerprint', ?)", (fp,))
            # Beim ALLERERSTEN Abruf gibt es keinen Vorgaenger - dann ist das
            # keine festgestellte Veraenderung, sondern nur der Anfang der
            # Aufzeichnung. Trotzdem als Zeitpunkt merken, aber gekennzeichnet.
            c.execute("INSERT OR REPLACE INTO scan_meta(k,v) "
                      "VALUES('assets_changed_at', ?)", (str(jetzt),))
            if alt is None:
                c.execute("INSERT OR REPLACE INTO scan_meta(k,v) "
                          "VALUES('assets_first_seen', ?)", (str(jetzt),))
    return asset_snapshot_info()


def asset_snapshot_info() -> dict:
    """{'changed_at', 'checked_at', 'erstaufzeichnung'} - Zeitstempel als
    float oder None. `erstaufzeichnung=True` heisst: der Zeitpunkt ist der
    Beginn der Aufzeichnung, nicht eine beobachtete Aenderung. Wichtig, damit
    die Oberflaeche nicht 'zuletzt geaendert' behauptet, wo sie in Wahrheit
    nur 'seit hier wird geschaut' meint."""
    def _f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    try:
        with _conn() as c:
            werte = {r["k"]: r["v"] for r in c.execute(
                "SELECT k, v FROM scan_meta WHERE k IN "
                "('assets_changed_at','assets_checked_at','assets_first_seen')")}
    except sqlite3.OperationalError:
        # Tabelle noch nicht angelegt (init_db() lief nicht, frische
        # Installation, fremdes HOME): das ist kein Fehler, sondern schlicht
        # "noch nichts aufgezeichnet". Vorher flog hier eine Ausnahme bis in
        # den Bauplan-Kopf, und die Zeile zeigte "Stand unbekannt" statt der
        # ehrlichen Auskunft.
        werte = {}
    geaendert = _f(werte.get("assets_changed_at"))
    zuerst = _f(werte.get("assets_first_seen"))
    return {"changed_at": geaendert,
            "checked_at": _f(werte.get("assets_checked_at")),
            # EXAKTER Vergleich, KEINE Toleranz: beide Werte stammen aus
            # demselben str(time.time())-Schreibvorgang. Mit abs(...) < 0.001
            # galt eine echte Aenderung, die weniger als eine Millisekunde
            # nach der Erstaufzeichnung kam, faelschlich noch als
            # "Aufzeichnung beginnt hier" - und der Bauplan-Kopf verschwieg
            # sie. Fiel als flackernde Pruefung auf (Sitzung 8).
            "erstaufzeichnung": bool(geaendert is not None and zuerst is not None
                                     and geaendert == zuerst)}


# ---- Order-Update: wie oft wurde eine Order schon nachgebessert -------------
# (jede Nachbesserung kostet Broker-Gebühr, auch wenn günstiger dank Advanced
# Broker Relations - das summiert sich bei vielen Nachbesserungen. Wird NUR
# im Abarbeiten-Modus über "Nächste" hochgezählt, per order_id (bleibt bei
# "Order ändern" ingame gleich - nur bei Löschen+Neuanlegen ändert sie sich,
# was inhaltlich auch ein neuer Versuch ist, also folgerichtig bei 0 startet).
def bump_order_mod_count(order_id: int, type_id: int, is_buy: bool,
                         character_id: int, price: float = 0.0,
                         vol_remain: int = 0) -> int:
    """Zählt eine Nachbesserung. Gibt den neuen Zählerstand zurück. Merkt sich
    auch Preis/Restmenge zum Zeitpunkt der Nachbesserung - für die spätere
    Gebührenschätzung im Portfolio (auch nachdem die Order längst gefüllt und
    aus "Orders prüfen" verschwunden ist)."""
    import time
    with _conn() as c:
        c.execute(
            """INSERT INTO order_mod_counts (order_id, type_id, is_buy,
                   character_id, mod_count, updated_at, last_price,
                   last_vol_remain)
               VALUES (?, ?, ?, ?, 1, ?, ?, ?)
               ON CONFLICT(order_id) DO UPDATE SET
                   mod_count = mod_count + 1, updated_at = excluded.updated_at,
                   type_id = excluded.type_id, is_buy = excluded.is_buy,
                   character_id = excluded.character_id,
                   last_price = excluded.last_price,
                   last_vol_remain = excluded.last_vol_remain""",
            (order_id, type_id, int(bool(is_buy)), character_id, time.time(),
             float(price or 0), int(vol_remain or 0)))
        row = c.execute("SELECT mod_count FROM order_mod_counts WHERE order_id=?",
                        (order_id,)).fetchone()
    return row["mod_count"] if row else 1


def order_preise_abgleichen(orders, broker_pct_je_order=None,
                            adv_broker_level: int = 0,
                            broker_pct: float = 0.0) -> dict:
    """ZAEHLT EINE AENDERUNG, WENN SICH DER PREIS DIESER ORDER WIRKLICH
    GEAENDERT HAT - und rechnet dabei die echte Gebuehr dazu (emm907/908).

    Nutzer 13.11.2026: "counter nur hochstellen wenn sich der preis
    meiner order veraendert hat, das ist die pruefung ob ich modifiziert
    habe oder nicht. Es muss aber exakt diese order sein. nicht eine neue
    die gleich heisst oder so ein fehler."

    GENAU DAS LEISTET DIE order_id: EVE behaelt sie beim Aendern einer
    Order und vergibt fuer eine NEUE Order eine neue - zwei gleichnamige
    Orders koennen sich hier also nicht vermischen. Der Primaerschluessel
    der Tabelle ist die order_id, nichts anderes wird verglichen.

    VORHER zaehlte `bump_order_mod_count` schon beim "Next"-KLICK hoch -
    also auch dann, wenn der Nutzer die Order danach gar nicht aenderte.
    Jetzt zaehlt nur die TAT.

    `orders`: [(order_id, preis, vol_remain)] oder Dicts mit diesen
    Schluesseln. `broker_pct_je_order`: optional {order_id: Prozentsatz}
    (die Fee haengt am Charakter und am Hub); sonst gilt `broker_pct`.

    ERSTE BEGEGNUNG ZAEHLT NICHT. Eine Order, deren Preis MoMa noch nie
    gesehen hat (`preis_gesehen` ist NULL), wird nur aufgenommen. Sonst
    zaehlte der erste Aufbau nach dieser Aenderung bei jeder Order eine
    Aenderung, die nie stattfand - dieselbe Regel wie bei den neuen
    Lagerorten (emm905).

    -> {order_id: {"mod_count", "gebuehr"}}
    """
    import time
    from . import config as _cfg
    _liste = []
    for _o in (orders or []):
        if isinstance(_o, dict):
            _oid = _o.get("order_id")
            _pr = _o.get("price")
            _vol = _o.get("vol_remain")
        else:
            _oid, _pr, _vol = (list(_o) + [None, None, None])[:3]
        if not _oid:
            continue
        _liste.append((int(_oid), float(_pr or 0), int(_vol or 0)))
    if not _liste:
        return {}
    _jetzt = time.time()
    _raus = {}
    with _conn() as c:
        _qs = ",".join("?" * len(_liste))
        _vorher = {
            int(r["order_id"]): r for r in c.execute(
                f"SELECT order_id, mod_count, preis_gesehen, vol_gesehen, "
                f"gebuehr_summe FROM order_mod_counts "
                f"WHERE order_id IN ({_qs})",
                [o for o, _p, _v in _liste]).fetchall()}
        for _oid, _pr, _vol in _liste:
            _r = _vorher.get(_oid)
            if _r is None:
                # Noch nie gesehen: aufnehmen, NICHT zaehlen.
                c.execute(
                    "INSERT OR IGNORE INTO order_mod_counts "
                    "(order_id, mod_count, updated_at, preis_gesehen, "
                    " vol_gesehen, gebuehr_summe) VALUES (?,0,?,?,?,0)",
                    (_oid, _jetzt, _pr, _vol))
                _raus[_oid] = {"mod_count": 0, "gebuehr": 0.0}
                continue
            _alt = _r["preis_gesehen"]
            _mc = int(_r["mod_count"] or 0)
            _geb = float(_r["gebuehr_summe"] or 0)
            if _alt is None:
                # Zeile aus einer frueheren Fassung: Preis nachtragen,
                # NICHT zaehlen (sonst zaehlte die Umstellung selbst).
                c.execute(
                    "UPDATE order_mod_counts SET preis_gesehen=?, "
                    "vol_gesehen=?, updated_at=? WHERE order_id=?",
                    (_pr, _vol, _jetzt, _oid))
            elif abs(float(_alt) - _pr) > 0.005:
                # ECHTE AENDERUNG. ISK hat zwei Nachkommastellen, darum
                # eine halbe davon als Schwelle - Gleitkomma-Rauschen
                # darf keine Gebuehr erfinden.
                _bp = (broker_pct_je_order or {}).get(_oid, broker_pct)
                _vol_alt = int(_r["vol_gesehen"] or _vol or 0)
                _geb += _cfg.relist_gebuehr(
                    float(_alt) * _vol_alt, _pr * _vol, _bp, adv_broker_level)
                _mc += 1
                c.execute(
                    "UPDATE order_mod_counts SET mod_count=?, "
                    "gebuehr_summe=?, preis_gesehen=?, vol_gesehen=?, "
                    "updated_at=? WHERE order_id=?",
                    (_mc, _geb, _pr, _vol, _jetzt, _oid))
            else:
                # Gleicher Preis: nur die Restmenge nachfuehren (sie
                # schrumpft beim Fuellen), nichts zaehlen.
                c.execute(
                    "UPDATE order_mod_counts SET vol_gesehen=? "
                    "WHERE order_id=?", (_vol, _oid))
            _raus[_oid] = {"mod_count": _mc, "gebuehr": _geb}
    return _raus


def get_order_mod_counts(order_ids: list) -> dict:
    """{order_id: mod_count} für die angegebenen Orders (fehlende = 0, nicht
    im Dict enthalten - Aufrufer soll .get(id, 0) nutzen)."""
    if not order_ids:
        return {}
    with _conn() as c:
        qs = ",".join("?" * len(order_ids))
        rows = c.execute(
            f"SELECT order_id, mod_count FROM order_mod_counts "
            f"WHERE order_id IN ({qs})", order_ids).fetchall()
    return {r["order_id"]: r["mod_count"] for r in rows}


# ORDER-UPDATE-INTERVALL (emm735, Nutzer 27.10.2026, Discord-Wunsch von
# "Spaceballs 2"): "Next" soll Orders ueberspringen, die vor kurzem erst
# angefasst wurden. Die UHR JE ORDER startet von selbst - beim ersten "Next"
# auf diese Order ODER wenn sich ihr ESI-Zeitstempel `issued` aendert (=
# im Spiel nachgebessert; `issued` springt bei jeder Aenderung). Sie endet,
# wenn die Order nicht mehr existiert (die Zeile wird dann spaeter geloescht;
# eine neue Order hat eine neue order_id und damit eine frische, leere Uhr).
# Eine Order, die die App zum ERSTEN Mal sieht, hat KEINE Uhr (clock_ts None):
# `issued` ist bei ihr nur das Erstelldatum, nicht "zuletzt angefasst" - sie
# gilt als faellig, bis "Next" oder eine Aenderung im Spiel die Uhr startet.
# Im Zweifel also faellig, nie faelschlich ueberspringen.
_INTERVALL_VERGESSEN_S = 120 * 86400     # laenger gesehene-nicht: Zeile weg


def _iso_ts(s):
    """ESI-Zeitstempel ("2026-10-27T10:05:00Z") -> Epoche, None wenn unlesbar."""
    import datetime as _dt
    try:
        return _dt.datetime.fromisoformat(
            str(s).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def order_intervall_sync(issued_by_oid: dict, now: float = None,
                         stand_ts=None, mit_status: bool = False):
    """Gleicht die gesehenen Orders mit den gemerkten ab und gibt
    {order_id: clock_ts oder None} zurueck. Eine geaenderte `issued` (im Spiel
    nachgebessert) startet die Uhr beim Zeitpunkt der Aenderung neu.

    DER VERKLICKER (emm883, Nutzerfrage 09.11.2026: "falls ich in 2 Days
    Anzeige ausloese und ESI trackt, dass ich doch nicht geupdatet habe
    ingame, sondern mich nur verklickt habe in MoMa"): "Next" startet
    die Uhr SOFORT, ohne dass im Spiel etwas geschehen ist - MoMa kennt
    nur den Klick, nicht die Tat. `order_intervall_start` merkt sich
    deshalb in `klick_issued`, welches `issued` beim Klick galt. Solange
    das gesetzt ist, ist die Uhr UNBESTAETIGT.

    `stand_ts` ist die `Last-Modified`-Zeit der Antwort (esi.orders_stand),
    also WANN ESI diese Daten erzeugt hat - eine Zahl fuer alle, oder ein
    {order_id: Zeit} je Charakter. Liegt sie NACH dem Klick und
    steht dort immer noch dasselbe `issued`, hat ESI die unveraenderte
    Order nach dem Klick gesehen: die Uhr faellt weg, die Zeile ist
    wieder faellig. OHNE `stand_ts` wird NICHTS zurueckgesetzt - ein
    Abruf aus dem Cache koennte aelter sein als der Klick, und die
    Cache-Dauer zu raten waere genau das, was Regel 2 verbietet. Dann
    bleibt die Uhr stehen und gilt weiter als unbestaetigt.

    `mit_status=True` liefert (clocks, unbestaetigt_set) statt nur
    clocks - die Oberflaeche zeigt die unbestaetigten anders an."""
    import time
    now = time.time() if now is None else float(now)
    if not issued_by_oid:
        return ({}, set()) if mit_status else {}
    out = {}
    unbestaetigt = set()
    _stand_je = stand_ts if isinstance(stand_ts, dict) else None

    def _stand_fuer(oid):
        _v = _stand_je.get(oid) if _stand_je is not None else stand_ts
        try:
            return None if _v is None else float(_v)
        except (TypeError, ValueError):
            return None
    with _conn() as c:
        have = {r["order_id"]: (r["last_issued"], r["clock_ts"],
                                r["klick_issued"])
                for r in c.execute(
                    "SELECT order_id, last_issued, clock_ts, klick_issued "
                    "FROM order_intervall").fetchall()}
        for oid, iss in issued_by_oid.items():
            if not oid:
                continue
            iss = str(iss) if iss else ""
            row = have.get(oid)
            if row is None:
                c.execute("INSERT OR REPLACE INTO order_intervall "
                          "(order_id, last_issued, clock_ts, seen_at, "
                          "klick_issued) VALUES (?, ?, NULL, ?, NULL)",
                          (oid, iss, now))
                out[oid] = None
                continue
            last_iss, clock, klick_iss = row
            if iss and iss != (last_iss or ""):
                clock = _iso_ts(iss) or now          # im Spiel angefasst
                klick_iss = None                     # bestaetigt (emm883)
            elif klick_iss and iss and iss == klick_iss and clock:
                # Unbestaetigte Uhr: zeigt ein Abruf, den ESI NACH dem
                # Klick erzeugt hat, immer noch dasselbe `issued`, war es
                # ein Verklicker.
                _st = _stand_fuer(oid)
                if _st is not None and _st > float(clock):
                    clock = None
                    klick_iss = None
            # Ein fehlendes issued ueberschreibt das gemerkte NICHT - sonst
            # zaehlte die Rueckkehr des Felds als "im Spiel geaendert".
            c.execute("UPDATE order_intervall SET last_issued=?, clock_ts=?, "
                      "seen_at=?, klick_issued=? WHERE order_id=?",
                      (iss or (last_iss or ""), clock, now, klick_iss, oid))
            out[oid] = clock
            if klick_iss and clock:
                unbestaetigt.add(oid)
        c.execute("DELETE FROM order_intervall WHERE seen_at < ?",
                  (now - _INTERVALL_VERGESSEN_S,))
    return (out, unbestaetigt) if mit_status else out


def order_intervall_start(order_id: int, issued: str = "",
                          now: float = None) -> None:
    """Startet die Uhr dieser Order jetzt ("Next" wurde benutzt). Eine spaeter
    geaenderte `issued` (im Spiel nachgebessert) setzt sie auf den genauen
    Zeitpunkt der Aenderung.

    DIESE UHR IST UNBESTAETIGT (emm883): gedrueckt wurde ein Knopf in
    MoMa, geaendert werden muss die Order im SPIEL. `klick_issued` haelt
    fest, welches `issued` dabei galt - bleibt es so, war es ein
    Verklicker (siehe `order_intervall_sync`)."""
    import time
    now = time.time() if now is None else float(now)
    if not order_id:
        return
    with _conn() as c:
        c.execute(
            """INSERT INTO order_intervall (order_id, last_issued, clock_ts,
                   seen_at, klick_issued) VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(order_id) DO UPDATE SET clock_ts = excluded.clock_ts,
                   seen_at = excluded.seen_at,
                   klick_issued = excluded.klick_issued""",
            (order_id, str(issued or ""), now, now, str(issued or "")))


def get_buy_mod_fee_raw_by_type() -> dict:
    """{type_id: SUM(mod_count * last_price * last_vol_remain)} NUR für
    Buy-Order-Nachbesserungen (das ist, was den Kaufpreis erhöht - Sell-Order-
    Nachbesserungen sind ein Kostenpunkt beim Verkauf, nicht beim Einstand).
    Noch OHNE den Broker-Satz multipliziert (der kann sich zwischen jetzt und
    dem Zeitpunkt der einzelnen Nachbesserungen geändert haben, z.B. neuer
    Skill - wird vom Aufrufer mit dem AKTUELLEN Satz draufgerechnet, als
    Näherung für alle historischen Nachbesserungen einheitlich)."""
    with _conn() as c:
        rows = c.execute(
            """SELECT type_id, SUM(mod_count * last_price * last_vol_remain) AS raw
               FROM order_mod_counts WHERE is_buy = 1 AND mod_count > 0
               GROUP BY type_id""").fetchall()
    return {r["type_id"]: (r["raw"] or 0.0) for r in rows}


# ---- contract-price cache (Capital-Schiffe: kein Marktpreis, nur Contracts) -
# Pseudo-Region fuer "ganz New Eden" (Nutzer-Wunsch: Durchschnitts-Contract-
# Preis ueber alle Regionen). 0 ist keine echte Regions-ID, kollidiert also
# nie mit einem regionalen Stand - beide koennen nebeneinander liegen.
ALL_REGIONS = 0


def save_contract_prices(rows: list, region: int) -> None:
    """rows: [{type_id, median, min, max, count}]. Ersetzt den alten Stand NUR
    für diese Region (andere Regionen bleiben unberührt, falls man mehrere
    scannt)."""
    import time
    now = time.time()
    with _conn() as c:
        try:
            # Migration (Sitzung 8): wie viele Preise stammen aus Bundles
            # (Beilagen abgezogen). Alte Installationen bekommen die Spalte
            # beim ersten Speichern; alte Zeilen zaehlen als 0.
            c.execute("ALTER TABLE contract_prices "
                      "ADD COLUMN from_bundles INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass   # Spalte existiert schon
        c.execute("DELETE FROM contract_prices WHERE region=?", (region,))
        c.executemany(
            "INSERT OR REPLACE INTO contract_prices"
            "(type_id,region,median_price,mean_price,min_price,max_price,"
            "count,updated_at,from_bundles) VALUES (?,?,?,?,?,?,?,?,?)",
            [(r["type_id"], region, r["median"], r.get("mean"), r["min"],
              r["max"], r["count"], now, int(r.get("from_bundles") or 0))
             for r in rows],
        )


def get_contract_prices(region: int) -> dict:
    """{type_id: {median, min, max, count, updated_at}} für eine Region."""
    with _conn() as c:
        try:
            rows = c.execute(
                "SELECT type_id, median_price, mean_price, min_price, "
                "max_price, count, updated_at, from_bundles "
                "FROM contract_prices WHERE region=?", (region,)).fetchall()
        except sqlite3.OperationalError:
            # Alte DB ohne die Spalte (noch nie neu gespeichert): ohne sie
            # lesen, from_bundles unten als 0 behandeln.
            rows = c.execute(
                "SELECT type_id, median_price, mean_price, min_price, "
                "max_price, count, updated_at, 0 AS from_bundles "
                "FROM contract_prices WHERE region=?", (region,)).fetchall()
    return {r["type_id"]: {"median": r["median_price"],
                           # mean: erst ab dem New-Eden-Scan gefuellt; bei
                           # alten Staenden None -> Aufrufer faellt auf den
                           # Median zurueck, statt 0 zu behaupten.
                           "mean": r["mean_price"],
                           "min": r["min_price"],
                           "max": r["max_price"], "count": r["count"],
                           "from_bundles": int(r["from_bundles"] or 0),
                           "updated_at": r["updated_at"]} for r in rows}


def contract_prices_age_seconds(region: int):
    import time
    with _conn() as c:
        row = c.execute("SELECT MAX(updated_at) AS u FROM contract_prices WHERE region=?",
                        (region,)).fetchone()
    if not row or not row["u"]:
        return None
    return time.time() - row["u"]


# ---- price history cache ----------------------------------------------------
def _migrate_history_region() -> None:
    """Older databases have history/history_meta keyed by type_id only. Add the
    region dimension. History is just a cache, so we drop and rebuild it."""
    with _conn() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(history)").fetchall()]
        if cols and "region" not in cols:
            c.executescript(
                """
                DROP TABLE IF EXISTS history;
                DROP TABLE IF EXISTS history_meta;
                CREATE TABLE history (
                    type_id INTEGER, region INTEGER DEFAULT 10000002, date TEXT,
                    average REAL, highest REAL, lowest REAL, volume INTEGER,
                    order_count INTEGER, PRIMARY KEY (type_id, region, date)
                );
                CREATE TABLE history_meta (
                    type_id INTEGER, region INTEGER DEFAULT 10000002,
                    updated_at REAL, PRIMARY KEY (type_id, region)
                );
                """
            )


def set_scan_label(label: str) -> None:
    """Merkt, VON WELCHEM HUB (NPC oder Struktur, menschenlesbar) der aktuelle
    Snapshot stammt. Ohne das musste die UI raten und beschriftete die
    Portfolio-Preisspalte hart mit "Jita Sell" - auch wenn längst ein
    Nullsec-Keepstar gescannt war (Nutzer-Fall 4-HWWF)."""
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO scan_meta(k, v) VALUES('hub_label', ?)",
                  (label or "",))


def get_scan_label(default: str = "Jita") -> str:
    with _conn() as c:
        row = c.execute("SELECT v FROM scan_meta WHERE k='hub_label'").fetchone()
    return (row["v"] if row and row["v"] else default)


def get_scan_hub(default: int = 10000002) -> int:
    """HUB-NUMMER des letzten Scans (emm952): Region - oder, bei einer
    zusaetzlichen NPC-Station, deren Stations-Nummer. Datenbanken von vor
    emm952 kennen den Eintrag nicht; dann gilt die Region wie bisher."""
    with _conn() as c:
        row = c.execute("SELECT v FROM scan_meta WHERE k='hub_id'").fetchone()
    if row is None or row["v"] is None or row["v"] == "":
        return get_scan_region(default)
    try:
        return int(row["v"])
    except (TypeError, ValueError):
        return get_scan_region(default)


def get_scan_region(default: int = 10000002) -> int:
    """Region des letzten Scans - oder 0, wenn sie UNBEKANNT ist.

    DIE 0 IST EIN ECHTER WERT, kein Fehler (emm838): ein Struktur-Scan
    ohne bekannte Region schreibt sie absichtlich, damit die Anzeige
    "kein Handelsvolumen" sagen kann. Wer hier ungeprueft weiterrechnet,
    holt Historien fuer Region 0 - die es nicht gibt - und bekommt leere
    Listen; das ist gewollt und besser als Jita-Zahlen an einem
    Nullsec-Hub.
    """
    with _conn() as c:
        row = c.execute("SELECT v FROM scan_meta WHERE k='region'").fetchone()
    if row is None or row["v"] is None or row["v"] == "":
        return default
    return int(row["v"])


def save_history(type_id: int, entries: list, region: int = 10000002) -> None:
    import time
    with _conn() as c:
        c.executemany(
            "INSERT OR REPLACE INTO history "
            "(type_id,region,date,average,highest,lowest,volume,order_count) "
            "VALUES (?,?,?,?,?,?,?,?)",
            [(type_id, region, e["date"], e.get("average"), e.get("highest"),
              e.get("lowest"), e.get("volume"), e.get("order_count")) for e in entries],
        )
        c.execute("INSERT OR REPLACE INTO history_meta(type_id,region,updated_at) "
                  "VALUES(?,?,?)", (type_id, region, time.time()))


def get_history(type_id: int, region: int = 10000002) -> list:
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT date,average,highest,lowest,volume,order_count "
            "FROM history WHERE type_id=? AND region=? ORDER BY date",
            (type_id, region))]


def get_histories(type_ids, region: int = 10000002) -> dict:
    """Wie get_history, aber fuer VIELE Items in wenigen Abfragen (emm336,
    offen seit der Ladezeit-Messung emm237: 1729 Einzelabfragen im Scan, je
    eine neue Verbindung). {type_id: [Zeilen nach Datum]} - Items ohne Zeilen
    stehen mit [] darin, genau wie get_history sie liefern wuerde."""
    ids = sorted({int(t) for t in (type_ids or ())})
    out = {t: [] for t in ids}
    if not ids:
        return out
    with _conn() as c:
        for i in range(0, len(ids), 500):          # SQLite-Grenze fuer ?-Platzhalter
            teil = ids[i:i + 500]
            for r in c.execute(
                    "SELECT type_id,date,average,highest,lowest,volume,order_count "
                    "FROM history WHERE region=? AND type_id IN (%s) "
                    "ORDER BY type_id,date" % ",".join("?" * len(teil)),
                    [region] + teil):
                d = dict(r)
                out[d.pop("type_id")].append(d)
    return out


def markt_statistik(tage: int = 90) -> list:
    """RANKING DER REGIONEN aus der gespeicherten Preishistorie (emm894).

    Nutzer 10.11.2026: "ich habe jetzt viele verschiedene Tradehubs schon
    in denen ich einen Marktscann ausfuehren kann. koennen wir eine
    'Marktstatistik' ... die zeigt von allen Hubs: Volumen, verschiedene
    gehandelte Items, wieviel ISK gefossen ist? ... Es geht darum ich
    brauche ein ranking, von den Regionen wo ich handeln willl."

    KEIN EINZIGER ESI-ABRUF: die `history`-Tabelle traegt je Item, Region
    und Tag schon `volume`, `average` und `order_count`. Alles Gefragte
    ergibt sich durch Summieren.

    WAS DIE ZAHLEN EHRLICH SIND - und was nicht: die Historie liegt nur
    fuer Items vor, die MoMa schon einmal abgerufen hat (Scan, Portfolio,
    Bauplan). Das ist NICHT der gesamte Handel einer Region, sondern der
    Teil, den MoMa kennt. Darum kommt `items` mit zurueck: zwei Regionen
    sind nur vergleichbar, wenn aehnlich viele Items dahinterstehen. Die
    Oberflaeche muss das dazusagen, sonst liest sich eine schlecht
    gescannte Region als toter Markt.

    Rueckgabe je Region, nach ISK absteigend:
      {"region", "items", "volumen", "isk", "orders", "tage"}
    `volume > 0` haelt Tage OHNE Handel draussen - sie wuerden `tage`
    aufblaehen und einen Markt lebendiger aussehen lassen, als er ist.
    """
    import datetime as _dt
    ab = (_dt.date.today() - _dt.timedelta(days=max(1, int(tage)))).isoformat()
    with _conn() as c:
        rows = c.execute(
            "SELECT region, "
            "       COUNT(DISTINCT type_id) AS items, "
            "       SUM(volume)             AS volumen, "
            "       SUM(volume * average)   AS isk, "
            "       SUM(order_count)        AS orders, "
            "       COUNT(DISTINCT date)    AS tage "
            "FROM history WHERE date >= ? AND volume > 0 "
            "GROUP BY region", (ab,)).fetchall()
    aus = [{"region": int(r["region"]), "items": int(r["items"] or 0),
            "volumen": int(r["volumen"] or 0), "isk": float(r["isk"] or 0.0),
            "orders": int(r["orders"] or 0), "tage": int(r["tage"] or 0)}
           for r in rows]
    aus.sort(key=lambda x: x["isk"], reverse=True)
    return aus


def ort_top_gehandelt(source: str, region: int, tage: int = 90,
                      limit: int = 15) -> list:
    """DIE TOP-HANDELSWARE EINES ORTES (emm922, neu gewichtet emm923).

    Nutzer 14.11.2026: "mich interessiert hier einzig und alleine die Sell
    orders wieviel kaufen die Leute es muss eine sinnvolle Liste sein die
    einen kompromiss macht zwischen ISK Flow und Handelsvolumen."

    GEMESSEN (emm922 in seiner DB, Jita): nach ISK allein standen
    Leviathan Blueprint (0,1 Abschluesse/Tag) und zwei Fortizars (0/Tag)
    oben - teuer, aber kaum gehandelt. Nach Stueck allein gewinnen
    Minerale mit Millionen Stueck und duennen Margen.

    KOMPROMISS: Rangfolge = ISK-Umsatz x Zahl der Abschluesse (beides aus
    der Historie der Region, `tage` Tage). Das ist dieselbe Reihenfolge
    wie das geometrische Mittel der beiden, also beides gleich gewichtet:
    ein Item muss VIEL ISK bewegen UND OFT gehandelt werden. Nur Items mit
    Sell-Orders an diesem Ort (sell_qty > 0).

    GRENZE (ehrlich): die ESI-Historie trennt nicht, ob ein Abschluss eine
    Sell- oder eine Buy-Order bediente. Es gibt keine Quelle, die nur die
    Kaeufe aus Sell-Orders zaehlt.

    Rueckgabe [{type_id, menge, gehandelt, isk, abschluesse, sell_min}],
    Rang absteigend; `sell_min` = guenstigste Sell-Order an DIESEM Ort
    (Verkaufspreis der Gewinn-Spalte, emm924).
    """
    import datetime as _dt
    ab = (_dt.date.today() - _dt.timedelta(days=max(1, int(tage)))).isoformat()
    with _conn() as c:
        rows = c.execute(
            "SELECT s.type_id AS type_id, COALESCE(s.sell_qty,0) AS menge, "
            "       COALESCE(s.sell_min,0) AS sell_min, "
            "       h.vol AS gehandelt, h.isk AS isk, h.abs AS abschluesse "
            "FROM market_snapshot s JOIN ("
            "    SELECT type_id, SUM(volume) AS vol, "
            "           SUM(volume * average) AS isk, "
            "           SUM(order_count) AS abs FROM history "
            "    WHERE region = ? AND date >= ? AND volume > 0 "
            "    GROUP BY type_id) h ON h.type_id = s.type_id "
            "WHERE s.source = ? AND COALESCE(s.sell_qty,0) > 0 "
            "ORDER BY h.isk * h.abs DESC LIMIT ?",
            (int(region), ab, str(source), max(1, int(limit)))).fetchall()
    return [{"type_id": int(r["type_id"]), "menge": int(r["menge"]),
             "gehandelt": int(r["gehandelt"] or 0),
             "isk": float(r["isk"] or 0.0),
             "abschluesse": int(r["abschluesse"] or 0),
             "sell_min": float(r["sell_min"] or 0.0)} for r in rows]


def item_handel(region: int, tids, tage: int = 90) -> dict:
    """{type_id: {"vol": Stueck, "abs": Abschluesse}} der Region ueber
    `tage` Tage (emm930, Doctrines: "Abschluesse/Tag + Stueck/Tag").
    Dieselbe Quelle wie Market Stats (`history`), nur fuer die genannten
    Items. Items ohne Historie fehlen im Ergebnis."""
    import datetime as _dt
    ids = sorted({int(x) for x in (tids or [])})
    if not ids:
        return {}
    ab = (_dt.date.today() - _dt.timedelta(days=max(1, int(tage)))).isoformat()
    out = {}
    with _conn() as c:
        for i in range(0, len(ids), 500):
            teil = ids[i:i + 500]
            for r in c.execute(
                    "SELECT type_id, SUM(volume) AS vol, "
                    "       SUM(order_count) AS abs FROM history "
                    "WHERE region = ? AND date >= ? AND volume > 0 "
                    f"AND type_id IN ({','.join('?' * len(teil))}) "
                    "GROUP BY type_id", [int(region), ab] + teil):
                out[int(r["type_id"])] = {"vol": int(r["vol"] or 0),
                                          "abs": int(r["abs"] or 0)}
    return out


def region_top_items(region: int, tage: int = 90, limit: int = 15) -> list:
    """DIE ITEMS MIT DEM MEISTEN ISK-UMSATZ EINER REGION (emm921).

    Nutzer 14.11.2026: "ich muss wissen welche Items am meisten ISK
    abwerfen koennen, wenn ich diese dort handel" - "Also Handelsvolumen,
    isk flow". Die Liste "biggest positions in the order book" sagte nur,
    was im Buch LIEGT; hier steht, was wirklich GEHANDELT wurde.

    Dieselbe Quelle wie `markt_statistik` (die `history`-Tabelle, kein
    ESI-Abruf), nur je Item statt je Region: Summe Stueck und Summe
    Stueck x Tagesdurchschnitt ueber die letzten `tage` Tage. Es gilt
    dieselbe Einschraenkung: nur Items, deren Historie MoMa kennt.

    Rueckgabe [{type_id, volumen, isk, tage}], ISK absteigend; `tage` =
    Tage mit Handel.
    """
    import datetime as _dt
    ab = (_dt.date.today() - _dt.timedelta(days=max(1, int(tage)))).isoformat()
    with _conn() as c:
        rows = c.execute(
            "SELECT type_id, SUM(volume) AS volumen, "
            "       SUM(volume * average) AS isk, "
            "       COUNT(DISTINCT date) AS tage "
            "FROM history WHERE region = ? AND date >= ? AND volume > 0 "
            "GROUP BY type_id ORDER BY isk DESC LIMIT ?",
            (int(region), ab, max(1, int(limit)))).fetchall()
    return [{"type_id": int(r["type_id"]), "volumen": int(r["volumen"] or 0),
             "isk": float(r["isk"] or 0.0), "tage": int(r["tage"] or 0)}
            for r in rows]


def snapshot_statistik() -> list:
    """WAS IN JEDEM GESCANNTEN ORT GERADE IM BUCH STEHT (emm894).

    Fuer eine SPIELERSTRUKTUR gibt es keine Historie - `/markets/{region}/
    history/` kennt nur Regionen. Ueber eine Keepstar laesst sich darum
    kein gehandeltes Volumen sagen, nur was ihr Orderbuch beim letzten
    Scan hergab. Genau das steht hier, GETRENNT von den Regionszahlen,
    damit niemand das eine fuer das andere haelt.

    Rueckgabe je Quelle (`hub:<region>` / `struct:<id>`), nach Buchwert
    absteigend: {"source", "items", "sell_wert", "buy_wert", "orders",
    "alter"}.
    """
    with _conn() as c:
        rows = c.execute(
            "SELECT source, "
            "       COUNT(*)                        AS items, "
            "       SUM(COALESCE(sell_qty,0) * COALESCE(sell_min,0)) "
            "                                       AS sell_wert, "
            "       SUM(COALESCE(buy_qty,0) * COALESCE(buy_max,0)) "
            "                                       AS buy_wert, "
            "       SUM(COALESCE(sell_orders,0) + COALESCE(buy_orders,0)) "
            "                                       AS orders, "
            "       MAX(updated_at)                 AS stand "
            "FROM market_snapshot GROUP BY source").fetchall()
    jetzt = time.time()
    aus = [{"source": str(r["source"] or ""), "items": int(r["items"] or 0),
            "sell_wert": float(r["sell_wert"] or 0.0),
            "buy_wert": float(r["buy_wert"] or 0.0),
            "orders": int(r["orders"] or 0),
            "alter": (jetzt - float(r["stand"])) if r["stand"] else None}
           for r in rows]
    aus.sort(key=lambda x: x["sell_wert"] + x["buy_wert"], reverse=True)
    return aus


def ort_top_items(source: str, nach: str = "wert", limit: int = 15) -> list:
    """DIE GROESSTEN POSTEN IM ORDERBUCH EINES ORTES (emm896).

    Nutzer 11.11.2026: "die strukturen haben dann nochmal ein dropdown
    wo man die Highest volume und ISK Value Items der Struktren sieht".

    WAS DIESE ZAHLEN SIND - und der Name muss es sagen: das ist, was
    dort im BUCH LIEGT, nicht was gehandelt wurde. Fuer eine
    Spielerstruktur fuehrt ESI keine Handelshistorie, es gibt also gar
    keine andere Zahl. "Menge" ist die Stueckzahl aller Verkaufs-Orders,
    "Wert" dieselbe Menge mal dem guenstigsten Preis.

    `nach`: "wert" (Menge x Preis) oder "menge" (reine Stueckzahl).
    Rueckgabe [{type_id, menge, preis, wert}], groesste zuerst.
    """
    _sp = ("COALESCE(sell_qty,0) * COALESCE(sell_min,0)"
           if nach != "menge" else "COALESCE(sell_qty,0)")
    with _conn() as c:
        rows = c.execute(
            "SELECT type_id, COALESCE(sell_qty,0) AS menge, "
            "       COALESCE(sell_min,0) AS preis "
            "FROM market_snapshot "
            "WHERE source=? AND COALESCE(sell_qty,0) > 0 "
            f"ORDER BY {_sp} DESC LIMIT ?",
            (str(source), max(1, int(limit)))).fetchall()
    return [{"type_id": int(r["type_id"]), "menge": int(r["menge"]),
             "preis": float(r["preis"]),
             "wert": int(r["menge"]) * float(r["preis"])} for r in rows]


def fresh_history_type_ids(region: int = 10000002, max_age_h: float = 24) -> set:
    """Alle type_ids dieser Region, deren Preishistorie FRISCH im Cache liegt
    (Zeitstempel jünger als max_age_h UND tatsächlich Zeilen vorhanden).

    Zweck: der Scanner darf gecachte Kandidaten beliebig mitanalysieren - sie
    kosten keinen einzigen ESI-Abruf, nur einen DB-Lesevorgang. Dafür muss er
    VOR der Kandidatenauswahl wissen, welche das sind, und zwar in EINER
    Abfrage statt 13.000 Einzel-Checks (scanner.history_cached pro Item).

    Bewusst identisch zur "kein Abruf nötig"-Bedingung in
    scanner.history_cached: Zeilen vorhanden + Alter <= max_age_h. Der dortige
    Sonderfall "Zeitstempel, aber KEINE Zeilen" (fehlgeschlagener/leerer Abruf,
    Wiederholung nach 1 h) bleibt bewusst draußen - solche Items haben keine
    Historie zu analysieren und gehören ins Abruf-Budget, nicht in den
    Gratis-Topf."""
    cutoff = time.time() - max_age_h * 3600
    with _conn() as c:
        rows = c.execute(
            "SELECT m.type_id FROM history_meta m "
            "WHERE m.region=? AND m.updated_at IS NOT NULL AND m.updated_at>=? "
            "  AND EXISTS (SELECT 1 FROM history h "
            "              WHERE h.type_id=m.type_id AND h.region=m.region)",
            (region, cutoff)).fetchall()
    return {r["type_id"] for r in rows}


def history_age_seconds(type_id: int, region: int = 10000002):
    import time
    with _conn() as c:
        row = c.execute("SELECT updated_at FROM history_meta WHERE type_id=? AND region=?",
                        (type_id, region)).fetchone()
    if not row or not row["updated_at"]:
        return None
    return time.time() - row["updated_at"]


def touch_history(type_id: int, region: int = 10000002) -> None:
    """Record a *failed* history fetch so it isn't retried on every run. The
    timestamp is backdated so the item gets another chance in ~4 hours (with the
    usual 24h cache window), instead of hammering ESI every single scan."""
    import time
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO history_meta(type_id,region,updated_at) "
                  "VALUES(?,?,?)", (type_id, region, time.time() - 20 * 3600))


def mark_history_tot(type_id: int, region: int = 10000002) -> None:
    """ESI ANTWORTETE MIT 404: DIESE type_id GIBT ES NICHT MEHR (emm899).

    Anders als `touch_history` (vorruebergehender Fehlschlag, bald wieder
    versuchen) haelt das den Fall dauerhaft fest. Siehe `esi.UnknownType`
    fuer den Beleg aus `werkzeuge/pruefe_historie.py`.
    """
    import time
    with _conn() as c:
        c.execute("INSERT OR REPLACE INTO history_tot(type_id,region,seit) "
                  "VALUES(?,?,?)", (type_id, region, time.time()))


def history_ist_tot(type_id: int, region: int = 10000002) -> bool:
    """Steht diese type_id als 404 vermerkt? (emm899)"""
    with _conn() as c:
        row = c.execute("SELECT 1 FROM history_tot WHERE type_id=? AND region=?",
                        (type_id, region)).fetchone()
    return bool(row)


def history_tot_ids(region: int = 10000002) -> set:
    """ALLE 404-Vermerke in EINER Abfrage (emm899).

    Fuer Stellen, die viele Items auf einmal pruefen - `history_ist_tot`
    je Item waere derselbe Fehler, den emm336/emm878 schon einmal gekostet
    haben (eine neue Verbindung je Item).
    """
    with _conn() as c:
        return {int(r["type_id"]) for r in c.execute(
            "SELECT type_id FROM history_tot WHERE region=?", (region,))}


# ---- region-trading favourites ---------------------------------------------
def _tx_spalten_nachruesten() -> None:
    """`tx_backfill_done`: ist das Rueckwaertsblättern bis ans Ende der
    ESI-Retention EINMAL durchgelaufen? (Sitzung 17)"""
    with _conn() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(characters)").fetchall()]
        if cols and "tx_backfill_done" not in cols:
            c.execute("ALTER TABLE characters ADD COLUMN "
                      "tx_backfill_done INTEGER DEFAULT 0")


def oldest_transaction_id(character_id: int):
    """Kleinste gespeicherte transaction_id - Ansatzpunkt, um NOCH AELTERE
    Eintraege nachzuholen (Sitzung 17)."""
    with _conn() as c:
        row = c.execute("SELECT MIN(transaction_id) m FROM transactions "
                        "WHERE character_id=?", (character_id,)).fetchone()
    return row["m"] if row and row["m"] else None


def tx_backfill_done(character_id: int) -> bool:
    _tx_spalten_nachruesten()
    with _conn() as c:
        row = c.execute("SELECT tx_backfill_done d FROM characters "
                        "WHERE character_id=?", (character_id,)).fetchone()
    return bool(row and row["d"])


def set_tx_backfill_done(character_id: int) -> None:
    _tx_spalten_nachruesten()
    with _conn() as c:
        c.execute("UPDATE characters SET tx_backfill_done=1 WHERE character_id=?",
                  (character_id,))


def newest_transaction_id(character_id: int):
    """Höchste gespeicherte transaction_id dieses Charakters (oder None) -
    Stopp-Marke fürs Rückwärtsblättern beim ESI-Abruf (Lücke schließen,
    statt blind alle ~30 Tage Retention neu zu ziehen)."""
    with _conn() as c:
        row = c.execute("SELECT MAX(transaction_id) m FROM transactions "
                        "WHERE character_id=?", (character_id,)).fetchone()
    return row["m"] if row and row["m"] else None


def init_journal():
    """Gebühren-Einträge aus dem Wallet-Journal (brokers_fee/transaction_tax).
    Akkumuliert wie die Transaktionen: ESI liefert nur ~30 Tage zurück, die DB
    behält alles ab Einführung. PK (journal_id, character_id) dedupliziert."""
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS wallet_journal (
            journal_id INTEGER NOT NULL,
            character_id INTEGER NOT NULL,
            date TEXT,
            ref_type TEXT,
            amount REAL,
            PRIMARY KEY (journal_id, character_id))""")
        c.execute("""CREATE INDEX IF NOT EXISTS idx_journal_char_date
                     ON wallet_journal (character_id, date)""")


def save_journal(character_id: int, entries) -> None:
    init_journal()
    with _conn() as c:
        c.executemany(
            "INSERT OR IGNORE INTO wallet_journal VALUES (?,?,?,?,?)",
            [(e["journal_id"], character_id, e.get("date"), e.get("ref_type"),
              float(e.get("amount") or 0.0))
             for e in entries if e.get("journal_id")])


def doctrine_verlauf_umbenennen(alt, neu) -> None:
    """Der Deckungs-Verlauf zieht beim Umbenennen einer Doctrine mit
    (emm936) - sonst finge die Kurve unter dem neuen Namen bei null an."""
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS doctrine_verlauf (
            doctrine TEXT, hub TEXT, ts REAL, pct REAL,
            fits INTEGER, ziel INTEGER)""")
        c.execute("UPDATE doctrine_verlauf SET doctrine=? WHERE doctrine=?",
                  (str(neu), str(alt)))


def doctrine_verlauf_merken(eintraege) -> None:
    """Deckung je Doctrine bei einem "Fetch market" merken (emm933, Nutzer
    14.11.2026: Idee "Deckungs-Verlauf" - "ja"). `eintraege` =
    [(doctrine, hub, ts, pct, fits, ziel)]. Eigene Tabelle, NICHT
    settings.json (waechst mit jedem Abruf)."""
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS doctrine_verlauf (
            doctrine TEXT, hub TEXT, ts REAL, pct REAL,
            fits INTEGER, ziel INTEGER)""")
        c.executemany("INSERT INTO doctrine_verlauf VALUES (?,?,?,?,?,?)",
                      [(str(d), str(h), float(ts), float(p), int(f), int(z))
                       for d, h, ts, p, f, z in (eintraege or [])])


def doctrine_verlauf(doctrine: str, hub: str, limit: int = 60) -> list:
    """[(ts, pct)] einer Doctrine an einem Hub, ALT -> NEU, hoechstens die
    letzten `limit` Abrufe (emm933)."""
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS doctrine_verlauf (
            doctrine TEXT, hub TEXT, ts REAL, pct REAL,
            fits INTEGER, ziel INTEGER)""")
        rows = c.execute(
            "SELECT ts, pct FROM doctrine_verlauf WHERE doctrine=? AND hub=? "
            "ORDER BY ts DESC LIMIT ?",
            (str(doctrine), str(hub), max(1, int(limit)))).fetchall()
    return [(float(r[0]), float(r[1])) for r in reversed(rows)]


def init_order_history():
    """Eigene Market-Orders, offen UND geschlossen (Funfact, emm570).

    ESI liefert geschlossene Orders nur rund 90 Tage zurueck (UNGEPRUEFT);
    Eve MoMa sammelt sie deshalb ab 1.1.5 dauerhaft, wie die Transaktionen.
    PK order_id: derselbe Auftrag kommt erst offen und spaeter in der
    Historie - der juengere Stand gewinnt (INSERT OR REPLACE), auch der
    juengere Preis. `order_history_stand` merkt je Charakter den ERSTEN
    Abruf: davor kennt Eve MoMa die Orders nur ab 90 Tagen vor diesem Tag."""
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS order_history (
            order_id INTEGER PRIMARY KEY,
            character_id INTEGER NOT NULL,
            type_id INTEGER,
            location_id INTEGER,
            is_buy_order INTEGER,
            price REAL,
            issued TEXT,
            duration INTEGER,
            volume_total INTEGER,
            volume_remain INTEGER,
            state TEXT)""")
        c.execute("""CREATE INDEX IF NOT EXISTS idx_orderhist_char
                     ON order_history (character_id, type_id)""")
        c.execute("""CREATE TABLE IF NOT EXISTS order_history_stand (
            character_id INTEGER PRIMARY KEY,
            erster_abruf TEXT)""")
        # LETZTER ABRUF (emm825): fuer die Frage "liegt davon noch etwas im
        # Verkauf?" ist nicht nur die Menge wichtig, sondern WIE ALT sie
        # ist - eine 0 kann "alles verkauft" heissen oder "seit zwei Tagen
        # nicht nachgesehen". Alte Datenbanken bekommen die Spalte hier
        # nachtraeglich (Muster wie _migrate_order_mod_counts).
        _cols = [r[1] for r in
                 c.execute("PRAGMA table_info(order_history_stand)").fetchall()]
        if _cols and "letzter_abruf" not in _cols:
            c.execute("ALTER TABLE order_history_stand "
                      "ADD COLUMN letzter_abruf TEXT")
        # WANN WURDE DIESE ORDER ERLEDIGT (emm884)? Eigene Tabelle, nicht
        # eine Spalte in `order_history`: dort schreibt
        # `INSERT OR REPLACE` die ganze Zeile neu, und der Zeitstempel
        # waere bei jedem Abruf wieder weg.
        c.execute("""CREATE TABLE IF NOT EXISTS order_erledigt (
            order_id INTEGER PRIMARY KEY,
            ts       REAL)""")


# Wie lange ein erledigter Auftrag ueberhaupt aufgehoben wird - weit
# ueber jedem einstellbaren Nachleuchten, damit die Einstellung frei
# bleibt (emm884).
_ERLEDIGT_VERGESSEN_S = 120 * 86400


def _ts_aus_iso884(iso_text):
    """ISO-Zeitstempel -> Epochensekunde; ohne/unlesbar -> jetzt."""
    import time as _t884
    _v = _iso_ts(iso_text) if iso_text else None
    return float(_v) if _v else _t884.time()


def kuerzlich_erledigte_orders(max_alter_s, now: float = None,
                               character_ids=None) -> list:
    """Orders, die INNERHALB der letzten `max_alter_s` Sekunden von
    offen auf erledigt gewechselt sind (emm884).

    Community-Wunsch (Spaceballs 2, Discord 09.11.2026): "Could you
    maybe keep the item listed on that page on the bottom of the page
    with the status text BOUGHT for few days. And similar behavior in
    sell orders with status text SOLD. ... because I could keep on
    buying/selling the same item without having to check other lists."

    `art` sagt, WAS geschehen ist, und unterscheidet sauber:
      * "erfuellt" - die Order ist aus den offenen verschwunden, ohne in
        der ESI-Historie aufzutauchen. Das IST der Verkauf bzw. Kauf:
        ESI listet unter /orders/history/ nur abgelaufene und
        stornierte Auftraege (siehe `save_orders`).
      * "abgelaufen" / "storniert" - so hat ESI sie selbst gemeldet.
        AUSNAHME (emm927): "expired" mit volume_remain 0 ist ausverkauft,
        also ebenfalls "erfuellt" - so meldet ESI leer verkaufte Orders.
    Ein Pauschal-"SOLD" waere hier falsch und wuerde einen Verkauf
    behaupten, den es nie gab (Regel 1)."""
    import time as _t884
    now = _t884.time() if now is None else float(now)
    grenze = now - float(max_alter_s or 0)
    if max_alter_s is None or float(max_alter_s) <= 0:
        return []
    _wo, _par = "", [grenze]
    if character_ids:
        _cids = [int(x) for x in character_ids]
        _wo = f" AND h.character_id IN ({','.join('?' * len(_cids))})"
        _par += _cids
    init_order_history()
    _ART = {"weg": "erfuellt", "expired": "abgelaufen",
            "cancelled": "storniert"}
    out = []
    with _conn() as c:
        c.execute("DELETE FROM order_erledigt WHERE ts < ?",
                  (now - _ERLEDIGT_VERGESSEN_S,))
        for r in c.execute(
                "SELECT h.order_id, h.character_id, h.type_id, "
                "h.is_buy_order, h.price, h.volume_total, h.volume_remain, "
                "h.state, h.location_id, e.ts "
                "FROM order_erledigt e JOIN order_history h "
                "  ON h.order_id = e.order_id "
                "WHERE e.ts >= ?" + _wo + " ORDER BY e.ts DESC", _par):
            out.append({
                "order_id": r[0], "character_id": r[1], "type_id": r[2],
                "is_buy": bool(r[3]), "price": float(r[4] or 0.0),
                "volume_total": r[5], "volume_remain": r[6],
                "state": r[7], "location_id": r[8], "ts": float(r[9] or 0.0),
                # AUSVERKAUFT IST NICHT ABGELAUFEN (emm927, Nutzer
                # 14.11.2026: "ich habe keine abgelaufenen Orders mit diesem
                # Charakter"). ESI meldet eine leer verkaufte Order in der
                # Historie als state "expired" mit volume_remain 0 -
                # gemessen in seiner DB: alle "EXPIRED"-Zeilen Restmenge 0,
                # erst Tage alt bei 90 Tagen Laufzeit; die einzige echte
                # Ablaufung (90 Tage um) hatte Restmenge 1.
                "art": ("erfuellt" if str(r[7] or "") == "expired"
                        and r[6] is not None and int(r[6]) == 0
                        else _ART.get(str(r[7] or ""), "beendet")),
                "alter_s": max(0.0, now - float(r[9] or 0.0))})
    return out


def save_orders(character_id: int, orders, jetzt_iso: str = None,
                nur_offene: bool = False) -> int:
    """Orders eines Charakters speichern (offen oder Historie). Rueckgabe:
    Zahl der geschriebenen Zeilen. Der erste Aufruf je Charakter setzt
    `erster_abruf` (INSERT OR IGNORE - spaetere aendern ihn nie),
    `letzter_abruf` wird jedes Mal gesetzt.

    `nur_offene=True` (emm825) sagt: DIESE Liste ist der VOLLSTAENDIGE
    Bestand der offenen Orders dieses Charakters (aus
    esi.fetch_character_orders). Dann werden alle bisher als "open"
    gefuehrten Orders, die NICHT mehr dabei sind, auf "weg" gesetzt.

    WARUM DAS NOETIG IST: ESI listet unter `/orders/history/` nur
    abgelaufene und stornierte Auftraege. Eine VOLLSTAENDIG ERFUELLTE
    Order taucht dort nicht wieder auf - sie verschwindet einfach aus
    den offenen. Ohne dieses Aufraeumen bliebe sie fuer immer als
    "open" stehen, und die Spalte "noch im Verkauf" zeigte Ware an, die
    laengst verkauft ist. Genau die Frage des Nutzers ("did I sell
    everything or do I need still to attend to it?") waere damit falsch
    beantwortet - und zwar in die beruhigende Richtung."""
    import datetime as _dt
    init_order_history()
    rows = []
    for o in (orders or []):
        try:
            oid = int(o["order_id"])
        except (KeyError, TypeError, ValueError):
            continue
        rows.append((oid, int(character_id), o.get("type_id"),
                     o.get("location_id"),
                     1 if o.get("is_buy_order") else 0,
                     float(o.get("price") or 0.0), o.get("issued"),
                     int(o.get("duration") or 0),
                     o.get("volume_total"), o.get("volume_remain"),
                     o.get("state") or "open"))
    if jetzt_iso is None:
        jetzt_iso = _dt.datetime.utcnow().replace(microsecond=0).isoformat()
    with _conn() as c:
        # WAS KANNTEN WIR BISHER ALS OFFEN (emm884)? Nur der beobachtete
        # UEBERGANG offen -> nicht mehr offen bekommt einen Zeitstempel.
        # Wuerde stattdessen jede geschlossene Order beim ersten Abruf
        # einen bekommen, truege eine Monate alte Order das heutige
        # Datum - und die Liste behauptete, sie sei gerade erledigt
        # worden (Regel 1).
        _war_offen884 = {r[0] for r in c.execute(
            "SELECT order_id FROM order_history "
            "WHERE character_id=? AND state='open'", (int(character_id),))}
        if nur_offene:
            _ids = [r[0] for r in rows]
            _frage = ",".join("?" * len(_ids))
            c.execute(
                "UPDATE order_history SET state='weg' "
                "WHERE character_id=? AND state='open'"
                + (f" AND order_id NOT IN ({_frage})" if _ids else ""),
                [int(character_id)] + _ids)
        c.executemany(
            "INSERT OR REPLACE INTO order_history VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            rows)
        if _war_offen884:
            _jetzt884 = _ts_aus_iso884(jetzt_iso)
            _liste884 = list(_war_offen884)
            _fr884 = ",".join("?" * len(_liste884))
            # INSERT OR IGNORE: der ERSTE beobachtete Uebergang gilt -
            # ein spaeterer Abruf darf den Zeitstempel nicht vorruecken,
            # sonst wuerde die Zeile nie aus der Nachleuchten-Liste
            # herausaltern.
            c.execute(
                "INSERT OR IGNORE INTO order_erledigt (order_id, ts) "
                f"SELECT order_id, ? FROM order_history "
                f"WHERE state != 'open' AND order_id IN ({_fr884})",
                [_jetzt884] + _liste884)
        c.execute("INSERT OR IGNORE INTO order_history_stand "
                  "(character_id, erster_abruf) VALUES (?,?)",
                  (int(character_id), jetzt_iso))
        if nur_offene:
            # Nur der Abruf der OFFENEN sagt etwas ueber die Aktualitaet
            # des Bestands - die Historie kann alt sein, ohne dass das
            # etwas heisst.
            c.execute("UPDATE order_history_stand SET letzter_abruf=? "
                      "WHERE character_id=?", (jetzt_iso, int(character_id)))
    return len(rows)


def offene_order_mengen(cid=None) -> dict:
    """{type_id: {"sell": Stueck, "buy": Stueck}} der eigenen OFFENEN
    Orders (emm825, Nutzerwunsch aus Discord 04.11.2026: "maybe add next
    to column QTY another column that shows how many items I am still
    selling").

    ENTHALTEN IST JEDES ITEM, ZU DEM JE EINE ORDER BEKANNT WAR - mit 0,
    wenn aktuell nichts mehr offen ist. Dieser Unterschied ist der Kern
    der Frage ("did I sell everything, or do I need still to attend to
    it?"): eine 0 heisst "du hattest hier Orders, jetzt ist alles weg" -
    die gute Nachricht. Ein FEHLENDER Eintrag heisst dagegen "zu diesem
    Item ist gar keine Order bekannt" - dazu darf die Oberflaeche nichts
    behaupten und laesst die Zelle leer. Wuerde hier nur `state='open'`
    gefiltert, fielen beide Faelle zusammen und das erfolgreiche
    Ausverkaufen saehe aus wie Unwissen.

    Gezaehlt wird nur, was offen IST; was `save_orders(..., nur_offene=
    True)` als verschwunden erkannt hat, steht auf 'weg'."""
    init_order_history()
    sql = ("SELECT type_id,"
           " SUM(CASE WHEN state='open' AND is_buy_order=0"
           "          THEN volume_remain ELSE 0 END) AS verkauf,"
           " SUM(CASE WHEN state='open' AND is_buy_order=1"
           "          THEN volume_remain ELSE 0 END) AS kauf"
           " FROM order_history")
    params = []
    if cid not in (None, "all"):
        sql += " WHERE character_id=?"
        params.append(cid)
    sql += " GROUP BY type_id"
    out = {}
    with _conn() as c:
        for r in c.execute(sql, params):
            if r["type_id"] is None:
                continue
            out[int(r["type_id"])] = {"sell": int(r["verkauf"] or 0),
                                      "buy": int(r["kauf"] or 0)}
    return out


def orders_letzter_abruf(cid=None):
    """Juengster Abruf der OFFENEN Orders als ISO-Text - oder None.

    Bei "alle Charaktere" zaehlt der AELTESTE der Charaktere: solange
    einer veraltet ist, ist die Gesamtsicht so alt wie er (Regel 3 -
    lieber zu vorsichtig als faelschlich frisch)."""
    init_order_history()
    sql = "SELECT letzter_abruf FROM order_history_stand"
    params = []
    if cid not in (None, "all"):
        sql += " WHERE character_id=?"
        params.append(cid)
    with _conn() as c:
        werte = [r["letzter_abruf"] for r in c.execute(sql, params)
                 if r["letzter_abruf"]]
    return min(werte) if werte else None


def auslaufende_orders(cid=None, tage=7, jetzt=None) -> list:
    """Offene eigene Orders, deren Laufzeit in hoechstens `tage` Tagen
    endet (emm937, Nutzer 14.11.2026: "Items ... die drohen auszulaufen").
    Ablauf = `issued` + `duration` Tage - beides liefert ESI je Order
    (`issued` springt beim Aendern der Order neu). Die am fruehesten
    endende zuerst. Ohne lesbares Datum oder ohne Laufzeit wird die Order
    NICHT gezeigt (keine erfundene Restzeit, Regel 1).
    `rest_s` kann negativ sein: laut gespeichertem Stand schon vorbei."""
    import datetime as _dt
    init_order_history()
    now = time.time() if jetzt is None else float(jetzt)
    sql = ("SELECT order_id, character_id, type_id, location_id, "
           "is_buy_order, price, issued, duration, volume_total, "
           "volume_remain FROM order_history WHERE state='open'")
    params = []
    if cid not in (None, "all"):
        sql += " AND character_id=?"
        params.append(int(cid))
    out = []
    with _conn() as c:
        rows = list(c.execute(sql, params))
    for r in rows:
        try:
            _d = _dt.datetime.fromisoformat(str(r[6]).replace("Z", "+00:00"))
            if _d.tzinfo is None:
                _d = _d.replace(tzinfo=_dt.timezone.utc)
            _dauer = int(r[7] or 0)
        except (TypeError, ValueError):
            continue
        if _dauer <= 0 or not r[2]:
            continue
        ablauf = _d.timestamp() + _dauer * 86400.0
        rest = ablauf - now
        if rest > float(tage) * 86400.0:
            continue
        out.append({"order_id": int(r[0]), "character_id": int(r[1]),
                    "type_id": int(r[2]), "location_id": r[3],
                    "is_buy": bool(r[4]), "price": float(r[5] or 0.0),
                    "volume_total": r[8], "volume_remain": r[9],
                    "ablauf_ts": ablauf, "rest_s": rest})
    out.sort(key=lambda x: (x["rest_s"], x["order_id"]))
    return out


def get_orders(cid=None) -> list:
    """Gespeicherte Orders als dicts (Schluessel wie ESI, plus character_id)."""
    init_order_history()
    sql, params = "SELECT * FROM order_history", []
    if cid not in (None, "all"):
        sql += " WHERE character_id=?"; params.append(cid)
    with _conn() as c:
        out = []
        for r in c.execute(sql, params):
            d = dict(r)
            d["is_buy_order"] = bool(d.get("is_buy_order"))
            out.append(d)
        return out


def order_abdeckung(tage: int = 90) -> dict:
    """{character_id: ISO-Datum}, ab dem die Orders vollstaendig bekannt
    sind = erster Abruf minus `tage`. Ein Kauf davor ist "unbekannt"."""
    import datetime as _dt
    init_order_history()
    out = {}
    with _conn() as c:
        for r in c.execute("SELECT character_id, erster_abruf FROM order_history_stand"):
            try:
                ab = _dt.datetime.fromisoformat(str(r["erster_abruf"]))
            except (TypeError, ValueError):
                continue
            out[int(r["character_id"])] = (ab - _dt.timedelta(days=tage)).isoformat()
    return out


def journal_fee_sums(character_id=None, since: str = "") -> dict:
    """Echte Gebühren-Summen aus dem Journal (als POSITIVE Beträge) plus das
    früheste erfasste Datum (für den Hinweis "seit Aufzeichnung")."""
    init_journal()
    w, params = [], []
    if character_id not in (None, "all"):
        w.append("character_id=?"); params.append(character_id)
    if since:
        w.append("date>=?"); params.append(since)
    wsql = (" WHERE " + " AND ".join(w)) if w else ""
    out = {"brokers_fee": 0.0, "transaction_tax": 0.0, "earliest": None}
    with _conn() as c:
        for r in c.execute("SELECT ref_type, SUM(amount) s FROM wallet_journal"
                           + wsql + " GROUP BY ref_type", params):
            if r["ref_type"] in out:
                out[r["ref_type"]] = abs(r["s"] or 0.0)
        row = c.execute("SELECT MIN(date) d FROM wallet_journal" + wsql,
                        params).fetchone()
        out["earliest"] = (row["d"] or "")[:10] if row and row["d"] else None
    return out


# ---------------------------------------------------------------------------
# JOB -> BAUPLAN (Stufe B, 21.09.2026)
#
# WOZU: ESI sagt NICHT, zu welchem Bauplan ein Industry-Job gehoert - das
# Feld gibt es in der Antwort schlicht nicht. Bis hierher wurde die Zuordnung
# bei JEDEM Bestands-Abruf neu erraten (Item + Aktivitaet + Zeitpunkt), und
# zwar fuer jeden Plan getrennt. Nachgestellt (aa382): EIN Job ueber 2'250
# Runs wurde zwei Plaenen gleichzeitig angerechnet, obwohl der zweite nur
# 400 Runs brauchte - und beider Einkaufsliste fiel auf leer.
#
# DIE ZUORDNUNG WIRD DESHALB GEMERKT, nicht jedes Mal neu geraten. Einmal
# entschieden, bleibt ein Job bei seinem Plan; die Runs anderer Plaene
# bewegen sich nicht mehr mit.
#
# WAS HIER STEHT UND WAS NICHT (Abgrenzung aus der Skizze, Punkt 2.4):
# gespeichert wird NUR die ZUORDNUNG (Job -> Plan). Die TATSACHE, dass
# gebaut wurde, bleibt die Aussage von ESI - ein Job, den das Spiel
# abbricht, verschwindet dort und darf hier nicht als gebaut weiterleben.
# Diese Tabelle ist also ein Adressbuch, kein Fortschrittsspeicher.
#
# WARUM IN industry.db UND NICHT IN settings.json: `config.save_settings`
# schreibt die Einstellungen bei JEDEM Speichern komplett neu (json.dumps
# der ganzen Struktur, inklusive aller Bauplan-Schnappschuesse). Eine
# wachsende Liste dort wuerde jedes Speichern verlangsamen und die Datei
# aufblaehen. Dasselbe Muster wie `favorites` und `wallet_journal`.
# "eindeutig" kam mit Stufe C dazu (24.09.2026): kein anderer gespeicherter
# Plan beansprucht das Item, also kann der Job nur von hier stammen. Die
# Liste ist eine SPERRE - eine Quelle, die hier fehlt, laesst
# `job_zuordnung_setzen` mit ValueError scheitern, und der Aufrufer faengt
# das ab. Ergebnis waere: die Zuordnung passiert nie, und niemand sieht es
# ausser fehler.log. Wer eine neue Quelle einfuehrt, traegt sie HIER ein.
JOB_QUELLEN = ("klick", "signatur", "reservierung", "nutzer", "eindeutig",
               # "prioritaet" (28.09.2026): strittiger Job, nach der
               # Kartenreihenfolge verteilt - GESPEICHERT, damit Umsortieren
               # ihn nicht rueckwirkend verschiebt; der Nutzer kann ihn im
               # Frage-Dialog bestaetigen oder umhaengen (-> "nutzer").
               "prioritaet")

# "Zu keinem meiner Plaene" (Stufe C, Teil 2): auch das ist eine ANTWORT und
# muss gemerkt werden, sonst fragt das Werkzeug bei jedem Aufbau erneut. Als
# Plan-Id gespeichert heisst das: der Job gilt als vergeben (keine Automatik
# fasst ihn mehr an), gehoert aber keinem Plan - `job_zuordnung_fuer_plan`
# einer echten Plan-Id liefert ihn nie. Ein Minus kann keine echte Plan-Id
# sein (die sind Zahlen als Text).
PLAN_KEINER = "-"


def init_job_zuordnung():
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS job_zuordnung (
                   job_id    INTEGER PRIMARY KEY,
                   plan_id   TEXT,
                   type_id   INTEGER,
                   runs      INTEGER,
                   quelle    TEXT,
                   ts        REAL)""")


def job_zuordnung_setzen(job_id, plan_id, type_id, runs, quelle, ts=None):
    """Einen Job einem Plan zuordnen. Eine bestehende Zuordnung bleibt.

    BEWUSST `INSERT OR IGNORE` STATT `REPLACE`: die erste Entscheidung
    gewinnt. Genau das ist der Zweck der Tabelle - wuerde jeder Abruf die
    Zuordnung ueberschreiben duerfen, waere sie wieder so wackelig wie die
    Raterei vorher. Eine falsche Zuordnung korrigiert der NUTZER
    (`quelle="nutzer"`, s. `job_zuordnung_umhaengen`), nicht die Automatik.
    """
    if job_id is None or plan_id is None:
        return False
    if quelle not in JOB_QUELLEN:
        raise ValueError("unknown origin: %r" % (quelle,))
    init_job_zuordnung()
    import time as _t
    with _conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO job_zuordnung "
            "(job_id, plan_id, type_id, runs, quelle, ts) VALUES (?,?,?,?,?,?)",
            (int(job_id), str(plan_id), int(type_id or 0), int(runs or 0),
             str(quelle), float(ts if ts is not None else _t.time())))
        return cur.rowcount > 0


def job_zuordnung_umhaengen(job_id, plan_id):
    """Zuordnung eines Jobs ERSETZEN - nur fuer eine Nutzer-Korrektur."""
    if job_id is None:
        return False
    init_job_zuordnung()
    import time as _t
    with _conn() as c:
        cur = c.execute(
            "UPDATE job_zuordnung SET plan_id=?, quelle='nutzer', ts=? "
            "WHERE job_id=?",
            (str(plan_id), float(_t.time()), int(job_id)))
        return cur.rowcount > 0


def job_zuordnung_fuer_plan(plan_id) -> dict:
    """{job_id: {plan_id, type_id, runs, quelle, ts}} dieses Plans."""
    if plan_id is None:
        return {}
    init_job_zuordnung()
    with _conn() as c:
        rows = c.execute(
            "SELECT job_id,plan_id,type_id,runs,quelle,ts FROM job_zuordnung "
            "WHERE plan_id=?", (str(plan_id),)).fetchall()
    return {int(r["job_id"]): {"plan_id": r["plan_id"], "type_id": r["type_id"],
                               "runs": r["runs"], "quelle": r["quelle"],
                               "ts": r["ts"]} for r in rows}


def job_zuordnung_alle() -> dict:
    """{job_id: plan_id} - fuer die Frage \"ist dieser Job schon vergeben?\"."""
    init_job_zuordnung()
    with _conn() as c:
        rows = c.execute("SELECT job_id,plan_id FROM job_zuordnung").fetchall()
    return {int(r["job_id"]): r["plan_id"] for r in rows}


def job_zuordnung_details() -> dict:
    """{job_id: {plan_id, type_id, runs, quelle, ts}} ALLER Eintraege - fuer
    die Uebersicht "Job assignments" (emm427, Umhaengen bestaetigter Jobs)."""
    init_job_zuordnung()
    with _conn() as c:
        rows = c.execute(
            "SELECT job_id,plan_id,type_id,runs,quelle,ts FROM job_zuordnung"
        ).fetchall()
    return {int(r["job_id"]): {"plan_id": r["plan_id"], "type_id": r["type_id"],
                               "runs": r["runs"], "quelle": r["quelle"],
                               "ts": r["ts"]} for r in rows}


def job_zuordnung_mit_quelle(quelle) -> dict:
    """{job_id: {plan_id, type_id, runs, ts}} aller Jobs einer Quelle."""
    init_job_zuordnung()
    with _conn() as c:
        rows = c.execute(
            "SELECT job_id,plan_id,type_id,runs,ts FROM job_zuordnung "
            "WHERE quelle=?", (str(quelle),)).fetchall()
    return {int(r["job_id"]): {"plan_id": r["plan_id"], "type_id": r["type_id"],
                               "runs": r["runs"], "ts": r["ts"]} for r in rows}


def job_zuordnung_loeschen(plan_id) -> int:
    """Alle Zuordnungen eines Plans entfernen (Plan geloescht/zurueckgesetzt)."""
    if plan_id is None:
        return 0
    init_job_zuordnung()
    with _conn() as c:
        cur = c.execute("DELETE FROM job_zuordnung WHERE plan_id=?",
                        (str(plan_id),))
        return cur.rowcount


def init_run_klicks():
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS run_klicks (
                   id       INTEGER PRIMARY KEY AUTOINCREMENT,
                   plan_id  TEXT,
                   type_id  INTEGER,
                   runs     INTEGER,
                   reaktion INTEGER,
                   ts       REAL)""")


def run_klick_merken(plan_id, type_id, runs, reaktion, ts=None):
    """Einen Klick auf einen Run-Knopf festhalten.

    Der Klick ist KEIN Fortschritt und KEIN Beweis - er sagt nur "diese
    Zeile, dieser Plan, jetzt". Wirksam wird er erst, wenn ESI danach einen
    passenden Job meldet (s. `mw_helpers.job_zuordnen`). Ein Fehlklick
    bleibt deshalb folgenlos.

    Warum hier und nicht in den Einstellungen: dieselbe Begruendung wie bei
    `job_zuordnung` - `save_settings` schreibt die ganze Datei neu.
    """
    if plan_id is None or not type_id:
        return False
    init_run_klicks()
    import time as _t
    with _conn() as c:
        c.execute(
            "INSERT INTO run_klicks (plan_id,type_id,runs,reaktion,ts) "
            "VALUES (?,?,?,?,?)",
            (str(plan_id), int(type_id), int(runs or 0),
             1 if reaktion else 0, float(ts if ts is not None else _t.time())))
    return True


def run_klicks_fuer_plan(plan_id, aelter_als=None) -> list:
    """[{tid, runs, ts, reaktion}] - das Eingabeformat von `job_zuordnen`."""
    if plan_id is None:
        return []
    init_run_klicks()
    with _conn() as c:
        rows = c.execute(
            "SELECT type_id,runs,reaktion,ts FROM run_klicks WHERE plan_id=? "
            "ORDER BY ts", (str(plan_id),)).fetchall()
    aus = []
    for r in rows:
        if aelter_als is not None and float(r["ts"]) < float(aelter_als):
            continue
        aus.append({"tid": int(r["type_id"]), "runs": int(r["runs"] or 0),
                    "reaktion": bool(r["reaktion"]), "ts": float(r["ts"])})
    return aus


def run_klicks_andere(plan_id, aelter_als=None) -> list:
    """Klicks ALLER ANDEREN Plaene, gleiches Format wie
    `run_klicks_fuer_plan` - damit bei gleichem Item und gleicher Run-Zahl
    der LETZTE Klick vor dem Jobstart gewinnt (Nutzer 28.09.2026)."""
    init_run_klicks()
    with _conn() as c:
        rows = c.execute(
            "SELECT type_id,runs,reaktion,ts FROM run_klicks WHERE plan_id<>? "
            "ORDER BY ts", (str(plan_id),)).fetchall()
    aus = []
    for r in rows:
        if aelter_als is not None and float(r["ts"]) < float(aelter_als):
            continue
        aus.append({"tid": int(r["type_id"]), "runs": int(r["runs"] or 0),
                    "reaktion": bool(r["reaktion"]), "ts": float(r["ts"])})
    return aus


def run_klicks_loeschen(plan_id) -> int:
    """Alle gemerkten Klicks eines Plans entfernen (Plan geloescht, oder der
    Plan wird neu aufgesetzt - alte Klicks duerfen dann nichts mehr binden)."""
    if plan_id is None:
        return 0
    init_run_klicks()
    with _conn() as c:
        cur = c.execute("DELETE FROM run_klicks WHERE plan_id=?",
                        (str(plan_id),))
        return cur.rowcount


def run_klicks_aufraeumen(vor_ts) -> int:
    """Klicks entfernen, die aelter sind als `vor_ts` - sie koennen keinen
    Job mehr binden (s. KLICK_FENSTER_SEK). Haelt die Tabelle klein."""
    init_run_klicks()
    with _conn() as c:
        cur = c.execute("DELETE FROM run_klicks WHERE ts < ?", (float(vor_ts),))
        return cur.rowcount


def init_favorites():
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS favorites (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   kind TEXT, name TEXT,
                   region_id INTEGER, station_id INTEGER,
                   structure_id INTEGER, character_id INTEGER)""")


def _favorite_schluessel(fav) -> tuple:
    """Woran man einen Ort wiedererkennt: Art + Struktur- ODER Stations-ID."""
    return (fav.get("kind"), fav.get("structure_id") or 0, fav.get("station_id") or 0)


def _verlinkte_charaktere() -> set:
    try:
        return {int(c["character_id"]) for c in list_characters()}
    except Exception:
        return set()


def add_favorite(fav: dict) -> bool:
    """Ort merken. Gibt False zurueck, wenn derselbe Ort (Art + ID) schon
    drin ist - Nutzer 19.09.2026: "falls man aus Versehen einen Hub doppelt
    hinzugefuegt hat". Vorher stand er dann zweimal im Dropdown.

    DER CHARAKTER ZAEHLT MIT: bei einer Struktur ruft der gemerkte Charakter
    das Orderbuch ab (Docking-Zugang). Ist der alte Eintrag an einen NICHT
    mehr verlinkten Charakter gebunden und der neue an einen verlinkten,
    wird der Eintrag auf den neuen Charakter umgeschrieben statt abgelehnt."""
    init_favorites()
    _neu = _favorite_schluessel(fav)
    if _neu[1] or _neu[2]:
        _da = _verlinkte_charaktere()
        for _alt in list_favorites():
            if _favorite_schluessel(_alt) == _neu:
                _alt_cid = int(_alt.get("character_id") or 0)
                _neu_cid = int(fav.get("character_id") or 0)
                if _alt_cid not in _da and _neu_cid in _da and _neu_cid != _alt_cid:
                    with _conn() as c:
                        c.execute("UPDATE favorites SET character_id=?, name=? WHERE id=?",
                                  (_neu_cid, fav.get("name") or _alt.get("name"), _alt["id"]))
                return False
    with _conn() as c:
        c.execute(
            "INSERT INTO favorites(kind,name,region_id,station_id,structure_id,character_id)"
            " VALUES (?,?,?,?,?,?)",
            (fav["kind"], fav["name"], fav.get("region_id"), fav.get("station_id"),
             fav.get("structure_id"), fav.get("character_id")))
    return True


def remove_favorite(fav_id: int) -> None:
    """Gemerkten Ort (Struktur/Station) wieder aus der Liste nehmen."""
    init_favorites()
    with _conn() as c:
        c.execute("DELETE FROM favorites WHERE id=?", (int(fav_id),))


def dedupe_favorites() -> int:
    """Doppelte Orte aus frueheren Fassungen (ohne Doppel-Sperre) einmalig
    bereinigen. Es BLEIBT der Eintrag, dessen Charakter noch verlinkt ist
    (er ruft das Orderbuch ab) - bei mehreren der aelteste. Gibt die Zahl
    der entfernten Eintraege zurueck."""
    init_favorites()
    _da = _verlinkte_charaktere()
    gruppen = {}
    for f in sorted(list_favorites(), key=lambda r: r["id"]):
        k = _favorite_schluessel(f)
        if not (k[1] or k[2]):
            continue
        gruppen.setdefault(k, []).append(f)
    weg = []
    for k, eintraege in gruppen.items():
        if len(eintraege) < 2:
            continue
        behalten = next((e for e in eintraege
                         if int(e.get("character_id") or 0) in _da), eintraege[0])
        weg += [e["id"] for e in eintraege if e["id"] != behalten["id"]]
    for i in weg:
        remove_favorite(i)
    return len(weg)


def list_favorites() -> list:
    init_favorites()
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM favorites ORDER BY name")]


# ---- shopping list ----------------------------------------------------------
def init_shopping():
    """'done' ist eine Altlast: das Abhaken-Feature im Einkaufswagen wurde
    entfernt. Die Spalte bleibt nur für die Kompatibilität bestehender
    Datenbanken stehen und wird nicht mehr gelesen oder geschrieben."""
    with _conn() as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS shopping (
                   id INTEGER PRIMARY KEY AUTOINCREMENT,
                   type_id INTEGER, name TEXT, qty INTEGER,
                   buy_price REAL, sell_price REAL, done INTEGER DEFAULT 0,
                   source TEXT DEFAULT '')""")
        # migrate older DBs that predate the 'done' / 'source' columns
        cols = [r[1] for r in c.execute("PRAGMA table_info(shopping)").fetchall()]
        if "done" not in cols:
            c.execute("ALTER TABLE shopping ADD COLUMN done INTEGER DEFAULT 0")
        if "source" not in cols:
            c.execute("ALTER TABLE shopping ADD COLUMN source TEXT DEFAULT ''")
        if "sugg_qty" not in cols:
            c.execute("ALTER TABLE shopping ADD COLUMN sugg_qty INTEGER DEFAULT 0")
        # GEKAUFTES ABZIEHEN (emm980): `seit` = wann die Zeile angelegt wurde
        # (ISO, UTC - nur Kaeufe DANACH zaehlen), `tx_bis` = hoechste schon
        # abgezogene transaction_id (kein Kauf wird zweimal abgezogen).
        if "seit" not in cols:
            c.execute("ALTER TABLE shopping ADD COLUMN seit TEXT")
        if "tx_bis" not in cols:
            c.execute("ALTER TABLE shopping ADD COLUMN tx_bis INTEGER DEFAULT 0")
        # FAVORITEN-ITEMS (emm962). Eigene Tabelle `item_favoriten` - die
        # Tabelle `favorites` gehoert den HUBS (Strukturen), nicht verwechseln.
        c.execute(
            """CREATE TABLE IF NOT EXISTS item_favoriten (
                   type_id INTEGER PRIMARY KEY, name TEXT, ts REAL)""")


def fav_items() -> list:
    """Favoriten-Items [{type_id, name}], alphabetisch (emm962)."""
    try:
        with _conn() as c:
            rows = c.execute(
                "SELECT type_id, name FROM item_favoriten "
                "ORDER BY name COLLATE NOCASE, type_id").fetchall()
    except sqlite3.OperationalError:
        return []                  # Tabelle noch nicht angelegt
    return [{"type_id": int(r["type_id"]), "name": r["name"] or str(r["type_id"])}
            for r in rows]


def fav_item_dazu(type_id, name) -> bool:
    """Item in die Favoriten. False, wenn es schon drin stand (kein
    Doppel - type_id ist der Schluessel)."""
    init_shopping()
    with _conn() as c:
        cur = c.execute(
            "INSERT OR IGNORE INTO item_favoriten(type_id, name, ts) VALUES (?,?,?)",
            (int(type_id), item_name_rein(name) or str(name or type_id), time.time()))
        return cur.rowcount > 0


def fav_item_weg(type_id) -> bool:
    """Item aus den Favoriten nehmen. False, wenn es nicht drin stand."""
    try:
        with _conn() as c:
            cur = c.execute("DELETE FROM item_favoriten WHERE type_id=?",
                            (int(type_id),))
            return cur.rowcount > 0
    except sqlite3.OperationalError:
        return False


# ANZEIGE-MARKER, die nie in einen Item-Namen gehoeren (emm359, Nutzer:
# EVE-Multibuy meldete "Could not be interpreted: ⚠ Curator I 166" - der
# Swing-Tab schreibt "⚠ " vor verdaechtige Items, und genau dieser Zellentext
# landete als Name in der Einkaufsliste).
_NAME_MARKER = "\u2605\u26a0\u2197\u26a1\u2713\ufe0f\u25cf\u2022"


def item_name_rein(name) -> str:
    """Item-Name ohne vorangestellte Anzeige-Marker (★ ⚠ ↗ ⚡ ✓ ● •) und
    ohne Rand-Leerzeichen - so, wie EVE ihn im Multibuy versteht. Rein."""
    s = str(name or "").strip()
    while s and (s[0] in _NAME_MARKER or s[0].isspace()):
        s = s[1:]
    return s.strip()


def hangar_name(zeile) -> str:
    """Item-Name aus EINER Zeile einer Ingame-Hangar-Kopie (Strg+C).

    Erste Tab-Spalte, ohne das Sternchen am Ende (emm428, Discord: die
    Verkaufsliste bekam "'Arbalest' Rocket Launcher I*" und fand das Item
    nicht -> Preis "?"). WOHER das "*" kommt, ist NICHT geklaert: die
    Vermutung "unverpackt" war FALSCH (Discord-Nutzer: 25 frisch in Jita
    gekaufte, gestapelte Items). Sein Verkaufsfenster zeigte auch den
    STATIONSNAMEN mit "*" ("Caldari Navy Montagewerk*", deutscher Client,
    englische Item-Namen) - Verdacht: eine Anzeige-/Spracheinstellung des
    Clients. Im Item-Namen selbst kommt "*" nie vor. Der Bestands-Import im
    Bauplan streift es laengst ab.
    """
    s = str(zeile or "").split("\t")[0].strip()
    while s.endswith("*"):
        s = s[:-1].rstrip()
    return s


def add_shopping(type_id, name, qty, buy=0.0, sell=0.0, source="", sugg_qty=0):
    """Add qty of an item. If the item is already on the list, the quantity is
    accumulated into the existing row (multibuy-style merge). The 'source'
    (daytrade / swing / …) of an existing row is kept, not overwritten.
    'sugg_qty' is the daily-volume-based suggested quantity, stored so the
    shopping list can apply it later per button."""
    name = item_name_rein(name)
    init_shopping()
    with _conn() as c:
        row = c.execute("SELECT id, qty FROM shopping WHERE type_id=?",
                        (type_id,)).fetchone()
        if row:
            if sugg_qty:
                c.execute("UPDATE shopping SET qty=qty+?, sugg_qty=? WHERE id=?",
                          (qty, sugg_qty, row["id"]))
            else:
                c.execute("UPDATE shopping SET qty=qty+? WHERE id=?", (qty, row["id"]))
        else:
            c.execute("INSERT INTO shopping(type_id,name,qty,buy_price,sell_price,"
                      "source,sugg_qty,seit) VALUES (?,?,?,?,?,?,?,?)",
                      (type_id, name, qty, buy, sell, source, sugg_qty,
                       _utc_iso_jetzt()))


def _utc_iso_jetzt() -> str:
    """Jetzt als ISO-Zeit in UTC - dasselbe Format wie `transactions.date`
    (ESI: 2026-11-22T10:15:00Z), damit beide als Text vergleichbar sind."""
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def shopping_kaeufe_abziehen(jetzt_iso=None) -> list:
    """GEKAUFTES VON DER EINKAUFSLISTE ABZIEHEN (emm980, Nutzer 22.11.2026:
    "3. ja auch shopping list" - "pruefe dann bauen").

    Je Zeile: alle KAEUFE dieses Items aus dem Wallet (alle verknuepften
    Charaktere), die NACH dem Anlegen der Zeile liegen (`date >= seit`) und
    noch nicht abgezogen wurden (`transaction_id > tx_bis`). Die Menge sinkt
    um das Gekaufte; ist nichts mehr uebrig, verschwindet die Zeile.

    Eine Zeile ohne `seit` (aus der Zeit vor emm980) bekommt beim ersten
    Lauf `jetzt` - fuer sie zaehlen also nur Kaeufe ab jetzt, nie alte.

    Rueckgabe [{type_id, name, bought, rest, entfernt}] der veraenderten
    Zeilen. GRENZE (dem Nutzer gesagt): das Wallet sagt nicht, WOFUER
    gekauft wurde - ein Kauf desselben Items fuer etwas anderes zaehlt mit."""
    init_shopping()
    jetzt = jetzt_iso or _utc_iso_jetzt()
    out = []
    with _conn() as c:
        rows = c.execute(
            "SELECT id, type_id, name, qty, seit, tx_bis FROM shopping").fetchall()
        for r in rows:
            if not r["seit"]:
                c.execute("UPDATE shopping SET seit=? WHERE id=?",
                          (jetzt, r["id"]))
                continue
            s = c.execute(
                "SELECT COALESCE(SUM(quantity), 0) AS menge, "
                "       COALESCE(MAX(transaction_id), 0) AS bis "
                "FROM transactions WHERE type_id=? AND is_buy=1 "
                "AND date>=? AND transaction_id>?",
                (r["type_id"], r["seit"], int(r["tx_bis"] or 0))).fetchone()
            gekauft = int(s["menge"] or 0)
            if gekauft <= 0:
                continue
            rest = int(r["qty"] or 0) - gekauft
            if rest <= 0:
                c.execute("DELETE FROM shopping WHERE id=?", (r["id"],))
            else:
                c.execute("UPDATE shopping SET qty=?, tx_bis=? WHERE id=?",
                          (rest, int(s["bis"] or 0), r["id"]))
            out.append({"type_id": int(r["type_id"]), "name": r["name"],
                        "bought": gekauft, "rest": max(0, rest),
                        "entfernt": rest <= 0})
    return out


def list_shopping():
    init_shopping()
    with _conn() as c:
        return [dict(r) for r in c.execute("SELECT * FROM shopping ORDER BY id")]


def update_shopping(row_id, **fields):
    if not fields:
        return
    cols = ", ".join(f"{k}=?" for k in fields)
    with _conn() as c:
        c.execute(f"UPDATE shopping SET {cols} WHERE id=?",
                  (*fields.values(), row_id))


def remove_shopping(row_id):
    with _conn() as c:
        c.execute("DELETE FROM shopping WHERE id=?", (row_id,))


def clear_shopping():
    with _conn() as c:
        c.execute("DELETE FROM shopping")


def tx_age_seconds():
    import time
    with _conn() as c:
        row = c.execute("SELECT MAX(tx_synced_at) AS u FROM characters").fetchone()
    if not row or not row["u"]:
        return None
    return time.time() - row["u"]


# ---- ignored containers (kept, not traded) ---------------------------------
def init_container_ignore():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS container_ignore (
                         item_id INTEGER PRIMARY KEY)""")


def set_container_ignored(item_id, ignored: bool):
    init_container_ignore()
    with _conn() as c:
        if ignored:
            c.execute("INSERT OR IGNORE INTO container_ignore(item_id) VALUES (?)",
                      (item_id,))
        else:
            c.execute("DELETE FROM container_ignore WHERE item_id=?", (item_id,))


def ignored_containers() -> set:
    init_container_ignore()
    with _conn() as c:
        return {r["item_id"] for r in c.execute("SELECT item_id FROM container_ignore")}


# ---- item volumes (m3) cache -----------------------------------------------
def init_volumes():
    with _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS type_volumes (
                         type_id INTEGER PRIMARY KEY, volume REAL)""")


def cached_volumes(type_ids) -> dict:
    init_volumes()
    if not type_ids:
        return {}
    with _conn() as c:
        q = "SELECT type_id, volume FROM type_volumes WHERE type_id IN (%s)" % \
            ",".join("?" * len(type_ids))
        return {r["type_id"]: r["volume"] for r in c.execute(q, list(type_ids))}


def save_volumes(mapping: dict):
    init_volumes()
    with _conn() as c:
        c.executemany("INSERT OR REPLACE INTO type_volumes(type_id,volume) VALUES(?,?)",
                      list(mapping.items()))


# ---- maintenance / cleanup --------------------------------------------------
def _table_count(c, table) -> int:
    try:
        return c.execute(f"SELECT COUNT(*) n FROM {table}").fetchone()["n"]
    except Exception:
        return 0


def db_stats() -> dict:
    """File size on disk plus row counts of the tables that actually grow, so
    the cleanup UI can show what is taking space."""
    import os
    path = config.db_path()
    size = 0
    for suffix in ("", "-wal", "-shm"):
        try:
            size += os.path.getsize(path + suffix)
        except OSError:
            pass
    with _conn() as c:
        counts = {t: _table_count(c, t) for t in
                  ("history", "market_snapshot", "transactions", "type_names")}
    return {"size_bytes": size, "counts": counts}


def clear_market_cache() -> dict:
    """Delete the self-healing market caches (per-item history + last hub scan).
    These are re-fetched automatically on the next scan, so this only costs a
    slower next run. Transactions, characters and the shopping list are kept.
    Runs VACUUM so the file on disk actually shrinks."""
    before = db_stats()["size_bytes"]
    with _conn() as c:
        for t in ("history", "history_meta", "market_snapshot", "scan_meta"):
            try:
                c.execute(f"DELETE FROM {t}")
            except Exception:
                pass
    # VACUUM must run outside a transaction / WAL checkpoint
    con = sqlite3.connect(config.db_path(), timeout=60)
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("VACUUM")
    finally:
        con.close()
    after = db_stats()["size_bytes"]
    return {"freed_bytes": max(0, before - after), "size_bytes": after}


def prune_transactions(before_date: str) -> dict:
    """Delete transactions older than an ISO date (YYYY-MM-DD). Sensitive: very
    old buys are the cost basis for long-held items, so the UI warns first.
    Legt davor IMMER ein Backup an (gleiche Regel wie beim Charakter-Entfernen:
    alte Historie ist über ESI nicht wiederbeschaffbar)."""
    backup_db(reason="prune")
    with _conn() as c:
        cur = c.execute("DELETE FROM transactions WHERE date < ?", (before_date,))
        removed = cur.rowcount
    con = sqlite3.connect(config.db_path(), timeout=60)
    try:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        con.execute("VACUUM")
    finally:
        con.close()
    return {"removed": removed, "size_bytes": db_stats()["size_bytes"]}
