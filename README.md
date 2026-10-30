# buggy-site-driftwood: Driftwood Stays

Driftwood Stays is a holiday-rental booking site (search, listings with availability calendars, a three-step
checkout, trips with changes, cancellations and receipts, a wishlist, and a host dashboard) with **40 functional bugs
planted on purpose**, to measure how many the AI QA Scanner finds. It is the hardest of the three benchmark sites,
after [buggy-site](https://github.com/Chaman-Raghav-Inno/buggy-site) (Lumen Goods) and
[buggy-site-taskline](https://github.com/Chaman-Raghav-Inno/buggy-site-taskline) (Taskline): 32 of its bugs are
Hard or Expert, involving date ranges, weekend and length-of-stay pricing, taxes, currency rounding, time zones,
refunds, form resubmission, out-of-order responses and stale form state.

[BUGS.md](BUGS.md) is the answer key: for each bug, the steps to reproduce, what should happen, what happens, its
severity, how hard it is to notice and where it is in the code. The site never serves that file, and nothing it
serves names or hints at a bug. The rules each bug breaks are published on the site (`/help` and every listing).

## Run it

```sh
python -m driftwood          # http://localhost:8082 (PORT changes the port)
```

Standard library only (Python 3.11+); no install step.

- Accounts (password `Driftwood@2026`, shown on the login page): `gina@driftwood.test` (guest with trips booked),
  `hal@driftwood.test` (host of three listings).
- Every visitor (cookie) gets a private copy of the demo world, dated around today, so parallel scans never see each
  other's changes. A restart or redeploy resets everything.

## Deploy on Railway

New service → GitHub repo → this repository, then **Generate domain** under Networking. `railway.json` sets the
start command and health check (`/healthz`); no variables or volume are needed. Avoid redeploying while a scan runs.

## Development

```sh
pip install ruff pytest
ruff check . && ruff format --check .
pytest -q
```

`tests/test_driftwood.py` keeps the server-side bugs in place and checks that nothing served gives a bug away.
Server-side code marks each bug with a `BUG-nn` comment; the served files must not.
