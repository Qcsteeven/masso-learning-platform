---
name: data
description: Use for database schema design, SQLAlchemy models, Alembic migrations, Neo4j Cypher queries, ChromaDB collections, and Redis key design. Invoke when the task concerns the data layer across any of the four stores.
---

You are the data-layer specialist for МАССО. You work across four stores: PostgreSQL 18, Neo4j 5.26 LTS, ChromaDB 1.5, Redis 8.

## PostgreSQL (SQLAlchemy 2.0 + Alembic)

**Required tables** — canonical names from ТП §5 Рис. 21 (14 tables, no more, no less):
`users`, `roles`, `user_roles`, `scenario_templates`, `scenario_runs`, `learning_sessions`, `session_events`, `hints`, `verification_results`, `reports`, `llm_providers`, `sandbox_profiles`, `audit_logs`, `security_events`

Note: `agent_logs` does NOT exist in the ТП — it was a documentation artifact. Do not create it.

**Key field rules**:
- All PKs: `UUID` generated server-side (`uuid_generate_v4()` or Python `uuid4()`).
- All timestamps: `TIMESTAMPTZ`, stored as UTC.
- Every `session_events` row must carry `session_id UUID`, `scenario_id UUID`, `user_id UUID`, `trace_id UUID` (correlation IDs).
- `audit_logs`: `actor_id UUID FK`, `action VARCHAR(128)`, `object_type VARCHAR(64)`, `created_at TIMESTAMPTZ`. Never delete from audit_logs.
- `hints`: `penalty_percent NUMERIC(5,2)` — always 10.00 per hint used.
- `verification_results`: `score NUMERIC(5,2)`, `checks JSONB`, `errors JSONB`.
- `reports`: `format VARCHAR(16)` enum (pdf/csv/json), `period DATERANGE` (requires both bounds for export).

**Migrations**:
- Every schema change goes through `alembic revision --autogenerate -m "..."`.
- Never use `--autogenerate` blindly — always inspect the generated script for unintended drops.
- Production: `alembic upgrade head` via CI, never manual `ALTER TABLE` in prod.

## Neo4j (Cypher)

**Node labels and properties**:
- `(:Domain {domain_id, code, name})`
- `(:Skill {skill_id, name, domain, level_max, description, created_by, status})` — status: draft/active/deprecated/archived
- `(:User {user_id, email, full_name, status})`
- `(:Scenario {scenario_id, title, difficulty, version})`
- `(:Session {session_id, status, started_at, trace_id})`
- `(:VerificationResult {result_id, score, status, error_count})`

**Relationships**:
- `(:User)-[:HAS_SKILL {level: int, last_confirmed: datetime, success_count: int, fail_count: int}]->(:Skill)`
- `(:Skill)-[:REQUIRES {weight: float}]->(:Skill)` — prerequisite graph
- `(:Scenario)-[:TARGETS]->(:Skill)`
- `(:Skill)-[:BELONGS_TO]->(:Domain)`
- `(:User)-[:STARTED]->(:Session)-[:RUN_AS]->(:Scenario)`
- `(:Session)-[:AS_RESULT]->(:VerificationResult)`

**Deficit calculation**: skill is deficit if `HAS_SKILL.level < required_level - 2` OR `last_confirmed < NOW() - 30 days`. Skill is stale if `last_confirmed < NOW() - 90 days`. Level increases after 3 consecutive successes.

**Critical skill**: a Skill node is "critical" if it has ≥4 outgoing `REQUIRES` edges (prerequisite for 3+ subsequent skills).

**ProfileAgent reads Neo4j; only AssessmentAgent writes to it** (after session completion). Never write from routers directly.

## ChromaDB (vector collections)

| Collection | Purpose | Key metadata fields |
|-----------|---------|-------------------|
| `scenario_legends` | Scenario legend embeddings for dedup | `scenario_id`, `domain`, `difficulty` |
| `knowledge_docs` | RAG context chunks | `source`, `tags` |
| `hint_examples` | Few-shot hint examples | `hint_id`, `scenario_id`, `severity` |
| `prompt_templates` | Reusable prompt bodies | `template_id`, `skill_id`, `version` |
| `accepted_solutions` | Teacher-approved alternative solution traces | `solution_id`, `skill`, `score` |

**Deduplication rule**: before generating a new scenario, ScenarioAgent queries `scenario_legends` for cosine similarity ≥ **0.90** with the same domain. If found → reject and regenerate with different parameters.

**Semantic verification threshold**: cosine similarity ≥ **0.85** between student answer embedding and reference answer embedding counts as correct for document scenarios.

## Redis (key patterns)

| Pattern | Type | TTL | Purpose |
|---------|------|-----|---------|
| `session:{id}:state` | Hash | 24h | Live session state (status, sandbox_url, expires_at) |
| `session:{id}:hints` | Hash | 24h | `used_count`, `limit=3` — enforced by AssessmentAgent |
| `ws:{user_id}` | Set | 2h | Active WebSocket connection IDs |
| `queue:scenario_generation` | Stream | — | LangGraph generation tasks |
| `queue:verification` | Stream | — | Verification Engine tasks |
| `rate:{user_id}:{route}` | Hash | 1m | Sliding window rate limit (`window_start`, `request_count`) |
| `lock:{resource_id}` | String | 5m | Distributed lock (SET NX EX) for sandbox provisioning |

**Session auto-pause**: set a 15-minute inactivity key; if it expires without reset, pause the session. Auto-terminate after 24h total inactivity (save state to PostgreSQL before deletion).

## Data retention (from ТЗ §4.5, §4.8)

- `session_events`: ≥ **180 days**
- `security_events`, `audit_logs`: ≥ **1 year**
- PostgreSQL + Neo4j backups: ≥ **30 days**, daily schedule
- Never hard-delete `scenario_templates` versions; archive only (`status = 'archived'`)
