#!/usr/bin/env python3
"""
JSON 修复功能演示

展示 OpenAI Agents SDK 的 JSON 修复功能，
能够自动修复 LLM 输出的各种格式异常。
"""

import json
from typing import Optional

from pydantic import BaseModel, Field

from agents import AgentOutputSchema, JsonObjectOutputSchema
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


def demo_basic_repair():
    """演示基本的 JSON 修复功能"""
    print("\n" + "=" * 60)
    print("1. 基本 JSON 修复功能演示")
    print("=" * 60)

    # 各种常见的 JSON 格式问题
    test_cases = [
        {
            "name": "缺少引号",
            "json": """{
                name: "张三",
                age: 25,
                city: "北京",
                is_active: true
            }"""
        },
        {
            "name": "尾随逗号",
            "json": """{
                "name": "李四",
                "age": 30,
                "city": "上海",
                "is_active": true,
                "interests": ["编程", "阅读",],
            }"""
        },
        {
            "name": "单引号",
            "json": """{
                'name': '王五',
                'age': 28,
                'city': '广州',
                'is_active': false,
                'interests': ['旅行', '摄影']
            }"""
        },
        {
            "name": "不完整的 JSON",
            "json": """{
                "name": "赵六",
                "age": 35,
                "city": "深圳",
                "is_active": true"""
        }
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. {case['name']}:")
        print("原始 JSON:")
        print(case['json'])

        try:
            result = repair_and_validate_json(case['json'])
            if result.success:
                print(f"✅ 修复成功: {result.repair_details}")
                print(f"修复后的 JSON: {result.repaired_json}")
                print(f"解析结果: {result.parsed_object}")
            else:
                print(f"❌ 修复失败: {result.repair_details}")
        except Exception as e:
            print(f"❌ 修复过程中出现异常: {e}")


def demo_type_validation_repair():
    """演示带类型验证的 JSON 修复"""
    print("\n" + "=" * 60)
    print("2. 带类型验证的 JSON 修复演示")
    print("=" * 60)

    from pydantic import TypeAdapter
    type_adapter = TypeAdapter(UserProfile)

    test_cases = [
        {
            "name": "修复后能通过类型验证",
            "json": """{
                name: "张三",
                age: 25,
                city: "北京",
                is_active: true,
                interests: ["编程", "阅读"]
            }"""
        },
        {
            "name": "修复后仍无法通过类型验证",
            "json": """{
                name: "李四",
                age: "无效年龄",
                city: "上海",
                is_active: true
            }"""
        }
    ]

    for i, case in enumerate(test_cases, 1):
        print(f"\n{i}. {case['name']}:")
        print("原始 JSON:")
        print(case['json'])

        result = repair_and_validate_json(case['json'], type_adapter)
        if result.success:
            print(f"✅ 修复和验证成功: {result.repair_details}")
            print(f"验证后的对象: {result.parsed_object}")
            print(f"对象类型: {type(result.parsed_object)}")
        else:
            print("❌ 修复或验证失败")
            if result.repair_applied:
                print(f"修复详情: {result.repair_details}")
            print(f"原始错误: {result.original_error}")


def demo_json_object_output_schema():
    """演示 JsonObjectOutputSchema 的修复功能"""
    print("\n" + "=" * 60)
    print("3. JsonObjectOutputSchema 修复功能演示")
    print("=" * 60)

    # 创建 JsonObjectOutputSchema
    schema = JsonObjectOutputSchema(UserProfile)

    print("默认启用修复功能:")
    print(f"修复功能状态: {'启用' if schema._enable_json_repair else '禁用'}")

    # 测试修复功能
    broken_json = """{
        name: "张三",
        age: 25,
        city: "北京",
        is_active: true,
        interests: ["编程", "阅读"]
    }"""

    print("\n测试损坏的 JSON:")
    print(broken_json)

    try:
        result = schema.validate_json(broken_json)
        print("✅ 修复和验证成功!")
        print(f"结果: {result}")
        print(f"类型: {type(result)}")
    except ModelBehaviorError as e:
        print(f"❌ 修复失败: {e}")

    # 测试禁用修复功能
    print("\n测试禁用修复功能:")
    schema_no_repair = JsonObjectOutputSchema(UserProfile, enable_json_repair=False)

    try:
        result = schema_no_repair.validate_json(broken_json)
        print(f"✅ 验证成功: {result}")
    except ModelBehaviorError as e:
        print(f"❌ 验证失败（预期）: {e}")


def demo_agent_output_schema():
    """演示 AgentOutputSchema 的修复功能"""
    print("\n" + "=" * 60)
    print("4. AgentOutputSchema 修复功能演示")
    print("=" * 60)

    # 创建 AgentOutputSchema
    schema = AgentOutputSchema(UserProfile)

    print("默认启用修复功能:")
    print(f"修复功能状态: {'启用' if schema._enable_json_repair else '禁用'}")

    # 测试修复功能
    broken_json = """{
        name: "李四",
        age: 30,
        city: "上海",
        is_active: false,
        interests: ["旅行", "摄影",]
    }"""

    print("\n测试损坏的 JSON:")
    print(broken_json)

    try:
        result = schema.validate_json(broken_json)
        print("✅ 修复和验证成功!")
        print(f"结果: {result}")
        print(f"类型: {type(result)}")
    except ModelBehaviorError as e:
        print(f"❌ 修复失败: {e}")


def demo_performance():
    """演示修复功能的性能"""
    print("\n" + "=" * 60)
    print("5. 性能演示")
    print("=" * 60)

    import time

    # 创建一个较大的 JSON 对象
    large_data = {
        "users": [
            {
                "name": f"用户{i}",
                "age": 20 + (i % 50),
                "city": "北京",
                "is_active": i % 2 == 0,
                "interests": ["编程", "阅读"] if i % 3 == 0 else ["旅行", "摄影"]
            }
            for i in range(100)
        ]
    }

    # 故意破坏 JSON 格式
    broken_json = json.dumps(large_data, ensure_ascii=False).replace('"name"', 'name')

    print(f"测试大型 JSON 修复（{len(broken_json)} 字符）")

    start_time = time.time()
    result = repair_and_validate_json(broken_json)
    end_time = time.time()

    if result.success:
        print("✅ 修复成功!")
        print(f"修复详情: {result.repair_details}")
        if result.parsed_object is not None:
            print(f"用户数量: {len(result.parsed_object['users'])}")
        print(f"修复耗时: {(end_time - start_time) * 1000:.2f} 毫秒")
    else:
        print(f"❌ 修复失败: {result.repair_details}")


def demo_error_cases():
    """演示错误处理"""
    print("\n" + "=" * 60)
    print("6. 错误处理演示")
    print("=" * 60)

    error_cases = [
        {
            "name": "空字符串",
            "json": ""
        },
        {
            "name": "完全无效的内容",
            "json": "这根本不是 JSON"
        },
        {
            "name": "部分损坏的复杂结构",
            "json": """{
                "data": {
                    "users": [
                        {"name": "张三", "age": 25},
                        {"name": "李四", "age":
                    ]
                }
            """
        }
    ]

    for i, case in enumerate(error_cases, 1):
        print(f"\n{i}. {case['name']}:")
        print(f"输入: {repr(case['json'])}")

        result = repair_and_validate_json(case['json'])
        if result.success:
            print(f"✅ 意外修复成功: {result.repair_details}")
            print(f"结果: {result.parsed_object}")
        else:
            print("❌ 修复失败（预期）")
            if result.repair_applied:
                print(f"修复详情: {result.repair_details}")


def main():
    """主函数"""
    print("OpenAI Agents SDK - JSON 修复功能演示")
    print("=" * 60)
    print("本演示展示了 SDK 的 JSON 修复功能")
    print("能够自动修复 LLM 输出的各种格式异常")
    print("使用 json-repair 库提供强大的修复能力")

    try:
        demo_basic_repair()
        demo_type_validation_repair()
        demo_json_object_output_schema()
        demo_agent_output_schema()
        demo_performance()
        demo_error_cases()

        print("\n" + "=" * 60)
        print("演示完成！")
        print("=" * 60)

        print("\n主要功能总结:")
        print("✅ 自动修复常见 JSON 格式问题")
        print("✅ 支持多种修复策略和重试机制")
        print("✅ 集成到 JsonObjectOutputSchema 和 AgentOutputSchema")
        print("✅ 可配置的修复功能开关")
        print("✅ 详细的修复日志和错误信息")
        print("✅ 高性能处理大型 JSON 数据")
        print("✅ 优雅的错误处理和降级策略")

        print("\n支持的修复类型:")
        print("• 缺少引号的属性名")
        print("• 尾随逗号")
        print("• 单引号替换双引号")
        print("• 不完整的 JSON 结构")
        print("• 其他常见格式错误")

    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
