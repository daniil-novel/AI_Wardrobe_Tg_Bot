# Implementation plan

## Objective

За три bounded-итерации закрыть максимальный проверяемый объём `P0/P1` из `IMPROVEMENTS.md`, не повреждая существующие незакоммиченные изменения.

## Iteration 1 — user-controlled recognition

Гипотеза: client-side selection/crop до upload снижает риск фонового распознавания без роста backend latency.

Изменения:

- selection editor с pointer events, preview, undo/redo/reset;
- crop выбранной области в browser canvas;
- multipart metadata с нормализованными координатами;
- таблица/API contract для provenance области;
- UI/accessibility/contract tests.

Проверка:

- typecheck/build;
- pytest schema/upload contracts;
- визуальный desktop/mobile проход;
- размер bundle и editor interaction latency.

Rollback: feature flag/режим `всё фото`, существующий upload endpoint остаётся обратно совместимым.

## Iteration 2 — consent-safe avatar and try-on domain

Гипотеза: нормализованный профиль и provider abstraction позволяют безопасно подключить генерацию без хранения неуправляемой биометрии и без фиктивного результата.

Изменения:

- avatar profile, measurements, try-on jobs/items и миграция;
- API profile consent/revoke/job lifecycle;
- premium UI для профиля, выбора вещей и статуса генерации;
- явный `provider_not_configured` fallback;
- privacy и entitlement tests.

Проверка:

- ruff/mypy/pytest;
- migration model contract;
- UI E2E/visual states;
- проверка удаления consent/reference linkage.

Rollback: отключить feature flag; данные остаются нормализованными и удаляемыми.

## Iteration 3 — subscriptions, promo and commercial QA

Гипотеза: server-side effective entitlements и 24-hour promo дают тестируемый premium flow без подключения реальных платежей.

Изменения:

- promo code/redemption schema и keyed hashing;
- `GET /billing/me`, `POST /billing/promos/redeem`;
- subscription-enabled/open builds;
- premium pricing/entitlement UI;
- high-entropy one-day test promo creation tool и попытка внесения в доступную DB;
- README/CHANGELOG/MEMORY и deployment docs.

Проверка:

- duplicate/expired/disabled/max-redemption/timezone tests;
- обе frontend builds;
- полный route audit;
- DB insert/readback, если PostgreSQL доступен;
- visual/accessibility/performance regression.

Rollback: `VITE_SUBSCRIPTIONS_ENABLED=false`, `ENABLE_BILLING_PAYMENTS=false`; promo можно отключить без удаления audit trail.

## Stop conditions

- максимум 3 итерации на epic;
- критерии не ослабляются;
- реальный payment, production migration/deploy и работа с приватными лицами требуют подтверждённой внешней среды;
- недоступный provider или Docker фиксируется как `BLOCKED`, а не маскируется mock-результатом.

## Execution result

Все три итерации выполнены в пределах stop conditions. PostgreSQL migration proof и фактический promo insert/readback закрыты после восстановления Docker. Semantic mask/zoom, live avatar fidelity, production payments и deployment двух вариантов не подменялись моками и остаются release gates. Подробные evidence и решения: `ENGINEERING_LOOP_REPORT.md`, `RELEASE_READINESS.md`, `UX_SCREEN_AUDIT.md`, `PERFORMANCE_BASELINE.md`.
