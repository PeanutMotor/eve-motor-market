"""Doctrinen - Allianz-Fits aus dem Ingame-Clipboard (Reiter "Market
Stocks", emm824).

NUTZER-IDEE (03.11.2026): "Da soll man verschiedene Allianz Doctrinen per
ingame Clipboard posten koennen, Abspeichern mit Name, es wird eine
Doctrine Liste erstellt wo man prozentual sieht ob sie komplett vorhanden
ist (mind. 10x Stacks von der ganzen Doctrine mit fitting und Cargo
Inhalt muss kaufbar sein also Ordertiefe muss es hergeben)."

Dieses Modul kann NUR Text und Mengen - kein Qt, kein ESI, keine Preise.
Was ein Fit KOSTET und ob er am Markt zu haben ist, rechnet
`marktdeckung.py`; beides getrennt, damit die aa-Suite die Rechnung ohne
Oberflaeche pruefen kann (wie `funfact.py` neben dem Funfact-Fenster).

DAS EFT-FORMAT, wie es aus dem Spiel und aus Pyfa wirklich kommt:

    [Rifter, WC Tackle v1.1]        <- Rumpf, dann Fitname (erstes Komma)
    200mm AutoCannon II, Republic Fleet EMP S
    200mm AutoCannon II, Republic Fleet EMP S
    [Empty High slot]               <- leerer Slot, zaehlt nichts

    1MN Afterburner II
    Warp Scrambler II

    Damage Control II

    Small Projectile Collision Accelerator I

    Hobgoblin II x5                 <- Drohnen mit Menge
    Nanite Repair Paste x50         <- Cargo mit Menge

Die Leerzeilen trennen im Spiel die Slot-Gruppen (High/Mid/Low/Rigs/
Subsysteme/Drohnen/Cargo). FUER UNS SIND SIE EGAL: der Nutzer will
"fitting und Cargo Inhalt" zusammen gedeckt sehen, also zaehlt jede
Zeile gleich viel. Darum wird hier auch nicht versucht, die Gruppen zu
erkennen - das waere Deutung ohne Nutzen und ginge bei exotischen
Fits (T3-Subsysteme, leere Gruppen) schief.

ZWEI STELLEN, DIE MAN LEICHT FALSCH MACHT:

1. GELADENE MUNITION HINTER DEM KOMMA. "200mm AutoCannon II, Republic
   Fleet EMP S" sind ZWEI Posten: die Waffe und ihre Ladung. Wer nur bis
   zum Komma liest, haelt die Doctrine fuer gedeckt, obwohl keine
   Munition am Markt liegt. Gezaehlt wird EINE Ladung je geladenem
   Modul - das ist die ehrliche Untergrenze (wie viel ein Pilot
   TATSAECHLICH mitnimmt, steht im Fit nicht; was darueber hinaus
   gebraucht wird, steht ohnehin als eigene Cargo-Zeile da).

2. DER RUMPF IST EIN POSTEN. Ein Fit ohne sein Schiff ist nicht
   kaufbar - "Total Hulls" ist in jeder Doctrine-Uebersicht die erste
   Zahl, auf die man schaut.

Namen werden hier NICHT aufgeloest: `fits_lesen` liefert Namen und
Mengen, `fit_aufloesen` macht daraus type_ids - dieselbe Teilung wie bei
`_parse_pasted_stock` (main_window), damit der Parser ohne Datenbank
pruefbar bleibt.
"""
import re

# Leere Slots, die EVE mitkopiert. Gross-/Kleinschreibung egal, und die
# Slot-Woerter wechseln (High/Med/Low/Rig/Subsystem/Service).
_LEER = re.compile(r"^\[\s*empty\s+.*slot\s*\]$", re.I)
# Kopfzeile: [Rumpf, Fitname]. Das ERSTE Komma trennt - ein Fitname darf
# selbst Kommas enthalten ("[Rifter, Tackle, v2]").
_KOPF = re.compile(r"^\[([^,\]]+),\s*(.*)\]$")
# Menge am Zeilenende: "Hobgoblin II x5". EVE schreibt grosse Zahlen mit
# Trennzeichen ("x1.000" / "x1,000" / "x1'000").
_MENGE = re.compile(r"^(.*?)\s+x\s*([\d.,']+)$", re.I)

# "VOLL" IST EINE SCHIFFSZAHL, KEINE STUECKZAHL (Nutzer 04.11.2026:
# "sagen wir, es hat ueber 250 Schiffe einer Doctrine ist sie 'Voll'
# (der Wert muss einstellbar sein) ... 1 Schiff ist nicht = 1 Munition /
# Wenn 1 Schiff 100 Schuss hat, gilt 'Markt ist voll' natuerlich nicht
# auch 250 Schuss / sondern 250000 Schuss ist = Markt voll").
# Das Ziel zaehlt also KOMPLETTE FITS; was das je Item bedeutet, sagt
# der Fit selbst (`fit_bedarf` mal Ziel). Am 03.11. war von "mind. 10x
# Stacks" die Rede - der Nutzer hat die Zahl am 04.11. praezisiert.
ZIEL_STANDARD = 250


def _menge(roh):
    """"1.000" -> 1000. Trennzeichen raus, dann Zahl - oder None."""
    _z = re.sub(r"[.,'\s]", "", str(roh or ""))
    try:
        return int(_z)
    except ValueError:                                   # pragma: no cover
        return None


def _zeile_posten(zeile):
    """Eine Fit-Zeile -> [(name, menge), ...]. Leere Slots: []."""
    z = (zeile or "").strip()
    if not z or _LEER.match(z):
        return []
    # Erst die Menge abtrennen, DANN das Komma teilen: "Hobgoblin II x5"
    # hat kein Komma, "Waffe, Ladung x100" waere eine Ladung mit Menge.
    m = _MENGE.match(z)
    anzahl = 1
    if m and _menge(m.group(2)) is not None:
        z, anzahl = m.group(1).strip(), _menge(m.group(2))
    if anzahl <= 0:
        return []
    teile = [p.strip() for p in z.split(",")]
    # Modul + geladene Ladung: beide zaehlen, die Ladung einmal je Modul.
    return [(p, anzahl) for p in teile if p]


def fits_lesen(text):
    """Einen ODER mehrere EFT-Fits aus einem Clipboard-Text lesen.

    Rueckgabe: Liste von {"schiff": str, "name": str,
    "posten": {name: menge}}. Mehrere Fits hintereinander sind erlaubt -
    jede neue Kopfzeile `[...]` beginnt einen neuen Fit. Text VOR der
    ersten Kopfzeile wird uebergangen (jemand kopiert gern eine
    Ueberschrift mit).

    Ein Rumpf, der auch als Modul vorkaeme, wird nicht doppelt gezaehlt:
    die Posten werden ueber den Namen ADDIERT, der Rumpf ist der erste
    Eintrag mit Menge 1."""
    fits = []
    akt = None
    for roh in (text or "").splitlines():
        z = (roh or "").strip()
        if not z:
            # DER WORTLAUT BLEIBT (emm946): Leerzeilen trennen im
            # EFT-Format die Slot-Gruppen - sie gehoeren zum Fit.
            if akt is not None:
                akt["eft"].append("")
            continue
        k = _KOPF.match(z)
        if k:
            akt = {"schiff": k.group(1).strip(),
                   "name": (k.group(2) or "").strip(),
                   "posten": {},
                   # emm946 (Nutzer 15.11.2026: "so ins clipboard
                   # kopieren, damit ich es ingame einfuegen kann und
                   # simulieren"): `posten` addiert ueber den Namen und
                   # verliert Slot-Reihenfolge und Modul/Ladung-Paare -
                   # daraus laesst sich kein Fit zurueckbauen. Darum
                   # wird der eingefuegte Text je Fit AUFGEHOBEN.
                   "eft": [z]}
            # DER RUMPF IST EIN POSTEN (s. Kopf des Moduls).
            akt["posten"][akt["schiff"]] = 1
            fits.append(akt)
            continue
        if akt is None:
            continue
        akt["eft"].append(z)
        for name, anzahl in _zeile_posten(z):
            akt["posten"][name] = akt["posten"].get(name, 0) + anzahl
    for f in fits:
        f["eft"] = "\n".join(f["eft"]).strip()
    return fits


def fit_aufloesen(fit, name_map):
    """{name: menge} -> ({type_id: menge}, [unbekannte Namen]).

    `name_map` ist `store.name_to_type_id()` (Name in Kleinschreibung ->
    type_id). Ein unbekannter Name wird GEMELDET, nicht verschluckt: eine
    Doctrine, von der die Haelfte fehlt, darf nicht als gedeckt
    durchgehen."""
    out, unbekannt = {}, []
    for name, menge in ((fit or {}).get("posten") or {}).items():
        tid = (name_map or {}).get(str(name).strip().lower())
        if tid is None:
            unbekannt.append(str(name))
            continue
        out[int(tid)] = out.get(int(tid), 0) + int(menge)
    return out, unbekannt


def doctrine_aus_text(name, text, name_map, ziel=ZIEL_STANDARD):
    """Fertige Doctrine aus einem eingefuegten Text.

    {"name", "ziel", "fits": [{"schiff","name","posten":[[tid,menge]..],
    "unaufgeloest":[...]}]}. Gespeichert werden type_ids UND der Klartext
    der unbekannten Namen - letztere, damit man sieht, was nicht
    aufgeloest werden konnte, statt es stillschweigend zu verlieren."""
    fits = []
    for f in fits_lesen(text):
        posten, unbekannt = fit_aufloesen(f, name_map)
        fits.append({"schiff": f.get("schiff") or "",
                     "name": f.get("name") or "",
                     "posten": [[t, q] for t, q in sorted(posten.items())],
                     "unaufgeloest": unbekannt,
                     "eft": f.get("eft") or ""})
    try:
        ziel = max(1, int(ziel))
    except (TypeError, ValueError):
        ziel = ZIEL_STANDARD
    return {"name": str(name or "").strip(), "ziel": ziel, "fits": fits}


def fit_text(doctrine):
    """Der eingefuegte EFT-Text eines Schiffs, so wie er kam (emm946) -
    zum Zurueckkopieren ins Spiel (Fitting-Fenster: aus der
    Zwischenablage importieren). Mehrere Fits durch eine Leerzeile
    getrennt. "" heisst: der Text wurde nie aufgehoben (Schiff stammt
    aus einer Fassung vor emm946) - dann wird NICHTS erfunden."""
    teile = [str(f.get("eft") or "").strip()
             for f in ((doctrine or {}).get("fits") or [])]
    return "\n\n".join(x for x in teile if x)


def fit_bedarf(fit):
    """{type_id: menge} fuer EIN Exemplar dieses Fits."""
    out = {}
    for paar in ((fit or {}).get("posten") or []):
        try:
            t, q = int(paar[0]), int(paar[1])
        except (TypeError, ValueError, IndexError):      # pragma: no cover
            continue
        out[t] = out.get(t, 0) + q
    return out


def doctrine_bedarf(doctrine):
    """{type_id: menge} fuer die GANZE Doctrine in Ziel-Stueckzahl."""
    try:
        ziel = max(1, int((doctrine or {}).get("ziel") or ZIEL_STANDARD))
    except (TypeError, ValueError):                      # pragma: no cover
        ziel = ZIEL_STANDARD
    out = {}
    for f in ((doctrine or {}).get("fits") or []):
        for t, q in fit_bedarf(f).items():
            out[t] = out.get(t, 0) + q * ziel
    return out


def doctrine_satz(doctrine):
    """{type_id: menge} fuer EINEN kompletten Satz der Doctrine - jeden
    Fit genau EINMAL, ohne das Ziel.

    Grundlage der Doctrine-Uebersicht (emm853, Nutzer 06.11.2026: "in
    Market Stock haette ich gerene eine auflistung aller Doctrine und
    infos dazu Baukosten/ Profit usw."): Baukosten und Profit werden je
    SATZ ausgewiesen, nicht je Zielmenge - 250 Schiffe x alles waere
    eine astronomische Zahl, die niemand vergleichen kann; einen Satz
    skaliert man im Kopf. Direkt aus den Fits summiert statt ueber
    doctrine_bedarf()//ziel - der Umweg "mal Ziel, dann durch Ziel"
    rechnet zweimal fuer nichts und hinge am Ziel-Feld, das hier gar
    keine Rolle spielt."""
    out = {}
    for f in ((doctrine or {}).get("fits") or []):
        for t, q in fit_bedarf(f).items():
            out[t] = out.get(t, 0) + q
    return out


def ordner_nachruesten(docs):
    """emm868 (Nutzer: "Doctrinen als Ueberordner erstellen ... darin
    sind dann die einzelnen Schiffe mit ihren Fittings"): jeder Eintrag
    traegt einen Ordnernamen. Alte Staende ohne "ordner" bekommen ihren
    eigenen Namen als Ordner - jede bisherige Karte wird damit ein
    Ordner mit ihrem Fit als erstem Schiff, nichts geht verloren."""
    for d in (docs or []):
        if not str(d.get("ordner") or "").strip():
            d["ordner"] = str(d.get("name") or "").strip() or "?"
    return docs


def ordner_gruppen(docs):
    """[(ordnername, [eintraege])] in Reihenfolge des ERSTEN Vorkommens
    - Kartenflaeche und Uebersicht gruppieren beide hierueber (eine
    Stelle). PUR, aa-prueftbar."""
    reihenfolge, je = [], {}
    for d in (docs or []):
        o = str(d.get("ordner") or d.get("name") or "?").strip() or "?"
        if o not in je:
            je[o] = []
            reihenfolge.append(o)
        je[o].append(d)
    return [(o, je[o]) for o in reihenfolge]


def alle_items(doctrinen):
    """{type_id: Gesamtbedarf} ueber ALLE Doctrinen (je mit ihrem Ziel).

    Das ist die Grundlage der zweiten Liste im Reiter: "eine komplette
    Liste aller Items von Allen Doctrinen" (Nutzer, 03.11.2026)."""
    out = {}
    for d in (doctrinen or []):
        for t, q in doctrine_bedarf(d).items():
            out[t] = out.get(t, 0) + q
    return out


def unbekannte(doctrinen):
    """Alle Namen, die beim Einlesen nicht aufgeloest werden konnten -
    einmal je Name, in der Reihenfolge ihres Auftretens."""
    out, gesehen = [], set()
    for d in (doctrinen or []):
        for f in ((d or {}).get("fits") or []):
            for n in (f.get("unaufgeloest") or []):
                if n not in gesehen:
                    gesehen.add(n)
                    out.append(n)
    return out
