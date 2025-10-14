from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_taxonomy_search_basic():
    r = client.get("/taxonomy/search", params={"q": "chocolate", "lang": "es"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert "results" in data
    assert len(data["results"]) >= 1
    first = data["results"][0]
    assert {"id","label","path"}.issubset(first.keys())

def test_classify_basic():
    r = client.post("/classify", json={"query": "tablet samsung", "lang": "es", "top_k": 3})
    assert r.status_code == 200, r.text
    data = r.json()
    # Debe existir latencia y alternatives
    assert "latency_ms" in data and isinstance(data["latency_ms"], int)
    assert "alternatives" in data and isinstance(data["alternatives"], list)
    # Prediction puede ser None si abstained
    if data.get("prediction"):
        p = data["prediction"]
        assert {"id","label","path","score","method"}.issubset(p.keys())
    # Asegura top_k (alternatives + 1 prediction posible) <= solicitado
    assert len(data["alternatives"]) <= 3
