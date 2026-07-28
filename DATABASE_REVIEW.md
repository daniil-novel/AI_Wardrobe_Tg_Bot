# Database review and normalization

Дата: 2026-07-28. Target: PostgreSQL 16, SQLAlchemy 2, Alembic.

## Вывод

Новый editor/avatar/try-on/promo domain приведён к 3NF/BCNF там, где атрибуты имеют стабильную реляционную семантику. JSONB сохранён для слабоструктурированных AI/style snapshots, где принудительная декомпозиция увеличила бы coupling без измеренной пользы.

Схема стала безопаснее. Migration chain проверена на fresh PostgreSQL и на baseline, построенном committed v0.3.1
кодом, однако исторический `0001_initial_schema` всё ещё вызывает `Base.metadata.create_all()` и остаётся
воспроизводимостью/maintenance debt до появления immutable baseline.

## Нормализованные сущности

### Recognition selection

- `image_selections.upload_id` уникален: один подтверждённый selection provenance на upload;
- geometry хранит нормализованные координаты `0..1`;
- crop pixels хранятся в private S3, а не в JSON/логах.

Geometry оставлена JSONB, потому что текущий контракт — единый value object rectangle. При появлении нескольких masks/strokes нужно выделить `image_selection_regions` и `image_selection_strokes`.

### Avatar

- `avatar_profiles`: один профиль на пользователя;
- `avatar_measurements`: одна характеристика на строку, ключ `(avatar_profile_id, code)`;
- value/unit/source/confidence отделены от текстового описания;
- положительное значение защищено DB check;
- reference и generated images — внешние ключи на `image_assets`.

Это соответствует 3NF/BCNF: measurement facts зависят от полного candidate key, транзитивных зависимостей нет.

### Try-on

- `try_on_jobs` хранит lifecycle и provider metadata;
- `try_on_items` — M:N job ↔ garment с deterministic `sort_order`;
- уникальны и `(job, item)`, и `(job, sort_order)`;
- output image — отдельный asset.

### Promo

- plaintext promo не хранится: только HMAC-SHA256 keyed hash;
- `promo_codes` определяет grant policy;
- `promo_redemptions` фиксирует факт и expiry;
- `(promo_code_id, user_id)` уникален;
- row-level lock и cached counter предотвращают oversubscription;
- DB checks защищают duration, max count, counter и expiry.

## Добавленные ограничения и индексы

Migration `0004_commercial_integrity`:

- unique role per `(user_id, role)`;
- не более одной active subscription на пользователя через partial unique index;
- unique usage window `(user_id, period, resets_at)`;
- unique payment provider event `(provider, provider_payment_id)` when ID is present;
- unique try-on order;
- unique AI analysis reservation per `(task_id, request_type)` for `analyze_image`;
- composite promo lookup `(user_id, expires_at)`;
- try-on history `(user_id, created_at)`;
- positive/check constraints для promo counters и avatar measurements.

## Quota consistency

До loop direct upload мог обходить displayed subscription limits, а `/ai/analyze-image` создавал queued row, после чего worker добавлял второй completed row. Это завышало usage.

Теперь:

1. user row блокируется `FOR UPDATE`;
2. effective access вычисляется из profile/subscription/promo;
3. count берётся за календарный UTC month;
4. reservation создаётся до enqueue;
5. retry повторно использует reservation;
6. worker обновляет ту же запись до completed/failed;
7. Telegram transfer применяет ту же проверку до S3 write/AI enqueue.

Open build не применяет paywall quota, но сохраняет audit request.

## Допустимая денормализация

### `users.subscription_plan`

Это legacy fallback рядом с `subscriptions`. Потенциально может расходиться с active subscription. Сейчас resolver выбирает strongest entitlement, поэтому ошибка ограничена лишним доступом из legacy field.

Решение до production payments:

- прекратить запись платного плана в `users.subscription_plan`;
- мигрировать активные значения в `subscriptions`;
- оставить column только как read-only compatibility cache или удалить после deprecation window.

### `promo_codes.redemption_count`

Это derived cached counter, нарушающий чистую нормализацию, но нужен для bounded global limit без дорогостоящего aggregate under lock. Допустим, потому что:

- обновляется в той же транзакции под row lock;
- `promo_redemptions` остаётся source of truth/audit;
- DB check запрещает выход за диапазон.

Нужен reconciliation job: сравнивать counter с `COUNT(*)` и алертить расхождения.

### `usage_limits`

Legacy table существует, но новый enforcement считает idempotent rows в `ai_requests`. Два источника счётчика одновременно использовать нельзя. Рекомендация: после production migration либо удалить `usage_limits`, либо превратить его в materialized/cache layer с reconciliation.

## JSONB review

JSONB оправдан:

- AI/provider snapshots;
- user style preferences с меняющейся taxonomy;
- outfit reasoning/context;
- research sources;
- UI-oriented weather/style snapshots.

Нормализовать при появлении хотя бы одного условия:

- поле участвует в FK/integrity;
- требуется high-selectivity filtering/index;
- значение переиспользуется несколькими aggregates;
- taxonomy стала стабильной;
- появились аномалии обновления.

Для frequently queried arrays потребуется GIN index, но добавлять его без query plan и workload преждевременно.

## PII и biometric boundary

- Telegram ID/username/name находятся в `users`;
- face reference — только ссылка на private `image_assets`;
- body measurements отделены и удаляются при revoke;
- generated avatar/try-on images удаляются из S3 и БД при revoke;
- original wardrobe upload сохраняется по общему retention policy, но отвязывается от avatar profile;
- `AiRequest` не содержит image/base64/prompt body.

Нужно дополнительно определить сроки retention для original uploads, soft-deleted garments, raw payment events и logs.

## Migration evidence and remaining debt

`0001_initial_schema.py` импортирует текущие models и вызывает `Base.metadata.create_all()`. Следствия:

- fresh database на старом revision может получить будущие таблицы;
- schema, созданная сегодня, не воспроизводит schema 0001;
- downgrade может удалить больше, чем создал исторический revision;
- autogenerate/diff теряет смысл;
- `checkfirst=True` в 0002/0003 маскирует проблему, но не исправляет историю.

Почему baseline не переписан автоматически: changelog указывает на существовавший production deployment. Изменение historical migration без schema snapshot и DB access может сломать уже применённую цепочку.

Выполнено 2026-07-28:

- fresh PostgreSQL 16: `upgrade head → downgrade base → upgrade head`;
- committed v0.3.1 baseline: 27 public tables;
- current `0002–0004`: успешный upgrade до 34 tables и `0004_commercial_integrity`;
- отдельный QA API с PostgreSQL/Redis достиг `/health/ready = 200`.

Оставшийся production-safe путь:

1. снять schema-only dump staging/production;
2. сравнить `alembic current`, metadata и live schema;
3. создать immutable baseline для новых installs;
4. сохранить bridge revision для существующих installs;
5. повторить upgrade на sanitized production clone с репрезентативными данными;
6. зафиксировать rollback.

## Статус normal forms

| Область | Оценка |
|---|---|
| Avatar measurements | BCNF |
| Try-on job/items | BCNF |
| Promo grants/redemptions | 3NF/BCNF + controlled cached counter |
| Wardrobe/outfits | В основном 3NF; JSONB — aggregate snapshots |
| Subscription | 3NF, но legacy plan column требует deprecation |
| Payments | 3NF; raw_event — audit payload с retention risk |
| Migration history | Local upgrade VERIFIED; immutable baseline и production-clone restore drill остаются |
