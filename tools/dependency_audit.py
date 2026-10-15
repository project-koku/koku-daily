"""Check installed versions against PyPI's advisory data."""

import importlib.metadata
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def package_result(distribution):
    name = distribution.metadata["Name"]
    version = distribution.version
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    with urllib.request.urlopen(url, timeout=30) as response:
        data = json.load(response)
    if "vulnerabilities" not in data:
        raise RuntimeError("Advisory response missing vulnerabilities field")
    metadata = distribution.metadata
    license_info = metadata.get("License-Expression") or metadata.get(
        "License"
    )
    if not license_info:
        license_info = "; ".join(metadata.get_all("Classifier", []))
    return {
        "name": name,
        "version": version,
        "advisories": data["vulnerabilities"],
        "license_metadata": (license_info or "not declared")[:1500],
    }


def main():
    root = Path(__file__).resolve().parents[1]
    baseline = json.loads((root / "Pipfile.lock").read_text())["default"]

    def canonical(name):
        return name.lower().replace("_", "-")

    baseline_versions = {
        canonical(name): entry["version"].lstrip("=")
        for name, entry in baseline.items()
    }
    distributions = list(importlib.metadata.distributions())
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(package_result, distributions))
    new_findings = []
    for result in results:
        result["unchanged_runtime_lock"] = (
            baseline_versions.get(canonical(result["name"]))
            == result["version"]
        )
        if result["advisories"] and not result["unchanged_runtime_lock"]:
            new_findings.append(result["name"])
    directory = root / ".cache"
    directory.mkdir(exist_ok=True)
    (directory / "dependency-audit.json").write_text(
        json.dumps(results, indent=2)
    )
    print(
        f"Audited {len(results)} installed distributions; "
        f"new vulnerable versions: {new_findings}"
    )
    if new_findings:
        raise RuntimeError("NEW_DEPENDENCY_ADVISORIES")


if __name__ == "__main__":
    main()
