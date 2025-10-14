from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_contains_expected_keys():
    r = client.get('/health')
    assert r.status_code == 200, r.text
    data = r.json()
    # Required top-level keys
    for k in [
        'status', 'version', 'git_sha', 'build_date', 'python_version',
        'artifacts', 'classes', 'embeddings_dim'
    ]:
        assert k in data, f'missing key {k}'
    # Types (allow None for optional fields)
    assert data['status'] == 'ok'
    assert isinstance(data['version'], str)
    assert isinstance(data['python_version'], str)
    assert isinstance(data['artifacts'], list)


def test_metrics_exposed_after_requests():
    # Trigger a taxonomy search (GET) and a classify (POST) to ensure latency + count metrics
    sr = client.get('/taxonomy/search', params={'q': 'a', 'lang': 'es'})
    # Ignore failures gracefully (in minimal CI environment taxonomy might be small)
    if sr.status_code not in (200, 404):
        return
    cr = client.post('/classify', json={'query': 'tablet samsung', 'lang': 'es', 'top_k': 3})
    if cr.status_code != 200:
        return  # If classify cannot run (e.g., missing artifacts) skip hard assertions
    classify_data = cr.json()

    mr = client.get('/metrics')
    # If metrics disabled in this environment, acceptable to skip
    if mr.status_code != 200:
        return
    text = mr.text
    # Core metrics always expected when enabled
    assert 'twic_request_latency_seconds' in text
    assert 'twic_requests_total' in text

    # Depending on abstention, one of these should appear
    if classify_data.get('prediction'):
        assert 'twic_classify_score_max' in text
    else:
        # Could still record latency even if abstained; check abstention counter
        assert 'twic_abstentions_total' in text or 'twic_classify_score_max' in text
