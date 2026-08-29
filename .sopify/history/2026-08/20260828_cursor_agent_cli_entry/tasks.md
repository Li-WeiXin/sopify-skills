# 任务清单: Cursor Agent CLI 顶层入口与一次安装产品化

目录: `.sopify/plan/20260828_cursor_agent_cli_entry/`

## 1. 本机 CLI Skill 优化

- [x] 1.1 根据近期真实会话收窄 managed-first description，保持薄入口结构并补充必要读取顺序。
- [x] 1.2 校验 Skill 结构、语言和行为边界，清理旧副本并把唯一最新版安装到 `~/.cursor/skills/sopify/SKILL.md`。
- [x] 1.3 执行 managed 请求前向验证，记录可复核的本机证据。

## 2. 第一轮 Cursor 独立审计

- [x] 2.1 将当前 Skill、证据与审计要求放入 worktree 可读 handoff。
- [x] 2.2 启动 Cursor 独立审计；收回认可/不认可结论并释放 worker 资源。
- [x] 2.3 对不认可项做最小修正并复验，直到本机 Skill 获得认可。

## 3. 一次安装产品化

- [x] 3.1 将中英文顶层 Skill 纳入 canonical source，并让 Cursor 安装完整性包含该入口。
- [x] 3.2 补最小共享副作用边界、升级/重装与 Doctor 测试；不新增 target、launcher 或能力框架。
- [x] 3.3 同步 Cursor Plugin 说明、接入文档、双语 README、Changelog 与 blueprint 稳定事实。

## 4. 产品化验证与独立审计

- [x] 4.1 运行目标测试、全量回归、Git diff 检查以及安装前后受保护文件哈希检查。
- [x] 4.2 执行 CLI managed 前向观察并保留可复核证据；IDE/CLI 行为项继续明确为独立 `BLACK_BOX_NOT_VERIFIED`，不以静态安装冒充行为证明。
- [x] 4.3 交给 Cursor 独立审计完整实现；修正跨宿主污染后复审获得认可。

## 5. 收尾

- [x] 5.1 完成 spec compliance 与 code quality 两阶段复审，更新方案和任务状态。
- [x] 5.2 将方案更新为 `ready_to_archive` 并保留在 `plan/`；不自动 finalize、commit、push 或发布。
