"""
generate_site.py

Builds a simple static HTML dashboard (index.html) summarizing the
latest fetched data -- one chart per topic plus each topic's current
day-over-day growth, and the latest AI summary if one exists. Meant to
be committed alongside data/ so GitHub Pages can serve it as a live,
always-current public page.

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
from chart import slugify
from config import load_topics

OUTPUT_PATH = "index.html"

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Election Pulse</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    max-width: 900px;
    margin: 2rem auto;
    padding: 0 1rem;
    color: #1a1a1a;
    background: #fff;
  }}
  h1 {{ margin-bottom: 0; }}
  .updated {{ color: #666; margin-top: 0.25rem; margin-bottom: 2rem; }}
  .summary {{
    background: #f5f5f5;
    border-left: 4px solid #444;
    padding: 0.75rem 1rem;
    margin-bottom: 2rem;
    font-style: italic;
  }}
  .topic {{ margin-bottom: 3rem; }}
  .topic img {{ max-width: 100%; border: 1px solid #ddd; border-radius: 4px; }}
  .topic .no-chart {{ color: #888; font-style: italic; }}
  .growth {{ font-size: 1.1rem; font-weight: 600; }}
</style>
</head>
<body>
<h1>Election Pulse</h1>
<p class="updated">Last updated: {updated_at}</p>
{summary_html}
{sections}
</body>
</html>
"""


def render_topic_section(topic, growth_result):
    slug = slugify(topic)
    chart_path = f"data/mentions_over_time_{slug}.png"
    growth_line = growth.format_result(growth_result)

    if os.path.exists(chart_path):
        chart_html = (
            f'<img src="{chart_path}" alt="{html.escape(topic)} mentions over time" loading="lazy">'
        )
    else:
        chart_html = '<p class="no-chart">No chart yet -- run fetch_posts.py for this topic first.</p>'

    return f"""
    <section class="topic">
      <h2>{html.escape(topic.capitalize())}</h2>
      {chart_html}
      <p class="growth">{html.escape(growth_line)}</p>
    </section>
    """


def render_page(topics, growth_results, summary=None):
    growth_by_topic = {r["topic"]: r for r in growth_results}
    sections = "\n".join(
        render_topic_section(topic, growth_by_topic[topic]) for topic in topics
    )
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    summary_html = (
        f'<p class="summary">{html.escape(summary)}</p>' if summary else ""
    )

    return PAGE_TEMPLATE.format(
        updated_at=updated_at,
        summary_html=summary_html,
        sections=sections,
    )


def build_site(topics=None, growth_results=None, summary=None):
    if topics is None:
        topics = load_topics()
    if growth_results is None:
        growth_results = growth.main(topics)

    page = render_page(topics, growth_results, summary=summary)
    with open(OUTPUT_PATH, "w") as f:
        f.write(page)

    print(f"Site written to {OUTPUT_PATH}")
    return OUTPUT_PATH


if __name__ == "__main__":
    build_site()
