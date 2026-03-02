"""文档采集 (Playwright)"""


from langchain_community.document_loaders import AsyncChromiumLoader
from langchain_community.document_transformers import Html2TextTransformer
from langchain_core.documents import Document

from micro_app_mcp.config import config
from micro_app_mcp.knowledge.base import BaseLoader


class DocsLoader(BaseLoader):
    """文档加载器"""

    def __init__(self):
        """初始化"""
        # 初始化加载器
        self.loader = AsyncChromiumLoader([config.DOCS_URL])
        self.transformer = Html2TextTransformer()

    async def load(self) -> list[Document]:
        """加载文档

        Returns:
            文档列表
        """
        # 加载 HTML
        docs = await self.loader.aload()

        # 转换为文本
        transformed_docs = list(self.transformer.transform_documents(docs))

        # 添加元数据
        for doc in transformed_docs:
            doc.metadata["source"] = "docs"
            doc.metadata["url"] = config.DOCS_URL
            doc.metadata["path"] = doc.metadata.get("path") or config.DOCS_URL

        return transformed_docs
