"""
agent.py

Single entry point for the Election Pulse pipeline. For every topic in
topics.json, it:
    1. Fetches new posts from Bluesky (fetch_posts.py)
    2. Redraws that topic's hourly mentions chart (chart.py)
    3. Computes that topic's day-over-day growth (growth.py)

It then asks the Anthropic API to write a short natural-language
summary comparing what changed across all topics (e.g. "immigration
mentions up 40%, healthcare flat, economy down 12%"), and commits +
pushes everything new under data/ back to git, so historical data
persists across runs even when this script executes somewhere with no
permanent local storage (e.g. a scheduled cloud job).

HOW TO RUN IT:
    python agent.py

SETUP REQUIRED:
    Same .env as fetch_posts.py (BLUESKY_HANDLE, BLUESKY_APP_PASSWORD),
    plus ANTHROPIC_API_KEY for the natural-language summary step. If
    ANTHROPIC_API_KEY isn't set, the rest of the pipeline still runs --
    the summary step is just skipped.
"""

import os
import subprocess
from datetime import datetime, timezone

from dotenv import load_dotenv

import chart
import fetch_posts
import growth
from config import load_topics

SUMMARY_LOG_PATH = "data/agent_summary_log.txt"


def format_growth_for_prompt(growth_results):
    lines = []
    for result in growth_results:
        status = result["status"]
        topic = result["topic"]
        if status == "ok":
            sign = "+" if result["growth_pct"] >= 0 else ""
            lines.append(
                f"{topic}: {result['today_count']} today vs "
                f"{result['yesterday_count']} yesterday "
                f"({sign}{result['growth_pct']:.0f}%)"
            )
        elif status == "zero_yesterday":
            lines.append(f"{topic}: {result['today_count']} today vs 0 yesterday (no baseline)")
        elif status == "insufficient_history":
            lines.append(f"{topic}: not enough historical data yet")
        else:
            lines.append(f"{topic}: no data yet")
    return "\n".join(lines)


def generate_summary(growth_results):
    """Ask the Anthropic API for a short natural-language summary of the
    day's growth numbers across all topics. Returns None (and prints why)
    if ANTHROPIC_API_KEY isn't configured, so the rest of the pipeline
    still works without it.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ANTHROPIC_API_KEY not set; skipping natural-language summary.")
        return None

    from anthropic import Anthropic

    stats_text = format_growth_for_prompt(growth_results)
    client = Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": (
                    "Here is today's day-over-day mention growth for "
                    "several topics tracked on Bluesky:\n\n"
                    f"{stats_text}\n\n"
                    "Write a short (1-2 sentence) natural-language summary "
                    "of what changed across topics, in the style of a "
                    "news brief. Example: 'Immigration mentions up 40%, "
                    "healthcare flat, economy down 12%.'"
                ),
            }
        ],
    )
    return message.content[0].text.strip()


def commit_and_push_data():
    """Commit any new/changed files under data/ (plus topics.json) so
    history persists across runs, then push to the current branch.
    Failures are logged as warnings rather than raised, so a git problem
    doesn't erase a successful pipeline run.
    """
    try:
        subprocess.run(["git", "add", "data/", "topics.json"], check=True)

        # git diff --cached --quiet exits 0 if there's nothing staged.
        diff_check = subprocess.run(["git", "diff", "--cached", "--quiet"])
        if diff_check.returncode == 0:
            print("No new data to commit.")
            return

        timestamp = datetime.now(timezone.utc).isoformat()
        subprocess.run(
            ["git", "commit", "-m", f"Update Election Pulse data ({timestamp})"],
            check=True,
        )

        branch = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        push = subprocess.run(["git", "push", "-u", "origin", branch])
        if push.returncode != 0:
            # Someone/something else may have pushed in the meantime --
            # rebase onto the latest remote state and retry once.
            subprocess.run(["git", "pull", "--rebase", "origin", branch], check=True)
            subprocess.run(["git", "push", "-u", "origin", branch], check=True)

        print(f"Committed and pushed data updates to {branch}.")
    except subprocess.CalledProcessError as e:
        print(f"Warning: failed to commit/push data ({e}). Continuing.")


def run(topics=None):
    load_dotenv()
    if topics is None:
        topics = load_topics()

    print(f"Running Election Pulse agent for topics: {', '.join(topics)}")

    fetch_posts.fetch_all_topics(topics)
    chart.main(topics)
    growth_results = growth.main(topics)

    summary = generate_summary(growth_results)
    if summary:
        print("\nSummary:")
        print(summary)
        os.makedirs("data", exist_ok=True)
        with open(SUMMARY_LOG_PATH, "a") as f:
            f.write(f"{datetime.now(timezone.utc).isoformat()}  {summary}\n")

    commit_and_push_data()


if __name__ == "__main__":
    run()
