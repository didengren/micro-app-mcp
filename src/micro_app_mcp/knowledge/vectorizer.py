"""向量化处理"""

import sys
from typing import List, Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_core.embeddings import Embeddings

from micro_app_mcp.config import config

_cached_embedder: Optional[Embeddings] = None


def get_embedder(lazy: Optional[bool] = None) -> Embeddings:
    """获取嵌入模型（支持全局缓存）
    
    Args:
        lazy: 是否懒加载，默认使用 config.EMBEDDING_LAZY_LOAD
        
    Returns:
        嵌入模型实例
    """
    global _cached_embedder
    
    if _cached_embedder is not None:
        return _cached_embedder
    
    if lazy is None:
        lazy = config.EMBEDDING_LAZY_LOAD
    
    if config.EMBEDDING_MODEL == "local":
        if lazy:
            _cached_embedder = LazyEmbedder(
                model_name=config.EMBEDDING_MODEL_NAME,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True}
            )
        else:
            _cached_embedder = HuggingFaceEmbeddings(
                model_name=config.EMBEDDING_MODEL_NAME,
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True}
            )
    elif config.EMBEDDING_MODEL == "api":
        raise NotImplementedError("API模式尚未实现")
    else:
        raise ValueError(f"不支持的嵌入模型: {config.EMBEDDING_MODEL}")
    
    return _cached_embedder


class LazyEmbedder(Embeddings):
    """懒加载嵌入器 - 延迟加载模型直到真正需要"""

    def __init__(self, model_name: str, model_kwargs: dict, encode_kwargs: dict):
        self.model_name = model_name
        self.model_kwargs = model_kwargs
        self.encode_kwargs = encode_kwargs
        self._inner = None
        self._loaded = False

    def _ensure_loaded(self):
        if self._inner is None:
            print("\n" + "=" * 50)
            print("⏳ 首次检索，正在加载向量模型...")
            print(f"   模型: {self.model_name}")
            print("   首次加载可能需要 10-30 秒，请耐心等待...")
            print("=" * 50 + "\n")
            sys.stdout.flush()
            self._inner = HuggingFaceEmbeddings(
                model_name=self.model_name,
                model_kwargs=self.model_kwargs,
                encode_kwargs=self.encode_kwargs
            )
            self._loaded = True
            print("✅ 向量模型加载完成！")
            sys.stdout.flush()
        return self._inner

    @property
    def model(self):
        return self._ensure_loaded()

    def embed_query(self, text: str) -> List[float]:
        return self._ensure_loaded().embed_query(text)

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        return self._ensure_loaded().embed_documents(documents)

    def __repr__(self):
        if self._loaded:
            return f"LazyEmbedder(model={self.model_name}, loaded=True)"
        return f"LazyEmbedder(model={self.model_name}, loaded=False)"


class Vectorizer:
    """向量化器"""

    def __init__(self):
        """初始化"""
        pass

    @property
    def embeddings(self) -> Embeddings:
        """获取嵌入模型（使用全局缓存）"""
        return get_embedder()

    def embed_query(self, query: str) -> List[float]:
        """嵌入查询文本

        Args:
            query: 查询文本

        Returns:
            嵌入向量
        """
        return self.embeddings.embed_query(query)

    def embed_documents(self, documents: List[str]) -> List[List[float]]:
        """嵌入文档列表

        Args:
            documents: 文档列表

        Returns:
            嵌入向量列表
        """
        return self.embeddings.embed_documents(documents)
