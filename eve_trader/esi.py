"""Authenticated + public ESI calls."""
import logging
import time

import requests
from requests.adapters import HTTPAdapter

from . import auth, config, store, tokens
from . import APP_NAME as _APP_NAME, __version__ as _VERSION

# Ohne Handler landet eine Warnung nur auf stderr (in der EXE: nirgends) -
# das ist gewollt: kein Dialog fuer einen fehlgeschlagenen Nebenabruf.
_log = logging.getLogger(__name__)

# CCP moechte an dieser Kennung erkennen koennen, welches Werkzeug spricht -
# das ist der Weg, auf dem sie bei Problemen den Entwickler erreichen, statt
# eine Anwendung blind zu sperren. Name und Version kommen aus derselben
# einen Quelle wie ueberall sonst; hier stand vorher der alte Projektname
# und eine fest eingetippte "0.1", die seit Fassung 0.1.0 nicht mehr stimmte.
_USER_AGENT = (f"{_APP_NAME}/{_VERSION} "
               f"(+https://github.com/{config.GITHUB_REPO})")

# Shared HTTP session with a connection pool. Bulk public fetches — most notably
# the ~1700 market-history calls a first hub scan makes — otherwise open a fresh
# TCP+TLS connection PER request, which is the dominant cost of that first run.
# A pooled session reuses keep-alive connections instead. urllib3's pool is
# thread-safe for the concurrent GETs we issue from the scan's worker threads.
# pool_maxsize is sized above the scan's worker count so connections aren't
# constantly discarded and re-opened.
_session = requests.Session()
_session.headers.update({"User-Agent": _USER_AGENT})
_adapter = HTTPAdapter(pool_connections=24, pool_maxsize=24)
_session.mount("https://", _adapter)
_session.mount("http://", _adapter)

# in-memory access-token cache: character_id -> (token, expiry_epoch)
_access_cache = {}


def _access_token(client_id: str, character_id: int) -> str:
    cached = _access_cache.get(character_id)
    if cached and cached[1] - 30 > time.time():
        return cached[0]
    refresh = tokens.get_token(character_id)
    if not refresh:
        from .sprache import t as _txt
        raise RuntimeError(_txt("No token for character {cid}. Link it again.").format(
            cid=character_id))
    data = auth.refresh_tokens(client_id, refresh)
    if data.get("refresh_token"):
        tokens.set_token(character_id, data["refresh_token"])  # rotation
    token = data["access_token"]
    _access_cache[character_id] = (token, time.time() + data.get("expires_in", 1200))
    return token


def scopes_from_token(access_token: str) -> set:
    """Die Scope-Liste aus einem JWT-Zugangstoken. REIN - kein Netz, kein
    Keyring, damit ein Waechter sie mit einem selbstgebauten Token pruefen
    kann. Unlesbares Token -> leere Menge (der Aufrufer behandelt das als
    "wir wissen es nicht")."""
    import base64
    import json as _json
    teile = str(access_token or "").split(".")
    if len(teile) < 2:
        return set()
    roh = teile[1]
    roh += "=" * (-len(roh) % 4)          # Base64url ohne Polsterung
    try:
        daten = _json.loads(base64.urlsafe_b64decode(roh).decode("utf-8"))
    except Exception:
        return set()
    scp = (daten or {}).get("scp") or []
    if isinstance(scp, str):
        scp = scp.split()
    return {str(s) for s in scp}


def granted_scopes(client_id: str, character_id: int) -> set:
    """Die Berechtigungen, die dieser Charakter WIRKLICH erteilt hat.

    WOZU: ESI antwortet auf /universe/structures/{id} mit 403 in ZWEI voellig
    verschiedenen Faellen - die Berechtigung fehlt, ODER der Charakter darf
    dort schlicht nicht andocken. Der zweite Fall ist der Normalfall: man kann
    Orders und liegengebliebenes Material in einer Struktur haben, ohne
    Andockrecht. Wer beides gleich zaehlt, schickt den Nutzer los, eine
    Einstellung zu aendern, die laengst stimmt (Nutzer, Sitzung 19: 100
    verweigerte Strukturen, "Structure Markets ist aber eh standardmaessig
    auf on").

    WOHER: die erteilten Scopes stehen im Zugangs-Token selbst, im Feld `scp`
    des JWT. Kein zusaetzlicher ESI-Aufruf noetig. Die Signatur pruefen wir
    NICHT und muessen es auch nicht: hier faellt keine Sicherheits-
    entscheidung, wir waehlen nur den richtigen Hinweistext. Das Token kommt
    ohnehin gerade von CCP.
    """
    return scopes_from_token(_access_token(client_id, character_id))


def cache_access_token(character_id: int, access_token: str, expires_in: int = 1200):
    """Seed the in-memory cache with a freshly obtained token (e.g. right after
    a re-link), so the new scopes take effect immediately instead of after the
    old cached token expires."""
    _access_cache[character_id] = (access_token, time.time() + expires_in)


def _auth_headers(client_id: str, character_id: int) -> dict:
    return {"Authorization": f"Bearer {_access_token(client_id, character_id)}",
            "User-Agent": _USER_AGENT}


# ESI-Datenstand der Asset-Antworten je Charakter (Last-Modified-Header).
# CCP cacht /assets/ serverseitig ~1 Stunde - frisch abgelieferte Industrie-
# Outputs erscheinen also bis zu 1 h verspätet. Das können wir nicht umgehen,
# aber ehrlich anzeigen ("Bestand laut ESI, Stand vor X min").
_assets_meta = {}


def _record_assets_meta(character_id: int, response) -> None:
    lm = response.headers.get("Last-Modified")
    if not lm:
        _assets_meta.pop(int(character_id), None)
        return
    try:
        from email.utils import parsedate_to_datetime
        _assets_meta[int(character_id)] = parsedate_to_datetime(lm).timestamp()
    except (TypeError, ValueError):
        _assets_meta.pop(int(character_id), None)


def assets_age_seconds(character_id: int):
    """Alter der zuletzt abgerufenen Asset-Daten dieses Charakters in Sekunden
    (laut ESI Last-Modified) - oder None, wenn unbekannt."""
    ts = _assets_meta.get(int(character_id))
    return (time.time() - ts) if ts else None


def _get_with_retry(url, headers=None, params=None, timeout=30, retries=2):
    """GET mit kurzem Retry bei transienten ESI-Fehlern (5xx/Timeout) -
    CCPs Tranquility-Gateway hat gelegentlich kurze Aussetzer (z.B. 502/503/504),
    die sich meist nach 1-2 Sekunden von selbst erledigen. Ohne Retry wurde
    daraus sofort ein harter Fehler in der Statuszeile, obwohl ein zweiter
    Versuch fast immer durchgeht. 4xx-Fehler (Auth/Scope-Probleme) werden NICHT
    wiederholt, die sind nicht transient - deshalb wird der Status-Code VOR
    raise_for_status() geprüft, statt die HTTPError-Exception danach generisch
    abzufangen (die wäre für 4xx UND 5xx gleich, und hätte 403/404 unnötig
    wiederholt)."""
    last_exc = None
    for attempt in range(retries + 1):
        try:
            # gepoolte Session (Keep-Alive) statt nacktem requests.get - sonst
            # zahlt jeder Abruf einen frischen TCP+TLS-Handshake, obwohl der
            # Pool oben genau dafür gebaut wurde. urllib3-Pool ist threadsicher.
            r = _session.get(url, headers=headers, params=params, timeout=timeout)
        except requests.exceptions.RequestException as e:
            last_exc = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        if r.status_code >= 500 and attempt < retries:
            time.sleep(1.5 * (attempt + 1))
            continue
        r.raise_for_status()   # 4xx (oder erschöpfte 5xx-Retries) -> sofort raus
        return r
    raise last_exc


def fetch_wallet_transactions(client_id: str, character_id: int,
                              stop_at_id=None, max_pages: int = 20) -> list:
    """Wallet-Transaktionen (Käufe + Verkäufe) MIT Rückwärtsblättern.

    ESI liefert pro Aufruf nur die ~2500 neuesten Einträge. Wer das Tool eine
    Weile nicht öffnet und viel handelt, verlor damit ältere Transaktionen -
    und mit ihnen die FIFO-Kostenbasis, unwiederbringlich. Deshalb wird jetzt
    per from_id (liefert Einträge ÄLTER als die genannte ID) rückwärts
    geblättert, bis
      - die Seite sich mit dem DB-Bestand überlappt (stop_at_id = neueste
        gespeicherte transaction_id -> Lücke geschlossen, Rest hat die DB),
      - ESI nichts Älteres mehr hat (leere/kurze Seite - Retention ~30 Tage),
      - oder die max_pages-Notbremse greift (20 x 2500 = 50k Einträge).
    Duplikate sind egal - save_transactions dedupliziert per Primärschlüssel."""
    url = f"{config.ESI_BASE}/characters/{character_id}/wallet/transactions/"
    headers = _auth_headers(client_id, character_id)
    out = []
    from_id = None
    for _page in range(max(1, int(max_pages))):
        params = {"from_id": from_id} if from_id else None
        r = _get_with_retry(url, headers=headers, params=params, timeout=30)
        r.raise_for_status()
        rows = r.json() or []
        if not rows:
            break
        out.extend(rows)
        ids = [int(t.get("transaction_id") or 0) for t in rows]
        oldest = min(ids)
        if stop_at_id and oldest <= int(stop_at_id):
            break                      # Überlappung mit DB-Bestand erreicht
        if len(rows) < 2000:
            break                      # kurze Seite = Ende der ESI-Retention
        from_id = oldest               # nächste Seite: alles ÄLTER als das
    return out


def fetch_wallet_transactions_older(client_id: str, character_id: int,
                                    from_id, max_pages: int = 20):
    """Eintraege ÄLTER als `from_id` holen, bis ESI nichts mehr hat.

    WARUM (Sitzung 17, Nutzer-Meldung aus dem Discord): fetch_wallet_
    transactions blaettert nur so lange zurueck, bis es den DB-Bestand
    UEBERLAPPT. Bricht der allererste Abruf ab (Netzfehler, Absturz, Fenster
    zu), stehen nur die neuesten Eintraege in der DB - und JEDER spaetere
    Abruf hoert genau dort auf. Die alten Kaeufe kommen nie mehr, obwohl ESI
    sie noch haette. Ohne Kauf-Lot faellt der Verkauf aus dem Gewinne-Tab
    (market.realized_trades verwirft ihn) - genau das hat der Nutzer gesehen.

    Rueckgabe: (eintraege, fertig). `fertig` = ESI hat nichts Aelteres mehr;
    dann muss nie wieder rueckwaerts geblaettert werden.
    """
    url = f"{config.ESI_BASE}/characters/{character_id}/wallet/transactions/"
    headers = _auth_headers(client_id, character_id)
    out = []
    fertig = False
    for _page in range(max(1, int(max_pages))):
        r = _get_with_retry(url, headers=headers,
                            params={"from_id": int(from_id)}, timeout=30)
        r.raise_for_status()
        rows = r.json() or []
        if not rows:
            fertig = True
            break
        out.extend(rows)
        from_id = min(int(t.get("transaction_id") or 0) for t in rows)
        if len(rows) < 2000:
            fertig = True
            break
    return out, fertig


def fetch_wallet_journal(client_id: str, character_id: int) -> list:
    """Gebühren-relevante Wallet-Journal-Einträge (brokers_fee = Broker beim
    Order-AUFGEBEN/Ändern - Kauf- UND Verkaufsseite -, transaction_tax =
    Verkaufssteuer). ESI liefert rückwirkend ~30 Tage; die DB akkumuliert
    (INSERT OR IGNORE), wie bei den Transaktionen. Rückgabe:
    [{journal_id, date, ref_type, amount}] - amount ist bei Gebühren NEGATIV.
    Grundlage für die ECHTEN Gebühren im Gewinne-Tab statt Formel-Schätzung
    (die Formel weiß nicht, ob ein Kauf per eigener Buy-Order lief - mit
    Broker - oder instant aus Sell-Orders - ohne)."""
    base = f"{config.ESI_BASE}/characters/{character_id}/wallet/journal/"
    headers = _auth_headers(client_id, character_id)
    first = _get_with_retry(base, params={"page": 1}, headers=headers, timeout=30)
    first.raise_for_status()
    pages = int(first.headers.get("X-Pages", "1"))
    rows = list(first.json() or [])
    for p in range(2, pages + 1):
        r = _get_with_retry(base, params={"page": p}, headers=headers, timeout=30)
        r.raise_for_status()
        rows.extend(r.json() or [])
    out = []
    for j in rows:
        rt = j.get("ref_type")
        if rt not in ("brokers_fee", "transaction_tax"):
            continue
        out.append({"journal_id": j.get("id"), "date": j.get("date"),
                    "ref_type": rt, "amount": float(j.get("amount") or 0.0)})
    return out


def fetch_wallet_balance(client_id: str, character_id: int) -> float:
    """Current liquid ISK on the character's wallet. Needs
    esi-wallet.read_character_wallet.v1."""
    url = f"{config.ESI_BASE}/characters/{character_id}/wallet/"
    r = _get_with_retry(url, headers=_auth_headers(client_id, character_id), timeout=30)
    r.raise_for_status()
    return float(r.json())


def fetch_character_orders(client_id: str, character_id: int) -> list:
    """Open market orders of the character. Needs
    esi-markets.read_character_orders.v1. Each order has price, volume_remain,
    is_buy_order and (for buy orders) escrow."""
    url = f"{config.ESI_BASE}/characters/{character_id}/orders/"
    r = _get_with_retry(url, headers=_auth_headers(client_id, character_id), timeout=30)
    r.raise_for_status()
    return r.json()


def _fetch_all_assets(client_id: str, character_id: int) -> list:
    base = f"{config.ESI_BASE}/characters/{character_id}/assets/"
    headers = _auth_headers(client_id, character_id)
    first = _get_with_retry(base, params={"page": 1}, headers=headers, timeout=30)
    first.raise_for_status()
    pages = int(first.headers.get("X-Pages", "1"))
    assets = list(first.json())
    for p in range(2, pages + 1):
        r = _get_with_retry(base, params={"page": p}, headers=headers, timeout=30)
        r.raise_for_status()
        assets.extend(r.json())
    return assets


def fetch_asset_names(client_id: str, character_id: int, item_ids: list) -> dict:
    """Custom names of containers/ships (assets endpoint). Needs assets scope."""
    url = f"{config.ESI_BASE}/characters/{character_id}/assets/names/"
    headers = _auth_headers(client_id, character_id)
    out = {}
    for i in range(0, len(item_ids), 1000):
        chunk = item_ids[i:i + 1000]
        r = _session.post(url, json=chunk, headers=headers, timeout=30)
        r.raise_for_status()
        for row in r.json():
            nm = row.get("name")
            out[row["item_id"]] = nm if nm and nm != "None" else None
    return out


def container_type_ids_safe() -> set:
    """Die Behaelter-Typen aus der SDE - darf nie etwas kosten.

    Spaeter Import wie beim SDE-Download weiter unten: `esi` soll nicht beim
    Laden schon an `industry` haengen. Faellt die SDE aus, kommt ein leeres
    Set zurueck und es gilt wieder allein die alte Inhalts-Regel.
    """
    try:
        from . import industry
        return industry.container_type_ids()
    except Exception:
        return set()


def _behaelter_pruefer(by_parent, container_typen=None):
    """Liefert die Frage "ist das ein Behaelter?" - EINE Regel fuer alle.

    Sie steht hier fuer sich, weil beide Bestands-Zaehlungen sie brauchen
    (Portfolio/"Ueberall" und die ortsgebundenen Bau-Bereiche). Zwei Kopien
    derselben Regel waeren zwei Wahrheiten - genau der Zustand, aus dem der
    Frachtcontainer-Fehler entstanden ist.

    `by_parent`: {location_id: [Assets darin]}.
    """
    _ctypes = set(container_typen or ())
    inner = {"Unlocked", "Locked"}

    def _ist_behaelter(a):
        if a.get("type_id") in _ctypes:
            return True
        # Alte Regel als Rueckfall: hat es Kinder mit Schloss-Markierung?
        return any(c.get("location_flag") in inner
                   for c in by_parent.get(a.get("item_id"), []))

    return _ist_behaelter


def hangar_und_container(assets, container_typen=None):
    """Hangar-Inhalt und Behaelter aus einer rohen Assets-Liste trennen.

    Gibt ({type_id: Menge}, [{item_id, type_id, name, contents}]) zurueck.

    EIGENE, PURE FUNKTION (statt mitten im ESI-Abruf): nur so laesst sich
    der Fall ohne Netz und ohne Spielstand nachstellen - genau daran ist der
    Fehler unten jahrelang unbemerkt geblieben.

    DER FEHLER, den der Nutzer am 15.09.2026 gemeldet hat: "das Portfolio
    trackt nur Items in Station Containern und in keinen anderen
    Containern." Ein Behaelter wurde bisher allein daran erkannt, dass sein
    INHALT die Markierung `Unlocked`/`Locked` trug. Die tragen aber nur die
    abschliessbaren Station-Container. Ein Freight Container im Hangar galt
    damit als gewoehnliches Item - und alles darin war fuer das Portfolio
    schlicht nicht vorhanden.

    JETZT WIRD DER BEHAELTER ERKANNT, NICHT SEIN INHALT: `container_typen`
    kommt aus der SDE (Gruppenname "... Container"). Bei so einem Typ zaehlt
    JEDES Kind als Inhalt, egal welche Markierung ESI dranschreibt - ein
    Behaelter hat keine Modulplaetze, alles darin IST Inhalt. Damit ist die
    Regel unabhaengig davon, welche Markierung CCP je Behaelterart vergibt.

    DIE ALTE REGEL BLEIBT DANEBEN BESTEHEN: ohne SDE (leeres
    `container_typen`) werden Station-Container weiter ueber ihren Inhalt
    erkannt. Eine Verbesserung darf nie schlechter sein als der Zustand,
    den sie ersetzt.

    NUR EINE EBENE TIEF WEITER: in einen Behaelter IM Behaelter wird
    hinabgestiegen, in ein SCHIFF im Behaelter nicht. Sonst zaehlten
    gefittete Module und Drohnen als Lagerbestand - und ein Bestand, der zu
    hoch ausgewiesen wird, ist die gefaehrliche Richtung (Regel 3).
    """
    _ctypes = set(container_typen or ())
    by_parent = {}
    for a in assets or []:
        by_parent.setdefault(a.get("location_id"), []).append(a)
    _ist_behaelter = _behaelter_pruefer(by_parent, _ctypes)

    hangar = {}
    containers = []
    for a in assets or []:
        if a.get("location_flag") != "Hangar":
            continue
        if not _ist_behaelter(a):
            hangar[a["type_id"]] = hangar.get(a["type_id"], 0) + a.get("quantity", 1)
            continue
        contents = {}
        stack = list(by_parent.get(a.get("item_id"), []))
        gesehen = set()
        while stack:
            c = stack.pop()
            _cid = c.get("item_id")
            if _cid in gesehen:
                continue
            gesehen.add(_cid)
            contents[c["type_id"]] = contents.get(c["type_id"], 0) + c.get("quantity", 1)
            if _ist_behaelter(c):
                stack.extend(by_parent.get(_cid, []))
        containers.append({"item_id": a.get("item_id"), "type_id": a["type_id"],
                           "name": None, "qty": a.get("quantity", 1),
                           "contents": contents})
    return hangar, containers


def hangar_summe(assets, container_typen=None) -> dict:
    """{type_id: Menge} fuer ALLES im Hangar - lose Items, die Behaelter
    selbst und ihr Inhalt.

    EINE WAHRHEIT FUER "WAS LIEGT IM HANGAR" (Arbeitsregel 9). Der Bauplan
    zaehlte im Bereich "Ueberall" mit einer EIGENEN Regel: Inhalt nur dann,
    wenn ESI ihn `Unlocked`/`Locked` markiert. Das Portfolio hatte dieselbe
    Regel - bis der Nutzer am 15.09.2026 zeigte, dass Freight Container so
    durchfallen. Beide Stellen jetzt auf derselben Funktion.

    DER BEHAELTER SELBST BLEIBT GEZAEHLT: ein Cargo Container ist ein
    baubares Item und kann Material sein. Ihn stillschweigend fallen zu
    lassen waere ein zu NIEDRIGER Bestand - und damit ein Einkauf zu viel.
    """
    hangar, container = hangar_und_container(assets, container_typen)
    summe = dict(hangar)
    for c in container:
        _t = int(c["type_id"])
        summe[_t] = summe.get(_t, 0) + int(c.get("qty") or 1)
        for t, q in (c.get("contents") or {}).items():
            summe[int(t)] = summe.get(int(t), 0) + int(q)
    return summe


def bestand_an_orten(assets, location_ids, container_typen=None):
    """Alles, was an diesen Orten haengt - PURE Funktion, ohne Netz pruefbar.

    Gibt ({type_id: Menge}, gesehene item_ids, {location_id: Anzahl Zeilen})
    zurueck. Das ist die Zaehlung der Bestandsbereiche "Nur Bau-Strukturen"
    und "Nur wo dieser Plan baut".

    SIE STEIGT IN BEHAELTER HINAB und fragt dort KEINE Markierung: was in
    einem Behaelter an der Struktur liegt, liegt an der Struktur. Deshalb
    war der gemeldete Frachtcontainer-Fehler hier nie ein Thema - anders als
    im Bereich "Ueberall", der bis zum 16.09.2026 eine eigene, markierungs-
    abhaengige Regel hatte.

    IN SCHIFFE ABER NICHT (Nutzer, 16.09.2026: "Schiffe und deren Fittings
    und Inhalt sollten niemals zaehlen, in keinem Szenario" - fuers BAUEN;
    im Portfolio bleibt alles wie es ist). Vorher stieg diese Schleife in
    JEDES Kind hinab, also auch in gefittete Module, Drohnen und
    Schiffsladung. Die galten damit als Baumaterial an der Struktur. Ein zu
    HOCH ausgewiesener Bestand ist die gefaehrliche Richtung (Regel 3): der
    Plan haelt Material fuer vorhanden, das im Job nicht verfuegbar ist.
    Der Rumpf selbst zaehlt weiter - er liegt an der Struktur wie jedes
    andere Item.

    HERAUSGELOEST (16.09.2026, Nutzer-Frage "erkennen die beiden Bereiche
    Container-Inhalte auch?"): vorher steckte diese Schleife im ESI-Abruf
    und war damit ohne Spielstand nicht nachstellbar - also unbewacht. Eine
    Zusage, die niemand nachpruefen kann, ist keine.
    """
    by_parent = {}
    for a in assets or []:
        by_parent.setdefault(a.get("location_id"), []).append(a)
    _ist_behaelter = _behaelter_pruefer(by_parent, container_typen)
    out = {}
    seen = set()

    def collect(loc):
        for a in by_parent.get(loc, []):
            iid = a.get("item_id")
            if iid in seen:
                continue
            seen.add(iid)
            out[a["type_id"]] = out.get(a["type_id"], 0) + a.get("quantity", 1)
            if _ist_behaelter(a):
                collect(iid)     # in den Behaelter-Inhalt hinein
    per_loc = {}
    for loc in {int(x) for x in location_ids or ()}:
        _vorher = len(seen)
        collect(loc)
        per_loc[loc] = len(seen) - _vorher
    return out, seen, per_loc


def fetch_assets_structured(client_id: str, character_id: int) -> dict:
    """Return hangar items plus each hangar container with its (nested) contents.

    {
      "hangar": {type_id: qty},                      # loose items in the hangar
      "containers": [
        {"item_id", "type_id", "name", "contents": {type_id: qty}},
        ...
      ]
    }
    Excludes fitted modules, ship cargo, drones and items in space."""
    assets = _fetch_all_assets(client_id, character_id)
    _ctypes = container_type_ids_safe()
    hangar, containers = hangar_und_container(assets, _ctypes)

    if containers:
        try:
            names = fetch_asset_names(client_id, character_id,
                                      [c["item_id"] for c in containers])
            for c in containers:
                c["name"] = names.get(c["item_id"])
        except requests.HTTPError:
            pass
    return {"hangar": hangar, "containers": containers}


def fetch_assets(client_id: str, character_id: int, only_hangar: bool = True) -> dict:
    """Return {type_id: total_quantity} for the character's assets.

    With only_hangar=True (default) counts items in a station hangar AND the
    contents of containers sitting in that hangar (nested containers included),
    while excluding fitted modules, drones, ship cargo and items in space.
    Raises requests.HTTPError (403) without the assets scope."""
    base = f"{config.ESI_BASE}/characters/{character_id}/assets/"
    headers = _auth_headers(client_id, character_id)
    first = _get_with_retry(base, params={"page": 1}, headers=headers, timeout=30)
    first.raise_for_status()
    _record_assets_meta(character_id, first)
    pages = int(first.headers.get("X-Pages", "1"))
    assets = list(first.json())
    for p in range(2, pages + 1):
        r = _get_with_retry(base, params={"page": p}, headers=headers, timeout=30)
        r.raise_for_status()
        assets.extend(r.json())

    if not only_hangar:
        totals = {}
        for a in assets:
            totals[a["type_id"]] = totals.get(a["type_id"], 0) + a.get("quantity", 1)
        return totals

    # DIESELBE REGEL WIE IM PORTFOLIO (Nutzer-Frage 16.09.2026, ob der
    # Bauplan-Bereich "Ueberall" noch die alte Erkennung benutzt - er tat
    # es). Vorher stand hier eine zweite, eigene Zaehlung: Inhalt nur bei
    # der Markierung `Unlocked`/`Locked`. Die neue Regel erkennt den
    # BEHAELTER an seinem Typ und ist damit ein OBERBEGRIFF der alten (die
    # bleibt als Rueckfall in `hangar_und_container` stehen) - es kann
    # also nichts wegfallen, was frueher gezaehlt wurde.
    return hangar_summe(assets, container_type_ids_safe())


def fetch_type_image_bytes(type_id: int, size: int = 64, kind: str = "icon") -> bytes:
    """Item-/Blueprint-/Schiffs-Bild von CCPs öffentlichem Bilder-Server (kein
    Auth nötig, nicht Teil der SDE). kind: 'icon' (alle Items, quadratisch,
    z.B. Blueprints/Datacores/Decryptoren) oder 'render' (nur Schiffe, echtes
    3D-Renderbild). size: 32/64/128/256/512 (CCP rundet automatisch auf die
    nächste unterstützte Größe). Wirft bei Fehler (404 = kein Bild für diesen
    Typ/kind) eine Exception - der Aufrufer soll das abfangen und einen
    Platzhalter/Text-Fallback zeigen, NICHT raten oder ein Bild erfinden."""
    url = f"https://images.evetech.net/types/{int(type_id)}/{kind}?size={int(size)}"
    r = _session.get(url, timeout=15)
    r.raise_for_status()
    return r.content


def fetch_character_portrait_bytes(character_id: int, size: int = 64) -> bytes:
    """Charakter-Portrait von CCPs öffentlichem Bilder-Server (kein Auth
    nötig). size: 32/64/128/256/512/1024 (CCP rundet auf die nächste
    unterstützte Größe). Wirft bei Fehler eine Exception - der Aufrufer zeigt
    dann einfach keinen Portrait an."""
    url = f"https://images.evetech.net/characters/{int(character_id)}/portrait?size={int(size)}"
    r = _session.get(url, timeout=15)
    r.raise_for_status()
    return r.content


def resolve_volumes(type_ids) -> dict:
    """Item volume in m³ per type, cached. Uses packaged_volume when present
    (ships/modules pack smaller), else the base volume."""
    from . import store
    ids = list({int(t) for t in type_ids})
    have = store.cached_volumes(ids)
    missing = [t for t in ids if t not in have]
    fetched = {}
    for t in missing:
        try:
            r = _session.get(f"{config.ESI_BASE}/universe/types/{t}/",
                             timeout=20)
            r.raise_for_status()
            d = r.json()
            vol = d.get("packaged_volume") or d.get("volume") or 0
            fetched[t] = float(vol)
        except Exception:
            fetched[t] = 0.0
    if fetched:
        store.save_volumes(fetched)
    have.update(fetched)
    return have


def _resolve_names_chunk(chunk) -> dict:
    """POST ids to /universe/names/. ESI antwortet 404 für den GANZEN Batch,
    wenn EINE id ungültig ist - NUR DANN wird gesplittet, um die kaputte id zu
    isolieren (alle guten Namen kommen trotzdem durch). Bei Rate-Limit (420/429),
    5xx oder Netzfehlern wird NICHT gesplittet - sonst würden aus einem Batch
    bis zu 1000 Einzel-Requests GEGEN ein aktives Rate-Limit (Split-Bombe);
    die Namen bleiben dann einfach ungecacht und kommen beim nächsten Versuch.
    Returns {id: name}."""
    if not chunk:
        return {}
    try:
        r = _session.post(f"{config.ESI_BASE}/universe/names/",
                          json=list(chunk), timeout=30)
    except Exception:
        return {}                      # Netzfehler: nicht splitten, später erneut
    if r.ok:
        try:
            return {item["id"]: item["name"] for item in r.json()}
        except Exception:
            return {}
    if r.status_code != 404:
        return {}                      # 420/429/5xx: nicht splitten, später erneut
    if len(chunk) == 1:
        return {}                      # this single id is the unresolvable one
    mid = len(chunk) // 2
    out = _resolve_names_chunk(chunk[:mid])
    out.update(_resolve_names_chunk(chunk[mid:]))
    return out


def _aufrufer_ausserhalb_esi():
    """Erste Stelle im Stapel, die NICHT in dieser Datei liegt - also der
    Aufrufer, der die ID hineingegeben hat.

    NUTZER-FALL (Sitzung 20): im Protokoll stand `type_id 300: HTTP 404`.
    300 ist gar keine Type-ID, sondern die Gruppe "Cyberimplant" - irgendeine
    Liste schiebt also eine fremde ID in die Namensaufloesung. WELCHE, war aus
    der Zeile nicht zu erkennen, und `resolve_names` wird an ueber zwanzig
    Stellen gefuettert. Ohne die Herkunft bleibt nur Raten.
    """
    import os as _os
    import traceback as _tb
    try:
        _hier = _os.path.basename(__file__)
        for _f in reversed(_tb.extract_stack()):
            if _os.path.basename(_f.filename) != _hier:
                return f"{_os.path.basename(_f.filename)}:{_f.lineno} {_f.name}()"
    except Exception:
        pass
    # de_scan4: aus - Eintrag fuer fehler.log, nicht Oberflaeche
    return "unbekannt"
    # de_scan4: an


def _log_name_fail(msg):
    """Fehlgeschlagene Namensaufloesung ins Fehlerprotokoll schreiben.

    Der Nutzer sieht seit Stunden "#16666" statt eines Itemnamens, und drei
    Vermutungen dazu waren falsch (Batch-Groesse, Kategorie-Filter,
    fehlender Fallback). Ohne den ANTWORT-CODE von ESI ist die vierte
    genauso wertlos - also wird er festgehalten.

    SEIT SITZUNG 20 AUCH DIE HERKUNFT: der Antwortcode sagt, dass ESI die ID
    nicht kennt - nicht, wer sie hineingegeben hat. Beides zusammen macht die
    Zeile in einer Minute beantwortbar statt in einer Stunde.
    """
    import datetime as _dt
    import os as _os
    import sys as _sys
    _woher = _aufrufer_ausserhalb_esi()
    try:
        base = _os.path.dirname(_os.path.abspath(_sys.argv[0])) or _os.getcwd()
        with open(_os.path.join(base, "fehler.log"), "a", encoding="utf-8") as fh:
            # de_scan5: aus  (Zeile in fehler.log, kein Anzeigetext)
            fh.write("\n" + _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                     + "  [Namensaufloesung] " + str(msg)
                     + "  (aufgerufen aus " + _woher + ")\n")
            # de_scan5: an
    except Exception:
        pass


def _resolve_type_single(tid):
    """Fallback für EINE type_id, die /universe/names/ nicht auflösen kann
    (manche unpublished/spezielle Items). /universe/types/{id}/ kennt sie oft doch.
    Gibt den Namen oder None zurück."""
    try:
        r = _session.get(f"{config.ESI_BASE}/universe/types/{int(tid)}/",
                         params={"datasource": "tranquility"}, timeout=15)
        if r.ok:
            nm = (r.json() or {}).get("name")
            if nm:
                return nm
            # de_scan4: aus - Eintrag fuer fehler.log, nicht Oberflaeche
            _log_name_fail(f"type_id {tid}: HTTP {r.status_code}, aber kein "
                           f"Name im Ergebnis")
            # de_scan4: an
            return None
        _log_name_fail(f"type_id {tid}: HTTP {r.status_code} "
                       f"{str(r.text)[:120]}")
    except Exception as e:
        _log_name_fail(f"type_id {tid}: {type(e).__name__}: {str(e)[:120]}")
    return None


def resolve_names(type_ids) -> dict:
    """Resolve typeIDs -> names, using cache + ESI /universe/names/. Resilient to
    individual bad ids (one bad id no longer blanks the whole batch). IDs that
    /universe/names/ can't resolve get a second try via /universe/types/{id}/."""
    # NIE NEGATIVE IDS AN ESI (Multi-Bauplan 1.0.9: das Buendel heisst -1
    # und ist kein Item - /universe/names/ wuerde den ganzen Block ablehnen).
    ids = sorted(set(int(t) for t in type_ids if int(t) > 0))
    result = store.cached_names(ids)
    missing = [t for t in ids if t not in result]
    new = {}
    for i in range(0, len(missing), 1000):
        new.update(_resolve_names_chunk(missing[i:i + 1000]))
    # Was /universe/names/ NICHT auflösen konnte, einzeln per types-Endpoint
    # nachziehen (z.B. type_id 16664). So bleibt keine "#12345"-Zeile übrig.
    still_missing = [t for t in missing if t not in new]
    # BREMSE gegen die Split-Bombe: bei vielen unaufloesbaren ids wuerden
    # hier Hunderte Einzel-Requests gegen ein aktives Rate-Limit laufen und
    # ALLE scheitern - dann bleiben Zeilen dauerhaft als "#12345" stehen
    # (vom Nutzer gemeldet). Ein Fehlschlag beendet die Runde; die restlichen
    # Namen kommen beim naechsten Oeffnen dran, statt das Limit zu fuettern.
    _fails = 0
    for t in still_missing:
        nm = _resolve_type_single(t)
        if nm:
            new[t] = nm
            _fails = 0
        else:
            _fails += 1
            if _fails >= 3:
                break
    if new:
        store.save_names(new)
        result.update(new)
    return result


# Market/trade skill type IDs (stable EVE IDs)
SKILL_ACCOUNTING = 16622
SKILL_BROKER_RELATIONS = 3446


def job_is_finished(job: dict, now: float = None) -> bool:
    """Ist ein Industry-Job FERTIG (Output existiert), aber noch nicht
    abgeliefert? ESI-Falle: CCP setzt den Status 'ready' praktisch NIE -
    fertige, unabgeholte Jobs bleiben auf status='active', nur ihr end_date
    liegt in der Vergangenheit (Nutzer-Fall: fertige Reaktionen standen
    tagelang im Industriefenster und der virtuelle Bestand sah sie nicht,
    weil er nur auf 'ready'/'delivered' prüfte). Deshalb: 'ready' ODER
    'active' mit abgelaufenem end_date."""
    st = job.get("status")
    if st == "ready":
        return True
    if st != "active":
        return False
    import time as _t
    from datetime import datetime as _dt
    try:
        end = _dt.fromisoformat(
            str(job.get("end_date")).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return False
    return end <= (now if now is not None else _t.time())


def fetch_active_jobs(client_id: str, character_id: int,
                      include_delivered: bool = False) -> list:
    """Aktive/pausierte Industry-Jobs des Charakters MIT Details:
    [{job_id, activity_id, product_type_id, blueprint_type_id, runs,
      start_date, end_date, status}].
    activity_id: 1=Fertigung, 3=TE-Research, 4=ME-Research, 5=Kopieren,
    8=Invention, 9/11=Reaktion. job_id + start_date: um NEUE Jobs zu erkennen
    (z.B. für die Verzugs-Erkennung im Bau-Kalender).
    include_delivered=True liefert zusätzlich ABGELIEFERTE Jobs (Status
    'delivered' + completed_date) - Basis für den virtuellen Bestand: frisch
    Abgeliefertes ist wegen des ~1-h-Asset-Caches von CCP noch nicht in
    /assets/ sichtbar, aber die Job-Liste (Cache ~5 min) kennt es schon."""
    url = f"{config.ESI_BASE}/characters/{character_id}/industry/jobs/"
    r = _get_with_retry(url, headers=_auth_headers(client_id, character_id),
                     params={"include_completed":
                             "true" if include_delivered else "false"},
                     timeout=30)
    r.raise_for_status()
    allowed = ("active", "paused", "ready") + \
        (("delivered",) if include_delivered else ())
    out = []
    for j in r.json() or []:
        st = j.get("status")
        # "ready" = fertig, aber noch nicht abgeliefert: MUSS mit rein - sonst
        # verschwindet ein fertiger (Reaktions-)Job aus dem "läuft schon"-Label,
        # obwohl sein Output noch nirgends im Lager ist, und der Bauplan
        # behauptet, man müsse ihn nochmal bauen.
        if st and st not in allowed:
            continue
        out.append({
            "job_id": j.get("job_id"),
            "activity_id": j.get("activity_id"),
            "product_type_id": j.get("product_type_id"),
            "blueprint_type_id": j.get("blueprint_type_id"),
            # DIE BLAUPAUSE IM JOB (item_id, 26.09.2026): damit
            # `blaupausen_in_jobs` sie aus dem Vorrat streichen kann.
            "blueprint_id": j.get("blueprint_id"),
            "runs": j.get("runs"),
            "start_date": j.get("start_date"),
            "end_date": j.get("end_date"),
            "completed_date": j.get("completed_date"),
            "status": st,
        })
    return out


# Aktivitaeten, die WIRKLICH ein Item herstellen: Fertigung und die beiden
# Reaktions-Kennungen. Forschung (3/4), Kopieren (5) und Invention (8)
# gehoeren NICHT dazu - ihr `product_type_id` ist eine Blaupause, kein
# gebautes Stueck; wer sie mitzaehlt, meldet Fortschritt fuer etwas, das
# nie im Hangar landet.
HERSTELLENDE_AKTIVITAETEN = (1, 9, 11)


def fetch_delivered_jobs(client_id: str, character_id: int) -> list:
    """Abgeschlossene ("delivered") HERSTELLENDE Jobs des Charakters -
    Grundlage der "Meine Baupläne"-Fertig-Erkennung UND des
    Fortschrittsbalkens. ESI liefert hier standardmäßig nur die letzten ~90
    Tage zurück (CCP-seitige Grenze, nicht unsere).

    BEFUND 22.09.2026 (Nutzer: "es fühlt sich an, als gäbe es am Anfang kaum
    Fortschritt und dann springt der Balken von 20 % auf 100 %"): hier stand
    `activity_id != 1` - REAKTIONEN fielen also komplett heraus. Für die
    Fertig-Erkennung des Endprodukts war das gedacht und meist harmlos; der
    Fortschrittsbalken kam aber später dazu und zählt POSITIONEN über ALLE
    Stufen - und die ersten Stufen eines Schiffsplans sind fast nur
    Reaktionen. Die konnten damit NIE als erledigt gelten, egal wie viele
    davon liefen. Genau dieselbe Fehlerklasse wie "unrefined war keine
    Reaktion" (21.09.2026): eine Liste, die für einen Zweck gefiltert wurde,
    bekam später einen zweiten Zweck.
    `activity_id` wandert jetzt mit, damit der Aufrufer die Frage selbst
    stellen kann, statt sie hier vorentschieden zu bekommen."""
    url = f"{config.ESI_BASE}/characters/{character_id}/industry/jobs/"
    r = _get_with_retry(url, headers=_auth_headers(client_id, character_id),
                     params={"include_completed": "true"}, timeout=30)
    r.raise_for_status()
    out = []
    for j in r.json() or []:
        if j.get("status") != "delivered":
            continue
        if j.get("activity_id") not in HERSTELLENDE_AKTIVITAETEN:
            continue
        out.append({
            "job_id": j.get("job_id"),
            "activity_id": j.get("activity_id"),
            "product_type_id": j.get("product_type_id"),
            "blueprint_type_id": j.get("blueprint_type_id"),
            "runs": j.get("runs"),
            "end_date": j.get("end_date"),
        })
    return out


def fetch_character_implants(client_id: str, character_id: int) -> list:
    """Aktuell eingesteckte Implantate des Charakters (type_ids) - z.B. um
    Zainou 'Beancounter' Industry BX-80X (Fertigungszeit-Bonus) zu erkennen.
    Leere Liste, wenn keine Implantate eingesteckt sind ODER der Scope fehlt
    (esi-clones.read_implants.v1 - siehe config.IMPLANT_SCOPE)."""
    url = f"{config.ESI_BASE}/characters/{character_id}/implants/"
    r = _get_with_retry(url, headers=_auth_headers(client_id, character_id), timeout=30)
    r.raise_for_status()
    return r.json() or []


JOB_SPERRT_BLAUPAUSE = ("active", "paused")
# FERTIGUNG SPERRT NIE (Nutzer 26.09.2026: "ich moechte, dass Fertigungs-
# auftraege niemals die Blueprints sperren. Das muss sein, weil ESI zu
# langsam trackt"): ein abgelieferter Bau-Job steht bei ESI noch Minuten
# als laufend, und solange fehlte die Blaupause im Runplaner. Nur
# Forschung, Kopie, Invention (und Reaktion) sperren.
JOB_SPERRT_NICHT_AKTIVITAET = (1,)     # 1 = Manufacturing


def blaupausen_in_jobs(blueprints, jobs):
    """Blaupausen markieren, die gerade in einem Industrie-Job stecken.
    Rein: {b} bekommt `in_job` = {job_id, activity_id, end_date}, wenn ihre
    item_id die blueprint_id eines nicht abgelieferten Jobs ist. Gibt
    (verfuegbar, belegt) zurueck.

    NUTZER-BEFUND 26.09.2026: "ich habe Component Blueprints am Researchen
    auf ME und TE in der Bauschleife, das Tool denkt jetzt ich habe diese
    zur Verfuegung ... ich habe eigentlich nur 5 Titanium Diborite Armor
    Plate Blueprint, die ich benutzen kann, die anderen sind am Researchen
    und das Tool denkt ich besitze 8 Stueck." ESI listet eine Blaupause im
    Job weiter unter /blueprints/; nur der Job (/industry/jobs/,
    blueprint_id) verraet, dass sie gerade nicht greifbar ist - egal ob
    Research, Kopie, Invention oder Fertigung. Regel 3: lieber eine
    Blaupause zu wenig als eine, die im Spiel gar nicht frei ist."""
    # NUR laufende Jobs sperren (Nutzer 26.09.2026: "Fertigung koennte zum
    # Problem werden, wenn etwas abholbereit ist, sollte es dennoch
    # zaehlen"): 'ready' braucht nur den Klick auf Abliefern, 'delivered',
    # 'cancelled' und 'reverted' haben die Blaupause schon zurueckgegeben.
    # 'paused' (Struktur ohne Strom) haelt sie weiter fest.
    belegt_von = {}
    for j in jobs or []:
        bid = j.get("blueprint_id")
        if bid is None or j.get("status") not in JOB_SPERRT_BLAUPAUSE:
            continue
        if j.get("activity_id") in JOB_SPERRT_NICHT_AKTIVITAET:
            continue
        belegt_von[int(bid)] = j
    frei, belegt = [], []
    for b in blueprints or []:
        j = belegt_von.get(b.get("item_id")) if b.get("item_id") is not None else None
        if j is None:
            frei.append(b)
            continue
        b = dict(b)
        b["in_job"] = {"job_id": j.get("job_id"),
                       "activity_id": j.get("activity_id"),
                       "end_date": j.get("end_date")}
        belegt.append(b)
    return frei, belegt


def fetch_blueprints(client_id: str, character_id: int, jobs=None,
                     mit_belegten: bool = False) -> list:
    """Alle persönlichen Blueprints eines Charakters (egal wo sie liegen:
    Stationen, Strukturen, Container, im Schiff). Braucht den Scope
    esi-characters.read_blueprints.v1.

    Rückgabe je Blueprint:
    [{item_id, type_id, quantity, material_efficiency, time_efficiency, runs,
      is_bpo, location_id}].
    - runs = -1 bei einer BPO (unbegrenzt), sonst verbleibende Runs einer BPC.
    - quantity = -1 bedeutet laut ESI eine einzelne BPO, -2 eine einzelne BPC;
      wir leiten daraus is_bpo ab und normalisieren quantity auf >=1.

    BLAUPAUSEN IN JOBS (26.09.2026, s. blaupausen_in_jobs) fehlen in der
    Rueckgabe - sie sind im Spiel nicht greifbar. `jobs` kann der Aufrufer
    mitgeben (spart den Abruf); sonst werden sie hier geholt. Scheitert
    dieser Abruf, bleibt es beim alten Verhalten (alle Blaupausen), und der
    Grund steht im Log. `mit_belegten=True` liefert sie MIT, markiert mit
    `in_job` (fuer den Blueprints-Ueberblick).

    ACHTUNG: Nur PERSÖNLICHE Blueprints. Blueprints in einem Corp-Hangar
    erscheinen hier NICHT (die bräuchten einen Corp-Scope + Rollen)."""
    base = f"{config.ESI_BASE}/characters/{character_id}/blueprints/"
    headers = _auth_headers(client_id, character_id)
    first = _get_with_retry(base, params={"page": 1}, headers=headers, timeout=30)
    first.raise_for_status()
    pages = int(first.headers.get("X-Pages", "1"))
    rows = list(first.json() or [])
    for p in range(2, pages + 1):
        r = _get_with_retry(base, params={"page": p}, headers=headers, timeout=30)
        r.raise_for_status()
        rows.extend(r.json() or [])
    out = []
    for b in rows:
        raw_qty = b.get("quantity", 1)
        # ESI: quantity -1 = einzelne BPO, -2 = einzelne BPC (aus dem Stack),
        # sonst die tatsächliche Stückzahl. runs -1 = BPO (unbegrenzt).
        runs = b.get("runs", -1)
        is_bpo = (runs == -1) or (raw_qty == -1)
        qty = raw_qty if raw_qty and raw_qty > 0 else 1
        out.append({
            "item_id": b.get("item_id"),
            "type_id": b.get("type_id"),
            "quantity": qty,
            "material_efficiency": b.get("material_efficiency", 0),
            "time_efficiency": b.get("time_efficiency", 0),
            "runs": runs,
            "is_bpo": is_bpo,
            "location_id": b.get("location_id"),
        })
    if jobs is None:
        try:
            jobs = fetch_active_jobs(client_id, character_id)
        except Exception as _e:
            # Englisch, weil de_scan jede deutsche Zeichenkette zaehlt
            # (Logtext, nie Oberflaeche).
            _log.warning("blueprints: jobs of %s unavailable (%s) - "
                         "blueprints in jobs stay listed as free",
                         character_id, _e)
            jobs = []
    frei, belegt = blaupausen_in_jobs(out, jobs)
    return frei + belegt if mit_belegten else frei


# ---------------------------------------------------------------------------
# CORP-HANGAR (1.0.8, nur fuers Bauen). Reine Logik in corp.py; hier nur die
# Abrufe. Jeder braucht seinen eigenen Scope (config.CORP_*_SCOPE) UND eine
# Ingame-Rolle (corp.ROLLE_*); ohne Rolle antwortet ESI mit 403.
# ---------------------------------------------------------------------------

def _get_alle_seiten(base, headers, params=None, timeout=30):
    """Alle Seiten eines paginierten ESI-Endpunkts (X-Pages) einsammeln.
    Gibt (zeilen, erste_antwort) zurueck - die erste Antwort traegt den
    Last-Modified-Header fuer das Datenalter."""
    _p = dict(params or {})
    _p["page"] = 1
    first = _get_with_retry(base, params=_p, headers=headers, timeout=timeout)
    first.raise_for_status()
    pages = int(first.headers.get("X-Pages", "1"))
    rows = list(first.json() or [])
    for p in range(2, pages + 1):
        _p["page"] = p
        r = _get_with_retry(base, params=_p, headers=headers, timeout=timeout)
        r.raise_for_status()
        rows.extend(r.json() or [])
    return rows, first


def fetch_character_corporation(character_id: int):
    """corporation_id eines Charakters - OEFFENTLICH, kein Token noetig.
    15 Minuten vorgehalten (Corp-Wechsel sind selten). None bei Fehler."""
    def _hole():
        r = _session.get(f"{config.ESI_BASE}/characters/{int(character_id)}/",
                         timeout=20)
        r.raise_for_status()
        return (r.json() or {}).get("corporation_id")
    try:
        return _ttl_geholt(("char_corp", int(character_id)), _hole)
    except Exception:
        return None


def fetch_corporation_name(corporation_id: int) -> str:
    """Name einer Corporation - oeffentlich; bei Fehler die Nummer."""
    def _hole():
        r = _session.get(
            f"{config.ESI_BASE}/corporations/{int(corporation_id)}/",
            timeout=20)
        r.raise_for_status()
        return (r.json() or {}).get("name") or str(corporation_id)
    try:
        return _ttl_geholt(("corp_name", int(corporation_id)), _hole)
    except Exception:
        return str(corporation_id)


def fetch_character_roles(client_id: str, character_id: int) -> set:
    """Die Corp-Rollen des Charakters (z.B. {"Director", "Factory_Manager"}).
    Braucht CORP_ROLES_SCOPE. Nur die ALLGEMEINEN Rollen - `roles_at_hq`
    usw. sind Standort-Einschraenkungen, die die Corp-Endpunkte nicht
    freischalten."""
    url = f"{config.ESI_BASE}/characters/{character_id}/roles/"
    r = _get_with_retry(url, headers=_auth_headers(client_id, character_id),
                        timeout=30)
    r.raise_for_status()
    return set((r.json() or {}).get("roles") or [])


def fetch_corporation_assets(client_id: str, character_id: int,
                             corporation_id: int) -> list:
    """ROHE Asset-Liste der Corp (alle Seiten). Rolle: Director.
    Das Datenalter wird unter der corporation_id gemerkt - so kann der
    virtuelle Bestand sie wie einen Charakter behandeln."""
    base = f"{config.ESI_BASE}/corporations/{int(corporation_id)}/assets/"
    rows, first = _get_alle_seiten(base, _auth_headers(client_id, character_id))
    _record_assets_meta(int(corporation_id), first)
    return rows


def fetch_corporation_divisions(client_id: str, character_id: int,
                                corporation_id: int) -> dict:
    """Rohe Antwort von /divisions/ ({"hangar": [...], "wallet": [...]}).
    Rolle: Director. Namen aufloesen macht corp.division_namen."""
    url = f"{config.ESI_BASE}/corporations/{int(corporation_id)}/divisions/"
    r = _get_with_retry(url, headers=_auth_headers(client_id, character_id),
                        timeout=30)
    r.raise_for_status()
    return r.json() or {}


def fetch_corporation_blueprints(client_id: str, character_id: int,
                                 corporation_id: int, divisions=None) -> list:
    """Corp-Blueprints in DERSELBEN Form wie fetch_blueprints - plus
    `location_flag` und `division`. Rolle: Director.

    Mit `divisions` nur die aus diesen Hangar-Divisions: eine Blaupause in
    einer nicht gewaehlten Division ist fuer den Bauplan so wenig da wie das
    Material dort."""
    from . import corp as _corp
    base = f"{config.ESI_BASE}/corporations/{int(corporation_id)}/blueprints/"
    rows, _ = _get_alle_seiten(base, _auth_headers(client_id, character_id))
    gewaehlt = (set(_corp.divisions_bereinigt(divisions))
                if divisions is not None else None)
    out = []
    for b in rows:
        div = _corp.division_von(b.get("location_flag"))
        if gewaehlt is not None and div not in gewaehlt:
            continue
        raw_qty = b.get("quantity", 1)
        runs = b.get("runs", -1)
        is_bpo = (runs == -1) or (raw_qty == -1)
        qty = raw_qty if raw_qty and raw_qty > 0 else 1
        out.append({
            "item_id": b.get("item_id"),
            "type_id": b.get("type_id"),
            "quantity": qty,
            "material_efficiency": b.get("material_efficiency", 0),
            "time_efficiency": b.get("time_efficiency", 0),
            "runs": runs,
            "is_bpo": is_bpo,
            "location_id": b.get("location_id"),
            "location_flag": b.get("location_flag"),
            "division": div,
            "corporation_id": int(corporation_id),
        })
    return out


def fetch_corporation_jobs(client_id: str, character_id: int,
                           corporation_id: int,
                           include_delivered: bool = False) -> list:
    """Industrie-Jobs der Corp in DERSELBEN Form wie fetch_active_jobs.
    Rolle: Factory_Manager. Paginiert (X-Pages)."""
    base = f"{config.ESI_BASE}/corporations/{int(corporation_id)}/industry/jobs/"
    rows, _ = _get_alle_seiten(
        base, _auth_headers(client_id, character_id),
        params={"include_completed": "true" if include_delivered else "false"})
    allowed = ("active", "paused", "ready") + \
        (("delivered",) if include_delivered else ())
    out = []
    for j in rows:
        st = j.get("status")
        if st and st not in allowed:
            continue
        out.append({
            "job_id": j.get("job_id"),
            "activity_id": j.get("activity_id"),
            "product_type_id": j.get("product_type_id"),
            "blueprint_type_id": j.get("blueprint_type_id"),
            "runs": j.get("runs"),
            "blueprint_id": j.get("blueprint_id"),
            "start_date": j.get("start_date"),
            "end_date": j.get("end_date"),
            "completed_date": j.get("completed_date"),
            "status": st,
            "corporation_id": int(corporation_id),
        })
    return out


def fetch_industry_jobs(client_id: str, character_id: int) -> dict:
    """Aktive Industry-Jobs des Charakters, gezählt nach Typ:
    {"manufacturing": n, "reaction": n, "science": n}. Für freie Slots
    (frei = max − belegt)."""
    url = f"{config.ESI_BASE}/characters/{character_id}/industry/jobs/"
    r = _get_with_retry(url, headers=_auth_headers(client_id, character_id),
                     params={"include_completed": "false"}, timeout=30)
    r.raise_for_status()
    out = {"manufacturing": 0, "reaction": 0, "science": 0}
    for j in r.json() or []:
        st = j.get("status")
        # "ready" (fertig, nicht abgeliefert) belegt in EVE WEITERHIN den Slot -
        # erst das Abliefern gibt ihn frei. Ohne ready zählte die Anzeige zu
        # viele freie Slots, solange fertige Jobs herumlagen.
        if st and st not in ("active", "paused", "ready"):
            continue
        act = j.get("activity_id")
        if act == 1:
            out["manufacturing"] += 1
        elif act in (9, 11):
            out["reaction"] += 1
        else:
            out["science"] += 1
    return out


def fetch_skills(client_id: str, character_id: int) -> dict:
    """Return {skill_id: level} using the current (active) level for each skill."""
    url = f"{config.ESI_BASE}/characters/{character_id}/skills/"
    r = _get_with_retry(url, headers=_auth_headers(client_id, character_id), timeout=30)
    r.raise_for_status()
    out = {}
    for s in r.json().get("skills", []):
        lvl = s.get("active_skill_level")
        if lvl is None:
            lvl = s.get("trained_skill_level", 0)
        out[s["skill_id"]] = lvl
    return out


def fetch_standings(client_id: str, character_id: int) -> list:
    """Return [{from_id, from_type, standing}] – the character's personal
    (unmodified) standings, which is exactly what the broker fee uses."""
    url = f"{config.ESI_BASE}/characters/{character_id}/standings/"
    r = _get_with_retry(url, headers=_auth_headers(client_id, character_id), timeout=30)
    r.raise_for_status()
    return r.json()


def resolve_entity_names(ids) -> dict:
    """Resolve any IDs (corp/faction/character/...) -> names via /universe/names/.
    Resilient to individual bad ids (one bad id won't blank the batch)."""
    ids = sorted(set(int(i) for i in ids if i))
    out = {}
    for i in range(0, len(ids), 1000):
        out.update(_resolve_names_chunk(ids[i:i + 1000]))
    return out


class RateLimited(Exception):
    """ESI returned 420 (error-rate limit) or 429 (too many requests)."""


def fetch_market_history(type_id: int, region: int = config.FORGE_REGION) -> list:
    url = f"{config.ESI_BASE}/markets/{region}/history/"
    # short timeout: a first hub scan fetches ~1700 of these, so one slow/stuck
    # request must fail fast instead of stalling the whole run for 20-40 s.
    # Uses the shared pooled session so connections are reused (keep-alive)
    # instead of a fresh TCP+TLS handshake per item.
    r = _session.get(url, params={"type_id": type_id}, timeout=8)
    if r.status_code in (420, 429):
        raise RateLimited()
    r.raise_for_status()
    return r.json()


def fetch_structure_orders(client_id: str, character_id: int, structure_id: int,
                           progress=None) -> dict:
    """Best buy/sell + on-book qty per type in a player structure.
    Needs scope esi-markets.structure_markets.v1 and market access for the char."""
    base = f"{config.ESI_BASE}/markets/structures/{structure_id}/"
    headers = _auth_headers(client_id, character_id)
    first = _get_with_retry(base, params={"page": 1}, headers=headers, timeout=40)
    first.raise_for_status()
    pages = int(first.headers.get("X-Pages", "1"))
    agg = {}

    def fold(orders):
        for o in orders:
            tid = o["type_id"]
            a = agg.setdefault(tid, {"sell_min": 0.0, "buy_max": 0.0,
                                     "sell_qty": 0, "buy_qty": 0,
                                     "sell_orders": 0, "buy_orders": 0})
            if o["is_buy_order"]:
                a["buy_orders"] += 1
                a["buy_qty"] += o["volume_remain"]
                a["buy_max"] = max(a["buy_max"], o["price"])
            else:
                a["sell_orders"] += 1
                a["sell_qty"] += o["volume_remain"]
                a["sell_min"] = o["price"] if a["sell_min"] == 0 else min(a["sell_min"], o["price"])

    fold(first.json())
    if progress:
        progress(1, pages)
    for p in range(2, pages + 1):
        r = _get_with_retry(base, params={"page": p}, headers=headers, timeout=40)
        r.raise_for_status()
        fold(r.json())
        if progress:
            progress(p, pages)
    return agg


def structure_has_market(client_id: str, character_id: int, structure_id: int):
    """Leichtgewichtiger Test, ob eine Upwell-Struktur einen Markt-Service hat.
    Nur Astrahus/Azbel/Raitaru/Athanor haben KEINEN Markt; Sotiyo/Keepstar/
    Fortizar/Tatara können einen haben (wenn das Modul verbaut ist). Statt den Typ
    zu raten, fragen wir den Markt-Endpunkt selbst -- der sagt die Wahrheit.

    Fragt nur Seite 1 ab (nicht das ganze Buch). Rückgabe:
      True  -> Markt vorhanden (HTTP 200)
      False -> definitiv kein Markt / kein Zugang (403/404)
      None  -> unbekannt (Netzwerk-/Auth-Fehler) -> Aufrufer sollte NICHT
               ausblenden, um echte Märkte nicht versehentlich zu verstecken."""
    base = f"{config.ESI_BASE}/markets/structures/{structure_id}/"
    try:
        headers = _auth_headers(client_id, character_id)
        r = _session.get(base, params={"page": 1}, headers=headers, timeout=20)
    except Exception:
        return None
    if r.status_code == 200:
        return True
    if r.status_code in (403, 404):
        # 403 = kein Markt-Service ODER kein Docking/Markt-Zugang;
        # 404 = Struktur/Markt existiert nicht. Beides -> nicht als Hub nutzbar.
        return False
    return None


def fetch_structure_orders_full(client_id: str, character_id: int, structure_id: int,
                                progress=None) -> dict:
    """Vollständige Order-Leitern je Item in einer Spielerstruktur (für Tiefen-Ansicht
    + Aggregat in einem). Rückgabe:
    {type_id: {'sell': [(p,q) aufsteigend], 'buy': [(p,q) absteigend],
               'sell_min','buy_max','sell_qty','buy_qty','sell_orders','buy_orders'}}."""
    base = f"{config.ESI_BASE}/markets/structures/{structure_id}/"
    headers = _auth_headers(client_id, character_id)
    first = _get_with_retry(base, params={"page": 1}, headers=headers, timeout=40)
    first.raise_for_status()
    pages = int(first.headers.get("X-Pages", "1"))
    book = {}

    def fold(orders):
        for o in orders:
            b = book.setdefault(o["type_id"], {"sell": [], "buy": []})
            (b["buy"] if o["is_buy_order"] else b["sell"]).append(
                (o["price"], o["volume_remain"]))

    fold(first.json())
    if progress:
        progress(1, pages)
    for p in range(2, pages + 1):
        r = _get_with_retry(base, params={"page": p}, headers=headers, timeout=40)
        r.raise_for_status()
        fold(r.json())
        if progress:
            progress(p, pages)
    for _tid, b in book.items():
        b["sell"].sort(key=lambda x: x[0])
        b["buy"].sort(key=lambda x: x[0], reverse=True)
        b["sell_min"] = b["sell"][0][0] if b["sell"] else 0.0
        b["buy_max"] = b["buy"][0][0] if b["buy"] else 0.0
        b["sell_qty"] = sum(q for _p, q in b["sell"])
        b["buy_qty"] = sum(q for _p, q in b["buy"])
        b["sell_orders"] = len(b["sell"])
        b["buy_orders"] = len(b["buy"])
    return book


def region_of_system(system_id: int) -> int:
    """Sonnensystem → Region-ID (öffentliches ESI, keine Auth). Für Struktur-Region."""
    s = _session.get(f"{config.ESI_BASE}/universe/systems/{system_id}/", timeout=20)
    s.raise_for_status()
    const_id = s.json().get("constellation_id")
    c = _session.get(f"{config.ESI_BASE}/universe/constellations/{const_id}/", timeout=20)
    c.raise_for_status()
    return c.json().get("region_id")


def fetch_region_ids() -> list:
    """Alle Regions-IDs von New Eden (fuer den Contract-Scan ueber GANZ
    New Eden statt nur den Hub - Nutzer: "den Durchschnitts-Contract-Preis
    von ganz New Eden"). OHNE Auth, aendert sich praktisch nie.
    Wurmloch- (11000000+) und Abyssal-Regionen (12000000+) fliegen raus:
    dort gibt es keine oeffentlichen Contracts, sie kosten nur Abrufe."""
    r = _get_with_retry(f"{config.ESI_BASE}/universe/regions/", timeout=30)
    r.raise_for_status()
    return sorted(int(x) for x in (r.json() or []) if int(x) < 11000000)


def fetch_public_contracts(region_id: int, min_price: float = 0, min_volume: float = 0,
                           should_cancel=None, progress=None) -> list:
    """Alle öffentlichen "Item Exchange"-Contracts einer Region, grob nach Preis/
    Volumen vorgefiltert. WICHTIG: die Contract-Liste selbst verrät NICHT, welches
    Item drin ist (nur price/volume/type) - der teure Schritt ist, für jeden
    einzelnen Contract die Items separat abzurufen (siehe fetch_contract_items).
    Bei 20.000+ Contracts in Jita/Forge ist das für ALLE unmöglich (>50 Min. laut
    Community-Erfahrung) - deshalb HIER schon grob filtern (Capitals sind riesig
    UND teuer), damit nur noch eine Handvoll Kandidaten übrig bleibt, für die sich
    der Item-Abruf lohnt."""
    url = f"{config.ESI_BASE}/contracts/public/{region_id}/"
    out = []
    page = 1
    while True:
        if should_cancel and should_cancel():
            break
        r = _get_with_retry(url, params={"page": page}, timeout=30)
        data = r.json() or []
        for ct in data:
            if ct.get("type") != "item_exchange":
                continue
            price = ct.get("price") or 0
            vol = ct.get("volume") or 0
            if price < min_price or vol < min_volume:
                continue
            out.append(ct)
        pages = int(r.headers.get("X-Pages", "1"))
        if progress:
            progress(page, pages)
        if page >= pages:
            break
        page += 1
    return out


def fetch_contract_items(contract_id: int) -> list:
    """Items in einem öffentlichen Contract: [{type_id, quantity, is_included, ...}]."""
    url = f"{config.ESI_BASE}/contracts/public/items/{contract_id}/"
    r = _get_with_retry(url, timeout=20)
    return r.json() or []


def resolve_structure(client_id: str, character_id: int, structure_id: int) -> dict:
    """Name + solar system of a player structure (needs esi-universe.read_structures.v1)."""
    url = f"{config.ESI_BASE}/universe/structures/{structure_id}/"
    r = _get_with_retry(url, headers=_auth_headers(client_id, character_id), timeout=30)
    r.raise_for_status()
    return r.json()  # {name, solar_system_id, type_id, ...}


def resolve_station(station_id: int) -> dict:
    """Name + Sonnensystem einer NPC-STATION.

    Gegenstueck zu resolve_structure - aber OEFFENTLICH: /universe/stations/
    braucht weder Anmeldung noch Andockrecht. Genau deshalb gibt es die
    Funktion: der Struktur-Endpunkt kennt nur Upwell-Bauten und antwortet auf
    eine Stations-ID mit einem Fehler. Ein Discord-Nutzer baut in einer
    NPC-Station und fand dort folglich nichts (Sitzung 19).
    """
    url = f"{config.ESI_BASE}/universe/stations/{station_id}/"
    r = _get_with_retry(url, headers={"User-Agent": _USER_AGENT}, timeout=30)
    r.raise_for_status()
    return r.json()   # {name, system_id, type_id, owner, ...}


# NPC-Stationen liegen in diesem ID-Bereich. Upwell-Strukturen fangen erst
# bei einer Billion an, Container und Schiffe ebenso - die koennen also nicht
# versehentlich als Station durchgehen. Als eigene Konstanten, damit ein
# Waechter die Grenzen pruefen kann statt der Zahlen im Schleifenrumpf.
NPC_STATION_MIN = 60_000_000
NPC_STATION_MAX = 64_000_000


def is_npc_station(location_id) -> bool:
    """True, wenn diese Orts-ID eine NPC-Station ist. REIN - pruefbar ohne
    Netz."""
    try:
        lid = int(location_id)
    except (TypeError, ValueError):
        return False
    return NPC_STATION_MIN <= lid < NPC_STATION_MAX


def station_location_ids(client_id: str, character_id: int) -> set:
    """NPC-Stations-IDs, an denen der Charakter Orders oder Assets hat.

    Pendant zu structure_location_ids, nur fuer den anderen Zahlenbereich:
    NPC-Stationen liegen bei 60 000 000 bis 64 000 000, Upwell-Strukturen ab
    1 000 000 000 000. Container und Schiffe haben ebenfalls riesige IDs und
    fallen deshalb nur in den Struktur-Zweig, nie hierher.

    KOSTEN: das ist ein ZWEITER voller Assets-Durchlauf. Bewusst in Kauf
    genommen, statt beide Funktionen zu einer zusammenzulegen - die
    bestehende wird von einem Waechter (b70) einzeln ersetzt, und ein
    gemeinsamer Rueckgabewert haette diese Pruefung still entwertet. Der
    Aufruf passiert nur beim Knopf "Find locations and link all", der ohnehin
    mit Fortschrittsanzeige laeuft.
    """
    out = set()

    def _nimm(lid):
        if is_npc_station(lid):
            out.add(int(lid))

    try:
        for o in fetch_character_orders(client_id, character_id):
            _nimm(o.get("location_id"))
    except Exception:
        pass
    try:
        base = f"{config.ESI_BASE}/characters/{character_id}/assets/"
        headers = _auth_headers(client_id, character_id)
        first = _get_with_retry(base, params={"page": 1}, headers=headers, timeout=30)
        first.raise_for_status()
        pages = int(first.headers.get("X-Pages", "1"))
        assets = list(first.json())
        for p in range(2, pages + 1):
            r = _get_with_retry(base, params={"page": p}, headers=headers, timeout=30)
            r.raise_for_status()
            assets.extend(r.json())
        for a in assets:
            _nimm(a.get("location_id"))
    except Exception:
        pass
    return out


def fetch_type_orders(type_id: int, station: int = config.JITA_STATION,
                      region: int = config.FORGE_REGION) -> dict:
    """Full order ladder for one item at a station.
    Returns {'sell': [(price, qty) ascending], 'buy': [(price, qty) descending]}."""
    url = f"{config.ESI_BASE}/markets/{region}/orders/"
    sell, buy = [], []
    page = 1
    while True:
        r = _get_with_retry(url, params={"type_id": type_id, "order_type": "all",
                                         "page": page}, timeout=30)
        r.raise_for_status()
        data = r.json()
        for o in data:
            if o["location_id"] != station:
                continue
            (buy if o["is_buy_order"] else sell).append((o["price"], o["volume_remain"]))
        pages = int(r.headers.get("X-Pages", "1"))
        if page >= pages:
            break
        page += 1
    sell.sort(key=lambda x: x[0])
    buy.sort(key=lambda x: x[0], reverse=True)
    return {"sell": sell, "buy": buy}


def resolve_corp_id(name: str):
    """Corporation-NAME -> ID ueber /universe/ids/ (kein Login noetig).

    Bewusst zur LAUFZEIT statt fest eingetragener Zahl: eine hartkodierte
    ID waere still falsch, wenn die Corp umbenannt/neu gegruendet wird -
    der Name ist das, was der Nutzer kennt und pruefen kann.
    Rueckgabe: int oder None (kein Treffer / kein Netz)."""
    if not name:
        return None
    try:
        r = _session.post(f"{config.ESI_BASE}/universe/ids/",
                          params={"datasource": "tranquility"},
                          json=[name], timeout=20)
        if r.status_code != 200:
            return None
        for eintrag in (r.json() or {}).get("corporations") or []:
            # exakter Name zuerst - ESI liefert auch Teiltreffer
            if (eintrag.get("name") or "").strip().lower() == name.strip().lower():
                return int(eintrag["id"])
    except Exception:
        return None
    return None


# Sitzung 17: beide Fenster-Funktionen melden dasselbe - EINE Quelle, englisch
# als Schluessel, uebersetzt beim Ausloesen (die Sprache steht dann fest).
_ESI_403_TEXT = ("403 \u2013 permission missing. Link the character again with "
                 "\u201eOpen in game\u201c enabled (scope esi-ui.open_window.v1).")
_ESI_NICHT_EINGELOGGT = ("{code} \u2013 the character is not logged into the game "
                         "(or another character is active). {body}")

def open_info_window(client_id: str, character_id: int, target_id: int):
    """Oeffnet ingame das Info-Fenster einer ID (Corporation, Charakter,
    Station, Item ...) - derselbe Weg wie open_market_window, nur der
    andere Endpunkt: /ui/openwindow/information/.

    Gebraucht fuer den Spenden-Knopf (Nutzer, Sitzung 8: "was muessen wir
    machen, damit ingame wirklich mein Corp-Info-Fenster aufgeht?").
    Voraussetzungen wie beim Markt-Fenster: Scope esi-ui.open_window.v1 und
    der Charakter muss im Spiel eingeloggt sein."""
    url = f"{config.ESI_BASE}/ui/openwindow/information/"
    r = _session.post(url,
                      params={"target_id": target_id,
                              "datasource": "tranquility"},
                      headers=_auth_headers(client_id, character_id),
                      timeout=20)
    if r.status_code in (200, 204):
        return {"ok": True, "status": r.status_code,
                "character_id": character_id}
    body = ""
    try:
        body = r.json().get("error", "")
    except Exception:
        body = (r.text or "")[:160]
    from .sprache import t as _txt
    if r.status_code == 403:
        raise RuntimeError(_txt(_ESI_403_TEXT))
    if r.status_code in (500, 520):
        raise RuntimeError(_txt(_ESI_NICHT_EINGELOGGT).format(code=r.status_code, body=body))
    raise RuntimeError(f"HTTP {r.status_code} \u2013 {body}")


def open_market_window(client_id: str, character_id: int, type_id: int):
    """Open the in-game market window (needs esi-ui.open_window.v1; the character
    must be logged into the game client – any PC, CCP routes it there).
    Returns the HTTP status code on success so the UI can show a clear result."""
    url = f"{config.ESI_BASE}/ui/openwindow/marketdetails/"
    r = _session.post(url, params={"type_id": type_id, "datasource": "tranquility"},
                      headers=_auth_headers(client_id, character_id), timeout=20)
    if r.status_code in (200, 204):
        return {"ok": True, "status": r.status_code, "character_id": character_id}
    # surface a clear reason instead of a generic failure
    body = ""
    try:
        body = r.json().get("error", "")
    except Exception:
        body = (r.text or "")[:160]
    from .sprache import t as _txt
    if r.status_code == 403:
        raise RuntimeError(_txt(_ESI_403_TEXT))
    if r.status_code in (500, 520):
        raise RuntimeError(_txt(_ESI_NICHT_EINGELOGGT).format(code=r.status_code, body=body))
    raise RuntimeError(f"HTTP {r.status_code} – {body}")


def assets_at_locations(client_id: str, character_id: int,
                        location_ids, diag_out=None) -> dict:
    """{type_id: qty} für die Items des Charakters an MEHREREN Stationen/
    Strukturen auf einmal (inkl. verschachtelter Container-Inhalte). Ein
    einziger Assets-Durchlauf pro Charakter statt einem pro Struktur - für
    den Bestand-Pool des Runplaners (mehrere Bau-Charaktere x mehrere
    verknüpfte Strukturen) macht das den Unterschied zwischen N und N x M
    vollen ESI-Paginierungen. Braucht den Assets-Scope."""
    base = f"{config.ESI_BASE}/characters/{character_id}/assets/"
    headers = _auth_headers(client_id, character_id)
    first = _get_with_retry(base, params={"page": 1}, headers=headers, timeout=30)
    first.raise_for_status()
    _record_assets_meta(character_id, first)
    pages = int(first.headers.get("X-Pages", "1"))
    assets = list(first.json())
    for p in range(2, pages + 1):
        r = _get_with_retry(base, params={"page": p}, headers=headers, timeout=30)
        r.raise_for_status()
        assets.extend(r.json())
    out, seen, _per_loc = bestand_an_orten(assets, location_ids,
                                           container_type_ids_safe())
    if diag_out is not None:
        # MESSUNG statt Vermutung (Aufgabe "Bestand erreicht den Bauplan
        # nicht"): unterscheidet "Charakter hat GAR keine Assets" (Abruf/
        # Scope-Problem) von "Assets existieren, aber KEINE haengt an diesen
        # location_ids" (falsche/fehlende Verknuepfung, Corp-Hangar, anderer
        # Ort). Erst diese Zahlen machen die Ursache benennbar.
        diag_out["rows_total"] = len(assets)
        diag_out["rows_at_loc"] = len(seen)
        diag_out["per_loc"] = _per_loc
    return out


def assets_at_location(client_id: str, character_id: int, location_id: int) -> dict:
    """{type_id: qty} for the character's items sitting AT the given station/structure,
    including the (nested) contents of containers there. Needs the assets scope."""
    return assets_at_locations(client_id, character_id, [location_id])


# SERVERWEITE LISTEN KURZ VORHALTEN (Nutzer, Sitzung 20: "koennen wir das
# Laden der Bauplaene beim Oeffnen beschleunigen?").
# GEMESSEN, wo die Zeit steckt: die Rechnung nicht (build_tree 1 ms,
# production_plan 1 ms). Es sind die beiden grossen Abrufe, die bei JEDEM
# Oeffnen eines Bauplans neu liefen:
#   /industry/systems/  ~8'000 Systeme
#   /markets/prices/    ~13'000 Preise
# Beides ist SERVERWEIT und bei CCP selbst eine Stunde gecacht - zweimal
# hintereinander abzurufen liefert garantiert dasselbe. 15 Minuten liegen
# sicher darunter und halten die Zahlen trotzdem frisch.
# NICHT auf Platte: bei einem Neustart lieber einmal frisch holen, als mit
# einem alten Stand zu rechnen, dessen Alter niemand sieht.
_TTL_CACHE: dict = {}
_TTL_SEKUNDEN = 900


def cache_leeren() -> None:
    """Vorgehaltene Listen verwerfen - fuer "Alles aktualisieren"."""
    _TTL_CACHE.clear()


def _ttl_geholt(schluessel, hole):
    import time as _t
    _e = _TTL_CACHE.get(schluessel)
    if _e and (_t.time() - _e[0]) < _TTL_SEKUNDEN:
        return _e[1]
    _wert = hole()
    _TTL_CACHE[schluessel] = (_t.time(), _wert)
    return _wert


def system_cost_indices() -> dict:
    """{solar_system_id: {activity: cost_index}} from public ESI /industry/systems/.
    Activities include 'manufacturing', 'reaction', 'invention', 'copying', ...

    Bis zu 15 Minuten vorgehalten - s. _TTL_CACHE oben.
    """
    return _ttl_geholt("system_cost_indices", _system_cost_indices_frisch)


def _system_cost_indices_frisch() -> dict:
    out = {}
    r = _session.get(f"{config.ESI_BASE}/industry/systems/", timeout=40)
    r.raise_for_status()
    for s in r.json():
        sid = s.get("solar_system_id")
        idx = {ci.get("activity"): ci.get("cost_index", 0.0)
               for ci in s.get("cost_indices", [])}
        if sid:
            out[int(sid)] = idx
    return out


def all_system_names() -> dict:
    """{solar_system_id: name} for every solar system (public ESI). Used for the
    build-system search box. Does not touch the type-name cache."""
    out = {}
    r = _session.get(f"{config.ESI_BASE}/universe/systems/", timeout=60)
    r.raise_for_status()
    ids = r.json()
    for i in range(0, len(ids), 1000):
        chunk = ids[i:i + 1000]
        try:
            rr = _session.post(f"{config.ESI_BASE}/universe/names/",
                               json=chunk, timeout=40)
            if rr.status_code != 200:
                continue
            for e in rr.json():
                if e.get("category") == "solar_system":
                    out[int(e["id"])] = e["name"]
        except Exception:
            continue
    return out


def system_info(system_id: int) -> dict:
    """{name, security} for one solar system (public ESI)."""
    r = _session.get(f"{config.ESI_BASE}/universe/systems/{int(system_id)}/", timeout=20)
    r.raise_for_status()
    d = r.json()
    # STATIONEN GLEICH MITNEHMEN (Sitzung 19): dieselbe Antwort enthaelt die
    # NPC-Stationen des Systems ohnehin - sie wegzuwerfen und spaeter erneut
    # zu fragen waere ein zweiter Abruf fuer Daten, die schon da sind. Der
    # Struktur-Dialog fuellt daraus die Stationsauswahl, damit niemand eine
    # ID abtippen oder einen Ingame-Link kopieren muss.
    return {"name": d.get("name", str(system_id)),
            "security": float(d.get("security_status", 1.0)),
            "stations": [int(x) for x in (d.get("stations") or [])]}


def market_prices() -> dict:
    """Beide CCP-Preise aus /markets/prices/ in EINEM Abruf.

    Rueckgabe: {"adjusted": {type_id: float}, "average": {type_id: float}}

    WARUM BEIDE (Nutzer, Sitzung 14): "wenn gerade nichts davon im Markt ist
    von einem Item, kann man dann nicht einen durchschnitsspreis des Items
    nehmen? man sieht ja dann spaeter wenn man in Jita ist, dass das Material
    gar nicht da ist." Genau dafuer ist `average_price` da - der Endpunkt
    liefert ihn ohnehin mit, das Tool hat ihn bisher weggeworfen und nur
    `adjusted_price` gelesen.

    ACHTUNG BEI DER VERWENDUNG: `average_price` ist ein SERVERWEITER
    Durchschnitt ueber alle Regionen, kein Hub-Preis. Er taugt als Rueckfall,
    wenn weder Orderbuch noch Hub-Preis vorliegen - aber eine damit
    gerechnete Summe darf nicht aussehen wie eine orderbuch-genaue.

    Bis zu 15 Minuten vorgehalten - s. _TTL_CACHE oben.
    """
    return _ttl_geholt("market_prices", _market_prices_frisch)


def _market_prices_frisch() -> dict:
    adj, avg = {}, {}
    r = _session.get(f"{config.ESI_BASE}/markets/prices/", timeout=60)
    r.raise_for_status()
    for e in r.json():
        try:
            _tid = int(e["type_id"])
        except (KeyError, TypeError, ValueError):
            continue
        ap = e.get("adjusted_price")
        if ap is not None:
            adj[_tid] = float(ap)
        av = e.get("average_price")
        if av is not None:
            avg[_tid] = float(av)
    return {"adjusted": adj, "average": avg}


def adjusted_prices() -> dict:
    """{type_id: adjusted_price} from public ESI /markets/prices/. This is the basis
    for the Estimated Item Value (EIV) used in industry job-cost calculation.

    Duenner Aufsatz auf `market_prices()` - EINE Abrufstelle fuer beide
    Preisarten, damit die zwei nicht auseinanderlaufen koennen.
    """
    return market_prices()["adjusted"]


def average_prices() -> dict:
    """{type_id: average_price} - serverweiter CCP-Durchschnitt.

    RUECKFALL-PREIS fuer Material, das gerade nirgends im Orderbuch steht.
    Ohne ihn fiel so ein Material still auf 0 ISK und machte den Bauplan
    doppelt so guenstig, wie er ist (Nutzer-Befund Sitzung 14).
    """
    return market_prices()["average"]


def structure_location_ids(client_id: str, character_id: int) -> set:
    """Structure IDs (>= 1e12) where the character has open orders or assets.
    Used to offer the player their own build structures as a dropdown."""
    out = set()
    try:
        for o in fetch_character_orders(client_id, character_id):
            lid = o.get("location_id")
            if lid and int(lid) >= 1_000_000_000_000:
                out.add(int(lid))
    except Exception:
        pass
    try:
        base = f"{config.ESI_BASE}/characters/{character_id}/assets/"
        headers = _auth_headers(client_id, character_id)
        first = _get_with_retry(base, params={"page": 1}, headers=headers, timeout=30)
        first.raise_for_status()
        pages = int(first.headers.get("X-Pages", "1"))
        assets = list(first.json())
        for p in range(2, pages + 1):
            r = _get_with_retry(base, params={"page": p}, headers=headers, timeout=30)
            r.raise_for_status()
            assets.extend(r.json())
        for a in assets:
            lid = a.get("location_id")
            if lid and int(lid) >= 1_000_000_000_000:
                out.add(int(lid))
    except Exception:
        pass
    return out


def eve_server_version():
    """Aktuelle EVE-Server-Build-Nummer (aus dem öffentlichen /status/-Endpoint).
    Ändert sich bei JEDEM EVE-Update/Patch (auch Balance-Änderungen). Gibt die
    server_version als String zurück oder None, wenn nicht erreichbar."""
    try:
        url = f"{config.ESI_BASE}/status/"
        r = _session.get(url, params={"datasource": "tranquility"}, timeout=15)
        r.raise_for_status()
        data = r.json() or {}
        v = data.get("server_version")
        return str(v) if v is not None else None
    except Exception:
        return None


def sde_last_modified():
    """Datum, wann die SDE bei Fuzzwork zuletzt aktualisiert wurde (Last-Modified-
    Header des SQLite-Dumps, ohne die 140-MB-Datei zu laden – nur ein HEAD-Request).
    Gibt den Header-String zurück oder None."""
    try:
        from . import industry
        url = getattr(industry, "_SQLITE_URL",
                      "https://www.fuzzwork.co.uk/dump/latest-sqlite.db.gz")
        r = _session.head(url, timeout=15, allow_redirects=True)
        return r.headers.get("Last-Modified")
    except Exception:
        return None
