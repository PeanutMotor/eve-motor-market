"""Rotprobe PARALLEL (emm823, Nutzer 02.11.2026: "Einen weg finden die
ganzen Rotproben zu beschleunigen").

Macht dasselbe wie `rotprobe_ueber_nacht.py` - jede Mutation einzeln
belegen -, nur auf mehreren Kernen gleichzeitig und ohne die Zeit, die
bisher ins Kopieren ging.

WARUM DAS GEHT, OHNE DASS SICH ZWEI LAEUFE INS GEHEGE KOMMEN:
`tests/rotprobe.py` legt seine Arbeitskopie dort an, wo ROTPROBE_TMP
hinzeigt (seit 27.09.2026). Jeder Streifen bekommt hier seinen EIGENEN
Ordner. Genau daran scheiterte der naive Versuch, einfach zwei
`rotprobe_nacht_*.bat` gleichzeitig zu starten: die teilen sich
`%TEMP%\\rotprobe_arbeitskopie` UND die Fortschrittsdatei - der zweite
Lauf loescht dem ersten die Dateien unter den Fuessen ("b-SUITE
ABGEBROCHEN - FileNotFoundError"), und das Ergebnis sind FALSCHE
BLIND-Meldungen. Beides ist hier getrennt.

DREI HEBEL, ZUSAMMEN GEMESSEN (Container, 02.11.2026):
  Projekt-Kopie je Mutation  9,0 s   (184 Dateien, 15,5 MB)
  aa-Suite                  49,5 s
  b-Suite                   36,2 s
  -> ein voller Durchgang (2309 Mutationen):        ~40 h
1. BLOECKE STATT EINZELAUFRUFE. `rotprobe_ueber_nacht.py` ruft
   `rotprobe.py i i+1` je Mutation auf - jeder Aufruf kopiert das ganze
   Projekt neu. Hier laufen BLOCK Mutationen in EINEM Aufruf, und
   rotprobe.py setzt dazwischen nur die eine mutierte Datei zurueck
   (0,01 s statt 9,0 s). Bei BLOCK=25 bleibt vom Kopieren rund 1 %.
2. Die richtige Suite zuerst (steckt in rotprobe.py).            ~28 h
3. PARALLEL ueber mehrere Kerne.                 bei 4 Prozessen  ~7 h

BLOCK IST EIN KOMPROMISS, KEIN WUNSCHWERT: ein Block ist die Einheit,
die ein Absturz oder eine Zeitueberschreitung mitreisst und die beim
naechsten Start wiederholt wird. 25 Mutationen dauern rund 20 Minuten
und tragen etwa 0,8 % Kopier-Aufwand - groesser bringt kaum noch etwas,
kleiner kostet wieder Kopien.

WIEDERAUFNAHME: je Streifen steht der naechste Index in
`berichte/rotprobe_par_fortschritt_<k>.txt`. Ein Neustart macht in
jedem Streifen dort weiter. Alles von vorne: die Dateien loeschen (oder
`python werkzeuge/rotprobe_parallel.py --neu`).

EINSTELLUNGEN (Umgebungsvariablen):
  EMM_ROTPROBE_PROZESSE  Anzahl gleichzeitiger Laeufe
                         (Standard: halbe Kernzahl, mindestens 1 -
                         damit der PC benutzbar bleibt)
  EMM_ROTPROBE_BLOCK     Mutationen je Aufruf (Standard 25)
  EMM_ROTPROBE_BUDGET_S  Abbruch nach so vielen Sekunden
                         (Standard 0 = bis alles durch ist)

Berichte: `berichte/rotprobe_parallel.txt`, Befunde zusaetzlich in
`berichte/rotprobe_parallel_BLIND.txt` - diese Datei ist der erste
Blick danach; sie bleibt leer, wenn jede Mutation erkannt wurde.
"""
import importlib.util
import os
import subprocess
import sys
import threading
import time

WURZEL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROTPROBE = os.path.join(WURZEL, "tests", "rotprobe.py")
BERICHTE = os.path.join(WURZEL, "berichte")
LOG = os.path.join(BERICHTE, "rotprobe_parallel.txt")
BLIND_DATEI = os.path.join(BERICHTE, "rotprobe_parallel_BLIND.txt")

BLOCK = max(1, int(os.environ.get("EMM_ROTPROBE_BLOCK", 25) or 25))
BUDGET_S = float(os.environ.get("EMM_ROTPROBE_BUDGET_S", 0) or 0)
# HALBE KERNZAHL ALS STANDARD: die Rotprobe soll den PC nicht
# beschlagnahmen (emm811 - waehrend der Probe krochen Downloads und
# Installationen). Wer mehr will, setzt EMM_ROTPROBE_PROZESSE.
PROZESSE = int(os.environ.get("EMM_ROTPROBE_PROZESSE", 0) or 0)
if PROZESSE <= 0:
    PROZESSE = max(1, (os.cpu_count() or 2) // 2)
# Der laengste bisher gemessene Einzellauf war ~90 s (eine Mutation, die
# BEIDE Suiten braucht). Ein Block darf entsprechend lange brauchen,
# plus Luft fuer einen langsamen PC.
NOTAUS_BLOCK_S = 300 * BLOCK

_schloss = threading.Lock()


def _gesamtzahl():
    """Die Mutationsliste aus der ECHTEN rotprobe.py - nie eine eigene
    Kopie der Zahl pflegen (Regel 9: EINE Quelle der Wahrheit)."""
    spec = importlib.util.spec_from_file_location("rotprobe", ROTPROBE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return len(mod.MUTATIONEN)


def _fortschritt_datei(k):
    return os.path.join(BERICHTE, f"rotprobe_par_fortschritt_{k}.txt")


def _lies_fortschritt(k, start):
    try:
        inhalt = open(_fortschritt_datei(k), encoding="utf-8").read().strip()
        return int(inhalt)
    except (OSError, ValueError):
        return start


def _schreibe_fortschritt(k, wert):
    # Erst .tmp, dann umbenennen - ein Stromausfall mitten im Schreiben
    # darf die Fortschrittsdatei nie halb-kaputt hinterlassen.
    tmp = _fortschritt_datei(k) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(str(wert))
    os.replace(tmp, _fortschritt_datei(k))


def _log(text):
    # EIN Bericht fuer alle Streifen: die Zeilen tragen ihre
    # Streifennummer, damit sie trotz Verzahnung zuordenbar bleiben.
    with _schloss:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(text)
        print(text, end="", flush=True)


def _standzeile(zustand, t0):
    """"STAND 418/2309 (18 %) - noch ca. 5,2 h" - nach jedem Block.

    Nutzer 03.11.2026: "wie weiss ich wann alles fertig ist? kann ich
    dich jeweils fragen wie weit wir sind und wie lange es noch etwa
    dauert?" Die Antwort gehoert dorthin, wo die Zahlen entstehen -
    dann steht sie im Fenster UND im Bericht, und niemand muss sie aus
    den Fortschrittsdateien zusammenrechnen.

    Das Tempo kommt aus DIESEM Lauf (erledigt seit Start / Laufzeit),
    nicht aus dem Gesamtfortschritt - sonst waere die Schaetzung nach
    einer Wiederaufnahme voellig daneben, weil die Arbeit von gestern
    in der Laufzeit von heute nicht steckt."""
    with _schloss:
        werte = list(zustand.values())
    if not werte:                                        # pragma: no cover
        return ""
    erledigt = sum(i - lo for i, lo, _hi in werte)
    offen = sum(hi - i for i, _lo, hi in werte)
    gesamt = erledigt + offen
    jetzt = erledigt - _START_ERLEDIGT[0]
    dauer = max(1e-9, time.monotonic() - t0)
    # ERST SCHAETZEN, WENN ES ETWAS ZU SCHAETZEN GIBT: aus einer
    # einzelnen Mutation gerechnet sprang die Restzeit im Test zwischen
    # 44 h und 22 h hin und her (die Mutationen dauern verschieden
    # lang - nur aa, nur b, oder beide). Eine Zahl, die sich im
    # Minutentakt halbiert, ist keine Auskunft, sondern Rauschen.
    rest = ""
    if offen > 0 and jetzt >= 5:
        sek = offen * dauer / jetzt
        rest = (f" - noch ca. {sek / 3600:.1f} h" if sek >= 3600
                else f" - noch ca. {sek / 60:.0f} min")
    elif offen > 0:
        rest = " - Restzeit sobald genug gemessen ist"
    return (f"   STAND {erledigt}/{gesamt} "
            f"({erledigt * 100 // max(1, gesamt)} %){rest}\n")


# Wie viele Mutationen schon erledigt waren, als dieser Lauf begann -
# fuer das Tempo zaehlt nur, was SEITHER dazugekommen ist.
_START_ERLEDIGT = [0]


def _streifen(k, lo, hi, t0, zustand):
    """Arbeitet [lo, hi) in Bloecken ab - eigener Arbeitsordner."""
    umgebung = dict(os.environ)
    umgebung["ROTPROBE_TMP"] = os.path.join(
        os.environ.get("TEMP") or os.environ.get("TMP") or "/tmp",
        f"rotprobe_arbeitskopie_{k}")
    # NIEDRIGE PRIORITAET (emm811): alles andere am PC geht vor.
    prio = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)
    index = _lies_fortschritt(k, lo)
    if index >= hi:
        _log(f"[{k}] schon fertig ({lo}-{hi})\n")
        return
    _log(f"[{k}] startet bei {index} (Streifen {lo}-{hi})\n")
    while index < hi:
        if BUDGET_S and (time.monotonic() - t0) >= BUDGET_S:
            _log(f"[{k}] Budget aus - Halt bei {index}\n")
            return
        ende = min(index + BLOCK, hi)
        try:
            r = subprocess.run(
                [sys.executable, ROTPROBE, str(index), str(ende)],
                cwd=WURZEL, capture_output=True, text=True,
                timeout=NOTAUS_BLOCK_S, creationflags=prio,
                env=umgebung)
            ausgabe = (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            ausgabe = (f"ZEITUEBERSCHREITUNG im Block {index}-{ende} - "
                       f"ueber {NOTAUS_BLOCK_S} s, abgebrochen.\n")
        _log(f"\n-- [{k}] {index}-{ende} {time.strftime('%H:%M:%S')} --\n"
             + ausgabe)
        if "BLIND" in ausgabe or "ZEITUEBERSCHREITUNG" in ausgabe:
            # NUR DIE BEFUND-ZEILEN, mit dem Block davor: so steht in der
            # BLIND-Datei, wo man nachsehen muss, ohne den ganzen Bericht
            # mitzuschleppen.
            with _schloss:
                with open(BLIND_DATEI, "a", encoding="utf-8") as f:
                    f.write(f"\n== Block {index}-{ende} (Streifen {k}) ==\n")
                    for zeile in ausgabe.splitlines():
                        if "BLIND" in zeile or "ZEITUEBERSCH" in zeile:
                            f.write(zeile + "\n")
        index = ende
        _schreibe_fortschritt(k, index)
        with _schloss:
            zustand[k] = (index, lo, hi)
        _log(_standzeile(zustand, t0))


def main():
    os.makedirs(BERICHTE, exist_ok=True)
    gesamt = _gesamtzahl()
    if "--neu" in sys.argv[1:]:
        for k in range(64):
            try:
                os.remove(_fortschritt_datei(k))
            except OSError:
                pass
        _log("Fortschritt zurueckgesetzt - es faengt bei 0 an.\n")

    # STREIFEN: jeder Prozess bekommt einen zusammenhaengenden Bereich.
    # Zusammenhaengend und nicht reihum, weil ein Streifen dann als
    # Bereich wiederaufnehmbar ist (eine Zahl je Streifen genuegt).
    grenzen = [k * gesamt // PROZESSE for k in range(PROZESSE)] + [gesamt]
    _log(f"\n== {time.strftime('%Y-%m-%d %H:%M:%S')} Rotprobe parallel: "
         f"{gesamt} Mutationen, {PROZESSE} gleichzeitig, Block {BLOCK}"
         + (f", Budget {BUDGET_S / 3600:.1f} h" if BUDGET_S else "")
         + f" ({os.cpu_count()} Kerne) ==\n")

    t0 = time.monotonic()
    # ALLE Streifen vorbelegen, bevor der erste Faden laeuft - sonst
    # zaehlt die erste Standzeile nur die Streifen, die schon einen
    # Block fertig haben, und meldet einen viel zu kleinen Nenner.
    zustand = {k: (_lies_fortschritt(k, grenzen[k]), grenzen[k],
                   grenzen[k + 1]) for k in range(PROZESSE)}
    _START_ERLEDIGT[0] = sum(i - lo for i, lo, _hi in zustand.values())
    if _START_ERLEDIGT[0]:
        _log(f"   (bei {_START_ERLEDIGT[0]} Mutationen geht es weiter)\n")
    faeden = []
    for k in range(PROZESSE):
        f = threading.Thread(target=_streifen,
                             args=(k, grenzen[k], grenzen[k + 1], t0,
                                   zustand),
                             daemon=True)
        f.start()
        faeden.append(f)
    try:
        for f in faeden:
            f.join()
    except KeyboardInterrupt:                            # pragma: no cover
        _log("\n== von Hand abgebrochen - der Fortschritt je Streifen "
             "steht in berichte\\rotprobe_par_fortschritt_*.txt ==\n")
        return 1

    dauer = time.monotonic() - t0
    offen = sum(max(0, grenzen[k + 1] - _lies_fortschritt(k, grenzen[k]))
                for k in range(PROZESSE))
    if offen:
        _log(f"\n== Halt nach {dauer / 60:.0f} min - es fehlen noch "
             f"{offen} von {gesamt} Mutationen "
             f"({(gesamt - offen) * 100 // gesamt} % sind durch). "
             f"Nochmal starten macht genau hier weiter. ==\n")
    else:
        _log(f"\n== FERTIG: ALLE {gesamt} MUTATIONEN DURCHLAUFEN "
             f"({dauer / 60:.0f} min in diesem Lauf) ==\n")
    print("\nBefunde: berichte\\rotprobe_parallel_BLIND.txt "
          "(leer = jede Mutation erkannt)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
