"""MATERIAL, DAS IN EINEM OFFENEN VERTRAG UNTERWEGS IST (emm745).

WOZU ES DAS GIBT - der Abend des 28.10.2026, Schritt fuer Schritt:

  17:11  "Stock Locations, ploetzlich fehlt ueberall Material, ich habe
         nix gemacht" - 18'240'750 Pyerite, 3'336'090 Mexallon und sieben
         weitere Posten rot als fehlend, Einkaufs-Knopf frei.
  17:15  "Die Plaene brauchen ploetzlich Material, was gar nicht sein kann
         dass die das brauchen."
  16:53  davor schon: "Bauplan behauptet ploetzlich ich haette blueprints
         nicht, ich habe sie aber alle" - acht Blaupausen rot
         "completely missing", obwohl im Spiel im Hangar sichtbar.
  17:50  die Aufloesung, vom Nutzer: "ich habe alles von Peanut Motor zu
         Leziris Lezflow getauscht vor gut 1 stunde".

GEMESSEN (sein lagerorte_bericht.txt, zwei Laeufe):

    Peanut Motor     1'859 -> 582 Zeilen   (22'246'857 -> 8'463'052 Stueck)
    Leziris Lezflow    160 -> 160 Zeilen   (346'840 -> 346'840, UNVERAENDERT)

Beim Absender weg, beim Empfaenger nicht angekommen. Genau das ist ein
offener Vertrag: solange ihn niemand annimmt, gehoeren die Sachen
NIEMANDEM - ESI meldet sie weder unter /assets/ noch unter /blueprints/,
bei keinem der beiden Charaktere. Eve MoMa sah also nichts und schloss
daraus "du hast es nicht". Dieselbe Fehlerklasse wie emm476/479/516/744:
NICHT SEHEN KOENNEN IST NICHT DASSELBE WIE NICHT HABEN.

Dieses Modul ist die reine Rechnung dazu - kein Qt, kein Netz, damit sie
sich ohne ESI pruefen laesst. Den Abruf macht `esi.fetch_character_contracts`
/ `esi.fetch_character_contract_items` (NICHT `fetch_contract_items` -
die gehoert den oeffentlichen Contracts des Scanners, s. emm763), die
Anzeige macht die Stock-Locations-Seite und der
Blueprints-Reiter.
"""
from __future__ import annotations

# Ein Vertrag haelt die Ware fest, solange er weder angenommen noch
# zurueckgezogen ist. ESI-Status laut Doku:
#   outstanding  steht offen, niemand hat ihn angenommen
#   in_progress  angenommen, aber noch nicht erfuellt (Kurier unterwegs)
# Alles andere (finished, cancelled, rejected, deleted, failed, reversed)
# hat die Ware wieder freigegeben - entweder beim Empfaenger oder zurueck
# beim Aussteller; dort taucht sie dann normal in /assets/ auf.
OFFEN = ("outstanding", "in_progress")

# Welche Vertragsarten ueberhaupt Ware halten. `auction` haelt sie
# ebenfalls (die Ware liegt im Vertrag, bis er endet), `courier` auch
# (sie ist im Frachtraum des Kuriers). `loan` haelt keine Ware.
MIT_WARE = ("item_exchange", "auction", "courier")


def offene_vertraege(vertraege, jetzt=None):
    """Die Vertraege, die gerade Ware festhalten - dedupliziert.

    WARUM DEDUPLIZIEREN: derselbe Vertrag steht bei JEDEM Beteiligten in
    der Liste. Peanut Motor (Aussteller) und Leziris Lezflow (Empfaenger)
    sind beide verknuepft, also kommt er zweimal an. Ungeprueft zaehlte
    seine Ware doppelt - dieselbe Falle wie bei den Corp-Assets
    (`corp.abrufplan`: je Corporation EIN Abruf, sonst verdreifacht sich
    der Hangar).

    `vertraege`: [[Vertrag, ...], ...] oder eine flache Liste; jeder
    Vertrag wie von ESI (contract_id, type, status, ...).
    Rueckgabe: {contract_id: Vertrag}, nach contract_id eindeutig.
    """
    out = {}
    for eintrag in (vertraege or []):
        liste = eintrag if isinstance(eintrag, (list, tuple)) else [eintrag]
        for v in (liste or []):
            if not isinstance(v, dict):
                continue
            if str(v.get("status") or "") not in OFFEN:
                continue
            if str(v.get("type") or "") not in MIT_WARE:
                continue
            try:
                cid = int(v.get("contract_id") or 0)
            except (TypeError, ValueError):
                continue
            if cid > 0:
                out.setdefault(cid, v)
    return out


def posten_aus_items(items):
    """{type_id: Menge} aus den Positionen EINES Vertrags.

    NUR WAS DER AUSSTELLER HERGIBT (`is_included` True). Die andere Haelfte
    ist das, was er VERLANGT - die liegt noch beim Empfaenger im Hangar und
    wuerde sonst doppelt gezaehlt.

    Blaupausen-Kopien zaehlen mit: fuer die Frage "wo ist meine Blaupause?"
    ist die Runs-Zahl egal, es geht nur darum, dass sie existiert.
    """
    out = {}
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        if not it.get("is_included", False):
            continue
        try:
            tid = int(it.get("type_id") or 0)
            menge = int(it.get("quantity") or 0)
        except (TypeError, ValueError):
            continue
        # ESI schickt bei einer einzelnen Blaupause quantity -1 (Original)
        # bzw. -2 (Kopie) - dieselbe Eigenart wie in `fetch_blueprints`.
        if menge < 0:
            menge = 1
        if tid > 0 and menge > 0:
            out[tid] = out.get(tid, 0) + menge
    return out


def unterwegs(vertraege, items_je_vertrag):
    """{type_id: Menge} ueber ALLE offenen Vertraege zusammen.

    `vertraege`: Ergebnis von `offene_vertraege` (oder eine Rohliste).
    `items_je_vertrag`: {contract_id: [Positionen]} - was der Aufrufer
        abgerufen hat. Fehlt ein Vertrag darin, zaehlt er nicht mit; das
        ist Absicht (ein gescheiterter Positions-Abruf darf keine Menge
        erfinden), und `fehlende_items` sagt, welche fehlen.
    """
    if not isinstance(vertraege, dict):
        vertraege = offene_vertraege(vertraege)
    out = {}
    for cid in vertraege:
        for tid, menge in posten_aus_items(
                (items_je_vertrag or {}).get(cid) or []).items():
            out[tid] = out.get(tid, 0) + menge
    return out


def fehlende_items(vertraege, items_je_vertrag):
    """Vertraege, deren Positionen NICHT abgerufen werden konnten.

    Regel 1: lieber sagen, dass etwas fehlt, als so tun, als sei nichts da.
    Der Aufrufer macht daraus denselben Hinweis wie bei einem
    gescheiterten Asset-Abruf - die Mengen sind dann unvollstaendig.
    """
    if not isinstance(vertraege, dict):
        vertraege = offene_vertraege(vertraege)
    return sorted(cid for cid in vertraege
                  if (items_je_vertrag or {}).get(cid) is None)


def lager_zeilen(vertraege_offen, items_je_vertrag):
    """Stock-Locations-Zeilen aus offenen Vertraegen (emm760).

    -> (zeilen, benutzte): `zeilen` im selben Format wie
    `lagerorte.zeilen_aus_assets`, damit Baum, Karten, Fehlbetrag und
    Einkaufsliste sie OHNE Sonderregel mitzaehlen ("liegt in einem
    offenen Vertrag" statt "fehlt"); `benutzte` = {contract_id: Vertrag}
    der Vertraege, die wirklich Zeilen beigetragen haben - der Aufrufer
    beschriftet fuer sie den synthetischen Behaelter.

    Je Zeile:
      ort      = start_location_id (0, wenn ESI keinen liefert - die
                 Seite nennt den Pseudo-Ort dann beim Namen)
      besitzer = issuer_id, art "char" (gezaehlt werden nur Vertraege
                 EIGENER Aussteller - der Aufrufer filtert mit
                 `beteiligte`, siehe mw_bauplan_tabs: Ware, die ein
                 Fremder UNS anbietet, gehoert uns erst nach Annahme)
      flag     = "Contract"
      pfad     = [-contract_id]: ein SYNTHETISCHER Behaelter je Vertrag.
                 Negativ, damit er nie mit einer echten item_id
                 kollidiert (die sind immer positiv) und nie an
                 fetch_asset_names geht; seinen Anzeigenamen setzt der
                 Aufrufer direkt in beh_namen.
      item_id  = None (es gibt kein Asset dahinter)
    """
    if not isinstance(vertraege_offen, dict):
        vertraege_offen = offene_vertraege(vertraege_offen)
    zeilen, benutzte = [], {}
    for cid, v in (vertraege_offen or {}).items():
        posten = posten_aus_items((items_je_vertrag or {}).get(cid) or [])
        if not posten:
            continue
        try:
            ort = int(v.get("start_location_id") or 0)
        except (TypeError, ValueError):
            ort = 0
        try:
            iss = int(v.get("issuer_id") or 0)
        except (TypeError, ValueError):
            iss = 0
        for tid, menge in sorted(posten.items()):
            zeilen.append({"tid": tid, "menge": menge, "ort": ort,
                           "besitzer": iss, "art": "char",
                           "flag": "Contract", "pfad": [-int(cid)],
                           "item_id": None})
        benutzte[cid] = v
    return zeilen, benutzte


def je_charakter(vertraege_offen, eigene_ids):
    """Wer hat wie viele offene Vertraege? (emm764)

    Nutzer 29.10.2026: "können wir bitte in Industry Jobs exta karte
    haben für Contracts und welcher charakter wie viele offen hat? für
    noch mehr übersicht".

    -> {character_id: {"raus": n, "rein": n, "kurier": n, "posten": n}}
       raus    = er ist AUSSTELLER (seine Ware haengt im Vertrag)
       rein    = er ist EMPFAENGER (Ware kommt zu ihm, sobald er annimmt)
       kurier  = davon Kurier-Vertraege (Ware ist unterwegs)
       posten  = Summe der Positionen, soweit sie abgerufen wurden

    Ein Vertrag zwischen ZWEI eigenen Charakteren zaehlt bei BEIDEN -
    einmal als `raus`, einmal als `rein`. Das ist Absicht: die Karte
    soll zeigen, wo etwas haengt UND wer es abholen muss.
    `vertraege_offen` ist das Ergebnis von `offene_vertraege` (oder eine
    Rohliste), `eigene_ids` die character_ids der verknuepften
    Charaktere.
    """
    if not isinstance(vertraege_offen, dict):
        vertraege_offen = offene_vertraege(vertraege_offen)
    _eig = set()
    for x in (eigene_ids or ()):
        try:
            _eig.add(int(x))
        except (TypeError, ValueError):
            continue
    out = {}

    def _e(cid):
        return out.setdefault(int(cid), {"raus": 0, "rein": 0, "kurier": 0,
                                         "posten": 0})
    for v in (vertraege_offen or {}).values():
        if not isinstance(v, dict):
            continue
        _kur = str(v.get("type") or "") == "courier"
        for _feld, _schl in (("issuer_id", "raus"), ("assignee_id", "rein")):
            try:
                _cid = int(v.get(_feld) or 0)
            except (TypeError, ValueError):
                continue
            if _cid not in _eig:
                continue
            _z = _e(_cid)
            _z[_schl] += 1
            if _kur:
                _z["kurier"] += 1
    return out


def anzunehmen(vertraege_offen, eigene_ids):
    """Nur die Vertraege, bei denen DU am Zug bist (emm771).

    Nutzer 30.10.2026: "zeige in den Contract Liste bitte nur
    ausstehende Contracts an und nur solche die ich annehmen muss".
    Zwei Bedingungen, beide hart:

      * Status GENAU "outstanding" - `in_progress` ist bereits
        angenommen (ein Kurier fliegt schon), da ist nichts mehr zu
        tun. `OFFEN` (= beides) bleibt fuer die BESTANDS-Frage
        richtig, denn beide halten Ware fest; fuer die TODO-Liste
        taugt nur der erste.
      * Du bist EMPFAENGER (`assignee_id`). Was du selbst ausgestellt
        hast, musst du nicht annehmen - das wartet auf den anderen.

    -> {character_id: {"rein": n, "kurier": n}} - dieselben Schluessel
    wie `je_charakter`, damit die Anzeige nicht zwei Formen kennen
    muss; "raus" und "posten" gibt es hier nicht, sie waeren immer 0.
    """
    if not isinstance(vertraege_offen, dict):
        vertraege_offen = offene_vertraege(vertraege_offen)
    _eig = set()
    for x in (eigene_ids or ()):
        try:
            _eig.add(int(x))
        except (TypeError, ValueError):
            continue
    out = {}
    for v in (vertraege_offen or {}).values():
        if not isinstance(v, dict):
            continue
        if str(v.get("status") or "") != "outstanding":
            continue
        try:
            _cid = int(v.get("assignee_id") or 0)
        except (TypeError, ValueError):
            continue
        if _cid not in _eig:
            continue
        _e = out.setdefault(_cid, {"rein": 0, "kurier": 0})
        _e["rein"] += 1
        if str(v.get("type") or "") == "courier":
            _e["kurier"] += 1
    return out


def posten_je_charakter(vertraege_offen, items_je_vertrag, eigene_ids):
    """Wie `je_charakter`, aber mit der Stueckzahl im Feld "posten"
    (emm764) - gezaehlt wird nur beim AUSSTELLER, denn nur dessen Ware
    liegt im Vertrag (dieselbe Regel wie `posten_aus_items`)."""
    if not isinstance(vertraege_offen, dict):
        vertraege_offen = offene_vertraege(vertraege_offen)
    out = je_charakter(vertraege_offen, eigene_ids)
    for cid, v in (vertraege_offen or {}).items():
        try:
            _iss = int((v or {}).get("issuer_id") or 0)
        except (TypeError, ValueError):
            continue
        if _iss not in out:
            continue
        out[_iss]["posten"] += sum(posten_aus_items(
            (items_je_vertrag or {}).get(cid) or []).values())
    return out


def beteiligte(v, eigene_ids):
    """("aussteller"|"empfaenger"|"fremd") - wer von uns haengt am Vertrag?

    Fuer den Anzeigetext: "du gibst her" liest sich anders als "kommt zu
    dir". `eigene_ids` sind die character_ids der verknuepften Charaktere.
    """
    _eig = {int(x) for x in (eigene_ids or ()) if str(x).lstrip("-").isdigit()}
    try:
        if int(v.get("issuer_id") or 0) in _eig:
            return "aussteller"
    except (TypeError, ValueError):
        pass
    try:
        if int(v.get("assignee_id") or 0) in _eig:
            return "empfaenger"
    except (TypeError, ValueError):
        pass
    return "fremd"
