"""Tests for changelog and release automation scripts."""

from pathlib import Path

import scripts.generate_changelog as changelog
import scripts.version_change_detector as version_detector


EXPECTED_CHANGED_FILES = [
    ("M", ".env.example"),
    ("M", "README.md"),
    ("M", "pyproject.toml"),
    ("M", "src/micro_app_mcp/app/server.py"),
    ("M", "src/micro_app_mcp/app/tools.py"),
    ("M", "src/micro_app_mcp/config.py"),
    ("M", "src/micro_app_mcp/knowledge/github_loader.py"),
    ("M", "src/micro_app_mcp/knowledge/vectorizer.py"),
    ("M", "src/micro_app_mcp/storage/metadata.py"),
    ("A", "tests/test_config.py"),
    ("M", "tests/test_knowledge.py"),
    ("M", "tests/test_tools.py"),
]


def test_extract_version_from_pyproject_text():
    text = """
[project]
name = \"demo\"
version = \"1.2.3\"
"""
    assert version_detector.extract_version(text) == "1.2.3"


def test_parse_name_status_with_rename():
    parsed = changelog.parse_name_status("M\ta.py\nR100\told.py\tnew.py\n")
    assert parsed == [("M", "a.py"), ("R100", "new.py")]


def test_build_categories_for_master_fix_timeout_diff():
    categories = changelog.build_categories(
        EXPECTED_CHANGED_FILES,
        key_diff="update_knowledge_base wait_for",
        commit_lines=["f1e67ef Merge branch 'feat/multi_process' into fix/timeout"],
        lang="zh",
    )

    assert any("统一命令分发增强" in item for item in categories["Added"])
    assert any("后台任务模式" in item for item in categories["Changed"])
    assert any("数据目录不可写" in item for item in categories["Fixed"])
    assert any("tests/test_tools.py" in item for item in categories["Tests"])


def test_upsert_section_is_idempotent_for_same_version():
    block = "### Added\n- 新增测试条目\n"
    first = changelog.upsert_section(
        changelog.DEFAULT_CHANGELOG_TEMPLATE,
        label="0.1.2",
        date="2026-02-24",
        block=block,
    )
    second = changelog.upsert_section(
        first,
        label="0.1.2",
        date="2026-02-24",
        block=block,
    )

    assert first == second
    assert second.count(changelog.AUTO_START) == 2
    assert second.count("## [0.1.2] - 2026-02-24") == 1


def test_upsert_compare_links_contains_expected_entries():
    content = changelog.upsert_section(
        changelog.DEFAULT_CHANGELOG_TEMPLATE,
        label="0.1.2",
        date="2026-02-24",
        block="### Changed\n- x\n",
    )
    linked = changelog.upsert_compare_links(content, "https://github.com/didengren/micro-app-mcp")

    assert "[Unreleased]: https://github.com/didengren/micro-app-mcp/compare/v0.1.2...HEAD" in linked
    assert "[0.1.2]: https://github.com/didengren/micro-app-mcp/compare/v0.1.1...v0.1.2" in linked


def test_pre_commit_hook_contains_required_steps():
    hook_path = Path(".githooks/pre-commit")
    content = hook_path.read_text(encoding="utf-8")

    assert "scripts/version_change_detector.py" in content
    assert "scripts/generate_changelog.py" in content
    assert "--base-ref main" in content
    assert "git add CHANGELOG.md" in content


def test_release_workflow_contains_required_jobs_and_secrets():
    workflow_path = Path(".github/workflows/release-pypi.yml")
    content = workflow_path.read_text(encoding="utf-8")

    assert "push:" in content and "tags:" in content and "v*" in content
    assert "validate-and-test:" in content
    assert "publish-testpypi:" in content
    assert "publish-pypi:" in content
    assert "TEST_PYPI_TOKEN" in content
    assert "PYPI_TOKEN" in content
    assert "uv publish" in content
