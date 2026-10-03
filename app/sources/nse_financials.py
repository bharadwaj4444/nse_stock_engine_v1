from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

import httpx


NSE_INTEGRATED_FINANCIALS_URL = (
    "https://www.nseindia.com/companies-listing/corporate-integrated-filing"
)


@dataclass
class FinancialFiling:
    symbol: str
    company_name: str
    period_end: date
    submission_type: str
    audit_status: str | None
    statement_scope: str
    details_url: str | None
    xbrl_url: str | None
    ixbrl_url: str | None
    broadcast_datetime: str | None
    revised_datetime: str | None
    revision_remarks: str | None
    source_reference: str | None
    raw: dict[str, Any]


class NSEFinancialClient:
    def __init__(self, timeout: float = 30.0):
        self.timeout = timeout

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/153.0 Safari/537.36"
            ),
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;"
                "q=0.9,image/avif,image/webp,*/*;q=0.8"
            ),
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
        }

    def get_filing_page(self, symbol: str) -> str:
        params = {
            "integratedType": "integratedfilingfinancials",
            "symbol": symbol.upper(),
            "tabIndex": "equity",
        }

        with httpx.Client(
            headers=self._headers(),
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            response = client.get(
                NSE_INTEGRATED_FINANCIALS_URL,
                params=params,
            )
            response.raise_for_status()
            return response.text

    def get_filings(
        self,
        symbol: str,
        from_date: str = "01-01-2026",
        to_date: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> list[FinancialFiling]:

        if to_date is None:
            to_date = datetime.now().strftime("%d-%m-%Y")

        params = {
            "index": "equities",
            "symbol": symbol.upper(),
            "from_date": from_date,
            "to_date": to_date,
            "type": "Integrated Filing- Financials",
            "page": page,
            "size": size,
        }

        headers = self._headers()
        headers["Accept"] = "application/json, text/plain, */*"

        with httpx.Client(
            headers=headers,
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            response = client.get(
                "https://www.nseindia.com/api/integrated-filing-results",
                params=params,
            )
            response.raise_for_status()
            payload = response.json()

        filings: list[FinancialFiling] = []

        for row in payload.get("data", []):
            qe_date = row.get("qe_Date")

            if not qe_date:
                continue

            period_end = datetime.strptime(
                qe_date,
                "%d-%b-%Y",
            ).date()

            filings.append(
                FinancialFiling(
                    symbol=row.get("symbol") or symbol.upper(),
                    company_name=(
                        row.get("cmName")
                        or row.get("smName")
                        or ""
                    ),
                    period_end=period_end,
                    submission_type=row.get("type_Sub") or "Unknown",
                    audit_status=row.get("audited"),
                    statement_scope=row.get("consolidated") or "Unknown",
                    details_url=row.get("pdf_attach"),
                    xbrl_url=row.get("xbrl"),
                    ixbrl_url=row.get("ixbrl"),
                    broadcast_datetime=row.get("broadcast_Date"),
                    revised_datetime=row.get("revised_Date"),
                    revision_remarks=row.get("revision_Remark"),
                    source_reference=row.get("seq_Id"),
                    raw=row,
                )
            )

        return filings

    def download_xbrl(self, url: str) -> str:
        headers = self._headers()
        headers["Accept"] = "application/xml, text/xml, */*"

        with httpx.Client(
            headers=headers,
            timeout=self.timeout,
            follow_redirects=True,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response.text

    def parse_xbrl(
        self,
        xml_text: str,
        filing: FinancialFiling,
    ) -> list[dict[str, Any]]:

        root = ET.fromstring(xml_text)

        def local_name(tag: str) -> str:
            return tag.split("}")[-1]

        # ---------------------------------------------------------
        # Build context metadata
        # ---------------------------------------------------------

        contexts: dict[str, dict[str, Any]] = {}

        for context in root:
            if local_name(context.tag) != "context":
                continue

            context_id = context.attrib.get("id")

            if not context_id:
                continue

            start_date = None
            end_date = None
            instant = None

            for element in context.iter():
                name = local_name(element.tag)

                if name == "startDate":
                    start_date = element.text

                elif name == "endDate":
                    end_date = element.text

                elif name == "instant":
                    instant = element.text

            has_segment = any(
                local_name(element.tag) == "segment"
                for element in context.iter()
            )

            has_scenario = any(
                local_name(element.tag) == "scenario"
                for element in context.iter()
            )

            contexts[context_id] = {
                "start": start_date,
                "end": end_date,
                "instant": instant,
                "has_segment": has_segment,
                "has_scenario": has_scenario,
            }

        # ---------------------------------------------------------
        # Collect facts
        # ---------------------------------------------------------

        facts: list[dict[str, Any]] = []

        for element in root.iter():
            context_ref = element.attrib.get("contextRef")

            if not context_ref:
                continue

            text = element.text

            if text is None:
                continue

            text = text.strip()

            if not text:
                continue

            facts.append(
                {
                    "concept": local_name(element.tag),
                    "context": context_ref,
                    "value": text,
                    "unit": element.attrib.get("unitRef"),
                    "decimals": element.attrib.get("decimals"),
                }
            )

        # ---------------------------------------------------------
        # Find a numeric fact for a concept/context
        # ---------------------------------------------------------

        def numeric_value(
            concept: str,
            context_id: str,
        ) -> float | None:

            for fact in facts:
                if (
                    fact["concept"] == concept
                    and fact["context"] == context_id
                ):
                    try:
                        return float(fact["value"])
                    except ValueError:
                        continue

            return None

        # ---------------------------------------------------------
        # Find contexts for the filing period
        # ---------------------------------------------------------

        period_end = filing.period_end.isoformat()

        duration_contexts: list[
            tuple[str, dict[str, Any]]
        ] = []

        instant_contexts: list[
            tuple[str, dict[str, Any]]
        ] = []

        for context_id, ctx in contexts.items():

            # Only primary, non-dimensional contexts.
            if ctx["has_segment"] or ctx["has_scenario"]:
                continue

            if ctx["start"] and ctx["end"] == period_end:
                duration_contexts.append(
                    (context_id, ctx)
                )

            if ctx["instant"] == period_end:
                instant_contexts.append(
                    (context_id, ctx)
                )

        # ---------------------------------------------------------
        # Identify quarterly, YTD and annual contexts
        # ---------------------------------------------------------
        #
        # Indian FY / NSE patterns:
        #
        #   ~90 days   = direct quarter
        #   ~180 days  = 6M YTD
        #   ~270 days  = 9M YTD
        #   ~365 days  = annual
        #
        # IMPORTANT:
        #
        # A 180/270-day context must NOT automatically become
        # a quarterly context.
        #
        # Exception:
        #
        # Some March filings provide Oct-Mar (~180 days) P&L.
        # That can be the actual Q4 P&L and is handled below.
        # ---------------------------------------------------------

        quarterly_context = None
        ytd_context = None
        annual_context = None

        duration_candidates: list[
            tuple[int, str, dict[str, Any]]
        ] = []

        for context_id, ctx in duration_contexts:

            start = datetime.strptime(
                ctx["start"],
                "%Y-%m-%d",
            ).date()

            end = datetime.strptime(
                ctx["end"],
                "%Y-%m-%d",
            ).date()

            days = (end - start).days

            duration_candidates.append(
                (days, context_id, ctx)
            )

        quarterly_candidates: list[
            tuple[int, str, dict[str, Any]]
        ] = []

        ytd_candidates: list[
            tuple[int, str, dict[str, Any]]
        ] = []

        annual_candidates: list[
            tuple[int, str, dict[str, Any]]
        ] = []

        for days, context_id, ctx in duration_candidates:

            # Normal quarterly period.
            if 75 <= days <= 105:
                quarterly_candidates.append(
                    (days, context_id, ctx)
                )

            # Six-month YTD.
            elif 160 <= days <= 200:
                ytd_candidates.append(
                    (days, context_id, ctx)
                )

            # Nine-month YTD.
            elif 250 <= days <= 300:
                ytd_candidates.append(
                    (days, context_id, ctx)
                )

            # Full financial year.
            elif 330 <= days <= 370:
                annual_candidates.append(
                    (days, context_id, ctx)
                )

        # ---------------------------------------------------------
        # Direct quarterly context
        # ---------------------------------------------------------

        if quarterly_candidates:
            quarterly_candidates.sort(
                key=lambda item: item[0]
            )

            quarterly_context = quarterly_candidates[0][1]

        # ---------------------------------------------------------
        # YTD context
        #
        # Prefer the longest cumulative context.
        #
        # September:
        #     Apr-Sep
        #
        # December:
        #     Apr-Dec
        # ---------------------------------------------------------

        if ytd_candidates:
            ytd_candidates.sort(
                key=lambda item: item[0],
                reverse=True,
            )

            ytd_context = ytd_candidates[0][1]

        # ---------------------------------------------------------
        # March Q4 special case
        #
        # Some March filings do not contain a 90-day Jan-Mar
        # context. Instead they contain Oct-Mar (~181 days)
        # containing the actual Q4 P&L.
        #
        # We promote that context to quarterly ONLY for March.
        # ---------------------------------------------------------

        if (
            quarterly_context is None
            and filing.period_end.month == 3
        ):
            march_fallbacks: list[
                tuple[int, str, dict[str, Any]]
            ] = []

            fiscal_year_start = date(
                filing.period_end.year - 1,
                4,
                1,
            )

            for days, context_id, ctx in duration_candidates:

                if not (160 <= days <= 300):
                    continue

                start_date = datetime.strptime(
                    ctx["start"],
                    "%Y-%m-%d",
                ).date()

                # Must start after the beginning of the
                # financial year. Example: Oct 1 -> Mar 31.
                if start_date > fiscal_year_start:
                    march_fallbacks.append(
                        (days, context_id, ctx)
                    )

            if march_fallbacks:
                march_fallbacks.sort(
                    key=lambda item: item[0]
                )

                quarterly_context = (
                    march_fallbacks[0][1]
                )

        # ---------------------------------------------------------
        # If there is no direct quarterly context, use the YTD
        # context as the reported quarterly record.
        #
        # This is intentional.
        #
        # The ingestion layer will later convert:
        #
        #   6M - previous 3M = Q2
        #   9M - previous 6M = Q3
        #
        # We must retain the source cumulative values here.
        # ---------------------------------------------------------

        if (
            quarterly_context is None
            and ytd_context is not None
        ):
            quarterly_context = ytd_context

        # ---------------------------------------------------------
        # Annual context
        # ---------------------------------------------------------

        if annual_candidates:
            annual_candidates.sort(
                key=lambda item: item[0]
            )

            annual_context = annual_candidates[0][1]

        # ---------------------------------------------------------
        # Balance sheet context
        #
        # Multiple non-dimensional instant contexts can exist.
        # Prefer the one containing the balance-sheet facts.
        # ---------------------------------------------------------

        balance_context = None

        if instant_contexts:

            balance_concepts = {
                "Assets",
                "Equity",
                "CashAndCashEquivalents",
                "BorrowingsCurrent",
                "BorrowingsNoncurrent",
            }

            best_score = -1

            for context_id, ctx in instant_contexts:

                score = sum(
                    1
                    for concept in balance_concepts
                    if numeric_value(
                        concept,
                        context_id,
                    ) is not None
                )

                if score > best_score:
                    best_score = score
                    balance_context = context_id

        # ---------------------------------------------------------
        # Extract a financial statement
        # ---------------------------------------------------------

        def build_statement(
            context_id: str | None,
            period_type: str,
        ) -> dict[str, Any] | None:

            if not context_id:
                return None

            # -----------------------------------------------------
            # Primary period values
            #
            # Normal companies use standard Ind AS concepts.
            # Banking filings use a different XBRL taxonomy.
            # -----------------------------------------------------

            revenue = numeric_value(
                "RevenueFromOperations",
                context_id,
            )

            pbt = numeric_value(
                "ProfitBeforeTax",
                context_id,
            )

            net_income = numeric_value(
                "ProfitLossForPeriod",
                context_id,
            )

            depreciation = numeric_value(
                "DepreciationDepletionAndAmortisationExpense",
                context_id,
            )

            finance_costs = numeric_value(
                "FinanceCosts",
                context_id,
            )

            # -----------------------------------------------------
            # Banking XBRL fallback
            #
            # HDFCBANK / ICICIBANK-style banking filings use:
            #
            #   Income
            #   ProfitLossFromOrdinaryActivitiesBeforeTax
            #   ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates
            #
            # Do not map banking EBITDA/EBIT because those concepts
            # are not economically equivalent to industrial EBITDA/EBIT.
            # -----------------------------------------------------

            if revenue is None:
                revenue = numeric_value(
                    "Income",
                    context_id,
                )

            if pbt is None:
                pbt = numeric_value(
                    "ProfitLossFromOrdinaryActivitiesBeforeTax",
                    context_id,
                )

            if net_income is None:
                net_income = numeric_value(
                    "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates",
                    context_id,
                )

            # -----------------------------------------------------
            # Primary cash flow
            #
            # Only treat the primary context as direct quarterly
            # cash flow when it is actually a ~90-day duration.
            #
            # The P&L context may legitimately be a YTD fallback,
            # but YTD cash flow must NOT be stored as quarterly.
            # -----------------------------------------------------

            operating_cf = None
            capex = None

            context_info = contexts.get(context_id)

            if context_info:
                cf_start = context_info.get("start")
                cf_end = context_info.get("end")

                if cf_start and cf_end:
                    try:
                        cf_start_date = datetime.strptime(
                            cf_start,
                            "%Y-%m-%d",
                        ).date()

                        cf_end_date = datetime.strptime(
                            cf_end,
                            "%Y-%m-%d",
                        ).date()

                        cf_days = (
                            cf_end_date - cf_start_date
                        ).days

                        if 75 <= cf_days <= 105:
                            operating_cf = numeric_value(
                                "CashFlowsFromUsedInOperatingActivities",
                                context_id,
                            )

                            capex = numeric_value(
                                "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                                context_id,
                            )

                    except ValueError:
                        pass

            eps = numeric_value(
                "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
                context_id,
            )

            # Banking taxonomy fallback.
            if eps is None:
                eps = numeric_value(
                    "BasicEarningsPerShareAfterExtraordinaryItems",
                    context_id,
                )

            if eps is None:
                eps = numeric_value(
                    "BasicEarningsPerShareBeforeExtraordinaryItems",
                    context_id,
                )

            # -----------------------------------------------------
            # Derived P&L
            # -----------------------------------------------------

            ebit = None
            ebitda = None

            # Only derive EBIT/EBITDA when the conventional
            # industrial concepts required for the calculation exist.
            #
            # Banking filings do not use EBITDA in the same economic
            # sense, so PBT must NOT be treated as EBIT.
            if (
                pbt is not None
                and finance_costs is not None
            ):
                ebit = pbt + finance_costs

                if depreciation is not None:
                    ebitda = ebit + depreciation

            # -----------------------------------------------------
            # Direct-period FCF
            # -----------------------------------------------------

            free_cash_flow = None

            if (
                operating_cf is not None
                and capex is not None
            ):
                free_cash_flow = (
                    operating_cf
                    - abs(capex)
                )

            # -----------------------------------------------------
            # YTD values
            #
            # These are retained internally for ingestion.
            # -----------------------------------------------------

            ytd_revenue = None
            ytd_pbt = None
            ytd_net_income = None
            ytd_depreciation = None
            ytd_finance_costs = None
            ytd_eps = None

            ytd_operating_cf = None
            ytd_capex = None
            ytd_fcf = None

            if ytd_context:

                ytd_revenue = numeric_value(
                    "RevenueFromOperations",
                    ytd_context,
                )

                ytd_pbt = numeric_value(
                    "ProfitBeforeTax",
                    ytd_context,
                )

                ytd_net_income = numeric_value(
                    "ProfitLossForPeriod",
                    ytd_context,
                )

                # Banking XBRL fallback.
                if ytd_revenue is None:
                    ytd_revenue = numeric_value(
                        "Income",
                        ytd_context,
                    )

                if ytd_pbt is None:
                    ytd_pbt = numeric_value(
                        "ProfitLossFromOrdinaryActivitiesBeforeTax",
                        ytd_context,
                    )

                if ytd_net_income is None:
                    ytd_net_income = numeric_value(
                        "ProfitLossAfterTaxesMinorityInterestAndShareOfProfitLossOfAssociates",
                        ytd_context,
                    )

                ytd_depreciation = numeric_value(
                    "DepreciationDepletionAndAmortisationExpense",
                    ytd_context,
                )

                ytd_finance_costs = numeric_value(
                    "FinanceCosts",
                    ytd_context,
                )

                ytd_eps = numeric_value(
                    "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
                    ytd_context,
                )

                if ytd_eps is None:
                    ytd_eps = numeric_value(
                        "BasicEarningsPerShareAfterExtraordinaryItems",
                        ytd_context,
                    )

                if ytd_eps is None:
                    ytd_eps = numeric_value(
                        "BasicEarningsPerShareBeforeExtraordinaryItems",
                        ytd_context,
                    )

                ytd_operating_cf = numeric_value(
                    "CashFlowsFromUsedInOperatingActivities",
                    ytd_context,
                )

                ytd_capex = numeric_value(
                    "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                    ytd_context,
                )

                if (
                    ytd_operating_cf is not None
                    and ytd_capex is not None
                ):
                    ytd_fcf = (
                        ytd_operating_cf
                        - abs(ytd_capex)
                    )

            # -----------------------------------------------------
            # Statement
            # -----------------------------------------------------

            statement = {
                "symbol": filing.symbol,
                "company_name": filing.company_name,

                "period_type": period_type,
                "period_end": filing.period_end,

                "filing_date": (
                    datetime.strptime(
                        filing.broadcast_datetime,
                        "%d-%b-%Y %H:%M:%S",
                    ).date()
                    if filing.broadcast_datetime
                    else None
                ),

                # Primary P&L
                "revenue": revenue,
                "ebitda": ebitda,
                "ebit": ebit,
                "profit_before_tax": pbt,
                "net_income": net_income,
                "eps": eps,

                # Primary cash flow
                "operating_cash_flow": operating_cf,

                "capital_expenditure": (
                    abs(capex)
                    if capex is not None
                    else None
                ),

                "free_cash_flow": free_cash_flow,

                # -------------------------------------------------
                # YTD P&L
                # -------------------------------------------------

                "_ytd_revenue": ytd_revenue,

                "_ytd_profit_before_tax": ytd_pbt,

                "_ytd_net_income": ytd_net_income,

                "_ytd_depreciation": ytd_depreciation,

                "_ytd_finance_costs": ytd_finance_costs,

                "_ytd_eps": ytd_eps,

                # -------------------------------------------------
                # YTD cash flow
                # -------------------------------------------------

                "_ytd_operating_cash_flow": (
                    ytd_operating_cf
                ),

                "_ytd_capital_expenditure": (
                    abs(ytd_capex)
                    if ytd_capex is not None
                    else None
                ),

                "_ytd_free_cash_flow": ytd_fcf,

                # -------------------------------------------------
                # YTD dates
                # -------------------------------------------------

                "_ytd_start": (
                    contexts[ytd_context]["start"]
                    if ytd_context
                    else None
                ),

                "_ytd_end": (
                    contexts[ytd_context]["end"]
                    if ytd_context
                    else None
                ),

                # -------------------------------------------------
                # Reported/source period dates
                # -------------------------------------------------

                "_cash_flow_start": (
                    contexts[context_id]["start"]
                ),

                "_cash_flow_end": (
                    contexts[context_id]["end"]
                ),

                "_period_start": (
                    contexts[context_id]["start"]
                ),

                "_period_end": (
                    contexts[context_id]["end"]
                ),
                "_pnl_context_type": (
                    "quarter"
                    if (
                        75 <= (
                            datetime.strptime(
                                contexts[context_id]["end"],
                                "%Y-%m-%d",
                            ).date()
                            - datetime.strptime(
                                contexts[context_id]["start"],
                                "%Y-%m-%d",
                            ).date()
                        ).days <= 105
                        or (
                            filing.period_end.month == 3
                            and 160 <= (
                                datetime.strptime(
                                    contexts[context_id]["end"],
                                    "%Y-%m-%d",
                                ).date()
                                - datetime.strptime(
                                    contexts[context_id]["start"],
                                    "%Y-%m-%d",
                                ).date()
                            ).days <= 200
                            and contexts[context_id]["start"]
                            >= f"{filing.period_end.year - 1}-10-01"
                        )
                    )
                    else "ytd"
                ),
                "_pnl_start": contexts[context_id]["start"],
            }

            return statement

        # ---------------------------------------------------------
        # Build statements
        # ---------------------------------------------------------

        statements: list[dict[str, Any]] = []

        for context_id, period_type in [
            (quarterly_context, "quarterly"),
            (annual_context, "annual"),
        ]:

            statement = build_statement(
                context_id,
                period_type,
            )

            if statement is None:
                continue

            # -----------------------------------------------------
            # Balance sheet
            # -----------------------------------------------------

            if balance_context:

                statement["total_assets"] = numeric_value(
                    "Assets",
                    balance_context,
                )

                statement["total_equity"] = numeric_value(
                    "Equity",
                    balance_context,
                )

                current_debt = numeric_value(
                    "BorrowingsCurrent",
                    balance_context,
                )

                noncurrent_debt = numeric_value(
                    "BorrowingsNoncurrent",
                    balance_context,
                )

                if (
                    current_debt is None
                    and noncurrent_debt is None
                ):
                    statement["total_debt"] = None

                else:
                    statement["total_debt"] = (
                        (current_debt or 0)
                        + (noncurrent_debt or 0)
                    )

                statement["cash_and_equivalents"] = (
                    numeric_value(
                        "CashAndCashEquivalents",
                        balance_context,
                    )
                )

            else:

                statement["total_assets"] = None
                statement["total_equity"] = None
                statement["total_debt"] = None
                statement["cash_and_equivalents"] = None

            # -----------------------------------------------------
            # Filing metadata
            # -----------------------------------------------------

            statement["statement_scope"] = (
                filing.statement_scope
            )

            statement["submission_type"] = (
                filing.submission_type
            )

            statement["audit_status"] = (
                filing.audit_status
            )

            statement["reporting_standard"] = (
                "Ind AS"
                if "INDAS" in (
                    filing.xbrl_url or ""
                ).upper()
                else None
            )

            statement["source"] = "NSE"

            statement["source_reference"] = (
                filing.source_reference
            )

            statement["source_url"] = filing.xbrl_url

            statements.append(statement)

        return statements