# Synthetic Concurrent User Simulator

## 1. Overview
The Synthetic Concurrent User Simulator is an internal engineering tool built in Python for exercising the organization's DNL streaming platform under controlled, synthetic concurrent load using Playwright browser automation. It also includes a YouTube adapter used strictly for compatibility and observation comparisons.

## 2. Project Objective
- Measure how the **DNL platform** behaves under N concurrent synthetic viewer sessions (e.g., navigation latency, playback start, session stability, chat delivery) using an authorized staging/test environment.
- Provide a **comparable, narrowly-scoped** way to open a YouTube URL and observe basic playback telemetry for reference.
- Produce structured, per-session logs suitable for analysis (success/failure, duration, error categories).

## 3. Key Capabilities
- **Concurrent Sessions:** Managed through `asyncio` and limited by a configurable concurrency semaphore.
- **Ramp-Up:** Per-session start delays jittered randomly across a ramp-up window.
- **Proxy Management:** Parses test proxy lists, assigns proxies round-robin, and excludes them on consecutive connection failures.
- **Behavior Simulation:** Randomized watch durations, mouse movements, and scrolling.
- **Structured Logging:** Console event logging and JSONL session files with masked credentials.
- **Platform Adapters:** Clean abstraction layer separating core simulator orchestration from specific platform implementations.

## 4. Architecture
The orchestrator manages isolated browser sessions running in parallel via `asyncio`.
Each session:
1. Loads configuration.
2. Acquires an optional proxy and waits for its ramp-up delay.
3. Acquires a concurrency semaphore slot.
4. Uses Playwright to launch an isolated browser context.
5. Invokes the appropriate platform adapter (DNL or YouTube) to navigate.
6. Executes synthetic behavior loops (scrolling, mouse movement, watch time).
7. Tears down the context and releases the semaphore, logging the final `SessionResult`.

## 5. Project Structure
```text
synthetic-user-simulator/
├── config/
│   ├── config.example.yaml
│   └── proxies.example.txt
├── src/
│   ├── main.py (entry point)
│   ├── config/ (loaders and schemas)
│   ├── models/ (pydantic session models)
│   ├── orchestrator/ (runner, concurrency limits)
│   ├── browser/ (manager and context utilities)
│   ├── platforms/ (dnl and youtube adapters)
│   ├── chat/ (chat transport base and dnl stubs)
│   ├── behavior/ (watch schedulers, scrolling, mouse movement)
│   ├── proxy/ (parser and rotation manager)
│   ├── logging_setup/ (console and jsonl sinks)
│   └── utils/ (seeded randomizers)
├── tests/
│   └── unit/
└── logs/
```

## 6. Technology Stack
- **Language:** Python 3.11+
- **Browser Automation:** Playwright
- **Concurrency:** Python `asyncio`
- **Validation:** Pydantic
- **Testing:** Pytest

## 7. Requirements
- Windows 10/11
- Python 3.11+
- Internet access for dependency installation
- Organization-specific DNL staging environment details (see Section 22)

## 8. Installation
```powershell
# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser binaries
python -m playwright install
```

## 9. Configuration
Configuration uses YAML (`config/config.yaml`). An example file is provided in `config/config.example.yaml`.

Key Settings:
- `platform`: `youtube` or `dnl`.
- `target_url`: The URL to launch.
- `num_sessions`: Total concurrent sessions to simulate.
- `max_concurrent_browsers`: Hard cap on concurrent instances to prevent local resource exhaustion.
- `ramp_up_seconds`: Time window (in seconds) over which sessions stagger their starts.
- `use_proxies` / `proxy_file_path`: Enable proxy rotation and specify path.
- `headless`: Run browsers in headless mode.
- `random_seed`: Seed for deterministic behavior patterns.

*Note: The setting `youtube_quality_preference` is currently parsed but has no runtime effect.*

## 10. Running the Simulator
Ensure your configuration file is properly set up.
```powershell
python -m src.main --config config/config.yaml
```
Optional arguments:
- `--log-dir LOG_DIR`: Specify a custom directory for JSON Lines session logs (default: `logs`).

## 11. Concurrency and Ramp-Up
Concurrent browser sessions are launched as `asyncio` tasks. A semaphore (sized to `max_concurrent_browsers`) prevents launching too many physical browser contexts simultaneously. Ramp-up/start delays are applied to sessions *before* they acquire the semaphore, correctly distributing initial connection load without blocking the semaphore queue.

## 12. Synthetic User Behavior
Sessions use deterministic randomizers to simulate human viewing times. While watching, `page.evaluate()` executes randomized `window.scrollBy()` and `page.mouse.move()` commands to simulate engagement.

## 13. Proxy Management
Proxy lists (e.g., `host:port` or `http://user:pass@host:port`) are parsed and assigned via round-robin. The manager tracks connection failures; proxies exceeding consecutive failure thresholds are excluded from the rotation. Unique IPs are not guaranteed if the proxy list size is smaller than the concurrent session count.

## 14. Browser Contexts
Each session runs in a fully isolated Playwright browser context with separate cookies and cache.
*Note: Browser fingerprint fields (viewport, user_agent, locale) are present in the configuration schema but are not randomized by the orchestrator at runtime. All sessions use the standard Playwright Chromium defaults.*

## 15. YouTube Adapter
The `YouTubeAdapter` implements navigation and video playback observation (checking `<video>` tag presence, `paused`, and `currentTime`).
- The adapter is for observational comparison only.
- It does not post chat messages.
- It does not simulate playback interactions (e.g., clicking controls).
- It does not attempt to bypass CAPTCHA or anti-bot defenses.

## 16. DNL Adapter
The `DNLAdapter` and `DNLChatClient` are implemented as abstract stubs. They provide the integration layer for the organization's streaming platform. Running `platform: dnl` will currently raise a `PlatformError` pending organization-specific DOM/API configuration.

## 17. Logging and Observability
- **Console:** Emits human-readable operational events (session start, platform navigation, errors).
- **JSONL:** Emits one JSON record per completed session into `logs/run_<timestamp>.jsonl`.
- **Security:** Proxy credentials are automatically masked (`username:****@host:port`) in all outputs.

## 18. Error Handling and Cleanup
Individual session failures (timeouts, proxy connection errors) are caught and logged without crashing sibling sessions. Playwright contexts and pages are safely closed in `finally` blocks upon completion, failure, or process cancellation.

## 19. Testing
The project includes a comprehensive unit test suite leveraging `pytest` and `pytest-mock`.
- **Total tests:** 120
- **Execution status:** 120 passed, 0 failed.
- The unit test suite validates configuration schemas, concurrency orchestration, proxy failure handling, randomized scheduling, and basic browser lifecycle expectations. No integration test suite currently exists.

## 20. Runtime Validation
- Runtime evidence exists for single and 2-session concurrent YouTube runs.
- **Target-scale execution (e.g., 50+ concurrent sessions) has NOT been runtime validated.**

## 21. Known Limitations
- **Fingerprint Randomization:** User-agent, locale, and viewport settings are not currently varied or randomized by the orchestrator.
- **Interactions:** Random clicks and player-control interactions are not simulated.
- **Configuration:** YouTube quality preference configuration is currently ignored.
- **Names:** Indian-specific username generation is not implemented.
- **Integration Tests:** No integration-test suite is currently present.
- **Concurrency Scale:** Target-scale concurrency has not been runtime validated.

## 22. Organization-Specific DNL Configuration
The simulator provides a platform-adapter structure for integration with the organization's internal DNL streaming platform. Final DNL integration requires organization-specific configuration such as staging URLs, DOM selectors, authentication flows, chat transport protocols, and test proxy configurations. These must be supplied by the organization authority before DNL load-testing can occur.

## 23. Troubleshooting
- **Playwright Executable Missing:** Ensure you have run `python -m playwright install` to download browser binaries.
- **Timeouts:** Ensure you are not running too many concurrent browsers (`max_concurrent_browsers`) for your local machine's CPU/RAM.

## 24. Project Status
**READY WITH DOCUMENTED LIMITATIONS**

The core simulator orchestration, configuration validation, proxy management, behavioral loop scheduling, and testing pipelines are fully implemented and verified. Platform integrations for DNL and specific behavioral variations (fingerprinting, chat automation, click simulation) remain organization-specific or unimplemented, as documented in the limitations.