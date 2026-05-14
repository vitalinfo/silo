"""Tests for the GitHub collector's pure helpers (no network)."""
from silo.collectors.github import _author_query_value


def test_author_query_translates_bot_suffix():
    assert _author_query_value("dependabot[bot]") == "app/dependabot"
    assert _author_query_value("renovate[bot]") == "app/renovate"


def test_author_query_passes_through_user_login():
    assert _author_query_value("alice") == "alice"
    assert _author_query_value("alice-gh") == "alice-gh"


def test_author_query_no_double_bracket():
    # Edge: someone writes the bot login without bracket; we don't try to be too clever.
    assert _author_query_value("dependabot") == "dependabot"
