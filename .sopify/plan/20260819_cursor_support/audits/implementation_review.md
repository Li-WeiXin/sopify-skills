# Sopify Cursor 宿主实施 · 独立复审包

## 审计任务

只读审查当前本地提交，不修改代码、方案、state、receipt 或 Git index。不要复述实现者结论；按源码、基线 diff、测试与真实 Cursor CLI transcript 独立裁决。

- Repository: `/Users/weixin.li/code/github/sopify`
- Branch: `feat/cursor-support`
- Baseline: `2c2c13f3f8fd94f05fb3e3789bd2e20755e27863`
- Diff: `git diff 2c2c13f3f8fd94f05fb3e3789bd2e20755e27863..HEAD`，并检查 `git status --short`
- Delivery: 本地已提交，未 push
- 范围: 本地 Cursor IDE + Cursor Agent CLI；不含 Cloud Agent
- 档位: `BASELINE_SUPPORTED`；不得从文件存在或单次模型自述推导 `PROTOCOL_VERIFIED`

## 已定边界

- 保留多宿主内核，Cursor 是新 host，不建 fork。
- 项目规则：`<workspace>/.cursor/rules/sopify.mdc`；全局 Skills：`~/.cursor/skills/sopify/`；payload：`~/.cursor/sopify/`；用户 Hooks：`~/.cursor/hooks.json`。
- 项目规则负责语义路由；Hook 只注入状态事实、拒绝明显直接改写 machine truth。它是 fail-open 防误写 guard，不是安全沙箱。
- 没有项目规则时 Hook no-op；不写仓库级 hooks；不修改 Cursor settings、代理、模型、账号、API Key、钥匙串或 MCP。
- managed writer 全流程与 finalize 不在本轮声明范围；不扩建 MCP、runtime、plugin、orchestrator 或 writer CLI。

## 本轮修复过的审计 finding

1. Doctor 缺席只看 Sopify 自有落点，不再把整个 `~/.cursor` 当成已安装。
2. Cursor 禁用未验证的 EvidentLoop agent 映射；`--workspace` 只安装项目规则，不 bootstrap `.sopify`。
3. Hook doctor 核对 helper 实际路径、可执行 Python 和 `failClosed: false`。
4. `sessionStart` 只注入与 active plan 匹配的 handoff，并声明状态事实不是恢复命令。
5. latest receipt 遵循 `final.json` 优先、timestamp 降序、缺 timestamp 时 receipt 数字兜底。
6. 文件 Hook 按目标路径选择多根 workspace；Shell 在 writer marker 前拒绝明显直接改写。
7. 非法 `hooks.json` 在任何 Sopify 产品写入前失败；合法配置原子合并并保留用户条目。
8. Cursor Hook/helper 绑定具体 `cursor` host，不与通用 `project_rules` surface 隐式耦合。
9. Helper 严格按 `hook_event_name` 分发，不猜事件。
10. 安装结果不再把项目规则落点误报成“已预热”。
11. 安装结果不再声称项目规则“会自动加载”，只说明已按 `alwaysApply: true` 安装并要求在 Cursor Rules 中确认。
12. 多根 `sessionStart` 只在 `cwd` 唯一归属一个已启用 workspace 时注入方案事实；否则只报告歧义。
13. Shell guard 可识别 state 与 receipt 的 `echo x>.sopify/...`、`echo x>>.sopify/...` 等紧贴输出重定向；仍明确不是完整 Shell 解析器或安全沙箱。

第一次独立 Cursor 复审对当时实现给出的裁决是：无 P0/P1，上述 11–13 为应修 P2。第二次复审确认 11、12 关闭，但重现了 receipt 紧贴 `>` 时 13 未关闭。当前实现只给 receipt 命令边界增加 `>`，并补对应测试和真实 CLI 复测；没有引入 Shell parser。`verify_002` 是修复前的过强历史 receipt，未覆盖；本轮用 `verify_003` 纠正。请重新按源码与可观察证据裁决，不沿用实现者结论。

## 自动化证据

- `python3 -m pytest tests -q`：307 passed / 76 subtests。
- `python3 -m compileall -q installer scripts sopify_writer`：passed。
- `git diff --check`：passed。
- 临时 home 测试覆盖 settings 保持不变、非法 hooks 无半安装、stale/fail-closed hooks doctor 失败、project_rules 不隐式装 Cursor Hook、多根路径与多根 sessionStart 歧义、receipt 排序、普通 Shell 绕过、state/receipt 紧贴重定向与命令路径空格。

## 真实 Cursor Agent CLI 证据

临时项目：`/private/tmp/sopify-cursor-cli-blackbox-v2.vDHYE4`。真实安装使用本机已登录的 `agent`，进程环境保留现有 `127.0.0.1:7898` 代理；未改代理或钥匙串。

- Consult：session `c647872d-20e2-4be3-8888-6b4cd0476b44` 实际读取项目 Rule 与 `~/.cursor/skills/sopify/references/shared-writing-dna.md`，未读 Claude/Codex 同名 Skill，未写 state/receipt；但仍读取 Develop Skill/payload，因此只证明副作用边界，不证明 consult 语义路由完全符合规则。
- sessionStart：session `162b4762-f5e1-4a87-970c-4b5dc3bf711f` 在不读取 `.sopify` 文件的情况下收到 `blackbox_plan / continue_host_develop / exec_001` Hook context。
- Shell deny：session `d9670b90-0173-4744-8f6f-c20976a77646` 的 `echo hacked > .sopify/state/active_plan.json # sopify_writer` 被 `beforeShellExecution` 拒绝。
- 无空格 Shell deny：session `40d6cbc5-5486-4df8-80bf-bbdb50dc8c19` 的实际命令 `echo hacked>.sopify/state/active_plan.json` 被 Hook 拒绝。
- Receipt 紧贴重定向 deny：session `3a13cbf2-d184-488e-9331-25e7a7510365` 的实际命令 `echo hacked>.sopify/plan/blackbox_plan/receipts/exec_001.json` 在 `agent -p --output-format stream-json` 标准输出中返回 `tool_call completed` 与 `result.rejected`。持久 transcript 仍只保存 `tool_use` 和模型回复，因此工具拒绝以本次 stream-json 输出为证，未用 transcript 中的模型自述替代。
- 文件工具 deny：session `4ac55fd4-aa38-4f9e-a39f-dc5601ffca99` 对 `current_handoff.json` 的 edit tool 调用被 `preToolUse` 拒绝。
- Analyze 部分失败：session `d2b1121e-7a5e-4c74-8e48-12050e18a32e` 实际读取项目 Rule、Cursor `analyze/SKILL.md`、长规则与评分脚本，但没有调用 `score_requirement.py`，而是继续寻找仓库中不存在的评分细则；会话被停止。不得判定评分门通过。
- 三份 machine truth 最终哈希与黑盒前一致：active `7bc36890...`、handoff `95438c62...`、receipt `00c09422...`；receipt 紧贴重定向复测后再次核对未变。
- Cursor IDE settings 前后哈希均为 `93128937...`；`~/.cursor/settings.json` 仍不存在。
- 多根 `sessionStart` 的歧义处理目前只有自动化证据，没有真实 IDE/CLI 多根黑盒；不得外推为宿主行为已验证。

Transcript 根目录：`/Users/weixin.li/.cursor/projects/private-tmp-sopify-cursor-cli-blackbox-v2-vDHYE4/agent-transcripts/`。请检查实际 tool call / hook result，不以 thinking 或最终自述代替证据。

## 明确未通过或未验证

- CLI Analyze：Skill 路由通过，评分脚本执行未通过。
- CLI consult：machine-truth 零写入通过，语义路由不干净。
- Cursor IDE：未验证 Rules 面板 `Always Apply`、IDE 内 consult/analyze/Hook 行为。
- managed develop/finalize writer-only 完整闭环：不在本轮发布声明范围。
- Doctor 的 IDE/CLI behavior 仍固定报告 `BLACK_BOX_NOT_VERIFIED`，没有把本机临时证据写成产品级持久认证。

## 请独立裁决

1. 是否存在 P0/P1 正确性或回归风险；给出文件、行号、复现。
2. `project_rules` 新 surface 是否保持最小，Cursor-specific Hook 是否避免污染其他 host。
3. Hook 的 fail-open、用户级落点、多根路径、shell 明显改写策略是否与声明一致；不要把它当安全沙箱审计。
4. Doctor、README、专项文档与支持档位是否存在过强口径。
5. 当前准确状态应否是：安装与 Hook baseline 已实现，CLI 黑盒部分通过，Analyze 与 IDE 未闭环，保持 `BASELINE_SUPPORTED`。
6. 是否有可删除的重复层、无消费者抽象或超出本期范围的实现。

输出建议按 `P0 / P1 / P2 / 非阻塞 / 证据缺口 / 过度设计 / 最终裁决`，只报告可复现问题。
