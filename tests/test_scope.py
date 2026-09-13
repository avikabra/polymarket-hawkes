import tempfile
from pathlib import Path

import pytest

from src.utils import assert_covers, read_scope, write_scope

_WINDOW = ("2024-01-01T00:00:00", "2024-12-31T00:00:00")


def test_read_scope_missing_returns_none():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert read_scope(Path(tmpdir)) is None


def test_write_scope_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        write_scope(d, ["b", "a", "a"], _WINDOW)
        scope = read_scope(d)
    assert scope["company_ids"] == ["a", "b"]
    assert scope["count"] == 2
    assert scope["window_start"] == _WINDOW[0]
    assert scope["window_end"] == _WINDOW[1]


def test_assert_covers_exact_match_passes():
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        write_scope(d, ["a", "b"], _WINDOW)
        assert_covers(d, ["a", "b"], _WINDOW)  # must not raise


def test_assert_covers_corpus_superset_passes():
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        write_scope(d, ["a", "b", "c"], ("2023-01-01T00:00:00", "2025-01-01T00:00:00"))
        assert_covers(d, ["a", "b"], _WINDOW)  # extra company + wider window: fine


def test_assert_covers_unions_multiple_corpus_dirs():
    with tempfile.TemporaryDirectory() as t1, tempfile.TemporaryDirectory() as t2:
        d1, d2 = Path(t1), Path(t2)
        write_scope(d1, ["a"], _WINDOW)
        write_scope(d2, ["b"], _WINDOW)
        assert_covers([d1, d2], ["a", "b"], _WINDOW)  # neither alone covers, union does


def test_assert_covers_missing_company_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        write_scope(d, ["a"], _WINDOW)
        with pytest.raises(RuntimeError, match="b"):
            assert_covers(d, ["a", "b"], _WINDOW)


def test_assert_covers_short_date_window_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        write_scope(d, ["a"], ("2024-06-01T00:00:00", "2024-12-31T00:00:00"))
        with pytest.raises(RuntimeError, match="window"):
            assert_covers(d, ["a"], _WINDOW)  # universe starts before corpus


def test_assert_covers_missing_scope_json_fails():
    with tempfile.TemporaryDirectory() as tmpdir:
        d = Path(tmpdir)
        with pytest.raises(RuntimeError, match="_SCOPE.json"):
            assert_covers(d, ["a"], _WINDOW)
