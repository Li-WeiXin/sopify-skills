"""Tests for the opt-in EvidentLoop companion installer."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from installer.distribution import (
    _companion_action_lines,
    DistributionError,
    DistributionRequest,
    DistributionSourceMetadata,
    render_distribution_error,
    render_distribution_result,
    render_distribution_user_error,
    render_distribution_user_result,
    run_distribution_install,
)
from installer.evidentloop import (
    EVIDENTLOOP_PACKAGE,
    EVIDENTLOOP_SKILL_SOURCE,
    SKILLS_CLI_PACKAGE,
    install_evidentloop_companion,
    prepare_evidentloop_install,
)
from installer.hosts.base import HostAdapter
from installer.hosts.claude import CLAUDE_ADAPTER
from installer.hosts.codex import CODEX_ADAPTER
from installer.hosts.copilot import COPILOT_ADAPTER
from installer.hosts.cursor import CURSOR_ADAPTER
from installer.hosts.qoder import QODER_ADAPTER
from installer.models import EvidentLoopInstallResult, InstallError
from scripts.install_sopify import build_parser, run_install


REPO_ROOT = Path(__file__).resolve().parents[1]
HEALTHY_VERSION = "0.2.0"
COMPLETE_SKILL = """\
---
name: evidentloop
---
Use EvidentLoop to audit a local Git diff.
"""


def _completed(
    argv: list[str],
    *,
    stdout: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(argv, returncode, stdout=stdout, stderr="")


def _write_complete_skill(skill_dir: Path) -> None:
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(COMPLETE_SKILL, encoding="utf-8")


class EvidentLoopInstallerTests(unittest.TestCase):
    def test_official_sources_and_host_native_paths(self) -> None:
        self.assertEqual(EVIDENTLOOP_PACKAGE, "evidentloop")
        self.assertEqual(EVIDENTLOOP_SKILL_SOURCE, "evidentloop/evidentloop")
        self.assertEqual(SKILLS_CLI_PACKAGE, "skills@latest")

        home = Path("/home/test")
        workspace = Path("/workspace/project")
        expected = {
            CODEX_ADAPTER: ("codex", home / ".agents/skills/evidentloop"),
            CLAUDE_ADAPTER: ("claude-code", home / ".claude/skills/evidentloop"),
            QODER_ADAPTER: ("qoder", home / ".qoder/skills/evidentloop"),
            COPILOT_ADAPTER: (
                "github-copilot",
                workspace / ".github/skills/evidentloop",
            ),
        }
        for adapter, (agent, path) in expected.items():
            with self.subTest(host=adapter.host_name):
                self.assertEqual(adapter.skills_cli_agent, agent)
                self.assertEqual(
                    adapter.skill_install_path(
                        home_root=home,
                        workspace_root=workspace,
                        skill_name="evidentloop",
                    ),
                    path,
                )
        self.assertIsNone(CURSOR_ADAPTER.skills_cli_agent)

    def test_flag_is_disabled_by_default_and_does_no_companion_work(self) -> None:
        parser = build_parser()
        self.assertFalse(
            parser.parse_args(["--target", "codex:en-US"]).with_evidentloop
        )
        self.assertTrue(
            parser.parse_args(
                ["--target", "codex:en-US", "--with-evidentloop"]
            ).with_evidentloop
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            with (
                patch("scripts.install_sopify.prepare_evidentloop_install") as prepare,
                patch(
                    "scripts.install_sopify.install_evidentloop_companion"
                ) as install,
            ):
                result = run_install(
                    target_value="codex:en-US",
                    workspace_value=None,
                    repo_root=REPO_ROOT,
                    home_root=Path(temp_dir),
                )

        prepare.assert_not_called()
        install.assert_not_called()
        self.assertIsNone(result.evidentloop_install)

    def test_cursor_rejects_explicit_evidentloop_flag(self) -> None:
        with tempfile.TemporaryDirectory() as home_dir, tempfile.TemporaryDirectory() as workspace_dir:
            with self.assertRaisesRegex(InstallError, "does not support --with-evidentloop"):
                run_install(
                    target_value="cursor",
                    workspace_value=workspace_dir,
                    repo_root=REPO_ROOT,
                    home_root=Path(home_dir),
                    with_evidentloop=True,
                )

    def test_missing_mapping_stops_before_command_lookup(self) -> None:
        adapter = HostAdapter(
            host_name="future-host",
            destination_dirname=".future",
            header_filename="AGENTS.md",
        )
        with patch("installer.evidentloop.shutil.which") as which:
            with self.assertRaisesRegex(InstallError, "missing Skill install mapping"):
                prepare_evidentloop_install(adapter, home_root=Path("/home/test"))
        which.assert_not_called()

    def test_healthy_existing_components_are_reused_without_installers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            skill_dir = home / ".agents/skills/evidentloop"
            _write_complete_skill(skill_dir)

            with (
                patch(
                    "installer.evidentloop.shutil.which",
                    side_effect=lambda name: (
                        "/tools/evidentloop" if name == "evidentloop" else None
                    ),
                ),
                patch(
                    "installer.evidentloop.subprocess.run",
                    side_effect=self._healthy_runner,
                ) as run,
            ):
                plan = prepare_evidentloop_install(CODEX_ADAPTER, home_root=home)
                result = install_evidentloop_companion(plan)

        self.assertFalse(plan.install_cli)
        self.assertFalse(plan.install_skill)
        self.assertEqual((result.cli_action, result.skill_action), ("reused", "reused"))
        self.assertEqual(result.package_version, HEALTHY_VERSION)
        self.assertEqual(len(run.call_args_list), 1)
        self.assertEqual(run.call_args.args[0][1:], ["doctor", "--json"])

    def test_prerequisites_are_required_only_for_missing_components(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            _write_complete_skill(home / ".agents/skills/evidentloop")
            with patch("installer.evidentloop.shutil.which", return_value=None):
                with self.assertRaisesRegex(
                    InstallError,
                    r"missing required command\(s\): uv$",
                ):
                    prepare_evidentloop_install(CODEX_ADAPTER, home_root=home)

        with tempfile.TemporaryDirectory() as temp_dir:

            def fake_which(name: str) -> str | None:
                return {
                    "evidentloop": "/tools/evidentloop",
                    "git": "/tools/git",
                }.get(name)

            with (
                patch("installer.evidentloop.shutil.which", side_effect=fake_which),
                patch(
                    "installer.evidentloop.subprocess.run",
                    side_effect=self._healthy_runner,
                ),
            ):
                with self.assertRaisesRegex(
                    InstallError,
                    r"missing required command\(s\): npx$",
                ):
                    prepare_evidentloop_install(
                        CODEX_ADAPTER,
                        home_root=Path(temp_dir),
                    )

    def test_existing_skill_rejects_empty_or_wrong_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            skill_dir = home / ".agents/skills/evidentloop"
            _write_complete_skill(skill_dir)
            entrypoint = skill_dir / "SKILL.md"
            entrypoint.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(InstallError, "entrypoint is empty"):
                prepare_evidentloop_install(CODEX_ADAPTER, home_root=home)

            entrypoint.write_text(
                "---\nname: another-skill\n---\nNot EvidentLoop.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                InstallError,
                r"expected front matter `name: evidentloop`",
            ):
                prepare_evidentloop_install(CODEX_ADAPTER, home_root=home)

    def test_unhealthy_cli_is_not_replaced(self) -> None:
        def unhealthy_runner(
            argv: list[str],
            **_kwargs: object,
        ) -> subprocess.CompletedProcess[str]:
            return _completed(
                argv,
                stdout=json.dumps(
                    {
                        "status": "error",
                        "version": HEALTHY_VERSION,
                        "python_executable": "/tools/python",
                    }
                ),
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            _write_complete_skill(home / ".agents/skills/evidentloop")
            with (
                patch(
                    "installer.evidentloop.shutil.which",
                    return_value="/tools/evidentloop",
                ),
                patch(
                    "installer.evidentloop.subprocess.run",
                    side_effect=unhealthy_runner,
                ) as run,
            ):
                with self.assertRaisesRegex(InstallError, "unhealthy installation"):
                    prepare_evidentloop_install(CODEX_ADAPTER, home_root=home)

        self.assertEqual(len(run.call_args_list), 1)

    def test_home_skill_install_stages_then_copies_to_final_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            target = home / ".agents/skills/evidentloop"
            observed: list[tuple[list[str], dict[str, object]]] = []

            def fake_which(name: str) -> str | None:
                return {
                    "evidentloop": "/tools/evidentloop",
                    "npx": "/tools/npx",
                    "git": "/tools/git",
                }.get(name)

            def fake_run(
                argv: list[str],
                **kwargs: object,
            ) -> subprocess.CompletedProcess[str]:
                observed.append((list(argv), kwargs))
                if argv[0] == "/tools/npx":
                    staging_home = Path(str(kwargs["env"]["HOME"]))
                    _write_complete_skill(staging_home / ".agents/skills/evidentloop")
                    return _completed(argv)
                return self._healthy_runner(argv, **kwargs)

            with (
                patch("installer.evidentloop.shutil.which", side_effect=fake_which),
                patch("installer.evidentloop.subprocess.run", side_effect=fake_run),
            ):
                plan = prepare_evidentloop_install(CODEX_ADAPTER, home_root=home)
                result = install_evidentloop_companion(plan)

            npx_argv, npx_kwargs = next(
                item for item in observed if item[0][0] == "/tools/npx"
            )
            self.assertEqual(
                npx_argv,
                [
                    "/tools/npx",
                    "--yes",
                    "skills@latest",
                    "add",
                    "evidentloop/evidentloop",
                    "--skill",
                    "evidentloop",
                    "-g",
                    "-a",
                    "codex",
                    "-y",
                    "--copy",
                ],
            )
            self.assertNotEqual(npx_kwargs["env"]["HOME"], str(home))
            self.assertEqual(npx_kwargs["env"]["DISABLE_TELEMETRY"], "1")
            self.assertTrue((target / "SKILL.md").is_file())
            self.assertEqual(result.skill_path, target / "SKILL.md")

    def test_copilot_install_copies_only_skill_to_project_path(self) -> None:
        with (
            tempfile.TemporaryDirectory() as home_dir,
            tempfile.TemporaryDirectory() as workspace_dir,
        ):
            home = Path(home_dir)
            workspace = Path(workspace_dir)
            target = workspace / ".github/skills/evidentloop"
            observed_npx: list[list[str]] = []

            def fake_which(name: str) -> str | None:
                return {
                    "evidentloop": "/tools/evidentloop",
                    "npx": "/tools/npx",
                    "git": "/tools/git",
                }.get(name)

            def fake_run(
                argv: list[str],
                **kwargs: object,
            ) -> subprocess.CompletedProcess[str]:
                if argv[0] == "/tools/npx":
                    observed_npx.append(list(argv))
                    staging_root = Path(str(kwargs["cwd"]))
                    _write_complete_skill(staging_root / ".agents/skills/evidentloop")
                    (staging_root / "skills-lock.json").write_text(
                        "{}\n", encoding="utf-8"
                    )
                    return _completed(argv)
                return self._healthy_runner(argv, **kwargs)

            with (
                patch("installer.evidentloop.shutil.which", side_effect=fake_which),
                patch("installer.evidentloop.subprocess.run", side_effect=fake_run),
            ):
                plan = prepare_evidentloop_install(
                    COPILOT_ADAPTER,
                    home_root=home,
                    workspace_root=workspace,
                )
                result = install_evidentloop_companion(plan)

            self.assertEqual(
                observed_npx[0][-4:],
                ["-a", "github-copilot", "-y", "--copy"],
            )
            self.assertTrue((target / "SKILL.md").is_file())
            self.assertFalse((workspace / ".agents/skills/evidentloop").exists())
            self.assertFalse((workspace / "skills-lock.json").exists())
            self.assertEqual(result.skill_path, target / "SKILL.md")

    def test_missing_cli_installs_current_package_and_reports_doctor_version(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            _write_complete_skill(home / ".agents/skills/evidentloop")
            bin_dir = home / "uv-bin"
            bin_dir.mkdir()
            executable = bin_dir / "evidentloop"
            executable.write_text("", encoding="utf-8")
            cli_installed = False
            observed: list[list[str]] = []

            def fake_which(name: str) -> str | None:
                if name == "evidentloop" and cli_installed:
                    return str(executable)
                return "/tools/uv" if name == "uv" else None

            def fake_run(
                argv: list[str],
                **kwargs: object,
            ) -> subprocess.CompletedProcess[str]:
                nonlocal cli_installed
                observed.append(list(argv))
                if argv[1:] == ["tool", "install", "evidentloop"]:
                    cli_installed = True
                    return _completed(argv)
                if argv[1:] == ["tool", "dir", "--bin"]:
                    return _completed(argv, stdout=f"{bin_dir}\n")
                return self._healthy_runner(argv, **kwargs)

            with (
                patch("installer.evidentloop.shutil.which", side_effect=fake_which),
                patch("installer.evidentloop.subprocess.run", side_effect=fake_run),
            ):
                plan = prepare_evidentloop_install(CODEX_ADAPTER, home_root=home)
                result = install_evidentloop_companion(plan)

        self.assertEqual(
            (result.cli_action, result.skill_action), ("installed", "reused")
        )
        self.assertEqual(result.package_version, HEALTHY_VERSION)
        self.assertIn(["/tools/uv", "tool", "install", "evidentloop"], observed)

    def test_fresh_cli_stops_when_command_is_not_on_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            _write_complete_skill(home / ".agents/skills/evidentloop")
            bin_dir = home / "uv-bin"
            bin_dir.mkdir()
            (bin_dir / "evidentloop").write_text("", encoding="utf-8")

            def fake_which(name: str) -> str | None:
                return "/tools/uv" if name == "uv" else None

            def fake_run(
                argv: list[str],
                **kwargs: object,
            ) -> subprocess.CompletedProcess[str]:
                if argv[1:] == ["tool", "install", "evidentloop"]:
                    return _completed(argv)
                if argv[1:] == ["tool", "dir", "--bin"]:
                    return _completed(argv, stdout=f"{bin_dir}\n")
                return self._healthy_runner(argv, **kwargs)

            with (
                patch("installer.evidentloop.shutil.which", side_effect=fake_which),
                patch("installer.evidentloop.subprocess.run", side_effect=fake_run),
            ):
                plan = prepare_evidentloop_install(CODEX_ADAPTER, home_root=home)
                with self.assertRaisesRegex(
                    InstallError,
                    r"not discoverable on PATH.*uv tool update-shell",
                ):
                    install_evidentloop_companion(plan)

    def test_failed_skill_install_leaves_no_target_and_can_be_retried(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            target = home / ".agents/skills/evidentloop"
            attempt = 0

            def fake_which(name: str) -> str | None:
                return {
                    "evidentloop": "/tools/evidentloop",
                    "npx": "/tools/npx",
                    "git": "/tools/git",
                }.get(name)

            def fake_run(
                argv: list[str],
                **kwargs: object,
            ) -> subprocess.CompletedProcess[str]:
                nonlocal attempt
                if argv[0] == "/tools/npx":
                    attempt += 1
                    staging_home = Path(str(kwargs["env"]["HOME"]))
                    staged_skill = staging_home / ".agents/skills/evidentloop"
                    if attempt == 1:
                        staged_skill.mkdir(parents=True)
                        (staged_skill / "partial.tmp").write_text(
                            "partial", encoding="utf-8"
                        )
                        return _completed(argv, returncode=1)
                    _write_complete_skill(staged_skill)
                    return _completed(argv)
                return self._healthy_runner(argv, **kwargs)

            with (
                patch("installer.evidentloop.shutil.which", side_effect=fake_which),
                patch("installer.evidentloop.subprocess.run", side_effect=fake_run),
            ):
                first_plan = prepare_evidentloop_install(CODEX_ADAPTER, home_root=home)
                with self.assertRaisesRegex(InstallError, "Skill install failed"):
                    install_evidentloop_companion(first_plan)
                self.assertFalse(target.exists())

                retry_plan = prepare_evidentloop_install(CODEX_ADAPTER, home_root=home)
                result = install_evidentloop_companion(retry_plan)

            self.assertTrue((target / "SKILL.md").is_file())
            self.assertEqual(result.skill_action, "installed")
            self.assertEqual(attempt, 2)

    def test_core_completion_is_visible_when_companion_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            with (
                patch(
                    "scripts.install_sopify.prepare_evidentloop_install",
                    return_value=object(),
                ),
                patch(
                    "scripts.install_sopify.install_evidentloop_companion",
                    side_effect=InstallError("Skill install failed"),
                ),
            ):
                with self.assertRaisesRegex(
                    InstallError,
                    "Sopify core installation completed.*setup did not complete",
                ):
                    run_install(
                        target_value="codex:en-US",
                        workspace_value=None,
                        repo_root=REPO_ROOT,
                        home_root=home,
                        with_evidentloop=True,
                    )
            self.assertTrue((home / ".codex/AGENTS.md").is_file())

    def test_distribution_reports_simple_actions_and_one_companion_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            home = Path(temp_dir)
            skill_path = home / ".agents/skills/evidentloop/SKILL.md"
            companion = EvidentLoopInstallResult(
                cli_action="installed",
                skill_action="reused",
                package_version=HEALTHY_VERSION,
                skill_path=skill_path,
            )
            with (
                patch(
                    "scripts.install_sopify.prepare_evidentloop_install",
                    return_value=object(),
                ),
                patch(
                    "scripts.install_sopify.install_evidentloop_companion",
                    return_value=companion,
                ),
            ):
                report = run_distribution_install(
                    request=self._request(),
                    repo_root=REPO_ROOT,
                    home_root=home,
                    install_executor=run_install,
                )

        detailed = render_distribution_result(report)
        user_facing = render_distribution_user_result(report)
        self.assertIn("EvidentLoop CLI (0.2.0): installed", detailed)
        self.assertIn("EvidentLoop Skill: reused (health check passed)", detailed)
        self.assertIn("EvidentLoop CLI（0.2.0）：已安装", user_facing)
        self.assertIn("EvidentLoop Skill：已复用（健康检查通过）", user_facing)

        def fail_install(**_kwargs: object) -> object:
            raise InstallError(
                "Sopify core installation completed, but EvidentLoop setup did not complete."
            )

        with self.assertRaises(DistributionError) as raised:
            run_distribution_install(
                request=self._request(),
                repo_root=REPO_ROOT,
                home_root=Path("/tmp/sopify-test-home"),
                install_executor=fail_install,
            )
        error = raised.exception
        self.assertEqual(error.reason_code, "EVIDENTLOOP_COMPANION_INCOMPLETE")
        self.assertIn("setup did not complete", render_distribution_error(error))
        self.assertIn(
            "EvidentLoop 安装未完成",
            render_distribution_user_error(error, language="zh-CN"),
        )
        self.assertIn(
            "重新运行同一命令，或单独安装",
            render_distribution_user_error(error, language="zh-CN"),
        )

        copilot = EvidentLoopInstallResult(
            cli_action="reused",
            skill_action="installed",
            package_version=HEALTHY_VERSION,
            skill_path=home / ".github/skills/evidentloop/SKILL.md",
        )
        copilot_lines = "\n".join(_companion_action_lines(copilot, language="zh-CN"))
        self.assertIn("如需云端使用，请审查后自行提交", copilot_lines)
        self.assertIn("Sopify 不会自动提交或更新", copilot_lines)

    @staticmethod
    def _request() -> DistributionRequest:
        return DistributionRequest(
            target="codex:zh-CN",
            workspace=None,
            ref_override=None,
            interactive=False,
            source_channel="repo-local",
            source_metadata=DistributionSourceMetadata(
                resolved_ref="working-tree",
                asset_name="scripts/install_sopify.py",
            ),
            with_evidentloop=True,
        )

    @staticmethod
    def _healthy_runner(
        argv: list[str],
        **_kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        if argv[1:] == ["doctor", "--json"]:
            return _completed(
                argv,
                stdout=json.dumps(
                    {
                        "status": "ok",
                        "version": HEALTHY_VERSION,
                        "python_executable": "/tools/python",
                    }
                ),
            )
        raise AssertionError(f"unexpected argv: {argv}")


if __name__ == "__main__":
    unittest.main()
