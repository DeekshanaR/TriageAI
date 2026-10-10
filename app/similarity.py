"""Find similar existing tickets (TF-IDF cosine similarity)."""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def find_similar(text: str, candidates: list[dict], threshold: float, top_k: int = 5) -> list[dict]:
    """Return candidates (with a 'score') whose text is similar to `text`."""
    if not candidates:
        return []
    docs = [text] + [f"{c['title']} {c['description']}" for c in candidates]
    try:
        matrix = TfidfVectorizer(ngram_range=(1, 2), stop_words="english").fit_transform(docs)
    except ValueError:               # nothing but stop-words
        return []
    scores = cosine_similarity(matrix[0], matrix[1:])[0]
    hits = [{**c, "score": round(float(s), 3)} for c, s in zip(candidates, scores) if s >= threshold]
    return sorted(hits, key=lambda h: h["score"], reverse=True)[:top_k]
