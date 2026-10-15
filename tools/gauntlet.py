"""Run each approved evidence layer; success requires the full manifest."""

import json
import os
import subprocess
import sys
from pathlib import Path

from tools.source_state import main as source_state

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = [
    "databases",
    "tests",
    "types",
    "lint",
    "coverage",
    "mutation",
    "execution",
    "memory",
    "audit",
    "secrets",
]


def validate_layers(layers):
    if layers != EXPECTED:
        raise RuntimeError("INCOMPLETE_GAUNTLET_MANIFEST")


def main():
    os.chdir(ROOT)
    source_state()
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    for path in (
        ROOT / ".coverage",
        ROOT / "coverage.xml",
        cache / "gauntlet.json",
    ):
        path.unlink(missing_ok=True)
    environment = dict(os.environ, PRE_COMMIT_HOME=str(cache / "pre-commit"))
    python = sys.executable
    completed = []

    def layer(name, commands):
        print(f"RUN {name}", flush=True)
        for command in commands:
            subprocess.run(command, cwd=ROOT, env=environment, check=True)
        completed.append(name)

    layer(
        "databases",
        [
            [
                "docker",
                "compose",
                "-f",
                "tests/postgres-compose.yaml",
                "up",
                "-d",
                "--wait",
            ]
        ],
    )
    layer(
        "tests",
        [
            [
                python,
                "-m",
                "coverage",
                "run",
                "--branch",
                "--source=kokudaily",
                "-m",
                "pytest",
                "-q",
                "-s",
                "--randomly-seed=8395",
                "--tb=short",
            ]
        ],
    )
    layer(
        "types",
        [
            [
                python,
                "-m",
                "mypy",
                "--ignore-missing-imports",
                "--check-untyped-defs",
                "--disable-error-code=import-untyped",
                "kokudaily/replica.py",
                "kokudaily/datasets.py",
                "kokudaily/config.py",
                "kokudaily/engine.py",
                "kokudaily/reports.py",
                "kokudaily/setup_runner.py",
            ]
        ],
    )
    layer("lint", [[python, "-m", "pre_commit", "run", "--all-files"]])
    layer(
        "coverage",
        [
            [python, "-m", "coverage", "xml"],
            [
                str(ROOT / ".venv/bin/diff-cover"),
                "coverage.xml",
                "--compare-branch=5b0cbda",
                "--fail-under=100",
            ],
        ],
    )
    layer(
        "mutation",
        [
            [python, "-m", "tools.negative_controls"],
            [python, "-m", "tools.mutation_check"],
        ],
    )
    layer("execution", [[python, "-m", "tools.run_local_reports"]])
    layer(
        "memory",
        [
            [python, "-m", "tools.memory_probe", "--tenants", "100"],
            [python, "-m", "tools.memory_probe", "--tenants", "500"],
        ],
    )
    layer("audit", [[python, "-m", "tools.dependency_audit"]])
    layer(
        "secrets",
        [
            [
                "gitleaks",
                "git",
                "--redact",
                "--no-banner",
                "--log-opts=5b0cbda..HEAD",
            ]
        ],
    )
    validate_layers(completed)
    source_state()
    (cache / "gauntlet.json").write_text(
        json.dumps(completed, indent=2) + "\n"
    )
    print("GAUNTLET COMPLETE: " + ", ".join(completed), flush=True)


if __name__ == "__main__":
    main()
