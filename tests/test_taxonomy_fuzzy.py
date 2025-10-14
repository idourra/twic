from fastapi.testclient import TestClient

from app.core.settings import settings
from app.main import app

client = TestClient(app)

def test_fuzzy_typo_chocoolates():
    # Activa peso fuzzy para asegurar contribuye (si está en 0 el test podría fallar)
    settings.taxo_w_fuzzy = max(settings.taxo_w_fuzzy, 10.0)
    r = client.get("/taxonomy/search", params={"q": "chocoolates", "lang": "es", "limit": 5})
    assert r.status_code == 200, r.text
    data = r.json()
    results = data.get("results", [])
    assert results, "No taxonomy results returned"
    labels = [x["label"].lower() for x in results]
    assert any("chocolates" in lbl for lbl in labels[:3]), (
        f"Fuzzy didn't surface chocolates: {labels}"
    )
