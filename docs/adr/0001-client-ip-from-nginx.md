# Client IP from nginx headers

Production serves the API behind nginx, which overwrites `X-Real-IP` and `X-Forwarded-For`. The Python backend (Phase 2) must trust those headers only when the direct socket peer is in a configured trusted proxy allowlist. When the peer is trusted, read `X-Real-IP` first, then the first `X-Forwarded-For` hop, then the socket peer. When the peer is not trusted, ignore forwarded headers and use only the socket peer.

`origin/main` Go does not store client IP (`question` has no `ip` column). Phase 2 adds the column and captures IP on submit; no backfill of historical IPs.

Recommended nginx location headers:

```nginx
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```
