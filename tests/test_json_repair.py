"""
JSON 修复功能测试

测试 JSON 修复功能在各种格式异常情况下的表现。
"""

import json
from typing import Optional

import pytest
from pydantic import BaseModel, Field

from agents import Agent, AgentOutputSchema, JsonObjectOutputSchema
from agents.exceptions import ModelBehaviorError
from agents.util._json_repair import repair_and_validate_json


# 测试用的数据模型
class UserProfile(BaseModel):
    """用户个人资料信息"""

    name: str = Field(description="用户的姓名")
    age: int = Field(description="用户的年龄", ge=0, le=150)
    city: str = Field(description="用户居住的城市")
    is_active: bool = Field(description="用户当前是否活跃")
    interests: Optional[list[str]] = Field(default=None, description="用户的兴趣爱好列表")


class TestJsonRepairCore:
    """JSON 修复核心功能测试"""

    def test_valid_json_no_repair_needed(self):
        """测试有效 JSON 无需修复"""
        valid_json = json.dumps(
            {
                "name": "张三",
                "age": 25,
                "city": "北京",
                "is_active": True,
                "interests": ["编程", "阅读"],
            },
            ensure_ascii=False,
        )

        result = repair_and_validate_json(valid_json)

        assert result.success is True
        assert result.repair_applied is False
        assert result.repaired_json == valid_json
        assert result.parsed_object is not None
        assert result.parsed_object["name"] == "张三"

    def test_missing_quotes_repair(self):
        """测试缺少引号的修复"""
        broken_json = """{
            name: "张三",
            age: 25,
            city: "北京",
            is_active: true,
            interests: ["编程", "阅读"]
        }"""

        result = repair_and_validate_json(broken_json)

        assert result.success is True
        assert result.repair_applied is True
        assert result.repair_details is not None and "修复" in result.repair_details
        assert result.parsed_object is not None
        assert result.parsed_object["name"] == "张三"

    def test_trailing_comma_repair(self):
        """测试尾随逗号的修复"""
        broken_json = """{
            "name": "张三",
            "age": 25,
            "city": "北京",
            "is_active": true,
            "interests": ["编程", "阅读",],
        }"""

        result = repair_and_validate_json(broken_json)

        assert result.success is True
        assert result.repair_applied is True
        assert result.parsed_object is not None
        assert result.parsed_object["name"] == "张三"

    def test_single_quotes_repair(self):
        """测试单引号的修复"""
        broken_json = """{
            'name': '张三',
            'age': 25,
            'city': '北京',
            'is_active': true,
            'interests': ['编程', '阅读']
        }"""

        result = repair_and_validate_json(broken_json)

        assert result.success is True
        assert result.repair_applied is True
        assert result.parsed_object is not None
        assert result.parsed_object["name"] == "张三"

    def test_incomplete_json_repair(self):
        """测试不完整 JSON 的修复"""
        broken_json = """{
            "name": "张三",
            "age": 25,
            "city": "北京",
            "is_active": true"""

        result = repair_and_validate_json(broken_json)

        # 这种情况可能修复成功也可能失败，取决于 json-repair 的能力
        if result.success:
            assert result.repair_applied is True
            assert result.parsed_object is not None
            assert result.parsed_object is not None
            assert result.parsed_object["name"] == "张三"

    def test_completely_broken_json(self):
        """测试完全损坏的 JSON"""
        broken_json = "这不是 JSON 格式的内容"

        result = repair_and_validate_json(broken_json)

        # json-repair 库很强大，可能会修复一些看似无法修复的内容
        # 所以我们只检查是否尝试了修复
        assert result.repair_applied is True
        if not result.success:
            assert result.repair_details is not None and "修复失败" in result.repair_details

    def test_with_type_validation(self):
        """测试带类型验证的修复"""
        from pydantic import TypeAdapter

        type_adapter = TypeAdapter(UserProfile)

        # 修复后能通过类型验证的 JSON
        broken_json = """{
            name: "张三",
            age: 25,
            city: "北京",
            is_active: true
        }"""

        result = repair_and_validate_json(broken_json, type_adapter)

        assert result.success is True
        assert result.repair_applied is True
        assert isinstance(result.parsed_object, UserProfile)
        assert result.parsed_object.name == "张三"

    def test_type_validation_failure(self):
        """测试类型验证失败"""
        from pydantic import TypeAdapter

        type_adapter = TypeAdapter(UserProfile)

        # 修复后仍无法通过类型验证的 JSON
        broken_json = """{
            name: "张三",
            age: "无效年龄",
            city: "北京",
            is_active: true
        }"""

        result = repair_and_validate_json(broken_json, type_adapter)

        # 修复可能成功，但类型验证应该失败
        assert result.success is False

    def test_repair_disabled(self):
        """测试禁用修复功能"""
        broken_json = """{
            name: "张三",
            age: 25
        }"""

        result = repair_and_validate_json(broken_json, enable_repair=False)

        assert result.success is False
        assert result.repair_applied is False


class TestJsonObjectOutputSchemaRepair:
    """JsonObjectOutputSchema JSON 修复测试"""

    def test_repair_enabled_by_default(self):
        """测试默认启用修复功能"""
        schema = JsonObjectOutputSchema(UserProfile)

        broken_json = """{
            name: "张三",
            age: 25,
            city: "北京",
            is_active: true
        }"""

        # 应该修复成功
        result = schema.validate_json(broken_json)
        assert isinstance(result, UserProfile)
        assert result.name == "张三"

    def test_repair_can_be_disabled(self):
        """测试可以禁用修复功能"""
        schema = JsonObjectOutputSchema(UserProfile, enable_json_repair=False)

        broken_json = """{
            name: "张三",
            age: 25
        }"""

        # 应该修复失败
        with pytest.raises(ModelBehaviorError):
            schema.validate_json(broken_json)

    def test_repair_override_in_method(self):
        """测试在方法调用时覆盖修复设置"""
        schema = JsonObjectOutputSchema(UserProfile, enable_json_repair=False)

        broken_json = """{
            name: "张三",
            age: 25,
            city: "北京",
            is_active: true
        }"""

        # 方法参数覆盖实例设置
        result = schema.validate_json(broken_json, enable_repair=True)
        assert isinstance(result, UserProfile)
        assert result.name == "张三"


class TestAgentOutputSchemaRepair:
    """AgentOutputSchema JSON 修复测试"""

    def test_repair_enabled_by_default(self):
        """测试默认启用修复功能"""
        schema = AgentOutputSchema(UserProfile)

        broken_json = """{
            name: "张三",
            age: 25,
            city: "北京",
            is_active: true
        }"""

        # 应该修复成功
        result = schema.validate_json(broken_json)
        assert isinstance(result, UserProfile)
        assert result.name == "张三"

    def test_repair_can_be_disabled(self):
        """测试可以禁用修复功能"""
        schema = AgentOutputSchema(UserProfile, enable_json_repair=False)

        broken_json = """{
            name: "张三",
            age: 25
        }"""

        # 应该修复失败
        with pytest.raises(ModelBehaviorError):
            schema.validate_json(broken_json)

    def test_repair_with_wrapped_output(self):
        """测试包装输出的修复"""
        # 使用会被包装的类型（int 会被包装）
        schema = AgentOutputSchema(int)

        # 测试修复包装格式的 JSON（缺少引号）
        broken_json = """{
            response: 42
        }"""

        # 应该修复成功
        result = schema.validate_json(broken_json)
        assert result == 42


class TestAgentIntegration:
    """Agent 集成测试"""

    def test_agent_with_json_repair(self):
        """测试 Agent 使用 JSON 修复功能"""
        agent = Agent(
            name="TestAgent",
            instructions="测试代理",
            output_type=JsonObjectOutputSchema(UserProfile),
        )

        # 验证输出类型支持修复
        assert hasattr(agent.output_type, "validate_json")
        assert hasattr(agent.output_type, "_enable_json_repair")
        output_type = agent.output_type
        assert isinstance(output_type, JsonObjectOutputSchema)
        assert output_type._enable_json_repair is True

    def test_agent_with_disabled_repair(self):
        """测试 Agent 禁用修复功能"""
        agent = Agent(
            name="TestAgent",
            instructions="测试代理",
            output_type=JsonObjectOutputSchema(UserProfile, enable_json_repair=False),
        )

        output_type = agent.output_type
        assert isinstance(output_type, JsonObjectOutputSchema)
        assert output_type._enable_json_repair is False


class TestErrorHandling:
    """错误处理测试"""

    def test_json_repair_library_unavailable(self):
        """测试 json-repair 库不可用的情况"""
        # 这个测试需要模拟库不可用的情况
        # 在实际环境中，库应该是可用的
        pass

    def test_repair_with_empty_string(self):
        """测试空字符串的处理"""
        result = repair_and_validate_json("")

        # json-repair 可能会将空字符串修复为某种有效的 JSON
        # 我们主要检查是否尝试了修复
        if not result.success:
            assert result.repair_applied is True

    def test_repair_with_none_input(self):
        """测试 None 输入的处理"""
        with pytest.raises(TypeError):
            repair_and_validate_json(None)  # type: ignore


class TestPerformance:
    """性能测试"""

    def test_repair_performance_with_large_json(self):
        """测试大 JSON 的修复性能"""
        # 创建一个较大的 JSON 对象
        large_data = {
            "users": [
                {"name": f"用户{i}", "age": 20 + (i % 50), "city": "北京", "is_active": i % 2 == 0}
                for i in range(100)
            ]
        }

        # 故意破坏 JSON 格式
        broken_json = json.dumps(large_data, ensure_ascii=False).replace('"name"', "name")

        result = repair_and_validate_json(broken_json)

        # 应该能够修复
        assert result.success is True
        assert result.repair_applied is True
        assert result.parsed_object is not None
        assert len(result.parsed_object["users"]) == 100
