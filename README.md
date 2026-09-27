# EVE Motor Market

Industry and trading tool for EVE Online - for players who build and trade across several characters.

![Regional trading: route strategy, freight costs and live margins across two hubs](docs/screenshot-regional-trading.png)

**[Download the latest release](https://github.com/PeanutMotor/eve-motor-market/releases)** · Windows 10 or later · GPL-3.0

## What it does

- **Build** - full recipe tree down to ore and reactions, ME/TE from your own blueprints, multi build plans with several end products, invention with decryptor choice, a run planner that spreads jobs across your characters, shopping list with order-book prices. Saved plans reserve their material, so you never buy the same stack twice.
- **Trade** - trade journal with real profit after your own tax and fees; daytrade, swing and regional deal finders; order update shows which orders were undercut.
- **Multi-character** - wallets, orders, assets, skills and industry jobs of all linked characters in one view.

![A build plan: recipe tree with buy-or-build per item, build cost, total profit and margin](docs/screenshot-build-plan.png)

## Install

Download the `.exe` from [Releases](https://github.com/PeanutMotor/eve-motor-market/releases) and run it. Windows warns on first launch because the file is not code-signed - click "More info", then "Run anyway". A one-time setup links your first character and downloads the recipe data (about 140 MB).

## Your data

Everything stays on your machine, in `%APPDATA%\EVE Motor Market`. The tool connects only to `login.eveonline.com`, `esi.evetech.net`, `images.evetech.net`, `www.fuzzwork.co.uk` (recipe data) and `api.github.com` (update check).

## Source code and checks

Full source in this repository and as a zip on every release (GPL-3.0). `eve_trader/` is the program (`industry.py` = build math, `reprocess.py` = ore and reaction yields, `ui/` = the windows); `run.bat` starts it from source (Python 3.12 or newer), `build.bat` builds the `.exe`.

The calculations are guarded, not trusted:

- two test suites, 4'604 and 1'814 checks, run with `python pruefe.py`
- a mutation harness (`tests/rotprobe.py`) that breaks the code on purpose, 1'486 mutations, to prove the checks catch a regression
- source-order lint, `pyflakes`, and six scanners that keep the English and German texts in step

## Community

Questions, bug reports and ideas: [Discord](https://discord.gg/Atuqe6c2Rj).

---

Not a CCP Games product, not endorsed by CCP. The developer has signed the EVE Online Developer License Agreement. EVE Online and all related trademarks belong to CCP hf.
