# 任务清单: Sopify Cursor 宿主支持

目录: `.sopify/plan/20260819_cursor_support/`

## 1. 用户级 Plugin 入口

- [x] 1.1 将 Cursor adapter 从项目 Rule 安装面调整为 Cursor-specific 用户 Plugin 安装面；移除 `--workspace` 必需条件，不影响其他 host 的 instruction surface。
  - 产物：Cursor registration/capability 与最小安装路径。
  - 验收：`--target cursor` 在未传 workspace 时可安装；Codex、Claude、Qoder、Copilot adapter 测试不变。
- [x] 1.2 增加 `.cursor-plugin/plugin.json`、渐进式双语 `README.md` 与单一 `rules/sopify.mdc` 资产，由现有双语权威内容生成/安装到 `~/.cursor/plugins/local/sopify/`。
  - 产物：用户级 Plugin manifest、用户可见简介与薄 Always Rule。
  - 验收：Rule 有合法 frontmatter、意图分类、精确 Skill 路由、Analyze 评分门、按当前会话能力使用 AskQuestion 并安全回退、四步入口和 writer-only 边界；Plugin 不含 Commands、Agents、MCP、Hooks 或私有 Skills 树。
- [x] 1.3 删除项目 `.cursor/rules/sopify.mdc` 的产品安装路径、双语项目 Rule 模板及本仓库临时规则；不建立 fallback 或兼容探测层。
  - 依赖：1.2 的隔离安装测试完成；最终删除受 5.2 CLI 发布门约束。
  - 验收：新安装不会写目标仓库 `.cursor/`；仓库不需要逐个安装 Sopify Rule。

## 2. 安装、状态与 Doctor

- [x] 2.1 调整 Cursor 安装流程：先预检已有 `~/.cursor/hooks.json`，再以同一次安装写 Plugin、全局五项 Skills/shared references、payload/helper 与用户级 Hooks。
  - 验收：非法 hooks JSON 时在首次产品写入前停止且原文件不变；重复安装幂等；不修改 `settings.json`、代理、模型、账号、API Key、钥匙串或 MCP。
- [x] 2.2 将 Cursor 安装结果、CLI help、distribution 文案从“项目规则落点”改为“用户级 Plugin + 全局资产”；移除 Cursor 的 workspace/bootstrap 暗示。
  - 验收：中英文输出只声明文件安装事实，先提示 Reload/Restart，再提示在 Cursor Customize 中确认 Rule 为 Always；不声称 IDE/CLI 已执行。
- [x] 2.3 将 Doctor/status 的 `project_rule_present` 改为 Cursor Plugin/Rule 安装检查，并继续独立检查 Skill 树、payload、Hooks、IDE/CLI behavior。
  - 验收：仅有 Cursor IDE settings 时 host 为 absent/skip；缺 Plugin Rule、Skill、payload 或 Hooks 时准确失败；行为项仍为 `BLACK_BOX_NOT_VERIFIED`，不因安装完整自动通过。

## 3. 复用用户级 Hooks

- [x] 3.1 移除 Hook helper 对项目 `.cursor/rules/sopify.mdc` 的依赖；按事件选择 `.sopify/` managed root：文件工具看目标路径，Shell 看 `cwd`，sessionStart 看唯一候选 workspace。
  - 验收：无 `.sopify/` 的普通仓库 no-op；父目录包含多个 Git 仓时不默认取第一个；目标明确落在某个子仓时只保护该仓。
- [x] 3.2 保持 sessionStart 非恢复语义，只有 active plan 指针、对应语义文件和匹配 handoff 有效时才注入事实；目录存在、残留 state 或多根歧义均不注入方案动作。
  - 验收：consult 不因快照自动 continue；handoff plan_id 不匹配时 action 为 none；latest receipt 仍按协议 timestamp/fallback 选择。
- [x] 3.3 保持现有 `preToolUse` 与 `beforeShellExecution` 最小写保护、`sopify_writer` 放行和 fail-open 行为，不新增 Hook 类型或完整 Shell parser。
  - 验收：Write/StrReplace 与明显 Shell 重定向不能直写 state/handoff/receipt；`plan.md` 与正常 writer API 调用放行；helper 异常由 Doctor 报告但不阻塞 Cursor。

## 4. 契约、文档与回归

- [x] 4.1 更新 Cursor capability、registry/catalog、README、`docs/cursor-host.md`、install.sh/install.ps1 帮助和 distribution 文案，统一描述“用户级 Plugin 唯一语义入口 + 全局 Skills/payload + 用户 Hooks”。
  - 验收：不再出现每仓安装项目 Rule、Plugin 已等价覆盖 CLI、文件存在等于行为通过等过强口径。
  - 视觉同步：README 顶部 badge、架构图和中英文产品形态图已加入 Cursor baseline；具体场景图保持示例语义，不扩写为宿主矩阵。
  - 独立视觉/文档复审：修复 Cursor 用户级安装后的 Verify Setup 断点、badge 导航和顶部跨宿主过强口径后返回 `accept`；P0/P1/P2 均无。
- [x] 4.2 同步 `.sopify/blueprint/` 中受影响的宿主架构与任务索引，不扩写与 Cursor 无关的协议内容。
  - 验收：长期文档与本方案在入口、Hook 边界、支持档位和证据门上无冲突。
- [x] 4.3 补 installer、distribution、Doctor、Plugin 资产与 Hook root-selection 测试，并重跑相关定向测试和全量 `python3 -m pytest tests -q`。
  - 验收：全量通过，`git diff --check` 与 Python compile 检查通过；其他四个 host 的安装快照与行为不变。

## 5. 黑盒与交付

- [x] 5.1 在隔离 home 安装 Cursor，证明 Plugin manifest/Rule、Skills、payload、helper、Hooks 路径正确，目标仓库没有 `.cursor/rules/sopify.mdc`，Cursor settings 与代理相关文件哈希不变。
- [-] 5.2 在不含项目 `.mdc` 的临时仓库运行真实 Cursor Agent CLI 自动入口验收。
  - 原自动入口判据：观察全局 Plugin 是否生效，以及 consult、Analyze 与 Hooks 的工具轨迹和文件哈希；该能力现已明确不在产品承诺内。
  - 2026-08-20 自动入口实测失败：session `4c24eab4-dd82-46f3-8fd7-67888baa1a53` 未加载用户 Plugin Rule，实际读取 `~/.claude/skills/sopify/kb/SKILL.md` 并在 consult 中读取 active plan/handoff/receipt；三份 machine truth 哈希未变。
  - 2026-08-20 纯 launcher 前置门失败：显式 `--plugin-dir ~/.cursor/plugins/local/sopify` 的 session `7626c137-9668-450f-ab00-a44619f90f9c` 未读取 Cursor shared-writing-dna，仍读取旧 `~/.claude/skills/sopify/develop/SKILL.md` 与 managed plan/state；唯一标记 Cursor Plugin 探针 session `109d2991-78e6-46d8-a19a-5bd86f3198f0` 未读取 marker 且直接回复 `OK`。依据“验证后实施”决策，不增加无效 launcher。
  - 产品收口：用户接受 IDE/CLI 能力不对称；CLI 低频使用时手工调用已安装 Skill，不承诺自动 Plugin Rule，本自动入口任务按范围取消。
- [x] 5.3 经用户授权安装到真实 `~/.cursor`，在 Cursor IDE 单独验证 Customize 中 Rule 为 Always、consult/analyze 路由与 direct-write deny；CLI 证据不得外推 IDE。
  - 真实安装与 2026-08-20 重装已完成；settings、CLI config、hooks 与代理哈希安装前后不变。Plugin 可见已通过；Local 详情页不渲染 description/README 的宿主限制已由用户接受，不再作为行为门。
  - 2026-08-20 首轮 Rule 复验失败：Customize Rules 为空，日志显示 Plugin `ruleCount: 0`，相关回答由 Agent 主动读取 Rule 后产生。已删除 manifest 的显式 `rules` 字段、保留 `rules/sopify.mdc` 目录自动发现并完成回归与真实重装；等待 Reload 后复验，不增加 fallback。
  - 2026-08-20 Reload 复验通过：Customize 在 User 范围显示 `sopify`，打开后真实文件为 `rules/sopify.mdc` 且为 Always Apply；多个最新窗口日志中的 Cursor Plugin 服务均为 `ruleCount: 1`。这关闭注册门，不外推 consult/Analyze 行为。
  - 2026-08-20 consult 会话 `067ce461-c667-46fb-88ce-bffe4c4362a1` 只读取 Cursor shared-writing-dna 和只读 Git 状态；Analyze 会话 `7101b90b-ce5d-4acb-8fc3-930056f95e68` 读取精确 Cursor Skill 并运行评分脚本得到 `3/10, pass=false`，两轮均无写入。
  - 2026-08-20 原位切换 `cursor:zh-CN` 后只有一个 Plugin 根和一个 Skill 根，英文阶段模板无残留；保护配置与系统代理不变。`sessionStart` 只保留自动化与既有补充线索，不把模型转述升级为独立行为通过。
  - 2026-08-20 AskQuestion baseline 证据完成：会话 `84e9fa01-c2dc-4db5-9611-0f15c120bcb8` 保留 AskQuestion tool use 与 `Tool not found` 回退。UI 卡片属于人工观察，transcript 不含 tool result 或选项回传；本期不承诺每个模型/会话都提供。
  - 2026-08-22 managed 黑盒完成：临时仓库 `/private/tmp/sopify-cursor-managed-blackbox.WRxVtd` 的 session `2448476f-57b8-4e1d-a522-c19e8202d658` 完成 Analyze → Design → 停车 → Develop，业务文件精确变更，state/handoff/receipt 只经 writer 写入；直接 Shell 改写 active plan 被 Hook 拒绝且哈希不变，未 finalize/commit。
- [x] 5.4 更新现有独立审计包，交 Cursor 只读复审；通过 `sopify_writer` 追加新的 verify receipt，不覆盖历史 receipt。
  - 前置 IDE baseline 证据已齐：Rule/consult/Analyze/AskQuestion/managed develop/writer/Hook 分别保留工具轨迹或文件结果；模型自述不单独计证据。
  - 2026-08-22 最终候选验证：308 passed / 78 subtests，Python compileall、`bash -n install.sh` 与 `git diff --check` 均通过。
  - 最终复审返回 `accept`，P0/P1 无。其三个 P2 已以真实安装与候选对齐、AskQuestion 口径降级和 UI/文件证据分层关闭；后续独立审计的两处术语修正由 `verify_005` 绑定最终方案版本。
- [x] 5.5 保持 `BASELINE_SUPPORTED`，清楚记录自动化、CLI、IDE 各自证据与缺口。
  - 独立 sessionStart、显式 finalize、AskQuestion 跨模型稳定性、CLI 自动 Plugin Rule 与 Cloud Agent 均记录为未验证或不支持边界，不阻塞本次 baseline 收口。

## 6. Release 收口修正

- [x] 6.1 将双语 Cursor Plugin Rule 的 `SOPIFY_VERSION` 纳入现有 release-sync、版本一致性检查和 pre-commit 回滚/暂存，不新增版本机制。
- [x] 6.2 将 Cursor 用户文档与宿主矩阵改为显式语言 target，并提供 stable release 一键安装命令。
- [x] 6.3 运行定向与全量回归，并追加新的 verify receipt，确认当前提交可以进入合并与发布步骤。
  - 结果：定向测试 33 passed；全量测试 311 passed / 78 subtests；Python 语法、Shell 语法、SVG XML 与 `git diff --check` 均通过。
  - 安装检查：隔离 home 中的 Cursor Plugin、Rule、Skills、payload 和 Hooks 均通过 Doctor；IDE/CLI 行为项仍保持未认证，不从文件安装结果外推。
- [x] 6.4 同步 GitHub Pages 的中英文宿主列表、安装支持范围和 FAQ；复用现有标签与响应式布局，不新增页面结构或样式机制。
  - 结果：双语内容测试 20 passed；桌面首页与中文移动端完成本地浏览器渲染检查，Cursor 标签沿用现有 baseline 样式。
