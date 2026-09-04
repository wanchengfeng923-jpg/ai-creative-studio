# Phase 5 governance evidence

## Goal

Encode repeatable evidence for retired AI caller decisions, projection scrub/restore, and versioned evaluation reports.

## Non-goals

Do not delete compatibility code, modify the live database, call real providers, or change the user-facing API.

## Acceptance

- Active prompt registry entries have exactly one production caller.
- Retired loaders have no runtime callers outside their definitions and audit metadata.
- A temporary SQLite copy reaches scrub fixed-point; a backup restore reproduces the pre-apply statistics.
- Evaluation report fixtures validate a stable schema and explicitly represent `not_run` results.

## Rollback

Revert this isolated test/documentation change. No runtime data or credentials are modified.
