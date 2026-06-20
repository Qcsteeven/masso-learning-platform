---
description: Run all linters and type-checkers for МАССО — ruff, mypy (backend) and tsc, eslint (frontend). Use when asked to lint, check types, or before committing changes.
---

Run all code-quality checks for МАССО.

## Backend

```bash
cd backend

# Linting (ruff)
ruff check .

# Auto-fix safe issues
ruff check . --fix

# Type checking (mypy)
mypy .

# Run both together (fail-fast on first error category)
ruff check . && mypy .
```

## Frontend

```bash
cd frontend

# TypeScript type check (no emit)
npx tsc --noEmit

# ESLint
npm run lint

# Run both
npx tsc --noEmit && npm run lint
```

## Interpreting results

- **ruff errors**: fix them; do not suppress with `# noqa` unless there's a genuine false positive — always add a comment explaining why.
- **mypy errors**: fix type annotations; do not use `# type: ignore` without a comment.
- **tsc errors**: fix them; do not use `@ts-ignore` or `any` without a comment.

## What to report

List each failing check with file path, line number, and the error message. If all checks pass, say so explicitly and include the command output summary.
