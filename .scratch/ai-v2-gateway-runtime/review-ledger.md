# AI v2 Gateway Runtime Review Ledger

## Round 1

### Findings

1. An unknown result from the initial image POST left an unrecoverable local session and attempt.
2. Ordinary chat2api `failed` and `gateway_restarted` envelopes were treated as terminal failures.
3. A terminal retry reused the provider request id and therefore resolved to the old provider job.
4. Immediate success for a continuation reset the cursor revision instead of advancing it.
5. The production composition root still constructed the legacy AI runtime, legacy generation routes remained callable, and the three v2 prompt registry entries did not identify unique callers.

### Red Evidence

- Command: `python -m unittest tests.test_ai_v2_gateway_runtime tests.test_ai_v2_static_visual tests.test_ai_v2_prompt_registry -v`
- Result before the implementation changes: 22 tests run, 9 failures and 4 errors.

### Resolution

- Initial unknown submissions fail before local session/attempt creation and map to retryable HTTP 503. Repeated client requests retain the same provider idempotency key.
- Only an explicit `terminal_failure` status, or `failed` with `terminal_failure=true`, is terminal. Other failed envelopes remain unknown.
- The logical `request_key` remains stable while provider request ids are scoped to attempt number.
- Continuation submission success now advances the prior cursor revision.
- `create_application()` and `StudioHandler` no longer construct or dispatch the legacy AI service, model client, image worker, or legacy generation endpoints.
- Registry callers now name the three concrete v2 use-case methods.

### Green Evidence

- `python -m unittest tests.test_ai_v2_gateway_runtime tests.test_ai_v2_static_visual tests.test_ai_v2_prompt_registry -v`: 22 tests passed.
- `python -m unittest discover -s tests -p 'test_ai_v2_*.py' -v`: 78 tests passed.
- `python -m unittest tests.test_auth tests.test_auth_refresh tests.test_repository.RepositoryTests.test_project_round_trip_and_search tests.test_ai_v2_app_integration -v`: 20 tests passed.
- `python -m compileall -q src chat2api launcher.py`: passed.
- `git diff --check`: passed.

### Broader Suite

- `python -m unittest discover -s tests -v`: 341 tests run; 329 passed, with 3 failures and 9 errors confined to retired legacy composition-root and legacy generation API expectations. No v2 test failed.
- The legacy tests were not made green by restoring retired production behavior. Their removal or replacement belongs to the final cutover cleanup.

### Safety Boundary

- No real text or image provider request was sent.
- `chat2api/.env`, the runtime database, generated images, uploads, and listener configuration were not modified.
