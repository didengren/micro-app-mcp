#!/usr/bin/env python3
"""测试导入和组件初始化"""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

print("测试导入开始...")

# 测试配置模块
try:
    from micro_app_mcp.config import config

    print("✅ 导入配置模块成功")
    print(f"  嵌入模型: {config.EMBEDDING_MODEL_NAME}")
    print(f"  GitHub 仓库: {config.GITHUB_REPO}")
    print(f"  文档 URL: {config.DOCS_URL}")
except Exception as e:
    print(f"❌ 导入配置模块失败: {e}")

# 测试向量存储模块
try:
    from micro_app_mcp.storage.vector_store import VectorStore

    vector_store = VectorStore()
    print("✅ 初始化向量存储成功")
except Exception as e:
    print(f"❌ 初始化向量存储失败: {e}")

# 测试元数据管理模块
try:
    from micro_app_mcp.storage.metadata import MetadataManager

    metadata_manager = MetadataManager()
    print("✅ 初始化元数据管理成功")
except Exception as e:
    print(f"❌ 初始化元数据管理失败: {e}")

# 测试工具模块
try:
    from micro_app_mcp.app.tools import (
        search_micro_app_knowledge,
        update_knowledge_base,
    )

    print("✅ 导入工具模块成功")
except Exception as e:
    print(f"❌ 导入工具模块失败: {e}")

# 测试 MCP 服务器模块 (FastMCP)
try:
    from micro_app_mcp.app.server import mcp

    print("✅ 导入 FastMCP 服务器模块成功")
except Exception as e:
    print(f"❌ 导入 FastMCP 服务器模块失败: {e}")

print("测试导入完成！")
