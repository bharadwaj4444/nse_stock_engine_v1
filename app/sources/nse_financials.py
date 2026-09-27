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

            # startDate/endDate/instant are children of <period>
            for element in context.iter():
                name = local_name(element.tag)

                if name == "startDate":
                    start_date = element.text

                elif name == "endDate":
                    end_date = element.text

                elif name == "instant":
                    instant = element.text

            # Detect dimensional/scenario contexts.
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
                        return None

            return None

        # ---------------------------------------------------------
        # Find contexts for the filing period
        # ---------------------------------------------------------
        period_end = filing.period_end.isoformat()

        duration_contexts: list[tuple[str, dict[str, Any]]] = []
        instant_contexts: list[tuple[str, dict[str, Any]]] = []

        for context_id, ctx in contexts.items():

            # Only primary, non-dimensional contexts.
            if ctx["has_segment"] or ctx["has_scenario"]:
                continue

            if ctx["start"] and ctx["end"] == period_end:
                duration_contexts.append((context_id, ctx))

            if ctx["instant"] == period_end:
                instant_contexts.append((context_id, ctx))

        # ---------------------------------------------------------
        # Identify quarter / annual contexts
        #
        # For a filing period, multiple duration contexts may end
        # on the same date:
        #
        #   Q4 filing -> quarterly + annual
        #   Q1/Q2/Q3 filing -> quarterly and possibly YTD
        #
        # Always choose deterministically:
        #   quarterly = shortest duration
        #   annual    = longest duration
        # ---------------------------------------------------------
        quarterly_context = None
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

        if duration_candidates:
            duration_candidates.sort(
                key=lambda item: item[0]
            )

            # Shortest duration ending on filing date.
            quarterly_context = duration_candidates[0][1]

            # Longest duration ending on filing date.
            annual_context = duration_candidates[-1][1]

            # Only expose an annual statement when the duration
            # actually represents approximately one financial year.
            annual_days = duration_candidates[-1][0]

            if not (330 <= annual_days <= 370):
                annual_context = None

        # ---------------------------------------------------------
        # Balance sheet context
        # ---------------------------------------------------------
        balance_context = None

        if instant_contexts:
            balance_context = instant_contexts[0][0]

        # ---------------------------------------------------------
        # Extract a financial statement
        # ---------------------------------------------------------
        def build_statement(
            context_id: str | None,
            period_type: str,
        ) -> dict[str, Any] | None:

            if not context_id:
                return None

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

            operating_cf = numeric_value(
                "CashFlowsFromUsedInOperatingActivities",
                context_id,
            )

            capex = numeric_value(
                "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
                context_id,
            )

            eps = numeric_value(
                "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
                context_id,
            )

            ebit = None
            ebitda = None

            if pbt is not None:
                ebit = pbt

                if finance_costs is not None:
                    ebit += finance_costs

            if ebit is not None and depreciation is not None:
                ebitda = ebit + depreciation

            free_cash_flow = None

            if operating_cf is not None and capex is not None:
                free_cash_flow = operating_cf - abs(capex)

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
                "revenue": revenue,
                "ebitda": ebitda,
                "ebit": ebit,
                "profit_before_tax": pbt,
                "net_income": net_income,
                "eps": eps,
                "operating_cash_flow": operating_cf,
                "capital_expenditure": (
                    abs(capex)
                    if capex is not None
                    else None
                ),
                "free_cash_flow": free_cash_flow,
            }

            return statement

        # ---------------------------------------------------------
        # Add balance sheet fields
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

                if current_debt is None and noncurrent_debt is None:
                    statement["total_debt"] = None
                else:
                    statement["total_debt"] = ((current_debt or 0) + (noncurrent_debt or 0))

                statement["cash_and_equivalents"] = numeric_value(
                    "CashAndCashEquivalents",
                    balance_context,
                )

            else:
                statement["total_assets"] = None
                statement["total_equity"] = None
                statement["total_debt"] = None
                statement["cash_and_equivalents"] = None

            statement["statement_scope"] = filing.statement_scope
            statement["submission_type"] = filing.submission_type
            statement["audit_status"] = filing.audit_status

            statement["reporting_standard"] = (
                "Ind AS"
                if "INDAS" in (
                    filing.xbrl_url or ""
                ).upper()
                else None
            )

            statement["source"] = "NSE"
            statement["source_reference"] = filing.source_reference
            statement["source_url"] = filing.xbrl_url

            statements.append(statement)

        return statements