"""MCP 工具实现"""

import hashlib

from micro_app_mcp.knowledge.docs_loader import DocsLoader
from micro_app_mcp.knowledge.github_loader import GitHubLoader
from micro_app_mcp.knowledge.text_splitter import TextSplitter
from micro_app_mcp.storage.metadata import MetadataManager
from micro_app_mcp.storage.vector_store import VectorStore

# from micro_app_mcp.config import config


CONCEPT_KEYWORDS = ["是什么", "什么是", "介绍", "原理", "概念", "如何使用", "怎么用", "教程", "文档", "作用", "特点", "优势", "缺点"]
CODE_KEYWORDS = ["代码", "实现", "源码", "示例", "demo", "用法", "调用", "函数", "API", "参数", "返回值", "配置"]


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

    vector_store = VectorStore()
    results = vector_store.search(query, base_top_k * 3)

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
        reverse=True
    )

    # 限制结果数量
    filtered_results = filtered_results[:top_k]

    # 格式化结果
    formatted_results = []
    for i, result in enumerate(filtered_results, 1):
        source = result.metadata.get("source", "unknown")
        path = result.metadata.get("path", "unknown") or result.metadata.get("url", "unknown")
        content = result.page_content[:2000]

        source_label = "📄 文档" if _is_docs_result(source, path) else "📝 源码"
        formatted_result = f"结果 {i} [{source_label}]\n路径: {path}\n内容:\n{content}\n"
        formatted_results.append(formatted_result)

    return "\n---\n".join(formatted_results)


async def get_knowledge_base_status() -> dict:
    """获取知识库状态（只读）"""
    metadata_manager = MetadataManager()
    status = metadata_manager.get_status()
    try:
        vector_store = VectorStore()
        status["document_count"] = vector_store.count_documents()
        status["vector_store_available"] = True
    except Exception as e:
        status["document_count"] = None
        status["vector_store_available"] = False
        status["vector_store_error"] = str(e)
    return status


async def update_knowledge_base(force: bool = False) -> str:
    """
    触发知识库更新。
    
    Args:
        force: 是否强制更新，强制更新会重新采集所有数据
    
    Returns:
        更新结果摘要
    """
    # 初始化元数据管理器
    metadata_manager = MetadataManager()
    
    # 检查是否需要更新
    if not force and metadata_manager.should_skip_update():
        return "知识库最近已更新，跳过更新操作。"
    
    try:
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
        split_docs = text_splitter.split_documents(all_docs)
        
        vector_store = VectorStore()
        # 5. 显式重建索引，避免多次更新累积重复向量
        vector_store.delete_all()

        # 6. 向量化存储文档
        vector_store.add_documents(split_docs)
        
        # 7. 更新元数据
        metadata_manager.update_metadata()
        
        return f"知识库更新成功，共添加 {len(split_docs)} 个文档片段。"
    except Exception as e:
        return f"知识库更新失败: {str(e)}"
