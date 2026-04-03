# 作者：小红书@人间清醒的李某人

from sqlalchemy import text

from app.db.base import Base
from app.db.models import (
    MedicalCase,
    ConversationMemory,
    MemoryEvent,
    MemoryPreference,
    Patient,
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
