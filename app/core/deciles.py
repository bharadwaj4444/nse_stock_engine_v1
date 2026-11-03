from __future__ import annotations


def decile_for_rank(overall_rank: int | None, overall_percentile: float | None) -> int | None:
    """
    Map a ranking position to a 1-10 backtest decile.

    Percentile is preferred (1.0 is the best score); rank is used as the
    fallback bucket when the percentile is missing. Mirrors the adapter's
    NTILE(10) ordering (best first).
    """

    if overall_percentile is not None:
        return max(1, 10 - int(float(overall_percentile) * 10))

    if overall_rank is not None:
        return max(1, min(10, -(-int(overall_rank) // 10)))

    return None
