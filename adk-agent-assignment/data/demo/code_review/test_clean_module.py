"""Tests that accompany clean_module.py (fixture data for the reviewer, not run by CI)."""

import pytest
from clean_module import clamp, mean


def test_mean():
    assert mean([1.0, 2.0, 3.0]) == 2.0


def test_mean_empty():
    with pytest.raises(ValueError):
        mean([])


def test_clamp():
    assert clamp(5, 0, 3) == 3
    assert clamp(-1, 0, 3) == 0
