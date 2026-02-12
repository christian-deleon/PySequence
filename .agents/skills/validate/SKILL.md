---
name: validate
description: Run lint and unit tests to validate code quality
---

# Validate

Run formatting checks and unit tests to ensure code quality.

## Steps

1. **Check formatting** — Run `just lint` to verify Black formatting.
   - If it fails, run `just fmt` to auto-fix, then run `just lint` again to confirm.

2. **Run unit tests** — Run `just test-unit` to execute unit tests in Docker.

3. **Report results** — Summarize pass/fail status for both lint and tests.
