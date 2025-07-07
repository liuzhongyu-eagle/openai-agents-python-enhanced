"""
JSON Object 输出兼容性模块

该模块提供对仅支持 {'type': 'json_object'} 格式的 LLM 供应商的兼容性支持。
主要包含：
1. JsonObjectOutputSchema - 兼容性输出模式类
2. InstructionGenerator - 智能指令生成器
3. ModelCapabilityDetector - 模型能力检测器
4. 相关配置和工具类
"""

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel, TypeAdapter, ValidationError

from .agent_output import AgentOutputSchemaBase
from .exceptions import ModelBehaviorError

logger = logging.getLogger(__name__)


# 简化的配置常量 - 移除不必要的全局配置
_DEFAULT_LANGUAGE = "zh"
_DEFAULT_INCLUDE_EXAMPLES = True
_ENABLE_INSTRUCTION_CACHE = True
_ENABLE_VALIDATOR_CACHE = True


class ModelCapabilityDetector:
    """检测模型供应商能力的工具类"""

    # 已知支持 json_schema 的模型名称模式
    KNOWN_JSON_SCHEMA_MODELS = [
        "gpt-4", "gpt-3.5-turbo", "gpt-4o", "gpt-4-turbo",
        "claude-3", "claude-3.5",
        "gemini-pro", "gemini-1.5"
    ]

    @classmethod
    def supports_json_schema(cls, model: Any) -> bool:
        """
        检测模型是否支持完整的 json_schema 格式

        Args:
            model: 模型实例或模型名称

        Returns:
            bool: 是否支持 json_schema
        """
        # 1. 检查模型是否有显式的能力声明方法
        if hasattr(model, 'supports_json_schema'):
            try:
                result = model.supports_json_schema()
                return bool(result)
            except Exception as e:
                logger.warning(f"调用模型的 supports_json_schema 方法失败: {e}")

        # 2. 检查模型是否有能力属性
        if hasattr(model, 'capabilities'):
            capabilities = getattr(model, 'capabilities', {})
            if isinstance(capabilities, dict):
                return bool(capabilities.get('json_schema', False))

        # 3. 基于模型名称的启发式检测
        model_str = str(model).lower()
        for known_model in cls.KNOWN_JSON_SCHEMA_MODELS:
            if known_model.lower() in model_str:
                logger.debug(f"基于名称检测到支持 json_schema 的模型: {model_str}")
                return True

        # 4. 检查模型类型（OpenAI 官方模型默认支持）
        model_type = type(model).__name__.lower()
        if 'openai' in model_type and 'chatcompletions' in model_type:
            logger.debug(f"检测到 OpenAI ChatCompletions 模型，默认支持 json_schema: {model_type}")
            return True

        # 5. 默认假设不支持（保守策略）
        logger.debug(f"未能确定模型能力，默认假设不支持 json_schema: {model_str}")
        return False


class InstructionGenerator:
    """简化的指令生成器，为 JsonObjectOutputSchema 生成结构化指令"""

    # 指令缓存（简化键）
    _instruction_cache: dict[tuple[Any, ...], str] = {}

    @classmethod
    def generate_json_instructions(
        cls,
        target_type: type[Any],
        language: str = "zh",
        include_examples: bool = True,
        custom_instructions: Optional[str] = None
    ) -> str:
        """
        基于目标类型生成 JSON 输出指令（简化版）

        Args:
            target_type: 目标 Python 类型
            language: 指令语言（保留兼容性，但固定使用中文）
            include_examples: 是否包含示例（保留兼容性，但固定包含）
            custom_instructions: 自定义指令（如果提供，将覆盖自动生成的指令）

        Returns:
            str: 生成的指令字符串
        """
        # 如果提供了自定义指令，直接返回
        if custom_instructions:
            return custom_instructions

        # 简化：固定使用中文和包含示例，检查缓存
        if _ENABLE_INSTRUCTION_CACHE:
            cache_key = (target_type,)  # 简化缓存键
            if cache_key in cls._instruction_cache:
                return cls._instruction_cache[cache_key]

        try:
            # 生成简化指令（固定中文+示例）
            instruction = cls._generate_simple_instruction(target_type)

            # 缓存指令
            if _ENABLE_INSTRUCTION_CACHE:
                cls._instruction_cache[cache_key] = instruction

            return instruction

        except Exception as e:
            logger.error(f"生成指令失败: {e}")
            # 返回基础指令作为降级方案
            return "请返回一个严格符合 JSON 格式的对象。确保输出严格符合 JSON 语法，所有字符串值都用双引号包围。"

    @classmethod
    def _generate_simple_instruction(cls, target_type: type[Any]) -> str:
        """生成简化的指令（固定中文+示例）"""
        try:
            # 提取类型信息
            type_info = cls._extract_type_info(target_type)

            # 构建简化指令
            instruction_parts = ["请返回一个严格符合 JSON 格式的对象，包含以下字段："]

            # 添加字段描述
            for field_name, field_info in type_info.get("fields", {}).items():
                field_line = f"- {field_name} ({field_info.get('type', 'unknown')}): {field_info.get('description', '无描述')}"
                instruction_parts.append(field_line)

            # 添加必需字段说明
            if type_info.get("has_required_fields", True):
                instruction_parts.append("所有字段都是必需的。")

            # 添加简单示例
            try:
                example = cls._generate_example(target_type)
                if example:
                    instruction_parts.extend([
                        "",  # 空行
                        "示例输出：",
                        example
                    ])
            except Exception:
                pass  # 忽略示例生成错误

            # 添加格式说明
            instruction_parts.append("")
            instruction_parts.append("请确保输出严格符合 JSON 语法，所有字符串值都用双引号包围。")

            return "\n".join(instruction_parts)

        except Exception as e:
            logger.error(f"生成简化指令失败: {e}")
            return "请返回一个严格符合 JSON 格式的对象。确保输出严格符合 JSON 语法，所有字符串值都用双引号包围。"



    @classmethod
    def _extract_type_info(cls, target_type: type[Any]) -> dict[str, Any]:
        """提取类型信息，包括字段、类型、描述等"""
        type_info: dict[str, Any] = {
            "fields": {},
            "has_required_fields": True
        }

        try:
            # 使用 TypeAdapter 获取 JSON Schema
            adapter = TypeAdapter(target_type)
            schema = adapter.json_schema()

            # 解析 schema 中的字段信息
            if "properties" in schema:
                properties = schema["properties"]
                if isinstance(properties, dict):
                    for field_name, field_schema in properties.items():
                        if isinstance(field_schema, dict):
                            field_info = {
                                "type": cls._schema_type_to_readable(
                                    field_schema.get("type", "unknown")
                                ),
                                "description": field_schema.get("description", "无描述")
                            }
                            type_info["fields"][field_name] = field_info

            # 检查是否有必需字段
            required_fields = schema.get("required", [])
            type_info["has_required_fields"] = len(required_fields) > 0

        except Exception as e:
            logger.warning(f"提取类型信息失败: {e}")
            # 降级方案：尝试从类型注解中提取
            type_info = cls._extract_type_info_fallback(target_type)

        return type_info

    @classmethod
    def _schema_type_to_readable(cls, schema_type: str) -> str:
        """将 JSON Schema 类型转换为可读的中文类型名"""
        type_mapping = {
            "string": "字符串",
            "integer": "整数",
            "number": "数字",
            "boolean": "布尔值",
            "array": "数组",
            "object": "对象",
            "null": "空值"
        }
        return type_mapping.get(schema_type, schema_type)

    @classmethod
    def _extract_type_info_fallback(cls, target_type: type[Any]) -> dict[str, Any]:
        """降级方案：从类型注解中提取信息"""
        type_info = {
            "fields": {},
            "has_required_fields": True
        }

        # 这里可以添加更多的降级逻辑
        # 例如检查 dataclass、TypedDict 等

        return type_info

    @classmethod
    def _generate_example(cls, target_type: type[Any]) -> Optional[str]:
        """生成示例 JSON 输出"""
        try:
            # 使用 TypeAdapter 生成示例
            adapter = TypeAdapter(target_type)
            schema = adapter.json_schema()

            # 基于 schema 生成示例数据
            example_data = cls._generate_example_from_schema(schema)

            if example_data is not None:
                return json.dumps(example_data, ensure_ascii=False, indent=2)

        except Exception as e:
            logger.warning(f"生成示例失败: {e}")

        return None

    @classmethod
    def _generate_example_from_schema(cls, schema: dict[str, Any]) -> Any:
        """基于 JSON Schema 生成示例数据"""
        schema_type = schema.get("type")

        if schema_type == "object":
            example = {}
            properties = schema.get("properties", {})
            for field_name, field_schema in properties.items():
                example[field_name] = cls._generate_example_from_schema(field_schema)
            return example

        elif schema_type == "array":
            items_schema = schema.get("items", {"type": "string"})
            example_item = cls._generate_example_from_schema(items_schema)
            return [example_item]

        elif schema_type == "string":
            return "示例文本"

        elif schema_type == "integer":
            return 42

        elif schema_type == "number":
            return 3.14

        elif schema_type == "boolean":
            return True

        else:
            return None


class JsonObjectOutputSchema(AgentOutputSchemaBase):
    """
    兼容仅支持 json_object 格式的 LLM 供应商的输出模式

    该类向 LLM 供应商声明输出格式为通用 JSON 对象，
    同时在本地进行严格的类型验证。
    """

    # 验证器缓存
    _validator_cache: dict[type[Any], TypeAdapter[Any]] = {}

    def __init__(
        self,
        target_type: type[Any],
        *,
        custom_instructions: Optional[str] = None
    ):
        """
        初始化 JsonObjectOutputSchema

        Args:
            target_type: 目标 Python 类型（Pydantic 模型、dataclass 等）
            custom_instructions: 自定义指令（如果提供，将覆盖自动生成的指令）
        """
        self._target_type = target_type
        self._custom_instructions = custom_instructions

        # 初始化验证器
        self._init_type_adapter()

        # 生成指令（简化版，固定使用中文和包含示例）
        if custom_instructions:
            self._generated_instructions = custom_instructions
        else:
            self._generated_instructions = InstructionGenerator.generate_json_instructions(
                target_type=target_type,
                language="zh",  # 固定使用中文
                include_examples=True,  # 固定包含示例
                custom_instructions=None
            )

    def _init_type_adapter(self) -> None:
        """初始化类型适配器"""
        if _ENABLE_VALIDATOR_CACHE:
            if self._target_type not in self._validator_cache:
                self._validator_cache[self._target_type] = TypeAdapter(self._target_type)
            self._type_adapter = self._validator_cache[self._target_type]
        else:
            self._type_adapter = TypeAdapter(self._target_type)

    def is_plain_text(self) -> bool:
        """返回 False，表示输出是 JSON 对象而非纯文本"""
        return False

    def name(self) -> str:
        """返回模式名称，用于日志和调试"""
        return f"JsonObjectOutputSchema({self._target_type.__name__})"

    def json_schema(self) -> dict[str, Any]:
        """
        返回传递给 LLM 供应商的 JSON Schema
        对于 json_object 模式，返回通用对象定义
        """
        return {"type": "object"}

    def is_strict_json_schema(self) -> bool:
        """返回 False，因为不使用严格的 JSON Schema"""
        return False

    def get_system_prompt_injection(self) -> str:
        """
        获取需要注入到系统提示词中的指令

        这是 json_object 模式的关键特性：由于 json_object 模式不支持传递完整的 JSON Schema，
        我们需要将 schema 定义以文本形式注入到系统提示词中，
        这是支持 json_object 的大模型的标准推荐用法。

        Returns:
            str: 需要注入到系统提示词中的指令文本
        """
        return self._generated_instructions

    def should_inject_to_system_prompt(self) -> bool:
        """
        判断是否需要将指令注入到系统提示词中

        对于 JsonObjectOutputSchema，总是返回 True，因为 json_object 模式
        需要在提示词中明确给出 schema 定义。

        Returns:
            bool: 是否需要注入到系统提示词
        """
        return True

    def validate_json(self, json_str: str) -> Any:
        """
        验证 LLM 生成的 JSON 字符串

        Args:
            json_str: LLM 返回的 JSON 字符串

        Returns:
            验证后的 Python 对象

        Raises:
            ModelBehaviorError: 当 JSON 无效或不符合目标类型时
        """
        logger.debug(f"开始验证 JSON: {json_str[:100]}...")

        try:
            # 首先尝试解析 JSON
            json_obj = json.loads(json_str)
            logger.debug(f"JSON 解析成功，类型: {type(json_obj)}")
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}")
            raise ModelBehaviorError(
                f"LLM 返回的内容不是有效的 JSON: {e}"
            ) from e

        try:
            # 然后进行类型验证
            validated_obj = self._type_adapter.validate_python(json_obj)
            logger.debug(f"类型验证成功，返回类型: {type(validated_obj)}")
            return validated_obj

        except ValidationError as e:
            logger.error(f"类型验证失败: {e}")
            # 简化：总是使用严格验证
            raise ModelBehaviorError(
                f"LLM 生成的 JSON 无效，不符合预期类型 {self._target_type.__name__}: {e}"
            ) from e

    @property
    def generated_instructions(self) -> str:
        """获取生成的指令"""
        return self._generated_instructions

    @property
    def target_type(self) -> type[Any]:
        """获取目标类型"""
        return self._target_type

    @classmethod
    def for_pydantic_model(
        cls,
        model_class: type[BaseModel],
        **kwargs
    ) -> "JsonObjectOutputSchema":
        """为 Pydantic 模型创建 JsonObjectOutputSchema"""
        return cls(target_type=model_class, **kwargs)

    @classmethod
    def for_dataclass(
        cls,
        dataclass_type: type[Any],
        **kwargs
    ) -> "JsonObjectOutputSchema":
        """为 dataclass 创建 JsonObjectOutputSchema"""
        return cls(target_type=dataclass_type, **kwargs)

    @classmethod
    def for_typed_dict(
        cls,
        typed_dict_type: type[Any],
        **kwargs
    ) -> "JsonObjectOutputSchema":
        """为 TypedDict 创建 JsonObjectOutputSchema"""
        return cls(target_type=typed_dict_type, **kwargs)

    @classmethod
    def cleanup_cache(cls, max_size: int = 100) -> None:
        """清理缓存（如果需要）"""
        if len(cls._validator_cache) > max_size:
            # 简单的 LRU 策略：清理一半
            items = list(cls._validator_cache.items())
            cls._validator_cache = dict(items[len(items)//2:])
            logger.info(f"清理验证器缓存，保留 {len(cls._validator_cache)} 项")
