"""
A small sanity check, written by hand: (review text, star rating or None, the
label a person would give). It catches obvious mistakes when the engine changes.
It's far too small to measure real accuracy, so its result must not be reported
as model performance. Some cases are hard on purpose, like sarcasm.
"""

LABELLED_REVIEWS = [
    # Clearly positive
    ("Absolutely love this watch, it works perfectly.", 5, "Positive"),
    ("Great value for the price, very happy with it.", 5, "Positive"),
    ("Excellent build and really comfortable to wear.", 5, "Positive"),
    ("Arrived quickly and the quality is impressive.", 4, "Positive"),
    ("Very good sound, easy to set up.", 4, "Positive"),
    ("Sturdy, reliable and worth every penny.", 5, "Positive"),
    ("Best purchase I have made this year!", 5, "Positive"),
    ("My kids love it and it was so easy to use.", 5, "Positive"),
    ("Not bad at all, quite happy with it.", 4, "Positive"),
    ("Would definitely recommend this to a friend.", 4, "Positive"),
    ("Good product.", None, "Positive"),
    ("Wonderful, exactly what I wanted 😍", None, "Positive"),

    # Clearly negative
    ("Terrible quality, broke after one day.", 1, "Negative"),
    ("Complete waste of money, do not buy.", 1, "Negative"),
    ("The strap is flimsy and feels cheap.", 2, "Negative"),
    ("Very disappointed, the battery drains in an hour.", 1, "Negative"),
    ("Arrived damaged and support was unhelpful.", 1, "Negative"),
    ("Overpriced and slow, I want a refund.", 1, "Negative"),
    ("Not good, I would not recommend it.", 2, "Negative"),
    ("It stopped working after a week.", 1, "Negative"),
    ("Keeps overheating and the screen is cracked.", 1, "Negative"),
    ("Awful experience, the worst product I have bought.", 1, "Negative"),
    ("Bad quality.", None, "Negative"),
    ("Horrible, it leaks everywhere 😡", None, "Negative"),

    # Neutral
    ("It is okay, does the job.", 3, "Neutral"),
    ("Average product, nothing special to report.", 3, "Neutral"),
    ("The bottle holds one litre.", 3, "Neutral"),
    ("It arrived on Tuesday in a brown box.", 3, "Neutral"),
    ("Works as described.", 3, "Neutral"),
    ("I bought this for my office.", None, "Neutral"),
    ("The battery lasts about two days.", None, "Neutral"),
    ("It comes in black and blue.", None, "Neutral"),

    # Mixed
    ("Great camera but terrible battery.", 3, "Mixed"),
    ("Excellent battery but the strap is flimsy and disappointing.", 3, "Mixed"),
    ("Great comfort but terrible packaging.", 3, "Mixed"),
    ("The sound is amazing. The battery is awful.", 3, "Mixed"),
    ("Love the design, however the zip broke and I am disappointed.", 3, "Mixed"),
    ("Nice screen, but the speakers are horrible.", 2, "Mixed"),
    ("Great product.", 1, "Mixed"),
    ("Terrible product.", 5, "Mixed"),

    # Star rating supports text with little sentiment in it
    ("The battery lasts 2 hours.", 1, "Negative"),
    ("It does what I needed it to.", 5, "Positive"),

    # Hard cases that dictionary methods often get wrong
    ("Oh great, another one that broke after a week.", 1, "Negative"),
    ("I wanted to love this but it never worked.", 1, "Negative"),
    ("Could not be happier with this purchase.", 5, "Positive"),
    ("This thing is sick, the performance is insane!", 5, "Positive"),
    ("Not the worst, but I expected more for the money.", 2, "Negative"),
    ("It is fine I guess.", 3, "Neutral"),
]
