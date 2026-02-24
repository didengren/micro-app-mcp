# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).

## [Unreleased]

<!-- AUTO-GENERATED:START -->
### Changed
- 暂无未发布变更。
<!-- AUTO-GENERATED:END -->


## [0.1.3] - 2026-02-24

<!-- AUTO-GENERATED:START -->
### Changed
- 暂无可归类变更。
<!-- AUTO-GENERATED:END -->

## [0.1.2] - 2026-02-24

<!-- AUTO-GENERATED:START -->
### Added
- /micro 统一命令分发增强，支持显式工具名解析与参数自动类型转换。
- 新增更新任务模型（提交任务、查询任务状态、任务生命周期字段）。
- 新增配置项：检索超时、更新任务保留策略、更新意图关键词。
- 新增目录回退来源标识（data_dir_source）与系统临时目录兜底。
- 新增测试文件 tests/test_config.py，补齐目录兜底链路验证。

### Changed
- search_micro_app_knowledge 改为线程下沉执行向量检索并加超时保护。
- update_knowledge_base 演进为后台任务模式（非阻塞）并支持任务轮询。
- MetadataManager 引入并发安全增强（单例、线程锁/文件锁、任务状态持久化）。
- GitHubLoader 改为 async 壳 + sync 核，避免阻塞事件循环。
- LazyEmbedder 增加并发加载保护，避免重复初始化。
- README、.env.example、MCP 配置示例全面更新。
- 更新文件：`pyproject.toml`

### Fixed
- 修复“更新日志/版本更新”类检索误触发更新任务的问题。
- 修复高并发/长时间运行下任务状态管理与裁剪行为不稳定的问题。
- 修复数据目录不可写时仅单级回退的脆弱性，改为多级候选链。

### Tests
- 扩展 tests/test_tools.py：路由优先级、超时提示、事件循环不阻塞、任务状态回退等。
- 扩展 tests/test_knowledge.py：GitHub loader 非阻塞、懒加载并发单次初始化。

### Docs
- 关联提交：f1e67ef Merge branch 'feat/multi_process' into fix/timeout；88f8ddd 重构多进程执行场景
<!-- AUTO-GENERATED:END -->



<!-- LINKS:START -->
[Unreleased]: https://github.com/didengren/micro-app-mcp/compare/v0.1.3...HEAD
[0.1.3]: https://github.com/didengren/micro-app-mcp/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/didengren/micro-app-mcp/compare/v0.1.1...v0.1.2
<!-- LINKS:END -->
