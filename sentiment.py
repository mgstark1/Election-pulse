"""
sentiment.py

Classifies each topic's recent posts as positive or negative, using a
TF-IDF + logistic regression model trained separately (see
sentiment_training/ -- a self-contained learning exercise, not part of
this pipeline). This script only *uses* the already-trained model; it
never trains anything itself.

HOW TO RUN IT:
    python sentiment.py

Like growth.py, only considers posts from DISPLAY_SINCE onward (see
config.py), so it stays consistent with the rest of the dashboard.

SETUP REQUIRED:
    models/sentiment_model.joblib and models/tfidf_vectorizer.joblib
    must exist -- see models/README.md. If they're missing, this script
    skips sentiment analysis gracefully (same pattern as agent.py
    skipping the AI summary when ANTHROPIC_API_KEY isn't set) rather
    than breaking the rest of the pipeline.
"""

import os
import re

import joblib

from config import DISPLAY_SINCE, load_topics
from db import get_connection

MODEL_PATH = "models/sentiment_model.joblib"
VECTORIZER_PATH = "models/tfidf_vectorizer.joblib"

# Cached after the first load so repeated calls in the same run don't
# re-read the model files from disk every time.
_model = None
_vectorizer = None


def clean_text(text):
    """Strip URL-shaped noise before vectorizing. Must match exactly
    the cleaning used in sentiment_training/explore.py when the model
    was trained -- the vectorizer's vocabulary was built on cleaned
    text, so inference needs the same cleaning to see consistent
    input."""
    return re.sub(r"\S*\.\S+/\S*", "", text)


def _load_model():
    """Load and cache the trained model + vectorizer. Returns
    (None, None) if the files aren't there yet."""
    global _model, _vectorizer
    if _model is not None:
        return _model, _vectorizer

    if not (os.path.exists(MODEL_PATH) and os.path.exists(VECTORIZER_PATH)):
        return None, None

    _model = joblib.load(MODEL_PATH)
    _vectorizer = joblib.load(VECTORIZER_PATH)
    return _model, _vectorizer


def load_post_texts(topic):
    """Fetch every saved post's text for one topic, from DISPLAY_SINCE
    onward (see config.py) -- same cutoff growth.py and chart.py use."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT text FROM posts WHERE topic = ? AND created_at >= ?",
        (topic, DISPLAY_SINCE),
    ).fetchall()
    conn.close()
    return [row[0] for row in rows]


def compute_sentiment(topic, model, vectorizer):
    """Classify every recent post for one topic as positive or
    negative. Returns a dict describing the result. "status" is one of:
        "no_model" -- the trained model files aren't available
        "no_data"  -- no posts to analyze yet
        "ok"       -- positive/negative counts are populated
    """
    texts = load_post_texts(topic)
    if not texts:
        return {"topic": topic, "status": "no_data"}

    cleaned = [clean_text(text) for text in texts]
    vectors = vectorizer.transform(cleaned)
    predictions = model.predict(vectors)

    positive = int(predictions.sum())
    total = len(predictions)
    negative = total - positive

    return {
        "topic": topic,
        "status": "ok",
        "positive": positive,
        "negative": negative,
        "total": total,
    }


def format_result(result):
    """Turn a compute_sentiment() result into a human-readable line."""
    topic = result["topic"].capitalize()
    status = result["status"]

    if status == "no_data":
        return f"{topic}: no posts to analyze sentiment for yet."
    return (
        f"{topic}: {result['positive']} positive, {result['negative']} negative "
        f"({result['total']} posts analyzed)."
    )


def main(topics=None):
    if topics is None:
        topics = load_topics()

    model, vectorizer = _load_model()
    if model is None:
        print(
            "Sentiment model not found (expected models/sentiment_model.joblib "
            "and models/tfidf_vectorizer.joblib) -- skipping sentiment analysis. "
            "See models/README.md."
        )
        return [{"topic": topic, "status": "no_model"} for topic in topics]

    results = []
    for topic in topics:
        result = compute_sentiment(topic, model, vectorizer)
        results.append(result)
        print(format_result(result))

    return results


if __name__ == "__main__":
    main()
