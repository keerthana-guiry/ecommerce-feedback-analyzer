import pytest

from nlp.sentiment import analyze_sentiment, extract_keywords


@pytest.mark.parametrize("text, rating, expected", [
    ("This product is very good and works great!", None, "Positive"),
    ("Absolutely terrible, broke after one day.", 1, "Negative"),
    ("It's okay, does the job.", 3, "Neutral"),
    ("Not bad at all, quite happy with it!!", 5, "Positive"),
])
def test_overall_sentiment(text, rating, expected):
    assert analyze_sentiment(text, rating)["sentiment"] == expected


def test_intensifier_increases_score():
    assert analyze_sentiment("very good")["text_score"] > analyze_sentiment("good")["text_score"]


def test_negation_flips_polarity():
    assert analyze_sentiment("not good")["text_score"] < 0


@pytest.mark.parametrize("phrase", ["somewhat bad", "a bit bad", "kind of bad"])
def test_downtoner_reduces_magnitude(phrase):
    assert abs(analyze_sentiment(phrase)["text_score"]) < abs(analyze_sentiment("bad")["text_score"])


@pytest.mark.parametrize("rating", [None, 1, 2, 3, 4, 5])
def test_mixed_review_at_any_rating(rating):
    assert analyze_sentiment("great camera but terrible battery", rating)["sentiment"] == "Mixed"


def test_one_sided_review_is_not_mixed():
    assert analyze_sentiment("great camera and great battery", 5)["sentiment"] == "Positive"


def test_spam_flags_repeated_words_and_shouting():
    result = analyze_sentiment("BEST BEST BEST PRODUCT EVER!!!!!!")
    assert result["likely_spam"] is True


def test_negated_keyword_counts_as_complaint():
    assert extract_keywords("not good") == [("good", "negative")]
