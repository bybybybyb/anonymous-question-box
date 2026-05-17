from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SubmittedImageRef(BaseModel):
    model_config = ConfigDict(extra="ignore")

    image_id: str = ""
    order: int = 0
    filename: str = ""


class SubmitQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    owner: str = ""
    type: str = ""
    text: str = ""
    images: list[SubmittedImageRef] | None = None


class OrderParams(BaseModel):
    model_config = ConfigDict(extra="ignore")

    by: str = "asked_at"
    reversed: bool = True


class ListQuestionsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    owner: str = ""
    type: str = ""
    order_params: OrderParams = Field(default_factory=OrderParams)
    day_limit: int = 0
    marked: bool = False
    reply_status: int = 0
    page_size: int = 20
    page: int = 1
    include_moderated: bool = False
    moderation_source: str | None = None


class AnswerQuestionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    uuid: str = ""
    answer: str = ""
    answered_by: str = ""


class UpdateQuestionMarkRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    mark: bool = False
    owner: str = ""
    type: str = ""


def model_from_payload(model: type[BaseModel], payload: Any) -> BaseModel:
    return model.model_validate(payload if isinstance(payload, dict) else {})
