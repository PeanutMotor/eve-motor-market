#!/usr/bin/env bash
# SCHNELLPRUEFUNG - aa- und b-Suite GLEICHZEITIG (emm549, Nutzer 13.10.2026:
# "deine Antworten dauern wieder sehr lange ... was muessen wir machen damit
# wir schneller werden").
#
# GEMESSEN im Container (13.10.2026, 2 Kerne):
#   aa-Suite  68 s   b-Suite  89 s   nacheinander 157 s   gleichzeitig 89 s
# Die beiden Suiten teilen sich keine Datei und keinen Port - sie koennen
# parallel laufen. Der Lint laeuft nebenher mit (er braucht ~1 s).
#
# NICHT hier drin: die Rotprobe. Sie wird NIE abgewartet (CLAUDE.md, TEMPO) -
# sie laeuft im Hintergrund, ihr Ergebnis kommt in der naechsten Antwort.
#
# Aufruf aus der Projektwurzel:  bash schnell.sh
cd "$(dirname "$0")" || exit 1

START=$(date +%s)
AA_LOG=$(mktemp); B_LOG=$(mktemp); L_LOG=$(mktemp)

python3.12 tests/test_bestand_herkunft.py > "$AA_LOG" 2>&1 &
AA_PID=$!
QT_QPA_PLATFORM=offscreen python3.12 tests/test_bauplan_aufbau.py > "$B_LOG" 2>&1 &
B_PID=$!
python3.12 tests/lint_order.py $(find eve_trader -name "*.py") main.py \
    > "$L_LOG" 2>&1 &
L_PID=$!

wait $AA_PID; AA_RC=$?
wait $B_PID;  B_RC=$?
wait $L_PID

echo "== aa-Suite =="
grep -E "^\(aa\)|FEHLER" "$AA_LOG" | head -40
echo "== b-Suite =="
grep -E "^\(b\) Bauplan|FEHLER" "$B_LOG" | head -40
echo "== Lint =="
tail -1 "$L_LOG"
echo "== Dauer: $(( $(date +%s) - START )) s (gleichzeitig) =="

rm -f "$AA_LOG" "$B_LOG" "$L_LOG"
[ "$AA_RC" = 0 ] && [ "$B_RC" = 0 ]
