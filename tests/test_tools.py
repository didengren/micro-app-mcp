"""测试 MCP 工具"""

import pytest

from micro_app_mcp.app.tools import search_micro_app_knowledge, update_knowledge_base


@pytest.mark.asyncio
async def test_search_micro_app_knowledge():
    """测试搜索工具"""
    # 测试搜索功能
    result = await search_micro_app_knowledge("如何使用 micro-app")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_update_knowledge_base():
    """测试更新工具"""
    # 测试更新功能
    result = await update_knowledge_base(force=True)
    assert isinstance(result, str)
    assert len(result) > 0
