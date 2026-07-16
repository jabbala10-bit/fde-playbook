"""Dynamic loader for coding/*.py reference scripts.

Their filenames (`eu-ai-act.py`, `gdpr.py`) contain hyphens in one case, and
none of them sit inside a package, so they can't be imported with a normal
`import` statement. This loads them directly from disk by path instead of
duplicating their assessment logic here.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

CODING_DIR = Path(__file__).resolve().parents[2] / "coding"


def load_coding_module(filename: str) -> ModuleType:
    """e.g. load_coding_module('eu-ai-act.py') -> the loaded module object."""
    path = CODING_DIR / filename
    module_name = f"fde_coding_{path.stem.replace('-', '_')}"
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
