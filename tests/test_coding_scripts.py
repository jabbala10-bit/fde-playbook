"""Smoke tests for coding/*.py — the 14 reference scripts. Several have
hyphens in their filenames, so they're loaded by path via importlib rather
than imported as normal modules. Each is exercised through whichever
no-network entry point it exposes (a `guide()`/`demo_*()` function, or
`main()` with `--mode guide`, which every argparse-based script here
defaults to). This proves the scripts still run after the Phase C bug
fixes and catches any future regression that breaks a script outright.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

CODING_DIR = Path(__file__).resolve().parents[1] / "coding"


def load_coding_module(filename: str) -> ModuleType:
    path = CODING_DIR / filename
    module_name = f"fde_coding_smoketest_{path.stem.replace('-', '_')}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


# Files whose main() is argparse-based and defaults every argument, so
# `--mode guide` (or equivalent) runs with an empty argv and touches no
# network/filesystem/subprocess.
MAIN_GUIDE_FILES = [
    "a2a_coding.py",
    "crewai.py",
    "google-adk.py",
    "mcp_coding.py",
    "ocr_code.py",
    "openai_sdk.py",
    "openclaw.py",
]


@pytest.mark.parametrize("filename", MAIN_GUIDE_FILES)
def test_main_guide_mode_runs_without_error(filename, monkeypatch, capsys):
    module = load_coding_module(filename)
    monkeypatch.setattr(sys, "argv", [filename])
    module.main()
    assert capsys.readouterr().out.strip()


def test_langchain_main_runs_without_error(capsys):
    module = load_coding_module("langchain.py")
    module.main()
    assert capsys.readouterr().out.strip()


def test_eu_ai_act_guide_and_demo():
    module = load_coding_module("eu-ai-act.py")
    assert "EU AI Act" in module.guide()
    report = module.EUAIActAssessor().assess(module.demo_profile())
    assert report.primary_category is not None


def test_gdpr_guide_and_demo():
    module = load_coding_module("gdpr.py")
    assert "GDPR" in module.guide() or "gdpr" in module.guide().lower()
    report = module.GDPRAssessor().assess(module.demo_profile())
    assert report.primary_risk is not None


def test_llm_metrics_guide_and_demo():
    module = load_coding_module("llm-metrics.py")
    assert module.guide()
    assert module.demo_profile() is not None


def test_ai_engineer_lightweight_demo():
    module = load_coding_module("ai_engineer.py")
    result = module.run_lightweight_demo()
    assert result


def test_rag_demo_small(capsys):
    module = load_coding_module("rag.py")
    module.demo_small()
    assert capsys.readouterr().out.strip()


def test_langgraph_imports_without_executing_demo():
    """demo_all() requires a real api_key, so this is an import-only smoke
    test — it still catches syntax errors and broken imports."""
    module = load_coding_module("langGraph.py")
    assert hasattr(module, "demo_all")


def test_agentic_ai_engineer_was_removed():
    """coding/agentic_ai_engineer.py was an empty 0-byte placeholder; Phase A
    hygiene removed it. Guard against it silently reappearing empty."""
    assert not (CODING_DIR / "agentic_ai_engineer.py").exists()
