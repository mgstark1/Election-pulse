"""
sentiment.py

Classifies each topic's recent posts as positive or negative, using a
TF-IDF + logistic regression model trained separately (see
sentiment_training/ -- a self-contained learning exercise, not part of
this pipeline). This script only *uses* the already-trained model; it
never trains anything itself.

Besides the current positive/negative counts, it also draws a
sentiment-over-time line chart per topic (% positive per day), so
sentiment swings show up alongside the existing hourly mentions chart.

HOW TO RUN IT:
    python sentiment.py

Like growth.py and chart.py, only considers posts from DISPLAY_SINCE
onward (see config.py), so it stays consistent with the rest of the
dashboard.

SETUP REQUIRED:
    models/sentiment_model.joblib and models/tfidf_vectorizer.joblib
    must exist -- see models/README.md. If they're missing, this script
    skips sentiment analysis gracefully (same pattern as agent.py
    skipping the AI summary when ANTHROPIC_API_KEY isn't set) rather
    than breaking the rest of the pipeline.
"""

import os
import re
from datetime import datetime

import joblib
import matplotlib.pyplot as plt

from chart import slugify
from config import DISPLAY_SINCE, load_topics
from db import get_connection
from palette import THEME, diverging_color

MODEL_PATH = "models/sentiment_model.joblib"
VECTORIZER_PATH = "models/tfidf_vectorizer.joblib"
CHART_DIR = "data"

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


def load_model():
    """Load and cache the trained model + vectorizer. Returns
    (None, None) if the files aren't there yet. Public because chart.py
    also needs it, to color the mentions chart by sentiment when a
    model is available."""
    global _model, _vectorizer
    if _model is not None:
        return _model, _vectorizer

    if not (os.path.exists(MODEL_PATH) and os.path.exists(VECTORIZER_PATH)):
        return None, None

    _model = joblib.load(MODEL_PATH)
    _vectorizer = joblib.load(VECTORIZER_PATH)
    return _model, _vectorizer


def classify_posts(topic, model, vectorizer):
    """Load and classify every recent post for one topic (from
    DISPLAY_SINCE onward, same cutoff growth.py and chart.py use), in a
    single pass. Returns a list of (created_at, prediction) pairs --
    prediction is 1 for positive, 0 for negative -- or None if there's
    no data yet."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT text, created_at FROM posts WHERE topic = ? AND created_at >= ?",
        (topic, DISPLAY_SINCE),
    ).fetchall()
    conn.close()

    if not rows:
        return None

    cleaned = [clean_text(text) for text, _ in rows]
    vectors = vectorizer.transform(cleaned)
    predictions = model.predict(vectors)

    return [(created_at, int(pred)) for (_, created_at), pred in zip(rows, predictions)]


def compute_sentiment(topic, classified):
    """Summarize a topic's classified posts into positive/negative
    totals. "status" is one of:
        "no_data" -- no posts to analyze yet
        "ok"      -- positive/negative counts are populated
    """
    if not classified:
        return {"topic": topic, "status": "no_data"}

    positive = sum(prediction for _, prediction in classified)
    total = len(classified)
    negative = total - positive

    return {
        "topic": topic,
        "status": "ok",
        "positive": positive,
        "negative": negative,
        "total": total,
    }


def compute_daily_sentiment(classified):
    """Bucket classified posts by calendar day (UTC) and return an
    ordered {date: percent_positive} dict, for a sentiment-over-time
    chart. Returns an empty dict if there's no data."""
    if not classified:
        return {}

    daily_counts = {}
    for created_at, prediction in classified:
        # Bluesky timestamps look like "2026-07-23T10:15:00.123Z";
        # fromisoformat() doesn't understand the trailing "Z", so we
        # swap it for "+00:00" (which means the same thing: UTC).
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        day = dt.date()
        bucket = daily_counts.setdefault(day, {"positive": 0, "total": 0})
        bucket["total"] += 1
        bucket["positive"] += prediction

    return {
        day: 100 * counts["positive"] / counts["total"]
        for day, counts in sorted(daily_counts.items())
    }


def render_sentiment_chart(topic, daily_pct, mode):
    """Draw one sentiment-over-time chart (light or dark) and return
    the Figure. Caller saves and closes it.

    A single line (% positive) against a 50% baseline -- % negative is
    just 100 minus this, since the model is a binary classifier, so one
    line fully shows the proportion. Diverging blue/red (the same hues
    already validated for this project's categorical palette, slots 1
    and 8) marks which side of 50% each day falls on: the fill between
    the line and the baseline, and the most-recent-day end-dot, carry
    the color; the line itself stays neutral ink, per the mark spec
    that data-color belongs on marks, not text."""
    theme = THEME[mode]
    labels = [day.strftime("%Y-%m-%d") for day in daily_pct.keys()]
    values = list(daily_pct.values())

    positive_hex = diverging_color("positive", mode)
    negative_hex = diverging_color("negative", mode)

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(theme["surface"])
    ax.set_facecolor(theme["surface"])

    ax.fill_between(
        labels, values, 50,
        where=[v >= 50 for v in values],
        color=positive_hex, alpha=0.10,
    )
    ax.fill_between(
        labels, values, 50,
        where=[v < 50 for v in values],
        color=negative_hex, alpha=0.10,
    )

    # Neutral reference line at the 50/50 midpoint -- not a data hue.
    ax.axhline(50, color=theme["baseline"], linewidth=1, linestyle="-")

    ax.plot(
        labels, values,
        color=theme["ink_secondary"], linewidth=2,
        solid_joinstyle="round", solid_capstyle="round",
    )

    # End-dot + direct label on the most recent value only -- never a
    # number on every point.
    end_color = positive_hex if values[-1] >= 50 else negative_hex
    ax.scatter(
        [labels[-1]], [values[-1]], s=80, color=end_color,
        edgecolors=theme["surface"], linewidths=2, zorder=3,
    )
    ax.annotate(
        f"{values[-1]:.0f}%",
        xy=(labels[-1], values[-1]),
        xytext=(10, 0), textcoords="offset points",
        va="center", color=theme["ink"], fontsize=10, fontweight="bold",
    )

    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(theme["ink_muted"])
    ax.spines["bottom"].set_linewidth(0.8)
    ax.yaxis.grid(True, color=theme["grid"], linewidth=1, linestyle="-")
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.set_ylim(0, 100)

    ax.tick_params(axis="x", colors=theme["ink_secondary"], labelsize=9)
    ax.tick_params(axis="y", colors=theme["ink_muted"], labelsize=9)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    ax.set_title(
        f'"{topic}" sentiment over time (% positive)',
        color=theme["ink"], fontsize=13, fontweight="bold", loc="left", pad=14,
    )
    ax.set_ylabel("% positive", color=theme["ink_secondary"], fontsize=10)

    fig.tight_layout()
    return fig


def make_sentiment_chart_for_topic(topic, daily_pct):
    """Draw and save the sentiment-over-time chart for one topic, as
    both a light-mode and a dark-mode image. Returns the light-mode
    image path, or None if there isn't enough data yet -- a trend needs
    at least 2 distinct days, unlike the single-snapshot counts."""
    if len(daily_pct) < 2:
        return None

    slug = slugify(topic)
    light_path = f"{CHART_DIR}/sentiment_over_time_{slug}.png"
    dark_path = f"{CHART_DIR}/sentiment_over_time_{slug}_dark.png"

    fig = render_sentiment_chart(topic, daily_pct, "light")
    fig.savefig(light_path, dpi=150)
    plt.close(fig)

    fig = render_sentiment_chart(topic, daily_pct, "dark")
    fig.savefig(dark_path, dpi=150)
    plt.close(fig)

    return light_path


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

    model, vectorizer = load_model()
    if model is None:
        print(
            "Sentiment model not found (expected models/sentiment_model.joblib "
            "and models/tfidf_vectorizer.joblib) -- skipping sentiment analysis. "
            "See models/README.md."
        )
        return [{"topic": topic, "status": "no_model"} for topic in topics]

    results = []
    for topic in topics:
        classified = classify_posts(topic, model, vectorizer)

        result = compute_sentiment(topic, classified)
        results.append(result)
        print(format_result(result))

        daily_pct = compute_daily_sentiment(classified)
        make_sentiment_chart_for_topic(topic, daily_pct)

    return results


if __name__ == "__main__":
    main()
