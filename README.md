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

## CLI Commands

All commands are run from the project root:

```cmd
python -m app.cli <command>
```

### 1. Build / refresh the NSE universe

Download the current NSE equity universe and populate the `companies` table:

```cmd
python -m app.cli universe
```

---

### 2. Daily price ingestion

Ingest the latest available NSE bhavcopy:

```cmd
python -m app.cli daily
```

---

### 3. Historical price backfill

Backfill historical NSE daily prices.

#### Last 5 years

```cmd
python -m app.cli backfill --years 5
```

#### Explicit date range

```cmd
python -m app.cli backfill --start 2021-01-01 --end 2026-09-25
```

#### Resume-safe backfill

The backfill is restartable.

Downloaded and successfully processed dates are automatically skipped:

```cmd
python -m app.cli backfill --start 2021-01-01 --end 2026-09-25
```

The backfill uses the following logic:

1. Valid raw ZIP + complete database data → skip the date.
2. Valid raw ZIP + incomplete database data → reuse the cached ZIP.
3. Missing/invalid raw ZIP → download from NSE.
4. Failed dates → retry on the next run.
5. Existing database rows are safely upserted.

This makes it safe to stop and restart a large historical backfill.

#### Force re-download

To ignore the cached raw ZIP and download/reprocess every requested date:

```cmd
python -m app.cli backfill --start 2021-01-01 --end 2026-09-25 --force
```

Use `--force` only when a fresh download is specifically required.

#### Example

```cmd
python -m app.cli backfill --start 2024-07-04 --end 2024-07-10
```

The historical NSE archive format is handled automatically:

* Dates before `2024-07-08` use the legacy NSE archive.
* Dates from `2024-07-08` onward use the current UDiFF archive.

---

### 4. Technical indicators

Calculate technical indicators for a specific trading date:

```cmd
python -m app.cli indicators --date 2026-09-25
```

Indicators include:

* SMA
* EMA
* RSI
* MACD
* ATR
* Bollinger Bands
* ADX
* Volatility
* Returns
* Relative volume
* NIFTY 50 relative performance

---

## Financial Data CLI

Financial data is obtained from NSE Integrated Filings and stored as raw filings before being processed into normalized financial statements.

### 5. Download financial filings for one company

```cmd
python -m app.cli financial-download --symbol HDFCBANK
```

The default start date is:

```text
01-01-2025
```

Specify an explicit date range:

```cmd
python -m app.cli financial-download \
    --symbol HDFCBANK \
    --from-date 01-01-2025 \
    --to-date 30-09-2026
```

Specify the request delay:

```cmd
python -m app.cli financial-download \
    --symbol HDFCBANK \
    --from-date 01-01-2025 \
    --delay 1.0
```

### 6. Download financial filings for the configured universe

```cmd
python -m app.cli financial-download \
    --from-date 01-01-2025
```

This downloads and catalogs the available NSE financial filings for the universe.

---

### 7. Process cached financial filings

Process cached raw financial XML for one company:

```cmd
python -m app.cli financial-process --symbol HDFCBANK
```

Process all cached financial filings:

```cmd
python -m app.cli financial-process
```

Processing converts the raw filings into normalized financial statement records.

---

## Typical Initial Setup

For a new database, the basic sequence is:

```cmd
python -m app.cli universe
```

Then populate historical prices:

```cmd
python -m app.cli backfill --start 2021-01-01 --end 2026-09-25
```

Then calculate indicators for the required dates:

```cmd
python -m app.cli indicators --date 2026-09-25
```

Download financial filings:

```cmd
python -m app.cli financial-download --from-date 01-01-2025
```

Process the downloaded filings:

```cmd
python -m app.cli financial-process
```

---

## Backfill / Recovery Workflow

For a large historical download, the recommended command is:

```cmd
python -m app.cli backfill --start 2021-01-01 --end 2026-09-25
```

If the process is interrupted, run the same command again:

```cmd
python -m app.cli backfill --start 2021-01-01 --end 2026-09-25
```

Previously completed dates are skipped, while incomplete dates are recovered from their cached raw ZIP files whenever possible.

To deliberately redownload everything:

```cmd
python -m app.cli backfill --start 2021-01-01 --end 2026-09-25 --force
```

The historical backfill currently processes dates **sequentially**. It does not use five concurrent workers.


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
