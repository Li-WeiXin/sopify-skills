#!/usr/bin/env bash
set -euo pipefail

REPO_OWNER="evidentloop"
REPO_NAME="sopify"
ASSET_NAME="install.sh"
SOURCE_CHANNEL="dev"
SOURCE_REF="main"

usage() {
  cat <<'EOF'
Usage: install.sh [--target <host[:lang]>] [--with-evidentloop] [--ref <tag-or-branch>]

Install Sopify for a supported AI host.

Use `--target copilot` to bootstrap the current workspace and write Copilot
instruction files. For Codex / Claude, this installs the host prompt and
Sopify protocol kernel only; project files are initialized later when you run `~go`
inside a workspace.

Options:
  --target <host[:lang]> Host and language to install, for example codex:zh-CN
                         or copilot.
  --workspace <path>     For copilot: target project directory (defaults to
                         current directory). For cursor: project-rule target
                         only; does not create `.sopify`. For other hosts:
                         advanced prewarm.
  --language <lang>      Copilot only: bootstrap output language (en-US/zh-CN).
  --no-copilot           Copilot only: skip Copilot instruction file
                         distribution and only write workspace markers.
  --with-evidentloop     Install the current EvidentLoop CLI and Skill from
                         official sources, or reuse healthy existing components.
                         Disabled by default.
  --verbose              Show full diagnostic install details.
  --ref <tag-or-branch>  Advanced: override the source ref.
  -h, --help             Show this help.
EOF
}

fail() {
  local phase="$1"
  local reason_code="$2"
  local detail="$3"
  local next_step="$4"
  {
    echo "Sopify install failed: $detail"
    echo
    echo "Fix:"
    echo "  $next_step"
    echo
    echo "Diagnostics:"
    echo "  reason_code: $reason_code"
    echo "  phase: $phase"
  } >&2
  exit 1
}

log_step() {
  echo "Sopify: $1" >&2
}

# ── Spinner ──────────────────────────────────────────────────────────────
_SPIN_PID=""
_SPIN_LINES=0  # number of completed ✓ lines printed

_spin_cleanup() {
  if [[ -n "$_SPIN_PID" ]]; then
    kill "$_SPIN_PID" 2>/dev/null || true
    wait "$_SPIN_PID" 2>/dev/null || true
    _SPIN_PID=""
  fi
}

_spinner_loop() {
  local msg="$1"
  local chars="⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
  while true; do
    for (( i=0; i<${#chars}; i++ )); do
      printf "\r  %s %s" "${chars:$i:1}" "$msg" >&2
      sleep 0.08
    done
  done
}

spin_start() {
  if [[ -t 2 ]]; then
    _spin_cleanup
    _spinner_loop "$1" &
    _SPIN_PID=$!
  else
    log_step "$1"
  fi
}

spin_stop() {
  if [[ -n "$_SPIN_PID" ]]; then
    kill "$_SPIN_PID" 2>/dev/null || true
    wait "$_SPIN_PID" 2>/dev/null || true
    _SPIN_PID=""
    printf "\r\033[K  ✓ %s\n" "$1" >&2
    (( _SPIN_LINES++ )) || true
  fi
}

# Erase all completed spinner lines (cursor up N + clear to bottom).
_spin_erase_all() {
  if [[ -t 2 ]] && (( _SPIN_LINES > 0 )); then
    printf "\033[%dA\033[J" "$_SPIN_LINES" >&2
    _SPIN_LINES=0
  fi
}

require_command() {
  local command_name="$1"
  local reason_code="$2"
  local next_step="$3"
  if ! command -v "$command_name" >/dev/null 2>&1; then
    fail "preflight" "$reason_code" "Missing required command: $command_name" "$next_step"
  fi
}

FORWARDED_ARGS=()
REF_OVERRIDE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --ref)
      if [[ $# -lt 2 || -z "${2:-}" ]]; then
        fail "input" "MISSING_REF_VALUE" '`--ref` requires a value.' "Pass --ref <tag-or-branch>, or omit the flag."
      fi
      REF_OVERRIDE="$2"
      FORWARDED_ARGS+=("$1" "$2")
      shift 2
      ;;
    --ref=*)
      REF_OVERRIDE="${1#*=}"
      if [[ -z "$REF_OVERRIDE" ]]; then
        fail "input" "MISSING_REF_VALUE" '`--ref` requires a value.' "Pass --ref <tag-or-branch>, or omit the flag."
      fi
      FORWARDED_ARGS+=("$1")
      shift
      ;;
    *)
      FORWARDED_ARGS+=("$1")
      shift
      ;;
  esac
done

RESOLVED_REF="${REF_OVERRIDE:-$SOURCE_REF}"
if [[ -z "$RESOLVED_REF" ]]; then
  fail "input" "MISSING_SOURCE_REF" "No source ref was resolved for the installer." "Retry with --ref <tag-or-branch>, or inspect the release asset rendering."
fi

spin_start "Checking requirements..."
require_command "curl" "MISSING_CURL" "Install curl, or use the inspect-first flow to download the release asset manually."
require_command "tar" "MISSING_TAR" "Install tar, or use a machine with basic archive support."

# Select the first available Python 3.11+ before downloading any source.
PYTHON_CMD=""
PYTHON_ARGS=()
FOUND_PYTHON_COMMAND=0
DETECTED_PYTHON=""
PYTHON_PROBE='import sys; print(".".join(map(str, sys.version_info[:3]))); raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'
for _candidate in python3 python py; do
  if command -v "$_candidate" >/dev/null 2>&1; then
    FOUND_PYTHON_COMMAND=1
    _probe_succeeded=0
    if [[ "$_candidate" == "py" ]]; then
      if _version="$("$_candidate" -3 -c "$PYTHON_PROBE" 2>/dev/null)"; then
        _probe_succeeded=1
      fi
    elif _version="$("$_candidate" -c "$PYTHON_PROBE" 2>/dev/null)"; then
      _probe_succeeded=1
    fi
    if (( _probe_succeeded == 1 )); then
      PYTHON_CMD="$_candidate"
      if [[ "$_candidate" == "py" ]]; then
        PYTHON_ARGS=("-3")
      fi
      break
    fi
    if [[ -z "$DETECTED_PYTHON" && -n "$_version" ]]; then
      DETECTED_PYTHON="$_candidate $_version"
    fi
  fi
done
if [[ -z "$PYTHON_CMD" ]]; then
  if (( FOUND_PYTHON_COMMAND == 0 )); then
    _python_reason="MISSING_PYTHON"
    _python_detail="Sopify needs Python 3.11 or newer, but no Python command was found. Nothing was downloaded or installed."
  elif [[ -n "$DETECTED_PYTHON" ]]; then
    _python_reason="UNSUPPORTED_PYTHON"
    _python_detail="Sopify needs Python 3.11 or newer. Found: $DETECTED_PYTHON. Nothing was downloaded or installed."
  else
    _python_reason="UNSUPPORTED_PYTHON"
    _python_detail="A Python command was found, but it could not run Python 3.11 or newer. Nothing was downloaded or installed."
  fi
  fail "preflight" "$_python_reason" "$_python_detail" "Install Python 3.11 or newer, then rerun the same command."
fi

spin_stop "Requirements OK"

TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sopify-install.XXXXXX")"
cleanup() {
  _spin_cleanup
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

ARCHIVE_URL="https://codeload.github.com/${REPO_OWNER}/${REPO_NAME}/tar.gz/${RESOLVED_REF}"
ARCHIVE_PATH="$TMP_DIR/source.tar.gz"

spin_start "Downloading Sopify source (${RESOLVED_REF})..."
if ! curl -fsSL "$ARCHIVE_URL" -o "$ARCHIVE_PATH"; then
  _spin_cleanup
  fail "download" "SOURCE_FETCH_FAILED" "Failed to download source archive: $ARCHIVE_URL" "Check network access, verify the ref exists, or use the inspect-first path."
fi
spin_stop "Downloaded (${RESOLVED_REF})"

spin_start "Unpacking installer..."
if ! tar -xzf "$ARCHIVE_PATH" -C "$TMP_DIR"; then
  _spin_cleanup
  fail "unpack" "SOURCE_EXTRACT_FAILED" "Failed to extract source archive: $ARCHIVE_PATH" "Retry the installer or inspect the downloaded archive locally."
fi

spin_stop "Unpacked"

SOURCE_DIR="$(find "$TMP_DIR" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
if [[ -z "$SOURCE_DIR" || ! -d "$SOURCE_DIR" ]]; then
  fail "unpack" "SOURCE_ROOT_MISSING" "The extracted source archive did not contain a repository root directory." "Retry the installer or inspect the downloaded archive locally."
fi

ENTRYPOINT="$SOURCE_DIR/scripts/install_sopify.py"
if [[ ! -f "$ENTRYPOINT" ]]; then
  fail "unpack" "INSTALL_ENTRYPOINT_MISSING" "Missing install entrypoint inside source archive: $ENTRYPOINT" "Retry the installer or inspect the downloaded archive locally."
fi

_spin_cleanup
_spin_erase_all
if [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]; then
  _LOGO_COLOR=$'\033[38;2;154;137;235m'
  _LOGO_RESET=$'\033[0m'
  printf '%s\n' \
    "${_LOGO_COLOR}███████╗ █████╗ ██████╗ ██╗███████╗██╗   ██╗${_LOGO_RESET}" \
    "${_LOGO_COLOR}██╔════╝██╔══██╗██╔══██╗██║██╔════╝╚██╗ ██╔╝${_LOGO_RESET}" \
    "${_LOGO_COLOR}███████╗██║  ██║██████╔╝██║█████╗   ╚████╔╝${_LOGO_RESET}" \
    "${_LOGO_COLOR}╚════██║██║  ██║██╔═══╝ ██║██╔══╝    ╚██╔╝${_LOGO_RESET}" \
    "${_LOGO_COLOR}███████║╚█████╔╝██║     ██║██║        ██║${_LOGO_RESET}" \
    "${_LOGO_COLOR}╚══════╝ ╚════╝ ╚═╝     ╚═╝╚═╝        ╚═╝${_LOGO_RESET}" \
    ""
elif [[ -t 1 ]]; then
  printf '%s\n' \
    "███████╗ █████╗ ██████╗ ██╗███████╗██╗   ██╗" \
    "██╔════╝██╔══██╗██╔══██╗██║██╔════╝╚██╗ ██╔╝" \
    "███████╗██║  ██║██████╔╝██║█████╗   ╚████╔╝" \
    "╚════██║██║  ██║██╔═══╝ ██║██╔══╝    ╚██╔╝" \
    "███████║╚█████╔╝██║     ██║██║        ██║" \
    "╚══════╝ ╚════╝ ╚═╝     ╚═╝╚═╝        ╚═╝" \
    ""
fi
SOPIFY_LOGO_PRINTED=1 "$PYTHON_CMD" ${PYTHON_ARGS+"${PYTHON_ARGS[@]}"} "$ENTRYPOINT" \
  --source-channel "$SOURCE_CHANNEL" \
  --source-resolved-ref "$RESOLVED_REF" \
  --source-asset-name "$ASSET_NAME" \
  ${FORWARDED_ARGS+"${FORWARDED_ARGS[@]}"}
exit $?
