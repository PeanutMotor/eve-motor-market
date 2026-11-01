# AUDIT VOR VERÖFFENTLICHUNG - Material-Fehlbeträge bei Kreuz-und-quer-Bauen
(31.10.2026, emm788. Drei parallele Code-Prüfungen + Ablauf-Simulation mit den
echten Funktionen; 175 Fuzz-Läufe. Positivkontrolle: der bekannte emm787-Fall
wird vom Harness erkannt. Jede Behauptung mit Datei:Zeile; die drei KRITISCH-
Befunde der Reservierung sind per Nachstellskript (repro.py/repro2.py)
rechnerisch belegt, die Simulationsbefunde per kreuzquer_sim.py.)

## RANGLISTE (was vor der Veröffentlichung gefixt gehört)

KRITISCH (kauft zu wenig / gibt fremdes Material frei):
 K1  Stock Locations, Einzelplan-Dropdown: "Copy shopping list" rechnet NUR den
     gewählten Plan gegen den VOLLEN Rohbestand (mw_bauplan_tabs.py:2415-2437,
     2807; lagerorte.py:702-705). 2 Pläne à 100, Bestand 100 -> "0 fehlt".
 K2  Nenner-Drift der mitlaufenden Reservierung: Zähler aus AKTUELLEN
     assignments, Freigabe-Mengen aus dem ALTEN Schnappschuss
     (mw_helpers.py:1817-1822, 1176-1234). Nachgestellt: 30/50 gebaut ->
     5'000/5'000 Tritanium freigegeben, verbraucht nur 3'000.
 K3  _frozen_auto_checked ignoriert die Job-Zuordnung: Jobs abgeschlossener/
     gelöschter Pläne (oder "keiner") zählen voll als eigener Fortschritt
     (mw_helpers.py:1618-1671; mw_bauplan_tabs.py:9671). Einkaufsliste
     schrumpft um fremden Fortschritt.
 K4  Stille Prio-Zuordnung bei krummen Run-Zahlen: 7 Runs für Plan #2 gebaut
     -> landen still bei Rang-1 (mw_helpers.py:4583-4592), der falsche Plan
     gibt unverbrauchte Zutaten frei. Nachgestellt (repro.py F3).

MITTEL:
 M1  Stock Locations ignoriert reservierte, NICHT eingefrorene Pläne komplett
     (lagerorte.py:566-585) - deren reserviertes Material deckt dort fremde
     Fehlmengen; das Bauplan-Fenster zieht dieselbe Reservierung korrekt ab.
 M2  Übersubskription der "fairen Aufteilung" (mw_helpers.py:1693): ist
     eigener+fremder Anspruch > Bestand (durch Überbau, Verkauf reservierter
     Ware, Rundung der Freigabe int(_q*anteil)), sieht JEDER Plan seinen
     Anspruch gedeckt - niemand kauft die Lücke nach. Gemessen: 29'600
     Bestand / 29'601 Anspruch -> 1 Tritanium fehlt; Überbau-Fall: 5'000.
 M3  "Neu berechnen"+Einfrieren mitten im Teilbau: frozen_ts-Reset verwirft
     den ESI-Fortschritt, der frische Schnappschuss plant das volle Soll
     (Endprodukt zählt nie gegen Bestand) - verstärkt M2.
 M4  Überlieferung (60-Run-Job bei 50 geplant) ist nirgends zuordenbar, nicht
     mal fragbar (mw_helpers.py:2879) -> Reservierung friert dauerhaft ein,
     während die Fortschritts-Anzeige "fertig" sagt (zwei Wahrheiten).
 M5  Globaler assets_checked_at nimmt die Abruf-Wanduhr statt des ESI-Daten-
     Alters (store.note_asset_snapshot; mw_helpers.py:49-63) -> Fenster, in
     dem freigegebener Anspruch UND alter Bestand dieselben Einheiten doppelt
     zählen.
 M6  Bündel ohne Schloss + Mitglied mit Schloss = NIEMAND reserviert
     (mw_helpers.py:1323-1334, 1886-1894). Nachgestellt (repro2.py):
     Anspruch = {} trotz sichtbarem 🔒 auf der Mitglieds-Karte.
 M7  "Trotzdem kaufen"-Haken wird beim Kopieren verworfen: drei Tooltips
     versprechen ihn, einkauf_posten wirft plan-gebaute Items auch ANGEHAKT
     raus (mw_helpers.py:5854-5859; main_window.py:24146-24172). Einziger
     Nachkauf-Weg für verlorene Eigenbau-Zwischenprodukte ist damit tot.
 M8  Fremde Job-Pipeline zählt in der PLANRECHNUNG als Bestand (nur
     _fehlbedarf_jetzt hat die emm721-Umstritten-Regel): Runplaner sagt
     "nothing to do", Baukosten zu niedrig, die Fehlt-Zeile verlangt
     gleichzeitig den Kauf (mw_bauplan_fenster.py:9443-9505;
     main_window.py:22735-22760; mw_bauplan_tabs.py:12484-12497).
 M9  Stock Locations zählt LAUFENDE Jobs nicht als erledigt (lagerorte.py:
     474-477, dort selbst als OFFEN markiert) -> Doppelkauf-Richtung.
 M10 _plan_to_cart zieht den Bestand DOPPELT ab (main_window.py:12188-12199)
     - derzeit toter Code ohne Aufrufer, aber gepflegt; bei Wiederanschluss
     sofortiger Unterkauf. Entfernen oder fixen.

GERING:
 G1  Multi-Hub-Kopierknöpfe: Dünner-Markt-Rest steht in keiner Liste, nur als
     Zähler-Warnung (main_window.py:24654-24688) - Item+Menge nennen.
 G2  Puffer bau_buy_surplus wirkt nicht auf der Stock-Locations-Liste und bei
     "Fehlendes nachkaufen" (lagerorte.py:840-870; main_window.py:33226).
 G3  Nie eingefrorene Pläne: Anspruch schrumpft nie, und reine KAUF-Posten
     gelten über den reserve_map-Rückfall als "baut selbst" -> Dauer-Streit,
     Über-Einkauf (mw_helpers.py:1388-1393, 1766-1770).
 G4  Runplaner-Hand-Haken verfallen bei Charakter-/Zielzeit-Wechsel still
     (Schlüssel trägt die cid; main_window.py:33444-33452).
 G5  Einkaufsmengen sind floats; einkauf_posten schneidet mit int() AB statt
     aufzurunden (REGEL-3-Richtung wäre ceil).

SAUBER GEPRÜFT (ohne Befund): alle lebenden Einkaufswege des Bauplan-Fensters
rechnen über den reservierungsbereinigten Bestand; kein doppelter Puffer;
Chromium-Fall (emm546) behoben; Deckel-/Negativprüfungen der Reservierung
sauber; Plan löschen/abschließen räumt auf; Doppel-Zuordnung eines Jobs
unmöglich; Gewinn-Kopf rechnet konsistent auf Schnappschuss-Basis;
175 Fuzz-Läufe (Schloss+eingefroren, ohne Störereignisse) ohne Fehlbetrag.

Die vollständigen Einzelberichte mit Szenarien und Gegenargumenten folgen
unten (A = Einkaufswege, B = Reservierungs-Lebenszyklus, C = Anzeigen,
D = Simulation).


==========================================================================
# TEIL A: # Audit: Material-Fehlbetrag bei mehreren gespeicherten Bauplänen — Einkaufswege

Stand: 31.10.2026, Arbeitskopie /mnt/user-data/uploads/eve-motor-market (nur gelesen, nichts geändert).
Jede Behauptung mit Datei:Zeile belegt; UNGEPRÜFTES ist als solches markiert.

## Geprüfte Wege und ihr Bestands-Fundament (Prüffrage 1)

| Weg | Mengenquelle | Bestand nach Reservierungsabzug? |
|---|---|---|
| „Einkaufsliste erstellen" (Materialien-Tab, `_copy_materials` → Kopier-Dialog, `mw_bauplan_fenster.py:5381-5531`) | Plan-Zahlen via `copy_qty` (`_menge`/`_rest_kaufmenge` → `_fehlbedarf_jetzt`) | JA — `_fehlbedarf_jetzt` (main_window.py:33296) nimmt `_bd_echter_bestand()` (22652-22712), das `_reservierungen_anwenden` durchläuft (22711) |
| Kopierknöpfe im Dialog (`_copy_rows` main_window.py:24472, `_copy_rows_hub` 24619, `einkauf_posten` mw_helpers.py:5809) | `rows[*]["missing"]` = Plan-Fehlmenge (im Kopier-Modus überschrieben, 23851-23875) | JA — dieselbe Quelle wie oben |
| „Einkauf jetzt"-Zeile (`_einkauf_jetzt` mw_bauplan_fenster.py:1598-1736) | identische Rechnung (nur Anzeige/Volumen, 8783-8819) | JA |
| Offener Bauplan generell | `_bd_opts["stock"]` | JA — `_recompute_bd_stock` (main_window.py:22731-22758) ruft `_reservierungen_anwenden` (22749) → `bestand_nach_reservierungen` (mw_helpers.py:1693) |
| Einkaufswagen-Multibuy (`shopping_copy` main_window.py:31085) | gespeicherte Wagen-Mengen | neutral — kopiert nur, rechnet nicht |
| Stock Locations „Copy shopping list" (`_lager_kaufliste_kopieren` mw_bauplan_tabs.py:2787-2814, `lagerorte.einkaufsliste` lagerorte.py:840) | `short = Bedarf − Rohbestand` (lagerorte.py:702-705) | **NEIN** — Rohbestand aus den Asset-Zeilen, KEIN Reservierungsabzug irgendwo in lagerorte.py (ganzes Modul gelesen) → Befunde 1 und 2 |
| `_plan_to_cart` (main_window.py:12162) | Dialog-Fehlmenge gegen `_bd_opts["stock"]` | JA, aber doppelt (Befund 3) — derzeit TOTER CODE |

`_owned_and_selling` (main_window.py:23765, roher Portfolio-Cache) speist in allen lebenden Wegen nur die ANZEIGE-Spalte „own" und die Konflikt-Warnung, nie die kopierte/gekaufte Menge (Überschreibung 23851-23875: „own bleibt UNANGETASTET … der Plan ist nur fuer MENGEN massgeblich").

---

## Befund 1 — Stock Locations: Einzelplan-Auswahl kauft gegen den GESAMTEN Bestand ein

**Schweregrad: KRITISCH**

**Stellen:**
- `eve_trader/ui/mw_bauplan_tabs.py:2415-2437` — `_lager_zeichnen`: `pid = self._lager_plan_cb.currentData()`; mit gewähltem Plan wird `bedarf = bedarf_je_plan[pid]` (NUR dieser Plan, berechnet mit `[p]` in 2018-2020), aber die Bestands-`zeilen` bleiben der volle Rohbestand aller Charaktere/Orte. `_lager_fehl_items` (2431-2437) folgt dieser Auswahl.
- `eve_trader/ui/mw_bauplan_tabs.py:2807-2808` — der Kopier-Knopf nimmt exakt `_lager_fehl_items`, also den Stand der letzten Zeichnung.
- `eve_trader/lagerorte.py:702-705` — `short = max(0, ges − verfügbar)`; `verfügbar` = Rohbestand minus `lag` (Job-Verbrauch), KEINE Reservierungen, keine Ansprüche anderer Pläne.
- `eve_trader/ui/mw_bauplan_tabs.py:1359-1364` — der Tooltip verspricht „Everything that is really missing across ALL listed plans" — bei Einzelplan-Auswahl stimmt das nicht mehr.

**Nutzer-Szenario:** Pläne A und B sind beide gespeichert+eingefroren(+reserviert), beide brauchen 100 Tritanium, im Hangar liegen 100 (für B gekauft). Der Nutzer wählt im Dropdown „Plan A", drückt „Copy shopping list": `short = 100 − 100 = 0` → „Nothing is missing". Er kauft nichts, baut A, verbraucht Bs Material — B steht mit 0 da. Im Bauplan-Fenster von A wäre dieselbe Frage richtig beantwortet worden (Reservierungsabzug, main_window.py:22631). In der Alle-Pläne-Ansicht ist die Summe korrekt (Bedarf beider Pläne addiert) — der Fehlbetrag entsteht NUR mit Dropdown-Auswahl ≠ „All frozen plans" (mw_bauplan_tabs.py:1600).

**Was dagegen spricht:** Nichts Belegtes. Der Einzelplan-Filter ist eine normale UI-Stellung (1348-1355), kein Sondermodus; der Knopf bleibt aktiv (gesperrt wird nur bei gescheiterten Abrufen, 2773-2775). Dass der Nutzer die Auswahl „nur zum Ansehen" nutzt, wäre eine Hoffnung, keine Sicherung.

---

## Befund 2 — Stock Locations ignoriert reservierte, aber NICHT eingefrorene Pläne (beide Seiten)

**Schweregrad: MITTEL**

**Stellen:**
- `eve_trader/lagerorte.py:566-585` — `plaene_fuer_lagerorte` nimmt nur Pläne MIT `frozen.plan_snapshot`. Ein gespeicherter Plan mit 🔒 (`reserve=True`), aber ohne Einfrieren, kommt weder als Bedarf noch als Reservierung vor.
- `eve_trader/ui/mw_helpers.py:1762-1770` — im Bauplan-Fenster zählt genau so ein Plan sehr wohl: ohne Schnappschuss gilt seine gespeicherte `reserve_map` („sicherer Rueckfall"), und `_reservierende_plaene` (1885-1894) filtert nur auf `reserve`, nicht auf eingefroren.
- Bestandsseite: lagerorte.py kennt keinerlei Reservierungsabzug (ganzes Modul, s.o.); `baum`/`karten` rechnen gegen die rohen Zeilen.

**Nutzer-Szenario:** Plan B ist gespeichert und reserviert (noch nicht eingefroren, z.B. weil er erst nächste Woche startet), sein Material (50 X) ist gekauft und liegt im Hangar. Plan A ist eingefroren und braucht 100 X. Die Giant Shopping List (auch in der Alle-Pläne-Ansicht) meldet `short = 100 − 50 = 50`. Der Nutzer kauft 50, baut A mit allen 100 — Bs reservierte 50 sind weg. Der offene Bauplan von A hätte Bs Reservierung abgezogen und 100 verlangt → zwei Wahrheiten für dieselbe Frage (genau die emm626-Krankheit, nur auf der Reservierungs-Schiene).

**Was dagegen spricht:** Die Seite ist laut Nutzer-Entscheid bewusst „nur fuer gespeicherte und eingefrorene Plaene" (lagerorte.py:567-568) — das deckt aber die BEDARFS-Seite (welche Pläne Zeilen bekommen), nicht die Entscheidung, fremd-reserviertes Material als frei zu zählen. Teilweise mildernd: ist B ebenfalls eingefroren, zählt sein Bedarf in der Alle-Pläne-Summe mit und der Fall kollabiert in Befund 1.

---

## Befund 3 — `_plan_to_cart`: Bestand wird DOPPELT abgezogen (derzeit toter Code)

**Schweregrad: MITTEL (latent — kein Aufrufer; bei Wiederanschluss sofort Fehlbetrag)**

**Stellen:**
- `eve_trader/industry.py:4455-4462` — `production_plan` verbraucht `opts["stock"]` VOR der Kauf-Entscheidung (`used = min(owned, D); D -= used; stock_used[...]`) → `plan["buy"]` ist bereits NETTO nach Bestandsdeckung.
- `eve_trader/ui/main_window.py:12188-12199` — `_plan_to_cart` übergibt `needed=buy` und `plan_stock=_bd_opts["stock"]`; in den Wagen wandert `_cart_qty[tid]`.
- `eve_trader/ui/main_window.py:22463-22465, 22481` — `missing = max(0, need − scope_stock)`, `cart_qty = missing` → derselbe Bestand wird ein zweites Mal abgezogen.

**Nutzer-Szenario (wenn der Weg wieder verdrahtet würde):** Bedarf 100, Hangar 30 → Plan: `buy=70`, `stock_used=30`. Dialog: `missing = 70 − 30 = 40` → der Wagen bekommt 40 statt 70. 30 Einheiten fehlen beim Bau. Mit Reservierungen wird es nicht besser, nur anders falsch.

**Was dagegen spricht:** Kein Aufrufer im gesamten Projekt (grep über alle .py: nur die Definition main_window.py:12162 und Kommentare/Tests); `tests/test_bauplan_aufbau.py:1996-1998` verankert ausdrücklich, dass der Bauplan-Knopf `self._plan_to_cart(...)` NICHT mehr existiert. Zwei Tests (test_bestand_herkunft.py:4561, 16189, 16419) verankern aber weiter die QUELLTEXT-Gestalt der Funktion — sie wirkt gepflegt und einsatzbereit. Entweder entfernen oder die Doppel-Subtraktion beheben, bevor jemand sie wieder anschließt.

---

## Befund 4 — Multi-Hub-Kopierknöpfe: Rest bei dünnem Markt steht in keiner Liste

**Schweregrad: GERING**

**Stellen:**
- `eve_trader/ui/main_window.py:24654-24688` — `_copy_rows_hub`: `multihub_split` liefert `rest > 0` (industry.py:590-608), die Restmenge landet in KEINER Hub-Liste; gemeldet wird nur „market too thin for {n} item(s)" — Anzahl, ohne Item-Namen und ohne Menge. Posten ohne Order an den gewählten Hubs (`_nur_scan`, 24660-24665) stehen nur im ALL-Knopf.
- Der ALL-Knopf (24600-24607) trägt die vollen Mengen — wer NUR die beiden Hub-Knöpfe benutzt (der beworbene Multi-Hub-Ablauf, emm723/724), kauft die Summe minus Rest.

**Nutzer-Szenario:** 4-HWWF+Jita zusammen haben 9'000 von 10'000 benötigten Stück im Orderbuch. Beide Hub-Listen zusammen enthalten 9'000; die 1'000 fehlen still bis auf den Zähler. Der Nutzer kauft je Hub die kopierte Liste und steht 1'000 zu kurz da.

**Was dagegen spricht:** Die Warnung erscheint bei jedem Kopieren sichtbar im Dialog (Regel-3-konform gemeldet statt still), und am Markt GIBT es die Menge in dem Moment schlicht nicht — der Fehlbetrag ist Marktlage, kein Rechenfehler. Verbesserungswürdig wäre nur, Item und Restmenge zu nennen.

---

## Befund 5 — Puffer (`bau_buy_surplus`) wirkt nicht auf allen Wegen

**Schweregrad: GERING**

**Stellen:**
- MIT Puffer: `_plan_to_cart` (main_window.py:12203), `_copy_rows` (24516), `_copy_rows_hub` (24656) — alle über die EINE Stelle `_buy_surplus_qty` (12156-12160, aufgerundet).
- OHNE Puffer: Stock-Locations-Liste (`lagerorte.einkaufsliste` 840-870 kopiert die rohe `short`-Menge; kein `_buy_surplus_qty` in mw_bauplan_tabs.py:2787-2814) und „Fehlendes nachkaufen" (`_buy_missing_again`, main_window.py:33226-33229, rohe Verlustmenge).

**Nutzer-Szenario:** Nutzer stellt 5 % Puffer ein („damit ein Fehlkauf nicht sofort eine zweite Einkaufsfahrt erzwingt", Tooltip 24565-24569), kauft aber über Stock Locations ein — die Liste kommt ohne Marge. Die Rohmenge ist korrekt; es fehlt „nur" die versprochene Sicherheitsreserve → bei Rundungs-/ME-Verlusten die zweite Fahrt, kein rechnerischer Fehlbetrag. Doppelte Pufferung wurde nirgends gefunden (geprüft: Wagen-Kopie `shopping_copy` 31108-31117 kopiert die gespeicherte Menge unverändert; der Puffer wird je Weg genau einmal gerechnet).

---

## Prüffragen ohne Befund (gemessen, nicht vermutet)

- **Frage 2 (Chromium 12'035 statt 6'770):** der historische Fall ist behoben — im Kopier-Modus überschreibt `copy_qty` Anzeige UND Kopie mit den Plan-Zahlen (main_window.py:23842-23875, Kommentar nennt den Fall wörtlich in 24477-24483); `_cqty` deckt ALLE `_bd_mat_rows` (mw_bauplan_fenster.py:5505-5527), es bleibt keine Zeile auf Dialog-eigener Rechnung.
- **Frage 3 (alter Plan nach Teilbauten):** Stock Locations rechnet den Fortschritt über `gebaute_runs` mit Haken-Verfall nach 65 min ohne ESI-Beleg (lagerorte.py:218-281, emm749) und `lag_verbrauch` gegen den ESI-Cache-Verzug (mw_bauplan_tabs.py:1977-2004); der offene Plan über `_fehlbedarf_jetzt`/`_bd_echter_bestand` (Live-Stand statt Einfrier-Merge, emm636). Kein zusätzlicher Veraltet-Weg gefunden — abgesehen von Befund 3 (dort wäre `plan["buy"]` die Einfrier-Menge).
- **Frage 4 (Rohmenge vs. gepuffert):** keine Stelle mit doppeltem Puffer; fehlender Puffer nur wie in Befund 5.


==========================================================================
# TEIL B: # Audit: Reservierungs-Lebenszyklus unter chaotischem Bauen (Eve MoMa)

Stand 31.10.2026, Arbeitskopie `/mnt/user-data/uploads/eve-motor-market`. Alle Rechen-Nachstellungen mit den ECHTEN Produktfunktionen (Regel 8a), Skripte: `repro.py`, `repro2.py` in diesem Ordner. Nichts im Projekt geändert.

---

## BEFUND 1 — KRITISCH: Nenner-Drift zwischen aktuellen `assignments` und eingefrorenem Schnappschuss → Über-Freigabe

**Dateien:** `eve_trader/ui/mw_helpers.py:1817-1822` (`plan_anspruch_mitlaufend` übergibt `p.get("assignments")` = AKTUELLER Stand), `:1176-1200` (`geplant` aus assignments; `build_runs`-Rückfall greift NUR für tids, die dort fehlen), `:1223-1234` (`_anteil = fertig/geplant`, freigegeben wird `_q` aus `build_mats` des SCHNAPPSCHUSSES = Gesamtmenge für die Schnappschuss-Runs), `eve_trader/ui/mw_bauplan_fenster.py:11254` + `:11328` (erneutes Speichern schreibt frische `_bd_last_assignments`, behält aber das alte `frozen`), `eve_trader/ui/main_window.py:20646-20653` (seit 28.09.2026 tragen gespeicherte assignments `tid` — der Zweig ist scharf).

**Nutzer-Szenario:** Plan eingefroren mit 50 Runs Item X (build_mats: 5'000 Tritanium). Nutzer ändert kreuz und quer die Runs/Charaktere, speichert neu (ohne neu einzufrieren) → assignments sagen 30 Runs. Er baut 30 Runs; der Job wird belegt.

**Nachstellung (`repro.py`, F2):** `_reserve_map_mitlaufend` mit geplant=30 (assignments), belegt=30, Schnappschuss 50 Runs/5'000 Trit → `anteil = 30/30 = 1.0` → **5'000 von 5'000 freigegeben, verbraucht sind nur 3'000.** Die 2'000 Tritanium, die der Plan laut Schnappschuss-Wahrheit (emm523) noch braucht, sieht jeder andere Plan als frei → **Materiallücke** mitten im Bau. Umgekehrte Drift (assignments > Schnappschuss) unter-gibt frei (nur konservativ). Zähler und Freigabe-Basis stammen aus zwei Zeitpunkten — genau die Fehlerklasse, die emm523 für die `reserve_map` behoben hat, hier für den NENNER.

---

## BEFUND 2 — KRITISCH: `_frozen_auto_checked` ignoriert die Job-Zuordnung — Jobs abgeschlossener/gelöschter Pläne (und „keiner"-Antworten) zählen als eigener Fortschritt

**Dateien:** `mw_helpers.py:1618-1671` (`_frozen_auto_checked`: nur tid + Aktivität + `completed_date >= frozen_ts`, KEIN `vergeben`-Parameter), `mw_bauplan_tabs.py:9671-9673` (bekommt ALLE `_bd_delivered_jobs`, ungefiltert), `mw_helpers.py:2943-2960` (`delivered_sicher` deckelt nur und verwirft nur UMSTRITTENE Items), `:1423-1424` (`_umstrittene_items`: `done_manual`-Pläne zählen nicht als Streit — bewusst, 25.09.2026).

**Nutzer-Szenario (zwei Pläne, dasselbe Item — Audit-Frage 3b):** Plan A und Plan B bauen beide Fuel Blocks. Solange beide offen sind, ist das Item umstritten und nur Belegtes zählt — korrekt. Nutzer schließt Plan A ab (oder löscht ihn: `main_window.py:17615` löscht dessen Zuordnungen) → A fällt aus `_umstrittene_items`. A's gelieferte Fuel-Block-Jobs (fertig nach B's frozen_ts) laufen weiter durch `_frozen_auto_checked` und zählen jetzt UNGESTRITTEN voll für B (`delivered_sicher` lässt sie durch, obwohl `job_zuordnung` sie A zuschreibt bzw. der Nutzer sie per Dialog auf `PLAN_KEINER` gesetzt hat). B's Einkaufsliste schrumpft um Fortschritt, den B nie gebaut hat → **zu wenig gekauft, Materiallücke**. Dieselbe Mechanik auf der Freigabe-Seite ist sauber (nur `belegte_runs_seit` aus der Zuordnung), aber Einkauf und Anzeige lesen `delivered_sicher`.

**Fix-Richtung:** gelieferte Jobs mit Zuordnung ≠ eigener Plan (und `PLAN_KEINER`) vor `_frozen_auto_checked`/`delivered_sicher` aussieben — dieselbe Quelle `store.job_zuordnung_alle()`, die `job_zuordnen` schon als `vergeben` nutzt.

---

## BEFUND 3 — KRITISCH: Stille Prioritäts-Zuordnung bei „krummen" Run-Zahlen gibt dem FALSCHEN Plan Material frei

**Dateien:** `mw_helpers.py:4583-4592` (`prio_jobs_zuteilen`: erster Rang-Plan, in den der Job GANZ passt), `mw_helpers.py:634-663` + `main_window`-Kommentar `mw_helpers.py:466-468` („SEIT emm430 STILL: keine Prüf-Frage mehr"), `:2290-2298` (Klick-Beleg verlangt EXAKT gleiche Run-Zahl `k_runs != runs` → bei abweichender Run-Zahl wirkungslos), `:4520-4527` (`signatur_zuteilen` nur bei exaktem Rest-Treffer).

**Nutzer-Szenario:** Plan #1 (Rang 1) hat 50 Runs Item X offen, Plan #2 hat 10. Nutzer baut spontan **7** Runs für Plan #2 (hält sich nicht an die Runs — sein erklärter Stil). Klick: greift nicht (7 ≠ geklickte Zeilen-Runs). Signatur: kein exakter Treffer (50≠7, 10≠7). Eindeutigkeit: beide bauen X → umstritten. **Nachstellung (`repro.py`, F3): Prioritaet schreibt den Job still an P1.** Folge: P1's `belegte_runs_seit` steigt → `_reserve_map_mitlaufend` gibt 7/50 von P1's Zutaten frei, obwohl P1's Material unangetastet im Hangar liegt (verbraucht wurde P2's) → **P1 unter-reserviert**, andere Pläne/Kauflisten verplanen Material, das P1 noch braucht. Korrektur nur manuell über „Job assignments" — der Nutzer erfährt von der stillen Entscheidung nichts.

---

## BEFUND 4 — MITTEL: Überlieferung (60 statt 50 Runs in EINEM Job) ist nirgends zuordenbar → Reservierung friert dauerhaft ein, zwei Wahrheiten

**Dateien:** `mw_helpers.py:2287` (`job_zuordnen`: Deckel überspringt), `:2419` (`job_zuordnen_eindeutig`), `:4522`/`:4586-4588` (signatur/prio), `:2879` (`offene_job_fragen`: `runs > grenze` → **nicht einmal gefragt**, Begründung „stammt sicher von woanders"), `:1666` (`_frozen_auto_checked` zählt ihn dagegen VOLL, kein Job-Deckel).

**Nutzer-Szenario:** Plan 50 Runs, Nutzer startet einen 60-Run-Job. **Nachstellung (`repro.py`, F1):** keine Zuordnung, keine offene Frage → `belegt = {}` → `_reserve_map_mitlaufend` gibt **nichts** frei: der Plan hält 5'000 Tritanium + 50 Stück Produkt-Anspruch fest, obwohl alles verbaut ist (emm638-Klasse: andere Pläne bekommen Kaufvorschläge für Phantome, gebundenes ISK). Gleichzeitig meldet `_frozen_auto_checked`/`delivered_sicher` min(60,50)=50 → Runplaner sagt „fertig", Reservierung sagt „unberührt" — zwei Wahrheiten auf einem Schirm. Richtung konservativ (keine Lücke), aber dauerhaft und unsichtbar; Ausweg nur „Job assignments" (falls der Job dort auftaucht) oder Plan abschließen. Mehrere kleine Jobs (50+10): die ersten 50 zählen, der 10er bleibt hängen — mildere Variante. **Negativ-/Deckelprüfung selbst ist sauber:** `repro.py` F1b: belegt=60/geplant=50 → `min`/`max(0,…)` greifen (`:1220`, `:1234`), keine negativen Mengen.

---

## BEFUND 5 — MITTEL: Globaler `checked_at` ignoriert das ESI-Cache-Alter → die Verzugs-Sperre hat ein Loch (Audit-Frage 5)

**Dateien:** `eve_trader/store.py` `note_asset_snapshot` (`jetzt = time.time()` als `assets_checked_at` — Wanduhr des ABRUFS, nicht Alter der DATEN), `mw_bauplan_fenster.py:~9400-9405` (der PLAN-Stempel rechnet ehrlich `now - age`), `mw_helpers.py:49-63` (`bestand_gesehen_bis` = **max** aus beiden → der ungealterte globale Stempel gewinnt), `:1105` (`belegte_runs_seit`: zählt, sobald Zuordnungs-ts ≤ diesem Stempel).

**Nutzer-Szenario:** Job startet 12:00, Zuordnung 12:01. Irgendeine Seite (Stock locations, anderer Plan, 5-Minuten-Takt emm629) macht 12:05 einen „vollständigen" Asset-Abruf, ESI liefert aber **gecachte** Daten von 11:10 (Assets-Cache bis ~1h). `checked_at`=12:05 ≥ 12:01 → `belegte_runs_seit` zählt (**Nachstellung `repro.py` F5**), die Zutaten werden freigegeben — der benutzte Bestand zeigt sie aber noch als vorhanden. Fenster bis Cache-Ablauf, in dem **dieselben Einheiten doppelt** existieren (als freier Bestand UND als freigegebener Anspruch): ein zweiter Plan verplant Phantom-Material → zu wenig gekauft. Genau das Loch, das die Sperre laut Docstring (`:1134-1140`) schließen soll. Fix-Richtung: `note_asset_snapshot` das Daten-Alter mitgeben (`jetzt - age`), wie es der Plan-Stempel schon tut.

---

## BEFUND 6 — MITTEL: Bündel ohne Schloss + Mitglieder mit Schloss = NIEMAND reserviert

**Dateien:** `mw_helpers.py:1323-1334` (`buendel_mitglieder`: prüft nur `type_id==-1` und `done_manual`, NICHT das `reserve`-Flag des Bündels), `:1886`/`:1894` (`_reservierende_plaene`: Bündel ohne Schloss fällt raus, Mitglied fällt als Mitglied raus), `:1346-1351` (identisch in `_fremde_reservierungen`), `mw_bauplan_fenster.py:11398-11400` (Mitglieds-Schloss wird nur beim MITGLIEDS-Speichern zwangsweise ausgeschaltet — ein VORHER gesetztes Schloss bleibt in den Settings stehen).

**Nachstellung (`repro2.py`):** Bündel `reserve=False` mit Quelle Plan 2 (`reserve=True`, reserve_map 9'000 Tritanium) → `_reserved_by_other_plans` für Plan 3 = **{}**; mit Bündel-Schloss korrekt {34: 9000}. **Nutzer-Szenario:** Nutzer verflicht einen bereits reservierten Einzelplan in ein Multi und lehnt die Bündel-Reservierungsfrage ab (oder entfernt später das Bündel-Schloss, während die Mitglieds-Karte das 🔒 noch zeigt): der Anspruch verschwindet komplett, obwohl ein Schloss sichtbar ist → andere Pläne verbauen das Material → **Materiallücke**. Mindestens müsste `buendel_mitglieder` Mitglieder nur ausnehmen, wenn das Bündel selbst reserviert, oder das Mitglieds-Schloss beim Verflechten sofort überall gelöscht werden.

---

## BEFUND 7 — GERING: Gespeichert-aber-nie-eingefroren: Anspruch schrumpft nie + Kaufposten gelten als „baut selbst"

**Dateien:** `mw_helpers.py:1766-1770` (ohne Schnappschuss bleibt die starre `reserve_map` vom Speichern — kein `build_mats` → `_reserve_map_mitlaufend` bucht nie ab; dokumentierter sicherer Rückfall), `:1388-1393` (`plan_baut_items`-Rückfall auf die reserve_map-SCHLÜSSEL: **Nachstellung `repro2.py`** — reiner Kaufposten Tritanium gilt als „baut es selbst"), `:1436-1437` (fließt in `_umstrittene_items`).

**Nutzer-Szenario:** Ein nie eingefrorener Plan, der Tritanium nur KAUFT, macht Tritanium-kompatible Items anderer Pläne umstritten → deren gelieferte Jobs fallen aus `delivered_sicher`, Fortschritt verschwindet, Einkaufsliste wächst (konservativ, aber dauerhafter Über-Einkauf + Dauer-Fragen). Zusammen mit dem nie schrumpfenden Anspruch bindet so ein „Karteileichen-Plan" Material auf unbestimmte Zeit. Richtung stets sicher, darum GERING — aber der größte Chaos-Verstärker im Alltag.

---

## GEPRÜFT UND SAUBER (keine Befunde)

* **Negative Mengen/Deckel:** `min(geplant, max(…))` `:1220`, `max(0, out-_weg)` `:1234`, `min(1.0, …)` `:1228` — Überlieferung erzeugt nie negative Reservierungen (repro F1b).
* **Plan löschen:** `main_window.py:17599-17619` räumt `job_zuordnung` + `run_klicks` mit auf; keine Job-Leichen, die fremde Zuordnung blockieren (Folgeproblem s. Befund 2: der verwaiste Job zählt danach frei für andere).
* **Plan abschließen:** `main_window.py:12908-12927` nimmt Schloss von Plan UND Bündel-Mitgliedern; `_umstrittene_items` lässt fertige Pläne korrekt aus.
* **Doppel-Zuordnung eines Jobs:** `store.job_zuordnung_setzen` = `INSERT OR IGNORE` je job_id — ein Job gehört höchstens einem Plan.
* **Fremder Charakter an sich:** Zuordnung/Fortschritt sind charakter-agnostisch (mw_bauplan_fenster.py:9417-9421 „Charakter-egal") — solange der Charakter im Tool autorisiert ist, landen seine Jobs richtig. Jobs eines NICHT autorisierten Charakters sind unsichtbar → Fortschritt zählt nie, Reservierung bleibt stehen (nur konservativ; Grenze von ESI, kein Code-Fehler).
* **Bündel vs. Einzel doppelt reserviert:** solange das Bündel offen UND reserviert ist, zählt das Mitglied nirgends doppelt (`:1350`, `:1428`, `:1894`).


==========================================================================
# TEIL C: # Audit: Konsistenz der Anzeigen im Bauplan-Fenster unter Teil-/Falschbau

Stand 31.10.2026, Code gelesen (nicht ausgeführt) in `/mnt/user-data/uploads/eve-motor-market`.
Nur echte Zahlen-/Mengen-Divergenzen; jede Behauptung mit Datei:Zeile.

---

## Befund 1 — „Trotzdem kaufen per Haken" wird dreifach versprochen, aber nie ausgeführt (Kopier-Modus des Einkaufsdialogs)

**Schweregrad: MITTEL** (kein Überkauf, aber ein Knopf, der nicht tut, was drei Tooltips zusagen; blockiert den einzigen Nachkauf-Weg für verlorene Eigenbau-Zwischenprodukte)

**Stellen:**
- `eve_trader/ui/main_window.py:24146–24152` — Zeilen-Tooltip Status: „Tick it only if you deliberately want to buy it instead."
- `eve_trader/ui/main_window.py:24154–24172` — emm668-Kommentar: To-cart-Zahl bleibt stehen, „denn der Dialog laesst bewusst zu, ihn trotzdem zu kaufen".
- `eve_trader/ui/main_window.py:24030–24036` — Spaltenkopf „Missing": „ticking there explicitly means ‚buy anyway'."
- `eve_trader/ui/mw_helpers.py:5854–5859` (`einkauf_posten`): der `baut`-Filter (`if tid in _baut: continue`) greift **nach** dem `nur_tids`-Filter und **unabhängig** davon — eine ANGEHAKTE Zeile eines plan-gebauten Items wird trotzdem verworfen (landet in `gebaut_raus`).
- Alle drei Kopierpfade laufen durch diesen Helfer: `main_window.py:24328` (Volumenzeile), `:24509` („Copy ALL missing"), `:24646` (Hub-Knöpfe). Der „Add"-Wagen-Pfad, der Haken ehrt (`:24743–24749`), existiert nur im Nicht-Kopier-Modus (`else`-Zweig `:24731`).

**Klick-/Bau-Szenario:** Eingefrorener Plan; ein selbstgebautes Zwischenprodukt (z. B. Composite) wurde geliefert und ist danach real verschwunden (Transportverlust, anderweitig verbaut). `_fehlbedarf_jetzt` meldet es korrekt als fehlend → im Kopier-Dialog zeigt die Zeile „partial – n missing" (`mw_helpers.py:1029–1062 _copy_mode_status`, missing>0-Zweig prüft `built` nicht), der KOPF zählt sie NICHT („you are missing 0 of …", `main_window.py:23933–23957`, Ausschluss über `_bd_plan_builds`), und „Copy ALL missing" kopiert 0 Zeilen mit Meldung „left out, this plan builds them" (`:24547–24552`). Der Nutzer setzt — wie der Tooltip rät — den Haken bewusst: es wird weiterhin nichts kopiert. Drei Aussagen (Zeile fehlt n / Kopf fehlt 0 / Kopie leer), dieselbe emm665-Fehlerklasse, nur in der Gegenrichtung. Da `build_runs` für das Item 0 offene Runs hat (ESI hat geliefert), bietet auch der Runplaner keinen Nachbau an — außer der `_nachlauf`-Pfad (emm646, `mw_bauplan_tabs.py:6718–6733`) greift; der deckt aber nur den Fall „Verbraucher braucht mehr", nicht jeden Verlustfall.

---

## Befund 2 — Fremde Job-Pipeline zählt nach „Neu berechnen" als eigener Bestand: Plan-Entscheidung, Baukosten und Runplaner-Info widersprechen Fehlt-Zeile und Einkaufsliste

**Schweregrad: MITTEL** (Baukosten/Gewinn zu optimistisch, Runplaner sagt „nothing to do", während die Rest-Einkaufsliste dasselbe Item kauft; die GEFÄHRLICHE Richtung — zu wenig kaufen — fängt emm721 nur auf der Prüfungsseite ab)

**Stellen:**
- `eve_trader/ui/mw_bauplan_fenster.py:9443–9505` (`_virtual_stock`): zählt laufende/fertige Jobs **aller** Charaktere/Pläne ungefiltert als Pipeline.
- `eve_trader/ui/main_window.py:22735–22760` (`_recompute_bd_stock`): Pipeline fließt in `_bd_opts["stock"]` → `production_plan` (`industry.py:4234`) stuft ein umstrittenes Zwischenprodukt als „stock covers" ein (kein `buy`, keine `build_runs`).
- `eve_trader/ui/main_window.py:33322–33392` (emm721): die Umstritten-Regel (fremde Pipeline deckt nicht) gilt **nur** in `_fehlbedarf_jetzt` — nicht in der Planrechnung selbst (im Code dort ausdrücklich gemessen: „die PIPELINE aller Jobs steckt in `live` (`_virtual_stock` zaehlt jobs_by_char ungefiltert)").
- `eve_trader/ui/mw_bauplan_tabs.py:12484–12497` (`_why_for`): Runplaner-Segment „ℹ Not planned" sagt für dieses Item „covered by the pipeline (running/finished jobs) – **nothing to do**".
- `eve_trader/ui/mw_bauplan_tabs.py:6663–6683`: Materialzeile sagt „enough ✓ · n of them in build" (reason: „nothing to rebuy!"); gleichzeitig hängt dieselbe Zeile den roten Live-Fehlt-Prefix an (`:7058–7080`, aus `_bd_fehl_live`). Zwei gegensätzliche Aussagen in einer Zeile.
- Baukosten: `plan["mat_cost"]`/`buy` enthalten das Item nicht → „Build cost"/„Total profit" (`mw_bauplan_fenster.py:7345–7360, 8268–8310`) sind um den realen Kaufposten zu niedrig, den die Rest-Einkaufsliste (über `_rest_fehlt`, `mw_bauplan_fenster.py:1653–1659`) gleichzeitig verlangt.

**Klick-/Bau-Szenario:** Gespeicherter Plan A fährt gerade Reaktions-Jobs für X (25 Runs laufen). Nutzer öffnet Plan B, der X ebenfalls braucht, und drückt „Neu berechnen" (oder ein ESI-Refresh rechnet neu, ungefroren). Plan B zählt A's Pipeline als eigenen Bestand: Runplaner „nothing to do", Materialstatus „enough · in build", Baukosten ohne X — die Fehlt-Zeile (emm721-korrekt) und die Rest-Einkaufsliste sagen dagegen „X fehlt / kaufen". Wer dem Runplaner glaubt, steht ohne Material da.

---

## Befund 3 — Stock Locations vs. Bauplan: laufende Jobs zählen nur im Bauplan (dokumentiert offene Lücke)

**Schweregrad: MITTEL** (zwei Fenster, zwei Einkaufslisten; Richtung „zu viel kaufen" — bewusst konservativ, aber unerklärt widersprüchlich)

**Stellen:**
- `eve_trader/lagerorte.py:474–477`: ausdrücklich „**OFFEN** (eigene Messung): die Erledigt-Karte dieser Seite auf denselben Stand bringen wie `_rest_geliefert_jetzt`."
- `eve_trader/lagerorte.py:127–168` (`delivered_geraten`): zählt nur **abgelieferte** Jobs seit `frozen_ts`; `:429–520` (`bedarf_aus_plaenen`): offener Bedarf = Plan-Runs minus `gebaute_runs` (Zuordnung + Haken + geliefert).
- `eve_trader/ui/main_window.py:33413–33460` (`_rest_geliefert_jetzt`): der Bauplan zählt zusätzlich **laufende** Jobs (bei plan-gefilterter Karte) als erledigt.

**Klick-/Bau-Szenario:** Nutzer startet alle Runs eines eingefrorenen Plans (nichts abgeliefert). Materials-Tab: „covered for the remaining runs ✓ / 0 zu kaufen". Stock-Locations-Seite: die Zutaten derselben Runs stehen weiter als Bedarf/rot (Material ist im Spiel längst verbraucht). Kauft er dort die Sammel-Einkaufsliste, kauft er doppelt. Teilabmilderung: „was ein Plan selbst baut, meldet er nicht" (emm527, `lagerorte.py:520–526`) deckt nur Eigenbau-Items, nicht deren Rohstoffe.

---

## Befund 4 — Runplaner-Hand-Haken verfallen still bei Umverteilung (Schlüssel enthält Charakter-ID)

**Schweregrad: GERING** (sichere Richtung — Bedarf steigt wieder; aber Anzeige und Einkaufsliste „springen" nach einem Charakter-/Zielzeit-Wechsel)

**Stellen:**
- `eve_trader/ui/main_window.py:33444–33452`: Hand-Haken zählen nur über `_bd_runplan_runs_by_key`; `mw_bauplan_tabs.py:9654` baut diese Karte bei jedem Runplaner-Aufbau neu. Haken-Schlüssel tragen die cid (`_char_zeile`, `mw_bauplan_tabs.py:8294–8300`; Bau-Zeilen analog).
- In MEMORY.md (emm742-Abschluss) als offener Komplex benannt („Haken-Wanderung, Schluessel enthaelt cid").

**Klick-/Bau-Szenario:** Nutzer hakt bei einem UNGEFRORENEN Plan 10 Runs bei Charakter A ab, nimmt dann A aus den Bau-Charakteren (oder ändert die Zielzeit → Neuverteilung auf B). Der alte Schlüssel existiert in `runs_by_key` nicht mehr → die 10 Runs gelten wieder als offen, Materials-Tab und Einkaufsliste verlangen die Zutaten erneut, obwohl er sie abgehakt hatte. Kein ISK-Verlust, aber genau das „Zahlen ändern sich ohne erkennbaren Grund"-Muster.

---

## Befund 5 — Surplus/Überproduktion: korrekt reserviert, aber nur mit gesetztem Schloss; Pipeline-Überschuss siehe Befund 2

**Schweregrad: GERING** (dokumentierter Opt-in-Entscheid, kein Rechenfehler — hier festgehalten, weil die Frage ausdrücklich gestellt war)

**Stellen:**
- `eve_trader/ui/mw_helpers.py:1532–1563` (`_plan_reserve_map`): reserviert `build_made` **inkl. Reaktions-Überschuss** — korrekt.
- `eve_trader/ui/mw_helpers.py:1884–1888` (`_reservierende_plaene`): die Reservierung wirkt nur bei `p.get("reserve")` (Schloss gesetzt) und nur für Pläne mit Rang VOR dem lesenden Plan.
- Folge: der abgelieferte Überschuss eines NICHT reservierten (oder rang-niedrigeren) Plans A zählt für Plan B als freier Bestand. Das ist der dokumentierte Nutzer-Entscheid („reserviert heißt vergeben", Opt-in). Der Überschuss in der **laufenden** Pipeline zählt dagegen immer ungefiltert mit (voller `runs × output`, `_virtual_stock`) — das ist Befund 2.

---

## Geprüft, KEINE Divergenz gefunden

- **Gewinn/Baukosten-Kopf (Build cost / Total profit / Margin):** rechnet konsistent auf Voll-Plan-Basis. Eingefroren = Schnappschuss (Preise, Mengen, `stock_cost`), Tooltip benennt es (`mw_bauplan_fenster.py:8216–8222`); Fracht aus `plan["buy"]` MIT Puffer (`:7379–7415`, emm545), also derselben Basis wie die Kosten — die Rest-Einkaufsliste hat ihre eigene Detail-Zeile „Einkauf jetzt" (emm547, `:1598ff`), keine Vermischung der Zeitbasen. Ein teilgebauter Plan zeigt bewusst die Gesamt-Plan-Ökonomie, keine Fantasiezahlen.
- **Runplaner RUNS/BLUEPRINTS/Wellen:** verteilen bewusst die vollen `build_runs` (eingefroren: feste Zuteilung, emm681 `mw_bauplan_tabs.py:9604–9609`); Erledigt-Budget läuft über `rest_und_budget`/`budget_eigene_zuerst` (`mw_helpers.py:3719–3760`), Wellen-Punkte verbrauchen den Job-Pool (emm519). Anzeige (darf färben) und Einkauf (`delivered_sicher`) sind seit emm667 dieselbe Karte.
- **Einkaufsdialog-Kopf vs. Materials-Tab „0 zu kaufen – n werden gebaut":** seit emm665/Sitzung 20 beidseitig über `_bd_plan_builds` abgeglichen (`main_window.py:23933–23957`, `mw_bauplan_tabs.py:7404–7424`); Zählweisen stimmen überein (n_missing schließt „covered for remaining runs" aus, `mw_bauplan_tabs.py:6775–6790`).
- **Haken-Freigabe von Reservierungen:** Hand-Haken geben seit emm750 nichts mehr frei (`mw_helpers.py:1148–1168`) — bewusster Nutzer-Entscheid, Preis dokumentiert (emm638-Richtung).


==========================================================================
# TEIL D: # Simulationsbefunde Kreuz-und-quer-Bauen (31.10.2026, Harness kreuzquer_sim.py)

Harness: echte Funktionen (production_plan, _plan_reserve_map,
plan_anspruch_mitlaufend, bestand_nach_reservierungen, material_menge),
nur die sqlite-Jobzuordnung (_belegt_fuer_plan) durch Sim-Zähler ersetzt.
Positivkontrolle: der bekannte emm787-Fall (ohne Schloss) wird erkannt.

## S-BEFUND 1 (MITTEL, GEMESSEN): Übersubskription durch die
## „faire Aufteilung" — Einkaufsliste kauft zu wenig, wenn
## eigener + fremder Anspruch > Bestand
Fundstelle: mw_helpers.bestand_nach_reservierungen (~1693):
`max(Bestand - fremd, eigen)` — die dokumentierte Gleichung
`eigen + max(0, Bestand - alle) == max(Bestand - fremd, eigen)` gilt NUR
solange eigen+fremd <= Bestand. Liegt die Summe darüber, sieht JEDER Plan
seinen vollen Anspruch gedeckt, niemand kauft die Lücke nach.
GEMESSEN (Fuzz-Seed 1088): Hangar 29'600 Trit, fremd 23'700, eigen 5'901
(Summe 29'601) -> Plan nutzt 5'901 aus Bestand, kauft 4'999 - am Ende
fehlt exakt 1 Tritanium. Die 1er-Differenz entsteht hier durch die
int()-Abschneidung der mitlaufenden Freigabe (int(_q*_anteil), ~1233):
der Anspruch bleibt 1 höher als die physisch verbliebene Eigenmenge.
GRÖSSER wird die Lücke durch: Überbau (mehr Runs als geplant, S3:
5'000 Trit), Verkauf reservierter Ware, Neu-berechnen+Einfrieren mitten
im Teilbau (Fortschritt-Reset, S7-Seeds 21/28/32/72/113: 90-760 REAC).
Die App zeigt `_bd_reserved_pending` („wartet auf Lieferung") an, aber
KEINE Einkaufsliste kauft die Übersubskription nach.

## S-BEFUND 2 (EINORDNUNG, kein neuer Fehler): ohne Schloss ist jede
## Mehrplan-Rechnung falsch (S5): A kauft, B zählt A's Einkäufe als frei.
Dokumentiertes Verhalten (Grund für das Schloss), emm787 verwandt.
Für die Veröffentlichung heißt das: Nutzer OHNE Schloss laufen bei
mehreren Plänen zwangsläufig in Fehlbeträge - Tutorial/UI sollte das
Schloss bei >1 gespeichertem Plan aktiv nahelegen.

## S-BEFUND 3 (MITTEL, GEMESSEN): „Neu berechnen" mitten im Teilbau
## verliert den Fortschritt und plant das volle Soll erneut
Harness-Nachstellung: Re-Einfrieren setzt frozen_ts zurück
(belegte_runs_seit zählt nur Jobs SEIT dem Einfrieren), der frische
Schnappschuss enthält wieder die vollen build_runs - bereits gebaute
Endprodukte werden nie gegen das Soll gerechnet (production_plan:
Endprodukt „immer bauen, kein Bestand"). Wer mitten im Plan neu
berechnet, bekommt eine Einkaufsliste für das VOLLE Soll, dessen
Deckung sich teilweise aus Beständen speist, die andere Pläne
beanspruchen (-> Befund 1 verstärkt). Hand-Haken (checked_runplan)
überleben zwar, aber ESI-Fortschritt vor dem neuen frozen_ts ist weg.

## Nebenbefund (GERING): Mengen auf Einkaufslisten sind floats
production_plan liefert buy-Mengen als float (z.B. 23'400.0);
einkauf_posten schneidet mit int() ab statt aufzurunden (REGEL 3).
Bei glatten Werten folgenlos; ein künftiger float-Drift würde still
abrunden. Aufrunden wäre die sichere Richtung.
