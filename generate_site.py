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
from palette import STATUS_CRITICAL, STATUS_GOOD, delta_text_color, topic_accent

OUTPUT_PATH = "index.html"

# An editorial serif for the masthead and topic names, paired with the
# existing system-sans for data and UI chrome -- the same pairing
# broadsheet data journalism (FT, The Economist) uses to read as a
# publication rather than a SaaS dashboard. No web font is loaded (this
# project has no build step and no external dependencies elsewhere);
# these are common system serifs, so the fallback chain always resolves
# to *some* real serif rather than dropping to the browser default.
SERIF = 'Georgia, "Iowan Old Style", Palatino, "Palatino Linotype", serif'

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Election Pulse</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {{
    color-scheme: light;
    --page: #f6f4ee;
    --surface: #fbfaf6;
    --ink: #16150f;
    --ink-secondary: #5b5748;
    --ink-muted: #8c8676;
    --border: rgba(22, 21, 15, 0.13);
    --delta-up: {delta_up_light};
    --delta-down: {delta_down_light};
    --status-good: {status_good};
    --status-critical: {status_critical};
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      color-scheme: dark;
      --page: #121110;
      --surface: #1c1b17;
      --ink: #f5f2ea;
      --ink-secondary: #c7c2b3;
      --ink-muted: #8c8676;
      --border: rgba(255, 255, 255, 0.13);
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
    padding: 2.5rem 1.5rem 4rem;
  }}

  .page {{ max-width: 1120px; margin: 0 auto; }}

  .masthead {{
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 0.5rem 1.5rem;
    padding-bottom: 1.25rem;
    margin-bottom: 2.25rem;
    border-bottom: 1px solid var(--border);
  }}

  .wordmark {{
    font-family: {serif};
    font-size: 2.15rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    margin: 0 0 0.3rem;
  }}

  .tagline {{
    font-size: 1rem;
    color: var(--ink-secondary);
    margin: 0;
  }}

  .updated {{
    color: var(--ink-muted);
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 0.4rem;
    white-space: nowrap;
  }}

  .summary {{
    border-left: 3px solid var(--ink);
    padding: 0.2rem 0 0.2rem 1.25rem;
    margin-bottom: 2.5rem;
  }}

  .summary .label {{
    display: block;
    color: var(--ink-muted);
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.4rem;
  }}

  .summary p {{
    font-family: {serif};
    font-style: italic;
    font-size: 1.1rem;
    line-height: 1.55;
    color: var(--ink);
    margin: 0;
  }}

  .grid {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 2rem;
  }}

  .card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 3px;
    padding: 1.5rem 1.5rem 1.75rem;
  }}

  .topic-heading {{
    display: flex;
    align-items: center;
    gap: 0.55rem;
    margin: 0 0 0.9rem;
  }}

  .topic-dot {{
    flex: none;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent-light);
  }}
  @media (prefers-color-scheme: dark) {{
    .topic-dot {{ background: var(--accent-dark); }}
  }}

  .card h2 {{
    font-family: {serif};
    font-weight: 700;
    font-size: 1.2rem;
    margin: 0;
  }}

  .trending {{
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    font-size: 0.66rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--delta-up);
    border: 1px solid var(--delta-up);
    border-radius: 3px;
    padding: 0.18rem 0.5rem;
    margin: 0 0 0.85rem;
  }}

  .stat {{ margin: 0 0 1.1rem; }}

  .stat-primary {{
    display: flex;
    align-items: baseline;
    gap: 0.5rem;
    flex-wrap: wrap;
  }}

  .stat-value {{
    font-size: 1.9rem;
    font-weight: 600;
    letter-spacing: -0.01em;
    font-variant-numeric: tabular-nums;
  }}

  .stat-label {{
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ink-muted);
  }}

  .stat-delta {{
    display: block;
    margin-top: 0.3rem;
    font-size: 0.85rem;
    font-weight: 600;
    color: var(--ink-secondary);
  }}

  .stat-delta.up {{ color: var(--delta-up); }}
  .stat-delta.down {{ color: var(--delta-down); }}

  .sentiment-block {{ margin: 0 0 0.25rem; }}

  .sentiment-bar {{
    display: flex;
    height: 6px;
    border-radius: 3px;
    overflow: hidden;
    background: var(--border);
    margin-bottom: 0.45rem;
  }}

  .sentiment-bar .pos {{ background: var(--status-good); }}
  .sentiment-bar .neg {{ background: var(--status-critical); }}

  .sentiment-caption {{
    font-size: 0.78rem;
    color: var(--ink-secondary);
    margin: 0;
  }}

  .chart-caption {{
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--ink-muted);
    margin: 1.35rem 0 0.5rem;
  }}

  .note {{
    color: var(--ink-muted);
    font-size: 0.9rem;
    font-style: italic;
    margin: 0 0 1rem;
  }}

  .card img {{
    width: 100%;
    border-radius: 2px;
    display: block;
    cursor: zoom-in;
  }}

  #lightbox-overlay {{
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.85);
    align-items: center;
    justify-content: center;
    z-index: 1000;
    padding: 2rem;
    cursor: zoom-out;
  }}

  #lightbox-overlay.open {{
    display: flex;
  }}

  #lightbox-overlay img {{
    max-width: 100%;
    max-height: 100%;
    border-radius: 4px;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  }}

  #lightbox-close {{
    position: fixed;
    top: 1.5rem;
    right: 1.5rem;
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 999px;
    border: none;
    background: rgba(255, 255, 255, 0.15);
    color: #ffffff;
    font-size: 1.25rem;
    line-height: 1;
    cursor: pointer;
  }}

  .no-chart {{
    color: var(--ink-muted);
    font-style: italic;
    font-size: 0.9rem;
    margin: 0;
  }}

  .site-footer {{
    margin-top: 3rem;
    padding-top: 1.5rem;
    border-top: 1px solid var(--border);
    color: var(--ink-muted);
    font-size: 0.82rem;
    line-height: 1.6;
  }}

  .site-footer .footer-label {{
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--ink-secondary);
  }}

  @media (max-width: 480px) {{
    .wordmark {{ font-size: 1.7rem; }}
    body {{ padding: 1.75rem 1rem 3rem; }}
  }}
</style>
</head>
<body>
<div class="page">
<header class="masthead">
  <div>
    <h1 class="wordmark">Election Pulse</h1>
    <p class="tagline">The UK's political conversation, in real time.</p>
  </div>
  <p class="updated">Updated {updated_at}</p>
</header>
{summary_html}
<div class="grid">
{sections}
</div>
<footer class="site-footer">
  <p><span class="footer-label">Phase 1</span> &mdash; This dashboard currently
  tracks mention volume, growth and sentiment for each topic on Bluesky, an
  early, working version of a bigger plan. Coming next: richer AI-driven
  analysis explaining <em>why</em> a topic is trending, and more topic
  categories.</p>
</footer>
</div>
<div id="lightbox-overlay">
  <button id="lightbox-close" aria-label="Close">&times;</button>
  <img id="lightbox-image" src="" alt="">
</div>
<script>
(function () {{
  var overlay = document.getElementById('lightbox-overlay');
  var overlayImg = document.getElementById('lightbox-image');
  var closeBtn = document.getElementById('lightbox-close');

  function openLightbox(img) {{
    overlayImg.src = img.currentSrc || img.src;
    overlayImg.alt = img.alt;
    overlay.classList.add('open');
  }}

  function closeLightbox() {{
    overlay.classList.remove('open');
    overlayImg.src = '';
  }}

  document.querySelectorAll('.card img').forEach(function (img) {{
    img.addEventListener('click', function () {{ openLightbox(img); }});
  }});

  overlay.addEventListener('click', closeLightbox);
  closeBtn.addEventListener('click', closeLightbox);
  document.addEventListener('keydown', function (e) {{
    if (e.key === 'Escape') closeLightbox();
  }});
}})();
</script>
</body>
</html>
"""


def render_stat(growth_result):
    """Render the stat-block markup (value + delta, or a plain note when
    there isn't enough data yet for a number)."""
    status = growth_result["status"]

    if status == "ok":
        is_up = growth_result["growth_pct"] >= 0
        arrow = "▲" if is_up else "▼"
        sign = "+" if is_up else ""
        direction_class = "up" if is_up else "down"
        return (
            '<div class="stat">'
            '<div class="stat-primary">'
            f'<span class="stat-value">{growth_result["today_count"]}</span>'
            '<span class="stat-label">mentions today</span>'
            "</div>"
            f'<span class="stat-delta {direction_class}">{arrow} {sign}{growth_result["growth_pct"]:.0f}% vs yesterday</span>'
            "</div>"
        )
    if status == "zero_yesterday":
        return (
            '<div class="stat">'
            '<div class="stat-primary">'
            f'<span class="stat-value">{growth_result["today_count"]}</span>'
            '<span class="stat-label">mentions today</span>'
            "</div>"
            '<span class="stat-delta">no baseline (0 yesterday)</span>'
            "</div>"
        )
    if status == "insufficient_history":
        return f'<p class="note">Not enough data yet to compare day over day (earliest post: {growth_result["earliest_day"]}).</p>'
    return '<p class="note">No posts collected yet.</p>'


def render_sentiment_bar(sentiment_result):
    """Render sentiment as a compact positive/negative proportion bar
    plus its underlying counts, or nothing if there's no result to show
    yet (model not trained, or no posts). Same numbers
    render_sentiment() used to print as plain text -- just a faster
    shape to scan across cards."""
    if sentiment_result is None or sentiment_result["status"] != "ok":
        return ""

    positive = sentiment_result["positive"]
    negative = sentiment_result["negative"]
    total = sentiment_result["total"]
    positive_pct = 100 * positive / total

    return (
        '<div class="sentiment-block">'
        '<div class="sentiment-bar">'
        f'<span class="pos" style="width: {positive_pct:.1f}%"></span>'
        f'<span class="neg" style="width: {100 - positive_pct:.1f}%"></span>'
        "</div>"
        f'<p class="sentiment-caption">{positive} positive &middot; {negative} negative</p>'
        "</div>"
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


def render_topic_section(
    topic, growth_result, sentiment_result, light_accent, dark_accent, is_top_growth=False
):
    slug = slugify(topic)
    topic_escaped = html.escape(topic)

    mentions_chart_html = render_chart_picture(
        f"data/mentions_over_time_{slug}.png",
        f"data/mentions_over_time_{slug}_dark.png",
        f"{topic_escaped} mentions over time",
        "No chart yet -- run fetch_posts.py for this topic first.",
    )
    mentions_block = f'<p class="chart-caption">Mentions, by day</p>\n{mentions_chart_html}'

    # No fallback message for the sentiment trend chart -- unlike the
    # mentions chart, it's expected to be absent for a while (needs 2+
    # days of data, or no trained model yet), and a blank card region is
    # less noisy than repeating a caveat every single day until then.
    sentiment_chart_html = render_chart_picture(
        f"data/sentiment_over_time_{slug}.png",
        f"data/sentiment_over_time_{slug}_dark.png",
        f"{topic_escaped} sentiment over time",
    )
    sentiment_chart_block = (
        f'<p class="chart-caption">Sentiment, % positive over time</p>\n{sentiment_chart_html}'
        if sentiment_chart_html
        else ""
    )

    trending_html = (
        '<p class="trending">&uarr; Fastest growing</p>' if is_top_growth else ""
    )

    style = f"--accent-light: {light_accent}; --accent-dark: {dark_accent};"
    return f"""
    <div class="card" style="{style}">
      <div class="topic-heading">
        <span class="topic-dot"></span>
        <h2>{html.escape(topic.capitalize())}</h2>
      </div>
      {trending_html}
      {render_stat(growth_result)}
      {render_sentiment_bar(sentiment_result)}
      {mentions_block}
      {sentiment_chart_block}
    </div>
    """


def rank_topics_by_growth(topics, growth_by_topic):
    """Order topics fastest-growing first, so emerging stories surface
    above flat/declining ones instead of always sitting in topics.json
    order. Topics without a comparable growth_pct (no data yet,
    insufficient history, or no baseline) sort after every "ok" topic,
    keeping their original relative order (Python's sort is stable).

    Returns (ranked_topics, top_growth_topic) -- top_growth_topic is
    None unless some topic actually grew (growth_pct > 0), so a page
    where every topic is flat or shrinking gets no "fastest growing"
    badge at all.
    """
    def rank_key(topic):
        result = growth_by_topic.get(topic, {"status": "no_data"})
        if result["status"] == "ok":
            return (0, -result["growth_pct"])
        return (1, 0)

    ranked_topics = sorted(topics, key=rank_key)

    top_growth_topic = None
    best_growth_pct = 0
    for topic in topics:
        result = growth_by_topic.get(topic, {"status": "no_data"})
        if result["status"] == "ok" and result["growth_pct"] > best_growth_pct:
            best_growth_pct = result["growth_pct"]
            top_growth_topic = topic

    return ranked_topics, top_growth_topic


def render_page(topics, growth_results, sentiment_results=None, summary=None):
    growth_by_topic = {r["topic"]: r for r in growth_results}
    sentiment_by_topic = {r["topic"]: r for r in (sentiment_results or [])}

    ranked_topics, top_growth_topic = rank_topics_by_growth(topics, growth_by_topic)

    # Colors stay tied to each topic's position in topics.json (its
    # identity), not its rank -- otherwise a topic's color would shift
    # day to day as growth rates change places. See palette.py.
    accent_index = {topic: i for i, topic in enumerate(topics)}

    sections = "\n".join(
        render_topic_section(
            topic,
            growth_by_topic[topic],
            sentiment_by_topic.get(topic),
            topic_accent(accent_index[topic], "light"),
            topic_accent(accent_index[topic], "dark"),
            is_top_growth=(topic == top_growth_topic),
        )
        for topic in ranked_topics
    )
    updated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    summary_html = (
        f'<div class="summary"><span class="label">AI summary</span><p>{html.escape(summary)}</p></div>'
        if summary
        else ""
    )

    return PAGE_TEMPLATE.format(
        updated_at=updated_at,
        summary_html=summary_html,
        sections=sections,
        serif=SERIF,
        delta_up_light=delta_text_color("up", "light"),
        delta_up_dark=delta_text_color("up", "dark"),
        delta_down_light=delta_text_color("down", "light"),
        delta_down_dark=delta_text_color("down", "dark"),
        status_good=STATUS_GOOD,
        status_critical=STATUS_CRITICAL,
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
