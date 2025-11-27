import os

os.environ.setdefault("OPENAI_API_KEY", "test-key")

from finbound import FinBound
from finbound.data.index.corpus_builder import CorpusDocument
from finbound.data.index.evidence_store import EvidenceStore
from finbound.types import EvidenceContext


def test_finbound_retrieve_evidence_from_store():
    store = EvidenceStore()
    store.add(
        CorpusDocument(
            doc_id="doc1",
            text="Interest expense increased year over year due to higher rates.",
            metadata={},
        )
    )
    fb = FinBound(evidence_store=store)

    snippets = fb._retrieve_evidence({"query_text": "interest expense"})

    assert snippets and "Interest expense" in snippets[0]


def test_prepare_evidence_context_merges_retrieval():
    fb = FinBound()
    base_context = EvidenceContext(text_blocks=["Existing evidence"], tables=[], metadata={})

    merged = fb._prepare_evidence_context(
        base_context,
        {"query_text": "interest expense"},
        ["Retrieved snippet"],
    )

    assert "Existing evidence" in merged.text_blocks
    assert "Retrieved snippet" in merged.text_blocks
    assert merged.metadata["retrieval_query"]["query_text"] == "interest expense"
