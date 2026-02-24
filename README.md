# Micro-App MCP Server

MCP Server for micro-app knowledge base

## 项目简介

该项目是一个专门用于查询 micro-app 微前端框架知识库的 MCP Server。它整合了 GitHub 源码和在线文档内容，支持语义检索。当用户输入 `/micro` 时，LLM 会先检索知识库再回答问题。

## 核心功能

- **数据采集**: 自动从 GitHub 获取源码，从在线文档站点获取文档内容
- **知识向量化**: 将采集的文本内容进行分块、向量化存储
- **语义检索**: 提供基于向量相似度的语义检索能力
- **MCP 协议集成**: 暴露标准 MCP 工具接口，支持 Trae AI Agent 和 VSCode 智能体

## 技术栈

- **MCP 框架**: FastMCP
- **HTTP 框架**: FastAPI
- **依赖管理**: uv
- **LLM 框架**: LangChain
- **向量数据库**: ChromaDB
- **文档采集**: LangChain AsyncChromiumLoader
- **源码采集**: PyGithub

## 用法
### 方法一：PyPI包方式

#### 安装PyPI包

```bash
pip install micro-app-mcp

# 运行依赖：DocsLoader 用 Playwright 爬取文档网站，Playwright 需要浏览器（Chromium）才能渲染页面
python -m playwright install chromium
```

#### 运行

```bash
micro-app-mcp
```

### 方法二：源码方式

#### 安装源码

```bash
# 克隆仓库
git clone <repository-url>
cd micro-app-mcp

# 安装依赖
uv sync

uv run python -m playwright install chromium

# 将本项目作为 editable 包安装，解决项目中自身包路径问题
uv run pip install -e .
```

#### 环境变量配置

复制 `.env.example` 文件为 `.env` 并根据需要修改配置：

```bash
cp .env.example .env
```

主要配置项：

- `EMBEDDING_MODEL`: 向量化模型类型，目前只支持 `local`
- `EMBEDDING_MODEL_NAME`: 本地向量化模型名称，默认 `BAAI/bge-small-zh-v1.5`
- `EMBEDDING_LAZY_LOAD`: 是否启用懒加载，默认 `true`（推荐开启，可减少启动内存占用）
- `GITHUB_TOKEN`: GitHub API Token，可选，用于提高 API 限流
- `DATA_DIR`: 数据存储路径，默认 `/xxx/micro_app_mcp`
- `FALLBACK_DATA_DIR`: 当 `DATA_DIR` 不可写时自动回退目录，默认 `/tmp/micro_app_mcp`
- `CACHE_DURATION_HOURS`: 智能缓存配置，默认 24 小时
- `DISPLAY_TIMEZONE`: 状态展示时区，默认 `Asia/Shanghai`

#### 本地服务器直接运行

```bash
uv run micro-app-mcp
```

#### MCP 服务器配置与运行（适合宿主项目配合开发调试）

```json
{
  "mcpServers": {
    "micro-app-mcp": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "src/micro_app_mcp/main.py"
      ],
      "cwd": "/xxx/work_space/micro-app-mcp",
      "env": {
        "DATA_DIR": "/xxx/micro_app_mcp",
        "GITHUB_TOKEN": "YOUR_GITHUB_TOKEN"
      }
    }
  }
}
```

#### 测试

```bash
# 运行测试
uv run pytest
```

### 方法三：IDE智能体方式

#### 安装依赖

```bash
uvx --from micro-app-mcp python -m playwright install chromium
```

#### MCP 服务器配置

###### 方法一：在 Trae AI Agent 中配置 MCP 服务器

- 打开 Trae AI Agent 配置文件（`config.json`）
- 添加以下内容：

```json
{
  "mcpServers": {
    "micro-app-knowledge": {
      "command": "uvx",
      "args": ["--from", "micro-app-mcp", "micro-app-mcp"],
      "env": {
        "DATA_DIR": "/xxx/micro_app_mcp"
      }
    }
  }
}
```

###### 方法二：在 VSCode 中配置 MCP 服务器

- 打开 VSCode 智能体配置文件（`mcp.json`）
- 添加以下内容：

```json
{
  "mcpServers": {
    "micro-app-knowledge": {
      "command": "uvx",
      "args": ["--from", "micro-app-mcp", "micro-app-mcp"],
      "env": {
        "DATA_DIR": "/xxx/micro_app_mcp"
      }
    }
  }
}
```

#### LLM调用MCP工具内在逻辑

当用户输入以 `/micro` 开头或包含 `/micro` 的消息时，会优先调用统一入口工具 `micro_app_command`，再按意图分发：

- 状态类请求：调用 `get_knowledge_base_status`
- 更新类请求：调用 `update_knowledge_base`
- 其他请求：调用 `search_micro_app_knowledge`

推荐的工具编排方式：

1. 先调用 `get_knowledge_base_status`（只读状态）
2. 当 `is_stale=true` 或用户明确要求更新时，再调用 `update_knowledge_base`
3. 最后调用 `search_micro_app_knowledge` 进行检索

可用 MCP 工具：

- `get_knowledge_base_status`: 返回本地时区的 `last_updated`/`next_recommended_update_at`，以及对应 UTC 字段、`is_stale`、`should_skip_update`、`document_count` 等状态信息
- `update_knowledge_base(force=False)`: 显式更新知识库（写操作）
- `search_micro_app_knowledge(query, top_k=15)`: 语义检索（只读）

#### 示例

1. `/micro 获取知识库状态`
2. `/micro 强制更新知识库 force=true`
3. `/micro <你的检索问题>`

## 项目结构

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

## 贡献

欢迎提交 Issue 和 Pull Request！

## 许可证

MIT
