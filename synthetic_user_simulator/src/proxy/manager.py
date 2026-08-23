"""Proxy list parsing and assignment.

Used only for DNL sessions -- AppConfig.validate() already rejects
use_proxies=True combined with platform='youtube' (see README.md
Section 4), so this module doesn't need to enforce that itself, but it
also makes no assumptions about *why* it's being used; it's a generic
"parse a proxy list, hand out entries, track failures" utility.

Proxy format is documented in README.md Section 14 and is a clearly
labeled placeholder syntax pending your real test-proxy format -- see
_PROXY_LINE_PATTERN below, which is the one place that needs to change
if the real format differs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Union


class ProxyError(Exception):
    """Raised for proxy file parsing problems or assignment failures."""


# Supported line syntax (see README.md Section 14):
#   host:port
#   scheme://host:port
#   scheme://username:password@host:port
# scheme defaults to "http" if omitted. This pattern is intentionally the
# single place proxy syntax is defined -- change it here if your real
# format differs, rather than adding parsing logic elsewhere.
_PROXY_LINE_PATTERN = re.compile(
    r"^(?:(?P<scheme>https?|socks4|socks5)://)?"
    r"(?:(?P<username>[^:@/\s]+):(?P<password>[^:@/\s]+)@)?"
    r"(?P<host>[^:@/\s]+):(?P<port>\d{1,5})$"
)

_DEFAULT_SCHEME = "http"


@dataclass(frozen=True)
class ProxyEntry:
    """One parsed, validated proxy from the proxy list file."""

    scheme: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None

    @property
    def server(self) -> str:
        """Full server URL as Playwright's context `proxy.server` expects."""
        return f"{self.scheme}://{self.host}:{self.port}"

    @property
    def masked(self) -> str:
        """Loggable identifier with credentials masked, per README.md Section 17."""
        if self.username:
            return f"{self.scheme}://{self.username}:****@{self.host}:{self.port}"
        return self.server


def parse_proxy_line(line: str, line_number: int) -> Optional[ProxyEntry]:
    """Parse a single line from a proxy list file.

    Args:
        line: Raw line text (not yet stripped).
        line_number: 1-indexed line number, used only for error messages.

    Returns:
        A ProxyEntry, or None if the line is blank or a comment (starts
        with '#') and should be skipped.

    Raises:
        ProxyError: if the line is non-blank, non-comment, and does not
            match the supported syntax.
    """
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    match = _PROXY_LINE_PATTERN.match(stripped)
    if not match:
        raise ProxyError(
            f"Line {line_number}: '{stripped}' does not match supported "
            f"proxy syntax (host:port, scheme://host:port, or "
            f"scheme://user:pass@host:port). See README.md Section 14."
        )

    scheme = match.group("scheme") or _DEFAULT_SCHEME
    port = int(match.group("port"))
    if not (1 <= port <= 65535):
        raise ProxyError(f"Line {line_number}: port {port} out of valid range 1-65535")

    return ProxyEntry(
        scheme=scheme,
        host=match.group("host"),
        port=port,
        username=match.group("username"),
        password=match.group("password"),
    )


def parse_proxy_file(path: Union[str, Path]) -> List[ProxyEntry]:
    """Parse a proxy list file into a list of ProxyEntry objects.

    Args:
        path: Path to the proxy list file (e.g. config/proxies.example.txt).

    Returns:
        List of ProxyEntry, in file order, skipping blank lines and
        lines starting with '#'.

    Raises:
        ProxyError: if the file does not exist, cannot be read, contains
            no usable entries, or contains a malformed line.
    """
    file_path = Path(path)
    if not file_path.exists():
        raise ProxyError(f"Proxy file not found: {file_path}")

    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ProxyError(f"Could not read proxy file {file_path}: {exc}") from exc

    entries: List[ProxyEntry] = []
    for line_number, line in enumerate(lines, start=1):
        entry = parse_proxy_line(line, line_number)
        if entry is not None:
            entries.append(entry)

    if not entries:
        raise ProxyError(
            f"Proxy file {file_path} contains no usable proxy entries "
            f"(only blank lines/comments, or the file is empty)"
        )

    return entries


class ProxyManager:
    """Assigns proxies to sessions round-robin, tracking per-proxy failures.

    A proxy that fails `max_retry_attempts` times in a row is taken out
    of rotation for the rest of the run (it is not deleted -- a later
    success would reset its failure count, but nothing currently calls
    mark_success() after exhaustion since an exhausted proxy is never
    assigned again). This keeps one consistently-broken proxy from
    repeatedly stalling sessions while still tolerating occasional
    transient failures.
    """

    def __init__(self, proxies: List[ProxyEntry], max_retry_attempts: int = 1) -> None:
        """
        Args:
            proxies: Parsed proxy list (from parse_proxy_file()).
            max_retry_attempts: How many consecutive failures a proxy
                tolerates before being excluded from further assignment.

        Raises:
            ProxyError: if proxies is empty.
        """
        if not proxies:
            raise ProxyError("ProxyManager requires at least one proxy")
        self._proxies = list(proxies)
        self._max_retry_attempts = max_retry_attempts
        self._failure_counts: Dict[str, int] = {p.server: 0 for p in self._proxies}
        self._next_index = 0

    def assign(self) -> ProxyEntry:
        """Return the next available proxy, round-robin among non-exhausted ones.

        Returns:
            A ProxyEntry that has not exceeded max_retry_attempts
            consecutive failures.

        Raises:
            ProxyError: if every proxy in the list is currently exhausted.
        """
        available = [p for p in self._proxies if not self._is_exhausted(p)]
        if not available:
            raise ProxyError(
                "No available proxies -- all entries have exceeded "
                f"max_retry_attempts={self._max_retry_attempts}"
            )

        # Round-robin over the full list order, skipping exhausted ones,
        # so assignment order stays predictable/reproducible rather than
        # jumping around as entries are exhausted.
        for _ in range(len(self._proxies)):
            candidate = self._proxies[self._next_index % len(self._proxies)]
            self._next_index += 1
            if not self._is_exhausted(candidate):
                return candidate
        raise ProxyError("No available proxies")  # pragma: no cover - defensive

    def mark_failure(self, proxy: ProxyEntry) -> None:
        """Record a failed use of `proxy`, counting toward exhaustion.

        Args:
            proxy: The ProxyEntry that failed (e.g. connection refused,
                context creation failed).
        """
        self._failure_counts[proxy.server] = self._failure_counts.get(proxy.server, 0) + 1

    def mark_success(self, proxy: ProxyEntry) -> None:
        """Reset `proxy`'s failure count after a successful use.

        Args:
            proxy: The ProxyEntry that was used successfully.
        """
        self._failure_counts[proxy.server] = 0

    def _is_exhausted(self, proxy: ProxyEntry) -> bool:
        return self._failure_counts.get(proxy.server, 0) > self._max_retry_attempts

    @property
    def available_count(self) -> int:
        """Number of proxies currently not exhausted."""
        return sum(1 for p in self._proxies if not self._is_exhausted(p))