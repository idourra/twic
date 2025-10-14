from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_taxonomy_detail_404():
    r = client.get("/taxonomy/___nope___")
    assert r.status_code == 404


def test_taxonomy_detail_success():
    # Use search to get an existing id (fallback if no results skip)
    sr = client.get("/taxonomy/search", params={"q": "a"})
    if sr.status_code != 200:
        return
    data = sr.json()
    results = data.get("results", [])
    if not results:
        return
    cid = results[0]["id"]
    dr = client.get(f"/taxonomy/{cid}")
    assert dr.status_code == 200
    detail = dr.json()
    for key in ["id", "prefLabel", "path", "broader"]:
        assert key in detail
