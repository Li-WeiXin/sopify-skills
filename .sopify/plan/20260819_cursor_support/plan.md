---
title: Sopify Cursor 宿主支持
plan_id: 20260819_cursor_support
status: in_progress
lifecycle_state: active
level: standard
created: 2026-08-19
updated: 2026-08-19
archive_ready: false
knowledge_sync:
  project: review
  background: review
  design: required
  tasks: review
---

# Sopify Cursor 宿主支持

## Plan Snapshot

- **Goal**: 在保留 Sopify 多宿主内核的前提下，为本地 Cursor IDE 与 Cursor Agent CLI 增加正式、可安装、可检查的宿主适配，并用用户级 Hooks 保护 machine truth。
- **Status**: Cursor adapter、用户级 Hook 与审计修正已落地；`python3 -m pytest tests -q` 为 307 passed / 76 subtests。第二次独立 Cursor 复审确认安装文案和多根 `sessionStart` 原问题关闭，并发现 receipt 紧贴重定向仍放行；该 P2 已用单一正则边界修复，真实 CLI session `3a13cbf2-d184-488e-9331-25e7a7510365` 返回 `tool_call completed / result.rejected`，receipt 与 state 哈希未变。consult 语义路由不干净、Analyze 未实际执行评分脚本；IDE 未验。本文件随用户授权的本地 commit 交付，未推送、未归档。
- **Next**: 在原目录交独立 Cursor 会话复核 receipt 紧贴重定向修复；IDE、consult 语义与 Analyze 缺口继续明确保留，不 push、不升级档位。
- **Task**: 见 `tasks.md`。

就绪状态: Ready to continue
依据: 用户确认最小分层，并把 Hook 从项目级改到用户级 `~/.cursor/hooks.json`；同时要求先修 doctor 缺席、EvidentLoop fail closed、禁止自动 bootstrap、可移植规则路径和文档口径。

## Context / Why

用户选择继续维护 Sopify 多宿主协议层，把 Cursor 作为新 host，不创建 Cursor 专用 fork。Cursor 需要项目级 `.cursor/rules/*.mdc` 薄规则、用户级 `~/.cursor/skills/sopify/` Skills 树、`~/.cursor/sopify/` payload，以及用户级 Hooks。

独立审计确认：规则和 Skill 只能指导 Agent，不能证明协议执行。官方 Cursor Hooks 可在工具边界做确定性保护，但不能替代自然语言意图、Analyze 评分和证据判断。首发只支持本地 IDE + Agent CLI，明确排除 Cloud。

## Scope

- 新增 Cursor host registration 与独立 `project_rules` instruction surface；现有四个 host 安装行为不变。
- 项目规则：`<workspace>/.cursor/rules/sopify.mdc`，合法 `.mdc` frontmatter，`alwaysApply: true`。规则中的 Skill 路径使用可移植的 `~/.cursor/skills/sopify`，不嵌入个人机器绝对路径。
- 全局五项 Skill 与 `shared-writing-dna.md` 安装到 `~/.cursor/skills/sopify/`；payload 安装到 `~/.cursor/sopify/`。
- 用户级 `~/.cursor/hooks.json` 只合并 Sopify 自有 `sessionStart`、`preToolUse`、`beforeShellExecution`；保留已有合法配置；非法 JSON 时停止，不覆盖。不写仓库级 `.cursor/hooks.json`，不增加项目 trampoline。
- Hook helper 放在全局 payload。仅当 workspace 存在 `.cursor/rules/sopify.mdc` 时启用 Sopify 行为；其他 workspace no-op。helper 缺失或异常 fail-open，由 Doctor 报错，不阻塞 Cursor 会话。
- `--workspace` 只用于项目规则落点，不自动 bootstrap `.sopify`。
- `--with-evidentloop` 对 Cursor fail closed：`skills_cli_agent=None`。
- Doctor 缺席只检查 Sopify 自有落点，不能把整个 `~/.cursor` 当成已安装。指定 workspace 时，`status.installed` 同时要求项目规则和全局 Skill 树。
- 安装与测试必须证明不修改 Cursor `settings.json`、代理、模型、账号、API Key、钥匙串或 MCP。
- Capability 保持 `BASELINE_SUPPORTED`。Hook 落地后 `entry_modes` 可含 `HOOKS`，但 IDE/CLI 行为仍为 `BLACK_BOX_NOT_VERIFIED`。

## Approach

- `project_rules` 保持最窄 surface；Cursor 走“项目规则 + 全局 Skills + 用户级 Hooks + payload”。
- Helper 消费 Cursor stdin JSON，只输出官方 hook JSON；不保存第二份状态，不分类自然语言，不执行任务。
- `sessionStart` 注入紧凑事实快照，并写明非恢复条款。
- `preToolUse` 不使用过窄 matcher；按 `tool_name` 与 `tool_input` 路径识别直接修改受保护 machine-truth 文件。
- Shell 只用 `beforeShellExecution` 拒绝明显直接改写；`sopify_writer` 库 API 调用放行。不宣称这是不可绕过的安全沙箱。
- 不扩建 MCP，不新增 orchestrator、plugin、runtime 或 `/go`。

## Waves / Steps

1. 用 `sopify_writer` 消费 decision，并把用户修正同步进 `plan.md` / `tasks.md`。
2. 修复 baseline 审计 finding：doctor 缺席、EvidentLoop、bootstrap、installed 合取、smoke、可移植路径、文档。
3. 实现用户级 Hook 合并与 payload helper，补 doctor 与自动化。
4. 跑定向与全量测试；分别记录 IDE/CLI 黑盒。模型自述不计证据，部分通过不外推完整通过。
5. 不 commit、不 push、不升级支持档位。

## Key Decisions

- Cursor 是第五个 host，不创建专用 fork。
- 方案级别为 standard，只维护 `plan.md + tasks.md`。
- 最小分层：Hooks 负责可确定的 session 状态注入和 machine-truth 副作用保护；Rule/Skill 负责自然语言意图、Analyze 评分、证据核验和设计判断。
- Hook 落点是用户级 `~/.cursor/hooks.json`，不是仓库级 `.cursor/hooks.json`。理由：首发排除 Cloud；用户级 Hook 可直接调用 `~/.cursor/sopify/`；避免影响未安装 Sopify 的同事。
- 只在 workspace 存在 `.cursor/rules/sopify.mdc` 时启用 Sopify Hook 行为。
- helper 缺失或异常 fail-open；这是应用层防误写 guard，不是安全沙箱。
- `sessionStart` 必须包含：“这是状态事实，不是恢复命令；先按本轮用户意图分类。consult_readonly 和 quick_fix 不自动接续 active plan。”
- 受保护路径仅限 `active_plan.json`、`current_handoff.json` 和 `plan/*/receipts/*.json`。不拦截 `plan.md` / `tasks.md` / `design.md`。
- Cursor 首发 `BASELINE_SUPPORTED`。未完成 IDE + CLI 黑盒前不声明 `PROTOCOL_VERIFIED`。
- 显式 `--with-evidentloop` 不纳入 Cursor 首发。
- 当前分支 `feat/cursor-support`，基线 `2c2c13f3f8fd94f05fb3e3789bd2e20755e27863`。

## Constraints / Not-in-scope

- 不新增 MCP tool、writer CLI、orchestrator、plugin、runtime、项目 trampoline 或第二套工作流。
- 不用关键词正则或额外模型在 hook 中分类自然语言。
- 不把 Cloud Agent、团队规则或 EvidentLoop 配套安装纳入默认首发。
- 不把模型自述当成黑盒通过。CLI 使用现有登录和代理环境，不修改 Keychain 或代理配置。
- 未获授权不 commit / push，不升级支持档位。

## Status / Progress

- [x] 分支 `feat/cursor-support` 已从基线 `2c2c13f` 创建。
- [x] Cursor adapter、`project_rules` surface、双语薄规则、全局 Skills/payload 与诚实 doctor baseline 已落地。
- [x] 用户以“接受但修改”消费应用层边界 decision。
- [x] 实施 baseline 审计修正与用户级 Hook；自动化 307 passed。
- [x] 两次独立 Cursor 复审均未发现 P0/P1；安装文案、多根 `sessionStart` 原问题已关闭，第二次复审重开的 receipt 紧贴重定向 P2 已最小修复。
- [x] 真实 CLI 已证明项目 Rule/全局 Skill 可见、consult 零 machine-truth 写入、sessionStart 注入、文件工具 deny 与 Shell deny；state 与 receipt 的无空格重定向均收到工具层拒绝。
- [!] CLI consult 仍读取 Develop Skill/payload，不能判定语义路由完全符合 `consult_readonly`。
- [!] CLI Analyze 已读 Cursor Skill 与评分脚本，但没有实际调用脚本，不能判通过。
- [ ] Cursor IDE 黑盒仍为 `BLACK_BOX_NOT_VERIFIED`。
- [x] 已生成 `audits/implementation_review.md` 独立复审包。
- [x] 用户已授权本地 commit、原目录切换到 `feat/cursor-support` 并删除临时 worktree。
- [ ] Push 未授权；不得推送。

## Next

在原目录等待独立 Cursor 复核 receipt 紧贴重定向修复。IDE、consult 语义与 Analyze 评分门继续作为证据缺口；只有未来要求把 Analyze 评分做成跨宿主确定性能力时，才需要另行决定是否调整共享规范。保持 `BASELINE_SUPPORTED`，不 push。
