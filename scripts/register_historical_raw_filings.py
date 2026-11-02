
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Company, FinancialRawFiling
from app.financial_raw import RAW_ROOT, iter_raw_filings


IST = timezone(timedelta(hours=5, minutes=30))

# Verified historical NSE symbol changes.
HISTORICAL_SYMBOL_MAP = {
    "GFSTEELS": 2349,    # Grand Foundry -> TIKONA
    "ICICIPRULI": 1007,  # ICICI Prudential Life -> ICICILIFE
}


def normalize(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def parse_nse_datetime(value):
    value = normalize(value)
    if not value:
        return None

    try:
        parsed = datetime.strptime(value, "%d-%b-%Y %H:%M:%S")
    except ValueError:
        parsed = datetime.fromisoformat(value)

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=IST)

    return parsed


def relative_raw_path(xml_path: Path) -> str:
    return xml_path.resolve().relative_to(
        RAW_ROOT.resolve()
    ).as_posix()


def main():
    parser = argparse.ArgumentParser(
        description="Register verified historical NSE raw filings."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist registrations. Without this flag, run a dry-run.",
    )
    args = parser.parse_args()

    inserted = 0
    existing = 0
    skipped = 0
    errors = 0

    with SessionLocal() as db:
        company_rows = db.scalars(
            select(Company).where(
                Company.id.in_(list(HISTORICAL_SYMBOL_MAP.values()))
            )
        ).all()

        companies = {row.id: row for row in company_rows}

        for symbol, company_id in HISTORICAL_SYMBOL_MAP.items():
            company = companies.get(company_id)

            if company is None:
                raise RuntimeError(
                    f"Mapped company ID does not exist: "
                    f"{symbol} -> {company_id}"
                )

            print(
                f"Mapping verified: {symbol} -> "
                f"{company.nse_symbol} ({company.company_name})"
            )

        for xml_path, metadata_path, filing in iter_raw_filings():
            symbol = filing.symbol.strip().upper()

            if symbol not in HISTORICAL_SYMBOL_MAP:
                continue

            company_id = HISTORICAL_SYMBOL_MAP[symbol]

            try:
                # Validate XML and sidecar integrity.
                xml_bytes = xml_path.read_bytes()
                actual_hash = hashlib.sha256(xml_bytes).hexdigest()
                actual_size = len(xml_bytes)

                import json

                metadata = json.loads(
                    metadata_path.read_text(encoding="utf-8")
                )

                if metadata.get("sha256") != actual_hash:
                    raise ValueError("SHA-256 mismatch")

                if metadata.get("file_size") != actual_size:
                    raise ValueError("File-size mismatch")

                if normalize(metadata.get("symbol")).upper() != symbol:
                    raise ValueError("Sidecar symbol mismatch")

                if str(metadata.get("source_reference")) != str(
                    filing.source_reference
                ):
                    raise ValueError("Source reference mismatch")

                broadcast = parse_nse_datetime(
                    filing.broadcast_datetime
                )
                revised = parse_nse_datetime(
                    filing.revised_datetime
                )

                # A filing should have at least one effective timestamp.
                if broadcast is None and revised is None:
                    raise ValueError(
                        "Missing broadcast and revision timestamps"
                    )

                raw_path = relative_raw_path(xml_path)

                existing_row = db.scalar(
                    select(FinancialRawFiling).where(
                        FinancialRawFiling.company_id == company_id,
                        FinancialRawFiling.source_reference
                        == filing.source_reference,
                        FinancialRawFiling.sha256 == actual_hash,
                    )
                )

                if existing_row is not None:
                    # Existing records are deliberately not modified.
                    existing += 1
                    action = "EXISTS"
                else:
                    row = FinancialRawFiling(
                        company_id=company_id,
                        symbol=symbol,
                        period_end=filing.period_end,
                        filing_date=(
                            revised or broadcast
                        ).date(),
                        statement_scope=filing.statement_scope,
                        submission_type=filing.submission_type,
                        audit_status=filing.audit_status,
                        source_reference=filing.source_reference,
                        broadcast_datetime=broadcast,
                        revised_datetime=revised,
                        revision_remarks=normalize(
                            filing.revision_remarks
                        ),
                        xbrl_url=filing.xbrl_url,
                        raw_relative_path=raw_path,
                        sha256=actual_hash,
                        file_size=actual_size,
                        processing_status="PENDING",
                    )

                    if args.apply:
                        db.add(row)
                        db.flush()

                    inserted += 1
                    action = "INSERTED" if args.apply else "WOULD_INSERT"

                print({
                    "symbol": symbol,
                    "company_id": company_id,
                    "period_end": filing.period_end,
                    "scope": filing.statement_scope,
                    "source_reference": filing.source_reference,
                    "broadcast": broadcast,
                    "revised": revised,
                    "remarks": normalize(filing.revision_remarks),
                    "action": action,
                    "xml": xml_path.name,
                })

            except Exception as exc:
                errors += 1
                print(
                    f"ERROR: symbol={symbol}, "
                    f"file={xml_path.name}, error={exc}"
                )

        if args.apply:
            if errors:
                db.rollback()
                raise RuntimeError(
                    f"Registration aborted: {errors} validation errors. "
                    "No registrations were committed."
                )

            db.commit()
        else:
            db.rollback()

    print("\n--- Registration summary ---")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"Inserted / would insert: {inserted}")
    print(f"Already existing: {existing}")
    print(f"Skipped: {skipped}")
    print(f"Errors: {errors}")


if __name__ == "__main__":
    main()
