# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

MyStock — a personal Taiwan/US stock market dashboard: TWSE/yfinance/MOPS crawlers feed a FastAPI backend that
serves K-line charts, institutional investor (三大法人) and margin/short (融資融券) chip data, and a
config-driven technical/chip/fundamental alert-scanning engine, rendered by a Vue 3 + PrimeVue frontend.

Code comments and the design docs under `docs/` are written in Traditional Chinese and are the authoritative
spec — many modules carry comments like `見設計文件第 X 節` (see design doc section X) pointing at a specific
doc under `docs/`. When changing behavior in `strategies/`, `services/`, or `db/`, check the referenced doc
folder first; the numbered `docs/N.主題/` folders roughly track the project's build phases.

## Commands

### Frontend (`frontend/`)
```bash
npm run dev       # Vite dev server, http://localhost:5173 (falls back to 5175 if busy)
npm run build      # production build to frontend/dist
npm run preview    # preview a production build
npm run lint       # eslint --fix over .vue/.js/.jsx/.cjs/.mjs
```
There is no frontend test suite.

### Backend (`backend/`)
Python 3.11+ (Docker image uses 3.11-slim; local `.venv` at repo root is 3.14), managed with a standard venv —
`pip install -r requirements.txt`. Copy `backend/.env.example` to `backend/.env` before running anything; it's
read via `python-dotenv` and re-read on most config lookups (so `.env` edits take effect without a restart).

```bash
cd backend
python main.py                                    # or: uvicorn main:app --reload --port 8000
```
API docs at `http://localhost:8000/docs`. There is no backend test suite — verify changes by hitting the
running API (`/health`, `/docs`) or running the one-off scripts below.

Utility scripts (run from `backend/`, each is documented in its own docstring):
```bash
python scripts/import_json_to_postgres.py     # one-time bulk import of data/**/*.json into Postgres (idempotent)
python scripts/compare_data_sources.py        # asserts JSON and Postgres chart-data responses are field-identical
python scripts/migrate_data_layout.py         # legacy: flat data/*.json -> data/{tw,us}/*.json
python scripts/restore_price_from_legacy.py   # one-time repair for a historical 0.0-price bug (--dry-run first)
```

### Postgres (optional, `backend/docker-compose.yml`)
```bash
cd backend
docker compose up -d       # postgres:15 (db) + flyway migrate (db/migration/*.sql) + nightly pg backups + app
```
`app` bakes in the FastAPI service; the scheduler runs inside its `uvicorn` process (no separate worker
container). `backend/.env` must exist before `up -d` — Docker will silently create it as a directory instead of
bind-mounting the file if it's missing. Flyway migrations live in `backend/db/migration/V*__*.sql`; add new ones
there, never edit an already-applied `V*` file.

`stop_servers.bat` (repo root) kills whatever is listening on ports 8000/5173/5175, for local (non-Docker) dev.

### Full-stack Docker deployment (repo root)
Root-level compose files are a separate, full-stack (db + flyway + backup + backend + frontend) setup layered
on top of `backend/docker-compose.yml` (which is untouched and still works standalone for backend-only use).

```bash
# prod/test/dev/local share one definition; only the --env-file differs (git branch -> env file):
#   main branch -> .env.prod, test branch -> .env.test, dev branch -> .env.dev, local -> .env.local (untracked)
docker compose --env-file .env.prod -f docker-compose.yml up -d --build

# local hot-reload (bind-mounted source, uvicorn --reload + Vite dev server), reads root .env (untracked):
docker compose -f docker-compose.dev.yml up -d --build
```
`docker-compose.traefik.yml` is an illustrative overlay only (example domain/network) for a future reverse-proxy
gateway; it is not required and not wired into normal usage. `frontend/Dockerfile` has `development` (Vite dev
server) and `production` (nginx, proxies `/api/` to `backend:8000`, see `frontend/nginx.conf`) build targets;
`backend/Dockerfile` gained a matching `development`/`production` split (default/no `--target` still builds
`production`, so `backend/docker-compose.yml` needs no changes).

## Architecture

### Dual data source: JSON files vs. PostgreSQL
JSON is the original and still-default storage: one file per symbol at `backend/data/{tw,us}/<symbol>.json`,
keyed by date. PostgreSQL is an optional, fully-parallel read path — controlled globally by `DATA_SOURCE` in
`.env` (`json` | `postgres`, `config.get_data_source()`), **not** decided per-call.

- Every read path branches on `get_data_source()` in `services/stock_service.load_stock_data()` — this is the
  only place that should ever branch on it. Add new read logic there, not scattered across callers.
- Crawlers (`services/fetcher.py`, `services/us_fetcher.py`) always write JSON as the source of truth, then
  best-effort **dual-write** to Postgres via `db/dual_write.py`. A Postgres failure only logs a warning; it must
  never fail the JSON write or block the crawl.
- `repositories/stock_repository.py` (`StockRepository`) is the sole SQL access point — no raw SQL elsewhere.
  Its `*_sync` methods exist because the crawlers are synchronous code calling into async SQLAlchemy; they each
  spin up a fresh `asyncio.run()` and dispose the engine afterward (`db/session.dispose_engine()`), because
  asyncpg connections are bound to the event loop they were created on.
- `db/mapping.py` converts between the JSON record shape (Chinese-keyed chip fields) and the Postgres row shape;
  a few Chinese-keyed margin/short detail fields intentionally have no Postgres column (frontend never reads
  them — see `scripts/compare_data_sources.py`'s `IGNORED_RECORD_FIELDS`).
- Startup backfill (`services/backfill.py`, wired into `main.py`'s lifespan) only runs when `DATA_SOURCE=postgres`
  — it diagnoses gaps by querying `daily_stock_data` / `market_no_trading_days`, which don't help in JSON mode.

### Multi-market abstraction (`markets/`)
`markets/base.py` defines `MarketAdapter` (ABC) + `MarketMeta`/`Metric` dataclasses; `markets/tw.py` and
`markets/us.py` implement it and are registered in `markets/__init__.py`'s `MARKETS` dict. An adapter owns
everything that differs by market: currency/lot size, red-up-vs-green-up color convention, which chip panels
apply (TW has margin/short/institutional data; US doesn't), symbol validation, and trading-session state. New
markets plug in by adding an adapter here, not by branching `if market == "xx"` in business logic. The frontend
mirrors this with `useMarket()` (`frontend/src/composables/useMarket.js`), a singleton whose `currentMarket` is
driven by the `:market` route param and persisted to `localStorage`.

### Strategy/alert engine (`strategies/`)
Config-driven signal scanner — thresholds live in `strategy_config/strategies.yaml`, not code, so tuning a
strategy is a YAML edit with no deploy (`config_loader.py` reparses the file on every call; it's small and
scanned once/day so no caching). Pipeline, per `strategies/scanner.py`:

1. `ChipDataProvider.get_bars()` (`services/chip_provider.py`) loads a symbol's history via
   `services/stock_service.py` (respecting `DATA_SOURCE`) and pre-computes MA/BIAS series into a `ScanContext`.
   **Condition functions must only read `ctx.ma`/`ctx.bias`, never recompute indicators themselves** — this
   keeps the strategy engine decoupled from JSON/SQL and guarantees the same numbers the frontend charts show
   (`indicators/moving_average.py`'s `sma()` is deliberately kept numerically identical to
   `frontend/src/utils/movingAverage.js`'s `sma()`).
2. For each enabled strategy (per `strategy.markets`) and each of its `conditions`, look up the condition type in
   `strategies/registry.CONDITION_REGISTRY` and call it. Conditions self-register via the `@condition(type=...)`
   decorator in `conditions_tech.py` (6 MA-based conditions), `conditions_chip.py` (3 chip-pattern conditions,
   TW-only), and `conditions_fund.py` (MOPS revenue-decline condition, TW-only) — importing
   `strategies/__init__.py` is what triggers registration, so a new condition module must be imported there.
   Every condition function has the signature `(ctx: ScanContext, idx: int, params: dict) -> list[dict] | None`.
3. Filters (`strategies/filters.py`, e.g. volume/candlestick/institutional-buy confirmation) score signal
   strength (`weak`/`moderate`/`strong` by how many filters pass) but never suppress a signal outright.
4. Dedup: a signal is dropped if the exact `(symbol, strategy_id, direction, trade_date)` key already exists, or
   if it's inside its cooldown window (`strategies/cooldown.py`, `ALERT_COOLDOWN_DAYS`, per `(symbol, strategy,
   direction)`) — this stops the same regime from re-alerting every day it stays true.
5. Surviving alerts are appended via `repositories/alert_repository.py` (flat-file store under
   `backend/data/_alerts/`, not a DB table).

Chip-category strategies additionally skip symbols matching the TW ETF/ETN code pattern (`00` + 2-6 digits, e.g.
`0050`, `00981A`) — margin/institutional data means something different for ETFs and would pollute chip signals.

The scanner runs both on a schedule (`services/scheduler.py`, chained right after each market's daily fetch) and
on demand via `POST /api/v1/alerts/scan`.

### Crawlers & scheduling (`services/`)
- `fetcher.py` (TWSE) / `us_fetcher.py` (yfinance) each expose a `fetch_status` singleton (so the scheduler and
  manual `/fetch/trigger` calls share one in-flight guard — a new trigger is refused while one is running) and a
  `mode` of `incremental` (fill the gap since the last stored date) vs `repair` (full window, discard existing).
  Fetch failures fall back to writing `0.0` for missing OHLC rather than crashing (see the caveat in
  `scripts/restore_price_from_legacy.py` about a historical bug this caused — `stock_service` now treats `0` as
  a missing value everywhere it aggregates/charts).
- `mops_fetcher.py` / `mops_eps_fetcher.py` scrape MOPS for monthly revenue YoY and quarterly EPS — TW only,
  JSON-only (no Postgres table yet), and must be triggered explicitly
  (`POST /api/v1/fundamentals/revenue|eps/trigger`) before `fundamental_revenue_decline` can fire.
- `scheduler.py` uses `AsyncIOScheduler` (shares FastAPI's event loop; jobs run in APScheduler's thread pool so
  the blocking `requests`-based crawlers don't stall the API) — TW fetch+scan at 14:30, US fetch+scan at 06:00,
  both `Asia/Taipei`. A scan is always chained immediately after its market's fetch.

### API layer (`api/v1/endpoints/`)
Each file is a market-agnostic `APIRouter` mounted in `main.py` under `/api/v1/<resource>`. Response envelope
convention: `{"success": bool, "data": ..., "message"?: ..., "error"?: {"code", "message"}}`. Domain-not-found
errors raise `core.exceptions.SymbolNotFoundException`, caught by a global handler in `main.py` and turned into
a `404` with `error.code = "SYMBOL_NOT_FOUND"`.

### Frontend structure (`frontend/src/`)
Vue 3 (`<script setup>` Composition API) + PrimeVue (Aura preset, brand color overridden via
`assets/layout/variables/_common-brass.scss` rather than the JS theme config — don't try to recolor via
`definePreset`) + `vue-echarts` for charts. Routes are under a single `AppLayout` shell
(`router/index.js`); `/stock/:id` and `/stock/:id/chart/:chartType` redirect to their `:market/...` equivalents
for backward-compat links. `router.beforeEach` calls `useMarket().setMarket()` whenever a route carries a
`:market` param, keeping the market singleton in sync with the URL. `service/*.js` are thin axios wrappers
around the backend (`stockApi.js`, `alertApi.js`) sharing one `apiClient` (`VITE_API_BASE`, defaults to
`http://localhost:8000/api/v1`).

`vite.config.mjs` has a custom plugin (`fixViteHashPlugin`) working around a third-party tool appending an
`#ai-agent` fragment to import specifiers — don't remove it without checking why it was added.
