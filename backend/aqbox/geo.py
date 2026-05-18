from __future__ import annotations

import ipaddress
import logging
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request
from ip2region import searcher, util  # type: ignore[import-untyped]

from .config import IP2REGION_CACHE_POLICIES, Settings
from .db import Database
from .timeutil import now_epoch

logger = logging.getLogger("aqbox.geo")
PROVIDER = "ip2region"

_searcher_lock = threading.RLock()
_searchers: dict[tuple[str, str, str], Any] = {}
_last_error_class: str | None = None
_last_error_at: int | None = None


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
    """Return the client hop for the documented single-nginx deployment."""
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
    """Resolve client IP with nginx as the trust boundary.

    Forwarded headers are accepted only when the socket peer is trusted. Production
    overwrites X-Real-IP, so that header wins before the X-Forwarded-For fallback.
    """
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
    """Skip private/reserved ranges so geo lookup is fail-open and operator-friendly."""
    try:
        parsed = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return not (parsed.is_private or parsed.is_reserved or parsed.is_loopback or parsed.is_link_local or parsed.is_multicast)


@dataclass(frozen=True, slots=True)
class ParsedRegion:
    country: str
    province: str
    city: str
    isp: str
    country_code: str
    addr: str
    raw_region: str


def _record_geo_error(exc: Exception) -> None:
    global _last_error_at, _last_error_class
    with _searcher_lock:
        _last_error_class = exc.__class__.__name__
        _last_error_at = now_epoch()
    logger.warning("ip2region lookup failed", exc_info=True)


def geo_status() -> dict[str, Any]:
    with _searcher_lock:
        return {
            "provider": PROVIDER,
            "last_error_class": _last_error_class,
            "last_error_at": _last_error_at,
        }


def _clean_region_part(value: str) -> str:
    value = value.strip()
    return "" if value in {"", "0"} else value


def parse_region(raw_region: str) -> ParsedRegion | None:
    """Parse ip2region's `Country|Province|City|ISP|CountryCode` record format."""
    parts = raw_region.split("|")
    if len(parts) != 5:
        return None
    country, province, city, isp, country_code = [_clean_region_part(part) for part in parts]
    if country_code.upper() == "CN":
        addr = "".join(part for part in (province, city) if part)
    else:
        addr = " ".join(part for part in (country, province, city) if part)
    if not addr:
        return None
    return ParsedRegion(
        country=country,
        province=province,
        city=city,
        isp=isp,
        country_code=country_code,
        addr=addr,
        raw_region=raw_region,
    )


def _xdb_path_for_ip(ip: str, settings: Settings) -> tuple[Any, str] | None:
    parsed = ipaddress.ip_address(ip)
    if parsed.version == 4:
        return util.IPv4, settings.ip2region_ipv4_xdb_path
    if not settings.ip2region_ipv6_xdb_path:
        return None
    return util.IPv6, settings.ip2region_ipv6_xdb_path


def _new_searcher(version: Any, xdb_path: str, cache_policy: str) -> Any:
    if cache_policy not in IP2REGION_CACHE_POLICIES:
        raise ValueError(f"unsupported ip2region cache policy {cache_policy}")
    path = str(Path(xdb_path).expanduser())
    util.verify_from_file(path)
    if cache_policy == "content":
        return searcher.new_with_buffer(version, util.load_content_from_file(path))
    if cache_policy == "vectorIndex":
        return searcher.new_with_vector_index(version, path, util.load_vector_index_from_file(path))
    return searcher.new_with_file_only(version, path)


def lookup_region(ip: str, settings: Settings) -> str | None:
    """Lookup an IP from configured xdb files using the configured cache policy."""
    version_and_path = _xdb_path_for_ip(ip, settings)
    if version_and_path is None:
        return None
    version, xdb_path = version_and_path
    if not xdb_path:
        return None
    cache_policy = settings.ip2region_cache_policy or "vectorIndex"
    path = str(Path(xdb_path).expanduser())
    if cache_policy in {"content", "vectorIndex"}:
        key = (version.name, path, cache_policy)
        with _searcher_lock:
            if key not in _searchers:
                _searchers[key] = _new_searcher(version, path, cache_policy)
            raw_region = _searchers[key].search(ip)
        return str(raw_region) if raw_region else None

    # file-only searchers own a file handle and do not cache index data, so keep them short-lived.
    per_lookup_searcher = _new_searcher(version, path, cache_policy)
    try:
        raw_region = per_lookup_searcher.search(ip)
    finally:
        per_lookup_searcher.close()
    return str(raw_region) if raw_region else None


async def lookup_and_store(
    db: Database,
    settings: Settings,
    ip: str,
    *,
    region_lookup: Callable[[str, Settings], str | None] | None = None,
) -> None:
    """Populate the geo cache for an IP; every lookup failure is fail-open."""
    if not settings.geo_enabled or not should_lookup(ip):
        return
    if db.get_ip_geo(ip) is not None:
        return

    try:
        raw_region = (region_lookup or lookup_region)(ip, settings)
        if not raw_region:
            return
        parsed = parse_region(raw_region)
        if parsed is None:
            return
        db.insert_ip_geo(
            {
                "ip": ip,
                "country": parsed.country,
                "province": parsed.province,
                "city": parsed.city,
                "region": "",
                "addr": parsed.addr,
                "isp": parsed.isp,
                "country_code": parsed.country_code,
                "provider": PROVIDER,
                "raw_region": parsed.raw_region,
                "looked_up_at": now_epoch(),
            }
        )
    except Exception as exc:
        _record_geo_error(exc)
        return
