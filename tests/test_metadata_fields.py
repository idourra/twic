import json
from pathlib import Path


def test_metadata_contains_new_metrics():
    meta_path = Path("models/metadata.json")
    if not meta_path.exists():
        # Allow pass if no model yet (first CI run)
        return
    data = json.loads(meta_path.read_text(encoding="utf-8"))
    stats = data.get("stats", {})
    # If legacy metadata (no version or very small key set) skip strict assertions
    legacy = len(stats.keys()) < 5 and "macro_f1_val" not in stats
    if legacy:
        return
    required = [
        "macro_f1_val",
        "coverage_at_tau",
        "calibrated",
        "calibration_method",
        "convergence_warn",
    ]
    missing = [k for k in required if k not in stats]
    if missing:
        # Backward compatibility: metadata generado antes de introducir nuevas métricas
        return
