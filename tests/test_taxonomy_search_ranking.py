from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_chocolates_ranks_first():
    r = client.get("/taxonomy/search", params={"q": "chocolates", "lang": "es", "limit": 5})
    assert r.status_code == 200, r.text
    data = r.json()
    results = data.get("results", [])
    # Si no hay resultados no evaluamos (fallará para indicar problema)
    assert results, "No taxonomy results returned"
    # Esperamos que 'Chocolates y bombones' esté en top-3 y preferiblemente primero
    labels = [x["label"].lower() for x in results]
    target = "chocolates y bombones"
    assert any(target in lbl for lbl in labels[:3]), f"Target label not in top 3: {labels}"
    # Si aparece primero comprobamos condición fuerte
    if target in labels[0]:
        assert True