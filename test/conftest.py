"""Test fixtures and helpers for build_prompt verification tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Make project root importable so tests can `from build_prompt import ...`.
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

GT_DIR = Path(__file__).parent / "ground_truth"
DATA_PATH = PROJECT_ROOT / "data_filtered.jsonl"


def load_sample(namespace: str) -> dict:
    """Load a single sample from data_filtered.jsonl by namespace."""
    with open(DATA_PATH) as f:
        for line in f:
            d = json.loads(line)
            if d["namespace"] == namespace:
                return d
    raise KeyError(f"Sample not found: {namespace}")


def list_ground_truth_dirs() -> list[Path]:
    """Return ground truth sample directories, sorted by line number prefix."""
    if not GT_DIR.is_dir():
        return []
    return sorted([p for p in GT_DIR.iterdir() if p.is_dir()])


def normalize(text: str) -> str:
    """Normalize whitespace for comparison: strip outer, collapse trailing on each line."""
    lines = [line.rstrip() for line in text.splitlines()]
    # Drop fully-empty trailing lines
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)
