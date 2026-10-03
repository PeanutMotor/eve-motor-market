"""Reprocessing im Bauplan (1.0.9, Weg B: Compressed Ore statt Minerale,
Weg A: Unrefined-Reaktionen).

Reine Rechenlogik, ohne Oberflaeche und ohne ESI - alles hier ist mit
Woerterbuechern pruefbar (Waechter aa366 / aa367). Die Ausbeute-Formel
selbst liegt in `industry` (reprocess_struktur_basis / reprocess_char_faktor
/ reprocess_ausbeute / reprocess_ergebnis) und ist gegen die Messungen vom
18.09.2026 geprueft.

Weg B (Erz):
  struktur_basis(s, sde)      - Struktur-Basis aus Typ, Rig, Sicherheit
  kandidaten(...)             - welche komprimierten Erze ueberhaupt in Frage
                                kommen (Preis bekannt, Ausgang bekannt)
  plane_erz_einkauf(...)      - ersetzt Mineral-Kaeufe durch Erz-Kaeufe,
                                wo das nach Preis guenstiger ist

Weg A (Unrefined-Reaktionen, Nutzer 19.09.2026 "erraten und einfuegen"):
  unrefined_kandidaten(...)   - je Zwischenmaterial X die Unrefined-Formel,
                                die nach Reprocessing X liefert (aus der SDE:
                                Formel mit Ausgang 1 Stueck, dessen
                                Reprocessing-Ausgang genau EIN Material ist,
                                das nicht zu den Inputs gehoert)
  unrefined_ausbeute(...)     - Stueck X je Run nach Ausbeute (abgerundet),
                                Ruecklaeufer je Run
  unrefined_wahl(...)         - Unrefined-Weg nur, wenn er je Stueck X
                                guenstiger ist als normale Reaktion UND Kauf
  rezepte_mit_unrefined(...)  - Rezept-Kopie, in der X ueber die Unrefined-
                                Formel gebaut wird (alles Weitere - Plan,
                                Baum, Runplaner, Zeiten - laeuft unveraendert
                                ueber dieselben Rezepte)
  unrefined_anwenden(...)     - Reprocessing-Schritte + Ruecklaeufer-
                                Gutschrift auf den fertigen Plan

AUSBEUTE WEG A (gemessen 19.09.2026, Vorschau Unrefined Titanium Chromide):
die Unrefined-Produkte laufen ueber den SCRAPMETAL-Pfad - Basis 50 % x
(1 + 0.02 x Scrapmetal Processing), sonst nichts: kein Reprocessing/
Efficiency (der Nutzer hat beide auf 5, sie fehlten in der Vorschau), kein
Erz-Skill, kein Rig, kein Struktur-Bonus. 53,0 % -> 36 -> 19, 164 -> 86
(abgerundet). Implantat: nicht gemessen, deshalb nicht gerechnet (Regel 3).
Die Struktur-Auswahl der Karte spielt fuer Weg A keine Rolle.

RUECKLAEUFER (Nutzer-Entscheid 19.09.2026): 16 der 17 Formeln geben beim
Reprocessing einen ihrer Inputs zurueck (z. B. 164 Vanadium je Unrefined
Vanadium Hafnite). Er kommt erst NACH der Reaktion, die Einkaufsliste
bleibt deshalb voll; Entscheidung und Baukosten schreiben ihn zum Hub-Preis
gut (eigener Posten, nicht still).

Regel 3 durchgehend: Portionen werden AUFgerundet, Ausgang je Portion
ABgerundet, Nebenprodukte zaehlen nur so weit, wie der Plan sie braucht
(der Rest ist Ueberschuss mit Wert 0). Fehlt ein Preis, kommt das Erz nicht
in Frage - lieber kein Tausch als ein geratener.
"""
import copy
import math

from . import industry

# Typschluessel der Struktur-Liste -> Name in der SDE (fuer den Bonus).
REFINERY_NAMEN = {"athanor": "Athanor", "tatara": "Tatara"}
# Sicherheits-Schluessel aus dem Sicherheits-Multiplikator der Struktur-Liste
# (1.0 High, 1.9 Low, 2.1 Null/WH). Wurmloch zaehlt wie Null - fuer
# Reprocessing-Rigs NICHT gemessen, nur uebernommen.
def sicherheits_schluessel(security) -> str:
    try:
        v = float(security if security is not None else 1.0)
    except (TypeError, ValueError):
        v = 1.0
    if v < 1.5:
        return "hi"
    if v < 2.0:
        return "low"
    return "null"


def struktur_basis(s: dict, sde: dict):
    """(basis 0..1 | None, info). `s` ist ein Eintrag der Struktur-Liste
    ({"type","rigs","security",...}), `sde` das Ergebnis von
    industry.reprocess_struktur_sde(). None + Grund, wenn die SDE die Werte
    nicht hat (Refinery ohne Bonus-Eintrag) - kein Rueckfall auf geratene
    Zahlen. Engineering Complexes: Basis des Service-Moduls ohne Bonus (in
    der SDE steht fuer sie kein strRefiningYieldBonus) - NICHT gemessen."""
    s = s or {}
    sde = sde or {}
    typ = (s.get("type") or "").lower()
    info = {"typ": typ, "rig": None, "sec": None, "bonus": 0.0}
    if typ == "npc":
        return industry.REPRO_SERVICE_BASIS, dict(info, quelle="npc")
    bonus = 0.0
    if typ in REFINERY_NAMEN:
        bonus = (sde.get("bonus") or {}).get(REFINERY_NAMEN[typ])
        if bonus is None:
            return None, dict(info, grund="sde")
    info["bonus"] = float(bonus)
    rig_mult = None
    rigs = sde.get("rig") or {}
    for key in (s.get("rigs") or []):
        if not key or not str(key).startswith("sde:"):
            continue
        try:
            rid = int(str(key)[4:])
        except ValueError:
            continue
        r = rigs.get(rid)
        if not r:
            continue
        # Nur echte Rigs (mit Sicherheits-Faktoren); das Service-Modul traegt
        # dasselbe Attribut, sitzt aber nie in einem Rig-Slot.
        if rig_mult is None or r["mult"] > rig_mult:
            rig_mult = r["mult"]
            info["rig"] = r["name"]
            info["sec"] = sicherheits_schluessel(s.get("security"))
            sec_faktor = r.get(info["sec"], 1.0)
    if rig_mult is None:
        return industry.reprocess_struktur_basis(None, 1.0, bonus), info
    return industry.reprocess_struktur_basis(rig_mult, sec_faktor, bonus), info


def kandidaten(karte: dict, names: dict, cats: dict, price_fn, gratis=()) -> dict:
    """{erz_id: {"portion", "out"}} - komprimierte Erze (Kategorie 25, Name
    beginnt mit "Compressed " oder "Batch Compressed "), die einen bekannten
    Ausgang UND einen Preis haben. Prismaticite (Zufallsausgang) bleibt
    draussen. "Batch Compressed" (Nutzer-Screenshot 18.09.2026: Batch
    Compressed Plagioclase -> 175 Tritanium + 70 Mexallon, Portion und
    Ausgang stehen in der SDE) zaehlt wie jedes andere komprimierte Erz.
    `cats` wie industry.item_category_map(). `gratis` (Blacklist, Nutzer
    19.09.2026: "das Compressed Erz bekommt man z. B. von einem Kollegen"):
    diese Erze zaehlen auch OHNE Hub-Preis - sie werden nicht gekauft."""
    out = {}
    gratis = set(int(g) for g in (gratis or ()))
    for tid, e in (karte or {}).items():
        nm = (names or {}).get(tid) or ""
        if not (nm.startswith("Compressed ") or nm.startswith("Batch Compressed ")):
            continue
        if "Prismaticite" in nm:
            continue
        info = (cats or {}).get(tid)
        if not info or info[0] != 25:
            continue
        if not e.get("out") or int(e.get("portion") or 0) < 1:
            continue
        try:
            p = float(price_fn(tid) or 0.0)
        except (TypeError, ValueError):
            p = 0.0
        if p <= 0.0 and int(tid) not in gratis:
            continue
        out[tid] = {"portion": int(e["portion"]), "out": dict(e["out"])}
    return out


def plane_erz_einkauf(buy: dict, price_fn, kand: dict, ausbeute_von, gratis=()) -> dict:
    """Ersetzt Mineral-Kaeufe durch Erz-Kaeufe, wo es guenstiger ist.

    buy:          {type_id: Menge} aus production_plan()["buy"]
    price_fn:     type_id -> Preis je Stueck (0/None = unbekannt)
    kand:         Ergebnis von kandidaten()
    ausbeute_von: erz_id -> (ausbeute 0..1 | None, char_id | None)

    Gierig, deterministisch: in jeder Runde das (Erz, Ziel-Material)-Paar mit
    der groessten Ersparnis; Nebenprodukte werden dem Plan gutgeschrieben,
    soweit er sie braucht, der Rest ist Ueberschuss (Wert 0). Endet, wenn
    kein Tausch mehr spart. Gibt {"buy", "schritte", "ersparnis",
    "ueberschuss"} zurueck; ohne Tausch ist "buy" eine Kopie des Eingangs.
    """
    buy = {int(k): int(v) for k, v in (buy or {}).items() if int(v or 0) > 0}
    need = dict(buy)
    schritte = []
    ueberschuss = {}
    ersparnis_gesamt = 0.0
    # GRATIS-ERZ (Blacklist = "bekomme ich, kaufe ich nicht"): kostet in
    # der Rechnung 0, gewinnt also ueberall, wo es etwas Gebrauchtes liefert,
    # und landet NICHT auf der Einkaufsliste (Schritt traegt "gratis").
    gratis = set(int(g) for g in (gratis or ()))

    def _preis(tid):
        try:
            return float(price_fn(tid) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _preis_erz(erz):
        return 0.0 if erz in gratis else _preis(erz)

    # Ausbeute je Erz einmal holen (Charakterwahl ist teuer genug).
    ausg = {}
    for erz, e in (kand or {}).items():
        a, cid = ausbeute_von(erz)
        if a is None or not (0.0 < a <= 1.0):
            continue
        je_portion = industry.reprocess_ergebnis(e["out"], e["portion"], e["portion"], a)
        if je_portion:
            ausg[erz] = (a, cid, je_portion)

    while True:
        best = None
        for erz in sorted(ausg):
            a, cid, je_portion = ausg[erz]
            portion = kand[erz]["portion"]
            p_erz = _preis_erz(erz)
            if p_erz <= 0.0 and erz not in gratis:
                continue
            for ziel in sorted(need):
                q_ziel = je_portion.get(ziel, 0)
                if q_ziel <= 0 or need[ziel] <= 0:
                    continue
                p_ziel = _preis(ziel)
                if p_ziel <= 0.0:
                    continue
                portionen = int(math.ceil(need[ziel] / float(q_ziel)))
                kosten = portionen * portion * p_erz
                ersetzt = need[ziel] * p_ziel
                for mat, q in je_portion.items():
                    if mat == ziel:
                        continue
                    gedeckt = min(q * portionen, need.get(mat, 0))
                    if gedeckt > 0:
                        ersetzt += gedeckt * _preis(mat)
                ersp = ersetzt - kosten
                if ersp <= 0.0:
                    continue
                kand_tuple = (ersp, -erz, -ziel)
                if best is None or kand_tuple > best[0]:
                    best = (kand_tuple, erz, ziel, portionen, kosten, ersetzt)
        if best is None:
            break
        _k, erz, ziel, portionen, kosten, ersetzt = best
        a, cid, je_portion = ausg[erz]
        portion = kand[erz]["portion"]
        deckt = {}
        ueb = {}
        for mat, q in je_portion.items():
            ganz = q * portionen
            gedeckt = min(ganz, need.get(mat, 0))
            if gedeckt > 0:
                deckt[mat] = gedeckt
                need[mat] -= gedeckt
                buy[mat] = buy.get(mat, 0) - gedeckt
                if buy[mat] <= 0:
                    buy.pop(mat, None)
            if ganz - gedeckt > 0:
                ueb[mat] = ganz - gedeckt
                ueberschuss[mat] = ueberschuss.get(mat, 0) + ganz - gedeckt
        if erz not in gratis:
            buy[erz] = buy.get(erz, 0) + portionen * portion
        ersparnis_gesamt += ersetzt - kosten
        schritte.append({"erz": erz, "portionen": portionen, "portion": portion,
                         "menge": portionen * portion, "ausbeute": a, "char": cid,
                         "ausgang": {m: q * portionen for m, q in je_portion.items()},
                         "deckt": deckt, "ueberschuss": ueb,
                         "kosten": kosten, "ersetzt": ersetzt,
                         "gratis": erz in gratis})
    # WARUM NICHT? (Nutzer 18.09.2026: "ist es richtig, dass Mexallon und
    # Isogen trotzdem gekauft werden?") Je Material, das gekauft bleibt und
    # das irgendein Kandidat liefern koennte: das beste geprueft Erz und
    # sein Aufpreis in % - oder "kein Erz", wenn keines es liefert. Nur
    # Anzeige, keine Entscheidung.
    abgelehnt = {}
    for ziel in sorted(need):
        if need[ziel] <= 0:
            continue
        p_ziel = _preis(ziel)
        best_erz, best_pct = None, None
        for erz in sorted(ausg):
            a, cid, je_portion = ausg[erz]
            q_ziel = je_portion.get(ziel, 0)
            p_erz = _preis(erz)
            if q_ziel <= 0 or p_erz <= 0.0 or p_ziel <= 0.0:
                continue
            portionen = int(math.ceil(need[ziel] / float(q_ziel)))
            kosten = portionen * kand[erz]["portion"] * _preis_erz(erz)
            ersetzt = need[ziel] * p_ziel
            for mat, q in je_portion.items():
                if mat != ziel:
                    gedeckt = min(q * portionen, need.get(mat, 0))
                    if gedeckt > 0:
                        ersetzt += gedeckt * _preis(mat)
            pct = (kosten - ersetzt) / ersetzt * 100.0 if ersetzt > 0 else None
            if pct is not None and (best_pct is None or pct < best_pct):
                best_erz, best_pct = erz, pct
        abgelehnt[ziel] = {"erz": best_erz, "aufpreis_pct": best_pct}
    return {"buy": buy, "schritte": schritte, "ersparnis": ersparnis_gesamt,
            "ueberschuss": ueberschuss, "abgelehnt": abgelehnt}


def ausbeute_funktion(basis, skills_by_char, implant_by_char, skill_ids, erz_skill,
                      fest=None):
    """Baut `ausbeute_von` fuer plane_erz_einkauf: je Erz den besten
    Charakter (industry.bester_reprocess_char) und daraus die Ausbeute.
    basis: Struktur-Basis 0..1; erz_skill: industry.reprocess_erz_skill().
    fest: Charakter-ID -> NUR dieser Charakter (ein Charakter reprocesst
    alles, s. ein_charakter)."""
    cache = {}
    if fest is not None:
        skills_by_char = {str(k): v for k, v in (skills_by_char or {}).items()
                          if str(k) == str(fest)}

    def _f(erz):
        if erz in cache:
            return cache[erz]
        if basis is None:
            cache[erz] = (None, None)
            return cache[erz]
        cid, faktor = industry.bester_reprocess_char(
            skills_by_char, implant_by_char, skill_ids, (erz_skill or {}).get(erz))
        if faktor is None:
            cache[erz] = (None, None)
            return cache[erz]
        cache[erz] = (industry.reprocess_ausbeute(basis, faktor), cid)
        return cache[erz]
    return _f


def ein_charakter(schritte, price_fn, skills_by_char, implant_by_char, skill_ids,
                  erz_skill):
    """EIN Charakter fuer alle Erze (Nutzer 19.09.2026: "man reprocesst mit
    einem Charakter alles auf einmal, dazu muss man kein Multi-Charakter-
    Setup machen - der mit den besten Skills/Implantaten, der den hoechsten
    Reprocessing-Output bekommt"). Die Charaktere unterscheiden sich nur im
    Erz-Skill je Erz; gewaehlt wird der mit dem hoechsten Faktor ueber die
    Erze des Plans, gewichtet mit dem Einkaufswert je Erz (Menge x Preis,
    ohne Preis = Menge). Gleichstand: kleinere ID. None ohne Schritte oder
    ohne Skills."""
    gewicht = {}
    for st in (schritte or []):
        erz = st.get("erz")
        if erz is None:
            continue
        try:
            p = float(price_fn(int(erz)) or 0.0)
        except Exception:
            p = 0.0
        gewicht[int(erz)] = gewicht.get(int(erz), 0.0) + float(st.get("menge") or 0) * (p or 1.0)
    if not gewicht:
        return None
    best = (None, None)
    for cid in (skills_by_char or {}):
        try:
            cid_i = int(cid)
        except (TypeError, ValueError):
            continue
        summe = 0.0
        ok = False
        for erz, w in gewicht.items():
            _c, f = industry.bester_reprocess_char(
                {str(cid_i): (skills_by_char or {}).get(cid, {})}, implant_by_char,
                skill_ids, (erz_skill or {}).get(erz))
            if f is None:
                continue
            ok = True
            summe += w * f
        if not ok:
            continue
        if best[1] is None or summe > best[1] or (summe == best[1] and cid_i < best[0]):
            best = (cid_i, summe)
    return best[0]


def scrap_ausbeute_funktion(skills_by_char, skill_ids):
    """`ausbeute_von` fuer Weg A (Unrefined-Produkte): je Item der Charakter
    mit der hoechsten Scrapmetal-Processing-Stufe, Ausbeute 0.50 x Faktor.
    Das Item selbst spielt keine Rolle - eine Antwort fuer alle."""
    cid, faktor = industry.bester_scrap_char(skills_by_char, skill_ids)
    if faktor is None:
        antwort = (None, None)
    else:
        antwort = (industry.scrap_ausbeute(faktor), cid)

    def _f(_item):
        return antwort
    return _f


# ---- Fortschritt: Stufe 0 abgehakt oder nicht ---------------------------
# Der Runplaner fuehrt je Schritt einen Haken ("reprocesst"). Solange er
# fehlt, zaehlt das ERZ als Bedarf und die gedeckten Minerale nicht; danach
# muessen die Minerale im Bestand liegen und das Erz ist verbraucht.

def schritt_key(schritt) -> str:
    """Schluessel eines Reprocessing-Schritts in _bd_runplan_checked."""
    return f"repro|{int((schritt or {}).get('erz') or 0)}"


def schritte_durch_bestand(schritte, need, stock) -> set:
    """Schluessel der Erz-Schritte, deren Minerale der Bestand SCHON deckt.

    NUTZER 28.09.2026 (Basilisk): "compressed Ore wird als nicht covered
    markiert, dabei habe ich das compressed ore zu Mineralien verarbeitet".
    Bisher galt ein Erz-Schritt nur durch den Hand-Haken in Stufe 0 als
    erledigt; ohne Haken stand das Erz als fehlend da, obwohl ALLE seine
    Minerale laengst im Hangar lagen.

    REGEL: liegt von JEDEM Mineral, das der Schritt decken soll, mindestens
    der ganze Restbedarf (`need`, ohne Erz-Gutschrift) im fuer diesen Plan
    zaehlenden Bestand (`stock`), ist das Erz ueberfluessig - gleich, ob der
    Nutzer es reprocesst oder die Minerale anders beschafft hat. Fehlt auch
    nur eines, bleibt der Schritt offen (Regel 3). Unrefined-Schritte (Weg A,
    `built`) und Gratis-Erz fallen nicht darunter."""
    aus = set()
    for st in (schritte or []):
        if st.get("built") or st.get("gratis") or not st.get("erz"):
            continue
        deckt = st.get("deckt") or {}
        if not deckt:
            continue
        if all(int((stock or {}).get(int(m), 0) or 0)
               >= int((need or {}).get(int(m), 0) or 0) for m in deckt):
            aus.add(schritt_key(st))
    return aus


def rest_anpassen(need: dict, schritte, abgehakt) -> dict:
    """Restbedarf {tid: Menge} um NICHT abgehakte Schritte anpassen: die
    gedeckten Minerale sinken (nie unter 0, 0 faellt raus), das Erz kommt
    mit seiner Blockmenge dazu. Abgehakte Schritte aendern nichts."""
    out = {int(k): int(v) for k, v in (need or {}).items()}
    abgehakt = set(abgehakt or ())
    for st in (schritte or []):
        if schritt_key(st) in abgehakt or st.get("built"):
            continue           # Weg A: das Unrefined-Produkt wird gebaut, nie gekauft
        for m, q in (st.get("deckt") or {}).items():
            m = int(m)
            rest = out.get(m, 0) - int(q or 0)
            if rest > 0:
                out[m] = rest
            else:
                out.pop(m, None)
        erz = int(st.get("erz") or 0)
        if erz and int(st.get("menge") or 0) > 0 and not st.get("gratis"):
            out[erz] = out.get(erz, 0) + int(st["menge"])
    return out


def fehl_anpassen(fehl, schritte, abgehakt, live_stock=None) -> list:
    """Fehlbedarfs-Liste [(tid, fehlt, bedarf, da, prod), ...] um NICHT
    abgehakte Schritte anpassen: gedeckte Minerale fehlen entsprechend
    weniger (Zeile faellt bei 0 weg), fehlendes Erz kommt als eigene Zeile
    dazu (Blockmenge minus Bestand). Reihenfolge wie die Eingabe:
    absteigend nach Fehlmenge."""
    abgehakt = set(abgehakt or ())
    kredit = {}
    erz_bedarf = {}
    for st in (schritte or []):
        if schritt_key(st) in abgehakt or st.get("built"):
            continue           # Weg A: siehe rest_anpassen
        for m, q in (st.get("deckt") or {}).items():
            kredit[int(m)] = kredit.get(int(m), 0) + int(q or 0)
        erz = int(st.get("erz") or 0)
        if erz and int(st.get("menge") or 0) > 0 and not st.get("gratis"):
            erz_bedarf[erz] = erz_bedarf.get(erz, 0) + int(st["menge"])
    out = []
    for row in (fehl or []):
        tid = int(row[0])
        fehlt = int(row[1]) - kredit.get(tid, 0)
        if fehlt > 0:
            out.append((tid, fehlt) + tuple(row[2:]))
    for erz, menge in sorted(erz_bedarf.items()):
        da = int((live_stock or {}).get(erz, 0) or 0)
        if menge - da > 0:
            out.append((erz, menge - da, menge, da, 0))
    out.sort(key=lambda x: -x[1])
    return out


# ---- Weg A: Unrefined-Reaktionen -----------------------------------------
# Eine Unrefined-Formel (z. B. "Unrefined Hexite Reaction Formula") liefert
# 1 Stueck "Unrefined Hexite" je Run; erst das Reprocessing macht daraus das
# Zwischenmaterial (36 Hexite bei 100 %). 16 der 17 Formeln geben dabei
# einen ihrer Inputs zurueck (Ruecklaeufer). Alles aus der SDE - erkannt an
# der Form, nicht am Namen.

def unrefined_kandidaten(recipes, karte: dict) -> dict:
    """{X: {"u": U, "bp": bp_id, "mats": [(m, q)], "je_run": {X: n, A: r},
    "zurueck": {A: r}}} - je Zwischenmaterial X die Unrefined-Formel U.

    Erkennung (ohne Namen): U ist Reaktions-Produkt mit 1 Stueck je Run,
    hat einen Reprocessing-Ausgang (Portion 1), und darin ist GENAU EIN
    Material, das nicht zu den Inputs der Formel gehoert - das ist X. X
    muss selbst ein Reaktions-Produkt sein (die normale Formel existiert).
    Alle uebrigen Ausgaenge sind Inputs der Formel: Ruecklaeufer. Passt die
    Form nicht, faellt U weg - lieber kein Kandidat als ein falscher."""
    out = {}
    p2b = getattr(recipes, "product_to_bp", None) or {}
    mats_of = getattr(recipes, "bp_materials", None) or {}
    rp = getattr(recipes, "reaction_products", None) or set()
    for u, bp in p2b.items():
        try:
            bp_id, act, qty = bp
        except (TypeError, ValueError):
            continue
        if act != industry.REACTION or int(qty or 0) != 1:
            continue
        e = (karte or {}).get(u)
        if not e or int(e.get("portion") or 0) != 1 or not e.get("out"):
            continue
        mats = list(mats_of.get((bp_id, act)) or [])
        if not mats:
            continue
        inputs = {int(m) for m, _q in mats}
        fremd = [int(m) for m in e["out"] if int(m) not in inputs]
        if len(fremd) != 1:
            continue
        x = fremd[0]
        if x == u or x not in rp or int(e["out"].get(x) or 0) < 1:
            continue
        je_run = {int(m): int(q) for m, q in e["out"].items() if int(q or 0) > 0}
        zurueck = {m: q for m, q in je_run.items() if m != x}
        # Ein Zwischenmaterial mit zwei Unrefined-Formeln gibt es in der SDE
        # nicht; kaeme es vor, gewinnt die kleinere Formel-ID (reproduzierbar).
        if x in out and out[x]["bp"] <= bp_id:
            continue
        out[x] = {"u": int(u), "bp": int(bp_id), "mats": [(int(m), int(q)) for m, q in mats],
                  "je_run": je_run, "zurueck": zurueck}
    return out


def unrefined_ausbeute(kand: dict, ausbeute_von) -> dict:
    """Ergaenzt je X: "ausbeute", "char", "out_je_run" (Stueck X je Run,
    abgerundet), "zurueck_je_run" ({A: Stueck}, abgerundet). Kandidaten ohne
    Ausbeute oder mit 0 Stueck je Run fallen weg. `ausbeute_von(U)` wie bei
    plane_erz_einkauf (der beste Charakter, hier ohne Erz-Skill)."""
    out = {}
    for x, k in (kand or {}).items():
        a, cid = ausbeute_von(k["u"])
        if a is None or not (0.0 < a <= 1.0):
            continue
        erg = industry.reprocess_ergebnis(k["je_run"], 1, 1, a)
        n = int(erg.get(x, 0) or 0)
        if n < 1:
            continue
        out[x] = dict(k, ausbeute=float(a), char=cid, out_je_run=n,
                      zurueck_je_run={m: int(q) for m, q in erg.items() if m != x})
    return out


def unrefined_wahl(kand: dict, ids, price_fn, recipes, opts: dict,
                   kredit_pfn=None) -> dict:
    """Entscheidet je X in `ids`: Unrefined-Weg oder nicht.

    Je Stueck X: (Inputs der Unrefined-Formel zu eff-Preisen x ME + Job-
    Kosten - Ruecklaeufer zum Hub-Preis) / out_je_run, verglichen mit dem
    guenstigeren von normaler Reaktion (industry.build_cost) und Kauf.
    Nur STRIKT guenstiger gewinnt. Gibt {"wahl": {X: kand+per_unit+
    vergleich}, "abgelehnt": {X: {"aufpreis_pct": ..}}} zurueck; ohne Preis
    fuer einen Input kein Tausch."""
    wahl, abgelehnt = {}, {}
    adj = (opts or {}).get("adjusted_prices") or {}
    marg = dict(opts or {}); marg["force_build"] = False
    kredit_pfn = kredit_pfn or price_fn
    memo = {}

    def _kauf(tid):
        try:
            p = float(price_fn(tid) or 0.0)
        except (TypeError, ValueError):
            p = 0.0
        if p > 0.0:
            return p
        a = adj.get(tid)
        return float(a) if (a and a > 0) else None

    never = set((opts or {}).get("never_build") or ()) | set((opts or {}).get("excluded") or ())

    def _eff2(tid):
        """(Preis, Quelle). Was das Material den Plan wirklich kostet: das
        guenstigere von Eigenbau und Kauf - aber Eigenbau nur, wenn der Plan
        es auch bauen DARF (never_build / Blacklist). build_cost() prueft
        das nur fuer die Unter-Materialien, nicht fuer das Item selbst; ein
        Fuel Block ohne eigene Blaupause stuende sonst mit seinem Baupreis
        in der Rechnung, waehrend die Einkaufsliste ihn zum Hub-Preis kauft.
        Bei 5 Bloecken je Run und 19 Stueck Ausgang kippt das die Wahl."""
        b = None if int(tid) in never else industry.build_cost(tid, price_fn, recipes, marg, memo)
        p = _kauf(tid)
        if b is not None and (p is None or b <= p):
            return b, "bau"
        if p is not None:
            return p, "kauf"
        return None, "-"

    def _eff(tid):
        return _eff2(tid)[0]

    def _me(x):
        rmap = (opts or {}).get("me_map_reaction") or {}
        pct = rmap.get(x, (opts or {}).get("me_reaction", 0) or 0)
        return 1.0 - float(pct or 0) / 100.0

    def _normal_detail(x, me):
        """Die normale Formel von X (Rezept, Inputs mit Bau-/Kaufpreis, Job,
        eigene Rechnung je Stueck) - nur fuer die Diagnose-Datei."""
        bp = (getattr(recipes, "product_to_bp", None) or {}).get(x)
        if not bp:
            return None
        mats = (getattr(recipes, "bp_materials", None) or {}).get((bp[0], bp[1])) or []
        zeilen = []
        summe = 0.0
        ok = True
        for m, q in mats:
            try:
                b = industry.build_cost(m, price_fn, recipes, marg, memo)
            except Exception:
                b = None
            p = _kauf(m)
            em, quelle = _eff2(m)
            zeilen.append((int(m), int(q), em, quelle, b, p,
                           int(m) in getattr(recipes, "reaction_products", set())))
            if em is None:
                ok = False
            else:
                summe += q * me * em
        try:
            jn = industry._job_cost(list(mats), bp[1], int(bp[2] or 1), opts or {}, type_id=x)
        except Exception:
            jn = None
        if jn is None:
            jn = summe * ((opts or {}).get("job_pct", 0) / 100.0)
        return {"bp": int(bp[0]), "out": int(bp[2] or 1), "inputs": zeilen, "job": jn,
                "kosten_run": summe + jn if ok else None,
                "per_unit": (summe + jn) / float(bp[2] or 1) if ok else None}

    detail = {}
    for x in sorted(set(int(i) for i in (ids or ())) & set(kand or {})):
        k = kand[x]
        me = _me(x)
        kosten = 0.0
        ok = True
        inputs = []
        for m, q in k["mats"]:
            em, quelle = _eff2(m)
            inputs.append((int(m), int(q), em, quelle))
            if em is None:
                ok = False
                break
            kosten += q * me * em
        if not ok:
            detail[x] = {"inputs": inputs, "grund": "no price"}
            continue
        jc = industry._job_cost(list(k["mats"]), industry.REACTION, 1, opts or {},
                                type_id=x)
        jc = jc if jc is not None else kosten * ((opts or {}).get("job_pct", 0) / 100.0)
        kosten += jc
        kredit = 0.0
        ruecklaeufer = []
        for m, q in (k.get("zurueck_je_run") or {}).items():
            try:
                pk = float(kredit_pfn(m) or 0.0)
            except (TypeError, ValueError):
                pk = 0.0
            kredit += q * pk
            ruecklaeufer.append((int(m), int(q), pk))
        per_unit = (kosten - kredit) / float(k["out_je_run"])
        vergleich = _eff(x)
        # DIAGNOSE (jede Zahl, die in die Entscheidung ging - nichts nachgerechnet)
        detail[x] = {"inputs": inputs, "me": me, "job": jc, "kosten_run": kosten,
                     "kredit_run": kredit, "ruecklaeufer": ruecklaeufer,
                     "out_je_run": int(k["out_je_run"]), "per_unit": per_unit,
                     "normal": industry.build_cost(x, price_fn, recipes, marg, memo),
                     "kauf": _kauf(x), "vergleich": vergleich,
                     # Die NORMALE Formel, wie build_cost sie sieht - Nutzer-
                     # Befund 19.09.2026 (Ishtar): build_cost(Hexite) 7'837
                     # je Stueck, aus Cobalt + Vanadium waeren es ~1'800.
                     # Nachgerechnet je Input mit Bau- UND Kaufpreis.
                     "normal_detail": _normal_detail(x, me)}
        if vergleich is None:
            # weder baubar noch kaufbar - dann ist Unrefined der einzige Weg
            wahl[x] = dict(k, per_unit=per_unit, vergleich=None, kredit_je_run=kredit)
            continue
        if per_unit < vergleich:
            wahl[x] = dict(k, per_unit=per_unit, vergleich=vergleich, kredit_je_run=kredit)
        else:
            abgelehnt[x] = {"aufpreis_pct": (per_unit - vergleich) / vergleich * 100.0
                            if vergleich > 0 else None, "per_unit": per_unit,
                            "vergleich": vergleich}
    return {"wahl": wahl, "abgelehnt": abgelehnt, "detail": detail}


# de_scan4: aus - ENTWICKLER-DIAGNOSE (Textdatei zum Nachsehen, nie Oberflaeche)
# de_scan5: aus
def unrefined_diagnose_text(res: dict, names=None, titel="") -> str:
    """Lesbarer Bericht der Wahl (fuer unrefined_diagnose.txt): je X die
    Inputs mit Preis, Job, Gutschrift, Stueck je Run, ISK je Stueck gegen
    normale Reaktion und Kauf. Nur Anzeige der Entscheidungszahlen."""
    names = names or {}

    def nm(t):
        return str(names.get(int(t)) or f"#{t}")

    def isk(v):
        try:
            return f"{float(v):,.2f}".replace(",", "'")
        except (TypeError, ValueError):
            return "-"
    zeilen = [f"UNREFINED-DIAGNOSE {titel}".rstrip(), ""]
    wahl = res.get("wahl") or {}
    for x, d in sorted((res.get("detail") or {}).items(), key=lambda kv: nm(kv[0])):
        zeilen.append(f"{nm(x)}  ->  {'GEWAEHLT' if x in wahl else 'abgelehnt'}")
        if d.get("grund"):
            zeilen.append(f"    {d['grund']}: " + ", ".join(
                f"{nm(m)} {q}x {isk(e) if e is not None else 'KEIN PREIS'}"
                for m, q, e, _qu in d.get("inputs") or []))
            zeilen.append("")
            continue
        for m, q, e, qu in d.get("inputs") or []:
            zeilen.append(f"    Input   {q:>5} x {nm(m):<32} je {isk(e):>16} ({qu:<4}) = {isk(q * (e or 0) * d.get('me', 1.0)):>18}")
        zeilen.append(f"    Job-Kosten je Run                                              {isk(d.get('job')):>18}")
        zeilen.append(f"    = Kosten je Run (ME {d.get('me', 1.0):.4f})                                {isk(d.get('kosten_run')):>18}")
        for m, q, pk in d.get("ruecklaeufer") or []:
            zeilen.append(f"    Zurueck {q:>5} x {nm(m):<32} je {isk(pk):>16}  = {isk(q * pk):>18}")
        zeilen.append(f"    - Gutschrift je Run                                            {isk(d.get('kredit_run')):>18}")
        zeilen.append(f"    / {d.get('out_je_run')} Stueck je Run  ->  UNREFINED je Stueck                 {isk(d.get('per_unit')):>18}")
        zeilen.append(f"    normale Reaktion je Stueck (build_cost)                        {isk(d.get('normal')) if d.get('normal') is not None else '-':>18}")
        nd = d.get("normal_detail")
        if nd:
            zeilen.append(f"      normale Formel #{nd.get('bp')}, {nd.get('out')} Stueck je Run - nachgerechnet:")
            for m, q, e, qu, b, p, rp in nd.get("inputs") or []:
                zeilen.append(
                    f"      Input {q:>5} x {nm(m):<30} je {isk(e) if e is not None else '-':>14} ({qu:<4})"
                    f"  bau {isk(b) if b is not None else '-':>14}  kauf {isk(p) if p is not None else '-':>14}"
                    f"{'  [Reaktionsprodukt -> wird immer gebaut]' if rp else ''}")
            zeilen.append(f"      Job je Run {isk(nd.get('job')):>16}   = je Run {isk(nd.get('kosten_run')) if nd.get('kosten_run') is not None else '-':>16}"
                          f"   -> eigene Rechnung je Stueck {isk(nd.get('per_unit')) if nd.get('per_unit') is not None else '-':>14}")
        zeilen.append(f"    Kaufpreis je Stueck                                            {isk(d.get('kauf')) if d.get('kauf') is not None else '-':>18}")
        zeilen.append(f"    Vergleichswert (kleinerer der beiden)                          {isk(d.get('vergleich')) if d.get('vergleich') is not None else '-':>18}")
        zeilen.append("")
    return "\n".join(zeilen)
# de_scan5: an
# de_scan4: an


def rezepte_mit_unrefined(recipes, wahl: dict):
    """Flache Kopie der Rezepte, in der jedes X aus `wahl` ueber seine
    Unrefined-Formel gebaut wird: product_to_bp[X] = (U-Formel, REACTION,
    out_je_run). Materialien und Zeiten der Formel stehen schon unter der
    Formel-ID - nichts weiter zu aendern. Das Original bleibt unberuehrt
    (es ist der Prozess-Cache). Ohne Wahl: das Original selbst."""
    if not wahl:
        return recipes
    neu = copy.copy(recipes)
    neu.product_to_bp = dict(recipes.product_to_bp)
    for x, k in wahl.items():
        neu.product_to_bp[int(x)] = (int(k["bp"]), industry.REACTION, int(k["out_je_run"]))
    neu.unrefined = {int(x): dict(k) for x, k in wahl.items()}
    return neu


def unrefined_anwenden(plan: dict, wahl: dict, kredit_pfn) -> dict:
    """Reprocessing-Schritte (gebaut, nicht gekauft) und Ruecklaeufer-
    Gutschrift auf den fertigen Plan. Kopie; ohne gebautes X unveraendert.
    Schritt: {"art": "unrefined", "built": True, "erz": U, "menge": Runs,
    "deckt": {X: Stueck}, "ueberschuss": {A: Ruecklaeufer}, "kredit": ISK}.
    total_cost sinkt um die Gutschrift (mat_cost NICHT: die Einkaufsliste
    bleibt voll), plan["reprocess"]["ruecklaeufer_wert"] nennt sie."""
    if not plan or not wahl:
        return plan
    runs_von = plan.get("build_runs") or {}
    neu = dict(plan)
    rp = dict(neu.get("reprocess") or {})
    schritte = list(rp.get("schritte") or [])
    surplus = dict(neu.get("surplus") or {})
    gesamt = 0.0
    for x in sorted(wahl):
        k = wahl[x]
        runs = int(runs_von.get(int(x), 0) or 0)
        if runs < 1:
            continue
        gemacht = runs * int(k["out_je_run"])
        deckt = {int(x): max(0, gemacht - int(surplus.get(int(x), 0) or 0))}
        zurueck = {int(m): int(q) * runs for m, q in (k.get("zurueck_je_run") or {}).items()}
        kredit = 0.0
        for m, q in zurueck.items():
            try:
                kredit += q * float(kredit_pfn(m) or 0.0)
            except (TypeError, ValueError):
                pass
            surplus[m] = int(surplus.get(m, 0) or 0) + q
        gesamt += kredit
        schritte.append({"art": "unrefined", "built": True, "erz": int(k["u"]),
                         "produkt": int(x), "portionen": runs, "portion": 1,
                         "menge": runs, "ausbeute": float(k["ausbeute"]),
                         "char": k.get("char"),
                         "ausgang": dict([(int(x), gemacht)] + list(zurueck.items())),
                         "deckt": deckt, "ueberschuss": zurueck,
                         "kredit": kredit, "kosten": 0.0, "ersetzt": 0.0})
    if gesamt or any(s.get("art") == "unrefined" for s in schritte):
        rp["schritte"] = schritte
        rp["ruecklaeufer_wert"] = float(rp.get("ruecklaeufer_wert") or 0.0) + gesamt
        rp.setdefault("ersparnis", 0.0)
        rp.setdefault("ueberschuss", {})
        neu["reprocess"] = rp
        neu["surplus"] = surplus
        if isinstance(neu.get("total_cost"), (int, float)):
            neu["total_cost"] = float(neu["total_cost"]) - gesamt
        # Die Wahl wandert mit dem Plan (Einfrieren): daraus laesst sich die
        # Rezept-Kopie spaeter ohne neue Entscheidung wiederherstellen.
        neu["unrefined"] = {int(x): dict(wahl[x]) for x in wahl
                            if int(runs_von.get(int(x), 0) or 0) > 0}
    return neu
