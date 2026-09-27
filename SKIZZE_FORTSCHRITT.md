# Skizze — woher der Bau-Fortschritt kommt (21.09.2026)

**Status: SKIZZE. Nichts davon ist gebaut.** Sie liegt vor dem Bauen auf dem
Tisch, damit du auf Papier entscheidest statt auf mein Wort — dasselbe
Vorgehen wie bei den zwei Wegen zum Multi Buildplaner.

Alle Zahlen und Zitate hier sind am Quelltext geprüft, nicht erinnert.

---

## 1. Was heute passiert (Ist-Zustand, gemessen)

Der Fortschritt eines Plans entsteht aus **zwei Quellen**:

| Quelle | Woher | Plan-Zuordnung |
|---|---|---|
| `_bd_runplan_checked` | Haken, die DU setzt | **eindeutig** — du hast im Plan geklickt |
| `_bd_runplan_delivered` | ESI-Jobs (`_frozen_auto_checked`) | **geraten** — Item + Aktivität + Zeitpunkt |

Die zweite Quelle ist das Problem: **ESI sagt nicht, zu welchem Bauplan ein
Job gehört.** Es gibt in der ESI-Antwort schlicht kein Feld dafür.

**Nachgestellt am 21.09.2026 (aa382):** ein gelieferter Job über 2'250 Runs,
Plan A braucht 2'250 (richtig), Plan B nur 400 — und bekam trotzdem 2'250
angerechnet.

### Wer diese Zahlen liest

`_bd_runplan_delivered` steht an **21 Stellen**, `_bd_runplan_checked` an
**14**. Gelesen wird beides von:

* der Runplaner-Anzeige (offene Runs, grüner/cyaner Punkt, Gedimmtes)
* `_restbedarf_jetzt` → **der Einkaufsliste**
* `_fehlbedarf_jetzt` → der Fehlbedarfs-Vorschau
* `_reserve_map_mitlaufend` → **der Reservierung** (nur über die Haken)
* der Plan-Karte (Fortschrittsbalken) und der Gewinn-Übersicht

Am 21.09.2026 wurde die Materialseite abgetrennt
(`_bd_runplan_delivered_sicher`, aa382): Einkaufsliste und Fehlbedarf rechnen
seitdem nur mit sicher zugeordneten Jobs. **Die Anzeige rät weiter** — das
war Absicht, ist aber nur die halbe Strecke.

---

## 2. Die Logik dahinter — in Frage gestellt

Bevor gebaut wird, gehören die Annahmen geprüft, auf denen der Vorschlag
steht. Sechs davon halten der Prüfung **nicht** stand oder brauchen eine
Bedingung.

### 2.1 „Der Kopier-Klick ist der Beweis" — FALSCH, so wie ich es sagte

Ich habe im Gespräch behauptet, der Klick auf den amberne Run-Knopf belege
die Zuordnung. Das stimmt nicht:

* man kann klicken und den Job dann doch nicht starten,
* man kann versehentlich oder zweimal klicken,
* bei „6 × 375" klickt man **einmal** und startet **sechs** Jobs.

Ein Klick ist also weder ein Job noch ein Beweis.

**Korrigierte Logik, und erst die trägt:**

> **ESI belegt, DASS gebaut wurde. Der Klick belegt, FÜR WEN.**

Der Klick allein ändert gar nichts. Er wird erst wirksam, wenn innerhalb
eines Zeitfensters ein ESI-Job mit passendem Item und passender Run-Zahl
auftaucht. Dann ist er der Entscheider zwischen zwei Plänen — nicht die
Quelle des Fortschritts. Damit kann ein Fehlklick nichts kaputtmachen: ohne
echten Job bleibt er folgenlos.

### 2.2 „Ein Klick ordnet einen Job zu" — zu eng

Bei mehreren Blaupausen je Zeile gehört der Klick der **Zeile**, nicht dem
einzelnen Job. Richtig ist: alle Jobs dieses Items im Zeitfenster gehen an
diesen Plan, **bis dessen Plan-Runs voll sind** — der Deckel von
`delivered_sicher` gilt weiter.

### 2.3 „Wer nicht klickt, ist selbst schuld" — nicht tragbar

Man kann die Zahl auch abtippen. Der Klick ist deshalb eine **zusätzliche**
Quelle, nie ein Ersatz. Ohne Klick greift die Reihenfolge von heute:
Run-Signatur → Reservierung → im Zweifel gar nichts anrechnen.

### 2.4 „Ein Protokoll wächst nur" — gefährlich bei abgebrochenen Jobs

Ein Job kann im Spiel abgebrochen werden. Ein reines Wachstums-Protokoll
würde ihn für immer als gebaut zählen. **Deshalb:** ein Eintrag ist nur so
lange gültig, wie ESI ihn als `delivered` bestätigt. Das Protokoll speichert
die **Zuordnung** (Job → Plan) dauerhaft, die **Tatsache** bleibt ESI.

### 2.5 „Das Protokoll gehört in die Einstellungen" — falsch

`config.save_settings` schreibt `settings.json` bei **jedem** Speichern
komplett neu (`json.dumps` der ganzen Struktur). Ein wachsendes Protokoll
dort würde jedes Speichern verlangsamen und die Datei aufblähen — in der
schon die Baupläne samt Schnappschüssen liegen.

**Richtige Heimat: `industry.db` (SQLite, `store.py`).** Das Muster gibt es
dort bereits: `favorites` und `wallet_journal` werden per
`CREATE TABLE IF NOT EXISTS` nachträglich angelegt.

### 2.6 „Danach ist die Reservierung sicher automatisch" — nur mit Bedingung

Automatisches Freigeben ist die **einzige** Änderung in dieser Kette, die in
die gefährliche Richtung kippen kann: gibt sie zu früh frei, sieht ein
anderer Plan Material als verfügbar, das noch gebraucht wird. Die bestehende
Sperre („ein Haken zählt erst, wenn der ESI-Bestand jünger ist als der
Haken") muss deshalb unverändert auch für Protokoll-Einträge gelten.

---

## 3. Was gebaut würde

### Stufe B — die Zuordnung belegen (klein, für sich lauffähig)

Neue Tabelle in `industry.db`:

```
job_zuordnung(job_id INTEGER PRIMARY KEY, plan_id, type_id, runs,
              quelle TEXT, ts REAL)
```

`quelle` ist einer von: `klick` · `signatur` · `reservierung` · `nutzer`.

* Der Run-Knopf merkt sich beim Klick **Plan, Item, Runs, Zeit** (er kennt
  alle vier bereits — `a["tid"]`, `a["name"]`, `_r`, `_bd_open_plan_id`).
* Beim nächsten Bestands-Abruf werden neue ESI-Jobs gegen diese Klicks
  gehalten. Passt einer, entsteht ein Eintrag mit `quelle="klick"`.
* Bleibt ein Job unzugeordnet, greift die Run-Signatur, dann die
  Reservierung. Passt nichts, bleibt er **ohne Eintrag** — und zählt für
  niemanden.
* `_frozen_auto_checked` liest ab dann **zuerst** die Tabelle und nur für
  den Rest die alte Heuristik.

**Sofort sichtbarer Gewinn:** ein Job gehört einem Plan, einmal und
dauerhaft. Die Runs anderer Pläne bewegen sich nicht mehr.

### Stufe C — der Zustand ist die Summe der Belege

Ist die Zuordnung stabil, wird `_bd_runplan_delivered` nicht mehr bei jedem
Abruf neu geraten, sondern aus der Tabelle gelesen. Die beiden Karten
(geraten / sicher) fallen wieder zu **einer** zusammen — die Trennung vom
21.09. war das Pflaster, die Tabelle ist die Heilung.

Dann, und erst dann: die Reservierung bucht ihre Zutaten auch ohne Hand-Haken
ab (Stufe 2.6, mit der ESI-Verzugs-Sperre).

### Nicht angefasst

* `industry.schedule_build` — die eigentliche Runplaner-Rechnung. Sie
  bekommt Runs und Slots und verteilt sie; sie ist nicht die Fehlerquelle.
* Die Slot-Logik. Dass mit dem **Maximum** statt den freien Slots geplant
  wird, ist ein Nutzer-Entscheid aus Sitzung 11 mit Befund dahinter.
* Die Haken. Sie bleiben die stärkste Quelle — du überstimmst jede Automatik.

---

## 4. Risiko und Rückfall

| | |
|---|---|
| Stufe B falsch | ein Plan sieht seinen eigenen Fortschritt nicht → du baust doppelt. Material liegt da. **Kostet Arbeit, nie Material.** |
| Stufe C falsch | wie B, plus: die Reservierung könnte zu früh freigeben → **gefährliche Richtung**, deshalb zuletzt und nur mit der Verzugs-Sperre |
| Alte Pläne | die Tabelle startet leer; ohne Eintrag gilt exakt das heutige Verhalten. Keine Migration nötig. |
| Notausgang | der Fertig-Knopf auf der Plan-Karte gibt jede Reservierung sofort frei — unabhängig von allem hier. |

---

## 5. Reihenfolge

1. **1.0.9 fertig und veröffentlicht.** Der Material-Fix vom 21.09. gehört zu
   den Nutzern, bevor ein Fundament angefasst wird.
2. Stufe B, mit Wächtern und Mutationen wie gewohnt.
3. Eine Weile damit bauen. Bleiben die Runs stabil?
4. Stufe C.
5. Reservierung zuletzt.
