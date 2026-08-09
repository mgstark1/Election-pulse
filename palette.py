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
        "baseline": "#c3c2b7",
    },
    "dark": {
        "surface": "#1a1a19",
        "ink": "#ffffff",
        "ink_secondary": "#c3c2b7",
        "ink_muted": "#898781",
        "grid": "#2c2c2a",
        "baseline": "#383835",
    },
}

# Diverging pair for "which side of a baseline" charts (e.g. sentiment %
# positive vs a 50% midpoint) -- reuses the exact blue/red hex already
# validated as TOPIC_COLORS slots 1 and 8, per the dataviz skill's
# documented diverging pair (blue <-> red, warm/cool poles).
DIVERGING = {
    "positive": TOPIC_COLORS[0],  # blue
    "negative": TOPIC_COLORS[7],  # red
}

# Status pair (fixed, not themed -- same hex in light and dark, per the
# dataviz skill's status palette) for "state" uses: a post's sentiment,
# or a stacked bar segment. Mark-safe (>=3:1 on both chart surfaces) but
# NOT text-safe on the light surface -- see DELTA_TEXT below for text.
STATUS_GOOD = "#0ca30c"
STATUS_CRITICAL = "#d03b3b"

# Text-safe green/red for the growth "delta" line (e.g. "+136%"),
# distinct from STATUS_GOOD/STATUS_CRITICAL because those two fail
# WCAG's 4.5:1 text-contrast threshold on at least one surface (status
# good is only 3.27:1 on light; status critical is only 3.62:1 on
# dark) -- fine for a mark, not for small text. "up" reuses this
# project's only documented text-safe delta token (the dataviz skill's
# "success text": #006300 light / #0ca30c dark). "down" has no
# equivalent documented token, so it's derived the same way: for each
# mode, the already-documented red step (status-critical for light,
# TOPIC_COLORS' red dark step for dark) that actually clears 4.5:1 on
# that mode's surface -- computed with the dataviz skill's
# scripts/validate_palette.js contrast() helper, not eyeballed:
#   #d03b3b vs light surface #fcfcfb -> 4.68:1 (passes)
#   #e66767 vs dark surface  #1a1a19 -> 5.39:1 (passes)
DELTA_TEXT = {
    "up": ("#006300", STATUS_GOOD),
    "down": (STATUS_CRITICAL, TOPIC_COLORS[7][1]),
}


def topic_accent(index, mode="light"):
    """Return the accent hex for the topic at this position in the
    topic list. mode is "light" or "dark"."""
    slot = TOPIC_COLORS[index] if index < len(TOPIC_COLORS) else TOPIC_COLOR_FALLBACK
    return slot[0] if mode == "light" else slot[1]


def diverging_color(key, mode="light"):
    """Return the diverging-pair hex for "positive" or "negative"."""
    slot = DIVERGING[key]
    return slot[0] if mode == "light" else slot[1]


def delta_text_color(direction, mode="light"):
    """Return the text-safe delta color for "up" or "down"."""
    slot = DELTA_TEXT[direction]
    return slot[0] if mode == "light" else slot[1]
