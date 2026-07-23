"""
growth.py

A script that compares how many posts we saved *today* vs *yesterday*
for each tracked topic, and prints the percentage change per topic.

This is an early, rough version of the "growth rate" idea from the
long-term vision (ranking topics by how fast they're growing, not just
raw volume).

HOW TO RUN IT:
    python growth.py

It reads everything currently in the database, so run fetch_posts.py a
few times across at least two different days before this will have
anything useful to say.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from config import load_topics
from db import get_connection


def load_post_dates(topic):
    """Fetch every saved post's "created_at" timestamp for one topic,
    and return just the calendar date (in UTC) each post was made on.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT created_at FROM posts WHERE topic = ?", (topic,)
    ).fetchall()
    conn.close()

    dates = []
    for (created_at,) in rows:
        # Bluesky timestamps look like "2026-07-23T10:15:00.123Z".
        # fromisoformat() doesn't understand the trailing "Z", so we
        # swap it for "+00:00" (which means the same thing: UTC).
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        dates.append(dt.date())
    return dates


def compute_growth(topic):
    """Compute today-vs-yesterday growth for one topic.

    Returns a dict describing the result. "status" is one of:
        "no_data"              -- nothing saved for this topic yet
        "insufficient_history" -- data doesn't go back to yesterday yet
        "zero_yesterday"       -- yesterday had 0 posts (can't do a %)
        "ok"                   -- growth_pct is populated
    """
    post_dates = load_post_dates(topic)

    if not post_dates:
        return {"topic": topic, "status": "no_data"}

    # Count how many posts happened on each calendar day, e.g.
    # {date(2026, 7, 22): 20, date(2026, 7, 23): 45}
    counts_by_day = Counter(post_dates)

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    earliest_day_we_have = min(post_dates)

    # We can only make a fair comparison if our data actually goes back
    # as far as yesterday.
    if earliest_day_we_have > yesterday:
        return {
            "topic": topic,
            "status": "insufficient_history",
            "earliest_day": earliest_day_we_have,
        }

    today_count = counts_by_day.get(today, 0)
    yesterday_count = counts_by_day.get(yesterday, 0)

    if yesterday_count == 0:
        # A percentage change from zero is undefined (can't divide by
        # zero), so we flag it instead of printing something like "+inf%".
        return {"topic": topic, "status": "zero_yesterday", "today_count": today_count}

    growth_pct = ((today_count - yesterday_count) / yesterday_count) * 100
    return {
        "topic": topic,
        "status": "ok",
        "today_count": today_count,
        "yesterday_count": yesterday_count,
        "growth_pct": growth_pct,
    }


def format_result(result):
    """Turn a compute_growth() result into a human-readable line."""
    topic = result["topic"].capitalize()
    status = result["status"]

    if status == "no_data":
        return f"{topic}: no posts found in the database yet."
    if status == "insufficient_history":
        return (
            f"{topic}: not enough data yet to compare day over day "
            f"(earliest saved post is from {result['earliest_day']})."
        )
    if status == "zero_yesterday":
        return (
            f"{topic}: {result['today_count']} mention(s) today vs 0 "
            "yesterday (can't calculate a percentage change from zero)."
        )

    sign = "+" if result["growth_pct"] >= 0 else ""
    return (
        f"{topic}: {result['today_count']} mention(s) today vs "
        f"{result['yesterday_count']} yesterday "
        f"({sign}{result['growth_pct']:.0f}%)"
    )


def main(topics=None):
    if topics is None:
        topics = load_topics()

    results = []
    for topic in topics:
        result = compute_growth(topic)
        results.append(result)
        print(format_result(result))

    return results


if __name__ == "__main__":
    main()
