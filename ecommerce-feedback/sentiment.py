"""
Enhanced Sentiment Analysis Engine
----------------------------------
A more serious, rule-based sentiment analyzer that goes beyond simple word
matching. It accounts for:
  - Intensifiers  ("very good" scores higher than "good")
  - Downtoners    ("somewhat bad" scores lower in magnitude than "bad")
  - Negation      ("not good" flips polarity)
  - Punctuation   ("great!!!" boosts confidence)
  - Star rating   (used as a strong supporting signal when available)

The result is a sentiment label (Positive / Negative / Neutral), a
confidence-weighted score, and a breakdown explaining why.
"""

import re

POSITIVE_WORDS = {
    "good": 1, "great": 2, "excellent": 2.5, "amazing": 2.5, "awesome": 2.5,
    "fantastic": 2.5, "wonderful": 2, "love": 2, "loved": 2, "best": 2.5,
    "happy": 1.5, "helpful": 1.5, "easy": 1, "smooth": 1, "nice": 1,
    "perfect": 2.5, "impressive": 2, "friendly": 1.5, "fast": 1,
    "efficient": 1.5, "clean": 1, "recommend": 2, "satisfied": 1.5,
    "pleased": 1.5, "superb": 2.5, "brilliant": 2.5, "outstanding": 2.5,
    "convenient": 1.5, "reliable": 1.5, "enjoyed": 1.5, "durable": 1.5,
    "worth": 1.5, "sturdy": 1.5, "affordable": 1, "comfortable": 1.5,
    "genuine": 1.5, "smoothly": 1, "quick": 1, "beautiful": 2
}

NEGATIVE_WORDS = {
    "bad": -1, "poor": -1.5, "terrible": -2.5, "awful": -2.5, "worst": -3,
    "hate": -2, "hated": -2, "disappointing": -2, "disappointed": -2,
    "slow": -1, "confusing": -1.5, "difficult": -1, "hard": -1,
    "broken": -2, "broke": -2, "useless": -2.5, "annoying": -1.5, "frustrating": -2,
    "rude": -2, "unhelpful": -1.5, "waste": -2, "problem": -1,
    "issue": -1, "buggy": -1.5, "crash": -2, "crashed": -2, "expensive": -1,
    "delayed": -1.5, "unreliable": -2, "horrible": -2.5, "mediocre": -1,
    "defective": -2.5, "damaged": -2, "flimsy": -1.5, "cheap": -1,
    "fake": -2.5, "misleading": -2, "scam": -3, "refund": -1,
    "malfunction": -2.5, "malfunctioning": -2.5, "died": -2, "quit": -1.5,
    "leaking": -2, "torn": -1.5, "stained": -1.5, "missing": -1.5,
    "wrong": -1.5, "incomplete": -1.5, "overpriced": -1.5
}

INTENSIFIERS = {"very": 1.5, "extremely": 2, "really": 1.4, "so": 1.3,
                "absolutely": 1.8, "totally": 1.5, "incredibly": 1.8}

DOWNTONERS = {"somewhat": 0.6, "slightly": 0.5, "a bit": 0.6,
              "kind of": 0.6, "fairly": 0.7}

NEGATION_WORDS = {"not", "no", "never", "isn't", "wasn't", "don't",
                   "didn't", "won't", "wouldn't", "cannot", "can't"}

# Words that signal a contrast/turnaround in opinion. The clause AFTER
# one of these usually carries the reviewer's real, final opinion.
CONTRAST_WORDS = {"but", "however", "although", "though", "yet",
                   "except", "still", "nonetheless"}


def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^\w\s'!]", " ", text)
    return text.split()


def _score_words(words):
    """
    Score a list of words (already cleaned/tokenized) and return
    (score, contributing_words). Shared by clause-splitting logic below.
    """
    score = 0
    contributing = []

    i = 0
    while i < len(words):
        word = words[i]
        multiplier = 1
        negated = False

        if i > 0 and words[i - 1] in INTENSIFIERS:
            multiplier *= INTENSIFIERS[words[i - 1]]
        if i > 0 and words[i - 1] in DOWNTONERS:
            multiplier *= DOWNTONERS[words[i - 1]]
        if i > 1 and words[i - 2] in NEGATION_WORDS:
            negated = True
        if i > 0 and words[i - 1] in NEGATION_WORDS:
            negated = True

        base = None
        if word in POSITIVE_WORDS:
            base = POSITIVE_WORDS[word]
        elif word in NEGATIVE_WORDS:
            base = NEGATIVE_WORDS[word]

        if base is not None:
            value = base * multiplier
            if negated:
                value *= -0.8
            score += value
            contributing.append({"word": word, "value": round(value, 2)})

        i += 1

    return score, contributing


def analyze_sentiment(text, rating=None):
    """
    Analyze feedback text (and optional 1-5 star rating) and return a
    detailed sentiment breakdown. Handles contrast clauses like
    "but", "however" by weighting the clause after them more heavily,
    since that usually reflects the reviewer's real final opinion.
    """
    words = clean_text(text)

    # Find contrast word positions and split into clauses
    split_points = [idx for idx, w in enumerate(words) if w in CONTRAST_WORDS]

    if split_points:
        clauses = []
        start = 0
        for idx in split_points:
            clauses.append(words[start:idx])
            start = idx + 1
        clauses.append(words[start:])

        # Weight later clauses more heavily (0.5x, 1x, 1.5x, 2x...)
        weighted_score = 0
        contributing = []
        num_clauses = len(clauses)
        for c_idx, clause in enumerate(clauses):
            clause_score, clause_words = _score_words(clause)
            weight = 0.5 + (c_idx / max(num_clauses - 1, 1)) * 1.0
            weighted_score += clause_score * weight
            contributing.extend(clause_words)

        raw_pos = sum(c["value"] for c in contributing if c["value"] > 0)
        raw_neg = sum(c["value"] for c in contributing if c["value"] < 0)
        score = weighted_score
    else:
        score, contributing = _score_words(words)
        raw_pos = sum(c["value"] for c in contributing if c["value"] > 0)
        raw_neg = sum(c["value"] for c in contributing if c["value"] < 0)

    # Punctuation emphasis
    exclamations = text.count("!")
    if exclamations > 0 and score != 0:
        score *= (1 + min(exclamations, 3) * 0.1)

    text_sentiment_score = score

    # Blend in star rating if provided
    final_score = text_sentiment_score
    if rating is not None:
        rating_score = (rating - 3) * 1.5
        final_score = (text_sentiment_score * 0.7) + (rating_score * 0.3)

    # Detect "Mixed" sentiment: both strong positive and negative signals
    # present with no clear winner (common in "great but disappointing" style reviews)
    is_mixed = (raw_pos >= 1.5 and raw_neg <= -1.5 and
                abs(raw_pos + raw_neg) < max(raw_pos, abs(raw_neg)) * 0.6)

    if is_mixed and rating is None:
        sentiment = "Mixed"
    elif final_score > 0.5:
        sentiment = "Positive"
    elif final_score < -0.5:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    confidence = min(abs(final_score) / 5, 1.0) * 100
    if sentiment == "Mixed":
        confidence = min(confidence, 60.0)  # mixed reviews are inherently less certain

    return {
        "sentiment": sentiment,
        "score": round(final_score, 2),
        "text_score": round(text_sentiment_score, 2),
        "confidence": round(confidence, 1),
        "contributing_words": contributing
    }


def extract_keywords(text):
    """Return the sentiment-bearing words found in a piece of text.
    Used by the admin dashboard to build 'top complaint/praise word' stats."""
    words = clean_text(text)
    found = []
    for word in words:
        if word in POSITIVE_WORDS:
            found.append((word, "positive"))
        elif word in NEGATIVE_WORDS:
            found.append((word, "negative"))
    return found


if __name__ == "__main__":
    tests = [
        ("This product is very good and works great!", None),
        ("Absolutely terrible, broke after one day.", 1),
        ("It's okay, does the job.", 3),
        ("Not bad at all, quite happy with it!!", 5),
        ("Somewhat disappointing quality.", 2),
    ]
    for t, r in tests:
        result = analyze_sentiment(t, r)
        print(f"'{t}' (rating={r}) -> {result['sentiment']} "
              f"(score={result['score']}, confidence={result['confidence']}%)")
