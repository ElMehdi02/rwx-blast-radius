# Blast Radius — Intelligent Test Selection

### RWX Builders Buildathon 2026 | Data Science & Software Engineering

## 1. Project Overview

Blast Radius is a test-selection project developed for the **RWX Builders Buildathon 2026**.

The goal is to make software testing faster by identifying which tests are most likely to be affected by changes in the source code.

Instead of running every test after each code change, our algorithm analyzes the changes, identifies related functions and dependencies, selects relevant tests, and distributes them across workers.

The challenge uses **SQLGlot**, an open-source Python library for parsing and working with SQL.

Our goal is to reduce testing time while avoiding missed failures.

## 2. The Problem

Large software projects contain many automated tests. Running all these tests after every small change can take a lot of time and computing resources.

However, selecting too few tests can also be dangerous because an important failure might go undetected.

This creates two main challenges:

- **Efficiency:** Reduce the number of tests and the total testing time.
- **Accuracy:** Make sure the selected tests can detect failures caused by code changes.

In this competition, missing a failing test can add a 300-second penalty to the score.

We needed to design an algorithm that balances speed and reliability.

## 3. Our Solution

We developed a Python-based test-selection algorithm that combines several techniques:

**1. Code change analysis**

The algorithm reads Git patch files to identify which source files and functions were modified.

**2. Function-level code coverage**

We use pytest and coverage information to identify which tests execute different parts of the SQLGlot codebase.

**3. Dependency analysis**

We analyze function calls and relationships between functions to identify how a change could affect other parts of the project.

**4. Test selection**

The algorithm combines information about code changes, coverage, and dependencies to choose relevant tests. When the available information is insufficient, it uses a broader fallback selection.

**5. Parallel test scheduling**

Selected tests are organized into groups of workers, taking test durations into account to reduce the total simulated execution time.

The objective is to select enough tests to detect failures without wasting time running unrelated tests.

## 4. How the Algorithm Works

The process follows these steps:

1. Read the list of available tests and their recorded execution times from `tests.json`.
2. Read the Git patches representing changes to SQLGlot.
3. Identify modified source files and affected functions.
4. Look up the recorded test coverage for those functions.
5. Analyze known function-call dependencies.
6. Select relevant tests using the dependency information and fallback rules.
7. Schedule the selected tests across available workers.
8. Generate JSON output containing the selected test numbers for each commit.

The program follows the output format required by the competition.

Example output:

```json
{
  "commit": "example_commit",
  "workers": [
    [12, 845, 901],
    [3, 77]
  ]
}
```

Each inner list represents the tests assigned to one worker.

## 5. Technologies Used

| Technology | Purpose |
|---|---|
| Python | Main programming language |
| Docker | Reproducible execution environment |
| Git and GitHub | Version control and source code management |
| pytest | Running and analyzing tests |
| pytest-cov / coverage.py | Collecting test coverage |
| Python AST | Analyzing source functions and calls |
| JSON | Reading test information and generating output |
| SQLGlot | Open-source project used in the competition |

## 6. Project Structure

```text
rwx-blast-radius/
│
├── Dockerfile
├── selector.py
├── previous_v17.py
├── previous_selector.py
├── baseline_selector.py
├── build_index.py
├── build_dependencies.py
├── requirements.lock
└── README.md
```

**Main files**

- `selector.py` — Main test-selection algorithm.
- `build_index.py` — Creates function-level coverage information.
- `build_dependencies.py` — Builds a static function dependency map.
- `previous_v17.py` — Earlier selection logic used by the current algorithm.
- `previous_selector.py` — Supporting selection and scheduling logic.
- `baseline_selector.py` — Original fallback selection logic.
- `Dockerfile` — Builds the execution environment and prepares the required analysis data.
- `requirements.lock` — Python dependencies.

## 7. Results and Improvements

During development, we created and tested several versions of our algorithm.

We focused on improving the selection process while keeping the number of missed failing commits at zero on the provided sample.

### Local Sample Results

| Version | Simulated Time | Missed Commits |
|---|---:|---:|
| Version 14 | 150.386 s | 0 |
| Version 16 | 143.533 s | 0 |
| Version 17 | 137.268 s | 0 |
| Version 20 | **129.996 s** | **0** |
| Version 21 | 129.996 s | 0 |

Version 20 achieved our best verified local sample result.

Compared with Version 14, the simulated selection time decreased by approximately **13.6%**.

These results were calculated using the competition's provided sample data and scoring script.

**Important:** The local scoring script does not measure the program's CPU overhead. Official leaderboard results may also differ because the final evaluation uses unseen commits. Our local results therefore do not represent an official leaderboard score.

## 8. How to Run the Project

### Requirements

- Docker
- Git
- Python 3.9 or newer for running the local scoring script
- The official Blast Radius sample files for local evaluation

### Build the Docker image

From the project directory:

```bash
docker build -t blast-radius .
```

During the build, Docker installs the dependencies, checks out the required SQLGlot revision, and generates the coverage and dependency indexes.

### Run the algorithm

Mount the official sample directory as `/data`:

```bash
docker run --rm \
  --network none \
  --read-only \
  --memory 4g \
  --cpus 2 \
  --tmpfs /tmp:rw,size=64m \
  -v "/path/to/sample:/data:ro" \
  blast-radius > output.jsonl
```

Replace `/path/to/sample` with the actual location of the sample directory.

### Evaluate the output

From the official starter project's directory:

```bash
python score.py sample sample/answers.json output.jsonl
```

The scoring script reports the simulated time and the number of missed commits.

The sample answer file is used only for local evaluation. It is not used by the submitted test-selection algorithm.

## 9. Challenges and Lessons Learned

One of the biggest challenges was determining which tests were truly necessary.

Some source changes affect functions indirectly, making it difficult to identify all relevant tests using only file names or code coverage.

We also discovered that removing too many tests could improve execution time but introduce missed failures and large penalties.

To address these issues, we improved the algorithm by combining function-level coverage with static dependency analysis and fallback rules.

Another challenge was parallel scheduling. We experimented with different worker arrangements, but the biggest improvements came from selecting better tests rather than changing how they were distributed.

This project helped us develop practical experience with code analysis, automated testing, algorithm optimization, Docker, and performance evaluation.

## 10. Limitations and Future Improvements

Our current solution has several limitations.

Static dependency analysis cannot identify every possible dynamic Python function call. Coverage information may also miss behavior that appears only after a code modification.

Future improvements could include:

- More complete function and class dependency analysis.
- Better support for inheritance, dynamic calls, and pytest fixtures.
- More accurate detection of indirect effects from code changes.
- Additional validation using independently generated code mutations.
- More efficient selection of expensive integration tests.

These improvements could further reduce testing time while maintaining reliable failure detection.

## 11. Conclusion

This project demonstrates how code analysis and dependency information can help reduce the cost of automated software testing.

By combining Git patch analysis, function-level coverage, dependency tracking, and parallel scheduling, we developed an algorithm that achieved **129.996 seconds with zero missed commits on the provided 30-commit sample**.

The project shows the importance of balancing performance and reliability when designing automated testing systems.

---

**Project:** RWX Blast Radius Buildathon 2026

**Repository:** https://github.com/ElMehdi02/rwx-blast-radius

**Technology:** Python, Docker, pytest, SQLGlot, GitHub