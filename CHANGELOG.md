# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.7] - 2025-11-13

### Added
- **OpenRouter 推理格式支持**：ChatCmplStreamHandler 现在可以识别和处理 OpenRouter API 返回的推理内容
  - 支持 `delta.reasoning` 字段（OpenRouter/标准 Chat Completions API 格式）
  - 保持对 `delta.reasoning_content` 字段的支持（OpenAI Responses API 格式）
  - 优先级检查：优先检查 `reasoning_content`，然后检查 `reasoning`
  - 流式处理：`chatcmpl_stream_handler.py` 支持流式推理事件
  - 非流式处理：`chatcmpl_converter.py` 支持非流式推理内容转换

### Fixed
- **OpenRouter 推理事件捕获**：修复使用 OpenRouter 作为模型提供商时，推理事件无法被捕获的问题
  - 之前：agents-sdk 只检查 `delta.reasoning_content`，无法识别 OpenRouter 的 `delta.reasoning`
  - 现在：同时支持两种格式，启用 OpenRouter 模型的推理功能（DeepSeek、Claude 等）

### Technical Details
- **修改文件**：
  - `src/agents/models/chatcmpl_stream_handler.py` - 添加 `delta.reasoning` 字段检查
  - `src/agents/models/chatcmpl_converter.py` - 添加 `message.reasoning` 字段检查
- **测试覆盖**：扩展 `tests/test_reasoning_content.py`，新增 2 个测试用例
  - `test_stream_response_with_openrouter_reasoning_format()` - 测试流式 OpenRouter 格式
  - `test_get_response_with_openrouter_reasoning_format()` - 测试非流式 OpenRouter 格式
  - 新增辅助函数 `create_openrouter_reasoning_delta()` 模拟 OpenRouter API 响应

### Impact
- **向后兼容性**：✅ 完全兼容，不影响现有代码
- **性能影响**：✅ 最小化，仅增加一次字段检查
- **模型兼容性**：✅ 提升，支持 OpenRouter、DeepSeek、Claude 等模型的推理功能
- **测试通过率**：✅ 所有推理相关测试通过（5/5）

## [0.2.6] - 2025-11-04

### Added
- **JSON Schema $ref 完全展开支持**：自动展开所有 `$ref` 引用，确保与不支持 JSON Schema `$ref` 的 LLM 模型兼容
  - 新增 `inline_all_refs()` 函数，递归展开所有 `$ref` 引用
  - 修改 `ensure_strict_json_schema()` 函数，在返回前自动调用 `inline_all_refs()`
  - 展开后移除 `$defs` 和 `definitions` 字段（已无引用）
  - 支持循环引用检测，避免无限递归

### Fixed
- **Gemini 2.5 Pro 兼容性**：修复 Gemini 2.5 Pro 无法解析 `$ref` 导致的参数错误问题
  - 之前：Gemini 将嵌套 Pydantic 对象当作字符串处理
  - 现在：生成内联 schema，Gemini 可以正确理解嵌套对象结构
- **Qwen3-max 兼容性**：修复 Qwen3-max 在 `additionalProperties: false` + `$ref` 组合下的序列化问题
  - 之前：Qwen3-max 将嵌套对象序列化为 JSON 字符串
  - 现在：使用内联定义，Qwen3-max 可以正确生成嵌套对象

### Technical Details
- **修改文件**：`src/agents/strict_schema.py`
- **新增函数**：`inline_all_refs(schema, root, visited)` - 110 行
- **修改函数**：`ensure_strict_json_schema()` - 添加 $ref 展开逻辑
- **测试覆盖**：新增 `tests/test_inline_refs.py`，包含 11 个测试用例
  - 简单 $ref 展开
  - 嵌套 $ref 展开
  - $ref + 额外属性（description）
  - anyOf/allOf 中的 $ref
  - 数组 items 中的 $ref
  - 循环引用检测
  - 多处引用同一定义

### Impact
- **向后兼容性**：✅ 完全兼容，不影响现有功能
- **性能影响**：✅ 最小化，仅在生成 schema 时执行一次
- **模型兼容性**：✅ 提升，支持更多 LLM 模型（Gemini、Qwen3-max 等）

### Use Case Example
```python
from pydantic import BaseModel
from agents import function_tool

class UserProfile(BaseModel):
    """用户画像"""
    name: str
    age: int
    city: str

@function_tool
def extract_profile(profile: UserProfile) -> UserProfile:
    """提取用户画像信息"""
    return profile

# 之前（使用 $ref）：
# Gemini 2.5 Pro 返回：{"profile": "我叫张三，28岁，住在北京"}  ❌
# Qwen3-max 返回：{"profile": "{\"name\": \"张三\", \"age\": 28, \"city\": \"北京\"}"}  ❌

# 现在（内联展开）：
# Gemini 2.5 Pro 返回：{"profile": {"name": "张三", "age": 28, "city": "北京"}}  ✅
# Qwen3-max 返回：{"profile": {"name": "张三", "age": 28, "city": "北京"}}  ✅
```

## [0.2.5] - 2025-04-11

### Added
- **Pydantic 对象保留支持**：当使用 `tool_use_behavior` 强制停止模式时，保留工具返回的 Pydantic 对象
  - 当 `tool_use_behavior="stop_on_first_tool"` 时，不再强制转换为字符串
  - 当 `tool_use_behavior={"stop_at_tool_names": [...]}` 时，保留原始对象类型
  - 当 `tool_use_behavior=custom_function` 时，保留原始对象类型
  - 支持 100% 可靠的结构化输出（通过 Function Calling）

### Enhanced
- **类型安全**：现在可以直接访问 `result.final_output.field_name`，无需解析字符串
- **数据验证**：Pydantic 在工具内部完成验证，无需二次解析
- **系统集成**：下游系统可以直接使用 Pydantic 对象，无需序列化/反序列化
- **向后兼容性**：默认行为（`tool_use_behavior="run_llm_again"`）保持不变，仍然转换为字符串

### Technical Details
- **修改范围**：仅修改 `src/agents/_run_impl.py` 第 366-375 行
- **逻辑优化**：当 `output_type` 未设置且 `tool_use_behavior != "run_llm_again"` 时，跳过字符串转换
- **测试覆盖**：添加了 6 个测试用例验证各种场景
- **代码质量**：通过所有 lint、format 和 mypy 检查

### Use Case Example
```python
from pydantic import BaseModel
from agents import Agent, Runner, function_tool

class UserProfile(BaseModel):
    name: str
    age: int

@function_tool
def extract_profile(text: str) -> UserProfile:
    return UserProfile(name="Alice", age=30)

agent = Agent(
    name="Extractor",
    tools=[extract_profile],
    tool_use_behavior="stop_on_first_tool"
)

result = await Runner.run(agent, "extract")
# result.final_output 现在是 UserProfile 对象，而不是字符串！
assert isinstance(result.final_output, UserProfile)
assert result.final_output.name == "Alice"
```

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
