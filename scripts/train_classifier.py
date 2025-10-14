from __future__ import annotations
import pandas as pd, joblib
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score

DATA = [
    ("iphone 13 128gb","TW:12345"),
    ("comprar smartphone barato","TW:12345"),
    ("airpods 2 gen","TW:11111"),
    ("auriculares bluetooth","TW:11111"),
]

def main()->None:
    df = pd.DataFrame(DATA, columns=["query","category_id"])
    le = LabelEncoder()
    y = le.fit_transform(df["category_id"])
    tfidf = TfidfVectorizer(ngram_range=(1,3), analyzer="char")
    X = tfidf.fit_transform(df["query"])
    lr = LogisticRegression(max_iter=1000)
    lr.fit(X, y)
    acc = accuracy_score(y, lr.predict(X))
    print({"train_acc": float(acc), "n_classes": len(le.classes_)})
    out = Path("models"); out.mkdir(exist_ok=True)
    joblib.dump(tfidf, out/"tfidf.joblib")
    joblib.dump(lr, out/"lr.joblib")
    joblib.dump(list(le.classes_), out/"classes.joblib")

if __name__=="__main__": main()
