#!/usr/bin/env python3
"""
流式工具事件演示

展示 helpdesk_agent 对 agents SDK 中新增的 @streaming_tool 功能的支持。
本示例演示了如何创建和使用流式工具，以及如何处理相关的流式事件。
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Any

from agents import Agent, NotifyStreamEvent, streaming_tool
from agents.stream_events import StreamEvent


@streaming_tool
async def data_analysis_tool(dataset_name: str, analysis_type: str = "basic") -> AsyncGenerator[StreamEvent | str, Any]:
    """
    数据分析工具 - 演示流式进度更新和通知事件
    
    Args:
        dataset_name: 要分析的数据集名称
        analysis_type: 分析类型 ("basic" 或 "advanced")
    """

    # 阶段1：数据加载
    yield NotifyStreamEvent(
        data=f"[1/4] 正在加载数据集 '{dataset_name}'...",
        tag="loading"
    )
    await asyncio.sleep(0.8)

    # 阶段2：数据预处理
    yield NotifyStreamEvent(
        data="[2/4] ✅ 数据加载完成，开始预处理数据",
        tag="success"
    )
    await asyncio.sleep(0.6)

    # 阶段3：执行分析（根据分析类型显示不同的进度）
    if analysis_type == "advanced":
        yield NotifyStreamEvent(
            data="[3/4] 执行高级分析：",
            tag="processing"
        )

        # 演示打字机效果
        analysis_steps = ["统计分析", "相关性分析", "回归分析", "聚类分析", "异常检测"]
        for i, step in enumerate(analysis_steps):
            yield NotifyStreamEvent(
                data=f" {step}",
                is_delta=True,
                tag="analysis_step"
            )
            await asyncio.sleep(0.4)

            # 每个步骤完成后的进度更新
            if i < len(analysis_steps) - 1:
                yield NotifyStreamEvent(
                    data=" ✓",
                    is_delta=True,
                    tag="step_complete"
                )
    else:
        yield NotifyStreamEvent(
            data="[3/4] 执行基础分析...",
            tag="processing"
        )
        await asyncio.sleep(1.0)

    # 阶段4：生成报告
    yield NotifyStreamEvent(
        data="\n[4/4] 正在生成分析报告...",
        tag="reporting"
    )
    await asyncio.sleep(0.5)

    yield NotifyStreamEvent(
        data="✅ 分析完成！",
        tag="complete"
    )

    # 最终结果（必须是最后一个 yield）
    analysis_result = f"数据分析完成！\n" \
                     f"- 数据集: {dataset_name}\n" \
                     f"- 分析类型: {analysis_type}\n" \
                     f"- 处理时间: 约 {3.5 if analysis_type == 'advanced' else 2.5} 秒"

    yield analysis_result


@streaming_tool
async def report_generator_tool(data_summary: str, format_type: str = "markdown") -> AsyncGenerator[StreamEvent | str, Any]:
    """
    报告生成工具 - 演示流式文本生成
    
    Args:
        data_summary: 数据摘要
        format_type: 报告格式 ("markdown", "html", "pdf")
    """

    yield NotifyStreamEvent(
        data=f"开始生成 {format_type.upper()} 格式报告...",
        tag="start"
    )

    # 模拟报告生成过程
    yield NotifyStreamEvent(
        data="正在生成报告内容：",
        tag="generating"
    )

    # 演示流式文本生成（打字机效果）
    report_content = f"""
# 数据分析报告

## 摘要
{data_summary}

## 详细分析
本次分析采用了多种统计方法，包括描述性统计、相关性分析等。

## 结论
数据质量良好，分析结果可信度高。

## 建议
建议进一步收集更多样本数据以提高分析精度。
"""

    # 逐字符流式输出（模拟真实的 LLM 生成过程）
    for char in report_content:
        yield NotifyStreamEvent(
            data=char,
            is_delta=True,
            tag="content"
        )
        await asyncio.sleep(0.02)  # 控制输出速度

    yield NotifyStreamEvent(
        data=f"\n✅ {format_type.upper()} 报告生成完成！",
        tag="complete"
    )

    # 最终结果
    yield f"报告生成成功！格式: {format_type}, 长度: {len(report_content)} 字符"


def create_data_analysis_agent():
    """创建数据分析 Agent"""
    return Agent(
        name="DataAnalysisAgent",
        instructions="""
你是一个专业的数据分析专家。你可以使用以下工具：

1. data_analysis_tool: 分析数据集并生成统计结果
2. report_generator_tool: 根据分析结果生成格式化报告

请根据用户的需求选择合适的工具，并提供详细的分析和报告。
        """.strip(),
        tools=[data_analysis_tool, report_generator_tool]
    )


async def demo_streaming_tool_events():
    """演示流式工具事件的完整流程"""
    print("=" * 80)
    print("流式工具事件演示")
    print("=" * 80)

    # 创建 Agent
    agent = create_data_analysis_agent()

    print(f"创建了 Agent: {agent.name}")
    print(f"可用工具: {[tool.name for tool in agent.tools]}")
    print()

    # 演示直接调用流式工具
    print("1. 直接调用流式工具演示:")
    print("-" * 40)

    from agents.run_context import RunContextWrapper

    ctx = RunContextWrapper(context=None)

    print("调用 data_analysis_tool (基础分析):")
    async for event in data_analysis_tool.on_invoke_tool(
        ctx,
        '{"dataset_name": "sales_data.csv", "analysis_type": "basic"}',
        "demo_call_1"
    ):
        if isinstance(event, NotifyStreamEvent):
            tag_info = f" [{event.tag}]" if event.tag else ""
            delta_info = " (增量)" if event.is_delta else ""
            print(f"  通知{tag_info}{delta_info}: {repr(event.data)}")
        elif isinstance(event, str):
            print(f"  最终结果: {event}")

    print()
    print("调用 report_generator_tool (流式文本生成):")

    # 收集增量文本以演示打字机效果
    accumulated_content = ""
    async for event in report_generator_tool.on_invoke_tool(
        ctx,
        '{"data_summary": "销售数据分析显示增长趋势良好", "format_type": "markdown"}',
        "demo_call_2"
    ):
        if isinstance(event, NotifyStreamEvent):
            if event.is_delta and event.tag == "content":
                accumulated_content += event.data
                # 只显示每10个字符的进度（避免输出过多）
                if len(accumulated_content) % 10 == 0:
                    print(f"  内容生成中... (已生成 {len(accumulated_content)} 字符)")
            elif not event.is_delta:
                tag_info = f" [{event.tag}]" if event.tag else ""
                print(f"  通知{tag_info}: {event.data}")
        elif isinstance(event, str):
            print(f"  最终结果: {event}")
            print(f"  生成的内容长度: {len(accumulated_content)} 字符")

    print()
    print("=" * 80)
    print("演示完成！")
    print()
    print("在实际的 helpdesk_agent 流式响应中，这些事件会被转换为:")
    print("- tool.stream.started: 工具开始执行")
    print("- tool.notification: 进度通知和增量内容")
    print("- tool.stream.ended: 工具执行完成")
    print("- item.completed: 工具调用项完成（包含最终结果）")


if __name__ == "__main__":
    asyncio.run(demo_streaming_tool_events())
