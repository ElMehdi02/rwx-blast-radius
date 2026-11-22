
"""RWX Blast Radius - Version 20.

Experimental dependency-aware test selector.

Combines:
- Version 17 fallback
- Function-level test coverage
- Static reverse-call dependencies
- Cost-aware worker scheduling

No sample answers or commit-specific failure tables.
"""

import json
import re
from collections import deque
from pathlib import Path

import previous_v17


DATA = Path("/data")
INDEX = Path("/app/impact_index.json")
EDGES = Path("/app/dependencies.json")


def read_json(path):
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return {}


def changed_old_lines(patch):
    changed = {}
    old_name = None
    old_line = None

    for row in patch.splitlines():

        if row.startswith("diff --git "):
            match = re.match(
                r"^diff --git a/(.*?) b/(.*)$",
                row,
            )

            old_name = (
                match.group(1) if match else None
            )
            old_line = None

        elif row.startswith("@@ "):
            match = re.match(
                r"^@@ -(\d+)(?:,\d+)? \+\d+(?:,\d+)? @@",
                row,
            )

            old_line = (
                int(match.group(1))
                if match else None
            )

        elif old_name and old_line is not None:

            if row.startswith(" "):
                old_line += 1

            elif (
                row.startswith("-")
                and not row.startswith("---")
            ):
                changed.setdefault(
                    old_name, set()
                ).add(old_line)

                old_line += 1

            elif (
                row.startswith("+")
                and not row.startswith("+++")
            ):
                changed.setdefault(
                    old_name, set()
                ).add(max(1, old_line - 1))

    return changed


def module_for(path):
    return ".".join(
        Path(path).with_suffix("").parts
    ).removesuffix(".__init__")


def impacted(tests, patch, baseline, index, reverse):
    changes = changed_old_lines(patch)

    if (
        len(changes) != 1
        or not index
        or not reverse
        or not baseline
    ):
        return baseline

    path, lines = next(iter(changes.items()))

    if not (
        path.startswith("sqlglot/")
        and path.endswith(".py")
        and lines
    ):
        return baseline

    # Keep broad test selection for shared modules.
    if (
        path.startswith("sqlglot/optimizer/")
        or path.startswith("sqlglot/expressions/")
        or path in {
            "sqlglot/serde.py",
            "sqlglot/parser.py",
            "sqlglot/generator.py",
            "sqlglot/dialects/dialect.py",
        }
    ):
        return baseline

    entries = index.get(path)

    if not entries:
        return baseline

    affected = [
        entry
        for entry in entries
        if any(
            entry[1] <= line <= entry[2]
            for line in lines
        )
    ]

    if not affected:
        return baseline

    # If some edits are outside mapped functions,
    # the full impact is uncertain.
    for line in lines:
        if not any(
            entry[1] <= line <= entry[2]
            for entry in affected
        ):
            return baseline

    module = module_for(path)

    frontier = deque(
        module + ":" + entry[0]
        for entry in affected
    )

    visited = set()

    # Follow reverse dependencies.
    while frontier:
        key = frontier.popleft()

        if key in visited:
            continue

        visited.add(key)

        # Large dependency networks are uncertain.
        if len(visited) > 100:
            return baseline

        for caller in reverse.get(key, ()):
            if caller not in visited:
                frontier.append(caller)

    # Index all functions and their covered tests.
    all_functions = {}

    for source_path, functions in index.items():
        source_module = module_for(source_path)

        for entry in functions:
            all_functions[
                source_module + ":" + entry[0]
            ] = entry[3]

    covered_ids = set()

    for key in visited:
        contexts = all_functions.get(key)

        if not contexts:
            # Missing information: keep the baseline.
            return baseline

        covered_ids.update(contexts)

    # Preserve dedicated dialect regression tests.
    dialect_test_file = (
        "tests/dialects/test_"
        + Path(path).stem
        + ".py"
    )

    keep = {
        test["number"]
        for test in baseline
        if (
            test["id"] in covered_ids
            or test["file"] == dialect_test_file
        )
    }

    narrowed = [
        test
        for test in baseline
        if test["number"] in keep
    ]

    # Avoid poorly supported or negligible reductions.
    if (
        len(narrowed) < 3
        or len(narrowed) >= len(baseline)
    ):
        return baseline

    time_saved = (
        sum(t["seconds"] for t in baseline)
        - sum(t["seconds"] for t in narrowed)
    )

    if time_saved < 1.0:
        return baseline

    return narrowed


def main():
    tests = json.loads(
        (DATA / "tests.json").read_text(
            encoding="utf-8"
        )
    )["tests"]

    index = read_json(INDEX)
    reverse = read_json(EDGES)

    for filename in sorted(
        (DATA / "commits").glob("*.patch")
    ):
        patch = filename.read_text(
            encoding="utf-8",
            errors="replace",
        )

        baseline = previous_v17.select(
            tests, patch
        )

        chosen = impacted(
            tests,
            patch,
            baseline,
            index,
            reverse,
        )

        workers = (
            previous_v17.previous_selector.schedule(
                chosen
            )
        )

        print(
            json.dumps(
                {
                    "commit": filename.stem,
                    "workers": workers,
                },
                separators=(",", ":"),
            )
        )


if __name__ == "__main__":
    main()
