#!/usr/bin/env python3
"""
OpenAI Agents SDK - JSON Object 输出兼容性演示

本演示展示了新的 JsonObjectOutputSchema 和智能降级功能，
支持仅接受 {'type': 'json_object'} 格式的 LLM 供应商。

功能特性：
1. JsonObjectOutputSchema - 专为 json_object 模式设计的输出模式
2. 智能降级机制 - 自动检测模型能力并降级到 json_object
3. 智能指令生成 - 自动生成结构化的 JSON 输出指令
4. 提示词注入 - 将 schema 指令注入到系统提示词中
5. 统一验证机制 - 使用 Pydantic 进行严格类型检查
"""

import json
from dataclasses import dataclass
from typing import Optional

from pydantic import BaseModel, Field

# 导入新的 JSON Object 兼容性功能
from agents import (
    Agent,
    AgentOutputSchema,
    InstructionGenerator,
    JsonObjectOutputSchema,
    ModelCapabilityDetector,
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


def demo_instruction_generator():
    """演示智能指令生成器"""
    print("\n" + "=" * 60)
    print("2. 智能指令生成器演示")
    print("=" * 60)

    # 中文指令生成
    print("中文指令:")
    print("-" * 40)
    zh_instructions = InstructionGenerator.generate_json_instructions(
        UserProfile,
        language="zh",
        include_examples=True
    )
    print(zh_instructions)

    # 英文指令生成
    print("\n英文指令:")
    print("-" * 40)
    en_instructions = InstructionGenerator.generate_json_instructions(
        UserProfile,
        language="en",
        include_examples=True
    )
    print(en_instructions)

    # 自定义指令
    print("\n自定义指令:")
    print("-" * 40)
    custom_instructions = "请返回用户信息的 JSON 对象，包含所有必需字段"
    custom_result = InstructionGenerator.generate_json_instructions(
        UserProfile,
        custom_instructions=custom_instructions
    )
    print(custom_result)


def demo_model_capability_detection():
    """演示模型能力检测"""
    print("\n" + "=" * 60)
    print("3. 模型能力检测演示")
    print("=" * 60)

    # 模拟不同类型的模型
    test_models = [
        ("OpenAI GPT-4", "gpt-4-turbo"),
        ("Claude 3", "claude-3-sonnet"),
        ("未知模型", "unknown-model"),
        ("自定义模型", "custom-llm-v1")
    ]

    for model_name, model_str in test_models:
        # 创建模拟模型对象
        class MockModel:
            def __init__(self, model_string: str):
                self.model_string = model_string

            def __str__(self):
                return self.model_string

        mock_model = MockModel(model_str)
        supports_json_schema = ModelCapabilityDetector.supports_json_schema(mock_model)

        print(f"{model_name} ({model_str}): "
              f"{'支持' if supports_json_schema else '不支持'} json_schema")


def demo_smart_fallback():
    """演示智能降级机制"""
    print("\n" + "=" * 60)
    print("4. 智能降级机制演示")
    print("=" * 60)

    # 创建启用智能降级的输出模式
    fallback_schema = AgentOutputSchema(
        UserProfile,
        fallback_to_json_object=True
    )

    print("智能降级配置:")
    print(f"- 启用降级: {fallback_schema.fallback_to_json_object}")
    print(f"- 目标类型: {fallback_schema.output_type.__name__}")

    # 模拟不同模型的降级行为
    class MockUnsupportedModel:
        def __str__(self):
            return "unsupported-model"

    class MockSupportedModel:
        def __str__(self):
            return "gpt-4-turbo"

    unsupported_model = MockUnsupportedModel()
    supported_model = MockSupportedModel()

    print(f"\n不支持的模型 ({unsupported_model}):")
    print(f"- 需要注入: {fallback_schema.should_inject_to_system_prompt(unsupported_model)}")
    if fallback_schema.should_inject_to_system_prompt(unsupported_model):
        print("- 注入的指令:")
        print("  " + fallback_schema.get_system_prompt_injection().replace("\n", "\n  "))

    print(f"\n支持的模型 ({supported_model}):")
    print(f"- 需要注入: {fallback_schema.should_inject_to_system_prompt(supported_model)}")


def demo_agent_integration():
    """演示与 Agent 系统的集成"""
    print("\n" + "=" * 60)
    print("5. Agent 系统集成演示")
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

    # 使用智能降级的 Agent
    smart_agent = Agent(
        name="SmartAgent",
        instructions="你是一个智能的用户信息处理助手",
        output_type=AgentOutputSchema(UserProfile, fallback_to_json_object=True)
    )

    print("\n智能降级 Agent:")
    print(f"- Agent 名称: {smart_agent.name}")
    print(f"- 输出类型: {type(smart_agent.output_type).__name__}")
    if smart_agent.output_type and hasattr(smart_agent.output_type, 'fallback_to_json_object'):
        print(f"- 启用降级: {smart_agent.output_type.fallback_to_json_object}")


def demo_configuration():
    """演示配置功能"""
    print("\n" + "=" * 60)
    print("6. 简化配置演示")
    print("=" * 60)

    print("配置已简化为常量，移除了复杂的全局配置类：")
    print("- 默认语言: 中文 (zh)")
    print("- 默认包含示例: True")
    print("- 指令缓存: 启用")
    print("- 验证器缓存: 启用")

    print("\n如需自定义配置，可在创建时指定：")
    print("# 英文指令")
    en_schema = JsonObjectOutputSchema(
        TaskItem,
        instruction_language="en",
        include_examples=False
    )
    print("英文模式下的指令 (前100字符):")
    print(en_schema.get_system_prompt_injection()[:100] + "...")

    print("\n# 中文指令（默认）")
    zh_schema = JsonObjectOutputSchema(TaskItem)
    print("中文模式下的指令 (前100字符):")
    print(zh_schema.get_system_prompt_injection()[:100] + "...")


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
        demo_instruction_generator()
        demo_model_capability_detection()
        demo_smart_fallback()
        demo_agent_integration()
        demo_configuration()
        demo_factory_methods()

        print("\n" + "=" * 60)
        print("演示完成！")
        print("=" * 60)
        print("\n主要功能总结:")
        print("✅ JsonObjectOutputSchema - 兼容 json_object 模式")
        print("✅ 智能指令生成 - 自动生成结构化指令")
        print("✅ 模型能力检测 - 自动检测模型支持")
        print("✅ 智能降级机制 - 自动降级到 json_object")
        print("✅ 提示词注入 - 自动注入 schema 指令")
        print("✅ 统一验证机制 - 严格类型检查")
        print("✅ 简化配置 - 实例级配置，无全局状态")
        print("✅ 工厂方法 - 便捷的创建方式")

    except Exception as e:
        print(f"\n演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
