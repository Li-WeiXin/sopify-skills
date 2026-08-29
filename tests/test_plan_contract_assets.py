from __future__ import annotations

from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from scripts._yaml_subset import load_yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILTIN_SKILL_IDS = ("analyze", "design", "develop", "kb", "templates")
SUPPORTED_HOSTS = ["codex", "claude", "qoder", "copilot", "cursor"]


class PlanContractAssetTests(unittest.TestCase):
    def test_bilingual_sources_share_current_plan_levels(self) -> None:
        for language in ("zh", "en"):
            with self.subTest(language=language):
                language_root = REPO_ROOT / "skills" / language
                header = (language_root / "header.md.template").read_text(
                    encoding="utf-8"
                )
                design_rules = (
                    language_root
                    / "skills"
                    / "sopify"
                    / "design"
                    / "references"
                    / "design-rules.md"
                ).read_text(encoding="utf-8")
                templates = (
                    language_root / "skills" / "sopify" / "templates" / "SKILL.md"
                ).read_text(encoding="utf-8")

                for content in (header, design_rules, templates):
                    self.assertIn("light", content)
                    self.assertIn("standard", content)
                    self.assertIn("architecture", content)
                self.assertNotIn("light/standard/full", header)
                self.assertNotIn("background.md + design.md + tasks.md", design_rules)
                self.assertNotIn("Full Level", templates)
                self.assertNotIn("Full 级别", templates)

    def test_design_assets_match_the_three_level_file_contract(self) -> None:
        for language in ("zh", "en"):
            with self.subTest(language=language):
                assets = (
                    REPO_ROOT
                    / "skills"
                    / language
                    / "skills"
                    / "sopify"
                    / "design"
                    / "assets"
                )
                self.assertTrue((assets / "plan-template.md").is_file())
                self.assertTrue((assets / "tasks-template.md").is_file())
                self.assertTrue((assets / "design-template.md").is_file())
                self.assertFalse((assets / "plan-light-template.md").exists())
                self.assertFalse((assets / "background-template.md").exists())

    def test_bilingual_selectors_return_architecture(self) -> None:
        for language in ("zh", "en"):
            with self.subTest(language=language):
                script = (
                    REPO_ROOT
                    / "skills"
                    / language
                    / "skills"
                    / "sopify"
                    / "design"
                    / "scripts"
                    / "select_plan_level.py"
                )
                result = subprocess.run(
                    [sys.executable, str(script), "--file-count", "2", "--new-system"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    json.loads(result.stdout)["plan_level"], "architecture"
                )

    def test_rendered_host_headers_keep_the_same_contract(self) -> None:
        render_script = REPO_ROOT / "scripts" / "render-host-skills.py"
        for language in ("zh", "en"):
            for host in ("codex", "claude", "qoder", "copilot"):
                with (
                    self.subTest(language=language, host=host),
                    tempfile.TemporaryDirectory() as temp_dir,
                ):
                    output = Path(temp_dir) / "host.md"
                    subprocess.run(
                        [
                            sys.executable,
                            str(render_script),
                            "--hosts-file",
                            str(REPO_ROOT / "skills" / "hosts.yaml"),
                            "--skills-root",
                            str(REPO_ROOT / "skills"),
                            "--lang",
                            language,
                            "--host",
                            host,
                            "--output",
                            str(output),
                        ],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    rendered = output.read_text(encoding="utf-8")
                    self.assertIn("plan_version", rendered)
                    self.assertIn("architecture", rendered)
                    self.assertNotIn("light/standard/full", rendered)

    def test_cursor_plugin_rule_uses_legal_frontmatter_and_thin_routing_contract(self) -> None:
        render_script = REPO_ROOT / "scripts" / "render-host-skills.py"
        for language in ("en", "zh"):
            with self.subTest(language=language), tempfile.TemporaryDirectory() as temp_dir:
                output = Path(temp_dir) / "sopify.mdc"
                subprocess.run(
                    [
                        sys.executable,
                        str(render_script),
                        "--hosts-file",
                        str(REPO_ROOT / "skills" / "hosts.yaml"),
                        "--skills-root",
                        str(REPO_ROOT / "skills"),
                        "--lang",
                        language,
                        "--host",
                        "cursor",
                        "--output",
                        str(output),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                rendered = output.read_text(encoding="utf-8")
                self.assertTrue(rendered.startswith("---\n"))
                self.assertIn("alwaysApply: true", rendered)
                self.assertIn("~/.cursor/skills/sopify/references/shared-writing-dna.md", rendered)
                self.assertIn("scripts/score_requirement.py", rendered)
                self.assertIn("auto_decide", rendered)
                self.assertIn("AskQuestion", rendered)
                self.assertIn("ask_question", rendered)
                self.assertIn("GetMcpTools", rendered)
                self.assertIn("Design/Develop", rendered)
                self.assertIn(
                    "free-form input" if language == "en" else "自由输入", rendered
                )
                self.assertNotRegex(rendered, r"(?m)^/.+/.cursor/skills/sopify")
                self.assertIn("analyze/SKILL.md", rendered)
                self.assertIn("consult_readonly", rendered)
                self.assertIn("IDE Entry" if language == "en" else "IDE 入口", rendered)
                self.assertIn(
                    "does not load a Plugin Rule by itself"
                    if language == "en"
                    else "不会自行加载 Plugin Rule",
                    rendered,
                )
                self.assertIn("~/.claude", rendered)
                self.assertIn("~/.codex", rendered)
                self.assertIn("state/active_plan.json", rendered)
                self.assertIn("sopify_writer", rendered)
                self.assertNotIn("{{skills_root}}", rendered)

    def test_develop_completion_requires_explicit_finalize(self) -> None:
        retired_phrases = {
            "zh": ("迁移方案至 history/", "方案完成后迁移到 `history/`", "## 步骤 4：方案迁移"),
            "en": ("Migrate plan to history/", "Move completed plans into `history/`", "## Step 4: Plan migration"),
        }
        for language in ("zh", "en"):
            with self.subTest(language=language):
                language_root = REPO_ROOT / "skills" / language
                sources = [
                    language_root / "header.md.template",
                    language_root / "skills" / "sopify" / "develop" / "SKILL.md",
                    language_root
                    / "skills"
                    / "sopify"
                    / "develop"
                    / "references"
                    / "develop-rules.md",
                ]
                contents: list[str] = []
                for source in sources:
                    content = source.read_text(encoding="utf-8")
                    contents.append(content)
                    self.assertIn("ready_to_archive", content)
                    self.assertIn("~go finalize", content)
                combined = "\n".join(contents)
                for phrase in retired_phrases[language]:
                    self.assertNotIn(phrase, combined)

    def test_kb_and_templates_defer_plan_lifecycle_to_protocol(self) -> None:
        for language in ("zh", "en"):
            with self.subTest(language=language):
                skill_root = REPO_ROOT / "skills" / language / "skills" / "sopify"
                kb = (skill_root / "kb/SKILL.md").read_text(encoding="utf-8")
                templates = (skill_root / "templates/SKILL.md").read_text(encoding="utf-8")
                for content in (kb, templates):
                    self.assertIn("Protocol", content)
                    self.assertNotIn("state/active_plan.json", content)
                    self.assertNotIn("plan/<plan_id>/plan.md", content)
                    self.assertNotIn("current_plan.path + current_plan.files", content)

    def test_builtin_host_support_matches_catalog_and_product_contract(self) -> None:
        catalog = json.loads(
            (REPO_ROOT / "skills" / "catalog" / "builtin_catalog.generated.json").read_text(
                encoding="utf-8"
            )
        )
        catalog_by_id = {item["id"]: item for item in catalog["skills"]}

        for skill_id in BUILTIN_SKILL_IDS:
            with self.subTest(skill_id=skill_id):
                manifest = load_yaml(
                    (
                        REPO_ROOT / "skills" / "catalog" / skill_id / "skill.yaml"
                    ).read_text(encoding="utf-8")
                )
                self.assertEqual(manifest["host_support"], SUPPORTED_HOSTS)
                self.assertEqual(catalog_by_id[skill_id]["host_support"], SUPPORTED_HOSTS)

        blueprint = (REPO_ROOT / ".sopify" / "blueprint" / "design.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("`host_support` 只声明官方适配器", blueprint)
        self.assertIn("`HostCapability`", blueprint)


if __name__ == "__main__":
    unittest.main()
