"""
fetch_posts.py

This script connects to Bluesky and searches for recent posts that
mention any of the topics listed in topics.json, then saves them into
our local SQLite database, tagged with which topic matched. For each
topic it pages through Bluesky's search results (in batches of 100 --
Bluesky's per-request limit) until Bluesky itself runs out of results
to give us, so a busy topic isn't capped at just the first 100
matches.

HOW TO RUN IT:
    python fetch_posts.py

You can run it as many times as you like (e.g. once an hour, by hand,
or via agent.py). Each run fetches whatever recent posts Bluesky's
search returns; posts we've already saved are skipped automatically (we
check the post's unique "uri" before inserting), so running it
repeatedly is safe and just fills in new posts over time.

SETUP REQUIRED:
    This script needs your Bluesky handle and an "app password" (NOT
    your real account password -- see README.md for how to create one).
    Put them in a file called ".env" in this folder, like this:

        BLUESKY_HANDLE=yourname.bsky.social
        BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
"""

import os
from datetime import datetime, timezone

from atproto import Client
from dotenv import load_dotenv

from config import load_topics
from db import get_connection, init_db

# How many posts to ask Bluesky for in one request. 100 is the max
# Bluesky allows per request.
POSTS_PER_REQUEST = 100

# A safety backstop, not a practical target: pages through as many
# results as Bluesky will give us for a topic, up to this many posts,
# so a single run can't loop forever if Bluesky's search ever fails to
# signal "no more results" (e.g. a cursor that never goes away). At 100
# posts/request this is 100 requests worst case per topic -- high
# enough that busy topics won't realistically hit it.
MAX_POSTS_PER_TOPIC = 10000


def get_client():
    """Load Bluesky credentials from .env and log in, returning a client."""
    load_dotenv()

    handle = os.getenv("BLUESKY_HANDLE")
    app_password = os.getenv("BLUESKY_APP_PASSWORD")

    if not handle or not app_password:
        raise SystemExit(
            "Missing Bluesky credentials. Create a .env file with "
            "BLUESKY_HANDLE and BLUESKY_APP_PASSWORD set (see README.md)."
        )

    print(f"Logging in to Bluesky as {handle}...")
    client = Client()
    client.login(handle, app_password)
    return client


def fetch_topic(client, conn, topic):
    """Search for one topic and save any new matching posts.

    Bluesky caps each individual search request at 100 posts, so this
    pages through further results (using the "cursor" Bluesky's search
    API gives back) until it has looked at MAX_POSTS_PER_TOPIC posts, or
    Bluesky runs out of matching posts to give us, whichever comes
    first.

    Returns (saved_count, skipped_count).
    """
    # "fetched_at" records when *we* ran this script, in UTC, using the
    # standard ISO 8601 text format (e.g. "2026-07-23T10:15:00+00:00").
    fetched_at = datetime.now(timezone.utc).isoformat()
    saved_count = 0
    skipped_count = 0
    posts_seen = 0
    next_page_cursor = None

    while posts_seen < MAX_POSTS_PER_TOPIC:
        print(f"Searching for recent posts mentioning '{topic}'...")
        params = {"q": topic, "limit": POSTS_PER_REQUEST}
        if next_page_cursor:
            params["cursor"] = next_page_cursor

        response = client.app.bsky.feed.search_posts(params=params)

        if not response.posts:
            break

        for post in response.posts:
            # INSERT OR IGNORE means: if a post with this "uri" is
            # already in the table, just skip it instead of raising an
            # error. This is what makes it safe to run the script over
            # and over.
            db_cursor = conn.execute(
                """
                INSERT OR IGNORE INTO posts
                    (uri, topic, text, author_handle, created_at, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    post.uri,
                    topic,
                    post.record.text,
                    post.author.handle,
                    post.record.created_at,
                    fetched_at,
                ),
            )
            if db_cursor.rowcount == 1:
                saved_count += 1
            else:
                skipped_count += 1

        posts_seen += len(response.posts)

        # Stop paging once Bluesky has nothing more to give us, or gave
        # us a partial page (a sign we've reached the end of the
        # results it's willing to return).
        if not response.cursor or len(response.posts) < POSTS_PER_REQUEST:
            break
        next_page_cursor = response.cursor

    return saved_count, skipped_count


def fetch_all_topics(topics=None):
    """Fetch and store posts for every topic (defaults to topics.json).

    Logs in to Bluesky once and reuses the connection across all
    topics, rather than logging in separately per topic. Returns a dict
    of {topic: {"saved": n, "skipped": n}}.
    """
    if topics is None:
        topics = load_topics()

    init_db()
    client = get_client()
    conn = get_connection()

    results = {}
    try:
        for topic in topics:
            saved, skipped = fetch_topic(client, conn, topic)
            results[topic] = {"saved": saved, "skipped": skipped}
            print(
                f"[{topic}] Saved {saved} new post(s), "
                f"skipped {skipped} already-seen post(s)."
            )
        conn.commit()
    finally:
        conn.close()

    return results


if __name__ == "__main__":
    fetch_all_topics()
