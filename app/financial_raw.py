from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from app.config import settings
from app.sources.nse_financials import FinancialFiling


RAW_ROOT = Path(settings.raw_data_dir) / "financial_xbrl"


def _safe_name(value: str) -> str:
    value = str(value or "").strip()
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    return value.strip("._-") or "unknown"


def _scope_name(scope: str) -> str:
    scope = str(scope or "Unknown").strip()

    if scope.lower().startswith("consol"):
        return "Consolidated"

    if scope.lower().startswith("stand"):
        return "Standalone"

    return _safe_name(scope)


def _url_filename(url: str) -> str:
    path = urlparse(url).path
    name = Path(path).name

    if not name:
        name = "financial_filing.xml"

    name = _safe_name(name)

    if not name.lower().endswith(".xml"):
        name += ".xml"

    return name


def filing_directory(filing: FinancialFiling) -> Path:
    return (
        RAW_ROOT
        / _safe_name(filing.symbol.upper())
        / filing.period_end.isoformat()
        / _scope_name(filing.statement_scope)
    )


def filing_base_name(
    filing: FinancialFiling,
    xml_bytes: bytes | None = None,
) -> str:
    """
    Build a stable raw filing name.

    The NSE URL basename identifies the filing, while the SHA-256
    suffix distinguishes revisions/content changes.
    """

    base = _url_filename(
        filing.xbrl_url
        or filing.source_reference
        or "financial_filing.xml"
    )

    stem = Path(base).stem

    if xml_bytes is not None:
        digest = hashlib.sha256(xml_bytes).hexdigest()[:16]
        return f"{stem}__{digest}"

    return stem


def filing_metadata_path(
    filing: FinancialFiling,
    xml_bytes: bytes | None = None,
) -> Path:
    directory = filing_directory(filing)

    base = filing_base_name(
        filing,
        xml_bytes,
    )

    return directory / f"{base}.json"


def filing_xml_base_path(
    filing: FinancialFiling,
    xml_bytes: bytes,
) -> Path:
    directory = filing_directory(filing)

    base = filing_base_name(
        filing,
        xml_bytes,
    )

    return directory / f"{base}.xml"

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def save_raw_filing(
    filing: FinancialFiling,
    xml_bytes: bytes,
) -> tuple[Path, Path, bool]:
    """
    Save an NSE XBRL filing as an immutable raw artifact.

    Returns:
        (xml_path, metadata_path, already_exists)
    """

    xml_path = filing_xml_base_path(filing, xml_bytes)
    metadata_path = filing_metadata_path(
        filing,
        xml_bytes,
    )

    xml_path.parent.mkdir(parents=True, exist_ok=True)

    already_exists = xml_path.exists()

    if not already_exists:
        xml_path.write_bytes(xml_bytes)

    metadata: dict[str, Any] = asdict(filing)

    metadata["period_end"] = (
        filing.period_end.isoformat()
        if isinstance(filing.period_end, date)
        else filing.period_end
    )

    metadata["raw_xml_path"] = str(xml_path)
    metadata["sha256"] = sha256_bytes(xml_bytes)
    metadata["file_size"] = len(xml_bytes)

    metadata_path.write_text(
        json.dumps(
            metadata,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    return xml_path, metadata_path, already_exists


def load_filing_metadata(
    metadata_path: Path,
) -> FinancialFiling:
    data = json.loads(
        metadata_path.read_text(encoding="utf-8")
    )

    period_end = data["period_end"]

    if isinstance(period_end, str):
        period_end = date.fromisoformat(period_end)

    return FinancialFiling(
        symbol=data["symbol"],
        company_name=data["company_name"],
        period_end=period_end,
        submission_type=data["submission_type"],
        audit_status=data.get("audit_status"),
        statement_scope=data["statement_scope"],
        details_url=data.get("details_url"),
        xbrl_url=data.get("xbrl_url"),
        ixbrl_url=data.get("ixbrl_url"),
        broadcast_datetime=data.get("broadcast_datetime"),
        revised_datetime=data.get("revised_datetime"),
        revision_remarks=data.get("revision_remarks"),
        source_reference=data.get("source_reference"),
        raw=data.get("raw") or {},
    )


def iter_raw_filings():
    """
    Yield (xml_path, metadata_path, filing) for all locally
    cached NSE XBRL filings.
    """

    if not RAW_ROOT.exists():
        return

    for metadata_path in sorted(RAW_ROOT.rglob("*.json")):
        try:
            data = json.loads(
                metadata_path.read_text(encoding="utf-8")
            )
        except Exception:
            continue

        xml_path_value = data.get("raw_xml_path")

        if not xml_path_value:
            continue

        xml_path = Path(xml_path_value)

        if not xml_path.is_absolute():
            xml_path = Path.cwd() / xml_path

        if not xml_path.exists():
            continue

        try:
            filing = load_filing_metadata(metadata_path)
        except Exception:
            continue

        yield xml_path, metadata_path, filing

def process_raw_filings():
    """
    Iterate over all cached raw financial XBRL files.

    Yields:
        tuple[Path, Path, FinancialFiling]:
            xml_path, metadata_path, filing
    """
    yield from iter_raw_filings()