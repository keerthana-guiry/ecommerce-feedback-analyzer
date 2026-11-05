import pytest

from conftest import add_review, count_rows
from db import config, models
from labelled_reviews import LABELLED_REVIEWS
from nlp.sentiment import (MODEL_NAME, RATING_ONLY_MODEL, analyze_sentiment, detect_language,
                           extract_keywords, sentiment_words)

TAMIL_REVIEW = "இந்த தயாரிப்பு மிகவும் நல்லது"
HINDI_REVIEW = "यह उत्पाद बहुत अच्छा है"
REANALYZE_URL = "/settings/reanalyze"


@pytest.mark.parametrize("text, rating, expected", [
    ("This product is very good and works great!", None, "Positive"),
    ("Absolutely terrible, broke after one day.", 1, "Negative"),
    ("It's okay, does the job.", 3, "Neutral"),
    ("Not bad at all, quite happy with it!!", 5, "Positive"),
])
def test_overall_sentiment(text, rating, expected):
    assert analyze_sentiment(text, rating)["sentiment"] == expected


def test_results_say_which_engine_made_them():
    assert analyze_sentiment("good")["model_name"] == MODEL_NAME


def test_intensifier_increases_score():
    assert analyze_sentiment("very good")["text_score"] > analyze_sentiment("good")["text_score"]


def test_negation_flips_polarity():
    assert analyze_sentiment("not good")["text_score"] < 0


@pytest.mark.parametrize("phrase", ["somewhat bad", "slightly bad"])
def test_downtoner_reduces_magnitude(phrase):
    assert abs(analyze_sentiment(phrase)["text_score"]) < abs(analyze_sentiment("bad")["text_score"])


@pytest.mark.parametrize("text", ["love it 😍", "😍"])
def test_emoji_count_as_sentiment(text):
    assert analyze_sentiment(text)["sentiment"] == "Positive"


@pytest.mark.parametrize("word", ["flimsy", "overpriced", "slow", "defective", "drains"])
def test_product_review_complaint_words_are_understood(word):
    assert analyze_sentiment(f"it is {word}")["text_score"] < 0


# ---------- Mixed ----------

@pytest.mark.parametrize("rating", [None, 1, 2, 3, 4, 5])
def test_mixed_review_at_any_rating(rating):
    assert analyze_sentiment("great camera but terrible battery", rating)["sentiment"] == "Mixed"


def test_mixed_across_sentences():
    assert analyze_sentiment("The sound is amazing. The battery is awful.")["sentiment"] == "Mixed"


def test_one_sided_review_is_not_mixed():
    assert analyze_sentiment("great camera and great battery", 5)["sentiment"] == "Positive"


def test_both_sides_of_but_positive_is_not_mixed():
    assert analyze_sentiment("good camera but even better battery", 5)["sentiment"] == "Positive"


@pytest.mark.parametrize("text, rating", [("great product", 1), ("terrible product", 5)])
def test_words_and_stars_disagreeing_is_mixed(text, rating):
    assert analyze_sentiment(text, rating)["sentiment"] == "Mixed"


def test_mild_words_with_low_stars_are_not_a_conflict():
    assert analyze_sentiment("it is okay", 2)["sentiment"] != "Mixed"


# ---------- The star rating ----------

@pytest.mark.parametrize("rating, expected", [(1, "Negative"), (3, "Neutral"), (5, "Positive")])
def test_rating_decides_when_the_words_carry_no_sentiment(rating, expected):
    assert analyze_sentiment("The battery lasts 2 hours.", rating)["sentiment"] == expected


def test_rating_supports_but_does_not_replace_the_text():
    with_stars = analyze_sentiment("good", 5)
    without_stars = analyze_sentiment("good")
    assert with_stars["score"] > without_stars["score"]
    assert with_stars["text_score"] == without_stars["text_score"]


# ---------- Confidence ----------

@pytest.mark.parametrize("text, rating", [
    ("great camera but terrible battery", 3), ("great product", 1), ("The bottle holds a litre", 3),
])
def test_unclear_results_are_never_highly_confident(text, rating):
    assert analyze_sentiment(text, rating)["confidence"] <= 60


def test_stronger_signals_give_higher_confidence():
    weak = analyze_sentiment("good", 4)["confidence"]
    strong = analyze_sentiment("Absolutely amazing, works perfectly!", 5)["confidence"]
    assert strong > weak


@pytest.mark.parametrize("text, rating", [
    ("", None), ("!!!", 5), ("12345", 1), (TAMIL_REVIEW, 3), ("x" * 5000, 3),
    ("good " * 1000, 5), ("terrible " * 1000, 1), ("but but but", 3),
])
def test_confidence_and_score_stay_in_range(text, rating):
    result = analyze_sentiment(text, rating)
    assert 0 <= result["confidence"] <= 100
    assert -1 <= result["score"] <= 1


# ---------- Languages VADER can't read ----------

@pytest.mark.parametrize("text, code", [
    ("great product", "en"), (TAMIL_REVIEW, "ta"), (HINDI_REVIEW, "hi"), ("очень хорошо", "other"),
    ("😍😍", "en"), ("12345", "en"), ("", "en"), ("நல்லது good", "en"),
])
def test_detect_language(text, code):
    assert detect_language(text) == code


@pytest.mark.parametrize("text", [TAMIL_REVIEW, HINDI_REVIEW])
def test_other_languages_use_only_the_rating_and_say_so(text):
    result = analyze_sentiment(text, 5)
    assert result["sentiment"] == "Positive"
    assert result["model_name"] == RATING_ONLY_MODEL
    assert result["text_analyzed"] is False
    assert result["text_score"] is None
    assert result["contributing_words"] == []
    assert result["aspects"] == {}
    assert result["confidence"] <= 50


def test_other_language_without_a_rating_has_no_confidence():
    result = analyze_sentiment(TAMIL_REVIEW)
    assert result["sentiment"] == "Neutral"
    assert result["confidence"] == 0


def test_language_is_stored_and_page_explains_rating_only_result(admin):
    response = admin.post("/analyze", follow_redirects=True,
                          data={"product_id": 1, "rating": 5, "review_text": TAMIL_REVIEW})
    review = models.search_reviews()[0]
    assert review["language"] == "ta"
    assert review["model_name"] == RATING_ONLY_MODEL
    assert b"star rating alone" in response.data


# ---------- Words behind the result ----------

def test_negated_keyword_counts_as_complaint():
    assert extract_keywords("not good") == [("good", "negative")]


def test_negated_complaint_is_not_a_complaint():
    assert extract_keywords("not bad") == [("bad", "positive")]


@pytest.mark.parametrize("text", ["no way", "pretty much", "it is not here"])
def test_negation_and_booster_words_are_not_counted_as_sentiment(text):
    assert sentiment_words(text) == []


def test_analysis_page_shows_the_engine_and_real_words(admin):
    page = admin.post("/analyze", follow_redirects=True, data={
        "product_id": 1, "rating": 1, "review_text": "terrible battery"}).data.decode()
    assert MODEL_NAME in page
    assert "terrible (-2.1)" in page


# ---------- Spam signals ----------

def test_spam_flags_repeated_words_and_shouting():
    result = analyze_sentiment("BEST BEST BEST PRODUCT EVER!!!!!!")
    assert result["likely_spam"] is True


def test_spam_flags_are_checked_in_other_languages_too():
    assert analyze_sentiment("நல்லது நல்லது நல்லது நல்லது!!!!!!")["likely_spam"] is True


# ---------- Re-analyzing older reviews ----------

def make_old_result(review_id):
    """Make a stored result look like the old engine produced it."""
    with config.get_cursor(commit=True) as cursor:
        cursor.execute("""
            UPDATE sentiment_results SET model_name = 'rule-based-v1', sentiment = 'Neutral',
                   score = 2.5, confidence = 99 WHERE review_id = %s
        """, (review_id,))


def test_reanalyzing_updates_old_results_only(admin):
    old_id = add_review(rating=5, text="excellent product")
    current_id = add_review(rating=1, text="terrible product")
    make_old_result(old_id)
    with config.get_cursor(commit=True) as cursor:
        cursor.execute("UPDATE sentiment_results SET confidence = 12 WHERE review_id = %s", (current_id,))

    response = admin.post(REANALYZE_URL, follow_redirects=True)

    assert b"Analyzed 1 reviews again" in response.data
    review = models.get_review(old_id)
    assert review["model_name"] == MODEL_NAME
    assert review["sentiment"] == "Positive"
    assert -1 <= review["score"] <= 1
    assert models.get_review(current_id)["confidence"] == 12


def test_reanalyzing_keeps_the_original_review(admin):
    review_id = add_review(rating=5, text="excellent product", customer_name="Asha")
    make_old_result(review_id)
    before = models.get_review(review_id)
    admin.post(REANALYZE_URL)
    after = models.get_review(review_id)
    for field in ("review_text", "rating", "customer_name", "review_date", "product_id", "source"):
        assert after[field] == before[field]
    assert count_rows("sentiment_results") == 1


def test_reanalyzing_handles_more_than_one_batch(admin, monkeypatch):
    monkeypatch.setattr("routes.settings.REANALYZE_BATCH_SIZE", 2)
    for _ in range(5):
        make_old_result(add_review())
    assert b"Analyzed 5 reviews again" in admin.post(REANALYZE_URL, follow_redirects=True).data
    assert models.count_reviews_by_model() == [{"model_name": MODEL_NAME, "total": 5}]


def test_reanalyzing_replaces_old_aspects(admin):
    review_id = add_review(rating=1, text="terrible battery")
    make_old_result(review_id)
    with config.get_cursor(commit=True) as cursor:
        cursor.execute("INSERT INTO aspect_results (review_id, aspect, sentiment) VALUES (%s, 'Stale', 'Positive')",
                       (review_id,))
    admin.post(REANALYZE_URL)
    assert [aspect["aspect"] for aspect in models.get_review(review_id)["aspects"]] == ["Battery"]


def test_nothing_to_reanalyze(admin):
    add_review()
    assert b"already up to date" in admin.post(REANALYZE_URL, follow_redirects=True).data


def test_settings_offers_reanalysis_only_when_needed(admin):
    review_id = add_review()
    assert b"Re-analyze" not in admin.get("/settings").data
    make_old_result(review_id)
    page = admin.get("/settings").data.decode()
    assert "Re-analyze 1 Review" in page
    assert "rule-based-v1" in page


def test_old_results_say_so_on_the_analysis_page(admin):
    review_id = add_review()
    make_old_result(review_id)
    assert b"older engine" in admin.get(f"/analyze?review={review_id}").data


def test_analysts_cannot_reanalyze(analyst):
    review_id = add_review()
    make_old_result(review_id)
    assert analyst.post(REANALYZE_URL).status_code == 403
    assert models.get_review(review_id)["model_name"] == "rule-based-v1"
    assert b"Analysis Engine" not in analyst.get("/settings").data


# ---------- Hand-written sanity check ----------

def test_engine_agrees_with_most_of_the_hand_labelled_reviews():
    wrong = [(text, rating, expected, analyze_sentiment(text, rating)["sentiment"])
             for text, rating, expected in LABELLED_REVIEWS
             if analyze_sentiment(text, rating)["sentiment"] != expected]
    print(f"\nAgreed on {len(LABELLED_REVIEWS) - len(wrong)} of {len(LABELLED_REVIEWS)}")
    for case in wrong:
        print(case)
    assert len(wrong) / len(LABELLED_REVIEWS) <= 0.25
