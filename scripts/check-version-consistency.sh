#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

README_PRIMARY="$ROOT_DIR/README.md"
README_ZH="$ROOT_DIR/README.zh-CN.md"
CHANGELOG="$ROOT_DIR/CHANGELOG.md"
SKILLS_ZH="$ROOT_DIR/skills/zh/header.md.template"
SKILLS_EN="$ROOT_DIR/skills/en/header.md.template"
CURSOR_RULE_ZH="$ROOT_DIR/skills/zh/cursor-plugin-rule.mdc.template"
CURSOR_RULE_EN="$ROOT_DIR/skills/en/cursor-plugin-rule.mdc.template"

usage() {
  cat <<'EOF'
Usage: scripts/check-version-consistency.sh

Validate version consistency across:
  - README.md / README.zh-CN.md version badges
  - Latest released version in CHANGELOG.md
  - SOPIFY_VERSION in the standard and Cursor Rule templates

Exit codes:
  0: all checks passed
  1: one or more mismatches found
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

required_files=(
  "$README_PRIMARY"
  "$README_ZH"
  "$CHANGELOG"
  "$SKILLS_ZH"
  "$SKILLS_EN"
  "$CURSOR_RULE_ZH"
  "$CURSOR_RULE_EN"
)

for file in "${required_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required file: $file" >&2
    exit 1
  fi
done

errors=()

add_error() {
  errors+=("$1")
}

extract_badge_version() {
  local file="$1"
  local encoded

  encoded="$(sed -n 's#.*badge/version-\([^)]*\)-orange\.svg.*#\1#p' "$file" | head -n 1)"
  if [[ -z "$encoded" ]]; then
    return 1
  fi

  # shields.io uses double hyphens in badges to represent literal '-' characters
  echo "${encoded//--/-}"
}

extract_sopify_version() {
  local file="$1"
  sed -n 's/^<!-- SOPIFY_VERSION: \(.*\) -->$/\1/p' "$file" | head -n 1
}

extract_latest_release_line() {
  awk '
    /^## \[Unreleased\]$/ { after_unreleased=1; next }
    after_unreleased && /^## \[/ { print; exit }
  ' "$CHANGELOG"
}

parse_release_line() {
  local line="$1"
  local version=""
  local date=""
  local regex='^## \[([^]]+)\] - ([0-9]{4}-[0-9]{2}-[0-9]{2})$'

  if [[ "$line" =~ $regex ]]; then
    version="${BASH_REMATCH[1]}"
    date="${BASH_REMATCH[2]}"
    printf '%s\n%s\n' "$version" "$date"
    return 0
  fi

  return 1
}

readme_primary_version="$(extract_badge_version "$README_PRIMARY" || true)"
readme_zh_version="$(extract_badge_version "$README_ZH" || true)"

if [[ -z "$readme_primary_version" ]]; then
  add_error "README.md: failed to parse version badge."
fi

if [[ -z "$readme_zh_version" ]]; then
  add_error "README.zh-CN.md: failed to parse version badge."
fi

if [[ -n "$readme_primary_version" && -n "$readme_zh_version" && "$readme_primary_version" != "$readme_zh_version" ]]; then
  add_error "README badge mismatch: README.md=$readme_primary_version, README.zh-CN.md=$readme_zh_version."
fi

latest_release_line="$(extract_latest_release_line)"
if [[ -z "$latest_release_line" ]]; then
  add_error "CHANGELOG.md: missing released section after [Unreleased]."
else
  parsed_release="$(parse_release_line "$latest_release_line" || true)"
  if [[ -z "$parsed_release" ]]; then
    add_error "CHANGELOG.md: latest release line has invalid format: $latest_release_line"
  else
    changelog_version="$(echo "$parsed_release" | sed -n '1p')"
    changelog_date="$(echo "$parsed_release" | sed -n '2p')"
    release_count="$(awk -v header="## [$changelog_version] - " 'index($0, header) == 1 { c++ } END { print c + 0 }' "$CHANGELOG")"
    if [[ "$release_count" -ne 1 ]]; then
      add_error "CHANGELOG.md: version $changelog_version appears $release_count times (expected 1)."
    fi
  fi
fi

skills_zh_version="$(extract_sopify_version "$SKILLS_ZH")"
skills_en_version="$(extract_sopify_version "$SKILLS_EN")"
cursor_zh_version="$(extract_sopify_version "$CURSOR_RULE_ZH")"
cursor_en_version="$(extract_sopify_version "$CURSOR_RULE_EN")"

if [[ -z "$skills_zh_version" ]]; then
  add_error "skills/zh/header.md.template: missing SOPIFY_VERSION header."
fi
if [[ -z "$skills_en_version" ]]; then
  add_error "skills/en/header.md.template: missing SOPIFY_VERSION header."
fi
if [[ -z "$cursor_zh_version" ]]; then
  add_error "skills/zh/cursor-plugin-rule.mdc.template: missing SOPIFY_VERSION header."
fi
if [[ -z "$cursor_en_version" ]]; then
  add_error "skills/en/cursor-plugin-rule.mdc.template: missing SOPIFY_VERSION header."
fi
source_versions=("$skills_zh_version" "$skills_en_version" "$cursor_zh_version" "$cursor_en_version")
first_header_version="${source_versions[0]}"
for version in "${source_versions[@]}"; do
  if [[ -n "$version" && "$version" != "$first_header_version" ]]; then
    add_error "Source SOPIFY_VERSION mismatch: generic=$skills_zh_version/$skills_en_version, cursor=$cursor_zh_version/$cursor_en_version."
    break
  fi
done

if [[ -n "${changelog_version:-}" && -n "$readme_primary_version" && "$changelog_version" != "$readme_primary_version" ]]; then
  add_error "Version mismatch: CHANGELOG latest=$changelog_version, README badge=$readme_primary_version."
fi

if [[ -n "${changelog_version:-}" && -n "$first_header_version" && "$changelog_version" != "$first_header_version" ]]; then
  add_error "Version mismatch: CHANGELOG latest=$changelog_version, SOPIFY_VERSION=$first_header_version."
fi

if [[ "${#errors[@]}" -gt 0 ]]; then
  echo "Version consistency check failed:"
  for err in "${errors[@]}"; do
    echo "  - $err"
  done
  exit 1
fi

echo "Version consistency check passed:"
echo "  - Version: ${changelog_version:-$first_header_version}"
echo "  - Date: ${changelog_date:-N/A}"
echo "  - README badge: $readme_primary_version"
echo "  - SOPIFY_VERSION: $first_header_version"
