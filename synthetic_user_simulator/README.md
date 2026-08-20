# Synthetic Concurrent User Simulator

Internal engineering tool for exercising the DNL streaming platform under
controlled, synthetic concurrent load using Playwright browser automation,
with a limited YouTube adapter used only for compatibility/observation
comparisons.

> **Status: architecture and README only.** No source modules have been
> implemented yet. This document describes the agreed design and will be
> kept in sync as modules are delivered stage by stage. Do not assume any
> feature described here is runnable until its stage explicitly says so.

---

## 1. Project Overview

This tool launches multiple concurrent Playwright browser sessions against
a target stream/video URL to observe how the DNL platform (and, in a
restricted way, YouTube) behaves under synthetic concurrent traffic:
navigation latency, playback start, session stability, chat delivery, and
failure modes, at configurable and gradually increasing scale.

It is built as an internal QA / load-testing tool, not as a generic
"multi-account bot." The distinction matters for both the DNL and YouTube
adapters and is explained in Section 4.

## 2. Objectives

- Measure how the **DNL platform** behaves under N concurrent synthetic
  viewer sessions (navigation latency, playback start, session failures,
  chat delivery) using our own authorized staging/test environment.
- Provide a **comparable, narrowly-scoped** way to open a YouTube URL and
  observe basic load/playback telemetry for reference, without attempting
  to replicate or exceed DNL-specific features on YouTube.
- Produce structured, per-session logs suitable for later analysis
  (success/failure rates, latency distributions, error categories).
- Be safe to run repeatedly against our own test environment without
  requiring escalating scale by default.

## 3. Scope

**In scope (DNL — full):**
- Concurrent session orchestration with configurable count, ramp-up, and
  per-session start jitter.
- Randomized watch duration, scrolling, and mouse-movement behavior.
- Optional proxy assignment from an example/test proxy list, with retry
  and failure logging.
- Browser context variation (viewport, locale, timezone, user-agent) for
  **cross-device/browser compatibility testing**.
- Chat message sending via an internal `ChatClient` abstraction (DNL
  implementation is a stub pending real API/DOM details — see Section 24).
- Structured per-session logging (JSON Lines + console).
- Graceful shutdown and per-session error isolation.

**In scope (YouTube — restricted, see Section 25):**
- Opening a YouTube video/stream URL and observing player/page state
  (loaded / not loaded, playback started / not started) for comparison
  purposes only.

**Explicitly out of scope (see Section 4):**
- Any mechanism whose purpose is to defeat YouTube's bot/fingerprint
  detection.
- Proxy usage aimed at giving synthetic sessions distinct apparent
  identities toward YouTube.
- Automated posting to YouTube's live chat.
- CAPTCHA or rate-limit bypass of any kind, on any platform.

## 4. Safety / Testing Boundaries

This project intentionally does **not** implement several things the
original task notes gestured at (stealth/fingerprint libraries, YouTube
chat automation, proxy-based identity rotation toward YouTube), because in
combination those features are the standard architecture for view-count
and chat-engagement manipulation on a third-party platform ("view bots"),
which this project will not build regardless of the stated intent.

What this means concretely:

| Capability | DNL (our platform) | YouTube |
|---|---|---|
| Concurrent sessions | ✅ Full | ✅ Open/observe only |
| Randomized watch duration & behavior | ✅ Full | ✅ Observation only, no engagement claim |
| Proxy assignment | ✅ Full (test proxies) | ❌ Not applied |
| Browser context variation | ✅ For compatibility testing | ✅ For compatibility testing only |
| Stealth/anti-fingerprint techniques | ❌ Not implemented anywhere | ❌ Not implemented anywhere |
| Chat automation | ✅ Via internal adapter (stub) | ❌ Not implemented |
| CAPTCHA/rate-limit bypass | ❌ Never | ❌ Never |

If a future requirement genuinely needs more YouTube capability than this,
that needs to be a separate, explicit conversation with justification —
it will not be added quietly inside an adapter.

## 5. Architecture

```text
                          ┌────────────────┐
                          │    main.py     │
                          └───────┬────────┘
                                  │
                     ┌────────────────────────┐
                     │  orchestrator/runner.py │
                     │  (ramp-up, task mgmt,   │
                     │   cancellation)          │
                     └───────────┬─────────────┘
                                 │  per session
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                   ▼
      browser/manager.py   proxy/manager.py    behavior/scheduler.py
      browser/context.py   (optional, DNL       scrolling.py / mouse.py
                             only)
              │
              ▼
      platforms/base.py  (PlatformAdapter ABC)
        ├── dnl.py        (full; selectors = TODO)
        └── youtube.py    (open/observe only)
              │
              ▼
      chat/base.py  (ChatClient ABC)
        └── dnl_chat.py    (stub; API = TODO)
              │
              ▼
      logging_setup/logger.py  →  logs/run_<timestamp>.jsonl + console
```

Each session runs as an isolated `asyncio.Task`. A failure in one session
(navigation error, proxy error, adapter error) is caught, logged with a
`SessionResult`, and does not cancel sibling sessions. Only process-level
shutdown (Ctrl+C) cancels the whole run.

## 6. Directory Structure

```text
synthetic-user-simulator/
│
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
│
├── config/
│   ├── config.example.yaml
│   └── proxies.example.txt
│
├── src/
│   ├── main.py
│   ├── config/
│   │   ├── loader.py
│   │   └── schema.py
│   ├── models/
│   │   ├── session.py
│   │   └── events.py
│   ├── orchestrator/
│   │   └── runner.py
│   ├── browser/
│   │   ├── manager.py
│   │   └── context.py
│   ├── platforms/
│   │   ├── base.py
│   │   ├── dnl.py
│   │   └── youtube.py
│   ├── chat/
│   │   ├── base.py
│   │   ├── dnl_chat.py
│   │   └── message_bank.py
│   ├── behavior/
│   │   ├── scheduler.py
│   │   ├── scrolling.py
│   │   └── mouse.py
│   ├── proxy/
│   │   └── manager.py
│   ├── logging_setup/
│   │   └── logger.py
│   └── utils/
│       └── randomization.py
│
├── tests/
│   ├── unit/
│   └── integration/
│
└── logs/
    └── .gitkeep
```

`logging/` from earlier drafts was renamed to `logging_setup/` to avoid
shadowing Python's standard-library `logging` module on import — this is a
real bug risk on any platform, not just Windows, so it's fixed now rather
than discovered later.

## 7. Prerequisites

- Windows 10/11
- Python 3.11 (target version — see Section 22 note on version
  verification)
- Visual Studio Code with the Python extension
- Internet access for `pip install` and `playwright install`
- A DNL staging/test URL you are authorized to load-test (not yet
  supplied — see Section 24)

## 8. Python Version

Target: **Python 3.11**. This is a design choice based on stable
`asyncio` and Playwright async-API support; exact package version pins
will be confirmed (not guessed) when `requirements.txt` is generated in
the implementation stage, and any version I cannot verify will be stated
as unverified rather than presented as confirmed-compatible.

## 9. Virtual Environment Setup

```powershell
python --version
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Command Prompt equivalent for activation:

```cmd
.venv\Scripts\activate.bat
```

## 10. Playwright Installation

(Run after `requirements.txt` exists and is installed — see Section 11.)

```powershell
pip install -r requirements.txt
python -m playwright install
```

`playwright install` downloads the browser binaries Playwright drives;
this is separate from `pip install` and is required once per environment.

## 11. Installation

```powershell
pip install -r requirements.txt
```

`requirements.txt` does not exist yet — it will be delivered with the
first implementation stage that has real dependencies (config loader
onward), and will list only packages actually imported by the code, each
with a stated reason.

## 12. Configuration

Configuration is YAML (`config/config.example.yaml`), chosen over TOML or
JSON because the config has nested, list-shaped sections (proxy settings,
chat bounds, per-platform settings) that read and comment more naturally
in YAML, and it matches the format already sketched during architecture
review. The loader will use `yaml.safe_load` only.

Secrets (e.g., authenticated proxy credentials, if ever used) belong in
`.env`, never in `config.yaml` or source code.

## 13. Configuration Reference

The following parameters are planned (implemented in the `config/loader.py`
+ `config/schema.py` stage, not yet built):

| Parameter | Purpose |
|---|---|
| `platform` | `dnl` or `youtube` |
| `target_url` | Stream/video URL to open |
| `num_sessions` | Total concurrent sessions to run |
| `max_concurrent_browsers` | Hard cap on simultaneous browser instances (safety valve, independent of `num_sessions`) |
| `ramp_up_seconds` | Total window over which sessions are started |
| `min_session_delay` / `max_session_delay` | Randomized per-session start jitter |
| `min_watch_duration` / `max_watch_duration` | Randomized watch time bounds (seconds) |
| `use_proxies` | Whether to assign proxies (DNL only) |
| `proxy_file_path` | Path to proxy list file |
| `proxy_retry_attempts` | Retry count before marking a session `PROXY_ERROR` |
| `chat_enabled` | Whether to send chat messages (DNL only) |
| `min_chat_messages` / `max_chat_messages` | Randomized chat message count per session |
| `min_chat_interval` / `max_chat_interval` | Randomized delay between chat messages |
| `youtube_quality_preference` | Best-effort quality hint for the YouTube adapter; documented as UI-dependent and not guaranteed |
| `headless` | Run browsers headless or headed |
| `log_level` | Console logging verbosity |
| `random_seed` | Optional seed for reproducible randomization |

## 14. Proxy File Format

**Not yet finalized against a real production format** — no real DNL
proxy format has been supplied (see Section 24). Until it is, the example
file documents one clearly-labeled placeholder syntax, kept isolated in
`proxy/manager.py` so the parser can be swapped without touching the rest
of the codebase:

```text
# config/proxies.example.txt
# One proxy per line. Example syntax only — replace with your actual
# test-proxy format when available.
#
# Unauthenticated:
#   host:port
#
# Authenticated:
#   http://username:password@host:port
#
203.0.113.10:8080
http://testuser:testpass@203.0.113.11:8080
```

This file is only used for DNL sessions, per Section 4.

## 15. Running the Simulator

Not runnable yet. This section will be filled in with the exact command
(`python -m src.main --config config/config.yaml` or equivalent) once
`main.py` exists.

## 16. Running a Small Test

Once implemented, the recommended validation order is:

```text
1 session → 2 sessions → 5 sessions → 10 sessions → 25 sessions → 50 sessions
```

Each stage should be validated (all sessions reach a terminal status,
logs look correct, no orphaned browser processes) before increasing
count. Do not start at 50.

## 17. Logging

Two sinks, both configured in `logging_setup/logger.py` (not yet built):

- **`logs/run_<timestamp>.jsonl`** — one JSON object per completed
  session, machine-parseable for later analysis.
- **Console** — human-readable line-per-event output, e.g.:

  ```text
  [2026-08-19 11:30:15] [INFO] session=0001 event=session_started
  [2026-08-19 11:30:17] [INFO] session=0001 event=navigation_started
  [2026-08-19 11:30:20] [INFO] session=0001 event=playback_started
  ```

Any proxy credentials present in `user:pass@host:port` form are masked
before being written to either sink.

**Sample log file:** the task deliverable asking for a "sample log
showing 50 concurrent sessions" will be produced **after** the logging
module and orchestrator exist, and will be explicitly labeled
`SAMPLE / ILLUSTRATIVE — NOT AN ACTUAL 50-SESSION RUN` unless we actually
execute a real 50-session run against a real DNL staging environment and
capture genuine output.

## 18. Error Handling

Distinct exception types are planned: `ConfigError`, `BrowserLaunchError`,
`NavigationError`, `TimeoutError` (Playwright's, re-raised with session
context), `ProxyError`, `PlatformError`, `ChatError`. No bare
`except Exception: pass`. Each session task catches at its own boundary
and reports a `SessionResult` with status `SUCCESS` / `PARTIAL` / `FAILED`
plus an error message where applicable; one session's failure does not
cancel others.

## 19. Testing

```text
tests/
├── unit/          # mocked Playwright + mocked adapters, no network
└── integration/   # opt-in, requires a real DNL staging URL (env var)
```

Unit tests will not require a real browser, real DNL environment, or real
YouTube access. Integration tests against DNL are opt-in and skipped by
default until a real staging URL is supplied.

## 20. Validation

Each implementation stage will ship with, at minimum:

- Syntax check: `python -m py_compile <file>`
- Import check: `python -c "import <module>"`
- Unit test command: `pytest tests/unit -v`
- Manual run steps and expected console output
- A short list of likely failure causes and how to diagnose them

## 21. Troubleshooting

Will be populated as real failure modes are encountered during
implementation and testing. Placeholder categories already anticipated:
`playwright install` not run, Windows execution-policy blocking
`Activate.ps1`, proxy connection refused, DNL selectors not yet supplied
(expected `NotImplementedError` until Section 24 is resolved).

## 22. Extending the Platform Adapters

New platforms implement `platforms/base.py`'s `PlatformAdapter` interface
(exact method signatures finalized at implementation time) and register
themselves with the orchestrator by platform name. Platform-specific
selectors/logic must stay inside that platform's adapter file — never in
`orchestrator/`, `browser/`, or `behavior/`.

## 23. DNL Integration Points

The following are **explicitly stubbed** pending real details from you,
each marked with a `TODO(DNL-INTEGRATION)` comment in code once written:

- `platforms/dnl.py`: real page/player selectors for the DNL watch page.
- `platforms/dnl.py`: authentication flow, if the target streams require
  login.
- `chat/dnl_chat.py`: the real transport for sending a chat message
  (DOM interaction vs. REST vs. WebSocket) and its message/response
  shape.
- `config/config.example.yaml`: the real DNL staging `target_url` format.

Until these are supplied, `DNLAdapter`/`DNLChatClient` will raise a clear,
documented `NotImplementedError` rather than guessing at behavior.

## 24. DNL Integration Points — Status

See Section 23; no DNL API/DOM/selector details have been provided as of
this document. Nothing here has been invented. Provide any of: staging
URL, page DOM/selectors, chat API docs, or auth flow, whenever available.

## 25. YouTube Integration Limitations

The YouTube adapter is scoped to opening a URL and reporting basic
page/player state for comparison purposes only. It does **not**:

- attempt to defeat YouTube's bot/anti-abuse detection,
- rotate proxies to disguise session identity toward YouTube,
- post chat messages,
- guarantee a specific video quality is actually applied (YouTube's
  player UI and available quality options are outside our control and
  can change; the adapter will attempt a best-effort UI interaction and
  log whether it succeeded, never assume success).

Because YouTube is a third-party site, its DOM/UI can change at any time
without notice; the adapter's selectors may need updates independent of
anything in this codebase.

## 26. Performance Considerations

Each concurrent Playwright browser context consumes non-trivial CPU/RAM.
On a typical Windows development machine, session count is far more
likely to be bottlenecked by local resources than by the target server.
The staged progression in Section 16 exists specifically to surface that
bottleneck early and safely, rather than at 50 sessions on the first run.

## 27. Resource Usage

To be measured, not assumed, once the orchestrator exists: expect to
record actual CPU/RAM usage per N-session run using Windows Task Manager
or `Get-Process` in PowerShell, rather than quoting fabricated numbers
here.

## 28. Cleanup / Shutdown

Ctrl+C triggers cancellation of all outstanding session tasks; each
session's `finally` block closes its Playwright context and, where it
owns one, its browser instance; the orchestrator waits for cleanup before
exiting and prints a final summary of session statuses. No browser
process should be left running after the process exits; this will be
explicitly checked (via Task Manager / `Get-Process chrome*`) as part of
Stage validation once the orchestrator is implemented.

## 29. Security Considerations

- No credentials in source code or `config.yaml`; secrets go in `.env`
  (gitignored).
- Proxy credentials masked in all logs.
- No CAPTCHA bypass, no anti-bot evasion, no rate-limit circumvention —
  anywhere, on any platform, per Section 4.
- DNL testing should target staging/authorized environments, not
  production traffic you don't control.

## 30. Project Limitations

- DNL adapter and chat client are non-functional stubs until real
  integration details are supplied (Section 23).
- YouTube adapter is intentionally limited to observation (Section 25).
- No implementation exists yet as of this document; this README describes
  agreed design, not delivered behavior.
- Proxy format is a placeholder pending your real test-proxy format.

## 31. Future Improvements

Candidates to discuss once the core is working: metrics aggregation/export
(e.g., summary CSV across runs), optional Docker packaging (explicitly
deferred until the native Windows version works, per project rules),
additional platform adapters if new internal properties need the same
kind of testing.