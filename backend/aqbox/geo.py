from __future__ import annotations

import ipaddress
import json
from typing import Any
from urllib.parse import urlencode

import httpx
from fastapi import Request

from .config import Settings
from .db import Database
from .timeutil import now_epoch


def _trusted_proxy(peer: str | None, settings: Settings) -> bool:
    if not peer:
        return False
    try:
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return False
    for cidr in settings.trusted_proxy_cidrs:
        try:
            if peer_ip in ipaddress.ip_network(cidr, strict=False):
                return True
        except ValueError:
            continue
    return False


def _first_forwarded_for(value: str | None) -> str | None:
    if not value:
        return None
    candidate = value.split(",", 1)[0].strip()
    return candidate or None


def _valid_ip(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return str(ipaddress.ip_address(value.strip()))
    except ValueError:
        return None


def resolve_client_ip(request: Request, settings: Settings) -> str:
    peer = request.client.host if request.client else ""
    if _trusted_proxy(peer, settings):
        return (
            _valid_ip(request.headers.get("x-real-ip"))
            or _valid_ip(_first_forwarded_for(request.headers.get("x-forwarded-for")))
            or _valid_ip(peer)
            or ""
        )
    return _valid_ip(peer) or ""


def should_lookup(ip: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (parsed.is_private or parsed.is_reserved or parsed.is_loopback or parsed.is_link_local or parsed.is_multicast)


async def lookup_and_store(db: Database, settings: Settings, ip: str, *, client: httpx.AsyncClient | None = None) -> None:
    if not settings.geo_enabled or not should_lookup(ip):
        return
    if db.get_ip_geo(ip) is not None:
        return

    close_client = client is None
    client = client or httpx.AsyncClient(timeout=settings.geo_timeout_seconds)
    try:
        url = f"{settings.pconline_geo_url}?{urlencode({'ip': ip, 'json': 'true'})}"
        resp = await client.get(url)
        body = resp.content.decode("gbk", errors="strict")
        parsed: dict[str, Any] = json.loads(body)
        db.insert_ip_geo(
            {
                "ip": ip,
                "province": parsed.get("pro", ""),
                "city": parsed.get("city", ""),
                "region": parsed.get("region", ""),
                "addr": parsed.get("addr", ""),
                "looked_up_at": now_epoch(),
            }
        )
    except Exception:
        return
    finally:
        if close_client:
            await client.aclose()
