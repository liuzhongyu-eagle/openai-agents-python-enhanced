# Agent 结构化输出兼容性增强技术设计文档

## 1. 设计概述

### 1.1 设计目标
为 OpenAI Agents SDK 提供对仅支持 `{'type': 'json_object'}` 格式的 LLM 供应商的兼容性支持，同时保持现有功能的完整性和向后兼容性。

### 1.2 核心原则
- **优先使用最佳方案**：默认使用 `json_schema`，仅在必要时降级到 `json_object`
- **最小侵入性**：不修改现有核心代码，通过扩展实现新功能
- **向后兼容**：完全兼容现有 API 和使用方式
- **智能适配**：自动检测供应商能力并选择最佳输出格式
- **类型安全**：保持完整的类型提示和验证
- **性能优先**：确保新功能不显著影响性能，`json_schema` 模式性能更优

### 1.3 架构概览
```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Layer                              │
├─────────────────────────────────────────────────────────────┤
│  AgentOutputSchemaBase (抽象基类)                           │
│  ├── AgentOutputSchema (增强：支持智能降级)                 │
│  └── JsonObjectOutputSchema (兼容性：显式 json_object)      │
├─────────────────────────────────────────────────────────────┤
│              智能降级决策层 (新增)                          │
│  ├── ModelCapabilityDetector (供应商能力检测)              │
│  └── FallbackStrategy (降级策略)                           │
├─────────────────────────────────────────────────────────────┤
│                 Converter Layer (增强)                     │
│  ├── ChatCompletion Converter (支持智能降级)               │
│  └── Responses Converter (支持智能降级)                     │
├─────────────────────────────────────────────────────────────┤
│                   Model Layer                               │
│  ├── 高级模型 (支持 json_schema) ← 优先使用                │
│  └── 基础模型 (仅支持 json_object) ← 降级使用              │
└─────────────────────────────────────────────────────────────┘

决策流程：
1. 默认尝试 json_schema (更好的性能和准确性)
2. 检测供应商能力
3. 如果不支持，自动降级到 json_object
4. 生成相应的指令和验证逻辑
```

## 2. 详细设计

### 2.1 JsonObjectOutputSchema 类设计

#### 2.1.1 类定义
```python
from typing import Any, Type, Optional, Dict
from pydantic import TypeAdapter, ValidationError
from agents.agent_output import AgentOutputSchemaBase
from agents.exceptions import ModelBehaviorError

class JsonObjectOutputSchema(AgentOutputSchemaBase):
    """
    兼容仅支持 json_object 格式的 LLM 供应商的输出模式。
    
    该类向 LLM 供应商声明输出格式为通用 JSON 对象，
    同时在本地进行严格的类型验证。
    """
    
    def __init__(
        self,
        target_type: Type[Any],
        *,
        instruction_language: str = "zh",
        include_examples: bool = True,
        custom_instructions: Optional[str] = None,
        validation_mode: str = "strict"
    ):
        """
        初始化 JsonObjectOutputSchema。
        
        Args:
            target_type: 目标 Python 类型（Pydantic 模型、dataclass 等）
            instruction_language: 指令语言（"zh", "en"）
            include_examples: 是否在指令中包含示例
            custom_instructions: 自定义指令（覆盖自动生成的指令）
            validation_mode: 验证模式（"strict", "lenient"）
        """
```

#### 2.1.2 核心方法实现
```python
def is_plain_text(self) -> bool:
    """返回 False，表示输出是 JSON 对象而非纯文本。"""
    return False

def name(self) -> str:
    """返回模式名称，用于日志和调试。"""
    return f"JsonObjectOutputSchema({self._target_type.__name__})"

def json_schema(self) -> Dict[str, Any]:
    """
    返回传递给 LLM 供应商的 JSON Schema。
    对于 json_object 模式，返回通用对象定义。
    """
    return {"type": "object"}

def is_strict_json_schema(self) -> bool:
    """返回 False，因为不使用严格的 JSON Schema。"""
    return False

def validate_json(self, json_str: str) -> Any:
    """
    验证 LLM 生成的 JSON 字符串。
    
    Args:
        json_str: LLM 返回的 JSON 字符串
        
    Returns:
        验证后的 Python 对象
        
    Raises:
        ModelBehaviorError: 当 JSON 无效或不符合目标类型时
    """
    try:
        validated_obj = self._type_adapter.validate_json(json_str)
        return validated_obj
    except ValidationError as e:
        raise ModelBehaviorError(
            f"LLM 生成的 JSON 无效，不符合预期类型 {self._target_type.__name__}: {e}"
        ) from e
```

### 2.2 智能指令生成系统

#### 2.2.1 指令生成器设计
```python
class InstructionGenerator:
    """为 JsonObjectOutputSchema 生成智能指令的工具类。"""
    
    @staticmethod
    def generate_json_instructions(
        target_type: Type[Any],
        language: str = "zh",
        include_examples: bool = True
    ) -> str:
        """
        基于目标类型生成 JSON 输出指令。
        
        Args:
            target_type: 目标 Python 类型
            language: 指令语言
            include_examples: 是否包含示例
            
        Returns:
            生成的指令字符串
        """
        
    @staticmethod
    def _extract_type_info(target_type: Type[Any]) -> Dict[str, Any]:
        """提取类型信息，包括字段、类型、描述等。"""
        
    @staticmethod
    def _generate_example(target_type: Type[Any]) -> str:
        """生成示例 JSON 输出。"""
```

#### 2.2.2 多语言指令模板
```python
INSTRUCTION_TEMPLATES = {
    "zh": {
        "base": "请返回一个严格符合 JSON 格式的对象，包含以下字段：",
        "field": "- {name} ({type}): {description}",
        "example": "示例输出：",
        "format_note": "请确保输出严格符合 JSON 语法，所有字符串值都用双引号包围。"
    },
    "en": {
        "base": "Please return a JSON object with the following fields:",
        "field": "- {name} ({type}): {description}",
        "example": "Example output:",
        "format_note": "Ensure the output strictly follows JSON syntax with all string values in double quotes."
    }
}
```

### 2.3 智能降级机制设计

#### 2.3.1 供应商能力检测
```python
class ModelCapabilityDetector:
    """检测模型供应商的能力。"""

    @staticmethod
    def supports_json_schema(model) -> bool:
        """检测模型是否支持完整的 json_schema。"""
        # 检查模型类型、API 版本等
        if hasattr(model, 'supports_json_schema'):
            return model.supports_json_schema()

        # 基于模型名称或类型的启发式检测
        known_json_schema_models = ['gpt-4', 'gpt-3.5-turbo', 'claude-3']
        return any(name in str(model) for name in known_json_schema_models)
```

#### 2.3.2 Converter 层增强
```python
class Converter:
    @classmethod
    def convert_response_format(
        cls, final_output_schema: AgentOutputSchemaBase | None, model=None
    ) -> ResponseFormat | NotGiven:
        if not final_output_schema or final_output_schema.is_plain_text():
            return NOT_GIVEN

        # 检查是否需要降级
        if (hasattr(final_output_schema, 'fallback_to_json_object') and
            final_output_schema.fallback_to_json_object and
            not ModelCapabilityDetector.supports_json_schema(model)):

            # 降级到 json_object 模式
            return {"type": "json_object"}

        # 默认使用 json_schema 模式
        return {
            "type": "json_schema",
            "json_schema": {
                "name": "final_output",
                "strict": final_output_schema.is_strict_json_schema(),
                "schema": final_output_schema.json_schema(),
            },
        }
```

#### 2.3.3 Agent 类集成
现有的 `Agent` 类无需修改，支持两种使用方式：

```python
# 方式1：显式使用 JsonObjectOutputSchema（适用于明确知道供应商限制的情况）
agent = Agent(
    name="DataProcessor",
    output_type=JsonObjectOutputSchema(UserProfile),
    model=third_party_model
)

# 方式2：使用智能降级（推荐方式）
agent = Agent(
    name="DataProcessor",
    output_type=AgentOutputSchema(UserProfile, fallback_to_json_object=True),
    model=any_model  # 自动适配不同供应商
)
```

### 2.4 性能优化设计

#### 2.4.1 验证器缓存
```python
class JsonObjectOutputSchema(AgentOutputSchemaBase):
    _validator_cache: Dict[Type[Any], TypeAdapter] = {}
    
    def __init__(self, target_type: Type[Any], **kwargs):
        # 使用缓存的验证器以提高性能
        if target_type not in self._validator_cache:
            self._validator_cache[target_type] = TypeAdapter(target_type)
        self._type_adapter = self._validator_cache[target_type]
```

#### 2.4.2 指令缓存
```python
class InstructionGenerator:
    _instruction_cache: Dict[tuple, str] = {}
    
    @staticmethod
    def generate_json_instructions(target_type, language, include_examples):
        cache_key = (target_type, language, include_examples)
        if cache_key not in InstructionGenerator._instruction_cache:
            # 生成并缓存指令
            pass
        return InstructionGenerator._instruction_cache[cache_key]
```

## 3. API 设计

### 3.1 主要 API

#### 3.1.1 JsonObjectOutputSchema 构造函数
```python
def __init__(
    self,
    target_type: Type[Any],
    *,
    instruction_language: str = "zh",
    include_examples: bool = True,
    custom_instructions: Optional[str] = None,
    validation_mode: str = "strict",
    auto_generate_instructions: bool = True
) -> None:
```

#### 3.1.2 便利工厂方法
```python
@classmethod
def for_pydantic_model(
    cls,
    model_class: Type[BaseModel],
    **kwargs
) -> "JsonObjectOutputSchema":
    """为 Pydantic 模型创建 JsonObjectOutputSchema。"""

@classmethod
def for_dataclass(
    cls,
    dataclass_type: Type[Any],
    **kwargs
) -> "JsonObjectOutputSchema":
    """为 dataclass 创建 JsonObjectOutputSchema。"""

@classmethod
def for_typed_dict(
    cls,
    typed_dict_type: Type[Any],
    **kwargs
) -> "JsonObjectOutputSchema":
    """为 TypedDict 创建 JsonObjectOutputSchema。"""
```

### 3.2 智能降级 API

#### 3.2.1 AgentOutputSchema 扩展
```python
class AgentOutputSchema(AgentOutputSchemaBase):
    """扩展现有 AgentOutputSchema 以支持智能降级。"""

    def __init__(
        self,
        output_type: Type[Any],
        strict_json_schema: bool = True,
        fallback_to_json_object: bool = False  # 新增参数
    ):
        """
        Args:
            fallback_to_json_object: 当供应商不支持 json_schema 时，
                                   自动降级到 json_object 模式
        """

#### 3.2.2 全局配置
```python
class JsonObjectConfig:
    """JsonObjectOutputSchema 的全局配置。"""

    default_language: str = "zh"
    default_include_examples: bool = True
    default_validation_mode: str = "strict"
    enable_instruction_cache: bool = True
    enable_validator_cache: bool = True
    enable_smart_fallback: bool = True  # 新增：启用智能降级

    @classmethod
    def set_defaults(cls, **kwargs) -> None:
        """设置全局默认配置。"""
```

## 4. 实现细节

### 4.1 类型支持矩阵

| Python 类型 | 支持状态 | 说明 |
|-------------|----------|------|
| Pydantic BaseModel | ✅ 完全支持 | 推荐使用，支持所有特性 |
| dataclass | ✅ 完全支持 | 支持字段类型和默认值 |
| TypedDict | ✅ 完全支持 | 支持类型提示 |
| NamedTuple | ✅ 基础支持 | 支持基本类型转换 |
| 普通类 | ⚠️ 有限支持 | 需要类型注解 |
| 内置类型 | ✅ 完全支持 | int, str, list, dict 等 |

### 4.2 错误处理策略

#### 4.2.1 验证错误处理
```python
def validate_json(self, json_str: str) -> Any:
    try:
        # 首先尝试解析 JSON
        json_obj = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ModelBehaviorError(
            f"LLM 返回的内容不是有效的 JSON: {e}"
        ) from e
    
    try:
        # 然后进行类型验证
        validated_obj = self._type_adapter.validate_python(json_obj)
        return validated_obj
    except ValidationError as e:
        if self._validation_mode == "lenient":
            # 宽松模式：尝试部分验证
            return self._lenient_validation(json_obj, e)
        else:
            # 严格模式：抛出错误
            raise ModelBehaviorError(
                f"JSON 结构不符合预期类型 {self._target_type.__name__}: {e}"
            ) from e
```

#### 4.2.2 降级策略
```python
def _lenient_validation(self, json_obj: Any, error: ValidationError) -> Any:
    """宽松验证模式的降级策略。"""
    # 尝试提取可用的字段
    # 记录警告日志
    # 返回部分验证的对象
```

### 4.3 日志和调试支持

#### 4.3.1 详细日志
```python
import logging

logger = logging.getLogger("agents.json_object_output")

class JsonObjectOutputSchema(AgentOutputSchemaBase):
    def validate_json(self, json_str: str) -> Any:
        logger.debug(f"开始验证 JSON: {json_str[:100]}...")
        
        try:
            result = self._type_adapter.validate_json(json_str)
            logger.debug(f"验证成功，返回类型: {type(result)}")
            return result
        except ValidationError as e:
            logger.error(f"验证失败: {e}")
            raise
```

#### 4.3.2 调试工具
```python
class JsonObjectDebugger:
    """JsonObjectOutputSchema 的调试工具。"""
    
    @staticmethod
    def analyze_validation_error(
        json_str: str,
        target_type: Type[Any],
        error: ValidationError
    ) -> Dict[str, Any]:
        """分析验证错误并提供诊断信息。"""
        
    @staticmethod
    def suggest_fixes(
        json_str: str,
        target_type: Type[Any]
    ) -> List[str]:
        """为常见问题提供修复建议。"""
```

## 5. 测试策略

### 5.1 单元测试覆盖

#### 5.1.1 核心功能测试
- JsonObjectOutputSchema 基本功能
- 各种 Python 类型的支持
- 验证逻辑的正确性
- 错误处理的完整性

#### 5.1.2 性能测试
- 验证器缓存效果
- 指令生成性能
- 内存使用情况
- 并发安全性

#### 5.1.3 集成测试
- 与现有 Agent 系统的集成
- 与不同模型供应商的兼容性
- 端到端功能验证

### 5.2 测试用例设计

#### 5.2.1 正常流程测试
```python
def test_basic_pydantic_model():
    """测试基本 Pydantic 模型的支持。"""
    
def test_complex_nested_types():
    """测试复杂嵌套类型的支持。"""
    
def test_instruction_generation():
    """测试指令生成的正确性。"""
```

#### 5.2.2 异常情况测试
```python
def test_invalid_json_handling():
    """测试无效 JSON 的处理。"""
    
def test_type_mismatch_handling():
    """测试类型不匹配的处理。"""
    
def test_partial_data_handling():
    """测试部分数据的处理。"""
```

## 6. 部署和发布

### 6.1 发布策略
1. **Alpha 版本**：内部测试，验证核心功能
2. **Beta 版本**：邀请部分用户测试，收集反馈
3. **正式版本**：全面发布，提供完整文档

### 6.2 向后兼容性保证
- 不修改现有 API
- 不改变现有行为
- 新功能通过新类提供
- 提供迁移指南

### 6.3 文档更新
- API 文档更新
- 使用示例添加
- 最佳实践指南
- 故障排除指南

## 7. 监控和维护

### 7.1 性能监控
- 验证延迟监控
- 内存使用监控
- 错误率监控
- 用户采用率监控

### 7.2 质量保证
- 自动化测试流水线
- 代码质量检查
- 性能回归测试
- 用户反馈收集

## 8. 实现示例

### 8.1 基本使用示例

#### 8.1.1 Pydantic 模型示例
```python
from pydantic import BaseModel, Field
from agents import Agent, Runner
from agents.extensions.json_object_output import JsonObjectOutputSchema

class UserProfile(BaseModel):
    """用户个人资料信息。"""
    name: str = Field(description="用户的姓名")
    age: int = Field(description="用户的年龄", ge=0, le=150)
    city: str = Field(description="用户居住的城市")
    is_active: bool = Field(description="用户当前是否活跃")

# 创建兼容 json_object 的输出模式
output_schema = JsonObjectOutputSchema(
    target_type=UserProfile,
    instruction_language="zh",
    include_examples=True
)

# 创建 Agent
agent = Agent(
    name="UserProfileAgent",
    instructions="您是一位生成用户资料的助手。",
    output_type=output_schema,
    model=ThirdPartyModel()  # 仅支持 json_object 的供应商
)

# 运行 Agent
async def main():
    result = await Runner.run(agent, "请为张三生成一份用户资料")
    print(f"结果类型: {type(result.final_output)}")
    print(f"用户姓名: {result.final_output.name}")
    print(f"用户年龄: {result.final_output.age}")
```

#### 8.1.2 Dataclass 示例
```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class TaskItem:
    """任务项目。"""
    title: str
    description: str
    priority: int  # 1-5, 5 为最高优先级
    completed: bool = False
    tags: Optional[List[str]] = None

# 使用便利工厂方法
output_schema = JsonObjectOutputSchema.for_dataclass(
    TaskItem,
    instruction_language="en",
    include_examples=True
)

agent = Agent(
    name="TaskManager",
    instructions="You are a task management assistant.",
    output_type=output_schema
)
```

### 8.2 智能降级配置示例

#### 8.2.1 推荐的智能降级配置
```python
# 推荐方式：使用智能降级，优先 json_schema，必要时降级到 json_object
agent = Agent(
    name="SmartAgent",
    instructions="您是一位智能助手，请返回结构化数据。",
    output_type=AgentOutputSchema(
        UserProfile,
        fallback_to_json_object=True  # 启用智能降级
    ),
    model=any_model  # 适配任何供应商
)

# 运行时会自动选择最佳格式：
# - 如果模型支持 json_schema：使用完整的 JSON Schema 验证
# - 如果模型仅支持 json_object：自动降级并生成指令
```

#### 8.2.2 显式 json_object 模式（特殊情况）
```python
# 仅在明确知道供应商限制时使用
custom_instructions = """
请返回一个包含用户信息的 JSON 对象。
必须包含以下字段：
- name: 字符串类型，用户姓名
- age: 数字类型，用户年龄（0-150）
- city: 字符串类型，城市名称
- is_active: 布尔类型，是否活跃

示例：{"name": "李四", "age": 28, "city": "北京", "is_active": true}
"""

output_schema = JsonObjectOutputSchema(
    target_type=UserProfile,
    custom_instructions=custom_instructions,
    validation_mode="lenient"  # 宽松验证模式
)
```

#### 8.2.3 全局智能降级配置
```python
from agents.extensions.json_object_output import JsonObjectConfig

# 设置全局智能降级策略
JsonObjectConfig.set_defaults(
    enable_smart_fallback=True,  # 全局启用智能降级
    default_language="zh",
    default_include_examples=True
)

# 之后创建的所有 Agent 都会自动应用智能降级
agent = Agent(
    name="AutoAgent",
    output_type=UserProfile,  # 简化使用
    model=any_model
)
```

### 8.3 错误处理示例

#### 8.3.1 验证错误处理
```python
from agents.exceptions import ModelBehaviorError

try:
    result = await Runner.run(agent, "生成用户资料")
    print(result.final_output)
except ModelBehaviorError as e:
    print(f"模型输出验证失败: {e}")
    # 可以选择降级处理或重试
```

#### 8.3.2 调试支持
```python
from agents.extensions.json_object_output import JsonObjectDebugger
import logging

# 启用详细日志
logging.getLogger("agents.json_object_output").setLevel(logging.DEBUG)

# 分析验证错误
try:
    result = await Runner.run(agent, input_text)
except ModelBehaviorError as e:
    # 获取诊断信息
    diagnosis = JsonObjectDebugger.analyze_validation_error(
        json_str=e.raw_json,  # 假设异常包含原始 JSON
        target_type=UserProfile,
        error=e.validation_error
    )
    print(f"诊断信息: {diagnosis}")

    # 获取修复建议
    suggestions = JsonObjectDebugger.suggest_fixes(
        json_str=e.raw_json,
        target_type=UserProfile
    )
    print(f"修复建议: {suggestions}")
```

## 9. 迁移指南

### 9.1 从现有 AgentOutputSchema 迁移

#### 9.1.1 简单迁移
```python
# 原有代码
agent = Agent(
    output_type=UserProfile,  # 或 AgentOutputSchema(UserProfile)
    model=openai_model
)

# 迁移后代码（适用于仅支持 json_object 的供应商）
agent = Agent(
    output_type=JsonObjectOutputSchema(UserProfile),
    model=third_party_model
)
```

#### 9.1.2 智能降级迁移（推荐）
```python
# 推荐方式：使用智能降级，一套代码适配所有供应商
def create_agent(model):
    return Agent(
        name="FlexibleAgent",
        output_type=AgentOutputSchema(
            UserProfile,
            fallback_to_json_object=True  # 自动降级
        ),
        model=model  # 任何供应商都可以
    )

# 或者设置全局默认降级策略
JsonObjectConfig.set_defaults(enable_smart_fallback=True)
agent = Agent(
    name="FlexibleAgent",
    output_type=UserProfile,  # 简化使用，自动应用降级策略
    model=any_model
)
```

### 9.2 最佳实践

#### 9.2.1 类型设计建议
```python
# 推荐：使用 Pydantic 模型，提供清晰的字段描述
class RecommendedModel(BaseModel):
    """推荐的模型设计。"""
    field1: str = Field(description="清晰的字段描述")
    field2: int = Field(description="数值字段", ge=0)
    field3: Optional[List[str]] = Field(description="可选列表字段")

# 避免：过于复杂的嵌套结构
class AvoidComplexModel(BaseModel):
    deeply: Dict[str, Dict[str, List[Dict[str, Any]]]]  # 过于复杂
```

#### 9.2.2 指令优化建议
```python
# 推荐：提供具体的输出要求
agent = Agent(
    instructions="""
    您是数据分析助手。请分析用户数据并返回结构化结果。

    输出要求：
    1. 确保所有必填字段都有值
    2. 数值字段必须为有效数字
    3. 布尔字段使用 true/false
    4. 字符串字段不能为空
    """,
    output_type=JsonObjectOutputSchema(AnalysisResult)
)
```

## 10. 性能优化建议

### 10.1 缓存策略
```python
# 在应用启动时预热缓存
def warm_up_cache():
    """预热常用类型的验证器缓存。"""
    common_types = [UserProfile, TaskItem, AnalysisResult]
    for type_class in common_types:
        JsonObjectOutputSchema(type_class)

# 在应用启动时调用
warm_up_cache()
```

### 10.2 内存管理
```python
# 定期清理缓存（如果需要）
def cleanup_cache():
    """清理不常用的缓存项。"""
    JsonObjectOutputSchema.cleanup_cache(max_size=100)

# 在适当的时候调用
cleanup_cache()
```

## 11. 故障排除

### 11.1 常见问题

#### 11.1.1 JSON 格式错误
**问题**：LLM 返回的不是有效 JSON
**解决方案**：
1. 检查指令是否明确要求 JSON 格式
2. 增加输出示例
3. 使用更明确的格式要求

#### 11.1.2 类型验证失败
**问题**：JSON 结构与目标类型不匹配
**解决方案**：
1. 检查类型定义是否合理
2. 使用宽松验证模式
3. 简化类型结构

#### 11.1.3 性能问题
**问题**：验证过程耗时过长
**解决方案**：
1. 启用验证器缓存
2. 简化类型结构
3. 使用异步验证

### 11.2 调试技巧

#### 11.2.1 启用详细日志
```python
import logging
logging.getLogger("agents.json_object_output").setLevel(logging.DEBUG)
```

#### 11.2.2 手动验证
```python
# 手动测试验证逻辑
schema = JsonObjectOutputSchema(UserProfile)
test_json = '{"name": "测试", "age": 25, "city": "北京", "is_active": true}'
try:
    result = schema.validate_json(test_json)
    print(f"验证成功: {result}")
except Exception as e:
    print(f"验证失败: {e}")
```

这个设计文档提供了实现 Agent 结构化输出兼容性增强功能的完整技术方案，包括详细的实现示例、迁移指南和故障排除建议，确保了功能的完整性、性能和可维护性。
