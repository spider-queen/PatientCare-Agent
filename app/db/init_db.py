
from sqlalchemy import text

from app.db.base import Base
from app.db.models import (
    AgentRunMetric,
    FollowUpPlan,
    MedicalCase,
    MedicationReminder,
    ConversationMemory,
    MemoryEvent,
    MemoryPreference,
    Patient,
    RiskEvent,
    SemanticEvidenceCache,
    UserProfile,
    VisitRecord,
)
from app.db.session import engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_sqlite_columns()


def _ensure_sqlite_columns() -> None:
    with engine.begin() as connection:
        columns = connection.execute(
            text("PRAGMA table_info(conversation_memories)")
        ).fetchall()
        column_names = {column[1] for column in columns}
        if "multimodal_payload" not in column_names:
            connection.execute(
                text(
                    "ALTER TABLE conversation_memories "
                    "ADD COLUMN multimodal_payload TEXT"
                )
            )
        metric_columns = connection.execute(
            text("PRAGMA table_info(agent_run_metrics)")
        ).fetchall()
        metric_column_names = {column[1] for column in metric_columns}
        if "risk_level" not in metric_column_names:
            connection.execute(
                text("ALTER TABLE agent_run_metrics ADD COLUMN risk_level VARCHAR(32)")
            )
        if "recommended_action" not in metric_column_names:
            connection.execute(
                text("ALTER TABLE agent_run_metrics ADD COLUMN recommended_action TEXT")
            )
        metric_column_specs = {
            "route_type": "VARCHAR(32)",
            "route_reason": "TEXT",
            "actor_role": "VARCHAR(32)",
            "access_purpose": "VARCHAR(64)",
            "operator_id": "VARCHAR(128)",
            "tenant_id": "VARCHAR(128)",
            "is_demo_context": "BOOLEAN DEFAULT 0 NOT NULL",
            "cache_match_strategy": "VARCHAR(32)",
            "cache_similarity_score": "INTEGER",
            "intent_confidence": "INTEGER DEFAULT 0 NOT NULL",
            "cache_hit": "BOOLEAN DEFAULT 0 NOT NULL",
            "latency_saved_ms": "INTEGER DEFAULT 0 NOT NULL",
            "fallback_reason": "TEXT",
        }
        for column_name, column_spec in metric_column_specs.items():
            if column_name not in metric_column_names:
                connection.execute(
                    text(
                        f"ALTER TABLE agent_run_metrics "
                        f"ADD COLUMN {column_name} {column_spec}"
                    )
                )
        cache_columns = connection.execute(
            text("PRAGMA table_info(semantic_evidence_caches)")
        ).fetchall()
        cache_column_names = {column[1] for column in cache_columns}
        if "query_embedding" not in cache_column_names:
            connection.execute(
                text("ALTER TABLE semantic_evidence_caches ADD COLUMN query_embedding TEXT")
            )
