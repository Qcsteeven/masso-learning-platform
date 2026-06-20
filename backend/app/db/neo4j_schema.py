"""Neo4j schema constraints — idempotent, safe to call on every startup.

Node labels and properties from ТП §5 Рис. 22 / architect.md lines 96-110.
"""
from app.db.neo4j import get_driver

# (label, property) pairs that must have UNIQUE constraints
_CONSTRAINTS: list[tuple[str, str]] = [
    ("Domain", "domain_id"),
    ("Skill", "skill_id"),
    ("User", "user_id"),
    ("Scenario", "scenario_id"),
    ("Session", "session_id"),
    ("VerificationResult", "result_id"),
]


async def ensure_neo4j_constraints() -> None:
    """Create uniqueness constraints for all 6 node labels (IF NOT EXISTS)."""
    driver = get_driver()
    async with driver.session() as session:
        for label, prop in _CONSTRAINTS:
            constraint_name = f"uq_{label.lower()}_{prop}"
            await session.run(
                f"CREATE CONSTRAINT {constraint_name} IF NOT EXISTS "
                f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE"
            )
