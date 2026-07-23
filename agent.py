"""
agent.py

Single entry point for the Election Pulse pipeline. For every topic in
topics.json, it:
    1. Fetches new posts from Bluesky (fetch_posts.py)
    2. Redraws that topic's hourly mentions chart (chart.py)
    3. Computes that topic's day-over-day growth (growth.py)

It then asks the Anthropic API to write a short natural-language
summary comparing what changed across all topics (e.g. "immigration
mentions up 40%, healthcare flat, economy down 12%"), regenerates the
index.html dashboard (see generate_site.py), and commits + pushes
everything new back to git, so historical data persists across runs
even when this script executes somewhere with no permanent local
storage (e.g. a scheduled cloud job). If GitHub Pages is enabled for
this repo (see README.md), that push also updates the live site.

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
import generate_site
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
    day's growth numbers across all topics, using web search to check for
    news that might explain any notable swings. Returns None (and prints
    why) if ANTHROPIC_API_KEY isn't configured, so the rest of the
    pipeline still works without it.
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
        max_tokens=500,
        tools=[{"type": "web_search_20260209", "name": "web_search", "max_uses": 3}],
        messages=[
            {
                "role": "user",
                "content": (
                    "Here is today's day-over-day mention growth for "
                    "several topics tracked on Bluesky:\n\n"
                    f"{stats_text}\n\n"
                    "For any topic with a notable change (a double-digit "
                    "percent move, or a swing from/to zero), search the "
                    "web briefly for recent news that might explain it. "
                    "Then write a short (2-4 sentence) natural-language "
                    "summary of what changed across topics, in the style "
                    "of a news brief -- mention a plausible news tie-in "
                    "where you found one. Example: 'Immigration mentions "
                    "up 40%, likely tied to yesterday's court ruling on "
                    "asylum claims; healthcare flat; economy down 12%.' "
                    "If nothing explains a move, just report the numbers "
                    "plainly."
                ),
            }
        ],
    )

    # message.content can include server_tool_use / web_search_tool_result
    # blocks alongside the final text -- keep only the text.
    text_blocks = [block.text for block in message.content if block.type == "text"]
    summary = "\n".join(text_blocks).strip()
    return summary or None


def commit_and_push_data():
    """Commit any new/changed files under data/ (plus topics.json) so
    history persists across runs, then push to the current branch.
    Failures are logged as warnings rather than raised, so a git problem
    doesn't erase a successful pipeline run.
    """
    try:
        subprocess.run(["git", "add", "data/", "topics.json", "index.html"], check=True)

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

    generate_site.build_site(topics, growth_results, summary=summary)

    commit_and_push_data()


if __name__ == "__main__":
    run()
