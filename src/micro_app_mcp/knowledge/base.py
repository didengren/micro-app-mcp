"""知识处理基类"""

from abc import ABC, abstractmethod

from langchain_core.documents import Document


class BaseLoader(ABC):
    """加载器基类"""

    @abstractmethod
    async def load(self) -> list[Document]:
        """加载文档

        Returns:
            文档列表
        """
        pass


class BaseProcessor(ABC):
    """处理器基类"""

    @abstractmethod
    def process(self, documents: list[Document]) -> list[Document]:
        """处理文档

        Args:
            documents: 文档列表

        Returns:
            处理后的文档列表
        """
        pass
