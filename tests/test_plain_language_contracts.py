from __future__ import annotations

import json
from pathlib import Path
import tempfile

import pytest

from installer.hosts.base import HEADER_TEMPLATE_NAME, install_host_assets, render_single_file
from installer.hosts.copilot import COPILOT_ADAPTER
from installer.hosts.qoder import QODER_ADAPTER
from installer.validate import validate_host_install


REPO_ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = REPO_ROOT / "tests" / "behavior-scenarios" / "plain-language-output-v1.json"


def _jpeg_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data.startswith(b"\xff\xd8")
    offset = 2
    start_of_frame = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}

    while offset < len(data):
        assert data[offset] == 0xFF
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        marker = data[offset]
        offset += 1
        if marker in start_of_frame:
            height = int.from_bytes(data[offset + 3 : offset + 5], "big")
            width = int.from_bytes(data[offset + 5 : offset + 7], "big")
            return width, height
        if marker in {0xD9, 0xDA}:
            break
        segment_length = int.from_bytes(data[offset : offset + 2], "big")
        offset += segment_length

    raise AssertionError(f"JPEG dimensions not found: {path}")


def _skill_file(language: str, relative: str) -> str:
    return (
        REPO_ROOT / "skills" / language / "skills" / "sopify" / relative
    ).read_text(encoding="utf-8")


def test_bilingual_skill_trees_have_the_same_files() -> None:
    roots = [REPO_ROOT / "skills" / language / "skills" / "sopify" for language in ("zh", "en")]
    trees = [
        {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()}
        for root in roots
    ]
    assert trees[0] == trees[1]


def test_behavior_scenarios_are_versioned_and_bounded() -> None:
    payload = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert len(payload["scenarios"]) == 6
    assert len(payload["comparison"]) == 6
    assert len(payload["source_revision"]) == 40

    required = {
        "scenario_id",
        "language",
        "surface",
        "input",
        "evidence",
        "expected_behavior",
        "allowed_write_set",
    }
    assert all(required <= scenario.keys() for scenario in payload["scenarios"])
    readonly = [
        scenario
        for scenario in payload["scenarios"]
        if scenario["surface"] == "host/consult_readonly"
    ]
    assert {scenario["language"] for scenario in readonly} == {"zh-CN", "en-US"}
    assert all(scenario["allowed_write_set"] == [] for scenario in readonly)
    for language, locale in (("zh", "zh-CN"), ("en", "en-US")):
        source_root = REPO_ROOT / "skills" / language
        rendered = render_single_file(
            source_root / HEADER_TEMPLATE_NAME,
            source_root / "skills" / "sopify",
            COPILOT_ADAPTER,
        )
        current = {
            "characters": len(rendered),
            "bytes": len(rendered.encode("utf-8")),
            "lines": len(rendered.splitlines()),
        }
        baseline = payload["copilot_baseline"][locale]
        observed_after = payload["copilot_after"][locale]
        assert current.keys() == baseline.keys() == observed_after.keys()
        assert all(current[metric] < baseline[metric] for metric in current)
        assert all(observed_after[metric] < baseline[metric] for metric in observed_after)


@pytest.mark.parametrize("language", ["zh", "en"])
def test_design_owns_plan_templates_and_uses_readiness(language: str) -> None:
    design_rules = _skill_file(language, "design/references/design-rules.md")
    plan_template = _skill_file(language, "design/assets/plan-template.md")
    summary = _skill_file(language, "design/assets/output-summary.md")
    templates = _skill_file(language, "templates/SKILL.md")

    assert "Ready" in design_rules and "Needs decision" in design_rules
    assert "`strict`" in design_rules and "`adaptive`" in design_rules
    assert "Ready" in plan_template and "Needs decision" in plan_template
    assert "Ready" in summary and "Needs decision" in summary
    assert "Solution quality" not in plan_template
    assert "方案质量" not in plan_template
    assert "## A2" not in templates
    assert "Protocol" in templates
    assert "plan/<plan_id>/plan.md" not in templates


@pytest.mark.parametrize("language", ["zh", "en"])
def test_phase_owners_keep_their_boundaries(language: str) -> None:
    analyze = _skill_file(language, "analyze/references/analyze-rules.md")
    analyze_output = _skill_file(language, "analyze/assets/success-output.md")
    develop = _skill_file(language, "develop/references/develop-rules.md")
    kb = _skill_file(language, "kb/SKILL.md")
    output_contract = _skill_file(language, "references/output-contract.md")

    assert "consult_readonly" in analyze
    assert "`strict`" in analyze and "`adaptive`" in analyze
    assert "证据来源不限" in analyze or "not an exhaustive source list" in analyze
    assert "Deliverable:" in analyze_output or "交付物:" in analyze_output
    assert "Assumptions used" in analyze_output or "本次采用的假设" in analyze_output
    assert "Type:" not in analyze_output and "类型:" not in analyze_output
    assert "explicit assumptions when used" in output_contract or "实际采用的假设" in output_contract
    assert "common root cause" in develop or "共同根因" in develop
    assert "knowledge_sync" in kb
    assert "sopify_writer" in kb


@pytest.mark.parametrize("language", ["zh", "en"])
def test_copilot_single_file_has_no_script_source_or_dangling_path(language: str) -> None:
    source_root = REPO_ROOT / "skills" / language
    rendered = render_single_file(
        source_root / HEADER_TEMPLATE_NAME,
        source_root / "skills" / "sopify",
        COPILOT_ADAPTER,
    )

    assert "<!-- inlined: analyze/scripts/" not in rendered
    assert "<!-- inlined: design/scripts/" not in rendered
    assert "scripts/score_requirement.py" not in rendered
    assert "scripts/select_plan_level.py" not in rendered
    assert "references/assets/scripts" not in rendered
    assert "import argparse" not in rendered
    assert "Ready" in rendered and "Needs decision" in rendered


def test_qoder_real_install_consumes_header_and_skill_tree() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        home_root = Path(temp_dir)
        install_host_assets(
            QODER_ADAPTER,
            repo_root=REPO_ROOT,
            home_root=home_root,
            language_directory="CN",
        )
        validate_host_install(QODER_ADAPTER, home_root=home_root)

        installed = home_root / ".qoder"
        header = (installed / "AGENTS.md").read_text(encoding="utf-8")
        analyze = (
            installed / "skills" / "sopify" / "analyze" / "references" / "analyze-rules.md"
        ).read_text(encoding="utf-8")
        assert "直接路由单个 Skill" in header
        assert "先读证据" in analyze


@pytest.mark.parametrize(
    "page,image_name,canonical",
    [
        ("index.html", "sopify-og-en.jpg", "https://evidentloop.github.io/sopify/"),
        (
            "zh-CN.html",
            "sopify-og-zh-CN.jpg",
            "https://evidentloop.github.io/sopify/zh-CN.html",
        ),
    ],
)
def test_static_pages_keep_release_metadata(
    page: str, image_name: str, canonical: str
) -> None:
    html = (REPO_ROOT / page).read_text(encoding="utf-8")
    assert f'<link rel="canonical" href="{canonical}"' in html
    assert 'hreflang="en"' in html and 'hreflang="zh-CN"' in html
    assert f"/assets/{image_name}" in html
    assert 'property="og:image:width" content="1200"' in html
    assert 'property="og:image:height" content="630"' in html
    assert (REPO_ROOT / "assets" / image_name).is_file()
    assert _jpeg_dimensions(REPO_ROOT / "assets" / image_name) == (1200, 630)
    assert (REPO_ROOT / ".nojekyll").is_file()


@pytest.mark.parametrize(
    "page,host_label,install_copy",
    [
        (
            "index.html",
            "Cursor · baseline",
            "Codex, Claude, Qoder, Copilot, and Cursor targets",
        ),
        (
            "zh-CN.html",
            "Cursor · 基线支持",
            "支持 Codex、Claude、Qoder、Copilot 与 Cursor",
        ),
    ],
)
def test_static_pages_include_cursor_host(
    page: str, host_label: str, install_copy: str
) -> None:
    html = (REPO_ROOT / page).read_text(encoding="utf-8")
    assert host_label in html
    assert install_copy in html


@pytest.mark.parametrize(
    "page,readme,asset,label,required",
    [
        (
            "index.html",
            "README.md",
            "sopify-product-form-release-en.svg",
            "Product form",
            (">HOST</text>", ">SKILL</text>", ">ASSETS</text>", ">HANDOFF</text>", ">ARCHIVE</text>", "RESUME WHEN ASKED", "Read evidence · score · ask if blocked", "Knowledge policy · document structure", ">FINALIZES</text>"),
        ),
        (
            "zh-CN.html",
            "README.zh-CN.md",
            "sopify-product-form-release.svg",
            "产品形态",
            (">HOST</text>", ">SKILL</text>", ">ASSETS</text>", ">HANDOFF</text>", ">ARCHIVE</text>", "明确要求后再接续", "先读证据 · 评分 · 必要时追问", "知识政策 · 文档结构", ">FINALIZES</text>"),
        ),
    ],
)
def test_product_form_is_clear_without_duplicating_the_homepage(
    page: str,
    readme: str,
    asset: str,
    label: str,
    required: tuple[str, ...],
) -> None:
    html = (REPO_ROOT / page).read_text(encoding="utf-8")
    readme_text = (REPO_ROOT / readme).read_text(encoding="utf-8")
    svg = (REPO_ROOT / "assets" / asset).read_text(encoding="utf-8")

    assert label in html
    assert "./assets/sopify-architecture.svg" in html
    assert "sopify-product-form-release" not in html
    assert f"./assets/{asset}" in readme_text
    assert all(term in svg for term in required)
    lowered_svg = svg.lower()
    assert "any host resumes" not in lowered_svg
    assert "always auditable" not in lowered_svg
    assert "community philosophy" not in lowered_svg
    assert "任一宿主打开即消费" not in svg
    assert "社区哲学" not in svg
    assert "永久可审计" not in svg
    assert ">RESUMES</text>" not in svg


def test_architecture_copy_matches_protocol_boundaries() -> None:
    svg = (REPO_ROOT / "assets" / "sopify-architecture.svg").read_text(
        encoding="utf-8"
    )

    entry_steps = (
        "active_plan.json → locate plan",
        "plan.md → semantic entry point",
        "current_handoff.json → resume hint",
        "receipts/ → latest evidence",
    )
    assert all(step in svg for step in entry_steps)
    assert [svg.index(step) for step in entry_steps] == sorted(
        svg.index(step) for step in entry_steps
    )
    assert "MANAGED PLAN 4-STEP ENTRY" in svg
    assert "three phase skills + explicit finalize action" in svg
    assert "~go finalize (action)" in svg
    assert "Validated protocol writes" in svg
    assert "handoff pointers stay local" in svg
    assert "Any Host" not in svg
    assert "any host" not in svg
    assert "rules live in .sopify" not in svg
    assert "Sole write path" not in svg
