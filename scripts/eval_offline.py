from __future__ import annotations
import os
import time
import numpy as np
from app.services import retrieval, classifier, fusion, preprocessing
from app.services.taxonomy_store import TaxonomyStore

# Hiperparámetros desde entorno (con valores por defecto)
ALPHA = float(os.getenv("FUSION_ALPHA", "0.5"))
TOPK = int(os.getenv("TOP_K", "20"))

# Mini test set demo
TEST = [
    ("iphone 13 128gb", "TW:12345"),
    ("airpods bluetooth", "TW:11111"),
]

def main() -> None:
    retrieval.load_index("data/class_embeddings.npy", "data/class_ids.npy")
    classifier.load("models")
    store = TaxonomyStore("data/taxonomy.json")
    store.load()

    lat_ms = []
    correct = 0
    for q, gold in TEST:
        t0 = time.time()
        qn = preprocessing.normalize(q)
        q_emb = retrieval.embed_query(qn)
        sem = retrieval.topk(q_emb, k=TOPK)
        cls = classifier.scores(qn)
        comb = fusion.combine(sem, cls, classifier.class_ids(), ALPHA)
        pred = comb[0][0]
        lat_ms.append((time.time() - t0) * 1000.0)
        if pred == gold:
            correct += 1

    exact1 = correct / len(TEST) if TEST else 0.0
    p95 = float(np.percentile(np.array(lat_ms, dtype="float32"), 95)) if lat_ms else 0.0
    print({"Exact@1": exact1, "p95_ms": p95, "alpha": ALPHA, "topk": TOPK})

if __name__ == "__main__":
    main()
