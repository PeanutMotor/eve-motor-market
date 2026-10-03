"""Corp-Hangar als Bau-Bestand (1.0.8) - die REINE Logik, ohne Netz.

Alles hier laesst sich mit einer konstruierten Asset-Liste nachstellen. Die
ESI-Abrufe stehen in `esi.py`, die Einbindung in den Bauplan in
`ui/mw_bauplan_fenster.py`. Diese Trennung ist Absicht: die gefaehrlichen
Fehler (Verdreifachung, falsche Division, Schiffsinhalt) muessen ohne
Spielstand pruefbar sein - sonst gibt es keinen Waechter dafuer.

DIE DREI ENTSCHEIDE VOM 14.09.2026 (CLAUDE.md, nicht wieder aufmachen):
1. Standard AUS.  2. Divisions einzeln anwaehlbar.  3. Corp-Vermoegen steht
im Portfolio NEBEN "Total assets" - das kommt spaeter, dieser Patch ist
nur fuers Bauen (Nutzer, 16.09.2026).

DIE GEFAHR, die dieser Bau abfangen muss: ein Corp-Hangar gehoert der CORP,
nicht dem Charakter. Drei verknuepfte Charaktere derselben Corp liefern
dreimal denselben Hangar. Ungeprueft verdreifacht sich der Bestand, und der
Plan kauft ZU WENIG - die gefaehrliche Richtung (Regel 3). Deshalb laeuft
der Abruf je CORPORATION (`abrufplan`), nie je Charakter.
"""

# Die sieben Hangar-Divisions, wie ESI sie an Corp-Assets schreibt.
DIVISION_FLAGS = {f"CorpSAG{i}": i for i in range(1, 8)}
ALLE_DIVISIONS = tuple(range(1, 8))

# Welche Ingame-Rolle welcher Abruf verlangt (ESI-Doku, nachgeschlagen am
# 16.09.2026). EINE Stelle dafuer - die Hinweise in der Oberflaeche lesen
# hier ab, statt die Rollennamen zu wiederholen.
ROLLE_ASSETS = "Director"
ROLLE_BLUEPRINTS = "Director"
ROLLE_DIVISIONS = "Director"
ROLLE_JOBS = "Factory_Manager"


def division_von(flag) -> int:
    """1..7 fuer einen CorpSAG-Flag, sonst 0."""
    return DIVISION_FLAGS.get(flag or "", 0)


def divisions_bereinigt(werte) -> list:
    """Die Einstellung `corp_divisions` als saubere, sortierte Liste 1..7.

    Nimmt Zahlen und Zahl-Strings, wirft alles andere weg. Doppelte fallen
    raus. Eine kaputte Einstellung darf nie dazu fuehren, dass MEHR gezaehlt
    wird als gewollt - im Zweifel zaehlt eine Division nicht.
    """
    out = set()
    for w in werte or ():
        try:
            n = int(w)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 7:
            out.add(n)
    return sorted(out)


def wurzel_ort(a, by_id, max_tiefe=32):
    """Die Station/Struktur, an der ein Corp-Item letztlich haengt.

    Corp-Hangar-Items haengen NICHT direkt an der Station: dazwischen liegt
    das Buero (Flag `OfficeFolder`), und darunter erst die Division. Also
    hochlaufen, bis die location_id kein Item mehr ist. `max_tiefe` ist ein
    Schutz gegen eine zyklische Liste - lieber 0 als eine Endlosschleife.
    """
    loc = a.get("location_id")
    for _ in range(max_tiefe):
        elt = by_id.get(loc)
        if elt is None:
            return loc
        loc = elt.get("location_id")
    return 0


def orte(assets) -> set:
    """Alle Stationen/Strukturen, an denen die Corp Assets hat - die WURZEL
    jedes Items (ueber Buero und Division hochgelaufen, s. wurzel_ort).
    Rein: {location_id}. Tester-Befund 19.09.2026 (Discord, Mike Jag): "Find
    locations and link all" fand seine Citadel nicht - die Suche sah nur
    Charakter-Assets/-Orders, der Corp-Hangar war unsichtbar, und damit
    liess sich die Bau-Struktur nie verknuepfen."""
    by_id = {}
    for a in assets or []:
        try:
            by_id[int(a.get("item_id"))] = a
        except (TypeError, ValueError):
            continue
    out = set()
    for a in assets or []:
        loc = wurzel_ort(a, by_id)
        try:
            loc = int(loc or 0)
        except (TypeError, ValueError):
            continue
        if loc > 0:
            out.add(loc)
    return out


def corp_bestand(assets, divisions, location_ids=None, container_typen=None,
                 ist_behaelter=None):
    """{type_id: Menge} aus den gewaehlten Hangar-Divisions einer Corp.

    `assets`: rohe Corp-Asset-Liste (ESI /corporations/{id}/assets/).
    `divisions`: welche Divisions zaehlen (1..7). Leer -> nichts zaehlt.
    `location_ids`: nur diese Stationen/Strukturen - oder None fuer ueberall.
    `container_typen`: Behaelter-Typen aus der SDE (wie bei den Charakter-
    Assets). `ist_behaelter` ueberschreibt die Regel (fuer Tests).

    DIESELBEN REGELN WIE BEIM EIGENEN BESTAND (eine Wahrheit):
    - in Behaelter wird hinabgestiegen, auch verschachtelt;
    - in SCHIFFE nicht - Rumpf ja, Fittings/Ladung/Drohnen nie (Nutzer,
      16.09.2026: "in keinem Szenario");
    - was in einer NICHT gewaehlten Division liegt, existiert fuer den
      Bauplan nicht.

    Gibt (summe, zeilen_je_division) zurueck; die Zaehlung je Division ist
    die Messung fuer den Hinweistext ("Division 3: 0 Zeilen" sagt mehr als
    "nichts gefunden").
    """
    gewaehlt = set(divisions_bereinigt(divisions))
    if not gewaehlt:
        return {}, {}
    by_id = {}
    by_parent = {}
    for a in assets or []:
        iid = a.get("item_id")
        if iid is not None:
            by_id[iid] = a
        by_parent.setdefault(a.get("location_id"), []).append(a)
    if ist_behaelter is None:
        from .esi import _behaelter_pruefer
        ist_behaelter = _behaelter_pruefer(by_parent, container_typen)
    orte = ({int(x) for x in location_ids} if location_ids is not None
            else None)
    summe = {}
    je_division = {}
    gesehen = set()

    def _zaehle(a):
        iid = a.get("item_id")
        if iid in gesehen:
            return
        gesehen.add(iid)
        t = a.get("type_id")
        summe[t] = summe.get(t, 0) + int(a.get("quantity", 1) or 1)
        if ist_behaelter(a):
            for c in by_parent.get(iid, []):
                _zaehle(c)

    for a in assets or []:
        div = division_von(a.get("location_flag"))
        if not div or div not in gewaehlt:
            continue
        if orte is not None and wurzel_ort(a, by_id) not in orte:
            continue
        je_division[div] = je_division.get(div, 0) + 1
        _zaehle(a)
    return summe, je_division


def abrufplan(charaktere, corp_von, rollen_von, rolle):
    """{corporation_id: character_id} - GENAU EIN Charakter je Corp.

    `charaktere`: Liste der verknuepften Charaktere (dicts mit character_id).
    `corp_von`: {character_id: corporation_id} (None = unbekannt).
    `rollen_von`: {character_id: set(Rollen)} (None = nicht abrufbar).
    `rolle`: die Rolle, die der Abruf verlangt (ROLLE_ASSETS, ...).

    DER RIEGEL GEGEN DIE VERDREIFACHUNG: eine Corp erscheint hoechstens
    einmal - egal, wie viele Charaktere in ihr sind. Genommen wird der
    ERSTE Charakter (in Listen-Reihenfolge) mit der noetigen Rolle;
    Charaktere ohne Rolle oder ohne bekannte Corp bleiben aussen vor.

    Gibt (plan, ohne_rolle) zurueck: `ohne_rolle` = {corporation_id:
    [character_ids]} fuer Corps, in denen zwar Charaktere sind, aber keiner
    die Rolle hat - damit die Oberflaeche es beim Namen nennen kann statt
    "0 Bestand" zu zeigen.
    """
    plan = {}
    kandidaten = {}
    for ch in charaktere or []:
        cid = ch.get("character_id") if isinstance(ch, dict) else ch
        if cid is None:
            continue
        corp = (corp_von or {}).get(cid)
        if not corp:
            continue
        kandidaten.setdefault(corp, []).append(cid)
        if corp in plan:
            continue
        rollen = (rollen_von or {}).get(cid) or set()
        if rolle in rollen:
            plan[corp] = cid
    ohne_rolle = {corp: cids for corp, cids in kandidaten.items()
                  if corp not in plan}
    return plan, ohne_rolle


def alle_mit_rolle(charaktere, corp_von, rollen_von, rolle):
    """{corporation_id: [character_ids]} - ALLE Charaktere je Corp mit der
    Rolle (Listen-Reihenfolge). Abgerufen wird weiter nur einmal je Corp
    (`abrufplan`); diese Liste sagt nur, unter WELCHEN Charakteren die
    Corp-Blaupausen in My Blueprints stehen (Nutzer 01.10.2026: "jeden
    Charakter mit Director-Rolle im Dropdown waehlen und die Corp-
    Blueprints sehen")."""
    alle = {}
    for ch in charaktere or []:
        cid = ch.get("character_id") if isinstance(ch, dict) else ch
        corp = (corp_von or {}).get(cid) if cid is not None else None
        if not corp:
            continue
        if rolle in ((rollen_von or {}).get(cid) or set()):
            alle.setdefault(corp, []).append(cid)
    return alle


def division_namen(esi_antwort, gewaehlt=None) -> dict:
    """{1..7: Name} - ESI liefert NUR die umbenannten Divisions; die
    uebrigen bekommen "Corp-Hangar N" (Nutzer 19.09.2026). Mit `gewaehlt`
    nur diese."""
    namen = {i: f"Corp-Hangar {i}" for i in ALLE_DIVISIONS}
    for eintrag in ((esi_antwort or {}).get("hangar") or []):
        try:
            n = int(eintrag.get("division"))
        except (TypeError, ValueError):
            continue
        if 1 <= n <= 7 and eintrag.get("name"):
            namen[n] = str(eintrag["name"])
    if gewaehlt is not None:
        return {n: namen[n] for n in divisions_bereinigt(gewaehlt)}
    return namen
