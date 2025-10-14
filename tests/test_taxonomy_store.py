from pathlib import Path
import json

from app.services.taxonomy_store import TaxonomyStore


def test_taxonomy_store_load_and_search():
    # Asegura que existe taxonomy.json mínimo
    p = Path("data/taxonomy.json")
    assert p.exists(), "Se requiere data/taxonomy.json para el test"
    store = TaxonomyStore(p.as_posix())
    store.load()
    # Debe haber conceptos
    assert store.concepts, "No se cargaron conceptos"
    # Elegir un término de búsqueda a partir del primer concepto
    raw = json.loads(p.read_text(encoding="utf-8"))
    first = raw[0]
    # Maneja formatos: prefLabel puede ser str o dict
    pl = first.get("prefLabel")
    if isinstance(pl, dict):
        term = list(pl.values())[0]
    else:
        term = str(pl)
    token = term.split()[0][:6]  # substring para búsqueda parcial
    res = store.search(token, "es")
    assert res, "Sin resultados para término derivado del primer concepto"
