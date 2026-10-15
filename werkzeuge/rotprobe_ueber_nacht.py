"""Rotprobe UEBER NACHT (emm551, Nutzer 14.10.2026: die volle Rotprobe in
~2-Stunden-Paketen laufen lassen, der PC faehrt danach automatisch runter -
"das kann ich ueber mehrere Tage ueber Nacht laufen lassen").

Ruft fuer JEDE Mutation `tests/rotprobe.py <i> <i+1>` einzeln auf - die
echte, schon geprueften Datei bleibt dabei unberuehrt (Regel 8a: die
richtige Funktion rufen, nicht nachbauen). Dieses Skript liefert nur drei
Dinge dazu, die rotprobe.py selbst nicht kann:

1. Merkt sich den Fortschritt in `berichte/rotprobe_fortschritt.txt` -
   nach JEDER einzelnen Mutation, nicht erst am Ende des Pakets. Ein
   Stromausfall mitten im Paket kostet so hoechstens eine Mutation.
2. Hoert nach ungefaehr EMM_ROTPROBE_BUDGET_S Sekunden auf (Standard 7200
   = 2 Stunden) statt nach einer festen Anzahl Mutationen - die
   Mutationen dauern unterschiedlich lang (hier im Container gemessen:
   ~34 s nur die b-Suite, ~40 s nur die aa-Suite, ~74 s wenn beide
   laufen muessen). Eine feste Stueckzahl pro Paket waere geraten
   (Regel 2) - und auf dem eigenen PC laeuft es ohnehin anders schnell.
3. Faehrt den PC danach herunter (`shutdown /s /t 60`), AUSSER es wurde
   in diesem Lauf keine einzige Mutation mehr gemacht (schon fertig,
   oder das Budget war beim Start schon aufgebraucht) - dann bleibt der
   PC an.

Alle BLIND-Befunde (Mutation wurde NICHT erkannt) stehen zusaetzlich in
`berichte/rotprobe_nacht_BLIND.txt` - die Datei bleibt leer, wenn alles
gut ging, und ist damit der erste Blick nach jeder Nacht.

EMM_ROTPROBE_TEST=1: taeuscht das Herunterfahren nur vor (zum
Ausprobieren, ohne dass der Rechner wirklich runterfaehrt).

Abbruch von Hand (Strg+C oder das Fenster schliessen): kein Herunterfahren.
"""
import importlib.util
import os
import subprocess
import sys
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROTPROBE = os.path.join(WURZEL, "tests", "rotprobe.py")
BERICHTE = os.path.join(WURZEL, "berichte")
FORTSCHRITT = os.path.join(BERICHTE, "rotprobe_fortschritt.txt")
LOG = os.path.join(BERICHTE, "rotprobe_nacht.txt")
BLIND_DATEI = os.path.join(BERICHTE, "rotprobe_nacht_BLIND.txt")

BUDGET_S = float(os.environ.get("EMM_ROTPROBE_BUDGET_S", 7200))
TEST = os.environ.get("EMM_ROTPROBE_TEST") == "1"
# Der laengste bisher gemessene Einzellauf war ~74 s (eine Mutation, die
# BEIDE Suiten braucht) - Luft fuer den letzten Lauf im Paket, der ueber
# das Budget hinaus zu Ende laufen darf, statt mitten im Testlauf
# abgewuergt zu werden.
NOTAUS_EINZELLAUF_S = 3700


def _gesamtzahl():
    """Die Mutationsliste aus der ECHTEN rotprobe.py - nie eine eigene
    Kopie der Zahl pflegen (Regel 9: EINE Quelle der Wahrheit)."""
    spec = importlib.util.spec_from_file_location("rotprobe", ROTPROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return len(mod.MUTATIONEN)


def _lies_fortschritt():
    if not os.path.exists(FORTSCHRITT):
        return 0
    try:
        inhalt = open(FORTSCHRITT, encoding="utf-8").read().strip()
    except OSError:
        return 0
    if inhalt == "FERTIG":
        return None  # schon komplett durchgelaufen
    try:
        return int(inhalt)
    except ValueError:
        return 0


def _schreibe_fortschritt(wert):
    # Erst in eine .tmp-Datei, dann umbenennen - ein Stromausfall mitten
    # im Schreiben darf die Fortschrittsdatei nie halb-kaputt hinterlassen.
    tmp = FORTSCHRITT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(wert))
    os.replace(tmp, FORTSCHRITT)


def _log(text):
    os.makedirs(BERICHTE, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(text)
    print(text, end="", flush=True)


def main():
    os.makedirs(BERICHTE, exist_ok=True)
    gesamt = _gesamtzahl()
    index = _lies_fortschritt()
    if index is None:
        _log(f"\n== {time.strftime('%Y-%m-%d %H:%M:%S')} Rotprobe ist schon "
             f"komplett durchgelaufen ({gesamt}/{gesamt}) - nichts zu tun.\n")
        return 0

    _log(f"\n== {time.strftime('%Y-%m-%d %H:%M:%S')} Paket-Start bei Index "
         f"{index}/{gesamt}, Budget {BUDGET_S / 3600:.1f} h ==\n")
    t0 = time.monotonic()
    gemacht = 0
    try:
        while index < gesamt and (time.monotonic() - t0) < BUDGET_S:
            _log(f"\n-- [{index}/{gesamt}] "
                 f"{time.strftime('%H:%M:%S')} --\n")
            try:
                r = subprocess.run(
                    [sys.executable, ROTPROBE, str(index), str(index + 1)],
                    cwd=WURZEL, capture_output=True, text=True,
                    timeout=NOTAUS_EINZELLAUF_S)
                ausgabe = (r.stdout or "") + (r.stderr or "")
            except subprocess.TimeoutExpired:
                ausgabe = (f"ZEITUEBERSCHREITUNG bei Mutation {index} - "
                           f"ueber {NOTAUS_EINZELLAUF_S} s, abgebrochen.\n")
            _log(ausgabe)
            if "BLIND" in ausgabe or "ZEITUEBERSCHREITUNG" in ausgabe:
                with open(BLIND_DATEI, "a", encoding="utf-8") as f:
                    f.write(f"[{index}] {ausgabe}\n")
            index += 1
            gemacht += 1
            _schreibe_fortschritt(index if index < gesamt else "FERTIG")
    except KeyboardInterrupt:
        _log(f"\n== von Hand abgebrochen bei Index {index}/{gesamt} - "
             f"kein Herunterfahren ==\n")
        return 1

    dauer = time.monotonic() - t0
    if index >= gesamt:
        _log(f"\n== FERTIG: alle {gesamt} Mutationen durchlaufen "
             f"({gemacht} in diesem Paket, {dauer / 60:.0f} min) ==\n")
    else:
        _log(f"\n== Paket-Ende bei Index {index}/{gesamt} "
             f"({gemacht} Mutationen, {dauer / 60:.0f} min) - die naechste "
             f"Nacht macht automatisch hier weiter ==\n")

    if gemacht == 0:
        return 0  # nichts gemacht in diesem Lauf -> PC bleibt an

    print("\nFaehrt in 60 Sekunden herunter. Zum Abbrechen in einem anderen "
          "Fenster: shutdown /a")
    if TEST:
        print("(EMM_ROTPROBE_TEST=1 - faehrt in Wirklichkeit NICHT runter)")
    else:
        subprocess.run(["shutdown", "/s", "/t", "60"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
