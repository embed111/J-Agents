import tempfile
import unittest
from pathlib import Path

from agent_workspace_generator import generate_agent_workspace
from workspace_compliance_checker import run_workspace_compliance_check


class AgentWorkspaceGeneratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp_dir = tempfile.TemporaryDirectory()
        self.temp_root = Path(self._temp_dir.name)
        self.target_workspace = self.temp_root / "generated_workspace"

    def tearDown(self) -> None:
        self._temp_dir.cleanup()

    def test_generate_workspace_creates_expected_files(self) -> None:
        generate_agent_workspace(self.target_workspace)

        expected_files = (
            "agent.md",
            "agent_principles.yaml",
            "config.yaml",
            "README.md",
            "workspace_compliance_checker.py",
            "docs/agent_framework.md",
            "docs/config_dashboard.md",
            "templates/framework.template.yaml",
            "reports/.gitkeep",
        )
        for rel_path in expected_files:
            self.assertTrue(
                (self.target_workspace / rel_path).is_file(),
                msg=f"缺少生成文件: {rel_path}",
            )

    def test_generate_workspace_passes_compliance(self) -> None:
        generate_agent_workspace(self.target_workspace)
        result = run_workspace_compliance_check(self.target_workspace)

        self.assertTrue(result.passed)
        self.assertEqual(result.failed_checks, 0)

    def test_non_empty_target_raises_without_overwrite(self) -> None:
        self.target_workspace.mkdir(parents=True, exist_ok=True)
        (self.target_workspace / "custom.txt").write_text("x", encoding="utf-8")

        with self.assertRaises(FileExistsError):
            generate_agent_workspace(self.target_workspace, overwrite=False)

    def test_overwrite_true_allows_generation(self) -> None:
        self.target_workspace.mkdir(parents=True, exist_ok=True)
        (self.target_workspace / "custom.txt").write_text("x", encoding="utf-8")

        generate_agent_workspace(self.target_workspace, overwrite=True)
        self.assertTrue((self.target_workspace / "agent.md").is_file())


if __name__ == "__main__":
    unittest.main()
