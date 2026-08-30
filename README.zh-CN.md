# Sopify

<div align="center">

**可恢复的 AI 编程 — 先问再写，方案跟着项目走**

[![许可证](https://img.shields.io/badge/License-Apache%202.0-blue.svg?style=for-the-badge)](./LICENSE)
[![文档](https://img.shields.io/badge/docs-CC%20BY%204.0-green.svg?style=for-the-badge)](./LICENSE-docs)
[![版本](https://img.shields.io/badge/version-2026--08--30.001152-orange.svg?style=for-the-badge)](#版本历史)
[![欢迎PR](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=for-the-badge)](./CONTRIBUTING_CN.md)

[![Codex](https://img.shields.io/badge/host-Codex-4A9EFF.svg?style=for-the-badge)](#快速开始)
[![Claude](https://img.shields.io/badge/host-Claude-CC785C.svg?style=for-the-badge)](#快速开始)
[![Qoder](https://img.shields.io/badge/host-Qoder-7C3AED.svg?style=for-the-badge)](#快速开始)
[![Copilot](https://img.shields.io/badge/host-Copilot-000000.svg?style=for-the-badge)](#快速开始)
[![Cursor](https://img.shields.io/badge/host-Cursor-111827.svg?style=for-the-badge)](./docs/cursor-host.md)

[English](./README.md) · 简体中文 · [快速开始](#快速开始) · [贡献者](./CONTRIBUTORS.md)

</div>

<div align="center">
<img src="./assets/sopify-cover-cn.jpg" width="660" alt="Sopify — 可恢复的 AI 编程，先问再写，方案跟着项目走" />
</div>

---

AI 工具写代码很快。但在事实没搞清、关键决策还没拍板前就直接动手，快就会变成返工。Sopify 是 AI 编程的开发过程协议层：在托管流程里，需求不全或决策未定时，宿主会先追问，再写代码。

Sopify 把方案和验证收据保存在 `.sopify/` 中，作为可纳入 git 的项目文件；只有恢复用的本地指针不进 git。在同一个仓库中，通过当前宿主已支持的托管入口从这些文件接续；具体入口与验证档位以宿主支持矩阵为准。

无需新编辑器、无需新 CLI。安装到你已有的宿主：Codex、Claude、Qoder、Copilot、Cursor 均支持。

**设计原则：**

- **不确定就停下** — 需求不全时先追问，再动手
- **跨托管宿主恢复** — 方案和验证收据都持久保存在 `.sopify/` 里；支持接续的宿主可从项目状态继续
- **决策留痕** — 方案、取舍、审查持久保存在 `.sopify/`

**Sopify 主要在防什么：**

- **过早开写** — 关键信息没补齐、关键决策没拍板，AI 就直接改代码
- **接力断档** — 一换宿主、换机器、换人接手，就得重新解释上下文
- **决策失忆** — 重要取舍留在聊天里，没沉淀成项目资产

[查看工作流图、checkpoint 与恢复流程 →](./docs/how-sopify-works.md)

## Sopify 在真实 Codex 任务中如何运行

下面展示的是 Sopify 在一次真实 Codex 任务中的运行过程，不是编排好的终端演示。复杂需求先沉淀为方案；审计发现问题时流程停车；用户裁定后再做最小修正，并把验证结果写入收据后归档。

<p align="center">
  <img src="./assets/readme-visuals/codex-dogfood.gif" alt="Sopify 在真实 Codex 任务中的运行过程：需求形成方案，审计发现问题后等待用户裁定，最小修正和验证证据写入收据后再归档" width="900" />
</p>

- **先形成方案** — Codex 没有直接改代码，而是先把目标、边界和验证步骤写入可追踪方案。
- **发现问题就停车** — 首次审计发现一项风险；流程等待用户裁定，随后只补最薄的身份校验。
- **有证据再收口** — 复审确认没有开放风险；最终收据记录 5 项协议检查、55 项定向测试和 48 项子测试，随后才归档。

真实任务是一次可选验证器接入。动效解释 Sopify 如何管理这项工作，归档文件记录实际过程：[方案](./.sopify/history/2026-07/20260718_evidentloop_optional_audit_integration/plan.md) · [验证收据](./.sopify/history/2026-07/20260718_evidentloop_optional_audit_integration/receipts/verify_001.json) · [最终收据](./.sopify/history/2026-07/20260718_evidentloop_optional_audit_integration/receipts/final.json)。

## 快速开始

```bash
curl -fsSL https://github.com/evidentloop/sopify/releases/latest/download/install.sh | bash -s -- --target codex:zh-CN
```

Sopify 需要 Python 3.11 或更高版本；安装器会在下载前检查。这条命令只安装 Sopify。

可选：在同一命令末尾追加 `--with-evidentloop` 可同时安装 EvidentLoop，详情见
[安装说明](#安装说明)。

安装后用 `~go` 启动全托管工作流。其他宿主、Windows，以及如何先查看脚本再安装，请看[安装说明](#安装说明)。

**已在 Sopify 管理的仓库里？** 明确说“继续”或使用 `~go`，即可恢复当前方案。普通问答和小范围修改会按当前请求直接处理，不会自动进入之前的方案流程。

## 为什么选择 Sopify？

**需求不清楚时，它会停下来。**
你说"加个缓存"。Sopify 不急着动手——先分析需求、设计方案、拆分任务，把讨论结果沉淀到 `.sopify/plan/` 里。方案确认后才写代码，改的每一行都有据可查。

<div align="center">
<img src="./assets/readme-visuals/sopify-scene-ask.jpg" width="720" alt="先有方案 再写代码 — 讨论·沉淀·执行" />
</div>

**你的队友可以直接接手。**
你在 Codex 里开始一个功能，完成了设计和两个任务。下周队友打开同一个仓库的 Claude，输入 `~go`。Sopify 读取 checkpoint，从任务 3 继续——不用写交接文档，不用重新交代上下文。

<div align="center">
<img src="./assets/readme-visuals/sopify-scene-cross-host.jpg" width="720" alt="跨宿主无缝接力" />
</div>

**每个决策都留有痕迹。**
一个月后，有人问为什么缓存 key 里带了用户 ID。答案在 `.sopify/plan/` 里——触发这个决策的需求、设计它的方案、通过它的审查，一应俱全。

<div align="center">
<img src="./assets/readme-visuals/sopify-scene-decision.jpg" width="720" alt="决策留痕 可追溯" />
</div>

## 产品形态

<div align="center">
<img src="./assets/sopify-product-form-release.svg" width="900" alt="Sopify 产品形态 — 宿主、Skill、项目资产、本地交接与显式归档" />
</div>

宿主 LLM 负责执行。Sopify 提供共享工作流规则，并把方案、决策和验证证据作为项目文件保存在 `.sopify/` 中；本地恢复指针只留在当前机器。

Sopify 主要做三件事：

- **共享工作流协议** — 各适配器通过宿主已支持的入口交付同一协议；入口形态与验证档位保持显式
- **项目记录随 Git 携带** — 方案、决策和验证证据跟着仓库走，本地指针不跟随
- **明确接续与收口** — 说“继续”或输入 `~go` 后，宿主才会恢复；交付证据就绪后，`~go finalize` 才归档方案

## 架构细节

想了解产品形态背后的内部层次，可以看下面的技术结构图。

<div align="center">
<img src="./assets/sopify-architecture.svg" width="760" alt="Sopify 架构 — 协议内核 + 默认工作流 + 知识层" />
</div>

## 安装说明

先查看脚本再安装：

```bash
curl -fsSL -o sopify-install.sh https://github.com/evidentloop/sopify/releases/latest/download/install.sh
less sopify-install.sh          # 审查后再执行
bash sopify-install.sh --target codex:zh-CN
```

Windows PowerShell：

```powershell
iwr https://github.com/evidentloop/sopify/releases/latest/download/install.ps1 -OutFile sopify-install.ps1
Get-Content sopify-install.ps1 | more
.\sopify-install.ps1 --target codex:zh-CN
```

宿主支持：

| 宿主 | Tier | Target | 说明 |
|------|------|--------|------|
| Codex | PROTOCOL_VERIFIED | `codex:zh-CN` / `codex:en-US` | 全能力接续 |
| Claude | PROTOCOL_VERIFIED | `claude:zh-CN` / `claude:en-US` | 全能力接续 |
| Qoder | PROTOCOL_VERIFIED | `qoder` | 已在 Qoder CLI 验证 |
| Copilot | BASELINE_SUPPORTED | `copilot:zh-CN` / `copilot:en-US` | 仅 prompt；payload 升级计划中 |
| [Cursor](docs/cursor-host.md) | BASELINE_SUPPORTED | `cursor:zh-CN` / `cursor:en-US` | 一次安装支持 IDE 与本地 CLI；CLI 方案/开发/接续/收口入口按需触发 |

可用 `--workspace <path>` 指定目标仓库，`--language <lang>` 控制输出语言；Cursor 为用户级一次安装，不需要 `--workspace`。

[EvidentLoop](https://github.com/evidentloop/evidentloop) 是一个可选的代码变更审计工具，
可基于本地 Git diff 生成交互式报告，将审计发现定位到具体修改行，并支持用户通过反馈
更新报告。如需随 Sopify 安装当前官方 CLI 与 Skill，或复用已有健康组件，请显式传入
`--with-evidentloop`：

```bash
bash sopify-install.sh --target codex:zh-CN --with-evidentloop
```

已有健康组件会直接复用，不自动升级。Copilot Skill 仅写入当前项目，Sopify 不会自动
提交或更新。前置条件、各宿主安装路径及本地/云端边界见
[Getting Started](./docs/getting-started.md#optional-evidentloop-companion)。

完整设置指南见 [Getting Started](./docs/getting-started.md)。分步 demo 见 [External Repo Quickstart](./examples/external-repo-quickstart/README.md)。

## 命令参考

| 命令 | 说明 |
|-----|------|
| `~go` | 自动判断并执行完整流程（有活动 plan 时自动恢复执行） |
| `~go plan` | 只规划不执行 |
| `~go finalize` | 收口当前活动方案 |

普通用户只需要记住 `~go / ~go plan`；维护者验证命令放在 [贡献指南](./CONTRIBUTING_CN.md)。

## 配置说明

```bash
cp examples/sopify.config.yaml ./sopify.config.yaml
```

```yaml
brand: auto
language: zh-CN

workflow:
  mode: adaptive   # strict | adaptive | minimal
  require_score: 7

```

## 目录结构

```text
sopify/
├── scripts/               # 安装、诊断与维护脚本
├── examples/              # 配置示例
├── docs/                  # 工作流指南与开发者参考
├── sopify_writer/         # 协议资产写入库
├── sopify_contracts/      # schema 定义与共享数据结构
├── skills/                # prompt-layer 源码
├── installer/             # 宿主适配器与安装编排
└── .sopify/               # 项目协议根目录
    ├── blueprint/         # 协议规范、设计基线与削减目标
    ├── plan/              # 活跃方案 + receipts
    └── history/           # 已归档方案 + receipts
```

完整工作流、checkpoint 和知识库层级说明见 [工作流说明](./docs/how-sopify-works.md)。

## 版本历史

- 详细变更记录见 [CHANGELOG.md](./CHANGELOG.md)

## 许可证

- 代码与配置：Apache 2.0，见 [LICENSE](./LICENSE)
- 文档：CC BY 4.0，见 [LICENSE-docs](./LICENSE-docs)

## 贡献

提交用户可见行为改动时，建议同步更新 `README.md` / `README.zh-CN.md`，并参考 [CONTRIBUTING_CN.md](./CONTRIBUTING_CN.md) 执行校验。
