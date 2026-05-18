from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from .dependencies import (
    current_settings,
    ops_service,
    owner_console_service,
    owner_query_rate_limiter,
    profile_service,
    require_asker,
    require_owner,
    submission_service,
    visit_service,
)
from .legacy import parse_model, read_body
from .schemas import AnswerQuestionRequest, ListQuestionsRequest, SubmitQuestionRequest, UpdateQuestionMarkRequest

router = APIRouter()


@router.get("/checkalive")
async def checkalive() -> PlainTextResponse:
    return PlainTextResponse("pong")


@router.get("/ops/health")
async def ops_health(request: Request) -> JSONResponse:
    status_code, payload = ops_service(request).health(request.app.state.visit_worker_task)
    return JSONResponse(payload, status_code=status_code)


@router.get("/ops/config")
async def ops_config(request: Request) -> dict[str, Any]:
    require_owner(request)
    return ops_service(request).config_status()


@router.get("/profiles")
async def profiles(request: Request) -> dict[str, Any]:
    return profile_service(request).public_profiles(current_settings(request))


@router.get("/new")
async def new_submission_token(request: Request) -> dict[str, str]:
    settings = current_settings(request)
    token = request.app.state.auth_service.new_asker_token(settings)
    return {"token": token}


@router.get("/questions/question")
async def get_submission(request: Request) -> dict[str, Any]:
    principal = require_asker(request)
    return submission_service(request).get_for_asker(principal.uuid, visit_service(request))


@router.post("/questions/submit")
async def submit_submission(request: Request) -> dict[str, str]:
    settings = current_settings(request)
    principal = require_asker(request)
    payload = await read_body(request, "投稿")
    req: SubmitQuestionRequest = parse_model(SubmitQuestionRequest, payload, "投稿")
    return submission_service(request).submit(request, principal, req, settings)


@router.get("/owner")
async def owner_info(request: Request) -> dict[str, str]:
    principal = require_owner(request)
    return {"owner": principal.uuid}


@router.post("/owner/questions")
async def list_submissions(request: Request) -> dict[str, Any]:
    settings = current_settings(request)
    principal = require_owner(request)
    if not owner_query_rate_limiter(request).allow(principal.uuid):
        return JSONResponse({"error": "请求过于频繁"}, status_code=429)  # type: ignore[return-value]
    payload = await read_body(request, "投稿")
    req: ListQuestionsRequest = parse_model(ListQuestionsRequest, payload, "投稿")
    return owner_console_service(request).list_submissions(req, settings)


@router.get("/owner/questions/{uuid}")
async def owner_submission_detail(request: Request, uuid: str) -> dict[str, Any]:
    settings = current_settings(request)
    require_owner(request)
    return owner_console_service(request).detail(uuid, settings)


@router.put("/owner/questions/{uuid}/answer")
async def answer_submission(request: Request, uuid: str) -> Response:
    require_owner(request)
    payload = await read_body(request, "投稿")
    req: AnswerQuestionRequest = parse_model(AnswerQuestionRequest, payload, "投稿")
    owner_console_service(request).answer(uuid, req)
    return Response(status_code=200)


@router.put("/owner/questions/{uuid}/mark")
async def mark_submission(request: Request, uuid: str) -> Response:
    settings = current_settings(request)
    require_owner(request)
    payload = await read_body(request, "标记")
    req: UpdateQuestionMarkRequest = parse_model(UpdateQuestionMarkRequest, payload, "标记")
    owner_console_service(request).mark(uuid, req, settings)
    return Response(status_code=200)


@router.delete("/owner/questions/{uuid}/delete")
async def delete_submission(request: Request, uuid: str) -> Response:
    require_owner(request)
    owner_console_service(request).delete(uuid)
    return Response(status_code=200)
