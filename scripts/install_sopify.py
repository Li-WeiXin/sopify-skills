#!/usr/bin/env python3
"""Install Sopify host prompts and the global payload, then optionally prewarm a workspace."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from installer.distribution import (
    BootstrapOnlyResult,
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
    install_evidentloop_companion,
    prepare_evidentloop_install,
)
from installer.cursor_hooks import install_cursor_user_hooks, preflight_cursor_user_hooks
from installer.hosts import get_host_adapter, iter_host_registrations, iter_installable_hosts
from installer.hosts.base import HostAdapter, install_host_assets
from installer.models import BootstrapResult, EvidentLoopInstallResult, InstallError, InstallPhaseResult, InstallResult, LANGUAGE_DIRECTORY_MAP, parse_install_target
from installer.payload import install_global_payload, run_workspace_bootstrap
from installer.validate import (
    validate_bundle_install,
    validate_host_install,
    validate_payload_install,
    validate_workspace_stub_manifest,
)
from scripts.sopify_init import init_workspace, _LOGO_LINES, _LOGO_COLOR, _LOGO_RESET


def build_parser() -> argparse.ArgumentParser:
    supported_targets = ", ".join(
        f"{capability.host_id}:{language}"
        for capability in iter_installable_hosts()
        for language in LANGUAGE_DIRECTORY_MAP
    )
    # Append bare targets for hosts that accept them (have default_language)
    bare_targets = [
        reg.adapter.host_name
        for reg in iter_host_registrations()
        if reg.capability.install_enabled and reg.adapter.default_language
    ]
    if bare_targets:
        supported_targets = supported_targets + ", " + ", ".join(bare_targets)
    parser = argparse.ArgumentParser(
        description=(
            "Install Sopify for a host. Workspace-scope hosts (e.g. copilot) bootstrap directly; "
            "for Codex / Claude this installs the host prompt and Sopify kernel only, and "
            "project files are initialized later when you run `~go` in a workspace."
        )
    )
    parser.add_argument(
        "--target",
        default=None,
        help=f"Host and language to install, for example codex:zh-CN. Supported: {supported_targets}",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help=(
            "For Copilot: bootstrap this workspace now (defaults to current directory). "
            "For Cursor: write the project rule into this workspace (defaults to current directory); "
            "this does not create `.sopify`. "
            "For Codex / Claude / Qoder: advanced prewarm path. Most of those users should omit this."
        ),
    )
    parser.add_argument("--language", choices=("en-US", "zh-CN"), default=None, help="Override output language for bare targets.")
    parser.add_argument(
        "--ref",
        default=None,
        help="Advanced: override the remote source ref. Not supported for repo-local installs.",
    )
    parser.add_argument("--verbose", action="store_true", help="Show full diagnostic install details.")
    parser.add_argument(
        "--with-evidentloop",
        action="store_true",
        help=(
            "Install the current EvidentLoop CLI and Skill from their official sources, "
            "or reuse healthy existing components. This option is disabled by default "
            "and is not a runtime switch."
        ),
    )
    parser.add_argument("--source-channel", default="repo-local", help=argparse.SUPPRESS)
    parser.add_argument("--source-resolved-ref", default="working-tree", help=argparse.SUPPRESS)
    parser.add_argument("--source-asset-name", default="scripts/install_sopify.py", help=argparse.SUPPRESS)
    return parser


def run_install(
    *,
    target_value: str,
    workspace_value: str | None,
    repo_root: Path,
    home_root: Path | None = None,
    with_evidentloop: bool = False,
) -> InstallResult | BootstrapOnlyResult:
    target = parse_install_target(target_value)
    workspace_root = Path(workspace_value).expanduser().resolve() if workspace_value is not None else None
    adapter = get_host_adapter(target.host)
    if with_evidentloop and adapter.skills_cli_agent is None:
        raise InstallError(
            f"Host '{adapter.host_name}' does not support --with-evidentloop in this release."
        )
    if adapter.requires_workspace and workspace_root is None:
        workspace_root = Path.cwd().resolve()
    if workspace_root is not None and not workspace_root.exists():
        raise InstallError(f"Workspace does not exist: {workspace_root}")
    if workspace_root is not None and not workspace_root.is_dir():
        raise InstallError(f"Workspace is not a directory: {workspace_root}")

    resolved_home = (home_root or Path.home()).expanduser().resolve()
    if adapter.host_name == "cursor":
        preflight_cursor_user_hooks(home_root=resolved_home)
    if adapter.is_workspace_scope:
        # Workspace-scope hosts (e.g. Copilot): render single file to workspace,
        # skip payload install and workspace bootstrap.
        host_install = install_host_assets(
            adapter,
            repo_root=repo_root,
            home_root=resolved_home,
            language_directory=target.language_directory,
            workspace_root=workspace_root,
        )
        evidentloop_install = _install_evidentloop_if_requested(
            enabled=with_evidentloop,
            adapter=adapter,
            home_root=resolved_home,
            workspace_root=workspace_root,
        )
        return InstallResult(
            target=target,
            workspace_root=workspace_root,
            host_root=host_install.root,
            payload_root=host_install.root,
            bundle_root=None,
            host_install=host_install,
            payload_install=InstallPhaseResult(
                action="skipped",
                root=host_install.root,
                version=host_install.version,
                paths=(),
            ),
            workspace_bootstrap=None,
            smoke_output="",
            evidentloop_install=evidentloop_install,
        )

    host_install = install_host_assets(
        adapter,
        repo_root=repo_root,
        home_root=resolved_home,
        language_directory=target.language_directory,
        workspace_root=workspace_root,
    )
    payload_install = install_global_payload(adapter, repo_root=repo_root, home_root=resolved_home)
    verified_host_paths = validate_host_install(adapter, home_root=resolved_home)
    if adapter.requires_workspace:
        workspace_paths = adapter.workspace_expected_paths(workspace_root)
        missing_workspace_paths = [path for path in workspace_paths if not path.exists()]
        if missing_workspace_paths:
            raise InstallError(f"Host install verification failed: {missing_workspace_paths[0]}")
        verified_host_paths = tuple(dict.fromkeys((*verified_host_paths, *workspace_paths)))
    verified_payload_paths = validate_payload_install(payload_install.root)
    if adapter.host_name == "cursor":
        hook_path = install_cursor_user_hooks(
            home_root=resolved_home,
            payload_root=payload_install.root,
        )
        verified_host_paths = tuple(dict.fromkeys((*verified_host_paths, hook_path)))

    workspace_bootstrap: BootstrapResult | None = None
    bundle_root: Path | None = None
    if workspace_root is not None and not adapter.is_project_rules_scope:
        workspace_bootstrap = run_workspace_bootstrap(payload_install.root, workspace_root)
        bundle_root = workspace_bootstrap.bundle_root
        validate_workspace_stub_manifest(workspace_root / ".sopify")

    evidentloop_install = _install_evidentloop_if_requested(
        enabled=with_evidentloop,
        adapter=adapter,
        home_root=resolved_home,
        workspace_root=workspace_root,
    )

    return InstallResult(
        target=target,
        workspace_root=workspace_root,
        host_root=adapter.destination_root(resolved_home),
        payload_root=payload_install.root,
        bundle_root=bundle_root,
        host_install=host_install.__class__(
            action=host_install.action,
            root=host_install.root,
            version=host_install.version,
            paths=tuple(dict.fromkeys((*host_install.paths, *verified_host_paths))),
        ),
        payload_install=payload_install.__class__(
            action=payload_install.action,
            root=payload_install.root,
            version=payload_install.version,
            paths=tuple(dict.fromkeys((*payload_install.paths, *verified_payload_paths))),
        ),
        workspace_bootstrap=workspace_bootstrap,
        smoke_output="",
        evidentloop_install=evidentloop_install,
    )


def _install_evidentloop_if_requested(
    *,
    enabled: bool,
    adapter: HostAdapter,
    home_root: Path,
    workspace_root: Path | None,
) -> EvidentLoopInstallResult | None:
    if not enabled:
        return None
    try:
        plan = prepare_evidentloop_install(
            adapter,
            home_root=home_root,
            workspace_root=workspace_root,
        )
        return install_evidentloop_companion(plan)
    except InstallError as exc:
        raise InstallError(
            "Sopify core installation completed, but EvidentLoop setup did not complete."
        ) from exc


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    verbose = args.verbose or _env_flag_enabled(os.environ.get("SOPIFY_DEBUG"))
    normalized_target = args.target
    # Expand bare targets for hosts with default_language (e.g. "copilot" → "copilot:zh-CN")
    if normalized_target and ":" not in normalized_target:
        try:
            adapter = get_host_adapter(normalized_target)
            if adapter.default_language:
                lang = args.language or _detect_default_output_language()
                normalized_target = f"{normalized_target}:{lang}"
        except ValueError:
            pass
    output_language = _infer_output_language(normalized_target)
    source_metadata = DistributionSourceMetadata(
        resolved_ref=args.source_resolved_ref,
        asset_name=args.source_asset_name,
    )
    request = DistributionRequest(
        target=normalized_target,
        workspace=args.workspace,
        ref_override=args.ref,
        interactive=sys.stdin.isatty() and sys.stdout.isatty(),
        source_channel=args.source_channel,
        source_metadata=source_metadata,
        with_evidentloop=args.with_evidentloop,
    )

    try:
        report = run_distribution_install(
            request=request,
            repo_root=REPO_ROOT,
            home_root=None,
            install_executor=run_install,
        )
    except DistributionError as exc:
        if verbose:
            rendered_error = render_distribution_error(exc)
        else:
            rendered_error = render_distribution_user_error(exc, language=output_language)
        print(rendered_error, file=sys.stderr)
        return 1
    except InstallError as exc:
        if verbose:
            print(f"Install failed: {exc}", file=sys.stderr)
        elif output_language == "zh-CN":
            print(f"Sopify 安装失败：{exc}\n\n诊断信息：\n  reason_code: INSTALLER_FAILED", file=sys.stderr)
        else:
            print(f"Sopify install failed: {exc}\n\nDiagnostics:\n  reason_code: INSTALLER_FAILED", file=sys.stderr)
        return 1

    if isinstance(report.install_result, BootstrapOnlyResult) and sys.stdout.isatty() and not os.environ.get("SOPIFY_LOGO_PRINTED"):
        use_color = os.environ.get("NO_COLOR") is None
        for line in _LOGO_LINES:
            print(f"{_LOGO_COLOR}{line}{_LOGO_RESET}" if use_color else line)
        print()
    print(render_distribution_result(report) if verbose else render_distribution_user_result(report))
    return 0


def _env_flag_enabled(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _infer_output_language(target_value: str | None) -> str:
    return "zh-CN" if str(target_value or "").strip().endswith(":zh-CN") else "en-US"


def _detect_default_output_language() -> str:
    lang_env = os.environ.get("LANG", "")
    if "zh" in lang_env.lower():
        return "zh-CN"
    return "en-US"


if __name__ == "__main__":
    raise SystemExit(main())
