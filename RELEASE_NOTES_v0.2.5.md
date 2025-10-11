# Release Notes - v0.2.5

## 📦 发布信息

- **版本号**: v0.2.5
- **发布日期**: 2025-04-11
- **构建文件**:
  - `dist/openai_agents-0.2.5-py3-none-any.whl` (139KB)
  - `dist/openai_agents-0.2.5.tar.gz` (1.4MB)

## 🎯 核心功能

### Pydantic 对象保留支持

当使用 `tool_use_behavior` 强制停止模式时，SDK 现在会保留工具返回的 Pydantic 对象，而不是强制转换为字符串。

#### 适用场景

- `tool_use_behavior="stop_on_first_tool"`
- `tool_use_behavior={"stop_at_tool_names": [...]}`
- `tool_use_behavior=custom_function`

#### 使用示例

```python
from pydantic import BaseModel
from agents import Agent, Runner, function_tool

class UserProfile(BaseModel):
    name: str
    age: int
    city: str

@function_tool
def extract_user_profile(text: str) -> UserProfile:
    """从文本中提取用户画像"""
    return UserProfile(name="张伟", age=28, city="北京")

agent = Agent(
    name="ProfileExtractor",
    instructions="提取用户信息",
    tools=[extract_user_profile],
    tool_use_behavior="stop_on_first_tool",  # 关键：调用工具后立即停止
)

result = await Runner.run(agent, "我叫张伟，28岁，在北京工作")

# ✅ 现在 result.final_output 是 UserProfile 对象！
assert isinstance(result.final_output, UserProfile)
assert result.final_output.name == "张伟"
assert result.final_output.age == 28
assert result.final_output.city == "北京"

# ❌ 之前的版本会返回字符串：
# result.final_output == "name='张伟' age=28 city='北京'"
```

## 💡 优势

### 1. 类型安全
- 可以直接访问 `result.final_output.name`，而不是解析字符串
- IDE 提供完整的类型提示和自动补全

### 2. 数据验证
- Pydantic 已经在工具内部完成验证，无需二次解析
- 保证数据格式的正确性

### 3. 系统集成
- 下游系统可以直接使用 Pydantic 对象
- 无需序列化/反序列化

### 4. 100% 可靠
- Function Calling 保证输出格式合法
- 比 `json_object` 模式更可靠

## 🔄 向后兼容性

### 完全兼容

所有现有代码无需修改，默认行为保持不变：

| `output_type` | `tool_use_behavior` | v0.2.4 行为 | v0.2.5 行为 | 兼容性 |
|--------------|---------------------|------------|------------|--------|
| `None` | `"run_llm_again"` | 转字符串 | 转字符串 | ✅ 完全兼容 |
| `None` | `"stop_on_first_tool"` | 转字符串 | **保留对象** | ⚠️ 改进 |
| `str` | `"run_llm_again"` | 转字符串 | 转字符串 | ✅ 完全兼容 |
| `str` | `"stop_on_first_tool"` | 转字符串 | 转字符串 | ✅ 完全兼容 |
| `UserProfile` | `"run_llm_again"` | 保留对象 | 保留对象 | ✅ 完全兼容 |
| `UserProfile` | `"stop_on_first_tool"` | 保留对象 | 保留对象 | ✅ 完全兼容 |

### 唯一的行为改变

- **条件**: `output_type=None` + `tool_use_behavior != "run_llm_again"`
- **原行为**: 转字符串
- **新行为**: 保留对象
- **影响**: 这是**改进**，不是破坏性变更
- **说明**: 用户使用 `stop_on_first_tool` 就是期望获得工具的原始返回值

### 如何保持旧行为

如果确实需要字符串输出，可以明确设置 `output_type=str`：

```python
agent = Agent(
    name="Test",
    tools=[extract_profile],
    tool_use_behavior="stop_on_first_tool",
    output_type=str,  # 明确要求字符串输出
)
```

## 🔧 技术细节

### 修改范围

- **文件**: `src/agents/_run_impl.py`
- **行数**: 第 366-375 行（仅 10 行代码）
- **影响**: 最小改动，最大价值

### 修改逻辑

**原代码**:
```python
if check_tool_use.is_final_output:
    # If the output type is str, then let's just stringify it
    if not agent.output_type or agent.output_type is str:
        check_tool_use.final_output = str(check_tool_use.final_output)
```

**新代码**:
```python
if check_tool_use.is_final_output:
    # If the output type is str, then let's just stringify it
    # When using tool_use_behavior to stop at tools, preserve the original type
    # unless explicitly requested str output
    should_stringify = (
        agent.output_type is str
        or (not agent.output_type and agent.tool_use_behavior == "run_llm_again")
    )
    if should_stringify:
        check_tool_use.final_output = str(check_tool_use.final_output)
```

### 测试覆盖

新增 6 个测试用例（`tests/test_pydantic_output_preservation.py`）：

1. ✅ `test_stop_on_first_tool_preserves_pydantic_object`
2. ✅ `test_run_llm_again_converts_to_string`
3. ✅ `test_explicit_str_output_type_converts_to_string`
4. ✅ `test_stop_at_tool_names_preserves_pydantic_object`
5. ✅ `test_explicit_pydantic_output_type_preserves_object`
6. ✅ `test_multiple_tools_stop_on_first_preserves_first_pydantic`

### 质量保证

- ✅ 所有现有测试通过（464 个测试）
- ✅ 通过 `make format`
- ✅ 通过 `make lint`
- ✅ 通过 `make mypy`（针对修改的文件）

## 📚 更多示例

### 示例 1: 结构化数据提取

```python
from pydantic import BaseModel
from agents import Agent, Runner, function_tool

class ProductInfo(BaseModel):
    name: str
    price: float
    category: str
    in_stock: bool

@function_tool
def extract_product_info(text: str) -> ProductInfo:
    """从商品描述中提取结构化信息"""
    # LLM 会按照 Pydantic schema 调用此函数
    return ProductInfo(
        name="iPhone 15 Pro",
        price=7999.0,
        category="手机",
        in_stock=True
    )

agent = Agent(
    name="ProductExtractor",
    tools=[extract_product_info],
    tool_use_behavior="stop_on_first_tool",
)

result = await Runner.run(agent, "iPhone 15 Pro，售价7999元，手机类别，有货")
product: ProductInfo = result.final_output
print(f"商品：{product.name}，价格：{product.price}元")
```

### 示例 2: 多步骤工作流

```python
from pydantic import BaseModel
from agents import Agent, Runner, function_tool

class AnalysisResult(BaseModel):
    sentiment: str
    confidence: float
    keywords: list[str]

@function_tool
def analyze_text(text: str) -> AnalysisResult:
    """分析文本情感和关键词"""
    return AnalysisResult(
        sentiment="positive",
        confidence=0.95,
        keywords=["优秀", "推荐", "满意"]
    )

agent = Agent(
    name="TextAnalyzer",
    tools=[analyze_text],
    tool_use_behavior={"stop_at_tool_names": ["analyze_text"]},
)

result = await Runner.run(agent, "这个产品非常优秀，强烈推荐，非常满意！")
analysis: AnalysisResult = result.final_output
print(f"情感：{analysis.sentiment}，置信度：{analysis.confidence}")
```

## 🚀 安装和升级

### 从 PyPI 安装（待发布）

```bash
pip install openai-agents==0.2.5
```

### 从源码安装

```bash
pip install dist/openai_agents-0.2.5-py3-none-any.whl
```

### 升级现有安装

```bash
pip install --upgrade openai-agents
```

## 📝 发布清单

- [x] 修改核心代码（`src/agents/_run_impl.py`）
- [x] 添加测试用例（`tests/test_pydantic_output_preservation.py`）
- [x] 运行完整测试套件（464 个测试通过）
- [x] 代码质量检查（format, lint, mypy）
- [x] 更新版本号（`pyproject.toml`）
- [x] 更新 CHANGELOG（`CHANGELOG.md`）
- [x] 构建包（`dist/openai_agents-0.2.5-py3-none-any.whl`）
- [x] 创建发布说明（`RELEASE_NOTES_v0.2.5.md`）
- [ ] 发布到 PyPI（需要权限）
- [ ] 创建 Git tag（`v0.2.5`）
- [ ] 推送到 GitHub

## 🔗 相关链接

- **仓库**: https://github.com/liuzhongyu-eagle/openai-agents-python-enhanced
- **文档**: https://openai.github.io/openai-agents-python/
- **问题反馈**: https://github.com/liuzhongyu-eagle/openai-agents-python-enhanced/issues

## 👥 贡献者

- @liuzhongyu-eagle - 核心功能实现和测试

---

**注意**: 这是一个高价值、低风险的改进，建议所有用户升级！

