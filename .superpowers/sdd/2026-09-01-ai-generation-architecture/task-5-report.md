# Task 5 Report

- Implementation commit: `4aa9ed4`
- Outcome: first-frame image jobs are idempotent and attempt-safe.

## Review Fix Addendum

- Follow-up fix commit: `0e9e5ab`
- Root cause: transient submit exceptions were cached by `request_id`, so a same-key retry rethrew locally instead of retrying the gateway call.
- Fix: cache only successful gateway jobs; let transient submit failures fall through so the next same-key retry can submit again.

## Changes

- Added request-key reuse in `src/creative_studio/image_jobs.py` for stable `creative-studio-{visual_item_id}-attempt-{attempt}` submissions.
- Made visual-item recovery and retry transitions transactional in `src/creative_studio/repository.py`.
- Kept generation-service image dispatch explicit without changing public API/history behavior.
- Added deterministic regression tests in `tests/test_image_jobs.py` and `tests/test_repository.py`.

## Verification

- `PYTHONPATH=src python -m unittest tests.test_image_jobs tests.test_repository tests.test_generation_service -v`
- `PYTHONPATH=src python -m unittest discover -s tests -v`
- `node --check static\app.js`
- `python -m compileall -q src chat2api`
- `git diff --check`

## Review Verification

- `PYTHONPATH=src python -m unittest tests.test_image_jobs tests.test_repository -v`
- `PYTHONPATH=src python -m unittest discover -s tests -v`
- `node --check static\app.js`
- `python -m compileall -q src chat2api`
- `git diff --check`

## Notes

- No real image requests were sent.
- `image_prompt` remains server-private and history/API behavior stayed unchanged.
