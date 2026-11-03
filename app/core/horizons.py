from __future__ import annotations

HORIZON_BUCKETS = (5, 20, 60)


def horizon_bucket(horizon_days: int) -> int:
    """
    Map a requested horizon (in trading days) to the smallest supported
    forward-return bucket greater than or equal to it, or to the largest
    bucket when the request exceeds every bucket.

    Forward returns only exist at 5, 20 and 60 trading days.
    """

    for bucket in HORIZON_BUCKETS:
        if horizon_days <= bucket:
            return bucket

    return HORIZON_BUCKETS[-1]
