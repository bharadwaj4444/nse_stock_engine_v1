from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any

import requests


API_URL = "https://www.nseindia.com/api/corporate-share-holdings-master"
REFERER = (
    "https://www.nseindia.com/"
    "companies-listing/corporate-filings-shareholding-pattern"
)
XBRL_HOST = "https://nsearchives.nseindia.com"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/153.0.0.0 Safari/537.36"
)


@dataclass(frozen=True)
class ShareholdingFiling:
    symbol: str
    effective_date: date
    submission_date: date | None
    revision_date: date | None
    revised: bool
    xbrl_url: str
    total_shares: int
    source: str = "NSE"
    calculation_method: str = "NSE_SHAREHOLDING_PATTERN"


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None

    value = str(value).strip()
    if not value:
        return None

    formats = (
        "%d-%b-%Y",
        "%d-%B-%Y",
        "%d-%m-%Y",
        "%Y-%m-%d",
        "%d/%m/%Y",
    )

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    return None


def _absolute_xbrl_url(value: str) -> str:
    value = (value or "").strip()

    if not value:
        return ""

    if value.upper() in {
        "-",
        "NA",
        "N/A",
        "NULL",
        "NONE",
    }:
        return ""

    if value.rstrip("/").endswith("/-"):
        return ""

    if value.startswith("http://") or value.startswith("https://"):
        return value

    if value.startswith("//"):
        return "https:" + value

    if value.startswith("/"):
        return XBRL_HOST + value

    return XBRL_HOST + "/" + value


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]

    if ":" in tag:
        return tag.rsplit(":", 1)[1]

    return tag


def _context_members(root: ET.Element) -> dict[str, set[str]]:
    contexts: dict[str, set[str]] = {}

    for element in root.iter():
        if _local_name(element.tag) != "context":
            continue

        context_id = element.attrib.get("id")
        if not context_id:
            continue

        members: set[str] = set()

        for child in element.iter():
            name = _local_name(child.tag)

            if name in {
                "explicitMember",
                "typedMember",
            }:
                text = "".join(child.itertext()).strip()

                if text:
                    members.add(text)

                dimension = child.attrib.get("dimension")
                if dimension:
                    members.add(dimension)

        contexts[context_id] = members

    return contexts


def _number_of_shares_facts(
    root: ET.Element,
) -> list[tuple[str, int]]:
    facts: list[tuple[str, int]] = []

    for element in root.iter():
        if _local_name(element.tag) != "NumberOfShares":
            continue

        context_ref = element.attrib.get("contextRef")
        if not context_ref:
            continue

        raw = "".join(element.itertext()).strip()

        if not raw:
            continue

        try:
            value = Decimal(raw)
        except Exception:
            continue

        if value <= 0:
            continue

        facts.append((context_ref, int(value)))

    return facts


def _extract_total_shares(xml_bytes: bytes) -> int | None:
    """
    Extract total shares from the SHP XBRL.

    Priority:
    1. Explicit NumberOfShares in ShareholdingPattern context.
    2. NumberOfShares associated with ShareholdingPatternMember.
    3. Undimensioned NumberOfShares.
    4. Promoter + Public shareholding fallback.
    """

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return _extract_total_shares_regex(xml_bytes)

    contexts = _context_members(root)
    facts = _number_of_shares_facts(root)

    # 1. Primary: explicit NumberOfShares in the standard
    # ShareholdingPattern context.
    for context_ref, value in facts:
        if context_ref == "ShareholdingPattern_ContextI":
            return value

    # 2. Some issuers may use a different context ID but
    # still associate NumberOfShares with ShareholdingPatternMember.
    shareholding_pattern_members = {
        "in-bse-shp:ShareholdingPatternMember",
        "ShareholdingPatternMember",
    }

    for context_ref, value in facts:
        members = contexts.get(context_ref, set())

        if any(member in shareholding_pattern_members for member in members):
            return value

    # 3. Secondary fallback: undimensioned NumberOfShares.
    candidates: list[int] = []

    for context_ref, value in facts:
        members = contexts.get(context_ref, set())

        if not members:
            candidates.append(value)

    if candidates:
        return max(candidates)

    # 4. Final fallback: promoter + public shareholding.
    promoter_members = {
        "in-bse-shp:ShareholdingOfPromoterAndPromoterGroupMember",
        "ShareholdingOfPromoterAndPromoterGroupMember",
        "in-bse-shp:PromoterAndPromoterGroupMember",
        "PromoterAndPromoterGroupMember",
        "in-bse-shp:PromoterMember",
        "PromoterMember",
    }

    public_members = {
        "in-bse-shp:PublicShareholdingMember",
        "PublicShareholdingMember",
        "in-bse-shp:PublicMember",
        "PublicMember",
    }

    promoter_values: list[int] = []
    public_values: list[int] = []

    for context_ref, value in facts:
        members = contexts.get(context_ref, set())

        if any(member in members for member in promoter_members):
            promoter_values.append(value)

        if any(member in members for member in public_members):
            public_values.append(value)

    if promoter_values and public_values:
        return max(promoter_values) + max(public_values)

    return None

def _extract_total_shares_regex(xml_bytes: bytes) -> int | None:
    """
    Conservative fallback for malformed/older XBRL.

    Looks for NumberOfShares facts and returns the largest value.
    It is deliberately not used before the structured XML parser.
    """

    text = xml_bytes.decode("utf-8", errors="replace")

    pattern = re.compile(
        r"<[^>]*NumberOfShares"
        r"(?:\s+[^>]*)?>"
        r"\s*([0-9]+(?:\.[0-9]+)?)"
        r"\s*</[^>]*NumberOfShares>",
        re.IGNORECASE,
    )

    values: list[int] = []

    for match in pattern.finditer(text):
        try:
            values.append(int(Decimal(match.group(1))))
        except Exception:
            pass

    return max(values) if values else None


class NSEShareholdingClient:
    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = 4,
        throttle_seconds: float = 1.0,
    ) -> None:
        self.timeout = timeout
        self.max_retries = max_retries
        self.throttle_seconds = throttle_seconds

        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,"
                    "application/xml;q=0.9,*/*;q=0.8"
                ),
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.nseindia.com/",
                "Connection": "keep-alive",
                "X-Requested-With": "XMLHttpRequest",
            }
        )

        self._warmed = False

    def _warm_session(self) -> None:
        if self._warmed:
            return

        response = self.session.get(
            "https://www.nseindia.com/",
            timeout=self.timeout,
        )

        response.raise_for_status()

        self._warmed = True

        time.sleep(self.throttle_seconds)

    def _get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        referer: str | None = None,
    ) -> requests.Response:

        self._warm_session()

        headers = {}

        if referer:
            headers["Referer"] = referer

        last_error: Exception | None = None

        for attempt in range(1, self.max_retries + 1):
            
            try:
                response = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )

                if response.status_code == 200:
                    return response

                if response.status_code in {
                    403,
                    408,
                    429,
                    500,
                    502,
                    503,
                    504,
                }:
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue

                response.raise_for_status()

            except requests.RequestException as exc:
                last_error = exc

                if attempt < self.max_retries:
                    time.sleep(min(2 ** (attempt - 1), 8))
                    continue

                raise

        if last_error:
            raise last_error

        raise RuntimeError(f"NSE request failed: {url}")

    def get_filings(self, symbol: str) -> list[dict[str, Any]]:
        symbol = symbol.strip().upper()

        response = self._get(
            API_URL,
            params={
                "index": "equities",
                "symbol": symbol,
            },
            referer=REFERER,
        )

        data = response.json()

        if not isinstance(data, list):
            raise RuntimeError(
                f"Unexpected NSE shareholding response for {symbol}: "
                f"{type(data).__name__}"
            )

        return data

    def _download_xbrl(self, url: str) -> bytes:
        response = self._get(
            url,
            referer=REFERER,
        )

        return response.content

    def get_shareholding_filings(
        self,
        symbol: str,
        *,
        latest_only: bool = False,
    ) -> list[ShareholdingFiling]:

        symbol = symbol.strip().upper()

        rows = self.get_filings(symbol)

        # ---------------------------------------------------------
        # Latest-only path:
        #
        # IMPORTANT:
        # Do NOT download historical XBRL files.
        # First identify the latest filing from metadata,
        # then download only that XBRL.
        # ---------------------------------------------------------
        if latest_only:
            candidates: list[dict[str, Any]] = []

            for row in rows:
                effective_date = _parse_date(
                    row.get("date")
                )

                if effective_date is None:
                    continue

                xbrl_url = _absolute_xbrl_url(
                    row.get("xbrl") or ""
                )

                if not xbrl_url:
                    continue

                submission_date = _parse_date(
                    row.get("submissionDate")
                )

                revision_date = _parse_date(
                    row.get("revisionDate")
                )

                candidates.append(
                    {
                        "row": row,
                        "effective_date": effective_date,
                        "xbrl_url": xbrl_url,
                        "submission_date": submission_date,
                        "revision_date": revision_date,
                    }
                )

            if not candidates:
                return []

            # Newest effective date first.
            # For the same effective date, prefer the newest
            # submission/revision.
            candidates.sort(
                key=lambda item: (
                    item["effective_date"],
                    item["submission_date"] or date.min,
                    item["revision_date"] or date.min,
                ),
                reverse=True,
            )

            latest = candidates[0]

            effective_date = latest["effective_date"]
            xbrl_url = latest["xbrl_url"]
            submission_date = latest["submission_date"]
            revision_date = latest["revision_date"]

            # Download ONLY the latest XBRL.
            xml_bytes = self._download_xbrl(xbrl_url)

            total_shares = _extract_total_shares(xml_bytes)

            if total_shares is None or total_shares <= 0:
                return []

            row = latest["row"]

            revised_value = str(
                row.get("revisedData") or ""
            ).strip().upper()

            filing = ShareholdingFiling(
                symbol=symbol,
                effective_date=effective_date,
                submission_date=submission_date,
                revision_date=revision_date,
                revised=revised_value in {
                    "Y",
                    "YES",
                    "TRUE",
                },
                xbrl_url=xbrl_url,
                total_shares=total_shares,
            )

            return [filing]

        # ---------------------------------------------------------
        # Full-history path.
        #
        # This intentionally downloads every valid XBRL because
        # historical share-capital data is required.
        # ---------------------------------------------------------
        result: list[ShareholdingFiling] = []

        for row in rows:
            effective_date = _parse_date(
                row.get("date")
            )

            if effective_date is None:
                continue

            xbrl_url = _absolute_xbrl_url(
                row.get("xbrl") or ""
            )

            if not xbrl_url:
                continue

            try:
                xml_bytes = self._download_xbrl(xbrl_url)
            except requests.HTTPError as exc:
                # Historical NSE archive entries can contain dead
                # XBRL URLs. Skip them for full-history ingestion.
                print(
                    f"{symbol}: skipping XBRL "
                    f"{xbrl_url}: {exc}"
                )
                continue

            total_shares = _extract_total_shares(xml_bytes)

            if total_shares is None or total_shares <= 0:
                continue

            submission_date = _parse_date(
                row.get("submissionDate")
            )

            revision_date = _parse_date(
                row.get("revisionDate")
            )

            revised_value = str(
                row.get("revisedData") or ""
            ).strip().upper()

            filing = ShareholdingFiling(
                symbol=symbol,
                effective_date=effective_date,
                submission_date=submission_date,
                revision_date=revision_date,
                revised=revised_value in {
                    "Y",
                    "YES",
                    "TRUE",
                },
                xbrl_url=xbrl_url,
                total_shares=total_shares,
            )

            result.append(filing)

            time.sleep(self.throttle_seconds)

        result.sort(
            key=lambda x: (
                x.effective_date,
                x.submission_date or date.min,
                x.revision_date or date.min,
            ),
            reverse=True,
        )

        # Keep only the latest filing for each effective quarter.
        deduped: dict[date, ShareholdingFiling] = {}

        for filing in result:
            existing = deduped.get(
                filing.effective_date
            )

            if existing is None:
                deduped[filing.effective_date] = filing
                continue

            existing_key = (
                existing.submission_date or date.min,
                existing.revision_date or date.min,
            )

            current_key = (
                filing.submission_date or date.min,
                filing.revision_date or date.min,
            )

            if current_key > existing_key:
                deduped[filing.effective_date] = filing

        result = sorted(
            deduped.values(),
            key=lambda x: x.effective_date,
            reverse=True,
        )

        return result


def fetch_latest_shareholding(
    symbol: str,
) -> ShareholdingFiling | None:
    client = NSEShareholdingClient()

    rows = client.get_shareholding_filings(
        symbol,
        latest_only=True,
    )

    return rows[0] if rows else None