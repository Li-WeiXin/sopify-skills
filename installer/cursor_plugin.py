"""Install the user-level Cursor Plugin entry owned by Sopify."""

from __future__ import annotations

import json
from pathlib import Path
import shutil

from installer.hosts.base import HostAdapter, render_user_plugin_rule, read_sopify_version
from installer.models import InstallError, InstallPhaseResult

_IGNORE_PATTERNS = shutil.ignore_patterns(".DS_Store", "Thumbs.db", "__pycache__")
_README_TEMPLATE_NAME = "cursor-plugin-readme.md.template"


def install_cursor_user_plugin_assets(
    adapter: HostAdapter,
    *,
    repo_root: Path,
    home_root: Path,
    language_directory: str,
) -> InstallPhaseResult:
    """Install one thin user Plugin rule and the canonical global Skill tree."""
    if adapter.host_name != "cursor" or not adapter.is_user_plugin_scope:
        raise InstallError("Cursor user Plugin installer received an incompatible host adapter")

    rule_source = adapter.instruction_source(repo_root, language_directory)
    readme_source = rule_source.with_name(_README_TEMPLATE_NAME)
    skills_source = adapter.source_root(repo_root, language_directory) / "skills" / "sopify"
    if not rule_source.is_file():
        raise InstallError(f"Missing source Cursor Plugin rule: {rule_source}")
    if not readme_source.is_file():
        raise InstallError(f"Missing source Cursor Plugin README: {readme_source}")
    if not skills_source.is_dir():
        raise InstallError(f"Missing source skills directory: {skills_source}")

    manifest_path, rule_path = adapter.user_plugin_paths(home_root)
    readme_path = adapter.user_plugin_readme_path(home_root)
    plugin_root = rule_path.parent.parent
    skills_destination = adapter.destination_root(home_root) / "skills" / "sopify"
    manifest = _manifest_text()
    rule = render_user_plugin_rule(rule_source, adapter)
    readme = readme_source.read_text(encoding="utf-8").rstrip("\n") + "\n"
    expected_paths = adapter.expected_paths(home_root)
    if (
        manifest_path.is_file()
        and manifest_path.read_text(encoding="utf-8") == manifest
        and rule_path.is_file()
        and rule_path.read_text(encoding="utf-8") == rule
        and readme_path.is_file()
        and readme_path.read_text(encoding="utf-8") == readme
        and all(path.exists() for path in adapter.global_skill_paths(home_root))
    ):
        return InstallPhaseResult(
            action="skipped",
            root=plugin_root,
            version=read_sopify_version(rule_source),
            paths=expected_paths,
        )

    action = "updated" if plugin_root.exists() or skills_destination.exists() else "installed"
    if plugin_root.exists():
        shutil.rmtree(plugin_root)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest, encoding="utf-8")
    rule_path.parent.mkdir(parents=True, exist_ok=True)
    rule_path.write_text(rule, encoding="utf-8")
    readme_path.write_text(readme, encoding="utf-8")

    if skills_destination.exists():
        shutil.rmtree(skills_destination)
    skills_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skills_source, skills_destination, ignore=_IGNORE_PATTERNS)

    return InstallPhaseResult(
        action=action,
        root=plugin_root,
        version=read_sopify_version(rule_source),
        paths=expected_paths,
    )


def _manifest_text() -> str:
    return json.dumps(
        {
            "name": "sopify",
            "description": "Sopify adaptive workflow entry for Cursor IDE",
        },
        ensure_ascii=False,
        indent=2,
    ) + "\n"
