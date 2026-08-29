---
title: Cursor Agent CLI 顶层入口与一次安装产品化
plan_id: 20260828_cursor_agent_cli_entry
status: done
lifecycle_state: ready_to_archive
level: standard
created: 2026-08-28
updated: 2026-08-29
archive_ready: true
---

# Cursor Agent CLI 顶层入口与一次安装产品化

就绪状态: Ready
依据: 用户已确认 managed-first 口径，并授权先优化本机 CLI 顶层 Skill、安装最新版、经 Cursor 独立审计后，再纳入现有 Cursor 一次安装产品链；不新增 launcher、项目 Rule、runtime 或独立 CLI target。

## Context / Why

Cursor IDE 已通过用户级 Always Plugin Rule 获得 Sopify 顶层协议。2026-08-28 的本机实验进一步证明 `agent` CLI 可以发现 `~/.cursor/skills/sopify/SKILL.md`，并通过该薄入口读取已安装 Plugin Rule、路由五个阶段 Skill。

受控实验不等于稳定产品能力。安装后的三个真实用户会话中，顶层 Skill 只自动命中一次；命中会话还出现了入口 Skill 与业务素材并行读取，以及 quick-fix 从默认应用修改扩展到缓存删除和 Helper App 持久化、未重新停车的问题。当前顶层 Skill 只有用户目录单份副本，仓库安装源、升级保护、Doctor、双语文档与产品声明均未纳入；重新运行现有 Cursor 安装会删除这份本机入口。

## Scope

- 第一层：按真实使用证据优化本机中文 CLI 顶层 Skill，清理旧副本并安装唯一最新版；保持入口短小、结构清晰、语言通顺。
- 第一层验证：校验 Skill 结构与安装哈希，完成 managed 请求前向测试，然后交给 Cursor 在独立标签审计；不认可则按审计结论做最小修正并复验。
- 第二层：将中英文 CLI 顶层 Skill 纳入 canonical source，使现有 `cursor:zh-CN` / `cursor:en-US` 一次安装默认同时覆盖 IDE 与本地 Agent CLI。
- 第二层验证：补安装完整性、升级/重装、Doctor、IDE 回归和 CLI managed 流程证据；实现完成后再次交给 Cursor 独立审计。
- 同步受影响的 Cursor 接入文档、双语产品说明、Changelog 与稳定 blueprint 事实；保持支持档位和未验证边界准确。

## Approach

保留“薄 CLI 入口 → 读取已安装 Plugin Rule → 路由现有阶段 Skills”的结构。顶层 Skill 的 description 从“任何软件请求”收窄为 managed-first 高信号触发，突出 `.sopify`、`~go`、分析/设计/开发、继续/接续/恢复和 finalize/收口；普通咨询不强制触发，也不据此声称已进入 Sopify。

Plugin Rule 只补一个共享边界：当已授权动作扩展为新的用户级或系统级持久化、删除操作时重新停车确认。产品化复用现有 Cursor 用户级安装与 `copytree`，把顶层 Skill 加入 canonical 双语源和安装必需路径，不增加新 target、安装参数、能力枚举或运行时组件。

## Waves / Steps

- [x] W1：完成本机中文顶层 Skill 受控实验，并保存旧版本 receipts。
- [x] W2：根据近期真实会话优化本机 Skill，安装唯一最新版并完成 Cursor 独立审计。
- [x] W3：把中英文入口纳入一次安装、Doctor/测试和用户文档，保持 IDE/CLI 证据分离。
- [x] W4：执行目标测试、全量回归、CLI managed 前向观察和第二次 Cursor 独立审计；IDE/CLI 行为证据继续分开。
- [x] W5：按验证结论同步稳定知识并更新为 `ready_to_archive`；不自动 finalize、commit、push 或发布。

## Key Decisions

- 采用 managed-first：只保证 Sopify/managed 请求的顶层入口，大部分相关场景应自然触发；普通咨询不强制。
- 用户仍只运行一次 `--target cursor:<language>`；IDE 与本地 CLI 共用阶段 Skills、payload 与 Hooks，但入口机制和行为证据分开声明。
- 本机 Skill 与产品源使用同一正文，不保留旧版、兼容副本或额外路由文件。
- 自动 Skill 选择按 best-effort 声明；安装存在、用户已读已用和模型自述均不单独证明稳定行为。
- Cursor 保持 `BASELINE_SUPPORTED`；Cloud Agent、跨模型一致性和 `PROTOCOL_VERIFIED` 升级不在本轮承诺内。

## Constraints / Not-in-scope

- 不新增 `cursor-cli` target、`--with-cursor-cli`、launcher、项目 `.cursor/rules`、`AGENTS.md`、Custom Mode、MCP 或 runtime。
- 不修改 Cursor settings、CLI config、代理、模型、账号、API Key、钥匙串或 Cloud Agent。
- 不重构五项阶段 Skill、writer、state schema、Hook 体系或 HostCapability 架构。
- 不把通用问答未命中视为失败；只对 managed 触发、读取顺序、协议消费和副作用边界做验收。
- 不保存含敏感内容的完整 transcript；正式证据记录 session id、受限 tool trace 摘要、用户观察和 digest。

knowledge_sync:
  project: skip
  background: skip
  design: required
  tasks: skip

## Status / Progress

- [x] 本机旧 Skill、受控 receipts、真实会话命中率和现有安装覆盖行为已完成批判审计。
- [x] 用户确认 managed-first、一次安装默认支持 IDE + CLI、不过度设计，并要求两阶段均经 Cursor 独立审计。
- [x] 第一层本机 Skill 优化与审计：当前唯一 Skill SHA-256 为 `d892a90fdb7c455367d870e5b47f454a422d578109919d93c9a68eb5fd0beee9`；Cursor 首审不认可读取顺序只在正文，修正 description 后复审认可。
- [x] 第二层产品化实现：中英文顶层 Skill、一次安装内容校验、旧入口清理、Doctor 必需路径、共享 Rule 边界和用户文档已完成；目标测试与全量 `312 passed / 78 subtests` 通过。
- [x] 跨宿主污染审计与修正：Cursor 首审不认可专用入口进入共享 Skill 树；现已改为 host-specific 双语模板，补 Codex/Claude/Qoder 负向测试并恢复 shared-tree golden。
- [x] 第二层 Cursor 最终复审认可，无待修项；最终全量回归为 `313 passed / 81 subtests`。
- [x] 用户已授权在 `feat/cursor-agent-cli-entry` 本地 commit 并 push 同名 feat 分支；不包含 finalize、合并或发布。

## Next

实现与独立审计均已完成。按用户授权将当前结果 commit 并 push 到 `feat/cursor-agent-cli-entry`；只有显式 `~go finalize` 才归档，合并与发布继续需要单独授权。
