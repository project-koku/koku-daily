"""Keep the import hook compatible with Black's module docstring spacing."""

import ast
import sys
from pathlib import Path


def module_spacing(source):
    tree = ast.parse(source)
    if not tree.body or not isinstance(tree.body[0], ast.Expr):
        return source
    docstring = tree.body[0]
    if not isinstance(docstring.value, ast.Constant):
        return source
    if not isinstance(docstring.value.value, str):
        return source
    lines = source.splitlines(keepends=True)
    end = docstring.end_lineno
    remaining = lines[end:]
    while remaining and not remaining[0].strip():
        remaining.pop(0)
    if remaining and remaining[0].startswith(("import ", "from ")):
        return "".join(lines[:end] + ["\n"] + remaining)
    return source


def main():
    import reorder_python_imports

    paths = [Path(arg) for arg in sys.argv[1:] if Path(arg).is_file()]
    original = {path: path.read_text() for path in paths}
    status = reorder_python_imports.main(sys.argv[1:])
    if status not in (0, 1):
        raise RuntimeError(f"Import hook failed with {status}")
    for path in paths:
        normalized = module_spacing(path.read_text())
        path.write_text(normalized)
    return int(any(path.read_text() != original[path] for path in paths))


if __name__ == "__main__":
    sys.exit(main())
