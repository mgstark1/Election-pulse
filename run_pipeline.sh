#!/bin/bash
#
# run_pipeline.sh
#
# Runs the full Election Pulse pipeline once: fetch new posts, redraw the
# chart, and print the day-over-day growth comparison. Meant to be run on
# a schedule (see README.md for how to set that up with cron).
#
# Assumes a virtual environment already exists at ./venv with the project's
# dependencies installed (see README.md).

set -e
cd "$(dirname "$0")"
source venv/bin/activate

LOG_FILE="data/pipeline.log"
mkdir -p data

{
    echo "===== $(date) ====="
    python fetch_posts.py
    python chart.py
    python growth.py
    echo
} >> "$LOG_FILE" 2>&1
