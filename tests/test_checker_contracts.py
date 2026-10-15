"""Negative controls for the home-grown assurance checks."""

import pytest
from tools.gauntlet import validate_layers
from tools.mutation_check import apply_mutation
from tools.reorder_imports import module_spacing
from tools.source_state import verify_clean


def test_mutation_anchor_guard_fails_closed():
    with pytest.raises(RuntimeError, match="MUTATION_ANCHOR_NOT_UNIQUE"):
        apply_mutation("source", "missing", "bug")
    with pytest.raises(RuntimeError, match="MUTATION_ANCHOR_NOT_UNIQUE"):
        apply_mutation("x x", "x", "bug")


def test_dirty_source_guard_fails_closed():
    with pytest.raises(RuntimeError, match="DIRTY_SOURCE"):
        verify_clean(" M kokudaily/reports.py\n")
    with pytest.raises(RuntimeError, match="DIRTY_SOURCE"):
        verify_clean("?? forgotten.py\n")
    verify_clean(" M EVIDENCE.md\n")


def test_module_spacing_preserves_code_and_is_idempotent():
    original = '"""Module."""\nimport os\n'
    expected = '"""Module."""\n\nimport os\n'
    assert module_spacing(original) == expected
    assert module_spacing(expected) == expected
    for source in (
        "import os\n",
        "1\n",
        '"""Module."""\n\ndef f():\n    pass\n',
    ):
        assert module_spacing(source) == source


def test_incomplete_gauntlet_manifest_fails_closed():
    with pytest.raises(RuntimeError, match="INCOMPLETE_GAUNTLET_MANIFEST"):
        validate_layers(["tests", "lint"])
