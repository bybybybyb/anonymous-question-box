# Anonymous Question Box

A multi-owner anonymous Q&A site where visitors submit text questions and owners answer from an admin console. Each owner has one or more **question types** (separate boxes with different limits and themes).

## Implementation Status

The canonical backend is the FastAPI/Pydantic implementation in `backend/`.

The original Go backend has been moved to `legacy/go_backend/` and is deprecated. Use it only as historical reference when investigating legacy behavior. Do not add new backend features there.

## Language

**Owner**:
A configured personality or channel (e.g. merry, umy) that owns one or more question types.
_Avoid_: profile, tenant

**Question type**:
A named submission box under an owner (e.g. normal, snail) with its own rune limit, theme, and optional time window.
_Avoid_: category, channel

**Submission**:
A single anonymous question stored in the database, identified by a stable **submission UUID** issued at token creation.
_Avoid_: post, ticket

**Asker**:
The anonymous visitor who holds a JWT tied to their submission UUID. Not a registered user account.
_Avoid_: user, customer

**Owner console**:
The authenticated admin view used to list, answer, mark, and delete submissions. Access requires an admin JWT (magic spell).
_Avoid_: dashboard, moderator panel

**Admin session UUID**:
The subject identifier embedded in an admin JWT, returned as the JSON field `owner` on `GET /owner`. This is not an **Owner** slug (slug appears in routes and list/submit bodies only).
_Avoid_: owner slug, profile id

**Soft-delete**:
A submission hidden from the owner list by setting `deleted_at`, while the asker may still see it. Used for keyword filtering and (planned) LLM moderation.
_Avoid_: hard delete, ban

**Client IP**:
The visitor IP stored on submit, intended to reflect the real client behind nginx via `X-Real-IP`.
_Avoid_: server IP, proxy IP

**IP location label**:
The human-readable location string returned to admins as `ip_addr`, sourced from `ip_geo.addr` in storage.
_Avoid_: geolocation object, geo JSON

## Relationships

- An **Owner** has one or more **Question types**
- Each **Submission** belongs to exactly one **Owner** and one **Question type**
- Each **Submission** may have at most one **Client IP** and one cached **IP location label**
- **Askers** authenticate with a JWT bound to their **Submission UUID**; **Owner console** uses a separate admin JWT

## Example dialogue

> **Dev:** "When a keyword filter matches, do we tell the asker?"
> **Domain expert:** "No — same as today. They get success and can still open their submission; owners never see it in the list. That's **soft-delete**, not a public rejection."

**Automated moderation**:
Keyword and/or LLM checks that may **soft-delete** a submission before owners see it.
_Avoid_: censorship, ban (unless owner manually deletes)

**Rewrite phase**:
A delivery stage for the Python backend migration — Phase 1 (backend parity, no frontend), Phase 2 (pconline geo + frontend IP display), Phase 3 (LLM moderation, deferred).
_Avoid_: sprint, milestone (unless tracking externally)

**Legacy image submission**:
A submission that still has rows in the `image` table (and possibly COS objects) from when `support_image` was true, even though Phase 1 no longer returns or accepts new images.
_Avoid_: orphaned upload, stale carousel

## Flagged ambiguities

- "Filtered" historically meant keyword **soft-delete** only; LLM moderation reuses stealth UX unless `moderation.ux=explicit`.
