"""Tests for release automation with commitizen."""

import tomllib
from pathlib import Path


def test_commitizen_config_exists():
    cz_path = Path(".cz.yaml")
    assert cz_path.exists()

    content = cz_path.read_text(encoding="utf-8")
    assert "commitizen" in content
    assert "cz_customize" in content
    assert "tag_format" in content
    assert "pep621" in content
    assert "update_changelog_on_bump" in content


def test_commitizen_in_dev_dependencies():
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text(encoding="utf-8")
    pyproject = tomllib.loads(content)

    dev_deps = (
        pyproject.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    )
    assert any("commitizen" in dep for dep in dev_deps)


def test_ruff_in_dev_dependencies():
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text(encoding="utf-8")
    pyproject = tomllib.loads(content)

    dev_deps = (
        pyproject.get("project", {}).get("optional-dependencies", {}).get("dev", [])
    )
    assert any("ruff" in dep for dep in dev_deps)


def test_ruff_config_in_pyproject():
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text(encoding="utf-8")
    pyproject = tomllib.loads(content)

    assert "ruff" in pyproject.get("tool", {})
    ruff = pyproject["tool"]["ruff"]
    assert "line-length" in ruff
    assert "target-version" in ruff


def test_pre_commit_hook_contains_ruff():
    hook_path = Path(".githooks/pre-commit")
    content = hook_path.read_text(encoding="utf-8")

    assert "ruff check" in content
    assert "git add" in content


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


def test_install_hooks_script_exists():
    script_path = Path("scripts/install_hooks.sh")
    assert script_path.exists()

    content = script_path.read_text(encoding="utf-8")
    assert "core.hooksPath" in content
    assert ".githooks/pre-commit" in content
