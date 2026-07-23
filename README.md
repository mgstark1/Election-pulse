# Election Pulse

A UK General Election narrative tracker.

**Current phase:** a simple, single-topic pipeline that tracks mentions of
"immigration" on Bluesky. This is step one of a bigger project (see
"Long-term vision" below) -- for now it just proves that we can fetch
posts, save them, and see them on a chart.

## What's in this repo

- `db.py` -- sets up the SQLite database (a single file, no server needed)
- `fetch_posts.py` -- logs in to Bluesky and saves recent posts mentioning
  "immigration" into the database
- `chart.py` -- reads the database and draws a simple chart of how many
  posts were made per hour, so you can see the data is real
- `growth.py` -- compares today's mention count to yesterday's and prints
  the percentage change, e.g. "Immigration: 45 mentions today vs 20
  yesterday (+125%)"
- `data/` -- where the database file (`election_pulse.db`) and the chart
  image get saved. This folder is excluded from git (see `.gitignore`)
  because it's data, not code.

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

## Running it

### Fetch posts

```bash
python fetch_posts.py
```

This logs in to Bluesky, searches for recent posts mentioning
"immigration", and saves any new ones into `data/election_pulse.db`.
Posts you've already saved are automatically skipped, so it's safe to
run this command as many times as you like -- e.g. run it by hand every
hour or so over a day to build up a useful spread of data. (Automated
scheduling isn't set up yet -- that's a later step.)

### View the chart

```bash
python chart.py
```

This reads everything in the database and saves a bar chart to
`data/mentions_over_time.png` showing how many posts were made each
hour. Open that image file to take a look. If it looks empty or sparse,
run `fetch_posts.py` a few more times (ideally spread across a few
hours) and try again.

### Check day-over-day growth

```bash
python growth.py
```

This compares how many "immigration" posts were saved *today* vs
*yesterday* and prints the percentage change, e.g.:

```
Immigration: 45 mention(s) today vs 20 yesterday (+125%)
```

You'll need to have run `fetch_posts.py` on at least two different
calendar days for this to have anything to compare -- otherwise it'll
tell you there isn't enough data yet.

## Long-term vision (not built yet)

This is just phase one. The eventual plan for Election Pulse is to:

- Track multiple topics (immigration, housing, NHS, etc.), not just one
- Pull posts from Bluesky and other sources automatically, every hour
- Use an LLM to automatically cluster posts into themes/narratives
- Rank topics by *growth rate*, not just raw volume, to surface
  emerging stories
- Generate an AI-written explanation of why a topic is trending
- Show it all on a dashboard with a "narrative lifecycle" timeline
- Later, tag posts by the kind of community/account that posted them
  (e.g. youth-leaning vs. general accounts) as a proxy for age
  segmentation -- note we deliberately don't try to determine any
  individual user's actual age. (This is why `fetch_posts.py` already
  saves each post's author handle now, even though nothing uses it yet.)

None of that is built yet -- it'll come in later phases, once this basic
pipeline is proven to work end to end.
