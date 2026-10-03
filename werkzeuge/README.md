# Tools ("Werkzeuge")

Small helpers for development and support. None of them is needed to run EVE Motor Market.

- `pruefe.bat` - runs all checks (`python pruefe.py`) and keeps the window open.
- `messe_ladezeit.bat` - measures start-up and loading times, report in `berichte\ladezeiten.txt`.
- `zeige_zuordnung`, `zeige_orders`, `zeige_multi`, `zeige_karten`, `hole_planer_diagnose` - read-only diagnostics (job assignment, orders, multi build plans, plan cards, run planner); each writes a report to `berichte\`.
- `pruefe_fracht` - recalculates the freight on your own purchases a second way and reports any difference.
- `szenario_prioritaet` - simulates re-ordering build plans and shows where material and jobs end up.
- `messung_bau_vs_bauplan.py` - compares the build calculation with the build plan window.

All tools only read your data; reports are written to `berichte\` (not part of the repository).
