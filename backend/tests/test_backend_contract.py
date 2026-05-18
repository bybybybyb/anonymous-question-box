from __future__ import annotations

import asyncio
from contextlib import suppress
from pathlib import Path
from time import time

import jwt
import pytest
import yaml
from fastapi.testclient import TestClient

from aqbox.app import create_app
from aqbox.config import Settings, load_settings
from aqbox.db import LOCATION_NO_DATA_LABEL, LOCATION_NO_DATA_VALUE, Database
from aqbox.geo import lookup_and_store, parse_region
from aqbox.moderation import llm_policy_for
from aqbox.rate_limit import TokenBucketRateLimiter
from aqbox.services import GeoService, VisitService
from aqbox.settings_provider import SettingsProvider


def settings(tmp_path: Path, *, geo_enabled: bool = False, trusted_proxy_cidrs: list[str] | None = None) -> Settings:
    return Settings(
        db_path=str(tmp_path / "aqbox.sqlite3"),
        jwt_secret_key="secret",
        magic_spell="spell",
        filtered_keywords=["blocked"],
        geo_enabled=geo_enabled,
        trusted_proxy_cidrs=trusted_proxy_cidrs or ["127.0.0.1/32", "::1/128"],
        owner_profiles={
            "owner": {
                "name": "owner",
                "colors": {"primary_color": "#111", "secondary_color": "#eee"},
                "question_types": {
                    "type": {
                        "name": "type",
                        "description": "Type",
                        "rune_limit": 20,
                        "theme": {"name": "theme", "background_class": "bg"},
                        "support_image": True,
                    }
                },
            }
        },
        metadata={"introductions": [], "console_prints": [], "admin": {}},
    )


def make_client(settings: Settings, *, client_addr: tuple[str, int] = ("127.0.0.1", 50000)) -> TestClient:
    db = Database(settings.db_path, geo_enabled=settings.geo_enabled, moderation_schema=bool(settings.llm_filter))
    return TestClient(create_app(settings=settings, db=db), client=client_addr)


def make_app_and_db(settings: Settings) -> tuple[object, Database]:
    db = Database(settings.db_path, geo_enabled=settings.geo_enabled, moderation_schema=bool(settings.llm_filter))
    return create_app(settings=settings, db=db), db


def admin_token(s: Settings, owner: str = "owner") -> str:
    now = int(time())
    return jwt.encode({s.magic_spell: owner, "iat": now, "exp": now + 3600}, s.jwt_secret_key, algorithm="HS256")


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def new_user_token(client: TestClient) -> str:
    return client.get("/new").json()["token"]


def insert_llm_blocked_state(
    db: Database,
    uuid: str,
    *,
    short_reason: str = "Harassing submission",
    rationale: str = "The submission is abusive.",
) -> None:
    row = db.conn.execute("SELECT asked_at FROM question WHERE uuid = ?", (uuid,)).fetchone()
    assert row is not None
    created_at = int(row["asked_at"])
    db.conn.execute(
        """
        INSERT INTO question_moderation_state (
          uuid, status, source, reason, category, short_reason, rationale, created_at, updated_at
        )
        VALUES (?, 'blocked', 'llm', 'model_reject', 'harassment', ?, ?, ?, ?)
        """,
        (uuid, short_reason, rationale, created_at, created_at),
    )
    db.conn.execute(
        """
        INSERT INTO question_moderation_event (
          uuid, event_type, status, source, reason, category, short_reason, rationale, created_at
        )
        VALUES (?, 'blocked', 'blocked', 'llm', 'model_reject', 'harassment', ?, ?, ?)
        """,
        (uuid, short_reason, rationale, created_at),
    )
    db.conn.commit()


def config_payload(tmp_path: Path, **overrides) -> dict:
    payload = {
        "db_path": str(tmp_path / "aqbox.sqlite3"),
        "jwt_secret_key": "secret",
        "magic_spell": "spell",
        "filtered_keywords": ["blocked"],
        "geo_enabled": False,
        "trusted_proxy_cidrs": ["127.0.0.1/32", "::1/128"],
        "visit_flush_interval_seconds": 10,
        "owner_profiles": {
            "owner": {
                "name": "owner",
                "colors": {"primary_color": "#111", "secondary_color": "#eee"},
                "question_types": {
                    "type": {
                        "name": "type",
                        "description": "Type",
                        "rune_limit": 20,
                        "theme": {"name": "theme", "background_class": "bg"},
                        "support_image": True,
                    }
                },
            }
        },
        "metadata": {"introductions": ["hello"], "console_prints": [], "admin": {}},
    }
    payload.update(overrides)
    return payload


def write_config(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def config_client(
    tmp_path: Path,
    payload: dict | None = None,
    *,
    client_addr: tuple[str, int] = ("127.0.0.1", 50000),
) -> tuple[TestClient, Path]:
    config_path = tmp_path / "config.yaml"
    write_config(config_path, payload or config_payload(tmp_path))
    client = TestClient(create_app(config_path=str(config_path)), client=client_addr)
    client.app.state.settings_provider._check_interval_seconds = 0
    client.app.state.settings_provider._next_check_at = 0
    return client, config_path


def test_profiles_force_support_image_false(tmp_path: Path) -> None:
    s = settings(tmp_path)
    with make_client(s) as client:
        resp = client.get("/profiles")
    assert resp.status_code == 200
    qtype = resp.json()["owner_profiles"]["owner"]["question_types"]["type"]
    assert qtype["support_image"] is False


def test_geo_enabled_defaults_to_true_when_config_omits_it(tmp_path: Path) -> None:
    payload = config_payload(tmp_path)
    payload.pop("geo_enabled")
    config_path = tmp_path / "config.yaml"
    write_config(config_path, payload)

    s = load_settings(str(config_path))

    assert s.geo_enabled is True


def test_sqlite_connection_uses_wal_and_busy_timeout(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "aqbox.sqlite3"))
    try:
        assert db.conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert db.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    finally:
        db.conn.close()


def test_schema_migrations_are_recorded_once(tmp_path: Path) -> None:
    db = Database(str(tmp_path / "aqbox.sqlite3"))
    db.bootstrap()
    first = db.applied_migrations()
    db.bootstrap()
    second = db.applied_migrations()
    assert first == [
        "0001_phase1_core",
        "0002_ip2region_geo",
        "0003_moderation_scaffold",
        "0004_moderation_state_events",
        "0005_llm_moderation_worker_fields",
        "0006_deletion_provenance",
    ]
    assert second == first
    assert db.conn.execute("SELECT COUNT(*) FROM question_moderation_state").fetchone()[0] == 0
    assert db.conn.execute("SELECT COUNT(*) FROM question_moderation_event").fetchone()[0] == 0


def test_image_routes_removed_and_submit_images_rejected(tmp_path: Path) -> None:
    s = settings(tmp_path)
    with make_client(s) as client:
        token = new_user_token(client)
        image_route = client.post("/image/process")
        resp = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "hello", "images": [{"image_id": "x"}]},
            headers=auth(token),
        )
    assert image_route.status_code == 404
    assert resp.status_code == 400
    assert resp.json() == {"error": "本提问箱不支持图片上传"}


def test_images_null_is_accepted_like_legacy_empty_images(tmp_path: Path) -> None:
    s = settings(tmp_path)
    with make_client(s) as client:
        token = new_user_token(client)
        resp = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "hello", "images": None},
            headers=auth(token),
        )
    assert resp.status_code == 200


def test_keyword_block_stealth_deletes_without_moderation_state_and_respects_visibility(tmp_path: Path) -> None:
    s = settings(tmp_path)
    app, db = make_app_and_db(s)
    with TestClient(app) as client:
        token = new_user_token(client)
        submit = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "blocked text"},
            headers=auth(token),
        )
        asker_read = client.get("/questions/question", headers=auth(token))
        owner_list = client.post(
            "/owner/questions",
            json={
                "owner": "owner",
                "type": "type",
                "order_params": {"by": "asked_at", "reversed": True},
                "day_limit": 1,
                "page_size": 10,
                "page": 1,
            },
            headers=auth(admin_token(s)),
        )
        owner_review = client.post(
            "/owner/questions",
            json={
                "owner": "owner",
                "type": "type",
                "moderation_status": "blocked",
                "day_limit": 1,
                "page_size": 10,
                "page": 1,
            },
            headers=auth(admin_token(s)),
        )
        owner_detail = client.get(f"/owner/questions/{submit.json()['uuid']}", headers=auth(admin_token(s)))
    uuid = submit.json()["uuid"]
    question_row = db.conn.execute("SELECT asked_at, deleted_at, deletion_source FROM question WHERE uuid = ?", (uuid,)).fetchone()
    state_row = db.conn.execute(
        "SELECT status, source, reason, category FROM question_moderation_state WHERE uuid = ?",
        (uuid,),
    ).fetchone()
    event_rows = db.conn.execute(
        "SELECT event_type, status, source, reason FROM question_moderation_event WHERE uuid = ?",
        (uuid,),
    ).fetchall()
    assert submit.status_code == 200
    assert question_row is not None
    assert question_row["deleted_at"] == question_row["asked_at"]
    assert question_row["deletion_source"] == "keyword"
    assert state_row is None
    assert event_rows == []
    assert asker_read.status_code == 200
    assert asker_read.json()["text"] == "blocked text"
    assert asker_read.json()["images"] == []
    assert "ip" not in asker_read.json()
    assert "moderation" not in asker_read.json()
    assert owner_list.status_code == 200
    assert owner_list.json()["total"] == 0
    assert owner_list.json()["moderation_counts"]["blocked"] == 0
    assert owner_review.status_code == 200
    assert owner_review.json()["total"] == 0
    assert owner_detail.status_code == 404
    assert owner_detail.json() == {"error": "投稿不存在"}


def test_owner_blocked_payload_exposes_safe_moderation_metadata(tmp_path: Path) -> None:
    s = settings(tmp_path)
    app, db = make_app_and_db(s)
    with TestClient(app) as client:
        token = new_user_token(client)
        uuid = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "mean text"},
            headers=auth(token),
        ).json()["uuid"]
        insert_llm_blocked_state(
            db,
            uuid,
            short_reason="Harassing submission",
            rationale="The submission targets a person with abusive language.",
        )
        owner_headers = auth(admin_token(s))
        review = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "moderation_status": "blocked", "day_limit": 1},
            headers=owner_headers,
        )
        detail = client.get(f"/owner/questions/{uuid}", headers=owner_headers)
        revealed_detail = client.get(f"/owner/questions/{uuid}?reveal_raw=1", headers=owner_headers)

    assert review.status_code == 200
    assert detail.status_code == 200
    assert revealed_detail.status_code == 200
    assert review.json()["questions"][0]["text"] == ""
    assert review.json()["questions"][0]["raw_text_hidden"] is True
    assert detail.json()["text"] == ""
    assert detail.json()["raw_text_hidden"] is True
    assert revealed_detail.json()["text"] == "mean text"
    assert "raw_text_hidden" not in revealed_detail.json()
    review_moderation = review.json()["questions"][0]["moderation"]
    detail_moderation = detail.json()["moderation"]
    assert review_moderation["status"] == "blocked"
    assert review_moderation["source"] == "llm"
    assert review_moderation["category"] == "harassment"
    assert review_moderation["reason"] == "model_reject"
    assert review_moderation["short_reason"] == "Harassing submission"
    assert review_moderation["rationale"] == "The submission targets a person with abusive language."
    assert detail_moderation["short_reason"] == review_moderation["short_reason"]
    assert detail_moderation["rationale"] == review_moderation["rationale"]
    assert "created_at" in detail_moderation
    assert "updated_at" in detail_moderation


def test_answering_blocked_submission_does_not_approve_it(tmp_path: Path) -> None:
    s = settings(tmp_path)
    with make_client(s) as client:
        token = new_user_token(client)
        submit = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "mean text"},
            headers=auth(token),
        )
        uuid = submit.json()["uuid"]
        insert_llm_blocked_state(client.app.state.db, uuid)
        owner_headers = auth(admin_token(s))
        answer = client.put(
            f"/owner/questions/{uuid}/answer",
            json={"uuid": uuid, "answer": "should not write", "answered_by": "manual"},
            headers=owner_headers,
        )
        normal = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=owner_headers,
        )
        review = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "moderation_status": "blocked", "day_limit": 1, "reply_status": 1},
            headers=owner_headers,
        )
        asker_read = client.get("/questions/question", headers=auth(token))
    assert answer.status_code == 200
    assert normal.json()["total"] == 0
    assert review.json()["total"] == 1
    assert review.json()["questions"][0]["answer"] == "should not write"
    assert review.json()["questions"][0]["moderation"]["status"] == "blocked"
    assert asker_read.status_code == 200
    assert asker_read.json()["answer"] == "should not write"


def test_approve_blocked_submission_is_idempotent_and_returns_to_normal_list(tmp_path: Path) -> None:
    s = settings(tmp_path)
    app, db = make_app_and_db(s)
    with TestClient(app) as client:
        token = new_user_token(client)
        submit = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "mean text"},
            headers=auth(token),
        )
        uuid = submit.json()["uuid"]
        insert_llm_blocked_state(db, uuid)
        owner_headers = auth(admin_token(s))
        approve = client.put(f"/owner/questions/{uuid}/moderation/approve", headers=owner_headers)
        approve_again = client.put(f"/owner/questions/{uuid}/moderation/approve", headers=owner_headers)
        normal = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=owner_headers,
        )
        review = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "moderation_status": "blocked", "day_limit": 1},
            headers=owner_headers,
        )
        detail = client.get(f"/owner/questions/{uuid}", headers=owner_headers)
    events = db.conn.execute(
        "SELECT event_type, status FROM question_moderation_event WHERE uuid = ? ORDER BY id",
        (uuid,),
    ).fetchall()
    assert approve.status_code == 200
    assert approve_again.status_code == 200
    assert normal.json()["total"] == 1
    assert normal.json()["questions"][0]["uuid"] == uuid
    assert normal.json()["questions"][0]["moderation"]["status"] == "approved"
    assert review.json()["total"] == 0
    assert detail.json()["moderation"]["status"] == "approved"
    assert [tuple(row) for row in events] == [("blocked", "blocked"), ("approved", "approved")]


def test_approve_race_does_not_emit_duplicate_approval_event(tmp_path: Path) -> None:
    s = settings(tmp_path)
    app, db = make_app_and_db(s)
    with TestClient(app) as client:
        token = new_user_token(client)
        uuid = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "mean text"},
            headers=auth(token),
        ).json()["uuid"]
        insert_llm_blocked_state(db, uuid)

    original_conn = db.conn

    class ConcurrentApprovalConnection:
        def __init__(self) -> None:
            self.raced = False

        def execute(self, sql: str, params: tuple = ()):
            if not self.raced and "UPDATE question_moderation_state" in sql and "WHERE uuid = ? AND status = 'blocked'" in sql:
                self.raced = True
                original_conn.execute(
                    "UPDATE question_moderation_state SET status = 'approved', updated_at = ? WHERE uuid = ?",
                    (111, uuid),
                )
                original_conn.execute(
                    """
                    INSERT INTO question_moderation_event (
                      uuid, event_type, status, source, reason, category, actor, created_at
                    )
                    VALUES (?, 'approved', 'approved', 'llm', 'model_reject', 'harassment', 'other-owner', ?)
                    """,
                    (uuid, 111),
                )
            return original_conn.execute(sql, params)

        def commit(self) -> None:
            original_conn.commit()

        def rollback(self) -> None:
            original_conn.rollback()

    db.conn = ConcurrentApprovalConnection()  # type: ignore[assignment]
    try:
        result = db.approve_moderation(uuid, 222)
    finally:
        db.conn = original_conn
    events = db.conn.execute(
        "SELECT event_type, status, actor, created_at FROM question_moderation_event WHERE uuid = ? ORDER BY id",
        (uuid,),
    ).fetchall()

    assert result == "already_approved"
    assert [tuple(row)[:3] for row in events] == [
        ("blocked", "blocked", ""),
        ("approved", "approved", "other-owner"),
    ]
    assert events[1]["created_at"] == 111


def test_approve_race_with_delete_does_not_emit_approval_event(tmp_path: Path) -> None:
    s = settings(tmp_path)
    app, db = make_app_and_db(s)
    with TestClient(app) as client:
        token = new_user_token(client)
        uuid = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "mean text"},
            headers=auth(token),
        ).json()["uuid"]
        insert_llm_blocked_state(db, uuid)

    original_conn = db.conn

    class ConcurrentDeleteConnection:
        def __init__(self) -> None:
            self.raced = False

        def execute(self, sql: str, params: tuple = ()):
            if not self.raced and "UPDATE question_moderation_state" in sql and "SET status = 'approved'" in sql:
                self.raced = True
                original_conn.execute(
                    "UPDATE question SET deleted_at = ? WHERE uuid = ? AND deleted_at IS NULL",
                    (111, uuid),
                )
            return original_conn.execute(sql, params)

        def commit(self) -> None:
            original_conn.commit()

        def rollback(self) -> None:
            original_conn.rollback()

    db.conn = ConcurrentDeleteConnection()  # type: ignore[assignment]
    try:
        result = db.approve_moderation(uuid, 222)
    finally:
        db.conn = original_conn
    events = db.conn.execute(
        "SELECT event_type, status FROM question_moderation_event WHERE uuid = ? ORDER BY id",
        (uuid,),
    ).fetchall()
    state = db.conn.execute(
        "SELECT status FROM question_moderation_state WHERE uuid = ?",
        (uuid,),
    ).fetchone()

    assert result == "deleted"
    assert [tuple(row) for row in events] == [("blocked", "blocked")]
    assert state["status"] == "blocked"


def test_invalid_approval_states_return_legacy_errors(tmp_path: Path) -> None:
    s = settings(tmp_path)
    app, db = make_app_and_db(s)
    with TestClient(app) as client:
        owner_headers = auth(admin_token(s))
        normal_token = new_user_token(client)
        normal_uuid = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "normal"},
            headers=auth(normal_token),
        ).json()["uuid"]
        pending_token = new_user_token(client)
        pending_uuid = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "pending"},
            headers=auth(pending_token),
        ).json()["uuid"]
        db.conn.execute(
            """
            INSERT INTO question_moderation_state (uuid, status, source, reason, created_at, updated_at)
            VALUES (?, 'pending', 'llm', 'queued', 1, 1)
            """,
            (pending_uuid,),
        )
        db.conn.commit()
        blocked_token = new_user_token(client)
        deleted_uuid = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "blocked text"},
            headers=auth(blocked_token),
        ).json()["uuid"]

        normal_approve = client.put(f"/owner/questions/{normal_uuid}/moderation/approve", headers=owner_headers)
        pending_approve = client.put(f"/owner/questions/{pending_uuid}/moderation/approve", headers=owner_headers)
        deleted_approve = client.put(f"/owner/questions/{deleted_uuid}/moderation/approve", headers=owner_headers)
        pending_detail = client.get(f"/owner/questions/{pending_uuid}", headers=owner_headers)

    assert normal_approve.status_code == 400
    assert normal_approve.json() == {"error": "投稿没有可审批的审核状态"}
    assert pending_approve.status_code == 400
    assert pending_approve.json() == {"error": "待审核投稿不能手动批准"}
    assert deleted_approve.status_code == 404
    assert deleted_approve.json() == {"error": "投稿不存在或已删除"}
    assert pending_detail.status_code == 404
    assert pending_detail.json() == {"error": "投稿不存在"}


def test_approve_old_style_keyword_block_returns_deleted_behavior_without_event(tmp_path: Path) -> None:
    s = settings(tmp_path)
    app, db = make_app_and_db(s)
    with TestClient(app) as client:
        owner_headers = auth(admin_token(s))
        token = new_user_token(client)
        uuid = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "old keyword state"},
            headers=auth(token),
        ).json()["uuid"]
        db.conn.execute(
            """
            INSERT INTO question_moderation_state (uuid, status, source, reason, created_at, updated_at)
            VALUES (?, 'blocked', 'keyword', 'keyword', 1, 1)
            """,
            (uuid,),
        )
        db.conn.commit()

        approve = client.put(f"/owner/questions/{uuid}/moderation/approve", headers=owner_headers)

    state = db.conn.execute(
        "SELECT status, source, reason FROM question_moderation_state WHERE uuid = ?",
        (uuid,),
    ).fetchone()
    events = db.conn.execute(
        "SELECT event_type, status, source, reason FROM question_moderation_event WHERE uuid = ?",
        (uuid,),
    ).fetchall()

    assert approve.status_code == 404
    assert approve.json() == {"error": "投稿不存在或已删除"}
    assert dict(state) == {"status": "blocked", "source": "keyword", "reason": "keyword"}
    assert events == []


def test_owner_detail_hides_old_style_keyword_block_as_not_found(tmp_path: Path) -> None:
    s = settings(tmp_path)
    app, db = make_app_and_db(s)
    with TestClient(app) as client:
        owner_headers = auth(admin_token(s))
        token = new_user_token(client)
        uuid = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "old keyword"},
            headers=auth(token),
        ).json()["uuid"]
        db.conn.execute(
            """
            INSERT INTO question_moderation_state (uuid, status, source, reason, created_at, updated_at)
            VALUES (?, 'blocked', 'keyword', 'keyword', 1, 1)
            """,
            (uuid,),
        )
        db.conn.commit()

        detail = client.get(f"/owner/questions/{uuid}", headers=owner_headers)

    assert detail.status_code == 404
    assert detail.json() == {"error": "投稿不存在"}


def test_owner_normal_views_hide_historical_approved_keyword_rows(tmp_path: Path) -> None:
    s = settings(tmp_path, geo_enabled=True, trusted_proxy_cidrs=["127.0.0.1/32"])
    app, db = make_app_and_db(s)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        owner_headers = auth(admin_token(s))
        normal_token = new_user_token(client)
        client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "normal"},
            headers={**auth(normal_token), "X-Real-IP": "8.8.8.8"},
        )
        approved_keyword_token = new_user_token(client)
        approved_keyword_uuid = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "old keyword"},
            headers={**auth(approved_keyword_token), "X-Real-IP": "9.9.9.9"},
        ).json()["uuid"]
        db.conn.execute(
            """
            INSERT INTO question_moderation_state (uuid, status, source, reason, created_at, updated_at)
            VALUES (?, 'approved', 'keyword', 'keyword', 1, 1)
            """,
            (approved_keyword_uuid,),
        )
        db.conn.commit()
        db.insert_ip_geo({"ip": "8.8.8.8", "addr": "正常地区", "isp": "正常运营商", "provider": "ip2region", "looked_up_at": 1})
        db.insert_ip_geo({"ip": "9.9.9.9", "addr": "历史关键词地区", "isp": "历史关键词运营商", "provider": "ip2region", "looked_up_at": 1})

        normal = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=owner_headers,
        )
        keyword_location = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1, "ip_addr": "历史关键词地区"},
            headers=owner_headers,
        )
        detail = client.get(f"/owner/questions/{approved_keyword_uuid}", headers=owner_headers)
        approve = client.put(f"/owner/questions/{approved_keyword_uuid}/moderation/approve", headers=owner_headers)

    assert normal.status_code == 200
    assert normal.json()["total"] == 1
    assert [question["text"] for question in normal.json()["questions"]] == ["normal"]
    assert {option["addr"] for option in normal.json()["location_options"]} == {"正常地区"}
    assert keyword_location.status_code == 200
    assert keyword_location.json()["total"] == 0
    assert detail.status_code == 404
    assert detail.json() == {"error": "投稿不存在"}
    assert approve.status_code == 404
    assert approve.json() == {"error": "投稿不存在或已删除"}


def test_delete_moderated_submission_hides_it_and_records_event(tmp_path: Path) -> None:
    s = settings(tmp_path)
    app, db = make_app_and_db(s)
    with TestClient(app) as client:
        token = new_user_token(client)
        uuid = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "mean text"},
            headers=auth(token),
        ).json()["uuid"]
        insert_llm_blocked_state(db, uuid)
        owner_headers = auth(admin_token(s))
        delete = client.delete(f"/owner/questions/{uuid}/delete", headers=owner_headers)
        normal = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=owner_headers,
        )
        review = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "moderation_status": "blocked", "day_limit": 1},
            headers=owner_headers,
        )
        detail = client.get(f"/owner/questions/{uuid}", headers=owner_headers)
        asker_read = client.get("/questions/question", headers=auth(token))
    events = db.conn.execute(
        "SELECT event_type, status FROM question_moderation_event WHERE uuid = ? ORDER BY id",
        (uuid,),
    ).fetchall()
    question_row = db.conn.execute("SELECT deletion_source FROM question WHERE uuid = ?", (uuid,)).fetchone()
    assert delete.status_code == 200
    assert question_row["deletion_source"] == "owner_manual"
    assert normal.json()["total"] == 0
    assert review.json()["total"] == 0
    assert detail.status_code == 404
    assert asker_read.status_code == 200
    assert asker_read.json()["text"] == "mean text"
    assert [tuple(row) for row in events] == [("blocked", "blocked"), ("deleted", "blocked")]


def test_delete_unmoderated_submission_records_owner_manual_deletion_source(tmp_path: Path) -> None:
    s = settings(tmp_path)
    app, db = make_app_and_db(s)
    with TestClient(app) as client:
        token = new_user_token(client)
        uuid = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "normal delete"},
            headers=auth(token),
        ).json()["uuid"]
        delete = client.delete(f"/owner/questions/{uuid}/delete", headers=auth(admin_token(s)))

    question_row = db.conn.execute(
        "SELECT deleted_at, deletion_source FROM question WHERE uuid = ?",
        (uuid,),
    ).fetchone()
    events = db.conn.execute("SELECT event_type FROM question_moderation_event WHERE uuid = ?", (uuid,)).fetchall()
    assert delete.status_code == 200
    assert question_row["deleted_at"] is not None
    assert question_row["deletion_source"] == "owner_manual"
    assert events == []


def test_moderation_status_defaults_validation_counts_and_location_options(tmp_path: Path) -> None:
    s = settings(tmp_path, geo_enabled=True, trusted_proxy_cidrs=["127.0.0.1/32"])
    app, db = make_app_and_db(s)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        normal_token = new_user_token(client)
        client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "normal"},
            headers={**auth(normal_token), "X-Real-IP": "8.8.8.8"},
        )
        blocked_token = new_user_token(client)
        blocked_uuid = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "review text"},
            headers={**auth(blocked_token), "X-Real-IP": "9.9.9.9"},
        ).json()["uuid"]
        insert_llm_blocked_state(db, blocked_uuid)
        db.insert_ip_geo({"ip": "8.8.8.8", "addr": "正常地区", "isp": "正常运营商", "provider": "ip2region", "looked_up_at": 1})
        db.insert_ip_geo({"ip": "9.9.9.9", "addr": "审核地区", "isp": "审核运营商", "provider": "ip2region", "looked_up_at": 1})
        owner_headers = auth(admin_token(s))
        default_normal = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=owner_headers,
        )
        blocked = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "moderation_status": "blocked", "day_limit": 1},
            headers=owner_headers,
        )
        invalid = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "moderation_status": "pending", "day_limit": 1},
            headers=owner_headers,
        )
        filtered_blocked = client.post(
            "/owner/questions",
            json={
                "owner": "owner",
                "type": "type",
                "moderation_status": "blocked",
                "day_limit": 1,
                "ip_addr": "审核地区",
            },
            headers=owner_headers,
        )
    assert default_normal.status_code == 200
    assert default_normal.json()["total"] == 1
    assert default_normal.json()["questions"][0]["text"] == "normal"
    assert default_normal.json()["moderation_counts"] == {"blocked": 1}
    assert {option["addr"] for option in default_normal.json()["location_options"]} == {"正常地区"}
    assert blocked.status_code == 200
    assert blocked.json()["total"] == 1
    assert blocked.json()["questions"][0]["text"] == ""
    assert blocked.json()["questions"][0]["raw_text_hidden"] is True
    assert {option["addr"] for option in blocked.json()["location_options"]} == {"审核地区"}
    assert filtered_blocked.json()["total"] == 1
    assert filtered_blocked.json()["moderation_counts"] == {"blocked": 1}
    assert invalid.status_code == 400
    assert "moderation_status" in invalid.json()["error"]


def test_visit_queue_flushes_on_shutdown(tmp_path: Path) -> None:
    s = settings(tmp_path)
    app, db = make_app_and_db(s)
    with TestClient(app) as client:
        token = new_user_token(client)
        submit = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "hello"},
            headers=auth(token),
        )
        uuid = submit.json()["uuid"]
        client.put(
            f"/owner/questions/{uuid}/answer",
            json={"uuid": uuid, "answer": "answer", "answered_by": "manual"},
            headers=auth(admin_token(s)),
        )
        read = client.get("/questions/question", headers=auth(token))
        assert read.status_code == 200
    row = db.conn.execute("SELECT visit_count FROM visit WHERE uuid = ?", (uuid,)).fetchone()
    assert row is not None
    assert row["visit_count"] == 1


def test_visit_queue_flushes_under_sustained_load(tmp_path: Path) -> None:
    class RecordingVisitRepo:
        def __init__(self) -> None:
            self.calls: list[tuple[str, int, int]] = []

        def upsert(self, uuid: str, visited_at: int, count: int = 1) -> None:
            self.calls.append((uuid, visited_at, count))

    async def run() -> None:
        s = settings(tmp_path)
        s.visit_flush_interval_seconds = 0.05
        repo = RecordingVisitRepo()
        service = VisitService(repo, SettingsProvider(settings=s))  # type: ignore[arg-type]
        task = asyncio.create_task(service.run())
        loop = asyncio.get_running_loop()
        started_at = loop.time()
        try:
            while loop.time() - started_at < 0.14:
                service.queue.put_nowait(("uuid", int(time())))
                await asyncio.sleep(0.01)
            assert repo.calls
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    asyncio.run(run())


def test_legacy_auth_and_sort_errors(tmp_path: Path) -> None:
    s = settings(tmp_path)
    with make_client(s) as client:
        missing = client.get("/questions/question")
        user_token = new_user_token(client)
        owner_as_user = client.post("/owner/questions", json={}, headers=auth(user_token))
        bad_sort = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "order_params": {"by": "question;drop", "reversed": True}},
            headers=auth(admin_token(s)),
        )
    assert missing.status_code == 403
    assert missing.json() == {"error": "无效token"}
    assert owner_as_user.status_code == 401
    assert owner_as_user.json() == {"error": "未授权访问"}
    assert bad_sort.status_code == 400
    assert "不支持的排序字段" in bad_sort.json()["error"]


def test_go_compatible_admin_magic_claim(tmp_path: Path) -> None:
    s = settings(tmp_path)
    with make_client(s) as client:
        resp = client.get("/owner", headers=auth(admin_token(s, "admin-session")))
    assert resp.status_code == 200
    assert resp.json() == {"owner": "admin-session"}


def test_owner_answer_body_uuid_cannot_shadow_url_uuid(tmp_path: Path) -> None:
    s = settings(tmp_path)
    with make_client(s) as client:
        first_token = new_user_token(client)
        first = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "first"},
            headers=auth(first_token),
        ).json()["uuid"]
        second_token = new_user_token(client)
        second = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "second"},
            headers=auth(second_token),
        ).json()["uuid"]
        mismatch = client.put(
            f"/owner/questions/{first}/answer",
            json={"uuid": second, "answer": "wrong target", "answered_by": "manual"},
            headers=auth(admin_token(s)),
        )
        first_read = client.get("/questions/question", headers=auth(first_token))
        second_read = client.get("/questions/question", headers=auth(second_token))
    assert mismatch.status_code == 400
    assert mismatch.json() == {"error": "投稿UUID不匹配"}
    assert first_read.json()["answer"] == ""
    assert second_read.json()["answer"] == ""


def test_phase2_trusted_proxy_header_and_spoof_rejection(tmp_path: Path) -> None:
    trusted = settings(tmp_path / "trusted", geo_enabled=True, trusted_proxy_cidrs=["127.0.0.1/32"])
    untrusted = settings(tmp_path / "untrusted", geo_enabled=True, trusted_proxy_cidrs=["127.0.0.1/32"])
    with make_client(trusted, client_addr=("127.0.0.1", 50000)) as client:
        token = new_user_token(client)
        client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "hello"},
            headers={**auth(token), "X-Real-IP": "8.8.8.8"},
        )
        listed = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=auth(admin_token(trusted)),
        ).json()["questions"][0]
    with make_client(untrusted, client_addr=("9.9.9.9", 50000)) as client:
        token = new_user_token(client)
        client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "hello"},
            headers={**auth(token), "X-Real-IP": "8.8.8.8"},
        )
        spoofed = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=auth(admin_token(untrusted)),
        ).json()["questions"][0]
    assert listed["ip"] == "8.8.8.8"
    assert listed["ip_addr"] == ""
    assert spoofed["ip"] == "9.9.9.9"


def test_phase2_forwarded_for_fallback_and_owner_detail_geo(tmp_path: Path) -> None:
    s = settings(tmp_path, geo_enabled=True, trusted_proxy_cidrs=["127.0.0.1/32"])
    app, db = make_app_and_db(s)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        token = new_user_token(client)
        submit = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "hello"},
            headers={**auth(token), "X-Forwarded-For": "10.20.30.40, 127.0.0.1"},
        )
        uuid = submit.json()["uuid"]
        db.insert_ip_geo(
            {
                "ip": "10.20.30.40",
                "province": "广东省",
                "city": "广州市",
                "region": "",
                "addr": "广东省广州市",
                "isp": "电信",
                "provider": "ip2region",
                "looked_up_at": 1,
            }
        )
        owner_detail = client.get(f"/owner/questions/{uuid}", headers=auth(admin_token(s)))
        asker_read = client.get("/questions/question", headers=auth(token))
    assert owner_detail.status_code == 200
    assert owner_detail.json()["ip"] == "10.20.30.40"
    assert owner_detail.json()["ip_addr"] == "广东省广州市"
    assert owner_detail.json()["ip_isp"] == "电信"
    assert "ip" not in asker_read.json()
    assert "ip_addr" not in asker_read.json()
    assert "ip_isp" not in asker_read.json()


def test_owner_location_filter_uses_cached_addr_and_dedupes_isp(tmp_path: Path) -> None:
    s = settings(tmp_path, geo_enabled=True, trusted_proxy_cidrs=["127.0.0.1/32"])
    app, db = make_app_and_db(s)
    with TestClient(app, client=("127.0.0.1", 50000)) as client:
        for ip, text in [
            ("8.8.8.8", "hangzhou one"),
            ("1.1.1.1", "hangzhou two"),
            ("9.9.9.9", "beijing"),
            ("127.0.0.1", "no geo data"),
        ]:
            token = new_user_token(client)
            submit = client.post(
                "/questions/submit",
                json={"owner": "owner", "type": "type", "text": text},
                headers={**auth(token), "X-Real-IP": ip},
            )
            assert submit.status_code == 200
        db.insert_ip_geo(
            {
                "ip": "8.8.8.8",
                "addr": "浙江省杭州市",
                "isp": "阿里",
                "provider": "ip2region",
                "looked_up_at": 1,
            }
        )
        db.insert_ip_geo(
            {
                "ip": "1.1.1.1",
                "addr": "浙江省杭州市",
                "isp": "电信",
                "provider": "ip2region",
                "looked_up_at": 1,
            }
        )
        db.insert_ip_geo(
            {
                "ip": "9.9.9.9",
                "addr": "北京市",
                "isp": "联通",
                "provider": "ip2region",
                "looked_up_at": 1,
            }
        )

        unfiltered = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=auth(admin_token(s)),
        ).json()
        filtered = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1, "ip_addr": "浙江省杭州市"},
            headers=auth(admin_token(s)),
        ).json()
        missing_filtered = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1, "ip_addr": LOCATION_NO_DATA_VALUE},
            headers=auth(admin_token(s)),
        ).json()

    hangzhou_option = next(option for option in unfiltered["location_options"] if option["addr"] == "浙江省杭州市")
    missing_option = next(option for option in unfiltered["location_options"] if option["addr"] == LOCATION_NO_DATA_VALUE)
    assert hangzhou_option["count"] == 2
    assert set(hangzhou_option["isps"]) == {"阿里", "电信"}
    assert "阿里" in hangzhou_option["label"]
    assert "电信" in hangzhou_option["label"]
    assert missing_option == {
        "addr": LOCATION_NO_DATA_VALUE,
        "isps": [],
        "label": LOCATION_NO_DATA_LABEL,
        "count": 1,
        "is_missing": True,
    }
    assert filtered["total"] == 2
    assert {question["text"] for question in filtered["questions"]} == {"hangzhou one", "hangzhou two"}
    assert missing_filtered["total"] == 1
    assert {question["text"] for question in missing_filtered["questions"]} == {"no geo data"}
    assert {option["addr"] for option in filtered["location_options"]} == {
        LOCATION_NO_DATA_VALUE,
        "浙江省杭州市",
        "北京市",
    }


def test_phase2_x_real_ip_precedes_forwarded_for(tmp_path: Path) -> None:
    s = settings(tmp_path, geo_enabled=True, trusted_proxy_cidrs=["127.0.0.1/32"])
    with make_client(s, client_addr=("127.0.0.1", 50000)) as client:
        token = new_user_token(client)
        client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "hello"},
            headers={**auth(token), "X-Real-IP": "10.0.0.1", "X-Forwarded-For": "10.0.0.2, 127.0.0.1"},
        )
        listed = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=auth(admin_token(s)),
        ).json()["questions"][0]
    assert listed["ip"] == "10.0.0.1"


class FakeRegionLookup:
    def __init__(self, raw_region: str | None):
        self.raw_region = raw_region
        self.calls = 0

    def __call__(self, ip: str, _: Settings) -> str | None:
        assert ip == "8.8.8.8"
        self.calls += 1
        return self.raw_region


def test_ip2region_lookup_cache(tmp_path: Path) -> None:
    import asyncio

    s = settings(tmp_path, geo_enabled=True)
    db = Database(s.db_path, geo_enabled=True)
    db.bootstrap()
    lookup = FakeRegionLookup("中国|广东省|深圳市|电信|CN")
    asyncio.run(lookup_and_store(db, s, "8.8.8.8", region_lookup=lookup))
    asyncio.run(lookup_and_store(db, s, "8.8.8.8", region_lookup=lookup))
    row = db.get_ip_geo("8.8.8.8")
    assert row is not None
    assert lookup.calls == 1
    assert row["provider"] == "ip2region"
    assert row["country"] == "中国"
    assert row["province"] == "广东省"
    assert row["city"] == "深圳市"
    assert row["isp"] == "电信"
    assert row["country_code"] == "CN"
    assert row["raw_region"] == "中国|广东省|深圳市|电信|CN"
    assert row["addr"] == "广东省深圳市"


def test_ip2region_default_cache_policy_is_vector_index(tmp_path: Path) -> None:
    s = settings(tmp_path)
    assert s.ip2region_cache_policy == "vectorIndex"
    config_path = tmp_path / "config.yaml"
    write_config(config_path, config_payload(tmp_path))
    from aqbox.config import load_settings

    assert load_settings(str(config_path)).ip2region_cache_policy == "vectorIndex"


def test_ip2region_invalid_lookup_fails_open(tmp_path: Path) -> None:
    import asyncio

    s = settings(tmp_path, geo_enabled=True)
    db = Database(s.db_path, geo_enabled=True)
    db.bootstrap()
    asyncio.run(lookup_and_store(db, s, "8.8.8.8", region_lookup=FakeRegionLookup("中国|广东省")))
    assert db.get_ip_geo("8.8.8.8") is None


def test_ip2region_missing_xdb_fails_open(tmp_path: Path) -> None:
    import asyncio

    s = settings(tmp_path, geo_enabled=True)
    s.ip2region_ipv4_xdb_path = str(tmp_path / "missing.xdb")
    db = Database(s.db_path, geo_enabled=True)
    db.bootstrap()
    asyncio.run(lookup_and_store(db, s, "8.8.8.8"))
    assert db.get_ip_geo("8.8.8.8") is None


def test_ip2region_parser_omits_zero_parts_and_isp_from_addr() -> None:
    cn = parse_region("中国|广东省|深圳市|电信|CN")
    overseas = parse_region("United States|California|San Jose|xTom|US")
    partial = parse_region("United States|0|0|Google|US")
    assert cn is not None
    assert overseas is not None
    assert partial is not None
    assert cn.addr == "广东省深圳市"
    assert overseas.addr == "United States California San Jose"
    assert partial.addr == "United States"


def test_ip2region_migration_drops_stale_wip_cache_rows(tmp_path: Path) -> None:
    s = settings(tmp_path)
    db = Database(s.db_path)
    db.bootstrap()
    db.conn.execute(
        "INSERT INTO ip_geo (ip, province, city, region, addr, looked_up_at) VALUES (?, ?, ?, ?, ?, ?)",
        ("8.8.8.8", "广东省", "广州市", "", "广东省广州市 电信", 1),
    )
    db.conn.commit()
    db.migrate_geo()
    db.conn.commit()
    assert db.get_ip_geo("8.8.8.8") is None


def test_ip2region_migration_keeps_current_provider_rows(tmp_path: Path) -> None:
    s = settings(tmp_path, geo_enabled=True)
    db = Database(s.db_path, geo_enabled=True)
    db.bootstrap()
    db.insert_ip_geo(
        {
            "ip": "8.8.8.8",
            "country": "中国",
            "province": "广东省",
            "city": "深圳市",
            "region": "",
            "addr": "广东省深圳市",
            "isp": "电信",
            "country_code": "CN",
            "provider": "ip2region",
            "raw_region": "中国|广东省|深圳市|电信|CN",
            "looked_up_at": 1,
        }
    )
    db.migrate_geo()
    db.migrate_geo()
    db.conn.commit()
    row = db.get_ip_geo("8.8.8.8")
    assert row is not None
    assert row["provider"] == "ip2region"
    assert row["addr"] == "广东省深圳市"


def test_profiles_and_keywords_hot_reload_without_restart(tmp_path: Path) -> None:
    payload = config_payload(tmp_path)
    client, config_path = config_client(tmp_path, payload)
    with client:
        original = client.get("/profiles").json()
        assert original["metadata"]["introductions"] == ["hello"]
        token_before = new_user_token(client)
        accepted = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "newblock text"},
            headers=auth(token_before),
        )
        assert accepted.status_code == 200

        payload["metadata"]["introductions"] = ["reloaded"]
        payload["filtered_keywords"] = ["newblock"]
        payload["owner_profiles"]["owner"]["question_types"]["type"]["rune_limit"] = 8
        write_config(config_path, payload)

        reloaded = client.get("/profiles").json()
        assert reloaded["metadata"]["introductions"] == ["reloaded"]
        assert reloaded["owner_profiles"]["owner"]["question_types"]["type"]["rune_limit"] == 8
        token_after = new_user_token(client)
        submit = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "newblock"},
            headers=auth(token_after),
        )
        owner_list = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=auth(admin_token(settings(tmp_path))),
        )
    assert submit.status_code == 200
    assert owner_list.json()["total"] == 1


def test_llm_moderation_config_requires_global_and_type_enablement(tmp_path: Path, monkeypatch) -> None:
    config_path = tmp_path / "config.yaml"
    payload = config_payload(
        tmp_path,
        llm_filter={
            "enabled": True,
            "api_key_env": "AQBOX_TEST_LLM_KEY",
            "api_key": "config-fallback-secret",
            "boxes": {
                "owner": {
                    "question_types": {
                        "type": {"enabled": True, "policy_prompt": ""},
                        "disabled": {"enabled": False, "policy_prompt": "unused"},
                    }
                }
            },
        },
    )
    write_config(config_path, payload)
    monkeypatch.setenv("AQBOX_TEST_LLM_KEY", "env-secret")

    loaded = load_settings(str(config_path))
    enabled_policy = loaded.llm_moderation.policy_for("owner", "type")
    assert enabled_policy is not None
    assert enabled_policy.policy_prompt == ""
    assert enabled_policy.api_key() == "env-secret"
    assert loaded.llm_moderation.provider == "deepseek"
    assert loaded.llm_moderation.base_url == "https://api.deepseek.com"
    assert loaded.llm_moderation.model == "deepseek-v4-flash"
    assert loaded.llm_moderation.high_confidence_reject_threshold == 0.85
    assert loaded.llm_moderation.review_all_model_rejects is True
    assert loaded.llm_moderation.max_attempts == 2
    assert loaded.llm_moderation.timeout_seconds == 10.0
    assert loaded.llm_moderation.max_tokens == 256
    assert loaded.llm_moderation.initial_backoff_seconds == 1.0
    assert loaded.llm_moderation.raw_retention_enabled is False
    assert loaded.llm_moderation.raw_retention_seconds == 0
    assert enabled_policy.timeout_seconds == 10.0
    assert enabled_policy.max_tokens == 256
    assert enabled_policy.initial_backoff_seconds == 1.0

    monkeypatch.delenv("AQBOX_TEST_LLM_KEY")
    assert enabled_policy.api_key() == "config-fallback-secret"
    assert loaded.llm_moderation.policy_for("owner", "disabled") is None
    assert loaded.llm_moderation.policy_for("owner", "missing") is None

    payload["llm_filter"]["enabled"] = False
    write_config(config_path, payload)
    globally_disabled = load_settings(str(config_path))
    assert globally_disabled.llm_moderation.policy_for("owner", "type") is None


def test_direct_settings_llm_filter_derives_typed_config() -> None:
    direct = Settings(
        llm_filter={
            "enabled": True,
            "boxes": {"owner": {"question_types": {"type": {"enabled": True, "policy_prompt": "direct"}}}},
        }
    )

    policy = llm_policy_for(direct, "owner", "type")
    assert policy is not None
    assert policy.policy_prompt == "direct"


def test_llm_policy_uses_config_api_key_fallback_and_redacts_repr(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    payload = config_payload(
        tmp_path,
        llm_filter={
            "enabled": True,
            "api_key": "config-fallback-secret",
            "boxes": {"owner": {"question_types": {"type": {"enabled": True, "policy_prompt": "policy"}}}},
        },
    )
    write_config(config_path, payload)

    policy = load_settings(str(config_path)).llm_moderation.policy_for("owner", "type")
    assert policy is not None
    assert policy.api_key() == "config-fallback-secret"
    assert policy.api_key_value == "config-fallback-secret"
    assert "config-fallback-secret" not in repr(policy)


def test_llm_config_and_settings_repr_redact_raw_api_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    payload = config_payload(
        tmp_path,
        llm_filter={
            "enabled": True,
            "api_key": "config-fallback-secret",
            "boxes": {"owner": {"question_types": {"type": {"enabled": True, "policy_prompt": "policy"}}}},
        },
    )
    write_config(config_path, payload)

    loaded = load_settings(str(config_path))
    assert loaded.llm_filter["api_key"] == "config-fallback-secret"
    assert loaded.llm_moderation.raw["api_key"] == "config-fallback-secret"
    assert "config-fallback-secret" not in repr(loaded.llm_moderation)
    assert "config-fallback-secret" not in repr(loaded)

    direct = Settings(llm_filter=payload["llm_filter"])
    assert direct.llm_filter["api_key"] == "config-fallback-secret"
    assert direct.llm_moderation.raw["api_key"] == "config-fallback-secret"
    assert "config-fallback-secret" not in repr(direct)


def test_llm_threshold_and_boolean_validation_rejects_invalid_values(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    base_filter = {
        "enabled": True,
        "boxes": {"owner": {"question_types": {"type": {"enabled": True, "policy_prompt": "policy"}}}},
    }
    for invalid_threshold in (-0.01, 1.01, float("nan")):
        payload = config_payload(
            tmp_path,
            llm_filter={**base_filter, "high_confidence_reject_threshold": invalid_threshold},
        )
        write_config(config_path, payload)
        with pytest.raises(ValueError, match="high_confidence_reject_threshold"):
            load_settings(str(config_path))

    payload = config_payload(tmp_path, llm_filter={**base_filter, "enabled": "ture"})
    write_config(config_path, payload)
    with pytest.raises(ValueError, match=r"llm_filter\.enabled"):
        load_settings(str(config_path))


def test_invalid_llm_threshold_hot_reload_keeps_last_good_config(tmp_path: Path) -> None:
    payload = config_payload(
        tmp_path,
        llm_filter={
            "enabled": True,
            "high_confidence_reject_threshold": 0.8,
            "boxes": {"owner": {"question_types": {"type": {"enabled": True, "policy_prompt": "policy"}}}},
        },
    )
    client, config_path = config_client(tmp_path, payload)
    with client:
        old_admin = admin_token(settings(tmp_path))
        assert client.app.state.settings_provider.current().llm_moderation.high_confidence_reject_threshold == 0.8

        payload["llm_filter"]["high_confidence_reject_threshold"] = 1.2
        write_config(config_path, payload)
        cfg = client.get("/ops/config", headers=auth(old_admin))
        current = client.app.state.settings_provider.current()

    assert cfg.status_code == 200
    assert cfg.json()["last_reload_error"]
    assert "high_confidence_reject_threshold" in cfg.json()["last_reload_error"]
    assert current.llm_moderation.high_confidence_reject_threshold == 0.8


def test_llm_moderation_config_parses_provider_and_retention_overrides(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    payload = config_payload(
        tmp_path,
        llm_filter={
            "enabled": True,
            "timeout_seconds": 3.5,
            "max_tokens": 96,
            "initial_backoff_seconds": 0.75,
            "raw_retention_enabled": True,
            "raw_retention_seconds": 172800,
            "boxes": {"owner": {"question_types": {"type": {"enabled": True, "policy_prompt": "policy"}}}},
        },
    )
    write_config(config_path, payload)

    loaded = load_settings(str(config_path))
    policy = loaded.llm_moderation.policy_for("owner", "type")
    assert policy is not None
    assert loaded.llm_moderation.timeout_seconds == 3.5
    assert loaded.llm_moderation.max_tokens == 96
    assert loaded.llm_moderation.initial_backoff_seconds == 0.75
    assert loaded.llm_moderation.raw_retention_enabled is True
    assert loaded.llm_moderation.raw_retention_seconds == 172800
    assert policy.timeout_seconds == 3.5
    assert policy.max_tokens == 96
    assert policy.initial_backoff_seconds == 0.75


def test_llm_policy_helper_uses_typed_enablement_semantics(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    payload = config_payload(
        tmp_path,
        llm_filter={
            "enabled": True,
            "owners": {
                "owner": {
                    "question_types": {
                        "type": {"enabled": True, "prompt": ""},
                        "legacy_prompt_only": {"prompt": "do not infer enablement"},
                    }
                }
            },
        },
    )
    write_config(config_path, payload)

    enabled_empty_policy = llm_policy_for(load_settings(str(config_path)), "owner", "type")
    assert enabled_empty_policy is not None
    assert enabled_empty_policy.policy_prompt == ""
    assert llm_policy_for(load_settings(str(config_path)), "owner", "legacy_prompt_only") is None

    payload["llm_filter"]["enabled"] = False
    write_config(config_path, payload)
    assert llm_policy_for(load_settings(str(config_path)), "owner", "type") is None


def test_llm_filter_hot_reloads_without_restart_required(tmp_path: Path) -> None:
    payload = config_payload(tmp_path)
    client, config_path = config_client(tmp_path, payload)
    with client:
        old_admin = admin_token(settings(tmp_path))
        assert client.app.state.settings_provider.current().llm_moderation.policy_for("owner", "type") is None

        payload["llm_filter"] = {
            "enabled": True,
            "boxes": {"owner": {"question_types": {"type": {"enabled": True, "policy_prompt": "local policy"}}}},
        }
        write_config(config_path, payload)

        cfg = client.get("/ops/config", headers=auth(old_admin))
        current = client.app.state.settings_provider.current()

    assert cfg.status_code == 200
    assert "llm_filter" not in cfg.json()["restart_required"]
    policy = current.llm_moderation.policy_for("owner", "type")
    assert policy is not None
    assert policy.policy_prompt == "local policy"


def test_ops_config_redacts_llm_api_keys_from_env_and_config(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AQBOX_TEST_LLM_KEY", "env-secret-value")
    payload = config_payload(
        tmp_path,
        llm_filter={
            "enabled": True,
            "api_key_env": "AQBOX_TEST_LLM_KEY",
            "api_key": "config-fallback-secret",
            "boxes": {"owner": {"question_types": {"type": {"enabled": True, "policy_prompt": "policy text"}}}},
        },
    )
    client, _ = config_client(tmp_path, payload)
    with client:
        cfg = client.get("/ops/config", headers=auth(admin_token(settings(tmp_path))))

    assert cfg.status_code == 200
    assert cfg.json()["llm_filter"]["api_key_configured"] is True
    assert cfg.json()["llm_filter"]["timeout_seconds"] == 10.0
    assert cfg.json()["llm_filter"]["max_tokens"] == 256
    assert cfg.json()["llm_filter"]["initial_backoff_seconds"] == 1.0
    assert cfg.json()["llm_filter"]["raw_retention_enabled"] is False
    assert cfg.json()["llm_filter"]["raw_retention_seconds"] == 0
    assert "env-secret-value" not in cfg.text
    assert "config-fallback-secret" not in cfg.text


def test_invalid_config_keeps_last_good_and_marks_unhealthy(tmp_path: Path) -> None:
    payload = config_payload(tmp_path)
    client, config_path = config_client(tmp_path, payload)
    with client:
        assert client.get("/ops/health").json()["ok"] is True
        config_path.write_text("owner_profiles: [", encoding="utf-8")
        profiles = client.get("/profiles")
        health = client.get("/ops/health")
        cfg = client.get("/ops/config", headers=auth(admin_token(settings(tmp_path))))
    assert profiles.status_code == 200
    assert profiles.json()["metadata"]["introductions"] == ["hello"]
    assert health.status_code == 503
    assert health.json()["config"] is False
    assert cfg.status_code == 200
    assert cfg.json()["last_reload_error"]


def test_malformed_question_type_window_returns_legacy_error(tmp_path: Path) -> None:
    payload = config_payload(tmp_path)
    payload["owner_profiles"]["owner"]["question_types"]["type"]["start_time"] = "not a timestamp"
    client, _ = config_client(tmp_path, payload)
    with client:
        token = new_user_token(client)
        submit = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "hello"},
            headers=auth(token),
        )
    assert submit.status_code == 500
    assert submit.json()["error"].startswith("投稿类型时间窗配置无效")


def test_restart_required_config_fields_do_not_hot_swap(tmp_path: Path) -> None:
    payload = config_payload(tmp_path)
    client, config_path = config_client(tmp_path, payload)
    original_settings = settings(tmp_path)
    with client:
        old_admin = admin_token(original_settings)
        assert client.get("/owner", headers=auth(old_admin)).status_code == 200

        payload["jwt_secret_key"] = "new-secret"
        payload["magic_spell"] = "new-spell"
        payload["db_path"] = str(tmp_path / "other.sqlite3")
        payload["host"] = "0.0.0.0"
        payload["port"] = 1234
        payload["ip2region_ipv4_xdb_path"] = str(tmp_path / "ip2region_v4.xdb")
        payload["ip2region_ipv6_xdb_path"] = str(tmp_path / "ip2region_v6.xdb")
        payload["ip2region_cache_policy"] = "file"
        write_config(config_path, payload)

        cfg = client.get("/ops/config", headers=auth(old_admin))
        new_claim_settings = settings(tmp_path)
        new_claim_settings.jwt_secret_key = "new-secret"
        new_claim_settings.magic_spell = "new-spell"
        new_admin = admin_token(new_claim_settings)
        new_auth = client.get("/owner", headers=auth(new_admin))
    assert cfg.status_code == 200
    assert set(cfg.json()["restart_required"]) >= {
        "jwt_secret_key",
        "magic_spell",
        "db_path",
        "host",
        "port",
        "ip2region_ipv4_xdb_path",
        "ip2region_ipv6_xdb_path",
        "ip2region_cache_policy",
    }
    assert '"secret"' not in cfg.text
    assert "new-secret" not in cfg.text
    assert new_auth.status_code == 401


def test_trusted_proxy_cidrs_hot_reload(tmp_path: Path) -> None:
    payload = config_payload(tmp_path, geo_enabled=True, trusted_proxy_cidrs=["10.0.0.0/8"])
    client, config_path = config_client(tmp_path, payload, client_addr=("127.0.0.1", 50000))
    s = settings(tmp_path, geo_enabled=True)
    with client:
        token = new_user_token(client)
        client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "first"},
            headers={**auth(token), "X-Real-IP": "8.8.8.8"},
        )
        first = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=auth(admin_token(s)),
        ).json()["questions"][0]

        payload["trusted_proxy_cidrs"] = ["127.0.0.1/32"]
        write_config(config_path, payload)
        token = new_user_token(client)
        client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "second"},
            headers={**auth(token), "X-Real-IP": "8.8.8.8"},
        )
        second = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=auth(admin_token(s)),
        ).json()["questions"]
    assert first["ip"] == "127.0.0.1"
    second_row = next(question for question in second if question["text"] == "second")
    assert second_row["ip"] == "8.8.8.8"


def test_geo_enabled_hot_reload_updates_database_state(tmp_path: Path) -> None:
    payload = config_payload(tmp_path, geo_enabled=False, trusted_proxy_cidrs=["127.0.0.1/32"])
    client, config_path = config_client(tmp_path, payload, client_addr=("127.0.0.1", 50000))
    s = settings(tmp_path, geo_enabled=True)
    with client:
        token = new_user_token(client)
        first_submit = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "first"},
            headers={**auth(token), "X-Real-IP": "8.8.8.8"},
        )
        payload["geo_enabled"] = True
        write_config(config_path, payload)
        token = new_user_token(client)
        second_submit = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "second"},
            headers={**auth(token), "X-Real-IP": "8.8.8.8"},
        )
        second_list = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=auth(admin_token(s)),
        ).json()["questions"]
        payload["geo_enabled"] = False
        write_config(config_path, payload)
        token = new_user_token(client)
        third_submit = client.post(
            "/questions/submit",
            json={"owner": "owner", "type": "type", "text": "third"},
            headers={**auth(token), "X-Real-IP": "8.8.8.8"},
        )
        third_list = client.post(
            "/owner/questions",
            json={"owner": "owner", "type": "type", "day_limit": 1},
            headers=auth(admin_token(settings(tmp_path))),
        )
    assert first_submit.status_code == 200
    assert second_submit.status_code == 200
    second_row = next(question for question in second_list if question["text"] == "second")
    assert second_row["ip"] == "8.8.8.8"
    assert third_submit.status_code == 200
    assert "ip" not in third_list.json()["questions"][0]


def test_owner_questions_rate_limit_uses_legacy_error(tmp_path: Path) -> None:
    client, _ = config_client(tmp_path)
    with client:
        token = admin_token(settings(tmp_path))
        statuses = [
            client.post(
                "/owner/questions",
                json={"owner": "owner", "type": "type", "day_limit": 1},
                headers=auth(token),
            )
            for _ in range(31)
        ]
    assert statuses[-1].status_code == 429
    assert statuses[-1].json() == {"error": "请求过于频繁"}


def test_rate_limiter_keeps_keys_independent_and_bounded() -> None:
    limiter = TokenBucketRateLimiter(rate_per_second=1.0, burst=1, max_buckets=2)
    assert limiter.allow("owner-a") is True
    assert limiter.allow("owner-a") is False
    assert limiter.allow("owner-b") is True
    assert limiter.allow("owner-c") is True
    assert len(limiter.buckets) <= 2


def test_geo_service_suppresses_duplicate_in_flight_ip(tmp_path: Path) -> None:
    import asyncio

    async def run() -> None:
        s = settings(tmp_path, geo_enabled=True)
        db = Database(s.db_path, geo_enabled=True)
        db.bootstrap()
        service = GeoService()
        repo = type("Repo", (), {"db": db})()
        service.schedule_lookup(repo, s, "8.8.8.8")  # type: ignore[arg-type]
        service.schedule_lookup(repo, s, "8.8.8.8")  # type: ignore[arg-type]
        assert len(service.background_tasks) == 1
        for task in list(service.background_tasks):
            task.cancel()

    asyncio.run(run())


def test_ops_config_requires_admin_and_health_is_minimal(tmp_path: Path) -> None:
    client, _ = config_client(tmp_path)
    with client:
        health = client.get("/ops/health")
        unauth = client.get("/ops/config")
        user_token = new_user_token(client)
        user = client.get("/ops/config", headers=auth(user_token))
        owner = client.get("/ops/config", headers=auth(admin_token(settings(tmp_path))))
    assert health.status_code == 200
    assert health.json() == {"ok": True, "db": True, "config": True, "visit_worker": True}
    assert unauth.status_code == 403
    assert user.status_code == 401
    assert owner.status_code == 200
    assert "jwt_secret_key" not in owner.text
    assert "magic_spell" not in owner.text


def test_request_logging_redacts_query_tokens(tmp_path: Path, caplog) -> None:
    client, _ = config_client(tmp_path)
    with client:
        caplog.set_level("INFO", logger="aqbox.request")
        client.get("/profiles?token=super-secret-token&page=2")
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "super-secret-token" not in messages
    assert "/profiles?token=<redacted>&page=2" in messages
