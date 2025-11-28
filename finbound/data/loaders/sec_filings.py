"""SEC EDGAR client for fetching 10-K/10-Q filings.

SEC EDGAR API docs: https://www.sec.gov/edgar/sec-api-documentation
Rate limits: 10 requests/second per user-agent
"""

from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import requests


@dataclass
class SECFiling:
    """Metadata and content for a single SEC filing."""

    cik: str
    company_name: str
    form_type: str  # 10-K, 10-Q, 8-K, etc.
    filing_date: str
    accession_number: str
    primary_document: str
    filing_url: str
    sections: Dict[str, str]  # section name -> text content


class SECFilingsClient:
    """
    SEC EDGAR client for downloading 10-K/10-Q filings.

    Supports:
    - Company lookup by ticker or CIK
    - Filing metadata retrieval
    - Full filing document download
    - Section extraction (Item 1, 7, 8, etc.)

    Usage:
        client = SECFilingsClient()
        filings = client.list_filings("AAPL", form_type="10-K", limit=5)
        filing = client.fetch_filing(filings[0]["accessionNumber"])
    """

    COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
    COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    FILING_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"

    def __init__(self, user_agent: Optional[str] = None) -> None:
        self.user_agent = user_agent or os.getenv(
            "SEC_USER_AGENT", "FinBound/0.1 (contact@example.com)"
        )
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})
        self._ticker_cache: Dict[str, str] | None = None
        self._last_request_time: float = 0
        self._min_request_interval: float = 0.1  # 10 req/sec limit

    def _rate_limit(self) -> None:
        """Enforce SEC rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()

    def _get(self, url: str, timeout: int = 30) -> requests.Response:
        """Rate-limited GET request."""
        self._rate_limit()
        response = self.session.get(url, timeout=timeout)
        response.raise_for_status()
        return response

    def ticker_to_cik(self, ticker: str) -> str:
        """Convert ticker symbol to CIK (zero-padded to 10 digits)."""
        if self._ticker_cache is None:
            response = self._get(self.COMPANY_TICKERS_URL)
            data = response.json()
            self._ticker_cache = {
                str(v["ticker"]).upper(): str(v["cik_str"]).zfill(10)
                for v in data.values()
            }
        cik = self._ticker_cache.get(ticker.upper())
        if not cik:
            raise ValueError(f"Unknown ticker: {ticker}")
        return cik

    def fetch_company_info(self, ticker_or_cik: str) -> Dict[str, Any]:
        """Fetch company metadata and recent filings."""
        cik = self._normalize_cik(ticker_or_cik)
        url = self.SUBMISSIONS_URL.format(cik=cik)
        response = self._get(url)
        return response.json()

    def fetch_company_facts(self, ticker_or_cik: str) -> Dict[str, Any]:
        """Fetch XBRL company facts (financial data)."""
        cik = self._normalize_cik(ticker_or_cik)
        url = self.COMPANY_FACTS_URL.format(cik=cik)
        response = self._get(url)
        return response.json()

    def list_filings(
        self,
        ticker_or_cik: str,
        form_type: Literal["10-K", "10-Q", "8-K"] = "10-K",
        limit: int = 10,
        year: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """List recent filings for a company."""
        info = self.fetch_company_info(ticker_or_cik)
        filings = info.get("filings", {}).get("recent", {})

        forms = filings.get("form", [])
        dates = filings.get("filingDate", [])
        accessions = filings.get("accessionNumber", [])
        documents = filings.get("primaryDocument", [])

        results: List[Dict[str, Any]] = []
        for i, form in enumerate(forms):
            if form != form_type:
                continue
            filing_date = dates[i] if i < len(dates) else ""
            if year and not filing_date.startswith(str(year)):
                continue

            results.append({
                "form": form,
                "filingDate": filing_date,
                "accessionNumber": accessions[i] if i < len(accessions) else "",
                "primaryDocument": documents[i] if i < len(documents) else "",
            })
            if len(results) >= limit:
                break

        return results

    def fetch_filing_document(
        self,
        ticker_or_cik: str,
        accession_number: str,
        document_name: str,
    ) -> str:
        """Fetch raw filing document (HTML/text)."""
        cik = self._normalize_cik(ticker_or_cik)
        cik_no_pad = cik.lstrip("0")
        accession_clean = accession_number.replace("-", "")
        url = self.FILING_URL.format(
            cik=cik_no_pad,
            accession=accession_clean,
            document=document_name,
        )
        response = self._get(url, timeout=60)
        return response.text

    def download_filing(
        self,
        ticker_or_cik: str,
        accession_number: str,
        document_name: str,
        output_dir: str | Path = "data/raw/sec",
    ) -> Path:
        """
        Download a filing and save it locally.

        Returns the path to the saved file.
        """
        html_content = self.fetch_filing_document(
            ticker_or_cik, accession_number, document_name
        )
        accession_clean = accession_number.replace("-", "")
        ticker = ticker_or_cik.upper() if not ticker_or_cik.isdigit() else f"CIK{ticker_or_cik}"

        base_dir = Path(output_dir) / ticker / accession_clean
        base_dir.mkdir(parents=True, exist_ok=True)

        file_path = base_dir / document_name
        file_path.write_text(html_content, encoding="utf-8", errors="ignore")
        return file_path

    def extract_sections(
        self,
        html_content: str,
        sections: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """
        Extract specific sections from 10-K/10-Q HTML.

        Common sections:
        - Item 1: Business
        - Item 1A: Risk Factors
        - Item 7: MD&A
        - Item 8: Financial Statements
        """
        if sections is None:
            sections = ["Item 1", "Item 1A", "Item 7", "Item 8"]

        # Simple regex-based extraction (production would use proper HTML parsing)
        extracted: Dict[str, str] = {}
        text = _strip_html_tags(html_content)

        for section in sections:
            pattern = rf"({re.escape(section)}[\.\s]+.*?)(?=Item \d|$)"
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                content = match.group(1).strip()
                # Truncate very long sections
                extracted[section] = content[:50000] if len(content) > 50000 else content

        return extracted

    def _normalize_cik(self, ticker_or_cik: str) -> str:
        """Normalize to zero-padded CIK."""
        if ticker_or_cik.isdigit():
            return ticker_or_cik.zfill(10)
        return self.ticker_to_cik(ticker_or_cik)


def _strip_html_tags(html: str) -> str:
    """Basic HTML tag stripping."""
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _match_year(date_str: Optional[str], year: int) -> bool:
    if not date_str:
        return False
    try:
        return datetime.fromisoformat(date_str).year == year
    except ValueError:
        return False
