# Task 1 Report

Status: completed

Commit: `8f9e296` (`Add auth helper primitives and tests`)

Test command:

```powershell
$env:PYTHONPATH = 'D:\code\ai_creative_studio\src'; python -m unittest tests.test_auth -v
```

Test output:

- Initial red run failed as expected with `ModuleNotFoundError: No module named 'creative_studio.auth'`.
- Final run passed:

```text
Ran 8 tests in 0.657s

OK
```

Concerns:

- `normalize_username()` now rejects surrounding whitespace rather than trimming it, which matches the brief's exact username contract.
- `verify_password()` returns `False` for unknown or malformed encoded strings instead of surfacing parsing errors.
- Full repository-wide tests and any later auth integration points were not touched in this task and remain for subsequent tasks.

## Review Fix Note

Date: 2026-09-01

Issue fixed:

- `verify_password()` no longer trusts the iteration count embedded in `encoded`. It now requires the fixed PBKDF2 iteration count and rejects mismatches before any hash derivation work starts.

Fix commit: `671dd89` (`Harden PBKDF2 verification`)

Regression test:

- Added `test_verify_password_rejects_unexpected_iteration_count_without_hashing` to confirm malformed iteration counts return `False` and do not call PBKDF2.

Verification:

```text
Ran 9 tests in 0.540s

OK
```
