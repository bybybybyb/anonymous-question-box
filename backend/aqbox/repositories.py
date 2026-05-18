from __future__ import annotations

from typing import Any

from .db import Database


class SubmissionRepository:
    def __init__(self, db: Database):
        self.db = db

    def insert(self, question: dict[str, Any], *, deleted_at: int | None = None, ip: str | None = None) -> bool:
        return self.db.insert_question(question, deleted_at=deleted_at, ip=ip)

    def insert_blocked(
        self,
        question: dict[str, Any],
        *,
        source: str,
        reason: str,
        category: str | None = None,
        ip: str | None = None,
    ) -> bool:
        return self.db.insert_blocked_question(question, source=source, reason=reason, category=category, ip=ip)

    def insert_pending(
        self,
        question: dict[str, Any],
        *,
        provider: str,
        model: str,
        prompt_version: str,
        policy_hash: str,
        config_hash: str,
        ip: str | None = None,
    ) -> bool:
        return self.db.insert_pending_question(
            question,
            provider=provider,
            model=model,
            prompt_version=prompt_version,
            policy_hash=policy_hash,
            config_hash=config_hash,
            ip=ip,
        )

    def get(
        self,
        uuid: str,
        *,
        with_visit: bool = False,
        include_geo: bool = False,
        include_deleted: bool = True,
        include_moderation: bool = False,
    ) -> dict[str, Any] | None:
        return self.db.get_question(
            uuid,
            with_visit=with_visit,
            include_geo=include_geo,
            include_deleted=include_deleted,
            include_moderation=include_moderation,
        )

    def list_owner(
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
        return self.db.list_questions(
            owner=owner,
            qtype=qtype,
            order_by=order_by,
            reversed_order=reversed_order,
            marked=marked,
            due_after=due_after,
            page_size=page_size,
            page=page,
            reply_status=reply_status,
            include_geo=include_geo,
            location_addr=location_addr,
            moderation_status=moderation_status,
        )

    def count_owner(
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
        return self.db.count_questions(
            owner=owner,
            qtype=qtype,
            marked=marked,
            due_after=due_after,
            reply_status=reply_status,
            include_geo=include_geo,
            location_addr=location_addr,
            moderation_status=moderation_status,
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
        return self.db.list_location_options(
            owner=owner,
            qtype=qtype,
            marked=marked,
            due_after=due_after,
            reply_status=reply_status,
            moderation_status=moderation_status,
        )

    def answer(self, uuid: str, answer: str, answered_by: str, answered_at: int) -> bool:
        return self.db.update_answer(uuid, answer, answered_by, answered_at)

    def mark(self, uuid: str, marked_at: int | None) -> bool:
        return self.db.update_mark(uuid, marked_at)

    def delete(self, uuid: str, deleted_at: int) -> bool:
        return self.db.mark_deleted(uuid, deleted_at)

    def approve_moderation(self, uuid: str, approved_at: int) -> str:
        return self.db.approve_moderation(uuid, approved_at)


class VisitRepository:
    def __init__(self, db: Database):
        self.db = db

    def upsert(self, uuid: str, visited_at: int, count: int = 1) -> None:
        self.db.upsert_visit(uuid, visited_at, count)


class GeoRepository:
    def __init__(self, db: Database):
        self.db = db

    def get(self, ip: str) -> dict[str, Any] | None:
        return self.db.get_ip_geo(ip)

    def insert(self, data: dict[str, Any]) -> None:
        self.db.insert_ip_geo(data)


class OpsRepository:
    def __init__(self, db: Database):
        self.db = db

    def ping(self) -> bool:
        return self.db.ping()
