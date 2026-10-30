"""A small, well-structured module used as the 'should approve' fixture."""

from __future__ import annotations


def mean(values: list[float]) -> float:
    """Return the arithmetic mean of ``values``.

    Raises:
        ValueError: if ``values`` is empty.
    """
    if not values:
        raise ValueError("mean() of empty sequence")
    return sum(values) / len(values)


def clamp(value: float, low: float, high: float) -> float:
    """Clamp ``value`` into the inclusive range [low, high]."""
    if low > high:
        raise ValueError("low must not exceed high")
    return max(low, min(value, high))
