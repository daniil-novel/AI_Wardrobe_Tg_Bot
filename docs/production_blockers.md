# Критические блокеры перед выпуском в production

## 0.1. Release update — 2026-07-05 (v0.3.0)

Проект развёрнут в production на VPS и доступен в Telegram (@wwardrobeai_bot, Mini App за TLS).
Закрыты найденные при выпуске release-blocking дефекты: webhook-режим бота не стартовал
(вложенный event loop), первая авторизация нового пользователя падала на NULL `user_id`,
Telegram-фото никогда не переносились в S3 (idempotency-skip), Celery-задачи маршрутизировались
в очереди без консьюмера, AI-провайдер не мог скачать presigned URL приватного MinIO
(теперь inline data URL), retry-endpoint'ы не ставили задачи, `ports:`/`profiles:` production
override не перекрывали базовый compose. Добавлен Redis rate limiting. Полный e2e прогнан
на боевом стенде: auth → refresh → upload → S3 → Celery → OpenRouter → item в гардеробе,
изоляция пользователей, 401/429, классификация ошибок Telegram file API.

Остаются follow-up'ы: load/chaos-прогоны, дашборды и алерты, автоматизация бэкапов,
PROXY protocol для точного client IP за общим haproxy.

## 0. Remediation update — 2026-05-21

Ветка `harden-production-release` закрывает release-blocking поведение ранней версии для RC:

- `Critical`: auth больше не выдаёт случайный user id; Telegram auth создаёт/обновляет пользователя, refresh token ротируется и отзывается, production startup блокируется на default secrets.
- `Critical`: пользовательские API больше не возвращают sample-данные наружу; wardrobe, looks, outfits, wishlist, style, designer и privacy endpoint'ы требуют bearer token и фильтруют данные по `user_id`.
- `Critical`: upload/AI lifecycle сохраняет состояние в PostgreSQL, изображения привязаны к S3 keys, worker сохраняет item, privacy receipt и AI request side effects; mock AI mode отключён.
- `Critical`: Mini App использует Telegram `initData` -> backend JWT и authenticated fetch wrapper с refresh retry.
- `Critical`: bot поддерживает production webhook mode и передаёт upload registration через internal secret; polling запрещён в production без явного feature flag.
- `Critical`: billing payments и marketplace search не имитируют готовность и остаются выключенными feature flags до подключения production provider adapters.
- `Critical`: добавлены `/health/live`, `/health/ready`, `/metrics`, production compose override, secret validation, release docs и воспроизводимый запуск тестов через Python 3.12.

Оставшиеся перед реальным GA-релизом проверки не скрыты: staging deploy с настоящими PostgreSQL/Redis/S3/OpenRouter/Telegram secrets, migrations-on-deploy, backup/restore drill, load/chaos/security scans и алерты должны быть выполнены в production-like окружении до включения массового трафика.

## 1. Краткое резюме

Текущий RC уже использует устойчивую авторизацию, user-scoped API, PostgreSQL/S3 upload state, Celery AI side effects и authenticated Mini App API calls. Этот документ сохраняет исходный список рисков как исторический release checklist; актуальный статус отражён в таблице ниже.

GA-выпуск всё ещё требует production secrets, staging rollout, load/chaos/security прогонов, backup/restore drill и алертов. Без этих внешних проверок проект нельзя считать полностью готовым к массовому production-трафику.

---

## 2. Список критических блокеров

| № | Блокер | Критичность | Область | Статус |
|---|--------|-------------|---------|--------|
| 1 | Нет полноценной авторизации, сессий и изоляции пользовательских данных | Critical | Security/Auth/API | Closed in RC |
| 2 | Основные API-модули возвращают stub/sample-данные вместо работы с БД | Critical | Backend/Data | Closed in RC |
| 3 | Upload pipeline не сохраняет состояние надёжно и не связан с Celery/S3/БД | Critical | Uploads/Storage/Queues | Closed in RC |
| 4 | AI pipeline не замкнут: результаты не персистятся, нет лимитов, учёта стоимости и контроля ошибок | Critical | AI/Workers/Cost Control | Closed in RC; exact provider cost metadata remains follow-up |
| 5 | Mini App не подключен к реальному backend-состоянию и не использует production auth flow | Critical | Frontend/Product Flow | Closed in RC |
| 6 | Telegram bot работает в polling-режиме и не реализует production-grade webhook/data flow | Critical | Telegram/Bot | Closed in RC |
| 7 | Нет production-grade удаления данных, privacy lifecycle и audit trail | Critical | Privacy/Compliance/Security | Closed in RC; external storage deletion drill remains follow-up |
| 8 | Billing и usage limits не реализованы, но присутствуют в публичном API | Critical | Billing/Monetization/Limits | Mitigated in RC with feature flags |
| 9 | Docker Compose и runtime-конфигурация ориентированы на разработку, а не на production | Critical | Infrastructure/Deployment | Closed in RC |
| 10 | Миграции БД не готовы для безопасной эволюции production-схемы | Critical | Database/Migrations | Closed in RC; staging migration drill remains follow-up |
| 11 | Нет rate limiting, backpressure и защиты от перегрузки дорогих операций | Critical | Highload/Resilience/Security | Partially closed; Redis rate middleware remains follow-up |
| 12 | Нет observability: метрик, трассировки, алертов и эксплуатационных SLO | Critical | Operations/Monitoring | Partially closed; dashboards/alerts remain follow-up |
| 13 | Недостаточное тестовое покрытие production-сценариев и нестабильная воспроизводимость тестов | Critical | QA/CI/CD | Closed in RC for unit/integration/build checks |
| 14 | Нет стратегии отказоустойчивости, graceful shutdown и восстановления после сбоев | Critical | Reliability/Highload | Partially closed; chaos/restore drills remain follow-up |

---

## 3. Подробное описание блокеров

### Блокер 1. Нет полноценной авторизации, сессий и изоляции пользовательских данных

**Проблема:**  
Endpoint `/auth/telegram` проверяет Telegram `initData`, но не создаёт и не обновляет пользователя в БД. Вместо стабильного пользователя создаётся новый случайный UUID. Refresh endpoint возвращает `501 Not Implemented`. Большинство бизнес-endpoint'ов не требуют bearer token и не фильтруют данные по `user_id`.

**Почему это критично:**  
В production нельзя обрабатывать гардероб, фото, платежи и AI-результаты без строгой связи данных с конкретным пользователем. При высокой нагрузке отсутствие user-scoping приведёт к некорректным данным, невозможности безопасно масштабировать API и риску доступа к чужим ресурсам.

**Риски:**  
- пользователь получает не свои вещи, луки, загрузки или рекомендации;
- невозможно корректно удалить данные конкретного пользователя;
- refresh/logout не отзывают сессии;
- нельзя надёжно применять тарифные лимиты;
- невозможно расследовать инциденты по конкретному аккаунту.

**Как исправить правильно:**  
1. Реализовать `UserService`: upsert пользователя по `telegram_id`, сохранение username, first name, language, timezone и privacy settings.
2. Реализовать session lifecycle: refresh token hash в таблице `sessions`, rotation refresh token, revoke on logout, expiration, device/user-agent/ip hash metadata.
3. Подключить `get_current_user_id` ко всем endpoint'ам, которые работают с пользовательскими данными.
4. Во всех SQL-запросах фильтровать данные по `user_id`; запретить доступ к объектам другого пользователя через `404` или `403`.
5. Добавить роли и RBAC только для admin/internal endpoint'ов.
6. На старте production окружения запрещать запуск с default `JWT_SECRET_KEY`.

**Какие проверки добавить:**  
- unit-тесты для Telegram `initData` validation, token creation, token expiration, refresh rotation;
- интеграционные тесты auth -> create user -> authenticated request;
- тесты изоляции: пользователь A не может читать/менять объекты пользователя B;
- security tests для invalid/expired/revoked tokens;
- e2e-тест Mini App auth через Telegram initData mock;
- алерты на рост `401`, `403`, refresh failures и подозрительную частоту auth-запросов.

**Критерий готовности:**  
Все пользовательские API требуют валидную авторизацию, пользователь стабильно хранится в БД, refresh/logout работают, чужие данные недоступны, default secrets запрещены в `production`.

---

### Блокер 2. Основные API-модули возвращают stub/sample-данные вместо работы с БД

**Проблема:**  
`items`, `looks`, `outfits`, `designer`, `marketplace`, `wishlist`, `style` и часть privacy flows возвращают статические sample-ответы или пустые списки. Изменения через PATCH/POST не сохраняются. Пользователь не получает реального состояния гардероба.

**Почему это критично:**  
Production-приложение должно сохранять и воспроизводить состояние пользователя. Stub-ответы ломают доверие, делают невозможными рекомендации, оплату тарифов, аналитику гардероба, восстановление после сбоев и поддержку.

**Риски:**  
- данные пользователя теряются после каждого запроса;
- рекомендации строятся не на реальном гардеробе;
- действия в UI не соответствуют состоянию backend;
- поддержка не сможет воспроизвести проблему пользователя;
- highload-тесты будут бессмысленны, потому что не проверяют реальные запросы к БД.

**Как исправить правильно:**  
1. Ввести сервисный слой: `ItemsService`, `LooksService`, `OutfitsService`, `WishlistService`, `StyleService`.
2. Реализовать CRUD через SQLAlchemy async sessions с транзакциями.
3. Добавить пагинацию, сортировку, фильтры и индексы для списков вещей, луков, избранного и wishlist.
4. Сделать optimistic/idempotent операции для favorite, confirm, hide, wear, delete.
5. Заменить sample factories на fixtures только в тестах.
6. Отделить read models/API DTO от ORM и явно валидировать входные payload'ы.

**Какие проверки добавить:**  
- unit-тесты сервисов на CRUD и бизнес-правила;
- интеграционные тесты с PostgreSQL на все основные endpoint'ы;
- тесты пагинации и фильтрации при больших объёмах данных;
- concurrency tests для одновременного favorite/wear/delete;
- миграционные тесты индексов и ограничений;
- метрики latency/error rate по каждому API group.

**Критерий готовности:**  
Все основные пользовательские операции сохраняются в PostgreSQL, читаются обратно, изолированы по `user_id`, покрыты интеграционными тестами и работают на объёмах, близких к production.

---

### Блокер 3. Upload pipeline не сохраняет состояние надёжно и не связан с Celery/S3/БД

**Проблема:**  
Прямой upload в `/uploads/file` использует локальную папку `storage/uploads` и in-memory dictionary. Статус обработки меняется по таймеру внутри процесса. `/uploads/complete` создаёт task id, но не ставит реальную задачу в очередь. Telegram upload сохраняет только `file_id`, но не переносит файл в object storage.

**Почему это критично:**  
При рестарте API все in-memory записи исчезнут. При нескольких репликах API разные пользователи будут попадать на разные stores. Под высокой нагрузкой локальный диск контейнера и память процесса станут точками потери данных и неконсистентности.

**Риски:**  
- потеря загруженных фото после restart/deploy;
- `GET /uploads/{id}` возвращает `404` на другой реплике API;
- Celery worker не получает реальную задачу;
- пользователь видит “готово”, хотя AI-обработка не выполнялась;
- локальный диск контейнера переполняется;
- невозможно безопасно удалить приватные изображения.

**Как исправить правильно:**  
1. Хранить метаданные upload в таблице `uploads`, изображения в S3-compatible storage.
2. Использовать presigned PUT для Mini App и backend-managed transfer для Telegram file downloads.
3. После `/uploads/complete` проверять наличие объекта в S3, создавать `ImageAsset`, обновлять `Upload.status=queued` и ставить Celery task.
4. Заменить in-memory `UploadStore` на репозиторий PostgreSQL.
5. Добавить file size limit, content-type allowlist, проверку magic bytes, image decoding validation.
6. Добавить lifecycle cleanup для failed/expired/orphan uploads.
7. Сделать idempotency key для повторного complete/retry.

**Какие проверки добавить:**  
- интеграционные тесты upload init -> S3 object -> complete -> DB upload -> Celery task;
- тесты reject для non-image, oversized image, corrupted image;
- тесты retry/delete с проверкой статусов и S3 cleanup;
- нагрузочные тесты параллельных uploads;
- chaos-тест: API restart между init и complete;
- метрики очереди upload processing, upload failures, average processing time, S3 errors.

**Критерий готовности:**  
Upload-состояние хранится в БД, файлы лежат в S3, статусы отражают реальные этапы обработки, pipeline работает при нескольких API replicas и переживает restart без потери данных.

---

### Блокер 4. AI pipeline не замкнут: результаты не персистятся, нет лимитов, учёта стоимости и контроля ошибок

**Проблема:**  
`LlmGateway` умеет вызвать OpenRouter, но endpoint `/ai/analyze-image` только возвращает `queued`. Worker `analyze_upload` возвращает результат задачи, но не обновляет `uploads`, не создаёт `garment_items`, `look_cards`, `privacy_receipts` и `ai_requests`. Research/outfit tasks возвращают `pending_provider_integration`.

**Почему это критично:**  
AI-обработка является дорогой и центральной частью продукта. Без персистентности, лимитов и контроля ошибок приложение будет терять результаты, бесконтрольно тратить деньги и показывать пользователю некорректный статус.

**Риски:**  
- OpenRouter costs растут без контроля;
- повторные retries создают дубли и лишние расходы;
- пользователь не видит результат анализа;
- ошибки provider'а не классифицируются и не восстанавливаются;
- нельзя расследовать качество AI-ответов;
- privacy receipt не отражает реальную обработку.

**Как исправить правильно:**  
1. Реализовать AI orchestration service: validate upload -> reserve quota -> enqueue task -> persist task state.
2. Worker должен в транзакции обновлять `uploads`, создавать `garment_items`/`look_cards`, `privacy_receipts` и запись `ai_requests`.
3. Добавить идемпотентность по `upload_id` и `task_type`.
4. Ввести per-user и global AI budgets: дневной cost cap, лимиты тарифов, rate limits.
5. Реализовать retries только для transient errors, без повторов для validation/safety/quota errors.
6. Валидировать JSON-ответы LLM строгими Pydantic-схемами и сохранять normalized result.
7. Добавить fallback/error states, которые UI может показать пользователю.

**Какие проверки добавить:**  
- unit-тесты prompt safety и JSON validation;
- интеграционные тесты worker -> DB side effects;
- тесты quota exceeded, provider timeout, malformed JSON, retry exhaustion;
- e2e upload image -> AI result -> item appears in wardrobe;
- нагрузочные тесты очередей AI с ограничением concurrency;
- метрики OpenRouter latency, error rate, token usage, cost per user, retry count;
- алерты на рост AI cost, provider failures, dead-letter queue size.

**Критерий готовности:**  
Каждая AI-задача имеет устойчивый статус, результат сохраняется в БД, расходы учитываются, лимиты применяются, ошибки видны пользователю и операторам, retries не создают дубли.

---

### Блокер 5. Mini App не подключен к реальному backend-состоянию и не использует production auth flow

**Проблема:**  
Mini App использует локальные демо-данные для Today, Wardrobe, Designer и Favorites. Реальный API client покрывает в основном upload lifecycle. Нет обмена Telegram `initData` на backend JWT, нет authenticated fetch wrapper, нет обработки token refresh, `401`, `403`, offline/error states.

**Почему это критично:**  
Для реальных пользователей UI должен показывать их гардероб, загрузки и рекомендации. Без production auth flow frontend не сможет безопасно обращаться к backend, а под высокой нагрузкой ошибки API будут выглядеть как “сломанный интерфейс”.

**Риски:**  
- пользователь видит демо-гардероб вместо своих данных;
- API-запросы невозможно связать с пользователем;
- истечение токена ломает сессию без восстановления;
- ошибки upload/AI не объясняются;
- невозможно масштабировать клиентские сценарии и e2e-тесты.

**Как исправить правильно:**  
1. При запуске Mini App читать `window.Telegram.WebApp.initData` и вызывать `/auth/telegram`.
2. Создать typed authenticated API client с bearer token, refresh flow и централизованной обработкой ошибок.
3. Заменить `data.ts` на реальные queries: wardrobe, outfits, looks, style DNA, upload status, favorites.
4. Добавить loading, empty, error, retry states на каждый экран.
5. Синхронизировать optimistic UI с backend confirmations.
6. Добавить feature flags для незавершённых функций, чтобы не показывать неработающие flows.

**Какие проверки добавить:**  
- unit-тесты API client error handling;
- component tests для loading/empty/error states;
- e2e-тест Mini App auth -> list wardrobe -> upload -> status -> result;
- visual regression tests для Telegram WebView viewport'ов;
- performance checks bundle size, TTI, API waterfall;
- frontend monitoring: JS errors, failed API calls, route/screen load time.

**Критерий готовности:**  
Mini App работает только с реальным backend-состоянием пользователя, авторизует запросы через Telegram initData/JWT, корректно переживает ошибки API и покрыт e2e-тестами основного сценария.

---

### Блокер 6. Telegram bot работает в polling-режиме и не реализует production-grade webhook/data flow

**Проблема:**  
Bot запускается через `start_polling`. Для production highload нужен webhook с TLS, secret token validation, быстрым ack и переносом тяжёлой работы в backend/queues. Команда `/delete_me` только сообщает текстом, но не выполняет удаление. Фото регистрируется через backend, но нет полного скачивания Telegram файла в object storage.

**Почему это критично:**  
Polling плохо контролируется при масштабировании, сложнее балансируется и создаёт риск дублирования обработки. Telegram photo flow должен быть надёжным, идемпотентным и не блокировать event loop.

**Риски:**  
- дубли обработки сообщений при нескольких bot-инстансах;
- задержки и timeouts Telegram updates;
- потеря фото или upload status;
- невозможность горизонтально масштабировать bot;
- privacy-команды не выполняют юридически значимые действия.

**Как исправить правильно:**  
1. Перевести bot на webhook endpoint в API или отдельный bot service behind reverse proxy.
2. Проверять Telegram webhook secret token.
3. Делать быстрый ack и ставить обработку photo/message в queue.
4. Реализовать скачивание Telegram file через Bot API и запись в S3.
5. Добавить idempotency по Telegram update id/file id.
6. Реализовать `/delete_me` как подтверждаемый workflow с backend deletion job.
7. Ограничить concurrency и добавить graceful shutdown.

**Какие проверки добавить:**  
- integration tests webhook signature/secret validation;
- tests duplicate update id is ignored;
- e2e bot photo -> S3 object -> upload row -> AI task;
- нагрузочный тест большого потока Telegram updates;
- chaos-тест падения bot/API во время обработки фото;
- метрики update latency, queue lag, duplicate count, Telegram API errors.

**Критерий готовности:**  
Bot работает через webhook, безопасно валидирует запросы, не дублирует обработку, переносит файлы в S3, масштабируется горизонтально и поддерживает реальные privacy-команды.

---

### Блокер 7. Нет production-grade удаления данных, privacy lifecycle и audit trail

**Проблема:**  
Архитектура содержит privacy-модели, но фактические flows удаления аккаунта, удаления оригинала, privacy receipt и data retention не реализованы end-to-end. Web research/AI privacy правила задокументированы, но не подтверждаются аудитом выполнения.

**Почему это критично:**  
Приложение обрабатывает приватные фотографии одежды и потенциально чувствительные пользовательские данные. В production необходимы контролируемое удаление, аудит обработки и доказуемая минимизация данных.

**Риски:**  
- пользователь запросил удаление, но фото остались в S3;
- privacy receipt не соответствует фактической AI-обработке;
- в логи попадают URL к приватным изображениям или Telegram данные;
- нельзя доказать, какой provider/model обрабатывал данные;
- регуляторные и репутационные риски.

**Как исправить правильно:**  
1. Реализовать privacy service для удаления аккаунта, uploads, image assets, AI requests, receipts и связанных объектов.
2. Удалять S3-объекты через background job с retry и финальным статусом.
3. Ввести retention policy для originals, failed uploads, logs и generated assets.
4. Создавать `privacy_receipts` только из реального AI pipeline.
5. Запретить логирование presigned URLs, Telegram initData, tokens и приватных payload'ов.
6. Добавить audit events для privacy-sensitive действий.

**Какие проверки добавить:**  
- integration tests delete account removes DB rows and S3 objects;
- tests delete-original removes object and records timestamp;
- tests logs do not contain secrets/presigned URLs/initData;
- e2e privacy receipt after AI processing;
- periodic audit job for orphan S3 objects and orphan DB assets;
- алерты на failed deletion jobs и orphan object growth.

**Критерий готовности:**  
Удаление данных выполняется фактически, проверяемо и идемпотентно; privacy receipts создаются из реального pipeline; sensitive data не попадает в логи.

---

### Блокер 8. Billing и usage limits не реализованы, но присутствуют в публичном API

**Проблема:**  
Есть планы и модели платежей, но нет создания invoice, provider webhook, подтверждения оплаты, subscription lifecycle и enforcement лимитов. API показывает тарифные ограничения, но backend не применяет их к uploads/items/AI.

**Почему это критично:**  
Если billing доступен пользователям, production должен корректно обрабатывать деньги. Если billing не готов, его нельзя показывать как рабочую функцию. Для AI-продукта usage limits также нужны для контроля стоимости даже без монетизации.

**Риски:**  
- пользователь платит, но подписка не активируется;
- бесплатный пользователь бесконечно запускает дорогие AI-задачи;
- webhook можно подделать или повторить;
- chargeback/support incidents;
- неконтролируемые расходы на provider'ов.

**Как исправить правильно:**  
1. Принять решение для MVP: полностью реализовать billing или скрыть paid flows за feature flag.
2. Реализовать provider adapters для Telegram Payments/external provider.
3. Валидировать webhooks подписью/provider secret.
4. Хранить idempotency по provider payment id.
5. Обновлять `subscriptions` и `usage_limits` транзакционно.
6. Проверять лимиты до создания upload/AI task/item.
7. Добавить admin/support read-only view для платежных событий.

**Какие проверки добавить:**  
- unit-тесты plan limits;
- integration tests invoice -> payment webhook -> subscription active;
- tests duplicate webhook does not double-activate;
- tests failed/refunded payment changes access;
- load tests limit checks on hot paths;
- алерты на payment failures, webhook signature failures, AI quota bypass attempts.

**Критерий готовности:**  
Платёжные сценарии идемпотентны, подписки обновляются корректно, лимиты применяются на дорогих операциях, неготовые paid-функции скрыты от пользователей.

---

### Блокер 9. Docker Compose и runtime-конфигурация ориентированы на разработку, а не на production

**Проблема:**  
API запускается с `--reload`, Mini App запускается через Vite dev server и `npm install` при старте контейнера, используются default secrets, PostgreSQL/Redis/MinIO проброшены наружу host ports, нет reverse proxy/TLS/static serving конфигурации.

**Почему это критично:**  
Development runtime не предназначен для надёжной работы с большим количеством пользователей. Он медленнее стартует, менее предсказуем, может раскрыть внутренние сервисы наружу и не даёт стабильного immutable artifact.

**Риски:**  
- API reload создаёт лишние процессы и нестабильность;
- npm install на старте ломает воспроизводимость deploy;
- БД/Redis/MinIO доступны извне;
- default JWT/S3/Postgres secrets приводят к компрометации;
- нет TLS и корректной Telegram Mini App HTTPS URL;
- сложно откатиться на предыдущую версию.

**Как исправить правильно:**  
1. Разделить `docker-compose.local.yml` и production manifests.
2. Собрать immutable images: API без `--reload`, Mini App как static `dist`.
3. Использовать reverse proxy/load balancer с TLS, HSTS, sane timeouts и body size limits.
4. Убрать наружные ports для DB/Redis/MinIO; доступ только внутри private network.
5. Запрещать запуск `APP_ENV=production` с default secrets.
6. Добавить health/readiness/liveness checks для API, worker, bot и frontend.
7. Настроить rolling deploy и rollback strategy.

**Какие проверки добавить:**  
- smoke tests production image start;
- config validation tests for production env;
- container vulnerability scanning;
- test no default secrets in production;
- test internal services are not externally reachable;
- deployment smoke: migrations -> API health -> Mini App static -> bot webhook.

**Критерий готовности:**  
Production запускается из immutable images, без dev server/reload/default secrets, внутренние сервисы закрыты, TLS настроен, deploy и rollback воспроизводимы.

---

### Блокер 10. Миграции БД не готовы для безопасной эволюции production-схемы

**Проблема:**  
Initial migration использует `Base.metadata.create_all()` и `drop_all()`. Для production это плохо контролируемо: review не показывает явных DDL-операций, downgrade разрушителен, а будущие изменения схемы сложно валидировать.

**Почему это критично:**  
База данных станет центральным состоянием приложения. При высокой нагрузке неконтролируемые миграции могут заблокировать таблицы, потерять данные или сломать старые версии приложения во время rolling deploy.

**Риски:**  
- случайное удаление всех таблиц при downgrade;
- невозможность безопасно ревьюить изменения схемы;
- долгие locks на больших таблицах;
- несовместимость старого и нового кода при rolling deploy;
- отсутствие индексов для highload queries.

**Как исправить правильно:**  
1. Заменить `create_all/drop_all` на явные Alembic operations.
2. Добавить migration review policy: expand/contract, backward-compatible changes.
3. Для больших таблиц использовать online-safe подходы: nullable column -> backfill -> constraint.
4. Добавить индексы под реальные query patterns.
5. Проверять миграции на staging snapshot.
6. Запретить destructive downgrade в production.

**Какие проверки добавить:**  
- migration tests upgrade from empty DB;
- migration tests upgrade from previous schema with data;
- SQL review for locks and missing indexes;
- performance tests for core queries on large datasets;
- backup/restore drill before destructive changes;
- алерты на migration duration/failures.

**Критерий готовности:**  
Миграции явные, ревьюируемые, совместимые с rolling deploy, протестированы на данных и не содержат небезопасного `drop_all` для production.

---

### Блокер 11. Нет rate limiting, backpressure и защиты от перегрузки дорогих операций

**Проблема:**  
Нет Redis-backed rate limiting для API, upload, auth, AI и marketplace/research операций. Нет backpressure при росте очередей, нет per-user concurrency limits, нет защиты от массовых загрузок и повторных AI-запросов.

**Почему это критично:**  
Highload-приложение с AI и загрузкой изображений должно ограничивать дорогостоящие операции. Без ограничений один пользователь, бот или сбой frontend может перегрузить API, очередь, S3, OpenRouter и базу.

**Риски:**  
- дорогостоящий AI provider получает всплеск запросов;
- Redis/Celery queue растёт без контроля;
- API деградирует для всех пользователей;
- auth/upload endpoints используются для abuse;
- расходы превышают бюджет за минуты.

**Как исправить правильно:**  
1. Добавить Redis-backed rate limiter для auth, uploads, AI, polling status и marketplace.
2. Ввести per-user и global concurrency limits для AI задач.
3. Добавить queue length thresholds: reject/defer новые задачи при перегрузке.
4. Ограничить file size, request body size и частоту upload retries.
5. Добавить idempotency keys для дорогих POST операций.
6. Настроить Celery routing по очередям и worker autoscaling policy.

**Какие проверки добавить:**  
- unit-тесты rate limit policies;
- integration tests `429 Too Many Requests`;
- нагрузочные тесты spike traffic;
- tests queue saturation returns controlled errors;
- метрики queue depth, rejected requests, per-user usage, provider spend;
- алерты на high queue lag, AI spend spike, 429 anomaly, worker crash loop.

**Критерий готовности:**  
Система ограничивает дорогостоящие операции, сохраняет доступность при пиках, возвращает контролируемые ошибки и не допускает неограниченного роста очередей/расходов.

---

### Блокер 12. Нет observability: метрик, трассировки, алертов и эксплуатационных SLO

**Проблема:**  
Есть базовое логирование, но нет централизованных structured logs, метрик, distributed tracing, алертов, dashboards, SLO и runbooks. Health endpoint не проверяет зависимости: БД, Redis, S3, Celery, provider availability.

**Почему это критично:**  
В production с большим числом пользователей сбои неизбежны. Без observability команда узнает о проблемах от пользователей, не сможет быстро понять причину деградации и не увидит рост AI cost или очередей.

**Риски:**  
- инцидент обнаруживается слишком поздно;
- невозможно понять, где проблема: API, DB, Redis, S3, worker, OpenRouter или Telegram;
- нет алертов на рост ошибок и latency;
- нет данных для capacity planning;
- невозможно доказать выполнение SLO.

**Как исправить правильно:**  
1. Ввести structured JSON logs с request id/correlation id/user id hash/task id.
2. Добавить Prometheus/OpenTelemetry metrics для API, DB, Redis, Celery, S3, AI provider, Telegram.
3. Добавить distributed tracing для request -> queue -> worker -> DB/provider.
4. Разделить `/health/live` и `/health/ready`.
5. Настроить dashboards: API latency/error, queue lag, DB pool, worker throughput, AI cost, upload failures.
6. Настроить alerts с конкретными thresholds и runbooks.

**Какие проверки добавить:**  
- tests health readiness fails when DB/Redis unavailable;
- smoke test metrics endpoint exposes required metrics;
- trace propagation tests for async task flow;
- log redaction tests for secrets/private URLs;
- alert simulation in staging;
- регулярный review SLO/SLA dashboards.

**Критерий готовности:**  
Любой production-инцидент виден через метрики/логи/трейсы, есть алерты до массового влияния на пользователей, health checks отражают состояние зависимостей.

---

### Блокер 13. Недостаточное тестовое покрытие production-сценариев и нестабильная воспроизводимость тестов

**Проблема:**  
Текущие тесты в основном контрактные и проверяют наличие endpoint'ов/строк. Без `PYTHONPATH` локальный `pytest` не собирается. Один тест зависит от значения `OPENROUTER_API_KEY` в локальном `.env`. Нет интеграционных тестов с PostgreSQL/Redis/S3/Celery, нет e2e для основного сценария, нет нагрузочных тестов.

**Почему это критично:**  
Production-релиз без воспроизводимых тестов создаёт высокий риск регрессий. Для highload важно проверять не только корректность ответов, но и транзакции, очереди, ретраи, лимиты, производительность и восстановление после сбоев.

**Риски:**  
- CI пропускает критические ошибки pipeline;
- тесты проходят у одного разработчика и падают у другого;
- реальные интеграции ломаются только в production;
- нет confidence для rolling deploy;
- невозможно безопасно рефакторить stub-код в production services.

**Как исправить правильно:**  
1. Настроить packaging/CI так, чтобы тесты запускались через install editable или корректный `PYTHONPATH`.
2. Изолировать тестовое окружение от локального `.env`.
3. Добавить pytest fixtures для Settings, PostgreSQL, Redis, S3-compatible storage.
4. Добавить integration tests для auth, uploads, AI task state, CRUD, privacy deletion, billing limits.
5. Добавить Playwright e2e для Mini App.
6. Добавить load tests через k6/Locust для API, uploads, status polling и AI enqueue.
7. В CI запускать lint, format check, mypy, pytest, frontend typecheck/build, migrations check, image build.

**Какие проверки добавить:**  
- unit/integration/e2e/load/security test suites;
- contract tests для OpenAPI;
- migration tests;
- frontend visual regression;
- CI на Python 3.12;
- flaky test detection и test duration monitoring.

**Критерий готовности:**  
CI полностью воспроизводим, не зависит от локального `.env`, покрывает основной пользовательский путь и блокирует merge/deploy при регрессиях.

---

### Блокер 14. Нет стратегии отказоустойчивости, graceful shutdown и восстановления после сбоев

**Проблема:**  
Не описано и не реализовано поведение при падении API, worker, Redis, PostgreSQL, S3, OpenRouter и Telegram. Нет dead-letter queue, нет компенсационных задач, нет graceful shutdown для in-flight jobs, нет backup/restore drill.

**Почему это критично:**  
При высокой нагрузке частичные сбои неизбежны. Production-ready система должна деградировать контролируемо, не терять пользовательские данные и восстанавливаться после ошибок без ручного исправления БД.

**Риски:**  
- AI-задачи зависают навсегда в `processing`;
- повторные retries создают дубли и лишние расходы;
- при падении Redis теряются queued tasks;
- при сбое S3 остаются orphan DB rows;
- deploy убивает in-flight обработку;
- backup есть формально, но восстановление не проверено.

**Как исправить правильно:**  
1. Описать failure modes для каждого компонента.
2. Добавить Celery task states, retry policy, timeout, max retries и dead-letter handling.
3. Реализовать reconciliation jobs: stuck uploads, orphan assets, failed deletion, missing receipts.
4. Настроить graceful shutdown API/worker/bot.
5. Использовать managed PostgreSQL/Redis/S3 или production-кластеры с backup/replication.
6. Настроить регулярные backups и restore drills.
7. Добавить runbooks для provider outage, DB degradation, queue saturation, bad deploy.

**Какие проверки добавить:**  
- chaos tests: provider timeout, Redis restart, worker kill, API restart;
- tests stuck task recovery;
- backup/restore test on staging;
- deployment test with in-flight jobs;
- alert tests for DLQ/stuck processing;
- metrics for task age, retry exhaustion, recovery job results.

**Критерий готовности:**  
Система переживает частичные сбои без потери данных, зависшие состояния автоматически восстанавливаются или алертятся, deploy не прерывает критические операции неконтролируемо.

---

## 4. Обязательные проверки перед production

### 4.1 Функциональные проверки

- Проверка основного пользовательского сценария: Telegram auth -> Mini App opens -> upload photo -> S3 object created -> Celery AI task -> item/look saved -> result visible in wardrobe.
- Проверка Telegram photo flow: user sends photo -> bot registers upload -> file copied to S3 -> processing status visible in Mini App.
- Проверка CRUD гардероба: list, get, patch, confirm, hide, wear, delete.
- Проверка outfits: generate from wardrobe, generate with anchors, favorite, rate, select, wear.
- Проверка wishlist: create, list, update, delete with real DB persistence.
- Проверка style DNA/rules: create/update/list with user isolation.
- Проверка обработки ошибок: invalid token, expired token, missing object, failed AI provider, corrupted image, quota exceeded.
- Проверка граничных случаев: пустой гардероб, очень большой гардероб, повторная загрузка, duplicate webhook, retry после transient error.

### 4.2 Проверки безопасности

- Проверка Telegram `initData` validation, истечения `auth_date` и некорректной подписи.
- Проверка JWT expiration, refresh rotation, logout/revoke.
- Проверка user isolation для всех объектов по `user_id`.
- Проверка хранения секретов: production не стартует с default `JWT_SECRET_KEY`, default DB/S3 passwords и пустыми обязательными secrets.
- Проверка защиты от инъекций: SQLAlchemy parameterized queries, строгие DTO, запрет произвольных storage keys.
- Проверка upload security: content type, magic bytes, image decode, max size, path traversal protection.
- Проверка webhook security: Telegram secret token, payment provider signatures, idempotency.
- Проверка логирования чувствительных данных: tokens, initData, presigned URLs, Telegram file ids и приватные payload'ы не попадают в logs/traces.
- Проверка CORS: разрешены только production Mini App domains.
- Проверка dependency/container vulnerability scanning.

### 4.3 Проверки производительности

- Нагрузочное тестирование API read/write endpoint'ов с реалистичным профилем пользователей.
- Проверка p95/p99 latency для auth, wardrobe list, upload init, upload status, outfit generation enqueue.
- Проверка PostgreSQL под нагрузкой: индексы, slow queries, connection pool, lock contention.
- Проверка Redis и Celery: queue depth, queue lag, worker throughput, retry rate.
- Проверка S3-compatible storage: presigned URL generation, parallel upload complete, object cleanup.
- Проверка AI enqueue под нагрузкой с per-user/global limits.
- Проверка frontend: bundle size, initial load, API waterfall, Telegram WebView performance.
- Проверка capacity plan: сколько API replicas, workers, DB connections и Redis memory нужно на целевой RPS.

### 4.4 Проверки отказоустойчивости

- Проверка поведения при падении API во время upload complete.
- Проверка поведения при падении worker во время AI-задачи.
- Проверка Redis restart и восстановления очередей.
- Проверка PostgreSQL degradation: timeouts, retry policy, readiness failure.
- Проверка S3 outage: controlled error, retry, no false completed status.
- Проверка OpenRouter outage: task status failed/retryable, budget not double-counted.
- Проверка Telegram webhook retries and duplicate update handling.
- Проверка graceful shutdown API, worker и bot.
- Проверка backup/restore PostgreSQL и object storage.
- Проверка rollback после failed deploy.

### 4.5 Проверки наблюдаемости

- Логи: structured JSON, correlation id, request id, user id hash, task id, no sensitive data.
- Метрики: API RPS/error/latency, DB pool, Redis latency, Celery queue lag, worker failures, S3 errors, AI cost/tokens/errors.
- Трейсинг: request -> DB -> queue -> worker -> provider -> DB.
- Алерты: high 5xx, high p95 latency, queue lag, worker crash, DB connection exhaustion, AI cost spike, failed deletions, webhook failures.
- Health checks: `/health/live` для процесса, `/health/ready` для зависимостей.
- Dashboards: API, workers, DB, Redis, S3, AI provider, Telegram, billing, privacy jobs.
- Runbooks: что делать при provider outage, queue saturation, DB locks, bad deploy, data deletion failures.

---

## 5. План доведения проекта до production-ready состояния

### Этап 1. Закрыть критические блокеры

1. Реализовать production auth: Telegram user upsert, sessions, refresh/logout, user-scoped dependencies.
2. Заменить stub routers на сервисы с PostgreSQL persistence.
3. Переписать upload pipeline на S3 + DB + Celery task orchestration.
4. Замкнуть AI pipeline: worker сохраняет результаты, receipts, costs, statuses.
5. Подключить Mini App к реальному authenticated API и убрать демо-данные из основных flows.
6. Перевести Telegram bot на webhook и реализовать idempotent photo flow.
7. Реализовать privacy deletion lifecycle и audit trail.
8. Ввести usage limits/rate limits для AI, uploads и auth.
9. Либо полностью реализовать billing, либо скрыть paid flows из MVP.

### Этап 2. Добавить обязательные проверки

1. Настроить CI на Python 3.12 с воспроизводимым окружением.
2. Изолировать тесты от локального `.env`.
3. Добавить integration tests с PostgreSQL, Redis и S3-compatible storage.
4. Добавить Celery worker tests с реальными task side effects.
5. Добавить Playwright e2e для Mini App и Telegram auth mock.
6. Добавить security tests для auth, user isolation, upload validation и secret redaction.
7. Добавить load tests для API, uploads, status polling и AI enqueue.
8. Добавить migration tests и OpenAPI contract checks.

### Этап 3. Подготовить инфраструктуру

1. Разделить local и production compose/manifests.
2. Собрать production Docker images без dev server, reload и runtime install.
3. Настроить TLS reverse proxy/load balancer.
4. Закрыть наружный доступ к PostgreSQL, Redis и object storage.
5. Настроить managed или production-grade PostgreSQL, Redis и S3.
6. Добавить secrets management и startup validation.
7. Настроить migrations-on-deploy с backup перед миграциями.
8. Настроить observability stack: logs, metrics, traces, alerts, dashboards.
9. Настроить backups, restore drills и rollback plan.

### Этап 4. Провести тестовый запуск

1. Развернуть staging, максимально близкий к production.
2. Прогнать полный e2e: auth -> upload -> AI -> wardrobe -> outfit -> privacy receipt.
3. Провести нагрузочное тестирование на целевых RPS/concurrency.
4. Провести chaos-проверки: worker kill, Redis restart, OpenRouter timeout, S3 failure.
5. Проверить алерты и runbooks на staging-инцидентах.
6. Проверить backup/restore на staging data snapshot.
7. Провести security review и dependency/container scan.
8. Исправить все найденные Critical/High issues до релиза.

### Этап 5. Подготовить релиз

1. Зафиксировать release candidate image tags.
2. Заморозить схему API и миграции для релиза.
3. Подготовить production `.env`/secrets без default values.
4. Проверить Telegram webhook URL, Mini App HTTPS URL и bot menu.
5. Выполнить production smoke на минимальном трафике.
6. Включить постепенный rollout или limited beta.
7. Мониторить SLO, queue lag, AI cost, error rate и user reports.
8. Иметь готовый rollback и feature flags для отключения AI/billing/marketplace flows.

---

## 6. Финальный production checklist

- [ ] Все критические блокеры закрыты.
- [ ] Все обязательные тесты проходят в CI на Python 3.12.
- [ ] Все основные API endpoint'ы работают с БД и user isolation.
- [ ] Telegram auth создаёт стабильного пользователя и рабочие сессии.
- [ ] Refresh/logout/revoke реализованы.
- [ ] Upload pipeline работает через S3, PostgreSQL и Celery.
- [ ] AI pipeline сохраняет результаты, статусы, receipts и costs.
- [ ] Mini App использует authenticated API, а не демо-данные.
- [ ] Bot работает через webhook с secret validation.
- [ ] Privacy deletion реально удаляет DB rows и S3 objects.
- [ ] Billing либо production-ready, либо скрыт за feature flag.
- [ ] Usage limits и rate limits применяются на дорогих операциях.
- [ ] Настроены structured logs.
- [ ] Настроены метрики.
- [ ] Настроены алерты.
- [ ] Настроены traces.
- [ ] Настроены health checks и readiness checks.
- [ ] Секреты не хранятся в коде и default secrets запрещены в production.
- [ ] Production images не используют dev server, `--reload` и runtime install.
- [ ] PostgreSQL, Redis и object storage не доступны напрямую из интернета.
- [ ] Миграции явные, проверены и совместимы с rolling deploy.
- [ ] Есть backup/restore процедура и она проверена.
- [ ] Есть rollback-план.
- [ ] Есть документация по запуску.
- [ ] Есть инструкция по эксплуатации и runbooks.
- [ ] Проведено нагрузочное тестирование.
- [ ] Проведена проверка безопасности.
- [ ] Проведён staging запуск с production-like конфигурацией.

---

## 7. Итоговое заключение

Сейчас приложение нельзя выпускать в `prod`.

Минимальная причина: проект пока не сохраняет и не обрабатывает основной пользовательский сценарий end-to-end на production-уровне. Auth не создаёт стабильного пользователя, API в основном возвращает заглушки, uploads живут в памяти/локальной папке, AI pipeline не сохраняет результаты, Mini App показывает демо-данные, bot не готов к highload webhook deployment, а observability и rate limiting отсутствуют.

Выпуск станет допустимым только после закрытия критических блокеров: полноценная авторизация и user isolation, реальные persistent API-сервисы, надёжный upload/AI pipeline через S3/Celery/PostgreSQL, production-ready Mini App и bot, privacy deletion, usage limits, безопасный production deployment, миграции, observability, отказоустойчивость и воспроизводимый CI с интеграционными/e2e/нагрузочными проверками.
