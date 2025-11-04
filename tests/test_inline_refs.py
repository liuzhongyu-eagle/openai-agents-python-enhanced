"""测试 inline_all_refs 函数的功能"""

from agents.strict_schema import inline_all_refs


def test_inline_simple_ref():
    """测试简单的 $ref 展开"""
    schema = {
        "$defs": {
            "UserProfile": {
                "type": "object",
                "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
                "required": ["name", "age"],
                "additionalProperties": False,
            }
        },
        "properties": {"profile": {"$ref": "#/$defs/UserProfile"}},
        "required": ["profile"],
        "type": "object",
        "additionalProperties": False,
    }

    result = inline_all_refs(schema)

    # 验证 $ref 被展开
    assert "$ref" not in result["properties"]["profile"]
    assert result["properties"]["profile"]["type"] == "object"
    assert "name" in result["properties"]["profile"]["properties"]
    assert "age" in result["properties"]["profile"]["properties"]
    assert result["properties"]["profile"]["required"] == ["name", "age"]
    assert result["properties"]["profile"]["additionalProperties"] is False


def test_inline_nested_refs():
    """测试嵌套的 $ref 展开"""
    schema = {
        "$defs": {
            "Address": {
                "type": "object",
                "properties": {"city": {"type": "string"}, "street": {"type": "string"}},
                "required": ["city", "street"],
                "additionalProperties": False,
            },
            "UserProfile": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "address": {"$ref": "#/$defs/Address"},
                },
                "required": ["name", "address"],
                "additionalProperties": False,
            },
        },
        "properties": {"profile": {"$ref": "#/$defs/UserProfile"}},
        "required": ["profile"],
        "type": "object",
        "additionalProperties": False,
    }

    result = inline_all_refs(schema)

    # 验证外层 $ref 被展开
    assert "$ref" not in result["properties"]["profile"]
    assert result["properties"]["profile"]["type"] == "object"

    # 验证嵌套的 $ref 也被展开
    assert "$ref" not in result["properties"]["profile"]["properties"]["address"]
    assert result["properties"]["profile"]["properties"]["address"]["type"] == "object"
    assert "city" in result["properties"]["profile"]["properties"]["address"]["properties"]
    assert "street" in result["properties"]["profile"]["properties"]["address"]["properties"]


def test_inline_ref_with_extra_properties():
    """测试 $ref + 额外属性（如 description）"""
    schema = {
        "$defs": {
            "UserProfile": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            }
        },
        "properties": {"profile": {"$ref": "#/$defs/UserProfile", "description": "用户画像信息"}},
        "required": ["profile"],
        "type": "object",
        "additionalProperties": False,
    }

    result = inline_all_refs(schema)

    # 验证 $ref 被展开
    assert "$ref" not in result["properties"]["profile"]
    assert result["properties"]["profile"]["type"] == "object"

    # 验证额外属性被保留
    assert result["properties"]["profile"]["description"] == "用户画像信息"


def test_inline_anyof_refs():
    """测试 anyOf 中的 $ref 展开"""
    schema = {
        "$defs": {
            "StringType": {"type": "string"},
            "IntType": {"type": "integer"},
        },
        "properties": {
            "value": {"anyOf": [{"$ref": "#/$defs/StringType"}, {"$ref": "#/$defs/IntType"}]}
        },
        "required": ["value"],
        "type": "object",
        "additionalProperties": False,
    }

    result = inline_all_refs(schema)

    # 验证 anyOf 中的 $ref 被展开
    assert len(result["properties"]["value"]["anyOf"]) == 2
    assert "$ref" not in result["properties"]["value"]["anyOf"][0]
    assert "$ref" not in result["properties"]["value"]["anyOf"][1]
    assert result["properties"]["value"]["anyOf"][0]["type"] == "string"
    assert result["properties"]["value"]["anyOf"][1]["type"] == "integer"


def test_inline_allof_refs():
    """测试 allOf 中的 $ref 展开"""
    schema = {
        "$defs": {
            "Base": {"type": "object", "properties": {"id": {"type": "integer"}}},
            "Extended": {"type": "object", "properties": {"name": {"type": "string"}}},
        },
        "properties": {"item": {"allOf": [{"$ref": "#/$defs/Base"}, {"$ref": "#/$defs/Extended"}]}},
        "required": ["item"],
        "type": "object",
        "additionalProperties": False,
    }

    result = inline_all_refs(schema)

    # 验证 allOf 中的 $ref 被展开
    assert len(result["properties"]["item"]["allOf"]) == 2
    assert "$ref" not in result["properties"]["item"]["allOf"][0]
    assert "$ref" not in result["properties"]["item"]["allOf"][1]
    assert result["properties"]["item"]["allOf"][0]["type"] == "object"
    assert result["properties"]["item"]["allOf"][1]["type"] == "object"


def test_inline_array_items_ref():
    """测试数组 items 中的 $ref 展开"""
    schema = {
        "$defs": {
            "Item": {
                "type": "object",
                "properties": {"name": {"type": "string"}},
                "required": ["name"],
                "additionalProperties": False,
            }
        },
        "properties": {"items": {"type": "array", "items": {"$ref": "#/$defs/Item"}}},
        "required": ["items"],
        "type": "object",
        "additionalProperties": False,
    }

    result = inline_all_refs(schema)

    # 验证 items 中的 $ref 被展开
    assert "$ref" not in result["properties"]["items"]["items"]
    assert result["properties"]["items"]["items"]["type"] == "object"
    assert "name" in result["properties"]["items"]["items"]["properties"]


def test_no_refs_schema():
    """测试没有 $ref 的 schema（应该保持不变）"""
    schema = {
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
        "type": "object",
        "additionalProperties": False,
    }

    result = inline_all_refs(schema)

    # 验证 schema 保持不变
    assert result == schema


def test_circular_reference_detection():
    """测试循环引用检测"""
    # 注意：这个测试模拟了一个循环引用的场景
    # 在实际的 Pydantic 生成的 schema 中，循环引用通常会被处理
    schema = {
        "$defs": {
            "Node": {
                "type": "object",
                "properties": {
                    "value": {"type": "integer"},
                    "next": {"$ref": "#/$defs/Node"},  # 自引用
                },
                "required": ["value"],
                "additionalProperties": False,
            }
        },
        "properties": {"root": {"$ref": "#/$defs/Node"}},
        "required": ["root"],
        "type": "object",
        "additionalProperties": False,
    }

    # 应该抛出 ValueError
    try:
        inline_all_refs(schema)
        raise AssertionError("应该抛出 ValueError")
    except ValueError as e:
        assert "Circular reference detected" in str(e)


def test_multiple_refs_to_same_def():
    """测试多个地方引用同一个定义"""
    schema = {
        "$defs": {
            "Address": {
                "type": "object",
                "properties": {"city": {"type": "string"}},
                "required": ["city"],
                "additionalProperties": False,
            }
        },
        "properties": {
            "home": {"$ref": "#/$defs/Address"},
            "work": {"$ref": "#/$defs/Address"},
        },
        "required": ["home", "work"],
        "type": "object",
        "additionalProperties": False,
    }

    result = inline_all_refs(schema)

    # 验证两个引用都被展开
    assert "$ref" not in result["properties"]["home"]
    assert "$ref" not in result["properties"]["work"]
    assert result["properties"]["home"]["type"] == "object"
    assert result["properties"]["work"]["type"] == "object"
    assert "city" in result["properties"]["home"]["properties"]
    assert "city" in result["properties"]["work"]["properties"]
