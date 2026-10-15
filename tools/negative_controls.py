"""Prove checker failure paths without retaining temporary mutants."""

import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check_defence(path, old, new, test):
    original = path.read_text()
    if original.count(old) != 1:
        raise RuntimeError("NEGATIVE_CONTROL_ANCHOR_NOT_UNIQUE")
    with tempfile.TemporaryDirectory(prefix="cost8395-control-") as temporary:
        try:
            path.write_text(original.replace(old, new, 1))
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-X",
                    "pycache_prefix=" + temporary,
                    "-m",
                    "pytest",
                    "-q",
                    test,
                    "--tb=short",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            )
        finally:
            path.write_text(original)
    if result.returncode != 1 or "FAILED " not in result.stdout:
        raise RuntimeError(
            "DEFENCE_REMOVAL_DID_NOT_BREAK_CONTROL: "
            f"exit={result.returncode}; {result.stdout}; {result.stderr}"
        )
    print("Defence removal detected: " + test, flush=True)


def main():
    checks = [
        (
            "tools/mutation_check.py",
            "if source.count(old) != 1:",
            "if False:",
            "tests/test_checker_contracts.py::"
            "test_mutation_anchor_guard_fails_closed",
        ),
        (
            "tools/source_state.py",
            "if dirty:",
            "if False:",
            "tests/test_checker_contracts.py::"
            "test_dirty_source_guard_fails_closed",
        ),
        (
            "tools/gauntlet.py",
            "if layers != EXPECTED:",
            "if False:",
            "tests/test_checker_contracts.py::"
            "test_incomplete_gauntlet_manifest_fails_closed",
        ),
        (
            "kokudaily/engine.py",
            '"sslmode": "verify-full"',
            '"sslmode": "require"',
            "tests/test_engine.py::test_tls_options_apply_to_both_engines",
        ),
        (
            "kokudaily/config.py",
            "APP_PORT = 8080",
            "APP_PORT = 0",
            "tests/test_config.py::"
            "test_touched_schedule_types_preserve_"
            "normalization_and_port_fallback",
        ),
    ]
    for filename, old, new, test in checks:
        check_defence(ROOT / filename, old, new, test)
    secret = "aws_access_key_id = " + "AKIA" + "QWERTYUIOPASDFGH"
    result = subprocess.run(
        ["gitleaks", "stdin", "--redact", "--no-banner"],
        input=secret,
        text=True,
        capture_output=True,
    )
    if result.returncode != 1 or "leaks found" not in result.stderr.lower():
        raise RuntimeError("SECRET_NEGATIVE_CONTROL_NOT_DETECTED")
    tree = ET.parse(ROOT / "coverage.xml")
    for line in tree.iter("line"):
        line.set("hits", "0")
    target = ROOT / ".cache/coverage-negative.xml"
    tree.write(target)
    result = subprocess.run(
        [
            str(ROOT / ".venv/bin/diff-cover"),
            str(target),
            "--compare-branch=5b0cbda",
            "--fail-under=100",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if (
        result.returncode != 1
        or "Coverage is below" not in result.stdout + result.stderr
    ):
        raise RuntimeError("COVERAGE_NEGATIVE_CONTROL_NOT_DETECTED")
    print("Known-bad secret and zero-coverage controls rejected", flush=True)


if __name__ == "__main__":
    main()
