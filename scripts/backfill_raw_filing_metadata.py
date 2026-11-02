from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import text

from app.config import settings
from app.db import SessionLocal


RAW_ROOT = Path(settings.raw_data_dir) / "financial_xbrl"
IST = timezone(timedelta(hours=5, minutes=30))

FIELDS = (
    "broadcast_datetime",
    "revised_datetime",
    "revision_remarks",
)


def normalize(value) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def parse_nse_datetime(value: str | None):
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


def load_metadata(row):
    xml_path = RAW_ROOT / Path(row["raw_relative_path"])
    json_path = xml_path.with_suffix(".json")

    if not json_path.is_file():
        raise ValueError(f"Missing JSON sidecar: {json_path}")

    data = json.loads(json_path.read_text(encoding="utf-8"))

    if normalize(data.get("symbol", "")).upper() != row["symbol"].upper():
        raise ValueError("Symbol mismatch")

    if normalize(data.get("source_reference")) != normalize(row["source_reference"]):
        raise ValueError("Source reference mismatch")

    return {
        "broadcast_datetime": parse_nse_datetime(data.get("broadcast_datetime")),
        "revised_datetime": parse_nse_datetime(data.get("revised_datetime")),
        "revision_remarks": normalize(data.get("revision_remarks")),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Backfill raw filing revision metadata from JSON sidecars."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates. Without this flag, the script performs a dry run.",
    )
    args = parser.parse_args()

    counts = Counter()
    examples = Counter()
    updates = []

    print(f"Raw filing directory: {RAW_ROOT.resolve()}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")

    with SessionLocal() as session:
        rows = session.execute(
            text("""
                SELECT
                    id,
                    symbol,
                    source_reference,
                    raw_relative_path,
                    broadcast_datetime,
                    revised_datetime,
                    revision_remarks
                FROM financial_raw_filings
                ORDER BY id
            """)
        ).mappings().all()

        counts["database_records"] = len(rows)

        for row in rows:
            counts["records_checked"] += 1

            try:
                incoming = load_metadata(row)
            except Exception as exc:
                counts["sidecar_or_mapping_errors"] += 1
                if examples["sidecar_or_mapping_errors"] < 5:
                    print(
                        f"ERROR id={row['id']} symbol={row['symbol']}: {exc}"
                    )
                    examples["sidecar_or_mapping_errors"] += 1
                continue

            counts["sidecars_loaded"] += 1
            has_candidate = False
            has_conflict = False

            for field in FIELDS:
                new_value = incoming[field]
                old_value = row[field]

                if new_value is None:
                    continue

                has_candidate = True

                if old_value is None:
                    counts[f"{field}_to_fill"] += 1
                elif old_value == new_value:
                    counts[f"{field}_already_matching"] += 1
                else:
                    counts[f"{field}_conflicts"] += 1
                    has_conflict = True

            if not has_candidate:
                counts["records_without_metadata"] += 1
                continue

            if has_conflict:
                counts["records_with_conflicts"] += 1
                continue

            if any(
                incoming[field] is not None and row[field] is None
                for field in FIELDS
            ):
                updates.append({
                    "id": row["id"],
                    **incoming,
                })

        counts["records_eligible_for_update"] = len(updates)

        print("\n========== BACKFILL SUMMARY ==========")
        for key, value in sorted(counts.items()):
            print(f"{key:40} {value:>10}")

        if not args.apply:
            print("\nDry run complete. No database modifications were made.")
            return

        if not updates:
            print("\nNo updates required.")
            return

        result = session.execute(
            text("""
                UPDATE financial_raw_filings
                SET
                    broadcast_datetime =
                        COALESCE(broadcast_datetime, :broadcast_datetime),
                    revised_datetime =
                        COALESCE(revised_datetime, :revised_datetime),
                    revision_remarks =
                        COALESCE(revision_remarks, :revision_remarks)
                WHERE id = :id
            """),
            updates,
        )

        session.commit()

        print(f"\nDatabase rows updated: {result.rowcount}")
        print("Backfill committed successfully.")


if __name__ == "__main__":
    main()
