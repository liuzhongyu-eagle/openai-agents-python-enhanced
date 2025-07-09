# 流式工具事件支持

本文档介绍 helpdesk_agent 对 agents SDK 中新增的 `@streaming_tool` 功能的支持，以及相关的流式事件处理机制。

## 概述

agents SDK 引入了 `@streaming_tool` 装饰器，允许工具在执行过程中实时发送进度通知和状态更新。helpdesk_agent 已扩展其事件处理机制来完全兼容这些新的流式事件。

## 支持的流式工具事件类型

### 1. 工具通知事件 (tool.notification)

用于工具执行过程中的进度更新和状态通知。

**API 事件格式：**
```json
{
  "event_id": "evt_abc123",
  "job_id": "job_456",
  "conversation_id": "conv_789",
  "event_type": "tool.notification",
  "payload": {
    "tool_name": "data_processor",
    "tool_call_id": "call_123",
    "message": "正在处理数据...",
    "is_delta": false,
    "tag": "progress"
  },
  "timestamp": "2025-01-08T10:30:00Z",
  "agent_name": "DataAgent",
  "turn": 1
}
```

**字段说明：**
- `tool_name`: 生成通知的工具名称
- `tool_call_id`: 工具调用的唯一标识符
- `message`: 通知消息内容
- `is_delta`: 是否为增量消息（用于打字机效果）
- `tag`: 可选的通知标签，用于 UI 分类

### 2. 工具流开始事件 (tool.stream.started)

标志着流式工具开始执行。

**API 事件格式：**
```json
{
  "event_id": "evt_def456",
  "job_id": "job_456",
  "conversation_id": "conv_789",
  "event_type": "tool.stream.started",
  "payload": {
    "tool_name": "data_pipeline",
    "tool_call_id": "call_123",
    "input_args": {
      "source_url": "https://example.com/api",
      "batch_size": 100
    }
  },
  "timestamp": "2025-01-08T10:30:00Z",
  "agent_name": "DataAgent",
  "turn": 1
}
```

### 3. 工具流结束事件 (tool.stream.ended)

标志着流式工具执行完成。

**API 事件格式：**
```json
{
  "event_id": "evt_ghi789",
  "job_id": "job_456",
  "conversation_id": "conv_789",
  "event_type": "tool.stream.ended",
  "payload": {
    "tool_name": "data_pipeline",
    "tool_call_id": "call_123",
    "input_args": null
  },
  "timestamp": "2025-01-08T10:30:05Z",
  "agent_name": "DataAgent",
  "turn": 1
}
```

## 使用示例

### 创建流式工具

```python
from agents import streaming_tool, NotifyStreamEvent
import asyncio
from typing import AsyncGenerator, Any
from agents.stream_events import StreamEvent

@streaming_tool
async def data_analysis_tool(dataset_path: str) -> AsyncGenerator[StreamEvent | str, Any]:
    """数据分析工具 - 演示流式进度更新"""
    
    # 阶段1：数据加载
    yield NotifyStreamEvent(data="[1/4] 正在加载数据集...", tag="loading")
    await asyncio.sleep(1)
    
    # 阶段2：数据清洗
    yield NotifyStreamEvent(data="[2/4] ✅ 数据加载完成，开始清洗数据", tag="success")
    await asyncio.sleep(1)
    
    # 阶段3：特征提取（带打字机效果）
    yield NotifyStreamEvent(data="[3/4] 正在提取特征：", tag="processing")
    
    features = ["特征A", "特征B", "特征C", "特征D"]
    for feature in features:
        yield NotifyStreamEvent(data=f" {feature}", is_delta=True, tag="feature")
        await asyncio.sleep(0.3)
    
    # 阶段4：分析完成
    yield NotifyStreamEvent(data="\n[4/4] ✅ 分析完成！", tag="complete")
    
    # 最终结果（必须是最后一个 yield）
    yield f"数据分析完成！处理了数据集 {dataset_path}，提取了 {len(features)} 个特征。"
```

### 在 Agent 中使用

```python
from agents import Agent

# 创建使用流式工具的 Agent
data_agent = Agent(
    name="DataAnalysisAgent",
    instructions="你是一个数据分析专家。使用 data_analysis_tool 来分析数据集。",
    tools=[data_analysis_tool]
)
```

### 客户端事件处理

客户端可以监听不同类型的流式工具事件来提供丰富的用户体验：

```javascript
// 监听流式事件
eventSource.onmessage = function(event) {
    const data = JSON.parse(event.data);
    
    switch(data.event_type) {
        case 'tool.stream.started':
            console.log(`工具 ${data.payload.tool_name} 开始执行`);
            showToolProgress(data.payload.tool_name, 'started');
            break;
            
        case 'tool.notification':
            if (data.payload.is_delta) {
                // 打字机效果
                appendToOutput(data.payload.message);
            } else {
                // 状态更新
                updateProgress(data.payload.message, data.payload.tag);
            }
            break;
            
        case 'tool.stream.ended':
            console.log(`工具 ${data.payload.tool_name} 执行完成`);
            showToolProgress(data.payload.tool_name, 'completed');
            break;
    }
};
```

## 事件流示例

一个完整的流式工具执行会产生以下事件序列：

1. `tool.stream.started` - 工具开始执行
2. 多个 `tool.notification` - 进度更新和状态通知
3. `tool.stream.ended` - 工具执行完成
4. `item.completed` - 工具调用项完成（包含最终结果）

## 设计原则

### 严格分离"过程展示"和"最终结果"

- **过程展示**: `yield NotifyStreamEvent(...)` - 不影响对话历史，纯展示性质
- **最终结果**: `yield "字符串结果"` - 作为最后一个 yield，影响对话历史

### 自动括号事件

`@streaming_tool` 装饰器会自动生成 `ToolStreamStartEvent` 和 `ToolStreamEndEvent`，为客户端提供清晰的流程边界。

### 工具信息注入

所有 `NotifyStreamEvent` 会自动注入 `tool_name` 和 `tool_call_id` 信息，确保事件可以正确关联到对应的工具调用。

## 兼容性说明

- 完全向后兼容现有的 `@function_tool` 工具
- 新的流式事件不会影响现有的事件处理逻辑
- 客户端可以选择性地处理流式工具事件，忽略的事件不会影响基本功能

## 最佳实践

1. **合理使用通知频率**: 避免过于频繁的通知事件，以免影响性能
2. **有意义的标签**: 使用有意义的 `tag` 值来帮助客户端进行 UI 分类
3. **增量消息**: 对于长文本输出，使用 `is_delta=True` 实现打字机效果
4. **错误处理**: 在工具中适当处理异常，确保始终能产生最终结果

## 测试

项目包含完整的测试套件来验证流式工具事件的处理：

```bash
# 运行流式工具事件测试
pytest tests/test_streaming_tool_events.py -v
```

测试覆盖了所有事件类型的处理、Schema 验证和集成场景。
