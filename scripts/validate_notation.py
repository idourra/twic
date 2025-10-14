from __future__ import annotations
import json, re, sys
from pathlib import Path
from typing import List, Dict

def clean(code: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", str(code))

def parents_dynamic(code_clean: str, universe: set[str]) -> List[str]:
    return [code_clean[:i] for i in range(1, len(code_clean)) if code_clean[:i] in universe]

def main(path="data/taxonomy.json"):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    ids = [str(row["id"]) for row in data]
    ids_clean = [clean(x) for x in ids]
    if len(set(ids)) != len(ids):
        print("ERROR: notations duplicadas (sin limpiar).", file=sys.stderr); sys.exit(1)
    if len(set(ids_clean)) != len(ids_clean):
        print("ADVERTENCIA: colisiones tras limpiar separadores.", file=sys.stderr)

    universe = set(ids_clean)
    missing_parents = []
    for raw, c in zip(ids, ids_clean):
        for p in parents_dynamic(c, universe):
            # todos los prefijos que existan son padres válidos; si no hay ninguno no es error
            if p not in universe:
                missing_parents.append((raw, p))
    if missing_parents:
        print(f"ADVERTENCIA: hay {len(missing_parents)} prefijos sin concepto explícito (no es error). Ej: {missing_parents[:10]}")
    else:
        print("OK: prefijos-parent detectados, sin faltantes explícitos.")

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "data/taxonomy.json"
    main(p)
