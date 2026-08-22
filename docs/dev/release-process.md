# Sopify 发布流程

面向维护者。每次发布 stable release 按此流程操作。

---

## 前置（每个 clone 只需一次）

```bash
git config core.hooksPath .githooks
```

---

## 发布步骤

### 1. preflight 检查

```bash
bash scripts/release-preflight.sh
```

依次跑：版本一致性、golden snapshot、builtin catalog 漂移检测、单元测试、skill eval 质量门禁。全部通过再继续。

### 2. 确认版本号

版本号复用现有 build version，不新发明。跑：

```bash
bash scripts/check-version-consistency.sh
```

通过后输出的版本号即为本次 release tag，例如 `2026-03-25.165725`。如果有新提交要发布，先按下方步骤更新版本。

#### 需要发新版本时：更新版本号

**CHANGELOG.md** — 在 `[Unreleased]` 下方插入新版本段：

```markdown
## [Unreleased]

## [2026-03-26.103000] - 2026-03-26

### Changed
- ...

## [2026-03-25.165725] - 2026-03-25
```

`[Unreleased]` 行必须保留。版本行格式固定为 `## [TAG] - YYYY-MM-DD`。

**README.md / README.zh-CN.md** — 替换 version badge 中的版本号（shields.io 格式：`-` 写成 `--`）：

```
version-2026--03--26.103000-orange.svg
```

**四个发布版本源文件顶部注释**：

```
skills/zh/header.md.template  →  <!-- SOPIFY_VERSION: 2026-03-26.103000 -->
skills/en/header.md.template
skills/zh/cursor-plugin-rule.mdc.template
skills/en/cursor-plugin-rule.mdc.template
```

更新后验证：

```bash
bash scripts/check-version-consistency.sh
# 预期：Version consistency check passed: Version: 2026-03-26.103000
```

提交：

```bash
TAG="2026-03-26.103000"
git add CHANGELOG.md README.md README.zh-CN.md \
  skills/zh/header.md.template skills/en/header.md.template \
  skills/zh/cursor-plugin-rule.mdc.template skills/en/cursor-plugin-rule.mdc.template
git commit -m "release: $TAG"
git push
```

### 3. 渲染 stable release asset

**不要直接上传仓库根目录的 `install.sh` / `install.ps1`**，它们是 dev 版（`SOURCE_CHANNEL=dev`）。必须渲染：

```bash
TAG="2026-03-25.165725"   # 替换为实际版本号
OUT_DIR="$(mktemp -d)"
python3 scripts/render-release-installers.py --release-tag "$TAG" --output-dir "$OUT_DIR"
```

验证渲染结果：

```bash
grep "SOURCE_CHANNEL\|SOURCE_REF" "$OUT_DIR/install.sh"
# SOURCE_CHANNEL="stable"
# SOURCE_REF="2026-03-25.165725"

grep "SourceChannel\|SourceRef" "$OUT_DIR/install.ps1"
# $SourceChannel = "stable"
# $SourceRef = "2026-03-25.165725"
```

### 4. 创建 GitHub Release

前往 `https://github.com/evidentloop/sopify/releases/new`：

1. Tag：填入 `$TAG`，目标分支选 `main`
2. Title：`$TAG`（或加可读描述）
3. Description：粘贴 CHANGELOG 本版本内容
4. 上传 `$OUT_DIR/install.sh` 和 `$OUT_DIR/install.ps1`（上传渲染结果，不是仓库原文件）
5. 勾选 **Set as the latest release**
6. Publish release

### 5. post-release smoke 验证

等约 30 秒 CDN 生效后：

```bash
# 快速验证（推荐）
HOME="$(mktemp -d)" bash -c \
  'curl -fsSL https://github.com/evidentloop/sopify/releases/latest/download/install.sh | bash -s -- --target codex:zh-CN --verbose'

# 本次 release 包含 Cursor 变更时，再验证 Cursor
HOME="$(mktemp -d)" bash -c \
  'curl -fsSL https://github.com/evidentloop/sopify/releases/latest/download/install.sh | bash -s -- --target cursor:zh-CN --verbose'
```

或用 smoke 脚本：

```bash
python3 scripts/check-install-payload-bundle-smoke.py --target codex:zh-CN
```

默认安装输出保持精简；发布 smoke 使用 `--verbose`，输出里必须出现：

```
source channel: stable
resolved source ref: 2026-03-25.165725   ← 与 TAG 一致
asset name: install.sh
```

**验证未通过前不要改 README。**

### 6. 切换 README 首屏（smoke 通过后）

确认 `README.md` / `README.zh-CN.md` 安装区块已指向 stable one-liner，主命令不带 `--workspace`，inspect-first 变体保留。`raw/main` 入口只出现在 `CONTRIBUTING*`，不进 README 首屏。

改完后验证：

```bash
python3 scripts/check-readme-links.py
bash scripts/check-version-consistency.sh
```

提交：

```bash
git add README.md README.zh-CN.md
git commit -m "docs: switch README install to stable one-liner $TAG"
git push
```

---

## 故障排查

**上传了未渲染的 `install.sh`**：立即在 Release 页删除该 asset，重新渲染后上传。`--verbose` 输出为 `source channel: dev` 时，需修复 asset 并重新安装。

**smoke 失败**：确认 Release 不是 draft、asset 文件名大小写正确（`install.sh`）、已勾选 "Set as the latest release"。

**临时跳过 git hook**：`SOPIFY_DISABLE_RELEASE_HOOK=1 git commit ...`，仅限调试。

---

## 快速参考

```bash
# 1. preflight
bash scripts/release-preflight.sh

# 2. 确认版本
bash scripts/check-version-consistency.sh
TAG="2026-03-25.165725"   # 替换为实际版本

# 3. 渲染 asset
OUT_DIR="$(mktemp -d)"
python3 scripts/render-release-installers.py --release-tag "$TAG" --output-dir "$OUT_DIR"
# 验证：grep "SOURCE_CHANNEL\|SOURCE_REF" "$OUT_DIR/install.sh"

# 4. 上传到 GitHub Release（手动）

# 5. smoke
HOME="$(mktemp -d)" bash -c \
  'curl -fsSL https://github.com/evidentloop/sopify/releases/latest/download/install.sh | bash -s -- --target codex:zh-CN --verbose'
# 确认：source channel: stable，resolved source ref: $TAG
```
