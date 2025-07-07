"""
JsonObjectOutputSchema 核心功能测试

测试 JsonObjectOutputSchema 类的各项功能，包括：
1. 基本功能测试
2. 指令生成测试
3. JSON 验证测试
4. 模型能力检测测试
5. 缓存机制测试
"""

import json
from dataclasses import dataclass
from typing import Optional
from unittest.mock import Mock

import pytest
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from agents.exceptions import ModelBehaviorError
from agents.json_object_output import (
    InstructionGenerator,
    JsonObjectOutputSchema,
    ModelCapabilityDetector,
)


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


class ProductInfo(TypedDict):
    """产品信息"""
    name: str
    price: float
    category: str
    in_stock: bool


class TestJsonObjectOutputSchema:
    """JsonObjectOutputSchema 基本功能测试"""

    def test_basic_initialization(self):
        """测试基本初始化"""
        schema = JsonObjectOutputSchema(UserProfile)

        assert schema.target_type == UserProfile
        assert not schema.is_plain_text()
        assert schema.name() == "JsonObjectOutputSchema(UserProfile)"
        assert schema.json_schema() == {"type": "object"}
        assert not schema.is_strict_json_schema()

    def test_custom_configuration(self):
        """测试自定义配置"""
        custom_instructions = "请返回用户信息的 JSON 对象"

        schema = JsonObjectOutputSchema(
            UserProfile,
            instruction_language="en",
            include_examples=False,
            custom_instructions=custom_instructions,
            validation_mode="lenient"
        )

        assert schema.generated_instructions == custom_instructions

    def test_valid_json_validation_pydantic(self):
        """测试有效 JSON 验证 - Pydantic 模型"""
        schema = JsonObjectOutputSchema(UserProfile)

        valid_json = json.dumps({
            "name": "张三",
            "age": 25,
            "city": "北京",
            "is_active": True
        }, ensure_ascii=False)

        result = schema.validate_json(valid_json)

        assert isinstance(result, UserProfile)
        assert result.name == "张三"
        assert result.age == 25
        assert result.city == "北京"
        assert result.is_active is True

    def test_valid_json_validation_dataclass(self):
        """测试有效 JSON 验证 - dataclass"""
        schema = JsonObjectOutputSchema(TaskItem)

        valid_json = json.dumps({
            "title": "完成项目",
            "description": "完成 JSON 输出兼容性功能",
            "priority": 5,
            "completed": False,
            "tags": ["开发", "功能"]
        }, ensure_ascii=False)

        result = schema.validate_json(valid_json)

        assert isinstance(result, TaskItem)
        assert result.title == "完成项目"
        assert result.priority == 5
        assert result.tags == ["开发", "功能"]

    def test_valid_json_validation_typed_dict(self):
        """测试有效 JSON 验证 - TypedDict"""
        schema = JsonObjectOutputSchema(ProductInfo)

        valid_json = json.dumps({
            "name": "智能手机",
            "price": 2999.99,
            "category": "电子产品",
            "in_stock": True
        }, ensure_ascii=False)

        result = schema.validate_json(valid_json)

        assert isinstance(result, dict)
        assert result["name"] == "智能手机"
        assert result["price"] == 2999.99
        assert result["in_stock"] is True

    def test_invalid_json_syntax(self):
        """测试无效 JSON 语法"""
        schema = JsonObjectOutputSchema(UserProfile)

        invalid_json = '{"name": "张三", "age": 25, "city": "北京"'  # 缺少结束括号

        with pytest.raises(ModelBehaviorError) as exc_info:
            schema.validate_json(invalid_json)

        assert "不是有效的 JSON" in str(exc_info.value)

    def test_invalid_json_structure_strict_mode(self):
        """测试无效 JSON 结构 - 严格模式"""
        schema = JsonObjectOutputSchema(UserProfile, validation_mode="strict")

        invalid_json = json.dumps({
            "name": "张三",
            "age": "二十五",  # 应该是数字，不是字符串
            "city": "北京",
            "is_active": True
        }, ensure_ascii=False)

        with pytest.raises(ModelBehaviorError) as exc_info:
            schema.validate_json(invalid_json)

        assert "不符合预期类型" in str(exc_info.value)

    def test_invalid_json_structure_lenient_mode(self):
        """测试无效 JSON 结构 - 宽松模式"""
        schema = JsonObjectOutputSchema(UserProfile, validation_mode="lenient")

        invalid_json = json.dumps({
            "name": "张三",
            "age": "二十五",  # 应该是数字，不是字符串
            "city": "北京",
            "is_active": True
        }, ensure_ascii=False)

        # 宽松模式应该返回原始对象而不抛出异常
        result = schema.validate_json(invalid_json)
        assert isinstance(result, dict)
        assert result["name"] == "张三"

    def test_factory_methods(self):
        """测试工厂方法"""
        # 测试 Pydantic 模型工厂方法
        pydantic_schema = JsonObjectOutputSchema.for_pydantic_model(UserProfile)
        assert pydantic_schema.target_type == UserProfile

        # 测试 dataclass 工厂方法
        dataclass_schema = JsonObjectOutputSchema.for_dataclass(TaskItem)
        assert dataclass_schema.target_type == TaskItem

        # 测试 TypedDict 工厂方法
        typed_dict_schema = JsonObjectOutputSchema.for_typed_dict(ProductInfo)
        assert typed_dict_schema.target_type == ProductInfo


class TestInstructionGenerator:
    """指令生成器测试"""

    def test_generate_instructions_chinese(self):
        """测试中文指令生成"""
        instructions = InstructionGenerator.generate_json_instructions(
            UserProfile,
            language="zh",
            include_examples=True
        )

        assert "请返回一个严格符合 JSON 格式的对象" in instructions
        assert "name (字符串): 用户的姓名" in instructions
        assert "age (整数): 用户的年龄" in instructions
        assert "示例输出：" in instructions
        assert "请确保输出严格符合 JSON 语法" in instructions

    def test_generate_instructions_english(self):
        """测试英文指令生成"""
        instructions = InstructionGenerator.generate_json_instructions(
            UserProfile,
            language="en",
            include_examples=True
        )

        assert "Please return a JSON object with the following fields:" in instructions
        assert "Example output:" in instructions
        assert "Ensure the output strictly follows JSON syntax" in instructions

    def test_generate_instructions_without_examples(self):
        """测试不包含示例的指令生成"""
        instructions = InstructionGenerator.generate_json_instructions(
            UserProfile,
            language="zh",
            include_examples=False
        )

        assert "请返回一个严格符合 JSON 格式的对象" in instructions
        assert "示例输出：" not in instructions

    def test_custom_instructions_override(self):
        """测试自定义指令覆盖"""
        custom_instructions = "这是自定义指令"

        instructions = InstructionGenerator.generate_json_instructions(
            UserProfile,
            custom_instructions=custom_instructions
        )

        assert instructions == custom_instructions

    def test_instruction_caching(self):
        """测试指令缓存"""
        # 清空缓存
        InstructionGenerator._instruction_cache.clear()

        # 缓存默认启用

        # 第一次生成
        instructions1 = InstructionGenerator.generate_json_instructions(UserProfile)

        # 检查缓存
        assert len(InstructionGenerator._instruction_cache) == 1

        # 第二次生成（应该从缓存获取）
        instructions2 = InstructionGenerator.generate_json_instructions(UserProfile)

        assert instructions1 == instructions2
        assert len(InstructionGenerator._instruction_cache) == 1


class TestModelCapabilityDetector:
    """模型能力检测器测试"""

    def test_explicit_capability_method(self):
        """测试显式能力声明方法"""
        # 模拟支持 json_schema 的模型
        mock_model = Mock()
        mock_model.supports_json_schema.return_value = True

        assert ModelCapabilityDetector.supports_json_schema(mock_model) is True

        # 模拟不支持 json_schema 的模型
        mock_model.supports_json_schema.return_value = False
        assert ModelCapabilityDetector.supports_json_schema(mock_model) is False

    def test_capability_attributes(self):
        """测试能力属性检测"""
        # 模拟有能力属性的模型
        mock_model = Mock()
        mock_model.capabilities = {"json_schema": True}
        # 确保没有 supports_json_schema 方法，这样会走到能力属性检测
        del mock_model.supports_json_schema

        assert ModelCapabilityDetector.supports_json_schema(mock_model) is True

        # 模拟不支持的模型
        mock_model.capabilities = {"json_schema": False}
        assert ModelCapabilityDetector.supports_json_schema(mock_model) is False

    def test_name_based_detection(self):
        """测试基于名称的检测"""
        # 模拟 OpenAI 模型
        class MockOpenAIModel:
            def __str__(self):
                return "gpt-4-turbo"

        mock_model = MockOpenAIModel()

        assert ModelCapabilityDetector.supports_json_schema(mock_model) is True

        # 模拟未知模型
        class MockUnknownModel:
            def __str__(self):
                return "unknown-model"

        mock_unknown_model = MockUnknownModel()
        assert ModelCapabilityDetector.supports_json_schema(mock_unknown_model) is False

    def test_type_based_detection(self):
        """测试基于类型的检测"""
        # 模拟 OpenAI ChatCompletions 模型
        class MockOpenAIChatCompletionsModel:
            pass

        mock_model = MockOpenAIChatCompletionsModel()
        assert ModelCapabilityDetector.supports_json_schema(mock_model) is True

    def test_fallback_to_false(self):
        """测试默认降级到 False"""
        # 模拟完全未知的模型
        class MockUnknownModel:
            def __str__(self):
                return "completely-unknown-model"

        mock_model = MockUnknownModel()

        assert ModelCapabilityDetector.supports_json_schema(mock_model) is False


# 移除了复杂的全局配置类，使用简单的常量配置


class TestCachingMechanism:
    """缓存机制测试"""

    def test_validator_caching(self):
        """测试验证器缓存"""
        # 清空缓存
        JsonObjectOutputSchema._validator_cache.clear()

        # 缓存默认启用

        # 创建第一个实例
        JsonObjectOutputSchema(UserProfile)
        assert len(JsonObjectOutputSchema._validator_cache) == 1

        # 创建第二个实例（相同类型）
        JsonObjectOutputSchema(UserProfile)
        assert len(JsonObjectOutputSchema._validator_cache) == 1  # 缓存复用

        # 创建不同类型的实例
        JsonObjectOutputSchema(TaskItem)
        assert len(JsonObjectOutputSchema._validator_cache) == 2

    def test_cache_cleanup(self):
        """测试缓存清理"""
        # 填充缓存
        JsonObjectOutputSchema._validator_cache.clear()

        # 使用已知的有效类型来填充缓存
        test_types = [UserProfile, TaskItem, ProductInfo]
        for i in range(10):
            # 循环使用已知类型
            test_type = test_types[i % len(test_types)]
            # 为了创建不同的缓存项，我们创建一个包装类
            wrapper_type = type(f"Wrapper{i}", (object,), {"inner_type": test_type})
            try:
                JsonObjectOutputSchema(wrapper_type)
            except Exception:
                # 如果类型不支持，跳过
                continue

        # 清理缓存
        JsonObjectOutputSchema.cleanup_cache(max_size=5)
        assert len(JsonObjectOutputSchema._validator_cache) <= 5


class TestErrorHandling:
    """错误处理测试"""

    def test_instruction_generation_error_handling(self):
        """测试指令生成错误处理"""
        # 模拟一个会导致错误的类型
        class ProblematicType:
            pass

        # 应该返回基础指令而不抛出异常
        instructions = InstructionGenerator.generate_json_instructions(ProblematicType)
        assert "请返回一个严格符合 JSON 格式的对象" in instructions

    def test_validation_error_logging(self):
        """测试验证错误日志记录"""
        schema = JsonObjectOutputSchema(UserProfile)

        invalid_json = json.dumps({
            "name": "张三",
            "age": "无效年龄",
            "city": "北京",
            "is_active": True
        })

        with pytest.raises(ModelBehaviorError):
            schema.validate_json(invalid_json)

    def test_capability_detection_error_handling(self):
        """测试能力检测错误处理"""
        # 模拟会抛出异常的模型
        mock_model = Mock()
        mock_model.supports_json_schema.side_effect = Exception("测试异常")

        # 应该降级到基于名称的检测，而不抛出异常
        result = ModelCapabilityDetector.supports_json_schema(mock_model)
        assert isinstance(result, bool)
