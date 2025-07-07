#!/usr/bin/env python3
"""
OpenAI Agents SDK - JSON Object 输出兼容性演示

本演示展示了 JsonObjectOutputSchema 的使用，
支持仅接受 {'type': 'json_object'} 格式的 LLM 供应商。

功能特性：
1. JsonObjectOutputSchema - 专为 json_object 模式设计的输出模式
2. 自动指令生成 - 自动生成结构化的 JSON 输出指令
3. 提示词注入 - 将 schema 指令注入到系统提示词中
4. 统一验证机制 - 使用 Pydantic 进行严格类型检查
"""

import json
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field

# 导入 JSON Object 兼容性功能
from agents import (
    Agent,
    AgentOutputSchema,
    JsonObjectOutputSchema,
)


# 定义测试用的数据模型
class UserProfile(BaseModel):
    """用户个人资料信息"""
    name: str = Field(description="用户的姓名")
    age: int = Field(description="用户的年龄", ge=0, le=150)
    city: str = Field(description="用户居住的城市")
    is_active: bool = Field(description="用户当前是否活跃")
    interests: list[str] = Field(description="用户的兴趣爱好列表")


@dataclass
class TaskItem:
    """任务项目"""
    title: str
    description: str
    priority: int  # 1-5, 5 为最高优先级
    completed: bool = False
    tags: Optional[list[str]] = None


def demo_json_object_output_schema():
    """演示 JsonObjectOutputSchema 的基本功能"""
    print("=" * 60)
    print("1. JsonObjectOutputSchema 基本功能演示")
    print("=" * 60)

    # 创建 JsonObjectOutputSchema
    output_schema = JsonObjectOutputSchema(UserProfile)

    print(f"模式名称: {output_schema.name()}")
    print(f"是否纯文本: {output_schema.is_plain_text()}")
    print(f"是否严格 JSON Schema: {output_schema.is_strict_json_schema()}")
    print(f"JSON Schema: {output_schema.json_schema()}")
    print(f"是否需要注入提示词: {output_schema.should_inject_to_system_prompt()}")

    print("\n生成的指令:")
    print("-" * 40)
    print(output_schema.get_system_prompt_injection())

    print("\n验证 JSON 输出:")
    print("-" * 40)
    test_json = json.dumps({
        "name": "张三",
        "age": 25,
        "city": "北京",
        "is_active": True,
        "interests": ["编程", "阅读", "旅行"]
    }, ensure_ascii=False)

    try:
        validated_result = output_schema.validate_json(test_json)
        print(f"验证成功: {validated_result}")
        print(f"结果类型: {type(validated_result)}")
    except Exception as e:
        print(f"验证失败: {e}")


def demo_basic_usage():
    """演示基本使用方法"""
    print("\n" + "=" * 60)
    print("2. 基本使用演示")
    print("=" * 60)

    # 创建 JsonObjectOutputSchema
    schema = JsonObjectOutputSchema(UserProfile)

    print("JsonObjectOutputSchema 配置:")
    print(f"- 模式名称: {schema.name()}")
    print(f"- 是否纯文本: {schema.is_plain_text()}")
    print(f"- JSON Schema: {schema.json_schema()}")
    print(f"- 需要注入提示词: {schema.should_inject_to_system_prompt()}")

    print("\n生成的指令:")
    print("-" * 40)
    print(schema.get_system_prompt_injection())


def demo_validation():
    """演示验证功能"""
    print("\n" + "=" * 60)
    print("3. 验证功能演示")
    print("=" * 60)

    schema = JsonObjectOutputSchema(UserProfile)

    # 测试有效的 JSON
    valid_json = '''
    {
        "name": "张三",
        "age": 25,
        "city": "北京",
        "is_active": true,
        "interests": ["编程", "阅读", "旅行"]
    }
    '''

    print("验证有效 JSON:")
    print("-" * 40)
    try:
        result = schema.validate_json(valid_json)
        print(f"验证成功: {result.name}, {result.age}岁, 来自{result.city}")
        print(f"兴趣: {', '.join(result.interests)}")
    except Exception as e:
        print(f"验证失败: {e}")

    # 测试需要修复的 JSON（缺少引号）
    malformed_json = '''
    {
        name: "李四",
        age: 30,
        city: "上海",
        is_active: true,
        interests: ["音乐", "运动"]
    }
    '''

    print("\n验证需要修复的 JSON:")
    print("-" * 40)
    try:
        result = schema.validate_json(malformed_json)
        print(f"修复并验证成功: {result.name}, {result.age}岁, 来自{result.city}")
    except Exception as e:
        print(f"修复失败: {e}")


def demo_dataclass_support():
    """演示 dataclass 支持"""
    print("\n" + "=" * 60)
    print("4. Dataclass 支持演示")
    print("=" * 60)

    schema = JsonObjectOutputSchema.for_dataclass(TaskItem)

    print("Dataclass 输出模式:")
    print(f"- 模式名称: {schema.name()}")
    print(f"- 目标类型: {schema.target_type.__name__}")

    # 测试验证
    test_json = '''
    {
        "title": "完成项目文档",
        "description": "编写项目的技术文档和用户手册",
        "priority": 1,
        "completed": false
    }
    '''

    print("\n验证 dataclass JSON:")
    print("-" * 40)
    try:
        result = schema.validate_json(test_json)
        print(f"验证成功: {result.title} (优先级: {result.priority})")
        print(f"描述: {result.description}")
        print(f"状态: {'已完成' if result.completed else '未完成'}")
    except Exception as e:
        print(f"验证失败: {e}")


def demo_custom_instructions():
    """演示自定义指令"""
    print("\n" + "=" * 60)
    print("5. 自定义指令演示")
    print("=" * 60)

    custom_instructions = """
请返回一个包含用户信息的 JSON 对象。
必须包含以下字段：
- name: 用户姓名（字符串）
- age: 用户年龄（数字，0-150）
- city: 居住城市（字符串）
- is_active: 是否活跃（布尔值）
- interests: 兴趣爱好（字符串数组）

示例：{"name": "示例用户", "age": 25, "city": "北京", "is_active": true, "interests": ["阅读"]}
"""

    schema = JsonObjectOutputSchema(
        UserProfile,
        custom_instructions=custom_instructions
    )

    print("自定义指令:")
    print("-" * 40)
    print(schema.get_system_prompt_injection())


def demo_agent_integration():
    """演示与 Agent 系统的集成"""
    print("\n" + "=" * 60)
    print("6. Agent 系统集成演示")
    print("=" * 60)

    # 使用 JsonObjectOutputSchema 的 Agent
    json_object_agent = Agent(
        name="JsonObjectAgent",
        instructions="你是一个专业的用户信息处理助手",
        output_type=JsonObjectOutputSchema(UserProfile)
    )

    print("JsonObjectOutputSchema Agent:")
    print(f"- Agent 名称: {json_object_agent.name}")
    print(f"- 输出类型: {type(json_object_agent.output_type).__name__}")
    if json_object_agent.output_type and hasattr(json_object_agent.output_type, 'target_type'):
        print(f"- 目标类型: {json_object_agent.output_type.target_type.__name__}")
    if json_object_agent.output_type and hasattr(json_object_agent.output_type, 'should_inject_to_system_prompt'):
        print(f"- 需要注入: {json_object_agent.output_type.should_inject_to_system_prompt()}")

    # 使用标准 AgentOutputSchema 的 Agent（业务层控制）
    standard_agent = Agent(
        name="StandardAgent",
        instructions="你是一个标准的用户信息处理助手",
        output_type=AgentOutputSchema(UserProfile)
    )

    print("\n标准 AgentOutputSchema Agent:")
    print(f"- Agent 名称: {standard_agent.name}")
    print(f"- 输出类型: {type(standard_agent.output_type).__name__}")
    print("- 说明: 业务层根据模型能力选择合适的 Schema")





def demo_factory_methods():
    """演示工厂方法"""
    print("\n" + "=" * 60)
    print("7. 工厂方法演示")
    print("=" * 60)

    # Pydantic 模型工厂方法
    pydantic_schema = JsonObjectOutputSchema.for_pydantic_model(UserProfile)
    print(f"Pydantic 模型: {pydantic_schema.name()}")

    # Dataclass 工厂方法
    dataclass_schema = JsonObjectOutputSchema.for_dataclass(TaskItem)
    print(f"Dataclass: {dataclass_schema.name()}")

    # 显示不同类型的指令差异
    print("\nPydantic 模型指令 (前100字符):")
    print(pydantic_schema.get_system_prompt_injection()[:100] + "...")

    print("\nDataclass 指令 (前100字符):")
    print(dataclass_schema.get_system_prompt_injection()[:100] + "...")


def main():
    """主演示函数"""
    print("OpenAI Agents SDK - JSON Object 输出兼容性演示")
    print("=" * 60)
    print("本演示展示了新的结构化输出兼容性功能")
    print("支持仅接受 {'type': 'json_object'} 格式的 LLM 供应商")

    try:
        demo_json_object_output_schema()
        demo_basic_usage()
        demo_validation()
        demo_dataclass_support()
        demo_custom_instructions()
        demo_agent_integration()

        print("\n" + "=" * 60)
        print("演示完成！")
        print("=" * 60)
        print("\n主要功能总结:")
        print("✅ JsonObjectOutputSchema - 兼容 json_object 模式")
        print("✅ 自动指令生成 - 自动生成结构化指令")
        print("✅ 提示词注入 - 自动注入 schema 指令")
        print("✅ 统一验证机制 - 严格类型检查")
        print("✅ 简化设计 - 业务层控制路由，移除复杂的自动降级逻辑")
        print("✅ 工厂方法 - 便捷的创建方式")

    except Exception as e:
        print(f"\n演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
