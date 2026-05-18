from __future__ import annotations

import sqlite3
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .timeutil import now_epoch, rfc3339_from_epoch

LOCATION_NO_DATA_VALUE = "__aqbox_no_location__"
LOCATION_NO_DATA_LABEL = "无地区信息"

SCHEMA_MIGRATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_migrations (
  version TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  applied_at INTEGER NOT NULL
);
"""

PHASE1_SCHEMA = """
CREATE TABLE IF NOT EXISTS question (
  id INTEGER PRIMARY KEY,
  uuid TEXT NOT NULL,
  owner TEXT NOT NULL,
  question_type TEXT NOT NULL,
  question TEXT NOT NULL,
  asked_at INTEGER NOT NULL,
  word_count INTEGER NOT NULL,
  answer TEXT,
  answered_at INTEGER,
  answered_by TEXT,
  deleted_at INTEGER,
  marked_at INTEGER
);
CREATE TABLE IF NOT EXISTS visit (
  id INTEGER PRIMARY KEY,
  uuid TEXT NOT NULL,
  last_visited_at INTEGER NOT NULL,
  visit_count INTEGER NOT NULL,
  FOREIGN KEY (uuid) REFERENCES question(uuid)
);
CREATE TABLE IF NOT EXISTS image (
  id INTEGER PRIMARY KEY,
  image_order INTEGER NOT NULL,
  filename TEXT NOT NULL,
  uuid TEXT NOT NULL,
  key TEXT NOT NULL,
  FOREIGN KEY (uuid) REFERENCES question(uuid)
);
CREATE UNIQUE INDEX IF NOT EXISTS uk_question_uuid ON question (uuid);
CREATE INDEX IF NOT EXISTS idx_owner_question_type_asked_at ON question (owner, question_type, asked_at);
CREATE UNIQUE INDEX IF NOT EXISTS uk_visit_uuid ON visit (uuid);
CREATE INDEX IF NOT EXISTS idx_image_uuid ON image (uuid);
"""


PHASE3_SCHEMA = """
CREATE TABLE IF NOT EXISTS question_moderation_audit (
  id INTEGER PRIMARY KEY,
  uuid TEXT NOT NULL,
  provider TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  prompt_version TEXT NOT NULL DEFAULT '',
  decision_json TEXT NOT NULL DEFAULT '',
  raw_prompt TEXT,
  raw_request TEXT,
  raw_response TEXT,
  latency_ms INTEGER,
  error_class TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  purge_after INTEGER,
  purged_at INTEGER,
  FOREIGN KEY (uuid) REFERENCES question(uuid)
);
CREATE INDEX IF NOT EXISTS idx_question_moderation_audit_uuid ON question_moderation_audit(uuid);
CREATE INDEX IF NOT EXISTS idx_question_moderation_audit_purge_after ON question_moderation_audit(purge_after);
"""


MODERATION_STATE_EVENTS_SCHEMA = """
CREATE TABLE IF NOT EXISTS question_moderation_state (
  uuid TEXT PRIMARY KEY,
  status TEXT NOT NULL CHECK (status IN ('pending', 'blocked', 'approved')),
  source TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL DEFAULT '',
  category TEXT,
  created_at INTEGER NOT NULL,
  updated_at INTEGER NOT NULL,
  FOREIGN KEY (uuid) REFERENCES question(uuid)
);
CREATE INDEX IF NOT EXISTS idx_question_moderation_state_status ON question_moderation_state(status);
CREATE TABLE IF NOT EXISTS question_moderation_event (
  id INTEGER PRIMARY KEY,
  uuid TEXT NOT NULL,
  event_type TEXT NOT NULL,
  status TEXT NOT NULL,
  source TEXT NOT NULL DEFAULT '',
  reason TEXT NOT NULL DEFAULT '',
  category TEXT,
  actor TEXT NOT NULL DEFAULT '',
  provider TEXT NOT NULL DEFAULT '',
  model TEXT NOT NULL DEFAULT '',
  prompt_version TEXT NOT NULL DEFAULT '',
  decision_json TEXT NOT NULL DEFAULT '',
  raw_prompt TEXT,
  raw_request TEXT,
  raw_response TEXT,
  latency_ms INTEGER,
  error_class TEXT NOT NULL DEFAULT '',
  created_at INTEGER NOT NULL,
  purge_after INTEGER,
  purged_at INTEGER,
  FOREIGN KEY (uuid) REFERENCES question(uuid)
);
CREATE INDEX IF NOT EXISTS idx_question_moderation_event_uuid ON question_moderation_event(uuid);
CREATE INDEX IF NOT EXISTS idx_question_moderation_event_purge_after ON question_moderation_event(purge_after);
"""


class Database:
    """SQLite boundary for schema migration plus the repository-facing SQL contract."""

    def __init__(self, path: str, *, geo_enabled: bool = False, moderation_schema: bool = False):
        self.path = path
        self.geo_enabled = geo_enabled
        self.moderation_schema = moderation_schema
        self.lock = threading.RLock()
        if path not in {":memory:", ""}:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA busy_timeout=5000")
        if path not in {":memory:", ""}:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")

    def bootstrap(self) -> None:
        """Apply all known idempotent migrations and record versions in schema_migrations."""
        with self.lock:
            self.conn.executescript(SCHEMA_MIGRATIONS_SCHEMA)
            self._run_migrations()
            self.conn.commit()

    def _run_migrations(self) -> None:
        """Run unapplied migrations in order; migration bodies stay idempotent for restores."""
        applied = {row["version"] for row in self.conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()}
        for version, name, migration in self._migrations():
            if version in applied:
                continue
            migration()
            self.conn.execute(
                "INSERT INTO schema_migrations (version, name, applied_at) VALUES (?, ?, ?)",
                (version, name, now_epoch()),
            )

    def _migrations(self) -> tuple[tuple[str, str, Callable[[], None]], ...]:
        """Central migration registry for the lightweight in-process runner."""
        return (
            ("0001_phase1_core", "Phase 1 core question, visit, and image tables", self._apply_phase1_schema),
            ("0002_ip2region_geo", "Offline ip2region geolocation schema", self.migrate_geo),
            ("0003_moderation_scaffold", "Moderation metadata and audit scaffold", self.migrate_moderation),
            ("0004_moderation_state_events", "Moderation state projection and event history", self.migrate_moderation_state_events),
        )

    def applied_migrations(self) -> list[str]:
        with self.lock:
            self.conn.executescript(SCHEMA_MIGRATIONS_SCHEMA)
            rows = self.conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
        return [str(row["version"]) for row in rows]

    def _apply_phase1_schema(self) -> None:
        self.conn.executescript(PHASE1_SCHEMA)

    def migrate_geo(self) -> None:
        """Create/repair geo storage and discard rows from the deprecated pconline cache."""
        with self.lock:
            cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(question)").fetchall()}
            if "ip" not in cols:
                self.conn.execute("ALTER TABLE question ADD COLUMN ip TEXT")
            self.conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ip_geo (
                  ip TEXT PRIMARY KEY,
                  country TEXT,
                  province TEXT NOT NULL DEFAULT '',
                  city TEXT NOT NULL DEFAULT '',
                  region TEXT NOT NULL DEFAULT '',
                  addr TEXT NOT NULL DEFAULT '',
                  isp TEXT,
                  country_code TEXT,
                  provider TEXT,
                  raw_region TEXT,
                  looked_up_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_question_ip ON question(ip);
                """
            )
            geo_cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(ip_geo)").fetchall()}
            for name, ddl in {
                "country": "ALTER TABLE ip_geo ADD COLUMN country TEXT",
                "isp": "ALTER TABLE ip_geo ADD COLUMN isp TEXT",
                "country_code": "ALTER TABLE ip_geo ADD COLUMN country_code TEXT",
                "provider": "ALTER TABLE ip_geo ADD COLUMN provider TEXT",
                "raw_region": "ALTER TABLE ip_geo ADD COLUMN raw_region TEXT",
            }.items():
                if name not in geo_cols:
                    self.conn.execute(ddl)
            self.conn.execute("DELETE FROM ip_geo WHERE provider IS NULL OR provider != 'ip2region'")

    def set_geo_enabled(self, enabled: bool) -> None:
        """Synchronize hot-reloaded geo config with the DB writer and migration state."""
        with self.lock:
            if enabled and not self.geo_enabled:
                self.migrate_geo()
                self.conn.commit()
            self.geo_enabled = enabled

    def migrate_moderation(self) -> None:
        """Create Phase 3 moderation metadata/audit tables without enabling LLM behavior."""
        with self.lock:
            cols = {row["name"] for row in self.conn.execute("PRAGMA table_info(question)").fetchall()}
            for name, ddl in {
                "moderation_source": "ALTER TABLE question ADD COLUMN moderation_source TEXT",
                "moderation_reason": "ALTER TABLE question ADD COLUMN moderation_reason TEXT",
                "moderated_at": "ALTER TABLE question ADD COLUMN moderated_at INTEGER",
            }.items():
                if name not in cols:
                    self.conn.execute(ddl)
            self.conn.executescript(PHASE3_SCHEMA)

    def migrate_moderation_state_events(self) -> None:
        """Create dedicated moderation state and append-only event tables."""
        with self.lock:
            self.conn.executescript(MODERATION_STATE_EVENTS_SCHEMA)

    def _insert_question_locked(self, question: dict[str, Any], *, deleted_at: int | None = None, ip: str | None = None) -> bool:
        cols = ["uuid", "owner", "question_type", "question", "word_count", "asked_at"]
        vals: list[Any] = [
            question["uuid"],
            question["owner"],
            question["type"],
            question["text"],
            len(question["text"]),
            question["asked_at"],
        ]
        if deleted_at is not None:
            cols.append("deleted_at")
            vals.append(deleted_at)
        if self.geo_enabled:
            cols.append("ip")
            vals.append(ip or "")
        placeholders = ",".join("?" for _ in cols)
        sql = f"INSERT INTO question ({','.join(cols)}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
        cur = self.conn.execute(sql, vals)
        return cur.rowcount == 1

    def insert_question(self, question: dict[str, Any], *, deleted_at: int | None = None, ip: str | None = None) -> bool:
        with self.lock:
            cur = self._insert_question_locked(question, deleted_at=deleted_at, ip=ip)
            self.conn.commit()
            return cur

    def insert_blocked_question(
        self,
        question: dict[str, Any],
        *,
        source: str,
        reason: str,
        category: str | None = None,
        ip: str | None = None,
    ) -> bool:
        created_at = int(question["asked_at"])
        with self.lock:
            try:
                inserted = self._insert_question_locked(question, ip=ip)
                if not inserted:
                    self.conn.commit()
                    return False
                self.conn.execute(
                    """
                    INSERT INTO question_moderation_state (
                      uuid, status, source, reason, category, created_at, updated_at
                    )
                    VALUES (?, 'blocked', ?, ?, ?, ?, ?)
                    """,
                    (question["uuid"], source, reason, category, created_at, created_at),
                )
                self._insert_moderation_event_locked(
                    question["uuid"],
                    event_type="blocked",
                    status="blocked",
                    source=source,
                    reason=reason,
                    category=category,
                    created_at=created_at,
                )
                self.conn.commit()
                return True
            except Exception:
                self.conn.rollback()
                raise

    def _insert_moderation_event_locked(
        self,
        uuid: str,
        *,
        event_type: str,
        status: str,
        source: str,
        reason: str,
        category: str | None,
        created_at: int,
        actor: str = "",
    ) -> None:
        self.conn.execute(
            """
            INSERT INTO question_moderation_event (
              uuid, event_type, status, source, reason, category, actor, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (uuid, event_type, status, source, reason, category, actor, created_at),
        )

    def get_question(
        self,
        uuid: str,
        *,
        with_visit: bool = False,
        include_geo: bool = False,
        include_deleted: bool = True,
        include_moderation: bool = False,
    ) -> dict[str, Any] | None:
        geo_select = ", q.ip, ig.addr AS ip_addr, ig.isp AS ip_isp" if include_geo and self.geo_enabled else ""
        geo_join = " LEFT JOIN ip_geo ig ON ig.ip = q.ip" if include_geo and self.geo_enabled else ""
        visit_select = ", v.last_visited_at, v.visit_count" if with_visit else ""
        visit_join = " LEFT JOIN visit v ON v.uuid = q.uuid" if with_visit else ""
        moderation_select = (
            ", ms.status AS moderation_status, ms.source AS moderation_source, "
            "ms.reason AS moderation_reason, ms.category AS moderation_category, "
            "ms.created_at AS moderation_created_at, ms.updated_at AS moderation_updated_at"
            if include_moderation
            else ""
        )
        moderation_join = " LEFT JOIN question_moderation_state ms ON ms.uuid = q.uuid" if include_moderation else ""
        sql = (
            "SELECT q.id, q.uuid, q.owner, q.question_type, q.question, q.word_count, q.answer, "
            "q.asked_at, q.answered_at, q.answered_by, q.marked_at"
            f"{visit_select}{geo_select}{moderation_select} FROM question q{visit_join}{geo_join}{moderation_join} "
            "WHERE q.uuid = ?"
        )
        params: list[Any] = [uuid]
        if not include_deleted:
            sql += " AND q.deleted_at IS NULL"
        with self.lock:
            row = self.conn.execute(sql, params).fetchone()
        return self._question_from_row(row, include_geo=include_geo, include_moderation=include_moderation) if row else None

    def _owner_filters(
        self,
        *,
        owner: str,
        qtype: str,
        marked: bool,
        due_after: int,
        reply_status: int,
        include_geo: bool,
        location_addr: str,
        moderation_status: str,
    ) -> tuple[list[str], list[Any], str, str]:
        filters = ["q.owner = ?", "q.question_type = ?", "q.asked_at > ?", "q.deleted_at IS NULL"]
        params: list[Any] = [owner, qtype, due_after]
        if reply_status < 0:
            filters.append("q.answered_at IS NULL")
        elif reply_status == 1:
            filters.append("q.answered_at IS NOT NULL")
        elif reply_status == 2:
            filters.append("q.answered_at IS NOT NULL")
            filters.append("q.answered_by = 'manual'")
        if marked:
            filters.append("q.marked_at IS NOT NULL")
        moderation_join = " LEFT JOIN question_moderation_state ms ON ms.uuid = q.uuid"
        if moderation_status == "blocked":
            filters.append("ms.status = 'blocked'")
        else:
            filters.append("(ms.uuid IS NULL OR ms.status = 'approved')")

        geo_join = " LEFT JOIN ip_geo ig ON ig.ip = q.ip" if include_geo and self.geo_enabled else ""
        filter_by_location = include_geo and self.geo_enabled and bool(location_addr)
        if filter_by_location:
            if location_addr == LOCATION_NO_DATA_VALUE:
                filters.append("(ig.addr IS NULL OR ig.addr = '')")
            else:
                filters.append("ig.addr = ?")
                params.append(location_addr)
        return filters, params, geo_join, moderation_join

    def list_questions(
        self,
        *,
        owner: str,
        qtype: str,
        order_by: str,
        reversed_order: bool,
        marked: bool,
        due_after: int,
        page_size: int,
        page: int,
        reply_status: int,
        include_geo: bool = False,
        location_addr: str = "",
        moderation_status: str = "normal",
    ) -> tuple[list[dict[str, Any]], int]:
        filters, params, geo_join, moderation_join = self._owner_filters(
            owner=owner,
            qtype=qtype,
            marked=marked,
            due_after=due_after,
            reply_status=reply_status,
            include_geo=include_geo,
            location_addr=location_addr,
            moderation_status=moderation_status,
        )
        where = " AND ".join(filters)
        direction = "DESC" if reversed_order else "ASC"
        geo_select = ", q.ip, ig.addr AS ip_addr, ig.isp AS ip_isp" if include_geo and self.geo_enabled else ""
        moderation_select = (
            ", ms.status AS moderation_status, ms.source AS moderation_source, "
            "ms.reason AS moderation_reason, ms.category AS moderation_category, "
            "ms.created_at AS moderation_created_at, ms.updated_at AS moderation_updated_at"
        )
        offset = max(page - 1, 0) * page_size
        with self.lock:
            total = self.conn.execute(
                f"SELECT COUNT(*) FROM question q{geo_join}{moderation_join} WHERE {where}",
                params,
            ).fetchone()[0]
            rows = self.conn.execute(
                "SELECT q.id, q.uuid, q.owner, q.question_type, q.question, q.word_count, q.answer, "
                "q.asked_at, q.answered_at, q.answered_by, q.marked_at, "
                "v.last_visited_at, v.visit_count"
                f"{geo_select}{moderation_select} FROM question q LEFT JOIN visit v ON v.uuid = q.uuid"
                f"{geo_join}{moderation_join} "
                f"WHERE {where} ORDER BY q.{order_by} {direction}, q.id ASC LIMIT ? OFFSET ?",
                [*params, page_size, offset],
            ).fetchall()
        return [self._question_from_row(row, include_geo=include_geo, include_moderation=True) for row in rows], int(total)

    def count_questions(
        self,
        *,
        owner: str,
        qtype: str,
        marked: bool,
        due_after: int,
        reply_status: int,
        include_geo: bool = False,
        location_addr: str = "",
        moderation_status: str = "normal",
    ) -> int:
        filters, params, geo_join, moderation_join = self._owner_filters(
            owner=owner,
            qtype=qtype,
            marked=marked,
            due_after=due_after,
            reply_status=reply_status,
            include_geo=include_geo,
            location_addr=location_addr,
            moderation_status=moderation_status,
        )
        where = " AND ".join(filters)
        with self.lock:
            return int(
                self.conn.execute(
                    f"SELECT COUNT(*) FROM question q{geo_join}{moderation_join} WHERE {where}",
                    params,
                ).fetchone()[0]
            )

    def list_location_options(
        self,
        *,
        owner: str,
        qtype: str,
        marked: bool,
        due_after: int,
        reply_status: int,
        moderation_status: str = "normal",
    ) -> list[dict[str, Any]]:
        if not self.geo_enabled:
            return []
        filters, params, _, moderation_join = self._owner_filters(
            owner=owner,
            qtype=qtype,
            marked=marked,
            due_after=due_after,
            reply_status=reply_status,
            include_geo=False,
            location_addr="",
            moderation_status=moderation_status,
        )
        where = " AND ".join(filters)
        located_where = where + " AND ig.addr IS NOT NULL AND ig.addr != ''"
        missing_where = where + " AND (ig.addr IS NULL OR ig.addr = '')"
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT ig.addr, ig.isp, COUNT(*) AS count
                FROM question q
                JOIN ip_geo ig ON ig.ip = q.ip
                """
                + moderation_join
                + """
                WHERE """
                + located_where
                + """
                GROUP BY ig.addr, ig.isp
                ORDER BY ig.addr ASC, ig.isp ASC
                """,
                params,
            ).fetchall()
            missing_count = self.conn.execute(
                "SELECT COUNT(*) FROM question q LEFT JOIN ip_geo ig ON ig.ip = q.ip" + moderation_join + " WHERE " + missing_where,
                params,
            ).fetchone()[0]

        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            addr = row["addr"] or ""
            if not addr:
                continue
            option = grouped.setdefault(addr, {"addr": addr, "isps": set(), "count": 0})
            if row["isp"]:
                option["isps"].add(row["isp"])
            option["count"] += int(row["count"] or 0)
        result = []
        for addr, option in grouped.items():
            isps = sorted(option["isps"])
            result.append(
                {
                    "addr": addr,
                    "isps": isps,
                    "label": f"{addr} / {'、'.join(isps)}" if isps else addr,
                    "count": option["count"],
                }
            )
        result = sorted(result, key=lambda item: item["addr"])
        if missing_count:
            result.insert(
                0,
                {
                    "addr": LOCATION_NO_DATA_VALUE,
                    "isps": [],
                    "label": LOCATION_NO_DATA_LABEL,
                    "count": int(missing_count),
                    "is_missing": True,
                },
            )
        return result

    def update_answer(self, uuid: str, answer: str, answered_by: str, answered_at: int) -> bool:
        with self.lock:
            cur = self.conn.execute(
                "UPDATE question SET answer = ?, answered_at = ?, answered_by = ? WHERE uuid = ? AND deleted_at IS NULL",
                (answer, answered_at, answered_by, uuid),
            )
            self.conn.commit()
            return cur.rowcount == 1

    def mark_deleted(self, uuid: str, deleted_at: int) -> bool:
        with self.lock:
            try:
                state = self.conn.execute(
                    """
                    SELECT status, source, reason, category
                    FROM question_moderation_state
                    WHERE uuid = ?
                    """,
                    (uuid,),
                ).fetchone()
                cur = self.conn.execute(
                    "UPDATE question SET deleted_at = ? WHERE uuid = ? AND deleted_at IS NULL",
                    (deleted_at, uuid),
                )
                if cur.rowcount == 1 and state is not None:
                    self._insert_moderation_event_locked(
                        uuid,
                        event_type="deleted",
                        status=str(state["status"]),
                        source=str(state["source"] or ""),
                        reason=str(state["reason"] or ""),
                        category=state["category"],
                        created_at=deleted_at,
                    )
                self.conn.commit()
                return cur.rowcount == 1
            except Exception:
                self.conn.rollback()
                raise

    def approve_moderation(self, uuid: str, approved_at: int) -> str:
        with self.lock:
            try:
                row = self.conn.execute(
                    """
                    SELECT q.deleted_at, ms.status, ms.source, ms.reason, ms.category
                    FROM question q
                    LEFT JOIN question_moderation_state ms ON ms.uuid = q.uuid
                    WHERE q.uuid = ?
                    """,
                    (uuid,),
                ).fetchone()
                if row is None:
                    return "missing"
                if row["deleted_at"] is not None:
                    return "deleted"
                status = row["status"]
                if status is None:
                    return "unmoderated"
                if status == "approved":
                    return "already_approved"
                if status == "pending":
                    return "pending"
                if status != "blocked":
                    return "invalid"
                self.conn.execute(
                    """
                    UPDATE question_moderation_state
                    SET status = 'approved', updated_at = ?
                    WHERE uuid = ? AND status = 'blocked'
                    """,
                    (approved_at, uuid),
                )
                self._insert_moderation_event_locked(
                    uuid,
                    event_type="approved",
                    status="approved",
                    source=str(row["source"] or ""),
                    reason=str(row["reason"] or ""),
                    category=row["category"],
                    created_at=approved_at,
                )
                self.conn.commit()
                return "approved"
            except Exception:
                self.conn.rollback()
                raise

    def update_mark(self, uuid: str, marked_at: int | None) -> bool:
        with self.lock:
            cur = self.conn.execute(
                "UPDATE question SET marked_at = ? WHERE uuid = ? AND deleted_at IS NULL",
                (marked_at, uuid),
            )
            self.conn.commit()
            return cur.rowcount == 1

    def upsert_visit(self, uuid: str, visited_at: int, count: int = 1) -> None:
        with self.lock:
            self.conn.execute(
                """
                INSERT INTO visit (uuid, last_visited_at, visit_count)
                VALUES (?, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET
                  visit_count = visit_count + excluded.visit_count,
                  last_visited_at = excluded.last_visited_at
                """,
                (uuid, visited_at, count),
            )
            self.conn.commit()

    def get_ip_geo(self, ip: str) -> dict[str, Any] | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM ip_geo WHERE ip = ?", (ip,)).fetchone()
        return dict(row) if row else None

    def insert_ip_geo(self, data: dict[str, Any]) -> None:
        with self.lock:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO ip_geo (
                  ip, country, province, city, region, addr, isp, country_code, provider, raw_region, looked_up_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data["ip"],
                    data.get("country", ""),
                    data.get("province", ""),
                    data.get("city", ""),
                    data.get("region", ""),
                    data.get("addr", ""),
                    data.get("isp", ""),
                    data.get("country_code", ""),
                    data.get("provider", ""),
                    data.get("raw_region", ""),
                    data["looked_up_at"],
                ),
            )
            self.conn.commit()

    def ping(self) -> bool:
        try:
            with self.lock:
                self.conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    @staticmethod
    def _question_from_row(row: sqlite3.Row, *, include_geo: bool, include_moderation: bool = False) -> dict[str, Any]:
        columns = set(row.keys())
        # The DB stores absent timestamps as NULL; legacy JSON uses epoch strings instead.
        question = {
            "uuid": row["uuid"],
            "type": row["question_type"],
            "owner": row["owner"],
            "text": row["question"],
            "word_count": int(row["word_count"] or 0),
            "asked_at": rfc3339_from_epoch(row["asked_at"]),
            "answer": row["answer"] or "",
            "answered_at": rfc3339_from_epoch(row["answered_at"]),
            "answered_by": row["answered_by"] or "",
            "last_visited_at": rfc3339_from_epoch(row["last_visited_at"] if "last_visited_at" in columns else 0),
            "visit_count": int((row["visit_count"] if "visit_count" in columns else 0) or 0),
            "images": [],
            "marked": bool(row["marked_at"]),
        }
        if include_geo and "ip" in columns:
            question["ip"] = row["ip"] or ""
            question["ip_addr"] = row["ip_addr"] or ""
            question["ip_isp"] = row["ip_isp"] or ""
        if include_moderation and "moderation_status" in columns and row["moderation_status"]:
            question["moderation"] = {
                "status": row["moderation_status"],
                "source": row["moderation_source"] or "",
                "reason": row["moderation_reason"] or "",
                "category": row["moderation_category"],
                "created_at": rfc3339_from_epoch(row["moderation_created_at"]),
                "updated_at": rfc3339_from_epoch(row["moderation_updated_at"]),
            }
        return question
