import json

from finbound.reasoning.chain_of_evidence import ChainOfEvidence
from finbound.reasoning.citations import format_citation


def test_chain_of_evidence_serialization():
    chain = ChainOfEvidence()
    chain.add_step("Retrieved evidence", citations=["para 1"])
    chain.add_step("Computed interest expense", parent_indices=[0], tool_result={"result": 380})

    payload = chain.to_dict()
    assert len(payload["steps"]) == 2
    assert payload["steps"][1]["parents"] == [0]


def test_format_citation_handles_strings():
    assert format_citation([" a ", "", "b"]) == ["a", "b"]
