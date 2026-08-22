"""Shared distribution facade for repo-local and one-liner installer entrypoints."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable, TextIO

from installer.hosts import get_host_adapter, iter_host_registrations, iter_installable_hosts
from installer.inspection import build_doctor_payload, build_status_payload
from installer.models import (
    EvidentLoopInstallResult,
    InstallError,
    InstallResult,
    InstallTarget,
    LANGUAGE_DIRECTORY_MAP,
)
from installer.outcome_contract import render_outcome_summary

SOURCE_CHANNEL_REPO_LOCAL = "repo-local"
DEFAULT_REPO_LOCAL_REF = "working-tree"
DEFAULT_REPO_LOCAL_ASSET = "scripts/install_sopify.py"
WORKSPACE_NOT_REQUESTED_REASON = "WORKSPACE_NOT_REQUESTED"

_CHECK_LABELS = {
    "host_prompt_present": "host prompt",
    "payload_present": "payload",
    "payload_bundle_resolution": "payload bundle",
    "workspace_bundle_manifest": "workspace bundle",
    "workspace_ingress_proof": "workspace ingress proof",
    "workspace_handoff_first": "handoff-first protocol",
    "bundle_smoke": "smoke",
}


@dataclass(frozen=True)
class DistributionSourceMetadata:
    """Resolved source metadata surfaced by distribution entrypoints."""

    resolved_ref: str
    asset_name: str


@dataclass(frozen=True)
class DistributionRequest:
    """Minimal input contract shared by repo-local and remote entrypoints."""

    target: str | None
    workspace: str | None
    ref_override: str | None
    interactive: bool
    source_channel: str
    source_metadata: DistributionSourceMetadata
    with_evidentloop: bool = False


@dataclass(frozen=True)
class DistributionInstallReport:
    """Public-facing install report produced by the shared distribution facade."""

    request: DistributionRequest
    install_result: InstallResult | BootstrapOnlyResult
    status_payload: dict[str, object]
    doctor_payload: dict[str, object]
    next_step: str


@dataclass(frozen=True)
class BootstrapOnlyResult:
    """Summary for unified-entrypoint bootstrap-only targets such as Copilot."""

    target: InstallTarget
    workspace_root: Path
    bundle_version: str | None
    details: tuple[str, ...]


class DistributionError(RuntimeError):
    """Raised when distribution entrypoints cannot complete safely."""

    def __init__(self, *, phase: str, reason_code: str, detail: str, next_step: str) -> None:
        super().__init__(detail)
        self.phase = phase
        self.reason_code = reason_code
        self.detail = detail
        self.next_step = next_step


InstallExecutor = Callable[..., InstallResult | BootstrapOnlyResult]


def default_source_metadata(
    *,
    source_channel: str = SOURCE_CHANNEL_REPO_LOCAL,
    resolved_ref: str = DEFAULT_REPO_LOCAL_REF,
    asset_name: str = DEFAULT_REPO_LOCAL_ASSET,
) -> DistributionSourceMetadata:
    """Return the default repo-local metadata used by local installer entrypoints."""
    return DistributionSourceMetadata(resolved_ref=resolved_ref, asset_name=asset_name)


def run_distribution_install(
    *,
    request: DistributionRequest,
    repo_root: Path,
    home_root: Path | None,
    install_executor: InstallExecutor,
    input_func: Callable[[str], str] = input,
    output_stream: TextIO | None = None,
) -> DistributionInstallReport:
    """Execute the shared install flow and attach post-install verification output."""
    if request.source_channel == SOURCE_CHANNEL_REPO_LOCAL and request.ref_override is not None:
        raise DistributionError(
            phase="input",
            reason_code="REF_OVERRIDE_UNSUPPORTED_FOR_REPO_LOCAL",
            detail="`--ref` is only supported for remote install entrypoints.",
            next_step="Drop `--ref` for repo-local installs, or use root `install.sh` / `install.ps1` for ref-pinned installs.",
        )

    target_value = _resolve_target_value(
        request=request,
        input_func=input_func,
        output_stream=output_stream or sys.stderr,
    )
    resolved_home = (home_root or Path.home()).expanduser().resolve()

    try:
        install_kwargs = {
            "target_value": target_value,
            "workspace_value": request.workspace,
            "repo_root": repo_root,
            "home_root": resolved_home,
        }
        if request.with_evidentloop:
            install_kwargs["with_evidentloop"] = True
        install_result = install_executor(**install_kwargs)
    except InstallError as exc:
        raise _map_install_error(exc) from exc

    if isinstance(install_result, BootstrapOnlyResult):
        status_payload = {
            "state": {"overall_status": "workspace_ready"},
            "workspace_state": {
                "requested": True,
                "root": str(install_result.workspace_root),
                "bootstrap_mode": "bootstrap_only",
            },
            "hosts": [
                {
                    "host_id": install_result.target.host,
                    "support_tier": "baseline_supported",
                    "install_enabled": True,
                    "state": {
                        "installed": "not_applicable",
                        "configured": "workspace_ready",
                        "workspace_bundle_healthy": "yes",
                        "workspace_ingress_proof": "not_requested",
                    },
                    "payload_bundle": {
                        "source_kind": "bootstrap_only",
                        "reason_code": "BOOTSTRAP_ONLY_TARGET",
                    },
                    "workspace_bundle": {
                        "reason_code": "WORKSPACE_BOOTSTRAPPED",
                    },
                }
            ],
        }
        doctor_payload = {"checks": []}
    else:
        try:
            status_payload = build_status_payload(home_root=resolved_home, workspace_root=install_result.workspace_root)
            doctor_payload = build_doctor_payload(home_root=resolved_home, workspace_root=install_result.workspace_root)
        except Exception as exc:  # pragma: no cover - defensive wrapper for unexpected verification regressions.
            raise DistributionError(
                phase="verification",
                reason_code="POST_INSTALL_VERIFICATION_FAILED",
                detail=f"Post-install verification failed unexpectedly: {exc}",
                next_step="Rerun the installer. If the failure persists, use the inspect-first path and review the local source snapshot.",
            ) from exc

    return DistributionInstallReport(
        request=request,
        install_result=install_result,
        status_payload=status_payload,
        doctor_payload=doctor_payload,
        next_step=_build_next_step(install_result.target, install_result.workspace_root),
    )


def render_distribution_result(report: DistributionInstallReport) -> str:
    """Render the full diagnostic install summary for repo-local and remote entrypoints."""
    install_result = report.install_result
    if isinstance(install_result, BootstrapOnlyResult):
        details = "\n".join(f"  - {item}" for item in install_result.details)
        return "\n".join(
            [
                "Initialized Sopify workspace successfully:",
                f"  target: {install_result.target.value}",
                f"  source channel: {report.request.source_channel}",
                f"  resolved source ref: {report.request.source_metadata.resolved_ref}",
                f"  asset name: {report.request.source_metadata.asset_name}",
                f"  workspace: {install_result.workspace_root}",
                f"  bundle version: {install_result.bundle_version or 'unknown'}",
                "",
                "Bootstrap details:",
                details or "  - none",
                "",
                f"Next: {report.next_step}",
            ]
        )
    selected_host = _select_host_status(report.status_payload, install_result.target)
    selected_checks = _select_host_checks(report.doctor_payload, install_result.target)
    payload_bundle = selected_host.get("payload_bundle") or {}
    workspace_bundle = selected_host.get("workspace_bundle") or {}
    payload_outcome = render_outcome_summary(payload_bundle)
    workspace_outcome = render_outcome_summary(workspace_bundle)
    workspace_line = _render_workspace_line(install_result)
    action_lines = [
        f"  host prompt: {install_result.host_install.action}",
        f"  payload: {install_result.payload_install.action}",
        f"  workspace bootstrap: {_workspace_bootstrap_action(install_result)}",
    ]
    if install_result.evidentloop_install is not None:
        action_lines.extend(
            _companion_action_lines(
                install_result.evidentloop_install,
                language="en-US",
            )
        )
    lines = [
        "Sopify already current:" if _is_noop_install(install_result) else "Installed Sopify successfully:",
        f"  target: {install_result.target.value}",
        f"  source channel: {report.request.source_channel}",
        f"  resolved source ref: {report.request.source_metadata.resolved_ref}",
        f"  asset name: {report.request.source_metadata.asset_name}",
        f"  host root: {install_result.host_root}",
        f"  payload root: {install_result.payload_root}",
        f"  workspace: {workspace_line}",
        f"  bundle root: {install_result.bundle_root if install_result.bundle_root is not None else '(not requested)'}",
        "",
        "Install actions:",
        *action_lines,
        "",
        "Verification:",
        (
            "  payload bundle: source_kind={source_kind}, reason_code={reason_code}".format(
                source_kind=payload_bundle.get("source_kind", "unresolved"),
                reason_code=payload_bundle.get("reason_code", "GLOBAL_INDEX_CORRUPTED"),
            )
        ),
        (
            "  host state: installed={installed}, configured={configured}, workspace_bundle_healthy={workspace_bundle_healthy}".format(
                installed=selected_host["state"]["installed"],
                configured=selected_host["state"]["configured"],
                workspace_bundle_healthy=selected_host["state"]["workspace_bundle_healthy"],
            )
        ),
    ]
    if payload_outcome:
        lines.append(f"  payload outcome: {payload_outcome}")
    if payload_bundle.get("recommendation"):
        lines.append(f"  payload hint: {payload_bundle['recommendation']}")
    if workspace_outcome:
        lines.append(f"  workspace outcome: {workspace_outcome}")
    if workspace_bundle.get("recommendation"):
        lines.append(f"  workspace hint: {workspace_bundle['recommendation']}")
    lines.extend(
        f"  - {_CHECK_LABELS.get(check['check_id'], check['check_id'])}: {check['status']} ({check['reason_code']})"
        for check in selected_checks
    )
    lines.extend(
        [
            "",
            f"  smoke output: {_first_smoke_line(install_result.smoke_output)}",
            f"  overall status: {report.status_payload['state']['overall_status']}",
            "",
            f"Next: {report.next_step}",
        ]
    )
    return "\n".join(lines)


def render_distribution_user_result(report: DistributionInstallReport) -> str:
    """Render the default user-facing install summary."""
    install_result = report.install_result
    if isinstance(install_result, BootstrapOnlyResult):
        return _render_distribution_bootstrap_user_result(report)
    # Workspace-scope hosts (e.g. Copilot): simpler output, no runtime/bundle/~go
    try:
        adapter = get_host_adapter(install_result.target.host)
    except KeyError:
        adapter = None
    if adapter is not None and adapter.is_workspace_scope:
        if install_result.target.language == "zh-CN":
            return _render_workspace_scope_result_zh(report)
        return _render_workspace_scope_result_en(report)
    if install_result.target.language == "zh-CN":
        return _render_distribution_user_result_zh(report)
    return _render_distribution_user_result_en(report)


def render_distribution_error(exc: DistributionError) -> str:
    """Render a stable error surface for shell, PowerShell, and repo-local installs."""
    title = (
        "Sopify installed; EvidentLoop setup did not complete:"
        if exc.reason_code == "EVIDENTLOOP_COMPANION_INCOMPLETE"
        else "Sopify install failed:"
    )
    return "\n".join(
        [
            title,
            f"  phase: {exc.phase}",
            f"  reason_code: {exc.reason_code}",
            f"  detail: {exc.detail}",
            f"  next_step: {exc.next_step}",
        ]
    )


def render_distribution_user_error(exc: DistributionError, *, language: str = "en-US") -> str:
    """Render a human-first install error while preserving diagnostic codes."""
    if exc.reason_code == "EVIDENTLOOP_COMPANION_INCOMPLETE":
        if language == "zh-CN":
            return "\n".join(
                [
                    "Sopify 已安装，可以正常使用。",
                    "EvidentLoop 安装未完成。",
                    "",
                    "下一步：",
                    "  可重新运行同一命令，或单独安装 EvidentLoop：",
                    "  https://github.com/evidentloop/evidentloop",
                ]
            )
        return "\n".join(
            [
                "Sopify is installed and ready to use.",
                "EvidentLoop setup did not complete.",
                "",
                "Next:",
                f"  {exc.next_step}",
            ]
        )
    if language == "zh-CN":
        lines = [
            f"Sopify 安装失败：{exc.detail}",
            "",
            "修复方式：",
            f"  {exc.next_step}",
            "",
            "诊断信息：",
            f"  reason_code: {exc.reason_code}",
            f"  phase: {exc.phase}",
        ]
        return "\n".join(lines)

    lines = [
        f"Sopify install failed: {exc.detail}",
        "",
        "Fix:",
        f"  {exc.next_step}",
        "",
        "Diagnostics:",
        f"  reason_code: {exc.reason_code}",
        f"  phase: {exc.phase}",
    ]
    return "\n".join(lines)


def _resolve_target_value(
    *,
    request: DistributionRequest,
    input_func: Callable[[str], str],
    output_stream: TextIO,
) -> str:
    if request.target:
        return request.target
    if not request.interactive:
        first_option = _target_options()[0]
        raise DistributionError(
            phase="input",
            reason_code="TARGET_REQUIRED",
            detail="Non-interactive installs must provide `--target <host:lang>`.",
            next_step=f"Re-run the installer with `--target {first_option}`.",
        )
    options = _target_options()
    output_stream.write("Select Sopify install target:\n")
    for index, option in enumerate(options, start=1):
        output_stream.write(f"  {index}. {option}\n")
    answer = input_func("Target number: ").strip()
    if not answer.isdigit():
        raise DistributionError(
            phase="input",
            reason_code="INVALID_TARGET_SELECTION",
            detail=f"Expected a numeric target selection, got: {answer or '(empty)'}",
            next_step=f"Choose one of the numbered options above, or pass `--target {options[0]}` directly.",
        )
    selected_index = int(answer) - 1
    if selected_index < 0 or selected_index >= len(options):
        raise DistributionError(
            phase="input",
            reason_code="INVALID_TARGET_SELECTION",
            detail=f"Target selection {answer} is out of range.",
            next_step=f"Choose a number between 1 and {len(options)}, or pass `--target {options[0]}` directly.",
        )
    return options[selected_index]


def _target_options() -> tuple[str, ...]:
    options = [
        f"{capability.host_id}:{language}"
        for capability in iter_installable_hosts()
        for language in LANGUAGE_DIRECTORY_MAP
    ]
    # Append bare targets for hosts that accept them (have default_language)
    for reg in iter_host_registrations():
        if reg.capability.install_enabled and reg.adapter.default_language:
            options.append(reg.adapter.host_name)
    return tuple(options)


def _map_install_error(exc: InstallError) -> DistributionError:
    detail = str(exc)
    if detail.startswith("Target must use the format"):
        return DistributionError(
            phase="input",
            reason_code="INVALID_TARGET_FORMAT",
            detail=detail,
            next_step=f"Use one of the supported targets: {', '.join(_target_options())}.",
        )
    if detail.startswith("Unsupported host:"):
        return DistributionError(
            phase="input",
            reason_code="UNSUPPORTED_HOST",
            detail=detail,
            next_step=f"Use one of the supported targets: {', '.join(_target_options())}.",
        )
    if detail.startswith("Unsupported language:"):
        return DistributionError(
            phase="input",
            reason_code="UNSUPPORTED_LANGUAGE",
            detail=detail,
            next_step="Use one of the supported language codes: zh-CN, en-US.",
        )
    if detail.startswith("Workspace does not exist:"):
        return DistributionError(
            phase="input",
            reason_code="WORKSPACE_NOT_FOUND",
            detail=detail,
            next_step="Pass an existing project directory to `--workspace`, or omit the internal prewarm flag and bootstrap on first project trigger instead.",
        )
    if detail.startswith("Workspace is not a directory:"):
        return DistributionError(
            phase="input",
            reason_code="WORKSPACE_NOT_DIRECTORY",
            detail=detail,
            next_step="Pass a project directory to `--workspace`, or omit the internal prewarm flag and bootstrap on first project trigger instead.",
        )
    if detail.startswith("Workspace prewarm requires explicit activation-root selection"):
        return DistributionError(
            phase="install",
            reason_code="WORKSPACE_PREWARM_ROOT_AMBIGUOUS",
            detail=detail,
            next_step="Omit `--workspace` and trigger Sopify inside that project instead. On first activation, choose whether to enable the current directory or the repository root.",
        )
    if detail.startswith(
        "Sopify core installation completed, but EvidentLoop setup did not complete"
    ):
        return DistributionError(
            phase="install",
            reason_code="EVIDENTLOOP_COMPANION_INCOMPLETE",
            detail=detail,
            next_step="Rerun the same command, or install EvidentLoop separately: https://github.com/evidentloop/evidentloop",
        )
    if detail.startswith("Missing source"):
        return DistributionError(
            phase="install",
            reason_code="INSTALLER_SOURCE_INCOMPLETE",
            detail=detail,
            next_step="Retry from a clean source snapshot or stable release asset.",
        )
    if detail.startswith("Host install verification failed:"):
        return DistributionError(
            phase="install",
            reason_code="HOST_VERIFICATION_FAILED",
            detail=detail,
            next_step="Rerun the installer. If it still fails, inspect the downloaded source snapshot and host home directory permissions.",
        )
    if detail.startswith("Payload verification failed:"):
        return DistributionError(
            phase="install",
            reason_code="PAYLOAD_VERIFICATION_FAILED",
            detail=detail,
            next_step="Rerun the installer. If it still fails, inspect the payload directory under the selected host home root.",
        )
    if detail.startswith("Bundle verification failed:"):
        return DistributionError(
            phase="install",
            reason_code="WORKSPACE_BUNDLE_VERIFICATION_FAILED",
            detail=detail,
            next_step="Trigger Sopify in that project to bootstrap on demand. If the issue persists, refresh the local install and retry.",
        )
    if detail.startswith("Missing bundle smoke script:"):
        return DistributionError(
            phase="verification",
            reason_code="BUNDLE_SMOKE_SCRIPT_MISSING",
            detail=detail,
            next_step="Refresh the payload from a clean release asset or repo-local installer snapshot.",
        )
    if detail.startswith("Bundle smoke check failed:"):
        return DistributionError(
            phase="verification",
            reason_code="BUNDLE_SMOKE_FAILED",
            detail=detail,
            next_step="Rerun the installer. If the failure persists, use the inspect-first path and review the bundle smoke output.",
        )
    return DistributionError(
        phase="install",
        reason_code="INSTALLER_FAILED",
        detail=detail,
        next_step="Rerun the installer. If the failure persists, switch to the inspect-first path and review the source snapshot locally.",
    )


def _build_next_step(target: InstallTarget, workspace_root: Path | None) -> str:
    adapter = get_host_adapter(target.host)
    if adapter.is_workspace_scope:
        if workspace_root is None:
            return f"Open {target.host.title()} in your project workspace to start using Sopify."
        return f"Open {target.host.title()} in {workspace_root} to start using Sopify."
    if adapter.is_user_plugin_scope:
        return (
            "Restart Cursor or run Developer: Reload Window, then open a target repository and "
            "verify the Sopify user Plugin is enabled. "
            "The installer does not modify project files."
        )
    if workspace_root is None:
        return (
            f"Open {target.host} in any project workspace and trigger Sopify. "
            "Workspace bootstrap will run on first project trigger."
        )
    return f"Open {target.host} in {workspace_root} and trigger Sopify."


def _render_distribution_user_result_en(report: DistributionInstallReport) -> str:
    install_result = report.install_result
    title = "Sopify is already current." if _is_noop_install(install_result) else "Sopify installed successfully."
    host_name = _host_display_name(install_result.target.host)
    installed_lines = [
        f"  Host: {host_name} ({install_result.target.value})",
        f"  Language: {_language_display_name(install_result.target.language, 'en-US')}",
        f"  Host prompt: {_action_label(install_result.host_install.action, 'en-US')}",
        f"  Runtime: {install_result.payload_root}",
        f"  Version: {install_result.payload_install.version or 'unknown'}",
        f"  Runtime action: {_action_label(install_result.payload_install.action, 'en-US')}",
    ]
    if install_result.evidentloop_install is not None:
        installed_lines.extend(
            _companion_action_lines(install_result.evidentloop_install, language="en-US")
        )
    lines = [
        title,
        "",
        "Installed:",
        *installed_lines,
        "",
        "Project:",
    ]
    if _is_user_plugin_install(install_result):
        lines.extend(
            [
                f"  User Plugin rule: {_user_plugin_rule_path(install_result)}",
                "  No project directory or .sopify state was changed.",
                "",
                "Next:",
                "  1. Restart Cursor or run `Developer: Reload Window`.",
                f"  2. Open {host_name} in a target repository.",
                "  3. Confirm the Sopify Plugin and its Always Rule in Cursor Settings before relying on host behavior.",
            ]
        )
    elif install_result.workspace_root is None:
        lines.extend(
            [
                "  No project directory was changed.",
                "  Sopify will initialize project files the first time you run `~go` in a workspace.",
                "",
                "Next:",
                f"  1. Open {host_name} in your project directory.",
                "  2. Type: ~go",
            ]
        )
    else:
        lines.extend(
            [
                f"  Prewarmed: {install_result.workspace_root}",
                f"  Bundle: {install_result.bundle_root if install_result.bundle_root is not None else '(not requested)'}",
                "",
                "Next:",
                f"  1. Reopen {host_name} in that project.",
                "  2. Type: ~go",
            ]
        )
    lines.extend(
        [
            "",
            "Diagnostics:",
            f"  {_friendly_smoke_summary(install_result.smoke_output, 'en-US')}",
            "  Run again with `--verbose` for full install details.",
        ]
    )
    return "\n".join(lines)


def _render_distribution_user_result_zh(report: DistributionInstallReport) -> str:
    install_result = report.install_result
    title = "Sopify 已是最新。" if _is_noop_install(install_result) else "Sopify 安装完成。"
    host_name = _host_display_name(install_result.target.host)
    installed_lines = [
        f"  宿主：{host_name}（{install_result.target.value}）",
        f"  语言：{_language_display_name(install_result.target.language, 'zh-CN')}",
        f"  宿主提示：{_action_label(install_result.host_install.action, 'zh-CN')}",
        f"  运行时：{install_result.payload_root}",
        f"  版本：{install_result.payload_install.version or 'unknown'}",
        f"  运行时操作：{_action_label(install_result.payload_install.action, 'zh-CN')}",
    ]
    if install_result.evidentloop_install is not None:
        installed_lines.extend(
            _companion_action_lines(install_result.evidentloop_install, language="zh-CN")
        )
    lines = [
        title,
        "",
        "已安装：",
        *installed_lines,
        "",
        "项目：",
    ]
    if _is_user_plugin_install(install_result):
        lines.extend(
            [
                f"  用户 Plugin 规则：{_user_plugin_rule_path(install_result)}",
                "  未修改任何项目目录，也未初始化 .sopify 状态。",
                "",
                "下一步：",
                "  1. 重启 Cursor，或执行 `Developer: Reload Window`。",
                f"  2. 在目标仓库中打开 {host_name}。",
                "  3. 使用前请在 Cursor Settings 中确认 Sopify Plugin 及其 Always Rule 已启用。",
            ]
        )
    elif install_result.workspace_root is None:
        lines.extend(
            [
                "  这次没有修改任何项目目录。",
                "  进入项目后第一次输入 `~go` 时，会自动初始化 Sopify 项目文件。",
                "",
                "下一步：",
                f"  1. 在项目目录打开 {host_name}。",
                "  2. 输入：~go",
            ]
        )
    else:
        lines.extend(
            [
                f"  已预热：{install_result.workspace_root}",
                f"  Bundle：{install_result.bundle_root if install_result.bundle_root is not None else '(not requested)'}",
                "",
                "下一步：",
                f"  1. 在该项目中重新打开 {host_name}。",
                "  2. 输入：~go",
            ]
        )
    lines.extend(
        [
            "",
            "诊断：",
            f"  {_friendly_smoke_summary(install_result.smoke_output, 'zh-CN')}",
            "  需要完整安装细节时，请加 `--verbose` 重新运行。",
        ]
    )
    return "\n".join(lines)


def _render_workspace_scope_result_zh(report: DistributionInstallReport) -> str:
    install_result = report.install_result
    assert isinstance(install_result, InstallResult)
    title = "Sopify 已是最新。" if _is_noop_install(install_result) else "Sopify 安装完成。"
    host_name = _host_display_name(install_result.target.host)
    lines = [
        title,
        "",
        "已安装：",
        f"  宿主：{host_name}（{install_result.target.value}）",
        f"  语言：{_language_display_name(install_result.target.language, 'zh-CN')}",
        f"  宿主提示：{_action_label(install_result.host_install.action, 'zh-CN')}",
        f"  版本：{install_result.host_install.version or 'unknown'}",
    ]
    if install_result.evidentloop_install is not None:
        companion = install_result.evidentloop_install
        lines.extend(_companion_action_lines(companion, language="zh-CN"))
    for p in install_result.host_install.paths:
        lines.append(f"  文件：{p}")
    lines.extend(
        [
            "",
            "下一步：",
            f"  1. 在项目目录打开 {host_name}。",
            "  2. Sopify 指令已自动加载，直接开始你的任务。",
        ]
    )
    return "\n".join(lines)


def _render_workspace_scope_result_en(report: DistributionInstallReport) -> str:
    install_result = report.install_result
    assert isinstance(install_result, InstallResult)
    title = "Sopify is already current." if _is_noop_install(install_result) else "Sopify installed successfully."
    host_name = _host_display_name(install_result.target.host)
    lines = [
        title,
        "",
        "Installed:",
        f"  Host: {host_name} ({install_result.target.value})",
        f"  Language: {_language_display_name(install_result.target.language, 'en-US')}",
        f"  Host prompt: {_action_label(install_result.host_install.action, 'en-US')}",
        f"  Version: {install_result.host_install.version or 'unknown'}",
    ]
    if install_result.evidentloop_install is not None:
        companion = install_result.evidentloop_install
        lines.extend(_companion_action_lines(companion, language="en-US"))
    for p in install_result.host_install.paths:
        lines.append(f"  File: {p}")
    lines.extend(
        [
            "",
            "Next:",
            f"  1. Open {host_name} in your project directory.",
            "  2. Sopify instructions are loaded automatically — start your task.",
        ]
    )
    return "\n".join(lines)


def _render_distribution_bootstrap_user_result(report: DistributionInstallReport) -> str:
    install_result = report.install_result
    assert isinstance(install_result, BootstrapOnlyResult)
    if install_result.target.language == "zh-CN":
        lines = [
            "Sopify 工作区已就绪。",
            "",
            "已初始化：",
            f"  宿主：{_host_display_name(install_result.target.host)}（{install_result.target.value}）",
            f"  语言：{_language_display_name(install_result.target.language, 'zh-CN')}",
            f"  工作区：{install_result.workspace_root}",
            f"  版本：{install_result.bundle_version or 'unknown'}",
            "",
            "下一步：",
            "  1. 在该目录打开 Copilot。",
            "  2. 直接开始你的任务，或在支持的宿主里输入：~go",
        ]
        return "\n".join(lines)

    lines = [
        "Sopify workspace ready.",
        "",
        "Initialized:",
        f"  Host: {_host_display_name(install_result.target.host)} ({install_result.target.value})",
        f"  Language: {_language_display_name(install_result.target.language, 'en-US')}",
        f"  Workspace: {install_result.workspace_root}",
        f"  Version: {install_result.bundle_version or 'unknown'}",
        "",
        "Next:",
        "  1. Open Copilot in that directory.",
        "  2. Start your task directly, or type `~go` in supported hosts.",
    ]
    return "\n".join(lines)


def _select_host_status(payload: dict[str, object], target: InstallTarget) -> dict[str, object]:
    for host in payload["hosts"]:
        if host["host_id"] == target.host:
            return host
    raise DistributionError(
        phase="verification",
        reason_code="TARGET_HOST_STATUS_MISSING",
        detail=f"Status payload did not include the selected host: {target.host}",
        next_step="Rerun the installer and verify the host registry declarations are still in sync.",
    )


def _select_host_checks(payload: dict[str, object], target: InstallTarget) -> tuple[dict[str, object], ...]:
    checks = []
    for check in payload["checks"]:
        if check.get("host_id") == target.host:
            checks.append(check)
    return tuple(checks)


def _render_workspace_line(install_result: InstallResult) -> str:
    if _is_user_plugin_install(install_result):
        return f"project unchanged; user Plugin rule installed at {_user_plugin_rule_path(install_result)}"
    if install_result.workspace_root is None:
        return "will bootstrap on first project trigger"
    return f"pre-warmed at {install_result.workspace_root}"


def _is_user_plugin_install(install_result: InstallResult) -> bool:
    try:
        return get_host_adapter(install_result.target.host).is_user_plugin_scope
    except ValueError:
        return False


def _user_plugin_rule_path(install_result: InstallResult) -> Path:
    for path in install_result.host_install.paths:
        if path.suffix == ".mdc":
            return path
    raise ValueError("User Plugin installation did not report its rule path")


def _workspace_bootstrap_action(install_result: InstallResult) -> str:
    if install_result.workspace_bootstrap is None:
        return "not requested"
    return (
        f"{install_result.workspace_bootstrap.action}"
        f" ({install_result.workspace_bootstrap.reason_code})"
    )


def _is_noop_install(install_result: InstallResult) -> bool:
    companion_noop = (
        install_result.evidentloop_install is None
        or (
            install_result.evidentloop_install.cli_action == "reused"
            and install_result.evidentloop_install.skill_action == "reused"
        )
    )
    return (
        install_result.host_install.action == "skipped"
        and install_result.payload_install.action == "skipped"
        and install_result.workspace_root is None
        and companion_noop
    )


def _first_smoke_line(smoke_output: str) -> str:
    first_line = smoke_output.splitlines()[0].strip() if smoke_output else ""
    return first_line or "(no smoke output)"


def _friendly_smoke_summary(smoke_output: str, language: str) -> str:
    first_line = _first_smoke_line(smoke_output)
    if first_line.startswith("Runtime smoke check passed"):
        return "运行时自检已通过。" if language == "zh-CN" else "Runtime smoke check passed."
    return first_line


def _companion_action_lines(
    result: EvidentLoopInstallResult,
    *,
    language: str,
) -> list[str]:
    if language == "zh-CN":
        lines = [
            f"  EvidentLoop CLI（{result.package_version}）：{_companion_action_label(result.cli_action, language)}",
            f"  EvidentLoop Skill：{_companion_action_label(result.skill_action, language)}",
            f"  EvidentLoop Skill 路径：{result.skill_path}",
        ]
        if _is_copilot_project_skill(result.skill_path):
            lines.append(
                "  Copilot 项目 Skill：如需云端使用，请审查后自行提交；"
                "Sopify 不会自动提交或更新。"
            )
        return lines
    lines = [
        f"  EvidentLoop CLI ({result.package_version}): {_companion_action_label(result.cli_action, language)}",
        f"  EvidentLoop Skill: {_companion_action_label(result.skill_action, language)}",
        f"  EvidentLoop Skill path: {result.skill_path}",
    ]
    if _is_copilot_project_skill(result.skill_path):
        lines.append(
            "  Copilot project Skill: review and commit it if your cloud workflow needs it; "
            "Sopify will not commit or update it."
        )
    return lines


def _is_copilot_project_skill(skill_path: Path) -> bool:
    return skill_path.parts[-4:-1] == (".github", "skills", "evidentloop")


def _companion_action_label(action: str, language: str) -> str:
    if action == "installed":
        return "已安装" if language == "zh-CN" else "installed"
    if action == "reused":
        return "已复用（健康检查通过）" if language == "zh-CN" else "reused (health check passed)"
    return _action_label(action, language)


def _host_display_name(host_id: str) -> str:
    return {
        "codex": "Codex",
        "claude": "Claude",
        "copilot": "Copilot",
        "qoder": "Qoder",
    }.get(host_id, host_id)


def _language_display_name(language: str, output_language: str) -> str:
    if output_language == "zh-CN":
        return {
            "zh-CN": "简体中文",
            "en-US": "English",
        }.get(language, language)
    return {
        "zh-CN": "Simplified Chinese",
        "en-US": "English",
    }.get(language, language)


def _action_label(action: str, language: str) -> str:
    if language == "zh-CN":
        return {
            "installed": "已安装",
            "updated": "已更新",
            "skipped": "已是最新",
            "reused": "已复用",
            "bootstrapped": "已初始化",
        }.get(action, action)
    return {
        "installed": "installed",
        "updated": "updated",
        "skipped": "already current",
        "reused": "reused",
        "bootstrapped": "initialized",
    }.get(action, action)
