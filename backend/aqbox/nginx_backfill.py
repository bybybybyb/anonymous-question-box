from __future__ import annotations

import gzip
import json
import re
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import Settings
from .db import Database
from .geo import PROVIDER, lookup_region, parse_region, should_lookup
from .timeutil import now_epoch

ACCESS_LOG_RE = re.compile(
    r"^(?P<remote>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] "
    r'"(?P<method>\S+) (?P<path>\S+) (?P<proto>[^"]+)" '
    r"(?P<status>\d{3}) \S+ "
    r'"(?P<referer>(?:[^"\\]|\\.)*)" "(?P<agent>(?:[^"\\]|\\.)*)" "(?P<xff>(?:[^"\\]|\\.)*)"'
)

DEFAULT_SUBMIT_PATHS = {"/api/questions/submit", "/questions/submit"}


@dataclass(frozen=True, slots=True)
class AccessLogRow:
    ip: str
    happened_at: int
    method: str
    path: str
    status: int
    user_agent: str
    source: str
    line_no: int


@dataclass(frozen=True, slots=True)
class SubmitLogEvent:
    ip: str
    happened_at: int
    user_agent: str
    source: str
    line_no: int
    has_followup_get: bool = False


@dataclass(frozen=True, slots=True)
class QuestionCandidate:
    uuid: str
    asked_at: int
    text_preview: str


@dataclass(frozen=True, slots=True)
class BackfillMatch:
    uuid: str
    ip: str
    asked_at: int
    happened_at: int
    source: str
    line_no: int
    delta_seconds: int
    text_preview: str
    has_followup_get: bool


@dataclass(slots=True)
class BackfillReport:
    total_lines: int = 0
    submit_events: int = 0
    with_followup_get: int = 0
    skipped_private_ip: int = 0
    parse_errors: int = 0
    no_candidate: int = 0
    ambiguous: int = 0
    matched: int = 0
    applied: int = 0
    geo_inserted: int = 0
    geo_skipped: int = 0
    geo_failed: int = 0
    sample_matches: list[dict[str, Any]] | None = None
    sample_ambiguous: list[dict[str, Any]] | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2, sort_keys=True)


RegionLookup = Callable[[str, Settings], str | None]


def iter_log_files(paths: Iterable[str]) -> Iterator[Path]:
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            yield from sorted(candidate for candidate in path.iterdir() if candidate.name.startswith("access.log"))
        else:
            yield path


def _open_text(path: Path) -> Iterator[str]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
            yield from fh
        return
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        yield from fh


def parse_access_row(line: str, *, source: str, line_no: int) -> AccessLogRow:
    match = ACCESS_LOG_RE.match(line.rstrip("\n"))
    if match is None:
        raise ValueError("unrecognized nginx access log line")
    happened_at = int(datetime.strptime(match.group("time"), "%d/%b/%Y:%H:%M:%S %z").timestamp())
    return AccessLogRow(
        ip=match.group("remote"),
        happened_at=happened_at,
        method=match.group("method"),
        path=match.group("path"),
        status=int(match.group("status")),
        user_agent=match.group("agent"),
        source=source,
        line_no=line_no,
    )


def _is_submit_row(row: AccessLogRow, submit_paths: set[str]) -> bool:
    return row.method == "POST" and row.path in submit_paths and row.status == 200


def _is_followup_get(row: AccessLogRow) -> bool:
    return row.method == "GET" and row.path == "/api/questions/question" and row.status == 200


def collect_submit_events(
    paths: Iterable[str],
    *,
    submit_paths: set[str] | None = None,
    followup_window_seconds: int = 2,
) -> tuple[list[SubmitLogEvent], BackfillReport]:
    """Collect successful submit requests, optionally confirmed by follow-up question reads."""
    report = BackfillReport(sample_matches=[], sample_ambiguous=[])
    events: list[SubmitLogEvent] = []
    allowed_paths = submit_paths or DEFAULT_SUBMIT_PATHS
    for path in iter_log_files(paths):
        for line_no, line in enumerate(_open_text(path), start=1):
            report.total_lines += 1
            try:
                row = parse_access_row(line, source=str(path), line_no=line_no)
            except ValueError:
                report.parse_errors += 1
                continue
            if _is_submit_row(row, allowed_paths):
                report.submit_events += 1
                if not should_lookup(row.ip):
                    report.skipped_private_ip += 1
                    continue
                events.append(
                    SubmitLogEvent(
                        ip=row.ip,
                        happened_at=row.happened_at,
                        user_agent=row.user_agent,
                        source=row.source,
                        line_no=row.line_no,
                    )
                )
                continue
            if _is_followup_get(row):
                for index in range(len(events) - 1, -1, -1):
                    event = events[index]
                    delta = row.happened_at - event.happened_at
                    if delta < 0:
                        continue
                    if delta > followup_window_seconds:
                        break
                    if event.ip == row.ip and event.user_agent == row.user_agent and event.source == row.source:
                        if not event.has_followup_get:
                            report.with_followup_get += 1
                        events[index] = replace(event, has_followup_get=True)
                        break
    return events, report


def _candidate_rows(db: Database, happened_at: int, window_seconds: int) -> list[QuestionCandidate]:
    rows = db.conn.execute(
        """
        SELECT uuid, asked_at, question
        FROM question
        WHERE (ip IS NULL OR ip = '')
          AND asked_at BETWEEN ? AND ?
        ORDER BY asked_at ASC, id ASC
        """,
        (happened_at - window_seconds, happened_at + window_seconds),
    ).fetchall()
    return [
        QuestionCandidate(
            uuid=row["uuid"],
            asked_at=int(row["asked_at"]),
            text_preview=(row["question"] or "")[:40],
        )
        for row in rows
    ]


def plan_backfill(
    db: Database,
    events: list[SubmitLogEvent],
    *,
    window_seconds: int = 1,
    sample_limit: int = 10,
) -> tuple[list[BackfillMatch], BackfillReport]:
    """Match log events to exactly one question timestamp; ambiguous clusters are skipped."""
    report = BackfillReport(
        total_lines=0,
        submit_events=len(events),
        with_followup_get=sum(1 for event in events if event.has_followup_get),
        sample_matches=[],
        sample_ambiguous=[],
    )
    event_candidates = [(event, _candidate_rows(db, event.happened_at, window_seconds)) for event in events]
    unique_candidate_counts = Counter(candidates[0].uuid for _, candidates in event_candidates if len(candidates) == 1)
    matches: list[BackfillMatch] = []

    for event, candidates in event_candidates:
        if not candidates:
            report.no_candidate += 1
            continue
        if len(candidates) != 1 or unique_candidate_counts[candidates[0].uuid] != 1:
            report.ambiguous += 1
            if report.sample_ambiguous is not None and len(report.sample_ambiguous) < sample_limit:
                report.sample_ambiguous.append(
                    {
                        "event": asdict(event),
                        "candidates": [asdict(candidate) for candidate in candidates[:5]],
                    }
                )
            continue
        candidate = candidates[0]
        match = BackfillMatch(
            uuid=candidate.uuid,
            ip=event.ip,
            asked_at=candidate.asked_at,
            happened_at=event.happened_at,
            source=event.source,
            line_no=event.line_no,
            delta_seconds=candidate.asked_at - event.happened_at,
            text_preview=candidate.text_preview,
            has_followup_get=event.has_followup_get,
        )
        matches.append(match)
        if report.sample_matches is not None and len(report.sample_matches) < sample_limit:
            report.sample_matches.append(asdict(match))

    report.matched = len(matches)
    return matches, report


def apply_backfill(
    db: Database,
    settings: Settings,
    matches: list[BackfillMatch],
    *,
    region_lookup: RegionLookup | None = None,
) -> BackfillReport:
    """Write matched IPs and lazily seed ip2region rows when lookup data is available."""
    report = BackfillReport(matched=len(matches))
    with db.lock:
        for match in matches:
            cur = db.conn.execute(
                "UPDATE question SET ip = ? WHERE uuid = ? AND (ip IS NULL OR ip = '')",
                (match.ip, match.uuid),
            )
            report.applied += cur.rowcount
        db.conn.commit()

    for ip in sorted({match.ip for match in matches}):
        if db.get_ip_geo(ip) is not None:
            report.geo_skipped += 1
            continue
        raw_region = (region_lookup or lookup_region)(ip, settings)
        if not raw_region:
            report.geo_skipped += 1
            continue
        parsed = parse_region(raw_region)
        if parsed is None:
            report.geo_failed += 1
            continue
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
        report.geo_inserted += 1
    return report
