import pytest

from silo.metrics.contribution import gini


def test_gini_empty_is_none():
    assert gini([]) is None


def test_gini_all_zero_is_none():
    assert gini([0, 0, 0]) is None


def test_gini_perfectly_even_is_zero():
    assert gini([1, 1, 1, 1]) == 0.0


def test_gini_fully_concentrated_approaches_one():
    # One person has all the contribution; others have zero.
    # For n=4, max gini = (n-1)/n = 0.75.
    g = gini([0, 0, 0, 10])
    assert g == pytest.approx(0.75, abs=1e-9)


def test_gini_negative_raises():
    with pytest.raises(ValueError):
        gini([1, -1])


def test_gini_known_example():
    # [1, 2, 3, 4] -> sorted: 1,2,3,4. total=10. weighted = 1*1 + 2*2 + 3*3 + 4*4 = 30.
    # G = (2*30) / (4*10) - 5/4 = 1.5 - 1.25 = 0.25
    assert gini([1, 2, 3, 4]) == pytest.approx(0.25, abs=1e-9)
