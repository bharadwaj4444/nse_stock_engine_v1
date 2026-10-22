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

    promoter_shares: int | None
    public_shares: int | None
    non_promoter_non_public_shares: int | None

    government_shares: int | None
    domestic_institutions_shares: int | None
    foreign_institutions_shares: int | None
    non_institutions_shares: int | None

    mutual_funds_shares: int | None
    venture_capital_funds_shares: int | None
    alternative_investment_funds_shares: int | None
    banks_shares: int | None
    insurance_companies_shares: int | None
    provident_pension_funds_shares: int | None
    asset_reconstruction_companies_shares: int | None
    domestic_sovereign_wealth_funds_shares: int | None
    nbfc_shares: int | None
    other_domestic_financial_institutions_shares: int | None

    fdi_shares: int | None
    foreign_vc_investors_shares: int | None
    foreign_sovereign_wealth_funds_shares: int | None
    fpi_category_i_shares: int | None
    fpi_category_ii_shares: int | None
    overseas_depositories_shares: int | None
    other_foreign_institutions_shares: int | None

    government_state_shares: int | None
    government_promoted_companies_shares: int | None
    governments_shares: int | None

    associate_companies_subsidiaries_shares: int | None
    directors_relatives_shares: int | None
    key_managerial_personnel_shares: int | None
    promoter_relatives_shares: int | None
    promoter_related_trusts_shares: int | None
    iepf_shares: int | None

    resident_individuals_upto_2l_shares: int | None
    resident_individuals_above_2l_shares: int | None
    nris_shares: int | None
    foreign_nationals_shares: int | None
    foreign_companies_shares: int | None
    bodies_corporate_shares: int | None
    other_non_institutions_shares: int | None

    shareholding_pattern_shares: int | None

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

        if value < 0:
            continue

        facts.append((context_ref, int(value)))

    return facts

def _extract_shareholding_snapshot(
    xml_bytes: bytes,
) -> dict[str, int | None]:
    """
    Extract top-level shareholding aggregates from SHP XBRL.

    Only facts associated with the CategoryOfShareholdersAxis are
    treated as top-level shareholder-category aggregates.

    Typed/detail dimensions are intentionally ignored because those
    represent underlying entities/details and must not be summed into
    the reported aggregates.
    """

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return {
            "total_shares": _extract_total_shares_regex(xml_bytes),
            "promoter_shares": None,
            "public_shares": None,
            "government_shares": None,
            "domestic_institutions_shares": None,
            "foreign_institutions_shares": None,
            "non_institutions_shares": None,
        }

    contexts = _context_members(root)
    facts = _number_of_shares_facts(root)

    category_axis_names = {
        "in-bse-shp:CategoryOfShareholdersAxis",
        "CategoryOfShareholdersAxis",
    }

    # Member name -> normalized field.
    category_members = {
        "ShareholdingOfPromoterAndPromoterGroupMember":
            "promoter_shares",

        "SharesHeldByNonPromoterNonPublicShareholdersMember":
            "non_promoter_non_public_shares",

        "MutualFundsOrUTIMember":
            "mutual_funds_shares",

        "VentureCapitalFundsMember":
            "venture_capital_funds_shares",

        "AlternativeInvestmentFundsMember":
            "alternative_investment_funds_shares",

        "BanksMember":
            "banks_shares",

        "InsuranceCompaniesMember":
            "insurance_companies_shares",

        "ProvidentFundsOrPensionFundsMember":
            "provident_pension_funds_shares",

        "AssetReconstructionCompaniesMember":
            "asset_reconstruction_companies_shares",

        "SovereignWealthFundsDomesticMember":
            "domestic_sovereign_wealth_funds_shares",

        "NBFCsRegisteredWithRBIMember":
            "nbfc_shares",

        "OtherFinancialInstitutionsMember":
            "other_domestic_financial_institutions_shares",

        "InstitutionsDomesticMember":
            "domestic_institutions_shares",

        "ForeignDirectInvestmentMember":
            "fdi_shares",

        "ForeignVentureCapitalInvestorsMember":
            "foreign_vc_investors_shares",

        "SovereignWealthFundsForeignMember":
            "foreign_sovereign_wealth_funds_shares",

        "InstitutionsForeignPortfolioInvestorCategoryOneMember":
            "fpi_category_i_shares",

        "InstitutionsForeignPortfolioInvestorCategoryTwoMember":
            "fpi_category_ii_shares",

        "OverseasDepositoriesMember":
            "overseas_depositories_shares",

        "OtherInstitutionsForeignMember":
            "other_foreign_institutions_shares",

        "InstitutionsForeignMember":
            "foreign_institutions_shares",

        "CentralGovernmentOrPresidentOfIndiaMember":
            "government_shares",

        "StateGovernmentsOrGovernorsMember":
            "government_state_shares",

        "ShareholdingByCompaniesOrBodiesCorporateWhereCentralOrStateGovernmentIsPromoterMember":
            "government_promoted_companies_shares",

        "GovernmentsMember":
            "governments_shares",

        "AssociateCompaniesOrSubsidiariesMember":
            "associate_companies_subsidiaries_shares",

        "DirectorsAndDirectorsRelativesMember":
            "directors_relatives_shares",

        "KeyManagerialPersonnelMember":
            "key_managerial_personnel_shares",

        "RelativesOfPromotersOtherThanPromoterGroupMember":
            "promoter_relatives_shares",

        "TrustsWhereAnyPersonBelongingToPromoterAndPromoterGroupIsTrusteeOrBeneficiaryOrAuthorOfTrustMember":
            "promoter_related_trusts_shares",

        "InvestorEducationAndProtectionFundMember":
            "iepf_shares",

        "ResidentIndividualShareholdersHoldingNominalShareCapitalUpToRsTwoLakhMember":
            "resident_individuals_upto_2l_shares",

        "ResidentIndividualShareholdersHoldingNominalShareCapitalInExcessOfRsTwoLakhMember":
            "resident_individuals_above_2l_shares",

        "NonResidentIndiansMember":
            "nris_shares",

        "ForeignNationalsMember":
            "foreign_nationals_shares",

        "ForeignCompaniesMember":
            "foreign_companies_shares",

        "BodiesCorporateMember":
            "bodies_corporate_shares",

        "OtherNonInstitutionsMember":
            "other_non_institutions_shares",

        "NonInstitutionsMember":
            "non_institutions_shares",

        "PublicShareholdingMember":
            "public_shares",

        "ShareholdingPatternMember":
            "shareholding_pattern_shares",
    }

    snapshot: dict[str, int | None] = {
        "total_shares": None,
        "promoter_shares": None,
        "public_shares": None,
        "government_shares": None,
        "domestic_institutions_shares": None,
        "foreign_institutions_shares": None,
        "non_institutions_shares": None,
    }

    # Add all detailed normalized fields as nullable.
    for field_name in category_members.values():
        snapshot.setdefault(field_name, None)

    for context_ref, value in facts:
        members = contexts.get(context_ref, set())

        # We only want contexts belonging to the explicit
        # CategoryOfShareholdersAxis.
        if not any(
            member in category_axis_names
            for member in members
        ):
            continue

        for member, field_name in category_members.items():
            if (
                member in members
                or f"in-bse-shp:{member}" in members
            ):
                snapshot[field_name] = value

    # Total shares:
    #
    # ShareholdingPatternMember is the preferred reported total
    # when available.
    if snapshot.get("shareholding_pattern_shares"):
        snapshot["total_shares"] = (
            snapshot["shareholding_pattern_shares"]
        )

    # Existing explicit context remains a fallback.
    if snapshot["total_shares"] is None:
        for context_ref, value in facts:
            if context_ref == "ShareholdingPattern_ContextI":
                snapshot["total_shares"] = value
                break

    # Government aggregate in NSE XBRL is represented by
    # GovernmentsMember. Keep the more explicit components too.
    if snapshot.get("governments_shares") is not None:
        snapshot["government_shares"] = (
            snapshot["governments_shares"]
        )

    return snapshot

def _extract_total_shares(xml_bytes: bytes) -> int | None:
    """
    Extract total shares from the SHP XBRL.

    Priority:
    1. Sum mutually exclusive top-level shareholder aggregates when
       at least two are explicitly reported.
    2. Explicit NumberOfShares in ShareholdingPattern context.
    3. NumberOfShares associated with ShareholdingPatternMember.
    4. Undimensioned NumberOfShares.
    5. Promoter + Public shareholding fallback.
    """

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return _extract_total_shares_regex(xml_bytes)

    contexts = _context_members(root)
    facts = _number_of_shares_facts(root)

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

    non_promoter_non_public_members = {
        "in-bse-shp:SharesHeldByNonPromoterNonPublicShareholdersMember",
        "SharesHeldByNonPromoterNonPublicShareholdersMember",
        "in-bse-shp:NonPromoterNonPublicShareholdersMember",
        "NonPromoterNonPublicShareholdersMember",
    }

    promoter_values: list[int] = []
    public_values: list[int] = []
    non_promoter_non_public_values: list[int] = []

    for context_ref, value in facts:
        members = contexts.get(context_ref, set())

        if any(member in members for member in promoter_members):
            promoter_values.append(value)

        if any(member in members for member in public_members):
            public_values.append(value)

        if any(
            member in members
            for member in non_promoter_non_public_members
        ):
            non_promoter_non_public_values.append(value)

    # 1. Prefer the mutually exclusive top-level shareholder
    # aggregates when at least two categories are explicitly reported.
    #
    # This handles older BSE XBRL where ShareholdingPatternMember
    # represents a percentage-related value rather than total shares.
    top_level_values = [
        max(values)
        for values in (
            promoter_values,
            public_values,
            non_promoter_non_public_values,
        )
        if values
    ]

    if len(top_level_values) >= 2:
        total = sum(top_level_values)
        if total > 0:
            return total

    # 2. Standard ShareholdingPattern context.
    for context_ref, value in facts:
        if context_ref == "ShareholdingPattern_ContextI":
            return value

    # 3. ShareholdingPatternMember fallback.
    shareholding_pattern_members = {
        "in-bse-shp:ShareholdingPatternMember",
        "ShareholdingPatternMember",
    }

    for context_ref, value in facts:
        members = contexts.get(context_ref, set())

        if any(member in shareholding_pattern_members for member in members):
            return value

    # 4. Undimensioned NumberOfShares.
    candidates: list[int] = []

    for context_ref, value in facts:
        members = contexts.get(context_ref, set())

        if not members:
            candidates.append(value)

    if candidates:
        return max(candidates)

    # 5. Final fallback: promoter + public shareholding.
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

def _snapshot_kwargs(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "promoter_shares": snapshot["promoter_shares"],
        "public_shares": snapshot["public_shares"],
        "non_promoter_non_public_shares": snapshot[
            "non_promoter_non_public_shares"
        ],
        "government_shares": snapshot["government_shares"],
        "domestic_institutions_shares": snapshot[
            "domestic_institutions_shares"
        ],
        "foreign_institutions_shares": snapshot[
            "foreign_institutions_shares"
        ],
        "non_institutions_shares": snapshot[
            "non_institutions_shares"
        ],
        "mutual_funds_shares": snapshot["mutual_funds_shares"],
        "venture_capital_funds_shares": snapshot[
            "venture_capital_funds_shares"
        ],
        "alternative_investment_funds_shares": snapshot[
            "alternative_investment_funds_shares"
        ],
        "banks_shares": snapshot["banks_shares"],
        "insurance_companies_shares": snapshot[
            "insurance_companies_shares"
        ],
        "provident_pension_funds_shares": snapshot[
            "provident_pension_funds_shares"
        ],
        "asset_reconstruction_companies_shares": snapshot[
            "asset_reconstruction_companies_shares"
        ],
        "domestic_sovereign_wealth_funds_shares": snapshot[
            "domestic_sovereign_wealth_funds_shares"
        ],
        "nbfc_shares": snapshot["nbfc_shares"],
        "other_domestic_financial_institutions_shares": snapshot[
            "other_domestic_financial_institutions_shares"
        ],
        "fdi_shares": snapshot["fdi_shares"],
        "foreign_vc_investors_shares": snapshot[
            "foreign_vc_investors_shares"
        ],
        "foreign_sovereign_wealth_funds_shares": snapshot[
            "foreign_sovereign_wealth_funds_shares"
        ],
        "fpi_category_i_shares": snapshot["fpi_category_i_shares"],
        "fpi_category_ii_shares": snapshot[
            "fpi_category_ii_shares"
        ],
        "overseas_depositories_shares": snapshot[
            "overseas_depositories_shares"
        ],
        "other_foreign_institutions_shares": snapshot[
            "other_foreign_institutions_shares"
        ],
        "government_state_shares": snapshot[
            "government_state_shares"
        ],
        "government_promoted_companies_shares": snapshot[
            "government_promoted_companies_shares"
        ],
        "governments_shares": snapshot["governments_shares"],
        "associate_companies_subsidiaries_shares": snapshot[
            "associate_companies_subsidiaries_shares"
        ],
        "directors_relatives_shares": snapshot[
            "directors_relatives_shares"
        ],
        "key_managerial_personnel_shares": snapshot[
            "key_managerial_personnel_shares"
        ],
        "promoter_relatives_shares": snapshot[
            "promoter_relatives_shares"
        ],
        "promoter_related_trusts_shares": snapshot[
            "promoter_related_trusts_shares"
        ],
        "iepf_shares": snapshot["iepf_shares"],
        "resident_individuals_upto_2l_shares": snapshot[
            "resident_individuals_upto_2l_shares"
        ],
        "resident_individuals_above_2l_shares": snapshot[
            "resident_individuals_above_2l_shares"
        ],
        "nris_shares": snapshot["nris_shares"],
        "foreign_nationals_shares": snapshot[
            "foreign_nationals_shares"
        ],
        "foreign_companies_shares": snapshot[
            "foreign_companies_shares"
        ],
        "bodies_corporate_shares": snapshot[
            "bodies_corporate_shares"
        ],
        "other_non_institutions_shares": snapshot[
            "other_non_institutions_shares"
        ],
        "shareholding_pattern_shares": snapshot[
            "shareholding_pattern_shares"
        ],
    }

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

            snapshot = _extract_shareholding_snapshot(xml_bytes)

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
                **_snapshot_kwargs(snapshot),
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

            snapshot = _extract_shareholding_snapshot(xml_bytes)

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
                **_snapshot_kwargs(snapshot),
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