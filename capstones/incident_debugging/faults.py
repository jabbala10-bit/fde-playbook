"""Fault injection: pick one of N seeded faults for the debugging drill.

Candidates don't see which fault is active up front — they diagnose it from
logs.py's trace output the way they would a real production incident, then
fix service.py and prove it with tests/capstones/test_incident_debugging.py.
"""

from __future__ import annotations

import random

FAULTS = [
    "pii_redaction_bypass",
    "missing_token_cap",
    "fallback_never_fires",
    "eval_sampling_blocks_path",
]


def inject(seed: int) -> str:
    """Deterministic fault selection from a seed — the same seed always
    yields the same fault, so a drill can be reproduced and graded
    consistently across attempts."""
    rng = random.Random(seed)
    return rng.choice(FAULTS)
