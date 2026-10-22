from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import text

from app.db import engine


PERCENT_FIELDS = {
    "promoter_pct": "promoter_shares",
    "public_pct": "public_shares",
    "non_promoter_non_public_pct": "non_promoter_non_public_shares",
    "government_pct": "government_shares",
    "domestic_institutions_pct": "domestic_institutions_shares",
    "foreign_institutions_pct": "foreign_institutions_shares",
    "non_institutions_pct": "non_institutions_shares",
    "mutual_funds_pct": "mutual_funds_shares",
    "venture_capital_funds_pct": "venture_capital_funds_shares",
    "alternative_investment_funds_pct": "alternative_investment_funds_shares",
    "banks_pct": "banks_shares",
    "insurance_companies_pct": "insurance_companies_shares",
    "provident_pension_funds_pct": "provident_pension_funds_shares",
    "fdi_pct": "fdi_shares",
    "foreign_vc_investors_pct": "foreign_vc_investors_shares",
    "foreign_sovereign_wealth_funds_pct": "foreign_sovereign_wealth_funds_shares",
    "fpi_category_i_pct": "fpi_category_i_shares",
    "fpi_category_ii_pct": "fpi_category_ii_shares",
    "overseas_depositories_pct": "overseas_depositories_shares",
    "resident_individuals_upto_2l_pct": "resident_individuals_upto_2l_shares",
    "resident_individuals_above_2l_pct": "resident_individuals_above_2l_shares",
    "nris_pct": "nris_shares",
    "foreign_nationals_pct": "foreign_nationals_shares",
    "foreign_companies_pct": "foreign_companies_shares",
    "bodies_corporate_pct": "bodies_corporate_shares",
    "other_non_institutions_pct": "other_non_institutions_shares",
}


def _percentage(
    shares: int | None,
    total_shares: int,
) -> Decimal | None:
    if shares is None:
        return None

    if total_shares <= 0:
        raise ValueError(
            f"total_shares must be positive, got {total_shares}"
        )

    return (
        Decimal(shares)
        * Decimal("100")
        / Decimal(total_shares)
    ).quantize(
        Decimal("0.000001"),
        rounding=ROUND_HALF_UP,
    )


def calculate_shareholding_metrics(
    company_id: int,
    effective_date: date,
) -> dict:
    query = text(
        """
        SELECT
            company_id,
            effective_date,
            total_shares,
            promoter_shares,
            public_shares,
            non_promoter_non_public_shares,
            government_shares,
            domestic_institutions_shares,
            foreign_institutions_shares,
            non_institutions_shares,
            mutual_funds_shares,
            venture_capital_funds_shares,
            alternative_investment_funds_shares,
            banks_shares,
            insurance_companies_shares,
            provident_pension_funds_shares,
            fdi_shares,
            foreign_vc_investors_shares,
            foreign_sovereign_wealth_funds_shares,
            fpi_category_i_shares,
            fpi_category_ii_shares,
            overseas_depositories_shares,
            resident_individuals_upto_2l_shares,
            resident_individuals_above_2l_shares,
            nris_shares,
            foreign_nationals_shares,
            foreign_companies_shares,
            bodies_corporate_shares,
            other_non_institutions_shares,
            source
        FROM shareholding_snapshots
        WHERE company_id = :company_id
          AND effective_date = :effective_date
        """
    )

    with engine.connect() as conn:
        row = conn.execute(
            query,
            {
                "company_id": company_id,
                "effective_date": effective_date,
            },
        ).mappings().first()

    if row is None:
        raise ValueError(
            f"No shareholding snapshot found for "
            f"company_id={company_id}, "
            f"effective_date={effective_date}"
        )

    total_shares = int(row["total_shares"])

    result = {
        "company_id": row["company_id"],
        "effective_date": row["effective_date"],
        "total_shares": total_shares,
        "source": row["source"],
        "calculation_method": "NSE_SHAREHOLDING_PERCENTAGE",
    }

    for pct_field, shares_field in PERCENT_FIELDS.items():
        result[pct_field] = _percentage(
            row[shares_field],
            total_shares,
        )

    return result

def save_shareholding_metrics(metrics: dict) -> None:
    columns = [
        "company_id",
        "effective_date",
        "total_shares",
        *PERCENT_FIELDS.keys(),
        "source",
        "calculation_method",
    ]

    values = ", ".join(f":{column}" for column in columns)

    update_columns = [
        "total_shares",
        *PERCENT_FIELDS.keys(),
        "source",
        "calculation_method",
        "updated_at",
    ]

    updates = ", ".join(
        f"{column} = EXCLUDED.{column}"
        for column in update_columns
        if column != "updated_at"
    )

    query = text(
        f"""
        INSERT INTO shareholding_metrics (
            {", ".join(columns)}
        )
        VALUES (
            {values}
        )
        ON CONFLICT (company_id, effective_date)
        DO UPDATE SET
            {updates},
            updated_at = NOW()
        """
    )

    with engine.begin() as conn:
        conn.execute(query, metrics)

def build_shareholding_metrics(
    batch_size: int = 500,
) -> dict[str, int]:
    select_query = text(
        """
        SELECT
            company_id,
            effective_date,
            total_shares,
            promoter_shares,
            public_shares,
            non_promoter_non_public_shares,
            government_shares,
            domestic_institutions_shares,
            foreign_institutions_shares,
            non_institutions_shares,
            mutual_funds_shares,
            venture_capital_funds_shares,
            alternative_investment_funds_shares,
            banks_shares,
            insurance_companies_shares,
            provident_pension_funds_shares,
            fdi_shares,
            foreign_vc_investors_shares,
            foreign_sovereign_wealth_funds_shares,
            fpi_category_i_shares,
            fpi_category_ii_shares,
            overseas_depositories_shares,
            resident_individuals_upto_2l_shares,
            resident_individuals_above_2l_shares,
            nris_shares,
            foreign_nationals_shares,
            foreign_companies_shares,
            bodies_corporate_shares,
            other_non_institutions_shares,
            source
        FROM shareholding_snapshots
        ORDER BY company_id, effective_date
        """
    )

    insert_query = text(
        """
        INSERT INTO shareholding_metrics (
            company_id,
            effective_date,
            total_shares,
            promoter_pct,
            public_pct,
            non_promoter_non_public_pct,
            government_pct,
            domestic_institutions_pct,
            foreign_institutions_pct,
            non_institutions_pct,
            mutual_funds_pct,
            venture_capital_funds_pct,
            alternative_investment_funds_pct,
            banks_pct,
            insurance_companies_pct,
            provident_pension_funds_pct,
            fdi_pct,
            foreign_vc_investors_pct,
            foreign_sovereign_wealth_funds_pct,
            fpi_category_i_pct,
            fpi_category_ii_pct,
            overseas_depositories_pct,
            resident_individuals_upto_2l_pct,
            resident_individuals_above_2l_pct,
            nris_pct,
            foreign_nationals_pct,
            foreign_companies_pct,
            bodies_corporate_pct,
            other_non_institutions_pct,
            source,
            calculation_method
        )
        VALUES (
            :company_id,
            :effective_date,
            :total_shares,
            :promoter_pct,
            :public_pct,
            :non_promoter_non_public_pct,
            :government_pct,
            :domestic_institutions_pct,
            :foreign_institutions_pct,
            :non_institutions_pct,
            :mutual_funds_pct,
            :venture_capital_funds_pct,
            :alternative_investment_funds_pct,
            :banks_pct,
            :insurance_companies_pct,
            :provident_pension_funds_pct,
            :fdi_pct,
            :foreign_vc_investors_pct,
            :foreign_sovereign_wealth_funds_pct,
            :fpi_category_i_pct,
            :fpi_category_ii_pct,
            :overseas_depositories_pct,
            :resident_individuals_upto_2l_pct,
            :resident_individuals_above_2l_pct,
            :nris_pct,
            :foreign_nationals_pct,
            :foreign_companies_pct,
            :bodies_corporate_pct,
            :other_non_institutions_pct,
            :source,
            :calculation_method
        )
        ON CONFLICT (company_id, effective_date)
        DO UPDATE SET
            total_shares = EXCLUDED.total_shares,
            promoter_pct = EXCLUDED.promoter_pct,
            public_pct = EXCLUDED.public_pct,
            non_promoter_non_public_pct = EXCLUDED.non_promoter_non_public_pct,
            government_pct = EXCLUDED.government_pct,
            domestic_institutions_pct = EXCLUDED.domestic_institutions_pct,
            foreign_institutions_pct = EXCLUDED.foreign_institutions_pct,
            non_institutions_pct = EXCLUDED.non_institutions_pct,
            mutual_funds_pct = EXCLUDED.mutual_funds_pct,
            venture_capital_funds_pct = EXCLUDED.venture_capital_funds_pct,
            alternative_investment_funds_pct = EXCLUDED.alternative_investment_funds_pct,
            banks_pct = EXCLUDED.banks_pct,
            insurance_companies_pct = EXCLUDED.insurance_companies_pct,
            provident_pension_funds_pct = EXCLUDED.provident_pension_funds_pct,
            fdi_pct = EXCLUDED.fdi_pct,
            foreign_vc_investors_pct = EXCLUDED.foreign_vc_investors_pct,
            foreign_sovereign_wealth_funds_pct = EXCLUDED.foreign_sovereign_wealth_funds_pct,
            fpi_category_i_pct = EXCLUDED.fpi_category_i_pct,
            fpi_category_ii_pct = EXCLUDED.fpi_category_ii_pct,
            overseas_depositories_pct = EXCLUDED.overseas_depositories_pct,
            resident_individuals_upto_2l_pct = EXCLUDED.resident_individuals_upto_2l_pct,
            resident_individuals_above_2l_pct = EXCLUDED.resident_individuals_above_2l_pct,
            nris_pct = EXCLUDED.nris_pct,
            foreign_nationals_pct = EXCLUDED.foreign_nationals_pct,
            foreign_companies_pct = EXCLUDED.foreign_companies_pct,
            bodies_corporate_pct = EXCLUDED.bodies_corporate_pct,
            other_non_institutions_pct = EXCLUDED.other_non_institutions_pct,
            source = EXCLUDED.source,
            calculation_method = EXCLUDED.calculation_method,
            updated_at = NOW()
        """
    )

    processed = 0
    failed = 0

    with engine.connect() as conn:
        result = conn.execute(select_query)
        mapping_result = result.mappings()
        rows = mapping_result.fetchmany(batch_size)

        while rows:
            metrics_batch = []

            for row in rows:
                try:
                    total_shares = int(row["total_shares"])

                    metrics = {
                        "company_id": row["company_id"],
                        "effective_date": row["effective_date"],
                        "total_shares": total_shares,
                        "source": row["source"],
                        "calculation_method":
                            "NSE_SHAREHOLDING_PERCENTAGE",
                    }

                    for pct_field, shares_field in PERCENT_FIELDS.items():
                        metrics[pct_field] = _percentage(
                            row[shares_field],
                            total_shares,
                        )

                    metrics_batch.append(metrics)
                    processed += 1

                except Exception as exc:
                    failed += 1
                    print(
                        f"FAILED company_id={row['company_id']} "
                        f"date={row['effective_date']}: {exc}"
                    )

            if metrics_batch:
                with engine.begin() as write_conn:
                    write_conn.execute(
                        insert_query,
                        metrics_batch,
                    )

            rows = mapping_result.fetchmany(batch_size)

    return {
        "processed": processed,
        "failed": failed,
    }