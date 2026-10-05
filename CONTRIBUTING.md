# Contributing to tasky

Thanks for your interest in improving **tasky**! This guide explains how to set
up the project, make a change, and submit it.

## Prerequisites

- Python **3.9 or newer** (no third-party dependencies are required — tasky
  uses the standard library only).
- `git`.

## Set up a local copy

```bash
git clone https://github.com/auramaxin/tasky.git
cd tasky
python -m tasky --help        # run straight from source
```

## Run the tests

The full suite uses the standard-library `unittest` runner:

```bash
python -m unittest discover -s tests -v
```

All tests must pass before a change can be merged. Please add tests for any new
behaviour.

## Making a change

1. **Create a branch** off `main`, named `feature/<issue#>-<short-slug>` for
   features or `fix/<issue#>-<short-slug>` for bug fixes:

   ```bash
   git switch main
   git pull origin main
   git switch -c feature/42-my-change
   ```

2. **Write code and tests.** Match the existing style:
   - keep the public API small and documented with docstrings;
   - the parser/serializer in `tasky/model.py` must round-trip (parsing then
     formatting a task yields the original line);
   - no new runtime dependencies.

3. **Run the test suite** and make sure it is green.

4. **Commit** with a clear message that references the issue:

   ```bash
   git commit -m "Add X (Closes #42)"
   ```

5. **Push and open a Pull Request** into `main`. Describe what changed and why,
   and include `Closes #<issue>` so the issue and its board card close
   automatically when the PR is merged.

## Continuous integration

Every push and pull request runs the test suite automatically via GitHub
Actions (see `.github/workflows/ci.yml`). A PR should not be merged until CI is
green.

## Project layout

```
tasky/
├── tasky/        # package: model, core, storage, cli
└── tests/        # unittest suite
```

## Code of conduct

Be respectful and constructive. Assume good intent, keep discussion focused on
the work, and help reviewers by keeping pull requests small and well described.
