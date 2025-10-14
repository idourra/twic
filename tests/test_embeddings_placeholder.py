from app.services.embeddings import backend_name, embed_text


def test_placeholder_deterministic():
    if backend_name() != "placeholder":  # Only test deterministic property for placeholder
        return
    v1 = embed_text("hola mundo")
    v2 = embed_text("hola mundo")
    assert v1.shape == v2.shape
    assert (v1 == v2).all(), "Placeholder embeddings must be deterministic for same text"
    assert v1.dtype.name == "float32"
