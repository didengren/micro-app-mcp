"""测试知识处理功能"""

import pytest

from micro_app_mcp.knowledge.docs_loader import DocsLoader
from micro_app_mcp.knowledge.github_loader import GitHubLoader
from micro_app_mcp.knowledge.text_splitter import TextSplitter
from micro_app_mcp.knowledge.vectorizer import Vectorizer


@pytest.mark.asyncio
async def test_github_loader():
    """测试 GitHub 加载器"""
    loader = GitHubLoader()
    docs = await loader.load()
    assert isinstance(docs, list)
    # 至少应该加载到一些文档
    assert len(docs) > 0


@pytest.mark.asyncio
async def test_docs_loader():
    """测试文档加载器"""
    loader = DocsLoader()
    docs = await loader.load()
    assert isinstance(docs, list)
    # 至少应该加载到一些文档
    assert len(docs) > 0


@pytest.mark.asyncio
async def test_text_splitter():
    """测试文本分块器"""
    from langchain_core.documents import Document

    # 创建测试文档
    test_doc = Document(page_content="""这是一个测试文档，用于测试文本分块功能。""")

    splitter = TextSplitter()
    split_docs = splitter.split_documents([test_doc])
    assert isinstance(split_docs, list)
    assert len(split_docs) > 0


@pytest.mark.asyncio
async def test_vectorizer():
    """测试向量化器"""
    vectorizer = Vectorizer()

    # 测试嵌入查询
    query_embedding = vectorizer.embed_query("如何使用 micro-app")
    assert isinstance(query_embedding, list)
    assert len(query_embedding) > 0

    # 测试嵌入文档
    docs_embedding = vectorizer.embed_documents(["测试文档 1", "测试文档 2"])
    assert isinstance(docs_embedding, list)
    assert len(docs_embedding) == 2
