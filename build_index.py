
"""Create a function-level coverage index.

Uses the pinned sqlglot source and its test coverage.
Never reads sample answers or incoming patches.
"""

import ast
import json
from pathlib import Path

from coverage import CoverageData

SOURCE = Path("/opt/sqlglot")
DATAFILE = "/app/.coverage"
OUTPUT = Path("/app/impact_index.json")


def functions(tree):
    found = []

    def visit(body, prefix=""):
        for node in body:
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                name = prefix + node.name

                found.append(
                    (
                        name,
                        node.lineno,
                        node.end_lineno or node.lineno,
                    )
                )

                visit(node.body, name + ".")

            elif isinstance(node, ast.ClassDef):
                visit(
                    node.body,
                    prefix + node.name + ".",
                )

    visit(tree.body)
    return found


def main():
    data = CoverageData(basename=DATAFILE)
    data.read()

    measured = {
        str(Path(filename).resolve()): filename
        for filename in data.measured_files()
    }

    index = {}

    for path in sorted(
        (SOURCE / "sqlglot").rglob("*.py")
    ):
        relative = path.relative_to(
            SOURCE
        ).as_posix()

        try:
            tree = ast.parse(
                path.read_text(encoding="utf-8")
            )
        except (SyntaxError, UnicodeError, OSError):
            continue

        measured_name = measured.get(
            str(path.resolve())
        )

        contexts = (
            data.contexts_by_lineno(measured_name)
            if measured_name
            else {}
        )

        entries = []

        for name, start, end in functions(tree):
            test_ids = set()

            for line in range(start, end + 1):
                for context in contexts.get(line, []):
                    node_id = context.split("|", 1)[0]

                    if (
                        node_id.startswith("tests/")
                        and "::" in node_id
                    ):
                        test_ids.add(node_id)

            entries.append(
                [
                    name,
                    start,
                    end,
                    sorted(test_ids),
                ]
            )

        index[relative] = entries

    OUTPUT.write_text(
        json.dumps(
            index,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    OUTPUT.chmod(0o644)

    print(
        "Indexed source files:",
        len(index),
        "functions:",
        sum(len(v) for v in index.values()),
        "covered functions:",
        sum(
            bool(entry[3])
            for values in index.values()
            for entry in values
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
