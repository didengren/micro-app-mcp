"""文本分块"""


from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from micro_app_mcp.knowledge.base import BaseProcessor


class TextSplitter(BaseProcessor):
    """文本分块器"""

    def __init__(self):
        """初始化"""
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=2000,
            chunk_overlap=400,
            length_function=len,
            separators=[
                "\n\n\n",
                "\n\n",
                "\nclass ",
                "\ndef ",
                "\nfunction ",
                "\nconst ",
                "\nlet ",
                "\nvar ",
                "\nimport ",
                "\nfrom ",
                "\n",
                " ",
                ""
            ]
        )

    def process(self, documents: list[Document]) -> list[Document]:
        """处理文档

        Args:
            documents: 文档列表

        Returns:
            处理后的文档列表
        """
        return self.split_documents(documents)

    def split_documents(self, documents: list[Document]) -> list[Document]:
        """分块文档

        Args:
            documents: 文档列表

        Returns:
            分块后的文档列表
        """
        return self.splitter.split_documents(documents)
