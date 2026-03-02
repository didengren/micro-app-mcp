# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/lang/zh-CN/).



## v0.1.8 (2026-03-03)


- refactor: 1. 重写日志模块 2. 知识库过期间隔由1天调整为7天
- fix: 1. 路径动态化 ：将 CHROMA_DB_PATH 和 METADATA_PATH 改为 @property 。这确保了无论 DATA_DIR 何时被修改（例如在测试环境或目录回退时），子路径永远自动保持同步，彻底消除了路径不一致的隐患。
- ci: 检出目标仓库解决action过程警告问题
- docs: changelog文件删除多余信息

## v0.1.7 (2026-02-28)


- fix: 修改更新知识库默认的总体超时上限并增加资源下载过程的日志 
- fix: 修复需类型判断推理的tool对象取值问题
- docs: 补充changelog
- ci: 优化publish流程

## v0.1.6 (2026-02-27)


- test: 修复测试用例错误
- chore: 新增提交规范、版本变更自动化等辅助功能
- fix: 升级依赖并增加与外部通信的网络协议支持
- fix: 增加Windows 系统下运行报错等常见问题的解决方案推荐

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
- 变更版本号
- Merge branch 'master'
- 修复因路径导致文件写入无权限的问题
- Merge branch 'main'
- Merge branch 'main' of github.com:didengren/micro-app-mcp 合并github仓库的LICENSE文件
- Initial commit
- 基本完成mcp server源码开发
