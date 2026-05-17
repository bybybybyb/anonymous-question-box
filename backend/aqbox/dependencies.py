from __future__ import annotations

from typing import cast

from fastapi import Request

from .auth import Principal
from .config import Settings
from .db import Database
from .repositories import OpsRepository, SubmissionRepository, VisitRepository
from .services import (
    AuthService,
    GeoService,
    ModerationService,
    OpsService,
    OwnerConsoleService,
    ProfileService,
    SubmissionService,
    VisitService,
)
from .settings_provider import SettingsProvider


def settings_provider(request: Request) -> SettingsProvider:
    return cast(SettingsProvider, request.app.state.settings_provider)


def current_settings(request: Request) -> Settings:
    provider = settings_provider(request)
    settings = provider.current()
    request.app.state.settings = settings
    db = database(request)
    if settings.geo_enabled and not db.geo_enabled:
        db.migrate_geo()
        db.conn.commit()
        db.geo_enabled = True
    return settings


def database(request: Request) -> Database:
    return cast(Database, request.app.state.db)


def auth_service(request: Request) -> AuthService:
    return cast(AuthService, request.app.state.auth_service)


def require_asker(request: Request) -> Principal:
    return auth_service(request).require_asker(current_settings(request), request.headers.get("authorization"))


def require_owner(request: Request) -> Principal:
    return auth_service(request).require_owner(current_settings(request), request.headers.get("authorization"))


def profile_service(request: Request) -> ProfileService:
    return cast(ProfileService, request.app.state.profile_service)


def submission_service(request: Request) -> SubmissionService:
    return cast(SubmissionService, request.app.state.submission_service)


def owner_console_service(request: Request) -> OwnerConsoleService:
    return cast(OwnerConsoleService, request.app.state.owner_console_service)


def visit_service(request: Request) -> VisitService:
    return cast(VisitService, request.app.state.visit_service)


def ops_service(request: Request) -> OpsService:
    return cast(OpsService, request.app.state.ops_service)


def build_services(db: Database, provider: SettingsProvider) -> dict[str, object]:
    submission_repo = SubmissionRepository(db)
    visit_repo = VisitRepository(db)
    ops_repo = OpsRepository(db)
    moderation = ModerationService()
    geo = GeoService()
    return {
        "auth_service": AuthService(),
        "profile_service": ProfileService(),
        "visit_service": VisitService(visit_repo, provider),
        "submission_service": SubmissionService(submission_repo, moderation, geo),
        "owner_console_service": OwnerConsoleService(submission_repo),
        "ops_service": OpsService(ops_repo, provider),
    }
