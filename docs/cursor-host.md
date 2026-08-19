# Cursor 宿主接入

本适配覆盖本地 Cursor IDE 与 Cursor Agent CLI，不覆盖 Cloud Agent。首发档位是 `BASELINE_SUPPORTED`：安装器可以证明文件落点、Skills 树、payload 和用户级 Hook 结构，但不能把“模型声称用了 Skill”当成 Cursor 已执行协议的证据。

## 安装面

在目标项目根目录执行：

```bash
python3 scripts/install_sopify.py --target cursor --workspace .
```

安装器只写入三类 Sopify 资产：

- 项目规则：`<workspace>/.cursor/rules/sopify.mdc`，合法 `.mdc` frontmatter，`alwaysApply: true`。
- 全局资产：`$HOME/.cursor/skills/sopify/` 下的 `analyze`、`design`、`develop`、`kb`、`templates` 五项 `SKILL.md`，以及 `references/shared-writing-dna.md`；payload 位于 `$HOME/.cursor/sopify/`。
- 用户级 Hooks：合并到 `$HOME/.cursor/hooks.json`，helper 位于 `$HOME/.cursor/sopify/helpers/cursor_hook.py`。不写仓库级 `.cursor/hooks.json`。

`--workspace` 只决定项目规则落点，不会自动创建 `.sopify`。`--with-evidentloop` 对 Cursor 首发 fail closed。

它不会创建或修改 Cursor 的 `settings.json`、代理、模型、账号、API Key、钥匙串或 MCP 配置。`~/.claude/skills`、`~/.codex/skills` 只作为 Cursor 的兼容发现面，不作为本适配安装成功的依据。

项目规则中的 Skill 路径使用可移植的 `~/.cursor/skills/sopify`，并要求宿主先读取该路径下的 `references/shared-writing-dna.md`。因此共享写作规范是确定的加载路径，不是只写一句“请参考”。

项目规则不改成 Cursor User Rule。Sopify 的启用边界、四步读链和 machine truth 都属于具体仓库；全局 User Rule 会把这些约束带入所有项目。全局只放可复用的 Skills、payload 与用户级 Hooks，而 Hooks 在项目没有 `.cursor/rules/sopify.mdc` 时 no-op。Cursor 的 Rules 页面只有在打开安装过项目规则的目标项目时，才能用来验收这条项目规则；在其他窗口看不到它是预期行为。

## Hook 边界

Hooks 只做可确定的 session 状态注入和 machine-truth 防误写。意图分类、Analyze 评分和证据判断仍由 Rule/Skill 负责。这是应用层 guard，不是不可绕过的安全沙箱。

- 只在 workspace 存在 `.cursor/rules/sopify.mdc` 时启用；其他 workspace no-op。
- helper 缺失或异常 fail-open，由 Doctor 报告，不阻塞 Cursor 会话。
- `sessionStart` 注入事实快照，并声明这不是恢复命令；`consult_readonly` 与 `quick_fix` 不自动接续 active plan。
- 多根工作区只在 `cwd` 唯一归属某个已启用项目时注入该项目快照；无法唯一判断时只报告歧义，不注入任何方案事实。
- `preToolUse` 按实际 `tool_name` / `tool_input` 检查受保护路径：`.sopify/state/active_plan.json`、`.sopify/state/current_handoff.json`、`.sopify/plan/*/receipts/*.json`。不拦截 `plan.md` / `tasks.md` / `design.md`。
- Shell 使用 `beforeShellExecution`：明显的 `sopify_writer` / `ProtocolStore` 调用放行，明显直接改写拒绝。
- 安装时保留已有合法用户 Hooks；`hooks.json` 非法时停止，不覆盖。

## Doctor 语义

```bash
python3 scripts/sopify_doctor.py --format json --workspace-root . --home-root "$HOME"
```

Cursor 的 doctor 结果分开报告：

- `project_rule_present`：项目规则文件是否存在；未指定 workspace 时 skip。
- `global_skill_tree_present`：全局五项 Skill 与共享写作规范是否存在；
- `payload_present`：版本化 payload/bundle 是否结构完整；
- `cursor_hooks_present`：用户级 `hooks.json` 与 helper 是否结构完整；
- `cursor_ide_behavior`、`cursor_cli_behavior`：真实宿主黑盒行为证据，首发默认是 `skip (BLACK_BOX_NOT_VERIFIED)`。

缺席判定只看 Sopify 自有落点（项目规则、`~/.cursor/skills/sopify`、`~/.cursor/sopify`），不能把整个 `~/.cursor` 或 IDE `settings.json` 当成已安装。指定 workspace 时，`status.installed` 同时要求项目规则和全局 Skill 树。

所以 `pass` 只代表可检查的文件或 bundle 事实，不能伪装成 Cursor 已遵守规则。只有分别取得 IDE 与 CLI 的可观察黑盒证据后，才可以评估是否升级支持档位；本轮不升级档位。

## IDE / CLI 黑盒验收

两条验收线必须分开记录：

1. IDE：在项目中打开 Agent，确认 Rules 面板将 `sopify.mdc` 列为 `Always Apply`；确认 user hooks 已加载；再发起 `consult_readonly`，观察没有新增或修改 `.sopify/state/`、`receipts/`；发起信息不足的 `analyze`，观察 Agent 读取全局 `analyze/SKILL.md` 并执行评分门。再观察 `sessionStart` 注入、文件工具对 machine-truth 的拒绝，以及 Shell 对明显直接改写的拒绝。
2. CLI：进入同一项目后使用已认证的 `agent -p --output-format stream-json "..."`（或等价的 `cursor-agent` 命令），重复上述 consult、analyze 与 Hook 场景；记录命令输出、工具调用及可观察文件变化，不能只记录模型自述。

CLI 与 IDE 共用项目 Rules 和 Skills，但 CLI 不能替代 IDE 的 Rules 面板、`Always Apply` 展示与 IDE 内工具行为验收。因此可以先用 CLI 收集大部分自动化友好的行为证据，IDE 仍必须单独记录，不能由 CLI 结果外推。

若要把 managed develop / finalize 纳入后续发布范围，还必须额外观察四步读链（`active_plan.json` → `plan.md` → `current_handoff.json` → `receipts/`）以及只经已安装 payload 的 `sopify_writer` 库 API 写入 machine truth；在该证据出现前，当前适配不宣称这部分已闭环。

官方依据：[`Cursor Rules`](https://cursor.com/docs/rules)、[`Cursor Agent Skills`](https://cursor.com/docs/skills)、[`Cursor Hooks`](https://cursor.com/docs/hooks)、[`Cursor CLI`](https://cursor.com/docs/cli/using)。
