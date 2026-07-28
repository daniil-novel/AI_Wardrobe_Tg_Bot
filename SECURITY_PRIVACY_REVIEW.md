# Security and privacy review

Дата: 2026-07-28.

## Вывод

Для commercial preview реализованы хорошие базовые границы: Telegram initData validation, JWT/refresh sessions, user-scoped queries, private S3, upload magic-byte validation, rate limits, production secret validation, structured log redaction и explicit avatar consent. После loop отзыв avatar consent удаляет производные изображения из S3 и БД.

Production payments и массовая обработка лиц/пропорций всё ещё требуют отдельного legal/security gate.

## Data classification

| Данные | Класс | Хранение | Требование |
|---|---|---|---|
| Telegram ID/profile | PII | PostgreSQL | access control, deletion/export |
| Original wardrobe photo | Private user content | S3 | private ACL, TTL/retention |
| Face/avatar reference link | Sensitive biometric-adjacent | PostgreSQL → S3 asset | explicit consent, purpose limitation |
| Body measurements | Sensitive profile data | normalized PostgreSQL rows | explicit consent, delete on revoke |
| Generated avatar/try-on | Sensitive derived image | S3 + asset row | delete on revoke |
| JWT/refresh/payment secret | Secret | env/hash only | never log/store plaintext |
| Promo plaintext | Bearer secret | shown once only | HMAC hash in DB |
| AI request metadata | Operational | PostgreSQL | no image/base64/private prompt |

## Implemented controls

### Auth and isolation

- Telegram initData signature and age validation;
- access token plus hashed refresh sessions and revocation;
- object queries include `user_id`;
- Telegram upload route requires webhook secret;
- storage keys scoped as `users/{user_id}/...`.

### Uploads

- allowlist JPEG/PNG/WebP;
- size limit;
- magic-byte/decode validation;
- sanitized filename segment;
- private object storage;
- user-controlled client crop can exclude background people/items before AI.

### Avatar consent

- explicit `consent=true`;
- version/timestamp persisted;
- no avatar generation without reference + consent;
- respectful prompt forbids slimming, reshaping, age/skin/body changes and sexualization;
- UI states simulation is not sizing guarantee;
- revoke removes description, measurement rows, face reference linkage, generated avatar, try-on jobs and derived S3 objects.

The original wardrobe photo is not automatically destroyed because it can remain necessary for the wardrobe item. Its use as an avatar reference ends when the FK is cleared. Full account deletion remains a separate privacy flow.

### Secrets and logs

- production refuses default JWT/DB/S3 secrets;
- production requires Telegram/OpenRouter/promo hash secrets;
- structured logs contain request ID, status, duration and hashed user ID;
- recursive redaction covers token/secret/key/password/initData/signed URL fields and bearer/sk-like values;
- raw photos, masks and measurements are not logged.

### Commercial controls

- payments disabled by default;
- promo code is normalized and HMAC-hashed;
- promo redemption is row-locked and bounded;
- monthly AI/avatar/try-on reservations are user-row locked;
- retry is idempotent for upload analysis;
- provider failure is surfaced, not replaced with a fake result.

## Threats and residual risks

| Threat | Current mitigation | Residual |
|---|---|---|
| IDOR | user-scoped SQL | Needs systematic route-level integration suite |
| Promo brute force | high-entropy code, hash storage, rate-limit bucket | Dedicated promo rate/attempt telemetry desirable |
| Quota race | `FOR UPDATE` user lock | Must verify on real PostgreSQL with concurrent transactions |
| Object orphan | DB/S3 orchestration | Reconciliation job still missing |
| Provider retention | inline base64 to current provider | Contract/DPA and provider-specific retention not verified |
| Face misuse | consent + purpose prompt + revoke | Legal basis, age policy and moderation not implemented |
| Payment replay | provider event unique index prepared | Webhook is not implemented |
| Log leakage | recursive redaction tests | Third-party SDK/infra logs need audit |
| Account deletion | existing privacy route | Full S3/DB cascade and restore-backup deletion need E2E |
| Abuse/cost spike | per-minute and monthly limits | Global provider budget/circuit breaker and alerts incomplete |

## Required production controls

1. Privacy policy/consent copy reviewed for applicable jurisdiction.
2. Age gate and policy for minors.
3. Provider DPA, training/retention confirmation and deletion procedure.
4. KMS/secret manager, key rotation and least-privilege S3 credentials.
5. Malware/image bomb protection and decoded pixel ceiling.
6. CSP, strict CORS origins, TLS/HSTS and reverse-proxy upload limits.
7. Payment webhook signature, replay window, event idempotency and reconciliation.
8. Dependency/container/SBOM scan.
9. Centralized security alerts and incident runbook.
10. Backup/restore plus deletion-from-backup policy.

## Logging and metrics privacy

Prometheus labels use method, normalized route and status only. User ID, promo, garment IDs and storage keys are intentionally excluded to prevent cardinality and privacy leaks. Product analytics should use consented pseudonymous events with a documented event schema, not raw request payloads.

## Decision

- Commercial preview: `ACCEPTED`.
- Real face/body pilot with explicit test users: `PARTIAL`, after provider/privacy approval.
- Public production payments: `BLOCKED`.
