from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


WORKSPACE_FILES_TO_COPY = (
    "agent.md",
    "agent_principles.yaml",
    "config.yaml",
    "README.md",
    "workspace_compliance_checker.py",
    "docs/agent_framework.md",
    "docs/config_dashboard.md",
    "templates/framework.template.yaml",
)


@dataclass
class WorkspaceGenerationResult:
    source_workspace: str
    target_workspace: str
    generated_at_utc: str
    copied_files: list[str]
    created_files: list[str]


def _default_source_workspace() -> Path:
    return Path(__file__).resolve().parent


def _is_non_empty_directory(path: Path) -> bool:
    return path.is_dir() and any(path.iterdir())


def _validate_target(target_workspace: Path, overwrite: bool) -> None:
    if target_workspace.exists() and not target_workspace.is_dir():
        raise ValueError(f"目标路径不是目录: {target_workspace}")
    if _is_non_empty_directory(target_workspace) and not overwrite:
        raise FileExistsError(
            f"目标目录非空，若要覆盖请设置 overwrite=True: {target_workspace}"
        )


def _safe_copy(source_file: Path, target_file: Path) -> None:
    target_file.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_file, target_file)


def generate_agent_workspace(
    target_workspace: Path,
    *,
    source_workspace: Path | None = None,
    overwrite: bool = False,
) -> WorkspaceGenerationResult:
    source_root = (source_workspace or _default_source_workspace()).resolve()
    target_root = target_workspace.resolve()

    _validate_target(target_root, overwrite=overwrite)
    target_root.mkdir(parents=True, exist_ok=True)

    copied_files: list[str] = []
    for rel_path in WORKSPACE_FILES_TO_COPY:
        source_file = source_root / rel_path
        if not source_file.is_file():
            raise FileNotFoundError(f"源文件不存在: {source_file}")
        target_file = target_root / rel_path
        _safe_copy(source_file, target_file)
        copied_files.append(rel_path)

    created_files: list[str] = []
    reports_keep = target_root / "reports" / ".gitkeep"
    reports_keep.parent.mkdir(parents=True, exist_ok=True)
    if not reports_keep.exists():
        reports_keep.write_text("\n", encoding="utf-8")
        created_files.append("reports/.gitkeep")

    unit_test_dir = target_root / ".unit_test"
    unit_test_dir.mkdir(parents=True, exist_ok=True)

    return WorkspaceGenerationResult(
        source_workspace=str(source_root),
        target_workspace=str(target_root),
        generated_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        copied_files=copied_files,
        created_files=created_files,
    )


def write_generation_report(
    result: WorkspaceGenerationResult, report_path: Path
) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(asdict(result), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="生成一个新的 Agent 工作区")
    parser.add_argument("--target", required=True, help="目标工作区目录")
    parser.add_argument(
        "--source",
        default="",
        help="源工作区目录（默认当前脚本所在目录）",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="允许覆盖非空目标目录",
    )
    parser.add_argument(
        "--report",
        default="",
        help="可选 JSON 报告输出路径",
    )
    args = parser.parse_args()

    source_workspace = Path(args.source) if args.source else None
    result = generate_agent_workspace(
        Path(args.target),
        source_workspace=source_workspace,
        overwrite=args.overwrite,
    )

    if args.report:
        write_generation_report(result, Path(args.report))

    print(
        f"[PASS] generated_workspace={result.target_workspace} "
        f"files={len(result.copied_files)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
