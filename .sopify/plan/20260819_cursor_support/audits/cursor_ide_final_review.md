# Sopify Cursor IDE Plugin 最终独立复审任务

## 复审模式

- 只读。不要修改代码、方案、`.sopify/state`、receipts、Cursor 配置或 Git index。
- 仓库：`/Users/weixin.li/code/github/sopify`
- 分支：`feat/cursor-support`
- 基线：`d0e81f168be629cfa7f1e6b3cce5ed01f712fc3e`
- 复审对象：相对基线的全部未提交 diff，包括删除文件与 untracked 文件。
- 不沿用实现者结论；只按源码、测试输出、IDE 工具轨迹和文件结果独立裁决。

## 已定产品边界

1. Cursor IDE 是自动语义入口：用户级 Plugin 中一个薄 `alwaysApply: true` Rule 负责意图分类和精确 Skill 路由。
2. Agent CLI 是低频兼容面：不承诺自动加载 Plugin Rule，只保留手工 Skill 与 Cursor 实际加载范围内的用户 Hooks。
3. 不安装项目 `.cursor/rules/sopify.mdc`，不新增 launcher、prompt injector、Command、Custom Agent、MCP、orchestrator 或 runtime。
4. 全局五项 Skills、shared references、payload 与用户 Hooks 由同一个 Cursor host installer 管理。
5. 支持档位保持 `BASELINE_SUPPORTED`；独立 sessionStart、显式 finalize、AskQuestion 跨模型稳定性不是本轮阻塞项，也不得写成已验证。
6. 不修改 Cursor settings、代理、模型、账号、API Key、钥匙串或 MCP；不支持 Cloud Agent。

## 代码与结构审查

- Cursor 仍是多宿主内核中的第五个 adapter，不是 fork。
- `installer/cursor_plugin.py` 只负责本地 Plugin manifest、README 和一个薄 Rule；不得维护 Plugin 私有 Skills 副本。
- Cursor 安装不要求 workspace、不预热项目 `.sopify`，首次产品写入前预检用户 hooks。
- Hooks 只保护明显直接写入 state/handoff/receipt，放行方案文档、业务代码和正常 `sopify_writer` 库 API；helper 异常 fail-open，并由 Doctor 报告。
- Doctor 分开报告 Plugin、Skill、payload、hooks 与 IDE/CLI behavior；临时本机 transcript 不得让静态 behavior 项冒充产品认证。
- 检查 Codex、Claude、Qoder、Copilot 行为没有被 Cursor-specific 分支意外改变。

实现者在 2026-08-22 的最终候选上报告：308 passed / 78 subtests，Python compileall、`bash -n install.sh` 与 `git diff --check` 均通过。复审者应按下面命令自行重跑，不把这段记录当成独立通过。

同日真实 home Doctor 中，Cursor 的 Plugin、payload、bundle resolution、Skill tree 与 Hooks 五项均为 pass；IDE/CLI behavior 仍按静态设计为 skip / `BLACK_BOX_NOT_VERIFIED`。Doctor 的 overall fail 来自本仓库旧 `.sopify/sopify.json` 对 Codex、Claude、Qoder bundle 的历史 pin，不是 Cursor 检查失败，本任务不顺手改写该 workspace 配置。

## 可独立核验的 IDE 证据

### Plugin、consult 与 Analyze

- User Rule `sopify` 已在 Cursor Customize 中显示为 Always Apply，Plugin 服务日志报告 `ruleCount: 1`。
- consult transcript：`/Users/weixin.li/.cursor/projects/Users-weixin-li-code-github-sopify/agent-transcripts/067ce461-c667-46fb-88ce-bffe4c4362a1/067ce461-c667-46fb-88ce-bffe4c4362a1.jsonl`
- Analyze transcript：`/Users/weixin.li/.cursor/projects/Users-weixin-li-code-nio-data-sprite/agent-transcripts/7101b90b-ce5d-4acb-8fc3-930056f95e68/7101b90b-ce5d-4acb-8fc3-930056f95e68.jsonl`
- 核验重点：consult 不加载阶段 Skill、不续旧方案、不写 machine truth；Analyze 实际读取 Cursor Skill 并执行评分脚本，低分时不进入 Design 或写文件。

### AskQuestion

- transcript：`/Users/weixin.li/.cursor/projects/Users-weixin-li-code-nio-data-sprite/agent-transcripts/84e9fa01-c2dc-4db5-9611-0f15c120bcb8/84e9fa01-c2dc-4db5-9611-0f15c120bcb8.jsonl`
- 同一会话包含 `AskQuestion` / `ask_question` 不可用样本，以及后续未再报 `Tool not found` 的 `AskQuestion` tool use；UI 卡片属于人工观察，transcript 不含选项回传或 `Other...`。
- 这只证明 AskQuestion 能力路径和文本回退都存在。不要据此宣称每个模型或每次会话都会稳定提供问卷。

### Managed 主链与 Hook

- 临时仓库：`/private/tmp/sopify-cursor-managed-blackbox.WRxVtd`
- transcript：`/Users/weixin.li/.cursor/projects/private-tmp-sopify-cursor-managed-blackbox-WRxVtd/agent-transcripts/2448476f-57b8-4e1d-a522-c19e8202d658/2448476f-57b8-4e1d-a522-c19e8202d658.jsonl`
- 初始业务文件为 `hello\n`。第一轮实际读取 Analyze/Design Skills，执行评分 `10/10` 和 light 分级，创建方案并经 writer 写 active plan/handoff，然后在 `confirm_decision` 停车，业务文件未改。
- 用户确认后，第二轮读取四步链与 Develop Skill，将 `src/greeting.txt` 精确改成 `hello from Cursor\n`，更新方案为 `ready_to_archive`，并经 writer 追加 `exec_001`、`verify_001` 与 handoff；未 finalize、未 commit。
- 第三轮实际执行紧贴重定向的 Shell 直写 `active_plan.json`，Cursor Hook 返回拒绝；Agent 未尝试绕过。

现场哈希：

```text
f9e1d6f57a5d7a795513cfb8ef1ce5c8c7c3deb3319a0ab38df5a73a735ad0b2  .sopify/state/active_plan.json
f24d2621d2fbc470b9febdcd8e700679358469f025c25f668e74dd1e661ce950  .sopify/state/current_handoff.json
7335746bb72af92df43cb5b1435934d8bed6fbe282307f02630d62836dfe4ecd  .sopify/plan/20260822_greeting_from_cursor/receipts/exec_001.json
70c06cac2adeecc10e91443a04149cd6d5c627befc8cc6fbdbba8943c4ff3e47  .sopify/plan/20260822_greeting_from_cursor/receipts/verify_001.json
bd601aecf0dae231623085daa65a69e8304327aaa829e629eb8362f34cb0496b  src/greeting.txt
```

不要只看最终回复。以 transcript 中的 `tool_use`、方案/receipt 内容、Git diff 和文件哈希为证据。

## CLI 已知边界

- 自动用户 Plugin：`4c24eab4-dd82-46f3-8fd7-67888baa1a53`
- 显式 `--plugin-dir`：`7626c137-9668-450f-ab00-a44619f90f9c`
- 唯一标记探针：`109d2991-78e6-46d8-a19a-5bd86f3198f0`

三次都没有证明 Agent CLI 自动加载用户 Plugin Rule。该能力不在产品承诺内，不是 IDE baseline 阻塞项，也不得改写成 CLI 自动支持。

## 建议命令

```bash
cd /Users/weixin.li/code/github/sopify
git status --short --branch
git diff --check
git diff -- . ':(exclude).sopify/plan/20260819_cursor_support/audits/cursor_ide_final_review.md'
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/opt/python@3.11/libexec/bin/python3 -m pytest -p no:cacheprovider tests -q
PYTHONDONTWRITEBYTECODE=1 /opt/homebrew/opt/python@3.11/libexec/bin/python3 scripts/sopify_doctor.py --format json --home-root /Users/weixin.li
```

普通 `git diff` 不展示 untracked 文件，请单独读取 `git status --short` 列出的全部新资产，尤其是：

- `installer/cursor_plugin.py`
- 双语 Cursor Plugin Rule 与 README 模板
- 本审计文件

## 输出要求

请直接在 chat 返回，不写文件：

1. 一句话裁决。
2. P0 / P1 / P2 findings；没有则明确“无”，每条附文件或可观察证据。
3. 是否存在过度设计、冗余入口或口径过强。
4. 自动化、IDE、CLI 三类证据分别证明什么，哪些仍未验证。
5. 是否认可保持 `BASELINE_SUPPORTED`。
6. 精确状态：`accept`、`accept_with_fixes` 或 `reject`。

不要 commit、push、安装新组件、删除兼容 Skill，或生成 verify receipt。

## 独立复审结果（2026-08-22）

- 精确裁决：`accept`；P0 无，P1 无。
- 认可：Cursor 仍是第五个 adapter，不是 fork；用户 Plugin 薄 Rule、全局 Skills/payload 与用户 Hooks 的分层没有引入 launcher、runtime、MCP、Custom Agent 或第二套项目 Rule。
- P2-1：复审时真实安装 Rule/README 与候选模板有文字差异。已用最终 `cursor:zh-CN` 候选原位重装并逐字核对；Hooks、CLI/User settings、MCP 文件存在状态与系统代理前后不变。
- P2-2：AskQuestion transcript 只证明文本回退和一次未再报 `Tool not found` 的 tool use。公开文档与方案已删除“原生问卷/Other 已验证”等过强口径，不承诺跨模型稳定性或选项回传。
- P2-3：本轮独立复审没有重看 Customize UI 或 `ruleCount: 1` 日志。公开证据口径以已安装 Rule 的 `alwaysApply: true`、consult/Analyze 工具轨迹和既有人工 UI 观察分层记录，不把 UI 观察写成可移植认证。
- 自动化：最终候选 `308 passed, 78 subtests passed`；Python compileall、`bash -n install.sh`、SVG XML 与 `git diff --check` 通过。
- 支持边界：保持 `BASELINE_SUPPORTED`。独立 sessionStart、显式 finalize、AskQuestion 跨模型稳定性、CLI 自动 Plugin Rule 与 Cloud Agent 不在本轮闭环内。

## 独立视觉与文档复审（2026-08-22）

- 最终裁决：`accept`；P0/P1/P2 均无，未发现重复入口或过度设计。
- 三张全量宿主矩阵 SVG 均通过视觉检查；Cursor 与 Copilot 均按 baseline 表达。封面、demo 与跨宿主场景图保持具体示例，不为凑齐宿主重绘。
- 首轮发现的 Cursor Verify Setup 断点、badge 错误导航与 README 顶部跨宿主过强口径，已分别以用户级 Doctor/Always 验证、专项文档直链和支持入口/档位分层关闭。
