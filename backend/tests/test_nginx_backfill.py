from __future__ import annotations

from pathlib import Path

from aqbox.config import Settings
from aqbox.db import Database
from aqbox.nginx_backfill import apply_backfill, collect_submit_events, plan_backfill


def sample_submit_lines() -> str:
    return "\n".join(
        [
            '223.64.168.134 - - [17/May/2026:14:23:32 +0800] "POST /api/questions/submit HTTP/2.0" 200 96 '
            '"https://mht.meumy.club/" "Mozilla/5.0 sample" "-"',
            '223.64.168.134 - - [17/May/2026:14:23:32 +0800] "GET /api/questions/question HTTP/2.0" 200 493 '
            '"https://mht.meumy.club/" "Mozilla/5.0 sample" "-"',
        ]
    )


def test_collect_submit_events_marks_followup_get(tmp_path: Path) -> None:
    log = tmp_path / "access.log"
    log.write_text(sample_submit_lines(), encoding="utf-8")

    events, report = collect_submit_events([str(log)])

    assert report.total_lines == 2
    assert report.submit_events == 1
    assert report.with_followup_get == 1
    assert len(events) == 1
    assert events[0].ip == "223.64.168.134"
    assert events[0].has_followup_get is True


def test_plan_and_apply_backfill_uses_unique_timestamp_match(tmp_path: Path) -> None:
    log = tmp_path / "access.log"
    log.write_text(sample_submit_lines(), encoding="utf-8")
    events, _ = collect_submit_events([str(log)])
    db = Database(str(tmp_path / "aqbox.sqlite3"), geo_enabled=True)
    db.bootstrap()
    assert db.insert_question(
        {
            "uuid": "question-1",
            "owner": "owner",
            "type": "type",
            "text": "hello",
            "asked_at": events[0].happened_at,
        }
    )

    matches, report = plan_backfill(db, events)
    apply_report = apply_backfill(
        db,
        Settings(geo_enabled=True),
        matches,
        region_lookup=lambda ip, _: "中国|浙江省|杭州市|阿里|CN" if ip == "223.64.168.134" else None,
    )

    row = db.conn.execute("SELECT ip FROM question WHERE uuid = 'question-1'").fetchone()
    geo = db.get_ip_geo("223.64.168.134")
    assert report.matched == 1
    assert matches[0].has_followup_get is True
    assert apply_report.applied == 1
    assert apply_report.geo_inserted == 1
    assert row["ip"] == "223.64.168.134"
    assert geo is not None
    assert geo["addr"] == "浙江省杭州市"
    assert geo["isp"] == "阿里"


def test_plan_backfill_skips_ambiguous_timestamp_cluster(tmp_path: Path) -> None:
    log = tmp_path / "access.log"
    log.write_text(sample_submit_lines(), encoding="utf-8")
    events, _ = collect_submit_events([str(log)])
    db = Database(str(tmp_path / "aqbox.sqlite3"), geo_enabled=True)
    db.bootstrap()
    for uuid in ["question-1", "question-2"]:
        assert db.insert_question(
            {
                "uuid": uuid,
                "owner": "owner",
                "type": "type",
                "text": uuid,
                "asked_at": events[0].happened_at,
            }
        )

    matches, report = plan_backfill(db, events)

    assert matches == []
    assert report.ambiguous == 1
