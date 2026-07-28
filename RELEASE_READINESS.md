# Release readiness

Срез: 2026-07-28.

| Требование | Статус | Доказательство / blocker |
|---|---|---|
| Исходный prompt сохранён | VERIFIED | `PROJECT_MASTER_REQUEST_RAW.md` |
| Prompt улучшен без потери требований | VERIFIED | `PROJECT_MASTER_PROMPT.md`; Prompt Machine candidate 90.3/accept |
| Проект и killer features проанализированы | VERIFIED | `PROJECT_AUDIT.md` |
| Рынок/цены/provider costs | VERIFIED | `MARKET_AND_PRICING_RESEARCH.md`, первичные ссылки |
| Engineering loop | VERIFIED | `ENGINEERING_LOOP_REPORT.md` |
| Все вкладки визуально пройдены | VERIFIED | 6/6 на 390×844; `UX_SCREEN_AUDIT.md` |
| Editor: контролируемая область/crop | VERIFIED | pointer + keyboard rectangle, undo/redo/reset/full, server provenance |
| Editor: semantic auto-detection/mask/zoom | PARTIAL | central proposal есть; segmentation/brush/zoom в P1 |
| Avatar profile/consent/revoke | VERIFIED | API/models/UI/tests; derived S3 deletion |
| Real avatar/try-on quality | BLOCKED | adapter есть, но consented live test/provider validation не выполнены |
| Premium entitlement | VERIFIED | server resolver + feature gate |
| Monthly cost quotas | VERIFIED locally | idempotent reservations and tests; quota race под real PostgreSQL concurrency не проверен |
| Promo module | VERIFIED PostgreSQL | HMAC/expiry/max/idempotency tests + authenticated HTTP redemption smoke |
| Однодневный promo записан в БД | VERIFIED | QA PostgreSQL readback: Premium, 24h, max 1, unused; plaintext only in handoff |
| Payments | BLOCKED | `ENABLE_BILLING_PAYMENTS=false`; нет webhook/invoices/refunds |
| Builds with/without paywall | VERIFIED | `build:subscriptions`, `build:open`, разные JS hashes |
| Production deployment нового scope | BLOCKED | HTTP healthy; SSH banner timeout в двух попытках, backup/rollback и separate targets не подтверждены |
| Structured logging/redaction | VERIFIED | JSON request logs and redaction tests |
| Metrics | PARTIAL | API counter/histogram/uptime; нет queue/provider/DB exporter/traces |
| Full test suite | VERIFIED | 115 passed, 67.91% coverage (gate 67%) |
| PostgreSQL migration up/down | VERIFIED locally | fresh up/down/up и committed-v0.3.1 → current upgrade прошли; live `0001` debt остаётся |
| DB normalization | PARTIAL | new domain normalized and constrained; legacy plan/UsageLimit cleanup remains |
| Go decision | REJECTED | нет measured CPU bottleneck |
| Claude Code review | VERIFIED | Opus alias, read-only, exit 0; separate Cloud Code Design unavailable |
| README/CHANGELOG/MEMORY | VERIFIED | обновлены текущим loop |

## Ship decision

- Local/product demo: **yes**.
- Closed preview without payments and without fidelity claim: **conditional yes**.
- Public production with paid subscriptions: **no**.

## Human gates

1. Восстановить SSH banner/доступ, подтвердить свежий off-host backup, rollback policy и отдельный URL для open variant.
2. Выбрать payment and try-on providers.
3. Подтвердить privacy/legal terms for face/body data.
4. Снять schema-only dump production и повторить upgrade на sanitized clone.
