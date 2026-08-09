# Sentiment training (learning project)

This folder is a **self-contained learning exercise** for building and
training a TF-IDF + logistic regression sentiment classifier from
scratch, kept separate from the rest of Election Pulse on purpose.

**Nothing here is part of the automated pipeline.** `agent.py` and the
GitHub Actions workflow never import or run anything in this folder --
you can experiment, break things, and rerun freely without any risk to
the live site or the daily data collection.

## Setup

Use a separate virtual environment from the main project (its
dependencies -- `scikit-learn`, `nltk`, `joblib` -- aren't needed by
Election Pulse itself and would just slow down every GitHub Actions
run if added to the main `requirements.txt`):

```bash
cd sentiment_training
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-training.txt
```

## What's the goal

Train a sentiment classifier on a labeled dataset (starting with
NLTK's `twitter_samples` corpus), understand each step of the pipeline
(vectorizing text, training, evaluating), and end up with a saved
model file. Once that model is trained and its accuracy looks
reasonable, it can be copied into the main project and loaded by a
`sentiment.py` there to classify real Bluesky posts -- but that's a
later step, done deliberately by hand, not automatically.

## Data

`twitter_samples` is downloaded via `nltk.download()` into NLTK's own
cache directory (`~/nltk_data`), not into this folder -- so there's
nothing large to accidentally commit. If you ever export any data to
a file here for convenience, don't commit it (see `.gitignore`).
