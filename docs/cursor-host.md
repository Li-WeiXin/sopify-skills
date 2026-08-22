# Cursor 宿主接入

主要目标是本地 Cursor IDE；Cursor Agent CLI 作为低频、手工 Skill 兼容面，不覆盖 Cloud Agent。支持档位保持 `BASELINE_SUPPORTED`。真实 IDE 已观察到 Plugin Rule 路由、Analyze 评分、AskQuestion tool use、managed develop、writer 写回和 Hook 拒绝明显直写；这些 baseline 证据不外推为跨模型稳定性或完整协议认证。真实 CLI 已证明用户 Plugin Rule 不会自动成为 CLI 入口，本期明确不为此增加 launcher、项目 Rule 或 runtime。

## 安装面

```bash
python3 scripts/install_sopify.py --target cursor
```

首次安装或更新本地 Plugin 后，重启 Cursor，或执行 `Developer: Reload Window`，再检查 Plugin 与 Rule。Cursor 官方将 reload/restart 作为 `~/.cursor/plugins/local` 本地测试流程的一部分。

安装一次，管理四个用户级落点：

- Plugin：`~/.cursor/plugins/local/sopify/.cursor-plugin/plugin.json`、`README.md` 与 `rules/sopify.mdc`。README 渐进介绍用途与边界；薄 Always Rule 是 IDE 的语义入口。
- Skills：`~/.cursor/skills/sopify/` 下的 `analyze`、`design`、`develop`、`kb`、`templates` 和共享 references。
- Payload：`~/.cursor/sopify/`，包含版本化 bundle 与 Hook helper。
- Hooks：合并到 `~/.cursor/hooks.json`；不写仓库级 hooks。

Cursor 不需要 `--workspace`，安装器不在目标仓库创建 `.cursor/rules/sopify.mdc` 或预热 `.sopify`。它也不创建或修改 Cursor 的 `settings.json`、代理、模型、账号、API Key、钥匙串或 MCP。兼容目录中的同名 Skills 不作为安装成功依据；Rule 明确路由到 `~/.cursor/skills/sopify`。

`--with-evidentloop` 对 Cursor 当前版本 fail closed。

## 语义与 Hook 边界

IDE Plugin Rule 负责意图分类与 Skill 路由：

- `consult_readonly` 直接只读回答，不自动恢复 active plan；
- `quick_fix` 可修改用户授权的产品代码，但不直接写协议 state、handoff、receipt 或知识库；
- `new_plan`、`continue_plan`、`finalize` 和明确的 managed develop 才进入对应 Skill 与四步协议入口；
- Analyze 必须实际执行 Skill 中的评分脚本，machine truth 只经 `sopify_writer` 库 API 写入。

用户级 Hooks 只补确定性边界，不做意图分类：

- `.sopify/` 是 managed-root 信号；没有该目录时文件与 Shell guard no-op。
- `sessionStart` 只在唯一 managed root 且 active plan 方案包有效时注入事实；多根不唯一或状态无效时不猜测。
- `preToolUse` 按文件目标路径拒绝明显直接写入 `active_plan.json`、`current_handoff.json` 与 `plan/*/receipts/*.json`。
- `beforeShellExecution` 只在 `cwd` 所属 managed root 中拒绝同类明显直接写入；`plan.md`、`tasks.md`、`design.md` 和业务代码不在保护范围。
- helper 缺失或异常 fail-open，由 Doctor 报告；这不是完整 Shell parser 或安全沙箱。

## Doctor 语义

```bash
python3 scripts/sopify_doctor.py --format json --home-root "$HOME"
```

Cursor 分开报告：

- `cursor_plugin_present`：Plugin manifest 与 Rule 是否存在；README 是包内说明，不作为行为或安装健康硬门槛；
- `global_skill_tree_present`：五项 Skills、共享写作/输出契约与 Analyze 评分脚本是否存在；
- `payload_present`：payload/bundle 是否结构完整；
- `cursor_hooks_present`：用户 hooks 与 helper 是否安全、完整；
- `cursor_ide_behavior`、`cursor_cli_behavior`：真实宿主黑盒，默认 `skip (BLACK_BOX_NOT_VERIFIED)`。

缺席判定只看 Sopify 自有落点，不把整个 `~/.cursor` 或现有 IDE settings 当成已安装。文件检查通过不代表 Cursor 已遵循工作流。

## IDE / CLI 证据边界

IDE 与 CLI 分开记录，不互相外推：

1. IDE baseline 已有可观察证据：已安装 Rule 含 `alwaysApply: true`，consult 实际读取 Cursor 写作规范并保持只读；Analyze 读取 Cursor Skill 并执行评分脚本；有限选项澄清至少一次出现未再报 `Tool not found` 的 AskQuestion tool use；managed 场景按 Analyze → Design → Develop 推进，经 `sopify_writer` 写 state、handoff 与 receipts；明显 Shell 直写 machine truth 被 Hook 拒绝且文件哈希不变。
2. IDE 未验证边界：AskQuestion 是否跨模型稳定提供、独立 `sessionStart` 行为与显式 finalize。本期依赖文本追问回退和现有协议边界，不把这些项目作为 baseline 发布阻塞。
3. CLI（可选兼容验收）：手工调用 `/analyze`、`/design` 或 `/develop`，确认实际读取 `~/.cursor/skills/sopify` 中的目标 Skill；若验证 Hooks，保留工具调用、拒绝结果与文件哈希。不得从手工 Skill 或 Hook 通过外推自动语义入口。

Cursor 官方 CLI 文档明确项目 Rules，但没有把用户 Plugin Rule 写成 CLI 加载契约。2026-08-20 的真实会话也未读取 Cursor Plugin Rule 指定的共享规范，显式 `--plugin-dir` 唯一标记探针同样未生效。因此 CLI 自动入口明确不支持，不是本期发布阻塞项；CLI 低频使用时走手工 Skill，不静默保留第二套 Rule。

一次临时仓库黑盒已观察到四步读链、managed develop 与 `sopify_writer` 写回；显式 finalize 仍按用户命令触发，未纳入本次 baseline 黑盒。Doctor 的行为项继续保持静态 `BLACK_BOX_NOT_VERIFIED`，不把某台机器上的临时 transcript 写成可移植产品认证。

官方依据：[`Cursor Plugins`](https://cursor.com/docs/plugins)、[`Plugin format`](https://cursor.com/docs/reference/plugins)、[`Cursor Rules`](https://cursor.com/docs/rules)、[`Cursor Agent Skills`](https://cursor.com/docs/skills)、[`Cursor Hooks`](https://cursor.com/docs/hooks)、[`Cursor CLI`](https://cursor.com/docs/cli/using)。
