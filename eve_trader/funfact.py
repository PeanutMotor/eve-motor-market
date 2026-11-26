"""Funfact - was ein Nutzer mit Eve MoMa gebaut und gehandelt hat (1.1.5).

NUTZER-IDEE (16.10.2026, Discord-Post "Funfact: I just buildet ~5500 Items
and made about 2400 trades in Jita with MoMa"): dasselbe in der App, hinter
einem Knopf "Funfact" in der linken Leiste, mit "Copy for Discord".

VORGABEN DES NUTZERS (emm569, alle am 16.10.2026):
* GEZAEHLT WIRD NUR FERTIGES - ein Plan, der von Hand "Done" bekam, oder
  den der ESI-Fertig-Check als vollstaendig gebaut meldet. Geplantes zaehlt
  nicht.
* MOMA SPEICHERT DIE STATISTIK SELBST (`settings["funfact"]`). Ein Plan
  wird beim Abschliessen eingetragen und bleibt drin, auch wenn er spaeter
  geloescht oder archiviert wird - sonst schrumpfte die Zahl mit jedem
  Aufraeumen. Nur "Reopen" nimmt einen von Hand abgeschlossenen Plan wieder
  heraus.
* KACHELN aus den SDE-Kategorien der ENDPRODUKTE, leere ausgeblendet. Nur
  Endprodukte: ein Buendel zaehlt jedes seiner Enden, Zwischenprodukte nie
  (sonst zaehlte jedes Schiff seine Bauteile mit).
* DAY- ODER SWINGTRADE ueber die EIGENEN ORDERS statt ueber die
  Haltedauer: lief der Kauf ueber die eigene Buy-Order, ist es ein
  Daytrade (Order-Flip), wurde aus fremden Sell-Orders gekauft, ein Swing.
  ESI-Transaktionen sagen das nicht - die Order-Historie schon. Sie wird
  seit 1.1.5 dauerhaft gespeichert (store.order_history). Fuer Kaeufe vor
  ihrer Reichweite bleibt nur die Haltedauer (< 24 h = Daytrade) - das ist
  eine SCHAETZUNG und wird als solche gezaehlt und angezeigt.

Dieses Modul ist REIN (kein Qt, kein ESI, keine Datei) - die Oberflaeche
und der Speicher reichen die Daten herein. So rechnen die Pruefungen
dieselben Funktionen nach, die das Fenster zeigt.
"""
from datetime import datetime, timedelta

# Reihenfolge der Kacheln = Reihenfolge im Fenster und im Discord-Text.
KACHELN = ("ships", "modules", "rigs", "ammo", "drones", "fighters",
           "implants", "subsystems", "structures", "deployables", "other")

# Englische Anzeige-Schluessel (die Oberflaeche uebersetzt mit t()).
KACHEL_NAMEN = {
    "ships": "Ships", "modules": "Modules", "rigs": "Rigs",
    "ammo": "Ammo & Charges", "drones": "Drones", "fighters": "Fighters",
    "implants": "Implants & Boosters", "subsystems": "Subsystems",
    "structures": "Structures", "deployables": "Deployables",
    "other": "Other",
}

# SDE-Kategorien (gemessen in industry.db, Endprodukte der Fertigung).
_KAT = {6: "ships", 8: "ammo", 18: "drones", 87: "fighters", 20: "implants",
        32: "subsystems", 22: "deployables",
        65: "structures", 66: "structures", 23: "structures",
        39: "structures", 40: "structures", 46: "structures"}

# Ab wann gilt ein Kauf als "aus der Order-Historie bekannt"? ESI liefert
# die Historie geschlossener Orders rund 90 Tage zurueck (UNGEPRUEFT, s.
# Kopf). Was davor gekauft wurde, ist unbekannt -> Schaetzung.
ORDER_HISTORIE_TAGE = 90
DAYTRADE_GRENZE_H = 24.0


def kachel(category_id, group_name):
    """Kachel-Schluessel eines Endprodukts. Rigs sind in der SDE Module
    (Kategorie 7) mit Gruppen "Rig ..." - eigene Kachel (Nutzer)."""
    try:
        c = int(category_id) if category_id is not None else None
    except (TypeError, ValueError):
        c = None
    if c == 7:
        return "rigs" if str(group_name or "").startswith("Rig ") else "modules"
    return _KAT.get(c, "other")


def plan_enden(plan):
    """[(type_id, Stueck)] der ENDPRODUKTE eines Plans - beim Buendel jedes
    Ende, sonst das eine Produkt. Kaputte Eintraege fallen weg."""
    p = plan or {}
    roh = (p.get("enden") or []) if p.get("multi") else [
        (p.get("type_id"), p.get("qty"))]
    # GEKAUFTE ENDEN SIND NICHT GEBAUT (emm951): ein Buendel merkt sich beim
    # Speichern, welche Enden es kauft (`enden_gekauft`) - die zaehlen nicht
    # in "built". Alte Plaene tragen das Feld nicht und zaehlen wie bisher.
    gek = set()
    if p.get("multi"):
        for g in (p.get("enden_gekauft") or []):
            try:
                gek.add(int(g))
            except (TypeError, ValueError):
                pass
    out = []
    for e in roh:
        try:
            t, q = int(e[0]), int(e[1])
        except (TypeError, ValueError, IndexError):
            continue
        if t > 0 and q > 0 and t not in gek:
            out.append((t, q))
    return out


def leer():
    return {"seit": None, "plaene": {}}


def _stand(stand):
    if not isinstance(stand, dict):
        stand = leer()
    stand.setdefault("seit", None)
    if not isinstance(stand.get("plaene"), dict):
        stand["plaene"] = {}
    return stand


def buendel_quellen(plaene):
    """str(plan_id) aller Einzelplaene, die in IRGENDEINEM Buendel stecken
    (auch einem abgeschlossenen). Sie zaehlen nie selbst - ihr Endprodukt
    zaehlt das Buendel, sonst stuende dasselbe Schiff zweimal da."""
    out = set()
    for p in (plaene or []):
        p = p or {}
        try:
            ist_b = bool(p.get("multi")) or int(p.get("type_id") or 0) == -1
        except (TypeError, ValueError):
            ist_b = bool(p.get("multi"))
        if ist_b:
            out.update(str(q) for q in (p.get("quellen") or []))
    return out


def erfassen(stand, plan, quelle, jetzt, mitglieder=()):
    """Einen FERTIGEN Plan eintragen. `quelle`: "done" (von Hand), "esi"
    (ESI-Fertig-Check) oder "import" (beim ersten Start schon fertig).
    Ein Mitglied, das ueber sein Buendel fertig wurde, zaehlt NICHT selbst -
    das Buendel zaehlt seine Enden. Rueckgabe: True, wenn sich etwas
    geaendert hat (schon eingetragene Plaene bleiben, wie sie sind)."""
    stand = _stand(stand)
    p = plan or {}
    if p.get("done_durch_buendel"):
        return False
    pid = str(p.get("id"))
    if pid in set(mitglieder or ()):
        return False
    if not p.get("id") or pid in stand["plaene"]:
        return False
    enden = plan_enden(p)
    if not enden:
        return False
    stand["plaene"][pid] = {"enden": [[t, q] for t, q in enden],
                            "ts": float(jetzt), "quelle": str(quelle),
                            "name": str(p.get("label") or p.get("item_name") or "")}
    if stand.get("seit") is None or float(jetzt) < float(stand["seit"]):
        stand["seit"] = float(jetzt)
    return True


def entfernen(stand, plan_id):
    """"Reopen": ein von Hand (oder beim Import) abgeschlossener Plan geht
    wieder heraus. Ein per ESI fertig gemeldeter bleibt - ESI hat die Stueck
    wirklich gebaut gesehen. Rueckgabe: True, wenn entfernt."""
    stand = _stand(stand)
    e = stand["plaene"].get(str(plan_id))
    if e is None or e.get("quelle") == "esi":
        return False
    del stand["plaene"][str(plan_id)]
    return True


def nachtragen(stand, plaene, jetzt):
    """Erster Start mit 1.1.5: was heute schon fertig ist (gespeicherte UND
    archivierte Plaene), wird EINMAL uebernommen. Zeitpunkt ist der echte
    `done_ts` des Plans, wenn er einen hat - sonst jetzt."""
    stand = _stand(stand)
    mit = buendel_quellen(plaene)
    n = 0
    for p in (plaene or []):
        if not (p or {}).get("done_manual"):
            continue
        try:
            ts = float(p.get("done_ts") or jetzt)
        except (TypeError, ValueError):
            ts = float(jetzt)
        if erfassen(stand, p, "import", ts, mit):
            n += 1
    return n


def gebaut(stand, kat_map, gruppen):
    """{kachel: Stueck} - nur Kacheln mit mindestens einem Stueck, in der
    Reihenfolge von KACHELN. `kat_map` = industry.item_category_map()
    (type_id -> (category_id, group_id, meta)), `gruppen` = type_id ->
    Gruppenname."""
    summe = {}
    for e in (_stand(stand)["plaene"] or {}).values():
        for t, q in (e.get("enden") or []):
            try:
                t, q = int(t), int(q)
            except (TypeError, ValueError):
                continue
            info = (kat_map or {}).get(t)
            k = kachel(info[0] if info else None, (gruppen or {}).get(t, ""))
            summe[k] = summe.get(k, 0) + q
    return {k: summe[k] for k in KACHELN if summe.get(k)}


def gewinn_offen(stand):
    """Plan-Ids der Statistik, denen noch kein Bau-Gewinn gemerkt ist
    (emm573) - Import, ESI-Weg oder ein Plan ohne Schaetzung beim Abschluss."""
    stand = _stand(stand)
    return [pid for pid, e in stand["plaene"].items()
            if not isinstance(e, dict) or e.get("gewinn") is None]


def gewinn_setzen(stand, werte):
    """Bau-Gewinne {pid: ISK} eintragen - NUR wo noch keiner steht: der
    einmal gemerkte Wert bleibt (er gehoert zum Abschluss, nicht zu den
    Preisen von heute). Rueckgabe: True, wenn sich etwas geaendert hat."""
    stand = _stand(stand)
    neu = False
    for pid, g in (werte or {}).items():
        e = stand["plaene"].get(str(pid))
        if not isinstance(e, dict) or e.get("gewinn") is not None:
            continue
        try:
            e["gewinn"] = float(g)
        except (TypeError, ValueError):
            continue
        neu = True
    return neu


def bau_gewinn(stand):
    """(Summe, Plaene mit Gewinn, Plaene ohne) ueber die Statistik."""
    stand = _stand(stand)
    summe, mit, ohne = 0.0, 0, 0
    for e in stand["plaene"].values():
        g = e.get("gewinn") if isinstance(e, dict) else None
        if g is None:
            ohne += 1
            continue
        try:
            summe += float(g)
            mit += 1
        except (TypeError, ValueError):
            ohne += 1
    return summe, mit, ohne


def _zeit(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).replace(tzinfo=None)
    except (TypeError, ValueError):
        return None


def kauf_herkunft(txs, orders, abdeckung_ab=None):
    """Lief ein KAUF ueber die eigene Buy-Order? {(transaction_id,
    character_id): True | False | None}.

    True  = es gab eine eigene Buy-Order fuer dasselbe Item zum selben
            Preis, die zu dem Zeitpunkt offen sein konnte
            (issued <= Kauf <= issued + duration + 1 Tag Spielraum).
    False = der Kauf liegt in der Reichweite der gespeicherten Orders
            (`abdeckung_ab[character_id]`, ISO-Datum), aber keine passt ->
            aus fremden Sell-Orders gekauft.
    None  = vor der Reichweite - unbekannt.

    OHNE ORT: eine Buy-Order mit Reichweite (Region, Spruenge) wird an der
    Station des VERKAEUFERS bedient - die Transaktion traegt dann einen
    anderen Ort als die Order.

    GRENZE (ehrlich): eine Order, deren Preis spaeter geaendert wurde,
    kennt ESI nur mit dem LETZTEN Preis. Fuellungen zum frueheren Preis
    finden dann keine passende Order und gelten als Marktkauf."""
    je = {}
    for o in (orders or []):
        if not o.get("is_buy_order") and not o.get("is_buy"):
            continue
        try:
            key = (int(o["character_id"]), int(o["type_id"]))
        except (KeyError, TypeError, ValueError):
            continue
        ab = _zeit(o.get("issued"))
        if ab is None:
            continue
        bis = ab + timedelta(days=int(o.get("duration") or 90) + 1)
        je.setdefault(key, []).append((float(o.get("price") or 0.0), ab, bis))
    out = {}
    for t in (txs or []):
        if not t.get("is_buy"):
            continue
        try:
            cid = int(t["character_id"])
            key = (cid, int(t["type_id"]))
        except (KeyError, TypeError, ValueError):
            continue
        z = _zeit(t.get("date"))
        if z is None:
            continue
        preis = float(t.get("unit_price") or 0.0)
        treffer = any(abs(preis - p) < 0.005 and ab <= z <= bis
                      for p, ab, bis in je.get(key, ()))
        if treffer:
            out[(t.get("transaction_id"), cid)] = True
            continue
        grenze = _zeit((abdeckung_ab or {}).get(cid)) if abdeckung_ab else None
        out[(t.get("transaction_id"), cid)] = (
            False if (grenze is not None and z >= grenze) else None)
    return out


def trades_einteilen(events):
    """Daytrades / Swingtrades aus den Verkaufs-Ereignissen von
    `market.realized_trades(..., herkunft=...)`. Je Verkauf zaehlt die
    Mehrheit der verkauften Stueck: ueber eigene Buy-Order gekauft ->
    Daytrade, aus dem Markt -> Swing. Ist die Herkunft unbekannt, entscheidet
    die Haltedauer (< 24 h -> Daytrade) und der Verkauf zaehlt zusaetzlich
    als `geschaetzt`. Rueckgabe {day, swing, geschaetzt, gesamt, netto}."""
    day = swing = geschaetzt = 0
    netto = 0.0
    for e in (events or []):
        netto += float(e.get("net") or 0.0)
        eigen = float(e.get("kauf_eigen") or 0)
        markt = float(e.get("kauf_markt") or 0)
        unbek = float(e.get("kauf_unbekannt") or 0)
        if eigen > markt and eigen >= unbek:
            day += 1
        elif markt >= eigen and markt >= unbek and markt > 0:
            swing += 1
        else:
            geschaetzt += 1
            if float(e.get("halte_h") or 0.0) < DAYTRADE_GRENZE_H:
                day += 1
            else:
                swing += 1
    return {"day": day, "swing": swing, "geschaetzt": geschaetzt,
            "gesamt": day + swing, "netto": netto}


def trades_auswerten(txs, orders, abdeckung, tax=0.0, broker=0.0, paar=None,
                     fracht_satz=0.0, volumen=None, ohne=()):
    """EIN Weg von den gespeicherten Daten zur Trades-Kachel - dieselbe
    FIFO-Rechnung wie der Profits-Tab (`market.realized_trades`), nur mit
    der Kauf-Herkunft dazu. Rueckgabe wie `trades_einteilen` plus `seit`
    (aeltester Handel, ISO-Datum) - None ohne einen einzigen Verkauf."""
    from . import market
    txs = list(txs or [])
    herk = kauf_herkunft(txs, orders, abdeckung)
    # Fracht wie im Profits-Tab (emm575) - sonst zeigt die Kachel mehr
    # Gewinn als der Tab bei "All characters".
    events = market.realized_trades(txs, tax, broker, paar=paar,
                                    fracht_satz=fracht_satz, volumen=volumen,
                                    ohne=ohne, herkunft=herk)
    if not events:
        return None
    out = trades_einteilen(events)
    out["seit"] = min(str(e.get("date") or "") for e in events) or None
    return out


def _zahl(n):
    return f"{int(n):,}".replace(",", "'")


def discord_text(gebaut_map, trades, seit_bau, seit_trades, namen=None,
                 titel=None):
    """Der Text fuer "Copy for Discord" - EINE Formatstelle, das Fenster
    zeigt dieselben Zahlen. `namen` = uebersetzte Kachelnamen, `titel` =
    die uebersetzten Ueberschriften; ohne sie Englisch (Discord ist
    englischsprachig)."""
    n = namen or KACHEL_NAMEN
    tt = {"kopf": "Funfact with Eve MoMa",
          "built": "Built since {seit}", "trades": "Trades since {seit}",
          "day": "Daytrades", "swing": "Swingtrades",
          "ca": "({n} of them estimated by holding time)"}
    tt.update(titel or {})
    z = [f"**{tt['kopf']}**", ""]
    if gebaut_map:
        z.append(f"**{tt['built'].format(seit=seit_bau)}:**")
        for k in KACHELN:
            if gebaut_map.get(k):
                z.append(f"{_zahl(gebaut_map[k])} {n.get(k, k)}")
        z.append("")
    if trades and trades.get("gesamt"):
        z.append(f"**{tt['trades'].format(seit=seit_trades)}:**")
        z.append(f"{_zahl(trades['day'])} {tt['day']}")
        z.append(f"{_zahl(trades['swing'])} {tt['swing']}")
        if trades.get("geschaetzt"):
            z.append(tt["ca"].format(n=_zahl(trades["geschaetzt"])))
    return "\n".join(z).rstrip() + "\n"
