from __future__ import annotations

from pathlib import Path
from time import time

import jwt
from fastapi.testclient import TestClient

from aqbox.app import create_app
from aqbox.auth import generate_token
from aqbox.config import Settings
from aqbox.db import Database
from aqbox.geo import lookup_and_store


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


def test_profiles_force_support_image_false(tmp_path: Path) -> None:
    s = settings(tmp_path)
    with make_client(s) as client:
        resp = client.get("/profiles")
    assert resp.status_code == 200
    qtype = resp.json()["owner_profiles"]["owner"]["question_types"]["type"]
    assert qtype["support_image"] is False


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


def test_keyword_soft_delete_stays_stealth_and_asker_can_read(tmp_path: Path) -> None:
    s = settings(tmp_path)
    with make_client(s) as client:
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
        owner_detail = client.get(f"/owner/questions/{submit.json()['uuid']}", headers=auth(admin_token(s)))
    assert submit.status_code == 200
    assert asker_read.status_code == 200
    assert asker_read.json()["text"] == "blocked text"
    assert asker_read.json()["images"] == []
    assert "ip" not in asker_read.json()
    assert owner_list.status_code == 200
    assert owner_list.json()["total"] == 0
    assert owner_detail.status_code == 404


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


class FakeResponse:
    content = '{"pro":"广东省","city":"广州市","region":"","addr":"广东省广州市 电信"}'.encode("gbk")


class FakeHTTPClient:
    async def get(self, url: str) -> FakeResponse:
        assert "whois.pconline.com.cn" in url
        return FakeResponse()


def test_pconline_gbk_lookup_cache(tmp_path: Path) -> None:
    import asyncio

    s = settings(tmp_path, geo_enabled=True)
    db = Database(s.db_path, geo_enabled=True)
    db.bootstrap()
    asyncio.run(lookup_and_store(db, s, "8.8.8.8", client=FakeHTTPClient()))  # type: ignore[arg-type]
    row = db.get_ip_geo("8.8.8.8")
    assert row is not None
    assert row["province"] == "广东省"
    assert row["city"] == "广州市"
    assert row["addr"] == "广东省广州市 电信"
