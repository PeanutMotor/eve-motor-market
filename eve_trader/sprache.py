"""Sprachumschaltung für die Oberfläche.

NUTZER-AUFTRAG (Sitzung 12): "Es soll umschaltbar sein. Standard beim
Öffnen soll immer English sein. Oben einen Button 'Language' und da soll
man von English auf Deutsch wechseln können."

WIE ES AUFGEBAUT IST - und warum genau so:

* DER QUELLTEXT IST ENGLISCH. `t("Portfolio")` gibt auf Englisch schlicht
  den Schlüssel zurück, auf Deutsch den Eintrag aus dem Katalog. Damit ist
  das Fehlerbild bei einer vergessenen Übersetzung: es erscheint ENGLISCH.
  Andersherum (deutscher Quelltext, englischer Katalog) stünde bei jeder
  Lücke ein deutsches Wort in einer englischen Oberfläche - genau das,
  was ein englischsprachiger Nutzer nicht deuten kann.

* KEIN Qt-Übersetzungssystem (QTranslator/.ts/.qm). Das verlangt eine
  eigene Werkzeugkette (lupdate/lrelease) und passt schlecht zu den vielen
  f-Strings hier. Ein Wörterbuch ist für ~1'550 Texte völlig ausreichend
  und ohne Zusatzwerkzeug pflegbar.

* PLATZHALTER BLEIBEN AUSSERHALB. `t("Found {n} deals").format(n=3)` statt
  eines Katalogs voller fertiger Sätze - sonst müsste jede Zahl eine
  eigene Zeile im Katalog bekommen.

WER EINEN TEXT ERGÄNZT: englisch schreiben, in `t()` einpacken, deutschen
Eintrag in KATALOG nachtragen. Fehlt der Eintrag, erscheint Englisch -
kein Absturz, keine leere Beschriftung.
"""

SPRACHEN = {"en": "English", "de": "Deutsch"}

# ENGLISCH IST DER SCHLÜSSEL, Deutsch die Übersetzung.
KATALOG = {
    "de": {
        # ---- Navigation und Reiter ----
        "Portfolio": "Portfolio",
        "Shopping list": "Einkaufswagen",
        "Sell list": "Verkaufsliste",
        "Order update": "Order-Update",
        "Profits": "Gewinne",
        "Transactions": "Transaktionen",
        "Price history": "Kursverlauf",
        "Characters": "Charaktere",
        "Settings": "Einstellungen",
        "Daytrade": "Daytrade",
        "Swing Trade": "Swing Trade",
        "Industry": "Bauen",
        "Regional Trading": "Regional Trading",
        "Tools": "Werkzeuge",
        # ---- Kopfzeile ----
        "Hub: ": "Hub: ",
        "Structure": "Struktur",
        "Market scan": "Markt-Scan",
        # ZWEI KNOEPFE, ZWEI WIRKUNGEN (17.09.2026): "Load recipes" laedt die
        # SDE (Rezeptdaten), "Load blueprints" holt die eigenen Blaupausen
        # aus ESI. Vorher hiessen beide "Load blueprints" - und die deutsche
        # Fassung nannte auch die Blaupausen-Seite "Baurezepte laden".
        "Load recipes": "Baurezepte laden",
        "Load blueprints": "Blaupausen laden",
        # Reprocessing (1.0.9): Skill-Stufen nur im Tooltip des Charakters.
        "Reprocessing skills: {r} / Efficiency {e}": "Reprocessing-Skills: {r} / Efficiency {e}",
        # Reprocessing, Weg B (18.09.2026): Karte in der Rezeptstruktur und
        # Zeilen im Materialien-Tab.
        "Reprocessing": "Reprocessing",
        "NPC station": "NPC-Station",
        "NPC station (50 %)": "NPC-Station (50 %)",
        "Buy compressed ore instead of minerals": "Komprimiertes Erz statt Minerale kaufen",
        "Reprocess at": "Reprocessen bei",
        "Detects the reprocessing implants (Zainou 'Beancounter' Reprocessing RX-801/802/804) of all linked characters via ESI. Needs the implant scope (Settings \u2192 \u201eImplant manufacturing bonus\u201c \u2192 On + relink). The bonus goes into the yield and the character choice.":
            "Erkennt die Reprocessing-Implantate (Zainou 'Beancounter' Reprocessing RX-801/802/804) aller verkn\u00fcpften Charaktere per ESI. Braucht den Implantat-Scope (Einstellungen \u2192 \u201eImplant manufacturing bonus\u201c \u2192 An + neu verkn\u00fcpfen). Der Bonus geht in Ausbeute und Charakterwahl ein.",
        "no reprocessing implant detected": "kein Reprocessing-Implantat erkannt",
        "No reprocessing implant data \u2013 run \u201eLoad recipes\u201c once.":
            "Keine Reprocessing-Implantat-Daten \u2013 einmal \u201eLoad recipes\u201c dr\u00fccken.",
        "{n} reprocessing implant(s) detected \u2713": "{n} Reprocessing-Implantat(e) erkannt \u2713",
        "Where the ore is reprocessed. Refineries (Athanor/Tatara) get their bonus and reprocessing rig from the structure list; an NPC station has a flat 50 % base.":
            "Wo das Erz reprocesst wird. Refineries (Athanor/Tatara) bekommen Bonus und Reprocessing-Rig aus der Strukturliste; eine NPC-Station hat fest 50 % Basis.",
        "No reprocessing data for this structure – run „Load recipes“ once (Setup).":
            "Keine Reprocessing-Daten für diese Struktur – einmal „Load recipes“ drücken (Setup).",
        "Structure base {pct} %": "Struktur-Basis {pct} %",
        "Not enough at the hub (order book, available / needed): {liste} \u2013 the rest is priced at the most expensive order, you may have to buy elsewhere or wait.":
            "Zu wenig am Hub (Orderbuch, da / gebraucht): {liste} \u2013 der Rest ist zum teuersten Angebot bewertet, du musst evtl. woanders kaufen oder warten.",
        "Reprocessing: no structure data – run „Load recipes“ once (Setup).":
            "Reprocessing: keine Strukturdaten – einmal „Load recipes“ drücken (Setup).",
        "Reprocessing could not be calculated – see fehler.log.":
            "Reprocessing konnte nicht berechnet werden – siehe fehler.log.",
        "Buy the compressed ore, reprocess it with the named character at this structure \u2013 then the minerals are in stock for the stages below. Ore is reprocessed in batches of 100; the number in the Runs column is the number of batches.":
            "Das komprimierte Erz kaufen und mit dem genannten Charakter an dieser Struktur reprocessen \u2013 dann liegen die Minerale f\u00fcr die Stufen darunter im Bestand. Erz wird in Bl\u00f6cken von 100 reprocesst; die Zahl in der Runs-Spalte ist die Anzahl Bl\u00f6cke.",
        "{n} batches": "{n} Bl\u00f6cke",
        "Best reprocessing character for these ores (skills x implant) \u2013 log in with this one.":
            "Bester Reprocessing-Charakter f\u00fcr diese Erze (Skills x Implantat) \u2013 mit dem einloggen.",
        "Click copies the name for the market search.": "Klick kopiert den Namen f\u00fcr die Marktsuche.",
        "What the ore yields for this plan; the rest is surplus (right).":
            "Was das Erz f\u00fcr diesen Plan liefert; der Rest ist \u00dcberschuss (rechts).",
        "Click copies {r} \u2013 paste it into the quantity field in game (Ctrl+V).":
            "Klick kopiert {r} \u2013 ins Mengenfeld im Spiel einf\u00fcgen (Strg+V).",
        "{n} batches of {p} units. Yield {pct} % with this character at this structure.\nTick = reprocessed: from then on the minerals must be in stock and the ore no longer counts as needed.":
            "{n} Bl\u00f6cke zu {p} St\u00fcck. Ausbeute {pct} % mit diesem Charakter an dieser Struktur.\nHaken = reprocesst: ab dann m\u00fcssen die Minerale im Bestand liegen, das Erz z\u00e4hlt nicht mehr als Bedarf.",
        "from reprocessing \u267b \u00b7 {n} units": "aus Reprocessing \u267b \u00b7 {n} St\u00fcck",
        "from compressed ore \u267b \u00b7 {ore}": "aus komprimiertem Erz \u267b \u00b7 {ore}",
        "buy \u00b7 partly from compressed ore \u267b": "kaufen \u00b7 teils aus komprimiertem Erz \u267b",
        "Unrefined reaction": "Unrefined-Reaktion",
        "Unrefined reactions": "Unrefined-Reaktionen",
        "on blacklist \u2013 provided, not bought":
            "auf der Blacklist \u2013 wird gestellt, nicht gekauft",
        "incl. freight":
            "inkl. Fracht",
        "no compressed ore is cheaper":
            "kein komprimiertes Erz ist g\xfcnstiger",
        "Compressed ore the plan buys instead of minerals \u2013 reprocessed at {struct}.":
            "Komprimiertes Erz, das der Plan statt Mineralen kauft \u2013 reprocesst an {struct}.",
        "saves {isk} \xb7 {n} ores":
            "spart {isk} \xb7 {n} Erze",
        "no unrefined reaction is cheaper":
            "keine Unrefined-Reaktion ist g\xfcnstiger",
        "reprocess \u2192 {out} \xb7 {pct} %":
            "reprocessen \u2192 {out} \xb7 {pct} %",
        "{n} intermediates via unrefined reaction":
            "{n} Zwischenmaterialien \xfcber Unrefined-Reaktion",
        "Compressed ore checked: {ore} would be {pct} % more expensive than buying the mineral.":
            "Komprimiertes Erz gepr\xfcft: {ore} w\xe4re {pct} % teurer als der Kauf des Minerals.",
        "Compressed ore \u267b":
            "Komprimiertes Erz \u267b",
        "Builds intermediates via their \u201eUnrefined \u2026 Reaction Formula\u201c when that is cheaper per unit than the normal reaction or buying.\nYield: 50 % \xd7 Scrapmetal Processing. The returned input is credited but stays on the shopping list.\nNeeds: hub scan + \u201eLoad skills\u201c.":
            "Baut Zwischenmaterialien \xfcber ihre \u201eUnrefined \u2026 Reaction Formula\u201c, wenn das je St\xfcck g\xfcnstiger ist als normale Reaktion oder Kauf.\nAusbeute: 50 % \xd7 Scrapmetal Processing. Der R\xfcckl\xe4ufer wird gutgeschrieben, bleibt aber auf der Einkaufsliste.\nBraucht: Hub-Scan + \u201eSkills laden\u201c.",
        "Buys compressed ore instead of a mineral when the ore is cheaper \u2013 with your yield (structure, rig, skills). By-products count as far as the plan needs them. Batches of 100.\nNeeds: hub scan + \u201eLoad skills\u201c.":
            "Kauft komprimiertes Erz statt eines Minerals, wenn das Erz g\xfcnstiger ist \u2013 mit deiner Ausbeute (Struktur, Rig, Skills). Nebenprodukte z\xe4hlen, soweit der Plan sie braucht. Bl\xf6cke zu 100.\nBraucht: Hub-Scan + \u201eSkills laden\u201c.",
        "Unrefined: 50 % \xd7 Scrapmetal Processing \u2013 no skills loaded":
            "Unrefined: 50 % \xd7 Scrapmetal Processing \u2013 keine Skills geladen",
        "Unrefined: {pct} % \xb7 {char} (50 % \xd7 Scrapmetal Processing, structure does not apply)":
            "Unrefined: {pct} % \xb7 {char} (50 % \xd7 Scrapmetal Processing, Struktur z\xe4hlt nicht)",
        "After the reaction: reprocess the unrefined products with the named character (any station or structure) \u2013 only then is the intermediate material in stock for the next stage. The returned input (surplus, right) comes back here as well.":
            "Nach der Reaktion: die Unrefined-Produkte mit dem genannten Charakter reprocessen (beliebige Station oder Struktur) \u2013 erst dann liegt das Zwischenmaterial f\xfcr die n\xe4chste Stufe im Bestand. Der R\xfcckl\xe4ufer (\xdcberschuss, rechts) kommt hier ebenfalls zur\xfcck.",
        "Base 50 % \xd7 Scrapmetal Processing":
            "Basis 50 % \xd7 Scrapmetal Processing",
        "{n} units from the reaction stage above. Yield {pct} % with this character: 50 % \xd7 Scrapmetal Processing \u2013 structure, rig and ore skills do not apply here.\nTick = reprocessed (progress mark only).":
            "{n} St\xfcck aus der Reaktionsstufe dar\xfcber. Ausbeute {pct} % mit diesem Charakter: 50 % \xd7 Scrapmetal Processing \u2013 Struktur, Rig und Erz-Skills z\xe4hlen hier nicht.\nHaken = reprocesst (nur Fortschrittsmarke).",
        "Use unrefined reactions where cheaper":
            "Unrefined-Reaktionen nutzen, wo g\xfcnstiger",
        "Input material that comes back when the unrefined products are reprocessed \u2013 credited at the hub price. It stays on the shopping list because it returns only after the reaction.":
            "Input-Material, das beim Reprocessing der Unrefined-Produkte zur\xfcckkommt \u2013 zum Hub-Preis gutgeschrieben. Es bleibt auf der Einkaufsliste, weil es erst nach der Reaktion zur\xfcckkommt.",
        "Returned after reprocessing (credit): ":
            "R\xfcckl\xe4ufer aus Reprocessing (Gutschrift): ",
        "via {formula} \u267b":
            "\xfcber {formula} \u267b",
        "Reprocessing of unrefined products":
            "Reprocessing der Unrefined-Produkte",
        "Unrefined reaction not cheaper for: {liste}":
            "Unrefined-Reaktion nicht g\xfcnstiger f\xfcr: {liste}",
        "\u2212 Returned (reprocessing)":
            "\u2212 R\xfcckl\xe4ufer (Reprocessing)",
        "Covered by reprocessing compressed ore (run planner, stage 0) \u2013 nothing to buy. Once the ore is reprocessed and ticked there, the minerals must lie in stock.":
            "Gedeckt durch Reprocessing von komprimiertem Erz (Runplaner, Stufe 0) \u2013 nichts zu kaufen. Sobald das Erz reprocesst und dort abgehakt ist, m\u00fcssen die Minerale im Bestand liegen.",
        "Character:": "Charakter:",
        "EVE data": "EVE-Daten",
        "Updates": "Updates",
        "Donate": "Spenden",
        # ---- Portfolio ----
        "Search \u2026": "Suchen \u2026",
        "Refresh": "Aktualisieren",
        "Columns": "Spalten",
        "All characters": "Alle Charaktere",
        "Total assets": "Gesamtverm\u00f6gen",
        "Wallet": "Kontostand",
        "Unrealised P/L": "Unrealisiert P/L",
        "Ready to sell": "Verkaufsbereit",
        "Containers": "Container",
        # ---- Tabellenkoepfe Portfolio ----
        "Item": "Item",
        "Qty": "Menge",
        "\u00d8 buy": "\u00d8-Kauf",
        "Oldest buy": "\u00c4ltester Kauf",
        "Sell @ hub": "Sell @ Hub",
        "Net/unit": "Netto/Stk",
        "Margin %": "Marge %",
        "Status": "Status",
        "Orders": "Orders",
        "Best sale": "Optimaler Verkauf",
        "\u00d8 buy +fees": "\u00d8-Kauf +Geb.",
        "In sell order at": "In Sell-Order zu",
        # ---- Zustaende ----
        "● SELL": "● VERKAUFEN",
        "● Hold": "● Halten",
        "● on market": "● im Markt",
        # ---- Altersangaben in der Kopfzeile ----
        "Prices (live)": "Preise (live)",
        "Market scan": "Markt-Scan",
        "never": "nie",
        "just now": "gerade",
        "{n} min ago": "vor {n} Min.",
        "{n} h ago": "vor {n} Std.",
        "{n} d ago": "vor {n} Tg.",
        # ---- Strategie-Karte ----
        "Strategy \u2013 what you are looking for": "Strategie \u2013 womit du suchst",
        "Mode": "Modus",
        "Strategy": "Strategie",
        "Preset": "Preset",
        "\u2014 Custom \u2014": "\u2014 Eigene Einstellung \u2014",
        "FINE FILTERS (OPTIONAL)": "FEINFILTER (OPTIONAL)",
        "STRATEGY": "STRATEGIE",
        # ---- Tabellenkoepfe Daytrade ----
        "Now (buy)": "Jetzt (Buy)",
        "Now (sell)": "Jetzt (Sell)",
        "\u00d8 price (window)": "\u00d8-Preis (Zeitraum)",
        "below \u00d8/drop/build %": "unter \u00d8/Drop/Bau %",
        "Build cost": "Baukosten",
        "Profit/unit": "Gewinn/Stk",
        "\u00d8 daily vol": "\u00d8 Tagesvol",
        "Volat. %": "Volatil. %",
        "Days of stock": "Bestandstage",
        "Profit/day": "Gewinn/Tag",
        "Trend": "Trend",
        "Target price": "Zielpreis",
        "Exp. profit %": "Erw. Gewinn %",
        "Competitors": "Konkurrenz",
        "Sellable/day": "Einnehmbar/Tag",
        "Tradability": "Handelbar.",
        "Capital eff. %/day": "Kapital-Eff. %/Tag",
        # ---- Tabellenkoepfe Swing ----
        "below normal %": "unter Normal %",
        "Exp. profit/unit": "Erw. Gewinn/Stk",
        "Sell side %": "Verk.-Seite %",
        "Recovery": "Erholung",
        "~Hold time": "~Haltedauer",
        # ---- Feinfilter Daytrade ----
        "Category": "Kategorie",
        "Meta": "Meta",
        "Window": "Zeitfenster",
        "Min margin/drop %": "Min Marge/Drop %",
        "Min \u00d8 daily volume": "Min \u00d8-Tagesvolumen",
        "Min profit/unit (ISK)": "Min Gewinn/Stk (ISK)",
        "Min margin": "Min Marge",
        "Min profit/day (ISK)": "Min Gewinn/Tag (ISK)",
        "Min buy-price share %": "Min Kaufpreis-Anteil %",
        "Max competitors (0=\u221e)": "Max Konkurrenten (0=\u221e)",
        "Min tradability": "Min Handelbarkeit",
        "Min buy fill %": "Min Buy-F\u00fcllung %",
        "Both sides daily %": "Beide Seiten t\u00e4gl. %",
        "Min depth at best price": "Min Tiefe am Bestpreis",
        "Max % above normal (0=\u221e)": "Max % \u00fcber Normal (0=\u221e)",
        "Max price spike \u2191 (0=\u221e)": "Max Preis-Sprung \u2191 (0=\u221e)",
        "Min units/day realistic (0=\u221e)": "Min St\u00fcck/Tag realist. (0=\u221e)",
        "Min volatility %": "Min Volatilit\u00e4t %",
        "Max days of stock (0=\u221e)": "Max Bestandstage (0=\u221e)",
        "Downtrend": "Abw\u00e4rtstrend",
        # ---- Feinfilter Swing ----
        "Min below normal %": "Min unter Normal %",
        "Max below normal %": "Max unter Normal %",
        "Min exp. profit %": "Min erw. Gewinn %",
        "Min exp. profit (ISK/unit)": "Min erw. Gewinn (ISK/Stk)",
        "Min sellable/day (0=\u221e)": "Min verkaufbar/Tag (0=\u221e)",
        "Price from": "Preis ab",
        "Price to (0=\u221e)": "Preis bis (0=\u221e)",
        # ---- Bauen-Reiter ----
        "Find blueprints": "Blaupausen suchen",
        "Delete": "L\u00f6schen",
        "Close": "Schlie\u00dfen",
        "Reset": "Zur\u00fccksetzen",
        "Resets everything in this build plan to the defaults (asks first). Your saved plan only changes when you save again.":
            "Setzt alles in diesem Bauplan auf Standard zur\u00fcck (fragt vorher). Dein gespeicherter Plan \u00e4ndert sich erst, wenn du wieder speicherst.",
        "Reset build plan?": "Bauplan zur\u00fccksetzen?",
        "Do you really want to reset everything in \u201e{name}\u201c to the defaults?":
            "Willst du wirklich alles in \u201e{name}\u201c auf Standard zur\u00fccksetzen?",
        "Plan frozen \u2013 unfreeze first ( button), then reset.":
            "Plan eingefroren \u2013 erst auftauen ( Knopf), dann zur\u00fccksetzen.",
        "Load order-book prices into the plan": "Orderbuch-Preise in den Plan laden",
        "Fetches the real sell order book of the hub for every material and uses it for the build cost of this plan (one live request per material, may take a moment).":
            "Holt f\u00fcr jedes Material das echte Sell-Orderbuch des Hubs und nutzt es f\u00fcr die Baukosten dieses Plans (ein Live-Abruf je Material, kann etwas dauern).",
        "\u2139 Quantities calculated live, order book prices from the last fetch (Tools \u2192 \u201eLoad order-book prices into the plan\u201c, at quantity {qty}). Run it again for fresh prices.":
            "\u2139 Mengen live gerechnet, Orderbuch-Preise vom letzten Abruf (Werkzeuge \u2192 \u201eOrderbuch-Preise in den Plan laden\u201c, bei Menge {qty}). F\u00fcr frische Preise erneut ausf\u00fchren.",
        "Flat price (current market scan) \u2013 for order-book-exact numbers use Tools \u2192 \u201eLoad order-book prices into the plan\u201c.":
            "Flachpreis (aktueller Markt-Scan) \u2013 f\u00fcr orderbuch-genaue Zahlen Werkzeuge \u2192 \u201eOrderbuch-Preise in den Plan laden\u201c.",
        "Optimal quantity": "Optimale Menge",
        "Estimate capital build cost": "Capital-Baukosten sch\u00e4tzen",
        "Load everything from ESI": "Alles aus ESI laden",
        "Check shortfall": "Fehlbedarf pr\u00fcfen",
        "Build margin": "Bau-Marge",
        "Min build margin %": "Min Bau-Marge %",
        "Rating": "Bewertung",
        "Ship": "Schiff",
        "Contract reference": "Contract-Referenz",
        "Build location (structure)": "Bau-Ort (Struktur)",
        "Blueprints per stage": "Blaupausen je Stufe",
        "Build characters": "Bau-Charaktere",
        "Recipe structure": "Rezept-Struktur",
        "Hulls": "H\u00fcllen",
        "Datacores and decryptors": "Datacores und Decryptoren",
        "Other blueprints (ME/TE)": "Andere Blaupausen (ME/TE)",
        "Only build structures": "Nur Bau-Strukturen",
        "Everywhere (all locations)": "\u00dcberall (alle Orte)",
        "Total profit": "Gewinn gesamt",
        "Gross profit (before fees)": "Rohgewinn gesamt (ohne Geb\u00fchren)",
        "Margin": "Marge",
        "Material": "Material",
        "Required": "Ben\u00f6tigt",
        "Owned": "Besitze",
        "Pasted": "Eingef\u00fcgt",
        "Missing": "Fehlt",
        "Apply": "\u00dcbernehmen",
        "Paste stock": "Bestand einf\u00fcgen",
        "You do not need to paste stock \u2013 this tool works with ESI. Only if you do not want that.":
            "Du musst keinen Bestand einf\u00fcgen \u2013 dieses Tool arbeitet mit ESI. Nur wenn du das nicht m\u00f6chtest.",
        "Continue": "Weiter",
        "Load skills": "Skills laden",
        "Load implants": "Implantate laden",
        # ---- Dialoge: Update-Pruefung ----
        "Check for updates": "Auf Updates pr\u00fcfen",
        "You are up to date \u2705": "Du bist auf dem neuesten Stand \u2705",
        "Blueprints and build times are already loaded \u2013 no download "
        "needed.": "Baurezepte + Bauzeiten bereits geladen \u2013 kein "
                   "Download n\u00f6tig.",
        "Could not check the update status (no connection to EVE or "
        "Fuzzwork).": "Konnte den Update-Status nicht abrufen (keine "
                      "Verbindung zu EVE oder Fuzzwork).",
        # ---- Dialoge: Charaktere und ESI ----
        "No ESI access, or no characters linked.":
            "Kein ESI-Zugang oder keine verkn\u00fcpften Charaktere.",
        "No blueprints (BPO/BPC) of your own found for the items here.":
            "Keine eigenen Blaupausen (BPO/BPC) f\u00fcr die Items hier "
            "gefunden.",
        "No blueprints of your own found for items at this stage.":
            "Keine eigenen Blaupausen f\u00fcr Items dieser Stufe gefunden.",
        "Open in game": "Ingame \u00f6ffnen",
        "Open market in game": "Ingame-Markt \u00f6ffnen",
        "Enable open in game": "Ingame \u00f6ffnen aktivieren",
        "Could not open the market in game.\n\n":
            "Konnte den Markt im Spiel nicht \u00f6ffnen.\n\n",
        # ---- Dialoge: Daten ----
        "Implant data missing": "Implantat-Daten fehlen noch",
        "Settings not readable": "Einstellungen nicht lesbar",
        "Price history missing": "Preisverl\u00e4ufe fehlen noch",
        "Could not open the build plan: ":
            "Konnte den Bauplan nicht \u00f6ffnen: ",
        # ---- Statuszeile ----
        "Computing deals \u2026 (the first run per hub loads the market "
        "history \u2013 cached and fast afterwards)":
            "Berechne Deals \u2026 (erster Lauf je Hub l\u00e4dt die "
            "Markthistorie \u2013 danach im Cache und schnell)",
        "Loading SDE database (once, ~140 MB) \u2026":
            "Lade SDE-Datenbank (einmalig ~140 MB) \u2026",
        "Gold search running \u2026": "Gold-Suche l\u00e4uft \u2026",
        "No character linked.": "Kein Charakter verkn\u00fcpft.",
        "Preset applied. First \u201eMarket scan\u201c, then "
        "\u201eLoad deals\u201c.":
            "Preset gesetzt. Erst \u201eMarkt-Scan\u201c, dann "
            "\u201eDeals laden\u201c.",
        "Checking open sell order prices \u2026":
            "Pr\u00fcfe offene Sell-Order-Preise \u2026",
        "All price histories for this hub are already loaded.":
            "Alle Preisverl\u00e4ufe dieses Hubs sind bereits geladen.",
        "Histories could not be loaded. Whatever was fetched stays saved.":
            "Verl\u00e4ufe konnten nicht geladen werden. Schon Geholtes "
            "bleibt gespeichert.",
        "Set up. Now use \u201eLink character\u201c.":
            "Eingerichtet. Jetzt \u201eCharakter verkn\u00fcpfen\u201c.",
        "The category/meta filter needs the SDE data \u2013 please run "
        "\u201eLoad recipes\u201c once.":
            "Kategorie-/Meta-Filter braucht die SDE-Daten \u2013 bitte "
            "einmal \u201eBaurezepte laden\u201c.",
        # ---- Trichterzeile: warum so wenige Treffer? ----
        # DIESE ZEILE IST DIE WICHTIGSTE ERKLAERUNG IM WERKZEUG. Sie sagt,
        # WARUM nichts gefunden wurde - genau die Zeile, an der der Nutzer
        # auf dem frisch installierten Rechner haengen blieb.
        "{n} hits ({label}). ": "{n} Treffer ({label}). ",
        "{n} analysed": "{n} analysiert",
        "\u26a0 analysis error (please load again)":
            "\u26a0 Analyse-Fehler (bitte erneut laden)",
        "without price history": "ohne Preishistorie",
        "below volume": "unter Volumen",
        "too hard to trade": "zu schwer handelbar",
        "not traded on both sides daily": "nicht beidseitig t\u00e4glich",
        "buy side barely reached": "Buy-Seite kaum erreicht",
        "buy side rarely fills": "Buy-Seite f\u00fcllt selten",
        "too little movement": "zu wenig Schwankung",
        "stock too large (days of supply)":
            "Bestand zu gro\u00df (Tage-Vorrat)",
        "too much competition": "zu viel Konkurrenz",
        "ghost buy order (buy-price share)":
            "Geister-Buy-Order (Kaufpreis-Anteil)",
        "profit/unit too small": "Gewinn/Stk zu klein",
        "margin too small": "Marge zu klein",
        "profit/day too small": "Gewinn/Tag zu klein",
        "realistically too few units/day":
            "realistisch zu wenig St\u00fcck/Tag",
        "\u2191 just spiked (do not buy)":
            "\u2191 frisch hochgeschossen (nicht bekaufen)",
        "too far above normal price": "zu weit \u00fcber Normalpreis",
        "depth at best price too thin": "Tiefe am Bestpreis zu d\u00fcnn",
        "sell fill too small": "Sell-F\u00fcllung zu klein",
        "build cost not computable": "Baukosten nicht berechenbar",
        "below minimum margin": "unter Mindest-Marge",
        "\u26a0 ESI limit reached \u2013 histories are loading in the "
        "background, load again shortly":
            "\u26a0 ESI-Limit erreicht \u2013 Historien werden im "
            "Hintergrund nachgeladen, gleich erneut laden",
        "Double-click = history \u00b7 multi-select (Ctrl/Shift) + "
        "right-click = whole selection into the shopping list.":
            "Doppelklick = Verlauf \u00b7 Mehrfachauswahl (Strg/Shift) + "
            "Rechtsklick = ganze Auswahl in die Einkaufsliste.",
        # ---- Tooltips der Kopfzeile ----
        "Active trading place for all tabs (Daytrade, Swing, Industry). "
        "NPC hubs on top, your Upwell structures below. Scan "
        "again after switching.":
            "Aktiver Handelsplatz f\u00fcr alle Reiter (Daytrade, Swing, "
            "Bauen). NPC-Hubs oben, deine Upwell-Strukturen darunter. Beim "
            "Wechsel neu scannen.",
        "Scans the active hub (all buy/sell orders) \u2013 the basis for "
        "deals, swing candidates and industry. The first scan per hub "
        "loads a lot, then it is cached.":
            "Scannt den aktiven Hub (alle Buy/Sell-Orders) \u2013 die "
            "Grundlage f\u00fcr Deals, Swing-Kandidaten und Bauen. Erster "
            "Scan pro Hub l\u00e4dt viel, danach Cache.",
        "Loads the EVE database (SDE, ~140 MB, once) for category/meta "
        "filters, \u201ebelow build cost\u201c (swing) and the Industry "
        "tab. Stored locally afterwards.\n"
        "RIGHT-CLICK: deep-check values \u2013 compares every yield and "
        "ingredient amount against the game data.":
            "L\u00e4dt die EVE-Datenbank (SDE, ~140 MB, einmalig) f\u00fcr "
            "Kategorie-/Meta-Filter, \u201eUnter Baupreis\u201c (Swing) "
            "und den Bauen-Reiter. Danach lokal gespeichert.\n"
            "RECHTSKLICK: Werte tiefenpr\u00fcfen \u2013 vergleicht jede "
            "Ausbeute und Zutatenmenge gegen den Spielstand.",
        "Active character for ALL tabs (portfolio, profits, shopping and "
        "sell lists, order update \u2026). Every tab follows this choice "
        "automatically \u2013 you no longer pick one per tab.":
            "Aktiver Charakter f\u00fcr ALLE Reiter (Portfolio, Gewinne, "
            "Einkaufs-/Verkaufsliste, Order-Update \u2026). Beim Wechsel "
            "\u00fcbernehmen alle Tabs diesen Charakter automatisch \u2013 "
            "du musst ihn nicht mehr pro Reiter w\u00e4hlen.",
        "Checks whether EVE had an update (server version + blueprint "
        "data). If it changed: load blueprints again.\n"
        "Does NOT check the program \u2013 use the button next to it.":
            "Pr\u00fcft, ob EVE ein Update hatte (Server-Version + "
            "Baurezepte-Daten). Bei \u00c4nderung: Baurezepte neu laden.\n"
            "Pr\u00fcft NICHT das Programm \u2013 daf\u00fcr der Knopf "
            "daneben.",
        "Asks GitHub whether a newer version of the PROGRAM exists.\n"
        "Does NOT check the EVE data \u2013 use the button next to it.":
            "Fragt bei GitHub nach, ob es eine neuere Fassung des PROGRAMMS "
            "gibt.\nPr\u00fcft NICHT die EVE-Daten \u2013 daf\u00fcr der "
            "Knopf daneben.",
        "Deep-check values": "Werte tiefenpr\u00fcfen",
        "Compares every yield and ingredient amount of the loaded "
        "blueprints against the game data and reports what is out of date.":
            "Vergleicht jede Ausbeute und Zutatenmenge der geladenen "
            "Baurezepte gegen den Spielstand und meldet, wo etwas veraltet "
            "ist.",
        # ---- Tooltips: Daytrade-Feinfilter ----
        'Ready-made complete setting for the chosen mode: sets all filters in one click to target specific chances. As soon as you change something by hand, it switches to „Custom“.':
            'Fertige Komplett-Einstellung zum gewählten Modus: setzt alle Filter in einem Klick, um gezielt bestimmte Chancen zu finden. Sobald du danach etwas von Hand änderst, springt es auf „Eigene Einstellung“.',
        'Minimum quantity AT THE BEST price (both sides). A spread that only exists behind a throwaway 1-unit order is not a spread. 0 = off. Takes effect from the next market scan (older snapshots do not know the depth – then it deliberately does not filter instead of discarding everything).':
            'Mindest-Menge AM BESTEN Preis (beide Seiten). Ein Spread, der nur hinter einer 1-Stück-Wegwerf-Order existiert, ist keiner. 0 = aus. Greift erst ab dem nächsten Markt-Scan (ältere Snapshots kennen die Tiefe noch nicht - dann filtert er bewusst nicht, statt alles zu verwerfen).',
        'For the buy-and-hold strategy: hides items with a clear downtrend (falling knives), shows only sideways/rising ones that should return to the normal level.':
            'Für die Kaufen-Halten-Strategie: blendet Items mit klarem Abwärtstrend aus (fallende Messer), zeigt nur seitwärts/steigende, die zum Normalniveau zurückkehren dürften.',
        'Plausibility check for flips: the buy order price must be at least this percentage of the sell price. Excludes unrealistic „1 ISK ghost orders“ with fantasy margins. 40 % = only real, tradable spreads.':
            'Plausibilität für Flips: Der Kauf-Order-Preis muss mindestens so viel Prozent des Verkaufspreises betragen. Schließt unrealistische „1-ISK-Geister-Orders“ mit Fantasie-Marge aus. 40 % = nur echte, handelbare Spannen.',
        'Window for Ø price, volume and volatility.':
            'Zeitraum für Ø-Preis, Volumen und Volatilität.',
        'Minimum threshold in %: margin (flip), distance to the Ø (undervalued) or drop (bargain).':
            'Mindest-Schwelle in %: Marge (Flip), Abstand zum Ø (Unterbewertet) bzw. Drop (Schnäppchen).',
        'Minimum profit per unit in ISK. For large traders: filters out penny items despite good percentages.':
            'Mindest-Gewinn pro Stück in ISK. Für Groß-Trader: filtert Centartikel trotz guter Prozente raus.',
        'Days of stock: how many days the current stock lasts. High = flooded/sits for a long time. 0 = off.':
            'Bestandstage: wie viele Tage der aktuelle Bestand reicht. Hoch = überschwemmt/liegt lange. 0 = aus.',
        'Minimum swing range (high/low within the window). High = good for swing trading. 0 = off.':
            'Mindest-Schwankungsbreite (Hoch/Tief im Zeitfenster). Hoch = gut für Swing-Trading. 0 = aus.',
        'Max competition: hides items with more than this many competing orders. Little competition = you hold the top order more easily and are not constantly undercut (every repricing costs a relist fee). 0 = off.':
            'Max. Konkurrenz: blendet Items mit mehr als so vielen konkurrierenden Orders aus. Wenig Konkurrenz = du hältst leichter die Top-Order und wirst nicht ständig überboten (jede Neupreisung kostet Relist-Gebühr). 0 = aus.',
        'Min units/day you REALISTICALLY flip (daily volume ÷ competitors+1). 0 = off. Filters the „1-unit traps“: items where too much competition leaves you almost nothing – but keeps low-competition niches.':
            'Min Stück/Tag, die du REALISTISCH flippst (Tagesvolumen ÷ Konkurrenz+1). 0 = aus. Filtert die „1-Stück-Fallen“: Items, bei denen du wegen zu viel Konkurrenz kaum etwas abbekommst – behält aber konkurrenzarme Nischen.',
        # ---- Tooltips: Swing Trade ----
        'Ready-made filter setting for the chosen strategy: sets all filters in one click. As soon as you change something by hand, it switches to „Custom“.':
            'Fertige Filter-Einstellung zur gewählten Strategie: setzt alle Filter in einem Klick. Sobald du danach etwas von Hand änderst, springt es auf „Eigene Einstellung“.',
        'Upper limit: items further below normal than this are hidden – such extreme gaps are almost always data errors, not real dips.':
            'Obergrenze: Items, die weiter als dieser Wert unter Normal liegen, werden ausgeblendet – solche extremen Abstände sind fast immer Datenfehler, keine echten Dips.',
        'Minimum share of trading that (estimated) runs through SELL orders. High = your sell order fills well. Low = trading happens almost only on buy orders – your sell order sits. 0 = off.':
            'Mindest-Anteil des Handels, der (geschätzt) an SELL-Orders läuft. Hoch = deine Verkaufs-Order füllt sich gut. Niedrig = es wird fast nur an Buy-Orders gehandelt – deine Sell-Order bleibt liegen. 0 = aus.',
        'Minimum expected profit after fees if the item returns to its normal level.':
            'Mindest-erwarteter Gewinn nach Gebühren, wenn das Item zum Normalniveau zurückkehrt.',
        'Max days of stock: a high value means flooded. 0 = off.':
            'Max Bestandstage: hoher Wert = überschwemmt. 0 = aus.',
        'Window used to determine the normal level and the trend.':
            'Zeitraum, über den Normalniveau und Trend bestimmt werden.',
        'Exit liquidity: how many units per day you can realistically SELL again (daily volume ÷ sell competitors+1). Stops you sitting on stock the market barely absorbs. 0 = off.':
            'Exit-Liquidität: wie viele Stück/Tag du realistisch wieder VERKAUFEN kannst (Tagesvolumen ÷ Sell-Konkurrenten+1). Verhindert, dass du auf einem Bestand sitzenbleibst, den der Markt kaum abnimmt. 0 = aus.',
        'Absolute minimum profit per unit (ISK) on recovery – on top of „min exp. profit %“. Kills penny items that look great in percent but yield only a few ISK (the „25 ISK“ trap). 0 = off.':
            'Absoluter Mindest-Gewinn pro Stück (ISK) bei Erholung – zusätzlich zu „Min erw. Gewinn %“. Killt Cent-Items, die prozentual toll aussehen, aber nur ein paar ISK Gewinn bringen (die „25-ISK“-Falle). 0 = aus.',
        'Recovery quality (0–100): rising/stabilised = high (green), still falling = low (red). Already part of the ranking.':
            'Erholungs-Qualität (0–100): steigend/stabilisiert = hoch (grün), noch fallend = niedrig (rot). Fließt bereits ins Ranking ein.',
        'Capital efficiency: competition-adjusted profit/day per ISK tied up, in % per day. Two deals with the same profit/day are not equally good – the one tying up less ISK makes your capital work harder. High = ideal when capital is tight.':
            'Kapitaleffizienz: wettbewerbsbereinigter Gewinn/Tag pro gebundenem ISK, in % pro Tag. Zwei Deals mit gleichem Gewinn/Tag sind nicht gleich gut – der, der weniger ISK bindet, lässt dein Kapital härter arbeiten. Hoch = ideal bei knappem Kapital.',
        'Current price against the historical normal price (median). Small/negative = cheaper, a low entry (good). Strongly positive = the price has spiked → riskier buy entry, downgraded in the ranking.':
            'Aktueller Preis gegenüber dem historischen Normalpreis (Median). Klein/negativ = günstiger, tiefer Einstieg (gut). Stark positiv = Preis ist hochgeschossen → riskanter Buy-Einstieg, wird im Ranking abgewertet.',
        # ---- Tooltips: Regional Trading ----
        'Transport cost per m³ charged by your hauling service (jump freight / hauling). Deducted per item as volume × this rate – so you see the REAL profit after transport (profit/unit, margin and profit/m³ all include it). 0 = no deduction.':
            'Transportkosten pro m³, die dein Frachtdienst verlangt (Jump-Freight / Hauling). Wird je Item als Volumen × diese Rate vom Gewinn abgezogen – so siehst du den ECHTEN Gewinn nach Transport (auch Gewinn/Stk, Marge und Gewinn/m³ berücksichtigen ihn). 0 = kein Abzug.',
        'Cargo capacity of your ship/freighter in m³. Shows below what ONE run realistically yields: the tool mentally fills the hold with the best profit/m³ items (limited by demand at the destination) and shows the profit per trip after freight. 0 = no trip limit.':
            'Frachtkapazität deines Schiffs/Frachters in m³. Zeigt unten, was EINE Fuhre realistisch bringt: das Tool füllt den Frachtraum gedanklich mit den besten Gewinn/m³-Items (begrenzt durch die Nachfrage im Ziel) und zeigt den Gewinn pro Trip nach Fracht. 0 = kein Trip-Limit.',
        'Where you buy – the source. The sell price there counts.':
            'Wo du kaufst – Quelle. Es zählt der dortige Sell-Preis.',
        'Where you sell – the destination. The achievable price and the demand are checked here.':
            'Wo du verkaufst – Ziel. Hier wird der erzielbare Preis und die Nachfrage geprüft.',
        'Sell order: you place a sell order at the destination (higher price, broker fee). Immediate: sell straight into buy orders there (lower, no broker fee).':
            'Sell-Order: du stellst im Ziel eine Verkaufs-Order (höherer Preis, Broker Fee). Sofort: Verkauf direkt an Buy-Orders im Ziel (niedriger, keine Broker Fee).',
        'Ready-made filter setting: sets margin, profit, freight efficiency and liquidity in one click. As soon as you change something by hand, it switches to „Custom“. (Source/destination stay your choice.)':
            'Fertige Filter-Einstellung: setzt Marge, Gewinn, Fracht-Effizienz & Liquidität in einem Klick. Sobald du danach etwas von Hand änderst, springt es auf „Eigene Einstellung“. (Quelle/Ziel bleiben deine Wahl.)',
        'Minimum margin in % on the purchase price, after fees.':
            'Mindest-Gewinnspanne in % auf den Kaufpreis, nach Gebühren.',
        'Minimum profit per unit in ISK. Filters out penny items despite high percentages.':
            'Mindest-Gewinn pro Stück in ISK. Filtert Centartikel trotz hoher Prozente raus.',
        'Minimum demand at the destination: the quantity currently requested there by buy orders (a snapshot).':
            'Mindest-Nachfrage im Ziel: Stückzahl, die dort GERADE auf Buy-Orders nachgefragt wird (Momentaufnahme).',
        'Minimum Ø daily volume at the destination: how many units are actually traded there PER DAY (from the market history). The honest test whether the item sells there. 0 = off. NPC hubs only (structures have no history).':
            'Mindest Ø Tagesvolumen im Ziel: wie viele Stück dort tatsächlich PRO TAG gehandelt werden (aus der Markthistorie). Der ehrliche Test, ob das Item sich dort verkauft. 0 = aus. Nur für NPC-Hubs (Strukturen haben keine Historie).',
        # ---- Tooltips: Filter-Feinheiten und Einstellungen ----
        'THE daytrade proof from the in-game price table: per trading day it measures how deep the daily LOW reaches towards the buy order AND how high the daily HIGH reaches towards the sell order - the MINIMUM of both sides counts, averaged over the window. 100 % = both order sides are fully served every day (a perfect flip item, low at the bottom + high at the top). 0 = filter off.':
            'DER Daytrade-Beleg aus der Ingame-Preistabelle: pro Handelstag wird gemessen, wie tief das Tages-LOW zur Buy-Order reicht UND wie hoch das Tages-HIGH zur Sell-Order reicht - gewertet wird das MINIMUM beider Seiten, gemittelt über das Fenster. 100 % = jeden Tag werden BEIDE Order-Seiten voll bedient (perfektes Flip-Item, Low unten + High oben). 0 = Filter aus.',
        'Min tradability (0–100): how reliably the item is traded daily on BOTH sides – i.e. your buy order fills AND you get rid of it again through your sell order. High = ideal for day/hour trading. 60+ is strong, 35+ usable. 0 = off.':
            'Min Handelbarkeit (0–100): wie zuverlässig das Item täglich an BEIDEN Seiten gehandelt wird – d. h. deine Buy-Order wird gefüllt UND du wirst es über deine Sell-Order wieder los. Hoch = ideal fürs Day-/Stunden-Trading. 60+ ist stark, 35+ brauchbar. 0 = aus.',
        'Min buy fill (0–100 %): share of trading days with a real price spread (daily low < daily high). Only on such days is the BUY side served – your buy order fills. If low == high, only the sell side traded and your buy order sits. High = your buy orders fill reliably. 0 = off.':
            'Min Buy-Füllung (0–100 %): Anteil der Handelstage mit echter Preis-spanne (Tages-Tief < Tages-Hoch). Nur an solchen Tagen wird auch die BUY-Seite bedient – deine Kauf-Order füllt sich. Steht Tief == Hoch, wurde nur die Sell-Seite gehandelt und deine Buy-Order bleibt liegen. Hoch = deine Buy-Orders füllen zuverlässig. 0 = aus.',
        'Max % above normal price (0 = off): hides items whose current price is more than X % above the historical normal price (median) – the ones that have just spiked. That way you only buy on a low entry (in addition to the automatic score downgrade).':
            'Max % über Normalpreis (0 = aus): blendet Items aus, deren aktueller Preis mehr als X % über dem historischen Normalpreis (Median) liegt – die also gerade hochgeschossen sind. So kaufst du nur bei tiefem Einstieg (zusätzlich zur automatischen Score-Abwertung).',
        'Max fresh price SPIKE upwards (0 = off): compares the average of the last 3 trading days with the median before that. If the price is more than X % above it, it has JUST spiked - placing a buy order there is risky, because the price usually falls back and fills exactly then.\nASYMMETRIC: sudden price CRASHES are NOT filtered - buying cheap is the whole point.\nDifference to „max % above normal“: that measures the LEVEL (expensive for weeks), this one the fresh MOVEMENT (jumped yesterday).':
            'Max frischer Preis-SPRUNG nach oben (0 = aus): vergleicht den Schnitt der letzten 3 Handelstage mit dem Median davor. Liegt der Preis mehr als X % darüber, ist er GERADE hochgeschossen - dort eine Buy-Order zu setzen ist riskant, weil der Preis meist zurückfällt und ausgerechnet dann füllt.\nASYMMETRISCH: plötzliche Preis-STÜRZE werden NICHT gefiltert - billig einkaufen ist ja der Sinn der Sache.\nUnterschied zu „Max % über Normal“: das misst das NIVEAU (seit Wochen teuer), das hier die frische BEWEGUNG (gestern gesprungen).',
        'Sales tax EVE deducts on a sale. Included in every profit calculation.':
            'Verkaufssteuer, die EVE beim Verkauf abzieht. Wird in allen Gewinnrechnungen berücksichtigt.',
        'Broker fee in NPC stations when placing an order (reducible by skills/standing, min 1 %). Applies to buy AND sell orders, not to immediate trades.':
            'Broker-Gebühr in NPC-Stationen beim Einstellen einer Order (durch Skills/Standing reduzierbar, min 1 %). Fällt bei Buy- UND Sell-Orders an, nicht beim Sofort-Handel.',
        'Broker fee in player structures (Upwell): 0.5 % SCC surcharge plus the percentage set by the owner. NOT reducible by skills. Used in regional trading when the destination is a structure.':
            'Broker-Gebühr in Spieler-Strukturen (Upwell): 0,5 % SCC-Surcharge + der vom Besitzer gesetzte Prozentsatz. NICHT durch Skills reduzierbar. Wird im Region-Trading verwendet, wenn das Ziel eine Struktur ist.',
        'Which hub price counts as the sale: sell order (higher, with broker fee) or immediate to a buy order (lower, without).':
            'Welcher Jita-Preis als Verkauf gilt: Sell-Order (höher, mit Broker Fee) oder Sofort an Buy-Order (niedriger, ohne).',
        'On: player structures (Keepstars) can be used in regional trading. Needs structure scopes + re-linking.':
            'An: Spielerstrukturen (Keepstars) im Region-Trading nutzbar. Braucht Struktur-Scopes + Neu-Verknüpfen.',
        'On: the „open“ button opens the item in game. Needs the ui scope + re-linking + a logged-in character.':
            'An: „Öffnen“-Knopf öffnet das Item im Spiel. Braucht ui-Scope + Neu-Verknüpfen + eingeloggten Charakter.',
        "Tech level. LP/faction items are excluded on principle because their BPC cost (LP + ISK) cannot be calculated reliably.":
            "Tech-Stufe. LP-/Faction-Items werden grunds\u00e4tzlich ausgeschlossen, weil ihre BPC-Kosten (LP + ISK) nicht verl\u00e4sslich berechenbar sind.",
        # ---- Tooltips: Bauplan-Fenster ----
        'Time efficiency of the FINAL product only – for the build time.':
            'Zeit-Effizienz NUR des Endprodukts – für die Bauzeit.',
        'Which quantity pays off most? Shows the profit curve over quantity, including market depth on the sell side.':
            'Wie viel Menge lohnt sich am meisten? Zeigt Gewinn-Kurve über die Menge, inkl. Markttiefe beim Verkauf.',
        'Replaces the flat price of the shopping list with real sell order book prices – shows how expensive thin markets really are (one live request per material).':
            'Ersetzt den Flachpreis der Einkaufsliste durch echte Sell-Orderbuch-Preise – zeigt, wie teuer dünne Märkte wirklich sind (ein Live-Abruf pro Material).',
        'Less frequently used actions: load ESI data, quantity optimiser, order-book-accurate prices – and for frozen plans „reset frozen stock“.':
            'Seltener gebrauchte Aktionen: ESI-Daten laden, Mengen-Optimierer, orderbuch-genaue Preise – und bei eingefrorenen Plänen „Einfrier-Bestand neu setzen“.',
        'Fetches across all linked characters which original blueprints (BPO) you own and how many.':
            'Holt über alle verknüpften Charaktere, welche Original-Blueprints (BPO) du besitzt und wie viele.',
        'ISK per m³ of transport volume – e.g. the price of your hauling service.\nMultiplied by the total volume of the shopping list and charged ON TOP of the flat fee below.':
            'ISK je m³ Transportvolumen – z.B. der Preis deines Frachtdienstes.\nWird mit dem Gesamtvolumen der Einkaufsliste multipliziert und ZUSÄTZLICH zur Pauschale unten berechnet.',
        'A freely entered amount deducted from the profit – e.g. purchased BPCs, brokerage, corp dues.\nApplies to the WHOLE build plan, not per unit.':
            'Frei eingebbarer Betrag, der vom Gewinn abgezogen wird – z.B. gekaufte BPCs, Vermittlungsgebühren, Corp-Abgaben.\nGilt für den GESAMTEN Bauplan, nicht je Stück.',
        'Profit in relation to the total cost (build cost + transport).\nPositive = you earn, negative = you are paying in.':
            'Gewinn im Verhältnis zu den Gesamtkosten (Baukosten + Transport).\nPositiv = du verdienst, negativ = du legst drauf.',
        'No breakdown available – the plan was calculated without ESI adjusted prices (flat rate instead of the EIV formula).':
            'Keine Aufschlüsselung verfügbar – der Plan wurde ohne ESI-Adjusted-Preise gerechnet (Pauschale statt EIV-Formel).',
        # ---- Tooltips: Mengen-Optimierer ----
        'The buy and sell hub is chosen at the top left of the tool and applies to all tabs.':
            'Einkaufs- und Verkaufs-Hub wird oben links im Tool gewählt und gilt für alle Reiter.',
        'Your actual sell price per unit – FIXED, independent of quantity (you sell at your own price, no price decay on selling is assumed). Pre-filled with the sell/unit price from the build plan dialog, editable here. It only determines where the curve stops automatically (at the loss point) – the recommended build quantity does not depend on it.':
            'Dein tatsächlicher Verkaufspreis pro Stück – FEST, unabhängig von der Menge (du verkaufst zu deinem eigenen Preis, kein Preisverfall beim Verkauf angenommen). Vorbelegt mit dem Sell/Stk-Preis aus dem Bauplan-Dialog, hier änderbar. Bestimmt nur, wo die Kurve automatisch aufhört (am Verlustpunkt) – die Baumengen-Empfehlung selbst hängt nicht davon ab.',
        'Cargo space PER TRIP for the SHOPPING LIST (build materials) – NOT for the finished ships/items, which are completed at the build location. 0 = freight trips are not calculated.':
            'Frachtraum PRO FAHRT für die EINKAUFSLISTE (Baumaterialien) – NICHT für die fertigen Schiffe/Items, die werden ja am Bauort fertig. 0 = Frachtfahrten werden nicht berechnet.',
        'The hub is chosen at the top left of the tool and applies to all tabs.':
            'Hub wird oben links im Tool gewählt und gilt für alle Reiter.',
        # ---- Auswahl-Eintraege, Werkzeugleisten, Order-Tiefe, Regional ----
        'Recommended · best all-round flips':
            'Empfohlen · beste Allround-Flips',
        'Active at the PC · many quick flips':
            'Aktiv am PC · viele schnelle Flips',
        'Little time · place orders, check rarely':
            'Wenig Zeit · Order hinlegen, selten nachschauen',
        'Hidden gems · off the beaten track':
            'Geheimtipps · abseits der Masse',
        'Lots of capital · few large trades':
            'Viel Kapital · wenige große Trades',
        'Below Ø (return to the mean)':
            'Unter Ø (Rückkehr zum Schnitt)',
        'Price crash (wait for recovery)':
            'Preis-Crash (Erholung abwarten)',
        'Below build cost (cheaper than production)':
            'Unter Baupreis (billiger als Produktion)',
        'Sell via sell order':
            'Verkauf per Sell-Order',
        'Immediate to buy order':
            'Sofort an Buy-Order',
        'Load deals':
            'Deals laden',
        'Gold search':
            'Gold-Suche',
        '→ Shopping list':
            '→ Einkaufswagen',
        'Price':
            'Preis',
        'Cumulative':
            'Kumuliert',
        'Cost':
            'Kosten',
        'Ø up to here':
            'Ø bis hier',
        'worth it':
            'lohnt',
        'CONTAINER':
            'CONTAINER',
        'Hide all containers':
            'Alle Container ausblenden',
        'ROUTE & STRATEGY':
            'ROUTE & STRATEGIE',
        'Route & strategy – where to buy, where to sell':
            'Route & Strategie – wo kaufen, wo verkaufen',
        'Buy in':
            'Kaufen in',
        'Sell in':
            'Verkaufen in',
        'Sale type':
            'Verkaufs-Art',
        'FREIGHT':
            'FRACHT',
        'Transport cost (ISK/m³)':
            'Transportkosten (ISK/m³)',
        'Cargo hold (m³)':
            'Frachtraum (m³)',
        # ---- Ladebildschirm und Unterreiter ----
        '◈ TRADING TIP':
            '◈ TRADING-TIPP',
        'Cancel':
            'Abbrechen',
        'Refreshing portfolio + prices …':
            'Aktualisiere Portfolio + Preise …',
        'Computing deals …':
            'Berechne Deals …',
        'Gold search …':
            'Gold-Suche …',
        'Searching for missing blueprints …':
            'Suche fehlende Blueprints …',
        'Searching contracts …':
            'Contracts durchsuchen …',
        'Searching swing candidates …':
            'Suche Swing-Kandidaten …',
        'Calculating the floor …':
            'Rechne Boden auf …',
        'Searching your structures …':
            'Suche deine Strukturen …',
        'Searching regional arbitrage …':
            'Suche Regional-Arbitrage …',
        'Sell list':
            'Verkaufsliste',
        'Load prices':
            'Preise laden',
        'Copy prices → in game':
            'Preise → Ingame kopieren',
        'Clear list':
            'Liste leeren',
        'Fill from portfolio':
            'Aus Portfolio füllen',
        'Copy undercut sell':
            'Unterbietende Sell-Preise kopieren',
        # ORDERS JE CHARAKTER (Nutzer-Befund 22.09.2026)
        'Hide active orders':
            'Positionen mit offener Kauf-Order ausblenden',
        # Order-Leiter (Daytrade/Swing/Regional), 22.09.2026
        'Add to shopping list':
            'In den Einkaufswagen',
        'Quantity:':
            'Menge:',
        'Selected: {name}':
            'Gew\u00e4hlt: {name}',
        'No item selected \u2013 click one in the list.':
            'Kein Item gew\u00e4hlt \u2013 eines in der Liste anklicken.',
        'How many units of the selected item go into the shopping list. Preset with a sensible suggestion \u2013 overwrite it as you like.':
            'Wie viele St\u00fcck des gew\u00e4hlten Items in den Einkaufswagen gehen. Mit einem sinnvollen Vorschlag vorbelegt \u2013 einfach \u00fcberschreiben.',
        "Hides items for which THIS character still has an open buy order in game \u2013 the stack is still being bought up.\nAn order belonging to another of your characters never hides anything: it says nothing about this character's stock.":
            'Blendet Positionen aus, f\u00fcr die DIESER Charakter im Spiel noch eine offene Kauf-Order hat \u2013 der Stack wird also noch aufgekauft.\nDie Order eines anderen deiner Charaktere blendet nie etwas aus: sie sagt \u00fcber den Bestand dieses Charakters nichts.',
        '{n} Item(s)':
            '{n} Item(s)',
        '{n} Item(s) \u2013 {k} hidden (open buy order)':
            '{n} Item(s) \u2013 {k} ausgeblendet (offene Kauf-Order)',
        'Buy order at: {chars}':
            'Kauf-Order bei: {chars}',
        'Sell order at: {chars}':
            'Verkaufs-Order bei: {chars}',
        "Another character of yours \u2013 it says nothing about THIS character's stock, which is why it does not mark this row.":
            'Ein anderer deiner Charaktere \u2013 das sagt \u00fcber den Bestand DIESES Charakters nichts, deshalb markiert es diese Zeile nicht.',
        # Einkaufswagen ohne "In buy order?" (Nutzer 22.09.2026)
        "Less frequently used actions: load prices, quantity suggestion \u2013 and at the very bottom \u201eClear list\u201c.":
            "Seltener gebrauchte Aktionen: Preise laden, Mengenvorschlag \u2013 und ganz unten \u201eListe leeren\u201c.",
        "Only daytrade items in the list (or list empty) \u2013 they do NOT belong in the multibuy. Use the buy order suggestion above instead.":
            "Nur Daytrade-Items in der Liste (oder Liste leer) \u2013 die geh\u00f6ren NICHT in den Multibuy. Nimm daf\u00fcr den Kauf-Order-Vorschlag oben.",
        " ({n} daytrade item(s) in the list, but they do NOT belong in Multibuy \u2013 use the buy-order suggestion above for those.)":
            " ({n} Daytrade-Item(s) in der Liste, die geh\u00f6ren aber NICHT in den Multibuy \u2013 nimm daf\u00fcr den Kauf-Order-Vorschlag oben.)",
        'Sold':
            'Verkauft',
        'Current sell':
            'Aktueller Sell',
        'Sell price':
            'Verkaufspreis',
        # DER KOPF SAGT DEN MODUS (Nutzer 22.09.2026). Dieselbe Spalte
        # traegt zwei verschiedene Zahlen-Arten - der Kopf nennt sie.
        'Sell price (target)':
            'Verkaufspreis (Ziel-Marge)',
        'Sell price (undercut)':
            'Verkaufspreis (Undercut)',
        'Proceeds (net)':
            'Erlös (netto)',
        'Exp. profit':
            'Erw. Gewinn',
        'All at target price':
            'Alle zum Ziel-Preis',
        'Open':
            'Öffnen',
        'Order update':
            'Order-Update',
        'Check orders':
            'Orders prüfen',
        'Next ▶':
            'Nächste ▶',
        'Buy orders (outbid?)':
            'Buy-Orders (Überboten?)',
        'Sell orders (undercut?)':
            'Sell-Orders (Unterboten?)',
        'Your order':
            'Deine Order',
        'Best buy':
            'Bester Buy',
        'Best sell':
            'Bester Sell',
        'New price':
            'Neuer Preis',
        'Price history':
            'Kursverlauf',
        'Item:':
            'Item:',
        'Copy multibuy':
            'Multibuy kopieren',
        'Work-through mode':
            'Abarbeiten-Modus',
        'Total cost':
            'Gesamtkosten',
        'Suggested quantity':
            'Vorgeschlagene Menge',
        'Character':
            'Charakter',
        'Action':
            'Aktion',
        'Remove':
            'Entfernen',
        'Link character':
            'Charakter verknüpfen',
        'Link your EVE characters with the official login. Only a refresh token is stored securely – no password.':
            'Verknüpfe deine EVE-Charaktere per offiziellem Login. Es wird nur ein Refresh-Token sicher gespeichert – kein Passwort.',
        # ---- Daytrade-Presets und Gold-Fenster ----
        # NICHT HIER: die Strategienamen (Spanne/Stunden/Konkurrenz/
        # Nische/Kapital) sind DICT-SCHLUESSEL in der Gold-Suche und
        # laufen als Datenwert durch die Logik. Uebersetzt gehoeren
        # sie erst beim ANZEIGEN in der Spalte "Gefunden in" -
        # ein eigener, noch offener Schritt.
        'Recommended · all prices':
            'Empfohlen · alle Preise',
        'Recommended · cheap only (up to 300k)':
            'Empfohlen · nur günstig (bis 300k)',
        'Recommended · mid range (300k–20M)':
            'Empfohlen · Mittelklasse (300k–20M)',
        'Recommended · expensive (from 20M)':
            'Empfohlen · teuer (ab 20M)',
        'Active at the PC · maximum turnover (cheap)':
            'Aktiv am PC · maximaler Umschlag (günstig)',
        'Active at the PC · mid range':
            'Aktiv am PC · Mittelklasse',
        'Little time · hardly any competition':
            'Wenig Zeit · kaum Konkurrenz',
        'Little time · solid margin':
            'Wenig Zeit · solide Marge',
        'Little time · expensive single items':
            'Wenig Zeit · teure Einzelstücke',
        'Hidden gems · overlooked mid range':
            'Geheimtipps · übersehene Mittelklasse',
        'Hidden gems · higher margin':
            'Geheimtipps · höhere Marge',
        'Lots of capital · efficiently tied up':
            'Viel Kapital · effizient gebunden',
        'Lots of capital · big single trades':
            'Viel Kapital · dicke Einzeltrades',
        'Gold search – the best flip chances':
            'Gold-Suche – die besten Flip-Chancen',
        'Capital you want to use:':
            'Kapital, das du einsetzen willst:',
        'Rank':
            'Rang',
        'Price (sell)':
            'Preis (Sell)',
        'Found in':
            'Gefunden in',
        'Gold score':
            'Gold-Score',
        'Selection → shopping list':
            'Auswahl → Einkaufswagen',
        # ---- Handelsplan ----
        'Capital':
            'Kapital',
        'Action':
            'Aktion',
        'Buy':
            'Kaufen',
        "Buy": "Kaufen",
        "Buy price": "Kaufpreis",
        # ---- Restliche Anzeigetexte (Sitzung 12, letzte Runde) ----
        'Loading …':
            'Lädt …',
        'Hide downtrends':
            'Abwärtstrends ausblenden',
        'Checking …':
            'Prüfe …',
        '✓ Apply':
            '✓ Übernehmen',
        '— Choose profile —':
            '— Profil wählen —',
        '＋ Add structure …':
            '＋ Struktur hinzufügen …',
        'Open':
            'Öffnen',
        'MY BUILD PLANS':
            'MEINE BAUPLÄNE',
        'Check finished status (ESI)':
            'Fertig-Status prüfen (ESI)',
        'PROFIT OVERVIEW':
            'GEWINN-ÜBERSICHT',
        'Not loaded yet – press „↻ Load blueprints“.':
            'Noch nicht geladen – „↻ Blueprints laden“ drücken.',
        'Add structure':
            'Struktur hinzufügen',
        'Right-click a structure here to remove it from the list.':
            'Rechtsklick auf eine Struktur hier entfernt sie aus der Liste.',
        'Remove \u201e{name}\u201c from the list':
            '\u201e{name}\u201c aus der Liste entfernen',
        'Remove structure':
            'Struktur entfernen',
        'Remove \u201e{name}\u201c from the hub list? Your orders and data there stay; you can add it again any time.':
            '\u201e{name}\u201c aus der Hub-Liste entfernen? Deine Orders und Daten dort bleiben; du kannst sie jederzeit wieder hinzufügen.',
        'Structure removed from the hub list.':
            'Struktur aus der Hub-Liste entfernt.',
        'Open build plan':
            'Bauplan öffnen',
        'Open price history':
            'Kursverlauf öffnen',
        'Checking structure access …':
            'Prüfe Struktur-Zugang …',
        'Loading order books …':
            'Lade Orderbücher …',
        'Add':
            'Hinzufügen',
        'Expected proceeds (net)':
            'Erwarteter Erlös (netto)',
        'Buy order suggestion – select an item in the list':
            'Buy-Order-Vorschlag – Item in der Liste wählen',
        'Apply as quantity':
            'Als Menge übernehmen',
        'Hide temporarily':
            'Vorübergehend ausblenden',
        'Fees actual (journal)':
            'Gebühren echt (Journal)',
        'Buys only':
            'Nur Käufe',
        'Sales only':
            'Nur Verkäufe',
        'On (open market in game)':
            'An (Markt ingame öffnen)',
        '⬇ Check for a new program version':
            '⬇ Auf neue Programm-Version prüfen',
        'Fees from skills (EVE-exact, NPC station)':
            'Gebühren aus Skills (EVE-genau, NPC-Station)',
        'Storage & cleanup':
            'Speicher & Aufräumen',
        '↻ Refresh size':
            '↻ Größe aktualisieren',
        'Delete old transactions':
            'Alte Transaktionen löschen',
        'No build plans saved yet. Open a build plan and click „Save build plan“.':
            'Noch keine gespeicherten Baupläne. Öffne einen Bauplan und klicke „Bauplan speichern“.',
        'No structures yet. Add your first one.':
            'Noch keine Strukturen. Füge deine erste hinzu.',
        'WHICH STRUCTURE FOR WHICH ACTIVITY?':
            'WELCHE STRUKTUR FÜR WELCHE AKTIVITÄT?',
        'Please choose source and destination above.':
            'Bitte oben Quelle und Ziel wählen.',
        'No order data available for this item.':
            'Für dieses Item liegen keine Order-Daten vor.',
        'Nothing pasted.':
            'Nichts eingefügt.',
        'Fee source':
            'Gebühren-Quelle',
        'Transactions older than:':
            'Transaktionen älter als:',
        'Check recipes':
            'Rezepte prüfen',
        'No character linked':
            'Kein Charakter verknüpft',
        'No EVE character is linked yet.':
            'Es ist noch kein EVE-Charakter verknüpft.',
        'No linked characters.':
            'Keine verknüpften Charaktere.',
        'For „below build cost“ load the blueprints first.':
            'Für „Unter Baupreis“ zuerst „Baurezepte laden“.',
        'Searching hold candidates (loading price histories) …':
            'Suche Halten-Kandidaten (lade Preisverläufe) …',
        # ---- Letzte Anzeigetexte (Sitzung 12) ----
        '+ Add structure':
            '+ Struktur hinzufügen',
        "Searching public contracts across New Eden \u2026 (takes a few minutes)":
            "Suche \u00f6ffentliche Contracts in ganz New Eden \u2026 (dauert ein paar Minuten)",
        'Paste the hangar selection here (select everything in the inventory, Ctrl+C) – one line per item. The name is enough; quantity and group may follow.':
            'Hangar-Auswahl hier einfügen (im Inventar alles markieren, Strg+C) – eine Zeile je Item. Es reicht der Name; Menge und Gruppe dürfen dranstehen.',
        'No system selected – search for a build system above (e.g. „Jita“) for the live cost index.':
            'Kein System gewählt – oben ein Bau-System suchen (z. B. „Jita“) für den Live-Kosten-Index.',
        'Load the blueprints first (that also loads the category/tech data).':
            'Erst „Baurezepte laden“ (lädt auch die Kategorie-/Tech-Daten).',
        'Please run „Market scan“ in the Daytrade or Swing tab first (for material prices).':
            'Bitte zuerst im Daytrade- oder Swing-Tab „Markt-Scan“ (für Materialpreise).',
        'No daily volume known – click „Load prices“ (loads order depth and daily volume). Without history I cannot suggest an order size.':
            'Kein Tagesvolumen bekannt – auf „Preise laden“ klicken (lädt Order-Tiefe und Tagesvolumen). Ohne Historie kann ich keine Ordergröße vorschlagen.',
        'No character linked – please log in under „Characters“ first.':
            'Kein Charakter verknüpft – bitte zuerst unter „Charaktere“ einloggen.',
        'Assumed: you own the blueprint (unlimited) – no invention needed for this item.':
            'Angenommen: eigene Blaupause vorhanden (unbegrenzt) - keine Invention nötig für dieses Item.',
        'ESI data active – the run planner uses it directly for scheduling.':
            'ESI-Daten aktiv - der Runplaner nutzt sie direkt für die Zeitplanung.',
        'No characters linked – add them in the Characters tab.':
            'Keine Charaktere verknüpft – im Charaktere-Tab hinzufügen.',
        'Items without your own blueprint are assumed to be unlimited (you buy or copy them).':
            'Items ohne eigene Blaupause werden als unbegrenzt verfügbar angenommen (kaufst/kopierst sie eben).',
        'No character linked – link one under „Characters“, then real blueprints load automatically.':
            'Kein Charakter verknüpft - unter "Charaktere" verknüpfen, dann werden echte Blaupausen automatisch geladen.',
        'not estimable':
            'nicht schätzbar',
        'Could not read skills/standings for any character – the scope may be missing, link again once.':
            'Konnte bei keinem Charakter Skills/Standings lesen - Scope fehlt evtl., einmal neu verknüpfen.',
        'All blueprints your linked characters own (via ESI, wherever they are).':
            'Alle Blueprints, die deine verknüpften Charaktere besitzen (per ESI, egal wo sie liegen).',
        'Merged from „below Ø“ and „price crash“. Rated by discount depth × expected recovery profit × safety × resaleability.':
            'Zusammengeführt aus „unter Ø“ + „Preis-Crash“. Bewertet nach Rabatt-Tiefe × Erwartetem Erholungs-Gewinn × Sicherheit × Wiederverkaufbarkeit.',
        "Units": "Stück",
        "Surplus": "Überschuss",
        "Paste here if ESI is not fast enough.":
            "Einfügen, falls ESI nicht schnell genug ist.",
        "No characters / client ID linked.": "Keine Charaktere/Client-ID verknüpft.",
        # ---- Nutzer-Screenshots Sitzung 12: Container, Zeitfenster, Presets ----
        'Trade / container':
            'Handeln / Container',
        'Qty':
            'Menge',
        'Hub value':
            'Jita-Wert',
        '{n} days':
            '{n} Tage',
        '1 year':
            '1 Jahr',
        'Max':
            'Max',
        '{hub}: {n} items captured. „Load deals“.':
            '{hub}: {n} Items erfasst. „Deals laden“.',
        'Min margin':
            'Min Marge',
        'Min profit/unit (ISK)':
            'Min Gewinn/Stk (ISK)',
        'Min demand (buy now)':
            'Min Nachfrage (Buy jetzt)',
        'Min Ø daily volume destination':
            'Min Ø Tagesvolumen Ziel',
        'Min profit/m³ (ISK)':
            'Min Gewinn/m³ (ISK)',
        'Price from':
            'Preis ab',
        'Price to (0=∞)':
            'Preis bis (0=∞)',
        'Sell (destination)':
            'Verkauf (Ziel)',
        'Profit/m³':
            'Gewinn/m³',
        'm³/unit':
            'm³/Stk',
        'Demand destination':
            'Nachfrage Ziel',
        'Supply destination':
            'Angebot Ziel',
        'Ø daily vol destination':
            'Ø Tagesvol Ziel',
        'Small safe dips · quick recovery':
            'Kleine sichere Dips · schnelle Erholung',
        'Deep dips · patience & a thick cushion':
            'Tiefe Dips · Geduld & dickes Polster',
        'Collect bulk goods · high volume':
            'Massenware einsammeln · hohes Volumen',
        'Safe exit · easy to resell':
            'Sicherer Exit · leicht wieder verkaufbar',
        'Balanced · solid 8 %+':
            'Ausgewogen · solide 8 %+',
        'Expensive chunks · capital & fat margin':
            'Teure Brocken · Kapital & dicke Marge',
        'Safe margin (liquid destinations)':
            'Sichere Marge (liquide Ziele)',
        'Freight-efficient (profit/m³)':
            'Fracht-effizient (Gewinn/m³)',
        'Cheap bulk (high volume)':
            'Billig-Bulk (hohes Volumen)',
        'Expensive niche (fat margin)':
            'Teure Nische (dicke Marge)',
        'Instant sale (out fast)':
            'Sofortverkauf (schnell raus)',
        "{n} items captured in {hub}. Now „Load deals“.":
            "{n} Items in {hub} erfasst. Jetzt „Deals laden“.",
        "{hub}: {n} items captured. „Load recipes“ (once), then „Find blueprints“.":
            "{hub}: {n} Items erfasst. „Baurezepte laden“ (einmalig), dann „Blaupausen suchen“.",
        "„Load deals“.": "„Deals laden“.",
        "„Load recipes“, then „Find blueprints“.":
            "„Baurezepte laden“, dann „Blaupausen suchen“.",
        '\u26a0 No market scan yet \u2013 run it once.':
            '\u26a0 Noch kein Markt-Scan \u2013 einmal ausf\u00fchren.',
        # ---- Zielzeit je Stufe im Runplaner (24.09.2026) ----
        'Target per stage:': 'Ziel je Stufe:',
        'as fast as possible': 'so schnell wie m\u00f6glich',
        '{n} h': '{n} h',
        '{n} d': '{n} T',
        '{d} d {h} h': '{d} T {h} h',
        'How long may THIS stage run? Days and hours together. The first '
        'entry is \u201eas fast as possible\u201c \u2013 the time the stage '
        'needs anyway; anything shorter is not offered because it would '
        'not change the plan. The more time you give it, the fewer '
        'blueprints and slots the planner uses.':
            'Wie lange darf DIESE Stufe laufen? Tage und Stunden zusammen. '
            'Der erste Eintrag ist \u201eso schnell wie m\u00f6glich\u201c \u2013 die '
            'Zeit, die die Stufe ohnehin braucht; k\u00fcrzer wird gar nicht '
            'angeboten, weil es am Plan nichts \u00e4ndern w\u00fcrde. Je mehr '
            'Zeit du ihr gibst, desto weniger Blaupausen und Slots nimmt der '
            'Planer.',
        'as long as it takes': 'so lange wie n\u00f6tig',
        'Shorter than {d} is not possible: {name} needs {runs} run(s) '
        'and can use {slots} slot(s) at once. More characters or more '
        'blueprint copies for that item would shorten it.':
            'K\u00fcrzer als {d} geht nicht: {name} braucht {runs} Run(s) '
            'und kann {slots} Slot(s) gleichzeitig nutzen. Mehr Charaktere '
            'oder mehr Blaupausen-Kopien dieses Items w\u00fcrden es verk\u00fcrzen.',
        '(building {n}/{m})': '(im Bau {n}/{m})',
        'How long may a stage run? The planner then uses as few '
        'blueprints and slots as fit into that time \u2013 a stage is '
        'finished only when its longest job is, so the shorter ones may '
        'be stretched for free. Each stage can be set separately in its '
        'own row below.':
            'Wie lange darf eine Stufe laufen? Der Planer nimmt dann so wenige '
            'Blaupausen und Slots, wie in die Zeit passen \u2013 eine Stufe ist '
            'ohnehin erst fertig, wenn ihr l\u00e4ngster Job fertig ist, die '
            'k\u00fcrzeren d\u00fcrfen also gratis gestreckt werden. Jede Stufe '
            'l\u00e4sst sich unten in ihrer eigenen Zeile einzeln einstellen.',
        # ---- Plan-Farben (23.09.2026) ----
        'Colour of this build plan \u2013 click to choose.':
            'Farbe dieses Bauplans \u2013 zum Ausw\u00e4hlen klicken.',
        'No colour': 'Keine Farbe',
        # ---- Multi-Bauplan: Karte einklappen (23.09.2026) ----
        'Hide the end products of this bundle':
            'Endprodukte dieses B\u00fcndels einklappen',
        'Show the end products of this bundle':
            'Endprodukte dieses B\u00fcndels ausklappen',
        # ---- Kopfzeile (23.09.2026) ----
        'Structure: add an Upwell structure as a trading place (needs a linked character with market/docking access and the structure scope). Selectable in the dropdown afterwards.':
            'Struktur: eine Upwell-Struktur als Handelsplatz hinzuf\u00fcgen (braucht einen verkn\u00fcpften Charakter mit Markt-/Andockrecht und den Struktur-Scope). Danach im Dropdown w\u00e4hlbar.',
        # ---- Handels-Reiter: rechte Leiste (23.09.2026) ----
        # Zwei Gruppen wie in der Bau-Rail: erst suchen, dann in den Wagen.
        'DEALS':
            'ANGEBOTE',
        'SHOPPING LIST':
            'EINKAUFSWAGEN',
        # ---- Industrie-Reiter: rechte Leiste und Plan-Karten ----
        'PLANNING':
            'PLANEN',
        'Scanner':
            'Scanner',
        'My blueprints':
            'Meine Blueprints',
        'PRODUCTION':
            'PRODUKTION',
        'New build plan':
            'Neuer Bauplan',
        'My build plans':
            'Meine Baupläne',
        'SETUP':
            'SETUP',
        'Structures':
            'Strukturen',
        "Done":
            "Fertig",
        'Mark the plan as COMPLETED by hand – e.g. when the invention did not cover every unit and the ESI check therefore never reaches the full quantity.\nAn existing material reservation is RELEASED: the material is used up, other plans should no longer see it as blocked.':
            'Plan von Hand als ABGESCHLOSSEN markieren – z.B. wenn die Invention nicht für alle Stück gereicht hat und der ESI-Check deshalb nie auf die volle Menge kommt.\nEine bestehende Material-Reservierung wird dabei FREIGEGEBEN: das Material ist verbaut, andere Pläne sollen es nicht länger als blockiert sehen.',
        'Profit ≈ {isk} ISK':
            'Gewinn ≈ {isk} ISK',
        '✅ Completed':
            '✅ Abgeschlossen',
        'Build {cost}/unit':
            'Bau {cost}/Stk',
        "Sell {sell}": "Verkauf {sell}",
        "Recommended sale per unit: {sell}\nClick copies it to the clipboard "
        "\u2013 paste it into the price field of the sell order in game.":
            "Empfohlener Verkauf pro St\u00fcck: {sell}\nKlick kopiert ihn in die "
            "Zwischenablage \u2013 ins Preisfeld der Verkaufsorder im Spiel "
            "einf\u00fcgen.",
        "In bundle: build {cost}/unit": "Im B\u00fcndel: Bau {cost}/Stk",
        "Built through multi build plan \u201e{multi}\u201c. Build cost per unit "
        "is this product's share of the bundle (shared intermediates split by "
        "demand): {cost}. The sell price reaches your target margin after fees; "
        "the profit is sale at the last market scan minus fees minus that share.":
            "Wird \u00fcber den Multi-Bauplan \u201e{multi}\u201c gebaut. Die Baukosten "
            "je St\u00fcck sind der Anteil dieses Produkts am B\u00fcndel (geteilte "
            "Zwischenprodukte nach Bedarf aufgeteilt): {cost}. Der Verkaufspreis "
            "erreicht nach Geb\u00fchren deine Ziel-Marge; der Gewinn ist Verkauf zum "
            "letzten Markt-Scan minus Geb\u00fchren minus dieser Anteil.",
        "Built through multi build plan \u201e{multi}\u201c. Build cost per unit "
        "is this product's share of the bundle (shared intermediates split by "
        "demand); the profit is sale at the last market scan minus fees minus "
        "that share \u2013 all end products add up to the bundle's total profit.":
            "Wird \u00fcber den Multi-Bauplan \u201e{multi}\u201c gebaut. Die Baukosten "
            "je St\u00fcck sind der Anteil dieses Produkts am B\u00fcndel (geteilte "
            "Zwischenprodukte nach Bedarf aufgeteilt); der Gewinn ist Verkauf zum "
            "letzten Markt-Scan minus Geb\u00fchren minus dieser Anteil \u2013 alle "
            "Endprodukte zusammen ergeben den Gesamtgewinn des B\u00fcndels.",
        "End product of multi build plan {name}":
            "Endprodukt des Multi-Bauplans {name}",
        "Sell/unit at last scan: {sell}":
            "Verkauf/Stk zum letzten Scan: {sell}",
        "Built through the multi build plan: its shopping list contains this "
        "product, shared intermediates are counted once. Build cost per unit "
        "is this product's share of the bundle; profit per end product adds "
        "up to the bundle's total profit.":
            "Wird \u00fcber den Multi-Bauplan gebaut: seine Einkaufsliste enth\u00e4lt "
            "dieses Produkt, geteilte Zwischenprodukte z\u00e4hlen einmal. Die "
            "Baukosten je St\u00fcck sind der Anteil dieses Produkts am B\u00fcndel; "
            "der Gewinn je Endprodukt summiert sich zum Gesamtgewinn des B\u00fcndels.",
        'Build price per unit: {cost}\nRecommended sale per unit: {sell}':
            'Baupreis pro Stück: {cost}\nEmpfohlener Verkauf pro Stück: {sell}',
        # ---- Tooltips: Bauplan-Reiter ----
        'Hides the normal result list and fine filters and shows ONLY the capital ships (carrier/dreadnought/FAX/titan/supercarrier/freighter) filling the window – since capitals have no market price, they need different filters anyway. Right-click a ship to open its build plan directly.':
            'Blendet die normale Ergebnisliste + Feinfilter aus und zeigt NUR die Capital-Schiffe (Carrier/Dreadnought/FAX/Titan/Supercarrier/Freighter) füllend im Fenster - da Capitals keinen Marktpreis haben, brauchen sie sowieso andere Filter als der Rest. Rechtsklick auf ein Schiff öffnet direkt den Bauplan.',
        'Save and load the whole build setup (system, structure, rigs, ME/TE, decryptor, surplus …) as a profile – so you do not have to set everything up again.':
            'Ganzes Bau-Setup (System, Struktur, Rigs, ME/TE, Decryptor, Überschuss …) als Profil speichern und laden – damit du nicht alles neu einstellst.',
        'Decryptor for invention (changes success chance and runs → invention cost per unit).':
            'Decryptor für Invention (ändert Erfolgschance & Runs → Invention-Kosten pro Stück).',
        'Recomputes the exact build-plan maths for EVERY result below (batch size and rounding effects, real job costs) instead of the quick per-unit estimate – quantity = Ø daily volume (a realistic build and sell size). Takes a few seconds to a minute depending on the number of hits. Results are kept for this session only (RAM, no file) – no data litter on the disk.':
            'Rechnet für JEDES Ergebnis unten die genaue Bauplan-Rechnung nach (Losgrößen-/Rundungseffekte, echte Job-Kosten) statt der schnellen Pro-Stück-Schätzung - Menge = Ø Tagesvolumen (realistische Bau-/Verkaufsgröße). Dauert je nach Trefferzahl ein paar Sekunden bis eine Minute. Ergebnisse werden nur für diese Sitzung gemerkt (RAM, keine Datei) - kein Datenmüll auf der Platte.',
        'Searches public contracts in ALL regions for capital sales and derives a reference value per ship type. Capitals are sold everywhere, not only in the hub – a scan over a single region yields no price at all for many types, or just one.\nTAKES LONGER (all of New Eden instead of one region, several minutes depending on time of day).\nThe MEDIAN is shown (the middle price): contract prices regularly have outliers on the high side that would skew an average. The average is in the tooltip of the cell next to it.\nPublic offers only – ESI sees alliance-internal contracts only through a character with the director or accountant role in that corp, which this scan does not cover.':
            'Durchsucht öffentliche Contracts in ALLEN Regionen nach Capital-Verkäufen und bildet daraus einen Richtwert je Schiffstyp. Capitals werden überall verkauft, nicht nur im Hub - ein Scan über nur eine Region liefert für viele Typen gar keinen oder nur einen einzigen Preis.\nDAUERT LÄNGER (ganz New Eden statt einer Region, je nach Tageszeit mehrere Minuten).\nAngezeigt wird der MEDIAN (der mittlere Preis): Contract-Preise haben regelmäßig Ausreißer nach oben, die einen Mittelwert verziehen würden. Der Mittelwert steht im Tooltip der Zelle daneben.\nNur öffentliche Angebote - Allianz-interne Contracts sieht ESI nur über einen Charakter mit Director/Accountant-Rolle in der jeweiligen Corp, das deckt dieser Scan nicht ab.',
        # ---- Tooltips: Bauplan-Fenster ----
        'On: ME/TE are freely editable here and the invention maths above in this panel is ignored for this end product (no invention cost) – e.g. when you already own the BPC or want to buy it instead of inventing it.':
            'An: ME/TE hier frei editierbar, die Invention-Rechnung oben in diesem Panel wird für dieses Endprodukt ignoriert (keine Invention-Kosten) - z.B. wenn du die BPC schon besitzt oder kaufen willst, statt sie zu erfinden.',
        'How many runs does ONE of your own BPCs have (not a BPO – a blueprint copy runs out eventually)? From that the tool works out how many BPC copies you need for the quantity set above – otherwise the run planner cannot split the end product across build slots and characters.':
            'Wie viele Runs hat EINE deiner eigenen BPCs (nicht BPO - eine Blueprint-Kopie ist irgendwann aufgebraucht)? Daraus errechnet das Tool automatisch, wie viele BPC-Kopien du für die oben eingestellte Menge brauchst - sonst weiß der Runplaner nicht, wie er das Endprodukt auf Bau-Slots/Charaktere aufteilen soll.',
        'ON: freezes the PLAN – recipe structure, buy/build decisions, quantities and run planner are fixed from now on (along with purchase prices, the job cost basis and the PURCHASING stock as of NOW). That way you can work on the run planner for days without it recalculating behind your back. PROGRESS is ticked off automatically from your ESI jobs (runs delivered since freezing), and ONLY the sell price of the end product stays live – so weeks later you still see the real profit against the purchase costs OF THAT TIME.\nOFF: back to live prices, live stock and a live plan.':
            'AN: friert den PLAN ein - Rezept-Struktur, Kauf/Bau-Entscheidungen, Mengen und Runplaner stehen ab jetzt fest (dazu Einkaufspreise, Jobkosten-Basis und der EINKAUFS-Bestand vom Stand JETZT). Am Runplaner kann man damit tagelang arbeiten, ohne dass er sich unter der Hand neu rechnet. Der FORTSCHRITT wird aus deinen ESI-Jobs automatisch abgehakt (gelieferte Runs seit dem Einfrieren), und NUR der Verkaufspreis des Endprodukts bleibt live - so sieht man in Wochen noch den echten Gewinn gegen die DAMALIGEN Einkaufskosten.\nAUS: zurück zu Live-Preisen, Live-Bestand und Live-Plan.',
        'Sets ONLY the frozen STOCK to the current live state (within the chosen stock scope) – prices and the job cost basis stay from the day of freezing. This clears out remote storage from the frozen state that the new build-structure scope no longer counts.\nSave the build plan afterwards so it survives a restart.':
            'Setzt NUR den eingefrorenen BESTAND auf den aktuellen Live-Stand (im gewählten Bestands-Scope) - Preise und Jobkosten-Basis bleiben vom Einfrier-Tag. Räumt z.B. Fern-Lager aus dem Einfrier-Stand, die der neue Scope nicht mehr zählt.\nDanach „Bauplan speichern“, damit es den Neustart überlebt.',
        'One click instead of four: fetches your real blueprints (BPOs/BPCs) for the end product, components and reactions AND reduces the invention attempts needed – all at once, instead of hunting for the individual buttons in each tab.':
            'Ein Klick statt vier: holt deine echten Blaupausen (BPOs/BPCs) für Endprodukt, Komponenten, Reaktionen UND reduziert die nötigen Invention-Versuche - alles auf einmal, statt die einzelnen Knöpfe in jedem Tab einzeln zu suchen.',
        'The buy and sell hub is chosen at the top left of the tool and applies to all tabs. The structure icon marks your market structures. With \u201eLoad order-book prices into the plan\u201c (Tools) its real sell order book is used for the material costs.':
            'Einkaufs-/Verkaufs-Hub wird oben links im Tool gewählt und gilt für alle Reiter. Das Struktur-Symbol markiert deine Markt-Strukturen. Mit \u201eOrderbuch-Preise in den Plan laden\u201c (Werkzeuge) wird dessen echtes Sell-Order-Buch für die Materialkosten genutzt.',
        'WHERE do you sell the end product? That changes two things:\n• the BROKER FEE (depends on your standings towards the station owner – different per hub)\n• the SELL PRICE (looked up there for this one item, no full market scan needed)\nPURCHASING stays at the scanned hub – you buy where the market scan comes from.\nIn player structures the owner sets the broker fee themselves; ESI does not report it – the global value applies there.':
            'WO verkaufst du das Endprodukt? Das ändert zwei Dinge:\n• die BROKER FEE (hängt an deinen Standings zum Stationsbesitzer – je Hub verschieden)\n• den VERKAUFSPREIS (wird für dieses eine Item dort abgefragt, kein kompletter Markt-Scan nötig)\nDer EINKAUF bleibt am gescannten Hub – gekauft wird dort, wo der Markt-Scan herkommt.\nBei Spielerstrukturen setzt der Besitzer die Broker Fee selbst; ESI liefert sie nicht – dort gilt der globale Wert.',
        'Builds everything that the manufacturing depth allows – EVEN when buying would be cheaper.\n\nDifference to the manufacturing depth: that decides WHICH categories you build yourself at all. This checkbox additionally switches off the cost comparison that otherwise decides per item.':
            'Baut alles, was laut Fertigungstiefe baubar ist – AUCH wenn Kaufen günstiger wäre.\n\nUnterschied zur Fertigungstiefe: die sagt, WELCHE Kategorien du überhaupt selbst baust. Dieser Haken schaltet zusätzlich die Kostenrechnung ab, die sonst pro Item entscheidet.',
        '„Last change detected“ is NOT the same as „last checked“.\nESI answers regularly even when nothing has happened in your storage –\nso the program compares the stock itself and shows the moment when it\nwas last actually different.':
            '„Letzte festgestellte Änderung“ ist NICHT dasselbe wie „zuletzt geprüft“.\nESI antwortet regelmäßig, auch wenn sich an deinem Lager nichts getan hat -\ndeshalb vergleicht das Programm den Bestand selbst und zeigt hier den\nZeitpunkt, an dem er zuletzt wirklich anders war.',
        "Copies ALL materials with their required total quantity to the clipboard, even when you already own them completely (format: item name + quantity per line) – sorted by category (Intermediate Reactions / Composite Reactions / components / minerals), just like in the run planner. Blacklisted items stay out (they were deliberately removed from the plan). The „# category“ lines are only for orientation – leave them out before pasting into EVE's multibuy if needed.":
            'Kopiert ALLE Materialien mit ihrer benötigten Gesamtmenge ins Clipboard, auch wenn du sie schon komplett besitzt (Format: Item-Name + Menge pro Zeile) - nach Kategorie sortiert (Intermediate Reactions / Composite Reactions / Komponenten / Mineralien), genau wie im Runplaner. Blacklist-Items bleiben außen vor (die sind ja bewusst aus dem Plan genommen). Die „# Kategorie“-Zeilen stehen nur zur Orientierung - vor dem Einfügen in EVEs Multibuy ggf. weglassen.',
        'ESI caches assets for up to an hour. Freshly delivered or just relocated material is therefore still missing there.\nThe same goes for material in places ESI cannot see for you.\nWhat you paste here applies as long as it is NEWER than the ESI data – after that ESI takes over again automatically.':
            'ESI cacht Assets bis zu einer Stunde. Frisch abgeliefertes oder gerade umgelagertes Material fehlt dort also noch.\nEbenso Material an Orten, die ESI für dich nicht sieht.\nWas du hier einfügst, gilt so lange, wie es NEUER ist als die ESI-Daten – danach übernimmt ESI automatisch wieder.',
        'ON (default): the pasted quantities apply permanently – even when ESI later delivers fresher data.\nOFF: they apply only as long as they are NEWER than the ESI data; after that ESI counts again.\nLeave it ON when ESI fundamentally cannot see this material – otherwise the value drops to 0 on the next fetch.':
            'AN (Standard): die eingefügten Mengen gelten dauerhaft – auch wenn ESI später frischere Daten liefert.\nAUS: sie gelten nur, solange sie NEUER sind als die ESI-Daten; danach zählt wieder ESI.\nAN lassen, wenn ESI dieses Material grundsätzlich nicht sieht – sonst fällt der Wert beim nächsten Abruf auf 0.',
        'ON: the ESI stock is ignored for this plan, only the pasted list counts.\nRunning and finished jobs still count – they are in no hangar and cannot be pasted at all.':
            'AN: der ESI-Lagerbestand wird für diesen Plan ignoriert, es zählt allein die eingefügte Liste.\nLaufende und fertige Jobs zählen weiter mit – die stehen in keinem Hangar und können gar nicht eingefügt werden.',
        'Per T2 item created through invention: datacores (fixed, from the blueprint recipe) plus a decryptor (selectable).\nSuccess chance, runs, ME and TE change live with the choice.\n\nThe total costs below are EXPECTED VALUES – in a single session you may need considerably more attempts if you are unlucky.':
            'Pro T2-Item, das über Invention entsteht: Datacores (fix, aus dem Blueprint-Rezept) + Decryptor (wählbar).\nErfolgschance, Runs, ME und TE ändern sich live mit der Wahl.\n\nDie Gesamtkosten unten sind ERWARTUNGSWERTE – in einer einzelnen Session kannst du bei Pech deutlich mehr Versuche brauchen.',
        'A flat amount per TRIP – e.g. the fuel cost of your jump freighter jump.\nIt is multiplied by the number of trips needed (volume ÷ cargo hold, rounded up) and charged ON TOP of the hauling service above.\nEnter in millions or billions, e.g. 50M or 1.2B.':
            'Pauschale je FAHRT – z.B. die Fuel-Kosten deines Jumpfrachter-Sprungs.\nWird mit der Anzahl nötiger Fahrten multipliziert (Volumen ÷ Frachtraum, aufgerundet) und ZUSÄTZLICH zum Frachtdienst oben berechnet.\nEingabe in Mio/Mrd, z.B. 50M oder 1,2B.',
        'Save this build plan under a name – it then appears under „Current build plans“ to work through.':
            'Diesen Bauplan benannt speichern – erscheint dann unter „Aktuelle Baupläne“ zum Abarbeiten.',
        'No market price available (capital ship) – this is the median price from public contracts (load contract prices in the capital area of the scanner). Not a real market price, only a reference value – alliance-internal contracts are not included.':
            'Kein Marktpreis vorhanden (Capital-Schiff) - das ist der Median-Preis aus öffentlichen Contracts (Contract-Preise laden im Capital-Bereich des Scanners). Kein echter Marktpreis, nur ein Richtwert - Allianz-interne Contracts sind darin nicht enthalten.',
        "FROZEN: the left stock column shows max(frozen state, live).":
            "EINGEFROREN: die linke Bestandsspalte zeigt max(Einfrier-Stand, live).",
        "covered for the remaining runs \u2713":
            "gedeckt für die restlichen Runs \u2713",
        "was covered \u2013 {n} missing now":
            "war gedeckt \u2013 jetzt fehlen {n}",
        "{n} materials were already covered and are missing now \u2013 check \u201e{action}\u201c in the tools menu.":
            "{n} Materialien waren schon gedeckt und fehlen jetzt \u2013 siehe \u201e{action}\u201c im Werkzeuge-Men\u00fc.",
        "Buy missing again": "Fehlendes nachkaufen",
        "Nothing is missing that was already covered \u2013 there is nothing to buy again.":
            "Es fehlt nichts, was schon einmal gedeckt war \u2013 es gibt nichts nachzukaufen.",
        "{n} materials added to the shopping list.":
            "{n} Materialien in die Einkaufsliste \u00fcbernommen.",
        "(building)": "(wird gebaut)",
        "Already running according to ESI at {who} ({what}) - before starting this again, check whether it is already enough.":
            "Läuft laut ESI bereits bei {who} ({what}) – bevor du das nochmal startest, prüfen ob's schon reicht.",
        "Reopen plan?": "Plan wieder \u00f6ffnen?",
        "Mark \u201e{name}\u201c as NOT finished again?\n\nIt then counts as open and appears in the work list again.\n\nThe material reservation stays OFF - switch it back on yourself if you need it.":
            "\u201e{name}\u201c wieder als NICHT abgeschlossen markieren?\n\nDer Plan gilt danach wieder als offen und taucht in der Arbeitsliste auf.\n\nDie Material-Reservierung bleibt AUS - schalte sie bei Bedarf selbst wieder ein.",
        "\u201e{name}\u201c is open again": "\u201e{name}\u201c ist wieder offen",
        "Reopen": "Wieder \u00f6ffnen",
        "Mark the plan as NOT finished again - it counts as open afterwards.":
            "Plan wieder als NICHT abgeschlossen markieren \u2013 er gilt danach als offen.",
        # ---- Sprachumschaltung ----
        "Language changed": "Sprache gewechselt",
        "The new language applies after a restart of "
        "EVE Motor Market.": "Die neue Sprache gilt nach einem Neustart von "
                             "EVE Motor Market.",
        # ---- Tooltips main_window.py (Sitzung 13) ----
        "If the tool helps you: donations go to my corporation in game.":
            "Wenn dir das Tool hilft: Spenden gehen ingame an meine Corporation.",
        "Fetches your real, currently open sell order prices from ESI - the \u201eIn sell order at\u201c column then shows the price you are ACTUALLY listing an item at right now (not just the theoretical target price).":
            "Holt deine echten, aktuell offenen Sell-Order-Preise von ESI - zeigt in der Spalte \u201eIn Sell-Order zu\u201c, zu welchem Preis du ein Item TATS\u00c4CHLICH gerade listest (nicht nur den theoretischen Zielpreis).",
        "Which columns are visible. Default: Qty, \u00d8 buy, Margin, Status, Orders \u2013 the rest can be switched on.":
            "Welche Spalten sichtbar sind. Standard: Menge, \u00d8-Kauf, Marge, Status, Orders \u2013 der Rest ist zuschaltbar.",
        "\u26a0 There is currently NO sell order at the destination. It traded there on {days} of the last 7 days \u2013 the market is alive, just empty. The destination price is the 30-day AVERAGE from history, not a price read off an order. Profit and margin are estimates.":
            "\u26a0 Am Ziel liegt derzeit KEINE Verkaufs-Order. Gehandelt wurde dort an {days} der letzten 7 Tage \u2013 der Markt ist also lebendig, nur leer. Der Zielpreis ist der 30-Tage-DURCHSCHNITT aus der Historie, keine abgelesene Order. Gewinn und Marge sind gesch\u00e4tzt.",
        "Buyer":
            "Kauft",
        "Seller":
            "Verkauft",
        "Only these characters count towards the average purchase price used by the order update. Leave both empty and all characters count, exactly as before.":
            "Nur diese Charaktere z\u00e4hlen f\u00fcr den \u00d8-Einkauf, den das Order-Update als Verlust-Schwelle benutzt. L\u00e4sst du beide leer, z\u00e4hlen alle \u2013 genau wie bisher.",
        "Copy":
            "Kopieren",
        "Copied \u2713":
            "Kopiert \u2713",
        "One-time setup":
            "Einmalige Einrichtung",
        "Connect EVE once":
            "EVE einmalig verbinden",
        "Set this up once; from then on a single click on \u201eLink character\u201c is enough. Takes about 2 minutes.":
            "Einmal kurz einrichten, danach reicht f\u00fcr immer ein Klick auf \u201eCharakter verkn\u00fcpfen\u201c. Dauert ~2 Minuten.",
        "Open the EVE developer portal and log in (same credentials as in the game).":
            "EVE-Entwicklerportal \u00f6ffnen und einloggen (gleiche Zugangsdaten wie im Spiel).",
        "\u2460 Open EVE portal":
            "\u2460 EVE-Portal \u00f6ffnen",
        "There: \u201eCreate New Application\u201c. Connection Type: \u201eAuthentication & API Access\u201c. Enter these values:":
            "Dort \u201eCreate New Application\u201c. Connection Type: \u201eAuthentication & API Access\u201c. Diese Werte eintragen:",
        "Callback URL":
            "Callback-URL",
        "Pick the scopes from the list in the portal (use the search box). Name and description of the app are up to you.":
            "Die Scopes im Portal aus der Liste ausw\u00e4hlen (Suchfeld nutzen). Name/Beschreibung der App sind frei w\u00e4hlbar.",
        "Save, then copy the \u201eClient ID\u201c and paste it here:":
            "Speichern, dann die \u201eClient ID\u201c kopieren und hier einf\u00fcgen:",
        "Paste Client ID here":
            "Client ID hier einf\u00fcgen",
        "Later":
            "Sp\u00e4ter",
        "Done & save":
            "Fertig & speichern",
        "Please paste the Client ID.":
            "Bitte die Client ID einf\u00fcgen.",
        "Error":
            "Fehler",
        "An error occurred \u2013 the app keeps running.\n\nDetails were saved to:":
            "Es ist ein Fehler aufgetreten \u2013 die App l\u00e4uft weiter.\n\nDetails wurden gespeichert in:",
        "Where is the unit cost lowest before buying the materials on the market gets too expensive \u2013 and where does the reaction batch divide up best?":
            "Wo sind die St\u00fcckkosten am niedrigsten, bevor der Material-Einkauf am Markt zu teuer wird \u2013 und wo geht die Reaktions-Charge am besten auf?",
        "Choose hub + sale price, then \u201eCalculate\u201c. The tool finds the upper end of the curve by itself.":
            "Hub + Verkaufspreis w\u00e4hlen, dann \u201eBerechnen\u201c. Die Obergrenze der Kurve findet das Tool selbst.",
        "Recommendation (best score) \xb7 Efficiency quantity (lowest unit cost)  \xb7  \u26a0 Bottlenecks = material not available at the hub in full depth (rest estimated conservatively)":
            "Empfehlung (bester Score) \u00b7 Effizienz-Menge (minimale St\u00fcckkosten) \u00b7 \u26a0 Engp\u00e4sse = Material am Hub nicht in voller Tiefe verf\u00fcgbar (Rest konservativ gesch\u00e4tzt)",
        "Calculating \u2026 (one live fetch per required material, may take a moment)":
            "Berechne \u2026 (ein Live-Abruf pro ben\u00f6tigtem Material, kann etwas dauern)",
        "calculating \u2026":
            "wird berechnet \u2026",
        "Enter a sale price to get a quantity recommendation (no price, no profit/score).":
            "F\u00fcr eine Mengen-Empfehlung einen Verkaufspreis eingeben (ohne Preis kein Gewinn/Score).",
        " \u2013 your real limit: ":
            " \u2013 deine echte Grenze: ",
        "Building pays off throughout: the unit cost stays almost the same (~{cost}/unit) no matter how many you build. So there is NO \u201eoptimal\u201c upper quantity{limit}.":
            "Bauen lohnt sich hier durchgehend: die St\u00fcckkosten bleiben fast gleich (~{cost}/Stk), egal wie viele du baust. Es gibt also KEINE \u201eoptimale\u201c Menge nach oben{limit}.",
        "Efficiency quantity: {qty} \xb7 {cost}/unit \u2013 from here on, building more hardly gets any cheaper (minimum {minimum}/unit). Building less would cost more per unit.":
            "Effizienz-Menge: {qty} \u00b7 {cost}/Stk \u2013 ab hier wird Mehr-Bauen kaum noch g\u00fcnstiger (Minimum {minimum}/Stk). Weniger zu bauen w\u00e4re teurer pro St\u00fcck.",
        " \u2013 unit price here {cost}/unit, ~{saved}/unit cheaper than at odd quantities (paid batches fully used)":
            " \u2013 St\u00fcckpreis hier {cost}/Stk, ~{saved}/Stk g\u00fcnstiger als bei krummen Mengen (bezahlte Chargen voll genutzt)",
        "\u2697 Batches divide up almost evenly at {qty}: only {pct}% surplus{extra}":
            "\u2697 Chargen gehen fast glatt auf bei {qty}: nur {pct}% \u00dcberschuss{extra}",
        "\u2697 No reaction is run at all in this range \u2013 the need is covered from stock or bought. The surplus value says nothing here.":
            "\u2697 In diesem Bereich wird gar keine Reaktion selbst gebaut \u2013 der Bedarf ist aus Bestand gedeckt oder wird gekauft. Der Verschnitt-Wert sagt hier nichts aus.",
        "\u2697 No reaction surplus in this range \u2013 the batches divide up evenly.":
            "\u2697 Kein Reaktions-\u00dcberschuss in diesem Bereich \u2013 die Chargen gehen auf.",
        "Market absorption at the hub (\xd8 last {days} days): ~{week} units/week \xb7 ~{month} units/month":
            "Markt-Absorption am Hub (\u00d8 letzte {days} Tage): ~{week} St\u00fcck/Woche \u00b7 ~{month} St\u00fcck/Monat",
        "Market absorption: no trade history available for this item at the hub.":
            "Markt-Absorption: keine Handelshistorie f\u00fcr dieses Item am Hub verf\u00fcgbar.",
        "Replaces the flat price of the shopping list with real order-book prices \u2013 one live fetch per material, may take a moment with many reaction materials.":
            "Ersetzt den Flachpreis der Einkaufsliste durch echte Orderbuch-Preise \u2013 ein Live-Abruf pro Material, kann bei vielen Reaktionsmaterialien etwas dauern.",
        "Choose a hub, then \u201eCalculate\u201c.":
            "Hub w\u00e4hlen, dann \u201eBerechnen\u201c.",
        "Markup %":
            "Aufschlag %",
        "\u201eMarkup %\u201c = how much more your purchase costs because you clear out the cheap sell orders (order-book price vs. best ask). Traffic light: green up to +5 % \xb7 yellow +5\u201320 % \xb7 red above +20 % (market too thin for this quantity). Sorted by markup \u2013 most expensive first. Double-click shows the individual sell orders. \u201eNo order book\u201c: no offer at the hub. \u201eShort\u201c: not enough for the full quantity.":
            "\u201eAufschlag %\u201c = wie viel teurer dein Einkauf wird, weil du die billigen Sell-Orders leerr\u00e4umst (Orderbuch-Preis vs. bester Ask). Ampel: gr\u00fcn bis +5 % \u00b7 gelb +5\u201320 % \u00b7 rot \u00fcber +20 % (Markt zu d\u00fcnn f\u00fcr diese Menge). Sortiert nach Aufschlag \u2013 die teuersten zuerst. Doppelklick zeigt die einzelnen Sell-Orders. \u201eKein Orderbuch\u201c: kein Angebot am Hub. \u201eKnapp\u201c: reicht nicht f\u00fcr die volle Menge.",
        "Calculating \u2026 (\u00d7{qty}, one live fetch per material, please wait)":
            "Berechne \u2026 (\u00d7{qty}, ein Live-Abruf pro Material, bitte warten)",
        "Double-click a material to see the INDIVIDUAL sell orders the order-book price was calculated from \u2013 so you can check every number directly against the in-game market (price \xd7 quantity, cheapest first).":
            "Doppelklick auf ein Material zeigt die EINZELNEN Sell-Orders, aus denen der Orderbuch-Preis berechnet wurde \u2013 so kannst du jede Zahl direkt gegen den In-Game-Markt gegenpr\u00fcfen (Preis \u00d7 Menge, g\u00fcnstigste zuerst).",
        "Required quantity of <b>{name}</b>: {need} units. Below are the real sell orders at the hub (cheapest first) \u2013 the tool buys them from top to bottom until the required quantity is reached. \u201eUsed\u201c = how many units from this order went into the calculation.":
            "Ben\u00f6tigte Menge von <b>{name}</b>: {need} St\u00fcck. Unten die echten Sell-Orders am Hub (g\u00fcnstigste zuerst) \u2013 das Tool kauft sie von oben nach unten ab, bis die ben\u00f6tigte Menge erreicht ist. \u201eGenutzt\u201c = wie viele St\u00fcck aus dieser Order in die Rechnung eingingen.",
        "No sell offer for this material at the chosen hub \u2013 the tool keeps the flat price here.":
            "Kein Sell-Angebot f\u00fcr dieses Material am gew\u00e4hlten Hub \u2013 im Tool bleibt hier der Flachpreis stehen.",
        "Recalculating exact build quantities \u2026":
            "Rechne genaue Bau-Mengen nach \u2026",
        "Quantity":
            "Menge",
        "Sets the fine filters automatically.":
            "Setzt die Feinfilter automatisch.",
        "Blueprint time efficiency (fully researched = 20 %). Reduces build time.":
            "Blueprint-Zeiteffizienz (voll erforscht = 20 %). Senkt die Bauzeit.",
        "Minimum daily volume \u2013 so you can actually sell what you build.":
            "Mindest-Tagesvolumen \u2013 damit du das Gebaute auch absetzt.",
        "Only items from this sale price upwards.":
            "Nur Items ab diesem Verkaufspreis.",
        "\u26a0 No structure set up - please add an invention-capable structure in the Structures tab.":
            "\u26a0 Keine Struktur angelegt - bitte im Struktur-Tab eine Invention-f\u00e4hige Struktur hinzuf\u00fcgen.",
        "\u26a0 Please choose a structure for invention in the Structures tab.":
            "\u26a0 Bitte im Struktur-Tab eine Struktur f\u00fcr Invention w\u00e4hlen.",
        "Skills for success chance of:":
            "Skills f\u00fcr Erfolgschance von:",
        "This plan is FROZEN \u2013 the materials are bought.\n\nRemove \u201e{name}\u201c anyway? The plan stays frozen: only this end product and the pre-stages only it needs are dropped. All other runs in the run planner stay exactly as they are \u2013 what it would have used of shared pre-stages becomes surplus.":
            "Dieser Plan ist EINGEFROREN \u2013 das Material ist gekauft.\n\n\u201e{name}\u201c trotzdem entfernen? Der Plan bleibt eingefroren: nur dieses Endprodukt und die Vorstufen, die nur es braucht, fallen weg. Alle anderen Runs im Runplaner bleiben genau so \u2013 was es von gemeinsamen Vorstufen gebraucht h\u00e4tte, wird \u00dcberschuss.",
        # emm334: Industry Jobs + Plan umbenennen
        "CHARACTERS":
            "CHARAKTERE",
        "All on":
            "Alle an",
        "On":
            "An",
        "{n} character(s) hidden":
            "{n} Charakter(e) ausgeblendet",
        "Rename\u2026":
            "Umbenennen\u2026",
        "(close the plan first)":
            "(erst den Plan schlie\u00dfen)",
        "Rename build plan":
            "Bauplan umbenennen",
        "New name of the build plan:":
            "Neuer Name des Bauplans:",
        "A build plan named \u201e{name}\u201c already exists \u2013 choose another name.":
            "Einen Bauplan \u201e{name}\u201c gibt es schon \u2013 bitte einen anderen Namen w\u00e4hlen.",
        "Renamed to \u201e{name}\u201c \u2713":
            "Umbenannt in \u201e{name}\u201c \u2713",
        "Bought for only {buy} per unit \u2013 the freight is more than the purchase price, so it is shown in ISK, not percent.":
            "Nur f\u00fcr {buy} je St\u00fcck gekauft \u2013 die Fracht ist h\u00f6her als der Einkaufspreis, deshalb steht sie in ISK statt in Prozent.",
        "IN PROGRESS ({n})":
            "LAUFEND ({n})",
        "COMPLETED ({n})":
            "ERLEDIGT ({n})",
        "{n} running job(s)":
            "{n} laufende(r) Job(s)",
        "{name} ({n} runs)":
            "{name} ({n} Runs)",
        "Count in the profit total":
            "Im Gewinn-Total mitz\u00e4hlen",
        "Exclude from profit total":
            "Aus dem Gewinn-Total nehmen",
        "Include in profit total":
            "Wieder ins Gewinn-Total nehmen",
        " {n} excluded by you.":
            " {n} von dir ausgeschlossen.",
        "Sold/day: ? \u2013 market history not loaded yet.":
            "Verkauft/Tag: ? \u2013 Markt-Historie noch nicht geladen.",
        "Sold/day: {v} \u00b7 {q} units \u2248 {d} days to sell":
            "Verkauft/Tag: {v} \u00b7 {q} St\u00fcck \u2248 {d} Tage bis verkauft",
        "Tick removed for {items} \u2013 ESI shows no job for it on any linked character 30 minutes after ticking.":
            "Haken bei {items} entfernt \u2013 ESI kennt 30 Minuten nach dem Abhaken bei keinem verkn\u00fcpften Charakter einen Job dazu.",
        "\u00d8 {v} sold per day at the hub (last 30 days, market history).":
            "\u00d8 {v} verkauft je Tag am Hub (letzte 30 Tage, Markt-Historie).",
        "Profit per unit \u00f7 build cost per unit \u2013 the same margin as in the build plan, with your skills and structures (T2: with the best decryptor). Settings in the build plan can raise it further.":
            "Gewinn je St\u00fcck \u00f7 Baukosten je St\u00fcck \u2013 dieselbe Marge wie im Bauplan, mit deinen Skills und Strukturen (T2: mit dem besten Decryptor). Einstellungen im Bauplan k\u00f6nnen sie weiter erh\u00f6hen.",
        "skills, standings, industry jobs, blueprints":
            "Skills, Standings, Industrie-Jobs, Blaupausen",
        "implants":
            "Implantate",
        "stock in your hangars":
            "Bestand in deinen Hangars",
        "structure markets":
            "Struktur-M\u00e4rkte",
        "open in game":
            "Im Spiel \u00f6ffnen",
        "corporation hangar":
            "Hangar der Corp",
        "location hint":
            "Standort-Hinweis",
        "wallet and orders":
            "Wallet und Orders",
        "New ESI permissions \u2013 quick re-link please":
            "Neue ESI-Rechte \u2013 bitte kurz neu verlinken",
        "o7 Pilot!\nUnfortunately you have to link your characters again to enjoy the full functionality of Eve MoMa. But in return there are lots of new features \u2013 isn't that great?":
            "o7 Pilot!\nLeider musst du deine Charaktere neu verlinken, um die volle Funktionalit\u00e4t von Eve MoMa zu genie\u00dfen. Aber daf\u00fcr gibt\u2019s ganz viele neue Funktionen \u2013 ist das nicht toll?",
        "Don't remind me again for these permissions":
            "F\u00fcr diese Rechte nicht mehr erinnern",
        "Re-link now":
            "Jetzt neu verlinken",
        "Re-link":
            "Neu verlinken",
        "Log in again with {name} \u2013 renews the ESI permissions. Nothing is deleted. In the EVE login, pick {name}.":
            "Mit {name} neu einloggen \u2013 erneuert die ESI-Rechte. Es wird nichts gel\u00f6scht. Im EVE-Login {name} ausw\u00e4hlen.",
        "Sold/day":
            "Verkauft/Tag",
        "(days)":
            "(Tage)",
        "Units of the product sold per day at the hub (average of the last 30 days, market history). Amber below 5/day, red = no trade. ? = history not loaded yet.":
            "Verkaufte St\u00fcck des Produkts je Tag am Hub (Schnitt der letzten 30 Tage, Markt-Historie). Amber unter 5/Tag, rot = kein Handel. ? = Historie noch nicht geladen.",
        "Market history not loaded yet \u2013 it is fetched in the background.":
            "Markt-Historie noch nicht geladen \u2013 sie wird im Hintergrund geholt.",
        "Not traded at the hub in the last 30 days.":
            "In den letzten 30 Tagen am Hub nicht gehandelt.",
        "Thin market: only {v} sold per day.":
            "D\u00fcnner Markt: nur {v} verkauft je Tag.",
        "\u00d8 {v} sold per day at the hub (last 30 days). {q} units \u2248 {d} days until all are sold \u2013 if you are the only seller.":
            "\u00d8 {v} verkauft je Tag am Hub (letzte 30 Tage). {q} St\u00fcck \u2248 {d} Tage, bis alle verkauft sind \u2013 wenn du der einzige Verk\u00e4ufer bist.",
        "\u26a0 Thin market for {items}: at the current daily volume the quantity takes more than {d} days to sell \u2013 the profit assumes it all sells at today\u2019s price.":
            "\u26a0 D\u00fcnner Markt bei {items}: beim heutigen Tagesvolumen braucht die Menge mehr als {d} Tage zum Verkauf \u2013 der Gewinn nimmt an, dass alles zum heutigen Preis weggeht.",
        "Click to show or hide the running jobs":
            "Klicken zeigt oder versteckt die laufenden Jobs",
        "Count completed plans in the profit total":
            "Erledigte Pl\u00e4ne im Gewinn-Total mitz\u00e4hlen",
        "READY":
            "FERTIG",
        "MANUFACTURING":
            "FERTIGUNG",
        "REACTIONS":
            "REAKTIONEN",
        "SCIENCE":
            "FORSCHUNG",
        "NEXT DONE":
            "N\u00c4CHSTER FERTIG",
        "ready to deliver":
            "bereit zum Abliefern",
        "free slots":
            "Slots frei",
        "{r} running \u00b7 {f} ready \u00b7 {m} slots":
            "{r} laufend \u00b7 {f} fertig \u00b7 {m} Slots",
        "{n} character(s) without known slot maximum (skills not loaded) \u2013 not counted in the slots.":
            "{n} Charakter(e) ohne bekanntes Slot-Maximum (Skills nicht geladen) \u2013 nicht in den Slots gez\u00e4hlt.",
        "(by hand)":
            "(von Hand)",
        "Set by hand\u2026":
            "Von Hand\u2026",
        "Choose the reprocessing implant per character yourself \u2013 e.g. when it sits in a jump clone (ESI only sees the active clone). Wins over the ESI detection.":
            "Reprocessing-Implantat je Charakter selbst w\u00e4hlen \u2013 z. B. wenn es in einem Jump-Clone steckt (ESI sieht nur den aktiven Clone). Geht vor die ESI-Erkennung.",
        "Reprocessing implants":
            "Reprocessing-Implantate",
        "ESI only sees the implants of the ACTIVE clone. If you reprocess in a jump clone, choose its implant here.":
            "ESI sieht nur die Implantate des AKTIVEN Clones. Reprocesst du in einem Jump-Clone, w\u00e4hle sein Implantat hier.",
        "Auto (ESI)":
            "Automatisch (ESI)",
        " Completed plans are not included.":
            " Erledigte Pl\u00e4ne z\u00e4hlen nicht mit.",
        "Copy Decryptor":
            "Decryptor kopieren",
        "Click copies the name of the decryptor chosen above \u2013 paste it into the in-game search.":
            "Klick kopiert den Namen des oben gew\u00e4hlten Decryptors \u2013 im Spiel in die Suche einf\u00fcgen.",
        "No decryptor chosen \u2013 nothing to copy.":
            "Kein Decryptor gew\u00e4hlt \u2013 nichts zu kopieren.",
        "Free science slots:": "Freie Science-Slots:",
        "Invention jobs at once:": "Invention-Jobs gleichzeitig:",
        "How many invention jobs run at the same time \u2013 one T1 copy each, one science slot each.\nLeft = 1 job (slow, 1 slot busy),\nright = all free science slots (as fast as possible).\nIt does NOT change how many T2 blueprints you get \u2013 that depends on quantity and decryptor.":
            "Wie viele Invention-Jobs gleichzeitig laufen \u2013 je eine T1-Kopie, je ein Science-Slot.\nLinks = 1 Job (langsam, 1 Slot belegt),\nrechts = alle freien Science-Slots (so schnell wie m\u00f6glich).\nDas \u00e4ndert NICHT, wie viele T2-Blaupausen du bekommst \u2013 das h\u00e4ngt an Menge und Decryptor.",
        "Copy your T1 original like this \u2192":
            "Kopiere dein T1-Original so \u2192",
        "{n} science slot(s) busy": "{n} Science-Slot(s) belegt",
        "done in \u2248{d}": "fertig in \u2248{d}",
        "Buy or not?": "Kaufen oder nicht?",
        "Checked {n} blueprint(s): {chg} changed, {same} already on their best decryptor, {skip} skipped (Own BPC).":
            "{n} Blaupause(n) gepr\u00fcft: {chg} gewechselt, {same} hatten schon ihren besten Decryptor, {skip} \u00fcbersprungen (Eigene BPC).",
        "\u26a0 No decryptor chosen yet \u2013 pick one or press \u201eAuto-Decryptor\u201c; building from your own copy? Tick \u201eOwn BPC\u201c and enter its ME/TE.":
            "\u26a0 Noch kein Decryptor gew\u00e4hlt \u2013 einen w\u00e4hlen oder \u201eAuto-Decryptor\u201c dr\u00fccken; baust du aus deiner eigenen Kopie? \u201eEigene BPC\u201c anhaken und ihre ME/TE eintragen.",
        "\u26a0 No decryptor chosen yet for: {items}. Invention tab: pick one or press \u201eAuto-Decryptor\u201c; building from your own copy? Tick \u201eOwn BPC\u201c and enter its ME/TE.":
            "\u26a0 Noch kein Decryptor gew\u00e4hlt f\u00fcr: {items}. Invention-Reiter: einen w\u00e4hlen oder \u201eAuto-Decryptor\u201c dr\u00fccken; baust du aus deiner eigenen Kopie? \u201eEigene BPC\u201c anhaken und ihre ME/TE eintragen.",
        "will be invented \u2697": "wird erfunden \u2697",
        "Buy Missing Blueprints": "Fehlende Blueprints kaufen",
        "Copies every blueprint of this plan that you own neither as an original nor as a copy \u2013 one original each, in EVE multibuy format. Make copies from it yourself for parallel jobs. Invented T2 copies are left out (they cannot be bought).":
            "Kopiert jede Blaupause dieses Plans, die du weder als Original noch als Kopie besitzt \u2013 je ein Original, im EVE-Multibuy-Format. Kopien f\u00fcr parallele Jobs ziehst du selbst daraus. Erfundene T2-Kopien bleiben drau\u00dfen (die kann man nicht kaufen).",
        "Load ESI ownership first \u2013 without it nobody knows which blueprints are missing.":
            "Zuerst den ESI-Besitz laden \u2013 ohne ihn wei\u00df niemand, welche Blaupausen fehlen.",
        "No blueprint is missing \u2713 (invented T2 copies are not bought).":
            "Es fehlt keine Blaupause \u2713 (erfundene T2-Kopien werden nicht gekauft).",
        "{n} blueprint(s) copied \u2713 \u2013 paste into the in-game multibuy window.":
            "{n} Blaupause(n) kopiert \u2713 \u2013 im Spiel ins Multibuy-Fenster einf\u00fcgen.",
        "Whether the datacores and decryptors worked out in the Invention tab go into the shopping list.":
            "Ob die im Invention-Reiter ermittelten Datacores und Decryptoren auf die Einkaufsliste kommen.",
        "Auto-Decryptor": "Auto-Decryptor",
        "Picks the best decryptor for every blueprint in this tab, one after the other: the lowest expected total cost for the current quantity. Cards with \u201eOwn BPC\u201c are left out.":
            "W\u00e4hlt f\u00fcr jede Blaupause in diesem Reiter nacheinander den besten Decryptor: die niedrigsten erwarteten Gesamtkosten f\u00fcr die aktuelle Menge. Karten mit \u201eEigene BPC\u201c bleiben aussen vor.",
        "Own BPC (your own ME/TE)": "Eigene BPC (deine ME/TE)",
        "Ticked = you build from your own researched copy: the invention for this end product is skipped and your ME/TE count. Same switch as \u201eOwn\u201c in the \u201eEnd products\u201c card.":
            "Angehakt = du baust aus deiner eigenen erforschten Kopie: die Invention f\u00fcr dieses Endprodukt entf\u00e4llt, deine ME/TE z\u00e4hlen. Derselbe Schalter wie \u201eOwn\u201c in der Karte \u201eEndprodukte\u201c.",
        "\u26a0 Own BPC for this end product: the invention is skipped, your ME/TE count (below or in the \u201eEnd products\u201c card).":
            "\u26a0 Eigene BPC f\u00fcr dieses Endprodukt: die Invention entf\u00e4llt, deine ME/TE z\u00e4hlen (darunter oder in der Karte \u201eEndprodukte\u201c).",
        "{n} runs already on hand as own BPC \u2013 fewer attempts needed":
            "{n} Runs schon als eigene BPC da \u2013 weniger Versuche n\u00f6tig",
        "\u221e \u00b7 largest job {need}":
            "\u221e \u00b7 gr\u00f6\u00dfter Job {need}",
        "Cap. {cap} \u00b7 largest job {need}":
            "Kap. {cap} \u00b7 gr\u00f6\u00dfter Job {need}",
        " \u26a0 not enough":
            " \u26a0 zu wenig",
        "Item type: not classified":
            "Item-Art: keine Einordnung",
        "This phase only starts once the previous one is completely finished \u2013 never at the same time.":
            "Diese Phase startet erst, wenn die vorherige komplett fertig ist \u2013 nie gleichzeitig.",
        "Item type: ":
            "Item-Art: ",
        "Facility tax charged by the structure owner (shown in the structure info). Goes into the job cost.":
            "Facility-Tax, die der Struktur-Besitzer verlangt (steht im Struktur-Info). Geht in die Job-Kosten.",
        "Assumed blueprint material efficiency (fully researched BPO = 10 %).":
            "Angenommene Blueprint-Materialeffizienz (voll erforschte BPO = 10 %).",
        "Search for the build system (e.g. type \u201eJita\u201c). Sets the cost index (live from ESI) and the security automatically.":
            "Bau-System suchen (z. B. \u201eJita\u201c tippen). Setzt den Kosten-Index (live aus ESI) und die Sicherheit automatisch.",
        "Security":
            "Sicherheit",
        "Only items of this category (ships, modules, ammo \u2026). Needs the SDE \u2013 \u201eLoad recipes\u201c.":
            "Nur Items dieser Kategorie (Schiffe, Module, Munition \u2026). Braucht die SDE \u2013 \u201eBaurezepte laden\u201c.",
        "Only items of this race (mainly relevant for ships - modules/ammo usually have no race assigned in the SDE and stay visible whatever you choose).":
            "Nur Items dieser Rasse (v.a. bei Schiffen relevant - Module/Munition haben meist keine Rassen-Zuordnung in der SDE und bleiben bei jeder Wahl sichtbar).",
        "Race/faction":
            "Rasse/Fraktion",
        "Time window":
            "Zeitfenster",
        "\u201eLoad recipes\u201c, then \u201eFind blueprints\u201c (after a hub scan in the Daytrade or Swing tab).":
            "\u201eBaurezepte laden\u201c, dann \u201eBlaupausen suchen\u201c (nach einem Hub-Scan im Daytrade- oder Swing-Tab).",
        "These ships are practically never traded in Jita via normal market orders, but via contracts (often alliance-internal, null/lowsec). \u201eLoad contract prices\u201c looks up public contracts as a reference - \u00d8 daily volume/volatility do not exist for them (no price history for contracts in ESI), so you get \u201eActive contracts\u201c/\u201ePrice range\u201c instead.":
            "Diese Schiffe werden in Jita praktisch nie \u00fcber normale Marktorders gehandelt, sondern \u00fcber Contracts (oft Allianz-intern, Null-/Lowsec). \u201eContract-Preise laden\u201c sucht \u00f6ffentliche Contracts als Richtwert - \u00d8 Tagesvolumen/Volatilit\u00e4t gibt's daf\u00fcr nicht (keine Preis-Historie f\u00fcr Contracts in ESI), deshalb \u201eAktive Contracts\u201c/\u201ePreisspanne\u201c statt dessen.",
        "This item needs no invention (T1/BPO) - ME/TE still apply, e.g. if your own blueprint is already researched.":
            "Dieses Item braucht keine Invention (T1/BPO) - ME/TE gelten trotzdem, z.B. wenn deine eigene Blaupause schon erforscht ist.",
        "No item in this build plan needs invention (either everything is T1/BPO, or invention is switched off in the build settings).":
            "Kein Item in diesem Bauplan braucht Invention (entweder alles T1/BPO, oder Invention ist in den Bau-Einstellungen ausgeschaltet).",
        "How likely the planned attempts are really enough.\nHigher = more attempts, more datacores, more certain to finish - but more expensive.\nThis does NOT change the success chance per attempt.\nAlso affects \u201eAuto-Decryptor\u201c: at high certainty, decryptors with a better success chance pay off sooner.\nApplies to this build plan only; a new one starts again at {pct} %.":
            "Wie wahrscheinlich die geplanten Versuche wirklich reichen.\nH\u00f6her = mehr Versuche, mehr Datacores, sicherer fertig - aber teurer.\nDas \u00e4ndert NICHT die Erfolgschance je Versuch.\nWirkt auch auf \u201eAuto-Decryptor\u201c: bei hoher Sicherheit lohnen Decryptoren mit besserer Erfolgschance eher.\nGilt nur f\u00fcr diesen Bauplan; ein neuer startet wieder bei {pct} %.",
        "pinned":
            "fixiert",
        "best character marked \u201eFor invention\u201c":
            "bestes \u201eF\u00fcr Invention\u201c-markiertes Charakter",
        "<b>Skill bonus active: \xd7{mod}</b> on the base success chance \u2013 skills of <span style='color:{color}; font-size:15px; font-weight:800;'>{name}</span> ({via})":
            "<b>Skill-Bonus aktiv: \u00d7{mod}</b> auf die Basis-Erfolgschance \u2013 Skills von <span style='color:{color}; font-size:15px; font-weight:800;'>{name}</span> ({via})",
        "\u26A0 <b>No skill bonus included</b> (base SDE value) - mark a character as \u201eFor invention\u201c in the build characters tab + \u201eLoad job slots\u201c for the real, higher success chance.":
            "\u26A0 <b>Kein Skill-Bonus eingerechnet</b> (Basis-SDE-Wert) - im Baucharaktere-Tab einen Charakter als \u201eF\u00fcr Invention\u201c markieren + \u201eJob-Slots laden\u201c f\u00fcr die echte, h\u00f6here Erfolgschance.",
        "attempts":
            "Versuche",
        "{n} attempts": "{n} Versuche",
        "Show or hide the details of this invention":
            "Details dieser Invention ein- oder ausblenden",
        "Skills \u00d7{mod}": "Skills \u00d7{mod}",
        "\u26A0 No skill bonus": "\u26A0 Kein Skill-Bonus",
        "\u2248{d} days":
            "\u2248{d} Tage",
        "{total} copy runs in total for {att} required attempts.\n{waves} job waves one after another (each wave {par} jobs in parallel).\nYou have to make the copies yourself first \u2013 with ONE original, copy jobs run one after another.":
            "{total} Kopie-Runs insgesamt f\u00fcr {att} n\u00f6tige Versuche.\n{waves} Job-Wellen nacheinander (je Welle {par} Jobs parallel).\nDie Kopien selbst musst du vorher ziehen \u2013 mit EINEM Original laufen Kopier-Jobs nacheinander.",
        "Material cost: only the base ME of this item \u2013 structure and rig ME apply on top and are the same for all decryptors.\nBuild time is for information only \u2013 \u201eAuto-Decryptor\u201c looks at total profit alone.\nInvention time is sequential with 1 free science slot; faster accordingly with more slots.":
            "Materialkosten: nur die Basis-ME dieses Items \u2013 Struktur- und Rig-ME wirken zus\u00e4tzlich und sind f\u00fcr alle Decryptoren gleich.\nBauzeit ist nur zur Info \u2013 \u201eAuto-Decryptor\u201c schaut ausschlie\u00dflich auf den Gesamtgewinn.\nInvention-Zeit gilt sequenziell bei 1 freiem Science-Slot; mit mehr Slots entsprechend schneller.",
        "\u2139 No stock data yet - \u201e Subtract assets\u201c above normally runs automatically on opening.":
            "\u2139 Noch keine Bestandsdaten - \u201e Assets abziehen\u201c oben l\u00e4uft normalerweise automatisch beim \u00d6ffnen.",
        "{types} material types \u00b7 {buy} to buy \u00b7 {build} will be built \u00b7 {stock} covered from stock \u2713":
            "{types} Material-Typen \u00b7 {buy} zu kaufen \u00b7 {build} werden gebaut \u00b7 {stock} aus Bestand gedeckt \u2713",
        " \xb7 {n} of them from PASTED stock":
            " \u00b7 {n} davon aus EINGEF\u00dcGTEM Bestand",
        " \xb7 pasted stock present, but superseded (ESI data is fresher)":
            " \u00b7 Einf\u00fcgung vorhanden, aber abgel\u00f6st (ESI-Daten sind frischer)",
        "Tick characters in the setup (\u201eFor building\u201c / \u201eFor reactions\u201c) + \u201eLoad skills\u201c, then the run planner appears here.":
            "Charaktere im Setup ankreuzen (\u201eF\u00fcr Bauen\u201c / \u201eF\u00fcr Reaktionen\u201c) + \u201eSkills laden\u201c, dann erscheint hier der Runplaner.",
        "\u26a0 The Blueprints tab could not be built completely. Details are in fehler.log next to the application.":
            "\u26a0 Der Blueprints-Tab konnte nicht vollst\u00e4ndig aufgebaut werden. Einzelheiten stehen in fehler.log neben der Anwendung.",
        "\u2139 End product blueprint ({n}) still missing - normal if you create the T2 BPC via invention only AFTER planning.":
            "\u2139 Endprodukt-Blaupause ({n}) fehlt noch - normal, wenn du das T2-BPC erst NACH der Planung per Invention erzeugst.",
        "\u26a0 {n} item(s) have too few blueprint copies for the fastest possible build:<br>":
            "\u26a0 {n} Item(s) haben zu wenig Blaupausen-Kopien f\u00fcr den schnellstm\u00f6glichen Bau:<br>",
        "Details in the Blueprints tab.":
            "Details im Blueprints-Tab.",
        "material rig":
            "Material-Rig",
        "Auto-choice by rig benefit for the items of THIS stage:\n":
            "Auto-Wahl nach Rig-Nutzen f\u00fcr die Items DIESER Stufe:\n",
        "\n\nAll level \u2013 no rig fits this item type, so the order decides. A capital rig, for instance, does NOT affect freighters (they count as Large Ship).":
            "\n\nAlle gleichauf \u2013 kein Rig passt auf diese Item-Art, also entscheidet die Reihenfolge. Ein Capital-Rig wirkt z. B. NICHT auf Freighter (die z\u00e4hlen als Large Ship).",
        "Rig CATEGORY of the items of this stage \u2013 NOT the rigs fitted to the structure (those are in the Structures tab).\nA material/time rig of the chosen structure only applies if it covers this category.\nFull ranking with classification: hover over the stage name on the left.":
            "Rig-KATEGORIE der Items dieser Stufe \u2013 NICHT die verbauten Rigs der Struktur (die stehen im Strukturen-Tab).\nEin Material-/Zeit-Rig der gew\u00e4hlten Struktur wirkt nur, wenn es diese Kategorie abdeckt.\nVolle Rangliste samt Einordnung: Maus \u00fcber den Stufennamen links.",
        "Planning uses {cap} slots (maximum per skills).\nIn game, at the last \u201eLoad skills\u201c{when} only {free} of them were free \u2013 the rest were busy.\nThis is DELIBERATELY ignored: by the time this stage comes up, those jobs are done. Previously a character with 0 free slots dropped out of the plan entirely and all the work landed on a single one.\nWhen opening a build plan the tool refreshes this state automatically if it is older than 10 minutes.":
            "Geplant wird mit {cap} Slots (Maximum laut Skills).\nIngame waren beim letzten \u201eSkills laden\u201c{when} nur {free} davon frei \u2013 der Rest lief gerade.\nDas wird BEWUSST ignoriert: bis diese Stufe drankommt, sind die Jobs fertig. Fr\u00fcher fiel ein Charakter mit 0 freien Slots ganz aus dem Plan, und die Arbeit landete auf einem einzigen.\nBeim \u00d6ffnen eines Bauplans zieht das Tool diesen Stand automatisch nach, wenn er \u00e4lter als 10 Minuten ist.",
        " on {d}":
            " am {d}",
        "More starts ({jobs}) than simultaneous slots ({cap}) \u2013 you start the surplus ones as soon as a slot frees up (next wave). The stage time already includes this waiting.":
            "Mehr Starts ({jobs}) als gleichzeitige Slots ({cap}) \u2013 die \u00fcberz\u00e4hligen startest du nach, sobald ein Slot frei wird (n\u00e4chste Welle). Die Stufenzeit enth\u00e4lt diese Wartezeit bereits.",
        "\n({cap} = FREE slots at the last \u201eLoad skills\u201c, maximum {max} per skills.)":
            "\n({cap} = FREIE Slots vom letzten \u201eSkills laden\u201c, maximal {max} laut Skills.)",
        "{n} units surplus in total for this item (reaction batch size) - split here proportionally by runs.":
            "{n} Stk. \u00dcberschuss insgesamt f\u00fcr dieses Item (Reaktions-Chargengr\u00f6\u00dfe) - hier anteilig nach Runs aufgeteilt.",
        "ESI sees {seen} runs of this item (delivered or in the build pipeline, across ALL plans) \u2013 this row needs {need}. Once fully covered, the item is HIDDEN from the plan.":
            "ESI sieht {seen} Runs dieses Items (geliefert oder in der Bauschleife, \u00fcber ALLE Pl\u00e4ne) \u2013 diese Zeile braucht {need}. Bei Vollstand wird das Item aus dem Plan AUSGEBLENDET.",
        "\u2705 DONE per ESI at {name} ({who}) - only DELIVER in game now. It can then take up to 1 h until ESI updates the stock (CCP cache).":
            "\u2705 FERTIG laut ESI bei {name} ({who}) - nur noch ingame ABLIEFERN. Danach kann es bis zu 1 h dauern, bis ESI den Bestand aktualisiert (CCP-Cache).",
        "{n} blueprints with {r} runs each.":
            "{n} Blaupausen mit je {r} Runs.",
        "{n} blueprint with {r} runs.":
            "{n} Blaupause mit {r} Runs.",
        "\nClick copies {r} \u2013 paste it into the \u201eRuns\u201c field in game (Ctrl+V).":
            "\nKlick kopiert {r} \u2013 ingame ins Feld \u201eRuns\u201c einf\u00fcgen (Strg+V).",
        "Buildable items the plan DELIBERATELY does not build: either buying at the current hub is cheaper than building (then they are on the shopping list), or your stock (incl. pipeline) covers the need. If an item you expected is missing here, THAT is the answer - not the plan forgetting it.":
            "Baubare Items, die der Plan BEWUSST nicht baut: entweder ist Kaufen am aktuellen Hub billiger als Selberbauen (dann stehen sie auf der Einkaufsliste), oder dein Bestand (inkl. Pipeline) deckt den Bedarf. Fehlt hier ein Item, das du erwartet hast, ist DAS die Antwort - nicht ein Vergessen des Plans.",
        "\u2026 and {n} more":
            "\u2026 und {n} weitere",
        "One run yields {n} units \u2013 less is not possible. Arrow up/down = one whole run more/less; typed values in between are rounded up.":
            "Ein Run liefert {n} St\u00fcck \u2013 weniger geht nicht. Pfeil hoch/runter = ein ganzer Run mehr/weniger; getippte Zwischenwerte werden aufgerundet.",
        "Material efficiency of the FINAL product only (usually T2 \u2013 often 0 % as long as the BPC from invention has not been researched separately).":
            "Material-Effizienz NUR des Endprodukts (meist T2 \u2013 oft 0 %, solange die BPC aus Invention noch nicht extra erforscht ist).",
        "Material efficiency of this final product's blueprint (T1: your research level, 0\u201310 %).":
            "Material-Effizienz der Blaupause dieses Endprodukts (T1: dein Forschungsstand, 0\u201310 %).",
        "Time efficiency of this final product's blueprint (T1: your research level, 0\u201320 %).":
            "Zeit-Effizienz der Blaupause dieses Endprodukts (T1: dein Forschungsstand, 0\u201320 %).",
        "Frozen stock":
            "Einfrier-Bestand",
        "The live state is not there yet \u2013 please enable \u201e Subtract assets\u201c first and wait for the fetch.":
            "Der Live-Stand fehlt noch \u2013 bitte zuerst \u201e Assets abziehen\u201c aktivieren und den Abruf abwarten.",
        "The frozen stock already matches the current live state exactly \u2013 there is nothing to change.\n\n(That is why nothing changes in the build plan either.)":
            "Der eingefrorene Bestand entspricht bereits exakt dem aktuellen Live-Stand \u2013 es gibt nichts zu \u00e4ndern.\n\n(Deshalb \u00e4ndert sich im Bauplan auch nichts.)",
        "Reset frozen stock":
            "Einfrier-Bestand neu setzen",
        "{n} position(s) change ({down} less, {up} more, {gone} to 0):\n\n{lines}\n\nPurchase prices and job-cost basis stay from the freeze day.\nCareful: whatever drops to 0 here is planned as TO BUY again afterwards.":
            "{n} Position(en) \u00e4ndern sich ({down} weniger, {up} mehr, {gone} auf 0):\n\n{lines}\n\nEinkaufspreise und Jobkosten-Basis bleiben vom Einfrier-Tag.\nAchtung: was hier auf 0 f\u00e4llt, plant der Bauplan danach wieder als ZU KAUFEN ein.",
        "Frozen stock reset on {when} \u2013 {n} position(s) changed ({down} less, {up} more, {gone} to 0). Prices still from the freeze day. Don't forget: \u201eSave build plan\u201c.":
            "Einfrier-Bestand am {when} neu gesetzt \u2013 {n} Position(en) ge\u00e4ndert ({down} weniger, {up} mehr, {gone} auf 0). Preise weiterhin vom Einfrier-Tag. Nicht vergessen: \u201eBauplan speichern\u201c.",
        "Checks the REMAINING runs of the plan against the real current stock (hangar + pipeline): what will be missing, and how much? Finds vanished stock before it is missing at build time.":
            "Rechnet die RESTLICHEN Runs des Plans gegen den echten Ist-Bestand (Lager + Pipeline): was wird fehlen, und wie viel? Findet verschwundenen Bestand, bevor er beim Bauen fehlt.",
        "Who sells the final product? Determines sales tax and broker fee \u2013 with thin margins the biggest lever of all.\n\u2b50 = lowest total fee, preset for NEW build plans.\n\u201e\u2014 global \u2014\u201c takes the values from the settings (behaviour as before).\nThe choice is saved with the build plan and freezes with it \u2013 otherwise the target price is off later.\nFill the list: Settings \u2192 \u201e Find best character automatically\u201c.":
            "Wer verkauft das Endprodukt? Bestimmt Sales Tax und Broker Fee \u2013 bei d\u00fcnnen Margen der gr\u00f6\u00dfte Hebel \u00fcberhaupt.\n\u2b50 = niedrigste Gesamtgeb\u00fchr, wird bei NEUEN Baupl\u00e4nen vorbelegt.\n\u201e\u2014 global \u2014\u201c nimmt die Werte aus den Einstellungen (Verhalten wie bisher).\nDie Auswahl wird mit dem Bauplan gespeichert und friert beim Einfrieren mit \u2013 sonst stimmt der Zielpreis sp\u00e4ter nicht mehr.\nListe f\u00fcllen: Einstellungen \u2192 \u201e Besten Charakter automatisch finden\u201c.",
        "\n\n\u26a0 NO character data loaded yet \u2013 the global fee rate from the settings applies. Click \u201e Find best character automatically\u201c once, then all characters with their total fee appear here.":
            "\n\n\u26a0 NOCH KEINE Charakterdaten geladen \u2013 es gilt der globale Geb\u00fchrensatz aus den Einstellungen. Einmal \u201e Besten Charakter automatisch finden\u201c klicken, dann stehen hier alle Charaktere mit ihrer Gesamtgeb\u00fchr.",
        "Tick it once you are really done: that releases the material this "
        "line still reserves for other build plans.":
            "Hak es ab, wenn du wirklich fertig bist: das gibt das Material "
            "frei, das diese Zeile noch f\u00fcr andere Baupl\u00e4ne reserviert.",
        "Use what you have, even if buying would be cheaper":
            "Vorhandenes verbauen, auch wenn Kauf billiger w\u00e4re",
        "Takes ME/TE from your own blueprints (ESI) instead of the fields next to it \u2013 per component the WORST copy found.\nUntick = your numbers next to it apply again.\nWithout an own blueprint for a component, the fields always apply.":
            "Nimmt ME/TE aus deinen eigenen Blaupausen (ESI) statt aus den Feldern daneben \u2013 je Bauteil die SCHLECHTESTE gefundene Kopie.\nAbhaken = deine Zahlen daneben gelten wieder.\nOhne eigene Blaupause zu einem Bauteil greifen die Felder immer.",
        "Expand/collapse all levels in the recipe structure.":
            "Alle Ebenen in der Rezept-Struktur auf-/zuklappen.",
        "\u229f Collapse all":
            "\u229f Alles zu",
        "\u229e Expand all":
            "\u229e Alles auf",
        "On = just list all runs per item, without character assignment.":
            "An = nur alle Runs je Item auflisten, ohne Charakter-Zuteilung.",
        "Reactions often automatically produce more than exactly needed (fixed batch size) - shows how much is left over that you can keep for the next build plan instead of wasting it.":
            "Bei Reaktionen entsteht oft automatisch mehr als exakt gebraucht (feste Chargen-Gr\u00f6\u00dfe) - zeigt, wie viel \u00fcbrig bleibt, das du f\u00fcr den n\u00e4chsten Bauplan aufheben kannst statt es zu verschwenden.",
        "Reaction stage (stage 1 \u2192 goes into a further reaction, stage 2 \u2192 goes into the build) + material type (Composite/Intermediate/...). The material type matches the checkbox under \u201eMy blueprints\u201c in the recipe structure tab. No tick there = bought instead of built.":
            "Stufe der Reaktion (Stufe 1 \u2192 geht in weitere Reaktion, Stufe 2 \u2192 geht in den Bau) + Materialtyp (Composite/Intermediate/...). Der Materialtyp entspricht der Checkbox unter \u201eMeine Blueprints\u201c im Rezept-Struktur-Tab. Kein H\u00e4kchen dort = wird gekauft statt gebaut.",
        "\u26a0 {n} blacklist line(s) match NO item in the plan \u2013 check the spelling: ":
            "\u26a0 {n} Blacklist-Zeile(n) passen zu KEINEM Item im Plan \u2013 Schreibweise pr\u00fcfen: ",
        "\u26a0 {n} item(s) hidden by the blacklist: ":
            "\u26a0 {n} Item(e) durch die Blacklist ausgeblendet: ",
        "Material efficiency of the FINAL product only.":
            "Material-Effizienz NUR des Endprodukts.",
        "Own slot (science) - blocks no build/reaction slots. Can be scheduled first/in parallel.":
            "Eigener Slot (Wissenschaft) - blockiert keine Bau-/Reaktions-Slots. Kann zuerst/parallel eingeplant werden.",
        "Attempts (column \u201eRuns\u201c) \xb7 required successes (column \u201eUnits\u201c) - details/decryptor choice in the Invention tab.":
            "Versuche (Spalte \u201eRuns\u201c) \u00b7 ben\u00f6tigte Erfolge (Spalte \u201eSt\u00fcck\u201c) - Details/Decryptor-Wahl im Invention-Tab.",
        "Sale price = MEDIAN of public contracts across all of New Eden (Tools \u2192 \u201eLoad contract prices\u201c).\n":
            "Verkaufspreis = MEDIAN der \u00f6ffentlichen Contracts in ganz New Eden (Werkzeuge \u2192 \u201eContract-Preise laden\u201c).\n",
        "{n} contract(s)":
            "{n} Contract(s)",
        ", {n} of them derived from bundles":
            ", davon {n} aus Bundles abgeleitet",
        " \u00b7 mean: {v}":
            " \u00b7 Mittelwert: {v}",
        " \u00b7 range: {lo} \u2013 {hi}":
            " \u00b7 Spanne: {lo} \u2013 {hi}",
        "\n\nMedian instead of mean: a few fantasy prices distort the mean, not the median. ESI does not see alliance-internal contracts.":
            "\n\nMedian statt Mittelwert: einzelne Fantasie-Preise verziehen den Mittelwert, den Median nicht. Allianz-interne Contracts sieht ESI nicht.",
        "BEFORE fees \u00b7 = {v} / unit":
            "VOR Geb\u00fchren \u00b7 = {v} / Stk",
        "This card shows the profit BEFORE sales tax and broker fee \u2013 relevant when selling via contract or directly to players.\n\n{raw}  (before fees)\n\u2212 {fees}  fees ({pct} % on {gross})\n= {prof}  \u2192 card \u201eTotal profit\u201c":
            "Diese Karte zeigt den Gewinn VOR Sales Tax und Broker Fee \u2013 relevant beim Verkauf per Contract oder direkt an Spieler.\n\n{raw}  (vor Geb\u00fchren)\n\u2212 {fees}  Geb\u00fchren ({pct} % auf {gross})\n= {prof}  \u2192 Karte \u201eGewinn gesamt\u201c",
        "\n\nThe fees eat {pct} % of your raw profit.":
            "\n\nDie Geb\u00fchren fressen {pct} % deines Rohgewinns.",
        "Profit WITHOUT sales tax + broker fee ({tax}% + {broker}% = {sum}% saved) - relevant if you sell/trade via contract or deal directly with other players instead of via the market.\nSale proceeds: {gross}\n\u2212 Build cost: \u2212{total}\n\u2212 Transport: \u2212{transport}\n= Raw profit: {raw}":
            "Gewinn OHNE Sales Tax + Broker Fee ({tax}% + {broker}% = {sum}% gespart) - relevant, wenn du per Contract verkaufst/tauschst oder direkt mit anderen Spielern handelst statt \u00fcber den Markt.\nVerkaufserl\u00f6s: {gross}\n\u2212 Baukosten: \u2212{total}\n\u2212 Transport: \u2212{transport}\n= Rohgewinn: {raw}",
        "No hangar stock is counted":
            "Kein Lagerbestand wird gez\u00e4hlt",
        "None of your build structures is linked to a real EVE structure.\n\nIn the \u201eBuild structures only\u201c scope, therefore NO hangar stock is counted at all \u2013 only running and finished jobs. The build costs are too high because of this.\n\nFix: Structures tab \u2192 \u201e Find locations and link all\u201c.\nImmediate workaround: set the stock scope here on the right to \u201e Everywhere\u201c.":
            "Keine deiner Bau-Strukturen ist mit einer echten EVE-Struktur verkn\u00fcpft.\n\nIm Scope \u201eNur Bau-Strukturen\u201c wird deshalb GAR KEIN Lagerbestand gez\u00e4hlt \u2013 nur laufende und fertige Jobs. Die Baukosten sind dadurch zu hoch.\n\nAbhilfe: Strukturen-Tab \u2192 \u201e Orte finden und alle verkn\u00fcpfen\u201c.\nSofort-Workaround: Bestands-Scope hier rechts auf \u201e \u00dcberall\u201c stellen.",
        "\u26a0 Assets/jobs partly not loadable ({who}) \u2013 the plan calculates without this stock. Try again later (tick off/on); the REASON per character is in fehler.log.":
            "\u26a0 Assets/Jobs teilweise nicht ladbar ({who}) \u2013 der Plan rechnet ohne diese Best\u00e4nde. Sp\u00e4ter erneut versuchen (H\u00e4kchen aus/an); der GRUND je Charakter steht in fehler.log.",
        "\u26a0 Assets loaded incompletely":
            "\u26a0 Assets unvollst\u00e4ndig geladen",
        "Plan frozen \u2013 the quantity belongs to the frozen plan. To change it, unfreeze first ( button).":
            "Plan eingefroren \u2013 die Menge geh\u00f6rt zum eingefrorenen Plan. Zum \u00c4ndern erst das Einfrieren aufheben (-Knopf).",
        "Frozen: recipe structure, quantities and run planner are fixed from now on, progress is ticked off automatically from your ESI jobs. Only the sale price of the final product stays live. Tip: save the plan, then this survives a restart too.":
            "Eingefroren: Rezept-Struktur, Mengen und Runplaner stehen ab jetzt fest, Fortschritt wird aus deinen ESI-Jobs automatisch abgehakt. Nur der Verkaufspreis des Endprodukts bleibt live. Tipp: Plan speichern, dann bleibt das auch nach einem Neustart erhalten.",
        "Frozen \u2013 SAVE the plan, or it is lost on closing!":
            "Eingefroren \u2013 Plan noch SPEICHERN, sonst geht's beim Schlie\u00dfen verloren!",
        "Add to blacklist":
            "Auf die Blacklist",
        "\u21a9 Remove from blacklist":
            "\u21a9 Von der Blacklist nehmen",
        "Cargo per trip in m\u00b3 \u2013 ~350'000 m\u00b3 = 1 jump freighter. 0 = unlimited (no warning/trips).":
            "Frachtraum pro Fahrt in m\u00b3 \u2013 ~350'000 m\u00b3 = 1 Jumpfrachter. 0 = unbegrenzt (keine Warnung/Fahrten).",
        "ON: the freight service rate (ISK/m\u00b3) is added to the purchase price of every material \u2013 the plan then decides \u201ebuy or build\u201c with the LANDED price instead of the hub price. Bulky material becomes less attractive, compact material more.\nThe freight cost is then inside \u201eBuild cost/unit\u201c and is NOT deducted twice.\nOFF: decision purely by hub price, freight cost deducted from profit only at the end (old behaviour).\nThe flat rate per trip is NEVER apportioned \u2013 it is a step function (an item costs nothing extra until it tips the trip) and stays a plan-level line.":
            "AN: der Frachtdienst-Satz (ISK/m\u00b3) wird auf den Kaufpreis jedes Materials aufgeschlagen \u2013 der Plan entscheidet \u201ekaufen oder selbst bauen\u201c dann mit dem LANDEPREIS statt dem Hub-Preis. Sperriges Material wird dadurch unattraktiver, kompaktes attraktiver.\nDie Frachtkosten stecken dann in \u201eBaukosten/Stk\u201c und werden NICHT doppelt abgezogen.\nAUS: Entscheidung rein nach Hub-Preis, Frachtkosten erst am Ende vom Gewinn abgezogen (altes Verhalten).\nDie Pauschale pro Fahrt wird NIE umgelegt \u2013 sie ist eine Sprungfunktion (ein Item kostet nichts extra, bis es die Fahrt kippt) und bleibt eine Position auf Plan-Ebene.",
        "A build plan named \u201e{name}\u201c already exists. Overwrite the existing one or create a new one next to it?":
            "Ein Bauplan namens \u201e{name}\u201c existiert schon. Bestehenden \u00fcberschreiben oder einen neuen daneben anlegen?",
        "Overwrite":
            "\u00dcberschreiben",
        "Create new":
            "Neu anlegen",
        "Cancel":
            "Abbrechen",
        # STUFE C, TEIL 2 (24.09.2026): einmal fragen, wem ein Job gehoert.
        "{n} job(s) not assigned \u2013 assign":
            "{n} Job(s) nicht zugeordnet \u2013 zuordnen",
        "ESI does not say which build plan a job belongs to. For these jobs more than one saved plan builds the same item, so the tool does not guess: they currently count for no plan at all, which makes your shopping list too big. Answer once \u2013 the answer is stored with the job and you will not be asked again.":
            "ESI sagt nicht, zu welchem Bauplan ein Job geh\u00f6rt. Bei diesen Jobs bauen mehrere gespeicherte Pl\u00e4ne dasselbe Item, deshalb r\u00e4t das Werkzeug nicht: sie z\u00e4hlen zurzeit f\u00fcr gar keinen Plan, und deine Einkaufsliste bleibt zu gro\u00df. Einmal antworten \u2013 die Antwort h\u00e4ngt danach am Job, gefragt wird nicht wieder.",
        "Which build plan do these jobs belong to?":
            "Zu welchem Bauplan geh\u00f6ren diese Jobs?",
        "More than one of your saved build plans builds these items, so the tool cannot tell whose job it was. Until you answer, they count for no plan \u2013 your shopping list stays bigger than it needs to be.":
            "Mehrere deiner gespeicherten Baupl\u00e4ne bauen diese Items, deshalb l\u00e4sst sich nicht sagen, wessen Job es war. Solange du nicht antwortest, z\u00e4hlen sie f\u00fcr keinen Plan \u2013 deine Einkaufsliste bleibt gr\u00f6\u00dfer als n\u00f6tig.",
        "Delivered":
            "Geliefert",
        "Belongs to":
            "Geh\u00f6rt zu",
        "None of these":
            "Zu keinem davon",
        "Save assignment":
            "Zuordnung speichern",
        "{n} job(s) assigned.":
            "{n} Job(s) zugeordnet.",
        # VERKAUFSPREIS AUF DER PLAN-KARTE ANKLICKBAR (Nutzer 25.09.2026;
        # seit 26.09.2026 ein Knopf, s. "Sell {sell}").
        "Sale price {price} for {name} copied \u2013 that is the price at which THIS build plan reaches your target margin after fees. The market may pay more or less.":
            "Verkaufspreis {price} f\u00fcr {name} kopiert \u2013 das ist der Preis, bei dem DIESER Bauplan nach Geb\u00fchren deine Ziel-Marge erreicht. Der Markt zahlt vielleicht mehr oder weniger.",
        # DIE ZAHL HIESS "LIVE" UND WAR ES NICHT (25.09.2026).
        "\u26a0 counted {da} \u2013 {fehlt} missing for the remaining runs":
            "\u26a0 gerechnet mit {da} \u2013 {fehlt} fehlen f\u00fcr die restlichen Runs",
        "really in the hangar: {n}":
            "wirklich im Hangar: {n}",
        # KURZERKLAERUNG AN JEDER DETAIL-ZEILE (Nutzer 25.09.2026).
        "Value of all materials in the plan \u2013 bought plus taken from stock, without the freight markup.":
            "Wert aller Materialien des Plans \u2013 gekauft plus aus dem Bestand genommen, ohne Frachtaufschlag.",
        "Freight for the shopping list, at your ISK/m\u00b3 rate.":
            "Fracht f\u00fcr die Einkaufsliste, zu deinem ISK/m\u00b3-Satz.",
        "Installation fees for all jobs: system cost index, structure tax and SCC surcharge.":
            "Anmeldegeb\u00fchren aller Jobs: System-Index, Struktur-Steuer und SCC-Zuschlag.",
        "Material from your own hangar, valued at what replacing it would cost.":
            "Material aus dem eigenen Hangar, bewertet mit dem, was Ersatz kosten w\u00fcrde.",
        "Everything above added up \u2013 what this build costs you.":
            "Alles dar\u00fcber zusammengez\u00e4hlt \u2013 was dich dieser Bau kostet.",
        "Total build cost divided by the quantity.":
            "Gesamte Baukosten geteilt durch die St\u00fcckzahl.",
        "What you still have to BUY, at Jita sell prices \u2013 your stock is not in here.":
            "Was du noch KAUFEN musst, zu Jita-Sell-Preisen \u2013 dein Bestand steckt nicht darin.",
        "The shopping list divided by the quantity.":
            "Die Einkaufsliste geteilt durch die St\u00fcckzahl.",
        "Price per unit at your sell hub \u2013 the basis of this whole calculation.":
            "Preis je St\u00fcck an deinem Verkaufs-Hub \u2013 die Grundlage dieser ganzen Rechnung.",
        "Sale price \u00d7 quantity, before any fees.":
            "Verkaufspreis \u00d7 St\u00fcckzahl, vor allen Geb\u00fchren.",
        "Sales tax and broker fee of the selling character at that hub.":
            "Verkaufssteuer und Broker-Geb\u00fchr des Verkaufs-Charakters an diesem Hub.",
        "The total build cost from the left column.":
            "Die gesamten Baukosten aus der linken Spalte.",
        "Flat fee for hauling it yourself, times the number of trips.":
            "Pauschale f\u00fcrs Selberfahren, mal der Anzahl Fahrten.",
        "Your own flat extra \u2013 contracts, courier, whatever you enter.":
            "Dein eigener Aufschlag \u2013 Contracts, Kurier, was immer du eintr\u00e4gst.",
        "What is left after fees, build cost, trip and extras.":
            "Was nach Geb\u00fchren, Baukosten, Fahrt und Zusatzkosten \u00fcbrig bleibt.",
        "Profit divided by the quantity.":
            "Gewinn geteilt durch die St\u00fcckzahl.",
        "Profit as a percentage of the gross sale proceeds.":
            "Gewinn in Prozent des Brutto-Verkaufserl\u00f6ses.",
        "Below this sale price per unit you make a loss \u2013 fees, trip and extras included.":
            "Unter diesem Verkaufspreis je St\u00fcck machst du Verlust \u2013 Geb\u00fchren, Fahrt und Zusatzkosten einbezogen.",
        # WARUM ETWAS FEHLT, OBWOHL NICHTS FEHLT (25.09.2026).
        "{n} in running jobs":
            "{n} in laufenden Jobs",
        "(covered \u2713 {plan}/{plan}: {gel} delivered \u00b7 {lauf} running)":
            "(gedeckt \u2713 {plan}/{plan}: {gel} geliefert \u00b7 {lauf} laufen)",
        "{r} of {n} runs open":
            "{r} von {n} Runs offen",
        "{n} running":
            "{n} laufen",
        "nothing left to build \u2713":
            "nichts mehr zu bauen \u2713",
        "Every planned run of this item is delivered or running according to ESI (or ticked in the run planner). Nothing to buy, nothing to start.":
            "Jeder geplante Run dieses Items ist laut ESI geliefert oder l\u00e4uft (oder im Runplaner abgehakt). Nichts zu kaufen, nichts zu starten.",
        "Still to build for the open runs: {n} ({r} runs open, delivered and running runs deducted).":
            "F\u00fcr die offenen Runs noch zu bauen: {n} ({r} Runs offen, gelieferte und laufende Runs abgezogen).",
        "{n} units of this are already used up by jobs that are RUNNING right now \u2013 in game the material is gone, but their output is not in the hangar yet, so the plan keeps counting the need. Nothing is really missing here. The number stays as it is on purpose (better to buy too much than too little); tick the running rows in the run planner to take their material out of the list.":
            "{n} Einheiten davon stecken schon in Jobs, die GERADE LAUFEN \u2013 im Spiel ist das Material weg, ihr Erzeugnis liegt aber noch nicht im Hangar, also z\u00e4hlt der Plan den Bedarf weiter mit. Hier fehlt in Wahrheit nichts. Die Zahl bleibt absichtlich stehen (lieber zu viel kaufen als zu wenig); hake die laufenden Zeilen im Runplaner ab, dann f\u00e4llt ihr Material aus der Liste.",
        "\u201eBuild cost/unit\u201c above accounts for batch rounding/surplus for your quantity \u2013 small quantities cost more per unit, large ones less. The tree shows the recipe structure. Blue = build, grey = buy; right-click \u2192 in-game market.":
            "\u201eBaukosten/Stk\u201c oben ber\u00fccksichtigt Batch-Rundung/Verschnitt f\u00fcr deine Menge \u2013 kleine Mengen sind teurer/St\u00fcck, gro\u00dfe g\u00fcnstiger. Der Baum zeigt die Rezept-Struktur. Blau = bauen, grau = kaufen; Rechtsklick \u2192 Ingame-Markt.",
        "Accounts for batch rounding and surplus for your quantity \u2013 small quantities cost more per unit, large ones less.":
            "Ber\u00fccksichtigt Batch-Rundung und Verschnitt f\u00fcr deine Menge \u2013 kleine Mengen sind teurer je St\u00fcck, gro\u00dfe g\u00fcnstiger.",
        "Blue = will be built, grey = will be bought. Right-click \u2192 in-game market.":
            "Blau = wird gebaut, grau = wird gekauft. Rechtsklick \u2192 Ingame-Markt.",
        "Settings were not readable \u2013 defaults apply. The old file is at: {path}":
            "Einstellungen waren nicht lesbar \u2013 es gelten die Vorgaben. Die alte Datei liegt unter: {path}",
        "Your settings.json could not be read. The program continues with default values.\n\nThe old file was NOT deleted, it is here:\n{path}\n\nYour characters, transactions and build plans are NOT affected \u2013 they live in the database, not in this file. Only settings such as fees, standings and hub selection are affected.":
            "Deine settings.json konnte nicht gelesen werden. Das Programm arbeitet mit den Vorgabewerten weiter.\n\nDie alte Datei wurde NICHT gel\u00f6scht, sie liegt hier:\n{path}\n\nDeine Charaktere, Transaktionen und Baupl\u00e4ne sind davon NICHT betroffen \u2013 die stehen in der Datenbank, nicht in dieser Datei. Betroffen sind nur Einstellungen wie Geb\u00fchren, Standings und Hub-Auswahl.",
        "EVE Motor Market knows only {have} of {total} items with a price history in {hub}.\n\nWithout it, Daytrade, Swing Trade and Regional Trading stay almost empty. (The Build tab keeps working, but then rates the demand as unknown.)\n\nLoad the histories for this hub in the background now? You can keep working normally and cancel at any time \u2013 what has already been fetched stays saved.":
            "EVE Motor Market kennt in {hub} erst {have} von {total} Items mit Preisverlauf.\n\nOhne ihn bleiben Daytrade, Swing Trade und Regional Trading fast leer. (Der Bauen-Tab arbeitet weiter, bewertet den Absatz dann aber als unbekannt.)\n\nVerl\u00e4ufe f\u00fcr diesen Hub jetzt im Hintergrund laden? Du kannst normal weiterarbeiten, und abbrechen kannst du jederzeit \u2013 schon Geholtes bleibt gespeichert.",
        "this hub":
            "diesem Hub",
        "Loading price histories \u2026 ({n} open)":
            "Lade Preisverl\u00e4ufe \u2026 ({n} offen)",
        "No character linked \u2013 link a character here first. Until then the tool calculates with base values without skills (7.5 % tax, 3 % broker), i.e. more cautiously than your real fees.":
            "Kein Charakter verkn\u00fcpft \u2013 zuerst hier einen Charakter verkn\u00fcpfen. Bis dahin rechnet das Tool mit Grundwerten ohne Skills (7,5 % Steuer, 3 % Broker), also vorsichtiger als deine echten Geb\u00fchren.",
        "The tool is free and stays free.\n\nIf it helps you, I would be happy about a donation IN GAME:\n\u2022 Corporation: {corp}\n\u2022 Open the corporation window in game and use \u201eGive Money\u201c / a contract there.\n\nThank you \u2013 but everything works the same without a donation.":
            "Das Tool ist kostenlos und bleibt es.\n\nWenn es dir hilft, freue ich mich \u00fcber eine Spende INGAME:\n\u2022 Corporation: {corp}\n\u2022 Im Spiel das Corporation-Fenster \u00f6ffnen und dort \u201eGive Money\u201c / Kontrakt nutzen.\n\nDanke \u2013 aber ohne Spende funktioniert alles genauso.",
        "\u2705 Sent to \u201e{name}\u201c \u2013 the info window of \u201e{corp}\u201c opens in game (this character must be logged in on the client).":
            "\u2705 An \u201e{name}\u201c gesendet \u2013 das Info-Fenster von \u201e{corp}\u201c \u00f6ffnet sich im Spiel (dieser Charakter muss im Client eingeloggt sein).",
        "Hub switched to {hub} \u2013 please run \u201eMarket scan\u201c.":
            "Hub auf {hub} gewechselt \u2013 bitte \u201eMarkt-Scan\u201c.",
        "Hub switched to {hub}. Portfolio/sell list/order update still compare against \u201e{scan}\u201c \u2013 until the next \u201eMarket scan\u201c.":
            "Hub auf {hub} gewechselt. Portfolio/Verkaufsliste/Order-Update vergleichen noch gegen \u201e{scan}\u201c \u2013 bis zum n\u00e4chsten \u201eMarkt-Scan\u201c.",
        "Asking GitHub \u2026":
            "Frage GitHub \u2026",
        "\u2b06 New version available: {new} (you have {own}).":
            "\u2b06 Neue Fassung verf\u00fcgbar: {new} (du hast {own}).",
        "New program version":
            "Neue Programm-Version",
        "Could not compare ({why}). Your version: {own}. Check: https://github.com/{repo}/releases":
            "Konnte nicht vergleichen ({why}). Deine Fassung: {own}. Nachsehen: https://github.com/{repo}/releases",
        "\u2705 You have the latest version ({own}).":
            "\u2705 Du hast die neueste Fassung ({own}).",
        "Could not reach GitHub. Your version: {own}. Check: https://github.com/{repo}/releases":
            "Konnte GitHub nicht erreichen. Deine Fassung: {own}. Nachsehen: https://github.com/{repo}/releases",
        "Current state remembered \u2705\n\nEVE server version: {srv}\nRecipe data (SDE): {sde}\n\nOn the next click I compare with this state and tell you whether EVE had an update in the meantime.":
            "Aktueller Stand gemerkt \u2705\n\nEVE-Server-Version: {srv}\nBaurezepte-Daten (SDE): {sde}\n\nBeim n\u00e4chsten Klick vergleiche ich mit diesem Stand und sage dir, ob EVE zwischenzeitlich ein Update hatte.",
        "unknown":
            "unbekannt",
        "No NEW update since the last notice \u2013 BUT: the patch reported back then has not been loaded yet. Your recipes are still outdated.\n\nOpen \u201eLoad recipes\u201c now?":
            "Kein NEUES Update seit dem letzten Hinweis \u2013 ABER: der damals gemeldete Patch wurde noch nicht geladen. Deine Baurezepte sind weiterhin veraltet.\n\nJetzt \u201eBaurezepte laden\u201c \u00f6ffnen?",
        "\u26A0 EVE had an update":
            "\u26A0 EVE hatte ein Update",
        "\u2192 Recommendation: reload the recipes so build times and materials are current.\n\nNote: if build times or structure bonuses (e.g. Tatara reaction time) look odd after reloading, a game rule may have changed. The tool cannot update itself \u2013 please report such cases so they can be adjusted in the program.\n\nOpen \u201eLoad recipes\u201c now?":
            "\u2192 Empfehlung: Baurezepte neu laden, damit Bauzeiten und Materialien aktuell sind.\n\nHinweis: Falls nach dem Neu-Laden Bauzeiten oder Struktur-Boni (z.B. Tatara-Reaktionszeit) komisch aussehen, kann sich eine Spielregel ge\u00e4ndert haben. Das Tool kann sich nicht selbst updaten \u2013 solche F\u00e4lle bitte melden, damit sie im Programm angepasst werden.\n\nJetzt \u201eBaurezepte laden\u201c \u00f6ffnen?",
        "Recipes":
            "Baurezepte",
        "Recipes + build times are already loaded.\n\nA fresh download (~140 MB) is only needed if EVE had an update. Download again anyway?":
            "Baurezepte + Bauzeiten sind bereits geladen.\n\nEin Neu-Download (~140 MB) ist nur n\u00f6tig, wenn EVE ein Update hatte. Trotzdem neu herunterladen?",
        "Loading SDE database \u2026 {d}/{tot} MB (please wait)":
            "Lade SDE-Datenbank \u2026 {d}/{tot} MB (bitte warten)",
        "Warning: only {m} materials / {p} products loaded \u2013 the source returned unexpected data. Please try again or report the numbers to me.":
            "Achtung: nur {m} Materialien / {p} Produkte geladen \u2013 die Quelle lieferte unerwartete Daten. Bitte erneut versuchen oder mir die Zahlen melden.",
        "Recipes loaded. \u201eBelow build price\u201c usable.":
            "Baurezepte geladen. \u201eUnter Baupreis\u201c nutzbar.",
        "Recipes loaded.":
            "Baurezepte geladen.",
        "Please run \u201eMarket scan\u201c first.":
            "Bitte zuerst \u201eMarkt-Scan\u201c.",
        "The compact/meta-level filter needs a current SDE \u2013 please run \u201eLoad recipes\u201c once (again), then metaLevel is available.":
            "Der Compact/Meta-Level-Filter braucht eine aktuelle SDE \u2013 bitte einmal \u201eBaurezepte laden\u201c (neu), dann steht metaLevel bereit.",
        "No items of this category/meta class in the current hub scan.":
            "Keine Items in dieser Kategorie/Meta-Klasse im aktuellen Hub-Scan.",
        "Gold search":
            "Gold-Suche",
        "Gold search filtered to markets that can absorb ~{cap} ({n} hits).":
            "Gold-Suche gefiltert auf M\u00e4rkte, die ~{cap} aufnehmen k\u00f6nnen ({n} Treffer).",
        "{name} \u2013 no history in the cache.":
            "{name} \u2013 kein Verlauf im Cache.",
        "{n} gold items added to the shopping list (quantity 1 \u2013 please adjust).":
            "{n} Gold-Items in die Einkaufsliste (Menge 1 \u2013 bitte anpassen).",
        "{n} items added to the shopping cart. Quantity = 1-day intake; adjustable in the list.":
            "{n} Items in den Einkaufswagen \u00fcbernommen. Menge = 1-Tages-Einnahme; in der Liste anpassbar.",
        "Please switch \u201eOpen in game\u201c on in the settings and re-link the character (permission esi-ui.open_window.v1).":
            "Bitte in Einstellungen \u201eIngame \u00f6ffnen\u201c auf An stellen und den Charakter neu verkn\u00fcpfen (Berechtigung esi-ui.open_window.v1).",
        "\u2705 Sent to \u201e{name}\u201c \u2013 the market window opens in game (this character must be logged in on the client).":
            "\u2705 An \u201e{name}\u201c gesendet \u2013 Marktfenster \u00f6ffnet sich im Spiel (dieser Charakter muss im Client eingeloggt sein).",
        "Opening the market failed: ":
            "Markt \u00f6ffnen fehlgeschlagen: ",
        "Your login predates the scope change.\n\n\u2192 FIX: open the Characters tab, \u201e\u2715 Remove\u201c the character and link it again. The token then has all permissions (incl. open market + read skills) and it works again.\n\n(Technical: ":
            "Dein Login ist nach der Scope-\u00c4nderung veraltet.\n\n\u2192 L\u00d6SUNG: Charaktere-Tab \u00f6ffnen, den Charakter \u201e\u2715 Entfernen\u201c und neu verkn\u00fcpfen. Danach hat der Token alle Berechtigungen (inkl. Markt \u00f6ffnen + Skills lesen) und es funktioniert wieder.\n\n(Technisch: ",
        "\n\nCommon causes:\n\u2022 The market window is not open in game \u2013 EVE can only load the item into an already open market window.\n\u2022 The character is not logged in right now.\n\u2022 Not re-linked after the scope change \u2192 Characters tab: remove and link again.":
            "\n\nH\u00e4ufige Ursachen:\n\u2022 Das Marktfenster ist im Spiel nicht ge\u00f6ffnet \u2013 EVE kann das Item nur in ein bereits offenes Marktfenster laden.\n\u2022 Der Charakter ist gerade nicht im Spiel eingeloggt.\n\u2022 Nach Scope-\u00c4nderung nicht neu verkn\u00fcpft \u2192 Charaktere-Tab: entfernen und neu verkn\u00fcpfen.",
        "{copies} copies \u00d7 {runs} runs - derived automatically from the invention success chance (Invention tab).":
            "{copies} Kopien \u00d7 {runs} Runs - automatisch aus der Invention-Erfolgschance abgeleitet (Invention-Tab).",
        "{n} item(s) loaded from ESI - exact values per item (incl. BPO/BPC) in the Blueprints tab.":
            "{n} Item(s) aus ESI geladen - genaue Werte je Item (inkl. BPO/BPC) im Blueprints-Tab.",
        "No ESI access or no linked characters.":
            "Kein ESI-Zugang oder keine verkn\u00fcpften Charaktere.",
        "No items at this stage.":
            "Keine Items in dieser Stufe.",
        "{a} of {b} items covered":
            "{a} von {b} Items abgedeckt",
        " ({n} as BPO)":
            " ({n} als BPO)",
        " - exact values per item in the Blueprints tab, the run planner uses them directly for scheduling.":
            " - genaue Werte je Item im Blueprints-Tab, der Runplaner nutzt sie direkt f\u00fcr die Zeitplanung.",
        "{a}/{b} items covered by ESI blueprints \u2713":
            "{a}/{b} Items mit ESI-Blaupausen abgedeckt \u2713",
        "Build cost per stage appears here once you have calculated a stage.":
            "Baukosten je Stufe erscheinen hier, sobald du eine Stufe gerechnet hast.",
        "Only this stage is calculated \u2013 click the others to compare.<br>":
            "Nur diese Stufe ist gerechnet \u2013 klick die anderen an, um zu vergleichen.<br>",
        "The SDE does not know any implant bonuses yet.\n\nPlease click \u201eLoad recipes\u201c at the top once and confirm the fresh download with \u201eYes\u201c when asked (once, approx. 140\u2009MB). Then reopen this dialog.":
            "Die SDE kennt noch keine Implantat-Boni.\n\nBitte einmal oben \u201eBaurezepte laden\u201c klicken und beim Nachfragen mit \u201eJa\u201c den Neu-Download best\u00e4tigen (einmalig, ca. 140\u2009MB). Danach diesen Dialog neu \u00f6ffnen.",
        "Fetching system index from ESI \u2026":
            "System-Index wird aus ESI geholt \u2026",
        "Fetching system index + security from ESI \u2026":
            "System-Index + Sicherheit werden aus ESI geholt \u2026",
        "NPC station (no rigs)":
            "NPC-Station (keine Rigs)",
        "\u2192 Blueprint material efficiency: {me} %   \u00b7   Rig bonuses (ME/TE) now come from the assigned structure (in the \u201eStructure fitting\u201c, category-specific per build plan).":
            "\u2192 Blueprint-Material-Effizienz: {me} %   \u00b7   Rig-Boni (ME/TE) kommen jetzt aus der zugewiesenen Struktur (im \u201eStruktur-Fitting\u201c, kategorie-spezifisch je Bauplan).",
        "Build plan":
            "Bauplan",
        "Run \u201eMarket scan\u201c first - the market prices are missing.":
            "Erst \u201eMarkt-Scan\u201c - es fehlen die Marktpreise.",
        "Calculating build plan for {name} \u2026":
            "Berechne Bauplan f\u00fcr {name} \u2026",
        "{name} cannot be built, or a material cannot be priced (market scan current?).":
            "{name} ist nicht baubar, oder ein Material l\u00e4sst sich nicht bepreisen (Markt-Scan aktuell?).",
        "Build plan error: ":
            "Bauplan-Fehler: ",
        "Does not fit in one trip":
            "Passt nicht in eine Fahrt",
        "The shopping list has {vol} m\u00b3, your cargo hold {cap} m\u00b3.\nThat is {n} trips.\n\nAdd anyway?":
            "Die Einkaufsliste hat {vol} m\u00b3, dein Frachtraum {cap} m\u00b3.\nDas sind {n} Fahrten.\n\nTrotzdem hinzuf\u00fcgen?",
        "Mark \u201e{name}\u201c as completed?\n\nThe plan then counts as finished, even if the ESI check never reaches the full quantity.":
            "\u201e{name}\u201c als abgeschlossen markieren?\n\nDer Plan gilt danach als fertig, auch wenn der ESI-Check die volle St\u00fcckzahl nie erreicht.",
        "\n\nThe material reservation is RELEASED in the process \u2013 other build plans then see the material as available again.":
            "\n\nDie Material-Reservierung wird dabei FREIGEGEBEN \u2013 andere Baupl\u00e4ne sehen das Material dann wieder als verf\u00fcgbar.",
        "Complete plan?":
            "Plan abschlie\u00dfen?",
        "End products":
            "Endprodukte",
        "Components":
            "Komponenten",
        "Reactions":
            "Reaktionen",
        "profitable only":
            "nur profitable",
        "Inventable T2":
            "Erfindbare T2",
        "\u26a0 Sample data ({n}) \u2013 no characters linked or blueprint scope missing. Re-link the character in game.":
            "\u26a0 Beispieldaten ({n}) \u2013 keine Charaktere verkn\u00fcpft oder Blueprint-Scope fehlt. Im Spiel Charakter neu verkn\u00fcpfen.",
        "{n} blueprints loaded. For profit/ISK per hour: load recipes (Scanner: \u201eLoad recipes\u201c) + one market scan.":
            "{n} Blueprints geladen. F\u00fcr Gewinn/ISK-Std: Baurezepte laden (Scanner: \u201eBaurezepte laden\u201c) + einmal Markt-Scan.",
        "{n} blueprints":
            "{n} Blueprints",
        " \xb7 {n} inventable T2 from your T1":
            " \u00b7 {n} erfindbare T2 aus deinen T1",
        " \u00b7 {calc} with profit calculated \u00b7 {prof} currently profitable. Tip: sort by \u201eISK/h\u201c for the best hourly rate.":
            " \u00b7 {calc} mit Gewinn berechnet \u00b7 {prof} aktuell profitabel. Tipp: nach \u201eISK/Std\u201c sortieren f\u00fcr den besten Stundenlohn.",
        "  \u26a0 {n} structure(s) without a name: ":
            "  \u26a0 {n} Struktur(en) ohne Namen: ",
        " \u2013 ESI error limit reached, run \u201eLoad blueprints\u201c again in about 1 min for the rest.":
            " \u2013 ESI-Error-Limit erreicht, in ca. 1 Min. erneut \u201eBlueprints laden\u201c f\u00fcr die restlichen.",
        "  \u26a0 Category has >500 missing items \u2013 only the first ones shown. For the complete list, choose a group as well.":
            "  \u26a0 Kategorie hat >500 fehlende Items \u2013 nur die ersten gezeigt. F\u00fcr die komplette Liste zus\u00e4tzlich eine Gruppe w\u00e4hlen.",
        "(not buildable / no market product)":
            "(nicht baubar / kein Marktprodukt)",
        "Find locations and link all":
            "Orte finden und alle verkn\u00fcpfen",
        "  ({n} open)":
            "  ({n} offen)",
        "  \u2713 all linked":
            "  \u2713 alle verkn\u00fcpft",        "\u2014 none (assets not location-bound) \u2014":
            "\u2014 keine (Assets nicht ortsgebunden) \u2014",
        "\u2192 Effective (security \u00d7{sec}):  Material up to \u2212{me} %  \u00b7  Time \u2212{te} %  \u00b7  Reaction mat up to \u2212{rme} %  \u00b7  Job cost \u2212{cost} %\n(Material rigs only affect the matching item type \u2013 e.g. \u201eAdvanced Component\u201c not the ship hull.)":
            "\u2192 Effektiv (Sicherheit \u00d7{sec}):  Material bis \u2212{me} %  \u00b7  Zeit \u2212{te} %  \u00b7  Reakt-Mat bis \u2212{rme} %  \u00b7  Job-Kosten \u2212{cost} %\n(Material-Rigs wirken nur auf die passende Item-Art \u2013 z. B. \u201eAdvanced Component\u201c nicht auf die Schiffsh\u00fclle.)",
        "Split yourself: {items} items \u00b7 {runs} runs in total \u2013 spread the blueprints across your characters yourself.":
            "Selber aufteilen: {items} Items \u00b7 {runs} Runs gesamt \u2013 verteile die Blaupausen selbst auf deine Chars.",
        "Order: reactions (Intermediate first, then Composite) \u2192 components \u2192 end product. \u201e\u00d7BP\u201c = that many copies you have per setup (that many jobs in parallel).":
            "Reihenfolge: Reaktionen (erst Intermediate, dann Composite) \u2192 Komponenten \u2192 Endprodukt. \u201e\u00d7BP\u201c = so viele Kopien hast du laut Setup (so viele Jobs parallel).",
        "\u201eFind blueprints\u201c works with the scanner filters (preset, category, tech level, margin \u2026) and therefore needs the scanner page. Please switch to \u201eScanner\u201c at the top left of the Build tab and try again there.":
            "\u201eBlaupausen suchen\u201c arbeitet mit den Scanner-Filtern (Preset, Kategorie, Tech-Stufe, Marge \u2026) und braucht deshalb die Scanner-Seite. Bitte im Bauen-Tab links oben auf \u201eScanner\u201c wechseln und es dort erneut versuchen.",
        "Please run \u201eMarket scan\u201c in the Daytrade or Swing tab first.":
            "Bitte zuerst im Daytrade- oder Swing-Tab \u201eMarkt-Scan\u201c.",
        "No buildable items (T1\u2013T3) of this category/tech level in the current scan.":
            "Keine baubaren Items (T1\u2013T3) in dieser Kategorie/Tech-Stufe im aktuellen Scan.",
        "{n} capital ships found \u00b7 {priced} with build-cost estimate \u00b7 {contract} with contract sale price (margin/profit calculated for those only). \u00d8 daily volume/volatility do not exist for contracts - no price history in ESI for them.":
            "{n} Capital-Schiffe gefunden \u00b7 {priced} mit Baukosten-Sch\u00e4tzung \u00b7 {contract} mit Contract-Verkaufspreis (Marge/Gewinn nur f\u00fcr die berechnet). \u00d8 Tagesvolumen/Volatilit\u00e4t gibt's f\u00fcr Contracts nicht - keine Preis-Historie in ESI daf\u00fcr.",
        "Contract scan finished (all of New Eden): {n} capital type(s) with public offers found. Public contracts only - ESI does not see alliance-internal ones without Director/Accountant access to the respective corp.":
            "Contract-Scan fertig (ganz New Eden): {n} Capital-Typ(en) mit \u00f6ffentlichem Angebot gefunden. Nur \u00f6ffentliche Contracts - Allianz-interne sieht ESI nicht ohne Director/Accountant-Zugang zur jeweiligen Corp.",        "{n} hold candidates. ":
            "{n} Halten-Kandidaten. ",
        "Sortable by column click \u00b7 double-click = history \u00b7 right-click = open in game / shopping list.":
            "Sortierbar per Spaltenklick \u00b7 Doppelklick = Verlauf \u00b7 Rechtsklick = Ingame \u00f6ffnen / Einkaufsliste.",
        "\u2728 Swing gold search \u2013 best items to collect":
            "\u2728 Swing Gold-Suche \u2013 beste Items zum Einsammeln",
        "Swing gold filtered to markets that can absorb ~{cap} ({n} hits).":
            "Swing-Gold gefiltert auf M\u00e4rkte, die ~{cap} aufnehmen k\u00f6nnen ({n} Treffer).",
        "{name} added to the shopping list.":
            "{name} in die Einkaufsliste.",
        "0  \u2013 not on site":
            "0  \u2013 nicht vor Ort",
        "Nothing copied \u2013 the plan has 0 {what} (everything is built or covered from stock/jobs, see status per row).":
            "Nichts kopiert \u2013 der Plan hat 0 {what} (alles wird gebaut oder ist aus Bestand/Jobs gedeckt, s. Status je Zeile).",
        "No {what} to copy.":
            "Keine {what} zum Kopieren.",
        "Floor calculation":
            "Boden-Rechnung",
        "Please run \u201eLoad recipes\u201c first.":
            "Bitte zuerst \u201eBaurezepte laden\u201c.",
        "No build recipe found for this item.":
            "Kein Bau-Rezept f\u00fcr dieses Item gefunden.",
        "{n} swing items added to the shopping cart.":
            "{n} Swing-Items in den Einkaufswagen \u00fcbernommen.",
        "Enable structures":
            "Strukturen aktivieren",
        "Please switch \u201eStructure markets\u201c on in the settings first and re-link the character (for the structure permission).":
            "Bitte erst in Einstellungen \u201eStruktur-M\u00e4rkte\u201c auf An stellen und den Charakter neu verkn\u00fcpfen (f\u00fcr die Struktur-Berechtigung).",
        "Character missing":
            "Charakter fehlt",
        "Link a character with market access first.":
            "Erst einen Charakter verkn\u00fcpfen, der Marktzugang hat.",
        "Auto search failed \u2013 please enter the ID manually.":
            "Auto-Suche fehlgeschlagen \u2013 bitte ID manuell.",
        "Link a character with access to the structure first.":
            "Erst einen Charakter verkn\u00fcpfen, der Zugang zur Struktur hat.",
        "Not assigned":
            "Nicht zugeordnet",
        "These build structures could NOT be assigned:\n\n":
            "Diese Bau-Strukturen konnten NICHT zugeordnet werden:\n\n",
        "\n\nReal locations found:\n":
            "\n\nGefundene echte Orte:\n",
        "\n\nAssignment is by NAME (system + name). If your build structure above is named differently from the real structure, name it the same (Edit \u2192 Name) \u2013 then it works by itself on the next click.\nIf a location is not in the list at all, ESI found neither assets nor orders there.\n\nImmediate alternative: set the stock scope in the build plan to \u201e Everywhere\u201c \u2013 then material at ANY location counts, linked or not.":
            "\n\nZugeordnet wird \u00fcber den NAMEN (System + Name). Hei\u00dft deine Bau-Struktur oben anders als die echte Struktur, benenne sie gleich (Bearbeiten \u2192 Name) \u2013 dann klappt es beim n\u00e4chsten Klick von selbst.\nSteht ein Ort gar nicht in der Liste, hat ESI dort weder Assets noch Orders gefunden.\n\nSofort-Alternative: im Bauplan den Bestands-Scope auf \u201e \u00dcberall\u201c stellen \u2013 dann z\u00e4hlt Material an JEDEM Ort, egal ob verkn\u00fcpft.",
        "Structures linked":
            "Strukturen verkn\u00fcpft",
        "These build structures are now linked to their real location \u2013 their assets count in the build plan from now on:\n\n":
            "Diese Bau-Strukturen sind jetzt mit ihrem echten Ort verkn\u00fcpft \u2013 ihre Assets z\u00e4hlen ab sofort im Bauplan:\n\n",
        "\n\nLeft without a link: ":
            "\n\nOhne Verkn\u00fcpfung blieben: ",
        "\nESI found neither assets nor orders there \u2013 so you currently have nothing there. That is not an error: as soon as material lies there, it is detected automatically on the next click.":
            "\nDort hat ESI weder Assets noch Orders gefunden \u2013 du hast dort also aktuell nichts. Das ist kein Fehler: sobald dort Material liegt, wird es beim n\u00e4chsten Klick automatisch erkannt.",
        "Structures added":
            "Strukturen hinzugef\u00fcgt",
        "Found and saved:\n\n":
            "Gefunden und gespeichert:\n\n",
        "\n\nNow choose it in the \u201eBuild location\u201c dropdown above.":
            "\n\nJetzt oben im \u201eBau-Ort\u201c-Dropdown ausw\u00e4hlen.",
        "No new structures":
            "Keine neuen Strukturen",
        "No new structures found in your assets/orders \u2013 either they are already saved (then they are already in the dropdown), or the character has nothing there.":
            "Keine neuen Strukturen in deinen Assets/Orders gefunden \u2013 entweder sind sie schon gespeichert (dann stehen sie schon im Dropdown), oder der Charakter hat dort nichts.",
        "Structure search failed":
            "Struktur-Suche fehlgeschlagen",
        "Could not load assets/orders: ":
            "Konnte Assets/Orders nicht laden: ",
        "Searching your structures (assets + orders) \u2026 takes 10\u201320 s":
            "Suche deine Strukturen (Assets + Orders) \u2026 dauert 10\u201320 s",
        "Not recognised":
            "Nicht erkannt",
        "Could not find a structure ID. Paste the structure link copied in game or enter the plain ID (digits only).":
            "Konnte keine Struktur-ID finden. F\u00fcge den ingame kopierten Struktur-Link ein oder gib die reine ID (nur Ziffern) ein.",
        "  \u2013 no results (old table discarded).":
            "  \u2013 keine Ergebnisse (alte Tabelle verworfen).",
        "{n} items added to the shopping list.":
            "{n} Items in die Einkaufsliste.",
        "buy orders":
            "Buy-Orders",
        "sell orders":
            "Sell-Orders",
        "Loading {side} for {name} \u2026":
            "Lade {side} f\u00fcr {name} \u2026",
        "Could not load orders: ":
            "Konnte Orders nicht laden: ",
        "choose a quantity or click an order.":
            "Menge w\u00e4hlen oder eine Order anklicken.",
        "{name} is already in the shopping cart \u2013 change the quantity there or remove it first. (No double purchase.)":
            "{name} liegt schon im Einkaufswagen \u2013 Menge dort \u00e4ndern oder erst entfernen. (Kein Doppelkauf.)",
        "{name} is already in the shopping cart.":
            "{name} ist bereits im Einkaufswagen.",
        "{qty} {name} added to the shopping cart.":
            "{qty} {name} zum Einkaufswagen hinzugef\u00fcgt.",
        "No sale price available.":
            "Kein Verkaufspreis verf\u00fcgbar.",
        "Sale price {price} for {name} copied \u2013 paste it into the price field of the sell order in game (undercuts the best sell by one tick).":
            "Verkaufspreis {price} f\u00fcr {name} kopiert \u2013 im Spiel ins Preisfeld der Verkaufs-Order einf\u00fcgen (unterbietet den besten Sell um einen Tick).",
        # ZIEL-PREIS-MODUS: dieselbe Zahl, aber eine ANDERE Bedeutung -
        # deshalb ein eigener Satz und nicht derselbe mit Zusatz.
        "Sale price {price} for {name} copied \u2013 that is YOUR target margin on the average buy price, independent of the current market price.":
            "Verkaufspreis {price} f\u00fcr {name} kopiert \u2013 das ist DEINE Ziel-Marge auf den \u00d8-Einkaufspreis, unabh\u00e4ngig vom aktuellen Marktpreis.",
        "Sale price {price} for {name} copied \u2013 your target price would be BELOW the current market here, so this is the market price minus one tick: it sells just as fast and earns more than your target margin.":
            "Verkaufspreis {price} f\u00fcr {name} kopiert \u2013 dein Ziel-Preis l\u00e4ge hier UNTER dem aktuellen Markt, deshalb ist das der Marktpreis minus einen Tick: verkauft genauso schnell und bringt mehr als deine Ziel-Marge.",
        "\u201e{name}\u201c copied \u2013 paste into the search in the inventory.":
            "\u201e{name}\u201c kopiert \u2013 im Inventar in die Suche einf\u00fcgen.",
        "\u21a9 Undo adjustment (currently {n}\u00d7)":
            "\u21a9 Nachbesserung r\u00fcckg\u00e4ngig (aktuell {n}\u00d7)",
        "Orders checked: {b} buy ({nb} to adjust), {s} sell ({ns} to adjust":
            "Orders gepr\u00fcft: {b} Buy ({nb} nachbessern), {s} Sell ({ns} nachbessern",
        ", {n} of them only at a loss":
            ", davon {n} nur mit Verlust",
        "{name}: this new price probably leads to a loss or zero profit.":
            "{name}: dieser neue Preis f\u00fchrt vermutlich zu Verlust oder Nullsummen-Gewinn.",
        "\n\nCopy anyway?":
            "\n\nTrotzdem kopieren?",
        "Copy anyway":
            "Trotzdem kopieren",
        "New price {price} for {name} copied \u2013 in game right-click the order, \u201emodify\u201c and paste.":
            "Neuer Preis {price} f\u00fcr {name} kopiert \u2013 ingame die Order per Rechtsklick \u201e\u00e4ndern\u201c und einf\u00fcgen.",
        "Work-through mode on: \u201eNext\u201c opens each order to adjust one after another + copies the price (you do the modifying in game).":
            "Abarbeiten-Modus an: \u201eN\u00e4chste\u201c \u00f6ffnet der Reihe nach jede nachzubessernde Order + kopiert den Preis (\u00e4ndern machst du ingame).",
        "Work-through mode off.":
            "Abarbeiten-Modus aus.",
        "No orders to adjust on this page \u2013 run \u201eCheck orders\u201c first.":
            "Keine nachzubessernden Orders auf dieser Seite \u2013 erst \u201eOrders pr\u00fcfen\u201c.",
        "End of list \u2013 starting over":
            "Liste durch \u2013 von vorn",
        "[{i}/{n}] {name}: market opened, new price {price} copied \u2013 in game \u201emodify\u201c the order + paste, then \u201eNext\u201c.":
            "[{i}/{n}] {name}: Markt ge\u00f6ffnet, neuer Preis {price} kopiert \u2013 ingame Order \u201e\u00e4ndern\u201c + einf\u00fcgen, dann \u201eN\u00e4chste\u201c.",
        "Sell list cleared \u2013 Tools \u203a \u201eFill from portfolio\u201c brings it back.":
            "Verkaufsliste geleert \u2013 Werkzeuge \u203a \u201eAus Portfolio f\u00fcllen\u201c holt sie zur\u00fcck.",
        "{n} items \u2013 the sell window only takes {lim} at once, so work in {blocks} blocks.":
            "{n} Items \u2013 das Verkaufsfenster nimmt nur {lim} auf einmal, also in {blocks} Bl\u00f6cken arbeiten.",
        "No character linked \u2013 orders cannot be checked.":
            "Kein Charakter verkn\u00fcpft \u2013 Orders nicht pr\u00fcfbar.",
        "Checking open buy orders \u2026":
            "Pr\u00fcfe offene Buy-Orders \u2026",
        "Checking open sell orders \u2026":
            "Pr\u00fcfe offene Sell-Orders \u2026",
        "Sell list is empty.":
            "Verkaufsliste ist leer.",
        "Loading current sell prices ({hub}) \u2026":
            "Lade aktuelle Sell-Preise ({hub}) \u2026",
        "Fetching sell prices ({hub}) for {n} row(s) \u2026":
            "Hole Sell-Preise ({hub}) f\u00fcr {n} Zeile(n) \u2026",
        "{n} rows copied \u2013 CAREFUL: the sell window only takes {lim} items at once. Work in {blocks} blocks: select and paste {lim} items first, then the next ones.":
            "{n} Zeilen kopiert \u2013 ACHTUNG: das Verkaufsfenster nimmt nur {lim} Items auf einmal. Arbeite in {blocks} Bl\u00f6cken: erst {lim} Items markieren und einf\u00fcgen, dann die n\u00e4chsten.",
        "{n} rows copied \u2013 in the sell window choose \u201eImport prices from clipboard (Decimal Point)\u201c. Tip: drag exactly {n} items into the sell window before pasting - if the count differs, the total proceeds are off too.":
            "{n} Zeilen kopiert \u2013 im Verkaufsfenster \u201eImport prices from clipboard (Decimal Point)\u201c w\u00e4hlen. Tipp: zieh genau {n} Items ins Verkaufsfenster, bevor du einf\u00fcgst - weicht die Anzahl ab, stimmt am Ende auch der Gesamterl\u00f6s nicht.",
        "Suggestion: {units} units  \u2248 {isk}  (= {pct} % of daily volume)":
            "Vorschlag: {units} Stk  \u2248 {isk}  (= {pct} % des Tagesvolumens)",
        "Quantity set to {n} (buy-order suggestion applied).":
            "Menge auf {n} gesetzt (Buy-Order-Vorschlag \u00fcbernommen).",
        "{name} added.":
            "{name} hinzugef\u00fcgt.",
        "Item not found \u2013 use the exact name.":
            "Item nicht gefunden \u2013 exakten Namen nutzen.",
        "No character selected.":
            "Kein Charakter gew\u00e4hlt.",
        "Suggested quantity (by daily volume) applied for {n} items.":
            "F\u00fcr {n} Items die vorgeschlagene Menge (nach Tagesvolumen) \u00fcbernommen.",
        "No suggestions available":
            "Keine Vorschl\u00e4ge vorhanden",        "Work-through mode on: \u201eNext\u201c opens each shopping item one after another + copies the buy-order price (you do the buying in game).":
            "Abarbeiten-Modus an: \u201eN\u00e4chste\u201c \u00f6ffnet der Reihe nach jedes Einkaufs-Item + kopiert den Buy-Order-Preis (Kauf machst du ingame).",
        "Shopping cart is empty.":
            "Einkaufswagen ist leer.",
        "[{i}/{n}] {name}: market opened":
            "[{i}/{n}] {name}: Markt ge\u00f6ffnet",
        ", buy-order price {price} copied":
            ", Buy-Order-Preis {price} kopiert",
        " (no price \u2013 run \u201eLoad prices\u201c first)":
            " (kein Preis \u2013 erst \u201ePreise laden\u201c)",
        "No buy-order price available \u2013 run \u201eLoad prices\u201c first.":
            "Kein Buy-Order-Preis verf\u00fcgbar \u2013 erst \u201ePreise laden\u201c.",
        "Buy-order price {price} for {name} copied \u2013 paste it into the price field of the buy order in game (outbids the best buy by exactly one valid tick).":
            "Buy-Order-Preis {price} f\u00fcr {name} kopiert \u2013 im Spiel ins Preisfeld der Kauf-Order einf\u00fcgen (\u00fcberbietet den besten Buy um genau einen g\u00fcltigen Tick).",
        "{n} items copied to Multibuy \u2013 paste in game (CTRL+V in the Multibuy window).":
            "{n} Items ins Multibuy kopiert \u2013 ingame einf\u00fcgen (STRG+V im Multibuy-Fenster).",
        "Showing the newest {shown} of {total} transactions. Use the filters or the CSV export for the rest. (The summary above counts all of them.)":
            "Zeige die neuesten {shown} von {total} Transaktionen. Nutze die Filter oder den CSV-Export f\u00fcr den Rest. (Die Zusammenfassung oben rechnet \u00fcber alle.)",
        "{n} transactions (all shown).":
            "{n} Transaktionen (alle gezeigt).",
        "Sell":
            "Verkauf",
        "No transactions to export.":
            "Keine Transaktionen zum Exportieren.",
        "Export transactions":
            "Transaktionen exportieren",
        "CSV files (*.csv)":
            "CSV-Dateien (*.csv)",
        "Date":
            "Datum",
        "Type":
            "Typ",
        "Price/unit":
            "Preis/Stk",
        "Total":
            "Summe",
        "Item not found.":
            "Item nicht gefunden.",
        "Loading price history \u2026":
            "Lade Preisverlauf \u2026",
        "No history available (item may be traded rarely).":
            "Keine Historie verf\u00fcgbar (Item wird evtl. kaum gehandelt).",
        "Browser opened \u2013 please log in \u2026":
            "Browser ge\u00f6ffnet \u2013 bitte einloggen \u2026",
        "Refreshes wallet, transactions, assets and orders, plus live hub prices for everything you hold or have on order. The big market scan of all items only runs if it is older than 6 h.":
            "Holt Wallet, Transaktionen, Assets und Orders neu, dazu Live-Hub-Preise f\u00fcr alles, was du hast oder in Orders stehen hast. Der gro\u00dfe Markt-Scan aller Items l\u00e4uft nur, wenn er \u00e4lter als 6 h ist.",
        "{name} linked. For the new data press \u201eRefresh\u201c at the top.":
            "{name} verkn\u00fcpft. F\u00fcr die neuen Daten oben \u201eAktualisieren\u201c dr\u00fccken.",
        "{n} of your items": "{n} deiner Items",
        "{name} linked.":
            "{name} verkn\u00fcpft.",
        "Remove character?":
            "Charakter entfernen?",
        "Remove the character and its locally stored data?":
            "Charakter und seine lokal gespeicherten Daten entfernen?",
        "\u26a0 This deletes the entire local transaction history of this character. On re-linking, EVE/ESI only returns the last ~30 days \u2013 older history (and the profit calculated from it) is gone for good afterwards.":
            "\u26a0 Dabei wird die gesamte lokale Transaktions-Historie dieses Charakters gel\u00f6scht. EVE/ESI liefert beim Neu-Verkn\u00fcpfen nur die letzten ~30 Tage zur\u00fcck \u2013 \u00e4ltere Historie (und damit der daraus berechnete Gewinn) ist danach unwiederbringlich weg.",
        "\n\nAffected: {n} stored transactions.":
            "\n\nBetroffen: {n} gespeicherte Transaktionen.",
        "\n\nA backup of the database is created automatically before deleting.":
            "\n\nEs wird automatisch ein Backup der Datenbank angelegt, bevor gel\u00f6scht wird.",
        "Remove permanently":
            "Endg\u00fcltig entfernen",
        "Client ID from developers.eveonline.com":
            "Client-ID von developers.eveonline.com",
        "Off (transactions only)":
            "Aus (nur Transaktionen)",
        "On (real inventory)":
            "An (echtes Inventar)",
        "{name} {ver}. The button asks GitHub whether there is a newer version \u2013 the tool can NOT update itself, it only tells you and where to find it.":
            "{name} {ver}. Der Knopf fragt bei GitHub nach, ob es eine neuere Fassung gibt \u2013 das Tool kann sich NICHT selbst aktualisieren, es sagt dir nur Bescheid und wo du sie findest.",
        "Size not readable: ":
            "Gr\u00f6\u00dfe nicht lesbar: ",
        "Database: {size}  \u00b7  Market history: {hist} rows  \u00b7  Snapshot: {snap} items  \u00b7  Transactions: {tx} (are kept)":
            "Datenbank: {size}  \u00b7  Markt-Historie: {hist} Zeilen  \u00b7  Snapshot: {snap} Items  \u00b7  Transaktionen: {tx} (bleiben erhalten)",
        "Clear market cache":
            "Markt-Cache leeren",
        "The cached market history and the last hub scan are deleted and the database shrinks.\n\nOn the next \u201eMarket scan\u201c / \u201eCalculate deals\u201c everything is reloaded automatically (slower once).\n\nTransactions, characters and shopping list are kept. Continue?":
            "Zwischengespeicherte Markt-Historie und der letzte Hub-Scan werden gel\u00f6scht und die Datenbank verkleinert.\n\nBeim n\u00e4chsten \u201eMarkt-Scan\u201c / \u201eDeals berechnen\u201c wird alles automatisch neu geladen (einmalig langsamer).\n\nTransaktionen, Charaktere und Einkaufsliste bleiben erhalten. Fortfahren?",
        "Cleanup error: ":
            "Aufr\u00e4um-Fehler: ",
        "Check recipes":
            "Rezepte pr\u00fcfen",
        "No recipes in the local database \u2013 run \u201eLoad recipes\u201c first.":
            "Keine Rezepte in der lokalen Datenbank \u2013 erst \u201eBaurezepte laden\u201c ausf\u00fchren.",
        "Check failed: ":
            "Pr\u00fcfung fehlgeschlagen: ",
        "Checking recipes \u2026":
            "Rezepte pr\u00fcfen \u2026",
        "No calculated plan with build positions open \u2013 run \u201eRecalculate\u201c first (older saved plans do not know the exact ingredient quantities yet).":
            "Kein berechneter Plan mit Bau-Positionen offen \u2013 erst \u201eNeu berechnen\u201c (\u00e4ltere gespeicherte Pl\u00e4ne kennen die exakten Zutatenmengen noch nicht).",
        "Everything is covered \u2713\n\nHangar + pipeline + your remaining runs cover the remaining need of every ingredient.\n(Calculated against the REAL current stock, not the frozen state.)":
            "Alles deckt sich \u2713\n\nLager + Pipeline + die restlichen eigenen Runs decken den Restbedarf jeder Zutat.\n(Gerechnet gegen den ECHTEN Ist-Bestand, nicht den Einfrier-Stand.)",
        "Working through the remaining runs, THIS WILL BE MISSING:":
            "Beim Abarbeiten der restlichen Runs WIRD FEHLEN:",
        "Delete old transactions":
            "Alte Transaktionen l\u00f6schen",
        "All transactions before {date} are permanently deleted.\n\nCareful: very old purchases are the cost basis (FIFO) for long-held items \u2013 their profit calculation may be incomplete afterwards. Continue?":
            "Alle Transaktionen vor {date} werden endg\u00fcltig gel\u00f6scht.\n\nAchtung: Sehr alte K\u00e4ufe sind die Kostenbasis (FIFO) f\u00fcr lange gehaltene Items \u2013 deren Gewinnberechnung kann danach unvollst\u00e4ndig sein. Fortfahren?",
        "{n} old transactions deleted.":
            "{n} alte Transaktionen gel\u00f6scht.",
        "Delete error: ":
            "L\u00f6sch-Fehler: ",
        "Reading skills & standings of {n} characters \u2026":
            "Lese Skills & Standings von {n} Charakteren \u2026",
        "Off":
            "Aus",
        "On (player structures)":
            "An (Spielerstrukturen)",
        "On (detect manufacturing-time implants)":
            "An (Fertigungszeit-Implantate erkennen)",
        "Enter this callback URL in the ESI app:  ":
            "Diese Callback-URL bei der ESI-App eintragen:  ",
        "Inventory enabled. Important: add scope esi-assets.read_assets.v1 in the app AND re-link the character for it to take effect.":
            "Inventar aktiviert. Wichtig: Scope esi-assets.read_assets.v1 in der App erg\u00e4nzen UND Charakter neu verkn\u00fcpfen, damit es wirkt.",
        "Implant detection enabled. Important: add scope esi-clones.read_implants.v1 in the app AND re-link the character for it to take effect.":
            "Implantat-Erkennung aktiviert. Wichtig: Scope esi-clones.read_implants.v1 in der App erg\u00e4nzen UND Charakter neu verkn\u00fcpfen, damit es wirkt.",
        "Settings saved.":
            "Einstellungen gespeichert.",
        "Jita scan still fresh ({age}) \u2013 cache used.":
            "Jita-Scan noch frisch ({age}) \u2013 Cache genutzt.",
        "No characters linked.":
            "Keine Charaktere verkn\u00fcpft.",
        "Client ID missing \u2013 see settings.":
            "Client-ID fehlt \u2013 bitte Einstellungen.",
        "Importing transactions + prices \u2026":
            "Importiere Transaktionen + Preise \u2026",
        "Inventory scope missing \u2013 using transactions. Add the scope in the app + re-link the character.":
            "Inventar-Scope fehlt \u2013 nutze Transaktionen. Scope in der App erg\u00e4nzen + Charakter neu verkn\u00fcpfen.",
        "\u26a0 No market snapshot \u2013 portfolio without prices. Please run \u201eMarket scan\u201c once.":
            "\u26a0 Kein Markt-Snapshot vorhanden \u2013 Portfolio ohne Preise. Bitte einmal \u201eMarkt scannen\u201c ausf\u00fchren.",
        "\u2139 Portfolio prices from the market snapshot of {h} h ago \u2013 rescan for current margins.":
            "\u2139 Portfolio-Preise aus dem Markt-Snapshot von vor {h} h \u2013 f\u00fcr aktuelle Margen neu scannen.",
        "\u26a0 Portfolio/sell list compare against \u201e{scan}\u201c (last scan) \u2013 \u201e{cur}\u201c is selected above. Run a market scan to compare against {short}.":
            "\u26a0 Portfolio/Verkaufsliste vergleichen gegen \u201e{scan}\u201c (letzter Scan) \u2013 oben ist \u201e{cur}\u201c gew\u00e4hlt. Markt-Scan ausf\u00fchren, um gegen {short} zu vergleichen.",
        "Loading \u2026":
            "L\u00e4dt \u2026",
        "in build \u00b7 {n} of {ges} position(s) running":
            "im Bau \u00b7 {n} von {ges} Position(en) laufen",
        "Calculate a build plan first ( Build plan)":
            "Erst einen Bauplan berechnen ( Bauplan)",
        "Calculate a build plan first ( Build plan).":
            "Erst einen Bauplan berechnen ( Bauplan).",
        "Quantity (units)":
            "Menge (St\u00fcck)",
        "{n} units (= {r} run{s})":
            "{n} St\u00fcck (= {r} Run{s})",
        "Profit: ":
            "Gewinn: ",
        "\u2696\ufe0f Cost vs. revenue per unit \u2013 your build cost against your fixed sale price":
            "\u2696\ufe0f Kosten vs. Erl\u00f6s pro St\u00fcck \u2013 deine Baukosten gegen deinen festen Verkaufspreis",
        "ISK / unit":
            "ISK / St\u00fcck",
        "Cost/unit: ":
            "Kosten/Stk: ",
        "Revenue/unit: ":
            "Erl\u00f6s/Stk: ",
        "\u267b\ufe0f Reaction surplus % \u2013 how much material is left over from the reaction batches (less is better)":
            "\u267b\ufe0f Reaktions-Verschnitt % \u2013 wie viel Material bei den Reaktions-Chargen \u00fcbrig bleibt (weniger ist besser)",
        "Reaction surplus (%)":
            "Reaktions-\u00dcberschuss (%)",
        "Surplus: ":
            "\u00dcberschuss: ",
        "profit holds":
            "Gewinn tr\u00e4gt",
        "capital efficiency optimal":
            "Kapital-Effizienz optimal",
        "batches divide up well":
            "Chargen gehen gut auf",
        "still fully sellable at the market":
            "noch voll am Markt absetzbar",
        "RECOMMENDATION: build {qty} \xb7 profit {profit} \xb7 {cost}/unit (balanced score {score}/100)":
            "EMPFEHLUNG: {qty} bauen \u00b7 Gewinn {profit} \u00b7 {cost}/Stk (ausgewogener Score {score}/100)",
        "cargo hold fits ~{n} units per trip":
            "Frachtraum reicht f\u00fcr ~{n} St\u00fcck pro Fahrt",
        "profit keeps growing to the end of the calculated range ({qty}, ~{per}/unit) \u2013 no profit maximum within":
            "Gewinn w\u00e4chst bis ans Ende des gerechneten Bereichs ({qty}, ~{per}/Stk) \u2013 kein Gewinn-Maximum darin",
        "\u26a0 material bottlenecks from {qty}":
            "\u26a0 Material-Engp\u00e4sse ab {qty}",
        "\u26a0 does not fit in one trip":
            "\u26a0 passt nicht in eine Fahrt",
        "Revenue/unit (fixed)":
            "Erl\u00f6s/Stk (fest)",
        "Prices are frozen \u2013 unfreeze first ( button at the top)":
            "Preise sind eingefroren \u2013 erst auftauen (-Knopf oben)",
        "Flat estimate: ":
            "Flach gesch\u00e4tzt: ",
        "Order-book exact: ":
            "Orderbuch-genau: ",
        "Total markup: {pct} % ({isk})":
            "Gesamt-Aufschlag: {pct} % ({isk})",
        "Available":
            "Verf\u00fcgbar",
        "Used":
            "Genutzt",
        "Cost of this order":
            "Kosten dieser Order",
        "Total used: {isk} for {n} units \u2192 \u00d8 {avg}/unit":
            "Summe genutzt: {isk} f\u00fcr {n} St\u00fcck \u2192 \u00d8 {avg}/Stk",
        "\u26a0 order book not deep enough: {n} units missing (estimated conservatively at the most expensive price in the tool).":
            "\u26a0 Orderbuch reicht nicht: {n} St\u00fcck fehlen (im Tool konservativ zum teuersten Preis gesch\u00e4tzt).",
        "\u2705 Reactions only (from preset)":
            "\u2705 Nur Reaktionen (aus Preset)",
        "\u2705 Rigs only (from preset)":
            "\u2705 Nur Rigs (aus Preset)",
        "Run \u201eFind blueprints\u201c first.":
            "Erst \u201eBlaupausen suchen\u201c ausf\u00fchren.",
        "(just now)":
            "(gerade eben)",
        "({n} min ago)":
            "(vor {n} min)",
        "({n} h ago)":
            "(vor {n} h)",
        "({n} d ago)":
            "(vor {n} d)",
        "Stock (ESI): no fetch yet in this installation":
            "Bestand (ESI): noch kein Abruf in dieser Installation",
        "Stock (ESI): last checked {checked} \u00b7 changes are recorded from now on":
            "Bestand (ESI): zuletzt gepr\u00fcft {checked} \u00b7 \u00c4nderungen werden ab jetzt aufgezeichnet",
        "Stock (ESI): last checked {checked}":
            "Bestand (ESI): zuletzt gepr\u00fcft {checked}",
        "Stock (ESI): last detected change {changed} \u00b7 last checked {checked}":
            "Bestand (ESI): letzte festgestellte \u00c4nderung {changed} \u00b7 zuletzt gepr\u00fcft {checked}",
        "no sell offer at the hub":
            "kein Verkaufsangebot am Hub",
        "{p} cannot be undercut":
            "{p} nicht unterbietbar",
        "\u23f3 loading \u2026":
            "\u23f3 l\u00e4dt \u2026",
        "Subtract assets needed":
            "Assets abziehen n\u00f6tig",
        "can be built \u2713 \u00b7 {n} units":
            "kann gebaut werden \u2713 \u00b7 {n} Stk",
        "All ingredients for the planned runs are in stock NOW \u2013 the build job can be started right away (see run planner). Nothing to buy.":
            "Alle Zutaten f\u00fcr die geplanten Runs liegen JETZT im Bestand \u2013 der Bau-Job kann sofort gestartet werden (siehe Runplaner). Nichts zu kaufen.",
        "Stock covers part of it, the rest is BUILT per plan (see run planner) \u2013 nothing to buy here.":
            "Bestand deckt einen Teil, der Rest wird laut Plan SELBST gebaut (siehe Runplaner) \u2013 hier ist nichts zu kaufen.",
        "will be built \u00b7 {n} units":
            "wird gebaut \u00b7 {n} Stk",
        "Built entirely per plan (see run planner) \u2013 nothing to buy, no stock needed.":
            "Wird laut Plan komplett SELBST gebaut (siehe Runplaner) \u2013 nichts zu kaufen, kein Bestand n\u00f6tig.",
        "on blacklist \u2013 never built":
            "auf Blacklist \u2013 wird nie gebaut",
        "{n} units from running/finished jobs (pipeline) - they ALWAYS count, whichever source wins (job output is in no hangar).":
            "{n} Stk aus laufenden/fertigen Jobs (Pipeline) - die z\u00e4hlen IMMER dazu, egal welche Quelle gewinnt (Job-Output steht in keinem Hangar).",
        "Frozen state, merged with the live stock (max per item).":
            "Einfrier-Stand, gemischt mit dem Live-Bestand (max je Item).",
        "Hangar stock per ESI in the chosen scope.":
            "Lagerbestand laut ESI im gew\u00e4hlten Scope.",
        "\nCurrently NOT used \u2013 the pasted stock is newer.":
            "\nGerade NICHT benutzt \u2013 die Einf\u00fcgung ist neuer.",
        "\nThis source counts right now.":
            "\nDiese Quelle z\u00e4hlt gerade.",
        "Pasted quantity (panel on the right).":
            "Eingef\u00fcgte Menge (Panel rechts).",
        "Nothing was pasted for this item.":
            "F\u00fcr dieses Item wurde nichts eingef\u00fcgt.",
        "\nSuperseded \u2013 the ESI data is fresher. Can be forced with \u201ePermanent\u201c.":
            "\nAbgel\u00f6st \u2013 die ESI-Daten sind frischer. Mit \u201eDauerhaft g\u00fcltig\u201c erzwingbar.",
        "pasted":
            "eingef\u00fcgt",
        "frozen+live":
            "eingefroren+live",
        "The plan calculates with this.\nSource: ":
            "Damit rechnet der Plan.\nQuelle: ",
        "{a} of {b} materials of this category are fully covered.":
            "{a} von {b} Materialien dieser Kategorie sind vollst\u00e4ndig gedeckt.",
        "If you buy via a buy order you save compared to the sell price \u2013 but you have to wait until someone sells to you.":
            "Kaufst du \xfcber eine Buy-Order, sparst du gegen\xfcber dem Sell-Preis \u2013 aber du musst warten, bis jemand an dich verkauft.",
        "Price wars: EVE only allows prices with 4 significant digits now, the 0.01-ISK undercut is history. The minimum tick grows with the price (around 1 M ISK it is steps of 1'000). Every reprice also costs a relist fee \u2013 constant chasing eats your margin.":
            "Preisk\xe4mpfe: EVE erlaubt nur noch Preise mit 4 signifikanten Stellen, das 0,01-ISK-Unterbieten ist Geschichte. Der Mindest-Tick w\xe4chst mit dem Preis (bei ~1 Mio ISK sind es 1'000er-Schritte). Jede Neupreisung kostet zudem eine Relist-Geb\xfchr \u2013 st\xe4ndiges Nachziehen frisst deine Marge.",
        "You pay the broker fee when placing the order, the sales tax when selling. Both rise/fall with your skills and your standing.":
            "Broker Fee zahlst du beim Platzieren der Order, Sales Tax beim Verkauf. Beide steigen/sinken mit deinen Skills und deinem Standing.",
        "The Accounting skill lowers the sales tax, Broker Relations the broker fee \u2013 for frequent traders these skills pay off quickly.":
            "Accounting-Skill senkt die Sales Tax, Broker Relations die Broker Fee \u2013 f\xfcr Vielh\xe4ndler zahlen sich diese Skills schnell aus.",
        "Volume beats margin: 100 trades at 5 % profit often bring more than one trade at 50 % that sits forever.":
            "Volumen schl\xe4gt Marge: 100 Trades mit 5 % Gewinn bringen oft mehr als ein Trade mit 50 %, der ewig liegen bleibt.",
        "Watch the daily volume. A huge spread is worthless if the item only trades twice a week.":
            "Achte auf das Tagesvolumen. Ein riesiger Spread n\xfctzt nichts, wenn das Item nur zweimal pro Woche gehandelt wird.",
        "Jita is the cheapest market \u2013 but also the most contested. In outlying regions the margins are bigger, the volume smaller.":
            "Jita ist der g\xfcnstigste Markt \u2013 aber auch der umk\xe4mpfteste. In Randregionen sind die Margen gr\xf6\xdfer, das Volumen aber kleiner.",
        "Region trading: buy cheap in one hub, sell dear in another. Don't forget freight cost and risk.":
            "Region-Trading: Kaufe billig in einem Hub, verkaufe teuer in einem anderen. Frachtkosten und Risiko nicht vergessen.",
        "A single 1-ISK order can inflate a margin artificially \u2013 always check the depth of the order book, not just the best price.":
            "Ein einzelner 1-ISK-Auftrag kann eine Marge k\xfcnstlich aufbl\xe4hen \u2013 pr\xfcfe immer die Tiefe des Orderbooks, nicht nur den besten Preis.",
        "PLEX, skill injectors and ships swing heavily with patches and events. Reading the news pays off for traders.":
            "PLEX, Skill-Injektoren und Schiffe schwanken stark mit Patches und Events. News lesen lohnt sich f\xfcr Trader.",
        "Buy when others sell in panic (e.g. after a nerf), and sell into the euphoria after a buff.":
            "Kaufe, wenn andere in Panik verkaufen (z. B. nach einem Nerf), und verkaufe in die Euphorie nach einem Buff.",
        "Spread your ISK across several items. A single market can collapse overnight after a patch.":
            "Verteile dein ISK auf mehrere Items. Ein einziger Markt kann durch einen Patch \xfcber Nacht einbrechen.",
        "Buy orders tie up ISK: when placing a buy order the full amount is reserved in escrow immediately (100 % since the Margin Trading skill was removed). Plan your capital so you can cover all open orders.":
            "Buy-Orders binden ISK: Beim Stellen einer Kauf-Order wird der volle Betrag sofort im Escrow reserviert (seit der Abschaffung des Margin-Trading-Skills zu 100 %). Plane dein Kapital so, dass du alle offenen Orders decken kannst.",
        "Items with high value per m\xb3 (e.g. modules) are more efficient to transport in region trading than bulky ships.":
            "Items mit hohem Volumen pro m\xb3 (z. B. Module) sind beim Region-Trading effizienter zu transportieren als sperrige Schiffe.",
        "The median price over 30\u201390 days is a better 'normal value' than the current price \u2013 that is what swing trading is about.":
            "Der Median-Preis \xfcber 30\u201390 Tage ist ein besserer 'Normalwert' als der aktuelle Preis \u2013 darum dreht sich Swing-Trading.",
        "Patience is a trading skill: the best order is sometimes the one you don't place.":
            "Geduld ist eine Trading-F\xe4higkeit: Die beste Order ist manchmal die, die du nicht stellst.",
        "Motor Market: the first \u201eCalculate deals\u201c per hub loads the market history fresh \u2013 that takes a few minutes once. Afterwards it is cached for 24 h and every further run is quick.":
            "Motor Market: Der erste \u201eDeals berechnen\u201c je Hub l\xe4dt die Markthistorie frisch \u2013 das dauert einmalig ein paar Minuten. Danach ist sie 24 h zwischengespeichert und jeder weitere Lauf l\xe4uft flott.",
        "Motor Market: in the Daytrade and Swing tab choose the hub at the top (Jita, Amarr, Dodixie, Rens, Hek). After switching, run \u201eMarket scan\u201c once, then calculate.":
            "Motor Market: Im Daytrade- und Swing-Tab oben den Hub w\xe4hlen (Jita, Amarr, Dodixie, Rens, Hek). Beim Wechsel einmal \u201eMarkt-Scan\u201c, dann rechnen.",
        "Motor Market: Daytrade looks for quick buy\u2192sell flips, Swing bets on mean reversion (buy below the normal level, hold, sell higher).":
            "Motor Market: Daytrade sucht schnelle Buy\u2192Sell-Flips, Swing setzt auf Mean-Reversion (kaufen unter Normalniveau, halten, h\xf6her verkaufen).",
        "Motor Market: the column headers can be dragged to reorder and resized \u2013 arrange every table the way you need it.":
            "Motor Market: Die Spaltenk\xf6pfe lassen sich per Drag verschieben und in der Breite ziehen \u2013 ordne dir jede Tabelle so an, wie du sie brauchst.",
        "Motor Market: a click on a deal row shows the real order ladder (sell orders) below \u2013 so you see how much is really worthwhile at the target price before a ghost order fools you.":
            "Motor Market: Ein Klick auf eine Deal-Zeile zeigt unten die echte Order-Leiter (Sell-Orders) \u2013 so siehst du, wie viel sich zum Zielpreis wirklich lohnt, bevor ein Geister-Auftrag dich t\xe4uscht.",
        "Motor Market: \u201eMin \xd8 daily volume\u201c is your most important filter against shelf warmers \u2013 a huge spread is worthless if the item barely trades.":
            "Motor Market: \u201eMin \xd8-Tagesvolumen\u201c ist dein wichtigster Filter gegen Ladenh\xfcter \u2013 ein riesiger Spread n\xfctzt nichts, wenn das Item kaum gehandelt wird.",
        "Motor Market: in Regional Trading, \u201e\xd8 daily vol destination\u201c shows whether an item sells at the destination at all. Red = hardly anyone buys, better keep away.":
            "Motor Market: Im Regional-Trading zeigt \u201e\xd8 Tagesvol Ziel\u201c, ob ein Item am Zielort \xfcberhaupt verkauft wird. Rot = kauft kaum jemand, lieber Finger weg.",
        "Motor Market: add your own stations or citadels for regional trading via \u201e\uff0b Structure\u201c \u2013 park a character with market access there and link it.":
            "Motor Market: Eigene Stationen oder Citadels f\xfcrs Regional-Trading \xfcber \u201e\uff0b Struktur\u201c hinzuf\xfcgen \u2013 Charakter mit Marktzugang davor abstellen und verkn\xfcpfen.",
        "Motor Market: right-click on a row opens the item in the in-game market (market window must be open in game) or puts it on the shopping list.":
            "Motor Market: Rechtsklick auf eine Zeile \xf6ffnet das Item im Spiel-Markt (Marktfenster muss im Spiel offen sein) oder setzt es auf die Einkaufsliste.",
        "Motor Market: the portfolio calculates with a FIFO cost basis from your real transactions \u2013 so the profit signals match your actual purchase prices.":
            "Motor Market: Das Portfolio rechnet mit FIFO-Kostenbasis aus deinen echten Transaktionen \u2013 die Gewinn-Signale stimmen also mit deinen tats\xe4chlichen Einkaufspreisen \xfcberein.",
        "Motor Market: \u201eProfit/m\xb3\u201c matters more than plain margin in regional trading \u2013 your cargo hold is limited, not your ISK.":
            "Motor Market: \u201eProfit/m\xb3\u201c ist beim Regional-Trading wichtiger als die reine Marge \u2013 dein Frachtraum ist begrenzt, nicht dein ISK.",
        "Motor Market: the recipes (\u201eBelow build cost\u201c) need the SDE database once (~140 MB). Load it once, afterwards it is stored locally.":
            "Motor Market: Die Baurezepte (\u201eUnter Baukosten\u201c) brauchen einmalig die SDE-Datenbank (~140 MB). Einmal laden gen\xfcgt, danach ist sie lokal gespeichert.",
        "Scam warning: inflated buy orders. A bid far above market price lures you into selling \u2013 but the placer cancels the order as soon as you react, or it is long gone. If a buy price looks too good: check order depth and don't rely on a single dream price.":
            "Scam-Warnung: \xdcberh\xf6hte Buy-Orders. Ein Kaufgebot weit \xfcber Marktpreis lockt dich zum Verkauf \u2013 doch der Steller cancelt die Order, sobald du reagierst, oder sie ist l\xe4ngst weg. Wenn ein Kaufpreis zu sch\xf6n wirkt: Order-Tiefe pr\xfcfen und nicht auf einen einzelnen Traum-Preis verlassen.",
        "Scam warning: contract item swap. Scammers offer an expensive item but swap it for an almost identically named cheap one (e.g. blueprint instead of ship). ALWAYS check the exact item name in the contract.":
            "Scam-Warnung: Contract-Item-Swap. Betr\xfcger bieten ein teures Item an, tauschen es aber gegen ein fast gleichnamiges Billig-Item (z. B. Blaupause statt Schiff). IMMER den exakten Item-Namen im Vertrag pr\xfcfen.",
        "Scam warning: the comma trick. A contract shows \u201e10.000.000\u201c but costs \u201e100.000.000\u201c \u2013 one digit shifted. Read the price twice before accepting.":
            "Scam-Warnung: Der Komma-Trick. Ein Vertrag zeigt \u201e10.000.000\u201c, kostet aber \u201e100.000.000\u201c \u2013 ein Zeichen verschoben. Vor dem Akzeptieren den Preis zweimal lesen.",
        "Scam warning: bot price wars. In heavily contested items bots follow your price within seconds. Competing with them rarely pays \u2013 switch to niches, quieter items or other hubs.":
            "Scam-Warnung: Bot-Preisk\xe4mpfe. In stark umk\xe4mpften Items ziehen Bots ihren Preis in Sekunden nach. Gegen sie anzutreten lohnt selten \u2013 weiche auf Nischen, ruhigere Items oder andere Hubs aus.",
        "Scam warning: \u201eDouble your ISK\u201c in Jita local. Nobody doubles your money for free. It is ALWAYS a scam \u2013 ignore.":
            "Scam-Warnung: \u201eDopple deine ISK\u201c im Jita-Local. Niemand verdoppelt dein Geld geschenkt. Es ist IMMER ein Scam \u2013 ignorieren.",
        "Scam warning: sell order in the wrong place. A great price is worthless if the item sits in a hard-to-reach station or a lowsec citadel. Check the location before buying.":
            "Scam-Warnung: Sell-Order am falschen Ort. Ein super Preis n\xfctzt nichts, wenn das Item in einer schwer erreichbaren Station oder Lowsec-Citadel liegt. Standort pr\xfcfen, bevor du kaufst.",
        "Scam warning: courier contracts with absurd collateral. Hauling jobs that lure you into gate camps so you lose the cargo (and the collateral). Check route and security.":
            "Scam-Warnung: Courier-Contracts mit absurder Collateral. Hauling-Auftr\xe4ge, die dich in Gatecamps locken, damit du die Fracht (und Collateral) verlierst. Route und Sicherheit pr\xfcfen.",
        "Scam warning: artificially pumped buy orders. Someone pushes the buy price so your tool reports a \u201ebargain\u201c \u2013 and cancels as soon as you buy. Look at the order depth (ladder), not just the top price.":
            "Scam-Warnung: K\xfcnstlich hochgekaufte Buy-Orders. Jemand pumpt den Buy-Preis, damit dein Tool ein \u201eSchn\xe4ppchen\u201c meldet \u2013 und cancelt, sobald du kaufst. Order-Tiefe (Leiste) ansehen, nicht nur den Top-Preis.",
        "Fun fact: EVE Online employed real economists and publishes monthly economic reports (MER) \u2013 with money supply, inflation and trade balance like a real economy.":
            "Fun Fact: EVE Online besch\xe4ftigte echte Volkswirte und ver\xf6ffentlicht monatliche Wirtschaftsberichte (MER) \u2013 mit Geldmenge, Inflation und Handelsbilanz wie bei einer echten Volkswirtschaft.",
        "Fun fact: Jita 4-4 (Caldari Navy Assembly Plant) is by far the busiest trading place in the whole EVE universe.":
            "Fun Fact: Jita 4-4 (Caldari Navy Assembly Plant) ist der mit Abstand gesch\xe4ftigste Handelsplatz im ganzen Universum von EVE.",
        "Fun fact: Tritanium is the most traded mineral in EVE \u2013 the bread-and-butter material almost everything is built from.":
            "Fun Fact: Tritanium ist das meistgehandelte Mineral in EVE \u2013 das Brot-und-Butter-Material, aus dem fast alles gebaut wird.",
        "Fun fact: some of the biggest \u201eheists\u201c in EVE history moved values worth tens of thousands of real euros \u2013 completely legal in game.":
            "Fun Fact: Manche der gr\xf6\xdften \u201eHeists\u201c der EVE-Geschichte bewegten Werte im Gegenwert von zehntausenden echten Euro \u2013 komplett legal im Spiel.",
        "Fun fact: PLEX used to be a physical item you could lose in transport. Today it sits in a secure vault.":
            "Fun Fact: PLEX war fr\xfcher ein physisches Item, das man beim Transport verlieren konnte. Heute liegt es in einem sicheren Tresor.",
        "Fun fact: \u201eBurn Jita\u201c \u2013 player events in which attackers deliberately shut down the biggest trade hub. Even the market is not safe.":
            "Fun Fact: \u201eBurn Jita\u201c \u2013 Spieler-Events, bei denen Angreifer den gr\xf6\xdften Handelsknotenpunkt absichtlich lahmlegten. Selbst der Markt ist nicht sicher.",
        "Fun fact: through PLEX, EVE practically has an exchange rate between game time and ISK \u2013 the economy is closely tied to the real world.":
            "Fun Fact: \xdcber PLEX hat EVE praktisch einen Wechselkurs zwischen Spielzeit und ISK \u2013 die \xd6konomie ist eng mit der realen Welt verzahnt.",
        "Spread = sell price minus buy price. That is your gross profit cushion per unit before tax and broker fee come off.":
            "Spread = Sell-Preis minus Buy-Preis. Das ist dein Brutto-Gewinnpolster pro St\xfcck, bevor Steuer und Broker-Fee abgehen.",
        "Don't underestimate relist costs: every adjustment of an order costs the broker fee again. Repricing too often eats the profit.":
            "Relist-Kosten nicht untersch\xe4tzen: Jedes Anpassen einer Order kostet erneut Broker Fee. Zu h\xe4ufiges Umpreisen frisst den Gewinn.",
        "Diversify across item types AND hubs. A patch can overturn a whole market \u2013 several legs cushion that.":
            "Diversifiziere \xfcber Item-Typen UND Hubs. Ein Patch kann einen ganzen Markt umwerfen \u2013 mehrere Standbeine federn das ab.",
        "Days of stock: how long the current supply lasts at normal turnover. Low = scarcity = often rising prices.":
            "Bestandstage: Wie lange das aktuelle Angebot bei normalem Umsatz reicht. Niedrig = Knappheit = oft steigende Preise.",
        "Skill injectors and PLEX are highly liquid but low-margin and heavily contested \u2013 good for volume, bad for relaxed profits.":
            "Skill-Injektoren und PLEX sind hochliquide, aber margenschwach und stark umk\xe4mpft \u2013 gut f\xfcr Volumen, schlecht f\xfcr entspannte Gewinne.",
        "Note your real purchase prices (Motor Market does this automatically via FIFO). Without a cost basis you never know whether a sale is really a profit.":
            "Notiere dir deine echten Kaufpreise (das macht Motor Market via FIFO automatisch). Ohne Kostenbasis wei\xdft du nie, ob ein Verkauf wirklich Gewinn ist.",
        "Whoever trades in EVE instead of fighting plays the hardest PvP of the game: against other traders, bots and the psychology of the market.":
            "Wer in EVE handelt statt k\xe4mpft, spielt das h\xe4rteste PvP des Spiels: gegen andere Trader, Bots und die Psychologie des Marktes.",
        "Motor Market: the column \u201eTradability\u201c shows how reliably an item trades daily on BOTH sides. 60+ means: your buy order fills AND you get rid of it via your sell order \u2013 ideal for hourly trading.":
            "Motor Market: Die Spalte \u201eHandelbar.\u201c zeigt, wie zuverl\xe4ssig ein Item t\xe4glich an BEIDEN Seiten gehandelt wird. 60+ hei\xdft: deine Buy-Order f\xfcllt sich UND du wirst es \xfcber deine Sell-Order wieder los \u2013 ideal f\xfcrs Stunden-Trading.",
        "Motor Market: the \u201e\u2728 Gold search\u201c button in Daytrade shows the best flip chances of the hub \u2013 and which flip strategy (spread, hours, competition, niche, capital) each item is particularly suited for.":
            "Motor Market: Der Button \u201e\u2728 Gold-Suche\u201c im Daytrade zeigt die besten Flip-Chancen des Hubs \u2013 und f\xfcr welche Flip-Strategie (Spanne, Stunden, Konkurrenz, Nische, Kapital) jedes Item besonders taugt.",
        "Motor Market: choose the mode first, then the preset \u2013 that is the core. Every mode has its own sensible presets. The fine filters below are just the finishing touch.":
            "Motor Market: Erst Modus w\xe4hlen, dann Preset \u2013 das ist der Kern. Jeder Modus hat eigene, sinnvolle Presets. Die Feinfilter darunter sind nur die K\xfcr.",
        "Motor Market: the \u201e\u2605 Top 15\u201c button highlights the 15 strongest hits of your preset in gold \u2013 for a quick look at the essentials.":
            "Motor Market: Der \u201e\u2605 Top 15\u201c-Knopf hebt die 15 st\xe4rksten Treffer deines Presets golden hervor \u2013 f\xfcr den schnellen Blick aufs Wesentliche.",
        "Motor Market: in the portfolio the status \u201ein market\u201c recognises that you have already listed an item \u2013 you are only waiting for the buyer, nothing to do.":
            "Motor Market: Im Portfolio erkennt der Status \u201eim Markt\u201c, dass du ein Item bereits gelistet hast \u2013 du wartest nur noch auf den K\xe4ufer, nichts zu tun.",
        "Motor Market: in the shopping list an item is locked after adding, so you don't accidentally buy twice and run into expensive sell orders.":
            "Motor Market: In der Einkaufsliste ist ein Item nach dem Hinzuf\xfcgen gesperrt, damit du nicht aus Versehen doppelt kaufst und in teure Sell-Orders l\xe4ufst.",
        "Motor Market: in the price history the dots show whether trading on a day happened at the top (at sell orders) or at the bottom (at buy orders). Both colours = the item runs on both sides = perfect for trading.":
            "Motor Market: Im Kursverlauf zeigen die Punkte, ob an einem Tag oben (an Sell-Orders) oder unten (an Buy-Orders) gehandelt wurde. Beide Farben = das Item l\xe4uft an beiden Seiten = perfekt zum Traden.",
        "Motor Market: up to 305 market orders are possible with all trading skills \u2013 the slots are your real bottleneck. The trade plan helps to fill them wisely.":
            "Motor Market: Bis zu 305 Market-Orders sind mit allen Handels-Skills m\xf6glich \u2013 die Slots sind dein echter Engpass. Der Handelsplan hilft, sie klug zu f\xfcllen.",
        "Tip: the \u201eSwing Trade\u201c tab finds items below their 90-day average that return to the normal level \u2013 patient, high-margin trading.":
            "Tipp: Der Reiter \u201eSwing Trade\u201c findet Items unter ihrem 90-Tage-Schnitt, die aufs Normalniveau zur\xfcckkehren \u2013 geduldiges, margenstarkes Trading.",
        "Tip: the \u201eBuild\u201c tab shows which items are worth producing \u2013 sale price minus estimated build cost. A whole separate profit channel next to trading.":
            "Tipp: Der Reiter \u201eBauen\u201c zeigt, welche Items sich zu produzieren lohnen \u2013 Verkaufspreis minus gesch\xe4tzte Baukosten. Ein ganz eigener Gewinnkanal neben dem Handel.",
        "Tip: \u201eRegional Trading\u201c finds price differences between Jita, Amarr, Dodixie, Rens and Hek \u2013 buy cheap, sell dear, earn on the transport.":
            "Tipp: \u201eRegional Trading\u201c findet Preisunterschiede zwischen Jita, Amarr, Dodixie, Rens und Hek \u2013 kaufe billig, verkaufe teuer, verdiene am Transport.",
        "Motor Market is free. If it helps you, the developer is happy about an in-game donation \u2013 \u201e\u2665 Donate\u201c at the bottom left.":
            "Motor Market ist kostenlos. Wenn es dir hilft, freut sich der Entwickler \xfcber eine Spende ingame \u2013 \u201e\u2665 Spenden\u201c unten links.",
        "Tip: every tab targets a different type of trader \u2013 Daytrade for the active, Swing for the patient, Build for producers, Regional for logisticians. Try them all.":
            "Tipp: Jeder Reiter zielt auf einen anderen Trader-Typ \u2013 Daytrade f\xfcr Aktive, Swing f\xfcr Geduldige, Bauen f\xfcr Produzenten, Regional f\xfcr Logistiker. Probier ruhig alle aus.",
        "Tip: combine the tabs: find an undervalued item in Regional Trading, check its normal value in Swing and plan the orders in Daytrade \u2013 together they give the full picture.":
            "Tipp: Kombiniere die Reiter: Finde im Regional-Trading ein unterbewertetes Item, pr\xfcfe im Swing seinen Normalwert und plane im Daytrade die Orders \u2013 zusammen ergeben sie das volle Bild.",
        "not two-sided":
            "nicht beidseitig",
        "exit too thin":
            "Exit zu d\u00fcnn",
        "history too short":
            "Historie zu kurz",
        "not deep enough":
            "nicht tief genug",
        "implausibly deep":
            "unglaubw\u00fcrdig tief",
        "still falling":
            "noch fallend",
        "contradictory (deep + rising)":
            "widerspr\u00fcchlich (tief + steigend)",
        "no profit after fees":
            "kein Gewinn nach Geb\u00fchren",
        "expected profit % too small":
            "Gewinnerwartung % zu klein",
        "ISK profit too small":
            "ISK-Gewinn zu klein",
        "floor = best-case producer (ME 10 \u00b7 T2 rigs \u00b7 nullsec \u00b7 own reactions) \u2013 not your own build cost":
            "Boden = Best-Case-Produzent (ME 10 \u00b7 T2-Rigs \u00b7 Nullsec \u00b7 Reaktionen selbst) \u2013 nicht deine eigenen Baukosten",
        "\u26a0 ESI limit reached \u2013 missing histories are loaded in the background, run \u201eLoad deals\u201c again shortly":
            "\u26a0 ESI-Limit erreicht \u2013 fehlende Historien werden im Hintergrund nachgeladen, gleich erneut \u201eDeals laden\u201c",
        "reloading paused: the cache pool exceeds the analysis cap ({cap}) \u2013 new fetches would add no candidates. Preset switches now run purely from the cache":
            "Nachladen pausiert: Cache-Topf liegt \u00fcber dem Analyse-Deckel ({cap}) \u2013 neue Abrufe br\u00e4chten keine zus\u00e4tzlichen Kandidaten. Preset-Wechsel laufen jetzt rein aus dem Cache",
        "newly loaded histories come free with the next scan":
            "neu geladene Historien sind ab dem n\u00e4chsten Scan gratis dabei",
        "below price-from":
            "unter Preis-ab",
        "above price-to":
            "\u00fcber Preis-bis",
        "no profit (spread + fees)":
            "kein Gewinn (Spread + Geb\u00fchren)",
        "freight eats the profit":
            "Fracht frisst den Gewinn",
        "profit/m\u00b3 too small":
            "Gewinn/m\u00b3 zu klein",
        "destination demand (order book) too thin":
            "Ziel-Nachfrage (Orderbuch) zu d\u00fcnn",
        "destination sales (history) too small":
            "Ziel-Absatz (Historie) zu klein",
        "\u2193 falling":
            "\u2193 f\u00e4llt",
        "\u2192 sideways":
            "\u2192 seitw.",
        "\u2191 rising":
            "\u2191 steigt",
        "Carrier/Dreadnought/FAX/Titan/Supercarrier/Freighter - trading runs via contracts instead of market orders, hence separate from the normal profit table above. Does NOT run automatically with the normal search - only when expanded or in Capital mode.":
            "Carrier/Dreadnought/FAX/Titan/Supercarrier/Freighter - Handel l\u00e4uft \u00fcber Contracts statt Marktorders, daher separat von der normalen Gewinn-Tabelle oben. L\u00e4uft NICHT automatisch mit der normalen Suche mit - erst beim Aufklappen oder im Capital-Modus.",
        "Copy first for building (1 blueprint = 1 simultaneous job, the original covers one of them): ":
            "Vorher kopieren f\u00fcrs Bauen (1 Blaupause = 1 gleichzeitiger Job, das Original deckt einen davon): ",
        "With \u201eOwn BPC instead of invention\u201c the invention is skipped - the decryptor no longer matters.":
            "Bei \u201eEigene BPC statt Invention\u201c wird die Erfindung \u00fcbersprungen - der Decryptor spielt dann keine Rolle mehr.",
        "Your simultaneously usable science slots (in game at the bottom left of the industry window, e.g. \u201eScience jobs 4/10\u201c). Limits how many copies can really work in parallel.":
            "Deine gleichzeitig nutzbaren Wissenschafts-Slots (Ingame unten links im Industry-Fenster, z.B. \u201eScience jobs 4/10\u201c). Begrenzt, wie viele Kopien wirklich parallel arbeiten k\u00f6nnen.",
        " ({have} already in the hangar \u2192 {buy} more to buy)":
            " ({have} schon im Hangar \u2192 noch {buy} kaufen)",
        "Owned ( frozen+live)":
            "Besitze ( eingefroren+live)",
        "Owned (ESI)":
            "Besitze (ESI)",
        "FROZEN plan: this shows max(frozen state, live stock) \u2013 NOT the raw ESI value.\nThe frozen state records what you had bought on the freeze day; anything built since is credited live.\nCan therefore be higher than your real hangar. Reset: Tools \u2192 \u201eReset frozen stock\u201c.":
            "EINGEFRORENER Plan: hier steht max(Einfrier-Stand, Live-Bestand) \u2013 NICHT der rohe ESI-Wert.\nDer Einfrier-Stand h\u00e4lt fest, was du am Einfrier-Tag gekauft hattest; seither Gebautes wird live gutgeschrieben.\nKann also h\u00f6her sein als dein echter Hangar. Zur\u00fccksetzen: Werkzeuge \u2192 \u201eEinfrier-Bestand neu setzen\u201c.",
        "Hangar stock per ESI \u2013 only the locations/characters of the chosen stock scope.\nWhat ESI does not see, you can paste on the right.":
            "Lagerbestand laut ESI \u2013 nur die Orte/Charaktere des gew\u00e4hlten Bestands-Scopes.\nWas ESI nicht sieht, kannst du rechts einf\u00fcgen.",
        "On the blacklist (\u201ealready have it\u201c, recipe structure tab) - therefore NEVER built, not even with \u201eBuild everything yourself: ON\u201c. Untick it there to make it buildable again.":
            "Auf der Blacklist (\u201ehab ich schon\u201c, Rezept-Struktur-Tab) - wird deshalb NIE gebaut, auch nicht mit \u201eAlles selbst bauen: AN\u201c. Dort abhaken, um es wieder bau-f\u00e4hig zu machen.",
        "Blueprint category in \u201eMy blueprints\u201c (recipe structure tab) not marked as owned - the tool assumes you do not have the blueprint/reaction formula and therefore buys, even with \u201eBuild everything yourself: ON\u201c (cannot build what you do not own). If you really have it: tick the matching category there.":
            "Blaupausen-Kategorie in \u201eMeine Blueprints\u201c (Rezept-Struktur-Tab) nicht als besessen markiert - das Tool geht davon aus, du hast die Blaupause/Reaktionsformel nicht, und kauft deshalb, auch mit \u201eAlles selbst bauen: AN\u201c (kann ja nicht bauen, was du nicht besitzt). Falls du sie wirklich hast: die passende Kategorie dort anhaken.",
        "No recipe of its own in the SDE (real raw material/commodity) - cannot be built, MUST be bought.":
            "Kein eigenes Rezept in der SDE (echter Rohstoff/Commodity) - kann nicht gebaut werden, MUSS gekauft werden.",
        "\n\u26d4 AND there is no sell order for it at the chosen hub. The price above is an estimate (ESI average), not an offer - you will not be able to buy it there.":
            "\n\u26d4 UND am gew\u00e4hlten Hub gibt es keine Sell-Order daf\u00fcr. Der Preis oben ist eine Sch\u00e4tzung (ESI-Durchschnitt), kein Angebot - du wirst es dort nicht kaufen k\u00f6nnen.",
        "There is NO sell order for this item at the chosen hub. The plan therefore builds it itself instead of planning a purchase you could not make.\nThe price in the cost is an estimate (ESI average), not an offer. As soon as someone sells at the hub again, the normal cost comparison decides.":
            "Am gew\u00e4hlten Hub gibt es KEINE Sell-Order f\u00fcr dieses Item. Der Plan baut es deshalb selbst, statt einen Kauf einzuplanen, den du nicht t\u00e4tigen k\u00f6nntest.\nDer Preis in den Kosten ist eine Sch\u00e4tzung (ESI-Durchschnitt), kein Angebot. Sobald wieder jemand am Hub verkauft, entscheidet der normale Kostenvergleich.",
        "enough \u2713 \u00b7 {n} of them in build":
            "genug \u2713 \u00b7 {n} davon in Bau",
        "Covered \u2013 but {n} units are still in running/finished jobs (pipeline) and only land in the hangar after delivery. For the SHOPPING LIST that rightly counts (nothing to rebuy!); for the JOB START it has to be delivered first and possibly moved to the build structure.":
            "Gedeckt \u2013 aber {n} Stk stecken noch in laufenden/fertigen Jobs (Pipeline) und liegen erst nach der Ablieferung im Hangar. F\u00fcr die EINKAUFSLISTE z\u00e4hlt das zu Recht mit (nichts nachkaufen!); zum JOB-START muss es erst abgeliefert und ggf. in die Bau-Struktur gebracht werden.",
        "What still has to be procured after deducting your stock (buy or build).\n":
            "Was nach Abzug deines Bestands noch beschafft werden muss (kaufen oder bauen).\n",
        "Required ":
            "Ben\u00f6tigt ",
        "Copying \u2248{d}":
            "Kopieren \u2248{d}",
        "Invention \u2248{d}":
            "Invention \u2248{d}",
        "plus ":
            "zzgl. ",
        " (rough, sequential \u2013 runs parallel to the build)":
            " (grob, sequenziell \u2013 l\u00e4uft parallel zum Bau)",
        "Total (rough): {tot}   \u00b7   Reactions {react} \u2192 Components {comp} \u2192 End product {end}":
            "Gesamt (grob): {tot}   \u00b7   Reaktionen {react} \u2192 Komponenten {comp} \u2192 Endprodukt {end}",
        "\u26a0 Science skill data missing \u2013 press \u201eLoad recipes\u201c once (reload SDE), otherwise the manufacturing times are too long.":
            "\u26a0 Science-Skill-Daten fehlen \u2013 einmal \u201eBaurezepte laden\u201c dr\u00fccken (SDE neu laden), sonst sind die Fertigungszeiten zu lang.",
        "\u26a0 Reaction skill not loaded \u2013 press \u201eLoad skills \u2192 Job slots\u201c, otherwise the reaction times are too long.":
            "\u26a0 Reaktions-Skill nicht geladen \u2013 \u201eSkills laden \u2192 Job-Slots\u201c dr\u00fccken, sonst sind die Reaktionszeiten zu lang.",
        "Other":
            "Sonstige",
        "T1 hull":
            "T1-H\u00fclle",
        "Ticked by hand. ESI: ":
            "Von Hand abgehakt. ESI: ",
        "{n} runs delivered.":
            "{n} Runs geliefert.",
        "no delivered jobs seen for it yet (may lag behind).":
            "dazu noch keine gelieferten Jobs gesehen (kann nachlaufen).",
        "BUY \u2013 market cheaper than building (is on the shopping list)":
            "KAUF \u2013 Markt billiger als Bauen (steht auf der Einkaufsliste)",
        "covered by PASTED stock ( Materials tab) \u2013 nothing to do":
            "durch EINGEF\u00dcGTEN Bestand gedeckt ( Materialien-Tab) \u2013 nichts zu tun",
        "covered by the pipeline (running/finished jobs) \u2013 nothing to do":
            "durch die Pipeline gedeckt (laufende/fertige Jobs) \u2013 nichts zu tun",
        "covered by ESI stock \u2013 nothing to do":
            "durch ESI-Bestand gedeckt \u2013 nichts zu tun",
        "Freight service":
            "Frachtdienst",
        "Job cost":
            "Job-Kosten",
        "Invention (\u00d8)":
            "Invention (\u00d8)",
        "Stock (replacement cost)":
            "Bestand (Ersatzkosten)",
        "= Total build cost":
            "= Baukosten gesamt",
        "\u00f7 units":
            "\u00f7 St\u00fcck",
        "Shopping list (Jita sell)":
            "Einkaufsliste (Jita Sell)",
        "Shopping list / unit":
            "Einkaufsliste / St\u00fcck",
        "Sale price / unit":
            "Verkaufspreis / Stk",
        "Gross sale proceeds":
            "Verkaufserl\u00f6s brutto",
        "\u2212 Tax + broker":
            "\u2212 Steuer + Broker",
        "\u2212 Build cost":
            "\u2212 Baukosten",
        "\u2212 Own trip":
            "\u2212 Eigene Fahrt",
        "\u2212 Extra cost":
            "\u2212 Zusatzkosten",
        "= Profit":
            "= Gewinn",
        "Profit / unit":
            "Gewinn / Stk",
        "Break-even / unit":
            "Verlustschwelle / Stk",
        "Statistical EXPECTED VALUE of the invention (required successes \u00f7 success chance) \u2013 only that belongs in the margin, otherwise every product would be priced too high.\nThe Invention tab, by contrast, shows the PURCHASE QUANTITY: the attempts for \u226575 % certainty. That number is higher \u2013 the difference is your safety buffer of datacores.":
            "Statistischer ERWARTUNGSWERT der Invention (ben\u00f6tigte Erfolge \u00f7 Erfolgschance) \u2013 nur er geh\u00f6rt in die Marge, sonst w\u00e4re jedes Produkt zu teuer gerechnet.\nDer Invention-Tab zeigt dagegen die KAUFMENGE: die Versuche f\u00fcr \u226575 % Sicherheit. Diese Zahl ist h\u00f6her \u2013 die Differenz ist dein Sicherheitspuffer an Datacores.",
        "Frozen stock set to NOW \u2013 {n} position(s) changed. Don't forget \u201eSave build plan\u201c!":
            "Einfrier-Bestand auf JETZT gesetzt \u2013 {n} Position(en) ge\u00e4ndert. \u201eBauplan speichern\u201c nicht vergessen!",
        "Not possible while the prices are frozen \u2013 the tool fetches LIVE order-book prices and would replace the pinned purchase prices. Unfreeze first ( button at the top).":
            "Nicht m\u00f6glich, solange die Preise eingefroren sind \u2013 das Werkzeug holt LIVE-Orderbuchpreise und w\u00fcrde die festgenagelten Einkaufspreise ersetzen. Erst auftauen (-Knopf oben).",
        "T1 ship hulls that serve as the invention base for T2 ships.":
            "T1-Schiffsh\u00fcllen, die als Invention-Basis f\u00fcr T2-Schiffe dienen.",
        "Fuel block blueprints for reaction/structure operation.":
            "Fuel-Block-Blaupausen f\u00fcr Reaktions-/Struktur-Betrieb.",
        "Build aids such as R.A.M. (Robotics/Starship Tech).":
            "Bau-Hilfsmittel wie R.A.M. (Robotics/Starship Tech).",
        "Components/T1 hulls/Fuel Blocks/Tools \u2013 usually fully researched T1 BPOs, unlike the end product above.\nDEFAULT is ME 10 % / TE 20 % (fully researched BPO). What you change here applies to THIS build plan and is saved with \u201eSave build plan\u201c - it is back on the next opening. A NEW build plan always starts at 10/20.\nChanges are applied automatically after a short pause.":
            "Komponenten/T1-H\u00fcllen/Fuel Blocks/Tools \u2013 i. d. R. voll ausgeforschte T1-BPOs, anders als das Endprodukt oben.\nSTANDARD ist ME 10 % / TE 20 % (voll erforschtes BPO). Was du hier \u00e4nderst, gilt f\u00fcr DIESEN Bauplan und wird mit \u201eBauplan speichern\u201c mitgesichert - beim n\u00e4chsten \u00d6ffnen steht es wieder so da. Ein NEUER Bauplan startet immer bei 10/20.\n\u00c4nderungen werden nach einer kurzen Pause automatisch \u00fcbernommen.",
        "Copies \u00d7 runs per stage (end product/components/reactions) \u2013 for this build plan only, remembered with \u201eSave build plan\u201c.":
            "Kopien \u00d7 Runs je Stufe (Endprodukt/Komponenten/Reaktionen) \u2013 nur f\u00fcr diesen Bauplan, wird mit \u201eBauplan speichern\u201c gemerkt.",
        "Build or buy?":
            "Bauen oder kaufen?",
        "Production depth":
            "Fertigungstiefe",
        "From which stage of the chain do you build yourself? Sets the category ticks below \u2013 a shortcut, not a second setting.":
            "Ab welcher Stufe der Kette baust du selbst? Setzt die Kategorie-Haken darunter \u2013 eine Abk\u00fcrzung, keine zweite Einstellung.",
        "Stage":
            "Stufe",
        "Total runs":
            "Runs gesamt",
        "Max runs/job":
            "Max Runs/Job",
        "Rec. copies":
            "Empf. Kopien",
        "Owned (BPO/BPC)":
            "Besitze (BPO/BPC)",
        "All blueprints this plan needs at the configured production depth.":
            "Alle Blaupausen, die dieser Plan bei der eingestellten Fertigungstiefe braucht.",
        "Reaction stage or component/end product.":
            "Reaktionsstufe bzw. Komponente/Endprodukt.",
        "Total runs for the current build plan quantity.":
            "Runs insgesamt f\u00fcr die aktuelle Bauplan-Menge.",
        "How many runs a single job can hold at most.":
            "Wie viele Runs ein einzelner Job maximal fassen kann.",
        "Minimum number of waves with a fully researched BPO and unlimited runs, capped at your free job slots.":
            "Minimale Wellenzahl bei voll erforschter BPO und unbegrenzten Runs, gedeckelt auf deine freien Job-Slots.",
        "Live per ESI: own BPOs (unlimited) and BPCs (limited runs, checked against the need).":
            "Live per ESI: eigene BPOs (unbegrenzt) und BPCs (begrenzte Runs, gegen den Bedarf gepr\u00fcft).",
        "Is what you own enough for this plan?":
            "Reicht dein Besitz f\u00fcr diesen Plan?",
        "Select the hangar in game \u2192 Ctrl+C \u2192 paste here \u2192 Apply.\nExpected is ONE item per line: name, then quantity.":
            "Hangar ingame markieren \u2192 Strg+C \u2192 hier einf\u00fcgen \u2192 \u00dcbernehmen.\nErwartet wird EIN Item pro Zeile: Name, dann Menge.",
        "{ok} recognised, {bad} unknown \u2013 applied as pasted stock":
            "{ok} erkannt, {bad} unbekannt \u2013 als eingef\u00fcgter Bestand \u00fcbernommen",
        "Pasted stock cleared \u2013 the ESI stock counts again":
            "Eingef\u00fcgter Bestand geleert \u2013 es z\u00e4hlt wieder der ESI-Bestand",
        "\u26d4 {n} material(s) without ANY price \u2013 neither order book nor flat price nor average. These costs are MISSING from the total, so the build cost is too low.":
            "\u26d4 {n} Material(ien) ohne JEDEN Preis \u2013 weder Orderbuch noch Flachpreis noch Durchschnitt. Diese Kosten FEHLEN in der Summe, die Baukosten sind also zu niedrig.",
        "Structure for the invention and the character whose skills go into the success chance.":
            "Struktur f\u00fcr die Invention und der Charakter, dessen Skills in die Erfolgschance eingehen.",
        "Total cost of this build plan:":
            "Gesamtkosten dieses Bauplans:",
        "Material to BUY: ":
            "Material zu KAUFEN: ",
        "Material from STOCK: ":
            "Material aus BESTAND: ",
        "Job cost: ":
            "Jobkosten: ",
        "Invention: ":
            "Invention: ",
        "The stock deliberately counts - it once cost you ISK. Valued at REPLACEMENT COST: what it costs you to put the unit back, via the cheaper of the two ways (buy OR build yourself).":
            "Der Bestand z\u00e4hlt bewusst MIT - er hat dich einmal ISK gekostet. Bewertet zu ERSATZKOSTEN: was es dich kostet, die Einheit wieder hinzustellen, auf dem g\u00fcnstigeren der beiden Wege (kaufen ODER selbst bauen).",
        "You only have to spend fresh: ":
            "Frisch ausgeben musst du nur: ",
        "Order-book exact: real sell-order prices of the build materials at the chosen hub, not the flat price.":
            "Orderbuch-genau: echte Sell-Order-Preise der Baumaterialien am gew\u00e4hlten Hub, nicht der Flachpreis.",
        "Undercut market: ":
            "Markt unterbieten: ",
        "no market price":
            "kein Marktpreis",
        "Target price per unit for your sell order.":
            "Zielpreis je St\u00fcck f\u00fcr deine Sell-Order.",
        "Minimum price (0 profit): ":
            "Mindestpreis (0 Gewinn): ",
        "build cost ":
            "Baukosten ",
        "transport ":
            "Transport ",
        "{n} units":
            "{n} St\u00fcck",
        "{pct} % fees":
            "{pct} % Geb\u00fchren",
        "Market (cheapest sell order): ":
            "Markt (billigste Sell-Order): ",
        "Undercut: ":
            "Unterbietung: ",
        "\u2192 You can undercut and earn ":
            "\u2192 Du kannst unterbieten und verdienst dabei ",
        " in total.":
            " gesamt.",
        "\u2192 Undercutting would only work at a LOSS. The target price stays the minimum price \u2013 so you are above the market and do not sell for now.":
            "\u2192 Unterbieten ginge nur mit VERLUST. Der Zielpreis bleibt der Mindestpreis \u2013 damit liegst du \u00fcber dem Markt und verkaufst vorerst nicht.",
        "No market price available \u2013 only the minimum price is known.":
            "Kein Marktpreis vorhanden \u2013 es steht nur der Mindestpreis fest.",
        "Plan frozen: build cost AND market price come from the freeze day \u2013 so this target price no longer changes, even if you only get to Jita in two weeks. The MARKET there may have moved since; the minimum price still applies.":
            "Plan eingefroren: Baukosten UND Marktpreis stammen vom Einfrier-Tag \u2013 dieser Zielpreis \u00e4ndert sich also nicht mehr, auch wenn du erst in zwei Wochen nach Jita kommst. Der MARKT dort kann sich inzwischen bewegt haben; der Mindestpreis gilt aber weiter.",
        "Volume of the PLAN shopping list (what still has to be procured), not of the shopping cart.":
            "Volumen der PLAN-Einkaufsliste (was noch beschafft werden muss), nicht des Einkaufswagens.",
        "Material you own but do NOT have at the build location counts here \u2013 you still have to bring it there.":
            "Material, das du zwar besitzt, aber NICHT am Bau-Ort liegen hast, z\u00e4hlt hier mit \u2013 du musst es ja trotzdem hinbringen.",
        "Largest items:":
            "Gr\u00f6\u00dfte Posten:",
        "Loading blueprints from ESI \u2026":
            "Blaupausen werden aus ESI geladen \u2026",
        "Freight cost":
            "Frachtkosten",
        "Cargo hold, freight service (ISK/m\u00b3), flat rate per own trip and whether freight goes into the buy-or-build decision. Set once, then leave collapsed.":
            "Frachtraum, Frachtdienst (ISK/m\u00b3), Pauschale je eigener Fahrt und ob die Fracht in die Kauf-oder-Bau-Entscheidung einf\u00e4llt. Einmal einstellen, dann zugeklappt lassen.",
        "Extra cost":
            "Zusatzkosten",
        "One-off amount for this build plan that is deducted from the profit \u2013 e.g. bought BPCs.":
            "Einmaliger Betrag f\u00fcr diesen Bauplan, der vom Gewinn abgezogen wird \u2013 z.B. gekaufte BPCs.",
        "\u26a0 no timestamp (plan from before this feature) \u2013 counts as \u201ePermanent\u201c until you paste anew":
            "\u26a0 ohne Zeitstempel (Plan von vor diesem Feature) \u2013 gilt wie \u201eDauerhaft\u201c, bis du neu einf\u00fcgst",
        "only pasted stock active":
            "nur eingef\u00fcgte Best\u00e4nde aktiv",
        "superseded: ESI data is fresher \u2013 ESI counts again":
            "abgel\u00f6st: ESI-Daten sind frischer \u2013 ESI z\u00e4hlt wieder",
        "ISK/m\u00b3 x volume of the shopping list. Included in the material price (because \u201eFreight in decision\u201c is on) - the material row above shows the amount WITHOUT this markup, together both give the full material cost. Is NOT deducted from the profit again.":
            "ISK/m\u00b3 x Volumen der Einkaufsliste. Steckt im Materialpreis (weil \u201eFracht mitentscheiden\u201c an ist) - die Material-Zeile dar\u00fcber zeigt den Betrag OHNE diesen Aufschlag, zusammen ergeben beide die vollen Materialkosten. Wird NICHT zus\u00e4tzlich vom Gewinn abgezogen.",
        "No ISK/m\u00b3 rate set or \u201eFreight in decision\u201c is off.":
            "Kein ISK/m\u00b3-Satz gesetzt oder \u201eFracht mitentscheiden\u201c ist aus.",
        "{n} material(s) without volume data in the SDE \u2013 calculated with 0 m\u00b3 there":
            "{n} Material(ien) ohne Volumen-Daten in der SDE \u2013 dort mit 0 m\u00b3 gerechnet",
        "ESI loading \u2026":
            "ESI l\u00e4dt \u2026",
        "Reserve material?":
            "Material reservieren?",
        "\u26a0 {n} material(s) not available at the hub in the full required depth \u2013 rest estimated conservatively at the most expensive known price.":
            "\u26a0 {n} Material(ien) am Hub nicht in voller ben\u00f6tigter Tiefe verf\u00fcgbar \u2013 Rest konservativ zum teuersten bekannten Preis gesch\u00e4tzt.",
        "\u26a0 {n} material(s) only on the shopping list at this quantity \u2013 no order book for them, calculated at the flat price.":
            "\u26a0 {n} Material(ien) erst bei dieser Menge in der Einkaufsliste \u2013 daf\u00fcr liegt kein Orderbuch vor, gerechnet zum Flachpreis.",
        "\u26a0 {n} material(s) are currently NOWHERE in the order book \u2013 valued at the CCP average price (server-wide average, not a hub price). You will probably not find them when buying in Jita.":
            "\u26a0 {n} Material(ien) liegen gerade NIRGENDS im Orderbuch \u2013 bewertet mit dem CCP-Durchschnittspreis (serverweiter Schnitt, kein Hub-Preis). Beim Einkauf in Jita wirst du sie voraussichtlich nicht finden.",
        "Sale price ({src})":
            "Verkaufspreis ({src})",
        " / unit":
            " / Stk",
        "Break-even":
            "Verlustschwelle",
        "To undercut":
            "Zum Unterbieten",
        "\u2212 Tax + broker ({pct}%)":
            "\u2212 Steuer + Broker ({pct}%)",
        "\u2212 Freight service + own trip":
            "\u2212 Frachtdienst + Eigene Fahrt",
        "per unit":
            "je St\u00fcck",
        "Both come off in the profit tooltip, not here: they belong to the plan, not to the single unit. Each row has its own input field above: \u201eFreight service\u201c (ISK/m\u00b3 \u00d7 volume), \u201eOwn trip\u201c (flat rate \u00d7 trips) and \u201eExtra cost\u201c (everything else one-off, e.g. bought BPCs).":
            "Beide gehen im Gewinn-Tooltip ab, nicht hier: sie h\u00e4ngen am Plan, nicht am einzelnen St\u00fcck. Jede Zeile hat ihr eigenes Eingabefeld oben: \u201eFrachtdienst\u201c (ISK/m\u00b3 \u00d7 Volumen), \u201eEigene Fahrt\u201c (Pauschale \u00d7 Fahrten) und \u201eZusatzkosten\u201c (alles andere Einmalige, z.B. gekaufte BPCs).",
        "The freight service is shown SEPARATELY above but counts towards the material cost (\u201eFreight in decision\u201c is on, so it takes part in the buy-or-build decision for every material). It is therefore inside the unit cost and is NOT deducted again below \u2013 the transport row only contains the flat rate per own trip.":
            "Der Frachtdienst ist oben EINZELN ausgewiesen, z\u00e4hlt aber zu den Materialkosten (\u201eFracht mitentscheiden\u201c ist an, deshalb entscheidet er bei jedem Material Kauf-oder-Bau mit). Er steckt damit in den St\u00fcckkosten und wird unten NICHT noch einmal abgezogen \u2013 die Transportzeile enth\u00e4lt nur die Pauschale je eigener Fahrt.",
        "\u26a0 Does NOT fit in one trip \u2013 {n} trips needed!":
            "\u26a0 Passt NICHT in eine Fahrt \u2013 {n} Fahrten n\u00f6tig!",
        "\u26a0 {n} ship(s) without packaged volume in the SDE \u2013 AS-FIT size used (far too large)!":
            "\u26a0 {n} Schiff/e ohne gepacktes Volumen in der SDE \u2013 AS-FIT-Gr\u00f6\u00dfe verwendet (deutlich zu gro\u00df)!",
        "\u26a0 None of your build structures is linked to a REAL EVE structure":
            "\u26a0 Keine deiner Bau-Strukturen ist mit einer ECHTEN EVE-Struktur verkn\u00fcpft",
        " \u2013 in the \u201eBuild structures only\u201c scope, therefore NO hangar stock is counted at all (only running/finished jobs).\n   Fix: Structures tab \u2192 Edit \u2192 field \u201e Real EVE structure\u201c. Immediate workaround: scope to \u201e Everywhere\u201c.":
            " \u2013 im Scope \u201eNur Bau-Strukturen\u201c wird deshalb GAR KEIN Lagerbestand gez\u00e4hlt (nur laufende/fertige Jobs).\n Abhilfe: Strukturen-Tab \u2192 Bearbeiten \u2192 Feld \u201e Echte EVE-Struktur\u201c. Sofort-Workaround: Scope auf \u201e \u00dcberall\u201c.",
        "Stock pool: {n} characters (all with role ticks)":
            "Bestand-Pool: {n} Charaktere (alle mit Rollen-H\u00e4kchen)",
        "Base frozen \xb7 intermediates BUILT since are credited live":
            "Basis eingefroren \u00b7 seither GEBAUTE Zwischenprodukte werden live gutgeschrieben",
        "ME comes from the decryptor chosen in the Invention tab (2% base + bonus) - not editable here, as an invented BPC never has a freely researched ME.":
            "ME kommt vom im Invention-Tab gew\u00e4hlten Decryptor (2% Basis + Bonus) - hier nicht editierbar, da eine invented BPC nie eine frei recherchierte ME hat.",
        "TE comes from the decryptor chosen in the Invention tab (4% base + bonus) - now also acts directly on the planned build time.":
            "TE kommt vom im Invention-Tab gew\u00e4hlten Decryptor (4% Basis + Bonus) - wirkt jetzt auch direkt auf die geplante Bauzeit.",
        "\u23f3 A job for this item is running per ESI right now.\nThis is your end product \u2013 the plan stays valid. Just check whether you really want to build MORE.":
            "\u23f3 Von diesem Item l\u00e4uft laut ESI gerade ein Job.\nDas hier ist dein Endprodukt \u2013 der Plan bleibt g\u00fcltig. Pr\u00fcfe nur, ob du wirklich ZUS\u00c4TZLICH bauen willst.",
        "\u23f3 Running per ESI right now (live jobs) \u2013 do not plan it extra.":
            "\u23f3 L\u00e4uft gerade laut ESI (Live-Jobs) \u2013 nicht extra einplanen.",
        "after \u2212{fees} fees":
            "nach \u2212{fees} Geb\u00fchren",
        "ONLY pasted stock: {n} item(s) \u2013 ESI hangar stock is OFF for this plan (job pipeline still counts)":
            "NUR eingef\u00fcgte Best\u00e4nde: {n} Item(s) \u2013 ESI-Lagerbestand ist f\u00fcr diesen Plan AUS (Job-Pipeline z\u00e4hlt weiter)",
        "{n} item(s) from PASTED stock (":
            "{n} Item(s) aus EINGEF\u00dcGTEM Bestand (",
        ", permanent":
            ", dauerhaft",
        ", newer than ESI":
            ", neuer als ESI",
        "{n} pasted item(s) SUPERSEDED \u2013 the ESI data is fresher by now, ESI counts again":
            "{n} eingef\u00fcgte Item(s) ABGEL\u00d6ST \u2013 die ESI-Daten sind inzwischen frischer, ESI z\u00e4hlt wieder",
        "Stock only from: ":
            "Bestand nur von: ",
        "\u26a0 NOT a single asset was found at the linked structures \u2013 but the characters have {n} asset rows at OTHER locations.\n   Typical causes: material sits in the CORP hangar (the character-assets endpoint does not return it \u2013 workaround: paste stock, \u201epermanent\u201c), it sits with a character WITHOUT a role tick, or the link points to a different structure_id. Details in fehler.log.":
            "\u26a0 An den verkn\u00fcpften Strukturen wurde KEIN einziges Asset gefunden \u2013 die Charaktere haben aber {n} Asset-Zeilen an ANDEREN Orten.\n   Typische Ursachen: Material liegt im CORP-Hangar (liefert der Charakter-Assets-Endpunkt nicht \u2013 Workaround: Bestand einf\u00fcgen, \u201edauerhaft\u201c), es liegt bei einem Charakter OHNE Rollen-H\u00e4kchen, oder die Verkn\u00fcpfung zeigt auf eine andere structure_id. Details in fehler.log.",
        "Reserved by: ":
            "Reserviert durch: ",
        " \u2013 {types} material types / {units} units deducted":
            " \u2013 {types} Material-Typen / {units} Stk abgezogen",
        " \u00b7 {n} units of the claim not on site yet (in transit?) \u2013 apply automatically on delivery":
            " \u00b7 {n} Stk des Anspruchs noch nicht vor Ort (unterwegs?) \u2013 greifen bei Anlieferung automatisch",
        "Assets subtracted (build structure not linked \u2013 only build/reaction characters counted) \u2013 {n} material(s) \u2713":
            "Assets abgezogen (Bau-Struktur nicht verkn\u00fcpft \u2013 nur Bau-/Reaktions-Charaktere gez\u00e4hlt) \u2013 {n} Material(ien) \u2713",
        "\u26a0 No hangar stock counted \u2013 no build structure linked (scope: build structures only)":
            "\u26a0 Kein Lager-Bestand gez\u00e4hlt \u2013 keine Bau-Struktur verkn\u00fcpft (Scope: Nur Bau-Strukturen)",
        "Assets subtracted ( ALL locations, per scope) \u2013 {n} material(s) \u2713":
            "Assets abgezogen ( ALLE Orte, per Scope gew\u00e4hlt) \u2013 {n} Material(ien) \u2713",
        "Loading assets \u2026":
            "Assets laden \u2026",
        "\u21a9 Removed from the blacklist: ":
            "\u21a9 Von der Blacklist genommen: ",
        "Other reactions":
            "Sonstige Reaktionen",
        "Tools (R.A.M. etc.)":
            "Tools (R.A.M. u. \u00c4.)",
        "SDE group 'Intermediate Materials'. Examples: Titanium Chromide, Crystallite Alloy, Fernite Alloy, Rolled Tungsten Alloy. Mostly stage-1 reactions (product goes into further reactions).":
            "SDE-Gruppe 'Intermediate Materials'. Beispiele: Titanium Chromide, Crystallite Alloy, Fernite Alloy, Rolled Tungsten Alloy. Meist Stufe-1-Reaktionen (Produkt geht in weitere Reaktionen).",
        "SDE group 'Composite'. Examples: Crystalline Carbonide, Titanium Carbide, Tungsten Carbide, Fernite Carbide, Sylramic Fibers, Fullerides. Mostly stage 2 (goes directly into the build).":
            "SDE-Gruppe 'Composite'. Beispiele: Crystalline Carbonide, Titanium Carbide, Tungsten Carbide, Fernite Carbide, Sylramic Fibers, Fullerides. Meist Stufe-2 (geht direkt in den Bau).",
        "SDE group 'Hybrid Polymers' (for T3). Examples: Fulleroferrocene, PPD Fullerene Fibers, Methanofullerene.":
            "SDE-Gruppe 'Hybrid Polymers' (f\u00fcr T3). Beispiele: Fulleroferrocene, PPD Fullerene Fibers, Methanofullerene.",
        "SDE group 'Biochemical Material' (booster/drug materials). Examples: Pure Standard/Improved Blue Pill Booster, Crash Booster, Frentix Booster.":
            "SDE-Gruppe 'Biochemical Material' (Booster-/Drogen-Materialien). Beispiele: Pure Standard/Improved Blue Pill Booster, Crash Booster, Frentix Booster.",
        "SDE group 'Molecular-Forged Materials'. Examples: Meta-Operant / Hypnagogic / Axosomatic Neurolink Enhancer (neurolink materials for faction/structure stuff).":
            "SDE-Gruppe 'Molecular-Forged Materials'. Beispiele: Meta-Operant / Hypnagogic / Axosomatic Neurolink Enhancer (Neurolink-Materialien f\u00fcr Faction-/Structure-Kram).",
        "SDE group 'Unrefined Mineral'. Examples: Unrefined Tritanium, Unrefined Pyerite, Unrefined Mexallon, Unrefined Isogen (precursors from the mineral reprocessing branch).":
            "SDE-Gruppe 'Unrefined Mineral'. Beispiele: Unrefined Tritanium, Unrefined Pyerite, Unrefined Mexallon, Unrefined Isogen (Vorstufen aus dem Mineral-Reprocessing-Zweig).",
        "Catch-all category: all remaining reactions that fit none of the SDE groups above.":
            "Auffang-Kategorie: alle \u00fcbrigen Reaktionen, die in keine der obigen SDE-Gruppen passen.",
        "T2 build components. Examples: Nanoelectrical Microprocessor, Fusion Thruster, Radar Sensor Cluster. Market: Manufacture & Research \u2192 Components.":
            "T2-Baukomponenten. Beispiele: Nanoelectrical Microprocessor, Fusion Thruster, Radar Sensor Cluster. Markt: Manufacture & Research \u2192 Components.",
        "Capital components. Examples: Capital Armor Plate, Capital Power Core, Capital Construction Parts. Market: Components \u2192 Capital.":
            "Capital-Komponenten. Beispiele: Capital Armor Plate, Capital Power Core, Capital Construction Parts. Markt: Components \u2192 Capital.",
        "T2 capital components. Example: Capital Nanoelectrical Microprocessor.":
            "T2-Capital-Komponenten. Beispiel: Capital Nanoelectrical Microprocessor.",
        "Hybrid Tech Components (T3 subsystem parts).":
            "Hybrid Tech Components (T3-Subsystem-Bauteile).",
        "Tech I ships that serve as the base for T2 (e.g. Amarr Cruiser for a HAC). Market: Ships. Blacklist them if you already have them.":
            "Tech-I-Schiffe, die als Basis f\u00fcr T2 dienen (z. B. Amarr Cruiser f\u00fcr einen HAC). Markt: Ships. Blacklisten, wenn du sie schon hast.",
        "Fuel Blocks (Nitrogen/Hydrogen/Oxygen/Helium). Market: Fuel Blocks. For reaction/structure operation.":
            "Fuel Blocks (Nitrogen/Hydrogen/Oxygen/Helium). Markt: Fuel Blocks. F\u00fcr Reaktions-/Struktur-Betrieb.",
        "Build aids such as R.A.M.- Robotics / Starship Tech. Market: Manufacture & Research \u2192 Tools.":
            "Bau-Hilfsmittel wie R.A.M.- Robotics / Starship Tech. Markt: Manufacture & Research \u2192 Tools.",
        "Catch-all: remaining self-buildable T1 stuff (modules/rigs) you prefer to buy.":
            "Auffang: \u00fcbrige selbst-baubare T1-Sachen (Module/Rigs), die du lieber kaufst.",
        "From which stage do you build yourself?":
            "Ab welcher Stufe baust du selbst?",
        "Component":
            "Komponente",
        "Reaction":
            "Reaktion",
        "Minerals":
            "Mineralien",
        "Moon materials":
            "Mond-Materialien",
        "Raw materials":
            "Rohstoffe",
        "not resolved yet":
            "noch nicht aufgel\u00f6st",
        "For building (manufacturing)":
            "F\u00fcr Bauen (Fertigung)",
        "For reactions":
            "F\u00fcr Reaktionen",
        "For invention":
            "F\u00fcr Invention",
        "For copying":
            "F\u00fcr Kopieren",
        "End product only":
            "Nur das Endprodukt",
        "All components AND reactions are bought. Little effort, smallest margin.":
            "Alle Komponenten UND Reaktionen werden gekauft. Wenig Aufwand, kleinste Marge.",
        "From components":
            "Ab Komponenten",
        "You build components and tools (incl. R.A.M.) yourself, you buy all reactions and fuel blocks.":
            "Komponenten und Tools (inkl. R.A.M.) baust du selbst, alle Reaktionen und Fuel Blocks kaufst du.",
        "From composite reactions":
            "Ab Composite-Reaktionen",
        "Composite reactions and fuel blocks yourself as well. You only buy the intermediate reactions.":
            "Zus\u00e4tzlich Composite-Reaktionen und Fuel Blocks selbst. Nur die Intermediate Reactions kaufst du zu.",
        "From intermediate reactions":
            "Ab Intermediate-Reaktionen",
        "The complete chain from the intermediate reactions to the end product. Largest margin, most work.":
            "Die komplette Kette von den Intermediate Reactions bis zum Endprodukt. Gr\u00f6\u00dfte Marge, meiste Arbeit.",
        "no contract price":
            "kein Contract-Preis",
        "cost uncertain":
            "Kosten unsicher",
        "demand unknown":
            "Absatz unbekannt",
        "thin market":
            "d\u00fcnner Markt",
        "clearly worth it":
            "lohnt sich klar",
        "solid":
            "solide",
        "tight":
            "knapp",
        "Price histories: {i} of {n}":
            "Preisverl\u00e4ufe: {i} von {n}",
        " \u00b7 about {m} min left":
            " \u00b7 noch etwa {m} Min.",
        " \u00b7 almost done":
            " \u00b7 gleich fertig",
        "Undervalued":
            "Unterbewertet",
        "Bargain":
            "Schn\u00e4ppchen",
        "Build":
            "Bauen",
        "{n} hits calculated without invention cost: own BPCs/BPOs on hand.":
            "{n} Treffer ohne Invention-Kosten gerechnet: eigene BPCs/BPOs vorhanden.",
        "nothing pasted yet":
            "noch nichts eingef\u00fcgt",
        "pasted {n} min ago":
            "eingef\u00fcgt vor {n} min",
        "pasted {h} h ago":
            "eingef\u00fcgt vor {h} h",
        "pasted {d} days ago":
            "eingef\u00fcgt vor {d} Tagen",
        "Category: ":
            "Kategorie: ",
        "Quantity held (real inventory, if enabled).":
            "Gehaltene Menge (echtes Inventar, falls aktiviert).",
        "Average purchase price of the units you currently hold (FIFO).":
            "Durchschnittlicher Kaufpreis deiner aktuell gehaltenen St\u00fcck (FIFO).",
        "Date of the oldest purchase still held.":
            "Datum des \u00e4ltesten noch gehaltenen Kaufs.",
        "Current Jita sell price.":
            "Aktueller Jita-Verkaufspreis.",
        "Net proceeds per unit after tax + broker.":
            "Netto-Erl\u00f6s pro St\u00fcck nach Steuer + Broker.",
        "Margin against your purchase price.":
            "Marge gegen\u00fcber deinem Kaufpreis.",
        "Three states: in market (order running) \u00b7 SELL (net margin above your target margin) \u00b7 hold (everything else \u2013 the reason is in the cell's tooltip).":
            "Drei Zust\u00e4nde: im Markt (Order l\u00e4uft) \u00b7 VERKAUFEN (Netto-Marge \u00fcber deiner Ziel-Marge) \u00b7 Halten (alles andere \u2013 der Grund steht im Tooltip der Zelle).",
        "Your open market orders for this item: \u201eBuy\u201c = you have a buy order running, \u201eSell\u201c = a sell order is listed.":
            "Deine offenen Market-Orders f\u00fcr dieses Item: \u201eBuy\u201c = du hast eine Kauf-Order laufen, \u201eSell\u201c = eine Verkaufs-Order ist gelistet.",
        "\u00d8 purchase plus estimated broker fees from adjusting your buy orders (\u201eOrder update\u201c, work-through mode) - separate, estimated extra column, does NOT change the normal \u00d8 purchase. \u201e\u2014\u201c = no adjustments recorded (or \u00d8 purchase unknown).":
            "\u00d8-Kauf plus gesch\u00e4tzte Broker-Geb\u00fchren aus dem Nachbessern deiner Buy-Orders (\u201eOrder-Update\u201c, Abarbeiten-Modus) - separate, gesch\u00e4tzte Zusatzspalte, ver\u00e4ndert NICHT den normalen \u00d8-Kauf. \u201e\u2014\u201c = keine Nachbesserungen erfasst (oder \u00d8-Kauf unbekannt).",
        "Price of your actually open sell order for this item (\u201e Load sell-order prices\u201c above) - green = you sell at a profit above your \xd8 purchase, red = at a loss or at best break-even. \u201e\u2014\u201c = no open sell order detected (or not loaded yet).":
            "Preis deiner tats\u00e4chlich offenen Sell-Order f\u00fcr dieses Item (\u201e Verkaufsorder-Preise laden\u201c oben) - Gr\u00fcn = du verkaufst dabei mit Gewinn \u00fcber deinem \u00d8-Kauf, Rot = mit Verlust oder h\u00f6chstens Kostendeckung. \u201e\u2014\u201c = keine offene Sell-Order erkannt (oder noch nicht geladen).",
        "Highest current buy-order price in Jita.":
            "H\u00f6chster aktueller Kauf-Order-Preis in Jita.",
        "Lowest current sell-order price in Jita.":
            "Niedrigster aktueller Verkaufs-Order-Preis in Jita.",
        "Average price over the time window.":
            "Durchschnittspreis \u00fcber das Zeitfenster.",
        "How far the price is below \u00d8 / below build cost, or the drop.":
            "Wie weit der Preis unter \u00d8 / unter Baukosten liegt bzw. der Drop.",
        "Estimated production cost per unit (relative).":
            "Gesch\u00e4tzte Produktionskosten pro St\u00fcck (relativ).",
        "Profit per unit after fees (flip only).":
            "Gewinn pro St\u00fcck nach Geb\u00fchren (nur Flip).",
        "Return on the ISK invested (flip only).":
            "Rendite auf das eingesetzte ISK (nur Flip).",
        "Average units traded per day.":
            "Durchschnittlich gehandelte St\u00fcck pro Tag.",
        "Price swing (high/low) in the time window.":
            "Preisschwankung (Hoch/Tief) im Zeitfenster.",
        "Days of stock: how long the supply lasts.":
            "Bestandstage: wie lange der Bestand reicht.",
        "Profit per day = profit/unit \u00d7 daily volume.":
            "Gewinn pro Tag = Gewinn/Stk \u00d7 Tagesvolumen.",
        "Price trend: falling / sideways / rising.":
            "Preistrend: f\u00e4llt / seitw\u00e4rts / steigt.",
        "Normal level the item should return to.":
            "Normalniveau, auf das das Item zur\u00fcckkehren d\u00fcrfte.",
        "Expected profit on return to the normal level (after fees).":
            "Erwarteter Gewinn bei R\u00fcckkehr aufs Normalniveau (nach Geb\u00fchren).",
        "Competition: number of competing orders on the busier side. Few = you hold the top order more easily.":
            "Konkurrenz: Anzahl konkurrierender Orders auf der st\u00e4rker besetzten Seite. Wenig = du h\u00e4ltst leichter die Top-Order.",
        "Takeable/day: realistic daily profit = profit/day divided by the competition (you share the flow). The flip mode sorts by this.":
            "Einnehmbar/Tag: realistischer Tagesgewinn = Gewinn/Tag geteilt durch die Konkurrenz (du teilst dir den Fluss). Danach wird im Flip-Modus sortiert.",
        "Tradability (0\u2013100): how reliably the item trades daily on BOTH sides \u2013 your buy order fills AND you get rid of it via your sell order. From active trading days, transactions/day and the daily price range. 60+ = ideal for day/hourly trading, 35+ usable.":
            "Handelbarkeit (0\u2013100): wie zuverl\u00e4ssig das Item t\u00e4glich an BEIDEN Seiten gehandelt wird \u2013 deine Buy-Order f\u00fcllt sich UND du wirst es \u00fcber deine Sell-Order wieder los. Aus aktiven Handelstagen, Transaktionen/Tag und der t\u00e4glichen Preisspanne. 60+ = ideal f\u00fcrs Day-/Stunden-Trading, 35+ brauchbar.",
        "Capital efficiency (% per day): realistic daily profit divided by the tied-up capital. Shows how hard your ISK works \u2013 2 %/day on tied-up capital beats a larger absolute profit that ties up ten times the ISK.":
            "Kapital-Effizienz (% pro Tag): realistischer Tagesgewinn geteilt durch das gebundene Kapital. Zeigt, wie hart dein ISK arbeitet \u2013 2 %/Tag auf gebundenes Kapital schl\u00e4gt einen gr\u00f6\u00dferen absoluten Gewinn, der das Zehnfache an ISK bindet.",
        "Current sell price at the scanned hub \u2013 your purchase price.":
            "Aktueller Sell-Preis am gescannten Hub \u2013 dein Kaufpreis.",
        "Normal level (median) \u2013 target price on return.":
            "Normalniveau (Median) \u2013 Zielpreis bei R\u00fcckkehr.",
        "How far the item is currently below normal.":
            "Wie weit das Item gerade unter Normal liegt.",
        "Price trend: sideways/rising good, falling avoided.":
            "Preistrend: seitw\u00e4rts/steigend gut, fallend gemieden.",
        "Expected profit per unit after fees on return.":
            "Erwarteter Gewinn pro St\u00fcck nach Geb\u00fchren bei R\u00fcckkehr.",
        "Expected profit in % on return to the normal level.":
            "Erwarteter Gewinn in % bei R\u00fcckkehr aufs Normalniveau.",
        "Estimate of how much trading happens at SELL orders (high = your sell order fills well; low = almost everything trades at buy orders, your sell order sits).":
            "Sch\u00e4tzung, wie viel Handel an SELL-Orders l\u00e4uft (hoch = deine Verkaufs-Order f\u00fcllt sich gut; niedrig = es wird fast nur an Buy-Orders gehandelt, deine Sell-Order bleibt liegen).",
        "Profit per unit after fees.":
            "Gewinn pro St\u00fcck nach Geb\u00fchren.",
        "Profit margin in % on the purchase price.":
            "Gewinnspanne in % auf den Kaufpreis.",
        "Profit per m\u00b3 of cargo hold \u2013 important for hauling.":
            "Gewinn pro m\u00b3 Frachtraum \u2013 wichtig f\u00fcrs Transportieren.",
        "Volume per unit in m\u00b3 (packaged).":
            "Volumen pro St\u00fcck in m\u00b3 (verpackt).",
        "Demand at the destination NOW: units on open buy orders (snapshot).":
            "Nachfrage im Ziel JETZT: St\u00fcck auf offenen Buy-Orders (Momentaufnahme).",
        "Supply at the destination: units on sell orders.":
            "Angebot im Ziel: St\u00fcck auf Sell-Orders.",
        "\u00d8 daily volume at the destination (market history): how many units actually trade there per day. \u201e\u2014\u201c = no history (e.g. structure).":
            "\u00d8 Tagesvolumen im Ziel (Markthistorie): wie viele St\u00fcck dort pro Tag tats\u00e4chlich gehandelt werden. \u201e\u2014\u201c = keine Historie (z. B. Struktur).",
        "Best all-round flips: provably BOTH sides served daily, real depth at the best price, short cycles. Competition is not filtered hard - weak deals slide down the ranking.":
            "Beste Allround-Flips: beweisbar t\xe4glich BEIDE Seiten bedient, echte Tiefe am Bestpreis, kurze Zyklen. Konkurrenz wird nicht hart gefiltert - schwache Deals rutschen im Ranking nach unten.",
        "Cheap bulk goods only pay off with VOLUME: \u2265300 units/day, \u226525 at the best price, \u226520 units/day realistic for you.":
            "Billige Massenware lohnt nur mit MASSE: \u2265300 St\xfcck/Tag, \u226525 am Bestpreis, \u226520 St\xfcck/Tag realistisch f\xfcr dich.",
        "Modules/ammo/small ships: solid profit per unit, traded on both sides daily.":
            "Module/Munition/kleine Schiffe: solider St\xfcckgewinn, t\xe4glich beidseitig gehandelt.",
        "Ships & expensive items: few units are enough, but fat profit per flip. Two-sidedness requirement deliberately milder.":
            "Schiffe & Teures: wenig St\xfcck reicht, daf\xfcr dicker Gewinn je Flip. Beidseitigkeits-Anspruch bewusst milder.",
        "For active hub trading: only items that fill both sides almost EVERY day (\u226545 %), max. 5 days of stock, strict spike cap (25 %).":
            "F\xfcr aktives Hub-Trading: nur Items, die fast JEDEN Tag beide Seiten f\xfcllen (\u226545 %), max. 5 Bestandstage, strenger Spike-Deckel (25 %).",
        "Ammo & consumables under continuous fire: \u2265800/day, \u226540 at the best price - here pure frequency counts.":
            "Munition & Verbrauchsg\xfcter im Dauerfeuer: \u2265800/Tag, \u226540 am Bestpreis - hier z\xe4hlt reine Frequenz.",
        "Quick turnover without penny goods: modules/rigs with daily two-sided trading.":
            "Schneller Umschlag ohne Cent-Ware: Module/Rigs mit t\xe4glich beidseitigem Handel.",
        "Max. 8 rivals: your order stays in front for a long time without constant 0.01-ISKing. In return, milder two-sidedness requirement.":
            "Max. 8 Rivalen: deine Order bleibt lange vorn, ohne st\xe4ndiges 0.01-isken. Daf\xfcr milder Beidseitigkeits-Anspruch.",
        "A little more competition allowed, in return \u226510 % margin as a buffer for the rare readjustment.":
            "Etwas mehr Konkurrenz erlaubt, daf\xfcr \u226510 % Marge als Puffer f\xfcrs seltene Nachjustieren.",
        "Patience goods: 1 fill can save the week (\u22651M per unit). Long days of stock are fine here.":
            "Geduldsware: 1 Fill kann die Woche retten (\u22651M je St\xfcck). Lange Bestandstage sind hier ok.",
        "Mid volume off the mass hit lists: enough trading for fills, too inconspicuous for the 0.01-ISKers.":
            "Mittelvolumen abseits der Massen-Hitlisten: gen\xfcgend Handel f\xfcr Fills, zu unauff\xe4llig f\xfcr die 0.01-Isker.",
        "\u226515 % margin with little competition - thin trading, but provably two-sided daily.":
            "\u226515 % Marge bei wenig Konkurrenz - d\xfcnner Handel, aber t\xe4glich beweisbar beidseitig.",
        "Ranks by profit per tied-up ISK: short cycles and two-sided trading so your capital never sits idle.":
            "Rankt nach Gewinn pro gebundenem ISK: kurze Zyklen und beidseitiger Handel, damit dein Kapital nie herumliegt.",
        "From 50M per unit: few trades, \u22652M profit per flip.":
            "Ab 50M je St\xfcck: wenige Trades, \u22652M Gewinn pro Flip.",
        "Liquid items with a small dip (\u22656 %) and quickly MEASURED recovery. A dip below your fees never pays - the diagnostic line counts such items under \u201eno profit after fees\u201c.":
            "Liquide Items mit kleinem Dip (\u22656 %) und schnell GEMESSENER Erholung. Ein Dip unterhalb deiner Geb\xfchren lohnt nie - solche Items z\xe4hlt die Diagnosezeile unter \u201ekein Gewinn nach Geb\xfchren\u201c.",
        "\u226520 % below the yearly baseline: larger cushion, longer holding time. Watch the \u26a0 dump flag - crashes with mass volume are NOT dips.":
            "\u226520 % unter der Jahres-Basislinie: gr\xf6\xdferes Polster, l\xe4ngere Haltezeit. Auf das \u26a0-Dump-Flag achten - St\xfcrze mit Massen-Volumen sind KEINE Dips.",
        "Small discount on very liquid goods: many units, short cycle, small margin x mass.":
            "Kleiner Rabatt auf sehr liquide Ware: viele St\xfcck, kurzer Zyklus, kleine Marge x Masse.",
        "Priority on resale: \u226510 realistically sellable units/day (volume divided by sell competition) - you never sit on the stock for long.":
            "Priorit\xe4t auf dem Wiederverkauf: \u226510 realistisch verkaufbare St\xfcck/Tag (Volumen geteilt durch Sell-Konkurrenz) - du sitzt nie lange auf dem Bestand.",
        "The middle way: decent discount (\u226510 %), solid expectation (\u22658 % after fees), moderate volume. For all hits between \u201esmall dip\u201c and \u201edeep cushion\u201c.":
            "Der Mittelweg: ordentlicher Rabatt (\u226510 %), solide Erwartung (\u22658 % nach Geb\xfchren), moderates Volumen. F\xfcr alle Treffer zwischen \u201ekleiner Dip\u201c und \u201etiefes Polster\u201c.",
        "From 5M per unit, \u2265150k expected profit per unit - few positions, patience needed.":
            "Ab 5M je St\xfcck, \u2265150k erwarteter Gewinn pro Einheit - wenige Positionen, Geduld n\xf6tig.",
        "Open corp window in game":
            "Corp-Fenster ingame \u00f6ffnen",
        "\u00d8 purchase":
            "\u00d8-Kauf",
        "Oldest purchase":
            "\u00c4ltester Kauf",
        "Optimal sale":
            "Optimaler Verkauf",
        "\u00d8 purchase +fees":
            "\u00d8-Kauf +Geb.",
        "Already listed in the market \u2013 your sell order is running, you are waiting for a buyer. Nothing more to do.":
            "Bereits im Markt gelistet \u2013 deine Verkaufs-Order l\u00e4uft, du wartest auf einen K\u00e4ufer. Nichts weiter zu tun.",
        "{hub} was just scanned ({age}s ago) \u2013 using the fresh data ({n} items). Rescan possible in {secs}s.":
            "{hub} wurde gerade gescannt (vor {age}s) \u2013 nutze die frischen Daten ({n} Items). Neu-Scan in {secs}s m\u00f6glich.",
        "Double-click = price history. T1/T2/T3 only \u2013 LP/faction excluded. Build cost is an estimate (without your system/rigs, without LP cost).":
            "Doppelklick = Kursverlauf. Nur T1/T2/T3 \u2013 LP/Faction ausgeschlossen. Baukosten sind eine Sch\u00e4tzung (ohne dein System/Rigs, ohne LP-Kosten).",
        "Already on hand \u2013 what do you have where?":
            "Schon vorhanden \u2013 was hast du wo?",
        "Item / character":
            "Item / Charakter",
        "at build location":
            "am Bau-Ort",
        "To cart":
            "In den Wagen",
        "What you own IN TOTAL \u2013 per portfolio, at ANY location.":
            "Was du INSGESAMT besitzt \u2013 laut Portfolio, an JEDEM Ort.",
        "{n} histories loaded":
            "{n} Verl\u00e4ufe geladen",
        "{n} items without trading":
            "{n} Items ohne Handel",
        "throttled by CCP \u2013 continue later":
            "von CCP gedrosselt \u2013 sp\u00e4ter fortsetzen",
        "  (Build margin & profit = produce and sell; build cost is an estimate without your system/rigs.)":
            "  (Bau-Marge & Profit = produzieren und verkaufen; Baukosten sind eine Sch\u00e4tzung ohne dein System/Rigs.)",
        "  (here you buy to hold \u2013 profit only on recovery.)":
            "  (hier kaufst du zum Halten \u2013 Gewinn erst bei Erholung.)",
        "Build plan not fully calculated yet - click \u201eRecalculate\u201c first.":
            "Bauplan ist noch nicht fertig berechnet - erst einmal \u201eNeu berechnen\u201c klicken.",
        "No characters/client ID linked.":
            "Keine Charaktere/Client-ID verkn\u00fcpft.",
        "{n} error(s) (missing scope? re-link)":
            "{n} Fehler (fehlender Scope? Neu verkn\u00fcpfen)",
        "Implants \u2026":
            "Implantate \u2026",
        "No profile selected":
            "Kein Profil gew\u00e4hlt",
        "Profile \u201e{name}\u201c deleted":
            "Profil \u201e{name}\u201c gel\u00f6scht",
        " (+{s}% surplus)":
            " (+{s}% \u00dcberschuss)",
        " + {n} invention items":
            " + {n} Invention-Posten",
        " ({n} already in the hangar, not bought)":
            " ({n} schon im Hangar, nicht gekauft)",
        "Decryptors":
            "Decryptoren",
        "  \u26a0 {what} NOT bought along - tick at \u201eInclude inventions\u201c missing":
            "  \u26a0 {what} NICHT mitgekauft - H\u00e4kchen bei \u201eInventions miteinbeziehen\u201c fehlt",
        "{n} materials{inv} \u2192 shopping list{extra} \u2713{warn}":
            "{n} Materialien{inv} \u2192 Einkaufsliste{extra} \u2713{warn}",
        "Progress: being checked \u2026":
            "Fortschritt: wird gepr\u00fcft \u2026",
        "Load recipes needed":
            "Baurezepte laden n\u00f6tig",
        "403 no access":
            "403 kein Zugriff",
        "404 unknown":
            "404 unbekannt",
        "skipped (error limit)":
            "\u00fcbersprungen (Error-Limit)",
        "\u26a0 No sell order for this item at the chosen sales hub \u2013 the price stays from the scanned hub.":
            "\u26a0 Am gew\u00e4hlten Verkaufs-Hub gibt es keine Sell-Order f\u00fcr dieses Item \u2013 der Preis bleibt vom gescannten Hub.",
        "\u26a0 Sale price at the chosen hub not loadable: ":
            "\u26a0 Verkaufspreis am gew\u00e4hlten Hub nicht ladbar: ",
        "linked to {where}{auto} \u2013 material lying there counts towards this plan":
            "verkn\u00fcpft mit {where}{auto} \u2013 Material, das dort liegt, z\u00e4hlt f\u00fcr diesen Plan",
        "Nothing here right now \u2013 ESI found neither assets nor orders. As soon as you have material here it is detected and counted automatically. Rigs, tax and system index of this structure count regardless, already.":
            "Hier liegt aktuell nichts \u2013 ESI hat weder Assets noch Orders gefunden. Sobald du hier Material hast, wird es automatisch erkannt und gez\u00e4hlt. Rigs, Steuer und System-Index dieser Struktur z\u00e4hlen unabh\u00e4ngig davon l\u00e4ngst.",
        "Not searched yet \u2013 click \u201eFind locations and link all\u201c above once, then the stock from here counts in the build plan. Rigs, tax and system index count even WITHOUT a link \u2013 only the hangar stock needs it.":
            "Noch nicht gesucht \u2013 einmal \u201eOrte finden und alle verkn\u00fcpfen\u201c oben klicken, dann z\u00e4hlen die Best\u00e4nde von hier im Bauplan. Rigs, Steuer und System-Index z\u00e4hlen auch OHNE Verkn\u00fcpfung \u2013 nur der Lagerbestand braucht sie.",
        "Edit structure":
            "Struktur bearbeiten",
        "{n} buildable hits ({hub}).":
            "{n} baubare Treffer ({hub}).",
        "\u26a0 {n} candidates WITHOUT price history skipped":
            "\u26a0 {n} Kandidaten OHNE Preishistorie \u00fcbersprungen",
        " (ESI limit reached)":
            " (ESI-Limit erreicht)",
        " \u2013 the history is loaded in the background, press \u201eCalculate\u201c again in a few minutes. Tip: minimum volume 0 shows them right away (without the sales check).":
            " \u2013 die Historie wird im Hintergrund nachgeladen, in ein paar Minuten erneut \u201eBerechnen\u201c dr\u00fccken. Tipp: Mindest-Volumen 0 zeigt sie sofort (ohne Absatz-Pr\u00fcfung).",
        "not buildable":
            "nicht baubar",
        "below margin (quick estimate)":
            "unter Marge (Schnellsch\u00e4tzung)",
        "below margin (exact calculation)":
            "unter Marge (genaue Rechnung)",
        "above the display limit (not discarded)":
            "\u00fcber dem Anzeige-Limit (nicht verworfen)",
        "\u26a0 analysis error":
            "\u26a0 Analyse-Fehler",
        "Filtered: ":
            "Gefiltert: ",
        "{n} analysed (sample of {sf} buildable candidates at the hub).":
            "{n} analysiert (Stichprobe aus {sf} baubaren Kandidaten am Hub).",
        "{n} analysed (all buildable candidates at the hub \u2013 the market scan found no more here).":
            "{n} analysiert (alle baubaren Kandidaten am Hub \u2013 mehr hat der Markt-Scan hier nicht gefunden).",
        "\u26a0 {n} candidates not assigned \u2013 a gate is missing in the funnel.":
            "\u26a0 {n} Kandidaten nicht zugeordnet \u2013 im Trichter fehlt ein Tor.",
        "{n} T2/T3 items skipped: BPC not inventable, only available via LP store/drop \u2013 the BPC price is missing from the calculation and would distort the margin.":
            "{n} T2/T3-Items \u00fcbersprungen: BPC nicht erfindbar, nur \u00fcber LP-Store/Drop zu bekommen \u2013 der BPC-Preis fehlt in der Rechnung und w\u00fcrde die Marge verf\u00e4lschen.",
        "\u26a0 {n} hits marked with \u2265 {pct} % adjusted-price share (material without a sell order at the hub) \u2013 build cost uncertain there.":
            "\u26a0 {n} Treffer mit \u2265 {pct} % Adjusted-Price-Anteil markiert (Material ohne Sell-Order am Hub) \u2013 Baukosten dort unsicher.",
        "{pct} % of the build cost comes from the adjusted-price fallback: there is currently no sell order for this material at the hub. The adjusted price is an ESI average, not an offer - the build cost can be off in either direction.":
            "{pct} % der Baukosten stammen aus dem Adjusted-Price-R\u00fcckfall: f\u00fcr dieses Material gibt es am Hub gerade keine Sell-Order. Der Adjusted Price ist ein ESI-Mittelwert, kein Angebot - die Baukosten k\u00f6nnen in beide Richtungen daneben liegen.",
        "Invention is calculated as 0 because own BPCs/BPOs are on hand - without them it would be {isk}/unit more. The saving only holds as long as the copies last.":
            "Invention ist mit 0 gerechnet, weil eigene BPCs/BPOs vorliegen - ohne sie w\u00e4ren es {isk}/Stk mehr. Die Ersparnis gilt nur, solange die Kopien reichen.",
        "Build cost: ":
            "Baukosten: ",
        "Build cost: unknown":
            "Baukosten: unbekannt",
        "Sell now (sell): ":
            "Verkauf jetzt (Sell): ",
        "Profit/day: ":
            "Gewinn/Tag: ",
        "ISK/h: {isk} (profit/unit \u00f7 build time/unit, incl. self-built intermediates)":
            "ISK/Std: {isk} (Gewinn/Stk \u00f7 Bauzeit/Stk, inkl. selbst gebauter Zwischenprodukte)",
        "Profit/m\u00b3: {isk} \u00b7 volume {vol} m\u00b3/unit":
            "Gewinn/m\u00b3: {isk} \u00b7 Volumen {vol} m\u00b3/Stk",
        "\u00d8 daily volume: ":
            "\u00d8 Tagesvolumen: ",
        "unknown (history still loading)":
            "unbekannt (Historie l\u00e4dt noch)",
        "units":
            "Stk",
        "Volatility: ":
            "Volatilit\u00e4t: ",
        "Days of stock: ":
            "Bestandstage: ",
        "Recalculated exactly with a realistic batch size of {n} units.":
            "Genau nachgerechnet mit einer realistischen Losgr\u00f6\u00dfe von {n} St\u00fcck.",
        "Minimum profit per m\u00b3 of cargo hold. Decisive in regional trading: shows what pays off per transport volume. 0 = off.":
            "Mindest-Gewinn pro m\u00b3 Frachtraum. Beim Regional-Trading entscheidend: zeigt, was sich pro Transportvolumen lohnt. 0 = aus.",
        "\uff0b Other structure (paste in-game link) \u2026":
            "\uff0b Andere Struktur (Ingame-Link einf\u00fcgen) \u2026",
        "Choose a structure (found from your orders) \u2013 or \u201ePaste in-game link\u201c below for another one (e.g. your Azbel):":
            "Struktur w\u00e4hlen (aus deinen Orders gefunden) \u2013 oder unten \u201eIngame-Link einf\u00fcgen\u201c f\u00fcr eine andere (z. B. deine Azbel):",
        "\n\u26a0 Current book spread is WIDER than what the item historically yields daily (throwaway-order suspicion) - the rating uses the realistic profit.":
            "\n\u26a0 Aktueller Buch-Spread ist BREITER als das, was das Item historisch t\u00e4glich hergibt (Wegwerf-Order-Verdacht) - Wertung nutzt den realistischen Gewinn.",
        "Searching your structures (assets + orders) \u2026 may take 10\u201320 s":
            "Suche deine Strukturen (Assets + Orders) \u2026 kann 10\u201320 s dauern",
        "Resolving names & volumes \u2026":
            "L\u00f6se Namen & Volumina auf \u2026",
        "{n} pairs checked":
            "{n} Paare gepr\u00fcft",
        "\u26a0 {n} without destination history (structure) \u2013 sales filter NOT applicable there, check demand yourself":
            "\u26a0 {n} ohne Ziel-Historie (Struktur) \u2013 Absatzfilter dort NICHT anwendbar, Nachfrage selbst pr\u00fcfen",
        " units via buy order at {bid} \u00b7 outlay {cost}":
            " St\u00fcck per Buy-Order \u00e0 {bid} \u00b7 Einsatz {cost}",
        " \u00b7 pays off up to bid {cut} (min {m}% profit)":
            " \u00b7 lohnt bis Gebot {cut} (min {m}% Gewinn)",
        " units \u00b7 cost {cost} \u00b7 \u00d8 {avg}":
            " St\u00fcck \u00b7 Kosten {cost} \u00b7 \u00d8 {avg}",
        " \u00b7 pays off up to {cut} (min {m}% profit)":
            " \u00b7 lohnt bis {cut} (min {m}% Gewinn)",
        " \u00b7 only {n} available":
            " \u00b7 nur {n} verf\u00fcgbar",
        "  \u2713 already on the shopping list":
            "  \u2713 bereits in der Einkaufsliste",
        "added to the shopping cart \u2713":
            "zum Einkaufswagen hinzugef\u00fcgt \u2713",
        "Item hidden temporarily":
            "Item vor\u00fcbergehend ausgeblendet",
        "Copies build-plan/swing/manual items (name + quantity) as a multibuy for the immediate purchase from sell orders.":
            "Kopiert Bauplan-/Swing-/manuelle Items (Name + Menge) als Multibuy f\u00fcr den Sofortkauf aus Sell-Orders.",
        " {n} daytrade item(s) in the list are deliberately NOT copied \u2013 they need their own buy order (see the buy-order suggestion above), otherwise you accidentally buy at the expensive sell price instead of placing a cheap buy order yourself.":
            " {n} Daytrade-Item(s) in der Liste werden bewusst NICHT mitkopiert \u2013 die brauchen eine eigene Buy-Order (siehe Buy-Order-Vorschlag oben), sonst kaufst du versehentlich zum teuren Sell-Preis statt selbst eine g\u00fcnstige Buy-Order zu stellen.",
        "New margin":
            "Marge neu",
        "\u00d8 purchase price from your collected transactions \u2013 the same number as in the portfolio.":
            "\u00d8-Einkaufspreis aus deinen gesammelten Transaktionen \u2013 dieselbe Zahl wie im Portfolio.",
        "\u26a0 fees eat the profit":
            "\u26a0 Geb\u00fchren fressen Gewinn",
        "\u26a0 no profit":
            "\u26a0 kein Gewinn",
        "\u26a0 loss":
            "\u26a0 Verlust",
        "\u26a0 outbid":
            "\u26a0 \u00fcberboten",
        "\u26a0 undercut":
            "\u26a0 unterboten",
        "This order has already been adjusted {n}\u00d7 - estimated broker fees from that so far: \u2248{fee}. That alone already eats the expected profit over the remaining quantity.":
            "Diese Order wurde schon {n}\u00d7 nachgebessert - gesch\u00e4tzte Broker-Geb\u00fchren dadurch bisher: \u2248{fee}. Das allein frisst den erwarteten Gewinn \u00fcber die Restmenge schon auf.",
        "{name} added to the shopping cart (quantity 1).":
            "{name} in den Einkaufswagen (Menge 1).",
        "{name} added to the shopping cart.":
            "{name} zum Einkaufswagen hinzugef\u00fcgt.",
        "Already in the shopping cart.":
            "Schon im Einkaufswagen.",
        "Corporation \u201e{corp}\u201c was not found at ESI.":
            "Corporation \u201e{corp}\u201c wurde bei ESI nicht gefunden.",
        "Price source is currently \u201e{src}\u201c \u2013 i.e. NOT the trade hub. A player structure often has only a few, overpriced sell orders; the margin would be invented. Run a market scan at the hub first, then the numbers are right.":
            "Preisquelle ist zurzeit \u201e{src}\u201c \u2013 also NICHT der Handelshub. In einer Spielerstruktur stehen oft nur wenige, \u00fcberteuerte Sell-Orders; die Marge w\u00e4re erfunden. Erst wieder einen Markt-Scan am Hub fahren, dann stimmen die Zahlen.",
        "Net margin above your target margin \u2013 sellable.":
            "Netto-Marge \u00fcber deiner Ziel-Marge \u2013 verkaufbar.",
        " Note: price is still below the normal level ({normal}) \u2013 there might be more, your call.":
            " Hinweis: Preis liegt noch unter dem Normalniveau ({normal}) \u2013 da ginge evtl. mehr, deine Entscheidung.",
        "Purchase price unknown (owned before the program) and price not at the normal level \u2013 no recommendation possible.":
            "Kaufpreis unbekannt (vor dem Programm besessen) und Preis nicht auf Normalniveau \u2013 keine Handlungsempfehlung m\u00f6glich.",
        "Net margin below your target margin":
            "Netto-Marge unter deiner Ziel-Marge",
        ", normal level {normal} not reached yet":
            ", Normalniveau {normal} noch nicht erreicht",
        " \u2013 wait.":
            " \u2013 warten.",
        "\u2022 EVE server version changed:\n    {old} \u2192 {new}":
            "\u2022 EVE-Server-Version ge\u00e4ndert:\n    {old} \u2192 {new}",
        "\u2022 Recipe data (SDE) is newer:\n    {sde}":
            "\u2022 Baurezepte-Daten (SDE) sind neuer:\n    {sde}",
        "Worth building":
            "Lohnt sich zu bauen",
        "Daily evidence from the price history (like the orange dots of the in-game price table):\n\u2022 Buy side (lows reach the buy order): {buy} %\n\u2022 Sell side (highs reach the sell order): {sell} %\n\u2022 BOTH sides on the same day: {both} %\n100/100/100 = every day low at the bottom + high at the top = perfect flip item. The tradability on the left is weighted with this.\n\n\u00d8 cycle (queue buy + sell): {cyc} days per flip.\nRealistic profit/unit (median daily spread of the history): {prof} ISK ({roi} %)":
            "Tages-Belege aus der Preishistorie (wie die orangen Punkte der Ingame-Preistabelle):\n\u2022 Buy-Seite (Lows erreichen die Buy-Order): {buy} %\n\u2022 Sell-Seite (Highs erreichen die Sell-Order): {sell} %\n\u2022 BEIDE Seiten am selben Tag: {both} %\n100/100/100 = jeden Tag Low unten + High oben = perfektes Flip-Item. Die Handelbarkeit links ist damit gewichtet.\n\n\u00d8 Zyklus (Warteschlange Buy + Sell): {cyc} Tage je Flip.\nRealistischer Gewinn/Stk (Median-Tagesspread der Historie): {prof} ISK ({roi} %)",
        "Being loaded automatically from ESI \u2026":
            "Wird gerade automatisch aus ESI geladen \u2026",
        "Plan was saved before the reservation feature \u2013 open it once and save again, then the consumption list is there.":
            "Plan wurde vor der Reservierungs-Funktion gespeichert \u2013 einmal \u00f6ffnen und neu speichern, dann steht die Verbrauchsliste.",
        "Plan comes from an older version \u2013 its reservation does not know the SELF-BUILT yet. Open it once and save again, then it also protects intermediates.":
            "Plan stammt aus einer \u00e4lteren Fassung \u2013 seine Reservierung kennt das SELBSTGEBAUTE noch nicht. Einmal \u00f6ffnen und neu speichern, dann sch\u00fctzt sie auch Zwischenprodukte.",
        "{n} build structure(s) automatically linked to the real EVE structure: ":
            "{n} Bau-Struktur(en) automatisch mit der echten EVE-Struktur verkn\u00fcpft: ",
        "enough \u2713 (via BPC)":
            "genug \u2713 (via BPC)",
        "too few \u2013 {n} more runs (BPC) needed":
            "zu wenig \u2013 noch {n} Runs (BPC) n\u00f6tig",
        "completely missing \u2013 you need {n}":
            "fehlt komplett \u2013 brauchst {n}",
        "\u2013 (load contract prices)":
            "\u2013 (Contract-Preise laden)",
        "Build margin: ":
            "Bau-Marge: ",
        "Profit/unit: ":
            "Gewinn/Stk: ",
        "Profit/m\u00b3: ":
            "Gewinn/m\u00b3: ",
        "ISK/h: ":
            "ISK/Std: ",
        "Active contracts: ":
            "Aktive Contracts: ",
        " ({n} of them derived from bundles: ship+accessory contracts, extras deducted at Jita price)":
            " (davon {n} aus Bundles abgeleitet: Schiff+Zubeh\u00f6r-Contracts, Beilagen zum Jita-Preis abgezogen)",
        "Price range: ":
            "Preisspanne: ",
        "(Reference = MEDIAN of the contracts; the mean would be distorted by outliers.)":
            "(Referenz = MEDIAN der Contracts; Mittelwert w\u00fcrde von Ausrei\u00dfern verzogen.)",
        "{a} of {b} cached (\u22647 d)":
            "{a} von {b} gecachten (\u22647 T)",
        "{n} from cache (\u22647 d, complete)":
            "{n} aus Cache (\u22647 T, vollst\u00e4ndig)",
        "{n} newly loaded":
            "{n} neu geladen",
        "Required: ":
            "Ben\u00f6tigt: ",
        "Owned:  ":
            "Besitze:  ",
        "Missing:    ":
            "Fehlt:    ",
        "BUY":
            "KAUF",
        "BUILD":
            "BAU",
        "  (building would have cost {isk})":
            "  (Bau h\u00e4tte {isk} gekostet)",
        "  (market {isk})":
            "  (Markt {isk})",
        "{n} \u2192 shopping cart \u2713":
            "{n} \u2192 Einkaufswagen \u2713",
        "Newly detected and linked: ":
            "Neu erkannt und verkn\u00fcpft: ",
        " \u2013 stock from there counts from the next fetch on.":
            " \u2013 Best\u00e4nde von dort z\u00e4hlen ab dem n\u00e4chsten Abruf mit.",
        "Checking actual sales at the destination \u2026":
            "Pr\u00fcfe tats\u00e4chlichen Absatz im Ziel \u2026",
        "Searching empty destination markets with sales \u2026":
            "Suche leere Zielm\u00e4rkte mit Absatz \u2026",
        "Counter reset to {n}":
            "Z\u00e4hler auf {n} zur\u00fcckgesetzt",
        "Outbidding to {price} leaves no flip profit after broker (buy) + tax/broker (sell) - the market sell is only {sell}.":
            "H\u00f6herbieten auf {price} l\u00e4sst nach Broker (Kauf) + Steuer/Broker (Verkauf) keinen Flip-Gewinn mehr \u00fcbrig - der Markt-Sell liegt nur bei {sell}.",
        "Undercutting to {price} would be BELOW your purchase price (\u00d8 {cost}) after tax + broker - you would make a loss.":
            "Unterbieten auf {price} l\u00e4ge nach Steuer + Broker UNTER deinem Einkaufspreis (\u00d8 {cost}) - du machst dann Verlust.",
        "Cancelled - {name} was NOT copied (loss warning).":
            "Abgebrochen - {name} wurde NICHT kopiert (Verlust-Warnung).",
        "Quantity applied \u2713":
            "Menge \u00fcbernommen \u2713",
        "No non-daytrade items in the shopping list.":
            "Keine Nicht-Daytrade-Items in der Einkaufsliste.",
        "No items in the shopping list. Add items first (e.g. in the build plan \u201eBuy materials \u2192 shopping cart\u201c).":
            "Keine Items in der Einkaufsliste. Erst Items hinzuf\u00fcgen (z. B. im Bauplan \u201eKauf-Materialien \u2192 Einkaufswagen\u201c).",
        "{n} daytrade item(s) NOT copied along \u2013 they need their own buy order, not Multibuy":
            "{n} Daytrade-Item(s) NICHT mitkopiert \u2013 die brauchen eine eigene Buy-Order, kein Multibuy",
        "Multibuy copied \u2713 ({n})":
            "Multibuy kopiert \u2713 ({n})",
        "{n} reaction formulas checked.":
            "{n} Reaktions-Formeln gepr\u00fcft.",
        "YIELD CENSUS (yield per run: number of formulas):":
            "AUSBEUTE-ZENSUS (Ausbeute je Run: Anzahl Formeln):",
        "!! {n} formula(s) with yield NULL/0 - the import silently turns that into 1!":
            "!! {n} Formel(n) mit Ausbeute NULL/0 - der Import macht daraus stillschweigend 1!",
        "!! {n} yield(s) do NOT arrive 1:1 in the loaded recipes!":
            "!! {n} Ausbeute(n) kommen NICHT 1:1 in den geladenen Rezepten an!",
        "Census: no anomalies, import arrived 1:1. \u2713":
            "Zensus: keine Anomalien, Import 1:1 angekommen. \u2713",
        "PATCH COMPARISON NOT POSSIBLE ({err}) \u2013 the census above still applies. Check again later with internet.":
            "PATCH-ABGLEICH NICHT M\u00d6GLICH ({err}) \u2013 der Zensus oben gilt trotzdem. Sp\u00e4ter mit Internet erneut pr\u00fcfen.",
        "!! {n} YIELD(S) OUTDATED (CCP patch) - first:":
            "!! {n} AUSBEUTE(N) VERALTET (CCP-Patch) - erste:",
        "   Product {pid}: local {loc}/run, game {game}/run":
            "   Produkt {pid}: lokal {loc}/Run, Spiel {game}/Run",
        "!! {n} INGREDIENT QUANTITY/QUANTITIES OUTDATED.":
            "!! {n} ZUTATENMENGE(N) VERALTET.",
        "\u26a0 {n} recipe(s) removed in game, still here locally.":
            "\u26a0 {n} Rezept(e) im Spiel entfernt, lokal noch da.",
        "\u26a0 {n} new recipe(s) in game, unknown locally.":
            "\u26a0 {n} neue(s) Rezept(e) im Spiel, lokal unbekannt.",
        "Patch comparison: ALL yields and ingredient quantities up to date. \u2713":
            "Patch-Abgleich: ALLE Ausbeuten und Zutatenmengen auf aktuellem Stand. \u2713",
        "-> run \u201eLoad recipes\u201c, then check again (must be empty afterwards).":
            "-> \u201eBaurezepte laden\u201c ausf\u00fchren, dann erneut pr\u00fcfen (muss danach leer sein).",
        "Sales mode":
            "Verkaufs-Modus",
        "Inventory import (assets)":
            "Inventar-Import (Assets)",
        "Structure markets":
            "Struktur-M\u00e4rkte",
        "Implant manufacturing bonus":
            "Implantat-Fertigungsbonus",
        "On: portfolio shows the real hangar inventory. Off: derived from transactions.":
            "An: Portfolio zeigt echtes Hangar-Inventar. Aus: aus Transaktionen abgeleitet.",
        "Contract price applied: median ":
            "Contract-Preis \u00fcbernommen: Median ",
        "Searching public contracts across all of New Eden \u2026":
            "Suche \u00f6ffentliche Contracts in ganz New Eden \u2026",
        "No public contract found for this item \u2013 the sale price stays unchanged.":
            "Kein \u00f6ffentlicher Contract f\u00fcr dieses Item gefunden \u2013 Verkaufspreis bleibt unver\u00e4ndert.",
        "The cause is usually stock that was counted at freeze time and is gone by now (used/sold/counted as pipeline). The plan deliberately sticks to the frozen state so the shopping list stays stable \u2013 this preview is the honest counter-calculation.":
            "Ursache ist meist Bestand, der beim Einfrieren angerechnet wurde und inzwischen weg ist (verbraucht/verkauft/als Pipeline gez\u00e4hlt). Der Plan h\u00e4lt bewusst am Einfrier-Stand fest, damit die Einkaufsliste stabil bleibt \u2013 diese Vorschau ist die ehrliche Gegenrechnung.",
        "\u2192 Buy the shortfalls OR push the affected reaction runs.":
            "\u2192 Fehlmengen nachkaufen ODER die betroffenen Reaktions-Runs nachschieben.",
        "{name} has the lowest fees ({combined}% = {tax}% tax + {broker}% broker) and was applied. Comparison: {cmp}":
            "{name} hat die niedrigsten Geb\u00fchren ({combined}% = {tax}% Tax + {broker}% Broker) und wurde \u00fcbernommen. Vergleich: {cmp}",
        "Taken from EVE: Accounting {acc}, Broker Relations {br}, {n} standing values \u2013 saved automatically.":
            "Aus EVE \u00fcbernommen: Accounting {acc}, Broker Relations {br}, {n} Standing-Werte \u2013 automatisch gespeichert.",
        "Skills could not be read \u2013 the token does not have the new scopes yet. Please remove and re-link once in the Characters tab.":
            "Skills konnten nicht gelesen werden \u2013 der Token hat die neuen Scopes noch nicht. Bitte im Charaktere-Tab einmal entfernen und neu verkn\u00fcpfen.",
        "Error reading the skills: ":
            "Fehler beim Lesen der Skills: ",
        "For wallet, orders and portfolio you need at least one linked character. You can scan the Jita market without a character too (for scanner & deals).":
            "F\u00fcr Wallet, Orders und Portfolio brauchst du mindestens einen verkn\u00fcpften Charakter. Den Jita-Markt kannst du auch ohne Charakter scannen (f\u00fcr Scanner & Deals).",
        "Link character":
            "Charakter verkn\u00fcpfen",
        "Scan market only":
            "Nur Markt scannen",
        "only what is still missing":
            "nur was noch fehlt",
        "ON: only the material for the runs that are still OPEN \u2013 the list shrinks while you build (same calculation as \u201eCheck shortfall\u201c).\nOFF: the full plan quantity, as on the freeze day.\nWhat you have already built into the next stage is NOT bought again.":
            "AN: nur das Material f\u00fcr die noch OFFENEN Runs \u2013 die Liste schrumpft beim Bauen (dieselbe Rechnung wie \u201eFehlbedarf pr\u00fcfen\u201c).\nAUS: die volle Planmenge wie am Einfrier-Tag.\nWas du schon in die n\u00e4chste Stufe verbaut hast, wird NICHT noch einmal gekauft.",
        "Nothing left to buy \u2013 the remaining runs are covered.":
            "Nichts mehr zu kaufen \u2013 die restlichen Runs sind gedeckt.",
        "Nothing to copy - the materials tab is empty.":
            "Nichts zu kopieren - Materialien-Tab ist leer.",
        "Below target margin":
            "Unter Ziel-Marge",
        "{name}: after adjusting, the margin is {have} % \u2013 your target is {want} %.":
            "{name}: nach dem Nachbessern liegt die Marge bei {have} % \u2013 dein Ziel sind {want} %.",
        "You still earn on this, just less than planned. Adjusting again later pushes it down further.\n\nCopy anyway?":
            "Du verdienst weiter daran, nur weniger als geplant. Nochmaliges Nachbessern drueckt sie weiter.\n\nTrotzdem kopieren?",
        "Cancelled - {name} was NOT copied (below target margin).":
            "Abgebrochen - {name} wurde NICHT kopiert (unter Ziel-Marge).",
        "below \u00d8 %":
            "unter \u00d8 %",
        "Build margin %":
            "Bau-Marge %",
        "% above normal":
            "% \u00fcber Normal",
        "{n} items from the portfolio \u2713":
            "{n} Items aus dem Portfolio \u2713",
        "\u2795 Into the cart without demand ({n}): ":
            "\u2795 Ohne Nachfrage in den Wagen ({n}): ",
        "\u26a0 Not held by any character (only in open orders)":
            "\u26a0 Liegt bei keinem Charakter (nur in offenen Orders)",
        "Best-case producer: ME {me} % \u00b7 T2 rigs x nullsec \u00b7 invention skills V \u00b7 reaction only if cheaper than buying\n":
            "Best-Case-Produzent: ME {me} % \u00b7 T2-Rigs x Nullsec \u00b7 Invention-Skills V \u00b7 Reaktion nur wenn billiger als Kaufen\n",
        "  \u26a0 Without a price (as \u201e?\u201c in the list, so nothing shifts): ":
            "  \u26a0 Ohne Preis (als \u201e?\u201c in der Liste, damit nichts verrutscht): ",
        "FLOOR CALCULATION \u00b7 {name}\n":
            "BODEN-RECHNUNG \u00b7 {name}\n",
        "Material prices: current market snapshot (sell min)\n":
            "Materialpreise: aktueller Markt-Snapshot (sell min)\n",
        "Load now":
            "Jetzt laden",
        "Subtracts what already lies on your build structures per ESI.":
            "Zieht ab, was laut ESI schon auf deinen Bau-Strukturen liegt.",
        "Expand/collapse all levels in the run planner.":
            "Alle Ebenen im Runplaner auf-/zuklappen.",
        "\u26a0 THE MARKET IS BELOW YOUR MINIMUM PRICE \u2013 at this price you make a loss.":
            "\u26a0 MARKT LIEGT UNTER DEINEM MINDESTPREIS \u2013 zu diesem Preis machst du Verlust.",
        "\u26a0 Market is BELOW your minimum price":
            "\u26a0 Markt liegt UNTER deinem Mindestpreis",
        "  \u2013 not with frozen prices":
            "  \u2013 nicht bei eingefrorenen Preisen",
        "Material you already have, valued at min(purchase price, your own build cost) - what it costs you to replace it.":
            "Bereits vorhandenes Material, bewertet mit min(Kaufpreis, eigene Baukosten) - was es dich kostet, es zu ersetzen.",
        "At the pure purchase price it would be {isk} ({pct} %) - that difference is other producers' margin and does not belong in your cost.":
            "Zum reinen Kaufpreis w\u00e4ren es {isk} ({pct} %) - diese Differenz ist die Marge fremder Produzenten und geh\u00f6rt nicht in deine Kosten.",
        "\u00f7 {n} units":
            "\u00f7 {n} St\u00fcck",
        "Reset frozen stock":
            "Einfrier-Bestand neu setzen",
        "  \u2013 load assets first":
            "  \u2013 erst Assets laden",
        "Minimum build margin: (sale \u2212 build cost) / build cost. 10 %+ counts as usable, below that it hardly pays.":
            "Mindest-Bau-Marge: (Verkauf \u2212 Baukosten) / Baukosten. 10 %+ gilt als brauchbar, darunter lohnt es kaum.",
        "Blueprint not marked as owned":
            "Blaupause nicht als besessen markiert",
        "Total profit \u2013 total profit by build quantity (dots = efficiency quantity and recommendation)":
            "Gewinn gesamt \u2013 Gesamtgewinn je nach Baumenge (Punkte = Effizienz-Menge und Empfehlung)",
        "Total profit (ISK)":
            "Gewinn gesamt (ISK)",
        "Profitable up to {qty}, not beyond":
            "Profitabel bis {qty}, dar\u00fcber nicht mehr",
        "Optimiser \u2013 {name}":
            "Optimierer \u2013 {name}",
        "OPTIMAL BUILD QUANTITY \u2013 {name}":
            "OPTIMALE BAU-MENGE \u2013 {name}",
        "End product:": "Endprodukt:",
        "A bundle has several end products; the quantity curve is calculated "
        "for ONE of them at a time (with the bundle's settings for that "
        "product).":
            "Ein B\u00fcndel hat mehrere Endprodukte; die Mengenkurve wird f\u00fcr "
            "EINES davon gerechnet (mit den Einstellungen des B\u00fcndels f\u00fcr "
            "dieses Produkt).",
        "Sale price/unit:":
            "Verkaufspreis/Stk:",
        "Cargo hold/trip:":
            "Frachtraum/Fahrt:",
        "Calculate":
            "Berechnen",
        "No curve data calculated.":
            "Keine Kurvendaten berechnet.",
        "\u26a0 Error while calculating: ":
            "\u26a0 Fehler beim Berechnen: ",
        "Order-book-exact material cost \u2013 {name}":
            "Orderbuch-genaue Materialkosten \u2013 {name}",
        "ORDER-BOOK EXACT \u2013 {name} \u00d7{qty}":
            "ORDERBUCH-GENAU \u2013 {name} \u00d7{qty}",
        "\u2014 No order book":
            "\u2014 Kein Orderbuch",
        "Order-book proof \u2013 {name}":
            "Orderbuch-Nachweis \u2013 {name}",
        "Preset set \u2013 now \u201eFind blueprints\u201c.":
            "Preset gesetzt \u2013 jetzt \u201eBlaupausen suchen\u201c.",
        "Run \u201eLoad recipes\u201c first.":
            "Erst \u201eBaurezepte laden\u201c.",
        "{hit}/{all} hits recalculated exactly ( marker) \u2713":
            "{hit}/{all} Treffer genau nachgerechnet (-Markierung) \u2713",
        "Error: ":
            "Fehler: ",
        "What you want to build":
            "Was du bauen willst",
        "Capital mode":
            "Capital-Modus",
        "Profile:":
            "Profil:",
        "Load":
            "Laden",
        "Save as \u2026":
            "Speichern unter \u2026",
        "Manufacturing \u2014 structure & rigs determine material efficiency (job cost & build time follow)":
            "Fertigung \u2014 Struktur & Rigs bestimmen Material-Effizienz (Job-Kosten & Bauzeit folgen)",
        "Build reactions yourself":
            "Reaktionen selbst bauen",
        "Buy reactions":
            "Reaktionen kaufen",
        "Include invention":
            "Invention einrechnen",
        "Ignore invention":
            "Invention ignorieren",
        "Decryptor":
            "Decryptor",
        "All categories":
            "Alle Kategorien",
        "All races":
            "Alle Rassen",
        "Only items up to this sale price (0 = \u221e).":
            "Nur Items bis zu diesem Verkaufspreis (0 = \u221e).",
        "Ship name \u2026":
            "Schiffs-Name \u2026",
        "Load contract prices (all of New Eden)":
            "Contract-Preise laden (ganz New Eden)",
        "\u2699 End product ME/TE ({name})":
            "\u2699 Endprodukt-ME/TE ({name})",
        "ME:":
            "ME:",
        "TE:":
            "TE:",
        "Structure: ":
            "Struktur: ",
        "Planned certainty:":
            "Geplante Sicherheit:",
        "\u2014 Best automatically \u2014":
            "\u2014 Bester automatisch \u2014",
        "\u00d7{n} per attempt":
            "\u00d7{n} je Versuch",
        "{name} Blueprint":
            "{name} Blueprint",
        "Success chance":
            "Erfolgschance",
        "Runs/success":
            "Runs/Erfolg",
        "ME":
            "ME",
        "TE":
            "TE",
        "{pct} % covered\n":
            "{pct} % gedeckt\n",
        "Nothing to build yourself (all bought?).":
            "Nichts selbst zu bauen (alles Kauf?).",
        "{name}: split {runs} runs across {n} blueprints (":
            "{name}: {runs} Runs auf {n} Blueprints aufteilen (",
        " = {runs}). ~{n}\u00d7 faster than 1 BP.":
            " = {runs}). ~{n}\u00d7 schneller als 1 BP.",
        "\u2139  Not planned \u2013 buying cheaper / stock covers ":
            "\u2139  Nicht eingeplant \u2013 Kauf billiger / Bestand deckt ",
        "({n} buildable items)":
            "({n} baubare Items)",
        "Build plan \u2013 {name}":
            "Bauplan \u2013 {name}",
        "= {r} run(s) with {n} units":
            "= {r} Run(s) \u00e0 {n} Stk",
        "Runs/BPC:":
            "Runs/BPC:",
        "Plan frozen \u2013 purchase ":
            "Plan eingefroren \u2013 Einkauf ",
        " \u00b7 profit live":
            " \u00b7 Gewinn live",
        "Bought on {d} \u2013 prices frozen":
            "Eingekauft am {d} \u2013 Preise eingefroren",
        "Freeze plan \u2013 purchase done":
            "Plan einfrieren \u2013 Einkauf erledigt",
        "Order-book exact":
            "Orderbuch-genau",
        "Order-book exact":
            "Orderbuch-genau",
        "Load contract prices (New Eden)":
            "Contract-Preise laden (New Eden)",
        "  \u2013 not for bundles": "  \u2013 nicht bei B\u00fcndeln",
        "A bundle sells its end products one by one at their own hub prices; "
        "a contract price per end product is not supported yet. Open the "
        "single build plan of that product for it.":
            "Ein B\u00fcndel verkauft seine Endprodukte einzeln zu ihren eigenen "
            "Hub-Preisen; ein Contract-Preis je Endprodukt wird noch nicht "
            "unterst\u00fctzt. Daf\u00fcr den Einzel-Bauplan des Produkts \u00f6ffnen.",
        "Sell in:":
            "Verkauf in:",
        "\u2014 global \u2014":
            "\u2014 global \u2014",
        "\u2014 global \u2014 (skills not loaded)":
            "\u2014 global \u2014 (Skills nicht geladen)",
        "Details \u25be":
            "Details \u25be",
        "Details \u25b4":
            "Details \u25b4",
        "Action":
            "Aktion",
        "unit":
            "Stk",
        "Cost":
            "Kosten",
        "Build (category / component)":
            "Bauen (Kategorie / Komponente)",
        "Tick build characters in the setup + \u201eLoad skills\u201c.":
            "Bau-Charaktere im Setup ankreuzen + \u201eSkills laden\u201c.",
        "Character / item / material":
            "Charakter / Item / Material",
        "Blueprints":
            "Blaupausen",
        "Time":
            "Zeit",
        "Copy blueprint name":
            "Blueprint-Name kopieren",
        "Copy all blueprint names":
            "Alle Blueprint-Namen kopieren",
        "Loading ESI blueprint ownership \u2026":
            "Lade ESI-Blueprint-Besitz \u2026",
        "Expand/collapse all category groups.":
            "Alle Kategorie-Gruppen auf-/zuklappen.",
        "Clear":
            "Leeren",
        "  (end product)":
            "  (Endprodukt)",
        "Invention ({n} jobs)":
            "Invention ({n} Jobs)",
        " \u2013 invention attempts":
            " \u2013 Invention-Versuche",
        "   ({n} jobs)":
            "   ({n} Jobs)",
        "of which {isk} from stock":
            "davon {isk} aus Bestand",
        "Plan frozen on {d} \u2013 structure, quantities + run planner fixed; progress from ESI jobs, profit live.":
            "Plan eingefroren am {d} \u2013 Struktur, Mengen + Runplaner fest; Fortschritt aus ESI-Jobs, Gewinn live.",
        "Frozen on {d} \u2013 costs fixed, sale price + build progress live.":
            "Eingefroren am {d} \u2013 Kosten fest, Verkaufspreis + Baufortschritt live.",
        " ({n} items)":
            " ({n} Items)",
        "\u25C8 TIP":
            "\u25C8 TIPP",
        "Error while loading: ":
            "Fehler beim Laden: ",
        "Recalculation failed: ":
            "Neu berechnen fehlgeschlagen: ",
        "Own trip:":
            "Eigene Fahrt:",
        "Freight in decision":
            "Fracht mitentscheiden",
        "Total amount:":
            "Betrag gesamt:",
        "Save build plan":
            "Bauplan speichern",
        "Name of the build plan:":
            "Name des Bauplans:",
        "Build plan already exists":
            "Bauplan existiert bereits",
        "Ready.":
            "Bereit.",
        "Load sell-order prices":
            "Verkaufsorder-Preise laden",
        "Key figures at the top":
            "Kennzahlen oben",
        "Container toggle failed: ":
            "Container-Umschalten fehlgeschlagen: ",
        "Show history":
            "Verlauf anzeigen",
        "Top 15":
            "Top 15",
        " days":
            " Tage",
        "Show all":
            "Alle anzeigen",
        "Only items from this sell price up.":
            "Nur Items ab diesem Sell-Preis.",
        "Scanning {hub} \u2026":
            "Scanne {hub} \u2026",
        "Scan cancelled.":
            "Scan abgebrochen.",
        "Scan cancelled / empty.":
            "Scan abgebrochen / leer.",
        "Structure scan error (access/scope/ID?): ":
            "Struktur-Scan-Fehler (Zugang/Scope/ID?): ",
        "Recipes + categories loaded. ":
            "Baurezepte + Kategorien geladen. ",
        "Now \u201eFind blueprints\u201c.":
            "Jetzt \u201eBlaupausen suchen\u201c.",
        "Analysing \u2026 {d}/{n}":
            "Analysiere \u2026 {d}/{n}",
        "(load recipes first)":
            "(erst \u201eBaurezepte laden\u201c)",
        "Gold search cancelled.":
            "Gold-Suche abgebrochen.",
        "Gold search done.":
            "Gold-Suche fertig.",
        "Gold search error: ":
            "Gold-Suche Fehler: ",
        "Preset set \u2013 now \u201eLoad deals\u201c.":
            "Preset gesetzt \u2013 jetzt \u201eDeals laden\u201c.",
        "\u2192 selection into the cart ({n} items)":
            "\u2192 Auswahl in Einkaufswagen ({n} Items)",
        "Only items from this current sell price up.":
            "Nur Items ab diesem aktuellen Sell-Preis.",
        "\u2014 none (ignore skills) \u2014":
            "\u2014 keiner (Skills ignorieren) \u2014",
        "Load own BPCs":
            "Eigene BPCs laden",
        "Buy datacores":
            "Datacores kaufen",
        "Buy decryptors":
            "Decryptoren kaufen",
        "\u2022 Own selection":
            "\u2022 Eigene Auswahl",
        "Implant":
            "Implantat",
        "No implant":
            "Kein Implantat",
        "Save profile":
            "Profil speichern",
        "Name of the profile (e.g. \u201eAzbel null \u00b7 own reactions\u201c):":
            "Name des Profils (z. B. \u201eAzbel Null \u00b7 Reaktionen selbst\u201c):",
        "System: {sys}  \u00b7  manufacturing cost index: {idx} %  (live from ESI)  \u00b7  facility tax: {ftax} %  \u00b7  + 4 % SCC (fixed)":
            "System: {sys}  \u00b7  Fertigungs-Kosten-Index: {idx} %  (live aus ESI)  \u00b7  Facility-Tax: {ftax} %  \u00b7  + 4 % SCC (fix)",
        "System index error (structure access?): ":
            "System-Index-Fehler (Struktur-Zugang?): ",
        # RAIL-KNOEPFE: alter Namensstand (Nutzer 22.09.2026, "gehe zurueck
        # auf alten Namensstand fuer Multibuildplan und Build plan"). Die
        # "Create ..."-Eintraege vom selben Tag sind wieder raus - ein
        # verwaister Katalogeintrag laesst aa235/aa257 rot laufen.
        "New build plan":
            "Neuer Bauplan",
        "Search blueprint / item:":
            "Blaupause / Item suchen:",
        "Stock (ESI): state unknown":
            "Bestand (ESI): Stand unbekannt",
        "completed by hand \u2713":
            "von Hand abgeschlossen \u2713",
        "{pct} % \u00b7 {b}/{q} built":
            "{pct} % \u00b7 {b}/{q} gebaut",
        "{b}/{q} built":
            "{b}/{q} gebaut",
        " (shared)":
            " (geteilt)",
        "MY BLUEPRINTS":
            "MEINE BLUEPRINTS",
        "Blueprint name \u2026":
            "Blueprint-Name \u2026",
        "Show original blueprints (unlimited runs).":
            "Original-Blaupausen (unbegrenzte Runs) anzeigen.",
        "Show copies (limited runs).":
            "Kopien (begrenzte Runs) anzeigen.",
        "\u26A0 Show missing":
            "\u26A0 Fehlende anzeigen",
        "Count":
            "Anzahl",
        "Build cost/unit":
            "Baukosten/Stk",
        "Sale/unit":
            "Verkauf/Stk",
        "ISK/h":
            "ISK/Std",
        "Opt. quantity":
            "Opt. Menge",
        "Location":
            "Standort",
        "Loading blueprints \u2026":
            "Lade Blueprints \u2026",
        "  \u26a0 Missing-blueprints search failed: ":
            "  \u26a0 Fehlende-Blueprints-Suche fehlgeschlagen: ",
        "MY STRUCTURES":
            "MEINE STRUKTUREN",
        "Edit":
            "Bearbeiten",
        "\u2013 auto (best per build plan) \u2013":
            "\u2013 Auto (beste je Bauplan) \u2013",        "Type a system \u2026":
            "System tippen \u2026",
        "Save":
            "Speichern",
        "{n}\u00d7 BP":
            "{n}\u00d7 BP",
        "Category data missing \u2013 \u201eLoad recipes\u201c.":
            "Kategorie-Daten fehlen \u2013 \u201eBaurezepte laden\u201c.",
        "Calculating build profits \u2026":
            "Berechne Bau-Gewinne \u2026",
        "Searching capital ships + calculating build cost \u2026":
            "Suche Capital-Schiffe + berechne Baukosten \u2026",
        "Discount %":
            "Rabatt %",
        "\u26a0 Error while loading: ":
            "\u26a0 Fehler beim Laden: ",
        "\u2713 in the cart":
            "\u2713 im Wagen",
        "Item (exact, e.g. PLEX)":
            "Item (exakt, z. B. PLEX)",
        "\u00d8 buy now":
            "\u00d8-Kauf sofort",
        "Buy order":
            "Buy-Order",
        "\u00d8 sale":
            "\u00d8-Verkauf",
        "Share of daily volume:":
            "Anteil vom Tagesvolumen:",
        "Source: {src}. (\u26a1 Daytrade \u00b7 \u2197 Swing)":
            "Quelle: {src}. (\u26a1 Daytrade \u00b7 \u2197 Swing)",
        "Copy quantity to the clipboard.":
            "Menge ins Clipboard kopieren.",
        "Loading open orders + market prices ({hub}) \u2026":
            "Lade offene Orders + Marktpreise ({hub}) \u2026",
        "Buy orders ({n} to adjust)":
            "Buy-Orders ({n} nachbessern)",
        "Sell orders ({n} to adjust)":
            "Sell-Orders ({n} nachbessern)",
        "Loss warning":
            "Verlust-Warnung",
        "Current sell prices loaded ({n} items).":
            "Aktuelle Sell-Preise geladen ({n} Items).",
        "No usable rows.":
            "Keine verwertbaren Zeilen.",
        "Fetch failed: ":
            "Abruf fehlgeschlagen: ",
        "Buy-order suggestion \u2013 {name}":
            "Buy-Order-Vorschlag \u2013 {name}",
        "   \u00b7   flow \u2248 {isk}/day":
            "   \u00b7   Durchfluss \u2248 {isk}/Tag",
        "Loading order depth ({hub}) \u2026":
            "Lade Order-Tiefe ({hub}) \u2026",
        "Order depth & daily volume loaded.":
            "Order-Tiefe & Tagesvolumen geladen.",
        "Empty the shopping cart?":
            "Einkaufswagen leeren?",
        "Revenue":
            "Umsatz",
        "Profit (net)":
            "Gewinn (netto)",
        "All":
            "Alle",
        "Everything":
            "Alles",
        "Last 30 days":
            "Letzte 30 Tage",
        "Last 90 days":
            "Letzte 90 Tage",
        "Last year":
            "Letztes Jahr",
        "Item name \u2026":
            "Item-Name \u2026",
        "CSV export":
            "CSV-Export",
        "Sum":
            "Summe",
        "Fetching the latest transactions from EVE \u2026":
            "Hole neueste Transaktionen aus EVE \u2026",
        "Update failed: ":
            "Aktualisieren fehlgeschlagen: ",
        " transactions exported: {path}":
            " Transaktionen exportiert: {path}",
        "\u00d8 line":
            "\u00d8-Linie",
        "Character removed. Backup saved: {file}":
            "Charakter entfernt. Backup gesichert: {file}",
        "Character removed.":
            "Charakter entfernt.",
        "Sell order (Jita sell min)":
            "Sell-Order (Jita sell min)",
        "Immediate (Jita buy max)":
            "Sofort (Jita buy max)",
        "Manual (values above)":
            "Manuell (Werte oben)",
        "Calculate from my skills":
            "Aus meinen Skills berechnen",
        "Level ":
            "Level ",
        "Program version":
            "Programm-Version",
        "Accounting (sales tax)":
            "Accounting (Sales Tax)",
        "Broker Relations (broker fee)":
            "Broker Relations (Broker Fee)",
        "\u21bb Fetch from EVE":
            "\u21bb Aus EVE holen",
        "Find the best character automatically":
            "Besten Charakter automatisch finden",
        "Corp standing":
            "Corp-Standing",
        "Faction standing":
            "Fraktions-Standing",
        "Broker fee":
            "Broker Fee",
        "2 years":
            "2 Jahre",
        "1 year":
            "1 Jahr",
        "6 months":
            "6 Monate",
        "Market cache cleared \u2013 {size} freed.":
            "Markt-Cache geleert \u2013 {size} freigegeben.",
        "Reading skills & standings from EVE \u2026":
            "Lese Skills & Standings aus EVE \u2026",
        "Updated ({src}): ":
            "Aktualisiert ({src}): ",
        "Cancelled. Nothing was calculated.":
            "Abgebrochen. Nichts wurde berechnet.",
        "Operation cancelled.":
            "Vorgang abgebrochen.",
        "Gold search \u2026 mode {d}/{n}":
            "Gold-Suche \u2026 Modus {d}/{n}",
        "you are missing {m} of {n} positions":
            "{m} von {n} Positionen fehlen dir",
        "you already have {n} item(s)":
            "{n} Item(s) hast du bereits",
        "covered":
            "gedeckt",
        "partly":
            "teilweise",
        "missing entirely":
            "fehlt komplett",
        "{c} covered, {p} partly":
            "{c} gedeckt, {p} teilweise",
        "\u21b3 with {who}":
            "\u21b3 bei {who}",
        "Tick all":
            "Alle ankreuzen",
        "None":
            "Keine",
        "Tick only missing":
            "Nur fehlende ankreuzen",
        "{n} {what} copied \u2713":
            "{n} {what} kopiert \u2713",
        " \u2013 {n} skipped without a name":
            " \u2013 {n} ohne Namen ausgelassen",
        "Copy missing materials":
            "Fehlende Materialien kopieren",
        "Floor calculation \u00b7 {name}":
            "Boden-Rechnung \u00b7 {name}",
        "Show floor calculation":
            "Boden-Rechnung anzeigen",
        "Freight":
            "Fracht",
        "Searching structures in your open orders \u2026":
            "Suche Strukturen in deinen offenen Orders \u2026",
        "Structure \u201e{name}\u201c saved.":
            "Struktur \u201e{name}\u201c gespeichert.",
        "Structure error (access/scope/ID?): ":
            "Struktur-Fehler (Zugang/Scope/ID?): ",
        "Filter applied (cache, < 5 min old).":
            "Filter angewendet (Cache, < 5 Min alt).",
        "{n} arbitrage hits. ":
            "{n} Arbitrage-Treffer. ",
        "Buy at the source, sell at the destination. Click a column to sort.":
            "Kauf in Quelle, Verkauf im Ziel. Spaltenklick sortiert.",
        "   \u00b7   buy-order price \u2248 {isk} ISK":
            "   \u00b7   Buy-Order-Preis \u2248 {isk} ISK",
        " trades \u00b7 bought {b} \u00b7 sold {s} \u00b7 turnover balance {n}":
            " Trades \u00b7 gekauft {b} \u00b7 verkauft {s} \u00b7 Umsatz-Saldo {n}",
        "\u2192 active hub {hub}:  sales tax {tax} %  \u00b7  broker fee {broker} %":
            "\u2192 Aktiver Hub {hub}:  Sales Tax {tax} %  \u00b7  Broker Fee {broker} %",
        "Interface language. Item names always come from EVE and stay English.":
            "Sprache der Oberfl\u00e4che. Item-Namen kommen immer aus EVE und bleiben englisch.",
        "Invention total (all items): ":
            "Invention gesamt (alle Items): ",
        " ({n} in the hangar)":
            " ({n} im Hangar)",
        "  \u00b7  {n} attempts in total \u2192 ":
            "  \u00b7  {n} Versuche gesamt \u2192 ",
        "Invention time includes {pct}% structure rig bonus.":
            "Invention-Zeit enth\u00e4lt {pct}% Struktur-Rig-Bonus.",
        "enough \u2713":
            "genug \u2713",
        "still to build \u00b7 {n} units":
            "noch zu bauen \u00b7 {n} Stk",
        "partly \u2013 {n} still to buy":
            "teilweise \u2013 noch {n} kaufen",
        "{a} / {b} covered":
            "{a} / {b} gedeckt",
        "Also {n} too few: ":
            "Au\u00dferdem {n} zu wenig: ",
        "{n} starts on {cap} slots \u00b7 waves":
            "{n} Starts auf {cap} Slots \u00b7 Wellen",
        "{n}/{cap} slots":
            "{n}/{cap} Slots",
        "\u2753 could belong to another build plan":
            "\u2753 evtl. anderer Bauplan",
        "A job for this item is running - but \u201e{plan}\u201c claims it too. ESI does not say which build plan a job belongs to.":
            "F\u00fcr dieses Item l\u00e4uft ein Job - aber \u201e{plan}\u201c beansprucht es ebenfalls. ESI sagt nicht, zu welchem Bauplan ein Job geh\u00f6rt.",
        "Materials":
            "Materialien",
        "Run planner":
            "Runplaner",
        "Own BPC instead of invention":
            "Eigene BPC statt Invention",
        "Ignore cost \u2013 always build":
            "Kosten ignorieren \u2013 immer bauen",
        "Subtract assets":
            "Assets abziehen",
        "Load ESI ownership":
            "ESI-Besitz laden",
        "Create shopping list":
            "Einkaufsliste erstellen",
        "Copy blueprint name":
            "Blueprint-Name kopieren",
        "Copy all blueprint names":
            "Alle Blueprint-Namen kopieren",
        "Open in-game market":
            "Im Ingame-Markt \u00f6ffnen",
        "End product":
            "Endprodukt",
        "Redo":
            "Wiederholen",
        "Transport volume (shopping list, incl. buffer):":
            "Transportvolumen (Einkaufsliste, inkl. Puffer):",
        "Manufacturing":
            "Fertigung",
        "All meta":
            "Alle Meta",
        "Tech I (all)":
            "Tech I (gesamt)",
        "Base T1 (meta 0)":
            "Basis-T1 (Meta 0)",
        "Named/Compact (meta 1-4)":
            "Benannt/Compact (Meta 1-4)",
        "All tech levels":
            "Alle Tech-Stufen",
        "All buildable (T1\u2013T3)":
            "Alle baubaren (T1\u2013T3)",
        "{n} days":
            "{n} Tage",
        "Load recipe data?":
            "Rezeptdaten laden?",
        "For build planning the tool needs EVE's recipe data (about 140 MB, once).":
            "F\u00fcr die Bauplanung braucht das Werkzeug die EVE-Rezeptdaten (rund 140 MB, einmalig).",
        "Without it the Industry tab stays empty. You can load it later at any time with the \u201eEVE data\u201c button at the top right.":
            "Ohne sie bleibt der Industry-Reiter leer. Du kannst sie jederzeit sp\u00e4ter \u00fcber den Knopf \u201eEVE-Daten\u201c oben rechts laden.",
        "Setting up EVE Motor Market":
            "EVE Motor Market einrichten",
        "Without this data the tool stays empty. It takes a few minutes - you can leave the window open.":
            "Ohne diese Daten bleibt das Werkzeug leer. Es dauert ein paar Minuten \u2013 du kannst das Fenster offen lassen.",
        "Opens your browser. Log in with EVE and confirm the access.":
            "\u00d6ffnet deinen Browser. Melde dich bei EVE an und best\u00e4tige den Zugriff.",
        "Recipe data":
            "Rezeptdaten",
        "About 140 MB, once. Needed for every build plan.":
            "Etwa 140 MB, einmalig. F\u00fcr jeden Bauplan n\u00f6tig.",
        "Price histories":
            "Preisverl\u00e4ufe",
        "For the deal lists. Can also run later in the background.":
            "F\u00fcr die Deal-Listen. Kann auch sp\u00e4ter im Hintergrund laufen.",
        "Quit":
            "Beenden",
        "Closes the program. The setup starts again next time.":
            "Schlie\u00dft das Programm. Die Einrichtung beginnt beim n\u00e4chsten Mal von vorn.",
        "Start":
            "Starten",
        "linked \u2713":
            "verlinkt \u2713",
        "loaded \u2713":
            "geladen \u2713",
        "Waiting for the login in your browser \u2026":
            "Warte auf die Anmeldung im Browser \u2026",
        "Login failed: ":
            "Anmeldung fehlgeschlagen: ",
        "No character linked yet - please try again.":
            "Noch kein Charakter verlinkt \u2013 bitte nochmal.",
        "Downloading \u2026":
            "Lade herunter \u2026",
        "Download failed: ":
            "Download fehlgeschlagen: ",
        "Check your internet connection. \u201eQuit\u201c closes the program; the setup starts again next time.":
            "Pr\u00fcfe deine Internetverbindung. \u201eBeenden\u201c schlie\u00dft das Programm; die Einrichtung beginnt beim n\u00e4chsten Mal von vorn.",
        "Runs in the background once you start.":
            "L\u00e4uft im Hintergrund, sobald du startest.",
        "will run in the background \u2713":
            "l\u00e4uft im Hintergrund \u2713",
        "Everything ready.":
            "Alles bereit.",
        "Track via ESI":
            "Aus ESI \u00fcbernehmen",
        "Meaningful in every mode":
            "Tr\u00e4gt in jedem Modus",
        "Only meaningful in: {modes}":
            "Tr\u00e4gt nur in: {modes}",
        "Which columns are visible - the rest can be switched on.":
            "Welche Spalten sichtbar sind \u2013 der Rest ist zuschaltbar.",
        "Which columns are visible. Default: Build cost/unit, Profit/unit, ISK/h, Runs \u2013 the rest can be switched on.":
            "Welche Spalten sichtbar sind. Standard: Baukosten/Stk, Gewinn/Stk, ISK/Std, Runs \u2013 der Rest ist zuschaltbar.",
        "Excludes all containers from trading \u2013 their contents do not count towards stock, signals or profit.":
            "Schlie\u00dft alle Container vom Handel aus \u2013 ihr Inhalt z\u00e4hlt nicht zu Best\u00e4nden, Signalen und Gewinn.",
        "Pulls the 15 best hits (\u2605) to the top and pins them there. While active, clicking a column header (e.g. Volat. % or Profit/day) sorts ONLY these starred items \u2013 the others stay untouched below.":
            "Zieht die 15 besten Treffer (\u2605) nach oben und pinnt sie fest. Solange aktiv, sortiert ein Klick auf einen Spaltenkopf (z. B. Volatil. % oder Gewinn/Tag) NUR diese Stern-Items \u2013 die anderen bleiben unangetastet darunter.",
        "All five are genuine daytrading (buy cheap via buy order, sell higher via sell order) \u2013 they just hunt for different things:\n\u2022 Spread: the highest realistic profit per day.\n\u2022 Hour trader: items you reliably flip many times per hour (high tradability + margin).\n\u2022 Little competition: hardly any competitors, \u201eset & forget\u201c.\n\u2022 Niche: overlooked mid-sized items with a solid margin.\n\u2022 Capital efficiency: best profit/day per ISK tied up \u2013 ideal when your capital is tight and has to work as hard as possible.":
            "Alle f\u00fcnf sind echtes Daytrading (per Buy-Order billig kaufen, per Sell-Order teurer verkaufen) \u2013 sie jagen nur Unterschiedliches:\n\u2022 Spanne: der h\u00f6chste realistische Gewinn pro Tag.\n\u2022 Stunden-Trader: Items, die du zuverl\u00e4ssig viele Male pro Stunde umschl\u00e4gst (hohe Handelbarkeit + Marge).\n\u2022 Wenig Konkurrenz: kaum Mitbewerber, \u201eset & forget\u201c.\n\u2022 Nische: \u00fcbersehene mittelgro\u00dfe Items mit solider Marge.\n\u2022 Kapitaleffizienz: bester Gewinn/Tag pro gebundenem ISK \u2013 ideal, wenn dein Kapital knapp ist und maximal arbeiten soll.",
        "Only show items of this category (e.g. ships, modules, charges/ammo, drones). Needs the SDE data \u2013 run \u201eLoad recipes\u201c once.":
            "Nur Items dieser Kategorie zeigen (z. B. Schiffe, Module, Ladungen/Munition, Drohnen). Braucht die SDE-Daten \u2013 einmal \u201eBaurezepte laden\u201c.",
        "Purchase price unknown \u2013 this item was not bought on the market (loot, self-built, contract) or the purchase predates the transaction import. Hence \u201e\u2014\u201c. Run \u201eFetch transactions\u201c in the Characters tab and the margin appears.":
            "Kaufpreis unbekannt \u2013 dieses Item wurde nicht \u00fcber den Markt gekauft (Loot, selbst gebaut, Contract) oder der Kauf liegt vor dem Transaktions-Import. Darum \u201e\u2014\u201c. Im Charaktere-Tab \u201eTransaktionen holen\u201c, dann erscheint die Marge.",
        "You have both a buy order and a sell order running for this item.":
            "Du hast f\u00fcr dieses Item sowohl eine Kauf- als auch eine Verkaufs-Order laufen.",
        "No purchase price known - cannot be calculated.":
            "Kein Kaufpreis bekannt - kann nicht berechnet werden.",
        "Sell order listed \u2013 waiting for a buyer.":
            "Verkaufs-Order gelistet \u2013 wartet auf einen K\u00e4ufer.",
        "Buy order running \u2013 waiting for someone to sell to you.":
            "Kauf-Order l\u00e4uft \u2013 wartet, dass jemand an dich verkauft.",
        "Filter by meta class: Tech I (standard), Tech II, Tech III, Storyline, Faction, Officer, Deadspace, Abyssal \u2026 Needs the SDE data \u2013 run \u201eLoad blueprints\u201c once. Every item has exactly one meta class.":
            "Nach Meta-Klasse filtern: Tech I (Standard), Tech II, Tech III, Storyline, Faction, Officer, Deadspace, Abyssal \u2026 Braucht die SDE-Daten \u2013 einmal \u201eBaurezepte laden\u201c. Jedes Item hat genau eine Meta-Klasse.",
        "Minimum profit per day = profit/unit \u00d7 daily volume. The most important figure: it catches cheap bulk goods with huge volume just as well as expensive items with small volume. 0 = off.":
            "Mindest-Gewinn pro Tag = Gewinn/Stk \u00d7 Tagesvolumen. Die wichtigste Kennzahl: erfasst billige Massenware mit Riesenvolumen genauso wie teure Items mit kleinem Volumen. 0 = aus.",
        "Flip: buy cheap via buy order, sell higher via sell order (station trading).\nUndervalued: buy from sell orders when below the \u00d8 price of the time window.\nBargain: sudden price crash with a volume spike (someone dumped).\nWorth building: produce and sell at a profit \u2013 the sell price is above the estimated build cost (buildable items only: ships, modules, ammo, drones; no ores/reactions).":
            "Flip: im Buy-Order billig rein, per Sell-Order teurer raus (Station-Trading).\nUnterbewertet: Sell-Order kaufen, wenn unter dem \u00d8-Preis des Zeitfensters.\nSchn\u00e4ppchen: pl\u00f6tzlicher Preis-Crash mit Volumen-Spike (jemand hat gedumpt).\nLohnt sich zu bauen: produzieren und mit Gewinn verkaufen \u2013 Verkaufspreis liegt \u00fcber den gesch\u00e4tzten Baukosten (nur baubare Items: Schiffe, Module, Munition, Drohnen; keine Erze/Reaktionen).",
        "Minimum trade volume per day. Filters out items hardly anyone trades.":
            "Mindest-Handelsvolumen pro Tag. Filtert Items raus, die kaum jemand handelt.",
        "Minimum return on the ISK invested (profit/outlay).":
            "Mindest-Rendite auf das eingesetzte ISK (Gewinn/Einsatz).",
        "Only items up to this sell price (0 = no upper limit).":
            "Nur Items bis zu diesem Sell-Preis (0 = keine Obergrenze).",
        "Optional: how much ISK you want to trade here. Hides markets too thin to absorb your capital (you would move the price yourself otherwise). 0 = no filter.":
            "Optional: Wie viel ISK du hier handeln m\u00f6chtest. Blendet M\u00e4rkte aus, die zu d\u00fcnn sind, um dein Kapital aufzunehmen (du w\u00fcrdest sonst den Preis selbst bewegen). 0 = kein Filter.",
        "Opens the item in the in-game market.":
            "\u00d6ffnet das Item im Ingame-Markt.",
        "Pulls the 15 best candidates (\u2605) to the top and pins them there. While active, clicking a column header sorts ONLY these starred items \u2013 the others stay untouched below.":
            "Zieht die 15 besten Kandidaten (\u2605) nach oben und pinnt sie fest. Solange aktiv, sortiert ein Klick auf einen Spaltenkopf NUR diese Stern-Items \u2013 die anderen bleiben unangetastet darunter.",
        "All three are holding strategies (buy and wait for recovery):\n\u2022 Below \u00d8: the item trades below its historical average and will probably return there.\n\u2022 Price crash: the item has just dropped sharply \u2013 you bet on the recovery.\n\u2022 Below build cost: the item sells for less than it costs to build \u2013 in the long run the price rises towards production cost. Needs \u201eLoad blueprints\u201c.":
            "Alle drei sind Halte-Strategien (kaufen und auf Erholung warten):\n\u2022 Unter \u00d8: Item handelt unter seinem historischen Durchschnitt und kehrt vermutlich dorthin zur\u00fcck.\n\u2022 Preis-Crash: Item ist gerade stark abgest\u00fcrzt \u2013 du wettest auf die Erholung.\n\u2022 Unter Baupreis: Item wird billiger verkauft, als es zu bauen kostet \u2013 der Preis steigt langfristig Richtung Produktionskosten. Braucht \u201eBaurezepte laden\u201c.",
        "How far below its normal level the item must be at least to count as a buy candidate.":
            "Wie weit das Item mindestens unter seinem Normalniveau liegen muss, um als Kauf-Kandidat zu gelten.",
        "Minimum daily volume \u2013 so you can actually sell the quantity again.":
            "Mindest-Tagesvolumen \u2013 damit du die Menge auch wieder verkauft bekommst.",
        "Target price = normal level the price is expected to recover to (for \u201eBelow build cost\u201c: the build cost). This is where you sell.":
            "Zielpreis = Normalniveau, auf das sich der Preis voraussichtlich erholt (bei \u201eUnter Baupreis\u201c die Baukosten). Hier verkaufst du.",
        "ROUGH estimate until recovery to the target level (discount \u00f7 current upward pace). \u201e?\u201c = only a weak/sideways drift, so especially uncertain. Falling items show \u201e\u2014\u201c (no recovery pace). Just a hint, no guarantee.":
            "GROBE Sch\u00e4tzung bis zur Erholung aufs Zielniveau (Rabatt \u00f7 aktuellem Aufw\u00e4rtstempo). \u201e?\u201c = nur schwacher/seitw\u00e4rts-Drift, also besonders unsicher. Bei fallenden Items steht \u201e\u2014\u201c (kein Erholungstempo). Nur ein Anhaltspunkt, keine Garantie.",
        "Remove individual items completely from the build plan \u2013 copy the names from the game, one item per line. They disappear from the recipe structure, build order and run planner \u2013 automatically, a moment after you stop typing.":
            "Einzelne Items komplett aus dem Bauplan nehmen \u2013 Namen aus dem Spiel kopieren, ein Item pro Zeile. Verschwinden aus Rezept-Struktur, Bau-Reihenfolge und Runplaner \u2013 automatisch, kurz nachdem du aufh\u00f6rst zu tippen.",
        "Ticked = the datacore quantities worked out in the Invention tab (at the number of attempts shown there) go into the shopping list when you click \u201eShopping list\u201c below.":
            "Angehakt = die im Invention-Tab ermittelten Datacore-Mengen (bei der jeweils angezeigten Versuchszahl) wandern mit in die Einkaufsliste, wenn du unten auf \u201eEinkaufswagen\u201c klickst.",
        "Ticked = the decryptor quantities worked out in the Invention tab go into the shopping list when you click \u201eShopping list\u201c below (not with \u201eNo decryptor\u201c).":
            "Angehakt = die im Invention-Tab ermittelten Decryptor-Mengen wandern mit in die Einkaufsliste, wenn du unten auf \u201eEinkaufswagen\u201c klickst (nicht bei \u201eKein Decryptor\u201c).",
        "Manufacturing time implant (Zainou 'Beancounter' Industry BX-80X). Detected automatically via ESI (button below) or chosen by hand.":
            "Fertigungszeit-Implantat (Zainou 'Beancounter' Industry BX-80X). Per ESI automatisch erkennbar (Button unten) oder manuell w\u00e4hlen.",
        "Fetches the manufacturing/reaction skills of every character from ESI and shows the parallel job slots (for the run planner).":
            "Holt die Fertigungs-/Reaktions-Skills jedes Charakters aus ESI und zeigt die parallelen Job-Slots (f\u00fcr den Runplaner).",
        "Detects automatically which of the plugged-in implants are manufacturing time bonus implants (Zainou 'Beancounter' Industry BX-80X). Needs the implant scope (Settings \u2192 'Implant manufacturing bonus' \u2192 On + relink).":
            "Erkennt automatisch, welche der eingesteckten Implantate ein Fertigungszeit-Bonus-Implantat sind (Zainou 'Beancounter' Industry BX-80X). Braucht den Implantat-Scope (Einstellungen \u2192 'Implantat-Fertigungsbonus' \u2192 An + neu verkn\u00fcpfen).",
        "Recalculates the run planner with the changed character selection.\nThe selection itself is already saved \u2013 the calculation only happens here, so the tool does not recalculate on every click while you change several ticks.":
            "Rechnet den Runplaner mit der ge\u00e4nderten Charakter-Auswahl neu.\nDie Auswahl selbst ist schon gespeichert \u2013 gerechnet wird erst hier, damit das Tool beim Umstellen mehrerer Kreuze nicht bei jedem Klick neu rechnet.",
        "Checks via ESI whether you have meanwhile built exactly the planned quantity (completed manufacturing jobs of all linked characters since the plan was saved). Runs once automatically when this page opens - button for a manual re-check.":
            "Pr\u00fcft \u00fcber ESI, ob du die geplante St\u00fcckzahl inzwischen exakt fertig gebaut hast (abgeschlossene Fertigungs-Jobs aller verkn\u00fcpften Charaktere seit dem Speichern des Plans). L\u00e4uft einmalig automatisch beim \u00d6ffnen dieser Seite - Knopf f\u00fcr einen manuellen Neu-Check.",
        "Filter by blueprint name - suggestions appear while typing.":
            "Nach Blueprint-Namen filtern - Vorschl\u00e4ge erscheinen beim Tippen.",
        "Additionally shows (violet) T2 blueprints you CAN build from your T1 blueprints via invention - with cost/profit including the expected invention cost. T2 you already own are not listed twice.":
            "Zeigt zus\u00e4tzlich (violett) T2-Blueprints, die du aus deinen T1-Blueprints per Invention bauen KANNST - mit Kosten/Gewinn inklusive Invention-Erwartungswert. Schon besessene T2 werden nicht doppelt gelistet.",
        "Only show blueprints of one specific linked character.":
            "Nur Blueprints eines bestimmten verkn\u00fcpften Charakters anzeigen.",
        "Additionally shows (red, at the bottom) blueprints matching the current category/tech selection that you do NOT own - e.g. category \u201eShips\u201c + \u201eTech I\u201c ticked: you see at once which T1 ship blueprints you are still missing. A category must be selected; without one the list would be endless, so it is capped.":
            "Zeigt zus\u00e4tzlich (rot, unten) Blueprints, die zur aktuellen Kategorie/Tech-Auswahl passen, die du aber NICHT besitzt - z.B. Kategorie \u201eSchiffe\u201c + \u201eTech I\u201c angehakt: du siehst sofort, welche T1-Schiffs-Blueprints dir noch fehlen. Eine Kategorie muss ausgew\u00e4hlt sein; ohne sie w\u00e4re die Liste endlos, deshalb ist sie gedeckelt.",
        "Searches your assets and orders for the real EVE structures and assigns them automatically to the build structures above \u2013 by name, without you having to pick anything.\nOnly after that does \u201e Deduct assets\u201c in the build plan count the material lying at these structures.\nTakes 10\u201320 s (ESI). Assigned only on an UNAMBIGUOUS name match \u2013 a wrong place would count foreign material as available.":
            "Sucht in deinen Assets und Orders nach den echten EVE-Strukturen und ordnet sie automatisch den Bau-Strukturen oben zu \u2013 \u00fcber den Namen, ohne dass du etwas ausw\u00e4hlen musst.\nErst danach z\u00e4hlt \u201e Assets abziehen\u201c im Bauplan das Material, das an diesen Strukturen liegt.\nDauert 10\u201320 s (ESI). Zugeordnet wird nur bei EINDEUTIGEM Namenstreffer \u2013 ein falscher Ort w\u00fcrde fremdes Material als vorhanden z\u00e4hlen.",
        "Link this build structure to its real EVE structure so that \u201eDeduct assets\u201c only counts material that really lies HERE (not in Jita or elsewhere). The list comes from your known structures \u2013 if one is missing, add it in the hub/structure area at the top.":
            "Verkn\u00fcpfe diese Bau-Struktur mit ihrer echten EVE-Struktur, damit \u201eAssets abziehen\u201c nur das Material z\u00e4hlt, das wirklich HIER liegt (nicht in Jita o.\u00e4.). Die Liste kommt aus deinen bekannten Strukturen \u2013 fehlt eine, f\u00fcge sie oben im Hub/Struktur-Bereich hinzu.",
        "RESERVE stock for this plan: its material consumption (purchases + stock coverage + invention) is deducted from the stock of all OTHER build plans \u2013 so plan 2 does not count the purchases of plan 1 as free. The plan itself still sees its stock in full.":
            "Bestand f\u00fcr diesen Plan RESERVIEREN: sein Material-Verbrauch (Einkauf + Bestandsdeckung + Invention) wird bei allen ANDEREN Bauplaenen vom Bestand abgezogen \u2013 damit Plan 2 nicht die Einkaeufe von Plan 1 als frei z\u00e4hlt. Der Plan selbst sieht seinen Bestand weiterhin voll.",
        "rows only: the decryptor with the highest profit/unit - compared across all options (incl. \u201eNo decryptor\u201c) with a real plan calculation. The row's build cost/profit include it.":
            "Nur -Zeilen: der Decryptor mit dem h\u00f6chsten Gewinn/Stk - per echter Plan-Rechnung \u00fcber alle Optionen (inkl. \u201eKein Decryptor\u201c) verglichen. Baukosten/Gewinn der Zeile rechnen MIT ihm.",
        "rows only: the matching optimal quantity = a full BPC batch (base runs + the decryptor's run modifier) x output/run. Invention cost and batch rounding are spread fairly over this quantity - smaller quantities cost more per unit.":
            "Nur -Zeilen: die dazu passende optimale St\u00fcckzahl = voller BPC-Batch (Basis-Runs + Run-Mod des Decryptors) x Output/Run. Auf dieser Menge sind Invention-Kosten und Batch-Rundung fair verteilt - kleinere Mengen sind pro St\u00fcck teurer.",
        "This plan was marked as completed BY HAND \u2013 regardless of what the ESI finished check counts (e.g. because the invention did not cover every unit).":
            "Dieser Plan wurde MANUELL als abgeschlossen markiert \u2013 unabh\u00e4ngig davon, was der ESI-Fertig-Check z\u00e4hlt (z.B. weil die Invention nicht f\u00fcr alle St\u00fcck gereicht hat).",        "Cannot be estimated \u2013 e.g. no market price for this item.":
            "Nicht sch\u00e4tzbar \u2013 z.B. kein Marktpreis f\u00fcr dieses Item.",
        "Frozen plan: material costs from the frozen state, sale at the last market scan.":
            "Eingefrorener Plan: Materialkosten aus dem Einfrier-Stand, Verkauf zum letzten Markt-Scan.",
        "Tax the OWNER of this structure charges on industry jobs.\nIn game: Show Info on the structure.\nOwn structure usually 0 %, foreign 1-5 %.\nEnters the job cost as EIV \u00d7 (facility tax + 4 % SCC) - does NOT come from ESI, so it has to be entered here. Left empty, the value from Setup applies.":
            "Steuer, die der BESITZER dieser Struktur auf Industrie-Jobs erhebt.\nIm Spiel: Show Info auf die Struktur.\nEigene Struktur meist 0 %, fremde 1-5 %.\nGeht als EIV \u00d7 (Facility-Tax + 4 % SCC) in die Job-Kosten ein - kommt NICHT aus ESI, muss also hier stehen. Leer gelassen gilt der Wert aus Setup.",
        "Optional: how much ISK you want to collect here. Hides markets too thin to absorb your capital over a holding horizon (you would buy the price up yourself otherwise). 0 = no filter.":
            "Optional: Wie viel ISK du hier einsammeln m\u00f6chtest. Blendet M\u00e4rkte aus, die zu d\u00fcnn sind, um dein Kapital \u00fcber einen Halte-Horizont aufzunehmen (du w\u00fcrdest sonst den Preis selbst hochkaufen). 0 = kein Filter.",
        "Ticks exactly those whose stock does NOT cover the demand (yellow + red) - the usual case.":
            "Kreuzt genau die an, deren Bestand den Bedarf NICHT deckt (gelb + rot) - der \u00fcbliche Fall.",
        "Highlights the 15 best trip candidates (by profit/m\u00b3) with \u2605 and pins them at the top.":
            "Hebt die 15 besten Fuhren-Kandidaten (nach Gewinn/m\u00b3) mit \u2605 hervor und pinnt sie oben.",
        "Only items up to this purchase price (0 = no upper limit).":
            "Nur Items bis zu diesem Kaufpreis (0 = keine Obergrenze).",
        "Safety margin on every copied quantity \u2013 e.g. 5 %, so a wrong purchase or rounding loss does not immediately force a second shopping trip.\nThis is THE SAME buffer as below in the build plan and in the shopping list (setting \u201ebau_buy_surplus\u201c) \u2013 changed here, it applies there too.":
            "Sicherheitsaufschlag auf jede kopierte Menge \u2013 z.B. 5 %, damit ein Fehlkauf oder Rundungsverlust nicht gleich einen zweiten Einkauf noetig macht.\nDies ist DERSELBE Puffer wie unten im Bauplan und im Einkaufswagen (Einstellung \u201ebau_buy_surplus\u201c) \u2013 hier geaendert gilt er auch dort.",
        "Only what the PLAN does not cover \u2013 the actual shopping list. If the top says \u201e0 to buy\u201c, there is nothing to copy here (built/covered does not count as missing).":
            "Nur was der PLAN nicht deckt \u2013 die eigentliche Einkaufsliste. Steht oben \u201e0 zu kaufen\u201c, gibt es hier nichts zu kopieren (gebaut/gedeckt z\u00e4hlt nicht als Fehlmenge).",
        "\u26a0 Suspected dump: the price drop came with MASSIVELY increased volume (\u22652.5x median) - that smells like a real revaluation (patch/meta), not a dip. The old price often does NOT come back then. The rating is already strongly dampened.":
            "\u26a0 Dump-Verdacht: Der Preissturz lief bei MASSIV erh\u00f6htem Volumen (\u22652.5x Median) - das riecht nach echter Neubewertung (Patch/Meta), nicht nach Dip. Der alte Preis kommt dann oft NICHT zur\u00fcck. Wertung ist bereits stark ged\u00e4mpft.",
        "The window's normal price was distorted upwards by a short spike (user case: outlier months ago, decay phase inside the window). The target was secured to the yearly baseline (median of the full history) - the expectation is honest accordingly.":
            "Der Fenster-Normalpreis war durch einen Kurz-Spike nach oben verzerrt (Nutzer-Fall: Ausrei\u00dfer vor Monaten, Abkling-Phase im Fenster). Ziel wurde auf die Jahres-Basislinie (Median der vollen Historie) abgesichert - Erwartung ist entsprechend ehrlich.",
        "S % = sell exit evidence at the DESTINATION: share of the spread the daily highs there reach on average towards the sell order. High = your sell order at the destination is realistically served; low = trading only happens on the buy side \u2013 you would sit on the goods.":
            "S % = Sell-Exit-Beleg am ZIEL: Anteil des Spreads, den die Tages-Hochs dort im Schnitt Richtung Sell-Order erreichen. Hoch = deine Sell-Order am Ziel wird realistisch bedient; niedrig = Handel findet nur an der Buy-Seite statt \u2013 du s\u00e4\u00dfest auf der Ware.",
        "Hardly anything is traded here at the destination \u2013 careful, it may not sell.":
            "Im Ziel wird hier kaum/nichts gehandelt \u2013 Vorsicht, bleibt evtl. liegen.",
        "Copies build plan/swing/manual items (name + quantity) as multibuy for instant purchase from sell orders. Daytrade items are deliberately NOT copied \u2013 they need their own, cheaper buy order instead of buying instantly at the sell price.":
            "Kopiert Bauplan-/Swing-/manuelle Items (Name + Menge) als Multibuy f\u00fcr den Sofortkauf aus Sell-Orders. Daytrade-Items werden bewusst NICHT mitkopiert \u2013 die brauchen eine eigene, g\u00fcnstigere Buy-Order statt sofort zum Sell-Preis zu kaufen.",
        "Sets the quantity suggested by daily volume for all daytrade items (your realistic daily share). Items without a suggestion (manual/swing) stay unchanged.":
            "Setzt f\u00fcr alle Daytrade-Items die nach Tagesvolumen vorgeschlagene Menge (dein realistischer Tagesanteil). Items ohne Vorschlag (manuell/Swing) bleiben unver\u00e4ndert.",
        "On: the \u201eNext\u201c button opens every open shopping item in game one after the other and copies the buy order price. Buying/placing the order is up to you.":
            "An: der \u201eN\u00e4chste\u201c-Knopf \u00f6ffnet der Reihe nach jedes offene Einkaufs-Item ingame und kopiert den Buy-Order-Preis. Kauf/Order setzen machst du selbst.",
        "Opens the next open shopping item in game and copies the buy order price.":
            "\u00d6ffnet das n\u00e4chste offene Einkaufs-Item ingame und kopiert den Buy-Order-Preis.",
        "How much of the daily traded volume you want to grab with your buy order. ~25 % \u2248 fills in about a day if you stay top bidder \u2013 that keeps your capital moving. Higher = more at once, but it takes longer until everything is filled and sold again.":
            "Wie viel des t\u00e4glich gehandelten Volumens du mit deiner Buy-Order greifen willst. ~25 % \u2248 f\u00fcllt in etwa einem Tag, wenn du H\u00f6chstbieter bleibst \u2013 so bleibt dein Kapital in Bewegung. H\u00f6her = mehr auf einmal, dauert aber l\u00e4nger bis alles gef\u00fcllt und wieder verkauft ist.",
        "This item is already in the shopping list. Change the quantity there or remove the item to add it again.":
            "Dieses Item liegt bereits im Einkaufswagen. Menge dort \u00e4ndern oder Item entfernen, um es erneut aufzunehmen.",
        "Buy order price to the clipboard \u2013 paste it into the price field of the buy order in game (outbids the best buy by exactly one valid EVE tick \u2192 you are the top bidder).":
            "Buy-Order-Preis ins Clipboard \u2013 im Spiel ins Preisfeld der Kauf-Order einf\u00fcgen (\u00fcberbietet den besten Buy um genau einen g\u00fcltigen EVE-Tick \u2192 du bist H\u00f6chstbieter).",
        "Click = copy quantity \u00b7 double-click = change quantity":
            "Klick = Menge kopieren \u00b7 Doppelklick = Menge \u00e4ndern",
        "Remove from the shopping list.":
            "Aus der Einkaufsliste entfernen.",
        "Click copies this price \u2013 paste it into the price field of the buy order in game and you are the top bidder.":
            "Klick kopiert diesen Preis \u2013 im Spiel ins Preisfeld der Kauf-Order einf\u00fcgen, dann bist du H\u00f6chstbieter.",
        "Buy instantly, sell via sell order (after tax + broker on the selling side).":
            "Sofort kaufen, per Verkaufs-Order raus (nach Steuer + Broker auf der Verkaufsseite).",
        "Profit in ISK: buy instantly from the sell orders, sell via your own sell order (tax + broker on the selling side). Quantity \u00d7 (net sale \u2212 instant purchase).":
            "Gewinn in ISK: sofort aus den Sell-Orders kaufen, per eigener Verkaufs-Order raus (Steuer + Broker auf der Verkaufsseite). Menge \u00d7 (Netto-Verkauf \u2212 Sofortkauf).",
        "Fetches the current sell prices from the market (Jita) and recalculates the sale price column from them. Without this the list uses the possibly outdated portfolio prices.":
            "Holt die aktuellen Sell-Preise aus dem Markt (Jita) und rechnet die Verkaufspreis-Spalte daraus neu. Ohne das rechnet die Liste mit den evtl. veralteten Portfolio-Preisen.",
        "Copies \u201eitem name sale price\u201c per line in the format EVE's sell window expects. There choose \u201eImport prices from clipboard (Decimal Point)\u201c \u2013 all prices are set at once.":
            "Kopiert \u201eItemname Verkaufspreis\u201c je Zeile im Format, das EVEs Verkaufsfenster erwartet. Dort dann \u201eImport prices from clipboard (Decimal Point)\u201c w\u00e4hlen \u2013 alle Preise werden auf einmal gesetzt.",
        "Clears the display and resets the ticks. \u201eRefresh\u201c fills it again from the portfolio.":
            "Leert die Anzeige und setzt die Haken zur\u00fcck. \u201eAktualisieren\u201c f\u00fcllt sie wieder aus dem Portfolio.",
        "ON: shows ALL bought items (without an open buy order - so the stack is complete) at the price that achieves your set target margin on the average buy price. Where the market is HIGHER than that target price, the row uses the market price instead (one tick below the cheapest sell) and is marked in cyan - at the target price you would have given that difference away. Set once, wait. OFF: normal list (status \u201e\u25cf SELL\u201c, price = undercut of the current market).":
            "AN: zeigt ALLE gekauften Items (ohne offene Kauf-Order - der Stack ist also komplett) zu dem Preis, der deine eingestellte Ziel-Marge auf den \u00d8-Einkaufspreis erzielt. Wo der Markt H\u00d6HER liegt als dieser Ziel-Preis, nimmt die Zeile stattdessen den Marktpreis (einen Tick unter dem billigsten Sell) und ist cyan markiert - zum Ziel-Preis h\u00e4ttest du die Differenz verschenkt. Einmal einstellen, abwarten. AUS: normale Liste (Status \u201e\u25cf VERKAUFEN\u201c, Preis = Undercut des aktuellen Marktes).",
        "Rebuilds the list from the portfolio: all positions marked SELL there that no longer have an open buy order.\nNeeds no network \u2013 purely from the existing data.":
            "Baut die Liste neu aus dem Portfolio auf: alle Positionen, die dort als VERKAUFEN markiert sind und keine offene Kauf-Order mehr haben.\nBraucht kein Netz \u2013 rein aus den vorhandenen Daten.",
        "Fetches the cheapest sell price at the ACTIVE hub (selectable at the top, player structures included) for every pasted line and puts \u201eitem name price\u201c on the clipboard \u2013 one tick below, so you are at the very top.\nThen in EVE's sell window choose \u201eImport prices from clipboard (Decimal Point)\u201c.":
            "Holt f\u00fcr jede eingef\u00fcgte Zeile den billigsten Sell-Preis am AKTIVEN Hub (oben w\u00e4hlbar, Player-Strukturen inklusive) und legt \u201eItemname Preis\u201c in die Zwischenablage \u2013 einen Tick darunter, damit du ganz oben stehst.\nIn EVE dann im Verkaufsfenster \u201eImport prices from clipboard (Decimal Point)\u201c w\u00e4hlen.",
        "Number of item rows in this list - for a quick cross-check: if you drag more or fewer items into the sell window in game than are listed here, that explains a deviation in the total proceeds without any price being calculated wrongly.":
            "Anzahl Item-Zeilen in dieser Liste - zum schnellen Gegenchecken: ziehst du ingame mehr oder weniger Items ins Verkaufsfenster, als hier aufgef\u00fchrt sind, erkl\u00e4rt das eine Abweichung beim Gesamterl\u00f6s, ohne dass ein Preis falsch berechnet w\u00e4re.",
        "Tick off as done \u2013 strikes the item through.":
            "Als erledigt abhaken \u2013 streicht das Item durch.",
        "Sale price to the clipboard \u2013 paste it into the price field of the sell order in game.":
            "Verkaufspreis ins Clipboard \u2013 im Spiel ins Preisfeld der Verkaufs-Order einf\u00fcgen.",
        "You already have an open sell order for this item in game. (Double-click copies the name.)":
            "Du hast f\u00fcr dieses Item bereits eine offene Sell-Order ingame. (Doppelklick kopiert den Namen.)",
        "Double-click copies the name \u2013 for searching in the inventory.":
            "Doppelklick kopiert den Namen \u2013 zum Suchen im Inventar.",
        "Click copies this price \u2013 paste it into the price field of the sell order (undercuts the best sell by exactly one valid EVE tick).":
            "Klick kopiert diesen Preis \u2013 ins Preisfeld der Verkaufs-Order einf\u00fcgen (unterbietet den besten Sell um genau einen g\u00fcltigen EVE-Tick).",
        "Click copies this price \u2013 it achieves exactly your target margin on the average buy price, regardless of the current market price.":
            "Klick kopiert diesen Preis \u2013 er erzielt genau deine Ziel-Marge auf den \u00d8-Einkaufspreis, unabh\u00e4ngig vom aktuellen Marktpreis.",
        # MARKT STATT ZIEL (Nutzer-Wunsch 22.09.2026): der Markt liegt
        # hoeher als die Ziel-Marge - dann waere der Ziel-Preis geschenkt.
        "MARKET INSTEAD OF TARGET: the cheapest sell at the hub is higher than your target price, so selling at the target price would give away the difference. This price undercuts the market by one tick \u2013 it sells just as fast and earns MORE than your target margin.":
            "MARKT STATT ZIEL: der billigste Sell am Hub liegt H\u00d6HER als dein Ziel-Preis \u2013 zum Ziel-Preis w\u00fcrdest du die Differenz verschenken. Dieser Preis unterbietet den Markt um einen Tick: er verkauft genauso schnell und bringt MEHR als deine Ziel-Marge.",
        "No purchase price known \u2013 profit cannot be calculated.":
            "Kein Einkaufspreis bekannt \u2013 Gewinn nicht berechenbar.",
        "Fetches your open orders and the current market prices and marks where you have been outbid/undercut.\nNote: EVE caches your orders for up to ~20 min \u2013 orders you just changed may still show \u201eoutbid\u201c until the cache refreshes.":
            "Holt deine offenen Orders und die aktuellen Marktpreise und markiert, wo du \u00fcberboten/unterboten wurdest.\nHinweis: EVE cached deine Orders bis ~20 Min \u2013 gerade ge\u00e4nderte zeigen evtl. noch \u201e\u00fcberboten\u201c, bis der Cache auffrischt.",
        "On: the \u201eNext\u201c button opens every order that needs repricing in game one after the other and copies the new price. \u201eModify\u201c/pasting is up to you \u2013 EVE does not allow orders to be changed automatically from outside.":
            "An: der \u201eN\u00e4chste\u201c-Knopf \u00f6ffnet der Reihe nach jede nachzubessernde Order ingame und kopiert den neuen Preis. Das \u201e\u00c4ndern\u201c/Einf\u00fcgen machst du selbst \u2013 EVE erlaubt keine automatische Order-\u00c4nderung von au\u00dfen.",
        "Opens the next order that needs repricing in game and copies the new price.":
            "\u00d6ffnet die n\u00e4chste nachzubessernde Order ingame und kopiert den neuen Preis.",
        "Only check the orders of this character (you change orders per character in game anyway). \u201eOpen\u201c opens the market at this character.":
            "Nur die Orders dieses Charakters pr\u00fcfen (Orders \u00e4nderst du ingame ohnehin pro Charakter). \u201e\u00d6ffnen\u201c \u00f6ffnet den Markt bei diesem Charakter.",
        "How often this order has already been repriced via \u201e\u25b6 Work-through mode\u201c. Every repricing costs a broker fee again (Advanced Broker Relations lowers it but does not make it free) - after many repricings in a row, pushing further is often no longer worth it even if the single-step check above still shows \u201eok\u201c. Right-click a row to undo a misclick.":
            "Wie oft diese Order schon \u00fcber den \u201e\u25b6 Abarbeiten-Modus\u201c nachgebessert wurde. Jede Nachbesserung kostet erneut Broker-Geb\u00fchr (Advanced Broker Relations senkt sie, macht sie aber nicht kostenlos) - bei vielen Nachbesserungen in Folge lohnt sich das Weiterschieben oft nicht mehr, auch wenn der Einzelschritt-Check oben noch \u201eok\u201c zeigt. Rechtsklick auf eine Zeile, um einen Fehlklick r\u00fcckg\u00e4ngig zu machen.",
        "Fetches the latest transactions directly from EVE (bypasses the 30-minute throttle). Note: EVE itself only updates the wallet about once an hour.":
            "Holt die neuesten Transaktionen direkt aus EVE (umgeht die 30-Minuten-Drosselung). Hinweis: EVE selbst aktualisiert das Wallet nur etwa st\u00fcndlich.",
        "Exports the currently filtered transactions as a CSV file \u2013 stores nothing permanently in the app.":
            "Exportiert die aktuell gefilterten Transaktionen als CSV-Datei \u2013 speichert nichts dauerhaft in der App.",
        "Detects plugged-in manufacturing time implants (Zainou 'Beancounter' Industry BX-80X) via ESI and includes their bonus in the build time. Needs a new login (new scope) - visible afterwards under 'Build characters' in the build plan.":
            "Erkennt per ESI eingesteckte Fertigungszeit-Implantate (Zainou 'Beancounter' Industry BX-80X) und rechnet deren Bonus in die Bauzeit ein. Braucht einen erneuten Login (neuer Scope) - danach im Bauplan bei 'Bau-Charaktere' sichtbar.",
        "NET margin (after tax + broker of your order character) IF you reprice to the new price \u2013 i.e. undercut the best sell.":
            "NETTO-Marge (nach Steuer + Broker deines Order-Charakters), WENN du auf den neuen Preis nachbesserst \u2013 also den besten Sell unterbietest.",
        "Copy the new price \u2013 paste it into \u201eModify order\u201c in game.":
            "Neuen Preis kopieren \u2013 ingame in \u201eOrder \u00e4ndern\u201c einf\u00fcgen.",
        "No journal data yet \u2013 run \u201eRefresh\u201c once, then the real fees are collected.":
            "Noch keine Journal-Daten \u2013 einmal \u201eAktualisieren\u201c ausf\u00fchren, dann werden die echten Geb\u00fchren gesammelt.",
        "Key of your ESI app from developers.eveonline.com. Enter once, enables the login.":
            "Schl\u00fcssel deiner ESI-App von developers.eveonline.com. Einmal eintragen, erm\u00f6glicht den Login.",
        "From this net margin upwards the portfolio marks a position as ready to sell (SELL).":
            "Ab dieser Netto-Marge markiert das Portfolio eine Position als verkaufsbereit (SELL).",
        "Queries the latest release in the GitHub repository and compares it with the running version. Does NOT check the EVE data \u2013 the \u201eUpdates\u201c button at the top right does that.":
            "Fragt die neueste Ver\u00f6ffentlichung im GitHub-Repository ab und vergleicht sie mit der laufenden Fassung. Pr\u00fcft NICHT die EVE-Daten \u2013 das macht der \u201eUpdates\u201c-Knopf oben rechts.",
        "Character whose skills & standings are read.":
            "Charakter, aus dem Skills & Standings gelesen werden.",
        "Reads Accounting, Broker Relations and your standings directly from EVE and fills the fields automatically. Needs the scopes esi-skills + esi-characters \u2013 log in again once if necessary.":
            "Liest Accounting, Broker Relations und deine Standings direkt aus EVE und f\u00fcllt die Felder automatisch. Braucht die Scopes esi-skills + esi-characters \u2013 ggf. einmal neu einloggen.",
        "Reads Accounting + Broker Relations + standings of ALL linked characters from EVE and automatically picks the one with the lowest fees at the active hub (sales tax + broker fee combined) - in case you have several characters and no longer know which one is best skilled for trading.":
            "Liest Accounting + Broker Relations + Standings ALLER verkn\u00fcpften Charaktere aus EVE und \u00fcbernimmt automatisch den, der im aktiven Hub die niedrigsten Geb\u00fchren (Sales Tax + Broker Fee zusammen) ergibt - falls du mehrere Charaktere hast und nicht mehr wei\u00dft, welcher am besten f\u00fcrs Traden geskillt ist.",
        "Your Accounting skill level (0\u20135). Lowers the sales tax by 11 % per level: 7.5 % \u2192 3.375 % at level 5.":
            "Dein Accounting-Skill-Level (0\u20135). Senkt die Sales Tax um 11 % pro Level: 7,5 % \u2192 3,375 % bei Level 5.",
        "Your Broker Relations level (0\u20135). Lowers the broker fee by 0.3 % per level: 3 % \u2192 1.5 % at level 5 (NPC station; the skill has no effect in structures).":
            "Dein Broker-Relations-Level (0\u20135). Senkt die Broker Fee um 0,3 % pro Level: 3 % \u2192 1,5 % bei Level 5 (NPC-Station; in Strukturen wirkt der Skill nicht).",
        "From skills: tax/broker are calculated from your levels + the standings of the active hub, the manual fields are locked. Manual: you enter the percentages above yourself.":
            "Aus Skills: Tax/Broker werden aus deinen Leveln + den Standings des aktiven Hubs berechnet, die manuellen Felder werden gesperrt. Manuell: du gibst die Prozents\u00e4tze oben selbst ein.",
        "Deletes the cached market history and the last hub scan. Reloaded automatically at the next scan \u2013 that next run is slower once. Transactions, characters and shopping list stay.":
            "L\u00f6scht die zwischengespeicherte Markt-Historie und den letzten Hub-Scan. Wird beim n\u00e4chsten Scan automatisch neu geladen \u2013 der n\u00e4chste Lauf ist dann einmalig langsamer. Transaktionen, Charaktere und Einkaufsliste bleiben.",
        "Careful: very old purchases are the cost basis (FIFO) for long-held items. Only delete if you no longer need the profit history of such old trades.":
            "Vorsicht: Sehr alte K\u00e4ufe sind die Kostenbasis (FIFO) f\u00fcr lange gehaltene Items. Nur l\u00f6schen, wenn du die Gewinn-Historie so alter Trades nicht mehr brauchst.",
        "Total assets = wallet + item value + open sell orders + buy order escrow.\nWallet: {balance}\nItem value (net): {value}\nIn sell orders: {sell}\nIn buy orders (escrow): {escrow}":
            "Gesamtverm\u00f6gen = Kontostand + Item-Wert + offene Verkaufs-Orders + Kauf-Order-Escrow.\nKontostand: {balance}\nItem-Wert (netto): {value}\nIn Verkaufs-Orders: {sell}\nIn Kauf-Orders (Escrow): {escrow}",
        "Average margin of the REAL sales in the chosen period: net profit {net} against purchases of {cost} over {trades} trades. ISK-weighted \u2013 big trades count more than small ones.":
            "Durchschnittliche Marge der ECHTEN Verk\u00e4ufe im gew\u00e4hlten Zeitraum: Netto-Gewinn {net} gegen Einkauf {cost} \u00fcber {trades} Trades. ISK-gewichtet \u2013 grosse Trades z\u00e4hlen st\u00e4rker als kleine.",
        "Ticked = I have it (can build). Not ticked = will be bought (no blueprint). Then \u201eRecalculate\u201c.\nDo I have this blueprint(s)? ":
            "Angehakt = habe ich (kann bauen). Nicht angehakt = wird gekauft (keine Blaupause). Danach \u201eNeu berechnen\u201c.\nHabe ich diese Blaupause(n)? ",
        "{name}\nCLICK the name: set all four roles of this character at once \u2013 and remove them again on the next click.\nParallel job slots from the skills: {slots}\n(Mfg. = manufacturing / Mass Production, React. = reactions / Mass Reactions)":
            "{name}\nKLICK auf den Namen: alle vier Rollen dieses Charakters auf einmal setzen \u2013 und beim n\u00e4chsten Klick wieder entfernen.\nParallele Job-Slots aus den Skills: {slots}\n(Fert. = Fertigung / Mass Production, Reakt. = Reaktionen / Mass Reactions)",
        "Actually paid according to the wallet journal since {since}:\n\u2022 Broker (buy + sell + order changes): {broker}\n\u2022 Sales tax: {tax}\n\nExact net profit (gross \u2212 real fees): {net}\n(ESI delivers the journal ~30 days back; the DB collects from introduction on \u2013 older periods are incomplete accordingly.)":
            "Tats\u00e4chlich gezahlt laut Wallet-Journal seit {since}:\n\u2022 Broker (Kauf + Verkauf + Order-\u00c4nderungen): {broker}\n\u2022 Verkaufssteuer: {tax}\n\nExakter Netto-Gewinn (Brutto \u2212 echte Geb\u00fchren): {net}\n(ESI liefert das Journal r\u00fcckwirkend ~30 Tage; die DB sammelt ab Einf\u00fchrung \u2013 \u00e4ltere Zeitr\u00e4ume sind entsprechend unvollst\u00e4ndig.)",
        "Overall progress {pct:.0f} %: {rdone:.0f} of {rall:.0f} planned runs are delivered or running (reactions, components, end product; a running job counts half). {done} of {all} stages have started. ":
            "Gesamtfortschritt {pct:.0f} %: {rdone:.0f} von {rall:.0f} geplanten Runs sind abgeliefert oder laufen (Reaktionen, Komponenten, Endprodukt; ein laufender Job z\u00e4hlt halb). {done} von {all} Stufen sind angelaufen. ",
        "Manufacturing jobs for this product delivered via ESI since the plan was saved: {b} of {q} units.":
            "Seit dem Speichern des Plans per ESI abgelieferte Fertigungs-Jobs f\u00fcr dieses Produkt: {b} von {q} St\u00fcck.",
        " ({n} over plan.)":
            " ({n} \u00fcber Plan.)",
        " \u26a0 CAUTION: several saved plans build this product. The ESI jobs carry no plan assignment, so the same jobs count for EACH of these plans - this bar may be too high.":
            " \u26a0 ACHTUNG: mehrere gespeicherte Pl\u00e4ne bauen dieses Produkt. Die ESI-Jobs tragen keine Plan-Zuordnung, deshalb z\u00e4hlen dieselben Jobs f\u00fcr JEDEN dieser Pl\u00e4ne - dieser Balken kann zu hoch stehen.",
        "Sum over {n} plan(s).":
            "Summe \u00fcber {n} Plan/Pl\u00e4ne.",
        " {n} cannot be estimated and are NOT included.":
            " {n} nicht sch\u00e4tzbar und NICHT enthalten.",
        "Quick estimate with the prices of the last market scan.<br><br>The opened build plan uses real <b>order book prices</b> and therefore usually comes out somewhat <b>more expensive</b> \u2013 a live fetch per material for the whole list would be too slow here.<br>So always open the build plan to compare; this card is for <b>sorting</b>: which plan is worth it at all right now.":
            "Schnellsch\u00e4tzung mit den Preisen des letzten Markt-Scans.<br><br>Der ge\u00f6ffnete Bauplan rechnet mit echten <b>Orderbuch-Preisen</b> und kommt dadurch meist etwas <b>teurer</b> heraus \u2013 hier w\u00e4re ein Live-Abruf je Material f\u00fcr die ganze Liste zu langsam.<br>Zum Vergleichen also immer den Bauplan \u00f6ffnen; die Karte ist zum <b>Sortieren</b> da: welcher Plan lohnt sich gerade \u00fcberhaupt.",
        "Source: {src}. You already have an open buy order for this item in game.":
            "Quelle: {src}. Du hast f\u00fcr dieses Item bereits eine offene Buy-Order ingame.",
        "This order has already been repriced {n}\u00d7 - estimated broker fees so far: \u2248{fee}. That alone already eats up the expected profit over the remaining quantity (rough estimate with the current price, as the exact prices of earlier repricings are unknown). Better just hold the order / let it fill now instead of repricing further.":
            "Diese Order wurde schon {n}\u00d7 nachgebessert - gesch\u00e4tzte Broker-Geb\u00fchren dadurch bisher: \u2248{fee}. Das allein frisst den erwarteten Gewinn \u00fcber die Restmenge schon auf (grobe Sch\u00e4tzung mit aktuellem Preis, da die genauen Preise fr\u00fcherer Nachbesserungen nicht bekannt sind). Besser die Order jetzt einfach halten/f\u00fcllen lassen statt weiter nachzubessern.",
        "{n}\u00d7 repriced - estimated broker fees so far: \u2248{fee} (approximation with current price \u00d7 remaining quantity, as the exact prices of earlier steps are unknown).":
            "{n}\u00d7 nachgebessert - gesch\u00e4tzte Broker-Geb\u00fchren dadurch bisher: \u2248{fee} (N\u00e4herung mit aktuellem Preis \u00d7 Restmenge, da die genauen Preise fr\u00fcherer Schritte nicht bekannt sind).",
        "Sell price from the market scan of: {when}":
            "Sell-Preis aus dem Markt-Scan von: {when}",
        "Tradability: how reliably the item is traded daily on BOTH sides (your buy AND sell order get filled).\n\n":
            "Handelbarkeit: wie zuverl\u00e4ssig das Item t\u00e4glich an BEIDEN Seiten gehandelt wird (deine Buy- UND Sell-Order werden gef\u00fcllt).\n\n",
        "Plan frozen: material costs from the frozen state":
            "Plan eingefroren: Materialkosten aus dem Einfrier-Stand",
        " of {when}":
            " vom {when}",
        ", sale at the last market scan \u2013 the same calculation as in the dialog (\u201epurchase fixed \u00b7 profit live\u201c). At LIVE purchase prices the same card would look different \u2013 but that answers \u201eis a NEW build worth it today?\u201c, not \u201ewhat does MY build yield?\u201c.":
            ", Verkauf zum letzten Markt-Scan \u2013 dieselbe Rechnung wie im Dialog (\u201eEinkauf fest \u00b7 Gewinn live\u201c). Zu LIVE-Einkaufspreisen s\u00e4he dieselbe Karte anders aus \u2013 das beantwortet aber die Frage \u201elohnt ein NEUER Bau heute?\u201c, nicht \u201ewas bringt MEIN Bau?\u201c.",
        "Net margin after tax + broker if you reprice to {price}.":
            "Netto-Marge nach Steuer + Broker, wenn du auf {price} nachbesserst.",
        "Bidding up to {price} leaves no flip profit after broker (buy) + tax/broker (sell) \u2013 the market sell is only at {sell}. Better wait than bid up.":
            "H\u00f6herbieten auf {price} l\u00e4sst nach Broker (Kauf) + Steuer/Broker (Verkauf) keinen Flip-Gewinn mehr \u2013 der Markt-Sell liegt nur bei {sell}. Besser warten statt hochbieten.",
        "{n}\u00d7 repriced - estimated broker fees so far: \u2248{fee} (approximation - recalculated with real values at the next \u201eCheck orders\u201c).":
            "{n}\u00d7 nachgebessert - gesch\u00e4tzte Broker-Geb\u00fchren dadurch bisher: \u2248{fee} (N\u00e4herung - wird beim n\u00e4chsten \u201eOrders pr\u00fcfen\u201c mit echten Werten neu berechnet).",
        "\u00d8 buy: {avg} + estimated {fee}/unit repricing fees = {adj}.\nRough approximation - fills cannot be matched exactly to individual repricings via ESI.":
            "\u00d8-Kauf: {avg} + gesch\u00e4tzt {fee}/Stk. Nachbesserungs-Geb\u00fchren = {adj}.\nGrobe N\u00e4herung - Fills lassen sich \u00fcber ESI nicht exakt einzelnen Nachbesserungen zuordnen.",
        "You sell at {sell}, \u00d8 buy was {avg} ({pct:+.1f} %). ":
            "Du verkaufst zu {sell}, \u00d8-Kauf war {avg} ({pct:+.1f} %). ",
        "Profit":
            "Gewinn",
        "Loss or at best break-even":
            "Verlust oder h\u00f6chstens Kostendeckung",
        " on this order.":
            " bei dieser Order.",
        "Sell order price for exactly {pct:.0f}% target margin on {avg} \u00d8 purchase (after tax+broker) - regardless of the current market price.":
            "Sell-Order-Preis f\u00fcr genau {pct:.0f}% Ziel-Marge auf {avg} \u00d8-Einkauf (nach Steuer+Broker) - unabh\u00e4ngig vom aktuellen Marktpreis.",
        "Undercutting to {price} would be BELOW your purchase price (\u00d8 {cost}) after tax + broker \u2013 you would make a loss. Better not reprice.":
            "Unterbieten auf {price} l\u00e4ge nach Steuer + Broker UNTER deinem Einkaufspreis (\u00d8 {cost}) \u2013 du machst dann Verlust. Besser nicht nachbessern.",
        "Inventable from your \u201e{t1}\u201c.\nBuild cost/profit INCLUDING the expected invention cost (datacores, failed attempts, ME 2/TE 4 without decryptor).":
            "Erfindbar aus deinem \u201e{t1}\u201c.\nBaukosten/Gewinn INKLUSIVE Invention-Erwartungswert (Datacores, Fehlversuche, ME 2/TE 4 ohne Decryptor).",
        "Of that, at the linked BUILD structures. Only this quantity is deducted from the demand by the build plan; everything else you have to haul there first (or set the stock scope to \u201e Everywhere\u201c).":
            "Davon an den verkn\u00fcpften BAU-Strukturen. Nur diese Menge zieht der Bauplan vom Bedarf ab; alles andere musst du erst hinkarren (oder den Bestands-Scope auf \u201e \u00dcberall\u201c stellen).",
        "This quantity goes into the shopping list when ticked \u2013 the SHORTFALL, not the full demand.\nFor items already covered (Missing 0) it is the full quantity: ticking there explicitly means \u201ebuy anyway\u201c.":
            "Diese Menge landet beim Ankreuzen im Einkaufswagen \u2013 die FEHLMENGE, nicht der volle Bedarf.\nBei bereits gedeckten Items (Fehlt 0) ist es die volle Menge: ankreuzen hei\u00dft dort ausdr\u00fccklich \u201etrotzdem kaufen\u201c.",
        "Only items whose purchase price is at least this high.":
            "Nur Items, deren Kaufpreis mindestens so hoch ist.",
        "Highlights this window. The full history stays visible dimmed in the background \u2013 so you see the long-term trend on the side.":
            "Hebt dieses Fenster hervor. Die volle Historie bleibt gedimmt im Hintergrund sichtbar \u2013 so siehst du nebenbei den langfristigen Verlauf.",
        "NOTHING of it lies at the build location. You own it, but elsewhere \u2013 the build plan cannot deduct it, you have to bring it there (or set the stock scope to \u201e Everywhere\u201c).":
            "Am Bau-Ort liegt davon NICHTS. Du besitzt es zwar, aber woanders \u2013 der Bauplan kann es nicht abziehen, du musst es hinbringen (oder den Bestands-Scope auf \u201e \u00dcberall\u201c stellen).",
        "It IS there on site, but {n} units are reserved for other build plans":
            "Vor Ort ist es DA, aber {n} Stk sind fuer andere Baupl\u00e4ne reserviert",
        ". This plan must therefore not schedule them. Release the reservation on the other plan's card ( button) or finish that plan \u2013 then it is freed automatically.":
            ". Dieser Plan darf sie deshalb nicht einplanen. Reservierung auf der Karte des anderen Plans l\u00f6sen (-Knopf) oder den Plan abschliessen \u2013 dann wird sie automatisch frei.",
        "MEASURED from comparable earlier dips of this item (not extrapolated).\nExpected swing yield: {isk} ISK/day (profit \u00f7 recovery time) - a shallow fast dip thus beats the deep slow one.":
            "GEMESSEN aus vergleichbaren fr\u00fcheren Dips dieses Items (nicht hochgerechnet).\nErwarteter Swing-Ertrag: {isk} ISK/Tag (Gewinn \u00f7 Erholungsdauer) - flacher schneller Dip schl\u00e4gt damit den tiefen langsamen.",
        "Shopping list is empty \u2013 nothing to copy.":
            "Einkaufswagen ist leer \u2013 nichts zu kopieren.",
        "Mode changed \u2013 \u201eLoad deals\u201c.":
            "Modus gewechselt \u2013 \u201eDeals laden\u201c.",
        "Estimate for {n} of {total} rows: price from the last market scan \u00d7 quantity (+ broker), WITHOUT order depth - with big quantities you buy through several orders and pay more. \u201eLoad prices\u201c fetches the real order book.":
            "Schaetzung fuer {n} von {total} Zeilen: Preis aus dem letzten Markt-Scan \u00d7 Menge (+ Broker), OHNE Order-Tiefe - bei grossen Mengen kaufst du dich durch mehrere Orders und zahlst mehr. \u201ePreise laden\u201c holt das echte Orderbuch.",
        "Calculated from the real order depth of the chosen hub.":
            "Aus der echten Order-Tiefe des gewaehlten Hubs gerechnet.",
        "{rest} of {plan} runs still open \u2013 {done} already delivered or currently building (seen via ESI). The frozen plan itself stays unchanged.":
            "{rest} von {plan} Runs noch offen \u2013 {done} bereits abgeliefert oder gerade in Bau (per ESI gesehen). Der eingefrorene Plan selbst bleibt unver\u00e4ndert.",
        "Nothing left to do here \u2013 ESI has this covered. The line stays so you can look up later what was built and what it needed.":
            "Hier ist nichts mehr zu tun \u2013 ESI hat das abgedeckt. Die Zeile bleibt stehen, damit du sp\u00e4ter nachsehen kannst, was gebaut wurde und was es gebraucht hat.",
        "Currently in the build queue according to ESI \u2013 nothing to do here.":
            "Steckt laut ESI gerade in der Bauschleife \u2013 hier ist nichts zu tun.",
        "finished \u00b7 {n} position(s) completed":
            "fertig \u00b7 {n} Position(en) erledigt",
        "Planned duration of this stage was {d}.":
            "Geplante Dauer dieser Stufe war {d}.",
        "Where stock of yours has already been used for an item, that item is BUILT without comparing prices - even if buying would be cheaper.\n\nThis does not decide WHETHER stock is used; that is what \u201eSubtract assets\u201c does.":
            "Wo f\u00fcr ein Item bereits eigener Bestand eingesetzt wurde, wird dieses Item OHNE Preisvergleich GEBAUT \u2013 auch wenn Kaufen g\u00fcnstiger w\u00e4re.\n\nDies entscheidet NICHT, OB Bestand verwendet wird; das tut \u201eAssets abziehen\u201c.",
        "Without effect while \u201eIgnore costs \u2013 always build\u201c is on: that already builds everything without comparing prices.":
            "Ohne Wirkung, solange \u201eKosten ignorieren \u2013 immer bauen\u201c an ist: das baut ohnehin alles ohne Preisvergleich.",
        "Without effect while \u201eSubtract assets\u201c is off: without stock there is nothing this could act on.":
            "Ohne Wirkung, solange \u201eAssets abziehen\u201c aus ist: ohne Bestand gibt es nichts, worauf es wirken k\u00f6nnte.",
        "What you have to spend NOW: every position on the shopping list at the sell price of the chosen hub.\n\nThis is NOT the same as \u201eMaterial\u201c (which leaves out what comes from your own stock) and not the same as \u201etotal build cost\u201c (which counts that stock at replacement value).":
            "Was du JETZT ausgeben musst: jede Position der Einkaufsliste zum Sell-Preis des gew\u00e4hlten Hubs.\n\nDas ist NICHT dasselbe wie \u201eMaterial\u201c (dort fehlt, was aus deinem eigenen Bestand kommt) und nicht dasselbe wie \u201eBaukosten gesamt\u201c (dort z\u00e4hlt dieser Bestand zu Ersatzkosten mit).",
        "{n} position(s) without a price - they are MISSING from this sum.":
            "{n} Position(en) ohne Preis \u2013 sie FEHLEN in dieser Summe.",
        "Only one build plan at a time":
            "Nur ein Bauplan gleichzeitig",
        "Two build plans cannot be open at the same time \u2013 they would share their data, and the shopping list of one could end up with the materials of the other.\n\nClose the open plan first, then open the next one.":
            "Es k\u00f6nnen nicht 2 Baupl\u00e4ne gleichzeitig ge\u00f6ffnet sein \u2013 sie w\u00fcrden sich ihre Daten teilen, und die Einkaufsliste des einen k\u00f6nnte die Materialien des anderen enthalten.\n\nSchliesse den offenen Plan zuerst, dann \u00f6ffne den n\u00e4chsten.",
        # Sitzung 17: die 133 Anzeigetexte ueber Variablen (de_scan3)
        "Scan error: ":
            "Scan-Fehler: ",
        "Scanning {hub} \u2026 page {d}/{n}":
            "Scanne {hub} \u2026 Seite {d}/{n}",
        "direct":
            "direkt",
        "fallback table":
            "Fallback-Tabelle",
        " \u00b7 Tech levels ({via}): T1={t1} \u00b7 T2={t2} \u00b7 T3={t3} \u00b7 unknown={t0}":
            " \u00b7 Tech-Stufen ({via}): T1={t1} \u00b7 T2={t2} \u00b7 T3={t3} \u00b7 unbekannt={t0}",
        "Recipes loaded: {m} materials \u00b7 {p} products \u00b7 {pr} invention. \u201eBelow build cost\u201c (swing) & building usable.":
            "Baurezepte geladen: {m} Materialien \u00b7 {p} Produkte \u00b7 {pr} Invention. \u201eUnter Baupreis\u201c (Swing) & Bauen nutzbar.",
        "Flip \u00b7 {sub}":
            "Flip \u00b7 {sub}",
        "{n} implant(s) detected \u2713":
            "{n} Implantat(e) erkannt \u2713",
        "Reaction {v}%":
            "Reakt {v}%",
        "Cost {v}%":
            "Kosten {v}%",
        "Invention \u2212{v}% (job time, included in the Invention tab)":
            "Invention \u2212{v}% (Job-Zeit, im Invention-Tab eingerechnet)",
        "no rig bonuses":
            "keine Rig-Boni",
        "too few \u2013 get {n} more":
            "zu wenig \u2013 noch {n} besorgen",
        " (buildable items in the current scan: T1={t1} \u00b7 T2={t2} \u00b7 T3={t3} \u00b7 unknown={t0} - before the margin/volume filter)":
            " (baubare Items im aktuellen Scan: T1={t1} \u00b7 T2={t2} \u00b7 T3={t3} \u00b7 unbekannt={t0} - vor Marge/Volumen-Filter)",
        "\u2014 (material without price)":
            "\u2014 (Material ohne Preis)",
        "\u2713 top":
            "\u2713 vorne",
        "{ok} of {n} prices copied ({hub}). In EVE: sell window \u2192 \u201eImport prices from clipboard (Decimal Point)\u201c.":
            "{ok} von {n} Preisen kopiert ({hub}). In EVE: Verkaufsfenster \u2192 \u201eImport prices from clipboard (Decimal Point)\u201c.",
        "Contract Median":
            "Contract-Median",
        "Contract":
            "Contract",
        "Recommendation":
            "Empfehlung",
        "Efficiency quantity":
            "Effizienz-Menge",
        "{n} freight trip":
            "{n} Frachtfahrt",
        "{n} freight trips":
            "{n} Frachtfahrten",
        "Shopping list at {which} ({qty}): {vol} m\u00b3 \u00b7 {trips}":
            "Einkaufsliste bei {which} ({qty}): {vol} m\u00b3 \u00b7 {trips}",
        "expensive":
            "teuer",
        "too expensive":
            "zu teuer",
        " \u00b7 short (-{n})":
            " \u00b7 knapp (-{n})",
        # Sitzung 17: Hintergrund-Module, Bauplan-Bestandszeile, CCP-Hinweis
        "No client ID set. Please enter it in the settings.":
            "Keine Client-ID gesetzt. Bitte in den Einstellungen eintragen.",
        "Login cancelled or timed out.":
            "Login abgebrochen oder Zeit\u00fcberschreitung.",
        "State does not match (possible error).":
            "State stimmt nicht \u00fcberein (m\u00f6glicher Fehler).",
        "No token for character {cid}. Link it again.":
            "Kein Token f\u00fcr Charakter {cid}. Neu verkn\u00fcpfen.",
        "403 \u2013 permission missing. Link the character again with \u201eOpen in game\u201c enabled (scope esi-ui.open_window.v1).":
            "403 \u2013 Berechtigung fehlt. Charakter neu verkn\u00fcpfen mit aktiviertem \u201eIngame \u00f6ffnen\u201c (Scope esi-ui.open_window.v1).",
        "{code} \u2013 the character is not logged into the game (or another character is active). {body}":
            "{code} \u2013 Charakter ist nicht im Spiel eingeloggt (oder ein anderer Charakter ist aktiv). {body}",
        "Hub fetch incomplete: {n} of {pages} order book pages could not be loaded (e.g. page {p}) \u2013 the comparison would be distorted, please try again.":
            "Hub-Abruf unvollst\u00e4ndig: {n} von {pages} Orderbuch-Seiten nicht ladbar (z.B. Seite {p}) \u2013 Vergleich w\u00e4re verf\u00e4lscht, bitte erneut versuchen.",
        "No access to the order book of \u201e{name}\u201c with the linked character (check docking/market rights or the token).":
            "Kein Zugriff auf das Orderbuch von \u201e{name}\u201c mit dem verkn\u00fcpften Charakter (Docking-/Markt-Rechte oder Token pr\u00fcfen).",
        "Recipe database download failed: {err}":
            "SDE-Datenbank-Download fehlgeschlagen: {err}",
        "no answer":
            "keine Antwort",
        "only a draft or a pre-release":
            "nur ein Entwurf oder eine Vorabfassung",
        "version tag not readable":
            "Versionsmarke nicht lesbar",
        "Market scan: page 1 of the order book could not be loaded (ESI unreachable?) \u2013 the old snapshot stays active.":
            "Markt-Scan: Seite 1 des Orderbuchs nicht ladbar (ESI nicht erreichbar?) \u2013 alter Snapshot bleibt aktiv.",
        "Market scan incomplete: {n} of {pages} order book pages could not be loaded (e.g. page {p}). The snapshot is NOT saved \u2013 the old one stays active. Please scan again.":
            "Markt-Scan unvollst\u00e4ndig: {n} von {pages} Orderbuch-Seiten nicht ladbar (z.B. Seite {p}). Snapshot wird NICHT gespeichert \u2013 der alte bleibt aktiv. Bitte erneut scannen.",
        "need unknown":
            "Bedarf unbekannt",
        "covered \u2713":
            "gedeckt \u2713",
        "partial \u2013 {n} missing":
            "teilweise \u2013 es fehlen {n}",
        "missing completely \u2013 {n}":
            "fehlt komplett \u2013 {n}",
        "covered \u2713 \u2013 being built":
            "gedeckt \u2713 \u2013 wird gebaut",
        "covered \u2713 \u2013 the plan covers it (stock/jobs)":
            "gedeckt \u2713 \u2013 Plan deckt's (Bestand/Jobs)",
        "{n} finished (still to deliver!)":
            "{n} fertigen (noch abliefern!)",
        "{n} freshly delivered":
            "{n} frisch abgelieferten",
        "{n} RUNNING (pipeline)":
            "{n} LAUFENDEN (Pipeline)",
        "\u2795 {units} units from {jobs} jobs counted in":
            "\u2795 {units} Stk aus {jobs} Jobs mitgerechnet",
        "Stock per ESI \u00b7 as of {m} min ago":
            "Bestand laut ESI \u00b7 Stand vor {m} min",
        "\u26a0 ESI caches assets for up to 1 h \u2013 freshly delivered items may still be missing":
            "\u26a0 ESI cacht Assets bis zu 1 h \u2013 frisch Abgeliefertes fehlt evtl. noch",
        "\u26a0 Not loadable: {what} \u2013 the plan calculates WITHOUT their stock!":
            "\u26a0 Nicht ladbar: {what} \u2013 Plan rechnet OHNE deren Bestand!",
        "Reservations active ({plans}), but none of the local stock is affected":
            "Reservierungen aktiv ({plans}), aber nichts vom hiesigen Bestand betroffen",
        " \u2013 {n} units waiting for delivery":
            " \u2013 {n} Stk warten auf Anlieferung",
        "Once for the whole plan \u2013 NOT per unit:":
            "Einmalig f\u00fcr den ganzen Plan \u2013 NICHT je St\u00fcck:",
        "Frozen: the purchasing stock stays fixed, intermediate products BUILT since then are credited live.":
            "Eingefroren: Einkaufs-Bestand bleibt fix, seither GEBAUTE Zwischenprodukte werden live gutgeschrieben.",
        "Now \u201eLoad deals\u201c.":
            "Jetzt \u201eDeals laden\u201c.",
        "Not a CCP Games product, not endorsed by CCP. The developer has signed the EVE Online Developer License Agreement. EVE Online and all related trademarks belong to CCP hf.":
            "Dieses Werkzeug ist kein Erzeugnis von CCP Games und wird von CCP weder herausgegeben noch unterst\u00fctzt. Der Entwickler hat die EVE Online Developer License Agreement unterzeichnet. EVE Online und alle zugeh\u00f6rigen Marken geh\u00f6ren CCP hf.",
        # Sitzung 17, Block 2: Bauplan-Fenster, Bauplan-Reiter, Optimierer
        "Quantity:":
            "Menge:",
        "Build cost / unit":
            "Baukosten / Stk",
        "Build cost, bundle total":
            "Baukosten, B\u00fcndel gesamt",
        " ISK, bundle total":
            " ISK, B\u00fcndel gesamt",
        "Sell / unit":
            "Sell / Stk",
        "Min. sell price / unit":
            "Min. Verkaufspreis / Stk",
        "Split myself (no char)":
            "Selber aufteilen (kein Char)",
        "{n} blueprint names copied \u2013 one line per blueprint.":
            "{n} Blueprint-Namen kopiert \u2013 eine Zeile je Blueprint.",
        "{ok} recognised, {bad} unknown":
            "{ok} erkannt, {bad} unbekannt",
        "{n} units deducted by reservations ({plans})":
            "{n} Stk durch Reservierungen abgezogen ({plans})",
        "\u26a0 not recognised: ":
            "\u26a0 nicht erkannt: ",
        "Blacklist \u2013 not planned":
            "Blacklist \u2013 nicht eingeplant",
        "on hand":
            "vorhanden",
        "\u2014 nothing to build":
            "\u2014 nichts zu bauen",
        "covered from stock":
            "aus Bestand gedeckt",
        "\u2014 not planned":
            "\u2014 nicht eingeplant",
        "buy":
            "kaufen",
        "buy \u00b7 no recipe":
            "kaufen \u00b7 kein Rezept",
        "buy \u00b7 partly from stock":
            "kaufen \u00b7 teils aus Bestand",
        " ({n} not at the build structure)":
            " ({n} nicht an der Baustruktur)",
        "Never buy and never build these groups:":
            "Diese Gruppen nie kaufen und nie bauen:",
        "(order running)":
            "(Order l\u00e4uft)",
        "this plan builds it":
            "dieser Plan baut es",
        "Largest positions (quantity \u00d7 price):":
            "Gr\u00f6\u00dfte Posten (Menge \u00d7 Preis):",
        "T1 original \u00b7 invention":
            "T1-Original \u00b7 Invention",
        "T1 original for the invention of the T2 copy - it also builds the T1 item that goes into the T2 product.":
            "T1-Original f\u00fcr die Invention der T2-Kopie \u2013 baut au\u00dferdem das T1-Item, das ins T2-Produkt geht.",
        "Copy job: \u2248{d}":
            "Kopierjob: \u2248{d}",
        "Then invention:":
            "Danach Invention:",
        "reserved by other plans":
            "von anderen Pl\u00e4nen reserviert",
        "{n} reserved":
            "{n} reserviert",
        "Hide this number \u2013 for screenshots and streams. Only the display "
        "changes, nothing is calculated differently.":
            "Diese Zahl verdecken \u2013 f\u00fcr Screenshots und Streams. Nur die "
            "Anzeige \u00e4ndert sich, gerechnet wird unver\u00e4ndert.",
        "Show this number again":
            "Diese Zahl wieder zeigen",
        "\u26a0 Market needs a scan!":
            "\u26a0 Markt muss gescannt werden!",
        "\u26a0 Market scan is too old \u2013 please run it again.":
            "\u26a0 Markt-Scan ist zu lange her \u2013 bitte neu laden.",
        "Do I have the blueprints?":
            "Habe ich die Blaupausen?",
        "Click copies the blueprint name:":
            "Klick kopiert den Blaupausen-Namen:",
        "Copy T1 Blueprint":
            "T1-Blueprint kopieren",
        "{name} copied \u2713":
            "{name} kopiert \u2713",
        " \u2013 you own {n} in total, the rest is not at this plan's structures":
            " \u2013 insgesamt besitzt du {n}, der Rest liegt nicht an den "
            "Strukturen dieses Plans",
        "{n} units are on site as well, but reserved for other build plans":
            "{n} Einheiten liegen ebenfalls vor Ort, sind aber f\u00fcr andere "
            "Baupl\u00e4ne reserviert",
        ". Release the reservation on the other plan's card or finish that plan, "
        "then this plan can use them.":
            ". Gib die Reservierung auf der Karte des anderen Plans frei oder "
            "schliesse ihn ab, dann kann dieser Plan sie nutzen.",
        " \u2013 {n} left out, this plan builds them":
            " \u2013 {n} weggelassen, dieser Plan baut sie",
        " {n} position(s) are made by the plan itself.":
            " {n} Position(en) stellt der Plan selbst her.",
        "The build plan makes this item itself - the material for it is already "
        "on the list. Buying it as well would pay for it twice. Tick it only if "
        "you deliberately want to buy it instead.":
            "Der Bauplan stellt dieses Item selbst her \u2013 das Material daf\u00fcr "
            "steht bereits auf der Liste. Es zusätzlich zu kaufen hiesse, zweimal "
            "zu zahlen. Nur ankreuzen, wenn du es bewusst kaufen willst.",
        "No daily volume for any row \u2013 click \u201eLoad prices\u201c here, or "
        "load the Daytrade deals. Without volume there is nothing to suggest.":
            "F\u00fcr keine Zeile ist ein Tagesvolumen bekannt \u2013 hier auf "
            "\u201ePreise laden\u201c klicken oder die Daytrade-Deals laden. Ohne "
            "Volumen gibt es nichts vorzuschlagen.",
        "Everything in this group is taken out of the plan completely \u2013 not "
        "built, not bought, and it disappears from the shopping list and the "
        "run planner. What it would have been made of falls away with it.":
            "Alles aus dieser Gruppe f\u00e4llt komplett aus dem Plan \u2013 wird "
            "weder gebaut noch gekauft und verschwindet aus Einkaufsliste und "
            "Runplaner. Was daf\u00fcr n\u00f6tig w\u00e4re, f\u00e4llt mit weg.",
        "Prefilled from your own blueprint (the worst-researched copy). "
        "Change it and the tool leaves it alone.":
            "Aus deiner eigenen Blaupause vorbelegt (die am schlechtesten "
            "erforschte Kopie). \u00c4nderst du den Wert, fasst das Werkzeug "
            "ihn nicht mehr an.",
        "The cost index is not 0 here but BORROWED from another system \u2013 "
        "{liste}. The number looks plausible, its origin is wrong.":
            "Der Kostenindex ist hier nicht 0, sondern GELIEHEN aus einem "
            "anderen System \u2013 {liste}. Die Zahl sieht plausibel aus, ihre "
            "Herkunft stimmt nicht.",
        "{n} linked character(s) have no role at all \u2013 they build nothing "
        "and their slots do not count.":
            "{n} verkn\u00fcpfte(r) Charakter(e) haben gar keine Rolle \u2013 sie bauen "
            "nichts, und ihre Slots z\u00e4hlen nicht.",
        "Sets all four roles for every linked character. You can untick "
        "individual ones again afterwards.":
            "Setzt alle vier Rollen f\u00fcr jeden verkn\u00fcpften Charakter. Einzelne "
            "kannst du danach wieder abw\u00e4hlen.",
        "BUILD \u00b7 {n} run":
            "BAUEN \u00b7 {n} Run",
        "BUILD \u00b7 {n} runs":
            "BAUEN \u00b7 {n} Runs",
        "\u2697 Reactions \u00b7 stage 1 (\u2192 further reaction)":
            "\u2697 Reaktionen \u00b7 Stufe 1 (\u2192 weitere Reaktion)",
        "\u2697 Reactions \u00b7 stage 2 (\u2192 build)":
            "\u2697 Reaktionen \u00b7 Stufe 2 (\u2192 Bau)",
        "Advanced Components":
            "Advanced Components",
        "Other (fuel blocks, components)":
            "Sonstige (Fuel Blocks, Komponenten)",
        "Material (purchase)":
            "Material (Einkauf)",
        "Freight service ({rate} ISK/m\u00b3)":
            "Frachtdienst ({rate} ISK/m\u00b3)",
        "Job costs":
            "Job-Kosten",
        "Facility tax (owner)":
            "Facility-Tax (Besitzer)",
        "SCC surcharge":
            "SCC-Abgabe",
        "= Job costs":
            "= Job-Kosten",
        "Plain purchase price of the same quantity: {v}.":
            "Reiner Kaufpreis derselben Menge: {v}.",
        "Blueprints: {name}":
            "Blaupausen: {name}",
        # ---- Corp-Hangar (1.0.8) ----
        "Corp roles: {name}":
            "Corp-Rollen: {name}",
        "Corp assets: {name}":
            "Corp-Assets: {name}",
        "Corp blueprints: {name}":
            "Corp-Blaupausen: {name}",
        "Corp jobs: {name}":
            "Corp-Jobs: {name}",
        # ---- Corp-Blaupausen in My Blueprints (1.1.0) ----
        "{corp} · several hangars":
            "{corp} · mehrere Hangars",
        "{corp} · Corp hangar {n}":
            "{corp} · Corp-Hangar {n}",
        "Corp blueprints: no corp hangar selected in the settings":
            "Corp-Blaupausen: in den Einstellungen ist kein Corp-Hangar gewählt",
        "{n} corp blueprint(s) from {corps}":
            "{n} Corp-Blaupause(n) aus {corps}",
        "re-link for corp access: {names}":
            "für Corp-Zugriff neu verlinken: {names}",
        "no Director role in: {corps}":
            "keine Director-Rolle in: {corps}",
        # ---- Vorstufen ohne offenen Verbraucher (1.1.0) ----
        "not needed any more \u2713":
            "nicht mehr n\u00f6tig \u2713",
        "Everything in this plan that uses this item is already built or running - the remaining runs are not needed. Nothing to buy, nothing to start.":
            "Alles in diesem Plan, was dieses Item verbraucht, ist schon gebaut oder l\u00e4uft \u2013 die restlichen Runs braucht es nicht mehr. Nichts zu kaufen, nichts zu starten.",
        "Corp":
            "Corp",
        "Market scanned \u2013 now load the deals":
            "Markt gescannt \u2013 jetzt die Deals laden",
        # ---- Runs statt Stueck (Discord, 16.09.2026) ----
        "Runs":
            "Runs",
        "Runs:":
            "Runs:",
        "Number of runs. One run yields {n} units - the plan keeps calculating in units.":
            "Anzahl Runs. Ein Run liefert {n} St\u00fcck \u2013 der Plan rechnet weiter in St\u00fcck.",
        "Switch the field between units and runs. Only offered for products that yield more than one unit per run.":
            "Schaltet das Feld zwischen St\u00fcck und Runs um. Gibt es nur bei Produkten, die mehr als ein St\u00fcck je Run liefern.",
        "= {q} units ({n} per run)":
            "= {q} St\u00fcck ({n} je Run)",
        "On (count corp hangars when building)":
            "An (Corp-Hangar beim Bauen mitzählen)",
        "Corp-Hangar {n}":
            "Corp-Hangar {n}",
        "wave {n}":
            "Welle {n}",
        "Second listing of this character: start these copies once the first wave has freed the slots (e.g. the next day).":
            "Zweite Auflistung dieses Charakters: diese Kopien starten, sobald die erste Welle die Slots freigegeben hat (z. B. am nächsten Tag).",
        "Load names":
            "Namen laden",
        "Fetches the division names of your corporation from ESI. Needs a linked character with the Director role and the corp permission.":
            "Holt die Division-Namen deiner Corporation aus ESI. Braucht einen verknüpften Charakter mit Director-Rolle und der Corp-Berechtigung.",
        "Corporation hangars (build)":
            "Corporation-Hangar (Bauen)",
        "Corp divisions":
            "Corp-Divisions",
        "On: the build plan, run planner and blueprints also count the hangar divisions ticked below - of every corporation your linked characters are in. One fetch per corporation, never per character. Needs the Director role in game and re-linking. Portfolio and Profits are NOT affected.":
            "An: Bauplan, Runplaner und Blaupausen zählen auch die unten angekreuzten Hangar-Divisions mit – von jeder Corporation, in der deine verknüpften Charaktere sind. Ein Abruf je Corporation, nie je Charakter. Braucht die Director-Rolle im Spiel und ein Neu-Verknüpfen. Portfolio und Profits sind NICHT betroffen.",
        "Which of the seven corp hangar divisions count as build stock. Nothing is counted until at least one is ticked.":
            "Welche der sieben Corp-Hangar-Divisions als Baubestand zählen. Solange keine angekreuzt ist, wird nichts gezählt.",
        "Corp divisions saved: {n}":
            "Corp-Divisions gespeichert: {n}",
        "No corp division selected – corp hangars count nothing.":
            "Keine Corp-Division gewählt – Corp-Hangar zählt nichts.",
        "Division names loaded.":
            "Division-Namen geladen.",
        "Re-link {names} first – the login has no corp permission yet.":
            "Erst {names} neu verknüpfen – die Anmeldung hat noch keine Corp-Berechtigung.",
        "No linked character holds the Director role – names cannot be loaded.":
            "Kein verknüpfter Charakter hat die Director-Rolle – Namen können nicht geladen werden.",
        "⚠ Corp hangars are ON, but no division is selected – Settings → Corporation.":
            "⚠ Corp-Hangar ist AN, aber keine Division gewählt – Einstellungen → Corporation.",
        "Corp stock: {corp} via {char} – {divs} ({n} rows)":
            "Corp-Bestand: {corp} über {char} – {divs} ({n} Zeilen)",
        "⚠ Re-link {names}: linked before the corp switch was turned on, the login has no corp permission yet.":
            "⚠ {names} neu verknüpfen: vor dem Einschalten des Corp-Schalters verknüpft, die Anmeldung hat noch keine Corp-Berechtigung.",
        "⚠ No linked character holds the Director role in {corps} – that corp hangar is NOT counted.":
            "⚠ Kein verknüpfter Charakter hat die Director-Rolle in {corps} – dieser Corp-Hangar wird NICHT gezählt.",
        "No matching assets found in stock":
            "Keine passenden Assets auf Lager gefunden",
        "Assets subtracted (build structures only) \u2013 {n} material(s) reduced \u2713":
            "Assets abgezogen (nur Bau-Strukturen) \u2013 {n} Material(ien) reduziert \u2713",
        "Added to the blacklist: ":
            "Auf die Blacklist: ",
        "Fetching order book prices \u2026":
            "Orderbuch-Preise werden geholt \u2026",
        "no blueprints of your own":
            "keine eigenen Blaupausen",
        "Plan frozen \u2713":
            "Plan eingefroren \u2713",
        "Back to live prices & live stock":
            "Wieder Live-Preise & Live-Bestand",
        "{name}: <b>{k}</b> copies ({j} jobs \u2013 {g} runs)":
            "{name}: <b>{k}</b> Kopien ({j} Jobs \u2013 {g} Runs)",
        " \u00b7 +{n} more":
            " \u00b7 +{n} weitere",
        "missing completely \u2013 buy {n}":
            "fehlt komplett \u2013 {n} kaufen",
        "\u26a0 {n} item missing completely:":
            "\u26a0 {n} Item fehlt komplett:",
        "\u26a0 {n} items missing completely:":
            "\u26a0 {n} Items fehlen komplett:",
        "Classification of the items (group \u2192 rig category):":
            "Einordnung der Items (Gruppe \u2192 Rig-Kategorie):",
        " (ready!)":
            " (fertig!)",
        "Not profitable at any quantity in this range":
            "In diesem Bereich bei keiner Menge profitabel",
        "Cost/unit":
            "Kosten/Stk",
        "Calculating optimal quantity \u2026":
            "Optimale Menge berechnen \u2026",
        "{name}: name not recognised":
            "{name}: Name nicht erkannt",
        # Sitzung 17, Block 3: main_window
        " units":
            " Stk",
        "SDE error: ":
            "SDE-Fehler: ",
        "Min below \u00d8 %":
            "Min unter \u00d8 %",
        "Min drop %":
            "Min Drop %",
        "Min margin %":
            "Min Marge %",
        "Invention: {n} item(s) with own BPCs":
            "Invention: {n} Item(s) mit eigenen BPCs",
        "{n} item(s) with own blueprints found \u2713":
            "{n} Item(s) mit eigenen Blaupausen gefunden \u2713",
        " ISK/unit":
            " ISK/Stk",
        "React":
            "Reakt",
        "Inv":
            "Inv",
        "\u2014 (load skills)":
            "\u2014 (Skills laden)",
        "Job slots loaded \u2713":
            "Job-Slots geladen \u2713",
        "Loading skills \u2026":
            "Skills laden \u2026",
        "Profile \u201e{name}\u201c loaded \u2713":
            "Profil \u201e{name}\u201c geladen \u2713",
        "Build \u2212{p} % time":
            "Bau \u2212{p} % Zeit",
        "System index error: ":
            "System-Index-Fehler: ",
        "Nothing to buy":
            "Nichts zu kaufen",
        "\u201e{name}\u201c completed \u2713":
            "\u201e{name}\u201c abgeschlossen \u2713",
        " \u00b7 reservation released":
            " \u00b7 Reservierung freigegeben",
        "no market scan":
            "kein Markt-Scan",
        "Sell/unit":
            "Verkauf/Stk",
        "\u26a0 {name} blueprint (missing)":
            "\u26a0 {name} Blueprint (fehlt)",
        "Reactions stage 1 (Intermediate)":
            "Reaktionen Stufe 1 (Intermediate)",
        "Reactions stage 2 (Composite)":
            "Reaktionen Stufe 2 (Composite)",
        "Components (incl. fuel blocks)":
            "Komponenten (mit Fuel Blocks)",
        "Reaction \u00b7 stage 1":
            "Reaktion \u00b7 Stufe 1",
        "Reaction \u00b7 stage 2":
            "Reaktion \u00b7 Stufe 2",
        "\u2697 Reactions \u2013 Intermediate (ingredients)":
            "\u2697 Reaktionen \u2013 Intermediate (Zutaten)",
        "\u2697 Reactions \u2013 Composite (needs stage 1)":
            "\u2697 Reaktionen \u2013 Composite (braucht Stufe 1)",
        "Contract scan error: ":
            "Contract-Scan-Fehler: ",
        "Below \u00d8":
            "Unter \u00d8",
        "Price crash":
            "Preis-Crash",
        "{n} covered":
            "{n} gedeckt",
        "{n} partial":
            "{n} teilweise",
        "{n} missing":
            "{n} fehlt",
        "Stock spread across:":
            "Bestand verteilt auf:",
        "{n} {what} copied \u2713 \u2013 {k} without a resolved name skipped ({names})":
            "{n} {what} kopiert \u2713 \u2013 {k} ohne aufgel\u00f6sten Namen ausgelassen ({names})",
        "{n} {what} copied \u2713 (EVE multibuy format)":
            "{n} {what} kopiert \u2713 (EVE-Multibuy-Format)",
        "{name} \u00b7 output {q}/run \u00b7 floor/unit {v}":
            "{name} \u00b7 Output {q}/Run \u00b7 Boden/Stk {v}",
        " \u00b7 of which invention {v}":
            " \u00b7 davon Invention {v}",
        "(none)":
            "(keine)",
        "Structure \u201e{name}\u201c set as build location \u2713":
            "Struktur \u201e{name}\u201c als Bau-Ort gesetzt \u2713",
        "Daily volume \u2248 {v} units/day":
            "Tagesvolumen \u2248 {v} Stk/Tag",
        "Quantity {n} copied \u2713":
            "Menge {n} kopiert \u2713",
        "Quantity set \u2713 ({n})":
            "Menge gesetzt \u2713 ({n})",
        "Export error: ":
            "Export-Fehler: ",
        "\u00d8 price":
            "\u00d8-Preis",
        "Login failed":
            "Login fehlgeschlagen",
        "{name}: {n} units   (remaining need {need}, on hand {have}, remaining production {prod})":
            "{name}: {n} Stk   (Restbedarf {need}, da {have}, Rest-Produktion {prod})",
        "Comparing characters \u2026":
            "Vergleiche Charaktere \u2026",
        "Price copied \u2713":
            "Preis kopiert \u2713",
        # Sitzung 17: Berechtigungs-Schalter
        "Switched on and saved. Now re-link your character (Characters tab) so EVE grants the permission.":
            "Eingeschaltet und gespeichert. Jetzt den Charakter neu verkn\u00fcpfen (Reiter Charaktere), damit EVE die Berechtigung erteilt.",
        "Switched off and saved.":
            "Ausgeschaltet und gespeichert.",
        "Fixed at 0.25 % in NPC stations \u2013 CCP sets this rate, it cannot be changed.":
            "In NPC-Stationen fest auf 0,25 % \u2013 diesen Satz legt CCP fest, er l\u00e4sst sich nicht \u00e4ndern.",
        "Station":
            "Station",
        "\u2014 none \u2014":
            "\u2014 keine \u2014",
        "\u26a0 No structure for: {stages}. Reactions REQUIRE a refinery with a reactor module \u2013 they cannot run in an NPC station at all. Job fees are calculated with system cost index 0, so the profit shown here is too high.":
            "\u26a0 Keine Struktur f\u00fcr: {stages}. Reaktionen BRAUCHEN eine Refinery mit Reactor-Modul \u2013 in einer NPC-Station gehen sie \u00fcberhaupt nicht. Die Anlagegeb\u00fchren werden mit Systemkostenindex 0 gerechnet, der hier gezeigte Gewinn ist also zu hoch.",
        "\u26a0 No structure for: {stages}. Job fees are calculated with system cost index 0, so the profit shown here is too high. Add a structure or an NPC station under Setup \u2192 Structures.":
            "\u26a0 Keine Struktur f\u00fcr: {stages}. Die Anlagegeb\u00fchren werden mit Systemkostenindex 0 gerechnet, der hier gezeigte Gewinn ist also zu hoch. Unter Setup \u2192 Strukturen eine Struktur oder NPC-Station anlegen.",
        "These assignments are impossible in EVE and are being ignored: {list}. Reactions only run in a refinery with a reactor module; a refinery can do nothing else. The automatic choice is used instead \u2013 pick a suitable structure below to make it explicit.":
            "Diese Zuweisungen gibt es in EVE nicht, sie werden ignoriert: {list}. Reaktionen laufen nur in einer Refinery mit Reactor-Modul; eine Refinery kann sonst nichts. Stattdessen greift die Auto-Wahl \u2013 unten eine passende Struktur w\u00e4hlen, um es festzulegen.",
        "Only this plan's structures (for structures in different regions)":
            "Nur die Strukturen dieses Plans (f\u00fcr Strukturen in verschiedenen Regionen)",
        "WHERE stock counts:\nOnly build structures \u2013 items at all your linked build structures (default).\nOnly this plan's structures \u2013 only the structures this plan actually uses; for people whose structures sit in different regions, so material in the wrong region is not counted.\nEverywhere \u2013 all assets of all pool characters, wherever they are (when you pull everything together anyway).":
            "WO Bestand z\u00e4hlt:\nNur Bau-Strukturen \u2013 Material in allen verkn\u00fcpften Bau-Strukturen (Standard).\nNur die Strukturen dieses Plans \u2013 nur die Strukturen, die dieser Plan wirklich benutzt; f\u00fcr Leute, deren Strukturen in verschiedenen Regionen liegen, damit Material in der falschen Region nicht z\u00e4hlt.\n\u00dcberall \u2013 alle Assets aller Pool-Charaktere, wo auch immer sie liegen (wenn man ohnehin alles zusammenzieht).",
        ", of which {n} reserved by other build plans":
            ", davon {n} von anderen Baupl\u00e4nen reserviert",
        "\u26a0 Own BPC: the invention settings above do not apply. ME {me} % / TE {te} % come from your own copy (the worst-researched one you own) and are what is being calculated. Change them if you want.":
            "\u26a0 Eigene BPC: die Invention-Einstellungen dar\u00fcber wirken nicht. ME {me} % / TE {te} % stammen von deiner eigenen Kopie (der am schlechtesten erforschten, die du besitzt) und werden so gerechnet. Du kannst sie \u00e4ndern.",
        "\u26a0 Own BPC: the invention settings above do not apply. No copy of your own was found via ESI, so ME/TE stay at 0/0 and 0/0 is what is being calculated \u2013 enter your own values.":
            "\u26a0 Eigene BPC: die Invention-Einstellungen dar\u00fcber wirken nicht. \u00dcber ESI wurde keine eigene Kopie gefunden, deshalb bleiben ME/TE auf 0/0 und es wird auch mit 0/0 gerechnet \u2013 trage deine eigenen Werte ein.",
        "Changed \u2013 applying it to the build plan \u2026":
            "Ge\u00e4ndert \u2013 wird auf den Bauplan angewendet \u2026",
        "\u2014 system not found \u2014":
            "\u2014 System nicht gefunden \u2014",
        "\u2014 choose a system first \u2014":
            "\u2014 erst ein System w\u00e4hlen \u2014",
        "\u2014 no NPC station in this system \u2014":
            "\u2014 keine NPC-Station in diesem System \u2014",
        "Checking station \u2026":
            "Station wird gepr\u00fcft \u2026",
        "Easiest: in game right-click the structure or NPC station \u2192 \u201eCopy info\u201c, then paste here (the copied link contains the ID).\n\nAlternatively enter the ID directly. For a player structure your character needs docking/market access there; an NPC station needs nothing.":
            "Am einfachsten: im Spiel Rechtsklick auf die Struktur oder NPC-Station \u2192 \u201eInfo kopieren\u201c, dann hier einf\u00fcgen (der kopierte Link enth\u00e4lt die ID).\n\nAlternativ die ID direkt eingeben. Bei einer Spielerstruktur braucht dein Charakter dort Andock-/Marktzugang; eine NPC-Station braucht nichts.",
        "Structures not accessible":
            "Strukturen nicht zug\u00e4nglich",
        "{n} structure(s) from your assets/orders could not be opened \u2013 your character has no docking access there. That is normal: you can have orders or leftover material in a structure without being allowed to dock, and access can be withdrawn later.\n\nThe permission itself is in place, so there is NOTHING for you to fix. You cannot build in those structures anyway.":
            "{n} Struktur(en) aus deinen Assets/Orders lie\u00dfen sich nicht \u00f6ffnen \u2013 dein Charakter hat dort kein Andockrecht. Das ist normal: man kann Orders oder liegengebliebenes Material in einer Struktur haben, ohne andocken zu d\u00fcrfen, und der Zugang kann sp\u00e4ter entzogen werden.\n\nDie Berechtigung selbst ist vorhanden, es gibt also NICHTS zu tun. Bauen kannst du in diesen Strukturen ohnehin nicht.",
        "Structure permission missing":
            "Struktur-Berechtigung fehlt",
        "{n} structure(s) found in your assets/orders, but EVE refused to reveal their names \u2013 the character is linked without the structure permission.\n\nSwitch \u201eStructure markets\u201c on in the settings, then re-link the character (Characters tab).":
            "{n} Struktur(en) in deinen Assets/Orders gefunden, aber EVE verweigert ihre Namen \u2013 der Charakter ist ohne Struktur-Berechtigung verkn\u00fcpft.\n\nIn den Einstellungen \u201eStructure markets\u201c einschalten und den Charakter neu verkn\u00fcpfen (Reiter Charaktere).",
        # Sitzung 17: Regional-Spalten
        "Sell (source)":
            "Sell-Preis (Quelle)",
        "Buy order (destination)":
            "Kaufgebot (Ziel)",
        "What you pay at the source: the average price when you buy up its cheapest sell orders (for a realistic quantity, so a single cheap order cannot distort the margin).":
            "Was du an der Quelle zahlst: der Durchschnittspreis, wenn du ihre g\u00fcnstigsten Sell-Orders leerkaufst (f\u00fcr eine realistische Menge, damit eine einzelne billige Order die Marge nicht verf\u00e4lscht).",
        "Destination price the profit is calculated with: its cheapest sell order when you sell via sell order, its highest buy order when you sell immediately.":
            "Zielpreis, mit dem der Gewinn gerechnet wird: die g\u00fcnstigste Sell-Order, wenn du per Sell-Order verkaufst, das h\u00f6chste Kaufgebot, wenn du sofort verkaufst.",
        # Sitzung 17: Ladetexte (label=/status)
        "Build plan {name} \u2026":
            "Bauplan {name} \u2026",
        "Loading source order book \u2026 (whole region, may take a while)":
            "Lade Quell-Orderbuch \u2026 (ganze Region, kann dauern)",
        "Loading destination order book \u2026 (whole region, may take a while)":
            "Lade Ziel-Orderbuch \u2026 (ganze Region, kann dauern)",
        "Comparing prices & calculating margin \u2026":
            "Vergleiche Preise & rechne Marge \u2026",
        "Sell prices {hub} \u2026":
            "Sell-Preise {hub} \u2026",
        "Reading skills & standings \u2026":
            "Lese Skills & Standings \u2026",
        "ESI blueprint ownership \u2026":
            "ESI-Blueprint-Besitz \u2026",
        "Order book prices \u2026":
            "Orderbuch-Preise \u2026",
        "Optimising \u2026":
            "Optimieren \u2026",
        "Fetching order book \u2026":
            "Orderbuch-Abruf \u2026",
        # Sitzung 17: Nutzer-Screenshots (Profits, Transactions, Settings, Industry)
        "Period:":
            "Zeitraum:",
        "\u00d8 margin":
            "\u00d8 Marge",
        "Type:":
            "Typ:",
        "Search:":
            "Suche:",
        "Show:":
            "Anzeigen:",
        "Category:":
            "Kategorie:",
        "ESI client ID":
            "ESI Client-ID",
        "Callback port":
            "Callback-Port",
        "Target margin":
            "Ziel-Marge",
        "Sales tax":
            "Sales Tax",
        "Broker fee (NPC)":
            "Broker Fee (NPC)",
        "Broker fee (structure)":
            "Broker Fee (Struktur)",
        "Profitable production (T1)":
            "Lohnende Produktion (T1)",
        "Profitable production (T2)":
            "Lohnende Produktion (T2)",
        "Reactions only":
            "Reaktionen",
        "Rigs (T1 + T2)":
            "Rigs (T1 + T2)",
        "Reaction \u2212{p} % time":
            "Reaktion \u2212{p} % Zeit",
        "Skills: ":
            "Skills: ",
        "Price history: {name}":
            "Kursverlauf: {name}",
        "Buffer:":
            "Puffer:",
        "Name":
            "Name",
        "System":
            "System",
        "Real EVE structure":
            "Echte EVE-Struktur",
        "Security (auto)":
            "Sicherheit (auto)",
        "Structure {id}":
            "Struktur {id}",
        "Sell order":
            "Sell-Order",
        "Inventory":
            "Inventar",
        "Spread":
            "Spanne",
        "Fast turnover":
            "Stunden",
        "Low competition":
            "Konkurrenz",
        "Niche":
            "Nische",
        "Capital-efficient":
            "Kapital",
        "Flip":
            "Flip",
        "via:":
            "durch:",
        "Margin: {v} %":
            "Marge: {v} %",
        "Own haul":
            "Eigene Fahrt",
        "Extra costs":
            "Zusatzkosten",
        "Cargo hold:":
            "Frachtraum:",
        "Freight service:":
            "Frachtdienst:",
        "Facility tax":
            "Facility-Tax",
        "Blueprint ME":
            "Blueprint-ME",
        "Blueprint TE":
            "Blueprint-TE",
        "Invention":
            "Invention",
        "Exact: ":
            "Exakt: ",
        "Fuel":
            "Treibstoff",
        "stage {n}":
            "St.{n}",
        # Sitzung 17: Discord-Knopf
        "Discord":
            "Discord",
        "Community server: questions, bug reports and feature requests. Opens in your browser.":
            "Community-Server: Fragen, Fehlermeldungen und W\u00fcnsche. \u00d6ffnet sich im Browser.",
        # Sitzung 17: eigene Anzeige-Helfer (kpi_card, _collapsible, addRow)
        "Invested (held)":
            "Investiert (gehalten)",
        "Item value (net)":
            "Item-Wert (netto)",
        "Rig slot {n}":
            "Rig-Slot {n}",
        "Expected profit":
            "Erwarteter Gewinn",
        "Trades":
            "Trades",
        "Blacklist":
            "Blacklist",
        "Invention settings":
            "Invention-Einstellungen",
        "FINE FILTERS":
            "FEINFILTER",
        "CAPITAL SHIPS (BUILD COST, NO MARKET PRICE)":
            "CAPITAL-SCHIFFE (BAUKOSTEN, KEIN MARKTPREIS)",
        # Sitzung 17: Fortschritt beim Rezeptdaten-Download
        "Unpacking and importing \u2026":
            "Entpacken und Einlesen \u2026",
        "Downloading \u2026 {n} of {total} MB":
            "Lade herunter \u2026 {n} von {total} MB",
        "Downloading \u2026 {n} MB":
            "Lade herunter \u2026 {n} MB",
        # Sitzung 17: Verlaufsladen fortsetzen / stoppen
        "Stop loading histories":
            "Verlaufsladen stoppen",
        "Continuing to load price histories from last time \u2026":
            "Setze das Laden der Preisverl\u00e4ufe vom letzten Mal fort \u2026",
        "Stop loading histories?":
            "Verlaufsladen stoppen?",
        "Without the missing price histories, Daytrade, Swing Trade and Regional Trading stay thin, and the Build tab rates demand as unknown.\n\nIf you stop now, the loading will NOT continue on its own \u2013 normal deal runs only add about 350 histories each.\nEverything fetched so far stays saved.\n\nStop anyway?":
            "Ohne die fehlenden Preisverl\u00e4ufe bleiben Daytrade, Swing Trade und Regional Trading d\u00fcnn, und der Bauen-Tab bewertet den Absatz als unbekannt.\n\nWenn du jetzt stoppst, l\u00e4dt es NICHT von selbst weiter \u2013 normale Deals-L\u00e4ufe holen nur je etwa 350 Verl\u00e4ufe dazu.\nAlles bisher Geholte bleibt gespeichert.\n\nTrotzdem stoppen?",
        "Stop":
            "Stoppen",
        "Keep loading":
            "Weiterladen",
        "Stopping \u2026 what was fetched stays saved.":
            "Stoppe \u2026 bisher Geholtes bleibt gespeichert.",
        # Sitzung 17: Bau-Strukturen aus Funden anlegen
        "Create entries":
            "Eintr\u00e4ge anlegen",
        "Only save as locations":
            "Nur als Orte speichern",
        "\n\nCreate build-structure entries for them? Name, type, system, security, cost index and the link are filled in \u2013 you only add the rigs. (Only engineering complexes and refineries; citadels are skipped.)":
            "\n\nBau-Struktur-Eintr\u00e4ge daf\u00fcr anlegen? Name, Typ, System, Sicherheit, Kostenindex und die Verkn\u00fcpfung werden ausgef\u00fcllt \u2013 du tr\u00e4gst nur noch die Rigs ein. (Nur Engineering Complexes und Refineries; Citadels werden \u00fcbersprungen.)",
        "already linked":
            "schon verkn\u00fcpft",
        "not an engineering complex or refinery":
            "kein Engineering Complex und keine Refinery",
        "Build structures created":
            "Bau-Strukturen angelegt",
        "Created:":
            "Angelegt:",
        "Skipped:":
            "\u00dcbersprungen:",
        "\n\nStill to do: enter the rigs \u2013 click \u201eEdit\u201c on each structure.":
            "\n\nNoch zu tun: die Rigs eintragen \u2013 bei jeder Struktur auf \u201eBearbeiten\u201c klicken.",
        "Could not load the structure details: ":
            "Struktur-Details konnten nicht geladen werden: ",
        "These can become build structures:":
            "Daraus k\u00f6nnen Bau-Strukturen werden:",
        # Sitzung 17: Update-Meldung mit Knoepfen
        "There is a newer version of {name}.\n\nYour version: {own}\nOn GitHub: {new}\n\nThe tool does NOT update itself: download the new EXE and replace the old one. Your settings and your journal stay \u2013 they live elsewhere.\n\nQuestions? Ask on Discord.":
            "Es gibt eine neuere Version von {name}.\n\nDeine Version: {own}\nAuf GitHub: {new}\n\nDas Werkzeug aktualisiert sich NICHT selbst: neue EXE herunterladen und die alte ersetzen. Einstellungen und Journal bleiben \u2013 sie liegen woanders.\n\nFragen? Frag im Discord.",
        "Open download page":
            "Download-Seite \u00f6ffnen",
        # Sitzung 17: Spalte Gewinn/m3 in My blueprints
        "Profit per unit \u00f7 packaged volume of the finished item (m\u00b3). Freight thinking: what a full cargo hold earns. \u2013 when the volume is unknown.":
            "Gewinn pro St\u00fcck \u00f7 verpacktes Volumen des fertigen Items (m\u00b3). Frachtdenken: was ein voller Frachtraum einbringt. \u2013 wenn das Volumen unbekannt ist.",
        "Could not load the orders: ":
            "Die Orders konnten nicht geladen werden: ",
        # Sitzung 17: Hinweis auf Orders an anderen Orten
        "{n} more orders are at other locations: {list} \u2013 switch the hub at the top to see them.":
            "{n} weitere Orders liegen an anderen Orten: {list} \u2013 stelle oben den Hub um, um sie zu sehen.",
        "Open releases page":
            "Releases-Seite \u00f6ffnen",
        "Could not check ({why}).":
            "Pr\u00fcfung nicht m\u00f6glich ({why}).",
        # Sitzung 17: kurz statt Roman (Nutzer)
        "Purchase price unknown \u2013 no margin shown.":
            "Kaufpreis unbekannt \u2013 keine Marge.",
        "Purchase price unknown.":
            "Kaufpreis unbekannt.",
        "\u26a0 Purchase price unknown \u2013 no loss check. Check the price yourself.":
            "\u26a0 Kaufpreis unbekannt \u2013 keine Verlust-Pr\u00fcfung. Preis selbst pr\u00fcfen.",
        # Sitzung 17: klarere Namen fuer die Paste-Stock-Haken
        "Keep after ESI updates":
            "Behalten, auch nach ESI-Aktualisierung",
        "Ignore ESI \u2013 use this list only":
            "ESI ignorieren \u2013 nur diese Liste",
        "T1 hulls & bases":
            "T1-H\u00fcllen & Basis-Items",
        "Plan frozen \u2013 this would change the plan. Unfreeze first ( button).":
            "Plan eingefroren \u2013 das w\u00fcrde den Plan \u00e4ndern. Erst auftauen ( Knopf).",
        # Sitzung 17: Warnung vor dem Auftauen
        "Unfreeze plan?":
            "Plan auftauen?",
        "Unfreeze":
            "Auftauen",
        "Keep frozen":
            "Eingefroren lassen",
        "The plan is recalculated with today's prices and stock. Build/buy decisions and the run planner order can change \u2013 material you already bought may then no longer fit the plan.\n\nUnfreeze?":
            "Der Plan wird mit den heutigen Preisen und Best\u00e4nden neu gerechnet. Kauf/Bau-Entscheidungen und die Reihenfolge im Runplaner k\u00f6nnen sich \u00e4ndern \u2013 schon gekauftes Material passt dann eventuell nicht mehr zum Plan.\n\nAuftauen?",
        "several":
            "mehrere",
        "GitHub was not reachable.":
            "GitHub war nicht erreichbar.",
        "Reactions \u2013 Intermediate":
            "Reaktionen \u2013 Intermediate",
        "Reactions \u2013 Composite":
            "Reaktionen \u2013 Composite",
        "Build components (advanced/capital/hybrid components etc.).":
            "Baukomponenten (Advanced/Capital/Hybrid Components etc.).",
        "Build plan \u201e{name}\u201c saved \u2713":
            "Bauplan \u201e{name}\u201c gespeichert \u2713",
        "material reserved":
            "Material reserviert",
        # Sitzung 17: Hinweise in leeren Listen
        "No market data yet":
            "Noch keine Marktdaten",
        "No blueprints loaded yet":
            "Noch keine Blaupausen geladen",
        "Nothing here yet":
            "Noch nichts vorhanden",
        "Loading your portfolio \u2026":
            "Portfolio wird geladen \u2026",
        "Wallet, assets, orders and prices are being fetched from ESI.":
            "Wallet, Bestand, Orders und Preise kommen gerade von ESI.",
        "\u27f3 Loading portfolio + prices \u2026 {s} s":
            "\u27f3 Lade Portfolio + Preise \u2026 {s} s",
        "\u27f3 Market scan \u2026 {s} s":
            "\u27f3 Markt-Scan \u2026 {s} s",
        "The market scan runs in the background. Daytrade, Swing Trade and Regional Trading fill in afterwards.":
            "Der Markt-Scan l\u00e4uft im Hintergrund. Daytrade, Swing Trade und Regional Trading f\u00fcllen sich danach.",
        "Wallet, assets, orders and prices are being fetched from ESI in the background. You can already use the tool.":
            "Wallet, Bestand, Orders und Preise werden im Hintergrund von ESI geholt. Du kannst das Tool schon benutzen.",
        "No transactions yet":
            "Noch keine Transaktionen",
        "Link a character under \u201eCharacters\u201c.":
            "Charakter unter \u201eCharaktere\u201c verlinken.",
        # Sitzung 17: Tutorial
        "Tutorial":
            "Tutorial",
        "Guided tour through EVE-MoMa. You can keep working while it runs.":
            "Gef\u00fchrte Tour durch EVE-MoMa. Du kannst nebenher weiterarbeiten.",
        "What would you like to see first?":
            "Was m\u00f6chtest du zuerst sehen?",
        "Trading":
            "Trading",
        "Would you like to see the other part as well?":
            "M\u00f6chtest du auch den anderen Teil sehen?",
        "No thanks":
            "Nein danke",
        "Would you like a short guided tour?":
            "M\u00f6chtest du eine kurze gef\u00fchrte Tour?",
        "Yes":
            "Ja",
        "No":
            "Nein",
        "You can start the tour again any time with the button on the bottom left.":
            "Du kannst die Tour jederzeit \u00fcber den Knopf links unten neu starten.",
        "Back":
            "Zur\u00fcck",
        "Next":
            "Weiter",
        "Finish":
            "Fertig",
        "Cancel tour":
            "Tour abbrechen",
        # Sitzung 17: Tutorial-Schritte
        "Welcome to EVE-MoMa":
            "Willkommen bei EVE-MoMa",
        "This tour shows you the industry side. You can set things up as you go.":
            "Diese Tour zeigt dir die Industrieseite. Du kannst nebenher gleich einrichten.",
        "The Industry tab":
            "Der Bauen-Tab",
        "Everything about building lives here. The panel on the right is your starting point.":
            "Alles rund ums Bauen steckt hier. Die Leiste rechts ist dein Ausgangspunkt.",
        "Structures first":
            "Zuerst die Strukturen",
        "Without a structure nothing is calculated correctly. Add yours now - and do not forget to enter the rigs, they change your material use.":
            "Ohne Struktur rechnet nichts richtig. Lege deine jetzt an - und vergiss die Rigs nicht, sie \u00e4ndern deinen Materialverbrauch.",
        "Finds what is worth building right now, from the market data.":
            "Findet aus den Marktdaten, was sich gerade zu bauen lohnt.",
        "Create a build plan":
            "Einen Bauplan anlegen",
        "Three ways: right-click a blueprint in the scanner or in My blueprints, or click 'New build plan' here.":
            "Drei Wege: Rechtsklick auf eine Blaupause im Scanner oder in Meine Blaupausen, oder hier auf 'Neuer Bauplan'.",
        "The full tree from the finished item down to ore. Blue means you build it, grey means you buy it.":
            "Der ganze Baum vom fertigen Item bis zum Erz. Blau hei\u00dft bauen, grau hei\u00dft kaufen.",
        "Decides what you make yourself. 'Production depth' switches whole stages at once.":
            "Entscheidet, was du selbst herstellst. 'Fertigungstiefe' schaltet ganze Stufen auf einmal um.",
        "For T2: how many attempts you need, which decryptor, and how many datacores that costs.":
            "F\u00fcr T2: wie viele Versuche du brauchst, welcher Decryptor, und wie viele Datacores das kostet.",
        "Which of your blueprints the plan uses, with their ME and TE.":
            "Welche deiner Blaupausen der Plan benutzt, mit ihrem ME und TE.",
        "What is missing and what is covered. 'Create shopping list' puts exactly that into your cart.":
            "Was fehlt und was gedeckt ist. 'Einkaufsliste erstellen' legt genau das in deinen Wagen.",
        "Splits the jobs across your characters by skills and free job slots.":
            "Verteilt die Jobs auf deine Charaktere, nach Skills und freien Job-Slots.",
        "Save and freeze":
            "Speichern und einfrieren",
        "Freezing keeps prices and quantities of the day you bought. A frozen plan cannot be changed until you unfreeze it.":
            "Einfrieren h\u00e4lt Preise und Mengen vom Einkaufstag fest. Ein eingefrorener Plan l\u00e4sst sich erst nach dem Auftauen \u00e4ndern.",
        "That is the industry side":
            "Das war die Industrieseite",
        "You can start this tour again any time with the button on the bottom left.":
            "Du kannst diese Tour jederzeit \u00fcber den Knopf links unten neu starten.",
        "This tour shows you the trading side in a few short steps. You can keep clicking in the tool while it runs.":
            "Diese Tour zeigt dir in wenigen Schritten die Handelsseite. Du kannst nebenher weiterklicken.",
        "Your hub":
            "Dein Hub",
        "This fetches the prices. Without it the deal lists stay empty.":
            "Das holt die Preise. Ohne ihn bleiben die Deal-Listen leer.",
        "Shows you when to sell an item and when to hold it a little longer until the margin is right \u2013 you read that off the \u201eStatus\u201c column.":
            "Zeigt dir, wann du ein Item verkaufen solltest und wann du es noch etwas h\u00e4ltst, bis die Marge stimmt \u2013 abzulesen in der Spalte \u201eStatus\u201c.",
        "Real profit per item after your sales tax and broker fees.":
            "Echter Gewinn je Item, nach deiner Steuer und den Broker-Geb\u00fchren.",
        "What is ready to be sold, with the price it should fetch.":
            "Was verkaufsbereit ist, mit dem Preis, den es bringen sollte.",
        "Shows which of your orders were undercut and what the new price would be.":
            "Zeigt, welche deiner Orders unterboten wurden und welcher Preis n\u00f6tig w\u00e4re.",
        "Every buy and sell EVE reports. This is where profit comes from.":
            "Jeder Kauf und Verkauf, den EVE meldet. Daraus entsteht der Gewinn.",
        "The price of a single item over time - useful before you commit to a big buy.":
            "Der Preis eines Items \u00fcber die Zeit - n\u00fctzlich vor einem gro\u00dfen Einkauf.",
        "Buy and sell at the SAME station: you profit from the gap between buy and sell orders.":
            "Kaufen und verkaufen an DERSELBEN Station: du verdienst an der Spanne zwischen Kauf- und Verkaufsorder.",
        "Buy low now, sell later when the price returns to normal. Needs patience, not a second station.":
            "Jetzt g\u00fcnstig kaufen, sp\u00e4ter verkaufen, wenn der Preis zur\u00fcckkommt. Braucht Geduld, keine zweite Station.",
        "That is the trading side":
            "Das war die Handelsseite",
        "Open a build plan now":
            "\u00d6ffne jetzt einen Bauplan",
        "Do the highlighted step first \u2013 then this continues by itself.":
            "Mach zuerst den blinkenden Schritt \u2013 dann geht es von selbst weiter.",
        "Everything is calculated for this market. Pick the station you trade at - your own structures can be added later.":
            "Alles wird f\u00fcr diesen Markt gerechnet. W\u00e4hle die Station, an der du handelst - eigene Strukturen kommen sp\u00e4ter dazu.",
        "Link your characters here - wallet, assets and orders come from them. Only once a character sits in a player structure can you add it as a hub with \u201e+ Structure\u201c above.":
            "Hier verlinkst du deine Charaktere - Wallet, Bestand und Orders kommen von ihnen. Erst wenn ein Charakter in einer Player-Struktur sitzt, kannst du sie oben mit \u201e+ Structure\u201c als Hub hinzuf\u00fcgen.",
        "Your buying list for TRADING. Right-click an item in Daytrade, Swing or Regional to put it in here.":
            "Deine Einkaufsliste f\u00fcrs TRADING. Rechtsklick auf ein Item in Daytrade, Swing oder Regional legt es hier hinein.",
        "Sales tax, broker fees and your structures. Worth a look once.":
            "Steuer, Broker-Geb\u00fchren und deine Strukturen. Einmal ansehen lohnt sich.",
        # Sitzung 17: Tutorial-Schritte Handels-Tabs
        "Strategy and presets":
            "Strategie und Presets",
        "The two dropdowns decide WHAT is searched for. Start with a preset - it sets all the filters below for you.":
            "Die zwei Auswahlfelder entscheiden, WONACH gesucht wird. Fang mit einem Preset an - es setzt alle Filter darunter f\u00fcr dich.",
        "Same idea as in Daytrade: the preset sets the filters. Here they look for prices that dropped below their usual level.":
            "Wie bei Daytrade: das Preset setzt die Filter. Hier suchen sie Preise, die unter ihr \u00fcbliches Niveau gefallen sind.",
        "Two hubs instead of one":
            "Zwei Hubs statt einem",
        "Different from the other two: here you pick where you BUY and where you SELL. The hub at the top is not used.":
            "Anders als bei den anderen zwei: hier w\u00e4hlst du, wo du KAUFST und wo du VERKAUFST. Der Hub oben wird nicht benutzt.",
        "The preset sets the filters - for example freight-efficient, which prefers profit per cubic metre.":
            "Das Preset setzt die Filter - zum Beispiel frachteffizient, das Gewinn je Kubikmeter bevorzugt.",
        "Nothing loads without a hub: the list is built for the hub selected at the top.":
            "Ohne Hub l\u00e4dt nichts: die Liste wird f\u00fcr den Hub gebaut, der oben ausgew\u00e4hlt ist.",
        "Same here: without a hub selected at the top nothing is loaded.":
            "Auch hier: ohne oben gew\u00e4hlten Hub wird nichts geladen.",
        "Buy in one region, sell in another. You can enter your own freight cost per m\u00b3 - the profit is calculated after it.":
            "In einer Region kaufen, in einer anderen verkaufen. Du kannst deine eigenen Frachtkosten je m\u00b3 eintragen - der Gewinn wird danach gerechnet.",
        "Who buys, who sells":
            "Wer kauft, wer verkauft",
        "The character who buys and the one who sells - their skills set the fees. The same character twice is fine.":
            "Der Charakter, der kauft, und der, der verkauft - ihre Skills bestimmen die Geb\u00fchren. Zweimal derselbe ist auch in Ordnung.",
        "Nothing loads until BOTH hubs are picked. The hub at the top does not matter here.":
            "Es l\u00e4dt erst, wenn BEIDE Hubs gew\u00e4hlt sind. Der Hub oben spielt hier keine Rolle.",
        "Click the highlighted button and type an item, for example \u201eRetribution\u201c - the next steps then explain the tabs on YOUR plan.":
            "Klick den blinkenden Knopf und tippe ein Item, zum Beispiel \u201eRetribution\u201c - die n\u00e4chsten Schritte erkl\u00e4ren dann die Reiter an DEINEM Plan.",
        "The button on this page fetches YOUR blueprints from EVE; the one at the top loads the recipe data. It also shows what the T2 version of your T1 blueprint would earn.":
            "Der Knopf auf dieser Seite holt DEINE Blaupausen aus EVE, der oben l\u00e4dt die Rezeptdaten. Es zeigt auch, was die T2-Fassung deiner T1-Blaupause bringen w\u00fcrde.",
        # ---- Sitzung 22: Texte, die bis dahin DEUTSCH in der englischen
        # Oberflaeche standen. Kein Scanner meldete sie - sie laufen ueber
        # eigene Helfer (_flash_tip, parts.append, _dv_label) oder ihre
        # Woerter fehlten in de_scan4s Handliste. Gefunden hat sie
        # de_scan5.py, der sein Vokabular aus genau diesem Katalog zieht.
        "{v}% success": "{v}% Erfolg",
        "Material cost ({me}% ME)": "Materialkosten ({me}% ME)",
        "No decryptor": "Kein Decryptor",
        "realistically you sell ~{n}/week": "realistisch verkaufst du ~{n}/Woche",
        "Best profit: {qty} \u00b7 {isk}": "Bester Gewinn: {qty} \u00b7 {isk}",
        "Profitable throughout the calculated range (up to {qty})":
            "Im gerechneten Bereich durchgehend profitabel (bis {qty})",
        "Blueprint name copied: {name}": "Blueprint-Name kopiert: {name}",
        "applies \u2713": "gilt \u2713",
        " (+{n} more)": " (+{n} weitere)",
        "= total build cost": "= Baukosten gesamt",
        "No characters / client ID": "Keine Charaktere / Client-ID",
        "{label}: {cov}/{tot} items covered": "{label}: {cov}/{tot} Items abgedeckt",
        "Mfg. {mfg} \u00b7 React. {react}": "Fert. {mfg} \u00b7 Reakt. {react}",
        # emm327 Industry-Jobs-Seite
        "Industry jobs": "Industrie-Jobs",
        "INDUSTRY JOBS": "INDUSTRIE-JOBS",
        "All linked characters: busy and free job slots, and every running job with what it builds and how long it still takes. A finished job keeps its slot until you deliver it.":
            "Alle verlinkten Charaktere: belegte und freie Job-Slots und jeder laufende Job \u2013 was er baut und wie lange er noch braucht. Ein fertiger Job belegt seinen Slot, bis du ihn ablieferst.",
        "Reverse engineering": "Reverse Engineering",
        "Loading jobs failed.": "Laden der Jobs fehlgeschlagen.",
        "Loading jobs \u2026": "Lade Jobs \u2026",
        "ready to deliver \u2713": "fertig \u2013 abliefern \u2713",
        "paused": "pausiert",
        "ESI error: {e}": "ESI-Fehler: {e}",
        "no running jobs": "keine laufenden Jobs",
        "Mfg.": "Fert.",
        "React.": "Reakt.",
        "Science": "Science",
        "\u2713 {n} ready to deliver": "\u2713 {n} fertig \u2013 abliefern",
        "{n} job(s) \u00b7 {r} runs": "{n} Job(s) \u00b7 {r} Runs",
        "as of {zeit}": "Stand {zeit}",
        "{name} (fixed assignment)": "{name} (fest zugewiesen)",
        "Profile \u201e{name}\u201c saved \u2713": "Profil \u201e{name}\u201c gespeichert \u2713",
        "{n} copied \u2713": "{n} kopiert \u2713",
        "copied \u2713": "kopiert \u2713",
        "copied: {name}": "kopiert: {name}",
        "\u2212{v}% time": "\u2212{v}% Zeit",
        " (automatic)": " (automatisch)",
        "(example)": "(Beispiel)",
        "missing item(s)": "fehlende Position(en)",
        "manual/portfolio": "manuell/Portfolio",
        "Nothing to adjust \u2713": "Nichts nachzubessern \u2713",
        "{n} prices copied \u2713": "{n} Preise kopiert \u2713",
        "Nothing to process \u2713": "Nichts abzuarbeiten \u2713",
        "Nothing to copy": "Nichts zu kopieren",
        "{item} \u00b7 {days} days history \u00b7 \u00d8 {avg} \u00b7 \u03a3 volume {vol}":
            "{item} \u00b7 {days} Tage Historie \u00b7 \u00d8 {avg} \u00b7 \u03a3 Volumen {vol}",
        # Einzelne deutsche Woerter, die de_scan5 in zweiter Runde fand -
        # sie standen ohne t() direkt in einer Tabellenzelle oder Statuszeile.
        "{n} shown": "{n} sichtbar",
        "{n} ticked off": "{n} abgehakt",
        "{n} hits": "{n} Treffer",
        "Daily volume": "Tagesvolumen",
        "inventable": "erfindbar",
        "Build time": "Bauzeit",
        "Invention time": "Invention-Zeit",
        "Gold": "Gold",
        "Silver": "Silber",
        "Bronze": "Bronze",
        "{n} trip(s) \u00e0 ": "{n} Fahrt(en) \u00e0 ",
        # Zweite Runde (de_scan6, Variablen-Verfolgung): Texte, die erst
        # ueber eine lokale Variable in die Anzeige wandern.
        "assigned": "zugewiesen",
        "transactions.csv": "transaktionen.csv",
        "{n} runs in reserve": "{n} Runs Reserve",
        # Handsortierung der Bauplan-Karten (Nutzer-Wunsch 15.09.2026).
        "Arrange plans yourself": "Bauplaene selber anordnen",
        # HIER STAND DIE WARNUNG BEIM AUSSCHALTEN DER HANDSORTIERUNG.
        # RAUS (Nutzer, 15.09.2026): sie warnte davor, dass die eigene
        # Reihenfolge gleich umgeworfen wird - seit "Sort by progress" ein
        # eigener Knopf ist, passiert das nicht mehr.
        # Warnung vor dem New-Eden-Contract-Scan (Nutzer, 15.09.2026).
        "This searches the public contracts of ALL regions and then "
        "looks into every hit individually \u2013 that takes SEVERAL "
        "MINUTES (around five is normal).\n\nIt runs in the "
        "background, you can keep working. Start now?":
            "Das durchsucht die \u00f6ffentlichen Contracts ALLER Regionen und "
            "sieht danach in jeden Treffer einzeln hinein \u2013 das dauert "
            "MEHRERE MINUTEN (f\u00fcnf sind normal).\n\nEs l\u00e4uft im "
            "Hintergrund, du kannst weiterarbeiten. Jetzt starten?",
        # Anordnen-Modus und Automatik sind seit 15.09.2026 getrennt: der
        # Modus laesst nur noch ZIEHEN zu, zurueck zur Fortschritts-Folge
        # geht es allein ueber diesen Knopf.
        "Drag the cards into the order you want with the left mouse "
        "button held down; the wheel keeps scrolling, and the buttons on "
        "the cards keep working. Your order is kept – also after closing "
        "the program and after an update. Switching this off only stops "
        "the dragging; your order stays until you click „Sort by "
        "progress“.":
            "Zieh die Karten mit gedrückter linker Maustaste in die "
            "Reihenfolge, die du willst; das Mausrad scrollt weiter, und die "
            "Knöpfe auf den Karten funktionieren weiterhin. Deine "
            "Reihenfolge bleibt erhalten – auch nach dem Schließen und "
            "nach einem Update. Ausschalten beendet nur das Ziehen; deine "
            "Reihenfolge bleibt, bis du „Nach Fortschritt sortieren“ "
            "drückst.",
        "Sort by progress": "Nach Fortschritt sortieren",
        # Rueckfrage beim Verlassen der Einstellungsseite (Nutzer, 15.09.2026).
        "Unsaved settings": "Nicht gespeicherte Einstellungen",
        "You changed settings but did not save them.":
            "Du hast Einstellungen geändert und nicht gespeichert.",
        "Without saving they have no effect – the program keeps "
        "working with the old values.":
            "Ohne Speichern wirken sie nicht – das Programm rechnet weiter "
            "mit den alten Werten.",
        "Save and continue": "Speichern und weiter",
        "Discard changes": "Änderungen verwerfen",
        "Back to settings": "Zurück zu den Einstellungen",
        "Sorts the cards by progress again: started plans on top, the "
        "furthest along first, finished ones at the bottom. Your own "
        "order stays saved – drag a card again and it applies once more.":
            "Sortiert die Karten wieder nach Fortschritt: angefangene "
            "Pläne oben, der am weitesten fortgeschrittene zuerst, fertige "
            "unten. Deine eigene Reihenfolge bleibt gespeichert – zieh "
            "eine Karte, dann gilt sie wieder.",
        "No progress known yet – click „Check finished status (ESI)“ "
        "first.":
            "Noch kein Fortschritt bekannt – drück zuerst „Fertig-Status "
            "prüfen (ESI)“.",
        # Der sichtbare Contract-Knopf im Bauplan (Nutzer-Wunsch 15.09.2026).
        "Load contract prices": "Contract-Preise laden",
        "There is no market price for this item \u2013 capitals are hardly "
        "ever sold through sell orders. This takes the median of the "
        "public New Eden contracts. The saved scan is used first; only "
        "an item that is missing from it is fetched fresh.":
            "F\u00fcr dieses Item gibt es keinen Marktpreis \u2013 Capitals werden "
            "kaum \u00fcber Sell-Orders verkauft. Das hier nimmt den Median der "
            "\u00f6ffentlichen New-Eden-Contracts. Zuerst gilt der gespeicherte "
            "Scan; nur ein Item, das darin fehlt, wird frisch geholt.",
        # Multi-Bauplan / Buendel (1.0.9, mw_multi_bauplan.py).
        "Multi build plan": "Multi-Bauplan",
        "Multi: {names}": "Multi: {names}",
        "Bundle:": "B\u00fcndel:",
        "{n} being built": "{n} im Bau",
        "{n} single plan(s) unfrozen / released \u2013 build and buy through "
        "the multi build plan from now on.":
            "{n} Einzelplan/-pl\u00e4ne aufgetaut / freigegeben \u2013 ab jetzt "
            "\u00fcber den Multi-Bauplan bauen und einkaufen.",
        # Vergleich allein / im Buendel in der Endprodukte-Karte (26.09.2026).
        # Invention-Tab je Ende (26.09.2026).
        # Endprodukt an einen Plan haengen (26.09.2026).
        "\u2026 or take a saved build plan (open, not reserved):":
            "\u2026 oder einen gespeicherten Bauplan \u00fcbernehmen (offen, nicht "
            "reserviert):",
        "(none \u2013 use the search above)":
            "(keiner \u2013 Suche oben benutzen)",
        "Add to multi build plan":
            "Zum Multi-Bauplan hinzuf\u00fcgen",
        "Add end product":
            "Endprodukt hinzuf\u00fcgen",
        "Add":
            "Hinzuf\u00fcgen",
        "Add build plan": "Bauplan hinzuf\u00fcgen",
        "Open the multi build plan \u201e{plan}\u201c now?":
            "Multi-Bauplan \u201e{plan}\u201c jetzt \u00f6ffnen?",
        "How many of each?":
            "Wie viele jeweils?",
        "New multi build plan":
            "Neuer Multi-Bauplan",
        "Select at least two different items for a multi build plan.":
            "F\u00fcr einen Multi-Bauplan mindestens zwei verschiedene Items markieren.",
        "Multi build plan with {n} end products opened \u2013 save it to keep it.":
            "Multi-Bauplan mit {n} Endprodukten ge\u00f6ffnet \u2013 speichern, um ihn zu behalten.",
        "{n} end products added to \u201e{plan}\u201c.":
            "{n} Endprodukte zu \u201e{plan}\u201c hinzugef\u00fcgt.",
        "Add build plan\u2026":
            "Bauplan hinzuf\u00fcgen\u2026",
        "(reserved or completed)":
            "(reserviert oder abgeschlossen)",
        "(part of a multi build plan)":
            "(Teil eines Multi-Bauplans)",
        "New multi build plan from selection ({n})":
            "Neuer Multi-Bauplan aus Auswahl ({n})",
        "Add {n} selected to multi build plan":
            "{n} markierte zum Multi-Bauplan hinzuf\u00fcgen",
        "Add another build plan (an item or a saved plan) to this one \u2013 a "
        "single plan becomes a bundle, shared intermediates are built once. "
        "A saved plan that is frozen, reserved or completed stays as it is "
        "\u2013 the addition goes into a new copy.":
            "Einen weiteren Bauplan (ein Item oder einen gespeicherten Plan) an "
            "diesen h\u00e4ngen \u2013 ein Einzelplan wird damit zum B\u00fcndel, "
            "gemeinsame Zwischenprodukte werden einmal gebaut. Ein gespeicherter "
            "Plan, der eingefroren, reserviert oder abgeschlossen ist, bleibt, wie "
            "er ist \u2013 die Erg\u00e4nzung kommt in eine neue Kopie.",
        "{name} (copy)":
            "{name} (Kopie)",
        "Added to a copy of \u201e{plan}\u201c \u2013 the saved plan stays unchanged. "
        "New plan: \u201e{neu}\u201c.":
            "In eine Kopie von \u201e{plan}\u201c aufgenommen \u2013 der gespeicherte Plan "
            "bleibt unver\u00e4ndert. Neuer Plan: \u201e{neu}\u201c.",
        "\u201e{name}\u201c \u00d7 {n} added to a copy of \u201e{plan}\u201c \u2013 the saved "
        "plan stays unchanged. Save the copy to keep it.":
            "\u201e{name}\u201c \u00d7 {n} in eine Kopie von \u201e{plan}\u201c aufgenommen "
            "\u2013 der gespeicherte Plan bleibt unver\u00e4ndert. Zum Behalten die "
            "Kopie speichern.",
        "\u201e{name}\u201c \u00d7 {n} added \u2013 save the plan to keep it.":
            "\u201e{name}\u201c \u00d7 {n} hinzugef\u00fcgt \u2013 zum Behalten den Plan speichern.",
        "\u201e{name}\u201c \u00d7 {n} added to \u201e{plan}\u201c \u2013 it is a bundle now.":
            "\u201e{name}\u201c \u00d7 {n} zu \u201e{plan}\u201c hinzugef\u00fcgt \u2013 ab jetzt "
            "ein B\u00fcndel.",
        "bundle, {n} end products":
            "B\u00fcndel, {n} Endprodukte",
        "(no saved build plan yet)":
            "(noch kein gespeicherter Bauplan)",
        # Endprodukt aus dem offenen Buendel nehmen (26.09.2026).
        "Remove from bundle":
            "Aus dem B\u00fcndel nehmen",
        "Remove this end product from the bundle. The window reopens with "
        "the remaining ones; save the plan to keep it.":
            "Dieses Endprodukt aus dem B\u00fcndel nehmen. Das Fenster \u00f6ffnet "
            "sich mit den \u00fcbrigen neu; zum Behalten den Plan speichern.",
        "A bundle needs at least two end products \u2013 use \u201eEdit\u201c in My "
        "build plans to dissolve it.":
            "Ein B\u00fcndel braucht mindestens zwei Endprodukte \u2013 zum "
            "Aufl\u00f6sen \u201eBearbeiten\u201c in Meine Baupl\u00e4ne.",
        "Remove \u201e{name}\u201c from this bundle?\n\nNothing is saved until you "
        "click \u201eSave build plan\u201c.":
            "\u201e{name}\u201c aus diesem B\u00fcndel nehmen?\n\nGespeichert wird erst "
            "mit \u201eBauplan speichern\u201c.",
        "\u201e{name}\u201c removed from the bundle \u2013 save the plan to keep it.":
            "\u201e{name}\u201c aus dem B\u00fcndel genommen \u2013 zum Behalten den "
            "Plan speichern.",
        # Blaupausen im Industrie-Job (26.09.2026).
        "{n} (+{j} in job)":
            "{n} (+{j} im Job)",
        "Not available \u2013 in an industry job:":
            "Nicht verf\u00fcgbar \u2013 in einem Industrie-Job:",
        "{activity} until {end}":
            "{activity} bis {end}",
        "TE research":
            "TE-Forschung",
        "ME research":
            "ME-Forschung",
        "Copying":
            "Kopieren",
        "Job":
            "Job",
        "Blueprints that are in an industry job right now (research, copy, "
        "invention, manufacturing) are shown as \u201ein job\u201c and do not "
        "count as available \u2013 neither here nor in the build plan.":
            "Blaupausen, die gerade in einem Industrie-Job stecken (Forschung, "
            "Kopie, Invention, Fertigung), stehen als \u201eim Job\u201c da und "
            "z\u00e4hlen nicht als verf\u00fcgbar \u2013 weder hier noch im Bauplan.",
        "{n} of them are built by this plan itself \u2013 nothing to buy, the "
        "open runs are in the run planner.":
            "{n} davon baut dieser Plan selbst \u2013 nichts zu kaufen, die "
            "offenen Runs stehen im Runplaner.",
        "{n} end product(s) belong to this bundle \u2013 show or hide them":
            "{n} Endprodukt(e) geh\u00f6ren zu diesem B\u00fcndel \u2013 ein- oder ausblenden",
        "{n} build plans": "{n} Baupl\u00e4ne",
        "Profit/unit, net": "Gewinn/Stk, netto",
        "Rigs": "Rigs",
        "Freeze build plan?": "Bauplan einfrieren?",
        "Why reserve? Without it, OTHER build plans treat this material as free "
        "and use it \u2013 then it is missing in the middle of your build.":
            "Warum reservieren? Ohne Reservierung halten ANDERE Baupl\u00e4ne dieses "
            "Material f\u00fcr frei und verbrauchen es \u2013 dann fehlt es mitten in "
            "deinem Bau.",
        "Reserve {n} material types for \u201e{name}\u201c?":
            "{n} Materialarten f\u00fcr \u201e{name}\u201c reservieren?",
        "These plans need the same materials:":
            "Diese Baupl\u00e4ne brauchen dieselben Materialien:",
        "Changeable any time with the lock on the plan card.":
            "Jederzeit \u00e4nderbar mit dem Schloss auf der Plan-Karte.",
        "Suggest end products for this plan": "Endprodukte f\u00fcr diesen Plan vorschlagen",
        "Profitable end products of the same tech level from your blueprints "
        "whose margin is at least that of this plan \u2013 sorted by shared "
        "materials. Right-click adds them to this plan.":
            "Lohnende Endprodukte derselben Tech-Stufe aus deinen Blaupausen, deren "
            "Marge mindestens so hoch ist wie die dieses Plans \u2013 sortiert nach "
            "gemeinsamen Materialien. Rechtsklick f\u00fcgt sie diesem Plan hinzu.",
        "Suggestions for this plan": "Vorschl\u00e4ge f\u00fcr diesen Plan",
        "Shared": "Gemeinsam",
        "Load your blueprints in \u201eMy Blueprints\u201c first \u2013 the suggestions "
        "come from their profit calculation.":
            "Lade zuerst deine Blaupausen in \u201eMy Blueprints\u201c \u2013 die "
            "Vorschl\u00e4ge kommen aus deren Gewinnrechnung.",
        "No end product of your blueprints fits: same tech level ({tech}), "
        "profitable and a margin of at least {m} %.":
            "Kein Endprodukt deiner Blaupausen passt: gleiche Tech-Stufe ({tech}), "
            "lohnend und eine Marge von mindestens {m} %.",
        "{n} end products from your blueprints, tech level {tech}, margin at least "
        "{m} % (this plan) \u2013 so the bundle margin cannot drop. Right-click adds "
        "them to this plan.":
            "{n} Endprodukte aus deinen Blaupausen, Tech-Stufe {tech}, Marge mindestens "
            "{m} % (dieser Plan) \u2013 so kann die B\u00fcndel-Marge nicht sinken. "
            "Rechtsklick f\u00fcgt sie diesem Plan hinzu.",
        "Add to this build plan ({n})": "Zu diesem Bauplan hinzuf\u00fcgen ({n})",
        "Delete build plan?": "Bauplan l\u00f6schen?",
        "Are you sure you want to delete the build plan \u201e{name}\u201c?":
            "Bist du sicher, dass du den Bauplan \u201e{name}\u201c l\u00f6schen willst?",
        "IMPORTANT: freeze the plan as soon as you have bought the materials!":
            "WICHTIG: Friere den Plan ein, sobald du die Materialien gekauft hast!",
        "\u2212 Freight service": "\u2212 Frachtdienst",
        "of which freight service": "davon Frachtdienst",
        "Includes freight of {isk}: units sold somewhere else than where they "
        "were bought, m\u00b3 \u00d7 your current rate ({satz} ISK/m\u00b3).":
            "Enth\u00e4lt Fracht von {isk}: Stück, die woanders verkauft als "
            "gekauft wurden, m\u00b3 \u00d7 dein aktueller Satz ({satz} ISK/m\u00b3).",
        "Margin after freight of {isk} per unit (units bought away from the hub). "
        "Without freight: {ohne}.":
            "Marge nach Fracht von {isk} je St\u00fcck (St\u00fcck, die nicht am Hub "
            "gekauft wurden). Ohne Fracht: {ohne}.",
        "Only blueprints whose product belongs to this faction. Ships of one "
        "faction often share components and materials \u2013 good for a multi "
        "build plan. Most modules and rigs have no faction.":
            "Nur Blaupausen, deren Produkt zu dieser Fraktion geh\u00f6rt. Schiffe "
            "einer Fraktion teilen oft Komponenten und Materialien \u2013 gut "
            "f\u00fcr einen Multiplan. Die meisten Module und Rigs haben keine "
            "Fraktion.",
        "Already included in the build cost above (\u201eFreight in decision\u201c "
        "is on) \u2013 not deducted a second time.":
            "Steckt schon in den Baukosten dar\u00fcber (\u201eFracht "
            "mitentscheiden\u201c ist an) \u2013 wird nicht ein zweites Mal "
            "abgezogen.",
        "ISK/m\u00b3 \u00d7 volume of the shopping list, deducted from the profit.":
            "ISK/m\u00b3 \u00d7 Volumen der Einkaufsliste, wird vom Gewinn abgezogen.",
        "Freeze \u201e{name}\u201c now?\n\nFreezing fixes quantities, prices and the "
        "run planner split, and from then on your ESI jobs count as progress. "
        "Freeze once you have bought the material \u2013 later via \u201eFreeze "
        "plan \u2013 purchase done\u201c in the plan.":
            "\u201e{name}\u201c jetzt einfrieren?\n\nEinfrieren h\u00e4lt Mengen, "
            "Preise und die Aufteilung im Runplaner fest, und ab dann z\u00e4hlen "
            "deine ESI-Jobs als Fortschritt. Friere ein, sobald du das Material "
            "gekauft hast \u2013 sp\u00e4ter \u00fcber \u201ePlan einfrieren "
            "\u2013 Einkauf erledigt\u201c im Plan.",
        "Net profit per unit divided by this product's cost per unit (incl. "
        "its share of freight and extra costs) \u2013 the same formula as the "
        "margin above.":
            "Nettogewinn je St\u00fcck geteilt durch die Kosten je St\u00fcck "
            "dieses Produkts (inkl. Anteil an Fracht und Extrakosten) \u2013 "
            "dieselbe Formel wie die Marge oben.",
        "Sale price minus sales tax and broker fee ({pct} %), minus this "
        "product's share of the build cost and of freight and extra costs. "
        "Quantity \u00d7 this column, summed over all end products, is the total "
        "profit above.":
            "Verkaufspreis abz\u00fcglich Verkaufssteuer und Broker-Geb\u00fchr "
            "({pct} %), abz\u00fcglich des Anteils dieses Produkts an den "
            "Baukosten und an Fracht und Extrakosten. Menge \u00d7 diese Spalte, "
            "\u00fcber alle Endprodukte summiert, ergibt den Gesamtgewinn oben.",
        "Sum over all end products: {v} ISK \u2013 this is the total profit "
        "above.":
            "Summe \u00fcber alle Endprodukte: {v} ISK \u2013 das ist der "
            "Gesamtgewinn oben.",
        "{n} end product(s) have no sale price \u2013 the sum is therefore "
        "incomplete.":
            "{n} Endprodukte haben keinen Verkaufspreis \u2013 die Summe ist "
            "deshalb unvollst\u00e4ndig.",
        # Rueckfrage VOR dem Bearbeiten eines eingefrorenen/reservierenden
        # Buendels (Nutzer-Entscheid 21.09.2026).
        "This multi build plan has no end products.":
            "Dieser Multi-Bauplan hat keine Endprodukte.",
        "These build plans were changed since this multi build plan was "
        "saved:\n\u2022 {names}\n\nTake over their current quantity, ME and TE? "
        "(No = keep the multi build plan as it is.)":
            "Diese Baupl\u00e4ne wurden seit dem Speichern dieses Multi-Bauplans "
            "ge\u00e4ndert:\n\u2022 {names}\n\nIhre aktuelle Menge, ME und TE "
            "\u00fcbernehmen? (Nein = Multi-Bauplan bleibt, wie er ist.)",
        "A multi build plan is always ONE bundle. Change the quantity per end "
        "product in the multi build plan.":
            "Ein Multi-Bauplan ist immer EIN B\u00fcndel. Die St\u00fcckzahl je "
            "Endprodukt \u00e4nderst du im Multi-Bauplan.",
        "END PRODUCT OF THIS PLAN":
            "ENDPRODUKT DIESES PLANS",
        "END PRODUCTS OF THIS BUNDLE": "ENDPRODUKTE DIESES B\u00dcNDELS",
        "Cost per unit = this product's share of the bundle: shared "
        "intermediates (and their surplus) are split by demand, its own job "
        "and invention costs are its own. The sum over all end products is "
        "exactly the bundle's total cost.":
            "Kosten je St\u00fcck = der Anteil dieses Produkts am B\u00fcndel: geteilte "
            "Zwischenprodukte (samt \u00dcberschuss) werden nach Bedarf aufgeteilt, "
            "eigene Job- und Invention-Kosten geh\u00f6ren ihm allein. Die Summe "
            "\u00fcber alle Endprodukte ist genau die Gesamtsumme des B\u00fcndels.",
        # Multi-Bauplan, Schritt 4: je Endprodukt (mw_multi_bauplan.py).
        "Own BPC": "Eigene BPC",
        "Runs/BPC": "Runs/BPC",
        "Quantity, ME/TE and \u201eOwn BPC\u201c belong to EACH end product here \u2013 "
        "that is why the single fields above are hidden for a bundle. T2 "
        "ends take ME/TE from their decryptor (Invention tab); tick \u201eOwn "
        "BPC\u201c to build from your own copy with its own values instead.":
            "Menge, ME/TE und \u201eEigene BPC\u201c geh\u00f6ren hier zu JEDEM Endprodukt "
            "einzeln \u2013 deshalb sind die einzelnen Felder oben beim B\u00fcndel "
            "ausgeblendet. T2-Enden nehmen ME/TE aus ihrem Decryptor "
            "(Invention-Reiter); \u201eEigene BPC\u201c anhaken, um stattdessen aus "
            "der eigenen Kopie mit deren Werten zu bauen.",
        "\u26a0 Unclear whether you invent or build from your own copies: "
        "{items}. The plan INVENTS these (datacores, attempts) \u2013 tick "
        "\u201eOwn BPC\u201c if you build from the copies in your hangar.":
            "\u26a0 Unklar, ob du erfindest oder aus eigenen Kopien baust: "
            "{items}. Der Plan ERFINDET diese (Datacores, Versuche) \u2013 "
            "\u201eEigene BPC\u201c anhaken, wenn du aus den Kopien im Hangar baust.",
        "{name} ({n} own copies)": "{name} ({n} eigene Kopien)",
        "How many of THIS end product the bundle builds.":
            "Wie viele St\u00fcck von DIESEM Endprodukt das B\u00fcndel baut.",
        "Material efficiency of YOUR blueprint copy of this end product "
        "(0\u201310 %).":
            "Materialeffizienz DEINER Blaupausen-Kopie dieses Endprodukts "
            "(0\u201310 %).",
        "Time efficiency of YOUR blueprint copy of this end product "
        "(0\u201320 %).":
            "Zeiteffizienz DEINER Blaupausen-Kopie dieses Endprodukts "
            "(0\u201320 %).",
        "Comes from the invention (2 % base plus decryptor) \u2013 an invented "
        "copy has no researched ME. Tick \u201eOwn BPC\u201c to enter your own "
        "copy's value.":
            "Kommt aus der Invention (2 % Basis plus Decryptor) \u2013 eine "
            "erfundene Kopie hat keine erforschte ME. Hak \u201eEigene BPC\u201c an, "
            "um den Wert deiner eigenen Kopie einzutragen.",
        "On: you already own a blueprint copy of this end product \u2013 its "
        "ME/TE below are yours to set, and invention is left out of the "
        "calculation for THIS product (no invention cost). Off: the ME "
        "comes from the invention (2 % base plus decryptor) and cannot "
        "be edited.":
            "An: du hast schon eine Blaupausen-Kopie dieses Endprodukts \u2013 "
            "ME/TE daneben geh\u00f6ren dir, und die Invention f\u00e4llt f\u00fcr DIESES "
            "Produkt aus der Rechnung (keine Invention-Kosten). Aus: die ME "
            "kommt aus der Invention (2 % Basis plus Decryptor) und ist "
            "nicht \u00e4nderbar.",
        "running since {t}": "l\u00e4uft seit {t}",
        "{name}  ({n} jobs)": "{name}  ({n} Jobs)",
        "Location: re-link":
            "Standort: neu verkn\u00fcpfen",
        "The location hint is on, but {name} was linked without the location permission. Add esi-location.read_location.v1 to your EVE app and link the character again (Characters).":
            "Der Standort-Hinweis ist an, aber {name} wurde ohne die Standort-Berechtigung verkn\u00fcpft. esi-location.read_location.v1 in deiner EVE-App eintragen und den Charakter neu verkn\u00fcpfen (Characters).",
        "a player structure in {system}":
            "einer Spieler-Struktur in {system}",
        "in space in {system}":
            "im All in {system}",
        "Not at the hub":
            "Nicht am Hub",
        "{name} is at {where}, not at {hub}. Orders you place in the game go where the character is docked \u2013 the prices here are for {hub}.":
            "{name} ist bei {where}, nicht bei {hub}. Orders, die du im Spiel setzt, landen dort, wo der Charakter angedockt ist \u2013 die Preise hier gelten f\u00fcr {hub}.",
        "On (warn when the character is not at the hub)":
            "An (warnen, wenn der Charakter nicht am Hub ist)",
        "Character location":
            "Charakter-Standort",
        "On: next to the character at the top a warning appears when the character is not docked at the selected hub. Needs the scope esi-location.read_location.v1 in your EVE app and re-linking.":
            "An: oben neben dem Charakter erscheint eine Warnung, wenn der Charakter nicht am gew\u00e4hlten Hub angedockt ist. Braucht den Scope esi-location.read_location.v1 in deiner EVE-App und ein Neu-Verkn\u00fcpfen.",
        "Switched on and saved. Add esi-location.read_location.v1 to your EVE app, then re-link your character (Characters tab).":
            "Eingeschaltet und gespeichert. esi-location.read_location.v1 in deiner EVE-App eintragen, dann den Charakter neu verkn\u00fcpfen (Reiter Characters).",
        "Needed for copying the T1 original "
        "(one copy run per attempt).":
            "Wird zum Kopieren des T1-Originals gebraucht "
            "(ein Kopie-Run je Versuch).",
        "not needed \u2013 its minerals are already in stock \u2713":
            "nicht mehr n\u00f6tig \u2013 seine Minerale liegen schon da \u2713",
        "Every mineral this ore was planned for is already "
        "in stock for this plan (reprocessed or bought). "
        "The ore is no longer needed and not on the "
        "shopping list.":
            "Jedes Mineral, f\u00fcr das dieses Erz geplant war, liegt f\u00fcr "
            "diesen Plan schon im Bestand (reprocesst oder gekauft). Das Erz "
            "wird nicht mehr gebraucht und steht nicht auf der Einkaufsliste.",
        "minerals already in stock \u2713": "Minerale schon da \u2713",
        "(running: {n} runs, not assigned to a plan yet)":
            "(l\u00e4uft: {n} Runs, noch keinem Plan zugeordnet)",
        "A job for this item is running, but more than one "
        "plan builds it and it is not assigned yet. It "
        "counts for no plan until you assign it (button "
        "\u201e\u2026 not assigned \u2013 assign\u201c).":
            "F\u00fcr dieses Item l\u00e4uft ein Job, aber mehrere Pl\u00e4ne bauen "
            "es und er ist noch nicht zugeordnet. Er z\u00e4hlt f\u00fcr keinen Plan, "
            "bis du ihn zuordnest (Knopf \u201e\u2026 not assigned \u2013 assign\u201c).",
        "{n} job(s) assigned by build priority \u2013 check":
            "{n} Job(s) nach Bau-Priorit\u00e4t zugeordnet \u2013 pr\u00fcfen",
        "These jobs were built for an item that more than one plan "
        "needs. The card order (#1, #2 ...) gave them to a plan. If you "
        "built them for another plan, change it here \u2013 saving "
        "confirms them and the button goes away.":
            "Diese Jobs bauten ein Item, das mehrere Pl\u00e4ne brauchen. Die "
            "Kartenreihenfolge (#1, #2 ...) hat sie einem Plan gegeben. Hast du "
            "sie f\u00fcr einen anderen Plan gebaut, \u00e4ndere es hier \u2013 "
            "Speichern best\u00e4tigt sie, und der Knopf verschwindet.",
        "Jobs with a plan already chosen were given out by the card "
        "order (build priority). Change the plan if you built them for "
        "another one \u2013 saving confirms them.":
            "Jobs mit schon gew\u00e4hltem Plan hat die Kartenreihenfolge "
            "(Bau-Priorit\u00e4t) verteilt. \u00c4ndere den Plan, wenn du sie "
            "f\u00fcr einen anderen gebaut hast \u2013 Speichern best\u00e4tigt sie.",
        "\u26a0 No lock: this plan reserves nothing \u2013 "
        "plans below it can use its material despite its number.":
            "\u26a0 Kein Schloss: dieser Plan reserviert nichts \u2013 "
            "Pl\u00e4ne unter ihm k\u00f6nnen sein Material trotz seiner Nummer "
            "verbrauchen.",
        "\u26a0 Looks finished but is not marked as done \u2013 it "
        "keeps its number and its reservation until you mark it done.":
            "\u26a0 Sieht fertig aus, ist aber nicht als erledigt markiert \u2013 "
            "er beh\u00e4lt Nummer und Reservierung, bis du ihn abschlie\u00dft.",
        "Build priority #{n}: plans with a smaller number get stock "
        "and unassigned jobs first. Change it by rearranging the "
        "cards.":
            "Bau-Priorit\u00e4t #{n}: Pl\u00e4ne mit kleinerer Zahl bekommen "
            "Bestand und nicht zugeordnete Jobs zuerst. \u00c4ndern: Karten "
            "umordnen.",
        "Your copies in the hangar have {n} runs each (ESI) \u2013 "
        "every job uses a whole copy.":
            "Deine Kopien im Hangar haben je {n} Runs (ESI) \u2013 "
            "jeder Job verbraucht eine ganze Kopie.",
        "How many runs does ONE of your own BPCs of this product have? "
        "The run planner never puts more than this into a single job.":
            "Wie viele Runs hat EINE deiner eigenen BPCs von diesem Produkt? "
            "Der Runplaner packt nie mehr als das in einen einzelnen Job.",
        "This end product is not invented. On: you build it from a blueprint "
        "COPY with a limited number of runs (below). Off: you own the "
        "original and can run it as often as you like.":
            "Dieses Endprodukt wird nicht erfunden. An: du baust es aus einer "
            "Blaupausen-KOPIE mit begrenzten Runs (daneben). Aus: du besitzt "
            "das Original und kannst beliebig oft bauen.",
        # Schritt 4b: Kopien je Endprodukt.
        "Copies": "Kopien",
        "How many blueprint copies of this end product the plan needs, and "
        "how many runs each one carries. The run planner never puts more "
        "than that into one job.":
            "Wie viele Blaupausen-Kopien dieses Endprodukts der Plan braucht "
            "und wie viele Runs jede davon tr\u00e4gt. Der Runplaner packt nie "
            "mehr als das in einen Job.",
        "Assumed: you own the blueprint (unlimited runs) \u2013 no invention, "
        "no copies needed.":
            "Angenommen: du besitzt die Blaupause (unbegrenzte Runs) \u2013 keine "
            "Invention, keine Kopien n\u00f6tig.",
        "Own copy \u2013 but how many runs one copy carries is unknown. Load "
        "your blueprints or type \u201eRuns/BPC\u201c, otherwise the run planner "
        "cannot limit the jobs.":
            "Eigene Kopie \u2013 wie viele Runs EINE Kopie tr\u00e4gt, ist aber "
            "unbekannt. Blaupausen laden oder \u201eRuns/BPC\u201c eintippen, sonst "
            "kann der Runplaner die Jobs nicht begrenzen.",
        "Several end products \u2013 copies and runs per product are in the "
        "\u201eEnd products\u201c card above.":
            "Mehrere Endprodukte \u2013 Kopien und Runs je Produkt stehen in der "
            "Karte \u201eEndprodukte\u201c oben.",
        # Schritt 5, Entscheid C: Einzelplaene in einem Multi-Bauplan.
        "Belongs to multi build plan {name}":
            "Geh\u00f6rt zum Multi-Bauplan {name}",
        "This plan is built as part of a multi build plan. Open THAT one to "
        "buy and build \u2013 its shopping list already contains this product, "
        "and shared intermediates are counted once.":
            "Dieser Plan wird als Teil eines Multi-Bauplans gebaut. \u00d6ffne "
            "JENEN zum Einkaufen und Bauen \u2013 seine Einkaufsliste enth\u00e4lt "
            "dieses Produkt schon, und geteilte Zwischenprodukte z\u00e4hlen nur "
            "einmal.",
        "Locked: this plan is part of a multi build plan, and that one "
        "already reserves the material. Reserving twice would block the "
        "same stock two times.":
            "Gesperrt: dieser Plan geh\u00f6rt zu einem Multi-Bauplan, und der "
            "reserviert das Material bereits. Zweimal reservieren w\u00fcrde "
            "denselben Bestand doppelt blockieren.",
        "Heads-up: this plan is part of the multi build plan \u201e{name}\u201c \u2013 "
        "buy and build there, otherwise you order the same material twice.":
            "Achtung: dieser Plan geh\u00f6rt zum Multi-Bauplan \u201e{name}\u201c \u2013 "
            "kauf und bau dort, sonst bestellst du dasselbe Material zweimal.",
        "No separate reservation: this plan belongs to the multi build plan "
        "\u201e{name}\u201c and is reserved there.":
            "Keine eigene Reservierung: dieser Plan geh\u00f6rt zum Multi-Bauplan "
            "\u201e{name}\u201c und wird dort reserviert.",
        # Fracht in der Verkaufsliste (emm272, 29.09.2026)
        "Freight {isk} per unit ({n} of {gesamt} units were bought away from "
        "this hub, {m3} m\u00b3 \u00d7 {satz} ISK/m\u00b3). The target price "
        "already includes it: +{pct} %.":
            "Fracht {isk} je St\u00fcck ({n} von {gesamt} St\u00fcck wurden nicht an "
            "diesem Hub gekauft, {m3} m\u00b3 \u00d7 {satz} ISK/m\u00b3). Der Zielpreis "
            "enth\u00e4lt sie schon: +{pct} %.",
        "No freight for this item":
            "Keine Fracht f\u00fcr dieses Item",
        "Charge freight for this item again":
            "Fracht f\u00fcr dieses Item wieder berechnen",
        "Freight per m\u00b3. Units you bought away from the active hub get "
        "volume \u00d7 this rate added to their cost; 0 = no freight.":
            "Fracht je m\u00b3. St\u00fcck, die nicht am aktiven Hub gekauft wurden, "
            "bekommen Volumen \u00d7 diesen Satz auf ihre Kosten; 0 = keine Fracht.",
        "Freight {satz} ISK/m\u00b3: applies to {n} item(s) \u2013 only units "
        "bought away from {hub} get it.":
            "Fracht {satz} ISK/m\u00b3: gilt f\u00fcr {n} Item(s) \u2013 nur St\u00fcck, "
            "die nicht in {hub} gekauft wurden, bekommen sie.",
        "Freight off (0 ISK/m\u00b3).":
            "Fracht aus (0 ISK/m\u00b3).",
        "Open build plan \u201e{plan}\u201c (not saved yet)":
            "Offener Bauplan \u201e{plan}\u201c (noch nicht gespeichert)",
        "{n} end products added \u2013 save the plan to keep it.":
            "{n} Endprodukte hinzugef\u00fcgt \u2013 speichere den Plan, um sie zu behalten.",
    },
}

_aktuell = "en"


def aktuelle_sprache():
    return _aktuell


def sprache_setzen(code):
    """Sprache umschalten. Unbekannte Codes fallen auf Englisch zurück -
    lieber die Standardsprache als eine halb leere Oberfläche."""
    global _aktuell
    _aktuell = code if code in SPRACHEN else "en"
    return _aktuell


def t(text):
    """Übersetzt EINEN Anzeigetext. Fehlt der Eintrag, bleibt Englisch."""
    if _aktuell == "en":
        return text
    return KATALOG.get(_aktuell, {}).get(text, text)


def fehlende(sprache):
    """Welche Schlüssel hat diese Sprache noch nicht? Für die Prüfungen -
    damit eine Lücke auffällt, statt still englisch durchzurutschen."""
    _da = set(KATALOG.get(sprache, {}))
    _alle = set()
    for _s in KATALOG.values():
        _alle |= set(_s)
    return sorted(_alle - _da)
