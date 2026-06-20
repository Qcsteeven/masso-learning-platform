"""Idempotent seed script for development and CI.

Run with: python -m app.db.seed
Uses INSERT ... ON CONFLICT DO NOTHING everywhere.
"""
import asyncio

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.neo4j import close_neo4j, get_driver, init_neo4j
from app.db.postgres import AsyncSessionFactory, engine

# ── Role definitions ───────────────────────────────────────────────────────
ROLES = [
    {"code": "student",   "name": "Обучающийся",        "permissions": {"can_start_scenario": True}},
    {"code": "teacher",   "name": "Преподаватель",       "permissions": {"can_view_groups": True, "can_correct_score": True}},
    {"code": "methodist", "name": "Методист",            "permissions": {"can_edit_graph": True, "can_approve_solutions": True}},
    {"code": "admin",     "name": "Администратор",       "permissions": {"can_manage_users": True, "can_manage_llm": True}},
    {"code": "sysadmin",  "name": "Системный администратор", "permissions": {"can_view_infra": True}},
]

# ── LLM providers ──────────────────────────────────────────────────────────
LLM_PROVIDERS = [
    {"code": "template-fallback", "mode": "template", "status": "active", "rate_limit": {}},
]

# ── Sandbox profiles ───────────────────────────────────────────────────────
SANDBOX_PROFILES = [
    {"code": "devops-base",   "cpu": 1.0, "ram_mb": 512,  "storage_gb": 5,  "network_policy": "deny_all"},
    {"code": "security-base", "cpu": 1.0, "ram_mb": 512,  "storage_gb": 5,  "network_policy": "deny_all"},
    {"code": "document-base", "cpu": 0.5, "ram_mb": 256,  "storage_gb": 2,  "network_policy": "deny_all"},
]


async def seed_postgres() -> None:
    from app.models.infra import LLMProvider, SandboxProfile
    from app.models.user import Role, User

    async with AsyncSessionFactory() as session:
        # Roles
        for role_data in ROLES:
            stmt = (
                pg_insert(Role)
                .values(**role_data)
                .on_conflict_do_nothing(index_elements=["code"])
            )
            await session.execute(stmt)

        # Admin user (hashed password for "admin" — bcrypt, do not use in prod)
        admin_hash = "$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewdBPj/2GcM9iBie"
        stmt = (
            pg_insert(User)
            .values(
                full_name="System Administrator",
                email="admin@masso.local",
                hashed_password=admin_hash,
                status="active",
            )
            .on_conflict_do_nothing(index_elements=["email"])
        )
        await session.execute(stmt)

        # LLM providers
        for prov in LLM_PROVIDERS:
            stmt = (
                pg_insert(LLMProvider)
                .values(**prov)
                .on_conflict_do_nothing(index_elements=["code"])
            )
            await session.execute(stmt)

        # Sandbox profiles
        for profile in SANDBOX_PROFILES:
            stmt = (
                pg_insert(SandboxProfile)
                .values(**profile)
                .on_conflict_do_nothing(index_elements=["code"])
            )
            await session.execute(stmt)

        await session.commit()


async def seed_neo4j() -> None:
    """Create default Domain nodes (idempotent via MERGE)."""
    domains = [
        {"domain_id": "domain-devops",   "code": "devops",   "name": "DevOps / Администрирование"},
        {"domain_id": "domain-security",  "code": "security", "name": "Информационная безопасность"},
        {"domain_id": "domain-legal",     "code": "legal",    "name": "Юриспруденция"},
        {"domain_id": "domain-audit",     "code": "audit",    "name": "Экономика / Аудит"},
    ]
    driver = get_driver()
    async with driver.session() as neo_session:
        for d in domains:
            await neo_session.run(
                "MERGE (n:Domain {domain_id: $domain_id}) "
                "SET n.code = $code, n.name = $name",
                **d,
            )


async def run() -> None:
    await seed_postgres()
    await init_neo4j()
    await seed_neo4j()
    await close_neo4j()
    await engine.dispose()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(run())
