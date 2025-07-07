"""
JsonObjectOutputSchema 集成测试

测试 JsonObjectOutputSchema 与 Agent 系统的集成，包括：
1. 与 Agent 的集成测试
2. 智能降级机制测试
3. Converter 层集成测试
4. 端到端功能测试
"""

import json
from dataclasses import dataclass
from typing import Any, Optional
from unittest.mock import Mock, patch

import pytest
from pydantic import BaseModel, Field

from agents import Agent, AgentOutputSchema
from agents.exceptions import ModelBehaviorError
from agents.json_object_output import (
    JsonObjectOutputSchema,
    ModelCapabilityDetector,
)
from agents.models.chatcmpl_converter import Converter as ChatCmplConverter
from agents.models.openai_responses import Converter as ResponsesConverter


# 测试用的数据模型
class UserProfile(BaseModel):
    """用户个人资料信息"""
    name: str = Field(description="用户的姓名")
    age: int = Field(description="用户的年龄", ge=0, le=150)
    city: str = Field(description="用户居住的城市")
    is_active: bool = Field(description="用户当前是否活跃")


@dataclass
class TaskItem:
    """任务项目"""
    title: str
    description: str
    priority: int  # 1-5, 5 为最高优先级
    completed: bool = False
    tags: Optional[list[str]] = None


class TestAgentIntegration:
    """Agent 集成测试"""

    def test_agent_with_json_object_output_schema(self):
        """测试 Agent 使用 JsonObjectOutputSchema"""
        output_schema = JsonObjectOutputSchema(UserProfile)

        agent = Agent(
            name="TestAgent",
            instructions="测试指令",
            output_type=output_schema
        )

        assert agent.output_type == output_schema
        assert isinstance(agent.output_type, JsonObjectOutputSchema)
        assert agent.output_type.target_type == UserProfile
        assert not agent.output_type.is_plain_text()

    def test_agent_with_smart_fallback_enabled(self):
        """测试 Agent 使用智能降级功能"""
        output_schema = AgentOutputSchema(
            UserProfile,
            fallback_to_json_object=True
        )

        agent = Agent(
            name="SmartAgent",
            instructions="智能降级测试",
            output_type=output_schema
        )

        assert isinstance(agent.output_type, AgentOutputSchema)
        assert agent.output_type.fallback_to_json_object is True
        assert agent.output_type.output_type == UserProfile

    def test_agent_with_custom_instructions(self):
        """测试 Agent 使用自定义指令"""
        custom_instructions = "请返回用户信息的 JSON 对象，包含姓名、年龄、城市和活跃状态"

        output_schema = JsonObjectOutputSchema(
            UserProfile,
            custom_instructions=custom_instructions
        )

        agent = Agent(
            name="CustomAgent",
            instructions="自定义指令测试",
            output_type=output_schema
        )

        assert isinstance(agent.output_type, JsonObjectOutputSchema)
        assert agent.output_type.generated_instructions == custom_instructions


class TestConverterIntegration:
    """Converter 层集成测试"""

    def test_chatcmpl_converter_with_json_object_schema(self):
        """测试 ChatCompletions Converter 处理 JsonObjectOutputSchema"""
        output_schema = JsonObjectOutputSchema(UserProfile)

        response_format = ChatCmplConverter.convert_response_format(output_schema)

        # JsonObjectOutputSchema 没有 fallback_to_json_object 属性，所以会使用默认的 json_schema
        # 但是它的 json_schema() 返回 {"type": "object"}，is_strict_json_schema() 返回 False
        assert isinstance(response_format, dict)
        assert response_format.get("type") == "json_schema"
        json_schema_part = response_format.get("json_schema", {})
        assert isinstance(json_schema_part, dict)
        assert json_schema_part.get("schema") == {"type": "object"}
        assert json_schema_part.get("strict") is False

    def test_chatcmpl_converter_with_smart_fallback_no_model(self):
        """测试 ChatCompletions Converter 智能降级（无模型）"""
        output_schema = AgentOutputSchema(
            UserProfile,
            fallback_to_json_object=True
        )

        # 不传递模型参数，应该使用默认的 json_schema
        response_format = ChatCmplConverter.convert_response_format(output_schema)

        assert isinstance(response_format, dict)
        assert response_format.get("type") == "json_schema"
        assert "json_schema" in response_format

    def test_chatcmpl_converter_with_smart_fallback_unsupported_model(self):
        """测试 ChatCompletions Converter 智能降级（不支持的模型）"""
        output_schema = AgentOutputSchema(
            UserProfile,
            fallback_to_json_object=True
        )

        # 模拟不支持 json_schema 的模型
        class MockUnsupportedModel:
            def __str__(self):
                return "unsupported-model"

        mock_model = MockUnsupportedModel()

        response_format = ChatCmplConverter.convert_response_format(output_schema, mock_model)

        # 应该降级到 json_object
        assert response_format == {"type": "json_object"}

    def test_chatcmpl_converter_with_smart_fallback_supported_model(self):
        """测试 ChatCompletions Converter 智能降级（支持的模型）"""
        output_schema = AgentOutputSchema(
            UserProfile,
            fallback_to_json_object=True
        )

        # 模拟支持 json_schema 的模型
        class MockSupportedModel:
            def __str__(self):
                return "gpt-4-turbo"

        mock_model = MockSupportedModel()

        response_format = ChatCmplConverter.convert_response_format(output_schema, mock_model)

        # 应该使用 json_schema
        assert isinstance(response_format, dict)
        assert response_format.get("type") == "json_schema"
        assert "json_schema" in response_format

    def test_responses_converter_with_json_object_schema(self):
        """测试 Responses Converter 处理 JsonObjectOutputSchema"""
        output_schema = JsonObjectOutputSchema(UserProfile)

        response_format = ResponsesConverter.get_response_format(output_schema)

        # JsonObjectOutputSchema 没有 fallback_to_json_object 属性，所以会使用默认的 json_schema
        assert isinstance(response_format, dict)
        format_data: Any = response_format.get("format", {})
        assert isinstance(format_data, dict)
        assert format_data.get("type") == "json_schema"
        assert format_data.get("schema") == {"type": "object"}
        assert format_data.get("strict") is False

    def test_responses_converter_with_smart_fallback_unsupported_model(self):
        """测试 Responses Converter 智能降级（不支持的模型）"""
        output_schema = AgentOutputSchema(
            UserProfile,
            fallback_to_json_object=True
        )

        # 模拟不支持 json_schema 的模型
        class MockUnsupportedModel:
            def __str__(self):
                return "unsupported-model"

        mock_model = MockUnsupportedModel()

        response_format = ResponsesConverter.get_response_format(output_schema, mock_model)

        # 应该降级到 json_object
        assert isinstance(response_format, dict)
        format_data: Any = response_format.get("format", {})
        assert isinstance(format_data, dict)
        assert format_data.get("type") == "json_object"

    def test_responses_converter_with_smart_fallback_supported_model(self):
        """测试 Responses Converter 智能降级（支持的模型）"""
        output_schema = AgentOutputSchema(
            UserProfile,
            fallback_to_json_object=True
        )

        # 模拟支持 json_schema 的模型
        class MockSupportedModel:
            def __str__(self):
                return "gpt-4-turbo"

        mock_model = MockSupportedModel()

        response_format = ResponsesConverter.get_response_format(output_schema, mock_model)

        # 应该使用 json_schema
        assert isinstance(response_format, dict)
        format_data: Any = response_format.get("format", {})
        assert isinstance(format_data, dict)
        assert format_data.get("type") == "json_schema"
        assert "name" in format_data


class TestSmartFallbackMechanism:
    """智能降级机制测试"""

    def test_fallback_detection_with_explicit_method(self):
        """测试显式方法的降级检测"""
        # 支持 json_schema 的模型
        mock_model = Mock()
        mock_model.supports_json_schema.return_value = True

        assert ModelCapabilityDetector.supports_json_schema(mock_model) is True

        # 不支持 json_schema 的模型
        mock_model.supports_json_schema.return_value = False
        assert ModelCapabilityDetector.supports_json_schema(mock_model) is False

    def test_fallback_detection_with_capabilities(self):
        """测试能力属性的降级检测"""
        # 支持 json_schema 的模型
        mock_model = Mock()
        mock_model.capabilities = {"json_schema": True}
        del mock_model.supports_json_schema

        assert ModelCapabilityDetector.supports_json_schema(mock_model) is True

        # 不支持 json_schema 的模型
        mock_model.capabilities = {"json_schema": False}
        assert ModelCapabilityDetector.supports_json_schema(mock_model) is False

    def test_fallback_detection_with_model_name(self):
        """测试基于模型名称的降级检测"""
        # OpenAI 模型
        class MockOpenAIModel:
            def __str__(self):
                return "gpt-4-turbo"

        mock_model = MockOpenAIModel()
        assert ModelCapabilityDetector.supports_json_schema(mock_model) is True

        # 未知模型
        class MockUnknownModel:
            def __str__(self):
                return "unknown-model"

        mock_unknown_model = MockUnknownModel()
        assert ModelCapabilityDetector.supports_json_schema(mock_unknown_model) is False

    def test_fallback_with_import_error(self):
        """测试导入错误时的降级处理"""
        output_schema = AgentOutputSchema(
            UserProfile,
            fallback_to_json_object=True
        )

        mock_model = Mock()

        # 模拟导入错误 - patch builtins.__import__ 来模拟导入失败
        def mock_import(name, *args, **kwargs):
            if 'json_object_output' in name:
                raise ImportError("Mocked import error")
            return __import__(name, *args, **kwargs)

        with patch('builtins.__import__', side_effect=mock_import):
            # 由于导入失败，应该继续使用 json_schema
            response_format = ChatCmplConverter.convert_response_format(output_schema, mock_model)

            # 应该降级到默认的 json_schema
            assert isinstance(response_format, dict)
            assert response_format.get("type") == "json_schema"


class TestEndToEndFunctionality:
    """端到端功能测试"""

    def test_json_object_schema_validation_flow(self):
        """测试 JsonObjectOutputSchema 的完整验证流程"""
        output_schema = JsonObjectOutputSchema(UserProfile)

        # 模拟 LLM 返回的有效 JSON
        valid_json = json.dumps({
            "name": "张三",
            "age": 25,
            "city": "北京",
            "is_active": True
        }, ensure_ascii=False)

        result = output_schema.validate_json(valid_json)

        assert isinstance(result, UserProfile)
        assert result.name == "张三"
        assert result.age == 25
        assert result.city == "北京"
        assert result.is_active is True

    def test_smart_fallback_complete_flow(self):
        """测试智能降级的完整流程"""
        # 创建启用智能降级的输出模式
        output_schema = AgentOutputSchema(
            UserProfile,
            fallback_to_json_object=True
        )

        # 模拟不支持 json_schema 的模型
        class MockUnsupportedModel:
            def __str__(self):
                return "unsupported-model"

        mock_model = MockUnsupportedModel()

        # 测试 ChatCompletions Converter
        chatcmpl_format = ChatCmplConverter.convert_response_format(output_schema, mock_model)
        assert chatcmpl_format == {"type": "json_object"}

        # 测试 Responses Converter
        responses_format = ResponsesConverter.get_response_format(output_schema, mock_model)
        assert isinstance(responses_format, dict)
        format_data: Any = responses_format.get("format", {})
        assert isinstance(format_data, dict)
        assert format_data.get("type") == "json_object"

        # 验证原始的验证功能仍然有效
        valid_json = json.dumps({
            "name": "李四",
            "age": 30,
            "city": "上海",
            "is_active": False
        }, ensure_ascii=False)

        result = output_schema.validate_json(valid_json)
        assert isinstance(result, UserProfile)
        assert result.name == "李四"

    def test_instance_configuration(self):
        """测试实例级配置（替代全局配置）"""
        # 英文配置
        en_schema = JsonObjectOutputSchema(
            UserProfile,
            instruction_language="en",
            include_examples=False
        )

        instructions = en_schema.generated_instructions
        assert "Please return a JSON object" in instructions
        assert "Example output:" not in instructions

        # 中文配置（默认）
        zh_schema = JsonObjectOutputSchema(UserProfile)
        zh_instructions = zh_schema.generated_instructions
        assert "请返回一个严格符合 JSON 格式的对象" in zh_instructions
        assert "示例输出：" in zh_instructions

    def test_error_handling_integration(self):
        """测试错误处理集成"""
        output_schema = JsonObjectOutputSchema(UserProfile)

        # 测试无效 JSON
        with pytest.raises(ModelBehaviorError) as exc_info:
            output_schema.validate_json("invalid json")

        assert "不是有效的 JSON" in str(exc_info.value)

        # 测试类型不匹配
        invalid_json = json.dumps({
            "name": "王五",
            "age": "三十",  # 应该是数字
            "city": "广州",
            "is_active": True
        })

        with pytest.raises(ModelBehaviorError) as exc_info:
            output_schema.validate_json(invalid_json)

        assert "不符合预期类型" in str(exc_info.value)


class TestBackwardCompatibility:
    """向后兼容性测试"""

    def test_existing_agent_output_schema_unchanged(self):
        """测试现有 AgentOutputSchema 功能不变"""
        # 不启用降级的传统用法
        output_schema = AgentOutputSchema(UserProfile)

        assert output_schema.output_type == UserProfile
        assert (not hasattr(output_schema, 'fallback_to_json_object') or
                not output_schema.fallback_to_json_object)
        assert output_schema.is_strict_json_schema() is True
        assert not output_schema.is_plain_text()

    def test_existing_converter_behavior_unchanged(self):
        """测试现有 Converter 行为不变"""
        output_schema = AgentOutputSchema(UserProfile)

        # 不传递模型参数的传统调用
        chatcmpl_format = ChatCmplConverter.convert_response_format(output_schema)
        assert isinstance(chatcmpl_format, dict)
        assert chatcmpl_format.get("type") == "json_schema"

        responses_format = ResponsesConverter.get_response_format(output_schema)
        assert isinstance(responses_format, dict)
        format_data: Any = responses_format.get("format", {})
        assert isinstance(format_data, dict)
        assert format_data.get("type") == "json_schema"

    def test_agent_creation_backward_compatibility(self):
        """测试 Agent 创建的向后兼容性"""
        from agents.run import AgentRunner

        # 传统的 Agent 创建方式
        agent1 = Agent(
            name="TraditionalAgent",
            instructions="传统指令",
            output_type=UserProfile
        )

        # Agent 的 output_type 是原始类型，需要通过 _get_output_schema 获取实际的 schema
        schema1 = AgentRunner._get_output_schema(agent1)
        assert schema1 is not None
        assert isinstance(schema1, AgentOutputSchema)
        assert schema1.output_type == UserProfile

        # 使用 AgentOutputSchema 的方式
        agent2 = Agent(
            name="SchemaAgent",
            instructions="Schema 指令",
            output_type=AgentOutputSchema(UserProfile)
        )

        schema2 = AgentRunner._get_output_schema(agent2)
        assert schema2 is not None
        assert isinstance(schema2, AgentOutputSchema)
        assert schema2.output_type == UserProfile

        # 两种方式创建的 Agent 应该具有相同的基本功能
        assert type(schema1) is type(schema2)
        assert schema1.is_strict_json_schema() == schema2.is_strict_json_schema()
