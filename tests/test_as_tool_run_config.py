"""
测试 Agent.as_tool() 方法的 run_config 参数传递功能
"""

import json

import pytest

from agents import Agent, ModelProvider, RunConfig, Runner
from agents.models.interface import Model

from .fake_model import FakeModel
from .test_responses import get_function_tool_call, get_text_message


class TrackingModelProvider(ModelProvider):
    """可以追踪调用的模型提供者，用于测试"""

    def __init__(self, name: str, supported_prefixes: list[str]):
        self.name = name
        self.supported_prefixes = supported_prefixes
        self.call_history: list[str | None] = []

    def get_model(self, model_name: str | None) -> Model:
        self.call_history.append(model_name)

        # 检查是否支持该前缀
        if model_name and "/" in model_name:
            prefix = model_name.split("/")[0]
            if prefix not in self.supported_prefixes:
                raise ValueError(f"Unknown prefix: {prefix}")

        # 返回一个 FakeModel
        fake_model = FakeModel()
        fake_model.set_next_output([get_text_message(f"Response from {self.name}")])
        return fake_model


class TestAsToolRunConfig:
    """测试 Agent.as_tool() 的 run_config 参数功能"""

    @pytest.mark.asyncio
    async def test_as_tool_without_run_config(self):
        """测试不传递 run_config 参数的默认行为"""

        # 创建一个简单的 Agent
        sub_agent = Agent(
            name="SubAgent",
            instructions="You are a sub agent",
            model="gpt-4o",  # 使用默认支持的模型
        )

        # 转换为工具（不传递 run_config）
        tool = sub_agent.as_tool(tool_name="sub_tool")

        # 验证工具创建成功
        assert tool is not None
        assert tool.name == "sub_tool"

    @pytest.mark.asyncio
    async def test_as_tool_with_custom_run_config_non_streaming(self):
        """测试非流式工具传递自定义 run_config"""

        # 创建自定义模型提供者
        custom_provider = TrackingModelProvider("CustomProvider", ["doubao", "deepseek"])
        run_config = RunConfig(model_provider=custom_provider)

        # 创建使用自定义前缀的 Agent
        sub_agent = Agent(
            name="SubAgent", instructions="You are a sub agent", model="doubao/test-model"
        )

        # 转换为工具，传递自定义 run_config
        tool = sub_agent.as_tool(tool_name="sub_tool", run_config=run_config)

        # 创建主 Agent
        main_agent = Agent(name="MainAgent", instructions="You are the main agent", tools=[tool])

        # 设置主 Agent 的模型输出，让它调用 sub_tool
        main_fake_model = FakeModel()
        main_fake_model.set_next_output(
            [
                get_function_tool_call("sub_tool", json.dumps({"input": "test input"})),
                get_text_message("Main agent completed"),
            ]
        )
        main_agent.model = main_fake_model

        # 运行主 Agent
        result = await Runner.run(
            main_agent,
            "Please use the sub tool",
            run_config=run_config,  # 使用相同的自定义提供者
        )

        # 验证自定义提供者被调用
        assert len(custom_provider.call_history) > 0
        assert "doubao/test-model" in custom_provider.call_history
        assert result.final_output is not None

    @pytest.mark.asyncio
    async def test_as_tool_with_custom_run_config_streaming(self):
        """测试流式工具传递自定义 run_config"""

        # 创建自定义模型提供者
        custom_provider = TrackingModelProvider("CustomProvider", ["deepseek"])
        run_config = RunConfig(model_provider=custom_provider)

        # 创建使用自定义前缀的 Agent
        sub_agent = Agent(
            name="SubAgent", instructions="You are a sub agent", model="deepseek/test-model"
        )

        # 转换为流式工具，传递自定义 run_config
        tool = sub_agent.as_tool(tool_name="sub_tool", streaming=True, run_config=run_config)

        # 创建主 Agent
        main_agent = Agent(name="MainAgent", instructions="You are the main agent", tools=[tool])

        # 设置主 Agent 的模型输出
        main_fake_model = FakeModel()
        main_fake_model.set_next_output(
            [
                get_function_tool_call("sub_tool", json.dumps({"input": "test input"})),
                get_text_message("Main agent completed"),
            ]
        )
        main_agent.model = main_fake_model

        # 运行主 Agent（流式）
        result = Runner.run_streamed(main_agent, "Please use the sub tool", run_config=run_config)

        # 收集所有事件
        events = []
        async for event in result.stream_events():
            events.append(event)

        # 验证自定义提供者被调用
        assert len(custom_provider.call_history) > 0
        assert "deepseek/test-model" in custom_provider.call_history
        assert result.final_output is not None

    @pytest.mark.asyncio
    async def test_as_tool_run_config_isolation(self):
        """测试不同工具可以使用不同的 run_config"""

        # 创建两个不同的模型提供者
        provider1 = TrackingModelProvider("Provider1", ["doubao"])
        provider2 = TrackingModelProvider("Provider2", ["deepseek"])

        config1 = RunConfig(model_provider=provider1)
        config2 = RunConfig(model_provider=provider2)

        # 创建两个使用不同前缀的 Agent
        agent1 = Agent(name="Agent1", instructions="You are agent 1", model="doubao/model1")

        agent2 = Agent(name="Agent2", instructions="You are agent 2", model="deepseek/model2")

        # 转换为工具，使用不同的 run_config
        tool1 = agent1.as_tool(tool_name="tool1", run_config=config1)
        tool2 = agent2.as_tool(tool_name="tool2", run_config=config2)

        # 创建主 Agent
        main_agent = Agent(
            name="MainAgent", instructions="You are the main agent", tools=[tool1, tool2]
        )

        # 设置主 Agent 调用两个工具
        main_fake_model = FakeModel()
        main_fake_model.set_next_output(
            [
                get_function_tool_call("tool1", json.dumps({"input": "test1"})),
                get_function_tool_call("tool2", json.dumps({"input": "test2"})),
                get_text_message("Main agent completed"),
            ]
        )
        main_agent.model = main_fake_model

        # 运行主 Agent
        result = await Runner.run(
            main_agent,
            "Please use both tools",
            run_config=RunConfig(),  # 使用默认配置
        )

        # 验证两个提供者都被正确调用
        assert len(provider1.call_history) > 0
        assert "doubao/model1" in provider1.call_history

        assert len(provider2.call_history) > 0
        assert "deepseek/model2" in provider2.call_history

        assert result.final_output is not None

    @pytest.mark.asyncio
    async def test_as_tool_backward_compatibility(self):
        """测试向后兼容性：现有代码应该继续工作"""

        # 创建 Agent
        agent = Agent(name="TestAgent", instructions="You are a test agent")

        # 使用旧的 API（不传递 run_config）
        tool = agent.as_tool(tool_name="test_tool", tool_description="A test tool", streaming=False)

        # 验证工具创建成功
        assert tool is not None
        assert tool.name == "test_tool"
        # 注意：不是所有工具类型都有 description 属性，所以我们只检查基本属性

        # 流式版本
        streaming_tool = agent.as_tool(
            tool_name="streaming_test_tool", streaming=True, enable_bracketing=True
        )

        assert streaming_tool is not None
        assert streaming_tool.name == "streaming_test_tool"
