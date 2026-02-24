#!/usr/bin/env python3
"""Generate or update CHANGELOG.md entries from git differences."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

AUTO_START = "<!-- AUTO-GENERATED:START -->"
AUTO_END = "<!-- AUTO-GENERATED:END -->"
LINKS_START = "<!-- LINKS:START -->"
LINKS_END = "<!-- LINKS:END -->"

CHANGELOG_PATH = Path("CHANGELOG.md")
CATEGORY_ORDER = ["Added", "Changed", "Fixed", "Tests", "Docs"]

DEFAULT_CHANGELOG_TEMPLATE = """# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).

## [Unreleased]

<!-- AUTO-GENERATED:START -->
### Changed
- 暂无未发布变更。
<!-- AUTO-GENERATED:END -->
"""


@dataclass(frozen=True)
class Section:
    label: str
    start: int
    header_end: int
    end: int


def run_git(args: Sequence[str]) -> str:
    """Run a git command and return stdout."""
    proc = subprocess.run(
        ["git", *args],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {stderr}")
    return proc.stdout


def parse_name_status(output: str) -> List[Tuple[str, str]]:
    """Parse `git diff --name-status` output into (status, path)."""
    entries: List[Tuple[str, str]] = []
    for raw in output.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        path = parts[-1]
        entries.append((status, path))
    return entries


def _append_unique(items: List[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _parse_sections(content: str) -> List[Section]:
    pattern = re.compile(r"^## \[([^\]]+)\](?: - [0-9]{4}-[0-9]{2}-[0-9]{2})?\s*$", re.M)
    matches = list(pattern.finditer(content))
    sections: List[Section] = []
    for idx, match in enumerate(matches):
        start = match.start()
        header_end = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(content)
        sections.append(Section(label=match.group(1), start=start, header_end=header_end, end=end))
    return sections


def _replace_or_prepend_generated_block(section_body: str, block: str) -> str:
    marker = f"{AUTO_START}\n{block.rstrip()}\n{AUTO_END}\n"

    start_idx = section_body.find(AUTO_START)
    end_idx = section_body.find(AUTO_END)
    if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
        end_idx += len(AUTO_END)
        prefix = section_body[:start_idx]
        suffix = section_body[end_idx:]
        return f"{prefix}{marker}{suffix}".strip("\n") + "\n"

    trimmed = section_body.strip("\n")
    if trimmed:
        return f"{marker}\n{trimmed}\n"
    return marker


def _find_section(content: str, label: str) -> Section | None:
    for section in _parse_sections(content):
        if section.label == label:
            return section
    return None


def upsert_section(content: str, label: str, date: str | None, block: str) -> str:
    """Upsert generated block under target section."""
    heading = f"## [{label}]" + (f" - {date}" if date else "")

    target = _find_section(content, label)
    if target is not None:
        body = content[target.header_end:target.end]
        new_body = _replace_or_prepend_generated_block(body, block)
        replacement = f"{heading}\n\n{new_body}\n"
        return content[:target.start] + replacement + content[target.end:].lstrip("\n")

    sections = _parse_sections(content)
    unreleased = _find_section(content, "Unreleased")
    if label != "Unreleased" and unreleased is not None:
        insert_at = unreleased.end
    elif sections:
        insert_at = sections[0].start
    else:
        insert_at = len(content)

    new_section = f"\n{heading}\n\n{AUTO_START}\n{block.rstrip()}\n{AUTO_END}\n"
    return content[:insert_at] + new_section + "\n" + content[insert_at:].lstrip("\n")


def previous_patch_version(version: str) -> str | None:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)$", version)
    if not match:
        return None
    major, minor, patch = map(int, match.groups())
    if patch <= 0:
        return None
    return f"{major}.{minor}.{patch - 1}"


def detect_repo_url() -> str:
    """Detect repository web URL from git remotes."""
    for remote in ("github", "origin"):
        try:
            raw = run_git(["config", "--get", f"remote.{remote}.url"]).strip()
        except RuntimeError:
            continue
        if not raw:
            continue

        if raw.startswith("git@"):
            host_path = raw.split("@", 1)[1]
            host, path = host_path.split(":", 1)
            return f"https://{host}/{path.removesuffix('.git')}"
        if raw.startswith("ssh://git@"):
            value = raw.removeprefix("ssh://git@")
            host, path = value.split("/", 1)
            return f"https://{host}/{path.removesuffix('.git')}"
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw.removesuffix(".git")

    return "https://github.com/didengren/micro-app-mcp"


def upsert_compare_links(content: str, repo_url: str) -> str:
    """Upsert compare links block at file end."""
    versions = [s.label for s in _parse_sections(content) if s.label != "Unreleased"]
    lines: List[str] = []

    if versions:
        lines.append(f"[Unreleased]: {repo_url}/compare/v{versions[0]}...HEAD")
    else:
        lines.append(f"[Unreleased]: {repo_url}/compare/HEAD")

    for idx, version in enumerate(versions):
        prev = versions[idx + 1] if idx + 1 < len(versions) else previous_patch_version(version)
        if prev:
            lines.append(f"[{version}]: {repo_url}/compare/v{prev}...v{version}")
        else:
            lines.append(f"[{version}]: {repo_url}/releases/tag/v{version}")

    block = f"{LINKS_START}\n" + "\n".join(lines) + f"\n{LINKS_END}\n"

    start_idx = content.find(LINKS_START)
    end_idx = content.find(LINKS_END)
    if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
        end_idx += len(LINKS_END)
        return content[:start_idx] + block + content[end_idx:].lstrip("\n")

    return content.rstrip() + "\n\n" + block


def build_categories(
    entries: Sequence[Tuple[str, str]],
    key_diff: str,
    commit_lines: Sequence[str],
    lang: str,
) -> Dict[str, List[str]]:
    """Build changelog categories from changed files and key diffs."""
    categories = {name: [] for name in CATEGORY_ORDER}
    paths = {path for _, path in entries}
    status_map = {path: status for status, path in entries}
    handled: set[str] = set()

    def add(cat: str, text: str) -> None:
        _append_unique(categories[cat], text)

    if "src/micro_app_mcp/app/server.py" in paths:
        add("Added", "/micro 统一命令分发增强，支持显式工具名解析与参数自动类型转换。")
        add("Fixed", "修复“更新日志/版本更新”类检索误触发更新任务的问题。")
        handled.add("src/micro_app_mcp/app/server.py")

    if "src/micro_app_mcp/app/tools.py" in paths:
        add("Added", "新增更新任务模型（提交任务、查询任务状态、任务生命周期字段）。")
        add("Changed", "search_micro_app_knowledge 改为线程下沉执行向量检索并加超时保护。")
        add("Changed", "update_knowledge_base 演进为后台任务模式（非阻塞）并支持任务轮询。")
        add("Fixed", "修复高并发/长时间运行下任务状态管理与裁剪行为不稳定的问题。")
        handled.add("src/micro_app_mcp/app/tools.py")

    if "src/micro_app_mcp/config.py" in paths:
        add("Added", "新增配置项：检索超时、更新任务保留策略、更新意图关键词。")
        add("Added", "新增目录回退来源标识（data_dir_source）与系统临时目录兜底。")
        add("Fixed", "修复数据目录不可写时仅单级回退的脆弱性，改为多级候选链。")
        handled.add("src/micro_app_mcp/config.py")

    if status_map.get("tests/test_config.py", "").startswith("A"):
        add("Added", "新增测试文件 tests/test_config.py，补齐目录兜底链路验证。")
        handled.add("tests/test_config.py")

    if "src/micro_app_mcp/storage/metadata.py" in paths:
        add("Changed", "MetadataManager 引入并发安全增强（单例、线程锁/文件锁、任务状态持久化）。")
        handled.add("src/micro_app_mcp/storage/metadata.py")

    if "src/micro_app_mcp/knowledge/github_loader.py" in paths:
        add("Changed", "GitHubLoader 改为 async 壳 + sync 核，避免阻塞事件循环。")
        handled.add("src/micro_app_mcp/knowledge/github_loader.py")

    if "src/micro_app_mcp/knowledge/vectorizer.py" in paths:
        add("Changed", "LazyEmbedder 增加并发加载保护，避免重复初始化。")
        handled.add("src/micro_app_mcp/knowledge/vectorizer.py")

    if "README.md" in paths or ".env.example" in paths:
        add("Changed", "README、.env.example、MCP 配置示例全面更新。")
        handled.update({"README.md", ".env.example"})

    if "tests/test_tools.py" in paths:
        add("Tests", "扩展 tests/test_tools.py：路由优先级、超时提示、事件循环不阻塞、任务状态回退等。")
        handled.add("tests/test_tools.py")

    if "tests/test_knowledge.py" in paths:
        add("Tests", "扩展 tests/test_knowledge.py：GitHub loader 非阻塞、懒加载并发单次初始化。")
        handled.add("tests/test_knowledge.py")

    if "tests/test_config.py" in paths:
        handled.add("tests/test_config.py")

    # Use key diff to mark docs/tests when dedicated files are absent.
    if "update_knowledge_base" in key_diff and not categories["Changed"]:
        add("Changed", "更新知识库流程已调整。")

    for path in sorted(paths - handled):
        if path.startswith("tests/"):
            add("Tests", f"更新测试：`{path}`")
        elif path.endswith(".md") or path.endswith(".example"):
            add("Docs", f"更新文档：`{path}`")
        else:
            add("Changed", f"更新文件：`{path}`")

    if all(not categories[name] for name in CATEGORY_ORDER):
        if lang == "zh":
            add("Changed", "暂无可归类变更。")
        else:
            add("Changed", "No notable changes were detected.")

    if commit_lines and len(commit_lines) <= 5:
        joined = "；".join(commit_lines)
        add("Docs", f"关联提交：{joined}")

    return categories


def render_categories(categories: Dict[str, List[str]]) -> str:
    lines: List[str] = []
    for category in CATEGORY_ORDER:
        items = categories.get(category, [])
        if not items:
            continue
        lines.append(f"### {category}")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default="main")
    parser.add_argument("--head-ref", default="HEAD")
    parser.add_argument("--version", required=True)
    parser.add_argument(
        "--date",
        default=datetime.now(timezone.utc).date().isoformat(),
        help="Release date in YYYY-MM-DD.",
    )
    parser.add_argument("--target", choices=["unreleased", "version"], default="version")
    parser.add_argument("--lang", default="zh")
    parser.add_argument("--update-links", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--changelog-path", default=str(CHANGELOG_PATH))
    return parser.parse_args(argv)


def load_changelog(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return DEFAULT_CHANGELOG_TEMPLATE


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    changelog_path = Path(args.changelog_path)

    range_ref = f"{args.base_ref}..{args.head_ref}"
    commit_output = run_git(["log", "--oneline", "--no-decorate", range_ref])
    commit_lines = [line.strip() for line in commit_output.splitlines() if line.strip()]

    diff_output = run_git(["diff", "--name-status", range_ref])
    entries = parse_name_status(diff_output)

    key_files = [
        "src/micro_app_mcp/app/server.py",
        "src/micro_app_mcp/app/tools.py",
        "src/micro_app_mcp/config.py",
        "src/micro_app_mcp/storage/metadata.py",
        "src/micro_app_mcp/knowledge/github_loader.py",
        "src/micro_app_mcp/knowledge/vectorizer.py",
        "tests/test_tools.py",
        "tests/test_knowledge.py",
        "tests/test_config.py",
    ]
    key_diff = run_git(["diff", "--unified=2", range_ref, "--", *key_files])

    categories = build_categories(entries, key_diff, commit_lines, args.lang)
    block = render_categories(categories)

    target_label = "Unreleased" if args.target == "unreleased" else args.version
    target_date = None if args.target == "unreleased" else args.date

    content = load_changelog(changelog_path)
    content = upsert_section(content, target_label, target_date, block)

    if args.update_links:
        content = upsert_compare_links(content, detect_repo_url())

    changelog_path.write_text(content, encoding="utf-8")

    print(
        f"updated {changelog_path} with range {range_ref} -> section [{target_label}]"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
