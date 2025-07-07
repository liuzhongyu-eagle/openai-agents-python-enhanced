import abc
from dataclasses import dataclass
from typing import Any, Optional

from pydantic import BaseModel, TypeAdapter
from typing_extensions import TypedDict, get_args, get_origin

from .exceptions import ModelBehaviorError, UserError
from .strict_schema import ensure_strict_json_schema
from .tracing import SpanError
from .util import _error_tracing
from .util._json_repair import validate_json_with_repair

_WRAPPER_DICT_KEY = "response"


class AgentOutputSchemaBase(abc.ABC):
    """An object that captures the JSON schema of the output, as well as validating/parsing JSON
    produced by the LLM into the output type.
    """

    @abc.abstractmethod
    def is_plain_text(self) -> bool:
        """Whether the output type is plain text (versus a JSON object)."""
        pass

    @abc.abstractmethod
    def name(self) -> str:
        """The name of the output type."""
        pass

    @abc.abstractmethod
    def json_schema(self) -> dict[str, Any]:
        """Returns the JSON schema of the output. Will only be called if the output type is not
        plain text.
        """
        pass

    @abc.abstractmethod
    def is_strict_json_schema(self) -> bool:
        """Whether the JSON schema is in strict mode. Strict mode constrains the JSON schema
        features, but guarantees valid JSON. See here for details:
        https://platform.openai.com/docs/guides/structured-outputs#supported-schemas
        """
        pass

    @abc.abstractmethod
    def validate_json(self, json_str: str) -> Any:
        """Validate a JSON string against the output type. You must return the validated object,
        or raise a `ModelBehaviorError` if the JSON is invalid.
        """
        pass


@dataclass(init=False)
class AgentOutputSchema(AgentOutputSchemaBase):
    """An object that captures the JSON schema of the output, as well as validating/parsing JSON
    produced by the LLM into the output type.
    """

    output_type: type[Any]
    """The type of the output."""

    _type_adapter: TypeAdapter[Any]
    """A type adapter that wraps the output type, so that we can validate JSON."""

    _is_wrapped: bool
    """Whether the output type is wrapped in a dictionary. This is generally done if the base
    output type cannot be represented as a JSON Schema object.
    """

    _output_schema: dict[str, Any]
    """The JSON schema of the output."""

    _strict_json_schema: bool
    """Whether the JSON schema is in strict mode. We **strongly** recommend setting this to True,
    as it increases the likelihood of correct JSON input.
    """

    def __init__(
        self,
        output_type: type[Any],
        strict_json_schema: bool = True,
        fallback_to_json_object: bool = False,
        enable_json_repair: bool = True
    ):
        """
        Args:
            output_type: The type of the output.
            strict_json_schema: Whether the JSON schema is in strict mode. We **strongly** recommend
                setting this to True, as it increases the likelihood of correct JSON input.
            fallback_to_json_object: Whether to automatically fallback to json_object mode when
                the model doesn't support json_schema. This enables smart fallback compatibility.
            enable_json_repair: Whether to enable JSON repair functionality for malformed JSON.
        """
        self.output_type = output_type
        self._strict_json_schema = strict_json_schema
        self.fallback_to_json_object = fallback_to_json_object
        self._enable_json_repair = enable_json_repair

        if output_type is None or output_type is str:
            self._is_wrapped = False
            self._type_adapter = TypeAdapter(output_type)
            self._output_schema = self._type_adapter.json_schema()
            return

        # We should wrap for things that are not plain text, and for things that would definitely
        # not be a JSON Schema object.
        self._is_wrapped = not _is_subclass_of_base_model_or_dict(output_type)

        if self._is_wrapped:
            OutputType = TypedDict(
                "OutputType",
                {
                    _WRAPPER_DICT_KEY: output_type,  # type: ignore
                },
            )
            self._type_adapter = TypeAdapter(OutputType)
            self._output_schema = self._type_adapter.json_schema()
        else:
            self._type_adapter = TypeAdapter(output_type)
            self._output_schema = self._type_adapter.json_schema()

        if self._strict_json_schema:
            try:
                self._output_schema = ensure_strict_json_schema(self._output_schema)
            except UserError as e:
                raise UserError(
                    "Strict JSON schema is enabled, but the output type is not valid. "
                    "Either make the output type strict, or pass output_schema_strict=False to "
                    "your Agent()"
                ) from e

    def is_plain_text(self) -> bool:
        """Whether the output type is plain text (versus a JSON object)."""
        return self.output_type is None or self.output_type is str

    def is_strict_json_schema(self) -> bool:
        """Whether the JSON schema is in strict mode."""
        return self._strict_json_schema

    def get_system_prompt_injection(self) -> str:
        """
        获取需要注入到系统提示词中的指令

        当启用智能降级且模型不支持 json_schema 时，
        需要将 schema 定义注入到系统提示词中。

        Returns:
            str: 需要注入到系统提示词中的指令文本
        """
        if not self.fallback_to_json_object:
            return ""

        # 导入指令生成器（避免循环导入）
        try:
            from .json_object_output import InstructionGenerator
            return InstructionGenerator.generate_json_instructions(
                target_type=self.output_type,
                language="zh",  # 默认使用中文
                include_examples=True
            )
        except ImportError:
            return ""

    def should_inject_to_system_prompt(self, model=None) -> bool:
        """
        判断是否需要将指令注入到系统提示词中

        Args:
            model: 模型实例，用于检测能力

        Returns:
            bool: 是否需要注入到系统提示词
        """
        if not self.fallback_to_json_object:
            return False

        if model is None:
            return False

        # 导入能力检测器（避免循环导入）
        try:
            from .json_object_output import ModelCapabilityDetector
            # 如果模型不支持 json_schema，则需要注入
            return not ModelCapabilityDetector.supports_json_schema(model)
        except ImportError:
            return False

    def json_schema(self) -> dict[str, Any]:
        """The JSON schema of the output type."""
        if self.is_plain_text():
            raise UserError("Output type is plain text, so no JSON schema is available")
        return self._output_schema

    def validate_json(self, json_str: str, enable_repair: Optional[bool] = None) -> Any:
        """Validate a JSON string against the output type. Returns the validated object, or raises
        a `ModelBehaviorError` if the JSON is invalid.

        Args:
            json_str: JSON string to validate
            enable_repair: Whether to enable JSON repair functionality
                (None to use instance setting)
        """
        # 使用实例配置或参数指定的修复设置
        repair_enabled = enable_repair if enable_repair is not None else self._enable_json_repair

        # 使用带修复功能的验证
        validated = validate_json_with_repair(
            json_str,
            self._type_adapter,
            enable_repair=repair_enabled,
            partial=False
        )
        if self._is_wrapped:
            if not isinstance(validated, dict):
                _error_tracing.attach_error_to_current_span(
                    SpanError(
                        message="Invalid JSON",
                        data={"details": f"Expected a dict, got {type(validated)}"},
                    )
                )
                raise ModelBehaviorError(
                    f"Expected a dict, got {type(validated)} for JSON: {json_str}"
                )

            if _WRAPPER_DICT_KEY not in validated:
                _error_tracing.attach_error_to_current_span(
                    SpanError(
                        message="Invalid JSON",
                        data={"details": f"Could not find key {_WRAPPER_DICT_KEY} in JSON"},
                    )
                )
                raise ModelBehaviorError(
                    f"Could not find key {_WRAPPER_DICT_KEY} in JSON: {json_str}"
                )
            return validated[_WRAPPER_DICT_KEY]
        return validated

    def name(self) -> str:
        """The name of the output type."""
        return _type_to_str(self.output_type)


def _is_subclass_of_base_model_or_dict(t: Any) -> bool:
    if not isinstance(t, type):
        return False

    # If it's a generic alias, 'origin' will be the actual type, e.g. 'list'
    origin = get_origin(t)

    allowed_types = (BaseModel, dict)
    # If it's a generic alias e.g. list[str], then we should check the origin type i.e. list
    return issubclass(origin or t, allowed_types)


def _type_to_str(t: type[Any]) -> str:
    origin = get_origin(t)
    args = get_args(t)

    if origin is None:
        # It's a simple type like `str`, `int`, etc.
        return t.__name__
    elif args:
        args_str = ", ".join(_type_to_str(arg) for arg in args)
        return f"{origin.__name__}[{args_str}]"
    else:
        return str(t)
