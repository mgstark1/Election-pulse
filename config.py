"""
config.py

Shared helper for loading the list of topics Election Pulse tracks.

Edit topics.json to add, remove, or rename topics -- fetch_posts.py,
chart.py, growth.py, and agent.py all read from it, so nothing else
needs to change.
"""

import json
from pathlib import Path

DEFAULT_TOPICS_PATH = Path(__file__).parent / "topics.json"

# Display-only cutoff: chart.py and growth.py only chart/compare posts
# created at or after this UTC timestamp, so the website shows data "from
# now on" rather than the earlier, less-complete collection runs. The
# underlying database keeps every post ever fetched -- nothing is
# deleted -- so this is easy to change or remove later if we ever want
# to look further back.
DISPLAY_SINCE = "2026-07-31T00:00:00Z"


def load_topics(path=None):
    """Load the list of topics to track from a JSON config file.

    The file should look like:
        {"topics": ["immigration", "healthcare", "economy"]}
    """
    path = Path(path) if path else DEFAULT_TOPICS_PATH
    with open(path) as f:
        data = json.load(f)

    topics = data["topics"]
    if not topics:
        raise SystemExit(f"No topics found in {path}. Add at least one topic to track.")
    return topics
