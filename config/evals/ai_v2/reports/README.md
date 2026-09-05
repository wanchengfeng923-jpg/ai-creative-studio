# AI v2 Contract Reports

Reports produced by the v2 release gate must declare:

- `evidence_type=deterministic_fake`
- `quality_claim=contract_only`
- real model quality: `not-run` until Prompt and supplier access are separately approved

Minimum metrics are schema pass rate, private-field leak count, model call count,
failure classifications, retry count, and budget. Reports must not contain
Prompt text, user originals, image bytes, credentials, provider cursors, or job ids.

`candidate-contract-evidence.v1.json` is the checked-in deterministic candidate
report. Rebuild and compare it with:

```powershell
$env:PYTHONPATH = "D:\code\ai_creative_studio\src"
python -m creative_studio.ai_v2.release_gate
```

The 30 text calls in that report are in-process deterministic fake calls. They
are not external requests, token usage, latency evidence, or real model quality.
