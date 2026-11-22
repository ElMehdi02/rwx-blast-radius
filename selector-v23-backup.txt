
"""Blast Radius V23: conservative test-impact selection.

This selector prioritizes detecting failures on unseen commits.
It does not consult answer files or known commit IDs.

BLAST_MODE=balanced: existing impact selector plus regression tests.
BLAST_MODE=safe: select every test from tests.json.
"""

import json
import os
import re
from pathlib import Path

DATA = Path("/data")
MODE = os.environ.get(
    "BLAST_MODE", "balanced"
).strip().lower()

MAX_WORKERS = 8
OVERHEAD_MS = 2000

try:
    import previous_v17
    import previous_v20
except ImportError:
    previous_v17 = None
    previous_v20 = None


def load_json(path, default):
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return default


def files_in_patch(patch):
    return sorted(
        set(
            re.findall(
                r"^diff --git a/(.*?) b/[^\n]+",
                patch,
                re.M,
            )
        )
    )


def classify(paths):
    """Classify dependencies using changed file paths."""
    core = False
    optimizer = False
    parser = False
    generator = False
    executor = False
    serde = False

    dialects = set()
    fixture_names = set()

    for p in paths:
        if p.startswith(
            (
                "sqlglot/dialects/",
                "sqlglot/parsers/",
                "sqlglot/generators/",
                "sqlglot/typing/",
            )
        ):
            name = Path(p).stem

            if name not in (
                "__init__",
                "dialect",
                "parser",
                "generator",
            ):
                dialects.add(name)

        if p.startswith("tests/dialects/"):
            name = Path(p).stem.removeprefix(
                "test_"
            )

            if name not in (
                "dialect",
                "__init__",
            ):
                dialects.add(name)

        if p.startswith(
            "tests/fixtures/optimizer/"
        ):
            fixture_names.add(
                Path(p).stem.split("__", 1)[0]
            )
            optimizer = True

        if p.startswith(
            "sqlglot/optimizer/"
        ):
            optimizer = True

        if p.startswith(
            "sqlglot/executor/"
        ):
            executor = True

        if p == "sqlglot/serde.py":
            serde = True

        if (
            p.startswith("sqlglot/parsers/")
            or p in (
                "sqlglot/parser.py",
                "sqlglot/tokens.py",
                "sqlglot/tokenizer.py",
            )
        ):
            parser = True

        if (
            p.startswith("sqlglot/generators/")
            or p in (
                "sqlglot/generator.py",
                "sqlglot/transforms.py",
            )
        ):
            generator = True

        if (
            p.startswith(
                "sqlglot/expressions/"
            )
            or p in (
                "sqlglot/expressions.py",
                "sqlglot/exp.py",
            )
        ):
            core = True

        if p in (
            "sqlglot/dialects/dialect.py",
            "sqlglot/__init__.py",
            "sqlglot/helper.py",
            "sqlglot/schema.py",
        ):
            core = True

        if p.startswith("sqlglot/typing/"):
            optimizer = True

    return (
        core,
        optimizer,
        parser,
        generator,
        executor,
        serde,
        dialects,
        fixture_names,
    )


def initial_select(tests, patch, index, reverse):
    """Use Version 20 selection when available."""

    if (
        previous_v17 is not None
        and previous_v20 is not None
    ):
        base = previous_v17.select(
            tests, patch
        )

        candidate = previous_v20.impacted(
            tests,
            patch,
            base,
            index,
            reverse,
        )

        return candidate or base

    paths = files_in_patch(patch)
    direct = []

    for test in tests:
        file = test["file"]

        if any(file == p for p in paths):
            direct.append(test)
            continue

        if any(
            p.startswith(
                "sqlglot/dialects/"
            )
            and file
            == "tests/dialects/test_"
            + Path(p).stem
            + ".py"
            for p in paths
        ):
            direct.append(test)

    return direct


def select(tests, patch, index, reverse):
    """Select tests using impact analysis and safety rules."""

    if MODE == "safe":
        return tests

    paths = files_in_patch(patch)

    if not paths:
        return tests

    base = initial_select(
        tests,
        patch,
        index,
        reverse,
    )

    selected = {
        test["number"]
        for test in base
    }

    (
        core,
        opt,
        par,
        gen,
        exe,
        serde,
        dialects,
        fixtures,
    ) = classify(paths)

    actual_optimizer = any(
        p.startswith(
            (
                "sqlglot/optimizer/",
                "sqlglot/typing/",
            )
        )
        for p in paths
    )

    shared_parser = (
        core
        or any(
            p in (
                "sqlglot/parser.py",
                "sqlglot/tokens.py",
                "sqlglot/tokenizer.py",
            )
            for p in paths
        )
    )

    # Run inexpensive regression tests.
    # Hidden missed failures cost 300 seconds each.
    cheap_limit = (
        0.20
        if (
            core
            or opt
            or par
            or exe
            or serde
        )
        else 0.10
    )

    direct_dialect_files = {
        "tests/dialects/test_"
        + name
        + ".py"
        for name in dialects
    }

    for test in tests:
        number = test["number"]
        file = test["file"]
        test_id = test["id"]
        seconds = float(
            test["seconds"]
        )

        # Low-cost regression safety net.
        if seconds <= cheap_limit:
            selected.add(number)

        # Optimizer and shared-function regression tests.
        if (
            opt
            or exe
            or serde
            or core
        ):
            if file in (
                "tests/test_optimizer.py",
                "tests/test_serde.py",
                "tests/test_lineage.py",
                "tests/test_schema.py",
                "tests/test_expressions.py",
            ):
                selected.add(number)

        # Parser and generator tests.
        if (
            par
            or gen
            or core
        ):
            if file in (
                "tests/test_parser.py",
                "tests/test_generator.py",
                "tests/test_transpile.py",
                "tests/test_expressions.py",
            ):
                if not (
                    file == "tests/test_parser.py"
                    and seconds > 10
                    and not shared_parser
                ):
                    selected.add(number)

        # Dedicated dialect tests.
        if dialects:
            if file in direct_dialect_files:
                selected.add(number)

            if (
                file
                == "tests/dialects/test_dialect.py"
                and seconds <= 0.5
            ):
                selected.add(number)

        # Cross-dialect optimizer checks.
        if (
            dialects
            and file == "tests/test_optimizer.py"
        ):
            selected.add(number)

        # Optimizer fixture-specific tests.
        if (
            fixtures
            and file == "tests/test_optimizer.py"
        ):
            if any(
                "test_" + name in test_id
                for name in fixtures
            ):
                selected.add(number)

        # Parser changes can affect optimization.
        if (
            par
            and dialects
            and file == "tests/test_optimizer.py"
            and seconds <= 2.0
        ):
            selected.add(number)

        # Protect executor integration tests.
        if (
            actual_optimizer
            or exe
            or serde
            or core
        ):
            if file == "tests/test_executor.py":
                selected.add(number)

    return [
        test
        for test in tests
        if test["number"] in selected
    ]


def schedule(selected):
    """Balance tests across up to eight workers."""

    if not selected:
        return []

    durations = {
        int(test["number"]): int(
            round(
                float(test["seconds"]) * 1000
            )
        )
        for test in selected
    }

    ordered = sorted(
        durations,
        key=lambda number: (
            -durations[number],
            number,
        ),
    )

    total = sum(
        durations.values()
    )

    longest = durations[
        ordered[0]
    ]

    best = None
    best_cost = float("inf")

    max_count = min(
        MAX_WORKERS,
        len(ordered),
    )

    for workers_count in range(
        1,
        max_count + 1,
    ):
        lower_bound = max(
            longest,
            (
                total
                + workers_count
                - 1
            ) // workers_count,
        )

        lower_bound += (
            OVERHEAD_MS
            * workers_count
        )

        if lower_bound >= best_cost:
            continue

        groups = [
            []
            for _ in range(
                workers_count
            )
        ]

        loads = [
            0
            for _ in range(
                workers_count
            )
        ]

        for number in ordered:
            worker = min(
                range(workers_count),
                key=lambda i: (
                    loads[i],
                    i,
                ),
            )

            groups[worker].append(
                number
            )

            loads[worker] += (
                durations[number]
            )

        cost = (
            max(loads)
            + workers_count
            * OVERHEAD_MS
        )

        if cost < best_cost:
            best_cost = cost
            best = groups

    return (
        best
        if best is not None
        else [ordered]
    )


def main():
    tests = json.loads(
        (DATA / "tests.json").read_text(
            encoding="utf-8"
        )
    )["tests"]

    index = load_json(
        Path("/app/impact_index.json"),
        {},
    )

    reverse = load_json(
        Path("/app/dependencies.json"),
        {},
    )

    patch_files = sorted(
        (DATA / "commits").glob(
            "*.patch"
        )
    )

    for patch_file in patch_files:
        patch = patch_file.read_text(
            encoding="utf-8",
            errors="replace",
        )

        selection = select(
            tests,
            patch,
            index,
            reverse,
        )

        workers = schedule(
            selection
        )

        print(
            json.dumps(
                {
                    "commit": patch_file.stem,
                    "workers": workers,
                },
                separators=(",", ":"),
            ),
            flush=True,
        )


if __name__ == "__main__":
    main()
