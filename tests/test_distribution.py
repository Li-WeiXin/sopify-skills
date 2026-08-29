# Test classification: distribution
from __future__ import annotations

from io import StringIO
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from installer.distribution import (
    DistributionError,
    DistributionInstallReport,
    DistributionRequest,
    DistributionSourceMetadata,
    render_distribution_result,
    render_distribution_user_error,
    render_distribution_user_result,
    run_distribution_install,
)
from installer.hosts.codex import CODEX_ADAPTER
from installer.inspection import build_doctor_payload, build_status_payload
from scripts.install_sopify import run_install


class DistributionFacadeTests(unittest.TestCase):
    def test_repo_local_and_stable_channels_share_install_truth(self) -> None:
        with tempfile.TemporaryDirectory() as repo_local_home, tempfile.TemporaryDirectory() as stable_home:
            repo_local_request = DistributionRequest(
                target="codex:zh-CN",
                workspace=None,
                ref_override=None,
                interactive=False,
                source_channel="repo-local",
                source_metadata=DistributionSourceMetadata(
                    resolved_ref="working-tree",
                    asset_name="scripts/install_sopify.py",
                ),
            )
            stable_request = DistributionRequest(
                target="codex:zh-CN",
                workspace=None,
                ref_override=None,
                interactive=False,
                source_channel="stable",
                source_metadata=DistributionSourceMetadata(
                    resolved_ref="2026-03-25.101956",
                    asset_name="install.sh",
                ),
            )

            repo_local_report = run_distribution_install(
                request=repo_local_request,
                repo_root=REPO_ROOT,
                home_root=Path(repo_local_home),
                install_executor=run_install,
            )
            stable_report = run_distribution_install(
                request=stable_request,
                repo_root=REPO_ROOT,
                home_root=Path(stable_home),
                install_executor=run_install,
            )

            self.assertEqual(repo_local_report.install_result.target.value, stable_report.install_result.target.value)
            self.assertEqual(repo_local_report.install_result.host_install.version, stable_report.install_result.host_install.version)
            self.assertEqual(repo_local_report.install_result.payload_install.version, stable_report.install_result.payload_install.version)
            self.assertEqual(repo_local_report.status_payload["state"], stable_report.status_payload["state"])
            self.assertEqual(
                repo_local_report.status_payload["hosts"][0]["state"],
                stable_report.status_payload["hosts"][0]["state"],
            )
            self.assertEqual(
                [check["status"] for check in repo_local_report.doctor_payload["checks"] if check.get("host_id") == "codex"],
                [check["status"] for check in stable_report.doctor_payload["checks"] if check.get("host_id") == "codex"],
            )

    def test_distribution_install_without_workspace_marks_bootstrap_on_first_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)
            request = DistributionRequest(
                target="codex:zh-CN",
                workspace=None,
                ref_override=None,
                interactive=False,
                source_channel="repo-local",
                source_metadata=DistributionSourceMetadata(
                    resolved_ref="working-tree",
                    asset_name="scripts/install_sopify.py",
                ),
            )

            report = run_distribution_install(
                request=request,
                repo_root=REPO_ROOT,
                home_root=home_root,
                install_executor=run_install,
            )

            self.assertFalse(report.status_payload["workspace_state"]["requested"])
            self.assertEqual(report.status_payload["workspace_state"]["bootstrap_mode"], "on_first_project_trigger")
            self.assertEqual(report.status_payload["hosts"][0]["state"]["workspace_bundle_healthy"], "not_requested")
            self.assertEqual(report.status_payload["hosts"][0]["payload_bundle"]["source_kind"], "global_active")
            self.assertEqual(report.status_payload["hosts"][0]["payload_bundle"]["reason_code"], "PAYLOAD_BUNDLE_READY")
            rendered = render_distribution_result(report)
            self.assertIn("source channel: repo-local", rendered)
            self.assertIn("payload bundle: source_kind=global_active, reason_code=PAYLOAD_BUNDLE_READY", rendered)
            self.assertIn("workspace: will bootstrap on first project trigger", rendered)
            self.assertIn("workspace bundle: skip (WORKSPACE_NOT_REQUESTED)", rendered)

            user_rendered = render_distribution_user_result(report)
            self.assertIn("Sopify 安装完成。", user_rendered)
            self.assertIn("宿主：Codex（codex:zh-CN）", user_rendered)
            self.assertIn(f"版本：{report.install_result.payload_install.version}", user_rendered)
            self.assertIn("这次没有修改任何项目目录。", user_rendered)
            self.assertIn("输入：~go", user_rendered)
            self.assertNotIn("source channel", user_rendered)
            self.assertNotIn("reason_code", user_rendered)
            self.assertNotIn("workspace_bundle_healthy", user_rendered)
            self.assertNotIn("overall status", user_rendered)

    def test_distribution_render_surfaces_legacy_payload_fallback_for_on_demand_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            home_root = Path(home_dir)
            request = DistributionRequest(
                target="codex:zh-CN",
                workspace=None,
                ref_override=None,
                interactive=False,
                source_channel="repo-local",
                source_metadata=DistributionSourceMetadata(
                    resolved_ref="working-tree",
                    asset_name="scripts/install_sopify.py",
                ),
            )

            report = run_distribution_install(
                request=request,
                repo_root=REPO_ROOT,
                home_root=home_root,
                install_executor=run_install,
            )
            payload_root = CODEX_ADAPTER.payload_root(home_root)
            payload_manifest = json.loads((payload_root / "payload-manifest.json").read_text(encoding="utf-8"))
            active_version = payload_manifest["active_version"]
            shutil.copytree(payload_root / "bundles" / active_version, payload_root / "bundle")
            (payload_root / "payload-manifest.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "payload_version": active_version,
                        "bundle_version": active_version,
                        "bundle_manifest": "bundle/manifest.json",
                        "bundle_template_dir": "bundle",
                        "helper_entry": "helpers/bootstrap_workspace.py",
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            legacy_report = DistributionInstallReport(
                request=report.request,
                install_result=report.install_result,
                status_payload=build_status_payload(home_root=home_root, workspace_root=None),
                doctor_payload=build_doctor_payload(home_root=home_root, workspace_root=None),
                next_step=report.next_step,
            )

            rendered = render_distribution_result(legacy_report)

            self.assertIn("payload bundle: source_kind=legacy_layout, reason_code=PAYLOAD_BUNDLE_READY", rendered)
            self.assertNotIn("payload outcome:", rendered)
            self.assertNotIn("payload hint:", rendered)
            self.assertIn("workspace: will bootstrap on first project trigger", rendered)

    def test_distribution_install_with_workspace_reports_prewarmed_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)
            request = DistributionRequest(
                target="codex:zh-CN",
                workspace=str(workspace_root),
                ref_override=None,
                interactive=False,
                source_channel="repo-local",
                source_metadata=DistributionSourceMetadata(
                    resolved_ref="working-tree",
                    asset_name="scripts/install_sopify.py",
                ),
            )

            report = run_distribution_install(
                request=request,
                repo_root=REPO_ROOT,
                home_root=home_root,
                install_executor=run_install,
            )

            self.assertTrue(report.status_payload["workspace_state"]["requested"])
            self.assertEqual(report.status_payload["workspace_state"]["root"], str(workspace_root.resolve()))
            self.assertEqual(report.status_payload["hosts"][0]["state"]["workspace_bundle_healthy"], "yes")
            rendered = render_distribution_result(report)
            self.assertIn(f"workspace: pre-warmed at {workspace_root.resolve()}", rendered)
            self.assertIn("workspace outcome: stub_selected [continue]", rendered)
            self.assertIn("workspace bundle: pass (STUB_SELECTED)", rendered)

    def test_cursor_distribution_reports_user_plugin_without_project_write(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            home_root = Path(home_dir)
            workspace_root = Path(workspace_dir)
            request = DistributionRequest(
                target="cursor:zh-CN",
                workspace=str(workspace_root),
                ref_override=None,
                interactive=False,
                source_channel="repo-local",
                source_metadata=DistributionSourceMetadata(
                    resolved_ref="working-tree",
                    asset_name="scripts/install_sopify.py",
                ),
            )

            report = run_distribution_install(
                request=request,
                repo_root=REPO_ROOT,
                home_root=home_root,
                install_executor=run_install,
            )

            rendered = render_distribution_user_result(report)
            rule_path = (
                home_root.resolve()
                / ".cursor"
                / "plugins"
                / "local"
                / "sopify"
                / "rules"
                / "sopify.mdc"
            )
            readme_path = rule_path.parent.parent / "README.md"
            self.assertIn(f"用户 Plugin 规则：{rule_path}", rendered)
            self.assertTrue(readme_path.is_file())
            self.assertIn("Cursor IDE 与本地 Agent CLI", readme_path.read_text(encoding="utf-8"))
            self.assertIn("未修改任何项目目录", rendered)
            self.assertIn("Developer: Reload Window", rendered)
            self.assertIn("确认 Sopify Plugin 及其 Always Rule 已启用", rendered)
            self.assertFalse((workspace_root / ".cursor").exists())
            self.assertFalse((workspace_root / ".sopify").exists())
            self.assertNotIn("已预热", rendered)
            verbose = render_distribution_result(report)
            self.assertIn(f"workspace: project unchanged; user Plugin rule installed at {rule_path}", verbose)
            self.assertNotIn("workspace: pre-warmed", verbose)

    def test_distribution_install_rejects_ambiguous_nested_workspace_prewarm(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as repo_dir:
            home_root = Path(home_dir)
            repo_root = Path(repo_dir)
            workspace_root = repo_root / "packages" / "feature"
            workspace_root.mkdir(parents=True, exist_ok=True)
            (repo_root / ".git").mkdir(parents=True, exist_ok=True)
            request = DistributionRequest(
                target="codex:zh-CN",
                workspace=str(workspace_root),
                ref_override=None,
                interactive=False,
                source_channel="repo-local",
                source_metadata=DistributionSourceMetadata(
                    resolved_ref="working-tree",
                    asset_name="scripts/install_sopify.py",
                ),
            )

            with self.assertRaises(DistributionError) as context:
                run_distribution_install(
                    request=request,
                    repo_root=REPO_ROOT,
                    home_root=home_root,
                    install_executor=run_install,
                )

            self.assertEqual(context.exception.reason_code, "WORKSPACE_PREWARM_ROOT_AMBIGUOUS")
            self.assertIn("omit `--workspace`", context.exception.detail.lower())
            self.assertIn("choose whether to enable the current directory or the repository root", context.exception.next_step)

    def test_non_interactive_distribution_install_requires_target(self) -> None:
        request = DistributionRequest(
            target=None,
            workspace=None,
            ref_override=None,
            interactive=False,
            source_channel="stable",
            source_metadata=DistributionSourceMetadata(
                resolved_ref="2026-03-25.101956",
                asset_name="install.sh",
            ),
        )

        with self.assertRaises(DistributionError) as context:
            run_distribution_install(
                request=request,
                repo_root=REPO_ROOT,
                home_root=Path(tempfile.gettempdir()),
                install_executor=run_install,
            )

        self.assertEqual(context.exception.reason_code, "TARGET_REQUIRED")
        rendered = render_distribution_user_error(context.exception, language="zh-CN")
        self.assertIn("Sopify 安装失败：", rendered)
        self.assertIn("Non-interactive installs must provide `--target <host:lang>`.", rendered)
        self.assertIn("修复方式：", rendered)
        self.assertIn("reason_code: TARGET_REQUIRED", rendered)
        self.assertIn("phase: input", rendered)

    def test_distribution_install_rejects_workspace_file(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.NamedTemporaryFile() as workspace_file:
            request = DistributionRequest(
                target="codex:zh-CN",
                workspace=workspace_file.name,
                ref_override=None,
                interactive=False,
                source_channel="stable",
                source_metadata=DistributionSourceMetadata(
                    resolved_ref="2026-03-25.101956",
                    asset_name="install.sh",
                ),
            )

            with self.assertRaises(DistributionError) as context:
                run_distribution_install(
                    request=request,
                    repo_root=REPO_ROOT,
                    home_root=Path(home_dir),
                    install_executor=run_install,
                )

            self.assertEqual(context.exception.reason_code, "WORKSPACE_NOT_DIRECTORY")
            self.assertIn("internal prewarm flag", context.exception.next_step)

    def test_interactive_distribution_install_selects_registry_target(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            request = DistributionRequest(
                target=None,
                workspace=None,
                ref_override=None,
                interactive=True,
                source_channel="stable",
                source_metadata=DistributionSourceMetadata(
                    resolved_ref="2026-03-25.101956",
                    asset_name="install.sh",
                ),
            )
            prompt_output = StringIO()

            report = run_distribution_install(
                request=request,
                repo_root=REPO_ROOT,
                home_root=Path(home_dir),
                install_executor=run_install,
                input_func=lambda _prompt: "1",
                output_stream=prompt_output,
            )

            self.assertEqual(report.install_result.target.value, "codex:zh-CN")
            self.assertIn("1. codex:zh-CN", prompt_output.getvalue())

    def test_distribution_install_supports_copilot_unified_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_dir:
            workspace_root = Path(workspace_dir)
            request = DistributionRequest(
                target="copilot",
                workspace=str(workspace_root),
                ref_override=None,
                interactive=False,
                source_channel="stable",
                source_metadata=DistributionSourceMetadata(
                    resolved_ref="2026-03-25.101956",
                    asset_name="install.sh",
                ),
            )

            report = run_distribution_install(
                request=request,
                repo_root=REPO_ROOT,
                home_root=Path(tempfile.gettempdir()),
                install_executor=run_install,
            )

            self.assertEqual(report.install_result.target.value, "copilot:en-US")
            rendered = render_distribution_user_result(report)
            self.assertIn("Copilot", rendered)
            self.assertTrue((workspace_root / ".github" / "copilot-instructions.md").exists())

    def test_install_script_copilot_defaults_language_from_lang(self) -> None:
        with tempfile.TemporaryDirectory() as workspace_dir:
            env = os.environ.copy()
            env["LANG"] = "zh_CN.UTF-8"
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "install_sopify.py"),
                    "--target",
                    "copilot",
                    "--workspace",
                    workspace_dir,
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            self.assertIn("Sopify 安装完成。", result.stdout)
            self.assertIn("宿主：Copilot（copilot:zh-CN）", result.stdout)

    def test_repo_local_ref_override_is_rejected(self) -> None:
        request = DistributionRequest(
            target="codex:zh-CN",
            workspace=None,
            ref_override="main",
            interactive=False,
            source_channel="repo-local",
            source_metadata=DistributionSourceMetadata(
                resolved_ref="working-tree",
                asset_name="scripts/install_sopify.py",
            ),
        )

        with self.assertRaises(DistributionError) as context:
            run_distribution_install(
                request=request,
                repo_root=REPO_ROOT,
                home_root=Path(tempfile.gettempdir()),
                install_executor=run_install,
            )

        self.assertEqual(context.exception.reason_code, "REF_OVERRIDE_UNSUPPORTED_FOR_REPO_LOCAL")

    def test_install_cli_defaults_to_user_summary_and_verbose_keeps_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir:
            env = dict(os.environ)
            env["HOME"] = home_dir
            env.pop("SOPIFY_DEBUG", None)
            env.pop("SOPIFY_DEBUG", None)
            default_completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "install_sopify.py"),
                    "--target",
                    "codex:zh-CN",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertEqual(default_completed.returncode, 0, msg=default_completed.stderr)
            self.assertIn("Sopify 安装完成。", default_completed.stdout)
            self.assertIn("输入：~go", default_completed.stdout)
            self.assertNotIn("source channel:", default_completed.stdout)

            verbose_completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "install_sopify.py"),
                    "--target",
                    "codex:zh-CN",
                    "--verbose",
                ],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

            self.assertEqual(verbose_completed.returncode, 0, msg=verbose_completed.stderr)
            self.assertIn("source channel: repo-local", verbose_completed.stdout)
            self.assertIn("reason_code", verbose_completed.stdout)


class ReleaseAssetRenderingTests(unittest.TestCase):
    def test_root_install_scripts_keep_internal_workspace_flag_out_of_primary_usage(self) -> None:
        install_sh = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
        install_ps1 = (REPO_ROOT / "install.ps1").read_text(encoding="utf-8")

        for flag in ("--target", "--ref", "--verbose", "--with-evidentloop"):
            self.assertIn(flag, install_sh)
            self.assertIn(flag, install_ps1)
        self.assertIn("--workspace", install_sh)
        self.assertIn("--workspace", install_ps1)
        self.assertIn("scripts/install_sopify.py", install_sh)
        self.assertIn("scripts/install_sopify.py", install_ps1)
        self.assertIn("--source-channel", install_sh)
        self.assertIn("--source-channel", install_ps1)
        self.assertIn("Usage: install.sh [--target <host[:lang]>] [--with-evidentloop] [--ref <tag-or-branch>]", install_sh)
        self.assertIn("Usage: install.ps1 [--target <host[:lang]>] [--with-evidentloop] [--ref <tag-or-branch>]", install_ps1)
        self.assertIn("Use `--target copilot` to bootstrap the current workspace", install_sh)
        self.assertIn("Use `--target copilot` to bootstrap the current workspace", install_ps1)
        self.assertIn("--language <lang>", install_sh)
        self.assertIn("--language <lang>", install_ps1)
        self.assertIn("--no-copilot", install_sh)
        self.assertIn("--no-copilot", install_ps1)

    def test_root_installers_probe_python_311_before_source_download(self) -> None:
        install_sh = (REPO_ROOT / "install.sh").read_text(encoding="utf-8")
        install_ps1 = (REPO_ROOT / "install.ps1").read_text(encoding="utf-8")
        self.assertIn('@("python3", "python", "py")', install_ps1)
        for content in (install_sh, install_ps1):
            self.assertIn("sys.version_info >= (3, 11)", content)
            self.assertIn("UNSUPPORTED_PYTHON", content)
            self.assertIn("Sopify needs Python 3.11 or newer", content)
        self.assertLess(
            install_sh.index("sys.version_info >= (3, 11)"),
            install_sh.index("ARCHIVE_URL"),
        )
        self.assertLess(
            install_ps1.index("sys.version_info >= (3, 11)"),
            install_ps1.index("$archiveUrl"),
        )

    def test_shell_installer_rejects_old_python_before_download(self) -> None:
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash is required")

        with tempfile.TemporaryDirectory() as temp_dir:
            tools_dir = Path(temp_dir)
            self._write_shell_stub(tools_dir / "curl", "exit 99")
            self._write_shell_stub(tools_dir / "tar", "exit 99")
            self._write_shell_stub(
                tools_dir / "python3",
                "printf '3.9.6\\n'\nexit 1",
            )
            env = os.environ.copy()
            env["PATH"] = str(tools_dir)
            completed = subprocess.run(
                [bash, str(REPO_ROOT / "install.sh"), "--target", "codex:en-US"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Sopify needs Python 3.11 or newer", completed.stderr)
        self.assertIn("Found: python3 3.9.6", completed.stderr)
        self.assertIn("Nothing was downloaded or installed", completed.stderr)
        self.assertIn("reason_code: UNSUPPORTED_PYTHON", completed.stderr)
        self.assertNotIn("Downloading Sopify source", completed.stderr)

    def test_shell_installer_uses_later_compatible_python(self) -> None:
        bash = shutil.which("bash")
        if bash is None:
            self.skipTest("bash is required")

        with tempfile.TemporaryDirectory() as temp_dir:
            tools_dir = Path(temp_dir)
            self._write_shell_stub(tools_dir / "curl", "exit 1")
            self._write_shell_stub(tools_dir / "tar", "exit 99")
            self._write_shell_stub(
                tools_dir / "python3",
                "printf '3.9.6\\n'\nexit 1",
            )
            self._write_shell_stub(
                tools_dir / "python",
                "printf '3.11.9\\n'\nexit 0",
            )
            env = os.environ.copy()
            env["PATH"] = os.pathsep.join((str(tools_dir), os.defpath))
            completed = subprocess.run(
                [bash, str(REPO_ROOT / "install.sh"), "--target", "codex:en-US"],
                capture_output=True,
                text=True,
                check=False,
                env=env,
            )

        self.assertEqual(completed.returncode, 1)
        self.assertIn("Downloading Sopify source", completed.stderr)
        self.assertIn("reason_code: SOURCE_FETCH_FAILED", completed.stderr)
        self.assertNotIn("UNSUPPORTED_PYTHON", completed.stderr)

    @staticmethod
    def _write_shell_stub(path: Path, body: str) -> None:
        path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        path.chmod(0o755)

    def test_render_release_installers_renders_stable_assets(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "render-release-installers.py"),
                    "--release-tag",
                    "2026-03-25.101956",
                    "--output-dir",
                    output_dir,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            install_sh = (Path(output_dir) / "install.sh").read_text(encoding="utf-8")
            install_ps1 = (Path(output_dir) / "install.ps1").read_text(encoding="utf-8")
            self.assertIn('SOURCE_CHANNEL="stable"', install_sh)
            self.assertIn('SOURCE_REF="2026-03-25.101956"', install_sh)
            self.assertNotIn('SOURCE_CHANNEL="dev"', install_sh)
            self.assertIn('$SourceChannel = "stable"', install_ps1)
            self.assertIn('$SourceRef = "2026-03-25.101956"', install_ps1)

    def test_stable_channel_does_not_use_main(self) -> None:
        with tempfile.TemporaryDirectory() as output_dir:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "render-release-installers.py"),
                    "--release-tag",
                    "2026-03-25.101956",
                    "--output-dir",
                    output_dir,
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            install_sh = (Path(output_dir) / "install.sh").read_text(encoding="utf-8")
            install_ps1 = (Path(output_dir) / "install.ps1").read_text(encoding="utf-8")
            self.assertNotIn('SOURCE_REF="main"', install_sh)
            self.assertNotIn('$SourceRef = "main"', install_ps1)

    def test_root_install_shell_help_returns_usage_without_network(self) -> None:
        completed = subprocess.run(
            ["bash", str(REPO_ROOT / "install.sh"), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertIn("Usage: install.sh", completed.stdout)


if __name__ == "__main__":
    unittest.main()
