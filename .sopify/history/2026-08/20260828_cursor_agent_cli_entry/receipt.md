---
plan_id: 20260828_cursor_agent_cli_entry
outcome: completed
plan_version: sha256:9a481e9161773c7d3ccb43aba20c0242e7e6dc85fc9a1861d93abdaf8746bf40
---

# completed

## Summary

Cursor IDE and local Agent CLI one-install support completed, independently reviewed, merged through PR #73, and passed the stable-release preflight.

## Key Decisions

- Keep one cursor:<language> install for IDE and local Agent CLI.
- Install the Cursor-only CLI entry from host-specific bilingual templates and keep it out of shared host Skill trees.
- Select the CLI entry for plan, development, resume, and closeout requests without forcing ordinary questions through it.
- Retain BASELINE_SUPPORTED and keep IDE/CLI behavior evidence separate from installation evidence.
