"""
JSON Object 输出兼容性模块

该模块提供对仅支持 {'type': 'json_object'} 格式的 LLM 供应商的兼容性支持。
业务层可以根据模型能力选择使用 JsonObjectOutputSchema 或标准的 AgentOutputSchema。
"""

import json
import logging
from typing import Any, Optional

from pydantic import BaseModel, TypeAdapter

from .agent_output import AgentOutputSchemaBase
from .exceptions import ModelBehaviorError
from .util._json_repair import repair_and_validate_json

logger = logging.getLogger(__name__)





class InstructionGenerator:
    """简化的指令生成器，为 JsonObjectOutputSchema 生成结构化指令"""

    @classmethod
    def generate_json_instructions(
        cls,
        target_type: type[Any],
        custom_instructions: Optional[str] = None
    ) -> str:
        """
        基于目标类型生成 JSON 输出指令

        Args:
            target_type: 目标 Python 类型
            custom_instructions: 自定义指令（如果提供，将附加到 schema 后面）

        Returns:
            str: 生成的指令字符串
        """
        # 获取 JSON Schema
        try:
            adapter = TypeAdapter(target_type)
            schema = adapter.json_schema()
            schema_text = json.dumps(schema, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"无法为类型 {target_type} 生成 JSON Schema: {e}")
            raise ValueError(f"Unsupported type for JSON schema generation: {target_type}") from e

        # 默认的格式要求指令
        default_instructions = (
            "Always respond strictly in the following JSON format "
            "with no additional explanatory text."
        )

        # 组合指令：JSON Schema + 自定义指令（或默认指令）
        instructions = custom_instructions if custom_instructions else default_instructions

        return f"JSON Schema:\n{schema_text}\n\n{instructions}"






class JsonObjectOutputSchema(AgentOutputSchemaBase):
    """
    Compatible output schema for LLM providers that only support {'type': 'json_object'} format.

    This class declares the output format as a generic JSON object to the LLM provider,
    while performing strict type validation locally. Instructions are generated based on
    the user-defined schema and injected into the system prompt.
    """

    def __init__(
        self,
        target_type: type[Any],
        *,
        custom_instructions: Optional[str] = None,
        enable_json_repair: bool = True
    ):
        """
        Initialize JsonObjectOutputSchema

        Args:
            target_type: Target Python type (Pydantic model, dataclass, etc.)
            custom_instructions: Custom instructions (if provided, will override
                auto-generated instructions)
            enable_json_repair: Whether to enable JSON repair functionality
        """
        self._target_type = target_type
        self._custom_instructions = custom_instructions
        self._enable_json_repair = enable_json_repair

        # 初始化验证器
        self._type_adapter = TypeAdapter(target_type)

        # 生成指令
        self._generated_instructions = InstructionGenerator.generate_json_instructions(
            target_type=target_type,
            custom_instructions=custom_instructions
        )



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

    def validate_json(self, json_str: str, enable_repair: Optional[bool] = None) -> Any:
        """
        验证 LLM 生成的 JSON 字符串，支持自动修复

        Args:
            json_str: LLM 返回的 JSON 字符串
            enable_repair: 是否启用 JSON 修复功能（None 时使用实例配置）

        Returns:
            验证后的 Python 对象

        Raises:
            ModelBehaviorError: 当 JSON 无效且修复失败时
        """
        # 使用实例配置或参数指定的修复设置
        repair_enabled = enable_repair if enable_repair is not None else self._enable_json_repair
        logger.debug(
            f"开始验证 JSON（修复功能{'启用' if repair_enabled else '禁用'}）: "
            f"{json_str[:100]}..."
        )

        # 使用带修复功能的验证
        result = repair_and_validate_json(
            json_str=json_str,
            type_adapter=self._type_adapter,
            enable_repair=repair_enabled
        )

        if result.success:
            if result.repair_applied:
                logger.info(f"JSON 修复成功: {result.repair_details}")
            logger.debug(f"验证成功，返回类型: {type(result.parsed_object)}")
            return result.parsed_object
        else:
            # 修复失败，抛出详细错误
            error_msg = f"LLM 生成的 JSON 无效，不符合预期类型 {self._target_type.__name__}"
            if result.repair_applied:
                error_msg += f"，修复尝试失败: {result.repair_details}"
            else:
                error_msg += f"，原始错误: {result.original_error}"

            logger.error(error_msg)
            raise ModelBehaviorError(error_msg) from result.original_error

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


