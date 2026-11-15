"""Assets tab helpers (emm863) - pure functions, testable without network.

User request 08.11.2026: a new main tab "Assets" with one card per
character (same look as Industry jobs), every station/structure the
character keeps items at as a fold-out, and a live search box: typing
"Retribution" leaves only the cards of characters that own Retributions,
each card showing the stations they sit at and, unfolded, how many.
"""

from .esi import container_wurzeln


def ort_art(lid):
    """"station" | "system" | "structure" | "other" fuer eine
    Orts-ID (emm865, Nutzer-Screenshot: "teilweise nur zahlen anstatt
    Struktur Namen koennten auch WH's sein wie Terra").

    #30000852 war ein SONNENSYSTEM (Assets "im All", auch Wurmloecher
    wie Thera, J-Space: 31xxxxxx), keine Struktur - der Struktur-Abruf
    scheiterte daran und frass das Fehlerbudget leer, wonach auch echte
    Strukturen namenlos blieben. ID-Baender wie in is_npc_station:
    NPC-Stationen 60-64 Mio, Sonnensysteme 30-34 Mio, Spielerstrukturen
    ab 10^12."""
    try:
        lid = int(lid)
    except (TypeError, ValueError):
        return "other"
    if 60000000 <= lid < 64000000:
        return "station"
    if 30000000 <= lid < 34000000:
        return "system"
    if lid >= 10 ** 12:
        return "structure"
    return "other"


def orte_mengen(assets):
    """{root_location_id: {type_id: qty}} from a raw ESI assets list.

    EVERY row counts and is pinned to its ROOT location (station,
    structure or solar system): items inside containers and ships hang
    on item_ids - `container_wurzeln` walks the chain up (emm807). This
    is a WAREHOUSE view, deliberately unlike the build-material rules in
    `bestand_an_orten` (ships' fittings excluded there): whoever searches
    "Retribution" here wants fitted and bagged hulls found too.
    """
    wurzeln = container_wurzeln(assets)
    out = {}
    for a in (assets or []):
        try:
            iid = int(a["item_id"])
            tid = int(a["type_id"])
            qty = int(a.get("quantity") or 1)
        except (KeyError, TypeError, ValueError):
            continue
        ort = wurzeln.get(iid)
        if not ort:
            continue
        je = out.setdefault(int(ort), {})
        je[tid] = je.get(tid, 0) + qty
    return out


def suche_filter(je_ort, namen, text):
    """Filter {ort: {tid: qty}} down to items whose NAME matches `text`.

    Multi-word AND, case-insensitive (same contract as the emm855 table
    search): every word must appear somewhere in the item's name. An
    empty/blank `text` returns the input unchanged. Locations without a
    single match disappear - the card logic drops characters that end up
    with no locations, exactly what the user described ("dann sehe ich
    nur noch die charakter karten die Retributions besitzen").
    """
    woerter = [w for w in str(text or "").lower().split() if w]
    if not woerter:
        return je_ort
    out = {}
    for ort, mengen in (je_ort or {}).items():
        rest = {}
        for tid, qty in (mengen or {}).items():
            nm = str((namen or {}).get(int(tid)) or "").lower()
            if nm and all(w in nm for w in woerter):
                rest[tid] = qty
        if rest:
            out[ort] = rest
    return out
