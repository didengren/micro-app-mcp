"""测试配置与目录兜底逻辑"""

from pathlib import Path

import pytest

import micro_app_mcp.config as config_module


def test_ensure_data_dirs_falls_back_to_system_temp(monkeypatch, tmp_path):
    """DATA_DIR 与 FALLBACK_DATA_DIR 不可写时应降级到系统临时目录。"""
    cfg = config_module.config

    primary = tmp_path / "primary"
    fallback = tmp_path / "fallback"
    temp_base = tmp_path / "temp_base"
    system_candidate = temp_base / "micro_app_mcp"

    cfg.DATA_DIR = primary
    cfg.DATA_DIR_SOURCE = "data_dir"

    monkeypatch.setenv("FALLBACK_DATA_DIR", str(fallback))
    monkeypatch.setattr(config_module.tempfile, "gettempdir", lambda: str(temp_base))

    # Mock Path.mkdir instead of _prepare_data_dir
    original_mkdir = Path.mkdir

    def fake_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        # Normalize paths for comparison
        path_str = str(self)
        if path_str.startswith(str(primary)) or path_str.startswith(str(fallback)):
            raise PermissionError(f"denied:{self}")

        # Call original mkdir for other paths (like temp_base)
        return original_mkdir(self, mode=mode, parents=parents, exist_ok=exist_ok)

    monkeypatch.setattr(Path, "mkdir", fake_mkdir)

    config_module._ensure_data_dirs()

    assert cfg.DATA_DIR == system_candidate
    assert cfg.CHROMA_DB_PATH == system_candidate / "chroma_db"
    assert cfg.METADATA_PATH == system_candidate / "metadata.json"
    assert cfg.DATA_DIR_SOURCE == "system_temp"


def test_ensure_data_dirs_raises_when_all_candidates_unwritable(monkeypatch, tmp_path):
    """全部候选目录不可写时应抛出可诊断错误。"""
    cfg = config_module.config

    primary = tmp_path / "primary"
    fallback = tmp_path / "fallback"
    temp_base = tmp_path / "temp_base"

    cfg.DATA_DIR = primary
    cfg.DATA_DIR_SOURCE = "data_dir"

    monkeypatch.setenv("FALLBACK_DATA_DIR", str(fallback))
    monkeypatch.setattr(config_module.tempfile, "gettempdir", lambda: str(temp_base))

    # Mock Path.mkdir to fail for ALL candidates
    def failing_mkdir(self, mode=0o777, parents=False, exist_ok=False):
        raise PermissionError(f"denied:{self}")

    monkeypatch.setattr(Path, "mkdir", failing_mkdir)

    with pytest.raises(RuntimeError) as exc_info:
        config_module._ensure_data_dirs()

    msg = str(exc_info.value)
    assert "数据目录初始化失败" in msg
    assert "data_dir" in msg
    assert "fallback_data_dir" in msg
    assert "system_temp" in msg
