from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_autocomplete_choc_returns_chocolates():
    r = client.get("/taxonomy/autocomplete", params={"q": "choc", "lang": "es", "limit": 10})
    assert r.status_code == 200, r.text
    data = r.json()
    results = data.get("results", [])
    assert results, "No autocomplete results"
    labels = [x["label"].lower() for x in results]
    assert any("chocolates" in lbl for lbl in labels[:3]), (
        f"'chocolates' not in top suggestions: {labels}"
    )
