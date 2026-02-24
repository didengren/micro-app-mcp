"""测试知识处理功能"""

import asyncio
import concurrent.futures
import threading
import time
from types import SimpleNamespace

from github import RateLimitExceededException
from langchain_core.documents import Document
from micro_app_mcp.knowledge.docs_loader import DocsLoader
from micro_app_mcp.knowledge.github_loader import GitHubLoader
from micro_app_mcp.knowledge.text_splitter import TextSplitter
from micro_app_mcp.knowledge.vectorizer import Vectorizer


def test_github_loader():
    """测试 GitHub 加载器（mock 仓库结构，无外网依赖）"""

    class FakeRepo:
        def get_branch(self, _branch_name):
            return SimpleNamespace(commit=SimpleNamespace(sha="test-sha"))

        def get_contents(self, path, ref=None):
            if path == "":
                return [
                    SimpleNamespace(
                        type="file",
                        path="README.md",
                        decoded_content=b"# mock readme",
                        html_url="https://example.com/readme",
                        sha="sha-readme",
                    ),
                    SimpleNamespace(type="dir", path="src"),
                ]
            if path == "src":
                return [
                    SimpleNamespace(
                        type="file",
                        path="src/index.ts",
                        decoded_content=b"export const x = 1;",
                        html_url="https://example.com/src-index",
                        sha="sha-index",
                    ),
                    # 非代码文件应被过滤
                    SimpleNamespace(
                        type="file",
                        path="src/logo.png",
                        decoded_content=b"png",
                        html_url="https://example.com/src-logo",
                        sha="sha-logo",
                    ),
                ]
            return []

    loader = GitHubLoader.__new__(GitHubLoader)
    loader.repo = FakeRepo()
    docs = asyncio.run(loader.load())
    assert isinstance(docs, list)
    assert len(docs) == 2
    assert all(doc.metadata["source"] == "github" for doc in docs)


def test_docs_loader():
    """测试文档加载器（mock Playwright，无浏览器依赖）"""

    class FakeAsyncLoader:
        async def aload(self):
            return [Document(page_content="<h1>mock docs</h1>", metadata={})]

    class FakeTransformer:
        def transform_documents(self, docs):
            return [Document(page_content="mock docs", metadata=doc.metadata) for doc in docs]

    loader = DocsLoader.__new__(DocsLoader)
    loader.loader = FakeAsyncLoader()
    loader.transformer = FakeTransformer()
    docs = asyncio.run(loader.load())
    assert isinstance(docs, list)
    assert len(docs) == 1
    assert docs[0].metadata["source"] == "docs"
    assert "path" in docs[0].metadata


def test_text_splitter():
    """测试文本分块器"""
    from langchain_core.documents import Document

    # 创建测试文档
    test_doc = Document(page_content="""这是一个测试文档，用于测试文本分块功能。""")

    splitter = TextSplitter()
    split_docs = splitter.split_documents([test_doc])
    assert isinstance(split_docs, list)
    assert len(split_docs) > 0


def test_vectorizer():
    """测试向量化器（mock embedding，无模型依赖）"""
    import micro_app_mcp.knowledge.vectorizer as vectorizer_module

    class FakeEmbeddings:
        def embed_query(self, _query):
            return [0.1, 0.2, 0.3]

        def embed_documents(self, docs):
            return [[float(i), float(i + 1)] for i, _ in enumerate(docs)]

    vectorizer_module._cached_embedder = None
    original_get_embedder = vectorizer_module.get_embedder
    vectorizer_module.get_embedder = lambda lazy=None: FakeEmbeddings()
    vectorizer = Vectorizer()

    try:
        query_embedding = vectorizer.embed_query("如何使用 micro-app")
        assert isinstance(query_embedding, list)
        assert len(query_embedding) > 0

        docs_embedding = vectorizer.embed_documents(["测试文档 1", "测试文档 2"])
        assert isinstance(docs_embedding, list)
        assert len(docs_embedding) == 2
    finally:
        vectorizer_module.get_embedder = original_get_embedder
        vectorizer_module._cached_embedder = None


def test_github_loader_does_not_block_event_loop():
    """GitHubLoader.load 应通过 to_thread 执行同步逻辑，不阻塞事件循环。"""

    loader = GitHubLoader.__new__(GitHubLoader)

    def fake_load_sync():
        time.sleep(0.08)
        return [Document(page_content="mock", metadata={"source": "github"})]

    loader._load_sync = fake_load_sync

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
            docs = await loader.load()
        finally:
            stop.set()
            await hb
        return docs, tick

    docs, tick = asyncio.run(run_case())
    assert len(docs) == 1
    assert tick > 3


def test_lazy_embedder_loads_model_once_under_concurrency():
    """并发调用 embed_query 时，LazyEmbedder 只应实例化一次底层模型。"""
    import micro_app_mcp.knowledge.vectorizer as vectorizer_module

    counter = {"count": 0}
    counter_lock = threading.Lock()

    class FakeHFEmbeddings:
        def __init__(self, *args, **kwargs):
            with counter_lock:
                counter["count"] += 1
            time.sleep(0.05)

        def embed_query(self, _text):
            return [1.0, 2.0]

        def embed_documents(self, docs):
            return [[float(i)] for i, _ in enumerate(docs)]

    original_hf = vectorizer_module.HuggingFaceEmbeddings
    vectorizer_module.HuggingFaceEmbeddings = FakeHFEmbeddings
    lazy = vectorizer_module.LazyEmbedder(
        model_name="mock-model",
        model_kwargs={},
        encode_kwargs={},
    )

    def call_embed():
        return lazy.embed_query("x")

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(call_embed) for _ in range(8)]
            results = [f.result() for f in futures]
    finally:
        vectorizer_module.HuggingFaceEmbeddings = original_hf

    assert all(r == [1.0, 2.0] for r in results)
    assert counter["count"] == 1


def test_github_loader_rate_limit_should_fail_fast():
    """GitHub 限流异常应快速转换为可读错误，不做长退避。"""

    class FakeRepo:
        def get_branch(self, _branch_name):
            raise RateLimitExceededException(
                403, {"message": "rate limit exceeded"}, None
            )

    loader = GitHubLoader.__new__(GitHubLoader)
    loader.repo = FakeRepo()

    try:
        loader._load_sync()
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "限流" in str(e)
