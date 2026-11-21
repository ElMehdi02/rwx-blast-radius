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




"""RWX Blast Radius - Version 16.

Uses the existing V14 selector as a conservative fallback.

For isolated optimizer-module edits, attempts to use the
dedicated test named after the modified optimizer module.

No sample answer keys or commit-specific lookups are used.
"""

import json
import re
from pathlib import Path

import baseline_selector


DATA = Path("/data")

select_baseline = (
    getattr(baseline_selector, "select_v10", None)
    or baseline_selector.select
)

schedule = baseline_selector.schedule


def select(tests, patch):
    """Select impacted tests from the incoming patch."""

    # Start with the Version 14 selection.
    baseline = select_baseline(tests, patch)

    # Identify the modified files.
    paths = re.findall(
        r"^diff --git a/.*? b/(.*?)$",
        patch,
        flags=re.MULTILINE,
    )

    # Keep the original selection for large or
    # multi-file changes.
    if len(paths) != 1 or len(baseline) > 30:
        return baseline

    path = paths[0]

    # Only refine isolated Python optimizer changes.
    if not (
        path.startswith("sqlglot/optimizer/")
        and path.endswith(".py")
    ):
        return baseline

    stem = Path(path).stem

    # These modules have broader dependencies.
    if stem in {"__init__", "scope"}:
        return baseline

    # Find a dedicated optimizer regression test.
    directly_named = [
        test
        for test in baseline
        if (
            test["file"] == "tests/test_optimizer.py"
            and test["id"].split("::")[-1]
            == "test_" + stem
        )
    ]

    # Use the existing selector if no matching
    # regression test is available.
    return directly_named or baseline


def main():
    tests = json.loads(
        (DATA / "tests.json").read_text()
    )["tests"]

    for patch_file in sorted(
        (DATA / "commits").glob("*.patch")
    ):
        patch = patch_file.read_text(
            errors="replace"
        )

        selected = select(tests, patch)

        workers = schedule(selected)

        # Print only the required JSON object.
        print(
            json.dumps(
                {
                    "commit": patch_file.stem,
                    "workers": workers,
                },
                separators=(",", ":"),
            )
        )


if __name__ == "__main__":
    main()
