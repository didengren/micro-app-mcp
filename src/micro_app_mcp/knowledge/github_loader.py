"""GitHub 源码采集"""

import asyncio
import logging
from typing import List

from github import Github
from langchain_core.documents import Document

from micro_app_mcp.config import config
from micro_app_mcp.knowledge.base import BaseLoader

logger = logging.getLogger(__name__)


class GitHubLoader(BaseLoader):
    """GitHub 源码加载器"""
    
    def __init__(self):
        """初始化"""
        # 初始化 GitHub 客户端
        self.github = Github(config.GITHUB_TOKEN) if config.GITHUB_TOKEN else Github()
        self.repo = self.github.get_repo(config.GITHUB_REPO)
    
    def _load_sync(self) -> List[Document]:
        """同步加载 GitHub 源码。"""
        documents = []

        # 获取指定分支
        branch = self.repo.get_branch(config.GITHUB_BRANCH)

        # 获取仓库根目录
        root = self.repo.get_contents("", ref=branch.commit.sha)

        # 递归获取文件
        def process_contents(contents, path=""):
            for item in contents:
                if item.type == "file":
                    # 只处理代码文件
                    if item.path.endswith((".js", ".ts", ".tsx", ".jsx", ".md", ".json")):
                        try:
                            # 获取文件内容
                            content = item.decoded_content.decode("utf-8")
                            
                            # 创建文档
                            doc = Document(
                                page_content=content,
                                metadata={
                                    "source": "github",
                                    "path": item.path,
                                    "url": item.html_url,
                                    "sha": item.sha
                                }
                            )
                            documents.append(doc)
                        except Exception as e:
                            logger.warning("处理文件 %s 时出错: %s", item.path, e)
                elif item.type == "dir":
                    # 递归处理子目录
                    sub_contents = self.repo.get_contents(item.path, ref=branch.commit.sha)
                    process_contents(sub_contents, item.path)

        # 处理所有文件
        process_contents(root)

        return documents

    async def load(self) -> List[Document]:
        """加载 GitHub 源码

        Returns:
            文档列表
        """
        return await asyncio.to_thread(self._load_sync)
