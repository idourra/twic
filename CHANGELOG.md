# Changelog

All notable changes to this project will be documented in this file.

The format roughly follows Keep a Changelog, with semantic version intent (pre-1.0 may introduce breaking changes).

## [0.1.0] - 2025-10-14

### Added

- Initial MVP scaffolding (FastAPI app structure `app/`, `scripts/`, `data/`, `models/`).
- SKOS JSON-LD import script (`import_skos_jsonld.py`) producing enriched `taxonomy.json`.
- Taxonomy store with multilingual search and inverted index.
- Embeddings build script (`build_embeddings.py`) for deterministic placeholder embeddings (ES/EN).
- Hybrid retrieval: dense (FAISS placeholder) + BM25 + fusion (triple strategy).
- Classification endpoint with abstention threshold (`TAU_LOW`).
- Feedback endpoint to collect user labeled intents.
- Admin reload endpoint resetting indices and taxonomy cache.
- Retraining script (`retrain_classifier.py`) for TF-IDF + LogisticRegression classifier.
- Dockerfile multi-stage + docker-compose setup.
- CI workflow (pytest, ruff, mypy) and GitHub Flow docs (`CONTRIBUTING.md`).
- SOW documentation (`docs/CONTRATO_SOW.md`) and retraining guide (`docs/retraining.md`).

### Changed

- Classify endpoint hardened: filters stale class IDs, logs discarded concepts, structured logging additions.
- README expanded with Docker usage and retraining instructions.

### Fixed

- KeyError on `/classify` when classifier classes not present in taxonomy (defensive filtering).
- Markdown lint issues in documentation files.

### Security

- Ensured taxonomy / embeddings paths configurable via environment variables.

---

## Unreleased

- Embeddings migration to real model (sentence-transformers) pending.
- Advanced metrics & monitoring.
- Production deployment hardening and rate limiting.
