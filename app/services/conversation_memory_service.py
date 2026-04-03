# 作者：小红书@人间清醒的李某人

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ConversationMemory
from app.schemas.memory import ConversationMemoryCreate


def create_conversation_memory(
    db: Session, payload: ConversationMemoryCreate
) -> ConversationMemory:
    memory = ConversationMemory(**payload.model_dump())
    db.add(memory)
    db.commit()
    db.refresh(memory)
    return memory


def list_conversation_memories(
    db: Session,
    patient_id: int,
    session_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[ConversationMemory]:
    stmt = (
        select(ConversationMemory)
        .where(ConversationMemory.patient_id == patient_id)
        .order_by(ConversationMemory.created_at.desc(), ConversationMemory.id.desc())
    )
    if session_id is not None:
        stmt = stmt.where(ConversationMemory.session_id == session_id)
    if limit is not None and limit > 0:
        stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


def list_recent_conversation_memories(
    db: Session,
    patient_id: int,
    limit: int = 6,
) -> list[ConversationMemory]:
    stmt = (
        select(ConversationMemory)
        .where(ConversationMemory.patient_id == patient_id)
        .order_by(ConversationMemory.created_at.desc(), ConversationMemory.id.desc())
        .limit(limit)
    )
    memories = list(db.scalars(stmt).all())
    memories.reverse()
    return memories


def count_conversation_memories(
    db: Session,
    patient_id: int,
) -> int:
    stmt = select(func.count(ConversationMemory.id)).where(
        ConversationMemory.patient_id == patient_id
    )
    return int(db.scalar(stmt) or 0)
