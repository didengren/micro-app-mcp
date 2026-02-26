"""MCP 工具实现"""

import asyncio
import hashlib
import threading
from datetime import UTC, datetime
from functools import partial
from typing import Any

from micro_app_mcp.config import config
from micro_app_mcp.knowledge.docs_loader import DocsLoader
from micro_app_mcp.knowledge.github_loader import GitHubLoader
from micro_app_mcp.knowledge.text_splitter import TextSplitter
from micro_app_mcp.storage.metadata import MetadataManager
from micro_app_mcp.storage.vector_store import VectorStore

CONCEPT_KEYWORDS = [
    "是什么",
    "什么是",
    "介绍",
    "原理",
    "概念",
    "如何使用",
    "怎么用",
    "教程",
    "文档",
    "作用",
    "特点",
    "优势",
    "缺点",
]
CODE_KEYWORDS = [
    "代码",
    "实现",
    "源码",
    "示例",
    "demo",
    "用法",
    "调用",
    "函数",
    "API",
    "参数",
    "返回值",
    "配置",
]

_METADATA_MANAGER: MetadataManager | None = None
_STATE_LOCK = threading.Lock()
_UPDATE_TASK: asyncio.Task[None] | None = None
_UPDATE_STATE: dict[str, Any] = {
    "update_status": "idle",
    "update_started_at": None,
    "update_finished_at": None,
    "update_last_message": None,
    "update_last_error": None,
}


def _get_metadata_manager() -> MetadataManager:
    """惰性获取 MetadataManager，避免导入期触发文件 I/O。"""
    global _METADATA_MANAGER
    if _METADATA_MANAGER is None:
        _METADATA_MANAGER = MetadataManager()
    return _METADATA_MANAGER


async def _run_blocking(func, *args, **kwargs):
    """在线程池中执行同步阻塞函数。"""
    return await asyncio.to_thread(partial(func, *args, **kwargs))


def _now_iso() -> str:
    """返回 UTC ISO8601 时间字符串"""
    return (
        datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


async def _should_skip_update() -> bool:
    """在后台线程中判断是否应跳过更新"""
    manager = _get_metadata_manager()
    return await asyncio.to_thread(manager.should_skip_update)


async def _update_metadata_timestamp() -> None:
    """在后台线程中更新时间元数据"""
    manager = _get_metadata_manager()
    await asyncio.to_thread(manager.update_metadata)


async def _get_metadata_status() -> dict[str, Any]:
    """在后台线程中读取知识库元数据状态"""
    manager = _get_metadata_manager()
    return await asyncio.to_thread(manager.get_status)


def _set_update_state(
    *,
    status: str,
    started_at: str | None = None,
    finished_at: str | None = None,
    message: str | None = None,
    error: str | None = None,
) -> None:
    """更新内存态更新任务状态。"""
    with _STATE_LOCK:
        _UPDATE_STATE["update_status"] = status
        if started_at is not None or status == "idle":
            _UPDATE_STATE["update_started_at"] = started_at
        if finished_at is not None or status in {"running", "idle"}:
            _UPDATE_STATE["update_finished_at"] = finished_at
        _UPDATE_STATE["update_last_message"] = message
        _UPDATE_STATE["update_last_error"] = error


def _get_update_state_snapshot() -> dict[str, Any]:
    """返回更新状态快照。"""
    with _STATE_LOCK:
        return dict(_UPDATE_STATE)


def detect_query_type(query: str) -> str:
    """检测查询类型：概念理解 / 代码实现 / 快速定位"""
    query_lower = query.lower()
    concept_score = sum(1 for kw in CONCEPT_KEYWORDS if kw in query_lower)
    code_score = sum(1 for kw in CODE_KEYWORDS if kw in query_lower)

    if concept_score > code_score:
        return "concept"
    if code_score > concept_score:
        return "code"
    return "hybrid"


def _is_docs_result(source: str, path: str) -> bool:
    """判断结果是否应视为文档"""
    normalized_path = path.lower()
    return source == "docs" or normalized_path.startswith("docs/")


def _build_dedup_key(source: str, path: str, content: str):
    """构建去重键"""
    if _is_docs_result(source, path):
        digest = hashlib.md5(content.encode("utf-8")).hexdigest()
        return ("docs", path, digest)

    if path:
        return (source, path)

    digest = hashlib.md5(content.encode("utf-8")).hexdigest()
    return (source, digest)


async def search_micro_app_knowledge(query: str, top_k: int = 15) -> str:
    """
    语义检索 micro-app 知识库。

    Args:
        query: 用户查询内容
        top_k: 返回最相关的结果数量，默认 15

    Returns:
        格式化的检索结果，包含源码和文档片段
    """
    query_type = detect_query_type(query)

    if query_type == "concept":
        base_top_k = 10
        source_priority = {"docs": 3, "github": 2, "unknown": 1}
    elif query_type == "code":
        base_top_k = 15
        source_priority = {"github": 3, "docs": 2, "unknown": 1}
    else:
        base_top_k = top_k
        source_priority = {"docs": 3, "github": 2, "unknown": 1}

    vector_store = await _run_blocking(VectorStore)
    try:
        results = await asyncio.wait_for(
            _run_blocking(vector_store.search, query, base_top_k * 3),
            timeout=config.SEARCH_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        return (
            "向量模型正在冷启动，本次检索已超时保护返回。"
            "请稍后重试（建议30-60秒后）。"
        )

    seen_paths = set()
    filtered_results = []

    for result in results:
        source = result.metadata.get("source", "unknown")
        path = result.metadata.get("path", "") or result.metadata.get("url", "")
        dedup_key = _build_dedup_key(source, path, result.page_content)
        if dedup_key in seen_paths:
            continue
        seen_paths.add(dedup_key)
        filtered_results.append(result)

    filtered_results.sort(
        key=lambda r: source_priority.get(
            "docs"
            if _is_docs_result(
                r.metadata.get("source", "unknown"),
                r.metadata.get("path", "") or r.metadata.get("url", ""),
            )
            else r.metadata.get("source", "unknown"),
            0,
        ),
        reverse=True,
    )

    filtered_results = filtered_results[:top_k]

    formatted_results = []
    for i, result in enumerate(filtered_results, 1):
        source = result.metadata.get("source", "unknown")
        path = result.metadata.get("path", "unknown") or result.metadata.get(
            "url", "unknown"
        )
        content = result.page_content[:2000]

        source_label = "📄 文档" if _is_docs_result(source, path) else "📝 源码"
        formatted_result = f"结果 {i} [{source_label}]\n路径: {path}\n内容:\n{content}\n"
        formatted_results.append(formatted_result)

    return "\n---\n".join(formatted_results)


async def get_knowledge_base_status() -> dict:
    """获取知识库状态（只读）"""
    try:
        status = await _get_metadata_status()
    except Exception as e:
        status = {
            "timezone": "UTC",
            "last_updated": "1970-01-01T00:00:00Z",
            "should_skip_update": False,
            "is_stale": True,
            "metadata_available": False,
            "metadata_error": str(e),
        }

    status.update(_get_update_state_snapshot())
    status["data_dir"] = str(config.DATA_DIR)
    status["data_dir_source"] = config.DATA_DIR_SOURCE

    try:
        vector_store = await _run_blocking(VectorStore)
        status["document_count"] = await _run_blocking(vector_store.count_documents)
        status["vector_store_available"] = True
    except Exception as e:
        status["document_count"] = None
        status["vector_store_available"] = False
        status["vector_store_error"] = str(e)

    return status


async def _execute_knowledge_base_update(force: bool = False) -> str:
    """执行知识库更新（内部实现）"""
    if not force and await _should_skip_update():
        return "知识库最近已更新，跳过更新操作。"

    github_loader = GitHubLoader()
    github_docs = await github_loader.load()

    docs_loader = DocsLoader()
    docs_docs = await docs_loader.load()

    all_docs = github_docs + docs_docs

    text_splitter = TextSplitter()
    split_docs = await _run_blocking(text_splitter.split_documents, all_docs)

    vector_store = await _run_blocking(VectorStore)
    await _run_blocking(vector_store.delete_all)
    await _run_blocking(vector_store.add_documents, split_docs)

    await _update_metadata_timestamp()

    return f"知识库更新成功，共添加 {len(split_docs)} 个文档片段。"


async def _run_update(force: bool) -> None:
    """后台执行更新任务并写入内存态状态。"""
    global _UPDATE_TASK
    current_task = asyncio.current_task()

    try:
        result = await asyncio.wait_for(
            _execute_knowledge_base_update(force=force),
            timeout=config.UPDATE_MAX_DURATION_SECONDS,
        )
        _set_update_state(
            status="succeeded",
            finished_at=_now_iso(),
            message=result,
            error=None,
        )
    except TimeoutError:
        _set_update_state(
            status="failed",
            finished_at=_now_iso(),
            message=(
                "知识库更新超时，已自动终止。"
                "请检查 GITHUB_TOKEN / 网络状态后重试。"
            ),
            error="update_timeout",
        )
    except Exception as e:
        _set_update_state(
            status="failed",
            finished_at=_now_iso(),
            message=f"知识库更新失败: {str(e)}",
            error=str(e),
        )
    finally:
        with _STATE_LOCK:
            if _UPDATE_TASK is current_task:
                _UPDATE_TASK = None


async def update_knowledge_base(force: bool = False) -> str:
    """
    非阻塞触发知识库更新。

    Args:
        force: 是否强制更新，强制更新会重新采集所有数据

    Returns:
        任务提交结果或“已有任务执行中”提示
    """
    global _UPDATE_TASK

    with _STATE_LOCK:
        if _UPDATE_TASK is not None and not _UPDATE_TASK.done():
            return "已有更新任务执行中，请稍后重试。"

        started_at = _now_iso()
        _UPDATE_STATE.update(
            {
                "update_status": "running",
                "update_started_at": started_at,
                "update_finished_at": None,
                "update_last_message": "更新任务已提交，正在后台执行。",
                "update_last_error": None,
            }
        )
        _UPDATE_TASK = asyncio.create_task(_run_update(force=force))

    return "更新任务已提交，正在后台执行。"
