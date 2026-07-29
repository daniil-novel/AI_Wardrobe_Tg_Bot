# Engineering loop report

Дата: 2026-07-29. Метод: bounded evidence-first loop, максимум три итерации на epic.

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
- 138 tests passed with 70.11% coverage in the final control run.

### CRITIQUE

In-process benchmark is not load evidence. No network/DB/queue/provider profile and no production trace backend.

### DECIDE

`ACCEPTED` as local baseline. Go rewrite `REJECTED`.

## External review and delegation

- Три requested subagent направления были запущены, но завершились provider `403` после потери сети; их выводы не использованы как доказательство.
- Claude Code Opus read-only review после reset завершился успешно. Подтверждённые замечания применены; исходный
  локальный review сохранён в `docs/reviews/CLAUDE_DESIGN_REVIEW.md`.
- Повторный Opus post-deploy review прошёл по 21 production screenshot и JSON trace. P1 с отсутствующими
  иллюстрациями сохранённых образов исправлен и повторно проверен; отчёт:
  `docs/reviews/CLAUDE_POSTDEPLOY_REVIEW_2026-07-29.md`.

## Retained decisions

1. Не выдавать mock/fallback за AI output.
2. Face/body data обрабатывается только с explicit consent.
3. Payments остаются выключены до real provider + COGS + webhook.
4. Failed provider/queue request не должен отнимать месячный slot.
5. Python сохраняется; оптимизируются измеренные I/O paths.
6. Deployment без target/health/rollback не объявляется выполненным.

## Epic 5 — local Codex runner and production hardening

### OBSERVE

Встраивание Codex CLI в VPS переносило бы пользовательскую авторизацию и приватные изображения на сервер. При этом
пользователь просил сохранить OpenRouter API и добавить постоянно работающий локальный CLI как второй real-AI path.

### HYPOTHESIZE

Исходящий HTTPS long-poll с heartbeat и bounded-TTL Redis jobs позволит рабочей станции выполнять recognition/text
без входящего порта, а `hybrid/runner_first` сможет немедленно переходить на OpenRouter при выключенном компьютере.

### PLAN / ACT

- hidden bearer-authenticated claim/complete/fail/heartbeat endpoints;
- ограничение размера, TTL, timeout, constant-time token check;
- Windows start/stop, реальный process-tree shutdown и relay canary;
- provider-neutral gateway с неизменённым API mode;
- production backup, migration on exact dump clone, atomic static activation and rollback copies;
- три browser runs, bug report и targeted post-fix checks.

### VERIFY

- production health: `hybrid:runner_first`, runner connected, OpenRouter configured;
- runner production canary and real image recognition completed locally;
- offline runner probe fell back to OpenRouter;
- final full E2E: upload `Готово`, 18 items, avatar/try-on `completed`, 0 console errors, 0 failed requests,
  0 layout issues;
- targeted post-fix try-on: one delivery, 11.0 s, no `job not found` retry;
- Favorites recheck: 7 cards/7 collages/7 images, width 390/390, no failures.

### CRITIQUE

Per-request CLI startup is a privacy/dev choice, not a high-throughput serving architecture. Runner-only capacity,
provider cost ingestion and long-duration soak/load evidence remain absent. Pixel generation intentionally remains API.

### DECIDE

`ACCEPTED` for controlled hybrid production testing. Runner-only public SLO: `PARTIAL`.

## Final infrastructure verification

- Fresh compressed PostgreSQL, source and static backups exist under `/opt/ai-wardrobe/backups/releases`.
- Exact production dump clones validated both migration repairs; production is at `0005_upload_image_links`.
- Production API and worker are healthy; rotating `api.log`/`worker.log` and Docker stdout are active.
- Local Codex runner remains connected from the trusted Windows workstation; the VPS contains no Codex auth/binary.
- Subscription build is live over TLS. Payments remain deliberately disabled; entitlement/promo/quota enforcement is live.
- Detailed incidents and fixes are recorded in `BUG_REPORT_2026-07-29.md`.
