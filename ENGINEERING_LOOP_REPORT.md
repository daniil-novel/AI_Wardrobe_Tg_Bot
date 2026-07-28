# Engineering loop report

Дата: 2026-07-28. Метод: bounded evidence-first loop, максимум три итерации на epic.

## Epic 1 — user-controlled recognition

### OBSERVE

Upload отправлял всё фото; пользователь не мог исключить манекены, фоновые рейлы и других людей.

### HYPOTHESIZE

Client-side crop подтверждённой области уменьшит false-positive background garments без backend latency.

### PLAN / ACT

- preview до upload;
- proposed central person rectangle;
- pointer drag, whole-photo, undo/redo/reset;
- keyboard move/resize;
- browser canvas crop;
- normalized geometry/provenance в `image_selections`;
- сохранение совместимости multipart endpoint.

### VERIFY

- unit validation координат;
- TypeScript typecheck и две builds;
- Chromium synthetic fitting-room scenario;
- drag исключил rack/mannequins, undo/redo/full/reset сработали.

### CRITIQUE

Это rectangle, а не semantic Photoshop mask. Нет local segmentation, brush add/subtract и zoom/pan.

### DECIDE

`ACCEPTED` для исходного сценария контролируемой области; `PARTIAL` для расширенного mask contract.

## Epic 2 — consent-safe avatar and try-on

### OBSERVE

Не было нормализованного профиля, consent lifecycle, avatar output и try-on jobs.

### HYPOTHESIZE

Отдельные profile/measurement/job entities позволят подключить provider без скрытого хранения биометрии и без fake results.

### PLAN / ACT

- `avatar_profiles`, `avatar_measurements`, `try_on_jobs`, `try_on_items`;
- profile/get/update/revoke/generate routes;
- real OpenRouter composite generation;
- neutral fitted opaque studio basics;
- explicit non-beautification prompt;
- premium feature gate;
- S3 deletion avatar/try-on derivatives on revoke;
- honest `provider_not_configured`.

### VERIFY

- route/privacy tests;
- visual Studio walkthrough;
- worker/type checks;
- no private image/prompt payload in operational metrics.

### CRITIQUE

Live generation quality and anthropometric fidelity are not validated. A garment crop may be unsuitable as face/full-body reference. Separate reference capture remains P1.

### DECIDE

`ACCEPTED` for domain, consent, deletion and provider wiring. `BLOCKED` for “один в один” quality claim.

## Epic 3 — subscriptions, quotas and promo

### OBSERVE

Billing models existed, but effective entitlements/promo UI were incomplete. Direct upload could bypass the displayed AI quota; one path could double-count usage.

### HYPOTHESIZE

Server-side grants plus transactionally reserved billable requests make trial/premium behavior auditable without enabling payments.

### PLAN / ACT

- Free/Premium/Pro catalog and preliminary prices;
- `GET /billing/me`, `POST /billing/promos/redeem`;
- HMAC promo storage, expiry, max redemption and unique user redemption;
- effective plan from subscription/promo;
- user-row `FOR UPDATE` quota lock;
- calendar-month analysis/avatar/try-on limits;
- idempotent upload analysis reservation;
- failed requests release quota slot;
- subscription/open builds;
- safe promo creation script.

### VERIFY

- hashing/redemption/expiry/idempotency/quota tests;
- DB integrity constraints in migration 0004;
- different build hashes;
- UI cards, promo and locked/unlocked copy.

### CRITIQUE

Payment provider/webhook and actual COGS ingestion are absent. После восстановления Docker promo был записан и
прочитан на PostgreSQL 16; отдельный smoke-code успешно активирован через authenticated HTTP endpoint, после чего
smoke user/redemption/code были удалены. Пользовательский 24-hour code остался неиспользованным.

### DECIDE

`ACCEPTED` as payment-disabled commercial preview. One-day code: `VERIFIED` в изолированной QA DB. Production billing:
`BLOCKED`.

## Epic 4 — UX, performance and observability

### OBSERVE

Mobile overflow appeared in nav, wardrobe chips and tariff grid. Metrics endpoint exposed only app info. No measured reason for Go rewrite.

### HYPOTHESIZE

Responsive CSS fixes and lightweight route metrics improve operability without adding a heavy frontend/runtime dependency.

### PLAN / ACT

- six-column safe bottom nav;
- scrollbar suppression;
- stacked mobile plans and full-width promo controls;
- Telegram haptic version gate;
- request/status counter and duration histogram;
- synthetic latency harness;
- two bundle measurements.

### VERIFY

- every tab opened at 390×844;
- no critical horizontal overflow after fixes;
- TestClient p95 6.8–7.9 ms on public routes;
- 115 tests passed with 67.91% coverage in the final control run.

### CRITIQUE

In-process benchmark is not load evidence. No network/DB/queue/provider profile and no production trace backend.

### DECIDE

`ACCEPTED` as local baseline. Go rewrite `REJECTED`.

## External review and delegation

- Три requested subagent направления были запущены, но завершились provider `403` после потери сети; их выводы не использованы как доказательство.
- Claude Code Opus read-only review после reset завершился успешно. Подтверждённые замечания применены; raw review сохранён в `docs/reviews/CLAUDE_DESIGN_REVIEW.md`.

## Retained decisions

1. Не выдавать mock/fallback за AI output.
2. Face/body data обрабатывается только с explicit consent.
3. Payments остаются выключены до real provider + COGS + webhook.
4. Failed provider/queue request не должен отнимать месячный slot.
5. Python сохраняется; оптимизируются измеренные I/O paths.
6. Deployment без target/health/rollback не объявляется выполненным.

## Late infrastructure verification

- PostgreSQL 16 fresh DB: `upgrade → downgrade base → upgrade head` прошёл, финальный revision
  `0004_commercial_integrity`.
- Upgrade realism: committed v0.3.1/HEAD создал 27-table baseline; current `0002–0004` обновили его до 34 tables и
  корректного head.
- QA API с PostgreSQL + Redis: `/health/ready` вернул HTTP 200.
- Promo HTTP smoke: `premium`, one active DB redemption, expiry present; smoke data удалены.
- Production HTTP root/health/ready вернули 200, но SSH дважды остановился на banner timeout, поэтому backup и
  rollback нельзя было подтвердить и deployment не выполнялся.
