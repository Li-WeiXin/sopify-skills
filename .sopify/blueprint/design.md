# 蓝图架构与契约

本文定位: Sopify 的架构分层、核心契约、削减目标与硬约束。这是协议内核（protocol kernel）的设计基线。

## 产品定位 (ADR-013)

Sopify 是装在现有 AI 编程宿主上的**开发过程协议层**。它把方案、决策、交接和验证记录沉淀为 `.sopify/` 里的项目资产，让 AI 编程任务能停、能接、能查。Sopify 官方在协议层之上提供一个轻量、可插拔的 blueprint-driven workflow 作为默认产品体验。

| 层级 | 表述 |
|------|------|
| 用户层 | 能停、能接、能查：缺事实时停下，换 session/host 可继续，决策和验证有据可溯 |
| 产品层 | 开发过程协议层：把方案、决策、交接、验证记录沉淀为 `.sopify/` 项目资产 |
| 能力层 | 接续、留痕、审计、跨宿主协作 |
| 架构层 | Protocol kernel + sopify_writer + receipts + default workflow + host/skill adapters |

## 产品分层

| 产品层 | 职责 | 映射到实现 |
|-------|------|-----------|
| **Protocol Kernel** | 证据规范、协议准入、receipts、handoff 接力、archive | protocol.md + sopify_writer + sopify_contracts |
| **Default Workflow** | 以 blueprint 为基线的分析、标准方案包生成、checkpoint 讨论（含跨宿主审查）、归档回写 | Protocol conventions + host prompt assets + skill prompts |
| **Plugins / Skills** | 外部能力接入，分三类（见下方） | Integration Contract (protocol.md §6) + protocol admission |

**层间规则：**

- **Core promotion rule**：只有影响跨宿主互操作、receipt validity、archive admissibility 的契约才能进 Protocol Kernel
- **Default Workflow 边界**：消费 Protocol Kernel 契约，不自行定义准入语义；是 Core 之上的 opinionated happy path
- **Plugin trust rule**：插件输出进入 receipt/handoff/blueprint 前，必须经过 protocol admission 或 knowledge_sync gate

**Plugin 三分类：**

| 类型 | 职责 | 典型实例 | 输出流向 |
|------|------|---------|---------|
| **Verifier** | 独立验证生产结果，输出 verdict + evidence | EvidentLoop（可选）或其他验证器 | 由宿主通过 writer 写入正式 receipt（不自授权） |
| **Deterministic Checker** | 确定性规则检查（lint / test / schema） | CI gate adapter（未实现） | 证据链 / handoff evidence |
| **Knowledge Provider** | 提供外部知识输入 | graphify | blueprint / plan context |

### Verifier 使用边界

以下形态都合法：只使用 Sopify；显式选择其他 Verifier；使用已独立安装的 EvidentLoop；通过 `--with-evidentloop` 一次性配套安装。第四种只是显式安装便利：Sopify 先完成，EvidentLoop 再按当前官方方式独立尝试，失败不回滚 Sopify，也不在最终 Skill 目录留下未验证内容。已有健康组件直接复用且不自动升级；兼容性由 EvidentLoop 自身负责，Sopify 不维护版本矩阵，也不自动提交 Copilot 项目 Skill；安装来源不进入运行判断或 receipt。

Sopify 不默认提示、安装或执行任何 Verifier。独立审计可不绑定方案；方案主审计使用 `audits/plan/`，附加审计使用 `audits/<scope>/`。`audits/` 不进入 active plan、handoff 或 4 步默认读取链；正式采用的证据由宿主通过 writer 写 receipt。

**对外承诺分层（Now / Emerging / Future）：**

| 层级 | 能力 | 当前状态 |
|------|------|---------|
| **Now** | 跨宿主可恢复状态（Protocol + sopify_writer） | ✅ Codex / Claude / Qoder protocol_verified |
| ~~**Now**~~ | ~~fail-closed 授权收据（ExecutionAuthorizationReceipt）~~ | ~~✅ P1.5 已交付~~ [RETIRED by P8] post-P8 审计主链改为 `plan/<id>/receipts/*.json` + `history/<id>/receipt.md` |
| **Now** | blueprint-driven 知识沉淀 | ✅ 已交付 |
| **Emerging** | 可选独立审查（EvidentLoop 为首个推荐实例） | 四宿主配套安装契约已验证；非默认执行，Skill discovery 与审计 E2E 仍只按真实宿主证据声明 |
| **Emerging** | Convention-first 外部宿主接入 | Protocol spec v0 已落地；缺少面向外部宿主的 quickstart |
| **Future** | 硅基↔硅基信任协议（跨 agent 授权） | 概念定义阶段 |
| **Future** | Plugin admission + Verifier evidence 标准化 | 设计阶段 |

**协作模式定位：** 当前主战场是碳基↔硅基（人与 AI）。硅基↔硅基仍属战略预留；当前只允许用户显式选择外部 Verifier 形成审计证据，不把某个验证器变成默认工作流。碳基↔碳基主要体现为 blueprint / history 共享带来的兼容收益，不是独立产品面。

**竞品边界：**

| 类别 | 代表产品 | Sopify 的边界 |
|------|---------|-------------|
| 宿主 / IDE（内建工作流状态） | Kiro (AWS)、Claude Code、Codex、Cursor | Sopify 不做模型推理、不做代码执行；宿主原生 spec/checkpoint 是最大吸收风险 |
| Spec / artifact 系统 | OpenSpec (Fission-AI)、Spec Kit (GitHub) | Sopify 不做 spec 方法论、不做 artifact 模板管理；与 spec 系统可互补 |
| Agent runtime / platform | OpenClaw、Hermes Agent | Sopify 不做 agent orchestration、不做 skill routing/gateway；runtime 层有重叠需关注 |
| Skills / methodology 生态 | Superpowers | Sopify 不做技能市场、不做方法论教学；Superpowers 是 agentic skills + methodology |

**Sopify 的不可替代面**：不在于某一项功能，而在于 **可验证的便携式证据与审计语义**——receipts 证据链、跨宿主可恢复状态、可审计项目记忆、独立合规套件。这些能力的组合是单一宿主难以完整替代的。

**竞品吸收应对策略：**

- 宿主吸收执行编排 → Sopify 退守 protocol + admission + compliance
- Spec 工具吸收 checkpoint → Sopify 强调跨宿主连续性 + receipt evidence
- Agent 框架吸收 state → Sopify 做 interop 标准层 / 可携带协议

**生存性测试：** 2027 年宿主原生支持 plan/checkpoint/multi-agent 后，Sopify 仍必须保留：项目级资产沉淀、跨宿主连续工作、可审计决策链、独立质量闭环。如果以上任一能力被宿主完全替代且无跨宿主可携带性需求，该能力应 sunset。

## 底层哲学

> 以下 3 条哲学是 ADR-013/016/017 的共同根基。所有设计决策可从中推导。

### 哲学 1: Convergence-first (收敛优先)

**微观（单任务）是收敛链**：produce → verify → record evidence → settle。目标是按风险逐步降低不确定性，收敛到"可归档阈值"即停止——不以"更完整/更优雅"为默认继续条件。

- produce: 外部生产器（LLM/宿主）输出候选事实
- verify: 外部验证器（EvidentLoop、其他审计器、测试和 lint 等）提供独立证据
- record evidence: sopify_writer + 协议校验将过程证据写入 receipts/；host 负责语义级 admission
- settle: 沉淀为 receipt / handoff / history

> **P8 Final**：原收敛链 produce → verify → authorize → settle 中的 authorize（pre-execution authorization）已在 P8 中退场。当前收敛链确定为 produce → verify → record evidence → settle。post-P8 的 admission 分为 write admission（sopify_writer 结构级校验）和 archive admission（finalize 归档准入）。

**宏观（跨任务）是知识飞轮**：每次 settle 沉淀的 machine truth 提高下一条收敛链的起点，降低验证成本并缩短授权路径。

**停点原则**：达到可授权阈值后即停止。不是每个任务都需要完整的设计 + 交叉审查 + 知识提炼全套流程；按风险选择验证深度。

**沉淀准入门槛**：只有同时满足以下条件的结论才进入长期知识层（blueprint / history）：
- 跨任务可复用
- 影响未来授权或验证基线
- 已经稳定
- 可 machine-readably 引用

**方案级收敛（Default Workflow 策略）**：收敛链不仅适用于单任务执行，也适用于方案讨论阶段。跨宿主审查遵循收敛链语义：

- 方案状态流转：`draft → under_review → [accept → approved | revise → draft | blocked → escalate]`
- 停点条件：至少一轮审查无阻塞性 finding 且返回 accept；或用户显式 override；或审查轮数达到上限（默认 3 轮）
- 多审查者冲突：有任一 `blocked` 则整体 blocked；`accept` + `revise` 混合时取 revise
- 机器契约：subject identity 见 `protocol.md §7`；verdict shape 见 `protocol.md §6`。策略性规则（轮数上限、severity 判定）归 Default Workflow，不进 Core

### 哲学 2: Wire-composable (线可组合)

独立收敛链通过**线**（机器契约）组合。Sopify 是串联收敛链的证据与审计线——负责证据规范、协议准入和收据生成，不做生产/验证/知识处理节点本身。

线独立于 session / model / host：同一逻辑 session（`session_id`）内，handoff 让中断后精确继续；跨 session 接力需显式 claim/receipt，不允许静默推进旧 session 的 pending checkpoint。

| 模式 | 实现 | 适用 |
|------|------|------|
| 显式 (Protocol) | sopify_writer → handoff → receipts JSON | 协议准入 / 审计 |
| 隐式 (Convention) | SKILL.md + 目录约定 | 轻量任务 / 新宿主 |

外部能力通过 integration contract 接入（见 `protocol.md` Integration Contract 小节）。

### 哲学 3: Surface-shared (面共享)

所有线共享一个知识面（blueprint / history）。知识面是跨 session/model/host 的共享工作记忆。

在多模型、多云、多宿主逐步解耦的环境下，Surface-shared 的目标是让项目连续性绑定到共享文件协议，而不是绑定到某个模型、云或聊天上下文。受支持的宿主可在用户明确要求后读取 blueprint、plan、history 与 receipts，基于同一项目记录继续工作；本地 handoff 只提供当前环境的恢复提示，推进 pending checkpoint 或产生副作用仍必须经过 protocol admission。

**Sopify 的不可替代性 = 线 + 面的组合。** Protocol 定义证据规范，sopify_writer 做协议准入，Receipts 提供审计证据。

## 三层定位 (ADR-016: Protocol-first)

> **P8 Final**：Protocol-first 是已完成的产品形态。`blueprint/protocol.md` 定义最小可携带协议。Runtime 已在 P8 中退场（W2.10 物理删除 46 文件 / ~15.6K LOC）。Protocol kernel（sopify_writer + sopify_contracts + protocol.md）是协议真相源和受控写入边界。
>
> **Blueprint Truth Cutover 原则**：Blueprint 是产品合法边界和预算的唯一定义源。Protocol kernel 定义 how it currently runs，blueprint 定义 what is valid。

| 层 | 内容 | 体量 | 可替代性 |
|----|------|------|---------|
| **Protocol Kernel** | `.sopify/` 目录约定、schema、sopify_writer、sopify_contracts | ~2K 行 + 纯文档 | 不可替代 |
| **Default Workflow** | analyze / design / develop 三个主阶段 Skill、辅助 Skill 与显式 finalize 动作 + host prompt assets | 纯文档/prompt | 可替换（宿主可用自有工作流） |
| **Host / Skill Adapters** | installer / host adapters / payload / doctor | ~3K 行 | 可按宿主扩展 |

**Convention 模式（当前唯一模式）**：宿主读 prompt 指令 → 自行推进 → sopify_writer 做结构化写入校验 → receipts 提供审计证据。

~~**Runtime 模式**~~：[RETIRED by P8 — runtime gate / router / engine 已在 P8 中物理删除]

协议准入（protocol admission）取代了 pre-execution authorization：sopify_writer 做结构级校验（schema 合法、plan_id 有效、receipt 命名规范），host prompt 做语义级引导，compliance smoke 做静态检查。

## 核心管线 (ADR-017: Action/Effect Boundary)

```
用户自然语言
  → Host LLM 形成 Work Request（意图 + 范围）
  → Protocol admission（sopify_writer schema 校验 + host prompt 语义引导）
  → 宿主执行
  → Receipt / Handoff 暴露过程证据
```

**不变量：**

- Host LLM 是执行者，**不是 authorizer**
- Protocol admission 做**结构级校验**（sopify_writer：schema 合法、plan_id 有效、receipt 命名规范）；host prompt 做**语义级引导**
- sopify_writer **不是 executor**：不生成或修改方案语义；唯一目录迁移例外是 `finalize_plan` 在版本校验后执行标准归档
- 宿主执行层**按协议文件做事**：读 plan.md / handoff / receipts；协议状态、handoff 与 receipts 通过 sopify_writer 写回

### Subject Identity（主体身份）

ActionProposal 管线中，每个 bound-subject side-effecting action 必须携带明确的 subject identity——"操作的是谁"。Subject identity 是 protocol 层契约，sopify_writer 和宿主都是消费方。Subject-free actions（`consult_readonly`、`propose_plan`）不要求主体。

- `subject_type`：被操作对象类型；当前只有 `plan` 为 normative
- `subject_ref`：对象定位，workspace-relative 路径（如 `.sopify/plan/20260501_dark_mode`）
- `plan_version`：完整方案版本，按 level 对应的语义文件集合确定性计算

主体取证优先级：explicit reference → self-reference → new-plan intent → stable handoff evidence → current-plan anchor。

> **规范来源**：`protocol.md` §7 定义 wire contract（P1 升格为 normative；P2 扩展到所有 bound-subject actions）。Bound-subject actions 的 subject binding 通过 `plan_subject` 字段块进入 ActionProposal。Action 与 subject 字段的完整适用关系见 `protocol.md` §7 Action Applicability Matrix。

### ExecutionAuthorizationReceipt（授权脊柱）— *[RETIRED by P8]*

> P8 后 pre-execution authorization 退场。审计主链改为 `plan/<id>/receipts/*.json` + `history/<id>/receipt.md`（post-execution evidence chain）。详见 ADR-017 [RETIRED by P8]。

~~执行授权不再是 checkpoint，而是机器授权事实。~~ Fail-closed 语义已被 receipt validity + protocol admission 取代。

### side_effect_delta（结构化变更清单）

ActionProposal 的标量 `side_effect` 字段表达粗粒度权限层级（`none|write_runtime_state|write_plan_package|write_files|execute_command`），不描述具体变更内容。`side_effect_delta` 是并行存在的可选字段，提供 file-level 结构化变更清单：

```json
{
  "side_effect_delta": [
    {"path": "src/auth.py", "change_type": "modified"},
    {"path": "src/new_module.py", "change_type": "added"},
    {"path": "tests/old_test.py", "change_type": "removed"}
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `path` | string | workspace-relative 文件路径 |
| `change_type` | enum | `added` \| `modified` \| `removed` |

**与标量 side_effect 的关系**：标量不替换、不废弃。两者并行——标量回答"我可以写什么类别？"，delta 回答"我具体要改哪些文件？"。

**P2 scope**：第一版仅 `modify_files` 消费 `side_effect_delta`。其他 action_type（含 `execute_existing_plan`）的 delta 支持为 future hook，蓝图留口但不进 P2 runtime acceptance。缺失 delta 等同 legacy 行为，validator 不 REJECT。

**Protocol admission 消费**：Workspace scoping — delta 路径 MUST 为 workspace-relative（无绝对路径、无 `..` 穿越）。不做 plan-scope 判定（无稳定的 plan scope 机器定义）。

**设计影响来源**：OpenSpec ADDED/MODIFIED/REMOVED delta 语义（T1 Adoption，准入 delta 枚举，不准入 specs/changes 工作区模型）。

### Action-Effect Canonical Pairing（admission 闭合）

每个 action_type 有且仅有一个合法的 side_effect。Protocol admission 在 subject/delta check 之后、evidence check 之前做 pairing 校验，不匹配 → REJECT（fail-close，不 downgrade consult）。完整 pairing 表见 `protocol.md` §7 Action Applicability Matrix 的 `canonical side_effect` 列。

**设计理据**：action_type 表达意图语义，side_effect 表达权限层级。1:1 pairing 防止 action_type 退化成标签而真正权限语义漂在 side_effect 上。不引入新常量类型或 schema 字段——只是一个 dict 常量 + validator 函数。

**P2 scope 边界**：P2 做的是 admission contract 闭合（哪些 action+effect 组合合法）。Execution routing 收敛（protocol admission 后直接走确定性执行，不再经 Router）属于 P3a。

## Runtime 五层架构 — *[RETIRED by P8]*

> P8 后 runtime 已物理删除（W2.10）。以下五层描述的是 pre-P8 Python runtime 的参考实现架构，保留为审计历史。Post-P8 架构为 Protocol Kernel + Default Workflow + Host/Skill Adapters（见 §三层定位）。

### 1. Ingress Layer | 入口守卫层

回答：当前请求能不能进入 runtime、带什么最小上下文进入。不负责路由或意图解释。

### 2. State Resolution Layer | 状态真相层

收敛"现在该信哪份状态"。Loader + Resolver 生成唯一 `ContextResolvedSnapshot`，下游只消费 snapshot，不散读 JSON。

### 3. Routing & Checkpoint Layer | 路由与停点层

基于 snapshot 决定：直接执行还是进入 checkpoint。只有两种 checkpoint 是真正的协作分叉：

- **clarification**：补事实
- **decision**：拍板选路

### 4. Execution & Handoff Layer | 执行交接层

执行当前动作，结果写入 `current_handoff.json`。宿主后续该做什么以 handoff 为准。

### 5. Knowledge Lifecycle Layer | 知识生命周期层

渐进式物化：bootstrap 建最小骨架 → 方案流补齐 blueprint → archive 后归档到 history。

## 削减目标

### 目标词汇表

以下是 canonical 目标。当前存在的非 canonical 词汇标为 legacy/compat，需带 sunset 条件，不得被 blueprint 重新合法化。

#### Checkpoint Types (target: 2)

| Canonical | 语义 |
|-----------|------|
| `clarification` | 补事实（真协作分叉） |
| `decision` | 拍板选路（真协作分叉） |

**已重分类（不再是 checkpoint type）：**

| 旧类型 | 新定位 | 说明 |
|--------|--------|------|
| `plan_proposal` | ~~propose_plan 的 pending artifact~~ | **Wave 3a 已 hard-cut 删除** |
| `execution_confirm` | ~~ExecutionAuthorizationReceipt~~ [RETIRED by P8] | pre-execution authorization 已退场 |
| `develop_checkpoint` | develop callback source | 可触发 clarification 或 decision，不是独立 checkpoint type |

#### required_host_action (target: 5)

| Canonical | 语义 |
|-----------|------|
| `answer_questions` | 宿主展示缺失事实，等待用户补充 |
| `confirm_decision` | 宿主展示设计分叉，等待用户选择 |
| `continue_host_consult` | 宿主继续问答 |
| `continue_host_develop` | 宿主继续代码修改（develop_mode 为 hint：quick_fix/standard） |
| `resolve_state_conflict` | 状态冲突，需宿主介入 |

**Sunset（不计入 canonical budget）：**

| Legacy action | 目标归宿 | Sunset 条件 | 替代 contract | 清理里程碑 |
|---------------|----------|------------|-------------|-----------|
| `confirm_plan_package` | — | — | — | ✅ 已完成（Wave 3a） |
| `confirm_execute` | ~~ExecutionAuthorizationReceipt~~ [RETIRED by P8] | receipt 替代 checkpoint；pre-execution authorization 已退场 | P1.5 authorization contract spec | ✅ 已完成（P8 退场） |
| `review_or_execute_plan` | ActionProposal routing | Validator 接管 plan review/execute 语义；plan review 状态改由 `continue_host_develop` + `plan_generated` stage 表达 | P2 local action contracts | ✅ 已完成（P3a） |
| `continue_host_quick_fix` | `continue_host_develop(mode=quick_fix)` | 合并为 hint | P2 local action contracts | P3a 复核（runtime 已清） |
| `continue_host_workflow` | `continue_host_develop(mode=standard)` | 合并 | P2 local action contracts | P3a 复核（runtime 已清） |
| `archive_completed` | — | — | — | ✅ 已完成（archive lifecycle cutover） |
| `archive_review` | — | — | — | ✅ 已完成（archive lifecycle cutover） |
| `host_replay_bridge_required` | — | — | — | ✅ 已完成（runtime 无活跃引用） |

> **P2 → P3a 衔接说明（P2 追记）**：P2 已落地替代 contract——bound-subject local actions 的 plan_subject binding + Action Applicability Matrix + side_effect_delta schema（见 `protocol.md` §7、本文 side_effect_delta 段落）。上述 3 项 legacy action 的替代 contract 条件已满足。P3a 执行实际清理时，以 P2 定义的 Action Applicability Matrix 为准入基线，删除对应 legacy surface。

#### Route Families — *[P8 后不再承诺]*

> P8 后 runtime 退场，route families 不再是活跃 contract。宿主自行决定工作流路由。以下为 pre-P8 legacy reference。

| Canonical | 覆盖 route_name（runtime 实际值） |
|-----------|-------------------------------|
| `plan` | `plan_only`, `workflow`, `light_iterate` |
| `develop` | `exec_plan`, `resume_active`, `quick_fix` |
| `consult` | `consult` |
| `archive` | `archive_lifecycle` |
| `clarification` | `clarification_pending`, `clarification_resume` |
| `decision` | `decision_pending`, `decision_resume` |

#### Non-family Surfaces — *[P8 后不再承诺]*

> P8 后 runtime 退场，non-family surfaces 不再是活跃 contract。以下为 pre-P8 legacy reference。

| route_name | 分类 | 说明 |
|------------|------|------|
| `state_conflict` | 跨路由错误面 | state-resolution error surface |
| `proposal_rejected` | 跨路由错误面 | protocol admission REJECT 独立 surface |
| `cancel_active` | control/teardown | 清空 active flow，不产出 handoff |

新增 non-family surface 必须显式修改本段落，默认不允许扩口。non-family surface 如果不再被 runtime 主链路引用，应直接删除而非保留为 legacy。

#### Core State Files (P8 post-cutover: 2 files)

> **P8 调整**：Core state files 从 6 收窄为 2。以下为 post-P8 active red-line。

| File | 职责 |
|------|------|
| `active_plan.json` | 定位：当前 plan_id（替代旧 current_plan.json） |
| `current_handoff.json` | 恢复：上次停哪 + required_host_action（保留，schema 收敛） |

**Legacy mapping（P8 退场）：**

| 旧文件 | P8 处置 |
|--------|---------|
| `current_run.json` | [RETIRED] → 语义下沉到 `plan/<id>/plan.md` Status 章节 |
| `current_plan.json` | [REPLACED] → `active_plan.json` |
| `current_clarification.json` | [RETIRED] → 折叠到 `current_handoff.required_host_action = answer_questions` |
| `current_decision.json` | [RETIRED] → 折叠到 `current_handoff.required_host_action = confirm_decision` |
| `current_archive_receipt.json` | [RETIRED] → 真相进 `history/<id>/receipt.md` |
| `current_gate_receipt.json` | [RETIRED] → P8 退场 pre-execution gate model |
| `last_route.json` | [RETIRED] → 可从 handoff 派生 |

### 削减预算表（P8 Final）

| 维度 | Pre-P8 | P8 Target | Hard Max | 状态 |
|------|-------:|----------:|---------:|------|
| Checkpoint types | 5 | 2 | 2 | ✅ canonical only（clarification + decision） |
| required_host_action | 13 | 5 | 6 | ✅ canonical; legacy sunset 完成 |
| Route families | 18 | — | — | ✅ P8 后不再承诺（runtime 退场） |
| Core state files | 8 | **2** | **2** | ✅ active_plan + current_handoff |

**Hard max 例外路径：** 只能通过 ADR 更新。必须说明替代了什么旧概念、为什么不能放到 artifacts/status/hint 里。

> **削减前提**：Runtime 减重目标 P4b，但 P4b 执行以 P4a 外部消费面 keep-list 冻结为硬前提。P4b 执行顺序固定为：release gate 收口 → runtime 旧面删除 → implementation-mirror tests 收口（详见 `tasks.md` P4b）。先 formalize contract，再清 runtime 旧面。不以 runtime 内部治理为驱动独立清理。


## Persistence Surface 分层

> **P8 调整**：以下为 post-P8 active persistence red-line。旧 runtime state 文件退场映射见下方 legacy mapping。

### Active Red-Line（P8 post-cutover）

| 层级 | 物理对应 | Git 状态 | 消费者 | 可删性 |
|------|---------|---------|--------|--------|
| **长期知识** | blueprint/ plan/ history/ project.md | tracked | 人 + 宿主 | 不可删 |
| **长期知识 / 偏好审计** | user/preferences.md · user/feedback.jsonl | tracked | 人 | 不可删 |
| **主链定位 + 恢复** | state/active_plan.json · state/current_handoff.json | gitignored | host protocol entry + sopify_writer | 可重建（gitignored） |

**P8 关键变化**：主链机器真相从 6 个 runtime state 文件收窄为 2 个协议文件（active_plan + current_handoff）。不再存在 runtime gate/router 作为消费者；宿主通过 protocol entry 4 步读顺序消费。

**会话入口稳定边界**：宿主先识别意图，consult / quick fix 不因陈旧状态进入接续链；`active_plan` 保持纯 `plan_id` 指针，Wave / 任务进度来自方案文件。显式审计非 active plan 时，Verifier 的语义审查对目标只读；宿主可按用户选定 Verifier 的官方流程执行只读取证和独立报告生成，随后校验完整方案的 `plan_version` 并仅通过 `sopify_writer` 写方案级 receipt，不切换 active plan / handoff。`session_id` 只作 provenance；只有用户明确并行开发、确认另一任务仍在运行，或写入前发现非本轮版本/状态变化时，才停止当前有副作用的开发。

**P8 偏好能力退场**：`user/preferences.md` 文件保留（persistence red-line 不可删），但旧 `preferences_preload` installer/doctor capability 在 P8 退场（runtime gate 删除后无自动预加载实现承接）。未来由 protocol entry 重新定义消费方式（TBD）。

### Legacy Mapping（P8 退场）

| 旧层级 | 旧文件 | P8 处置 |
|--------|--------|---------|
| 主链机器真相 | state/current_run.json | [RETIRED] → plan.md Status |
| 主链机器真相 | state/current_plan.json | [REPLACED] → active_plan.json |
| 主链机器真相 | state/current_clarification.json | [RETIRED] → handoff.required_host_action |
| 主链机器真相 | state/current_decision.json | [RETIRED] → handoff.required_host_action |
| 可审计凭证 | state/current_gate_receipt.json | [RETIRED] → pre-execution gate model 退场 |
| 可审计凭证 | state/current_archive_receipt.json | [RETIRED] → history/receipt.md |
| 运行态附属 | state/sessions/* | [RETIRED] → runtime 内部，P8 删除 |
| 运行态附属 | state/last_route.json | [RETIRED] → 可从 handoff 派生 |

> replay/ 已在 P3b 列为能力下线（tasks.md P3b），不再列入 persistence surface。

### Mainline-only Keep-list（跨宿主接续最小主链）— *[pre-P8 legacy reference; P8 后以 active 2-file red-line + protocol entry 为准]*

> **P8 Final**：本段以下所列 gate ingress contract / current_run.json / current_plan.json / current_clarification.json / current_decision.json / ExecutionAuthorizationReceipt / current_archive_receipt.json 等 surface 已在 P8 中退场。post-P8 跨宿主接续主链为：active_plan.json → plan.md → current_handoff.json → receipts/（详见 protocol.md §8 Host Protocol Entry Contract）。本段保留为 pre-P8 legacy reference。

当削减目标从 `contract-preserving slimming` 切到 `mainline-only slimming` 时，判断基准不再是“旧 runtime 能力是否完整保留”，而是“跨宿主写入后能否继续接续，且继续过程仍有 machine-readable spec”。据此，真正主链不是一串 Python 调用名，而是以下可携带 contract surface：

1. **Gate ingress contract**
   - `current_gate_receipt.json`
   - `allowed_response_mode`
   - gate 通过条件与当轮时效
2. **Continuation anchors**
   - `state/current_handoff.json`
   - `state/current_run.json`
   - `state/current_plan.json`
3. **Interactive checkpoint branches**
   - `state/current_clarification.json`
   - `state/current_decision.json`
   - 仅在 runtime 因补事实/拍板而暂停时进入，不是每轮必经主干
4. **Authorization evidence**
   - `ExecutionAuthorizationReceipt`
   - `current_archive_receipt.json`（archive 审计补强；非每轮主链必需）
5. **Host consumption rules**
   - 宿主必须先过 gate，再按 handoff 的 `required_host_action` 接班
   - 宿主不得自行重判 route，不得手写 machine truth

通俗地说，主链不是“代码里谁调用谁”，而是“下一个宿主靠哪些文件和字段知道上次停在哪、现在该干嘛、为什么这次能继续”。只要这组 surface 还在，很多 runtime 内围 helper、validator、future boundary、message/presentation 面都可以删。

**删除判定规则（mainline-only）**：

- 若一个模块只服务于文案、观测、兼容桥、未来边界、非 canonical validator，则默认可删
- 若一个模块提供的能力仍需要，但只是在 retained surface 背后组装数据，则优先内联到 retained writer / handoff builder，不保文件
- 若删除某模块后不会破坏 gate receipt、handoff、`current_*` machine truth、host 消费规则、授权凭证，则不因“历史上被调用过”而保留
- `checkpoint` 只保 clarification / decision 两种 canonical 分叉；其他“像 checkpoint 的旧能力”一律按非主链处理


## 外部消费面 Keep-list

> **P8 Final**：本表大部分条目基于 pre-P8 runtime 模型。P8 后 runtime 退场，EAR / gate_receipt / runtime-only state 文件已退场。Post-P8 活跃消费面以 protocol.md §8 Host Protocol Entry Contract + 宿主能力治理 §契约消费矩阵 为准。本表保留为审计参考。

P4b 减重和 P4c 宿主消费治理的红线边界。只冻结 artifact / schema / host-visible contract，不冻结 Python 内部 API、route 枚举、输出文案措辞。未列入本表的面默认为 runtime 内部实现，P4b 可删。

| surface | kind | consumer | freeze_level | why_kept | non-goals / not frozen |
|---------|------|----------|-------------|----------|----------------------|
| protocol.md §6 Verifier: `verdict`, `evidence`, `source` | doc_contract | host / external_tool | semantics | 跨宿主验证结果的标准格式；宿主消费 verdict 做风险判断 | `scope`（SHOULD，非 MUST）；verifier 内部实现方式 |
| ~~protocol.md §6 ExecutionAuthorizationReceipt~~ [RETIRED by P8] | ~~doc_contract~~ | ~~host / external_tool~~ | ~~semantics~~ | ~~fail-closed 授权回执~~ P8 后审计主链改为 `plan/<id>/receipts/*.json` + `history/<id>/receipt.md` | — |
| protocol.md §7 plan Subject Identity: `subject_type`, `subject_ref`, `plan_version` | doc_contract | host / external_tool | semantics | 操作主体绑定；admission fail-closed 的前提 | 其他主体的版本字段 |
| protocol.md §7 plan_subject block: `subject_ref`, `plan_version` | doc_contract | host | semantics | bound-subject 操作的必要条件 | action applicability matrix 的具体枚举值（实现细节） |
| ~~`current_gate_receipt.json`~~ [RETIRED by P8] | ~~gate_contract~~ | ~~host / external_tool~~ | ~~schema~~ | ~~gate 入口判定~~ P8 退场 pre-execution gate model | — |
| `current_handoff.json` top-level: `schema_version`, `route_name`, `run_id`, `plan_id`, `plan_path`, `handoff_kind`, `required_host_action`, `artifacts`, `notes`, `observability`, `resolution_id` | machine_truth | host | schema | 宿主消费 handoff 做执行交接；跨宿主恢复的核心数据 | 内部组装方式（Python to_dict/from_dict）；observability 子字段可演进；`recommended_skill_ids` 已在 6.3 裁定中退役（宿主从未消费） |
| Archive truth — ArchiveCheckResult: `status`, `subject`, `notes`, `knowledge_sync_result` | machine_truth | host | schema | archive 前检查结果；宿主据此决定是否归档 | Python dataclass 名称和内部方法 |
| Archive truth — ArchiveApplyResult: `status`, `subject`, `archived_plan`, `kb_artifact`, `notes`, `registry_updated`, `state_cleared`, `knowledge_sync_result` | machine_truth | host | schema | archive 执行结果的完整凭证 | Python dataclass 名称和内部方法 |
| `install.sh` / `install.ps1` user params: `--target`, `--ref`, `--workspace`, `--language`, `--no-copilot`, `--with-evidentloop`, `--verbose`, `-h` | install_contract | user | existence | 用户安装入口的稳定参数；源码下载前选择 Python 3.11+，没有兼容解释器时不下载、不写入 | 内部转发参数（`--source-channel`, `--source-resolved-ref`, `--source-asset-name`）；不自动安装 Python 或修改用户环境；`SOURCE_CHANNEL`/`SOURCE_REF` 为 distribution metadata，非用户面稳定接口，默认值可变 |
| `builtin_catalog.generated.json` file-level: `schema_version`, `generated_at`, `source`, `skills`; per-skill: `id`, `names`, `descriptions`, `mode`, `entry_kind`, `handoff_kind`, `contract_version`, `supports_routes`, `triggers`, `metadata`, `tools`, `disallowed_tools`, `allowed_paths`, `requires_network`, `host_support`, `permission_mode`, `runtime_entry` | machine_truth | host | schema | 宿主消费 skill 清单做能力发现和 prompt 注入 | 具体 skill 枚举（能力上下线属内容变更，不违反 freeze）；Python API 签名（`load_builtin_skills()`） |
| Persistence: `blueprint/` `plan/` `history/` `project.md` | persistence_red_line | user / host | existence | 长期知识；人 + 宿主 + runtime 共同消费 | 目录内部文件结构（可增删文件） |
| Persistence: `user/preferences.md` · `user/feedback.jsonl` | persistence_red_line | user / host | existence | 偏好审计；tracked 不可删 | 文件内部格式可演进 |
| Persistence: ~~`state/current_run` · `current_plan` ·~~ `current_handoff` · ~~`current_clarification` · `current_decision`~~ [P8: 仅 current_handoff 保留；其余 RETIRED，详见 Core State Files legacy mapping] | persistence_red_line | host | existence | 主链机器真相；运行期不可删 → P8 后仅 current_handoff + active_plan | — |
| ~~Persistence: `state/current_gate_receipt` · `current_archive_receipt`~~ [RETIRED by P8] | ~~persistence_red_line~~ | ~~external_tool~~ | ~~existence~~ | ~~可审计凭证；运行期不可删~~ P8 后 gate model 退场，archive receipt 真相进 history/receipt.md | — |

> **未列入面默认可删**：`state/sessions/*`、`state/last_route.json`、runtime 内部模块边界、route name 全集、output 渲染文案措辞均为 runtime 内部实现，不在 keep-list 内。P4b 减重时可自由处置。

`host_support` 只声明官方适配器能把 Skill 语义交付到对应宿主的支持界面并由宿主消费。它不等同于原生 Skill discovery，也不证明该宿主已经完成 E2E；支持等级、已验证能力和入口形态继续由 `HostCapability` 表达。当前五个内置 Skill 面向 `codex / claude / qoder / copilot / cursor`，其中 Copilot 通过单文件展开消费，Cursor 通过项目规则与全局 Skill 树拆分消费。


## Output Rendering Audit — *[pre-P8 legacy reference]*

> P8 后 runtime output.py 已退场。本审计表保留为 pre-P8 渲染层分类参考。Post-P8 输出由宿主自行渲染，Sopify 只规定协议文件和 receipts 的结构。

output.py 渲染层逐字段分类。只做分类，不做改造决策（改造属 P4c）。

| field / section | source | classification | note |
|----------------|--------|---------------|------|
| Title: `[brand] phase status_symbol` | derived（route_name → phase label 映射） | human_hint | phase label 和 ✓/?/! 均为人类可读提示，不是 machine truth |
| `Plan: <path>` / `Current Plan: <path>` | plan_artifact.path / current_plan.path | machine_truth_projection | resume_active/exec_plan 路径渲染 Current Plan，其余路径渲染 Plan |
| `Summary: <summary>` | plan_artifact.summary / clarification.summary | machine_truth_projection | |
| `Stage: <stage>` | current_run.stage | machine_truth_projection | |
| `Gate: gate_status / blocking_reason / plan_completion` | current_run.execution_gate 或 handoff.artifacts | internal_taxonomy_leak | 三元组直接暴露 runtime 内部 gate 状态机；默认输出中不应前置 |
| `Handoff: <path>` | handoff 文件路径 | machine_truth_projection | |
| `Status: <message>` | derived（route_name + gate_status + handoff） | human_hint | 消息模板由 route_name 和 required_host_action 推导 |
| `Priority note` | result.notes（plan_registry 事件） | human_hint | |
| `Missing Facts: <facts>` | current_clarification.missing_facts | machine_truth_projection | |
| `Questions: <questions>` | current_clarification.questions | machine_truth_projection | |
| `Question: <question>` + `Options: <options>` | current_decision | machine_truth_projection | |
| `Decision Status: awaiting confirmation` | derived（recommended_option_id） | human_hint | |
| `Conflict Code: <code>` + `Reason: <message>` | state_conflict payload | machine_truth_projection | |
| `Quarantined: <count>` | quarantined_items | machine_truth_projection | |
| `Entry Guard Reason: <code>` | handoff.artifacts.entry_guard_reason_code | internal_taxonomy_leak | runtime 内部守卫码，非宿主需消费的 contract |
| `Archive: <path>` + archive status | plan_artifact / archive result | machine_truth_projection | |
| `Route: <route_name>` | result.route.route_name | internal_taxonomy_leak | 仅在 cancel_active 和 fallback 路径直接暴露内部 route 名 |
| `Reason: <reason>` | result.notes / route.reason / route_name（fallback） | mixed（machine_truth_projection + internal） | fallback 到 route_name 时属于 internal taxonomy leak |
| `Changes: N files` + file list | kb_artifact.files + plan_artifact.files + loaded_files + generated_files + state paths | mixed（machine_truth_projection + internal） | 混合了实际写入文件和恢复上下文加载文件（loaded_files）；loaded 不是 Changed |
| `Next: <hint>` | derived（required_host_action + route_name + handoff_kind） | human_hint | 推导逻辑混合了内部 route_name 和 handoff contract 字段 |

**已知热点汇总**：
- **Gate 三元组 leak**：`gate_status / blocking_reason / plan_completion` 直接渲染 runtime 内部 gate 状态机到默认输出
- **Changes 混层**：`loaded_files`（恢复上下文）与实际写入文件混在同一个 Changes 区块
- **Next 推导**：human hint 但内部依赖 route_name + required_host_action 交叉推导，逻辑复杂
- **Route 名泄露**：cancel_active 和 fallback 路径直接渲染 route_name
- **Entry Guard Reason**：内部守卫码不应在默认输出中暴露


## 宿主能力治理 — *[pre-P8 legacy reference; deep_verified / 审计增强 / EAR / gate_receipt 相关表述在 P8 后失效]*


## 宿主能力治理（P8 Final）

> 能力梯度的判定标准是"能消费哪些 protocol contract"，不是"有没有某个安装动作"或"是否接了 runtime"。

### 能力梯度（3 级）

| 梯度 | 含义 | 进入条件 |
|------|------|---------|
| `convention_only` | 只支持文件协议；无 payload | 能消费 protocol.md；有 `.sopify/` 目录结构；遵守 repo-local 优先级 |
| `payload_capable` | 有稳定 payload 落点；能消费 prompt asset | convention_only 全部条件 + payload 落点 + prompt asset 消费 |
| `protocol_verified` | 通过协议 smoke / receipt / resume 验证 | payload_capable 全部条件 + workspace bootstrap + handoff contract 消费 + host adapter + protocol smoke 验证 |

### 宿主验证状态

| 宿主 | 梯度 | 安装命令 | 增强 | 验证 |
|------|------|---------|------|------|
| Codex | `protocol_verified` | `install.sh --target codex:zh-CN` | CONTINUATION + INTERACTION + AUDIT | 已验证 |
| Claude | `protocol_verified` | `install.sh --target claude:zh-CN` | CONTINUATION + INTERACTION + AUDIT | 已验证 |
| Qoder | `protocol_verified` | `install.sh --target qoder` | CONTINUATION + INTERACTION + AUDIT | W3.1-W3.3 已验证 |
| Copilot | `baseline_supported` | `install.sh --target copilot` | PROMPT_ONLY | Prompt-only |
| Cursor | `baseline_supported` | `install.sh --target cursor --workspace <path>` | PROMPT_ONLY + HOOKS | Project `.cursor/rules/*.mdc` + global Skills/payload + user-level `~/.cursor/hooks.json`; IDE/CLI black-box pending |

### 契约消费矩阵（P8 2-file state model）

| surface | convention_only | payload_capable | protocol_verified |
|---------|:-:|:-:|:-:|
| `state/active_plan.json` | ✗ | ○ | ● |
| `state/current_handoff.json` | ✗ | ○ | ● |
| `plan/<id>/receipts/*.json` | ✗ | ○ | ● |
| `history/<id>/receipt.md` | ✗ | ○ | ○ |
| `blueprint/` / `plan/` / `history/` | ✓ | ✓ | ✓ |
| `protocol.md` | ✓ | ✓ | ✓ |

> ✗ = forbidden ○ = optional ● = required ✓ = readable

### 增强组合

| 增强组合 | 消费的 contract 面 | 回答的问题 |
|---------|-------------------|-----------|
| **接续增强** | handoff + active_plan + receipts | 上次停哪了？现在该干嘛？ |
| **交互增强** | handoff.required_host_action（answer_questions / confirm_decision） | AI 是否在等用户补事实或拍板？ |
| **审计增强** | receipts 证据链 + history receipt | 这次接续有没有验证证据？ |

### 官方接入路径

```
步骤 1: 读 protocol + 遵守文件约定 → convention_only ✅
步骤 2: 装 prompt asset / payload → payload_capable ✅
步骤 3: 通过 protocol smoke / receipt / resume 验证 → protocol_verified ✅
```

- 官方新宿主最低接入：`payload_capable` + 接续增强
- 需要处理用户补事实/拍板：再加交互增强
- 需要证明审计链：再加审计增强

### MCP Tool Plane 试点边界

- MCP 只承接 active plan / handoff 读取、protocol check 与受 guard 约束的低层 receipt 写入；分析、设计、开发、checkpoint 与 finalize 决策继续由 prompt/skill 和宿主负责。
- repo-local server 为 `scripts/sopify_mcp_server.py`。Codex-first 注册已通过官方 `codex mcp get/add`、真实 stdio tool 调用和 no-op 复验。
- 2026-07-17 Claude 会话级消费已通过：使用临时 MCP 配置加载同一 repo-local server，成功调用 `sopify.workspace_status_lite`；该证据不等同于持久注册。
- Codex-first 表示验证顺序，不改变 Qoder、Claude、Copilot、Cursor 的能力梯度或支持声明。其他宿主自动注册须复用同一最小契约并各自补证据。
- 当前不把 Python/MCP 依赖供给、payload 打包、doctor 检查或多宿主配置抽象升级为产品面；只有后续证据证明重复痛点时再设计。

### 禁止消费面

所有梯度均不得将以下内容作为稳定消费 contract：

| # | forbidden surface | 为什么禁止 |
|---|-------------------|-----------|
| F1 | `state/` 中除 `active_plan.json` / `current_handoff.json` 外的文件 | P8 后不存在（已退场） |
| F2 | Runtime 内部模块边界（Python API / class / dataclass） | 实现细节，宿主消费的是协议文件 |
| F3 | Output 渲染文案措辞（`Next:` / `Status:` 等 human hint） | derived 人类提示，不是 machine truth |

### Prompt 镜像治理

- prompt asset 属于 payload/install surface
- `skills/{zh,en}` 是 prompt-layer source of truth；宿主安装产物由 installer / host adapter 渲染
- 新宿主不进 legacy 目录树结构；新宿主如需 prompt asset，走 host adapter / payload 机制
- 宿主可按请求直接路由 Analyze、Design、Develop、KB 或 Templates；单个 Skill 只完成自身职责，仍共享正式协议、授权和输出边界，不作为独立产品运行
- Analyze 负责目标、交付物与证据交接；Design 负责方案取舍、readiness 和方案正文模板；Develop 负责批准范围内的实施与验证；KB 负责长期知识和 `knowledge_sync`；Templates 只提供知识库文档形状
- Copilot 单文件产物只展开 header、Skill 入口、references 和 assets。`scripts/` 只属于具备 Skill tree 的宿主；单文件使用 references 中的等价规则，不内联 Python 或暴露不可执行脚本路径

### 公开推广页

- 仓库根目录的 `index.html` 与 `zh-CN.html` 是同一静态产品页的英文和中文入口，共用 `assets/sopify-site.css` 与 `assets/sopify-site.js`
- 页面只陈述当前正式能力与宿主梯度；GitHub Pages 已于 2026-07-21 从 `main / root` 启用，公开入口为 `https://evidentloop.github.io/sopify/`
- 首页在现有接续区说明产品形态，并以架构图作为唯一技术结构入口；Product Form 中英文 SVG 原路径保留，仅供 README 说明 Host、Skill、Assets、Handoff、Archive 五个组成，不进入首页重复展示

---

_以下为 pre-P8 legacy reference，不作为 post-P8 新宿主接入 contract。保留用于审计历史。_

<details>
<summary>pre-P8 宿主能力治理（legacy reference）</summary>

原三级梯度为 convention_only / payload_capable / deep_verified。deep_verified 要求完整 runtime 深适配。P8 后 runtime 退场，deep_verified 重定义为 protocol_verified——验证的是 protocol 行为（smoke / receipt / resume），不是 runtime 接入深度。

原契约消费矩阵基于 6-file state model。P8 后收窄为 2-file（active_plan + current_handoff）。EAR / gate_receipt / archive_receipt 退场。

原模块运行必需性审计评估了 runtime/ 59 个模块。P8 后 runtime/ 已物理删除，此审计不再适用。post-P8 宿主只需消费协议文件 + 调用 sopify_writer。

</details>

## 轻量化产品指标

Sopify 的设计目标不仅是工程轻量（削减 runtime），更是产品轻量（少概念、少前置、默认能用、可逐步增强）。

| 指标 | 目标 |
|------|------|
| Convention 首次上手步骤数 | ≤3（读 blueprint → 写 light plan → finalize） |
| 首次上手必需持久化文件 | ≤4（project.md + blueprint/ 三件套） |
| 默认 workflow 必需 contract 数 | ≤5（plan package + archive + receipt + knowledge_sync + blueprint read） |
| 增强路径额外概念 | 逐步引入：review loop → checkpoint → runtime state → plugin |

## 硬约束

1. **能删则删**：新概念必须替换旧概念或证明不增加概念预算
2. **sopify_writer 只做确定性协议操作**：负责结构/版本校验、receipt 写入、标准目录迁移与成功后清理 state；不做 plan materialization、自动修复或语义状态推断
3. **确定性执行层只按结构化事实执行**：不理解人话、不做语义推断
4. **Host prompt 不定义机器真相**：prompt 只渲染 machine truth，不作为 truth source
5. **develop_mode 是 hint**：不参与权限裁决；权限裁决看 ActionProposal side_effect + state + risk policy
6. **archive 终态不是 host action**：`archive_receipt.status` 是结果状态，不进 `required_host_action`
7. **不用 router phrasing patch 或 prompt workaround 充当长期解法**：machine truth 未收敛时，回到 protocol / sopify_writer 修复
8. **新增判断挂旧语法**：蓝图变更优先强化证据与审计层，不优先做"更多能力"；新增项必须挂回现有 P 主航道，不得新造编号/章节体系
9. **外部接入优先于官方适配**：优先做能让外部宿主看懂、接入、被验证的事，不优先增加官方深适配负担

## 核心契约

### Archive lifecycle

- `ActionProposal(action_type="archive_plan")` 是协议入口；`~go finalize` 只是 alias
- 主体是结构化 `archive_subject`，不通过正则或词表猜
- 两层分离：宿主负责确认显式 finalize 意图并准备语义输入；sopify_writer 负责结构/版本校验、receipt 写入、标准目录迁移和成功后清理 state
- Legacy/metadata 不完整主体返回 `migration_required`，不自动修复
- 归档只在主体等于当前 `active_plan.json` 指向的 plan 时清理执行状态

### Checkpoint 契约

只有两种 canonical checkpoint：

**Clarification：** 补齐最小事实。Host 通过 `current_handoff.required_host_action = answer_questions` 表达。宿主展示问题列表，等待用户补充后继续。Pending 期间不生成正式 plan。

**Decision：** 多方案拍板。Host 通过 `current_handoff.required_host_action = confirm_decision` 表达。宿主展示选项，等待确认后继续。Pending 期间不物化 plan。

**Develop callback（已退役）：** `continue_host_develop` 期间的 develop_callback 回调机制已在 mainline-only slimming 中退役。`continue_host_develop` 作为 handoff action 值保留，但宿主不再支持中途回调 runtime 触发分叉。

### knowledge_sync

`knowledge_sync` 是唯一正式同步契约。旧 `blueprint_obligation` 概念只保留 legacy reject 语义，不重新合法化。

```yaml
knowledge_sync:
  project: skip|review|required
  background: skip|review|required
  design: skip|review|required
  tasks: skip|review|required
```

- `skip`: 本轮无需同步
- `review`: 可能受影响，finalize 时复核
- `required`: 必须更新，否则 finalize 阻断

### Runtime gate ingress — *[RETIRED by P8]*

> P8 后 runtime gate 退场。协议入口改为 Host Protocol Entry Contract（protocol.md §8）：active_plan → plan.md → current_handoff → receipts 4 步读链。

### Runtime state scope — *[RETIRED by P8]*

> P8 后 state/ 收窄为 2 文件（active_plan.json + current_handoff.json），sessions/ 已退场。以下为 pre-P8 legacy reference。

**Post-P8 state scope**：

- `state/active_plan.json`：当前 plan_id 指针（gitignored）
- `state/current_handoff.json`：上次停哪 + required_host_action（gitignored）
- 其余 state 文件（current_run / current_plan / current_clarification / current_decision / current_gate_receipt / sessions/）已退场
- `session_id` 仅作为 provenance 审计字段出现在 handoff/receipt 中，不再对应 state 目录

### 消费契约

| Context | 读取集 | Fail-open |
|---------|--------|-----------|
| `bootstrap` | project.md, preferences.md, blueprint/README.md | 缺深层 blueprint 不报错 |
| `consult` | project.md, preferences.md, blueprint/README.md | 不要求 background/design/tasks |
| `plan` | 上述 + blueprint 全集 + active_plan | 深层 blueprint 缺失先补齐 |
| `develop` | plan 读取集 + state/*.json | history 缺失不阻断 |
| `archive` | archive_subject, knowledge_sync, blueprint 全集, history/index.md | history/index.md 缺失现场创建 |

## Design Influence Intake Gate

外部设计影响分三级准入：

| 级别 | 含义 | 准入条件 |
|------|------|---------|
| T0 Reference | 启发方向 | plan 包内标注 |
| T1 Adoption | 采纳待验证 | 映射到哲学 + 有实现路径 + 有验证方案 + 不与 ADR 冲突 |
| T2 Principle | 沉淀原则 | 已实现 + dogfood 未回退 + 通过删除测试 |

### 已登记的外部设计影响（2026-05）

| 来源 | 吸收方向 | 准入 | 落点 | 映射哲学 |
|------|---------|------|------|---------|
| HelloAGENTS | 验证证据结构化挂载（contract.json / review.json 启发 Verifier evidence 标准化） | T1 | P1.5→P2 桥接 Verifier slice | Convergence-first |
| OpenSpec | side_effect delta 语义（ADDED / MODIFIED / REMOVED，file-level 第一版） | T1 | P2 子项 | Wire-composable |
| Superpowers | 行为级协议合规验证（headless behavioral test 启发 Protocol Compliance Suite） | T1 | P1.5 先行 Phase 1 + 长期 Phase 2 | Convergence-first |
| Hermes Agent | 知识自动提炼方向（persistent memory + skill curator） | T0 | 明确延后 | Surface-shared |
| Spec-Kit | 声明式工作流定义 / 离线分发 | T0 | 明确延后 / installer 层 | Wire-composable |

## ADR 索引

| ADR | 标题 | 状态 |
|-----|------|------|
| ADR-013 | Product Positioning: Evidence & Authorization Layer | 已确认 |
| ADR-016 | Protocol-first / Runtime-optional | 已确认 |
| ADR-017 | Action/Effect Boundary | P0 完成，持续扩展 |

详见 `architecture-decision-records/`。

## KB 职责矩阵

| Path | Layer | Created When | Git Default |
|------|-------|-------------|-------------|
| `blueprint/README.md` | L0 index | 首次项目触发 | tracked |
| `project.md` | L1 stable | 首次 bootstrap | tracked |
| `blueprint/{background,design,tasks}.md` | L1 stable | 首次进入 plan 流 | tracked |
| `plan/YYYYMMDD_feature/` | L2 active | 每次正式方案流 | tracked |
| `history/YYYY-MM/...` | L3 archive | archive_plan apply 成功 | tracked |
| `state/*.json` | runtime | runtime 执行期间 | ignored |
| `replay/` | ~~optional~~ P3b 下线 | 命中主动记录策略（P3b 后移除） | ignored |
