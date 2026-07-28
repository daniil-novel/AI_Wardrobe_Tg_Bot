# Market, competitors and pricing

Срез: 2026-07-28. Цены storefront зависят от региона и могут включать налоги. Для иллюстративного пересчёта использован официальный курс Банка России на 2026-07-28: `1 USD = 78.0172 RUB` ([Банк России](https://www.cbr.ru/eng/currency_base/dynamics/?UniDbQuery.From=01.01.2022&UniDbQuery.Posted=True&UniDbQuery.VAL_NM_RQ=R01235&UniDbQuery.date_req1=&UniDbQuery.date_req2=&UniDbQuery.mode=1&UniDbQuery.so=1)).

## Прямые аналоги

| Продукт | Модель и цена | Сильные стороны | Вывод для AI Wardrobe |
|---|---|---|---|
| Stylebook | `$4.99` one-time, ≈389 RUB | 90+ функций, closet, free-form outfits, calendar, packing, cost-per-wear, AI background removal | Низкая цена задаёт benchmark для базового organizer, но AI generation требует Apple Intelligence ([App Store](https://apps.apple.com/us/app/stylebook/id335709058)) |
| Acloset | Free до 100 вещей; Basic `$3.99`, Premium `$9.99`, Expert `$24.99` в месяц | AI stylist, community, auto-split до 4 вещей, avatar из full-body photo и try-on на своих вещах | Avatar/try-on уже не уникальны; конкурентное преимущество должно быть в controllable selection, privacy и Telegram onboarding ([App Store](https://apps.apple.com/us/app/acloset-ai-fashion-assistant/id1542311809)) |
| Whering | Free + IAP/credits; 10 credits `$2.99`, 100 `$12.99` | 9M+ users, social styling, wardrobe insights, packing, Style Pass | Сильный free/social moat; AI Wardrobe выгоднее позиционировать как private assistant, а не social network ([App Store](https://apps.apple.com/us/app/whering-your-digital-closet/id1519461680)) |
| Pureple | `$6.99/week`, `$14.99/month`, `$89.99/year` | AI outfits, virtual try-on, calendar, packing, background erase, sync | Цена выше предлагаемого Premium; продукт честно говорит, что try-on не является sizing tool — тот же дисклеймер обязателен здесь ([App Store](https://apps.apple.com/us/app/pureple-ai-outfit-planner/id628106373)) |
| Indyx | Human styling Feed от `$35/month` | Реальный стилист каждую неделю, основанный на digital wardrobe | Верхняя граница willingness-to-pay за human-in-the-loop; будущий Pro stylist mode может стоить существенно выше software-only тарифа ([Indyx](https://www.myindyx.com/blog/launching-the-feed)) |
| Cladwell | Free + IAP | Daily weather outfits, capsules, Ask Cladwell | Сильный routine/capsule use case; exact current IAP price не подтверждён в этом срезе ([App Store](https://apps.apple.com/us/app/cladwell-outfit-planner/id1140550878)) |

## Provider costs

### FASHN

[FASHN API pricing](https://help.fashn.ai/plans-and-pricing/api-pricing):

- on-demand: `$0.075` за credit, минимум 100 credits / `$7.50`;
- v1.6 virtual try-on: 1 credit = `$0.075` ≈ `5.85 RUB`;
- generation endpoints: 1–5 credits в зависимости от mode/resolution;
- face reference: ещё 3 credits;
- failed predictions не списывают credits;
- commitment tiers уменьшают стоимость credit.

[Try-on v1.6](https://docs.fashn.ai/api-reference/tryon-v1-6) заявляет 5 s performance, 8 s balanced и 12–17 s quality при 864×1296. Это provider claim, не локальный benchmark.

[Privacy guidance FASHN](https://docs.fashn.ai/api-overview/data-retention-privacy) сообщает: request history хранит параметры и submitted URLs; CDN outputs планируются к удалению через три дня; base64 output доступен до 60 минут; customer content не используется для обучения. Для face/body data предпочтительны base64 input/output или минимальный signed URL TTL.

### Replicate

[PrunaAI p-image-try-on](https://replicate.com/prunaai/p-image-try-on): `$0.015` за первую garment image и `$0.008` за каждую следующую; 4 вещи стоят `$0.039`. Это сильная цена для multi-garment preview, но перед выбором нужны quality/privacy/latency tests.

### Текущий OpenRouter provider

[Gemini 2.5 Flash Image на OpenRouter](https://openrouter.ai/google/gemini-2.5-flash-image): `$0.30 / 1M` input units и `$2.50 / 1M` output units. Без фактических usage units нельзя честно перевести это в цену одного изображения. Поэтому `ai_requests.cost_usd` пока остаётся hook, а payments выключены.

## Предлагаемые тарифы

| План | Цена | Лимиты | Позиционирование |
|---|---:|---|---|
| Free | 0 RUB | 20 вещей, 5 AI analyses, без avatar/try-on | Проверить ценность editor и базовых образов |
| Premium | 699 RUB/month | 500 вещей, 100 analyses, 2 avatars, 6 try-ons | Private personal wardrobe + controlled AI |
| Pro | 1490 RUB/month | вещи/analyses без лимита, 5 avatars, 15 try-ons | Multi-wardrobe, export, capsules, trips, stylist workflow |

699 RUB ≈ `$8.96`, то есть чуть ниже Acloset Premium `$9.99` и заметно ниже Pureple `$14.99`. 1490 RUB ≈ `$19.10`, ниже human styling Indyx `$35`.

Статус цен: **proposal**, не публичная оферта. UI маркирует их как предварительные, а payment CTA отключён.

## Unit economics

Расчёт покрывает только provider generation; не включает OpenRouter garment analysis, storage, egress, observability, поддержку, налоги, refunds и payment commission.

### Premium, полное использование

- low-cost v1.6: `6 × 1 credit`;
- avatar proxy: `2 × (1 base + 3 face) credits`;
- всего 14 credits = `$1.05` ≈ `81.92 RUB`, 11.7% от gross revenue.

Консервативный quality case:

- try-on: `6 × 5 credits`;
- avatar: `2 × 8 credits` (quality + face reference proxy);
- всего 46 credits = `$3.45` ≈ `269.16 RUB`, 38.5% gross.

### Pro, полное использование

- low-cost: `15 × 1 + 5 × 4 = 35 credits` = `$2.625` ≈ `204.80 RUB`, 13.7% gross;
- quality proxy: `15 × 5 + 5 × 8 = 115 credits` = `$8.625` ≈ `672.90 RUB`, 45.2% gross.

Верхний сценарий Pro оставляет слишком мало места для остальных COGS. До включения оплаты нужно:

1. собрать реальные credits/tokens per job;
2. выбрать конкретный provider/mode;
3. добавить remaining quota и paid top-ups;
4. задать minimum gross-margin guardrail;
5. учесть retry policy — платный лимит не должен удваиваться из-за idempotent retry.

## Дифференциация

Avatar сам по себе уже не killer feature: Acloset и Pureple предлагают try-on. Предлагаемый wedge:

1. user-controlled crop до AI, особенно в примерочной с фоновыми вещами;
2. Telegram-native zero-install onboarding;
3. explicit face/body consent, revocation и derived-image deletion;
4. сохранение реальных пропорций без slimming/beautification;
5. wardrobe-grounded stylist и explainable outfits;
6. open build без paywall для B2B/white-label deployment.

## Коммерческий gate

`ENABLE_BILLING_PAYMENTS` должен оставаться `false`, пока не выполнены:

- signed/idempotent webhook;
- фактический cost accounting;
- tested quotas under concurrency;
- privacy/legal review;
- staging load/E2E;
- refund/reconciliation/runbook;
- подтверждённый production target и rollback.
