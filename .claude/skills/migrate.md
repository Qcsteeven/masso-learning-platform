---
description: Manage Alembic database migrations for МАССО PostgreSQL schema. Use when asked to create, apply, or roll back migrations, or when SQLAlchemy models have changed.
---

Manage Alembic migrations for the МАССО PostgreSQL schema.

## Apply pending migrations

```bash
cd backend
alembic upgrade head
```

## Create a new migration after model changes

```bash
cd backend

# Auto-generate (inspect the result before committing!)
alembic revision --autogenerate -m "short_description_of_change"

# Then open the generated file in alembic/versions/ and verify:
# - No unintended DROP TABLE or DROP COLUMN operations
# - Foreign key constraints are correct
# - Indexes are created for columns used in WHERE / JOIN clauses
# - JSONB columns have correct nullable settings
```

## Roll back one step

```bash
cd backend
alembic downgrade -1
```

## Check current state

```bash
cd backend
alembic current       # current revision
alembic history       # full history
alembic check         # check if models are in sync with migrations
```

## Rules

- **Always inspect** the auto-generated migration script before committing. Alembic sometimes generates unexpected drops.
- **Never** run `alembic stamp head` to skip migrations in production without understanding what schema differences exist.
- Every migration must have both `upgrade()` and `downgrade()` implemented.
- If a migration adds a NOT NULL column to an existing table with data, include a default or a two-step migration (add nullable → backfill → add NOT NULL constraint).
- `audit_logs` table: never add a DROP or migration that removes records — it's append-only by design.

## After running migrations

Run `alembic check` to confirm models and DB are in sync. Report the current revision hash and confirm no pending migrations remain.
