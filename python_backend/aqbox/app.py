from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from pydantic import ValidationError

from .auth import Principal, bearer_token, generate_token, validate_token
from .config import Settings, load_settings
from .db import Database
from .geo import lookup_and_store, resolve_client_ip
from .moderation import keyword_filter
from .schemas import (
    AnswerQuestionRequest,
    ListQuestionsRequest,
    SubmitQuestionRequest,
    UpdateQuestionMarkRequest,
    model_from_payload,
)
from .timeutil import now_epoch, rfc3339_from_epoch


class LegacyAPIError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


def legacy_error(status_code: int, message: str) -> JSONResponse:
    return JSONResponse({"error": message}, status_code=status_code)


async def read_body(request: Request, action: str) -> dict[str, Any]:
    try:
        payload = await request.json()
    except Exception as exc:
        raise LegacyAPIError(400, f"无法读取{action}请求，错误信息：{exc}") from exc
    return payload if isinstance(payload, dict) else {}


def parse_model(model: type, payload: dict[str, Any], action: str) -> Any:
    try:
        return model_from_payload(model, payload)
    except ValidationError as exc:
        raise LegacyAPIError(400, f"无法解析{action}请求，错误信息：{exc}") from exc


def auth_principal(request: Request) -> Principal:
    settings: Settings = request.app.state.settings
    token = bearer_token(request.headers.get("authorization"))
    if token is None:
        raise LegacyAPIError(403, "无效token")
    try:
        return validate_token(settings, token)
    except Exception as exc:
        raise LegacyAPIError(401, f"无法解析token，错误信息：{exc}") from exc


def require_user(request: Request) -> Principal:
    principal = auth_principal(request)
    if principal.is_admin:
        raise LegacyAPIError(403, "提问箱主人能问自己和其他提问箱主人问题嘛？答案是不能")
    return principal


def require_admin(request: Request) -> Principal:
    principal = auth_principal(request)
    if not principal.is_admin:
        raise LegacyAPIError(401, "未授权访问")
    return principal


def _parse_time(value: str | None) -> int | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return int(datetime.fromisoformat(normalized).astimezone(timezone.utc).timestamp())


def _validate_question_type(settings: Settings, owner: str, qtype: str) -> dict[str, Any]:
    question_type = settings.question_type(owner, qtype)
    if question_type is None:
        raise LegacyAPIError(400, f"未知提问箱主人 {owner} 或投稿类型 {qtype}")
    return question_type


async def _visit_worker(app: FastAPI) -> None:
    queue: asyncio.Queue[tuple[str, int]] = app.state.visit_queue
    interval = app.state.settings.visit_flush_interval_seconds
    pending: dict[str, tuple[int, int]] = {}

    def collect(uuid: str, visited_at: int) -> None:
        count, latest = pending.get(uuid, (0, 0))
        pending[uuid] = (count + 1, max(latest, visited_at))

    def flush() -> None:
        if not pending:
            return
        for uuid, (count, latest) in list(pending.items()):
            app.state.db.upsert_visit(uuid, latest, count)
        pending.clear()

    try:
        while True:
            try:
                uuid, visited_at = await asyncio.wait_for(queue.get(), timeout=interval)
                collect(uuid, visited_at)
            except asyncio.TimeoutError:
                flush()
    except asyncio.CancelledError:
        while not queue.empty():
            uuid, visited_at = queue.get_nowait()
            collect(uuid, visited_at)
        flush()
        raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db.bootstrap()
    worker = asyncio.create_task(_visit_worker(app))
    try:
        yield
    finally:
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass


def create_app(*, config_path: str | None = None, settings: Settings | None = None, db: Database | None = None) -> FastAPI:
    settings = settings or load_settings(config_path)
    db = db or Database(settings.db_path, geo_enabled=settings.geo_enabled, moderation_schema=bool(settings.llm_filter))
    app = FastAPI(title="Anonymous Question Box API", version="0.1.0", lifespan=lifespan)
    app.state.settings = settings
    app.state.db = db
    app.state.visit_queue = asyncio.Queue()

    @app.exception_handler(LegacyAPIError)
    async def legacy_exception_handler(_: Request, exc: LegacyAPIError) -> JSONResponse:
        return legacy_error(exc.status_code, exc.message)

    @app.get("/checkalive")
    async def checkalive() -> PlainTextResponse:
        return PlainTextResponse("pong")

    @app.get("/profiles")
    async def profiles(request: Request) -> dict[str, Any]:
        return request.app.state.settings.public_profiles()

    @app.get("/new")
    async def new_question_token(request: Request) -> dict[str, str]:
        token = generate_token(request.app.state.settings, str(uuid4()))
        return {"token": token}

    @app.get("/questions/question")
    async def get_question(request: Request) -> dict[str, Any]:
        principal = require_user(request)
        question = request.app.state.db.get_question(principal.uuid, with_visit=False, include_geo=False)
        if question is None:
            raise LegacyAPIError(404, "投稿不存在")
        if question["answered_at"] != rfc3339_from_epoch(0):
            request.app.state.visit_queue.put_nowait((principal.uuid, now_epoch()))
        return question

    @app.post("/questions/submit")
    async def submit_question(request: Request) -> dict[str, str]:
        principal = require_user(request)
        payload = await read_body(request, "投稿")
        req: SubmitQuestionRequest = parse_model(SubmitQuestionRequest, payload, "投稿")
        settings: Settings = request.app.state.settings
        question_type = _validate_question_type(settings, req.owner, req.type)
        text = req.text.strip()
        rune_limit, _ = settings.rune_limit(req.owner, req.type)
        if len(text) > rune_limit:
            raise LegacyAPIError(400, f"投稿长度超过最大限度 {rune_limit}")
        if len(text) == 0:
            raise LegacyAPIError(400, "空投稿")
        start = _parse_time(question_type.get("start_time"))
        end = _parse_time(question_type.get("end_time"))
        current = now_epoch()
        if start is not None and current < start:
            raise LegacyAPIError(400, f"尚未开始接受投稿，投稿将于 {rfc3339_from_epoch(start)} 开放")
        if end is not None and current > end:
            raise LegacyAPIError(400, f"投稿已于 {rfc3339_from_epoch(end)} 截止")
        if req.images:
            raise LegacyAPIError(400, "本提问箱不支持图片上传")

        asked_at = now_epoch()
        filter_result = keyword_filter(text, settings.filtered_keywords)
        deleted_at = asked_at if filter_result.soft_delete else None
        ip = resolve_client_ip(request, settings) if settings.geo_enabled else None
        inserted = request.app.state.db.insert_question(
            {"uuid": principal.uuid, "owner": req.owner, "type": req.type, "text": text, "asked_at": asked_at},
            deleted_at=deleted_at,
            ip=ip,
        )
        if not inserted:
            raise LegacyAPIError(409, "提交失败，错误信息：no row inserted，请联系网站管理员")
        if settings.geo_enabled and ip:
            asyncio.create_task(lookup_and_store(request.app.state.db, settings, ip))
        return {"uuid": principal.uuid, "asked_at": rfc3339_from_epoch(asked_at)}

    @app.get("/owner")
    async def owner_info(request: Request) -> dict[str, str]:
        principal = require_admin(request)
        return {"owner": principal.uuid}

    @app.post("/owner/questions")
    async def list_questions(request: Request) -> dict[str, Any]:
        require_admin(request)
        payload = await read_body(request, "投稿")
        req: ListQuestionsRequest = parse_model(ListQuestionsRequest, payload, "投稿")
        settings: Settings = request.app.state.settings
        _validate_question_type(settings, req.owner, req.type)
        allowed_sort = {"asked_at": "asked_at", "word_count": "word_count"}
        if req.order_params.by not in allowed_sort:
            raise LegacyAPIError(400, f"不支持的排序字段 {req.order_params.by}")
        page_size = req.page_size if req.page_size > 0 else 20
        page = req.page if req.page > 0 else 1
        due_after = now_epoch() - max(req.day_limit, 0) * 24 * 60 * 60
        questions, total = request.app.state.db.list_questions(
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
        )
        return {"questions": questions, "total": total, "page_size": page_size, "page": page}

    @app.get("/owner/questions/{uuid}")
    async def owner_question_detail(request: Request, uuid: str) -> dict[str, Any]:
        require_admin(request)
        question = request.app.state.db.get_question(
            uuid,
            with_visit=True,
            include_geo=request.app.state.settings.geo_enabled,
            include_deleted=False,
        )
        if question is None:
            raise LegacyAPIError(404, "投稿不存在")
        return question

    @app.put("/owner/questions/{uuid}/answer")
    async def answer_question(request: Request, uuid: str) -> Response:
        require_admin(request)
        payload = await read_body(request, "投稿")
        req: AnswerQuestionRequest = parse_model(AnswerQuestionRequest, payload, "投稿")
        ok = request.app.state.db.update_answer(req.uuid or uuid, req.answer, req.answered_by, now_epoch())
        if not ok:
            raise LegacyAPIError(404, "投稿不存在或已过期销毁")
        return Response(status_code=200)

    @app.put("/owner/questions/{uuid}/mark")
    async def mark_question(request: Request, uuid: str) -> Response:
        require_admin(request)
        payload = await read_body(request, "标记")
        req: UpdateQuestionMarkRequest = parse_model(UpdateQuestionMarkRequest, payload, "标记")
        _validate_question_type(request.app.state.settings, req.owner, req.type)
        ok = request.app.state.db.update_mark(uuid, now_epoch() if req.mark else None)
        if not ok:
            raise LegacyAPIError(404, "投稿不存在或已标记")
        return Response(status_code=200)

    @app.delete("/owner/questions/{uuid}/delete")
    async def delete_question(request: Request, uuid: str) -> Response:
        require_admin(request)
        ok = request.app.state.db.mark_deleted(uuid, now_epoch())
        if not ok:
            raise LegacyAPIError(404, "投稿不存在或已过期销毁")
        return Response(status_code=200)

    return app
