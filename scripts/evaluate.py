"""Honest evaluation on a HARD test set (typos, dropped words, mixed topics).

Reports
  1. accuracy on clean vs hard data (shows the drop from synthetic -> realistic text)
  2. confusion matrix
  3. the automation trade-off: the more cautious the policy, the lower the
     coverage, the higher the accuracy of tickets that ARE automated
  4. learning from human corrections: accuracy before/after retraining

Usage:  python -m scripts.evaluate        (also writes docs/EVALUATION.md)
"""
from pathlib import Path

import pandas as pd
from sklearn.metrics import confusion_matrix

from app.classifier import TicketClassifier, fit_models, _text
from app.config import DATA_PATH
from scripts.generate_data import generate, generate_hard


def _acc(models, df, target="category") -> float:
    return float((models[target].predict(_text(df)) == df[target]).mean())


def main() -> str:
    if not DATA_PATH.exists():
        generate(DATA_PATH)
    clean = pd.read_csv(DATA_PATH)
    hard = pd.DataFrame(generate_hard(600))
    pool, test = hard.iloc[:300], hard.iloc[300:]          # pool = what humans will correct
    models = fit_models(clean)
    out = ["# Evaluation", "",
           "Training data is clean synthetic text. The hard set adds typos, dropped words and "
           "tickets that mention a second, unrelated problem.", "",
           "## 1. Accuracy (category)", "",
           f"| Test set | Accuracy |", "|---|---|",
           f"| Clean (training distribution) | {_acc(models, clean):.1%} |",
           f"| Hard (typos / mixed topics), 300 tickets | {_acc(models, test):.1%} |", ""]

    labels = sorted(clean["category"].unique())
    pred = models["category"].predict(_text(test))
    cm = pd.DataFrame(confusion_matrix(test["category"], pred, labels=labels),
                      index=[f"true {l}" for l in labels], columns=labels)
    out += ["## 2. Confusion matrix on the hard set", "", cm.to_markdown(), ""]

    clf = TicketClassifier(models)
    conf = [clf.predict(r.title, r.description)["confidence"] for r in test.itertuples()]
    correct = (pred == test["category"].values)
    out += ["## 3. Automation trade-off (confidence gate)", "",
            "| Min. confidence to automate | Automated share | Accuracy of automated tickets |", "|---|---|---|"]
    for gate in (0.0, 0.4, 0.5, 0.6, 0.7, 0.8):
        mask = [c >= gate for c in conf]
        n = sum(mask)
        acc = sum(c for c, m in zip(correct, mask) if m) / n if n else float("nan")
        out.append(f"| {gate:.0%} | {n / len(conf):.0%} | {acc:.1%} |")
    out += ["", "Reading: raising the gate sends more tickets to humans but makes the automated "
                "decisions more reliable. Policy thresholds in `app/config.py` are chosen from this table.", ""]

    before = _acc(models, test)
    retrained = fit_models(pd.concat([clean] + [pool] * 5))     # corrections weighted x5 (RETRAIN_WEIGHT)
    after = _acc(retrained, test)
    out += ["## 4. Learning from human corrections", "",
            f"300 corrected hard tickets were fed back; accuracy on 300 UNSEEN hard tickets:", "",
            "| Model | Accuracy |", "|---|---|",
            f"| Before corrections | {before:.1%} |", f"| After retraining | {after:.1%} |", ""]
    text = "\n".join(out)
    Path("docs").mkdir(exist_ok=True)
    Path("docs/EVALUATION.md").write_text(text, encoding="utf-8")
    print(text)
    return text


if __name__ == "__main__":
    main()
