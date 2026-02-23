"""FastMCP Server 定义"""

from fastmcp import FastMCP
from micro_app_mcp.app.tools import (
    get_knowledge_base_status as status_tool,
    search_micro_app_knowledge as search_tool,
    update_knowledge_base as update_tool
)

# 创建 FastMCP 实例，包含 /micro 触发机制
mcp = FastMCP(
    "micro-app-knowledge-server",
    instructions=(
        "当用户消息以 /micro 开头或包含 /micro 时，优先调用 micro_app_command 工具。"
        "micro_app_command 会自动分发："
        "1) 状态类请求 -> get_knowledge_base_status；"
        "2) 更新/同步类请求 -> update_knowledge_base；"
        "3) 其他请求 -> search_micro_app_knowledge。"
    )
)


def _normalize_micro_command(command: str) -> str:
    """移除 /micro 前缀，得到实际命令内容"""
    return command.replace("/micro", "", 1).strip()


def _is_status_command(command: str) -> bool:
    """判断是否为状态查询命令"""
    keywords = ("状态", "status", "更新时间", "是否过期", "过期", "stale")
    lowered = command.lower()
    return "get_knowledge_base_status" in lowered or any(k in lowered for k in keywords)


def _is_update_command(command: str) -> bool:
    """判断是否为更新命令"""
    keywords = ("更新", "同步", "重建", "refresh", "update")
    lowered = command.lower()
    return "update_knowledge_base" in lowered or any(k in lowered for k in keywords)


def _is_force_update(command: str) -> bool:
    """判断是否要求强制更新"""
    lowered = command.lower()
    return "force=true" in lowered or "强制" in lowered


@mcp.tool()
async def micro_app_command(command: str, top_k: int = 15) -> object:
    """
    统一处理 /micro 命令并自动分发到对应工具。

    Args:
        command: 用户输入命令（可包含 /micro 前缀）
        top_k: 搜索时返回结果数量

    Returns:
        状态字典或结果文本
    """
    normalized = _normalize_micro_command(command)

    if _is_status_command(normalized):
        return await status_tool()

    if _is_update_command(normalized):
        return await update_tool(force=_is_force_update(normalized))

    query = normalized or command
    return await search_tool(query, top_k)


@mcp.tool()
async def search_micro_app_knowledge(query: str, top_k: int = 15) -> str:
    """
    语义检索 micro-app 知识库。

    Args:
        query: 用户查询内容
        top_k: 返回最相关的结果数量，默认 15

    Returns:
        格式化的检索结果，包含源码和文档片段
    """
    return await search_tool(query, top_k)


@mcp.tool()
async def get_knowledge_base_status() -> dict:
    """
    获取知识库状态。

    Returns:
        状态信息，包含更新时间、过期状态、文档数量等
    """
    return await status_tool()


@mcp.tool()
async def update_knowledge_base(force: bool = False) -> str:
    """
    触发知识库更新。
    
    Args:
        force: 是否强制更新，强制更新会重新采集所有数据
    
    Returns:
        更新结果摘要
    """
    return await update_tool(force)
