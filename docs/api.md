# API Notes

Implemented endpoint groups:

- `/auth`: Telegram initData auth, refresh, logout.
- `/uploads`: signed upload URL, complete, Telegram file_id, status, retry, delete.
- `/items`: wardrobe CRUD and item actions; `GET /items/{id}/image` streams the private photo for authenticated owners.
- `/looks`: LookCard, favorites and similar generation.
- `/outfits`: recommendations, prompt generation, anchored generation, rating and selection.
- `/ai`: image analysis task lifecycle and usage.
- `/designer`: wardrobe gaps, missing selected items, safe look rating and `POST /designer/chat` — the AI stylist chat that answers in Russian and persists proposed outfits (`outfit_id`, `outfit_item_ids`, explanation, score) built strictly from the user's wardrobe.
- `/weather`: authenticated Open-Meteo daily summary by latitude/longitude with Redis cache.
- `/marketplace`: similar item search.
- `/wishlist`: wishlist CRUD.
- `/style-dna`, `/rules`, `/wardrobe/health`: taste and explainability features.
- `/privacy`, `/purchase-simulator`, `/capsules`, `/challenges`, `/share`: privacy and v0.2.2 advanced flows.
- `/billing/plans`: provider-neutral plan surface.

Runtime user flows are authenticated and user-scoped. Wardrobe, wishlist, style, upload, AI, privacy and outfit
state is persisted in PostgreSQL, with private image bytes stored in S3-compatible object storage. Endpoints that need
external production providers return explicit unavailable errors until their provider adapter and secrets are configured.
