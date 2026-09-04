# AI v2 Contract Reports

Reports produced by the v2 release gate must declare:

- `evidence_type=deterministic_fake`
- `quality_claim=contract_only`
- real model quality: `not-run` until Prompt and supplier access are separately approved

Minimum metrics are schema pass rate, private-field leak count, model call count,
failure classifications, retry count, and budget. Reports must not contain
Prompt text, user originals, image bytes, credentials, provider cursors, or job ids.

