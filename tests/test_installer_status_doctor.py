# Test classification: distribution
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from installer.hosts import get_host_capability, iter_declared_hosts, iter_installable_hosts
from installer.hosts.base import install_host_assets
from installer.hosts.claude import CLAUDE_ADAPTER
from installer.hosts.codex import CODEX_ADAPTER
from installer.hosts.cursor import CURSOR_ADAPTER
from installer.inspection import build_doctor_payload, build_status_payload, render_doctor_text, render_status_text
from installer.models import InstallError
from installer.payload import _REQUIRED_BUNDLE_CAPABILITIES, install_global_payload, run_workspace_bootstrap
from installer.validate import validate_host_install, validate_payload_install
from scripts.sopify_doctor import main as doctor_main
from scripts.sopify_status import main as status_main
from scripts.install_sopify import run_install


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _seed_workspace_state(workspace_root: Path) -> None:
    state_root = workspace_root / ".sopify" / "state"
    _write_json(
        state_root / "active_plan.json",
        {"plan_id": "20260320_helloagents_integration_enhancements"},
    )
    _write_json(
        state_root / "current_handoff.json",
        {"required_host_action": "continue_host_develop"},
    )



class HostCapabilityRegistryTests(unittest.TestCase):
    def test_registry_returns_complete_capabilities_for_declared_hosts(self) -> None:
        codex = get_host_capability("codex")
        claude = get_host_capability("claude")

        self.assertEqual(codex.support_tier.value, "protocol_verified")
        self.assertEqual(claude.support_tier.value, "protocol_verified")
        self.assertTrue(codex.install_enabled)
        self.assertTrue(claude.install_enabled)
        self.assertIn("handoff_first", [feature.value for feature in claude.verified_features])

        retired_host = "tr" + "ae-cn"
        with self.assertRaisesRegex(ValueError, f"Unsupported host capability: {retired_host}"):
            get_host_capability(retired_host)

    def test_qoder_capability_contract(self) -> None:
        from installer.hosts import get_host_adapter

        qoder = get_host_capability("qoder")
        adapter = get_host_adapter("qoder")

        self.assertEqual(qoder.support_tier.value, "protocol_verified")
        self.assertTrue(qoder.install_enabled)

        verified = {f.value for f in qoder.verified_features}
        self.assertEqual(verified, {"prompt_install", "payload_install", "workspace_bootstrap", "handoff_first", "host_bridge"})

        enhancements = {e.value for e in qoder.declared_enhancements}
        self.assertEqual(enhancements, {"continuation", "interaction", "audit"})

        self.assertEqual(adapter.default_language, "zh-CN")
        self.assertEqual(adapter.destination_dirname, ".qoder")
        self.assertEqual(adapter.header_filename, "AGENTS.md")
        self.assertEqual(adapter.config_dir, "~/.qoder")

    def test_installable_hosts_only_return_install_enabled_entries(self) -> None:
        installable = [capability.host_id for capability in iter_installable_hosts()]
        declared = [capability.host_id for capability in iter_declared_hosts()]

        self.assertEqual(set(installable), {"codex", "claude", "copilot", "cursor", "qoder"})
        self.assertEqual(set(declared), {"codex", "claude", "copilot", "cursor", "qoder"})

    def test_cursor_capability_is_baseline_split_surface(self) -> None:
        cursor = get_host_capability("cursor")
        adapter = CURSOR_ADAPTER

        self.assertEqual(cursor.support_tier.value, "baseline_supported")
        self.assertTrue(cursor.install_enabled)
        self.assertEqual(adapter.destination_dirname, ".cursor")
        self.assertEqual(
            adapter.instruction_file_relpath,
            ".cursor/plugins/local/sopify/rules/sopify.mdc",
        )
        self.assertTrue(adapter.is_user_plugin_scope)
        self.assertFalse(adapter.is_workspace_scope)
        self.assertFalse(adapter.requires_workspace)
        self.assertIsNone(adapter.skills_cli_agent)
        self.assertEqual(adapter.skill_install_dirname, ".cursor/skills")
        self.assertEqual(cursor.smoke_targets, ())
        self.assertEqual(tuple(mode.value for mode in cursor.entry_modes), ("prompt_only", "hooks"))
        self.assertIn("cursor_hooks_present", cursor.doctor_checks)

    def test_cursor_install_proves_split_paths_without_touching_settings(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)
            settings = home_root / ".cursor" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text('{"proxy": "127.0.0.1:7898"}\n', encoding="utf-8")

            result = run_install(
                target_value="cursor",
                workspace_value=str(workspace_root),
                repo_root=REPO_ROOT,
                home_root=home_root,
            )

            plugin_root = home_root / ".cursor" / "plugins" / "local" / "sopify"
            manifest = plugin_root / ".cursor-plugin" / "plugin.json"
            rule = plugin_root / "rules" / "sopify.mdc"
            readme = plugin_root / "README.md"
            skill_root = home_root / ".cursor" / "skills" / "sopify"
            self.assertTrue(manifest.is_file())
            self.assertTrue(rule.is_file())
            self.assertTrue(readme.is_file())
            manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertNotIn("rules", manifest_payload)
            self.assertIn("adaptive workflow layer", readme.read_text(encoding="utf-8"))
            self.assertIn("BASELINE_SUPPORTED", readme.read_text(encoding="utf-8"))
            self.assertTrue((skill_root / "analyze" / "SKILL.md").is_file())
            self.assertTrue((skill_root / "design" / "SKILL.md").is_file())
            self.assertTrue((skill_root / "develop" / "SKILL.md").is_file())
            self.assertTrue((skill_root / "kb" / "SKILL.md").is_file())
            self.assertTrue((skill_root / "templates" / "SKILL.md").is_file())
            self.assertTrue((skill_root / "references" / "shared-writing-dna.md").is_file())
            self.assertTrue((skill_root / "references" / "output-contract.md").is_file())
            self.assertTrue((skill_root / "analyze" / "scripts" / "score_requirement.py").is_file())
            self.assertTrue((home_root / ".cursor" / "sopify" / "payload-manifest.json").is_file())
            self.assertTrue((home_root / ".cursor" / "sopify" / "bundles").is_dir())
            self.assertEqual(settings.read_text(encoding="utf-8"), '{"proxy": "127.0.0.1:7898"}\n')
            self.assertFalse((home_root / ".cursor" / "AGENTS.md").exists())
            self.assertFalse((workspace_root / ".cursor" / "skills").exists())
            self.assertFalse((workspace_root / ".cursor").exists())
            self.assertFalse((workspace_root / ".sopify").exists())
            self.assertFalse((workspace_root / ".cursor" / "hooks.json").exists())
            self.assertTrue((home_root / ".cursor" / "hooks.json").is_file())
            self.assertTrue((home_root / ".cursor" / "sopify" / "helpers" / "cursor_hook.py").is_file())
            self.assertIn("alwaysApply: true", rule.read_text(encoding="utf-8"))
            self.assertIn("~/.cursor/skills/sopify/references/shared-writing-dna.md", rule.read_text(encoding="utf-8"))
            self.assertIn("Cursor IDE", rule.read_text(encoding="utf-8"))
            self.assertIn("does not automatically load", rule.read_text(encoding="utf-8"))
            self.assertNotIn(str(skill_root), rule.read_text(encoding="utf-8"))
            self.assertIsNone(result.workspace_bootstrap)
            self.assertEqual(result.target.host, "cursor")

            doctor = build_doctor_payload(home_root=home_root, workspace_root=workspace_root)
            cursor_checks = {check["check_id"]: check for check in doctor["checks"] if check.get("host_id") == "cursor"}
            self.assertEqual(cursor_checks["cursor_plugin_present"]["status"], "pass")
            self.assertEqual(cursor_checks["global_skill_tree_present"]["status"], "pass")
            self.assertEqual(cursor_checks["payload_present"]["status"], "pass")
            self.assertEqual(cursor_checks["cursor_hooks_present"]["status"], "pass")
            self.assertEqual(cursor_checks["cursor_ide_behavior"]["reason_code"], "BLACK_BOX_NOT_VERIFIED")
            self.assertEqual(cursor_checks["cursor_cli_behavior"]["reason_code"], "BLACK_BOX_NOT_VERIFIED")
            self.assertNotEqual(doctor["summary"]["overall_status"], "fail")
            cursor_fails = [
                check
                for check in doctor["checks"]
                if check.get("host_id") == "cursor" and check["status"] == "fail"
            ]
            self.assertEqual(cursor_fails, [])

            status = build_status_payload(home_root=home_root, workspace_root=workspace_root)
            cursor_status = next(host for host in status["hosts"] if host["host_id"] == "cursor")
            self.assertEqual(cursor_status["state"]["installed"], "yes")
            self.assertEqual(cursor_status["state"]["configured"], "yes")
            self.assertEqual(cursor_status["state"]["workspace_bundle_healthy"], "not_requested")

            readme.unlink()
            doctor_without_readme = build_doctor_payload(
                home_root=home_root,
                workspace_root=workspace_root,
            )
            plugin_check = next(
                check
                for check in doctor_without_readme["checks"]
                if check.get("host_id") == "cursor"
                and check["check_id"] == "cursor_plugin_present"
            )
            self.assertEqual(plugin_check["status"], "pass")

            status_without_readme = build_status_payload(
                home_root=home_root,
                workspace_root=workspace_root,
            )
            cursor_without_readme = next(
                host
                for host in status_without_readme["hosts"]
                if host["host_id"] == "cursor"
            )
            self.assertEqual(cursor_without_readme["state"]["installed"], "yes")

            repair_result = run_install(
                target_value="cursor",
                workspace_value=str(workspace_root),
                repo_root=REPO_ROOT,
                home_root=home_root,
            )
            self.assertEqual(repair_result.host_install.action, "updated")
            self.assertTrue(readme.is_file())

    def test_cursor_install_preflights_invalid_hooks_before_any_product_write(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)
            hooks = home_root / ".cursor" / "hooks.json"
            settings = home_root / ".cursor" / "settings.json"
            hooks.parent.mkdir(parents=True)
            hooks.write_text("{not json\n", encoding="utf-8")
            settings.write_text('{"proxy": "127.0.0.1:7898"}\n', encoding="utf-8")

            with self.assertRaisesRegex(InstallError, "Refusing to overwrite invalid Cursor hooks.json"):
                run_install(
                    target_value="cursor",
                    workspace_value=str(workspace_root),
                    repo_root=REPO_ROOT,
                    home_root=home_root,
                )

            self.assertEqual(hooks.read_text(encoding="utf-8"), "{not json\n")
            self.assertEqual(settings.read_text(encoding="utf-8"), '{"proxy": "127.0.0.1:7898"}\n')
            self.assertFalse((home_root / ".cursor" / "plugins" / "local" / "sopify").exists())
            self.assertFalse((home_root / ".cursor" / "skills" / "sopify").exists())
            self.assertFalse((home_root / ".cursor" / "sopify").exists())

    def test_cursor_doctor_rejects_stale_or_fail_closed_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)
            run_install(
                target_value="cursor",
                workspace_value=str(workspace_root),
                repo_root=REPO_ROOT,
                home_root=home_root,
            )
            hooks_path = home_root / ".cursor" / "hooks.json"
            hooks_payload = json.loads(hooks_path.read_text(encoding="utf-8"))
            for event in ("sessionStart", "preToolUse", "beforeShellExecution"):
                hooks_payload["hooks"][event][-1] = {
                    "command": "/missing/python /missing/.cursor/sopify/helpers/cursor_hook.py",
                    "failClosed": True,
                }
            hooks_path.write_text(json.dumps(hooks_payload), encoding="utf-8")

            doctor = build_doctor_payload(home_root=home_root, workspace_root=workspace_root)
            cursor_hooks = next(
                check
                for check in doctor["checks"]
                if check.get("host_id") == "cursor" and check["check_id"] == "cursor_hooks_present"
            )

            self.assertEqual(cursor_hooks["status"], "fail")
            self.assertTrue(any("Stale or unsafe" in item for item in cursor_hooks.get("evidence", [])))

    def test_user_plugin_surface_is_not_a_generic_hook_framework(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)
            future_adapter = replace(
                CURSOR_ADAPTER,
                host_name="future-project-rules",
                destination_dirname=".future-project-rules",
                config_dir="~/.future-project-rules",
                skill_install_dirname=".future-project-rules/skills",
            )

            with patch("scripts.install_sopify.get_host_adapter", return_value=future_adapter):
                with self.assertRaisesRegex(InstallError, "incompatible host adapter"):
                    run_install(
                        target_value="cursor",
                        workspace_value=str(workspace_root),
                        repo_root=REPO_ROOT,
                        home_root=home_root,
                    )

            self.assertFalse((home_root / ".cursor" / "hooks.json").exists())
            self.assertFalse(
                (home_root / ".future-project-rules" / "sopify" / "helpers" / "cursor_hook.py").exists()
            )

    def test_cursor_doctor_skips_when_only_ide_settings_exist(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)
            settings = home_root / ".cursor" / "settings.json"
            settings.parent.mkdir(parents=True)
            settings.write_text("{}\n", encoding="utf-8")

            doctor = build_doctor_payload(home_root=home_root, workspace_root=None)
            cursor_checks = {check["check_id"]: check for check in doctor["checks"] if check.get("host_id") == "cursor"}
            self.assertEqual(cursor_checks["cursor_plugin_present"]["status"], "skip")
            self.assertEqual(cursor_checks["global_skill_tree_present"]["status"], "skip")
            self.assertEqual(cursor_checks["payload_present"]["status"], "skip")
            self.assertEqual(cursor_checks["cursor_hooks_present"]["status"], "skip")
            self.assertNotEqual(cursor_checks["cursor_plugin_present"]["status"], "fail")
            self.assertEqual(doctor["summary"]["fail_count"], 0)

            status = build_status_payload(home_root=home_root, workspace_root=None)
            cursor_status = next(host for host in status["hosts"] if host["host_id"] == "cursor")
            self.assertEqual(cursor_status["state"]["installed"], "no")

    def test_cursor_doctor_does_not_skip_a_stale_sopify_hook_only_install(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)
            hooks_path = home_root / ".cursor" / "hooks.json"
            _write_json(
                hooks_path,
                {
                    "version": 1,
                    "hooks": {
                        "sessionStart": [
                            {
                                "command": "/missing/.cursor/sopify/helpers/cursor_hook.py",
                                "failClosed": False,
                            }
                        ]
                    },
                },
            )

            doctor = build_doctor_payload(home_root=home_root, workspace_root=None)
            cursor_hooks = next(
                check
                for check in doctor["checks"]
                if check.get("host_id") == "cursor" and check["check_id"] == "cursor_hooks_present"
            )

            self.assertEqual(cursor_hooks["status"], "fail")

    def test_cursor_status_installed_requires_plugin_and_skills(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)
            run_install(
                target_value="cursor",
                workspace_value=str(workspace_root),
                repo_root=REPO_ROOT,
                home_root=home_root,
            )
            plugin_rule = (
                home_root / ".cursor" / "plugins" / "local" / "sopify" / "rules" / "sopify.mdc"
            )
            plugin_rule.unlink()

            missing_rule = build_status_payload(home_root=home_root, workspace_root=workspace_root)
            cursor_missing = next(host for host in missing_rule["hosts"] if host["host_id"] == "cursor")
            self.assertEqual(cursor_missing["state"]["installed"], "no")

            run_install(
                target_value="cursor",
                workspace_value=None,
                repo_root=REPO_ROOT,
                home_root=home_root,
            )
            (home_root / ".cursor" / "skills" / "sopify" / "analyze" / "SKILL.md").unlink()
            missing_skill = build_status_payload(home_root=home_root, workspace_root=None)
            cursor_missing_skill = next(host for host in missing_skill["hosts"] if host["host_id"] == "cursor")
            self.assertEqual(cursor_missing_skill["state"]["installed"], "no")

            for required_path in (
                home_root / ".cursor" / "skills" / "sopify" / "references" / "output-contract.md",
                home_root
                / ".cursor"
                / "skills"
                / "sopify"
                / "analyze"
                / "scripts"
                / "score_requirement.py",
            ):
                with self.subTest(required_path=required_path):
                    run_install(
                        target_value="cursor",
                        workspace_value=None,
                        repo_root=REPO_ROOT,
                        home_root=home_root,
                    )
                    required_path.unlink()
                    incomplete = build_status_payload(home_root=home_root, workspace_root=None)
                    cursor_incomplete = next(
                        host for host in incomplete["hosts"] if host["host_id"] == "cursor"
                    )
                    self.assertEqual(cursor_incomplete["state"]["installed"], "no")


class StatusDoctorContractTests(unittest.TestCase):
    def test_status_payload_supports_workspace_not_requested(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            payload = build_status_payload(home_root=home_root, workspace_root=None)

            self.assertFalse(payload["workspace_state"]["requested"])
            self.assertEqual(payload["workspace_state"]["bootstrap_mode"], "on_first_project_trigger")
            self.assertEqual(payload["hosts"][0]["state"]["workspace_bundle_healthy"], "not_requested")
            self.assertEqual(payload["hosts"][0]["payload_bundle"]["source_kind"], "global_active")
            self.assertEqual(payload["hosts"][0]["payload_bundle"]["reason_code"], "PAYLOAD_BUNDLE_READY")
            rendered = render_status_text(payload)
            self.assertIn("requested: no", rendered)
            self.assertIn("will bootstrap on first project trigger", rendered)
            self.assertIn("payload_bundle=global_active (PAYLOAD_BUNDLE_READY)", rendered)

    def test_doctor_payload_supports_workspace_not_requested(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            payload = build_doctor_payload(home_root=home_root, workspace_root=None)

            workspace_check = next(
                check
                for check in payload["checks"]
                if check["host_id"] == "codex" and check["check_id"] == "workspace_bundle_manifest"
            )
            self.assertEqual(workspace_check["status"], "skip")
            self.assertEqual(workspace_check["reason_code"], "WORKSPACE_NOT_REQUESTED")
            self.assertEqual(
                workspace_check["recommendation"],
                "Workspace bootstrap was not requested. Trigger Sopify in a project workspace to bootstrap on demand.",
            )
            payload_bundle_check = next(
                check
                for check in payload["checks"]
                if check["host_id"] == "codex" and check["check_id"] == "payload_bundle_resolution"
            )
            self.assertEqual(payload_bundle_check["status"], "pass")
            self.assertEqual(payload_bundle_check["reason_code"], "PAYLOAD_BUNDLE_READY")
            self.assertEqual(payload_bundle_check["source_kind"], "global_active")

    def test_status_and_doctor_surface_legacy_payload_bundle_layout(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            payload_root = CODEX_ADAPTER.payload_root(home_root)
            payload_manifest = json.loads((payload_root / "payload-manifest.json").read_text(encoding="utf-8"))
            active_version = payload_manifest["active_version"]
            legacy_bundle_root = payload_root / "bundle"
            shutil.copytree(payload_root / "bundles" / active_version, legacy_bundle_root)
            _write_json(
                payload_root / "payload-manifest.json",
                {
                    "schema_version": "1",
                    "payload_version": active_version,
                    "bundle_version": active_version,
                    "bundle_manifest": "bundle/manifest.json",
                    "bundle_template_dir": "bundle",
                    "helper_entry": "helpers/bootstrap_workspace.py",
                },
            )

            status_payload = build_status_payload(home_root=home_root, workspace_root=None)
            self.assertEqual(status_payload["hosts"][0]["payload_bundle"]["source_kind"], "legacy_layout")
            self.assertEqual(status_payload["hosts"][0]["payload_bundle"]["reason_code"], "PAYLOAD_BUNDLE_READY")
            rendered = render_status_text(status_payload)
            self.assertIn("payload_bundle=legacy_layout (PAYLOAD_BUNDLE_READY)", rendered)
            self.assertNotIn("payload_outcome:", rendered)

            doctor_payload = build_doctor_payload(home_root=home_root, workspace_root=None)
            payload_bundle_check = next(
                check
                for check in doctor_payload["checks"]
                if check["host_id"] == "codex" and check["check_id"] == "payload_bundle_resolution"
            )
            self.assertEqual(payload_bundle_check["status"], "pass")
            self.assertEqual(payload_bundle_check["reason_code"], "PAYLOAD_BUNDLE_READY")
            self.assertEqual(payload_bundle_check["source_kind"], "legacy_layout")
            self.assertNotIn("outcome:", render_doctor_text(doctor_payload))

    def test_status_and_doctor_fail_closed_for_non_object_payload_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            payload_root = CODEX_ADAPTER.payload_root(home_root)
            (payload_root / "payload-manifest.json").write_text("[1]", encoding="utf-8")

            status_payload = build_status_payload(home_root=home_root, workspace_root=None)
            self.assertEqual(status_payload["hosts"][0]["payload_bundle"]["source_kind"], "unresolved")
            self.assertEqual(status_payload["hosts"][0]["payload_bundle"]["reason_code"], "GLOBAL_INDEX_CORRUPTED")
            self.assertEqual(status_payload["hosts"][0]["payload_bundle"]["primary_code"], "global_index_corrupted")
            self.assertEqual(status_payload["hosts"][0]["payload_bundle"]["action_level"], "fail_closed")
            self.assertIn("payload_outcome: global_index_corrupted [fail_closed]", render_status_text(status_payload))

            doctor_payload = build_doctor_payload(home_root=home_root, workspace_root=None)
            payload_bundle_check = next(
                check
                for check in doctor_payload["checks"]
                if check["host_id"] == "codex" and check["check_id"] == "payload_bundle_resolution"
            )
            self.assertEqual(payload_bundle_check["status"], "fail")
            self.assertEqual(payload_bundle_check["reason_code"], "GLOBAL_INDEX_CORRUPTED")
            self.assertEqual(payload_bundle_check["source_kind"], "unresolved")
            self.assertEqual(payload_bundle_check["primary_code"], "global_index_corrupted")
            self.assertEqual(payload_bundle_check["action_level"], "fail_closed")
            self.assertIn("outcome: global_index_corrupted [fail_closed]", render_doctor_text(doctor_payload))

    def test_status_and_doctor_fail_closed_for_versioned_layout_missing_active_version(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            payload_root = CODEX_ADAPTER.payload_root(home_root)
            payload_manifest = json.loads((payload_root / "payload-manifest.json").read_text(encoding="utf-8"))
            payload_manifest.pop("active_version", None)
            (payload_root / "payload-manifest.json").write_text(
                json.dumps(payload_manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            status_payload = build_status_payload(home_root=home_root, workspace_root=None)
            self.assertEqual(status_payload["hosts"][0]["payload_bundle"]["source_kind"], "global_active")
            self.assertEqual(status_payload["hosts"][0]["payload_bundle"]["reason_code"], "GLOBAL_INDEX_CORRUPTED")

            doctor_payload = build_doctor_payload(home_root=home_root, workspace_root=None)
            payload_bundle_check = next(
                check
                for check in doctor_payload["checks"]
                if check["host_id"] == "codex" and check["check_id"] == "payload_bundle_resolution"
            )
            self.assertEqual(payload_bundle_check["status"], "fail")
            self.assertEqual(payload_bundle_check["reason_code"], "GLOBAL_INDEX_CORRUPTED")
            self.assertEqual(payload_bundle_check["source_kind"], "global_active")

    def test_status_json_contains_required_contract_and_workspace_state(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)
            _seed_workspace_state(workspace_root)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)
            validate_host_install(CODEX_ADAPTER, home_root=home_root)
            validate_payload_install(CODEX_ADAPTER.payload_root(home_root))

            payload = build_status_payload(home_root=home_root, workspace_root=workspace_root)

            self.assertEqual(payload["schema_version"], "2")
            self.assertIn("hosts", payload)
            self.assertIn("state", payload)
            self.assertIn("workspace_state", payload)
            self.assertEqual(payload["workspace_state"]["active_plan"], "20260320_helloagents_integration_enhancements")
            self.assertEqual(payload["workspace_state"]["pending_checkpoint"], "continue_host_develop")
            self.assertEqual(payload["state"]["overall_status"], "partial")
            self.assertEqual(payload["hosts"][0]["verified_features"], ["prompt_install", "payload_install", "workspace_bootstrap", "handoff_first", "host_bridge"])
            self.assertEqual(
                set(payload["hosts"][0]["state"].keys()),
                {"installed", "configured", "workspace_bundle_healthy"},
            )
            self.assertIn("workspace_bundle", payload["hosts"][0])
            self.assertEqual(payload["hosts"][0]["state"]["configured"], "yes")
            self.assertEqual(payload["hosts"][0]["state"]["workspace_bundle_healthy"], "no")
            self.assertNotIn("verified", payload["hosts"][0]["state"])

    def test_doctor_json_contains_reason_codes_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            payload = build_doctor_payload(home_root=home_root, workspace_root=workspace_root)

            self.assertEqual(payload["schema_version"], "1")
            self.assertIn("checks", payload)
            self.assertIn("summary", payload)
            self.assertTrue(payload["checks"])
            check = payload["checks"][0]
            self.assertIn("check_id", check)
            self.assertIn("status", check)
            self.assertIn("reason_code", check)
            self.assertIn(check["reason_code"], {"ok", "MISSING_REQUIRED_FILE", "MISSING_BUNDLE", "UNEXPECTED_ERROR"})


    def test_status_json_reports_ready_when_workspace_bundle_is_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)
            run_workspace_bootstrap(CODEX_ADAPTER.payload_root(home_root), workspace_root)

            payload = build_status_payload(home_root=home_root, workspace_root=workspace_root)

            self.assertEqual(payload["schema_version"], "2")
            self.assertEqual(payload["state"]["overall_status"], "ready")
            self.assertEqual(payload["state"]["workspace_bundle_healthy_hosts"], ["codex"])
            self.assertEqual(payload["hosts"][0]["state"]["workspace_bundle_healthy"], "yes")

    def test_status_and_doctor_treat_stub_only_workspace_as_ready_when_global_bundle_resolves(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)
            run_workspace_bootstrap(CODEX_ADAPTER.payload_root(home_root), workspace_root)

            bundle_root = workspace_root / ".sopify"
            for name in ("sopify_contracts", "sopify_writer"):
                target = bundle_root / name
                if target.exists():
                    import shutil

                    shutil.rmtree(target)

            status_payload = build_status_payload(home_root=home_root, workspace_root=workspace_root)
            self.assertEqual(status_payload["hosts"][0]["state"]["workspace_bundle_healthy"], "yes")
            self.assertEqual(status_payload["hosts"][0]["workspace_bundle"]["primary_code"], "stub_selected")
            self.assertEqual(status_payload["hosts"][0]["workspace_bundle"]["action_level"], "continue")
            self.assertIn("workspace_outcome: stub_selected [continue]", render_status_text(status_payload))

            doctor_payload = build_doctor_payload(home_root=home_root, workspace_root=workspace_root)
            workspace_check = next(
                check
                for check in doctor_payload["checks"]
                if check["host_id"] == "codex" and check["check_id"] == "workspace_bundle_manifest"
            )
            self.assertEqual(workspace_check["status"], "pass")
            self.assertEqual(workspace_check["reason_code"], "STUB_SELECTED")
            self.assertEqual(workspace_check["primary_code"], "stub_selected")
            self.assertEqual(workspace_check["action_level"], "continue")
            self.assertIn("NON_GIT_WORKSPACE", workspace_check["evidence"])
            self.assertIn("ignore_mode=noop", workspace_check["evidence"])
            self.assertIn("outcome: stub_selected [continue]", render_doctor_text(doctor_payload))

    def test_doctor_resolves_workspace_capabilities_from_global_bundle_when_workspace_manifest_is_stub_only(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)
            run_workspace_bootstrap(CODEX_ADAPTER.payload_root(home_root), workspace_root)

            workspace_manifest = json.loads((workspace_root / ".sopify" / "sopify.json").read_text(encoding="utf-8"))
            self.assertEqual(workspace_manifest["capabilities"], [])
            self.assertNotIn("limits", workspace_manifest)

            doctor_payload = build_doctor_payload(home_root=home_root, workspace_root=workspace_root)
            handoff_check = next(
                check
                for check in doctor_payload["checks"]
                if check["host_id"] == "codex" and check["check_id"] == "workspace_handoff_first"
            )
            self.assertEqual(handoff_check["status"], "pass")
            self.assertEqual(handoff_check["reason_code"], "ok")

    def test_doctor_fail_closes_when_selected_global_bundle_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)
            run_workspace_bootstrap(CODEX_ADAPTER.payload_root(home_root), workspace_root)

            payload_root = CODEX_ADAPTER.payload_root(home_root)
            payload_manifest = json.loads((payload_root / "payload-manifest.json").read_text(encoding="utf-8"))
            selected_version = str(payload_manifest["active_version"])
            selected_bundle_root = payload_root / "bundles" / selected_version
            shutil.rmtree(selected_bundle_root)

            doctor_payload = build_doctor_payload(home_root=home_root, workspace_root=workspace_root)
            workspace_check = next(
                check
                for check in doctor_payload["checks"]
                if check["host_id"] == "codex" and check["check_id"] == "workspace_bundle_manifest"
            )
            handoff_check = next(
                check
                for check in doctor_payload["checks"]
                if check["host_id"] == "codex" and check["check_id"] == "workspace_handoff_first"
            )
            payload_bundle_check = next(
                check
                for check in doctor_payload["checks"]
                if check["host_id"] == "codex" and check["check_id"] == "payload_bundle_resolution"
            )

            self.assertEqual(workspace_check["reason_code"], "GLOBAL_BUNDLE_MISSING")
            self.assertEqual(handoff_check["status"], "fail")
            self.assertEqual(handoff_check["reason_code"], "GLOBAL_BUNDLE_MISSING")
            self.assertEqual(payload_bundle_check["reason_code"], "GLOBAL_BUNDLE_MISSING")

    def test_doctor_recommends_on_demand_bootstrap_without_public_workspace_flag(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            doctor_payload = build_doctor_payload(home_root=home_root, workspace_root=workspace_root)
            workspace_check = next(
                check
                for check in doctor_payload["checks"]
                if check["host_id"] == "codex" and check["check_id"] == "workspace_bundle_manifest"
            )

            self.assertEqual(workspace_check["reason_code"], "MISSING_BUNDLE")
            self.assertIn("Trigger Sopify there to bootstrap on demand", workspace_check["recommendation"])
            self.assertNotIn("--workspace", workspace_check["recommendation"])

    def test_status_and_doctor_surface_partial_bundle_damage_as_replace_required(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)
            run_workspace_bootstrap(CODEX_ADAPTER.payload_root(home_root), workspace_root)

            payload_root = CODEX_ADAPTER.payload_root(home_root)
            payload_manifest = json.loads((payload_root / "payload-manifest.json").read_text(encoding="utf-8"))
            active_version = payload_manifest["active_version"]
            bundle_root = workspace_root / ".sopify"
            for name in ("sopify_contracts", "sopify_writer"):
                shutil.copytree(payload_root / "bundles" / active_version / name, bundle_root / name)

            doctor_payload = build_doctor_payload(home_root=home_root, workspace_root=workspace_root)
            workspace_check = next(
                check
                for check in doctor_payload["checks"]
                if check["host_id"] == "codex" and check["check_id"] == "workspace_bundle_manifest"
            )
            self.assertEqual(workspace_check["status"], "pass")
            self.assertEqual(workspace_check["reason_code"], "STUB_SELECTED")
            self.assertIn("NON_GIT_WORKSPACE", workspace_check["evidence"])
            self.assertNotIn("recommendation", workspace_check)

    def test_status_cli_json_output_contains_hosts_and_workspace_state(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)
            _seed_workspace_state(workspace_root)

            install_host_assets(CLAUDE_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="EN")
            install_global_payload(CLAUDE_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            completed = _run_script(
                status_main,
                [
                    "--format",
                    "json",
                    "--home-root",
                    str(home_root),
                    "--workspace-root",
                    str(workspace_root),
                ],
            )
            payload = json.loads(completed)
            self.assertEqual(payload["schema_version"], "2")
            self.assertIn("hosts", payload)
            self.assertIn("workspace_state", payload)

    def test_doctor_cli_json_output_contains_checks_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)

            install_host_assets(CLAUDE_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="EN")
            install_global_payload(CLAUDE_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            completed = _run_script(
                doctor_main,
                [
                    "--format",
                    "json",
                    "--home-root",
                    str(home_root),
                    "--workspace-root",
                    str(workspace_root),
                ],
            )
            payload = json.loads(completed)
            self.assertEqual(payload["schema_version"], "1")
            self.assertIn("checks", payload)
            self.assertIn("summary", payload)


    def test_status_text_renders_human_labels_not_raw_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)
            state_root = workspace_root / ".sopify" / "state"
            _write_json(
                state_root / "active_plan.json",
                {"plan_id": "p"},
            )
            _write_json(
                state_root / "current_handoff.json",
                {"required_host_action": "answer_questions"},
            )

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            status_payload = build_status_payload(home_root=home_root, workspace_root=workspace_root)
            rendered = render_status_text(status_payload)

            self.assertIn("pending_checkpoint: awaiting supplemental info", rendered)
            self.assertNotIn("answer_questions", rendered)

    def test_status_text_renders_mapped_checkpoint_labels(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)
            _seed_workspace_state(workspace_root)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            status_payload = build_status_payload(home_root=home_root, workspace_root=workspace_root)
            rendered = render_status_text(status_payload)

            self.assertIn("pending_checkpoint: ready to continue", rendered)
            self.assertNotIn("continue_host_develop", rendered)


def _run_script(entrypoint, argv: list[str]) -> str:
    from io import StringIO
    from contextlib import redirect_stdout

    buffer = StringIO()
    with redirect_stdout(buffer):
        exit_code = entrypoint(argv)
    if exit_code != 0:
        raise AssertionError(f"Expected exit code 0, got {exit_code}")
    return buffer.getvalue()


class TestWorkspaceVersionClassifier(unittest.TestCase):
    """W0.10a: tests for the 4-state workspace version classifier."""

    def setUp(self) -> None:
        from installer.inspection import classify_workspace_version_state
        self.classify = classify_workspace_version_state

    def test_up_to_date(self) -> None:
        result = self.classify(
            workspace_pin="2026-06-10.191940",
            active_version="2026-06-10.191940",
            bundle_resolvable=True,
        )
        self.assertEqual(result, "up_to_date")

    def test_pinned_old_but_healthy(self) -> None:
        result = self.classify(
            workspace_pin="2026-05-31.142150",
            active_version="2026-06-10.191940",
            bundle_resolvable=True,
        )
        self.assertEqual(result, "pinned_old_but_healthy")

    def test_stale(self) -> None:
        result = self.classify(
            workspace_pin="2026-05-31.142150",
            active_version="2026-06-10.191940",
            bundle_resolvable=False,
        )
        self.assertEqual(result, "stale")

    def test_broken_pin_null(self) -> None:
        result = self.classify(
            workspace_pin=None,
            active_version="2026-06-10.191940",
            bundle_resolvable=True,
        )
        self.assertEqual(result, "broken")

    def test_broken_active_null(self) -> None:
        result = self.classify(
            workspace_pin="2026-06-10.191940",
            active_version=None,
            bundle_resolvable=True,
        )
        self.assertEqual(result, "broken")

    def test_broken_both_null(self) -> None:
        result = self.classify(
            workspace_pin=None,
            active_version=None,
            bundle_resolvable=False,
        )
        self.assertEqual(result, "broken")

    def test_broken_pin_empty_string(self) -> None:
        result = self.classify(
            workspace_pin="",
            active_version="2026-06-10.191940",
            bundle_resolvable=True,
        )
        self.assertEqual(result, "broken")


class TestVersionStateIntegration(unittest.TestCase):
    """F3: integration tests verifying version_state flows through build_status/doctor_payload."""

    def test_status_pipeline_up_to_date(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as ws_dir:
            home_root = Path(home_dir)
            workspace_root = Path(ws_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            payload_root = CODEX_ADAPTER.payload_root(home_root)
            manifest = json.loads((payload_root / "payload-manifest.json").read_text(encoding="utf-8"))
            active_version = manifest["active_version"]

            _write_json(workspace_root / ".sopify" / "sopify.json", {"bundle_version": active_version})

            payload = build_status_payload(home_root=home_root, workspace_root=workspace_root)
            ws_state = payload["workspace_state"]
            self.assertEqual(ws_state["version_state"], "up_to_date")
            self.assertEqual(ws_state["workspace_pin"], active_version)
            self.assertEqual(ws_state["active_version"], active_version)

            rendered = render_status_text(payload)
            self.assertIn("version_state: aligned", rendered)

    def test_status_pipeline_pinned_old_but_healthy(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as ws_dir:
            home_root = Path(home_dir)
            workspace_root = Path(ws_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            payload_root = CODEX_ADAPTER.payload_root(home_root)
            manifest = json.loads((payload_root / "payload-manifest.json").read_text(encoding="utf-8"))
            active_version = manifest["active_version"]

            old_pin = "2026-01-01.000000"
            old_bundle_dir = payload_root / "bundles" / old_pin
            shutil.copytree(payload_root / "bundles" / active_version, old_bundle_dir)

            _write_json(workspace_root / ".sopify" / "sopify.json", {"bundle_version": old_pin})

            payload = build_status_payload(home_root=home_root, workspace_root=workspace_root)
            ws_state = payload["workspace_state"]
            self.assertEqual(ws_state["version_state"], "pinned_old_but_healthy")
            self.assertEqual(ws_state["workspace_pin"], old_pin)
            self.assertEqual(ws_state["active_version"], active_version)

            rendered = render_status_text(payload)
            self.assertIn("version_state: pinned (old but usable)", rendered)

    def test_doctor_pipeline_surfaces_version_hint(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as ws_dir:
            home_root = Path(home_dir)
            workspace_root = Path(ws_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            _write_json(workspace_root / ".sopify" / "sopify.json", {"bundle_version": None})

            payload = build_doctor_payload(home_root=home_root, workspace_root=workspace_root)
            ws_state = payload["workspace_state"]
            self.assertEqual(ws_state["version_state"], "broken")

            rendered = render_doctor_text(payload)
            self.assertIn("Version alignment:", rendered)
            self.assertIn("state: broken", rendered)
            self.assertIn("hint:", rendered)

    def test_status_pipeline_stale(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as ws_dir:
            home_root = Path(home_dir)
            workspace_root = Path(ws_dir)

            install_host_assets(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root, language_directory="CN")
            install_global_payload(CODEX_ADAPTER, repo_root=REPO_ROOT, home_root=home_root)

            old_pin = "2026-01-01.000000"
            _write_json(workspace_root / ".sopify" / "sopify.json", {"bundle_version": old_pin})

            payload = build_status_payload(home_root=home_root, workspace_root=workspace_root)
            ws_state = payload["workspace_state"]
            self.assertEqual(ws_state["version_state"], "stale")
            self.assertEqual(ws_state["workspace_pin"], old_pin)

            rendered = render_status_text(payload)
            self.assertIn("version_state: stale (unresolvable)", rendered)


if __name__ == "__main__":
    unittest.main()
