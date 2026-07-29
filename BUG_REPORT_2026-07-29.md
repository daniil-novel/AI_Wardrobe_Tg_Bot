# Production bug report — 2026-07-29

Scope: hybrid API + local Codex runner release, Telegram Mini App at 390×844, all six tabs, selection editor,
subscriptions/promo, avatar and virtual try-on.

## Final status

**GO for controlled production testing.** The final full pass completed upload recognition, wardrobe, Designer,
Favorites, promo access, avatar and try-on with zero browser console errors, failed requests or measured layout issues.
The post-review Favorites pass also returned seven collages/seven images, `390 == 390` viewport width and no failed
requests. Payments intentionally remain disabled.

## Findings and resolution

| ID | Severity | Finding and evidence | Resolution | Verification |
| --- | --- | --- | --- | --- |
| BR-01 | External | The bundled in-app browser kernel failed before executing JavaScript with Windows `os error 3`. | Used an isolated Playwright Chromium fallback; did not claim the broken surface worked. | 21 production screenshots plus JSON trace were produced. The host/plugin issue remains external. |
| BR-02 | P1 | The first runner canary left the Python/Codex child alive because the PID represented the wrapper. | Start script now persists the real Python PID; stop script terminates its process tree. | Repeated lifecycle canary left zero processes/listeners. |
| BR-03 | P1 | A Redis relay exception could bypass hybrid fallback. | Relay failures are normalized as `CodexRunnerUnavailable`; API mode remains unchanged. | Runner-offline production probe completed through OpenRouter. |
| BR-04 | P0 deploy | Migration `0004` met four legacy duplicate `(task_id, analyze_image)` reservations. | Migration preserves audit rows but clears duplicate task links before creating the partial unique index. | Exact production dump clone and production upgrade both reached `0005`. |
| BR-05 | P0 config | Production correctly failed closed because `PROMO_HASH_SECRET` was absent. | Generated a dedicated secret directly on the VPS; it was never printed or committed. | One-day promo was created and redeemed by the synthetic E2E user. |
| BR-06 | P1 | A direct Mini App upload created `Upload` before flushing `ImageAsset`, leaving `original_image_id = NULL`; avatar save returned 404. | Flush image first; migration `0005` repairs only unambiguous same-user/same-source/same-timestamp pairs. | Exact dump clone: broken links `1 → 0`; production null-link count `0`; avatar profile, avatar and try-on completed. |
| BR-07 | P1 | Sequential Celery tasks reused an asyncpg pool from a closed event loop (`Future attached to a different loop`). | One persistent asyncio loop is now reused per prefork worker process. | Regression test plus final upload/avatar/try-on sequence; no cross-loop exception after deploy. |
| BR-08 | P2 | A new user's expected missing avatar profile returned 404, producing browser console/network noise. | `GET /avatar/profile` returns JSON `null` with 200 when no profile exists. | Final full pass: zero console errors and zero failed requests. |
| BR-09 | P1 UX | Confidence badges expanded narrow garment metadata, causing root widths of 413–416 px at a 390 px viewport. | Constrained the text flex child and made badges non-shrinking within the card. | Final full pass: every recorded step has `scrollWidth == clientWidth == 390`. |
| BR-10 | P1 ops | `/opt/ai-wardrobe/logs` was root-owned; API/worker disabled rotating-file logging and used stdout only. | Set UID/GID `10001`, mode `0750`, and documented server preparation. | `api.log` and `worker.log` are writable, growing and owned by `10001:10001`; stdout remains available. |
| BR-11 | P1 | A fast worker consumed a try-on message before its transaction committed and retried `Try-on job not found`. | Avatar/try-on state and quota reservation now commit before broker delivery. | Targeted real try-on: one receive, success in 11.0 s, no retry/not-found, no browser failures. |
| BR-12 | P1 UX | Saved outfit cards contained copy/actions but no visual identity. | Favorites now fetch bounded-concurrency item images and render one-to-four-item collages. | Post-review browser pass: 7 cards, 7 collages, 7 images, no overflow/failures. |
| BR-13 | P2 UX | `VIRTUAL TRY-ON` remained in English in the Russian Studio. | Localized to `Виртуальная примерка`. | Static build passed and final DOM check found no English label. |
| BR-14 | P2 ops | Windows-created static tar entries arrived mode `0777`. | Production static directories/files normalized to `0755/0644` after atomic activation. | `ls -l` confirms root-owned, non-writable assets. |

## Final production evidence

- Hybrid health: `ready`, `runner_first`, OpenRouter configured, local Codex runner connected.
- Full E2E: upload `Готово`, 18 wardrobe items, avatar `completed`, try-on `completed`, `0/0/0` browser
  errors/failed requests/issues.
- Local runner performed the recognition call; OpenRouter performed product/avatar/try-on pixel generation.
- Backend: 138 tests passed, 70.11% coverage (gate 67%), Ruff and Mypy passed.
- Frontend: TypeScript and subscription production build passed; final JS 214.31 kB / 66.85 kB gzip.
- PostgreSQL schema: Alembic `0005_upload_image_links`.

## Accepted limitations

- `ENABLE_BILLING_PAYMENTS=false`: plans, entitlements, quotas and promos are live; payment capture/webhooks are not.
- Avatar fidelity was tested on a fictional adult fixture, not a consented real person's biometric reference.
- The editor provides a rectangular touch/keyboard selection, not semantic brush segmentation or zoom.
- Runner capacity is suitable for controlled testing; queue/concurrency benchmarking is still required before
  runner-only reliance.
- The in-app browser tool failure is an external Codex desktop/runtime issue; visual QA used the documented fallback.
