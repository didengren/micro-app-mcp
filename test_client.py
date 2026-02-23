#!/usr/bin/env python3
"""MCP Server 测试客户端"""

import json

from mcp.client.session import ClientSession
from mcp.client.stdio import stdio_client


async def test_mcp_server():
    """测试 MCP 服务器"""
    print("连接到 MCP 服务器...")

    try:
        # 创建 stdio 客户端
        async with stdio_client() as (read_stream, write_stream):
            # 创建 MCP 客户端会话
            async with ClientSession(read_stream, write_stream) as session:
                # 初始化连接
                initialization = await session.initialize()
                print(
                    f"✅ 初始化成功: {initialization.serverInfo.name} v{initialization.serverInfo.version}"
                )

                # 获取工具列表
                tools = await session.list_tools()
                print("\n✅ 获取工具列表成功:")
                for tool in tools:
                    print(f"  - {tool.name}: {tool.description}")
                    print(f"    输入 schema: {json.dumps(tool.inputSchema, indent=4)}")

                # 测试搜索工具
                print("\n✅ 测试搜索工具:")
                search_result = await session.call_tool(
                    "search_micro_app_knowledge",
                    {"query": "micro-app 是什么？", "top_k": 2},
                )
                print(f"搜索结果: {search_result}")

                # 测试更新工具
                print("\n✅ 测试更新工具:")
                update_result = await session.call_tool(
                    "update_knowledge_base", {"force": False}
                )
                print(f"更新结果: {update_result}")
                print("\n✅ 测试完成，连接即将关闭")

    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_mcp_server())
