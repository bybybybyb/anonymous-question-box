from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_backend_contract import admin_token, auth, new_user_token, settings

from aqbox.app import create_app
from aqbox.config import Settings
from aqbox.db import Database
from aqbox.llm_provider import LLMProviderRequest, LLMProviderResponse, LLMProviderUsage
from aqbox.services import LLMModerationWorker
from aqbox.settings_provider import SettingsProvider


def llm_settings(
    tmp_path: Path,
    *,
    enabled: bool = True,
    max_attempts: int = 2,
    high_confidence_reject_threshold: float = 0.85,
    review_all_model_rejects: bool = True,
) -> Settings:
    s = settings(tmp_path)
    s.llm_filter = {
        "enabled": enabled,
        "api_key": "test-key",
        "model": "test-model",
        "max_attempts": max_attempts,
        "timeout_seconds": 0.2,
        "initial_backoff_seconds": 0,
        "high_confidence_reject_threshold": high_confidence_reject_threshold,
        "review_all_model_rejects": review_all_model_rejects,
        "boxes": {"owner": {"question_types": {"type": {"enabled": True, "policy_prompt": "test policy"}}}},
    }
    s.__post_init__()
    return s


def provider_response(
    *,
    decision: str = "accept",
    category: str = "safe",
    confidence: float = 0.99,
    short_reason: str = "Safe submission",
    rationale: str = "No concern.",
    error_class: str | None = None,
    finish_reason: str | None = "stop",
    content: str | None = None,
    raw_response: dict[str, Any] | None = None,
) -> LLMProviderResponse:
    if content is None and error_class is None:
        content = json.dumps(
            {
                "decision": decision,
                "moderation_category": category,
                "confidence": confidence,
                "short_reason": short_reason,
                "rationale": rationale,
            }
        )
    return LLMProviderResponse(
        content=content,
        finish_reason=finish_reason,
        model="test-model",
        latency_ms=12.5,
        usage=LLMProviderUsage(prompt_tokens=7, completion_tokens=5, total_tokens=12),
        error_class=error_class,  # type: ignore[arg-type]
        http_status=200 if error_class is None else None,
        raw_response=raw_response,
    )


class FakeLLMProvider:
    def __init__(self, *responses: LLMProviderResponse):
        self.responses = list(responses)
        self.requests: list[LLMProviderRequest] = []
        self.on_complete: Any = None

    async def complete(self, request: LLMProviderRequest) -> LLMProviderResponse:
        self.requests.append(request)
        if self.on_complete is not None:
            await self.on_complete()
        if not self.responses:
            raise AssertionError("fake provider received unexpected request")
        return self.responses.pop(0)


class BlockingLLMProvider:
    def __init__(self, response: LLMProviderResponse):
        self.response = response
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.requests: list[LLMProviderRequest] = []

    async def complete(self, request: LLMProviderRequest) -> LLMProviderResponse:
        self.requests.append(request)
        self.started.set()
        await self.release.wait()
        return self.response


async def run_worker_once(db: Database, s: Settings, provider: FakeLLMProvider) -> None:
    worker = LLMModerationWorker(db, SettingsProvider(settings=s), provider=provider, poll_interval_seconds=0.01)
    await worker.run_once()


def submitted_pending_uuid(db: Database, s: Settings, text: str, *, provider: FakeLLMProvider | None = None) -> str:
    app = create_app(settings=s, db=db, llm_provider=provider or FakeLLMProvider())
    with TestClient(app) as client:
        token = new_user_token(client)
        submit = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": text},
            headers=auth(token),
        )
        assert submit.status_code == 200
        asker_read = client.get("/questions/question", headers=auth(token))
        assert asker_read.status_code == 200
        assert asker_read.json()["text"] == text
        return submit.json()["uuid"]


def test_llm_worker_migration_0005_is_idempotent_and_adds_queue_fields(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "aqbox.sqlite3"), moderation_schema=True)
    db.bootstrap()
    first = db.applied_migrations()
    db.bootstrap()

    state_columns = {row["name"] for row in db.conn.execute("PRAGMA table_info(question_moderation_state)").fetchall()}
    event_columns = {row["name"] for row in db.conn.execute("PRAGMA table_info(question_moderation_event)").fetchall()}

    assert first[-1] == "0005_llm_moderation_worker_fields"
    assert db.applied_migrations() == first
    assert {
        "attempt_count",
        "next_attempt_at",
        "locked_until",
        "lock_owner",
        "last_error_class",
        "last_attempt_at",
        "short_reason",
        "rationale",
        "confidence",
        "provider",
        "model",
        "prompt_version",
        "policy_hash",
        "config_hash",
        "finish_reason",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
        "latency_ms",
    } <= state_columns
    assert {
        "short_reason",
        "rationale",
        "confidence",
        "finish_reason",
        "prompt_tokens",
        "completion_tokens",
        "total_tokens",
    } <= event_columns


def test_llm_enabled_submit_inserts_pending_atomically_and_keyword_skip_still_blocks(tmp_path: Path) -> None:
    s = llm_settings(tmp_path)
    db = Database(s.db_path, moderation_schema=True)

    pending_uuid = submitted_pending_uuid(db, s, "gentle safe")
    keyword_uuid = submitted_pending_uuid(db, s, "blocked text")

    pending_state = db.conn.execute(
        "SELECT status, source, reason, attempt_count, next_attempt_at FROM question_moderation_state WHERE uuid = ?",
        (pending_uuid,),
    ).fetchone()
    keyword_state = db.conn.execute(
        "SELECT status, source, reason FROM question_moderation_state WHERE uuid = ?",
        (keyword_uuid,),
    ).fetchone()
    events = db.conn.execute(
        "SELECT event_type, status, source, reason FROM question_moderation_event WHERE uuid = ? ORDER BY id",
        (pending_uuid,),
    ).fetchall()

    assert dict(pending_state) == {
        "status": "pending",
        "source": "llm",
        "reason": "queued",
        "attempt_count": 0,
        "next_attempt_at": pending_state["next_attempt_at"],
    }
    assert pending_state["next_attempt_at"] is not None
    assert [tuple(row) for row in events] == [("queued", "pending", "llm", "queued")]
    assert dict(keyword_state) == {"status": "blocked", "source": "keyword", "reason": "keyword"}


def test_worker_accepts_safe_pending_submission_and_normal_visibility_returns(tmp_path: Path) -> None:
    s = llm_settings(tmp_path)
    db = Database(s.db_path, moderation_schema=True)
    provider = FakeLLMProvider(provider_response())
    uuid = submitted_pending_uuid(db, s, "gentle safe", provider=provider)

    asyncio.run(run_worker_once(db, s, provider))

    state = db.conn.execute("SELECT * FROM question_moderation_state WHERE uuid = ?", (uuid,)).fetchone()
    events = db.conn.execute(
        """
        SELECT event_type, status, source, reason, model, short_reason, prompt_tokens, total_tokens
        FROM question_moderation_event
        WHERE uuid = ?
        ORDER BY id
        """,
        (uuid,),
    ).fetchall()
    with TestClient(create_app(settings=s, db=db, llm_provider=FakeLLMProvider())) as client:
        normal = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=auth(admin_token(s)),
        )

    assert state is None
    assert [tuple(row)[:4] for row in events] == [("queued", "pending", "llm", "queued"), ("accepted", "approved", "llm", "model_accept")]
    assert events[1]["model"] == "test-model"
    assert events[1]["short_reason"] == "Safe submission"
    assert events[1]["prompt_tokens"] == 7
    assert events[1]["total_tokens"] == 12
    assert normal.json()["total"] == 1
    assert normal.json()["questions"][0]["uuid"] == uuid


@pytest.mark.parametrize(
    ("confidence", "review_all", "expected_source", "expected_reason"),
    [
        (0.93, False, "llm", "model_reject"),
        (0.42, False, "llm_low_confidence", "needs_review"),
        (0.93, True, "llm", "model_reject"),
    ],
)
def test_worker_rejects_to_review_queue_with_threshold_and_review_all_framing(
    tmp_path: Path,
    confidence: float,
    review_all: bool,
    expected_source: str,
    expected_reason: str,
) -> None:
    s = llm_settings(tmp_path, high_confidence_reject_threshold=0.85, review_all_model_rejects=review_all)
    db = Database(s.db_path, moderation_schema=True)
    provider = FakeLLMProvider(
        provider_response(
            decision="reject",
            category="harassment",
            confidence=confidence,
            short_reason="Harassing submission",
            rationale="The submission is abusive.",
        )
    )
    uuid = submitted_pending_uuid(db, s, "mean text", provider=provider)

    asyncio.run(run_worker_once(db, s, provider))

    state = db.conn.execute(
        "SELECT status, source, reason, category, confidence, short_reason FROM question_moderation_state WHERE uuid = ?",
        (uuid,),
    ).fetchone()
    assert dict(state) == {
        "status": "blocked",
        "source": expected_source,
        "reason": expected_reason,
        "category": "harassment",
        "confidence": confidence,
        "short_reason": "Harassing submission",
    }
    with TestClient(create_app(settings=s, db=db, llm_provider=FakeLLMProvider())) as client:
        review = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "moderation_status": "blocked", "day_limit": 1},
            headers=auth(admin_token(s)),
        )
    assert review.json()["total"] == 1
    assert review.json()["questions"][0]["uuid"] == uuid


def test_worker_provider_error_and_invalid_response_exhaust_to_llm_error_review(tmp_path: Path) -> None:
    s = llm_settings(tmp_path, max_attempts=2)
    db = Database(s.db_path, moderation_schema=True)
    provider = FakeLLMProvider(
        provider_response(error_class="timeout", finish_reason=None),
        provider_response(content='{"decision": "accept"}'),
    )
    uuid = submitted_pending_uuid(db, s, "needs retries", provider=provider)

    asyncio.run(run_worker_once(db, s, provider))
    retry_state = db.conn.execute(
        "SELECT status, attempt_count, last_error_class FROM question_moderation_state WHERE uuid = ?",
        (uuid,),
    ).fetchone()
    asyncio.run(run_worker_once(db, s, provider))
    final_state = db.conn.execute(
        "SELECT status, source, reason, attempt_count, last_error_class FROM question_moderation_state WHERE uuid = ?",
        (uuid,),
    ).fetchone()

    assert dict(retry_state) == {"status": "pending", "attempt_count": 1, "last_error_class": "timeout"}
    assert dict(final_state) == {
        "status": "blocked",
        "source": "llm_error",
        "reason": "never_evaluated",
        "attempt_count": 2,
        "last_error_class": "invalid_response_missing_field",
    }


def test_worker_moves_pending_to_review_when_llm_hot_reload_disables_policy(tmp_path: Path) -> None:
    s = llm_settings(tmp_path)
    db = Database(s.db_path, moderation_schema=True)
    uuid = submitted_pending_uuid(db, s, "gentle safe")
    s.llm_filter["enabled"] = False
    s.__post_init__()

    asyncio.run(run_worker_once(db, s, FakeLLMProvider()))

    state = db.conn.execute(
        "SELECT status, source, reason, last_error_class FROM question_moderation_state WHERE uuid = ?", (uuid,)
    ).fetchone()
    assert dict(state) == {
        "status": "blocked",
        "source": "llm_error",
        "reason": "never_evaluated",
        "last_error_class": "config_disabled",
    }


def test_worker_moves_in_flight_pending_to_review_when_llm_hot_reload_disables_policy(tmp_path: Path) -> None:
    async def run() -> None:
        s = llm_settings(tmp_path)
        db = Database(s.db_path, moderation_schema=True)
        provider = BlockingLLMProvider(provider_response())
        uuid = submitted_pending_uuid(db, s, "gentle safe", provider=provider)  # type: ignore[arg-type]
        worker = LLMModerationWorker(db, SettingsProvider(settings=s), provider=provider, poll_interval_seconds=0.01)
        task = asyncio.create_task(worker.run_once())
        await provider.started.wait()

        s.llm_filter["enabled"] = False
        s.__post_init__()
        provider.release.set()
        await task

        state = db.conn.execute(
            "SELECT status, source, reason, last_error_class FROM question_moderation_state WHERE uuid = ?", (uuid,)
        ).fetchone()
        events = db.conn.execute(
            "SELECT event_type, status, source, reason, error_class FROM question_moderation_event WHERE uuid = ? ORDER BY id",
            (uuid,),
        ).fetchall()
        assert dict(state) == {
            "status": "blocked",
            "source": "llm_error",
            "reason": "never_evaluated",
            "last_error_class": "config_disabled",
        }
        assert [tuple(row) for row in events] == [
            ("queued", "pending", "llm", "queued", ""),
            ("blocked", "blocked", "llm_error", "never_evaluated", "config_disabled"),
        ]

    asyncio.run(run())


def test_worker_exhausts_due_pending_row_when_hot_reload_lowers_max_attempts(tmp_path: Path) -> None:
    s = llm_settings(tmp_path, max_attempts=3)
    db = Database(s.db_path, moderation_schema=True)
    provider = FakeLLMProvider(provider_response(error_class="timeout", finish_reason=None))
    uuid = submitted_pending_uuid(db, s, "needs retries", provider=provider)
    asyncio.run(run_worker_once(db, s, provider))
    s.llm_filter["max_attempts"] = 1
    s.__post_init__()

    asyncio.run(run_worker_once(db, s, FakeLLMProvider()))

    state = db.conn.execute(
        "SELECT status, source, reason, attempt_count, last_error_class FROM question_moderation_state WHERE uuid = ?",
        (uuid,),
    ).fetchone()
    assert dict(state) == {
        "status": "blocked",
        "source": "llm_error",
        "reason": "never_evaluated",
        "attempt_count": 1,
        "last_error_class": "max_attempts_exhausted",
    }


def test_worker_does_not_hold_database_lock_across_provider_io(tmp_path: Path) -> None:
    s = llm_settings(tmp_path)
    db = Database(s.db_path, moderation_schema=True)
    provider = FakeLLMProvider(provider_response())
    uuid = submitted_pending_uuid(db, s, "gentle safe", provider=provider)
    observed_count = 0

    async def provider_can_read_db() -> None:
        nonlocal observed_count
        observed_count = db.conn.execute("SELECT COUNT(*) FROM question WHERE uuid = ?", (uuid,)).fetchone()[0]

    provider.on_complete = provider_can_read_db
    asyncio.run(run_worker_once(db, s, provider))

    assert observed_count == 1


def test_worker_raw_retention_stores_raw_payloads_without_api_key_when_enabled(tmp_path: Path) -> None:
    s = llm_settings(tmp_path)
    s.llm_filter["raw_retention_enabled"] = True
    s.llm_filter["raw_retention_seconds"] = 60
    s.__post_init__()
    db = Database(s.db_path, moderation_schema=True)
    provider = FakeLLMProvider(provider_response(raw_response={"id": "raw-response"}))
    uuid = submitted_pending_uuid(db, s, "gentle safe", provider=provider)

    asyncio.run(run_worker_once(db, s, provider))

    event = db.conn.execute(
        """
        SELECT raw_prompt, raw_request, raw_response, purge_after
        FROM question_moderation_event
        WHERE uuid = ? AND event_type = 'accepted'
        """,
        (uuid,),
    ).fetchone()
    assert event["raw_prompt"]
    assert event["raw_request"]
    assert json.loads(event["raw_response"]) == {"id": "raw-response"}
    assert event["purge_after"] is not None
    assert "test-key" not in event["raw_request"]


def test_claim_finalize_requires_matching_lock_owner(tmp_path: Path) -> None:
    s = llm_settings(tmp_path)
    db = Database(s.db_path, moderation_schema=True)
    uuid = submitted_pending_uuid(db, s, "gentle safe")
    claimed = db.claim_due_llm_moderation(now=9_999_999_999, lock_owner="worker-a", lock_seconds=30, limit=1)

    wrong_owner = db.finalize_llm_moderation_accept(uuid=uuid, lock_owner="worker-b", finalized_at=2_001, metadata={})
    right_owner = db.finalize_llm_moderation_accept(uuid=uuid, lock_owner="worker-a", finalized_at=2_002, metadata={})

    assert [item["uuid"] for item in claimed] == [uuid]
    assert wrong_owner is False
    assert right_owner is True


def test_ops_health_includes_moderation_worker_details_when_llm_enabled(tmp_path: Path) -> None:
    s = llm_settings(tmp_path)
    db = Database(s.db_path, moderation_schema=True)
    provider = FakeLLMProvider()
    app = create_app(settings=s, db=db, llm_provider=provider)
    with TestClient(app) as client:
        health = client.get("/ops/health")

    assert health.status_code == 200
    payload = health.json()
    assert payload["ok"] is True
    assert payload["moderation_worker"]["enabled"] is True
    assert payload["moderation_worker"]["running"] is True
    assert set(payload["moderation_worker"]) >= {"pending", "due", "locked", "last_successful_check_at", "recent_error_class"}
    assert "test-key" not in health.text
