# Release readiness

Срез: 2026-07-29.

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
| Real avatar/try-on pipeline | VERIFIED synthetic | real provider generated avatar and try-on from a fictional adult fixture; no one-to-one biometric fidelity claim |
| Premium entitlement | VERIFIED | server resolver + feature gate |
| Monthly cost quotas | VERIFIED locally | idempotent reservations and tests; quota race под real PostgreSQL concurrency не проверен |
| Promo module | VERIFIED PostgreSQL | HMAC/expiry/max/idempotency tests + authenticated HTTP redemption smoke |
| Однодневный promo записан в БД | VERIFIED production | Premium, 24h, max 1; E2E code redeemed, a separate unused handoff code is created at delivery |
| Payments | BLOCKED | `ENABLE_BILLING_PAYMENTS=false`; нет webhook/invoices/refunds |
| Builds with/without paywall | VERIFIED | `build:subscriptions`, `build:open`, разные JS hashes |
| Production deployment нового scope | VERIFIED | fresh backups, exact archive hashes, `0005`, atomic static activation, healthy API/worker/runner |
| Structured logging/redaction | VERIFIED production | JSON request logs and redaction tests; rotating files plus Docker stdout |
| Metrics | PARTIAL | API counter/histogram/uptime; нет queue/provider/DB exporter/traces |
| Full test suite | VERIFIED | 138 passed, 70.11% coverage (gate 67%) |
| PostgreSQL migration up/down | VERIFIED local + production clone | fresh up/down/up, exact production dump repair and live upgrade to `0005` |
| DB normalization | PARTIAL | new domain normalized and constrained; legacy plan/UsageLimit cleanup remains |
| Go decision | REJECTED | нет measured CPU bottleneck |
| Claude Code review | VERIFIED | Opus alias, read-only, exit 0; initial and post-deploy reviews saved |
| README/CHANGELOG/MEMORY | VERIFIED | обновлены текущим loop |

## Ship decision

- Local/product demo: **yes**.
- Closed production preview without payments and without biometric-fidelity claim: **yes**.
- Public production with paid subscriptions: **no**.

## Remaining commercial gates

1. Выбрать payment provider и реализовать signed webhook/invoices/refunds.
2. Подтвердить privacy/legal terms and retention for face/body data.
3. Провести consented avatar fidelity study and define an honest product claim.
4. Добавить off-host automated backups, queue/provider dashboards, alerts and a production soak/load test.
