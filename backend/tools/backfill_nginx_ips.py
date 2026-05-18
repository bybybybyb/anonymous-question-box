#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import asdict

from aqbox.config import Settings, load_settings
from aqbox.db import Database
from aqbox.nginx_backfill import apply_backfill, collect_submit_events, plan_backfill


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill question.ip from nginx submit access logs.")
    parser.add_argument("--db", required=True, help="SQLite database path.")
    parser.add_argument("--log", action="append", required=True, help="Nginx access log file, .gz file, or directory. Repeatable.")
    parser.add_argument("--config", help="Backend config path for ip2region xdb settings.")
    parser.add_argument("--ipv4-xdb", default="", help="Override IPv4 ip2region xdb path.")
    parser.add_argument("--ipv6-xdb", default="", help="Override IPv6 ip2region xdb path.")
    parser.add_argument("--cache-policy", choices=["file", "vectorIndex", "content"], help="Override ip2region cache policy.")
    parser.add_argument("--window-seconds", type=int, default=1, help="Timestamp match window around question.asked_at.")
    parser.add_argument("--followup-window-seconds", type=int, default=2, help="Window for same-IP post-submit GET confidence marker.")
    parser.add_argument(
        "--require-followup-get",
        action="store_true",
        help="Only match submit events followed by GET /api/questions/question.",
    )
    parser.add_argument("--sample-limit", type=int, default=10, help="Number of sample matches/ambiguities to print.")
    parser.add_argument("--apply", action="store_true", help="Actually update question.ip and ip_geo. Defaults to dry-run.")
    return parser.parse_args()


def build_settings(args: argparse.Namespace) -> Settings:
    settings = load_settings(args.config) if args.config else Settings()
    settings.geo_enabled = True
    if args.ipv4_xdb:
        settings.ip2region_ipv4_xdb_path = args.ipv4_xdb
    if args.ipv6_xdb:
        settings.ip2region_ipv6_xdb_path = args.ipv6_xdb
    if args.cache_policy:
        settings.ip2region_cache_policy = args.cache_policy
    return settings


def main() -> int:
    args = parse_args()
    settings = build_settings(args)
    db = Database(args.db, geo_enabled=True)
    db.bootstrap()

    events, parse_report = collect_submit_events(args.log, followup_window_seconds=args.followup_window_seconds)
    if args.require_followup_get:
        events = [event for event in events if event.has_followup_get]
    matches, match_report = plan_backfill(db, events, window_seconds=args.window_seconds, sample_limit=args.sample_limit)
    output = {
        "mode": "apply" if args.apply else "dry-run",
        "parse": asdict(parse_report),
        "match": asdict(match_report),
    }
    if args.apply:
        output["apply"] = asdict(apply_backfill(db, settings, matches))
    print_json(output)
    return 0


def print_json(value: object) -> None:
    import json

    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
