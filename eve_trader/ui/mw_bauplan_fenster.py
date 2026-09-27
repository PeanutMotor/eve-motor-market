"""Das Bauplan-Fenster selbst: `_show_build_detail` (5'461 Zeilen).

Schnitt 3 der main_window-Zerlegung (Sitzung 10) und mit Abstand der
groesste Brocken - die Methode war allein rund ein Fuenftel des
Methodencodes im Hauptfenster (Messung aus Sitzung 8, `kennzahlen.py`).

Der Rumpf ist WOERTLICH aus main_window.py verschoben, kein Zeichen
geaendert. Fuer den Nutzer aendert sich dadurch NICHTS - der Dialog sieht
aus und rechnet wie vorher; der Schnitt macht nur kuenftige Aenderungen
schneller und weniger fehleranfaellig.

Die Methode greift per `self.` auf 58 weitere MainWindow-Methoden und
82 Attribute zu; das loest sich zur Laufzeit an der zusammengesetzten
Klasse auf. Direkte `MainWindow.`-Bezuege gibt es KEINE (vorher per AST
geprueft), deshalb konnte alles unveraendert umziehen.

Die Tab-Fueller des Dialogs stehen weiter in `mw_bauplan_tabs.py`
(Schnitt 1), die Werkzeug-Fenster Optimierer/Leiter in `mw_optimizer.py`
(Schnitt 2). `open_build_detail` - der RECHNENDE Vorlauf, der die Optionen
je Stufe zusammenstellt - ist bewusst in main_window.py geblieben.
"""
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QMessageBox, QPushButton,
                               QScrollArea, QSpinBox, QSplitter, QTableWidget,
                               QTabWidget, QVBoxLayout, QWidget)

from .. import config, esi, industry, reprocess, store
from ..workers import Worker
from . import icons
from ..sprache import t
from . import theme
from .mw_basis import (IskGroupedSpin, IskMillionSpin, MinimizableDialog,
                       ROLLE_KOPIERNAME, combos_ohne_mausrad, isk,
                       kopier_text_rect, tab_icon, tab_icon_at)


class BauplanFenster:
    """Mixin: der Bauplan-Dialog (`_show_build_detail`)."""

    def _offener_bauplan(self):
        """Das bereits offene Bauplan-Fenster, oder None.

        Gleiche Pruefung wie in `_tool_parent`: nach einem deleteLater() lebt
        der Python-Wrapper weiter, waehrend das C++-Objekt schon weg ist -
        shiboken sagt es sicher, isVisible() nicht.
        """
        d = getattr(self, "_bd_dialog", None)
        if d is None:
            return None
        try:
            import shiboken6
            if not shiboken6.isValid(d):
                self._bd_dialog = None
                return None
        except Exception:
            pass
        try:
            return d if d.isVisible() else None
        except RuntimeError:
            self._bd_dialog = None
            return None

    def _sched_name_klick(self, item, column):
        """Linksklick auf den Item-Namen im Runplaner kopiert den Blaupausen-
        bzw. Reaktions-Formel-Namen (Nutzer, 15.09.2026).

        NUR AUF DEM TEXT, NICHT AUF DEM KAESTCHEN: `itemClicked` kommt auch,
        wenn man den Haken setzt - ohne Positionspruefung wuerde jeder Haken
        still die Zwischenablage ueberschreiben. Deshalb wird dieselbe
        Rechteck-Rechnung benutzt, die auch den Rahmen malt: was ausserhalb
        des gerahmten Textes liegt, ist kein Kopierklick.

        Eine Bequemlichkeit darf den Runplaner nie kosten - alles in try.
        """
        try:
            if column != 0 or item is None:
                return
            name = item.data(0, ROLLE_KOPIERNAME)
            if not name:
                return
            tree = item.treeWidget()
            if tree is None:
                return
            from PySide6.QtGui import QCursor
            idx = tree.indexFromItem(item, 0)
            rect = kopier_text_rect(tree, idx, tree.visualRect(idx))
            pos = tree.viewport().mapFromGlobal(QCursor.pos())
            if rect is not None and not rect.contains(pos):
                return
            self._copy_bp_name_value(name)
        except Exception:
            pass

    def _bd_contract_knopf(self, hat_preis):
        """Contract-Knopf zeigen und blinken lassen, solange dieser Bauplan
        KEINEN Verkaufspreis hat.

        NUTZER, 15.09.2026: der Knopf soll ersichtlich sein und "im richtigen
        Moment" blinken wie der Markt-Scan-Knopf. Der richtige Moment ist
        genau der, in dem das Verkaufsfeld leer bleibt - bei Capitals, die in
        Jita keine Sell-Orders haben und deren Contract-Preise noch nicht
        geladen sind.

        DER TIMER HAENGT AM KNOPF, nicht am Hauptfenster: der Bauplan-Dialog
        wird bei jedem Oeffnen neu gebaut, ein Timer am Fenster zeigte danach
        auf einen geloeschten Knopf (in PySide6 ein harter Absturz, kein
        Python-Fehler). Als Kind des Knopfes stirbt er mit ihm.

        Eine Anzeige darf den Bauplan NIE kosten - deshalb steht alles in
        try/except, wie beim Rest der Fuell-Funktion.
        """
        btn = getattr(self, "_bd_ct_btn", None)
        if btn is None:
            return
        try:
            from PySide6.QtCore import QTimer as _QTimer
            btn.setVisible(not hat_preis)
            tmr = getattr(btn, "_ct_blink_timer", None)
            if hat_preis:
                if tmr is not None and tmr.isActive():
                    tmr.stop()
                btn.setStyleSheet(getattr(btn, "_ct_css", ""))
                btn._ct_blink_an = False
                return
            if tmr is None:
                tmr = _QTimer(btn)          # Kind des Knopfes, s. oben
                tmr.setInterval(700)        # derselbe Takt wie der Markt-Scan

                def _schritt(_b=btn):
                    try:
                        _b._ct_blink_an = not getattr(_b, "_ct_blink_an", False)
                        self._blink_rahmen(_b, _b._ct_blink_an,
                                           getattr(_b, "_ct_css", ""))
                    except Exception:
                        pass
                tmr.timeout.connect(_schritt)
                btn._ct_blink_timer = tmr
            if not tmr.isActive():
                tmr.start()
        except Exception:
            pass

    def _corp_bau_daten(self, client_id, chars, loc_ids):
        """Corp-Hangar fuers Bauen (1.0.8): Bestand, Blueprints, Jobs.

        Laeuft im Bestands-Worker, NICHT im Oberflaechen-Faden. Gibt ein
        dict zurueck, das der Worker in seinen Pool mischt:
          summe      {type_id: Menge} aus den gewaehlten Divisions
          blueprints [wie fetch_blueprints]
          jobs       {corporation_id: [Jobs]} - unter der CORP-Nummer, damit
                     der virtuelle Bestand sie wie einen Charakter behandelt
          corps      [{"name", "via", "divisions": {n: Name}, "rows": n}]
          ohne_rolle [Corp-Namen ohne Director unter den Charakteren]
          relink     [Charakter-Namen, deren Token den Corp-Scope nicht hat]
          keine_division  True, wenn der Schalter an ist, aber nichts gewaehlt
          failed     [Texte fuer die Fehlerliste]

        `loc_ids`: None = ueberall, sonst nur diese Strukturen - dieselbe
        Grenze wie beim eigenen Bestand.

        DER RIEGEL GEGEN DIE VERDREIFACHUNG steckt in corp.abrufplan: je
        Corporation genau EIN Abruf. Drei Charaktere derselben Corp liefern
        denselben Hangar; ungeprueft zaehlte er dreifach und der Plan kaufte
        ZU WENIG (CLAUDE.md, Abschnitt Corp-Assets).

        Jeder Einzelschritt ist abgefangen: ein fehlgeschlagener Corp-Abruf
        landet in `failed` und im fehler.log, er reisst nie den Bestand der
        Charaktere mit.
        """
        from .. import corp as _corp
        leer = {"summe": {}, "blueprints": [], "jobs": {}, "corps": [],
                "ohne_rolle": [], "relink": [], "keine_division": False,
                "failed": [], "aktiv": False, "bp_ok": True,
                # {location_id: character_id} - Orte mit Corp-Assets (unge-
                # filtert) und der Charakter, der sie aufloesen kann; fuer
                # "Find locations and link all" (Tester-Befund 19.09.2026).
                "orte": {}}
        if not self.settings.get("use_corp"):
            return leer
        out = dict(leer)
        out["aktiv"] = True
        divisions = _corp.divisions_bereinigt(self.settings.get("corp_divisions"))
        if not divisions:
            out["keine_division"] = True
            return out
        namen = {c["character_id"]: c.get("character_name", "?") for c in chars}
        corp_von, rollen_von = {}, {}
        for ch in chars:
            cid = ch["character_id"]
            corp_von[cid] = esi.fetch_character_corporation(cid)
            try:
                _gs = esi.granted_scopes(client_id, cid)
            except Exception as _ge:
                self._log_exception(f"Corp: Scopes {namen.get(cid, cid)}", str(_ge))
                _gs = set()
            if config.CORP_ROLES_SCOPE not in _gs or config.CORP_ASSETS_SCOPE not in _gs:
                # Token ohne Corp-Scope: der Charakter wurde VOR dem
                # Einschalten verknuepft. Beim Namen nennen - "0 Bestand"
                # waere die falsche Aussage.
                out["relink"].append(namen.get(cid, str(cid)))
                rollen_von[cid] = None
                continue
            try:
                rollen_von[cid] = esi.fetch_character_roles(client_id, cid)
            except Exception as _re:
                self._log_exception(f"Corp: Rollen {namen.get(cid, cid)}", str(_re))
                rollen_von[cid] = None
                out["failed"].append(t("Corp roles: {name}").format(name=namen.get(cid, cid)))
        plan, ohne = _corp.abrufplan(chars, corp_von, rollen_von, _corp.ROLLE_ASSETS)
        plan_jobs, _ = _corp.abrufplan(chars, corp_von, rollen_von, _corp.ROLLE_JOBS)
        for corp_id in ohne:
            # Nur melden, wenn es nicht schon am fehlenden Scope liegt -
            # sonst stehen zwei Hinweise fuer eine Ursache da.
            if all(rollen_von.get(c) is None for c in ohne[corp_id]):
                continue
            out["ohne_rolle"].append(esi.fetch_corporation_name(corp_id))
        _ctypes = esi.container_type_ids_safe()
        for corp_id, cid in plan.items():
            cname = esi.fetch_corporation_name(corp_id)
            try:
                assets = esi.fetch_corporation_assets(client_id, cid, corp_id)
                for _o in _corp.orte(assets):
                    out["orte"].setdefault(int(_o), cid)
                summe, je_div = _corp.corp_bestand(assets, divisions, loc_ids, _ctypes)
                for _t, _q in summe.items():
                    out["summe"][int(_t)] = out["summe"].get(int(_t), 0) + int(_q)
            except Exception as _ae:
                self._log_exception(f"Corp: Assets {cname}", str(_ae))
                out["failed"].append(t("Corp assets: {name}").format(name=cname))
                continue
            try:
                div_namen = _corp.division_namen(
                    esi.fetch_corporation_divisions(client_id, cid, corp_id),
                    divisions)
            except Exception as _de:
                self._log_exception(f"Corp: Divisions {cname}", str(_de))
                div_namen = _corp.division_namen(None, divisions)
            try:
                out["blueprints"].extend(
                    esi.fetch_corporation_blueprints(client_id, cid, corp_id,
                                                     divisions))
            except Exception as _be:
                self._log_exception(f"Corp: Blaupausen {cname}", str(_be))
                out["failed"].append(t("Corp blueprints: {name}").format(name=cname))
                out["bp_ok"] = False
            out["corps"].append({"corp_id": int(corp_id), "name": cname,
                                 "via": namen.get(cid, str(cid)),
                                 "divisions": div_namen,
                                 "rows": sum(je_div.values())})
        for corp_id, cid in plan_jobs.items():
            cname = esi.fetch_corporation_name(corp_id)
            try:
                out["jobs"][int(corp_id)] = esi.fetch_corporation_jobs(
                    client_id, cid, corp_id, include_delivered=True)
            except Exception as _je:
                self._log_exception(f"Corp: Jobs {cname}", str(_je))
                out["failed"].append(t("Corp jobs: {name}").format(name=cname))
        # Corp-Blaupausen, die gerade in einem Corp-Job stecken (Research,
        # Kopie, Fertigung), sind im Spiel nicht greifbar - wie bei den
        # persoenlichen (esi.fetch_blueprints, 26.09.2026). Ohne Job-Abruf
        # (keine Rolle / Fehler) bleibt die Liste wie sie ist.
        _alle_jobs = [j for _js in out["jobs"].values() for j in (_js or [])]
        if _alle_jobs and out["blueprints"]:
            out["blueprints"], _belegt = esi.blaupausen_in_jobs(
                out["blueprints"], _alle_jobs)
        return out

    # ---- Reprocessing im Bauplan (1.0.9, Weg B) ----------------------------
    # Compressed Ore statt Minerale kaufen - NUR mit dem Schalter in der
    # Rezeptstruktur (Standard aus). Aus: kein Rechenpfad beruehrt. Die
    # Logik liegt in eve_trader/reprocess.py, die Ausbeute-Formel in industry
    # (gegen die Messung vom 18.09.2026 geprueft).

    def _reprocess_struktur(self):
        """Die Struktur, an der reprocesst wird: die gewaehlte, sonst die
        erste Refinery der Liste, sonst eine NPC-Station (50 %)."""
        structs = self.settings.get("bau_structures", []) or []
        wahl = self.settings.get("bau_reprocess_struct")
        npc = {"type": "npc", "name": t("NPC station"), "id": "npc", "rigs": []}
        if wahl == "npc":
            return npc
        for s in structs:
            if wahl and s.get("id") == wahl:
                return s
        for s in structs:
            if (s.get("type") or "").lower() in reprocess.REFINERY_NAMEN:
                return s
        return npc

    def _reprocess_implants_map(self):
        """{cid(int): prozent} der erkannten Reprocessing-Implantate aus
        settings["bau_char_reproc_implant"] ({str(cid): {"tid","pct","name"}})."""
        out = {}
        for k, v in (self.settings.get("bau_char_reproc_implant", {}) or {}).items():
            try:
                pct = float((v or {}).get("pct") or 0.0)
                if pct > 0.0:
                    out[int(k)] = pct
            except (TypeError, ValueError):
                continue
        return out

    def _reprocess_implants_text(self):
        """Eine Zeile fuer die Karte: "Peanut Motor RX-804 +4 %, ..." oder "".
        """
        m = self.settings.get("bau_char_reproc_implant", {}) or {}
        if not m:
            return ""
        namen = {int(c["character_id"]): (c.get("character_name") or str(c["character_id"]))
                 for c in store.list_characters()}
        teile = []
        for k, v in sorted(m.items(), key=lambda kv: namen.get(int(kv[0]), str(kv[0]))):
            try:
                pct = float((v or {}).get("pct") or 0.0)
            except (TypeError, ValueError):
                continue
            if pct <= 0.0:
                continue
            # de_scan6: aus - Item-NAME aus der SDE (Praefix kuerzen), kein Anzeigetext
            kurz = str((v or {}).get("name") or "").replace("Zainou 'Beancounter' Reprocessing ", "")
            # de_scan6: an
            teile.append(f"{namen.get(int(k), k)} {kurz} +{pct:g} %")
        return ", ".join(teile)

    def _load_reproc_implants(self, fertig=None):
        """Reprocessing-Implantate (Zainou 'Beancounter' Reprocessing RX-80X)
        aller verknuepften Charaktere per ESI erkennen und speichern
        (Nutzer 18.09.2026: "Implantate muessen erkannt werden ... direkt im
        Bauplan unter Reprocessing"). Gleicher Scope wie das Fertigungs-
        Implantat (esi-clones.read_implants.v1). Erkennung ueber die SDE-
        Tabelle reprocess_implant - keine hartkodierte ID. `fertig()` wird
        nach dem Speichern gerufen (Karte + Plan nachziehen)."""
        client_id = self.settings.get("client_id")
        chars = store.list_characters()
        if not client_id or not chars:
            self._flash_tip(t("No characters/client ID linked."))
            return
        bekannt = industry.reprocess_implants()
        if not bekannt:
            self._flash_tip(t("No reprocessing implant data – run „Load recipes“ once."))
            return

        def job():
            out, errors = {}, []
            for ch in chars:
                cid = int(ch["character_id"])
                try:
                    implants = esi.fetch_character_implants(client_id, cid)
                except Exception as fehler:
                    errors.append(f"{ch.get('character_name', cid)}: {fehler}")
                    continue
                best = None
                for tid in implants:
                    eintrag = bekannt.get(int(tid))
                    if eintrag and (best is None
                                    or float(eintrag.get("value") or 0) > best["pct"]):
                        best = {"tid": int(tid), "pct": float(eintrag.get("value") or 0),
                                "name": eintrag.get("name") or ""}
                if best:
                    out[str(cid)] = best
            return out, errors

        def done(res):
            out, errors = res
            self.settings["bau_char_reproc_implant"] = out
            config.save_settings(self.settings)
            msg = t("{n} reprocessing implant(s) detected ✓").format(n=len(out))
            if errors:
                msg += "  ·  " + t("{n} error(s) (missing scope? re-link)").format(
                    n=len(errors))
            self._flash_tip(msg)
            if fertig is not None:
                try:
                    fertig()
                except Exception as _fe:
                    self._log_exception("Reprocessing: Implantate nachziehen", str(_fe))
        self._run(Worker(job), done, label=t("Implants …"), overlay=False)

    def _reprocess_opts(self):
        """opts["reprocess"] fuer den Plan - oder None, wenn beide Schalter
        aus sind. "on" = Weg B (Erz statt Minerale), "unrefined" = Weg A
        (Unrefined-Reaktionen). Enthaelt die Struktur-Basis und einen
        Fingerabdruck der Skills, damit der Plan-Cache bei neuen Skills
        nicht weiterrechnet."""
        weg_b = bool(self.settings.get("bau_reprocess_on"))
        weg_a = bool(self.settings.get("bau_unrefined_on"))
        if not weg_b and not weg_a:
            return None
        s = self._reprocess_struktur()
        basis, info = reprocess.struktur_basis(s, industry.reprocess_struktur_sde())
        skills = self.settings.get("bau_char_skills", {}) or {}
        fp = repr(sorted((str(k), sorted((str(a), int(b or 0))
                                         for a, b in (v or {}).items()))
                         for k, v in skills.items()))
        imps = self._reprocess_implants_map()
        return {"on": weg_b, "unrefined": weg_a, "basis": basis, "info": info,
                "struct": s.get("name"), "sid": s.get("id"),
                "skills_fp": hash(fp), "implants": tuple(sorted(imps.items()))}

    def _bp_basisname(self, tid, name):
        """Item-Name, aus dem der Blaupausen-Name gebildet wird. Weg A: wird
        X ueber seine Unrefined-Formel gebaut, heisst die Blaupause
        "Unrefined X Reaction Formula" - der Name des Unrefined-Produkts
        ist die Basis, nicht X selbst. Sonst der uebergebene Name."""
        try:
            _uw = (getattr(self, "_bd_unrefined", None) or {}).get(int(tid))
        except (TypeError, ValueError):
            _uw = None
        if not _uw:
            return name
        _nm = (getattr(self, "_bd_names_ref", None) or {}).get(int(_uw.get("u") or 0))
        return _nm if _nm else name

    def _unrefined_overlay(self, type_id, recipes_basis, price_fn, opts, kredit_pfn=None,
                           fest=None):
        """Weg A: (Rezepte, Wahl). Ist der Schalter aus, fehlt die Struktur-
        Basis oder gibt es nichts zu tauschen, kommen die Basis-Rezepte
        unveraendert zurueck und die Wahl ist leer. Sonst eine Rezept-KOPIE,
        in der jedes gewaehlte Zwischenmaterial ueber seine Unrefined-Formel
        laeuft - Plan, Baum, Runplaner, Blueprint-Tab und Zeiten folgen dann
        von selbst. Merkt sich Wahl und Ablehnungen fuer die Anzeige.
        `fest` (eingefrorener Plan): die gespeicherte Wahl gilt unveraendert,
        auch wenn Schalter oder Preise inzwischen anders sind."""
        self._bd_unrefined = {}
        self._bd_unrefined_abgelehnt = {}
        if fest is not None:
            wahl = {}
            for _x, _k in (fest or {}).items():
                try:
                    if int(_k["bp"]) > 0 and int(_k["out_je_run"]) > 0:
                        wahl[int(_x)] = dict(_k)
                except (KeyError, TypeError, ValueError):
                    continue
            self._bd_unrefined = wahl
            return reprocess.rezepte_mit_unrefined(recipes_basis, wahl), wahl
        ro = (opts or {}).get("reprocess") or {}
        if not ro.get("unrefined"):
            return recipes_basis, {}
        try:
            karte = industry.reprocess_map()
            kand = reprocess.unrefined_kandidaten(recipes_basis, karte)
            if not kand:
                return recipes_basis, {}
            # SCRAPMETAL-PFAD (gemessen 19.09.2026): 50 % x Scrapmetal
            # Processing - Struktur, Rig, Implantat und Erz-Skill zaehlen
            # hier nicht, deshalb keine Struktur-Basis noetig.
            af = reprocess.scrap_ausbeute_funktion(
                self.settings.get("bau_char_skills", {}) or {},
                industry.reprocess_skill_ids())
            kand = reprocess.unrefined_ausbeute(kand, af)
            ids = set(industry.alle_items_der_kette(type_id, recipes_basis)) | {int(type_id)}
            res = reprocess.unrefined_wahl(kand, ids, price_fn, recipes_basis, opts,
                                           kredit_pfn=kredit_pfn)
        except Exception as _ue:
            self._log_exception("Reprocessing: Unrefined-Wahl", str(_ue))
            return recipes_basis, {}
        self._bd_unrefined = dict(res.get("wahl") or {})
        self._bd_unrefined_abgelehnt = dict(res.get("abgelehnt") or {})
        # DIAGNOSE-DATEI (Nutzer-Befund 19.09.2026: Plan mit Unrefined
        # teurer als ohne): jede Zahl der Entscheidung, nachlesbar.
        try:
            import os as _os
            _pfad = _os.path.join(config.app_data_dir(), "unrefined_diagnose.txt")
            with open(_pfad, "w", encoding="utf-8") as _fh:
                _fh.write(reprocess.unrefined_diagnose_text(
                    res, getattr(self, "_bd_names_ref", None) or {},
                    # de_scan5: aus - Diagnose-Datei, nicht Oberflaeche
                    titel=f"(Plan {type_id}, Fracht in Preisen: "
                          f"{'ja' if kredit_pfn is not price_fn else 'nein'})"))
                # de_scan5: an
        except Exception as _ud:
            self._log_exception("Reprocessing: Unrefined-Diagnose", str(_ud))
        return reprocess.rezepte_mit_unrefined(recipes_basis, self._bd_unrefined), self._bd_unrefined

    def _reprocess_erz_ids(self, price_fn):
        """Kandidaten-Erze (Kategorie 25 mit Reprocessing-Ausgang und Preis)
        - fuer die Namensaufloesung, damit `kandidaten()` sie erkennt."""
        try:
            karte = industry.reprocess_map()
            cats = industry.item_category_map()
        except Exception:
            return set()
        out = set()
        for tid in karte:
            info = cats.get(tid)
            if info and info[0] == 25:
                try:
                    if float(price_fn(tid) or 0.0) > 0.0:
                        out.add(int(tid))
                except (TypeError, ValueError):
                    continue
        return out

    def _reprocess_anwenden(self, plan, price_fn, names, ro, kredit_pfn=None):
        """Wendet Weg B auf einen fertigen Plan an: Erz-Kaeufe statt
        Mineral-Kaeufe, wo guenstiger. Gibt eine KOPIE zurueck; ohne
        Schalter oder ohne Struktur-Basis bleibt der Plan unveraendert (nur
        plan["reprocess"] traegt dann den Grund). total_cost/mat_cost werden
        um die Ersparnis gesenkt - dieselbe Zahl, die die Schritte nennen.
        Danach Weg A (Unrefined-Schritte + Ruecklaeufer-Gutschrift zum
        reinen Hub-Preis `kredit_pfn`), wenn dessen Schalter an ist."""
        if not plan or not ro or not (ro.get("on") or ro.get("unrefined")):
            return plan
        neu = dict(plan)
        basis = ro.get("basis")
        if basis is None:
            neu["reprocess"] = {"schritte": [], "ersparnis": 0.0, "ueberschuss": {},
                                "grund": ((ro.get("info") or {}).get("grund") or "none")
                                if ro.get("on") else None,
                                "struct": ro.get("struct")}
            # Weg A braucht keine Struktur-Basis (Scrapmetal-Pfad).
            return self._unrefined_anwenden(neu, ro, kredit_pfn or price_fn)
        if not ro.get("on"):
            # Nur Weg A: leerer Weg-B-Rahmen, damit die Anzeige einen Block hat.
            neu["reprocess"] = {"schritte": [], "ersparnis": 0.0, "ueberschuss": {},
                                "abgelehnt": {}, "basis": basis, "struct": ro.get("struct"),
                                "info": ro.get("info") or {}}
            return self._unrefined_anwenden(neu, ro, kredit_pfn or price_fn)
        try:
            karte = industry.reprocess_map()
            cats = industry.item_category_map()
            # BLACKLIST GILT AUCH FUER ERZ (Nutzer 19.09.2026: "wir rechnen
            # damit, es zu reprocessen, ABER es kommt weder in die Einkaufs-
            # liste noch in den Runplaner - man bekommt es z. B. von einem
            # Kollegen"). Gruppe "Compressed ore" oder ein Erz-Name im
            # Textfeld: das Erz ist GRATIS - deckt seine Minerale, wird nicht
            # gekauft, Stufe 0 zeigt es nicht.
            _erz_alle = [int(_t) for _t, _i in (cats or {}).items()
                         if _i and _i[0] == 25 and _t in karte]
            try:
                _gratis = self._bau_never_build(_erz_alle, {}, set(), names or {})
            except Exception:
                _gratis = set()
            kand = reprocess.kandidaten(karte, names or {}, cats, price_fn, gratis=_gratis)
            af = reprocess.ausbeute_funktion(
                basis, self.settings.get("bau_char_skills", {}) or {},
                self._reprocess_implants_map(),
                industry.reprocess_skill_ids(), industry.reprocess_erz_skill())
            res = reprocess.plane_erz_einkauf(plan.get("buy") or {}, price_fn, kand, af,
                                              gratis=_gratis)
            # EIN CHARAKTER FUER ALLES (Nutzer 19.09.2026): stehen mehrere
            # Charaktere in den Schritten (je Erz der beste), noch einmal
            # mit dem einen planen, der ueber alle Erze am meisten holt.
            _chars_rp = {_s.get("char") for _s in (res.get("schritte") or [])}
            if len(_chars_rp) > 1:
                _skills_rp = self.settings.get("bau_char_skills", {}) or {}
                _einer = reprocess.ein_charakter(
                    res.get("schritte"), price_fn, _skills_rp, self._reprocess_implants_map(),
                    industry.reprocess_skill_ids(), industry.reprocess_erz_skill())
                if _einer is not None:
                    af = reprocess.ausbeute_funktion(
                        basis, _skills_rp, self._reprocess_implants_map(),
                        industry.reprocess_skill_ids(), industry.reprocess_erz_skill(),
                        fest=_einer)
                    res = reprocess.plane_erz_einkauf(plan.get("buy") or {}, price_fn,
                                                      kand, af, gratis=_gratis)
        except Exception as _re:
            self._log_exception("Reprocessing: Erz statt Mineral", str(_re))
            neu["reprocess"] = {"schritte": [], "ersparnis": 0.0, "ueberschuss": {},
                                "grund": "fehler", "struct": ro.get("struct")}
            return neu
        res["basis"] = basis
        res["struct"] = ro.get("struct")
        res["info"] = ro.get("info") or {}
        res["erz_on"] = True
        neu["reprocess"] = res
        if res["schritte"]:
            neu["buy"] = res["buy"]
            ersp = float(res.get("ersparnis") or 0.0)
            for key in ("total_cost", "mat_cost"):
                if isinstance(plan.get(key), (int, float)):
                    neu[key] = float(plan[key]) - ersp
            surplus = dict(plan.get("surplus") or {})
            for mat, q in (res.get("ueberschuss") or {}).items():
                surplus[int(mat)] = surplus.get(int(mat), 0) + int(q)
            neu["surplus"] = surplus
        return self._unrefined_anwenden(neu, ro, kredit_pfn or price_fn)

    def _unrefined_anwenden(self, plan, ro, kredit_pfn):
        """Weg A auf den Plan: Schritte fuer jedes ueber die Unrefined-Formel
        gebaute X (aus self._bd_unrefined, gesetzt von _unrefined_overlay)."""
        if not ro.get("unrefined"):
            return plan
        wahl = getattr(self, "_bd_unrefined", None) or {}
        try:
            neu = reprocess.unrefined_anwenden(plan, wahl, kredit_pfn)
        except Exception as _ua:
            self._log_exception("Reprocessing: Unrefined anwenden", str(_ua))
            return plan
        if isinstance(neu.get("reprocess"), dict):
            neu["reprocess"]["unrefined_abgelehnt"] = dict(
                getattr(self, "_bd_unrefined_abgelehnt", None) or {})
            neu["reprocess"]["unrefined_on"] = True
        return neu

    def _jobfrage_knopf_auffrischen(self):
        """Die Zeile im Runplaner: "n Jobs nicht zugeordnet - zuordnen".

        Gibt es nichts zu fragen, ist der Knopf WEG - nicht ausgegraut. Ein
        grauer Knopf sagt "hier koennte etwas sein"; hier ist aber wirklich
        nichts, und das ist der Normalfall.
        """
        from ..sprache import t as _txt   # `t` kann hier lokal belegt sein
        _btn = getattr(self, "_bd_jobfrage_btn", None)
        if _btn is None:
            return
        _offen = getattr(self, "_bd_job_offen", None) or []
        if not _offen:
            _btn.hide()
            return
        _btn.setText(_txt("{n} job(s) not assigned – assign").format(
            n=len(_offen)))
        _btn.setToolTip(_txt(
            "ESI does not say which build plan a job belongs to. For these "
            "jobs more than one saved plan builds the same item, so the tool "
            "does not guess: they currently count for no plan at all, which "
            "makes your shopping list too big. Answer once – the answer "
            "is stored with the job and you will not be asked again."))
        _btn.show()

    def _job_frage_dialog(self):
        """Einmal fragen, wem diese Jobs gehoeren - und die Antwort merken."""
        from ..sprache import t as _txt   # `t` ist hier lokal belegt
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                       QLabel, QPushButton, QComboBox,
                                       QTableWidget, QTableWidgetItem,
                                       QHeaderView, QAbstractItemView)
        import time as _t_jf
        _offen = list(getattr(self, "_bd_job_offen", None) or [])
        if not _offen:
            return 0
        d = QDialog(self)
        d.setWindowTitle(_txt("Which build plan do these jobs belong to?"))
        d.setMinimumWidth(720)
        v = QVBoxLayout(d)
        _erkl = QLabel(_txt(
            "More than one of your saved build plans builds these items, so "
            "the tool cannot tell whose job it was. Until you answer, they "
            "count for no plan – your shopping list stays bigger than "
            "it needs to be."))
        _erkl.setWordWrap(True)
        _erkl.setObjectName("Muted")
        v.addWidget(_erkl)
        tbl = QTableWidget(len(_offen), 4)
        tbl.setHorizontalHeaderLabels([_txt("Item"), _txt("Runs"),
                                       _txt("Delivered"),
                                       _txt("Belongs to")])
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        tbl.setSelectionMode(QAbstractItemView.NoSelection)
        _boxen = {}
        for _r, _f in enumerate(_offen):
            tbl.setItem(_r, 0, QTableWidgetItem(str(_f.get("name")
                                                    or _f["type_id"])))
            tbl.setItem(_r, 1, QTableWidgetItem(
                f"{int(_f['runs']):,}".replace(",", "'")))
            try:
                _wann = _t_jf.strftime("%Y-%m-%d %H:%M",
                                       _t_jf.localtime(float(_f["fertig_ts"])))
            except (TypeError, ValueError, OSError):
                _wann = "?"
            tbl.setItem(_r, 2, QTableWidgetItem(_wann))
            _cb = QComboBox()
            for _pid, _nm in (_f.get("kandidaten") or []):
                _cb.addItem(str(_nm), _pid)
            # "Keiner" ist eine vollwertige Antwort und wird genauso
            # gemerkt - sonst kaeme dieselbe Frage bei jedem Aufbau wieder.
            _cb.addItem(_txt("None of these"), None)
            tbl.setCellWidget(_r, 3, _cb)
            _boxen[int(_f["job_id"])] = _cb
        tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for _c in (1, 2, 3):
            tbl.resizeColumnToContents(_c)
        tbl.setColumnWidth(3, max(tbl.columnWidth(3), 220))
        v.addWidget(tbl, 1)
        _zeile = QHBoxLayout()
        _zeile.addStretch()
        _ab = QPushButton(_txt("Cancel"))
        _ab.clicked.connect(lambda: d.reject())
        _zeile.addWidget(_ab)
        _ok = QPushButton(_txt("Save assignment"))
        _ok.setDefault(True)
        _ok.clicked.connect(lambda: d.accept())
        _zeile.addWidget(_ok)
        v.addLayout(_zeile)
        self._bd_jobfrage_dialog = d       # fuer die Pruefung greifbar
        if d.exec() != QDialog.Accepted:
            return 0
        _n = self._job_frage_antworten(
            {_jid: _cb.currentData() for _jid, _cb in _boxen.items()})
        self._flash_tip(_txt("{n} job(s) assigned.").format(n=_n))
        # Der Runplaner rechnet mit der neuen Zuordnung - also neu aufbauen.
        try:
            self._bd_full_rebuild()
        except Exception as _re_jf:
            self._log_exception("Job-Frage: Neuaufbau", str(_re_jf))
        return _n

    def _show_build_detail(self, type_id, name, res):
        from ..sprache import t as _txt   # `t` ist hier lokal belegt
        from PySide6.QtWidgets import (QDialog, QTreeWidget, QTreeWidgetItem,
                                       QSpinBox, QHeaderView, QMenu)
        # NUR EIN BAUPLAN GLEICHZEITIG (Sitzung 13, Nutzer-Meldung:
        # "wenn ich 2 oder mehrere Bauplaene gleichzeitig offen habe, dann
        # wird irgendwas gemischt und vermischt").
        #
        # REPRODUZIERT, nicht vermutet: zwei Fenster nacheinander geoeffnet,
        # danach zeigte `self._bd_mat_rows` die Materialzeilen des ZWEITEN
        # Plans - und "Einkaufsliste erstellen" im ERSTEN Fenster liest genau
        # dieses Feld. Man klickt im Schiff-Bauplan und bekommt die Zutaten
        # des Komponenten-Plans. Auch `_bd_dialog` zeigte nur noch auf das
        # zweite Fenster, das erste war fuer alles unerreichbar, was darueber
        # laeuft.
        #
        # URSACHE: der Dialog legt seinen GESAMTEN Zustand auf der MainWindow
        # ab - 179 `self._bd_...` in main_window.py, 182 in dieser Datei, 53
        # in mw_bauplan_tabs.py. Zwei Fenster teilen sich also jedes Feld.
        #
        # WARUM SPERREN STATT TRENNEN: 414 Felder auf ein Dialog-Objekt
        # umzuhaengen ist ein Umbau quer durch drei Dateien. Die Sperre sind
        # ein paar Zeilen, wirkt sofort und macht nichts schlimmer. Der
        # saubere Umbau bleibt jederzeit moeglich (OFFENE_PUNKTE.md).
        #
        # KEIN STILLES NICHTS-PASSIERT (Regel 6): der bereits offene Plan
        # wird nach vorn geholt und der Grund benannt.
        _offen = self._offener_bauplan()
        if _offen is not None:
            from PySide6.QtWidgets import QMessageBox as _QMB
            _QMB.information(
                _offen, _txt("Only one build plan at a time"),
                _txt("Two build plans cannot be open at the same time \u2013 "
                     "they would share their data, and the shopping list of "
                     "one could end up with the materials of the other.\n\n"
                     "Close the open plan first, then open the next one."))
            try:
                _offen.showNormal(); _offen.raise_(); _offen.activateWindow()
            except Exception:
                pass                    # Nach-vorn-Holen ist Komfort
            return
        tree = res["tree"]; names = res["names"]; sell = res["sell"]
        # Fuer Helfer ausserhalb dieses Rahmens (Blaupausen-Name bei Weg A):
        # dasselbe dict, das rebuild() nachfuellt - keine Kopie.
        self._bd_names_ref = names
        # DER BAUM MUSS MITWACHSEN (Sitzung 20). `tree` kam bisher EINMAL beim
        # Oeffnen aus res["tree"] und wurde nie wieder gerechnet - `rebuild()`
        # erneuerte nur den Plan. Deshalb als veraenderliche Referenz, genau
        # wie `plan_ref` weiter unten; rebuild() legt dort den frischen Baum ab.
        tree_ref = {"tree": tree}
        sell_is_contract = res.get("sell_is_contract", False)
        # IST DAS ENDPRODUKT EINE REAKTION? Dann sind mehrere Bedien-Elemente
        # rechnerisch wirkungslos und werden unten ausgeblendet: Reaktionen
        # sind in EVE nicht erforschbar (ME/TE fest 0) und werden nicht
        # erfunden (keine Invention, keine Decryptoren). Sichtbar lassen hiesse
        # dem Nutzer Stellschrauben zeigen, die nichts bewegen.
        _bd_rec = getattr(self, "_bd_recipes", None)
        _is_reaction_product = bool(
            _bd_rec and type_id in (getattr(_bd_rec, "reaction_products", None) or ()))
        dlg = MinimizableDialog(None); dlg.setWindowTitle(_txt("Build plan \u2013 {name}").format(name=name))
        # Der Bauplan-Dialog ist bewusst PARENTLOS (eigenes Top-Level-Fenster,
        # damit man ihn minimieren kann). Folge: Werkzeug-Dialoge, die an der
        # MainWindow haengen, landen in DEREN Z-Ordnung - also HINTER dem
        # Bauplan-Fenster, und beim Aktivieren rutscht der Bauplan nach hinten
        # bzw. in die Taskleiste (Nutzer-Meldung). Deshalb merken wir uns das
        # offene Fenster: _tool_parent() haengt Werkzeuge daran auf, damit sie
        # OBENDRAUF erscheinen.

        self._bd_dialog = dlg
        dlg.finished.connect(lambda *_a: setattr(self, "_bd_dialog", None))
        # FREIE SLOTS AUTOMATISCH NACHZIEHEN (Nutzer, Sitzung 9). Die freien
        # Slots sind ein SCHNAPPSCHUSS (max minus damals laufende Jobs) und
        # veralten still: laeuft ingame ein Job aus, sieht das Tool den
        # freien Slot erst nach erneutem "Skills laden" - genau der
        # Handgriff, den der Nutzer vor jedem Bauplan machen musste.
        # Jetzt holt der Dialog sie beim Oeffnen selbst nach, aber NUR wenn
        # der Stand aelter als 10 Minuten ist (sonst laeuft bei jedem
        # Oeffnen ein ESI-Abruf) und nur, wenn ueberhaupt schon einmal
        # Skills geladen wurden (sonst fehlen die Charakter-Rollen und der
        # Abruf ginge ins Leere). Laeuft im Hintergrund - der Dialog
        # oeffnet sofort, die Slots ziehen nach.
        try:
            _fts9 = float(self.settings.get("bau_char_free_ts") or 0)
        except Exception:
            _fts9 = 0.0
        import time as _t9auto
        if (self.settings.get("bau_char_slots")
                and (_t9auto.time() - _fts9) > 600):
            QTimer.singleShot(0, lambda: self._load_char_slots(silent=True))
        dlg.setMinimumSize(820, 420)
        dlg.resize(1400, 820)
        v = QVBoxLayout(dlg); v.setContentsMargins(18, 14, 18, 14); v.setSpacing(9)

        endp_card = QFrame(); endp_card.setObjectName("Card")
        endp_card.setStyleSheet(
            f"QFrame#Card {{ border: 1px solid rgba(242,162,60,0.4); }}")
        endp_v = QVBoxLayout(endp_card)
        endp_v.setContentsMargins(14, 10, 14, 10); endp_v.setSpacing(6)
        # Nutzer-Vorgabe: die Zeile "ENDPRODUKT - DAS ZU BAUENDE ITEM" ist
        # weg. Das Item steht direkt darunter gross mit Bild - dass es das
        # Endprodukt ist, muss man niemandem zweimal sagen. Spart eine ganze
        # Zeile Hoehe, die der Materialliste zugutekommt.

        ctrl = QHBoxLayout()
        _qty_lbl = QLabel(_txt("Quantity:"))
        ctrl.addWidget(_qty_lbl)
        # OBERGRENZE (Nutzer, Sitzung 20): 1'000'000 war bei Reaktionen nach
        # 100 Runs zu Ende - Fernite Carbide wirft 10'000 je Run ab, da ist
        # eine Million nichts. Jetzt 100 Mio; das Feld wird dafuer breiter,
        # sonst schneidet es die Zahl ab.
        qty_spin = QSpinBox(); qty_spin.setRange(1, 100000000)
        # WAEHREND DES TIPPENS STUMM (Nutzer, Sitzung 20: "ich druecke 2, dann
        # laedt es, ich druecke 0, dann laedt es nochmal - das ist nicht gut").
        # Der Zeitschalter unten allein reicht nicht: Qt meldet mit
        # eingeschaltetem keyboardTracking JEDE Ziffer als Wertaenderung, und
        # schon das Einsammeln kostet Arbeit. Ausgeschaltet meldet das Feld den
        # Wert erst bei ENTER, beim Verlassen oder ueber die Pfeiltasten - also
        # genau dann, wenn der Nutzer fertig ist.
        qty_spin.setKeyboardTracking(False)
        qty_spin.setGroupSeparatorShown(True)
        qty_spin.setValue(int(getattr(self, "_bd_qty", 1) or 1)); qty_spin.setMaximumWidth(140)
        ctrl.addWidget(qty_spin)
        # EIN RUN IST UNTEILBAR (Nutzer-Hinweis). Reaktionen liefern 200 Stk
        # pro Run, T2-Munition 100 - "Menge 1" gibt es dort im Spiel nicht.
        # Trotzdem bleibt der Wert hier in STUECK, nicht in Runs: `_bd_qty`
        # haengt an 13 Stellen dran, darunter das Speicherformat gespeicherter
        # Bauplaene ("qty"). Eine Bedeutungsaenderung wuerde die still
        # umdeuten. Stattdessen kann die Eingabe gar nicht mehr mitten in
        # einem Run landen:
        #   Minimum + Schrittweite = Ausgabe pro Run  -> ein Klick auf Pfeil
        #                                                hoch ist genau 1 Run
        #   getippte Werte werden aufgerundet
        #   daneben steht, wie viele Runs das sind
        # Wirkung ist dieselbe wie eine Runs-Eingabe, nur ohne Umbau.
        _bp_end = (_bd_rec.product_to_bp.get(type_id) if _bd_rec else None)
        _out_per_run = int((_bp_end[2] if _bp_end else 1) or 1)
        _runs_lbl = QLabel("")
        _runs_lbl.setObjectName("Muted")
        _runs_lbl.setProperty("bd_role", "runs_hint")
        # RUNS DIREKT EINGEBEN (Discord, Commander Hibb, 16.09.2026: "eine
        # Umschaltfunktion bei den Durchlaeufen zu Menge"). NUR bei Produkten,
        # die pro Run mehr als 1 Stueck liefern (Fuel Blocks 40, Munition
        # 5000, Reaktionen 200 - 368 von 4849 Fertigungsprodukten laut SDE);
        # beim Einzelstueck waere der Schalter sinnlos und nur Laerm.
        # DIE WAHRHEIT BLEIBT `qty_spin` IN STUECK - das Runs-Feld ist eine
        # zweite Ansicht derselben Zahl, keine zweite Quelle. Gespeicherte
        # Plaene, Reservierung, Runplaner: alles liest weiter Stueck.
        runs_spin = None
        _qty_mode_btn = None
        if _out_per_run > 1:
            qty_spin.setMinimum(_out_per_run)
            qty_spin.setSingleStep(_out_per_run)
            qty_spin.setToolTip(_txt(
                "One run yields {n} units \u2013 less is not possible. Arrow up/down "
                "= one whole run more/less; typed values in between are rounded up."
            ).format(n=_out_per_run))
            runs_spin = QSpinBox()
            runs_spin.setRange(1, max(1, 100000000 // _out_per_run))
            runs_spin.setKeyboardTracking(False)
            runs_spin.setGroupSeparatorShown(True)
            runs_spin.setMaximumWidth(140)
            runs_spin.setProperty("bd_role", "runs_spin")
            runs_spin.setToolTip(_txt(
                "Number of runs. One run yields {n} units - the plan keeps "
                "calculating in units.").format(n=_out_per_run))
            ctrl.addWidget(runs_spin)
            _qty_mode_btn = QPushButton(_txt("Runs"))
            _qty_mode_btn.setIcon(icons.icon("refresh"))
            _qty_mode_btn.setCheckable(True)
            _qty_mode_btn.setProperty("bd_role", "qty_mode")
            _qty_mode_btn.setToolTip(_txt(
                "Switch the field between units and runs. Only offered for "
                "products that yield more than one unit per run."))
            ctrl.addWidget(_qty_mode_btn)
            _qty_mode = {"runs": bool(self.settings.get("bau_qty_in_runs"))}
            _sync = {"on": False}

            def _snap_qty_to_runs():
                _v = qty_spin.value()
                _snapped = -(-_v // _out_per_run) * _out_per_run
                if _snapped != _v:
                    qty_spin.setValue(_snapped)   # loest rebuild() ueber
                                                  # valueChanged mit aus

            def _show_runs(_=0):
                _r = -(-qty_spin.value() // _out_per_run)
                if _qty_mode["runs"]:
                    _runs_lbl.setText(_txt("= {q} units ({n} per run)").format(
                        q=f"{_r * _out_per_run:,}".replace(",", "'"), n=_out_per_run))
                else:
                    _runs_lbl.setText(
                        _txt("= {r} run(s) with {n} units").format(r=_r, n=_out_per_run))

            def _runs_to_qty(_=0):
                # Runs-Feld -> Stueckfeld. Der Riegel `_sync` verhindert das
                # Ping-Pong der beiden valueChanged-Signale.
                if _sync["on"]:
                    return
                _sync["on"] = True
                try:
                    qty_spin.setValue(runs_spin.value() * _out_per_run)
                finally:
                    _sync["on"] = False

            def _qty_to_runs(_=0):
                if _sync["on"]:
                    return
                _sync["on"] = True
                try:
                    runs_spin.setValue(-(-qty_spin.value() // _out_per_run))
                finally:
                    _sync["on"] = False

            def _apply_qty_mode(runs_mode, speichern=True):
                _qty_mode["runs"] = bool(runs_mode)
                qty_spin.setVisible(not _qty_mode["runs"])
                runs_spin.setVisible(_qty_mode["runs"])
                _qty_lbl.setText(_txt("Runs:") if _qty_mode["runs"]
                                 else _txt("Quantity:"))
                if _qty_mode_btn.isChecked() != _qty_mode["runs"]:
                    _qty_mode_btn.setChecked(_qty_mode["runs"])
                _show_runs()
                if speichern:
                    self.settings["bau_qty_in_runs"] = _qty_mode["runs"]
                    config.save_settings(self.settings)

            qty_spin.editingFinished.connect(_snap_qty_to_runs)
            qty_spin.valueChanged.connect(_show_runs)
            qty_spin.valueChanged.connect(_qty_to_runs)
            runs_spin.valueChanged.connect(_runs_to_qty)
            _qty_mode_btn.toggled.connect(lambda _on: _apply_qty_mode(_on))
            _snap_qty_to_runs()
            _qty_to_runs()
            _apply_qty_mode(_qty_mode["runs"], speichern=False)
            ctrl.addWidget(_runs_lbl)
        ctrl.addSpacing(14)
        # Endprodukt-ME/TE + "Eigene BPC" sitzen jetzt NICHT mehr hier oben,
        # sondern direkt im Invention-Tab neben der T2-Blaupause, für die sie
        # gelten (macht dort optisch mehr Sinn - man sieht Erfolgschance/ME/TE
        # und die eigene BPC-Option an derselben Stelle). Die Widgets selbst
        # bleiben dieselben Objekte wie vorher (nur wo sie eingefügt werden hat
        # sich geändert) - die ganze bestehende Sync-Logik unten (Invention vs.
        # Eigene BPC) funktioniert dadurch unverändert weiter.
        me_spin = QSpinBox(); me_spin.setRange(0, 10)
        me_spin.setKeyboardTracking(False)   # s. qty_spin
        me_spin.setSuffix(" %")
        me_spin.setMinimumWidth(90)
        _cm = getattr(self, "_bd_me", None)
        me_spin.setValue(int(_cm if _cm is not None else self.settings.get("bau_me", 10)))
        me_spin.setToolTip(_txt("Material efficiency of the FINAL product only (usually T2 "
                                "\u2013 often 0 % as long as the BPC from invention has not "
                                "been researched separately)."))
        te_spin = QSpinBox(); te_spin.setRange(0, 20)
        te_spin.setKeyboardTracking(False)   # s. qty_spin
        te_spin.setSuffix(" %")
        te_spin.setMinimumWidth(90)
        te_spin.setValue(int(getattr(self, "_bd_te", 0) or 0))
        te_spin.setToolTip(_txt(
            "Time efficiency of the FINAL product only – for the build "
              "time."))
        # WO GIBT MAN ME/TE EIN? (Nutzer-Frage) Haengt davon ab, WOHER sie
        # kommen:
        #   T2/T3 (erfunden)  -> aus der Invention (2 % Basis + Decryptor).
        #                        Die Felder gehoeren neben die Invention-Karte,
        #                        wo sie nur ueber "Eigene BPC" ueberschrieben
        #                        werden. Unveraendert.
        #   T1 (BPO/BPC)      -> gibt es nur als ERFORSCHTEN Wert. Ohne
        #                        Invention-Tab gaebe es kein Eingabefeld mehr -
        #                        deshalb wandern die Felder hier nach oben,
        #                        direkt neben die Menge.
        #   Reaktion          -> gar nicht. Reaktionsformeln sind in EVE nicht
        #                        erforschbar, ME/TE sind immer 0. Ein Feld
        #                        dafuer waere eine Stellschraube ohne Wirkung.
        _bp0 = (_bd_rec.product_to_bp.get(type_id) if _bd_rec else None)
        _is_invented = bool(
            _bp0 and _bd_rec
            and _bp0[0] in (getattr(_bd_rec, "invention_for_bpc", None) or {}))
        # BUENDEL (Befund 26.09.2026, Nutzer: "mir fehlt ein Invention-Tab
        # im Multibauplan"): `_bp0` ist hier die Pseudo-Blaupause des
        # Buendels (-2), die nie in invention_for_bpc steht - der Tab flog
        # damit fuer JEDES Buendel raus, auch mit lauter T2-Enden. Erfunden
        # wird, sobald EIN Ende erfindbar ist; der Tab zeigt dann je Ende
        # seinen Decryptor (mw_bauplan_tabs).
        if type_id == industry.BUENDEL_ID and _bd_rec:
            _is_invented = bool(self._multi_enden_erfindbar(
                _bd_rec, self._bd_enden(type_id, _bd_rec)))
        # MULTI-BAUPLAN (Schritt 4): ein Buendel hat MEHRERE Endprodukte, jedes
        # mit eigener ME/TE. EIN Feld oben koennte nur eines davon meinen - es
        # waere eine Stellschraube, die das Falsche verstellt. Die Werte stehen
        # stattdessen je Zeile in der Karte "Endprodukte" (_multi_enden_karte).
        _ist_buendel = (type_id == industry.BUENDEL_ID)
        _me_te_in_header = (bool(_bp0) and not _is_invented
                            and not _is_reaction_product and not _ist_buendel)
        # ME/TE DES ENDPRODUKTS AUS DER EIGENEN BLAUPAUSE (Nutzer-Fund,
        # Sitzung 20, Ametat I): fuer ZWISCHENSTUFEN holt das Werkzeug ME/TE
        # laengst per ESI aus der schlechtesten eigenen Kopie - beim
        # ENDPRODUKT nahm es das Eingabefeld, und das stand auf 0. Im Spiel
        # hatte seine BPC 10/20; die geplante Bauzeit war dadurch falsch
        # (47 m gegen 1:05:17 im Industriefenster).
        # NUR VORBELEGEN, NICHT ERZWINGEN: die Felder bleiben bedienbar, und
        # sobald der Nutzer sie einmal selbst anfasst, wird nichts mehr
        # ueberschrieben (`_bd_me_manuell`). Kennt das Werkzeug keine eigene
        # Kopie, bleibt es bei dem, was dasteht - Nichtwissen darf keine
        # guenstige Zahl erzeugen.
        if _me_te_in_header and not getattr(self, "_bd_me_manuell", False):
            try:
                _e_me, _e_te = self._bd_own_bpc_me_te(type_id)
            except Exception:
                _e_me = _e_te = 0
            if _e_me or _e_te:
                self._bd_me, self._bd_te = int(_e_me), int(_e_te)
                me_spin.setValue(int(_e_me))
                te_spin.setValue(int(_e_te))
                me_spin.setToolTip(me_spin.toolTip() + "\n\n" + _txt(
                    "Prefilled from your own blueprint (the worst-researched "
                    "copy). Change it and the tool leaves it alone."))
                te_spin.setToolTip(te_spin.toolTip() + "\n\n" + _txt(
                    "Prefilled from your own blueprint (the worst-researched "
                    "copy). Change it and the tool leaves it alone."))
        if _me_te_in_header:
            _me_cap = QLabel(_txt("ME"))
            _te_cap = QLabel(_txt("TE"))
            # Marke auch auf die SPINNER, nicht nur auf die Beschriftungen:
            # der Test prueft sonst nur, dass "ME"/"TE" dastehen - und genau das
            # war beim Rokh der Fall, waehrend die Eingabefelder fehlten.
            me_spin.setProperty("bd_role", "endproduct_me_te")
            te_spin.setProperty("bd_role", "endproduct_me_te")
            for _w in (_me_cap, _te_cap):
                _w.setObjectName("Muted")
                # Eindeutige Marke: es gibt weiter unten noch die Kategorie-
                # Chips mit ebenfalls "ME"/"TE" beschrifteten Labels. Ohne
                # das trifft jede Pruefung "steht ME oben?" auch die.
                _w.setProperty("bd_role", "endproduct_me_te")
            me_spin.setToolTip(_txt("Material efficiency of this final product's blueprint "
                                    "(T1: your research level, 0\u201310 %)."))
            te_spin.setToolTip(_txt("Time efficiency of this final product's blueprint "
                                    "(T1: your research level, 0\u201320 %)."))
            ctrl.addWidget(_me_cap); ctrl.addWidget(me_spin)
            ctrl.addSpacing(6)
            ctrl.addWidget(_te_cap); ctrl.addWidget(te_spin)
            ctrl.addSpacing(14)
        # "Eigene BPC statt Invention": falls man die BPC schon besitzt (mit
        # bekannter ME/TE aus eigener Forschung) oder plant, sie zu kaufen statt
        # zu erfinden, kann man hier die echten Werte selbst eintragen und die
        # Invention-Rechnung für DIESES Item komplett ignorieren (kein
        # Invention-Kosten-Posten mehr).
        own_bpc_cb = QCheckBox(_txt("Own BPC instead of invention"))
        own_bpc_cb.setIcon(icons.icon("clipboard"))
        own_bpc_cb.setToolTip(_txt(
            "On: ME/TE are freely editable here and the invention "
              "maths above in this panel is ignored for this end "
              "product (no invention cost) – e.g. when you already own "
              "the BPC or want to buy it instead of inventing it."))
        own_bpc_cb.setChecked(bool(getattr(self, "_bd_own_bpc", False)))
        # NUR VERSTECKEN, NIE ZEIGEN (b8, 20.09.2026): `setVisible(True)` auf
        # einem Widget, das noch in KEINEM Layout haengt, macht daraus ein
        # eigenes Fenster - die b-Suite fand drei streunende QCheckBoxen.
        # Sichtbar wird es ohnehin, sobald `ctrl` es aufnimmt.
        if _ist_buendel:
            own_bpc_cb.hide()                    # s. _me_te_in_header
        own_bpc_runs_lbl = QLabel(_txt("Runs/BPC:"))
        own_bpc_runs_spin = QSpinBox(); own_bpc_runs_spin.setRange(1, 9999)
        own_bpc_runs_spin.setMinimumWidth(70)
        own_bpc_runs_spin.setValue(int(getattr(self, "_bd_own_bpc_runs", 0) or
                                       max(1, int(getattr(self, "_bd_qty", 1) or 1))))
        own_bpc_runs_spin.setToolTip(_txt(
            "How many runs does ONE of your own BPCs have (not a BPO "
              "– a blueprint copy runs out eventually)? From that the "
              "tool works out how many BPC copies you need for the "
              "quantity set above – otherwise the run planner cannot "
              "split the end product across build slots and characters."))

        def _on_own_bpc_runs_change(v):
            self._bd_own_bpc_runs = int(v)
            cb = getattr(self, "_bd_full_rebuild", None)
            if cb:
                # Aufgeschoben, gleicher Grund wie bei ME/TE: der Rebuild
                # loescht die Karte, in der dieser Spinner sitzt.
                QTimer.singleShot(0, cb)
        own_bpc_runs_spin.valueChanged.connect(_on_own_bpc_runs_change)
        if _ist_buendel or not own_bpc_cb.isChecked():
            own_bpc_runs_lbl.hide()
            own_bpc_runs_spin.hide()

        def _on_own_bpc_toggle(v):
            self._bd_own_bpc = bool(v)
            if v:
                # AUF 0/0 ZURUECK (Nutzer, Sitzung 19, woertlich: "falls ein
                # nutzer es uebersieht oder ignoriert, muss der ME/TE 0/0
                # zaehlen" und "0/0 soll auch als startwert da stehen
                # ersichtlich").
                #
                # WARUM: solange erfunden wird, stehen in den Feldern die
                # Werte der ERFUNDENEN Blaupause (2 % Basis / 4 % Basis, ggf.
                # plus Decryptor) - die schreibt der Invention-Zweig weiter
                # unten hinein und sperrt die Felder dabei. Haengt der Nutzer
                # "Eigene BPC" an, gelten diese Zahlen nicht mehr: seine
                # eigene Kopie hat die ME/TE, die SIE hat. Bleiben die 2/4
                # stehen, rechnet das Werkzeug mit fremden Werten und kauft
                # ZU WENIG - die einzige Richtung, die dem Nutzer wehtut.
                #
                # Beides setzen: die Bauzeit-Planung liest `_bd_te`/`_bd_me`
                # direkt, nicht nur das Eingabefeld (siehe Invention-Zweig).
                # Die Felder werden beim Rebuild aus genau diesen Werten neu
                # aufgebaut - deshalb steht die 0 danach auch sichtbar da.
                # ECHTE WERTE, WENN WIR SIE KENNEN (Nutzer, Sitzung 19:
                # "dann nehmen wir immer die am schlechtesten gefundene ME
                # wert per ESI"). Kennt das Werkzeug keine eigene Kopie,
                # bleibt es bei 0/0 - Nichtwissen darf keine guenstige Zahl
                # erzeugen.
                self._bd_me, self._bd_te = self._bd_own_bpc_me_te(type_id)
            own_bpc_runs_lbl.setVisible(bool(v))
            own_bpc_runs_spin.setVisible(bool(v))
            try:
                bp0 = self._bd_recipes.product_to_bp.get(type_id)
                if bp0:
                    ov = self._bd_opts.setdefault("inv_manual_override", {})
                    if v:
                        ov[bp0[0]] = True
                    else:
                        ov.pop(bp0[0], None)
            except Exception:
                pass
            cb = getattr(self, "_bd_full_rebuild", None)
            if cb:
                # Aufgeschoben: `toggled` feuert waehrend Qt die Checkbox noch
                # selbst bearbeitet - und der Rebuild raeumt genau die Karte
                # ab, in der diese Checkbox steckt.
                QTimer.singleShot(0, cb)
        own_bpc_cb.toggled.connect(_on_own_bpc_toggle)
        recalc = QPushButton(_txt("Recalculate"))
        recalc.setIcon(icons.icon("refresh"))
        recalc.setObjectName("Primary")
        recalc.setMinimumHeight(34)
        recalc.setStyleSheet("font-size:13px; font-weight:800; padding:6px 16px;")
        recalc.setToolTip(_txt(
            "Applies all ME/TE fields (recalculates the chain). It "
              "also fetches the real material purchase prices from the "
              "order book of the chosen hub (one live request per "
              "material, may take a moment) – replacing the flat price "
              "in build cost per unit."))
        ctrl.addWidget(recalc)
        # --- "🔒 Alle Materialien gekauft": friert die KOSTEN-Seite des Plans
        # auf dem Stand von JETZT ein (Materialpreise, Jobkosten-Basis,
        # Lagerbestand). Danach ändern sich Stückzahlen/Preise beim Wieder-
        # öffnen nicht mehr - nur der Verkaufspreis des Endprodukts bleibt
        # live, damit man Wochen später den echten Gewinn gegen die DAMALIGEN
        # Einkaufskosten rechnen kann. Wird pro gespeichertem Plan mitgesichert.
        import time as _time_mod
        frozen_btn = self._bd_frozen_btn = QPushButton()
        frozen_btn.setIcon(icons.icon("lock"))
        frozen_btn.setCheckable(True)
        frozen_btn.setMinimumHeight(34)

        def _frozen_btn_style(on):
            # NUR IM EIN-ZUSTAND farbig (Nutzer: "alle Buttons leuchten in zu
            # vielen Farben, das lenkt ab"). Ausgeschaltet ist das ein Knopf
            # wie jeder andere - dass er AN ist, ist dagegen eine echte
            # Zustandsinfo und darf leuchten. Hervorgehoben bleibt in der
            # Kopfzeile sonst nur "Neu berechnen" als primaere Aktion.
            if on:
                frozen_btn.setStyleSheet(
                    f"QPushButton{{background:{theme.AMBER}; color:{theme.BG}; "
                    f"border:2px solid {theme.AMBER}; border-radius:6px; "
                    f"padding:6px 16px; font-size:13px; font-weight:800;}}")
            else:
                frozen_btn.setStyleSheet(
                    f"QPushButton{{background:transparent; color:{theme.MUTED}; "
                    f"border:1px solid {theme.BORDER}; border-radius:6px; "
                    f"padding:6px 16px; font-size:13px;}}"
                    f"QPushButton:hover{{border-color:{theme.AMBER}; "
                    f"color:{theme.AMBER};}}")

        # Sichtbarkeits-Sync für den Rebase-Knopf über einen HOLDER, nicht
        # über die Closure-Variable direkt: _frozen_btn_text() läuft schon,
        # bevor der Knopf weiter unten gebaut ist (NameError, Nutzer-
        # Traceback). Der Holder existiert immer, die Funktion wird erst
        # eingehängt, wenn der Knopf da ist - reihenfolge-unabhängig.
        _refz_sync = {"fn": None}

        def _frozen_btn_text():
            fz = getattr(self, "_bd_frozen", None)
            if _refz_sync["fn"]:
                _refz_sync["fn"]()
            if fz and fz.get("ts"):
                d = _time_mod.strftime("%d.%m.%Y", _time_mod.localtime(fz["ts"]))
                if fz.get("plan_snapshot"):
                    # Nutzer-Spez Punkt 4: der Knopf sagt, was er tut.
                    frozen_btn.setText(_txt("Plan frozen \u2013 purchase ")
                                       + d + _txt(" \u00b7 profit live"))
                else:
                    # Alt-Payload (nur Preise fest) ehrlich benennen.
                    frozen_btn.setText(_txt("Bought on {d} \u2013 prices frozen").format(d=d))
            else:
                frozen_btn.setText(_txt("Freeze plan \u2013 purchase done"))
        _frozen_btn_text()
        _frozen_btn_style(bool(getattr(self, "_bd_frozen", None)))
        frozen_btn.setChecked(bool(getattr(self, "_bd_frozen", None)))
        frozen_btn.setToolTip(_txt(
            "ON: freezes the PLAN – recipe structure, buy/build "
              "decisions, quantities and run planner are fixed from "
              "now on (along with purchase prices, the job cost basis "
              "and the PURCHASING stock as of NOW). That way you can "
              "work on the run planner for days without it "
              "recalculating behind your back. PROGRESS is ticked off "
              "automatically from your ESI jobs (runs delivered since "
              "freezing), and ONLY the sell price of the end product "
              "stays live – so weeks later you still see the real "
              "profit against the purchase costs OF THAT TIME.\nOFF: "
              "back to live prices, live stock and a live plan."))
        ctrl.addWidget(frozen_btn)
        # Nutzer-Fall 91 Lowsec-Cormorants: der Einfrier-STAND kann Fern-
        # Bestände enthalten (max(eingefroren, live) hält sie fest, egal was
        # der neue Orts-Scope live zählt). Dieser Knopf setzt NUR den
        # Bestand des Einfrier-Stands auf den aktuellen Live-Stand (im
        # gewählten Scope) neu - Einkaufspreise/Jobkosten-Basis bleiben vom
        # Einfrier-Tag (einfaches Aus/Ein-Frieren würde die verfälschen).
        refz_btn = QPushButton(_txt("Reset frozen stock"))
        refz_btn.setIcon(icons.icon("package"))
        refz_btn.setMinimumHeight(34)
        # _secondary_btn_css wird ERST WEITER UNTEN definiert - hier bewusst
        # eine eigenständige Zuweisung statt einer Vorwärts-Referenz.
        refz_btn.setStyleSheet(
            f"QPushButton{{background:transparent; color:{theme.TEXT}; "
            f"border:1px solid {theme.BORDER}; border-radius:6px; "
            f"padding:6px 14px; font-size:13px;}}"
            f"QPushButton:hover{{border-color:{theme.CYAN}; color:{theme.CYAN};}}")
        refz_btn.setToolTip(
            _txt(
                "Sets ONLY the frozen STOCK to the current live state "
                  "(within the chosen stock scope) – prices and the job "
                  "cost basis stay from the day of freezing. This clears "
                  "out remote storage from the frozen state that the new "
                  "build-structure scope no longer counts.\nSave the "
                  "build plan afterwards so it survives a restart."))
        refz_btn.setVisible(False)

        def _rebase_frozen_stock():
            fz = getattr(self, "_bd_frozen", None)
            if not fz:
                return
            live = getattr(self, "_bd_live_stock", None)
            if live is None:
                # An den DIALOG haengen, nicht an die MainWindow - sonst
                # erscheint die Meldung hinter dem Bauplan-Fenster und es
                # sieht aus, als passiere nichts.
                QMessageBox.information(
                    dlg, _txt("Frozen stock"),
                    _txt("The live state is not there yet \u2013 please enable "
                         "\u201e Subtract assets\u201c first and wait for the fetch."))
                return
            # VORSCHAU + Bestaetigung: der Eingriff kann den halben Plan auf
            # "muss gekauft werden" kippen (der Einfrier-Stand haelt ja die
            # Kaufmengen vom Einfrier-Tag fest). Vorher gab es nur einen
            # fluechtigen Tooltip - "es aendert sich nichts" war von "hat
            # nicht ausgeloest" nicht zu unterscheiden (Nutzer-Meldung).
            _diff = self._frozen_stock_rebase_diff(fz.get("stock") or {}, live)
            if not _diff["changed"]:
                QMessageBox.information(
                    dlg, _txt("Frozen stock"),
                    _txt("The frozen stock already matches the current live state "
                         "exactly \u2013 there is nothing to change.\n\n"
                         "(That is why nothing changes in the build plan either.)"))
                return
            try:
                _nm = store.cached_names([c[0] for c in _diff["changed"][:8]])
            except Exception:
                _nm = {}
            _lines = "\n".join(
                "  \u2022 " + _nm.get(c[0], f"#{c[0]}") + ": "
                + f"{c[1]:,}".replace(",", "'") + " \u2192 "
                + f"{c[2]:,}".replace(",", "'")
                for c in _diff["changed"][:8])
            if len(_diff["changed"]) > 8:
                _lines += "\n  " + _txt("\u2026 and {n} more").format(n=len(_diff['changed']) - 8)
            _ans = QMessageBox.question(
                dlg, _txt("Reset frozen stock"),
                _txt("{n} position(s) change ({down} less, {up} more, {gone} to 0):"
                     "\n\n{lines}\n\n"
                     "Purchase prices and job-cost basis stay from the freeze day.\n"
                     "Careful: whatever drops to 0 here is planned as TO BUY again "
                     "afterwards.").format(
                    n=len(_diff['changed']), down=_diff['down'], up=_diff['up'],
                    gone=_diff['gone'], lines=_lines),
                QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
            if _ans != QMessageBox.Yes:
                return
            fz["stock"] = {int(k): int(v) for k, v in live.items()}
            # Der Einfrier-Stand IST ab jetzt der Live-Stand - also die neue
            # "ESI-Seite". Nicht direkt in _bd_opts["stock"] schreiben, sonst
            # läuft der Klick an der Herkunfts-Auflösung vorbei: eine
            # eingefügte Bestandsliste wäre weg und _bd_stock_src zeigte eine
            # Herkunft, die es nicht mehr gibt (gleiche Fehlerklasse wie im
            # eingefrorenen job()-Pfad).
            self._bd_esi_stock_base = dict(fz["stock"])
            self._bd_virt_stock = {}
            self._recompute_bd_stock()
            _sp_rb = getattr(self, "_bd_sync_paste_panel", None)
            if _sp_rb is not None:
                _sp_rb(refill_box=False)
            rebuild()
            self._flash_tip(_txt(
                "Frozen stock set to NOW \u2013 {n} position(s) changed. "
                "Don't forget \u201eSave build plan\u201c!").format(
                n=len(_diff['changed'])))
            # Zusaetzlich in die Bestandszeile schreiben: der Tooltip ist nach
            # 2 s weg, diese Zeile bleibt stehen.
            try:
                asset_age_lbl.setText(_txt(
                    "Frozen stock reset on {when} \u2013 {n} position(s) changed "
                    "({down} less, {up} more, {gone} to 0). Prices still from the freeze "
                    "day. Don't forget: \u201eSave build plan\u201c."
                ).format(when=_time_mod.strftime("%d.%m. %H:%M", _time_mod.localtime()),
                         n=len(_diff['changed']), down=_diff['down'], up=_diff['up'],
                         gone=_diff['gone']))
                asset_age_lbl.setStyleSheet(
                    f"font-size:11px; color:{theme.AMBER}; font-weight:700;")
                # Das Label ist normalerweise versteckt (Kleingedrucktes im
                # Tooltip) - diese Rueckmeldung MUSS er sehen.
                asset_age_lbl.setVisible(True)
            except NameError:
                pass
        # HINWEIS: hier stand der Knopf „\U0001F4CB Bestand einfügen". Er ist
        # auf Nutzer-Vorgabe ERSATZLOS aus der Kopfleiste verschwunden - die
        # Leiste war „voll mit verwirrendem, unübersichtlichem Zeug". Die
        # Funktion wandert als festes Panel nach RECHTS in den Materialien-Tab
        # (dort war die halbe Breite leer, und dort sieht man die Lücke in der
        # Spalte „Besitze" auch tatsächlich). Bewusst NICHT verdoppelt: es gibt
        # genau EINEN Aufrufpunkt.
        refz_btn.clicked.connect(_rebase_frozen_stock)
        # refz_btn haengt NICHT mehr in der Kopfleiste (s. Werkzeuge-Menue
        # weiter unten). Die Sichtbarkeits-Steuerung wandert an den
        # MENUEEINTRAG - setVisible(True) auf einem parentlosen Widget waere
        # ein frei fliegendes Fenster.
        # Die restlichen drei Kopfzeilen-Knöpfe sind bewusst dezenter als "Neu
        # berechnen" - das ist der eine klare Haupt-Klick, die anderen sind
        # optionale Zusatzfunktionen, kein Grund, gleich stark ins Auge zu
        # fallen. Einheitlicher, ruhiger Stil statt drei verschiedener,
        # kräftiger Farbrahmen.
        _secondary_btn_css = (
            f"QPushButton{{border:1px solid {theme.BORDER}; border-radius:6px; "
            f"padding:6px 12px; color:{theme.MUTED}; font-size:13px; "
            f"background:transparent;}}"
            f"QPushButton:hover{{border-color:{theme.CYAN}; color:{theme.TEXT};}}")
        esi_all_btn = QPushButton(_txt("Load everything from ESI"))
        esi_all_btn.setIcon(icons.icon("satellite"))
        esi_all_btn.setMinimumHeight(34)
        esi_all_btn.setStyleSheet(_secondary_btn_css)
        esi_all_btn.setToolTip(
            _txt(
                "One click instead of four: fetches your real "
                  "blueprints (BPOs/BPCs) for the end product, "
                  "components and reactions AND reduces the invention "
                  "attempts needed – all at once, instead of hunting for "
                  "the individual buttons in each tab."))
        _lhub_lbl = QLabel(f"Hub: {self._active_hub_label()}")
        _lhub_lbl.setObjectName("Muted")
        _lhub_lbl.setToolTip(_txt(
            "The buy and sell hub is chosen at the top left of the "
              "tool and applies to all tabs. The structure icon "
              "marks your market structures. On the next "
              "„Recalculate“ its real sell order book is used for "
              "the material costs."))
        self._register_tool_hub_label(_lhub_lbl)
        # NICHT in die Kopfleiste haengen (Nutzer: "das was da fix
        # reingeschrieben steht kann weg"). Der EINKAUFS-Hub wird oben links
        # im Tool gewaehlt und aendert sich hier nie - als dauerhafter Text
        # war er nur Ballast. Das Objekt bleibt registriert, damit die
        # Hub-Aktualisierung weiterlaeuft; es hat einen Parent und wird
        # dadurch nicht zum eigenen Fenster.
        _lhub_lbl.setParent(dlg)
        _lhub_lbl.setVisible(False)
        optimizer_btn = QPushButton(_txt("Optimal quantity"))
        optimizer_btn.setIcon(icons.icon("trend_up"))
        optimizer_btn.setToolTip(_txt(
            "Which quantity pays off most? Shows the profit curve over "
              "quantity, including market depth on the sell side."))
        optimizer_btn.setStyleSheet(_secondary_btn_css)
        optimizer_btn.clicked.connect(self.open_optimizer)
        ladder_btn = QPushButton(_txt("Order-book exact"))
        ladder_btn.setIcon(icons.icon("chart"))
        ladder_btn.setToolTip(_txt(
            "Replaces the flat price of the shopping list with real "
              "sell order book prices – shows how expensive thin markets "
              "really are (one live request per material)."))
        ladder_btn.setStyleSheet(_secondary_btn_css)
        ladder_btn.clicked.connect(self.open_ladder_check)
        # ---- Kopfleiste entruempelt (Nutzer: "die Uebersichtlichkeit im UI
        # Layout ist schrecklich"). Vorher standen SECHS gleich grosse Knoepfe
        # nebeneinander, ohne dass irgendetwas sagte, was man staendig braucht
        # und was einmal im Monat. Sichtbar bleiben jetzt nur die HAUPTAKTION
        # ("Neu berechnen") und der ZUSTAND (Einfrieren); alles Seltene liegt
        # hinter EINEM Menue.
        # BEWUSST so gebaut: alle Knopf-Objekte bleiben bestehen und behalten
        # ihre komplette Verdrahtung (Handler, enabled-Umschaltung waehrend
        # Ladevorgaengen). Sie werden nur nicht mehr in die Leiste gehaengt -
        # das Menue loest sie per click() aus. Der Umbau ist damit rein
        # visuell und kann an der Logik nichts kaputtmachen.
        from PySide6.QtWidgets import QMenu as _QMenu
        tools_btn = QPushButton(_txt("Tools"))
        tools_btn.setIcon(icons.icon("menu"))
        tools_btn.setMinimumHeight(34)
        tools_btn.setStyleSheet(_secondary_btn_css)
        tools_btn.setToolTip(_txt(
            "Less frequently used actions: load ESI data, quantity "
              "optimiser, order-book-accurate prices – and for frozen "
              "plans „reset frozen stock“."))
        _tools_menu = _QMenu(tools_btn)
        # QMenu zeigt Tooltips per Default GAR NICHT - ein ausgegrauter
        # Eintrag stand deshalb voellig unerklaert da (Nutzer-Meldung
        # "kann ich gar nicht mehr anklicken"). Zusaetzlich steht der Grund
        # ab jetzt im Eintragstext selbst, damit man ihn ohne Hovern sieht.
        _tools_menu.setToolTipsVisible(True)
        # SYMBOLE STATT EMOJI (Nutzer, Sitzung 8): eigenes Strich-Set aus
        # icons.py - nimmt den ruhigen Stahlton an, hellt beim Hovern auf
        # und passt zur Typografie (Emoji brachten fremde Farben und
        # Groessen mit). Der Text traegt KEIN Symbol mehr, das Icon sitzt
        # links davon, wo Qt es erwartet.
        _refz_act = _tools_menu.addAction(
            icons.icon("package"), _txt("Reset frozen stock"))
        _esi_act = _tools_menu.addAction(
            icons.icon("satellite"), _txt("Load everything from ESI"))
        _tools_menu.addSeparator()
        _opt_act = _tools_menu.addAction(
            icons.icon("trend_up"), _txt("Optimal quantity"))
        _lad_act = _tools_menu.addAction(
            icons.icon("chart"), _txt("Order-book exact"))
        _tools_menu.addSeparator()
        # NUTZER-VORFAELLE (Sitzung 8: Ferrofluid 290, Ferrogel 805, Hexite):
        # der eingefrorene Plan haelt am Einfrier-Bestand fest (max-Merge,
        # bewusst) und ist blind fuer real verschwundenen Bestand. Diese
        # Vorschau sagt VORHER, was beim Abarbeiten der restlichen Runs
        # fehlen wird - statt es am Reaktor zu merken.
        _fehl_act = _tools_menu.addAction(
            icons.icon("target"), _txt("Check shortfall"))
        # NACHKAUFEN NUR AUF KLICK (Nutzer-Wunsch Sitzung 12: "gekauft ist
        # gekauft" - die Einkaufsliste darf nicht von selbst wachsen).
        # Dieser Eintrag nimmt AUSSCHLIESSLICH echte Verluste auf: Material,
        # das schon einmal gedeckt WAR und jetzt fehlt. Der gewoehnliche
        # Rest-Bedarf kommt hier nie hinein.
        _nach_act = _tools_menu.addAction(
            icons.icon("cart"), _txt("Buy missing again"))
        _nach_act.triggered.connect(self._buy_missing_again)
        # CONTRACT-PREISE (Nutzer, Sitzung 9): Capitals haben in Jita
        # praktisch keine echten Sell-Orders - der Verkaufswert kommt dann
        # sinnvoll nur aus oeffentlichen Contracts. Der Eintrag nimmt den
        # gespeicherten New-Eden-Stand des Scanners; fehlt das Item darin,
        # wird GEZIELT NUR dieses Item frisch gescannt.
        _ct_act = _tools_menu.addAction(
            _txt("Load contract prices (New Eden)"))
        _fehl_act.setToolTip(_txt(
            "Checks the REMAINING runs of the plan against the real current stock "
            "(hangar + pipeline): what will be missing, and how much? Finds "
            "vanished stock before it is missing at build time."))
        _fehl_act.triggered.connect(self._check_shortfall)
        _ct_act.triggered.connect(
            lambda *_a, _tid=type_id: self._bd_load_contract_prices_for(_tid))
        _tool_pairs = ((_refz_act, refz_btn), (_esi_act, esi_all_btn),
                       (_opt_act, optimizer_btn), (_lad_act, ladder_btn))
        for _a, _b in _tool_pairs:
            _a.setToolTip(_b.toolTip())
            _a.triggered.connect(_b.click)

        def _sync_tools_menu():
            """Menueeintraege an den Zustand der (unsichtbaren) Knoepfe
            angleichen - inkl. der enabled-Umschaltung waehrend laufender
            ESI-Abrufe."""
            for _sa, _sb in _tool_pairs:
                _sa.setEnabled(_sb.isEnabled())
            _frozen_now = bool(getattr(self, "_bd_frozen", None))
            # "Einfrier-Bestand neu setzen" gibt es nur bei eingefrorenen
            # Plaenen (vorher steuerte das die Knopf-Sichtbarkeit).
            _refz_act.setVisible(_frozen_now)
            # Nutzer-Meldung "es passiert nichts": beide Eintraege konnten
            # stumm abbrechen (Orderbuch-genau verweigert bei eingefrorenen
            # Preisen, Rebase braucht einen geladenen Live-Stand) - die
            # Begruendung kam nur als fluechtiger Tooltip am Cursor. Jetzt
            # wird der Eintrag SICHTBAR gesperrt und sagt im Tooltip, warum.
            _lad_act.setEnabled(not _frozen_now)
            _lad_act.setText(_txt("Order-book exact")
                             + (_txt("  \u2013 not with frozen prices")
                                if _frozen_now else ""))
            _lad_act.setToolTip(
                _txt("Not possible while the prices are frozen \u2013 the tool "
                     "fetches LIVE order-book prices and would replace the pinned "
                     "purchase prices. Unfreeze first ( button at the top).")
                if _frozen_now else ladder_btn.toolTip())
            _has_live = getattr(self, "_bd_live_stock", None) is not None
            _refz_act.setEnabled(_has_live)
            _refz_act.setText(_txt("Reset frozen stock")
                              + ("" if _has_live
                                 else _txt("  \u2013 load assets first")))
            _refz_act.setToolTip(
                refz_btn.toolTip() if _has_live else
                _txt("The live state is not there yet \u2013 please enable "
                     "\u201e Subtract assets\u201c first and wait for the fetch."))
            # CONTRACT-PREISE GIBT ES JE ITEM, NICHT JE BUENDEL (Pruefung
            # der Werkzeuge 26.09.2026): der Eintrag haette die Buendel-ID
            # (-1) in die New-Eden-Contract-Suche geschickt - minutenlang
            # nach einem Typ gesucht, den es nicht gibt, und dann "kein
            # Contract gefunden". Sichtbar gesperrt, mit Grund.
            _ist_b = (type_id == industry.BUENDEL_ID)
            _ct_act.setEnabled(not _ist_b)
            _ct_act.setText(_txt("Load contract prices (New Eden)")
                            + (_txt("  \u2013 not for bundles") if _ist_b else ""))
            _ct_act.setToolTip(_txt(
                "A bundle sells its end products one by one at their own hub "
                "prices; a contract price per end product is not supported "
                "yet. Open the single build plan of that product for it.")
                if _ist_b else "")
        _tools_menu.aboutToShow.connect(_sync_tools_menu)
        _sync_tools_menu()
        # Fuer die b-Suite: Menue und Eintraege erreichbar (b114 prueft die
        # Werkzeuge am Buendel).
        self._bd_tools_menu = _tools_menu
        self._bd_tools_actions = {"refz": _refz_act, "esi": _esi_act,
                                  "opt": _opt_act, "ladder": _lad_act,
                                  "fehl": _fehl_act, "nach": _nach_act,
                                  "contract": _ct_act}
        # Holder-Muster wie gehabt: der Einfrier-Handler ruft _refz_sync["fn"],
        # egal wann er das erste Mal laeuft.
        _refz_sync["fn"] = _sync_tools_menu
        tools_btn.setMenu(_tools_menu)
        ctrl.addWidget(tools_btn)
        # "+ ENDPRODUKT" (Nutzer-Entscheid 26.09.2026: "direkt aus einem
        # Bauplan ein Multibauplan erstellen"): haengt ein weiteres Ende an
        # den offenen Plan - ein Einzelplan wird dabei zum Buendel.
        # NAME (Nutzer 26.09.2026: "'Add end product' zeigt nicht direkt, um
        # was es geht - evtl. 'Add build plan'"): der Knopf haengt einen
        # weiteren Bauplan (Item oder gespeicherten Plan) an - so heisst er.
        ende_btn = QPushButton(" " + _txt("Add build plan"))
        ende_btn.setIcon(icons.icon("plus"))
        ende_btn.setMinimumHeight(34)
        # AMBER-RAHMEN (Nutzer 27.09.2026: "Add build plan ein wenig
        # ersichtlicher, Amber-Rahmen, auch beim normalen Bauplan - optisch
        # gleich und an derselben Position"): derselbe Stil wie "Create
        # shopping list" und "Buy Missing Blueprints".
        ende_btn.setStyleSheet(theme.amber_rahmen_knopf())
        ende_btn.setToolTip(_txt(
            "Add another build plan (an item or a saved plan) to this one \u2013 a "
            "single plan becomes a bundle, shared intermediates are built once. "
            "A saved plan that is frozen, reserved or completed stays as it is "
            "\u2013 the addition goes into a new copy."))
        ende_btn.clicked.connect(lambda _c=False: self._multi_ende_hinzufuegen_offen())
        # LAGE (Nutzer 26.09.2026: "lieber dort, wo die Endprodukte auch
        # aufgelistet sind - direkt unter 'Bundle', in der Endprodukt-Box"):
        # beim Buendel steht der Knopf in der Kopfzeile der Karte
        # "Endprodukte" (_multi_enden_karte holt ihn sich). SEIT 27.09.2026
        # AUCH BEIM EINZELPLAN dort (Nutzer: "an derselben Position"): eine
        # schmale Karte "End product of this plan" mit demselben Kopf -
        # nicht mehr in der Leiste oben.
        self._bd_ende_btn = ende_btn         # b-Suite drueckt ihn
        # CONTRACT-PREISE SICHTBAR STATT IM MENUE (Nutzer, 15.09.2026: "der
        # Load-Contract-Prices-Knopf soll ersichtlicher werden, nicht
        # versteckt in Dropdowns"). Er erscheint GENAU DANN, wenn es keinen
        # Verkaufspreis gibt - der Capital-Fall - und blinkt dann wie der
        # Markt-Scan-Knopf. Sonst bleibt die Leiste ruhig; ein Knopf, der
        # immer da ist, faellt nicht mehr auf.
        # DER MENUEEINTRAG BLEIBT zusaetzlich bestehen: wer den Preis auch
        # ohne Not neu laden will, findet ihn dort wie bisher.
        ct_btn = QPushButton(_txt("Load contract prices"))
        ct_btn.setIcon(icons.icon("satellite"))
        ct_btn.setMinimumHeight(34)
        # 2 PX RAHMEN SCHON IM RUHEZUSTAND - sonst waechst der Knopf beim
        # Blinken um ein Pixel und schiebt die ganze Leiste (derselbe
        # Nutzer-Befund wie beim Markt-Scan-Knopf, Sitzung 20).
        _ct_btn_css = (
            f"QPushButton{{border:2px solid {theme.BORDER}; border-radius:6px; "
            f"padding:6px 12px; color:{theme.MUTED}; font-size:13px; "
            f"background:transparent;}}"
            # NUR DIE FARBE, nicht die ganze Rahmenregel: die Staerke bleibt
            # bei 2 px (sonst springt die Breite beim Hovern), und aa78 haelt
            # cyane Panel-Rahmen aus dem Bauplan heraus.
            f"QPushButton:hover{{border-color:{theme.CYAN}; color:{theme.TEXT};}}")
        ct_btn.setStyleSheet(_ct_btn_css)
        ct_btn._ct_css = _ct_btn_css
        ct_btn.setToolTip(_txt(
            "There is no market price for this item \u2013 capitals are hardly "
            "ever sold through sell orders. This takes the median of the "
            "public New Eden contracts. The saved scan is used first; only "
            "an item that is missing from it is fetched fresh."))
        ct_btn.setVisible(False)
        ct_btn.clicked.connect(
            lambda *_a, _tid=type_id: self._bd_load_contract_prices_for(_tid))
        self._bd_ct_btn = ct_btn
        ctrl.addWidget(ct_btn)
        # VERKAUFSCHARAKTER: bestimmt Sales Tax + Broker Fee (Accounting /
        # Broker Relations + Standings). Vorher galt EIN globaler Wert fuer
        # alle Plaene, und man sah nicht, von welchem Charakter er stammt.
        # VERKAUFS-HUB: bestimmt Broker Fee (Standings je Hub) und den
        # Verkaufspreis des Endprodukts. Der EINKAUF bleibt am gescannten Hub -
        # gekauft wird ja dort, wo der Markt-Scan herkommt.
        # KOPFZEILE ENTLASTEN (Nutzer: "damit es wenns standard zugeklappt ist
        # nicht so ueberladen wirkt"): Verkaufsort, Verkaufscharakter, Fracht
        # und Zusatzkosten wandern in den ausklappbaren Details-Bereich. Sie
        # werden hier wie bisher GEBAUT (die ganze Logik daran bleibt
        # unveraendert), aber gesammelt statt sofort in die Kopfzeile gehaengt
        # - der Details-Bereich entsteht erst weiter unten.
        _moved_ctrl = []
        _hlbl = QLabel(_txt("Sell in:")); _hlbl.setStyleSheet(f"color:{theme.MUTED};")
        _moved_ctrl.append(_hlbl)
        sellhub_cb = QComboBox()
        sellhub_cb.setMinimumWidth(130); sellhub_cb.setMaximumWidth(210)
        for _lbl, _key in self._sell_hub_choices(self._market_structures()):
            sellhub_cb.addItem(_lbl, _key)
        _wanthub = getattr(self, "_bd_sell_hub", None) or "jita"
        _hix = sellhub_cb.findData(_wanthub)
        sellhub_cb.setCurrentIndex(_hix if _hix >= 0 else 0)
        sellhub_cb.setToolTip(_txt(
            "WHERE do you sell the end product? That changes two "
              "things:\n• the BROKER FEE (depends on your standings "
              "towards the station owner – different per hub)\n• the "
              "SELL PRICE (looked up there for this one item, no full "
              "market scan needed)\nPURCHASING stays at the scanned "
              "hub – you buy where the market scan comes from.\nIn "
              "player structures the owner sets the broker fee "
              "themselves; ESI does not report it – the global value "
              "applies there."))
        self._bd_sell_hub = sellhub_cb.currentData()

        def _pick_sell_hub(_i=0):
            self._bd_sell_hub = sellhub_cb.currentData()
            self._bd_hub_sell_price = None      # neu holen
            _fn = getattr(self, "_bd_full_rebuild", None)
            if _fn is not None:
                _fn()
            self._fetch_hub_sell_price(type_id)
        sellhub_cb.currentIndexChanged.connect(_pick_sell_hub)
        _moved_ctrl.append(sellhub_cb)
        _cf = self.settings.get("char_fees") or {}
        if True:
            # IMMER anzeigen, auch ohne geladene Charakterdaten - sonst ist
            # das Feld unsichtbar und niemand ahnt, dass es existiert
            # (Nutzer: "wo ist das?"). Ohne Daten steht drin, wie man sie holt.
            _sclbl = QLabel(_txt("via:")); _sclbl.setStyleSheet(f"color:{theme.MUTED};")
            _moved_ctrl.append(_sclbl)
            sellchar_cb = QComboBox()
            sellchar_cb.setMinimumWidth(130); sellchar_cb.setMaximumWidth(210)

            def _fill_sellchar():
                """Liste aus den AKTUELLEN Settings aufbauen. Als Funktion,
                weil der Nutzer die Skills typischerweise erst holt, WENN der
                Bauplan schon offen ist - vorher war die Liste dann dauerhaft
                leer und nur Schliessen/Neu-Oeffnen half."""
                _now = self.settings.get("char_fees") or {}
                _keep = sellchar_cb.currentData()
                sellchar_cb.blockSignals(True)
                sellchar_cb.clear()
                _bc = self._best_sell_char(_now)
                sellchar_cb.addItem(
                    _txt("\u2014 global \u2014") if _now
                    else _txt("\u2014 global \u2014 (skills not loaded)"), None)
                sellchar_cb.setStyleSheet(
                    "" if _now else
                    f"QComboBox{{border:1px solid {theme.AMBER}; "
                    f"color:{theme.AMBER};}}")
                for _cid, _d in sorted(
                        _now.items(),
                        key=lambda kv: float(kv[1].get("combined", 99))):
                    sellchar_cb.addItem(
                        f"{_d.get('name', _cid)}  "
                        f"{float(_d.get('combined', 0)):.2f} %"
                        + ("  \u2b50" if int(_cid) == (_bc or -1) else ""),
                        int(_cid))
                _w = _keep if _keep is not None else getattr(
                    self, "_bd_sell_char", None)
                if _w is None:
                    _w = _bc
                _i = sellchar_cb.findData(_w)
                sellchar_cb.setCurrentIndex(_i if _i >= 0 else 0)
                sellchar_cb.blockSignals(False)
                self._bd_sell_char = sellchar_cb.currentData()
            _fill_sellchar()
            self._bd_refill_sellchar = _fill_sellchar
            sellchar_cb.setToolTip(_txt(
                "Who sells the final product? Determines sales tax and broker fee "
                "\u2013 with thin margins the biggest lever of all.\n\u2b50 = lowest "
                "total fee, preset for NEW build plans.\n\u201e\u2014 global \u2014\u201c "
                "takes the values from the settings (behaviour as before).\nThe "
                "choice is saved with the build plan and freezes with it \u2013 "
                "otherwise the target price is off later.\nFill the list: Settings "
                "\u2192 \u201e Find best character automatically\u201c.")
                + ("" if _cf else _txt(
                   "\n\n\u26a0 NO character data loaded yet \u2013 the global fee rate "
                   "from the settings applies. Click \u201e Find best character "
                   "automatically\u201c once, then all characters with their total fee "
                   "appear here.")))

            def _pick_sell_char(_i=0):
                self._bd_sell_char = sellchar_cb.currentData()
                _fn = getattr(self, "_bd_full_rebuild", None)
                if _fn is not None:
                    _fn()
            sellchar_cb.currentIndexChanged.connect(_pick_sell_char)
            # FEHLTE: das Dropdown wurde erzeugt und verdrahtet, aber nie ins
            # Layout gehaengt - sichtbar war nur die Beschriftung "durch:".
            _moved_ctrl.append(sellchar_cb)
            self._bd_sell_char = sellchar_cb.currentData()
        ctrl.addStretch()
        from PySide6.QtWidgets import QCheckBox as _QCheckBox
        asset_cb = _QCheckBox(_txt("Subtract assets"))
        asset_cb.setIcon(icons.icon("package"))
        asset_cb.setToolTip(_txt("Subtracts what already lies on your build "
                                 "structures per ESI."))
        # Nutzer-Wunsch (91 Cormorants im Lowsec-Nirgendwo zählten als
        # Bestand): der ORT des Bestands ist jetzt wählbar und sichtbar,
        # statt bei fehlender Struktur-Verknüpfung still auf "überall"
        # zurückzufallen.
        stock_scope_cb = QComboBox()
        # NEUE VOREINSTELLUNG (Nutzer, Sitzung 19). "Only build structures"
        # meint ALLE eingetragenen Bau-Strukturen - nicht die, in der DIESER
        # Plan baut. Solange alle im selben System standen, war das dasselbe.
        # Seit der Nutzer die Produktion auf eine NPC-Station umgestellt hat,
        # zaehlte weiter sein Material in A-DDGY mit, und der Plan meldete
        # "gedeckt", obwohl am Bauort nichts liegt. In EVE muss das Material
        # dort liegen, wo der Job laeuft.
        # STANDARD WIEDER "ONLY BUILD STRUCTURES" (Nutzer-Entscheid Sitzung
        # 20). "Nur wo dieser Plan baut" war seit Sitzung 19 Standard - fuer
        # den Simurgh-Fall (Struktur in einer anderen Region). Fuer den
        # ueblichen Fall - alle Strukturen in EINEM System, Datacores auf der
        # Refinery, Invention auf dem Raitaru - liess der Bereich Material
        # aussen vor, das erreichbar ist. Der Nutzer: "bei Only build
        # structures werden meine Materialien richtig getrackt." Der enge
        # Bereich bleibt waehlbar und sagt jetzt im Namen, wofuer er ist.
        stock_scope_cb.addItem(" " + _txt("Only build structures"), "structures")
        stock_scope_cb.addItem(" " + _txt(
            "Only this plan's structures (for structures in different regions)"),
            "plan")
        stock_scope_cb.addItem(" " + _txt("Everywhere (all locations)"), "all")
        # ALS BEDIENELEMENT ERKENNBAR (Sitzung 17, Nutzer: "man erkennt
        # nicht, dass es ein Button ist - evtl. mit blauem Kreis um den
        # Button herum, und beim Draufhalten bewegt er sich leicht").
        # Umgesetzt als deutlicher Rahmen in Cyan-Blau; beim Draufhalten
        # hellt er auf und der Rahmen wird kraeftiger. Ein echtes Verschieben
        # waere in Qt nur ueber Groessenaenderung machbar - das laesst die
        # Nachbarn springen, deshalb Farbe statt Bewegung.
        stock_scope_cb.setCursor(Qt.PointingHandCursor)
        stock_scope_cb.setStyleSheet(
            f"QComboBox{{border:2px solid {theme.BLUE}; border-radius:6px; "
            f"padding:4px 8px; background:{theme.PANEL2}; color:{theme.TEXT};}}"
            f"QComboBox:hover{{border-color:{theme.CYAN}; "
            f"background:{theme.PANEL};}}"
            f"QComboBox::drop-down{{border:none; width:18px;}}")
        stock_scope_cb.setToolTip(
            _txt(
                "WHERE stock counts:\nOnly build structures – items at all "
                "your linked build structures (default).\nOnly this plan's "
                "structures – only the structures this plan actually uses; "
                "for people whose structures sit in different regions, so "
                "material in the wrong region is not counted.\nEverywhere – "
                "all assets of all pool characters, wherever they are (when "
                "you pull everything together anyway)."))
        _ix_scope = stock_scope_cb.findData(
            self.settings.get("bau_stock_scope") or "structures")
        stock_scope_cb.setCurrentIndex(_ix_scope if _ix_scope >= 0 else 0)

        def _scope_changed(_i):
            self.settings["bau_stock_scope"] = stock_scope_cb.currentData()
            config.save_settings(self.settings)
            if asset_cb.isChecked():
                _toggle_assets(True)      # sofort mit neuem Scope neu laden
        stock_scope_cb.currentIndexChanged.connect(_scope_changed)
        # Alter der ESI-Bestandsdaten (CCP cacht /assets/ ~1 h - frisch
        # abgelieferte Reaktionen erscheinen entsprechend verspätet; das hier
        # macht sichtbar, WIE alt der Stand ist, statt still Falsches zu zeigen).
        asset_age_lbl = QLabel("")
        asset_age_lbl.setVisible(False)   # nur bei Reservierung/Warnung
        asset_age_lbl.setObjectName("Muted")
        asset_age_lbl.setStyleSheet("font-size:11px;")
        asset_age_lbl.setWordWrap(True)
        # asset_cb wird NICHT hier in die obere Leiste gehängt, sondern unten in die
        # rechte Spalte über „Meine Blueprints“ (einheitliches Aussehen).
        # fbtn/pbtn ("Kosten ignorieren \u2013 immer bauen"/"Lagerbestand immer verwenden") werden
        # HIER nur gebaut, aber NICHT mehr in die obere Kopfzeile gehängt - stehen
        # stattdessen als Checkboxen im "🔧 Bau-Strategie"-Panel weiter unten,
        # zusammen mit "Assets abziehen" (gehört inhaltlich zusammen: alle drei
        # entscheiden mit, was gebaut statt gekauft wird) - einheitlicher
        # Checkbox-Stil statt separater Buttons.
        on = bool(getattr(self, "_bd_force", False))
        # UMBENANNT (Nutzer-Frage "braucht es das noch?"): der Haken hiess
        # "Alles selbst bauen" und klang damit wie die Stufe "Alles selbst"
        # der Fertigungstiefe - er tut aber etwas ANDERES. Die Tiefe sagt,
        # WELCHE Kategorien du bauen KANNST; dieser Haken schaltet die
        # KOSTENOPTIMIERUNG ab und baut auch dann, wenn Kaufen guenstiger
        # waere. Beide zusammen sind sinnvoll, der Name war das Problem.
        fbtn = _QCheckBox(_txt("Ignore cost \u2013 always build"))
        fbtn.setIcon(icons.icon("hammer"))
        fbtn.setChecked(on)
        fbtn.setToolTip(_txt(
            "Builds everything that the manufacturing depth allows – "
              "EVEN when buying would be cheaper.\n\nDifference to the "
              "manufacturing depth: that decides WHICH categories you "
              "build yourself at all. This checkbox additionally "
              "switches off the cost comparison that otherwise decides "
              "per item."))
        _prefer_on = bool(getattr(self, "_bd_prefer_owned", False))
        # UMBENANNT (Nutzer, Sitzung 14). Der Haken hiess "Lagerbestand immer
        # verwenden" und beschrieb damit einen MATERIALFLUSS - er entscheidet
        # aber ueber das BAUEN. In `industry.production_plan` steht:
        #     _prefer_owned = opts["prefer_build_if_owned"] and
        #                     stock_used.get(tid, 0) > 0
        #     do_build = force or _prefer_owned or ...
        # Also: wo schon eigener Bestand eingesetzt wurde, wird das Item OHNE
        # Preisvergleich gebaut. Ob Bestand ueberhaupt VERWENDET wird, haengt
        # dagegen an "Assets abziehen" - nicht an diesem Haken.
        pbtn = _QCheckBox(_txt("Use what you have, even if buying "
                               "would be cheaper"))
        pbtn.setChecked(_prefer_on)
        pbtn.setToolTip(_txt(
            "Where stock of yours has already been used for an item, that "
              "item is BUILT without comparing prices - even if buying "
              "would be cheaper.\n\nThis does not decide WHETHER stock is "
              "used; that is what \u201eSubtract assets\u201c does."))

        def _pbtn_sperre():
            """`pbtn` grau schalten, wo er nachweislich nichts bewirkt.

            NUTZER (Sitzung 14): "komisch das man beides anhacken kann, das
            eine sollte das andere aushebeln" - und "wenn man das eine
            anhackt sollte das andere frei werden".

            ZWEI GRUENDE, beide aus dem Code:
            1. `do_build = force or _prefer_owned or ...` - steht `force`
               ("Kosten ignorieren") vorne, wird `_prefer_owned` NIE
               ausgewertet.
            2. `_prefer_owned` verlangt `stock_used.get(tid, 0) > 0`. Ohne
               "Assets abziehen" gibt es gar keinen Bestand, die Bedingung
               kann nie zutreffen.
            Ein Haken, der nichts bewirkt, aber bedienbar aussieht, ist
            dieselbe Fehlerklasse wie die Kaestchen an fertigen Runs.
            """
            _f = fbtn.isChecked()
            _a = asset_cb.isChecked()
            _aus = _f or not _a
            pbtn.setEnabled(not _aus)
            if _f:
                pbtn.setToolTip(_txt(
                    "Without effect while \u201eIgnore costs \u2013 always "
                      "build\u201c is on: that already builds everything "
                      "without comparing prices."))
            elif not _a:
                pbtn.setToolTip(_txt(
                    "Without effect while \u201eSubtract assets\u201c is "
                      "off: without stock there is nothing this could act "
                      "on."))

        fbtn.toggled.connect(lambda _v: _pbtn_sperre())
        asset_cb.toggled.connect(lambda _v: _pbtn_sperre())
        _pbtn_sperre()
        # FUER DIE PRUEFUNG ERREICHBAR MACHEN: der Test darf die Sperre nicht
        # ueber `setChecked` ausloesen - daran haengen weitere Slots, die
        # jedes Mal den ganzen Bauplan neu rechnen (die b-Suite lief damit in
        # ihr Zeitlimit). So laesst sich der Zustand setzen und die Sperre
        # gezielt nachziehen, ohne Neuberechnung.
        self._bd_pbtn_sperre = _pbtn_sperre
        endp_v.addLayout(ctrl)
        v.addWidget(endp_card)
        # MULTI-BAUPLAN (1.0.9): die Menge ist IMMER 1 Buendel - die Stueck-
        # zahlen je Endprodukt stehen im Multi Buildplaner. Der Spinner
        # bleibt sichtbar (Layout), aber gesperrt und erklaert sich.
        if type_id == industry.BUENDEL_ID:
            qty_spin.setValue(1)
            qty_spin.setEnabled(False)
            qty_spin.setToolTip(_txt(
                "A multi build plan is always ONE bundle. Change the quantity "
                "per end product in the multi build plan."))
            _qty_lbl.setText(_txt("Bundle:"))
        # Karte "Endprodukte" (nur Buendel): Kosten/Verkauf/Gewinn je Stueck
        # und Ende; rebuild() frischt sie ueber self._bd_multi_refresh auf.
        self._multi_enden_karte(type_id, names, v)

        # --- "Andere Blaupausen" (ME/TE-Einstellungen) - wird weiter unten in
        # den Blueprints-Tab eingehängt (nicht mehr in einer eigenen Seiten-
        # leiste), damit die Haupt-Tabs die volle Breite bekommen. ---------------
        cat_card = QWidget()
        cat_card.setStyleSheet(
            "QSpinBox#PctSpin { padding: 3px 20px 3px 6px; }"
            "QSpinBox#PctSpin::up-button, QSpinBox#PctSpin::down-button { width: 14px; }")
        cat_outer = QVBoxLayout(cat_card)
        cat_outer.setContentsMargins(0, 2, 0, 2); cat_outer.setSpacing(6)

        # Standardwerte je Kategorie (Settings, sonst Notfall-Default) -
        # greifen, wenn ein Attribut gar nicht bzw. auf None gesetzt ist.
        _catv = self._cat_me_te_defaults(self.settings)
        self._bd_esi_me_boxes = {}

        def _cat_chip(label, me_attr, te_attr, tip, kat_key=None):
            chip = QFrame()
            chip.setStyleSheet(
                f"QFrame{{background:{theme.PANEL2}; "
                f"border:1px solid {theme.BORDER}; border-radius:6px;}}")
            cl = QVBoxLayout(chip)
            cl.setContentsMargins(8, 6, 8, 6); cl.setSpacing(3)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"color:{theme.BLUE}; font-weight:800; font-size:13px;")
            cl.addWidget(lbl)
            row = QHBoxLayout(); row.setSpacing(4)
            row.addWidget(QLabel(_txt("ME")))
            sm = QSpinBox(); sm.setRange(0, 10); sm.setSuffix(" %")
            sm.setObjectName("PctSpin")
            sm.setFixedWidth(102); sm.setAlignment(Qt.AlignRight)
            # `or 0` waere hier falsch: ein None (s. Fix in _plan_attrs)
            # wuerde zu 0 statt zum Standard. None heisst „nicht gesetzt".
            _mv = getattr(self, me_attr, None)
            sm.setValue(int(_mv if _mv is not None else _catv[me_attr]))
            sm.setToolTip(tip)
            row.addWidget(sm)
            row.addWidget(QLabel(_txt("TE")))
            st = QSpinBox(); st.setRange(0, 20); st.setSuffix(" %")
            st.setObjectName("PctSpin")
            st.setFixedWidth(102); st.setAlignment(Qt.AlignRight)
            _tv = getattr(self, te_attr, None)
            st.setValue(int(_tv if _tv is not None else _catv[te_attr]))
            st.setToolTip(tip)
            row.addWidget(st)
            cl.addLayout(row)
            # UMSCHALTER ESI <-> HANDEINGABE (Nutzer, Sitzung 16: "Zusaetzlich
            # moechte ich, dass man umschalten kann auf manuelle Eingabe").
            # ANGEHAKT = die echten Werte der eigenen Blaupausen gelten,
            # schlechteste Kopie je Bauteil. Die Drehfelder sind dann
            # GESPERRT statt versteckt - sonst waere unklar, ob sie noch
            # wirken. Sie greifen weiter fuer Bauteile, zu denen KEINE eigene
            # Blaupause gefunden wird.
            if kat_key:
                esi_cb = QCheckBox(_txt("Track via ESI"))
                esi_cb.setToolTip(_txt(
                    "Takes ME/TE from your own blueprints (ESI) instead of the fields "
                    "next to it \u2013 per component the WORST copy found.\nUntick = your "
                    "numbers next to it apply again.\nWithout an own blueprint for a "
                    "component, the fields always apply."))
                esi_cb.setChecked(self._bd_esi_me_aktiv(kat_key))
                sm.setEnabled(not esi_cb.isChecked())
                st.setEnabled(not esi_cb.isChecked())

                def _esi_um(an, _sm=sm, _st=st, _k=kat_key):
                    _sm.setEnabled(not an)
                    _st.setEnabled(not an)
                    _sch = self.settings.get("bau_me_aus_esi")
                    _sch = dict(_sch) if isinstance(_sch, dict) else {}
                    _sch[_k] = bool(an)
                    self.settings["bau_me_aus_esi"] = _sch
                    config.save_settings(self.settings)
                    # Der Punkt am "Neu berechnen"-Knopf muss angehen - sonst
                    # steht der Schalter um, die Zahlen oben aber noch auf dem
                    # alten Stand, und nichts sagt es. Der Marker wird erst
                    # SPAETER gebaut, deshalb ueber getattr.
                    _sync = getattr(self, "_bd_sync_recalc_marker", None)
                    if _sync is not None:
                        _sync()
                esi_cb.toggled.connect(_esi_um)
                cl.addWidget(esi_cb)
                self._bd_esi_me_boxes[kat_key] = esi_cb
            cat_outer.addWidget(chip)
            return sm, st
        # BESCHRIFTUNG ENTZERRT (Nutzer, Sitzung 16: "ausserdem ist
        # Komponenten 2x vorhanden, das sollte wahrscheinlich nicht sein").
        # Es war KEIN doppelter Regler: in "Blueprints per stage" zaehlt
        # "Komponenten" die aus ESI gefundenen KOPIEN und RUNS fuer den
        # Runplaner, hier ging es um ME/TE fuer die KOSTEN. Zwei ganz
        # verschiedene Dinge unter demselben Namen - der Name war das
        # Problem, nicht die Doppelung. Deshalb tragen die Karten hier
        # jetzt den Zusatz "ME/TE".
        comp_me_spin, comp_te_spin = _cat_chip(
            _txt("Components") + " \u00b7 ME/TE", "_bd_me_component",
            "_bd_te_component",
            _txt("Build components (advanced/capital/hybrid components etc.)."),
            kat_key="components")
        hull_me_spin, hull_te_spin = _cat_chip(
            _txt("Hulls") + " \u00b7 ME/TE", "_bd_me_t1hull", "_bd_te_t1hull",
            _txt("T1 ship hulls that serve as the invention base for T2 ships."),
            kat_key="t1_hulls")
        fuel_me_spin, fuel_te_spin = _cat_chip(
            "Fuel Blocks \u00b7 ME/TE", "_bd_me_fuel", "_bd_te_fuel",
            _txt("Fuel block blueprints for reaction/structure operation."),
            kat_key="fuel_blocks")
        tools_me_spin, tools_te_spin = _cat_chip(
            "Tools \u00b7 ME/TE", "_bd_me_tools", "_bd_te_tools",
            _txt("Build aids such as R.A.M. (Robotics/Starship Tech)."),
            kat_key="tools")
        andere_bp_card = self._collapsible(
            _txt("Other blueprints (ME/TE)"), cat_card, expanded=False, accent=theme.MUTED,
            tip=_txt("Components/T1 hulls/Fuel Blocks/Tools \u2013 usually fully "
                     "researched T1 BPOs, unlike the end product above.\nDEFAULT is "
                     "ME 10 % / TE 20 % (fully researched BPO). What you change here "
                     "applies to THIS build plan and is saved with \u201eSave build "
                     "plan\u201c - it is back on the next opening. A NEW build plan "
                     "always starts at 10/20.\nThe change takes effect with \u201e\u21bb "
                     "Recalculate\u201c (the button shows \u2022 while it is not yet "
                     "included)."))
        # Nutzer-Wunsch: die eigene Einstellung soll nicht bei jedem neuen
        # Bauplan verloren gehen. Bewusst an valueChanged (= der Nutzer dreht
        # wirklich) statt an "Neu berechnen": beim \u00d6ffnen eines GESPEICHERTEN
        # Plans schreibt dessen Wert per setValue in die Spins - h\u00e4ngte das
        # Speichern dort, w\u00fcrde ein einziges \u00d6ffnen eines alten Plans die
        # globale Vorgabe stillschweigend umstellen. Das setValue() im Aufbau
        # (_cat_chip) l\u00e4uft VOR diesem connect, feuert hier also nicht.
        _cat_spin_keys = ((comp_me_spin, "bau_me_component"),
                          (comp_te_spin, "bau_te_component"),
                          (hull_me_spin, "bau_me_t1hull"),
                          (hull_te_spin, "bau_te_t1hull"),
                          (fuel_me_spin, "bau_me_fuel"),
                          (fuel_te_spin, "bau_te_fuel"),
                          (tools_me_spin, "bau_me_tools"),
                          (tools_te_spin, "bau_te_tools"))

        # HINWEIS: hier schrieb ein entprellter Timer jeden Reglerwert sofort
        # als GLOBALEN Standard zurueck. Auf Nutzer-Entscheid entfernt: ein
        # versehentlicher Pfeilklick machte damit z.B. TE 19 % zum Standard
        # fuer alle kuenftigen Plaene. Jetzt gilt fest 10/20 als Standard
        # (config.DEFAULT_SETTINGS); eine Aenderung betrifft NUR den offenen
        # Bauplan und wird mit ihm gespeichert (_save_plan schreibt alle acht
        # Werte, _open_saved_plan stellt sie wieder her).

        # ---- "Neu berechnen" markieren, sobald ME/TE-Regler von dem
        # abweichen, womit zuletzt GERECHNET wurde. Grund (Nutzer-Frage):
        # _store_cat_me_te() laeuft nur in _recompute - dreht man einen
        # Regler, zeigte der Dialog weiter die alten Baukosten, ohne dass
        # irgendetwas darauf hinwies. Automatisch neu rechnen waere falsch:
        # production_plan ist teuer und "Neu berechnen" holt je nach Zustand
        # Live-Orderbuchpreise - bei jedem Pfeiltastendruck unbrauchbar.
        # Also nur ein sichtbarer Hinweis.
        _me_te_spins = ((me_spin, "end_me"), (te_spin, "end_te")) + tuple(
            (sp, key) for sp, key in _cat_spin_keys)
        _recalc_css_clean = recalc.styleSheet()
        _recalc_css_dirty = (_recalc_css_clean
                             + f" border:2px solid {theme.AMBER};")
        _recalc_tip_clean = recalc.toolTip()

        def _current_me_te():
            _st = {_k: int(_sp.value()) for _sp, _k in _me_te_spins}
            # DIE ESI-SCHALTER GEHOEREN IN DEN VERGLEICH (Sitzung 16): sie
            # aendern die Rechnung genauso wie ein gedrehtes Feld. Ohne sie
            # bliebe der Punkt am "Neu berechnen"-Knopf aus, obwohl die
            # angezeigten Zahlen nicht mehr zur Einstellung passen.
            for _k, _cb in (getattr(self, "_bd_esi_me_boxes", None) or {}).items():
                _st["esi:" + _k] = int(_cb.isChecked())
            return _st

        def _sync_recalc_marker():
            _dirty = self._me_te_dirty(_current_me_te(),
                                       getattr(self, "_bd_me_te_applied", None))
            recalc.setText(_txt("\u21bb Recalculate") + (" \u2022" if _dirty else ""))
            recalc.setStyleSheet(_recalc_css_dirty if _dirty
                                 else _recalc_css_clean)
            recalc.setToolTip(
                (_txt("\u26a0 CHANGED ME/TE values are NOT included yet - the numbers "
                      "above belong to the previous state.\n\n")
                 + _recalc_tip_clean) if _dirty else _recalc_tip_clean)
            # Dieser Tooltip wird SPAETER neu gesetzt als der zentrale
            # Umbruch-Lauf (bei jeder Reglerbewegung) - deshalb hier selbst
            # umbrechen, sonst zieht er sich wieder ueber die volle Breite.
            self._wrap_tooltips(recalc)
        # Beim \u00d6ffnen gilt: was in den Reglern steht, IST der gerechnete
        # Stand (die Spins werden aus den _bd_*-Attributen des Plans gesetzt).
        self._bd_me_te_applied = _current_me_te()
        self._bd_sync_recalc_marker = _sync_recalc_marker
        _sync_recalc_marker()
        for _msp, _ in _me_te_spins:
            _msp.valueChanged.connect(lambda _v=0: _sync_recalc_marker())

        hdr_w = QFrame(); hdr_w.setObjectName("Card")
        hv = QVBoxLayout(hdr_w); hv.setContentsMargins(14, 10, 14, 10); hv.setSpacing(7)
        st_title = QLabel("\u2013")
        st_title.setStyleSheet(f"color:{theme.AMBER}; font-size:19px; font-weight:700;")
        # Nutzer-Vorgabe: Titel+Bild und die Kennzahlen NEBENEINANDER statt
        # untereinander. Vorher brauchte der Kopfbereich zwei Zeilen Hoehe,
        # jetzt eine - der Platz geht an Tabs und Item-Liste.
        _hero_row = QHBoxLayout(); _hero_row.setSpacing(18)
        _hero_row.addWidget(st_title, 0, Qt.AlignVCenter)
        stats_row = QHBoxLayout(); stats_row.setSpacing(18)

        def _box(caption, accent=None):
            chip = QFrame()
            chip.setStyleSheet(
                f"QFrame{{background:{theme.PANEL2}; border:1px solid {theme.BORDER}; "
                f"border-radius:8px;}}")
            col = QVBoxLayout(chip); col.setContentsMargins(14, 9, 14, 9); col.setSpacing(2)
            cap = QLabel(caption); cap.setObjectName("Muted")
            cap.setStyleSheet("font-size:11px;")
            val = QLabel("\u2013")
            val.setStyleSheet("font-size:19px; font-weight:700;"
                              + (f" color:{accent};" if accent else ""))
            col.addWidget(cap); col.addWidget(val)
            # GLEICHE GROESSE fuer alle Karten (Nutzer): ohne feste
            # Mindestbreite war jede Karte so breit wie ihre Zahl.
            chip.setMinimumWidth(210)
            val.chip = chip
            # Unterzeile: der BEZUG einer Zahl (pro Stueck bzw. Abzug). Der
            # Nutzer las "Gewinn gesamt 4'664'785" als Gewinn PRO STUECK und
            # hielt den Plan fuer falsch - drei Gesamtwerte und zwei
            # Stueckwerte standen gleich aussehend nebeneinander, einer davon
            # ganz ohne Kennzeichnung. Leer = unsichtbar, kostet keinen Platz.
            sub = QLabel("")
            sub.setObjectName("Muted")
            sub.setStyleSheet("font-size:11px;")
            sub.setVisible(False)
            # PARENT SETZEN, obwohl das Label nicht ins Layout kommt: ein
            # PARENTLOSES Widget wird durch setVisible(True) zu einem eigenen
            # Top-Level-Fenster - beim Nutzer poppte prompt ein leeres
            # "python"-Fenster mit dem Text "davon ... aus Bestand" auf.
            # Genau die Falle, die beim Werkzeuge-Menue schon dokumentiert
            # war. Mit Parent kann das nicht mehr passieren.
            sub.setParent(chip)
            # Nutzer-Vorgabe: "alle diese Kleininformationen weg, nur mit
            # Mouseover arbeiten". Die Unterzeile wird deshalb GAR NICHT ins
            # Layout gehaengt - alle bestehenden setText/setVisible-Aufrufe
            # bleiben gueltig und laufen ins Leere, die Inhalte stehen in den
            # Tooltips der jeweiligen Karte.
            val.sub_lbl = sub
            stats_row.addWidget(chip)
            return val
        # BEIM BUENDEL HEISST DIE ZAHL, WAS SIE IST (Nutzer 26.09.2026: "wie
        # ist hier Build Cost/unit gerechnet? ... wie machen wir das bei
        # mehreren Endprodukten?"): das Buendel hat Menge 1, die Karte zeigt
        # also die GESAMTEN Baukosten aller Enden. Ein Durchschnitt ueber
        # verschiedene Produkte waere eine Zahl ohne Bedeutung; die Kosten je
        # Stueck stehen je Ende in der Karte "Endprodukte".
        st_cost = _box(_txt("Build cost, bundle total") if _ist_buendel
                       else _txt("Build cost / unit"), theme.CYAN)
        st_total = _box(_txt("Total"))
        st_sell = _box(_txt("Sell / unit"))
        st_target = _box(_txt("Min. sell price / unit"), theme.AMBER)
        st_profit = _box(_txt("Total profit"))
        st_profit_raw = _box(_txt("Gross profit (before fees)"), theme.MUTED)
        # NUR DIE KARTEN-BESCHRIFTUNG uebersetzen. Weiter unten ist
        # "Marge" ein interner SCHLUESSEL (_pf.get("Marge"),
        # _profit_rows) - wer den mituebersetzt, findet die Zeile auf
        # Englisch nicht mehr und die Zahl bleibt leer.
        st_marge = _box(_txt("Margin"))
        # Nutzer-Vorgabe: weniger Zahlen. "Gesamt", "Sell / Stk" und
        # "Rohgewinn" verschwinden aus der Leiste - berechnet werden sie
        # weiter und stehen in den Tooltips. Ausblenden statt entfernen:
        # so bleibt jede bestehende setText-Stelle gueltig.
        # Nutzer-Vorgabe (zweite Runde): auch "Min. Verkaufspreis / Stk" raus -
        # vier Karten nebeneinander waren zu viel. Die Zahl bleibt wichtig und
        # steht jetzt im Tooltip von t("Total profit"), zusammen mit dem
        # Verkaufspreis, mit dem dieser Gewinn gerechnet ist. Wieder
        # AUSBLENDEN statt entfernen: alle bestehenden setText/setStyleSheet/
        # setToolTip-Stellen bleiben gueltig und laufen weiter.
        for _hidden in (st_total, st_sell, st_profit_raw, st_target):
            _hidden.chip.setVisible(False)
        stats_row.addStretch()
        _hero_row.addLayout(stats_row, 1)
        hv.addLayout(_hero_row)
        # BESTANDS-STAND (Nutzer-Wunsch, Sitzung 8): "ich will oben im Bauplan
        # sehen, wann die letzte erfolgreiche ESI-Aktualisierung war, die
        # Veraenderungen festgestellt hat". Steht bewusst DIREKT unter den
        # KPI-Karten - der Plan ist nur so viel wert wie der Bestand, auf dem
        # er rechnet. Wird beim Oeffnen aus der Datenbank gefuellt und nach
        # jedem Bestands-Abruf in adone() aktualisiert.
        self._bd_esi_stand_lbl = QLabel("")
        # SICHTBARER (Sitzung 17, Nutzer: "kannst du die ESI-Info etwas
        # ersichtlicher machen?"). Sie sagt, WIE ALT der Bestand ist - und
        # ein veralteter Bestand laesst die Einkaufsliste zu viel kaufen.
        # Also kein Grau mehr: normale Textfarbe, groesser, mit Uhr-Symbol.
        self._bd_esi_stand_lbl.setStyleSheet(
            f"color:{theme.TEXT}; font-size:13px; padding:1px 0;")
        self._bd_esi_stand_lbl.setToolTip(_txt(
            "„Last change detected“ is NOT the same as „last "
              "checked“.\nESI answers regularly even when nothing has "
              "happened in your storage –\nso the program compares the "
              "stock itself and shows the moment when it\nwas last "
              "actually different."))
        self._bd_update_esi_stand()
        hv.addWidget(self._bd_esi_stand_lbl)
        # Kostenzeile: standardmäßig nur die Marge sichtbar (das ist die eine
        # Zahl, die auf einen Blick zählt) - der Rest (Material/Job-Kosten/
        # Invention/Gebühren/Bestandswert/Transport) steckt in einem
        # einklappbaren Mini-Tabellen-Panel, nicht mehr in einer langen
        # Fließtext-Zeile mit sechs Zahlen drin.
        st_break_row = QHBoxLayout(); st_break_row.setContentsMargins(0, 0, 0, 0)
        st_marge_lbl = QLabel(""); st_marge_lbl.setWordWrap(True)
        # Die Marge steht jetzt als vierte KPI-Karte oben (Nutzer-Wunsch) -
        # die eigene Zeile darunter entfaellt. Das Label bleibt MIT PARENT
        # bestehen, damit jede setText-Stelle weiter gilt und daraus kein
        # parentloses Geisterfenster wird.
        st_marge_lbl.setParent(dlg)
        st_marge_lbl.setVisible(False)
        st_details_toggle = QPushButton(_txt("Details \u25be"))
        st_details_toggle.setCheckable(True)
        st_details_toggle.setFixedWidth(90)
        # ALS KNOPF ERKENNBAR (Sitzung 17, Nutzer: "auch das Details zum
        # Ausklappen ist kaum ersichtlich"). Vorher randlos und grau - das
        # sah aus wie Text. Jetzt Rahmen, Cyan-Schrift und ein Hover.
        st_details_toggle.setCursor(Qt.PointingHandCursor)
        st_details_toggle.setStyleSheet(
            f"QPushButton{{border:1px solid {theme.BORDER}; border-radius:5px; "
            f"color:{theme.CYAN}; font-size:11px; padding:2px 8px; "
            f"background:{theme.PANEL2};}}"
            f"QPushButton:hover{{border-color:{theme.CYAN}; "
            f"background:{theme.PANEL};}}"
            f"QPushButton:checked{{border-color:{theme.CYAN}; "
            f"background:{theme.PANEL};}}")
        st_break_row.addWidget(st_details_toggle)
        hv.addLayout(st_break_row)
        st_details_panel = QFrame()
        st_details_panel.setStyleSheet(
            f"QFrame{{background:{theme.PANEL2}; border:1px solid {theme.BORDER}; "
            f"border-radius:6px;}}")
        # Nutzer-Vorgabe: nicht \u00fcber die ganze Fensterbreite ziehen
        # ("ich bin kein Cham\u00e4leon und kann nicht nach links und rechts
        # gleichzeitig schauen"). Label und Wert stehen jetzt dicht
        # beieinander, das Panel bekommt eine feste Maximalbreite.
        # ZWEI SPALTEN (Nutzer): links wie sich die Baukosten zusammensetzen,
        # rechts wie daraus der Gewinn wird. Ziel ist, dass man die Mouseover-
        # Tooltips nicht mehr braucht - alles steht ausgeklappt da. Deshalb
        # auch breiter als die frueheren 420 px; die alte Begrenzung galt fuer
        # EINE Spalte.
        st_details_panel.setMaximumWidth(1240)
        st_details_grid = QGridLayout(st_details_panel)
        st_details_grid.setContentsMargins(12, 8, 12, 8)
        st_details_grid.setHorizontalSpacing(14); st_details_grid.setVerticalSpacing(3)
        st_details_grid.setColumnStretch(0, 1)
        # BENENNUNG (Nutzer-Entscheid): der Bestand wird zu ERSATZKOSTEN
        # bewertet, nicht zum Jita-Sell - siehe stock_price_of(). Die alte
        # Beschriftung "zum Marktpreis" waere jetzt schlicht falsch; der
        # Jita-Sell-Vergleichswert steht im Tooltip der Zeile.
        # "Frachtdienst" steht BEWUSST direkt unter "Material": der ISK/m3-Satz
        # steckt rechnerisch im Materialpreis (siehe _fr_rate), und der Nutzer
        # will die Zahl trotzdem einzeln sehen. Die Material-Zeile zeigt
        # deshalb den Betrag OHNE Aufschlag - beide zusammen ergeben weiterhin
        # genau die Materialkosten, kein Posten wird doppelt abgezogen.
        # LINKE SPALTE - woraus die Baukosten bestehen. "Gebuehren" steht
        # bewusst NICHT mehr hier: sie gehoeren zum Verkauf, nicht zur
        # Herstellung, und stehen jetzt rechts in der Gewinnrechnung.
        # "Invention (\u00d8)" statt nur "Invention" (Nutzer-Befund Sitzung 9:
        # "die Invention-Kosten im Invention-Tab stimmen nicht mit der
        # Details-Liste ueberein"). Es sind ZWEI verschiedene Groessen mit
        # bisher demselben Namen: der Tab zeigt die KAUFMENGE (8 Versuche
        # fuer >=75% Sicherheit), diese Zeile den ERWARTUNGSWERT (Erfolge /
        # Erfolgschance, hier 6,58 Versuche) - denn nur der gehoert in die
        # Marge, sonst waere jedes Produkt zu teuer gerechnet. Nachgerechnet
        # mit den Nutzer-Zahlen: 15'516'167 / (18'879'287/8) = 6,575.
        # EINKAUFSLISTE ALS EIGENE ZEILEN (Nutzer, Sitzung 14): "die
        # gesammtkosten der einkaufsliste und pro stueck, ich will aber jita
        # Sell preis sehen". Ihm war aufgefallen, dass hier "nirgendwo die
        # einkaufsliste mitgerechnet oder angezeigt wird".
        #
        # WARUM DAS NOETIG IST: "Material" ist NICHT die Einkaufsliste. Die
        # Baukosten mischen zwei Dinge, die verschieden zu lesen sind - was
        # der Nutzer JETZT ausgeben muss, und was er zusaetzlich aus dem
        # Hangar verbraucht (Bestand, zu Ersatzkosten). Ohne die Trennung
        # laesst sich nicht beurteilen, was eine Einstellung wirklich kostet:
        # bei ihm sanken die Materialkosten um 250 Mio, waehrend der Bestand
        # um 240 Mio stieg - in der Summe fast unsichtbar.
        # Er hat gegengeprueft: Janice nannte fuer seine Einkaufsliste
        # 1'297 Mio, die Zeile "Material" 1'835 Mio. Zwei verschiedene
        # Groessen, und keine Zeile sagte welche was ist.
        # (SCHLUESSEL, englische Beschriftung): der Schluessel bleibt deutsch,
        # weil er an vielen Stellen als Dict-Key benutzt wird
        # (_detail_val_lbls["Job-Kosten"] ...). Nur die ANZEIGE laeuft durch
        # den Katalog (Englisch -> Deutsch). Sitzung 16.
        # de_scan2: aus  (die ERSTEN Elemente sind Dict-Schluessel, nie sichtbar)
        _detail_rows = [("Material", "Material"), ("Frachtdienst", "Freight service"),
                        ("Job-Kosten", "Job cost"),
                        ("Invention (\u00d8)", "Invention (\u00d8)"),
                        ("Bestand (Ersatzkosten)", "Stock (replacement cost)"),
                        ("\u2212 R\u00fcckl\u00e4ufer", "\u2212 Returned (reprocessing)"),
                        ("= Baukosten gesamt", "= Total build cost"),
                        ("\u00f7 St\u00fcck", "\u00f7 units"),
                        ("Einkaufsliste (Jita Sell)", "Shopping list (Jita sell)"),
                        ("Einkaufsliste / St\u00fcck", "Shopping list / unit")]
        # RECHTE SPALTE - wie aus dem Verkauf der Gewinn wird. Reihenfolge und
        # Vorzeichen genau wie im bisherigen Gewinn-Tooltip, damit man beim
        # Umgewoehnen dieselbe Rechnung wiedererkennt.
        _profit_rows = [("Verkaufspreis / Stk", "Sale price / unit"),
                        ("Verkaufserl\u00f6s brutto", "Gross sale proceeds"),
                        ("\u2212 Steuer + Broker", "\u2212 Tax + broker"),
                        ("\u2212 Baukosten", "\u2212 Build cost"),
                        ("\u2212 Eigene Fahrt", "\u2212 Own trip"),
                        ("\u2212 Zusatzkosten", "\u2212 Extra cost"),
                        ("= Gewinn", "= Profit"), ("Gewinn / Stk", "Profit / unit"),
                        ("Marge", "Margin"),
                        ("Verlustschwelle / Stk", "Break-even / unit")]
        # KURZERKLAERUNG AN JEDER ZEILE (Nutzer 25.09.2026: "waere nett im
        # Dropdown Details auf allen Zeilen eine Mouseover-Info fuer alle
        # ISK-Eintraege, nur kurze Woerter oder Saetze die erklaeren was was
        # ist und kostet"). Bewusst EIN Satz je Zeile: wer hier hovert, will
        # wissen, was die Zahl bedeutet, nicht die Herleitung.
        # Zeilen mit einer EIGENEN, genaueren Erklaerung (Invention,
        # Ruecklaeufer, Frachtdienst, Job-Kosten, Bestand) behalten sie - die
        # wird weiter unten gesetzt und ueberschreibt diese hier.
        # de_scan2: aus  (Schluessel wie in _detail_rows, nie sichtbar)
        # de_scan4: aus  (dito - nur die WERTE laufen durch den Katalog)
        _DETAIL_TIPS = {
            "Material":
                "Value of all materials in the plan – bought plus taken "
                "from stock, without the freight markup.",
            "Frachtdienst":
                "Freight for the shopping list, at your ISK/m³ rate.",
            "Job-Kosten":
                "Installation fees for all jobs: system cost index, "
                "structure tax and SCC surcharge.",
            "Bestand (Ersatzkosten)":
                "Material from your own hangar, valued at what replacing it "
                "would cost.",
            "= Baukosten gesamt":
                "Everything above added up – what this build costs you.",
            "÷ Stück":
                "Total build cost divided by the quantity.",
            "Einkaufsliste (Jita Sell)":
                "What you still have to BUY, at Jita sell prices – your "
                "stock is not in here.",
            "Einkaufsliste / Stück":
                "The shopping list divided by the quantity.",
            "Verkaufspreis / Stk":
                "Price per unit at your sell hub – the basis of this "
                "whole calculation.",
            "Verkaufserlös brutto":
                "Sale price × quantity, before any fees.",
            "− Steuer + Broker":
                "Sales tax and broker fee of the selling character at that "
                "hub.",
            "− Baukosten":
                "The total build cost from the left column.",
            "− Eigene Fahrt":
                "Flat fee for hauling it yourself, times the number of "
                "trips.",
            "− Zusatzkosten":
                "Your own flat extra – contracts, courier, whatever you "
                "enter.",
            "= Gewinn":
                "What is left after fees, build cost, trip and extras.",
            "Gewinn / Stk":
                "Profit divided by the quantity.",
            "Marge":
                "Profit as a percentage of the gross sale proceeds.",
            "Verlustschwelle / Stk":
                "Below this sale price per unit you make a loss – fees, "
                "trip and extras included.",
        }
        # de_scan4: an
        # de_scan2: an
        self._bd_detail_tips = _DETAIL_TIPS
        _detail_val_lbls = {}
        self._bd_detail_val_lbls = _detail_val_lbls   # fuer die Waechter (b7v)
        _detail_caps = {}     # Beschriftungen, damit eine Zeile als GANZES
                              # ausgeblendet werden kann (Reaktionen: Invention)
        for _ri, (_rlabel, _rtext) in enumerate(_detail_rows):
            _cap = QLabel(_txt(_rtext)); _cap.setObjectName("Muted")
            _cap.setStyleSheet("font-size:11px;")
            _val = QLabel("\u2013"); _val.setStyleSheet("font-size:11px; font-weight:700;")
            _val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            _val.setMinimumWidth(120)
            st_details_grid.addWidget(_cap, _ri, 0)
            st_details_grid.addWidget(_val, _ri, 1)
            _tip0 = _DETAIL_TIPS.get(_rlabel)
            if _tip0:
                _cap.setToolTip(_txt(_tip0)); _val.setToolTip(_txt(_tip0))
            if _rlabel.startswith("Invention"):
                # ERKLAERT DIE ABWEICHUNG zum Invention-Tab (Nutzer-Befund
                # Sitzung 9). Beide Zahlen sind richtig, meinen aber
                # Verschiedenes - das gehoert an die Zeile, nicht in ein
                # Handbuch.
                _tt9 = _txt("Statistical EXPECTED VALUE of the invention (required "
                            "successes \u00f7 success chance) \u2013 only that belongs in "
                            "the margin, otherwise every product would be priced too "
                            "high.\nThe Invention tab, by contrast, shows the PURCHASE "
                            "QUANTITY: the attempts for \u226575 % certainty. That number "
                            "is higher \u2013 the difference is your safety buffer of "
                            "datacores.")
                _cap.setToolTip(_tt9)
                _val.setToolTip(_tt9)
            # de_scan4: aus - interner Dict-Schluessel (siehe _detail_rows)
            if _rlabel.startswith("\u2212 R\u00fcckl"):
            # de_scan4: an
                # WEG A: nur sichtbar, wenn es einen Ruecklaeufer gibt (rebuild).
                _ttr = _txt("Input material that comes back when the unrefined "
                            "products are reprocessed \u2013 credited at the hub price. "
                            "It stays on the shopping list because it returns only "
                            "after the reaction.")
                _cap.setToolTip(_ttr); _val.setToolTip(_ttr)
                _cap.setVisible(False); _val.setVisible(False)
            _detail_val_lbls[_rlabel] = _val
            _detail_caps[_rlabel] = _cap
        _profit_val_lbls = {}
        for _ri, (_rlabel, _rtext) in enumerate(_profit_rows):
            _cap = QLabel(_txt(_rtext)); _cap.setObjectName("Muted")
            _cap.setStyleSheet("font-size:11px;")
            _val = QLabel("\u2013")
            _val.setStyleSheet("font-size:11px; font-weight:700;")
            _val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            _val.setMinimumWidth(120)
            st_details_grid.addWidget(_cap, _ri, 2)
            st_details_grid.addWidget(_val, _ri, 3)
            _tip1 = _DETAIL_TIPS.get(_rlabel)
            if _tip1:
                _cap.setToolTip(_txt(_tip1)); _val.setToolTip(_txt(_tip1))
            _profit_val_lbls[_rlabel] = _val
        st_details_grid.setColumnStretch(2, 1)
        # DRITTE SPALTE statt Zeile darunter (Nutzer: "nimm die einfach nach
        # rechts, da hat es so viel freien Platz"). Als Zeile UNTER den beiden
        # Zahlenspalten wurden die Fracht-Felder zusammengequetscht und
        # ueberlappten - der Platz rechts daneben lag dagegen leer.
        _set_row = QVBoxLayout()
        _set_row.setContentsMargins(18, 0, 0, 0)
        _set_row.setSpacing(6)
        st_details_grid.addLayout(_set_row, 0, 4, 12, 1)
        st_details_grid.setColumnStretch(4, 2)
        # Beschriftung + Feld bleiben zusammen (Label, Widget, Label, Widget …)
        # - ein Label ohne sein Feld daneben ist keine Zeile, sondern Raetsel.
        _pair = None
        for _w in _moved_ctrl:
            if isinstance(_w, QLabel):
                _pair = QHBoxLayout(); _pair.setSpacing(6)
                _pair.addWidget(_w)
                _set_row.addLayout(_pair)
            elif _pair is not None:
                _pair.addWidget(_w, 1)
                _pair = None
            else:
                _set_row.addWidget(_w)
        st_details_panel.setVisible(False)

        def _toggle_st_details(checked):
            st_details_toggle.setText(_txt("Details \u25b4") if checked else _txt("Details \u25be"))
            st_details_panel.setVisible(checked)
        st_details_toggle.toggled.connect(_toggle_st_details)
        hv.addWidget(st_details_panel)
        st_struct = QLabel(""); st_struct.setWordWrap(True)
        st_struct.setStyleSheet(
            f"color:{theme.CYAN}; font-size:13px; padding:6px 10px; "
            f"background:rgba(70,224,200,0.08); border:1px solid rgba(70,224,200,0.25); "
            f"border-radius:6px;")
        # Die Struktur-Zeile ("Fertigung: X (Auto) - Reaktionen: Y (Auto)")
        # ist reine Information und aendert sich waehrend eines Plans nie.
        # Sie wandert in den Tooltip der Baukosten-Karte; das Label bleibt
        # bestehen (mit Parent!), damit jede setText-Stelle weiter gilt.
        st_struct.setParent(dlg)
        st_struct.setVisible(False)
        st_transport = QLabel(""); st_transport.setWordWrap(True)
        st_transport.setStyleSheet("font-size:13px;")
        hv.addWidget(st_transport)
        v.addWidget(hdr_w)

        tw = QTreeWidget(); tw.setColumnCount(5)
        tw.setEditTriggers(QTreeWidget.NoEditTriggers)
        # Nutzer-Vorgabe: "ISK/Stk" und "Kosten" interessieren im Baum nicht -
        # das Tool rechnet ja. Die Spalten bleiben im Datenmodell (der Code
        # setzt sie weiter), werden aber ausgeblendet: so bleibt jede
        # bestehende setText-Stelle gueltig und nichts kann kaputtgehen.
        tw.setHeaderLabels([_txt("Item"), _txt("Quantity"), _txt("Action"), "ISK/" + _txt("unit"), _txt("Cost")])
        tw.setColumnHidden(3, True)
        tw.setColumnHidden(4, True)
        # RUHIGERE OPTIK (Nutzer: "weniger Excel-tabellenmaessig"): keine
        # Zebrastreifen, weichere Trennlinien und mehr Zeilenabstand. Der
        # Baum soll wie eine Gliederung wirken, nicht wie ein Datenblatt.
        tw.setAlternatingRowColors(False)
        tw.setRootIsDecorated(True)
        tw.setIndentation(22)
        tw.setUniformRowHeights(True)
        # KEINE eigene Hintergrundfarbe setzen: mit `background:transparent`
        # schien der dunkle Fensterhintergrund durch, und der Baum wirkte
        # deutlich dunkler als vorher (Nutzer: "den helleren Hintergrund
        # fand ich besser"). Ohne die Angabe greift wieder das globale
        # App-Stylesheet. Die uebrigen Beruhigungen bleiben.
        tw.setStyleSheet(
            "QTreeWidget{border:none; outline:none; font-size:13px;}"
            "QTreeWidget::item{padding:4px 2px; "
            "border-bottom:1px solid rgba(255,255,255,0.04);}"
            f"QHeaderView::section{{border:none; "
            f"border-bottom:1px solid {theme.BORDER}; padding:6px 2px; "
            f"color:{theme.MUTED}; font-size:11px;}}")
        tw.header().setStretchLastSection(False)
        # Nur noch drei sichtbare Spalten -> mehr Platz fuer den Namen.
        self._make_tree_movable(tw, [560, 110, 260, 130, 140])
        tw.setContextMenuPolicy(Qt.CustomContextMenu)
        # Mehrere Zeilen auswaehlbar - fuer "Rechtsklick -> Blacklist"
        # (Nutzer-Wunsch). Tippen und Namen abgleichen entfaellt damit
        # komplett; genau daran war die Blacklist vorher gescheitert.
        tw.setSelectionMode(QTreeWidget.ExtendedSelection)
        # Dieselbe Absicherung wie beim Runplaner: Qt überschreibt sonst die
        # eigene Blau/Grau-Einfärbung (bauen/kaufen) beim Selektieren einer Zeile.
        from PySide6.QtGui import QPalette as _QPalette2
        _twp = tw.palette()
        _twp.setColor(_QPalette2.HighlightedText, _twp.color(_QPalette2.Text))
        tw.setPalette(_twp)

        def _on_tree_check(item, _col):
            struck = item.checkState(0) == Qt.Checked
            f = item.font(0); f.setStrikeOut(struck)
            for c in range(tw.columnCount()):
                item.setFont(c, f)
        tw.itemChanged.connect(_on_tree_check)
        from PySide6.QtWidgets import QTabWidget, QTableWidget, QTableWidgetItem
        # WARNZEILE UEBER DEN TABS (Nutzer, Sitzung 19). Bewusst HIER und
        # nicht in einem Tab: welche Struktur fehlt, haengt am Inhalt des
        # Plans - ein T2-Schiff braucht womoeglich Refinery, Invention und
        # Fertigung. In der Rezeptstruktur waere die Warnung weg, sobald
        # jemand auf Materialien oder Runplaner wechselt, und genau dort
        # stehen die Zahlen, die zu guenstig sind. Fuer Reaktionen gibt es
        # ausserdem gar keinen eigenen Tab.
        try:
            _fehlt_st = self._fehlende_bau_strukturen(
                tree, type_id,
                getattr(self._bd_recipes, "reaction_products", None) or set(),
                getattr(self, "_bd_reaction_stages", None), _is_invented)
        except Exception:
            _fehlt_st = []
        if _fehlt_st:
            _lbl_map = dict(self._STRUCT_ACTIVITIES)
            _namen = ", ".join(_txt(_lbl_map.get(_k, _k)) for _k, _kr in _fehlt_st)
            _kritisch = any(_kr for _k, _kr in _fehlt_st)
            # PUNKT D (Sitzung 20): "Index 0" stimmt nur, wenn wirklich keiner
            # gefunden wurde. Ist einer GELIEHEN - aus einem anderen System,
            # weil dieser Stufe keine Struktur zugewiesen ist -, dann ist die
            # Zahl plausibel und die Herkunft falsch. Das ist die gefaehrlichere
            # Lage, also wird sie benannt statt mit "0" verwechselt.
            _geliehen = getattr(self, "_bd_index_geliehen", None) or {}
            _gl = [(_k, _geliehen[_k]) for _k, _kr in _fehlt_st if _k in _geliehen]
            _warn_lbl = QLabel()
            _warn_lbl.setWordWrap(True)
            if _kritisch:
                # Reaktionen ohne Refinery sind in EVE nicht bloss unbekannt,
                # sondern unmoeglich - das darf nicht wie ein Schoenheits-
                # fehler aussehen.
                _warn_lbl.setText(_txt(
                    "\u26a0 No structure for: {stages}. Reactions REQUIRE a "
                    "refinery with a reactor module \u2013 they cannot run in an "
                    "NPC station at all. Job fees are calculated with system "
                    "cost index 0, so the profit shown here is too high."
                ).format(stages=_namen))
                _warn_lbl.setStyleSheet(
                    f"color:{theme.RED}; font-weight:700; padding:6px 8px;")
            else:
                _warn_lbl.setText(_txt(
                    "\u26a0 No structure for: {stages}. Job fees are calculated "
                    "with system cost index 0, so the profit shown here is too "
                    "high. Add a structure or an NPC station under "
                    "Setup \u2192 Structures."
                ).format(stages=_namen))
                _warn_lbl.setStyleSheet(
                    f"color:{theme.AMBER}; font-weight:700; padding:6px 8px;")
            if _gl:
                # NICHT statt der Warnung, sondern DAZU: die fehlende Struktur
                # bleibt das Problem, die geliehene Zahl erklaert nur, warum
                # die Job-Kosten trotzdem plausibel aussehen.
                _gl_txt = ", ".join(
                    "{a}: {v:.2f} % ({s})".format(
                        a=_txt(_lbl_map.get(_k, _k)), v=_w * 100.0, s=_s)
                    for _k, (_w, _s) in _gl)
                _warn_lbl.setText(_warn_lbl.text() + " " + _txt(
                    "The cost index is not 0 here but BORROWED from another "
                    "system \u2013 {liste}. The number looks plausible, its "
                    "origin is wrong."
                ).format(liste=_gl_txt))
            v.addWidget(_warn_lbl)
        _tabs = QTabWidget()
        # Eigene, deutlich fettere Tab-Optik nur für dieses Dialog-Herzstück (Rezept-
        # Struktur/Bau-Reihenfolge/Runplaner) - größer + kräftiger als die generische
        # QTabBar-Optik aus theme.py, damit die drei Ansichten sofort als DIE zentrale
        # Navigation des Bauplans erkennbar sind.
        _tabs.setStyleSheet(
            f"QTabWidget::pane {{ border: 1px solid {theme.BORDER}; top: -1px; "
            f"background: {theme.BG}; }}"
            f"QTabBar::tab {{ background: {theme.PANEL2}; color: {theme.MUTED}; "
            f"padding: 13px 28px; font-size: 15px; font-weight: 700; "
            f"border: 1px solid {theme.BORDER}; border-bottom: none; "
            f"border-top-left-radius: 8px; border-top-right-radius: 8px; "
            f"margin-right: 4px; }}"
            f"QTabBar::tab:selected {{ background: {theme.CYAN_FILL}; color: {theme.CYAN}; "
            f"font-weight: 800; border: 1px solid {theme.CYAN}; }}"
            f"QTabBar::tab:hover {{ color: {theme.TEXT}; }}")
        struct_w = QWidget()
        struct_v = QVBoxLayout(struct_w)
        struct_v.setContentsMargins(0, 0, 0, 0); struct_v.setSpacing(6)
        tw_toolbar = QHBoxLayout()
        tw_expcol_btn = QPushButton(_txt("\u229e Expand all"))
        tw_expcol_btn.setToolTip(_txt("Expand/collapse all levels in the recipe structure."))
        tw_expcol_btn.setCheckable(True)
        tw_expcol_btn.setMaximumWidth(120)

        def _tw_toggle_expand(checked):
            tw_expcol_btn.setText(_txt("\u229f Collapse all") if checked else _txt("\u229e Expand all"))
            (tw.expandAll if checked else tw.collapseAll)()
        tw_expcol_btn.toggled.connect(_tw_toggle_expand)
        tw_toolbar.addWidget(tw_expcol_btn)
        tw_toolbar.addStretch()
        struct_v.addLayout(tw_toolbar)
        struct_h = QHBoxLayout()
        struct_h.setContentsMargins(0, 0, 0, 0); struct_h.setSpacing(8)
        struct_h.addWidget(tw, 1)
        struct_v.addLayout(struct_h, 1)
        _rightcol = QWidget()
        _rcv = QVBoxLayout(_rightcol)
        _rcv.setContentsMargins(0, 0, 0, 0); _rcv.setSpacing(8)
        # "Bau-Strategie": alle drei Bauen/Kaufen-Entscheidungs-Schalter in EINER
        # Sektion, einheitlicher Checkbox-Stil, keine sichtbaren Erklärtexte mehr
        # (stehen nur noch als Tooltip - spart Platz, jeder Schalter hat schon
        # eine ausführliche Erklärung beim Draufhalten).
        _strat_panel = QWidget()
        _spv = QVBoxLayout(_strat_panel)
        _spv.setContentsMargins(10, 4, 6, 4); _spv.setSpacing(6)
        _spv.addWidget(fbtn)
        _spv.addWidget(pbtn)
        _spv.addWidget(asset_cb)
        _spv.addWidget(stock_scope_cb)
        _spv.addWidget(asset_age_lbl)
        # Nutzer-Vorgabe: k\u00fcrzere Titel und standardm\u00e4ssig EINGEKLAPPT.
        # Die Seitenleiste war ein Block aus vier dauerhaft offenen Panels -
        # man scrollte an Einstellungen vorbei, die man selten anfasst.
        # REIHENFOLGE nach dem Arbeitsablauf (Nutzer-Vorgabe): erst die
        # Grundentscheidung, dann die Tiefe, dann die Feinheiten. Alles
        # EINGEKLAPPT beim Oeffnen - man sucht sich gezielt, was man braucht,
        # statt an vier offenen Panels vorbeizuscrollen.
        # AN self MERKEN (Sitzung 17): das Tutorial zeigt auf diese Karte.
        self._bd_karte_bauenkaufen = self._collapsible(
            _txt("Build or buy?"),
            _strat_panel, expanded=True, accent=theme.CYAN)
        _rcv.addWidget(self._bd_karte_bauenkaufen)   # Nutzer, Sitzung 17: standard offen
        # AN self MERKEN (18.09.2026): das Tutorial laesst beide Karten blinken.
        self._bd_karte_tiefe = self._collapsible(
            _txt("Production depth"),   # ohne Zahnrad (Nutzer, Sitzung 17)
            self._build_depth_panel(), expanded=True, accent=theme.AMBER,   # standard offen
            tip=_txt("From which stage of the chain do you build yourself? Sets the "
                     "category ticks below \u2013 a shortcut, not a second setting."))
        _rcv.addWidget(self._bd_karte_tiefe)
        # REPROCESSING (1.0.9, Weg B; Nutzer 17./18.09.2026): Compressed Ore
        # statt Minerale kaufen, wenn es am Hub guenstiger ist. Opt-in -
        # Standard aus und eingeklappt, ohne Schalter aendert sich nichts am
        # Plan. Zweite Frage: WO wird reprocesst (Struktur bestimmt Basis).
        _rp_panel = QWidget()
        _rpv = QVBoxLayout(_rp_panel)
        _rpv.setContentsMargins(10, 4, 6, 4); _rpv.setSpacing(6)
        rp_cb = _QCheckBox(_txt("Buy compressed ore instead of minerals"))
        rp_cb.setIcon(icons.icon("package"))
        rp_cb.setToolTip(_txt(
            "Buys compressed ore instead of a mineral when the ore is cheaper \u2013 "
            "with your yield (structure, rig, skills). By-products count as far as "
            "the plan needs them. Batches of 100.\nNeeds: hub scan + \u201eLoad skills\u201c."))
        rp_cb.setChecked(bool(self.settings.get("bau_reprocess_on")))
        _rpv.addWidget(rp_cb)
        # WEG A (Nutzer 19.09.2026: "erraten und einfuegen"): Unrefined-
        # Reaktionen, wo sie je Stueck guenstiger sind als normale Reaktion
        # und Kauf. Die Ausbeute-Annahme (Skills ohne Erz-Skill) ist noch
        # nicht gemessen - das steht sichtbar dabei, bis die Vorschau da ist.
        ru_cb = _QCheckBox(_txt("Use unrefined reactions where cheaper"))
        ru_cb.setIcon(icons.icon("package"))
        ru_cb.setToolTip(_txt(
            "Builds intermediates via their \u201eUnrefined \u2026 Reaction Formula\u201c "
            "when that is cheaper per unit than the normal reaction or buying.\n"
            "Yield: 50 % \u00d7 Scrapmetal Processing. The returned input is credited "
            "but stays on the shopping list.\nNeeds: hub scan + \u201eLoad skills\u201c."))
        ru_cb.setChecked(bool(self.settings.get("bau_unrefined_on")))
        _rpv.addWidget(ru_cb)
        ru_lbl = QLabel(""); ru_lbl.setObjectName("Muted"); ru_lbl.setWordWrap(True)
        ru_lbl.setStyleSheet("font-size:11px;")
        _rpv.addWidget(ru_lbl)
        _rp_row = QHBoxLayout()
        _rp_row.setSpacing(6)
        _rp_at = QLabel(_txt("Reprocess at")); _rp_at.setObjectName("Muted")
        _rp_row.addWidget(_rp_at)
        rp_struct_cb = QComboBox()
        for _s_rp in (self.settings.get("bau_structures", []) or []):
            rp_struct_cb.addItem(" " + str(_s_rp.get("name") or _s_rp.get("id")),
                                 _s_rp.get("id"))
        rp_struct_cb.addItem(" " + _txt("NPC station (50 %)"), "npc")
        _ix_rp = rp_struct_cb.findData(self._reprocess_struktur().get("id"))
        rp_struct_cb.setCurrentIndex(_ix_rp if _ix_rp >= 0 else rp_struct_cb.count() - 1)
        rp_struct_cb.setToolTip(_txt(
            "Where the ore is reprocessed. Refineries (Athanor/Tatara) get their "
            "bonus and reprocessing rig from the structure list; an NPC station "
            "has a flat 50 % base."))
        rp_struct_cb.setEnabled(rp_cb.isChecked() or ru_cb.isChecked())
        _rp_row.addWidget(rp_struct_cb, 1)
        _rpv.addLayout(_rp_row)
        rp_lbl = QLabel(""); rp_lbl.setObjectName("Muted"); rp_lbl.setWordWrap(True)
        rp_lbl.setStyleSheet("font-size:11px;")
        _rpv.addWidget(rp_lbl)
        # IMPLANTATE (Nutzer 18.09.2026): Knopf + Zeile direkt unter der
        # Struktur. Erkennung per ESI gegen die SDE-Tabelle, Ergebnis geht in
        # Ausbeute und Charakterwahl ein.
        _rp_imp_row = QHBoxLayout()
        _rp_imp_row.setSpacing(6)
        rp_imp_btn = QPushButton(" " + _txt("Load implants"))
        rp_imp_btn.setIcon(icons.icon("trend_up"))
        rp_imp_btn.setStyleSheet("padding:4px 10px; font-size:11px;")
        rp_imp_btn.setToolTip(_txt(
            "Detects the reprocessing implants (Zainou 'Beancounter' Reprocessing "
            "RX-801/802/804) of all linked characters via ESI. Needs the implant "
            "scope (Settings \u2192 \u201eImplant manufacturing bonus\u201c \u2192 On + "
            "relink). The bonus goes into the yield and the character choice."))
        _rp_imp_row.addWidget(rp_imp_btn)
        rp_imp_lbl = QLabel(""); rp_imp_lbl.setObjectName("Muted"); rp_imp_lbl.setWordWrap(True)
        rp_imp_lbl.setStyleSheet("font-size:11px;")
        _rp_imp_row.addWidget(rp_imp_lbl, 1)
        _rpv.addLayout(_rp_imp_row)

        def _rp_imp_lbl_refresh():
            _tx = self._reprocess_implants_text()
            rp_imp_lbl.setText(_tx if _tx else _txt("no reprocessing implant detected"))
        _rp_imp_lbl_refresh()

        def _rp_lbl_refresh():
            _ro = self._reprocess_opts()
            if not _ro:
                rp_lbl.setText("")
                rp_lbl.setStyleSheet("font-size:11px;")
                return
            if _ro.get("basis") is None:
                if not _ro.get("on"):
                    rp_lbl.setText("")          # nur Weg A: Struktur ohne Belang
                    rp_lbl.setStyleSheet("font-size:11px;")
                    return
                rp_lbl.setText("\u26a0 " + _txt(
                    "No reprocessing data for this structure – run "
                    "„Load recipes“ once (Setup)."))
                rp_lbl.setStyleSheet(f"font-size:11px; color:{theme.AMBER};")
                return
            _inf = _ro.get("info") or {}
            _teile = [str(_ro.get("struct") or "")]
            if _inf.get("rig"):
                _teile.append(str(_inf["rig"]).replace("Standup ", ""))
            rp_lbl.setText(_txt("Structure base {pct} %").format(
                pct=f"{float(_ro['basis']) * 100.0:.1f}") + " \u00b7 " + " \u00b7 ".join(
                _x for _x in _teile if _x))
            rp_lbl.setStyleSheet("font-size:11px;")
        _rp_lbl_refresh()

        def _rp_karte_nachziehen(_plan):
            """Ergebnis-Zeilen in der Karte (Nutzer 19.09.2026: der Textblock
            ueber der Materialliste war "komisch und ueberladen"): Weg B -
            Ersparnis und Anzahl Erze; Weg A - wie viele Zwischenmaterialien
            den Unrefined-Weg gehen, "warum nicht" im Tooltip."""
            _rpp = (_plan or {}).get("reprocess") or {}
            _sch = _rpp.get("schritte") or []
            _erz = [_s for _s in _sch if _s.get("art") != "unrefined"]
            _unr = [_s for _s in _sch if _s.get("art") == "unrefined"]
            _rp_lbl_refresh()
            if rp_cb.isChecked() and _rpp.get("basis") is not None:
                if _erz:
                    _z = "\u267b " + _txt("saves {isk} \u00b7 {n} ores").format(
                        isk=isk(_rpp.get("ersparnis") or 0.0), n=len(_erz))
                    if _rpp.get("mit_fracht"):
                        _z += " \u00b7 " + _txt("incl. freight")
                elif _rpp.get("erz_on"):
                    _z = "\u267b " + _txt("no compressed ore is cheaper")
                else:
                    _z = ""
                if _z:
                    rp_lbl.setText((rp_lbl.text() + "\n" if rp_lbl.text() else "") + _z)
            _ru_lbl_refresh()
            if ru_cb.isChecked():
                _abg = _rpp.get("unrefined_abgelehnt") or {}
                if _unr:
                    ru_lbl.setText(ru_lbl.text() + "\n\u267b " + _txt(
                        "{n} intermediates via unrefined reaction").format(n=len(_unr)))
                elif _rpp.get("unrefined_on"):
                    ru_lbl.setText(ru_lbl.text() + "\n\u267b " + _txt(
                        "no unrefined reaction is cheaper"))
                if _abg:
                    ru_lbl.setToolTip(_txt("Unrefined reaction not cheaper for: {liste}").format(
                        liste=", ".join(
                            "{m} ({pct} %)".format(m=str(names.get(_m) or _m),
                                                   pct=f"{float(_e['aufpreis_pct']):+.0f}")
                            for _m, _e in sorted(_abg.items())
                            if _e.get("aufpreis_pct") is not None)))
                else:
                    ru_lbl.setToolTip("")
        self._bd_rp_karte_nachziehen = _rp_karte_nachziehen

        def _rp_namen_nachziehen():
            # `kandidaten()` erkennt komprimierte Erze am NAMEN. Wurde der
            # Schalter erst im offenen Dialog gesetzt, sind die Erz-Namen
            # noch nicht aufgeloest - einmal nachziehen (ESI cacht sie).
            try:
                _oids = self._reprocess_erz_ids(self._bd_pricemap.get)
                _fehlt = [_i for _i in _oids if _i not in names]
                if _fehlt:
                    names.update(esi.resolve_names(_fehlt))
            except Exception as _ne:
                self._log_exception("Reprocessing: Erz-Namen", str(_ne))

        def _rp_opts_setzen():
            _ro = self._reprocess_opts()
            if _ro:
                self._bd_opts["reprocess"] = _ro
            else:
                self._bd_opts.pop("reprocess", None)
            _rp_lbl_refresh()

        def _rp_imp_fertig():
            _rp_imp_lbl_refresh()
            if rp_cb.isChecked() or ru_cb.isChecked():
                _rp_opts_setzen()
                rebuild()
        rp_imp_btn.clicked.connect(lambda: self._load_reproc_implants(_rp_imp_fertig))
        self._bd_reprocess_imp_btn = rp_imp_btn
        self._bd_reprocess_imp_lbl = rp_imp_lbl

        def _rp_toggle(checked=False):
            self.settings["bau_reprocess_on"] = bool(checked)
            config.save_settings(self.settings)
            rp_struct_cb.setEnabled(bool(checked) or ru_cb.isChecked())
            if checked:
                _rp_namen_nachziehen()
            _rp_opts_setzen()
            rebuild()
            _rp_ladder_nachziehen()
        rp_cb.clicked.connect(_rp_toggle)

        def _rp_ladder_nachziehen():
            # NACH DEM SCHALTER DIE ORDERBUCH-PREISE NACHHOLEN (Nutzer
            # 19.09.2026: "ich moechte nicht Recalculate druecken"). Die
            # Einkaufsliste aendert sich mit dem Schalter grundlegend (Erz
            # statt Minerale, andere Inputs) - die gecachten Buecher kennen
            # die neuen Positionen nicht. Nur wenn es schon Orderbuch-Preise
            # gibt (sonst rechnet der Plan ohnehin mit Flachpreisen, wie
            # jeder andere Schalter auch) und der Plan nicht eingefroren ist.
            if (self._bd_ladder_ctx(qty_spin.value()) is not None
                    and not getattr(self, "_bd_frozen", None)):
                try:
                    _ladder_refresh()
                except Exception as _lr:
                    self._log_exception("Reprocessing: Orderbuch nach Schalter", str(_lr))

        def _ru_lbl_refresh():
            # SCRAPMETAL-PFAD (gemessen 19.09.2026): 50 % x Scrapmetal Processing
            # des besten Charakters - die Struktur oben spielt hier keine Rolle.
            if not ru_cb.isChecked():
                ru_lbl.setText("")
                return
            _cid_s, _f_s = industry.bester_scrap_char(
                self.settings.get("bau_char_skills", {}) or {},
                industry.reprocess_skill_ids())
            if _f_s is None:
                ru_lbl.setText(_txt("Unrefined: 50 % \u00d7 Scrapmetal Processing \u2013 "
                                    "no skills loaded"))
                return
            _nm_s = {int(_ch["character_id"]): (_ch.get("character_name")
                                                or str(_ch["character_id"]))
                     for _ch in store.list_characters()}.get(_cid_s, str(_cid_s))
            ru_lbl.setText(_txt("Unrefined: {pct} % \u00b7 {char} (50 % \u00d7 Scrapmetal "
                                "Processing, structure does not apply)").format(
                pct=f"{industry.scrap_ausbeute(_f_s) * 100.0:.1f}", char=_nm_s))

        def _ru_toggle(checked=False):
            self.settings["bau_unrefined_on"] = bool(checked)
            config.save_settings(self.settings)
            rp_struct_cb.setEnabled(bool(checked) or rp_cb.isChecked())
            _ru_lbl_refresh()
            _rp_opts_setzen()
            rebuild()
            _rp_ladder_nachziehen()
        ru_cb.clicked.connect(_ru_toggle)
        _ru_lbl_refresh()
        self._bd_unrefined_cb = ru_cb
        self._bd_unrefined_lbl = ru_lbl

        def _rp_struct_changed(_i=0):
            self.settings["bau_reprocess_struct"] = rp_struct_cb.currentData()
            config.save_settings(self.settings)
            if rp_cb.isChecked() or ru_cb.isChecked():
                _rp_opts_setzen()
                rebuild()
        rp_struct_cb.currentIndexChanged.connect(_rp_struct_changed)
        self._bd_reprocess_cb = rp_cb
        self._bd_reprocess_struct_cb = rp_struct_cb
        self._bd_reprocess_lbl = rp_lbl
        _rcv.addWidget(self._collapsible(
            _txt("Reprocessing"), _rp_panel,
            expanded=True, accent=theme.AMBER))   # Nutzer 27.09.2026: offen
        # DIREKT UNTER PRODUCTION DEPTH (Nutzer 18.09.2026: "schieb das
        # bitte hoeher, da wo man es sieht"). STANDARD JETZT OFFEN (Nutzer
        # 27.09.2026: "im Bauplan den Reprocessing ausklappen als Standard" -
        # frueher, 26.09., hatte er es zu gewuenscht).
        # BLACKLIST DIREKT UNTER DIE FERTIGUNGSTIEFE (Nutzer, Sitzung 20).
        # Beide beantworten "was soll gar nicht erst im Plan auftauchen" -
        # die Fertigungstiefe grob nach Stufe, die Blacklist nach Gruppe und
        # Name. Die Blaupausen-Frage darunter ist die feinste Stufe.
        _rcv.addWidget(self._collapsible(
            _txt("Blacklist"),
            # STANDARD OFFEN (Nutzer, Sitzung 20) - die Gruppen-Haekchen sind
            # eine Einstellung, die man beim Planen sehen will, keine, die man
            # sucht.
            self._build_blacklist_compact(), expanded=True, accent=theme.AMBER))
        # TITEL SAGT, WAS DIE HAEKCHEN TUN (Nutzer, Sitzung 20: "Categories
        # sagt zu wenig ueber die Funktionalitaet aus ... eher: habe ich
        # Blueprints oder muss ich kaufen"). Die Karte ist die feine Fassung
        # der "Fertigungstiefe" darueber: je Kategorie entscheidet sie, ob das
        # Werkzeug annehmen darf, dass du selbst baust.
        # Die zwei Invention-Haken sind HIER RAUS und stehen im
        # Invention-Reiter, direkt unter ihrer Mengenrechnung - eine Karte,
        # eine Frage.
        _rcv.addWidget(self._collapsible(
            _txt("Do I have the blueprints?"),
            self._build_bp_ownership_panel(with_head=False),
            expanded=False, accent=theme.CYAN))
        _rcv.addStretch()
        # EINHEITLICHE BREITE aller drei Bauplan-Seitenleisten (Nutzer:
        # "einheitliches Layout bitte ueberall"). Vorher: Rezept-Struktur 380,
        # Runplaner 600, Blueprints 340 - dieselben Klapp-Karten sahen dadurch
        # in jedem Tab anders aus. Die App-Navigation links (sidebar 196,
        # rail 210) bleibt unberuehrt, das ist ein anderer Zweck.
        _rightcol.setFixedWidth(380)
        # In eine QScrollArea packen: vorher zwang die volle gestapelte Höhe
        # aller 4 aufgeklappten Panels (Assets/Inventions/Blueprints/Blacklist)
        # das ganze Bauplan-Fenster zu einer Mindesthöhe, die man nicht
        # unterschreiten konnte, selbst mit dlg.setMinimumSize() niedriger
        # gesetzt - Qt nimmt das Maximum aus beidem. Jetzt kann die rechte
        # Spalte bei wenig Platz einfach scrollen statt das Fenster aufzuzwingen.
        _rightcol_scroll = QScrollArea()
        _rightcol_scroll.setWidgetResizable(True)
        _rightcol_scroll.setFrameShape(QFrame.NoFrame)
        _rightcol_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        _rightcol_scroll.setMinimumHeight(120)
        _rightcol_scroll.setWidget(_rightcol)
        _rightcol_scroll.setFixedWidth(380)
        struct_h.addWidget(_rightcol_scroll)
        tab_icon(_tabs, struct_w, _txt("Recipe structure"), "blueprint")
        # "Bau-Reihenfolge" als eigener Tab ist raus (war redundant zum
        # Runplaner - der zeigt dieselbe Bau-Reihenfolge, nur zusätzlich mit
        # Charakter-Zuteilung. Die eine wirklich einzigartige Info dort war die
        # "Überschuss"-Spalte - die steht jetzt im Runplaner selbst). bo_tree
        # bleibt als (nie angezeigtes) Objekt bestehen, weil die bestehende
        # Füll-Logik weiter unten in rebuild() noch darauf zugreift - so bleibt
        # diese tief verschachtelte Stelle unangetastet, statt sie herauszureißen
        # und ein neues Risiko einzugehen.
        bo_tree = QTreeWidget(); bo_tree.setColumnCount(4)
        bo_tree.setEditTriggers(QTreeWidget.NoEditTriggers)
        bo_tree.setHeaderLabels([_txt("Build (category / component)"), "Runs",
                                 _txt("Units"), _txt("Surplus")])
        # ⏱ Runplaner-Tab (Char → Item → Runs, aus dem aktuellen Plan)
        sched_w = QWidget(); sched_v = QVBoxLayout(sched_w)
        sched_v.setContentsMargins(4, 6, 4, 4)
        # Diese Zeile ist eine AUFFORDERUNG, kein Dauertext - _fill_bauplan_schedule
        # ersetzt sie, sobald Charaktere da sind. Bleibt daher stehen.
        sched_hdr = QLabel(_txt("Tick build characters in the setup + \u201eLoad skills\u201c."))
        sched_hdr.setWordWrap(True); sched_hdr.setStyleSheet("font-weight:600;")
        sched_v.addWidget(sched_hdr)
        sched_sub = QLabel(""); sched_sub.setObjectName("Muted"); sched_sub.setWordWrap(True)
        sched_v.addWidget(sched_sub)
        sched_bp_warn = QLabel(""); sched_bp_warn.setWordWrap(True)
        sched_bp_warn.setVisible(False)
        sched_v.addWidget(sched_bp_warn)
        # --- Pro-Bauplan-Einstellungen: Blaupausen-Kopien \u00d7 Runs je Stufe ----------
        # Kompakt gestapelt statt 7-spaltiges Grid -- passt in die schmale Sidebar
        # und lässt sich einklappen, wenn man die Tabs (die eigentliche Stärke des
        # Tools) mehr Höhe geben will.
        from PySide6.QtWidgets import (QSpinBox as _SB, QCheckBox as _CB)
        if getattr(self, "_bd_bp", None) is None:
            # Endprodukt: braucht es Invention? Dann übernimmt die Invention-
            # Tab-Logik weiter unten die genaue Ableitung (Erfolge × Runs/BPC).
            # Braucht es KEINE Invention (T1, direkt gebaut), nehmen wir einfach
            # BPO/unbegrenzt an - Vereinfachung, damit man nicht erst angeben
            # muss, ob man die Blaupause hat, um bauen zu können.
            _end_needs_inv = False
            try:
                _bp0 = self._bd_recipes.product_to_bp.get(type_id) if getattr(
                    self, "_bd_recipes", None) else None
                if _bp0:
                    _end_needs_inv = bool(self._bd_recipes.invention_for_bpc.get(_bp0[0]))
            except Exception:
                pass
            self._bd_bp = {
                "end": ({"copies": 1, "runs": 1, "bpo": False} if _end_needs_inv
                       else (self._bd_lookup_owned_bp_for_item(type_id)
                             or {"copies": 999999, "runs": 1, "bpo": True})),
                # Komponenten/Reaktionen: Fallback für Items OHNE ESI-Daten
                # (unbegrenzt angenommen, wie bisher) - für Items MIT
                # ESI-Daten zählt eh die genaue Pro-Item-Zahl (per_item_cap),
                # nicht dieser Wert.
                "component": {"copies": 1, "runs": 1, "bpo": True},
                "reaction": {"copies": 1, "runs": 1, "bpo": True},
                "manual": False}
        bpcard = QWidget()
        _bg = QVBoxLayout(bpcard); _bg.setContentsMargins(0, 2, 0, 2); _bg.setSpacing(6)
        self._bd_bp_widgets = {}

        def _refill_schedule(*_a):
            self._fill_bauplan_schedule(plan_ref.get("plan"), res["names"], type_id,
                                        qty_spin.value(), sched_hdr, sched_sub, sched_tree,
                                        bp_tbl=bp_tab_tbl, bp_warn_lbl=sched_bp_warn)
        _stage_colors = {"end": theme.AMBER, "component": theme.BLUE,
                         "reaction": theme.VIOLET}
        # Ohne Emoji (Sitzung 16): die Farbe links unterscheidet die Stufen
        # bereits, ein zweites Signal braucht es nicht.
        for _key, _lab in (("end", _txt("End product")),
                           ("component", _txt("Components")),
                           ("reaction", _txt("Reactions"))):
            blk = QFrame()
            blk.setStyleSheet(
                f"QFrame{{background:{theme.PANEL2}; "
                f"border:1px solid {theme.BORDER}; border-radius:6px;}}")
            bv = QVBoxLayout(blk); bv.setContentsMargins(8, 7, 8, 7); bv.setSpacing(5)
            lbl = QLabel(_lab)
            lbl.setStyleSheet(f"color:{_stage_colors[_key]}; font-weight:800; "
                              f"font-size:15px;")
            bv.addWidget(lbl)
            # Reine Anzeige, nicht mehr editierbar - Endprodukt kommt automatisch
            # aus der Invention-Erfolgschance (falls nötig) oder wird als BPO
            # angenommen; Komponenten/Reaktionen kommen aus "🛰 Alles aus ESI
            # laden" oben (pro Item genau, siehe Blueprints-Tab), Items ohne
            # eigene Blaupause werden dabei als unbegrenzt verfügbar angenommen
            # (du kaufst/kopierst sie eben) statt den Plan zu blockieren.
            info_lbl = QLabel(""); info_lbl.setWordWrap(True)
            info_lbl.setStyleSheet(f"color:{theme.TEXT}; font-size:13px;")
            bv.addWidget(info_lbl)
            status_lbl = QLabel(""); status_lbl.setWordWrap(True)
            status_lbl.setContentsMargins(0, 2, 0, 2)
            status_lbl.setStyleSheet(
                f"color:{theme.GREEN}; font-size:11px; line-height:150%; padding:2px 0;")
            bv.addWidget(status_lbl)
            capl = QLabel(""); capl.setObjectName("Muted"); capl.setStyleSheet("font-size:11px;")
            bv.addWidget(capl)
            self._bd_bp_widgets[_key] = {"info_lbl": info_lbl, "status_lbl": status_lbl,
                                         "cap": capl}
            _bg.addWidget(blk)
        self._bd_refresh_bp_stage_info()   # Labels initial befüllen
        manual_cb = _CB(_txt("Split myself (no char)"))
        manual_cb.setChecked(bool(self._bd_bp.get("manual")))
        manual_cb.setToolTip(_txt("On = just list all runs per item, without character assignment."))
        manual_cb.toggled.connect(lambda v: (self._bd_bp.__setitem__("manual", bool(v)),
                                             _refill_schedule()))
        _bg.addWidget(manual_cb)
        # t("Blueprints per stage") und "Andere Blaupausen" wandern jetzt in den
        # Blueprints-Tab (mehr Platz für die Haupt-Tabs) - hier nur bauen,
        # eingehängt wird weiter unten bei der Blueprints-Tab-Konstruktion.
        _bp_stage_collapsible = self._collapsible(
            _txt("Blueprints per stage"), bpcard, expanded=False, accent=theme.MUTED,
            tip=_txt("Copies \u00d7 runs per stage (end product/components/reactions) "
                     "\u2013 for this build plan only, remembered with \u201eSave build "
                     "plan\u201c."))
        # Bau-Charaktere direkt im Runplaner (wer baut/reagiert). Änderung → Plan neu füllen.
        self._char_roles_on_change = _refill_schedule
        # AUFGEKLAPPT (Nutzer, Sitzung 16). Nicht nur Geschmack: bei einer
        # frischen Installation ist KEIN Rollen-Haken gesetzt. Zugeklappt
        # sieht der Nutzer nicht, dass er noch niemanden zugeteilt hat -
        # der Runplaner bleibt leer und die Ursache unsichtbar.
        _char_roles_collapsible = self._collapsible(
            " " + _txt("Build characters"),
            self._build_char_roles_widget(), expanded=True, accent=theme.GREEN)
        sched_tree = QTreeWidget(); sched_tree.setColumnCount(6)
        sched_tree.setEditTriggers(QTreeWidget.NoEditTriggers)
        sched_tree.setHeaderLabels([_txt("Character / item / material"), "Runs", _txt("Blueprints"),
                                    _txt("Time"), _txt("Stage"), _txt("Surplus")])
        sched_tree.setAlternatingRowColors(True)
        sched_tree.header().setStretchLastSection(False)
        self._make_tree_movable(sched_tree, [430, 90, 280, 130, 210, 100])
        sched_tree.header().setStretchLastSection(True)   # Überschuss füllt Restbreite
        # NAME ANKLICKBAR, ABER OHNE JEDE HERVORHEBUNG (Nutzer, 15.09.2026
        # nach dem Ausprobieren: "die Items sollen wieder normal aussehen").
        # Ein Rahmen und spaeter ein Chip waren beide zu laut - die Zeile
        # sieht jetzt aus wie immer, nur der Klick kopiert.
        sched_tree.itemClicked.connect(self._sched_name_klick)
        sched_tree.headerItem().setTextAlignment(1, Qt.AlignCenter)   # Runs-Header mittig
        sched_tree.headerItem().setTextAlignment(5, Qt.AlignCenter)
        sched_tree.headerItem().setToolTip(
            5, _txt("Reactions often automatically produce more than exactly needed "
                    "(fixed batch size) - shows how much is left over that you can keep "
                    "for the next build plan instead of wasting it."))
        # Luftigeres Aussehen (weniger „Excel“): mehr Zeilenhöhe, keine harten
        # vertikalen Gitterlinien, dezente Auswahl. Hintergrund im Panel-Ton
        # (nicht transparent -> sonst scheint der schwarze Fensterhintergrund durch).
        # WICHTIG: "selection-background-color" statt einer "::item:selected {...}"-
        # Selektor-Regel - Letzteres zwingt Qt in einen kompletten eigenen Mal-Modus
        # für selektierte Zeilen, der die Palette-basierte Farb-Erhaltung unten
        # (HighlightedText = Text) komplett ignoriert. Die spezielle
        # "selection-background-color"-Eigenschaft mappt dagegen direkt auf die
        # Palette (Highlight-Rolle) und lässt die eigene Zeilenfarbe in Ruhe.
        sched_tree.setStyleSheet(
            f"QTreeWidget {{ border:none; background:{theme.PANEL2}; "
            f"selection-background-color:rgba(70,224,200,0.15); }}"
            f"QTreeWidget::item {{ padding:5px 4px; }}")
        # Qt überschreibt beim Selektieren einer Zeile sonst die eigene Textfarbe
        # (z.B. das Orange für "mehrere Blaupausen nötig" oder das Violett für
        # "läuft laut ESI schon") mit der Palette-Farbe für markierten Text.
        # Explizit auf dieselbe Farbe wie normaler Text setzen, damit eigene
        # Zeilenfarben auch bei angeklickten/markierten Zeilen sichtbar bleiben.
        from PySide6.QtGui import QPalette as _QPalette
        _sp = sched_tree.palette()
        _sp.setColor(_QPalette.HighlightedText, _sp.color(_QPalette.Text))
        _sp.setColor(_QPalette.Inactive, _QPalette.HighlightedText, _sp.color(_QPalette.Text))
        sched_tree.setPalette(_sp)
        sched_tree.setIndentation(18)
        sched_tree.headerItem().setToolTip(
            4, _txt("Reaction stage (stage 1 \u2192 goes into a further reaction, stage 2 "
                    "\u2192 goes into the build) + material type (Composite/Intermediate/"
                    "...). The material type matches the checkbox under \u201eMy "
                    "blueprints\u201c in the recipe structure tab. No tick there = bought "
                    "instead of built."))

        # ENTPRELLTES SPEICHERN (Nutzer: "Abhaken dauert 5-8 Sekunden, in
        # der Zeit geht nichts"): der alte Handler formatierte 6 Spalten -
        # JEDE setFont/setForeground-Aenderung feuerte itemChanged erneut,
        # der Handler lief also zigfach rekursiv pro Klick, und jeder
        # Durchlauf schrieb die KOMPLETTEN Settings synchron auf Platte
        # (gross seit eingefrorenen Preisen + Reservierungs-Maps). Jetzt:
        # Formatierung unter blockSignals (feuert nichts), gespeichert wird
        # EINMAL, 400 ms nach dem letzten Klick (Timer haengt am Baum und
        # stirbt mit dem Dialog; der Timeout schreibt nur Settings - kein
        # UI-Rebuild, Regel 13 bleibt gewahrt).
        _sched_save_timer = QTimer(sched_tree)
        _sched_save_timer.setSingleShot(True)
        _sched_save_timer.setInterval(400)

        def _sched_save_now():
            pid = getattr(self, "_bd_open_plan_id", None)
            if pid is None:
                return
            cset = getattr(self, "_bd_runplan_checked", None) or set()
            for p in (self.settings.get("bau_saved_plans", []) or []):
                if p.get("id") == pid:
                    p["checked_runplan"] = list(cset)
                    # ZEITSTEMPEL MITSICHERN (Sitzung 10): ohne sie waere die
                    # mitlaufende Reservierung beim naechsten Oeffnen wieder
                    # ohne Grundlage - sie braucht je Haken den Zeitpunkt, um
                    # ihn gegen das Alter des ESI-Bestands zu halten. Nur die
                    # Stempel zu Haken sichern, die es noch gibt: sonst
                    # wuechse die Karte mit jedem Setzen-und-Loesen weiter.
                    _tsm = getattr(self, "_bd_runplan_ts", None) or {}
                    p["checked_runplan_ts"] = {str(k): float(v)
                                               for k, v in _tsm.items()
                                               if k in cset}
                    # ... und die erledigten Runs je Item, die eine
                    # Umverteilung ueberleben (s. `_runplan_erledigt_pflegen`).
                    _erl = getattr(self, "_bd_runplan_erledigt", None) or {}
                    p["checked_runplan_runs"] = {str(k): int(v)
                                                 for k, v in _erl.items()
                                                 if int(v or 0) > 0}
                    config.save_settings(self.settings)
                    break
        _sched_save_timer.timeout.connect(_sched_save_now)

        def _fmt_struck(item, struck):
            for c in range(sched_tree.columnCount()):
                f = item.font(c); f.setStrikeOut(struck); item.setFont(c, f)
                if struck:
                    if item.data(c, Qt.UserRole + 5) is None:
                        # ganze QBrush merken (kennt auch die „Standardfarbe“)
                        item.setData(c, Qt.UserRole + 5, item.foreground(c))
                    item.setForeground(c, QColor(theme.GREEN))
                else:
                    orig = item.data(c, Qt.UserRole + 5)
                    if orig is not None:
                        item.setForeground(c, orig)   # Original-Brush zurück

        def _on_sched_check(item, _col):
            if _col != 0:
                return                     # nur die Checkbox-Spalte zaehlt
            struck = item.checkState(0) == Qt.Checked
            sched_tree.blockSignals(True)
            try:
                _fmt_struck(item, struck)
            finally:
                sched_tree.blockSignals(False)
            # Häkchen = "Job schon ingame gestartet" - automatisch im gerade
            # geöffneten gespeicherten Bauplan sichern (NUR für diesen Plan, kein
            # globaler Zustand), damit er beim nächsten Öffnen noch da ist. Ohne
            # gespeicherten Plan (frisch geöffnetes Item) gibt's nichts, wohin
            # gespeichert werden könnte - dann bleibt es nur für diese Sitzung.
            key = item.data(0, Qt.UserRole + 6)
            if key is not None:
                cset = getattr(self, "_bd_runplan_checked", None)
                if cset is None:
                    cset = set(); self._bd_runplan_checked = cset
                # ZEITSTEMPEL JE HAKEN (Sitzung 10): die mitlaufende
                # Reservierung darf die Zutaten eines abgehakten Runs erst
                # freigeben, wenn ESI den Verbrauch auch gesehen hat - sonst
                # gibt der Plan sie frei, waehrend der Hangar-Stand sie noch
                # als vorhanden meldet, und niemand beansprucht sie mehr
                # (Nutzer: "so schnell gehts nicht, die ESI aktualisiert nur
                # alle Stunde"). Ohne den Stempel gaebe es dafuer keine
                # Grundlage. Beim Abhaken RAUS, damit ein versehentlich
                # gesetzter und wieder geloester Haken nichts nachwirkt.
                _tsmap = getattr(self, "_bd_runplan_ts", None)
                if _tsmap is None:
                    _tsmap = {}; self._bd_runplan_ts = _tsmap
                if struck:
                    cset.add(key)
                    _tsmap[key] = _time_mod.time()
                else:
                    cset.discard(key)
                    _tsmap.pop(key, None)
                # ERLEDIGTE RUNS JE ITEM MITFUEHREN (Nutzer-Befund
                # 24.09.2026: "ich habe mit Peanut Motor Runs gemacht und
                # abgehakt, danach Charaktere ausgewechselt und Apply
                # gedrueckt - nun sind die abgehakten Runs verschwunden").
                # Der Haken-Schluessel traegt die Charakter-ID; nach einer
                # Umverteilung zeigt er ins Leere. Was er wirklich gemeint
                # hat, ist "so viele Runs dieses Items habe ich gestartet" -
                # und das gilt unabhaengig davon, wer sie faehrt.
                self._runplan_erledigt_pflegen(key, struck)
                _sched_save_timer.start()   # entprellt: einmal am Ende
            # KINDER MITZIEHEN (Nutzer: "hake ich Peanut Motor ab, soll
            # Titanium Carbide darunter automatisch mit abgehakt werden"):
            # jedes abhakbare Kind bekommt denselben Zustand. setCheckState
            # feuert je Kind EIN itemChanged (Spalte 0) - das laeuft durch
            # DIESEN Handler und erledigt Formatierung, cset und (entprellt)
            # das Speichern; tiefere Ebenen ziehen dadurch rekursiv mit.
            # NUR ZEILEN, DIE SCHON EIN KAESTCHEN HABEN (Nutzer, 15.09.2026):
            # `checkState(0)` liefert auch fuer eine Zeile OHNE Kaestchen
            # brav "Unchecked", und Qt.ItemIsUserCheckable steht in den
            # Standard-Flags jedes QTreeWidgetItem. Beides zusammen hiess:
            # die Kaskade hat den Material-Unterzeilen ein Kaestchen
            # ANGELEGT, statt nur ein vorhandenes umzuschalten - der Haken,
            # den er nie gesetzt hat und nicht wegbekam. CheckStateRole ist
            # die ehrliche Frage: "gibt es hier ueberhaupt etwas zu haken?"
            _want = Qt.Checked if struck else Qt.Unchecked
            for _ci in range(item.childCount()):
                _ch = item.child(_ci)
                if (_ch.data(0, Qt.CheckStateRole) is not None
                        and _ch.flags() & Qt.ItemIsUserCheckable
                        and _ch.checkState(0) != _want):
                    _ch.setCheckState(0, _want)
        sched_tree.itemChanged.connect(_on_sched_check)

        def _sched_klapp_merken(item, offen):
            """Welche Charakterzeilen offen sind - AM FENSTER gemerkt, nicht
            am Baum (Nutzer 24.09.2026: "dann laedt es auch keine Runs" - der
            Neuaufbau klappte alles wieder zu, und die Runs stehen darunter.
            Beim Neuaufbau ist der alte Baum schon leer, also muss der Stand
            woanders liegen).

            Gemerkt wird NUR, was der Nutzer selbst getan hat: waehrend des
            Neuaufbaus sind die Signale des Baums abgeschaltet
            (`tbl.blockSignals`), die Vorgaben landen also nicht hier. Es ist
            ein Woerterbuch und keine Menge, weil beide Richtungen zaehlen -
            eine fertige Stufe klappt ihre Charakterzeilen von sich aus AUF,
            und wer sie zuklappt, will sie zu haben."""
            _k = item.data(0, Qt.UserRole + 6)
            if not _k:
                return
            _m = getattr(self, "_bd_sched_klapp", None)
            if _m is None:
                _m = {}; self._bd_sched_klapp = _m
            _m[str(_k)] = bool(offen)
        sched_tree.itemExpanded.connect(
            lambda _it: _sched_klapp_merken(_it, True))
        sched_tree.itemCollapsed.connect(
            lambda _it: _sched_klapp_merken(_it, False))
        self._sched_tree_ref = sched_tree

        # --- Blueprint-Namen kopieren (CTRL+C / Rechtsklick) ---------------------
        # In EVE heißt der Blueprint "<Item> Blueprint" (Fertigung) bzw.
        # "<Item> Reaction Formula" (Reaktion). So kann man ingame schnell filtern.
        def _bp_name_for(item):
            # Daten VOR Anzeigetext: der Text traegt Schmuck ("ESI 2/4",
            # Status-Punkte), der Nutzer will den suchbaren NAMEN. Das
            # Regex-Netz faengt Baeume, die vor der Daten-Rettung gefuellt
            # wurden (eingefrorene Plaene). `re` LOKAL importieren -
            # main_window hat KEINEN Modul-Import dafuer, und weil dieser
            # Zweig nur beim Kopieren laeuft, haette keine Suite den
            # NameError je ausgeloest.
            import re
            base = str(item.data(0, Qt.UserRole + 8) or item.text(0)).strip()
            # Die frueheren Marken vorn (\U0001F7E3 laeuft / \u2705 fertig) sind
            # seit Sitzung 16 raus; \u2705 setzt der Runplaner noch. Beide
            # abschneiden, falls doch eine dransteht - der Blueprint-Name
            # muss sauber ins Clipboard.
            if base[:1] in ("\U0001F7E3", "\u2705"):
                base = base[1:].strip()
            base = re.sub(r"\s+\u00b7\s+ESI \d+/\d+$", "", base).strip()
            if not base:
                return ""
            act = item.data(0, Qt.UserRole + 7)   # gemerkte Aktivität (11=Reaktion)
            if act == industry.REACTION:
                return f"{base} Reaction Formula"
            return f"{base} Blueprint"

        def _copy_bp_names():
            names_out = []
            for it in sched_tree.selectedItems():
                nm = _bp_name_for(it)
                if nm:
                    names_out.append(nm)
            if not names_out:
                return
            from PySide6.QtWidgets import QApplication as _QA
            _QA.clipboard().setText("\n".join(names_out))
            self._flash_tip(_txt("Blueprint name copied: {name}").format(
                                name=names_out[0])
                            + (f" (+{len(names_out) - 1})" if len(names_out) > 1 else ""))

        def _sched_key(ev):
            from PySide6.QtGui import QKeySequence
            if ev.matches(QKeySequence.Copy):
                _copy_bp_names()
                return
            QTreeWidget.keyPressEvent(sched_tree, ev)
        sched_tree.keyPressEvent = _sched_key
        sched_tree.setContextMenuPolicy(Qt.CustomContextMenu)

        def _sched_menu(pos):
            it = sched_tree.itemAt(pos)
            if it is None:
                return
            from PySide6.QtWidgets import QMenu
            m = QMenu(sched_tree)
            a_bp = m.addAction(icons.icon("clipboard"), _txt("Copy blueprint name"))
            a_bp.triggered.connect(_copy_bp_names)
            # ALLE auf einmal (Nutzer, Sitzung 9: "ich will da alle
            # blueprints per kopieren ins clipboard bekommen um ingame
            # schneller zu finden"). NUR echte Item-Zeilen: Stufen-Koepfe
            # und Charakter-Zeilen tragen keine Aktivitaet (UserRole+7) -
            # ohne den Filter stuende "Peanut Motor Blueprint" in der Liste.
            a_alle = m.addAction(icons.icon("clipboard"), _txt("Copy all blueprint names"))

            def _copy_all_bp_names():
                from PySide6.QtWidgets import (QApplication as _QA,
                                               QTreeWidgetItemIterator)
                seen, out = set(), []
                _sti = QTreeWidgetItemIterator(sched_tree)
                while _sti.value():
                    _it9 = _sti.value()
                    if _it9.data(0, Qt.UserRole + 7) is not None:
                        nm = _bp_name_for(_it9)
                        if nm and nm not in seen:
                            seen.add(nm)
                            out.append(nm)
                    _sti += 1
                if out:
                    _QA.clipboard().setText("\n".join(out))
                    self._flash_tip(
                        _txt("{n} blueprint names copied \u2013 one line per "
                             "blueprint.").format(n=len(out)))
            a_alle.triggered.connect(_copy_all_bp_names)
            m.exec(sched_tree.viewport().mapToGlobal(pos))
        sched_tree.customContextMenuRequested.connect(_sched_menu)

        sched_toolbar = QHBoxLayout()
        sched_expcol_btn = QPushButton(_txt("\u229e Expand all"))
        sched_expcol_btn.setToolTip(_txt("Expand/collapse all levels in the run planner."))
        sched_expcol_btn.setCheckable(True)
        sched_expcol_btn.setMaximumWidth(120)

        def _sched_toggle_expand(checked):
            sched_expcol_btn.setText(_txt("\u229f Collapse all") if checked else _txt("\u229e Expand all"))
            (sched_tree.expandAll if checked else sched_tree.collapseAll)()
        sched_expcol_btn.toggled.connect(_sched_toggle_expand)
        sched_toolbar.addWidget(sched_expcol_btn)
        # ZIELZEIT FUER ALLE STUFEN (Nutzer 24.09.2026: "abends einloggen,
        # Runs starten auf 23 h, am naechsten Tag Components"). Hier steht die
        # VORGABE; jede Stufenzeile darf davon abweichen (eigenes Feld in der
        # Runs-Spalte). Diese Auswahl setzt die Vorgabe und nimmt die
        # Ausnahmen weg - sonst waehlte man oben etwas, und unten bliebe eine
        # Stufe stumm bei ihrem alten Wert stehen.
        sched_toolbar.addSpacing(18)
        _zl_lbl = QLabel(_txt("Target per stage:"))
        _zl_lbl.setObjectName("Muted")
        sched_toolbar.addWidget(_zl_lbl)
        _zl_cb = QComboBox()
        _zl_cb.setToolTip(_txt(
            "How long may a stage run? The planner then uses as few "
            "blueprints and slots as fit into that time – a stage is "
            "finished only when its longest job is, so the shorter ones may "
            "be stretched for free. Each stage can be set separately in its "
            "own row below."))
        for _hz in (0, 8, 12, 16, 20, 23, 24, 36, 48, 72, 168, -1):
            _zl_cb.addItem(self._runplan_ziel_text(_hz), _hz)
        _iz = _zl_cb.findData(int(self.settings.get("bau_runplan_ziel_std", 0) or 0))
        _zl_cb.setCurrentIndex(max(0, _iz))
        _zl_cb.currentIndexChanged.connect(
            lambda *_a, _c=_zl_cb: self._runplan_ziel_alle_gewaehlt(_c.currentData()))
        sched_toolbar.addWidget(_zl_cb)
        self._bd_ziel_box = _zl_cb
        sched_toolbar.addStretch()
        # OFFENE ZUORDNUNGEN (Stufe C, Teil 2, Nutzer-Entscheid 24.09.2026:
        # "einmal fragen, gesammelt im Runplaner"). Bewusst KEIN Dialog beim
        # Oeffnen: die Frage ist wichtig, aber nie so dringend, dass sie
        # einem den Bauplan vor die Nase stellen darf. Der Knopf ist weg,
        # solange es nichts zu fragen gibt.
        _jf_btn = QPushButton("")
        _jf_btn.setCursor(Qt.PointingHandCursor)
        _jf_btn.setStyleSheet(
            f"QPushButton{{background:{theme.PANEL2}; "
            f"border:1px solid {theme.AMBER_DIM}; color:{theme.AMBER}; "
            f"border-radius:5px; padding:3px 12px; font-weight:700;}}"
            f"QPushButton:hover{{border-color:{theme.AMBER}; "
            f"background:{theme.PANEL};}}")
        _jf_btn.clicked.connect(lambda: self._job_frage_dialog())
        _jf_btn.hide()
        sched_toolbar.addWidget(_jf_btn)
        self._bd_jobfrage_btn = _jf_btn
        sched_v.addLayout(sched_toolbar)
        sched_v.addWidget(sched_tree, 1)
        sched_main_w = QWidget()
        sched_main_v = QVBoxLayout(sched_main_w)
        sched_main_v.setContentsMargins(0, 0, 0, 0); sched_main_v.setSpacing(0)
        sched_main_v.addWidget(sched_w)
        sched_side_w = QWidget(); sched_side_w.setFixedWidth(380)   # s. _BD_SIDE_W
        sched_side_v = QVBoxLayout(sched_side_w)
        sched_side_v.setContentsMargins(4, 6, 0, 4)
        sched_side_scroll = QScrollArea(); sched_side_scroll.setWidgetResizable(True)
        sched_side_scroll.setFrameShape(QFrame.NoFrame)
        sched_side_inner = QWidget()
        sched_side_inner_v = QVBoxLayout(sched_side_inner)
        sched_side_inner_v.setContentsMargins(0, 0, 0, 0)
        sched_side_inner_v.addWidget(_char_roles_collapsible)
        sched_side_inner_v.addStretch()
        sched_side_scroll.setWidget(sched_side_inner)
        sched_side_v.addWidget(sched_side_scroll)
        sched_split_w = QWidget()
        sched_split = QHBoxLayout(sched_split_w)
        sched_split.setContentsMargins(0, 0, 0, 0); sched_split.setSpacing(8)
        sched_split.addWidget(sched_main_w, 1)
        sched_split.addWidget(sched_side_w)
        tab_icon(_tabs, sched_split_w, _txt("Run planner"), "clock")



        # ---- \U0001F4CB Blueprints-Tab: welche Blaupausen brauche ich, wie viele
        # Kopien für minimale Wellenzahl, und was besitze ich laut ESI? ----------
        bp_tab_w = QWidget()
        bp_tab_body = QHBoxLayout(bp_tab_w)
        bp_tab_body.setContentsMargins(0, 0, 0, 0); bp_tab_body.setSpacing(8)
        bp_tab_main_w = QWidget(); bp_tab_v = QVBoxLayout(bp_tab_main_w)
        bp_tab_v.setContentsMargins(4, 6, 4, 4); bp_tab_v.setSpacing(6)
        # Nutzer-Linie: kurze Zeile, Details in den Tooltip. Vorher stand
        # hier ein Vier-Zeilen-Absatz, der bei jedem Blick im Weg war.
        # Zeile "Alle Blaupausen der Kette - unabhaengig davon, ob der Plan
        # das Material kauft oder baut" ENTFERNT (Nutzer). Sie war seit der
        # Fertigungstiefe-Aenderung ausserdem SACHLICH FALSCH: der Tab folgt
        # jetzt `never_build`, zeigt also genau die Blaupausen, die der Plan
        # auch wirklich braucht.
        # Die Erklaerungen zu den Spalten ("Empf. Kopien", "Besitze") wandern
        # in die Spalten-Tooltips der Tabelle, wo sie hingehoeren.
        bp_tab_row = QHBoxLayout()
        # Der einzelne Knopf wurde entfernt (Übersichtlichkeit) - "🛰 Alles aus
        # ESI laden" oben im Dialog stößt "_load_bp_ownership()" jetzt
        # automatisch mit an. Das Button-Objekt bleibt (nur nicht sichtbar),
        # weil die Funktion intern dessen enabled-Status umschaltet.
        bp_own_btn = QPushButton(_txt("Load ESI ownership"))
        bp_own_btn.setIcon(icons.icon("link"))
        bp_own_btn.setToolTip(_txt(
            "Fetches across all linked characters which original "
              "blueprints (BPO) you own and how many."))
        bp_tab_status = QLabel(""); bp_tab_status.setObjectName("Muted")
        bp_tab_row.addWidget(bp_tab_status, 1)
        bp_tab_v.addLayout(bp_tab_row)
        bp_tab_tbl = QTableWidget()
        bp_tab_tbl.setColumnCount(7)
        bp_tab_tbl.setHorizontalHeaderLabels(
            ["Blueprint", _txt("Stage"), _txt("Total runs"), _txt("Max runs/job"),
             _txt("Rec. copies"), _txt("Owned (BPO/BPC)"), _txt("Status")])
        # Spalten-Tooltips statt Kopfzeilen-Absatz: die Erklaerung steht dort,
        # wo die Zahl steht, und nur wenn man sie braucht.
        for _c, _tip in enumerate([
                _txt("All blueprints this plan needs at the configured production "
                     "depth."),
                _txt("Reaction stage or component/end product."),
                _txt("Total runs for the current build plan quantity."),
                _txt("How many runs a single job can hold at most."),
                _txt("Minimum number of waves with a fully researched BPO and "
                     "unlimited runs, capped at your free job slots."),
                _txt("Live per ESI: own BPOs (unlimited) and BPCs (limited runs, "
                     "checked against the need)."),
                _txt("Is what you own enough for this plan?")]):
            _hi = bp_tab_tbl.horizontalHeaderItem(_c)
            if _hi is not None:
                _hi.setToolTip(_tip)
        # RUHIGERE OPTIK wie beim Rezept-Baum (Nutzer): kein Gitter, keine
        # Zeilennummern links, proportionale statt Monospace-Schrift, weiche
        # Trennlinien. Die Item-Icons uebernehmen die Orientierung, die
        # vorher die Nummernspalte leisten musste.
        bp_tab_tbl.setShowGrid(False)
        bp_tab_tbl.verticalHeader().setVisible(False)
        bp_tab_tbl.setAlternatingRowColors(False)
        bp_tab_tbl.setIconSize(QSize(22, 22))
        bp_tab_tbl.setStyleSheet(
            "QTableWidget{{border:none; outline:none; font-size:13px;}}"
            "QTableWidget::item{{padding:5px 4px; "
            "border-bottom:1px solid rgba(255,255,255,0.04);}}"
            f"QHeaderView::section{{{{border:none; "
            f"border-bottom:1px solid {theme.BORDER}; padding:6px 4px; "
            f"color:{theme.MUTED}; font-size:11px;}}}}")
        bp_tab_tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        bp_tab_tbl.setSortingEnabled(True)
        bp_tab_v.addWidget(bp_tab_tbl, 1)
        self._bd_bp_tab_tbl = bp_tab_tbl
        self._bd_bp_owned_counts = getattr(self, "_bd_bp_owned_counts", None)
        # t("Blueprints per stage") (Zusammenfassung: Endprodukt/Komponenten/
        # Reaktionen) und "Andere Blaupausen" (ME/TE-Einstellungen) in eine
        # schmale, scrollbare Sidebar rechts - damit die eigentliche
        # Blaupausen-LISTE (die Haupt-Sache hier) die volle Höhe bekommt,
        # ohne dass man erst daran vorbeiscrollen muss.
        bp_tab_side_w = QWidget(); bp_tab_side_w.setFixedWidth(380)  # s. _BD_SIDE_W
        bp_tab_side_v = QVBoxLayout(bp_tab_side_w)
        bp_tab_side_v.setContentsMargins(4, 6, 0, 4)
        bp_tab_side_scroll = QScrollArea(); bp_tab_side_scroll.setWidgetResizable(True)
        bp_tab_side_scroll.setFrameShape(QFrame.NoFrame)
        bp_tab_side_inner = QWidget()
        bp_tab_side_inner_v = QVBoxLayout(bp_tab_side_inner)
        bp_tab_side_inner_v.setContentsMargins(0, 0, 0, 0); bp_tab_side_inner_v.setSpacing(8)
        # "BUY MISSING BLUEPRINTS" (Nutzer 26.09.2026: "in der rechten
        # Sidebar einen funktionablen Button -> Buy Missing Blueprints, dann
        # werden die fehlenden Blueprints ins Clipboard kopiert, so dass man
        # sie ingame ins Multibuy-Fenster einfuegen kann. Dazu zaehlen nicht
        # die T2-Blueprint-Copys, die man erforschen muss").
        _bp_kauf_btn = QPushButton(_txt("Buy Missing Blueprints"))
        _bp_kauf_btn.setIcon(icons.icon("cart"))
        _bp_kauf_btn.setMinimumHeight(34)
        _bp_kauf_btn.setToolTip(_txt(
            "Copies every blueprint of this plan that you own neither as an "
            "original nor as a copy \u2013 one original each, in EVE multibuy "
            "format. Make copies from it yourself for parallel jobs. Invented T2 "
            "copies are left out (they cannot be bought)."))
        # WIE "CREATE SHOPPING LIST" (Nutzer 26.09.2026): nur Rahmen und
        # Text amber, Flaeche des Themas.
        _bp_kauf_btn.setStyleSheet(theme.amber_rahmen_knopf())
        _bp_kauf_btn.clicked.connect(lambda: self._bp_fehlende_kopieren())
        self._bd_bp_kauf_btn = _bp_kauf_btn          # b-Suite
        _bp_kauf_lbl = QLabel("")
        _bp_kauf_lbl.setWordWrap(True)
        self._bd_bp_kauf_lbl = _bp_kauf_lbl
        bp_tab_side_inner_v.addWidget(_bp_kauf_btn)
        bp_tab_side_inner_v.addWidget(_bp_kauf_lbl)
        _bp_kauf_lbl.hide()
        bp_tab_side_inner_v.addWidget(_bp_stage_collapsible)
        bp_tab_side_inner_v.addWidget(andere_bp_card)
        bp_tab_side_inner_v.addStretch()
        bp_tab_side_scroll.setWidget(bp_tab_side_inner)
        bp_tab_side_v.addWidget(bp_tab_side_scroll)
        bp_tab_body.addWidget(bp_tab_main_w, 1)
        bp_tab_body.addWidget(bp_tab_side_w)

        def _apply_bp_ownership(owned_bp):
            """Verarbeitet eine BEREITS geholte Blaupausen-Liste (gemeinsamer
            ESI-Cache) zu BPO-Zählungen UND BPC-Runs für die Blueprints-Tab-
            Tabelle - kein eigener ESI-Abruf mehr (früher: zweiter kompletter
            Abruf parallel zum zentralen "Alles aus ESI laden", jetzt: eine
            einzige Quelle). BPC-Runs werden SEPARAT erfasst (nicht mehr
            komplett ignoriert wie vorher) - eine BPC mit 15 Runs bedeutet
            nicht "fehlt komplett", auch wenn keine BPO vorhanden ist."""
            counts = {}       # bp_id -> Anzahl BPO (unbegrenzt nutzbar)
            bpc_runs = {}     # bp_id -> Summe verbleibender Runs über alle eigenen BPCs
            # WIEVIELE LIEGEN WOANDERS (Punkt C, Sitzung 20)? Die location_id
            # kam schon immer mit, wurde aber nie ausgewertet - deshalb stand
            # "enough" auch dann da, wenn die Kopie 30 Spruenge entfernt liegt.
            # Gezaehlt wird je Blaupausen-Typ, NICHT gefiltert und NICHT rot
            # gefaerbt (Nutzer-Entscheid: sonst wird der Reiter bei vielen
            # komplett rot, weil BPO woanders liegen als kopiert wird).
            anderswo = {}     # bp_id -> Anzahl Stueck ausserhalb der Bau-Strukturen
            _bau_orte = self._bau_plan_struct_ids()
            # NUR WAS BEWEISBAR WOANDERS LIEGT (Nutzer-Befund mit Screenshot,
            # Sitzung 20): liegt eine Blaupause in einem CONTAINER ("00 Amarr
            # Builder Pack", "BP COPY T1"), ist ihre `location_id` die ID des
            # CONTAINERS - nicht die der Struktur. Die erste Fassung hielt das
            # fuer "woanders" und schrieb den Hinweis an JEDE Zeile, obwohl
            # alles am richtigen Ort lag.
            # Deshalb: gezaehlt wird nur, wenn der Ort eine der EIGENEN
            # verknuepften Strukturen ist - dann ist er bekannt und die Aussage
            # belegt. Alles andere (Container, fremde Station, unbekannt) wird
            # NICHT gezaehlt. Lieber schweigen als etwas Falsches behaupten.
            _bekannt = set()
            for _bs in (self.settings.get("bau_structures") or []):
                _lsid = _bs.get("link_structure_id")
                if _lsid:
                    _bekannt.add(int(_lsid))
            for b in owned_bp:
                tid = b.get("type_id")
                if not tid:
                    continue
                if b.get("is_bpo"):
                    counts[tid] = counts.get(tid, 0) + int(b.get("quantity", 1) or 1)
                else:
                    qty = int(b.get("quantity", 1) or 1)
                    runs = int(b.get("runs", 0) or 0)
                    bpc_runs[tid] = bpc_runs.get(tid, 0) + qty * runs
                # OHNE verknuepfte Bau-Struktur wird NICHTS gezaehlt: dann ist
                # "anderswo" keine Aussage, sondern eine Behauptung.
                if _bau_orte:
                    _loc = b.get("location_id")
                    _loc = int(_loc) if _loc else None
                    if _loc is not None and _loc in _bekannt and _loc not in _bau_orte:
                        anderswo[tid] = anderswo.get(tid, 0) + int(
                            b.get("quantity", 1) or 1)
            self._bd_bp_elsewhere = anderswo
            self._bd_bp_owned_counts = counts
            self._bd_bp_owned_bpc_runs = bpc_runs
            # ERFOLGSMELDUNG WEG (Nutzer): "1148 BPO ueber 467 Blueprint-Typen
            # ..." beschreibt den GESAMTBESITZ, nicht diesen Plan - und blieb
            # danach dauerhaft stehen. Was fuer den Plan zaehlt, steht je Zeile
            # in der Spalte "Besitze". Lade- und Fehlermeldungen bleiben.
            bp_tab_status.setText("")
            _refill_schedule()   # Tabelle mit neuen Besitz-Daten neu füllen

        def _load_bp_ownership():
            # Eigenständiger Aufruf (z.B. falls diese Funktion je einzeln
            # gebraucht wird) - holt sich die Daten über denselben
            # gemeinsamen Cache wie "Alles aus ESI laden".
            from ..sprache import t as _txt   # `t` ist hier lokal belegt
            client_id = self.settings.get("client_id")
            chars = store.list_characters()
            if not client_id or not chars:
                bp_tab_status.setText(_txt("No characters / client ID linked."))
                return
            bp_own_btn.setEnabled(False)
            bp_tab_status.setText(_txt("Loading ESI blueprint ownership \u2026"))

            def job():
                return self._bd_fetch_all_owned_blueprints(force=True)

            def done(owned_bp):
                bp_own_btn.setEnabled(True)
                _apply_bp_ownership(owned_bp)
            self._run(Worker(job), done, label=_txt("ESI blueprint ownership \u2026"),
                      overlay=False)
        bp_own_btn.clicked.connect(_load_bp_ownership)
        # TAB-REIHENFOLGE FOLGT DEM ARBEITSABLAUF (Nutzer):
        #   Rezept-Struktur -> Invention -> Blueprints -> Materialien -> Runplaner
        # "Rezept anschauen, dann Invention planen, dann Blueprints checken,
        # dann Materialien einkaufen, dann ingame mit dem Runplaner arbeiten."
        # Die drei insertTab-Aufrufe stehen im Code an verschiedenen Stellen
        # (jeder Tab wird dort gebaut, wo seine Daten entstehen) - deshalb
        # zaehlen die Indizes, nicht die Reihenfolge der Zeilen:
        #   Blueprints kommt als erster dazu und landet auf 1,
        #   Materialien schiebt sich auf 2, Invention davor auf 1.
        tab_icon_at(_tabs, 1, bp_tab_w, "Blueprints", "columns")

        # ---- \U0001F9F0 Materialien-Tab: alle tatsächlich einzukaufenden Rohstoffe
        # (Blaupausen/Komponenten stehen im "Blueprints"-Tab) mit ESI-Bestand +
        # Status, genau wie dort - nutzt dieselben Daten wie "📦 Assets abziehen"
        # oben, kein eigener ESI-Abruf nötig. ------------------------------------
        mat_tab_w = QWidget(); mat_tab_v = QVBoxLayout(mat_tab_w)
        mat_tab_v.setContentsMargins(4, 6, 4, 4); mat_tab_v.setSpacing(6)
        # Zeile "Rohstoffe, die eingekauft werden muessen. Details in den
        # Spalten-Tooltips." ENTFERNT (Nutzer): der Tab heisst "Materialien",
        # die Spalten heissen BENOETIGT/BESITZE/FEHLT - der Satz sagte nichts,
        # was die Tabelle nicht selbst zeigt.
        # DAS LABEL BLEIBT ABER: es trug zusaetzlich die EINGEFROREN-Warnung,
        # und die ist keine Erklaerung, sondern eine Zustandsinfo ueber die
        # gezeigten Zahlen. Jetzt standardmaessig unsichtbar und nur fuer
        # diese Warnung da (Testkette hat den Wegfall sofort gemeldet).
        mat_tab_info = QLabel("")
        mat_tab_info.setObjectName("Muted"); mat_tab_info.setWordWrap(True)
        mat_tab_info.setVisible(False)
        mat_tab_v.addWidget(mat_tab_info)
        mat_tab_toolbar = QHBoxLayout(); mat_tab_toolbar.setContentsMargins(0, 0, 0, 0)
        # "Einkaufsliste erstellen" (Nutzer) - der Knopf kopiert laengst nicht
        # mehr direkt, er oeffnet das Einkaufsfenster. Der alte Name versprach
        # das Falsche.
        # AN self MERKEN (Sitzung 17): das Tutorial laesst ihn blinken.
        mat_copy_btn = self._bd_mat_copy_btn = QPushButton(
            _txt("Create shopping list"))
        mat_copy_btn.setIcon(icons.icon("cart"))
        _rest_only_cb = QCheckBox(_txt("only what is still missing"))
        _rest_only_cb.setToolTip(_txt(
            "ON: only the material for the runs that are still OPEN \u2013 the "
            "list shrinks while you build (same calculation as \u201eCheck "
            "shortfall\u201c).\nOFF: the full plan quantity, as on the freeze "
            "day.\nWhat you have already built into the next stage is NOT "
            "bought again."))
        mat_copy_btn.setToolTip(_txt(
            "Copies ALL materials with their required total quantity "
              "to the clipboard, even when you already own them "
              "completely (format: item name + quantity per line) – "
              "sorted by category (Intermediate Reactions / Composite "
              "Reactions / components / minerals), just like in the "
              "run planner. Blacklisted items stay out (they were "
              "deliberately removed from the plan). The „# category“ "
              "lines are only for orientation – leave them out before "
              "pasting into EVE's multibuy if needed."))
        # Amber umrandet, ohne eigene Flaeche. ETWAS GROESSER (Nutzer
        # 26.09.2026) - 14 px Schrift, mehr Polster; derselbe Stil gilt fuer
        # "Buy Missing Blueprints" und beide "Best Decryptor"-Knoepfe
        # (theme.amber_rahmen_knopf, EINE Stelle).
        mat_copy_btn.setStyleSheet(theme.amber_rahmen_knopf())
        mat_copy_btn.setMinimumHeight(34)

        def _collect_materials():
            """Alle Materialien des Plans mit den ECHTEN Zahlen aus
            _fill_material_tab (self._bd_mat_rows) - NICHT aus den angezeigten
            Texten: die Tabelle kuerzt gross Zahlen ("5.53M"), daraus laesst
            sich nichts zurueckrechnen. EINE Sammelstelle fuer das
            Einkaufsfenster UND die Kopier-Knoepfe."""
            out = []
            for r in (getattr(self, "_bd_mat_rows", None) or []):
                _reason = r.get("reason") or ""
                out.append({
                    "name": r.get("name") or "",
                    # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                    "cat": r.get("category") or "Rohstoffe",
                    # de_scan4: an
                    # benoetigt = ALLES, was der Plan braucht (auch was aus dem
                    # Lager kommt oder selbst gebaut wird) - genau die Menge
                    # fuer "Alle Materialien kopieren".
                    "benoetigt": int(r.get("total", 0) or 0),
                    "besitze": int(r.get("owned", 0) or 0),
                    # fehlt = was wirklich eingekauft werden muss (plan["buy"]).
                    # de_scan4: aus - Dict-SCHLUESSEL (interne Materialzeile), nie sichtbar
                    "fehlt": int(r.get("missing", 0) or 0),
                    # de_scan4: an
                    "status": _reason,
                    # Blacklist = "hab ich schon, wird extern besorgt". Bleibt
                    # SICHTBAR (Nutzer will alles sehen), wandert aber nicht in
                    # die Kopie - dort waere es eine falsche Bestellung.
                    "kopierbar": "Blacklist" not in _reason})
            out.sort(key=lambda r: (r["cat"], r["name"]))
            return out

        def _materials_multibuy(rows, feld):
            """Multibuy-Text nach Kategorie sortiert. `feld` ist "benoetigt"
            oder "fehlt" - die Auswahl der Menge ist der EINZIGE Unterschied
            zwischen den beiden Kopier-Knoepfen."""
            _CAT_ORDER = ["Intermediate Reactions", "Composite Reactions",
                          # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                          "Komponenten", "Mineralien", "Mond-Materialien",
                          # de_scan4: an
                          # KEIN t() HIER: _CAT_ORDER ist eine SCHLUESSEL-Liste.
                          # Die Zeilen tragen ihre Kategorie als Datenwert
                          # (r["cat"]) - uebersetzt man den Schluessel, landen
                          # auf Englisch alle Huellen still in "Rohstoffe".
                          # de_scan2: aus  (Kategorie-SCHLUESSEL, Anzeige via _kategorie_anzeige)
                          "PI", "Tools", "H\u00fcllen", "Fuel", "Rohstoffe"]
                          # de_scan2: an
            by_cat = {c: [] for c in _CAT_ORDER}
            n = 0
            for r in rows:
                if not r["kopierbar"] or r[feld] <= 0:
                    continue
                by_cat.setdefault(
                    # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                    r["cat"] if r["cat"] in by_cat else "Rohstoffe",
                    # de_scan4: an
                    []).append(f"{r['name']}\t{r[feld]}")
                n += 1
            lines = []
            for cat in _CAT_ORDER:
                items = by_cat.get(cat) or []
                if not items:
                    continue
                if lines:
                    lines.append("")
                lines.append(f"# {cat}")
                lines.extend(items)
            return "\n".join(lines), n

        def _copy_materials():
            """EINKAUFSFENSTER DIREKT AUS DEM BAUPLAN (Nutzer: "ich will den
            Einkaufswagen ausserhalb des Bauplanes umgehen koennen").
            Benutzt DENSELBEN Dialog wie der Einkaufswagen
            (`_cart_conflict_filter`, copy_mode=True) statt einen zweiten mit
            gleichem Zweck danebenzustellen: Item-Bilder, Aufklappen nach
            Charakter ("wer hat was wo"), Ampelfarben und Sortierung sind dort
            schon drin - nachgebaut waeren sie eine zweite Wahrheit, die
            auseinanderlaufen kann.
            show_all=True, weil hier ALLE Materialien des Plans zu sehen sein
            sollen, nicht nur die mit Bestandskonflikt."""
            _rows = getattr(self, "_bd_mat_rows", None) or []
            # NUR DER RESTBEDARF (Nutzer, Sitzung 16): "die Einkaufsliste zeigt
            # absurd viele Materialien an, die ich gar nicht mehr brauche, weil
            # ich Teile davon schon hergebaut habe ... ich will ja nicht mehr
            # einkaufen als noetig."
            #
            # Der Plan-Bedarf (r["total"]) ist die VOLLE Menge fuer alle Runs.
            # Sobald Runs erledigt sind, ist er zu hoch: das Material steckt
            # laengst in der naechsten Stufe. Dieselbe Rechnung wie die
            # Fehlbedarfs-Pruefung (mw_helpers.restbedarf_map) - EINE Wahrheit,
            # sonst sagen Knopf und Pruefung wieder Verschiedenes.
            #
            # WICHTIG, und darum ein SCHALTER statt stiller Umstellung: der
            # eingefrorene Plan haelt die Einkaufsliste bewusst stabil
            # ("gekauft ist gekauft", Sitzung 13). Wer den Vollkauf will,
            # bekommt ihn weiter - der Haken sagt, was gerade gilt.
            _rest = {}
            if _rest_only_cb.isChecked():
                try:
                    _rest = self._restbedarf_jetzt() or {}
                except Exception:
                    _rest = {}          # kein Plan offen -> Vollmenge

            # WAS MUSS ICH NOCH KAUFEN? – EINE WAHRHEIT (Sitzung 16).
            #
            # NUTZER: "wenn ich dieser Einkaufsliste Glauben schenken wuerde
            # und das kaufen wuerde, koennte ich mir gar nicht meine
            # fehlenden Materialien zusammenbauen."
            #
            # ZWEI FEHLER DER ERSTEN FASSUNG, beide in die GEFAEHRLICHE
            # Richtung (zu wenig kaufen):
            #   1. sie zog `r["owned"]` ab - beim eingefrorenen Plan ist das
            #      `max(Einfrier-Stand, live)` und zeigt laengst Verbrauchtes
            #      weiter an (derselbe Mechanismus, der ihn 13'400 Thulium
            #      Hafnite gekostet hat).
            #   2. sie zog `built` ab - die VOLLE Planproduktion, nicht das
            #      schon Gebaute. Abgezogen wurde also Material, das erst
            #      entstehen muss.
            #
            # Jetzt dieselbe Rechnung wie "Werkzeuge -> Fehlbedarf pruefen":
            # `fehlbedarf_vorschau` rechnet gegen den ROHEN Live-Bestand und
            # zaehlt die Produktion der OFFENEN Runs mit. Wer die Liste
            # kauft, kann danach alle offenen Runs starten - das ist die
            # Zusage, und sie steht als aa275 in der Suite.
            _rest_fehlt = {}
            if _rest:
                try:
                    _rest_fehlt = {int(_m): int(_f)
                                   for _m, _f, *_r in (self._fehlbedarf_jetzt() or [])}
                except Exception:
                    _rest_fehlt = {}

            # ERFINDUNGSMATERIAL FAELLT SONST DURCH (Sitzung 17, Nutzer:
            # "ich habe nicht genuegend Datacores in den Einkaufswagen
            # bekommen, obwohl das Materials-Tab erkennt, dass ich zu wenige
            # habe"). GEMESSEN: `_fehlbedarf_jetzt` rechnet aus
            # plan["build_runs"]/["build_mats"] - reines FERTIGUNGS-Material.
            # Datacores/Decryptoren stehen bewusst in eigenen Feldern
            # (inv_buy/inv_stock_used), damit ihre Kosten nicht doppelt
            # zaehlen. Fuer sie lieferte _rest_fehlt also 0, und alles mit 0
            # fliegt unten aus der Liste. Ergebnis: sie fehlten still.
            # Fuer diese Zeilen zaehlt ihre EIGENE Fehlmenge (r["missing"]) -
            # sie haengt nicht an den offenen Runs, denn erfunden wird vorab.
            _inv_tids = set()
            try:
                _p_inv = (getattr(self, "_bd_plan_ref", None) or {}).get("plan") or {}
                _inv_tids = {int(_t) for _t in
                             (set(_p_inv.get("inv_buy") or {})
                              | set(_p_inv.get("inv_stock_used") or {}))}
            except Exception:
                _inv_tids = set()

            def _rest_kaufmenge(r):
                """Fehlmenge dieses Materials fuer die noch OFFENEN Runs."""
                _t = int(r["tid"])
                if _t in _inv_tids:
                    return int(r.get("missing", 0) or 0)
                return int(_rest_fehlt.get(_t, 0) or 0)

            def _menge(r):
                # OHNE HAKEN: der VOLLE Bedarf, aber OHNE die Stufen, die der
                # Plan selbst baut (Nutzer, Sitzung 17: "nur die
                # Grundmaterialien, alles weitere baue ich ja daraus").
                # `total = missing + used + built` - `built` ist die
                # Eigenproduktion. Ohne diesen Abzug kaufte die Liste die
                # Zwischenstufe UND ihre Rohstoffe, also doppelt.
                if _rest:
                    return _rest_kaufmenge(r)
                # Durch Reprocessing gedeckte Minerale werden wie Gebautes
                # NICHT gekauft - das Erz steht als eigene Zeile drin.
                return max(0, int(r.get("total", 0) or 0)
                           - int(r.get("built", 0) or 0)
                           - int(r.get("reprocessed", 0) or 0))

            _items = [(int(r["tid"]), r.get("name") or f"#{r['tid']}")
                      for r in _rows if _menge(r) > 0]
            if not _items:
                self._flash_tip(
                    _txt("Nothing left to buy \u2013 the remaining runs are covered.")
                    if _rest else
                    _txt("Nothing to copy - the materials tab is empty."),
                    ms=self.FLASH_LESEN_MS)     # lesbar lange (Nutzer 26.09.2026)
                return
            _needed = {int(r["tid"]): _menge(r) for r in _rows}
            # Zu kopierende Mengen kommen aus DEM PLAN (Materialien-Tab), nicht
            # aus der Bestandsrechnung des Dialogs - sonst zeigt das Fenster
            # die Plan-Zahlen und kopiert andere.
            # "vollkauf" = KOMPLETT-EINKAUF AN DER FERTIGUNGSGRENZE
            # (Nutzer: "alles kaufen, um selber zu reacten/Komponenten/
            # Endprodukt zu bauen - je nach eingestellter Fertigungsstufe"):
            # voller Bedarf OHNE Bestandsabzug, aber OHNE die Stufen, die
            # der Plan selbst baut (deren Rohstoffe stehen als eigene
            # Zeilen laengst in der Liste). total - built = missing + used.
            # Die Fertigungstiefe steckt bereits in der Bau-Entscheidung
            # des Plans - hier wird nichts zweites gerechnet.
            # WAS FEHLT JETZT WIRKLICH? (Nutzer-Entscheidung Sitzung 12)
            #
            # `r["missing"]` ist beim EINGEFRORENEN Plan die Kaufmenge vom
            # Einfrier-Tag - sie schrumpft nicht, waehrend gebaut wird.
            # Deshalb standen laengst gekaufte Mineralien wieder auf der
            # Liste ("warum sollte ich mehr einkaufen wollen, als ich
            # brauche?").
            #
            # EINFRIEREN SCHUETZT DIE PLANUNG, NICHT DIE EINKAUFSLISTE: sein
            # eigener Tooltip nennt Rezept-Struktur, Mengen, Runplaner und
            # Preise - "damit du tagelang am Runplaner arbeiten kannst".
            # Der Wagen darf also der Wirklichkeit folgen.
            #
            # BEIDE RICHTUNGEN stimmen damit: gebaut -> faellt raus;
            # verloren (Transport, zerstoert) -> taucht wieder auf UND wird
            # zusaetzlich als "war gedeckt" markiert, damit man den
            # Unterschied zu "hatte ich nie" sieht.
            try:
                _rest = {int(_x[0]): int(_x[1])
                         for _x in (self._fehlbedarf_jetzt() or [])}
                _rest_da = True
            except Exception:
                _rest, _rest_da = {}, False
            _cqty = {int(r["tid"]): {"need": int(r.get("total", 0) or 0),
                                     # Ohne Rest-Rechnung bleibt die
                                     # Plan-Menge stehen - lieber zu viel
                                     # anbieten als eine Luecke verschweigen.
                                     "missing": (_rest_kaufmenge(r)
                                                 if _rest_da
                                                 else int(r.get("missing", 0) or 0)),
                                     # built: fuer die Kopier-Modus-Ampel
                                     # ("gedeckt - wird gebaut" statt eines
                                     # irrefuehrenden "es fehlen X").
                                     "built": int(r.get("built", 0) or 0),
                                     "vollkauf": max(0,
                                         int(r.get("total", 0) or 0)
                                         - int(r.get("built", 0) or 0)
                                         - int(r.get("reprocessed", 0) or 0))}
                     for r in _rows}
            self._cart_conflict_filter(
                _items, needed=_needed,
                plan_stock=(getattr(self, "_bd_opts", None) or {}).get("stock"),
                show_all=True, copy_mode=True, copy_qty=_cqty)
        # SCHALTER: Restbedarf statt Vollmenge. Vorgabe AN - der Nutzer hat
        # den Vollkauf-Fall genau einmal (beim ersten Einkauf), den
        # Nachkauf-Fall bei jedem weiteren Blick.
        _rest_only_cb.setChecked(True)
        mat_copy_btn.clicked.connect(_copy_materials)
        # AUF-/ZUKLAPPEN wie in Rezept-Struktur und Runplaner (Nutzer: "im
        # Materialien-Tab fehlt der Button"). Der Materialien-Baum hat
        # dieselben einklappbaren Kategorie-Gruppen - dass der Knopf hier
        # fehlte, war schlicht eine Luecke.
        # Der Knopf wird ERST NACH dem Baum verdrahtet (mat_tab_tbl gibt es
        # hier noch nicht); hier nur anlegen und einsortieren, damit er links
        # neben "Einkaufsliste erstellen" steht wie in den anderen Tabs.
        mat_expcol_btn = QPushButton(_txt("\u229e Expand all"))
        mat_expcol_btn.setToolTip(_txt("Expand/collapse all category groups."))
        mat_expcol_btn.setCheckable(True)
        mat_expcol_btn.setMaximumWidth(120)
        mat_tab_toolbar.addWidget(mat_expcol_btn)
        mat_tab_toolbar.addWidget(mat_copy_btn)
        mat_tab_toolbar.addWidget(_rest_only_cb)
        mat_tab_toolbar.addStretch()
        mat_tab_v.addLayout(mat_tab_toolbar)
        mat_tab_status = QLabel(""); mat_tab_status.setObjectName("Muted")
        mat_tab_v.addWidget(mat_tab_status)
        # GRUPPEN-BAUM statt flacher Tabelle (Nutzer-Vorgabe): Kategorien
        # einklappbar, mit Fortschritt je Gruppe. Ein QTreeWidget sortiert
        # INNERHALB des Elternknotens - die Gruppierung kann durch Sortieren
        # also nicht zerfallen (das war bei Gruppenzeilen in einer Tabelle
        # der Knackpunkt).
        mat_tab_tbl = QTreeWidget()
        mat_tab_tbl.setColumnCount(7)
        mat_tab_tbl.setHeaderLabels(
            [_txt("Material"), _txt("Category"), _txt("Required"), _txt("Owned"),
             _txt("Pasted"), _txt("Missing"), _txt("Status")])
        def _mat_toggle_expand(checked):
            mat_expcol_btn.setText(_txt("\u229f Collapse all") if checked
                                   else _txt("\u229e Expand all"))
            (mat_tab_tbl.expandAll if checked else mat_tab_tbl.collapseAll)()

        mat_expcol_btn.toggled.connect(_mat_toggle_expand)
        mat_tab_tbl.setRootIsDecorated(True)
        mat_tab_tbl.setIndentation(18)
        mat_tab_tbl.setUniformRowHeights(True)
        mat_tab_tbl.setAlternatingRowColors(False)
        mat_tab_tbl.setIconSize(QSize(22, 22))
        mat_tab_tbl.setStyleSheet(
            "QTreeWidget{border:none; outline:none; font-size:13px;}"
            "QTreeWidget::item{padding:5px 4px; "
            "border-bottom:1px solid rgba(255,255,255,0.04);}"
            "QHeaderView::section{border:none; "
            "border-bottom:1px solid " + theme.BORDER + "; padding:6px 4px; "
            "color:" + theme.MUTED + "; font-size:11px;}")
        mat_tab_tbl.setEditTriggers(QTreeWidget.NoEditTriggers)
        mat_tab_tbl.setSortingEnabled(True)

        def _mat_dbl(_it, _col):
            # Gruppenzeilen tragen keine type_id - dort passiert nichts.
            _t = _it.data(0, Qt.UserRole) if _it is not None else None
            if _t:
                self._build_to_chart_tid(int(_t), _it.text(0))
        mat_tab_tbl.itemDoubleClicked.connect(_mat_dbl)
        # ---- Zweispaltig (Nutzer-VORGABE): links die Tabelle wie bisher,
        # rechts das feste Clipboard-Panel. Vorher war die rechte Hälfte des
        # Tabs schlicht leer und die Funktion steckte als weiterer Knopf in
        # der ohnehin überfüllten Kopfleiste. Splitter statt fixer Breite,
        # damit man das Panel bei Bedarf schmaler ziehen kann. ------------
        mat_split = QSplitter(Qt.Horizontal)
        mat_split.addWidget(mat_tab_tbl)

        # Das Panel ist der wichtigste Bedienpunkt dieses Tabs (Nutzer:
        # "muss gesehen werden") - deshalb eigener Rahmen, grosse Ueberschrift
        # und nur EINE Zeile Erklaerung. Details stehen in den Tooltips.
        paste_panel = QFrame()
        # AMBER wie alle anderen Panel-Akzente (Nutzer: "ich moechte, dass
        # alle Tabs farblich gleich aufgebaut sind"). Cyan bleibt der Farbe
        # fuer AKTIVE/ausgewaehlte Elemente vorbehalten - ein Panel-Rahmen ist
        # kein Zustand.
        paste_panel.setStyleSheet(
            f"QFrame{{background:{theme.PANEL2}; border:2px solid {theme.AMBER}; "
            f"border-radius:8px;}}")
        pp = QVBoxLayout(paste_panel)
        pp.setContentsMargins(12, 10, 12, 10); pp.setSpacing(7)
        # KEIN EIGENER TITEL MEHR (26.09.2026): das Panel sitzt jetzt in der
        # Klappe "Paste stock" der Seitenleiste - deren Kopf ist der Titel.
        # WOF\u00dcR das gut ist - stand bisher nirgends. Ohne diesen Satz wirkt
        # das Panel wie eine Doppelung des ESI-Bestands (Nutzer-Wunsch).
        pp_why = QLabel(_txt("Paste here if ESI is not fast enough."))
        pp_why.setWordWrap(True)
        pp_why.setStyleSheet(
            f"font-size:13px; font-weight:700; color:{theme.AMBER}; border:none;")
        pp_why.setToolTip(_txt(
            "ESI caches assets for up to an hour. Freshly delivered "
              "or just relocated material is therefore still missing "
              "there.\nThe same goes for material in places ESI cannot "
              "see for you.\nWhat you paste here applies as long as it "
              "is NEWER than the ESI data – after that ESI takes over "
              "again automatically."))
        pp.addWidget(pp_why)
# Anleitung "Hangar markieren -> Strg+C -> einfuegen -> Uebernehmen"
        # ENTFERNT (Nutzer). Sie steht jetzt im Tooltip des Textfelds, und der
        # Platzhaltertext im Feld zeigt das erwartete Format ohnehin.
        _pp_help_tip = _txt("Select the hangar in game \u2192 Ctrl+C \u2192 paste here "
                            "\u2192 Apply.\nExpected is ONE item per line: name, then "
                            "quantity.")
        from PySide6.QtWidgets import QPlainTextEdit as _QPTE
        paste_box = _QPTE()
        # de_scan3: aus  (Beispiel-Itemnamen aus EVE, sprachneutral)
        paste_box.setPlaceholderText("Gravimetric Sensor Cluster\t1.485\n"
                                     "Magpulse Thruster\t1.188\n\u2026")
        # de_scan3: an
        paste_box.setMinimumHeight(260)
        paste_box.setToolTip(_pp_help_tip)
        pp.addWidget(paste_box, 1)
        paste_perm_cb = QCheckBox(_txt("Keep after ESI updates"))
        paste_perm_cb.setStyleSheet("border:none;")
        # STANDARD AN (Nutzer: "der Haken schadet ja nicht, ist sinnvoll").
        # Begruendung: wer etwas von Hand einfuegt, tut das GERADE WEIL ESI
        # es nicht oder nicht schnell genug sieht. Ohne den Haken faellt der
        # Wert beim naechsten Abruf still auf 0 zurueck - genau der Fall, den
        # man vermeiden wollte. Abschalten kann man ihn weiterhin.
        paste_perm_cb.setChecked(True)
        paste_perm_cb.setToolTip(_txt(
            "ON (default): the pasted quantities apply permanently – "
              "even when ESI later delivers fresher data.\nOFF: they "
              "apply only as long as they are NEWER than the ESI data; "
              "after that ESI counts again.\nLeave it ON when ESI "
              "fundamentally cannot see this material – otherwise the "
              "value drops to 0 on the next fetch."))
        pp.addWidget(paste_perm_cb)
        paste_only_cb = QCheckBox(_txt("Ignore ESI \u2013 use this list only"))
        paste_only_cb.setStyleSheet("border:none;")
        paste_only_cb.setToolTip(_txt(
            "ON: the ESI stock is ignored for this plan, only the "
              "pasted list counts.\nRunning and finished jobs still "
              "count – they are in no hangar and cannot be pasted at "
              "all."))
        pp.addWidget(paste_only_cb)
        pp_btns = QHBoxLayout(); pp_btns.setContentsMargins(0, 0, 0, 0)
        paste_apply_btn = QPushButton(_txt("Apply"))
        paste_apply_btn.setIcon(icons.icon("check"))
        # Derselbe Stil wie "Create shopping list" (aa78: die beiden
        # Aktions-Knoepfe des Reiters sehen gleich aus) - EINE Stelle.
        paste_apply_btn.setStyleSheet(theme.amber_rahmen_knopf())
        paste_clear_btn = QPushButton(_txt("Clear"))
        paste_clear_btn.setIcon(icons.icon("trash"))
        paste_clear_btn.setStyleSheet(
            f"QPushButton{{border:1px solid {theme.BORDER}; border-radius:6px; "
            f"padding:5px 12px; color:{theme.MUTED};}}"
            f"QPushButton:hover{{border-color:{theme.RED}; color:{theme.RED};}}")
        pp_btns.addWidget(paste_apply_btn); pp_btns.addWidget(paste_clear_btn)
        pp_btns.addStretch()
        pp.addLayout(pp_btns)
        paste_state_lbl = QLabel("")
        paste_state_lbl.setWordWrap(True)
        paste_state_lbl.setStyleSheet("font-size:11px; border:none;")
        pp.addWidget(paste_state_lbl)

        def _paste_state_text():
            """Zustandszeile des Panels: Alter der Einfügung + Trefferbilanz +
            ob sie gerade tatsächlich GILT (Zeitstempel-Automatik)."""
            n_ok = len(getattr(self, "_bd_manual_stock", None) or {})
            n_bad = len(getattr(self, "_bd_manual_unknown", None) or [])
            if not n_ok and not n_bad:
                # LEER = NORMALFALL, also nichts sagen (Nutzer). Die Zeile
                # "Noch nichts eingefuegt" stand dauerhaft da und beschrieb
                # den Zustand, den man ohnehin sieht: ein leeres Feld.
                return ""
            _ts = getattr(self, "_bd_manual_ts", None)
            bits = [f"<b>{self._stock_age_text(_ts)}</b>",
                    _txt("{ok} recognised, {bad} unknown").format(ok=n_ok, bad=n_bad)]
            # 🔒-ABZUG AUCH HIER SICHTBAR (Nutzer-Vorfall: Hangar
            # eingefuegt, "Besitze aendert sich gar nicht" - die
            # Reservierungen ANDERER Plaene hatten den eingefuegten Bestand
            # an der zentralen Abzugsstelle geschluckt, aber die einzige
            # Anzeige dafuer hing am ESI-Pfad. Ohne diese Zeile sieht der
            # Einfuege-Weg wie kaputt aus, obwohl er korrekt rechnet).
            _ra_p = getattr(self, "_bd_reserved_applied", None) or {}
            if _ra_p:
                _rp_p = ", ".join(getattr(self, "_bd_reserved_plans", None)
                                  or [])
                bits.append(
                    f"<span style='color:{theme.AMBER};'>"
                    + _txt("{n} units deducted by reservations ({plans})").format(
                        n=f"{sum(_ra_p.values()):,}".replace(",", "'"), plans=_rp_p)
                    + "</span>")
            if getattr(self, "_bd_manual_legacy", False):
                bits.append(f"<span style='color:{theme.AMBER};'>"
                            + _txt("\u26a0 no timestamp (plan from before this feature) "
                                   "\u2013 counts as \u201ePermanent\u201c until you paste "
                                   "anew") + "</span>")
            if getattr(self, "_bd_manual_only", False):
                bits.append(f"<span style='color:{theme.CYAN};'>"
                            + _txt("only pasted stock active") + "</span>")
            elif self._manual_stock_is_current(
                    _ts, getattr(self, "_bd_esi_stock_ts", None),
                    bool(getattr(self, "_bd_manual_perm", False))):
                bits.append(f"<span style='color:{theme.GREEN};'>"
                            + _txt("applies \u2713") + "</span>")
            else:
                bits.append(f"<span style='color:{theme.MUTED};'>"
                            + _txt("superseded: ESI data is fresher \u2013 ESI counts again")
                            + "</span>")
            out = " \u00b7 ".join(bits)
            _unk = getattr(self, "_bd_manual_unknown", None) or []
            if _unk:
                out += (f"<br><span style='color:{theme.AMBER};'>"
                        + _txt("\u26a0 not recognised: ") + ", ".join(_unk[:4])
                        + ("\u2026" if len(_unk) > 4 else "") + "</span>")
            return out

        def _sync_paste_panel(refill_box=True):
            """Panel auf den gespeicherten Stand bringen. Liest bewusst NUR
            Widgets, die oben schon existieren, und self-Attribute - darf
            deshalb sofort beim Aufbau laufen (Reihenfolge-Lehre)."""
            cur = dict(getattr(self, "_bd_manual_stock", None) or {})
            if refill_box:
                if cur:
                    try:
                        _nm = store.cached_names(list(cur))
                    except Exception:
                        _nm = {}
                    paste_box.setPlainText("\n".join(
                        f"{_nm.get(t, '#%d' % t)}\t{q}"
                        for t, q in sorted(cur.items())))
                else:
                    paste_box.setPlainText("")
            # Standardwerte je Haken: "Dauerhaft gueltig" ist AN, wenn nichts
            # anderes gespeichert ist (s. oben).
            for _cb, _attr, _dflt in ((paste_perm_cb, "_bd_manual_perm", True),
                                      (paste_only_cb, "_bd_manual_only", False)):
                _cb.blockSignals(True)
                _cb.setChecked(bool(getattr(self, _attr, _dflt)))
                _cb.blockSignals(False)
            # Leere Zeile auch WIRKLICH verstecken - ein leeres QLabel behaelt
            # sonst seine Hoehe und laesst eine Luecke stehen.
            _pst = _paste_state_text()
            paste_state_lbl.setText(_pst)
            paste_state_lbl.setVisible(bool(_pst))
        self._bd_sync_paste_panel = _sync_paste_panel
        _sync_paste_panel()

        def _paste_refresh_view():
            """Bestand neu auflösen + Ansicht nachziehen. Der volle Rebuild
            läuft über self._bd_full_rebuild (wird weiter unten belegt) -
            als self-Attribut, damit hier keine Vorwärts-Referenz entsteht."""
            self._recompute_bd_stock()
            _sync_paste_panel(refill_box=False)
            _fn = getattr(self, "_bd_full_rebuild", None)
            if _fn is not None:
                _fn()

        def _paste_apply():
            try:
                nmap = store.name_to_type_id()
            except Exception:
                nmap = {}
            parsed, unknown = self._parse_pasted_stock(paste_box.toPlainText(),
                                                       nmap)
            self._bd_manual_stock = parsed
            self._bd_manual_unknown = list(unknown or [])
            # Zeitstempel = JETZT. Ab hier gilt die Einfügung, solange sie
            # neuer ist als die ESI-Bestandsdaten (bzw. dauerhaft, s. Häkchen).
            self._bd_manual_ts = _time_mod.time() if parsed else None
            self._bd_manual_legacy = False
            self._bd_manual_perm = paste_perm_cb.isChecked()
            self._bd_manual_only = paste_only_cb.isChecked()
            msg = _txt("{ok} recognised, {bad} unknown \u2013 applied as pasted "
                       "stock").format(ok=len(parsed), bad=len(unknown or []))
            if unknown:
                msg += (" \u00b7 \u26a0 " + ", ".join(unknown[:3])
                        + ("\u2026" if len(unknown) > 3 else ""))
            self._flash_tip(msg)
            _paste_refresh_view()

        def _paste_clear():
            paste_box.setPlainText("")
            self._bd_manual_stock = {}
            self._bd_manual_unknown = []
            self._bd_manual_ts = None
            self._bd_manual_legacy = False
            self._flash_tip(_txt("Pasted stock cleared \u2013 the ESI stock "
                                 "counts again"))
            _paste_refresh_view()

        def _paste_flags(_checked=False):
            self._bd_manual_perm = paste_perm_cb.isChecked()
            self._bd_manual_only = paste_only_cb.isChecked()
            _paste_refresh_view()
        paste_apply_btn.clicked.connect(_paste_apply)
        paste_clear_btn.clicked.connect(_paste_clear)
        paste_perm_cb.toggled.connect(_paste_flags)
        paste_only_cb.toggled.connect(_paste_flags)

        # IN EINE KLAPPE RECHTS, STANDARD ZU (Nutzer 26.09.2026: "Paste
        # Stock ist gut und nuetzlich, aber wenn alles richtig eingestellt
        # ist, braucht man das ja nicht. Packen wir das in ein Dropdown als
        # rechte Sidebar und machen es standardmaessig zu. Mit der Info, wenn
        # man es aufklappt: 'Du brauchst keine Stocks zu pasten, da dieses
        # Tool eigentlich mit ESI funktioniert. Es sei denn, du moechtest es
        # nicht.' und dann weiter -> Dropdown geht auf. Schliessen kann man
        # wieder ohne Kommentar").
        # Ablauf: Klappe auf -> NUR der Hinweis mit "Continue"; "Continue"
        # -> Hinweis weg, Panel da. Klappe zu -> einfach zu; beim naechsten
        # Aufklappen kommt der Hinweis wieder (jedes Oeffnen ist eine neue
        # Entscheidung gegen ESI).
        pp_side = QWidget()
        pp_side_v = QVBoxLayout(pp_side)
        pp_side_v.setContentsMargins(4, 6, 0, 4); pp_side_v.setSpacing(0)
        pp_inner = QWidget()
        pp_inner_v = QVBoxLayout(pp_inner)
        pp_inner_v.setContentsMargins(0, 0, 0, 0); pp_inner_v.setSpacing(6)
        pp_hint = QFrame()
        pp_hint.setStyleSheet(
            f"QFrame{{background:{theme.PANEL2}; border:1px solid {theme.AMBER}; "
            f"border-radius:8px;}}")
        pp_hint_v = QVBoxLayout(pp_hint)
        pp_hint_v.setContentsMargins(12, 10, 12, 10); pp_hint_v.setSpacing(8)
        pp_hint_lbl = QLabel(_txt(
            "You do not need to paste stock \u2013 this tool works with ESI. "
            "Only if you do not want that."))
        pp_hint_lbl.setWordWrap(True)
        pp_hint_lbl.setStyleSheet(
            f"font-size:13px; color:{theme.TEXT}; border:none;")
        pp_hint_v.addWidget(pp_hint_lbl)
        pp_weiter_btn = QPushButton(_txt("Continue"))
        pp_weiter_btn.setIcon(icons.icon("check"))
        pp_weiter_btn.setStyleSheet(theme.amber_rahmen_knopf())
        _pp_wr = QHBoxLayout(); _pp_wr.setContentsMargins(0, 0, 0, 0)
        _pp_wr.addWidget(pp_weiter_btn); _pp_wr.addStretch()
        pp_hint_v.addLayout(_pp_wr)
        pp_inner_v.addWidget(pp_hint)
        pp_inner_v.addWidget(paste_panel, 1)
        paste_panel.hide()
        pp_side_v.addWidget(self._collapsible(
            _txt("Paste stock"), pp_inner, expanded=False,
            header_attr="_bd_paste_hdr",
            tip=_txt("Paste here if ESI is not fast enough.")))
        pp_side_v.addStretch(1)

        def _pp_zeigen(panel_da):
            """Hinweis ODER Panel; mit Panel bekommt die Klappe die Hoehe."""
            pp_hint.setVisible(not panel_da)
            paste_panel.setVisible(panel_da)
            pp_side_v.setStretch(0, 1 if panel_da else 0)
            pp_side_v.setStretch(1, 0 if panel_da else 1)

        def _pp_klappe(offen):
            if offen:
                _pp_zeigen(False)       # jedes Aufklappen: erst der Hinweis
        self._bd_paste_hdr.toggled.connect(_pp_klappe)
        pp_weiter_btn.clicked.connect(lambda _c=False: _pp_zeigen(True))
        self._bd_paste_hint = pp_hint            # b-Suite
        self._bd_paste_weiter = pp_weiter_btn    # b-Suite
        self._bd_paste_panel = paste_panel       # b-Suite
        mat_split.addWidget(pp_side)
        mat_split.setStretchFactor(0, 1)
        mat_split.setStretchFactor(1, 0)
        # Nutzer: das Panel darf gr\u00f6\u00dfer sein - in der Tabelle stand rechts
        # ohnehin viel Leerraum, seit zwei Spalten ausgeblendet sind.
        mat_split.setSizes([640, 480])
        mat_tab_v.addWidget(mat_split, 1)
        self._bd_mat_tab_tbl = mat_tab_tbl
        self._bd_mat_tab_status = mat_tab_status
        # Referenz merken: der Info-Text muss sich ändern, sobald der Plan
        # eingefroren ist - dann steht in der "ESI"-Spalte nicht mehr der
        # rohe ESI-Wert (s. _fill_material_tab).
        self._bd_mat_tab_info = mat_tab_info
        tab_icon_at(_tabs, 2, mat_tab_w, _txt("Materials"), "package")   # hinter Blueprints

        # ---- \U0001F9EA Invention-Tab: Datacores/Decryptor pro T2-Item, mit
        # live nachgerechneter Erfolgschance/Runs/ME/TE, plus Gesamtbedarf für
        # die aktuelle Bauplan-Menge. ------------------------------------------
        inv_tab_w = QWidget(); inv_tab_v = QVBoxLayout(inv_tab_w)
        # Gleiche Raender und Abstaende wie Materialien/Blueprints/Runplaner
        # (Nutzer: "Rezept-Struktur ist das Ausgangslayout"). Spacing 8 statt 6
        # war der einzige Ausreisser.
        inv_tab_v.setContentsMargins(4, 6, 4, 4); inv_tab_v.setSpacing(6)
        # Nutzer-Linie "mehr per Mouseover": vorher standen hier 314 Zeichen
        # Dauertext, die man einmal liest und danach jedes Mal ueberspringt.
        # Die kurze Zeile sagt, WAS der Tab tut; das WIE steht im Tooltip.
        # Auch diese Zeile weg (Nutzer): der Tab heisst "Invention", die
        # Karten zeigen Datacores, Decryptor und Kosten - der Satz wiederholte
        # nur die Ueberschrift. Das Label bleibt als TOOLTIP-Traeger fuer die
        # Erwartungswert-Warnung, die keine Erklaerung, sondern eine Einordnung
        # der Zahlen ist.
        inv_tab_info = QLabel("")
        inv_tab_info.setObjectName("Muted"); inv_tab_info.setWordWrap(True)
        inv_tab_info.setVisible(False)
        inv_tab_info.setToolTip(_txt(
            "Per T2 item created through invention: datacores "
              "(fixed, from the blueprint recipe) plus a decryptor "
              "(selectable).\nSuccess chance, runs, ME and TE change "
              "live with the choice.\n\nThe total costs below are "
              "EXPECTED VALUES – in a single session you may need "
              "considerably more attempts if you are unlucky."))
        inv_tab_v.addWidget(inv_tab_info)
        inv_scroll = QScrollArea(); inv_scroll.setWidgetResizable(True)
        inv_scroll.setFrameShape(QFrame.NoFrame)
        inv_inner = QWidget(); inv_cards_v = QVBoxLayout(inv_inner)
        inv_cards_v.setContentsMargins(0, 0, 0, 0); inv_cards_v.setSpacing(6)
        # Der Stretch wird beim Fuellen ohnehin neu gesetzt (s.
        # _fill_invention_tab) - hier nur, damit die Spalte auch VOR dem
        # ersten Fuellen oben ausgerichtet ist.
        inv_cards_v.addStretch()
        inv_scroll.setWidget(inv_inner)
        # GLEICHE INHALTSBREITE WIE DIE ANDEREN TABS (Nutzer: "jeder Tab soll
        # optisch gleich aussehen"). Rezept-Struktur, Blueprints und Runplaner
        # haben links den Inhalt und rechts eine 380px-Seitenleiste; der
        # Invention-Tab zog sich als einziger ueber die volle Fensterbreite,
        # wodurch die Karten auf breiten Monitoren auseinandergerissen wurden.
        # ECHTE SEITENLEISTE statt Platzhalter (Nutzer: "das gehoert doch
        # rechts ran, genau wie bei den anderen Tabs, in gelber Farbe,
        # dieselbe Groesse"). Der leere 380px-Block war nur ein Abstandhalter -
        # die Bedienelemente (Struktur, Skill-Charakter, Zuruecksetzen) lagen
        # weiterhin quer ueber der Kartenspalte. Jetzt liegen sie dort, wo in
        # jedem anderen Tab die Einstellungen liegen.
        _inv_row = QHBoxLayout()
        _inv_row.setContentsMargins(0, 0, 0, 0); _inv_row.setSpacing(8)
        _inv_row.addWidget(inv_scroll, 1)
        _inv_side = QWidget(); _inv_side.setFixedWidth(380)
        _inv_side_v = QVBoxLayout(_inv_side)
        _inv_side_v.setContentsMargins(0, 0, 0, 0); _inv_side_v.setSpacing(8)
        _inv_side_box = QWidget()
        self._bd_inv_side_v = QVBoxLayout(_inv_side_box)
        self._bd_inv_side_v.setContentsMargins(0, 0, 0, 0)
        self._bd_inv_side_v.setSpacing(6)
        # "BUY OR NOT?" GANZ OBEN, STANDARD OFFEN (Nutzer 26.09.2026: "Buy
        # Datacores und Buy Decryptors nimm das rechts in die Sidebar mit neuer
        # Kategorie 'Buy or not?' (standard ausgeklappt), ganz oben als erste
        # Position ueber Invention Settings"). Die zwei Haken sind globale
        # Einstellungen - einmal je Fenster, nicht je Karte.
        _inv_side_v.addWidget(self._collapsible(
            _txt("Buy or not?"), self._build_invention_purchase_panel(),
            expanded=True,
            tip=_txt("Whether the datacores and decryptors worked out in the "
                     "Invention tab go into the shopping list.")))
        # "BEST DECRYPTOR FOR ALL BLUEPRINTS" (Nutzer, gleiche Nachricht:
        # "damit man nicht jeden Blueprint separat ansteuern muss").
        _alle_best = QPushButton(_txt("Best Decryptor for all Blueprints"))
        _alle_best.setIcon(icons.icon("trophy"))
        _alle_best.setMinimumHeight(34)
        _alle_best.setToolTip(_txt(
            "Picks the best decryptor for every blueprint in this tab, one after "
            "the other, with the same calculation as each card's \u201eBest "
            "Decryptor\u201c button. Cards with \u201eOwn BPC\u201c are left out."))
        # WIE "CREATE SHOPPING LIST" (Nutzer 26.09.2026).
        _alle_best.setStyleSheet(theme.amber_rahmen_knopf())
        _alle_best.clicked.connect(lambda: self._inv_alle_besten())
        self._bd_inv_alle_btn = _alle_best          # b-Suite
        _inv_side_v.addWidget(_alle_best)
        _alle_lbl = QLabel("")
        _alle_lbl.setWordWrap(True)
        _alle_lbl.setStyleSheet(f"color:{theme.GREEN};")
        self._bd_inv_alle_lbl = _alle_lbl
        _inv_side_v.addWidget(_alle_lbl)
        _alle_lbl.hide()
        _inv_side_v.addWidget(self._collapsible(
            # Standard ZU (Nutzer): die Seitenleiste soll nicht dauerhaft
            # Platz kosten - man stellt Struktur, Sicherheit und Charakter
            # einmal ein und sieht danach lieber den Invention-Tab selbst.
            _txt("Invention settings"), _inv_side_box, expanded=False,
            tip=_txt("Structure for the invention and the character whose skills "
                     "go into the success chance.")))
        _inv_side_v.addStretch()
        _inv_row.addWidget(_inv_side)
        _inv_row_w = QWidget(); _inv_row_w.setLayout(_inv_row)
        inv_tab_v.addWidget(_inv_row_w, 1)
        # Auch der Erklaertext oben bricht jetzt in der Inhaltsspalte um,
        # statt sich als einzelne Zeile ueber den ganzen Bildschirm zu ziehen.
        inv_tab_info.setMaximumWidth(1200)
        self._bd_inv_cards_v = inv_cards_v
        self._bd_decryptor_map = getattr(self, "_bd_decryptor_map", {}) or {}
        tab_icon_at(_tabs, 1, inv_tab_w, "Invention", "flask")

        # ZIELREIHENFOLGE (Nutzer): zuerst das, was man beim Bauen wirklich
        # braucht - Materialien (was kaufe ich?), Invention, Runplaner. Die
        # Nachschlage-Tabs Blueprints und Rezept-Struktur wandern nach hinten.
        # Deklarativ statt \u00fcber insertTab-Indizes: die verschieben sich, sobald
        # irgendwo ein Tab dazukommt, und dann stimmt die Reihenfolge still
        # nicht mehr.
        # REZEPT-STRUKTUR ZUERST (Nutzer): dort trifft man die Entscheidungen
        # (bauen/kaufen, Blacklist per Rechtsklick, Kategorien) - die
        # Materialliste ist das ERGEBNIS davon, nicht der Einstieg.
        # RUNPLANER GANZ NACH RECHTS (Nutzer): er ist der letzte Schritt -
        # erst entscheiden (Rezept-Struktur), dann einkaufen (Materialien),
        # dann erfinden, dann nachschlagen (Blueprints), und zuletzt die
        # Jobs verteilen.
        # Sitzung 17: UEBERSETZTE Titel suchen - mit "Materialien"/"Runplaner"
        # fand die Suche auf Englisch nichts (Reihenfolge stimmte nur zufaellig).
        for _pos, _key in enumerate((_txt("Recipe structure"), _txt("Materials"),
                                     "Invention", "Blueprints", _txt("Run planner"))):
            for _i in range(_tabs.count()):
                if _key in _tabs.tabText(_i):
                    if _i != _pos:
                        _tabs.tabBar().moveTab(_i, _pos)
                    break
        # Startet auf Materialien: die h\u00e4ufigste Frage ist "was muss ich
        # kaufen?", nicht "wie sieht die Rezept-Kette aus".
        _tabs.setCurrentIndex(0)
        if _is_reaction_product or not _is_invented:
            # KEIN INVENTION-TAB, wenn nichts erfunden wird: Reaktionen nicht,
            # T1 nicht. Bei T1 stehen ME/TE stattdessen oben neben der Menge
            # (s. _me_te_in_header) - sonst waere mit dem Tab auch das einzige
            # Eingabefeld verschwunden.
            # NACH dem Sortieren entfernen, nicht davor: die Reihenfolge oben
            # sucht per Namen, ein fehlender Tab wuerde sie sonst still
            # verschieben. removeTab loescht das Widget NICHT - die
            # bestehende Fuell-Logik in rebuild() greift weiter darauf zu,
            # genau wie beim ebenfalls nicht angezeigten bo_tree.
            for _i in range(_tabs.count() - 1, -1, -1):
                if "Invention" in _tabs.tabText(_i):
                    _tabs.removeTab(_i)
            # Die Kostenzeile "Invention" bliebe dauerhaft auf 0 ISK stehen -
            # eine Zahl, die nur Platz kostet und Fragen aufwirft.
            _inv_cap = _detail_caps.get("Invention (\u00d8)")
            if _inv_cap is not None:
                _inv_cap.setVisible(False)
            _detail_val_lbls["Invention (\u00d8)"].setVisible(False)
        # Rechte Seitenleiste weggefallen - t("Blueprints per stage") und "Andere
        # Blaupausen" sind in den Blueprints-Tab gezogen, alle Haupt-Tabs
        # bekommen jetzt die volle Breite.
        body = QHBoxLayout(); body.setSpacing(10)
        # REIHENFOLGE ZUM SCHLUSS EXPLIZIT SETZEN statt sie aus drei
        # insertTab-Indizes zusammenzuwuerfeln. Die drei Aufrufe stehen an
        # verschiedenen Stellen und laufen NICHT in Quelltext-Reihenfolge -
        # die tatsaechliche Abfolge war dadurch etwas anderes als die
        # Indizes vermuten liessen (im Test aufgefallen: Materialien landete
        # vor Blueprints). Ausserdem faellt der Invention-Tab bei T1 ganz
        # weg, was jede feste Indexrechnung verschiebt.
        # Reihenfolge = Arbeitsablauf des Nutzers: Rezept anschauen ->
        # Invention planen -> Blueprints checken -> Materialien einkaufen ->
        # ingame mit dem Runplaner arbeiten.
        _wunsch = [_txt("Recipe structure"), "Invention", "Blueprints",
                   _txt("Materials"), _txt("Run planner")]
        _ziel = 0
        for _name in _wunsch:
            for _i in range(_tabs.count()):
                if _name in _tabs.tabText(_i):
                    if _i != _ziel:
                        _tabs.tabBar().moveTab(_i, _ziel)
                    _ziel += 1
                    break
        _tabs.setCurrentIndex(0)

        body.addWidget(_tabs, 1)
        v.addLayout(body, 1)

        def fmt(q):
            return (f"{q:,.1f}".replace(",", "'") if q % 1
                    else f"{int(q):,}".replace(",", "'"))

        _TIER_COLORS = theme.TIER_PALETTE

        # Die "bauen vs. kaufen"-Entscheidung kommt aus production_plan (die eine
        # Wahrheit), NICHT aus build_tree. rebuild() füllt dieses Ref mit
        # plan["decision"]; add_node liest daraus. So zeigt die Rezept-Struktur
        # exakt das, was der Runplaner ausführt -- kein Auseinanderdriften mehr.
        plan_dec_ref = {"decision": {}}

        def _decision_of(comp):
            """Entscheidung für ein Item: bevorzugt aus dem Plan (Quelle),
            Fallback auf die vom build_tree gelieferte (falls das Item nicht im
            Plan auftaucht, z. B. bei abgeschnittener Baumtiefe)."""
            pd = plan_dec_ref["decision"]
            return pd.get(comp["type_id"], comp["decision"])

        def add_node(parent, comp, parent_runs, depth=1):
            # comp["qty"] = Material pro RUN des Eltern-Items (durchgehender
            # Float aus build_tree) → × Runs des Eltern-Items = Bedarf für den
            # GESAMTEN Job. Genau HIER, einmal auf die Summe, wird aufgerundet
            # - offizielle CCP-Regel (Material-Efficiency-Research-Artikel):
            # "Material Efficiency calculations are applied to the whole job,
            # not individual runs [...] rounded up to the next significant
            # digit" (Beispiel dort: 14.4 Tritanium für 10 Stück → 15, NICHT
            # 10× einzeln aufgerundet). Vorher stand hier gar keine Rundung
            # (deshalb "174'585.9"-Dezimalstellen in der Anzeige).
            import math as _math
            aq_raw = comp["qty"] * parent_runs
            # JOB-SICHER (Sitzung 13): nicht einmal auf die Summe aller Runs
            # runden, sondern PRO RUN - der Runplaner verteilt die Runs auf
            # mehrere Jobs, und jeder Job rundet in EVE fuer sich auf.
            # Begruendung und Beweis in industry.material_menge; dieselbe
            # Funktion rechnet die Einkaufsliste, damit Baum und Wagen nicht
            # zwei verschiedene Zahlen zeigen.
            aq = (industry.material_menge(comp["qty"], parent_runs, 1.0)
                  if aq_raw > 0 else 0.0)
            total = comp["unit_cost"] * aq
            dec = _decision_of(comp)          # Entscheidung aus dem Plan (Quelle)
            if dec == "owned":
                # "vorhanden" war irrefuehrend: bei einem Blacklist-Item sah
                # es aus, als waere es weiter Teil des Plans (Nutzer: "die
                # Blacklist funktioniert nicht"). Die RECHNUNG stimmt - das
                # Item wird weder gebaut noch gekauft, und seine Materialien
                # fallen ebenfalls weg -, aber die Zeile sagte das nicht.
                _excl = (getattr(self, "_bd_excluded_ids", None) or set())
                if int(comp["type_id"]) in _excl:
                    act = _txt("Blacklist \u2013 not planned")
                else:
                    act = _txt("on hand")
            elif dec == "build":
                act = _txt("BUILD")
                # "BAUEN \u00b7 0 Runs" las sich, als wuerde gebaut - dabei ist
                # genau NICHTS zu tun (der Bedarf ist bereits gedeckt oder
                # der Elternknoten wird gekauft). Nutzer-Meldung: "trotzdem
                # will der Bauplan sie bauen".
                if aq <= 0:
                    act = _txt("\u2014 nothing to build")
                # AUS DEM BESTAND GEDECKT: der Baum zeigt die ENTSCHEIDUNG
                # (bauen statt kaufen), der Runplaner die tatsaechlichen
                # JOBS. Was der Bestand deckt, wird nicht gebaut - deshalb
                # stand hier "BAUEN", waehrend der Runplaner nichts einplante
                # (Nutzer: "trotzdem will er gewisse Dinge bauen, aber im
                # Runplaner kommen sie nicht vor"). Jetzt sagt es die Zeile.
                _br = getattr(self, "_bd_plan_builds", None)
                _su = getattr(self, "_bd_plan_stock", None) or set()
                _cid = int(comp["type_id"])
                _act_fixed = False
                if aq > 0 and _br is not None and _cid not in _br:
                    act = (_txt("covered from stock")
                           if _cid in _su else _txt("\u2014 not planned"))
                    _act_fixed = True
            else:
                # NETZ GEGEN EIN LUEGENDES ETIKETT (Sitzung 20). Selbst wenn
                # die Baum-Entscheidung einmal veralten sollte, darf "kaufen"
                # nicht ueber einer Zeile stehen, die der Plan gar nicht
                # kauft. Bedingung ist BEIDES - im Bestand verbraucht UND
                # nicht in der Kaufliste -, sonst verschwaende ein echter
                # Zukauf hinter einem beruhigenden Wort.
                _cid_b = int(comp["type_id"])
                _su_b = getattr(self, "_bd_plan_stock", None) or set()
                _by_b = getattr(self, "_bd_plan_buy", None)
                _rp_b = (getattr(self, "_bd_plan_repro", None) or {}).get(_cid_b)
                if aq > 0 and _rp_b and _by_b is not None and _cid_b not in _by_b:
                    # AUS KOMPRIMIERTEM ERZ (1.0.9, Weg B): der Plan kauft das
                    # Erz, nicht das Mineral - die Zeile nennt das Erz.
                    act = _txt("from compressed ore \u267b \u00b7 {ore}").format(
                        ore=", ".join(_rp_b))
                elif aq > 0 and _rp_b and _by_b is not None and _cid_b in _by_b:
                    act = _txt("buy \u00b7 partly from compressed ore \u267b")
                elif (aq > 0 and _cid_b in _su_b and _by_b is not None
                        and _cid_b not in _by_b):
                    act = _txt("covered from stock")
                elif (aq > 0 and _cid_b in _su_b and _by_b is not None
                        and _cid_b in _by_b):
                    # DER MITTLERE FALL (Nutzer, Sitzung 20): der Bestand deckt
                    # einen TEIL, der Rest wird wirklich gekauft. "kaufen"
                    # allein verschweigt den gedeckten Teil - dieselbe zu arme
                    # Sprache, die PI und Mineralien pauschal auf "kaufen"
                    # gesetzt hat.
                    # BEWUSST OHNE MENGEN: die Mengenspalte dieser Zeile zeigt
                    # den STRUKTUR-Bedarf des Rezepts, die Zahlen kaemen aber
                    # aus dem Plan NACH Bestandsabzug. Genau dieser Unterschied
                    # hat bei Fermionic Condensates 1'920 gegen 1'880 ergeben
                    # und wie ein Widerspruch ausgesehen. Die genauen Mengen
                    # stehen im Materialien-Reiter, wo sie EINE Bezugsgroesse
                    # haben.
                    act = _txt("buy \u00b7 partly from stock")
                else:
                    act = _txt("buy")
                    # KEIN REZEPT AUSDRUECKLICH SAGEN (Nutzer-Vorgabe zu
                    # Punkt G): wer nicht bauen KANN, soll das lesen - nicht
                    # stillschweigend auf "kaufen" fallen und raetseln, warum
                    # kein Aufklapp-Pfeil da ist.
                    _rec_b = getattr(self, "_bd_recipes", None)
                    _p2b = getattr(_rec_b, "product_to_bp", None) or {}
                    if not _p2b.get(_cid_b):
                        act = _txt("buy \u00b7 no recipe")
            runs = 0
            if dec == "build" and comp.get("subtree"):
                oq = comp["subtree"].get("output_qty", 1) or 1
                runs = int(-(-aq // oq))                 # ceil → ganze Runs dieses Items
                # NUR wenn oben nichts anderes entschieden wurde. Diese Zeile
                # hat `act` bisher BEDINGUNGSLOS ueberschrieben - deshalb
                # stand auch bei Items, die der Plan gar nicht baut,
                # "BAUEN - N Runs" (und der Runplaner zeigte sie folgerichtig
                # nicht). Der Merker war noetig, weil die Runs-Zahl weiter
                # unten noch gebraucht wird.
                if not locals().get("_act_fixed", False) and aq > 0:
                    act = (_txt("BUILD \u00b7 {n} run") if runs == 1
                           else _txt("BUILD \u00b7 {n} runs")).format(n=runs)
                    # WEG A (1.0.9): gebaut ueber die Unrefined-Formel - die
                    # Zeile nennt sie, sonst passen Runs und Materialien
                    # nicht zur normalen Formel, die man im Kopf hat.
                    _uw_t = (getattr(self, "_bd_unrefined", None) or {}).get(
                        int(comp["type_id"]))
                    if _uw_t:
                        act += "  \u00b7  " + _txt("via {formula} \u267b").format(
                            formula=names.get(int(_uw_t.get("u") or 0),
                                              f"#{_uw_t.get('u')}"))
            # Transparenz: welcher Struktur-Rig wirkt (kategorie-spezifisch)?
            rmpct = (getattr(self, "_bd_rig_me_map", {}) or {}).get(comp["type_id"], 0)
            # Rig-Bonus wird weiter GERECHNET, nur nicht mehr angezeigt
            # (Nutzer: "logisch ein Muss, aber sehen muss ich es nicht").
            if False and dec == "build" and rmpct:
                act += f"  · Rig \u2212{rmpct:.1f}%"
            it = QTreeWidgetItem([names.get(comp["type_id"], f"#{comp['type_id']}"),
                                  fmt(aq), act, isk(comp["unit_cost"], suffix=False),
                                  isk(total, suffix=False)])
            it.setData(0, Qt.UserRole, comp["type_id"])
            # Item-Bildchen wie in den Tabellen - macht die Gliederung ohne
            # zusaetzliche Spalte lesbar (Nutzer-Wunsch).
            _ic = self._table_icon(comp["type_id"])
            if _ic:
                it.setIcon(0, _ic)
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(0, Qt.Unchecked)
            it.setForeground(0, QColor(_TIER_COLORS[min(depth, len(_TIER_COLORS) - 1)]))
            for cc in (1, 3, 4):
                it.setTextAlignment(cc, Qt.AlignRight | Qt.AlignVCenter)
            it.setForeground(2, QColor(theme.CYAN if dec == "build"
                                       else theme.MUTED))
            parent.addChild(it)
            if comp.get("subtree"):
                for c in comp["subtree"]["components"]:
                    add_node(it, c, runs, depth + 1)   # die RUNS dieses Items, nicht seine Stückzahl

        plan_ref = {"plan": res.get("plan")}
        self._bd_plan_ref = plan_ref
        # Transport-Parameter als mutable Ref (Widgets werden erst weiter unten
        # gebaut, aber rebuild() wird schon vorher einmal aufgerufen).
        transport_ref = {"cap": float(self.settings.get("bau_transport_m3", 350000) or 0),
                         "mode": None,     # beide Kostenarten zaehlen immer
                         "rate": float(self.settings.get("bau_transport_rate", 0) or 0),
                         "trip": float(self.settings.get("bau_transport_trip_cost", 0) or 0),
                         "in_decision": bool(self.settings.get(
                             "bau_freight_in_decision", True))}

        def rebuild():
            from ..sprache import t as _txt   # `t` ist hier lokal belegt
            from PySide6.QtWidgets import QTableWidgetItem
            # SANDUHR WAEHREND DER NEUBERECHNUNG (Nutzer: "lieber ein kleines
            # Ladepopup als warten und nicht wissen ob wir freezen").
            # rebuild() rechnet den ganzen Plan neu und laeuft im GUI-Thread,
            # das Fenster steht dabei zwangslaeufig. Die Sanduhr sagt
            # wenigstens ehrlich "ich arbeite" statt "ich haenge".
            # Gesetzt wird sie hier, zurueckgenommen am Ende der Funktion UND
            # in jedem vorzeitigen return - siehe _rb_done().
            from PySide6.QtWidgets import QApplication as _QAcur
            _QAcur.setOverrideCursor(Qt.WaitCursor)

            def _rb_done(_v=None):
                _QAcur.restoreOverrideCursor()
                return _v
            # Charakter-Liste nachziehen: die Skills werden meist erst geholt,
            # WENN der Bauplan schon offen ist.
            _rf = getattr(self, "_bd_refill_sellchar", None)
            if _rf is not None:
                try:
                    _rf()
                except Exception:
                    pass
            qty = qty_spin.value()
            # FRACHTAUFSCHLAG: ist er aktiv, entscheidet der Plan pro Knoten
            # mit dem LANDEPREIS (Hub-Preis + Volumen x ISK/m3) statt dem
            # nackten Hub-Preis - sperriges Material wird dadurch
            # unattraktiver, kompaktes attraktiver. Die Frachtkosten stecken
            # dann in total_cost und duerfen unten NICHT nochmal abgezogen
            # werden (s. _rate_for_estimate).
            _pfn = self._bd_pricemap.get
            _fr_rate = (float(transport_ref.get("rate", 0) or 0)
                        if transport_ref.get("in_decision") else 0.0)
            if _fr_rate > 0:
                try:
                    _fvols, _ = self._item_volumes_with_esi_fix(
                        list(self._bd_pricemap.keys()))
                    _pfn = industry.freight_adjusted_price_fn(
                        _pfn, _fvols, _fr_rate)
                    # Der Frachtdienst transportiert NUR die Einkaufsliste
                    # (Nutzer-Klarstellung). Material, das schon am Bau-Ort
                    # liegt, wird deshalb OHNE Frachtaufschlag bewertet -
                    # sonst rechnet der Plan Fracht mit, die nie anfaellt.
                    self._bd_opts["stock_price_fn"] = self._bd_pricemap.get
                except Exception as _fr_err:
                    # NICHT MEHR STILL (Sitzung 14): hier stand
                    # `except Exception:` ohne Meldung. Faellt die
                    # Volumen-Ermittlung aus, wird der Frachtaufschlag
                    # KOMPLETT abgeschaltet - der Plan entscheidet dann wieder
                    # ohne Fracht, waehrend die Frachtkosten in der Anzeige
                    # trotzdem erscheinen (sie werden separat gerechnet).
                    # Der Nutzer sieht also dieselbe Zahl und eine andere
                    # Entscheidung, ohne Hinweis.
                    #
                    # WARUM DAS HIER BESONDERS WIEGT: der Frachtvorteil kann
                    # eine Kauf/Bau-Entscheidung kippen. An echten Daten
                    # gerechnet - 50 Cormorants kaufen sind 250'000 m3, selbst
                    # bauen nur 50'500 m3 (die Mineralien); bei 350 ISK/m3
                    # rund 70 Mio ISK Unterschied. Faellt der Aufschlag
                    # stumm aus, plant das Tool an dieser Ersparnis vorbei.
                    self._log_exception("Frachtaufschlag: Volumen", str(_fr_err))
                    _fr_rate = 0.0
                    self._bd_opts.pop("stock_price_fn", None)
            else:
                # Ohne Aufschlag ist die Kaufpreis-Funktion ohnehin der reine
                # Marktpreis - dann keine Sonderbehandlung (identisches
                # Verhalten wie vorher).
                self._bd_opts.pop("stock_price_fn", None)
            # PLAN NUR NEU RECHNEN, WENN SICH DIE EINGABE GEAENDERT HAT.
            # production_plan laeuft ueber den ganzen Rezeptbaum und ist der
            # teuerste Teil von rebuild() - im GUI-Thread also der Grund fuer
            # das Stocken. Aenderungen, die den PLAN nicht beruehren (z.B.
            # Zusatzkosten: reine Gewinn-Rechnung), bekommen so den
            # zwischengespeicherten Plan.
            # FINGERABDRUCK statt "hat sich irgendwas geaendert?": er umfasst
            # ALLES, was in den Plan einfliesst. Kommt eine neue Option dazu,
            # gehoert sie hier hinein - sonst rechnet der Dialog mit einem
            # veralteten Plan weiter, und das ist der Fehler, der hier schon
            # zweimal Zeit gekostet hat (s. _depth_fingerprint).
            # REPROCESSING WEG A: die Rezept-Kopie jedes Mal neu aus den
            # Basis-Rezepten ableiten (Schalter, Struktur, Skills oder
            # Fracht koennen sich seit dem Oeffnen geaendert haben) - MIT
            # derselben Preisfunktion wie der Plan, Gutschrift zum reinen
            # Hub-Preis. Eingefroren: die Wahl kommt aus dem Schnappschuss,
            # damit Runs und Stueck je Run zu den eingefrorenen Zahlen passen.
            _fz_fuer_uo = self._frozen_snapshot_plan()
            _rec_basis = getattr(self, "_bd_recipes_basis", None) or self._bd_recipes
            # BUENDEL: DIE MENGEN DER ENDEN KOMMEN AUS DEM ZUSTAND, NICHT AUS
            # DEM OEFFNEN (Nutzer-Befund 26.09.2026: "warum hat die Prowler, von
            # der ich 10 Stk bauen will, gleich viel wie die Sacrilege, von der
            # ich nur 1 bauen will?"). Nachgestellt (b85): Menge in der
            # Endprodukte-Karte 10 -> 25, `_bd_buendel_enden` sagte 25, der
            # Plan rechnete weiter mit 10 - die Rezept-Kopie mit den Bündel-
            # Mengen entstand nur beim Oeffnen (`_bd_recipes_basis`). Folge:
            # Einkaufsliste, Invention-Versuche, Runplaner fuer die ALTE Menge,
            # also ZU WENIG (Regel 3). Jetzt jedes Mal neu aus dem Zustand.
            # `buendel_rezepte` ueberschreibt die Buendel-Eintraege der Kopie.
            if int(type_id) == industry.BUENDEL_ID and getattr(self, "_bd_buendel_enden", None):
                _rec_basis = industry.buendel_rezepte(_rec_basis, self._bd_buendel_enden)
                self._bd_recipes_basis = _rec_basis
            _uw_vorher = set((getattr(self, "_bd_unrefined", None) or {}).keys())
            self._bd_recipes, _uw = self._unrefined_overlay(
                type_id, _rec_basis, _pfn, self._bd_opts,
                kredit_pfn=self._bd_pricemap.get,
                fest=((_fz_fuer_uo or {}).get("unrefined") or {})
                if _fz_fuer_uo is not None else None)
            if set(_uw.keys()) != _uw_vorher:
                self._bd_reaction_stages = None     # Stufen-Karte haengt an den Rezepten
                self._bd_plan_cache = None
                self._bd_tree_cache = None
            if _uw:
                try:
                    _u_ids = set()
                    for _uk in _uw.values():
                        _u_ids.add(int(_uk["u"]))
                        _u_ids |= {int(_m) for _m, _q in _uk["mats"]}
                        _u_ids |= {int(_m) for _m in (_uk.get("zurueck_je_run") or {})}
                    _u_fehlt = [_i for _i in _u_ids if _i not in names]
                    if _u_fehlt:
                        names.update(esi.resolve_names(_u_fehlt))
                    # _bd_groups setzt open_build_detail; wird der Detail-
                    # Aufbau frueher erreicht (b-Suite, gespeicherter Plan),
                    # fehlt das Attribut - dann leer anlegen statt Ausnahme
                    # ("'MainWindow' object has no attribute '_bd_groups'",
                    # fehler.log 18.09.2026, sechsmal je Prueflauf).
                    _gm_u = getattr(self, "_bd_groups", None)
                    if _gm_u is None:
                        _gm_u = self._bd_groups = {}
                    _g_fehlt = [_i for _i in _u_ids if _i not in _gm_u]
                    if _g_fehlt:
                        _gm_u.update(industry.group_names(_g_fehlt))
                except Exception as _un:
                    self._log_exception("Reprocessing: Unrefined-Namen", str(_un))
            _plan_fp = (int(type_id), int(qty),
                        repr(sorted((str(k), repr(v))
                                    for k, v in self._bd_opts.items())))
            # EINGEFROREN = der PLAN steht (Nutzer-Spez): kein production_plan-
            # Aufruf, der Schnappschuss vom Einfrier-Zeitpunkt IST der Plan.
            # Nur der Verkaufspreis des Endprodukts (steckt live in
            # _bd_pricemap) fliesst weiter in die Gewinn-Rechnung. Alt-Payloads
            # ohne plan_snapshot behalten das bisherige Verhalten.
            _frozen_plan = self._frozen_snapshot_plan()
            _cached = getattr(self, "_bd_plan_cache", None)
            if _frozen_plan is not None:
                plan = _frozen_plan
            elif _cached and _cached[0] == _plan_fp and _cached[1] is not None:
                plan = _cached[1]
            else:
                try:
                    plan = industry.production_plan(type_id, qty, _pfn,
                                                    self._bd_recipes, self._bd_opts)
                except Exception:
                    plan = plan_ref["plan"]
                # REPROCESSING (Weg B) mit DERSELBEN Preisfunktion wie der
                # Plan - mit Frachtaufschlag, wenn er mitentscheidet: genau
                # dort zahlt sich das kleine Volumen des Erzes aus.
                if self._bd_opts.get("reprocess"):
                    plan = self._reprocess_anwenden(plan, _pfn, names,
                                                    self._bd_opts["reprocess"],
                                                    kredit_pfn=self._bd_pricemap.get)
                    # Die Ersparnis ist mit DIESER Preisfunktion gerechnet -
                    # steckt die Fracht drin, soll die Zeile das sagen.
                    if isinstance(plan.get("reprocess"), dict):
                        plan["reprocess"]["mit_fracht"] = bool(_fr_rate > 0)
                self._bd_plan_cache = (_plan_fp, plan)
            plan_ref["plan"] = plan
            try:
                _rp_karte_nachziehen(plan)
            except Exception as _rk:
                self._log_exception("Reprocessing: Karte nachziehen", str(_rk))
            _mr = getattr(self, "_bd_multi_refresh", None)
            if _mr is not None:
                try:
                    _mr(plan)
                except Exception as _mre:
                    self._log_exception("Multi-Bauplan: Enden-Karte", str(_mre))
            # Fuer den Rezept-Baum: WAS baut der Plan wirklich, und was deckt
            # der Bestand? Der Baum kennt nur die Entscheidung bauen/kaufen -
            # ohne diese beiden Mengen zeigt er "BAUEN" fuer Dinge, die der
            # Runplaner gar nicht einplant (Nutzer-Meldung).
            self._bd_plan_builds = set((plan.get("build_runs") or {}).keys())
            self._bd_plan_stock = set((plan.get("stock_used") or {}).keys())
            # WAS DER PLAN WIRKLICH ZUKAUFT. Ohne diese Menge kann die
            # Rezept-Struktur "aus Bestand gedeckt" nicht von einem echten
            # Zukauf unterscheiden - und ein beruhigendes Wort ueber einem
            # Einkauf waere dieselbe Fehlerklasse mit umgekehrtem Vorzeichen.
            self._bd_plan_buy = set((plan.get("buy") or {}).keys())
            # REPROCESSING (1.0.9, Weg B): welches Mineral kommt aus welchem
            # Erz - fuer die Aktionsspalte des Rezept-Baums (Nutzer 18.09.2026:
            # "im Rezeptbaum noch keine Beschreibung fuer compressed Ores").
            _repro_von = {}
            for _st_r in ((plan.get("reprocess") or {}).get("schritte") or []):
                _erz_nm = str(names.get(_st_r.get("erz")) or _st_r.get("erz"))
                for _m_r in (_st_r.get("deckt") or {}):
                    _repro_von.setdefault(int(_m_r), []).append(_erz_nm)
            self._bd_plan_repro = _repro_von
            # ---- DEN BAUM MITRECHNEN (Sitzung 20) --------------------------
            # NUTZER-BEFUND: Fermionic Condensates stand in der Rezept-Struktur
            # auf "kaufen", obwohl 10.2k im Hangar lagen und "Kosten ignorieren
            # - immer bauen" an war. Nach Schliessen+Neuoeffnen war es weg -
            # vom Nutzer bestaetigt.
            # URSACHE: `rebuild()` rechnete nur den Plan neu. Wo der Plan gar
            # keine Entscheidung setzt - Bedarf voll aus dem Bestand gedeckt,
            # `if D <= 1e-9: continue` in production_plan - faellt die Anzeige
            # ueber `_decision_of` auf die Baum-Entscheidung zurueck, und die
            # stammte vom Oeffnen des Fensters, als `force_build` noch False
            # war (main_window.py, "neuer Plan" setzt `_bd_force = False`).
            # DERSELBE FINGERABDRUCK wie beim Plan: aendert sich keine Option,
            # wird nichts gerechnet. Gemessen: build_tree 1 ms gegen 2 ms Plan.
            # DIESELBE PREISFUNKTION wie der Plan (`_pfn`, also mit
            # Frachtaufschlag, wenn er mitentscheidet) - sonst entstehen wieder
            # zwei Wahrheiten ueber denselben Plan.
            # EINGEFROREN = auch der Baum steht: beim eingefrorenen Plan ist
            # der Schnappschuss die Wahrheit, ein frischer Baum daneben waere
            # genau der Widerspruch, den das Einfrieren verhindern soll.
            if _frozen_plan is None:
                _tc = getattr(self, "_bd_tree_cache", None)
                if _tc and _tc[0] == _plan_fp and _tc[1] is not None:
                    tree_ref["tree"] = _tc[1]
                else:
                    try:
                        _neu_tree = industry.build_tree(
                            type_id, _pfn, self._bd_recipes, self._bd_opts)
                    except Exception:
                        _neu_tree = None      # lieber der alte Baum als keiner
                    if _neu_tree:
                        tree_ref["tree"] = _neu_tree
                        self._bd_tree_cache = (_plan_fp, _neu_tree)
            if hasattr(self, "_bd_mat_tab_tbl"):
                self._fill_material_tab(plan, names, self._bd_mat_tab_tbl,
                                        getattr(self, "_bd_mat_tab_status", None))
            if hasattr(self, "bl_notice_lbl"):
                _hit = plan.get("excluded_hit") or set()
                # ZEILEN OHNE TREFFER melden. Beim Nutzer stand
                # "Gravimietric Sensor Cluster 1455" in der Blacklist -
                # Tippfehler plus angehaengte Menge. Der Abgleich schlug
                # still fehl, und er hielt die ganze Blacklist fuer kaputt.
                # Die Mengen faengt _bl_clean() ab; einen Tippfehler kann
                # niemand raten - also wird er wenigstens BENANNT.
                _bl_raw = [x for x in
                           (self.settings.get("bau_blacklist_names", []) or [])
                           if str(x).strip()]
                _hit_lc = {(_n or "").strip().lower()
                           for _n in store.cached_names(list(_hit)).values()}
                _miss_lines = []
                for _raw in _bl_raw:
                    _c = self._bl_clean_name(_raw)
                    if _c and _c not in _hit_lc:
                        _miss_lines.append(str(_raw).strip())
                if _miss_lines:
                    self.bl_notice_lbl.setText(
                        _txt("\u26a0 {n} blacklist line(s) match NO item in the plan "
                             "\u2013 check the spelling: ").format(n=len(_miss_lines))
                        + ", ".join(_miss_lines[:4])
                        + (f" (+{len(_miss_lines) - 4})"
                           if len(_miss_lines) > 4 else ""))
                    self.bl_notice_lbl.setStyleSheet(f"color:{theme.AMBER};")
                    self.bl_notice_lbl.setVisible(True)
                elif _hit:
                    _hit_names = store.cached_names(list(_hit))
                    _shown = ", ".join(sorted(_hit_names.get(t, f"#{t}") for t in _hit)[:6])
                    _more = (_txt(" (+{n} more)").format(n=len(_hit) - 6)
                             if len(_hit) > 6 else "")
                    self.bl_notice_lbl.setText(
                        _txt("\u26a0 {n} item(s) hidden by the blacklist: ").format(n=len(_hit))
                        + f"{_shown}{_more}")
                    self.bl_notice_lbl.setVisible(True)
                else:
                    self.bl_notice_lbl.setVisible(False)
            # Endprodukt-ME/TE oben synchron zur Invention-Tab-Wahl halten,
            # WENN das Endprodukt selbst über Invention entsteht und Invention
            # aktiv ist: die echten Werte kommen dann vom gewählten Decryptor
            # (2% Basis + Bonus), nicht vom Eingabefeld - das Feld würde sonst
            # "0%" zeigen, obwohl in Wirklichkeit z.B. 4% ME gerechnet werden.
            # Felder werden dafür schreibgeschützt (kein Doppel-Zählen möglich
            # - _invention_me_pct in industry.py ignoriert dieses Feld ohnehin
            # komplett, sobald Invention greift).
            try:
                _bp0 = self._bd_recipes.product_to_bp.get(type_id)
                _inv0 = _bp0 and self._bd_recipes.invention_for_bpc.get(_bp0[0])
                if getattr(self, "_bd_own_bpc", False) and type_id != industry.BUENDEL_ID:
                    # Nutzer hat "Eigene BPC" angehakt: ME/TE oben bleiben frei
                    # editierbar, Invention wird für DIESES Item komplett
                    # ignoriert (kein Invention-Kosten-Posten, ME/TE kommen
                    # normal aus dem Eingabefeld über den bestehenden me_map-
                    # Pfad - nichts doppelt gezählt).
                    if _bp0:
                        self._bd_opts.setdefault(
                            "inv_manual_override", {})[_bp0[0]] = True
                    # DERSELBE RUECKFALL AUCH HIER (Sitzung 19). Der Zweig
                    # oben faengt das Umschalten ab; dieser faengt den Fall,
                    # dass ein Plan mit bereits gesetztem "Eigene BPC"
                    # aufgebaut wird, waehrend die Felder noch unter der
                    # Invention-Sperre stehen. `isEnabled() == False` heisst
                    # genau das: der Wert darin stammt aus der Invention und
                    # gehoert nicht zu einer eigenen Kopie.
                    _obc_me, _obc_te = self._bd_own_bpc_me_te(type_id)
                    if not me_spin.isEnabled():
                        me_spin.setEnabled(True)
                        me_spin.blockSignals(True)
                        me_spin.setValue(_obc_me)
                        me_spin.blockSignals(False)
                        self._bd_me = _obc_me
                        me_spin.setToolTip(_txt("Material efficiency of the FINAL product only."))
                    if not te_spin.isEnabled():
                        te_spin.setEnabled(True)
                        te_spin.blockSignals(True)
                        te_spin.setValue(_obc_te)
                        te_spin.blockSignals(False)
                        self._bd_te = _obc_te
                        te_spin.setToolTip(_txt(
                            "Time efficiency of the FINAL product only – for the build "
                              "time."))
                    # "Eigene BPC" = du hast schon eine eigene Kopie, keine
                    # Invention nötig - echte ESI-Daten nutzen, falls schon
                    # geladen (siehe "🛰 Alles aus ESI laden" oben, läuft beim
                    # Öffnen automatisch). Sonst aus "Runs/BPC" + Ziel-Menge
                    # errechnen, wie viele Kopien wirklich nötig sind - genau
                    # dasselbe Muster wie beim Invention-Zweig unten (jede BPC
                    # ist irgendwann aufgebraucht, keine unbegrenzte BPO).
                    _own_real = self._bd_lookup_owned_bp_for_item(type_id)
                    if _own_real:
                        self._bd_bp["end"] = _own_real
                    else:
                        _runs_per_bpc_e = max(1, int(getattr(
                            self, "_bd_own_bpc_runs", 0) or qty_spin.value() or 1))
                        _target_runs_e = max(1, int(qty_spin.value()))
                        _copies_needed_e = -(-_target_runs_e // _runs_per_bpc_e)  # ceil
                        self._bd_bp["end"] = {"copies": _copies_needed_e,
                                              "runs": _runs_per_bpc_e, "bpo": False,
                                              "runs_known": True}
                    self._bd_refresh_bp_stage_info()
                elif _inv0 and self._bd_opts.get("invention", True):
                    _dv0 = (self._bd_opts.get("inv_decryptor_map") or {}).get(_bp0[0])
                    if _dv0 is None:
                        _dv0 = (self._bd_opts.get("inv_prob_mult", 1.0),
                               self._bd_opts.get("inv_run_mod", 0),
                               self._bd_opts.get("inv_me_mod", 0),
                               self._bd_opts.get("inv_te_mod", 0),
                               self._bd_opts.get("inv_decryptor_id"))
                    _t1_0, _br0, _bp_0, _dcs0 = _inv0
                    _out0 = industry.invention_outcome(_br0, _bp_0, _dv0)
                    for _sp, _val, _attr, _tip in (
                            (me_spin, _out0["me_pct"], "_bd_me",
                             _txt("ME comes from the decryptor chosen in the Invention "
                                  "tab (2% base + bonus) - not editable here, as an "
                                  "invented BPC never has a freely researched ME.")),
                            (te_spin, _out0["te_pct"], "_bd_te",
                             _txt("TE comes from the decryptor chosen in the Invention "
                                  "tab (4% base + bonus) - now also acts directly on "
                                  "the planned build time."))):
                        if _sp.value() != _val:
                            _sp.blockSignals(True)
                            _sp.setValue(_val)
                            _sp.blockSignals(False)
                        setattr(self, _attr, _val)   # Bauzeit-Planung liest
                                                     # self._bd_te/_bd_me direkt,
                                                     # nicht nur das Widget
                        _sp.setEnabled(False)
                        _sp.setToolTip(_tip)
                    # "Kopien" fürs Endprodukt automatisch aus der erwarteten
                    # Anzahl erfolgreicher Invention-Versuche ableiten: JEDER
                    # Erfolg gibt eine EIGENE, NEUE BPC mit den Runs des
                    # gewählten Decryptors - also genau so viele "Kopien", wie
                    # du BPCs bekommen wirst. Damit kann der Runplaner die
                    # Endprodukt-Runs auf mehrere Charaktere gleichzeitig
                    # verteilen, statt (falscherweise) von nur 1 BPC
                    # auszugehen. "Eigene BPC" überschreibt das wie gewohnt
                    # (siehe Zweig oben - unbegrenzt angenommen).
                    _runs_per_bpc = max(1, int(_out0.get("runs", 1) or 1))
                    _target_runs = max(1, int(qty_spin.value()))
                    _successes_needed = -(-_target_runs // _runs_per_bpc)  # ceil
                    self._bd_bp["end"] = {"copies": _successes_needed,
                                          "runs": _runs_per_bpc, "bpo": False,
                                          "runs_known": True}
                    self._bd_refresh_bp_stage_info()
                else:
                    if not me_spin.isEnabled():
                        me_spin.setEnabled(True)
                        me_spin.setToolTip(_txt("Material efficiency of the FINAL product only (usually T2 "
                                                "\u2013 often 0 % as long as the BPC from invention has not "
                                                "been researched separately)."))
                    if not te_spin.isEnabled():
                        te_spin.setEnabled(True)
                        te_spin.setToolTip(_txt(
                            "Time efficiency of the FINAL product only – for the build "
                              "time."))
            except Exception:
                pass
            # Entscheidungen aus dem Plan an die Rezept-Struktur weiterreichen
            # (production_plan ist die Quelle, der Baum zeigt sie nur an).
            plan_dec_ref["decision"] = (plan or {}).get("decision", {}) or {}
            # Fehlende Item-Namen des (evtl. geänderten) Plans nachladen → keine #12345
            if plan:
                miss = [t for t in (set(plan.get("build_runs", {}))
                                    | set(plan.get("buy", {}))
                                    | set(plan.get("stock_used", {}))) if t not in names]
                if miss:
                    try:
                        names.update(esi.resolve_names(miss))
                    except Exception:
                        pass
            total = plan["total_cost"] if plan else tree_ref["tree"]["per_unit"] * qty
            # BESTAND ZU ERSATZKOSTEN (Nutzer-Entscheid: er betreibt die
            # Reaktionskette weiter). Bewertet wird mit
            # `min(Kaufpreis, eigene Baukosten)` aus industry.stock_price_of -
            # was kostet es MICH, diese Einheit zu ersetzen. Zum Jita-Sell zu
            # bewerten hiesse, die Marge fremder Produzenten in die eigenen
            # Kosten zu rechnen: eine BESSERE eigene Reaktionskette liesse das
            # Schiff dadurch teurer aussehen (genau der Sprung 42 -> 64
            # Mio/Stk aus einer frueheren Sitzung).
            # WICHTIG: `stock_cost` steckt bereits in plan["total_cost"] -
            # hier also NICHTS mehr addieren (das war die Doppelzaehlung, die
            # bei Menge 1 aus 44,6 Mio/Stk 73,6 Mio/Stk gemacht hat).
            # `stock_value` = dieselbe Menge zum Kaufpreis, nur noch fuer den
            # Vergleich im Tooltip; geht in KEINE Summe ein.
            stock_cost = float((plan or {}).get("stock_cost", 0.0) or 0.0)
            stock_value = 0.0
            if plan:
                for _tid, _used_qty in (plan.get("stock_used") or {}).items():
                    _price = self._bd_pricemap.get(_tid)
                    if _price:
                        stock_value += _price * _used_qty
            per = total / qty if qty else total
            # Orderbuch-genaue Material-Ladder statt Flachpreis. Gilt jetzt
            # auch nach einer Mengenänderung im Spinner, solange die
            # Orderbücher des letzten Abrufs vorliegen - Gültigkeit
            # entscheidet _bd_ladder_ctx (eine Stelle, auch fürs
            # Decryptor-Ranking).
            # FRACHT VOR DER LADDER (18.09.2026, Befund am Compressed-Ore-
            # Vergleich): mit "Fracht entscheidet mit" und aktiver Orderbuch-
            # Ladder fehlte der Frachtdienst in Gesamtkosten und Gewinn - die
            # Ladder rechnet reine Orderbuchpreise, der Abzug unten nahm aber
            # an, die Fracht stecke im Materialpreis. Deshalb steht der
            # Frachtanteil jetzt VOR der Ladder fest und wird dort addiert.
            # --- Transportvolumen & -kosten der Einkaufsliste (Punkt B) ---
            buy_map = (plan or {}).get("buy", {}) or {}
            buy_surplus = {t: self._buy_surplus_qty(q) for t, q in buy_map.items()}
            vols, _unpkg_ships = self._item_volumes_with_esi_fix(buy_surplus.keys())
            # Steckt der m3-Satz schon im Kaufpreis (Frachtaufschlag aktiv),
            # darf er hier NICHT nochmal berechnet werden - sonst zahlt man
            # ihn zweimal. Die Pauschale pro Fahrt bleibt in jedem Fall hier.
            tinfo = industry.transport_estimate(
                buy_surplus, vols, capacity_m3=transport_ref["cap"],
                mode=None,
                rate_per_m3=(0.0 if _fr_rate > 0 else transport_ref["rate"]),
                trip_cost=transport_ref["trip"])
            tinfo["rate_in_price"] = bool(_fr_rate > 0)
            # WIEVIEL VOM MATERIALPREIS IST FRACHT? Aus DERSELBEN Einkaufsliste
            # und denselben Volumen, aus denen auch die Materialkosten
            # entstanden sind (buy_map x vols x Satz) - keine Nebenrechnung.
            # Nur zum AUSWEISEN: der Betrag steckt bereits in mc und wird
            # nirgends zusaetzlich abgezogen.
            # DREI ZEILEN, DREI EINGABEFELDER (Nutzer: "eine Kost ist zu viel"
            # - es war eine Zeile ZU VIEL BENANNT). transport_estimate liefert
            # beide Anteile schon getrennt; vorher wurden sie als eine Zahl
            # "Transport" angezeigt, fuer die es kein Eingabefeld gibt:
            #   Frachtdienst  <- Feld "Frachtdienst" (ISK/m3) x Volumen
            #   Eigene Fahrt  <- Feld "Eigene Fahrt"  (Pauschale) x Fahrten
            _eigene_fahrt = float((tinfo or {}).get("cost_trip", 0) or 0)
            _fr_in_mat = 0.0
            if _fr_rate > 0:
                try:
                    _fr_in_mat = _fr_rate * sum(
                        float(vols.get(_t, 0) or 0) * float(_q)
                        for _t, _q in buy_map.items())
                except Exception as _fr_err:
                    # de_scan4: aus - Beschriftung fuer fehler.log, nicht Oberflaeche
                    self._log_exception("Bauplan: Frachtanteil", str(_fr_err))
                    # de_scan4: an
            # Der Frachtdienst zaehlt entweder im Materialpreis ODER in der
            # Transportsumme - nie in beiden. Fuer die ANZEIGE ist es dieselbe
            # Zeile; wo er verrechnet wird, sagt der Tooltip.
            _fracht_dienst = _fr_in_mat or float(
                (tinfo or {}).get("cost_m3", 0) or 0)
            _lctx = self._bd_ladder_ctx(qty)
            ladder = (_lctx or {}).get("ladder")
            ladder_active = _lctx is not None
            ladder_shorts = []
            self._bd_ladder_shorts = []
            ladder_no_book = []
            # Vorbelegen, damit der Tooltip-Zweig sie IMMER kennt - auch wenn
            # die Ladder gar nicht aktiv ist. Ein NameError haette hier die
            # ganze Kopfzeile gerissen.
            ladder_avg = []
            ladder_unpriced = []
            if ladder_active:
                # Orderbuch-PREISE bleiben aus der Ladder (gecacht, kein neuer
                # Live-Abruf nötig) - aber die benötigten MENGEN kommen LIVE aus
                # dem gerade frisch berechneten `plan`. Sonst bleibt die Menge
                # (und damit der Materialpreis) auf dem Stand von "Neu
                # berechnen" eingefroren, obwohl sich die Menge mit jedem
                # Decryptor-Wechsel (andere ME) ändert - genau das führte dazu,
                # dass "Beste Wahl" nicht den wirklich profitabelsten Decryptor
                # traf, weil die Kopfzeile dessen Materialersparnis ignorierte.
                _obs = _lctx["obs"]
                if _obs is not None:
                    # Warnungen MIT der Summe holen: sie gelten fuer die
                    # gerade angezeigte Menge, nicht fuer die des Abrufs.
                    # Sonst zeigte eine bei Menge 20 geholte Ladder die
                    # Tiefen-Warnung von Menge 20 neben den Kosten fuer
                    # Menge 200.
                    _avg_map = ((getattr(self, "_bd_opts", None) or {})
                                .get("average_prices") or {})
                    _ldet = industry.ladder_detail_for_buy(
                        (plan or {}).get("buy") or {}, _obs,
                        self._bd_pricemap.get, _avg_map.get)
                    mat_ladder = _ldet["mat_cost"]
                    ladder_shorts = _ldet["short_materials"]
                    ladder_no_book = _ldet["no_book"]
                    ladder_avg = _ldet.get("avg_priced") or []
                    ladder_unpriced = _ldet.get("unpriced") or []
                else:
                    mat_ladder = float(ladder.get("mat_cost_ladder", 0.0) or 0.0)
                    ladder_shorts = list(ladder.get("short_materials") or [])
                # Orderbuchpreise sind OHNE Fracht - mit "Fracht entscheidet
                # mit" gehoert der Frachtanteil dazu, sonst fehlt er in
                # Gesamtkosten und Gewinn (Material-Zeile zieht ihn unten ab).
                if _fr_rate > 0:
                    mat_ladder += _fr_in_mat
                # FUER DEN MATERIALIEN-TAB (Nutzer 18.09.2026: "was passiert,
                # wenn in Jita etwas ausverkauft ist?"): die Knappheit stand
                # nur als Zahl im Tooltip der Baukosten. Der Tab nennt jetzt
                # die Materialien mit "da / gebraucht".
                self._bd_ladder_shorts = list(ladder_shorts or [])
                try:
                    self._knappheit_nachziehen(names)
                except Exception as _kn_err:
                    self._log_exception("Bauplan: Knappheitszeile", str(_kn_err))
                live_job = float((plan or {}).get("job_cost", 0.0) or 0.0)
                live_inv = float((plan or {}).get("inv_cost", 0.0) or 0.0)
                # WICHTIG: der Bestand darf hier NICHT fehlen - dieser Zweig
                # baut total/per komplett neu auf und wuerde ihn sonst
                # stillschweigend auf 0 setzen. Dieselbe Bewertung wie oben:
                # Ersatzkosten aus dem Plan, nicht der Kaufpreis.
                total = mat_ladder + live_job + live_inv + stock_cost
                # RUECKLAEUFER-GUTSCHRIFT (Weg A) auch hier abziehen - dieser
                # Zweig baut `total` neu auf und liess sie weg (Nutzer-Befund
                # 19.09.2026: Plan mit Unrefined 139.8 statt 127.6 M je Stueck,
                # obwohl jede Wahl in der Diagnose guenstiger war; die 435 M
                # Gutschrift fehlten nur in der Summe nach "Recalculate").
                total -= float(((plan or {}).get("reprocess") or {}).get(
                    "ruecklaeufer_wert") or 0.0)
                per = total / qty if qty else total
            # Aufklapp-Zustand merken, damit er bei Mengen-Änderung erhalten bleibt
            _was_exp = set()

            def _collect_exp(item):
                t = item.data(0, Qt.UserRole)
                if t is not None and item.isExpanded():
                    _was_exp.add(int(t))
                for i in range(item.childCount()):
                    _collect_exp(item.child(i))
            for i in range(tw.topLevelItemCount()):
                _collect_exp(tw.topLevelItem(i))
            # --- Rezept-Baum (Struktur, pro Stück) ---
            tw.blockSignals(True)
            tw.clear()
            _tree = tree_ref["tree"]
            cost = _tree["per_unit"]
            oq = _tree.get("output_qty", 1) or 1
            rr = int(-(-qty // oq))
            root_act = (_txt("BUILD \u00b7 {n} run") if rr == 1
                        else _txt("BUILD \u00b7 {n} runs")).format(n=rr)
            _rmr = (getattr(self, "_bd_rig_me_map", {}) or {}).get(type_id, 0)
            if False and _rmr:
                root_act += f"  · Rig \u2212{_rmr:.1f}%"
            root = QTreeWidgetItem([name + _txt("  (end product)"), fmt(qty), root_act,
                                    isk(cost, suffix=False), isk(cost * qty, suffix=False)])
            root.setData(0, Qt.UserRole, type_id)
            root.setFlags(root.flags() | Qt.ItemIsUserCheckable)
            root.setCheckState(0, Qt.Unchecked)
            root.setForeground(0, QColor(theme.AMBER))
            root.setForeground(2, QColor(theme.AMBER))
            tw.addTopLevelItem(root)
            # NACH KATEGORIE SORTIEREN + ANSCHREIBEN (Nutzer: "man erkennt
            # nicht, was welcher Kategorie angehoert, da fehlt mir
            # Uebersicht"). Die Reihenfolge folgt der Bau-Logik: erst die
            # Komponenten, dann Reaktionen, ganz zum Schluss das, was man nur
            # noch einkauft (Mineralien, T1-Huellen). Der Rezeptbaum
            # DARUNTER bleibt unveraendert - nur die oberste Ebene wird
            # geordnet, sonst waere es kein Rezept mehr.
            _rp = getattr(self._bd_recipes, "reaction_products", None) or set()
            _p2b = getattr(self._bd_recipes, "product_to_bp", None) or {}

            # FUEL und TOOLS als eigene Gruppen (Nutzer-Vorgabe) - dieselbe
            # Einteilung wie im Materialien-Baum, damit nicht zwei Schemata
            # nebeneinander laufen. Quelle ist wieder `_category_key`.
            _cm_rt = industry.item_category_map() or {}
            _gm_rt = (getattr(self, "_bd_groups", None)
                      or getattr(self, "_bd_groups_cache", None) or {})

            def _cat_of(_tid):
                if _tid in _rp:
                    # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                    return (4, "Reaktion")
                    # de_scan4: an
                _inf = _cm_rt.get(_tid)
                try:
                    _k = self._category_key(_tid, _gm_rt.get(_tid, ""), False,
                                            _inf[0] if _inf else None,
                                            _inf[2] if _inf else None)
                except Exception:
                    _k = None
                if _k == "t1_hulls":
                    # de_scan2: aus  (Kategorie-SCHLUESSEL, Anzeige via _kategorie_anzeige)
                    return (2, "H\u00fcllen")   # Kategoriename, kein Anzeigetext
                    # de_scan2: an
                if _k == "fuel_blocks":
                    return (3, "Fuel")
                if _k == "tools":
                    return (5, "Tools")
                # Planetary Interaction - eigene Gruppe, s. _fill_material_tab.
                if _inf and _inf[0] in (41, 43):
                    return (6, "PI")
                if _tid in _p2b:
                    # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                    return (1, "Komponente")
                    # de_scan4: an
                # Gleiche Aufteilung wie im Materialien-Tab, gleiche Quelle.
                # "noch nicht aufgeloest" bekommt einen EIGENEN Rang: die
                # Koepfe werden je Rang angelegt - mit demselben Rang wie
                # "Rohstoffe" stuenden unaufgeloeste Items unter einem
                # Rohstoffe-Kopf, und die Markierung waere wieder eine
                # Behauptung.
                _rg = self._bd_rohstoff_gruppe(_gm_rt.get(_tid, ""))
                # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                return ({"Mineralien": 7, "Mond-Materialien": 8,
                         "Rohstoffe": 9}.get(_rg, 10), _rg)
                # de_scan4: an
            _cat_col = {1: theme.CYAN, 2: theme.AMBER, 3: theme.GREEN,
                        4: theme.VIOLET, 5: theme.AMBER, 6: theme.CYAN,
                        7: theme.MUTED, 8: theme.VIOLET, 9: theme.MUTED,
                        10: theme.MUTED}
            _kids = sorted(
                _tree["components"],
                key=lambda _c: (_cat_of(_c.get("type_id"))[0],
                                names.get(_c.get("type_id"), "")))
            # ECHTE GRUPPEN statt nur Etiketten am Item (Nutzer: "Kategorien
            # ... wie im Materialien Tab"). Vorher stand die Kategorie als
            # "  · Komponente" hinter dem Namen und die erste Zeile je Rang war
            # fett - man musste die Zugehoerigkeit Zeile fuer Zeile ablesen.
            # Jetzt: ein Kopfknoten je Kategorie, die Items haengen darunter.
            # Die Sortierung nach Rang (_kids oben) bleibt die Reihenfolge der
            # Koepfe - EINE Quelle fuer Reihenfolge und Gruppierung.
            _headers = {}
            for c in _kids:
                _rank, _lbl = _cat_of(c.get("type_id"))
                _hdr = _headers.get(_rank)
                if _hdr is None:
                    _hdr = QTreeWidgetItem([self._kategorie_anzeige(_lbl), "", ""])
                    root.addChild(_hdr)
                    _hf = _hdr.font(0); _hf.setBold(True); _hdr.setFont(0, _hf)
                    _hdr.setForeground(0, QColor(_cat_col.get(_rank, theme.MUTED)))
                    # Kein Haken am Kopf: er ist kein Material, das man
                    # "erledigt" abhaken koennte.
                    _hdr.setFlags(_hdr.flags() & ~Qt.ItemIsUserCheckable)
                    _hdr.setToolTip(0, _txt("Category: ") + self._kategorie_anzeige(_lbl))
                    _headers[_rank] = _hdr
                add_node(_hdr, c, rr)
                _it = _hdr.child(_hdr.childCount() - 1)
                _it.setToolTip(0, (_it.toolTip(0) + "\n" if _it.toolTip(0)
                                   else "") + _txt("Category: ") + self._kategorie_anzeige(_lbl))
            for _rank, _hdr in _headers.items():
                # Anzahl in den Kopf - so sieht man zugeklappt, wie viel
                # dahintersteckt.
                _hdr.setText(0, f"{_hdr.text(0)}   ({_hdr.childCount()})")
                _hdr.setExpanded(True)
            # KOMPRIMIERTES ERZ (1.0.9, Weg B; Nutzer 19.09.2026: "Rezept-
            # Struktur hat keine Eintragsmoeglichkeit fuer Ore"): das Erz ist
            # kein Rezept-Bestandteil, deshalb stand es nirgends im Baum. Ein
            # eigener Kopf unter den Kategorien: je Erz Menge, was es liefert,
            # Ausbeute. Zeilen sind Anzeige, kein Haken (nichts zu "erledigen").
            _rp_tree = (plan_ref.get("plan") or {}).get("reprocess") or {}
            _erz_steps = [_s for _s in (_rp_tree.get("schritte") or [])
                          if _s.get("art") != "unrefined"]
            if _erz_steps:
                # de_scan5: aus - Kategorie-SCHLUESSEL, Anzeige via _kategorie_anzeige
                _ehdr = QTreeWidgetItem([self._kategorie_anzeige("Erz")
                                         + f"   ({len(_erz_steps)})", "", ""])
                # de_scan5: an
                root.addChild(_ehdr)
                _ehf = _ehdr.font(0); _ehf.setBold(True); _ehdr.setFont(0, _ehf)
                _ehdr.setForeground(0, QColor(theme.GREEN))
                _ehdr.setFlags(_ehdr.flags() & ~Qt.ItemIsUserCheckable)
                _ehdr.setToolTip(0, _txt("Compressed ore the plan buys instead of "
                                         "minerals \u2013 reprocessed at {struct}.").format(
                    struct=str(_rp_tree.get("struct") or "")))
                for _s in _erz_steps:
                    _eid = int(_s.get("erz") or 0)
                    _eact = "\u267b " + _txt("reprocess \u2192 {out} \u00b7 {pct} %").format(
                        out=", ".join(
                            f"{int(_q):,}".replace(",", "'") + " " + names.get(_m, f"#{_m}")
                            for _m, _q in sorted((_s.get("deckt") or {}).items())),
                        pct=f"{float(_s.get('ausbeute') or 0) * 100.0:.1f}")
                    if _s.get("gratis"):
                        _eact = _txt("on blacklist \u2013 provided, not bought") + "  \u00b7  " + _eact
                    _eit = QTreeWidgetItem([names.get(_eid, f"#{_eid}"),
                                            fmt(int(_s.get("menge") or 0)), _eact])
                    _eit.setData(0, Qt.UserRole, _eid)
                    _eic = self._table_icon(_eid)
                    if _eic:
                        _eit.setIcon(0, _eic)
                    _eit.setFlags(_eit.flags() & ~Qt.ItemIsUserCheckable)
                    _eit.setTextAlignment(1, Qt.AlignRight | Qt.AlignVCenter)
                    _eit.setForeground(0, QColor(_TIER_COLORS[1]))
                    _eit.setForeground(2, QColor(theme.GREEN))
                    _ehdr.addChild(_eit)
                _ehdr.setExpanded(True)
            # STANDARD-AUFKLAPPZUSTAND, explizit und in EINER Richtung gesetzt
            # (Nutzer: "so standardmaessig ausgeklappt wie im Bild"):
            #   Endprodukt auf  ->  Kategorie-Koepfe auf  ->  alles darunter zu.
            # Vorher wurde das an drei Stellen nebenbei gesetzt (root hier, die
            # Koepfe in ihrer Schleife, die Items gar nicht) - und ob ein
            # setExpanded VOR dem Aufklappen des Elternteils haengenbleibt, ist
            # Qt-Reihenfolgeglueck. Jetzt einmal am Ende, deterministisch.
            root.setExpanded(True)

            def _collapse_below(_it):
                for _i in range(_it.childCount()):
                    _c = _it.child(_i)
                    _c.setExpanded(False)
                    _collapse_below(_c)
            for _hdr in _headers.values():
                _collapse_below(_hdr)      # Materialien und ihre Unterbaeume zu
                _hdr.setExpanded(True)     # der Kopf selbst auf
            restore = getattr(self, "_bd_restore_checked", None)
            if restore:
                def _apply_check(item):
                    t = item.data(0, Qt.UserRole)
                    if t is not None and int(t) in restore:
                        item.setCheckState(0, Qt.Checked)
                        f = item.font(0); f.setStrikeOut(True)
                        for cc in range(tw.columnCount()):
                            item.setFont(cc, f)
                    for i in range(item.childCount()):
                        _apply_check(item.child(i))
                for i in range(tw.topLevelItemCount()):
                    _apply_check(tw.topLevelItem(i))
                self._bd_restore_checked = None      # nur einmal anwenden
            # ESI-Live-Jobs: Items, die laut zuletzt geladenen ESI-Daten (\u201e\U0001F504
            # Live-Jobs laden\u201c im Bau-Kalender) GERADE von einem deiner Bau-/
            # Reaktions-Charaktere gebaut werden, automatisch markieren \u2013 nicht
            # nur einmalig wie restore, sondern bei JEDEM rebuild() (Menge \u00e4ndern
            # etc.), da sich die Live-Daten unabh\u00e4ngig \u00e4ndern k\u00f6nnen.
            _esi_ids = set()
            _live_jobs = self.settings.get("bau_live_jobs", []) or []
            if _live_jobs:
                _relevant_chars = set()
                _cmap_bc = {c["character_id"]: (c.get("character_name") or str(c["character_id"]))
                           for c in store.list_characters()}
                for _cid in (set(self.settings.get("bau_build_chars", []) or []) |
                            set(self.settings.get("bau_reaction_chars", []) or [])):
                    _relevant_chars.add(_cmap_bc.get(_cid, str(_cid)))
                for _jb in _live_jobs:
                    if _jb.get("char") in _relevant_chars and _jb.get("product_type_id"):
                        _esi_ids.add(int(_jb["product_type_id"]))
            if _esi_ids:
                def _apply_esi(item):
                    t = item.data(0, Qt.UserRole)
                    if t is not None and int(t) in _esi_ids:
                        # DURCHSTREICHEN nur bei Zwischenstufen: dort heisst es
                        # "laeuft schon, nicht nochmal einplanen". Auf dem
                        # ENDPRODUKT las es sich, als waere der ganze Plan
                        # ungueltig (Nutzer-Meldung) - dabei ist genau das das
                        # Item, das man bauen WILL. Dort nur einfaerben und im
                        # Tooltip sagen, was los ist.
                        # BUENDEL: JEDES ENDE IST EIN ENDPRODUKT (Nutzer-
                        # Befund 21.09.2026, Screenshot "warum ist Flycatcher
                        # violett?"). `== type_id` trifft beim Multi-Bauplan
                        # NIE zu - dort ist `type_id` die Buendel-ID (-1).
                        # Folge: ein Ende, fuer das gerade ein Job laeuft,
                        # wurde wie eine ZWISCHENSTUFE behandelt -
                        # durchgestrichen ("laeuft schon, nicht nochmal
                        # einplanen") und mit dem falschen Tooltip. Bei dem
                        # Item, das man bauen WILL, ist das die falsche
                        # Aussage - genau deshalb gibt es die Unterscheidung.
                        # In Schritt 2 (19.09.2026) wurde diese Frage ueberall
                        # auf `_bd_enden` umgestellt; diese eine Stelle wurde
                        # dabei uebersehen.
                        _is_root = (int(t) == int(type_id)
                                    or int(t) in self._bd_enden(type_id))
                        if not _is_root:
                            f = item.font(0); f.setStrikeOut(True)
                            for cc in range(tw.columnCount()):
                                item.setFont(cc, f)
                        for cc in range(tw.columnCount()):
                            item.setForeground(cc, QColor(theme.VIOLET))
                        item.setToolTip(0, (
                            _txt("\u23f3 A job for this item is running per ESI right "
                                 "now.\nThis is your end product \u2013 the plan stays "
                                 "valid. Just check whether you really want to build "
                                 "MORE.")
                            if _is_root else
                            _txt("\u23f3 Running per ESI right now (live jobs) \u2013 do "
                                 "not plan it extra.")))
                    for i in range(item.childCount()):
                        _apply_esi(item.child(i))
                for i in range(tw.topLevelItemCount()):
                    _apply_esi(tw.topLevelItem(i))
            if _was_exp:                              # Aufklapp-Zustand wiederherstellen
                def _apply_exp(item):
                    t = item.data(0, Qt.UserRole)
                    if t is not None and int(t) in _was_exp:
                        item.setExpanded(True)
                    for i in range(item.childCount()):
                        _apply_exp(item.child(i))
                for i in range(tw.topLevelItemCount()):
                    _apply_exp(tw.topLevelItem(i))
            tw.blockSignals(False)
            # --- Bau-Reihenfolge (von unten nach oben) ---
            # --- Bau-Reihenfolge, kategorisiert (Jobs to Run) ---
            from collections import defaultdict as _dd
            bo_tree.clear()
            seq = (plan or {}).get("build_seq", [])
            surp = (plan or {}).get("surplus", {})
            groups = getattr(self, "_bd_groups", {})
            rp = self._bd_recipes.reaction_products
            # --- Invention ZUERST (eigener Slot, blockiert keine Bau-/Reaktions-
            # Slots) - eigene Kategorie oben in der Liste, separat von der
            # normalen Fertigung des Items (die bleibt zusätzlich in ihrer
            # üblichen Kategorie stehen, z.B. Endprodukt/Components). Menge kommt
            # aus self._bd_invention_needs (vom Invention-Tab live gepflegt).
            inv_needs = getattr(self, "_bd_invention_needs", None) or {}
            inv_rows = []
            for tid, _runs in seq:
                bp = self._bd_recipes.product_to_bp.get(tid)
                if not bp or not self._bd_recipes.invention_for_bpc.get(bp[0]):
                    continue
                need = inv_needs.get(bp[0]) or {}
                inv_rows.append((tid, need.get("attempts"), need.get("successes_needed")))
            if inv_rows:
                _n_jobs = len(inv_rows)
                inv_parent = QTreeWidgetItem([
                    _txt("Invention ({n} jobs)").format(n=_n_jobs),
                    "", "", ""])
                inv_parent.setToolTip(0, _txt("Own slot (science) - blocks no build/reaction "
                                              "slots. Can be scheduled first/in parallel."))
                inv_bg = QColor(theme.CYAN); inv_bg.setAlpha(38)
                ipf = inv_parent.font(0); ipf.setBold(True)
                ipf.setPointSize(ipf.pointSize() + 1)
                inv_parent.setFont(0, ipf)
                for col in range(4):
                    inv_parent.setBackground(col, QBrush(inv_bg))
                inv_parent.setForeground(0, QColor(theme.CYAN))
                bo_tree.addTopLevelItem(inv_parent)
                for tid, attempts, succ in inv_rows:
                    att_txt = f"{attempts:,}".replace(",", "'") if attempts else "\u2013"
                    succ_txt = f"{succ:,}".replace(",", "'") if succ else "\u2013"
                    ich = QTreeWidgetItem([
                        res["names"].get(tid, f"#{tid}") + _txt(" \u2013 invention attempts"),
                        att_txt, succ_txt, "\u2013"])
                    ich.setToolTip(0, _txt("Attempts (column \u201eRuns\u201c) \u00b7 required successes "
                                           "(column \u201eUnits\u201c) - details/decryptor choice in "
                                           "the Invention tab."))
                    for col in (1, 2, 3):
                        ich.setTextAlignment(col, Qt.AlignRight | Qt.AlignVCenter)
                    inv_parent.addChild(ich)
                inv_parent.setExpanded(False)
            # Stufen-Map aus der echten Rezept-Kette (Stufe 1 = Produkt geht in
            # weitere Reaktion, Stufe 2 = geht direkt in den Bau). Einmal je
            # Bauplan berechnet und gecacht.
            stage_map = getattr(self, "_bd_reaction_stages", None)
            if stage_map is None:
                try:
                    stage_map = industry.reaction_stage_map(self._bd_recipes)
                except Exception:
                    stage_map = {}
                self._bd_reaction_stages = stage_map

            _enden_kat = self._bd_enden(type_id)   # Buendel: jedes Ende

            def categorize(tid):
                if tid in _enden_kat:
                    return (6, _txt("End product"))
                if tid in rp:
                    st = stage_map.get(tid, 2)
                    if st == 1:
                        return (1, _txt("\u2697 Reactions \u00b7 stage 1 (\u2192 further reaction)"))
                    return (2, _txt("\u2697 Reactions \u00b7 stage 2 (\u2192 build)"))
                g = groups.get(tid, "") or ""
                if "Construction Component" in g:
                    return (4, _txt("Advanced Components"))
                return (5, _txt("Other (fuel blocks, components)"))

            cats = _dd(list)
            for tid, runs in seq:
                cats[categorize(tid)].append((tid, runs))
            for key in sorted(cats.keys()):
                items = cats[key]
                parent = QTreeWidgetItem([key[1] + _txt("   ({n} jobs)").format(n=len(items)), "", "", ""])
                # Dieselben Phasenfarben wie im Runplaner (Reaktionen violett,
                # Komponenten blau, Endprodukt amber) + Hintergrund-Tönung, damit
                # Kategorien wie echte Abschnitte aussehen, nicht wie Tabellenzeilen.
                cat_color = (theme.VIOLET if key[0] <= 3 else
                            theme.AMBER if key[0] == 6 else theme.BLUE)
                cbg = QColor(cat_color); cbg.setAlpha(38)
                pf = parent.font(0); pf.setBold(True); pf.setPointSize(pf.pointSize() + 1)
                parent.setFont(0, pf)
                for col in range(4):
                    parent.setBackground(col, QBrush(cbg))
                parent.setForeground(0, QColor(cat_color))
                bo_tree.addTopLevelItem(parent)
                for tid, runs in items:
                    bp = self._bd_recipes.product_to_bp.get(tid)
                    oqi = (bp[2] if bp else 1) or 1
                    stk = runs * oqi
                    ov = int(round(surp.get(tid, 0)))
                    ch = QTreeWidgetItem([res["names"].get(tid, f"#{tid}"),
                                          f"{runs:,}".replace(",", "'"),
                                          f"{int(stk):,}".replace(",", "'"),
                                          f"{ov:,}".replace(",", "'") if ov else "\u2013"])
                    for col in (1, 2, 3):
                        ch.setTextAlignment(col, Qt.AlignRight | Qt.AlignVCenter)
                    if ov:
                        ch.setForeground(3, QColor(theme.AMBER))
                    parent.addChild(ch)
                parent.setExpanded(False)
            # --- Kopfzeile (Kennzahl-Boxen) ---
            # Groesseres 3D-Render (Nutzer: "mehr wie ein Spiel aussehen").
            # _icon_html_hero faellt automatisch auf das kleine Icon zurueck,
            # wenn es kein Render gibt (Module/Komponenten haben keins).
            st_title.setText(f'{self._icon_html_hero(type_id, size=72)}{name}   '
                             f'<span style="color:{theme.AMBER}; '
                             f'font-size:25px; font-weight:800;">×{qty}</span>')
            st_cost.setText(isk(per))
            st_total.setText(isk(total))
            # AUFSCHLUESSELUNG: seit der Bestand mitzaehlt, ist "Gesamt" nicht
            # mehr dasselbe wie "was ich noch ausgeben muss". Beide Lesarten
            # bleiben ablesbar, statt eine davon still zu verlieren.
            # DIESELBE Zahl wie in `total` und in der Aufschluesselung
            # ("Bestand (Ersatzkosten)"): plan["stock_cost"]. Hier stand
            # zwischenzeitlich der Kaufwert - eine zweite Bewertung desselben
            # Bestands, direkt neben einer Summe, in der sie nicht steckt.
            _sc = float(stock_cost or 0)
            _mc = float((plan or {}).get("mat_cost", 0) or 0)
            _jc = float((plan or {}).get("job_cost", 0) or 0)
            _ic = float((plan or {}).get("inv_cost", 0) or 0)
            _tt = [_txt("Total cost of this build plan:"),
                   "  " + _txt("Material to BUY: ") + isk(_mc)]
            if _sc:
                _tt.append("  " + _txt("Material from STOCK: ") + isk(_sc))
            _tt.append("  " + _txt("Job cost: ") + isk(_jc))
            if _ic:
                _tt.append("  " + _txt("Invention: ") + isk(_ic))
            # WEG A: der Ruecklaeufer senkt die Gesamtkosten, nicht die
            # Einkaufsliste - als eigener Posten sichtbar, nie still.
            _rlw = float(((plan or {}).get("reprocess") or {}).get("ruecklaeufer_wert") or 0.0)
            if _rlw:
                _tt.append("  " + _txt("Returned after reprocessing (credit): ")
                           + "\u2212" + isk(_rlw))
            if _sc:
                _tt += ["",
                        _txt("The stock deliberately counts - it once cost you ISK. "
                             "Valued at REPLACEMENT COST: what it costs you to put "
                             "the unit back, via the cheaper of the two ways (buy OR "
                             "build yourself)."),
                        _txt("You only have to spend fresh: ") + isk(total - _sc)]
                if stock_value > 0 and abs(stock_value - _sc) > 1:
                    _tt.append(
                        _txt("At the pure purchase price it would be {isk} ({pct} %) - "
                             "that difference is other producers' margin and does not "
                             "belong in your cost.").format(
                            isk=isk(stock_value),
                            pct=f"{(stock_value / _sc - 1) * 100:+.1f}"))
            st_total.setToolTip("\n".join(_tt))
            # Bestandsanteil SICHTBAR machen: der Nutzer hielt die gestiegene
            # Summe fuer einen Rechenfehler, weil nirgends stand, wieviel
            # davon aus eigenem Material kommt.
            if _sc:
                st_total.sub_lbl.setText(_txt("of which {isk} from stock").format(isk=isk(_sc)))
                st_total.sub_lbl.setVisible(False)
            else:
                st_total.sub_lbl.setVisible(False)
            if ladder_active:
                st_cost.setStyleSheet("font-size:19px; font-weight:700; "
                                      f"color:{theme.GREEN};")
                _ltip = [_txt("Order-book exact: real sell-order prices of "
                              "the build materials at the chosen hub, not the flat "
                              "price.")]
                if not (_lctx or {}).get("same_qty", True):
                    # Ehrlich bleiben: die MENGEN sind live, die PREISE stammen
                    # vom letzten Abruf. Das ist der Preis dafuer, dass die
                    # Menge ohne Klick durchrechnet.
                    _ltip.append(
                        _txt("\u2139 Quantities calculated live, order book prices "
                             "from the last \u201eRecalculate\u201c (fetched at quantity "
                             "{qty}). Click again for fresh prices.").format(
                                 qty=(_lctx or {}).get('qty')))
                if ladder_shorts:
                    _ltip.append(_txt("\u26a0 {n} material(s) not available at the hub in "
                                      "the full required depth \u2013 rest estimated "
                                      "conservatively at the most expensive known "
                                      "price.").format(n=len(ladder_shorts)))
                if ladder_no_book:
                    _ltip.append(_txt("\u26a0 {n} material(s) only on the shopping list at "
                                      "this quantity \u2013 no order book for them, "
                                      "calculated at the flat price.").format(
                        n=len(ladder_no_book)))
                # NICHTS AM MARKT -> CCP-DURCHSCHNITT (Nutzer, Sitzung 14).
                # Die Zahl ist grob (serverweiter Schnitt ueber ALLE Regionen,
                # kein Hub-Preis) und darf deshalb nicht aussehen wie eine
                # orderbuch-genaue - sie wird hier benannt.
                if ladder_avg:
                    _ltip.append(_txt(
                        "\u26a0 {n} material(s) are currently NOWHERE in the order book "
                        "\u2013 valued at the CCP average price (server-wide average, "
                        "not a hub price). You will probably not find them when "
                        "buying in Jita.").format(n=len(ladder_avg)))
                # KEIN PREIS ZU BEKOMMEN: diese Menge FEHLT in der Summe.
                # Frueher fiel sie still auf 0 und machte den Plan doppelt so
                # guenstig, wie er ist (Nutzer-Befund Sitzung 14).
                if ladder_unpriced:
                    _ltip.append(_txt(
                        "\u26d4 {n} material(s) without ANY price \u2013 neither order "
                        "book nor flat price nor average. These costs are MISSING from "
                        "the total, so the build cost is too low.").format(
                        n=len(ladder_unpriced)))
                _cost_src_tip = " ".join(_ltip)
            else:
                st_cost.setStyleSheet("font-size:19px; font-weight:700; "
                                      f"color:{theme.CYAN};")
                _cost_src_tip = _txt("Flat price (current market scan) \u2013 for order-"
                                     "book-exact numbers click \u201eRecalculate\u201c (hub "
                                     "selectable next to it).")
            plan_ref["transport"] = tinfo
            # Fuer die Kapazitaets-Warnung beim Einkaufswagen: die
            # Transportzeile verschwindet aus der Anzeige, die WARNUNG darf
            # nicht mit ihr verschwinden.
            self._bd_transport = dict(tinfo)
            transport_cost = tinfo["cost"]
            # ZUSATZKOSTEN (Nutzer-Wunsch): einmaliger Betrag fuer den GANZEN
            # Bauplan, z.B. gekaufte BPCs. Wird wie Transport behandelt -
            # gehoert nicht in die Baukosten je Stueck (sonst verzerrt er die
            # Kauf-oder-Bau-Entscheidung jedes Materials), aber sehr wohl in
            # Gewinn und Marge.
            extra_cost = float(self.settings.get("bau_extra_cost", 0) or 0)
            marge = None
            fees = 0.0
            # OHNE VERKAUFSPREIS GIBT ES DIESE ZAHLEN NICHT.
            # Nutzer "buyenne", 15.09.2026 (Discord): Hel und Phoenix
            # stuerzten beim Oeffnen ab, Stork und Avalanche nicht. Grund:
            # Capitals haben in Jita praktisch keine Sell-Orders - sind dann
            # auch keine Contract-Preise geladen, bleibt `_sell_eff` leer.
            # Der ganze Gewinn-Block haengt aber an der Bedingung
            # `_sell_eff` (Anker von aa353 - HIER NICHT WOERTLICH
            # hinschreiben, sonst findet die Pruefung den Kommentar statt
            # der Verzweigung und meldet falsch), und die
            # rechte Spalte liest `gross`/`prof` danach BEDINGUNGSLOS:
            #   UnboundLocalError: cannot access local variable 'gross'
            # `marge` und `fees` waren vorbelegt, diese hier wurden beim
            # Nachruesten der Spalte vergessen.
            # KEINE 0 ALS VORGABE: eine 0 im Feld "Gewinn" liest sich wie ein
            # gerechnetes Ergebnis - und das waere eine erfundene Zahl. None
            # macht `_pset` zu einem Strich, so wie der Kopf es ohne Preis
            # auch schon tut. Waechter: b7d in test_bauplan_aufbau.py.
            gross = None
            prof = None
            prof_raw = None
            total_all = None

            def _r(lbl, val, col=None, bold=False):
                """Eine Tooltip-Tabellenzeile: Beschriftung links, Zahl rechts.
                BEWUSST HIER und nicht im Gewinn-Block: der Baukosten-Tooltip
                nutzt ihn ebenfalls, und der wird auch dann gebaut, wenn keine
                Gebuehren anfallen (fees == 0). Im inneren Block definiert
                waere er dort ein NameError."""
                _st = f"color:{col};" if col else ""
                if bold:
                    _st += "font-weight:700;"
                return (f"<tr><td style='padding:1px 10px 1px 0;'>{lbl}</td>"
                        f"<td align='right' style='{_st}'>{val}</td></tr>")

            _hubk = getattr(self, "_bd_sell_hub", None)
            tax, broker, _fee_src = self._fees_for_hub(
                self.settings, getattr(self, "_bd_sell_char", None),
                _hubk if isinstance(_hubk, str) else None)
            # Verkaufspreis des gewaehlten Hubs, falls schon geholt.
            # WICHTIG: NICHT an `sell` zuweisen! `sell` stammt aus dem
            # umgebenden _show_build_detail; eine Zuweisung hier machte es zur
            # LOKALEN Variable von rebuild() - und der Lesezugriff weiter oben
            # knallte als UnboundLocalError (vom Nutzer gemeldet). Genau die
            # Fehlerklasse, fuer die lint_order.py da ist; sie hat sie in
            # dieser Form (Closure-Shadowing in verschachtelter Funktion)
            # aber nicht erkannt - Pruefung dort nachgeruestet.
            _hp = getattr(self, "_bd_hub_sell_price", None)
            _sell_eff = float(_hp) if _hp else sell
            # BUENDEL: Verkaufswert = Summe Preis x AKTUELLE Menge je Ende.
            # `sell` und `_bd_hub_sell_price` entstanden beim Oeffnen bzw. beim
            # Hub-Wechsel mit den DAMALIGEN Mengen (Befund 26.09.2026, s. o.:
            # Prowler 10 statt 1 aenderte den Gewinn oben nicht). Preise je
            # Ende: vom gewaehlten Hub, sonst aus dem Scan.
            if int(type_id) == industry.BUENDEL_ID and getattr(self, "_bd_buendel_enden", None):
                _je_sell = ((getattr(self, "_bd_hub_sell_je_ende", None) or {})
                            if _hp else (getattr(self, "_bd_pricemap", None) or {}))
                _sell_eff = float(self._multi_buendel_verkauf(
                    _je_sell, self._bd_buendel_enden) or 0.0)
            # CONTRACT-PREIS ALS QUELLE (Nutzer, Sitzung 9: "Gewinn ist
            # absoluter Quatsch" - Capitals haben in Jita praktisch keine
            # echten Sell-Orders, ein einzelner Hoffnungspreis stand als
            # Verkaufswert im Kopf). Werkzeuge -> "Contract-Preise laden"
            # setzt _bd_contract_sell; dann gilt der MEDIAN der
            # oeffentlichen New-Eden-Contracts und schlaegt Jita UND
            # Hub-Preis (Median statt Mittelwert wegen Scam-Ausreissern,
            # s. scanner.aggregate_contract_prices).
            # NEUER Name statt Zuweisung an sell_is_contract - das waere
            # exakt die oben dokumentierte Closure-Falle (UnboundLocal).
            _ct9 = getattr(self, "_bd_contract_sell", None)
            if _ct9 and _ct9.get("median"):
                _sell_eff = float(_ct9["median"])
            _ct_active9 = bool(_ct9 and _ct9.get("median")) or sell_is_contract
            # ZIELPREIS: zu welchem St\u00fcckpreis muss/kann ich verkaufen?
            # Auch OHNE Marktpreis sinnvoll - der Mindestpreis h\u00e4ngt nur an
            # den eigenen Kosten. Beim eingefrorenen Plan friert er
            # automatisch mit, weil Baukosten UND Marktpreis aus der
            # eingefrorenen Preistabelle kommen (genau der Nutzer-Fall:
            # "damit ich in 1-2 Wochen wei\u00df, zu welchem Preis ich verkaufen
            # muss").
            try:
                self._note_depth_cost(total / max(1, int(qty or 1)))
            except Exception:
                pass
            _rec = self._recommended_sell_price(
                total, qty, tax, broker, market_sell=_sell_eff,
                transport_cost=transport_cost, extra_cost=extra_cost)
            if _rec:
                # Nutzer-Vorgabe: die Karte zeigt den MINDESTPREIS (Break-even),
                # nicht den Unterbietungspreis. Das ist die Zahl, unter der
                # man Verlust macht - sie gilt auch noch in zwei Wochen, waehrend
                # der Unterbietungspreis von der Marktlage abhaengt. Der steht
                # jetzt in der Unterzeile bzw. im Tooltip.
                st_target.setText(isk(_rec["break_even"]))
                _frz = bool(getattr(self, "_bd_frozen", None))
                if _rec["can_undercut"] is False:
                    st_target.setStyleSheet(
                        f"font-size:19px; font-weight:700; color:{theme.RED};")
                    # NICHT hier in `_tip` schreiben: die Liste wird erst
                    # WEITER UNTEN gebaut - an dieser Stelle ist `_tip` noch
                    # eine Zeichenkette aus dem umgebenden Code, und
                    # `.insert()` darauf liess jeden Bauplan abstuerzen
                    # (AttributeError: 'str' object has no attribute
                    # 'insert'). Die Warnung wird jetzt gemerkt und nach dem
                    # Aufbau der Liste vorangestellt.
                    _tip_warn = _txt("\u26a0 THE MARKET IS BELOW YOUR MINIMUM PRICE "
                                     "\u2013 at this price you make a loss.")
                    st_target.sub_lbl.setText(
                        _txt("\u26a0 Market is BELOW your minimum price"))
                    st_target.sub_lbl.setVisible(False)
                else:
                    _tip_warn = None
                    st_target.setStyleSheet(
                        "font-size:19px; font-weight:700; color:"
                        + (theme.GREEN if _rec["can_undercut"] else theme.AMBER))
                    st_target.sub_lbl.setText(
                        (_txt("Undercut market: ") + isk(_rec["undercut"]))
                        if _rec["undercut"] is not None else _txt("no market price"))
                    st_target.sub_lbl.setVisible(False)
                _tip = [
                    _txt("Target price per unit for your sell order."),
                    "",
                    _txt("Minimum price (0 profit): ") + isk(_rec['break_even']),
                    "   = (" + _txt("build cost ") + isk(total)
                    + ((" + " + _txt("transport ") + isk(transport_cost))
                       if transport_cost else "")
                    + ") \u00f7 " + _txt("{n} units").format(n=max(1, int(qty or 1))),
                    "   \u00f7 (1 \u2212 " + _txt("{pct} % fees").format(
                        pct=f"{(tax + broker) * 100:.2f}") + ")"]
                if _rec["undercut"] is not None:
                    _tip += ["",
                             _txt("Market (cheapest sell order): ") + isk(_sell_eff),
                             _txt("Undercut: ") + isk(_rec['undercut'])]
                    if _rec["can_undercut"]:
                        _tip.append(
                            _txt("\u2192 You can undercut and earn ")
                            + isk((_rec["undercut"] - _rec["break_even"])
                                  * (1 - tax - broker) * max(1, int(qty or 1)))
                            + _txt(" in total."))
                    else:
                        _tip.append(_txt(
                            "\u2192 Undercutting would only work at a LOSS. The target "
                            "price stays the minimum price \u2013 so you are above the "
                            "market and do not sell for now."))
                else:
                    _tip += ["", _txt("No market price available \u2013 only the minimum "
                                      "price is known.")]
                if _frz:
                    _tip += ["", _txt(
                        "Plan frozen: build cost AND market price come "
                        "from the freeze day \u2013 so this target price no longer "
                        "changes, even if you only get to Jita in two weeks. The "
                        "MARKET there may have moved since; the minimum price still "
                        "applies.")]
                if _tip_warn:
                    _tip = [_tip_warn, ""] + _tip
                st_target.setToolTip("\n".join(_tip))
            else:
                st_target.setText("\u2013")
                st_target.sub_lbl.setVisible(False)
            # STUECKZAHL VOR DIE VERZWEIGUNG (Absturz beim Nutzer, Sitzung 20:
            # "UnboundLocalError: cannot access local variable '_q'").
            # `_q` wurde nur im Zweig MIT Verkaufspreis gesetzt, weiter unten
            # aber immer gebraucht (Kosten je Stueck im Tooltip). Ein Plan
            # ohne Verkaufspreis - bei ihm die Capital-Blaupausen mit "no
            # contract price" - riss das Fenster damit auf.
            _q = max(1, int(qty or 1))
            if _sell_eff:
                st_sell.setText((" " if _ct_active9 else "")
                                + isk(_sell_eff))
                if _ct9 and _ct9.get("median"):
                    _fb9 = int(_ct9.get("from_bundles") or 0)
                    st_sell.setToolTip(
                        _txt("Sale price = MEDIAN of public contracts across all of New "
                             "Eden (Tools \u2192 \u201eLoad contract prices\u201c).\n")
                        + _txt("{n} contract(s)").format(n=int(_ct9.get('count') or 0))
                        + (_txt(", {n} of them derived from bundles").format(n=_fb9) if _fb9
                           else "")
                        + (_txt(" \u00b7 mean: {v}").format(v=isk(_ct9['mean']))
                           if _ct9.get("mean") else "")
                        + (_txt(" \u00b7 range: {lo} \u2013 {hi}").format(
                               lo=isk(_ct9['min']), hi=isk(_ct9['max']))
                           if _ct9.get("min") is not None else "")
                        + _txt("\n\nMedian instead of mean: a few fantasy prices distort "
                               "the mean, not the median. ESI does not see "
                               "alliance-internal contracts."))
                elif sell_is_contract:
                    st_sell.setToolTip(
                        _txt(
                            "No market price available (capital ship) – this is "
                              "the median price from public contracts (load contract "
                              "prices in the capital area of the scanner). Not a "
                              "real market price, only a reference value – "
                              "alliance-internal contracts are not included."))
                # Verkaufsgebühren des Endprodukts abziehen: beim Verkauf per
                # Sell-Order zahlst du Sales Tax + Broker Fee (Materialeinkauf per
                # Multibuy aus Sell-Orders ist gebührenfrei -> nur Verkaufsseite).
                gross = _sell_eff * qty
                self._bd_brutto_stand = gross     # b-Suite: Verkaufswert folgt der Menge
                fees = gross * (tax + broker)
                prof = gross - fees - total - transport_cost - extra_cost
                prof_raw = gross - total - transport_cost - extra_cost  # OHNE Sales Tax/Broker Fee -
                                                                # für Contract-Verkauf/Tausch,
                                                                # wo der Markt umgangen wird.
                total_all = total + transport_cost + extra_cost
                marge = (prof / total_all * 100.0) if total_all else 0.0
                # GEWINN JE ENDPRODUKT ERST HIER (Nutzer-Befund 20.09.2026:
                # "im Profit wirkt es falsch, es muesste mehr Profit sein").
                # Die Karte "Endprodukte" wird weiter oben gefuellt - da sind
                # Verkaufsgebuehren, Fracht und Extrakosten noch gar nicht
                # gerechnet. Ihre Gewinn-Spalte stand deshalb BRUTTO da,
                # waehrend der grosse Gewinn NETTO ist: bei seinem Buendel
                # 287 Mio gegen 164 Mio, die Differenz war genau
                # Steuer+Broker. Zwei Gewinnbegriffe nebeneinander - deshalb
                # traegt die Spalte die Zahlen jetzt von HIER.
                # KEIN ZWISCHENNAME: aa355 verlangt, dass jeder im
                # Gewinn-Block gelesene Name VOR dem Zweig vorbelegt ist -
                # zu Recht (zwei echte Abstuerze, siehe CLAUDE.md). Also
                # direkt ueber self, ohne lokale Variable.
                if getattr(self, "_multi_gewinn_nachziehen", None) is not None:
                    try:
                        self._multi_gewinn_nachziehen(
                            satz=(tax + broker),
                            fracht=float(transport_cost or 0.0),
                            extra=float(extra_cost or 0.0),
                            gesamt=float(total or 0.0))
                    except Exception as _mge:
                        self._log_exception("Multi-Bauplan: Gewinn je Ende",
                                            str(_mge))
                st_profit.setText(isk(prof))
                st_profit.setStyleSheet("font-size:19px; font-weight:700; color:"
                                        + (theme.GREEN if prof >= 0 else theme.RED))
                st_profit_raw.setText(isk(prof_raw))
                st_profit_raw.setStyleSheet("font-size:15px; font-weight:700; color:"
                                            + (theme.MUTED if prof_raw >= 0 else theme.RED))
                # Bezug sichtbar machen: Gewinn PRO STUECK unter dem Gesamtwert,
                # und die Gebuehren als eigene Zahl (bei duennen Margen ist das
                # der groesste Posten und tauchte nirgends auf).
                # Die Geb\u00fchrenzeile gehoert unter den GEWINN, nicht unter
                # den Rohgewinn: dort las sie sich als "ohne Gebuehren, minus
                # Gebuehren" und der Nutzer hielt die Karten fuer
                # widerspruechlich. Jetzt steht bei jeder Karte, worauf sie
                # sich bezieht - und der Abzug dort, wo er wirkt.
                st_profit.sub_lbl.setText(
                    "= " + isk(prof / _q) + _txt(" / unit")
                    + ("   \u2190 " + _txt("after \u2212{fees} fees").format(fees=isk(fees))
                       if fees > 0 else ""))
                st_profit.sub_lbl.setVisible(False)
                if fees > 0:
                    st_profit_raw.sub_lbl.setText(
                        _txt("BEFORE fees \u00b7 = {v} / unit").format(v=isk(prof_raw / _q)))
                    st_profit_raw.sub_lbl.setToolTip(
                        _txt("This card shows the profit BEFORE sales tax and broker fee "
                             "\u2013 relevant when selling via contract or directly to "
                             "players.\n\n{raw}  (before fees)\n\u2212 {fees}  fees "
                             "({pct} % on {gross})\n= {prof}  \u2192 card \u201eTotal "
                             "profit\u201c").format(
                            raw=isk(prof_raw), fees=isk(fees),
                            pct=f"{(tax + broker) * 100:.2f}", gross=isk(gross),
                            prof=isk(prof))
                        + (_txt("\n\nThe fees eat {pct} % of your raw profit.").format(
                               pct=f"{fees / prof_raw * 100:.0f}")
                           if prof_raw > 0 else ""))
                    st_profit_raw.sub_lbl.setVisible(False)
                else:
                    st_profit_raw.sub_lbl.setVisible(False)
                st_profit_raw.setToolTip(_txt(
                    "Profit WITHOUT sales tax + broker fee ({tax}% + {broker}% = {sum}% "
                    "saved) - relevant if you sell/trade via contract or deal directly "
                    "with other players instead of via the market.\n"
                    "Sale proceeds: {gross}\n\u2212 Build cost: \u2212{total}\n"
                    "\u2212 Transport: \u2212{transport}\n= Raw profit: {raw}"
                ).format(tax=f"{tax*100:.2f}", broker=f"{broker*100:.2f}",
                         sum=f"{(tax+broker)*100:.2f}", gross=isk(gross),
                         total=isk(total), transport=isk(transport_cost),
                         raw=isk(prof_raw)))
                # Gebühren transparent machen (der Nutzer wollte sie sehen).
                if fees > 0:
                    # ZU WELCHEM PREIS? Das ist die Frage hinter jedem
                    # Gewinnbetrag, und seit die Karte "Min. Verkaufspreis"
                    # weg ist, stand sie nirgends mehr. Deshalb VORNE:
                    # angenommener Verkaufspreis je Stueck und die
                    # Verlustschwelle darunter.
                    # RICH-TEXT statt Fliesstext: rechtsbuendige Zahlenspalte,
                    # gedaempfte Beschriftungen, Farbe nur da wo sie etwas
                    # bedeutet (Abzuege rot, Ergebnis gruen). Vorher stand
                    # alles in 19px Gruen untereinander - unlesbar.
                    _src_lbl = (_txt("Contract Median") if _ct9 and _ct9.get("median")
                                else _txt("Contract") if sell_is_contract
                                else "Jita Sell")
                    # max-width mitgeben: der zentrale _wrap_tooltips laesst
                    # bereits formatierte Tooltips unangetastet, die
                    # Breitenbegrenzung muss also hier stehen (Test b7b prueft
                    # das fuer ALLE Tooltips - zu Recht rot geworden).
                    _t = [f"<div style='max-width:420px; font-size:13px; "
                          f"color:{theme.TEXT};'>",
                          "<table cellspacing='0' cellpadding='0'>",
                          _r(_txt("Sale price ({src})").format(src=_src_lbl),
                             isk(_sell_eff) + _txt(" / unit"), theme.CYAN, True)]
                    if _rec:
                        _t.append(_r(_txt("Break-even"),
                                     isk(_rec["break_even"]) + _txt(" / unit"), theme.RED))
                        # ZEILE NUR, WENN SIE ETWAS ANDERES SAGT. Der Tick ist
                        # fest 0.01 ISK - bei einem 44-Mio-Item verschwindet
                        # das in der Rundung, und die Zeile behauptete dann,
                        # zum Unterbieten reiche genau der Preis, mit dem
                        # ohnehin gerechnet wird (Nutzer-Fund). Sinnvoll ist
                        # sie nur bei billigen Items, wo 0.01 ISK sichtbar
                        # sind.
                        _und = _rec.get("undercut")
                        if (_rec.get("can_undercut") and _und
                                and isk(_und) != isk(_sell_eff)):
                            _t.append(_r(_txt("To undercut"),
                                         isk(_und) + _txt(" / unit"), theme.AMBER))
                    _t += ["</table>",
                           f"<hr style='border:0; border-top:1px solid {theme.BORDER};'>",
                           "<table cellspacing='0' cellpadding='0'>",
                           _r(_txt("Gross sale proceeds"), isk(gross)),
                           _r(_txt("\u2212 Tax + broker ({pct}%)").format(
                                  pct=f"{(tax + broker) * 100:.2f}"),
                              "\u2212" + isk(fees), theme.RED),
                           _r(_txt("\u2212 Build cost"), "\u2212" + isk(total), theme.RED)]
                    if transport_cost:
                        # Name = Eingabefeld. Steckt der Frachtdienst im
                        # Materialpreis, enthaelt diese Zeile NUR die Pauschale
                        # je Fahrt - dann darf sie auch nicht "Transport"
                        # heissen, sonst sucht man den Frachtdienst hier.
                        _t.append(_r(
                            _txt("\u2212 Own trip") if _fr_in_mat
                            else _txt("\u2212 Freight service + own trip"),
                            "\u2212" + isk(transport_cost), theme.RED))
                    if extra_cost:
                        _t.append(_r(_txt("\u2212 Extra cost"),
                                     "\u2212" + isk(extra_cost), theme.RED))
                    _t += [_r("<b>" + _txt("= Profit") + "</b>", "<b>" + isk(prof) + "</b>",
                              theme.GREEN if prof >= 0 else theme.RED, True),
                           _r(_txt("per unit"), isk(prof / _q), theme.MUTED),
                           "</table></div>"]
                    # TOOLTIP ENTFAELLT (Nutzer): jede Zeile daraus steht jetzt
                    # in der rechten Details-Spalte - Verkaufspreis, Erloes,
                    # Gebuehren, Baukosten, Eigene Fahrt, Zusatzkosten, Gewinn,
                    # Gewinn/Stk, Marge, Verlustschwelle. Ein Mouseover, das
                    # dasselbe nochmal sagt, ist eine zweite Anzeige derselben
                    # Zahlen - und genau daraus sind heute mehrfach Abweichungen
                    # entstanden. `_t` bleibt stehen: den Block bauen mehrere
                    # Stellen mit auf (Zielpreis/Verlustschwelle).
                    st_profit.setToolTip("")
            else:
                st_sell.setText("\u2013")
                st_profit.setText("\u2013")
                st_profit.setStyleSheet("font-size:19px; font-weight:700;")
                st_profit_raw.setText("\u2013")
                st_profit.sub_lbl.setVisible(False)
                st_profit_raw.sub_lbl.setVisible(False)
            # DER RICHTIGE MOMENT fuer den Contract-Knopf: hier steht fest,
            # ob dieser Plan einen Verkaufspreis hat. Gilt fuer BEIDE Zweige -
            # mit Preis verschwindet der Knopf wieder, auch wenn der Nutzer
            # ihn gerade selbst geladen hat.
            self._bd_contract_knopf(bool(_sell_eff))
            if plan:
                # DIESELBE Rechnung wie die Kopfzeile: ist die Ladder aktiv,
                # steckt in `total` der Orderbuch-Preis, nicht der Flachpreis
                # aus plan["mat_cost"]. Sonst ging die Aufschluesselung nie
                # ganz auf - beim Flycatcher um 3'790 ISK. Klein, aber genau
                # die Differenz, an der man den Bestands-Doppelzaehler
                # gefunden hat: die Details muessen sich addieren lassen.
                mc = mat_ladder if ladder_active else plan.get("mat_cost", 0.0)
                jco = plan.get("job_cost", 0.0)
                ico = plan.get("inv_cost", 0.0)
                if marge is None:
                    st_marge_lbl.setText("")
                    st_marge.setText("\u2013")
                    st_marge.setStyleSheet("font-size:19px; font-weight:700;")
                else:
                    st_marge_lbl.setText(
                        f'<span style="color:{theme.GREEN if marge >= 0 else theme.RED};'
                        f'font-weight:700;">' + _txt("Margin: {v} %").format(v=f"{marge:+.1f}")
                        + '</span>')
                    st_marge.setText(f"{marge:+.1f} %")
                    st_marge.setStyleSheet(
                        "font-size:19px; font-weight:700; color:"
                        + (theme.GREEN if marge >= 0 else theme.RED))
                    st_marge.setToolTip(_txt(
                        "Profit in relation to the total cost (build cost + "
                          "transport).\nPositive = you earn, negative = you are "
                          "paying in."))
                # BAUKOSTEN-AUFSCHLUESSELUNG (Nutzer-Wunsch, analog zum
                # Gewinn-Tooltip): woraus setzen sich die Kosten je Stueck
                # zusammen? Erst hier moeglich - vorher sind mc/jco/ico noch
                # nicht gerechnet. Deshalb wurde die Preisquelle oben nur
                # gemerkt (_cost_src_tip) statt gesetzt; ein frueher gesetzter
                # Tooltip wuerde hier ohnehin ueberschrieben.
                _ct = [f"<div style='max-width:420px; font-size:13px; "
                       f"color:{theme.TEXT};'>",
                       "<table cellspacing='0' cellpadding='0'>",
                       _r(_txt("Material (purchase)"), isk(mc - _fr_in_mat))]
                if _fr_in_mat:
                    _ct.append(_r(_txt("Freight service ({rate} ISK/m\u00b3)").format(
                                      rate=isk(_fr_rate, suffix=False)),
                                  isk(_fr_in_mat), theme.AMBER))
                _ct.append(_r(_txt("Job costs"), isk(jco)))
                if ico:
                    _ct.append(_r("Invention", isk(ico)))
                if stock_cost:
                    _ct.append(_r(_txt("Stock (replacement cost)"), isk(stock_cost),
                                  theme.AMBER))
                # TRANSPORT GEHOERT NICHT IN DIE STUECKKOSTEN - dieselbe
                # Entscheidung wie bei den Zusatzkosten (er faellt einmal fuer
                # den ganzen Plan an, nicht je Stueck). Die Summe hier zaehlte
                # ihn frueher TROTZDEM mit, waehrend die Karte darueber ohne
                # ihn rechnete: 1'571'378'925 im Tooltip gegen 129'281'577 x 12
                # auf der Karte. Zwei Zahlen fuer dieselbe Groesse, direkt
                # nebeneinander (Arbeitsregel 10). Jetzt zeigt der Tooltip
                # exakt das, was die Karte rechnet - und weist Transport und
                # Zusatzkosten darunter separat aus, statt sie zu verstecken.
                _ct += [_r("<b>" + _txt("= total build cost") + "</b>",
                           "<b>" + isk(total) + "</b>", theme.CYAN, True),
                        _r(_txt("\u00f7 {n} units").format(n=_q), isk(total / _q),
                           theme.MUTED),
                        "</table>"]
                _neben = []
                if _fracht_dienst and not _fr_in_mat:
                    # zaehlt hier nur, wenn er NICHT schon im Materialpreis
                    # steckt - sonst stuende er zweimal da
                    _neben.append((_txt("Freight service"), _fracht_dienst))
                if _eigene_fahrt:
                    _neben.append((_txt("Own haul"), _eigene_fahrt))
                if extra_cost:
                    _neben.append((_txt("Extra costs"), extra_cost))
                if _neben:
                    _ct.append("<table cellspacing='0' cellpadding='0' "
                               "style='margin-top:6px;'>")
                    _ct.append(_r("<i>" + _txt("Once for the whole plan \u2013 NOT "
                                               "per unit:") + "</i>", "", theme.MUTED))
                    for _lbl, _v in _neben:
                        _ct.append(_r(_lbl, isk(_v), theme.MUTED))
                    _ct.append("</table>")
                    _ct.append(
                        f"<div style='color:{theme.MUTED}; margin-top:4px;'>"
                        + _txt("Both come off in the profit tooltip, not here: they "
                               "belong to the plan, not to the single unit. Each row has "
                               "its own input field above: \u201eFreight service\u201c "
                               "(ISK/m\u00b3 \u00d7 volume), \u201eOwn trip\u201c (flat rate "
                               "\u00d7 trips) and \u201eExtra cost\u201c (everything else "
                               "one-off, e.g. bought BPCs).") + "</div>")
                # Steckt der ISK/m3-Satz schon im Materialpreis, sieht man ihn
                # in der Transportzeile NICHT - der Nutzer haelt ihn dann fuer
                # nicht berechnet. Also sagen, wo er steckt.
                if (tinfo or {}).get("rate_in_price"):
                    _ct.append(
                        f"<div style='color:{theme.MUTED}; margin-top:4px;'>"
                        + _txt("The freight service is shown SEPARATELY above but counts "
                               "towards the material cost (\u201eFreight in decision\u201c "
                               "is on, so it takes part in the buy-or-build decision for "
                               "every material). It is therefore inside the unit cost and "
                               "is NOT deducted again below \u2013 the transport row only "
                               "contains the flat rate per own trip.") + "</div>")
                # Gebuehren und Zusatzkosten sind bewusst NICHT dabei: sie
                # gehoeren zum Verkauf bzw. zum Bauplan als Ganzem, nicht zu
                # den Herstellkosten eines Stuecks. Sie stehen im
                # Gewinn-Tooltip.
                # DIE ZAHLEN-TABELLE WIRD NICHT MEHR ALS TOOLTIP GESETZT
                # (Nutzer): sie steht vollstaendig in der linken Details-Spalte.
                # `_ct` wird weiter gebaut - der Block oben ist die Stelle, an
                # der die Aufschluesselung entsteht, und die Tests haengen an
                # ihr; nur die Anzeige als Mouseover entfaellt.
                # WAS BLEIBT: der Hinweis zur PREISQUELLE (Orderbuch-genau vs.
                # Flachpreis, und wie viele Materialien mangels Orderbuch zum
                # Flachpreis gerechnet sind). Der steht in keiner Spalte, und
                # ihn mit wegzuwerfen hiesse, eine Unsicherheit zu verstecken.
                if _cost_src_tip:
                    st_cost.setToolTip(_cost_src_tip)
                else:
                    st_cost.setToolTip("")
                _ct.append("</div>")
                _detail_val_lbls["Material"].setText(
                    isk(mc - _fr_in_mat, suffix=False))
                # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                _frl = _detail_val_lbls["Frachtdienst"]
                # de_scan4: an
                _frl.setText(isk(_fracht_dienst, suffix=False)
                             if _fracht_dienst else "\u2013")
                _frl.setToolTip(
                    _txt("ISK/m\u00b3 x volume of the shopping list. Included in the "
                         "material price (because \u201eFreight in decision\u201c is on) - "
                         "the material row above shows the amount WITHOUT this markup, "
                         "together both give the full material cost. Is NOT deducted "
                         "from the profit again.")
                    if _fr_in_mat else
                    _txt("No ISK/m\u00b3 rate set or \u201eFreight in decision\u201c is "
                         "off."))
                # de_scan4: aus - interner Dict-Schluessel; die Beschriftung kommt uebersetzt aus _detail_rows
                _detail_val_lbls["Job-Kosten"].setText(isk(jco, suffix=False))
                # de_scan4: an
                # AUFSCHLUESSELUNG (Nutzer: "Index-Anteil, Facility-Tax und
                # SCC einzeln sehen"). Die Teile kommen aus DERSELBEN
                # Rechnung wie die Summe (_job_cost, parts_out) - keine
                # Nebenrechnung fuer die Anzeige (Arbeitsregel 10). Sie
                # stehen NUR hier, die Summe bleibt die einzige Zahl in der
                # Spalte selbst.
                _jcp = (plan.get("job_cost_parts") or {}) if plan else {}
                if any(_jcp.get(_k) for _k in ("index", "tax", "scc")):
                    # de_scan4: aus - interner Dict-Schluessel; die Beschriftung kommt uebersetzt aus _detail_rows
                    _detail_val_lbls["Job-Kosten"].setToolTip(
                    # de_scan4: an
                        "<table cellspacing='0' cellpadding='1'>"
                        + _r("Index-Anteil (EIV \u00d7 System-Index, nach "
                             "Rollenbonus/Cost-Rig)",
                             isk(_jcp.get("index", 0.0)))
                        + _r(_txt("Facility tax (owner)"),
                             isk(_jcp.get("tax", 0.0)))
                        + _r(_txt("SCC surcharge"), isk(_jcp.get("scc", 0.0)))
                        + _r(_txt("= Job costs"), isk(jco))
                        + "</table>")
                else:
                    # de_scan4: aus - interner Dict-Schluessel; die Beschriftung kommt uebersetzt aus _detail_rows
                    _detail_val_lbls['Job-Kosten'].setToolTip(_txt(
                    # de_scan4: an
                        "No breakdown available – the plan was calculated without "
                          "ESI adjusted prices (flat rate instead of the EIV "
                          "formula)."))
                # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                _detail_val_lbls["= Baukosten gesamt"].setText(
                # de_scan4: an
                    isk(total, suffix=False))
                # de_scan2: aus  (Dict-Schluessel, Anzeige laeuft ueber _detail_rows)
                _detail_val_lbls["\u00f7 St\u00fcck"].setText(
                    # de_scan2: an
                    isk(total / max(1, int(qty or 1)), suffix=False))
                _detail_val_lbls["Invention (\u00d8)"].setText(isk(ico, suffix=False))
                # WEG A: Ruecklaeufer-Gutschrift als eigene Zeile, sonst weg.
                # de_scan4: aus - interner Dict-Schluessel; die Beschriftung kommt uebersetzt aus _detail_rows
                _rl_lbl = _detail_val_lbls.get("\u2212 R\u00fcckl\u00e4ufer")
                _rl_cap = _detail_caps.get("\u2212 R\u00fcckl\u00e4ufer")
                # de_scan4: an
                _rl_w = float(((plan or {}).get("reprocess") or {}).get(
                    "ruecklaeufer_wert") or 0.0)
                if _rl_lbl is not None:
                    _rl_lbl.setText("\u2212" + isk(_rl_w, suffix=False) if _rl_w else "\u2013")
                    _rl_lbl.setStyleSheet(
                        f"font-size:11px; font-weight:700; color:{theme.GREEN};")
                    _rl_lbl.setVisible(bool(_rl_w))
                    if _rl_cap is not None:
                        _rl_cap.setVisible(bool(_rl_w))
                # --- EINKAUFSLISTE ZU JITA SELL (Nutzer, Sitzung 14) ---
                # Was er JETZT ausgeben muss - im Unterschied zu "Material",
                # das den Bestandsanteil nicht enthaelt, und zu "Baukosten
                # gesamt", das ihn zu Ersatzkosten mitrechnet.
                #
                # DIESELBE Mengenliste, aus der auch der Einkaufswagen und das
                # Transportvolumen entstehen (`plan["buy"]`) - keine
                # Nebenrechnung fuer die Anzeige (Arbeitsregel 10). Preis ist
                # der Sell-Preis des gewaehlten Hubs aus `_bd_pricemap`, also
                # genau die Zahl, gegen die sich ein Janice-Vergleich prueft.
                #
                # POSTEN OHNE PREIS WERDEN GEZAEHLT, NICHT VERSCHWIEGEN: sie
                # als 0 durchgehen zu lassen war der Fehler, der heute aus
                # 20 Mio/Stk 10 Mio/Stk gemacht hat. Fehlt ein Preis, sagt es
                # der Tooltip.
                _buy_map_e = (plan or {}).get("buy") or {}
                _ekl_summe = 0.0
                _ekl_ohne = 0
                for _tid_e, _menge_e in _buy_map_e.items():
                    _m_e = int(round(_menge_e or 0))
                    if _m_e < 1:
                        continue
                    _p_e = self._bd_pricemap.get(_tid_e)
                    if _p_e:
                        _ekl_summe += _p_e * _m_e
                    else:
                        _ekl_ohne += 1
                _q_e = max(1, int(qty or 1))
                # UEBER .get, NICHT ueber den Index: fehlt eine Zeile, soll
                # die Kopfzeile weiter stehen statt mit KeyError zu reissen.
                # Aufgefallen in der Rotprobe (Sitzung 14) - die Mutation, die
                # die Zeilen entfernt, brach die ganze b-Suite ab, statt eine
                # benannte Pruefung rot zu machen. Dieselbe Schwaeche haette
                # im Betrieb den ganzen Bauplan-Kopf mitgenommen.
                # de_scan4: aus - interner Dict-Schluessel; die Beschriftung kommt uebersetzt aus _detail_rows
                _ekl_lbl = _detail_val_lbls.get("Einkaufsliste (Jita Sell)")
                # de_scan4: an
                # de_scan4: aus - interner Dict-Schluessel; die Beschriftung kommt uebersetzt aus _detail_rows
                _ekl_stk = _detail_val_lbls.get("Einkaufsliste / St\u00fcck")
                # de_scan4: an
                if _ekl_lbl is not None:
                    _ekl_lbl.setText(isk(_ekl_summe, suffix=False))
                if _ekl_stk is not None:
                    _ekl_stk.setText(isk(_ekl_summe / _q_e, suffix=False))
                _ekl_tip = _txt(
                    "What you have to spend NOW: every position on the "
                    "shopping list at the sell price of the chosen hub.\n\n"
                    "This is NOT the same as \u201eMaterial\u201c (which "
                    "leaves out what comes from your own stock) and not the "
                    "same as \u201etotal build cost\u201c (which counts "
                    "that stock at replacement value).")
                if _ekl_ohne:
                    _ekl_tip += "\n\n" + _txt(
                        "{n} position(s) without a price - they are MISSING "
                        "from this sum.").format(n=_ekl_ohne)
                # de_scan2: aus  (Dict-Schluessel, nie sichtbar)
                for _k_e in ("Einkaufsliste (Jita Sell)",
                             "Einkaufsliste / St\u00fcck"):
                    # de_scan2: an
                    for _w_e in (_detail_val_lbls.get(_k_e),
                                 _detail_caps.get(_k_e)):
                        if _w_e is not None:
                            _w_e.setToolTip(_ekl_tip)
                # --- RECHTE SPALTE: die vollstaendige Gewinnrechnung ---
                # Alle Werte stammen aus DENSELBEN Variablen, aus denen auch
                # der Gewinn-Tooltip und die KPI-Karten gebaut werden - keine
                # Nebenrechnung fuer die Anzeige (Arbeitsregel 10).
                _q_ = max(1, int(qty or 1))
                _pf = _profit_val_lbls

                def _pset(_k, _v, _neg=False, _col=None):
                    _l = _pf.get(_k)
                    if _l is None:
                        return
                    _l.setText(("\u2212" if (_neg and _v) else "")
                               + isk(_v, suffix=False) if _v else "\u2013")
                    _l.setStyleSheet("font-size:11px; font-weight:700;"
                                     + (f" color:{_col};" if _col else ""))
                # de_scan2: aus  (Dict-Schluessel der Aufschluesselung, nie sichtbar)
                _pset("Verkaufspreis / Stk", _sell_eff)
                _pset("Verkaufserl\u00f6s brutto", gross)
                _pset("\u2212 Steuer + Broker", fees, True, theme.RED)
                _pset("\u2212 Baukosten", total, True, theme.RED)
                _pset("\u2212 Eigene Fahrt", _eigene_fahrt, True, theme.RED)
                _pset("\u2212 Zusatzkosten", extra_cost, True, theme.RED)
                # `prof` kann None sein (kein Verkaufspreis, s. oben) -
                # dann steht ein Strich da, und die Farbe spielt keine Rolle.
                _pset("= Gewinn", prof, False,
                      theme.GREEN if (prof or 0) >= 0 else theme.RED)
                _pset("Gewinn / Stk", (prof / _q_) if prof is not None else None,
                      False, theme.GREEN if (prof or 0) >= 0 else theme.RED)
                # de_scan2: an
                # de_scan4: aus - interner SCHLUESSEL (Kategorie/Stufe/Dict), Anzeige uebersetzt woanders
                _mg = _pf.get("Marge")
                # de_scan4: an
                if _mg is not None:
                    _mgv = (prof / gross * 100.0) if gross else None
                    _mg.setText(f"{_mgv:+.1f} %" if _mgv is not None else "\u2013")
                    _mg.setStyleSheet(
                        "font-size:11px; font-weight:700; color:"
                        + (theme.GREEN if (_mgv or 0) >= 0 else theme.RED))
                # de_scan4: aus - interner Dict-Schluessel; die Beschriftung kommt uebersetzt aus _detail_rows
                _pset("Verlustschwelle / Stk",
                # de_scan4: an
                      (total + transport_cost + extra_cost)
                      / (1 - tax - broker) / _q_ if (1 - tax - broker) else 0,
                      False, theme.AMBER)
                # de_scan4: aus - interner Dict-Schluessel; die Beschriftung kommt uebersetzt aus _detail_rows
                _sv = _detail_val_lbls["Bestand (Ersatzkosten)"]
                # de_scan4: an
                _sv.setText(isk(stock_cost, suffix=False)
                            if stock_cost > 0 else "\u2013")
                _sv.setStyleSheet(
                    f"font-size:11px; font-weight:700; color:{theme.AMBER};"
                    if stock_cost > 0 else "font-size:11px; font-weight:700;")
                # Der Kaufwert bleibt ablesbar - als VERGLEICH, nicht als
                # zweite Zahl in der Summe (er steckt in keiner).
                if stock_cost > 0:
                    _svtip = [_txt("Material you already have, valued at "
                                   "min(purchase price, your own build cost) - what "
                                   "it costs you to replace it.")]
                    if stock_value > 0:
                        _svtip.append(
                            _txt("Plain purchase price of the same quantity: "
                                 "{v}.").format(v=isk(stock_value)))
                    _sv.setToolTip("\n".join(_svtip))
                else:
                    # OHNE Bestand bleibt die KURZERKLAERUNG stehen - ein
                    # leerer Tooltip waere ein Rueckschritt gegenueber der
                    # Zeile daneben (Nutzer 25.09.2026: Erklaerung auf jeder
                    # Zeile).
                    # de_scan4: aus - interner Dict-Schluessel
                    _sv.setToolTip(_txt((getattr(self, "_bd_detail_tips", None)
                                         or {}).get("Bestand (Ersatzkosten)")
                                        or ""))
                    # de_scan4: an
                # "Eigene Fahrt" und "Zusatzkosten" stehen jetzt in der
                # RECHTEN Spalte (Gewinnrechnung) - sie sind keine
                # Herstellkosten. Hier nichts mehr zu setzen.
            else:
                st_marge_lbl.setText("")
                for _lbl in (list(_detail_val_lbls.values())
                             + list(_profit_val_lbls.values())):
                    _lbl.setText("\u2013")
            # --- Transport-Zeile (Volumen / Fahrten / Warnung) ---
            if tinfo["volume"] > 0:
                nfahrt = tinfo["trips"]
                vol_txt = (f'{tinfo["volume"]:,.0f}'.replace(",", "'") + " m\u00b3")
                base = (icons.html("package")
                        + f' <span style="color:{theme.MUTED};">'
                        + _txt("Transport volume (shopping list, incl. buffer):")
                        + f'</span> <b>{vol_txt}</b>')
                # AUFSCHLUESSELUNG: bei Schiffen als Material (ein Cormorant hat
                # 5'000 m3 verpackt!) macht EIN Posten schnell 99 % des
                # Volumens aus. Der Nutzer hielt 100'010 m3 fuer einen Fehler,
                # weil im Wagen nur ein paar Promethium lagen - die 20
                # Cormorants stehen zwar auf der PLAN-Einkaufsliste, wurden im
                # "Schon vorhanden"-Dialog aber abgewaehlt (er besitzt sie,
                # nur nicht am Bau-Ort). Wer sie nicht kauft, muss sie
                # trotzdem hinkarren - das Volumen stimmt also, es war nur
                # nicht nachvollziehbar.
                _vparts = []
                for _t2, _q2 in sorted(
                        buy_surplus.items(),
                        key=lambda kv: -(vols.get(kv[0], 0) or 0) * kv[1])[:5]:
                    _v2 = (vols.get(_t2, 0) or 0) * _q2
                    if _v2 <= 0:
                        continue
                    _vparts.append(
                        "  " + names.get(_t2, f"#{_t2}") + f": {int(_q2):,}".replace(",", "'")
                        + " \u00d7 " + f"{vols.get(_t2, 0):,.2f}".replace(",", "'")
                        + " m\u00b3 = " + f"{_v2:,.0f}".replace(",", "'") + " m\u00b3"
                        + (f"  ({_v2 / tinfo['volume'] * 100:.0f} %)"
                           if tinfo["volume"] else ""))
                _vtip = [_txt("Volume of the PLAN shopping list (what still has to be "
                              "procured), not of the shopping cart."),
                         _txt("Material you own but do NOT have at the build location "
                              "counts here \u2013 you still have to bring it there."), ""]
                if _vparts:
                    _vtip.append(_txt("Largest items:"))
                    _vtip += _vparts
                _lbl_tip = "\n".join(_vtip)
                if tinfo["capacity"] > 0:
                    base += (f'  \u00b7  <span style="color:{theme.MUTED};">'
                             + _txt("{n} trip(s) \u00e0 ").format(n=nfahrt)
                             + f'{tinfo["capacity"]:,.0f}'.replace(",", "'")
                             + " m\u00b3</span>")
                if tinfo["missing_volume"]:
                    base += (f'  \u00b7  <span style="color:{theme.MUTED};">'
                            + _txt("{n} material(s) without volume data in the SDE "
                                   "\u2013 calculated with 0 m\u00b3 there").format(
                                n=len(tinfo["missing_volume"])) + '</span>')
                st_transport.setToolTip(_lbl_tip)
                # Nutzer-Vorgabe: die Zeile verschwindet aus der Anzeige. Die
                # Kapazitaets-WARNUNG lebt jetzt im Einkaufswagen-Dialog
                # (s. _plan_to_cart) - sie geht also nicht verloren. Nur wenn
                # der Frachtraum ueberschritten ist, bleibt sie sichtbar.
                st_transport.setVisible(bool(tinfo.get("over_capacity"))
                                        or bool(_unpkg_ships))
                # _unpkg_ships kommt schon von oben (nach ESI-Korrekturversuch) -
                # enthält jetzt nur noch Schiffe, die AUCH per ESI nicht aufgelöst
                # werden konnten (z.B. Netzwerkfehler).
                warn_lines = []
                if tinfo["over_capacity"]:
                    warn_lines.append(_txt("\u26a0 Does NOT fit in one trip \u2013 {n} trips "
                                           "needed!").format(n=nfahrt))
                if _unpkg_ships:
                    warn_lines.append(_txt("\u26a0 {n} ship(s) without packaged volume in "
                                           "the SDE \u2013 AS-FIT size used (far too "
                                           "large)!").format(n=len(_unpkg_ships)))
                if warn_lines:
                    base += '<br>' + '<br>'.join(
                        f'<span style="color:{theme.AMBER}; font-weight:800; '
                        f'font-size:15px;">{w}</span>' for w in warn_lines)
                    st_transport.setStyleSheet(
                        "font-size:13px; background:rgba(242,162,60,0.14); "
                        "border:1px solid rgba(242,162,60,0.5); border-radius:6px; "
                        "padding:8px 10px;")
                else:
                    st_transport.setStyleSheet("font-size:13px;")
                st_transport.setText(base)
            else:
                st_transport.setStyleSheet("font-size:13px;")
                st_transport.setText("")
            # Welche Struktur baut was (Auto-Wahl bzw. zugewiesen)?
            su = getattr(self, "_bd_struct_used", {}) or {}
            parts = []
            for akey, icon, alabel in (("manufacturing", "factory",
                                        _txt("Manufacturing")),
                                       ("reaction", "flask", _txt("Reactions"))):
                info = su.get(akey)
                if not info:
                    continue
                nm, assigned = info
                if nm:
                    # "Auto" heisst in beiden Sprachen gleich und bleibt.
                    tag = _txt("assigned") if assigned else "Auto"
                    parts.append(icons.html(icon)
                                 + f' <span style="color:{theme.MUTED};">{alabel}:</span> '
                                 f'<b>{nm}</b> <span style="color:{theme.MUTED};">({tag})</span>')
            st_struct.setText("&nbsp;&nbsp;&nbsp;&nbsp;".join(parts) if parts else "")
            self._fill_bauplan_schedule(plan, names, type_id, qty,
                                        sched_hdr, sched_sub, sched_tree,
                                        bp_tbl=bp_tab_tbl, bp_warn_lbl=sched_bp_warn)
            # ME/TE NICHT ZWEIMAL VERGEBEN: _fill_invention_tab haengt me_spin/
            # te_spin in die Invention-Karte um (dieselben Widget-Objekte, nur
            # anderer Ort). Stehen sie oben im Header - also wenn das Endprodukt
            # NICHT erfunden wird -, verschwinden sie dadurch aus dem Header und
            # zurueck bleiben nur die Beschriftungen "ME TE" ohne Eingabefeld.
            # Genau das hat der Nutzer beim Rokh gesehen. In dem Fall bekommt der
            # Invention-Tab sie gar nicht erst; seine eigene Rueckfall-Karte
            # (_own_bpc_fallback_card) entfaellt damit ebenfalls - sie saesse
            # ohnehin in einem Tab, der fuer T1 entfernt wird.
            self._fill_invention_tab(
                plan, self._bd_recipes, names, inv_cards_v, type_id,
                own_bpc_widgets=None if _me_te_in_header else (
                    me_spin, te_spin, own_bpc_cb,
                    own_bpc_runs_lbl, own_bpc_runs_spin))
            # Zum Schluss alle Tooltips umbrechen lassen - in diesem Durchlauf
            # sind viele neu gesetzt worden (KPI-Karten, Tabellen, Baum), und
            # reiner Text ohne Umbruch zieht sich sonst \u00fcber die ganze
            # Fensterbreite (s. _wrap_tooltips).
            try:
                self._wrap_tooltips(dlg)
            except Exception:
                pass
            _rb_done()   # Sanduhr wieder weg - siehe Kopf der Funktion
        self._bd_full_rebuild = rebuild   # externer Trigger, z.B. Decryptor-Dropdown
        rebuild()
        # ICONS NACHLADEN (Oeffnungszeit, gemessen ~62 % der Aufbauzeit): der
        # Aufbau oben hat alle fehlenden Icons nur VORGEMERKT statt sie einzeln
        # synchron aus dem Netz zu holen. Jetzt einmal im Hintergrund holen und
        # danach GENAU EINEN Nachtrag fahren (rebuild ist dieselbe Funktion, die
        # auch Decryptor-Wechsel & Co. nutzen - kein zweiter Aufbauweg).
        self._icon_prefetch_pending(rebuild)

        def _toggle_assets(checked=False):
            # HINWEIS: hier stand ein früher Abbruch für eingefrorene Pläne
            # ("kein Live-Abruf") - DER war der Grund, warum trotz entsperrter
            # Checkbox "nichts passierte" (Nutzer-Meldung). Eingefrorene Pläne
            # dürfen den Live-Abruf inzwischen ausdrücklich: adone() ERSETZT
            # den Einfrier-Bestand nicht, sondern mischt nur Zuwächse dazu
            # (max(eingefroren, live), s. _merge_frozen_stock).
            if not checked:
                if getattr(self, "_bd_frozen", None):
                    # Abwählen bei eingefrorenem Plan = zurück auf den REINEN
                    # Einfrier-Stand (nicht auf "kein Bestand").
                    self._bd_esi_stock_base = {
                        int(k): int(v) for k, v in
                        ((self._bd_frozen or {}).get("stock") or {}).items()}
                else:
                    self._bd_esi_stock_base = {}
                # ESI-Seite aus, Pipeline aus - der EINGEFÜGTE Bestand bleibt
                # aber stehen: er ist seit dem Umbau eine eigene Quelle, nicht
                # ein Anhängsel des Assets-Häkchens. Zum Entfernen gibt's
                # "Leeren" im Panel. esi_ts=None -> die Einfügung gilt.
                self._bd_virt_stock = {}
                self._bd_esi_stock_ts = None
                self._recompute_bd_stock()
                _sp0 = getattr(self, "_bd_sync_paste_panel", None)
                if _sp0 is not None:
                    _sp0(refill_box=False)
                rebuild()
                return
            client_id = self.settings.get("client_id")
            chars = store.list_characters()
            if not client_id or not chars:
                self._flash_tip(_txt("No characters / client ID"))
                asset_cb.setChecked(False)
                return

            def ajob():
                agg = {}
                # ALLE verknuepften Bau-Strukturen zaehlen - nicht nur die
                # gerade zugewiesene Fertigungs-/Reaktionsstruktur. NUTZER-
                # FALL (Falcon-Plan): Mineralien lagen bei "Dockside
                # Innovations" (verknuepft), gebaut wurde aber an "Capslock"
                # (Fertigung, unverknuepft) und "R&R Yard" (Reaktionen) -
                # gezaehlt wurde nur der R&R Yard, alle Mineralien standen
                # auf 0. Dabei verspricht die Strukturen-Liste bei JEDER
                # verknuepften Struktur gruen "Assets von hier werden
                # gezaehlt" (Arbeitsregel 9: eine Wahrheit). Die Bau-
                # Strukturen sind die eigene Bau-Infrastruktur des Nutzers
                # (hier: alle im selben System) - das ist weiterhin der
                # bewusst enge Gegenpol zu "Ueberall" (die 91 Cormorants aus
                # dem Lowsec-Nirgendwo bleiben draussen: deren Ort ist keine
                # Bau-Struktur).
                structs = self.settings.get("bau_structures", []) or []
                _scope0 = (self.settings.get("bau_stock_scope") or "structures")
                if _scope0 == "plan":
                    # NUR DIE STRUKTUREN DIESES PLANS (Sitzung 19). Material,
                    # das woanders liegt, kann nicht in den Job - es als
                    # "gedeckt" auszuweisen ist eine falsche Aussage, keine
                    # grosszuegige.
                    # DIESELBE Antwort wie Plan und Runplaner (Sitzung 20):
                    # `_bau_plan_structs` nimmt die Stufen-Strukturen, die der
                    # Plan beim Rechnen gewaehlt hat. Vorher stand hier
                    # `_struct_for_activity` - eine ZWEITE Auto-Wahl nach
                    # pauschalem Rig-Prozent, die von der des Plans abweichen
                    # konnte. Dann zaehlte der Bereich eine Struktur, in der
                    # gar nicht gebaut wird, und uebersah die richtige.
                    structs = self._bau_plan_structs()
                locs = {}   # structure_id -> character_id (dedupe)
                loc_names = []
                for bs in structs:
                    # NUR die structure_id ist Pflicht: die Assets holt der
                    # Zweig unten ohnehin von ALLEN Pool-Charakteren, die
                    # verknuepfte character_id wird dort gar nicht benutzt.
                    _sid = bs.get("link_structure_id")
                    if not _sid:
                        continue
                    if int(_sid) not in locs:
                        loc_names.append(bs.get("name") or str(_sid))
                    locs[int(_sid)] = int(bs.get("link_character_id") or 0)
                _scope = (self.settings.get("bau_stock_scope") or "structures")
                # Nutzer-Wunsch: NICHT still auf "überall" zurückfallen (so
                # zählten 91 Cormorants aus dem Lowsec-Nirgendwo als Bestand).
                # Ohne verknüpfte Bau-Struktur wird im Struktur-Scope GAR KEIN
                # Lager-Bestand gezählt - nur der virtuelle (Jobs laufen ja per
                # Definition an Bau-Orten). Hier nur MERKEN: die Rückgabe
                # passiert weiter unten, wo _virtual_stock definiert ist
                # (der frühe Return hier war ein NameError - vom
                # Reihenfolge-Prüfer gefunden, bevor es jemand traf).
                _no_locs = (_scope != "all" and not locs)
                if _scope == "all":
                    locs = {}          # bewusst global: alle Orte zählen
                # Aktive Jobs derselben (Bau-/Reaktions-)Charaktere gleich mit
                # abrufen - fürs violette "läuft schon"-Label im Runplaner, ohne
                # dafür einen zweiten, separaten ESI-Rundgang zu brauchen.
                relevant_ids0 = self._runplan_pool_char_ids(self.settings)
                relevant_chars0 = ([c for c in chars if c["character_id"] in relevant_ids0]
                                   if relevant_ids0 else chars)
                active_by_product = {}
                failed = []          # Charaktere/Orte, deren Abruf scheiterte
                ages = []            # Alter der Asset-Daten (ESI Last-Modified)
                jobs_by_char = {}    # character_id -> rohe Jobliste (inkl. delivered)
                for ch in relevant_chars0:
                    try:
                        _jobs = esi.fetch_active_jobs(client_id, ch["character_id"],
                                                      include_delivered=True)
                        jobs_by_char[ch["character_id"]] = _jobs
                        for j in _jobs:
                            pid = j.get("product_type_id")
                            # 'delivered' NICHT ins "läuft schon"-Label - der Job
                            # ist Geschichte; er zählt nur unten für den
                            # virtuellen Bestand.
                            if not pid or j.get("status") == "delivered":
                                continue
                            _st = j.get("status")
                            if _st == "active" and esi.job_is_finished(j):
                                _st = "ready"     # ESI meldet fertige Jobs als 'active'
                            active_by_product.setdefault(pid, []).append(
                                {"char": ch.get("character_name", "?"),
                                 "runs": j.get("runs"), "end_date": j.get("end_date"),
                                 "status": _st})
                    except Exception as _jf_err:
                        # GRUND MITSCHREIBEN (Regel 8; Nutzer sah "alle 5
                        # Charaktere, Jobs+Assets nicht ladbar" und konnte
                        # nur raten: Token? ESI down? Timeout?). Die Warn-
                        # leiste bleibt kurz - der Grund steht in fehler.log.
                        # de_scan4: aus - Beschriftung fuer fehler.log, nicht Oberflaeche
                        self._log_exception(
                            f"Bestand: Jobs {ch.get('character_name', '?')}",
                            str(_jf_err))
                        # de_scan4: an
                        failed.append(f"Jobs: {ch.get('character_name', '?')}")

                # CORP-HANGAR (1.0.8, nur fuers Bauen). Dieselbe Orts-Grenze
                # wie der eigene Bestand: im Struktur-Bereich nur die
                # verknuepften Strukturen, bei "Ueberall" alles. Ohne
                # verknuepfte Struktur (_no_locs) zaehlt auch die Corp
                # nichts - sonst hiesse "kein Hangarbestand" ploetzlich
                # "kein eigener, aber der ganze Corp-Hangar".
                _corp = self._corp_bau_daten(
                    client_id, chars,
                    None if _scope == "all" else list(locs.keys())
                ) if not _no_locs else self._corp_bau_daten(client_id, [], [])
                failed.extend(_corp.get("failed") or [])
                # Corp-Jobs in den "laeuft schon"-Pool und (unten) in den
                # virtuellen Bestand - unter der CORP-Nummer, mit dem
                # Corp-Namen als "Charakter".
                for _corp_id, _cjobs in (_corp.get("jobs") or {}).items():
                    jobs_by_char[_corp_id] = _cjobs
                    _cn = next((c["name"] for c in _corp.get("corps") or []
                                if c.get("corp_id") == _corp_id), None)
                    for j in _cjobs:
                        pid = j.get("product_type_id")
                        if not pid or j.get("status") == "delivered":
                            continue
                        _st = j.get("status")
                        if _st == "active" and esi.job_is_finished(j):
                            _st = "ready"
                        active_by_product.setdefault(pid, []).append(
                            {"char": _cn or _txt("Corp"),
                             "runs": j.get("runs"), "end_date": j.get("end_date"),
                             "status": _st})

                # BLAUPAUSEN FRISCH MITHOLEN (Nutzer-Fund, Sitzung 8: "ich
                # habe neue Blueprints gekauft und ESI erkennt das nicht im
                # gespeicherten Bauplan"). Der gemeinsame Blaupausen-Cache
                # wurde bisher NUR bei 'Alles aus ESI laden' erneuert - der
                # Bestands-Refresh holte Assets und Jobs, aber keine
                # Blaupausen. Neue Kaeufe blieben damit fuer Runplaner UND
                # Blueprints-Tab unsichtbar, bis man den grossen Lade-Knopf
                # drueckte. Jetzt laufen sie hier mit (ein Abruf je
                # Charakter, wie Assets/Jobs auch).
                owned_bp_fresh = []
                bp_fetch_ok = True
                for ch in chars:
                    try:
                        # jobs= : die oben schon geholte Liste, damit die
                        # Blaupausen in Jobs ohne zweiten Abruf wegfallen
                        # (esi.blaupausen_in_jobs, 26.09.2026). Charaktere
                        # ohne Job-Abruf holen sie sich selbst (None).
                        for _b in esi.fetch_blueprints(
                                client_id, ch["character_id"],
                                jobs=jobs_by_char.get(ch["character_id"])):
                            owned_bp_fresh.append(_b)
                    except Exception as _bp_err:
                        # Ein gescheiterter Charakter darf den ALTEN Cache
                        # nicht durch eine Teilliste ersetzen - sonst
                        # "verschwinden" Blaupausen und der Runplaner deckelt
                        # zu streng. Dann lieber beim alten Stand bleiben und
                        # den Grund nennen.
                        bp_fetch_ok = False
                        # de_scan4: aus - Beschriftung fuer fehler.log, nicht Oberflaeche
                        self._log_exception(
                            f"Bestand: Blaupausen "
                            f"{ch.get('character_name', '?')}", str(_bp_err))
                        # de_scan4: an
                        failed.append(
                            _txt("Blueprints: {name}").format(name=ch.get('character_name', '?')))
                # Corp-Blaupausen aus den gewaehlten Divisions dazu. Ein
                # gescheiterter Corp-Abruf steht schon in `failed`; dann gilt
                # dieselbe Regel wie bei den Charakteren: alter Vollstand
                # statt Teilliste.
                owned_bp_fresh.extend(_corp.get("blueprints") or [])
                if _corp.get("bp_ok") is False:
                    bp_fetch_ok = False

                # GELIEFERTE Jobs flach einsammeln (fuer die automatische
                # Fortschritts-Erkennung eingefrorener Plaene): nur die vier
                # Felder, die _frozen_auto_checked braucht. Charakter-egal -
                # der Fortschritt zaehlt je ITEM, nicht je Haendepaar (wer den
                # Job gefahren hat, ist fuer "ist die Stufe durch?" egal).
                delivered_jobs = []
                for _jl in jobs_by_char.values():
                    for _j in _jl:
                        if _j.get("status") != "delivered":
                            continue
                        delivered_jobs.append({
                            "product_type_id": _j.get("product_type_id"),
                            "activity_id": _j.get("activity_id"),
                            "runs": _j.get("runs"),
                            "completed_date": _j.get("completed_date"),
                            # JOB-ID UND START (Stufe B, 21.09.2026): ohne
                            # beide laesst sich ein Job weder dauerhaft einem
                            # Plan zuordnen noch gegen einen Klick halten -
                            # der Klick gilt nur fuer Jobs, die NACH ihm
                            # gestartet wurden. ESI liefert beides schon
                            # (s. esi.fetch_active_jobs), es wurde hier nur
                            # weggeworfen.
                            "job_id": _j.get("job_id"),
                            "start_date": _j.get("start_date"),
                        })

                def _virtual_stock():
                    """Virtueller Bestand aus Jobs, deren Output existiert ODER
                    sicher entstehen wird. Doppelzählung ausgeschlossen (die
                    Inputs verlassen die Assets beim Jobstart, der Output ist
                    noch nirgends):
                    - 'ready' (fertig, nicht abgeliefert - ESI meldet das als
                      'active' mit abgelaufenem end_date, s. job_is_finished).
                    - 'delivered': nur wenn die Ablieferung NACH dem Asset-
                      Zeitstempel lag (sonst zählt sie der Asset-Stand schon).
                    - LAUFENDE Jobs ('active', end_date in der Zukunft) - auf
                      Nutzer-Wunsch: ein laufender Run ist ein Run, den der
                      Runplaner nicht nochmal einplanen darf; der Output ist
                      "in der Pipeline". Risiko bewusst akzeptiert: bricht man
                      den Job ab, fehlt das Material wieder. 'paused' zählt
                      NICHT (kann ewig stehen).
                    Output-Menge = Runs x Ausstoß/Run (SDE)."""
                    recipes = getattr(self, "_bd_recipes", None)
                    virt = {}
                    n_ready = n_fresh = n_running = units = 0
                    if recipes is None:
                        return virt, 0, 0, 0, 0
                    from datetime import datetime
                    for cid, jobs in jobs_by_char.items():
                        asset_ts = esi._assets_meta.get(int(cid))
                        for j in jobs:
                            st = j.get("status")
                            pid = j.get("product_type_id")
                            runs = int(j.get("runs") or 0)
                            # ESI-Falle (s. esi.job_is_finished): fertige,
                            # unabgeholte Jobs bleiben status='active' - über
                            # das abgelaufene end_date erkennen und wie
                            # 'ready' zählen (Output existiert, ist aber
                            # sicher noch NICHT in den Assets -> keine
                            # Doppelzählung möglich).
                            if st == "active" and esi.job_is_finished(j):
                                st = "ready"
                            if not pid or runs <= 0 or \
                                    st not in ("ready", "delivered", "active"):
                                continue
                            bp = recipes.product_to_bp.get(pid)
                            out_qty = int(bp[2]) if bp else 0
                            if out_qty <= 0:
                                continue
                            if st == "delivered":
                                cd = j.get("completed_date")
                                try:
                                    cd_ts = datetime.fromisoformat(
                                        str(cd).replace("Z", "+00:00")).timestamp()
                                except (TypeError, ValueError):
                                    continue
                                if not asset_ts or cd_ts <= asset_ts:
                                    continue
                                n_fresh += 1
                            elif st == "active":
                                n_running += 1       # läuft noch -> Pipeline
                            else:
                                n_ready += 1
                            q = runs * out_qty
                            virt[int(pid)] = virt.get(int(pid), 0) + q
                            units += q
                    return virt, n_ready, n_fresh, n_running, units

                if _no_locs:
                    _virt, _nr, _nf, _nrun, _units = _virtual_stock()
                    # assets/virt_map GETRENNT zurückgeben: nur so kann die
                    # Herkunft je Item auseinandergehalten werden (und nur so
                    # kann eine Einfügung den LAGER-Anteil ersetzen, ohne die
                    # Pipeline mit zu überschreiben).
                    return {"agg": dict(_virt), "assets": {},
                            "owned_bp": owned_bp_fresh if bp_fetch_ok else None,
                            "virt_map": dict(_virt), "located": False,
                            "no_locations": True, "active": active_by_product,
                            "delivered": delivered_jobs,
                            "failed": failed, "age": None, "corp": _corp,
                            "virtual": {"ready": _nr, "fresh": _nf,
                                        "running": _nrun, "units": _units}}
                if locs:
                    # Ortsgebunden: Assets AN den verknüpften Strukturen -
                    # aber von ALLEN Pool-Charakteren (jedes Rollen-Häkchen),
                    # nicht nur vom je Struktur verknüpften Charakter.
                    # Nutzer-Setup "gemeinsames Inventar, verteilt auf
                    # Charaktere": das Material eines anderen Häkchen-Chars an
                    # derselben Struktur zählte vorher NICHT zum Bestand ->
                    # zweite Wurzel des "Reaktionen verschwinden nie"-Falls.
                    cmap0 = {c["character_id"]: c.get("character_name", "?")
                             for c in chars}
                    _loc_ids = list(locs.keys())
                    _pool = [c for c in relevant_chars0
                             if c["character_id"] in cmap0]
                    _loc_diag = {}   # Messung je Charakter (Aufgabe 0b)
                    for ch in _pool:
                        cid = ch["character_id"]
                        try:
                            _dg = {}
                            a = esi.assets_at_locations(client_id, cid,
                                                        _loc_ids, diag_out=_dg)
                            _loc_diag[cmap0.get(cid, cid)] = _dg
                            for t, q in (a or {}).items():
                                agg[int(t)] = agg.get(int(t), 0) + int(q)
                            _age = esi.assets_age_seconds(cid)
                            if _age is not None:
                                ages.append(_age)
                        except Exception as _af_err:
                            # de_scan4: aus - Beschriftung fuer fehler.log, nicht Oberflaeche
                            self._log_exception(
                                f"Bestand: Assets {cmap0.get(cid, cid)}",
                                str(_af_err))
                            # de_scan4: an
                            failed.append(f"Assets: {cmap0.get(cid, cid)}")
                    # CORP-HANGAR an denselben Strukturen dazu (1.0.8).
                    for t, q in (_corp.get("summe") or {}).items():
                        agg[int(t)] = agg.get(int(t), 0) + int(q)
                    _assets_only = dict(agg)      # vor dem Aufaddieren merken
                    _virt, _nr, _nf, _nrun, _units = _virtual_stock()
                    for t, q in _virt.items():
                        agg[t] = agg.get(t, 0) + q
                    return {"agg": agg, "assets": _assets_only,
                            "owned_bp": owned_bp_fresh if bp_fetch_ok else None,
                            "virt_map": dict(_virt),
                            "loc_diag": _loc_diag, "loc_ids": _loc_ids,
                            "located": True, "loc_names": loc_names,
                            "active": active_by_product,
                            "delivered": delivered_jobs,
                            "failed": failed, "age": max(ages) if ages else None,
                            "corp": _corp,
                            "virtual": {"ready": _nr, "fresh": _nf,
                                        "running": _nrun, "units": _units}}
                # Fallback: keine Verknüpfung -> altes Verhalten (alle Orte), aber
                # ehrlich kennzeichnen, damit der Nutzer weiß, dass es nicht
                # ortsgebunden ist. NUR die für Bauen/Reaktionen markierten
                # Charaktere zählen (bau_build_chars/bau_reaction_chars) - ein
                # unbeteiligter Handels-Alt, der zufällig irgendwo Material
                # liegen hat, das er nie an die Struktur liefert, darf nicht
                # als "schon vorhanden" durchgehen (führte dazu, dass Material
                # als gedeckt galt, obwohl es real nicht an der Struktur war).
                relevant_ids = relevant_ids0
                relevant_chars = relevant_chars0
                for ch in relevant_chars:
                    try:
                        a = esi.fetch_assets(client_id, ch["character_id"])
                        for t, q in (a or {}).items():
                            agg[int(t)] = agg.get(int(t), 0) + int(q)
                        _age = esi.assets_age_seconds(ch["character_id"])
                        if _age is not None:
                            ages.append(_age)
                    except Exception as _af2_err:
                        # de_scan4: aus - Beschriftung fuer fehler.log, nicht Oberflaeche
                        self._log_exception(
                            f"Bestand: Assets {ch.get('character_name', '?')}",
                            str(_af2_err))
                        # de_scan4: an
                        failed.append(f"Assets: {ch.get('character_name', '?')}")
                # CORP-HANGAR ueberall dazu (1.0.8).
                for t, q in (_corp.get("summe") or {}).items():
                    agg[int(t)] = agg.get(int(t), 0) + int(q)
                _assets_only = dict(agg)          # vor dem Aufaddieren merken
                _virt, _nr, _nf, _nrun, _units = _virtual_stock()
                for t, q in _virt.items():
                    agg[t] = agg.get(t, 0) + q
                return {"agg": agg, "assets": _assets_only,
                       "virt_map": dict(_virt), "located": False,
                       "limited_to_build_chars": bool(relevant_ids),
                       "active": active_by_product,
                       "delivered": delivered_jobs,
                       "failed": failed, "age": max(ages) if ages else None,
                       "corp": _corp,
                       "virtual": {"ready": _nr, "fresh": _nf,
                                   "running": _nrun, "units": _units}}

            def adone(result):
                agg = result.get("agg", {})
                located = result.get("located", False)
                limited = result.get("limited_to_build_chars", False)
                failed = result.get("failed") or []
                age = result.get("age")
                _manual = getattr(self, "_bd_manual_stock", None) or {}
                _assets = result.get("assets")
                if _assets is None:                # Rückfall für alte Pfade
                    _assets = dict(agg)
                _virt_map = result.get("virt_map") or {}
                _frozen = getattr(self, "_bd_frozen", None)
                # ZEITSTEMPEL der ESI-Bestandsdaten (Punkt 3): daran misst
                # sich, ob eine Einfügung noch gilt. Kein Alter, aber Assets
                # angekommen -> als "jetzt" werten; gar keine Lagerdaten
                # (Scope zählt nichts / Abruf leer) -> None, dann gilt die
                # Einfügung, weil ESI schlicht nichts weiß.
                _now = _time_mod.time()
                if age is not None:
                    self._bd_esi_stock_ts = _now - float(age)
                elif _assets:
                    self._bd_esi_stock_ts = _now
                else:
                    self._bd_esi_stock_ts = None
                # BIS WANN HAT ESI DEN BESTAND GESEHEN (Sitzung 10, fuer die
                # mitlaufende Reservierung): dieselbe Zahl, nur dauerhaft am
                # gespeicherten Plan statt nur am offenen Fenster. Die
                # Reservierung gibt die Zutaten eines abgehakten Runs erst
                # frei, wenn der Bestand JUENGER ist als der Haken - sonst
                # gibt der Plan sie frei, waehrend ESI sie noch als vorhanden
                # meldet (Nutzer: "die ESI aktualisiert nur alle Stunde").
                _sst = getattr(self, "_bd_esi_stock_ts", None)
                if _sst is not None:
                    _pid_s = getattr(self, "_bd_open_plan_id", None)
                    if _pid_s is not None:
                        for _p_s in (self.settings.get("bau_saved_plans", [])
                                     or []):
                            if _p_s.get("id") == _pid_s:
                                _fr_s = _p_s.get("frozen")
                                if isinstance(_fr_s, dict):
                                    _fr_s["stock_seen_ts"] = float(_sst)
                                    config.save_settings(self.settings)
                                break
                # NUTZER-WUNSCH (Sitzung 8): Zeitpunkt der letzten
                # Bestands-AENDERUNG festhalten, nicht nur des Abrufs.
                # `vollstaendig=not failed`: ist auch nur ein Charakter-Abruf
                # gescheitert, ist der Bestand unvollstaendig - daraus wuerde
                # sonst eine Schein-Aenderung, und die Anzeige waere wertlos.
                try:
                    _stand = store.note_asset_snapshot(
                        _assets, vollstaendig=not failed)
                    self._bd_update_esi_stand(_stand)
                except Exception as _snap_err:
                    self._log_exception("Bestands-Zeitstempel", str(_snap_err))
                if _frozen:
                    _fs = {int(k): int(v) for k, v
                           in (_frozen.get("stock") or {}).items()}
                    # Letzten LIVE-Stand merken: "Neu berechnen" setzt den
                    # Bestand sonst wieder hart auf den Einfrier-Stand und
                    # die gerade gutgeschriebenen Zuwächse wären bis zum
                    # nächsten Abruf wieder weg.
                    self._bd_live_stock = dict(agg)
                    # Beim eingefrorenen Plan ist der Einfrier-Stand nicht in
                    # Lager/Pipeline zerlegbar - er zählt komplett als
                    # "ESI-Seite" (die Pipeline steckt bereits drin).
                    self._bd_esi_stock_base = self._merge_frozen_stock(_fs, agg)
                    self._bd_virt_stock = {}
                else:
                    self._bd_esi_stock_base = dict(_assets)
                    self._bd_virt_stock = dict(_virt_map)
                # KEIN stilles Überschreiben mehr: die Einfügung ersetzt nur
                # den Lager-Anteil, gilt nur solange sie neuer ist als ESI
                # (bzw. dauerhaft), und die Herkunft wird je Item mitgeführt.
                agg, _src = self._recompute_bd_stock()
                # Blaupausen-Cache erneuern - NUR wenn der Abruf fuer ALLE
                # Charaktere gelang (None = mindestens einer scheiterte, dann
                # bleibt der alte Stand; eine Teilliste waere schlimmer als
                # ein veralteter Vollstand). rebuild() unten liest den Cache
                # ueber _resolve_per_item_bp_cap - der Runplaner passt seine
                # Blaupausen-Deckel damit im selben Durchlauf an.
                if result.get("owned_bp") is not None:
                    self._bd_owned_bp_cache = result["owned_bp"]
                # Rohschichten fuer planer_diagnose.txt (26.09.2026): Hangar
                # ohne Pipeline und die Pipeline allein - nur zum Aufschreiben.
                self._bd_hangar_only = dict(_assets)
                self._bd_pipeline_live = dict(_virt_map)
                self._bd_active_jobs_map = result.get("active") or {}
                # Gelieferte Jobs fuer die Fortschritts-Erkennung eingefrorener
                # Plaene merken - VOR rebuild(), damit der Runplaner-Aufbau
                # sie im selben Durchlauf schon sieht.
                self._bd_delivered_jobs = result.get("delivered") or []
                # ZEITSTEMPEL DER JOB-DATEN. Ohne ihn kann die
                # Verlust-Warnung nicht wissen, ob sie auf frische Zahlen
                # schaut - und wuerde bei veralteten Job-Daten einen
                # Fehlbedarf melden, den es nicht gibt: verbrauchtes
                # Grundmaterial sieht dann aus wie verlorenes.
                import time as _t_jobs
                self._bd_jobs_ts = _t_jobs.time()
                rebuild()
                # Datenalter sichtbar machen (CCP cacht /assets/ ~1 h): so sieht
                # man sofort, ob frisch abgelieferte Outputs schon drin sein
                # KÖNNEN - statt sich über "nicht erkannte" Reaktionen zu wundern.
                parts = []
                if _manual:
                    _n_act = sum(1 for _i in (_src or {}).values()
                                 if _i.get("src") == "manuell")
                    if getattr(self, "_bd_manual_only", False):
                        parts.append(_txt("ONLY pasted stock: {n} item(s) \u2013 "
                                          "ESI hangar stock is OFF for this plan (job "
                                          "pipeline still counts)").format(n=len(_manual)))
                    elif _n_act:
                        parts.append(_txt("{n} item(s) from PASTED stock (").format(
                                         n=_n_act) +
                                     self._stock_age_text(
                                         getattr(self, "_bd_manual_ts", None))
                                     + (_txt(", permanent")
                                        if getattr(self, "_bd_manual_perm", False)
                                        else _txt(", newer than ESI")) + ")")
                    else:
                        parts.append(_txt("{n} pasted item(s) SUPERSEDED \u2013 the "
                                          "ESI data is fresher by now, ESI counts again"
                                          ).format(n=len(_manual)))
                if result.get("no_locations") and not getattr(
                        self, "_bd_nostruct_warned", False):
                    # EINMAL pro Dialog deutlich warnen, nicht nur eine Zeile
                    # in die Seitenleiste schreiben. Diese Warnung war der
                    # einzige Hinweis darauf, dass GAR KEIN Lagerbestand
                    # gezaehlt wird - sie darf nicht in einem Info-Block
                    # untergehen, den man ausblendet.
                    self._bd_nostruct_warned = True
                    from PySide6.QtWidgets import QMessageBox as _QMB2
                    _QMB2.warning(
                        dlg, _txt("No hangar stock is counted"),
                        _txt("None of your build structures is linked to a real EVE "
                             "structure.\n\nIn the \u201eBuild structures only\u201c scope, "
                             "therefore NO hangar stock is counted at all \u2013 only "
                             "running and finished jobs. The build costs are too high "
                             "because of this.\n\nFix: Structures tab \u2192 \u201e "
                             "Find locations and link all\u201c.\nImmediate workaround: set "
                             "the stock scope here on the right to \u201e "
                             "Everywhere\u201c."))
                if result.get("no_locations"):
                    # Die Struktur(en) BEIM NAMEN nennen und sagen, WO man es
                    # einstellt - "keine Struktur verknuepft" allein liess den
                    # Nutzer im Regen (er hatte ja Strukturen angelegt).
                    _unlinked = [str(_b.get("name") or "?") for _b in
                                 (self.settings.get("bau_structures", []) or [])
                                 if not _b.get("link_structure_id")]
                    _who = (": " + ", ".join(_unlinked[:4])
                            + ("\u2026" if len(_unlinked) > 4 else "")
                            ) if _unlinked else ""
                    parts.append(
                        _txt("\u26a0 None of your build structures is linked to a REAL "
                             "EVE structure") + _who
                        + _txt(" \u2013 in the \u201eBuild structures only\u201c scope, "
                               "therefore NO hangar stock is counted at all (only "
                               "running/finished jobs).\n   Fix: Structures tab \u2192 "
                               "Edit \u2192 field \u201e Real EVE structure\u201c. "
                               "Immediate workaround: scope to \u201e "
                               "Everywhere\u201c."))
                elif located and result.get("loc_names"):
                    parts.append(_txt("Stock only from: ")
                                 + ", ".join(result["loc_names"]))
                    # MESSUNG (Aufgabe "Bestand erreicht den Bauplan nicht"):
                    # Assets kamen an, aber KEINE Zeile haengt an den
                    # verknuepften structure_ids -> das ist die praezise
                    # Aussage, keine Vermutung. Moegliche Ursachen benennen
                    # und die Rohzahlen ins Fehlerprotokoll schreiben, damit
                    # die Ursache beim Nutzer OHNE Raten bestimmbar ist.
                    _ld = result.get("loc_diag") or {}
                    _rt = sum(int((d or {}).get("rows_total") or 0)
                              for d in _ld.values())
                    _ra = sum(int((d or {}).get("rows_at_loc") or 0)
                              for d in _ld.values())
                    if _rt and not _ra:
                        parts.append(_txt(
                            "\u26a0 NOT a single asset was found at the linked "
                            "structures \u2013 but the characters have {n} asset rows at "
                            "OTHER locations.\n   Typical causes: material sits in the "
                            "CORP hangar (the character-assets endpoint does not "
                            "return it \u2013 workaround: paste stock, \u201epermanent\u201c), "
                            "it sits with a character WITHOUT a role tick, or the link "
                            "points to a different structure_id. Details in fehler.log."
                        ).format(n=f"{_rt:,}".replace(",", "'")))
                        # de_scan2: aus  (fehler.log-Eintrag, nie in der Oberflaeche)
                        self._log_exception(
                            "Bestand-Ort",
                            "Ortsgebundener Abruf fand an den verknuepften "
                            "Strukturen keine Assets.\n"
                            f"loc_ids={result.get('loc_ids')}\n"
                            f"loc_names={result.get('loc_names')}\n"
                            + "\n".join(
                                f"  {n}: gesamt={d.get('rows_total')} "
                                f"an_orten={d.get('rows_at_loc')} "
                                f"je_ort={d.get('per_loc')}"
                                for n, d in _ld.items()) + "\n")
                _npool = len(self._runplan_pool_char_ids(self.settings))
                        # de_scan2: an
                # CORP-HANGAR (1.0.8): sagen, WAS gezaehlt wurde und WARUM
                # etwas nicht - "0 Bestand" allein liesse den Nutzer raten.
                _ci = result.get("corp") or {}
                if _ci.get("aktiv"):
                    if _ci.get("keine_division"):
                        parts.append(_txt(
                            "⚠ Corp hangars are ON, but no division is "
                            "selected – Settings → Corporation."))
                    for _c in _ci.get("corps") or []:
                        parts.append(_txt(
                            "Corp stock: {corp} via {char} – {divs} "
                            "({n} rows)").format(
                                corp=_c.get("name"), char=_c.get("via"),
                                divs=", ".join((_c.get("divisions") or {}).values()),
                                n=_c.get("rows", 0)))
                    if _ci.get("relink"):
                        parts.append(_txt(
                            "⚠ Re-link {names}: linked before the corp switch "
                            "was turned on, the login has no corp permission yet."
                        ).format(names=", ".join(_ci["relink"])))
                    if _ci.get("ohne_rolle"):
                        parts.append(_txt(
                            "⚠ No linked character holds the Director role in "
                            "{corps} – that corp hangar is NOT counted."
                        ).format(corps=", ".join(_ci["ohne_rolle"])))
                if _npool:
                    parts.append(_txt("Stock pool: {n} characters (all with role "
                                      "ticks)").format(n=_npool))
                if _frozen:
                    parts.append(_txt("Base frozen \u00b7 intermediates BUILT "
                                      "since are credited live"))
                _v = result.get("virtual") or {}
                if _v.get("units"):
                    _bits = []
                    if _v.get("ready"):
                        _bits.append(_txt("{n} finished (still to deliver!)").format(n=_v['ready']))
                    if _v.get("fresh"):
                        _bits.append(_txt("{n} freshly delivered").format(n=_v['fresh']))
                    if _v.get("running"):
                        _bits.append(_txt("{n} RUNNING (pipeline)").format(n=_v['running']))
                    parts.append(_txt("\u2795 {units} units from {jobs} jobs counted in").format(
                        units=f"{_v['units']:,}".replace(",", "'"), jobs=" + ".join(_bits)))
                if age is not None:
                    mins = int(age // 60)
                    parts.append(_txt("Stock per ESI \u00b7 as of {m} min ago").format(m=mins))
                    if mins >= 30:
                        parts.append(_txt("\u26a0 ESI caches assets for up to 1 h \u2013 "
                                          "freshly delivered items may still be missing"))
                if failed:
                    parts.append(_txt("\u26a0 Not loadable: {what} \u2013 the plan "
                                      "calculates WITHOUT their stock!").format(
                                          what=", ".join(failed)))
                # 🔒-RESERVIERUNGEN SICHTBAR MACHEN: der Abzug passiert in
                # _recompute_bd_stock (das adone unten anstoesst) - ein
                # still schrumpfender Bestand waere eine neue Falle. Namen
                # der reservierenden Plaene und abgezogene Stueckzahl klar
                # benennen (Arbeitsregel 6/10).
                _ra = getattr(self, "_bd_reserved_applied", None) or {}
                _rp = getattr(self, "_bd_reserved_plans", None) or []
                _pend = int(getattr(self, "_bd_reserved_pending", 0) or 0)
                if _ra:
                    _sum = sum(_ra.values())
                    _line = (_txt("Reserved by: ") + ", ".join(_rp)
                             + _txt(" \u2013 {types} material types / {units} units "
                                    "deducted").format(
                                 types=len(_ra), units=f"{_sum:,}".replace(",", "'")))
                    if _pend:
                        _line += _txt(" \u00b7 {n} units of the claim not on site yet (in "
                                      "transit?) \u2013 apply automatically on delivery"
                                      ).format(n=f"{_pend:,}".replace(",", "'"))
                    parts.append(_line)
                elif _rp:
                    _line = _txt("Reservations active ({plans}), but none of the "
                                 "local stock is affected").format(plans=", ".join(_rp))
                    if _pend:
                        _line += _txt(" \u2013 {n} units waiting for delivery").format(
                            n=f"{_pend:,}".replace(",", "'"))
                    parts.append(_line)
                # Panel rechts im Materialien-Tab nachziehen: ob die Einfügung
                # noch gilt, hängt am gerade geholten ESI-Zeitstempel.
                _sp = getattr(self, "_bd_sync_paste_panel", None)
                if _sp is not None:
                    _sp(refill_box=False)
                # KLEINGEDRUCKTES IN DEN TOOLTIP (Nutzer, Sitzung 16:
                # "dieses Kleingedruckte stoert mich, kann das weg").
                # NICHT geloescht, sondern verlegt: die Zeilen erklaeren den
                # Einfrier-Stand, die Pipeline und - wichtig - WELCHER Plan
                # gerade Material reserviert. Genau die Zeile hat heute den
                # Fall "Ametat II haelt 29,7 Mio Einheiten" aufgeklaert.
                # Sichtbar bleibt nur, was eine ENTSCHEIDUNG ausloest: eine
                # fremde Reservierung oder eine Warnung. Der Rest wandert
                # unter die Maus.
                # WORAN "wichtig" ERKANNT WIRD (Sitzung 16, zweite Fassung):
                # frueher am Emoji-Praefix (\U0001F512 / \u26a0). Seit die
                # Emojis raus sind, traegt nur noch die WARNUNG ein Zeichen -
                # die Reservierungszeile wird deshalb am Text erkannt.
                # Ein Praefix-Vergleich auf "" wuerde ALLES durchlassen; das
                # war beim Emoji-Umbau kurz der Fall.
                _res_kopf = _txt("Reserved by: ")
                _wichtig = [_p for _p in parts
                            if _p.lstrip().startswith("\u26a0")
                            or _res_kopf.strip() in _p]
                asset_age_lbl.setText("\n".join(_wichtig))
                asset_age_lbl.setVisible(bool(_wichtig))
                asset_age_lbl.setToolTip("\n".join(parts))
                asset_age_lbl.setStyleSheet(
                    f"font-size:11px; color:{theme.AMBER}; font-weight:700;"
                    if failed else "font-size:11px;")
                if failed:
                    self.statusBar().showMessage(
                        _txt("\u26a0 Assets/jobs partly not loadable ({who}) \u2013 the plan "
                             "calculates without this stock. Try again later (tick "
                             "off/on); the REASON per character is in fehler.log."
                        ).format(who=", ".join(failed)))
                used = (plan_ref.get("plan") or {}).get("stock_used") or {}
                if failed:
                    self._flash_tip(_txt("\u26a0 Assets loaded incompletely"))
                elif not used:
                    self._flash_tip(_txt("No matching assets found in stock"))
                elif located:
                    self._flash_tip(_txt("Assets subtracted (build structures only) \u2013 "
                                         "{n} material(s) reduced \u2713").format(n=len(used)))
                elif limited:
                    self._flash_tip(_txt("Assets subtracted (build structure not linked "
                                         "\u2013 only build/reaction characters counted) "
                                         "\u2013 {n} material(s) \u2713").format(n=len(used)))
                elif result.get("no_locations"):
                    self._flash_tip(_txt("\u26a0 No hangar stock counted \u2013 no build "
                                         "structure linked (scope: build structures only)"))
                else:
                    self._flash_tip(_txt("Assets subtracted ( ALL locations, per "
                                         "scope) \u2013 {n} material(s) \u2713").format(
                        n=len(used)))
            self._run(Worker(ajob), adone, label=_txt("Loading assets \u2026"))
        asset_cb.toggled.connect(_toggle_assets)
        # Gespeicherten "Assets abziehen"-Zustand wiederherstellen - ERST NACH dem
        # connect(), damit setChecked(True) den ESI-Abruf auch wirklich auslöst
        # (wie ein echter Klick). Nur einmalig anwenden (wie _bd_restore_checked).
        if getattr(self, "_bd_restore_assets_toggle", False):
            asset_cb.setChecked(True)
            self._bd_restore_assets_toggle = False

        # --- Einfrieren-Handler ("Alle Materialien gekauft") --------------------
        def _apply_frozen_ui():
            _is_frozen = bool(getattr(self, "_bd_frozen", None))
            # Bewusst NICHT mehr gesperrt: der Live-Abruf ersetzt den
            # eingefrorenen Bestand nicht, er schreibt nur ZUWÄCHSE gut
            # (max(eingefroren, live), s. _merge_frozen_stock) - Baufort-
            # schritt bleibt damit auch bei eingefrorenen Plänen sichtbar.
            asset_cb.setToolTip(
                _txt("Frozen: the purchasing stock stays fixed, intermediate "
                     "products BUILT since then are credited live.")
                if _is_frozen else
                _txt("Subtracts what already lies on your build structures per ESI."))
            _frozen_btn_text()
            _frozen_btn_style(_is_frozen)
            # MENGE SPERREN, solange der PLAN eingefroren ist (neue Payloads
            # mit plan_snapshot): der Plan kommt aus dem Schnappschuss - eine
            # geaenderte Menge daneben ergaebe Zahlen aus ZWEI Rechnungen
            # (Arbeitsregel 10). Alt-Payloads (nur Preise fest) rechnen den
            # Plan weiterhin selbst, dort bleibt die Menge frei.
            _snap_on = _is_frozen and bool(
                (self._bd_frozen or {}).get("plan_snapshot"))
            if _snap_on:
                _fq = int((self._bd_frozen or {}).get("qty") or 0)
                if _fq > 0 and qty_spin.value() != _fq:
                    qty_spin.setValue(_fq)
                qty_spin.setEnabled(False)
                qty_spin.setToolTip(_txt(
                    "Plan frozen \u2013 the quantity belongs to the frozen plan. "
                    "To change it, unfreeze first ( button)."))
            elif type_id == industry.BUENDEL_ID:
                # MULTI-BAUPLAN: die Menge bleibt IMMER gesperrt (1 Buendel),
                # der Tooltip von oben erklaert es - nicht wieder freigeben.
                qty_spin.setEnabled(False)
            else:
                qty_spin.setEnabled(True)
                qty_spin.setToolTip("")
            # Das Runs-Feld ist dieselbe Zahl - gesperrt und frei im Gleichtakt.
            if runs_spin is not None:
                runs_spin.setEnabled(qty_spin.isEnabled())
            # ALLES SPERREN, WAS DEN PLAN AENDERN WUERDE (Sitzung 17, Nutzer:
            # "unbedingt sperren solche Sachen"). Beim eingefrorenen Plan
            # rechnet production_plan NICHT mehr - ein Klick auf einen
            # Kategorie-Haken oder die Fertigungstiefe tat also NICHTS, ohne
            # dass man es sah. Stilles Nichtstun ist die schlechteste Antwort.
            # BEWUSST NICHT gesperrt: "Subtract assets" und der
            # Bestandsbereich - sie ersetzen den eingefrorenen Bestand nicht,
            # sie schreiben nur Zuwaechse gut (s. _merge_frozen_stock).
            _sperr_tip = _txt("Plan frozen \u2013 this would change the plan. "
                              "Unfreeze first ( button).")
            for _w in ([fbtn, pbtn]
                       + list((getattr(self, "_bp_own_boxes", None) or {}).values())
                       + list((getattr(self, "_depth_btns", None) or {}).values())):
                try:
                    _w.setEnabled(not _snap_on)
                    if _snap_on:
                        _w.setToolTip(_sperr_tip)
                except RuntimeError:
                    continue          # Widget gehoert zu einem alten Fenster
            if _is_frozen:
                fz = self._bd_frozen or {}
                d = (_time_mod.strftime("%d.%m.%Y %H:%M",
                                        _time_mod.localtime(fz["ts"]))
                     if fz.get("ts") else "?")
                if _snap_on:
                    asset_age_lbl.setText(
                        _txt("Plan frozen on {d} \u2013 structure, "
                             "quantities + run planner fixed; progress from ESI "
                             "jobs, profit live.").format(d=d))
                else:
                    asset_age_lbl.setText(_txt(
                        "Frozen on {d} \u2013 costs fixed, sale price + "
                        "build progress live.").format(d=d))
                asset_age_lbl.setStyleSheet("font-size:11px;")

        def _save_frozen_to_plan():
            pid = getattr(self, "_bd_open_plan_id", None)
            if pid is None:
                return
            for p in (self.settings.get("bau_saved_plans", []) or []):
                if p.get("id") == pid:
                    p["manual_stock"] = {str(k): int(v) for k, v in
                                         (getattr(self, "_bd_manual_stock",
                                                  None) or {}).items()}
                    p["manual_stock_ts"] = (
                        float(getattr(self, "_bd_manual_ts", None) or 0) or None)
                    p["manual_stock_perm"] = bool(
                        getattr(self, "_bd_manual_perm", False))
                    p["manual_stock_only"] = bool(
                        getattr(self, "_bd_manual_only", False))
                    p["frozen"] = (dict(self._bd_frozen)
                                   if getattr(self, "_bd_frozen", None) else None)
                    # "EINMAL GEDECKT" MUSS DEN NEUSTART UEBERLEBEN
                    # (Nutzer-Frage Sitzung 12: "wenn ich den 20mal oeffne
                    # und schliesse, sollte immer alles gleich bleiben?").
                    # Lebte es nur im Speicher, faenge die Verlust-Erkennung
                    # bei jedem Oeffnen bei null an - und ein zwischenzeitlich
                    # verlorenes Material saehe wieder aus wie ein
                    # gewoehnlicher Kauf-Posten. Damit waere die ganze
                    # Unterscheidung wertlos.
                    p["covered_once"] = sorted(
                        int(_x) for _x in
                        (getattr(self, "_bd_covered_once", None) or ()))
                    config.save_settings(self.settings)
                    break

        def _on_freeze_toggle(on):
            if on:
                self._bd_frozen = {
                    "ts": _time_mod.time(),
                    "qty": int(getattr(self, "_bd_qty", 1) or 1),
                    "prices": dict(getattr(self, "_bd_pricemap", {}) or {}),
                    "adjusted": dict((getattr(self, "_bd_opts", {}) or {})
                                     .get("adjusted_prices") or {}),
                    "stock": dict((getattr(self, "_bd_opts", {}) or {})
                                  .get("stock") or {}),
                    "cost_idx": dict(getattr(self, "_bau_cost_idx", None) or {}),
                    # NEU (Nutzer-Spez "Einfrieren friert den PLAN ein"): der
                    # komplette Plan als Schnappschuss. Solange eingefroren,
                    # wird production_plan NICHT mehr aufgerufen - Rezept-
                    # Struktur, Kauf/Bau-Entscheidungen, Mengen und Runplaner
                    # stehen damit fest; nur der Verkaufspreis des Endprodukts
                    # bleibt live. (JSON macht int-Keys zu Strings ->
                    # _plan_snapshot_unpack dreht das beim Laden zurueck.)
                    "plan_snapshot": self._plan_snapshot_pack(
                        (getattr(self, "_bd_plan_ref", None) or {})
                        .get("plan")),
                }
                self._bd_frozen_plan_cache = None
                _save_frozen_to_plan()
                _apply_frozen_ui()
                self._flash_tip(_txt("Plan frozen \u2713"))
                self.statusBar().showMessage(_txt(
                    "Frozen: recipe structure, quantities and run planner are fixed "
                    "from now on, progress is ticked off automatically from your ESI "
                    "jobs. Only the sale price of the final product stays live. Tip: "
                    "save the plan, then this survives a restart too."))
                if getattr(self, "_bd_open_plan_id", None) is None:
                    self._flash_tip(_txt("Frozen \u2013 SAVE the plan, or it is "
                                         "lost on closing!"))
            else:
                # WARNUNG VOR DEM AUFTAUEN (Sitzung 17, Nutzer: "kurz knapp
                # beschreiben, was dann die Folgen sind"). Der Plan wird neu
                # gerechnet - Kauf/Bau-Entscheidungen und die Reihenfolge im
                # Runplaner koennen sich aendern, obwohl schon eingekauft ist.
                if not self._auftauen_bestaetigen():
                    frozen_btn.blockSignals(True)
                    frozen_btn.setChecked(True)
                    frozen_btn.blockSignals(False)
                    return
                self._bd_frozen = None
                self._bd_frozen_plan_cache = None
                _save_frozen_to_plan()
                # Zurück zu Live-Daten: Preise frisch aus dem Markt-Snapshot,
                # Bestand per ESI neu (Häkchen wie ein echter Klick auslösen).
                _snap = store.get_snapshot()
                _pm_live = {s["type_id"]: s["sell_min"] for s in _snap
                            if s["sell_min"] > 0}
                if _pm_live:
                    self._bd_pricemap = _pm_live
                    self._bd_plan_cache = None   # neue Preise -> Plan neu
                self._bd_opts["adjusted_prices"] = (dict(self._adj_prices or {})
                                                    or dict(self._bd_pricemap))
                self._bd_opts.pop("stock", None)
                _apply_frozen_ui()
                rebuild()
                if asset_cb.isChecked():
                    _toggle_assets(True)
                else:
                    asset_cb.setChecked(True)
                self._flash_tip(_txt("Back to live prices & live stock"))
        frozen_btn.toggled.connect(_on_freeze_toggle)
        _apply_frozen_ui()

        def _menu(pos):
            it = tw.itemAt(pos)
            if not it:
                return
            tid = it.data(0, Qt.UserRole)
            if not tid:
                return
            # ALLE ausgewaehlten Zeilen mit type_id einsammeln (nicht nur die
            # angeklickte) - so lassen sich mehrere Items auf einmal setzen.
            _sel = [x for x in tw.selectedItems() if x.data(0, Qt.UserRole)]
            if it not in _sel:
                _sel = [it]
            # NUR DEN ITEMNAMEN nehmen. Die Zeile enthaelt zusaetzlich das
            # Kategorie-Suffix ("Gravimetric Sensor Cluster  \u00b7 Komponente")
            # und beim Endprodukt "(Endprodukt)" - beides wanderte mit in die
            # Blacklist, wo es dann zu keinem Item passte (Nutzer-Meldung:
            # "wird nicht erkannt, wahrscheinlich weil Komponente
            # mitkopiert wird"). Genau der Fehler, den die neue
            # Nicht-Treffer-Meldung sichtbar gemacht hat.
            _sel_names = []
            for _x in _sel:
                _nm = _x.text(0).split("  (")[0]
                _nm = _nm.split("\u00b7")[0].strip()
                if _nm and _nm not in _sel_names:
                    _sel_names.append(_nm)
            _bl_now = [str(x).strip() for x in
                       (self.settings.get("bau_blacklist_names", []) or [])
                       if str(x).strip()]
            _bl_lc = {self._bl_clean_name(x) for x in _bl_now}
            _add = [n for n in _sel_names
                    if self._bl_clean_name(n) not in _bl_lc]
            _rem = [n for n in _sel_names
                    if self._bl_clean_name(n) in _bl_lc]
            m = QMenu(self)
            a_mkt = m.addAction(icons.icon("trend_up"), _txt("Open in-game market"))
            def _bl_uebernehmen():
                """Blacklist speichern UND die Ausschlussliste neu rechnen.

                NUTZER-BEFUND (Sitzung 20): "man kann Sachen per Rechtsklick
                blacklisten, sie kommen ins Feld, aber es wird dennoch nicht
                geblacklistet." Genau so war es: hier stand nur `rebuild()`.
                Das zeichnet den Plan neu, rechnet aber `opts["excluded"]`
                NICHT - und die entsteht erst in
                `_bau_refresh_exclusions_and_rebuild`, demselben Auffrischer,
                den das Textfeld und die Gruppen-Haekchen benutzen.
                Der Name stand also im Feld und wirkte nichts.
                Gespeichert wird ebenfalls hier - sonst waere der Eintrag nach
                einem Neustart weg.
                """
                try:
                    config.save_settings(self.settings)
                except Exception:
                    pass
                self._bau_refresh_exclusions_and_rebuild()

            a_chart = m.addAction(icons.icon("chart"), _txt("Show history"))
            m.addSeparator()
            a_bl = a_unbl = None
            if _add:
                a_bl = m.addAction(
                    _txt("Add to blacklist")
                    + (_txt(" ({n} items)").format(n=len(_add))
                       if len(_add) > 1 else ""))
            if _rem:
                a_unbl = m.addAction(
                    _txt("\u21a9 Remove from blacklist")
                    + (_txt(" ({n} items)").format(n=len(_rem))
                       if len(_rem) > 1 else ""))
            ch = m.exec(tw.viewport().mapToGlobal(pos))
            if ch == a_mkt:
                self.open_ingame_market(tid)
            elif ch == a_chart:
                self._open_chart_for(tid, it.text(0))
            elif a_bl is not None and ch == a_bl:
                self.settings["bau_blacklist_names"] = _bl_now + _add
                self._push_blacklist_to_ui()
                self._flash_tip(_txt("Added to the blacklist: ")
                                + ", ".join(_add[:3])
                                + ("\u2026" if len(_add) > 3 else ""))
                _bl_uebernehmen()
            elif a_unbl is not None and ch == a_unbl:
                _rem_lc = {self._bl_clean_name(n) for n in _rem}
                self.settings["bau_blacklist_names"] = [
                    x for x in _bl_now
                    if self._bl_clean_name(x) not in _rem_lc]
                self._push_blacklist_to_ui()
                self._flash_tip(_txt("\u21a9 Removed from the blacklist: ")
                                + ", ".join(_rem[:3]))
                _bl_uebernehmen()
        tw.customContextMenuRequested.connect(_menu)

        # MENGE: NICHT BEI JEDEM TASTENDRUCK RECHNEN (Nutzer, Sitzung 20:
        # "wenn ich 120 tippen will rechnet es 3 mal, das macht es laggy").
        # `valueChanged` feuert je Ziffer, und rebuild() rechnet den ganzen
        # Plan im GUI-Thread - bei "120" also drei komplette Laeufe, von denen
        # zwei niemanden interessieren.
        # DERSELBE MECHANISMUS WIE BEI DER BLACKLIST (Sitzung 19): ein
        # Einzelschuss-Timer sammelt die Tastendruecke ein. Enter oder ein
        # Klick woanders hin rechnen SOFORT (`editingFinished`) - so wartet
        # niemand auf den Timer, der fertig getippt hat.
        # Die Pfeiltasten des Feldes loesen kein `editingFinished` aus,
        # deshalb bleibt der Timer als Netz dahinter.
        _qty_timer = QTimer(dlg)
        _qty_timer.setSingleShot(True)
        _qty_timer.setInterval(450)

        def _qty_uebernehmen():
            _qty_timer.stop()
            # NUR DAS OFFENE FENSTER (26.09.2026, in der b-Suite nachgestellt):
            # der 450-ms-Timer eines FRUEHEREN Bauplan-Fensters lief nach dem
            # Oeffnen des naechsten noch ab und schrieb dessen Menge (10) in
            # den gemeinsamen Zustand `_bd_qty` - samt rebuild() mit den
            # Widgets des alten Fensters. Ein anderes Fenster ist dran: nichts tun.
            if getattr(self, "_bd_dialog", None) is not dlg:
                return
            if int(getattr(self, "_bd_qty", 0) or 0) == qty_spin.value():
                return                     # nichts geaendert -> nicht rechnen
            self._bd_qty = qty_spin.value()
            rebuild()
        _qty_timer.timeout.connect(_qty_uebernehmen)
        qty_spin.valueChanged.connect(lambda _=0: _qty_timer.start())
        qty_spin.editingFinished.connect(_qty_uebernehmen)
        # Das Runs-Feld rechnet genauso sofort bei Enter/Verlassen - es
        # schreibt ins Stueckfeld, und von dort geht es denselben Weg.
        if runs_spin is not None:
            runs_spin.editingFinished.connect(_qty_uebernehmen)

        def _store_cat_me_te():
            self._bd_me_component = comp_me_spin.value()
            self._bd_te_component = comp_te_spin.value()
            self._bd_me_t1hull = hull_me_spin.value()
            self._bd_te_t1hull = hull_te_spin.value()
            self._bd_me_fuel = fuel_me_spin.value()
            self._bd_te_fuel = fuel_te_spin.value()
            self._bd_me_tools = tools_me_spin.value()
            self._bd_te_tools = tools_te_spin.value()
            # Ab jetzt ist der eingestellte Stand auch der GERECHNETE ->
            # Marker an "Neu berechnen" verschwindet.
            self._bd_me_te_applied = _current_me_te()
            _sync_recalc_marker()

        def _dlg_overlay_show(msg=_txt("Fetching order book prices \u2026")):
            ov = getattr(dlg, "_calc_overlay", None)
            if ov is None:
                ov = QFrame(dlg)
                ov.setStyleSheet("background: rgba(10,15,20,0.90); border-radius:10px;")
                ovl = QVBoxLayout(ov)
                ovl.setAlignment(Qt.AlignCenter); ovl.setSpacing(6)
                spin = QLabel("\u280B"); spin.setAlignment(Qt.AlignCenter)
                spin.setStyleSheet(f"color:{theme.CYAN}; font-size:40px; "
                                   f"font-family:{theme.MONO};")
                txt = QLabel(msg); txt.setAlignment(Qt.AlignCenter)
                txt.setWordWrap(True)
                txt.setStyleSheet(f"color:{theme.TEXT}; font-size:15px; "
                                  f"font-weight:600; padding-top:4px;")
                tiphead = QLabel(_txt("\u25C8 TIP")); tiphead.setAlignment(Qt.AlignCenter)
                tiphead.setStyleSheet(f"color:{theme.AMBER}; font-size:11px; "
                                      f"letter-spacing:2px; padding-top:16px;")
                tip = QLabel(""); tip.setAlignment(Qt.AlignCenter); tip.setWordWrap(True)
                tip.setMaximumWidth(480)
                tip.setStyleSheet(f"color:{theme.MUTED}; font-size:13px; padding:0 18px;")
                for w in (spin, txt, tiphead, tip):
                    ovl.addWidget(w, alignment=Qt.AlignCenter)
                ov.hide()
                timer = QTimer(dlg)
                frames = "\u280B\u2819\u2839\u2838\u283C\u2834\u2826\u2827\u2807\u280F"

                def _tick():
                    i = (getattr(dlg, "_calc_spin_i", 0) + 1) % len(frames)
                    dlg._calc_spin_i = i
                    spin.setText(frames[i])
                timer.timeout.connect(_tick)
                dlg._calc_overlay = ov
                dlg._calc_overlay_txt = txt
                dlg._calc_overlay_tip = tip
                dlg._calc_overlay_timer = timer
            else:
                dlg._calc_overlay_txt.setText(msg)
            try:
                dlg._calc_overlay_tip.setText(self._pick_tip() if hasattr(
                    self, "_pick_tip") else "")
            except Exception:
                pass
            ov.setGeometry(0, 0, dlg.width(), dlg.height())
            ov.show(); ov.raise_()
            dlg._calc_overlay_timer.start(90)

        def _dlg_overlay_hide():
            ov = getattr(dlg, "_calc_overlay", None)
            if ov is not None:
                ov.hide()
                getattr(dlg, "_calc_overlay_timer", None) and dlg._calc_overlay_timer.stop()

        def _esi_lade_anzeige(an):
            """Dezente Anzeige in der Bestands-Zeile, solange ESI laeuft.

            NUTZER (Sitzung 14): "wenn der Bauplan ESI zieht koennen wir das
            im Bauplanfenster anzeigen? ESI laden oder so." Er hatte den
            5-Minuten-Nachlauf nur daran gemerkt, dass sich die Zahlen
            ploetzlich aenderten - waehrend er Jobs plante.

            NICHT das grosse Overlay: der Nachlauf soll den Nutzer beim
            Arbeiten nicht blockieren (so stand es auch im Kommentar am
            Timer - der Code zeigte es aber trotzdem, s. `still`-Schalter).
            """
            lbl = getattr(self, "_bd_esi_stand_lbl", None)
            if lbl is None:
                return
            _basis = getattr(self, "_bd_esi_stand_text", None)
            if _basis is None:
                _basis = self._bd_esi_stand_text = lbl.text()
            lbl.setText(_basis + ("   " + _txt("ESI loading \u2026") if an else ""))

        def _run_esi_load_all(still=False):
            # LAEUFT-MERKER fuer den automatischen Nachlauf: zwei
            # parallele ESI-Laeufe wuerden sich die Ergebnisse
            # ueberschreiben und CCPs Fehlerbudget verbrauchen.
            self._bd_esi_busy = True
            self._bd_esi_stand_text = None    # Basistext neu einlesen
            _esi_lade_anzeige(True)
            if not still:
                _dlg_overlay_show(_txt("Loading blueprints from ESI \u2026"))

            def _job():
                return self._load_all_esi_for_plan_core(type_id)

            def _done(result):
                self._bd_esi_busy = False
                _esi_lade_anzeige(False)
                _dlg_overlay_hide()
                summary, err, owned_bp = result
                if err:
                    QMessageBox.warning(self, _txt("Load everything from ESI"), err)
                    return
                # Blueprints-Tab-Tabelle mit DERSELBEN gemeinsam geholten
                # Blaupausen-Liste befüllen - kein zweiter, paralleler
                # ESI-Abruf mehr nötig.
                try:
                    _apply_bp_ownership(owned_bp)
                except Exception:
                    pass
                self._bd_refresh_bp_stage_info()
                cb = getattr(self, "_bd_full_rebuild", None)
                if cb:
                    cb()
                if summary:
                    self._flash_tip(" \u00b7 ".join(summary) + " \u2713")
                else:
                    # NUTZER (Sitzung 8, ZWEITER Fund derselben Sorte):
                    # "Wenn ich einen Bauplan oeffne und deren Blueprints
                    # nicht habe, kommt dieses Warnpopup und der Bauplan
                    # rutscht in den Hintergrund. Das nervt." Beim ersten
                    # Mal wurde eine ANDERE, fast gleich aussehende Stelle
                    # entschaerft - diese hier blieb stehen. "Keine BPs
                    # gefunden" ist kein Fehler, sondern der Normalfall bei
                    # T2-Items, die man noch nicht erforscht hat.
                    self._flash_tip(_txt("no blueprints of your own"))

                # Nach dem Lauf den Bauplan-Dialog nach vorne holen - jeder
                # Dialog waehrend des Ladens aktiviert sonst die MainWindow
                # und schiebt den parentlosen Bauplan dahinter.
                QTimer.singleShot(0, lambda: dlg.raise_()
                                  or dlg.activateWindow())

            def _fail(msg):
                # AUCH IM FEHLERFALL freigeben - sonst blockiert ein einziger
                # misslungener Abruf den automatischen Nachlauf fuer immer.
                self._bd_esi_busy = False
                _dlg_overlay_hide()
                QMessageBox.warning(self, _txt("Load everything from ESI"),
                                   _txt("Error while loading: ") + str(msg))
                QTimer.singleShot(0, lambda: dlg.raise_()
                                  or dlg.activateWindow())
            self._run(Worker(_job), _done, fail_cb=_fail, overlay=False)
        esi_all_btn.clicked.connect(_run_esi_load_all)
        # Automatisch beim Öffnen laden (einmalig), damit der Runplaner von
        # Anfang an mit den echten Blaupausen-Daten rechnet, statt erst auf
        # einen Klick zu warten und bis dahin "unbegrenzt" anzunehmen.
        if self.settings.get("client_id") and store.list_characters():
            QTimer.singleShot(50, _run_esi_load_all)
            # Nach dem automatischen Lauf den Bauplan-Dialog vorne halten -
            # der ESI-Lauf lief im Hintergrund, und jeder Dialog-Aufruf
            # (frueheres QMessageBox, Fehler-Box) haette das Fenster hinter
            # die MainWindow geschoben. 150 ms reichen, damit der Worker-
            # Start durch ist, ohne dass der Nutzer Flackern sieht.
            QTimer.singleShot(150, lambda: dlg.raise_() or dlg.activateWindow())

            # AUTOMATISCHER NACHLAUF, solange der Bauplan offen ist
            # (Nutzer: "der Runplaner reagiert nicht oder bleibt stehen").
            #
            # Bisher lief der ESI-Abruf NUR beim Oeffnen. Wer den Plan offen
            # liess und im Spiel weiterbaute, sah stundenlang den alten Stand
            # - der Runplaner leerte sich nicht, und die Verlust-Warnung
            # rechnete mit veralteten Job-Daten.
            #
            # STILL UND OHNE LADEBILDSCHIRM: der Nutzer arbeitet am Plan, ein
            # Overlay alle zwei Minuten waere unertraeglich. Laeuft schon ein
            # Abruf, wird dieser Takt uebersprungen statt zwei parallel zu
            # starten.
            _nach_timer = QTimer(dlg)
            # 5 MINUTEN, nicht kuerzer: CCP liefert Industrie-Jobs mit
            # 300 s Cache. Haeufiger zu fragen bringt keine neuen Daten und
            # verbraucht nur das Fehlerbudget. (Assets kommen sogar nur
            # stuendlich - dafuer gibt es die Einfuege-Funktion.)
            _nach_timer.setInterval(300_000)          # 5 Minuten

            def _nachlauf():
                if getattr(self, "_bd_esi_busy", False):
                    return          # laeuft schon - Takt auslassen
                try:
                    # STILL: kein Ladebildschirm mitten in der Arbeit. Nur die
                    # dezente Zeile oben zeigt, dass gerade geladen wird -
                    # genau das, was im Kommentar am Timer schon versprochen
                    # war, aber nicht umgesetzt: `_run_esi_load_all()` zeigte
                    # auch beim Nachlauf das volle Overlay.
                    _run_esi_load_all(still=True)
                except Exception as _nl_err:
                    # Nachlauf ist Komfort, nie kritisch - aber nicht stumm:
                    # ein `pass` hat in dieser Sitzung schon zweimal einen
                    # Ausfall verdeckt.
                    _esi_lade_anzeige(False)
                    self._log_exception("ESI-Nachlauf", str(_nl_err))

            _nach_timer.timeout.connect(_nachlauf)
            _nach_timer.start()
            # BEIM SCHLIESSEN ANHALTEN - nicht erst beim Zerstoeren.
            #
            # `destroyed` reicht NICHT: der Dialog wird beim Schliessen nur
            # versteckt, nicht geloescht. Nachgemessen (Sonde am laufenden
            # Fenster): der Takt lief nach `close()` munter weiter und haette
            # fuer einen laengst geschlossenen Bauplan alle zwei Minuten ESI
            # abgefragt - verschwendete Abrufe, und schlimmer: er haette den
            # `_bd_*`-Zustand eines Plans ueberschrieben, den der Nutzer gar
            # nicht mehr offen hat.
            dlg.destroyed.connect(_nach_timer.stop)
            _alt_close = dlg.closeEvent

            def _close_stop(ev):
                _nach_timer.stop()
                _alt_close(ev)

            dlg.closeEvent = _close_stop

        def _hakerl_reset():
            """Runplaner-Haekchen zuruecksetzen + sofort im Plan sichern.
            NUTZER-ENTSCHEIDUNG (Falcon-Screenshot, Sitzung 7): "wenn Neu
            berechnen geklickt wird, sollen ja auch die Runs neu berechnet
            werden" - alte "ingame gestartet"-Haken gehoeren zur ALTEN
            Rechnung und klebten sonst auf den frischen Zeilen (Titanium
            Carbide stand durchgestrichen da, obwohl ingame nichts lief).
            NICHT still (Regel 6): der Aufrufer zeigt eine Meldung an.
            Nur fuer den expliziten "Neu berechnen"-Weg - Mengen-Spinner &
            Co. rechnen zwar auch, aber dort waere das Wegraeumen bei jedem
            Tipp-Schritt eine Ueberraschung."""
            if not getattr(self, "_bd_runplan_checked", None):
                return False
            self._bd_runplan_checked = set()
            self._bd_runplan_auto = {}
            _sched_save_now()          # sofort sichern, nicht entprellt -
                                       # der Klick ist eine bewusste Aktion
            return True

        def _recompute():
            self._bd_qty = qty_spin.value()
            if (me_spin.value() != int(getattr(self, "_bd_me", 0) or 0)
                    or te_spin.value() != int(getattr(self, "_bd_te", 0) or 0)):
                self._bd_me_manuell = True
            self._bd_me = me_spin.value()
            self._bd_te = te_spin.value()
            _store_cat_me_te()
            if getattr(self, "_bd_frozen", None):
                if (self._bd_frozen or {}).get("plan_snapshot"):
                    # PLAN eingefroren (Nutzer-Spez): "Neu berechnen" wuerde
                    # genau die Verschiebung ausloesen, gegen die das
                    # Einfrieren gebaut ist (2'665 -> 2'789 GSC-Runs). Deshalb
                    # erst fragen - Ja loest den 🔒-Knopf, dessen Aus-Zweig
                    # rebuild() + Live-Bestand ohnehin schon sauber macht
                    # (EINE Wahrheit, kein zweiter Auftau-Pfad).
                    _ans = QMessageBox.question(
                        self, _txt("Recalculate"),
                        _txt("Plan is frozen \u2013 unfreeze and recalculate?\n\nAfter that, "
                             "recipe structure, quantities and run planner are LIVE again "
                             "(and may shift compared to the purchase). Run planner ticks "
                             "are reset in the process \u2013 they belong to the old "
                             "calculation."))
                    if _ans == QMessageBox.Yes:
                        # Erst leeren, dann auftauen: der rebuild() im
                        # Aus-Zweig baut den Runplaner schon ohne Alt-Haken.
                        _hakerl_reset()
                        frozen_btn.setChecked(False)   # -> _on_freeze_toggle(False)
                    return
                # ALT-Payload (nur Preise eingefroren, kein plan_snapshot):
                # bisheriges Verhalten - ME/TE/Menge uebernehmen und mit den
                # festgenagelten Preisen neu rechnen, ohne Live-Orderbuch.
                self._bd_ladder_result = None
                rebuild()
                self._flash_tip(_txt("Recalculated with frozen prices"))
                return
            # NEUE RECHNUNG = NEUE RUNS: die alten "ingame gestartet"-Haken
            # gehoeren nicht mehr dazu (Nutzer-Entscheidung, s. _hakerl_reset).
            if _hakerl_reset():
                self._flash_tip(_txt("\u21bb Runs recalculated \u2013 old run planner "
                                     "ticks reset"))
            # Live-Orderbuch-Abruf als EIGENER Hintergrund-Job, statt wie bisher
            # den ganzen Dialog zu schließen und neu zu öffnen (dlg.accept() +
            # Neuaufbau) - das Fenster bleibt jetzt offen, nur rebuild() läuft
            # danach mit dem frischen Ladder-Ergebnis. Eigenes kleines Lade-
            # Overlay IM Dialog (Spinner + Tipp, wie gewohnt), statt des
            # großen Haupt-Overlays, das hinterm modalen Dialog nicht sichtbar
            # wäre.
            _ladder_refresh()

        def _ladder_refresh():
            """Orderbuch-Abruf im Hintergrund, danach rebuild() - der Teil von
            "Recalculate", der die Preise holt. Eigene Funktion, damit ihn
            auch die Reprocessing-Schalter ausloesen koennen (Nutzer
            19.09.2026: "es soll automatisch nach dem Anhaken das selber
            machen")."""
            _qty_now = qty_spin.value()
            _dlg_overlay_show()

            def _ladder_job():
                _l_region, _l_station, _l_struct = self._active_hub()

                def _lpf(n):
                    return industry.production_plan(type_id, n, self._bd_pricemap.get,
                                                     self._bd_recipes, self._bd_opts)

                def _lof(mtid):
                    try:
                        ob = self._hub_orders(int(mtid), _l_region, _l_station, _l_struct)
                        return ob.get("sell", [])
                    except Exception:
                        return []
                rows = industry.ladder_cost_curve([_qty_now], _lpf, _lof,
                                                  price_fn=self._bd_pricemap.get)
                return rows[0] if rows else None

            def _ladder_done(result):
                self._bd_ladder_result = result
                self.build_status.setText("")
                _dlg_overlay_hide()
                rebuild()

            def _ladder_fail(msg):
                self.build_status.setText(_txt("Recalculation failed: ") + str(msg))
                _dlg_overlay_hide()
                rebuild()
            self._run(Worker(_ladder_job), _ladder_done, fail_cb=_ladder_fail,
                      label=_txt("Order book prices \u2026"), overlay=False)
        recalc.clicked.connect(_recompute)

        def _toggle(checked=False):
            self._bd_force = bool(checked)
            self._bd_opts["force_build"] = bool(checked)
            rebuild()
        fbtn.clicked.connect(_toggle)

        def _toggle_prefer(checked=False):
            self._bd_prefer_owned = bool(checked)
            self._bd_opts["prefer_build_if_owned"] = bool(checked)
            rebuild()
        pbtn.clicked.connect(_toggle_prefer)

        # BUGFIX (4. und tats\u00e4chlich letzter Versuch - siehe die drei
        # vorherigen Kommentare unten f\u00fcr die Fehlschl\u00e4ge, alle mit echten
        # Dialog-Tests widerlegt): ME/TE des Endprodukts hatten bisher GAR
        # KEINEN Live-Handler.
        # WARUM SELBST "Neu berechnen" DAS NICHT KORRIGIERT: self._bd_opts wird
        # nur EINMAL beim \u00d6ffnen des Dialogs per "self._bd_opts = dict(opts)"
        # gesetzt (Zeile ~6546) - eine KOPIE, kein Alias. Danach schreibt NICHTS
        # den Schl\u00fcssel "me" (oder "me_map"[type_id]) je wieder neu - auch
        # "Neu berechnen"/_recompute() nicht, das nur self._bd_me aktualisiert,
        # aber nie in self._bd_opts zur\u00fcckschreibt. Direkter Fix: exakt
        # dieselbe eff_me-Formel wie beim ersten \u00d6ffnen (Zeile ~6400) hier
        # erneut anwenden UND direkt in self._bd_opts schreiben - genau das
        # Muster, das "Alles selbst bauen"/"Rest mitbauen" schon nutzen.
        def _on_me_te_finished():
            # NUR BEI ECHTER AENDERUNG (Nutzer, Sitzung 20: beim Bearbeiten von
            # ME/TE "verschwindet die Anzeige kurzzeitig komplett").
            # `editingFinished` feuert auch beim blossen VERLASSEN des Feldes -
            # von ME nach TE zu klicken loeste also einen vollen Rebuild aus,
            # der die Karte abreisst und neu aufbaut, ohne dass sich ein Wert
            # geaendert hat.
            if (me_spin.value() == int(getattr(self, "_bd_me", 0) or 0)
                    and te_spin.value() == int(getattr(self, "_bd_te", 0) or 0)):
                return
            # SELBST GESETZT: ab hier fasst die ESI-Vorbelegung die Felder nicht
            # mehr an (Sitzung 20). Wer bewusst 0 eintraegt, behaelt 0.
            self._bd_me_manuell = True
            self._bd_me = me_spin.value()
            self._bd_te = te_spin.value()
            _rig = self._bau_rig_me()
            _eff_me = (1 - (1 - self._bd_me / 100.0) * (1 - _rig / 100.0)) * 100.0
            self._bd_opts["me"] = _eff_me
            _mm = self._bd_opts.get("me_map")
            if isinstance(_mm, dict) and type_id in _mm:
                _mm[type_id] = _eff_me   # sonst hätte der alte me_map-Eintrag Vorrang
            # NICHT DIREKT rebuild() AUFRUFEN - APP-ABSTURZ (Nutzer: "TE
            # eingeben im Bauplan, App schliesst sich, keine Fehlermeldung").
            # `editingFinished` feuert MITTEN in Qts Fokusbehandlung fuer genau
            # diesen Spinner. rebuild() baut den Invention-Tab neu auf und
            # loescht dabei per deleteLater() alle Karten - auch die, in der
            # dieser Spinner gerade steckt. Ein Widget, das aus seinem eigenen
            # Signal heraus sein Elternteil abraeumt, ist in Qt ein harter
            # Absturz (C++-Ebene, deshalb kein Python-Traceback und nichts in
            # fehler.log). singleShot(0, ...) haengt den Rebuild an die
            # Ereignisschleife: er laeuft erst, wenn Qt mit dem Fokuswechsel
            # fertig ist. Fuer den Nutzer identisch, nur einen Wimpernschlag
            # spaeter.
            QTimer.singleShot(0, rebuild)
        me_spin.editingFinished.connect(_on_me_te_finished)
        te_spin.editingFinished.connect(_on_me_te_finished)

        from PySide6.QtWidgets import QSpinBox as _SBx
        _amber_btn = (f"QPushButton{{background:rgba(242,162,60,0.14); color:{theme.AMBER}; "
                      f"border:1px solid rgba(242,162,60,0.45); border-radius:7px; "
                      f"padding:9px 16px; font-weight:700;}}"
                      f"QPushButton:hover{{background:rgba(242,162,60,0.26);}}")
        _cyan_btn = (f"QPushButton{{background:{theme.CYAN_FILL}; color:{theme.CYAN}; border:none; "
                     f"border-radius:7px; padding:9px 16px; font-weight:700;}}"
                     f"QPushButton:hover{{background:#5fe9d4;}}")
        # Nutzer-Vorgabe: Puffer und Fracht gehoeren nach OBEN zu den
        # Grundeinstellungen, nicht in die Fusszeile. Eigene Zeile direkt
        # unter der Kopfleiste - dort ist Platz, und unten bleiben nur noch
        # die Aktionen.
        r2s = QHBoxLayout(); r2s.setContentsMargins(0, 0, 0, 0)
        r2 = QHBoxLayout()
        # PUFFER gehoert zur Einkaufsliste, nicht zu den Grundeinstellungen
        # (Nutzer). Er wirkt beim Hinzufuegen zum Wagen - also steht er auch
        # dort unten, direkt neben dem Knopf.
        # PUFFER UND EINKAUFSWAGEN-KNOPF ENTFERNT (Nutzer: "alles ist jetzt
        # ueber den Material-Tab machbar"). Beides ist in das Einkaufsfenster
        # gewandert, das "Einkaufsliste erstellen" oeffnet - dort stehen die
        # Mengen, der Puffer und beide Kopier-Knoepfe beieinander, und die
        # Zahlen stammen nachweislich aus derselben Rechnung wie der Plan.
        # Die EINSTELLUNG `bau_buy_surplus` bleibt: das Fenster liest und
        # schreibt sie, ebenso `_plan_to_cart` fuer andere Aufrufer.
        r2.addSpacing(14)
        _tl = QLabel(_txt("Cargo hold:")); _tl.setObjectName("Muted"); r2s.addWidget(_tl)
        transport_cap_spin = _SBx(); transport_cap_spin.setRange(0, 5_000_000)
        transport_cap_spin.setSingleStep(10000); transport_cap_spin.setSuffix(" m\u00b3")
        transport_cap_spin.setMaximumWidth(110)
        transport_cap_spin.setValue(int(self.settings.get("bau_transport_m3", 350000)))
        transport_cap_spin.setToolTip(_txt("Cargo per trip in m\u00b3 \u2013 ~350'000 m\u00b3 = 1 "
                                           "jump freighter. 0 = unlimited (no warning/trips)."))
        r2s.addWidget(transport_cap_spin)
        # Beide Kostenarten UNTEREINANDER, kein Entweder/Oder mehr
        # (Nutzer-Fall: Frachtdienst nach ISK/m\u00b3 UND zusaetzlich eigene
        # Jumpfrachter-Spruenge, deren Fuel als Pauschale pro Fahrt anfaellt).
        # Beides wird addiert; ein Feld auf 0 faellt einfach weg.
        _tcol = QVBoxLayout(); _tcol.setContentsMargins(0, 0, 0, 0); _tcol.setSpacing(2)
        _trow1 = QHBoxLayout(); _trow1.setContentsMargins(0, 0, 0, 0); _trow1.setSpacing(4)
        _tlbl1 = QLabel(_txt("Freight service:")); _tlbl1.setObjectName("Muted")
        _tlbl1.setMinimumWidth(96)
        _trow1.addWidget(_tlbl1)
        transport_rate_m3_spin = IskGroupedSpin()
        transport_rate_m3_spin.setRange(0, 2_000_000_000)
        transport_rate_m3_spin.setMaximumWidth(140)
        transport_rate_m3_spin.setSuffix(" ISK/m\u00b3")
        transport_rate_m3_spin.setSingleStep(10)
        transport_rate_m3_spin.setValue(int(self.settings.get("bau_transport_rate", 0)))
        transport_rate_m3_spin.setToolTip(_txt(
            "ISK per m³ of transport volume – e.g. the price of your "
              "hauling service.\nMultiplied by the total volume of the "
              "shopping list and charged ON TOP of the flat fee below."))
        _trow1.addWidget(transport_rate_m3_spin)
        _tcol.addLayout(_trow1)
        _trow2 = QHBoxLayout(); _trow2.setContentsMargins(0, 0, 0, 0); _trow2.setSpacing(4)
        _tlbl2 = QLabel(_txt("Own trip:")); _tlbl2.setObjectName("Muted")
        _tlbl2.setMinimumWidth(96)
        _trow2.addWidget(_tlbl2)
        transport_rate_trip_spin = IskMillionSpin()
        transport_rate_trip_spin.setRange(0, 100_000)
        transport_rate_trip_spin.setSingleStep(1)
        transport_rate_trip_spin.setMaximumWidth(140)
        transport_rate_trip_spin.setValue(
            float(self.settings.get("bau_transport_trip_cost", 0) or 0) / 1_000_000.0)
        transport_rate_trip_spin.setToolTip(_txt(
            "A flat amount per TRIP – e.g. the fuel cost of your "
              "jump freighter jump.\nIt is multiplied by the number of "
              "trips needed (volume ÷ cargo hold, rounded up) and "
              "charged ON TOP of the hauling service above.\nEnter in "
              "millions or billions, e.g. 50M or 1.2B."))
        _trow2.addWidget(transport_rate_trip_spin)
        _tcol.addLayout(_trow2)
        r2s.addLayout(_tcol)
        freight_dec_cb = QCheckBox(_txt("Freight in decision"))
        freight_dec_cb.setChecked(
            bool(self.settings.get("bau_freight_in_decision", True)))
        freight_dec_cb.setToolTip(_txt(
            "ON: the freight service rate (ISK/m\u00b3) is added to the purchase price "
            "of every material \u2013 the plan then decides \u201ebuy or build\u201c with the "
            "LANDED price instead of the hub price. Bulky material becomes less "
            "attractive, compact material more.\n"
            "The freight cost is then inside \u201eBuild cost/unit\u201c and is NOT "
            "deducted twice.\n"
            "OFF: decision purely by hub price, freight cost deducted from profit "
            "only at the end (old behaviour).\n"
            "The flat rate per trip is NEVER apportioned \u2013 it is a step function "
            "(an item costs nothing extra until it tips the trip) and stays a "
            "plan-level line."))
        r2s.addWidget(freight_dec_cb)
        r2s.addStretch()
        # FRACHT EINKLAPPEN (Nutzer: "das mit dem Frachtraum stoert mich
        # noch"). Diese vier Werte stellt man einmal ein und fasst sie dann
        # monatelang nicht an - als Dauerzeile kosten sie eine ganze
        # Bildschirmzeile. Eingeklappt bleibt nur eine schmale Kopfzeile.
        _fr_w = QWidget(); _fr_w.setLayout(r2s)
        # ZUSATZKOSTEN (Nutzer-Wunsch): frei eingebbarer Betrag, der vom Gewinn
        # abgeht - z.B. gekaufte BPCs, Vermittlungsgebuehren, Corp-Abgaben.
        # Bewusst EIN Feld ohne Kategorien: was da hineingehoert, weiss der
        # Nutzer besser als wir, und jede Kategorienliste waere geraten.
        _xc_row = QHBoxLayout(); _xc_row.setSpacing(6)
        _xc_lbl = QLabel(_txt("Total amount:")); _xc_lbl.setObjectName("Muted")
        _xc_row.addWidget(_xc_lbl)
        # IskMillionSpin statt roher QDoubleSpinBox: zeigt 850 als "850M" und
        # 1150 als "1,15B" und nimmt beide Schreibweisen auch entgegen. Die
        # Klasse gibt es schon - kein zweites Zahlenformat erfinden.
        extra_cost_spin = IskMillionSpin()
        extra_cost_spin.setRange(0.0, 1_000_000.0)
        extra_cost_spin.setDecimals(2)
        extra_cost_spin.setMaximumWidth(130)
        extra_cost_spin.setValue(
            float(self.settings.get("bau_extra_cost", 0) or 0) / 1_000_000.0)
        extra_cost_spin.setToolTip(_txt(
            "A freely entered amount deducted from the profit – e.g. "
              "purchased BPCs, brokerage, corp dues.\nApplies to the "
              "WHOLE build plan, not per unit."))
        _xc_row.addWidget(extra_cost_spin)
        _xc_row.addStretch()
        _xc_w = QWidget(); _xc_w.setLayout(_xc_row)
        # Beide Sektionen NEBENEINANDER in einer Zeile, jede nur so breit wie
        # ihr Text (compact_header) - vorher zog sich "Fracht & Transport"
        # ueber die volle Fensterbreite, ohne dass da etwas stand.
        _tp_row = QVBoxLayout(); _tp_row.setContentsMargins(0, 0, 0, 0)
        _tp_row.setSpacing(6)
        _tp_row.addWidget(self._collapsible(
            _txt("Freight cost"), _fr_w, expanded=False,
            compact_header=True,
            tip=_txt("Cargo hold, freight service (ISK/m\u00b3), flat rate per own "
                     "trip and whether freight goes into the buy-or-build decision. "
                     "Set once, then leave collapsed.")))
        _tp_row.addWidget(self._collapsible(
            _txt("Extra cost"), _xc_w, expanded=False,
            compact_header=True,
            tip=_txt("One-off amount for this build plan that is deducted from the "
                     "profit \u2013 e.g. bought BPCs.")))
        _tp_w = QWidget(); _tp_w.setLayout(_tp_row)
        # IN DIE OBERE ZEILE (Nutzer: "nur in einer Linie, aktuell sinds 2").
        # VOR den Stretch einfuegen, sonst landen beide Sektionen ganz rechts
        # am Fensterrand statt neben den Bedienelementen. Kein eigener Stretch
        # im _tp_row - den liefert ctrl, zwei hintereinander wuerden den Platz
        # aufteilen und die Sektionen mittig zerren.
        # Nicht mehr in die Kopfzeile - dieselbe Details-Zeile wie Verkaufsort
        # und -charakter. VOR dem Stretch einfuegen, sonst rutschen die beiden
        # Klapp-Koepfe an den rechten Fensterrand.
        _set_row.addWidget(_tp_w)
        _set_row.addStretch()

        # NEURECHNUNG ENTKOPPELN. Erster Wurf haengte `rebuild()` direkt an
        # editingFinished - das rechnet `production_plan` ueber den GANZEN
        # Baum, im GUI-Thread, und editingFinished feuert bei jedem
        # Fokuswechsel und jedem Pfeilklick. Ergebnis beim Nutzer: "laedt
        # relativ lange und friert paar mal fast ein".
        # Zwei Bremsen:
        #   (1) nur bei ECHTER Aenderung - der bisherige Wert wird gemerkt.
        #   (2) Entprellung: schnelle Klicks loesen EINE Rechnung aus, nicht N.
        # Die Zusatzkosten aendern den Plan nicht, nur Gewinn/Marge - ein
        # vollstaendiger Neuaufbau ist hier ohnehin mehr als noetig; das
        # bleibt der naechste Schritt (s. OFFENE_PUNKTE).
        _xc_last = {"v": float(self.settings.get("bau_extra_cost", 0) or 0)}
        _xc_timer = QTimer(dlg)
        _xc_timer.setSingleShot(True)
        _xc_timer.setInterval(450)

        def _apply_extra_cost():
            _cb = getattr(self, "_bd_full_rebuild", None)
            if callable(_cb):
                _cb()

        _xc_timer.timeout.connect(_apply_extra_cost)

        def _save_extra_cost(*_a):
            _new = float(extra_cost_spin.value()) * 1_000_000.0
            if abs(_new - _xc_last["v"]) < 0.5:
                return          # unveraendert - nichts tun
            _xc_last["v"] = _new
            self.settings["bau_extra_cost"] = _new
            config.save_settings(self.settings)
            _xc_timer.start()   # entprellt: erst 450 ms nach der letzten Eingabe

        extra_cost_spin.editingFinished.connect(_save_extra_cost)
        extra_cost_spin.valueChanged.connect(_save_extra_cost)

        # ENTPRELLT wie die Zusatzkosten daneben (gleiche Mechanik, gleicher
        # Grund): `valueChanged` feuert bei JEDER getippten Ziffer. Vorher hing
        # daran direkt ein config.save_settings() UND ein komplettes rebuild()
        # des Plans - bei "350000" also sechs volle Neuberechnungen hinter-
        # einander. Der Nutzer sah ein eingefrorenes Fenster ("einige Sekunden
        # spaeter war es wieder da, aber es war knapp"). Jetzt wird 450 ms nach
        # der LETZTEN Eingabe genau einmal gerechnet.
        _tr_timer = QTimer(dlg)
        _tr_timer.setSingleShot(True)
        _tr_timer.setInterval(450)

        def _apply_transport():
            self.settings["bau_transport_m3"] = int(transport_cap_spin.value())
            # BEIDE Werte werden immer gespeichert und immer gerechnet.
            self.settings["bau_transport_rate"] = float(
                transport_rate_m3_spin.value())
            self.settings["bau_transport_trip_cost"] = (
                float(transport_rate_trip_spin.value()) * 1_000_000.0)
            self.settings["bau_freight_in_decision"] = bool(
                freight_dec_cb.isChecked())
            config.save_settings(self.settings)
            transport_ref["cap"] = float(self.settings.get("bau_transport_m3", 0) or 0)
            transport_ref["mode"] = None      # kein Entweder/Oder mehr
            transport_ref["rate"] = float(self.settings.get("bau_transport_rate", 0) or 0)
            transport_ref["trip"] = float(self.settings.get("bau_transport_trip_cost", 0) or 0)
            transport_ref["in_decision"] = bool(freight_dec_cb.isChecked())
            rebuild()

        _tr_timer.timeout.connect(_apply_transport)

        def _save_transport(*_a):
            _tr_timer.start()      # entprellt - siehe oben
        transport_cap_spin.valueChanged.connect(_save_transport)
        transport_rate_m3_spin.valueChanged.connect(_save_transport)
        transport_rate_trip_spin.valueChanged.connect(_save_transport)
        freight_dec_cb.toggled.connect(_save_transport)

        # (hier hing der Modus-Umschalter des alten Dropdowns - entfaellt,
        # seit beide Kostenarten gleichzeitig zaehlen)
        r2.addSpacing(14)
        _footer_sep = QFrame(); _footer_sep.setFrameShape(QFrame.VLine)
        _footer_sep.setStyleSheet(f"background:{theme.BORDER}; max-width:1px; min-width:1px;")
        r2.addWidget(_footer_sep)
        # Nutzer-Vorgabe: die beiden HAUPTAKTIONEN nach unten LINKS und
        # groesser - vorher standen sie ganz rechts am Fensterrand, wo man
        # sie zuletzt sucht. Der Stretch wandert dahinter.
        # "Zu Einkaufswagen hinzufuegen" ENTFAELLT - der Weg fuehrt jetzt ueber
        # Materialien-Tab -> "Einkaufsliste erstellen". Gegengeprueft, bevor der
        # Knopf verschwand: beide Wege lieferten dieselbe Appraisal auf die ISK
        # genau (Buy 40'842'249,21 / 9'552,47 m3, 15 Positionen).
        # "Bauplan speichern" sitzt jetzt OBEN in der Bedienleiste, zwischen
        # "Neu berechnen" und "Alle Materialien gekauft" (Nutzer) - und
        # BEWUSST NEUTRAL statt cyan: hervorgehoben ist dort genau EINE
        # Aktion, und das ist "Neu berechnen". Zwei leuchtende Knoepfe
        # nebeneinander heben sich gegenseitig auf.
        save_btn = self._bd_save_btn = QPushButton(_txt("Save build plan"))
        save_btn.setIcon(icons.icon("check"))
        save_btn.setMinimumHeight(34)
        save_btn.setStyleSheet(_secondary_btn_css)
        save_btn.setToolTip(_txt(
            "Save this build plan under a name – it then appears "
              "under „Current build plans“ to work through."))

        def _save_plan():
            from PySide6.QtWidgets import QInputDialog
            import time as _t
            default = f"{name} \u00d7{qty_spin.value()}"
            label, ok = QInputDialog.getText(
                dlg, _txt("Save build plan"),
                _txt("Name of the build plan:"), text=default)
            label = config.plan_name_bereinigen(label)
            if not ok or not label:
                return
            plans = self.settings.setdefault("bau_saved_plans", [])
            existing = next((p for p in plans if p.get("label") == label), None)
            overwrite_id = None
            if existing is not None:
                box = QMessageBox(dlg)
                box.setWindowTitle(_txt("Build plan already exists"))
                box.setText(_txt("A build plan named \u201e{name}\u201c already exists. "
                                 "Overwrite the existing one or create a new one next to "
                                 "it?").format(name=label))
                overwrite_btn = box.addButton(_txt("Overwrite"), QMessageBox.AcceptRole)
                new_btn = box.addButton(_txt("Create new"), QMessageBox.DestructiveRole)
                box.addButton(_txt("Cancel"), QMessageBox.RejectRole)
                box.setDefaultButton(overwrite_btn)
                box.exec()
                clicked = box.clickedButton()
                if clicked is overwrite_btn:
                    overwrite_id = existing.get("id")
                elif clicked is new_btn:
                    base = label
                    existing_labels = {p.get("label") for p in plans}
                    n = 2
                    candidate = f"{base} ({n})"
                    while candidate in existing_labels:
                        n += 1
                        candidate = f"{base} ({n})"
                    label = candidate
                else:
                    return   # Abbrechen
            # PLAN FESTNAGELN (Nutzer-Ansage Sitzung 10, Variante A:
            # "Bauplan einmal eingestellt, darf er sich nicht veraendern").
            # Gespeichert = fest. Ohne das rechnete jedes Oeffnen den Plan
            # neu: andere Runs (Bestand hat sich geaendert) UND eine andere
            # Charakter-Zuteilung (freie Slots haben sich geaendert). Weil der
            # Haekchen-Schluessel den Charakter traegt ("Stufe|Charakter|Item"),
            # verlor damit jeder gesetzte Haken seinen Anker - der Nutzer hakte
            # ab und fand am naechsten Tag wieder offene Runs vor.
            #
            # KEIN ZWEITER EINFRIER-PFAD: wir gehen ueber genau den Knopf, den
            # es schon gibt (EINE Wahrheit). Der packt den Plan-Schnappschuss,
            # und solange der liegt, wird production_plan gar nicht mehr
            # gerufen - Rezept-Struktur, Mengen, Runs und Zuteilung stehen fest.
            # Ist der Plan schon eingefroren, bleibt alles wie es ist.
            _war_schon_fest = bool((getattr(self, "_bd_frozen", None)
                                    or {}).get("plan_snapshot"))
            if not _war_schon_fest:
                # Die zwei Hinweise aus dem Einfrier-Knopf passen hier nicht
                # ("Plan noch SPEICHERN!" - wir speichern ja gerade). Der
                # Aufrufer meldet stattdessen einmal am Ende, s. unten.
                self._bd_autofreeze = True
                try:
                    frozen_btn.setChecked(True)   # -> _on_freeze_toggle(True)
                finally:
                    self._bd_autofreeze = False

            checked = []

            def collect(item):
                if item.checkState(0) == Qt.Checked:
                    t = item.data(0, Qt.UserRole)
                    if t is not None:
                        checked.append(int(t))
                for i in range(item.childCount()):
                    collect(item.child(i))
            for i in range(tw.topLevelItemCount()):
                collect(tw.topLevelItem(i))
            # Bauzeit für den Kalender FRISCH berechnen (parallele Char-Aufteilung),
            # statt auf einen evtl. veralteten Merker zu vertrauen. So bekommt der
            # Kalender immer die korrekte Runplaner-Zeit -- auch wenn der Nutzer den
            # Runplaner-Tab nicht angeschaut oder die Menge zuletzt geändert hat.
            try:
                self._fill_bauplan_schedule(plan_ref.get("plan"), res["names"],
                                            type_id, qty_spin.value(),
                                            sched_hdr, sched_sub, sched_tree,
                                            bp_tbl=bp_tab_tbl, bp_warn_lbl=sched_bp_warn)
            except Exception:
                pass
            new_entry = {"id": overwrite_id if overwrite_id is not None
                                else int(_t.time() * 1000),
                          "label": label,
                          "type_id": type_id,
                          "item_name": config.plan_name_bereinigen(name),
                          "qty": qty_spin.value(), "me": me_spin.value(),
                          "te": te_spin.value(), "checked": checked,
                          # PLAN-EIGENE EINSTELLUNGEN MITSICHERN (Nutzer,
                          # Sitzung 20): "jeder neue Bauplan sollte sich nach
                          # Standardeinstellung immer gleich oeffnen - nur
                          # gespeicherte Bauplaene speichern die
                          # Einstellungen." Vorher lagen Blacklist und die
                          # zwei Invention-Haken GLOBAL: was man in einem Plan
                          # eintrug, galt beim naechsten weiter, auch ohne zu
                          # speichern.
                          "blacklist_names": list(
                              self.settings.get("bau_blacklist_names", []) or []),
                          "blacklist_gruppen": list(
                              self.settings.get("bau_blacklist_gruppen", []) or []),
                          "buy_datacores": bool(
                              self.settings.get("bau_buy_datacores", True)),
                          "buy_decryptors": bool(
                              self.settings.get("bau_buy_decryptors", True)),
                          "reprocess_on": bool(self.settings.get("bau_reprocess_on")),
                          "unrefined_on": bool(self.settings.get("bau_unrefined_on")),
                          "bp": getattr(self, "_bd_bp", None),
                          # Verbrauchs-Map fuer die 🔒-Reservierung (Toggle in
                          # "Meine Bauplaene"): was DIESER Plan aus dem
                          # geteilten Pool nimmt. Immer mitsichern - der
                          # Schalter selbst bleibt aus, bis der Nutzer ihn
                          # setzt ("reserve" fehlt/False).
                          "reserve_map": self._plan_reserve_map(
                              (getattr(self, "_bd_plan_ref", None) or {})
                              .get("plan")),
                          # 🔒-Flag UEBERNEHMEN statt verlieren: beim
                          # Ueberschreiben ersetzt new_entry den ganzen
                          # Eintrag - ohne diese Zeile schaltete jedes
                          # Neu-Speichern die Reservierung still aus. Und
                          # Neu-Speichern ist genau das, was Alt-Plaenen
                          # fuer die Verbrauchsliste empfohlen wird.
                          # NUR beim echten Ueberschreiben (overwrite_id) -
                          # beim "Neu anlegen" neben einem gleichnamigen
                          # Plan ist `existing` der ANDERE Plan, dessen
                          # Flag hier nichts verloren hat.
                          "reserve": bool(existing.get("reserve"))
                          if (overwrite_id is not None
                              and existing is not None) else False,
                          "seconds": int(getattr(self, "_bd_last_sched_seconds", 0) or 0),
                          # Kategorie-ME/TE (Komponenten/T1-Hüllen/Fuel Blocks/Tools)
                          # mitsichern, sonst gehen individuelle Annahmen beim
                          # späteren Neu-Öffnen verloren und alles springt auf die
                          # Standardwerte zurück.
                          "me_component": comp_me_spin.value(),
                          "te_component": comp_te_spin.value(),
                          "me_t1hull": hull_me_spin.value(),
                          "te_t1hull": hull_te_spin.value(),
                          "me_fuel": fuel_me_spin.value(),
                          "te_fuel": fuel_te_spin.value(),
                          "me_tools": tools_me_spin.value(),
                          "te_tools": tools_te_spin.value(),
                          # Invention-Tab: gewählter Decryptor je Blueprint (bp_id ->
                          # Decryptor-Name), sonst geht die Wahl beim Neu-Öffnen
                          # verloren und springt zurück auf "Kein Decryptor".
                          "decryptor_map": dict(getattr(self, "_bd_decryptor_map", {})
                                                or {}),
                          # Manuelle Versuchszahl je Item (bp_id -> (manuell an/aus,
                          # Wert)) mitsichern, sonst springt beim Neu-Öffnen alles
                          # zurück auf die automatische ≥75%-Zahl.
                          "manual_attempts": {str(k): list(v) for k, v in
                                             (getattr(self, "_bd_manual_attempts", {})
                                              or {}).items()},
                          "own_bpc": bool(getattr(self, "_bd_own_bpc", False)),
                          "own_bpc_runs": int(getattr(self, "_bd_own_bpc_runs", 0) or 0),
                          "owned_bp": getattr(self, "_bd_owned_bp", None),
                          "assignments": getattr(self, "_bd_last_assignments", None) or [],
                          "waves": getattr(self, "_bd_last_waves", None) or {},
                          "stage_times": getattr(self, "_bd_last_stage_times", None) or {},
                          "invention_char": int(getattr(self, "_bd_invention_char", 0) or 0),
                          # Invention ein/ausrechnen ist PRO PLAN gespeichert -
                          # sonst würde ein später geänderter globaler Standard
                          # (Bau-Setup) rückwirkend alte gespeicherte Pläne
                          # verändern, was der Nutzer beim Speichern nicht sah.
                          "invention": bool(self.settings.get("bau_invention", False)),
                          # "Alles selbst bauen" + "Assets abziehen" (Checkbox-
                          # Zustand) mitsichern - sonst geht beim Neu-Öffnen
                          # jede Einstellung verloren, die der User bewusst
                          # gesetzt hat, und der Bauplan verhält sich anders
                          # als beim Speichern.
                          "force": bool(getattr(self, "_bd_force", False)),
                          "prefer_build_if_owned": bool(getattr(
                              self, "_bd_prefer_owned", False)),
                          "assets_abziehen": bool(asset_cb.isChecked()),
                          # BUGFIX (bei diesem Umbau gefunden): der eingefügte
                          # Bestand wurde hier NIE mitgespeichert - nur
                          # _save_frozen_to_plan schrieb ihn, und das läuft
                          # ausschließlich beim Einfrier-Klick. Wer Bestand
                          # einfügte und den Plan speicherte, verlor die
                          # Einfügung beim nächsten Öffnen. Jetzt inkl.
                          # Zeitstempel + Dauerhaft-Häkchen + "nur eingefügte".
                          "manual_stock": {str(k): int(v) for k, v in
                                           (getattr(self, "_bd_manual_stock",
                                                    None) or {}).items()},
                          "manual_stock_ts": (
                              float(getattr(self, "_bd_manual_ts", None) or 0)
                              or None),
                          "manual_stock_perm": bool(
                              getattr(self, "_bd_manual_perm", False)),
                          "manual_stock_only": bool(
                              getattr(self, "_bd_manual_only", False)),
                          # Verkaufscharakter mitspeichern: sonst rechnet der
                          # Plan beim naechsten Oeffnen mit anderen Gebuehren
                          # und der Zielpreis stimmt nicht mehr.
                          "sell_char_id": getattr(self, "_bd_sell_char", None),
                          "sell_hub": getattr(self, "_bd_sell_hub", None),
                          "sell_hub_price": getattr(
                              self, "_bd_hub_sell_price", None),
                          # Eingefrorener Kosten-Zustand ("Alle Materialien
                          # gekauft"): Preise/Adjusted/Bestand/Kostenindizes vom
                          # Einfrier-Zeitpunkt - damit der Plan auch in Wochen
                          # noch die DAMALIGEN Einkaufskosten zeigt.
                          "frozen": (dict(getattr(self, "_bd_frozen", None) or {})
                                     or None),
                          # Frachtraum/Transportkosten pro Plan (nicht nur global
                          # "zuletzt benutzt") - jeder Bauplan hat oft ein anderes
                          # Frachtvolumen/Route, daher hier mitgespeichert statt
                          # nur in den globalen Settings.
                          "transport_m3": float(self.settings.get("bau_transport_m3", 350000) or 0),
                          "transport_rate": float(self.settings.get("bau_transport_rate", 0) or 0),
                          "transport_trip_cost": float(
                              self.settings.get("bau_transport_trip_cost", 0) or 0),
                          # Zusatzkosten gehoeren ebenfalls zum Plan - sie waren
                          # vorher NUR global und galten dadurch fuer jeden
                          # anderen Bauplan mit.
                          "extra_cost": float(
                              self.settings.get("bau_extra_cost", 0) or 0),
                          # Runplaner-Häkchen ("Job ingame gestartet") - werden ab
                          # jetzt automatisch bei jedem Klick nachgeführt (s.
                          # _on_sched_check), hier nur der Stand beim Speichern.
                          "checked_runplan": list(getattr(self, "_bd_runplan_checked",
                                                          set()) or []),
                          # Zeitstempel je Haken - Grundlage fuer die
                          # mitlaufende Reservierung (s. _sched_save_now).
                          "checked_runplan_ts": {
                              str(_k): float(_v) for _k, _v in
                              (getattr(self, "_bd_runplan_ts", None) or {}).items()
                              if _k in (getattr(self, "_bd_runplan_checked", None)
                                        or set())}}
            # MULTI-BAUPLAN (1.0.9): Enden, Quellen und ME/TE je Ende gehoeren
            # zum Eintrag - sonst waere der gespeicherte Plan ein Buendel ohne
            # Inhalt (Format: mw_multi_bauplan, Kopf).
            if type_id == industry.BUENDEL_ID:
                new_entry.update(self._multi_eintrag_felder(existing))
                # QUELLEN FREIGEBEN - auch auf DIESEM Speicherweg (Nutzer-
                # Befund 26.09.2026: die drei Einzelplaene des Buendels
                # standen weiter eingefroren mit alten Einkaeufen da).
                _frei_q, _auf_q = config.buendel_quellen_freigeben(
                    plans, new_entry.get("quellen") or [])
                if _frei_q or _auf_q:
                    self._flash_tip(_txt(
                        "{n} single plan(s) unfrozen / released \u2013 build "
                        "and buy through the multi build plan from now on."
                    ).format(n=len(set(_frei_q + _auf_q))))
            if overwrite_id is not None:
                for i, p in enumerate(plans):
                    if p.get("id") == overwrite_id:
                        plans[i] = new_entry
                        break
                else:
                    plans.append(new_entry)
            else:
                plans.append(new_entry)
            config.save_settings(self.settings)
            self._bd_open_plan_id = new_entry["id"]   # ab jetzt Auto-Speicherung für Häkchen
            # RESERVIERUNG ANBIETEN (Nutzer, Sitzung 9: er hatte zwei
            # Plaene fuer dasselbe Produkt OHNE Schloss - beide sahen das
            # Material des anderen als frei an, und mitten im Bau fehlte
            # es). Frueher startete jeder neue Plan still mit offenem
            # Schloss; wer die Funktion nicht kannte, merkte es erst beim
            # Materialmangel. Gefragt wird NUR, wenn es wirklich etwas zu
            # schuetzen gibt und der Plan noch nicht reserviert.
            # GEHOERT DER PLAN SCHON ZU EINEM MULTI-BAUPLAN, wird GAR NICHT
            # gefragt (Nutzer-Frage 20.09.2026: "wie soll ich da antworten?").
            # Dort reserviert das Buendel gemeinsam; ein "Ja" hier wuerde
            # denselben Bestand ein zweites Mal blockieren - genau das, wogegen
            # die Reservierung gebaut ist. Auf der Karte ist das Schloss aus
            # demselben Grund gesperrt (Entscheid C); ohne diese Stelle haette
            # der Speicherdialog es hintenrum doch eingeschaltet.
            _multi_von9 = self._multi_gehoert_zu(plans).get(new_entry["id"]) or []
            if _multi_von9:
                new_entry["reserve"] = False
                self._flash_tip(_txt(
                    "No separate reservation: this plan belongs to the multi "
                    "build plan \u201e{name}\u201c and is reserved there."
                ).format(name=_multi_von9[0]))
            _neu_res = (not new_entry.get("reserve")
                        and bool(new_entry.get("reserve_map"))
                        and not _multi_von9)
            if _neu_res:
                from PySide6.QtWidgets import QMessageBox as _QMB9
                _rm9 = new_entry.get("reserve_map") or {}
                # Kollidiert der Plan mit anderen? Das ist das eigentliche
                # Argument fuer die Reservierung - also ausrechnen und
                # BENENNEN statt allgemein zu fragen.
                _koll9 = []
                for _p9 in plans:
                    if _p9 is new_entry or _p9.get("id") == new_entry["id"]:
                        continue
                    _o9 = _p9.get("reserve_map") or {}
                    if any(int(_t9) in _o9 for _t9 in _rm9):
                        _koll9.append(str(_p9.get("label")
                                          or _p9.get("item_name") or "?"))
                _txt9 = _txt("Reserve material for \u201e{name}\u201c?\n\n{n} material "
                             "types will be reserved. Without a reservation, OTHER build "
                             "plans see this material as free and plan with it \u2013 "
                             "then it is missing in the middle of the build.").format(
                    name=label, n=len(_rm9))
                # DEN DRUCK AUS DER FRAGE NEHMEN: sie kommt beim Speichern,
                # also bevor man weiss, ob der Plan spaeter in ein Buendel
                # wandert. Das ist nicht schlimm - die Antwort laesst sich auf
                # der Karte jederzeit aendern, und beim Buendeln wird sie
                # automatisch richtiggestellt. Wer das weiss, muss hier nicht
                # ueberlegen.
                _txt9 += "\n\n" + _txt(
                    "You can change this any time with the lock on the plan's "
                    "card. And if you later put this plan into a multi build "
                    "plan, its own reservation is released automatically \u2013 "
                    "the bundle reserves for all its plans together.")
                if _koll9:
                    _txt9 += (_txt("\n\n\u26a0 These plans need the same materials:\n"
                                   "\u2022 ")
                              + "\n\u2022 ".join(_koll9[:6])
                              + ("\n\u2022 \u2026" if len(_koll9) > 6 else ""))
                # KEIN DRITTER KNOPF (Nutzer-Idee 20.09.2026 und sein eigener
                # Einwand dagegen, dem ich folge): "Nein, ich will einen
                # Multiplan daraus machen" kaeme zum falschen Zeitpunkt - man
                # muss erst mehrere Plaene anlegen, bevor man buendeln kann.
                # Und er waere gar nicht noetig: die Antwort hier ist NICHT
                # bindend. Nimmt man den Plan spaeter in ein Buendel, hebt
                # `config.buendel_quellen_freigeben` (aus `_save_plan`) seine
                # Reservierung ohnehin auf. Das
                # stand nur nirgends - deshalb sagt es der Text jetzt, statt
                # eine dritte Wahl anzubieten.
                _ans9 = _QMB9.question(
                    self, _txt("Reserve material?"), _txt9,
                    _QMB9.Yes | _QMB9.No, _QMB9.Yes if _koll9 else _QMB9.No)
                if _ans9 == _QMB9.Yes:
                    new_entry["reserve"] = True
                    config.save_settings(self.settings)
            if hasattr(self, "_reload_saved_plans"):
                self._reload_saved_plans()
            self._flash_tip(
                _txt("Build plan \u201e{name}\u201c saved \u2713").format(name=label)
                + (" \u00b7 " + _txt("material reserved")
                   if new_entry.get("reserve") else ""))
        save_btn.clicked.connect(_save_plan)
        # In die obere Leiste, direkt hinter "Neu berechnen". Der Knopf wird
        # WEITER UNTEN im Code gebaut als die Leiste - deshalb hier per
        # insertWidget an die feste Position statt per addWidget ans Ende.
        ctrl.insertWidget(ctrl.indexOf(recalc) + 1, save_btn)
        # "Schliessen" ENTFAELLT (Nutzer: "wir koennen das Fenster ja normal
        # ueber das rote X schliessen"). Ein zweiter Schliessen-Weg direkt
        # neben den Arbeitsknoepfen war nur eine Gelegenheit, versehentlich
        # das Fenster zuzumachen.
        r2.addStretch()      # schiebt alles Folgende nach rechts
        v.addLayout(r2)
        hint = QLabel(_txt("\u201eBuild cost/unit\u201c above accounts for batch rounding/"
                           "surplus for your quantity \u2013 small quantities cost more per "
                           "unit, large ones less. The tree shows the recipe structure. "
                           "Blue = build, grey = buy; right-click \u2192 in-game market."))
        hint.setObjectName("Muted"); hint.setWordWrap(True)
        # Dauerhafter Erklaertext am Fensterboden -> in die Tooltips, wo er
        # hingehoert (Nutzer-Linie "mehr per Mouseover").
        hint.setParent(dlg)
        hint.setVisible(False)
        st_cost.setToolTip(
            (st_cost.toolTip() + "\n\n" if st_cost.toolTip() else "")
            + _txt("Accounts for batch rounding and surplus for your quantity "
                   "\u2013 small quantities cost more per unit, large ones less."))
        # NUR AUF DER KOPFZEILE (Nutzer 27.09.2026: "wenn ich mit der Maus
        # herumfahre, kommt ab und zu so ein random Infotext" - er hing an
        # der GANZEN Baumflaeche, auch an leeren Stellen; "Variante 1").
        tw.header().setToolTip(_txt("Blue = will be built, grey = will be bought. "
                                    "Right-click \u2192 in-game market."))
        # MAUSRAD NUR ZUM SCROLLEN (Nutzer 27.09.2026: "scrollt das Dropdown
        # und nicht die rechte Sidebar - Dropdown bitte nur klickbar";
        # "dasselbe in den Invention-Settings, 75 % laesst sich scrollen"):
        # im ganzen Bauplan-Fenster aendern Dropdowns, Zahlenfelder und
        # Regler ihren Wert nie per Rad - auch spaeter entstehende.
        combos_ohne_mausrad(dlg)
        self._persist_window(dlg, "bauplan",
                             {"tree": tw.header(), "order": bo_tree.header(),
                              "sched": sched_tree.header()})
        # WICHTIG danach: `_persist_window` stellt den GESPEICHERTEN
        # Header-Zustand wieder her - und der enthaelt auch die
        # Spalten-Sichtbarkeit. Ein frueher gespeicherter Stand holte die
        # ausgeblendeten Spalten "ISK/Stk" und "Kosten" zurueck (Nutzer sah
        # sie weiterhin). Deshalb hier ERNEUT verstecken, nach dem Restore.
        tw.setColumnHidden(3, True)
        tw.setColumnHidden(4, True)
        dlg.finished.connect(lambda *_: setattr(self, "_char_roles_on_change", None))
        self._show_tool_window(dlg)
