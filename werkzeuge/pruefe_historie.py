"""WELCHE ITEMS HABEN KEINE PREISHISTORIE - UND WARUM? (emm898)

WOZU: Nutzer 11.11.2026, nach den neuen Ladezeit-Zaehlern: "Items ohne
historie sind sowieso ITems die nicht gemacht sind zum traden oder?"
Sein Portfolio-Lauf holt in JEDEM Durchgang dieselben 55 Historien neu
(held=2186, hist-cached=2131, hist-fetched=55). Die kosten Zeit und
ESI-Budget - im Portfolio UND in jedem Daytrade-/Swing-Scan, denn alle
gehen durch `scanner.history_cached`.

DIE FRAGE, DIE DIESER BERICHT BEANTWORTET: sind das wirklich Items ohne
Handel (BPCs, Abyssals - dann kann MoMa sie laenger ruhen lassen), oder
sind es FEHLGESCHLAGENE Abrufe (dann waere laenger ruhen lassen ein
Fehler, der echte Daten versteckt)? Der Kommentar in `history_cached`
sagt ausdruecklich "or (more often) a fetch that failed" - genau das
gilt es zu pruefen, bevor irgendetwas geaendert wird.

WIE UNTERSCHIEDEN WIRD, ohne zu raten: MoMa schreibt beide Faelle
verschieden in die Datenbank.
  * `save_history` (Abruf GEGLUECKT, auch mit leerer Antwort) setzt
    `updated_at = jetzt`.
  * `touch_history` (Abruf GESCHEITERT) datiert um 20 Stunden zurueck,
    damit es bald wieder versucht wird.
Ein Zeitstempel, der juenger als 20 Stunden ist, kann also nur von
einem geglueckten Abruf stammen.

ZUR SICHERHEIT WIRD NACHGEFRAGT: fuer bis zu `--max` Items holt der
Bericht die Historie EINMAL direkt von ESI und schreibt hin, was
zurueckkam - leer, Daten, oder ein Fehler. Das ist die Antwort aus
erster Hand statt aus einer Heuristik.

NUR LESEN: ausser den ESI-Abfragen aendert dieser Bericht nichts.

AUFRUF: werkzeuge\\pruefe_historie.bat doppelklicken, danach
`berichte\\historie_bericht.txt` hochladen.
"""
import os
import sys
import time

_WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _WURZEL)

from eve_trader import config, esi, industry, store   # noqa: E402

FASSUNG = 1
MAX_ESI = 60          # so viele fragen wir zur Probe wirklich bei ESI nach


def _zahl(n):
    return f"{n:,}".replace(",", "'")


def main():
    zeilen = []

    def p(s=""):
        zeilen.append(s)
        print(s)

    region = config.FORGE_REGION
    p(f"HISTORIE-PRUEFUNG Fassung {FASSUNG} - "
      f"{time.strftime('%d.%m.%Y %H:%M')}")
    p(f"Region: {region} (The Forge)")
    p()

    # ---- WAS LIEGT IN DER DATENBANK? -----------------------------------
    with store._conn() as c:
        _meta = c.execute(
            "SELECT type_id, updated_at FROM history_meta WHERE region=?",
            (region,)).fetchall()
        _mit_zeilen = {int(r["type_id"]) for r in c.execute(
            "SELECT DISTINCT type_id FROM history WHERE region=?",
            (region,)).fetchall()}
    jetzt = time.time()
    leer = [(int(r["type_id"]), float(r["updated_at"] or 0))
            for r in _meta if int(r["type_id"]) not in _mit_zeilen]
    p(f"Items mit Zeitstempel: {_zahl(len(_meta))}")
    p(f"  davon MIT Historie:  {_zahl(len(_meta) - len(leer))}")
    p(f"  davon OHNE Historie: {_zahl(len(leer))}   <- um die geht es")
    p()

    if not leer:
        p("Keine Items ohne Historie - nichts zu klaeren.")
        _schreiben(zeilen)
        return 0

    # ---- GEGLUECKT ODER GESCHEITERT? -----------------------------------
    # `touch_history` (Fehlschlag) datiert 20 h zurueck, `save_history`
    # (Erfolg) setzt die aktuelle Zeit. Ein Zeitstempel juenger als
    # 20 Stunden kann also nur von einem geglueckten Abruf stammen.
    _geglueckt = [t for t, a in leer if a and (jetzt - a) < 20 * 3600]
    _unklar = [t for t, a in leer if not a or (jetzt - a) >= 20 * 3600]
    p(f"Zeitstempel juenger als 20 h (Abruf GEGLUECKT, Antwort war leer):"
      f" {_zahl(len(_geglueckt))}")
    p(f"Zeitstempel aelter (geglueckt ODER gescheitert, nicht mehr "
      f"unterscheidbar): {_zahl(len(_unklar))}")
    p()

    # ---- WAS SIND DAS FUER ITEMS? --------------------------------------
    ids = [t for t, _a in leer]
    namen = store.cached_names(ids)
    try:
        gruppen = industry.group_names(ids)
    except Exception:
        gruppen = {}
    _je_gruppe = {}
    for t in ids:
        _je_gruppe.setdefault(gruppen.get(t) or "(Gruppe unbekannt)",
                              []).append(t)
    p("NACH GRUPPE:")
    for g, ts in sorted(_je_gruppe.items(), key=lambda kv: -len(kv[1])):
        _bsp = ", ".join((namen.get(t) or f"#{t}") for t in ts[:3])
        p(f"  {len(ts):>5}x  {g}   z.B. {_bsp}")
    p()

    # ---- NACHFRAGEN BEI ESI --------------------------------------------
    # Die ehrliche Antwort kommt aus erster Hand, nicht aus der Heuristik
    # oben. Gedeckelt, damit der Bericht kein Scan wird.
    probe = ids[:MAX_ESI]
    p(f"ESI-PROBE an {len(probe)} von {len(ids)} Items "
      f"(mehr waere ein Scan, kein Bericht):")
    _leer_esi, _daten, _fehler = [], [], []
    for t in probe:
        try:
            d = esi.fetch_market_history(t, region)
        except Exception as e:
            _fehler.append((t, f"{type(e).__name__}: {str(e)[:60]}"))
            continue
        if d:
            _daten.append((t, len(d)))
        else:
            _leer_esi.append(t)
    p(f"  ESI antwortet LEER (Item wird nicht gehandelt): "
      f"{_zahl(len(_leer_esi))}")
    p(f"  ESI liefert DOCH Daten (der Cache lag falsch):  "
      f"{_zahl(len(_daten))}")
    p(f"  Abruf GESCHEITERT:                              "
      f"{_zahl(len(_fehler))}")
    p()
    if _daten:
        p("  DIESE HABEN DOCH HISTORIE - hier waere laenger ruhen "
          "lassen FALSCH:")
        for t, n in _daten[:20]:
            p(f"    {namen.get(t) or t}: {n} Tage")
        p()
    if _fehler:
        p("  FEHLER:")
        for t, m in _fehler[:20]:
            p(f"    {namen.get(t) or t}: {m}")
        p()

    # ---- ERGEBNIS -------------------------------------------------------
    p("=" * 70)
    if _daten:
        p("ERGEBNIS: NICHT alle sind untradeable - mindestens "
          f"{len(_daten)} haben Historie. Eine laengere Ruhefrist wuerde "
          "diese verstecken.")
    elif _fehler:
        p(f"ERGEBNIS: {len(_fehler)} Abrufe scheitern. Erst klaeren, "
          "warum - eine laengere Ruhefrist wuerde den Fehler zudecken.")
    else:
        p("ERGEBNIS: ESI fuehrt fuer diese Items wirklich keine Historie. "
          "Eine laengere Ruhefrist ist sicher.")
    _schreiben(zeilen)
    return 0


def _schreiben(zeilen):
    os.makedirs(os.path.join(_WURZEL, "berichte"), exist_ok=True)
    with open(os.path.join(_WURZEL, "berichte", "historie_bericht.txt"),
              "w", encoding="utf-8") as f:
        f.write("\n".join(zeilen) + "\n")


if __name__ == "__main__":
    sys.exit(main())
