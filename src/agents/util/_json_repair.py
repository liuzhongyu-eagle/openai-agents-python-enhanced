"""
JSON 修复工具模块

提供 LLM 输出的 JSON 字符串修复功能，处理各种可能的格式异常。
使用 json-repair 库来修复常见的 JSON 格式问题。
"""

import json
import logging
from typing import Any, Optional

from pydantic import TypeAdapter, ValidationError

try:
    import json_repair
    JSON_REPAIR_AVAILABLE = True
except ImportError:
    JSON_REPAIR_AVAILABLE = False

from ..exceptions import ModelBehaviorError
from ..tracing import SpanError
from ._error_tracing import attach_error_to_current_span

logger = logging.getLogger(__name__)


class JsonRepairResult:
    """JSON 修复结果"""

    def __init__(
        self,
        success: bool,
        repaired_json: Optional[str] = None,
        parsed_object: Optional[Any] = None,
        original_error: Optional[Exception] = None,
        repair_applied: bool = False,
        repair_details: Optional[str] = None
    ):
        self.success = success
        self.repaired_json = repaired_json
        self.parsed_object = parsed_object
        self.original_error = original_error
        self.repair_applied = repair_applied
        self.repair_details = repair_details


def repair_and_validate_json(
    json_str: str,
    type_adapter: Optional[TypeAdapter[Any]] = None,
    enable_repair: bool = True,
    max_repair_attempts: int = 3
) -> JsonRepairResult:
    """
    修复并验证 JSON 字符串

    Args:
        json_str: 原始 JSON 字符串
        type_adapter: Pydantic TypeAdapter，用于类型验证
        enable_repair: 是否启用 JSON 修复
        max_repair_attempts: 最大修复尝试次数

    Returns:
        JsonRepairResult: 修复结果
    """
    logger.debug(f"开始修复和验证 JSON: {json_str[:100]}...")

    # 首先尝试直接解析原始 JSON
    try:
        parsed_obj = json.loads(json_str)
        logger.debug("原始 JSON 解析成功，无需修复")

        # 如果有类型适配器，进行类型验证
        if type_adapter:
            try:
                validated_obj = type_adapter.validate_python(parsed_obj)
                return JsonRepairResult(
                    success=True,
                    repaired_json=json_str,
                    parsed_object=validated_obj,
                    repair_applied=False
                )
            except ValidationError as e:
                logger.debug(f"原始 JSON 类型验证失败: {e}")
                return JsonRepairResult(
                    success=False,
                    original_error=e,
                    repair_applied=False
                )
        else:
            return JsonRepairResult(
                success=True,
                repaired_json=json_str,
                parsed_object=parsed_obj,
                repair_applied=False
            )

    except json.JSONDecodeError as original_error:
        logger.debug(f"原始 JSON 解析失败: {original_error}")

        # 如果禁用修复或修复库不可用，直接返回失败
        if not enable_repair or not JSON_REPAIR_AVAILABLE:
            logger.warning("JSON 修复被禁用或 json-repair 库不可用")
            return JsonRepairResult(
                success=False,
                original_error=original_error,
                repair_applied=False
            )

        # 尝试修复 JSON
        return _attempt_json_repair(
            json_str,
            type_adapter,
            original_error,
            max_repair_attempts
        )


def _attempt_json_repair(
    json_str: str,
    type_adapter: Optional[TypeAdapter[Any]],
    original_error: Exception,
    max_attempts: int
) -> JsonRepairResult:
    """
    尝试修复 JSON 字符串

    Args:
        json_str: 原始 JSON 字符串
        type_adapter: 类型适配器
        original_error: 原始解析错误
        max_attempts: 最大尝试次数

    Returns:
        JsonRepairResult: 修复结果
    """
    logger.debug(f"开始尝试修复 JSON，最大尝试次数: {max_attempts}")

    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(f"第 {attempt} 次修复尝试")

            # 使用 json-repair 修复 JSON
            if attempt == 1:
                # 第一次尝试：基本修复
                repaired_json = json_repair.repair_json(json_str)
                repair_method = "基本修复"
            elif attempt == 2:
                # 第二次尝试：使用 loads 方法（更激进的修复）
                try:
                    repaired_obj = json_repair.loads(json_str)
                    repaired_json = json.dumps(repaired_obj, ensure_ascii=False)
                    repair_method = "loads 方法修复"
                except Exception:
                    # 如果 loads 失败，回退到基本修复
                    repaired_json = json_repair.repair_json(json_str)
                    repair_method = "基本修复（loads 失败后回退）"
            else:
                # 第三次尝试：返回对象模式
                try:
                    repaired_obj = json_repair.repair_json(json_str, return_objects=True)
                    if repaired_obj is not None:
                        repaired_json = json.dumps(repaired_obj, ensure_ascii=False)
                        repair_method = "返回对象模式修复"
                    else:
                        logger.warning("json-repair 返回了空对象")
                        break
                except Exception as e:
                    logger.warning(f"返回对象模式修复失败: {e}")
                    break

            # 检查修复结果是否为空
            if not repaired_json or repaired_json.strip() == "":
                logger.warning(f"第 {attempt} 次修复返回空字符串")
                continue

            logger.debug(f"修复后的 JSON: {repaired_json[:100]}...")

            # 验证修复后的 JSON
            try:
                parsed_obj = json.loads(repaired_json)
                logger.debug(f"修复后的 JSON 解析成功，使用方法: {repair_method}")

                # 如果有类型适配器，进行类型验证
                if type_adapter:
                    try:
                        validated_obj = type_adapter.validate_python(parsed_obj)
                        logger.info(f"JSON 修复成功，方法: {repair_method}，尝试次数: {attempt}")
                        return JsonRepairResult(
                            success=True,
                            repaired_json=repaired_json,
                            parsed_object=validated_obj,
                            repair_applied=True,
                            repair_details=f"{repair_method}（第{attempt}次尝试）"
                        )
                    except ValidationError as e:
                        logger.debug(f"修复后的 JSON 类型验证失败: {e}")
                        # 继续尝试下一种修复方法
                        continue
                else:
                    logger.info(f"JSON 修复成功，方法: {repair_method}，尝试次数: {attempt}")
                    return JsonRepairResult(
                        success=True,
                        repaired_json=repaired_json,
                        parsed_object=parsed_obj,
                        repair_applied=True,
                        repair_details=f"{repair_method}（第{attempt}次尝试）"
                    )

            except json.JSONDecodeError as e:
                logger.debug(f"第 {attempt} 次修复后仍无法解析 JSON: {e}")
                continue

        except Exception as e:
            logger.warning(f"第 {attempt} 次修复过程中出现异常: {e}")
            continue

    # 所有修复尝试都失败了
    logger.error(f"JSON 修复失败，已尝试 {max_attempts} 次")
    return JsonRepairResult(
        success=False,
        original_error=original_error,
        repair_applied=True,
        repair_details=f"修复失败，已尝试 {max_attempts} 次"
    )


def validate_json_with_repair(
    json_str: str,
    type_adapter: TypeAdapter[Any],
    enable_repair: bool = True,
    partial: bool = False
) -> Any:
    """
    带修复功能的 JSON 验证（兼容现有 _json.validate_json 接口）

    Args:
        json_str: JSON 字符串
        type_adapter: Pydantic TypeAdapter
        enable_repair: 是否启用修复
        partial: 是否允许部分验证

    Returns:
        验证后的 Python 对象

    Raises:
        ModelBehaviorError: 当 JSON 无效且修复失败时
    """
    # 如果启用了部分验证，使用原有逻辑（不进行修复）
    if partial:
        from . import _json
        return _json.validate_json(json_str, type_adapter, partial=True)

    # 尝试修复和验证
    result = repair_and_validate_json(
        json_str=json_str,
        type_adapter=type_adapter,
        enable_repair=enable_repair
    )

    if result.success:
        if result.repair_applied:
            logger.info(f"JSON 修复成功: {result.repair_details}")
        return result.parsed_object
    else:
        # 修复失败，记录错误并抛出异常
        attach_error_to_current_span(
            SpanError(
                message="JSON 解析和修复失败",
                data={
                    "original_json": json_str[:200],
                    "repair_attempted": result.repair_applied,
                    "repair_details": result.repair_details
                },
            )
        )

        error_msg = f"JSON 解析失败，原始错误: {result.original_error}"
        if result.repair_applied:
            error_msg += f"，修复尝试也失败: {result.repair_details}"

        raise ModelBehaviorError(error_msg) from result.original_error
