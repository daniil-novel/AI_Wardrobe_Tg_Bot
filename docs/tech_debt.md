# Technical Debt

- Add real marketplace provider adapters and trust-layer checks before enabling marketplace search in production.
- Add admin dashboard routes and RBAC-protected UI.
- Add Playwright visual checks for Telegram WebView viewports.
- Add exact OpenRouter token/cost accounting once provider billing metadata is available in responses.
- Add staging load/chaos/security pipelines before GA rollout.
- Behind the shared TLS reverse proxy the API sees only loopback client addresses, so unauthenticated rate limiting collapses to one bucket; enable PROXY protocol or a dedicated ingress when traffic grows.
- Automate the daily PostgreSQL dump (`/opt/ai-wardrobe/backups`) with cron/systemd on the production host and add an off-host copy.

Done in 0.3.0:

- ~~Add rate limiting middleware backed by Redis.~~ Implemented in `apps/api/aiwardrobe_api/rate_limit.py` with fail-open semantics and tests.
