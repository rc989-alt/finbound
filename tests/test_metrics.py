from finbound.evaluation.metrics import (
    GroundingAccuracy,
    HallucinationRate,
    TransparencyScore,
    AuditabilityMetric,
    RunIDFidelity,
)


def test_grounding_accuracy_updates_average():
    metric = GroundingAccuracy()
    metric.update(0.5)
    metric.update(1.0)
    assert metric.value == 0.75


def test_hallucination_rate_detects():
    metric = HallucinationRate()
    metric.update(["numeric hallucination"])
    metric.update([])
    assert abs(metric.value - 0.5) < 1e-6


def test_transparency_score_counts_cited_steps():
    metric = TransparencyScore()
    metric.update({"chain_of_evidence": {"steps": [{"citations": ["a"]}, {"citations": []}]}})
    assert metric.value == 0.5


def test_auditability_metric():
    metric = AuditabilityMetric()
    metric.update({"layer1_issues": []})
    metric.update({})
    assert metric.value == 0.5


def test_run_id_fidelity():
    metric = RunIDFidelity()
    metric.update({"tracking_run_id": "abc"})
    metric.update({})
    assert metric.value == 0.5
