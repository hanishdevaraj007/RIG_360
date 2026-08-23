"""Command-line entrypoint for the Synthetic Concurrent User Simulator.

Usage (see README.md Section 15):
    python -m src.main --config config/config.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import List, Sequence

from src.config.loader import load_config
from src.config.schema import ConfigError
from src.logging_setup.logger import (
    JsonlSessionLogger,
    configure_console_logging,
    log_event,
)
from src.models.session import SessionResult, SessionStatus
from src.orchestrator.runner import Orchestrator
from src.proxy.manager import ProxyError

# NOTE on Windows event loops: Playwright requires the Proactor event
# loop on Windows. Earlier drafts of this file explicitly set
# WindowsProactorEventLoopPolicy for that reason, but that's redundant:
# Proactor has been the *default* asyncio policy on Windows since Python
# 3.8, and explicitly setting it now raises a DeprecationWarning on
# Python 3.14 (confirmed against a real run -- see stage delivery
# notes). asyncio.run() already picks it up with no code needed here.


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments.

    Args:
        argv: Argument list, or None to use sys.argv (the normal case;
            explicit argv is used by tests).

    Returns:
        Parsed arguments with `.config` and `.log_dir`.
    """
    parser = argparse.ArgumentParser(
        description="Synthetic Concurrent User Simulator -- internal load-testing tool."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config/config.yaml",
        help="Path to config YAML file (default: config/config.yaml)",
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default="logs",
        help="Directory for JSON Lines session logs (default: logs)",
    )
    return parser.parse_args(argv)


def summarize(results: List[SessionResult]) -> str:
    """Build a human-readable summary of a run's session results.

    Args:
        results: SessionResults from Orchestrator.run().

    Returns:
        A multi-line summary string with total and per-status counts.
    """
    counts = {status: 0 for status in SessionStatus}
    for result in results:
        counts[result.status] += 1

    lines = [f"Total sessions: {len(results)}"]
    for status in SessionStatus:
        lines.append(f"  {status.value}: {counts[status]}")
    return "\n".join(lines)


async def async_main(args: argparse.Namespace) -> int:
    """Async entrypoint: load config, run the orchestrator, report results.

    Args:
        args: Parsed CLI arguments.

    Returns:
        Process exit code: 0 on a run that completed (even with some
        failed sessions), 1 on a configuration error or a run where
        every session failed, 130 is used by main() for Ctrl+C.
    """
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"Configuration error:\n{exc}", file=sys.stderr)
        return 1

    console_logger = configure_console_logging(config.log_level)
    session_logger = JsonlSessionLogger(log_dir=args.log_dir)

    log_event(
        console_logger,
        "info",
        "run_started",
        platform=config.platform,
        target_url=config.target_url,
        num_sessions=config.num_sessions,
    )

    orchestrator = Orchestrator(config, console_logger, session_logger)

    try:
        results = await orchestrator.run()
    except ProxyError as exc:
        print(f"Proxy configuration error:\n{exc}", file=sys.stderr)
        return 1
    finally:
        session_logger.close()

    print()
    print(summarize(results))
    print(f"Session log written to: {session_logger.file_path}")

    log_event(
        console_logger,
        "info",
        "run_finished",
        session_log_file=str(session_logger.file_path),
    )

    if results and all(r.status == SessionStatus.FAILED for r in results):
        return 1
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Synchronous entrypoint (what `python -m src.main` actually calls).

    Args:
        argv: Argument list, or None to use sys.argv.

    Returns:
        Process exit code.
    """
    args = parse_args(argv)
    try:
        return asyncio.run(async_main(args))
    except KeyboardInterrupt:
        # asyncio.run() cancels the running task on KeyboardInterrupt
        # before this is reached; Orchestrator.run() has already turned
        # any still-running sessions into FAILED("cancelled during
        # shutdown") results and written them to the session log by the
        # time this prints. See README.md Section 28.
        print(
            "\nShutdown requested (Ctrl+C) -- sessions cancelled and cleaned up.",
            file=sys.stderr,
        )
        return 130


if __name__ == "__main__":
    sys.exit(main())