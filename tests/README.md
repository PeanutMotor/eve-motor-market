# Tests

The calculations in EVE Motor Market are guarded, not trusted. Run everything with

```
python pruefe.py
```

from the project root (or double-click `werkzeuge\pruefe.bat`). It runs:

- `test_bestand_herkunft.py` - logic suite (stock, recipes, reservations, invention, freight ...), no window needed
- `test_bauplan_aufbau.py` - UI suite, builds the real windows offscreen (`QT_QPA_PLATFORM=offscreen`)
- `lint_order.py` - source-order lint (catches `UnboundLocalError` patterns before they reach a user)
- `pyflakes` - undefined names

Further tools:

- `rotprobe.py` - mutation harness: breaks the code on purpose, one mutation at a time, and checks that the expected test turns red. `python tests/rotprobe.py --check` only verifies that every mutation still applies.
- `de_scan.py` ... `de_scan6.py` - keep every visible English text and its German translation in step (run by the logic suite).

The UI suite needs a test profile in `.smoke_home/` (not in the repository, it contains character IDs).
