# API Notes

Implemented endpoint groups:

- `/auth`: Telegram initData auth, refresh, logout.
- `/uploads`: signed upload URL, complete, Telegram file_id, status, retry, delete.
- `/items`: wardrobe CRUD and item actions; `GET /items/{id}/image` streams the private photo for authenticated owners.
- `/looks`: LookCard, favorites and similar generation.
- `/outfits`: recommendations, prompt generation, anchored generation, rating and selection.
- `/ai`: image analysis task lifecycle and usage.
- `/designer`: wardrobe gaps, missing selected items, safe look rating and `POST /designer/chat` — the AI stylist chat that answers in Russian and persists proposed outfits (`outfit_id`, `outfit_item_ids`, explanation, score) built strictly from the user's wardrobe.
- `/weather`: authenticated Open-Meteo daily summary by latitude/longitude with Redis cache.
- `/marketplace`: similar item search.
- `/wishlist`: wishlist CRUD.
- `/style-dna`, `/rules`, `/wardrobe/health`: taste and explainability features.
- `/privacy`, `/purchase-simulator`, `/capsules`, `/challenges`, `/share`: privacy and v0.2.2 advanced flows.
- `/billing/plans`: public provider-neutral plan catalog with monthly AI/avatar/try-on limits.
- `/billing/me`: authenticated effective plan, grant source, expiry and feature set.
- `/billing/promos/redeem`: authenticated HMAC-backed promo redemption.
- `/avatar/profile`: consented profile and normalized measurements; `DELETE` revokes consent and deletes derivatives.
- `/avatar/generate`: asynchronous premium avatar generation.
- `/avatar/image`: authenticated avatar image response.
- `/avatar/try-ons`: asynchronous multi-garment try-on jobs.
- `/avatar/try-ons/{id}` and `/avatar/try-ons/{id}/image`: authenticated status/output.

Runtime user flows are authenticated and user-scoped. Wardrobe, wishlist, style, upload, AI, privacy and outfit
state is persisted in PostgreSQL, with private image bytes stored in S3-compatible object storage. Endpoints that need
external production providers return explicit unavailable errors until their provider adapter and secrets are configured.

`POST /uploads/file` optionally accepts multipart `selection_json`:

```json
{
  "kind": "rectangle",
  "source": "user",
  "x": 0.2,
  "y": 0.1,
  "width": 0.6,
  "height": 0.8
}
```

Coordinates are normalized to the original preview. The Mini App crops locally before upload; metadata is retained as
selection provenance. Billable analysis is reserved transactionally before enqueue and retries reuse the same request.

Real payments are not exposed: `ENABLE_BILLING_PAYMENTS=false` keeps plan actions disabled until a signed, idempotent
payment provider integration exists.

## Local Codex runner transport

The following server-to-workstation transport routes are deliberately excluded from OpenAPI and are not user APIs:

- `POST /internal/codex-runner/claim` — authenticated long poll; returns `204` when no job exists;
- `POST /internal/codex-runner/jobs/{id}/complete` — completes an active job with bounded JSON;
- `POST /internal/codex-runner/jobs/{id}/fail` — records a safe error code for an active job;
- `POST /internal/codex-runner/heartbeat` — optional explicit heartbeat.

All require `Authorization: Bearer <CODEX_RUNNER_TOKEN>`. The token must contain at least 32 characters. Jobs are
accepted only while their Redis record is active, payloads are capped, and no prompt, image, token or raw model output
is written to request logs.
