import re

from fastapi.testclient import TestClient


def test_embeddings_cache_gauge_exposed(monkeypatch):
    # Ensure vector weight >0 before app imports settings
    monkeypatch.setenv("TAXO_W_VEC", "5")
    # Import after env set
    from app.main import app  # noqa: WPS433

    client = TestClient(app)
    # Trigger a taxonomy load (search call)
    r = client.get("/taxonomy/search", params={"q": "chocolates", "lang": "es", "limit": 1})
    assert r.status_code == 200
    # Fetch metrics
    m = client.get("/metrics")
    assert m.status_code == 200
    body = m.text
    # Gauge name as defined in observability: twic_taxo_embeddings_cache_size
    pattern = re.compile(r"^twic_taxo_embeddings_cache_size\{lang=\"es\"} ", re.MULTILINE)
    assert pattern.search(body), (
        "Gauge twic_taxo_embeddings_cache_size not found in metrics:\n" + body[:1000]
    )
