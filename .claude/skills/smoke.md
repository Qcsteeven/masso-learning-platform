---
description: Run an end-to-end smoke test of the МАССО core learning cycle: login → scenario generation → session start → hint → submission → verification → report. Use when asked to verify the system works end-to-end or before a demo.
---

Run the МАССО end-to-end smoke test covering the critical learning lifecycle.

## Prerequisites

All services must be running:
```bash
docker compose -f infra/docker/docker-compose.dev.yml up -d
# Wait until all health checks are green:
docker compose -f infra/docker/docker-compose.dev.yml ps
```

## Run smoke tests

```bash
cd backend
pytest tests/smoke/ -x -v --tb=short
```

If `tests/smoke/` doesn't exist yet, perform the following checks manually via the API:

### 1. Auth
```bash
curl -s -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"student@test.local","password":"test"}' | jq .
# Expect: status=success, access_token present
```

### 2. Profile load
```bash
curl -s http://localhost:8000/skills/recommendations \
  -H "Authorization: Bearer $TOKEN" | jq .
# Expect: list of skill deficits with priorities
```

### 3. Scenario generation
```bash
curl -s -X POST http://localhost:8000/scenarios/generate \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"domain":"devops","difficulty":2}' | jq .
# Expect: status=success, scenario_id, legend, checks list
# Must complete within 120 seconds
```

### 4. Session start + sandbox deploy
```bash
curl -s -X POST http://localhost:8000/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scenario_id":"<from step 3>"}' | jq .
# Expect: session_id, status=starting → ready
# Environment deploy must complete within 120 seconds
```

### 5. Session completion + verification
```bash
curl -s -X POST http://localhost:8000/sessions/$SESSION_ID/submit \
  -H "Authorization: Bearer $TOKEN" | jq .
# Expect: verification triggered, report_id returned within 30 seconds
```

### 6. Report retrieval
```bash
curl -s http://localhost:8000/reports/$REPORT_ID \
  -H "Authorization: Bearer $TOKEN" | jq .
# Expect: score, checks breakdown, hints used, recommendations
```

### 7. Sandbox cleanup
```bash
docker ps | grep "masso-session-$SESSION_ID"
# Expect: no containers found (cleanup ≤30 seconds after submit)
```

## What to report

For each step: ✓ (pass) or ✗ (fail) with the actual response and error. Flag any step that exceeds the SLA (generation >120s, deploy >120s, verification >30s, cleanup >30s).
