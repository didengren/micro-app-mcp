"""测试 MCP 工具"""

import asyncio
import time

from langchain_core.documents import Document

import micro_app_mcp.app.server as server_module
import micro_app_mcp.app.tools as tools_module


async def _reset_update_runtime() -> None:
    """重置更新任务内存态，避免测试间相互影响。"""
    task = None
    with tools_module._STATE_LOCK:
        task = tools_module._UPDATE_TASK
    if task is not None and not task.done():
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    with tools_module._STATE_LOCK:
        tools_module._UPDATE_TASK = None
        tools_module._UPDATE_STATE.update(
            {
                "update_status": "idle",
                "update_started_at": None,
                "update_finished_at": None,
                "update_last_message": None,
                "update_last_error": None,
            }
        )


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


def test_update_knowledge_base_non_blocking_and_single_flight():
    """更新接口应非阻塞提交，且并发提交只允许单任务运行。"""

    async def fake_execute(force=False):
        await asyncio.sleep(0.08)
        return f"知识库更新成功(force={force})"

    async def run_case():
        await _reset_update_runtime()
        original_execute = tools_module._execute_knowledge_base_update
        tools_module._execute_knowledge_base_update = fake_execute
        try:
            first = await tools_module.update_knowledge_base(force=True)
            second = await tools_module.update_knowledge_base(force=True)
            running_status = await tools_module.get_knowledge_base_status()
            await asyncio.sleep(0.12)
            done_status = await tools_module.get_knowledge_base_status()
            return first, second, running_status, done_status
        finally:
            tools_module._execute_knowledge_base_update = original_execute
            await _reset_update_runtime()

    first, second, running_status, done_status = asyncio.run(run_case())

    assert "已提交" in first
    assert "已有更新任务执行中" in second
    assert running_status["update_status"] == "running"
    assert done_status["update_status"] == "succeeded"
    assert "知识库更新成功" in (done_status.get("update_last_message") or "")


def test_update_knowledge_base_failed_status():
    """后台更新失败时应在状态里可见失败信息。"""

    async def fake_execute(force=False):
        await asyncio.sleep(0.02)
        raise RuntimeError("boom")

    async def run_case():
        await _reset_update_runtime()
        original_execute = tools_module._execute_knowledge_base_update
        tools_module._execute_knowledge_base_update = fake_execute
        try:
            result = await tools_module.update_knowledge_base(force=True)
            await asyncio.sleep(0.06)
            status = await tools_module.get_knowledge_base_status()
            return result, status
        finally:
            tools_module._execute_knowledge_base_update = original_execute
            await _reset_update_runtime()

    result, status = asyncio.run(run_case())

    assert "已提交" in result
    assert status["update_status"] == "failed"
    assert status["update_last_error"] == "boom"


def test_update_knowledge_base_timeout_sets_failed_state():
    """后台更新超时时应落入 failed 且写入 timeout 错误码。"""

    async def fake_execute(force=False):
        await asyncio.sleep(0.08)
        return "ok"

    async def run_case():
        await _reset_update_runtime()
        original_execute = tools_module._execute_knowledge_base_update
        original_timeout = tools_module.config.UPDATE_MAX_DURATION_SECONDS
        tools_module._execute_knowledge_base_update = fake_execute
        tools_module.config.UPDATE_MAX_DURATION_SECONDS = 0.01
        try:
            result = await tools_module.update_knowledge_base(force=True)
            await asyncio.sleep(0.05)
            status = await tools_module.get_knowledge_base_status()
            return result, status
        finally:
            tools_module._execute_knowledge_base_update = original_execute
            tools_module.config.UPDATE_MAX_DURATION_SECONDS = original_timeout
            await _reset_update_runtime()

    result, status = asyncio.run(run_case())

    assert "已提交" in result
    assert status["update_status"] == "failed"
    assert status["update_last_error"] == "update_timeout"
    assert "超时" in (status.get("update_last_message") or "")


def test_micro_command_prefers_update_when_status_and_update_both_present():
    """当状态词与更新词同时存在时，应优先触发更新。"""

    async def fake_update_tool(force=False):
        return {"routed_to": "update", "force": force}

    async def fake_status_tool():
        return {"routed_to": "status"}

    original_update = server_module.update_tool
    original_status = server_module.status_tool
    server_module.update_tool = fake_update_tool
    server_module.status_tool = fake_status_tool
    try:
        micro_command = getattr(
            server_module.micro_app_command, "fn", server_module.micro_app_command
        )
        result = asyncio.run(micro_command("更新知识库状态"))
    finally:
        server_module.update_tool = original_update
        server_module.status_tool = original_status

    assert isinstance(result, dict)
    assert result.get("routed_to") == "update"


def test_micro_command_dispatches_registered_tool_by_name():
    """显式工具名分发应覆盖已注册工具（非硬编码列表）。"""

    async def fake_status_tool():
        return {"ok": True}

    original_status = server_module.status_tool
    server_module.status_tool = fake_status_tool
    try:
        micro_command = getattr(
            server_module.micro_app_command, "fn", server_module.micro_app_command
        )
        result = asyncio.run(micro_command("get_knowledge_base_status"))
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


def test_get_knowledge_base_status_contains_data_dir_and_update_fields():
    """知识库状态应暴露 data_dir/data_dir_source 与更新状态字段。"""

    class FakeVectorStore:
        def count_documents(self):
            return 12

    async def fake_metadata_status():
        return {"timezone": "UTC", "last_updated": "2026-01-01T00:00:00Z"}

    original_vector_store = tools_module.VectorStore
    original_get_status = tools_module._get_metadata_status
    tools_module.VectorStore = FakeVectorStore
    tools_module._get_metadata_status = fake_metadata_status

    with tools_module._STATE_LOCK:
        tools_module._UPDATE_STATE.update(
            {
                "update_status": "running",
                "update_started_at": "2026-01-01T00:00:10Z",
                "update_finished_at": None,
                "update_last_message": "running",
                "update_last_error": None,
            }
        )

    try:
        status = asyncio.run(tools_module.get_knowledge_base_status())
    finally:
        tools_module.VectorStore = original_vector_store
        tools_module._get_metadata_status = original_get_status
        asyncio.run(_reset_update_runtime())

    assert "data_dir" in status
    assert "data_dir_source" in status
    assert status["document_count"] == 12
    assert status["update_status"] == "running"
    assert "update_started_at" in status
    assert "update_finished_at" in status
    assert "update_last_message" in status
    assert "update_last_error" in status
