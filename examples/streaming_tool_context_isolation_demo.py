"""
Streaming Tool 上下文隔离演示

本示例演示 streaming_tool 的上下文隔离机制，展示：
1. StreamingToolContextEvent 的自动包装
2. 内部 agent 事件与主 agent 事件的分离
3. 客户端如何处理不同类型的事件
4. 上下文隔离对对话历史的影响

核心概念：
- 内部 RunItemStreamEvent、RawResponsesStreamEvent 和 AgentUpdatedStreamEvent 被自动包装
- 只有 tool_output 影响对话历史
- 客户端仍能看到完整的内部进展
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from agents import (
    NotifyStreamEvent,
    StreamEvent,
    streaming_tool,
)

# 注意：在实际使用中，请使用真实的模型
# from agents.models.fake import FakeModel


# ============================================================================
# 示例：嵌套 Agent 的 streaming_tool
# ============================================================================

@streaming_tool
async def nested_agent_tool(task: str) -> AsyncGenerator[StreamEvent | str, Any]:
    """包含嵌套 agent 的 streaming_tool

    这个工具内部会运行一个 agent，演示上下文隔离机制。
    """
    yield NotifyStreamEvent(data=f"🚀 开始执行嵌套任务: {task}")

    # 模拟内部处理逻辑（在实际使用中，这里会是真实的 agent）
    yield NotifyStreamEvent(data="🔧 模拟内部处理...")

    # 模拟一些处理步骤
    steps = ["数据验证", "核心计算", "结果整理"]
    for step in steps:
        yield NotifyStreamEvent(data=f"  • {step}")
        await asyncio.sleep(0.2)

    yield NotifyStreamEvent(data="✅ 内部处理完成")

    # 最终结果
    yield f"嵌套任务 '{task}' 完成。处理了 {len(steps)} 个步骤。"


# ============================================================================
# 演示函数
# ============================================================================

async def demo_context_isolation_events():
    """演示上下文隔离的事件流"""
    print("=" * 70)
    print("Streaming Tool 上下文隔离事件演示")
    print("=" * 70)

    print("\n🎯 演示概念（模拟事件流）:")
    print("-" * 50)

    # 模拟事件流演示
    print("  [1] 📢 NotifyStreamEvent: 🚀 开始执行嵌套任务: 数据分析")
    print("  [2] 🔒 StreamingToolContextEvent:")
    print("       工具: nested_agent_tool")
    print("       调用ID: call_123")
    print("       内部事件类型: RunItemStreamEvent")
    print("  [3] 📢 NotifyStreamEvent: 🔧 模拟内部处理...")
    print("  [4] 🔒 StreamingToolContextEvent:")
    print("       工具: nested_agent_tool")
    print("       调用ID: call_123")
    print("       内部事件类型: RawResponsesStreamEvent")
    print("  [5] 📢 NotifyStreamEvent: ✅ 内部处理完成")
    print("  [6] 📝 RunItemStreamEvent (主Agent的工具输出)")

    # 模拟统计
    context_events = 2  # 模拟的 StreamingToolContextEvent 数量
    notify_events = 3   # 模拟的 NotifyStreamEvent 数量
    run_item_events = 1 # 模拟的其他事件数量
    event_count = context_events + notify_events + run_item_events

    print("\n📊 事件统计:")
    print(f"  • 总事件数: {event_count}")
    print(f"  • StreamingToolContextEvent: {context_events} (内部事件被包装)")
    print(f"  • NotifyStreamEvent: {notify_events} (直接传递)")
    print(f"  • 其他事件: {run_item_events} (主Agent事件)")

    # 模拟对话历史分析
    print("\n🔍 对话历史分析 (模拟):")
    print("  • to_input_list 项目数: 4")
    print("    [1] 用户: 请执行数据分析任务")
    print("    [2] 工具调用: nested_agent_tool")
    print("    [3] 工具输出: 嵌套任务 '数据分析' 完成。处理了 3 个步骤。")
    print("    [4] 助手: 任务已完成")

    print("\n✅ 上下文隔离验证:")
    print("  • 内部处理的消息没有出现在对话历史中")
    print("  • 只有主Agent的消息和工具输出被保留")
    print("  • 客户端仍能通过 StreamingToolContextEvent 看到内部进展")


async def demo_client_event_handling():
    """演示客户端事件处理逻辑"""
    print("\n" + "=" * 70)
    print("客户端事件处理逻辑演示")
    print("=" * 70)

    print("\n📋 推荐的客户端事件处理模式:")

    client_code = '''
// JavaScript 客户端处理示例
class StreamingToolEventHandler {
    constructor() {
        this.internalProgressContainer = document.getElementById('internal-progress');
        this.mainConversationContainer = document.getElementById('main-conversation');
        this.notificationContainer = document.getElementById('notifications');
    }
    
    handleEvent(eventData) {
        switch(eventData.event_type) {
            case 'streaming_tool_context_event':
                // 内部事件 - 仅用于展示，不影响对话
                this.showInternalProgress(eventData);
                break;
                
            case 'run_item_stream_event':
                // 主对话事件 - 更新对话历史
                this.updateMainConversation(eventData);
                break;
                
            case 'notify_stream_event':
                // 通知事件 - 显示进度通知
                this.showNotification(eventData);
                break;
                
            case 'streaming_tool_start_event':
                // 工具开始 - 显示工具状态
                this.showToolStart(eventData);
                break;

            case 'streaming_tool_end_event':
                // 工具结束 - 更新工具状态
                this.showToolEnd(eventData);
                break;
        }
    }
    
    showInternalProgress(eventData) {
        const internalEvent = eventData.internal_event;
        const toolName = eventData.tool_name;
        
        // 在专门的内部进度区域显示
        const progressItem = document.createElement('div');
        progressItem.className = 'internal-progress-item';
        progressItem.innerHTML = `
            <span class="tool-name">${toolName}</span>: 
            <span class="event-type">${internalEvent.event_type}</span>
        `;
        
        this.internalProgressContainer.appendChild(progressItem);
        
        // 可选：自动滚动到最新进度
        progressItem.scrollIntoView({ behavior: 'smooth' });
    }
    
    updateMainConversation(eventData) {
        // 这些事件会影响对话历史，需要持久化
        const conversationItem = this.createConversationItem(eventData);
        this.mainConversationContainer.appendChild(conversationItem);
        
        // 保存到对话历史
        this.saveToConversationHistory(eventData);
    }
    
    showNotification(eventData) {
        // 显示临时通知
        const notification = document.createElement('div');
        notification.className = `notification ${eventData.tag || 'info'}`;
        notification.textContent = eventData.data;
        
        this.notificationContainer.appendChild(notification);
        
        // 自动消失
        setTimeout(() => {
            notification.remove();
        }, 5000);
    }
}

// 使用示例
const eventHandler = new StreamingToolEventHandler();

eventSource.onmessage = function(event) {
    const eventData = JSON.parse(event.data);
    eventHandler.handleEvent(eventData);
};
'''

    print(client_code)

    print("\n🎯 关键要点:")
    print("  1. StreamingToolContextEvent 仅用于展示，不保存到对话历史")
    print("  2. RunItemStreamEvent 是真实的对话事件，需要持久化")
    print("  3. NotifyStreamEvent 用于临时通知和进度展示")
    print("  4. 分离展示逻辑，提供更好的用户体验")


if __name__ == "__main__":
    """运行上下文隔离演示"""
    async def main():
        await demo_context_isolation_events()
        await demo_client_event_handling()

        print("\n" + "=" * 70)
        print("🎉 上下文隔离演示完成！")
        print("📚 更多信息请参考: docs/streaming_tool_context_isolation.md")
        print("=" * 70)

    asyncio.run(main())
