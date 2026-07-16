"""Regression tests for the 3 bugs found in the initial repo audit and
fixed in Phase C, plus the eu-ai-act.py confidence/rationale swap found
while building Capstone 2. Each test fails against the pre-fix code."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

CODING_DIR = Path(__file__).resolve().parents[1] / "coding"


def load_coding_module(filename: str) -> ModuleType:
    path = CODING_DIR / filename
    module_name = f"fde_coding_bugtest_{path.stem.replace('-', '_')}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_ai_engineer_calculate_without_calculator_tool_does_not_crash():
    """Previously: matching the arithmetic regex without a registered
    'calculator' tool raised KeyError instead of escalating safely."""
    module = load_coding_module("ai_engineer.py")
    agent = module.SimpleToolAgent(tools=[])
    result = agent.run("what is 2 + 2")
    assert result["answer"]  # did not raise


def test_langchain_evaluation_uses_expected():
    """Previously: `expected` was computed but never used in the score."""
    module = load_coding_module("langchain.py")
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        module.evaluation_example()
    assert "matched:" in buf.getvalue()


def test_rag_chunk_text_rejects_overlap_ge_chunk_size():
    """Previously: overlap >= chunk_size silently infinite-looped."""
    module = load_coding_module("rag.py")
    try:
        module.chunk_text("a b c d e f", chunk_size=3, overlap=3)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")


def test_eu_ai_act_explicit_flags_do_not_crash_on_confidence_sort():
    """Previously: DetectionHit's confidence/rationale positional args were
    swapped for the four explicit-flag hits (G0/T0/H0/H10), so any profile
    with is_generative_ai/is_biometric_system/etc. set raised
    `TypeError: '<' not supported between instances of 'str' and 'float'`
    when sorting hits by confidence."""
    module = load_coding_module("eu-ai-act.py")
    profile = module.AISystemProfile(
        name="test",
        description="test system",
        intended_purpose="test",
        is_generative_ai=True,
        is_biometric_system=True,
        is_safety_component=True,
        is_gpai_model_provider=True,
    )
    report = module.EUAIActAssessor().assess(profile)
    assert all(isinstance(hit.confidence, float) for hit in report.detections)
