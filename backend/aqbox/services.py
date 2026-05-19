from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from contextlib import suppress
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from fastapi import Request

from .auth import Principal, bearer_token, generate_token, validate_token
from .config import Settings
from .geo import geo_status, lookup_and_store, resolve_client_ip
from .legacy import LegacyAPIError
from .llm_provider import LLMProvider, LLMProviderResponse, build_llm_provider_request
from .moderation import (
    FilterResult,
    InvalidLLMModerationResponseError,
    ParsedLLMModerationResponse,
    build_llm_moderation_prompt,
    keyword_filter,
    llm_policy_for,
    parse_llm_moderation_response,
)
from .repositories import OpsRepository, SubmissionRepository, VisitRepository
from .schemas import AnswerQuestionRequest, ListQuestionsRequest, SubmitQuestionRequest, UpdateQuestionMarkRequest
from .settings_provider import SettingsProvider
from .timeutil import now_epoch, rfc3339_from_epoch

logger = logging.getLogger(__name__)


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


class LLMModerationWorker:
    """Processes pending LLM moderation rows without holding SQLite locks across provider I/O."""

    def __init__(
        self,
        db: Any,
        settings_provider: SettingsProvider,
        *,
        provider: LLMProvider,
        poll_interval_seconds: float = 0.5,
        lock_seconds: int = 30,
        batch_size: int = 5,
    ):
        self.db = db
        self.settings_provider = settings_provider
        self.provider = provider
        self.poll_interval_seconds = max(poll_interval_seconds, 0.01)
        self.lock_seconds = max(lock_seconds, 1)
        self.batch_size = max(batch_size, 1)
        self.lock_owner = f"llm-worker-{uuid4()}"
        self._stop = asyncio.Event()
        self.last_successful_check_at: int | None = None
        self.recent_error_class: str | None = None

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        while not self._stop.is_set():
            with suppress(TimeoutError):
                await asyncio.wait_for(self._stop.wait(), timeout=self.poll_interval_seconds)
            if self._stop.is_set():
                break
            await self.run_once()

    async def run_once(self) -> None:
        now = now_epoch()
        settings = self.settings_provider.current()
        max_attempts = settings.llm_moderation.max_attempts if settings.llm_moderation.enabled else None
        sweep_future = not settings.llm_moderation.enabled
        rows = self.db.claim_due_llm_moderation(
            now=now,
            lock_owner=self.lock_owner,
            lock_seconds=self.lock_seconds,
            limit=self.batch_size,
            max_attempts=max_attempts,
            include_future=sweep_future,
        )
        if settings.llm_moderation.enabled and len(rows) < self.batch_size:
            rows.extend(self._claim_disabled_policy_rows(settings, now, self.batch_size - len(rows)))
        self.db.purge_due_raw_moderation_event_fields(now=now)
        self.last_successful_check_at = now
        for row in rows:
            try:
                await self._process_claimed(row)
            except Exception:
                logger.exception("Unexpected LLM moderation worker error for %s", row.get("uuid"))
                self._handle_worker_exception(row, now_epoch())

    def _claim_disabled_policy_rows(self, settings: Settings, now: int, limit: int) -> list[dict[str, Any]]:
        pairs = self.db.list_pending_llm_moderation_pairs(now=now, limit=max(limit * 4, limit))
        disabled_pairs = [(owner, qtype) for owner, qtype in pairs if llm_policy_for(settings, owner, qtype) is None]
        return cast(
            list[dict[str, Any]],
            self.db.claim_pending_llm_moderation_by_pairs(
                now=now,
                lock_owner=self.lock_owner,
                lock_seconds=self.lock_seconds,
                limit=limit,
                pairs=disabled_pairs,
            ),
        )

    def _handle_worker_exception(self, row: dict[str, Any], attempted_at: int) -> None:
        settings = self.settings_provider.current(force=True)
        if not settings.llm_moderation.enabled or llm_policy_for(settings, row["owner"], row["type"]) is None:
            self._finalize_config_disabled(row, settings, attempted_at)
            return
        self._handle_failed_attempt(
            row,
            settings,
            attempted_at,
            "worker_exception",
            _llm_metadata_from_row(row, settings),
        )

    async def _process_claimed(self, row: dict[str, Any]) -> None:
        settings = self.settings_provider.current()
        policy = llm_policy_for(settings, row["owner"], row["type"])
        finalized_at = now_epoch()
        if policy is None:
            self._finalize_config_disabled(row, settings, finalized_at)
            return
        if int(row.get("attempt_count") or 0) >= settings.llm_moderation.max_attempts:
            self.recent_error_class = "max_attempts_exhausted"
            self.db.finalize_llm_moderation_block(
                uuid=row["uuid"],
                lock_owner=self.lock_owner,
                finalized_at=finalized_at,
                source="llm_error",
                reason="never_evaluated",
                short_reason="LLM moderation attempts were already exhausted",
                rationale="The pending submission reached the configured maximum attempts before this worker run.",
                confidence=None,
                error_class="max_attempts_exhausted",
                metadata=_llm_metadata_from_row(row, settings),
                increment_attempt=False,
            )
            return

        prompt = build_llm_moderation_prompt(policy, row["text"])
        request = build_llm_provider_request(prompt=prompt, policy=policy)
        if settings.llm_moderation.raw_retention_enabled:
            request = replace(request, capture_raw_response=True)
        response = await self.provider.complete(request)
        metadata = _llm_metadata_from_response(prompt, request, policy, settings, response)
        attempted_at = now_epoch()
        current_settings = self.settings_provider.current(force=True)
        if llm_policy_for(current_settings, row["owner"], row["type"]) is None:
            self._finalize_config_disabled(row, current_settings, attempted_at)
            return
        if response.error_class is not None:
            self._handle_failed_attempt(row, current_settings, attempted_at, str(response.error_class), metadata)
            return
        try:
            parsed = parse_llm_moderation_response(
                finish_reason=response.finish_reason or "",
                content=response.content,
                original_text=row["text"],
            )
        except InvalidLLMModerationResponseError as exc:
            self._handle_failed_attempt(row, current_settings, attempted_at, f"invalid_response_{exc.code}", metadata)
            return

        if parsed.decision == "accept":
            self.db.finalize_llm_moderation_accept(
                uuid=row["uuid"],
                lock_owner=self.lock_owner,
                finalized_at=attempted_at,
                metadata={
                    **metadata,
                    "decision_json": _decision_json(parsed),
                    "short_reason": parsed.short_reason,
                    "rationale": parsed.rationale,
                },
            )
            return

        source, reason = _reject_framing(parsed, current_settings)
        self.db.finalize_llm_moderation_block(
            uuid=row["uuid"],
            lock_owner=self.lock_owner,
            finalized_at=attempted_at,
            source=source,
            reason=reason,
            short_reason=parsed.short_reason,
            rationale=parsed.rationale,
            confidence=parsed.confidence,
            error_class="",
            metadata={**metadata, "decision_json": _decision_json(parsed)},
        )

    def _finalize_config_disabled(self, row: dict[str, Any], settings: Settings, finalized_at: int) -> None:
        self.recent_error_class = "config_disabled"
        self.db.finalize_llm_moderation_block(
            uuid=row["uuid"],
            lock_owner=self.lock_owner,
            finalized_at=finalized_at,
            source="llm_error",
            reason="never_evaluated",
            short_reason="LLM moderation disabled before evaluation",
            rationale="The configured LLM policy was disabled while the submission was pending.",
            confidence=None,
            error_class="config_disabled",
            metadata=_llm_metadata_from_row(row, settings),
            increment_attempt=False,
        )

    def _handle_failed_attempt(
        self, row: dict[str, Any], settings: Settings, attempted_at: int, error_class: str, metadata: dict[str, Any]
    ) -> None:
        self.recent_error_class = error_class
        attempt_count = int(row.get("attempt_count") or 0) + 1
        if attempt_count >= settings.llm_moderation.max_attempts:
            self.db.finalize_llm_moderation_block(
                uuid=row["uuid"],
                lock_owner=self.lock_owner,
                finalized_at=attempted_at,
                source="llm_error",
                reason="never_evaluated",
                short_reason="LLM moderation could not evaluate this submission",
                rationale="The provider did not return a usable moderation decision before attempts were exhausted.",
                confidence=None,
                error_class=error_class,
                metadata=metadata,
            )
            return
        self.db.reschedule_llm_moderation_error(
            uuid=row["uuid"],
            lock_owner=self.lock_owner,
            attempted_at=attempted_at,
            next_attempt_at=attempted_at + self._retry_delay_seconds(settings, attempt_count),
            error_class=error_class,
            metadata=metadata,
        )

    @staticmethod
    def _retry_delay_seconds(settings: Settings, attempt_count: int) -> int:
        base_delay = max(0.0, settings.llm_moderation.initial_backoff_seconds)
        if base_delay == 0:
            return 0
        return int(min(base_delay * (2 ** max(attempt_count - 1, 0)), 3600))

    def health(self, *, task_running: bool) -> dict[str, Any]:
        counts = self.db.llm_moderation_counts(now=now_epoch())
        return {
            "enabled": self.settings_provider.current().llm_moderation.enabled,
            "running": task_running,
            "pending": counts["pending"],
            "due": counts["due"],
            "locked": counts["locked"],
            "last_successful_check_at": self.last_successful_check_at,
            "recent_error_class": self.recent_error_class,
        }


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
            inserted = self.repo.insert(
                question,
                deleted_at=asked_at,
                deletion_source="keyword",
                deletion_reason="keyword_filter",
                ip=ip,
            )
        elif (llm_policy := llm_policy_for(settings, req.owner, req.type)) is not None:
            prompt = build_llm_moderation_prompt(llm_policy, text)
            inserted = self.repo.insert_pending(
                question,
                provider=llm_policy.provider,
                model=llm_policy.model,
                prompt_version=prompt.prompt_version,
                policy_hash=prompt.policy_hash,
                config_hash=_llm_config_hash(settings),
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
            "questions": [_redact_blocked_question_text(question) for question in questions],
            "total": total,
            "page_size": page_size,
            "page": page,
            "location_options": location_options,
            "moderation_counts": {"blocked": blocked_count},
        }

    def detail(self, uuid: str, settings: Settings, *, reveal_raw: bool = False) -> dict[str, Any]:
        question = self.repo.get(
            uuid,
            with_visit=True,
            include_geo=settings.geo_enabled,
            include_deleted=False,
            include_moderation=True,
        )
        if question is None:
            raise LegacyAPIError(404, "投稿不存在")
        moderation = question.get("moderation", {})
        if moderation.get("status") == "pending" or moderation.get("source") == "keyword":
            raise LegacyAPIError(404, "投稿不存在")
        if moderation.get("status") == "blocked" and not reveal_raw:
            question = _redact_blocked_question_text(question)
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
            raise LegacyAPIError(400, "待审核投稿不能手动批准")
        if result == "unmoderated":
            raise LegacyAPIError(400, "投稿没有可审批的审核状态")
        raise LegacyAPIError(400, "投稿审核状态无法批准")


class OpsService:
    def __init__(self, repo: OpsRepository, settings_provider: SettingsProvider):
        self.repo = repo
        self.settings_provider = settings_provider

    def health(
        self,
        visit_task: asyncio.Task | None,
        moderation_task: asyncio.Task | None = None,
        moderation_worker: LLMModerationWorker | None = None,
    ) -> tuple[int, dict[str, Any]]:
        db_ok = self.repo.ping()
        config_ok = self.settings_provider.healthy
        worker_ok = visit_task is not None and not visit_task.done()
        payload: dict[str, Any] = {
            "db": db_ok,
            "config": config_ok,
            "visit_worker": worker_ok,
        }
        moderation_ok = True
        if self.settings_provider.current().llm_moderation.enabled:
            moderation_ok = moderation_task is not None and not moderation_task.done() and moderation_worker is not None
            payload["moderation_worker"] = (
                moderation_worker.health(task_running=moderation_ok)
                if moderation_worker is not None
                else {
                    "enabled": True,
                    "running": False,
                    "pending": 0,
                    "due": 0,
                    "locked": 0,
                    "last_successful_check_at": None,
                    "recent_error_class": None,
                }
            )
        ok = db_ok and config_ok and worker_ok
        if self.settings_provider.current().llm_moderation.enabled:
            payload["degraded"] = not moderation_ok
        payload["ok"] = ok
        return (200 if ok else 503, payload)

    def config_status(self) -> dict[str, Any]:
        status = self.settings_provider.status_dict()
        status["llm_filter"] = self.settings_provider.current().llm_moderation.public_status()
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


def _llm_config_hash(settings: Settings) -> str:
    public_config = settings.llm_moderation.public_status()
    payload = json.dumps(public_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _llm_metadata_from_row(row: dict[str, Any], settings: Settings) -> dict[str, Any]:
    return {
        "provider": row.get("provider") or settings.llm_moderation.provider,
        "model": row.get("model") or settings.llm_moderation.model,
        "prompt_version": row.get("prompt_version") or "",
        "policy_hash": row.get("policy_hash") or "",
        "config_hash": row.get("config_hash") or _llm_config_hash(settings),
    }


def _llm_metadata_from_response(
    prompt: Any, request: Any, policy: Any, settings: Settings, response: LLMProviderResponse
) -> dict[str, Any]:
    metadata = {
        "provider": policy.provider,
        "model": response.model or policy.model,
        "prompt_version": prompt.prompt_version,
        "policy_hash": prompt.policy_hash,
        "config_hash": _llm_config_hash(settings),
        "finish_reason": response.finish_reason or "",
        "latency_ms": int(response.latency_ms),
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    if settings.llm_moderation.raw_retention_enabled:
        metadata["raw_prompt"] = json.dumps(prompt.messages, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        metadata["raw_request"] = json.dumps(
            {
                "base_url": request.base_url,
                "max_tokens": request.max_tokens,
                "messages": request.messages,
                "model": request.model,
                "response_format": request.response_format,
            },
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        )
        if response.raw_response is not None:
            metadata["raw_response"] = json.dumps(response.raw_response, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
        if settings.llm_moderation.raw_retention_seconds > 0:
            metadata["purge_after"] = now_epoch() + settings.llm_moderation.raw_retention_seconds
    return metadata


def _decision_json(parsed: ParsedLLMModerationResponse) -> str:
    return json.dumps(
        {
            "decision": parsed.decision,
            "confidence": parsed.confidence,
            "short_reason": parsed.short_reason,
            "rationale": parsed.rationale,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _reject_framing(parsed: ParsedLLMModerationResponse, settings: Settings) -> tuple[str, str]:
    if parsed.confidence >= settings.llm_moderation.high_confidence_reject_threshold:
        return "llm", "model_reject"
    return "llm_low_confidence", "needs_review"


def _redact_blocked_question_text(question: dict[str, Any]) -> dict[str, Any]:
    moderation = question.get("moderation") or {}
    if moderation.get("status") != "blocked":
        return question
    redacted = dict(question)
    redacted["text"] = ""
    redacted["raw_text_hidden"] = True
    return redacted
