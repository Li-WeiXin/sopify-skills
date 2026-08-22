# Test classification: distribution
from __future__ import annotations

from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy_script(relative_path: str, target_root: Path) -> Path:
    source = REPO_ROOT / relative_path
    target = target_root / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    target.chmod(0o755)
    return target


def _git_subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    for key in (
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_DIR",
        "GIT_GRAFT_FILE",
        "GIT_IMPLICIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_NAMESPACE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_PREFIX",
        "GIT_SUPER_PREFIX",
        "GIT_WORK_TREE",
    ):
        env.pop(key, None)
    return env


def _run_git(root: Path, *args: str, capture_output: bool = True, text: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=capture_output,
        text=text,
        env=_git_subprocess_env(),
    )


def _minimal_readme(version: str, *, english: bool) -> str:
    anchor = "#version-history" if english else "#版本历史"
    return textwrap.dedent(
        f"""\
        # {'Sopify Skills' if english else 'Sopify 技能'}

        [![Version](https://img.shields.io/badge/version-{version.replace('-', '--')}-orange.svg)]({anchor})
        """
    )


def _minimal_changelog(version: str, date: str) -> str:
    return textwrap.dedent(
        f"""\
        # Changelog

        ## [Unreleased]

        ## [{version}] - {date}

        ### Changed

        - Baseline release.
        """
    )


def _minimal_source_template(version: str, *, english: bool) -> str:
    body = "Note: {{config_dir}}/sopify/" if english else "说明：{{config_dir}}/sopify/"
    return textwrap.dedent(
        f"""\
        <!-- SOPIFY_VERSION: {version} -->
        # HEADER

        {body}
        """
    )


def _minimal_cursor_rule(version: str) -> str:
    return textwrap.dedent(
        f"""\
        ---
        description: "Sopify workflow entry for Cursor IDE"
        alwaysApply: true
        ---
        <!-- SOPIFY_VERSION: {version} -->
        """
    )


def _minimal_agents(version: str, *, claude: bool, english: bool) -> str:
    header = "CLAUDE" if claude else "AGENTS"
    body = "Note: ~/.claude/sopify/" if claude else "说明：~/.codex/sopify/"
    if english:
        body = "Note: ~/.claude/sopify/" if claude else "Note: ~/.codex/sopify/"
    return textwrap.dedent(
        f"""\
        <!-- SOPIFY_VERSION: {version} -->
        # {header}

        {body}
        """
    )


def _unreleased_body(changelog_text: str) -> str:
    start = changelog_text.index("## [Unreleased]") + len("## [Unreleased]")
    end = changelog_text.find("\n## [", start)
    if end < 0:
        end = len(changelog_text)
    return changelog_text[start:end]


def _release_body(changelog_text: str, version: str) -> str:
    header = f"## [{version}] - "
    start = changelog_text.index(header)
    body_start = changelog_text.find("\n", start) + 1
    end = changelog_text.find("\n## [", body_start)
    if end < 0:
        end = len(changelog_text)
    return changelog_text[body_start:end]


def _init_release_hook_fixture(root: Path, *, inject_sync_failure: bool = False) -> None:
    for relative in (
        "scripts/release-sync.sh",
        "scripts/release-draft-changelog.py",
        "scripts/release-preflight.sh",
        "scripts/sync-skills.sh",
        "scripts/check-version-consistency.sh",
        "scripts/render-host-skills.py",
        "scripts/regenerate-golden-snapshots.py",
        ".githooks/pre-commit",
        ".githooks/commit-msg",
    ):
        _copy_script(relative, root)

    # Inject a post-update check failure to verify pre-commit rollback after
    # release-sync has already modified README/CHANGELOG and source templates.
    _copy_script("skills/hosts.yaml", root)
    if inject_sync_failure:
        _write(
            root / "scripts/check-version-consistency.sh",
            "#!/usr/bin/env bash\nexit 1\n",
        )

    old_version = "2026-03-20.183348"
    old_date = "2026-03-20"
    _write(root / "README.md", _minimal_readme(old_version, english=True))
    _write(root / "README.zh-CN.md", _minimal_readme(old_version, english=False))
    _write(root / "CHANGELOG.md", _minimal_changelog(old_version, old_date))

    # Source templates (skills/ is the source of truth)
    _write(root / "skills/zh/header.md.template", _minimal_source_template(old_version, english=False))
    _write(root / "skills/en/header.md.template", _minimal_source_template(old_version, english=True))
    _write(root / "skills/zh/cursor-plugin-rule.mdc.template", _minimal_cursor_rule(old_version))
    _write(root / "skills/en/cursor-plugin-rule.mdc.template", _minimal_cursor_rule(old_version))
    _write(root / "skills/zh/skills/sopify/SKILL.md", "# skill\n")
    _write(root / "skills/en/skills/sopify/SKILL.md", "# skill\n")

    _write(root / "installer/payload.py", "print('baseline')\n")
    _write(root / "sopify_contracts/__init__.py", "print('baseline test')\n")

    _run_git(root, "init")
    _run_git(root, "config", "user.name", "Test User", capture_output=False, text=False)
    _run_git(root, "config", "user.email", "test@example.com", capture_output=False, text=False)
    _run_git(root, "add", ".", capture_output=False, text=False)
    _run_git(root, "commit", "-m", "baseline")

    _write(root / "installer/payload.py", "print('changed')\n")
    _write(root / "sopify_contracts/__init__.py", "print('changed test')\n")
    _run_git(root, "add", "installer/payload.py", "sopify_contracts/__init__.py", capture_output=False, text=False)


class ReleaseHookTests(unittest.TestCase):
    def test_commit_msg_leaves_message_unchanged_without_release_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_release_hook_fixture(root)

            message_file = root / "COMMIT_EDITMSG"
            _write(message_file, "docs: update contribution guide\n")

            completed = subprocess.run(
                ["bash", str(root / ".githooks" / "commit-msg"), str(message_file)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                env=_git_subprocess_env(),
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            message = message_file.read_text(encoding="utf-8")
            self.assertEqual(message, "docs: update contribution guide\n")
            self.assertNotIn("Release-Sync:", message)

    def test_commit_msg_preserves_manual_coauthor_trailers_without_duplication(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_release_hook_fixture(root)

            message_file = root / "COMMIT_EDITMSG"
            _write(
                message_file,
                textwrap.dedent(
                    """\
                    docs: update contribution guide

                    Co-authored-by: Claude <claude@anthropic.com>
                    Co-authored-by: ChatGPT <chatgpt@openai.com>
                    """
                ),
            )

            completed = subprocess.run(
                ["bash", str(root / ".githooks" / "commit-msg"), str(message_file)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                env=_git_subprocess_env(),
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            message = message_file.read_text(encoding="utf-8")
            self.assertEqual(message.count("Co-authored-by: Claude <claude@anthropic.com>"), 1)
            self.assertEqual(message.count("Co-authored-by: ChatGPT <chatgpt@openai.com>"), 1)

    def test_release_draft_changelog_populates_empty_unreleased(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            changelog = root / "CHANGELOG.md"
            _write(changelog, _minimal_changelog("2026-03-20.183348", "2026-03-20"))

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "release-draft-changelog.py"),
                    "--root",
                    str(root),
                    "--file",
                    "installer/payload.py",
                    "--file",
                    "scripts/release-sync.sh",
                    "--file",
                    "sopify_contracts/__init__.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            text = changelog.read_text(encoding="utf-8")
            unreleased = _unreleased_body(text)
            self.assertIn("### Summary", unreleased)
            self.assertIn("Changes across:", unreleased)
            self.assertIn("### Changed", unreleased)
            self.assertIn("**Scripts**", unreleased)
            self.assertNotIn("**Runtime**", unreleased)
            self.assertNotIn("**Tests**", unreleased)
            self.assertNotIn("<details>", unreleased)

    def test_release_sync_auto_drafts_unreleased_before_version_bump(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_release_hook_fixture(root)

            completed = subprocess.run(
                ["bash", str(root / "scripts" / "release-sync.sh"), "2026-03-21.010203", "2026-03-21"],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                env=_git_subprocess_env(),
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
            release_body = _release_body(changelog, "2026-03-21.010203")
            self.assertIn("## [2026-03-21.010203] - 2026-03-21", changelog)
            self.assertIn("### Summary", release_body)
            self.assertIn("### Changed", release_body)
            self.assertIn("**Changed**", release_body)
            self.assertNotIn("**Runtime**", release_body)
            self.assertNotIn("<details>", release_body)
            self.assertIn("badge/version-2026--03--21.010203-orange.svg", (root / "README.md").read_text(encoding="utf-8"))
            self.assertIn("<!-- SOPIFY_VERSION: 2026-03-21.010203 -->", (root / "skills/zh/header.md.template").read_text(encoding="utf-8"))
            self.assertIn("<!-- SOPIFY_VERSION: 2026-03-21.010203 -->", (root / "skills/en/header.md.template").read_text(encoding="utf-8"))
            self.assertIn(
                "<!-- SOPIFY_VERSION: 2026-03-21.010203 -->",
                (root / "skills/zh/cursor-plugin-rule.mdc.template").read_text(encoding="utf-8"),
            )
            self.assertIn(
                "<!-- SOPIFY_VERSION: 2026-03-21.010203 -->",
                (root / "skills/en/cursor-plugin-rule.mdc.template").read_text(encoding="utf-8"),
            )

    def test_version_consistency_rejects_stale_cursor_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_release_hook_fixture(root)
            _write(root / "skills/en/cursor-plugin-rule.mdc.template", _minimal_cursor_rule("stale-version"))

            completed = subprocess.run(
                ["bash", str(root / "scripts" / "check-version-consistency.sh")],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                env=_git_subprocess_env(),
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("Source SOPIFY_VERSION mismatch", completed.stdout)

    def test_release_draft_only_renders_non_empty_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            changelog = root / "CHANGELOG.md"
            _write(changelog, _minimal_changelog("2026-03-20.183348", "2026-03-20"))

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "release-draft-changelog.py"),
                    "--root",
                    str(root),
                    "--file",
                    "README.md",
                    "--file",
                    "sopify_contracts/__init__.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            text = changelog.read_text(encoding="utf-8")
            unreleased = _unreleased_body(text)
            self.assertIn("### Summary", unreleased)
            self.assertIn("Docs", unreleased)
            self.assertIn("Changed", unreleased)
            self.assertNotIn("**Runtime**", unreleased)
            self.assertNotIn("**Scripts**", unreleased)
            self.assertNotIn("**Skills**", unreleased)

    def test_release_draft_ignores_sopify_kb_paths(self) -> None:
        """Plan/history package paths are included for attribution; non-package .sopify/ paths are excluded."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            changelog = root / "CHANGELOG.md"
            _write(changelog, _minimal_changelog("2026-03-20.183348", "2026-03-20"))

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "release-draft-changelog.py"),
                    "--root",
                    str(root),
                    "--file",
                    ".sopify/history/index.md",
                    "--file",
                    ".sopify/plan/20260324_task/tasks.md",
                    "--file",
                    "installer/payload.py",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            unreleased = _unreleased_body(changelog.read_text(encoding="utf-8"))
            # Plan package path is now included for attribution
            self.assertIn("`20260324_task`", unreleased)
            self.assertIn("**Changed**", unreleased)
            # Non-package .sopify/ paths still excluded
            self.assertNotIn("history/index.md", unreleased)
            # Blueprint internals still excluded
            self.assertNotIn(".sopify/blueprint/", unreleased)

    def test_release_draft_skips_when_only_sopify_kb_paths_changed(self) -> None:
        """Only non-package .sopify/ paths → no eligible files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            changelog = root / "CHANGELOG.md"
            original = _minimal_changelog("2026-03-20.183348", "2026-03-20")
            _write(changelog, original)

            completed = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "release-draft-changelog.py"),
                    "--root",
                    str(root),
                    "--file",
                    ".sopify/history/index.md",
                    "--file",
                    ".sopify/blueprint/design.md",
                    "--file",
                    ".sopify/state/current_handoff.json",
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, msg=completed.stderr)
            self.assertIn("No release-note-eligible changed files found. Skipped auto-draft.", completed.stdout)
            self.assertEqual(changelog.read_text(encoding="utf-8"), original)

    def test_pre_commit_restores_release_managed_files_when_release_sync_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _init_release_hook_fixture(root, inject_sync_failure=True)

            original_readme = (root / "README.md").read_text(encoding="utf-8")
            original_changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
            original_template = (root / "skills/zh/header.md.template").read_text(encoding="utf-8")
            original_cursor_rule = (root / "skills/zh/cursor-plugin-rule.mdc.template").read_text(encoding="utf-8")

            completed = subprocess.run(
                ["bash", str(root / ".githooks" / "pre-commit")],
                cwd=root,
                env={**_git_subprocess_env(), "SOPIFY_SKIP_RELEASE_PREFLIGHT": "1"},
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual((root / "README.md").read_text(encoding="utf-8"), original_readme)
            self.assertEqual((root / "CHANGELOG.md").read_text(encoding="utf-8"), original_changelog)
            self.assertEqual((root / "skills/zh/header.md.template").read_text(encoding="utf-8"), original_template)
            self.assertEqual(
                (root / "skills/zh/cursor-plugin-rule.mdc.template").read_text(encoding="utf-8"),
                original_cursor_rule,
            )
            self.assertFalse((root / ".git" / ".sopify-release-sync-state").exists())


if __name__ == "__main__":
    unittest.main()
