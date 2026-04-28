from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from app.db.session import SessionLocal
from app.services import memory_service, patient_service


logger = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class MemoryRefreshTrigger:
    patient_id: int
    recent_limit: int
    short_term_count: int
    triggered_at: str
    source: str = "agent_query"
    run_id: str | None = None

    @classmethod
    def create(
        cls,
        *,
        patient_id: int,
        recent_limit: int,
        short_term_count: int,
        run_id: str | None = None,
    ) -> "MemoryRefreshTrigger":
        return cls(
            patient_id=patient_id,
            recent_limit=recent_limit,
            short_term_count=short_term_count,
            triggered_at=datetime.now(timezone.utc).isoformat(),
            run_id=run_id,
        )


def refresh_conversation_memory_for_trigger(trigger: MemoryRefreshTrigger) -> None:
    db = SessionLocal()
    try:
        patient = patient_service.get_patient_by_id(db, trigger.patient_id)
        if patient is None:
            logger.warning(
                "memory_refresh_patient_missing %s",
                json.dumps(asdict(trigger), ensure_ascii=False),
            )
            return

        conversation_texts = memory_service.get_conversation_texts_for_extraction(
            db=db,
            patient_id=patient.id,
            limit=trigger.recent_limit,
        )
        if not conversation_texts:
            logger.info(
                "memory_refresh_skipped_empty %s",
                json.dumps(asdict(trigger), ensure_ascii=False),
            )
            return

        memory_events, user_profile = memory_service.refresh_conversation_memory(
            db=db,
            patient=patient,
            conversation_texts=conversation_texts,
        )
        logger.info(
            "memory_refresh_completed %s",
            json.dumps(
                {
                    **asdict(trigger),
                    "event_count": len(memory_events),
                    "profile_updated": user_profile is not None,
                },
                ensure_ascii=False,
            ),
        )
    except Exception:
        logger.exception(
            "memory_refresh_failed %s",
            json.dumps(asdict(trigger), ensure_ascii=False),
        )
    finally:
        db.close()
