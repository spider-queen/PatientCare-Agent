from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock

from app.services import memory_service


def test_memory_search_falls_back_to_recent_when_vector_search_fails(monkeypatch):
    fake_events = [
        SimpleNamespace(
            id=1,
            event_time=datetime(2026, 4, 1, 10, 0, 0),
            title="Cardiology follow-up",
            summary="Stable symptoms",
        ),
        SimpleNamespace(
            id=2,
            event_time=datetime(2026, 3, 15, 9, 0, 0),
            title="Blood test review",
            summary="No major issue",
        ),
    ]

    monkeypatch.setattr(memory_service, "list_memory_events", lambda db, patient_id: fake_events)
    monkeypatch.setattr(
        memory_service.memory_vector_service,
        "search_memory_events",
        lambda patient_id, query, top_n: (_ for _ in ()).throw(RuntimeError("vector down")),
    )

    results = memory_service.search_memory_events(
        db=Mock(),
        patient_id=1,
        query="general consultation",
        top_n=2,
    )

    assert len(results) == 2
    assert all(item["retrieval_sources"] == ["recent"] for item in results)
