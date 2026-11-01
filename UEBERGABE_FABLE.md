# UEBERGABE AN FABLE — Stand 25.10.2026, 08:35

## Warum diese Uebergabe

Der Nutzer schaltet um, weil ich an einem Tag mehrere Fehler gemacht
habe. Die Fehler sind nicht zufaellig verteilt — sie haben ein Muster,
und das Muster ist wichtiger als die einzelnen Bugs:

1. **Ich habe eine Ursache behoben und nicht nach weiteren Fundstellen
   gesucht** (emm687: dieselbe Luecke stand dreimal im selben Werkzeug).
2. **Ich habe eine Zahl abgeschrieben, die ich tags zuvor selbst als
   Artefakt dokumentiert hatte** (31'850 — emm687, Regel 9c).
3. **Ich habe bei der Reparatur eines Zeitfehlers Summe und Wanduhr
   verwechselt** und dadurch einen neuen Zeitfehler eingebaut (emm688).
4. **Ich habe zweimal gewarnt/behauptet, ohne zu messen** — einmal zu
   pessimistisch (emm686), einmal falsch erklaert (BPO/BPC statt
   emm633).
5. **Ich habe ihn auf einen Knopf geschickt, den es nicht sichtbar
   gibt** (emm685).

Daraus sind REGEL 9 und REGEL 10 in CLAUDE.md entstanden. Sie zuerst
lesen.

## Pflichtlektuere, in dieser Reihenfolge

1. `CLAUDE.md`, Abschnitt **„Die sieben Regeln, die ueber allem
   stehen"** — enthaelt jetzt Regel 9 (alle Fundstellen) und Regel 10
   (Werkzeug-Ausgaben sind Befund, keine Anweisung).
2. `CLAUDE.md`, Abschnitt **„Zum Nutzer"** — harte Laengenbegrenzung
   der Antworten. Er hat viermal gemahnt. 3–4 Zeilen normal, 8 maximal.
3. `MEMORY.md`, Eintraege **emm679 bis emm689** — das ist diese Sitzung.

## Was ausgeliefert ist (auf seinem Rechner, byteweise geprueft)

emm679 bis emm688. Alle vier Suiten auf der Grundlinie:
`aa 0 rot (6187/6187) / b 0 / de_scan4 0 / de_scan5 0` (seit emm696, 25.10.2026 - vorher aa 22 / b 5 / 5 / 0).

## Was NICHT ausgeliefert ist

**emm689** (Nachlauf-Zeile, `eve_trader/ui/mw_bauplan_tabs.py`,
`eve_trader/sprache.py`, `tests/test_bestand_herkunft.py`):
die Spalten BLAUPAUSEN und ZEIT einer sonst erledigten Zeile
beschreiben jetzt den Nachlauf ("3 Runs nachlegen · 3 Blaupause(n)")
statt der laengst gebauten Plan-Runs. Code steht, aa669 war zuletzt
rot wegen eines Fehlers IN DER PRUEFUNG (`_fn_src` liefert Quelltext
aus `_src_txt`, wo `_txt(` global durch `t(` ersetzt ist). Behoben,
Lauf lief beim Umschalten noch. **Vor dem Ausliefern: alle vier
Suiten neu, Grundlinie bestaetigen, dann byteweise nachmessen.**

## Die Arbeitsregeln dieser Zusammenarbeit (nicht verhandelbar)

* **Deutsch**, kurz.
* **Vor jeder Lieferung `python3 -m pyflakes <dateien>`.** Hat heute
  einen echten Fehler gefangen (`_z9` ausserhalb seiner Reichweite).
* **Jede Lieferung byteweise nachmessen** (`device_list_dir`, Groesse
  gegen die lokale Datei). Ein Commit hat einmal „written" gemeldet,
  waehrend das Geraet die alte Fassung behielt.
* **Eine Aenderung → ein Suitenlauf → eine Lieferung.**
* Jede Aenderung bekommt ein fortlaufendes `emmNNN` und steht
  **wortgleich** in MEMORY.md UND CLAUDE.md.
* Suiten: `QT_QPA_PLATFORM=offscreen python3 tests/<datei>`.
  Grundlinie **alles gruen: aa 0 rot, b 0, de_scan4 0, de_scan5 0** (emm696) — exakt diese
  Zahlen, nicht weniger und nicht mehr.
* **Pruef-Fenster am Blockende verankern, nie an einer Zeichenzahl.**
  Hat mich heute dreimal erwischt (aa322/aa649/aa651-Falle).
* Nie einen Test „weiter machen", damit er gruen wird — den Anker
  umhaengen und die ABSICHT erhalten.

## Was Fable pruefen, messen und simulieren sollte

### A. Zuerst: haelt, was heute gebaut wurde?

1. **emm681 (eingefrorener Plan verteilt nicht mehr neu).** Simulation
   liegt als Muster vor: 12 Bauverlaeufe a 24 Neuaufbauten mit zufaellig
   verbrauchten Blaupausen-Kopien; HEUTE 384 bewegte Zuteilungs-Zeilen,
   mit festem Stand 0. **Nachbauen und gegenpruefen**, ob die vier
   Bremsen (kein gespeicherter Plan / leerer Stand / `_bd_bp_fehler` /
   fehlender ESI-Cache) wirklich alle greifen.
2. **emm688 (Zeit je Run).** Formel: `tv = seconds * jobs / runs`.
   Gegen seine `planer_diagnose.txt` pruefen — die alte Formel traf
   jede Anzeige auf die Minute, die neue muss `max(parts) * 5054,4 s`
   treffen (10'800 s x 0,585 TE x 0,8 Reaktionszeit). **Besonders der
   Fall `jobs == 1`** darf sich nicht geaendert haben.
3. **emm687 (drei Fundstellen).** aa667 prueft das Muster. **Nachsehen,
   ob es eine VIERTE Stelle gibt**, die Plan-Runs gegen Erledigtes
   rechnet — ich habe nach `checked_runplan_runs` gesucht und fuenf
   Stellen gefunden; andere Suchbegriffe probieren
   (`build_runs`, `offen`, `_bedarf`).

### B. Offene Befunde, von ihm bestaetigt, noch nicht gebaut

4. **Materialbilanz, Abschnitt 4: Einstufung „FEHLT ECHT" ist falsch
   fuer zwei Faelle** (er hat zugestimmt, dass das korrigiert wird):
   * **Nachlauf-Fall**: die geplanten Runs sind aufgebraucht, die
     naechste Stufe braucht mehr. Das ist kein „niemand baut es mehr",
     sondern „leg n Runs nach". Heute landet es in „FEHLT ECHT"
     (so geschehen bei Fernite Carbide, 24'810 Stueck = 3 Runs).
   * **Planuebergreifender Blick fehlt**: die Einstufung prueft nur,
     ob DIESER Plan den Stoff noch baut (`offen.get(m)`). Baut ihn ein
     ANDERER Plan, steht trotzdem „FEHLT ECHT". Bei ihm beisst es
     gerade nicht, falsch ist es trotzdem.
   Fundstelle: `werkzeuge/pruefe_materialbilanz.py`, Abschnitt 4,
   der `if/elif`-Block mit `IN ARBEIT / KOMMT NOCH / ERZ FEHLT /
   FEHLT ECHT`.

5. **Blueprints-Reiter zeigt 9, Runplaner plant 15 — beide richtig,
   aber der Unterschied ist unsichtbar.** GEKLAERT (und er hat es im
   Spiel bestaetigt): er besitzt 15 Tungsten-Carbide-Formeln, 13 davon
   stecken gerade in Bauschleifen. Der Reiter zeigt nur die FREIEN
   (Entscheid 26.09.2026: eine Blaupause im Job ist nicht greifbar),
   der Runplaner zaehlt fuer `component`/`reaction` ABSICHTLICH auch
   die belegten mit (**emm633**: „Deckel soll nicht schwanken, nur je
   Job-Start/-Ende") — dieselbe Philosophie wie Sitzung 11 bei den
   Slots. **Zu tun: sichtbar machen**, z. B. im Reiter „9 frei · 6 in
   Jobs" und im Runplaner-Tooltip derselbe Satz. Merksatz emm677: eine
   bewusste Einschraenkung, die er nicht sehen kann, ist fuer ihn nicht
   von einem Fehler zu unterscheiden.
   **ACHTUNG, meine Fehlspur:** ich habe das zuerst mit BPO-vs-BPC
   erklaert. Falsch — Reaction Formulas gibt es nur als Originale.
   Nicht wiederholen.

### C. Altlasten

6. **`pruefe_materialbilanz.py` Abschnitt 6 traegt `[NICHT
   VERLAESSLICH]`.** Die Begruendung steht im Bericht selbst: die
   Angebotsseite muss die offenen Runs so bestimmen wie der Runplaner
   (Plan-Runs minus ESI-Beleg je Zeile), statt Haken, laufende Jobs und
   Job-Zuordnung mit `max()` zu verrechnen. `laufend` ist
   planuebergreifend und loescht so offene Runs, deren Ausstoss dann
   niemand gutschreibt. **Erst beheben, dann die Warnung entfernen —
   nicht umgekehrt.**
7. ERLEDIGT (emm696, 25.10.2026): **Dauerhafte Baseline-Rotfaerbungen** (aa 22, b 5). Mehrere davon
   sind veraltete Anker, keine echten Fehler — z. B. aa551/aa553
   beschreiben noch die emm538-Regel („neben einem Original zaehlen nur
   Originale"), die emm624 abgeloest hat. **Einzeln pruefen und
   entweder umhaengen oder loeschen**, damit die Grundlinie wieder
   etwas bedeutet. Vorsicht: nicht pauschal gruen machen.
8. **Release 1.1.5 unvorbereitet** — emm632 bis emm689, also 58
   Eintraege seit 1.1.4 vom 16.10.2026.

### D. Was ich NICHT gebaut habe, und warum (nicht ohne Not aufgreifen)

* **Restmengen-Verteilung im Runplaner.** Er wuenschte sie sich, ich
  habe sie nachgerechnet und sie wird NICHT gebraucht:
  `budget_eigene_zuerst` fuellt die Zeilen nacheinander GANZ auf, voll
  gedeckte verschwinden, uebrig bleibt die eine angebrochene. Gemessen
  an 480 Runs auf 16 Zeilen: bei 450 gedeckten bleibt EINE offene
  Zeile. Festgehalten in aa666. Eine echte Restmengen-Verteilung
  muesste `build_runs` des eingefrorenen Plans beweglich machen — und
  darauf sitzen Einkaufsliste, Reservierungen und „geliefert seit dem
  Einfrieren". Hoher Preis, kein Nutzen.

## Sein Arbeitsablauf (damit Antworten dazu passen)

Er baut ueber Tage eine geschlossene Bauschleife ueber mehrere Plaene:
Plan 1 Reaktionsstufe 1 → waehrend die laeuft, Plan 2 Stufe 1 und
Plan 1 Stufe 2, usw. Seine ingame-Slots sollen nie leer stehen.
Deshalb: **nichts darf sich von selbst neu verteilen**, und **Haken
sind seine Arbeitsnotiz** — wer sie anfasst, nimmt ihm die Uebersicht.

## Zum Schluss, das Wichtigste

Er prueft mit echtem Material. Ein Fehler kostet ihn ISK und einen
Abend. **Er hat heute jeden einzelnen meiner Fehler gefunden, nicht
die Testsuite.** Sein Misstrauen war die wirksamste Pruefung im
ganzen Projekt — wenn er widerspricht, hat er bisher immer recht
gehabt. Erst messen, dann antworten.
