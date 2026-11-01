# Tools ("Werkzeuge")

Small helpers for development and support. None of them is needed to run EVE Motor Market.

- `pruefe.bat` - runs all checks (`python pruefe.py`) and keeps the window open.
- `messe_ladezeit.bat` - measures start-up and loading times, report in `berichte\ladezeiten.txt`.
- `zeige_zuordnung`, `zeige_orders`, `zeige_multi`, `zeige_karten`, `zeige_lagerorte`, `hole_planer_diagnose` - read-only diagnostics (job assignment, orders, multi build plans, plan cards, stock locations: demand vs. stock, run planner); each writes a report to `berichte\`.
- `pruefe_fracht` - recalculates the freight on your own purchases a second way and reports any difference.
- `szenario_prioritaet` - simulates re-ordering build plans and shows where material and jobs end up.
- `messung_bau_vs_bauplan.py` - compares the build calculation with the build plan window.
- `suiten_parallel.bat` / `suiten_parallel.py` - runs both GUI test suites (aa + b) and the two language scans AT THE SAME TIME instead of one after another (measured 25.10.2026: 84 s sequential -> 64 s parallel on this machine). Exit code 0 only if all four are green.

All tools only read your data; reports are written to `berichte\` (not part of the repository).
