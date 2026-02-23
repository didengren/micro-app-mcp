# Micro-App MCP Server 技术方案

## 1. 项目概述

### 1.1 项目目标
开发一个 MCP Server，专门用于查询 micro-app 微前端框架的知识库。该知识库整合了 GitHub 源码和在线文档内容，支持语义检索。当用户输入 `/micro` 时，LLM 会先检索知识库再回答问题。

### 1.2 核心功能
- **数据采集**: 自动从 GitHub 获取源码，从在线文档站点获取文档内容
- **知识向量化**: 将采集的文本内容进行分块、向量化存储
- **语义检索**: 提供基于向量相似度的语义检索能力
- **MCP 协议集成**: 暴露标准 MCP 工具接口，支持 Trae AI Agent 和 VSCode 智能体

### 1.3 目标用户
- 使用 micro-app 框架的开发者
- 需要了解 micro-app 框架文档和源码的技术人员

---

## 2. 技术架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                        MCP Client                               │
│                   (Trae AI Agent / VSCode)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Server 核心层                            │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │              FastMCP / MCP Python SDK                     │  │
│  │  - search_micro_app_knowledge (语义检索)                   │  │
│  │  - update_knowledge_base (知识库更新)                       │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      知识处理层                                   │
│  ┌─────────────┐  ┌──────────────────────┐  ┌─────────────────────────┐ │
│  │ GitHub 采集器 │  │ 文档采集器            │  │ 文本处理流水线           │ │
│  │ (PyGithub)   │  │(AsyncChromiumLoader)  │  │(RecursiveCharacterText  │ │
│  │             │  │                    │  │ Splitter + Embeddings)   │ │
│  └─────────────┘  └──────────────────────┘  └─────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      数据存储层                                   │
│  ┌─────────────────────┐  ┌────────────────────────────────┐  │
│  │    ChromaDB 向量库    │  │  元数据存储 (JSON/SQLite)       │  │
│  │  - 持久化存储         │  │  - 版本信息                     │  │
│  │  - 相似度检索        │  │  - 采集时间戳                   │  │
│  └─────────────────────┘  └────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                     智能缓存层                                   │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  智能跳过逻辑 (24小时缓存)                                 │  │
│  │  - 非强制更新时检查上次同步时间                            │  │
│  │  - 快速返回缓存状态，避免重复同步                            │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 技术选型理由

| 组件 | 选型 | 理由 |
|------|------|------|
| **MCP 框架** | FastMCP | 轻量、Python 原生、与 FastAPI 天然兼容 |
| **HTTP 框架** | FastAPI | 高性能、自动 OpenAPI 文档、异步支持 |
| **依赖管理** | uv | 现代 Python 包管理，速度极快 |
| **LLM 框架** | LangChain | 成熟的 RAG 流水线、丰富的加载器生态 |
| **向量数据库** | ChromaDB | 轻量、易用、Python 原生、支持持久化，完全满足项目规模需求 |
| **文档采集** | LangChain AsyncChromiumLoader | 基于 Playwright，与 LangChain 生态集成更好，API 更简洁 |
| **源码采集** | PyGithub | 直接调用 REST API，支持按文件流式拉取，更可控，避免大型仓库克隆阻塞 |

---

## 3. 模块设计

### 3.1 项目目录结构

```
micro-app-mcp/
├── pyproject.toml                 # 项目配置
├── uv.lock                        # 依赖锁定
├── README.md                      # 项目说明
├── src/
│   └── micro_app_mcp/
│       ├── __init__.py
│       ├── main.py                # FastMCP 入口
│       ├── config.py              # 配置管理
│       ├── mcp/
│       │   ├── __init__.py
│       │   ├── server.py          # MCP Server 定义
│       │   └── tools.py           # MCP 工具实现
│       ├── knowledge/
│       │   ├── __init__.py
│       │   ├── base.py            # 知识处理基类
│       │   ├── github_loader.py   # GitHub 源码采集
│       │   ├── docs_loader.py     # 文档采集 (Playwright)
│       │   ├── text_splitter.py   # 文本分块
│       │   └── vectorizer.py      # 向量化处理
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── vector_store.py    # ChromaDB 封装
│       │   └── metadata.py        # 元数据管理
│       └── utils/
│           ├── __init__.py
│           └── logger.py          # 日志工具
├── tests/
│   ├── __init__.py
│   ├── test_tools.py
│   └── test_knowledge.py
└── .env.example                   # 环境变量示例
```

### 3.2 核心模块详细设计

#### 3.2.1 MCP Server 核心层

**文件**: `src/micro_app_mcp/mcp/server.py`

```python
from fastmcp import FastMCP
from micro_app_mcp.mcp.tools import (
    search_micro_app_knowledge,
    update_knowledge_base
)

mcp = FastMCP(
    "micro-app-knowledge-server",
    instructions="当用户消息以 /micro 开头或包含 /micro 时，自动调用 search_micro_app_knowledge 工具来查询 micro-app 知识库。"
)

@mcp.tool()
async def search_micro_app_knowledge(query: str, top_k: int = 5) -> str:
    """
    语义检索 micro-app 知识库。
    
    Args:
        query: 用户查询内容
        top_k: 返回最相关的结果数量，默认 5
    
    Returns:
        格式化的检索结果，包含源码和文档片段
    """
    ...

@mcp.tool()
async def update_knowledge_base(force: bool = False) -> str:
    """
    触发知识库更新。
    
    Args:
        force: 是否强制更新，强制更新会重新采集所有数据
    
    Returns:
        更新结果摘要
    """
    ...
```

**MCP 工具定义**:

| 工具名 | 输入参数 | 返回类型 | 说明 |
|--------|----------|----------|------|
| `search_micro_app_knowledge` | `query: str`, `top_k: int = 5` | `str` | 语义检索，返回最相关的知识片段 |
| `update_knowledge_base` | `force: bool = False` | `str` | 触发知识库更新，返回更新结果 |

#### 3.2.2 知识处理层

**GitHub 采集器**: 使用 `PyGithub` 直接调用 REST API
- **优势**: 避免大型仓库克隆阻塞，支持按文件流式拉取，更可控
- 支持指定仓库、分支、文件路径
- 自动提取代码内容、文件路径作为元数据
- 实现增量同步，只获取变更文件

**文档采集器**: 基于 LangChain AsyncChromiumLoader 实现
- 底层使用 Playwright 渲染 SPA 应用
- 自动等待网络空闲，确保页面完全加载
- 与 LangChain 生态无缝集成，直接返回 Document 对象
- 支持增量更新（基于最后修改时间）

**文本分块器**: `RecursiveCharacterTextSplitter`
- 默认 chunk_size: 1000
- 默认 chunk_overlap: 200
- 按代码文件/文档页面分别处理

**向量化器**: 仅使用本地模式
- **本地模式**: 使用 `HuggingFaceEmbeddings`，模型为 `BAAI/bge-small-zh-v1.5` (中文优化，性能更好)

#### 3.2.3 数据存储层

**ChromaDB 封装**:
- 持久化存储路径: `~/work_space/tmp/micro_app_mcp/chroma_db/`
- Collection 名称: `micro_app_knowledge`
- 元数据字段: `source` (github/docs), `path`, `title`, `url`

**元数据存储**: JSON 文件
- 位置: `~/work_space/tmp/micro_app_mcp/metadata.json`
- 内容:
  ```json
  {
    "version": "1.0.0",
    "last_updated": "2025-01-01T00:00:00Z",
    "github_commit": "abc123",
    "docs_hash": "def456"
  }
  ```

#### 3.2.4 智能缓存层

**智能跳过逻辑**:
- 在 `update_knowledge_base` 工具中实现智能跳过机制
- 若距上次成功同步不足 24 小时且非 `force=True`，直接返回缓存状态
- 从而在实际使用中达到"快速启动"的效果，无需额外维护静态文件服务

**缓存状态管理**:
- 在元数据文件中记录上次同步时间和状态
- 支持手动强制更新（`force=True`）
- 提供缓存状态查询能力

---

## 4. 数据流设计

### 4.1 知识库更新流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   触发更新   │ ──▶ │  数据采集   │ ──▶ │  文本处理   │ ──▶ │  向量存储   │
│ (工具调用)   │     │             │     │  (分块)     │     │  (ChromaDB) │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                    │ GitHub API  │     │AsyncChromiumLoader│ │ 持久化存储  │
                    │ 获取源码    │     │ 渲染 SPA    │     │   本地磁盘   │
                    └─────────────┘     └─────────────┘     └─────────────┘
```

### 4.2 语义检索流程

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  用户查询   │ ──▶ │  查询向量化 │ ──▶ │  相似度检索 │ ──▶ │ 结果格式化  │
│             │     │             │     │  (ChromaDB) │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                   │                   │
                           ▼                   ▼                   ▼
                    ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
                    │  Embeddings │     │ Top-K 结果  │     │  返回文本   │
                    │   模型      │     │             │     │  + 元数据   │
                    └─────────────┘     └─────────────┘     └─────────────┘
```

---

## 5. 配置设计

### 5.1 环境变量 (.env)

```bash
# 向量化模型配置
EMBEDDING_MODEL=local
EMBEDDING_MODEL_NAME=BAAI/bge-small-zh-v1.5

# GitHub 配置
GITHUB_TOKEN=ghp_xxx   # 可选，提高 API 限流

# 数据存储路径
DATA_DIR=~/work_space/tmp/micro_app_mcp

# 智能缓存配置（可选）
CACHE_DURATION_HOURS=24
```

### 5.2 pyproject.toml 关键配置

```toml
[project]
name = "micro-app-mcp"
version = "0.1.0"
description = "MCP Server for micro-app knowledge base"
requires-python = ">=3.12"
dependencies = [
    "fastmcp>=0.1.0",
    "fastapi>=0.109.0",
    "langchain>=0.2.0",
    "langchain-community>=0.2.0",
    "chromadb>=0.4.0",
    "playwright>=1.40.0",
    "huggingface-hub>=0.20.0",
    "uvicorn>=0.27.0",
    "pydantic>=2.5.0",
    "python-dotenv>=1.0.0",
]

[project.scripts]
micro-app-mcp = "micro_app_mcp.main:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

---

## 6. MCP 集成配置

### 6.1 Trae AI Agent 配置

在项目的 `./trae/mcp.json` 中添加：

```json
{
  "mcpServers": {
    "micro-app-knowledge": {
      "command": "uvx",
      "args": ["--with", "micro-app-mcp", "micro-app-mcp"],
      "env": {
        "EMBEDDING_MODEL": "local"
      }
    }
  }
}
```

### 6.2 VSCode 智能体配置

在 VSCode 的 `mcp.json` 中添加类似配置。

---

## 7. 实现优先级

### 7.1 第一阶段：核心功能
1. 项目骨架搭建（FastMCP + 目录结构）
2. GitHub 源码采集
3. 文本分块 + 向量化
4. ChromaDB 存储
5. 语义检索工具实现
6. 基本测试

### 7.2 第二阶段：完善功能
1. AsyncChromiumLoader 文档采集
2. 知识库更新工具
3. 元数据管理
4. 配置优化

### 7.3 第三阶段：完善功能
1. 智能缓存层实现
2. 增量更新优化
3. 错误处理与重试机制

---

## 8. 关键技术点

### 8.1 /micro 触发机制
- **实现方式**: 在 MCP Server 的 `instructions` 字段中注入 System Prompt
- **触发条件**: 当用户消息以 `/micro` 开头或包含 `/micro` 时
- **行为**: 自动调用 `search_micro_app_knowledge` 工具查询知识库
- **优势**: 无需修改 Agent 端代码，通过 MCP 协议的 System Prompt 注入机制实现
- **示例**: 用户输入 "/micro 如何使用 js 沙箱" 时，LLM 会自动调用搜索工具

### 8.2 SPA 文档采集
- 目标 URL: `https://jd-opensource.github.io/micro-app/docs.html#/`
- 使用 AsyncChromiumLoader 自动等待网络空闲
- 底层基于 Playwright 渲染，确保 SPA 完全加载
- 提取可阅读文本内容，支持动态加载的内容

### 8.3 GitHub API 限流
- 未认证: 60 次/小时
- 认证: 5000 次/小时
- 建议配置 GITHUB_TOKEN

### 8.4 向量化模型选择
- 本地模型: `BAAI/bge-small-zh-v1.5` (~120MB)，中文优化，性能更好
- 移除云端模型选项，仅使用本地模型

---

## 9. 部署形态

### 9.1 本地 Python 包模式
```bash
# 安装
pip install micro-app-mcp

# 运行
micro-app-mcp

# 或通过 uvx
uvx micro-app-mcp
```

### 9.2  MCP Server 集成
- 通过 stdio 模式与 MCP Client 通信
- 符合 MCP 协议标准
- 支持 Trae、VSCode 等主流 IDE
