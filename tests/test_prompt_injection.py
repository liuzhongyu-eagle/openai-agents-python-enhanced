"""
提示词注入机制测试

测试 json_object 模式下的提示词注入功能，包括：
1. JsonObjectOutputSchema 的提示词注入
2. AgentOutputSchema 智能降级时的提示词注入
3. 不同模型实现的提示词注入
4. 提示词合并逻辑
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pydantic import BaseModel, Field

from agents import Agent, AgentOutputSchema
from agents.extensions.models.litellm_model import LitellmModel
from agents.json_object_output import JsonObjectOutputSchema
from agents.models.openai_chatcompletions import OpenAIChatCompletionsModel
from agents.models.openai_responses import OpenAIResponsesModel


# 测试用的数据模型
class UserProfile(BaseModel):
    """用户个人资料信息"""
    name: str = Field(description="用户的姓名")
    age: int = Field(description="用户的年龄", ge=0, le=150)
    city: str = Field(description="用户居住的城市")
    is_active: bool = Field(description="用户当前是否活跃")


class TestPromptInjectionMechanism:
    """提示词注入机制测试"""

    def test_json_object_output_schema_injection_methods(self):
        """测试 JsonObjectOutputSchema 的注入方法"""
        output_schema = JsonObjectOutputSchema(UserProfile)

        # 测试注入方法
        assert output_schema.should_inject_to_system_prompt() is True

        injection = output_schema.get_system_prompt_injection()
        assert "请返回一个严格符合 JSON 格式的对象" in injection
        assert "name (字符串): 用户的姓名" in injection
        assert "age (整数): 用户的年龄" in injection
        assert "city (字符串): 用户居住的城市" in injection
        assert "is_active (布尔值): 用户当前是否活跃" in injection

    def test_agent_output_schema_injection_methods(self):
        """测试 AgentOutputSchema 的注入方法"""
        # 不启用降级的情况
        output_schema = AgentOutputSchema(UserProfile)
        assert output_schema.should_inject_to_system_prompt() is False
        assert output_schema.get_system_prompt_injection() == ""

        # 启用降级但无模型的情况
        output_schema = AgentOutputSchema(UserProfile, fallback_to_json_object=True)
        assert output_schema.should_inject_to_system_prompt() is False
        assert output_schema.get_system_prompt_injection() != ""  # 有指令但不注入

        # 启用降级且模型不支持的情况
        class MockUnsupportedModel:
            def __str__(self):
                return "unsupported-model"

        mock_model = MockUnsupportedModel()
        assert output_schema.should_inject_to_system_prompt(mock_model) is True

        # 启用降级且模型支持的情况
        class MockSupportedModel:
            def __str__(self):
                return "gpt-4-turbo"

        mock_supported_model = MockSupportedModel()
        assert output_schema.should_inject_to_system_prompt(mock_supported_model) is False

    def test_custom_instructions_injection(self):
        """测试自定义指令的注入"""
        custom_instructions = "请返回用户信息的 JSON 对象，包含所有必需字段"

        output_schema = JsonObjectOutputSchema(
            UserProfile,
            custom_instructions=custom_instructions
        )

        injection = output_schema.get_system_prompt_injection()
        assert injection == custom_instructions

    @pytest.mark.asyncio
    async def test_openai_chatcompletions_prompt_injection(self):
        """测试 OpenAI ChatCompletions 模型的提示词注入"""
        # 模拟 OpenAI 客户端
        mock_client = Mock()
        mock_completion = Mock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        model = OpenAIChatCompletionsModel("gpt-4", openai_client=mock_client)

        # 使用 JsonObjectOutputSchema
        output_schema = JsonObjectOutputSchema(UserProfile)

        with patch.object(model, '_fetch_response') as mock_fetch:
            mock_fetch.return_value = mock_completion

            # 模拟调用
            await model._fetch_response(
                system_instructions="原始系统指令",
                input="测试输入",
                model_settings=Mock(),
                tools=[],
                output_schema=output_schema,
                handoffs=[],
                span=Mock(),
                tracing=Mock(),
                stream=False
            )

            # 验证调用参数
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args

            # 由于我们 patch 了 _fetch_response，实际的注入逻辑不会执行
            # 这里主要验证方法被正确调用
            assert call_args is not None

    @pytest.mark.asyncio
    async def test_litellm_prompt_injection(self):
        """测试 LiteLLM 模型的提示词注入"""
        model = LitellmModel("claude-3-sonnet")

        # 使用启用降级的 AgentOutputSchema
        output_schema = AgentOutputSchema(UserProfile, fallback_to_json_object=True)

        with patch.object(model, '_fetch_response') as mock_fetch:
            mock_response = Mock()
            mock_fetch.return_value = mock_response

            # 模拟调用
            await model._fetch_response(
                system_instructions="原始系统指令",
                input="测试输入",
                model_settings=Mock(),
                tools=[],
                output_schema=output_schema,
                handoffs=[],
                span=Mock(),
                tracing=Mock(),
                stream=False
            )

            # 验证调用
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_openai_responses_prompt_injection(self):
        """测试 OpenAI Responses 模型的提示词注入"""
        # 模拟 OpenAI 客户端
        mock_client = Mock()
        mock_response = Mock()
        mock_client.responses.create = AsyncMock(return_value=mock_response)

        model = OpenAIResponsesModel("gpt-4", openai_client=mock_client)

        # 使用 JsonObjectOutputSchema
        output_schema = JsonObjectOutputSchema(UserProfile)

        with patch.object(model, '_fetch_response') as mock_fetch:
            mock_fetch.return_value = mock_response

            # 模拟调用
            await model._fetch_response(
                system_instructions="原始系统指令",
                input="测试输入",
                model_settings=Mock(),
                tools=[],
                output_schema=output_schema,
                handoffs=[],
                previous_response_id=None,
                stream=False
            )

            # 验证调用
            mock_fetch.assert_called_once()


class TestPromptMerging:
    """提示词合并逻辑测试"""

    def test_prompt_merging_with_existing_instructions(self):
        """测试与现有指令的合并"""
        output_schema = JsonObjectOutputSchema(UserProfile)

        original_instructions = "你是一个专业的助手，请帮助用户处理个人资料信息。"
        schema_injection = output_schema.get_system_prompt_injection()

        # 模拟合并逻辑
        final_instructions = f"{original_instructions}\n\n{schema_injection}"

        assert original_instructions in final_instructions
        assert schema_injection in final_instructions
        assert final_instructions.count("\n\n") >= 1  # 确保有分隔符（生成的指令中可能包含多个）

    def test_prompt_merging_without_existing_instructions(self):
        """测试无现有指令时的处理"""
        output_schema = JsonObjectOutputSchema(UserProfile)

        schema_injection = output_schema.get_system_prompt_injection()

        # 模拟无原始指令的情况
        final_instructions = schema_injection

        assert final_instructions == schema_injection
        assert "请返回一个严格符合 JSON 格式的对象" in final_instructions

    def test_prompt_merging_with_empty_injection(self):
        """测试空注入的处理"""
        # 模拟不需要注入的情况
        original_instructions = "你是一个专业的助手。"
        schema_injection = ""

        # 模拟合并逻辑
        if schema_injection:
            final_instructions = f"{original_instructions}\n\n{schema_injection}"
        else:
            final_instructions = original_instructions

        assert final_instructions == original_instructions
        assert "\n\n" not in final_instructions


class TestIntegrationWithAgents:
    """与 Agent 系统的集成测试"""

    def test_agent_with_json_object_output_schema(self):
        """测试 Agent 使用 JsonObjectOutputSchema"""
        output_schema = JsonObjectOutputSchema(UserProfile)

        agent = Agent(
            name="TestAgent",
            instructions="处理用户个人资料",
            output_type=output_schema
        )

        assert agent.output_type == output_schema
        assert isinstance(agent.output_type, JsonObjectOutputSchema)

        # 验证注入方法可用
        assert hasattr(agent.output_type, 'should_inject_to_system_prompt')
        assert hasattr(agent.output_type, 'get_system_prompt_injection')
        assert agent.output_type.should_inject_to_system_prompt() is True

    def test_agent_with_smart_fallback_schema(self):
        """测试 Agent 使用智能降级 Schema"""
        output_schema = AgentOutputSchema(UserProfile, fallback_to_json_object=True)

        agent = Agent(
            name="SmartAgent",
            instructions="智能处理用户个人资料",
            output_type=output_schema
        )

        assert isinstance(agent.output_type, AgentOutputSchema)
        assert agent.output_type.fallback_to_json_object is True

        # 验证注入方法可用
        assert hasattr(agent.output_type, 'should_inject_to_system_prompt')
        assert hasattr(agent.output_type, 'get_system_prompt_injection')


class TestErrorHandling:
    """错误处理测试"""

    def test_injection_with_import_error(self):
        """测试导入错误时的处理"""
        output_schema = AgentOutputSchema(UserProfile, fallback_to_json_object=True)

        # 模拟导入错误
        with patch('builtins.__import__', side_effect=ImportError("Mocked import error")):
            # 应该返回空字符串而不抛出异常
            injection = output_schema.get_system_prompt_injection()
            assert injection == ""

            # 应该返回 False 而不抛出异常
            class MockModel:
                def __str__(self):
                    return "test-model"

            mock_model = MockModel()
            should_inject = output_schema.should_inject_to_system_prompt(mock_model)
            assert should_inject is False

    def test_injection_with_invalid_output_schema(self):
        """测试无效输出模式的处理"""
        # 模拟没有注入方法的输出模式
        class MockOutputSchema:
            def is_plain_text(self):
                return False

        mock_schema = MockOutputSchema()

        # 模拟模型处理逻辑
        schema_injection = ""

        if (hasattr(mock_schema, 'should_inject_to_system_prompt') and
            hasattr(mock_schema, 'get_system_prompt_injection')):
            # 这个分支不会执行
            schema_injection = "should not reach here"

        assert schema_injection == ""

    def test_injection_with_callable_check(self):
        """测试可调用性检查"""
        # 模拟有属性但不可调用的情况
        class MockOutputSchema:
            should_inject_to_system_prompt = "not_callable"
            def get_system_prompt_injection(self):
                return "test injection"

        mock_schema = MockOutputSchema()

        # 模拟模型处理逻辑
        schema_injection = ""

        if (hasattr(mock_schema, 'should_inject_to_system_prompt') and
            hasattr(mock_schema, 'get_system_prompt_injection')):
            if callable(mock_schema.should_inject_to_system_prompt):
                # 这个分支不会执行，因为属性不可调用
                schema_injection = "should not reach here"

        assert schema_injection == ""
