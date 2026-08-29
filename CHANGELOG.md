# Changelog

All notable changes to Sopify are documented in this file.

Format: Summary → Changed → Plan Packages. File-level details live in `git log`.

## [Unreleased]

## [2026-08-30.001152] - 2026-08-30

### Summary

Extended the existing Cursor user-scope installation so one install covers the IDE and local Agent CLI.

### Changed

- **Cursor Agent CLI**: Added bilingual top-level Skills for plan, development, resume, and closeout requests. The CLI selects the entry when relevant, reads the installed Plugin Rule, and keeps IDE/CLI behavior evidence separate.
- **Cursor installation**: The existing `cursor:<language>` target now installs and verifies the CLI entry, replaces stale local copies on reinstall, and keeps settings, proxy, model, account, and Cloud Agent out of scope.

### Plan Packages

- `20260828_cursor_agent_cli_entry` → archived after PR #73 merge and independent Cursor release-gate approval; stable release follows this entry.

## [2026-08-22.134737] - 2026-08-22

### Summary

Added baseline support for local Cursor IDE without per-project Sopify setup.

### Changed

- **Cursor host**: Added a user Plugin entry, global Skills/payload, user Hooks, and matching GitHub Pages content. Local IDE evidence covers routing, planning, writer writes, and direct-write rejection. Agent CLI automatic entry and Cloud Agent remain outside scope.

### Plan Packages

- `20260819_cursor_support` → release candidate; explicit archive remains a later `~go finalize` action

## [2026-07-21] - 2026-07-21

### Summary

Added optional EvidentLoop installation and made Sopify's bilingual workflow, repository handoff, and public product surface easier to understand.

### Changed

- **Optional audit companion**: Added explicit `--with-evidentloop` installation with host-native Skill paths, prerequisite checks, healthy-component reuse, and clear partial-success recovery.
- **Workflow contracts**: Clarified the responsibilities and handoffs of Analyze, Design, Develop, KB, and Templates while keeping consultation read-only and archival explicit.
- **Public product surface**: Added responsive English and Chinese product pages, refreshed workflow and architecture visuals, and documented the optional companion and Python 3.11 requirement.
- **Protocol and verification**: Tightened plan-package, writer, distribution, and host-consumption contracts with targeted scenarios and full regression coverage.

### Plan Packages

- `20260718_evidentloop_optional_audit_integration` → archived to `history/2026-07/`
- `20260720_plain_language_output` → release candidate; archive follows verified publication

## [2026-07-17.194640] - 2026-07-17

### Summary

Made managed-plan entry intent-first: existing work resumes only when the user explicitly asks to continue or uses `~go`, while ordinary questions and small fixes stay on the current request.

### Changed

- **Protocol entry**: Added finite state facts and prompt rules for stale pointers, checkpoint answers, valid plan switches, and three parallel-progress signals without new state, locks, or automatic repair.
- **Receipt safety**: Made plan receipt creation atomic and non-overwriting, with concurrent regression coverage.
- **Docs and evidence**: Aligned bilingual public docs, recorded bounded Codex and Claude host evidence, and archived the independently reviewed plan package.

### Plan Packages

- `20260717_sopify_entry_preflight` → archived to `history/2026-07/`

## [2026-07-16.230506] - 2026-07-16

### Summary

Added a repo-local, Codex-first MCP registration pilot with dry-run/apply safeguards and real stdio verification. Codex is the first validation target; other supported hosts remain future evidence work rather than being classified as incapable.

### Changed

- **MCP registration**: Added `scripts/sopify_mcp_register.py`, delegating user config changes to official `codex mcp get/add` commands and failing closed on conflicts, disabled servers, unsupported MCP SDK versions, and executable startup errors.
- **Tests**: Covered absent, no-op, disabled/conflicting config, apply verification, missing dependency, unsupported SDK versions, and invalid executable paths.
- **Docs**: Documented the maintainer-only pilot boundary and deferred dependency packaging, doctor integration, and multi-host automation until further host evidence exists.

### Plan Packages

- `20260626_mcp_tool_plane_pilot` → archived to `history/2026-07/`

## [2026-06-13.221525] - 2026-06-13

### Summary

- Changes across: Docs, Scripts, Tests, Changed.

### Changed

- **Docs**: Refined public documentation (4 files)
- **Scripts**: Adjusted maintenance scripts (2 files)
- **Tests**: Updated automated coverage (2 files)
- **Changed**: Updated project files (15 files)

## [2026-06-13.220854] - 2026-06-13

### Summary

Public surface refresh + W0 version model hardening: README rewrite with new hero tagline ("Resumable AI coding — ask first, plans stay with the repo"), bilingual scene illustrations, product-form diagrams, architecture SVG update, installer fail-loud version handling, 4-state status/doctor classifier, and protocol check continuation semantics fix.

### Changed

- **README**: New hero tagline (EN/CN), "how it works" body paragraph (managed workflow scoping, git-tracked plans/receipts vs local resume pointers), host compatibility badges (Codex / Claude / Qoder / Copilot), `for-the-badge` style for all shields.
- **Illustrations**: 3 bilingual scene images (ask / cross-host / decision), 2 product-form release SVGs (EN/CN), architecture SVG regenerated.
- **Installer (W0)**: Fail-loud version handling — 3 silent `0.0.0-dev` fallbacks replaced with `InstallError`; 4-state inspection classifier (`up_to_date` / `pinned_old_but_healthy` / `stale` / `broken`) with status/doctor rendering; bootstrap workspace stale-pin diagnostics.
- **Protocol check**: Continuation semantics fix for handoff pointer handling.
- **Docs**: Release process preflight updated; getting-started bundle_version example aligned to version model.
- **Blueprint**: Status L2 active; focus updated to "版本模型闭环 + 公共展示面刷新".

### Host Support

- Codex / Claude / Qoder: PROTOCOL_VERIFIED
- Copilot: BASELINE_SUPPORTED (verification planned for W1a)

## [2026-06-10.191940] - 2026-06-10

### Summary

P8 Protocol Kernel & Runtime Retirement: deleted runtime (~15.6K LOC), renamed canonical root to `.sopify`, simplified state to 2 files, onboarded Qoder as PROTOCOL_VERIFIED host, aligned all docs to "development process protocol layer" positioning.

### Changed

- **Runtime deleted**: Removed `runtime/` directory (46 files / ~15.6K LOC). Protocol kernel (`sopify_writer` + `sopify_contracts` + `protocol.md`) is now the sole truth source.
- **Canonical root**: Renamed `.sopify-skills` → `.sopify` across all layers (~481 replacements). Removed `plan.directory` configurable root.
- **State model**: Simplified from 6 state files + sessions/ to 2 files (`active_plan.json` + `current_handoff.json`). Both gitignored.
- **Host support**: Added Qoder as `PROTOCOL_VERIFIED` host (home-scope hybrid, bare `--target qoder`). Renamed `DEEP_VERIFIED` → `PROTOCOL_VERIFIED` for Codex/Claude.
- **Product positioning**: Established "development process protocol layer" (开发过程协议层) with 4-layer model: 用户层/产品层/能力层/架构层.
- **Blueprint**: Full narrative sync — ADR-013/017 updated, host capability governance rewritten, Runtime 五层架构 marked RETIRED, Validator → protocol admission.
- **Docs**: README pair rewritten; architecture SVG regenerated; how-sopify-works fully updated to post-P8 model.
- **Authorization**: EAR/gate_receipt retired. Audit chain now uses `plan/<id>/receipts/*.json` + `history/<id>/receipt.md`.
- **Workspace marker**: `sopify.json` updated — removed `runtime_gate` capability, `workspace_kind` set to `external`.

### Plan Packages

- `20260605_p8_protocol_kernel_runtime_retirement` → archived to `history/2026-06/`

## [2026-05-31.142150] - 2026-05-31

### Summary

Pre-launch consolidation: README rewrite, SVG diagrams, CI golden snapshot auto-fix, output contract upgrade.

### Changed

- **Docs**: Complete README pair rewrite for pre-launch (PR #50); JPG → SVG/PNG diagram migration, image compression (PR #51)
- **CI**: Extract golden snapshot regeneration script + auto-stage in pre-commit hook (PR #53)
- **Output Contract**: Add density gradient, symbol discipline, desensitization self-check (PR #54)
- **Tests**: Update golden snapshot markers, add regeneration script to fixtures (PR #51, #53, #54)

## [2026-05-30.222058] - 2026-05-30

### Summary

- Changes across: Docs, Tests, Changed.

### Changed

- **Docs**: Refined public documentation (4 files)
- **Tests**: Updated automated coverage (1 files)
- **Changed**: Updated project files (14 files)

## [2026-05-30.213559] - 2026-05-30

### v1.0 — Pre-launch Summary

Sopify 解决的问题只有一条：AI 会忘，任务不能因为一次对话结束就丢失进度。

v1.0 包含的能力：

- **可恢复工作流**：任务在任意时间点中断，下次会话从 project state 恢复，无需重新解释背景
- **三段式结构化流程**：需求分析 → 方案设计 → 开发实施，每段均可单独触发或跳过
- **Checkpoint 暂停机制**：事实缺失时 AI 停下追问，遇到分叉决策时等待用户确认，不猜测推进
- **持久知识库**：项目约定、长期偏好、方案包跨会话保留在 `.sopify/`，git-tracked
- **三宿主支持**：Copilot、Codex、Claude（ZH/EN 双语），单行命令安装，无侵入性
- **输出契约**：所有阶段输出遵循统一格式（状态符、验证摘要、Changes、Next），AI 不自行发明格式
- **一行命令启动**：`~go` 自动检测活动 plan 并恢复执行，无需记住上次做到哪步

**当前状态：** 656 测试全绿，推广阻断项清零。

## [2026-05-30.193318] - 2026-05-30

### Summary

- Changes across: Scripts, Tests.

### Changed

- **Scripts**: Adjusted maintenance scripts (1 files)
- **Tests**: Updated automated coverage (1 files)

## [2026-05-30.152842] - 2026-05-30

### Summary

- Updated 1 active plan package(s); Changes across: Docs, Changed.

### Changed

- **Docs**: Refined public documentation (2 files)
- **Changed**: Updated project files (6 files)

### Plan Packages

- `20260529_pre_launch_consolidation` (active)

## [2026-05-29.180035] - 2026-05-29

### Summary

- `~go exec` 命令移除，`~go` 自动检测活动 plan 并恢复执行
- 预发布安全清理：.gitignore 补全、本地配置取消追踪、残留 pattern 清除

### Changed

- **Runtime**: `~go exec` 全仓移除；bare `~go` 自动路由 `exec_plan`；`~go finalize` 显式路由 `archive_lifecycle`；旧命令输入返回 migration hint
- **Security**: `.gitignore` 补全敏感路径；`.claude/settings.local.json` 取消追踪；`bootstrap_workspace.py` 移除 `~summary` 残留 regex
- **Docs**: README / header templates / blueprint protocol 命令表对齐
- **Tests**: 658 tests 全过，新增 `~go exec` migration hint 测试

## [2026-05-28.044700] - 2026-05-28

### Summary

- Stale stub diagnostics: enriched error messages when workspace stub version mismatches installed bundle
- Removed `reason_code` from user-facing develop output templates (internal-only field)
- Output contract enforcement for all skill stages (PR #48)
- Added renderer scope audit backlog item

### Changed

- **Installer**: `_stale_stub_diagnostic()` helper in `bootstrap_workspace.py`; enriched `_workspace_bundle_recommendation` in `inspection.py`; neutral hint in `gate_output.py`
- **Skills**: Removed `reason_code` column from 6 develop output templates (ZH+EN); added human-readable 说明/Note column to partial templates; updated `output-contract.md` and `develop-rules.md`
- **Tests**: 2 new unit tests for stale stub diagnostic; updated golden snapshot hashes

### Plan Packages

- `20260528_output_contract_enforcement` (completed)

## [2026-05-27.220559] - 2026-05-27

### Summary

- Host bundle unification closeout: `runtime_bundle` → `sopify_bundle` rename, Copilot 纳入统一 registry.
- Skill writing quality convergence: shared writing DNA (6 rules ZH+EN), output template v2 with verification tables, render pipeline fix for top-level `references/` inline.
- Changes across: Installer, Skills, Tests, Plan Governance.

### Changed

- **Installer**: `render_single_file()` now inlines top-level `references/` directory (+8 lines)
- **Skills**: Shared writing DNA + 3 SKILL.md philosophy lines + 4 output templates rewritten with verification summary tables, reason_code, review evidence, status symbol constraint (ZH+EN, 22 files)
- **Scripts**: `check-runtime-smoke` → `check-bundle-smoke` rename, script cleanup
- **Tests**: Golden snapshot hashes updated (8/8 passing)
- **Docs**: Public documentation and README refinements

### Plan Packages

- `20260526_pre_launch_host_and_bundle_unification` (completed → archived)
- `20260527_skill_writing_quality` (completed → archived)

## [2026-05-26.221112] - 2026-05-26

### Summary

- Updated 1 active plan package(s); Changes across: Scripts, Changed.

### Changed

- **Scripts**: Adjusted maintenance scripts (1 files)
- **Changed**: Updated project files (52 files)

### Plan Packages

- `20260526_pre_launch_host_and_bundle_unification` (active)

## [2026-05-26.134110] - 2026-05-26

### Summary

- Updated 1 active plan package(s); Changes across: Docs, Runtime, Scripts, Skills, Tests, Changed.
- Runtime slimming closeout: `_kernel_turn.py` → `_orchestration.py` rename, kernel turn direct tests, smoke contract stabilization, docs + archive.

### Changed

- **Docs**: Refined public documentation (2 files)
- **Runtime**: Updated runtime internals — module rename + docstring polish + plan/ package split (15 files)
- **Scripts**: Adjusted maintenance scripts (2 files)
- **Skills**: Synced prompt-layer skills (4 files)
- **Tests**: Updated automated coverage — 5 kernel turn contract tests + rename alignment (6 files)
- **Changed**: Updated project files (1 files)

### Plan Packages

- `20260522_runtime_slimming_kernel_extraction` (active)

## [2026-05-25.194723] - 2026-05-25

### Summary

- Changes across: Runtime, Tests.

### Changed

- **Runtime**: Updated runtime internals (5 files)
- **Tests**: Updated automated coverage (5 files)

## [2026-05-24.205420] - 2026-05-24

### Summary

- Changes across: Scripts.

### Changed

- **Scripts**: Adjusted maintenance scripts (1 files)

## [2026-05-22.232127] - 2026-05-22

### Summary

- Updated 1 active plan package(s); Changes across: Docs, Runtime, Skills, Tests.

### Changed

- **Docs**: Refined public documentation (2 files)
- **Runtime**: Updated runtime internals (5 files)
- **Skills**: Synced prompt-layer skills (4 files)
- **Tests**: Updated automated coverage (2 files)

### Plan Packages

- `20260522_runtime_slimming_kernel_extraction` (active)

## [2026-05-22.231627] - 2026-05-22

### Summary

- Updated 1 active plan package(s); Changes across: Runtime, Tests.

### Changed

- **Runtime**: Updated runtime internals (5 files)
- **Tests**: Updated automated coverage (2 files)

### Plan Packages

- `20260522_runtime_slimming_kernel_extraction` (active)

## [2026-05-21.101226] - 2026-05-21

### Summary

- Updated 1 active plan package(s); Changes across: Docs, Runtime, Skills, Tests, Changed.

### Changed

- **Docs**: Refined public documentation (2 files)
- **Runtime**: Updated runtime internals (21 files)
- **Skills**: Synced prompt-layer skills (4 files)
- **Tests**: Updated automated coverage (1 files)
- **Changed**: Updated project files (1 files)

### Plan Packages

- `20260520_p6_canonical_writer_cutover` (active)

## [2026-05-21.100824] - 2026-05-21

### Summary

- Updated 1 active plan package(s); Changes across: Runtime, Tests, Changed.

### Changed

- **Runtime**: Updated runtime internals (21 files)
- **Tests**: Updated automated coverage (1 files)
- **Changed**: Updated project files (1 files)

### Plan Packages

- `20260520_p6_canonical_writer_cutover` (active)

## [2026-05-20.221259] - 2026-05-20

### Summary

- Updated 1 active plan package(s); Changes across: Scripts, Tests, Changed.

### Changed

- **Scripts**: Adjusted maintenance scripts (2 files)
- **Tests**: Updated automated coverage (3 files)
- **Changed**: Updated project files (2 files)

### Plan Packages

- `20260520_p6_canonical_writer_cutover` (active)

## [2026-05-20.215230] - 2026-05-20

### Summary

- Updated 1 active plan package(s); Changes across: Docs, Runtime, Scripts, Skills, Tests, Changed.

### Changed

- **Docs**: Refined public documentation (2 files)
- **Runtime**: Updated runtime internals (4 files)
- **Scripts**: Adjusted maintenance scripts (2 files)
- **Skills**: Synced prompt-layer skills (4 files)
- **Tests**: Updated automated coverage (2 files)
- **Changed**: Updated project files (10 files)

### Plan Packages

- `20260520_p6_canonical_writer_cutover` (active)

## [2026-05-20.214859] - 2026-05-20

### Summary

- Updated 1 active plan package(s); Changes across: Runtime, Scripts, Tests, Changed.

### Changed

- **Runtime**: Updated runtime internals (4 files)
- **Scripts**: Adjusted maintenance scripts (2 files)
- **Tests**: Updated automated coverage (2 files)
- **Changed**: Updated project files (10 files)

### Plan Packages

- `20260520_p6_canonical_writer_cutover` (active)

## [2026-05-20.191545] - 2026-05-20

### Summary

- Updated 1 active plan package(s); Changes across: Runtime, Scripts, Tests, Changed.

### Changed

- **Runtime**: Updated runtime internals (7 files)
- **Scripts**: Adjusted maintenance scripts (2 files)
- **Tests**: Updated automated coverage (4 files)
- **Changed**: Updated project files (10 files)

### Plan Packages

- `20260520_p6_canonical_writer_cutover` (active)

## [2026-05-20.143728] - 2026-05-20

### Summary

- Archived 1 plan package(s); Changes across: Docs, Runtime, Skills, Tests.

### Changed

- **Docs**: Refined public documentation (2 files)
- **Runtime**: Updated runtime internals (1 files)
- **Skills**: Synced prompt-layer skills (4 files)
- **Tests**: Updated automated coverage (4 files)

### Plan Packages

- `20260520_p5_contract_surface_shrinkage` (archived)

## [2026-05-20.143147] - 2026-05-20

### Summary

- Archived 1 plan package(s); Changes across: Docs, Runtime, Skills.

### Changed

- **Docs**: Refined public documentation (2 files)
- **Runtime**: Updated runtime internals (1 files)
- **Skills**: Synced prompt-layer skills (4 files)

### Plan Packages

- `20260520_p5_contract_surface_shrinkage` (archived)

## [2026-05-20.142600] - 2026-05-20

### Summary

- Archived 1 plan package(s); Changes across: Runtime.

### Changed

- **Runtime**: Updated runtime internals (1 files)

### Plan Packages

- `20260520_p5_contract_surface_shrinkage` (archived)

## [2026-05-19.183358] - 2026-05-19

### Summary

- Updated 1 active plan package(s); Changes across: Docs, Scripts, Skills, Changed.

### Changed

- **Docs**: Refined public documentation (4 files)
- **Scripts**: Adjusted maintenance scripts (1 files)
- **Skills**: Synced prompt-layer skills (4 files)
- **Changed**: Updated project files (12 files)

## [2026-05-19.180220] - 2026-05-19

### Summary

- Changes across: Docs, Changed.

### Changed

- **Docs**: Refined public documentation (1 files)
- **Changed**: Updated project files (1 files)

## [2026-05-19.174031] - 2026-05-19

### Summary

- Updated 1 active plan package(s); Changes across: Docs, Scripts, Changed.

### Changed

- **Docs**: Refined public documentation (4 files)
- **Scripts**: Adjusted maintenance scripts (1 files)
- **Changed**: Updated project files (12 files)

## [2026-05-13.111757] - 2026-05-13

### Summary

- Changes across: Runtime, Tests, Changed.

### Changed

- **Runtime**: Updated runtime internals (2 files)
- **Tests**: Updated automated coverage (3 files)
- **Changed**: Updated project files (1 files)

## [2026-05-11.202509] - 2026-05-11

### Summary

- P4c Host Consumption Governance delivered: host-facing prompt/runtime surfaces now consume canonical protocol facts instead of exposing route taxonomy, blueprint concepts, or internal helper details.
- Changes across: Docs, Runtime, Scripts, Skills, Tests.

### Changed

- **Docs**: Added protocol §8 as the host-consumption authority and refreshed blueprint/history bookkeeping.
- **Runtime**: Converged output, gate status fallback, Next hints, and status/doctor text around handoff/protocol facts.
- **Scripts**: Added enhancement declaration validation for host capability metadata.
- **Skills**: Reduced Codex/Claude prompt assets to protocol references and user-facing workflow semantics.
- **Tests**: Added rendering/status/doctor coverage for de-taxonomy and host-facing labels.

### Plan Packages

- `20260510_p4c_host_consumption_governance` (archived)

## [2026-05-09.175537] - 2026-05-09

### Summary

- Archived 1 plan package(s); Changes across: Docs, Runtime, Skills.

### Changed

- **Docs**: Refined public documentation (2 files)
- **Runtime**: Updated runtime internals (2 files)
- **Skills**: Synced prompt-layer skills (4 files)

### Plan Packages

- `20260509_p4b_runtime_surface_consolidation` (archived)

## [2026-05-09.170825] - 2026-05-09

### Summary

- Archived 1 plan package(s); Changes across: Runtime.

### Changed

- **Runtime**: Updated runtime internals (2 files)

### Plan Packages

- `20260509_p4b_runtime_surface_consolidation` (archived)

## [2026-05-09.152019] - 2026-05-09

### Summary

- Updated 1 active plan package(s); Changes across: Scripts, Changed.

### Changed

- **Scripts**: Adjusted maintenance scripts (1 files)
- **Changed**: Updated project files (1 files)

### Plan Packages

- `20260509_p4b_runtime_surface_consolidation` (active)

## [2026-05-08.191000] - 2026-05-08

### Summary

- Archived 1 plan package(s); Changes across: Skills, Tests.

### Changed

- **Skills**: Synced prompt-layer skills (12 files)
- **Tests**: Updated automated coverage (1 files)

### Plan Packages

- `20260508_p3b_perimeter_cleanup` (archived)

## [2026-05-07.220011] - 2026-05-07

### Summary

P3a Contract-Aligned Surface Cleanup delivered in full. Execution routing convergence, cancel_scope fix, knowledge_sync audit trail, dead path cleanup (-88 LOC), blueprint milestone compression + P4b split-out.

### Changed

- **Execution routing convergence**: authorized ActionProposal → deterministic route derive (`_derive_route_from_authorized_proposal`); Router.classify demoted to bare-text legacy fallback
- **cancel_scope fix**: cancel_flow inlined in derive path, fixing default-to-global-cleanup bug when artifacts list is empty
- **knowledge_sync audit trail**: `knowledge_sync_result` threaded through full archive pipeline (success / blocked / archive_target_conflict)
- **Dead code removal**: removed 6 unreferenced private functions + 1 orphan constant (-88 LOC)
- **Test coverage**: +17 routing convergence tests, +2 archive knowledge_sync tests, classify exclusion + checkpoint split coverage filled
- **Blueprint restructure**: P0–P3a compressed to one-line summaries; runtime weight reduction split out as P4b (runtime_surface_consolidation)

### Plan Packages

- `20260507_p3a_contract_aligned_surface_cleanup` (archived)

---

## Historical Entries (compressed)

The 102 auto-generated entries below (2026-01-15 to 2026-05-07) have been compressed into phase summaries. Full file-level detail is preserved in `git log`.

### P3a Development Iterations (2026-05-03 – 2026-05-07)

25 releases. Contract-aligned surface cleanup development:

- Execution routing → ActionProposal-based derive pipeline
- cancel_scope hardening and fail-close contract enforcement
- knowledge_sync audit trail through archive lifecycle
- Deterministic guard, signal priority, failure recovery tables
- Fail-close contract fixture + eval entries
- Plan: `20260507_p3a_contract_aligned_surface_cleanup`

### P2 Local Action Contracts (2026-05-01 – 2026-05-02)

8 releases. Action intent and proposal authorization:

- ActionIntent model + gate integration
- Action proposal / rejection / authorization flow
- Direct-edit runtime guard with entry_guard_reason_code
- Plan: `20260506_p2_local_action_contracts`

### P1.5 Authorization & Plan Materialization (2026-04-27 – 2026-04-29)

6 releases. Checkpoint-gated plan writes and rejection surface:

- Plan materialization auth (checkpoint-gated plan writes)
- Reject surface (proposal_rejected route + host action)
- Advance slices (multi-slice plan orchestration)
- Plans: `20260506_p15_authorization_contract_spec`, `20260506_p15_reject_surface`, `20260505_p15_plan_materialization_auth`, `20260505_p15_advance_slices`

### P1 Runtime System Build-Out (2026-03-19 – 2026-04-14)

42 releases. Core runtime construction:

- Engine, router, gate, handoff, output pipeline
- Checkpoint system (clarification + decision)
- Develop callback + quality loop
- Skill resolver + builtin catalog + runtime skill execution
- KB bootstrap + blueprint scaffold
- Plan registry + plan scaffold + archive lifecycle
- State store (session-scoped review isolation)
- Bundle manifest + install/payload bootstrap
- Convention smoke test (`20260501_convention_smoke`)
- Prompt-layer skills (Codex/Claude CN/EN)

### Foundation (2026-02-13)

- Skill sync scripts (`sync-skills.sh`, `check-skills-sync.sh`)
- Sub-skill `workflow-learning` for replay/review (sunset in P3b)
- User preference layer (`preferences.md`, `feedback.jsonl`)
- Config: `workflow.learning.auto_capture` (sunset in P3b)
- Title color behavior, branding semantics clarification

### Initial Release (2026-01-15)

- Initial version (ruleset and skill structure).
