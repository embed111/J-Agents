from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


@dataclass
class CheckResult:
    check_id: str
    description: str
    passed: bool
    details: str


@dataclass
class ComplianceResult:
    workspace: str
    checked_at_utc: str
    passed: bool
    total_checks: int
    passed_checks: int
    failed_checks: int
    checks: list[CheckResult]


REQUIRED_FILES = (
    "agent.md",
    "agent_principles.yaml",
    "config.yaml",
    "docs/agent_framework.md",
    "docs/config_dashboard.md",
    "templates/framework.template.yaml",
)

REQUIRED_CONFIG_LINES = (
    "workspace_compliance_check: true",
    "generated_agent_compliance_check: true",
    "require_test_for_each_change: true",
    "require_open_closed_principle: true",
    "require_minimal_token_usage: true",
    "require_script_for_repeatable_flows: true",
    "enforce_workspace_compliance: true",
    "enforce_generated_agent_compliance: true",
    "workspace_compliance: true",
    "generated_agent_compliance: true",
)

REQUIRED_PRINCIPLES_LINES = (
    "- id: dual_scope_compliance",
    "title: 双域合规",
    "enforce_workspace_compliance: true",
    "enforce_generated_agent_compliance: true",
    "workspace_compliance: true",
    "generated_agent_compliance: true",
)


def _normalized_lines(content: str) -> set[str]:
    normalized: set[str] = set()
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if " #" in line:
            line = line.split(" #", 1)[0].rstrip()
        normalized.add(line)
    return normalized


def _build_required_line_checks(
    *,
    source_name: str,
    available_lines: set[str],
    required_lines: Iterable[str],
    check_prefix: str,
) -> list[CheckResult]:
    checks: list[CheckResult] = []
    for required_line in required_lines:
        passed = required_line in available_lines
        details = (
            f"{source_name} 包含 `{required_line}`"
            if passed
            else f"{source_name} 缺少 `{required_line}`"
        )
        checks.append(
            CheckResult(
                check_id=f"{check_prefix}:{required_line}",
                description=f"{source_name} 包含关键设置 `{required_line}`",
                passed=passed,
                details=details,
            )
        )
    return checks


def run_workspace_compliance_check(workspace: Path) -> ComplianceResult:
    workspace = workspace.resolve()
    checks: list[CheckResult] = []

    for rel_path in REQUIRED_FILES:
        file_path = workspace / rel_path
        exists = file_path.is_file()
        checks.append(
            CheckResult(
                check_id=f"required_file:{rel_path}",
                description=f"存在必需文件 `{rel_path}`",
                passed=exists,
                details=(
                    f"文件存在: {rel_path}" if exists else f"文件缺失: {rel_path}"
                ),
            )
        )

    config_path = workspace / "config.yaml"
    if config_path.is_file():
        config_lines = _normalized_lines(config_path.read_text(encoding="utf-8"))
        checks.extend(
            _build_required_line_checks(
                source_name="config.yaml",
                available_lines=config_lines,
                required_lines=REQUIRED_CONFIG_LINES,
                check_prefix="config_key",
            )
        )
    else:
        checks.append(
            CheckResult(
                check_id="config_read",
                description="读取 config.yaml",
                passed=False,
                details="无法读取 config.yaml，跳过配置项检查",
            )
        )

    principles_path = workspace / "agent_principles.yaml"
    if principles_path.is_file():
        principle_lines = _normalized_lines(
            principles_path.read_text(encoding="utf-8")
        )
        checks.extend(
            _build_required_line_checks(
                source_name="agent_principles.yaml",
                available_lines=principle_lines,
                required_lines=REQUIRED_PRINCIPLES_LINES,
                check_prefix="principle_key",
            )
        )
    else:
        checks.append(
            CheckResult(
                check_id="principles_read",
                description="读取 agent_principles.yaml",
                passed=False,
                details="无法读取 agent_principles.yaml，跳过原则项检查",
            )
        )

    total_checks = len(checks)
    passed_checks = sum(1 for check in checks if check.passed)
    failed_checks = total_checks - passed_checks
    passed = failed_checks == 0

    return ComplianceResult(
        workspace=str(workspace),
        checked_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        passed=passed,
        total_checks=total_checks,
        passed_checks=passed_checks,
        failed_checks=failed_checks,
        checks=checks,
    )


def write_markdown_report(result: ComplianceResult, report_path: Path) -> None:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        "# Workspace Compliance Report",
        "",
        f"- Workspace: `{result.workspace}`",
        f"- Checked At (UTC): `{result.checked_at_utc}`",
        f"- Status: `{status}`",
        f"- Summary: `{result.passed_checks}/{result.total_checks}` checks passed",
        "",
        "## Check Details",
    ]
    for check in result.checks:
        marker = "PASS" if check.passed else "FAIL"
        lines.append(
            f"- [{marker}] `{check.check_id}` - {check.description} - {check.details}"
        )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_json_report(result: ComplianceResult, report_path: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="检查工作区是否符合设计原则")
    parser.add_argument(
        "--workspace", default=".", help="待检查工作区路径（默认当前目录）"
    )
    parser.add_argument(
        "--report",
        default="reports/workspace_compliance.md",
        help="Markdown 报告输出路径",
    )
    parser.add_argument(
        "--json-report",
        default="",
        help="可选 JSON 报告路径",
    )
    args = parser.parse_args()

    workspace = Path(args.workspace)
    report_path = Path(args.report)
    json_report_path = Path(args.json_report) if args.json_report else None

    result = run_workspace_compliance_check(workspace)
    write_markdown_report(result, report_path)
    if json_report_path:
        write_json_report(result, json_report_path)

    status = "PASS" if result.passed else "FAIL"
    print(
        f"[{status}] workspace={result.workspace} "
        f"passed={result.passed_checks}/{result.total_checks} "
        f"report={report_path}"
    )
    return 0 if result.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
