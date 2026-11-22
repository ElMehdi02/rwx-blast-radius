
"""RWX Blast Radius - Version 16.

Experimental test-impact selector.

Uses the original Version 14 algorithm as its baseline.
Refines isolated optimizer and executor changes.

No sample answers, commit IDs, or precomputed failure
lookup tables are used.
"""

import json
from pathlib import Path

import baseline_selector


DATA = Path("/data")

schedule = baseline_selector.schedule


def select(tests, patch):
    """Choose tests based on the modified source files."""

    # Start with the verified baseline selection.
    original = baseline_selector.select(tests, patch)

    # Ignore comment-only changes according to baseline rules.
    cleaned = baseline_selector.non_comment_patch(patch)

    paths, _ = baseline_selector.patch_files(cleaned)

    # Multi-file and unknown changes retain baseline selection.
    if len(paths) != 1 or not original:
        return original

    path = paths[0]
    module = Path(path).stem

    # Optimization 1:
    # Isolated optimizer modules sometimes have a directly
    # corresponding regression test.
    if (
        path.startswith("sqlglot/optimizer/")
        and path.endswith(".py")
    ):

        # Keep wider coverage for shared, high-impact modules.
        high_impact = {
            "scope",
            "eliminate_joins",
            "__init__",
        }

        if (
            module not in high_impact
            and len(original) <= 30
        ):

            direct = [
                test
                for test in original
                if (
                    test["file"] == "tests/test_optimizer.py"
                    and test["id"].split("::")[-1]
                    == "test_" + module
                )
            ]

            if direct:
                return direct

    # Optimization 2:
    # Prefer executor-specific tests plus a smaller
    # set of general optimizer regression checks.
    if (
        path.startswith("sqlglot/executor/")
        and path.endswith(".py")
        and module != "__init__"
    ):

        dedicated = [
            test
            for test in original
            if test["file"] == "tests/test_executor.py"
        ]

        if dedicated:

            smoke_tests = {
                "test_optimize",
                "test_qualify_columns",
            }

            smoke = [
                test
                for test in original
                if (
                    test["file"] == "tests/test_optimizer.py"
                    and test["id"].split("::")[-1]
                    in smoke_tests
                )
            ]

            return dedicated + smoke

    # When specific evidence is unavailable,
    # preserve the baseline test selection.
    return original


def main():
    tests = json.loads(
        (DATA / "tests.json").read_text(
            encoding="utf-8"
        )
    )["tests"]

    for patch_path in sorted(
        (DATA / "commits").glob("*.patch")
    ):

        patch = patch_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        chosen = select(tests, patch)

        workers = schedule(chosen)

        # Competition requirement:
        # exactly one JSON object per commit.
        print(
            json.dumps(
                {
                    "commit": patch_path.stem,
                    "workers": workers,
                },
                separators=(",", ":"),
            )
        )


if __name__ == "__main__":
    main()
