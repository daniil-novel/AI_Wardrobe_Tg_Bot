# Performance baseline

Дата: 2026-07-29.

## Что измерено

Команда:

```powershell
uv run --extra dev python scripts/benchmark-api.py
```

Harness использует FastAPI `TestClient`, один процесс, 500 последовательных запросов на маршрут, `perf_counter` и `tracemalloc`. Логи во время измерения отключены. Это synthetic in-process evidence: нет TCP/TLS, PostgreSQL, Redis, S3, Celery, Telegram или внешнего AI.

## Результат

| Маршрут | RPS | p50 | p95 | p99 | max | peak traced memory |
|---|---:|---:|---:|---:|---:|---:|
| `/` | 191.72 | 4.910 ms | 6.788 ms | 8.625 ms | 58.834 ms | 0.409 MiB |
| `/billing/plans` | 189.99 | 4.930 ms | 7.923 ms | 9.443 ms | 14.605 ms | 0.385 MiB |

Предыдущий прогон в той же сессии дал 172–173 RPS и p95 7.6–8.3 ms. Рост до 190 RPS нельзя приписать изменению кода: последовательный TestClient чувствителен к warm-up, фоновым процессам и частоте CPU. Практический вывод — оба прогона находятся в одном классе, явного CPU regression на публичных маршрутах нет.

## Frontend bundles

| Сборка | JS raw / gzip | CSS raw / gzip |
|---|---:|---:|
| До editor/avatar/subscription UI | 189.98 / 60.29 kB | 14.67 / 3.62 kB |
| Subscription (final) | 214.31 / 66.85 kB | 21.76 / 4.78 kB |
| Open (final) | 210.33 / 65.90 kB | 21.76 / 4.78 kB |

Цена новых функций: финальный subscription JS вырос на `24.33 kB` raw и `6.56 kB` gzip; CSS — на `7.09 kB`
raw и `1.16 kB` gzip. Open variant реально отличается и на `3.98 kB` raw JS меньше subscription variant.

## Latency budget

Для реального сценария нужно измерять отдельно:

| Сегмент | Требуемая метрика |
|---|---|
| Telegram auth | p50/p95/p99, error rate |
| upload client → S3 | bytes, time-to-first-byte, completion |
| API → broker | enqueue p95 и failures |
| queue | oldest task age и queue lag |
| provider | per-model latency, retries, cost |
| worker | total job duration и success rate |
| UI | first useful screen, wardrobe ready, editor ready |

FASHN документирует 5–8 s для performance/balanced и 12–17 s для quality у try-on v1.6; это внешний ориентир, не измерение данного приложения.

## Observability after loop

- JSON request logs: request id, route, status, duration, hashed user id;
- redaction ключей, bearer tokens и signed URLs;
- Prometheus-compatible request counter and duration histogram by route/status;
- process uptime и missing-secret gauges;
- worker logs содержат hashed job IDs и task duration;
- `ai_requests` хранит request type/status/latency hook/cost field.

Остаток: provider cost ingestion, queue metrics, DB pool wait, S3 metrics, traces и production dashboards.

## Hybrid AI latency note

Codex CLI is executed as a fresh ephemeral process on the trusted workstation for each inference. The public server
uses Redis for bounded-TTL coordination and the runner claims work through outbound authenticated HTTPS. This improves
credential isolation and enables saved ChatGPT/Codex or local OSS-provider execution, but adds process/model startup
and is not expected to beat a pooled HTTP client on throughput.

Real smoke on this Windows workstation confirmed JSON, strict schema, Russian UTF-8 and image input behavior. Three
earlier direct text probes took 6,165 ms median (min 6,051 ms; max 7,656 ms). The first complete
Redis → FastAPI claim → `codex exec` → FastAPI completion canary took about 28.2 s of inference; a repeated canary took
about 5.2 s. The lifecycle regression check then found zero leftover runner/API processes and zero listeners on the
canary port. These samples are deliberately small and exclude image understanding, load and production concurrency,
so they are observations, not an SLO benchmark.

Rollout policy:

- production default: `api`;
- privacy-oriented trusted workstation: `runner`;
- controlled migration/canary: `hybrid`; `runner_first` is safe only while the heartbeat/fallback path is monitored;
- collect `ai_requests.provider/model/latency_ms`, queue lag, success/fallback rate and cost before changing the default.

Codex is deliberately absent from all server Docker targets, avoiding credential duplication and image-size overhead.

## Production observations

These are single-run observations, not an SLO:

- final image recognition through the local runner: about 57 s;
- complete upload analysis with six API-generated product images: 104.3 s;
- avatar generation: 8.1 s;
- virtual try-on before the queue-order fix: 17.3 s;
- targeted virtual try-on after the fix: 11.0 s with one delivery and no retry.

The hybrid path optimizes control/privacy and testing flexibility, not raw latency. Product-image fan-out dominates the
full upload wall time; measure provider concurrency/cost before raising worker concurrency.

## Решение по Go

`REJECTED` для полного rewrite сейчас.

- публичные Python endpoints не показывают CPU saturation;
- upload/AI/try-on paths зависят от сети, object storage, broker и provider;
- переписывание не уменьшит 5–17 s inference latency;
- риск регрессии auth/privacy/billing выше ожидаемой выгоды.

Повторно открыть решение можно, если production-like профиль покажет устойчивый CPU-bound участок, например image preprocessing с CPU >80%, p95 выше SLO и доказанный Go prototype с минимум 2× выигрышем при приемлемом TCO.
