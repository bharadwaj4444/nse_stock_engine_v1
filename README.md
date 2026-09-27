# NSE Stock Engine V1

Python/PostgreSQL V1 for:

- NSE equity universe download
- NSE CM-UDiFF EOD bhavcopy ingestion
- 5-year daily price backfill
- PostgreSQL migrations
- Technical indicators: SMA, EMA, RSI, MACD, ATR, Bollinger Bands, ADX, returns, volatility, relative volume
- Idempotent ingestion
- Raw downloaded files retained locally
- FastAPI health endpoint
- CLI commands

## Important NSE data note

NSE discontinued the old equity bhavcopy/common bhavcopy formats in July 2024. V1 uses the current
`CM-UDiFF Common Bhavcopy Final (zip)` format.

The current securities universe is downloaded from NSE's official "Securities available for Trading"
CSV endpoint.

Use NSE data according to NSE's applicable data terms/licensing. This project is intended as a
personal research/engineering foundation, not a redistribution service.

## Requirements

- Python 3.12+
- PostgreSQL 15+
- Internet access
- Windows/Linux/macOS

## Quick start

### 1. Create database

```bash
createdb nse_stocks
```

Or use Docker:

```bash
docker compose up -d postgres
```

### 2. Install

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

pip install -e .
```

### 3. Configure

Copy `.env.example` to `.env`.

Default:

```text
DATABASE_URL=postgresql+psycopg://nse:nse@localhost:5432/nse_stocks
```

### 4. Run migration

```bash
alembic upgrade head
```

### 5. Download current NSE universe

```bash
python -m app.cli universe
```

### 6. Backfill five years

```bash
python -m app.cli backfill --years 5
```

This downloads weekday archive files, skips weekends, retries failures, and safely ignores
non-trading dates.

For a test run:

```bash
python -m app.cli backfill --start 2026-09-01 --end 2026-09-25
```

### 7. Calculate indicators

```bash
python -m app.cli indicators --date 2026-09-25
```

Or calculate the latest available trading date:

```bash
python -m app.cli indicators
```

### 8. Run evening pipeline

```bash
python -m app.cli daily
```

The daily job:

1. refreshes the NSE universe
2. downloads the latest bhavcopy
3. validates and stores prices
4. calculates indicators

## Database

Main tables:

- `companies`
- `daily_prices`
- `technical_indicators`
- `ingestion_runs`

## Current NSE URLs used

Universe:

`https://nsearchives.nseindia.com/content/equities/EQUITY_L.csv`

Archive:

`https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip`

The archive filename is generated from the requested trade date.

If NSE changes its URL or schema, update only the source adapter in:

`app/sources/nse.py`

## Design

Raw archive files are stored under:

`data/raw/nse/cm/YYYY/MM/DD/`

The database stores normalized equity rows only.

Technical indicators are deterministic Python calculations. No AI/LLM is used in V1.

## Indicator definitions

- SMA20/50/100/200
- EMA20/50
- RSI14 (Wilder)
- MACD 12/26/9
- ATR14 (Wilder)
- Bollinger 20/2
- ADX14
- 20/60-day annualized volatility
- 1/5/20/60/120/252-day returns
- 20-day relative volume
- 20/60-day relative performance vs NIFTY 50

The NIFTY comparison is populated when the NIFTY 50 symbol is present in the database; otherwise
the stock-relative fields remain NULL.

## Production next steps

V1 intentionally does not include fundamentals, filings, news, corporate actions, F&O or an LLM.
Those should be added as independent ingestion adapters after the price pipeline has been proven.
