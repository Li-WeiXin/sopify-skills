# 任务清单: Sopify Cursor 宿主支持

目录: `.sopify/plan/20260819_cursor_support/`

## 1. 契约与范围

- [x] 1.1 核对 Cursor 官方 Rules、Skills、Hooks、IDE/CLI 契约，以及现有 HostAdapter、payload、writer、doctor 事实。
  - 验收：区分文件放置、宿主发现和行为遵守；冻结 `BASELINE_SUPPORTED`。
- [x] 1.2 选择多宿主内核 + Cursor adapter，不创建 fork，不扩建 MCP/runtime，不修改 Cursor settings 或代理。
- [x] 1.3 用户裁定应用层边界：接受但修改。
  - 验收：Hooks 负责状态注入和 machine-truth 保护；Rule/Skill 负责语义；Hook 落点改为用户级 `~/.cursor/hooks.json`；项目级 hooks 与 trampoline 取消。

## 2. Baseline 安装面

- [x] 2.1 增加 `project_rules` surface 与 Cursor registration，安装项目 `.mdc`、全局五项 Skills/shared writing 和 payload。
- [x] 2.2 Doctor 分开报告文件事实与 IDE/CLI 行为未验证状态。
- [x] 2.3 同步 registry、catalog、README、专项文档、长期设计基线与测试。
- [x] 2.4 完成首轮定向与全量自动化。后续以本波修正后的回归为准。

## 3. 审计修正与用户级 Hook

- [x] 3.1 修复 baseline finding：Doctor 缺席只看 Sopify 自有落点；`skills_cli_agent=None` 且 `--with-evidentloop` fail closed；`--workspace` 不自动 bootstrap；指定 workspace 时 `status.installed` 同时要求项目规则和全局 Skill 树；清空 `smoke_targets`；项目规则改用 `~/.cursor/skills/sopify`；修正 README / install.sh / install.ps1 / Cursor 文档口径。
  - 验收：隔离 home 仅有 `settings.json` 时 Cursor doctor skip 且 `fail_count=0`；规则文本含 `~/.cursor/skills/sopify`，不含机器绝对路径。
- [x] 3.2 安装并合并用户级 `~/.cursor/hooks.json`：只管理 Sopify 的 `sessionStart`、`preToolUse`、`beforeShellExecution`；保留已有合法 hook；非法 JSON 停止；不写仓库级 `.cursor/hooks.json`。
  - 验收：安装后无项目 `hooks.json`；非法 JSON 原样保留；用户 `sessionStart` 条目保留。
- [x] 3.3 在 payload 增加单一 stdio helper。无项目规则时 no-op；异常 fail-open。`sessionStart` 注入紧凑事实和非恢复条款。`preToolUse` 按实际工具路径拒绝 machine-truth 直接写入。`beforeShellExecution` 拒绝明显直接改写，放行 `sopify_writer`。
  - 验收：`tests/test_cursor_hooks.py` 覆盖 no-op、非恢复条款、多根歧义不注入方案事实、StrReplace deny、plan.md allow、shell deny/allow、fail-open。
- [x] 3.4 同步 doctor（含 hook/helper 结构）、`entry_modes` 增加 `HOOKS`、行为检查保持 `BLACK_BOX_NOT_VERIFIED`，并补自动化测试。
  - 验收：`python3 -m pytest tests` → 307 passed；`cursor_ide_behavior` / `cursor_cli_behavior` 仍为 `BLACK_BOX_NOT_VERIFIED`。

## 4. 黑盒与收口

- [!] 4.1 分别验证 Cursor IDE 与 CLI：Hook 加载、sessionStart 注入、文件工具拒绝、Shell 拒绝、consult 无写入、Analyze 真读 Skill 并执行评分门。模型自述不计证据。
  - CLI 已通过：项目 Rule/共享规范可见、consult 零 machine-truth 写入、sessionStart 事实注入、文件工具 deny、Shell deny（含 state 与 receipt 的无空格 `>` 重定向）；三份 machine truth 哈希不变。
  - CLI 语义缺口：consult 仍读取 Develop Skill/payload，不能判定 `consult_readonly` 路由完全符合规则。
  - CLI 未通过：Analyze 实际读取 `~/.cursor/skills/sopify/analyze/SKILL.md` 与评分脚本，但未调用脚本，继续寻找不存在的评分 rubric 后停止。
  - IDE 未验证：Rules 面板 `Always Apply` 与 IDE 内工具行为不能由 CLI 外推。
- [!] 4.2 本波实现后做复审；只修被接受的回归。不 commit、不 push、不升级档位。
  - 两次独立 Cursor 复审均未发现 P0/P1；第二次复审重开的 receipt 紧贴重定向 P2 已最小修复，达到 307 tests / 76 subtests，并取得真实 CLI 工具层拒绝；等待同一审计口径复核。
- [x] 4.3 用户已授权本地 commit、原目录切换到 `feat/cursor-support` 并删除临时 worktree；本文件随该交付提交。
  - Push 与 finalize 未授权，不执行。
