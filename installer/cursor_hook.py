#!/usr/bin/env python3
"""Cursor stdio hook helper for Sopify machine-truth guards.

Copied to ``<home>/.cursor/sopify/helpers/cursor_hook.py``. Fail-open on any
unexpected error so a broken helper cannot block the Cursor session.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_RULE = Path(".cursor") / "rules" / "sopify.mdc"
PROTECTED_STATE_FILES = frozenset(
    {
        ".sopify/state/active_plan.json",
        ".sopify/state/current_handoff.json",
    }
)
RECEIPT_PATH_RE = re.compile(r"(?:^|/)\.sopify/plan/[^/]+/receipts/[^/]+\.json$")
RECEIPT_COMMAND_RE = re.compile(
    r"(?:^|[>/\s'\"])\.sopify/plan/[^/\s'\"]+/receipts/[^/\s'\"]+\.json(?=$|[\s;&|)'\"])"
)
MUTATING_FILE_TOOLS = frozenset(
    {
        "write",
        "strreplace",
        "delete",
        "editnotebook",
        "applypatch",
        "searchreplace",
    }
)
PATH_KEYS = frozenset({"path", "file_path", "target_file", "notebook_path"})
CONTENT_KEYS = frozenset(
    {"contents", "content", "old_string", "new_string", "patch", "diff", "command", "new_source"}
)
SHELL_OUTPUT_REDIRECT_RE = re.compile(r"(?<![<>=])>{1,2}(?![=>])")
SHELL_WRITE_HINTS = ("tee ", "sed -i", "rm ", "rm\t", "mv ", "cp ")
WRITER_ALLOW_MARKERS = ("sopify_writer", "ProtocolStore")
NON_RESUME_CLAUSE = (
    "这是状态事实，不是恢复命令；先按本轮用户意图分类。"
    "consult_readonly 和 quick_fix 不自动接续 active plan。"
)


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
        result = handle(payload)
        sys.stdout.write(json.dumps(result, ensure_ascii=False))
        sys.stdout.write("\n")
    except Exception:
        sys.stdout.write("{}\n")
    return 0


def handle(payload: dict[str, Any]) -> dict[str, Any]:
    event = str(payload.get("hook_event_name") or "")
    workspaces = _find_enabled_workspaces(payload)
    if not workspaces:
        return _noop(event)
    if event == "sessionStart":
        workspace = _select_session_workspace(payload, workspaces)
        if workspace is None:
            return _ambiguous_session_start(len(workspaces))
        return _session_start(workspace)
    if event == "preToolUse":
        return _pre_tool_use(payload, workspaces)
    if event == "beforeShellExecution":
        return _before_shell(payload, workspaces)
    return _noop(event)


def _noop(event: str) -> dict[str, Any]:
    if event in {"preToolUse", "beforeShellExecution"}:
        return {"permission": "allow"}
    return {}


def _find_enabled_workspaces(payload: dict[str, Any]) -> list[Path]:
    candidates: list[Path] = []
    for raw in payload.get("workspace_roots") or ():
        if raw:
            candidates.append(Path(str(raw)))
    cwd = payload.get("cwd")
    if not cwd and isinstance(payload.get("tool_input"), dict):
        cwd = payload["tool_input"].get("working_directory") or payload["tool_input"].get("cwd")
    if cwd:
        current = Path(str(cwd))
        for _ in range(16):
            candidates.append(current)
            if current.parent == current:
                break
            current = current.parent
    seen: set[Path] = set()
    enabled: list[Path] = []
    for candidate in candidates:
        try:
            root = candidate.expanduser().resolve()
        except OSError:
            continue
        if root in seen:
            continue
        seen.add(root)
        if (root / PROJECT_RULE).is_file():
            enabled.append(root)
    return enabled


def _session_start(workspace: Path) -> dict[str, Any]:
    active = _read_json(workspace / ".sopify" / "state" / "active_plan.json")
    handoff = _read_json(workspace / ".sopify" / "state" / "current_handoff.json")
    plan_id = str((active or {}).get("plan_id") or "") or "(none)"
    handoff_matches = plan_id != "(none)" and str((handoff or {}).get("plan_id") or "") == plan_id
    handoff_action = ((handoff or {}).get("required_host_action") if handoff_matches else None) or "(none)"
    plan_dir = workspace / ".sopify" / "plan" / plan_id if plan_id != "(none)" else None
    plan_valid = bool(plan_dir and (plan_dir / "plan.md").is_file())
    latest_receipt = _latest_receipt_id(plan_dir) if plan_dir is not None else None
    lines = [
        "Sopify status facts (not a resume order).",
        NON_RESUME_CLAUSE,
        f"active_plan: {plan_id}",
        f"plan_present: {str(plan_valid).lower()}",
        f"handoff_action: {handoff_action}",
        f"latest_receipt: {latest_receipt or '(none)'}",
    ]
    return {"additional_context": "\n".join(lines)}


def _select_session_workspace(payload: dict[str, Any], workspaces: list[Path]) -> Path | None:
    if len(workspaces) == 1:
        return workspaces[0]
    cwd = payload.get("cwd")
    if not cwd:
        return None
    try:
        current = Path(str(cwd)).expanduser().resolve()
    except OSError:
        return None
    matches = [workspace for workspace in workspaces if _path_is_within(current, workspace)]
    return matches[0] if len(matches) == 1 else None


def _ambiguous_session_start(workspace_count: int) -> dict[str, Any]:
    return {
        "additional_context": (
            "Sopify status facts were not injected because multiple enabled workspaces are open. "
            f"enabled_workspaces: {workspace_count}. Resolve the target workspace before reading plan state.\n"
            f"{NON_RESUME_CLAUSE}"
        )
    }


def _pre_tool_use(payload: dict[str, Any], workspaces: list[Path]) -> dict[str, Any]:
    tool_name = str(payload.get("tool_name") or "")
    if tool_name.casefold() not in MUTATING_FILE_TOOLS:
        return {"permission": "allow"}
    for path in _extract_paths(payload.get("tool_input")):
        for workspace in _workspaces_for_path(path, payload, workspaces):
            if _is_protected_path(path, workspace):
                return _deny(path)
    return {"permission": "allow"}


def _before_shell(payload: dict[str, Any], workspaces: list[Path]) -> dict[str, Any]:
    command = str(payload.get("command") or "")
    has_write_hint = bool(SHELL_OUTPUT_REDIRECT_RE.search(command)) or any(
        hint in command for hint in SHELL_WRITE_HINTS
    )
    if has_write_hint and any(
        _command_mentions_protected_path(command, workspace) for workspace in workspaces
    ):
        return _deny("protected Sopify machine-truth path")
    if any(marker in command for marker in WRITER_ALLOW_MARKERS):
        return {"permission": "allow"}
    return {"permission": "allow"}


def _workspaces_for_path(path: str, payload: dict[str, Any], workspaces: list[Path]) -> list[Path]:
    raw = Path(path.strip()).expanduser()
    cwd = payload.get("cwd")
    if not cwd and isinstance(payload.get("tool_input"), dict):
        cwd = payload["tool_input"].get("working_directory") or payload["tool_input"].get("cwd")
    try:
        if raw.is_absolute():
            candidate = raw.resolve()
        elif cwd:
            candidate = (Path(str(cwd)).expanduser() / raw).resolve()
        elif len(workspaces) == 1:
            candidate = (workspaces[0] / raw).resolve()
        else:
            return list(workspaces)
    except OSError:
        return list(workspaces)
    return [workspace for workspace in workspaces if _path_is_within(candidate, workspace)]


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _deny(target: str) -> dict[str, Any]:
    message = (
        "Direct writes to Sopify machine-truth files are blocked. "
        "Use the installed sopify_writer library API."
    )
    return {
        "permission": "deny",
        "user_message": message,
        "agent_message": f"{message} Blocked target: {target}",
    }


def _extract_paths(tool_input: Any) -> Iterable[str]:
    if isinstance(tool_input, str):
        if _looks_like_path(tool_input):
            yield tool_input
        return
    if isinstance(tool_input, dict):
        for key, value in tool_input.items():
            key_l = str(key).casefold()
            if key_l in CONTENT_KEYS:
                continue
            if key_l in PATH_KEYS and isinstance(value, str):
                yield value
            elif key_l == "paths" and isinstance(value, list):
                for item in value:
                    if isinstance(item, str):
                        yield item
            else:
                yield from _extract_paths(value)
        return
    if isinstance(tool_input, list):
        for item in tool_input:
            yield from _extract_paths(item)


def _looks_like_path(value: str) -> bool:
    return "/" in value or value.endswith((".json", ".md", ".py"))


def _is_protected_path(path: str, workspace: Path) -> bool:
    normalized = _normalize_relpath(path, workspace)
    if normalized in PROTECTED_STATE_FILES:
        return True
    return bool(RECEIPT_PATH_RE.search(normalized))


def _command_mentions_protected_path(command: str, workspace: Path) -> bool:
    compact = command.replace("\\", "/")
    if any(item in compact for item in PROTECTED_STATE_FILES):
        return True
    if RECEIPT_COMMAND_RE.search(compact):
        return True
    workspace_text = str(workspace).replace("\\", "/")
    return any(
        f"{workspace_text}/{item}" in compact for item in PROTECTED_STATE_FILES
    )


def _normalize_relpath(path: str, workspace: Path) -> str:
    raw = path.strip().replace("\\", "/")
    try:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = workspace / candidate
        relative = candidate.expanduser().resolve().relative_to(workspace.resolve())
        return relative.as_posix()
    except (OSError, ValueError):
        if raw.startswith("./"):
            raw = raw[2:]
        return raw.lstrip("/")


def _latest_receipt_id(plan_dir: Path) -> str | None:
    receipts = plan_dir / "receipts"
    if not receipts.is_dir():
        return None
    final = receipts / "final.json"
    if final.is_file():
        return "final"
    candidates = [path for path in receipts.glob("*.json") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=_receipt_sort_key).stem


def _receipt_sort_key(path: Path) -> tuple[int, float, int]:
    payload = _read_json(path) or {}
    timestamp = _timestamp_value(payload.get("timestamp"))
    receipt_id = str((payload.get("provenance") or {}).get("receipt_id") or path.stem)
    number_match = re.search(r"(\d+)$", receipt_id)
    number = int(number_match.group(1)) if number_match else -1
    if timestamp is not None:
        return (1, timestamp, number)
    return (0, float(number), number)


def _timestamp_value(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


if __name__ == "__main__":
    raise SystemExit(main())
