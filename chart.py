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
and saves two chart images per topic (a light-mode and a dark-mode
version, so the dashboard can show the right one for the visitor's
color scheme) to data/mentions_over_time_<topic>.png and
..._<topic>_dark.png. Run fetch_posts.py a few times first (ideally
spread out over a few hours) so there's actually something to see.
"""

import re
from collections import Counter
from datetime import datetime

import matplotlib.pyplot as plt

from config import load_topics
from db import get_connection
from palette import THEME, topic_accent

OUTPUT_DIR = "data"

# A bar is capped well short of its category slot -- see the mark spec
# this follows: "never fill the slot; let the band's leftover be air".
BAR_WIDTH = 0.55


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


def render_chart(topic, hourly_counts, accent, mode):
    """Draw one chart (light or dark) and return the Figure. Caller
    saves and closes it."""
    theme = THEME[mode]
    labels = list(hourly_counts.keys())
    values = list(hourly_counts.values())

    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_facecolor(theme["surface"])
    ax.set_facecolor(theme["surface"])

    ax.bar(labels, values, width=BAR_WIDTH, color=accent, edgecolor="none")

    # Recessive chrome: no box, a muted baseline, hairline horizontal
    # gridlines only (never dashed), behind the bars.
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(theme["ink_muted"])
    ax.spines["bottom"].set_linewidth(0.8)
    ax.yaxis.grid(True, color=theme["grid"], linewidth=1, linestyle="-")
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)

    ax.tick_params(axis="x", colors=theme["ink_secondary"], labelsize=9)
    ax.tick_params(axis="y", colors=theme["ink_muted"], labelsize=9)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")

    # A single series needs no legend -- the title already names it.
    ax.set_title(
        f'"{topic}" mentions on Bluesky, by hour',
        color=theme["ink"],
        fontsize=13,
        fontweight="bold",
        loc="left",
        pad=14,
    )
    ax.set_ylabel("Number of posts", color=theme["ink_secondary"], fontsize=10)

    fig.tight_layout()
    return fig


def make_chart_for_topic(topic, light_accent=None, dark_accent=None):
    """Draw and save the hourly-mentions chart for one topic, as both a
    light-mode and a dark-mode image.

    Returns the light-mode image path, or None if there was no data yet.
    """
    timestamps = load_post_timestamps(topic)

    if not timestamps:
        print(f"[{topic}] No posts found in the database yet.")
        return None

    if light_accent is None:
        light_accent = topic_accent(0, "light")
    if dark_accent is None:
        dark_accent = topic_accent(0, "dark")

    hourly_counts = bucket_by_hour(timestamps)
    slug = slugify(topic)
    light_path = f"{OUTPUT_DIR}/mentions_over_time_{slug}.png"
    dark_path = f"{OUTPUT_DIR}/mentions_over_time_{slug}_dark.png"

    fig = render_chart(topic, hourly_counts, light_accent, "light")
    fig.savefig(light_path, dpi=150)
    plt.close(fig)

    fig = render_chart(topic, hourly_counts, dark_accent, "dark")
    fig.savefig(dark_path, dpi=150)
    plt.close(fig)

    print(
        f"[{topic}] Chart saved to {light_path} and {dark_path} "
        f"({len(timestamps)} posts total)."
    )
    return light_path


def main(topics=None):
    if topics is None:
        topics = load_topics()

    any_data = False
    for i, topic in enumerate(topics):
        light_accent = topic_accent(i, "light")
        dark_accent = topic_accent(i, "dark")
        if make_chart_for_topic(topic, light_accent, dark_accent):
            any_data = True

    if not any_data:
        print(
            "No posts found in the database yet. Run fetch_posts.py first, "
            "then try this again."
        )


if __name__ == "__main__":
    main()
