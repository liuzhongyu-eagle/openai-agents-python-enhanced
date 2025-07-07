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

    def test_custom_instructions(self):
        """测试自定义指令"""
        custom_instructions = "Please return user information as JSON with examples."

        schema = JsonObjectOutputSchema(
            UserProfile,
            custom_instructions=custom_instructions
        )

        # 应该包含 JSON Schema 和自定义指令
        assert "JSON Schema:" in schema.generated_instructions
        assert custom_instructions in schema.generated_instructions
        assert '"properties"' in schema.generated_instructions

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

        # 新的错误消息包含修复尝试信息
        assert "JSON 无效" in str(exc_info.value) or "修复失败" in str(exc_info.value)

    def test_invalid_json_structure(self):
        """测试无效 JSON 结构（简化版，只有严格验证）"""
        schema = JsonObjectOutputSchema(UserProfile)

        invalid_json = json.dumps({
            "name": "张三",
            "age": "二十五",  # 应该是数字，不是字符串
            "city": "北京",
            "is_active": True
        }, ensure_ascii=False)

        with pytest.raises(ModelBehaviorError) as exc_info:
            schema.validate_json(invalid_json)

        assert "不符合预期类型" in str(exc_info.value)

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

    def test_generate_instructions_basic(self):
        """测试基本指令生成"""
        instructions = InstructionGenerator.generate_json_instructions(UserProfile)

        assert "JSON Schema:" in instructions
        assert '"type": "string"' in instructions
        assert '"type": "integer"' in instructions
        assert '"type": "boolean"' in instructions
        assert "Always respond strictly in the following JSON format with no additional explanatory text." in instructions

    def test_generate_instructions_with_schema(self):
        """测试生成的指令包含完整的 JSON Schema"""
        instructions = InstructionGenerator.generate_json_instructions(UserProfile)

        # 验证包含 JSON Schema
        assert "JSON Schema:" in instructions
        assert '"properties"' in instructions
        assert '"required"' in instructions
        assert '"name"' in instructions
        assert '"age"' in instructions



    def test_custom_instructions_append(self):
        """测试自定义指令附加到 JSON Schema 后面"""
        custom_instructions = "Please include examples in your response."

        instructions = InstructionGenerator.generate_json_instructions(
            UserProfile,
            custom_instructions=custom_instructions
        )

        # 应该包含 JSON Schema 和自定义指令
        assert "JSON Schema:" in instructions
        assert custom_instructions in instructions
        assert '"properties"' in instructions









class TestErrorHandling:
    """错误处理测试"""

    def test_instruction_generation_error_handling(self):
        """测试指令生成错误处理"""
        # 模拟一个会导致错误的类型
        class ProblematicType:
            pass

        # 应该抛出异常而不是返回基础指令
        with pytest.raises(ValueError, match="Unsupported type for JSON schema generation"):
            InstructionGenerator.generate_json_instructions(ProblematicType)

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


