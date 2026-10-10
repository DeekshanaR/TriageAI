import pytest

from app import classifier
from app.config import DATA_PATH


@pytest.fixture(scope="session", autouse=True)
def trained_model(tmp_path_factory):
    """Train once into a temporary location so tests never touch models/."""
    from scripts.generate_data import generate
    mp = pytest.MonkeyPatch()
    mp.setenv("TICKET_MODEL", str(tmp_path_factory.mktemp("model") / "m.joblib"))
    if not DATA_PATH.exists():
        generate(DATA_PATH)
    classifier.reset()
    classifier.train(verbose=False)
    yield
    mp.undo()


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    """Fresh database per test, LLM disabled, model cache cleared."""
    monkeypatch.setenv("TICKET_DB", str(tmp_path / "test.db"))
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    classifier.reset()
    yield
    classifier.reset()
