"""Unit tests for src/proxy/manager.py."""

from pathlib import Path

import pytest

from src.proxy.manager import (
    ProxyEntry,
    ProxyError,
    ProxyManager,
    parse_proxy_file,
    parse_proxy_line,
)


# --- parse_proxy_line ---------------------------------------------------

def test_parse_host_port_defaults_to_http_scheme():
    entry = parse_proxy_line("203.0.113.10:8080", 1)
    assert entry.scheme == "http"
    assert entry.host == "203.0.113.10"
    assert entry.port == 8080
    assert entry.username is None


def test_parse_scheme_host_port():
    entry = parse_proxy_line("socks5://203.0.113.10:1080", 1)
    assert entry.scheme == "socks5"
    assert entry.port == 1080


def test_parse_with_credentials():
    entry = parse_proxy_line("http://testuser:testpass@203.0.113.11:8080", 1)
    assert entry.username == "testuser"
    assert entry.password == "testpass"
    assert entry.server == "http://203.0.113.11:8080"


def test_blank_line_returns_none():
    assert parse_proxy_line("   ", 1) is None


def test_comment_line_returns_none():
    assert parse_proxy_line("# this is a comment", 1) is None


def test_malformed_line_raises_proxy_error():
    with pytest.raises(ProxyError, match="does not match supported proxy syntax"):
        parse_proxy_line("not-a-valid-proxy-line", 1)


def test_out_of_range_port_raises_proxy_error():
    with pytest.raises(ProxyError, match="out of valid range"):
        parse_proxy_line("203.0.113.10:99999", 1)


def test_masked_hides_password():
    entry = parse_proxy_line("http://testuser:testpass@203.0.113.11:8080", 1)
    assert "testpass" not in entry.masked
    assert "****" in entry.masked
    assert "testuser" in entry.masked


def test_masked_without_credentials_equals_server():
    entry = parse_proxy_line("203.0.113.10:8080", 1)
    assert entry.masked == entry.server


# --- parse_proxy_file ----------------------------------------------------

def test_parse_proxy_file_skips_comments_and_blanks(tmp_path: Path):
    content = (
        "# example proxy list\n"
        "\n"
        "203.0.113.10:8080\n"
        "http://testuser:testpass@203.0.113.11:8080\n"
        "\n"
    )
    proxy_file = tmp_path / "proxies.txt"
    proxy_file.write_text(content, encoding="utf-8")

    entries = parse_proxy_file(proxy_file)
    assert len(entries) == 2
    assert entries[0].host == "203.0.113.10"
    assert entries[1].username == "testuser"


def test_parse_proxy_file_missing_raises_proxy_error(tmp_path: Path):
    with pytest.raises(ProxyError, match="not found"):
        parse_proxy_file(tmp_path / "does_not_exist.txt")


def test_parse_proxy_file_empty_raises_proxy_error(tmp_path: Path):
    proxy_file = tmp_path / "empty.txt"
    proxy_file.write_text("# only comments\n\n", encoding="utf-8")
    with pytest.raises(ProxyError, match="no usable proxy entries"):
        parse_proxy_file(proxy_file)


def test_parse_proxy_file_malformed_line_raises_with_line_number(tmp_path: Path):
    proxy_file = tmp_path / "bad.txt"
    proxy_file.write_text("203.0.113.10:8080\nbad-line\n", encoding="utf-8")
    with pytest.raises(ProxyError, match="Line 2"):
        parse_proxy_file(proxy_file)


# --- ProxyManager ----------------------------------------------------------

def make_entries(n: int) -> list[ProxyEntry]:
    return [
        ProxyEntry(scheme="http", host=f"10.0.0.{i}", port=8080) for i in range(1, n + 1)
    ]


def test_empty_proxy_list_raises_proxy_error():
    with pytest.raises(ProxyError, match="at least one proxy"):
        ProxyManager(proxies=[])


def test_assign_round_robins_through_all_proxies():
    entries = make_entries(3)
    manager = ProxyManager(proxies=entries, max_retry_attempts=1)
    assigned = [manager.assign() for _ in range(6)]
    assert assigned == entries + entries  # wraps around in order


def test_mark_failure_eventually_excludes_proxy():
    entries = make_entries(2)
    manager = ProxyManager(proxies=entries, max_retry_attempts=1)
    bad_proxy = entries[0]

    manager.mark_failure(bad_proxy)
    manager.mark_failure(bad_proxy)  # exceeds max_retry_attempts=1

    assert manager.available_count == 1
    # Every subsequent assignment should be the surviving proxy only.
    for _ in range(3):
        assert manager.assign() == entries[1]


def test_mark_success_resets_failure_count():
    entries = make_entries(2)
    manager = ProxyManager(proxies=entries, max_retry_attempts=1)
    proxy = entries[0]

    manager.mark_failure(proxy)
    manager.mark_success(proxy)
    manager.mark_failure(proxy)  # only 1 failure again, should still be available

    assert manager.available_count == 2


def test_all_proxies_exhausted_raises_proxy_error():
    entries = make_entries(1)
    manager = ProxyManager(proxies=entries, max_retry_attempts=0)
    manager.mark_failure(entries[0])
    with pytest.raises(ProxyError, match="No available proxies"):
        manager.assign()