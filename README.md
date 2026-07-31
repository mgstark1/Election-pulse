# Election Pulse

A UK General Election narrative tracker.

**Current phase:** a multi-topic pipeline that tracks mentions of several
topics (see `topics.json`) on Bluesky, and can run itself as a single
autonomous agent. This is step one of a bigger project (see "Long-term
vision" below) -- for now it just proves that we can fetch posts, save
them, chart them per topic, and summarize what changed.

## What's in this repo

- `topics.json` -- the list of topics to track (edit this to add/remove
  topics; everything else reads from it)
- `config.py` -- shared helper that loads `topics.json`
- `db.py` -- sets up the SQLite database (a single file, no server needed)
- `fetch_posts.py` -- logs in to Bluesky and saves recent posts mentioning
  each topic in `topics.json`, tagged by topic
- `chart.py` -- reads the database and draws one chart per topic of how
  many posts were made per hour, so you can see the data is real. Saves
  a light-mode and a dark-mode version of each chart (styled with
  `palette.py`), so the dashboard shows the right one for the visitor's
  system color scheme
- `growth.py` -- compares today's mention count to yesterday's for each
  topic and prints the percentage change, e.g. "Immigration: 45 mentions
  today vs 20 yesterday (+125%)"
- `agent.py` -- the single entry point: runs fetch -> chart -> growth for
  every topic, asks the Anthropic API for a short natural-language
  summary of what changed across topics, regenerates `index.html`, and
  commits the updated data back to git so history persists even on
  ephemeral compute
- `generate_site.py` -- builds `index.html`, a public dashboard page with
  a stat tile + chart per topic (see "Publishing as a website" below)
- `palette.py` -- the colorblind-safe color palette shared by `chart.py`
  and `generate_site.py`, so chart bars and dashboard accents always
  match. Don't reorder or edit the hex values without re-validating
  colorblind-safety first
- `data/` -- where the database file (`election_pulse.db`), chart images
  (light + dark per topic), and the agent's summary log get saved.
  `agent.py` commits these to git itself (see "Automated commits" below).

## One-time setup

### 1. Install Python dependencies

It's good practice to use a "virtual environment" so this project's
packages don't clash with anything else on your machine:

```bash
python3 -m venv venv
source venv/bin/activate      # on Windows: venv\Scripts\activate
pip install -r requirements.txt
```

You'll need to run `source venv/bin/activate` again each time you open a
new terminal to work on this project.

### 2. Create a Bluesky "app password"

Don't use your real Bluesky password in this project. Instead, create a
separate "app password" that you can revoke later without changing your
main password:

1. Go to <https://bsky.app/settings/app-passwords> (while logged in)
2. Click "Add App Password", give it a name like "election-pulse"
3. Copy the password it gives you (it looks like `xxxx-xxxx-xxxx-xxxx`)

### 3. Add your credentials

Copy the example env file and fill in your details:

```bash
cp .env.example .env
```

Then open `.env` in a text editor and fill in:

```
BLUESKY_HANDLE=yourname.bsky.social
BLUESKY_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
```

`.env` is listed in `.gitignore`, so it will never be committed to git.

### 4. (Optional) Add an Anthropic API key

Only needed if you want `agent.py` to generate its natural-language
summary. Get a key at <https://console.anthropic.com/> and add it to
`.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Without it, `agent.py` still runs the full fetch/chart/growth pipeline --
it just skips the summary step and says so. This is entirely optional and
can be added at any time; nothing else depends on it.

When it is set, the summary step also searches the web (up to 3 searches
per run) for recent news that might explain any notable swing in a
topic's mentions, and mentions it in the summary, e.g. "Immigration
mentions up 40%, likely tied to yesterday's court ruling on asylum
claims." Web search costs $10 per 1,000 searches on top of normal token
costs -- at once a day this comes to well under $2/month. See
<https://claude.com/pricing> for current rates.

## Running it

### The easy way: run everything with agent.py

```bash
python agent.py
```

This is the single entry point. For every topic listed in `topics.json`
it fetches new posts, redraws that topic's chart, and computes its
day-over-day growth -- then asks Claude for a short summary comparing
what changed across all topics, e.g.:

```
Immigration mentions up 40%, healthcare flat, economy down 12%.
```

Finally, it commits and pushes everything new under `data/` (the
database, the chart images, and the summary log) back to git, so the
historical data persists even if this script is run somewhere with no
permanent local storage -- see "Automated commits" below.

### Or run each step yourself

You can still run the individual scripts by hand if you just want one
piece:

```bash
python fetch_posts.py   # fetch new posts for every topic in topics.json
python chart.py          # redraw data/mentions_over_time_<topic>.png for each topic
python growth.py         # print today-vs-yesterday growth for each topic
```

`fetch_posts.py` logs in to Bluesky once and searches for each topic in
`topics.json` in turn, tagging every saved post with which topic
matched. Posts you've already saved are automatically skipped (by their
unique Bluesky URI), so it's safe to run any of these as many times as
you like.

`chart.py` saves one bar chart per topic, e.g.
`data/mentions_over_time_immigration.png`, showing posts per hour. If a
chart looks empty or sparse, run `fetch_posts.py` a few more times
(ideally spread across a few hours) and try again.

`growth.py` prints one line per topic comparing today's mention count to
yesterday's, e.g.:

```
Immigration: 45 mention(s) today vs 20 yesterday (+125%)
```

You'll need to have run `fetch_posts.py` on at least two different
calendar days for any topic to have something to compare -- otherwise
it'll say there isn't enough data yet for that topic.

### Adding or changing topics

Edit `topics.json`:

```json
{
  "topics": ["immigration", "healthcare", "economy"]
}
```

Every script reads from this file, so adding a topic here is the only
change needed to start tracking it.

### Automated commits

`agent.py` runs `git add data/ topics.json`, commits if anything
changed, and pushes to whatever branch is currently checked out. This
is meant to make it safe to run `agent.py` on a schedule (cron,
GitHub Actions, a cloud job, etc.) with no persistent disk: each run's
new posts, charts, and summary get pushed straight to git as the
permanent record. If the push fails (e.g. someone else pushed first),
it pulls with `--rebase` and retries once; if that also fails, it prints
a warning and moves on rather than losing the run's data.

### Scheduling it with GitHub Actions (recommended -- runs even if your machine is off)

`.github/workflows/daily-pipeline.yml` runs `agent.py`'s full pipeline
once a day on GitHub's own servers -- no dependency on your laptop being
on, awake, or even open. This is what the project actually uses.

One-time setup:

1. Add two repository secrets (**Settings -> Secrets and variables ->
   Actions -> "New repository secret"**): `BLUESKY_HANDLE` and
   `BLUESKY_APP_PASSWORD`, with the same values as your local `.env`.
   Optionally add `ANTHROPIC_API_KEY` too, for the AI summary step --
   without it, that step is just skipped.
2. That's it. The workflow is already committed and already registered
   (workflow files only take effect once they exist on the repo's
   default branch, `main` -- see "Automated commits" if you need to
   merge a feature branch into `main` again after editing it).

It runs daily at **23:50 UTC** -- late in the day rather than the
morning, on purpose: `growth.py` compares "today" vs "yesterday" by
calendar date, so a run early in the day only has a few hours of
"today" to compare against a full 24 hours of "yesterday," making every
day look artificially down. Running late captures nearly the whole day
first. Convert 23:50 UTC to your local time and adjust the `cron` line
in the workflow file if you'd like it to run at a different point in
the day (GitHub Actions only understands UTC).

To trigger a run manually instead of waiting for the schedule, go to
the repo's **Actions** tab -> **"Daily Election Pulse run"** ->
**"Run workflow."** Check progress and logs from the same page.

### Scheduling it locally instead (macOS/Linux)

If you'd rather run it from your own machine instead of (or alongside)
GitHub Actions, cron works the same way -- though unlike the GitHub
Actions option above, it only fires if your machine is on and awake at
the scheduled time:

```bash
echo "0 9 * * * cd /path/to/election-pulse && venv/bin/python agent.py >> data/agent_cron.log 2>&1" | crontab -
```

Replace `/path/to/election-pulse` with this project's actual full path
on your machine (run `pwd` from inside the project folder to get it).
Check it saved correctly with `crontab -l`, and remove it with
`crontab -l | grep -v election-pulse | crontab -` if you switch to
GitHub Actions and don't want both running. `data/agent_cron.log`
captures each local run's output for debugging -- it's a local file
only (see `.gitignore`), not something `agent.py` commits.

### Publishing as a website

`agent.py` already regenerates `index.html` -- a simple public dashboard
page with each topic's chart and current growth line -- and commits it
alongside the data on every run. To make that a real, live URL, turn on
GitHub Pages for this repo (one-time setup):

1. On GitHub, go to the repo's **Settings** tab, then **Pages** in the
   left sidebar (under "Code and automation").
2. Under **Build and deployment** -> **Source**, choose **Deploy from a
   branch**.
3. Under **Branch**, select `claude/election-pulse-setup-f5lyfh` (or
   whichever branch `agent.py` is actually pushing to) and folder
   `/ (root)`, then **Save**.
4. GitHub gives you a URL, typically
   `https://<your-username>.github.io/<repo-name>/`. It can take a
   minute or two to go live the first time.

After that, every time `agent.py` runs and pushes (by cron or by hand),
GitHub Pages picks up the new `index.html` and chart images
automatically -- no separate deploy step. If you'd rather the live site
track `main` instead of the feature branch, merge into `main` first
(see "Automated commits" above) and point Pages at `main` in step 3.

## Long-term vision (not built yet)

This is just phase one. The eventual plan for Election Pulse is to:

- Pull posts from Bluesky and other sources automatically, every hour
- Use an LLM to automatically cluster posts into themes/narratives
  (today's topic list in `topics.json` is manually curated)
- Rank topics by *growth rate*, not just raw volume, to surface
  emerging stories
- Generate a richer AI-written explanation of why a topic is trending,
  not just a one-line summary
- Show it all on a dashboard with a "narrative lifecycle" timeline
- Later, tag posts by the kind of community/account that posted them
  (e.g. youth-leaning vs. general accounts) as a proxy for age
  segmentation -- note we deliberately don't try to determine any
  individual user's actual age. (This is why `fetch_posts.py` already
  saves each post's author handle now, even though nothing uses it yet.)

None of that is built yet -- it'll come in later phases, once this basic
pipeline is proven to work end to end.
