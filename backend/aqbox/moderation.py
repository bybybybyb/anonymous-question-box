from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from .config import LLMModerationPolicy


@dataclass(slots=True)
class FilterResult:
    blocked: bool
    source: str | None = None
    reason: str | None = None


def keyword_filter(text: str, keywords: list[str]) -> FilterResult:
    """Keyword hits are stealth moderation blocks with no matched keyword stored."""
    for keyword in keywords:
        keyword = str(keyword)
        if keyword and keyword in text:
            return FilterResult(blocked=True, source="keyword", reason="keyword")
    return FilterResult(blocked=False)


def llm_policy_for(settings: Any, owner: str, qtype: str) -> LLMModerationPolicy | None:
    """Return typed LLM policy only when global and owner/type enablement both opt in."""
    llm_moderation = getattr(settings, "llm_moderation", None)
    if llm_moderation is None:
        return None
    return cast("LLMModerationPolicy | None", llm_moderation.policy_for(owner, qtype))


def purge_due_raw_audit_fields(db: Any, now_epoch: int) -> int:
    """Purge raw LLM payloads while retaining permanent moderation metadata."""
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
