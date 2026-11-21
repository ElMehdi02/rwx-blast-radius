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

import math
import json
import sys
from pathlib import Path

DATA = Path("/data")
MAX_WORKERS = 8


def choose_workers(tests: list[dict]) -> list[list[int]]:
    # Match the scorer's rounding before adding times together.
    jobs = sorted(
        ((test["number"], math.floor(test["seconds"] * 1000 + 0.5)) for test in tests),
        key=lambda job: job[1],
        reverse=True,
    )

    best_cost = math.inf
    best_workers = []

    for count in range(1, min(MAX_WORKERS, len(jobs)) + 1):
        workers = [[] for _ in range(count)]
        loads = [0] * count

        for number, milliseconds in jobs:
            lightest = loads.index(min(loads))
            workers[lightest].append(number)
            loads[lightest] += milliseconds

        occupied = [worker for worker in workers if worker]
        cost = max(loads) + 2000 * len(occupied)

        if cost < best_cost:
            best_cost = cost
            best_workers = occupied

    return best_workers


def main() -> None:
    tests = json.loads((DATA / "tests.json").read_text())["tests"]
    workers = choose_workers(tests)

    for patch in sorted((DATA / "commits").glob("*.patch")):
        print(json.dumps({"commit": patch.stem, "workers": workers}))

    print(f"selected {len(tests)} tests on every commit", file=sys.stderr)


if __name__ == "__main__":
    main()