#!/usr/bin/env python3
"""直接测试 MCP 服务器功能"""

import os
import sys

# 确保能导入项目模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

import asyncio

from micro_app_mcp.app.tools import search_micro_app_knowledge, update_knowledge_base


async def test_server_functions():
    """测试服务器功能"""
    print("测试服务器功能开始...")

    # 测试更新知识库
    print("\n1. 测试更新知识库:")
    try:
        update_result = await update_knowledge_base(force=False)
        print(f"✅ 更新结果: {update_result}")
    except Exception as e:
        print(f"❌ 更新失败: {e}")

    # 测试搜索功能
    print("\n2. 测试搜索功能:")
    try:
        search_result = await search_micro_app_knowledge(
            query="micro-app 是什么？", top_k=2
        )
        print("✅ 搜索结果:")
        print(search_result)
    except Exception as e:
        print(f"❌ 搜索失败: {e}")

    print("\n测试服务器功能完成！")


if __name__ == "__main__":
    asyncio.run(test_server_functions())
