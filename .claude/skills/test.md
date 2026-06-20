---
description: Run the МАССО test suite — backend pytest (unit + integration) and frontend tests. Use when asked to run tests, check if tests pass, or verify a change before committing.
---

Run the МАССО test suite.

## Backend (pytest)

```bash
cd backend

# Full suite
pytest -x -q

# Unit only (fast)
pytest tests/unit/ -x -q

# Integration only (requires running DBs via docker compose)
pytest tests/integration/ -x -q

# Specific module
pytest tests/unit/test_scenario_agent.py -x -v

# With coverage
pytest --cov=app --cov-report=term-missing -q
```

Integration tests require the dev stack running. If not running:
```bash
docker compose -f infra/docker/docker-compose.dev.yml up -d postgres neo4j redis chromadb
# wait for health checks, then:
pytest tests/integration/ -x -q
```

## Frontend

```bash
cd frontend
npm test          # Jest / Vitest
npm run test:e2e  # Playwright (if configured)
```

## What to report

After running, report:
- How many tests passed / failed / skipped
- If failed: the test name, the assertion error, and the file:line
- Whether the failure looks like a code bug or a broken test setup (missing env, DB not running)

Do NOT claim "tests pass" without actually running them. Do NOT skip integration tests by saying "they require infrastructure" — check if docker compose is running first.
