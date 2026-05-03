# API Notes

Implemented endpoint groups:

- `/auth`: Telegram initData auth, refresh, logout.
- `/uploads`: signed upload URL, complete, Telegram file_id, status, retry, delete.
- `/items`: wardrobe CRUD and item actions.
- `/looks`: LookCard, favorites and similar generation.
- `/outfits`: recommendations, prompt generation, anchored generation, rating and selection.
- `/ai`: image analysis task lifecycle and usage.
- `/designer`: wardrobe gaps, missing selected items and safe look rating.
- `/marketplace`: similar item search.
- `/wishlist`: wishlist CRUD.
- `/style-dna`, `/rules`, `/wardrobe/health`: taste and explainability features.
- `/privacy`, `/purchase-simulator`, `/capsules`, `/challenges`, `/share`: privacy and v0.2.2 advanced flows.
- `/billing/plans`: provider-neutral plan surface.

Current implementation returns contract-safe responses for scaffolded business flows. Persistence and advanced recommendation internals are isolated behind the existing module boundaries.
