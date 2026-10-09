"""Configuration, constants and persisted user settings."""
import json
import os

# ORDNERNAME FUER DIE NUTZERDATEN.
# BEWUSST EIN EIGENES WORT und nicht `APP_NAME` aus eve_trader/__init__.py,
# obwohl beide gerade gleich lauten: der Anzeigename darf sich jederzeit
# wieder aendern, der Datenordner NICHT einfach mit. Waeren sie gekoppelt,
# wuerde die naechste Umbenennung des Programms unbemerkt einen weiteren
# Umzug ausloesen - und jeder Umzug ist ein Risiko fuer die Daten.
DATENORDNER_NAME = "EVE Motor Market"

# Der Ordner hiess frueher so (alter Projektname). app_data_dir() benennt
# ihn EINMAL um. Dieser Eintrag darf NIE geloescht werden: sonst findet das
# Programm bei jedem, der noch nicht umgestiegen ist, seine Daten nicht mehr
# und startet scheinbar leer.
_ALTER_DATENORDNER_NAME = "EveTradeLedger"

# ---- Distribution ------------------------------------------------------------
# Paste YOUR Client-ID between the quotes to share the program with others.
# With it set, anyone who runs the app skips setup entirely and only logs in
# their own character. The Client-ID is NOT a secret (PKCE flow), so embedding
# it here is safe and intended.
EMBEDDED_CLIENT_ID = "6a34624f4e954d6e9f4e9c23aed3ff52"

# GitHub-Repository fuer die PROGRAMM-Update-Pruefung (Auftrag F4).
# Form: "KONTO/REPO". Der Kontoname darf kein Leerzeichen enthalten -
# aus "Peanut Motor" wird deshalb "PeanutMotor".
# Umbenennen ist spaeter unkritisch: GitHub leitet alte Adressen weiter,
# und geaendert werden muss nur diese eine Zeile.
GITHUB_REPO = "PeanutMotor/eve-motor-market"
# COMMUNITY-SERVER (Nutzer, Sitzung 17) - EINE Stelle; der Knopf in der
# Seitenleiste oeffnet ihn im Browser. Das Werkzeug verbindet sich NICHT
# selbst dorthin (deshalb in aa293 bei den Ausnahmen).
DISCORD_URL = "https://discord.gg/Atuqe6c2Rj"

# ---- EVE SSO / ESI endpoints ------------------------------------------------
SSO_AUTHORIZE = "https://login.eveonline.com/v2/oauth/authorize/"
SSO_TOKEN = "https://login.eveonline.com/v2/oauth/token"
ESI_BASE = "https://esi.evetech.net/latest"

# Market data
FORGE_REGION = 10000002          # The Forge
JITA_STATION = 60003760          # Jita IV - Moon 4 - Caldari Navy Assembly Plant

# Core access rights – these are always requested and known to work.
DEFAULT_SCOPES = [
    "publicData",
    "esi-wallet.read_character_wallet.v1",
    "esi-markets.read_character_orders.v1",
]
# Optional, only added when the user enables inventory import.
ASSETS_SCOPE = "esi-assets.read_assets.v1"
# Optional, only added when the user enables player-structure markets.
# EINE QUELLE FUER DIESEN EINEN SCOPE (Sitzung 19): die Struktur-Suche muss
# pruefen koennen, ob ein Charakter ihn WIRKLICH erteilt hat - sonst kann sie
# ein 403 nicht von "kein Andockrecht" unterscheiden. Als Positionsindex in
# STRUCTURE_SCOPES waere das still falsch, sobald jemand die Liste umsortiert.
STRUCTURE_READ_SCOPE = "esi-universe.read_structures.v1"
STRUCTURE_SCOPES = ["esi-markets.structure_markets.v1", STRUCTURE_READ_SCOPE]
# Optional, only added when the user enables opening items in the game client.
UI_SCOPE = "esi-ui.open_window.v1"
# Optional, only added when fees are derived from skills (auto-read levels+standings).
SKILL_SCOPES = ["esi-skills.read_skills.v1", "esi-characters.read_standings.v1",
                "esi-industry.read_character_jobs.v1",
                "esi-characters.read_blueprints.v1"]
# Optional, only added when the user enables implant-based time-bonus detection
# (Zainou 'Beancounter' Industry BX-80X etc.).
IMPLANT_SCOPE = "esi-clones.read_implants.v1"
# Optional, only added when the user enables the location hint (emm313,
# Nutzer 01.10.2026: Meldung, wenn der Trading-Charakter nicht am Hub ist).
# Name laut esi/esi-issues #1518 ("esi-location.read_location.v1"); der
# Endpunkt /characters/{id}/location/ liefert solar_system_id (immer),
# station_id bzw. structure_id (nur wenn angedockt).
LOCATION_SCOPE = "esi-location.read_location.v1"
# Optional, only added when the user enables corporation hangars (build only).
# JEDER EINZELNE MIT NAMEN, nicht als Positionsindex (dieselbe Lehre wie bei
# STRUCTURE_READ_SCOPE): der Bauplan muss je Charakter pruefen koennen, ob
# GENAU dieser Scope erteilt ist - sonst ist ein 403 nicht von "keine
# Director-Rolle" zu unterscheiden. Rollen laut ESI-Doku (16.09.2026):
# Assets/Blueprints/Divisions = Director, Jobs = Factory_Manager, Rollen-
# Abfrage = keine.
CORP_ASSETS_SCOPE = "esi-assets.read_corporation_assets.v1"
CORP_BLUEPRINTS_SCOPE = "esi-corporations.read_blueprints.v1"
CORP_DIVISIONS_SCOPE = "esi-corporations.read_divisions.v1"
CORP_JOBS_SCOPE = "esi-industry.read_corporation_jobs.v1"
CORP_ROLES_SCOPE = "esi-characters.read_corporation_roles.v1"
CORP_SCOPES = [CORP_ASSETS_SCOPE, CORP_BLUEPRINTS_SCOPE, CORP_DIVISIONS_SCOPE,
               CORP_JOBS_SCOPE, CORP_ROLES_SCOPE]

# ============================================================================
# HARTCODIERTE CCP-SPIELWERTE: GEBÜHREN (bewusste Ausnahme von der Grundregel
# "alles aus ESI/SDE" - diese Formeln sind CCP-Server-Logik und stehen WEDER
# in der SDE NOCH sind sie per ESI abrufbar; hartcodieren ist unvermeidbar).
#
# >>> WENN CCP DIE GEBÜHREN PER PATCH ÄNDERT, NUR HIER ANPASSEN. <<<
#
# Alle anderen Stellen im Tool lesen die EFFEKTIVEN Werte aus den Settings
# (sales_tax_pct / broker_fee_pct) - die werden bei fees_from_skills=True
# laufend aus DIESEN Formeln neu berechnet (MainWindow._sync_fees_to_hub und
# MainWindow.save_settings). Wer hier ändert, muss danach prüfen:
#   1. SALES_TAX_BASE / effective_sales_tax  (Basis-%, Reduktion je
#      Accounting-Level)
#   2. BROKER_FEE_BASE / effective_broker_fee  (Basis-%, Reduktion je
#      Broker-Relations-Level, Standings-Koeffizienten, Floor/Cap)
#   3. Die aus den Formeln ABGELEITETEN Defaults unten in DEFAULT_SETTINGS
#      (sales_tax_pct, broker_fee_pct) - passiert automatisch mit, weil sie
#      hier per Funktionsaufruf berechnet werden. NICHT wieder als freie
#      Zahlen eintragen.
#   4. Verwandte CCP-Policy-Werte in DEFAULT_SETTINGS, die NICHT aus diesen
#      Formeln kommen, aber derselben Klasse angehören (bei einem Gebühren-
#      Patch mitprüfen!): structure_broker_pct (0,5 % SCC-Aufschlag + Owner-%
#      im Upwell-Markt) und bau_scc (4 % SCC-Surcharge auf Industriejobs).
#   5. Struktur-Rollen-Boni in industry.py (_STRUCT_ROLE_ME etc.) - eigene,
#      bereits dokumentierte Ausnahme, siehe OFFENE_PUNKTE.md.
#
# VERIFIKATION (nur ingame möglich): 1 Buy-Order + 1 Verkauf an einer
# NPC-Station aufgeben und die angezeigte Gebühr gegen die Formel rechnen.
# Stand: siehe OFFENE_PUNKTE.md (Ausnahme-Block).
# ============================================================================
SALES_TAX_BASE = 7.5      # % before Accounting
BROKER_FEE_BASE = 3.0     # % before Broker Relations / standings (NPC station)


def effective_sales_tax(accounting_level: int) -> float:
    """Base 7.5 %, reduced 11 % per Accounting level (3.375 % at V)."""
    lvl = max(0, min(5, int(accounting_level)))
    return round(SALES_TAX_BASE * (1 - 0.11 * lvl), 3)


def effective_broker_fee(broker_level: int, faction_standing: float = 0.0,
                         corp_standing: float = 0.0) -> float:
    """NPC station: 3 % − 0.3 %/BrokerRelations − 0.03 %/faction − 0.02 %/corp,
    floored at 1 %. Uses unmodified standings (skills like Connections don't
    count). Negative standings raise the fee (capped at 5 %)."""
    lvl = max(0, min(5, int(broker_level)))
    fee = (BROKER_FEE_BASE - 0.3 * lvl
           - 0.03 * faction_standing - 0.02 * corp_standing)
    return round(max(1.0, min(5.0, fee)), 3)


# AUSGELIEFERTE STANDARDWERTE SIND NEUTRAL (Auftrag F1, Sitzung 11).
#
# Hier standen bis Sitzung 11 die Standings des Entwicklers zum Jita-4-4-Owner
# (corp und faction je knapp 10) und dazu Accounting V und Broker Relations V -
# also die Werte eines maximal geskillten Haendlers. Beim Erststart gegen ein
# leeres Verzeichnis bekam damit JEDER fremde Spieler diese Zahlen, ohne es
# zu merken: seine Margen waren still zu optimistisch, und 9,86 / 9,40 sind
# persoenliche Zahlen, die in einer oeffentlichen Fassung nichts verloren
# haben.
#
# NUTZER-ENTSCHEID: "zuerst muss man einen charakter verlinken." Die Werte
# kommen also NICHT mehr aus einer Annahme, sondern aus den echten Skills -
# und bis dahin steht hier der ungeskillte Grundfall. Der ist bewusst
# PESSIMISTISCH (7,5 % statt 3,375 % Steuer): wer ohne Charakter rechnet,
# sieht zu schlechte Margen statt zu guter. Ein Kauf, der sich nachher als
# besser herausstellt, ist verzeihlich - andersherum nicht.
_NEUTRALE_STANDINGS = {"corp": 0.0, "faction": 0.0}

# "KEIN DECRYPTOR" IST EIN GESPEICHERTER WERT, KEINE BESCHRIFTUNG.
# Er steht so in settings["bau_decryptor"], in den Bauplan-Zuordnungen und
# in gespeicherten Bau-Profilen. Er wird deshalb NICHT umbenannt - dieselbe
# Ueberlegung wie bei SERVICE in tokens.py: unter dem alten Namen liegt die
# Wahl aller bestehenden Nutzer. Angezeigt wird er uebersetzt, ueber
# ui.mw_basis.dec_anzeige.
# de_scan4: aus  (gespeicherter Wert, Anzeige laeuft ueber dec_anzeige)
# de_scan5: aus
KEIN_DECRYPTOR = "Kein Decryptor"
# de_scan5: an
# de_scan4: an

DEFAULT_SETTINGS = {
    "client_id": EMBEDDED_CLIENT_ID,   # baked-in id for distribution (optional)
    "callback_port": 8635,    # must match the callback URL you register
    # ZIEL-MARGE: ab dieser NETTO-Marge meldet das Portfolio "verkaufen".
    # 12 statt 20 (Nutzer, 15.09.2026): "das gibt den Nutzern eher das
    # Gefuehl, dass sie etwas verkaufen koennen". Bei 20 % blieb die Liste
    # der Verkaufs-Empfehlungen oft leer - wer nichts empfohlen bekommt,
    # haelt das Werkzeug fuer nutzlos, obwohl 12 % netto ein guter Handel
    # sind. GILT NUR FUER NEUE NUTZER: wer schon eine settings.json hat,
    # behaelt seinen eingestellten Wert (Standardwerte fuellen nur Luecken).
    "target_margin": 12.0,    # flag a position once net margin >= this
    # Effektive Arbeitswerte - werden bei fees_from_skills=True laufend aus den
    # Formeln oben überschrieben, sobald ein Charakter verlinkt und seine
    # Skills geladen sind. Defaults = Formel mit den Werten unten (KEINE
    # Skills, KEINE Standings), damit hier NIE eine freie Zahl steht, die zu
    # keiner Formel passt (alter Wert 4.5 war so ein Restwert).
    "sales_tax_pct": effective_sales_tax(0),
    "broker_fee_pct": effective_broker_fee(
        0, _NEUTRALE_STANDINGS["faction"], _NEUTRALE_STANDINGS["corp"]),
    "structure_broker_pct": 1.0,  # player Upwell market: 0.5% SCC surcharge + owner %
    # ---- fees derived from EVE skills (opt-in; NPC-station formulas) ----
    "fees_from_skills": True,      # an: sobald Skills da sind, gelten die echten
    "skill_accounting": 0,         # Accounting level 0-5 (sales tax)
    "skill_broker_relations": 0,   # Broker Relations level 0-5 (broker fee)
    # per-hub unmodified standings to the station owner (corp + faction). The
    # broker fee is computed per hub because each hub has a different owner.
    # LEER ausgeliefert - Standings sind persoenlich und kommen aus ESI.
    "hub_standings": {},
    "sell_mode": "relist",    # "relist" = Jita sell min, "instant" = Jita buy max
    "use_assets": True,       # real inventory import on by default (needs assets scope)
    # STANDARD AN (Nutzer, Sitzung 17): "player structures ... soll bitte
    # standard einstellung sein". Wirkt auf NEUE Installationen; wer den
    # Schalter schon gespeichert hat, behaelt seinen Wert.
    "use_structures": True,   # player-structure markets (needs structure scopes)
    "use_ui": True,           # opening items in the game client on by default (needs ui scope)
    # IMPLANTAT-ERKENNUNG STANDARD AN (Nutzer, 19.09.2026: "genau so wie es
    # bei mir ist als Standard fuer alle Nutzer"). Der Implantat-Scope wird
    # beim Verlinken mit angefragt. Gilt fuer NEUE Installationen.
    "use_implants": True,
    # STANDORT-HINWEIS (emm313). STANDARD AN seit emm316 (Nutzer 01.10.2026:
    # "character location standardmaessig auf on bitte") - ERSETZT "Standard
    # aus". Folge: der Scope wird beim Verlinken angefragt, er muss also in
    # der EVE-App stehen; der Einrichtungs-Assistent listet ihn deshalb mit.
    "use_location": True,
    # CORP-HANGAR ALS BAU-BESTAND (1.0.8). War STANDARD AUS (Entscheid
    # 14.09.2026, Regel 3). STANDARD AN seit 19.09.2026 (Nutzer-Entscheid,
    # s. oben) - ohne gewaehlte Division zaehlt trotzdem nichts, die Karte
    # sagt das ("Corp hangars are ON, but no division is selected"). Nur
    # fuers Bauen (Bauplan, Runplaner, Blueprints) - nicht Portfolio, nicht
    # Profits (Nutzer, 16.09.2026).
    "use_corp": True,
    # Welche der sieben Corp-Hangars (Divisions 1..7) zaehlen. STANDARD
    # ALLE SIEBEN (Nutzer-Entscheid 19.09.2026: "alle Corp Divisions auf
    # Standard ON") - ersetzt den Entscheid vom 14.09.2026 (leer, einzeln
    # anwaehlen). Wer einen Hangar fuer den Corp-Verkauf nutzt, nimmt ihn
    # in den Einstellungen raus. Gilt fuer NEUE Installationen.
    "corp_divisions": [1, 2, 3, 4, 5, 6, 7],
    "bau_me": 10,             # assumed blueprint material efficiency % (BPO research)
    "bau_te": 0,              # assumed blueprint time efficiency % (0..20)
    # ---- ME/TE je Item-Kategorie (Punkt: "wir kaufen sonst zu viel Material") ----
    # Endprodukt kommt weiterhin aus bau_me/bau_te oben (meist T2, oft 0/0 ab
    # Invention). Alles andere hat ein EIGENES Forschungslevel: T1-Komponenten/
    # -Hüllen/Fuel Blocks/Tools sind normalerweise voll ausgeforschte BPOs (10/10).
    # Reaktionen sind absichtlich NICHT dabei – die sind in EVE nie erforschbar.
    # TE-Defaults sind 20, nicht 10: ein voll erforschtes BPO hat ME 10 % UND
    # TE 20 % (das sind die jeweiligen Maxima). Die frühere 10 hier war eine
    # Altlast, die nie gewirkt hat - der Bauplan-Dialog setzte hart 20. Diese
    # Werte sind jetzt der GLOBALE STANDARD für neue Baupläne und werden vom
    # Dialog zurückgeschrieben, sobald der Nutzer die Regler dreht
    # (MainWindow._CAT_ME_TE_KEYS ist die zugehörige Attribut-Zuordnung).
    "bau_me_component": 10,   # Komponenten-Blaupausen ME %
    "bau_te_component": 20,   # Komponenten-Blaupausen TE %
    "bau_me_t1hull": 10,      # T1-Schiffshüllen (Invention-Basis) ME %
    "bau_te_t1hull": 20,      # T1-Schiffshüllen TE %
    "bau_me_fuel": 10,        # Fuel-Block-Blaupausen ME %
    "bau_te_fuel": 20,        # Fuel-Block-Blaupausen TE %
    "bau_me_tools": 10,       # Tools (R.A.M. u.Ä.) ME %
    "bau_te_tools": 20,       # Tools (R.A.M. u.Ä.) TE %
    # Invention-Einkauf: Standard AN. Es wird ohnehin nur gekauft, was FEHLT -
    # der ESI-/eingefuegte Bestand wird vorher abgezogen (s. "covered_by_stock"
    # in _add_build_materials_to_cart). Ein voller Brutto-Einkauf ist also
    # nicht moeglich.
    "bau_buy_datacores": True,    # Datacores in die Einkaufsliste
    "bau_buy_decryptors": True,   # Decryptoren in die Einkaufsliste
    "bau_buy_inv_default_applied": False,   # Marker der Einmal-Migration
    "bau_cat_me_te_reset_applied": False,   # Marker: Kategorie-ME/TE-Aufraeumung
    # Fracht: BEIDE Kostenarten zaehlen immer und werden addiert (Frachtdienst
    # nach ISK/m3 + Pauschale je eigener Fahrt). "bau_transport_mode" ist damit
    # Geschichte - der Schluessel bleibt nur fuer die Einmal-Migration stehen.
    "fees_char_id": None,                 # Charakter fuer Tax/Broker-Berechnung
    "bau_freight_in_decision": True,       # ISK/m3 auf den Kaufpreis aufschlagen
    "bau_transport_both_applied": False,   # Marker der Einmal-Migration
    "bau_rollen_vorbelegt": False,         # Marker: Rollen-Haken nachgezogen
    "bau_job_pct": 3,         # job-cost overhead % on material value
    "bau_reactions": True,    # build T2 reaction intermediates yourself
    "bau_invention": True,    # include T2 invention cost (datacores / success chance)
    "bau_struct": "raitaru",  # manufacturing structure type (role bonus: cost/time)
    "bau_me_rig": 2,          # 0=none, 1=T1, 2=T2 material-efficiency rig
    "bau_te_rig": 2,          # 0=none, 1=T1, 2=T2 time-efficiency rig (for build time)
    "bau_security": 1.0,      # rig multiplier: 1.0 high · 1.9 low · 2.1 null/WH
    "bau_location": "npc",    # manufacturing structure (structure_id) or "npc"
    "bau_system_id": 0,       # solar system of the build location (for the cost index)
    "bau_system_name": "",    # its name (display)
    "bau_mfg_index": 0.0,     # manufacturing system cost index (live from ESI)
    "bau_reaction_index": 0.0,  # reaction system cost index (live from ESI)
    "bau_role_bonus": 0.0,    # structure manufacturing job-cost role bonus % (e.g. 3)
    "bau_facility_tax": 0.25,  # facility tax % set by the structure owner
    "bau_decryptor": KEIN_DECRYPTOR,  # invention decryptor choice
    "bau_parallel_chars": 1,   # build characters working in parallel (time estimate)
    "bau_buy_surplus": 0,      # extra % of materials to buy (safety, rounded up)
    "bau_blacklist_names": [],  # exact item names to never build (paste list)
    # REPROCESSING-SCHALTER (1.0.9) - plan-eigen wie die Blacklist: ein
    # neuer, ungespeicherter Bauplan oeffnet mit BEIDEN AUS (Nutzer
    # 19.09.2026), ein gespeicherter Plan bringt seinen Stand mit.
    "bau_reprocess_on": False,   # Weg B: Compressed Ore statt Minerale
    "bau_unrefined_on": False,   # Weg A: Unrefined-Reaktionen
    # Reprocessing-Steuer der Struktur in Prozent (emm392, Nutzer
    # 04.10.2026) - Prozent vom Wert der Ausgaenge, 0 = keine.
    "bau_reproc_steuer": 0.0,
    # JE STRUKTUR gemerkte Reprocessing-Steuer (emm496): {struct_id|"npc":
    # Prozent}. Der alte globale Wert oben bleibt nur als Migrationsquelle.
    "bau_reproc_steuer_map": {},
    # Preisverlauf: zuletzt angesehenes Item [type_id, Name] - beim Oeffnen
    # des Tabs steht sofort ein Graph (18.09.2026).
    "mk_last_item": None,
    # VERKAUFSLISTE: Items mit offener eigener Kauf-Order ausblenden.
    # Standard AUS (Nutzer-Befund 22.09.2026): bis dahin filterte die
    # Liste das IMMER und still - bei ihm fielen 13 von 14 verkaufs-
    # bereiten Positionen heraus, waehrend die Kachel "Ready to sell"
    # weiter 14 zeigte. Wer filtern will, schaltet es im Tools-Menue ein.
    "sell_hide_active_orders": False,
    # FRACHT (Nutzer 29.09.2026): ISK je m3 fuer den Transport. EIN Wert fuer
    # Regional Trading UND Verkaufsliste. 0 = keine Fracht (Standard).
    # Fracht bekommen nur Stueck, die laut Wallet NICHT am Verkaufs-Hub
    # gekauft wurden (`market.fracht_je_item`).
    "fracht_isk_m3": 0,
    # Items, fuer die der Nutzer per Rechtsklick "keine Fracht" gewaehlt hat.
    "fracht_aus_items": [],
    # Die Karte "Endprodukte dieses Buendels" im Multi-Bauplan laesst sich
    # einklappen (Nutzer 23.09.2026) - standardmaessig OFFEN, weil dort die
    # Mengen und ME/TE jedes Endes geschraubt werden.
    "bau_multi_enden_offen": True,
    # ZIELZEIT JE STUFE IM RUNPLANER (Nutzer 24.09.2026: "abends
    # einloggen, Runs starten auf 23 h, am naechsten Tag Components").
    # {stage: Stunden}; 0 oder fehlend = automatisch (nur straffen, die
    # Stufe wird nicht laenger als noetig). `..._std` gilt fuer jede
    # Stufe ohne eigenen Wert.
    "bau_runplan_ziel": {},
    "bau_runplan_ziel_std": 0,
    # GANZE GRUPPEN nie bauen und nie kaufen (Nutzer, Sitzung 20).
    # Werte = die Gruppen des Materialien-Reiters, s. _MATERIAL_GRUPPEN.
    "bau_blacklist_gruppen": [],
    # Zuletzt sortierte Reihenfolge von "Meine Bauplaene" (Plan-IDs).
    # Damit stehen die Karten beim Oeffnen gleich richtig, statt sichtbar
    # umzuspringen, sobald der ESI-Fortschritt eintrifft.
    "bau_plan_sortierung": [],
    # EIGENE REIHENFOLGE DER BAUPLAN-KARTEN (Nutzer, 15.09.2026: "Bauplaene
    # selber anordnen ... die eigene Anordnung bleibt gespeichert beim
    # Schliessen und wieder Oeffnen, auch bei einem Update").
    # Zwei getrennte Schluessel mit Absicht: `bau_plan_sortierung` merkt sich
    # die zuletzt AUTOMATISCH sortierte Folge, damit beim Oeffnen nichts
    # sichtbar umspringt. Wuerde die Handsortierung dort hineinschreiben,
    # ueberschriebe der naechste ESI-Lauf sie wieder.
    # Beides liegt in settings.json im Nutzerordner, nicht im Programm - ein
    # Update ersetzt nur die .exe und laesst die Datei stehen.
    "bau_plan_manuell": False,      # Handsortierung an/aus
    "bau_plan_reihenfolge": [],     # Plan-IDs in der Reihenfolge des Nutzers
    # ZUGEKLAPPTE Multi-Baupläne in "Meine Baupläne" (Ordnerstruktur).
    # LEER = alle offen (Nutzer 26.09.2026: "Multiplans standard ausgeklappt,
    # es sei denn man schliesst das Dropdown"). Ersetzt `bau_multi_offen`
    # (Standard zu, 20.09.2026); der alte Schlüssel wird nicht mehr gelesen.
    "bau_multi_zu": [],
    # Zugeklappte Karten im Invention-Reiter (Blaupausen-IDs), Standard
    # offen (Nutzer 26.09.2026: "kompakter, verbraucht zu viel Platz").
    "bau_inv_zu": [],
    # GILT SEINE REIHENFOLGE? (Nutzer, 15.09.2026: "die Reihenfolge bleibt,
    # aber dann fuehren wir einen Knopf ein 'Nach Fortschritt sortieren'").
    # BEWUSST GETRENNT von `bau_plan_manuell`: der sagt nur, ob man gerade
    # ZIEHEN kann. Vorher haben beide dasselbe bedeutet - das Ausschalten
    # des Anordnen-Modus warf die Handarbeit sofort wieder um, und genau das
    # nannte er sinnlos. Jetzt endet die eigene Folge nur auf ausdruecklichen
    # Klick.
    "bau_plan_eigene_folge": False,
    # Mengenfeld im Bauplan in RUNS statt Stueck zeigen (Discord-Wunsch,
    # 16.09.2026). Wirkt nur bei Produkten mit mehr als 1 Stueck je Run.
    "bau_qty_in_runs": False,
    # Verdeckte Kennzahlen (Portfolio/Gewinne) - fuer Streams und
    # Screenshots. Nur die ANZEIGE, gerechnet wird unveraendert.
    "kpi_zensiert": [],
    "bau_sell_hub": 0,         # optimizer sell-hub station_id
    "bau_transport_m3": 350000,   # cargo capacity per trip for the buy-list (m3, ~1 jump freighter)
    "bau_transport_mode": "per_m3",  # "per_m3" (ISK/m3) or "per_trip" (flat/fuel per trip)
    "bau_transport_rate": 0.0,    # ISK per m3 (mode "per_m3")
    "bau_transport_trip_cost": 0.0,  # ISK flat cost per trip, e.g. fuel (mode "per_trip")
    # Frei eingebbarer Einmalbetrag je Bauplan (gekaufte BPCs, Gebuehren) -
    # geht vom Gewinn ab, nicht in die Baukosten je Stueck.
    "bau_extra_cost": 0.0,
    "bau_saved_plans": [],     # saved named build plans
    "bau_structures": [],      # player structures with rigs (Struktur-Fitting)
    "bau_activity_struct": {}, # activity -> structure id mapping
    "bau_scc": 0.04,           # SCC surcharge (CCP policy value, editable)
    "bau_build_chars": [],     # chars for manufacturing (components + end)
    "bau_reaction_chars": [],  # chars for reactions
    "bau_invention_chars": [], # chars for invention
    "bau_copy_chars": [],      # chars for blueprint copying
    "bau_component_bp": 1,     # copies of each component blueprint you own (split cap)
    "bau_reaction_bp": 1,      # copies of each reaction blueprint you own (split cap)
    "bau_char_roles": {},      # {char_id: [role keys]} for multi-char build scheduling
    "bau_char_slots": {},      # {char_id: [max_mfg, max_react]} from skills
    "bau_char_free": {},       # {char_id: [free_mfg, free_react]} from active ESI jobs
    "bau_char_skills": {},     # {char_id: {skill_id: level}} cached per build character
    "bau_character": 0,        # character whose manufacturing skills apply (0 = none)
    "bau_skills": {},          # cached manufacturing skill levels {skill_id: level}
    "bau_react_character": 0,  # character whose reaction skills apply (0 = none)
    "bau_react_skills": {},    # cached reaction skill levels {skill_id: level}
    "bau_blacklist": [],       # categories to NEVER build (always buy)
    "tx_cache_minutes": 5,    # how long imported transactions stay fresh (war 30 -
                               # neue Transaktionen sollten deutlich schneller
                               # sichtbar sein; 5 Min ist immer noch ein sinnvoller
                               # Puffer gegen zu häufige ESI-Anfragen bei jedem Klick
                               # auf "Alles aktualisieren")
    # ---- monetisation (local accounting; server validation comes later) ----
    "test_mode": True,        # unlimited Order Marks + everything unlockable (for the dev)
    "credits": 0,             # Order Marks balance
    "subs": {},               # {tab_key: unix expiry timestamp}
    "master": False,          # unlocked once via the secret master code
    "sim_slave": False,       # master flips this on to test the friend experience
    "trial_until": 0,         # unix ts a redeemed trial runs until (whole tool)
    "redeemed_codes": [],     # nonces of trial codes already used on this machine
}

# ----- Order Marks economy -------------------------------------------------
CREDIT_NAME = "Order Marks"        # bilingual DE/EN; rename here only
CREDIT_ABBR = "OM"
ISK_PER_CREDIT = 1_000_000         # 1 OM = 1,000,000 ISK  → 1000 OM = 1B ISK
SUB_DAYS = 30                      # a tab subscription lasts this many days
# de_scan5: aus  (Eigenname einer Corporation im Spiel, wird nicht uebersetzt)
CORP_NAME = "Der Handelsorden"     # ISK transfers go to this in-game corp
# de_scan5: an

# unlockable (paid) tabs → cost in Order Marks per SUB_DAYS


def app_data_dir() -> str:
    """Per-user writable directory for settings + database.

    UMZUG (Sitzung 11, Nutzer: "es soll ueberall EVE Motor Market heissen"):
    der Ordner hiess bis dahin "EveTradeLedger", nach dem alten Projektnamen.
    Er wird EINMAL umbenannt, sobald das Programm das erste Mal in der neuen
    Fassung startet.

    DIE WICHTIGSTE REGEL DABEI: geht der Umzug schief, wird WEITER MIT DEM
    ALTEN ORDNER gearbeitet. Ein Programm, das nach einem misslungenen Umzug
    einen frischen, leeren Ordner anlegt, sieht fuer den Nutzer so aus, als
    waeren Handelsjournal, Einstellungen und alle gespeicherten Bauplaene
    verschwunden - und er merkt es erst, wenn er nachsieht. Lieber der alte
    Name als verlorene Daten.
    """
    if os.name == "nt":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.join(os.path.expanduser("~"), ".local", "share")
    neu = os.path.join(base, DATENORDNER_NAME)
    # SCHNELLWEG (Ladezeit-Messung des Nutzers, 27.09.2026): jede
    # Datenbank-Verbindung fragt hier nach dem Ordner - 27'000 Mal beim
    # Start, jedes Mal exists + isdir + isdir + makedirs (unter Windows ein
    # echter mkdir-Versuch). Steht der NEUE Ordner schon da, ist die Antwort
    # immer dieselbe: EIN isdir genuegt. Fehlt er (erster Start, Umzug,
    # von Hand geloescht), laeuft der volle Weg darunter wie bisher.
    if _DATENORDNER_BEKANNT.get(neu) and os.path.isdir(neu):
        return neu
    alt = os.path.join(base, _ALTER_DATENORDNER_NAME)
    if not os.path.exists(neu) and os.path.isdir(alt):
        try:
            # os.rename im selben Verzeichnis: EIN Schritt, kein Kopieren.
            # Entweder der Ordner heisst danach neu, oder es hat sich nichts
            # geaendert - es kann kein halb umgezogener Zustand entstehen.
            os.rename(alt, neu)
        except Exception:
            # Nichts weiter tun: die Zeile darunter faengt diesen Fall
            # ohnehin ab (alt ist noch da, neu nicht -> alt wird
            # zurueckgegeben). Ein zweiter Rueckgabeweg hier sah nach
            # Absicherung aus, war aber wirkungslos - eine Rotprobe hat es
            # aufgedeckt: die Mutation "except: pass" aenderte nichts.
            pass
    if os.path.isdir(alt) and not os.path.isdir(neu):
        # HIER haengt die Zusage "misslungener Umzug -> alte Daten
        # weiterbenutzen". Gilt auch, wenn der neue Ordner nachtraeglich
        # von Hand geloescht wurde.
        return alt
    os.makedirs(neu, exist_ok=True)
    _DATENORDNER_BEKANNT[neu] = True
    return neu


_DATENORDNER_BEKANNT = {}


def db_path() -> str:
    return os.path.join(app_data_dir(), "ledger.db")


def settings_path() -> str:
    return os.path.join(app_data_dir(), "settings.json")


def load_settings() -> dict:
    path = settings_path()
    data = dict(DEFAULT_SETTINGS)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data.update(json.load(f))
        except Exception:
            # NICHT STILL UEBERGEHEN (Nutzer-Befund Sitzung 11: auf einem
            # zweiten Rechner standen ploetzlich die Vorgaben statt der
            # eigenen Werte). Vorher stand hier `pass`: eine unlesbare
            # Datei wurde ignoriert, das Programm lief mit den Vorgaben
            # weiter - und beim naechsten Speichern war die kaputte Datei
            # ueberschrieben. Damit sind Gebuehren, Hub-Standings und alle
            # Einstellungen endgueltig weg, ohne dass je etwas gesagt wurde.
            # Jetzt wird sie ZUERST beiseitegelegt; wiederherstellen kann
            # man dann von Hand, und die Oberflaeche sagt Bescheid.
            _rette_defekte_settings(path)
    return _nach_migrationen(data)


# Wohin die unlesbare Datei gerettet wurde - die Oberflaeche liest das aus
# und sagt es dem Nutzer. None, solange nichts passiert ist.
defekte_settings_kopie = None


def _rette_defekte_settings(path):
    """Unlesbare settings.json beiseitelegen statt sie zu verlieren."""
    global defekte_settings_kopie
    import time as _t
    ziel = f"{path}.defekt-{_t.strftime('%Y%m%d-%H%M%S')}"
    try:
        os.replace(path, ziel)
        defekte_settings_kopie = ziel
    except Exception:
        # Selbst das Umbenennen kann scheitern (Datei in Benutzung). Dann
        # lieber gar nichts tun: eine unlesbare Datei ist immer noch besser
        # als eine geloeschte.
        defekte_settings_kopie = path


_PLAN_NAME_SCHMUTZ = "\U0001F9EA\u2697\ufe0f \t"


def plan_name_bereinigen(name: str) -> str:
    """Emoji-Vorsatz (Reagenzglas u.ae.) und Leerraum vom Plan-Namen."""
    return (name or "").strip(_PLAN_NAME_SCHMUTZ).strip()


def buendel_quellen_freigeben(plans, quellen_ids):
    """Quellen eines Buendels auftauen und ihre Reservierung loesen.
    Rueckgabe (freigegeben, aufgetaut) als Listen von Plan-Namen.

    EINE Stelle fuer beide Speicherwege (26.09.2026). Bis dahin tat das nur
    "In Meine Bauplaene speichern" im frueheren Multi-Buildplaner-Dialog
    (`_multi_plan_speichern`, ausgebaut 26.09.2026); wer stattdessen "Bauplan
    oeffnen" waehlte und das Buendel aus dem Bauplan-Dialog speicherte
    (`_save_plan`), liess seine Quellen eingefroren zurueck - mit
    Einkaufs-Schnappschuessen von frueher.
    Nutzer-Befund (karten_bericht): Ametat II / Flycatcher / Stork standen
    weiter mit ihren Einzel-Einkaeufen vom 10./11.09. da, obwohl alles ueber
    das Buendel vom 23.09. gekauft war. Ein eingefrorener Einzelplan rechnet
    nicht mehr; ab dem Buendeln rechnet das Buendel fuer ihn - also weg mit
    Schnappschuss und Schloss (Entscheid C, Korrektur 20.09.2026)."""
    frei, aufgetaut = [], []
    _q = set(quellen_ids or [])
    for x in plans or []:
        if x.get("id") not in _q:
            continue
        if x.get("reserve"):
            x["reserve"] = False
            frei.append(str(x.get("label") or ""))
        if x.get("frozen"):
            x["frozen"] = None
            aufgetaut.append(str(x.get("label") or ""))
    return frei, aufgetaut


def buendel_quellen_nachziehen(plans):
    """Alle Quellen aller OFFENEN Buendel freigeben (Migration fuer Plaene,
    die ueber den Bauplan-Dialog gespeichert wurden, s. oben). -1 ist
    industry.BUENDEL_ID; config darf industry nicht importieren.
    Abgeschlossene Buendel (done_manual) lassen ihre Quellen in Ruhe.
    Rueckgabe: Namen der veraenderten Quellen."""
    aus = []
    for p in plans or []:
        try:
            if int(p.get("type_id", 0) or 0) != -1 or p.get("done_manual"):
                continue
        except (TypeError, ValueError):
            continue
        frei, auf = buendel_quellen_freigeben(plans, p.get("quellen") or [])
        aus += [n for n in frei + auf if n not in aus]
    return aus


# BAU-PROFIL = NUR EINSTELLUNGEN (03.10.2026, gefunden in der settings.json des
# Nutzers): ein Profil speicherte ALLE "bau_*"-Schluessel - auch die
# gespeicherten Bauplaene (20 MB im Profil "WipeOut/A-DD Pocket"), Jobs,
# Skills und Reihenfolgen. "Profil laden" haette damit die aktuellen Plaene
# still durch einen alten Stand ersetzt (Fortschritt, Haken, Reservierungen
# weg). Ab jetzt: ein Profil traegt nur Einstellungen; Zustand und
# abgerufene Daten bleiben draussen - beim Speichern, beim Laden (alte
# Profile) und einmal per Migration.
BAU_PROFIL_OHNE = frozenset({
    "bau_profiles", "bau_saved_plans", "bau_live_jobs", "bau_owned_bp",
    "bau_char_skills", "bau_char_slots", "bau_char_free", "bau_char_free_ts",
    "bau_char_roles", "bau_char_implant", "bau_char_reproc_implant",
    "bau_char_reproc_implant_hand", "bau_structures", "bau_struct_scan_ts",
    "bau_online_windows", "bau_calendar", "bau_inv_zu", "bau_rollen_vorbelegt",
})


def bau_profil_schluessel(k) -> bool:
    """Gehoert der Schluessel in ein Bau-Profil? Nur Einstellungen - keine
    Plaene, keine Plan-Reihenfolge/-Ansicht, keine abgerufenen Daten, keine
    Migrations-Marker."""
    k = str(k)
    return (k.startswith("bau_") and k not in BAU_PROFIL_OHNE
            and not k.startswith(("bau_plan_", "bau_multi_"))
            and not k.endswith("_applied"))


def bau_profil_bereinigen(snap) -> dict:
    """Ein Profil (auch ein altes) auf seine Einstellungen reduzieren."""
    return {k: v for k, v in (snap or {}).items() if bau_profil_schluessel(k)}


ARCHIV_FRIST_SEK = 30 * 86400     # erledigte Plaene aelter als 30 Tage


def bauplan_archiv_path() -> str:
    return os.path.join(app_data_dir(), "bauplan_archiv.json")


def bauplan_archiv_anzahl() -> int:
    """Wie viele Plaene liegen im Archiv? 0 bei fehlender/unlesbarer Datei."""
    try:
        with open(bauplan_archiv_path(), encoding="utf-8") as f:
            return len(json.load(f) or [])
    except Exception:
        return 0


def archiv_faellig(plans, jetzt):
    """Welche Plaene duerfen ins Archiv? Rein (emm388, 04.10.2026, Nutzer:
    "solange du Bauplaene nicht einfach loeschst, ist es okay").

    Faellig: von Hand abgeschlossen (`done_manual`) und seit mehr als 30
    Tagen (`done_ts`). NIE faellig: ein Plan, den ein VERBLEIBENDER Plan als
    Quelle (`quellen`) nennt - sonst verloere ein offenes Buendel sein
    Mitglied (bzw. "Reopen" sein Ziel). Die Pruefung laeuft, bis sich nichts
    mehr aendert: faellt ein Buendel heraus, bleiben auch seine Mitglieder."""
    plans = list(plans or [])
    s = set()
    for p in plans:
        try:
            ts = float(p.get("done_ts") or 0)
        except (TypeError, ValueError):
            ts = 0.0
        if p.get("done_manual") and ts and (jetzt - ts) >= ARCHIV_FRIST_SEK:
            s.add(str(p.get("id")))
    while True:
        halter = set()
        for p in plans:
            if str(p.get("id")) in s:
                continue
            for q in (p.get("quellen") or []):
                halter.add(str(q))
        neu = s - halter
        if neu == s:
            return [p for p in plans if str(p.get("id")) in s]
        s = neu


def plaene_archivieren(data, jetzt=None) -> int:
    """Faellige erledigte Plaene aus den Settings in bauplan_archiv.json
    VERSCHIEBEN (nie loeschen). Erst wenn die Archivdatei sicher geschrieben
    ist, verlassen die Plaene die Settings; ist die vorhandene Archivdatei
    unlesbar, passiert NICHTS (lieber eine grosse settings.json als ein
    verlorener Plan). Gibt die Zahl der verschobenen Plaene zurueck."""
    import time as _t
    jetzt = jetzt if jetzt is not None else _t.time()
    plans = data.get("bau_saved_plans") or []
    weg = archiv_faellig(plans, jetzt)
    if not weg:
        return 0
    pfad = bauplan_archiv_path()
    alt = []
    if os.path.exists(pfad):
        try:
            with open(pfad, encoding="utf-8") as f:
                alt = json.load(f) or []
            if not isinstance(alt, list):
                return 0
        except Exception:
            return 0
    for p in weg:
        q = dict(p)
        q["archiviert_ts"] = jetzt
        alt.append(q)
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix="archiv-", suffix=".tmp", dir=app_data_dir())
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(alt, f, separators=(",", ":"))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, pfad)
    except Exception:
        try:
            os.remove(tmp)
        except OSError:
            pass
        return 0
    ids = {str(p.get("id")) for p in weg}
    data["bau_saved_plans"] = [p for p in plans if str(p.get("id")) not in ids]
    for k in ("bau_plan_reihenfolge", "bau_plan_eigene_folge", "bau_plan_sortierung"):
        if isinstance(data.get(k), list):
            data[k] = [x for x in data[k] if str(x) not in ids]
    return len(weg)


def _nach_migrationen(data: dict) -> dict:
    # Migration: tx_cache_minutes war nie über die UI einstellbar - jeder
    # gespeicherte Wert von genau 30 ist also der alte hartkodierte Default,
    # nicht eine bewusste Nutzerwahl. Auf den neuen, kürzeren Default heben,
    # damit neue Transaktionen schneller sichtbar werden.
    if data.get("tx_cache_minutes") == 30:
        data["tx_cache_minutes"] = DEFAULT_SETTINGS["tx_cache_minutes"]
    # Migration (Nutzer-Wunsch: "in die Standardisierung aufnehmen"): die
    # beiden Invention-Einkaufshaken sind ab jetzt Standard AN. Ein frueher
    # gespeichertes False haette den neuen Default fuer immer verdeckt.
    # GENAU EINMAL nachziehen, per Marker - danach gilt wieder ausschliesslich
    # die Nutzerwahl (sonst koennte man sie nie wieder ausschalten).
    _migrated = False
    if not data.get("bau_buy_inv_default_applied"):
        data["bau_buy_datacores"] = True
        data["bau_buy_decryptors"] = True
        data["bau_buy_inv_default_applied"] = True
        _migrated = True
    # Migration: die Kategorie-ME/TE ("ANDERE BLAUPAUSEN") waren kurzzeitig
    # "letzter Reglerwert wird globaler Standard". Ein versehentlicher
    # Pfeilklick konnte damit z.B. TE 19 % zum Standard fuer ALLE kuenftigen
    # Plaene machen. Nutzer-Entscheid: Standard ist fest 10/20, Abweichungen
    # gehoeren in den EINZELNEN Bauplan (wird dort mitgespeichert). Einmalig
    # auf die Defaults zuruecksetzen, damit keine verirrten Werte kleben.
    if not data.get("bau_cat_me_te_reset_applied"):
        for _k in ("bau_me_component", "bau_te_component",
                   "bau_me_t1hull", "bau_te_t1hull",
                   "bau_me_fuel", "bau_te_fuel",
                   "bau_me_tools", "bau_te_tools"):
            data[_k] = DEFAULT_SETTINGS[_k]
        data["bau_cat_me_te_reset_applied"] = True
        _migrated = True
    # Migration: frueher galt ENTWEDER ISK/m3 ODER Pauschale/Fahrt (Dropdown).
    # Jetzt zaehlen beide. Ein liegengebliebener Wert der damals INAKTIVEN
    # Variante wuerde ab sofort ploetzlich Kosten verursachen, die der Nutzer
    # nie gewollt hat - deshalb einmalig auf 0 setzen.
    if not data.get("bau_transport_both_applied"):
        _m = data.get("bau_transport_mode")
        if _m == "per_trip":
            data["bau_transport_rate"] = 0.0
        elif _m == "per_m3":
            data["bau_transport_trip_cost"] = 0.0
        data["bau_transport_both_applied"] = True
        _migrated = True
    # ROLLEN-HAKEN FUER SCHON VERKNUEPFTE CHARAKTERE (Sitzung 19).
    # Wer seine Charaktere vor dieser Fassung verknuepft hat, hat womoeglich
    # gar keine Rollen gesetzt - dann bleiben Runplaner UND Blueprints-Tabelle
    # leer, ohne dass irgendwo steht warum. Neue Charaktere bekommen die Haken
    # jetzt beim Verknuepfen (_bau_rollen_vorbelegen); die bestehenden holt
    # diese Einmal-Migration nach.
    #
    # NUR wenn NICHTS gesetzt ist. Wer bewusst einzelne Charaktere abgewaehlt
    # hat, hat mindestens einen drin - dem wird hier nichts umgestellt.
    if not data.get("bau_rollen_vorbelegt"):
        _rollen = ("bau_build_chars", "bau_reaction_chars",
                   "bau_invention_chars", "bau_copy_chars")
        if not any(data.get(_k) for _k in _rollen):
            try:
                from . import store as _st
                _cids = [int(c["character_id"]) for c in _st.list_characters()]
            except Exception:
                _cids = []
            if _cids:
                for _k in _rollen:
                    data[_k] = list(_cids)
        data["bau_rollen_vorbelegt"] = True
        _migrated = True
    # BESTANDS-POOL FUER ROLLEN JE PLAN (emm426): einmalig die heutigen
    # Rollen-Charaktere merken - ab jetzt koennen Plaene eigene Rollen
    # tragen, ihr Bestand soll aber fuer jeden Plan weiter zaehlen.
    if "bau_rollen_pool" not in data:
        _pool = set()
        for _k in ("bau_build_chars", "bau_reaction_chars",
                   "bau_invention_chars", "bau_copy_chars"):
            for _c in (data.get(_k) or []):
                try:
                    _pool.add(int(_c))
                except (TypeError, ValueError):
                    continue
        data["bau_rollen_pool"] = sorted(_pool)
        _migrated = True
    # REAGENZGLAS-EMOJI AUS ALTEN PLAN-NAMEN (Nutzer 18.09.2026: "diese
    # Reagenzglas-Emojis im Profit-Tab muessen weg"). Eine fruehere Fassung
    # nannte erfindbare T2-Zeilen "\U0001F9EA Name"; gespeicherte Plaene
    # tragen das Zeichen bis heute in label und item_name. Hier einmalig
    # abstreifen - im Code entsteht es nicht mehr.
    for _p in (data.get("bau_saved_plans") or []):
        for _k in ("label", "item_name"):
            _v = _p.get(_k)
            if isinstance(_v, str) and plan_name_bereinigen(_v) != _v:
                _p[_k] = plan_name_bereinigen(_v)
                _migrated = True
    # QUELLEN OFFENER BUENDEL SIND NIE EINGEFROREN (26.09.2026, s.
    # buendel_quellen_freigeben). Idempotent: beim zweiten Lauf gibt es
    # nichts mehr zu aendern.
    if buendel_quellen_nachziehen(data.get("bau_saved_plans") or []):
        _migrated = True
    # MITGLIEDER ABGESCHLOSSENER BUENDEL (29.09.2026): Buendel, die VOR emm269
    # abgeschlossen wurden, liessen ihre Einzelplaene offen - sie bekamen
    # Rang #3/#4/#5 und schoben neue Plaene nach hinten (Nutzer-Screenshot
    # "Linsen Multiplan 1 #6"). Dasselbe wie "Done" am Buendel heute:
    # abschliessen mit Merker, "Reopen" am Buendel oeffnet sie wieder.
    # EINMAL (Marker) - wer danach ein Mitglied selbst oeffnet, behaelt das.
    if not data.get("buendel_done_nachgezogen"):
        _pl = data.get("bau_saved_plans") or []
        _nach_id = {str(x.get("id")): x for x in _pl}
        for _b in _pl:
            try:
                _ist_b = int(_b.get("type_id", 0) or 0) == -1
            except (TypeError, ValueError):
                _ist_b = False
            if not _ist_b or not _b.get("done_manual"):
                continue
            for _qid in (_b.get("quellen") or []):
                _q = _nach_id.get(str(_qid))
                if _q is not None and not _q.get("done_manual"):
                    _q["done_manual"] = True
                    _q["reserve"] = False
                    _q["done_durch_buendel"] = _b.get("id")
        data["buendel_done_nachgezogen"] = True
        _migrated = True
    # INVENTION WIEDER AN (emm385, 03.10.2026): die Einstellung ist seit
    # langem unsichtbar, stand bei manchen Nutzern aber noch auf "aus"
    # (geerbt von einem alten gespeicherten Plan) - Decryptoren wirkten dann
    # nicht. EINMAL zuruecksetzen; der Code rechnet ohnehin immer mit Invention.
    if not data.get("bau_invention_an_applied"):
        data["bau_invention"] = True
        data["bau_invention_an_applied"] = True
        _migrated = True
    # REPROCESSING-STEUER JE STRUKTUR (emm496, Nutzer 09.10.2026: "einmal
    # eingegebene Steuer soll auf zukuenftig erstellten Bauplaenen
    # uebernommen werden, solange die selbe Reprocessing Struktur gewaehlt
    # ist"): der alte GLOBALE Wert wandert EINMAL unter die damals
    # gewaehlte Struktur, danach zaehlt nur noch die Karte je Struktur.
    if not data.get("reproc_steuer_map_applied"):
        try:
            _alt_st = float(data.get("bau_reproc_steuer") or 0.0)
        except (TypeError, ValueError):
            _alt_st = 0.0
        if _alt_st > 0 and not (data.get("bau_reproc_steuer_map") or {}):
            data["bau_reproc_steuer_map"] = {
                str(data.get("bau_reprocess_struct") or "npc"): _alt_st}
        data["reproc_steuer_map_applied"] = True
        _migrated = True
    # ALTE BAU-PROFILE ENTSCHLACKEN (03.10.2026): Plaene, Jobs, Skills raus
    # (siehe BAU_PROFIL_OHNE). EINMAL per Marker.
    if not data.get("bau_profile_bereinigt"):
        _pr = data.get("bau_profiles")
        if isinstance(_pr, dict):
            data["bau_profiles"] = {_n: bau_profil_bereinigen(_v)
                                    for _n, _v in _pr.items() if isinstance(_v, dict)}
        data["bau_profile_bereinigt"] = True
        _migrated = True
    # ERLEDIGTE PLAENE ARCHIVIEREN (emm388, laeuft bei jedem Laden):
    # done_manual ohne Zeitstempel bekommt ihn JETZT (die 30 Tage zaehlen ab
    # heute - nie rueckwirkend raten), danach wandern faellige ins Archiv.
    try:
        import time as _t_arch
        for _p in (data.get("bau_saved_plans") or []):
            if _p.get("done_manual") and not _p.get("done_ts"):
                _p["done_ts"] = _t_arch.time()
                _migrated = True
        if plaene_archivieren(data):
            _migrated = True
    except Exception:
        pass
    if _migrated:
        try:
            save_settings(data)   # Marker muss ueberleben, sonst Endlos-Lauf
        except Exception:
            pass
    return data


def save_settings(settings: dict) -> None:
    """Atomar speichern: erst vollständig in eine Temp-Datei im selben Ordner
    schreiben, dann per os.replace über die alte Datei schieben (atomar, auch
    unter Windows). Grund: settings.json enthält Guthaben/Subs/Trial und
    gespeicherte Baupläne - ein Absturz mitten im Schreiben (oder zwei Threads
    gleichzeitig) darf die Datei nicht halb geschrieben zurücklassen, sonst
    fällt load_settings still auf die Defaults zurück und alles ist weg."""
    # Ein noch laufendes Hintergrund-Schreiben ZUERST abwarten, sonst koennte
    # es hinterher den aelteren Stand ueber den neueren schieben.
    flush_settings()
    _schreibe_settings(_settings_text(settings))


def _settings_text(settings: dict) -> str:
    """EINE Stelle fuer den JSON-Text (emm388, 04.10.2026, Nutzer: "machen").
    OHNE Einrueckung: an seiner echten settings.json (39 MB) gemessen dauerte
    `json.dumps(indent=2)` 1,7 s je Speichern, kompakt 0,34 s - und die Datei
    wird nebenbei kleiner. Lesbarkeit braucht die Datei nicht, sie wird nur
    von Programmen gelesen."""
    return json.dumps(settings, separators=(",", ":"))


def _schreibe_settings(text: str) -> None:
    """Der eigentliche atomare Schreibvorgang - Text rein, Datei raus."""
    import tempfile
    fd, tmp_path = tempfile.mkstemp(prefix="settings-", suffix=".tmp",
                                    dir=app_data_dir())
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, settings_path())
    except Exception:
        # Halb geschriebene Temp-Datei nicht liegen lassen; Original bleibt
        # unangetastet gültig.
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


# ---- Hintergrund-Schreiben ---------------------------------------------------
# NUTZER-BEFUND (Sitzung 10 + 11): "wenn ich da mehrere Sachen und Charaktere
# austauschen und anhaken will, dauert es sehr lange, teilweise friert mir das
# Tool fast ein" - nachgemessen ~3 s je Klick auf seinem Rechner.
#
# GEMESSEN (hier, an einer settings.json in seiner Groessenordnung):
#   JSON-Text bauen  ~57 ms   <- muss auf dem Oberflaechen-Faden passieren,
#                                sonst koennte sich das Dict waehrenddessen
#                                aendern ("dictionary changed size")
#   Platte + fsync    ~8 ms   <- hier auf schneller SSD ohne Virenscanner;
#                                bei ihm ist GENAU DAS der teure Teil, weil
#                                der Scanner jede frisch angelegte Temp-Datei
#                                anfasst, bevor os.replace sie umhaengt.
# Deshalb wird der teure Teil ausgelagert: der Text entsteht sofort (der Stand
# ist damit eingefroren und kann nicht mehr verlorengehen), das Schreiben
# laeuft im Hintergrund. Die Oberflaeche wartet nicht mehr auf die Platte.
_schreib_sperre = None
_schreib_offen = {"text": None}
_schreib_faden = None


def _schreib_sperre_holen():
    global _schreib_sperre
    if _schreib_sperre is None:
        import threading
        _schreib_sperre = threading.Lock()
    return _schreib_sperre


def save_settings_async(settings: dict) -> None:
    """Wie save_settings, aber die Platte wartet nicht auf die Oberflaeche.

    Der JSON-Text wird SOFORT erzeugt (Momentaufnahme - spaetere Aenderungen
    am Dict koennen ihn nicht mehr verfaelschen), geschrieben wird er von
    einem Hintergrundfaden. Laeuft schon einer, uebernimmt der einfach den
    neuesten Text - es gibt also nie eine Warteschlange veralteter Staende,
    immer nur den letzten.
    """
    import threading
    global _schreib_faden
    text = _settings_text(settings)
    with _schreib_sperre_holen():
        _schreib_offen["text"] = text
        if _schreib_faden is not None and _schreib_faden.is_alive():
            return                      # laufender Faden nimmt den neuen Text
        _schreib_faden = threading.Thread(target=_schreib_schleife,
                                          name="settings-writer", daemon=True)
        _schreib_faden.start()


def _schreib_schleife():
    while True:
        with _schreib_sperre_holen():
            text = _schreib_offen["text"]
            _schreib_offen["text"] = None
            if text is None:
                return
        try:
            _schreibe_settings(text)
        except Exception:
            return                      # naechster Aufruf versucht es erneut


def flush_settings(timeout: float = 10.0) -> None:
    """Auf ein laufendes Hintergrund-Schreiben warten.

    Wird vor jedem synchronen Speichern und beim Schliessen des Programms
    gerufen: ein Fenster-Schliessen darf die letzte Auswahl nicht mitnehmen,
    nur weil sie noch im Hintergrund unterwegs war.
    """
    faden = _schreib_faden
    if faden is not None and faden.is_alive():
        faden.join(timeout)


def callback_url(port: int) -> str:
    return f"http://localhost:{port}/callback"

# Spenden (Nutzer-Entscheidung, Sitzung 8: Abo-Modell verworfen). Der
# Name erscheint im Spenden-Hinweis; ingame oeffnet der Spieler damit das
# Corporation-Fenster. Hier zentral aenderbar.
# Spenden-Ziel: NAME der Corporation ingame. Die ID wird zur Laufzeit ueber
# ESI aufgeloest (esi.resolve_corp_id) - so bleibt der Eintrag lesbar und
# ueberpruefbar, statt einer stillen Zahl.
# de_scan5: aus  (Eigenname einer Corporation im Spiel, wird nicht uebersetzt)
DONATION_CORP = "Der Handelsorden"
# de_scan5: an
