#!/usr/bin/env python3
"""Render host-specific headers from header.md.template + hosts.yaml.

Local maintainer helper — NOT part of release / CI / pre-commit pipeline.
Used by sync-skills.sh to generate gitignored Codex/Skills/ and Claude/Skills/
local cache directories.

Usage:
    python3 scripts/render-host-skills.py --hosts-file skills/hosts.yaml --lang en --host claude
    python3 scripts/render-host-skills.py --hosts-file skills/hosts.yaml --lang en --host claude --output /tmp/CLAUDE.md
    python3 scripts/render-host-skills.py --hosts-file skills/hosts.yaml --verify-all

The script reads header.md.template, substitutes {{config_dir}} with the
host-specific value from hosts.yaml, and writes (or prints) the rendered header.

--verify-all renders all host:lang header combos and prints their sha256.
Note: this only covers header rendering, not full install-product hashes.
Full install-product verification is in tests/test_golden_snapshots.py.

No external dependencies — stdlib only.
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path


def _parse_hosts_yaml(text: str) -> dict:
    """Minimal parser for skills/hosts.yaml.

    Supports the two-level structure used in this repo:
        hosts:
          host_id:
            key: value

    Values: bare strings, "quoted strings", null, true/false.
    Does NOT support arrays, anchors, flow mappings, or multi-line values.
    """
    result: dict[str, dict[str, object]] = {}
    current_host: str | None = None
    in_hosts = False

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(raw_line) - len(raw_line.lstrip())

        if stripped == "hosts:":
            in_hosts = True
            continue

        if not in_hosts:
            continue

        # Top-level key resets hosts section
        if indent == 0:
            in_hosts = False
            continue

        # Host id line (2-space indent): "  host_id:"
        if indent == 2 and stripped.endswith(":"):
            current_host = stripped[:-1].strip()
            result[current_host] = {}
            continue

        # Property line (4+ space indent): "    key: value"
        if indent >= 4 and current_host is not None and ":" in stripped:
            key, _, raw_value = stripped.partition(":")
            key = key.strip()
            raw_value = raw_value.strip()

            # Parse value
            if raw_value == "null":
                value: object = None
            elif raw_value == "true":
                value = True
            elif raw_value == "false":
                value = False
            elif raw_value.startswith('"') and raw_value.endswith('"'):
                value = raw_value[1:-1]
            else:
                value = raw_value

            result[current_host][key] = value

    return result


def _load_hosts(hosts_file: Path) -> dict:
    """Load hosts.yaml and return {"hosts": {...}} structure."""
    text = hosts_file.read_text(encoding="utf-8")
    return {"hosts": _parse_hosts_yaml(text)}


def render_header(template_path: Path, host_vars: dict) -> str:
    """Render header.md.template with host-specific variables."""
    content = template_path.read_text(encoding="utf-8")
    config_dir = host_vars.get("config_dir")
    if config_dir is not None:
        content = content.replace("{{config_dir}}", config_dir)
    else:
        content = content.replace("{{config_dir}}", "")
    skills_root = f"{config_dir}/skills/sopify" if config_dir else ""
    content = content.replace("{{skills_root}}", skills_root)
    # Warn on unresolved variables
    unresolved = re.findall(r"\{\{(\w+)\}\}", content)
    if unresolved:
        print(
            f"WARNING: unresolved template variables: {unresolved}",
            file=sys.stderr,
        )
    return content


def main() -> None:
    parser = argparse.ArgumentParser(description="Render host-specific headers")
    parser.add_argument(
        "--hosts-file",
        type=Path,
        default=Path("skills/hosts.yaml"),
        help="Path to hosts.yaml",
    )
    parser.add_argument("--lang", help="Language code (en or zh)")
    parser.add_argument("--host", help="Host id (claude, codex, qoder, copilot)")
    parser.add_argument("--output", type=Path, help="Output file path (default: stdout)")
    parser.add_argument(
        "--verify-all",
        action="store_true",
        help="Render all combos and print sha256 hashes",
    )
    parser.add_argument(
        "--skills-root",
        type=Path,
        default=Path("skills"),
        help="Root of skills directory",
    )
    args = parser.parse_args()

    hosts_data = _load_hosts(args.hosts_file)
    hosts = hosts_data.get("hosts", {})

    if args.verify_all:
        for host_id, host_vars in sorted(hosts.items()):
            for lang in ("en", "zh"):
                template_path = _template_path(args.skills_root, lang, host_vars)
                if not template_path.exists():
                    print(f"  SKIP {host_id}:{lang} — template not found")
                    continue
                rendered = render_header(template_path, host_vars)
                h = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
                print(f"  {host_id}:{lang} → sha256:{h[:16]}... ({len(rendered)} bytes)")
        return

    if not args.lang or not args.host:
        parser.error("--lang and --host are required (or use --verify-all)")

    if args.host not in hosts:
        parser.error(f"Unknown host: {args.host}. Available: {list(hosts.keys())}")

    template_path = _template_path(args.skills_root, args.lang, hosts[args.host])
    if not template_path.exists():
        parser.error(f"Template not found: {template_path}")

    rendered = render_header(template_path, hosts[args.host])

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Rendered {args.host}:{args.lang} → {args.output}")
    else:
        sys.stdout.write(rendered)


def _template_path(skills_root: Path, language: str, host_vars: dict[str, object]) -> Path:
    relpath = str(host_vars.get("instruction_source_relpath") or "header.md.template")
    return skills_root / language / relpath


if __name__ == "__main__":
    main()
