"""Identify a clean source commit; evidence prose may be written afterwards."""

import subprocess
from pathlib import Path


def verify_clean(status):
    dirty = [line for line in status.splitlines() if line[3:] != "EVIDENCE.md"]
    if dirty:
        raise RuntimeError("DIRTY_SOURCE: " + "; ".join(dirty))


def main():
    root = Path(__file__).resolve().parents[1]
    status = subprocess.check_output(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=root,
        text=True,
    )
    verify_clean(status)
    print(
        subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip()
    )


if __name__ == "__main__":
    main()
