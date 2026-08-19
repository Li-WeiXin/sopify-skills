"""Install and inspect user-level Cursor hooks for Sopify."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from typing import Any

from installer.models import InstallError

HOOKS_RELATIVE_PATH = Path(".cursor") / "hooks.json"
HELPER_RELATIVE_PATH = Path("helpers") / "cursor_hook.py"
SOPIFY_HOOK_MARKER = "helpers/cursor_hook.py"
SOPIFY_HOOK_EVENTS = ("sessionStart", "preToolUse", "beforeShellExecution")
HOOKS_SCHEMA_VERSION = 1


def user_hooks_path(home_root: Path) -> Path:
    return home_root / HOOKS_RELATIVE_PATH


def hook_helper_path(payload_root: Path) -> Path:
    return payload_root / HELPER_RELATIVE_PATH


def preflight_cursor_user_hooks(*, home_root: Path) -> None:
    """Validate the existing user hooks file before any Cursor install writes."""
    _read_existing_hooks(user_hooks_path(home_root))


def install_cursor_user_hooks(*, home_root: Path, payload_root: Path) -> Path:
    """Merge Sopify-owned user hooks; refuse to overwrite invalid JSON."""
    helper = hook_helper_path(payload_root)
    if not helper.is_file():
        raise InstallError(f"Missing Cursor hook helper: {helper}")

    path = user_hooks_path(home_root)
    existing = _read_existing_hooks(path)
    hooks = existing.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise InstallError(f"Refusing to overwrite invalid Cursor hooks.json: {path}")

    command = _hook_command(helper)
    sopify_entry = {"command": command, "failClosed": False}
    for event in SOPIFY_HOOK_EVENTS:
        entries = [item for item in _as_hook_list(hooks.get(event)) if not _is_sopify_hook(item)]
        entries.append(dict(sopify_entry))
        hooks[event] = entries
    existing["version"] = existing.get("version") or HOOKS_SCHEMA_VERSION
    existing["hooks"] = hooks

    _atomic_write_json(path, existing)
    return path


def sopify_hooks_are_present(*, home_root: Path, payload_root: Path) -> tuple[bool, str | None]:
    """Return whether Sopify user hooks and helper are structurally present."""
    helper = hook_helper_path(payload_root)
    if not helper.is_file():
        return False, f"Missing Cursor hook helper: {helper}"
    path = user_hooks_path(home_root)
    if not path.is_file():
        return False, f"Missing Cursor hooks.json: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, f"Invalid Cursor hooks.json: {path}"
    if not isinstance(payload, dict):
        return False, f"Invalid Cursor hooks.json: {path}"
    hooks = payload.get("hooks")
    if not isinstance(hooks, dict):
        return False, f"Invalid Cursor hooks.json: {path}"
    for event in SOPIFY_HOOK_EVENTS:
        matches = [item for item in _as_hook_list(hooks.get(event)) if _is_sopify_hook(item)]
        if not matches:
            return False, f"Missing Sopify {event} hook in {path}"
        if not any(_hook_entry_is_healthy(item, helper) for item in matches):
            return False, f"Stale or unsafe Sopify {event} hook in {path}"
    return True, None


def sopify_hook_entries_present(*, home_root: Path) -> bool:
    """Return whether a readable hooks file still contains Sopify-owned entries."""
    path = user_hooks_path(home_root)
    if not path.is_file():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    hooks = payload.get("hooks") if isinstance(payload, dict) else None
    if not isinstance(hooks, dict):
        return False
    return any(
        _is_sopify_hook(item)
        for event in SOPIFY_HOOK_EVENTS
        for item in _as_hook_list(hooks.get(event))
    )


def _read_existing_hooks(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"version": HOOKS_SCHEMA_VERSION, "hooks": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InstallError(f"Refusing to overwrite invalid Cursor hooks.json: {path}") from exc
    if not isinstance(payload, dict):
        raise InstallError(f"Refusing to overwrite invalid Cursor hooks.json: {path}")
    hooks = payload.get("hooks")
    if hooks is not None and not isinstance(hooks, dict):
        raise InstallError(f"Refusing to overwrite invalid Cursor hooks.json: {path}")
    return payload


def _hook_command(helper: Path) -> str:
    parts = (str(Path(sys.executable).resolve()), str(helper.resolve()))
    if os.name == "nt":
        return subprocess.list2cmdline(parts)
    return shlex.join(parts)


def _hook_entry_is_healthy(entry: Any, helper: Path) -> bool:
    if not isinstance(entry, dict) or entry.get("failClosed") is not False:
        return False
    try:
        parts = shlex.split(str(entry.get("command") or ""), posix=os.name != "nt")
    except ValueError:
        return False
    if len(parts) != 2:
        return False
    executable_text = parts[0].strip('"')
    helper_text = parts[1].strip('"')
    executable = Path(executable_text).expanduser()
    configured_helper = Path(helper_text).expanduser()
    try:
        return (
            executable.is_file()
            and os.access(executable, os.X_OK)
            and configured_helper.resolve() == helper.resolve()
        )
    except OSError:
        return False


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    existing_mode = path.stat().st_mode & 0o777 if path.exists() else None
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        if existing_mode is not None:
            temporary_path.chmod(existing_mode)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _as_hook_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    return [value]


def _is_sopify_hook(entry: Any) -> bool:
    if not isinstance(entry, dict):
        return False
    return SOPIFY_HOOK_MARKER in str(entry.get("command") or "").replace("\\", "/")
