"""
chart.py

A simple script to check that our data collection is working, by
drawing a chart of how many posts we've saved for each tracked topic,
grouped by hour.

This is just a sanity check for this early phase of the project -- not
the fancy dashboard described in the long-term vision. That comes later.

HOW TO RUN IT:
    python chart.py

It reads everything currently in the database (data/election_pulse.db)
and saves one chart image per topic to
data/mentions_over_time_<topic>.png. Run fetch_posts.py a few times
first (ideally spread out over a few hours) so there's actually
something to see.
"""

import re
from collections import Counter
from datetime import datetime

import matplotlib.pyplot as plt

from config import load_topics
from db import get_connection

OUTPUT_DIR = "data"


def slugify(topic):
    """Turn a topic string into a filesystem-safe slug, e.g.
    "Student Debt" -> "student_debt"."""
    return re.sub(r"[^a-z0-9]+", "_", topic.lower()).strip("_")


def load_post_timestamps(topic):
    """Fetch every saved post's "created_at" timestamp for one topic."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT created_at FROM posts WHERE topic = ?", (topic,)
    ).fetchall()
    conn.close()
    # rows is a list of 1-item tuples, e.g. [("2026-07-23T10:15:00Z",), ...]
    return [row[0] for row in rows]


def bucket_by_hour(timestamps):
    """Count how many posts fall into each hour, e.g. "2026-07-23 10:00".

    Returns a dict sorted by time, like:
        {"2026-07-23 09:00": 3, "2026-07-23 10:00": 7, ...}
    """
    counts = Counter()
    for ts in timestamps:
        # Bluesky timestamps look like "2026-07-23T10:15:00.123Z".
        # fromisoformat() doesn't understand the trailing "Z", so we
        # swap it for "+00:00" (which means the same thing: UTC).
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        hour_bucket = dt.strftime("%Y-%m-%d %H:00")
        counts[hour_bucket] += 1

    # Sort by the bucket label so the chart reads left-to-right in time order.
    return dict(sorted(counts.items()))


def make_chart_for_topic(topic):
    """Draw and save the hourly-mentions chart for one topic.

    Returns the output image path, or None if there was no data yet.
    """
    timestamps = load_post_timestamps(topic)

    if not timestamps:
        print(f"[{topic}] No posts found in the database yet.")
        return None

    hourly_counts = bucket_by_hour(timestamps)
    labels = list(hourly_counts.keys())
    values = list(hourly_counts.values())

    plt.figure(figsize=(10, 5))
    plt.bar(labels, values)
    plt.title(f'"{topic}" mentions on Bluesky, by hour')
    plt.xlabel("Hour")
    plt.ylabel("Number of posts")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()

    output_path = f"{OUTPUT_DIR}/mentions_over_time_{slugify(topic)}.png"
    plt.savefig(output_path)
    plt.close()

    print(f"[{topic}] Chart saved to {output_path} ({len(timestamps)} posts total).")
    return output_path


def main(topics=None):
    if topics is None:
        topics = load_topics()

    any_data = False
    for topic in topics:
        if make_chart_for_topic(topic):
            any_data = True

    if not any_data:
        print(
            "No posts found in the database yet. Run fetch_posts.py first, "
            "then try this again."
        )


if __name__ == "__main__":
    main()
