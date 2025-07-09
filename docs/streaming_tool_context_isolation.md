# Streaming Tool 上下文隔离机制

本文档描述了 OpenAI Agents SDK 中 streaming_tool 的上下文隔离机制设计和实现。

## 概述

streaming_tool 是一个特殊的工具类型，允许在工具执行过程中向客户端发送实时事件。为了确保 streaming_tool 遵循工具的基本原则，SDK 实现了上下文隔离机制：

- **过程展示**：客户端可以看到内部进展（通过流式事件）
- **结果输出**：只有 `tool_output` 影响对话历史
- **上下文隔离**：内部 agent 的 `RunItem` 不会进入主 agent 的对话历史

## 问题背景

在引入 streaming_tool 之前，传统的 function_tool 机制比较简单：
1. 调用工具函数
2. 获取返回值
3. 将返回值作为 tool_output 加入对话历史

但是 streaming_tool 更复杂：
1. 可能内部运行 agent（如 `agent.as_tool(streaming=True)`）
2. 内部 agent 会产生各种 `RunItem`（MessageOutputItem、ReasoningItem 等）
3. 这些内部 `RunItem` 不应该影响主 agent 的对话历史

## 解决方案：StreamingToolContextEvent

### 设计原理

我们引入了 `StreamingToolContextEvent` 作为事件容器，将 streaming_tool 内部产生的事件包装起来：

```python
@dataclass
class StreamingToolContextEvent:
    """streaming_tool 内部上下文事件容器
    
    用于包装 streaming_tool 内部产生的事件，这些事件仅用于展示，
    不会影响主 agent 的对话历史。实现上下文隔离的关键机制。
    """
    tool_name: str
    """生成此事件的 streaming_tool 名称"""
    
    tool_call_id: str
    """streaming_tool 调用的唯一标识符"""
    
    internal_event: RunItemStreamEvent | RawResponsesStreamEvent | AgentUpdatedStreamEvent
    """被包装的内部事件，仅用于展示目的"""
    
    type: Literal["streaming_tool_context_event"] = "streaming_tool_context_event"
```

### 包装机制

在 streaming_tool 执行过程中，以下类型的事件会被自动包装：

1. **RunItemStreamEvent**：包含内部 agent 的 RunItem（MessageOutputItem、ReasoningItem 等）
2. **RawResponsesStreamEvent**：包含内部 agent 的原始响应（打字机效果等）
3. **AgentUpdatedStreamEvent**：包含内部 agent 切换事件

其他事件类型（如 `NotifyStreamEvent`、`StreamingToolStartEvent`、`StreamingToolEndEvent`）会直接传递，不被包装。

### 实现位置

包装逻辑在 `execute_streaming_tool_calls` 函数中实现：

```python
# 实现上下文隔离：包装来自 streaming_tool 内部的事件
if isinstance(event, (RunItemStreamEvent, RawResponsesStreamEvent, AgentUpdatedStreamEvent)):
    # 将内部事件包装为容器事件，实现上下文隔离
    wrapped_event = StreamingToolContextEvent(
        tool_name=tool_name,
        tool_call_id=tool_call_id,
        internal_event=event
    )
    streamed_result._event_queue.put_nowait(wrapped_event)
else:
    # 其他事件直接传递
    streamed_result._event_queue.put_nowait(event)
```

## 客户端处理

客户端可以这样处理不同类型的事件：

```javascript
eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.event_type) {
        case 'streaming_tool_context_event':
            // 展示内部进展，但知道这不影响对话
            showInternalProgress(data.internal_event);
            break;
            
        case 'run_item_stream_event':
            // 真实的对话事件
            updateConversation(data.item);
            break;
            
        case 'notify_stream_event':
            // 通知事件
            showNotification(data.data);
            break;
            
        case 'tool_stream_start_event':
            // 工具开始执行
            showToolStart(data.tool_name);
            break;
            
        case 'tool_stream_end_event':
            // 工具执行结束
            showToolEnd(data.tool_name);
            break;
    }
};
```

## 适用场景

这个机制适用于所有 streaming_tool 场景：

1. **直接调用**：agent 直接调用 `@streaming_tool` 装饰的函数
2. **agent.as_tool(streaming=True)**：agent 被封装为 streaming_tool
3. **嵌套调用**：streaming_tool 内部调用其他 streaming_tool

在所有这些场景中，内部产生的 `RunItemStreamEvent` 和 `RawResponsesStreamEvent` 都会被自动包装，确保上下文隔离。

## 优势

1. **语义清晰**：明确区分"展示事件"和"结果事件"
2. **完全隔离**：内部 `RunItem` 不会影响主 agent 的对话历史
3. **客户端友好**：仍能看到完整的内部进展，包括打字机效果
4. **扩展性好**：可以处理多层嵌套的 streaming_tool
5. **向后兼容**：不破坏现有功能，客户端可以选择性处理新事件类型

## 测试验证

SDK 包含了完整的测试用例来验证上下文隔离机制：

```python
@pytest.mark.asyncio
async def test_streaming_tool_context_isolation(self):
    """测试 streaming_tool 的上下文隔离功能"""
    # 验证内部 RunItem 事件被包装为 StreamingToolContextEvent
    # 验证 RawResponsesStreamEvent 也被正确包装
    # 验证 to_input_list 不包含内部事件
```

这确保了 streaming_tool 在提供丰富的实时反馈的同时，严格遵循上下文隔离原则。
