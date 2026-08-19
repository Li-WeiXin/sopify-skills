# Getting Started with Sopify

This guide walks through adding Sopify to an existing repository and using it
with your preferred AI host.

## Overview

Sopify adds resumable, traceable AI workflows to any project. After setup:

- Work pauses automatically when facts are missing or a decision needs you
- Work resumes from where it stopped — even on a different AI host
- Plans, decisions, and reviews persist as reusable project assets

## Requirements

- Git repository (local or remote)
- Python 3.11+
- An AI host: Codex, Claude, Qoder, Copilot, or Cursor

## Quick Setup (One Command)

From your project root:

```bash
curl -fsSL https://github.com/evidentloop/sopify/releases/latest/download/install.sh | bash -s -- --target copilot
```

This creates:

| File | Purpose |
|------|---------|
| `.sopify/sopify.json` | Workspace marker — tells the host that Sopify is active |
| `.gitignore` | Managed block — excludes transient state from version control |
| `.github/copilot-instructions.md` | Copilot entry — project-level instruction for Copilot |

> **Skip Copilot files:** Pass `--no-copilot` with `--target copilot` if you only want workspace markers.

## Inspect-First Setup

Review the script before running:

```bash
curl -fsSL -o sopify-install.sh https://github.com/evidentloop/sopify/releases/latest/download/install.sh
less sopify-install.sh
bash sopify-install.sh --target copilot
```

Or clone and run the Python entry point directly:

```bash
git clone https://github.com/evidentloop/sopify.git /tmp/sopify
python3 /tmp/sopify/scripts/sopify_init.py init --workspace .
```

## Optional EvidentLoop Companion

Sopify works without EvidentLoop. [EvidentLoop](https://github.com/evidentloop/evidentloop)
turns a local Git diff into an interactive, feedback-ready HTML audit report. To install
the current EvidentLoop CLI and Skill from their official sources, or reuse healthy
existing components, opt in explicitly:

```bash
curl -fsSL https://github.com/evidentloop/sopify/releases/latest/download/install.sh | bash -s -- --target codex:en-US --with-evidentloop
```

If you downloaded the installer for inspection, pass the same flag to
`bash sopify-install.sh`.

The option is off by default and is not saved as a runtime setting. The CLI is a
current-user `uv tool`; the Skill path depends on the target host:

| Target | EvidentLoop Skill path | Scope |
|--------|-------------------------|-------|
| Codex | `$HOME/.agents/skills/evidentloop/` | Current user |
| Claude | `$HOME/.claude/skills/evidentloop/` | Current user |
| Qoder | `$HOME/.qoder/skills/evidentloop/` | Current user |
| Copilot | `<workspace>/.github/skills/evidentloop/` | Current project |

These locations follow the host documentation for
[Codex](https://learn.chatgpt.com/docs/build-skills),
[Claude Code](https://code.claude.com/docs/en/slash-commands),
[Qoder](https://docs.qoder.com/en/cli/Skills), and
[GitHub Copilot](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills).

For new installs, Sopify follows EvidentLoop's current official commands: `uv tool install
evidentloop` for the CLI and `npx skills@latest add evidentloop/evidentloop --skill
evidentloop` for the Skill. Existing components are reused when the CLI doctor is healthy
and the Skill front matter declares `name: evidentloop`; Sopify does not upgrade them or
maintain an EvidentLoop compatibility matrix. `uv` is required only when the CLI is
missing; Git and `npx` only when the Skill is missing.

Sopify is installed first and remains usable if the optional setup does not finish. Skill
downloads happen in a temporary directory and are copied to the final host path only after
validation, so a failed attempt does not leave a partial Skill there. Rerun the same
command, or install EvidentLoop independently from its official repository.

After a fresh CLI install, the installer also checks that a future host can resolve
`evidentloop` from `PATH`. If the uv tool directory is not visible yet, it leaves the
validated CLI in place and asks you to run `uv tool update-shell`, restart the shell and
AI host, then rerun the same command. It never edits your shell profile automatically.

For Copilot, pass `--workspace <path>` or run the installer from the target project.
The installer writes only `.github/skills/evidentloop/`; it does not add a project
`.agents/skills/` copy or `skills-lock.json`. That is GitHub's documented project Skill
location and becomes part of your project: review it, and commit it yourself if a cloud
workflow needs it. Sopify does not commit or update it. A cloud-hosted agent also does not
automatically receive the EvidentLoop CLI installed on your local machine. This option
proves local component placement and health only; Skill discovery and audit E2E
still require host evidence, and cloud CLI availability must be provisioned separately.

## Host-Specific Setup

### Codex / Claude

These hosts use a global prompt header. Install Sopify globally first, then
bootstrap individual projects:

```bash
# Global install (one-time)
curl -fsSL https://github.com/evidentloop/sopify/releases/latest/download/install.sh | bash -s -- --target codex:en-US

# Workspace bootstrap (per project)
curl -fsSL https://github.com/evidentloop/sopify/releases/latest/download/install.sh | bash -s -- --target copilot
```

After install, use `~go` in your AI host to start a managed workflow.

### Copilot

Copilot discovers instructions via project-level files. The install command
writes `.github/copilot-instructions.md` automatically.

```bash
curl -fsSL https://github.com/evidentloop/sopify/releases/latest/download/install.sh | bash -s -- --target copilot
```

Copilot reads project-level instruction files across its supported surfaces
(VS Code Chat, Copilot CLI, Cloud Agent, Code Review — as of May 2025).
Full trigger wiring (equivalent to Codex/Claude `~go`) is coming in a future
release.

### Cursor IDE / Cursor Agent CLI

Cursor uses a split installation: a project rule in `.cursor/rules/sopify.mdc`,
a global Skill/payload tree under `~/.cursor/`, and user-level hooks in
`~/.cursor/hooks.json`. Run the installer from the target project:

```bash
python3 scripts/install_sopify.py --target cursor --workspace .
```

`--workspace` writes the project rule only; it does not create `.sopify`.
`--with-evidentloop` is not supported for Cursor in this release. The rule is
valid Cursor `.mdc` with `alwaysApply: true` and a portable Skill path
`~/.cursor/skills/sopify`. Cursor discovers the same rule surface in its IDE
and Agent CLI, but discovery is not execution proof. See
[Cursor host acceptance](./cursor-host.md) for hook boundaries and the
separate IDE/CLI black-box checks. The current tier remains
`BASELINE_SUPPORTED`.

## Verify Setup

After bootstrap, check the workspace marker:

```bash
cat .sopify/sopify.json
```

Expected output:

```json
{
  "bundle_version": "2026-06-10.191940",
  "capabilities": [],
  "locator_mode": "global_first",
  "schema_version": "1",
  "workspace_kind": "external"
}
```

## Using Sopify

### Start a Task

Open your AI host in the project directory and describe what you want to do:

```text
Fix the typo on line 42 in src/utils.ts
```

For managed workflows with planning and review:

```text
~go Add user authentication with JWT
```

### Commands

> **Note:** These commands currently work in Codex and Claude. Copilot trigger
> wiring is coming in a future release — see [Host-Specific Setup](#copilot).

| Command | Description |
|---------|-------------|
| `~go` | Automatically route and run the full workflow |
| `~go plan` | Plan only — analyze and produce a plan without executing |
| `~go finalize` | Close out the current plan |

Most users only need `~go`.

Ordinary questions and small fixes are answered directly, even if local plan state is stale. Sopify reads the managed-plan chain only when you start, continue, or finalize managed work; any state write then goes through `sopify_writer`.

### What Gets Created

As you work, Sopify creates project knowledge in `.sopify/`:

```
.sopify/
├── sopify.json       # workspace marker (from bootstrap)
├── project.md        # technical conventions (auto-created)
├── blueprint/        # design baseline and protocol spec
├── plan/             # active work packages + receipts
├── history/          # archived completed work + receipts
└── state/            # protocol state (git-ignored, 2 files only)
```

- `blueprint/`, `plan/`, `history/` are tracked by git — they are your project memory
- `state/` is git-ignored — it holds only `active_plan.json` (a pure `plan_id` pointer) and `current_handoff.json` (resume hint). If missing during a managed action, the host can browse `plan/` for candidates without auto-resuming one during ordinary questions

## Updating

Re-run the install command to update the workspace marker and instruction files:

```bash
curl -fsSL https://github.com/evidentloop/sopify/releases/latest/download/install.sh | bash -s -- --target copilot
```

The workspace bootstrap path is idempotent — it preserves existing settings and only updates
what changed.

## Removing Sopify

```bash
rm -rf .sopify/
rm -f .github/copilot-instructions.md
```

Then remove the `# BEGIN sopify-managed` / `# END sopify-managed` block from
your `.gitignore`.

## Further Reading

- [How Sopify Works](./how-sopify-works.en.md) — workflow, checkpoints, directory structure
- [External Repo Quickstart](../examples/external-repo-quickstart/README.md) — minimal step-by-step demo
- [Contributing](../CONTRIBUTING.md) — development and validation guidelines
