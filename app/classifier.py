"""AI component 1: ML model that predicts ticket category and priority,
and can EXPLAIN which words drove its decision.

TF-IDF text features + Logistic Regression (scikit-learn). Linear models are
used on purpose: their per-word contribution can be read directly, which makes
routing decisions auditable.
"""
import logging

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from app.config import DATA_PATH, RETRAIN_WEIGHT, model_path

log = logging.getLogger(__name__)
TARGETS = ("category", "priority")


def _pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), lowercase=True, sublinear_tf=True)),
        ("clf", LogisticRegression(C=10, max_iter=2000)),
    ])


def _text(df: pd.DataFrame) -> list:
    return (df["title"] + " " + df["description"]).tolist()


def fit_models(df: pd.DataFrame) -> dict:
    return {t: _pipeline().fit(_text(df), df[t]) for t in TARGETS}


def train(csv_path=DATA_PATH, save_to=None, extra_rows=None, verbose=True) -> dict:
    """Train, evaluate on a clean hold-out split and save.

    extra_rows: human-corrected tickets (list of dicts). They are added to the
    training data only, repeated RETRAIN_WEIGHT times so they influence the model.
    """
    df = pd.read_csv(csv_path)
    extra = pd.DataFrame(extra_rows) if extra_rows else pd.DataFrame(columns=df.columns)
    extra = pd.concat([extra[df.columns]] * RETRAIN_WEIGHT) if len(extra) else extra

    scores = {}
    for target in TARGETS:
        train_df, test_df = train_test_split(df, test_size=0.2, random_state=42, stratify=df[target])
        model = _pipeline().fit(_text(pd.concat([train_df, extra])), pd.concat([train_df, extra])[target])
        pred = model.predict(_text(test_df))
        report = classification_report(test_df[target], pred, output_dict=True, zero_division=0)
        scores[target] = round(report["accuracy"], 3)
        if verbose:
            print(f"\n=== {target.upper()} model (clean hold-out) ===")
            print(classification_report(test_df[target], pred, zero_division=0))

    models = fit_models(pd.concat([df, extra]))
    path = save_to or model_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(models, path)
    log.info("Model saved to %s", path)
    return scores


class TicketClassifier:
    def __init__(self, models: dict):
        self.models = models

    def predict(self, title: str, description: str) -> dict:
        text = [f"{title} {description}"]
        cat, pri = self.models["category"], self.models["priority"]
        cat_p, pri_p = cat.predict_proba(text)[0], pri.predict_proba(text)[0]
        return {
            "category": str(cat.classes_[cat_p.argmax()]),
            "priority": str(pri.classes_[pri_p.argmax()]),
            "confidence": round(float(cat_p.max()), 3),
        }

    def explain(self, title: str, description: str, top_k: int = 5) -> list[dict]:
        """Words/phrases that pushed the model towards its predicted category."""
        model = self.models["category"]
        tfidf, clf = model.named_steps["tfidf"], model.named_steps["clf"]
        x = tfidf.transform([f"{title} {description}"])
        predicted = model.predict([f"{title} {description}"])[0]
        class_idx = list(clf.classes_).index(predicted)
        contributions = x.toarray()[0] * clf.coef_[class_idx]
        names = tfidf.get_feature_names_out()
        order = contributions.argsort()[::-1][:top_k]
        return [{"term": str(names[i]), "weight": round(float(contributions[i]), 3)}
                for i in order if contributions[i] > 0]


_classifier = None


def reset() -> None:
    """Forget the cached model so the next call reloads it from disk."""
    global _classifier
    _classifier = None


def get_classifier() -> TicketClassifier:
    global _classifier
    if _classifier is None:
        if not model_path().exists():
            if not DATA_PATH.exists():
                from scripts.generate_data import generate
                generate(DATA_PATH)
            train(verbose=False)
        _classifier = TicketClassifier(joblib.load(model_path()))
    return _classifier
