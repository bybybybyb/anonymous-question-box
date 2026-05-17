from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FilterResult:
    soft_delete: bool
    source: str | None = None
    reason: str | None = None


def keyword_filter(text: str, keywords: list[str]) -> FilterResult:
    for keyword in keywords:
        keyword = str(keyword)
        if keyword and keyword in text:
            return FilterResult(soft_delete=True, source="keyword", reason="keyword")
    return FilterResult(soft_delete=False)


def llm_policy_for(settings: Any, owner: str, qtype: str) -> dict[str, Any] | None:
    cfg = getattr(settings, "llm_filter", {}) or {}
    per_owner = cfg.get("owners", {}).get(owner, {})
    per_type = per_owner.get("question_types", {}).get(qtype)
    if per_type and per_type.get("prompt"):
        return dict(per_type)
    return None


def purge_due_raw_audit_fields(db: Any, now_epoch: int) -> int:
    if not getattr(db, "moderation_schema", False):
        return 0
    with db.lock:
        cur = db.conn.execute(
            """
            UPDATE question_moderation_audit
            SET raw_prompt = NULL,
                raw_request = NULL,
                raw_response = NULL,
                purged_at = ?
            WHERE purge_after IS NOT NULL
              AND purge_after <= ?
              AND purged_at IS NULL
            """,
            (now_epoch, now_epoch),
        )
        db.conn.commit()
        return int(cur.rowcount)
