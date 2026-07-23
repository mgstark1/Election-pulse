"""
palette.py

Shared color palette for both chart.py (matplotlib chart images) and
generate_site.py (the HTML dashboard), so the chart bars and the
dashboard's per-topic accents always match. Colorblind-safe fixed
order, validated with the dataviz skill's scripts/validate_palette.js
(worst adjacent CVD delta 9.2 light / 9.4 dark, both above the >=8
target). Don't reorder or insert colors -- append new topic colors at
the end only, and re-validate if you do.
"""

# (light hex, dark hex) per topic, assigned by position in topics.json.
# Never cycled past 8 -- see TOPIC_COLOR_FALLBACK.
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
TOPIC_COLOR_FALLBACK = ("#898781", "#898781")  # muted ink -- no distinct hues left

# Light/dark chart surfaces and ink, matching the dashboard's CSS
# variables in generate_site.py so a chart image looks native to
# whichever mode it's shown in.
THEME = {
    "light": {
        "surface": "#fcfcfb",
        "ink": "#0b0b0b",
        "ink_secondary": "#52514e",
        "ink_muted": "#898781",
        "grid": "#e1e0d9",
    },
    "dark": {
        "surface": "#1a1a19",
        "ink": "#ffffff",
        "ink_secondary": "#c3c2b7",
        "ink_muted": "#898781",
        "grid": "#2c2c2a",
    },
}


def topic_accent(index, mode="light"):
    """Return the accent hex for the topic at this position in the
    topic list. mode is "light" or "dark"."""
    slot = TOPIC_COLORS[index] if index < len(TOPIC_COLORS) else TOPIC_COLOR_FALLBACK
    return slot[0] if mode == "light" else slot[1]
