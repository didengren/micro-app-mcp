"""测试 MCP 工具"""

import asyncio
from datetime import datetime, timedelta, timezone
import time

from langchain_core.documents import Document

import micro_app_mcp.app.server as server_module
import micro_app_mcp.app.tools as tools_module


def test_search_micro_app_knowledge():
    """测试搜索工具（mock 向量库，无模型依赖）"""

    class FakeVectorStore:
        def search(self, _query, _k):
            return [
                Document(
                    page_content="文档内容",
                    metadata={"source": "docs", "path": "docs/intro.md"},
                ),
                Document(
                    page_content="源码内容",
                    metadata={"source": "github", "path": "src/index.ts"},
                ),
            ]

    original_vector_store = tools_module.VectorStore
    tools_module.VectorStore = FakeVectorStore
    try:
        result = asyncio.run(tools_module.search_micro_app_knowledge("如何使用 micro-app"))
    finally:
        tools_module.VectorStore = original_vector_store

    assert isinstance(result, str)
    assert "📄 文档" in result
    assert "📝 源码" in result


def test_update_knowledge_base():
    """测试更新工具（mock 更新执行，无外网依赖）"""

    async def fake_execute(force=False):
        return f"知识库更新成功(force={force})"

    original_execute = tools_module._execute_knowledge_base_update
    tools_module._execute_knowledge_base_update = fake_execute
    try:
        result = asyncio.run(tools_module.update_knowledge_base(force=True, blocking=True))
    finally:
        tools_module._execute_knowledge_base_update = original_execute

    assert isinstance(result, str)
    assert "知识库更新成功" in result


def test_micro_command_prefers_update_when_status_and_update_both_present():
    """当状态词与更新词同时存在时，应优先触发更新。"""

    async def fake_submit_update_tool(force=False):
        return {"routed_to": "update", "force": force}

    async def fake_status_tool():
        return {"routed_to": "status"}

    original_submit = server_module.submit_update_tool
    original_status = server_module.status_tool
    server_module.submit_update_tool = fake_submit_update_tool
    server_module.status_tool = fake_status_tool
    try:
        result = asyncio.run(server_module.micro_app_command.fn("更新知识库状态"))
    finally:
        server_module.submit_update_tool = original_submit
        server_module.status_tool = original_status

    assert isinstance(result, dict)
    assert result.get("routed_to") == "update"


def test_get_update_job_falls_back_to_memory_when_metadata_unavailable():
    """持久化层异常时，任务查询应回退到内存缓存。"""

    async def boom(_job_id):
        raise RuntimeError("metadata unavailable")

    original_get_persisted = tools_module._get_persisted_update_job
    tools_module._get_persisted_update_job = boom
    tools_module.UPDATE_JOBS["job-memory"] = {
        "job_id": "job-memory",
        "status": "running",
        "message": "in-memory",
        "created_at": "2099-01-01T00:00:00Z",
    }
    try:
        result = asyncio.run(tools_module.get_update_knowledge_base_job("job-memory"))
    finally:
        tools_module._get_persisted_update_job = original_get_persisted
        tools_module.UPDATE_JOBS.pop("job-memory", None)

    assert isinstance(result, dict)
    assert result.get("job_id") == "job-memory"
    assert result.get("status") == "running"


def test_update_jobs_in_memory_trimmed_by_max_records():
    """内存任务池应按最大条数裁剪，避免无限增长。"""
    now = datetime.now(timezone.utc)
    original_max = tools_module.config.UPDATE_JOB_MAX_RECORDS
    original_hours = tools_module.config.UPDATE_JOB_RETENTION_HOURS
    tools_module.config.UPDATE_JOB_MAX_RECORDS = 3
    tools_module.config.UPDATE_JOB_RETENTION_HOURS = 999

    async def run_case():
        async with tools_module._get_update_submit_lock():
            tools_module.UPDATE_JOBS.clear()
            for idx in range(6):
                created = (now - timedelta(minutes=idx)).isoformat().replace("+00:00", "Z")
                tools_module.UPDATE_JOBS[f"job-{idx}"] = {
                    "job_id": f"job-{idx}",
                    "status": "succeeded",
                    "created_at": created,
                }
            tools_module._trim_update_jobs_in_memory_unlocked()
            return sorted(tools_module.UPDATE_JOBS.keys())

    try:
        keys = asyncio.run(run_case())
    finally:
        tools_module.config.UPDATE_JOB_MAX_RECORDS = original_max
        tools_module.config.UPDATE_JOB_RETENTION_HOURS = original_hours
        tools_module.UPDATE_JOBS.clear()

    assert len(keys) == 3
    assert keys == ["job-0", "job-1", "job-2"]


def test_micro_command_dispatches_registered_tool_by_name():
    """显式工具名分发应覆盖已注册工具（非硬编码列表）。"""

    async def fake_status_tool():
        return {"ok": True}

    original_status = server_module.status_tool
    server_module.status_tool = fake_status_tool
    try:
        result = asyncio.run(server_module.micro_app_command.fn("get_knowledge_base_status"))
    finally:
        server_module.status_tool = original_status

    assert result == {"ok": True}


def test_search_micro_app_knowledge_timeout_returns_readable_message():
    """检索超时时应返回可读提示，不抛异常。"""

    class SlowVectorStore:
        def search(self, _query, _k):
            time.sleep(0.2)
            return []

    original_vector_store = tools_module.VectorStore
    original_timeout = tools_module.config.SEARCH_TIMEOUT_SECONDS
    tools_module.VectorStore = SlowVectorStore
    tools_module.config.SEARCH_TIMEOUT_SECONDS = 0.01
    try:
        result = asyncio.run(tools_module.search_micro_app_knowledge("micro-app 是什么"))
    finally:
        tools_module.VectorStore = original_vector_store
        tools_module.config.SEARCH_TIMEOUT_SECONDS = original_timeout

    assert isinstance(result, str)
    assert "冷启动" in result
    assert "稍后重试" in result


def test_search_micro_app_knowledge_does_not_block_event_loop():
    """搜索中的阻塞查询应在线程执行，不阻塞事件循环心跳。"""

    class SlowVectorStore:
        def search(self, _query, _k):
            time.sleep(0.08)
            return [
                Document(
                    page_content="文档内容",
                    metadata={"source": "docs", "path": "docs/intro.md"},
                )
            ]

    original_vector_store = tools_module.VectorStore
    tools_module.VectorStore = SlowVectorStore

    async def run_case():
        tick = 0
        stop = asyncio.Event()

        async def heartbeat():
            nonlocal tick
            while not stop.is_set():
                tick += 1
                await asyncio.sleep(0.005)

        hb = asyncio.create_task(heartbeat())
        try:
            result = await tools_module.search_micro_app_knowledge("如何使用 micro-app", top_k=1)
        finally:
            stop.set()
            await hb
        return result, tick

    try:
        result, tick = asyncio.run(run_case())
    finally:
        tools_module.VectorStore = original_vector_store

    assert "📄 文档" in result
    assert tick > 3


def test_get_knowledge_base_status_contains_data_dir_fields():
    """知识库状态应暴露 data_dir 与 data_dir_source。"""

    class FakeVectorStore:
        def count_documents(self):
            return 12

    async def fake_metadata_status():
        return {"timezone": "UTC", "last_updated": "2026-01-01T00:00:00Z"}

    original_vector_store = tools_module.VectorStore
    original_get_status = tools_module._get_metadata_status
    tools_module.VectorStore = FakeVectorStore
    tools_module._get_metadata_status = fake_metadata_status
    try:
        status = asyncio.run(tools_module.get_knowledge_base_status())
    finally:
        tools_module.VectorStore = original_vector_store
        tools_module._get_metadata_status = original_get_status

    assert "data_dir" in status
    assert "data_dir_source" in status
    assert status["document_count"] == 12
