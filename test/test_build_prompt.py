"""Verify build_prompt.build_context_string against hand-curated ground truth.

For each test/ground_truth/<sample>/ directory:
  - Load meta.json to get the namespace.
  - Load sd_sd.py and full_full.py as expected context strings.
  - Call build_context_string with the corresponding modes.
  - Assert (after whitespace normalization) that output matches expected.

Run with::

    pytest test/ -v
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import GT_DIR, load_sample, list_ground_truth_dirs, normalize

from build_prompt import build_context_string


# --- Parametrize over (sample_dir, mode) pairs --------------------------------

_MODES = [
    ("sd_sd", "sig_doc", "sig_doc"),
    ("sd_init", "sig_doc", "sd_init"),
    ("full_full", "full", "full"),
]


def _all_cases():
    cases = []
    for sample_dir in list_ground_truth_dirs():
        for mode_name, _, _ in _MODES:
            cases.append((sample_dir, mode_name))
    return cases


def _case_ids():
    return [f"{sd.name}::{m}" for sd, m in _all_cases()]


@pytest.mark.parametrize("sample_dir,mode_name", _all_cases(), ids=_case_ids())
def test_context_matches_ground_truth(sample_dir: Path, mode_name: str):
    # Look up the func/class modes for this case.
    func_mode, class_mode = next(
        (fm, cm) for n, fm, cm in _MODES if n == mode_name
    )

    # Load expected context.
    expected_path = sample_dir / f"{mode_name}.py"
    assert expected_path.exists(), f"Missing ground truth file: {expected_path}"
    expected = expected_path.read_text()

    # Load sample metadata.
    meta = json.loads((sample_dir / "meta.json").read_text())
    sample = load_sample(meta["namespace"])

    # Run the extractor.
    actual = build_context_string(sample, func_mode=func_mode, class_mode=class_mode)

    # Compare normalized.
    exp_norm = normalize(expected)
    act_norm = normalize(actual)

    if exp_norm != act_norm:
        # Show a brief diff snippet for easier debugging.
        msg = (
            f"\n--- Expected ({sample_dir.name} / {mode_name}) ---\n"
            f"{exp_norm[:500]}\n"
            f"--- Actual ---\n"
            f"{act_norm[:500]}\n"
        )
        pytest.fail(msg)
