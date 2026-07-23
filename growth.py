"""
growth.py

A simple script that compares how many "immigration" posts we saved
*today* vs *yesterday*, and prints the percentage change.

This is an early, rough version of the "growth rate" idea from the
long-term vision (ranking topics by how fast they're growing, not just
raw volume). Right now there's only one topic and no ranking -- this
script just answers the question "is immigration talk going up or down
compared to yesterday?"

HOW TO RUN IT:
    python growth.py

It reads everything currently in the database, so run fetch_posts.py a
few times across at least two different days before this will have
anything useful to say.
"""

from collections import Counter
from datetime import datetime, timedelta, timezone

from db import get_connection

TOPIC = "immigration"


def load_post_dates():
    """Fetch every saved post's "created_at" timestamp for our topic,
    and return just the calendar date (in UTC) each post was made on.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT created_at FROM posts WHERE topic = ?", (TOPIC,)
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


def main():
    post_dates = load_post_dates()

    if not post_dates:
        print("No posts found in the database yet. Run fetch_posts.py first.")
        return

    # Count how many posts happened on each calendar day, e.g.
    # {date(2026, 7, 22): 20, date(2026, 7, 23): 45}
    counts_by_day = Counter(post_dates)

    today = datetime.now(timezone.utc).date()
    yesterday = today - timedelta(days=1)
    earliest_day_we_have = min(post_dates)

    # We can only make a fair comparison if our data actually goes back
    # as far as yesterday. If the oldest post we've saved is from today
    # (e.g. we only just started running fetch_posts.py), we don't have
    # a real "yesterday" to compare against yet.
    if earliest_day_we_have > yesterday:
        print(
            f"Not enough data yet to compare {TOPIC} mentions day over day.\n"
            f"Our earliest saved post is from {earliest_day_we_have}, but we'd "
            f"need data going back to {yesterday}. Keep running fetch_posts.py "
            f"over the next day or so, then try again."
        )
        return

    today_count = counts_by_day.get(today, 0)
    yesterday_count = counts_by_day.get(yesterday, 0)

    if yesterday_count == 0:
        # We have coverage for yesterday, but happened to save zero
        # matching posts that day. A percentage change from zero is
        # undefined (you can't divide by zero), so we say so plainly
        # instead of printing something like "+inf%".
        print(
            f"{TOPIC.capitalize()}: {today_count} mention(s) today vs "
            f"0 yesterday (can't calculate a percentage change from zero)."
        )
        return

    growth_pct = ((today_count - yesterday_count) / yesterday_count) * 100
    sign = "+" if growth_pct >= 0 else ""

    print(
        f"{TOPIC.capitalize()}: {today_count} mention(s) today vs "
        f"{yesterday_count} yesterday ({sign}{growth_pct:.0f}%)"
    )


if __name__ == "__main__":
    main()
