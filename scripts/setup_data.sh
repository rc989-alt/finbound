#!/usr/bin/env bash

set -euo pipefail

TICKERS=("AAPL" "MSFT" "JPM")

echo "Downloading sample SEC filings for tickers: ${TICKERS[*]}"

python3 - <<'PY'
from pathlib import Path

from finbound.data.loaders.sec_filings import SECFilingsClient
from finbound.data.processors.section_splitter import SectionSplitter

tickers = ["AAPL", "MSFT", "JPM"]
client = SECFilingsClient()
splitter = SectionSplitter()

for ticker in tickers:
    try:
        filings = client.list_filings(ticker, form_type="10-K", limit=1)
    except Exception as exc:
        print(f"[WARN] Unable to list filings for {ticker}: {exc}")
        continue

    if not filings:
        print(f"[WARN] No filings found for {ticker}")
        continue

    filing = filings[0]
    accession = filing["accessionNumber"]
    primary_doc = filing["primaryDocument"]

    try:
        path = client.download_filing(
            ticker,
            accession,
            primary_doc,
            output_dir="data/raw/sec",
        )
        text = Path(path).read_text(encoding="utf-8", errors="ignore")
        sections = splitter.split(text)
    except Exception as exc:
        print(f"[WARN] Failed to download/process filing for {ticker}: {exc}")
        continue

    corpus_dir = Path("data/corpus/sec") / ticker
    corpus_dir.mkdir(parents=True, exist_ok=True)

    for section, body in sections.items():
        safe_section = section.replace(" ", "_").replace("/", "_")
        outfile = corpus_dir / f"{accession.replace('-', '')}_{safe_section}.txt"
        outfile.write_text(body, encoding="utf-8")
        print(f"[INFO] Wrote {outfile}")
PY

echo "SEC sample data setup complete."
