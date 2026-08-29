"""Base host adapter and shared install helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
import shutil

from installer.models import HostCapability, InstallError, InstallPhaseResult, language_to_source_dir

_IGNORE_PATTERNS = shutil.ignore_patterns(".DS_Store", "Thumbs.db", "__pycache__")
_SOPIFY_VERSION_RE = re.compile(r"^<!--\s*SOPIFY_VERSION:\s*(?P<version>.+?)\s*-->$", re.MULTILINE)
HEADER_TEMPLATE_NAME = "header.md.template"

_MANAGED_BLOCK_BEGIN = "<!-- BEGIN SOPIFY MANAGED BLOCK -->"
_MANAGED_BLOCK_END = "<!-- END SOPIFY MANAGED BLOCK -->"

INSTRUCTION_SURFACE_HEADER_EMBEDDED = "header_embedded"
INSTRUCTION_SURFACE_SINGLE_FILE = "single_file"
INSTRUCTION_SURFACE_USER_PLUGIN = "user_plugin"


@dataclass(frozen=True)
class HostAdapter:
    """Host-specific layout for Sopify prompt-layer assets."""

    host_name: str
    destination_dirname: str
    header_filename: str
    config_dir: str | None = None
    instruction_surface: str = field(default=INSTRUCTION_SURFACE_HEADER_EMBEDDED)
    instruction_file_relpath: str | None = field(default=None)
    instruction_source_relpath: str | None = field(default=None)
    default_language: str | None = field(default=None)
    skills_cli_agent: str | None = field(default=None)
    skill_install_dirname: str | None = field(default=None)

    @property
    def is_workspace_scope(self) -> bool:
        return self.instruction_surface == INSTRUCTION_SURFACE_SINGLE_FILE

    @property
    def is_user_plugin_scope(self) -> bool:
        return self.instruction_surface == INSTRUCTION_SURFACE_USER_PLUGIN

    @property
    def requires_workspace(self) -> bool:
        """Whether installation needs a project root for its instruction surface."""
        return self.is_workspace_scope

    def source_root(self, repo_root: Path, language_directory: str) -> Path:
        return repo_root / "skills" / language_to_source_dir(language_directory)

    def instruction_source(self, repo_root: Path, language_directory: str) -> Path:
        """Return the source asset for this host's instruction surface."""
        source_root = self.source_root(repo_root, language_directory)
        if self.instruction_source_relpath is not None:
            return source_root / self.instruction_source_relpath
        template = source_root / HEADER_TEMPLATE_NAME
        return template if template.is_file() else source_root / self.header_filename

    def destination_root(self, home_root: Path) -> Path:
        return home_root / self.destination_dirname

    def payload_root(self, home_root: Path) -> Path:
        return self.destination_root(home_root) / "sopify"

    def expected_paths(self, home_root: Path) -> tuple[Path, ...]:
        root = self.destination_root(home_root)
        if self.instruction_surface == INSTRUCTION_SURFACE_SINGLE_FILE:
            paths: list[Path] = [root / self.header_filename]
            if self.instruction_file_relpath is not None:
                paths.append(home_root / self.instruction_file_relpath)
            return tuple(paths)
        if self.is_user_plugin_scope:
            return (*self.user_plugin_paths(home_root), *self.global_skill_paths(home_root))
        return (
            root / self.header_filename,
            root / "skills" / "sopify" / "analyze" / "SKILL.md",
            root / "skills" / "sopify" / "design" / "SKILL.md",
        )

    def workspace_expected_paths(self, workspace_root: Path) -> tuple[Path, ...]:
        """Expected output paths relative to workspace root (workspace-scope hosts only)."""
        paths: list[Path] = [workspace_root / self.destination_dirname / self.header_filename]
        if self.instruction_file_relpath is not None:
            paths.append(workspace_root / self.instruction_file_relpath)
        return tuple(paths)

    def global_skill_paths(self, home_root: Path) -> tuple[Path, ...]:
        skills_root = self.destination_root(home_root) / "skills" / "sopify"
        return (
            skills_root / "SKILL.md",
            skills_root / "analyze" / "SKILL.md",
            skills_root / "design" / "SKILL.md",
            skills_root / "develop" / "SKILL.md",
            skills_root / "kb" / "SKILL.md",
            skills_root / "templates" / "SKILL.md",
            skills_root / "references" / "shared-writing-dna.md",
            skills_root / "references" / "output-contract.md",
            skills_root / "analyze" / "scripts" / "score_requirement.py",
        )

    def user_plugin_paths(self, home_root: Path) -> tuple[Path, ...]:
        if self.instruction_file_relpath is None:
            raise InstallError(f"Host '{self.host_name}' has no user Plugin rule path")
        rule = home_root / self.instruction_file_relpath
        plugin_root = rule.parent.parent
        return (plugin_root / ".cursor-plugin" / "plugin.json", rule)

    def user_plugin_readme_path(self, home_root: Path) -> Path:
        """Return the user-visible README path for a user Plugin surface."""
        _, rule = self.user_plugin_paths(home_root)
        return rule.parent.parent / "README.md"

    def expected_payload_paths(self, home_root: Path) -> tuple[Path, ...]:
        payload_root = self.payload_root(home_root)
        return (
            payload_root / "payload-manifest.json",
            payload_root / "bundles",
            payload_root / "helpers" / "bootstrap_workspace.py",
        )

    def skill_install_path(
        self,
        *,
        home_root: Path,
        workspace_root: Path | None,
        skill_name: str,
    ) -> Path:
        """Return the host-native install directory for an optional Skill."""
        if self.skill_install_dirname is None:
            raise InstallError(
                f"Host '{self.host_name}' does not declare a Skill install path"
            )
        if self.is_workspace_scope:
            if workspace_root is None:
                raise InstallError(
                    f"Host '{self.host_name}' requires a workspace for Skill installation"
                )
            root = workspace_root
        else:
            root = home_root
        return root / self.skill_install_dirname / skill_name


@dataclass(frozen=True)
class HostRegistration:
    """Registry entry combining layout adapter and product capability metadata."""

    adapter: HostAdapter
    capability: HostCapability

    def __post_init__(self) -> None:
        if self.adapter.host_name != self.capability.host_id:
            raise ValueError(
                f"Host registration mismatch: adapter={self.adapter.host_name}, capability={self.capability.host_id}"
            )


def install_host_assets(
    adapter: HostAdapter,
    *,
    repo_root: Path,
    home_root: Path,
    language_directory: str,
    workspace_root: Path | None = None,
) -> InstallPhaseResult:
    """Install or update Sopify prompt-layer assets for one host.

    For workspace-scope hosts (instruction_surface=single_file), *workspace_root*
    is required and the rendered single file is written directly into the
    workspace (e.g. ``.github/copilot-instructions.md``).

    For home-scope hosts (header_embedded), assets are written under *home_root*.
    """
    if adapter.is_workspace_scope:
        return _install_single_file_assets(
            adapter,
            repo_root=repo_root,
            workspace_root=workspace_root,
            language_directory=language_directory,
        )
    if adapter.is_user_plugin_scope:
        from installer.cursor_plugin import install_cursor_user_plugin_assets

        return install_cursor_user_plugin_assets(
            adapter,
            repo_root=repo_root,
            home_root=home_root,
            language_directory=language_directory,
        )
    return _install_home_host_assets(
        adapter,
        repo_root=repo_root,
        home_root=home_root,
        language_directory=language_directory,
    )


def _install_home_host_assets(
    adapter: HostAdapter,
    *,
    repo_root: Path,
    home_root: Path,
    language_directory: str,
) -> InstallPhaseResult:
    """Install header + skills tree to home directory (Claude/Codex path)."""
    source_root = adapter.source_root(repo_root, language_directory)
    header_source = adapter.instruction_source(repo_root, language_directory)
    skills_source = source_root / "skills" / "sopify"
    if not header_source.is_file():
        raise InstallError(f"Missing source header file: {header_source}")
    if not skills_source.is_dir():
        raise InstallError(f"Missing source skills directory: {skills_source}")

    destination_root = adapter.destination_root(home_root)
    expected_paths = adapter.expected_paths(home_root)
    source_version = read_sopify_version(header_source)
    destination_header = destination_root / adapter.header_filename
    destination_version = read_sopify_version(destination_header)
    if source_version is not None and source_version == destination_version and all(path.exists() for path in expected_paths):
        return InstallPhaseResult(
            action="skipped",
            root=destination_root,
            version=source_version,
            paths=expected_paths,
        )

    action = "updated" if destination_root.exists() else "installed"
    destination_root.mkdir(parents=True, exist_ok=True)

    header_destination = destination_root / adapter.header_filename
    header_destination.parent.mkdir(parents=True, exist_ok=True)
    _render_header(header_source, header_destination, adapter)

    skills_destination = destination_root / "skills" / "sopify"
    if skills_destination.exists():
        shutil.rmtree(skills_destination)
    skills_destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(skills_source, skills_destination, ignore=_IGNORE_PATTERNS)

    return InstallPhaseResult(
        action=action,
        root=destination_root,
        version=source_version,
        paths=adapter.expected_paths(home_root),
    )


def _install_single_file_assets(
    adapter: HostAdapter,
    *,
    repo_root: Path,
    workspace_root: Path | None,
    language_directory: str,
) -> InstallPhaseResult:
    """Self-contained managed block in copilot-instructions.md (Copilot path).

    Writes full rendered rules into a managed block inside
    ``workspace/.github/copilot-instructions.md``.  Copilot CLI reads this
    file directly — the block must be self-contained.
    """
    if workspace_root is None:
        raise InstallError(
            f"Host '{adapter.host_name}' requires --workspace for single-file rendering"
        )
    source_root = adapter.source_root(repo_root, language_directory)
    header_template = source_root / HEADER_TEMPLATE_NAME
    header_source = header_template if header_template.is_file() else source_root / adapter.header_filename
    skills_source = source_root / "skills" / "sopify"
    if not header_source.is_file():
        raise InstallError(f"Missing source header file: {header_source}")
    if not skills_source.is_dir():
        raise InstallError(f"Missing source skills directory: {skills_source}")

    source_version = read_sopify_version(header_source)
    managed_block_file = workspace_root / adapter.destination_dirname / adapter.header_filename

    full_content = render_single_file(header_source, skills_source, adapter)

    # Content-based skip: extract existing managed block and compare strictly
    if managed_block_file.is_file():
        existing = managed_block_file.read_text(encoding="utf-8")
        match = re.search(
            rf"{re.escape(_MANAGED_BLOCK_BEGIN)}\n(.*?)\n{re.escape(_MANAGED_BLOCK_END)}",
            existing,
            re.DOTALL,
        )
        if match and match.group(1).strip() == full_content.strip():
            return InstallPhaseResult(
                action="skipped",
                root=workspace_root / adapter.destination_dirname,
                version=source_version,
                paths=adapter.workspace_expected_paths(workspace_root),
            )

    action = "updated" if managed_block_file.is_file() else "installed"

    managed_block_file.parent.mkdir(parents=True, exist_ok=True)
    _write_managed_block(managed_block_file, full_content)

    return InstallPhaseResult(
        action=action,
        root=workspace_root / adapter.destination_dirname,
        version=source_version,
        paths=adapter.workspace_expected_paths(workspace_root),
    )


_TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".txt", ".json", ".toml"}
_SKILL_DIRS_ORDER = ("analyze", "design", "develop", "kb", "templates")
_SINGLE_FILE_SCRIPT_HEADINGS = {
    "## 确定性逻辑（脚本优先）",
    "## Deterministic logic first",
}


def _render_single_file_skill_entry(content: str) -> str:
    """Remove tree-only script navigation from a flattened skill entry."""
    rendered: list[str] = []
    skipping_script_section = False
    for line in content.splitlines():
        if line in _SINGLE_FILE_SCRIPT_HEADINGS:
            skipping_script_section = True
            continue
        if skipping_script_section:
            if line.startswith("## "):
                skipping_script_section = False
            else:
                continue
        if "`scripts/" in line:
            continue
        line = line.replace("references/assets/scripts", "references/assets")
        rendered.append(line)
    return "\n".join(rendered).rstrip("\n")


def render_single_file(
    header_source: Path,
    skills_source: Path,
    adapter: HostAdapter,
) -> str:
    """Flatten header template + skill tree into a single instruction file.

    Returns the complete rendered content as a string.
    """
    # Render header
    header = header_source.read_text(encoding="utf-8")
    if adapter.config_dir is not None:
        header = header.replace("{{config_dir}}", adapter.config_dir)
    else:
        header = header.replace("{{config_dir}}", "")

    parts = [header.rstrip("\n")]

    # Inline shared top-level references (e.g. shared-writing-dna.md)
    shared_refs = skills_source / "references"
    if shared_refs.is_dir():
        for child in sorted(shared_refs.iterdir()):
            if child.is_file() and child.suffix in _TEXT_SUFFIXES:
                file_content = child.read_text(encoding="utf-8").rstrip("\n")
                rel_path = child.relative_to(skills_source)
                parts.append(f"<!-- inlined: {rel_path} -->\n{file_content}")

    # Flatten skills in deterministic order
    for skill_name in _SKILL_DIRS_ORDER:
        skill_dir = skills_source / skill_name
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            continue
        skill_content = _render_single_file_skill_entry(
            skill_md.read_text(encoding="utf-8")
        )
        parts.append(skill_content)
        # Scripts are tree-only executable helpers. The flattened product keeps
        # the equivalent rules from references/ and the user-facing assets.
        for subdir_name in ("references", "assets"):
            subdir = skill_dir / subdir_name
            if not subdir.is_dir():
                continue
            for child in sorted(subdir.iterdir()):
                if child.is_file() and child.suffix in _TEXT_SUFFIXES:
                    file_content = child.read_text(encoding="utf-8").rstrip("\n")
                    rel_path = child.relative_to(skills_source)
                    parts.append(f"<!-- inlined: {rel_path} -->\n{file_content}")

    return "\n\n---\n\n".join(parts) + "\n"


def _render_header(source: Path, destination: Path, adapter: HostAdapter) -> None:
    """Render header template with host-specific variables and write to destination."""
    content = source.read_text(encoding="utf-8")
    if adapter.config_dir is not None:
        content = content.replace("{{config_dir}}", adapter.config_dir)
    else:
        content = content.replace("{{config_dir}}", "")
    destination.write_text(content, encoding="utf-8")


def render_user_plugin_rule(source: Path, adapter: HostAdapter) -> str:
    """Render a Cursor Plugin rule with a portable user-directory Skill path."""
    content = source.read_text(encoding="utf-8")
    content = content.replace("{{config_dir}}", adapter.config_dir or "")
    if adapter.skill_install_dirname is None:
        raise InstallError(f"Host '{adapter.host_name}' has no global Skill install path")
    global_skill_root = f"~/{adapter.skill_install_dirname}/sopify"
    content = content.replace("{{skills_root}}", global_skill_root)
    return content.rstrip("\n") + "\n"


def _write_managed_block(path: Path, content: str) -> bool:
    """Upsert a managed instruction block, preserving user content outside markers.

    If the file already contains BEGIN/END markers, only the managed section is
    replaced.  Otherwise, the block is appended to the end of the file.
    Returns True when the file was actually changed.
    """
    block = "\n".join((_MANAGED_BLOCK_BEGIN, content.strip(), _MANAGED_BLOCK_END))
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""

    if _MANAGED_BLOCK_BEGIN in existing and _MANAGED_BLOCK_END in existing:
        new_content = re.sub(
            rf"{re.escape(_MANAGED_BLOCK_BEGIN)}.*?{re.escape(_MANAGED_BLOCK_END)}",
            lambda _: block,
            existing,
            count=1,
            flags=re.DOTALL,
        )
    else:
        base = existing.rstrip("\n")
        separator = "\n\n" if base else ""
        new_content = f"{base}{separator}{block}"

    new_content = new_content.rstrip("\n") + "\n"
    if new_content == existing:
        return False
    path.write_text(new_content, encoding="utf-8")
    return True


def read_sopify_version(path: Path) -> str | None:
    """Read the Sopify version header from a host prompt file when present."""
    if not path.is_file():
        return None
    match = _SOPIFY_VERSION_RE.search(path.read_text(encoding="utf-8"))
    if match is None:
        return None
    return match.group("version").strip()
