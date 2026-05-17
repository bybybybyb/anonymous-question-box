from __future__ import annotations

from pathlib import Path
from time import time

import jwt
import yaml
from fastapi.testclient import TestClient

from aqbox.app import create_app
from aqbox.config import Settings
from aqbox.db import Database
from aqbox.geo import lookup_and_store, parse_region
from aqbox.services import GeoService


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

    hangzhou_option = next(option for option in unfiltered["location_options"] if option["addr"] == "浙江省杭州市")
    assert hangzhou_option["count"] == 2
    assert set(hangzhou_option["isps"]) == {"阿里", "电信"}
    assert "阿里" in hangzhou_option["label"]
    assert "电信" in hangzhou_option["label"]
    assert filtered["total"] == 2
    assert {question["text"] for question in filtered["questions"]} == {"hangzhou one", "hangzhou two"}
    assert {option["addr"] for option in filtered["location_options"]} == {"浙江省杭州市", "北京市"}


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
        """
        CREATE TABLE ip_geo (
          ip TEXT PRIMARY KEY,
          province TEXT NOT NULL DEFAULT '',
          city TEXT NOT NULL DEFAULT '',
          region TEXT NOT NULL DEFAULT '',
          addr TEXT NOT NULL DEFAULT '',
          looked_up_at INTEGER NOT NULL
        )
        """
    )
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
        ).json()["questions"][0]
    assert first["ip"] == "127.0.0.1"
    assert second["ip"] == "8.8.8.8"


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
        client.get("/profiles?token=super-secret-token")
    messages = "\n".join(record.getMessage() for record in caplog.records)
    assert "super-secret-token" not in messages
    assert "/profiles?<redacted>" in messages
