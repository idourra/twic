from __future__ import annotations
import os
from pydantic import BaseModel

class Settings(BaseModel):
    api_name: str = "twic"
    api_version: str = "0.2.1"
    git_sha: str | None = os.getenv("GIT_SHA")  # inyectado por pipeline de build
    build_date: str | None = os.getenv("BUILD_DATE")  # ISO8601 opcional

    # Pesos de fusión (semántico + BM25 + clasificador)
    alpha_sem: float = float(os.getenv("ALPHA_SEM", "0.5"))
    beta_bm25: float = float(os.getenv("BETA_BM25", "0.3"))
    gamma_clf: float = float(os.getenv("GAMMA_CLF", "0.2"))

    # Umbral y top-k
    tau_low: float = float(os.getenv("TAU_LOW", "0.4"))
    top_k: int = int(os.getenv("TOP_K", "20"))

    # Rutas de artefactos
    models_dir: str = os.getenv("MODELS_DIR", "models")
    data_dir: str = os.getenv("DATA_DIR", "data")

    # Idiomas
    default_lang: str = os.getenv("DEFAULT_LANG", "es")
    supported_langs: list[str] = ["es", "en"]

    # Embeddings
    embeddings_backend: str = os.getenv("EMBEDDINGS_BACKEND", "placeholder")  # placeholder | st
    embeddings_model: str = os.getenv(
        "EMBEDDINGS_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # Classifier training defaults (used by retrain script fallback)
    clf_max_iter: int = int(os.getenv("CLF_MAX_ITER", "300"))
    clf_calibration: str = os.getenv("CLF_CALIBRATION", "none")  # none|platt|isotonic
    clf_cv_folds: int = int(os.getenv("CLF_CV_FOLDS", "3"))

    # Observability / limits
    enable_metrics: bool = os.getenv("ENABLE_METRICS", "1") == "1"
    request_rate_limit: int = int(os.getenv("REQUEST_RATE_LIMIT", "100"))  # tokens per window
    rate_limit_window_s: int = int(os.getenv("RATE_LIMIT_WINDOW_S", "60"))
    max_query_chars: int = int(os.getenv("MAX_QUERY_CHARS", "512"))

    # Taxonomy search weights (heuristic ranking) & vector mixing
    taxo_w_exact: float = float(os.getenv("TAXO_W_EXACT", "100"))
    taxo_w_prefix: float = float(os.getenv("TAXO_W_PREFIX", "60"))
    taxo_w_substring: float = float(os.getenv("TAXO_W_SUBSTRING", "40"))
    taxo_w_alt: float = float(os.getenv("TAXO_W_ALT", "30"))
    taxo_w_hidden: float = float(os.getenv("TAXO_W_HIDDEN", "20"))
    taxo_w_path: float = float(os.getenv("TAXO_W_PATH", "10"))
    taxo_w_context: float = float(os.getenv("TAXO_W_CONTEXT", "5"))  # definition/scope/note/example
    taxo_w_vec: float = float(os.getenv("TAXO_W_VEC", "0"))  # peso de similitud vectorial (0 = off)
    taxo_top_k: int = int(os.getenv("TAXO_TOP_K", "25"))
    taxo_w_fuzzy: float = float(os.getenv("TAXO_W_FUZZY", "0"))  # peso adicional fuzzy ratio
    taxo_fuzzy_min_ratio: float = float(os.getenv("TAXO_FUZZY_MIN_RATIO", "70"))  # umbral mínimo 0-100

    # Feature & infra toggles
    enable_docs: bool = os.getenv("FASTAPI_ENABLE_DOCS", "1") == "1"
    redis_url: str | None = os.getenv("REDIS_URL")

settings = Settings()
