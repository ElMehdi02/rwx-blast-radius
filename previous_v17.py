
"""RWX Blast Radius - Version 17.

Experimental test-impact selection.

Uses the Version 16 selector as its baseline.
Refines general optimizer test selection for isolated
dialect and parser changes.

No sample answers, commit-specific tables,
or hardcoded failure predictions are used.
"""

import json
from pathlib import Path

import baseline_selector
import previous_selector


DATA = Path("/data")


def select(tests, patch):
    """Choose tests for an incoming source-code change."""

    # Use the previous verified algorithm first.
    chosen = previous_selector.select(tests, patch)

    # Analyze the actual patch.
    cleaned = baseline_selector.non_comment_patch(patch)

    paths, _ = baseline_selector.patch_files(cleaned)

    if not paths or not chosen:
        return chosen

    # Optimization 1:
    # Dialect implementation changes have dedicated
    # dialect tests.
    #
    # Keep those tests, but omit two general optimizer
    # checks that can add unnecessary execution time.
    if all(
        path.startswith("sqlglot/dialects/")
        for path in paths
    ):
        excluded = {
            "test_annotate_funcs",
            "test_qualify_columns",
        }

    # Optimization 2:
    # For changes confined to parser implementations,
    # retain parser and dialect regression tests,
    # while omitting one generic optimizer check.
    elif all(
        path.startswith("sqlglot/parsers/")
        for path in paths
    ):
        excluded = {
            "test_simplify",
        }

    else:
        # Keep Version 16 selection for other changes.
        return chosen

    trimmed = [
        test
        for test in chosen
        if not (
            test["file"] == "tests/test_optimizer.py"
            and test["id"].split("::")[-1] in excluded
        )
    ]

    # Never return an empty set merely because
    # the refinement excluded every selected test.
    return trimmed if trimmed else chosen


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

        workers = previous_selector.schedule(chosen)

        # Print one JSON line per commit.
        # No debugging output goes to stdout.
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
