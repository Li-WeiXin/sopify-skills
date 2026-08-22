---
title: Sopify Cursor 宿主支持
plan_id: 20260819_cursor_support
status: completed
lifecycle_state: ready_to_archive
level: standard
created: 2026-08-19
updated: 2026-08-22
archive_ready: true
knowledge_sync:
  project: review
  background: review
  design: required
  tasks: review
---

# Sopify Cursor 宿主支持

就绪状态: Ready to archive
依据: User Rule `sopify` 已显示为 Always Apply；consult、Analyze 评分门、AskQuestion tool use 与文本回退、Analyze → Design → Develop、writer 写回及 Hook direct-write deny 均有可观察 IDE 证据。最终独立复审返回 `accept`；未单独验证的 sessionStart、显式 finalize 与 AskQuestion 跨模型稳定性只作为后续边界，不阻塞本次 baseline 收口。

## Context / Why

当前 `feat/cursor-support` 已将第五个 host 从每仓项目 Rule 修正为 IDE 用户 Plugin、全局五项 Skills/payload 与用户级 Hooks。安装面、Rule 路由、consult、Analyze 评分、AskQuestion 能力路径、managed develop、writer 写回与 Hook direct-write 证据已闭环；最终独立复审已接受候选，支持档位保持 `BASELINE_SUPPORTED`。Doctor 的行为项继续静态报告 `BLACK_BOX_NOT_VERIFIED`，不把本机临时证据写成可移植产品认证。

用户主要在包含多个独立 Git 仓库的工作区中使用 Cursor，希望 Sopify 成为安装一次即可跨仓库工作的默认语义入口，自动区分 consult、quick fix 与 managed workflow，并按当前仓库的 `.sopify/`、项目规则和知识文档进入现有 Skills。每个仓库单独安装项目 `.mdc` 会增加迁移成本，也无法证明模型实际执行协议。

Cursor 官方允许用户范围安装 Cursor Plugin，Plugin 可包含 `rules/*.mdc`，`alwaysApply: true` 的 Rule 可作为 IDE 默认上下文；官方 CLI 文档仍只明确列出项目 `.cursor/rules`、`AGENTS.md` 与 `CLAUDE.md`。真实 CLI 也未自动加载用户 Plugin Rule，因此本期将 IDE 作为自动入口，CLI 作为手工 Skill 兼容面。

## Scope

- 保留 Sopify 多宿主内核与 `cursor` host，不创建 Cursor fork；现有 Codex、Claude、Qoder、Copilot 行为保持不变。
- Cursor IDE 改为用户级 Cursor Plugin：安装到 `~/.cursor/plugins/local/sopify/`，包含 `.cursor-plugin/plugin.json` 与一个极薄的 `rules/sopify.mdc`，作为 IDE 唯一 Sopify 语义入口。
- Agent CLI 不承诺自动加载 Plugin Rule；低频使用时手工调用已安装的 `/analyze`、`/design`、`/develop` 等 Skill，用户 Hooks 继续提供其实际加载范围内的写保护。
- IDE Plugin Rule 负责意图分类与 Skill 路由；Analyze 需要有限选项澄清时，当前会话提供内建 AskQuestion 就优先调用并使用问卷自带自由输入，否则回退文本。问卷不成为 Sopify machine truth，也不授权提前进入 Design/Develop。
- Cursor 不再要求 `--workspace`，不再安装或检查项目 `.cursor/rules/sopify.mdc`；当前双语项目 Rule 的有效内容迁入全局薄 Rule 后删除项目 Rule 模板与本仓库临时规则。
- 同一次 Sopify 安装继续管理 `~/.cursor/skills/sopify/`、`~/.cursor/sopify/` 与 `~/.cursor/hooks.json`。Plugin 不维护 Cursor 私有 Skills 副本，也不复制 Hook 配置或 helper。
- 复用现有 `sessionStart`、`preToolUse`、`beforeShellExecution` Hooks。Hook 不再以项目 `.mdc` 为开关，改为按本次事件的目标路径、`cwd` 与 `workspace_roots` 识别由 `.sopify/` 管理的仓库。
- 文件工具按目标路径选择所属 managed root；Shell 按 `cwd` 选择；`sessionStart` 只有在唯一 managed root 且 active plan 语义有效时才注入事实，多根不唯一或状态无效时 no-op。
- `preToolUse` 与 `beforeShellExecution` 继续只拒绝对 `active_plan.json`、`current_handoff.json`、`plan/*/receipts/*.json` 的明显直接写入；`plan.md`、`tasks.md`、`design.md` 与业务代码不在保护范围，`sopify_writer` 库 API 继续放行。
- Doctor 分开报告 Plugin/Rule、全局 Skill 树、payload、用户级 Hooks 的安装事实，以及 IDE/CLI 的行为证据；安装事实不得冒充宿主遵守协议。
- 同步 installer、registry/capability、CLI 安装文案、README、Cursor 专项文档、长期 blueprint 与相关自动化测试。

## Approach

- 只增加 Cursor-specific 的用户 Plugin 安装能力，不抽象通用 Plugin 框架。Plugin 资产由仓库内单一模板/manifest 生成，五项 Skills 与共享 references 继续来自现有权威源码。
- IDE 薄 Rule 只保留路由与边界：先分类本轮意图；consult 不续旧 plan；quick fix 不写 protocol machine truth；Analyze 必须实际评分，有限选项澄清按当前会话能力优先调用非 MCP 的内建 AskQuestion；machine truth 只经 `sopify_writer`。不新增问卷状态、tool wrapper 或手工“其他”选项。
- 不给阶段 Skills 增加 `disable-model-invocation: true`。该字段会把 Skills 变成手工调用，与自然语言默认路由目标冲突；阶段语义继续由薄 Rule 的精确路径读取约束和黑盒证据验证。
- `.sopify/` 只作为 Hook 写保护的 managed-root 信号，不作为可恢复方案事实。`sessionStart` 仍须验证 active plan 指针、对应 `plan.md` 与匹配 handoff；不能仅凭目录存在注入恢复上下文。
- 保持 Hook fail-open：helper 缺失或异常不阻塞 Cursor，由 Doctor 报错。Hook 是应用层防误写 guard，不是安全沙箱，不新增完整 Shell parser。
- 先在隔离 home 验证 Plugin Rule、Skills、payload、Hooks 与 settings 不变，再安装到真实 `~/.cursor`，以 IDE 作为本期唯一自动入口黑盒。
- CLI 自动 Plugin Rule 与显式 `--plugin-dir` 的失败证据作为已知边界保留，不再作为发布否决门；不长期保留双入口，也不把手工 Skill 使用写成自动路由。

## Waves / Steps

1. 把 Cursor adapter 从 `project_rules` 调整为用户 Plugin 安装面，增加最小 Plugin manifest/Rule 资产并移除 workspace 依赖。
2. 调整 installer、distribution、Doctor/status 与缺席判定，保证一次安装完成 Plugin、Skills、payload、Hooks，且不修改 Cursor settings、代理或账号相关文件。
3. 复用现有 Hook helper，替换项目 Rule 启用条件，补目标路径、Shell cwd、唯一 session workspace 与有效事实注入测试。
4. 删除项目 Rule 产品路径，更新 capability、双语文案、README、Cursor 文档、blueprint 与自动化。
5. 运行定向和全量回归；保留 CLI 自动入口失败证据，随后执行真实 IDE 黑盒和独立 Cursor 复审。所有行为结论以工具轨迹和文件结果为证据。

## Key Decisions

- 继续使用当前分支 `feat/cursor-support` 与当前 active plan `20260819_cursor_support`；这是同一宿主功能的架构修正，不另建分支或方案包。
- Cursor IDE 的唯一 Sopify 语义入口是用户级 Plugin 中的薄 Always Rule；项目 `.cursor/rules/sopify.mdc` 不保留为默认或可选第二入口。
- Plugin 只承载 manifest 与薄 Rule。现有全局 Skills、shared references、payload 与用户级 Hooks 由同一个安装器管理，只有一份维护源和一个安装生命周期。
- 项目 `AGENTS.md`、`CLAUDE.md`、已有 `.cursor/rules` 与 `.sopify/` 是当前仓库事实，不是第二套 Sopify 入口。真实冲突按 Cursor 规则优先级处理，writer/Hook 边界不依赖模型服从。
- Hook 使用 `.sopify/` managed-root 信号，但按事件选择目标：文件工具看目标路径、Shell 看 `cwd`、sessionStart 只接受唯一有效 workspace；不新增通用 Git-root resolver。
- 不设置 `disable-model-invocation: true`，不把 Plugin 的正常构建/安装产物误判为第二套协议源码。
- 支持档位本波继续为 `BASELINE_SUPPORTED`。Plugin 已安装、Rule 显示 Always、Skill 可发现或模型自述均不能自动升级；`PROTOCOL_VERIFIED` 不在本波承诺范围。
- CLI 自动入口明确不支持；手工 Skill 是低频兼容路径。当前分支不增加 launcher、prompt injector 或第二套 Rule。

## Constraints / Not-in-scope

- 不做 Marketplace 发布、Team Plugin、Cloud Agent、workspaceOpen 动态加载或 data-sprite 专用 manifest。
- 不新增 `/sopify` dispatcher、Custom Agent、Command、`/go`、MCP、orchestrator、runtime 或 writer CLI。
- 不新增 Plugin 自有 Hooks，不把五项 Skills 手工复制成 Cursor 私有维护树，不建立项目 `.mdc` 兼容探测层。
- 不修改 Cursor `settings.json`、代理、模型、账号、API Key、钥匙串或 MCP 配置；现有 `127.0.0.1:7898` 环境不受影响。
- 不把文件存在、Customize 列表、Rule 为 Always、Skill discovery 或模型自述当成行为通过。
- 不覆盖已有 `exec_001`、`exec_002`、`verify_001`、`verify_002`、`verify_003` 或独立审计；新实施和验证追加新 receipt。
- 本轮只完成本地 feature commit；push、release 与显式 finalize 仍需用户另行授权。

## Status / Progress

- [x] 原 Cursor adapter、用户级 Hooks 与 baseline 修正已提交为 `d0e81f1`；既有自动化为 307 passed / 76 subtests。
- [x] 用户确认采用“全局 Plugin 唯一薄入口 + 现有 Skills/payload/Hooks”的产品方向，并确认不新增 Hooks 框架。
- [x] 完成独立 Cursor 审计的二次裁决：接受证据门与分层，驳回 `sopify.json` 唯一标记、`disable-model-invocation: true`、禁止 Plugin 正常复用权威资产三项过度修正。
- [x] 2026-08-20 复核 Cursor 官方 Plugin、Rules、Hooks 与 CLI 文档，并把 CLI 未自动加载 Plugin Rule 的事实固化为支持边界。
- [x] 当前 standard 方案与任务清单已按新决策收口，Ready to implement。
- [x] 实施用户级 Plugin 安装面、Hook managed-root 启用、Doctor 与文档调整。
- [x] 完成定向与全量自动化，保持其他 host 行为不变：308 passed / 78 subtests，compileall 与 `git diff --check` 通过。
- [x] 唯一一轮 Cursor 独立复审已返回；批判裁决接受安装结构与 Hook D，关闭其沙箱 pytest 与代理快照误判，保留 IDE A/B/C 行为缺口。
- [x] 按官方本地 Plugin 流程补充 Reload/Restart 安装提示与测试，重新本地安装；settings、CLI config、hooks 与系统代理哈希均未变化。
- [x] 根据真实 Customize 空白详情页补充最薄双语 Plugin README；只介绍用途、工作方式与支持边界，不复制 Rule 或协议正文。真实 Reload 证明 Local 详情页不渲染 manifest description 或 README，用户已接受该宿主限制；README 保留为包内/发布文档，但不作为 Doctor 或 installed 健康硬门槛。
- [-] CLI 自动入口验收已按产品决策关闭：2026-08-20 session `4c24eab4-dd82-46f3-8fd7-67888baa1a53` 反证自动 Plugin 入口未加载；显式 `--plugin-dir` session `7626c137-9668-450f-ab00-a44619f90f9c` 与唯一标记探针 `109d2991-78e6-46d8-a19a-5bd86f3198f0` 同样未加载 Rule。三份 machine truth 哈希均未变化。用户接受 CLI 低频手工 Skill 路径，因此不实施 launcher。
- [x] 批判核验 Plugin 自动入口失败：包加载成功但 Plugin `ruleCount: 0`；“会遵循 Plugin”的回答前主动 Glob/Read 本地 Rule，不计注入证据。完成单变量 manifest 自动发现修复、22 tests / 2 subtests 定向验证、308 tests / 78 subtests 全量回归、compileall、diff check 与真实重装，受保护配置哈希未变。
- [x] Reload 后 UI 显示 User Rule `sopify`，真实文件名为 `sopify.mdc`、模式为 Always Apply；Cursor Plugin 服务在 sopify、data-sprite 等窗口均报告 `ruleCount: 1`，目录自动发现修复成立。
- [x] IDE consult 会话 `067ce461-c667-46fb-88ce-bffe4c4362a1` 只读取 Cursor shared-writing-dna 并执行只读 Git 查询；分支和 23 个 tracked / 6 个 untracked 变更与现场一致，未加载阶段 Skill、未续跑 active plan、未写 machine truth。
- [x] IDE Analyze 会话 `7101b90b-ce5d-4acb-8fc3-930056f95e68` 读取 Cursor Analyze Skill、必要规则与输出契约，并实际运行 `score_requirement.py` 得到 `3/10, pass=false`；随后只追问，不进入 Design、不创建 plan/state/receipt。
- [x] 真实 Cursor 安装原位切换为 `cursor:zh-CN`；Plugin 与 Skill 根各只有一份，英文 `Requirements Analysis` 模板无残留，hooks / CLI config 哈希及系统代理不变，settings 仍不存在。全量回归为 308 passed / 78 subtests，compileall 与 `git diff --check` 通过。
- [x] 最薄 AskQuestion 扩展仅修改双语 Cursor Plugin Rule 与既有静态契约测试：有限选项按当前会话能力优先使用内建 AskQuestion，不经 MCP 探测，使用问卷自带自由输入并保留文本回退。会话 `84e9fa01-c2dc-4db5-9611-0f15c120bcb8` 同时保留了工具不可用与后续未再报 `Tool not found` 的 AskQuestion tool use，证明能力路径存在但不承诺跨模型稳定或选项回传。
- [x] 临时仓库 `/private/tmp/sopify-cursor-managed-blackbox.WRxVtd` 完成真实 IDE managed 主链：首轮评分 `10/10`、选择 light、创建 plan 并经 writer 写 active plan/handoff 后停车；用户确认后修改唯一业务文件，经 writer 追加 `exec_001`、`verify_001` 与 handoff，方案保持 `ready_to_archive` 且未 finalize/commit。随后 Shell 直写 `active_plan.json` 被 Hook 拒绝，前后哈希一致。完整轨迹为 session `2448476f-57b8-4e1d-a522-c19e8202d658`。
- [x] 2026-08-22 最终 Cursor 只读独立复审返回 `accept`：P0/P1 无；三个 P2 分别以真实安装对齐、AskQuestion 证据降级和 UI/文件证据分层关闭。
- [x] README 宿主 badge、架构图与中英文产品形态 SVG 已同步 Cursor；仅修改全量宿主矩阵，封面、demo 与跨宿主场景图保持具体示例，不为凑齐宿主重绘。
- [x] 独立视觉/文档复审最终返回 `accept`，P0/P1/P2 均无；其发现的 Cursor 验证断点、badge 导航和顶部跨宿主口径已做最小修正，未新增入口或机制。
- [x] 最终候选回归通过：308 passed / 78 subtests，Python compileall、`bash -n install.sh`、SVG XML、视觉渲染与 `git diff --check` 均通过；真实 `cursor:zh-CN` 安装与候选逐字对齐，受保护配置及系统代理前后不变。

## Next

本方案保持 `ready_to_archive`；显式归档留给后续 `~go finalize`。本轮不 push、不 release。
