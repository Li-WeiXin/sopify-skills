"""Cursor IDE and Cursor Agent CLI host adapter."""

from __future__ import annotations

from installer.models import EntryMode, FeatureId, HostCapability, SupportTier

from .base import INSTRUCTION_SURFACE_PROJECT_RULES, HostAdapter, HostRegistration

CURSOR_ADAPTER = HostAdapter(
    host_name="cursor",
    destination_dirname=".cursor",
    header_filename="sopify.mdc",
    config_dir="~/.cursor",
    instruction_surface=INSTRUCTION_SURFACE_PROJECT_RULES,
    instruction_file_relpath=".cursor/rules/sopify.mdc",
    instruction_source_relpath="cursor-rules.mdc.template",
    default_language="en-US",
    skills_cli_agent=None,
    skill_install_dirname=".cursor/skills",
)

CURSOR_CAPABILITY = HostCapability(
    host_id="cursor",
    support_tier=SupportTier.BASELINE_SUPPORTED,
    install_enabled=True,
    declared_features=(
        FeatureId.PROMPT_INSTALL,
        FeatureId.PAYLOAD_INSTALL,
    ),
    verified_features=(
        FeatureId.PROMPT_INSTALL,
        FeatureId.PAYLOAD_INSTALL,
    ),
    declared_enhancements=(),
    entry_modes=(
        EntryMode.PROMPT_ONLY,
        EntryMode.HOOKS,
    ),
    doctor_checks=(
        "project_rule_present",
        "global_skill_tree_present",
        "payload_present",
        "cursor_hooks_present",
        "cursor_ide_behavior",
        "cursor_cli_behavior",
    ),
    smoke_targets=(),
)

CURSOR_HOST = HostRegistration(adapter=CURSOR_ADAPTER, capability=CURSOR_CAPABILITY)
