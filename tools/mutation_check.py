"""Auditable manual mutants; every mutation runs in a fresh Python process."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUTANTS = [
    (
        "readonly",
        "replica",
        "SET TRANSACTION READ ONLY",
        "SET TRANSACTION READ WRITE",
    ),
    ("retry", "replica", "if not is_recovery_conflict(error):", "if True:"),
    (
        "history",
        "replica",
        'merged.update({row["date"]: row for row in current})',
        "merged.update({})",
    ),
    (
        "routing",
        "reports",
        "reader = create_engine(readonly=True)",
        "reader = DB_ENGINE",
    ),
    ("partial", "reports", "if complete:", "if True:"),
]


def apply_mutation(source, old, new):
    if source.count(old) != 1:
        raise RuntimeError("MUTATION_ANCHOR_NOT_UNIQUE")
    return source.replace(old, new, 1)


def run_mutant(name, module, old, new, properties_only=False):
    path = ROOT / "kokudaily" / (module + ".py")
    original = path.read_text()
    mutated = apply_mutation(original, old, new)
    digest = hashlib.sha256(mutated.encode()).hexdigest()
    tests = (
        ["tests/test_report_properties.py"]
        if properties_only
        else [
            "tests/test_replica.py",
            "tests/test_reports.py",
            "tests/test_postgres_reports.py::"
            "test_exhausted_schema_retries_continue_"
            "but_never_persist_partial_totals",
        ]
    )
    with tempfile.TemporaryDirectory(prefix="cost8395-mutant-") as temporary:
        cache = str(Path(temporary) / "never-created-cache")
        # No bytecode can be read: the fresh prefix does not exist and -B
        # prevents creating it. Verify the loaded source hash before pytest.
        child = (
            "import hashlib,importlib,pathlib,sys; "
            "assert not pathlib.Path(sys.pycache_prefix).exists(); "
            f"m=importlib.import_module('kokudaily.{module}'); "
            "assert not pathlib.Path(m.__cached__).exists(); "
            "assert hashlib.sha256(pathlib.Path(m.__file__).read_bytes())"
            f".hexdigest() == {digest!r}; "
            f"print('EXECUTED {name} {digest}', flush=True); "
            f"import pytest; tests={tests!r}; "
            "sys.exit(pytest.main(tests+"
            "['-q','--tb=short','--randomly-seed=8395']))"
        )
        try:
            path.write_text(mutated)
            completed = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-X",
                    "pycache_prefix=" + cache,
                    "-c",
                    child,
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                timeout=180,
            )
        finally:
            path.write_text(original)
        if path.read_text() != original:
            raise RuntimeError("MUTATION_RESTORE_FAILED")
        output = completed.stdout + completed.stderr
        directory = ROOT / ".cache/mutations"
        directory.mkdir(parents=True, exist_ok=True)
        suffix = "-properties" if properties_only else ""
        (directory / (name + suffix + ".log")).write_text(output)
        if f"EXECUTED {name} {digest}" not in output:
            raise RuntimeError("MUTATION_EXECUTION_NOT_PROVEN")
        if completed.returncode not in (0, 1):
            raise RuntimeError(
                f"Invalid test exit {completed.returncode}: {output}"
            )
        killed = completed.returncode == 1
        if killed and "FAILED tests/" not in output:
            raise RuntimeError(
                "MUTATION_FAILED_WITHOUT_BEHAVIORAL_TEST_FAILURE"
            )
        print(
            f"{name}{suffix}: {'killed' if killed else 'survived'}", flush=True
        )
        return killed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    if args.negative_control:
        apply_mutation("source", "absent anchor", "mutant")
        return
    results = []
    for mutant in MUTANTS:
        killed = run_mutant(*mutant)
        if not killed:
            raise RuntimeError("SURVIVING_MANUAL_MUTANT: " + mutant[0])
        property_kill = run_mutant(*mutant, properties_only=True)
        results.append(
            {
                "name": mutant[0],
                "suite_killed": killed,
                "properties_killed": property_kill,
            }
        )
    (ROOT / ".cache/mutations/results.json").write_text(
        json.dumps(results, indent=2) + "\n"
    )
    print(f"Manual mutation: {len(results)}/{len(MUTANTS)} killed")


if __name__ == "__main__":
    main()
