# Micro-App MCP Server

`micro-app-mcp` 是一个面向 **micro-app 微前端框架** 的专用知识库 MCP Server。  
它会自动 **吃透 micro-app 仓库源码、爬取官方文档内容、用嵌入模型向量化后存入本地数据库**，并通过 MCP 协议提供语义检索与可控更新能力。

---

## 特性亮点

- **源码级掌握 micro-app**：从官方 GitHub 仓库拉取源码，结合文档做统一知识建模。
- **自动爬取官方文档**：利用 Playwright 渲染 + 文档爬虫，从文档站点采集完整内容。
- **本地向量化知识库**：基于嵌入模型将文本向量化，存入本地 ChromaDB，查询低延迟、可离线可缓存。
- **可控更新策略**：支持按需更新、强制更新与状态查询，避免每次都重建知识库。
- **标准 MCP 接入**：开箱即用接入 Trae AI Agent、VSCode 等支持 MCP 的智能体。

---

## 对话场景

在你的智能体里（如 Trae / VSCode MCP 插件）完成配置后，当用户输入 `/micro` 时，LLM 会先通过统一入口工具按问题类别（状态 / 更新 / 检索）识别意图后再回答问题，比如：

- **查询知识库状态**：`/micro 获取知识库状态`
- **控制知识库更新**：`/micro 更新知识库` 或 `/micro 强制更新知识库 force=true`
- **询问 API / 配置项**：`/micro micro-app 支持哪些沙箱隔离模式？`
- **理解源码实现**：`/micro micro-app 子应用的加载流程怎么实现的？入口源码在哪？`
- **看版本变更 / 升级注意**：`/micro 从 vX 到 vY 有哪些 breaking changes？`

---

## 安装和运行（需要 Python 3.12）

### CLI 方式

> 全局安装（pip为例）

```bash
pip install micro-app-mcp # 手动安装包
python -m playwright install chromium # 使用依赖模块 Playwright 安装 Chromium
```

**运行**

```bash
# 配置 shell 环境变量，其中一项是指定数据目录
export DATA_DIR=<DATA_DIR>

micro-app-mcp
```

> 或者 
> 临时环境安装（uvx为例）

```bash
uvx --from micro-app-mcp python -m playwright install chromium
```

**运行**

```bash
export DATA_DIR=<DATA_DIR>

uvx --from micro-app-mcp micro-app-mcp
```

---

### 源码方式

> 适合本地开发与调试

#### 克隆仓库

```bash
# 克隆仓库
git clone https://github.com/didengren/micro-app-mcp.git
cd micro-app-mcp
```

#### 安装依赖

```bash
# 安装依赖（含开发依赖）
uv sync --extra dev

# 安装 Playwright 浏览器
uv run python -m playwright install chromium

# 以 editable 方式安装本项目作为依赖模块，方便开发调试
uv run pip install -e .
```

#### 配置项目环境变量

```bash
cp .env.example .env
# 按需修改 .env
```

#### 本地直接运行

```bash
uv run micro-app-mcp
# 或
uv run python -m micro_app_mcp.main
```

---

## IDE / Agent 集成 MCP Server

### Trae AI Agent 配置示例

在 Trae 配置文件 `config.json` 中新增（示例）：

```json
{
  "mcpServers": {
    "micro-app-knowledge": {
      "command": "uvx",
      "args": ["--from", "micro-app-mcp==<version>", "micro-app-mcp"],
      "env": {
        "DATA_DIR": "<DATA_DIR>/micro_app_mcp",
        "FALLBACK_DATA_DIR": "<FALLBACK_DATA_DIR>/micro_app_mcp",
        "GITHUB_TOKEN": "<YOUR_GITHUB_TOKEN>",
        "UPDATE_INTENT_ACTION_KEYWORDS": "强制更新,更新知识库,同步知识库,重建索引,force update,update knowledge base,rebuild index,sync knowledge base",
        "UPDATE_INTENT_TARGET_KEYWORDS": "知识库,索引,向量库,knowledge base,index,vector",
        "UPDATE_INTENT_SEARCH_ONLY_PATTERNS": "更新日志,changelog,release note,release notes,版本更新,最新更新"
      }
    }
  }
}
```

### VSCode MCP 配置示例

在 VSCode 的 `mcp.json` 中新增：

```json
{
  "mcpServers": {
    "micro-app-knowledge": {
      "command": "uvx",
      "args": ["--from", "micro-app-mcp==<version>", "micro-app-mcp"],
      "env": {
        "DATA_DIR": "<DATA_DIR>/micro_app_mcp",
        "FALLBACK_DATA_DIR": "<FALLBACK_DATA_DIR>/micro_app_mcp",
        "GITHUB_TOKEN": "<YOUR_GITHUB_TOKEN>",
        "UPDATE_INTENT_ACTION_KEYWORDS": "强制更新,更新知识库,同步知识库,重建索引,force update,update knowledge base,rebuild index,sync knowledge base",
        "UPDATE_INTENT_TARGET_KEYWORDS": "知识库,索引,向量库,knowledge base,index,vector",
        "UPDATE_INTENT_SEARCH_ONLY_PATTERNS": "更新日志,changelog,release note,release notes,版本更新,最新更新"
      }
    }
  }
}
```

---

## 配置说明（运行时可配置的环境变量）

在 `.env` 或进程环境中可以配置以下变量：

- `EMBEDDING_MODEL`: 向量化模型类型，目前只支持 `local`
- `EMBEDDING_MODEL_NAME`: 本地向量化模型名称，默认 `BAAI/bge-small-zh-v1.5`
- `EMBEDDING_LAZY_LOAD`: 是否启用懒加载，默认 `true`（推荐开启，可减少启动内存占用）
- `GITHUB_TOKEN`: GitHub API Token，强烈建议配置（否则更新知识库时易触发限流）
- `GITHUB_HTTP_TIMEOUT_SECONDS`: GitHub 请求超时时间（秒），默认 15
- `GITHUB_RETRY_TOTAL`: GitHub 请求重试次数，默认 0（避免限流后长时间退避阻塞）
- `DATA_DIR`: 数据存储路径
- `FALLBACK_DATA_DIR`: 当 `DATA_DIR` 不可写时自动回退目录，默认 `/tmp/micro_app_mcp`（若仍不可写会自动降级到系统临时目录）
- `CACHE_DURATION_HOURS`: 智能缓存配置，默认 24 小时
- `SEARCH_TIMEOUT_SECONDS`: 检索超时秒数，默认 30 秒（超时会返回“请稍后重试”提示）
- `UPDATE_MAX_DURATION_SECONDS`: 单次更新最大持续时间（秒），默认 600（超时自动失败）
- `CHROMA_ANONYMIZED_TELEMETRY`: Chroma 匿名遥测开关，默认 `false`（关闭）
- `UPDATE_INTENT_ACTION_KEYWORDS`: `/micro` 更新动作关键词（逗号分隔）
- `UPDATE_INTENT_TARGET_KEYWORDS`: `/micro` 更新目标关键词（逗号分隔）
- `UPDATE_INTENT_SEARCH_ONLY_PATTERNS`: `/micro` 检索优先短语（命中后不触发更新）
- `HF_ENDPOINT`: 国内环境拉取嵌入模型可配置成 HuggingFace 镜像地址，比如 `https://hf-mirror.com`

> **最简配置建议**：  
> 只体验功能时，优先设置 `GITHUB_TOKEN` 和 `DATA_DIR`，其它可保持默认。
>
> **网络问题提示**：
> - 拉取嵌入模型（首次加载）和 GitHub 源码时需要访问国外网络，建议自备代理或使用国内镜像源
> - 嵌入模型：配置 `HF_ENDPOINT=https://hf-mirror.com` 使用 HuggingFace 国内镜像
> - GitHub 源码：配置 `GITHUB_TOKEN` 可提高 API 限流阈值（60次→5000次/小时），但网络超时问题仍需代理解决
> - 代理配置：`HTTP_PROXY` / `HTTPS_PROXY` 环境变量（会影响所有 HTTP 请求）

---

## 项目结构

```text
micro-app-mcp/
├── .github/workflows/release-pypi.yml  # Tag 自动发布 TestPyPI/PyPI
├── .githooks/pre-commit                # 版本变更时自动更新 CHANGELOG
├── pyproject.toml                      # 项目配置
├── uv.lock                             # 依赖锁文件
├── README.md                           # 项目说明
├── CHANGELOG.md                        # 版本变更记录
├── scripts/
│   ├── generate_changelog.py           # 基于 git diff 生成 changelog
│   ├── version_change_detector.py      # 检测版本变更
│   └── install_hooks.sh                # 安装本地 git hooks
├── src/micro_app_mcp/
│   ├── main.py                         # FastMCP 入口
│   ├── config.py                       # 配置管理
│   ├── app/
│   │   ├── server.py                   # MCP Server 定义
│   │   └── tools.py                    # MCP 工具实现
│   ├── knowledge/
│   │   ├── github_loader.py            # micro-app 仓库源码采集
│   │   ├── docs_loader.py              # 官方文档采集（Playwright）
│   │   ├── text_splitter.py            # 文本切分
│   │   └── vectorizer.py               # 嵌入与向量存储
│   ├── storage/
│   │   ├── vector_store.py             # ChromaDB 封装
│   │   └── metadata.py                 # 元数据管理
│   └── utils/logger.py                 # 日志工具
├── tests/
│   ├── test_tools.py
│   └── test_knowledge.py
└── .env.example                        # 环境变量示例
```

---

## 测试

```bash
uv run pytest
```

---

## 贡献

欢迎提交 Issue 和 Pull Request，一起把 micro-app 生态的知识体验做得更好。

---

## 许可证

MIT