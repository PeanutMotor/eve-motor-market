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
            """
        )
    _migrate_history_region()
    _migrate_order_mod_counts()
    _migrate_contract_prices_mean()
    _migrate_snapshot_source()


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
    with _conn() as c:
        return [dict(r) for r in c.execute(
            "SELECT * FROM characters ORDER BY added_at")]


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


def save_snapshot(rows: list, region: int = 10000002, source: str = None) -> None:
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
        src = source or hub_source(region)
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
        c.execute("INSERT OR REPLACE INTO scan_meta(k,v) VALUES('region', ?)",
                  (str(region),))
        c.execute("INSERT OR REPLACE INTO scan_meta(k,v) VALUES('source', ?)",
                  (src,))
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


def note_asset_snapshot(bestand, vollstaendig=True) -> dict:
    """Einen erfolgreichen Bestands-Abruf vermerken. Gibt den Stand zurueck
    (dieselben Felder wie asset_snapshot_info()).

    `vollstaendig=False` (ein Charakter-Abruf ist fehlgeschlagen) schreibt
    NICHTS: aus einem unvollstaendigen Bestand wuerde sonst eine
    'Veraenderung' - genau die Sorte Falschmeldung, die die Anzeige wertlos
    macht. Lieber ein aelterer, ehrlicher Zeitpunkt als ein frischer falscher.
    """
    import time
    if not vollstaendig:
        return asset_snapshot_info()
    fp = asset_fingerprint(bestand)
    jetzt = time.time()
    with _conn() as c:
        row = c.execute(
            "SELECT v FROM scan_meta WHERE k='assets_fingerprint'").fetchone()
        alt = row["v"] if row else None
        c.execute("INSERT OR REPLACE INTO scan_meta(k,v) "
                  "VALUES('assets_checked_at', ?)", (str(jetzt),))
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


def undo_order_mod_count(order_id: int) -> int:
    """Ein Fehlklick rückgängig - zählt eins runter, nie unter 0. Gibt den
    neuen Zählerstand zurück."""
    import time
    with _conn() as c:
        c.execute(
            """UPDATE order_mod_counts SET mod_count = MAX(0, mod_count - 1),
                   updated_at = ? WHERE order_id = ?""",
            (time.time(), order_id))
        row = c.execute("SELECT mod_count FROM order_mod_counts WHERE order_id=?",
                        (order_id,)).fetchone()
    return row["mod_count"] if row else 0


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


def get_scan_region(default: int = 10000002) -> int:
    with _conn() as c:
        row = c.execute("SELECT v FROM scan_meta WHERE k='region'").fetchone()
    return int(row["v"]) if row and row["v"] else default


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
                      "source,sugg_qty) VALUES (?,?,?,?,?,?,?)",
                      (type_id, name, qty, buy, sell, source, sugg_qty))


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
