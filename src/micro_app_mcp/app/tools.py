"""MCP 工具实现"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta, timezone
from functools import partial
from typing import Any, Dict
from uuid import uuid4

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
UPDATE_JOBS: Dict[str, Dict[str, Any]] = {}
_METADATA_MANAGER: MetadataManager | None = None
_UPDATE_SUBMIT_LOCK: asyncio.Lock | None = None
_UPDATE_SUBMIT_LOCK_LOOP: asyncio.AbstractEventLoop | None = None
_ACTIVE_UPDATE_RUNNING = False
_ACTIVE_UPDATE_JOB_ID: str | None = None
logger = logging.getLogger(__name__)


def _get_metadata_manager() -> MetadataManager:
    """惰性获取 MetadataManager，避免导入期触发文件 I/O。"""
    global _METADATA_MANAGER
    if _METADATA_MANAGER is None:
        _METADATA_MANAGER = MetadataManager()
    return _METADATA_MANAGER


def _get_update_submit_lock() -> asyncio.Lock:
    """按当前事件循环惰性创建锁，避免跨 loop 复用报错。"""
    global _UPDATE_SUBMIT_LOCK, _UPDATE_SUBMIT_LOCK_LOOP
    loop = asyncio.get_running_loop()
    if _UPDATE_SUBMIT_LOCK is None or _UPDATE_SUBMIT_LOCK_LOOP is not loop:
        _UPDATE_SUBMIT_LOCK = asyncio.Lock()
        _UPDATE_SUBMIT_LOCK_LOOP = loop
    return _UPDATE_SUBMIT_LOCK


async def _run_blocking(func, *args, **kwargs):
    """在线程池中执行同步阻塞函数。"""
    return await asyncio.to_thread(partial(func, *args, **kwargs))


def _now_iso() -> str:
    """返回 UTC ISO8601 时间字符串"""
    return (
        datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    )


async def _should_skip_update() -> bool:
    """在后台线程中判断是否应跳过更新"""
    manager = _get_metadata_manager()
    return await asyncio.to_thread(manager.should_skip_update)


async def _update_metadata_timestamp() -> None:
    """在后台线程中更新时间元数据"""
    manager = _get_metadata_manager()
    await asyncio.to_thread(manager.update_metadata)


async def _save_update_job(job: Dict[str, Any]) -> None:
    """在后台线程中持久化任务状态"""
    manager = _get_metadata_manager()
    await asyncio.to_thread(manager.save_update_job, job)


async def _get_persisted_update_job(job_id: str) -> Dict[str, Any] | None:
    """在后台线程中查询持久化任务状态"""
    manager = _get_metadata_manager()
    return await asyncio.to_thread(manager.get_update_job, job_id)


async def _get_metadata_status() -> Dict[str, Any]:
    """在后台线程中读取知识库元数据状态"""
    manager = _get_metadata_manager()
    return await asyncio.to_thread(manager.get_status)


def _get_active_job_snapshot_unlocked() -> Dict[str, Any] | None:
    """读取当前活跃任务快照（调用方需先持有 _UPDATE_SUBMIT_LOCK）。"""
    if _ACTIVE_UPDATE_JOB_ID is None:
        return None
    job = UPDATE_JOBS.get(_ACTIVE_UPDATE_JOB_ID)
    if job is None:
        return None
    if job.get("status") in {"queued", "running"}:
        return job.copy()
    return None


async def _safe_persist_job(job: Dict[str, Any]) -> None:
    """最佳努力持久化，不因落盘失败中断主流程。"""
    try:
        await _save_update_job(job)
    except Exception as e:  # pragma: no cover - 持久化失败仅记录日志
        logger.warning("持久化更新任务失败(job_id=%s): %s", job.get("job_id"), e)


def _parse_utc_datetime(value: str | None) -> datetime:
    """解析 UTC 时间字符串，异常时回退 epoch。"""
    if not value:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)
    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


def _trim_update_jobs_in_memory_unlocked() -> None:
    """裁剪内存中的 UPDATE_JOBS，避免长期运行内存无限增长。"""
    if not UPDATE_JOBS:
        return

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=config.UPDATE_JOB_RETENTION_HOURS)
    active_statuses = {"queued", "running"}
    active_jobs: dict[str, dict[str, Any]] = {}
    finished_jobs: list[tuple[str, dict[str, Any], datetime]] = []

    for job_id, job in UPDATE_JOBS.items():
        status = str(job.get("status", ""))
        created_at = _parse_utc_datetime(job.get("created_at"))
        if status in active_statuses:
            active_jobs[job_id] = job
            continue
        if created_at >= cutoff:
            finished_jobs.append((job_id, job, created_at))

    finished_jobs.sort(key=lambda item: item[2], reverse=True)
    remaining_slots = max(config.UPDATE_JOB_MAX_RECORDS - len(active_jobs), 0)
    kept_finished = finished_jobs[:remaining_slots]

    UPDATE_JOBS.clear()
    UPDATE_JOBS.update(active_jobs)
    for job_id, job, _ in kept_finished:
        UPDATE_JOBS[job_id] = job


def detect_query_type(query: str) -> str:
    """检测查询类型：概念理解 / 代码实现 / 快速定位"""
    query_lower = query.lower()
    concept_score = sum(1 for kw in CONCEPT_KEYWORDS if kw in query_lower)
    code_score = sum(1 for kw in CODE_KEYWORDS if kw in query_lower)

    if concept_score > code_score:
        return "concept"
    elif code_score > concept_score:
        return "code"
    else:
        return "hybrid"


def _is_docs_result(source: str, path: str) -> bool:
    """判断结果是否应视为文档"""
    normalized_path = path.lower()
    return source == "docs" or normalized_path.startswith("docs/")


def _build_dedup_key(source: str, path: str, content: str):
    """构建去重键

    docs 结果按内容粒度去重，避免单一 path 导致文档片段被大量压缩。

    去重策略总结：
    | 类型 | 去重键 | 说明 |
    |------|-------|------|
    | 文档 | (source, path, content_hash) | 相同路径 + 相同内容才去重 |
    | 有路径 | (source, path) | 相同路径去重 |
    | 无路径 | (source, content_hash) | 相同内容去重 |
    """
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
    # 检测查询类型
    query_type = detect_query_type(query)

    # 根据查询类型设置基础 top_k 和源优先级
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
    except asyncio.TimeoutError:
        return (
            "向量模型正在冷启动，本次检索已超时保护返回。"
            "请稍后重试（建议30-60秒后）。"
        )

    seen_paths = set()
    filtered_results = []

    # 去重
    for result in results:
        source = result.metadata.get("source", "unknown")
        path = result.metadata.get("path", "") or result.metadata.get("url", "")
        dedup_key = _build_dedup_key(source, path, result.page_content)
        if dedup_key in seen_paths:
            continue
        seen_paths.add(dedup_key)
        filtered_results.append(result)

    # 排序
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

    # 限制结果数量
    filtered_results = filtered_results[:top_k]

    # 格式化结果
    formatted_results = []
    for i, result in enumerate(filtered_results, 1):
        source = result.metadata.get("source", "unknown")
        path = result.metadata.get("path", "unknown") or result.metadata.get(
            "url", "unknown"
        )
        content = result.page_content[:2000]

        source_label = "📄 文档" if _is_docs_result(source, path) else "📝 源码"
        formatted_result = (
            f"结果 {i} [{source_label}]\n路径: {path}\n内容:\n{content}\n"
        )
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
    # 检查是否需要更新
    if not force and await _should_skip_update():
        return "知识库最近已更新，跳过更新操作。"

    # 1. 采集 GitHub 源码
    github_loader = GitHubLoader()
    github_docs = await github_loader.load()

    # 2. 采集文档
    docs_loader = DocsLoader()
    docs_docs = await docs_loader.load()

    # 3. 合并文档
    all_docs = github_docs + docs_docs

    # 4. 文本分块
    text_splitter = TextSplitter()
    split_docs = await _run_blocking(text_splitter.split_documents, all_docs)

    vector_store = await _run_blocking(VectorStore)
    # 5. 显式重建索引，避免多次更新累积重复向量
    await _run_blocking(vector_store.delete_all)

    # 6. 向量化存储文档
    await _run_blocking(vector_store.add_documents, split_docs)

    # 7. 更新元数据
    await _update_metadata_timestamp()

    return f"知识库更新成功，共添加 {len(split_docs)} 个文档片段。"


async def _run_update_job(job_id: str, force: bool) -> None:
    """后台执行更新任务"""
    job = UPDATE_JOBS.get(job_id)
    if job is None:
        return
    job["status"] = "running"
    job["started_at"] = _now_iso()
    await _safe_persist_job(job)

    try:
        result = await _execute_knowledge_base_update(force=force)
        job["status"] = "succeeded"
        job["message"] = result
    except Exception as e:
        job["status"] = "failed"
        job["message"] = f"知识库更新失败: {str(e)}"
        job["error"] = str(e)
    finally:
        job["finished_at"] = _now_iso()
        await _safe_persist_job(job)
        global _ACTIVE_UPDATE_RUNNING, _ACTIVE_UPDATE_JOB_ID
        async with _get_update_submit_lock():
            _ACTIVE_UPDATE_RUNNING = False
            if _ACTIVE_UPDATE_JOB_ID == job_id:
                _ACTIVE_UPDATE_JOB_ID = None
            _trim_update_jobs_in_memory_unlocked()


async def submit_update_knowledge_base(force: bool = False) -> dict:
    """提交知识库后台更新任务"""
    global _ACTIVE_UPDATE_RUNNING, _ACTIVE_UPDATE_JOB_ID

    async with _get_update_submit_lock():
        if _ACTIVE_UPDATE_RUNNING:
            active_job = _get_active_job_snapshot_unlocked()
            if active_job is not None:
                active_job["message"] = (
                    f"已有更新任务执行中，请复用 job_id={active_job['job_id']} 查询进度。"
                )
                return active_job
            return {
                "job_id": None,
                "type": "update_knowledge_base",
                "status": "running",
                "force": force,
                "message": "已有更新任务执行中，请稍后重试。",
                "error": None,
            }

    job_id = uuid4().hex
    job = {
        "job_id": job_id,
        "type": "update_knowledge_base",
        "status": "queued",
        "force": force,
        "created_at": _now_iso(),
        "started_at": None,
        "finished_at": None,
        "message": "更新任务已提交，正在排队执行。",
        "error": None,
    }
    async with _get_update_submit_lock():
        UPDATE_JOBS[job_id] = job
        _ACTIVE_UPDATE_RUNNING = True
        _ACTIVE_UPDATE_JOB_ID = job_id
        _trim_update_jobs_in_memory_unlocked()

    await _safe_persist_job(job)
    asyncio.create_task(_run_update_job(job_id, force))
    return job.copy()


async def get_update_knowledge_base_job(job_id: str) -> dict:
    """查询更新任务状态"""
    persisted = None
    try:
        persisted = await _get_persisted_update_job(job_id)
    except Exception as e:
        logger.warning("读取持久化任务状态失败(job_id=%s): %s", job_id, e)

    if persisted is not None:
        async with _get_update_submit_lock():
            UPDATE_JOBS[job_id] = persisted
            _trim_update_jobs_in_memory_unlocked()
            job = UPDATE_JOBS.get(job_id)
    else:
        async with _get_update_submit_lock():
            _trim_update_jobs_in_memory_unlocked()
            job = UPDATE_JOBS.get(job_id)

    if job is None:
        # 再次回退到内存，避免极端并发下刚好被裁剪后误判。
        job = UPDATE_JOBS.get(job_id)

    if job is None:
        return {
            "job_id": job_id,
            "status": "not_found",
            "message": "任务不存在或已过期。",
        }
    return job.copy()


async def update_knowledge_base(force: bool = False, blocking: bool = False) -> str:
    """
    触发知识库更新。

    Args:
        force: 是否强制更新，强制更新会重新采集所有数据
        blocking: 是否阻塞等待更新完成，默认 False（推荐）

    Returns:
        非阻塞模式下返回任务提交结果；阻塞模式下返回更新结果摘要
    """
    if not blocking:
        job = await submit_update_knowledge_base(force=force)
        if job.get("job_id") is None:
            return job.get("message", "已有更新任务执行中，请稍后重试。")
        return (
            f"更新任务已提交，job_id={job['job_id']}。"
            "请调用 get_update_knowledge_base_job 查询进度。"
        )

    global _ACTIVE_UPDATE_RUNNING, _ACTIVE_UPDATE_JOB_ID
    async with _get_update_submit_lock():
        if _ACTIVE_UPDATE_RUNNING:
            active_job = _get_active_job_snapshot_unlocked()
            if active_job is not None:
                return f"已有更新任务执行中，请复用 job_id={active_job['job_id']} 查询进度。"
            return "已有更新任务执行中，请稍后重试。"
        _ACTIVE_UPDATE_RUNNING = True
        _ACTIVE_UPDATE_JOB_ID = None

    try:
        return await _execute_knowledge_base_update(force=force)
    except Exception as e:
        return f"知识库更新失败: {str(e)}"
    finally:
        async with _get_update_submit_lock():
            _ACTIVE_UPDATE_RUNNING = False
            _ACTIVE_UPDATE_JOB_ID = None
