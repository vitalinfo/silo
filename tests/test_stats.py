from silo.metrics._stats import percentile


def test_percentile_empty_returns_none():
    assert percentile([], 50) is None


def test_percentile_single_value():
    assert percentile([42.0], 0) == 42.0
    assert percentile([42.0], 50) == 42.0
    assert percentile([42.0], 100) == 42.0


def test_percentile_endpoints():
    assert percentile([1, 2, 3, 4, 5], 0) == 1.0
    assert percentile([1, 2, 3, 4, 5], 100) == 5.0


def test_percentile_midpoint():
    assert percentile([1, 2, 3, 4, 5], 50) == 3.0
    # p50 on even-count list interpolates
    assert percentile([1, 2, 3, 4], 50) == 2.5


def test_percentile_linear_interp():
    # 5 values, p25 -> rank 1.0 -> exact value at index 1
    assert percentile([10, 20, 30, 40, 50], 25) == 20.0
    # p10 -> rank 0.4 -> interpolated between 10 and 20: 10 + 0.4 * 10 = 14
    assert percentile([10, 20, 30, 40, 50], 10) == 14.0
