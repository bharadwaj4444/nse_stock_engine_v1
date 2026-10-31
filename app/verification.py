from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import text

from app.db import engine
from app.verification_history import save_verification_run

@dataclass(frozen=True)
class CheckResult:
    status: str
    name: str
    expected: int | None = None
    actual: int | None = None
    details: str = ""


def _coverage_status(expected: int, missing: int) -> str:
    if expected == 0:
        return "INFO"
    return "PASS" if missing == 0 else "FAIL"

def _completeness_status(total: int, missing: int) -> str:
    if total == 0:
        return "INFO"
    return "INFO" if missing > 0 else "PASS"

def _check_output(
    conn,
    target_date: date,
    table: str,
    date_column: str,
    scope_filter: str = "",
) -> CheckResult:
    # Table and column names are internal constants, not user input.
    query = text(f"""
        SELECT COUNT(*)
        FROM daily_prices dp
        JOIN companies c
          ON c.id = dp.company_id
         AND c.is_active = TRUE
        WHERE dp.trade_date = :target_date
          AND NOT EXISTS (
              SELECT 1
              FROM {table} output
              WHERE output.company_id = dp.company_id
                AND output.{date_column} = dp.trade_date
                {scope_filter}
          )
    """)

    missing = int(
        conn.execute(
            query, {"target_date": target_date}
        ).scalar_one()
    )

    expected = int(
        conn.execute(
            text("""
                SELECT COUNT(*)
                FROM daily_prices dp
                JOIN companies c
                  ON c.id = dp.company_id
                 AND c.is_active = TRUE
                WHERE dp.trade_date = :target_date
            """),
            {"target_date": target_date},
        ).scalar_one()
    )

    return CheckResult(
        status=_coverage_status(expected, missing),
        name=f"{table} coverage",
        expected=expected,
        actual=expected - missing,
        details=f"{missing} expected price-backed rows missing",
    )


def run_verification(target_date: date) -> list[CheckResult]:
    results: list[CheckResult] = []

    with engine.connect() as conn:
        input_stats = conn.execute(
            text("""
                SELECT
                    COUNT(*) AS price_rows,
                    COUNT(DISTINCT dp.company_id) AS priced_companies,
                    COUNT(DISTINCT dp.company_id)
                        FILTER (WHERE c.is_active) AS active_priced_companies,
                    (
                        SELECT COUNT(*)
                        FROM companies
                        WHERE is_active = TRUE
                    ) AS active_companies
                FROM daily_prices dp
                JOIN companies c ON c.id = dp.company_id
                WHERE dp.trade_date = :target_date
            """),
            {"target_date": target_date},
        ).mappings().one()

        price_rows = int(input_stats["price_rows"])
        active_priced = int(input_stats["active_priced_companies"])
        active_companies = int(input_stats["active_companies"])

        results.append(CheckResult(
            status="PASS" if price_rows > 0 else "FAIL",
            name="Daily price input",
            expected=None,
            actual=price_rows,
            details=(
                f"{active_priced} active companies priced; "
                f"{active_companies} active companies in universe"
            ),
        ))

        if price_rows == 0:
            results.append(CheckResult(
                status="INFO",
                name="Downstream checks",
                details="Skipped because no prices exist for this date",
            ))
            return results

        if active_priced < active_companies:
            missing_symbols = conn.execute(
                text("""
                    SELECT c.nse_symbol
                    FROM companies c
                    WHERE c.is_active = TRUE
                      AND NOT EXISTS (
                          SELECT 1
                          FROM daily_prices dp
                          WHERE dp.company_id = c.id
                            AND dp.trade_date = :target_date
                      )
                    ORDER BY c.nse_symbol
                """),
                {"target_date": target_date},
            ).scalars().all()

            symbols_text = ", ".join(missing_symbols)

            results.append(CheckResult(
                status="WARN",
                name="Active-universe price coverage",
                expected=active_companies,
                actual=active_priced,
                details=(
                    f"{active_companies - active_priced} active companies "
                    f"have no price row. Symbols: {symbols_text}"
                ),
            ))
        else:
            results.append(CheckResult(
                status="PASS",
                name="Active-universe price coverage",
                expected=active_companies,
                actual=active_priced,
            ))

        output_checks = [
            ("market_metrics", "trade_date", ""),
            ("historical_features", "trade_date",
             "AND output.statement_scope = 'Consolidated'"),
            ("historical_feature_scores", "trade_date",
             "AND output.statement_scope = 'Consolidated'"),
            ("stock_rankings", "trade_date",
             "AND output.statement_scope = 'Consolidated'"),
        ]

        for table, date_column, scope_filter in output_checks:
            results.append(
                _check_output(
                    conn,
                    target_date,
                    table,
                    date_column,
                    scope_filter,
                )
            )
        
        ratio_stats = conn.execute(
            text("""
                WITH eligible AS (
                    SELECT
                        dp.company_id,
                        t.period_end
                    FROM daily_prices dp
                    JOIN companies c
                      ON c.id = dp.company_id
                     AND c.is_active = TRUE
                    JOIN LATERAL (
                        SELECT
                            t.period_end,
                            t.latest_filing_date
                        FROM ttm_financials t
                        WHERE t.company_id = dp.company_id
                          AND t.statement_scope = 'Consolidated'
                          AND t.latest_filing_date <= dp.trade_date
                        ORDER BY
                            t.period_end DESC,
                            t.latest_filing_date DESC,
                            t.id DESC
                        LIMIT 1
                    ) t ON TRUE
                    WHERE dp.trade_date = :target_date
                      AND EXISTS (
                          SELECT 1
                          FROM market_metrics mm
                          WHERE mm.company_id = dp.company_id
                            AND mm.trade_date = dp.trade_date
                      )
                )
                SELECT
                    COUNT(*) AS eligible,
                    COUNT(*) FILTER (
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM financial_ratios r
                            WHERE r.company_id = eligible.company_id
                              AND r.period_end = eligible.period_end
                              AND r.statement_scope = 'Consolidated'
                        )
                    ) AS missing
                FROM eligible
            """),
            {"target_date": target_date},
        ).mappings().one()

        ratio_eligible = int(ratio_stats["eligible"])
        ratio_missing = int(ratio_stats["missing"])

        results.append(CheckResult(
            status=_coverage_status(ratio_eligible, ratio_missing),
            name="Eligible financial-ratio coverage",
            expected=ratio_eligible,
            actual=ratio_eligible - ratio_missing,
            details=(
                f"{ratio_missing} eligible companies lack a matching "
                "Consolidated financial-ratio row"
            ),
        ))

        valuation_stats = conn.execute(
            text("""
                SELECT
                    COUNT(*) AS eligible,
                    COUNT(*) FILTER (
                        WHERE NOT EXISTS (
                            SELECT 1
                            FROM valuation_metrics v
                            WHERE v.company_id = dp.company_id
                              AND v.valuation_date = dp.trade_date
                              AND v.statement_scope = 'Consolidated'
                        )
                    ) AS missing
                FROM daily_prices dp
                JOIN companies c
                  ON c.id = dp.company_id
                 AND c.is_active = TRUE
                WHERE dp.trade_date = :target_date
                  AND EXISTS (
                      SELECT 1
                      FROM market_metrics mm
                      WHERE mm.company_id = dp.company_id
                        AND mm.trade_date = dp.trade_date
                  )
                  AND EXISTS (
                      SELECT 1
                      FROM ttm_financials t
                      WHERE t.company_id = dp.company_id
                        AND t.statement_scope = 'Consolidated'
                        AND t.latest_filing_date <= dp.trade_date
                  )
            """),
            {"target_date": target_date},
        ).mappings().one()

        eligible = int(valuation_stats["eligible"])
        missing_valuations = int(valuation_stats["missing"])

        results.append(CheckResult(
            status=_coverage_status(eligible, missing_valuations),
            name="Eligible valuation coverage",
            expected=eligible,
            actual=eligible - missing_valuations,
            details=(
                f"{missing_valuations} eligible companies missing a "
                "Consolidated valuation"
            ),
        ))

        valuation_field_stats = conn.execute(
            text("""
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE pe_ratio IS NULL
                    ) AS missing_pe,
                    COUNT(*) FILTER (
                        WHERE ev_to_ebitda IS NULL
                    ) AS missing_ev_ebitda,
                    COUNT(*) FILTER (
                        WHERE price_to_fcf IS NULL
                    ) AS missing_price_to_fcf,
                    COUNT(*) FILTER (
                        WHERE fcf_yield IS NULL
                    ) AS missing_fcf_yield
                FROM valuation_metrics
                WHERE valuation_date = :target_date
                  AND statement_scope = 'Consolidated'
            """),
            {"target_date": target_date},
        ).mappings().one()

        valuation_total = int(valuation_field_stats["total"])

        valuation_fields = [
            ("P/E", "missing_pe"),
            ("EV/EBITDA", "missing_ev_ebitda"),
            ("Price-to-FCF", "missing_price_to_fcf"),
            ("FCF yield", "missing_fcf_yield"),
        ]

        for field_name, missing_key in valuation_fields:
            missing = int(valuation_field_stats[missing_key])

            results.append(CheckResult(
                status=_completeness_status(valuation_total, missing),
                name=f"{field_name} availability",
                expected=valuation_total,
                actual=valuation_total - missing,
                details=(
                    f"{missing} of {valuation_total} valuation rows "
                    f"have NULL {field_name}; NULL values may be legitimate "
                    "when the required inputs are unavailable"
                ),
            ))

        cash_flow_stats = conn.execute(
            text("""
                SELECT
                    COUNT(*) AS total_quarters,
                    COUNT(*) FILTER (
                        WHERE operating_cash_flow IS NULL
                           OR capital_expenditure IS NULL
                           OR free_cash_flow IS NULL
                    ) AS incomplete_quarters
                FROM financial_statements_canonical
                WHERE period_type = 'quarterly'
                  AND statement_scope = 'Consolidated'
                  AND rn = 1
            """)
        ).mappings().one()

        total_quarters = int(cash_flow_stats["total_quarters"])
        incomplete_quarters = int(cash_flow_stats["incomplete_quarters"])

        results.append(CheckResult(
            status=(
                "WARN"
                if incomplete_quarters > 0
                else "PASS"
            ),
            name="Quarterly cash-flow coverage",
            expected=total_quarters,
            actual=total_quarters - incomplete_quarters,
            details=(
                f"{incomplete_quarters} of {total_quarters} quarterly "
                "statements have at least one missing cash-flow field; "
                "this is a coverage warning, not proof of a code defect"
            ),
        ))

    return results


def print_report(
    target_date: date,
    trigger: str = "verify",
) -> bool:
    started_at = datetime.now(timezone.utc)

    results = run_verification(target_date)

    completed_at = datetime.now(timezone.utc)

    failures = sum(r.status == "FAIL" for r in results)
    warnings = sum(r.status == "WARN" for r in results)

    print(f"\nVerification report: {target_date}")
    print("-" * 78)

    for result in results:
        counts = ""
        if result.expected is not None:
            counts = f" [{result.actual}/{result.expected}]"

        details = f" - {result.details}" if result.details else ""
        print(
            f"{result.status:4} | {result.name}{counts}{details}"
        )

    print("-" * 78)
    print(
        f"Failures: {failures}; warnings: {warnings}; "
        f"checks: {len(results)}"
    )

    run_id = save_verification_run(
        target_date=target_date,
        results=results,
        trigger=trigger,
        started_at=started_at,
        completed_at=completed_at,
    )

    print(f"Verification history saved (run ID: {run_id})")

    return failures == 0
