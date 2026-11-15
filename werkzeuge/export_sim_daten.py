"""Alles, was eine BAUPLAN-RECHNUNG woanders nachvollziehbar macht.

NUTZER 05.11.2026: "kannst du das alles nicht selber Simulieren? muss ich
davon immer screenshots machen"

BERECHTIGT. Bis hierher kamen Zahlen-Befunde aus Screenshots: der
T3-Relic-Preis (20 Mio gegen 1,2 Mio), die Versuchszahl 5 gegen 6, die
Invention-Summe, die das Relic verschwieg. Alle drei haengen an DATEN, die
nur auf dem Rechner des Nutzers liegen - Marktpreise, Skills, Strukturen.
Die Rechnung selbst laeuft woanders und hatte sie nie.

DIESES WERKZEUG holt sie EINMAL und legt sie als eine Datei ab
(`berichte/sim_daten.json`). Damit laesst sich jede Bauplan-Frage
nachrechnen, ohne dass der Nutzer noch einmal etwas anklickt oder
fotografiert. Gegenstueck: `werkzeuge/sim_plan.py` rechnet damit.

ES ERGAENZT `exportiere_diagnose.py`, ersetzt es nicht: das bringt MENGEN
(Hangar, laufende Jobs, Kaeufe) und laesst Preise bewusst weg - hier ist
genau die Preis- und Einstellungs-Seite dran.

DRIN IST (alles NUR LESEND):
  * preise      je type_id sell_min/buy_max/sell_qty aus `market_snapshot`,
                nach Quelle getrennt (der Scan speichert je Hub eine)
  * adjusted    {type_id: Adjusted Price} von der oeffentlichen ESI -
                Grundlage der Jobgebuehren (EIV). Nur mit --esi.
  * average     dito, der serverweite Durchschnitt (Rueckfallpreis)
  * settings    NUR die Schluessel, die in die Rechnung eingehen
                (Whitelist unten) - Skills, Strukturen, ME/TE, Indizes
  * plaene      die gespeicherten Bauplaene (Name, Item, Menge, ME/TE,
                Decryptor- und Relic-Wahl) - ohne --plan nur die Namen
  * umgebung    Fassung, Zeit, Pfade der benutzten Datenbanken

NICHT DRIN, BEWUSST: Token (die liegen im Windows-Anmeldeinformations-
speicher, nicht hier), Charakternamen, Handelsjournal, ISK-Salden,
Vertraege. Die Charakter-IDs der Skill-Tabelle bleiben drin - ohne sie
laesst sich der Invention-Skillbonus nicht nachrechnen, und sie sind in
EVE oeffentlich.

AUFRUF:
    python werkzeuge\\export_sim_daten.py
    python werkzeuge\\export_sim_daten.py --esi
    python werkzeuge\\export_sim_daten.py --plan "Confessor"
"""
import argparse
import json
import os
import sqlite3
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from eve_trader import config                                   # noqa: E402

# WHITELIST STATT AUSSCHLUSSLISTE. Eine Ausschlussliste vergisst irgendwann
# einen neuen Schluessel, und dann steht etwas in der Datei, das dort nicht
# hingehoert. Hier kommt nur hinein, was eine Bauplan-Rechnung WIRKLICH
# braucht - alles andere bleibt zu Hause.
SETTINGS_WEISS = (
    # Material-/Zeiteffizienz je Kategorie
    "bau_me", "bau_te", "bau_me_component", "bau_te_component",
    "bau_me_t1hull", "bau_te_t1hull", "bau_me_fuel", "bau_te_fuel",
    "bau_me_tools", "bau_te_tools", "bau_me_aus_esi",
    # Jobkosten, Steuern, Indizes
    "bau_job_pct", "bau_facility_tax", "bau_scc", "bau_extra_cost",
    "bau_mfg_index", "bau_reaction_index", "bau_system_name",
    # Strukturen und Rollen
    "bau_structures", "bau_activity_struct", "bau_location",
    # Charaktere: Skills und Rollen (IDs, keine Namen)
    "bau_char_skills", "bau_react_skills", "bau_skills",
    "bau_invention_chars", "bau_copy_chars", "bau_char_slots",
    "bau_char_free", "bau_char_implant", "bau_char_reproc_implant",
    "bau_char_reproc_implant_hand",
    # Invention
    "bau_decryptor", "bau_invention", "bau_buy_datacores",
    "bau_buy_decryptors", "bau_inv_confidence",
    # Reprocessing / Einkauf
    "bau_buy_surplus", "bau_blacklist_names", "bau_blacklist_gruppen",
)

# Aus einem gespeicherten Plan nur das, was die Rechnung steuert.
PLAN_WEISS = ("id", "label", "item_name", "type_id", "qty", "me", "te",
              "invention", "decryptor_map", "relic_map", "own_bpc",
              "own_bpc_runs", "force", "prefer_build_if_owned", "owned_bp",
              "invention_char", "multi", "enden", "me_je_ende", "te_je_ende",
              "own_bpc_je_ende", "own_bpc_runs_je_ende",
              "blacklist_names", "blacklist_gruppen")


def _preise(db_pfad):
    """market_snapshot -> {quelle: {type_id: {sell, buy, sell_qty}}}.

    Nach QUELLE getrennt: der Scan legt je Handelsplatz eine eigene Zeile
    ab (seit der Quellen-Spalte, store._migrate_snapshot_source). Wer die
    zusammenwirft, mischt Jita-Preise mit denen einer Keepstar.
    """
    aus, alter = {}, None
    with sqlite3.connect(db_pfad) as c:
        c.row_factory = sqlite3.Row
        for r in c.execute("SELECT * FROM market_snapshot"):
            q = str(r["source"] or "")
            aus.setdefault(q, {})[int(r["type_id"])] = {
                "sell": r["sell_min"], "buy": r["buy_max"],
                "sell_qty": r["sell_qty"]}
            if r["updated_at"] and (alter is None or r["updated_at"] > alter):
                alter = r["updated_at"]
    return aus, alter


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--esi", action="store_true",
                   help="Adjusted/Average Prices von der oeffentlichen ESI "
                        "dazuholen (braucht Netz, keine Anmeldung)")
    p.add_argument("--plan", default=None,
                   help="Name (oder Teil davon) eines gespeicherten Plans - "
                        "nur dieser kommt mit allen Feldern mit")
    p.add_argument("--aus", default=None, help="Zieldatei")
    a = p.parse_args()

    db = config.db_path()
    ziel = a.aus or os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "berichte", "sim_daten.json")
    os.makedirs(os.path.dirname(ziel), exist_ok=True)

    daten = {"fassung": 1, "erstellt": time.strftime("%Y-%m-%d %H:%M:%S")}

    # --- Preise -------------------------------------------------------
    preise, alter = _preise(db)
    daten["preise"] = {k: {str(t): v for t, v in d.items()}
                       for k, d in preise.items()}
    daten["preise_stand"] = alter
    print(f"Preise: {sum(len(d) for d in preise.values())} Eintraege in "
          f"{len(preise)} Quelle(n)")

    # --- Einstellungen (Whitelist) ------------------------------------
    try:
        with open(config.settings_path(), "r", encoding="utf-8") as f:
            alle = json.load(f)
    except Exception as e:
        alle = {}
        print(f"settings.json nicht lesbar ({e}) - Abschnitt bleibt leer")
    daten["settings"] = {k: alle[k] for k in SETTINGS_WEISS if k in alle}
    print(f"Einstellungen: {len(daten['settings'])} von {len(SETTINGS_WEISS)} "
          f"Schluesseln vorhanden")

    # --- Gespeicherte Plaene ------------------------------------------
    plaene = alle.get("bau_saved_plans") or []
    namen = [str(x.get("label") or x.get("item_name") or x.get("id"))
             for x in plaene]
    daten["plan_namen"] = namen
    if a.plan:
        treffer = [x for x in plaene
                   if a.plan.lower() in str(x.get("label") or "").lower()
                   or a.plan.lower() in str(x.get("item_name") or "").lower()]
        daten["plaene"] = [{k: x[k] for k in PLAN_WEISS if k in x}
                           for x in treffer]
        print(f"Plaene: {len(treffer)} Treffer fuer {a.plan!r} "
              f"(von {len(plaene)})")
    else:
        daten["plaene"] = []
        print(f"Plaene: {len(plaene)} gespeichert - mit --plan NAME "
              f"kommt einer mit")

    # --- ESI-Preise (oeffentlich, keine Anmeldung) --------------------
    if a.esi:
        try:
            from eve_trader import esi
            mp = esi.market_prices()
            daten["adjusted"] = {str(k): v for k, v in (mp["adjusted"] or {}).items()}
            daten["average"] = {str(k): v for k, v in (mp["average"] or {}).items()}
            print(f"ESI: {len(daten['adjusted'])} Adjusted Prices, "
                  f"{len(daten['average'])} Durchschnittspreise")
        except Exception as e:
            print(f"ESI-Abruf fehlgeschlagen ({e}) - ohne Adjusted Prices")
    else:
        print("ESI: uebersprungen (mit --esi dazuholen)")

    # --- Umgebung ------------------------------------------------------
    try:
        from eve_trader import industry
        _ind = industry._db_path()
    except Exception:
        _ind = ""
    daten["umgebung"] = {"db": db, "industry_db": _ind,
                         "datenordner": config.app_data_dir()}

    with open(ziel, "w", encoding="utf-8") as f:
        json.dump(daten, f, ensure_ascii=False)
    print(f"\nGeschrieben: {ziel}")
    print(f"Groesse: {os.path.getsize(ziel) / 1e6:.1f} MB")
    print("Keine Token, keine Charakternamen, kein Handelsjournal darin.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
