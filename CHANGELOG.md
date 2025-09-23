# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.4] - 2025-01-23

### Added
- **@streaming_tool failure_error_function 支持**：为 `@streaming_tool` 装饰器添加了与 `@function_tool` 一致的异常处理机制
  - 新增 `failure_error_function: ToolErrorFunction | None = default_tool_error_function` 参数
  - 支持自定义错误处理函数，当工具调用失败时生成错误消息发送给 LLM
  - 与 `@function_tool` 保持完全一致的异常处理行为
  - 确保 Hook 框架（如 `UserConfirmationHook`）在流式工具上正常工作

### Enhanced
- **开发者体验一致性**：统一了 `@function_tool` 和 `@streaming_tool` 的异常处理模式
- **Hook 框架兼容性**：现在 Hook 拦截后，流式工具也会返回错误消息而不是导致整个 Agent 崩溃
- **错误跟踪完善**：添加了与 `@function_tool` 一致的错误跟踪机制
- **日志记录改进**：完善了参数和完成状态的日志记录，与 `@function_tool` 保持一致
- **文档质量提升**：改进了 `@streaming_tool` 的文档字符串，提供详细的参数说明

### Fixed
- **异常处理不一致**：修复了 `@streaming_tool` 缺少 `failure_error_function` 支持的问题
- **错误跟踪缺失**：添加了 `_error_tracing.attach_error_to_current_span` 调用
- **日志记录不完整**：补充了参数详细日志和工具完成日志
- **装饰器返回逻辑**：统一了装饰器的返回逻辑和注释风格

### Technical Details
- **架构一致性**：确保两种工具装饰器在异常处理、日志记录、错误跟踪等方面完全一致
- **向后兼容性**：所有更改都保持向后兼容，现有代码无需修改
- **类型安全**：完整的类型注解支持，包括新的 `failure_error_function` 参数

## [0.2.3] - 2025-01-19

### Added
- **Agent.as_tool() RunConfig 支持**：为 `Agent.as_tool()` 方法添加了 `run_config` 参数支持
  - 新增 `run_config: RunConfig | None = None` 参数，允许为工具 Agent 指定自定义配置
  - 支持自定义模型提供者，解决企业级部署中的模型前缀问题（如 `doubao/`, `deepseek/` 等）
  - 同时支持流式和非流式工具的 RunConfig 传递
  - 保持完全的向后兼容性，现有代码无需修改

### Enhanced
- **企业级部署支持**：现在可以在 Agent 作为工具时使用自定义模型提供者和配置
- **配置隔离**：不同工具可以使用不同的 RunConfig，实现更灵活的配置管理
- **文档改进**：更新了 `docs/tools.md`，添加了自定义模型提供者的使用示例

### Fixed
- **RunConfig 传递问题**：修复了 `Agent.as_tool()` 内部调用 `Runner.run()` 时不传递 `run_config` 的问题
- **模型提供者配置**：解决了工具 Agent 无法使用主 Agent 的自定义模型提供者配置的问题

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
