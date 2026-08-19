# Test classification: distribution
from __future__ import annotations

import io
import json
from pathlib import Path
import shlex
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from installer.cursor_hook import NON_RESUME_CLAUSE, handle, main
from installer.cursor_hooks import install_cursor_user_hooks, sopify_hooks_are_present
from installer.models import InstallError


def _enable_workspace(root: Path) -> Path:
    rule = root / ".cursor" / "rules" / "sopify.mdc"
    rule.parent.mkdir(parents=True, exist_ok=True)
    rule.write_text("---\nalwaysApply: true\n---\n", encoding="utf-8")
    return root


def _payload_with_helper(home_root: Path) -> Path:
    helper = home_root / "sopify" / "helpers" / "cursor_hook.py"
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text("# helper\n", encoding="utf-8")
    return helper.parent.parent


class CursorHookHelperTests(unittest.TestCase):
    def test_noop_without_project_rule(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_dir:
            workspace = Path(workspace_dir)
            self.assertEqual(
                handle(
                    {
                        "hook_event_name": "sessionStart",
                        "workspace_roots": [str(workspace)],
                    }
                ),
                {},
            )
            self.assertEqual(
                handle(
                    {
                        "hook_event_name": "preToolUse",
                        "workspace_roots": [str(workspace)],
                        "tool_name": "StrReplace",
                        "tool_input": {"path": ".sopify/state/active_plan.json"},
                    }
                ),
                {"permission": "allow"},
            )

    def test_session_start_injects_facts_and_non_resume_clause(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_dir:
            workspace = _enable_workspace(Path(workspace_dir))
            state = workspace / ".sopify" / "state"
            state.mkdir(parents=True)
            (state / "active_plan.json").write_text(
                json.dumps({"plan_id": "20260819_cursor_support"}),
                encoding="utf-8",
            )
            (state / "current_handoff.json").write_text(
                json.dumps({"required_host_action": "confirm_decision", "plan_id": "20260819_cursor_support"}),
                encoding="utf-8",
            )
            plan_dir = workspace / ".sopify" / "plan" / "20260819_cursor_support"
            (plan_dir / "receipts").mkdir(parents=True)
            (plan_dir / "plan.md").write_text("# plan\n", encoding="utf-8")
            (plan_dir / "receipts" / "exec_001.json").write_text("{}\n", encoding="utf-8")

            result = handle(
                {
                    "hook_event_name": "sessionStart",
                    "workspace_roots": [str(workspace)],
                }
            )
            context = result["additional_context"]
            self.assertIn("Sopify status facts (not a resume order).", context)
            self.assertIn(NON_RESUME_CLAUSE, context)
            self.assertIn("active_plan: 20260819_cursor_support", context)
            self.assertIn("plan_present: true", context)
            self.assertIn("handoff_action: confirm_decision", context)
            self.assertIn("latest_receipt: exec_001", context)

    def test_session_start_ignores_mismatched_handoff(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_dir:
            workspace = _enable_workspace(Path(workspace_dir))
            state = workspace / ".sopify" / "state"
            state.mkdir(parents=True)
            (state / "active_plan.json").write_text(
                json.dumps({"plan_id": "plan_a"}),
                encoding="utf-8",
            )
            (state / "current_handoff.json").write_text(
                json.dumps({"plan_id": "plan_b", "required_host_action": "confirm_wrong"}),
                encoding="utf-8",
            )
            plan_dir = workspace / ".sopify" / "plan" / "plan_a"
            plan_dir.mkdir(parents=True)
            (plan_dir / "plan.md").write_text("# plan\n", encoding="utf-8")

            result = handle(
                {
                    "hook_event_name": "sessionStart",
                    "workspace_roots": [str(workspace)],
                }
            )

            self.assertIn("active_plan: plan_a", result["additional_context"])
            self.assertIn("handoff_action: (none)", result["additional_context"])
            self.assertNotIn("confirm_wrong", result["additional_context"])

    def test_session_start_selects_receipt_by_timestamp_and_prefers_final(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_dir:
            workspace = _enable_workspace(Path(workspace_dir))
            state = workspace / ".sopify" / "state"
            state.mkdir(parents=True)
            (state / "active_plan.json").write_text(json.dumps({"plan_id": "plan_a"}), encoding="utf-8")
            plan_dir = workspace / ".sopify" / "plan" / "plan_a"
            receipts = plan_dir / "receipts"
            receipts.mkdir(parents=True)
            (plan_dir / "plan.md").write_text("# plan\n", encoding="utf-8")
            (receipts / "exec_002.json").write_text(
                json.dumps(
                    {
                        "timestamp": "2026-08-19T10:00:00+00:00",
                        "provenance": {"receipt_id": "exec_002"},
                    }
                ),
                encoding="utf-8",
            )
            (receipts / "verify_999.json").write_text(
                json.dumps(
                    {
                        "timestamp": "2026-08-19T09:00:00+00:00",
                        "provenance": {"receipt_id": "verify_999"},
                    }
                ),
                encoding="utf-8",
            )
            payload = {"hook_event_name": "sessionStart", "workspace_roots": [str(workspace)]}

            self.assertIn("latest_receipt: exec_002", handle(payload)["additional_context"])

            (receipts / "final.json").write_text("{}\n", encoding="utf-8")
            self.assertIn("latest_receipt: final", handle(payload)["additional_context"])

    def test_session_start_falls_back_to_receipt_number_without_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_dir:
            workspace = _enable_workspace(Path(workspace_dir))
            state = workspace / ".sopify" / "state"
            state.mkdir(parents=True)
            (state / "active_plan.json").write_text(json.dumps({"plan_id": "plan_a"}), encoding="utf-8")
            plan_dir = workspace / ".sopify" / "plan" / "plan_a"
            receipts = plan_dir / "receipts"
            receipts.mkdir(parents=True)
            (plan_dir / "plan.md").write_text("# plan\n", encoding="utf-8")
            (receipts / "exec_100.json").write_text("{}\n", encoding="utf-8")
            (receipts / "verify_999.json").write_text("{}\n", encoding="utf-8")

            result = handle({"hook_event_name": "sessionStart", "workspace_roots": [str(workspace)]})

            self.assertIn("latest_receipt: verify_999", result["additional_context"])

    def test_session_start_does_not_guess_between_multiple_enabled_workspaces(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = _enable_workspace(Path(first_dir))
            second = _enable_workspace(Path(second_dir))
            for workspace, plan_id in ((first, "plan_first"), (second, "plan_second")):
                state = workspace / ".sopify" / "state"
                state.mkdir(parents=True)
                (state / "active_plan.json").write_text(
                    json.dumps({"plan_id": plan_id}),
                    encoding="utf-8",
                )

            ambiguous = handle(
                {
                    "hook_event_name": "sessionStart",
                    "workspace_roots": [str(first), str(second)],
                }
            )["additional_context"]
            self.assertIn("multiple enabled workspaces", ambiguous)
            self.assertNotIn("plan_first", ambiguous)
            self.assertNotIn("plan_second", ambiguous)

            selected = handle(
                {
                    "hook_event_name": "sessionStart",
                    "workspace_roots": [str(first), str(second)],
                    "cwd": str(second),
                }
            )["additional_context"]
            self.assertIn("active_plan: plan_second", selected)
            self.assertNotIn("plan_first", selected)

    def test_pre_tool_use_denies_strreplace_on_state_allows_plan_docs(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_dir:
            workspace = _enable_workspace(Path(workspace_dir))
            deny = handle(
                {
                    "hook_event_name": "preToolUse",
                    "workspace_roots": [str(workspace)],
                    "tool_name": "StrReplace",
                    "tool_input": {
                        "path": str(workspace / ".sopify" / "state" / "active_plan.json"),
                        "old_string": "x",
                        "new_string": "y",
                    },
                }
            )
            self.assertEqual(deny["permission"], "deny")

            receipt_deny = handle(
                {
                    "hook_event_name": "preToolUse",
                    "workspace_roots": [str(workspace)],
                    "tool_name": "Write",
                    "tool_input": {
                        "path": ".sopify/plan/20260819_cursor_support/receipts/verify_001.json",
                        "contents": "{}",
                    },
                }
            )
            self.assertEqual(receipt_deny["permission"], "deny")

            allow = handle(
                {
                    "hook_event_name": "preToolUse",
                    "workspace_roots": [str(workspace)],
                    "tool_name": "StrReplace",
                    "tool_input": {
                        "path": str(workspace / ".sopify" / "plan" / "20260819_cursor_support" / "plan.md"),
                        "old_string": "read .sopify/state/active_plan.json",
                        "new_string": "keep mentioning current_handoff.json",
                    },
                }
            )
            self.assertEqual(allow, {"permission": "allow"})

    def test_pre_tool_use_selects_the_target_workspace_in_multi_root_input(self) -> None:
        with tempfile.TemporaryDirectory() as first_dir, tempfile.TemporaryDirectory() as second_dir:
            first = _enable_workspace(Path(first_dir))
            second = _enable_workspace(Path(second_dir))

            denied = handle(
                {
                    "hook_event_name": "preToolUse",
                    "workspace_roots": [str(first), str(second)],
                    "tool_name": "Write",
                    "tool_input": {"path": str(second / ".sopify" / "state" / "active_plan.json")},
                }
            )

            self.assertEqual(denied["permission"], "deny")

    def test_before_shell_allows_writer_and_denies_obvious_direct_write(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_dir:
            workspace = _enable_workspace(Path(workspace_dir))
            self.assertEqual(
                handle(
                    {
                        "hook_event_name": "beforeShellExecution",
                        "cwd": str(workspace),
                        "command": "python3 -c 'from sopify_writer import ProtocolStore; print(1)'",
                    }
                ),
                {"permission": "allow"},
            )
            denied = handle(
                {
                    "hook_event_name": "beforeShellExecution",
                    "cwd": str(workspace),
                    "command": "echo '{}' > .sopify/state/current_handoff.json",
                }
            )
            self.assertEqual(denied["permission"], "deny")
            marker_bypass = handle(
                {
                    "hook_event_name": "beforeShellExecution",
                    "cwd": str(workspace),
                    "command": "echo '{}' > .sopify/state/active_plan.json # sopify_writer",
                }
            )
            self.assertEqual(marker_bypass["permission"], "deny")
            no_space_redirect = handle(
                {
                    "hook_event_name": "beforeShellExecution",
                    "cwd": str(workspace),
                    "command": "echo '{}' >.sopify/state/active_plan.json",
                }
            )
            self.assertEqual(no_space_redirect["permission"], "deny")
            for command in (
                "echo '{}' >.sopify/plan/plan_a/receipts/exec_003.json",
                "echo '{}' >>.sopify/plan/plan_a/receipts/exec_003.json",
                "echo '{}'>.sopify/plan/plan_a/receipts/exec_003.json",
            ):
                with self.subTest(command=command):
                    receipt_redirect = handle(
                        {
                            "hook_event_name": "beforeShellExecution",
                            "cwd": str(workspace),
                            "command": command,
                        }
                    )
                    self.assertEqual(receipt_redirect["permission"], "deny")
            chained_receipt = handle(
                {
                    "hook_event_name": "beforeShellExecution",
                    "cwd": str(workspace),
                    "command": "echo '{}' > .sopify/plan/plan_a/receipts/exec_003.json && echo done",
                }
            )
            self.assertEqual(chained_receipt["permission"], "deny")
            self.assertEqual(
                handle(
                    {
                        "hook_event_name": "beforeShellExecution",
                        "cwd": str(workspace),
                        "command": "python3 -c \"open('.sopify/state/active_plan.json', 'w').write('x')\"",
                    }
                ),
                {"permission": "allow"},
            )
            self.assertEqual(
                handle(
                    {
                        "hook_event_name": "beforeShellExecution",
                        "cwd": str(workspace),
                        "command": "ls .sopify/state",
                    }
                ),
                {"permission": "allow"},
            )

    def test_unknown_event_does_not_guess_from_payload_shape(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_dir:
            workspace = _enable_workspace(Path(workspace_dir))
            self.assertEqual(
                handle({"workspace_roots": [str(workspace)], "session_id": "session"}),
                {},
            )
            self.assertEqual(
                handle({"workspace_roots": [str(workspace)], "command": "echo hi"}),
                {},
            )

    def test_main_fail_open_on_invalid_json(self) -> None:
        with patch("sys.stdin", io.StringIO("not-json")), patch("sys.stdout", io.StringIO()) as out:
            self.assertEqual(main(), 0)
            self.assertEqual(out.getvalue(), "{}\n")


class CursorUserHooksInstallTests(unittest.TestCase):
    def test_merges_sopify_hooks_and_preserves_existing_entries(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)
            hooks_path = home_root / ".cursor" / "hooks.json"
            hooks_path.parent.mkdir(parents=True)
            hooks_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "hooks": {
                            "sessionStart": [{"command": "echo mine"}],
                            "stop": {"command": "echo leftover"},
                        },
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            payload_root = _payload_with_helper(home_root)
            written = install_cursor_user_hooks(home_root=home_root, payload_root=payload_root)
            payload = json.loads(written.read_text(encoding="utf-8"))
            session_commands = [item["command"] for item in payload["hooks"]["sessionStart"]]
            self.assertIn("echo mine", session_commands)
            self.assertTrue(any("helpers/cursor_hook.py" in command for command in session_commands))
            self.assertEqual(payload["hooks"]["stop"]["command"], "echo leftover")
            self.assertTrue(any("helpers/cursor_hook.py" in item["command"] for item in payload["hooks"]["preToolUse"]))
            self.assertTrue(
                any("helpers/cursor_hook.py" in item["command"] for item in payload["hooks"]["beforeShellExecution"])
            )
            self.assertTrue(all(item.get("failClosed") is False for item in payload["hooks"]["preToolUse"]))
            present, detail = sopify_hooks_are_present(home_root=home_root, payload_root=payload_root)
            self.assertTrue(present)
            self.assertIsNone(detail)

            install_cursor_user_hooks(home_root=home_root, payload_root=payload_root)
            again = json.loads(written.read_text(encoding="utf-8"))
            sopify_session = [item for item in again["hooks"]["sessionStart"] if "helpers/cursor_hook.py" in item["command"]]
            self.assertEqual(len(sopify_session), 1)

    def test_invalid_hooks_json_stops_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)
            hooks_path = home_root / ".cursor" / "hooks.json"
            hooks_path.parent.mkdir(parents=True)
            hooks_path.write_text("{not json\n", encoding="utf-8")
            payload_root = _payload_with_helper(home_root)
            with self.assertRaisesRegex(InstallError, "Refusing to overwrite invalid Cursor hooks.json"):
                install_cursor_user_hooks(home_root=home_root, payload_root=payload_root)
            self.assertEqual(hooks_path.read_text(encoding="utf-8"), "{not json\n")

    def test_stale_or_fail_closed_sopify_hooks_are_not_reported_present(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)
            payload_root = _payload_with_helper(home_root)
            hooks_path = install_cursor_user_hooks(home_root=home_root, payload_root=payload_root)
            payload = json.loads(hooks_path.read_text(encoding="utf-8"))
            for event in ("sessionStart", "preToolUse", "beforeShellExecution"):
                payload["hooks"][event][-1] = {
                    "command": "/missing/python /missing/.cursor/sopify/helpers/cursor_hook.py",
                    "failClosed": True,
                }
            hooks_path.write_text(json.dumps(payload), encoding="utf-8")

            present, detail = sopify_hooks_are_present(home_root=home_root, payload_root=payload_root)

            self.assertFalse(present)
            self.assertIn("Stale or unsafe", detail or "")

    def test_hook_health_accepts_a_different_existing_python_executable(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)
            payload_root = _payload_with_helper(home_root)
            helper = payload_root / "helpers" / "cursor_hook.py"
            executable = home_root / "alternate-python"
            executable.write_text("#!/bin/sh\n", encoding="utf-8")
            executable.chmod(0o755)
            hooks_path = install_cursor_user_hooks(home_root=home_root, payload_root=payload_root)
            payload = json.loads(hooks_path.read_text(encoding="utf-8"))
            command = shlex.join((str(executable), str(helper)))
            for event in ("sessionStart", "preToolUse", "beforeShellExecution"):
                payload["hooks"][event][-1]["command"] = command
            hooks_path.write_text(json.dumps(payload), encoding="utf-8")

            present, detail = sopify_hooks_are_present(home_root=home_root, payload_root=payload_root)

            self.assertTrue(present)
            self.assertIsNone(detail)

    def test_hook_command_quotes_helper_paths_with_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home_root = Path(temp_dir) / "home with spaces"
            payload_root = _payload_with_helper(home_root)

            hooks_path = install_cursor_user_hooks(home_root=home_root, payload_root=payload_root)
            payload = json.loads(hooks_path.read_text(encoding="utf-8"))
            command = payload["hooks"]["sessionStart"][-1]["command"]

            self.assertEqual(shlex.split(command)[1], str((payload_root / "helpers" / "cursor_hook.py").resolve()))


if __name__ == "__main__":
    unittest.main()
