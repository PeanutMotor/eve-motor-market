"""Multi-Bauplan (1.0.9) - mehrere Endprodukte ZUSAMMEN planen.

WARUM (Nutzer, Sitzung 23): "wenn wir Bauplaene zusammen nehmen, dass wir
overall etwas guenstiger kommen, weil wir Ueberschuss mitnehmen koennen und
auch evt. die Entscheidung auf Compressed Ore und so haeufiger faellt". Und:
"am Ende moechte ich den Einzelproduktionspreis sehen von jedem Endprodukt".

WIE (Weg 1 aus CLAUDE.md): das Buendel ist ein Pseudo-Endprodukt
(industry.BUENDEL_ID) mit dem Rezept "1 Buendel = 20 A + 10 B + ...". Der
normale Bauplan-Dialog rechnet damit wie mit jedem Item - Einkaufsliste,
Runplaner, Materialien, alles laeuft ueber die Rezept-Kopie
(industry.buendel_rezepte). Dieses Modul liefert den gespeicherten
Multi-Plan, die Wege, ein Ende DAZUZUNEHMEN (Rechtsklick "Add to multi build
plan >", Knopf "+ Add end product") oder HERAUSZUNEHMEN (x je Ende), und die
Karte "Endprodukte" im Bauplan-Dialog.

EIN BAUPLAN IST EIN BUENDEL MIT N ENDEN (Nutzer-Entscheid 26.09.2026): der
fruehere eigene "Multi Buildplaner"-Dialog (Einzelplaene ankreuzen, Vorschau
einzeln vs. gebuendelt, Bearbeiten-Dialog) ist AUSGEBAUT (Aufraeumen
26.09.2026, emm222). Ein Buendel entsteht aus jedem Bauplan, indem man ein
weiteres Endprodukt anhaengt; der Vergleich "alone vs. in bundle" steht in
der Karte "Endprodukte".

ENTSCHEIDE DES NUTZERS (A/B/C, CLAUDE.md "1.0.9 - Multi Buildplaner"):
  A  Der Multi-Plan uebernimmt die Einzelplaene SO, WIE SIE GESPEICHERT SIND
     (ME/TE des Endprodukts, Decryptoren, Versuchszahlen, Invention,
     Blacklist). Aendert sich ein Einzelplan spaeter, folgt der Multi-Plan
     NICHT still - beim Oeffnen kommt der Hinweis "Plan X geaendert -
     neu uebernehmen?" (_open_multi_saved_plan).
  B  Nur gleiche Struktur: erfuellt sich von selbst - die Strukturen stehen
     GLOBAL im Bau-Setup (bau_structures), nicht je Plan. Jeder Plan baut an
     denselben Strukturen; das Buendel auch.
  C  Einzelplaene, die in einem Multi-Plan stecken, werden markiert (Karte
     in "Meine Bauplaene") - Schritt 5, noch offen.

GESPEICHERTER MULTI-PLAN (bau_saved_plans-Eintrag):
  {"type_id": industry.BUENDEL_ID, "qty": 1, "multi": True,
   "enden": [[tid, stueck], ...], "quellen": [plan_id, ...],
   "me_je_ende": {"tid": me}, "te_je_ende": {"tid": te},
   "own_bpc_je_ende": {"tid": bool}, "own_bpc_runs_je_ende": {"tid": runs},
   "quellen_stand": {"plan_id": [qty, me, te, own_bpc, own_bpc_runs]},
   "mengen_je_quelle": {"plan_id": stueck},
   ... plus die ueblichen Felder eines Bauplans (label, item_name, checked, ...)}

`quellen`, `quellen_stand` und `mengen_je_quelle` stammen aus der Zeit des
Multi-Buildplaner-Dialogs (Buendel aus Einzelplaenen). Neue Buendel (Ende
angehaengt) haben `quellen = []`; alte behalten ihre Quellen, damit
_open_multi_saved_plan weiter fragen kann, wenn sich ein Quellplan
geaendert hat (Entscheid A), und die Mitglieder-Sperre (Entscheid C) gilt.
"""
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel,
                               QMessageBox, QPushButton, QSpinBox,
                               QTableWidget, QTableWidgetItem, QVBoxLayout,
                               QHeaderView, QWidget)

from .. import config, esi, industry
from ..sprache import t
from . import icons, theme
from .mw_basis import NumericItem, isk
from .mw_helpers import eigene_kopie_lage


class MultiBauplan:
    """Mixin fuer MainWindow - alles rund um den Multi-Bauplan (Buendel)."""

    # ------------------------------------------------------------ Daten
    @staticmethod
    def _multi_ist_plan(p):
        """Ist dieser gespeicherte Eintrag ein Multi-Plan?"""
        try:
            return int((p or {}).get("type_id", 0) or 0) == industry.BUENDEL_ID
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _multi_ist_eingefroren(p):
        """Ist dieser Plan eingefroren? (Material gekauft, Plan festgenagelt)"""
        return bool((p or {}).get("frozen"))

    @staticmethod
    def _multi_gehoert_zu(plans):
        """{plan_id: [Multi-Plan-Name, ...]} - welcher Einzelplan steckt in
        welchem Multi-Bauplan? (Entscheid C, Schritt 5)

        ABGELEITET, NICHT GESPEICHERT: die Quellen stehen im Multi-Plan
        (`quellen`). Ein Merker auf dem Einzelplan waere eine ZWEITE
        Wahrheit - loescht man den Multi-Plan, bliebe die Markierung
        haengen und wuerde einen Plan sperren, der zu nichts mehr gehoert
        (Arbeitsregel 9)."""
        aus = {}
        for p in plans or []:
            try:
                if int(p.get("type_id", 0) or 0) != industry.BUENDEL_ID:
                    continue
            except (TypeError, ValueError):
                continue
            name = str(p.get("label") or "")
            for qid in (p.get("quellen") or []):
                aus.setdefault(qid, [])
                if name not in aus[qid]:
                    aus[qid].append(name)
        return aus

    @classmethod
    def _plan_gruppen(cls, plans, in_multi=None):
        """ORDNERSTRUKTUR fuer "Meine Bauplaene" (Nutzer 20.09.2026: "waere
        gut wenn die 2 Bauplaene in den Multibauplan untergeordnet werden, so
        dass man die ausklappen kann").

        Liefert ({multi_id: [Einzelplan, ...]}, {ids aller Kinder}). Ein
        Einzelplan haengt unter dem ERSTEN Multi-Plan, der ihn als Quelle
        nennt - steckt er (theoretisch) in zweien, waere er sonst zweimal auf
        der Seite. Alles ABGELEITET aus `quellen`, wie die Markierung selbst:
        kein Merker am Einzelplan, der nach dem Loeschen des Buendels haengen
        bliebe."""
        in_multi = in_multi if in_multi is not None else cls._multi_gehoert_zu(plans)
        kinder, kind_ids = {}, set()
        for p in plans or []:
            pid = p.get("id")
            if pid is None or not (in_multi.get(pid) or []):
                continue
            eltern = next((m for m in plans
                           if cls._multi_ist_plan(m)
                           and pid in (m.get("quellen") or [])), None)
            if eltern is None or eltern.get("id") == pid:
                continue
            kinder.setdefault(eltern["id"], []).append(p)
            kind_ids.add(pid)
        return kinder, kind_ids

    def _plan_gruppe_offen(self, pid):
        """Ist dieser Multi-Bauplan aufgeklappt? Standard: OFFEN (Nutzer
        26.09.2026: "Multiplans standard ausgeklappt, es sei denn man
        schliesst das Dropdown") - gemerkt wird, was ZUGEKLAPPT wurde.
        Ersetzt den Entscheid vom 20.09.2026 (Standard zu)."""
        try:
            return int(pid) not in {int(x) for x in
                                    (self.settings.get("bau_multi_zu") or [])}
        except (TypeError, ValueError):
            return True

    def _plan_gruppe_toggle(self, pid, offen):
        """Auf-/Zuklappen und den Zustand merken (ueberlebt den Neustart)."""
        box = (getattr(self, "_plan_gruppe_box", None) or {}).get(pid)
        if box is not None:
            box.setVisible(bool(offen))
        btn = (getattr(self, "_plan_multi_pfeil", None) or {}).get(pid)
        if btn is not None:
            btn.setIcon(icons.icon("chevron" if offen else "arrow_right"))
        try:
            aus = [int(x) for x in (self.settings.get("bau_multi_zu") or [])]
        except (TypeError, ValueError):
            aus = []
        aus = [x for x in aus if x != int(pid)]
        if not offen:
            aus.append(int(pid))
        self.settings["bau_multi_zu"] = aus
        config.save_settings(self.settings)

    @staticmethod
    def _multi_quellen_stand(p):
        """Was vom Einzelplan in den Multi-Plan einfliesst - als Vergleichs-
        stand fuer den Hinweis "Plan geaendert" (Entscheid A).

        "Eigene BPC" gehoert dazu (Schritt 4): eine eigene erforschte Kopie
        (ME 10) statt der Invention-ME (2 %) aendert den Materialbedarf
        spuerbar - schaltet der Nutzer das im Einzelplan um, muss der
        Multi-Plan fragen, statt still mit der alten Annahme zu rechnen."""
        return [int(p.get("qty", 0) or 0), int(p.get("me", 0) or 0),
                int(p.get("te", 0) or 0), bool(p.get("own_bpc", False)),
                int(p.get("own_bpc_runs", 0) or 0)]

    def _multi_plan_aus_quellen(self, quellen, mengen=None, label=None):
        """Baut den Multi-Plan-Eintrag aus Einzelplaenen.

        quellen: Liste der Einzelplan-Eintraege; mengen: {plan_id: stueck}
        (fehlt -> die Menge des Einzelplans). Doppelte Endprodukte werden
        addiert (zwei Viator-Plaene = ein Ende mit der Summe; ME/TE nimmt
        den ersten). Liefert das dict OHNE id (die vergibt der Speicherer).
        """
        enden = {}
        mengen_je = {}
        me_je, te_je = {}, {}
        obpc_je, obpc_runs_je = {}, {}
        dec, man = {}, {}
        bl_n, bl_g = [], []
        inv = False
        stand = {}
        for p in quellen:
            tid = int(p["type_id"])
            q = int((mengen or {}).get(p["id"], p.get("qty", 0)) or 0)
            if q <= 0:
                continue
            enden[tid] = enden.get(tid, 0) + q
            mengen_je[str(p["id"])] = q
            if tid not in me_je:
                me_je[tid] = int(p.get("me", 0) or 0)
                te_je[tid] = int(p.get("te", 0) or 0)
                # SCHRITT 4: "Eigene BPC" ist eine Aussage ueber DIESES
                # Endprodukt (eigene erforschte Kopie statt Invention) und
                # gehoert deshalb je Ende in den Multi-Plan - frueher war es
                # EIN Schalter fuer den ganzen Dialog.
                obpc_je[tid] = bool(p.get("own_bpc", False))
                obpc_runs_je[tid] = int(p.get("own_bpc_runs", 0) or 0)
            for k, v in (p.get("decryptor_map") or {}).items():
                dec.setdefault(str(k), v)
            for k, v in (p.get("manual_attempts") or {}).items():
                man.setdefault(str(k), list(v))
            for n in (p.get("blacklist_names") or []):
                if n not in bl_n:
                    bl_n.append(n)
            for g in (p.get("blacklist_gruppen") or []):
                if g not in bl_g:
                    bl_g.append(g)
            inv = inv or bool(p.get("invention", False))
            stand[str(p["id"])] = self._multi_quellen_stand(p)
        if not enden:
            return None
        if not label:
            label = self._multi_standard_name(quellen)
        return {"label": label, "type_id": industry.BUENDEL_ID,
                "item_name": label, "qty": 1, "multi": True,
                "enden": [[tid, q] for tid, q in sorted(enden.items())],
                "quellen": [p["id"] for p in quellen],
                "quellen_stand": stand,
                "mengen_je_quelle": mengen_je,
                "me_je_ende": {str(k): v for k, v in me_je.items()},
                "te_je_ende": {str(k): v for k, v in te_je.items()},
                "own_bpc_je_ende": {str(k): bool(v) for k, v in obpc_je.items()},
                "own_bpc_runs_je_ende": {str(k): int(v)
                                         for k, v in obpc_runs_je.items()},
                "me": 0, "te": 0, "checked": [],
                "decryptor_map": dec, "manual_attempts": man,
                "blacklist_names": bl_n, "blacklist_gruppen": bl_g,
                "invention": inv}

    @staticmethod
    def _multi_standard_name(quellen):
        """"Multi: Viator + Ishtar" - aus den Item-Namen der Einzelplaene."""
        namen = []
        for p in quellen:
            n = str(p.get("item_name") or p.get("label") or "").strip()
            if n and n not in namen:
                namen.append(n)
        kurz = " + ".join(namen[:3]) + (" + …" if len(namen) > 3 else "")
        return t("Multi: {names}").format(names=kurz)

    @staticmethod
    def _multi_buendel_verkauf(pm, enden):
        """Verkaufswert EINES Buendels = Summe Preis x Menge ueber die Enden.
        Ein Ende ohne Preis zaehlt 0 (sichtbar in der Enden-Karte)."""
        s = 0.0
        for tid, q in enden or []:
            p = pm.get(int(tid))
            if p and p > 0:
                s += float(p) * int(q)
        return s

    def _multi_opts_je_ende(self, opts, recipes):
        """SCHRITT 4: "Eigene BPC" je Endprodukt in die opts uebersetzen.

        WARUM ES DAS BRAUCHT (Nutzer, 19.09.2026: "aber jeder Plan hat doch
        seine eigene ME/TE wenn sie T2 sind"): eine erfundene BPC hat eine
        FESTE ME (2 % + Decryptor), eine eigene erforschte Kopie dagegen bis
        zu 10 %. Der Dialog hatte dafuer EINEN Schalter ("Eigene BPC") und
        EIN ME-Feld - fuer EIN Endprodukt. Im Buendel zeigt `type_id` auf das
        Buendel, der Schalter landete auf dessen Pseudo-Blaupause (-2) und
        verpuffte: JEDES Ende rechnete mit der Invention-Annahme, auch das
        mit der eigenen ME-10-Kopie. Das ist kein Schoenheitsfehler - der
        Materialbedarf lag damit daneben.

        DIE RECHNUNG KANN DAS LAENGST: `inv_manual_override` ist je
        BLAUPAUSE (bp_id), `me_map`/`me_map_reaction` je ITEM. Es fehlte nur
        die Uebersetzung. `_invention_me_pct` gibt fuer ein Ende mit
        Override None zurueck -> `_me_of` nimmt die me_map, die
        `_bau_me_maps` aus `_bd_me_je_ende` gefuellt hat.

        Ohne Buendel passiert hier NICHTS (leere Mengen) - der Einzelplan
        behaelt sein bisheriges Verhalten unveraendert."""
        enden = self._bd_enden(industry.BUENDEL_ID, recipes) \
            if getattr(self, "_bd_buendel_enden", None) else set()
        if not enden:
            return opts
        obpc = getattr(self, "_bd_own_bpc_je_ende", None) or {}
        p2b = getattr(recipes, "product_to_bp", None) or {}
        ov = dict(opts.get("inv_manual_override") or {})
        for tid in enden:
            bp = p2b.get(int(tid))
            if not bp:
                continue
            if obpc.get(int(tid)):
                ov[bp[0]] = True
            else:
                # AUSDRUECKLICH WIEDER WEG, nicht nur "nicht setzen": der
                # Nutzer kann den Haken im offenen Plan auch ZURUECK-
                # nehmen, und `_bd_opts` ueberlebt den rebuild.
                ov.pop(bp[0], None)
        opts["inv_manual_override"] = ov
        # INVENTION IST IM BUENDEL IMMER AN, sobald ein Ende erfindbar ist
        # (Nutzer 26.09.2026: "Decryptorwahl ueberschreibt immer haendisch
        # eingegebene ME/TE, es sei denn man waehlt eigene BPC"). Der globale
        # Schalter "Include invention" gehoert zum Einzelplan; ein Buendel,
        # das aus einem Plan mit Schalter AUS entstand, rechnete seine
        # T2-Enden sonst mit getippter ME und ohne Datacores - und der
        # Invention-Tab fehlte (sein Screenshot: Sacrilege + Prowler, ME/TE
        # frei tippbar, kein Tab). "Eigene BPC" je Ende bleibt der einzige
        # Weg, die Invention fuer EIN Ende auszuschalten (Override oben).
        if self._multi_enden_erfindbar(recipes, enden):
            opts["invention"] = True
        return opts

    @staticmethod
    def _multi_enden_erfindbar(recipes, enden):
        """{tid} der Enden, die ueber Invention entstehen (T2/T3): ihre
        Blaupause steht in invention_for_bpc. Leer bei T1/Reaktionen."""
        p2b = getattr(recipes, "product_to_bp", None) or {}
        inv = getattr(recipes, "invention_for_bpc", None) or {}
        aus = set()
        for tid in enden or ():
            try:
                bp = p2b.get(int(tid))
            except (TypeError, ValueError):
                continue
            if bp and bp[0] in inv:
                aus.add(int(tid))
        return aus

    def _multi_me_te_auffrischen(self, opts=None):
        """ME/TE je Ende in die opts nachziehen, wenn die Karte sie aendert.

        WARUM NOETIG: `me_map` und `te_by_tid` entstehen NUR im Rechenlauf
        beim Oeffnen (`open_build_detail`), nicht in `rebuild()`. Der
        Einzelplan kennt dasselbe Problem und loest es genauso - sein
        `_on_me_te_finished` schreibt den neuen Wert direkt in
        `opts["me_map"][type_id]` zurueck. Ohne das hier blieb die im
        Buendel eingetippte ME wirkungslos, bis man den Plan neu oeffnet
        (in der b-Suite GEMESSEN: B rechnete mit 1'000 statt 900 Stueck).

        KEINE ZWEITE FORMEL: die Rig-/EC-Anteile stehen schon in
        `rig_me_map`/`ec_me_map` (aus `_bau_me_maps`), und die Verrechnung
        macht `industry.me_invented_pct` - dieselbe drei-Faktoren-Formel,
        die auch `_bau_me_maps` benutzt. Die TE laeuft ueber genau die zwei
        Aufrufe des Rechenlaufs (`_bau_struct_fuer_item` +
        `_bau_category_te_factor`), damit dort keine dritte Ableitung
        entsteht (Arbeitsregel 9)."""
        opts = self._bd_opts if opts is None else opts
        if opts is None:
            return
        recipes = getattr(self, "_bd_recipes", None)
        enden = self._bd_enden(industry.BUENDEL_ID, recipes) \
            if getattr(self, "_bd_buendel_enden", None) else set()
        if not enden:
            return
        me_je = getattr(self, "_bd_me_je_ende", None) or {}
        rig = opts.get("rig_me_map") or {}
        ec = opts.get("ec_me_map") or {}
        mm = dict(opts.get("me_map") or {})
        for tid in enden:
            basis = me_je.get(int(tid))
            if basis is None:
                continue
            mm[int(tid)] = industry.me_invented_pct(
                basis, rig.get(int(tid), 0) or 0, ec.get(int(tid), 0) or 0)
        opts["me_map"] = mm
        _tb = dict(opts.get("te_by_tid") or {})
        if _tb:
            try:
                _sm = industry.reaction_stage_map(recipes) if recipes else {}
            except Exception:
                _sm = {}
            _rp = getattr(recipes, "reaction_products", None) or set()
            _gr = getattr(self, "_bd_groups", None) or {}
            for tid in enden:
                _s = self._bau_struct_fuer_item(int(tid), _rp, _sm,
                                                industry.BUENDEL_ID)
                _tb[int(tid)] = self._bau_category_te_factor(
                    int(tid), _gr, _rp, industry.BUENDEL_ID,
                    mfg_struct=_s, react_struct=_s, recipes=recipes, opts=opts)
            opts["te_by_tid"] = _tb

    def _multi_bp_je_ende(self, plan=None):
        """SCHRITT 4b: Blaupausen-Lage JE ENDPRODUKT -
        {tid: {"copies", "runs", "bpo"}}.

        WAS VORHER FEHLTE: `_bd_bp["end"]` haelt EINEN Satz Zahlen fuer die
        Stufe "Endprodukt" - Kopien, Runs je Kopie, BPO ja/nein. Beim
        Einzelplan ist das genau richtig, beim Buendel beschreibt es
        mehrere verschiedene Produkte mit EINER Zahl. Der Runplaner nahm
        sie dann fuer JEDES Ende: eine 10er-Kopie von A wurde auch B
        unterstellt, und die Kopienzahl von A deckelte B mit.

        DIESELBEN ZWEI RECHNUNGEN wie beim Einzelplan, nur je Ende:
          * "Eigene BPC": `mw_helpers.eigene_kopie_lage` - getippte
            "Runs/BPC", sonst die kleinste eigene Kopie aus dem
            Blaupausen-Cache, sonst KEIN Eintrag (Nutzer-Befund 51 Tage,
            21.09.2026 - die alte Annahme "alle Runs sind EINE Kopie"
            zwang den ganzen Plan auf einen einzigen Slot);
          * erfunden: Runs je BPC aus `invention_outcome` mit dem Decryptor
            DIESER Blaupause (`industry.decryptor_fuer_bp` - dieselbe
            Quelle, aus der auch die ME kommt), Kopien = ceil(Runs / Runs);
          * sonst (T1/BPO): kein Eintrag, also unbegrenzt wie bisher.

        `plan` liefert die tatsaechlichen Runs je Ende (`build_runs`);
        fehlt er, wird der offene Plan genommen."""
        rec = getattr(self, "_bd_recipes", None)
        enden = self._bd_enden(industry.BUENDEL_ID, rec) \
            if getattr(self, "_bd_buendel_enden", None) else set()
        if not enden or rec is None:
            return {}
        if plan is None:
            plan = (getattr(self, "_bd_plan_ref", None) or {}).get("plan") or {}
        runs_von = (plan or {}).get("build_runs") or {}
        opts = getattr(self, "_bd_opts", None) or {}
        obpc = getattr(self, "_bd_own_bpc_je_ende", None) or {}
        obpc_runs = getattr(self, "_bd_own_bpc_runs_je_ende", None) or {}
        p2b = getattr(rec, "product_to_bp", None) or {}
        inv_map = getattr(rec, "invention_for_bpc", None) or {}
        # DER BLAUPAUSEN-CACHE WEISS ES SCHON (Befund 21.09.2026): aus ihm
        # holt sich `_resolve_per_item_runs_cap` laengst den Runs-Deckel und
        # `_resolve_per_item_bp_cap` die Stueckzahl. Dieselbe Quelle hier,
        # statt danebenzuraten - sonst stehen zwei Ableitungen derselben
        # Tatsache im Code (Regel 9) und die geratene gewinnt.
        _cache = getattr(self, "_bd_owned_bp_cache", None) or []
        _esi_runs = self._bpc_runs_by_tid(_cache, runs_von, p2b) if _cache else {}
        _esi_kop = self._bp_copies_by_tid(_cache, runs_von, p2b) if _cache else {}
        aus = {}
        for tid in sorted(enden):
            tid = int(tid)
            bp = p2b.get(tid)
            if not bp:
                continue
            noetig = max(1, int(runs_von.get(tid, 0) or 0))
            if obpc.get(tid):
                _lage = eigene_kopie_lage(noetig, obpc_runs.get(tid),
                                          _esi_runs.get(tid), _esi_kop.get(tid))
                if _lage is None:
                    # "EIGENE BPC" OHNE BEKANNTE GROESSE (Nutzer 26.09.2026,
                    # Einherji II: "da wird angezeigt, ich haette unendlich
                    # T2 Copys? das geht nicht"): das Feld "Runs/BPC" zeigt
                    # in dem Fall seine 1 - dann gilt auch die 1, und sie
                    # wird gespeichert, damit Feld und Rechnung dieselbe
                    # Zahl tragen. Vorher hiess "unbekannt" hier
                    # "unbegrenzt" - fuer eine KOPIE ist das nie wahr.
                    self._bd_own_bpc_runs_je_ende = dict(obpc_runs)
                    self._bd_own_bpc_runs_je_ende[tid] = 1
                    obpc_runs = self._bd_own_bpc_runs_je_ende
                    _lage = eigene_kopie_lage(noetig, 1, None, _esi_kop.get(tid))
                aus[tid] = {"copies": _lage["copies"], "runs": _lage["runs"],
                            "bpo": False, "runs_known": True}
                continue
            _inv = inv_map.get(bp[0])
            if not _inv or not opts.get("invention", True):
                continue              # T1/BPO: unbegrenzt, wie bisher
            _t1, _br, _prob, _dcs = _inv
            try:
                _out = industry.invention_outcome(
                    _br, _prob, industry.decryptor_fuer_bp(bp[0], opts))
            except Exception as _ie:
                self._log_exception("Multi-Bauplan: Invention je Ende", str(_ie))
                continue
            je_bpc = max(1, int(_out.get("runs", 1) or 1))
            aus[tid] = {"copies": -(-noetig // je_bpc),   # ceil
                        "runs": je_bpc, "bpo": False, "runs_known": True}
        return aus

    def _multi_enden_ohne_decryptor(self):
        """[tid] - T2-Enden ohne "Eigene BPC", deren Decryptor noch nie
        gewaehlt wurde (steht auf "No decryptor", nicht in
        `_bd_dec_bestaetigt`). Nutzer 26.09.2026: "eine Warnung, wenn man noch
        keinen Decryptor gewaehlt hat oder keine eigene BPC ME/TE eingegeben -
        das ist wichtig beim Bauen von T2". Dieselbe Bedingung wie die
        Warnzeile der Invention-Karte (dort mit gesperrter Combo = Own BPC)."""
        from ..config import KEIN_DECRYPTOR
        rec = getattr(self, "_bd_recipes", None)
        enden = self._bd_enden(industry.BUENDEL_ID, rec) \
            if getattr(self, "_bd_buendel_enden", None) else set()
        if not enden or rec is None:
            return []
        p2b = getattr(rec, "product_to_bp", None) or {}
        obpc = getattr(self, "_bd_own_bpc_je_ende", None) or {}
        dmap = getattr(self, "_bd_decryptor_map", None) or {}
        ok = getattr(self, "_bd_dec_bestaetigt", None) or set()
        aus = []
        for tid in sorted(self._multi_enden_erfindbar(rec, enden)):
            if obpc.get(int(tid)):
                continue
            bp = (p2b.get(int(tid)) or (None,))[0]
            if bp is None:
                continue
            if dmap.get(bp, KEIN_DECRYPTOR) == KEIN_DECRYPTOR and int(bp) not in ok:
                aus.append(int(tid))
        return aus

    def _multi_unklare_enden(self, plan=None):
        """[(tid, eigene Kopien)] - T2-Enden ohne Haken "Eigene BPC", fuer die
        der Blaupausen-Cache eigene Kopien kennt (Nutzer 26.09.2026). Ohne
        Cache (noch nicht geladen) ist nichts unklar - dann fehlt schlicht
        die Auskunft, und Nichtwissen erzeugt keine Warnung."""
        rec = getattr(self, "_bd_recipes", None)
        enden = self._bd_enden(industry.BUENDEL_ID, rec) \
            if getattr(self, "_bd_buendel_enden", None) else set()
        _cache = getattr(self, "_bd_owned_bp_cache", None) or []
        if not enden or rec is None or not _cache:
            return []
        if plan is None:
            plan = (getattr(self, "_bd_plan_ref", None) or {}).get("plan") or {}
        runs_von = (plan or {}).get("build_runs") or {}
        p2b = getattr(rec, "product_to_bp", None) or {}
        obpc = getattr(self, "_bd_own_bpc_je_ende", None) or {}
        try:
            _kop = self._bp_copies_by_tid(_cache, runs_von, p2b)
        except Exception:
            return []
        aus = []
        for tid in sorted(self._multi_enden_erfindbar(rec, enden)):
            if obpc.get(int(tid)):
                continue
            n = int(_kop.get(int(tid)) or 0)
            if n > 0:
                aus.append((int(tid), n))
        return aus

    def _multi_runs_cap_je_ende(self, out=None):
        """{tid: max Runs je Job} je Endprodukt - Runs der EINEN Kopie.

        Eine BPC ist irgendwann aufgebraucht: wer 40 Viator mit 10er-Kopien
        baut, kann keinen 40er-Job fahren (Nutzer-Befund Einherji II, in
        derselben Fehlerklasse). `_resolve_per_item_runs_cap` kannte diese
        Grenze nur fuer EIN Endprodukt; hier kommt sie je Ende dazu - fuer
        eigene UND fuer erfundene Kopien. Kleinster Wert gewinnt (Regel 3)."""
        out = dict(out or {})
        for tid, d in (self._multi_bp_je_ende() or {}).items():
            r = int(d.get("runs", 0) or 0)
            if r >= 1:
                out[int(tid)] = min(out.get(int(tid), r), r)
        return out

    def _multi_bp_cap_je_ende(self, out=None):
        """{tid: Kopien} je Endprodukt fuer schedule_build's per_item_cap -
        der Pro-Item-Wert schlaegt dort die pauschale Stufen-Zahl."""
        out = dict(out or {})
        for tid, d in (self._multi_bp_je_ende() or {}).items():
            c = int(d.get("copies", 0) or 0)
            if c >= 1 and not d.get("bpo"):
                out[int(tid)] = c
        return out

    # ------------------------------------------------------------ Oeffnen
    def _multi_plan_oeffnen(self, eintrag, plan_id=None):
        """Den grossen Bauplan-Dialog mit dem Buendel oeffnen.

        `eintrag` ist ein Multi-Plan-dict (gespeichert oder frisch gebaut);
        `plan_id` bindet den Dialog an den gespeicherten Eintrag (Speichern
        ueberschreibt ihn dann, Runplaner-Haken landen dort)."""
        enden = []
        for a, b in (eintrag.get("enden") or []):
            try:
                if int(b) > 0:
                    enden.append((int(a), int(b)))
            except (TypeError, ValueError):
                continue
        if not enden:
            QMessageBox.information(self, t("Multi build plan"),
                                    t("This multi build plan has no end products."))
            return
        # ERST der gespeicherte Zustand (wie _open_saved_plan), DANN das
        # Buendel: open_build_detail verbraucht `_bd_buendel_pending` nach
        # seinem Zuruecksetz-Zweig - so ueberlebt es den Neustart der
        # Dialog-Felder, und ein normaler Plan danach findet es geleert vor.
        if plan_id is not None:
            self._open_saved_plan_zustand(eintrag, plan_id)
        else:
            self._bd_bp_pending = None
            self._bd_frozen_pending = None
            self._bd_manual_pending = None
            self._bd_manual_meta_pending = None
            self._bd_bp_type = None
            self._bd_open_plan_id = None
            for _pk, _sk in (("blacklist_names", "bau_blacklist_names"),
                             ("blacklist_gruppen", "bau_blacklist_gruppen")):
                if _pk in eintrag:
                    self.settings[_sk] = list(eintrag[_pk] or [])
            self.settings["bau_invention"] = bool(eintrag.get("invention", False))
            self._bd_decryptor_map = {}
            for k, v in (eintrag.get("decryptor_map") or {}).items():
                try:
                    self._bd_decryptor_map[int(k)] = v
                except (TypeError, ValueError):
                    continue
            # Gespeicherte Wahl gilt als bewusst getroffen (keine Warnung).
            self._bd_dec_bestaetigt = set(self._bd_decryptor_map)
            self._bd_manual_attempts = {}
            for k, v in (eintrag.get("manual_attempts") or {}).items():
                try:
                    self._bd_manual_attempts[int(k)] = (bool(v[0]), int(v[1]))
                except (TypeError, ValueError, IndexError):
                    continue
        self._bd_buendel_pending = {
            "enden": enden,
            "quellen": list(eintrag.get("quellen") or []),
            "me": {int(k): float(v) for k, v in (eintrag.get("me_je_ende") or {}).items()},
            "te": {int(k): float(v) for k, v in (eintrag.get("te_je_ende") or {}).items()},
            "own_bpc": {int(k): bool(v) for k, v in
                        (eintrag.get("own_bpc_je_ende") or {}).items()},
            "own_bpc_runs": {int(k): int(v) for k, v in
                             (eintrag.get("own_bpc_runs_je_ende") or {}).items()},
            "label": str(eintrag.get("label") or t("Multi build plan")),
        }
        self._bd_loading_saved = plan_id is not None
        self.open_build_detail(industry.BUENDEL_ID,
                               str(eintrag.get("label") or t("Multi build plan")),
                               fresh=plan_id is None)

    # ------------------------------------------------------------ Ende dazu
    # NUTZER-ENTSCHEID 26.09.2026 ("dann koennte man direkt aus einem Bauplan
    # ein Multibauplan erstellen ... per Rechtsklick in Multiplans umwandeln
    # und immer weitere hinzufuegen"): ein Bauplan ist ein Buendel mit N
    # Enden. Ein Einzelplan wird beim ersten Anhaengen zum Buendel (sein
    # bisheriges Endprodukt bleibt als erstes Ende, mit Menge, ME/TE und
    # "Eigene BPC"); ein Buendel waechst. EINGEFRORENE ODER RESERVIERTE
    # PLAENE SIND AUSGESCHLOSSEN - auch aus der Auflistung (Nutzer: "sogar
    # aus der Anzeige"): eingefroren heisst gekauft, ein neues Ende wuerde
    # Schnappschuss und Reservierung entwerten.
    @staticmethod
    def _multi_ende_anhaengbar(p):
        """Darf dieser gespeicherte Plan ein weiteres Ende bekommen?

        EINGEFROREN IST KEIN HINDERNIS (zweites Mal, 26.09.2026 - Nutzer:
        "ich habe Bauplaene, kann aber keinen Multiplan erstellen"):
        Speichern friert JEDEN Plan ein (Sitzung 10), ein Filter auf
        "eingefroren" schliesst also alle gespeicherten Plaene aus - genau
        die Falle vom 20.09.2026. Beim Anhaengen wird der Plan AUFGETAUT
        (der Schnappschuss passt nicht mehr zur neuen Materialliste) und
        der Nutzer erfaehrt es. Ausgeschlossen bleiben RESERVIERTE (das
        Material ist gekauft und gebunden) und abgeschlossene Plaene."""
        # SEIT 27.09.2026 JEDER gespeicherte Plan (Nutzer: "gespeicherte,
        # gefrorene, reservierte Plaene auch nehmen, dafuer eine Kopie davon
        # machen ... somit bleibt der alte Plan bestehen"): ist er eingefroren,
        # reserviert oder abgeschlossen, geht das Ende in eine KOPIE
        # (_multi_braucht_kopie / _multi_kopie_von) - der Plan selbst bleibt.
        if not p:
            return False
        try:
            return int(p.get("type_id", 0) or 0) != 0
        except (TypeError, ValueError):
            return False

    @staticmethod
    def _multi_braucht_kopie(p):
        """Eingefroren, reserviert oder abgeschlossen -> NICHT veraendern,
        sondern eine Kopie als neuen Multiplan anlegen (Nutzer 27.09.2026:
        "gefrorene und gespeicherte Plaene sind dazu da, dass ich im Profit-
        Overview immer weiss, wie viel Profit ich mache ... veraendere ich
        das, verliere ich die Uebersicht"; "alles, was in Meine Bauplaene
        steht, soll zaehlen" - also zaehlen Original UND Kopie)."""
        return bool(p) and bool(p.get("frozen") or p.get("reserve")
                                or p.get("done_manual"))

    def _multi_kopie_von(self, p):
        """Kopie eines Plans als NEUER Plan: neue ID (= neuer Zeitpunkt, ab
        dem ESI-Jobs zaehlen - die Plan-ID ist der ms-Zeitstempel), nicht
        eingefroren, nicht reserviert, nicht abgeschlossen, keine Haken,
        keine eingefuegten Bestaende, keine Quellplaene (die gehoeren weiter
        zum Original). Name "<alt> (copy)". Aendert `p` nicht."""
        import copy as _cp
        import time as _tm
        e = _cp.deepcopy(dict(p or {}))
        _ids = {x.get("id") for x in (self.settings.get("bau_saved_plans", []) or [])}
        nid = int(_tm.time() * 1000)
        while nid in _ids:
            nid += 1
        e["id"] = nid
        for _k, _v in (("frozen", None), ("reserve", False), ("reserve_map", {}),
                       ("done_manual", False), ("checked", []),
                       ("checked_runplan", []), ("checked_runplan_ts", None),
                       ("manual_stock", {}), ("manual_stock_ts", None),
                       ("quellen", []), ("quellen_stand", {}),
                       ("mengen_je_quelle", {})):
            if _k in e:
                e[_k] = _cp.deepcopy(_v)
        _alt = str(e.get("label") or e.get("item_name") or "")
        e["label"] = t("{name} (copy)").format(name=_alt)
        return e

    def _multi_ende_anhaengen(self, eintrag, tid, qty, me=None, te=None,
                              own_bpc=False, own_bpc_runs=0):
        """NEUER Eintrag = `eintrag` (Einzelplan ODER Buendel) + Ende tid x qty.
        Aendert `eintrag` nicht. Gleiches Ende noch einmal -> Mengen addiert
        (wie _multi_plan_aus_quellen). ME/TE des neuen Endes: Vorgabe aus
        den Einstellungen (bau_me/bau_te), wie bei einem neuen Bauplan."""
        e = dict(eintrag or {})
        tid = int(tid)
        qty = max(1, int(qty or 1))
        # Der Schnappschuss gehoert zur ALTEN Materialliste - auftauen.
        e["frozen"] = None
        if not self._multi_ist_plan(e):
            alt_tid = int(e.get("type_id") or 0)
            alt_q = max(1, int(e.get("qty") or 1))
            e.update({
                "type_id": industry.BUENDEL_ID, "qty": 1, "multi": True,
                "enden": [[alt_tid, alt_q]] if alt_tid > 0 else [],
                "quellen": [], "quellen_stand": {}, "mengen_je_quelle": {},
                "me_je_ende": {str(alt_tid): int(e.get("me", 0) or 0)} if alt_tid > 0 else {},
                "te_je_ende": {str(alt_tid): int(e.get("te", 0) or 0)} if alt_tid > 0 else {},
                "own_bpc_je_ende": ({str(alt_tid): bool(e.get("own_bpc", False))}
                                    if alt_tid > 0 else {}),
                "own_bpc_runs_je_ende": ({str(alt_tid): int(e.get("own_bpc_runs", 0) or 0)}
                                         if alt_tid > 0 else {}),
                "me": 0, "te": 0})
            if not e.get("label"):
                e["label"] = str(e.get("item_name") or "")
        enden = {}
        for a, b in (e.get("enden") or []):
            enden[int(a)] = enden.get(int(a), 0) + int(b)
        enden[tid] = enden.get(tid, 0) + qty
        e["enden"] = [[a, b] for a, b in sorted(enden.items())]
        for _k, _v in (("me_je_ende", me if me is not None
                        else int(self.settings.get("bau_me", 10) or 0)),
                       ("te_je_ende", te if te is not None
                        else int(self.settings.get("bau_te", 0) or 0)),
                       ("own_bpc_je_ende", bool(own_bpc)),
                       ("own_bpc_runs_je_ende", int(own_bpc_runs or 0))):
            _d = dict(e.get(_k) or {})
            _d.setdefault(str(tid), _v)
            e[_k] = _d
        return e

    def _multi_ende_zu_plan(self, plan_id, tid, name, qty=None, vorgabe=1):
        """Rechtsklick "Add to multi build plan > <Plan>": EIN Ende anhaengen.
        Ohne `qty` fragt der Mengen-Dialog, VORBEFUELLT mit `vorgabe` (aus
        dem Scanner: die Stueckzahl, mit der er gerechnet hat)."""
        self._multi_enden_zu_plan(
            plan_id, [{"tid": int(tid), "name": str(name),
                       "qty": qty, "vorgabe": vorgabe}])

    def _multi_mengen_dialog(self, items, titel):
        """MENGEN-DIALOG, VORBEFUELLT (Nutzer 26.09.2026, Bedienidee 2: "den
        Mengen-Dialog aus dem Scanner vorbefuellen"). items = [{tid, name,
        vorgabe}] - EINE Zeile je Item mit eigener Menge, damit eine
        Mehrfachauswahl (Bedienidee 1) nicht N Dialoge nacheinander braucht.
        Gibt [{tid, name, qty}] zurueck oder None (Abbrechen)."""
        from PySide6.QtWidgets import QDialog, QGridLayout
        dlg = QDialog(self._tool_parent()); dlg.setWindowTitle(titel)
        dlg.setMinimumWidth(420)
        v = QVBoxLayout(dlg); v.setContentsMargins(18, 16, 18, 16); v.setSpacing(10)
        v.addWidget(QLabel(t("How many of each?")))
        g = QGridLayout(); g.setHorizontalSpacing(12); g.setVerticalSpacing(6)
        spins = []
        for _i, it in enumerate(items):
            g.addWidget(QLabel(str(it["name"])), _i, 0)
            sp = QSpinBox(); sp.setRange(1, 100000000)
            sp.setGroupSeparatorShown(True); sp.setMinimumWidth(120)
            sp.setValue(max(1, int(it.get("vorgabe") or 1)))
            g.addWidget(sp, _i, 1)
            spins.append(sp)
        v.addLayout(g)
        row = QHBoxLayout(); row.addStretch()
        cancel = QPushButton(t("Cancel")); cancel.clicked.connect(dlg.reject)
        ok = QPushButton(" " + t("Add")); ok.setObjectName("Primary")
        ok.setIcon(icons.icon("plus")); ok.setDefault(True)
        ok.clicked.connect(dlg.accept)
        row.addWidget(cancel); row.addWidget(ok); v.addLayout(row)
        if spins:
            spins[0].setFocus(); spins[0].selectAll()
        self._multi_mengen_dlg = dlg            # b-Suite
        self._multi_mengen_spins = spins        # b-Suite
        if dlg.exec() != QDialog.Accepted:
            return None
        return [{"tid": int(it["tid"]), "name": str(it["name"]),
                 "qty": int(sp.value())} for it, sp in zip(items, spins)]

    def _multi_enden_zu_plan(self, plan_id, items):
        """EIN ODER MEHRERE Enden an einen gespeicherten Plan haengen (auch
        aus einer Mehrfachauswahl, Bedienidee 1), SPEICHERN (es gibt kein
        offenes Fenster, das speichern koennte), Karten auffrischen und den
        Plan oeffnen. items = [{tid, name, qty|None, vorgabe, me?, te?,
        own_bpc?, own_bpc_runs?}]; fehlt eine Menge, fragt der Dialog."""
        plans = self.settings.get("bau_saved_plans", []) or []
        p = next((x for x in plans if x.get("id") == plan_id), None)
        if p is None or not self._multi_ende_anhaengbar(p):
            return
        items = [dict(x) for x in (items or [])]
        if not items:
            return
        # Eingefroren/reserviert/abgeschlossen: in eine KOPIE, das Original
        # bleibt (Nutzer 27.09.2026).
        _kopie = self._multi_braucht_kopie(p)
        _alt_label = str(p.get("label") or p.get("item_name") or "")
        if any(x.get("qty") is None for x in items):
            _m = self._multi_mengen_dialog(
                [x for x in items if x.get("qty") is None],
                t("Add to multi build plan"))
            if _m is None:
                return
            _it = iter(_m)
            for x in items:
                if x.get("qty") is None:
                    x["qty"] = next(_it)["qty"]
        neu = self._multi_kopie_von(p) if _kopie else p
        for x in items:
            neu = self._multi_ende_anhaengen(
                neu, int(x["tid"]), int(x["qty"]),
                me=x.get("me"), te=x.get("te"),
                own_bpc=bool(x.get("own_bpc", False)),
                own_bpc_runs=int(x.get("own_bpc_runs", 0) or 0))
        if _kopie:
            plans.append(neu)
            plan_id = neu["id"]
        else:
            for i, x in enumerate(plans):
                if x.get("id") == plan_id:
                    plans[i] = neu
                    break
        config.save_settings(self.settings)
        try:
            self._reload_saved_plans()
        except Exception as _re:
            self._log_exception("Multi-Bauplan: Karten nach Anhaengen", str(_re))
        if len(items) == 1:
            _msg = t("\u201e{name}\u201c \u00d7 {n} added to \u201e{plan}\u201c \u2013 "
                     "it is a bundle now.").format(
                         name=str(items[0]["name"]), n=int(items[0]["qty"]),
                         plan=str(neu.get("label") or ""))
        else:
            _msg = t("{n} end products added to \u201e{plan}\u201c.").format(
                n=len(items), plan=str(neu.get("label") or ""))
        if _kopie:
            _msg = t("Added to a copy of \u201e{plan}\u201c \u2013 the saved plan stays "
                     "unchanged. New plan: \u201e{neu}\u201c.").format(
                         plan=_alt_label, neu=str(neu.get("label") or ""))
        self._flash_tip(_msg)
        # IST GENAU DIESER PLAN SCHON OFFEN (Nutzer 27.09.2026: "hat man den
        # Multiplan offen und fuegt per Rechtsklick ein Endprodukt hinzu, wird
        # man gefragt, ob man ihn oeffnen moechte, dabei ist er ja schon
        # offen - bei No wird nichts hinzugefuegt"): das Ende kommt direkt
        # ins offene Fenster, ohne Frage und ohne Neu-Oeffnen.
        if self._multi_offen_einfuegbar(plan_id):
            self._multi_offen_einfuegen(items)
            return
        _offen_gleich = (plan_id is not None and self._offener_bauplan() is not None
                         and getattr(self, "_bd_open_plan_id", None) == plan_id)
        # ERST FRAGEN, DANN OEFFNEN (Nutzer 27.09.2026: "wenn der Plan nach
        # jedem Hinzufuegen geoeffnet wird, nervt das - das Oeffnen dauert
        # sehr lange, Multi-Bauplaene mehrere Minuten"). Gespeichert ist er
        # schon; "No" laesst ihn einfach zu. Ist er offen, aber noch ein
        # Einzelplan (oder eingefroren), muss das Fenster neu - dann ohne Frage.
        if not _offen_gleich and not self._multi_jetzt_oeffnen_fragen(
                str(neu.get("label") or "")):
            return
        _d = self._offener_bauplan()
        if _d is not None:
            _d.close()
        self._multi_plan_oeffnen(neu, plan_id=plan_id)

    def _multi_jetzt_oeffnen_fragen(self, label):
        """Ja/Nein: den Plan nach dem Hinzufuegen jetzt oeffnen? Standard
        "No" - Enter oeffnet also nicht versehentlich einen langen Ladevorgang."""
        r = QMessageBox.question(
            self._tool_parent(), t("Multi build plan"),
            t("Open the multi build plan \u201e{plan}\u201c now?").format(plan=label),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        return r == QMessageBox.Yes

    @staticmethod
    def _multi_auswahl(tbl, row, lese):
        """MEHRFACHAUSWAHL einer Tabelle als [{tid, name, vorgabe}] (Bedienidee
        1). NUR wenn die angeklickte Zeile zur Auswahl gehoert und mehr als
        eine Zeile markiert ist - sonst [] (dann gilt das Einzel-Menue wie
        bisher). `lese(tbl, r)` liefert das dict einer Zeile oder None.
        Doppelte Items (gleiche type_id) zaehlen einmal."""
        try:
            rows = sorted({ix.row() for ix in tbl.selectionModel().selectedRows()})
        except Exception:
            return []
        if row not in rows or len(rows) < 2:
            return []
        out, gesehen = [], set()
        for r in rows:
            x = lese(tbl, r)
            if x and int(x["tid"]) not in gesehen:
                gesehen.add(int(x["tid"]))
                out.append(x)
        return out if len(out) >= 2 else []

    def _multi_auswahl_menue(self, menu, auswahl):
        """Die zwei Eintraege fuer eine Mehrfachauswahl: "Add N selected to
        multi build plan >" (Untermenue wie beim Einzel-Item) und "New multi
        build plan from selection (N)". Gibt (aktionen, a_neu) zurueck."""
        n = len(auswahl)
        a_neu = menu.addAction(icons.icon("package"),
                               t("New multi build plan from selection ({n})").format(n=n))
        akt = self._multi_untermenue(
            menu, None, None,
            titel=t("Add {n} selected to multi build plan").format(n=n))
        return akt, a_neu

    def _multi_neu_aus_auswahl(self, items):
        """NEUER MULTI-BAUPLAN AUS EINER MEHRFACHAUSWAHL (Nutzer 26.09.2026,
        Bedienidee 1): mehrere Zeilen markieren -> Rechtsklick -> "New multi
        build plan from selection". Mengen im vorbefuellten Dialog, dann
        oeffnet das Buendel UNGESPEICHERT - gespeichert wird wie immer mit
        "Save build plan". Gleiche Items werden addiert
        (`_multi_ende_anhaengen`). Unter zwei verschiedenen Enden entsteht
        kein Buendel - dafuer gibt es "Open build plan"."""
        if len({int(x["tid"]) for x in (items or [])}) < 2:
            self._flash_tip(t("Select at least two different items for a multi "
                              "build plan."))
            return None
        _m = self._multi_mengen_dialog(items, t("New multi build plan"))
        if _m is None:
            return None
        erst = _m[0]
        e = {"type_id": int(erst["tid"]), "qty": int(erst["qty"]),
             "item_name": erst["name"],
             "me": int(self.settings.get("bau_me", 10) or 0),
             "te": int(self.settings.get("bau_te", 0) or 0),
             "label": self._multi_standard_name(
                 [{"item_name": x["name"]} for x in _m])}
        for x in _m[1:]:
            e = self._multi_ende_anhaengen(e, int(x["tid"]), int(x["qty"]))
        _d = self._offener_bauplan()
        if _d is not None:
            _d.close()
        self._multi_plan_oeffnen(e, plan_id=None)
        self._flash_tip(t("Multi build plan with {n} end products opened \u2013 "
                          "save it to keep it.").format(n=len(e.get("enden") or [])),
                        ms=getattr(self, "FLASH_LESEN_MS", 2000))
        return e

    def _plan_karten_menue(self, card, plan_id, pos):
        """RECHTSKLICK AUF EINE KARTE IN "MY BUILD PLANS" (Nutzer 26.09.2026,
        Bedienidee 3): "Add build plan..." haengt ein weiteres Endprodukt an
        DIESEN Plan (Suche oder gespeicherter Plan, wie der Knopf im
        Bauplan-Fenster) - ohne den Plan erst zu oeffnen. Reservierte und
        abgeschlossene Plaene: Eintrag gesperrt, mit Grund."""
        from PySide6.QtWidgets import QMenu
        plans = self.settings.get("bau_saved_plans", []) or []
        p = next((x for x in plans if x.get("id") == plan_id), None)
        if p is None:
            return
        menu = QMenu(card)
        a_open = menu.addAction(icons.icon("hammer"), t("Open"))
        a_add = menu.addAction(icons.icon("plus"), t("Add build plan\u2026"))
        if not self._multi_ende_anhaengbar(p):
            a_add.setEnabled(False)
            a_add.setText(t("Add build plan\u2026") + "  "
                          + t("(reserved or completed)"))
        elif str(plan_id) in self.buendel_mitglieder(self.settings):
            # Ein Buendel-Mitglied ist kein eigener Plan mehr (Entscheid C) -
            # das Ende gehoert an das Buendel, nicht an das Mitglied.
            a_add.setEnabled(False)
            a_add.setText(t("Add build plan\u2026") + "  "
                          + t("(part of a multi build plan)"))
        self._plan_karten_menu = menu            # b-Suite
        chosen = menu.exec(card.mapToGlobal(pos))
        if chosen is a_open:
            self._open_saved_plan(plan_id)
        elif chosen is a_add and a_add.isEnabled():
            self._plan_karte_ende_dazu(plan_id)

    def _plan_karte_ende_dazu(self, plan_id):
        """"Add build plan..." einer Karte: Endprodukt waehlen (derselbe Dialog
        wie im Bauplan-Fenster, ohne den Plan selbst in der Liste) und an den
        gespeicherten Plan haengen - gespeichert, Karten neu, Plan offen."""
        wahl = self._multi_ende_waehlen(ausser=plan_id)
        if not wahl:
            return
        self._multi_enden_zu_plan(plan_id, [{
            "tid": int(wahl["tid"]), "name": str(wahl["name"]),
            "qty": int(wahl["qty"]), "me": wahl.get("me"), "te": wahl.get("te"),
            "own_bpc": bool(wahl.get("own_bpc", False)),
            "own_bpc_runs": int(wahl.get("own_bpc_runs", 0) or 0)}])

    def _multi_ende_waehlen(self, ausser=None):
        """Kleiner Dialog "Endprodukt hinzufuegen": Item-Suche (dieselbe
        Liste wie "Neuer Bauplan") + Menge. Gibt (tid, name, qty) oder None."""
        from PySide6.QtWidgets import QComboBox, QCompleter, QDialog
        pairs = getattr(self, "_build_picker_pairs", None)
        if not pairs:
            self._flash_tip(t("Run \u201eLoad recipes\u201c first."))
            return None
        dlg = QDialog(self._tool_parent()); dlg.setWindowTitle(t("Add end product"))
        dlg.setMinimumWidth(440)
        v = QVBoxLayout(dlg); v.setContentsMargins(18, 16, 18, 16); v.setSpacing(10)
        v.addWidget(QLabel(t("Search blueprint / item:")))
        cb = QComboBox(); cb.setEditable(True); cb.setMinimumHeight(34)
        cb.setInsertPolicy(QComboBox.NoInsert)
        for _nm, _tid in pairs:
            cb.addItem(_nm, _tid)
        cb.setCurrentIndex(-1); cb.setEditText("")
        comp = cb.completer()
        if comp:
            comp.setCompletionMode(QCompleter.PopupCompletion)
            comp.setFilterMode(Qt.MatchContains)
            comp.setCaseSensitivity(Qt.CaseInsensitive)
        v.addWidget(cb)
        _zr = QHBoxLayout(); _zr.addWidget(QLabel(t("Quantity")))
        menge = QSpinBox(); menge.setRange(1, 100000000); menge.setValue(1)
        menge.setGroupSeparatorShown(True)
        _zr.addWidget(menge); _zr.addStretch(); v.addLayout(_zr)
        # ODER EIN GESPEICHERTER BAUPLAN (Nutzer 26.09.2026: "ja unbedingt,
        # aber nur nicht eingefrorene, nicht reservierte Plaene"): Menge,
        # ME/TE und "Eigene BPC" kommen dann aus dem Plan; der Plan selbst
        # bleibt bestehen. Buendel stehen nicht drin (ein Buendel in ein
        # Buendel gibt es nicht).
        _mitgl = self.buendel_mitglieder(self.settings)
        plaene = [p for p in (self.settings.get("bau_saved_plans", []) or [])
                  if self._multi_ende_anhaengbar(p) and not self._multi_ist_plan(p)
                  and str(p.get("id")) not in _mitgl
                  and (ausser is None or p.get("id") != ausser)]
        v.addWidget(QLabel(t("\u2026 or take a saved build plan (open, not reserved):")))
        pb = QComboBox(); pb.setMinimumHeight(34)
        pb.addItem(t("(none \u2013 use the search above)"), None)
        for p in plaene:
            pb.addItem(f"{p.get('label') or p.get('item_name')}  \u00b7  "
                       f"{p.get('item_name')} \u00d7 {int(p.get('qty') or 1)}", p.get("id"))
        pb.setEnabled(bool(plaene))
        v.addWidget(pb)
        row = QHBoxLayout(); row.addStretch()
        cancel = QPushButton(t("Cancel")); cancel.clicked.connect(dlg.reject)
        ok = QPushButton(" " + t("Add")); ok.setObjectName("Primary")
        ok.setIcon(icons.icon("plus"))
        row.addWidget(cancel); row.addWidget(ok); v.addLayout(row)
        wahl = {}

        def _ok():
            _pid = pb.currentData()
            if _pid is not None:
                p = next((x for x in plaene if x.get("id") == _pid), None)
                if p is None:
                    return
                wahl["w"] = {"tid": int(p["type_id"]),
                             "name": str(p.get("item_name") or p.get("label")),
                             "qty": int(p.get("qty") or 1),
                             "me": int(p.get("me", 0) or 0), "te": int(p.get("te", 0) or 0),
                             "own_bpc": bool(p.get("own_bpc", False)),
                             "own_bpc_runs": int(p.get("own_bpc_runs", 0) or 0),
                             "plan_id": _pid}
                dlg.accept()
                return
            txt = cb.currentText().strip()
            tid = None; name = txt
            for i in range(cb.count()):
                if cb.itemText(i).lower() == txt.lower():
                    tid = cb.itemData(i); name = cb.itemText(i); break
            if tid is None and cb.currentIndex() >= 0:
                tid = cb.itemData(cb.currentIndex()); name = cb.currentText()
            if tid is None:
                return
            wahl["w"] = {"tid": int(tid), "name": name, "qty": int(menge.value())}
            dlg.accept()
        ok.clicked.connect(lambda _c=False: _ok())
        cb.lineEdit().returnPressed.connect(_ok)
        self._multi_ende_dialog = dlg          # b-Suite greift zu
        self._multi_ende_dialog_plaene = pb    # b-Suite liest die Planliste
        if dlg.exec() != QDialog.Accepted:
            return None
        return wahl.get("w")

    def _multi_offenen_plan_eintrag(self):
        """Der OFFENE Plan als Eintrag - Einzelplan oder Buendel, gespeichert
        oder nicht - so, wie das Fenster ihn gerade zeigt (Menge, ME/TE,
        Eigene BPC, Enden). Basis ist der gespeicherte Eintrag, falls es
        einen gibt (Haken, Blacklist, Decryptoren bleiben erhalten)."""
        plan_id = getattr(self, "_bd_open_plan_id", None)
        plans = self.settings.get("bau_saved_plans", []) or []
        e = dict(next((x for x in plans if x.get("id") == plan_id), None) or {}) \
            if plan_id is not None else {}
        _tid = int(getattr(self, "_bd_type", 0) or 0)
        if _tid == industry.BUENDEL_ID:
            e.update(self._multi_eintrag_felder(existing=e or None))
            e["type_id"] = industry.BUENDEL_ID
        else:
            e.update({"type_id": _tid,
                      "qty": int(getattr(self, "_bd_qty", 1) or 1),
                      "me": int(getattr(self, "_bd_me", 0) or 0),
                      "te": int(getattr(self, "_bd_te", 0) or 0),
                      "own_bpc": bool(getattr(self, "_bd_own_bpc", False)),
                      "own_bpc_runs": int(getattr(self, "_bd_own_bpc_runs", 0) or 0)})
        if not e.get("label"):
            _d = self._offener_bauplan()
            _titel = str(_d.windowTitle() if _d is not None else "")
            e["label"] = (_titel.split("\u2013", 1)[1].strip() if "\u2013" in _titel
                          else str(getattr(self, "_bd_name", "") or ""))
        e.setdefault("item_name", e["label"])
        return e

    def _multi_ende_hinzufuegen_offen(self):
        """Knopf "+ Add end product" im Bauplan-Fenster: Item waehlen, an den
        OFFENEN Plan haengen (ein Einzelplan wird dabei zum Buendel), Fenster
        mit dem neuen Stand neu oeffnen. Gespeichert wird mit "Save build
        plan". Eingefroren -> wird aufgetaut (der Schnappschuss passt nicht
        mehr), Hinweis dazu. Reserviert oder abgeschlossen -> nur ein Hinweis
        (Nutzer 26.09.2026: "kann aber keinen Multiplan erstellen")."""
        plan_id = getattr(self, "_bd_open_plan_id", None)
        plans = self.settings.get("bau_saved_plans", []) or []
        gesp = next((x for x in plans if x.get("id") == plan_id), None) \
            if plan_id is not None else None
        # Gespeichert und eingefroren/reserviert/abgeschlossen (oder das
        # Fenster selbst eingefroren): KOPIE statt Umbau (Nutzer 27.09.2026).
        _kopie = self._multi_braucht_kopie(gesp) or bool(getattr(self, "_bd_frozen", None))
        wahl = self._multi_ende_waehlen()
        if not wahl:
            return
        tid, name, qty = int(wahl["tid"]), str(wahl["name"]), int(wahl["qty"])
        # OFFENES BUENDEL: direkt hinein, Fenster bleibt (Nutzer 27.09.2026:
        # "an einem offenen Multiplan arbeiten und gleichzeitig Endprodukte
        # hinzufuegen und loeschen, ohne Uebergaenge").
        if not _kopie and self._multi_offen_einfuegbar(plan_id, auch_ungespeichert=True):
            self._multi_offen_einfuegen([dict(wahl)])
            self._flash_tip(t("\u201e{name}\u201c \u00d7 {n} added \u2013 save the plan to "
                              "keep it.").format(name=name, n=qty))
            return
        _basis = self._multi_offenen_plan_eintrag()
        _alt_label = str(_basis.get("label") or "")
        if _kopie:
            # NEUES, noch ungespeichertes Fenster mit der Kopie - der
            # gespeicherte Plan bleibt, wie er ist.
            _basis = self._multi_kopie_von(_basis)
        eintrag = self._multi_ende_anhaengen(
            _basis, tid, qty,
            me=wahl.get("me"), te=wahl.get("te"),
            own_bpc=bool(wahl.get("own_bpc", False)),
            own_bpc_runs=int(wahl.get("own_bpc_runs", 0) or 0))
        _d = self._offener_bauplan()
        if _d is not None:
            _d.close()
        self._multi_plan_oeffnen(eintrag, plan_id=None if _kopie else plan_id)
        if _kopie:
            self._flash_tip(t("\u201e{name}\u201c \u00d7 {n} added to a copy of \u201e{plan}\u201c "
                              "\u2013 the saved plan stays unchanged. Save the copy to "
                              "keep it.").format(name=name, n=qty, plan=_alt_label))
        else:
            self._flash_tip(t("\u201e{name}\u201c \u00d7 {n} added \u2013 save the plan to "
                              "keep it.").format(name=name, n=qty))

    def _multi_untermenue(self, menu, tid, name, titel=None):
        """Untermenue "Add to multi build plan >": ein Eintrag je gespeichertem Plan,
        der ein Ende annehmen darf (s. _multi_ende_anhaengbar) - seit
        27.09.2026 JEDER; eingefrorene, reservierte und abgeschlossene bekommen
        das Ende in einer Kopie (_multi_braucht_kopie). Gibt {Action:
        plan_id} zurueck; der Aufrufer prueft `chosen` dagegen."""
        aktionen = {}
        # Mitglieder eines Buendels sind KEINE eigenen Plaene mehr (Entscheid
        # C) - sie stehen nicht in der Liste (Nutzer-Screenshot 26.09.2026:
        # Ametat II / Flycatcher / Stork aus Multiplan 1 wurden angeboten).
        _mitgl = self.buendel_mitglieder(self.settings)
        plans = [p for p in (self.settings.get("bau_saved_plans", []) or [])
                 if self._multi_ende_anhaengbar(p) and str(p.get("id")) not in _mitgl]
        sub = menu.addMenu(icons.icon("package"), titel or t("Add to multi build plan"))
        if not plans:
            # KEIN STILLES VERSCHWINDEN (Nutzer 26.09.2026: "Rechtsklick-
            # Funktion ist weg" - alle seine Plaene waren eingefroren,
            # reserviert, abgeschlossen oder Buendel-Mitglieder). Der
            # Eintrag bleibt und sagt, warum er leer ist.
            _leer = sub.addAction(t("(no saved build plan yet)"))
            _leer.setEnabled(False)
            return aktionen
        # MULTIPLAENE ZUERST UND FETT (Nutzer 27.09.2026: "bestehende
        # Multiplaene hervorheben und ganz oben anzeigen, in Fett"). Danach
        # ein Trennstrich, dann die Einzelplaene - jeweils in der Reihenfolge
        # von "Meine Bauplaene".
        _multi = [p for p in plans if self._multi_ist_plan(p)]
        _einzel = [p for p in plans if not self._multi_ist_plan(p)]
        for p in _multi + _einzel:
            if p is (_einzel[0] if _einzel else None) and _multi:
                sub.addSeparator()
            _lbl = str(p.get("label") or p.get("item_name") or p.get("id"))
            if self._multi_ist_plan(p):
                _lbl += "  \u00b7 " + t("bundle, {n} end products").format(
                    n=len(p.get("enden") or []))
            a = sub.addAction(_lbl)
            if self._multi_ist_plan(p):
                _f = a.font()
                _f.setBold(True)
                a.setFont(_f)
            aktionen[a] = p.get("id")
        return aktionen

    def _multi_offen_einfuegbar(self, plan_id, auch_ungespeichert=False):
        """Kann ein Ende DIREKT ins offene Fenster (ohne Neu-Oeffnen)? Nur
        wenn dort ein Buendel offen ist (ein Einzelplan wird beim Anhaengen
        erst zum Buendel - das braucht ein neues Fenster), es nicht
        eingefroren ist (Schnappschuss-Preise) und - beim Rechtsklick - es
        GENAU dieser gespeicherte Plan ist."""
        if self._offener_bauplan() is None:
            return False
        if int(getattr(self, "_bd_type", 0) or 0) != industry.BUENDEL_ID:
            return False
        if not getattr(self, "_bd_buendel_enden", None):
            return False
        if getattr(self, "_bd_frozen", None):
            return False
        if getattr(self, "_bd_full_rebuild", None) is None:
            return False
        _offen = getattr(self, "_bd_open_plan_id", None)
        if auch_ungespeichert:
            return plan_id == _offen
        return plan_id is not None and plan_id == _offen

    def _multi_offen_einfuegen(self, items):
        """Enden ins OFFENE Buendel haengen, ohne das Fenster zu schliessen
        (Nutzer 27.09.2026). Derselbe Weg wie eine Mengen-Aenderung in der
        Endprodukte-Karte: Zustand aendern, neu rechnen - rebuild() baut das
        Buendel-Rezept aus `_bd_buendel_enden`, die Preise kommen aus dem
        ganzen Markt-Schnappschuss (`_bd_pricemap`), die Karte baut ihre
        Zeilen selbst neu. Was beim Oeffnen zusaetzlich entstand - NAMEN und
        GRUPPEN der Materialien -, holt ein Hintergrund-Job fuer die neuen
        Items nach und rechnet danach noch einmal.
        items = [{tid, name, qty, me?, te?, own_bpc?, own_bpc_runs?}]."""
        e = self._multi_offenen_plan_eintrag()
        for x in items:
            e = self._multi_ende_anhaengen(
                e, int(x["tid"]), int(x["qty"]),
                me=x.get("me"), te=x.get("te"),
                own_bpc=bool(x.get("own_bpc", False)),
                own_bpc_runs=int(x.get("own_bpc_runs", 0) or 0))
        self._bd_buendel_enden = [(int(a), int(b)) for a, b in (e.get("enden") or [])]
        self._bd_me_je_ende = {int(k): float(v) for k, v in
                               (e.get("me_je_ende") or {}).items()}
        self._bd_te_je_ende = {int(k): float(v) for k, v in
                               (e.get("te_je_ende") or {}).items()}
        self._bd_own_bpc_je_ende = {int(k): bool(v) for k, v in
                                    (e.get("own_bpc_je_ende") or {}).items()}
        self._bd_own_bpc_runs_je_ende = {int(k): int(v) for k, v in
                                         (e.get("own_bpc_runs_je_ende") or {}).items()}
        names = getattr(self, "_bd_names_ref", None)
        pm = getattr(self, "_bd_pricemap", None) or {}
        hub_je = getattr(self, "_bd_hub_sell_je_ende", None)
        for x in items:
            _tid = int(x["tid"])
            if names is not None and x.get("name"):
                names.setdefault(_tid, str(x["name"]))
            # Anderer Verkaufs-Hub gewaehlt: fuer das neue Ende gibt es dort
            # noch keinen Preis - bis zum naechsten Hub-Abruf der Scan-Preis.
            if hub_je and _tid not in hub_je and pm.get(_tid):
                hub_je[_tid] = pm.get(_tid)
        self._bd_plan_cache = None
        self._bd_tree_cache = None
        self._bd_reaction_stages = None
        self._bd_full_rebuild()
        self._multi_namen_nachholen()

    def _multi_namen_nachholen(self):
        """Namen + Gruppen fuer Items, die das offene Buendel neu braucht
        (im Hintergrund, ESI/SDE), danach einmal neu rechnen. Ohne das
        stuenden neue Materialien als "#34" da."""
        from .. import workers as _wk
        names = getattr(self, "_bd_names_ref", None)
        groups = getattr(self, "_bd_groups", None)
        rec = getattr(self, "_bd_recipes", None)
        pm = dict(getattr(self, "_bd_pricemap", None) or {})
        opts = dict(getattr(self, "_bd_opts", None) or {})
        if names is None or rec is None:
            return
        _keys = tuple(getattr(self, "PLAN_QTY_KEYS", ()) or ())
        _bekannt = set(names)
        _gruppen_bekannt = set(groups or {})

        def job():
            plan = industry.production_plan(industry.BUENDEL_ID, 1, pm.get, rec, opts)
            ids = set()
            for _k in _keys:
                _d = plan.get(_k) or {}
                if isinstance(_d, dict):
                    ids |= {int(x) for x in _d}
            ids.discard(industry.BUENDEL_ID)
            neu_n = [i for i in ids if i not in _bekannt]
            neu_g = [i for i in ids if i not in _gruppen_bekannt]
            return (esi.resolve_names(neu_n) if neu_n else {},
                    industry.group_names(neu_g) if neu_g else {})

        def done(res):
            n_neu, g_neu = res or ({}, {})
            if not n_neu and not g_neu:
                return
            if getattr(self, "_bd_names_ref", None) is not names:
                return                      # inzwischen anderer Plan offen
            names.update({k: v for k, v in n_neu.items() if k not in names})
            if groups is not None:
                groups.update(g_neu)
            _fn = getattr(self, "_bd_full_rebuild", None)
            if _fn is not None:
                self._bd_tree_cache = None
                _fn()
        self._run(_wk.Worker(job), done,
                  fail_cb=lambda _m: self._log_exception(
                      "Multi-Bauplan: Namen nachholen", str(_m)),
                  overlay=False)

    def _multi_ende_entfernen(self, tid):
        """Ein Endprodukt aus dem OFFENEN Buendel nehmen (Nutzer 26.09.2026:
        "nach genaueren Einstellungen habe ich festgestellt, dass sich einige
        Endprodukte nicht lohnen zu bauen, wir brauchen einen Knopf, um
        diese aus dem Multiplan wieder entfernen zu koennen").

        DAS FENSTER BLEIBT OFFEN (Nutzer 27.09.2026: "loescht man im
        Multiplan einen Bauplan heraus, schliesst sich der Multiplan und
        oeffnet sich anschliessend wieder - besser der bleibt offen und
        entfernt einfach einen Plan"). Frueher wurde neu geoeffnet, weil das
        Buendel-Rezept nur beim Oeffnen entstand. Seit b85 baut
        `rebuild()` es JEDES MAL aus `_bd_buendel_enden` neu (derselbe Weg
        wie eine Mengen-Aenderung in der Endprodukte-Karte) - also genuegt
        es, den Zustand zu aendern und neu zu rechnen; die Karte baut ihre
        Zeilen selbst neu, sobald sich ihre Anzahl aendert. Der Quellplan
        des Endes verlaesst `_bd_buendel_quellen` mit (er ist danach wieder
        frei). Gespeichert wird NICHT hier, sondern mit "Save build plan".

        GRENZEN: eingefroren -> erst auftauen (das Material ist gekauft,
        dieselbe Regel wie beim Bearbeiten-Dialog, aa388); unter zwei Enden
        -> kein Buendel mehr, dafuer gibt es "Edit" in "Meine Bauplaene".
        """
        tid = int(tid)
        enden = [(int(a), int(b)) for a, b in
                 (getattr(self, "_bd_buendel_enden", None) or [])]
        if tid not in {a for a, _b in enden}:
            return
        namen = getattr(self, "_bd_names_ref", None) or {}
        name = str(namen.get(tid) or tid)
        if getattr(self, "_bd_frozen", None):
            self._flash_tip(t("Frozen plan \u2013 unfreeze it first (Tools), then "
                              "remove \u201e{name}\u201c.").format(name=name))
            return
        if len(enden) <= 2:
            self._flash_tip(t("A bundle needs at least two end products \u2013 "
                              "use \u201eEdit\u201c in My build plans to dissolve it."))
            return
        r = QMessageBox.question(
            self._tool_parent(), t("Multi build plan"),
            t("Remove \u201e{name}\u201c from this bundle?\n\nNothing is saved until you "
              "click \u201eSave build plan\u201c.").format(name=name),
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if r != QMessageBox.Yes:
            return
        plans = self.settings.get("bau_saved_plans", []) or []
        by_id = {x.get("id"): x for x in plans}
        # Der Quellplan dieses Endes geht mit - und nur er.
        self._bd_buendel_quellen = [
            qid for qid in (getattr(self, "_bd_buendel_quellen", None) or [])
            if int((by_id.get(qid) or {}).get("type_id", 0) or 0) != tid]
        self._bd_buendel_enden = [(a, b) for a, b in enden if a != tid]
        for _attr in ("_bd_me_je_ende", "_bd_te_je_ende", "_bd_own_bpc_je_ende",
                      "_bd_own_bpc_runs_je_ende"):
            _d = dict(getattr(self, _attr, None) or {})
            _d.pop(tid, None)
            _d.pop(str(tid), None)
            setattr(self, _attr, _d)
        # Wie bei einer Mengen-Aenderung - plus Baum und Stufen, denn hier
        # faellt ein ganzer Ast weg.
        self._bd_plan_cache = None
        self._bd_tree_cache = None
        self._bd_reaction_stages = None
        _fn = getattr(self, "_bd_full_rebuild", None)
        if _fn is not None:
            _fn()
        self._flash_tip(t("\u201e{name}\u201c removed from the bundle \u2013 save the "
                          "plan to keep it.").format(name=name))

    def _multi_eintrag_felder(self, existing=None):
        """Die Buendel-Felder fuer den Speicherer im Bauplan-Dialog: aus dem
        offenen Zustand (Enden, Quellen, ME/TE je Ende); den Vergleichsstand
        der Quellen vom vorhandenen Eintrag uebernehmen, sonst neu bilden."""
        enden = [[int(a), int(b)] for a, b in
                 (getattr(self, "_bd_buendel_enden", None) or [])]
        quellen = list(getattr(self, "_bd_buendel_quellen", None) or [])
        stand = dict((existing or {}).get("quellen_stand") or {})
        if not stand and quellen:
            by_id = {x.get("id"): x for x in
                     (self.settings.get("bau_saved_plans", []) or [])}
            for qid in quellen:
                q = by_id.get(qid)
                if q is not None and not self._multi_ist_plan(q):
                    stand[str(qid)] = self._multi_quellen_stand(q)
        return {"multi": True, "qty": 1, "enden": enden, "quellen": quellen,
                "quellen_stand": stand,
                "me_je_ende": {str(k): v for k, v in
                               (getattr(self, "_bd_me_je_ende", None) or {}).items()},
                "te_je_ende": {str(k): v for k, v in
                               (getattr(self, "_bd_te_je_ende", None) or {}).items()},
                "own_bpc_je_ende": {
                    str(k): bool(v) for k, v in
                    (getattr(self, "_bd_own_bpc_je_ende", None) or {}).items()},
                "own_bpc_runs_je_ende": {
                    str(k): int(v) for k, v in
                    (getattr(self, "_bd_own_bpc_runs_je_ende", None) or {}).items()}}

    def _multi_hinweis_einzelplan(self, pid):
        """Beim Oeffnen eines Einzelplans, der in einem Multi-Bauplan steckt:
        kurz sagen, dass eingekauft und gebaut DORT wird.

        BEWUSST KEIN MODALER DIALOG: den Plan einzeln anzusehen ist voellig
        in Ordnung (Preise pruefen, ME nachschlagen). Nur die Einkaufsliste
        waere doppelt - das ist einen Hinweis wert, keine Nachfrage."""
        namen = (self._multi_gehoert_zu(
            self.settings.get("bau_saved_plans", []) or []).get(pid) or [])
        if not namen:
            return False
        self._flash_tip(t(
            "Heads-up: this plan is part of the multi build plan \u201e{name}\u201c \u2013 "
            "buy and build there, otherwise you order the same material twice."
        ).format(name=namen[0]))
        return True

    def _open_multi_saved_plan(self, pid):
        """Gespeicherten Multi-Plan oeffnen - mit dem Hinweis aus Entscheid A,
        wenn sich ein Einzelplan seit dem Speichern geaendert hat."""
        plans = self.settings.get("bau_saved_plans", []) or []
        p = next((x for x in plans if x.get("id") == pid), None)
        if not p:
            return
        by_id = {x.get("id"): x for x in plans}
        stand_alt = p.get("quellen_stand") or {}
        geaendert = []
        for qid in (p.get("quellen") or []):
            q = by_id.get(qid)
            if q is None or self._multi_ist_plan(q):
                continue
            alt = stand_alt.get(str(qid))
            if alt is not None and list(alt) != self._multi_quellen_stand(q):
                geaendert.append(q)
        if geaendert:
            namen = "\n• ".join(str(q.get("label")) for q in geaendert[:6])
            r = QMessageBox.question(
                self, t("Multi build plan"),
                t("These build plans were changed since this multi build plan "
                  "was saved:\n• {names}\n\nTake over their current "
                  "quantity, ME and TE? (No = keep the multi build plan as it "
                  "is.)").format(names=namen),
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if r == QMessageBox.Yes:
                quellen = [by_id[qid] for qid in (p.get("quellen") or [])
                           if qid in by_id and not self._multi_ist_plan(by_id[qid])]
                # de_scan4: aus - Plan-Name des Nutzers, kein Anzeigetext
                neu = self._multi_plan_aus_quellen(quellen, label=p.get("label"))
                # de_scan4: an
                if neu:
                    for k in ("enden", "quellen", "quellen_stand",
                              "me_je_ende", "te_je_ende",
                              "own_bpc_je_ende", "own_bpc_runs_je_ende"):
                        p[k] = neu[k]
                    config.save_settings(self.settings)
        self._multi_plan_oeffnen(p, plan_id=pid)

    # ------------------------------------------------------------ Bauplan-Dialog
    # POLSTER UM DEN INHALT EINER ZAHLENSPALTE - hier und in b85 dieselbe
    # Quelle, sonst laufen Code und Pruefung auseinander. Gemessen ist der
    # Inhalt; das Polster ist nur der Zellenrand (4 px links, 4 px rechts)
    # plus ein wenig Luft, damit nichts an der Gitterlinie klebt.
    # HOECHSTENS SO VIELE ENDEN OHNE BILDLAUF in der Karte "Endprodukte"
    # (Nutzer 26.09.2026); mehr laufen in der Tabelle selbst.
    ENDEN_SICHTBAR = 5
    _SP_PAD_WIDGET = 8
    # 6 px Polster je Seite (theme: QTableWidget::item padding 5px 6px)
    # + 2 px Rahmen + Reserve; mit 14 wurden Zahlen auf seinem Windows
    # noch mit "..." gekuerzt (26.09.2026: "23'063'0...").
    _SP_PAD_TEXT = 24
    _SP_MIN = 46

    @staticmethod
    def _multi_enden_spalten(tbl):
        """Die Zahlenspalten der Endprodukte-Karte auf ihren INHALT deckeln.

        NUTZER-BEFUND 23.09.2026 (pruefe.py auf seinem Rechner): "alle
        Spalten passen ins Fenster (1361 px in 1334 px)" und "der Name
        bekommt den freien Platz" schlug fehl. Mit `ResizeToContents` nimmt
        eine Spalte die Breite des BREITESTEN von Kopf und Zelle - und der
        Kopf ist hier das Breitere. Auf seinem Windows sind dieselben
        Widgets rund 1,6x breiter (Lehre b66), also wuchsen die neun
        Zahlenspalten ueber das Fenster hinaus, und die Namensspalte
        (Stretch) fiel auf die Mindestbreite.

        HIER WIRD GEMESSEN, NICHT GERATEN: jede Spalte bekommt fest, was
        ihre ZELLEN brauchen - das Bedienfeld seine `sizeHint`, die Zahl
        ihre Textbreite. Der Kopf darf schmaler werden als sein Text (er
        kuerzt mit "..." und traegt den vollen Text als Tooltip); die Zahl
        darunter darf es nie, sonst liest man sie falsch. Was uebrig
        bleibt, geht an die Namensspalte - die einzige, die mit jeder
        Breite etwas anfangen kann.
        """
        from PySide6.QtWidgets import QHeaderView as _HV
        hh = tbl.horizontalHeader()
        hh.setMinimumSectionSize(MultiBauplan._SP_MIN)
        _fm = tbl.fontMetrics()
        # DER KOPF WIRD ANDERS GEZEICHNET ALS SEINE SCHRIFT VERSPRICHT
        # (Nutzer-Screenshot 26.09.2026, zweiter Anlauf: "COST/UNIT (I...",
        # "ROFIT/UNIT, NE" links abgeschnitten): das Thema setzt fuer
        # QHeaderView::section GROSSBUCHSTABEN, fett 12 px, 0,5 px
        # Buchstabenabstand und 8 px Polster je Seite - `hh.fontMetrics()`
        # misst davon nichts. Deshalb wird hier mit genau dieser Schrift
        # gemessen, am GROSSGESCHRIEBENEN Text, plus Polster.
        from PySide6.QtGui import QFont as _QF, QFontMetrics as _QFM
        _hf = _QF(hh.font())
        _hf.setBold(True)
        _hf.setPixelSize(12)
        _hf.setLetterSpacing(_QF.AbsoluteSpacing, 0.5)
        _hfm = _QFM(_hf)
        _KOPF_POLSTER = 16          # theme: padding 7px 8px
        for _c in range(1, tbl.columnCount()):
            _br = hh.minimumSectionSize()
            _nur_text = True
            for _r in range(tbl.rowCount()):
                _w = tbl.cellWidget(_r, _c)
                if _w is not None:
                    _nur_text = False
                    # Der Deckel gewinnt: ein Feld, das breiter sein WILL,
                    # als es sein darf, darf seine Spalte nicht aufblasen.
                    _wb = _w.sizeHint().width()
                    if _w.maximumWidth() > 0:
                        _wb = min(_wb, _w.maximumWidth())
                    _br = max(_br, _wb + MultiBauplan._SP_PAD_WIDGET)
                    continue
                _it = tbl.item(_r, _c)
                if _it is not None:
                    _br = max(_br, _fm.horizontalAdvance(_it.text() or "")
                              + MultiBauplan._SP_PAD_TEXT)
            # ZAHLENSPALTEN BEKOMMEN AUCH IHREN KOPF (Nutzer 26.09.2026:
            # "Profit/Unit, Cop..., Cost/uni abgeschnitten"): die Ueberschrift
            # ist zweizeilig, die laengste ZEILE davon passt neben die Zahl,
            # ohne die neun Spalten ueber das Fenster zu treiben - das taten
            # nur die Bedienfeld-Spalten (Quantity/ME/TE/Own BPC/Runs/BPC),
            # und die bleiben bei der Breite ihres Feldes (Kopf kuerzt,
            # Tooltip traegt den Text).
            if _nur_text:
                _hi = tbl.horizontalHeaderItem(_c)
                for _zeile in str(_hi.text() if _hi is not None else "").split("\n"):
                    _br = max(_br, _hfm.horizontalAdvance(_zeile.upper())
                              + _KOPF_POLSTER + MultiBauplan._SP_PAD_TEXT)
            hh.setSectionResizeMode(_c, _HV.Fixed)
            tbl.setColumnWidth(_c, int(_br))
        hh.setSectionResizeMode(0, _HV.Stretch)

    def _multi_enden_karte(self, type_id, names, parent_layout):
        """Karte "Endprodukte" im Bauplan-Dialog - nur fuer ein Buendel.

        SIE IST DIE EINE STELLE, AN DER MAN JE ENDPRODUKT SCHRAUBT
        (Schritt 4). Beim Einzelplan sitzen ME/TE und "Eigene BPC" oben in
        der Kopfzeile - fuer EIN Endprodukt. Ein Buendel hat mehrere, und
        jedes kann anders sein (Nutzer, 19.09.2026: "aber jeder Plan hat
        doch seine eigene ME/TE wenn sie T2 sind"). Deshalb sind die Felder
        oben beim Buendel ausgeblendet und stehen stattdessen HIER, je
        Zeile - direkt neben den Kosten, die sie erzeugen.

        Spalten: Endprodukt | Menge | ME | TE | Eigene BPC | Runs/BPC |
        Kosten/Stk | Verkauf/Stk | Gewinn/Stk.

        ME/TE sind GESPERRT, solange die Invention regiert: eine erfundene
        BPC hat eine feste ME (2 % + Decryptor), da gibt es nichts
        einzustellen - das Feld zeigt den echten Wert und sagt im Tooltip,
        woher er kommt. Erst "Eigene BPC" gibt sie frei; dann ist es DEINE
        Kopie, und die Invention wird fuer dieses Ende aus der Rechnung
        genommen. Genau dieselbe Regel wie oben beim Einzelplan, nur je
        Zeile.

        Liefert die Auffrisch-Funktion, die rebuild() nach jedem Plan
        aufruft (self._bd_multi_refresh)."""
        if type_id != industry.BUENDEL_ID:
            self._bd_multi_refresh = None
            self._bd_multi_tbl = None
            # EINZELPLAN: dieselbe Karte, nur der Kopf - damit "+ Add build
            # plan" an DERSELBEN Stelle und im selben Stil steht wie beim
            # Buendel (Nutzer 27.09.2026).
            _eb = getattr(self, "_bd_ende_btn", None)
            if _eb is not None and _eb.parentWidget() is None:
                _k1 = QFrame(); _k1.setObjectName("Card")
                _k1.setStyleSheet(
                    f"QFrame#Card {{ border: 1px solid rgba(242,162,60,0.4); }}")
                _v1 = QVBoxLayout(_k1); _v1.setContentsMargins(14, 10, 14, 10)
                _h1 = QHBoxLayout(); _h1.setContentsMargins(0, 0, 0, 0)
                _t1 = QLabel(t("END PRODUCT OF THIS PLAN"))
                _t1.setStyleSheet(
                    f"color:{theme.AMBER}; font-weight:800; letter-spacing:1px;")
                _h1.addWidget(_t1)
                _h1.addSpacing(14)
                _h1.addWidget(_eb)
                _h1.addStretch()
                _v1.addLayout(_h1)
                parent_layout.addWidget(_k1)
                self._bd_ende_karte_einzel = _k1        # b-Suite
            return None
        card = QFrame(); card.setObjectName("Card")
        card.setStyleSheet(f"QFrame#Card {{ border: 1px solid rgba(242,162,60,0.4); }}")
        cv = QVBoxLayout(card); cv.setContentsMargins(14, 10, 14, 10); cv.setSpacing(6)
        # EINKLAPPBAR WIE "DETAILS" (Nutzer 23.09.2026: "ausserdem moechte
        # ich, dass man 'Endprodukte dieses Buendels' einklappen kann wie
        # der Details auch - standardmaessig aber offen"). Dieselbe Optik
        # wie dort: kleiner Knopf mit Pfeil, Cyan, am rechten Rand der
        # Ueberschrift.
        _kopf = QHBoxLayout()
        _kopf.setContentsMargins(0, 0, 0, 0)
        titel = QLabel(t("END PRODUCTS OF THIS BUNDLE"))
        titel.setStyleSheet(f"color:{theme.AMBER}; font-weight:800; letter-spacing:1px;")
        _kopf.addWidget(titel)
        # "+ ADD BUILD PLAN" HIER, nicht in der Leiste oben (Nutzer
        # 26.09.2026: "in der Endprodukt-Box drin, direkt unter 'Bundle'").
        # Der Knopf entsteht im Fenster (mw_bauplan_fenster) und wird beim
        # Buendel nur hier eingehaengt.
        _ende_btn = getattr(self, "_bd_ende_btn", None)
        if _ende_btn is not None and _ende_btn.parentWidget() is None:
            _kopf.addSpacing(14)
            _kopf.addWidget(_ende_btn)
        _kopf.addStretch()
        _klapp = QPushButton("")
        _klapp.setCheckable(True)
        _klapp.setFixedWidth(34)
        _klapp.setCursor(Qt.PointingHandCursor)
        _klapp.setStyleSheet(
            f"QPushButton{{border:1px solid {theme.BORDER}; border-radius:5px; "
            f"color:{theme.CYAN}; font-size:11px; padding:2px 8px; "
            f"background:{theme.PANEL2};}}"
            f"QPushButton:hover{{border-color:{theme.CYAN}; "
            f"background:{theme.PANEL};}}")
        _kopf.addWidget(_klapp)
        cv.addLayout(_kopf)
        # ALLES AUSSER DER UEBERSCHRIFT KOMMT IN EINEN KASTEN - nur der
        # laesst sich am Stueck verstecken, und die Ueberschrift bleibt
        # stehen, damit man die Karte wiederfindet.
        _body = QWidget()
        _bv = QVBoxLayout(_body)
        _bv.setContentsMargins(0, 0, 0, 0); _bv.setSpacing(6)
        hinweis = QLabel(t(
            "Quantity, ME/TE and \u201eOwn BPC\u201c belong to EACH end product here \u2013 "
            "that is why the single fields above are hidden for a bundle. T2 "
            "ends take ME/TE from their decryptor (Invention tab); tick \u201eOwn "
            "BPC\u201c to build from your own copy with its own values instead."))
        hinweis.setObjectName("Muted"); hinweis.setWordWrap(True)
        _bv.addWidget(hinweis)
        # WARNUNG, WENN UNKLAR IST, OB ERFUNDEN WIRD (Nutzer 26.09.2026:
        # "Warnmeldung wenn nicht klar ist, ob man T2 noch baut ueber
        # Decryptoren oder alle Own BPC sind"): ein T2-Ende OHNE Haken
        # "Eigene BPC", fuer das der Blaupausen-Cache eigene Kopien kennt -
        # der Plan erfindet dann (Datacores, Versuche), obwohl Kopien im
        # Hangar liegen. Versteckt, solange nichts unklar ist.
        _warn = QLabel("")
        _warn.setStyleSheet(f"color:{theme.AMBER}; font-weight:700;")
        _warn.setWordWrap(True)
        _warn.setVisible(False)
        _bv.addWidget(_warn)
        self._bd_multi_warn_lbl = _warn
        # ISK EINMAL IN DIE KOPFZEILE statt dreimal je Zeile (Nutzer-Befund
        # 20.09.2026: Spalten zu schmal, Text abgeschnitten) - " ISK" hinter
        # jeder Zahl kostet rund 45 px je Geldspalte, hier also 135.
        SPALTEN = [t("End product"), t("Quantity"), t("ME"), t("TE"),
                   t("Own BPC"), t("Runs/BPC"), t("Copies"),
                   # ZWEIZEILIG (Nutzer-Befund 23.09.2026, sein Windows:
                   # "1361 px in 1334 px" - die Spalten passten nicht mehr
                   # nebeneinander, der Name bekam nur noch die Mindest-
                   # breite). Die Ueberschrift ist das Breiteste an diesen
                   # Spalten, nicht die Zahl darunter; auf zwei Zeilen
                   # braucht sie rund ein Drittel weniger Platz.
                   t("Cost/unit") + "\n(ISK)", t("Sell/unit") + "\n(ISK)",
                   t("Profit/unit, net") + "\n(ISK)",
                   # HERAUSNEHMEN (Nutzer 26.09.2026: "einige Endprodukte
                   # lohnen sich nicht ... wir brauchen einen Knopf, um diese
                   # aus dem Multiplan wieder entfernen zu koennen").
                   ""]
        tbl = QTableWidget(0, len(SPALTEN))
        tbl.setHorizontalHeaderLabels(SPALTEN)
        tbl.verticalHeader().setVisible(False)
        tbl.setEditTriggers(QTableWidget.NoEditTriggers)
        tbl.setSelectionMode(QTableWidget.NoSelection)
        # Mehr als ENDEN_SICHTBAR Enden: Bildlaufleiste rechts, zeilenweise.
        tbl.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        tbl.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
        hh = tbl.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, len(SPALTEN)):
            hh.setSectionResizeMode(c, QHeaderView.ResizeToContents)
        hh.setMinimumSectionSize(58)
        hh.setTextElideMode(Qt.ElideRight)
        for _c0, _txt0 in enumerate(SPALTEN):
            _hi0 = tbl.horizontalHeaderItem(_c0)
            if _hi0 is not None:
                _hi0.setToolTip(_txt0.replace("\n", " ")
                                or t("Remove from bundle"))
        tbl.setFocusPolicy(Qt.NoFocus)
        tbl.setToolTip(t(
            "Cost per unit = this product's share of the bundle: shared "
            "intermediates (and their surplus) are split by demand, its own job "
            "and invention costs are its own. The sum over all end products is "
            "exactly the bundle's total cost."))
        # BILDER DER ENDPRODUKTE (Nutzer 23.09.2026: "danach fehlen mir in
        # einem Multibuildplan immer noch die Icons der Endprodukte ganz
        # oben"). Geholt wird EINMAL je Ende und dann gemerkt: `_refresh`
        # laeuft bei jedem Neuaufbau, ein Abruf je Durchgang waere eine
        # Abruf-Lawine (dieselbe Ueberlegung wie bei der Plan-Liste des
        # Multi-Dialogs, nur andersherum entschieden - hier sind es die
        # wenigen Enden EINES Buendels, dort waren es alle Plaene).
        tbl.setIconSize(QSize(24, 24))
        _bv.addWidget(tbl)
        # DIE SUMME DAZUSCHREIBEN (Nutzer-Befund 20.09.2026: "ich bin mir
        # nicht sicher ob hier auch die Rechnung beider Plaene stimmt, im
        # Profit wirkt es falsch"). Er hatte die Spalte selbst addiert und
        # kam auf eine andere Zahl als oben - weil die Spalte damals brutto
        # war. Jetzt steht die Summe da und muss den grossen Gewinn treffen.
        _gsum = QLabel("")
        _gsum.setObjectName("Muted"); _gsum.setWordWrap(True)
        _bv.addWidget(_gsum)
        self._bd_multi_gewinn_lbl = _gsum
        # "Compare: alone vs. in bundle" ist seit 26.09.2026 AUSGEBAUT (Nutzer:
        # "ich moechte, dass der Profit pro Unit oben rechts stimmt, einfach
        # ohne Button"). Die Spalten Kosten/Stk und Gewinn/Stk stimmen jetzt
        # von selbst mit den grossen Feldern darunter ueberein (s.
        # `_gewinn_nachziehen`, Parameter `gesamt`).
        cv.addWidget(_body)
        parent_layout.addWidget(card)
        self._bd_multi_tbl = tbl
        self._bd_multi_body = _body
        self._bd_multi_klapp = _klapp

        def _klapp_setzen(offen):
            # setVisible erst JETZT - `_body` haengt seit cv.addWidget im
            # Layout (b8-Falle: vorher waere daraus ein eigenes Fenster
            # geworden).
            _body.setVisible(bool(offen))
            _klapp.setText("\u25b4" if offen else "\u25be")
            _klapp.setToolTip(t("Hide the end products of this bundle")
                              if offen else
                              t("Show the end products of this bundle"))

        def _klapp_geklickt(offen):
            _klapp_setzen(bool(offen))
            self.settings["bau_multi_enden_offen"] = bool(offen)
            try:
                config.save_settings(self.settings)
            except Exception:
                pass
        # STANDARD OFFEN (Nutzer-Vorgabe), der eigene Stand gewinnt.
        _offen0 = bool(self.settings.get("bau_multi_enden_offen", True))
        _klapp.setChecked(_offen0)
        _klapp_setzen(_offen0)
        _klapp.toggled.connect(_klapp_geklickt)

        def _ende_icon(tid):
            """Bild eines Endprodukts - einmal geholt, dann gemerkt."""
            _c = getattr(self, "_bd_multi_icons", None)
            if _c is None:
                _c = {}
                self._bd_multi_icons = _c
            if int(tid) not in _c:
                try:
                    _c[int(tid)] = self._item_pixmap(int(tid), size=32)
                except Exception:
                    _c[int(tid)] = None
            return _c[int(tid)]

        # EINMAL BAUEN, NUR ZAHLEN NACHFUEHREN: die Bedien-Elemente je Zeile
        # duerfen nicht bei jedem rebuild() neu entstehen - sonst verliert
        # das Feld, in dem man gerade tippt, den Fokus.
        self._bd_multi_zeilen = {}
        _anstoss = QTimer(tbl); _anstoss.setSingleShot(True); _anstoss.setInterval(250)

        def _neu_rechnen():
            _fn = getattr(self, "_bd_full_rebuild", None)
            if _fn is not None:
                _fn()
        _anstoss.timeout.connect(_neu_rechnen)

        def _invention_regiert(tid):
            """Kommt die ME dieses Endes aus der Invention (statt aus dem
            Feld)? Genau die Frage, die `_invention_me_pct` beantwortet -
            hier mit derselben Quelle, nicht nachgebaut."""
            rec = getattr(self, "_bd_recipes", None)
            opts = getattr(self, "_bd_opts", None) or {}
            bp = (getattr(rec, "product_to_bp", None) or {}).get(int(tid))
            if not bp:
                return False
            return industry._invention_me_pct(bp[0], rec, opts) is not None

        def _kann_invention(tid):
            rec = getattr(self, "_bd_recipes", None)
            bp = (getattr(rec, "product_to_bp", None) or {}).get(int(tid))
            return bool(bp and bp[0] in (getattr(rec, "invention_for_bpc", None) or {}))

        def _zeile_bauen(r, tid):
            from PySide6.QtWidgets import QCheckBox as _CB, QSpinBox as _SB
            w = {}
            menge = _SB(); menge.setRange(1, 100000000)
            menge.setGroupSeparatorShown(True); menge.setKeyboardTracking(False)
            menge.setToolTip(t("How many of THIS end product the bundle builds."))
            me = _SB(); me.setRange(0, 10)
            te = _SB(); te.setRange(0, 20)
            obpc = _CB()
            obpc.setToolTip(t(
                "On: you already own a blueprint copy of this end product \u2013 its "
                "ME/TE below are yours to set, and invention is left out of the "
                "calculation for THIS product (no invention cost). Off: the ME "
                "comes from the invention (2 % base plus decryptor) and cannot "
                "be edited."))
            runs = _SB(); runs.setRange(1, 9999)
            runs.setToolTip(t(
                "How many runs does ONE of your own BPCs of this product have? "
                "The run planner never puts more than this into a single job."))
            # BREITEN GEDECKELT (Nutzer-Befund "zu wenig Platz"): die
            # Mengenspalte nahm sich 121 px, die dem Namen fehlten.
            # ABER NIE UNTER DEM, WAS DIE BOX BRAUCHT (Nutzer-Befund
            # 20.09.2026: "oben rechts sind die ME/TE abgeschnitten, kann man
            # nicht lesen/tippen"). Die 58 px reichten hier offscreen, auf
            # seinem Windows nicht - dort sind dieselben Widgets rund 1,85x
            # breiter (derselbe Befund wie bei b66). Deshalb GEMESSEN statt
            # geraten: sizeHint() kennt Ziffern, Pfeile und Rand des Themas.
            _deckel = []
            for _w, _c, _br in ((menge, 1, 88), (me, 2, 58), (te, 3, 58),
                                (runs, 5, 74)):
                _w.setMinimumWidth(46)
                tbl.setCellWidget(r, _c, _w)
                _deckel.append((_w, _br))
            _wrap = QWidget(); _hl = QHBoxLayout(_wrap)
            _hl.setContentsMargins(6, 0, 6, 0); _hl.addWidget(obpc)
            _hl.setAlignment(Qt.AlignCenter)
            tbl.setCellWidget(r, 4, _wrap)
            # KNOPF "AUS DEM BUENDEL NEHMEN" (Nutzer 26.09.2026). Das Fenster
            # wird mit den restlichen Enden neu geoeffnet - gespeichert wird
            # erst mit "Save build plan", wie jede andere Aenderung hier.
            raus = QPushButton("\u2715")
            # SICHTBAR UND ROT (Nutzer 26.09.2026: "das X ist etwas
            # abgeschnitten und rot soll es sein, damit man erkennt, was es
            # fuer ein Symbol ist"). Der Themen-Stil "Danger" hat 12 px
            # Polster links und rechts - in 30 px blieben 6 px fuer das X.
            # Eigene Regel ohne Polster, feste Groesse, Rahmen in Ruhe und
            # Hover gleich stark (sonst springt die Zeile).
            # HOEHE NICHT FEST (Nutzer 26.09.2026, Bild: "X noch
            # abgeschnitten"): das Themen-QSS gibt QTableWidget::item 5 px
            # Polster oben/unten, der Zell-Widget-Rahmen ist darum nur ~18 px
            # hoch - ein fest 24 px hoher Knopf verlor seinen unteren Rand.
            # Nachgestellt mit theme.QSS: Rahmen 18, Knopf 24 -> abgeschnitten.
            # Jetzt feste Breite, Hoehe = Zellrahmen (AlignHCenter statt
            # AlignCenter), also passt er bei jedem Polster ganz hinein.
            raus.setFixedWidth(28)
            raus.setMinimumHeight(0)
            raus.setStyleSheet(
                f"QPushButton{{color:{theme.RED}; border:1px solid {theme.RED}; "
                f"border-radius:4px; padding:0px; font-weight:800; "
                f"font-size:13px; background:transparent;}}"
                f"QPushButton:hover{{background:{theme.RED}; color:{theme.BG}; "
                f"border:1px solid {theme.RED};}}")
            raus.setToolTip(t("Remove this end product from the bundle. The "
                              "window reopens with the remaining ones; save "
                              "the plan to keep it."))
            raus.clicked.connect(lambda _c=False, _t=tid: self._multi_ende_entfernen(_t))
            _wr = QWidget(); _hr = QHBoxLayout(_wr)
            _hr.setContentsMargins(4, 0, 4, 0); _hr.addWidget(raus)
            _hr.setAlignment(Qt.AlignHCenter)
            tbl.setCellWidget(r, 10, _wr)
            w.update({"menge": menge, "me": me, "te": te, "obpc": obpc,
                      "runs": runs, "deckel": _deckel, "raus": raus})

            def _breiten():
                """Deckel nachziehen - ERST JETZT kennt die Box ihre Groesse.

                Beim Bauen ist sie noch nicht im Layout und hat noch keinen
                Wert; ihr sizeHint war hier 104 px und nach dem Fuellen 120.
                Ein einmal gesetzter Deckel schnitt sie also ab - genau das,
                was der Nutzer sah ("ME/TE abgeschnitten, kann man nicht
                lesen/tippen"). Dieselbe Falle wie adjustSize() ohne Layout.
                """
                for _wx, _brx in _deckel:
                    _soll = _wx.sizeHint().width()
                    if _wx is menge:
                        # DIE MENGE BRAUCHT PLATZ FUER IHRE ZAHL, NICHT FUER
                        # DIE OBERGRENZE (Nutzer-Messung 24.09.2026: die
                        # Spalte war auf seinem Rechner 194 px breit). Der
                        # sizeHint einer Box richtet sich nach ihrem
                        # groessten Wert - hier 100'000'000, also elf
                        # Zeichen, die dort nie stehen. Gemessen wird die
                        # Zahl, die WIRKLICH drinsteht, plus zwei Ziffern
                        # Reserve; der Rahmen samt Pfeilen kommt aus der
                        # Differenz zum sizeHint und bleibt damit dem Thema
                        # ueberlassen.
                        _fmx = _wx.fontMetrics()
                        _rahmen = max(0, _wx.sizeHint().width()
                                      - _fmx.horizontalAdvance(
                                          _wx.textFromValue(_wx.maximum())))
                        _soll = (_fmx.horizontalAdvance(
                            _wx.textFromValue(_wx.value()) + "00") + _rahmen)
                    _wx.setMaximumWidth(max(_brx, _soll))

            w["breiten"] = _breiten

            def _sperren():
                """ME/TE nur frei, wenn KEINE Invention regiert."""
                _frei = not _invention_regiert(tid)
                me.setEnabled(_frei); te.setEnabled(_frei)
                runs.setEnabled(bool(obpc.isChecked()))
                if not _frei:
                    me.setToolTip(t(
                        "Comes from the invention (2 % base plus decryptor) \u2013 an "
                        "invented copy has no researched ME. Tick \u201eOwn BPC\u201c to "
                        "enter your own copy's value."))
                    te.setToolTip(me.toolTip())
                else:
                    me.setToolTip(t("Material efficiency of YOUR blueprint copy "
                                    "of this end product (0\u201310 %)."))
                    te.setToolTip(t("Time efficiency of YOUR blueprint copy of "
                                    "this end product (0\u201320 %)."))
            w["sperren"] = _sperren

            def _menge_geaendert(v, _tid=tid):
                _neu = []
                for _a, _b in (getattr(self, "_bd_buendel_enden", None) or []):
                    _neu.append((int(_a), int(v) if int(_a) == int(_tid) else int(_b)))
                self._bd_buendel_enden = _neu
                self._bd_plan_cache = None      # Menge geaendert -> Plan neu
                _anstoss.start()

            def _me_geaendert(v, _tid=tid):
                self._bd_me_je_ende = dict(getattr(self, "_bd_me_je_ende", None) or {})
                self._bd_me_je_ende[int(_tid)] = float(v)
                self._multi_me_te_auffrischen()
                self._bd_plan_cache = None
                _anstoss.start()

            def _te_geaendert(v, _tid=tid):
                self._bd_te_je_ende = dict(getattr(self, "_bd_te_je_ende", None) or {})
                self._bd_te_je_ende[int(_tid)] = float(v)
                self._multi_me_te_auffrischen()
                self._bd_plan_cache = None
                _anstoss.start()

            def _obpc_geaendert(an, _tid=tid):
                self._bd_own_bpc_je_ende = dict(
                    getattr(self, "_bd_own_bpc_je_ende", None) or {})
                self._bd_own_bpc_je_ende[int(_tid)] = bool(an)
                if an:
                    # Das Feld "Runs/BPC" zeigt schon eine Zahl - die gilt
                    # ab jetzt (s. _multi_bp_je_ende, Einherji-Befund).
                    _r0 = dict(getattr(self, "_bd_own_bpc_runs_je_ende", None) or {})
                    if int(_r0.get(int(_tid), 0) or 0) < 1:
                        _r0[int(_tid)] = max(1, int(runs.value()))
                        self._bd_own_bpc_runs_je_ende = _r0
                # Die Uebersetzung in inv_manual_override MUSS hier passieren:
                # `_bd_opts` ueberlebt den rebuild, und der Rechenlauf-Zweig
                # in open_build_detail laeuft nur beim Oeffnen.
                try:
                    self._multi_opts_je_ende(self._bd_opts,
                                             getattr(self, "_bd_recipes", None))
                except Exception as _oe:
                    self._log_exception("Multi-Bauplan: Eigene BPC je Ende", str(_oe))
                self._multi_me_te_auffrischen()
                self._bd_plan_cache = None
                self._bd_tree_cache = None
                _sperren()
                _anstoss.start()

            def _runs_geaendert(v, _tid=tid):
                self._bd_own_bpc_runs_je_ende = dict(
                    getattr(self, "_bd_own_bpc_runs_je_ende", None) or {})
                self._bd_own_bpc_runs_je_ende[int(_tid)] = int(v)
                _anstoss.start()

            menge.valueChanged.connect(_menge_geaendert)
            me.valueChanged.connect(_me_geaendert)
            te.valueChanged.connect(_te_geaendert)
            obpc.toggled.connect(_obpc_geaendert)
            runs.valueChanged.connect(_runs_geaendert)
            if not _kann_invention(tid):
                # KORRIGIERT (20.09.2026, beim Ansehen der Karte aufgefallen):
                # hier stand `setEnabled(False)` mit der Begruendung, bei einem
                # T1-Ende gaebe es keine Invention zum Abwaehlen. Das stimmt,
                # der Haken ist trotzdem NICHT wirkungslos: er unterscheidet
                # "ich habe die BPO, unbegrenzt" von "ich habe eine Kopie mit
                # N Runs" - und genau daraus kommen Kopienzahl und der
                # Runplaner-Deckel (`_multi_bp_je_ende`). Ausgegraut war er
                # eine Stellschraube, die man BRAUCHT und nicht erreicht.
                obpc.setToolTip(t(
                    "This end product is not invented. On: you build it from a "
                    "blueprint COPY with a limited number of runs (below). Off: "
                    "you own the original and can run it as often as you like."))
            return w

        def _werte_setzen(w, tid, bpd=None):
            """Felder aus dem Zustand fuellen, OHNE einen rebuild auszuloesen.

            `bpd` ist die Blaupausen-Lage dieses Endes (`_multi_bp_je_ende`);
            damit zeigen auch die GESPERRTEN Felder die Zahlen, mit denen
            wirklich gerechnet wird - sonst stuende in "Runs/BPC" eine 1,
            waehrend die Spalte daneben "40 x 10 Runs" meldet."""
            _me = (getattr(self, "_bd_me_je_ende", None) or {}).get(int(tid))
            _te = (getattr(self, "_bd_te_je_ende", None) or {}).get(int(tid))
            _ob = bool((getattr(self, "_bd_own_bpc_je_ende", None) or {}).get(int(tid)))
            _ru = int((getattr(self, "_bd_own_bpc_runs_je_ende", None) or {}).get(
                int(tid), 0) or 0)
            _mg = 0
            for _a, _b in (getattr(self, "_bd_buendel_enden", None) or []):
                if int(_a) == int(tid):
                    _mg = int(_b)
            # ME/TE unter Invention: den ECHTEN Wert zeigen, nicht 0 -
            # sonst stuende im gesperrten Feld eine Zahl, die nichts mit der
            # Rechnung zu tun hat (Regel: keine erfundenen Zahlen anzeigen).
            if _invention_regiert(tid):
                _rec = getattr(self, "_bd_recipes", None)
                _opt = getattr(self, "_bd_opts", None) or {}
                _bp = (getattr(_rec, "product_to_bp", None) or {}).get(int(tid))
                _inv = (getattr(_rec, "invention_for_bpc", None) or {}).get(
                    _bp[0]) if _bp else None
                try:
                    _o = industry.invention_outcome(
                        _inv[1], _inv[2],
                        industry.decryptor_fuer_bp(_bp[0], _opt)) if _inv else None
                except Exception:
                    _o = None
                if _o is not None:
                    # ME UND TE der erfundenen Kopie - beide aus DERSELBEN
                    # Rechnung wie die Kosten, nicht aus dem leeren Feld.
                    _me, _te = _o["me_pct"], _o["te_pct"]
            # "Runs/BPC" zeigt, WOMIT GERECHNET WIRD - fuer die erfundene
            # Kopie wie fuer die eigene. Vorher stand hier `not _ob`: bei
            # "Eigene BPC" ohne getippten Wert zeigte das Feld seine 1,
            # waehrend die Spalte daneben "1 x 52 runs" meldete (Nutzer-
            # Befund 21.09.2026, zwei Zahlen fuer dieselbe Sache). Jetzt
            # steht dort die Kopiengroesse aus dem Blaupausen-Cache; tippt
            # der Nutzer eine eigene, gewinnt seine (eigene_kopie_lage).
            if bpd and int(bpd.get("runs", 0) or 0) >= 1:
                _ru = int(bpd["runs"])
            for _w, _v in ((w["menge"], max(1, _mg)), (w["me"], int(_me or 0)),
                           (w["te"], int(_te or 0)), (w["runs"], max(1, _ru))):
                _w.blockSignals(True); _w.setValue(int(_v)); _w.blockSignals(False)
            w["obpc"].blockSignals(True); w["obpc"].setChecked(_ob)
            w["obpc"].blockSignals(False)
            w["sperren"]()
            _br = w.get("breiten")
            if _br is not None:
                _br()

        def _refresh(plan):
            je = industry.buendel_kosten_je_ende(plan or {})
            _bp_je_ende = self._multi_bp_je_ende(plan) or {}
            pm = getattr(self, "_bd_pricemap", None) or {}
            hub_je = getattr(self, "_bd_hub_sell_je_ende", None) or {}
            reihen = sorted(je.items(), key=lambda kv: names.get(kv[0], str(kv[0])))
            if tbl.rowCount() != len(reihen) or not self._bd_multi_zeilen:
                tbl.setRowCount(0)
                self._bd_multi_zeilen = {}
                for tid, _k in reihen:
                    r = tbl.rowCount(); tbl.insertRow(r)
                    _it0 = QTableWidgetItem(names.get(tid, f"#{tid}"))
                    _px0 = _ende_icon(tid)
                    if _px0 is not None and not _px0.isNull():
                        _it0.setIcon(QIcon(_px0))
                    tbl.setItem(r, 0, _it0)
                    self._bd_multi_zeilen[int(tid)] = _zeile_bauen(r, int(tid))
            # FUER DEN GEWINN-NACHZUG (der laeuft erst, wenn Gebuehren,
            # Fracht und Extrakosten gerechnet sind - siehe rebuild()).
            self._bd_multi_je = dict(je)
            self._bd_multi_reihen = [int(tid) for tid, _k in reihen]
            _unklar = self._multi_unklare_enden(plan)
            _ohne_dec = self._multi_enden_ohne_decryptor()
            _wl = getattr(self, "_bd_multi_warn_lbl", None)
            if _wl is not None:
                _warn_teile = []
                if _ohne_dec:
                    _warn_teile.append(t(
                        "\u26a0 No decryptor chosen yet for: {items}. Invention tab: "
                        "pick one or press \u201eBest Decryptor for all "
                        "Blueprints\u201c; building from your own copy? Tick "
                        "\u201eOwn BPC\u201c and enter its ME/TE.").format(
                            items=", ".join(names.get(tid, f"#{tid}")
                                            for tid in _ohne_dec)))
                if _unklar:
                    _warn_teile.append(t(
                        "\u26a0 Unclear whether you invent or build from your own "
                        "copies: {items}. The plan INVENTS these (datacores, "
                        "attempts) \u2013 tick \u201eOwn BPC\u201c if you build "
                        "from the copies in your hangar.").format(
                            items=", ".join(
                                t("{name} ({n} own copies)").format(
                                    name=names.get(tid, f"#{tid}"), n=n)
                                for tid, n in _unklar)))
                _wl.setText("<br>".join(_warn_teile))
                _wl.setVisible(bool(_warn_teile))
            for r, (tid, k) in enumerate(reihen):
                w = self._bd_multi_zeilen.get(int(tid))
                if w is not None:
                    _werte_setzen(w, int(tid), _bp_je_ende.get(int(tid)))
                # KOPIEN JE ENDE (Schritt 4b): "3 \u00d7 10 Runs" - dieselbe
                # Rechnung, die auch den Runplaner deckelt. Ohne eigene oder
                # erfundene Kopie steht hier "\u221e" (BPO-Annahme wie bisher).
                _bpd = _bp_je_ende.get(int(tid))
                if _bpd:
                    _kop = NumericItem(
                        # NUR ZAHLEN (Nutzer-Messung 24.09.2026: die Spalte
                        # war auf seinem Rechner 146 px breit - das Wort
                        # "runs" machte aus einer Zahlenspalte eine
                        # Textspalte). Was es bedeutet, steht im Tooltip.
                        "{n} \u00d7 {r}".format(n=_bpd["copies"], r=_bpd["runs"]),
                        _bpd["copies"])
                    _kop.setToolTip(t(
                        "How many blueprint copies of this end product the plan "
                        "needs, and how many runs each one carries. The run "
                        "planner never puts more than that into one job."))
                elif (getattr(self, "_bd_own_bpc_je_ende", None) or {}).get(int(tid)):
                    # EIGENE KOPIE, GROESSE UNBEKANNT: frueher wurde hier
                    # "alle Runs sind EINE Kopie" angenommen - daraus wurde
                    # EIN Job auf EINEM Slot (Nutzer: 51 Tage). Jetzt wird
                    # nichts geraten, und der Tooltip sagt, was fehlt.
                    _kop = NumericItem("\u221e", 0)
                    _kop.setToolTip(t(
                        "Own copy \u2013 but how many runs one copy carries is "
                        "unknown. Load your blueprints or type \u201eRuns/BPC\u201c, "
                        "otherwise the run planner cannot limit the jobs."))
                else:
                    _kop = NumericItem("\u221e", 0)
                    _kop.setToolTip(t("Assumed: you own the blueprint (unlimited "
                                      "runs) \u2013 no invention, no copies needed."))
                tbl.setItem(r, 6, _kop)
                tbl.setItem(r, 7, NumericItem(isk(k["je_stueck"], suffix=False),
                                              k["je_stueck"]))
                sell = hub_je.get(tid) or pm.get(tid)
                tbl.setItem(r, 8, NumericItem(
                    isk(sell, suffix=False) if sell else "\u2014", sell or 0.0))
                # DIE GEWINN-SPALTE FUELLT _gewinn_nachziehen - hier steht
                # noch kein Wert, weil Verkaufsgebuehren und Zuschlaege an
                # dieser Stelle im rebuild() noch gar nicht gerechnet sind.
                # Lieber ein Strich als eine Zahl, die etwas anderes meint
                # als ihre Ueberschrift.
                if tbl.item(r, 9) is None:
                    tbl.setItem(r, 9, NumericItem("\u2014", 0.0))
            # Hoehe aus den echten Zeilen (geschaetzte 34 px liessen unter der
            # letzten Zeile einen leeren Streifen stehen) - GEDECKELT auf
            # ENDEN_SICHTBAR Zeilen, darueber laeuft die Tabelle mit eigener
            # Bildlaufleiste (Nutzer 26.09.2026, elf Enden: "wir koennen
            # nicht scrollen ... maximal 5 Endprodukte, dafuer eine
            # Scrollleiste rechts, so wie unten im Planer selbst").
            _zh = tbl.rowHeight(0) if tbl.rowCount() else 30
            _n_sicht = max(1, min(tbl.rowCount(), self.ENDEN_SICHTBAR))
            tbl.setFixedHeight(tbl.horizontalHeader().height()
                               + (_zh or 30) * _n_sicht
                               + 2 * tbl.frameWidth() + 2)
            self._multi_enden_spalten(tbl)

        def _gewinn_nachziehen(satz=0.0, fracht=0.0, extra=0.0, gesamt=None):
            """Gewinn je Endprodukt NETTO - damit die Spalte dasselbe meint
            wie der grosse "Total profit" darunter.

            Verkaufsgebuehren (Sales Tax + Broker) sind ein PROZENTSATZ auf
            den Verkaufspreis, lassen sich also je Ende exakt abziehen.
            Fracht und Extrakosten sind Pauschalen fuer den ganzen Plan; sie
            werden nach dem KOSTENANTEIL des Endes verteilt - dieselbe
            Aufteilung, mit der buendel_kosten_je_ende die Gesamtkosten
            zerlegt. Damit trifft die Summe der Spalte den Gesamtgewinn."""
            from ..sprache import t as _txt
            je = getattr(self, "_bd_multi_je", None) or {}
            reihen = getattr(self, "_bd_multi_reihen", None) or []
            lbl = getattr(self, "_bd_multi_gewinn_lbl", None)
            if not je or not reihen:
                return None
            pm = getattr(self, "_bd_pricemap", None) or {}
            hub_je = getattr(self, "_bd_hub_sell_je_ende", None) or {}
            _kges = sum(float(k.get("gesamt") or 0.0) for k in je.values())
            _zuschlag = float(fracht or 0.0) + float(extra or 0.0)
            # AUF DIE GROSSE ZAHL DARUNTER ABGLEICHEN (Nutzer 26.09.2026,
            # Screenshot: Summe der Enden 2'828'364'637, "Total profit"
            # 2'838'554'463 - 10'189'826 auseinander, ebenso Build cost gegen
            # Summe Kosten/Stk x Menge). Ursache: die Aufteilung je Ende kommt
            # aus dem Plan (Preise aus dem Scan), die Kopfzeile rechnet nach
            # "Recalculate" mit dem ORDERBUCH (`mat_ladder`). Der Unterschied
            # wird nach Kostenanteil verteilt - derselbe Schluessel wie Fracht
            # und Extrakosten -, damit Spalte und Kopfzeile dieselbe Zahl sind.
            _skala = ((float(gesamt) / _kges) if (gesamt is not None and _kges > 0
                                                   and float(gesamt) > 0) else 1.0)
            summe, fehlt = 0.0, 0
            for r, tid in enumerate(reihen):
                k = je.get(tid) or je.get(int(tid)) or {}
                if r >= tbl.rowCount():
                    break
                sell = hub_je.get(tid) or pm.get(tid)
                if not sell or not k:
                    tbl.setItem(r, 9, NumericItem("\u2014", 0.0))
                    fehlt += 1
                    continue
                menge = max(1, int(k.get("menge") or 1))
                anteil = (float(k.get("gesamt") or 0.0) / _kges) if _kges else 0.0
                _je_st = float(k.get("je_stueck") or 0.0) * _skala
                # Kosten/Stk-Spalte mit derselben Zahl, die hier abgezogen wird.
                tbl.setItem(r, 7, NumericItem(isk(_je_st, suffix=False), _je_st))
                g = (float(sell) * (1.0 - float(satz or 0.0))
                     - _je_st
                     - (_zuschlag * anteil / menge))
                summe += g * menge
                it = NumericItem(isk(g, suffix=False), g)
                it.setForeground(QColor(theme.GREEN if g >= 0 else theme.RED))
                it.setToolTip(_txt(
                    "Sale price minus sales tax and broker fee ({pct} %), minus "
                    "this product's share of the build cost and of freight and "
                    "extra costs. Quantity \u00d7 this column, summed over all end "
                    "products, is the total profit above.").format(
                        pct=f"{float(satz or 0.0) * 100:.2f}"))
                tbl.setItem(r, 9, it)
            if lbl is not None:
                if fehlt:
                    lbl.setText(_txt(
                        "{n} end product(s) have no sale price \u2013 the sum is "
                        "therefore incomplete.").format(n=fehlt))
                else:
                    lbl.setText(_txt(
                        "Sum over all end products: {v} ISK \u2013 this is the "
                        "total profit above.").format(
                            v=isk(summe, suffix=False)))
            # DIE SPALTEN NACHMESSEN: die Gewinn-Zahl entsteht erst hier -
            # beim Fuellen stand noch ein Strich, und die Spalte war so
            # schmal wie der Strich (Nutzer 26.09.2026: "Profit/U...").
            self._multi_enden_spalten(tbl)
            return summe

        self._bd_multi_refresh = _refresh
        self._multi_gewinn_nachziehen = _gewinn_nachziehen
        return _refresh

    def _multi_hub_sell_job(self, enden, key):
        """Verkaufspreise ALLER Enden am gewaehlten Verkaufs-Hub (fuer
        _fetch_hub_sell_price beim Buendel). Rueckgabe {tid: preis}; Enden
        ohne Order fehlen."""
        from .. import hubs
        aus = {}
        if isinstance(key, tuple) and key and key[0] == "struct":
            sid = int(key[1])
            cid = None
            for f in self._market_structures():
                if f.get("structure_id") == sid:
                    cid = f.get("character_id")
                    break
            if not cid:
                return aus
            d = esi.fetch_structure_orders(self.settings.get("client_id", ""),
                                           int(cid), sid) or {}
            for tid, _q in enden:
                p = (d.get(int(tid)) or {}).get("sell_min")
                if p:
                    aus[int(tid)] = float(p)
            return aus
        for k, _lbl, region, station in hubs.NPC_HUBS:
            if k == key:
                for tid, _q in enden:
                    lad = esi.fetch_type_orders(int(tid), station, region)
                    s = (lad or {}).get("sell") or []
                    if s:
                        aus[int(tid)] = float(s[0][0])
                break
        return aus
