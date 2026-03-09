import tempfile
import unittest
from pathlib import Path

from workspace_compliance_checker import (
    run_workspace_compliance_check,
    write_markdown_report,
)


REQUIRED_WORKSPACE_FILES = (
    "agent.md",
    "docs/agent_framework.md",
    "docs/config_dashboard.md",
    "templates/framework.template.yaml",
)


class WorkspaceComplianceCheckerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.workspace = Path(self._temp_dir.name)
        self._create_compliant_workspace(self.workspace)

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def _create_compliant_workspace(self, root: Path) -> None:
        for rel_path in REQUIRED_WORKSPACE_FILES:
            full_path = root / rel_path
            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_text("# placeholder\n", encoding="utf-8")

        (root / "config.yaml").write_text(
            "\n".join(
                [
                    "pipeline:",
                    "  workspace_compliance_check: true",
                    "  generated_agent_compliance_check: true",
                    "framework_requirements:",
                    "  change_testing:",
                    "    require_test_for_each_change: true",
                    "  oo_design:",
                    "    require_open_closed_principle: true",
                    "  token_efficiency:",
                    "    require_minimal_token_usage: true",
                    "  scriptization:",
                    "    require_script_for_repeatable_flows: true",
                    "  compliance_scope:",
                    "    enforce_workspace_compliance: true",
                    "    enforce_generated_agent_compliance: true",
                    "  quality_gate_rules:",
                    "    workspace_compliance: true",
                    "    generated_agent_compliance: true",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        (root / "agent_principles.yaml").write_text(
            "\n".join(
                [
                    "principles:",
                    "  - id: dual_scope_compliance",
                    "    title: 双域合规",
                    "compliance_scope:",
                    "  enforce_workspace_compliance: true",
                    "  enforce_generated_agent_compliance: true",
                    "quality_gates:",
                    "  workspace_compliance: true",
                    "  generated_agent_compliance: true",
                    "",
                ]
            ),
            encoding="utf-8",
        )

    def test_compliant_workspace_passes(self) -> None:
        result = run_workspace_compliance_check(self.workspace)
        self.assertTrue(result.passed)
        self.assertEqual(result.failed_checks, 0)

    def test_missing_required_file_fails(self) -> None:
        (self.workspace / "docs/config_dashboard.md").unlink()

        result = run_workspace_compliance_check(self.workspace)
        self.assertFalse(result.passed)
        self.assertGreater(result.failed_checks, 0)
        self.assertTrue(
            any(
                check.check_id == "required_file:docs/config_dashboard.md"
                and not check.passed
                for check in result.checks
            )
        )

    def test_missing_required_setting_fails(self) -> None:
        config_path = self.workspace / "config.yaml"
        content = config_path.read_text(encoding="utf-8")
        content = content.replace("workspace_compliance_check: true", "")
        config_path.write_text(content, encoding="utf-8")

        result = run_workspace_compliance_check(self.workspace)
        self.assertFalse(result.passed)
        self.assertTrue(
            any(
                check.check_id == "config_key:workspace_compliance_check: true"
                and not check.passed
                for check in result.checks
            )
        )

    def test_report_is_written(self) -> None:
        result = run_workspace_compliance_check(self.workspace)
        report_path = self.workspace / "reports" / "workspace_compliance.md"
        write_markdown_report(result, report_path)

        self.assertTrue(report_path.is_file())
        report_content = report_path.read_text(encoding="utf-8")
        self.assertIn("Workspace Compliance Report", report_content)


if __name__ == "__main__":
    unittest.main()
