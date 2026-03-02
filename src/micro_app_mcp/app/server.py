"""FastMCP Server 定义"""

import inspect
import re
import shlex
from typing import Any, get_args, get_origin

from fastmcp import FastMCP
from fastmcp.tools.function_tool import FunctionTool

from micro_app_mcp.app.tools import get_knowledge_base_status as status_tool
from micro_app_mcp.app.tools import search_micro_app_knowledge as search_tool
from micro_app_mcp.app.tools import update_knowledge_base as update_tool
from micro_app_mcp.config import config

mcp = FastMCP(
    "micro-app-knowledge-server",
    instructions=(
        "当用户消息以 /micro 开头或包含 /micro 时，优先调用 micro_app_command 工具。"
        "若命令中显式包含工具名（如 update_knowledge_base），会优先按工具名精确分发。"
        "micro_app_command 会自动分发："
        "1) 状态类请求 -> get_knowledge_base_status；"
        "2) 更新/同步类请求 -> update_knowledge_base；"
        "3) 其他请求 -> search_micro_app_knowledge。"
    ),
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
    lowered = command.lower().strip()
    if not lowered:
        return False

    if "update_knowledge_base" in lowered:
        return True

    search_only_patterns = config.UPDATE_INTENT_SEARCH_ONLY_PATTERNS
    if any(p in lowered for p in search_only_patterns):
        return False

    action_keywords = config.UPDATE_INTENT_ACTION_KEYWORDS
    target_keywords = config.UPDATE_INTENT_TARGET_KEYWORDS
    has_action = any(k in lowered for k in action_keywords)
    has_target = any(k in lowered for k in target_keywords)

    action_pattern = "|".join(re.escape(k) for k in action_keywords)
    target_pattern = "|".join(re.escape(k) for k in target_keywords)
    compact_patterns = []
    if action_pattern and target_pattern:
        compact_patterns = [
            rf"({action_pattern}).{{0,8}}({target_pattern})",
            rf"({target_pattern}).{{0,8}}({action_pattern})",
        ]
    has_compact_match = any(re.search(p, lowered) for p in compact_patterns)

    return has_compact_match or (has_action and has_target)


def _is_force_update(command: str) -> bool:
    """判断是否要求强制更新"""
    lowered = command.lower()
    _strip_lowered = "".join(lowered.split())
    return "force=true" in _strip_lowered or "强制" in lowered


def _parse_bool(value: str) -> bool:
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "y"}:
        return True
    if lowered in {"false", "0", "no", "n"}:
        return False
    raise ValueError(f"无法解析布尔值: {value}")


def _coerce_param_value(raw: str, param: inspect.Parameter) -> Any:
    """根据函数签名将字符串参数转换为目标类型。"""
    annotation = param.annotation
    default = param.default
    target = annotation
    if target is inspect._empty and default is not inspect._empty:
        target = type(default)

    origin = get_origin(target)
    if origin is None:
        if target in (inspect._empty, str):
            return raw
        if target is bool:
            return _parse_bool(raw)
        if target is int:
            return int(raw)
        if target is float:
            return float(raw)
        return raw

    if origin is list:
        return [item.strip() for item in raw.split(",") if item.strip()]

    if origin is tuple:
        return tuple(item.strip() for item in raw.split(",") if item.strip())

    if origin is type(None):
        return None

    if origin is Any:
        return raw

    if origin is not None:
        union_args = [arg for arg in get_args(target) if arg is not type(None)]
        if len(union_args) == 1:
            temp_param = inspect.Parameter(
                param.name,
                kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=union_args[0],
                default=param.default,
            )
            return _coerce_param_value(raw, temp_param)

    return raw


def _tokenize_command(command: str) -> list[str]:
    """解析命令字符串为 token。"""
    if not command.strip():
        return []
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


async def _dispatch_explicit_tool_call(command: str, top_k: int) -> object | None:
    """显式工具名分发：支持所有已注册 MCP 工具通过 /micro 触发。"""
    tokens = _tokenize_command(command)  # list化命令参数
    if not tokens:
        return None

    tool_name = tokens[0]  # 提取的工具名

    if tool_name == "micro_app_command":
        return {
            "status": "bad_request",
            "message": "请勿在 /micro 内再次调用 micro_app_command。",
        }

    try:
        tool = await mcp.local_provider.get_tool(tool_name)  # 通过工具名拿到注册的工具实例
    except Exception:
        tool = None

    if tool is None:
        return None

    if not isinstance(tool, FunctionTool):
        return None

    fn = tool.fn  # 工具名对应的工具函数
    signature = inspect.signature(fn)  # 工具函数的参数签名对象

    raw_kwargs: dict[str, str] = {}  # 存储解析token后的键值对参数
    positional_tokens: list[str] = []  # 存储token里的位置参数
    for token in tokens[1:]:
        if "=" in token:
            key, value = token.split("=", 1)
            raw_kwargs[key.strip()] = value.strip()
        else:
            positional_tokens.append(token)

    kwargs: dict[str, Any] = {}  # 经过类型转换的参数键值对列表
    pos_idx = 0
    parameters = list(signature.parameters.values())  # 形参对象的列表
    for idx, param in enumerate(parameters):
        if param.kind in {
            inspect.Parameter.VAR_POSITIONAL,
            inspect.Parameter.VAR_KEYWORD,
        }:
            continue

        name = param.name
        if name in raw_kwargs:
            try:
                kwargs[name] = _coerce_param_value(raw_kwargs.pop(name), param)
            except ValueError as e:
                return {"status": "bad_request", "message": str(e)}
            continue

        if name in {"query", "command"} and pos_idx < len(positional_tokens):
            kwargs[name] = " ".join(positional_tokens[pos_idx:])
            pos_idx = len(positional_tokens)
            continue

        if pos_idx < len(positional_tokens):
            try:
                kwargs[name] = _coerce_param_value(positional_tokens[pos_idx], param)
            except ValueError as e:
                return {"status": "bad_request", "message": str(e)}
            pos_idx += 1
            continue

        if name == "top_k":
            kwargs[name] = top_k
            continue

        if name == "force" and tool_name == "update_knowledge_base":
            kwargs[name] = _is_force_update(command)
            continue

        if param.default is inspect._empty:
            missing = [name]
            missing.extend(
                p.name
                for p in parameters[idx + 1 :]
                if p.default is inspect._empty
                and p.kind
                not in {
                    inspect.Parameter.VAR_POSITIONAL,
                    inspect.Parameter.VAR_KEYWORD,
                }
            )
            return {
                "status": "bad_request",
                "message": f"{tool_name} 缺少必填参数: {', '.join(missing)}",
            }

    if raw_kwargs:
        return {
            "status": "bad_request",
            "message": f"{tool_name} 存在未知参数: {', '.join(sorted(raw_kwargs.keys()))}",
        }

    if pos_idx < len(positional_tokens):
        return {
            "status": "bad_request",
            "message": (f"{tool_name} 存在无法解析的额外参数: {' '.join(positional_tokens[pos_idx:])}"),
        }

    if inspect.iscoroutinefunction(fn):
        return await fn(**kwargs)
    return fn(**kwargs)


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

    explicit_result = await _dispatch_explicit_tool_call(normalized, top_k)
    if explicit_result is not None:
        return explicit_result

    if _is_update_command(normalized):
        return await update_tool(force=_is_force_update(normalized))

    if _is_status_command(normalized):
        return await status_tool()

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
    非阻塞触发知识库更新。

    Args:
        force: 是否强制更新，强制更新会重新采集所有数据

    Returns:
        任务提交结果或“已有任务执行中”提示
    """
    return await update_tool(force=force)
