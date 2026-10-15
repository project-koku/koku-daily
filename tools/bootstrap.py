"""Install the runtime lock and pinned test tools in the local venv."""

import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
lock = json.loads((root / "Pipfile.lock").read_text())
requirements = root / ".venv/runtime-requirements.txt"
lines = []
for name, package in lock["default"].items():
    entry = name + package["version"]
    if "markers" in package:
        entry += "; " + package["markers"]
    entry += " " + " ".join("--hash=" + h for h in package["hashes"])
    lines.append(entry)
requirements.write_text("\n".join(lines) + "\n")
subprocess.run([sys.executable, "-m", "pip", "install", "--require-hashes", "-r", str(requirements)], check=True)
subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(root / "requirements-dev.txt")], check=True)
