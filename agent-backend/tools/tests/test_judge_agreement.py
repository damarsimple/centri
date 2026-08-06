"""Cohen's kappa, pinned — a reliability figure that is quietly wrong is worse than none.

Kappa reaches the deck as the agreement column of the judge table, where nobody can eyeball it
against the ratings it came from. These tests fix the three ways it can be wrong while still
looking plausible: a scale error, a silent zero for the undefined case, and weights that do not
distinguish a near miss from a total disagreement.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from judge_agreement import kappa  # noqa: E402

# Textbook 2x2: both-yes 20, both-no 15, A-yes/B-no 5, A-no/B-yes 10 -> kappa = 0.40.
TEXTBOOK = [(2, 2)] * 20 + [(1, 1)] * 15 + [(2, 1)] * 5 + [(1, 2)] * 10


def test_matches_the_textbook_2x2():
    assert round(kappa(TEXTBOOK, "unweighted"), 4) == 0.4


def test_kappa_does_not_scale_with_sample_size():
    """REGRESSION: the expected-disagreement term was divided by n once too often, which made
    kappa grow with the number of pairs — 21 worksheets would have reported ~21x the true value,
    turning poor agreement into a headline."""
    once = kappa(TEXTBOOK, "unweighted")
    thrice = kappa(TEXTBOOK * 3, "unweighted")
    assert abs(once - thrice) < 1e-12
    assert once <= 1.0


def test_perfect_and_opposite():
    assert kappa([(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)] * 3, "unweighted") == 1.0
    # Systematically one apart in the same direction: agreement is worse than chance.
    assert kappa([(1, 2), (2, 3), (3, 4), (4, 5)] * 4, "unweighted") < 0


def test_no_variance_is_undefined_not_zero():
    """Both raters always said 5. They never once disagreed, but chance cannot disagree either,
    so kappa is 0/0. Reporting 0.0 would read as 'no agreement' — the exact opposite."""
    assert kappa([(5, 5)] * 21, "quadratic") is None
    assert kappa([(3, 3)] * 21, "unweighted") is None


def test_empty_input_is_undefined():
    assert kappa([], "quadratic") is None


def test_quadratic_weighting_forgives_a_near_miss():
    """On an ordinal 1-5 scale, 4-vs-5 is a near miss and 1-vs-5 is not. Unweighted kappa counts
    them the same; quadratic must not."""
    near = [(4, 5)] * 10 + [(2, 1)] * 10 + [(3, 3)] * 10
    assert kappa(near, "quadratic") > kappa(near, "unweighted")
    assert kappa(near, "quadratic") > kappa(near, "linear") > kappa(near, "unweighted")


def test_out_of_range_pairs_are_dropped_not_counted():
    """A rater that failed to return an integer 1-5 must not be scored as if it had."""
    assert kappa(TEXTBOOK + [(None, 3), (9, 1)], "unweighted") == kappa(TEXTBOOK, "unweighted")
