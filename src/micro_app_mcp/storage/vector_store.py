"""ChromaDB 封装"""

import logging

from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from micro_app_mcp.config import config
from micro_app_mcp.knowledge.vectorizer import Vectorizer

logging.getLogger("chromadb.telemetry.product.posthog").setLevel(logging.WARNING)


class VectorStore:
    """向量存储"""

    def __init__(self):
        """初始化"""
        # 初始化向量化器
        self.vectorizer = Vectorizer()

        # 初始化 ChromaDB
        self.db = Chroma(
            collection_name="micro_app_knowledge",
            embedding_function=self.vectorizer.embeddings,
            persist_directory=str(config.CHROMA_DB_PATH),
            client_settings=Settings(
                anonymized_telemetry=config.CHROMA_ANONYMIZED_TELEMETRY
            ),
        )

    def add_documents(self, documents: list[Document]) -> list[str]:
        """添加文档

        Args:
            documents: 文档列表

        Returns:
            文档 ID 列表
        """
        return self.db.add_documents(documents)

    def search(self, query: str, k: int = 5) -> list[Document]:
        """搜索文档

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            文档列表
        """
        results = self.db.similarity_search(query, k=k)
        return results

    def delete_all(self):
        """删除所有文档"""
        self.db.delete_collection()
        # 重新初始化
        self.db = Chroma(
            collection_name="micro_app_knowledge",
            embedding_function=self.vectorizer.embeddings,
            persist_directory=str(config.CHROMA_DB_PATH),
            client_settings=Settings(
                anonymized_telemetry=config.CHROMA_ANONYMIZED_TELEMETRY
            ),
        )

    def count_documents(self) -> int:
        """统计向量库中文档数量"""
        try:
            return int(self.db._collection.count())
        except Exception:
            return 0
