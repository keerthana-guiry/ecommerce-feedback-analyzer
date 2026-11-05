"""
Sentiment analysis using VADER, a published dictionary-and-rules method that
handles negation ("not good"), intensifiers ("very good"), "but" and emoji.

On top of VADER, this file adds:
  - Common product-review words missing from VADER's dictionary
  - Mixed sentiment, found by scoring each part of a review separately
  - The star rating as a supporting signal
  - Language detection, since VADER's dictionary only covers English

"Confidence" here means how strong and consistent the signals are. VADER doesn't
produce a probability, so it isn't a measured chance of being correct.
"""

import re

from vaderSentiment.vaderSentiment import (BOOSTER_DICT, N_SCALAR, NEGATE,
                                           SentimentIntensityAnalyzer, negated)

# Stored with each result, so it's clear what produced it
MODEL_NAME = "vader-3.3.2"
RATING_ONLY_MODEL = "rating-only"
CURRENT_MODELS = (MODEL_NAME, RATING_ONLY_MODEL)

TEXT_WEIGHT = 0.7
RATING_WEIGHT = 0.3

# Scores run from -1 to 1. VADER's authors suggest 0.05 for short social media
# posts, but that makes mild wording like "it's okay" count as Positive.
SENTIMENT_THRESHOLD = 0.25

# Mixed needs a clear opinion in both directions
MIXED_CLAUSE_STRENGTH = 0.3
STRONG_TEXT_STRENGTH = 0.4
# Mixed and Neutral reviews have no clear overall signal
MAX_UNCLEAR_CONFIDENCE = 60.0
MAX_RATING_ONLY_CONFIDENCE = 50.0

# Words from product reviews that aren't in VADER's dictionary, on its scale of -4 to 4
PRODUCT_REVIEW_WORDS = {
    "smooth": 1, "smoothly": 1, "fast": 1, "quick": 1, "convenient": 1.5, "reliable": 1.5,
    "durable": 1.5, "sturdy": 1.5, "affordable": 1, "genuine": 1.5, "lightweight": 1,
    "spacious": 1, "crisp": 1, "responsive": 1,
    "slow": -1, "unhelpful": -1.5, "issue": -1, "buggy": -1.5, "crashed": -2, "expensive": -1,
    "unreliable": -2, "mediocre": -1, "flimsy": -1.5, "cheap": -1, "refund": -1,
    "malfunction": -2.5, "malfunctioning": -2.5, "quit": -1.5, "leaking": -2, "leaks": -2,
    "stained": -1.5, "incomplete": -1.5, "overpriced": -1.5, "drains": -1.5, "overheats": -2,
    "overheating": -2, "rusted": -2, "scratched": -1.5, "cracked": -2, "cracks": -1.5,
    "peeling": -1.5, "wobbly": -1.5, "laggy": -1.5, "glitchy": -1.5, "counterfeit": -2.5,
    "disconnects": -1.5, "bulky": -1,
}

# Words VADER scores that are too often filler to list as a review's reasons or
# complaints, like "no" in "no issues", "pretty" in "pretty bad", or "feels like"
NOT_REASON_WORDS = {"no", "pretty", "kind", "like"}

_analyzer = SentimentIntensityAnalyzer()
_analyzer.lexicon.update(PRODUCT_REVIEW_WORDS)

# Letter ranges for the languages planned next. Other languages written in Latin
# letters can't be told apart from English this way, and just score as Neutral.
SCRIPT_RANGES = {"ta": ("஀", "௿"), "hi": ("ऀ", "ॿ")}

CLAUSE_BOUNDARY = re.compile(r"[.!?;]+|\b(?:but|however|although|though|yet|except)\b", re.IGNORECASE)

# ---------- Emotion detection ----------
# Maps specific words to a more granular emotion than plain +/- sentiment.
EMOTION_WORDS = {
    "😍 Loved": {"love", "loved", "amazing", "perfect", "outstanding", "best"},
    "😊 Happy": {"good", "great", "happy", "pleased", "satisfied", "nice",
                 "helpful", "recommend", "enjoyed"},
    "😡 Angry": {"terrible", "awful", "worst", "hate", "hated", "scam",
                 "useless", "rude", "horrible"},
    "😢 Sad": {"disappointing", "disappointed", "poor", "mediocre",
               "waste", "cheap", "flimsy", "bad"},
    "😠 Frustrated": {"annoying", "frustrating", "confusing", "buggy",
                      "broken", "broke", "crash", "crashed", "unreliable",
                      "defective", "malfunction", "malfunctioning"},
    "😕 Confused": {"confusing", "wrong", "missing", "incomplete", "misleading"},
}

# ---------- Aspect-based sentiment ----------
# Maps common product review "aspects" to the keywords that usually
# indicate a review is talking about that aspect.
ASPECT_KEYWORDS = {
    "Battery": {"battery", "charge", "charging", "power", "backup"},
    "Camera": {"camera", "photo", "picture", "lens", "video"},
    "Build Quality": {"build", "material", "sturdy", "flimsy", "quality",
                       "durable", "plastic", "solid"},
    "Display": {"screen", "display", "resolution", "brightness"},
    "Performance": {"speed", "fast", "slow", "lag", "performance",
                     "smooth", "efficient", "responsive"},
    "Price": {"price", "expensive", "cheap", "affordable", "worth",
              "overpriced", "value"},
    "Comfort": {"comfortable", "comfort", "fit", "ergonomic", "weight"},
    "Delivery": {"delivery", "shipping", "delayed", "packaging",
                 "arrived", "shipped"},
}


def detect_language(text):
    """Return a language code from the letters used. Text with no letters,
    such as only emoji, counts as English because VADER can still score it."""
    letters = [char for char in text if char.isalpha()]
    latin = sum(1 for char in letters if char < "ɐ")
    if not letters or latin / len(letters) >= 0.5:
        return "en"

    counts = {code: sum(1 for char in letters if low <= char <= high)
              for code, (low, high) in SCRIPT_RANGES.items()}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else "other"


def detect_emotion(contributing_words):
    """
    Return the emotion whose keyword set best matches the review, based on
    the NEGATION-AWARE contributing words (each already has a signed value
    from sentiment_words, so "not good" correctly counts as negative here,
    not as the word "good").
    """
    positive_emotions = {"😍 Loved", "😊 Happy"}
    negative_emotions = {"😡 Angry", "😢 Sad", "😠 Frustrated", "😕 Confused"}

    scores = {emotion: 0 for emotion in EMOTION_WORDS}

    for item in contributing_words:
        word = item["word"]
        value = item["value"]
        for emotion, keywords in EMOTION_WORDS.items():
            if word not in keywords:
                continue
            # Only count this word toward an emotion if the word's actual
            # (post-negation) polarity matches that emotion's polarity
            if emotion in positive_emotions and value > 0:
                scores[emotion] += abs(value)
            elif emotion in negative_emotions and value < 0:
                scores[emotion] += abs(value)

    best_emotion = max(scores, key=scores.get)
    return best_emotion if scores[best_emotion] > 0 else None


def detect_aspects(text):
    """Return a dict of {aspect: sentiment_label} for every aspect mentioned
    in the review, scoring a small window of words around each mention."""
    words = clean_text(text)
    results = {}

    for aspect, keywords in ASPECT_KEYWORDS.items():
        mentioned = False
        aspect_score = 0
        for i, word in enumerate(words):
            if word in keywords:
                mentioned = True
                window = words[max(0, i - 3):i + 4]
                aspect_score += _compound(" ".join(window))

        if mentioned:
            if aspect_score > SENTIMENT_THRESHOLD:
                results[aspect] = "Positive"
            elif aspect_score < -SENTIMENT_THRESHOLD:
                results[aspect] = "Negative"
            else:
                results[aspect] = "Neutral"

    return results


def detect_spam(text):
    """
    Rule-based spam/fake-review detector. Returns a spam score (0-100)
    and the specific red flags found. This is NOT meant to be perfectly
    accurate - it's a heuristic first-pass filter for admins to review.
    """
    flags = []
    score = 0

    stripped = text.strip()

    if len(stripped) < 5:
        flags.append("Extremely short review")
        score += 30

    # Repeated characters (e.g. "sooooo good", "!!!!!!")
    if re.search(r"(.)\1{4,}", stripped):
        flags.append("Excessive repeated characters")
        score += 25

    # Excessive punctuation
    if stripped.count("!") > 5 or stripped.count("?") > 5:
        flags.append("Excessive punctuation")
        score += 15

    # ALL CAPS shouting (only counts if there's enough alphabetic content)
    letters = [c for c in stripped if c.isalpha()]
    if len(letters) > 8 and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7:
        flags.append("Written mostly in capital letters")
        score += 20

    # Repeated words (e.g. "good good good good")
    words = stripped.lower().split()
    if len(words) >= 4:
        for i in range(len(words) - 2):
            if words[i] == words[i + 1] == words[i + 2]:
                flags.append("Same word repeated 3+ times in a row")
                score += 25
                break

    # Excessive emoji-like unicode characters (rough heuristic)
    emoji_count = len(re.findall(r"[\U0001F300-\U0001FAFF]", text))
    if emoji_count > 5:
        flags.append("Excessive emoji use")
        score += 15

    # Generic low-content reviews
    generic_phrases = {"good", "nice", "ok", "okay", "fine", "great product"}
    if stripped.lower() in generic_phrases:
        flags.append("Generic, low-detail review")
        score += 20

    score = min(score, 100)
    return {"spam_score": score, "flags": flags, "likely_spam": score >= 50}


def clean_text(text):
    text = text.lower()
    text = re.sub(r"[^\w\s'!]", " ", text)
    return text.split()


def _compound(text):
    return _analyzer.polarity_scores(text)["compound"]


def sentiment_words(text):
    """The words in a review that carry sentiment, each with its dictionary
    value. The value is flipped for a negated word, like "good" in "not good"."""
    words = clean_text(text)
    found = []
    for i, word in enumerate(words):
        if (word in NEGATE or word in BOOSTER_DICT or word in NOT_REASON_WORDS
                or word not in _analyzer.lexicon):
            continue
        value = _analyzer.lexicon[word]
        if negated(words[max(0, i - 3):i]):
            value *= N_SCALAR
        found.append({"word": word, "value": round(value, 2)})
    return found


def _clause_scores(text):
    """Score each part of a review separately, split at sentence ends and contrast words."""
    clauses = [clause.strip() for clause in CLAUSE_BOUNDARY.split(text)]
    return [_compound(clause) for clause in clauses if clause]


def _label(score):
    if score > SENTIMENT_THRESHOLD:
        return "Positive"
    if score < -SENTIMENT_THRESHOLD:
        return "Negative"
    return "Neutral"


def _rating_signal(rating):
    """Convert a 1-5 star rating to the same -1 to 1 scale as VADER."""
    return (rating - 3) / 2


def _rating_only_result(rating, language, spam_check):
    """For text VADER can't read. Showing a text score here would be made up,
    so the result comes from the star rating alone, and says so."""
    score = _rating_signal(rating) if rating is not None else 0.0
    return {
        "sentiment": _label(score),
        "score": round(score, 2),
        "text_score": None,
        "confidence": round(min(abs(score) * 100, MAX_RATING_ONLY_CONFIDENCE), 1),
        "contributing_words": [],
        "emotion": None,
        "aspects": {},
        "spam_score": spam_check["spam_score"],
        "spam_flags": spam_check["flags"],
        "likely_spam": spam_check["likely_spam"],
        "language": language,
        "text_analyzed": False,
        "model_name": RATING_ONLY_MODEL
    }


def analyze_sentiment(text, rating=None):
    """
    Analyze review text and an optional 1-5 star rating, returning the sentiment
    label, scores, the words behind them, emotion, aspects and spam signals.
    """
    spam_check = detect_spam(text)
    language = detect_language(text)
    if language != "en":
        return _rating_only_result(rating, language, spam_check)

    text_score = _compound(text)
    final_score = text_score
    rating_signal = None
    if rating is not None:
        rating_signal = _rating_signal(rating)
        final_score = text_score * TEXT_WEIGHT + rating_signal * RATING_WEIGHT

    clauses = _clause_scores(text)
    strongest_positive = max(clauses, default=0)
    strongest_negative = min(clauses, default=0)

    # Opposite opinions inside the review, like "great camera but terrible battery"
    mixed_opinions = (strongest_positive >= MIXED_CLAUSE_STRENGTH and
                      strongest_negative <= -MIXED_CLAUSE_STRENGTH)
    # The words and the stars disagree, like "great product" with 1 star
    rating_conflict = (rating_signal is not None and abs(text_score) >= STRONG_TEXT_STRENGTH and
                       text_score * rating_signal < 0)

    if mixed_opinions or rating_conflict:
        sentiment = "Mixed"
        confidence = min(abs(final_score) * 100, MAX_UNCLEAR_CONFIDENCE)
        if mixed_opinions:
            confidence = min(strongest_positive, -strongest_negative) * MAX_UNCLEAR_CONFIDENCE
    else:
        sentiment = _label(final_score)
        confidence = abs(final_score) * 100
        if sentiment == "Neutral":
            confidence = (1 - abs(final_score) / SENTIMENT_THRESHOLD) * MAX_UNCLEAR_CONFIDENCE

    contributing = sentiment_words(text)

    return {
        "sentiment": sentiment,
        "score": round(final_score, 2),
        "text_score": round(text_score, 2),
        "confidence": round(confidence, 1),
        "contributing_words": contributing,
        "emotion": detect_emotion(contributing),
        "aspects": detect_aspects(text),
        "spam_score": spam_check["spam_score"],
        "spam_flags": spam_check["flags"],
        "likely_spam": spam_check["likely_spam"],
        "language": language,
        "text_analyzed": True,
        "model_name": MODEL_NAME
    }


def extract_keywords(text):
    """Return the sentiment-bearing words found in a piece of text, with
    polarity determined by their NEGATION-AWARE signed value (so "not good"
    correctly counts as a negative/complaint keyword, not praise)."""
    return [(item["word"], "positive" if item["value"] > 0 else "negative")
            for item in sentiment_words(text)]
