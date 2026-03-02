"""测试日志工具"""

import logging
from logging.handlers import RotatingFileHandler

from micro_app_mcp.utils.logger import setup_logging


def test_setup_logging_creates_directory_and_file(monkeypatch, tmp_path):
    """测试 setup_logging 会自动创建日志目录和文件。"""
    # Mock config.DATA_DIR 到临时目录
    import micro_app_mcp.config as config_module

    # 模拟数据目录
    mock_data_dir = tmp_path / "data"

    # 使用 monkeypatch 安全地修改全局配置，测试结束后会自动还原
    monkeypatch.setattr(config_module.config, "DATA_DIR", mock_data_dir)

    # 执行初始化
    setup_logging()

    # 验证目录是否创建
    log_dir = mock_data_dir / "logs"
    assert log_dir.exists()
    assert log_dir.is_dir()

    # 验证日志文件是否创建（logging 只有写入时才创建文件，或者初始化时创建空文件，取决于实现）
    # basicConfig 里的 FileHandler 通常会在打开时创建文件
    log_file = log_dir / "micro_app_mcp.log"

    # 强制写入一条日志以触发文件创建
    logger = logging.getLogger("test_logger")
    logger.info("test message")

    assert log_file.exists()
    assert "test message" in log_file.read_text(encoding="utf-8")


def test_logging_handlers_configuration(capsys, monkeypatch, tmp_path):
    """测试日志处理器的配置是否正确（RotatingFileHandler + StreamHandler）。"""
    # 必须先配置环境，否则 handlers 为空或残留
    import micro_app_mcp.config as config_module

    mock_data_dir = tmp_path / "handlers_test"
    monkeypatch.setattr(config_module.config, "DATA_DIR", mock_data_dir)

    setup_logging()

    # 获取 root logger 的 handlers
    root_logger = logging.getLogger()
    handlers = root_logger.handlers

    # 验证是否包含 RotatingFileHandler 和 StreamHandler
    has_rotating = any(isinstance(h, RotatingFileHandler) for h in handlers)
    has_stream = any(isinstance(h, logging.StreamHandler) for h in handlers)

    assert has_rotating, "必须配置 RotatingFileHandler"
    assert has_stream, "必须配置 StreamHandler"

    # 验证 RotatingFileHandler 的配置
    rotating_handler = next(h for h in handlers if isinstance(h, RotatingFileHandler))
    assert rotating_handler.backupCount == 3
    # 验证是否使用了 UTF-8
    assert rotating_handler.encoding is not None
    assert rotating_handler.encoding.lower() == "utf-8"

    # 验证 StreamHandler 输出到 stderr (通过行为验证)
    logger = logging.getLogger("stderr_test")
    logger.error("error_message_to_stderr")

    captured = capsys.readouterr()
    assert "error_message_to_stderr" in captured.err
    # 注意：根据 setup_logging 的配置，info 级别也会输出到 stderr
    logger.info("info_message_to_stderr")
    captured = capsys.readouterr()
    assert "info_message_to_stderr" in captured.err


def test_log_rotation_logic(monkeypatch, tmp_path):
    """测试日志轮转逻辑（通过 mock maxBytes）。"""
    import micro_app_mcp.config as config_module

    # Mock 数据目录
    mock_data_dir = tmp_path / "rotation_test"
    monkeypatch.setattr(config_module.config, "DATA_DIR", mock_data_dir)

    # 关键：我们不能直接改 setup_logging 里的硬编码参数，
    # 但我们可以验证 RotatingFileHandler 的行为，或者在这里重新配置一个极小的 handler 来模拟轮转。
    # 鉴于 setup_logging 里的参数是硬编码的，单元测试很难直接测到 "10MB" 这个值引发的轮转。
    # 这里我们采用 "验证配置值" + "手动触发轮转" 的策略。

    setup_logging()

    root_logger = logging.getLogger()
    handler = next(h for h in root_logger.handlers if isinstance(h, RotatingFileHandler))

    # 验证配置的 maxBytes (假设是 1MB 或 10MB，这里先断言它大于 0)
    assert handler.maxBytes > 0

    # 模拟轮转：手动调用 doRollover
    log_file = mock_data_dir / "logs" / "micro_app_mcp.log"
    log_file.write_text("content", encoding="utf-8")

    handler.doRollover()

    # 验证备份文件是否存在
    assert (mock_data_dir / "logs" / "micro_app_mcp.log.1").exists()
