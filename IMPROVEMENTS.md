# AI Wardrobe: предлагаемые улучшения

Дата аудита: 2026-07-28. Статус: три bounded-итерации выполнены; остаток явно отмечен как `PARTIAL` или `BLOCKED`.

## Короткий вывод

Проект уже не является прототипом «с нуля»: в нём есть Telegram auth, user-scoped FastAPI, PostgreSQL-модели, S3 upload, Celery AI pipeline, гардероб, образы, погода, AI-дизайнер, privacy receipts и rate limits. За текущий loop добавлены управляемая область распознавания, consent-safe avatar/try-on domain, серверные entitlements, квоты и промокоды. Производственными разрывами остаются semantic segmentation, проверенная точность виртуальной примерки, реальные платежи и безопасный migration/deployment gate.

Baseline текущего дерева:

- `115 passed`, coverage `67.91%` в финальном контрольном прогоне;
- ruff, format, mypy, frontend typecheck и build проходят;
- Mini App: subscription JS `213.61 kB` (`66.66 kB gzip`), open JS `209.63 kB` (`65.67 kB gzip`), CSS `21.32 kB` (`4.71 kB gzip`);
- public TestClient routes: около `190 RPS`, p95 `<8 ms` в synthetic in-process прогоне;
- Docker Linux engine доступен; PostgreSQL migration `up/down/up`, upgrade от committed v0.3.1 schema, Redis readiness и promo HTTP E2E подтверждены. S3/Celery/provider E2E и production-like latency ещё не выполнены.

## Результат bounded loop

| Направление | Статус | Что принято |
|---|---|---|
| P0 privacy/integrity | `ACCEPTED` | consent lifecycle, HMAC promo, redaction, deletion of avatar derivatives |
| Selection editor | `ACCEPTED/PARTIAL` | crop, pointer/keyboard, undo/redo/full/reset; semantic mask/brush/zoom остаются P1 |
| Avatar/try-on | `ACCEPTED/BLOCKED` | domain/API/UI/provider adapter готовы; fidelity на согласованном live dataset не доказана |
| Entitlements/quotas/promo | `ACCEPTED` | unit tests, real PostgreSQL insert/readback и authenticated promo HTTP E2E |
| Payments/deployment | `BLOCKED` | feature flag выключен; нет provider/webhook, двух targets и server backup/rollback proof; SSH banner timeout |
| Performance/Go | `ACCEPTED` / rewrite `REJECTED` | локальный baseline есть; данных о CPU bottleneck нет |

## P0 — доверие, безопасность и целостность

1. Не отправлять на AI лишние области фотографии: добавить локальное кадрирование/selection editor до upload.
2. Добавить явное согласие на хранение face reference, пропорций и генерацию аватара; обеспечить отзыв согласия и удаление.
3. Разделить «реальная генерация», «ожидание провайдера» и dev mock. Никогда не показывать mock как готовый AI-результат.
4. Хранить промокоды только в виде keyed hash; проверять срок, лимит и повторное использование транзакционно на сервере.
5. Исключить фото, маски, face references, токены, presigned URLs и биометрические параметры из логов/метрик.

## P1 — killer feature: редактор области

Реализовано до отправки фото:

- preview изображения;
- автоматически предложенную центральную область человека с явной маркировкой «предложение»;
- выбор `всё фото` / `только область`;
- touch/mouse drag-selection;
- undo/redo, reset, zoom-ready data contract;
- preview именно тех пикселей, которые будут отправлены;
- серверное сохранение нормализованных координат и provenance выделения;
- в перспективе заменить геометрическую подсказку на реальный person/garment segmentation adapter.

Критерий: background mannequins/racks можно исключить до upload, а worker получает только подтверждённый crop.

## P1 — killer feature: avatar и virtual try-on

Реализован нормализованный домен:

- `avatar_profiles` — consent/status/reference/output;
- `avatar_measurements` — одна измеримая характеристика на строку с unit/source/confidence;
- `try_on_jobs` и `try_on_items` — асинхронный job и выбранные вещи;
- API чтения/обновления/отзыва профиля и создания/проверки try-on job;
- premium entitlement `avatar_try_on`;
- UI настройки пропорций без оценочных ярлыков тела;
- нейтральная прилегающая базовая одежда и нейтральный фон;
- дисклеймер: результат является визуальной симуляцией, не гарантией физической посадки.

До подключения подтверждённого image-generation provider UI обязан показывать `provider_not_configured`, а не фальшивую картинку.

## P1 — subscriptions, entitlements и промокоды

- расширить планы читаемыми названиями, ценой/валютой, feature list и рекомендованным тарифом;
- добавлены `GET /billing/me` и `POST /billing/promos/redeem`;
- вычислять эффективный план из подписки и активного promo grant;
- добавить `promo_codes` и `promo_redemptions` с уникальностью и атомарным лимитом;
- создание высокоэнтропийного 24-часового test promo реализовано скриптом, но фактическая запись заблокирована недоступной PostgreSQL;
- вынести payment activation за feature flag до появления production provider/webhook;
- собирать Mini App в вариантах `subscription-enabled` и `subscription-disabled` из одной кодовой базы.

## P1 — скорость и задержки

Уже присутствующие незакоммиченные улучшения — ограничение параллельной загрузки изображений, cache object URLs, optimistic delete, увеличенный DB pool — выглядят обоснованно, но требуют after-замеров.

Следующие шаги:

- измерить API p50/p95/p99 на auth, items, image, upload init/status и billing;
- убрать последовательные client waterfalls;
- добавить cache headers/thumbnail endpoint или batch manifest изображений;
- измерять queue lag, provider latency/cost, DB pool wait и upload time;
- добавить browser performance marks для first screen, wardrobe ready и editor ready.

Решение по Go: полный rewrite сейчас не обоснован. Основные задержки I/O-bound (PostgreSQL, S3, Telegram, очередь, внешний AI) и frontend waterfall. Go рассматривать только для измеренного CPU/throughput hot path после профилирования.

## P2 — UX и коммерческая подача

- единый skeleton/empty/error/retry pattern на всех шести текущих вкладках;
- отдельный premium/avatar surface без перегрузки нижней навигации;
- устранить ложные действия: кнопка секционного заголовка не должна выглядеть кликабельной без handler;
- добавить видимый статус auth/offline/provider;
- сделать прогресс upload доступным через `role=progressbar` и `aria-valuenow`;
- сохранить фокус, клавиатурную навигацию и touch target не меньше 44 px;
- в subscription UI показывать лимиты и честную стоимость без dark patterns;
- проверить desktop 390–520 px и mobile 320/360/390 px, dark mode и reduced motion.

## P2 — тестирование и эксплуатация

- поднять meaningful coverage прежде всего для `uploads`, `ai`, `items`, `outfits`, `auth`, а не строковыми contract tests;
- добавить unit/integration tests для promo hashing/redemption/concurrency/expiry;
- добавить migration smoke up/down на disposable PostgreSQL;
- добавить component/E2E editor tests, billing states и visual regression;
- добавить OpenTelemetry trace propagation API → Celery → provider;
- документировать SLO, alerts, runbooks и cost dashboards.

## Границы текущего loop

В текущем bounded loop реализуются проверяемые контракты editor, avatar/try-on и entitlements/promocode, UI-коммерциализация, сборки с/без подписки, документация и локальная visual QA. Реальный production payment webhook, production deploy и гарантия антропометрической точности требуют подтверждённых внешних провайдеров, staging target и согласованных юридических/privacy документов.
