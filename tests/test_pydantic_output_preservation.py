# Copyright

"""
Tests for preserving Pydantic objects when using tool_use_behavior stop modes.

This test suite verifies that when using tool_use_behavior modes that stop at tool calls
(e.g., "stop_on_first_tool", {"stop_at_tool_names": [...]}, or custom functions),
the SDK preserves the original return type from tools instead of converting to strings.
"""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from agents import Agent, Runner, function_tool

from .fake_model import FakeModel
from .test_responses import get_function_tool_call, get_text_message


class UserProfile(BaseModel):
    """Test Pydantic model for user profile."""

    name: str
    age: int
    city: str


class WeatherData(BaseModel):
    """Test Pydantic model for weather data."""

    temperature: int
    conditions: str


@function_tool
def extract_user_profile() -> UserProfile:
    """Extract user profile from text."""
    return UserProfile(name="张伟", age=28, city="北京")


@function_tool
def get_weather() -> WeatherData:
    """Get weather information."""
    return WeatherData(temperature=20, conditions="晴天")


@pytest.mark.asyncio
async def test_stop_on_first_tool_preserves_pydantic_object():
    """测试 stop_on_first_tool 保留 Pydantic 对象而不是转换为字符串"""
    model = FakeModel()
    agent = Agent(
        name="ProfileExtractor",
        model=model,
        tools=[extract_user_profile],
        tool_use_behavior="stop_on_first_tool",
        # 注意：不设置 output_type，让它默认为 None
    )

    model.add_multiple_turn_outputs(
        [
            [
                get_text_message("正在提取用户信息"),
                get_function_tool_call("extract_user_profile", None),
            ],
        ]
    )

    result = await Runner.run(agent, input="提取用户信息")

    # 应该返回 Pydantic 对象，而不是字符串
    assert isinstance(result.final_output, UserProfile), (
        f"Expected UserProfile object, got {type(result.final_output)}"
    )
    assert result.final_output.name == "张伟"
    assert result.final_output.age == 28
    assert result.final_output.city == "北京"


@pytest.mark.asyncio
async def test_run_llm_again_converts_to_string():
    """测试 run_llm_again（默认行为）仍然转换为字符串"""
    model = FakeModel()
    agent = Agent(
        name="ProfileExtractor",
        model=model,
        tools=[extract_user_profile],
        tool_use_behavior="run_llm_again",  # 默认行为
        # 不设置 output_type
    )

    model.add_multiple_turn_outputs(
        [
            [
                get_text_message("正在提取用户信息"),
                get_function_tool_call("extract_user_profile", None),
            ],
            # 第二轮：LLM 接收工具结果后生成最终响应
            [get_text_message("用户是张伟，28岁，来自北京")],
        ]
    )

    result = await Runner.run(agent, input="提取用户信息")

    # 应该返回字符串（LLM 的最终响应）
    assert isinstance(result.final_output, str)
    assert "张伟" in result.final_output or "28" in result.final_output


@pytest.mark.asyncio
async def test_explicit_str_output_type_converts_to_string():
    """测试明确指定 output_type=str 时转换为字符串"""
    model = FakeModel()
    agent = Agent(
        name="ProfileExtractor",
        model=model,
        tools=[extract_user_profile],
        tool_use_behavior="stop_on_first_tool",
        output_type=str,  # 明确要求字符串输出
    )

    model.add_multiple_turn_outputs(
        [
            [
                get_text_message("正在提取用户信息"),
                get_function_tool_call("extract_user_profile", None),
            ],
        ]
    )

    result = await Runner.run(agent, input="提取用户信息")

    # 应该转换为字符串
    assert isinstance(result.final_output, str)
    # 字符串应该包含 Pydantic 对象的表示
    assert "张伟" in result.final_output
    assert "28" in result.final_output
    assert "北京" in result.final_output


@pytest.mark.asyncio
async def test_stop_at_tool_names_preserves_pydantic_object():
    """测试 stop_at_tool_names 保留 Pydantic 对象"""
    model = FakeModel()
    agent = Agent(
        name="WeatherAgent",
        model=model,
        tools=[extract_user_profile, get_weather],
        tool_use_behavior={"stop_at_tool_names": ["get_weather"]},
        # 不设置 output_type
    )

    model.add_multiple_turn_outputs(
        [
            [
                get_text_message("正在获取天气信息"),
                get_function_tool_call("get_weather", None),
            ],
        ]
    )

    result = await Runner.run(agent, input="获取天气")

    # 应该返回 Pydantic 对象
    assert isinstance(result.final_output, WeatherData), (
        f"Expected WeatherData object, got {type(result.final_output)}"
    )
    assert result.final_output.temperature == 20
    assert result.final_output.conditions == "晴天"


@pytest.mark.asyncio
async def test_explicit_pydantic_output_type_preserves_object():
    """测试明确指定 Pydantic output_type 时保留对象"""
    model = FakeModel()
    agent = Agent(
        name="ProfileExtractor",
        model=model,
        tools=[extract_user_profile],
        tool_use_behavior="stop_on_first_tool",
        output_type=UserProfile,  # 明确指定 Pydantic 类型
    )

    model.add_multiple_turn_outputs(
        [
            [
                get_text_message("正在提取用户信息"),
                get_function_tool_call("extract_user_profile", None),
            ],
        ]
    )

    result = await Runner.run(agent, input="提取用户信息")

    # 应该返回 Pydantic 对象
    assert isinstance(result.final_output, UserProfile)
    assert result.final_output.name == "张伟"
    assert result.final_output.age == 28
    assert result.final_output.city == "北京"


@pytest.mark.asyncio
async def test_multiple_tools_stop_on_first_preserves_first_pydantic():
    """测试多个工具调用时，stop_on_first_tool 保留第一个 Pydantic 对象"""
    model = FakeModel()
    agent = Agent(
        name="MultiToolAgent",
        model=model,
        tools=[extract_user_profile, get_weather],
        tool_use_behavior="stop_on_first_tool",
        # 不设置 output_type
    )

    model.add_multiple_turn_outputs(
        [
            [
                get_text_message("正在处理"),
                get_function_tool_call("extract_user_profile", None),
                get_function_tool_call("get_weather", None),
            ],
        ]
    )

    result = await Runner.run(agent, input="处理请求")

    # 应该返回第一个工具的 Pydantic 对象
    assert isinstance(result.final_output, UserProfile), (
        f"Expected UserProfile object (first tool), got {type(result.final_output)}"
    )
    assert result.final_output.name == "张伟"
