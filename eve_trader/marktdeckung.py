"""Marktdeckung - ist eine Doctrine am Handelsplatz wirklich kaufbar, und
wie lange reicht, was dort liegt? (Reiter "Market Stocks", emm824)

Rechnet nur; kein Qt, kein ESI. Die Order-Leitern kommen von
`esi.fetch_structure_orders_full` ({type_id: {'sell': [(preis, menge)
aufsteigend], ...}}), die Doctrine-Mengen von `doctrinen.py`.

ZWEI FRAGEN, ZWEI ANTWORTEN:

1. "IST SIE KOMPLETT VORHANDEN?" Nutzer 03.11.2026: "mind. 10x Stacks von
   der ganzen Doctrine mit fitting und Cargo Inhalt muss kaufbar sein also
   Ordertiefe muss es hergeben". Gezaehlt werden KOMPLETTE FITS: das
   schwaechste Teil entscheidet. Auf Nachfrage nach einer Empfehlung so
   festgelegt (03.11.2026) - eine Doctrine ist nur dann "da", wenn ein
   Pilot ein GANZES Schiff kaufen kann; 95 % der Positionen nuetzen nichts,
   wenn die Munition fehlt. Damit der Balken nicht nur anklagt, liefert
   `fit_deckung` die Engpaesse gleich mit: woran es haengt, knappstes
   Teil zuerst.

2. "WIE LANGE HAELT ES?" Bestand am Platz geteilt durch das
   Tages-Handelsvolumen. WICHTIG UND IN DER OBERFLAECHE SO BENANNT: ESI
   fuehrt Markthistorie nur je REGION, nicht je Struktur - eine Keepstar
   hat keine eigene Volumen-Historie. Die Reichweite ist also "Bestand
   HIER, Verbrauch der REGION". Vom Nutzer so entschieden (03.11.2026,
   Antwort "Region, klar benannt"), weil die Alternative - der eigene
   geplante Verbrauch - kein Marktverbrauch ist.

DER PREISDECKEL (Nutzer 03.11.2026): "Da sollten wir uns an den jita
Preis orientieren, das wird oft im ganzen EVE universum als normalpreis
gesehen. also eine einstellung 'ueber Jita Preis' standard auf 30 %
(aber einstellbar)". Ohne Deckel zaehlte eine einzelne Order zum
50-fachen Preis als "kaufbar_stk" und die Doctrine staende gruen da, waehrend
sie in Wahrheit unbezahlbar ist. Fehlt ein Jita-Preis, wird NICHT
geraten: dann zaehlt das Buch ungedeckelt, und das Item steht in
`ohne_preis` - die Zeile sagt es, statt eine Sicherheit vorzutaeuschen,
die es nicht gibt.
"""

AUFSCHLAG_STANDARD = 30.0       # Prozent ueber Jita (Nutzer, 03.11.2026)
# Ab so viel weggeschnittener Menge lohnt der Hinweis "da liegt zwar
# etwas, aber zu Wucherpreisen" - sonst wundert man sich, warum ein Item
# mit vollem Buch als Engpass gilt.
DECKEL_WARNT_AB = 0.5


def grenzpreis(jita_preis, aufschlag_pct=AUFSCHLAG_STANDARD):
    """Hoechster Preis, der noch als "kaufbar_stk" zaehlt - oder None, wenn
    es keinen Jita-Preis gibt (dann gilt kein Deckel)."""
    try:
        jp = float(jita_preis or 0.0)
    except (TypeError, ValueError):
        return None
    if jp <= 0:
        return None
    try:
        auf = float(aufschlag_pct)
    except (TypeError, ValueError):                      # pragma: no cover
        auf = AUFSCHLAG_STANDARD
    return jp * (1.0 + max(0.0, auf) / 100.0)


def kaufbare_menge(leiter, grenze=None):
    """Stueckzahl in den Sell-Orders bis `grenze` (None = ohne Deckel).

    `leiter` ist der Eintrag eines Items aus `fetch_structure_orders_full`
    oder direkt die Liste [(preis, menge), ...]. Rueckgabe:
    (kaufbar, gesamt_im_buch)."""
    if isinstance(leiter, dict):
        sells = leiter.get("sell") or []
    else:
        sells = leiter or []
    kaufbar = gesamt = 0
    for eintrag in sells:
        try:
            preis, menge = float(eintrag[0]), int(eintrag[1])
        except (TypeError, ValueError, IndexError):      # pragma: no cover
            continue
        if menge <= 0:
            continue
        gesamt += menge
        if grenze is None or preis <= grenze:
            kaufbar += menge
    return kaufbar, gesamt


def bester_sell(leiter):
    """Guenstigstes Sell-Angebot im Buch - oder None, wenn keines da ist.

    Das ist der Preis, zu dem man HIER tatsaechlich kaufen koennte.
    Bewusst OHNE Deckel: der Deckel entscheidet, was als `kaufbar_stk`
    zaehlt; hier geht es um die Frage "was kostet es, wenn ich es
    trotzdem hier nehme" (emm872)."""
    if isinstance(leiter, dict):
        sells = leiter.get("sell") or []
    else:
        sells = leiter or []
    best = None
    for eintrag in sells:
        try:
            preis, menge = float(eintrag[0]), int(eintrag[1])
        except (TypeError, ValueError, IndexError):      # pragma: no cover
            continue
        if menge <= 0 or preis <= 0:
            continue
        if best is None or preis < best:
            best = preis
    return best


def fracht_je_stueck(m3, satz):
    """Transportkosten je Stueck: Volumen mal Satz.

    None, wenn kein Frachtsatz gesetzt ist oder das Volumen fehlt
    (Container, unbekanntes Schiffsvolumen). Bewusst NICHT 0.0 - eine
    Null waere die Behauptung "der Transport ist gratis", und die
    Spalte saehe gerechnet aus, wo nichts gerechnet wurde (Regel 1)."""
    try:
        v = float(m3 or 0.0)
        s = float(satz or 0.0)
    except (TypeError, ValueError):                      # pragma: no cover
        return None
    if v <= 0 or s <= 0:
        return None
    return v * s


def fracht_vergleich(jita_preis, hier_preis, fracht_stk):
    """Wo ist das Stueck guenstiger - HIER kaufen oder in Jita kaufen
    und herkarren? (emm872, Nutzer 08.11.2026 zur 8B-Luecke: "wie ist
    es sinnvoll weiterzugehen hier".)

    Rueckgabe:
      jita_frei_haus - Jita-Preis + Fracht je Stueck (None ohne Basis)
      local          - guenstigstes Angebot am Platz (None = nichts da)
      guenstiger     - "here" | "jita" | None
      diff_stk/_pct  - Ersparnis je Stueck der guenstigeren Seite
      nur_eine_seite - True, wenn die Antwort NICHT aus einem
                       Preisvergleich kommt, sondern weil es die andere
                       Seite gar nicht gibt. Die Anzeige muss das
                       unterscheiden, sonst sieht "Jita" nach einem
                       Rechenergebnis aus (Regel 3)."""
    try:
        jp = float(jita_preis or 0.0)
    except (TypeError, ValueError):                      # pragma: no cover
        jp = 0.0
    try:
        hp = float(hier_preis or 0.0)
    except (TypeError, ValueError):                      # pragma: no cover
        hp = 0.0
    frei_haus = ((jp + fracht_stk)
                 if (jp > 0 and fracht_stk is not None) else None)
    erg = {"jita_frei_haus": frei_haus, "local": hp if hp > 0 else None,
           "guenstiger": None, "diff_stk": None, "diff_pct": None,
           "nur_eine_seite": False}
    if hp <= 0 and frei_haus is None:
        return erg                        # beide Seiten unbekannt
    if hp <= 0:
        erg["guenstiger"] = "jita"        # hier liegt nichts
        erg["nur_eine_seite"] = True
        return erg
    if frei_haus is None:
        erg["guenstiger"] = "here"        # kein Jita-Preis oder keine Fracht
        erg["nur_eine_seite"] = True
        return erg
    if hp <= frei_haus:
        erg["guenstiger"] = "here"
        erg["diff_stk"] = frei_haus - hp
        erg["diff_pct"] = (frei_haus - hp) / frei_haus * 100.0
    else:
        erg["guenstiger"] = "jita"
        erg["diff_stk"] = hp - frei_haus
        erg["diff_pct"] = (hp - frei_haus) / hp * 100.0
    return erg


def fit_deckung(bedarf, buch, jita_preise=None,
                aufschlag_pct=AUFSCHLAG_STANDARD, ziel=10):
    """Wie viele KOMPLETTE Exemplare dieses Fits sind am Platz kaufbar?

    `bedarf` = {type_id: Menge je EINEM Fit} (doctrinen.fit_bedarf),
    `buch` = {type_id: Leiter} aus der Struktur, `jita_preise` =
    {type_id: Preis}.

    Rueckgabe:
      fits         - komplette Exemplare, hoechstens `ziel`
      pct          - fits / ziel * 100
      positionen   - JEDE Position des Fits, knappste zuerst:
                     {tid, je_fit, voll, kaufbar, im_buch, fehlt, pct,
                      reicht_fuer, ohne_preis, wucher, leer}
      engpaesse    - die Teilmenge davon, die unter dem Ziel bleibt
                     (dieselben Objekte, nicht kopiert)
      ohne_preis / wucher / fehlt_ganz - type_ids fuer die Kurzhinweise

    ALLE POSITIONEN, NICHT NUR DIE ENGPAESSE (Nutzer 04.11.2026: "cool
    waere auch, dass man Doctrine die man hat jeweils ausklappen kann und
    dann alle Module sieht und der Cargo inhalt (munition usw) und
    daneben jeweils Stocks in % sieht, damit man noch selber entscheiden
    kann ob man wirklich die ganze Doctrine bauen will"). Die
    Engpass-Liste ist deshalb nur noch ein Ausschnitt derselben Daten -
    eine zweite, eigene Rechnung dafuer waere ein zweiter Ort fuer
    denselben Wert (Regel 9).

    `voll` ist die Stueckzahl, bei der DIESE Position zu 100 % gilt:
    Menge je Fit mal Ziel. Genau der Punkt, auf den der Nutzer Wert
    legt - 250 Schiffe mit je 100 Schuss sind 25 000 Schuss, nicht 250.
    """
    try:
        ziel = max(1, int(ziel))
    except (TypeError, ValueError):                      # pragma: no cover
        ziel = 10
    bedarf = {int(t): int(q) for t, q in (bedarf or {}).items() if int(q) > 0}
    if not bedarf:
        # Ein Fit ohne Posten ist kein gedeckter Fit, sondern gar keiner.
        return {"fits": 0, "pct": 0.0, "positionen": [], "engpaesse": [],
                "ohne_preis": [], "wucher": [], "fehlt_ganz": [],
                "ziel": ziel}
    buch = buch or {}
    preise = jita_preise or {}
    fits = ziel
    positionen, ohne_preis, wucher, fehlt_ganz = [], [], [], []
    for tid, je_fit in bedarf.items():
        gr = grenzpreis(preise.get(tid), aufschlag_pct)
        kaufbar, gesamt = kaufbare_menge(buch.get(tid), gr)
        _leer = gesamt <= 0
        _ohne = gr is None
        _wucher = (not _leer and gr is not None
                   and kaufbar < gesamt * DECKEL_WARNT_AB)
        if _ohne:
            ohne_preis.append(tid)
        if _leer:
            fehlt_ganz.append(tid)
        elif _wucher:
            wucher.append(tid)
        voll = je_fit * ziel
        reicht_fuer = kaufbar // je_fit
        positionen.append({
            "tid": tid, "je_fit": je_fit, "voll_stk": voll,
            "kaufbar_stk": kaufbar, "im_buch": gesamt,
            "fehlt_stk": max(0, voll - kaufbar),
            "pct": min(100.0, kaufbar * 100.0 / voll) if voll else 0.0,
            "reicht_fuer": reicht_fuer, "ohne_preis": _ohne,
            "wucher": _wucher, "leer": _leer,
            # emm872: was kostet das Stueck HIER wirklich - Grundlage
            # fuer den Vergleich mit "Jita + Fracht" in der Karte.
            "bester_sell": bester_sell(buch.get(tid))})
        fits = min(fits, reicht_fuer)
    # KNAPPSTE ZUERST - die Zeile, die die Doctrine aufhaelt, steht oben.
    positionen.sort(key=lambda p: (p["pct"], p["tid"]))
    fits = max(0, min(ziel, fits))
    return {"fits": fits, "pct": fits * 100.0 / ziel,
            "positionen": positionen,
            "engpaesse": [p for p in positionen if p["reicht_fuer"] < ziel],
            "ohne_preis": ohne_preis, "wucher": wucher,
            "fehlt_ganz": fehlt_ganz, "ziel": ziel}


def doctrine_deckung(doctrine, buch, jita_preise=None,
                     aufschlag_pct=AUFSCHLAG_STANDARD):
    """Deckung einer ganzen Doctrine: das SCHWAECHSTE Fit entscheidet.

    Begruendung wie beim Fit selbst - eine Doctrine, bei der ein Fit
    fehlt, ist nicht geflogen. `je_fit` traegt die Einzelwerte fuer die
    Aufklappansicht."""
    from . import doctrinen as _d
    fits = (doctrine or {}).get("fits") or []
    ziel = (doctrine or {}).get("ziel") or _d.ZIEL_STANDARD
    if not fits:
        return {"fits": 0, "pct": 0.0, "je_fit": [], "positionen": [],
                "engpaesse": [], "ohne_preis": [], "wucher": [],
                "fehlt_ganz": [], "ziel": ziel}
    je_fit, schwach = [], None
    ids = {"ohne_preis": [], "wucher": [], "fehlt_ganz": []}
    # EIN ITEM, EINE ZEILE - auch wenn mehrere Fits der Doctrine es
    # brauchen: dann addieren sich die Mengen je Fit, denn der Markt
    # muss ALLE Fits zugleich tragen. Dieselbe Falle wie bei geteilten
    # Items zwischen Doctrinen, nur eine Ebene tiefer.
    sammel = {}
    for f in fits:
        _bed = _d.fit_bedarf(f)
        erg = fit_deckung(_bed, buch, jita_preise, aufschlag_pct, ziel)
        erg["schiff"] = f.get("schiff") or ""
        erg["name"] = f.get("name") or ""
        je_fit.append(erg)
        schwach = erg["fits"] if schwach is None else min(schwach, erg["fits"])
        for k in ids:
            for x in erg[k]:
                if x not in ids[k]:
                    ids[k].append(x)
        for t, q in _bed.items():
            sammel[t] = sammel.get(t, 0) + q
    gesamt = fit_deckung(sammel, buch, jita_preise, aufschlag_pct, ziel)
    schwach = max(0, int(schwach or 0))
    return {"fits": schwach, "pct": schwach * 100.0 / max(1, int(ziel)),
            "je_fit": je_fit, "ziel": ziel,
            "positionen": gesamt["positionen"],
            "engpaesse": gesamt["engpaesse"], **ids}


def reichweite_tage(bestand, tagesvolumen):
    """Wie viele Tage haelt der Bestand beim Tagesverbrauch der Region?

    None, wenn es kein brauchbares Volumen gibt - dann wird NICHT
    gerechnet und die Zeile sagt "unbekannt", statt eine Zahl zu
    erfinden (Regel 1)."""
    try:
        b = float(bestand or 0.0)
        v = float(tagesvolumen or 0.0)
    except (TypeError, ValueError):                      # pragma: no cover
        return None
    if v <= 0:
        return None
    return max(0.0, b) / v


def item_lage(tid, bedarf_gesamt, buch, jita_preise=None,
              aufschlag_pct=AUFSCHLAG_STANDARD, tagesvolumen=None):
    """Eine Zeile der Gesamt-Itemliste: was liegt da, reicht es, wie lange.

    `bedarf_gesamt` ist der Bedarf ueber ALLE Doctrinen
    (doctrinen.alle_items)."""
    gr = grenzpreis((jita_preise or {}).get(tid), aufschlag_pct)
    kaufbar, gesamt = kaufbare_menge((buch or {}).get(tid), gr)
    try:
        noetig = max(0, int(bedarf_gesamt or 0))
    except (TypeError, ValueError):                      # pragma: no cover
        noetig = 0
    return {"tid": int(tid), "kaufbar_stk": kaufbar, "im_buch": gesamt,
            "noetig": noetig, "fehlt_stk": max(0, noetig - kaufbar),
            "tage": reichweite_tage(gesamt, tagesvolumen),
            "ohne_preis": gr is None,
            "wucher": gr is not None and gesamt > 0
            and kaufbar < gesamt * DECKEL_WARNT_AB}
