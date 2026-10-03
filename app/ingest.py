from __future__ import annotations

from decimal import Decimal
import hashlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select, func, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import SessionLocal, engine
from app.models import (
    Company,
    DailyPrice,
    FinancialStatement,
    IngestionRun,
    BenchmarkPrice,
    FinancialRawFiling,
)
from app.sources.nse import NSEClient
from app.sources.nse_financials import FinancialFiling, NSEFinancialClient
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.financial_raw import (
    RAW_ROOT,
    iter_raw_filings,
    save_raw_filing,
    sha256_bytes,
)


# ============================================================
# General helpers
# ============================================================

def _int(v):
    try:
        if pd.isna(v):
            return None
        return int(float(v))
    except Exception:
        return None


def _same_scope_submission(
    a: dict[str, Any],
    b: dict[str, Any],
) -> bool:
    return (
        a.get("statement_scope") == b.get("statement_scope")
        and a.get("submission_type") == b.get("submission_type")
    )


def _value_for_cumulative(
    statement: dict[str, Any],
    field: str,
    ytd_field: str,
) -> Any:
    """
    Return the cumulative value represented by a statement.

    For an actual YTD filing, use _ytd_*.

    For a direct Q1/quarter statement, the quarter itself is
    the cumulative FY-to-Q1 value.
    """
    value = statement.get(ytd_field)

    if value is not None:
        return value

    if statement.get("_pnl_context_type") == "quarter":
        return statement.get(field)

    return None


def _find_previous_cumulative(
    statement: dict[str, Any],
    ytd_start: str | None,
    quarterly_statements: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """
    Find the immediately preceding statement belonging to
    the same fiscal-year cumulative chain.

    A Q1 direct-quarter statement can serve as the first
    cumulative base because Q1 == FY-start through Q1-end.
    """
    if ytd_start is None:
        return None

    for candidate in reversed(quarterly_statements):
        if candidate is statement:
            continue

        if candidate["period_end"] >= statement["period_end"]:
            continue

        if not _same_scope_submission(candidate, statement):
            continue

        candidate_start = (
            candidate.get("_ytd_start")
            or candidate.get("_pnl_start")
        )

        if candidate_start != ytd_start:
            continue

        return candidate

    return None


# ============================================================
# Quarterly P&L derivation
# ============================================================

def _derive_quarter_pnl(
    statement: dict[str, Any],
    previous: dict[str, Any],
) -> None:
    """
    Convert a cumulative/YTD P&L statement into a true quarter.

    Example:

        Q1 YTD = 100
        Q2 YTD = 240

        Q2 actual quarter = 240 - 100 = 140

    EPS is deliberately NOT subtracted because EPS is not additive.

    EBIT and EBITDA are derived from:
        EBIT = PBT + finance costs
        EBITDA = EBIT + depreciation

    The parser must provide the corresponding _ytd_* fields.
    """

    # --------------------------------------------------------
    # Revenue / PBT / Net Income
    # --------------------------------------------------------

    additive_fields = (
        ("revenue", "_ytd_revenue"),
        ("profit_before_tax", "_ytd_profit_before_tax"),
        ("net_income", "_ytd_net_income"),
    )

    for field, ytd_field in additive_fields:
        current_value = _value_for_cumulative(
            statement,
            field,
            ytd_field,
        )

        previous_value = _value_for_cumulative(
            previous,
            field,
            ytd_field,
        )

        if (
            current_value is not None
            and previous_value is not None
        ):
            statement[field] = (
                current_value - previous_value
            )

    # EPS is not additive.
    statement["eps"] = None

    # --------------------------------------------------------
    # EBIT / EBITDA
    # --------------------------------------------------------

    current_finance = statement.get(
        "_ytd_finance_costs"
    )
    previous_finance = previous.get(
        "_ytd_finance_costs"
    )

    current_depreciation = statement.get(
        "_ytd_depreciation"
    )
    previous_depreciation = previous.get(
        "_ytd_depreciation"
    )

    current_pbt = _value_for_cumulative(
        statement,
        "profit_before_tax",
        "_ytd_profit_before_tax",
    )

    previous_pbt = _value_for_cumulative(
        previous,
        "profit_before_tax",
        "_ytd_profit_before_tax",
    )

    if (
        current_pbt is None
        or previous_pbt is None
    ):
        return

    quarter_pbt = (
        current_pbt - previous_pbt
    )

    statement["profit_before_tax"] = quarter_pbt

    # EBIT requires finance costs.
    if (
        current_finance is not None
        and previous_finance is not None
    ):
        quarter_finance = (
            current_finance
            - previous_finance
        )

        statement["ebit"] = (
            quarter_pbt
            + quarter_finance
        )

        # EBITDA requires depreciation.
        if (
            current_depreciation is not None
            and previous_depreciation is not None
        ):
            quarter_depreciation = (
                current_depreciation
                - previous_depreciation
            )

            statement["ebitda"] = (
                statement["ebit"]
                + quarter_depreciation
            )


# ============================================================
# Quarterly P&L processing
# ============================================================

def _derive_quarterly_pnl(
    all_statements: list[dict[str, Any]],
) -> None:
    """
    Convert cumulative/YTD quarterly P&L rows into true
    quarter-level values in-place.
    """

    quarterly_statements = [
        row
        for row in all_statements
        if row.get("period_type") == "quarterly"
    ]

    quarterly_statements.sort(
        key=lambda row: row["period_end"]
    )

    for statement in quarterly_statements:
        pnl_context_type = statement.get(
            "_pnl_context_type"
        )

        # Genuine direct quarter.
        if pnl_context_type == "quarter":
            continue

        # Nothing to derive.
        if pnl_context_type != "ytd":
            continue

        ytd_start = statement.get(
            "_pnl_start"
        )

        previous = _find_previous_cumulative(
            statement,
            ytd_start,
            quarterly_statements,
        )

        if previous is None:
            # Never store a cumulative YTD value as if it were
            # a quarterly value when there is no base to subtract.
            statement["revenue"] = None
            statement["ebitda"] = None
            statement["ebit"] = None
            statement["profit_before_tax"] = None
            statement["net_income"] = None
            statement["eps"] = None
            continue

        _derive_quarter_pnl(
            statement,
            previous,
        )


# ============================================================
# Quarterly cash-flow processing
# ============================================================

def _derive_quarterly_cash_flow(
    all_statements: list[dict[str, Any]],
) -> None:
    """
    Convert cumulative/YTD cash flow into true quarterly
    operating cash flow, capex and FCF.
    """

    quarterly_statements = [
        row
        for row in all_statements
        if row.get("period_type") == "quarterly"
    ]

    quarterly_statements.sort(
        key=lambda row: row["period_end"]
    )

    for statement in quarterly_statements:
        ytd_ocf = statement.get(
            "_ytd_operating_cash_flow"
        )

        ytd_capex = statement.get(
            "_ytd_capital_expenditure"
        )

        ytd_start = statement.get(
            "_ytd_start"
        )

        ytd_end = statement.get(
            "_ytd_end"
        )

        cash_flow_start = statement.get(
            "_cash_flow_start"
        )

        cash_flow_end = statement.get(
            "_cash_flow_end"
        )

        period_end = statement[
            "period_end"
        ].isoformat()

        if (
            ytd_ocf is None
            and ytd_capex is None
        ):
            continue

        # ----------------------------------------------------
        # Determine whether the source contains a direct
        # quarterly cash-flow period.
        # ----------------------------------------------------

        direct_cash_flow = False

        if (
            cash_flow_start is not None
            and cash_flow_end == period_end
        ):
            try:
                cf_start = date.fromisoformat(
                    cash_flow_start
                )

                cf_end = date.fromisoformat(
                    cash_flow_end
                )

                cf_days = (
                    cf_end - cf_start
                ).days

                direct_cash_flow = (
                    75 <= cf_days <= 105
                    and statement.get("operating_cash_flow") is not None
                    and statement.get("capital_expenditure") is not None
                )

            except ValueError:
                direct_cash_flow = False

        # ----------------------------------------------------
        # Case 1: direct quarterly cash flow
        # ----------------------------------------------------

        if direct_cash_flow:
            pass

        # ----------------------------------------------------
        # Case 2: cumulative/YTD cash flow
        # ----------------------------------------------------

        else:
            previous = None

            for candidate in reversed(
                quarterly_statements
            ):
                if candidate is statement:
                    continue

                if (
                    candidate["period_end"]
                    >= statement["period_end"]
                ):
                    continue

                if (
                    candidate.get("_ytd_start")
                    != ytd_start
                ):
                    continue

                if (
                    candidate.get("_ytd_end")
                    != candidate[
                        "period_end"
                    ].isoformat()
                ):
                    continue

                if not _same_scope_submission(
                    candidate,
                    statement,
                ):
                    continue

                previous = candidate
                break

            if previous is not None:
                previous_ocf = previous.get(
                    "_ytd_operating_cash_flow"
                )

                previous_capex = previous.get(
                    "_ytd_capital_expenditure"
                )

                # Q1 may be a direct quarter and therefore
                # may not expose _ytd_* fields.
                if previous_ocf is None:
                    previous_ocf = previous.get(
                        "operating_cash_flow"
                    )

                if previous_capex is None:
                    previous_capex = previous.get(
                        "capital_expenditure"
                    )

                if (
                    ytd_ocf is not None
                    and previous_ocf is not None
                ):
                    statement[
                        "operating_cash_flow"
                    ] = (
                        ytd_ocf
                        - previous_ocf
                    )

                if (
                    ytd_capex is not None
                    and previous_capex is not None
                ):
                    statement[
                        "capital_expenditure"
                    ] = (
                        ytd_capex
                        - previous_capex
                    )

        # ----------------------------------------------------
        # Free cash flow
        # ----------------------------------------------------

        ocf = statement.get(
            "operating_cash_flow"
        )

        capex = statement.get(
            "capital_expenditure"
        )

        if (
            ocf is not None
            and capex is not None
        ):
            statement[
                "free_cash_flow"
            ] = (
                ocf - abs(capex)
            )


# ============================================================
# Annual / Q4 P&L processing
# ============================================================

def _derive_q4_pnl(
    all_statements: list[dict[str, Any]],
) -> None:
    """
    Derive Q4 P&L from annual cumulative P&L minus the
    preceding cumulative quarterly statement.
    """

    quarterly_statements = [
        row
        for row in all_statements
        if row.get("period_type") == "quarterly"
    ]

    annual_statements = [
        row
        for row in all_statements
        if row.get("period_type") == "annual"
    ]

    quarterly_statements.sort(
        key=lambda row: row["period_end"]
    )

    annual_statements.sort(
        key=lambda row: row["period_end"]
    )

    for annual in annual_statements:
        annual_start = annual.get(
            "_pnl_start"
        )

        if annual_start is None:
            annual_start = annual.get(
                "_period_start"
            )

        if annual_start is None:
            continue

        # ----------------------------------------------------
        # Find preceding cumulative quarterly statement.
        # ----------------------------------------------------

        previous = None

        for candidate in reversed(
            quarterly_statements
        ):
            if (
                candidate["period_end"]
                >= annual["period_end"]
            ):
                continue

            if not _same_scope_submission(
                candidate,
                annual,
            ):
                continue

            candidate_start = (
                candidate.get("_ytd_start")
                or candidate.get("_pnl_start")
            )

            if candidate_start != annual_start:
                continue

            previous = candidate
            break

        if previous is None:
            continue

        # ----------------------------------------------------
        # Find Q4 row corresponding to annual period.
        # ----------------------------------------------------

        q4_statement = next(
            (
                row
                for row in quarterly_statements
                if (
                    row["period_end"]
                    == annual["period_end"]
                    and _same_scope_submission(
                        row,
                        annual,
                    )
                )
            ),
            None,
        )

        if q4_statement is None:
            continue

        # If parser already identified a direct Q4,
        # preserve it.
        if q4_statement.get(
            "_pnl_context_type"
        ) != "ytd":
            continue

        _derive_quarter_pnl(
            q4_statement,
            previous,
        )


# ============================================================
# Annual / Q4 cash-flow processing
# ============================================================

def _derive_q4_cash_flow(
    all_statements: list[dict[str, Any]],
) -> None:
    """
    Derive Q4 cash flow as:

        Annual cumulative cash flow
        -
        preceding cumulative quarterly cash flow
    """

    quarterly_statements = [
        row
        for row in all_statements
        if row.get("period_type") == "quarterly"
    ]

    annual_statements = [
        row
        for row in all_statements
        if row.get("period_type") == "annual"
    ]

    quarterly_statements.sort(
        key=lambda row: row["period_end"]
    )

    annual_statements.sort(
        key=lambda row: row["period_end"]
    )

    for annual in annual_statements:
        annual_ocf = annual.get(
            "operating_cash_flow"
        )

        annual_capex = annual.get(
            "capital_expenditure"
        )

        annual_start = annual.get(
            "_cash_flow_start"
        )

        annual_end = annual.get(
            "_cash_flow_end"
        )

        if annual_start is None:
            continue

        if (
            annual_end
            != annual["period_end"].isoformat()
        ):
            continue

        # ----------------------------------------------------
        # Find preceding cumulative quarterly statement.
        # ----------------------------------------------------

        previous = None

        for candidate in reversed(
            quarterly_statements
        ):
            if (
                candidate["period_end"]
                >= annual["period_end"]
            ):
                continue

            if (
                candidate.get("_ytd_start")
                != annual_start
            ):
                continue

            if (
                candidate.get("_ytd_end")
                != candidate[
                    "period_end"
                ].isoformat()
            ):
                continue

            if not _same_scope_submission(
                candidate,
                annual,
            ):
                continue

            previous = candidate
            break

        if previous is None:
            continue

        previous_ocf = previous.get(
            "_ytd_operating_cash_flow"
        )

        previous_capex = previous.get(
            "_ytd_capital_expenditure"
        )

        # ----------------------------------------------------
        # Derive Q4 OCF.
        # ----------------------------------------------------

        if (
            annual_ocf is not None
            and previous_ocf is not None
        ):
            annual_q4_ocf = (
                annual_ocf
                - previous_ocf
            )
        else:
            annual_q4_ocf = None

        # ----------------------------------------------------
        # Derive Q4 capex.
        # ----------------------------------------------------

        if (
            annual_capex is not None
            and previous_capex is not None
        ):
            annual_q4_capex = (
                annual_capex
                - previous_capex
            )
        else:
            annual_q4_capex = None

        # ----------------------------------------------------
        # Find corresponding Q4 row.
        # ----------------------------------------------------

        q4_statement = next(
            (
                row
                for row in quarterly_statements
                if (
                    row["period_end"]
                    == annual["period_end"]
                    and _same_scope_submission(
                        row,
                        annual,
                    )
                )
            ),
            None,
        )

        if q4_statement is None:
            continue

        if annual_q4_ocf is not None:
            q4_statement[
                "operating_cash_flow"
            ] = annual_q4_ocf

        if annual_q4_capex is not None:
            q4_statement[
                "capital_expenditure"
            ] = annual_q4_capex

        q4_ocf = q4_statement.get(
            "operating_cash_flow"
        )

        q4_capex = q4_statement.get(
            "capital_expenditure"
        )

        if (
            q4_ocf is not None
            and q4_capex is not None
        ):
            q4_statement[
                "free_cash_flow"
            ] = (
                q4_ocf
                - abs(q4_capex)
            )


# ============================================================
# Financial statement derivation pipeline
# ============================================================

def derive_quarterly_financials(
    all_statements: list[dict[str, Any]],
) -> None:
    """
    Apply all transformations required to convert raw
    NSE/XBRL financial data into quarterly analytical data.

    This mutates all_statements in-place.
    """

    if not all_statements:
        return

    # P&L quarterly conversion.
    _derive_quarterly_pnl(
        all_statements
    )

    # Cash-flow quarterly conversion.
    _derive_quarterly_cash_flow(
        all_statements
    )

    # Annual -> Q4 P&L.
    _derive_q4_pnl(
        all_statements
    )

    # Annual -> Q4 cash flow.
    _derive_q4_cash_flow(
        all_statements
    )


# ============================================================
# Company universe
# ============================================================

def save_universe(
    df: pd.DataFrame,
) -> int:
    written = 0

    with SessionLocal.begin() as db:
        existing = {
            x.nse_symbol: x
            for x in db.scalars(
                select(Company)
            ).all()
        }

        for row in df.itertuples(
            index=False
        ):
            symbol = row.nse_symbol

            if symbol in existing:
                c = existing[symbol]

                c.isin = (
                    row.isin
                    if pd.notna(row.isin)
                    else c.isin
                )

                c.company_name = (
                    row.company_name
                )

                c.series = (
                    row.series
                    if pd.notna(row.series)
                    else c.series
                )

                c.listing_date = (
                    row.listing_date
                    if pd.notna(row.listing_date)
                    else c.listing_date
                )

                c.is_active = True

                c.updated_at = (
                    datetime.now().astimezone()
                )

            else:
                db.add(
                    Company(
                        nse_symbol=symbol,
                        isin=(
                            row.isin
                            if pd.notna(row.isin)
                            else None
                        ),
                        company_name=(
                            row.company_name
                        ),
                        series=(
                            row.series
                            if pd.notna(row.series)
                            else None
                        ),
                        listing_date=(
                            row.listing_date
                            if pd.notna(row.listing_date)
                            else None
                        ),
                        is_active=True,
                        source_updated_at=(
                            datetime.now().astimezone()
                        ),
                    )
                )

            written += 1

    return written


def download_universe() -> int:
    client = NSEClient()

    df = client.universe()

    return save_universe(df)


# ============================================================
# Financial statement persistence
# ============================================================

def save_financial_statements(
    rows: list[dict],
) -> int:
    if not rows:
        return 0

    written = 0

    with SessionLocal.begin() as db:
        for row in rows:
            company_id = row["company_id"]

            stmt = insert(
                FinancialStatement
            ).values(
                company_id=company_id,
                period_type=row["period_type"],
                period_end=row["period_end"],
                filing_date=row.get(
                    "filing_date"
                ),
                revenue=row.get(
                    "revenue"
                ),
                ebitda=row.get(
                    "ebitda"
                ),
                ebit=row.get(
                    "ebit"
                ),
                profit_before_tax=row.get(
                    "profit_before_tax"
                ),
                net_income=row.get(
                    "net_income"
                ),
                eps=row.get(
                    "eps"
                ),
                total_assets=row.get(
                    "total_assets"
                ),
                total_equity=row.get(
                    "total_equity"
                ),
                total_debt=row.get(
                    "total_debt"
                ),
                cash_and_equivalents=row.get(
                    "cash_and_equivalents"
                ),
                operating_cash_flow=row.get(
                    "operating_cash_flow"
                ),
                capital_expenditure=row.get(
                    "capital_expenditure"
                ),
                free_cash_flow=row.get(
                    "free_cash_flow"
                ),
                source=row["source"],
                source_reference=row.get(
                    "source_reference"
                ),
                statement_scope=row.get(
                    "statement_scope",
                    "UNKNOWN",
                ),
                submission_type=row.get(
                    "submission_type",
                    "ORIGINAL",
                ),
                audit_status=row.get(
                    "audit_status"
                ),
                reporting_standard=row.get(
                    "reporting_standard"
                ),
                source_url=row.get(
                    "source_url"
                ),
            )

            stmt = stmt.on_conflict_do_update(
                constraint=(
                    "uq_financial_statement_identity"
                ),
                set_={
                    "filing_date":
                        stmt.excluded.filing_date,
                    "revenue":
                        stmt.excluded.revenue,
                    "ebitda":
                        stmt.excluded.ebitda,
                    "ebit":
                        stmt.excluded.ebit,
                    "profit_before_tax":
                        stmt.excluded.profit_before_tax,
                    "net_income":
                        stmt.excluded.net_income,
                    "eps":
                        stmt.excluded.eps,
                    "total_assets":
                        stmt.excluded.total_assets,
                    "total_equity":
                        stmt.excluded.total_equity,
                    "total_debt":
                        stmt.excluded.total_debt,
                    "cash_and_equivalents":
                        stmt.excluded.cash_and_equivalents,
                    "operating_cash_flow": stmt.excluded.operating_cash_flow,
                    "capital_expenditure": stmt.excluded.capital_expenditure,
                    "free_cash_flow": stmt.excluded.free_cash_flow,
                    "audit_status": stmt.excluded.audit_status,
                    "reporting_standard":
                        stmt.excluded.reporting_standard,
                    "source_url":
                        stmt.excluded.source_url,
                },
            )

            db.execute(stmt)

            written += 1

    return written


# ============================================================
# Company map
# ============================================================

def _company_map(db):
    return {
        c.nse_symbol: c.id
        for c in db.scalars(
            select(Company)
        ).all()
    }


# ============================================================
# NSE Bhavcopy
# ============================================================

def ingest_bhavcopy(
    trade_date: date,
    client: NSEClient | None = None,
) -> int:
    client = client or NSEClient()

    started = (
        datetime.now().astimezone()
    )

    raw_dir = (
        Path(settings.raw_data_dir)
        / "nse"
        / "cm"
        / trade_date.strftime(
            "%Y/%m/%d"
        )
    )

    raw_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    with SessionLocal.begin() as db:
        run = IngestionRun(
            run_type="bhavcopy",
            trade_date=trade_date,
            source="NSE",
            status="RUNNING",
            started_at=started,
        )

        db.add(run)
        db.flush()

        run_id = run.id

    try:
        df, url, content = (
            client.bhavcopy(
                trade_date
            )
        )

        digest = hashlib.sha256(
            content
        ).hexdigest()

        zip_path = (
            raw_dir
            / f"BhavCopy_{trade_date:%Y%m%d}.csv.zip"
        )

        zip_path.write_bytes(
            content
        )

        # Only normal equity series are used
        # for the initial V1 universe.
        if "series" in df.columns:
            df = df[
                df["series"].isin(
                    [
                        "EQ",
                        "BE",
                        "BZ",
                        "SM",
                        "ST",
                    ]
                )
            ].copy()

        with SessionLocal.begin() as db:
            cmap = _company_map(db)

            rows = []

            for r in df.itertuples(
                index=False
            ):
                company_id = cmap.get(
                    r.symbol
                )

                if not company_id:
                    continue

                rows.append(
                    {
                        "company_id":
                            company_id,
                        "trade_date":
                            trade_date,
                        "open_price":
                            getattr(
                                r,
                                "open",
                                None,
                            ),
                        "high_price":
                            getattr(
                                r,
                                "high",
                                None,
                            ),
                        "low_price":
                            getattr(
                                r,
                                "low",
                                None,
                            ),
                        "close_price":
                            getattr(
                                r,
                                "close",
                                None,
                            ),
                        "prev_close":
                            getattr(
                                r,
                                "prev_close",
                                None,
                            ),
                        "volume":
                            _int(
                                getattr(
                                    r,
                                    "volume",
                                    None,
                                )
                            ),
                        "traded_value":
                            getattr(
                                r,
                                "value",
                                None,
                            ),
                        "trades_count":
                            _int(
                                getattr(
                                    r,
                                    "trades",
                                    None,
                                )
                            ),
                        "delivery_qty":
                            _int(
                                getattr(
                                    r,
                                    "delivery_qty",
                                    None,
                                )
                            ),
                        "delivery_pct":
                            getattr(
                                r,
                                "delivery_pct",
                                None,
                            ),
                        "vwap":
                            getattr(
                                r,
                                "vwap",
                                None,
                            ),
                        "source_file":
                            (
                                f"{url} "
                                f"sha256={digest}"
                            ),
                    }
                )

            if rows:
                stmt = insert(
                    DailyPrice
                ).values(rows)

                stmt = (
                    stmt.on_conflict_do_update(
                        index_elements=[
                            "company_id",
                            "trade_date",
                        ],
                        set_={
                            k: getattr(
                                stmt.excluded,
                                k,
                            )
                            for k in [
                                "open_price",
                                "high_price",
                                "low_price",
                                "close_price",
                                "prev_close",
                                "volume",
                                "traded_value",
                                "trades_count",
                                "delivery_qty",
                                "delivery_pct",
                                "vwap",
                                "source_file",
                            ]
                        },
                    )
                )

                db.execute(stmt)

            run = db.get(
                IngestionRun,
                run_id,
            )

            run.status = "SUCCESS"
            run.records_seen = len(df)
            run.records_written = len(rows)
            run.finished_at = (
                datetime.now().astimezone()
            )

            return len(rows)

    except Exception as exc:
        with SessionLocal.begin() as db:
            run = db.get(
                IngestionRun,
                run_id,
            )

            if run:
                run.status = "FAILED"
                run.error_message = repr(
                    exc
                )
                run.finished_at = (
                    datetime.now().astimezone()
                )

        raise


# ============================================================
# Financial filings
# ============================================================

def ingest_financial_filings(
    symbol: str,
    from_date: str = "01-01-2026",
    to_date: str | None = None,
) -> int:
    symbol = symbol.upper()

    client = NSEFinancialClient()

    # --------------------------------------------------------
    # Resolve company.
    # --------------------------------------------------------

    with SessionLocal() as db:
        company = db.execute(
            select(Company).where(
                Company.nse_symbol == symbol
            )
        ).scalar_one_or_none()

        if company is None:
            raise ValueError(
                f"Company not found for NSE symbol: "
                f"{symbol}. "
                "Run universe ingestion first."
            )

        company_id = company.id

    # --------------------------------------------------------
    # Download and parse ALL filings first.
    # --------------------------------------------------------

    filings = client.get_filings(
        symbol=symbol,
        from_date=from_date,
        to_date=to_date,
    )

    total_statements = 0

    all_statements: list[
        dict[str, Any]
    ] = []

    for filing in filings:
        if not filing.xbrl_url:
            continue

        try:
            xml_text = client.download_xbrl(
                filing.xbrl_url
            )

            # --------------------------------------------------------
            # Persist the exact NSE XML before parsing.
            #
            # This makes the raw filing reproducible and allows the
            # parser to be improved later without downloading again.
            # --------------------------------------------------------
            xml_bytes = xml_text.encode("utf-8")

            xml_path, metadata_path, already_exists = save_raw_filing(
                filing=filing,
                xml_bytes=xml_bytes,
            )

            if already_exists:
                print(
                    f"Financial raw cache: existing "
                    f"{symbol} {filing.period_end} "
                    f"{filing.statement_scope}"
                )
            else:
                print(
                    f"Financial raw cache: saved "
                    f"{xml_path}"
                )

            statements = client.parse_xbrl(
                xml_text=xml_text,
                filing=filing,
            )

            if not statements:
                continue

            # Attach Company ID.
            for statement in statements:
                statement[
                    "company_id"
                ] = company_id

            all_statements.extend(
                statements
            )

        except Exception as exc:
            print(
                f"Financial filing failed: "
                f"{symbol} "
                f"{filing.period_end} "
                f"{filing.source_reference}: "
                f"{exc}"
            )

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # All filings have now been collected.
    #
    # Only now derive Q1/Q2/Q3/Q4 values.
    # --------------------------------------------------------

    if all_statements:
        derive_quarterly_financials(
            all_statements
        )

        # ----------------------------------------------------
        # Save only real database fields.
        #
        # Internal fields beginning with "_" are intentionally
        # ignored by save_financial_statements().
        # ----------------------------------------------------

        total_statements = (
            save_financial_statements(
                all_statements
            )
        )

    return total_statements

def _effective_filing_date(
    broadcast_datetime: str | None,
    revised_datetime: str | None,
) -> date | None:
    value = revised_datetime or broadcast_datetime

    if not value:
        return None

    for fmt in (
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
    ):
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue

    return None

# ============================================================
# Financial ingestion for complete universe
# ============================================================

def ingest_financial_filings_for_universe(
    from_date: str = "01-01-2025",
    to_date: str | None = None,
    delay_seconds: float = 1.0,
) -> int:
    import time

    with SessionLocal() as db:
        symbols = db.execute(
            select(
                Company.nse_symbol
            )
            .where(
                Company.is_active.is_(True),
                Company.nse_symbol.is_not(None),
            )
            .order_by(
                Company.nse_symbol
            )
        ).scalars().all()

    total_statements = 0
    failed = 0

    print(
        f"Financial ingestion: "
        f"{len(symbols)} companies"
    )

    for index, symbol in enumerate(
        symbols,
        start=1,
    ):
        try:
            saved = (
                ingest_financial_filings(
                    symbol=symbol,
                    from_date=from_date,
                    to_date=to_date,
                )
            )

            total_statements += saved

            print(
                f"[{index}/{len(symbols)}] "
                f"{symbol}: "
                f"{saved} statements"
            )

        except Exception as exc:
            failed += 1

            print(
                f"[{index}/{len(symbols)}] "
                f"{symbol}: FAILED: {exc}"
            )

        if delay_seconds > 0:
            time.sleep(
                delay_seconds
            )

    print()
    print(
        f"Completed: {len(symbols)}"
    )
    print(
        f"Failed:    {failed}"
    )
    print(
        f"Statements: {total_statements}"
    )

    return total_statements


# ============================================================
# NIFTY 50 history
# ============================================================

def ingest_nifty50_history(
    start: date,
    end: date,
) -> int:
    import yfinance as yf

    data = yf.download(
        "^NSEI",
        start=start.isoformat(),
        end=(
            end + timedelta(days=1)
        ).isoformat(),
        auto_adjust=False,
        progress=False,
    )

    if data.empty:
        raise RuntimeError(
            f"No NIFTY 50 data returned "
            f"for {start} to {end}"
        )

    # yfinance may return MultiIndex columns
    # such as ('Close', '^NSEI')
    if isinstance(
        data.columns,
        pd.MultiIndex,
    ):
        data.columns = (
            data.columns
            .get_level_values(0)
        )

    written = 0

    with SessionLocal() as db:
        for index_date, row in data.iterrows():
            trade_date = (
                pd.Timestamp(
                    index_date
                ).date()
            )

            def value(column):
                raw = row.get(
                    column
                )

                if (
                    raw is None
                    or pd.isna(raw)
                ):
                    return None

                return Decimal(
                    str(float(raw))
                )

            existing = (
                db.query(
                    BenchmarkPrice
                )
                .filter(
                    BenchmarkPrice.benchmark
                    == "NIFTY50",
                    BenchmarkPrice.trade_date
                    == trade_date,
                )
                .one_or_none()
            )

            values = {
                "benchmark":
                    "NIFTY50",
                "trade_date":
                    trade_date,
                "open_price":
                    value("Open"),
                "high_price":
                    value("High"),
                "low_price":
                    value("Low"),
                "close_price":
                    value("Close"),
                "source":
                    "YAHOO_FINANCE",
                "source_reference":
                    "^NSEI",
            }

            if existing:
                for key, item in (
                    values.items()
                ):
                    setattr(
                        existing,
                        key,
                        item,
                    )
            else:
                db.add(
                    BenchmarkPrice(
                        **values
                    )
                )

            written += 1

        db.commit()

    return written

def save_shareholding_filing(filing) -> int:
    """
    Persist one validated NSE shareholding filing.

    The effective_date identifies the quarter.
    If NSE later publishes a revised filing for the same quarter,
    the existing row is replaced with the latest filing information.
    """

    with engine.begin() as conn:
        company = conn.execute(
            text(
                """
                SELECT id
                FROM companies
                WHERE nse_symbol = :symbol
                """
            ),
            {
                "symbol": filing.symbol,
            },
        ).mappings().first()

        if company is None:
            raise ValueError(
                f"Company not found for NSE symbol: {filing.symbol}"
            )

        company_id = company["id"]

        result = conn.execute(
            text(
                """
                INSERT INTO share_capital (
                    company_id,
                    effective_date,
                    shares_outstanding,
                    share_type,
                    filing_date,
                    source,
                    source_url,
                    calculation_method,
                    created_at,
                    updated_at
                )
                VALUES (
                    :company_id,
                    :effective_date,
                    :shares_outstanding,
                    :share_type,
                    :filing_date,
                    :source,
                    :source_url,
                    :calculation_method,
                    NOW(),
                    NOW()
                )
                ON CONFLICT (
                    company_id,
                    effective_date,
                    share_type
                )
                DO UPDATE SET
                    shares_outstanding = EXCLUDED.shares_outstanding,
                    filing_date = EXCLUDED.filing_date,
                    source = EXCLUDED.source,
                    source_url = EXCLUDED.source_url,
                    calculation_method = EXCLUDED.calculation_method,
                    updated_at = NOW()
                RETURNING id
                """
            ),
            {
                "company_id": company_id,
                "effective_date": filing.effective_date,
                "shares_outstanding": filing.total_shares,
                "share_type": "EQUITY",
                "filing_date": filing.submission_date,
                "source": filing.source,
                "source_url": filing.xbrl_url,
                "calculation_method": filing.calculation_method,
            },
        )

        return int(result.scalar_one())

def ingest_shareholding_for_company(
    symbol: str,
    *,
    latest_only: bool = False,
) -> int:
    """
    Download NSE shareholding filings and persist them.
    """

    from app.sources.nse_shareholding import NSEShareholdingClient

    client = NSEShareholdingClient()

    filings = client.get_shareholding_filings(
        symbol,
        latest_only=latest_only,
    )

    written = 0

    for filing in filings:
        save_shareholding_filing(filing)
        written += 1

    return written

# ============================================================
# Shareholding ingestion for complete universe
# ============================================================

def ingest_shareholding_for_universe(
    latest_only: bool = True,
    delay_seconds: float = 0.0,
    limit: int | None = None,
    workers: int = 5,
) -> int:
    """
    Ingest shareholding data for the NSE universe concurrently.

    Args:
        latest_only:
            If True, ingest only the latest filing for each company.
        delay_seconds:
            Optional delay applied by each worker after processing a company.
            Recommended: 0.0 initially when using bounded concurrency.
        limit:
            Optional limit for testing.
        workers:
            Number of concurrent NSE workers.

    Returns:
        Total number of shareholding rows written.
    """
    import time

    if workers < 1:
        raise ValueError("workers must be >= 1")

    if delay_seconds < 0:
        raise ValueError("delay_seconds must be >= 0")

    query = text(
        """
        SELECT nse_symbol
        FROM companies
        WHERE is_active IS TRUE
          AND nse_symbol IS NOT NULL
        ORDER BY nse_symbol
        """
    )

    with engine.begin() as conn:
        symbols = [
            row["nse_symbol"]
            for row in conn.execute(query).mappings().all()
        ]

    if limit is not None:
        symbols = symbols[:limit]

    total = len(symbols)

    if total == 0:
        print("No companies to process.")
        return 0

    def process_one(symbol: str) -> tuple[str, int, str | None]:
        """
        Process one company inside a worker thread.
        """
        try:
            written = ingest_shareholding_for_company(
                symbol,
                latest_only=latest_only,
            )

            if delay_seconds > 0:
                time.sleep(delay_seconds)

            return symbol, written, None

        except Exception as exc:
            return symbol, 0, str(exc)

    completed = 0
    failed = 0
    total_written = 0

    print(
        f"Starting shareholding ingestion: "
        f"{total} companies, {workers} workers"
    )

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_one, symbol): symbol
            for symbol in symbols
        }

        for future in as_completed(futures):
            symbol = futures[future]

            try:
                result_symbol, written, error = future.result()
            except Exception as exc:
                result_symbol = symbol
                written = 0
                error = str(exc)

            completed += 1
            total_written += written

            if error:
                failed += 1
                print(
                    f"[{completed}/{total}] "
                    f"{result_symbol} FAILED: {error}"
                )
            else:
                print(
                    f"[{completed}/{total}] "
                    f"{result_symbol}: {written}"
                )

    print()
    print(f"Completed: {completed}")
    print(f"Failed:    {failed}")
    print(f"Rows:      {total_written}")

    return total_written

def process_cached_financial_filings(
    symbol: str | None = None,
    batch_size: int = 250,
) -> int:
    """
    Process financial XBRL files registered in the raw-file catalog.

    No NSE network access is performed.
    PostgreSQL locates raw files; the filesystem remains
    the immutable raw-data store.

    Processing is performed in batches so the job is resumable
    and does not accumulate the entire raw archive in memory.
    """
    client = NSEFinancialClient()

    symbol_filter = symbol.strip().upper() if symbol else None

    total_statements = 0
    total_processed = 0
    total_failed = 0

    while True:
        # ---------------------------------------------------------
        # Load one batch of pending/failed filings.
        # ---------------------------------------------------------
        with Session(engine) as db:
            # Recover rows left in PROCESSING by an interrupted run.
            db.execute(
                update(FinancialRawFiling)
                .where(
                    FinancialRawFiling.processing_status == "PROCESSING"
                )
                .values(
                    processing_status="PENDING",
                    processing_error=None,
                )
            )
            db.commit()

            query = (
                select(FinancialRawFiling)
                .where(
                    FinancialRawFiling.processing_status == "PENDING"
                )
                .order_by(
                    FinancialRawFiling.period_end,
                    FinancialRawFiling.id,
                )
                .limit(batch_size)
            )

            if symbol_filter:
                query = query.where(
                    FinancialRawFiling.symbol == symbol_filter
                )

            raw_filings = db.scalars(query).all()

            if not raw_filings:
                break

            batch_filings = []

            # Claim this batch before doing filesystem/parser work.
            for raw_filing in raw_filings:
                raw_filing.processing_status = "PROCESSING"
                raw_filing.processing_error = None

            db.commit()

            # Copy everything needed outside the SQLAlchemy session.
            for raw_filing in raw_filings:
                batch_filings.append(
                    {
                        "id": raw_filing.id,
                        "company_id": raw_filing.company_id,
                        "symbol": raw_filing.symbol,
                        "period_end": raw_filing.period_end,
                        "statement_scope": raw_filing.statement_scope,
                        "submission_type": raw_filing.submission_type,
                        "audit_status": raw_filing.audit_status,
                        "xbrl_url": raw_filing.xbrl_url,
                        "source_reference": raw_filing.source_reference,
                        "raw_relative_path": raw_filing.raw_relative_path,
                    }
                )

        # ---------------------------------------------------------
        # Parse the batch outside the database transaction.
        # ---------------------------------------------------------
        all_statements: list[dict[str, Any]] = []
        successful_ids: list[int] = []
        failed_items: list[tuple[int, str]] = []

        for raw_filing in batch_filings:
            try:
                xml_path = (
                    RAW_ROOT / raw_filing["raw_relative_path"]
                )

                if not xml_path.exists():
                    raise FileNotFoundError(
                        f"Raw XML not found: {xml_path}"
                    )

                xml_text = xml_path.read_text(
                    encoding="utf-8"
                )

                filing = FinancialFiling(
                    symbol=raw_filing["symbol"],
                    company_name="",
                    period_end=raw_filing["period_end"],
                    submission_type=raw_filing["submission_type"],
                    audit_status=raw_filing["audit_status"],
                    statement_scope=raw_filing["statement_scope"],
                    details_url=None,
                    xbrl_url=raw_filing["xbrl_url"],
                    ixbrl_url=None,
                    broadcast_datetime=None,
                    revised_datetime=None,
                    revision_remarks=None,
                    source_reference=raw_filing["source_reference"],
                    raw={},
                )

                statements = client.parse_xbrl(
                    xml_text=xml_text,
                    filing=filing,
                )

                if not statements:
                    raise ValueError(
                        "XBRL parser returned no statements"
                    )

                for statement in statements:
                    statement["company_id"] = (
                        raw_filing["company_id"]
                    )

                all_statements.extend(statements)
                successful_ids.append(raw_filing["id"])

            except Exception as exc:
                error_text = str(exc)[:4000]

                failed_items.append(
                    (raw_filing["id"], error_text)
                )

                print(
                    f"Cached financial processing failed: "
                    f"{raw_filing['symbol']} "
                    f"{raw_filing['period_end']} "
                    f"{raw_filing['statement_scope']}: "
                    f"{exc}"
                )

        # ---------------------------------------------------------
        # Derive and persist statements for this batch.
        # ---------------------------------------------------------
        batch_statements = 0

        try:
            if all_statements:
                derive_quarterly_financials(
                    all_statements
                )

                batch_statements = save_financial_statements(
                    all_statements
                )

        except Exception as exc:
            # If database persistence fails for the batch,
            # don't mark those filings as successfully processed.
            error_text = (
                f"Batch persistence failed: {exc}"
            )[:4000]

            for filing_id in successful_ids:
                failed_items.append(
                    (filing_id, error_text)
                )

            successful_ids = []

        # ---------------------------------------------------------
        # Update statuses for this completed batch.
        # ---------------------------------------------------------
        with Session(engine) as db:
            now = datetime.now(timezone.utc)

            for filing_id in successful_ids:
                raw_filing = db.get(
                    FinancialRawFiling,
                    filing_id,
                )

                if raw_filing is not None:
                    raw_filing.processing_status = "PROCESSED"
                    raw_filing.processing_error = None
                    raw_filing.processed_at = now

            for filing_id, error_text in failed_items:
                raw_filing = db.get(
                    FinancialRawFiling,
                    filing_id,
                )

                if raw_filing is not None:
                    raw_filing.processing_status = "FAILED"
                    raw_filing.processing_error = error_text

            db.commit()

        batch_processed = len(successful_ids)
        batch_failed = len(failed_items)

        total_processed += batch_processed
        total_failed += batch_failed
        total_statements += batch_statements

        print(
            f"Cached financial batch complete: "
            f"batch={len(batch_filings)}, "
            f"processed={batch_processed}, "
            f"failed={batch_failed}, "
            f"statements={batch_statements}, "
            f"total_processed={total_processed}, "
            f"total_failed={total_failed}"
        )

    print(
        f"Cached financial processing complete: "
        f"processed={total_processed}, "
        f"failed={total_failed}, "
        f"statements={total_statements}"
    )

    return total_statements

def catalog_raw_financial_filings() -> int:
    """
    Register existing raw XBRL files in financial_raw_filings.

    The filesystem remains the immutable raw-data store.
    PostgreSQL stores the searchable catalog/index.
    """
    inserted = 0
    existing = 0
    skipped = 0

    with Session(engine) as session:
        company_cache: dict[str, int | None] = {}

        for xml_path, metadata_path, filing in iter_raw_filings():
            symbol = filing.symbol.strip().upper()

            # Resolve company once per symbol.
            if symbol not in company_cache:
                company = session.scalar(
                    select(Company).where(
                        Company.nse_symbol == symbol
                    )
                )
                company_cache[symbol] = (
                    company.id if company else None
                )

            company_id = company_cache[symbol]

            if company_id is None:
                skipped += 1
                print(
                    f"Raw catalog skipped: "
                    f"company not found: {symbol}"
                )
                continue

            xml_bytes = xml_path.read_bytes()
            sha256 = sha256_bytes(xml_bytes)
            file_size = len(xml_bytes)

            relative_path = xml_path.resolve().relative_to(
                RAW_ROOT.resolve()
            ).as_posix()

            existing_id = session.scalar(
                select(FinancialRawFiling.id).where(
                    FinancialRawFiling.company_id == company_id,
                    FinancialRawFiling.source_reference
                    == filing.source_reference,
                    FinancialRawFiling.sha256 == sha256,
                )
            )

            if existing_id is not None:
                existing += 1
                continue

            row = FinancialRawFiling(
                company_id=company_id,
                symbol=symbol,
                period_end=filing.period_end,
                filing_date=_effective_filing_date(
                    filing.broadcast_datetime,
                    filing.revised_datetime,
                ),
                statement_scope=filing.statement_scope,
                submission_type=filing.submission_type,
                audit_status=filing.audit_status,
                source_reference=filing.source_reference,
                xbrl_url=filing.xbrl_url,
                raw_relative_path=relative_path,
                sha256=sha256,
                file_size=file_size,
                processing_status="PENDING",
            )

            session.add(row)
            inserted += 1

            if inserted % 500 == 0:
                session.commit()
                print(
                    f"Raw catalog progress: "
                    f"inserted={inserted}, "
                    f"existing={existing}, "
                    f"skipped={skipped}"
                )

        session.commit()

    print(
        f"Raw catalog complete: "
        f"inserted={inserted}, "
        f"existing={existing}, "
        f"skipped={skipped}"
    )

    return inserted
