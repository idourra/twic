from fastapi.testclient import TestClient

from app.main import app


def test_ready_endpoint():
    client = TestClient(app)
    # Trigger startup events automatically by instantiating client
    r = client.get('/ready')
    assert r.status_code in (200, 503)
    data = r.text
    # Basic shape checks
    assert 'taxonomy' in data
    assert 'classifier' in data
    # If ready, status should be ready
    if r.status_code == 200:
        assert 'ready' in data
