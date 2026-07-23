"""
fetch_posts.py

This script connects to Bluesky and searches for recent posts that
mention a topic (right now, just "immigration"), then saves them into
our local SQLite database.

HOW TO RUN IT:
    python fetch_posts.py

You can run it as many times as you like (e.g. once an hour, by hand).
Each run fetches whatever recent posts Bluesky's search returns; posts
we've already saved are skipped automatically (we check the post's
unique "uri" before inserting), so running it repeatedly is safe and
just fills in new posts over time.

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

from db import get_connection, init_db

# The single topic we're tracking for now. Later this could become a
# list of topics, but the task right now is just "immigration".
TOPIC = "immigration"

# How many posts to ask Bluesky for in one go. 100 is the max Bluesky
# allows per request.
POSTS_PER_REQUEST = 100


def fetch_and_store_posts():
    # Load BLUESKY_HANDLE and BLUESKY_APP_PASSWORD from the .env file
    # into the environment, so we can read them with os.getenv() below.
    load_dotenv()

    handle = os.getenv("BLUESKY_HANDLE")
    app_password = os.getenv("BLUESKY_APP_PASSWORD")

    if not handle or not app_password:
        raise SystemExit(
            "Missing Bluesky credentials. Create a .env file with "
            "BLUESKY_HANDLE and BLUESKY_APP_PASSWORD set (see README.md)."
        )

    # Make sure the database and its table exist before we try to use it.
    init_db()

    # Log in to Bluesky using the app password. The atproto library
    # handles all the authentication details for us.
    print(f"Logging in to Bluesky as {handle}...")
    client = Client()
    client.login(handle, app_password)

    print(f"Searching for recent posts mentioning '{TOPIC}'...")
    response = client.app.bsky.feed.search_posts(
        params={"q": TOPIC, "limit": POSTS_PER_REQUEST}
    )
    posts = response.posts

    conn = get_connection()
    saved_count = 0
    skipped_count = 0

    # "fetched_at" records when *we* ran this script, in UTC, using the
    # standard ISO 8601 text format (e.g. "2026-07-23T10:15:00+00:00").
    fetched_at = datetime.now(timezone.utc).isoformat()

    for post in posts:
        # INSERT OR IGNORE means: if a post with this "uri" is already
        # in the table, just skip it instead of raising an error. This
        # is what makes it safe to run the script over and over.
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO posts
                (uri, topic, text, author_handle, created_at, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                post.uri,
                TOPIC,
                post.record.text,
                post.author.handle,
                post.record.created_at,
                fetched_at,
            ),
        )
        if cursor.rowcount == 1:
            saved_count += 1
        else:
            skipped_count += 1

    conn.commit()
    conn.close()

    print(f"Done. Saved {saved_count} new post(s), skipped {skipped_count} already-seen post(s).")


if __name__ == "__main__":
    fetch_and_store_posts()
