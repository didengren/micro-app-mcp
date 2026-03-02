# Micro-App MCP Server

[![Python Version](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![PyPI Version](https://img.shields.io/pypi/v/micro-app-mcp)](https://pypi.org/project/micro-app-mcp/)
[![Release PyPI](https://github.com/didengren/micro-app-mcp/actions/workflows/release-pypi.yml/badge.svg)](https://github.com/didengren/micro-app-mcp/actions/workflows/release-pypi.yml)

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

## 安装与运行（需要 Python 3.12+）

### 方式 A：源码运行（推荐，已内置 CPU 优化）
适合开发者。本项目已配置 `uv` 智能索引，在 Windows/Linux 下会自动安装轻量化 CPU 版 Torch。

```bash
# 克隆仓库
git clone https://github.com/didengren/micro-app-mcp.git
cd micro-app-mcp

# 1. 一键安装依赖（自动处理跨平台 Torch 索引）
uv sync --extra dev

# 2. 安装浏览器内核
uv run python -m playwright install chromium

# 3. 以 editable 方式安装本项目作为依赖模块，方便开发调试
uv run pip install -e .

# 4. 复制一份 .env 按需修改项目环境变量，如 GITHUB_TOKEN、DATA_DIR 等
cp .env.example .env

# 5. 运行
uv run micro-app-mcp

# 6. 测试
uv run pytest
```

### 方式 B：CLI 快速运行（uvx）
适合普通用户。需手动指定 CPU 源以减小体积：

```bash
# Linux/Windows 用户手动设置环境变量指定 CPU 源以减小体积并使用 unsafe-best-match 策略避开依赖冲突
UV_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu" \
uvx --from micro-app-mcp --index-strategy unsafe-best-match micro-app-mcp

# macOS 用户（默认已支持 Metal/MPS GPU 加速且体积小，无需额外配置）
uvx --from micro-app-mcp micro-app-mcp
```

---

## IDE / Agent 集成

在 Trae (`config.json`) 或 VSCode (`mcp.json`) 的 `mcpServers` 中添加：

```json
{
  "mcpServers": {
    "micro-app-knowledge": {
      "command": "uvx",
      "args": ["--from", "micro-app-mcp", "--index-strategy", "unsafe-best-match", "micro-app-mcp"],
      "env": {
        "UV_EXTRA_INDEX_URL": "https://download.pytorch.org/whl/cpu",
        "DATA_DIR": "<您的数据目录>",
        "GITHUB_TOKEN": "<您的GITHUB_TOKEN>",
        "UPDATE_INTENT_ACTION_KEYWORDS": "强制更新,更新知识库,同步知识库,重建索引,force update,update knowledge base,rebuild index,sync knowledge base",
        "UPDATE_INTENT_TARGET_KEYWORDS": "知识库,索引,向量库,knowledge base,index,vector",
        "UPDATE_INTENT_SEARCH_ONLY_PATTERNS": "更新日志,changelog,release note,release notes,版本更新,最新更新"
      }
    }
  }
}
```

---

## 配置说明

在源码运行方式项目级 `.env` 或 CLI 运行方式终端进程级的环境中可以配置以下变量：

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
- `UPDATE_MAX_DURATION_SECONDS`: 单次更新最大持续时间（秒），默认 3600（超时自动失败）
- `CHROMA_ANONYMIZED_TELEMETRY`: Chroma 匿名遥测开关，默认 `false`（关闭）
- `UPDATE_INTENT_ACTION_KEYWORDS`: `/micro` 更新动作关键词（逗号分隔）
- `UPDATE_INTENT_TARGET_KEYWORDS`: `/micro` 更新目标关键词（逗号分隔）
- `UPDATE_INTENT_SEARCH_ONLY_PATTERNS`: `/micro` 检索优先短语（命中后不触发更新）
- `HF_ENDPOINT`: 国内环境拉取嵌入模型可配置成 HuggingFace 镜像地址，比如 `https://hf-mirror.com`
- `UV_EXTRA_INDEX_URL`: (可选) PyTorch 官方 CPU 仓库地址，Linux/Windows 用户配置为 `https://download.pytorch.org/whl/cpu` 可大幅减小安装体积（**源码运行模式下无需配置，会自动处理**）

> **最简配置建议**：  
> 只体验功能时，优先设置 `DATA_DIR` 和 `GITHUB_TOKEN`，其它可保持默认。

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

## 常见问题 (FAQ)

### 1. 网络与限流
- **模型下载/GitHub 采集失败**：请检查代理配置（`HTTP_PROXY`）或使用 `HF_ENDPOINT` 镜像。
- **更新报错**：确保配置了 `GITHUB_TOKEN`。

### 2. PyTorch 跨平台安装与依赖差异
由于 PyTorch 的分发策略差异，不同系统的安装方式略有不同：
- **macOS**：官方源下载的即为 **支持 Metal (MPS) GPU 加速** 的版本。因其无需捆绑 CUDA 库，体积依然很小，开箱即用。
- **Windows / Linux**：官方源默认会下载带 CUDA 的 **NVIDIA GPU 版**（体积巨大、易缺 DLL）。
  - **源码模式**：本项目已配置 `uv` 锁定 CPU 源，直接 `uv sync` 即可。
  - **CLI 模式**：需手动指定 `UV_EXTRA_INDEX_URL="https://download.pytorch.org/whl/cpu"`。
  - **依赖冲突**：若遇 `requests` 等库版本冲突，请添加 `--index-strategy unsafe-best-match` 参数。

### 3. Windows 常见报错 (DLL 1114/126)
通常因误装 GPU 版且环境缺失驱动导致。
- **方案 A**：安装 [VC++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe) 并重启。
- **方案 B（推荐）**：强制重装为 CPU 版本（参考上条 CLI 模式配置），彻底规避显卡驱动依赖。

---

## 贡献

欢迎提交 Issue 和 Pull Request，一起把 micro-app 生态的知识体验做得更好。

---

## 许可证

MIT