from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import Request

from .auth import Principal, bearer_token, generate_token, validate_token
from .config import Settings
from .geo import geo_status, lookup_and_store, resolve_client_ip
from .legacy import LegacyAPIError
from .moderation import FilterResult, keyword_filter
from .repositories import OpsRepository, SubmissionRepository, VisitRepository
from .schemas import AnswerQuestionRequest, ListQuestionsRequest, SubmitQuestionRequest, UpdateQuestionMarkRequest
from .settings_provider import SettingsProvider
from .timeutil import now_epoch, rfc3339_from_epoch


class AuthService:
    def principal(self, settings: Settings, auth_header: str | None) -> Principal:
        token = bearer_token(auth_header)
        if token is None:
            raise LegacyAPIError(403, "无效token")
        try:
            return validate_token(settings, token)
        except Exception as exc:
            raise LegacyAPIError(401, f"无法解析token，错误信息：{exc}") from exc

    def require_asker(self, settings: Settings, auth_header: str | None) -> Principal:
        principal = self.principal(settings, auth_header)
        if principal.is_admin:
            raise LegacyAPIError(403, "提问箱主人能问自己和其他提问箱主人问题嘛？答案是不能")
        return principal

    def require_owner(self, settings: Settings, auth_header: str | None) -> Principal:
        principal = self.principal(settings, auth_header)
        if not principal.is_admin:
            raise LegacyAPIError(401, "未授权访问")
        return principal

    def new_asker_token(self, settings: Settings) -> str:
        return generate_token(settings, str(uuid4()))


class ProfileService:
    def public_profiles(self, settings: Settings) -> dict[str, Any]:
        return settings.public_profiles()


class ModerationService:
    def keyword_decision(self, text: str, settings: Settings) -> FilterResult:
        return keyword_filter(text, settings.filtered_keywords)


class GeoService:
    """Coordinates background geo lookups and suppresses duplicate in-flight IP work."""

    def __init__(self):
        self.background_tasks: set[asyncio.Task[None]] = set()
        self.in_flight_ips: set[str] = set()
        self.lookup_semaphore = asyncio.Semaphore(2)

    def client_ip(self, request: Request, settings: Settings) -> str | None:
        return resolve_client_ip(request, settings) if settings.geo_enabled else None

    def schedule_lookup(self, repo: SubmissionRepository, settings: Settings, ip: str | None) -> None:
        if settings.geo_enabled and ip:
            if ip in self.in_flight_ips:
                return
            self.in_flight_ips.add(ip)
            task = asyncio.create_task(self._lookup_once(repo, settings, ip))
            self.background_tasks.add(task)
            task.add_done_callback(lambda finished: self._forget_lookup(finished, ip))

    async def _lookup_once(self, repo: SubmissionRepository, settings: Settings, ip: str) -> None:
        async with self.lookup_semaphore:
            await lookup_and_store(repo.db, settings, ip)

    def _forget_lookup(self, task: asyncio.Task[None], ip: str) -> None:
        self.background_tasks.discard(task)
        self.in_flight_ips.discard(ip)


class VisitService:
    """Batches asker visits so reads stay fast while counts flush on a fixed cadence."""

    def __init__(self, repo: VisitRepository, settings_provider: SettingsProvider):
        self.repo = repo
        self.settings_provider = settings_provider
        self.queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()

    def enqueue_if_answered(self, uuid: str, question: dict[str, Any]) -> None:
        if question["answered_at"] != rfc3339_from_epoch(0):
            self.queue.put_nowait((uuid, now_epoch()))

    async def run(self) -> None:
        """Flush pending visits by deadline even when traffic never goes idle."""
        pending: dict[str, tuple[int, int]] = {}
        loop = asyncio.get_running_loop()
        interval = max(self.settings_provider.current().visit_flush_interval_seconds, 0.001)
        next_flush = loop.time() + interval

        def collect(uuid: str, visited_at: int) -> None:
            count, latest = pending.get(uuid, (0, 0))
            pending[uuid] = (count + 1, max(latest, visited_at))

        def flush() -> None:
            if not pending:
                return
            for uuid, (count, latest) in list(pending.items()):
                self.repo.upsert(uuid, latest, count)
            pending.clear()

        try:
            while True:
                timeout = max(0.0, next_flush - loop.time())
                try:
                    uuid, visited_at = await asyncio.wait_for(self.queue.get(), timeout=timeout)
                    collect(uuid, visited_at)
                except TimeoutError:
                    pass
                if loop.time() >= next_flush:
                    flush()
                    interval = max(self.settings_provider.current().visit_flush_interval_seconds, 0.001)
                    next_flush = loop.time() + interval
        except asyncio.CancelledError:
            while not self.queue.empty():
                uuid, visited_at = self.queue.get_nowait()
                collect(uuid, visited_at)
            flush()
            raise


class SubmissionService:
    """Asker-side submission behavior, including stealth keyword moderation blocks."""

    def __init__(self, repo: SubmissionRepository, moderation: ModerationService, geo: GeoService):
        self.repo = repo
        self.moderation = moderation
        self.geo = geo

    def get_for_asker(self, uuid: str, visit_service: VisitService) -> dict[str, Any]:
        question = self.repo.get(uuid, with_visit=False, include_geo=False)
        if question is None:
            raise LegacyAPIError(404, "投稿不存在")
        visit_service.enqueue_if_answered(uuid, question)
        return question

    def submit(self, request: Request, principal: Principal, req: SubmitQuestionRequest, settings: Settings) -> dict[str, str]:
        question_type = validate_question_type(settings, req.owner, req.type)
        text = req.text.strip()
        rune_limit, _ = settings.rune_limit(req.owner, req.type)
        if len(text) > rune_limit:
            raise LegacyAPIError(400, f"投稿长度超过最大限度 {rune_limit}")
        if len(text) == 0:
            raise LegacyAPIError(400, "空投稿")
        start = parse_time(question_type.get("start_time"))
        end = parse_time(question_type.get("end_time"))
        current = now_epoch()
        if start is not None and current < start:
            raise LegacyAPIError(400, f"尚未开始接受投稿，投稿将于 {rfc3339_from_epoch(start)} 开放")
        if end is not None and current > end:
            raise LegacyAPIError(400, f"投稿已于 {rfc3339_from_epoch(end)} 截止")
        if req.images:
            raise LegacyAPIError(400, "本提问箱不支持图片上传")

        asked_at = now_epoch()
        moderation_decision = self.moderation.keyword_decision(text, settings)
        ip = self.geo.client_ip(request, settings)
        question = {"uuid": principal.uuid, "owner": req.owner, "type": req.type, "text": text, "asked_at": asked_at}
        if moderation_decision.blocked:
            # Keyword moderation is stealthy to the submitter but no longer uses owner deletion storage.
            inserted = self.repo.insert_blocked(
                question,
                source=moderation_decision.source or "keyword",
                reason=moderation_decision.reason or "keyword",
                ip=ip,
            )
        else:
            inserted = self.repo.insert(question, ip=ip)
        if not inserted:
            raise LegacyAPIError(409, "提交失败，错误信息：no row inserted，请联系网站管理员")
        self.geo.schedule_lookup(self.repo, settings, ip)
        return {"uuid": principal.uuid, "asked_at": rfc3339_from_epoch(asked_at)}


class OwnerConsoleService:
    """Owner console operations; normal reads hide deleted and moderation-hidden submissions."""

    def __init__(self, repo: SubmissionRepository):
        self.repo = repo

    def list_submissions(self, req: ListQuestionsRequest, settings: Settings) -> dict[str, Any]:
        validate_question_type(settings, req.owner, req.type)
        allowed_sort = {"asked_at": "asked_at", "word_count": "word_count"}
        if req.order_params.by not in allowed_sort:
            raise LegacyAPIError(400, f"不支持的排序字段 {req.order_params.by}")
        page_size = req.page_size if req.page_size > 0 else 20
        page = req.page if req.page > 0 else 1
        due_after = now_epoch() - max(req.day_limit, 0) * 24 * 60 * 60
        questions, total = self.repo.list_owner(
            owner=req.owner,
            qtype=req.type,
            order_by=allowed_sort[req.order_params.by],
            reversed_order=req.order_params.reversed,
            marked=req.marked,
            due_after=due_after,
            page_size=page_size,
            page=page,
            reply_status=req.reply_status,
            include_geo=settings.geo_enabled,
            location_addr=req.ip_addr if settings.geo_enabled else "",
            moderation_status=req.moderation_status,
        )
        blocked_count = self.repo.count_owner(
            owner=req.owner,
            qtype=req.type,
            marked=req.marked,
            due_after=due_after,
            reply_status=req.reply_status,
            include_geo=settings.geo_enabled,
            location_addr=req.ip_addr if settings.geo_enabled else "",
            moderation_status="blocked",
        )
        location_options = (
            self.repo.list_location_options(
                owner=req.owner,
                qtype=req.type,
                marked=req.marked,
                due_after=due_after,
                reply_status=req.reply_status,
                moderation_status=req.moderation_status,
            )
            if settings.geo_enabled
            else []
        )
        return {
            "questions": questions,
            "total": total,
            "page_size": page_size,
            "page": page,
            "location_options": location_options,
            "moderation_counts": {"blocked": blocked_count},
        }

    def detail(self, uuid: str, settings: Settings) -> dict[str, Any]:
        question = self.repo.get(
            uuid,
            with_visit=True,
            include_geo=settings.geo_enabled,
            include_deleted=False,
            include_moderation=True,
        )
        if question is None or question.get("moderation", {}).get("status") == "pending":
            raise LegacyAPIError(404, "投稿不存在")
        return question

    def answer(self, uuid: str, req: AnswerQuestionRequest) -> None:
        if req.uuid and req.uuid != uuid:
            raise LegacyAPIError(400, "投稿UUID不匹配")
        ok = self.repo.answer(uuid, req.answer, req.answered_by, now_epoch())
        if not ok:
            raise LegacyAPIError(404, "投稿不存在或已过期销毁")

    def mark(self, uuid: str, req: UpdateQuestionMarkRequest, settings: Settings) -> None:
        validate_question_type(settings, req.owner, req.type)
        ok = self.repo.mark(uuid, now_epoch() if req.mark else None)
        if not ok:
            raise LegacyAPIError(404, "投稿不存在或已删除")

    def delete(self, uuid: str) -> None:
        # Delete is UUID-only on the public contract, so keep it independent of current owner/type config.
        # That lets owners clean up historical submissions even if a question type is later removed.
        ok = self.repo.delete(uuid, now_epoch())
        if not ok:
            raise LegacyAPIError(404, "投稿不存在或已过期销毁")

    def approve_moderation(self, uuid: str) -> None:
        result = self.repo.approve_moderation(uuid, now_epoch())
        if result in {"approved", "already_approved"}:
            return
        if result in {"missing", "deleted"}:
            raise LegacyAPIError(404, "投稿不存在或已删除")
        if result == "pending":
            raise LegacyAPIError(400, "待审核投稿不能手动通过")
        if result == "unmoderated":
            raise LegacyAPIError(400, "投稿没有可审批的审核状态")
        raise LegacyAPIError(400, "投稿审核状态无法通过")


class OpsService:
    def __init__(self, repo: OpsRepository, settings_provider: SettingsProvider):
        self.repo = repo
        self.settings_provider = settings_provider

    def health(self, visit_task: asyncio.Task | None) -> tuple[int, dict[str, Any]]:
        db_ok = self.repo.ping()
        config_ok = self.settings_provider.healthy
        worker_ok = visit_task is not None and not visit_task.done()
        ok = db_ok and config_ok and worker_ok
        return (
            200 if ok else 503,
            {
                "ok": ok,
                "db": db_ok,
                "config": config_ok,
                "visit_worker": worker_ok,
            },
        )

    def config_status(self) -> dict[str, Any]:
        status = self.settings_provider.status_dict()
        status["geo"] = geo_status()
        return status


def parse_time(value: str | None) -> int | None:
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return int(datetime.fromisoformat(normalized).astimezone(UTC).timestamp())
    except ValueError as exc:
        raise LegacyAPIError(500, f"投稿类型时间窗配置无效: {value}") from exc


def validate_question_type(settings: Settings, owner: str, qtype: str) -> dict[str, Any]:
    question_type = settings.question_type(owner, qtype)
    if question_type is None:
        raise LegacyAPIError(400, f"未知提问箱主人 {owner} 或投稿类型 {qtype}")
    return question_type
