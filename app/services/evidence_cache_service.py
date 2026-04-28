from __future__ import annotations

import json
import math
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import SequenceMatcher
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import SemanticEvidenceCache
from app.services import memory_vector_service


DEFAULT_TTL_SECONDS = 600
SIMILARITY_THRESHOLD = 0.68
EMBEDDING_SIMILARITY_THRESHOLD = 0.78
LOCAL_EMBEDDING_HASH_DIMENSIONS = 24
LOCAL_EMBEDDING_FEATURES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("follow_up_plan", ("随访", "复查", "复诊", "计划", "安排", "下次", "下一次", "接下来", "哪天", "什么时候")),
    ("latest_visit", ("最近一次", "最新一次", "上次", "最近", "最新", "就诊记录", "复诊记录", "就诊", "记录", "摘要")),
    ("medication", ("用药", "服药", "吃药", "药品", "药物", "剂量", "频次", "提醒")),
    ("profile", ("基本信息", "患者信息", "个人信息", "资料", "概览", "姓名", "性别")),
    ("case", ("病历", "病例", "诊断", "主诉", "治疗计划", "病情")),
    ("time", ("时间", "日期", "哪天", "什么时候", "几号", "安排")),
)


@dataclass(frozen=True)
class CacheLookupResult:
    entry: SemanticEvidenceCache | None = None
    miss_reason: str | None = None
    match_strategy: str | None = None
    similarity_score: float | None = None


def normalize_query(query: str) -> str:
    normalized = re.sub(r"P\d{4,}", "", query.upper())
    normalized = re.sub(r"[\s，。！？、,.!?：:；;（）()【】\[\]“”\"']", "", normalized)
    return normalized.lower()


def query_terms(query: str) -> list[str]:
    normalized = normalize_query(query)
    ascii_tokens = re.findall(r"[a-z0-9]+", normalized)
    cjk_tokens = [
        normalized[index : index + 2]
        for index in range(max(len(normalized) - 1, 0))
        if any("\u4e00" <= char <= "\u9fff" for char in normalized[index : index + 2])
    ]
    return sorted(set(ascii_tokens + cjk_tokens))


def query_similarity(left: str, right: str) -> float:
    left_normalized = normalize_query(left)
    right_normalized = normalize_query(right)
    if not left_normalized or not right_normalized:
        return 0.0

    left_terms = set(query_terms(left_normalized))
    right_terms = set(query_terms(right_normalized))
    token_score = (
        len(left_terms & right_terms) / len(left_terms | right_terms)
        if left_terms and right_terms
        else 0.0
    )
    sequence_score = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    return max(token_score, sequence_score)


def embed_query(query: str) -> list[float]:
    provider = os.getenv("EVIDENCE_CACHE_EMBEDDING_PROVIDER", "local").strip().lower()
    if provider in {"off", "disabled", "none"}:
        raise RuntimeError("evidence cache embedding disabled")
    if provider == "qwen":
        return memory_vector_service.embed_query(query)
    return _local_prototype_embedding(query)


def find_fresh_cache_entry(
    db: Session,
    *,
    patient_id: int,
    actor_role: str,
    access_purpose: str,
    intent: str,
    query: str,
    source_version_resolver: Callable[[SemanticEvidenceCache], str],
    threshold: float = SIMILARITY_THRESHOLD,
) -> CacheLookupResult:
    now = _utcnow_naive()
    stmt = (
        select(SemanticEvidenceCache)
        .where(SemanticEvidenceCache.patient_id == patient_id)
        .where(SemanticEvidenceCache.actor_role == actor_role)
        .where(SemanticEvidenceCache.access_purpose == access_purpose)
        .where(SemanticEvidenceCache.intent == intent)
        .where(SemanticEvidenceCache.expires_at > now)
        .order_by(SemanticEvidenceCache.created_at.desc(), SemanticEvidenceCache.id.desc())
        .limit(10)
    )
    entries = list(db.scalars(stmt).all())

    query_embedding = _try_embed_query(query)
    if query_embedding is not None:
        result = _find_by_embedding(
            db,
            entries=entries,
            query_embedding=query_embedding,
            source_version_resolver=source_version_resolver,
            threshold=EMBEDDING_SIMILARITY_THRESHOLD,
        )
        if result.entry is not None:
            return result
        if result.miss_reason not in {None, "cache_entry_embedding_missing"}:
            return result

    return _find_by_string_fallback(
        db,
        entries=entries,
        query=query,
        source_version_resolver=source_version_resolver,
        threshold=threshold,
    )


def _find_by_embedding(
    db: Session,
    *,
    entries: list[SemanticEvidenceCache],
    query_embedding: list[float],
    source_version_resolver: Callable[[SemanticEvidenceCache], str],
    threshold: float,
) -> CacheLookupResult:
    stale_reason: str | None = None
    best_entry: SemanticEvidenceCache | None = None
    best_score = 0.0
    saw_embedding = False
    for entry in entries:
        current_source_version = source_version_resolver(entry)
        if current_source_version != entry.source_version:
            stale_reason = "evidence_source_version_changed"
            continue
        entry_embedding = load_entry_query_embedding(entry)
        if entry_embedding is None:
            stale_reason = "cache_entry_embedding_missing"
            continue
        saw_embedding = True
        score = cosine_similarity(query_embedding, entry_embedding)
        if score > best_score:
            best_score = score
            best_entry = entry

    if best_entry is not None and best_score >= threshold:
        _mark_cache_hit(db, best_entry)
        return CacheLookupResult(
            entry=best_entry,
            match_strategy="embedding",
            similarity_score=round(best_score, 4),
        )
    if saw_embedding:
        return CacheLookupResult(
            miss_reason=stale_reason or "embedding_similarity_below_threshold",
            match_strategy="embedding",
            similarity_score=round(best_score, 4),
        )
    return CacheLookupResult(
        miss_reason=stale_reason,
        match_strategy="embedding",
        similarity_score=None,
    )


def _find_by_string_fallback(
    db: Session,
    *,
    entries: list[SemanticEvidenceCache],
    query: str,
    source_version_resolver: Callable[[SemanticEvidenceCache], str],
    threshold: float,
) -> CacheLookupResult:
    stale_reason: str | None = None
    best_score = 0.0
    for entry in entries:
        current_source_version = source_version_resolver(entry)
        if current_source_version != entry.source_version:
            stale_reason = "evidence_source_version_changed"
            continue
        score = query_similarity(query, entry.normalized_query)
        best_score = max(best_score, score)
        if score < threshold:
            stale_reason = "semantic_similarity_below_threshold"
            continue
        _mark_cache_hit(db, entry)
        return CacheLookupResult(
            entry=entry,
            match_strategy="string_fallback",
            similarity_score=round(score, 4),
        )
    return CacheLookupResult(
        miss_reason=stale_reason,
        match_strategy="string_fallback",
        similarity_score=round(best_score, 4) if entries else None,
    )


def create_cache_entry(
    db: Session,
    *,
    patient_id: int,
    actor_role: str,
    access_purpose: str,
    intent: str,
    query: str,
    tool_name: str,
    tool_arguments: dict,
    evidence: dict,
    source_version: str,
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> SemanticEvidenceCache:
    now = _utcnow_naive()
    query_embedding = _try_embed_query(query)
    entry = SemanticEvidenceCache(
        patient_id=patient_id,
        actor_role=actor_role,
        access_purpose=access_purpose,
        intent=intent,
        normalized_query=normalize_query(query),
        query_terms=json.dumps(query_terms(query), ensure_ascii=False),
        query_embedding=(
            json.dumps(query_embedding, ensure_ascii=False)
            if query_embedding is not None
            else None
        ),
        tool_name=tool_name,
        tool_arguments=json.dumps(tool_arguments, ensure_ascii=False, sort_keys=True),
        evidence=json.dumps(evidence, ensure_ascii=False, sort_keys=True),
        source_version=source_version,
        created_at=now,
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def load_entry_tool_arguments(entry: SemanticEvidenceCache) -> dict:
    return json.loads(entry.tool_arguments)


def load_entry_evidence(entry: SemanticEvidenceCache) -> dict:
    return json.loads(entry.evidence)


def load_entry_query_embedding(entry: SemanticEvidenceCache) -> list[float] | None:
    if not entry.query_embedding:
        return None
    try:
        value = json.loads(entry.query_embedding)
    except json.JSONDecodeError:
        return None
    if not isinstance(value, list):
        return None
    embedding = []
    for item in value:
        if not isinstance(item, (int, float)):
            return None
        embedding.append(float(item))
    return embedding


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _try_embed_query(query: str) -> list[float] | None:
    try:
        return embed_query(query)
    except Exception:
        return None


def _mark_cache_hit(db: Session, entry: SemanticEvidenceCache) -> None:
    entry.hit_count += 1
    entry.last_hit_at = _utcnow_naive()
    db.add(entry)
    db.commit()
    db.refresh(entry)


def _local_prototype_embedding(query: str) -> list[float]:
    normalized = normalize_query(query)
    terms = query_terms(query)
    vector: list[float] = []
    for _, keywords in LOCAL_EMBEDDING_FEATURES:
        score = 0.0
        for keyword in keywords:
            if normalize_query(keyword) in normalized:
                score += 1.0
        vector.append(score)

    hash_buckets = [0.0 for _ in range(LOCAL_EMBEDDING_HASH_DIMENSIONS)]
    for term in terms:
        bucket = sum(ord(char) for char in term) % LOCAL_EMBEDDING_HASH_DIMENSIONS
        hash_buckets[bucket] += 0.25
    vector.extend(hash_buckets)
    return _normalize_vector(vector)


def _normalize_vector(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 6) for value in vector]


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)
