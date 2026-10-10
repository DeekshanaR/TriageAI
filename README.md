# Self-Governing AI Ticket Agent

![CI](https://github.com/YOUR-USERNAME/ticket-automation-ai/actions/workflows/ci.yml/badge.svg)

Most ticket-automation demos do one thing: *predict a category and route it*. This project is
about the harder question: **when should automation act, and when must a human decide?**

It is an IT-service-desk agent in Python that classifies tickets with ML, explains its reasoning,
defends itself against prompt-injection, collapses ticket storms into one major incident, tracks
SLAs, and **learns from human corrections**. Every automated action is governed by an explicit policy.

## What makes it different

| Feature | What it does | Why it matters |
|---|---|---|
| **Autonomy policy engine** (`policy.py`) | Each ticket gets AUTO, APPROVAL or MANUAL based on category risk and model confidence. Security is never automated; access changes need approval. | Real automation fails when it acts on things it should not. |
| **Prompt-injection guard** (`guard.py`) | Ticket text is untrusted input. Suspicious text is flagged, **never sent to the LLM**, and held for a human. LLM input is sanitised and delimited. | LLM security is a hot topic and rare in portfolios. |
| **Explainable routing** (`classifier.explain`) | Every ticket stores the top words that drove the prediction. | Decisions are auditable, not a black box. |
| **Incident-storm correlation** (`service._correlate`) | 3+ similar tickets inside 30 minutes become one **major incident** with linked children. | AIOps-style event correlation instead of 40 duplicate tickets. |
| **Human-in-the-loop learning** | Humans approve or correct a route. Corrections are stored and used by `/model/retrain`. | Models need maintenance; this closes the loop. |
| **SLA risk engine** (`sla.py`) | Due dates by priority; flags tickets at risk or breached. | Matches how ITSM tools measure success. |
| **Honest evaluation** (`scripts/evaluate.py`) | Tests on a noisy "hard" set, shows the confusion matrix and the coverage-vs-accuracy trade-off, and measures improvement after corrections. | Most demos only report one flattering number. |

## Architecture

```
ticket (REST API  or  CSV via master_runner)
   │
   ▼
 guard ──flags──▶ (LLM skipped, human review)
   │
 classifier (TF-IDF + LogReg) ──▶ category, priority, confidence, explanation
   │
 policy ──▶ AUTO | APPROVAL | MANUAL
   │
 similarity + correlation ──▶ links to / creates MAJOR INCIDENT
   │
 AUTO ──▶ assign team            APPROVAL/MANUAL ──▶ wait ──▶ human approve / correct
   │                                                                     │
 lifecycle state machine + audit history (SQLite)          corrections ──▶ retrain
```

## See it in 1 second

```bash
python -m scripts.demo
```
Walks through: an auto-routed ticket with explanation, a blocked security ticket, an approval flow,
a prompt-injection attempt, a 5-ticket VPN storm becoming one incident, a wrong AI guess corrected
by a human, and SLA warnings.

## Quick start

```bash
git clone https://github.com/YOUR-USERNAME/ticket-automation-ai.git
cd ticket-automation-ai
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python -m scripts.generate_data      # synthetic dataset
python -m scripts.train_model        # train + metrics
python -m scripts.evaluate           # honest evaluation -> docs/EVALUATION.md
pytest -v                            # 46 tests
uvicorn app.main:app --reload        # API docs: http://127.0.0.1:8000/docs
```

Optional Claude suggestions: `export ANTHROPIC_API_KEY="your-key"`. Without it, a built-in knowledge base is used.

## API

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/tickets` | Create: guard, classify, explain, policy, correlate, maybe assign |
| GET | `/tickets`, `/tickets/{id}`, `/tickets/{id}/history` | Read tickets and audit trail |
| POST | `/tickets/{id}/transition` | Move through the validated lifecycle |
| GET | `/approvals` | Tickets waiting for a human |
| POST | `/tickets/{id}/approve` | Human approves the AI's route |
| POST | `/tickets/{id}/correct` | Human corrects category/priority (stored for retraining) |
| POST | `/model/retrain` | Retrain with base data plus all corrections |
| GET | `/incidents` | Major incidents with linked tickets |
| GET | `/sla/at-risk` | Tickets near or past their SLA |
| GET | `/stats` | Automation rate, pending reviews, flagged injections, ... |

## Evaluation (see `docs/EVALUATION.md` for full tables)

Run `python -m scripts.evaluate` to reproduce. Summary on 300 unseen noisy tickets:
- Accuracy on the hard set is lower than on clean data, as expected.
- Raising the confidence gate trades automation coverage for reliability; policy thresholds come from this table.
- Feeding back 300 human-corrected tickets raises accuracy on unseen hard tickets (about 95% to 99%).

## Honest limitations
- **All data is synthetic** (template-based, even the "hard" set), so absolute accuracy numbers are optimistic.
  The value here is the *system design*; drop a real labelled CSV into `data/sample_tickets.csv` to use real data.
- The injection guard is pattern-based. It catches common attacks, not every possible one.
- SQLite and TF-IDF were chosen for clarity; PostgreSQL and sentence embeddings are natural upgrades.

## Tech stack
Python 3.12, FastAPI, SQLite (plain SQL), scikit-learn, pandas, Anthropic Claude API (optional), pytest, GitHub Actions
