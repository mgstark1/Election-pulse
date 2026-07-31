"""
db.py

Small helper module for talking to our SQLite database.

We use SQLite because it's just a single file on disk (no server to set
up), which is perfect for a simple project like this. Later, if the app
grows, we could swap this for a bigger database without changing much
else, because all the database logic is kept in this one file.
"""

import sqlite3
from pathlib import Path

# The database file lives in the "data" folder next to this script.
DB_PATH = Path(__file__).parent / "data" / "election_pulse.db"


def get_connection():
    """Open a connection to the SQLite database file.

    If the file doesn't exist yet, SQLite will create it automatically.
    """
    # Make sure the "data" folder exists before we try to write to it.
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    """Create the "posts" table if it doesn't already exist.

    Each row is one post (from Bluesky today; other sources like Twitter
    may be added later) that mentioned our tracked topic.

    Columns:
      - uri:            unique ID the source platform gives every post
                         (used to avoid saving the same post twice)
      - source:         which platform this post came from, e.g. "bluesky".
                         Only one source today, but storing it now means
                         we don't have to change the table when a second
                         one is added.
      - topic:          which topic we were searching for (e.g. "immigration").
                         Only one topic today, but storing it now means we
                         don't have to change the table later.
      - text:           the post's text content
      - author_handle:  the username of whoever posted it (e.g. "alice.bsky.social").
                         Not used for anything yet, but we're saving it now
                         because a future feature will group posts by the
                         kind of account that posted them.
      - created_at:     when the post was made (from the source platform), as
                         text in ISO 8601 format, e.g. "2026-07-23T10:15:00.000Z"
      - fetched_at:     when *we* saved this row, so we know how fresh
                         our data is
    """
    conn = get_connection()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS posts (
            uri            TEXT PRIMARY KEY,
            source         TEXT NOT NULL DEFAULT 'bluesky',
            topic          TEXT NOT NULL,
            text           TEXT NOT NULL,
            author_handle  TEXT NOT NULL,
            created_at     TEXT NOT NULL,
            fetched_at     TEXT NOT NULL
        )
        """
    )

    # Migration for databases created before "source" existed -- adds the
    # column (defaulting existing rows to "bluesky", the only source that
    # existed then) instead of losing them. A no-op once the column is
    # already there, so it's safe to run on every startup.
    existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(posts)")}
    if "source" not in existing_columns:
        conn.execute("ALTER TABLE posts ADD COLUMN source TEXT NOT NULL DEFAULT 'bluesky'")

    conn.commit()
    conn.close()


if __name__ == "__main__":
    # Running "python db.py" directly just sets up the database file.
    init_db()
    print(f"Database ready at: {DB_PATH}")
