from __future__ import annotations

from typing import Any

from openai import NOT_GIVEN
from typing_extensions import TypeGuard

from .exceptions import UserError

_EMPTY_SCHEMA = {
    "additionalProperties": False,
    "type": "object",
    "properties": {},
    "required": [],
}


def ensure_strict_json_schema(
    schema: dict[str, Any],
) -> dict[str, Any]:
    """Mutates the given JSON schema to ensure it conforms to the `strict` standard
    that the OpenAI API expects.

    Additionally, this function inlines all $ref references to ensure compatibility
    with LLM models that don't support JSON Schema $ref (e.g., Gemini 2.5 Pro).
    """
    if schema == {}:
        return _EMPTY_SCHEMA

    # 第一步：应用 strict 模式的所有规则
    strict_schema = _ensure_strict_json_schema(schema, path=(), root=schema)

    # 第二步：完全展开所有 $ref 引用
    inlined_schema = inline_all_refs(strict_schema)

    # 第三步：移除 $defs 和 definitions（已经没有引用了）
    inlined_schema.pop("$defs", None)
    inlined_schema.pop("definitions", None)

    return inlined_schema


# Adapted from https://github.com/openai/openai-python/blob/main/src/openai/lib/_pydantic.py
def _ensure_strict_json_schema(
    json_schema: object,
    *,
    path: tuple[str, ...],
    root: dict[str, object],
) -> dict[str, Any]:
    if not is_dict(json_schema):
        raise TypeError(f"Expected {json_schema} to be a dictionary; path={path}")

    defs = json_schema.get("$defs")
    if is_dict(defs):
        for def_name, def_schema in defs.items():
            _ensure_strict_json_schema(def_schema, path=(*path, "$defs", def_name), root=root)

    definitions = json_schema.get("definitions")
    if is_dict(definitions):
        for definition_name, definition_schema in definitions.items():
            _ensure_strict_json_schema(
                definition_schema, path=(*path, "definitions", definition_name), root=root
            )

    typ = json_schema.get("type")
    if typ == "object" and "additionalProperties" not in json_schema:
        json_schema["additionalProperties"] = False
    elif (
        typ == "object"
        and "additionalProperties" in json_schema
        and json_schema["additionalProperties"]
    ):
        raise UserError(
            "additionalProperties should not be set for object types. This could be because "
            "you're using an older version of Pydantic, or because you configured additional "
            "properties to be allowed. If you really need this, update the function or output tool "
            "to not use a strict schema."
        )

    # object types
    # { 'type': 'object', 'properties': { 'a':  {...} } }
    properties = json_schema.get("properties")
    if is_dict(properties):
        json_schema["required"] = list(properties.keys())
        json_schema["properties"] = {
            key: _ensure_strict_json_schema(prop_schema, path=(*path, "properties", key), root=root)
            for key, prop_schema in properties.items()
        }

    # arrays
    # { 'type': 'array', 'items': {...} }
    items = json_schema.get("items")
    if is_dict(items):
        json_schema["items"] = _ensure_strict_json_schema(items, path=(*path, "items"), root=root)

    # unions
    any_of = json_schema.get("anyOf")
    if is_list(any_of):
        json_schema["anyOf"] = [
            _ensure_strict_json_schema(variant, path=(*path, "anyOf", str(i)), root=root)
            for i, variant in enumerate(any_of)
        ]

    # intersections
    all_of = json_schema.get("allOf")
    if is_list(all_of):
        if len(all_of) == 1:
            json_schema.update(
                _ensure_strict_json_schema(all_of[0], path=(*path, "allOf", "0"), root=root)
            )
            json_schema.pop("allOf")
        else:
            json_schema["allOf"] = [
                _ensure_strict_json_schema(entry, path=(*path, "allOf", str(i)), root=root)
                for i, entry in enumerate(all_of)
            ]

    # strip `None` defaults as there's no meaningful distinction here
    # the schema will still be `nullable` and the model will default
    # to using `None` anyway
    if json_schema.get("default", NOT_GIVEN) is None:
        json_schema.pop("default")

    # we can't use `$ref`s if there are also other properties defined, e.g.
    # `{"$ref": "...", "description": "my description"}`
    #
    # so we unravel the ref
    # `{"type": "string", "description": "my description"}`
    ref = json_schema.get("$ref")
    if ref and has_more_than_n_keys(json_schema, 1):
        assert isinstance(ref, str), f"Received non-string $ref - {ref}"

        resolved = resolve_ref(root=root, ref=ref)
        if not is_dict(resolved):
            raise ValueError(
                f"Expected `$ref: {ref}` to resolved to a dictionary but got {resolved}"
            )

        # properties from the json schema take priority over the ones on the `$ref`
        json_schema.update({**resolved, **json_schema})
        json_schema.pop("$ref")
        # Since the schema expanded from `$ref` might not have `additionalProperties: false` applied
        # we call `_ensure_strict_json_schema` again to fix the inlined schema and ensure it's valid
        return _ensure_strict_json_schema(json_schema, path=path, root=root)

    return json_schema


def resolve_ref(*, root: dict[str, object], ref: str) -> object:
    if not ref.startswith("#/"):
        raise ValueError(f"Unexpected $ref format {ref!r}; Does not start with #/")

    path = ref[2:].split("/")
    resolved = root
    for key in path:
        value = resolved[key]
        assert is_dict(value), (
            f"encountered non-dictionary entry while resolving {ref} - {resolved}"
        )
        resolved = value

    return resolved


def is_dict(obj: object) -> TypeGuard[dict[str, object]]:
    # just pretend that we know there are only `str` keys
    # as that check is not worth the performance cost
    return isinstance(obj, dict)


def is_list(obj: object) -> TypeGuard[list[object]]:
    return isinstance(obj, list)


def has_more_than_n_keys(obj: dict[str, object], n: int) -> bool:
    i = 0
    for _ in obj.keys():
        i += 1
        if i > n:
            return True
    return False


def inline_all_refs(
    schema: dict[str, Any],
    *,
    root: dict[str, Any] | None = None,
    visited: set[str] | None = None,
) -> dict[str, Any]:
    """完全展开 JSON Schema 中的所有 $ref 引用。

    这个函数递归遍历 JSON Schema，将所有 $ref 引用替换为实际定义的内联版本。
    这样可以确保与不支持 JSON Schema $ref 的 LLM 模型（如 Gemini 2.5 Pro）兼容。

    Args:
        schema: 要处理的 JSON Schema
        root: 根 schema（用于解析 $ref），如果为 None 则使用 schema 本身
        visited: 已访问的 $ref 集合（用于检测循环引用）

    Returns:
        展开后的 JSON Schema（不包含任何 $ref）

    Raises:
        ValueError: 当检测到循环引用时
    """
    if root is None:
        root = schema
    if visited is None:
        visited = set()

    # 如果不是字典，直接返回
    if not is_dict(schema):
        return {}

    # 1. 如果当前节点有 $ref，解析并替换
    ref = schema.get("$ref")
    if ref:
        assert isinstance(ref, str), f"Received non-string $ref - {ref}"

        # 检测循环引用
        if ref in visited:
            raise ValueError(f"Circular reference detected: {ref}")

        # 解析 $ref
        resolved = resolve_ref(root=root, ref=ref)
        if not is_dict(resolved):
            raise ValueError(
                f"Expected `$ref: {ref}` to resolve to a dictionary but got {resolved}"
            )

        # 标记为已访问
        new_visited = visited | {ref}

        # 递归展开解析后的定义
        inlined = inline_all_refs(resolved, root=root, visited=new_visited)

        # 合并其他属性（如 description），$ref 之外的属性优先
        result = {**inlined, **{k: v for k, v in schema.items() if k != "$ref"}}

        return result

    # 2. 递归处理嵌套结构
    result = dict(schema)

    # 处理 properties
    properties = result.get("properties")
    if is_dict(properties):
        result["properties"] = {
            key: inline_all_refs(prop if is_dict(prop) else {}, root=root, visited=visited)
            for key, prop in properties.items()
        }

    # 处理 items（数组）
    items = result.get("items")
    if is_dict(items):
        result["items"] = inline_all_refs(items, root=root, visited=visited)

    # 处理 anyOf
    any_of = result.get("anyOf")
    if is_list(any_of):
        result["anyOf"] = [
            inline_all_refs(variant if is_dict(variant) else {}, root=root, visited=visited)
            for variant in any_of
        ]

    # 处理 allOf
    all_of = result.get("allOf")
    if is_list(all_of):
        result["allOf"] = [
            inline_all_refs(entry if is_dict(entry) else {}, root=root, visited=visited)
            for entry in all_of
        ]

    # 处理 $defs（递归展开其中的定义，但不移除，因为可能还有其他地方引用）
    defs = result.get("$defs")
    if is_dict(defs):
        result["$defs"] = {
            key: inline_all_refs(
                def_schema if is_dict(def_schema) else {},
                root=root,
                visited=visited,
            )
            for key, def_schema in defs.items()
        }

    # 处理 definitions（同 $defs）
    definitions = result.get("definitions")
    if is_dict(definitions):
        result["definitions"] = {
            key: inline_all_refs(
                def_schema if is_dict(def_schema) else {},
                root=root,
                visited=visited,
            )
            for key, def_schema in definitions.items()
        }

    return result
