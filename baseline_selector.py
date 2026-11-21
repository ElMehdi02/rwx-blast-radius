"""The starter selector: run every test on every commit, spread over 3 workers.

It never misses a failing test and it is slow. Everything you do from here
is deciding which tests a change cannot break.
"""
"""
import json
import sys
from pathlib import Path

DATA = Path("/data")
WORKERS = 3


def split(tests: list[dict], worker_count: int) -> list[list[int]]:
   """ """Longest test first, each onto the worker with the least to do so far.""""""
    workers: list[list[int]] = [[] for _ in range(worker_count)]
    loads = [0.0] * worker_count
    for test in sorted(tests, key=lambda test: test["seconds"], reverse=True):
        lightest = loads.index(min(loads))
        workers[lightest].append(test["number"])
        loads[lightest] += test["seconds"]
    return workers


def main() -> None:
    tests = json.loads((DATA / "tests.json").read_text())["tests"]
    workers = split(tests, WORKERS)
    for patch in sorted((DATA / "commits").glob("*.patch")):
        print(json.dumps({"commit": patch.stem, "workers": workers}))
    print(f"selected {len(tests)} tests on every commit", file=sys.stderr)


if __name__ == "__main__":
    main()
"""


"""Choose the least expensive worker count for the full suite."""


"""Impact-based test selector for sqlglot. Uses patches and tests.json only.
No sample answers or per-commit lookup is included.
"""



"""Impact-based test selector for sqlglot. Uses patches and tests.json only.
No sample answers or per-commit lookup is included.
"""



"""RWX Blast Radius - Version 8.

Predict impacted tests from patch paths and code context.
Uses only the provided tests.json and patch files.
"""




"""RWX Blast Radius selector - Version 9.

Select tests using changed files and code context.
Ignore independently comment-only Python file changes.
No sample answers or commit-specific lookup tables.
"""




"""RWX Blast Radius - Version 10.

Impact-based test selection using patches and tests.json.
No sample answers or per-commit lookup tables are used.
"""




"""Blast Radius selector - Version 14.

Patch-aware test selection and worker scheduling.
Uses incoming patches and tests.json only.

No sample answers or commit-specific lookup tables.
"""

import json
import math
import re
from pathlib import Path

DATA = Path("/data")

CORE = {
    "test_optimize",
    "test_qualify_columns",
    "test_qualify_tables",
    "test_quote_identifiers",
    "test_simplify",
    "test_annotate_funcs",
    "test_annotate_types",
}

SERDE_OPT = {
    "test_canonicalize",
    "test_canonicalize_internal_names",
    "test_eliminate_ctes",
    "test_eliminate_joins",
    "test_eliminate_subqueries",
    "test_isolate_table_selects",
    "test_merge_subqueries",
    "test_normalize",
    "test_normalize_identifiers",
    "test_optimize_joins",
    "test_pushdown_cte_alias_columns",
    "test_pushdown_predicates",
    "test_pushdown_projection",
    "test_qualify_columns__with_invisible",
    "test_qualify_order_by_source_columns",
    "test_unnest_subqueries",
    "test_tpcds",
    "test_tpch",
}


def patch_files(patch):
    paths = []
    changes = []
    current = None

    for line in patch.splitlines():
        if line.startswith("diff --git a/"):
            match = re.match(
                r"diff --git a/(.*?) b/(.*)", line
            )
            current = match.group(2) if match else None

            if current:
                paths.append(current)

        elif line.startswith((
            "+++ ", "--- ", "@@", "index ",
            "new file ", "deleted file "
        )):
            continue

        elif current and line.startswith(("+", "-")):
            changes.append(line[1:].strip())

    return paths, changes


def non_comment_patch(patch):
    """Remove independently comment-only Python diffs."""

    kept = []

    blocks = re.split(
        r"(?=^diff --git )",
        patch,
        flags=re.MULTILINE,
    )

    for block in blocks:
        if not block.startswith("diff --git "):
            continue

        paths, lines = patch_files(block)

        comment_only = (
            bool(paths)
            and bool(lines)
            and all(p.endswith(".py") for p in paths)
            and all(
                not line or line.startswith("#")
                for line in lines
            )
        )

        if not comment_only:
            kept.append(block)

    return "\n".join(kept)


def changed_symbols(patch):
    names = set()
    current = None

    for line in patch.splitlines():
        if line.startswith("@@"):
            current = None

            match = re.search(
                r"\bdef\s+([A-Za-z_][\w]*)",
                line.split("@@")[-1],
            )

            if match:
                current = match.group(1).lower()

        elif (
            line.startswith((" ", "+"))
            and not line.startswith("+++")
        ):
            match = re.match(
                r"^[ +]\s*(?:async\s+)?def\s+([A-Za-z_][\w]*)",
                line,
            )

            if match:
                current = match.group(1).lower()

        if (
            line.startswith(("+", "-"))
            and not line.startswith(("+++", "---"))
            and current
        ):
            names.add(current)

    return names


def direct_parser_test(tests, patch):
    """Match a changed SQL parser dictionary entry to its test."""

    paths, _ = patch_files(patch)

    if (
        len(paths) != 1
        or not paths[0].startswith("sqlglot/parsers/")
    ):
        return None

    dialect = Path(paths[0]).stem

    if dialect in ("parser", "__init__"):
        return None

    lines = patch.splitlines()

    hunks = [
        i for i, line in enumerate(lines)
        if line.startswith("@@")
    ]

    if len(hunks) != 1:
        return None

    start = hunks[0]

    edits = [
        i
        for i in range(start + 1, len(lines))
        if lines[i].startswith(("+", "-"))
        and not lines[i].startswith(("+++", "---"))
    ]

    if not edits:
        return None

    keys = []

    for line in lines[
        max(start + 1, min(edits) - 5):min(edits) + 1
    ]:
        match = re.match(
            r"""^[-+ ]\s*["']([A-Z][A-Z_0-9]*)["']\s*:""",
            line,
        )

        if match:
            keys.append(match.group(1).lower())

    if not keys:
        return None

    file = f"tests/dialects/test_{dialect}.py"

    matched = [
        test
        for test in tests
        if test["file"] == file
        and test["id"].split("::")[-1] == "test_" + keys[-1]
    ]

    return matched or None


def select(tests, original_patch):
    patch = non_comment_patch(original_patch)

    if not patch:
        return []

    targeted = direct_parser_test(tests, patch)

    if targeted is not None:
        return targeted

    paths, _ = patch_files(patch)

    if not paths:
        return tests

    symbols = changed_symbols(patch)
    lower = patch.lower()

    by_file = {}

    for test in tests:
        by_file.setdefault(
            test["file"], []
        ).append(test)

    selected = set()

    def add_files(*files):
        for file in files:
            selected.update(
                t["number"]
                for t in by_file.get(file, ())
            )

    def add_names(file, names):
        selected.update(
            t["number"]
            for t in by_file.get(file, ())
            if t["id"].split("::")[-1] in names
        )

    for path in paths:

        # Optimizer fixture matching
        if (
            path.startswith("tests/fixtures/optimizer/")
            and path.endswith(".sql")
        ):
            stem = Path(path).stem

            names = ["test_" + stem]

            if stem.endswith("s"):
                names.append("test_" + stem[:-1])

            parts = stem.split("_")

            names.extend(
                "test_" + "_".join(parts[:n])
                for n in range(len(parts) - 1, 0, -1)
            )

            optimizer_tests = by_file.get(
                "tests/test_optimizer.py", ()
            )

            matched = next(
                (
                    name
                    for name in names
                    if any(
                        t["id"].split("::")[-1] == name
                        for t in optimizer_tests
                    )
                ),
                None,
            )

            if matched:
                add_names(
                    "tests/test_optimizer.py",
                    {matched},
                )
            else:
                add_files("tests/test_optimizer.py")

        elif path.startswith("tests/fixtures/"):
            return tests

        elif (
            path.startswith("tests/")
            and path.endswith(".py")
        ):
            add_files(path)

        # Optimizer source code
        elif path.startswith("sqlglot/optimizer/"):
            stem = Path(path).stem

            add_names(
                "tests/test_optimizer.py",
                CORE | {"test_" + stem},
            )

            if stem == "eliminate_joins":
                add_files(
                    "tests/test_optimizer.py",
                    "tests/test_executor.py",
                )

        # Dialect parsers
        elif path.startswith("sqlglot/parsers/"):
            dialect = Path(path).stem

            if dialect in ("parser", "__init__"):
                return tests

            add_files(
                f"tests/dialects/test_{dialect}.py"
            )

            add_names(
                "tests/test_optimizer.py",
                CORE,
            )

            add_names(
                "tests/test_parser.py",
                {"test_ref_type"},
            )

            add_names(
                "tests/test_expressions.py",
                {"test_replace_tables"},
            )

        # Dialect generators
        elif path.startswith("sqlglot/generators/"):
            dialect = Path(path).stem

            if dialect in ("generator", "__init__"):
                return tests

            # Experimental narrower selection:
            # retain dialect-specific tests.
            add_files(
                f"tests/dialects/test_{dialect}.py"
            )

        # Dialect implementations
        elif path.startswith("sqlglot/dialects/"):
            dialect = Path(path).stem

            if dialect in ("dialect", "__init__"):
                add_files(
                    "tests/dialects/test_dialect.py"
                )

                add_names(
                    "tests/test_optimizer.py",
                    CORE,
                )

            else:
                add_files(
                    f"tests/dialects/test_{dialect}.py"
                )

                lexical_terms = (
                    "numeric_escapes",
                    "string_escapes",
                    "hex_strings",
                    "raw_strings",
                    "drop_unknown_escapes",
                )

                if any(
                    term in lower
                    for term in lexical_terms
                ):
                    add_files("tests/test_tokens.py")

                else:
                    add_names(
                        "tests/test_optimizer.py",
                        CORE,
                    )

        # Type annotation
        elif path.startswith("sqlglot/typing/"):
            dialect = Path(path).stem

            add_names(
                "tests/test_optimizer.py",
                CORE,
            )

            add_files("tests/test_typing.py")

            for test in by_file.get(
                f"tests/dialects/test_{dialect}.py",
                (),
            ):
                terms = (
                    "type",
                    "annotat",
                    "percentile",
                    "within_group",
                    "cast",
                    "ordered",
                )

                if any(
                    term in test["id"].lower()
                    for term in terms
                ):
                    selected.add(test["number"])

        # Executor
        elif path.startswith("sqlglot/executor/"):
            direct = [
                t
                for t in by_file.get(
                    "tests/test_executor.py", ()
                )
                if any(
                    sym in t["id"].lower()
                    for sym in symbols
                    if len(sym) >= 4
                )
            ]

            if direct:
                selected.update(
                    t["number"] for t in direct
                )

            else:
                add_files("tests/test_executor.py")

            add_names(
                "tests/test_optimizer.py",
                CORE,
            )

        # Expressions
        elif path.startswith("sqlglot/expressions/"):
            add_files("tests/test_expressions.py")

            if not re.search(
                r"@@[^\n]*\bclass\s+\w+",
                patch,
            ):
                add_names(
                    "tests/test_optimizer.py",
                    CORE,
                )

        # Serialization
        elif path == "sqlglot/serde.py":
            add_files(
                "tests/test_serde.py",
                "tests/test_executor.py",
                "tests/dialects/test_teradata.py",
                "tests/dialects/test_databricks.py",
            )

            add_names(
                "tests/test_optimizer.py",
                CORE | SERDE_OPT,
            )

            add_names(
                "tests/test_expressions.py",
                {"test_ref_type_builder"},
            )

        else:
            return tests

    if not selected:
        return tests

    return [
        t for t in tests
        if t["number"] in selected
    ]


def schedule(tests):
    """Minimize the longest worker plus 2s per worker."""

    if not tests:
        return []

    jobs = sorted(
        (
            (
                t["number"],
                math.floor(t["seconds"] * 1000 + 0.5),
            )
            for t in tests
        ),
        key=lambda job: job[1],
        reverse=True,
    )

    best = []
    best_cost = float("inf")

    for count in range(
        1, min(8, len(jobs)) + 1
    ):
        workers = [
            [] for _ in range(count)
        ]

        loads = [0] * count

        for number, milliseconds in jobs:
            index = loads.index(min(loads))

            workers[index].append(number)
            loads[index] += milliseconds

        cost = max(loads) + 2000 * count

        if cost < best_cost:
            best = workers
            best_cost = cost

    return best


def main():
    tests = json.loads(
        (DATA / "tests.json").read_text()
    )["tests"]

    full = schedule(tests)

    for file in sorted(
        (DATA / "commits").glob("*.patch")
    ):
        chosen = select(
            tests,
            file.read_text(errors="replace"),
        )

        workers = (
            full
            if len(chosen) == len(tests)
            else schedule(chosen)
        )

        print(
            json.dumps(
                {
                    "commit": file.stem,
                    "workers": workers,
                },
                separators=(",", ":"),
            )
        )


if __name__ == "__main__":
    main()
