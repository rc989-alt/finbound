from finbound.data.unified import UnifiedSample
from finbound.reasoning.prompt_builder import PromptBuilder


def test_prompt_builder_formats_tasks():
    sample = UnifiedSample(
        id="S1",
        question="What happened?",
        gold_answer="It increased.",
        source="finqa",
        text_evidence=["Evidence paragraph"],
        table_evidence=[["Metric", "Value"]],
        answer_type="span",
        scale="",
        derivation="",
        metadata={},
    )
    builder = PromptBuilder()
    context = builder.from_unified_sample(sample)
    formatted = builder.format_for_task_family(context, "F1")

    assert "Task: F1" in formatted
    assert "Evidence paragraph" in formatted
