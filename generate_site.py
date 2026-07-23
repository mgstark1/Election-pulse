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
from chart import slugify
from config import load_topics

OUTPUT_PATH = "index.html"

# Fixed-order categorical palette (light / dark), one accent color per
# topic card. Order matters for colorblind-safe separation between
# adjacent slots -- never reassign or cycle past 8 topics; beyond that,
# TOPIC_COLOR_FALLBACK is used instead of generating a 9th hue.
TOPIC_COLORS = [
    ("#2a78d6", "#3987e5"),  # blue
    ("#eb6834", "#d95926"),  # orange
    ("#1baf7a", "#199e70"),  # aqua
    ("#eda100", "#c98500"),  # yellow
    ("#e87ba4", "#d55181"),  # magenta
    ("#008300", "#008300"),  # green
    ("#4a3aa7", "#9085e9"),  # violet
    ("#e34948", "#e66767"),  # red
]
TOPIC_COLOR_FALLBACK = ("#898781", "#898781")  # muted ink -- no more distinct hues left

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
    border-top: 3px solid var(--accent);
    border-radius: 12px;
    padding: 1.5rem;
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
    color: var(--ink-secondary);
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
        arrow = "▲" if growth_result["growth_pct"] >= 0 else "▼"
        sign = "+" if growth_result["growth_pct"] >= 0 else ""
        return (
            '<div class="stat">'
            f'<span class="value">{growth_result["today_count"]}</span>'
            '<span class="unit">mentions today</span>'
            f'<span class="delta">{arrow} {sign}{growth_result["growth_pct"]:.0f}% vs yesterday</span>'
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


def render_topic_section(topic, growth_result, accent):
    slug = slugify(topic)
    chart_path = f"data/mentions_over_time_{slug}.png"

    if os.path.exists(chart_path):
        chart_html = (
            f'<img src="{chart_path}" alt="{html.escape(topic)} mentions over time" loading="lazy">'
        )
    else:
        chart_html = '<p class="no-chart">No chart yet -- run fetch_posts.py for this topic first.</p>'

    return f"""
    <div class="card" style="--accent: {accent};">
      <h2>{html.escape(topic.capitalize())}</h2>
      {render_stat(growth_result)}
      {chart_html}
    </div>
    """


def render_page(topics, growth_results, summary=None):
    growth_by_topic = {r["topic"]: r for r in growth_results}

    # Card accents use each slot's light-mode hex in both color schemes.
    # Both the light and dark step of every slot pass the same CVD/
    # contrast checks, so reusing the light value under dark mode is
    # still accessible -- just a slightly less-tuned accent -- and it
    # keeps this simple (no separate dark-mode HTML to generate).
    sections = "\n".join(
        render_topic_section(
            topic,
            growth_by_topic[topic],
            (TOPIC_COLORS[i] if i < len(TOPIC_COLORS) else TOPIC_COLOR_FALLBACK)[0],
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
    )


def build_site(topics=None, growth_results=None, summary=None):
    if topics is None:
        topics = load_topics()
    if growth_results is None:
        growth_results = growth.main(topics)

    # Accent colors are set via a CSS custom property per card, using the
    # light-mode hex; the browser's own dark-mode media query swap for
    # everything else (surfaces, ink) doesn't touch these accents, which
    # is fine -- both the light and dark steps for each slot pass the
    # same CVD/contrast checks, so using the light value in both modes
    # doesn't break accessibility, it's just a slightly less-tuned dark
    # accent. Good enough for a small set of card top-borders.
    page = render_page(topics, growth_results, summary=summary)
    with open(OUTPUT_PATH, "w") as f:
        f.write(page)

    print(f"Site written to {OUTPUT_PATH}")
    return OUTPUT_PATH


if __name__ == "__main__":
    build_site()
