# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).



## [0.1.5] - 2026-02-26

### Changed
- 升级依赖并增加与外部通信的网络协议支持（http/sse/streamable-http）。
- README 新增 Windows 系统运行报错 FAQ 与解决方案。

## [0.1.4] - 2026-02-25

### Fixed
- fix: 剪除不再使用的运行时依赖，重写readme

## [0.1.3] - 2026-02-24

### Fixed
- fix: 修复子包导入问题

## [0.1.2] - 2026-02-24

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


[Unreleased]: https://github.com/didengren/micro-app-mcp/compare/v0.1.5...HEAD
[0.1.5]: https://github.com/didengren/micro-app-mcp/compare/v0.1.4...v0.1.5
[0.1.4]: https://github.com/didengren/micro-app-mcp/compare/v0.1.3...v0.1.4
[0.1.3]: https://github.com/didengren/micro-app-mcp/compare/v0.1.2...v0.1.3
[0.1.2]: https://github.com/didengren/micro-app-mcp/compare/v0.1.1...v0.1.2

## v0.1.6 (2026-02-27)


- test: 修复测试用例错误
- chore: 新增提交规范、版本变更自动化等辅助功能
- 1. 升级依赖并增加与外部通信的网络协议支持 2. 增加Windows 系统下运行报错等常见问题的解决方案推荐

## v0.1.4 (2026-02-25)


- 变更changelog
- 剪除不再使用的运行时依赖，重写readme

## v0.1.3 (2026-02-25)


- 变更changelog和uv.lock中包版本
- fix: 修复子包导入问题

## v0.1.2 (2026-02-24)


- Merge branch 'fix/timeout'
- release: 0.1.2 automation + changelog
- Merge branch 'feat/multi_process' into fix/timeout
- 重构多进程执行场景
- #
- 变更版本号
- Merge branch 'master'
- 修复因路径导致文件写入无权限的问题
- Merge branch 'main'
- Merge branch 'main' of github.com:didengren/micro-app-mcp 合并github仓库的LICENSE文件
- Initial commit
- 基本完成mcp server源码开发
