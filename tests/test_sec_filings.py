from pathlib import Path

from finbound.data.loaders.sec_filings import SECFilingsClient


def test_download_filing_writes_file(tmp_path, monkeypatch):
    client = SECFilingsClient(user_agent="FinBoundTest/0.1 (example@example.com)")

    monkeypatch.setattr(client, "_normalize_cik", lambda ticker: "0000123456")
    monkeypatch.setattr(
        client,
        "fetch_filing_document",
        lambda ticker, accession, document: "<html>mock filing</html>",
    )

    output = client.download_filing(
        "TEST", "0000123456-23-000010", "test.htm", output_dir=tmp_path
    )

    assert output.exists()
    assert output.read_text() == "<html>mock filing</html>"
