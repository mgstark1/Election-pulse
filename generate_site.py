"""
generate_site.py

Builds a static HTML dashboard (index.html) summarizing the latest
fetched data -- a stat tile + chart per topic, and the latest AI
summary if one exists. Meant to be committed alongside data/ so GitHub
Pages can serve it as a live, always-current public page.

HOW TO RUN IT:
    python generate_site.py

agent.py calls this automatically after computing growth results, so
you don't normally need to run it by hand -- but it works standalone
too, using whatever's already in the database.
"""

import html
import os
from datetime import datetime, timezone

import growth
import sentiment
from chart import slugify
from config import load_topics
from palette import delta_text_color, topic_accent

OUTPUT_PATH = "index.html"

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Election Pulse</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    color-scheme: light;
    --page: #f9f9f7;
    --surface: #fcfcfb;
    --ink: #0b0b0b;
    --ink-secondary: #52514e;
    --ink-muted: #898781;
    --border: rgba(11,11,11,0.10);
    --delta-up: {delta_up_light};
    --delta-down: {delta_down_light};
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      color-scheme: dark;
      --page: #0d0d0d;
      --surface: #1a1a19;
      --ink: #ffffff;
      --ink-secondary: #c3c2b7;
      --ink-muted: #898781;
      --border: rgba(255,255,255,0.10);
      --delta-up: {delta_up_dark};
      --delta-down: {delta_down_dark};
    }}
  }}

  * {{ box-sizing: border-box; }}

  body {{
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
    background: var(--page);
    color: var(--ink);
    margin: 0;
    padding: 2.5rem 1.25rem 4rem;
  }}

  .page {{ max-width: 1000px; margin: 0 auto; }}

  header h1 {{
    font-size: 1.75rem;
    margin: 0 0 0.25rem;
    letter-spacing: -0.02em;
  }}

  .updated {{
    color: var(--ink-muted);
    font-size: 0.875rem;
    margin: 0 0 2rem;
  }}

  .roadmap {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1.1rem 1.25rem;
    margin-bottom: 1.75rem;
    color: var(--ink-secondary);
    font-size: 0.9rem;
    line-height: 1.6;
  }}

  .roadmap .badge {{
    display: inline-block;
    background: var(--ink);
    color: var(--surface);
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
    margin-bottom: 0.65rem;
  }}

  .roadmap p {{ margin: 0; }}

  .roadmap strong {{
    color: var(--ink);
    font-weight: 600;
  }}

  .summary {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 3px solid #2a78d6;
    border-radius: 8px;
    padding: 1rem 1.25rem;
    margin-bottom: 2.5rem;
    color: var(--ink-secondary);
    font-size: 0.95rem;
    line-height: 1.5;
  }}

  .summary .label {{
    display: block;
    color: var(--ink);
    font-size: 0.75rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.35rem;
  }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 1.5rem;
  }}

  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-top: 3px solid var(--accent-light);
    border-radius: 12px;
    padding: 1.5rem;
  }}
  @media (prefers-color-scheme: dark) {{
    .card {{ border-top-color: var(--accent-dark); }}
  }}

  .card h2 {{
    margin: 0 0 0.75rem;
    font-size: 1.1rem;
  }}

  .stat {{
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    margin-bottom: 1rem;
    flex-wrap: wrap;
  }}

  .stat .value {{
    font-size: 2rem;
    font-weight: 600;
    letter-spacing: -0.02em;
  }}

  .stat .unit {{
    font-size: 0.8rem;
    color: var(--ink-muted);
  }}

  .stat .delta {{
    font-size: 0.95rem;
    font-weight: 600;
    color: var(--ink-secondary);
  }}

  .stat .delta.up {{ color: var(--delta-up); }}
  .stat .delta.down {{ color: var(--delta-down); }}

  .sentiment {{
    color: var(--ink-secondary);
    font-size: 0.85rem;
    margin: 0 0 1rem;
  }}

  .note {{
    color: var(--ink-muted);
    font-size: 0.9rem;
    margin-bottom: 1rem;
  }}

  .card img {{
    width: 100%;
    border-radius: 6px;
    display: block;
  }}

  .no-chart {{
    color: var(--ink-muted);
    font-style: italic;
    font-size: 0.9rem;
    margin: 0;
  }}
</style>
</head>
<body>
<div class="page">
<header>
  <h1>Election Pulse</h1>
  <p class="updated">Last updated: {updated_at}</p>
</header>
<div class="roadmap">
  <span class="badge">Phase 1</span>
  <p>This dashboard currently tracks raw mention volume for each topic on
  Bluesky -- an early, working version of a bigger plan. Coming next:
  <strong>richer AI-driven analysis</strong> explaining <em>why</em> a
  topic is trending (not just a one-line summary),
  <strong>more topic categories</strong>, and
  <strong>growth-rate rankings</strong> to surface emerging stories
  faster than raw volume alone.</p>
</div>
{summary_html}
<div class="grid">
{sections}
</div>
</div>
</body>
</html>
"""


def render_stat(growth_result):
    """Render the stat-tile markup (value + delta, or a plain note when
    there isn't enough data yet for a number)."""
    status = growth_result["status"]

    if status == "ok":
        is_up = growth_result["growth_pct"] >= 0
        arrow = "▲" if is_up else "▼"
        sign = "+" if is_up else ""
        direction_class = "up" if is_up else "down"
        return (
            '<div class="stat">'
            f'<span class="value">{growth_result["today_count"]}</span>'
            '<span class="unit">mentions today</span>'
            f'<span class="delta {direction_class}">{arrow} {sign}{growth_result["growth_pct"]:.0f}% vs yesterday</span>'
            "</div>"
        )
    if status == "zero_yesterday":
        return (
            '<div class="stat">'
            f'<span class="value">{growth_result["today_count"]}</span>'
            '<span class="unit">mentions today</span>'
            '<span class="delta">no baseline (0 yesterday)</span>'
            "</div>"
        )
    if status == "insufficient_history":
        return f'<p class="note">Not enough data yet to compare day over day (earliest post: {growth_result["earliest_day"]}).</p>'
    return '<p class="note">No posts collected yet.</p>'


def render_sentiment(sentiment_result):
    """Render the sentiment line for a topic, or nothing if there's no
    result to show yet (model not trained, or no posts)."""
    if sentiment_result is None or sentiment_result["status"] != "ok":
        return ""
    return (
        f'<p class="sentiment">{sentiment_result["positive"]} positive · '
        f'{sentiment_result["negative"]} negative</p>'
    )


def render_chart_picture(light_path, dark_path, alt, missing_message=None):
    """Render a light/dark <picture> pair for a chart image. If the
    light-mode image doesn't exist yet, returns missing_message as a
    fallback note, or "" if no message was given (e.g. a chart that's
    expected to be legitimately absent for a while, where repeating a
    caveat every day would just be noise)."""
    if not os.path.exists(light_path):
        return f'<p class="no-chart">{missing_message}</p>' if missing_message else ""

    if os.path.exists(dark_path):
        # The dark-mode image is rendered to match; show it when the
        # visitor's system is in dark mode instead of a light-surface
        # chart forced into a dark page.
        return (
            "<picture>"
            f'<source srcset="{dark_path}" media="(prefers-color-scheme: dark)">'
            f'<img src="{light_path}" alt="{alt}" loading="lazy">'
            "</picture>"
        )
    return f'<img src="{light_path}" alt="{alt}" loading="lazy">'


def render_topic_section(topic, growth_result, sentiment_result, light_accent, dark_accent):
    slug = slugify(topic)
    topic_escaped = html.escape(topic)

    mentions_chart_html = render_chart_picture(
        f"data/mentions_over_time_{slug}.png",
        f"data/mentions_over_time_{slug}_dark.png",
        f"{topic_escaped} mentions over time",
        "No chart yet -- run fetch_posts.py for this topic first.",
    )

    # No fallback message for the sentiment trend chart -- unlike the
    # mentions chart, it's expected to be absent for a while (needs 2+
    # days of data, or no trained model yet), and a blank card region is
    # less noisy than repeating a caveat every single day until then.
    sentiment_chart_html = render_chart_picture(
        f"data/sentiment_over_time_{slug}.png",
        f"data/sentiment_over_time_{slug}_dark.png",
        f"{topic_escaped} sentiment over time",
    )

    style = f"--accent-light: {light_accent}; --accent-dark: {dark_accent};"
    return f"""
    <div class="card" style="{style}">
      <h2>{html.escape(topic.capitalize())}</h2>
      {render_stat(growth_result)}
      {render_sentiment(sentiment_result)}
      {mentions_chart_html}
      {sentiment_chart_html}
    </div>
    """


def render_page(topics, growth_results, sentiment_results=None, summary=None):
    growth_by_topic = {r["topic"]: r for r in growth_results}
    sentiment_by_topic = {r["topic"]: r for r in (sentiment_results or [])}

    sections = "\n".join(
        render_topic_section(
            topic,
            growth_by_topic[topic],
            sentiment_by_topic.get(topic),
            topic_accent(i, "light"),
            topic_accent(i, "dark"),
        )
        for i, topic in enumerate(topics)
    )
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    summary_html = (
        f'<div class="summary"><span class="label">AI summary</span>{html.escape(summary)}</div>'
        if summary
        else ""
    )

    return PAGE_TEMPLATE.format(
        updated_at=updated_at,
        summary_html=summary_html,
        sections=sections,
        delta_up_light=delta_text_color("up", "light"),
        delta_up_dark=delta_text_color("up", "dark"),
        delta_down_light=delta_text_color("down", "light"),
        delta_down_dark=delta_text_color("down", "dark"),
    )


def build_site(topics=None, growth_results=None, sentiment_results=None, summary=None):
    if topics is None:
        topics = load_topics()
    if growth_results is None:
        growth_results = growth.main(topics)
    if sentiment_results is None:
        sentiment_results = sentiment.main(topics)

    page = render_page(topics, growth_results, sentiment_results=sentiment_results, summary=summary)
    with open(OUTPUT_PATH, "w") as f:
        f.write(page)

    print(f"Site written to {OUTPUT_PATH}")
    return OUTPUT_PATH


if __name__ == "__main__":
    build_site()
