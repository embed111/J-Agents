#!/usr/bin/env python3
"""
Create/install/register Codex skills in the current workspace only.
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

MAX_SKILL_NAME_LENGTH = 64
AVAILABLE_HEADER = "### Available skills"

SKILL_TEMPLATE = """---
name: {skill_name}
description: {description}
---

# {title}

## Overview

[TODO: Explain what this skill enables.]

## Workflow

1. [TODO: Add the main workflow steps.]
2. [TODO: Link scripts/references only when needed.]
"""


def normalize_skill_name(raw_name: str) -> str:
    normalized = raw_name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = normalized.strip("-")
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized


def validate_skill_name(name: str) -> None:
    if not name:
        raise ValueError("Skill name must include at least one letter or digit.")
    if len(name) > MAX_SKILL_NAME_LENGTH:
        raise ValueError(
            f"Skill name '{name}' is too long ({len(name)} characters). "
            f"Maximum is {MAX_SKILL_NAME_LENGTH}."
        )
    if not re.match(r"^[a-z0-9-]+$", name):
        raise ValueError("Skill name must use lowercase letters, digits, and hyphens.")


def title_case(name: str) -> str:
    return " ".join(word.capitalize() for word in name.split("-") if word)


def generate_short_description(display_name: str) -> str:
    description = f"Help with {display_name} tasks"
    if len(description) < 25:
        description = f"Help with {display_name} workflows"
    if len(description) > 64:
        description = f"{display_name} helper"
    if len(description) > 64:
        description = description[:64].rstrip()
    if len(description) < 25:
        description = "Help with local skill workflows"
    return description


def read_text_with_fallback(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030", "cp936"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    # Final fallback preserves bytes and allows parsing markers.
    return path.read_text(encoding="utf-8", errors="replace")


def write_openai_yaml(skill_dir: Path, skill_name: str) -> None:
    display_name = title_case(skill_name)
    short_description = generate_short_description(display_name)
    agents_dir = skill_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    content = (
        "interface:\n"
        f'  display_name: "{display_name}"\n'
        f'  short_description: "{short_description}"\n'
    )
    (agents_dir / "openai.yaml").write_text(content, encoding="utf-8")


def parse_skill_frontmatter(skill_md: Path) -> tuple[str | None, str | None]:
    content = read_text_with_fallback(skill_md)
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return None, None
    frontmatter = match.group(1).splitlines()
    name = None
    description = None
    for line in frontmatter:
        stripped = line.strip()
        if stripped.startswith("name:"):
            name = stripped.split(":", 1)[1].strip().strip('"').strip("'")
        elif stripped.startswith("description:"):
            description = stripped.split(":", 1)[1].strip().strip('"').strip("'")
    return name, description


def ensure_available_skills_entry(
    workspace_root: Path,
    skill_name: str,
    skill_md_path: Path,
    description: str | None,
    dry_run: bool,
) -> bool:
    agents_path = workspace_root / "AGENTS.md"
    if not agents_path.exists():
        print(f"[WARN] AGENTS.md not found at {agents_path}; registration skipped.")
        return False

    text = read_text_with_fallback(agents_path)
    if str(skill_md_path.as_posix()) in text:
        print(f"[OK] Skill path already registered in {agents_path}.")
        return True

    lines = text.splitlines()
    header_index = None
    for idx, line in enumerate(lines):
        if line.strip() == AVAILABLE_HEADER:
            header_index = idx
            break

    if header_index is None:
        print(
            f"[WARN] '{AVAILABLE_HEADER}' not found in {agents_path}; "
            "registration skipped."
        )
        return False

    insert_at = header_index + 1
    while insert_at < len(lines) and not lines[insert_at].strip():
        insert_at += 1
    while insert_at < len(lines) and lines[insert_at].lstrip().startswith("- "):
        insert_at += 1

    use_description = (
        description
        or "Local workspace skill installed without writing to global Codex home."
    )
    entry = (
        f"- {skill_name}: {use_description} "
        f"(file: {skill_md_path.as_posix()})"
    )
    lines.insert(insert_at, entry)

    if dry_run:
        print(f"[DRY-RUN] Would append Available skills entry to {agents_path}.")
        print(entry)
        return True

    agents_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] Registered skill in {agents_path}.")
    return True


def create_skill(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).resolve()
    normalized_name = normalize_skill_name(args.name)
    try:
        validate_skill_name(normalized_name)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    if normalized_name != args.name:
        print(f"[INFO] Normalized name: {args.name} -> {normalized_name}")

    skill_root = workspace_root / args.dest_root / normalized_name
    skill_md_path = skill_root / "SKILL.md"
    description = args.description.strip()
    skill_content = SKILL_TEMPLATE.format(
        skill_name=normalized_name,
        description=description,
        title=title_case(normalized_name),
    )

    if skill_root.exists():
        print(f"[ERROR] Destination already exists: {skill_root}")
        return 1

    if args.dry_run:
        print(f"[DRY-RUN] Would create {skill_root}")
        print(f"[DRY-RUN] Would write {skill_md_path}")
        if args.register:
            ensure_available_skills_entry(
                workspace_root,
                normalized_name,
                skill_md_path,
                description,
                dry_run=True,
            )
        return 0

    skill_root.mkdir(parents=True, exist_ok=False)
    skill_md_path.write_text(skill_content, encoding="utf-8")
    write_openai_yaml(skill_root, normalized_name)

    for folder in args.resources:
        (skill_root / folder).mkdir(exist_ok=True)

    print(f"[OK] Created local skill at {skill_root}")
    if args.register:
        ensure_available_skills_entry(
            workspace_root,
            normalized_name,
            skill_md_path,
            description,
            dry_run=False,
        )
    return 0


def install_skill(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).resolve()
    source = Path(args.source).resolve()
    if not source.exists() or not source.is_dir():
        print(f"[ERROR] Source not found: {source}")
        return 1
    if not (source / "SKILL.md").exists():
        print(f"[ERROR] SKILL.md not found in source: {source}")
        return 1

    source_name, source_description = parse_skill_frontmatter(source / "SKILL.md")
    requested_name = args.name or source_name or source.name
    normalized_name = normalize_skill_name(requested_name)
    try:
        validate_skill_name(normalized_name)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    dest = workspace_root / args.dest_root / normalized_name
    if dest.exists():
        print(f"[ERROR] Destination already exists: {dest}")
        return 1

    if args.dry_run:
        print(f"[DRY-RUN] Would copy {source} -> {dest}")
        if args.register:
            ensure_available_skills_entry(
                workspace_root,
                normalized_name,
                dest / "SKILL.md",
                source_description,
                dry_run=True,
            )
        return 0

    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)
    print(f"[OK] Installed local skill at {dest}")

    if args.register:
        ensure_available_skills_entry(
            workspace_root,
            normalized_name,
            dest / "SKILL.md",
            source_description,
            dry_run=False,
        )
    return 0


def register_skill(args: argparse.Namespace) -> int:
    workspace_root = Path(args.workspace_root).resolve()
    skill_dir = Path(args.skill_dir).resolve()
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        print(f"[ERROR] SKILL.md not found: {skill_md}")
        return 1

    source_name, source_description = parse_skill_frontmatter(skill_md)
    skill_name = normalize_skill_name(args.name or source_name or skill_dir.name)
    try:
        validate_skill_name(skill_name)
    except ValueError as exc:
        print(f"[ERROR] {exc}")
        return 1

    description = args.description or source_description
    ensure_available_skills_entry(
        workspace_root,
        skill_name,
        skill_md,
        description,
        dry_run=args.dry_run,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Manage local workspace skills without global writes."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Create a new local skill")
    create_parser.add_argument("--name", required=True, help="Skill name")
    create_parser.add_argument(
        "--description",
        default=(
            "Local workspace skill. Update this description to explain behavior and "
            "trigger conditions."
        ),
        help="Frontmatter description for the new skill",
    )
    create_parser.add_argument(
        "--workspace-root",
        default=".",
        help="Workspace root path (default: current directory)",
    )
    create_parser.add_argument(
        "--dest-root",
        default=".codex/skills",
        help="Skill destination root under workspace (default: .codex/skills)",
    )
    create_parser.add_argument(
        "--resources",
        nargs="*",
        default=[],
        choices=["scripts", "references", "assets"],
        help="Optional resource folders to create",
    )
    create_parser.add_argument(
        "--no-register",
        action="store_true",
        help="Skip registration in AGENTS.md",
    )
    create_parser.add_argument("--dry-run", action="store_true")

    install_parser = subparsers.add_parser(
        "install", help="Install an existing skill directory locally"
    )
    install_parser.add_argument("--source", required=True, help="Source skill directory")
    install_parser.add_argument("--name", help="Destination skill name override")
    install_parser.add_argument(
        "--workspace-root",
        default=".",
        help="Workspace root path (default: current directory)",
    )
    install_parser.add_argument(
        "--dest-root",
        default=".codex/skills",
        help="Skill destination root under workspace (default: .codex/skills)",
    )
    install_parser.add_argument(
        "--no-register",
        action="store_true",
        help="Skip registration in AGENTS.md",
    )
    install_parser.add_argument("--dry-run", action="store_true")

    register_parser = subparsers.add_parser(
        "register", help="Register an existing local skill in AGENTS.md"
    )
    register_parser.add_argument("--skill-dir", required=True, help="Local skill directory")
    register_parser.add_argument("--name", help="Skill name override")
    register_parser.add_argument("--description", help="Description override")
    register_parser.add_argument(
        "--workspace-root",
        default=".",
        help="Workspace root path (default: current directory)",
    )
    register_parser.add_argument("--dry-run", action="store_true")

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "create":
        args.register = not args.no_register
        return create_skill(args)
    if args.command == "install":
        args.register = not args.no_register
        return install_skill(args)
    if args.command == "register":
        return register_skill(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
