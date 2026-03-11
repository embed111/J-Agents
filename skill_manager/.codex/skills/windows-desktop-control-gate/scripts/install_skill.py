from __future__ import annotations

import argparse
import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class CopyResult:
    source: str
    target: str
    action: str
    backup: str | None = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install Windows desktop control gate files into a target workspace."
    )
    parser.add_argument("--workspace-root", required=True, help="Target workspace root.")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite changed files without creating a backup copy.",
    )
    return parser.parse_args()


def copy_with_backup(source: Path, target: Path, *, force: bool) -> CopyResult:
    target.parent.mkdir(parents=True, exist_ok=True)

    if not target.exists():
        shutil.copy2(source, target)
        return CopyResult(str(source), str(target), "created")

    source_bytes = source.read_bytes()
    target_bytes = target.read_bytes()
    if source_bytes == target_bytes:
        return CopyResult(str(source), str(target), "unchanged")

    backup_path = None
    if not force:
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = target.with_name(f"{target.name}.bak.{timestamp}")
        shutil.copy2(target, backup_path)

    shutil.copy2(source, target)
    return CopyResult(
        str(source),
        str(target),
        "updated" if backup_path else "overwritten",
        str(backup_path) if backup_path else None,
    )


def main() -> int:
    args = parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    skill_root = Path(__file__).resolve().parents[1]
    script_root = skill_root / "scripts"

    mappings = [
        (script_root / "control_ui.py", workspace_root / "scripts" / "control_ui.py"),
        (
            script_root / "lib" / "interactive-control.ps1",
            workspace_root / "scripts" / "lib" / "interactive-control.ps1",
        ),
        (
            script_root / "lib" / "window-activation.ps1",
            workspace_root / "scripts" / "lib" / "window-activation.ps1",
        ),
        (
            skill_root / ".test" / "test-control-request.ps1",
            workspace_root / ".test" / "test-control-request.ps1",
        ),
    ]

    created_dirs = []
    for relative in (
        workspace_root / "scripts",
        workspace_root / "scripts" / "lib",
        workspace_root / ".test",
        workspace_root / ".test" / "runs",
        workspace_root / "workspace_state",
        workspace_root / "workspace_state" / "control",
    ):
        if not relative.exists():
            relative.mkdir(parents=True, exist_ok=True)
            created_dirs.append(str(relative))

    results = [copy_with_backup(source, target, force=args.force) for source, target in mappings]

    summary = {
        "workspaceRoot": str(workspace_root),
        "skillRoot": str(skill_root),
        "createdDirectories": created_dirs,
        "files": [result.__dict__ for result in results],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
