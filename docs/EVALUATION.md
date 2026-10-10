# Evaluation

Training data is clean synthetic text. The hard set adds typos, dropped words and tickets that mention a second, unrelated problem.

## 1. Accuracy (category)

| Test set | Accuracy |
|---|---|
| Clean (training distribution) | 100.0% |
| Hard (typos / mixed topics), 300 tickets | 95.0% |

## 2. Confusion matrix on the hard set

|               |   Access |   Email |   Hardware |   Network |   Security |   Software |
|:--------------|---------:|--------:|-----------:|----------:|-----------:|-----------:|
| true Access   |       43 |       0 |          0 |         1 |          1 |          0 |
| true Email    |        2 |      52 |          0 |         0 |          0 |          0 |
| true Hardware |        1 |       0 |         40 |         1 |          2 |          2 |
| true Network  |        0 |       1 |          0 |        48 |          2 |          0 |
| true Security |        0 |       0 |          0 |         1 |         55 |          0 |
| true Software |        1 |       0 |          0 |         0 |          0 |         47 |

## 3. Automation trade-off (confidence gate)

| Min. confidence to automate | Automated share | Accuracy of automated tickets |
|---|---|---|
| 0% | 100% | 95.0% |
| 40% | 100% | 95.0% |
| 50% | 98% | 96.6% |
| 60% | 94% | 98.2% |
| 70% | 84% | 100.0% |
| 80% | 73% | 100.0% |

Reading: raising the gate sends more tickets to humans but makes the automated decisions more reliable. Policy thresholds in `app/config.py` are chosen from this table.

## 4. Learning from human corrections

300 corrected hard tickets were fed back; accuracy on 300 UNSEEN hard tickets:

| Model | Accuracy |
|---|---|
| Before corrections | 95.0% |
| After retraining | 98.7% |
