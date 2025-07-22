# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1] - 2025-07-22

### Fixed
- **JsonObjectOutputSchema 兼容性问题**：修复了 `JsonObjectOutputSchema` 在 DeepSeek API 中出现的 `response_format type is unavailable` 错误
  - 修改 `convert_response_format` 方法，为 `JsonObjectOutputSchema` 添加特殊处理
  - `JsonObjectOutputSchema` 现在使用 `{'type': 'json_object'}` 格式而不是 `json_schema` 格式
  - 保持了其他输出模式（`AgentOutputSchema`）的向后兼容性
  - 添加了单元测试验证修复效果和回归测试

## [0.2.0] - 2025-01-09

### Added

#### 🚀 Streaming Tool 功能
- **新增 `@streaming_tool` 装饰器**：支持创建流式工具，可以实时输出进度和中间结果
- **新增 `Agent.as_tool(streaming=True)` 功能**：将 Agent 转换为流式工具，支持嵌套 Agent 调用
- **新增流式事件系统**：
  - `StreamingToolStartEvent` - 流式工具开始事件
  - `StreamingToolEndEvent` - 流式工具结束事件
  - `StreamingToolContextEvent` - 流式工具上下文隔离事件
  - `NotifyStreamEvent` - 通知事件，支持进度展示和打字机效果

#### 🔒 上下文隔离机制
- **实现完整的上下文隔离**：streaming_tool 内部 agent 的事件被自动包装，不会影响主 agent 的对话历史
- **智能事件包装**：
  - `RunItemStreamEvent`、`RawResponsesStreamEvent`、`AgentUpdatedStreamEvent` 被包装为 `StreamingToolContextEvent`
  - `NotifyStreamEvent`、`StreamingToolStartEvent`、`StreamingToolEndEvent` 直接传递
- **保持对话历史清洁**：只有 streaming_tool 的最终输出会被添加到主 agent 的对话历史中

#### 📚 文档和示例
- **新增完整的文档**：`docs/streaming_tool_context_isolation.md`
- **新增示例代码**：
  - `examples/basic/streaming_tool_basic.py` - 基础流式工具示例
  - `examples/tools/streaming_tools.py` - 高级流式工具示例
  - `examples/streaming_tool_context_isolation_demo.py` - 上下文隔离演示
- **新增测试用例**：`tests/test_streaming_tool.py` - 完整的单元测试覆盖

### Enhanced

#### 🎯 用户体验改进
- **实时进度反馈**：支持通过 `NotifyStreamEvent` 展示工具执行进度
- **打字机效果**：支持通过 `is_delta=True` 实现流式文本输出
- **事件标签系统**：支持为事件添加标签，便于前端分类处理
- **工具调用追踪**：每个流式工具调用都有唯一的 `tool_call_id` 用于追踪

#### 🔧 开发者体验
- **类型安全**：完整的 TypeScript 风格类型注解
- **错误处理**：完善的异常处理和错误传播机制
- **测试覆盖**：20+ 个测试用例，覆盖所有核心功能
- **代码质量**：通过 mypy、ruff 等工具的严格检查

### Technical Details

#### 架构改进
- **事件驱动架构**：基于 asyncio.Queue 的高性能事件处理
- **内存优化**：智能的事件包装机制，避免内存泄漏
- **并发支持**：支持多个 streaming_tool 并发执行
- **向后兼容**：完全兼容现有的 `@function_tool` 和 Agent API

#### 性能优化
- **异步优先**：所有流式操作都基于 asyncio
- **事件缓冲**：智能的事件队列管理
- **资源管理**：自动的任务清理和资源释放

### Breaking Changes
- 无破坏性变更，完全向后兼容

### Migration Guide
- 现有代码无需修改即可升级到 0.2.0
- 新功能为可选功能，不影响现有工作流

---

## [0.1.0] - 2024-12-XX

### Added
- 初始版本发布
- 基础 Agent 功能
- `@function_tool` 装饰器
- OpenAI API 集成
