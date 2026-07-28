# Claude Code Opus — independent read-only review

Дата: 2026-07-28 23:35–23:38 Europe/Moscow.

## Команда

```powershell
$reviewPrompt = Get-Content -LiteralPath docs/reviews/CLAUDE_DESIGN_REVIEW_PROMPT.md -Raw
& 'C:\Users\GF62\.local\bin\claude.exe' `
  -p `
  --model opus `
  --effort high `
  --permission-mode plan `
  --tools 'Read,Grep,Glob' `
  --no-session-persistence `
  --max-budget-usd 2 `
  $reviewPrompt
```

CLI: Claude Code `2.1.205`. Запрошенных пользователем идентификаторов `Opus 4.8`/`Opus 5` CLI не показывал; использован поддерживаемый alias `opus`. Первый запуск до 23:30 был заблокирован сообщением `You've hit your session limit · resets 11:30pm (Europe/Moscow)`. Повторный запуск после reset завершился с exit code 0.

Отдельного инструмента с названием `Cloud Code Design` в окружении не найдено. Его функциональная роль покрыта read-only Opus review плюс собственный Chromium UX audit; несуществующий вызов не симулировался.

## Проверка выводов

Приняты и применены:

- editor был rectangle-only, а interactive stage ошибочно имел `role=img`;
- добавлены keyboard move/resize и focus ring;
- failed request больше не занимает месячный quota slot;
- удалено дублирующее присваивание `original_image_id`;
- migration baseline, dead `UsageLimit`, image proxy и отдельное avatar reference остаются явными backlog items;
- Go rewrite не обоснован.

Не принято как достаточное доказательство:

- `conditional ship` не означает production-ready: reviewer не запускал браузер, E2E, latency или PostgreSQL migrations;
- оценка `7/10` субъективна и не заменяет screen/task evidence.

## Stdout

```text
Инструмент записи файлов недоступен в этом контексте, поэтому привожу итог аудита прямо в ответе. Это read-only аудит — изменений в коде не выполнялось и не предлагается.

# Независимый аудит AI Wardrobe

Источники: `PROJECT_MASTER_PROMPT.md`, `IMPROVEMENTS.md`, `models.py`, `billing.py`, `entitlements.py`, `usage.py`, роутеры `avatar/billing/uploads`, `App.tsx` (редактор + Studio), миграции `0002/0003/0004`.

## 1. UX и визуальная архитектура

**Факты:** редактор области (`App.tsx:686-1015`) делает клиентский crop до upload (`cropImageFile:116-152`), режимы «Только область / Всё фото», pointer-события с `setPointerCapture`, undo/redo/reset, `role=progressbar`+`aria-valuenow` (`:991-995`). На сервер уходит только подтверждённый crop (`:826-827`). Studio (`:1346-1806`) показывает честный дисклеймер try-on «не гарантирует физическую посадку» (`:1765`), обязательный consent (`:1738`), кнопку тарифа `disabled`→«Оплата скоро» без dark-pattern (`:1636-1638`).

**Проблемы (доказано):**
- Редактор — **один прямоугольник**, не Photoshop-mask: нет add/subtract, zoom/pan, реальной сегментации. `DEFAULT_PERSON_SELECTION` — статичная догадка, не auto-detection (честно помечена). Требование п.8 выполнено **частично**.
- `role="img"` на интерактивном stage (`:915`) семантически неверно; **нет keyboard-способа** менять прямоугольник (только pointer) → доступность keyboard-only не покрыта.
- Studio перегружен (тарифы+промо+аватар+примерка в одном скролле).

## 2. Архитектура, приватность, безопасность, производительность

**Крепко:** user-isolation везде фильтрует `user_id`, image-эндпоинты доп. проверяют `image.user_id` (`avatar.py:259,383`); промокоды — HMAC-SHA256 (`entitlements.py:37-40`); redemption атомарен (`FOR UPDATE` `:130` + уникальность `models.py:503`); квота лочит строку `User` `FOR UPDATE` (`usage.py:58`); отзыв аватара реально удаляет S3+строки, при сбое → 503 (`avatar.py:148-195`); без `real_ai_enabled` — `provider_not_configured`, без фейков (`:213-217, 317-321`).

**Риски (доказано):**
- **Проксирование картинок через event loop** (`avatar.py:261-262, 385-386`) без presigned URL и cache-заголовков.
- **Failed съедает квоту**: `usage.py:83-90` считает все `AiRequest` без фильтра по статусу → `queue_unavailable` теряет платный слот.
- **Face-reference неоднозначен**: аватар берёт «последнее фото» (`avatar.py:106-113`), но загрузки кропаются под одежду → лицо может быть вырезано.

## 3. Нормализация БД

1. **`UsageLimit` (`models.py:517-533`)** — `item_limit/ai_analysis_limit` зависят от `plan` (не ключ) → **нарушение 3НФ**; при этом `usage.py` считает по `count(AiRequest)` и таблицу не использует → **мёртвая схема**.
2. **План дублируется в 3 местах**: `User.subscription_plan`, `Subscription.plan`, `PromoRedemption.plan` → integrity-риск рассинхрона (`entitlements.py:64-117`).
3. **JSONB-массивы** (`GarmentItem`, `User.preferred_*`) — формально <1НФ, приемлемо как осознанная денормализация, но стоит задокументировать.

Корректно: partial-unique на активной подписке, `uq_ai_requests_analysis_task` (idempotency), check-constraints (0004).

## 4. Критические дефекты

- **P1 — миграции строятся из живой ORM-метадаты**: `0002:18`, `0003:33-36` вызывают `__table__.create(checkfirst=True)`, `0004:18-19` признаёт «builds from live metadata». Миграция не является снимком → на свежей БД воспроизводит текущую модель, `checkfirst` маскирует drift, up/down ненадёжны.
- **P2** — квота за неуспех (`usage.py:83-90`).
- **P2** — дубль присвоения `original_image_id` (`uploads.py:150` и `:154`).
- **P2** — мёртвая `UsageLimit`.

**Не подтверждено (нет запуска/браузера):** реальный E2E, latency p50/p95/p99, миграция up/down на disposable PostgreSQL, визуал в Telegram WebView.

---

## Итог

**Вердикт: `conditional ship`.** Ядро приватности/безопасности честное и крепкое, дыр не найдено. Условия запуска — воспроизводимость миграций и подтверждённый E2E/latency на реальном стеке.

**P0/P1/P2:**
- **P0** — прогнать миграции up/down на disposable PostgreSQL и перевести `0002/0003` на явный DDL.
- **P0** — подтвердить E2E happy-path на реальном стеке (upload→crop→S3→Celery→item; avatar/try-on при `real_ai_enabled`).
- **P1** — отдавать avatar/try-on через presigned URL + cache вместо проксирования байтов.
- **P1** — отдельный consent-flow фото-лица (не переиспользовать garment-cropped upload).
- **P2** — не списывать квоту за `FAILED`; решить судьбу `UsageLimit`.

**Перенос на Go — не нужен.** Узкие места I/O-bound (БД, S3, OpenRouter, брокер) и клиентские waterfalls; измеренного CPU-хотспота нет. Единственный тяжёлый путь (картинки) лечится presigned URL/CDN в текущем стеке. Rewrite = риск без доказанного выигрыша.

**Дизайн: 7/10.** Плюсы: mobile-first, честные состояния/дисклеймеры, приличная a11y. Минусы: редактор-прямоугольник без mask/zoom/keyboard, перегруженный Studio, `role="img"` на интерактиве. Финальная WebView-проверка не проводилась.
```

Секретов в выводе не было; stderr пуст.
