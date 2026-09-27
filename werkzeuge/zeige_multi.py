"""Schreibt auf, wie deine MULTI-BAUPLAENE wirklich rechnen (1.0.9).

WOZU (20.09.2026): der letzte offene Test am echten SDE ist ein Buendel mit
zwei Enden verschiedener Art - eines ueber INVENTION, eines mit EIGENER
BPC. Genau dort greifen ME/TE je Ende, die Zahl der Kopien und der
Runs-Deckel des Runplaners ineinander, und genau das laesst sich am
Bildschirm schlecht nachrechnen: die Karte zeigt Ergebnisse, nicht die
Zwischenwerte.

Dieser Bericht zeigt je Endprodukt, WELCHE ME gilt und WOHER sie kommt.

WAS ER NICHT KANN, damit keine falsche Sicherheit entsteht: DIESER BERICHT
laeuft ohne das Fenster, also ohne deine Strukturwahl - er sieht Rig- und
Strukturboni nicht und den Bestand auch nicht.

DAS HEISST NICHT, DASS DER MULTI-BAUPLAN SIE NICHT RECHNET. Er rechnet sie
voll, je Endprodukt, in derselben Drei-Faktoren-Formel wie ein Einzelplan
(Basis-ME x Rig-ME x Rollenbonus des Engineering Complexes,
`industry.me_invented_pct`; die Strukturwahl laeuft je Stufe und kennt die
Buendel-Enden). Nur dieser Bericht hier kann sie nicht nachschlagen.

Die ME-Werte unten sind deshalb die REINEN Invention- bzw. Blaupausen-Werte;
im Bauplan stehen sie hoeher. Verglichen wird hier nur, was sich ohne
Fenster sauber vergleichen laesst - und das ist genau die Frage des Tests:
bekommt jedes Ende SEINE eigene ME, oder rechnen beide mit derselben?

VORAUSSETZUNG: einmal "Load recipes" gedrueckt, und mindestens ein
Multi-Bauplan in "Meine Bauplaene" gespeichert.

AUFRUF:  werkzeuge\\zeige_multi.bat  doppelklicken
         (oder  python werkzeuge\\zeige_multi.py)

Danach liegt  berichte\\multi_bericht.txt  bereit. Die hochladen. Deine
Daten werden nur GELESEN, nichts veraendert.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))   # Projektwurzel

from eve_trader import config, industry, store   # noqa: E402

FASSUNG = 2


def _name(names, tid):
    return names.get(int(tid)) or f"#{tid}"


def _mz(n, ein, mehr):
    """„1 Kopie" / „5 Kopien" - er liest den Bericht, also stimmt die Mehrzahl."""
    return f"{n} {ein if int(n) == 1 else mehr}"


def _ist_multi(p):
    try:
        return int((p or {}).get("type_id", 0) or 0) == industry.BUENDEL_ID
    except (TypeError, ValueError):
        return False


def _bp_von(recipes, tid):
    """(blueprint_id, aktivitaet, stueck_je_run) oder None."""
    return (getattr(recipes, "product_to_bp", None) or {}).get(int(tid))


def _erfindbar(recipes, bp_id):
    """(t1_bp, base_runs, base_prob, datacores) oder None."""
    return (getattr(recipes, "invention_for_bpc", None) or {}).get(bp_id)


def dec_liste():
    """{Name: (prob_mult, run_mod, me_mod, te_mod, type_id)} aus der SDE.

    Der gespeicherte Bauplan merkt sich je Blaupause nur den NAMEN des
    Decryptors (`decryptor_map`); die Zahlen dahinter holt das Fenster mit
    `_decryptor_list()` aus der SDE. Dessen Rueckfall-Liste wird hier
    ABSICHTLICH NICHT nachgebaut - neun Zahlenpaare ein zweites Mal im Code
    waeren eine zweite Wahrheit. Fehlen die SDE-Daten, sagt der Bericht das.
    """
    try:
        sde = industry.load_decryptors()
    except Exception:
        sde = []
    aus = {config.KEIN_DECRYPTOR: (1.0, 0, 0, 0, None)}
    for d in sde or []:
        aus[d.get("name") or ""] = (d.get("prob_mult", 1.0), int(d.get("run_mod") or 0),
                                    int(d.get("me_mod") or 0), int(d.get("te_mod") or 0),
                                    d.get("type_id"))
    return aus


def opts_fuer_plan(p, settings, decs):
    """(opts fuer decryptor_fuer_bp, {bp_id: Name}) - wie `_resolve_inv_decryptor_map`.

    Je Blaupause der Name aus dem Plan; fuer alles andere die globale
    Einstellung `bau_decryptor` - genau die Reihenfolge, die
    `industry.decryptor_fuer_bp` im Programm vorfindet.
    """
    namen, karte = {}, {}
    for k, v in (p.get("decryptor_map") or {}).items():
        try:
            bp = int(k)
        except (TypeError, ValueError):
            continue
        namen[bp] = v
        if v in decs:
            karte[bp] = decs[v]
    global_name = (settings or {}).get("bau_decryptor") or config.KEIN_DECRYPTOR
    if global_name not in decs:
        global_name = f"{global_name} - nicht in der SDE, also ohne Decryptor"
    gd = decs.get(global_name, (1.0, 0, 0, 0, None))
    opts = {"inv_decryptor_map": karte, "inv_prob_mult": gd[0], "inv_run_mod": gd[1],
            "inv_me_mod": gd[2], "inv_te_mod": gd[3], "inv_decryptor_id": gd[4]}
    return opts, namen, global_name


def _zeilen_fuer_plan(p, recipes, names, zeile, settings, decs):
    """Einen Multi-Plan aufschluesseln. `zeile` ist die Ausgabefunktion."""
    enden = [(int(a), int(b)) for a, b in (p.get("enden") or [])]
    zeile(f"  Endprodukte: {len(enden)}")
    me_je = {int(k): v for k, v in (p.get("me_je_ende") or {}).items()}
    te_je = {int(k): v for k, v in (p.get("te_je_ende") or {}).items()}
    ob_je = {int(k): bool(v) for k, v in (p.get("own_bpc_je_ende") or {}).items()}
    obr_je = {int(k): int(v or 0) for k, v in (p.get("own_bpc_runs_je_ende") or {}).items()}
    opts, dec_namen, global_dec = opts_fuer_plan(p, settings, decs)
    gesehen_me = {}
    for tid, menge in enden:
        zeile("")
        zeile(f"  --- {_name(names, tid)}  (type_id {tid}) x {menge}")
        bp = _bp_von(recipes, tid)
        if not bp:
            zeile("      KEIN REZEPT in der SDE - dieses Ende kann der Plan "
                  "nicht bauen. (Load recipes gedrueckt?)")
            continue
        bp_id = bp[0]
        inv = _erfindbar(recipes, bp_id)
        eigene = ob_je.get(tid, False)
        zeile(f"      Blaupause {bp_id} · {bp[2]} Stueck je Run · "
              f"{'ERFINDBAR (T2)' if inv else 'nicht erfindbar (T1/BPO)'}")
        zeile(f"      gespeichert: ME {me_je.get(tid, 0)} · TE {te_je.get(tid, 0)}"
              f" · Eigene BPC: {'JA' if eigene else 'nein'}"
              + (f" · Runs je BPC: {obr_je.get(tid, 0)}" if eigene else ""))
        if eigene:
            quelle = f"DEINE eigene Kopie: ME {me_je.get(tid, 0)}"
            runs_bpc = max(1, obr_je.get(tid, 0) or 1)
            zeile(f"      -> gerechnet wird mit {quelle}")
            runs_noetig = math.ceil(menge / max(1, bp[2]))
            zeile(f"      -> eine Kopie traegt {_mz(runs_bpc, 'Run', 'Runs')}; "
                  f"fuer {menge} Stueck sind das "
                  f"{_mz(runs_noetig, 'Run', 'Runs')} = "
                  + _mz(math.ceil(runs_noetig / runs_bpc), "Kopie", "Kopien"))
            gesehen_me[tid] = ("eigene BPC", float(me_je.get(tid, 0) or 0))
        elif inv:
            dec = industry.decryptor_fuer_bp(bp_id, opts)
            erg = industry.invention_outcome(inv[1], inv[2], dec)
            _dn = dec_namen.get(bp_id)
            if _dn is None:
                zeile(f"      Decryptor: {global_dec}  (globale Einstellung - "
                      "diese Blaupause hat keine eigene Wahl)")
            elif _dn in decs:
                zeile(f"      Decryptor: {_dn}")
            else:
                zeile(f"      Decryptor: {_dn} - ACHTUNG: dieser Name steht "
                      "nicht in deiner SDE. Gerechnet wird hier mit der "
                      f"globalen Einstellung ({global_dec}).")
            zeile(f"      -> Invention: ME {erg['me_pct']} % · TE {erg['te_pct']} % · "
                  f"{_mz(erg['runs'], 'Run', 'Runs')} je Kopie · Chance "
                  f"{erg['prob'] * 100:.1f} %")
            runs_noetig = math.ceil(menge / max(1, bp[2]))
            zeile(f"      -> fuer {menge} Stueck: "
                  f"{_mz(runs_noetig, 'Run', 'Runs')} = "
                  + _mz(math.ceil(runs_noetig / max(1, erg['runs'])),
                        "Kopie", "Kopien")
                  + " (der Runplaner darf je Job hoechstens "
                  + _mz(erg['runs'], 'Run', 'Runs') + " fahren)")
            gesehen_me[tid] = ("Invention", float(erg["me_pct"]))
        else:
            zeile("      -> T1/BPO: ME aus deiner Blaupause, keine Kopien-Grenze")
            gesehen_me[tid] = ("T1/BPO", float(me_je.get(tid, 0) or 0))
    # DIE KERNFRAGE DES TESTS
    zeile("")
    arten = {a for a, _m in gesehen_me.values()}
    if len(gesehen_me) >= 2 and len(arten) >= 2:
        zeile("  PRUEFUNG: dieses Buendel mischt " + " und ".join(sorted(arten))
              + " - genau der Fall, um den es geht.")
        for tid, (art, me) in gesehen_me.items():
            zeile(f"    {_name(names, tid)}: rechnet mit ME {me:g} % ({art})")
        werte = {round(m, 6) for _a, m in gesehen_me.values()}
        if len(werte) == 1:
            zeile("    ACHTUNG: alle Enden rechnen mit DERSELBEN ME. Das kann "
                  "stimmen (gleiche Werte), waere aber auch genau das "
                  "Fehlerbild, das im September behoben wurde - bitte melden.")
        else:
            zeile("    -> verschiedene ME je Ende. So soll es sein.")
    elif len(gesehen_me) >= 2:
        zeile("  PRUEFUNG: alle Enden sind von derselben Art (" +
              ", ".join(sorted(arten)) + "). Fuer den offenen Test fehlt ein "
              "Buendel, das INVENTION und EIGENE BPC mischt.")
    else:
        zeile("  PRUEFUNG: nur "
              + _mz(len(gesehen_me), "baubares Endprodukt", "baubare Endprodukte")
              + " - zu wenig fuer eine Aussage.")


def main():
    wurzel = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ziel_ordner = os.path.join(wurzel, "berichte")
    os.makedirs(ziel_ordner, exist_ok=True)
    ziel = os.path.join(ziel_ordner, "multi_bericht.txt")
    zeilen = []

    def zeile(s=""):
        zeilen.append(str(s))
        print(s, flush=True)

    zeile(f"MULTI-BAUPLAN-BERICHT (Fassung {FASSUNG})")
    zeile("=" * 60)
    zeile("Dieser Bericht laeuft OHNE das Bauplan-Fenster und sieht deshalb")
    zeile("keine Rig- und Strukturboni. Der Multi-Bauplan selbst rechnet sie")
    zeile("voll mit, je Endprodukt - die ME unten sind nur die reinen Basis-")
    zeile("werte, im Bauplan stehen sie hoeher.")
    zeile("")
    settings = config.load_settings()
    plans = settings.get("bau_saved_plans", []) or []
    multis = [p for p in plans if _ist_multi(p)]
    zeile(f"Gespeicherte Bauplaene: {len(plans)} · davon Multi: {len(multis)}")
    if not industry.sde_ready():
        zeile("")
        zeile("ABBRUCH: keine Rezeptdaten. Im Tool einmal „Load recipes\" "
              "druecken und den Bericht danach neu erzeugen.")
    elif not multis:
        zeile("")
        zeile("Kein Multi-Bauplan gespeichert. Im Tool: „Multi build plan\" "
              "anklicken, zwei Plaene anhaken, speichern - dann diesen "
              "Bericht neu erzeugen.")
    else:
        recipes = industry.recipes_cached()
        decs = dec_liste()
        if len(decs) <= 1:
            zeile("(Keine Decryptor-Daten in der SDE - erfundene Enden werden "
                  "hier OHNE Decryptor gerechnet. Im Programm greift dann die "
                  "Rueckfall-Liste, die Zahlen unten koennen also abweichen.)")
        alle_tids = sorted({int(a) for p in multis for a, _b in (p.get("enden") or [])})
        try:
            names = store.cached_names(alle_tids)
        except Exception as e:                       # pragma: no cover
            names = {}
            zeile(f"(Namen nicht lesbar: {e})")
        for p in multis:
            zeile("")
            zeile("-" * 60)
            zeile(f"MULTI-BAUPLAN: {p.get('label') or '(ohne Namen)'}")
            zeile(f"  Quellen (Einzelplaene): {p.get('quellen') or []}")
            zeile(f"  eingefroren: {'ja' if p.get('frozen') else 'nein'}"
                  f" · reserviert: {'ja' if p.get('reserve') else 'nein'}")
            try:
                _zeilen_fuer_plan(p, recipes, names, zeile, settings, decs)
            except Exception as e:                   # pragma: no cover
                import traceback
                zeile(f"  FEHLER beim Aufschluesseln: {type(e).__name__}: {e}")
                zeile("  " + traceback.format_exc().splitlines()[-3].strip())
    zeile("")
    zeile("=" * 60)
    zeile("Bitte diese Datei hochladen.")
    with open(ziel, "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")
    print(f"\nGeschrieben: {ziel}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
