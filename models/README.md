# models/

Holds the trained sentiment model `sentiment.py` loads at runtime:

- `sentiment_model.joblib` -- the trained logistic regression classifier
- `tfidf_vectorizer.joblib` -- the TF-IDF vectorizer used to turn post
  text into the numeric vectors the model expects

Both are produced by the learning exercise in `sentiment_training/`
(see its own README) -- train there, then copy the two resulting
`.joblib` files here and commit them, replacing these placeholders.
Unlike `sentiment_training/`, files here **are** meant to be committed
-- this is a required runtime dependency for the live pipeline, not
training scratch work.

If these files aren't present, `sentiment.py` skips sentiment analysis
gracefully (same pattern as `agent.py` skipping the AI summary step
when `ANTHROPIC_API_KEY` isn't set) rather than breaking the rest of
the pipeline -- so it's safe for this folder to be empty until you're
ready.
